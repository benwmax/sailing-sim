"""Quick-look PNG of the Gulf front: NAIP ortho at 8 m with the Seawall (red), jetties (orange), piers (magenta),
groins (yellow) and beach profiles (cyan). Usage: preview.py <out.png> [W lon] [E lon]"""
import sys, os, json, glob, numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "piers"))
from geo import ll2utm
from stage1 import G2
D = f"{G2}/GalvestonGulf"; DEST = os.environ.get("GULF_DEST", f"{G2}/GalvestonBay/gulf-front")
w = float(sys.argv[2]) if len(sys.argv) > 2 else -95.0; e = float(sys.argv[3]) if len(sys.argv) > 3 else -94.76
S = 8.0 if len(sys.argv) <= 2 else 1.5
E0, N0 = ll2utm(w, 29.20); E1, N1 = ll2utm(e, 29.31)
E0, N0, E1, N1 = int(E0), int(N0), int(E1), int(N1)
img = Image.new("RGB", (int((E1 - E0) / S), int((N1 - N0) / S)), (20, 30, 45))
for f in glob.glob(f"{D}/ortho/*.tif"):
    im = Image.open(f); ext = im.tag_v2.get(33922); sc = im.tag_v2.get(33550)[0]
    x0, y1 = ext[3], ext[4]; x1, y0 = x0 + im.width * sc, y1 - im.height * sc
    if x1 < E0 or x0 > E1 or y1 < N0 or y0 > N1: continue
    sm = im.convert("RGB").resize((max(1, int(im.width * sc / S)), max(1, int(im.height * sc / S))))
    img.paste(sm, (int((x0 - E0) / S), int((N1 - y1) / S)))
d = ImageDraw.Draw(img)
def xy(c):
    c = np.array(c); E, N = ll2utm(c[:, 0], c[:, 1]); return [((a - E0) / S, (N1 - b) / S) for a, b in zip(E, N)]
for f in json.load(open(f"{DEST}/beach_profiles.geojson"))["features"]: d.line(xy(f["geometry"]["coordinates"]), fill=(0, 230, 255), width=1)
for f in json.load(open(f"{DEST}/groins.geojson"))["features"]:
    g = f["geometry"]; d.line(xy(g["coordinates"] if g["type"] == "LineString" else g["coordinates"][0]), fill=(255, 230, 0), width=3)
for f in json.load(open(f"{DEST}/gulf_piers.geojson"))["features"]:
    g = f["geometry"]; d.polygon(xy(g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]), outline=(255, 0, 255))
for f in json.load(open(f"{DEST}/landmarks.geojson"))["features"]:
    g = f["geometry"]
    if g["type"] == "LineString": d.line(xy(g["coordinates"]), fill=(255, 40, 40) if f["properties"]["kind"] == "seawall" else (255, 150, 0), width=3)
img.save(sys.argv[1], optimize=True); print(img.size)
