"""Bakes Lake Ray Hubbard (Dallas / Rockwall, Texas) into game data.

Inputs (downloaded into Data/RayHubbard/raw by Tools/terrain/fetch_rayhubbard.sh):
  - TWDB daily levels (level.csv): the latest reading becomes the "gauge" lake level in game
  - USGS 3DEP 1/3 arc-second elevation (dem_3dep.tif), public domain
  - OpenStreetMap: lake multipolygon 952396, docks, bridges, buildings, land use (ODbL)
  - TWDB 2015 volumetric survey of Lake Ray Hubbard: interpolated lake-bottom points (public)
Outputs (Content/TerrainData, packaged with the game):
  - RayHubbard.height : int16 heights in cm relative to the conservation pool (435.5 ft NGVD29), 5 m grid
  - RayHubbard.trees  : uint8 tree density, 20 m grid
  - RayHubbard.json   : grid and projection, sources, docks, bridges, buildings, launch spots, shoreline checkpoints
  - docs/phase-3/terrain-preview.png

World frame: local transverse Mercator centered on the lake, meters; game X = north, Y = east, Z = up,
Z = 0 at the conservation pool.

Run: Tools/venv/bin/python Tools/terrain/build_rayhubbard.py
"""
import json
import math
import os
import struct
import sys

import numpy as np
import shapefile
import tifffile
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "Data", "RayHubbard", "raw")
OUT = os.path.join(ROOT, "Content", "TerrainData")
DOCS = os.path.join(ROOT, "docs", "phase-3")

POOL_FT = 435.5                      # conservation pool, ft NGVD29 (TWDB)
FT = 0.3048006096                    # US survey foot
POOL_M = POOL_FT * FT
LAT0, LON0 = 32.8233, -96.5000         # projection center: Rush Creek Yacht Club, so home waters are near the origin
CELL = 5.0                          # m
TREE_CELL = 20.0
DEM_BBOX = (-96.62, 32.78, -96.445, 33.025)  # lon_min, lat_min, lon_max, lat_max of dem_3dep.tif

LOCAL = f"+proj=tmerc +lat_0={LAT0} +lon_0={LON0} +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m +no_defs"
to_local = Transformer.from_crs("EPSG:4326", LOCAL, always_xy=True)
from_local = Transformer.from_crs(LOCAL, "EPSG:4326", always_xy=True)
sp_to_local = Transformer.from_crs("EPSG:2276", LOCAL, always_xy=True)  # TWDB: Texas North Central, US ft


def ll2xy(lat, lon):
    """lat/lon -> game (X north, Y east) meters."""
    e, n = to_local.transform(lon, lat)
    return n, e


def load_json(name):
    with open(os.path.join(RAW, name)) as f:
        return json.load(f)


# ---------------------------------------------------------------- grid
corners = [ll2xy(DEM_BBOX[1], DEM_BBOX[0]), ll2xy(DEM_BBOX[3], DEM_BBOX[2]), ll2xy(DEM_BBOX[1], DEM_BBOX[2]), ll2xy(DEM_BBOX[3], DEM_BBOX[0])]
X0 = math.ceil(min(c[0] for c in corners) / CELL) * CELL + CELL
X1 = math.floor(max(c[0] for c in corners) / CELL) * CELL - CELL
Y0 = math.ceil(min(c[1] for c in corners) / CELL) * CELL + CELL
Y1 = math.floor(max(c[1] for c in corners) / CELL) * CELL - CELL
NY = int((X1 - X0) / CELL) + 1  # rows (north)
NX = int((Y1 - Y0) / CELL) + 1  # cols (east)
print(f"grid {NX} x {NY} cells of {CELL} m, north {X0:.0f}..{X1:.0f}, east {Y0:.0f}..{Y1:.0f}")
gx = X0 + np.arange(NY) * CELL
gy = Y0 + np.arange(NX) * CELL
GX, GY = np.meshgrid(gx, gy, indexing="ij")


def xy2rc(x, y):
    return (np.asarray(x) - X0) / CELL, (np.asarray(y) - Y0) / CELL


# ---------------------------------------------------------------- land: USGS 3DEP
# Georeferencing comes from the GeoTIFF itself: the export service widens the requested box to keep square
# pixels, so the requested DEM_BBOX is not the raster's extent.
with tifffile.TiffFile(os.path.join(RAW, "dem_3dep.tif")) as tif:
    dem = tif.pages[0].asarray().astype(np.float64)
    tie = tif.pages[0].tags["ModelTiepointTag"].value
    scale = tif.pages[0].tags["ModelPixelScaleTag"].value
DEM_LON0, DEM_LAT0, DEM_DLON, DEM_DLAT = tie[3], tie[4], scale[0], scale[1]  # top-left corner of pixel (0, 0)
lon, lat = from_local.transform(GY, GX)
fc = (lon - DEM_LON0) / DEM_DLON - 0.5
fr = (DEM_LAT0 - lat) / DEM_DLAT - 0.5
land = ndimage.map_coordinates(dem, [fr, fc], order=1, mode="nearest") - POOL_M
print(f"land relative to pool: {land.min():.1f} .. {land.max():.1f} m")

# ---------------------------------------------------------------- lake bottom: TWDB 2015
r = shapefile.Reader(os.path.join(RAW, "twdb", "RH15_aeidwptsf10_clip"))
fields = [f[0] for f in r.fields[1:]]
ix, iy, iz = fields.index("x"), fields.index("y"), fields.index("current_su")
recs = np.array([(rec[ix], rec[iy], rec[iz]) for rec in r.iterRecords()], dtype=np.float64)
e, n = sp_to_local.transform(recs[:, 0], recs[:, 1])
rr, cc = xy2rc(n, e)
ri, ci = np.round(rr).astype(int), np.round(cc).astype(int)
ok = (ri >= 0) & (ri < NY) & (ci >= 0) & (ci < NX)
bsum = np.zeros((NY, NX)); bcnt = np.zeros((NY, NX))
np.add.at(bsum, (ri[ok], ci[ok]), recs[ok, 2] * FT - POOL_M)
np.add.at(bcnt, (ri[ok], ci[ok]), 1)
has = bcnt > 0
bottom = np.where(has, bsum / np.maximum(bcnt, 1), np.nan)
# Fill gaps inside the lake from the nearest surveyed cell.
idx = ndimage.distance_transform_edt(~has, return_distances=False, return_indices=True)
bottom = bottom[idx[0], idx[1]]
print(f"TWDB points {ok.sum()}, bottom {np.nanmin(bottom):.1f} .. {np.nanmax(bottom):.1f} m (deepest {-np.nanmin(bottom) / FT:.0f} ft)")

# ---------------------------------------------------------------- shoreline: OSM multipolygon
def rings_from_relation(rel, role):
    """Join a multipolygon's member ways of one role into closed rings of (lat, lon)."""
    ways = [[(p["lat"], p["lon"]) for p in m["geometry"]] for m in rel["members"] if m["type"] == "way" and m["role"] == role and m.get("geometry")]
    rings = []
    while ways:
        ring = ways.pop(0)
        changed = True
        while ring[0] != ring[-1] and changed:
            changed = False
            for i, w in enumerate(ways):
                if w[0] == ring[-1]: ring += w[1:]
                elif w[-1] == ring[-1]: ring += w[::-1][1:]
                elif w[-1] == ring[0]: ring = w[:-1] + ring
                elif w[0] == ring[0]: ring = w[::-1][:-1] + ring
                else: continue
                ways.pop(i); changed = True; break
        rings.append(ring)
    return rings


lake = load_json("lake_osm.json")["elements"][0]
outer = rings_from_relation(lake, "outer")
inner = rings_from_relation(lake, "inner")
SS = 4  # supersampling for the water fraction
img = Image.new("L", (NX * SS, NY * SS), 0)
draw = ImageDraw.Draw(img)


def to_px(ring):
    pts = []
    for la, lo in ring:
        x, y = ll2xy(la, lo)
        r_, c_ = xy2rc(x, y)
        pts.append(((c_ + 0.5) * SS - 0.5, (r_ + 0.5) * SS - 0.5))
    return pts


for ring in outer:
    draw.polygon(to_px(ring), fill=255)
for ring in inner:
    draw.polygon(to_px(ring), fill=0)
water = np.asarray(img, dtype=np.float64).reshape(NY, SS, NX, SS).mean(axis=(1, 3)) / 255.0
print(f"OSM lake: {len(outer)} outer rings, {len(inner)} islands, area {water.sum() * CELL * CELL / 1e6:.1f} km^2")

# ---------------------------------------------------------------- combine: the OSM shoreline sets where land meets water
# Land at least 0.4 m above pool, water at least 0.4 m deep, blended by water fraction so the zero contour
# falls where a cell is half covered by the OSM polygon (shoreline within half a cell).
height = (1.0 - water) * np.maximum(land, 0.4) + water * np.minimum(bottom, -0.4)
# Cells the shoreline passes through: symmetric about the pool, so the water's edge falls where the OSM line
# splits the cell, whatever the bank height or depth on either side.
edge = (water > 0.0) & (water < 1.0)
height[edge] = 0.6 - 1.2 * water[edge]
height = np.clip(height, -320.0, 320.0)

# ---------------------------------------------------------------- trees: land use and buildings
TNY, TNX = int(math.ceil(NY * CELL / TREE_CELL)), int(math.ceil(NX * CELL / TREE_CELL))
tree_img = Image.new("L", (TNX, TNY), 70)  # unlabeled land: scattered cross-timbers trees
tdraw = ImageDraw.Draw(tree_img)
density_by_tag = {("landuse", "forest"): 230, ("natural", "wood"): 230, ("leisure", "park"): 120, ("leisure", "nature_reserve"): 200,
                  ("landuse", "residential"): 60, ("landuse", "commercial"): 5, ("landuse", "industrial"): 5,
                  ("landuse", "grass"): 15, ("landuse", "meadow"): 25, ("landuse", "farmland"): 10}


def to_tree_px(geom):
    pts = []
    for p in geom:
        x, y = ll2xy(p["lat"], p["lon"])
        pts.append(((y - Y0) / TREE_CELL, (x - X0) / TREE_CELL))
    return pts


order = ["farmland", "meadow", "grass", "residential", "commercial", "industrial", "park", "nature_reserve", "forest", "wood"]
elements = load_json("landuse_osm.json")["elements"]
elements.sort(key=lambda el: order.index(next((v for k, v in el.get("tags", {}).items() if v in order), "farmland")))
for el in elements:
    tags = el.get("tags", {})
    val = next((d for (k, v), d in density_by_tag.items() if tags.get(k) == v), None)
    if val is None:
        continue
    geoms = [el["geometry"]] if el["type"] == "way" and el.get("geometry") else [m["geometry"] for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
    for g in geoms:
        if len(g) >= 3:
            tdraw.polygon(to_tree_px(g), fill=val)
trees = np.asarray(tree_img, dtype=np.float64)

# Buildings: footprints near the shore become boxes in the game; every footprint clears trees.
buildings = []
water_dist = ndimage.distance_transform_edt(water < 0.5) * CELL  # distance to water (m) for land cells
for el in load_json("buildings_osm.json")["elements"]:
    g = el.get("geometry")
    if not g or len(g) < 4:
        continue
    pts = np.array([ll2xy(p["lat"], p["lon"]) for p in g[:-1]])
    cx, cy = pts.mean(axis=0)
    r_, c_ = xy2rc(cx, cy)
    if not (0 <= r_ < NY and 0 <= c_ < NX):
        continue
    tr, tc = int((cx - X0) / TREE_CELL), int((cy - Y0) / TREE_CELL)
    if 0 <= tr < TNY and 0 <= tc < TNX:
        trees[tr, tc] *= 0.3
    if water_dist[int(r_), int(c_)] > 450.0:
        continue
    # Oriented box from the longest edge.
    edges = np.diff(np.vstack([pts, pts[:1]]), axis=0)
    k = int(np.argmax(np.hypot(edges[:, 0], edges[:, 1])))
    ang = math.atan2(edges[k, 1], edges[k, 0])
    ca, sa = math.cos(ang), math.sin(ang)
    rel = pts - [cx, cy]
    u = rel[:, 0] * ca + rel[:, 1] * sa
    v = -rel[:, 0] * sa + rel[:, 1] * ca
    length, width = float(u.max() - u.min()), float(v.max() - v.min())
    if length < 3 or width < 3 or length > 250:
        continue
    levels = el.get("tags", {}).get("building:levels")
    try:
        h = float(levels) * 3.2 if levels else (4.5 if el.get("tags", {}).get("building") in ("house", "garage", "shed") else 7.0)
    except ValueError:
        h = 6.0
    ground = float(land[int(r_), int(c_)])
    buildings.append([round(float(cx + (u.max() + u.min()) / 2 * ca - (v.max() + v.min()) / 2 * sa), 1),
                      round(float(cy + (u.max() + u.min()) / 2 * sa + (v.max() + v.min()) / 2 * ca), 1),
                      round(max(ground, 0.4), 1), round(length, 1), round(width, 1), round(h, 1), round(math.degrees(ang), 1)])
print(f"buildings near the shore: {len(buildings)}")

# No trees in the water or on the beach line; fewer on steep banks (rock).
wl = np.zeros((TNY, TNX))
wsmall = water[: TNY * 2, : TNX * 2]
wl[: wsmall.shape[0] // 2, : wsmall.shape[1] // 2] = wsmall[: wsmall.shape[0] // 2 * 2, : wsmall.shape[1] // 2 * 2].reshape(wsmall.shape[0] // 2, 2, wsmall.shape[1] // 2, 2).max(axis=(1, 3))
trees[wl > 0.05] = 0
trees = np.clip(trees, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- docks, bridges, launch spots, checkpoints
def local_polyline(geom):
    return [[round(v, 2) for v in ll2xy(p["lat"], p["lon"])] for p in geom]


docks = []
for name in ("club_osm.json", "marinas_osm.json"):
    for el in load_json(name)["elements"]:
        t = el.get("tags", {})
        if t.get("man_made") in ("pier", "breakwater") and el.get("geometry"):
            docks.append({"id": el["id"], "kind": t["man_made"], "points": local_polyline(el["geometry"])})
seen = set(); docks = [d for d in docks if not (d["id"] in seen or seen.add(d["id"]))]

bridges = []
for el in load_json("bridges_osm.json")["elements"]:
    t = el.get("tags", {})
    if not el.get("geometry"):
        continue
    pts = local_polyline(el["geometry"])
    # Keep bridge spans that cross open water.
    wet = 0
    for x, y in pts:
        r_, c_ = xy2rc(x, y)
        if 0 <= r_ < NY and 0 <= c_ < NX and water[int(r_), int(c_)] > 0.5:
            wet += 1
    if wet == 0 and len(pts) >= 2:
        mx, my = (pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2
        r_, c_ = xy2rc(mx, my)
        if not (0 <= r_ < NY and 0 <= c_ < NX and water[int(r_), int(c_)] > 0.5):
            continue
    bridges.append({"name": t.get("ref") or t.get("name") or t.get("railway") or "bridge", "kind": t.get("highway") or t.get("railway"), "points": pts,
                    "deck": 7.0 if t.get("highway") in ("motorway", "trunk", "primary") else 5.0})
print(f"docks {len(docks)}, bridges over water {len(bridges)}")


def lake_xy(lat, lon):
    x, y = ll2xy(lat, lon)
    return [round(x, 1), round(y, 1)]


launch_spots = [
    {"name": "Rush Creek Yacht Club", "lat": 32.82335, "lon": -96.50040, "heading": 300.0},
    {"name": "Off Rush Creek, open water", "lat": 32.8290, "lon": -96.5060, "heading": 0.0},
    {"name": "South lake, near the dam", "lat": 32.8150, "lon": -96.5150, "heading": 30.0},
    {"name": "Chandlers Landing", "lat": 32.8735, "lon": -96.4880, "heading": 270.0},
    {"name": "North lake, below the SH-66 causeway", "lat": 32.9120, "lon": -96.5100, "heading": 180.0},
]
for s in launch_spots:
    x, y = ll2xy(s["lat"], s["lon"])
    # Move each spot to the nearest water at least 2 m deep (spots are picked by hand from the map).
    r_, c_ = int(round((x - X0) / CELL)), int(round((y - Y0) / CELL))
    if s["name"] != "Rush Creek Yacht Club":
        deep = height < -2.0
        rr, cc = np.nonzero(deep[max(0, r_ - 300):r_ + 300, max(0, c_ - 300):c_ + 300])
        rr = rr + max(0, r_ - 300); cc = cc + max(0, c_ - 300)
        k = int(np.argmin((rr - r_) ** 2 + (cc - c_) ** 2))
        x, y = X0 + rr[k] * CELL, Y0 + cc[k] * CELL
    s["xy"] = [round(float(x), 1), round(float(y), 1)]
    s["depth_m"] = round(float(-height[int(round((x - X0) / CELL)), int(round((y - Y0) / CELL))]), 1)

# Shoreline checkpoints: the nearest vertex of the main OSM shoreline (outer ring, away from islands and spits
# narrower than the grid) to each site; the test checks the terrain's zero contour against it.
islands = np.array([ll2xy(la, lo) for ring in inner for la, lo in ring]) if inner else np.zeros((0, 2))
shore_all = np.array([ll2xy(la, lo) for ring in outer for la, lo in ring])
keep = np.zeros(len(shore_all), bool)


def frac(x, y):
    r_, c_ = int(round((x - X0) / CELL)), int(round((y - Y0) / CELL))
    return water[r_, c_] if 0 <= r_ < NY and 0 <= c_ < NX else 0.0


for i in range(3, len(shore_all) - 3):
    x, y = shore_all[i]
    if len(islands) and np.min(np.hypot(islands[:, 0] - x, islands[:, 1] - y)) < 40.0:
        continue
    # A real stretch of shore: solid land 15 m to one side and open water 15 m to the other, across the local line.
    tx, ty = shore_all[i + 3] - shore_all[i - 3]
    n = np.hypot(tx, ty)
    if n < 5.0:
        continue
    nx_, ny_ = -ty / n, tx / n
    a, b = frac(x + nx_ * 15, y + ny_ * 15), frac(x - nx_ * 15, y - ny_ * 15)
    keep[i] = (a > 0.99 and b < 0.01) or (a < 0.01 and b > 0.99)
shore = shore_all[keep]
checkpoints = []
for name, la, lo in (("Rush Creek Yacht Club docks", 32.8228, -96.4983), ("Chandlers Landing", 32.8751, -96.4805), ("Harry Myers Park", 32.9304, -96.4513)):
    x, y = ll2xy(la, lo)
    k = int(np.argmin(np.hypot(shore[:, 0] - x, shore[:, 1] - y)))
    checkpoints.append({"name": name, "shore": [round(float(shore[k, 0]), 2), round(float(shore[k, 1]), 2)]})

# Latest TWDB gauge reading (level.csv from Water Data for Texas), or the reading at the first bake.
level_date, level_ft = "2026-10-11", 432.32
level_csv = os.path.join(RAW, "level.csv")
if os.path.exists(level_csv):
    rows = [l.split(",") for l in open(level_csv) if l[:1].isdigit()]
    rows = [r for r in rows if len(r) > 1 and r[1]]
    if rows:
        level_date, level_ft = rows[-1][0], float(rows[-1][1])
print(f"gauge {level_date}: {level_ft:.2f} ft ({POOL_FT - level_ft:.2f} ft below pool)")

meta = {
    "name": "Lake Ray Hubbard",
    "grid": {"rows_north": NY, "cols_east": NX, "cell_m": CELL, "origin_north_m": X0, "origin_east_m": Y0, "height_unit_m": 0.01},
    "trees": {"rows_north": TNY, "cols_east": TNX, "cell_m": TREE_CELL},
    "projection": LOCAL,
    "pool_ft_ngvd29": POOL_FT,
    f"level_{level_date.replace('-', '_')}_ft": level_ft,
    "sources": {
        "elevation": "USGS 3D Elevation Program, 1/3 arc-second, exported Oct 2026 (public domain)",
        "bathymetry": "Texas Water Development Board, 2015 Volumetric Survey of Lake Ray Hubbard, interpolated bottom points (public)",
        "shoreline_docks_bridges_buildings_landuse": "OpenStreetMap contributors, ODbL 1.0 (lake relation 952396)",
        "pool_level": "TWDB Water Data for Texas, conservation pool 435.5 ft NGVD29",
    },
    "launch_spots": launch_spots,
    "checkpoints": checkpoints,
    "docks": docks,
    "bridges": bridges,
    "buildings": buildings,
}

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "RayHubbard.height"), "wb") as f:
    f.write(b"SSHT" + struct.pack("<IIIffff", 1, NX, NY, CELL, X0, Y0, 0.01))
    f.write(np.round(height * 100).astype("<i2").tobytes())
with open(os.path.join(OUT, "RayHubbard.trees"), "wb") as f:
    f.write(b"SSTR" + struct.pack("<IIIfff", 1, TNX, TNY, TREE_CELL, X0, Y0))
    f.write(trees.tobytes())
with open(os.path.join(OUT, "RayHubbard.json"), "w") as f:
    json.dump(meta, f, separators=(",", ":"))

# Preview: hillshaded land, depth-shaded water, docks and bridges.
os.makedirs(DOCS, exist_ok=True)
gy_, gx_ = np.gradient(height)
shade = np.clip(0.6 + 0.5 * (gx_ - gy_) / CELL, 0, 1)
rgb = np.zeros((NY, NX, 3))
depth = np.clip(-height / 15.0, 0, 1)
landc = np.stack([0.55 + 0.2 * shade, 0.5 + 0.2 * shade, 0.35 + 0.15 * shade], -1) * (1 - 0.35 * (trees.repeat(int(TREE_CELL / CELL), 0).repeat(int(TREE_CELL / CELL), 1)[:NY, :NX, None] / 255.0))
waterc = np.stack([0.2 - 0.15 * depth, 0.45 - 0.3 * depth, 0.65 - 0.3 * depth], -1)
rgb = np.where(height[..., None] < 0, waterc, landc)
img = Image.fromarray((np.flipud(rgb) * 255).astype(np.uint8))
d = ImageDraw.Draw(img)
for b in bridges:
    d.line([((p[1] - Y0) / CELL, NY - 1 - (p[0] - X0) / CELL) for p in b["points"]], fill=(220, 40, 40), width=3)
for s in launch_spots:
    c, r_ = (s["xy"][1] - Y0) / CELL, NY - 1 - (s["xy"][0] - X0) / CELL
    d.ellipse([c - 6, r_ - 6, c + 6, r_ + 6], outline=(255, 255, 0), width=2)
img.save(os.path.join(DOCS, "terrain-preview.png"))
print("wrote", OUT, "and", os.path.join(DOCS, "terrain-preview.png"))
