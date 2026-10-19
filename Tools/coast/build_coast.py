"""Bakes a coast world into game data, chart first: a box and a name (Tools/coast/worlds/<World>.json).

Two chart sources, picked by the world's "chart":
  - "enc": NOAA ENC cells (S-57, Data/<World>/raw/enc/ENC_ROOT; Tools/coast/fetch_galveston.sh, fetch_gulf.sh): depth
    areas, soundings, contours, dredged channels, land, coastline, shoreline constructions, pontoons, bridges, buoys,
    beacons, lights, landmarks, magnetic variation (public domain); NOAA CO-OPS tides and currents; USGS 3DEP land.
  - "osm": no official chart (Tools/coast/fetch_world.py): the OpenStreetMap coastline, harbours and seamarks, EMODnet
    depths, NGA Pub 113 lights and Copernicus or IGN land (osm_chart.py turns them into the same S-57-shaped rows).
Outputs (Content/TerrainData):
  - <World>.height : int16 cm above the world's datum, CELL grid ("SSHT", same format as the lake)
  - <World>.trees  : tree density, 20 m grid
  - <World>.current: tidal current field, 50 m grid ("SSCF"), when the world has a current station
  - <World>.json   : grid, sources, docks, bridges, buildings, launch spots, checkpoints, navaids, landmarks,
                     tide and current stations, magnetic variation, and NOAA reference predictions for the tests
  - <World>.chart.json : the vector chart for the in-game chart view
  - docs/<docs>/terrain-preview.png (Galveston) or <World>-preview.png

Heights are in meters above the world's datum: MLLW on the Texas coast (depths on the chart are positive below it; in
game the water surface stands at the predicted tide, so the terrain is shifted by the tide each frame), NGF-IGN69 (mean
sea level) at Marseille, where there is no tide model.

Run: Tools/venv/bin/python Tools/coast/build_coast.py [galveston|gulf|<World>]

The Gulf passage (Galveston to Freeport, `gulf`) bakes 50 m cells from the offshore and approach charts, flat barrier
islands (no DEM), Gulf tide stations, no tidal-current field, written as GulfPassage.* with its passage plan.
"""
import collections
import glob
import heapq
import json
import math
import os
import struct
import sys
import types

import numpy as np
import shapely
import tifffile
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage
from scipy.interpolate import griddata

sys.path.insert(0, os.path.dirname(__file__))
import enc  # noqa: E402
import geotiff  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REGION = sys.argv[1] if len(sys.argv) > 1 else "galveston"
WORLDS = {}
for _p in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "worlds", "*.json"))):
    _w = json.load(open(_p))
    WORLDS[_w["name"]] = _w
    if "alias" in _w:
        WORLDS[_w["alias"]] = _w
CFG = WORLDS[REGION]
NAME = CFG["name"]
CHART = CFG.get("chart", "enc")
TIDES_CFG = CFG.get("tides", {"source": "none"})
RAW = os.path.join(ROOT, "Data", NAME, "raw")
OUT = os.path.join(ROOT, "Content", "TerrainData")
DOCS = os.path.join(ROOT, "docs", CFG["docs"])
CELL = CFG["cell"]
TREE_CELL = 20.0 if CELL <= 10.0 else 100.0
CURRENT_CELL = 50.0
CENTER = tuple(CFG["center"])
BBOX = tuple(CFG["bbox"])
# NAD83 on the Texas coast; GRS80 with no shift (ETRS89 / RGF93, which WGS84 positions match to centimetres) in Europe.
# FGeoAnchor::ParseProj4 reads either.
DATUM = "+datum=NAD83" if CFG.get("ellipsoid", "NAD83") == "NAD83" else "+ellps=GRS80 +towgs84=0,0,0,0,0,0,0"
LOCAL = f"+proj=tmerc +lat_0={CENTER[0]} +lon_0={CENTER[1]} +k=1 +x_0=0 +y_0=0 {DATUM} +units=m +no_defs"
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
SS_LAND = 4
ctx = types.SimpleNamespace(raw=RAW, world=CFG, NY=NY, NX=NX, CELL=CELL, X0=X0, Y0=Y0, SS_LAND=SS_LAND, ll2xy=ll2xy,
                            geom_xy=lambda g: geom_xy(g), polygons=lambda g: polygons(g), fill_polygon=lambda d, p, v, ss=1: fill_polygon(d, p, v, ss),
                            new_image=lambda ss: (lambda im: (im, ImageDraw.Draw(im)))(Image.new("L", (NX * ss, NY * ss), 0)))
CHART_INFO = None
if CHART == "enc":
    cells = enc.cells(os.path.join(RAW, "enc"))
    print(f"{len(cells)} ENC cells")
    depmin = np.full((NY, NX), np.nan, np.float32)
    depmax = np.full((NY, NX), np.nan, np.float32)
    dredged = np.full((NY, NX), np.nan, np.float32)
    land = np.zeros((NY, NX), bool)
    covered = np.zeros((NY, NX), bool)
    samples = []  # (north, east, depth)
    features = collections.defaultdict(list)  # layer -> rows (game-frame geometry), from every cell
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
            # Overlapping cells: keep the deepest charted dredged depth (a cell whose polygon gives no depth must not
            # erase another's 45 ft for the Houston Ship Channel).
            dredged[hit] = np.fmax(dredged[hit], np.array(vals, np.float32)[dr[hit]])
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
                      "BCNCAR", "BCNSAW", "BCNISD", "LIGHTS", "DAYMAR", "TOPMAR", "LNDMRK", "FAIRWY", "MAGVAR", "OBSTRN", "WRECKS", "OFSPLF"):
            if layer in layers:
                for row in enc.read(path, layer):
                    row["geom_xy"] = geom_xy(row["geom"]) if row["geom"] is not None else None
                    features[layer].append(row)

    land_frac = np.asarray(land_hi, np.float64).reshape(NY, SS_LAND, NX, SS_LAND).mean(axis=(1, 3)) / 255.0
    print(f"depth samples {len(samples)}, covered {covered.mean() * 100:.0f}% of the grid, land {land_frac.mean() * 100:.0f}%")
else:
    import osm_chart  # noqa: E402
    depmin, depmax, dredged, land_frac, covered, samples, osm_features, CHART_INFO = osm_chart.load(ctx)
    features = collections.defaultdict(list, osm_features)
    cells = []
    print(f"depth samples {len(samples)}, covered {covered.mean() * 100:.0f}% of the grid, land {land_frac.mean() * 100:.0f}%")

# ---------------------------------------------------------------- depths: interpolate soundings and contours, honor the chart's ranges
water = (land_frac < 0.5) & covered
pts = np.array(samples)
GX, GY = np.meshgrid(gx, gy, indexing="ij")
# Zero-depth samples along the land edge pin the interpolation to the shore.
edge = ndimage.binary_dilation(land_frac >= 0.5, iterations=1) & water
er, ec = np.nonzero(edge[::3, ::3])
# Without a chart's depth areas (an osm world) the pin is the water's depth at the coast: a quay or a rocky shore drops
# straight to a few metres, a beach shelves from zero.
shore_z = CHART_INFO["shore_depth"](gx[er * 3], gy[ec * 3]) if CHART_INFO else np.zeros(len(er))
shore = np.column_stack([gx[er * 3], gy[ec * 3], shore_z])
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
water_bottom = -depth  # height above the datum
print(f"deepest {np.nanmax(depth):.1f} m below the datum, water cells {water.sum()}")

# ---------------------------------------------------------------- land: USGS 3DEP (NAVD88 -> MLLW), IGN RGE ALTI or Copernicus
def read_ascii_grid(path):
    """An ESRI ASCII grid (IGN's downloadable RGE ALTI tiles, Lambert-93): array and the georef of its cell centres."""
    head = {}
    with open(path) as fh:
        for _ in range(6):
            k, v = fh.readline().split()
            head[k.lower()] = float(v)
        a = np.loadtxt(fh, dtype=np.float64)
    x0 = head.get("xllcenter", head.get("xllcorner", 0.0) + head["cellsize"] / 2)
    y0 = head.get("yllcenter", head.get("yllcorner", 0.0) + head["cellsize"] / 2) + (a.shape[0] - 1) * head["cellsize"]
    a[a == head.get("nodata_value", -99999.0)] = np.nan
    return a, geotiff.Georef(x0, y0, head["cellsize"], -head["cellsize"])


def read_bil(path):
    """An ESRI BIL tile with its .hdr (fetch_world.py's RGE ALTI tiles, Lambert-93): array and the georef of its cell
    centres. The no-data value (-99999 out at sea) and anything far below the sea become NaN."""
    head = {}
    for line in open(path[:-4] + ".hdr"):
        if line.strip():
            k, v = line.split()[:2]
            head[k.upper()] = v
    a = np.fromfile(path, "<f4" if head.get("BYTEORDER", "I") == "I" else ">f4").reshape(int(head["NROWS"]), int(head["NCOLS"])).astype(np.float64)
    a[a < -50.0] = np.nan
    return a, geotiff.Georef(float(head["ULXMAP"]), float(head["ULYMAP"]), float(head["XDIM"]), -float(head["YDIM"]))


def land_from_sources():
    """The world's elevation sources in order; the first with a value wins at each node. NaN where none covers."""
    z = np.full((NY, NX), np.nan)
    lon, lat = from_local.transform(GY, GX)
    used = []
    for src in CFG.get("elevation", []):
        if src["kind"] == "geotiff" and os.path.exists(os.path.join(RAW, src["path"])):
            d, ref = geotiff.read(os.path.join(RAW, src["path"]))
            v = geotiff.sample(d, ref, lon, lat)
        elif src["kind"] == "rgealti" and glob.glob(os.path.join(RAW, src["glob"])):
            l93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
            ex, ny_ = l93.transform(lon, lat)
            v = np.full((NY, NX), np.nan)
            for tile in sorted(glob.glob(os.path.join(RAW, src["glob"]))):
                d, ref = read_bil(tile) if tile.endswith(".bil") else read_ascii_grid(tile)
                t = geotiff.sample(d, ref, ex, ny_)
                v = np.where(np.isnan(v), t, v)
        else:
            continue
        hit = np.isnan(z) & np.isfinite(v)
        z[hit] = v[hit]
        used.append(src["note"])
        print(f"land: {src['note']}: {hit.mean() * 100:.0f}% of the grid")
    return z, used


ELEVATION_USED = []
if TIDES_CFG["source"] == "noaa":
    datums = {d["name"]: d["value"] for d in json.load(open(os.path.join(RAW, "tides", f"datums_{TIDES_CFG['datum_station']}.json")))["datums"]}
    NAVD_TO_MLLW = datums["NAVD88"] - datums["MLLW"]
    MHW = datums["MHW"] - datums["MLLW"]
else:
    NAVD_TO_MLLW = None
    MHW = float(CFG["datum"]["mhw_m"])
if CHART == "enc" and os.path.exists(os.path.join(RAW, "dem_3dep.tif")):
    with tifffile.TiffFile(os.path.join(RAW, "dem_3dep.tif")) as tif:
        dem = tif.pages[0].asarray().astype(np.float64)
        tie = tif.pages[0].tags["ModelTiepointTag"].value
        scale = tif.pages[0].tags["ModelPixelScaleTag"].value
    lon, lat = from_local.transform(GY, GX)
    fc = (lon - tie[3]) / scale[0] - 0.5
    fr = (tie[4] - lat) / scale[1] - 0.5
    land_z = ndimage.map_coordinates(dem, [fr, fc], order=1, mode="nearest") + NAVD_TO_MLLW
elif CHART == "enc":
    # No DEM (the Gulf passage): the barrier islands and the beach as low, flat land a couple of meters up.
    land_z = np.full((NY, NX), MHW + 1.8)
else:
    land_z, ELEVATION_USED = land_from_sources()
    land_z = np.where(np.isnan(land_z), MHW + 1.8, land_z) + float(CFG["datum"].get("elevation_offset_m", 0.0))
land_z = np.maximum(land_z, MHW + 0.25)
f = 1.0 - land_frac
height = (1.0 - f) * land_z + f * np.where(np.isnan(water_bottom), -0.5, np.minimum(water_bottom, MHW - 0.3))
shore_cells = (f > 0.0) & (f < 1.0)
height[shore_cells] = MHW + 0.6 - 1.2 * f[shore_cells]  # the water's edge at mean high water falls on the chart's line
# Outside the charts' coverage (inland) the land comes from the DEM; a DEM surface below high water there is a
# pond or marsh, kept shallow.
outside = ~covered
if os.path.exists(os.path.join(RAW, "dem_3dep.tif")) or ELEVATION_USED:
    height[outside] = np.where(land_z[outside] > MHW + 0.25, land_z[outside], -0.5)
else:
    # Offshore past the charts' coverage (the Gulf passage's far corners): open water, as deep as the nearest charted water.
    idx = ndimage.distance_transform_edt(outside, return_distances=False, return_indices=True)
    height[outside] = np.minimum(height[idx[0][outside], idx[1][outside]], -5.0)
# int16 heights: centimetres reach 327 m; a world with higher land (Marseille's Garlaban, 714 m) takes a coarser unit.
UNIT = float(CFG.get("height_unit_m", 0.01))
height = np.clip(height, -320.0, 320.0) if UNIT == 0.01 else np.clip(height, -32000.0 * UNIT, 32000.0 * UNIT)

# ---------------------------------------------------------------- shoreline checkpoints (chart coastline vs the terrain's MHW contour)
CHECK = CFG["check"]
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
                   "height": scalar(row.get("HEIGHT")), "cell": row["cell"], "name": scalar(row.get("OBJNAM")) or ""})
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
# Round 12: Kemah's water tower (OpenStreetMap man_made=water_tower, 29.5386 N, 95.0280 W) is a landmark from the bay but
# is not charted; the chart's towers near Kemah are generic towers (CATLMK 17), drawn slim.
kx, ky = ll2xy(29.5386, -95.0280)
if in_box(kx, ky):
    landmarks.append({"x": round(kx, 1), "y": round(ky, 1), "name": "Water tower", "category": "osm", "conspicuous": True, "height": None})
# A world's own landmarks (the ones a sailor takes bearings on, whatever OSM tags them as): name, lat, lon, height, note.
for nm, la, lo_, hgt, _ in CFG.get("landmarks", []):
    lx, ly = ll2xy(la, lo_)
    landmarks.append({"x": round(lx, 1), "y": round(ly, 1), "name": nm, "category": "world", "conspicuous": True, "height": hgt})
# Offshore oil and gas platforms: landmarks to take a bearing on (their lights come in with the lights below).
for row in features["OFSPLF"]:
    g = row["geom_xy"]
    if g is None:
        continue
    c = g.centroid
    if in_box(c.x, c.y):
        landmarks.append({"x": round(c.x, 1), "y": round(c.y, 1), "name": scalar(row.get("OBJNAM")) or "Platform", "category": "platform",
                          "conspicuous": True, "height": scalar(row.get("HEIGHT"))})
# Major lights not on a buoy or beacon (jetty lights, range lights) are aids too.
for lt in lights:
    if in_box(lt["x"], lt["y"]) and not any((a["x"] - lt["x"]) ** 2 + (a["y"] - lt["y"]) ** 2 < 9.0 for a in navaids):
        navaids.append({"x": round(lt["x"], 2), "y": round(lt["y"], 2), "kind": "light", "layer": "LIGHTS", "name": lt["name"] if CHART != "enc" else "", "shape": None,
                        "colour": [], "colpat": None, "catlam": None, "cell": lt["cell"],
                        "light": {k: lt[k] for k in ("litchr", "siggrp", "sigper", "colour", "range", "height")}})
print(f"navaids {len(navaids)} ({sum(1 for a in navaids if 'light' in a)} lit), landmarks {len(landmarks)}")

# ---------------------------------------------------------------- docks, jetties, bridges
SLCONS_KIND = {1: "breakwater", 2: "breakwater", 3: "breakwater", 4: "pier", 5: "pier", 6: "pier", 7: "breakwater", 8: "breakwater",
               15: "pier", 16: "pier"}
docks = []
dock_fixed = []   # per dock: a fixed pier (not a breakwater or a pontoon)
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
                dock_fixed.append(layer == "SLCONS" and kind == "pier")
        for ln in ([g] if g.geom_type == "LineString" else (list(g.geoms) if g.geom_type == "MultiLineString" else [])):
            pts_ = [[round(x, 2), round(y, 2)] for x, y in ln.coords]
            if all(in_box(x, y) for x, y in pts_):
                docks.append({"kind": kind, "closed": False, "points": pts_})
                dock_fixed.append(layer == "SLCONS" and kind == "pier")
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
# An osm world's breakwaters and pontoons go to <World>.piers with their widths and crests (osm_harbour.py): the chart
# draws them, the world json keeps only the fixed piers.
chart_docks = docks
if CHART != "enc":
    docks = [d for d, fixed in zip(docks, dock_fixed) if fixed]
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


def osm_height(tags):
    """A building's height from OSM: height, else storeys at 3 m plus a 1 m roof."""
    for k in ("height", "building:height"):
        try:
            return float(str(tags[k]).replace("m", "").strip())
        except (KeyError, ValueError):
            pass
    try:
        return 3.0 * float(tags["building:levels"]) + 1.0
    except (KeyError, ValueError):
        return None


TNY, TNX = int(math.ceil(NY * CELL / TREE_CELL)), int(math.ceil(NX * CELL / TREE_CELL))
tree_img = Image.new("L", (TNX, TNY), int(CFG.get("tree_default", 25)))  # Texas: mostly grass, marsh and town
tdraw = ImageDraw.Draw(tree_img)
density = {("landuse", "forest"): 200, ("natural", "wood"): 200, ("natural", "scrub"): 90, ("natural", "wetland"): 5,
           ("leisure", "park"): 80, ("landuse", "residential"): 45, ("landuse", "commercial"): 5, ("landuse", "industrial"): 0,
           ("landuse", "grass"): 10, ("landuse", "meadow"): 10, ("landuse", "farmland"): 5}
# A world can give its own densities ([key, value, density] rows): the Mediterranean's garrigue and Aleppo pines.
density = {(k, kv): v for k, kv, v in CFG["tree_density"]} if "tree_density" in CFG else density
for el in load_osm("landuse_osm*.json"):
    t = el.get("tags", {})
    val = next((v for (k, kv), v in density.items() if t.get(k) == kv), None)
    if val is not None and el.get("type") == "relation" and CHART != "enc":
        for poly in osm_chart.area_polygons(el):
            for pp in polygons(geom_xy(poly)):
                tdraw.polygon([((y - Y0) / TREE_CELL, (x - X0) / TREE_CELL) for x, y in pp.exterior.coords], fill=val)
        continue
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
    # Same layout as the lake: x, y, ground, length, width, height, yaw. On an osm world, OSM's height or storeys when
    # mapped (the Texas bakes keep their two sizes: their houses come from the G2 lidar instead).
    tags = el.get("tags", {})
    tall = 4.0 if length * width < 400 else 8.0
    if CHART != "enc" and osm_height(tags) is not None:
        tall = round(osm_height(tags), 1)
    buildings.append([round(float(c[0]), 1), round(float(c[1]), 1), round(max(ground, MHW), 2), round(float(length), 1), round(float(width), 1),
                      tall, round(yaw, 1)])
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


height_stations = [station(s) for s in TIDES_CFG.get("stations", [])] if TIDES_CFG["source"] == "noaa" else []
current_station = None
reference = None
if TIDES_CFG.get("current"):
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
LAUNCH = CFG["launch"]
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
# The ENC carries the variation two ways: whole-degree area bands (between isogonic lines) and the compass roses'
# exact values. Use the compass rose nearest home (Kemah, the map origin), not whichever record comes first.
roses = [r for r in features["MAGVAR"] if r.get("geom_xy") is not None and r["geom_xy"].geom_type == "Point"]
mv = min(roses, key=lambda r: r["geom_xy"].x ** 2 + r["geom_xy"].y ** 2) if roses else (features["MAGVAR"][0] if features["MAGVAR"] else None)
variation = None
if "variation" in CFG:
    v = CFG["variation"]
    variation = {"deg_east": v["deg_east"], "base": v["deg_east"], "base_year": v["year"], "annual_change_min": v["annual_change_min"],
                 "year": v["year"], "rose_xy": [0, 0], "source": v["source"]}
elif mv is not None:
    base_year = int(scalar(mv.get("RYRMGV")) or 2021)
    variation = {"deg_east": round(float(mv["VALMAG"]) + (2026 - base_year) * float(mv.get("VALACM") or 0.0) / 60.0, 2),
                 "base": float(mv["VALMAG"]), "base_year": base_year, "annual_change_min": float(mv.get("VALACM") or 0.0), "year": 2026,
                 "rose_xy": [round(mv["geom_xy"].x), round(mv["geom_xy"].y)] if mv.get("geom_xy") is not None and mv["geom_xy"].geom_type == "Point" else None}

# ---------------------------------------------------------------- vector chart for the chart view
def tri(poly, tol=max(4.0, 0.4 * CELL)):
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
if CHART_INFO:
    # No ENC: the chart is drawn from the bake itself (depth classes and contours of the grid, soundings sampled from
    # it, OSM land). Labelled as such on the chart view: not for navigation.
    o_areas, o_contours, o_soundings = osm_chart.chart(ctx, height, water, CHART_INFO["land"].intersection(box))
    for cls, p in o_areas:
        for t in tri(p):
            chart["areas"].append([cls] + t)
    for ln, v in o_contours:
        for part in lines(ln.intersection(box)):
            chart["contours"].append([round(v, 1)] + [round(c, 1) for xy in part.simplify(5.0).coords for c in xy])
    chart["soundings"] = [[round(x, 1), round(y, 1), z] for x, y, z in o_soundings]
chart["bridges"] = [[b["name"]] + [c for p in b["points"] for c in p] for b in bridges]
chart["docks"] = [[d["kind"]] + [c for p in d["points"] for c in p] for d in chart_docks]
print(f"chart: {len(chart['areas'])} triangles, {len(chart['contours'])} contours, {len(chart['soundings'])} soundings")

# ---------------------------------------------------------------- write
os.makedirs(OUT, exist_ok=True)
os.makedirs(DOCS, exist_ok=True)
with open(os.path.join(OUT, f"{NAME}.height"), "wb") as fh:
    fh.write(b"SSHT" + struct.pack("<III", 1, NX, NY) + struct.pack("<ffff", CELL, X0, Y0, UNIT))
    fh.write(np.round(height * 100.0 if UNIT == 0.01 else height / UNIT).astype("<i2").tobytes())
with open(os.path.join(OUT, f"{NAME}.trees"), "wb") as fh:
    fh.write(b"SSTR" + struct.pack("<III", 1, TNX, TNY) + struct.pack("<fff", TREE_CELL, X0, Y0))
    fh.write(trees.astype(np.uint8).tobytes())
if TIDES_CFG.get("current"):
    with open(os.path.join(OUT, f"{NAME}.current"), "wb") as fh:
        fh.write(b"SSCF" + struct.pack("<III", 1, cnx, cny) + struct.pack("<fff", CURRENT_CELL, X0, Y0))
        fh.write(np.round(dir_x * 10000).astype("<i2").tobytes())
        fh.write(np.round(dir_y * 10000).astype("<i2").tobytes())
        fh.write(np.clip(np.round(gain * 1000), 0, 65535).astype("<u2").tobytes())
        fh.write(np.clip(np.round(delay), 0, 65535).astype("<u2").tobytes())
meta = {
    "name": CFG["display"],
    "ocean": CFG["ocean"],
    "grid": {"rows_north": NY, "cols_east": NX, "cell_m": CELL, "origin_north_m": X0, "origin_east_m": Y0, "height_unit_m": UNIT},
    "trees": {"rows_north": TNY, "cols_east": TNX, "cell_m": TREE_CELL},
    "projection": LOCAL,
    "datum": "MLLW (chart datum); heights in meters above it",
    "mhw_m": round(MHW, 3), "navd88_to_mllw_m": round(NAVD_TO_MLLW, 3) if NAVD_TO_MLLW is not None else None,
    "latitude": CENTER[0], "longitude": CENTER[1],
    "sources": {
        "chart": "NOAA ENC cells " + ", ".join(sorted(os.path.basename(c)[:-4] for c in cells)) + " (public domain)",
        "elevation": "USGS 3D Elevation Program, 1/3 arc-second, NAVD88 converted to MLLW (public domain)" if os.path.exists(os.path.join(RAW, "dem_3dep.tif")) else "none: barrier islands as flat land",
        "tides": "NOAA CO-OPS harmonic constituents and datums: " + ", ".join(st["name"] for st in height_stations) + ("; currents: Bolivar Roads ACT8856 bin 2" if TIDES_CFG.get("current") else ""),
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
    "passage": [{"name": nm, "xy": [round(v, 1) for v in ll2xy(la, lo_)]} for nm, la, lo_ in CFG["passage"]],
}
if CHART_INFO:
    # A coast without an official chart or tide model: say where everything came from, and carry the world's own
    # extras (its ports, climate, the city glow and the far coast ring's sources) for the game.
    del meta["navd88_to_mllw_m"]
    meta["datum"] = CFG["datum"]["name"]
    meta["coast"] = True
    meta["iala"] = CFG.get("iala", "A")
    if "time_zone" in CFG:
        meta["time_zone"] = CFG["time_zone"]
    meta["sources"] = {"chart": CHART_INFO["chart"], "elevation": "; ".join(ELEVATION_USED) or "none",
                       "tides": TIDES_CFG.get("note", "none"), "buildings_landuse": "OpenStreetMap contributors, ODbL 1.0"}
    meta["harbours"] = CHART_INFO["harbours"]
    names = [sp["name"] for sp in launch]
    meta["spots"] = {k: names.index(v[0]) for k, v in CFG.get("spots", {}).items() if v[0] in names}
    meta["ports"] = [{"name": pt["name"], "xy": [round(v, 1) for v in ll2xy(pt["lat"], pt["lon"])]} for pt in CFG.get("ports", [])]
    meta["city_glow"] = [{"name": c["name"], "xy": [round(v, 1) for v in ll2xy(c["lat"], c["lon"])], "radius_m": c["radius_km"] * 1000.0,
                          "population": c["population"]} for c in CFG.get("city_glow", [])]
    if "climate" in CFG:
        meta["climate"] = {k: v for k, v in CFG["climate"].items() if not k.endswith("_note")}
    if "far_ring" in CFG:
        fr = CFG["far_ring"]
        meta["far_ring"] = {"radius_km": fr["radius_km"], "draw_km": fr["draw_km"],
                            "skyline": [{"name": n, "xy": [round(v, 1) for v in ll2xy(la, lo_)], "height_m": h} for n, la, lo_, h in fr["skyline"]]}
with open(os.path.join(OUT, f"{NAME}.json"), "w") as fh:
    json.dump(meta, fh, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o))
with open(os.path.join(OUT, f"{NAME}.chart.json"), "w") as fh:
    json.dump(chart, fh, separators=(",", ":"))

# Preview: depth shading, land, navaids.
rgb = np.zeros((NY, NX, 3), np.uint8)
dshade = np.clip(-height / float(CFG.get("preview_depth_m", 6.0)), 0, 1)
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
if CHART != "enc":
    img.convert("RGB").save(os.path.join(DOCS, "terrain-preview.jpg"), quality=85)   # docs images are JPEGs under 300 KB
else:
    img.save(os.path.join(DOCS, "terrain-preview.png" if NAME == "GalvestonBay" else f"{NAME}-preview.png"))
print("wrote", OUT, "and", DOCS)
