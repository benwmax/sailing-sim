"""Bakes Galveston Bay (Clear Lake / Kemah to Bolivar Roads, Texas) into game data, chart first.

Inputs (Data/GalvestonBay/raw, fetched by Tools/coast/fetch_galveston.sh):
  - NOAA ENC cells (S-57, enc/ENC_ROOT): depth areas, soundings, contours, dredged channels, land, coastline,
    shoreline constructions, pontoons, bridges, buoys, beacons, lights, landmarks, magnetic variation (public domain)
  - USGS 3DEP 1/3 arc-second DEM (dem_3dep.tif) for the land (NAVD88), public domain
  - NOAA CO-OPS harmonic constituents, datums and predictions (tides/), public domain
  - OpenStreetMap buildings, land use and marina piers (ODbL)
Outputs (Content/TerrainData):
  - GalvestonBay.height : int16 cm above chart datum (MLLW), 10 m grid ("SSHT", same format as the lake)
  - GalvestonBay.trees  : tree density, 20 m grid
  - GalvestonBay.current: tidal current field, 50 m grid ("SSCF")
  - GalvestonBay.json   : grid, sources, docks, bridges, buildings, launch spots, checkpoints, navaids, landmarks,
                          tide and current stations, magnetic variation, and NOAA reference predictions for the tests
  - GalvestonBay.chart.json : the vector chart for the in-game chart view
  - docs/phase-5/terrain-preview.png

Heights are in meters above MLLW (the chart datum): depths on the chart are positive below it. In game the water
surface stands at the predicted tide, so the terrain is shifted by the tide each frame.

Run: Tools/venv/bin/python Tools/coast/build_galveston.py
"""
import collections
import glob
import heapq
import json
import math
import os
import struct
import sys

import numpy as np
import shapely
import tifffile
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage
from scipy.interpolate import griddata

sys.path.insert(0, os.path.dirname(__file__))
import enc  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "Data", "GalvestonBay", "raw")
OUT = os.path.join(ROOT, "Content", "TerrainData")
DOCS = os.path.join(ROOT, "docs", "phase-5")
CELL = 10.0
TREE_CELL = 20.0
CURRENT_CELL = 50.0
CENTER = (29.5446, -95.0193)            # Kemah, at the Clear Lake channel
BBOX = (-95.115, 29.295, -94.665, 29.625)  # lon_min, lat_min, lon_max, lat_max
LOCAL = f"+proj=tmerc +lat_0={CENTER[0]} +lon_0={CENTER[1]} +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m +no_defs"
to_local = Transformer.from_crs("EPSG:4326", LOCAL, always_xy=True)
from_local = Transformer.from_crs(LOCAL, "EPSG:4326", always_xy=True)


def ll2xy(lat, lon):
    e, n = to_local.transform(lon, lat)
    return n, e  # game X = north, Y = east


def geom_xy(g):
    """Shapely geometry in lon/lat -> shapely geometry in game (north, east) meters, keeping Z (sounding depths)."""
    def f(c):
        e, n = to_local.transform(c[:, 0], c[:, 1])
        return np.column_stack([n, e] + ([c[:, 2]] if c.shape[1] > 2 else []))
    return shapely.transform(g, f, include_z=bool(g.has_z))


# ---------------------------------------------------------------- grid
corners = [ll2xy(BBOX[1], BBOX[0]), ll2xy(BBOX[3], BBOX[2]), ll2xy(BBOX[1], BBOX[2]), ll2xy(BBOX[3], BBOX[0])]
# corners: SW, NE, SE, NW. The projected box is slightly rotated, so take the box inside all four.
X0 = math.ceil(max(corners[0][0], corners[2][0]) / CELL) * CELL + CELL
X1 = math.floor(min(corners[1][0], corners[3][0]) / CELL) * CELL - CELL
Y0 = math.ceil(max(corners[0][1], corners[3][1]) / CELL) * CELL + CELL
Y1 = math.floor(min(corners[1][1], corners[2][1]) / CELL) * CELL - CELL
NY = int((X1 - X0) / CELL) + 1
NX = int((Y1 - Y0) / CELL) + 1
print(f"grid {NX} x {NY} cells of {CELL} m, north {X0:.0f}..{X1:.0f}, east {Y0:.0f}..{Y1:.0f}")
gx = X0 + np.arange(NY) * CELL
gy = Y0 + np.arange(NX) * CELL


def to_px(coords, ss=1):
    """(north, east) pairs -> image pixel coordinates (column = east, row = north), supersampled."""
    return [((y - Y0) / CELL * ss + (ss - 1) / 2.0, (x - X0) / CELL * ss + (ss - 1) / 2.0) for x, y in coords]


def polygons(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    if g.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for p in g.geoms if p.geom_type == "Polygon"]
    return []


def lines(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    if g.geom_type == "MultiLineString":
        return list(g.geoms)
    if g.geom_type == "Polygon":
        return [shapely.LineString(g.exterior.coords)]
    if g.geom_type == "MultiPolygon":
        return [shapely.LineString(p.exterior.coords) for p in g.geoms]
    return []


def fill_polygon(img_draw, poly, value, ss=1):
    img_draw.polygon(to_px(poly.exterior.coords, ss), fill=value)
    for hole in poly.interiors:
        img_draw.polygon(to_px(hole.coords, ss), fill=0)


# ---------------------------------------------------------------- ENC: depth areas, land, dredging, soundings
cells = enc.cells(os.path.join(RAW, "enc"))
print(f"{len(cells)} ENC cells")
depmin = np.full((NY, NX), np.nan, np.float32)
depmax = np.full((NY, NX), np.nan, np.float32)
dredged = np.full((NY, NX), np.nan, np.float32)
land = np.zeros((NY, NX), bool)
covered = np.zeros((NY, NX), bool)
samples = []  # (north, east, depth)
features = collections.defaultdict(list)  # layer -> rows (game-frame geometry), from every cell
SS_LAND = 4
land_hi = Image.new("L", (NX * SS_LAND, NY * SS_LAND), 0)
land_hi_draw = ImageDraw.Draw(land_hi)
for path in cells:  # coarse cells first, detailed ones paint over them inside their coverage
    name = os.path.basename(path)[:-4]
    cov_img = Image.new("L", (NX, NY), 0)
    cov_draw = ImageDraw.Draw(cov_img)
    cov_hi = Image.new("L", (NX * SS_LAND, NY * SS_LAND), 0)
    cov_hi_draw = ImageDraw.Draw(cov_hi)
    for row in enc.read(path, "M_COVR"):
        if row.get("CATCOV") == 1:
            for p in polygons(geom_xy(row["geom"])):
                fill_polygon(cov_draw, p, 255)
                fill_polygon(cov_hi_draw, p, 255, SS_LAND)
    cov = np.asarray(cov_img) > 0
    if not cov.any():
        continue
    layers = set(enc.layers(path))
    # Depth areas: draw ids, then map to DRVAL1/DRVAL2 inside this cell's coverage.
    ids_img = Image.new("I", (NX, NY), 0)
    ids_draw = ImageDraw.Draw(ids_img)
    ranges = [(np.nan, np.nan)]
    for row in enc.read(path, "DEPARE") if "DEPARE" in layers else []:
        for p in polygons(geom_xy(row["geom"])):
            ranges.append((row.get("DRVAL1"), row.get("DRVAL2")))
            fill_polygon(ids_draw, p, len(ranges) - 1)
    ids = np.asarray(ids_img)
    lut1 = np.array([np.nan if r[0] is None else float(r[0]) for r in ranges], np.float32)
    lut2 = np.array([np.nan if r[1] is None else float(r[1]) for r in ranges], np.float32)
    has = cov & (ids > 0)
    depmin[has] = lut1[ids[has]]
    depmax[has] = lut2[ids[has]]
    # Land areas (supersampled for a crisp shoreline) and dredged channels.
    cell_land = Image.new("L", (NX * SS_LAND, NY * SS_LAND), 0)
    cell_land_draw = ImageDraw.Draw(cell_land)
    for row in enc.read(path, "LNDARE") if "LNDARE" in layers else []:
        for p in polygons(geom_xy(row["geom"])):
            fill_polygon(cell_land_draw, p, 255, SS_LAND)
    cov_hi_arr = np.asarray(cov_hi) > 0
    land_arr = np.asarray(land_hi).copy()
    land_arr[cov_hi_arr] = np.asarray(cell_land)[cov_hi_arr]
    land_hi = Image.fromarray(land_arr)
    land_hi_draw = ImageDraw.Draw(land_hi)
    if "DRGARE" in layers:
        dr_img = Image.new("I", (NX, NY), 0)
        dr_draw = ImageDraw.Draw(dr_img)
        vals = [np.nan]
        for row in enc.read(path, "DRGARE"):
            for p in polygons(geom_xy(row["geom"])):
                vals.append(np.nan if row.get("DRVAL1") is None else float(row["DRVAL1"]))
                fill_polygon(dr_draw, p, len(vals) - 1)
        dr = np.asarray(dr_img)
        hit = cov & (dr > 0)
        dredged[hit] = np.array(vals, np.float32)[dr[hit]]
    covered |= cov
    # Soundings and contours as depth samples; everything else kept for the chart and the world.
    for layer in ("SOUNDG", "DEPCNT"):
        if layer not in layers:
            continue
        for row in enc.read(path, layer):
            g = geom_xy(row["geom"])
            if layer == "SOUNDG":
                for pt in (g.geoms if hasattr(g, "geoms") else [g]):
                    if pt.has_z:
                        samples.append((pt.x, pt.y, pt.z))
                        features["SOUNDG"].append((pt.x, pt.y, pt.z, name))
            else:
                v = row.get("VALDCO")
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                for ln in lines(g):
                    n = max(2, int(ln.length / 30.0))
                    for k in range(n + 1):
                        p = ln.interpolate(k / n, normalized=True)
                        samples.append((p.x, p.y, float(v)))
                features["DEPCNT"].append((g, float(v), name))
    for layer in ("COALNE", "SLCONS", "PONTON", "BRIDGE", "BOYLAT", "BOYSPP", "BOYCAR", "BOYSAW", "BOYISD", "BCNLAT", "BCNSPP",
                  "BCNCAR", "BCNSAW", "BCNISD", "LIGHTS", "DAYMAR", "TOPMAR", "LNDMRK", "FAIRWY", "MAGVAR", "OBSTRN", "WRECKS"):
        if layer in layers:
            for row in enc.read(path, layer):
                row["geom_xy"] = geom_xy(row["geom"]) if row["geom"] is not None else None
                features[layer].append(row)
land_frac = np.asarray(land_hi, np.float64).reshape(NY, SS_LAND, NX, SS_LAND).mean(axis=(1, 3)) / 255.0
print(f"depth samples {len(samples)}, covered {covered.mean() * 100:.0f}% of the grid, land {land_frac.mean() * 100:.0f}%")

# ---------------------------------------------------------------- depths: interpolate soundings and contours, honor the chart's ranges
water = (land_frac < 0.5) & covered
pts = np.array(samples)
GX, GY = np.meshgrid(gx, gy, indexing="ij")
# Zero-depth samples along the land edge pin the interpolation to the shore.
edge = ndimage.binary_dilation(land_frac >= 0.5, iterations=1) & water
er, ec = np.nonzero(edge[::3, ::3])
shore = np.column_stack([gx[er * 3], gy[ec * 3], np.zeros(len(er))])
pts = np.vstack([pts, shore])
depth = np.full((NY, NX), np.nan)
wr, wc = np.nonzero(water)
depth[wr, wc] = griddata(pts[:, :2], pts[:, 2], (gx[wr], gy[wc]), method="linear")
missing = np.isnan(depth) & water
if missing.any():
    idx = ndimage.distance_transform_edt(np.isnan(depth) | ~water, return_distances=False, return_indices=True)
    depth[missing] = depth[idx[0][missing], idx[1][missing]]
lo = np.where(np.isnan(depmin), -np.inf, depmin)
hi = np.where(np.isnan(depmax), np.inf, depmax)
depth = np.clip(depth, lo, np.maximum(lo, hi - 0.05))
depth = np.where(np.isnan(dredged), depth, np.maximum(depth, dredged))
water_bottom = -depth  # height above MLLW
print(f"deepest {np.nanmax(depth):.1f} m below MLLW, water cells {water.sum()}")

# ---------------------------------------------------------------- land: USGS 3DEP, NAVD88 -> MLLW
datums = {d["name"]: d["value"] for d in json.load(open(os.path.join(RAW, "tides", "datums_8771450.json")))["datums"]}
NAVD_TO_MLLW = datums["NAVD88"] - datums["MLLW"]
MHW = datums["MHW"] - datums["MLLW"]
with tifffile.TiffFile(os.path.join(RAW, "dem_3dep.tif")) as tif:
    dem = tif.pages[0].asarray().astype(np.float64)
    tie = tif.pages[0].tags["ModelTiepointTag"].value
    scale = tif.pages[0].tags["ModelPixelScaleTag"].value
lon, lat = from_local.transform(GY, GX)
fc = (lon - tie[3]) / scale[0] - 0.5
fr = (tie[4] - lat) / scale[1] - 0.5
land_z = ndimage.map_coordinates(dem, [fr, fc], order=1, mode="nearest") + NAVD_TO_MLLW
land_z = np.maximum(land_z, MHW + 0.25)
f = 1.0 - land_frac
height = (1.0 - f) * land_z + f * np.where(np.isnan(water_bottom), -0.5, np.minimum(water_bottom, MHW - 0.3))
shore_cells = (f > 0.0) & (f < 1.0)
height[shore_cells] = MHW + 0.6 - 1.2 * f[shore_cells]  # the water's edge at mean high water falls on the chart's line
# Outside the charts' coverage (inland) the land comes from the DEM; a DEM surface below high water there is a
# pond or marsh, kept shallow.
outside = ~covered
height[outside] = np.where(land_z[outside] > MHW + 0.25, land_z[outside], -0.5)
height = np.clip(height, -320.0, 320.0)

# ---------------------------------------------------------------- shoreline checkpoints (chart coastline vs the terrain's MHW contour)
CHECK = (("Kemah, Clear Lake channel", 29.5440, -95.0150), ("Texas City Dike", 29.3880, -94.8800), ("Eagle Point", 29.4810, -94.9170))
coast = [ln for row in features["COALNE"] for ln in lines(row["geom_xy"])]
checkpoints = []
for cname, la, lo_ in CHECK:
    x, y = ll2xy(la, lo_)
    best = None
    for ln in coast:
        d = ln.distance(shapely.Point(x, y))
        if best is None or d < best[0]:
            best = (d, ln.interpolate(ln.project(shapely.Point(x, y))))
    if best:
        checkpoints.append({"name": cname, "shore": [round(best[1].x, 2), round(best[1].y, 2)]})

# ---------------------------------------------------------------- navaids: buoys, beacons, their lights, dayboards and topmarks
def scalar(v):
    if v is None:
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return [str(x) for x in v]
    if isinstance(v, float) and math.isnan(v):
        return None
    return v.item() if hasattr(v, "item") else v


lights = []
for row in features["LIGHTS"]:
    g = row["geom_xy"]
    if g is None or g.geom_type != "Point":
        continue
    lights.append({"x": g.x, "y": g.y, "litchr": scalar(row.get("LITCHR")), "siggrp": scalar(row.get("SIGGRP")) or "",
                   "sigper": scalar(row.get("SIGPER")), "colour": scalar(row.get("COLOUR")) or [], "range": scalar(row.get("VALNMR")),
                   "height": scalar(row.get("HEIGHT")), "cell": row["cell"]})
navaids = {}
KINDS = {"BOYLAT": "buoy", "BOYSPP": "buoy", "BOYCAR": "buoy", "BOYSAW": "buoy", "BOYISD": "buoy",
         "BCNLAT": "beacon", "BCNSPP": "beacon", "BCNCAR": "beacon", "BCNSAW": "beacon", "BCNISD": "beacon"}
for layer, kind in KINDS.items():
    for row in features[layer]:
        g = row["geom_xy"]
        if g is None or g.geom_type != "Point":
            continue
        key = (round(g.x / 3.0), round(g.y / 3.0))  # the same aid charted in two cells
        aid = {"x": round(g.x, 2), "y": round(g.y, 2), "kind": kind, "layer": layer, "name": scalar(row.get("OBJNAM")) or "",
               "shape": scalar(row.get("BOYSHP") if kind == "buoy" else row.get("BCNSHP")), "colour": scalar(row.get("COLOUR")) or [],
               "colpat": scalar(row.get("COLPAT")), "catlam": scalar(row.get("CATLAM")), "cell": row["cell"]}
        if key not in navaids or row["cell"][2] >= navaids[key]["cell"][2]:
            navaids[key] = aid
navaids = list(navaids.values())
for aid in navaids:
    near = [lt for lt in lights if (lt["x"] - aid["x"]) ** 2 + (lt["y"] - aid["y"]) ** 2 < 9.0]
    if near:
        lt = max(near, key=lambda t: t["cell"][2])
        aid["light"] = {k: lt[k] for k in ("litchr", "siggrp", "sigper", "colour", "range", "height")}
for row in features["DAYMAR"]:
    g = row["geom_xy"]
    if g is not None and g.geom_type == "Point":
        for aid in navaids:
            if (aid["x"] - g.x) ** 2 + (aid["y"] - g.y) ** 2 < 9.0:
                aid["daymark"] = {"shape": scalar(row.get("TOPSHP")), "colour": scalar(row.get("COLOUR")) or []}
in_box = lambda x, y: X0 <= x <= X1 and Y0 <= y <= Y1
navaids = [a for a in navaids if in_box(a["x"], a["y"])]
landmarks = []
for row in features["LNDMRK"]:
    g = row["geom_xy"]
    if g is None:
        continue
    c = g.centroid
    CATLMK = {1: "Cairn", 3: "Chimney", 5: "Flagstaff", 7: "Mast", 9: "Monument", 15: "Dome", 17: "Tower", 18: "Windmill", 20: "Spire", 21: "Boulder"}
    cat = scalar(row.get("CATLMK"))
    cat = cat[0] if isinstance(cat, list) and cat else cat
    if in_box(c.x, c.y):
        landmarks.append({"x": round(c.x, 1), "y": round(c.y, 1), "name": scalar(row.get("OBJNAM")) or CATLMK.get(int(cat) if cat else 0, "Landmark"), "category": cat,
                          "conspicuous": scalar(row.get("CONVIS")) == 1, "height": scalar(row.get("HEIGHT"))})
# Major lights not on a buoy or beacon (jetty lights, range lights) are aids too.
for lt in lights:
    if in_box(lt["x"], lt["y"]) and not any((a["x"] - lt["x"]) ** 2 + (a["y"] - lt["y"]) ** 2 < 9.0 for a in navaids):
        navaids.append({"x": round(lt["x"], 2), "y": round(lt["y"], 2), "kind": "light", "layer": "LIGHTS", "name": "", "shape": None,
                        "colour": [], "colpat": None, "catlam": None, "cell": lt["cell"],
                        "light": {k: lt[k] for k in ("litchr", "siggrp", "sigper", "colour", "range", "height")}})
print(f"navaids {len(navaids)} ({sum(1 for a in navaids if 'light' in a)} lit), landmarks {len(landmarks)}")

# ---------------------------------------------------------------- docks, jetties, bridges
SLCONS_KIND = {1: "breakwater", 2: "breakwater", 3: "breakwater", 4: "pier", 5: "pier", 6: "pier", 7: "breakwater", 8: "breakwater",
               15: "pier", 16: "pier"}
docks = []
seen = set()
for layer in ("SLCONS", "PONTON"):
    for row in features[layer]:
        kind = "pier" if layer == "PONTON" else SLCONS_KIND.get(scalar(row.get("CATSLC")))
        g = row["geom_xy"]
        if kind is None or g is None:
            continue
        key = (round(g.centroid.x), round(g.centroid.y), kind)
        if key in seen:
            continue
        seen.add(key)
        for p in polygons(g):
            pts_ = [[round(x, 2), round(y, 2)] for x, y in p.exterior.coords]
            if all(in_box(x, y) for x, y in pts_):
                docks.append({"kind": kind, "closed": True, "points": pts_})
        for ln in ([g] if g.geom_type == "LineString" else (list(g.geoms) if g.geom_type == "MultiLineString" else [])):
            pts_ = [[round(x, 2), round(y, 2)] for x, y in ln.coords]
            if all(in_box(x, y) for x, y in pts_):
                docks.append({"kind": kind, "closed": False, "points": pts_})
bridges = []
for row in features["BRIDGE"]:
    g = row["geom_xy"]
    if g is None:
        continue
    clearance = scalar(row.get("VERCLR")) or scalar(row.get("VERCCL"))
    deck = (MHW + float(clearance)) if clearance else MHW + 3.0
    for ln in lines(g):
        pts_ = [[round(x, 2), round(y, 2)] for x, y in ln.coords]
        if all(in_box(x, y) for x, y in pts_) and len(pts_) >= 2:
            bridges.append({"name": scalar(row.get("OBJNAM")) or "bridge", "deck": round(deck, 2), "points": pts_})
print(f"docks and jetties {len(docks)}, bridges {len(bridges)}")


# ---------------------------------------------------------------- trees and buildings (OpenStreetMap)
def load_osm(pattern):
    els = []
    for p in glob.glob(os.path.join(RAW, pattern)):
        try:
            els += json.load(open(p)).get("elements", [])
        except Exception:
            pass
    return els


TNY, TNX = int(math.ceil(NY * CELL / TREE_CELL)), int(math.ceil(NX * CELL / TREE_CELL))
tree_img = Image.new("L", (TNX, TNY), 25)  # the coast is mostly grass, marsh and town: few trees by default
tdraw = ImageDraw.Draw(tree_img)
density = {("landuse", "forest"): 200, ("natural", "wood"): 200, ("natural", "scrub"): 90, ("natural", "wetland"): 5,
           ("leisure", "park"): 80, ("landuse", "residential"): 45, ("landuse", "commercial"): 5, ("landuse", "industrial"): 0,
           ("landuse", "grass"): 10, ("landuse", "meadow"): 10, ("landuse", "farmland"): 5}
for el in load_osm("landuse_osm*.json"):
    t = el.get("tags", {})
    val = next((v for (k, kv), v in density.items() if t.get(k) == kv), None)
    if val is None or "geometry" not in el:
        continue
    xy = [ll2xy(p["lat"], p["lon"]) for p in el["geometry"]]
    if len(xy) >= 3:
        tdraw.polygon([((y - Y0) / TREE_CELL, (x - X0) / TREE_CELL) for x, y in xy], fill=val)
trees = np.asarray(tree_img, np.uint8).copy()
land_t = ndimage.zoom((land_frac > 0.5).astype(np.float32), (TNY / NY, TNX / NX), order=0)[:TNY, :TNX] > 0.5
trees[:land_t.shape[0], :land_t.shape[1]][~land_t] = 0
buildings = []
for el in load_osm("buildings_osm*.json"):
    g = el.get("geometry")
    if not g or len(g) < 4:
        continue
    xy = np.array([ll2xy(p["lat"], p["lon"]) for p in g])
    c = xy.mean(axis=0)
    if not in_box(c[0], c[1]):
        continue
    r, k = int((c[0] - X0) / CELL), int((c[1] - Y0) / CELL)
    near = water[max(0, r - 40):r + 40, max(0, k - 40):k + 40]
    if not near.any():
        continue
    rect = shapely.minimum_rotated_rectangle(shapely.MultiPoint(xy))
    if rect.geom_type != "Polygon":
        continue
    rc = np.array(rect.exterior.coords)[:4]
    e1, e2 = rc[1] - rc[0], rc[2] - rc[1]
    length, width = np.linalg.norm(e1), np.linalg.norm(e2)
    if length < 3 or width < 3:
        continue
    yaw = math.degrees(math.atan2(e1[1], e1[0]))
    ground = float(height[min(max(r, 0), NY - 1), min(max(k, 0), NX - 1)])
    # Same layout as the lake: x, y, ground, length, width, height, yaw.
    buildings.append([round(float(c[0]), 1), round(float(c[1]), 1), round(max(ground, MHW), 2), round(float(length), 1), round(float(width), 1),
                      4.0 if length * width < 400 else 8.0, round(yaw, 1)])
print(f"buildings near the water {len(buildings)}")

# ---------------------------------------------------------------- tides and currents
TIDES = os.path.join(RAW, "tides")


def station(st):
    meta = json.load(open(os.path.join(TIDES, f"station_{st}.json")))["stations"][0]
    d = {x["name"]: x["value"] for x in json.load(open(os.path.join(TIDES, f"datums_{st}.json")))["datums"]}
    hc = json.load(open(os.path.join(TIDES, f"harcon_{st}.json")))["HarmonicConstituents"]
    x, y = ll2xy(meta["lat"], meta["lng"])
    return {"id": st, "name": meta["name"], "x": round(x, 1), "y": round(y, 1), "z0": round(d["MSL"] - d["MLLW"], 4),
            "constituents": [[c["name"].upper(), c["amplitude"], c["phase_GMT"]] for c in hc if c["amplitude"] > 0.0]}


height_stations = [station(s) for s in ("8771450", "8771341", "8771013", "8770613", "8771486")]
cur = json.load(open(os.path.join(TIDES, "curharcon_ACT8856.json")))["HarmonicConstituents"]
cur_const = [[c["constituentName"].upper(), c["majorAmplitude"] / 100.0, c["majorPhaseGMT"]] for c in cur if c["majorAmplitude"] > 0.0]
sys.path.insert(0, os.path.dirname(__file__))
import datetime as dtm  # noqa: E402
import tides as tidepy  # noqa: E402
month = json.load(open(os.path.join(TIDES, "curpred6_ACT8856_month.json")))["current_predictions"]["cp"]
residual = np.mean([float(p["Velocity_Major"]) / 100.0 - tidepy.predict(cur_const, 0.0, dtm.datetime.strptime(p["Time"], "%Y-%m-%d %H:%M").replace(
    tzinfo=dtm.timezone.utc)) for p in month[::3]])
flood_dir = float(month[0]["meanFloodDir"])
cx, cy = ll2xy(29.343299865722656, -94.78130340576172)
current_station = {"id": "ACT8856", "name": "Bolivar Roads", "x": round(cx, 1), "y": round(cy, 1), "z0": round(float(residual), 4),
                   "flood_deg": flood_dir, "constituents": cur_const}
print(f"current: Bolivar Roads mean (non-tidal) {residual * 100:.1f} cm/s, flood toward {flood_dir:.0f} deg")
reference = {"hilo": {}, "current_max_slack": []}
for st in ("8771450", "8771013"):
    reference["hilo"][st] = [[p["t"], float(p["v"]), p["type"]] for p in json.load(open(os.path.join(TIDES, f"pred_hilo_{st}.json")))["predictions"]]
reference["current_max_slack"] = [[p["Time"], p["Type"], float(p["Velocity_Major"]) * 0.514444] for p in json.load(
    open(os.path.join(TIDES, "curpred_ACT8856.json")))["current_predictions"]["cp"]]

# Current field: geodesic distance from the entrance through the water (channels are cheaper to travel), flood
# along increasing distance, strength falling with distance and in shallow water, arrival delayed by distance.
step = int(CURRENT_CELL / CELL)
cdepth = depth[::step, ::step]
cwater = water[::step, ::step] & (np.nan_to_num(cdepth) > 0.3)
cny, cnx = cdepth.shape
dist = np.full((cny, cnx), np.inf)
sr, sc = int(round((cx - X0) / CURRENT_CELL)), int(round((cy - Y0) / CURRENT_CELL))
heap = [(0.0, sr, sc)]
dist[sr, sc] = 0.0
while heap:
    d0, r, c = heapq.heappop(heap)
    if d0 > dist[r, c]:
        continue
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < cny and 0 <= cc < cnx and cwater[rr, cc]:
                w = CURRENT_CELL * math.hypot(dr, dc) * math.sqrt(12.0 / max(min(cdepth[rr, cc], 12.0), 0.5))
                if d0 + w < dist[rr, cc]:
                    dist[rr, cc] = d0 + w
                    heapq.heappush(heap, (d0 + w, rr, cc))
reach = np.isfinite(dist)
dfill = np.where(reach, dist, np.nanmax(np.where(reach, dist, np.nan)) * 1.5)
gr, gc = np.gradient(ndimage.gaussian_filter(dfill, 2.0))
norm = np.hypot(gr, gc) + 1e-9
dir_x, dir_y = gr / norm, gc / norm
# At the station the field points along NOAA's mean flood direction.
geo_km = np.where(reach, dist, 0.0) / 1000.0
gain = np.clip(np.sqrt(np.nan_to_num(cdepth) / 12.0), 0.15, 1.2) * np.exp(-geo_km / 12.0)
gain = np.where(reach, gain / max(gain[sr, sc], 1e-6), 0.0)
delay = np.where(reach, np.minimum(dist / 5.0, 65000.0), 0.0)
fd = math.radians(flood_dir)
blend = np.clip(1.0 - geo_km / 3.0, 0.0, 1.0)  # near the station, use NOAA's measured axis
dir_x = (1 - blend) * dir_x + blend * math.cos(fd)
dir_y = (1 - blend) * dir_y + blend * math.sin(fd)
norm = np.hypot(dir_x, dir_y) + 1e-9
dir_x, dir_y = dir_x / norm, dir_y / norm

# ---------------------------------------------------------------- launch spots
LAUNCH = (("Clear Lake, off the yacht clubs", 29.5560, -95.0560, 90.0), ("Kemah channel, outbound", 29.5418, -95.0080, 110.0),
          ("Galveston Bay, off Clear Lake", 29.5250, -94.9700, 130.0), ("Red Fish Bar", 29.4950, -94.8750, 180.0),
          ("Texas City Dike", 29.4000, -94.8600, 140.0), ("Bolivar Roads", 29.3550, -94.7700, 120.0))
launch = []
for nm, la, lo_, hd in LAUNCH:
    x, y = ll2xy(la, lo_)
    r, k = int(round((x - X0) / CELL)), int(round((y - Y0) / CELL))
    best = None
    for rad in range(0, 120):
        rr0, rr1, cc0, cc1 = max(0, r - rad), min(NY, r + rad + 1), max(0, k - rad), min(NX, k + rad + 1)
        win = height[rr0:rr1, cc0:cc1]
        ok = np.argwhere(win < -2.0)
        if len(ok):
            d = (ok[:, 0] + rr0 - r) ** 2 + (ok[:, 1] + cc0 - k) ** 2
            j = int(np.argmin(d))
            best = (ok[j, 0] + rr0, ok[j, 1] + cc0)
            break
    if best:
        x, y = X0 + best[0] * CELL, Y0 + best[1] * CELL
    launch.append({"name": nm, "xy": [round(x, 1), round(y, 1)], "heading": hd, "depth_m": round(float(-height[best] if best else 0.0), 1)})

# ---------------------------------------------------------------- magnetic variation (ENC, updated to the bake year)
mv = features["MAGVAR"][0] if features["MAGVAR"] else None
variation = None
if mv is not None:
    base_year = int(scalar(mv.get("RYRMGV")) or 2021)
    variation = {"deg_east": round(float(mv["VALMAG"]) + (2026 - base_year) * float(mv.get("VALACM") or 0.0) / 60.0, 2),
                 "base": float(mv["VALMAG"]), "base_year": base_year, "annual_change_min": float(mv.get("VALACM") or 0.0), "year": 2026}

# ---------------------------------------------------------------- vector chart for the chart view
def tri(poly, tol=4.0):
    poly = poly.simplify(tol, preserve_topology=True)
    if poly.is_empty or poly.area < 200.0:
        return []
    out = []
    for t in shapely.constrained_delaunay_triangles(poly).geoms:
        c = np.array(t.exterior.coords)[:3]
        out.append([round(v, 1) for v in c.flatten().tolist()])
    return out


def depth_class(d1):
    if d1 is None or (isinstance(d1, float) and math.isnan(d1)):
        return 3
    if d1 < 0.0:
        return 0      # drying
    if d1 < 1.8:
        return 1      # shoal (under 6 ft)
    if d1 < 3.6:
        return 2      # under 12 ft
    return 3          # deep


box = shapely.box(X0, Y0, X1, Y1)
chart = {"areas": [], "contours": [], "coast": [], "soundings": [], "channels": [], "bridges": [], "docks": []}
by_detail = sorted(cells, key=lambda p: os.path.basename(p)[2])
seen_area = shapely.Polygon()
for path in reversed(by_detail):  # most detailed first: coarser cells only fill what is left
    layers = set(enc.layers(path))
    cov = shapely.unary_union([geom_xy(r["geom"]) for r in enc.read(path, "M_COVR") if r.get("CATCOV") == 1]) if "M_COVR" in layers else None
    if cov is None or cov.is_empty:
        continue
    new = cov.intersection(box).difference(seen_area)
    if new.is_empty:
        continue
    for layer in ("DEPARE", "LNDARE"):
        if layer not in layers:
            continue
        for row in enc.read(path, layer):
            g = geom_xy(row["geom"]).intersection(new)
            for p in polygons(g):
                cls = 4 if layer == "LNDARE" else depth_class(scalar(row.get("DRVAL1")))
                for t in tri(p):
                    chart["areas"].append([cls] + t)
    seen_area = seen_area.union(new)
for g, v, _ in features["DEPCNT"]:
    for ln in lines(g.intersection(box)):
        chart["contours"].append([round(v, 1)] + [round(c, 1) for xy in ln.simplify(5.0).coords for c in xy])
for row in features["COALNE"]:
    for ln in lines(row["geom_xy"].intersection(box)):
        chart["coast"].append([round(c, 1) for xy in ln.simplify(3.0).coords for c in xy])
grid_seen = set()
for x, y, z, _ in sorted(features["SOUNDG"], key=lambda s: -ord(s[3][2])):
    key = (int(x // 350), int(y // 350))  # thin to about one per 350 m, preferring detailed cells
    if in_box(x, y) and key not in grid_seen:
        grid_seen.add(key)
        chart["soundings"].append([round(x, 1), round(y, 1), round(z, 1)])
for row in features["FAIRWY"]:
    for ln in lines(row["geom_xy"].intersection(box)):
        chart["channels"].append([round(c, 1) for xy in ln.simplify(5.0).coords for c in xy])
chart["bridges"] = [[b["name"]] + [c for p in b["points"] for c in p] for b in bridges]
chart["docks"] = [[d["kind"]] + [c for p in d["points"] for c in p] for d in docks]
print(f"chart: {len(chart['areas'])} triangles, {len(chart['contours'])} contours, {len(chart['soundings'])} soundings")

# ---------------------------------------------------------------- write
os.makedirs(OUT, exist_ok=True)
os.makedirs(DOCS, exist_ok=True)
with open(os.path.join(OUT, "GalvestonBay.height"), "wb") as fh:
    fh.write(b"SSHT" + struct.pack("<III", 1, NX, NY) + struct.pack("<ffff", CELL, X0, Y0, 0.01))
    fh.write(np.round(height * 100.0).astype("<i2").tobytes())
with open(os.path.join(OUT, "GalvestonBay.trees"), "wb") as fh:
    fh.write(b"SSTR" + struct.pack("<III", 1, TNX, TNY) + struct.pack("<fff", TREE_CELL, X0, Y0))
    fh.write(trees.astype(np.uint8).tobytes())
with open(os.path.join(OUT, "GalvestonBay.current"), "wb") as fh:
    fh.write(b"SSCF" + struct.pack("<III", 1, cnx, cny) + struct.pack("<fff", CURRENT_CELL, X0, Y0))
    fh.write(np.round(dir_x * 10000).astype("<i2").tobytes())
    fh.write(np.round(dir_y * 10000).astype("<i2").tobytes())
    fh.write(np.clip(np.round(gain * 1000), 0, 65535).astype("<u2").tobytes())
    fh.write(np.clip(np.round(delay), 0, 65535).astype("<u2").tobytes())
meta = {
    "name": "Galveston Bay",
    "grid": {"rows_north": NY, "cols_east": NX, "cell_m": CELL, "origin_north_m": X0, "origin_east_m": Y0, "height_unit_m": 0.01},
    "trees": {"rows_north": TNY, "cols_east": TNX, "cell_m": TREE_CELL},
    "projection": LOCAL,
    "datum": "MLLW (chart datum); heights in meters above it",
    "mhw_m": round(MHW, 3), "navd88_to_mllw_m": round(NAVD_TO_MLLW, 3),
    "latitude": CENTER[0], "longitude": CENTER[1],
    "sources": {
        "chart": "NOAA ENC cells " + ", ".join(sorted(os.path.basename(c)[:-4] for c in cells)) + " (public domain)",
        "elevation": "USGS 3D Elevation Program, 1/3 arc-second, NAVD88 converted to MLLW with the Galveston Pier 21 datums (public domain)",
        "tides": "NOAA CO-OPS harmonic constituents and datums: Galveston Pier 21, North Jetty, Eagle Point, Morgans Point, Railroad Bridge; currents: Bolivar Roads ACT8856 bin 2",
        "buildings_landuse": "OpenStreetMap contributors, ODbL 1.0",
    },
    "variation": variation,
    "launch_spots": launch,
    "checkpoints": checkpoints,
    "docks": docks,
    "bridges": bridges,
    "buildings": buildings,
    "navaids": navaids,
    "landmarks": landmarks,
    "tide_stations": height_stations,
    "current_station": current_station,
    "reference_predictions": reference,
}
with open(os.path.join(OUT, "GalvestonBay.json"), "w") as fh:
    json.dump(meta, fh, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o))
with open(os.path.join(OUT, "GalvestonBay.chart.json"), "w") as fh:
    json.dump(chart, fh, separators=(",", ":"))

# Preview: depth shading, land, navaids.
rgb = np.zeros((NY, NX, 3), np.uint8)
dshade = np.clip(-height / 6.0, 0, 1)
rgb[..., 0] = np.where(height < 0, 40 + 60 * (1 - dshade), 170)
rgb[..., 1] = np.where(height < 0, 110 + 90 * (1 - dshade), 160)
rgb[..., 2] = np.where(height < 0, 170 + 70 * (1 - dshade), 120)
img = Image.fromarray(rgb[::-1])
dr = ImageDraw.Draw(img)
for a in navaids:
    px, py = (a["y"] - Y0) / CELL, NY - 1 - (a["x"] - X0) / CELL
    col = (220, 40, 40) if a.get("catlam") == 2 else ((40, 170, 40) if a.get("catlam") == 1 else (240, 220, 40))
    dr.ellipse([px - 4, py - 4, px + 4, py + 4], fill=col)
img.thumbnail((1600, 1600))
img.save(os.path.join(DOCS, "terrain-preview.png"))
print("wrote", OUT, "and", DOCS)
