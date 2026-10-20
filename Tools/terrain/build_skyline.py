"""Wide World Rendering PR 4, band D (docs/world-haze): the mountains beyond the far ring as a 500 m height grid.

  Tools/venv/bin/python -I Tools/terrain/build_skyline.py [World ...]   (default Marseille)

Past the far coast ring (45 km) only silhouettes matter: Mont Ventoux (1,909 m, 97 km north of the Vieux-Port), the
Luberon, the Montagne de Lure and the Alps' foothills, the Maures. The game marches this grid from the camera every
500 m on a worker (Sailing::FSkyline) for the highest elevation angle per azimuth, and the sky dome draws the land under
it, faded by the haze. Source: the Copernicus DEM GLO-90 tiles in Data/Far/raw or Data/<World>/raw/far (a missing tile
is all sea), averaged to 500 m (block means, so a peak's 500 m cell keeps its mean height; the silhouette's error at
100 km is under 0.02 degrees).

Output: Content/TerrainData/<World>.skyline (little endian): "SSKL", uint32 version 1, uint32 nx (east), ny (north),
float cell (m), origin north, origin east (map frame of the world's bake), then ny x nx int16 heights (m; sea 0).
"""
import glob
import json
import math
import os
import struct
import sys

import numpy as np
from pyproj import Transformer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "Tools", "coast"))
import geotiff  # noqa: E402

CELL = 500.0
RADIUS = {"Marseille": 160000.0}


def build(world):
    meta = json.load(open(os.path.join(ROOT, "Content", "TerrainData", f"{world}.json")))
    to_ll = Transformer.from_crs(meta["projection"], "EPSG:4326", always_xy=True)
    r = RADIUS.get(world, 150000.0)
    n = int(round(2 * r / CELL)) + 1
    north = -r + np.arange(n) * CELL
    east = -r + np.arange(n) * CELL
    # Block means: sample a 5 x 5 sub-grid in each 500 m cell (every 100 m, about the DEM's own 90 m).
    sub = (np.arange(5) - 2) * (CELL / 5.0)
    heights = np.zeros((n, n))
    weight = np.zeros((n, n))
    tiles = sorted(set(glob.glob(os.path.join(ROOT, "Data", "Far", "raw", "glo90_*.tif"))) | set(glob.glob(os.path.join(ROOT, "Data", world, "raw", "far", "glo90_*.tif"))))
    for path in tiles:
        d, ref = geotiff.read(path)
        lat_hi, lon_lo = ref.y0, ref.x0
        lat_lo, lon_hi = ref.y0 + ref.dy * (d.shape[0] - 1), ref.x0 + ref.dx * (d.shape[1] - 1)
        for dn in sub:
            for de in sub:
                N, E = np.meshgrid(north + dn, east + de, indexing="ij")
                lon, lat = to_ll.transform(E, N)
                inside = (lat >= lat_lo) & (lat <= lat_hi) & (lon >= lon_lo) & (lon <= lon_hi)
                if not inside.any():
                    continue
                v = geotiff.sample(d, ref, lon[inside], lat[inside], fill=np.nan)
                ok = np.isfinite(v)
                idx = np.nonzero(inside)
                heights[idx[0][ok], idx[1][ok]] += np.maximum(v[ok], 0.0)
                weight[idx[0][ok], idx[1][ok]] += 1.0
        print(f"  {os.path.basename(path)}")
    h = np.where(weight > 0, heights / np.maximum(weight, 1), 0.0)
    out = os.path.join(ROOT, "Content", "TerrainData", f"{world}.skyline")
    with open(out, "wb") as fh:
        fh.write(b"SSKL" + struct.pack("<III", 1, n, n) + struct.pack("<fff", CELL, float(north[0]), float(east[0])))
        fh.write(np.round(h).astype("<i2").tobytes())
    i = np.unravel_index(np.argmax(h), h.shape)
    print(f"{world}: skyline grid {n} x {n} of {CELL:.0f} m, {len(tiles)} tiles, highest {h.max():.0f} m at "
          f"{north[i[0]] / 1000:.0f} km N, {east[i[1]] / 1000:.0f} km E; {os.path.getsize(out) / 1e6:.1f} MB -> {out}")


if __name__ == "__main__":
    for w in sys.argv[1:] or ["Marseille"]:
        build(w)
