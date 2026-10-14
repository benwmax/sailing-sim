"""Quick-look mosaics of cover (8 m/px) per region."""
import sys, glob, numpy as np, rasterio
from rasterio.enums import Resampling
from PIL import Image
from common import *
pal = {0: (40, 80, 160), 1: (120, 190, 80), 2: (90, 130, 60), 3: (150, 115, 80), 4: (230, 210, 150), 5: (255, 128, 0), 6: (220, 220, 220), 7: (70, 70, 70), 8: (30, 90, 40), 9: (200, 60, 60)}
for reg in active_regions():
    fs = sorted(glob.glob(f"{OUT}/{reg}/cover/*.tif"))
    es = [int(f.split("_")[-2]) for f in fs]; ns = [int(f.split("_")[-1][:-4]) for f in fs]
    f = 8; px = 1000 // f
    W, H = (max(es) - min(es) + 1) * px, (max(ns) - min(ns) + 1) * px
    img = np.zeros((H, W, 3), np.uint8)
    for p, e, n in zip(fs, es, ns):
        with rasterio.open(p) as s:
            a = s.read(1, out_shape=(px, px), resampling=Resampling.mode)
        rgb = np.zeros((px, px, 3), np.uint8)
        for k, v in pal.items(): rgb[a == k] = v
        y = (max(ns) - n) * px; x = (e - min(es)) * px
        img[y:y + px, x:x + px] = rgb
    import os; os.makedirs(f"{OUT}/previews", exist_ok=True)
    Image.fromarray(img).save(f"{OUT}/previews/{reg}_cover_8m.png", optimize=True); print(reg, img.shape)
