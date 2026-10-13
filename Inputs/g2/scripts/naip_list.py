import sys, numpy as np, shapefile
from shapely.geometry import shape, box
from shapely.ops import transform as stf
from common import *
r = shapefile.Reader(f"{SRC}/naipidx/naip-2022-nccir-60cm_index")
prj = open(f"{SRC}/naipidx/naip-2022-nccir-60cm_index.prj").read()
for reg in REGIONS:
    m = np.load(f"{WORK}/{reg}_mask10.npz"); band = m["band"]; C = float(m["cell"]); ntop = float(m["n_top"]); el = float(m["e_left"])
    t = tf(reg, prj, "local")
    out = []
    for sr in r.iterShapeRecords():
        g = stf(lambda x, y, z=None: t.transform(x, y), shape(sr.shape.__geo_interface__))
        e0, n0, e1, n1 = g.bounds
        c0, c1 = int((e0 - el) / C), int((e1 - el) / C) + 1
        r0, r1 = int((ntop - n1) / C), int((ntop - n0) / C) + 1
        if c1 < 0 or r1 < 0 or c0 >= band.shape[1] or r0 >= band.shape[0]:
            continue
        if band[max(r0, 0):r1, max(c0, 0):c1].any():
            out.append(sr.record[0].replace("naip22-nc-cir-60cm", "naip-2022-nccir-60cm"))
    print(reg, len(out))
    open(f"{WORK}/{reg}_naip.txt", "w").write("\n".join(out) + "\n")
