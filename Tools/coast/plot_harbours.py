"""Plots a port's harbours from its bake (heights, walkways, riprap, decks, moored boats, navaids) to check osm_harbour.py.

  Tools/venv/bin/python -I Tools/coast/plot_harbours.py Marseille docs/world-marseille/harbours.jpg
"""
import json, os, struct, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pyproj import Transformer
W = sys.argv[1]; out = sys.argv[2]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(ROOT)
m = json.load(open(f"Content/TerrainData/{W}.json")); pr = json.load(open(f"Content/TerrainData/{W}.piers"))
T = Transformer.from_crs("EPSG:4326", m["projection"], always_xy=True)
d = open(f"Content/TerrainData/{W}.height", "rb").read()
_, _, nx, ny, cell, x0, y0, u = struct.unpack("<4sIIIffff", d[:32]); H = np.frombuffer(d[32:32 + nx * ny * 2], "<i2").reshape(ny, nx) * u
views = json.load(open("Tools/coast/worlds/" + W + ".json")).get("harbour_views") or [(h["name"], h["lat"], h["lon"], 600) for h in m.get("harbours", [])][:4]
fig, axs = plt.subplots(2, 2, figsize=(14, 14))
for ax, (nm, la, lo, R) in zip(axs.ravel(), views):
    e, n = T.transform(lo, la)
    r0, r1 = int((n - R - x0) / cell), int((n + R - x0) / cell); c0, c1 = int((e - R - y0) / cell), int((e + R - y0) / cell)
    ax.imshow(np.clip(H[r0:r1, c0:c1], -8, 20), origin="lower", extent=[y0 + c0 * cell, y0 + c1 * cell, x0 + r0 * cell, x0 + r1 * cell], cmap="terrain", vmin=-12, vmax=30)
    for w in pr["walkways"]:
        p = np.array(w["pts"]); ax.plot(p[:, 1], p[:, 0], "w-", lw=1.5)
    for rr in pr["riprap"]:
        p = np.array(rr["pts"]); ax.plot(p[:, 1], p[:, 0], "-", color="0.3", lw=3)
    for dk in pr["decks"]:
        p = np.array(dk["pts"]); ax.fill(p[:, 1], p[:, 0], color="sienna")
    for b in pr["boats"]:
        h = np.radians(b[2]); ax.plot([b[1] - np.sin(h) * b[3] / 2, b[1] + np.sin(h) * b[3] / 2], [b[0] - np.cos(h) * b[3] / 2, b[0] + np.cos(h) * b[3] / 2], "-", color="red" if b[5] else "yellow", lw=1)
    for a in m["navaids"]:
        ax.plot(a["y"], a["x"], "m^", ms=6)
    ax.set_xlim(e - R, e + R); ax.set_ylim(n - R, n + R); ax.set_title(nm); ax.set_aspect("equal")
plt.tight_layout(); plt.savefig("/tmp/_harbours.png", dpi=70)
from PIL import Image
Image.open("/tmp/_harbours.png").convert("RGB").save(out, quality=80)
