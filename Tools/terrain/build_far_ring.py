"""Wide World Rendering, PR 1: bakes a world's far coast ring (docs/world-far).

The near terrain (ALakeTerrainActor's chunks from the world's grid) stops at the ring's inner edge (8 km from the camera);
past it, out to the outer edge (40 km from anywhere in the grid on Galveston Bay and the Gulf), the land is drawn from
static Nanite meshes, one per 8 km tile, which UWorldKitLibrary::BakeFarRing builds from the file this script writes:

  Content/TerrainData/<World>.far   "SSFR", version 1, tile count, tile size, inner and outer edge, height unit (m: 0.01,
                                    or 0.05 where the land rises past 320 m); then per tile its row and column (north,
                                    east, in tiles from the map origin), cells per side and the byte offset of its data;
                                    then each tile's (n+1)^2 int16 heights (units above the world's datum, rows north,
                                    columns east) and (n+1)^2 uint8 sky visibility (255 open).

Heights: the world's own grid wherever it reaches (sampled as FLakeTerrain::HeightAt does, so the hand-over to the near
chunks has no step), the Copernicus DEM GLO-90 beyond it (Tools/terrain/fetch_far_dem.sh; EGM2008 heights, taken as
NAVD88 on the Texas coast, then the world's NAVD88 -> datum; as NGF-IGN69 in Marseille), blended over the first kilometre outside the grid. GLO-90 is a surface model:
its water is flat at about 0, which becomes a bed under the water here; land never sits below mean high water + 0.25 m,
as in the grid's bake. Tiles out to coarse_past_km from the grid are meshed at cell_m (88 cells), the rest at coarse_m
(44); a fine tile's edge against a coarse one takes the coarse edge's straight line, so the meshes meet without cracks.
Tiles with no land above -1 m are left out. Sky visibility is the open share of the sky over eight horizons marched to
2 km (the material darkens hollows and valley floors with it).

Ultra (--ultra): <World>.far30, the same format meshed at 30.3 m (264 cells) out to coarse_past_km and 90.9 beyond, from
the Copernicus DEM GLO-30 (glo30_<tile>.tif beside the GLO-90 files; a missing GLO-30 tile falls back to GLO-90). The game
draws it on Ultra (FFarRingData::PathFor(World, "30"), /Game/World/Far30).

Run: Tools/venv/bin/python Tools/terrain/build_far_ring.py [--ultra] [World ...]   (default GalvestonBay GulfPassage Marseille)
     ... --tiles [World ...] prints the GLO-90 tile names the worlds need (fetch_far_dem.sh uses it).
"""
import json
import math
import os
import struct
import sys
import time

import numpy as np
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TERRAIN = os.path.join(ROOT, "Content", "TerrainData")
RAW = os.path.join(ROOT, "Data", "Far", "raw")
CONFIG = json.load(open(os.path.join(ROOT, "Tools", "terrain", "far_ring.json")))
DEFAULT = CONFIG["_default"]
WORLDS = ["GalvestonBay", "GulfPassage", "Marseille"]


ULTRA = False   # --ultra: the GLO-30 ring (far_ring.json's _ultra spacings), written to <World>.far30


def ring_config(world):
    """far_ring.json's entry for the world, else the default with the world bake's own far_ring.draw_km as the outer edge
    (Marseille: 60 km; Tools/coast/worlds/<World>.json); None when the world has neither (Ray Hubbard: no ring). With
    --ultra the spacings are _ultra's."""
    ultra = CONFIG.get("_ultra", {}) if ULTRA else {}
    if world in CONFIG:
        return {**DEFAULT, **CONFIG[world], **ultra}
    meta = json.load(open(os.path.join(TERRAIN, f"{world}.json")))
    if "far_ring" in meta:
        return {**DEFAULT, "outer_km": meta["far_ring"]["draw_km"], **ultra}
    return None


def raw_dirs(world):
    """Where GLO-90 tiles may be: this tool's own downloads and a world's (Tools/coast/fetch_world.py puts them in
    Data/<World>/raw/far)."""
    return [RAW, os.path.join(ROOT, "Data", world, "raw", "far")]
FAR_WATER = -2.0        # GLO-90's flattened water, as a bed under the water plane
BLEND_M = 1000.0        # the grid fades into GLO-90 over this, outside the grid
SKY_REACH_M = 2000.0


def world_meta(world):
    meta = json.load(open(os.path.join(TERRAIN, f"{world}.json")))
    g = meta["grid"]
    return meta, g


def load_grid(world):
    with open(os.path.join(TERRAIN, f"{world}.height"), "rb") as fh:
        data = fh.read()
    assert data[:4] == b"SSHT"
    _, nx, ny = struct.unpack_from("<III", data, 4)
    cell, x0, y0, unit = struct.unpack_from("<ffff", data, 16)
    h = np.frombuffer(data, dtype="<i2", count=nx * ny, offset=32).reshape(ny, nx).astype(np.float64) * unit
    return h, float(cell), float(x0), float(y0)


def grid_box(meta):
    g = meta["grid"]
    x0, y0, c = g["origin_north_m"], g["origin_east_m"], g["cell_m"]
    return x0, y0, x0 + (g["rows_north"] - 1) * c, y0 + (g["cols_east"] - 1) * c


def box_distance(bx, tx0, ty0, tx1, ty1):
    """Nearest distance (m) between the grid box and a tile rectangle."""
    dx = max(0.0, bx[0] - tx1, tx0 - bx[2])
    dy = max(0.0, bx[1] - ty1, ty0 - bx[3])
    return math.hypot(dx, dy)


def ring_tiles(world):
    """(row, col, cells) for every tile within the ring's outer edge of the grid."""
    meta, _ = world_meta(world)
    cfg = ring_config(world)
    bx = grid_box(meta)
    T = cfg["tile_km"] * 1000.0
    ext = cfg["outer_km"] * 1000.0
    out = []
    for i in range(math.floor((bx[0] - ext) / T), math.floor((bx[2] + ext) / T) + 1):
        for j in range(math.floor((bx[1] - ext) / T), math.floor((bx[3] + ext) / T) + 1):
            d = box_distance(bx, i * T, j * T, (i + 1) * T, (j + 1) * T)
            if d > ext:
                continue
            fine = d <= cfg["coarse_past_km"] * 1000.0
            out.append((i, j, int(round(T / (cfg["cell_m"] if fine else cfg["coarse_m"])))))
    return meta, cfg, out


def transformer(meta):
    from pyproj import Transformer
    return Transformer.from_crs(meta["projection"], "EPSG:4326", always_xy=True)


def glo_tile_name(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00"


def needed_glo(world):
    meta, cfg, tiles = ring_tiles(world)
    tr = transformer(meta)
    T = cfg["tile_km"] * 1000.0
    names = set()
    for i, j, _ in tiles:
        for a in np.linspace(0, 1, 5):
            for b in np.linspace(0, 1, 5):
                lon, lat = tr.transform((j + b) * T, (i + a) * T)
                names.add(glo_tile_name(math.floor(lat), math.floor(lon)))
    return sorted(names)


class Glo:
    """The GLO-90 tiles on disk (with --ultra the GLO-30 ones first, GLO-90 where a 30 m tile is missing), sampled
    bilinearly by latitude and longitude."""

    def __init__(self, dirs):
        import tifffile
        self.tiles = {}
        for prefix in (("glo30_", "glo90_") if ULTRA else ("glo90_",)):
            for d in dirs:
                for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                    if not (f.startswith(prefix) and f.endswith(".tif")) or f[6:-4] in self.tiles:
                        continue
                    self.load(tifffile, os.path.join(d, f), f[6:-4])

    def load(self, tifffile, path, name):
        if True:
            with tifffile.TiffFile(path) as tif:
                page = tif.pages[0]
                dem = page.asarray().astype(np.float64)
                tie = page.tags["ModelTiepointTag"].value
                scale = page.tags["ModelPixelScaleTag"].value
            self.tiles[name] = (dem, tie[3], tie[4], scale[0], scale[1])

    def sample(self, lat, lon):
        out = np.full(lat.shape, np.nan)
        keys = np.array([glo_tile_name(math.floor(a), math.floor(o)) for a, o in zip(lat.ravel(), lon.ravel())]).reshape(lat.shape)
        for k in np.unique(keys):
            m = keys == k
            if k not in self.tiles:
                out[m] = 0.0   # no tile: all sea
                continue
            dem, lon0, lat0, sx, sy = self.tiles[k]
            # GLO-90's tiles are PixelIsPoint (GTRasterTypeGeoKey 2): the tiepoint is the first pixel's centre.
            fc = (lon[m] - lon0) / sx
            fr = (lat0 - lat[m]) / sy
            out[m] = ndimage.map_coordinates(dem, [fr, fc], order=1, mode="nearest")
        return out


def grid_sample(h, cell, x0, y0, X, Y):
    """FLakeTerrain::HeightAt on the grid (no lidar detail on the coasts): bilinear, clamped at the edge."""
    R = np.clip((X - x0) / cell, 0, h.shape[0] - 1)
    C = np.clip((Y - y0) / cell, 0, h.shape[1] - 1)
    return ndimage.map_coordinates(h, [R, C], order=1, mode="nearest")


def heights(world_ctx, X, Y):
    meta, h, cell, x0, y0, bx, tr, glo, navd, mhw = world_ctx
    g = grid_sample(h, cell, x0, y0, X, Y)
    dx = np.maximum(0.0, np.maximum(bx[0] - X, X - bx[2]))
    dy = np.maximum(0.0, np.maximum(bx[1] - Y, Y - bx[3]))
    out = np.hypot(dx, dy)
    w = np.clip(out / BLEND_M, 0.0, 1.0)
    z = g.copy()
    m = w > 0
    if m.any():
        lon, lat = tr.transform(Y[m], X[m])
        e = glo.sample(np.asarray(lat), np.asarray(lon))
        far = np.where(e > 0.3, np.maximum(e + navd, mhw + 0.25), FAR_WATER)
        z[m] = (1.0 - w[m]) * g[m] + w[m] * far
    return z


def sky_visibility(Z, step):
    """Open share of the sky over eight horizons (2 km): 1 on flat ground, less in hollows. Z is padded by P cells."""
    P = int(math.ceil(SKY_REACH_M / step))
    core = Z[P:-P, P:-P]
    vis = np.zeros_like(core)
    for a in range(8):
        ang = a * math.pi / 4
        dr, dc = math.cos(ang), math.sin(ang)
        best = np.zeros_like(core)
        for k in range(1, P + 1):
            r, c = int(round(dr * k)), int(round(dc * k))
            if r == 0 and c == 0:
                continue
            d = math.hypot(r, c) * step
            s = Z[P + r:Z.shape[0] - P + r, P + c:Z.shape[1] - P + c]
            best = np.maximum(best, (s - core) / d)
        vis += 1.0 - np.sin(np.arctan(best))
    return vis / 8.0


def bake(world):
    t0 = time.time()
    meta, cfg, tiles = ring_tiles(world)
    h, cell, x0, y0 = load_grid(world)
    ctx = (meta, h, cell, x0, y0, grid_box(meta), transformer(meta), Glo(raw_dirs(world)), meta.get("navd88_to_mllw_m") or 0.0, meta.get("mhw_m") or 0.0)
    if not ctx[7].tiles:
        sys.exit(f"No GLO-90 tiles in {RAW}: run Tools/terrain/fetch_far_dem.sh {world}")
    T = cfg["tile_km"] * 1000.0
    cells = {(i, j): n for i, j, n in tiles}
    kept = []
    for i, j, n in tiles:
        step = T / n
        P = int(math.ceil(SKY_REACH_M / step))
        k = np.arange(-P, n + 1 + P)
        X, Y = np.meshgrid(i * T + k * step, j * T + k * step, indexing="ij")
        Zp = heights(ctx, X, Y)
        Z = Zp[P:-P, P:-P].copy()
        if Z.max() < -1.0:
            continue
        # A fine tile's edge against a coarse neighbour (n / nb cells to one of its): the vertices between the coarse
        # ones on the coarse line.
        for (di, dj), edge in (((-1, 0), (0, slice(None))), ((1, 0), (-1, slice(None))), ((0, -1), (slice(None), 0)), ((0, 1), (slice(None), -1))):
            nb = cells.get((i + di, j + dj))
            if nb is not None and nb < n:
                r = n // nb
                line = Z[edge].copy()
                k = np.arange(n + 1)
                a = (k // r) * r
                b = np.minimum(a + r, n)
                t = (k - a) / r
                Z[edge] = (1.0 - t) * line[a] + t * line[b]
        sky = sky_visibility(Zp, step)
        kept.append((i, j, n, Z, np.clip(np.round(sky * 255.0), 0, 255).astype(np.uint8)))
    path = os.path.join(TERRAIN, f"{world}.far30" if ULTRA else f"{world}.far")
    unit = 0.01 if max(float(np.abs(t[3]).max()) for t in kept) < 320.0 else 0.05
    kept = [(i, j, n, np.clip(np.round(Z / unit), -32768, 32767).astype("<i2"), s) for i, j, n, Z, s in kept]
    head = struct.pack("<4sIIffff", b"SSFR", 1, len(kept), T, cfg["inner_km"] * 1000.0, cfg["outer_km"] * 1000.0, unit)
    index_size = len(kept) * 16
    off = len(head) + index_size
    index, blobs = b"", []
    for i, j, n, z, s in kept:
        index += struct.pack("<iiII", i, j, n, off)
        blob = z.tobytes() + s.tobytes()
        blobs.append(blob)
        off += len(blob)
    with open(path, "wb") as fh:
        fh.write(head + index + b"".join(blobs))
    fine = sum(1 for t in kept if t[2] == max(cells.values()))
    print(f"Far ring {world}: {len(kept)} tiles with land of {len(tiles)} ({fine} at {T / max(cells.values()):.1f} m), "
          f"heights in {unit * 100:.0f} cm, {os.path.getsize(path) / 1e6:.1f} MB, {time.time() - t0:.0f} s -> {path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--ultra" in args:
        ULTRA = True
        args.remove("--ultra")
    if args and args[0] == "--tiles":
        names = set()
        for w in args[1:] or WORLDS:
            names.update(needed_glo(w))
        print("\n".join(sorted(names)))
    else:
        for w in args or WORLDS:
            bake(w)
