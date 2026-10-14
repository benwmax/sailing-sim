"""Copy the GalvestonGulf region's G2 layers into the Gulf-front pack, keeping only what lies south of the bay grid
(sim_north < -27600, i.e. south of 29.295 N): the seam tiles exist in both regions and the bay copy wins north of it.
Vectors are clipped by their centroid; raster tiles are copied whole (tiles.json lists them).
Usage: package.py           (reads <G2>/GalvestonGulf, writes <GULF_DEST>/shore and <GULF_DEST>/piers)"""
import sys, os, json, shutil, glob, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "piers"))
from geo import ll2local
from stage1 import G2
D = f"{G2}/GalvestonGulf"; DEST = os.environ.get("GULF_DEST", f"{G2}/GalvestonBay/gulf-front")
BAY_SOUTH = -27600.0

def centre(g):
    t = g["type"]; c = g["coordinates"]
    pts = [c] if t == "Point" else c if t == "LineString" else c[0] if t == "Polygon" else c[0][0]
    a = np.array(pts, float).reshape(-1, 2); return a[:, 0].mean(), a[:, 1].mean()

def clip(src, dst):
    d = json.load(open(src)); n0 = len(d["features"])
    d["features"] = [f for f in d["features"] if ll2local(*centre(f["geometry"]))[1] < BAY_SOUTH]
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(d, open(dst, "w"), separators=(",", ":")); print(os.path.basename(dst), n0, "->", len(d["features"]))

for k in ("buildings", "trees", "shore_armour"):
    clip(f"{D}/{k}.geojson", f"{DEST}/shore/{k}.geojson")
shutil.copy(f"{D}/tiles.json", f"{DEST}/shore/tiles.json")
for k in ("overwater_structures", "narrow_structures", "narrow_structures_centrelines", "moored_boats_2018", "marinas", "seawall"):
    if os.path.exists(f"{D}/piers/{k}.geojson"): clip(f"{D}/piers/{k}.geojson", f"{DEST}/piers/{k}.geojson")
if "--rasters" in sys.argv:
    for k in ("dem", "dsm", "cover", "ortho"):
        os.makedirs(f"{DEST}/shore/{k}", exist_ok=True)
        fs = sorted(glob.glob(f"{D}/{k}/*.tif"))
        for f in fs: shutil.copy(f, f"{DEST}/shore/{k}/")
        print(k, len(fs), "tiles")
