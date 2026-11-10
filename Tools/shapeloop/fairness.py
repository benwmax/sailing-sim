"""Shape loop, check 3: fairness of the hull (docs/shape-loop).

    python fairness.py <j22_hero.blend | fbx dir> <out dir> [--object Hull]

Cuts the hull's outer skin with 10 waterline planes (z) and 10 station planes (x), orders each cut into a polyline and
measures its curvature (turning angle per metre). A fair line bends one way, smoothly: the report counts
  inflections  sign changes of curvature (ignoring bends under the noise floor), a ripple shows as extra pairs
  kinks        samples whose curvature (over a 10 cm chord) jumps more than 4x the line's median step and 0.5 rad/m:
               a facet, crease or bump
per line, and writes <out>/fairness.json. The check compares against the baseline: a round must not add inflections
or kinks to any line (a line the drawing bends both ways, such as a reverse sheer, keeps its own count).
Needs Blender's Python (pip bpy) and numpy.
"""
import json
import math
import os
import sys

import bpy  # noqa: F401  (pip bpy: bpy must load before bmesh)
import bmesh
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
NAME = ARGS[ARGS.index("--object") + 1] if "--object" in ARGS else "Hull"
os.makedirs(OUT, exist_ok=True)
C.load_scene(SRC)
DG = bpy.context.evaluated_depsgraph_get()
OB = bpy.data.objects[NAME]


def cut(no, co):
    """Edges of the plane cut through the hull, chained into polylines; the outer skin's chain is the longest one."""
    bm = bmesh.new()
    bm.from_object(OB, DG)
    bm.transform(OB.matrix_world)
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
    edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a.index, []).append(b.index)
        adj.setdefault(b.index, []).append(a.index)
    pos = {v.index: tuple(v.co) for e in edges for v in e.verts}
    bm.free()
    seen, chains = set(), []
    for start in sorted(adj, key=lambda k: len(adj[k])):     # open ends first
        if start in seen:
            continue
        chain, cur, prev = [start], start, None
        seen.add(start)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            chain.append(cur)
        chains.append([pos[i] for i in chain])
    if not chains:
        return None
    best = max(chains, key=lambda c: sum(math.dist(a, b) for a, b in zip(c, c[1:])) * (1 + 0.001 * max(abs(p[1]) for p in c)))
    return np.array(best)


def port_run(p):
    """The longest contiguous run of a cut on the port side (y >= 0), so a closed loop isn't cut into a jump."""
    side = p[:, 1] >= 0
    if side.all() or not side.any():
        return p
    start = int(np.argmin(side))                    # roll so the run doesn't wrap past the array's end
    p, side = np.roll(p, -start, axis=0), np.roll(side, -start)
    best, cur = (0, 0), None
    for i, s in enumerate(list(side) + [False]):
        if s and cur is None:
            cur = i
        elif not s and cur is not None:
            if i - cur > best[1] - best[0]:
                best = (cur, i)
            cur = None
    return p[best[0]:best[1]]


def fairness(p, axes):
    """Signed curvature along a polyline in the plane of `axes` (two coordinate indices)."""
    q = p[:, axes]
    # drop near-duplicates, resample to even spacing so the mesh's own spacing doesn't read as bumps
    seg = np.linalg.norm(np.diff(q, axis=0), axis=1)
    keep = np.concatenate([[True], seg > 1e-5])
    q = q[keep]
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))])
    if len(q) < 8 or s[-1] < 0.2:
        return None
    n = max(int(s[-1] / 0.02), 16)                 # one sample every 2 cm
    t = np.linspace(0, s[-1], n)
    q = np.stack([np.interp(t, s, q[:, 0]), np.interp(t, s, q[:, 1])], axis=1)
    # turning over a 10 cm chord either side: a cut through a faceted mesh turns at every edge it crosses, which a
    # point-to-point curvature reads as noise; the chord curvature sees the surface's own bends and real bumps
    w = 5
    a = q[w:-w] - q[:-2 * w]
    b = q[2 * w:] - q[w:-w]
    ang = np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(axis=1))
    k = ang / (w * s[-1] / (n - 1))                 # rad per metre
    floor = max(0.05, 0.05 * np.max(np.abs(k)))
    sig = np.sign(np.where(np.abs(k) > floor, k, 0))
    nz = sig[sig != 0]
    infl = int(np.sum(nz[1:] != nz[:-1])) if len(nz) > 1 else 0
    dk = np.abs(np.diff(k))
    med = float(np.median(dk)) + 1e-6
    kinks = int(np.sum(dk > max(4 * med, 0.5)))
    return {"length_m": round(float(s[-1]), 3), "inflections": infl, "kinks": kinks,
            "k_max": round(float(np.max(np.abs(k))), 3), "k_step_median": round(med, 4)}


lo = [min((OB.matrix_world @ v.co)[i] for v in OB.data.vertices) for i in range(3)]
hi = [max((OB.matrix_world @ v.co)[i] for v in OB.data.vertices) for i in range(3)]
lines = {}
for i in range(10):
    z = lo[2] + (hi[2] - lo[2]) * (0.08 + 0.84 * i / 9)
    p = cut((0, 0, 1), (0, 0, z))
    if p is not None:
        f = fairness(port_run(p), [0, 1])
        if f:
            lines[f"wl_{i}"] = dict(z=round(z, 3), **f)
for i in range(10):
    x = lo[0] + (hi[0] - lo[0]) * (0.06 + 0.88 * i / 9)
    p = cut((1, 0, 0), (x, 0, 0))
    if p is not None:
        f = fairness(port_run(p), [1, 2])
        if f:
            lines[f"st_{i}"] = dict(x=round(x, 3), **f)
out = {"object": NAME, "lines": lines,
       "total_inflections": sum(v["inflections"] for v in lines.values()), "total_kinks": sum(v["kinks"] for v in lines.values())}
json.dump(out, open(os.path.join(OUT, "fairness.json"), "w"), indent=1)
print(f"shapeloop fairness {NAME}: {len(lines)} lines, inflections {out['total_inflections']}, kinks {out['total_kinks']}")
