"""Graphics G2: bakes the 1 m shore detail of Lake Ray Hubbard from the USGS 3DEP 1 m lidar DEM.

The 5 m grid (RayHubbard.height, build_rayhubbard.py) shows facets near the camera. This adds a 1 m layer, only where
it is seen up close: a band around the shoreline (land within LAND_BAND of the water, water within WATER_BAND of the
land), in 64 m tiles of 65 x 65 nodes. FLakeTerrain uses it wherever a tile exists (HeightAt and the near terrain
chunks); everywhere else the 5 m grid stands.

  - land: the lidar bare-earth DEM (TX Pecos Dallas 2018, NAVD88, treated like the 5 m bake's elevations) minus the pool
  - water: the lidar is hydro-flattened at the 2018 water level there, so it says nothing about the bed; the bed comes
    from the 5 m grid (TWDB bathymetry), meeting the lidar shoreline on a shelf that deepens 8 cm per metre
  - the band's outer edge blends into the 5 m grid over EDGE_BLEND metres, so there is no step where detail ends

Inputs: Content/TerrainData/RayHubbard.height (run build_rayhubbard.py first), Data/RayHubbard/raw/lidar/*.tif
(Tools/terrain/fetch_rayhubbard.sh). Output: Content/TerrainData/RayHubbard.detail:
  "SSDZ" + uint32 raw size + zlib( "SSDT" + uint32 version 1, tile cells 64, tile count, float cell 1.0, origin north,
  origin east, unit 0.01; then per tile int32 row, int32 col; then per tile 65 x 65 int16 heights in cm relative to the
  pool, rows north, columns east )

Run: Tools/venv/bin/python -I Tools/terrain/build_shore_detail.py
"""
import glob
import math
import os
import struct
import zlib

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "Data", "RayHubbard", "raw", "lidar")
OUT = os.path.join(ROOT, "Content", "TerrainData")
POOL_M = 435.5 * 0.3048006096
LAT0, LON0 = 32.8233, -96.5000
LOCAL = f"+proj=tmerc +lat_0={LAT0} +lon_0={LON0} +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m +no_defs"
TILE = 64            # cells (m) per tile side
LAND_BAND = 150.0    # m of land from the water
WATER_BAND = 30.0    # m of water from the land
EDGE_BLEND = 12.0    # m over which the detail fades into the 5 m grid at the band's edge
SHELF = 0.08         # m of depth per m from the lidar shoreline, until the bathymetry is deeper
Image.MAX_IMAGE_PIXELS = None

# ---------------------------------------------------------------- the 5 m grid
with open(os.path.join(OUT, "RayHubbard.height"), "rb") as f:
    data = f.read()
_, ver, NX, NY, CELL, X0, Y0, UNIT = struct.unpack("<4sIIIffff", data[:32])
H5 = np.frombuffer(data[32:32 + NX * NY * 2], "<i2").reshape(NY, NX).astype(np.float64) * UNIT
print(f"5 m grid {NX} x {NY}, origin {X0:.0f}, {Y0:.0f}")
water5 = H5 < 0.0
land_dist = ndimage.distance_transform_edt(~water5) * CELL     # land cells: metres to water
water_dist = ndimage.distance_transform_edt(water5) * CELL     # water cells: metres to land
band5 = (~water5 & (land_dist <= LAND_BAND)) | (water5 & (water_dist <= WATER_BAND))

# Tiles that the band touches (tile (i, j) spans rows north X0 + 64 i .. + 64, columns east Y0 + 64 j .. + 64).
TR, TC = int(math.ceil((NY - 1) * CELL / TILE)), int(math.ceil((NX - 1) * CELL / TILE))
per = int(TILE / CELL)
pad = np.zeros((TR * per + 1, TC * per + 1), bool)
pad[:NY, :NX] = band5[:TR * per + 1, :TC * per + 1]
sel = pad[:TR * per, :TC * per].reshape(TR, per, TC, per).any(axis=(1, 3))

# ---------------------------------------------------------------- the lidar mosaic (UTM 14N, NAD83)
to_utm = Transformer.from_crs(LOCAL, "EPSG:26914", always_xy=True)
tiles = []
for path in sorted(glob.glob(os.path.join(RAW, "*.tif"))):
    im = Image.open(path)
    tie = im.tag_v2[33922]
    scale = im.tag_v2[33550]
    tiles.append({"path": path, "e0": tie[3], "n0": tie[4], "de": scale[0], "dn": scale[1], "w": im.size[0], "h": im.size[1], "a": None})
print(f"lidar tiles: {len(tiles)}")


def lidar_at(e, n):
    """Bilinear lidar elevation (NAVD88 m) at UTM points; NaN where no tile covers them or there is no data."""
    out = np.full(e.shape, np.nan)
    for t in tiles:
        c = (e - t["e0"]) / t["de"] - 0.5
        r = (t["n0"] - n) / t["dn"] - 0.5
        inside = (c >= 0) & (r >= 0) & (c <= t["w"] - 1) & (r <= t["h"] - 1) & np.isnan(out)
        if not inside.any():
            continue
        if t["a"] is None:
            t["a"] = np.asarray(Image.open(t["path"]), dtype=np.float32)
        v = ndimage.map_coordinates(t["a"], [r[inside], c[inside]], order=1, mode="nearest")
        v[v < -1000] = np.nan
        out[inside] = v
    return out


def h5_at(x, y):
    return ndimage.map_coordinates(H5, [(x - X0) / CELL, (y - Y0) / CELL], order=1, mode="nearest")


# The 2018 water level: the flattened value over open water.
wr, wc = np.nonzero(water5 & (water_dist > 200.0))
pick = np.random.default_rng(1).choice(len(wr), 4000, replace=False)
xs, ys = X0 + wr[pick] * CELL, Y0 + wc[pick] * CELL
e, n = to_utm.transform(ys, xs)
lv = lidar_at(np.asarray(e), np.asarray(n))
lv = lv[np.isfinite(lv)]
vals, counts = np.unique(np.round(lv, 2), return_counts=True)
FLAT = float(vals[np.argmax(counts)])
print(f"hydro-flattened lake surface {FLAT:.2f} m NAVD88 ({(FLAT - POOL_M) / 0.3048:+.2f} ft against the pool), {counts.max() / len(lv):.0%} of samples")

# Distance (m) from each point to the edge of the selected tiles, on a 4 m raster, for the blend.
EDGE_RES = 4.0
k = int(TILE / EDGE_RES)
fine = np.repeat(np.repeat(sel, k, 0), k, 1)
edge_dist = ndimage.distance_transform_edt(np.pad(fine, 1))[1:-1, 1:-1] * EDGE_RES

# ---------------------------------------------------------------- bake each tile
idx = np.argwhere(sel)
print(f"band tiles: {len(idx)} of {TR * TC} ({len(idx) * TILE * TILE / 1e6:.1f} km^2)")
N = TILE + 1
heights = np.zeros((len(idx), N, N), np.int16)
stats = {"no_lidar": 0, "water": 0, "nodes": 0}
A = 48  # apron (m): the shelf's distance to the shore is measured past the tile's edge and capped at A, so neighbours agree
for t, (i, j) in enumerate(idx):
    M = N + 2 * A
    x = X0 + i * TILE - A + np.arange(M)[:, None] + np.zeros((1, M))
    y = Y0 + j * TILE - A + np.arange(M)[None, :] + np.zeros((M, 1))
    e, n = to_utm.transform(y.ravel(), x.ravel())
    lid = lidar_at(np.asarray(e), np.asarray(n)).reshape(M, M)
    base = h5_at(x.ravel(), y.ravel()).reshape(M, M)
    # Water: the flattened surface (within 3 cm) near the 5 m grid's water, and, where the grid is clearly lake, anything
    # near that level (bare earth interpolated under bridges and docks). Its depth: the shelf from the lidar shoreline,
    # or the bathymetry where that is deeper.
    lake = np.isfinite(lid) & (((np.abs(lid - FLAT) < 0.03) & (base < 1.5)) | ((np.abs(lid - FLAT) < 1.0) & (base < -1.0)))
    shore_d = ndimage.distance_transform_edt(lake)  # 1 m nodes: distance to the nearest non-lake node
    h = np.where(lake, np.minimum(base, (FLAT - POOL_M) - 0.15 - SHELF * np.minimum(shore_d, A)), lid - POOL_M)
    x, y, lid, base, lake, h = (a[A:A + N, A:A + N] for a in (x, y, lid, base, lake, h))
    ok = np.isfinite(h)
    h = np.where(ok, h, base)
    w = np.clip((ndimage.map_coordinates(edge_dist, [(x - X0) / EDGE_RES - 0.5, (y - Y0) / EDGE_RES - 0.5], order=1, mode="nearest") - EDGE_RES) / EDGE_BLEND, 0.0, 1.0)
    w = np.where(ok, w * w * (3 - 2 * w), 0.0)
    h = base + (h - base) * w
    heights[t] = np.round(np.clip(h, -320, 320) * 100).astype(np.int16)
    stats["no_lidar"] += int((~ok).sum())
    stats["water"] += int(lake.sum())
    stats["nodes"] += N * N
    if t % 1000 == 0:
        print(f"  tile {t}/{len(idx)}")
print(f"nodes {stats['nodes']:,}: lake {stats['water'] / stats['nodes']:.0%}, without lidar {stats['no_lidar'] / stats['nodes']:.1%}")
d = heights.astype(np.float64) / 100.0
print(f"detail heights {d.min():.1f} .. {d.max():.1f} m")

raw = b"SSDT" + struct.pack("<IIIffff", 1, TILE, len(idx), 1.0, X0, Y0, 0.01)
raw += idx.astype("<i4").tobytes() + heights.astype("<i2").tobytes()
packed = zlib.compress(raw, 9)
with open(os.path.join(OUT, "RayHubbard.detail"), "wb") as f:
    f.write(b"SSDZ" + struct.pack("<I", len(raw)) + packed)
print(f"wrote RayHubbard.detail: {len(raw) / 1e6:.1f} MB raw, {len(packed) / 1e6:.1f} MB compressed")
