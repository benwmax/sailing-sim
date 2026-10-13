"""Step 5: NAIP 2022 RGB at its native 0.6 m grid, cut to each land tile (UTM, JPEG-compressed GeoTIFF)."""
import sys, os, glob, pickle, math, numpy as np, rasterio
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from multiprocessing import Pool
from common import *
reg = sys.argv[1]; R = REGIONS[reg]
P = pickle.load(open(f"{WORK}/{reg}_prep.pkl", "rb"))
def job(p):
    info = pickle.load(open(p, "rb"))["info"]
    if not info["has_land"]:
        return None
    e0, n0 = info["e_min"], info["n_min"]
    x0 = math.floor(e0 / 0.6) * 0.6; y1 = math.ceil((n0 + 1000) / 0.6) * 0.6
    W = math.ceil((e0 + 1000 - x0) / 0.6); H = math.ceil((y1 - n0) / 0.6)
    out = np.zeros((3, H, W), np.uint8)
    for f in P["naip"]:
        b = f["bbox"]
        if b[2] < x0 or b[0] > x0 + W * 0.6 or b[3] < y1 - H * 0.6 or b[1] > y1:
            continue
        with rasterio.open(f["path"]) as s:
            # NAIP quarter quads share the global 0.6 m grid, so this is a straight pixel copy
            c0 = round((x0 - s.transform.c) / 0.6); r0 = round((s.transform.f - y1) / 0.6)
            win = rasterio.windows.Window(c0, r0, W, H)
            a = s.read([1, 2, 3], window=win, boundless=True, fill_value=0)
            ok = (a.max(0) > 0) & (out.max(0) == 0)
            out[:, ok] = a[:, ok]
    os.makedirs(f"{OUT}/{reg}/ortho", exist_ok=True)
    with rasterio.open(f"{OUT}/{reg}/ortho/{info['name']}.tif", "w", driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs=f"EPSG:{R['utm_epsg']}",
                       transform=from_origin(x0, y1, 0.6, 0.6), tiled=True, blockxsize=256, blockysize=256, compress="jpeg", photometric="ycbcr", jpeg_quality=85) as d:
        d.write(out)
        d.update_tags(SOURCE="USDA NAIP 2022, 60 cm, public domain", DATE="2022 (see README)")
    return info["name"]
with Pool(4) as p:
    n = sum(1 for r in p.imap_unordered(job, sorted(glob.glob(f"{WORK}/{reg}/tiles/*.pkl"))) if r)
print(reg, "ortho tiles", n)
