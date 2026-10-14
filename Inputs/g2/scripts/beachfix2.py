"""Step 7b: a grey flat edge only counts as a hard edge (bulkhead) when pavement or buildings sit right behind it
in the cover raster; grey edges backed by grass or marsh are mud or shell flats and stay 'beach'."""
import json, numpy as np, rasterio, os, collections
from pyproj import Transformer
from common import *
for reg in active_regions():
    U = REGIONS[reg]["utm_epsg"]; t = Transformer.from_crs(4326, U, always_xy=True)
    p = f"{OUT}/{reg}/shore_armour.geojson"; d = json.load(open(p))
    cache = {}; cnt = collections.Counter()
    for f in d["features"]:
        pr = f["properties"]
        if pr.get("detection") != "flat_grey_edge":
            continue
        xs, ys = t.transform(*np.array(f["geometry"]["coordinates"]).T)
        cls = []
        for x, y in zip(xs, ys):
            name = f"{U - 26900}_{int(x // 1000):04d}_{int(y // 1000):04d}"
            if name not in cache:
                fp = f"{OUT}/{reg}/cover/{name}.tif"
                cache[name] = (rasterio.open(fp).read(1), rasterio.open(fp).transform) if os.path.exists(fp) else None
            c = cache[name]
            if c is None: continue
            a, tr = c
            col, row = int((x - tr.c) / 0.5), int((tr.f - y) / 0.5)
            cls.append(a[max(row - 8, 0):row + 9, max(col - 8, 0):col + 9].ravel())
        if not cls: continue
        c = np.concatenate(cls); c = c[(c != 0) & (c != 255)]
        hard = np.isin(c, [6, 7, 9]).mean() if len(c) else 0
        if hard < 0.3:
            pr["type"] = "beach"; pr["detection"] = "lidar_profile"; cnt["back_to_beach"] += 1
        else:
            cnt["hard_edge"] += 1
        if len(cache) > 80: cache.clear()
    json.dump(d, open(p, "w"), separators=(",", ":"))
    L = collections.defaultdict(float)
    for f in d["features"]: L[f["properties"]["type"]] += f["properties"]["length_m"]
    print(reg, dict(cnt), {k: round(v / 1000, 1) for k, v in L.items()})
