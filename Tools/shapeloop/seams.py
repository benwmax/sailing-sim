"""Shape loop: joins between sections (docs/shape-loop, rule 3: joins overlap, they don't just meet).

    python seams.py <j22_hero.blend | fbx dir> <sections.json> <out dir>

For each join on the sections file (pairs of object-name rules), samples the first part's surface every centimetre
within 2 cm of the second part and measures each sample's distance to the second part's surface, then builds the
join's gap profile: along the join's longest axis, in 5 cm bins, the closest the two parts come. Parts that touch or
overlap come within 0.5 mm in a bin (a sample under the second part's surface counts as touching); a bin whose closest approach is 0.5-20 mm is "open", a hairline gap the lower
tiers' separate simplification can widen; parts more than 2 cm apart leave the profile altogether, which the score
reads as lost contact. Sampling the surface rather than the vertices keeps the profile independent of mesh density.
Writes <out>/seams.json (per join: bins, span, open bins, open fraction, where, widest gap). The score compares
against the baseline: a join must not lose contact (fewer bins), open a larger fraction of its bins or get a wider gap.
Needs Blender's Python (pip bpy).
"""
import json
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, SECTIONS, OUT = ARGS[0], ARGS[1], ARGS[2]
os.makedirs(OUT, exist_ok=True)
SC = C.load_scene(SRC)
SEC = C.load_sections(SECTIONS)
DG = bpy.context.evaluated_depsgraph_get()
OPEN = (0.0005, 0.02)
NEAR = 0.02
BIN = 0.05
STEP = 0.01

cache = {}


def geo(prefix):
    if prefix not in cache:
        verts, tris = [], []
        for o in C.mesh_objects(SC):
            if C.matches(o.name, prefix):
                v, t = C.evaluated_mesh(o, DG)
                base = len(verts)
                verts += v
                tris += [(a + base, b + base, c + base) for a, b, c in t]
        cache[prefix] = (verts, tris)
    return cache[prefix]


out = {}
for a, b in SEC.get("joins", []):
    va, ta = geo(a)
    vb, tb = geo(b)
    if not va or not vb:
        out[f"{a}|{b}"] = {"missing": True}
        continue
    lo = [min(v[i] for v in vb) - NEAR for i in range(3)]
    hi = [max(v[i] for v in vb) + NEAR for i in range(3)]
    tree = BVHTree.FromPolygons([Vector(v) for v in vb], tb)
    # sample the first part's surface every centimetre (not its vertices), so a denser mesh of the same shape
    # samples the same places
    near = []
    for t in ta:
        pa, pb, pc = (Vector(va[i]) for i in t)
        if not any(all(lo[i] <= p[i] <= hi[i] for i in range(3)) for p in (pa, pb, pc)):
            continue
        n = max(1, min(40, int(max((pa - pb).length, (pb - pc).length, (pc - pa).length) / STEP) + 1))
        for i in range(n + 1):
            for j in range(n + 1 - i):
                v = pa + (pb - pa) * (i / n) + (pc - pa) * (j / n)
                hit = tree.find_nearest(v, NEAR)
                if hit[0] is not None:
                    # a sample under the second part's surface (the parts interpenetrate there, as a keel root in
                    # the hull or a cabin sunk into the deck) is in contact: 0, not its distance back out
                    inside = (v - hit[0]).dot(hit[1]) < -0.001      # 1 mm deep, so edges and corners don't flicker
                    near.append((tuple(v), 0.0 if inside else hit[3]))
    if not near:
        out[f"{a}|{b}"] = {"near": 0, "bins": 0, "open_bins": 0, "widest_mm": 0.0}
        continue
    # the join's gap profile: along its longest axis, in 5 cm bins, the closest the two parts come. Parts that
    # touch or overlap come within 0.5 mm somewhere in every bin; a bin whose closest approach is wider is open.
    ext = [max(p[0][i] for p in near) - min(p[0][i] for p in near) for i in range(3)]
    ax = ext.index(max(ext))
    bins = {}
    for v, d in near:
        k = int(v[ax] // BIN)
        bins[k] = min(bins.get(k, 1.0), d)
    opened = {k: d for k, d in bins.items() if OPEN[0] < d < OPEN[1]}
    out[f"{a}|{b}"] = {"near": len(near), "axis": "xyz"[ax], "bins": len(bins), "open_bins": len(opened),
                       "open_frac": round(len(opened) / len(bins), 3), "span": [round(min(bins) * BIN, 2), round((max(bins) + 1) * BIN, 2)],
                       "widest_mm": round(max(opened.values(), default=0.0) * 1000, 2),
                       "open_at": sorted(round(k * BIN, 2) for k in opened),
                       "bin_mm": {f"{k * BIN:.2f}": round(d * 1000, 2) for k, d in sorted(bins.items())}}
json.dump(out, open(os.path.join(OUT, "seams.json"), "w"), indent=1)
for k, v in out.items():
    print("shapeloop seams", k, v)
