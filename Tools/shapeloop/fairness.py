"""Shape loop, check 3: fairness of the hull (docs/shape-loop).

    python fairness.py <j22_hero.blend | fbx dir> <out dir> [--object Hull]

Cuts the hull's outer skin with 10 waterline planes (z) and 10 station planes (x), orders each cut into a polyline and
measures its curvature (turning angle per metre). A fair line bends one way, smoothly: the report counts
  inflections  sign changes of the curvature smoothed over 30 cm (bends under 0.15 rad/m ignored): a ripple shows
               as extra pairs
  kinks        peaks and dips of the 10 cm chord curvature that stand out by more than 0.5 rad/m (their
               prominence; kinks_firm: 0.7): a bump, a flat or a crease adds a peak and a dip, while a bend made
               tighter or gentler on purpose keeps one peak; 15 cm at each end of a line (stem, transom corner) is
               left out
Both are measured on 2 cm resampled cuts, so a denser mesh of the same shape gives the same counts.
It writes the counts per line to <out>/fairness.json, with where each one is (inflections_at, kinks_at: the point in
the cut's plane). The check compares against the baseline: a round must not add inflections or kinks to any line (a
line the drawing bends both ways, such as a reverse sheer, keeps its own count).
Needs Blender's Python (pip bpy), numpy and scipy.
"""
import json
import math
import os
import sys

import bpy  # noqa: F401  (pip bpy: bpy must load before bmesh)
import bmesh
import numpy as np
from scipy.signal import find_peaks

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


def port_run(p, off_transom=False):
    """The longest contiguous run of a cut on the port side (y >= 0), so a closed loop isn't cut into a jump. With
    off_transom, points on the transom face (within 5 mm of the cut's aftmost x) are left out too: whether a cut runs
    on across the transom depends on how the transom face is triangulated, not on the shape."""
    side = p[:, 1] >= 0
    if off_transom:
        side &= p[:, 0] > p[:, 0].min() + 0.005
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
    at = q[w:-w]                                    # where each k is, in the cut's plane
    # inflections: sign changes of the curvature smoothed over 30 cm, ignoring bends under 0.15 rad/m (a 6.7 m radius).
    # Both counts are measured on the surface, not the mesh: a denser mesh of the same shape gives the same counts
    # (docs/shape-loop, density test).
    def smooth(v, m):
        m = max(1, min(m, len(v) // 2 * 2 - 1))
        return np.convolve(np.pad(v, m // 2, mode="edge"), np.ones(m) / m, mode="valid")[:len(v)]

    # the line's ends (the stem, the transom corner, the keel root) are corners by design: leave 15 cm off each end
    e = min(len(k) // 4, 7)
    k = k[e:len(k) - e] if e else k
    at = at[e:len(at) - e] if e else at
    ks = smooth(k, 15)
    floor = 0.15
    sig = np.sign(np.where(np.abs(ks) > floor, ks, 0))
    nz = sig[sig != 0]
    infl = int(np.sum(nz[1:] != nz[:-1])) if len(nz) > 1 else 0
    # kinks: extra wiggles in the curvature. A fair line's curvature rises and falls smoothly, with one peak per bend
    # (the bilge, the turn at the stem); a bump, a flat or a crease adds a peak and a dip next to it. Count the peaks
    # and dips of the 10 cm curvature that stand out by more than 0.5 rad/m (their prominence), so a bend made
    # tighter or gentler on purpose keeps its count and a ripple of a few millimetres over 20 cm does not.
    peaks = sorted(set(find_peaks(k, prominence=0.5)[0]) | set(find_peaks(-k, prominence=0.5)[0]))
    firm_at = set(find_peaks(k, prominence=0.7)[0]) | set(find_peaks(-k, prominence=0.7)[0])   # score.py's hysteresis
    kinks, firm = len(peaks), len(firm_at)
    med = float(np.median(np.abs(np.diff(k)))) if len(k) > 1 else 0.0
    # where they are, in the cut's plane (x, y for a waterline; y, z for a station), so a report can say which turn
    # each one is: an inflection at the first point of the new sign, a kink with its curvature and firm or soft
    idx = np.where(sig != 0)[0]
    infl_at = [[round(float(c), 2) for c in at[idx[j + 1]]] for j in np.where(nz[1:] != nz[:-1])[0]]
    kink_at = [[round(float(at[i][0]), 2), round(float(at[i][1]), 2), round(float(k[i]), 2),
                "firm" if i in firm_at else "soft"] for i in peaks]
    return {"length_m": round(float(s[-1]), 3), "inflections": infl, "kinks": kinks, "kinks_firm": firm,
            "k_max": round(float(np.max(np.abs(k))), 3), "k_step_median": round(med, 4),
            "inflections_at": infl_at, "kinks_at": kink_at}


lo = [min((OB.matrix_world @ v.co)[i] for v in OB.data.vertices) for i in range(3)]
hi = [max((OB.matrix_world @ v.co)[i] for v in OB.data.vertices) for i in range(3)]
lines = {}
for i in range(10):
    z = lo[2] + (hi[2] - lo[2]) * (0.08 + 0.84 * i / 9)
    p = cut((0, 0, 1), (0, 0, z))
    if p is not None:
        f = fairness(port_run(p, off_transom=True), [0, 1])
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
