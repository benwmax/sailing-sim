"""Water W6 LES follow-up: inputs for ntxlake.ini. The pilot's profiles and geostrophic wind (as ntxcbl_input.py), plus
the surface maps from the game's Lake Ray Hubbard height grid: a 10 x 10 km window centred on Rush Creek (the map origin),
averaged from 5 m to 25 m (north -4.7 to +5.3 km: the grid starts 4.8 km south of the club). A cell is lake where its mean height is below the 435.5 ft pool (the game's Z = 0).
  lake: sensible heat flux 0, z0m 2e-4 m, z0h 2e-5 m (open water)
  land: 250 W/m2 (0.218 K m/s), z0m 0.05 m, z0h 0.005 m
MicroHH reads them as raw doubles, x (east) fastest: z0m.0000000, z0h.0000000 and th_bot_in.<t> every 3600 s (the same
map each hour; swtimedep_sbot_2d needs one file per load time to the end and one past it).
The height grid: $SAILING_ROOT/Content/TerrainData/RayHubbard.height (default /mnt/c/dev/sailing-sim-w6)."""
import os
import struct

import numpy as np

exec(open("ntxcbl_input.py").read().replace("ntxcbl.ini", "ntxlake.ini").replace("ntxcbl_input.nc", "ntxlake_input.nc"))

N, L, SRC_CELL = 400, 10000.0, 5.0
root = os.environ.get("SAILING_ROOT", "/mnt/c/dev/sailing-sim-w6")
with open(os.path.join(root, "Content", "TerrainData", "RayHubbard.height"), "rb") as f:
    data = f.read()
_, nx, ny = struct.unpack_from("<3I", data, 4)
cell, ox, oy, unit = struct.unpack_from("<4f", data, 16)
h = np.frombuffer(data, dtype="<i2", count=nx * ny, offset=32).reshape(ny, nx).astype(np.float32) * unit
k = int(round(L / N / cell))                     # 5 m cells per 25 m cell
r0 = int(round((-4700.0 - ox) / cell))          # window: north -4.7 .. +5.3 km (the grid starts 4.8 km south), east -5 .. +5 km
c0 = int(round((-L / 2 - oy) / cell))
win = h[r0:r0 + N * k, c0:c0 + N * k].reshape(N, k, N, k).mean(axis=(1, 3))   # [north j][east i]
lake = win < 0.0
flux = np.where(lake, 0.0, 0.218)
z0m = np.where(lake, 2e-4, 0.05)
z0h = np.where(lake, 2e-5, 0.005)
for name, arr in (("z0m.0000000", z0m), ("z0h.0000000", z0h)):
    arr.astype("<f8").tofile(name)
for t in range(0, 10800 + 2 * 3600, 3600):
    flux.astype("<f8").tofile(f"th_bot_in.{t:07d}")
np.save("lake_mask.npy", lake)
print(f"surface maps: lake {lake.mean() * 100:.0f}% of the tile; domain-mean heat flux {flux.mean() * 1.14 * 1004:.0f} W/m2")
