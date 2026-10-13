"""Step 7: re-check 'beach' shore runs against the native ortho. A flat, bright edge that is grey (concrete
boardwalk, seawall cap, marina edge) is a hard edge, not sand: relabel it 'bulkhead' with detection='flat_grey_edge'."""
import sys, json, numpy as np, rasterio, os, collections
from pyproj import Transformer
from common import *
for reg in REGIONS:
    U = REGIONS[reg]["utm_epsg"]; t = Transformer.from_crs(4326, U, always_xy=True)
    p = f"{OUT}/{reg}/shore_armour.geojson"; d = json.load(open(p))
    cache = {}
    cnt = collections.Counter()
    for f in d["features"]:
        pr = f["properties"]; pr.setdefault("detection", "lidar_profile")
        if pr["type"] != "beach":
            continue
        xs, ys = t.transform(*np.array(f["geometry"]["coordinates"]).T)
        pix = []
        for x, y in zip(xs, ys):
            name = f"{U - 26900}_{int(x // 1000):04d}_{int(y // 1000):04d}"
            if name not in cache:
                fp = f"{OUT}/{reg}/ortho/{name}.tif"
                cache[name] = (rasterio.open(fp).read(), rasterio.open(fp).transform) if os.path.exists(fp) else None
            c = cache[name]
            if c is None:
                continue
            a, tr = c
            col, row = int((x - tr.c) / 0.6), int((tr.f - y) / 0.6)
            w = a[:, max(row - 4, 0):row + 5, max(col - 4, 0):col + 5].reshape(3, -1).T.astype(int)
            if len(w):
                pix.append(w)
        if not pix:
            continue
        px_ = np.concatenate(pix)
        br = px_.mean(1); land = px_[br >= np.median(br)]
        r, g, b = np.median(land, axis=0)
        if abs(r - b) < 20 and abs(r - g) < 20:
            pr["type"] = "bulkhead"; pr["detection"] = "flat_grey_edge"; cnt["to_bulkhead"] += 1
        else:
            cnt["kept_beach"] += 1
        if len(cache) > 60:
            cache.clear()
    json.dump(d, open(p, "w"), separators=(",", ":"))
    L = collections.defaultdict(float)
    for f in d["features"]: L[f["properties"]["type"]] += f["properties"]["length_m"]
    print(reg, dict(cnt), {k: round(v / 1000, 1) for k, v in L.items()})
