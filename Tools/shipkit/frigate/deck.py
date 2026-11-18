"""The frigate's spar deck (docs/shipkit-7): the planked quarterdeck, gangways and forecastle round the open waist, and
what stands on them: the waterways, the waist's coamings and beams, the breast rails and ladders at the breaks, the
hatchways with their gratings, the companion, the skylights, the capstan's head, the double wheel and its binnacle, the
belfry, the galley's chimney, the bowsprit's step, the mast coats and the hammock nettings.

    from deck import Deck;  dk = Deck(sk, rig).build();  dk.parts();  dk.nettings(obstacles)

Sizes and places are deck_1797.json's, each with its source: the 1849 spar deck plan (registered to our masts), the 1817
draught, or the period's practice. Units: metres in the ship frame (X forward, Y starboard, Z up, origin on the
centreline at midships on waterline A).

The deck is flat across, its top at the bulwark's foot (skin.py's w_Pd row) and its underside its planks' 3 in below
(g_Pu; slice 12's gundeck.py frames the beams under them), as slices 2 to 6 laid it. Its top is one surface cut round the open waist, the masts, the hatchways,
companion, skylights, chimney and the capstan's barrel (Blender's constrained Delaunay triangulation, so this module
runs in Blender's Python), with a UV map 'Planking' (u, v = x, y in metres) from which the material draws the planks,
their seams, butts and plugs (planking_terms; build_frigate.py's DeckPlanks). Where a hole's coaming stands, the hole is
the coaming's outside and the coaming runs down to the underside; the masts' and the capstan's holes have walls.

The capstan and the wheel each have a frame of their own (origin on the axis they turn about, see parts()); everything
else is built in place. The hammock nettings come last (nettings()), after the running rigging is rove: each runs along
its rail cap and narrows, or breaks, wherever a rope, block or fitting comes over the rail (the obstacles it is given).
"""
import collections
import json
import math
import os

import numpy as np

import loft
from rigging import fillet, tube, rope_r
from spars import box, circle, loft_solid, spar, ring_band, clip_convex, unit

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)
CLOTH_OVER = 0.6 * IN          # the hammock cloth hangs down outside each side of a netting by this much


# ---- mesh pieces -------------------------------------------------------------------------------------------------------
class Part:
    """Vertices (metres), faces, a material per face and two UVs per vertex (four columns, zero where unused: the deck's
    'Planking' and 'Margin', the nettings' 'Netting'). Its add() takes spars.py's and rigging.py's mesh calls."""

    def __init__(self):
        self.V, self.F, self.M, self.U = [], [], [], []
        self.n = 0

    def add(self, V, F, mat, uv=None):
        V = np.array(V, float).reshape(-1, 3)                  # a copy: seat() and drape() move it in place
        self.V.append(V)
        self.F += [tuple(self.n + int(i) for i in f) for f in F]
        if isinstance(mat, (list, tuple)):                      # a material per face (head.slab gives its walls theirs)
            if len(mat) != len(F):
                raise SystemExit(f"deck: Part.add given {len(mat)} materials for {len(F)} faces")
            self.M += list(mat)
        else:
            self.M += [mat] * len(F)
        U = np.zeros((len(V), 4))
        if uv is not None:
            uv = np.asarray(uv, float).reshape(len(V), -1)
            U[:, :uv.shape[1]] = uv
        self.U.append(U)
        self.n += len(V)

    def extend(self, other):
        """append another Part's vertices, faces, materials and UVs"""
        self.V += other.V
        self.U += other.U
        self.F += [tuple(self.n + i for i in f) for f in other.F]
        self.M += other.M
        self.n += other.n

    def arrays(self):
        if not self.V:
            return np.zeros((0, 3)), [], [], np.zeros((0, 4))
        return np.concatenate(self.V), list(self.F), list(self.M), np.concatenate(self.U)

    def tris(self):
        return sum(len(f) - 2 for f in self.F)


def newell(P):
    """A polygon's area normal (Newell's method)."""
    P = np.asarray(P, float)
    Q = np.roll(P, -1, axis=0)
    return np.array([np.sum((P[:, 1] - Q[:, 1]) * (P[:, 2] + Q[:, 2])),
                     np.sum((P[:, 2] - Q[:, 2]) * (P[:, 0] + Q[:, 0])),
                     np.sum((P[:, 0] - Q[:, 0]) * (P[:, 1] + Q[:, 1]))])


def convex(P):
    """whether a flat ring of points (n, 3) is convex"""
    E = np.roll(P, -1, axis=0) - P
    c = np.cross(E, np.roll(E, -1, axis=0)) @ newell(P)
    return bool(np.all(c >= -1e-9 * np.abs(c).max()))


def solid(mesh, rings, mat, cap0=True, cap1=True):
    """spars.loft_solid through rings (the same count each), each ring's points turned counter-clockwise about the
    direction from the first ring to the last, so every face points out. Each end is one face where its ring is convex,
    not a fan round a point in its middle: an end that stands flush in an opening (a coaming's end in the deck's) has no
    vertex inside what it stands in, for the room check to read as buried. A ring that is not convex (a waterway's
    cove) is filled with triangles inside its outline (end_fill); a fan from its middle would cross its own sides"""
    rings = [np.asarray(r, float) for r in rings]
    d = rings[-1].mean(0) - rings[0].mean(0)
    if newell(rings[0]) @ d < 0:
        rings = [r[::-1] for r in rings]
    n = len(rings[0])
    caps = {}
    for k, ring, want in ((0, rings[0], -1.0), (len(rings) - 1, rings[-1], 1.0)):
        if (k == 0 and not cap0) or (k > 0 and not cap1):
            continue
        if convex(ring):
            caps[k] = [tuple(range(n)) if want > 0 else tuple(range(n - 1, -1, -1))]
        else:
            caps[k] = end_fill(ring, want * newell(ring))
            if caps[k] is None:                        # (a ring the fill cannot take: the fan round its middle)
                loft_solid(mesh, rings, mat, cap0, cap1)
                return
    F = [(j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
         for j in range(len(rings) - 1) for i in range(n)]
    for k, faces in caps.items():
        F += [tuple(k * n + i for i in f) for f in faces]
    mesh.add(np.concatenate(rings), F, mat)


def end_fill(ring, want):
    """triangles (indices into ring) filling a flat ring that need not be convex, each facing want; None if the fill
    does not cover the ring's area (a ring that crosses itself or repeats a point)"""
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    tris = tessellate_polygon([[Vector(tuple(map(float, p))) for p in ring]])
    out, area = [], 0.0
    for a, b, c in tris:
        nrm = np.cross(ring[b] - ring[a], ring[c] - ring[a])
        area += 0.5 * float(np.linalg.norm(nrm))
        out.append((a, b, c) if nrm @ want >= 0 else (a, c, b))
    whole = 0.5 * float(np.linalg.norm(newell(ring)))
    if len(out) != len(ring) - 2 or abs(area - whole) > 1e-2 * whole + 1e-9:
        return None
    return out


def chevron(mesh, ring0, ring1, mat):
    """A closed roof: a section of six points (eave, ridge, eave along the underside, then back along the top: points 1
    and 4 are the ridge's) from ring0 to ring1, each end closed by two quads either side of the ridge, so the two slopes
    are one solid (no face between them) and every face points out."""
    r0, r1 = np.asarray(ring0, float), np.asarray(ring1, float)
    if newell(r0) @ (r1.mean(0) - r0.mean(0)) < 0:              # counter-clockwise seen from ring1 (the ridge stays 1, 4)
        r0, r1 = r0[::-1], r1[::-1]
    V = np.concatenate([r0, r1])
    F = [(i, (i + 1) % 6, 6 + (i + 1) % 6, 6 + i) for i in range(6)]
    F += [(6, 7, 10, 11), (7, 8, 9, 10), (5, 4, 1, 0), (4, 3, 2, 1)]
    mesh.add(V, F, mat)


def vbox(mesh, lo, hi, mat):
    """An axis-aligned box between corners lo and hi."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    c, h = 0.5 * (lo + hi), 0.5 * (hi - lo)
    box(mesh, c, EX, EY, EZ, h[0], h[1], h[2], mat)


def bar(mesh, a, b, w, t, mat, up=EZ):
    """A square-sectioned bar from a to b: w wide (across, square to up), t deep (along up's part square to it)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = unit(b - a)
    s = np.cross(d, up)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(d, EX)
    s = unit(s)
    v = np.cross(s, d)
    ring = lambda p: np.array([p - s * w / 2 - v * t / 2, p + s * w / 2 - v * t / 2, p + s * w / 2 + v * t / 2,  # noqa
                               p - s * w / 2 + v * t / 2])
    solid(mesh, [ring(a), ring(b)], mat)


def strut(mesh, a, b, w, t, mat, up=EZ):
    """bar() with its foot (at a) cut level instead of square, so a raking strut stands flat on what is under it"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = unit(b - a)
    s = np.cross(d, up)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(d, EX)
    s = unit(s)
    v = np.cross(s, d)
    ring = lambda p: np.array([p - s * w / 2 - v * t / 2, p + s * w / 2 - v * t / 2, p + s * w / 2 + v * t / 2,  # noqa
                               p - s * w / 2 + v * t / 2])
    r0 = ring(a)
    r0 = r0 + d[None] * ((a[2] - r0[:, 2]) / d[2])[:, None]
    solid(mesh, [r0, ring(b)], mat)


def strip(mesh, A, B, mat, want):
    """Quads between two polylines of the same count, turned so their mean normal points along want."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    n = len(A)
    V = np.concatenate([A, B])
    F = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    nrm = sum(np.cross(V[f[1]] - V[f[0]], V[f[3]] - V[f[0]]) for f in F)
    if nrm @ np.asarray(want, float) < 0:
        F = [f[::-1] for f in F]
    mesh.add(V, F, mat)


def lathe(mesh, o, axis, ref, profile, mat, n=16):
    """A solid of revolution about axis through o: profile [(h, r)] from one end to the other (spars.spar's stations;
    the ends are capped flat)."""
    spar(mesh, np.asarray(o, float), unit(np.asarray(axis, float)), unit(np.asarray(ref, float)),
         [(h, max(r, 1e-4)) for h, r in profile], mat, n)


def revolve(mesh, o, axis, ref, profile, mat, n=16, want_out=True):
    """an open surface of revolution about axis through o: profile [(h, r)] (r > 0), its faces turned away from the
    axis (want_out) or toward it"""
    o = np.asarray(o, float)
    axis, ref = unit(np.asarray(axis, float)), unit(np.asarray(ref, float))
    b = np.cross(axis, ref)
    th = np.arange(n) * 2 * math.pi / n
    rings = [o + h * axis + r * (np.cos(th)[:, None] * ref + np.sin(th)[:, None] * b)
             for h, r in profile]
    V = np.concatenate(rings)
    F = [(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i)
         for k in range(len(rings) - 1) for i in range(n)]
    f0 = F[0]
    nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
    radial = V[f0[0]] - (o + ((V[f0[0]] - o) @ axis) * axis)
    if (nrm @ radial < 0) == want_out:
        F = [f[::-1] for f in F]
    mesh.add(V, F, mat)


def cell_solid(mesh, us, vs, depth, P, N, mat):
    """A solid over a grid of cells (a grating, a sash): us, vs the cells' edges; depth[i][j] how deep cell (i, j)'s
    column runs below the top (0: an opening); P(u, v) the top's point, N(u, v) its outward normal. Faces: each column's
    top and bottom, and a side wherever two neighbouring columns (or a column and the outside) differ in depth, cut at
    every depth any column has: where a shallow side meets a deep one at a corner, the deep one has a vertex at the
    shallow one's foot (no T-junction: they share it, and nothing cracks or reads as a fold)"""
    us, vs = np.asarray(us, float), np.asarray(vs, float)
    D = np.asarray(depth, float)
    nu, nv = D.shape
    levels = np.unique(np.round(np.concatenate([[0.0], D[D > 0]]), 7))
    V, idx = [], {}

    def vert(i, j, d):
        k = (i, j, round(float(d), 7))
        if k not in idx:
            idx[k] = len(V)
            V.append(P(us[i], vs[j]) - N(us[i], vs[j]) * d)
        return idx[k]
    F = []

    def face(q, want):
        q = list(q)
        A = [V[k] for k in q]
        nrm = np.cross(A[1] - A[0], A[2] - A[0]) + np.cross(A[2] - A[0], A[3] - A[0])
        F.append(tuple(q) if nrm @ want >= 0 else tuple(q[::-1]))

    def dep(i, j):
        return D[i, j] if 0 <= i < nu and 0 <= j < nv else 0.0
    for i in range(nu):
        for j in range(nv):
            d = D[i, j]
            if d <= 0:
                continue
            uc, vc = 0.5 * (us[i] + us[i + 1]), 0.5 * (vs[j] + vs[j + 1])
            nn = N(uc, vc)
            face((vert(i, j, 0), vert(i + 1, j, 0), vert(i + 1, j + 1, 0), vert(i, j + 1, 0)), nn)
            face((vert(i, j, d), vert(i + 1, j, d), vert(i + 1, j + 1, d), vert(i, j + 1, d)), -nn)
    def steps(lo, hi):
        """the depths a side from lo to hi is cut at"""
        cut = levels[(levels > lo + 1e-9) & (levels < hi - 1e-9)]
        return np.concatenate([[lo], cut, [hi]])
    # sides on the u lines (between columns i-1 and i) and the v lines
    for i in range(nu + 1):
        for j in range(nv):
            a, b = dep(i - 1, j), dep(i, j)
            if abs(a - b) < 1e-9:
                continue
            vc = 0.5 * (vs[j] + vs[j + 1])
            du = P(us[i] + 1e-4, vc) - P(us[i] - 1e-4, vc)
            want = unit(du) * (1.0 if a > b else -1.0)          # toward the shallower column
            st = steps(min(a, b), max(a, b))
            for lo, hi in zip(st[:-1], st[1:]):
                face((vert(i, j, lo), vert(i, j + 1, lo), vert(i, j + 1, hi), vert(i, j, hi)), want)
    for j in range(nv + 1):
        for i in range(nu):
            a, b = dep(i, j - 1), dep(i, j)
            if abs(a - b) < 1e-9:
                continue
            uc = 0.5 * (us[i] + us[i + 1])
            dv = P(uc, vs[j] + 1e-4) - P(uc, vs[j] - 1e-4)
            want = unit(dv) * (1.0 if a > b else -1.0)
            st = steps(min(a, b), max(a, b))
            for lo, hi in zip(st[:-1], st[1:]):
                face((vert(i, j, lo), vert(i + 1, j, lo), vert(i + 1, j, hi), vert(i, j, hi)), want)
    mesh.add(np.array(V), F, mat)


def bars_and_gaps(lo, hi, bar_w, gap_w):
    """Cell edges across [lo, hi]: a bar at each end and bars between, the gaps as near gap_w as fits: (edges, which
    cells are bars)."""
    n = max(1, int(round((hi - lo - bar_w) / (bar_w + gap_w))))
    g = (hi - lo - (n + 1) * bar_w) / n
    edges, is_bar = [lo], []
    x = lo
    for k in range(n):
        x += bar_w
        edges.append(x)
        is_bar.append(True)
        x += g
        edges.append(x)
        is_bar.append(False)
    edges.append(hi)
    is_bar.append(True)
    return np.array(edges), np.array(is_bar)


def swept(V, origin, axis, lo_deg, hi_deg, step_deg, label):
    """a moving spar's vertices V (the ship's frame, as it hangs) turned about axis through origin from lo_deg to
    hi_deg every step_deg, for the nettings' obstacles: [(points, radius per point, label)], each point's radius half
    the way it moves between two steps"""
    V = np.asarray(V, float)
    o, ax = np.asarray(origin, float), unit(np.asarray(axis, float))
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    rel = V - o
    rho = np.linalg.norm(rel - (rel @ ax)[:, None] * ax[None], axis=1)
    rad = rho * math.radians(step_deg) / 2
    out = []
    for a in np.arange(lo_deg, hi_deg + step_deg / 2, step_deg):
        th = math.radians(a)
        Rm = np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)
        out.append((o + rel @ Rm.T, rad, label))
    return out


# ---- plan geometry -----------------------------------------------------------------------------------------------------
def in_poly(pts, P):
    """Even-odd test of points (m, 2) against polygon P (n, 2)."""
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    x0, y0 = P[:, 0][None, :], P[:, 1][None, :]
    x1, y1 = np.roll(P[:, 0], -1)[None, :], np.roll(P[:, 1], -1)[None, :]
    cross = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / np.where(y1 != y0, y1 - y0, 1e-30) + x0)
    return np.count_nonzero(cross, axis=1) % 2 == 1


def seg_dist(pts, P, closed=True, chunk=800):
    """Least distance from points (m, 2) to the polyline P (n, 2)."""
    A = P if closed else P[:-1]
    B = np.roll(P, -1, axis=0) if closed else P[1:]
    d = B - A
    L2 = np.maximum(np.sum(d * d, 1), 1e-30)
    out = np.empty(len(pts))
    for s in range(0, len(pts), chunk):
        q = pts[s:s + chunk][:, None, :]
        t = np.clip(np.sum((q - A[None]) * d[None], 2) / L2[None], 0, 1)
        c = A[None] + t[..., None] * d[None]
        out[s:s + chunk] = np.sqrt(np.min(np.sum((q - c) ** 2, 2), 1))
    return out


def densify(P, step, closed=True):
    """A polygon (or open polyline) with points added along any edge longer than step."""
    P = np.asarray(P, float)
    pairs = zip(P, np.roll(P, -1, axis=0)) if closed else zip(P[:-1], P[1:])
    out = []
    for a, b in pairs:
        n = max(int(math.ceil(np.linalg.norm(b - a) / step)), 1)
        out.extend(a + (b - a) * (k / n) for k in range(n))
    if not closed:
        out.append(P[-1])
    return np.array(out)


def rect2(cx, cy, L, W):
    """A rectangle in plan, counter-clockwise: L along x, W along y."""
    return np.array([[cx - L / 2, cy - W / 2], [cx + L / 2, cy - W / 2], [cx + L / 2, cy + W / 2],
                     [cx - L / 2, cy + W / 2]])


def cdt(outline, holes, step):
    """Triangles over the polygon outline (n, 2) less the holes (each (m, 2)), keeping every edge of each, with a
    triangular lattice of points step apart inside: (points (k, 2), triangles (t, 3) counter-clockwise from above)."""
    try:
        from mathutils import Vector, geometry      # Blender's constrained Delaunay triangulation
    except ImportError:                             # the bpy module registers mathutils when it is imported
        import bpy  # noqa: F401
        from mathutils import Vector, geometry
    outline = np.asarray(outline, float)
    xs = np.arange(outline[:, 0].min() + step / 2, outline[:, 0].max(), step)
    yw = float(np.abs(outline[:, 1]).max()) + step
    pts = []
    for j, xx in enumerate(xs):
        ys = np.arange(-yw + (step / 2 if j % 2 else 0.0), yw, step * math.sqrt(0.75) * 2 / math.sqrt(3))
        pts.append(np.column_stack([np.full(len(ys), xx), ys]))
    pts = np.concatenate(pts)
    keep = in_poly(pts, outline)
    for h in holes:
        keep &= ~in_poly(pts, h)
    pts = pts[keep]
    clear = seg_dist(pts, outline)
    for h in holes:
        clear = np.minimum(clear, seg_dist(pts, h))
    pts = pts[clear > 0.55 * step]
    P2 = np.concatenate([outline] + list(holes) + [pts])
    E, k0 = [], 0
    for poly in [outline] + list(holes):
        m = len(poly)
        E += [(k0 + k, k0 + (k + 1) % m) for k in range(m)]
        k0 += m
    out = geometry.delaunay_2d_cdt([Vector((float(a), float(b))) for a, b in P2], E, [], 0, 1e-9, True)
    ov, of, orig_v = out[0], out[2], out[3]
    if len(ov) != len(P2):
        raise ValueError(f"the deck's triangulation added or merged points ({len(ov)} for {len(P2)})")
    to_in = [ids[0] for ids in orig_v]
    T = np.array([[to_in[i] for i in f] for f in of])
    # which triangles are the solid's: walked over from the triangulation's hull (outside), turning inside out across
    # every edge of the outline and the holes. Where three of the outline's points lie in a line (a straight side cut
    # into steps) the hull can run across them, leaving a triangle of no area along the boundary whose centre a test
    # can't place; the walk does. The centre test checks it everywhere else.
    cons = set(frozenset(e) for e in E)
    adj = {}
    for i, t in enumerate(T):
        for k in range(3):
            adj.setdefault(frozenset((int(t[k]), int(t[(k + 1) % 3]))), []).append(i)
    par = np.full(len(T), -1)
    todo = collections.deque()
    for e, ts in adj.items():
        if len(ts) == 1 and par[ts[0]] < 0:                 # on the hull: inside where the edge is the outline's
            par[ts[0]] = 1 if e in cons else 0
            todo.append(ts[0])
    while todo:
        i = todo.popleft()
        for k in range(3):
            e = frozenset((int(T[i, k]), int(T[i, (k + 1) % 3])))
            for j in adj[e]:
                if par[j] < 0:
                    par[j] = par[i] ^ (1 if e in cons else 0)
                    todo.append(j)
    sel = par == 1
    cen = P2[T].mean(1)
    sel_c = in_poly(cen, outline)
    for h in holes:
        sel_c &= ~in_poly(cen, h)
    a2 = (P2[T[:, 1], 0] - P2[T[:, 0], 0]) * (P2[T[:, 2], 1] - P2[T[:, 0], 1]) - \
         (P2[T[:, 1], 1] - P2[T[:, 0], 1]) * (P2[T[:, 2], 0] - P2[T[:, 0], 0])
    long2 = np.max(np.sum((P2[T[:, [1, 2, 0]]] - P2[T]) ** 2, axis=2), axis=1)
    if np.any((sel != sel_c) & (np.abs(a2) >= 1e-9 * long2)) or np.any(par < 0):
        raise ValueError("the deck's triangulation: the walk from its hull and the centre test disagree")
    T = T[sel]
    have = set()
    for t in T:
        for k in range(3):
            have.add(frozenset((int(t[k]), int(t[(k + 1) % 3]))))
    missing = [e for e in E if frozenset(e) not in have]
    if missing:
        raise ValueError(f"the deck's triangulation lost {len(missing)} edges of its outline and holes")
    a2 = (P2[T[:, 1], 0] - P2[T[:, 0], 0]) * (P2[T[:, 2], 1] - P2[T[:, 0], 1]) - \
         (P2[T[:, 1], 1] - P2[T[:, 0], 1]) * (P2[T[:, 2], 0] - P2[T[:, 0], 0])
    T[a2 < 0] = T[a2 < 0][:, ::-1]
    return P2, T


# ---- the deck's planking, as the material draws it ---------------------------------------------------------------------
def planking_terms(m, U, V, P, Mg=None, Ms=None, aa=0.0015):
    """The laid deck's pattern from its 'Planking' UV (U, V = x, y in metres), written once for the material (m makes
    Blender Math nodes) and for numpy (np_math): planks w wide straight fore and aft with one on the middle line, seams
    'seam' wide, butts on a beam every Lb beams, shifted by 'stagger' beams from strake to strake (over four strakes),
    and two plugs over the spikes in each plank at every beam (at a quarter of its width from each edge; either side of
    a butt they move off it to the plank ends). P: w, seam, x0 (a beam), bp (the beam pitch), Lb, stagger, plug_r,
    plug_off, nib.

    Where the deck narrows (the bow and stern) the planks are nibbed into the waterway: from its 'Margin' UV (Mg, Ms =
    the waterway's inner edge's half-breadth less |y|, and how fast that edge's half-breadth changes along x), a plank
    runs on until only 'nib' of its width is left inside the waterway's edge and ends there square across; beyond that
    the waterway is let in wider to take it (the material draws that part as the waterway's oak).

    Returns {'seam': 1 on a seam, 0 off it, a soft edge aa wide; 'plug': 1 on a plug; 'margin': 1 where the waterway
    is drawn; 'j': the plank's strake; 'seg': its length along the strake}."""
    sw, w, b = P["seam"], P["w"], P["bp"]
    L = P["Lb"] * b
    st = P["stagger"]

    def near(v, step):
        return m("ABSOLUTE", m("SUBTRACT", v, m("MULTIPLY", m("ROUND", m("DIVIDE", v, step)), step)))

    def line(d, width):
        return m("ADD", m("DIVIDE", m("SUBTRACT", width / 2, d), aa), 0.5, clamp=True)

    def step_(d):                                     # 1 where d < 0, a soft edge aa wide
        return m("ADD", m("DIVIDE", m("MULTIPLY", d, -1.0), aa), 0.5, clamp=True)
    Uo = m("SUBTRACT", U, P["x0"])
    s_long = line(near(m("SUBTRACT", V, w / 2), w), sw)
    j = m("FLOOR", m("DIVIDE", m("ADD", V, w / 2), w))
    k = m("FLOORED_MODULO", j, float(len(st)))
    off = 0.0
    for i, s in enumerate(st):
        if s:
            off = m("ADD", off, m("MULTIPLY", m("COMPARE", k, float(i), 0.5), s * b))
    Ub = m("SUBTRACT", Uo, off)
    s_butt = line(near(Ub, L), sw)
    # plugs: at every beam, a quarter of the plank's width in from each edge; at a butt, plug_off either side of it
    at_butt = line(near(Ub, L), b)                    # 1 where the nearest beam carries this plank's butt
    du = m("ABSOLUTE", m("SUBTRACT", near(Uo, b), m("MULTIPLY", at_butt, P["plug_off"])))
    dv = near(m("SUBTRACT", V, w / 4), w / 2)
    dist = m("SQRT", m("ADD", m("MULTIPLY", du, du), m("MULTIPLY", dv, dv)))
    plug = line(dist, 2 * P["plug_r"])
    seg = m("FLOOR", m("DIVIDE", Ub, L))
    if Mg is None:
        return {"seam": m("MAXIMUM", s_long, s_butt), "plug": plug, "margin": 0.0, "j": j, "seg": seg}
    # the nibs: this strake's width left inside the waterway's edge (expo), and its inner neighbour's (w more); along x
    # the distance to where it falls to the nib is (expo - nib) / slope
    jj = m("ABSOLUTE", j)
    yin = m("SUBTRACT", m("MULTIPLY", jj, w), w / 2)                  # the strake's inner edge, |y|
    expo = m("ADD", Mg, m("SUBTRACT", m("ABSOLUTE", V), yin))
    slope = m("MAXIMUM", Ms, 0.01)
    nibw = P["nib"] * w
    dx_own = m("DIVIDE", m("SUBTRACT", expo, nibw), slope)
    dx_in = m("DIVIDE", m("SUBTRACT", m("ADD", expo, w), nibw), slope)
    zone = step_(dx_own)                                               # this strake is waterway here
    zone_in = step_(dx_in)                                             # and its inner neighbour
    f = m("DIVIDE", m("SUBTRACT", m("ABSOLUTE", V), yin), w)          # 0 at its inner edge, 1 at its outer
    outer = m("GREATER_THAN", f, 0.5)
    kill = m("ADD", m("MULTIPLY", outer, zone), m("MULTIPLY", m("SUBTRACT", 1.0, outer), zone_in))
    s_nib = m("MULTIPLY", line(m("ABSOLUTE", dx_own), sw), m("SUBTRACT", 1.0, zone_in))
    seam = m("MAXIMUM", m("MULTIPLY", s_long, m("SUBTRACT", 1.0, kill)),
             m("MAXIMUM", m("MULTIPLY", s_butt, m("SUBTRACT", 1.0, zone)), s_nib))
    return {"seam": seam, "plug": m("MULTIPLY", plug, m("SUBTRACT", 1.0, zone)), "margin": zone, "j": j, "seg": seg}


def np_math(op, a, b=None, c=None, clamp=False):
    """Blender's Math node operations on numpy arrays, for planking_terms outside Blender."""
    a = np.asarray(a, float)
    b = None if b is None else np.asarray(b, float)
    r = {"ADD": lambda: a + b, "SUBTRACT": lambda: a - b, "MULTIPLY": lambda: a * b,
         "DIVIDE": lambda: np.where(b != 0, a / np.where(b != 0, b, 1.0), 0.0),
         "ABSOLUTE": lambda: np.abs(a), "ROUND": lambda: np.floor(a + 0.5), "FLOOR": lambda: np.floor(a),
         "SQRT": lambda: np.sqrt(np.maximum(a, 0.0)),
         "FLOORED_MODULO": lambda: np.where(b != 0, a - np.floor(a / np.where(b != 0, b, 1.0)) * b, 0.0),
         "MAXIMUM": lambda: np.maximum(a, b), "GREATER_THAN": lambda: (a > b).astype(float),
         "COMPARE": lambda: (np.abs(a - b) <= max(float(c), 1e-5)).astype(float)}[op]()
    return np.clip(r, 0.0, 1.0) if clamp else r


def planks_material(bpy, name, P, plank, pitch, oak, fade_m=(25.0, 90.0)):
    """The laid deck's material in Blender (bpy passed in, so this module imports without it): planking_terms over the
    'Planking' and 'Margin' UVs, each plank length its own slight tint and a fine grain along it, pitch in the seams,
    the plugs a shade darker (end grain), the waterway let in for the nibs in its oak; the seams fade to the deck's
    average tone between fade_m's distances from the camera (they are a centimetre wide) and are let in a millimetre
    by a bump. plank, pitch and oak: linear RGB."""
    mt = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    N, Lk = nt.nodes, nt.links
    b = N.get("Principled BSDF")

    def m(op, a, b_=None, c=None, clamp=False):
        n = N.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for k, v in enumerate((a, b_, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                Lk.new(v, n.inputs[k])
        return n.outputs[0]

    def uv(name_):
        u = N.new("ShaderNodeUVMap")
        u.uv_map = name_
        sp = N.new("ShaderNodeSeparateXYZ")
        Lk.new(u.outputs[0], sp.inputs[0])
        return sp.outputs[0], sp.outputs[1]
    U, V = uv("Planking")
    Mg, Ms = uv("Margin")
    T = planking_terms(m, U, V, P, Mg, Ms)
    cv = N.new("ShaderNodeCombineXYZ")
    Lk.new(T["j"], cv.inputs[0])
    Lk.new(T["seg"], cv.inputs[1])
    wn = N.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    Lk.new(cv.outputs[0], wn.inputs["Vector"])
    tint = m("ADD", 0.88, m("MULTIPLY", wn.outputs["Value"], 0.24))
    gv = N.new("ShaderNodeCombineXYZ")
    Lk.new(m("MULTIPLY", U, 2.0), gv.inputs[0])
    Lk.new(m("ADD", m("MULTIPLY", V, 60.0), m("MULTIPLY", wn.outputs["Value"], 37.0)), gv.inputs[1])
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.6
    Lk.new(gv.outputs[0], nz.inputs["Vector"])
    grain = m("ADD", 0.9, m("MULTIPLY", nz.outputs["Fac"], 0.2))
    shade = m("MULTIPLY", m("MULTIPLY", tint, grain), m("SUBTRACT", 1.0, m("MULTIPLY", T["plug"], 0.22)))
    dist = N.new("ShaderNodeCameraData").outputs["View Distance"]
    n0, n1 = fade_m
    fade = m("DIVIDE", m("SUBTRACT", n1, dist), n1 - n0, clamp=True)
    seen = m("MULTIPLY", T["seam"], fade)
    share = P["seam"] / P["w"]                        # the seams' share of the deck, for its tone far off
    far = m("MULTIPLY", m("SUBTRACT", 1.0, fade), share)
    mg = T["margin"]
    rgb = N.new("ShaderNodeCombineColor")
    for i in range(3):
        wood = m("ADD", m("MULTIPLY", m("MULTIPLY", shade, plank[i]), m("SUBTRACT", 1.0, mg)),
                 m("MULTIPLY", mg, m("MULTIPLY", grain, oak[i])))
        mix_far = m("ADD", m("MULTIPLY", wood, m("SUBTRACT", 1.0, far)), m("MULTIPLY", far, pitch[i]))
        Lk.new(m("ADD", m("MULTIPLY", mix_far, m("SUBTRACT", 1.0, seen)), m("MULTIPLY", seen, pitch[i])), rgb.inputs[i])
    Lk.new(rgb.outputs[0], b.inputs["Base Color"])
    Lk.new(m("ADD", 0.72, m("MULTIPLY", seen, 0.2)), b.inputs["Roughness"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 1.0
    Lk.new(m("ADD", m("MULTIPLY", seen, -0.001), m("MULTIPLY", T["plug"], -0.0002)), bump.inputs["Height"])
    Lk.new(bump.outputs[0], b.inputs["Normal"])
    return mt


def netting_material(bpy, name, rope, mesh_m, cord_m):
    """the hammock nettings' rope mesh in Blender: diamonds mesh_m on a side from the netting faces' UV 'Netting' (arc
    length along, height; metres), cords cord_m thick, cut out between by the alpha"""
    mt = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    N, Lk = nt.nodes, nt.links
    b = N.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rope, 1)
    b.inputs["Roughness"].default_value = 0.9

    def m(op, a, b_=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for k, v in enumerate((a, b_)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                Lk.new(v, n.inputs[k])
        return n.outputs[0]
    uvn = N.new("ShaderNodeUVMap")
    uvn.uv_map = "Netting"
    sp = N.new("ShaderNodeSeparateXYZ")
    Lk.new(uvn.outputs[0], sp.inputs[0])
    U, V = sp.outputs[0], sp.outputs[1]
    d = mesh_m * math.sqrt(2.0)                  # cords at 45 degrees, mesh_m apart: u +- v steps by d between them
    cords = []
    for op in ("ADD", "SUBTRACT"):
        f = m("ABSOLUTE", m("SUBTRACT", m("FRACT", m("DIVIDE", m(op, U, V), d)), 0.5))   # 0.5 on a cord, 0 between
        cords.append(m("GREATER_THAN", f, 0.5 - cord_m / (2 * mesh_m)))
    Lk.new(m("MAXIMUM", cords[0], cords[1]), b.inputs["Alpha"])
    return mt


# ---- what meets by design ----------------------------------------------------------------------------------------------
MEETS = {
    # (deck part, object or another deck part): (why they meet, how far either may go into the other, inches). The gun
    # deck's parts (slice 12: the ladders' feet on it, the capstan's barrel through the beams) are gundeck_1797.json's
    ("Waterways", "BulwarkIn"): ("the waterway is let into the bulwark's face", 0.5),
    ("Nettings", "RailCap"): ("the nettings' cranes and cloth stand on the rail cap", 0.5),
    ("SparDeck", "PinRails"): ("the fife rails' posts and the eyebolts stand in the deck", 8.0),
    ("SparDeck", "BulwarkIn"): ("the deck's top meets the bulwark's foot along its edge (under the waterway)", 0.1),
    ("SparDeck", "GunWall"): ("the deck's underside meets the gun deck's side along its edge", 0.1),
    ("SparDeck", "Bulkheads"): ("the placeholder bulkheads (slices 9-14) stand up to the deck's underside", 0.1),
    # the deck's own parts
    ("Waterways", "SparDeck"): ("the waterway is let into the deck", 0.55),
    ("WaistFrame", "SparDeck"): ("the gangways' coamings stand in the deck's edge, and the waist's beams run on under "
                                 "the gangways' planks, their tops at the planks' underside", 0.3),
    ("Hatches", "SparDeck"): ("the hatchways' coamings stand in the deck's openings, their outsides its sides", 0.1),
    ("Companion", "SparDeck"): ("the companion's coaming stands in the deck's opening, its outside the opening's sides", 0.1),
    ("Skylights", "SparDeck"): ("the skylights' coamings stand in the deck's openings, their outsides its sides", 0.1),
    ("Chimney", "SparDeck"): ("the chimney's coaming stands in the deck's opening, its outside the opening's sides", 0.1),
    ("MastCoats", "SparDeck"): ("the mast coats' skirts are let into the deck", 0.35),
    ("CapstanPawls", "SparDeck"): ("the capstan's pawl ring is let into the deck", 0.25),
    ("BreastRails", "SparDeck"): ("the breast rails' posts and foot rails are let into the deck", 0.25),
    ("Belfry", "SparDeck"): ("the belfry's posts and braces are let into the deck", 0.25),
    ("Binnacle", "SparDeck"): ("the binnacle is let into the deck", 0.15),
    ("BowspritStep", "SparDeck"): ("the bowsprit's step and bitts are let into the deck", 0.25),
    ("WheelStandards", "SparDeck"): ("the wheel's standards and the tiller rope's plates are let into the deck", 0.25),
    ("TillerRope", "SparDeck"): ("the tiller rope's legs go down into the plates' holes, ending a hair into the deck "
                                 "(the gun deck's slice takes them on from its underside to the leading sheaves)", 0.4),
    ("TillerRope", "WheelStandards"): ("the tiller rope's legs go down through the plates' holes (each drawn as a dark "
                                       "box the rope passes through)", 0.4),
    ("Wheel", "WheelStandards"): ("the wheel's axle turns in the standards' bearings", 1.3),
    ("Belfry", "BreastRails"): ("the forecastle's breast rail runs half an inch into the belfry's posts", 0.55),
    ("Ladders", "BreastRails"): ("the ladders' hand ropes are made fast to eye plates let into the breast rails' posts",
                                 0.15),
}


def meets_by_design(a, b, meets=None):
    """why deck part a meets object b (or another deck part) by design (MEETS or meets, either way round), or None"""
    meets = MEETS if meets is None else meets
    m = meets.get((a, b)) or meets.get((b, a))
    return m[0] if m else None


def meets_depth_in(a, b, meets=None):
    """how far (inches) a and b may go into each other where they meet by design"""
    meets = MEETS if meets is None else meets
    return (meets.get((a, b)) or meets[(b, a)])[1]


def islands(T, n):
    """each vertex's connected piece of a triangle mesh (T (m, 3) over n vertices): labels 0..k-1"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    T = np.asarray(T, int).reshape(-1, 3)
    a = np.concatenate([T[:, 0], T[:, 1], T[:, 2]])
    b = np.concatenate([T[:, 1], T[:, 2], T[:, 0]])
    return connected_components(coo_matrix((np.ones(len(a)), (a, b)), shape=(n, n)), directed=False)[1]


def room(objs, mine, z_deck, near=0.3, meets=None, flat=("SparDeck",)):
    """The deck's clearance check (build.json deck.room). objs: {name: (V (n, 3) in the ship's frame, T (m, 3))} for
    every mesh of the ship (the sails and ropes in every state too) but the measured reference; mine: the deck's parts;
    z_deck(x): the deck's top (flat across), or None to leave out the standing check (the head's and stern's parts,
    slice 9, which check their own meets, not MEETS); flat: the deck itself, left out of the standing check (the gun
    deck's room, slice 12, passes its own). Returns:

    * meet: the pairs, a deck part and another object or another deck part, whose surfaces cross and don't meet by
      design (MEETS, either way round), and those that do but go deeper than MEETS allows;
    * by_design: the pairs that meet by design, each with how deep the two go into each other: every vertex of either
      near where they meet (within 'near' of the box round the other's meeting triangles), measured behind the other's
      nearest face where that face lies square to it (within 'near'), so a part buried whole (an eyebolt's shank in
      the deck) counts as well as one crossing the other's surface; where that face's piece is closed, the vertex
      counts only if it is inside the piece by parity (one off a thin plate's edge lies square behind the edge's
      narrow face, outside the plate);
    * floats: a piece of a deck part that reaches the deck's top must stand on it: none of its faces looking down (a
      foot) may hang between 0.1 in and 2.5 in over the deck (a flat foot left level on the sheer) unless it bears on
      something else, another object's surface within 0.3 in of it along the face's normal (a partition scribed into
      the waterway, an edge let into a raked wall, a chair's foot on the floor cloth); and a piece that comes within
      2.5 in of the deck without reaching it must touch something (a pawl on its ring)."""
    try:
        from mathutils.bvhtree import BVHTree
    except ImportError:                             # the bpy module registers mathutils when it is imported
        import bpy  # noqa: F401
        from mathutils.bvhtree import BVHTree
    names = sorted(objs)
    mine = [n for n in names if n in mine]
    trees, labels = {}, {}

    def tree(n):
        if n not in trees:
            V, T = objs[n]
            trees[n] = BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True)
        return trees[n]

    def lab(n):
        if n not in labels:
            labels[n] = islands(objs[n][1], len(objs[n][0]))
        return labels[n]
    # everything that isn't the deck's, in one tree; each deck part against it and against the deck's other parts
    off, owner, Vs, Ts, nv = {}, [], [], [], 0
    for n in names:
        if n in mine:
            continue
        V, T = objs[n]
        off[n] = len(owner)
        owner += [n] * len(T)
        Vs.append(V)
        Ts.append(T + nv)
        nv += len(V)
    rest = BVHTree.FromPolygons(np.concatenate(Vs).tolist(), np.concatenate(Ts).tolist(), all_triangles=True)
    pairs = {}
    for a in mine:
        for i, j in tree(a).overlap(rest):
            b = owner[j]
            pairs.setdefault((a, b), ([], []))
            pairs[(a, b)][0].append(i)
            pairs[(a, b)][1].append(j - off[b])
        for b in mine:
            if b > a:
                for i, j in tree(a).overlap(tree(b)):
                    pairs.setdefault((a, b), ([], []))
                    pairs[(a, b)][0].append(i)
                    pairs[(a, b)][1].append(j)

    pieces = {}

    def piece(n, f):
        """the closed piece of n that face f belongs to, as a tree of its own faces, or None where that piece is open
        (a sheet, a disc), where a point's side of it can't be told by parity"""
        key = (n, int(lab(n)[objs[n][1][f][0]]))
        if key not in pieces:
            V, T = objs[n]
            Tp = T[lab(n)[T[:, 0]] == key[1]]
            E = np.sort(np.concatenate([Tp[:, [0, 1]], Tp[:, [1, 2]], Tp[:, [2, 0]]]), axis=1)
            closed = bool(len(Tp)) and bool((np.unique(E, axis=0, return_counts=True)[1] == 2).all())
            pieces[key] = BVHTree.FromPolygons(V.tolist(), Tp.tolist(), all_triangles=True) if closed else None
        return pieces[key]

    def inside(t, p):
        """p is inside the closed piece in tree t: the parity of its faces crossed along three rays, two of three"""
        from mathutils import Vector
        votes = 0
        for d_ in ((0.5773, 0.5774, 0.5775), (-0.3112, 0.8231, -0.4751), (0.7071, -0.2911, -0.6443)):
            d_ = Vector(d_).normalized()
            o, n = Vector(np.asarray(p, float).tolist()), 0
            while n < 200:
                hit = t.ray_cast(o, d_)[0]
                if hit is None:
                    break
                n += 1
                o = hit + d_ * 1e-6
            votes += n & 1
        return votes >= 2

    def depth(a, b):
        """how deep a and b go into each other: a vertex square behind the other's nearest face, where that face's
        piece is closed only if the vertex is inside it by parity (a vertex off a thin plate's edge lies square behind
        the edge's narrow face without being in the plate)"""
        d = 0.0
        for x, y, sel in ((a, b, pairs[(a, b)][1]), (b, a, pairs[(a, b)][0])):
            V = objs[x][0]
            Vy, Ty = objs[y]
            P = Vy[Ty[np.unique(sel)]].reshape(-1, 3)
            vs = np.nonzero(np.all((V >= P.min(0) - near) & (V <= P.max(0) + near), axis=1))[0]
            ty = tree(y)
            cand = []
            for v in vs:
                co, nrm, f, dist = ty.find_nearest(V[v].tolist(), near)
                if co is None:
                    continue
                s_ = float((V[v] - np.array(co)) @ np.array(nrm))
                if s_ < 0 and -s_ >= 0.95 * dist and -s_ > d:
                    cand.append((-s_, int(v), int(f)))
            for s_, v, f in sorted(cand, reverse=True):
                t = piece(y, f)
                if t is None or inside(t, V[v]):
                    d = max(d, s_)
                    break
        return d
    ok = {}
    for k in pairs:
        if meets_by_design(*k, meets):
            ok[k] = (len(pairs[k][0]), round(depth(*k) / IN, 2))
    meet = [[a, b, len(pairs[(a, b)][0])] for a, b in sorted(pairs) if (a, b) not in ok]
    meet += [[a, b, n, "deeper than " + str(meets_depth_in(a, b, meets)) + " in: " + str(dp) + " in"]
             for (a, b), (n, dp) in sorted(ok.items()) if dp > meets_depth_in(a, b, meets)]
    by_design = [[a, b, n, meets_by_design(a, b, meets), "deepest " + str(dp) + " in"]
                 for (a, b), (n, dp) in sorted(ok.items())]
    # standing on the deck
    floats, tol, band, reach = [], 0.1 * IN, 2.5 * IN, 0.3 * IN

    def bears(a, V, T, faces, nrm, v):
        """the foot vertex v of part a (on the downward faces 'faces', their normals nrm) bears on something else:
        another object's surface within reach of it along those faces' mean normal, before or behind it (a partition
        scribed into the waterway, an edge let into a raked wall, a chair's foot on the floor cloth)"""
        at = (T[faces] == v).any(1)
        n = nrm[faces[at]].sum(0)
        n = n / max(float(np.linalg.norm(n)), 1e-12)
        o, d = (V[v] - reach * n).tolist(), n.tolist()
        return rest.ray_cast(o, d, 2.0 * reach)[0] is not None or \
            any(tree(b).ray_cast(o, d, 2.0 * reach)[0] is not None for b in mine if b != a)
    for a in (mine if z_deck is not None else []):
        if a in flat:
            continue
        V, T = objs[a]
        L = lab(a)
        h = V[:, 2] - z_deck(V[:, 0])
        nrm = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
        down = nrm[:, 2] < -0.7 * np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)
        lt = L[T[:, 0]]
        hmin = np.full(L.max() + 1, np.inf)
        np.minimum.at(hmin, L, h)
        for p in np.nonzero(hmin <= tol)[0]:                  # it reaches the deck: no foot hangs over it
            faces = np.nonzero(down & (lt == p))[0]
            vv = np.unique(T[faces].ravel())
            bad = [v for v in vv[(h[vv] > tol) & (h[vv] < band)] if not bears(a, V, T, faces, nrm, v)]
            if len(bad):
                v = bad[int(np.argmax(h[bad]))]
                floats.append([a, "a foot over the deck", round(float(h[v]) / IN, 2), np.round(V[v], 3).tolist()])
        for p in np.nonzero((hmin > tol) & (hmin < band))[0]:  # near the deck without reaching it: on something
            tp = np.nonzero(lt == p)[0]
            tr = BVHTree.FromPolygons(V.tolist(), T[tp].tolist(), all_triangles=True)
            on = any(lt[j] != p for _, j in tr.overlap(tree(a))) or bool(tr.overlap(rest)) or \
                any(tr.overlap(tree(b)) for b in mine if b != a)
            if not on:
                v = np.nonzero(L == p)[0][np.argmin(h[L == p])]
                floats.append([a, "a piece standing free over the deck", round(float(h[v]) / IN, 2),
                               np.round(V[v], 3).tolist()])
    return {"meet": meet, "by_design": by_design, "floats": floats}


def surface_points(V, T, step, lo=None, hi=None):
    """points over triangles' surfaces (V (n, 3), T (m, 3)) no more than step apart, for clearance tests against point
    obstacles. A small triangle gives its corners and middle; a bigger one is laid out from the corner opposite its
    shortest edge, in rows across it every step along its length and points every step along each row (a long thin
    rope's triangle gives a few points a row). With a box (lo, hi: corners in x, |y|, z), only the rows that can pass
    through it are laid, so a long rope yields points only where it passes near the box"""
    V, T = np.asarray(V, float), np.asarray(T, int).reshape(-1, 3)
    tri = V[T]                                                    # (m, 3, 3)
    if lo is not None and len(tri):
        mn, mx = tri.min(1), tri.max(1)
        ay_lo = np.where(mn[:, 1] * mx[:, 1] <= 0.0, 0.0, np.minimum(np.abs(mn[:, 1]), np.abs(mx[:, 1])))
        ay_hi = np.maximum(np.abs(mn[:, 1]), np.abs(mx[:, 1]))
        tri = tri[(mx[:, 0] >= lo[0]) & (mn[:, 0] <= hi[0]) & (ay_hi >= lo[1]) & (ay_lo <= hi[1]) &
                  (mx[:, 2] >= lo[2]) & (mn[:, 2] <= hi[2])]
    e = np.linalg.norm(tri[:, [1, 2, 0]] - tri, axis=2)              # edge k runs from corner k to corner k+1
    small = e.max(1) <= step
    out = [tri[small].reshape(-1, 3), tri[small].mean(1)]
    for t3, ek in zip(tri[~small], e[~small]):
        k = int(ek.argmin())                                      # the shortest edge, corner k to corner k+1
        B, C, A = t3[k], t3[(k + 1) % 3], t3[(k + 2) % 3]
        n_s = int(math.ceil(max(ek[(k + 1) % 3], ek[(k + 2) % 3]) / step))
        sv = np.arange(n_s + 1) / n_s
        if lo is not None:                                        # the rows whose ends' span can reach the box
            P1, P2 = A + sv[:, None] * (B - A), A + sv[:, None] * (C - A)
            m1, m2 = np.minimum(P1, P2) - step, np.maximum(P1, P2) + step
            sv = sv[(m2[:, 0] >= lo[0]) & (m1[:, 0] <= hi[0]) & (m2[:, 2] >= lo[2]) & (m1[:, 2] <= hi[2])]
        w = float(np.linalg.norm(C - B))
        for s_ in sv:
            n_t = max(1, int(math.ceil(s_ * w / step)))
            tv = np.arange(n_t + 1) / n_t
            out.append(A + s_ * ((1.0 - tv)[:, None] * (B - A) + tv[:, None] * (C - A)))
    P = np.concatenate(out) if out else np.zeros((0, 3))
    if lo is not None and len(P):
        P = P[(P[:, 0] >= lo[0]) & (P[:, 0] <= hi[0]) & (np.abs(P[:, 1]) >= lo[1]) & (np.abs(P[:, 1]) <= hi[1]) &
              (P[:, 2] >= lo[2]) & (P[:, 2] <= hi[2])]
    return np.unique(np.round(P, 5), axis=0) if len(P) else P


class Deck:
    """The spar deck and its fittings for the skin sk (skin.Skin, built) and the rig (spars.Rig, built)."""

    def __init__(self, sk, rig, path=os.path.join(HERE, "deck_1797.json")):
        import skin as SKM
        self.sk, self.rig, self.SKM = sk, rig, SKM
        self.c = json.load(open(path))
        if not hasattr(sk, "pos"):
            sk.positions()
        self.L = sk.L
        pr = sk.pr
        self.e0, self.e1, self.fc = (self.xm(v) for v in (pr.x_e0, pr.x_e1, pr.x_fc))

        def row(name):
            P, _, _ = sk.row_points(name)
            return P[np.argsort(P[:, 0])]
        self.top = row("w_Pd")           # the deck's top at the bulwark's inner face
        self.und = row("g_Pu")           # its underside at the gun deck's side
        self.gun = row("g_G")            # the gun deck's top
        self.psh = row("w_P")            # the plankshear's top at the bulwark's inner face
        self.parts_ = {}
        self.frames = {}
        self.info = {}

    # --- along the ship -------------------------------------------------------------------------------------------------
    def xm(self, xpx):
        return float((xpx - self.L.mid_px) * self.sk.m.sx)

    def xpx(self, x):
        return float(x) / self.sk.m.sx + self.L.mid_px

    def z(self, x):
        """the deck's top at x (flat across)"""
        return np.interp(x, self.top[:, 0], self.top[:, 2])

    def zu(self, x):
        return np.interp(x, self.und[:, 0], self.und[:, 2])

    def zg(self, x):
        return np.interp(x, self.gun[:, 0], self.gun[:, 2])

    def y_side(self, x):
        """the bulwark's inner face at the deck's top (starboard)"""
        return np.interp(x, self.top[:, 0], self.top[:, 1])

    def face(self, x, h):
        """the bulwark's inner face (starboard) at x, h above the deck's top: the point and the horizontal unit vector
        square to the face, pointing inboard"""
        X = np.array([self.xpx(x)])
        target = float(self.z(x)) + h
        zp = target / FT * self.L.ppf_y
        for _ in range(4):
            P, N = self.sk.surf(X, np.array([zp]), True, 0, self.SKM.BUL)
            zp += (target - P[0][2]) / FT * self.L.ppf_y
        n = np.array([N[0][0], N[0][1], 0.0])
        n = -unit(n) if n[1] > 0 else unit(n)
        return P[0], n

    def seat(self, part, k0, z_flat, let, tol=0.01 * IN):
        """lay on the deck what was added to part since k0 (its count of vertex blocks then) and stands on the flat
        level z_flat: each vertex at that level goes to the deck's top under it, less let, so a flat foot follows the
        deck's sheer instead of standing clear of it at one end and sinking at the other"""
        for V in part.V[k0:]:
            m = np.abs(V[:, 2] - z_flat) < tol
            if m.any():
                V[m, 2] = self.z(V[m, 0]) - let

    def drape(self, part, k0, z_flat):
        """lay what was added to part since k0, built level on z_flat, along the deck's sheer: each vertex moves up or
        down by the deck's rise under it (for things lying on the deck: the capstan's pawl ring)"""
        for V in part.V[k0:]:
            V[:, 2] += self.z(V[:, 0]) - z_flat

    def plan_x(self, px):
        """a place on the 1849 plan (x px) in the ship: between two masts by its share of the way, aft of the mizzen or
        forward of the fore mast by its distance from the mast at the plan's scale"""
        reg = self.c["registration"]
        mp = reg["masts_px"]
        names = sorted(mp, key=lambda k: mp[k])
        P = [mp[k] for k in names]
        X = [float(self.rig.masts[k]["O"][0]) for k in names]
        if px <= P[0]:
            return X[0] + (px - P[0]) / reg["px_per_ft"] * FT
        if px >= P[-1]:
            return X[-1] + (px - P[-1]) / reg["px_per_ft"] * FT
        return float(np.interp(px, P, X))

    def mast_at(self, name, z):
        """the mast's axis point at height z and its radius there"""
        m = self.rig.masts[name]
        O, u = np.asarray(m["O"], float), np.asarray(m["u"], float)
        s = (z - O[2]) / u[2]
        return O + s * u, float(m["R_lower"](s)), u

    # --- the layout -----------------------------------------------------------------------------------------------------
    def layout(self):
        c = self.c
        it = self.items = {}
        hw = c["hatchways"]
        for h in hw["items"]:
            L, W = (v * FT for v in h["inside_ft"])
            it[h["name"]] = dict(x=self.plan_x(h["plan_px"][0]), L=L, W=W, t=hw["coaming_thick_in"] * IN,
                                 high=hw["coaming_high_in"] * IN, kind="hatch")
        cp = c["companion"]
        L, W = (v * FT for v in cp["inside_ft"])
        it["Companion"] = dict(x=self.plan_x(cp["plan_px"][0]), L=L, W=W, t=cp["coaming_thick_in"] * IN,
                               high=6 * IN, kind="companion")
        sl = c["skylights"]
        for s in sl["items"]:
            L, W = (v * FT for v in s["inside_ft"])
            x = s["x_m"] if "x_m" in s else self.plan_x(s["plan_px"][0])
            it[s["name"]] = dict(x=x, L=L, W=W, t=sl["coaming_thick_in"] * IN, high=sl["coaming_high_in"] * IN,
                                 kind="skylight")
        ch = c["chimney"]
        L, W = (v * FT for v in ch["inside_ft"])
        it["Chimney"] = dict(x=self.plan_x(ch["plan_px"][0]), L=L, W=W, t=ch["coaming_thick_in"] * IN,
                             high=ch["coaming_high_in"] * IN, kind="chimney")
        for v in it.values():
            v["Lo"], v["Wo"] = v["L"] + 2 * v["t"], v["W"] + 2 * v["t"]      # the coaming's outside
        a, b = (it[n]["x"] for n in c["capstan"]["between"])
        self.x_capstan = 0.5 * (a + b)
        wh = c["wheel"]
        self.x_wheel = wh["x_m"]
        # the binnacle: its after face gap_to_wheel_m forward of the fore wheel's nave
        fwd = self.x_wheel + (wh["between_wheels_in"] / 2 + wh["nave_in"][1] / 2) * IN
        bs = c["binnacle"]["size_in"]
        self.x_binnacle = fwd + c["binnacle"]["gap_to_wheel_m"] + bs[0] / 2 * IN
        # the waist: its opening square-sided, the gangways at least gangway_width_ft wide
        xs = np.linspace(self.e1, self.fc, 200)
        self.y_open = float(np.min(self.y_side(xs)) - c["deck"]["gangway_width_ft"] * FT)
        wa = c["waist"]
        self.t_coam = wa["coaming_thick_in"] * IN
        self.beam_pitch = (self.fc - self.e1) / (2 * (wa["beams"] + 1))
        self.info["layout"] = {k: {"x_m": round(v["x"], 3), "inside_m": [round(v["L"], 3), round(v["W"], 3)]}
                               for k, v in it.items()}
        self.info["layout"].update({"Capstan": {"x_m": round(self.x_capstan, 3)},
                                    "Wheel": {"x_m": round(self.x_wheel, 3)},
                                    "Binnacle": {"x_m": round(self.x_binnacle, 3)}})
        self.info["waist"] = {"x_m": [round(self.e1, 3), round(self.fc, 3)], "half_width_m": round(self.y_open, 3),
                              "beam_pitch_m": round(self.beam_pitch, 4)}
        return self

    def footprints(self):
        """every fitting's plan outline (name -> (n, 2)) for the layout check"""
        fp = {}
        for k, v in self.items.items():
            fp[k] = rect2(v["x"], 0.0, v["Lo"], v["Wo"])
        cs = self.c["capstan"]
        fp["Capstan"] = circle(cs["drumhead_diam_in"] / 2 * IN, 32) + [self.x_capstan, 0.0]
        wh = self.c["wheel"]
        r = (wh["rim_diam_in"] / 2 + wh["handle_out_in"]) * IN
        half = (wh["between_wheels_in"] / 2 + wh["nave_in"][1] / 2) * IN
        fp["Wheel"] = rect2(self.x_wheel, 0.0, 2 * half, 2 * r)
        bs = self.c["binnacle"]["size_in"]
        fp["Binnacle"] = rect2(self.x_binnacle, 0.0, bs[0] * IN, bs[1] * IN)
        for name in ("fore", "main", "mizzen"):
            p, R, _ = self.mast_at(name, float(self.z(self.rig.masts[name]["O"][0])))
            fp["Mast_" + name] = circle(R + self.c["mast_coats"]["out_in"] * IN, 24) + p[:2]
        return fp

    def layout_check(self, extra=None, gap=0.15):
        """the least room in plan between every two fittings (and the fife rails, extra: name -> outline): a list of
        pairs closer than gap"""
        fp = dict(self.footprints(), **(extra or {}))
        names = list(fp)
        close = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                A, B = fp[a], fp[b]
                if in_poly(A, B).any() or in_poly(B, A).any():
                    d = 0.0
                else:
                    d = float(min(seg_dist(A, B).min(), seg_dist(B, A).min()))
                if d < gap:
                    close.append([a, b, round(d, 3)])
        return close

    # --- the deck itself ------------------------------------------------------------------------------------------------
    def holes(self):
        """the openings through the deck: [(name, top outline, underside outline, walls)], each outline (n, 2)
        counter-clockwise; walls: True where the deck's edge shows (the masts, the capstan's barrel), a list of the
        top outline's runs that show for the waist (its ends), else False (a coaming stands in it)"""
        out = []
        yo, t = self.y_open, self.t_coam
        e1, fc = self.e1, self.fc
        # the waist: its corners and the coaming's edges at each end, every 0.2 m
        ring = np.array([[e1, -(yo + t)], [e1, -yo], [e1, yo], [e1, yo + t], [fc, yo + t], [fc, yo], [fc, -yo],
                         [fc, -(yo + t)]])
        P = densify(ring[[0, 7, 6, 5, 4, 3, 2, 1]], 0.2)       # counter-clockwise from the aft starboard... corner
        out.append(("Waist", P, P.copy(), "ends"))
        g = self.c["deck"]["mast_hole_gap_in"] * IN
        for name in ("fore", "main", "mizzen"):
            m = self.rig.masts[name]
            xt = float(m["O"][0])
            for _ in range(3):
                pt, R, u = self.mast_at(name, float(self.z(xt)))
                xt = pt[0]
            pb, _, _ = self.mast_at(name, float(self.zu(xt)))
            a, b = (R + g) / u[2], R + g
            th = np.linspace(0, 2 * math.pi, 32, endpoint=False)
            E = np.stack([a * np.cos(th), b * np.sin(th)], 1)
            out.append(("Mast_" + name, E + pt[:2], E + pb[:2], True))
        cs = self.c["capstan"]
        rb = (cs["barrel_diam_in"][1] / 2 + self.c["deck"]["mast_hole_gap_in"]) * IN
        C = circle(rb, 24) + [self.x_capstan, 0.0]
        out.append(("Capstan", C, C.copy(), True))
        for k, v in self.items.items():
            R = densify(rect2(v["x"], 0.0, v["Lo"], v["Wo"]), 0.2)
            out.append((k, R, R.copy(), False))
        return out

    def pockets(self):
        """recesses in the deck's top: the bowsprit's heel is let into it [(name, outline (n, 2), floor z)]"""
        bs = self.rig.bs
        H, ub, up = (np.asarray(bs[k], float) for k in ("H", "ub", "up"))
        side = np.cross(ub, up)
        th = np.linspace(0, 2 * math.pi, 96, endpoint=False)
        pts = []
        for s in np.linspace(0.0, 1.0, 41):
            r = float(bs["R"](s))
            pts.append(H + s * ub + r * (np.cos(th)[:, None] * up + np.sin(th)[:, None] * side))
        r0 = float(bs["R"](0.0))
        for rr in np.linspace(0.0, r0, 12):                    # the heel's end
            pts.append(H + rr * (np.cos(th)[:, None] * up + np.sin(th)[:, None] * side))
        Q = np.concatenate(pts)
        under = Q[Q[:, 2] < self.z(Q[:, 0]) + 0.004]
        if not len(under):
            return []
        m = 0.012
        x0, x1 = under[:, 0].min() - m, under[:, 0].max() + m
        y1 = np.abs(under[:, 1]).max() + m
        floor = float((under[:, 2] - 0.0).min()) - 0.006
        self.info["bowsprit_heel_pocket"] = {"x_m": [round(x0, 3), round(x1, 3)], "half_width_m": round(y1, 3),
                                             "depth_below_deck_m": round(float(self.z(0.5 * (x0 + x1))) - floor, 3),
                                             "note": "the bowsprit's heel stands that far into the deck's top (the "
                                                     "deck at the bulwark is higher than the rig's deck line at the "
                                                     "bow's flare): it is let into a recess"}
        return [("BowspritHeel", densify(rect2(0.5 * (x0 + x1), 0.0, x1 - x0, 2 * y1), 0.05), floor)]

    def surface(self, part):
        """the deck's top (planked: UV 'Planking'), its underside, and the walls of its openings"""
        holes = self.holes()
        pockets = self.pockets()
        # the top: the bulwark's foot along both sides, across at the ends
        T = self.top
        stb = T[:, :2]
        port = (T[::-1, :2] * [1.0, -1.0])
        aft = densify(np.array([port[-1], stb[0]]), 0.3, closed=False)[1:-1]
        fwd = densify(np.array([stb[-1], port[0]]), 0.3, closed=False)[1:-1]
        outline = np.concatenate([stb, fwd, port, aft])
        zo = np.concatenate([T[:, 2], self.z(fwd[:, 0]), T[::-1, 2], self.z(aft[:, 0])])
        tops = [h[1] for h in holes] + [p[1] for p in pockets]
        P2, Tt = cdt(outline, tops, self.c["deck"].get("mesh_step_m", 0.3))
        Z = self.z(P2[:, 0])
        Z[:len(outline)] = zo
        V = np.column_stack([P2, Z])
        part.add(V, [tuple(t) for t in Tt], "DeckPlanks", uv=np.column_stack([P2, self.margin_uv(P2)]))
        self.info["deck"] = {"top_triangles": len(Tt), "area_m2": round(float(0.5 * np.abs(
            (P2[Tt[:, 1], 0] - P2[Tt[:, 0], 0]) * (P2[Tt[:, 2], 1] - P2[Tt[:, 0], 1]) -
            (P2[Tt[:, 1], 1] - P2[Tt[:, 0], 1]) * (P2[Tt[:, 2], 0] - P2[Tt[:, 0], 0])).sum()), 1)}
        # the underside
        U = self.und
        stb = U[:, :2]
        port = (U[::-1, :2] * [1.0, -1.0])
        aft = densify(np.array([port[-1], stb[0]]), 0.3, closed=False)[1:-1]
        fwd = densify(np.array([stb[-1], port[0]]), 0.3, closed=False)[1:-1]
        outline = np.concatenate([stb, fwd, port, aft])
        zo = np.concatenate([U[:, 2], self.zu(fwd[:, 0]), U[::-1, 2], self.zu(aft[:, 0])])
        P2, Tu = cdt(outline, [h[2] for h in holes], 0.5)
        Z = self.zu(P2[:, 0])
        Z[:len(outline)] = zo
        part.add(np.column_stack([P2, Z]), [tuple(t[::-1]) for t in Tu], "Interior")
        # the openings' walls
        for name, top, und, walls in holes:
            if walls is False:
                continue
            A = np.column_stack([top, self.z(top[:, 0])])
            B = np.column_stack([und, self.zu(und[:, 0])])
            if walls is True:
                A, B = np.concatenate([A, A[:1]]), np.concatenate([B, B[:1]])
                n = len(A)
                V = np.concatenate([A, B])
                F = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
                c2 = top.mean(0)
                want = np.array([c2[0] - A[0, 0], c2[1] - A[0, 1], 0.0])
                f0 = F[0]
                nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
                if nrm @ want < 0:
                    F = [f[::-1] for f in F]
                part.add(V, F, "Deck")
            else:                                          # the waist's ends: the breast beams' faces
                for xe, want in ((self.e1, EX), (self.fc, -EX)):
                    sel = (np.abs(top[:, 0] - xe) < 1e-9) & (np.abs(top[:, 1]) <= self.y_open + 1e-9)
                    o = np.argsort(top[sel, 1])
                    strip(part, A[sel][o], B[sel][o], "Deck", want)
        for name, outline, floor in pockets:
            A = np.column_stack([outline, self.z(outline[:, 0])])
            B = np.column_stack([outline, np.full(len(outline), floor)])
            n = len(A)
            V = np.concatenate([A, B])
            F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
            c3 = np.array([*outline.mean(0), floor])
            nrm = np.cross(V[F[0][1]] - V[F[0][0]], V[F[0][3]] - V[F[0][0]])
            if nrm @ (c3 - V[0]) < 0:
                F = [f[::-1] for f in F]
            part.add(V, F, "Deck")
            Fl = [(n + 0, n + i, n + i + 1) for i in range(1, n - 1)]
            # no slivers where the outline runs straight on through its first corner
            Fl = [f for f in Fl if np.linalg.norm(np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])) > 1e-8]
            if newell(B) @ EZ < 0:
                Fl = [f[::-1] for f in Fl]
            part.add(V, Fl, "Deck")

    # --- along the sides ------------------------------------------------------------------------------------------------
    def waterway_stations(self):
        """the x stations the waterway is built at (both sides), from the stern to where the half-breadth falls to
        0.4 m at the bow"""
        T = self.top
        i = int(np.nonzero(T[:, 1] >= 0.4)[0].max())               # where the half-breadth falls to 0.4 m at the bow
        x_end = float(T[i, 0]) if i + 1 >= len(T) else float(
            np.interp(0.4, [T[i + 1, 1], T[i, 1]], [T[i + 1, 0], T[i, 0]]))
        xs = T[:, 0]
        return np.unique(np.concatenate([xs[(xs > xs[0] + 0.02) & (xs < x_end)][::2], [xs[0] - 0.01, x_end]]))

    def waterway_edge(self):
        """the waterway's inner edge (starboard) along the ship: (x, y) points, and its half-breadth and slope at any x
        (the deck's 'Margin' UV for the nibs)"""
        if getattr(self, "_ww_edge", None) is None:
            prof = np.array(self.c["deck"]["waterway"]["profile_in"], float) * IN
            E = []
            for x in self.waterway_stations():
                P0, n = self.face(x, 0.0)
                E.append(P0 + n * min(prof[-1, 0], P0[1] - 0.004))
            E = np.array(E)[:, :2]
            E = E[np.argsort(E[:, 0])]
            self._ww_edge = (E, np.gradient(E[:, 1], E[:, 0]))
        return self._ww_edge

    def margin_uv(self, P2):
        """the 'Margin' UV at plan points P2 (n, 2): the waterway's inner edge's half-breadth less |y|, and how fast it
        changes along x"""
        E, dE = self.waterway_edge()
        x = np.clip(P2[:, 0], E[0, 0], E[-1, 0])
        return np.column_stack([np.interp(x, E[:, 0], E[:, 1]) - np.abs(P2[:, 1]), np.abs(np.interp(x, E[:, 0], dE))])

    def waterways(self, part):
        """the waterway along each side: its hollowed face from the bulwark's foot to the deck, let into both; in the
        waist (open above the plankshear) it stops just under the plankshear's top"""
        ww = self.c["deck"]["waterway"]
        prof = np.array(ww["profile_in"], float) * IN
        let = ww["let_in_in"] * IN
        h0 = prof[0, 1]
        xs = self.waterway_stations()
        zp = np.interp(xs, self.psh[:, 0], self.psh[:, 2])
        rings = []
        for x, zpp in zip(xs, zp):
            open_ = self.e0 - 1e-6 < x < self.fc + 1e-6
            sc = min(1.0, (zpp - float(self.z(x)) - 0.1 * IN) / h0) if open_ else 1.0
            P0, n = self.face(x, 0.0)
            P1, _ = self.face(x, h0 * sc)
            w_max = P0[1] - 0.004
            ring = [P0 - n * 0.25 * IN - EZ * let, P1 - n * 0.25 * IN]
            for w, h in prof:
                # each point is laid in from the face at its height, so it follows the bulwark's tumblehome (15 deg in
                # the waist) instead of standing plumb over the foot and inside the bulwark
                ring.append(P0 + (P1 - P0) * (h / h0) + n * min(w, w_max))
            ring.append(P0 + n * min(prof[-1, 0], w_max) - EZ * let)
            ring = np.array(ring)
            # each point over the deck where it stands: where the side turns in at the bow the inner edge stands
            # further aft than the foot, lower on the sheer
            ring[:, 2] += self.z(ring[:, 0]) - float(self.z(x))
            rings.append(ring)
        for sgn in (1.0, -1.0):
            f = np.array([1.0, sgn, 1.0])
            solid(part, [r * f for r in rings], "Oak")

    # --- the waist ------------------------------------------------------------------------------------------------------
    def waist(self, part, end=None):
        """the coamings along the gangways' inner edges, and the beams across the open waist, carried on under the
        gangways to the gun deck's side: their tops at the spar deck's underside (as the gun deck's own beams,
        gundeck.py), their undersides on the gun deck's clamp. end(x0, x1, z): how far out a beam spanning x0..x1 may
        reach at height z (the side's inner face, less a hair); the gun deck gives it (rebuild_waist), so each end is
        cut to the side as it leans; without it, the deck's underside row less 5 mm"""
        wa = self.c["waist"]
        yo, t = self.y_open, self.t_coam
        hi = wa["coaming_high_in"] * IN
        xs = np.linspace(self.e1, self.fc, 41)
        for sgn in (1.0, -1.0):
            rings = []
            for x in xs:
                zt, zb = float(self.z(x)), float(self.zu(x))
                rings.append(np.array([[x, sgn * yo, zb], [x, sgn * (yo + t), zb], [x, sgn * (yo + t), zt + hi],
                                       [x, sgn * yo, zt + hi]]))
            solid(part, rings, "Oak")
        sided = wa["beam_sided_in"] * IN
        self.beams_x = []
        for k in range(1, wa["beams"] + 1):
            x = self.e1 + 2 * k * self.beam_pitch
            x0, x1 = x - sided / 2, x + sided / 2
            rings = []
            for xx in (x0, x1):
                # each face at its own height: the beam follows the sheer along its siding, as the gun deck's own beams
                # do, so its top lies on the planks' underside and its underside on the clamp across all 14 in (laid
                # level, the forward beams stood up to 0.28 in off both at one face)
                ztop, zbot = self.waist_beam_z(xx)
                if end is None:
                    yt = yb = float(min(np.interp(xe, self.und[:, 0], self.und[:, 1]) for xe in (x0, x1))) - 0.005
                else:
                    yt, yb = end(x0, x1, ztop), end(x0, x1, zbot)
                rings.append(np.array([[xx, -yb, zbot], [xx, yb, zbot], [xx, yt, ztop], [xx, -yt, ztop]]))
            solid(part, rings, "Oak")
            self.beams_x.append(round(x, 4))

    def waist_beam_z(self, x):
        """a waist beam's top (the spar deck's underside) and underside at x"""
        top = float(self.zu(x))
        return top, top - self.c["waist"]["beam_moulded_in"] * IN

    def rebuild_waist(self, end):
        """the waist's coamings and beams made again, each beam's ends cut to the side by end (waist's): the gun deck
        (gundeck.py) calls this once it knows where its side's inner face is"""
        P = Part()
        self.waist(P, end)
        self.parts_["WaistFrame"] = P

    def ladder_gaps(self):
        lc = self.c["ladders"]
        yc = lc["y_ft"] * FT
        half = (lc["width_in"] / 2 + lc["stringer_in"][1]) * IN + 0.05
        return [(-yc - half, -yc + half), (yc - half, yc + half)]

    def breast_rails(self, part):
        """a rail on turned balusters across each break, at the opening's end, with a gap at each ladder; in the
        forecastle's the belfry's posts stand in it (its runs end on them, and a short run between them)"""
        br = self.c["breast_rails"]
        H = br["height_in"] * IN
        cw, ct = (v * IN for v in br["cap_in"])
        fw, ft = (v * IN for v in br["foot_in"])
        ps = br["post_in"] * IN
        bmax = br["baluster_max_in"] * IN / 2
        pitch = br["baluster_pitch_in"] * IN
        bf = self.c["belfry"]
        bp = bf["posts_apart_in"] / 2 * IN
        bpost = bf["post_in"] * IN
        prof = [(0.0, 0.55), (0.06, 0.55), (0.1, 0.42), (0.3, 1.0), (0.45, 0.62), (0.6, 0.38), (0.85, 0.42),
                (0.92, 0.6), (1.0, 0.6)]
        self.breast_x = {}
        for name, xe, sgn in (("quarterdeck", self.e1, -1.0), ("forecastle", self.fc, 1.0)):
            xb = xe + sgn * (cw / 2 + 1.0 * IN)
            self.breast_x[name] = xb
            zd = float(self.z(xb))
            k0 = len(part.V)
            cuts = list(self.ladder_gaps())
            if name == "forecastle":
                cuts.append((-bp - bpost / 2, bp + bpost / 2))
            runs, lo = [], -self.y_open + ps / 2 + 0.01
            for a, b in sorted(cuts):
                runs.append([lo, a])
                lo = b
            runs.append([lo, self.y_open - ps / 2 - 0.01])
            # a post at each end of a run, except where it ends on one of the belfry's posts
            on_belfry = (lambda y: name == "forecastle" and abs(abs(y) - (bp + bpost / 2)) < 1e-6)  # noqa: E731
            runs = [(a - (0.5 * IN if on_belfry(a) else 0.0), b + (0.5 * IN if on_belfry(b) else 0.0),
                     not on_belfry(a), not on_belfry(b)) for a, b in runs]
            if name == "forecastle":                       # into the belfry's posts half an inch
                runs.append((-bp + bpost / 2 - 0.5 * IN, bp - bpost / 2 + 0.5 * IN, False, False))
            for a, b, post_a, post_b in runs:
                if b - a < 0.2:
                    continue
                vbox(part, [xb - fw / 2, a, zd - 0.2 * IN], [xb + fw / 2, b, zd + ft], "Rail")
                vbox(part, [xb - cw / 2, a, zd + H - ct], [xb + cw / 2, b, zd + H], "Rail")
                for y, has in ((a, post_a), (b, post_b)):
                    if not has:
                        continue
                    vbox(part, [xb - ps / 2, y - ps / 2, zd - 0.2 * IN], [xb + ps / 2, y + ps / 2, zd + H + 1.5 * IN],
                         "Rail")
                    lathe(part, [xb, y, zd + H + 1.5 * IN], EZ, EX, [(0.0, 0.42 * ps), (0.6 * IN, 0.5 * ps),
                                                                    (1.8 * IN, 0.38 * ps), (2.6 * IN, 0.12 * ps)],
                          "Rail", 8)
                # the balusters between the posts (or the belfry's)
                y0 = a + (ps / 2 if post_a else 0.5 * IN)
                y1 = b - (ps / 2 if post_b else 0.5 * IN)
                n = max(1, int((y1 - y0) // pitch))
                hb = H - ct - ft
                for k in range(n):
                    y = y0 + (k + 0.5) * (y1 - y0) / n
                    lathe(part, [xb, y, zd + ft - 0.1 * IN], EZ, EX, [(f * (hb + 0.2 * IN), r * bmax) for f, r in prof],
                          "Rail", 8)
            self.seat(part, k0, zd - 0.2 * IN, 0.2 * IN)               # the feet follow the deck's sheer under them

    def ladders(self, part):
        """four ladders down to the gun deck in the waist, two at each break"""
        lc = self.c["ladders"]
        yc = lc["y_ft"] * FT
        wi = lc["width_in"] * IN
        sd, st = (v * IN for v in lc["stringer_in"])
        td, tt = (v * IN for v in lc["tread_in"])
        rise = lc["rise_in"] * IN
        ang = math.radians(lc["angle_deg"])
        rh = lc["rail_high_in"] * IN
        self.ladder_info = []
        for name, xe, d in (("quarterdeck", self.e1, 1.0), ("forecastle", self.fc, -1.0)):
            zt = float(self.z(xe))
            for _ in range(3):                                  # the foot on the gun deck
                xf = xe + d * (zt - float(self.zg(xe + d * 1.2))) / math.tan(ang)
                zf = float(self.zg(xf))
                xf = xe + d * (zt - zf) / math.tan(ang)
            drop = zt - zf
            for sy in (1.0, -1.0):
                y0 = sy * yc
                # the stringers: their centre line from the deck's edge (its top at the deck's top) to the gun deck,
                # the top end cut square against the deck's edge, the foot cut level on the gun deck
                for side in (-1.0, 1.0):
                    yy = y0 + side * (wi / 2 + st / 2)
                    T = np.array([xe, zt - 0.5 * IN])
                    F_ = np.array([xf, zf])
                    a = unit(F_ - T)
                    nrm = np.array([-a[1], a[0]])
                    if nrm[1] < 0:
                        nrm = -nrm
                    ext = 0.5
                    P = np.array([T - a * ext + nrm * sd / 2, F_ + a * ext + nrm * sd / 2, F_ + a * ext - nrm * sd / 2,
                                  T - a * ext - nrm * sd / 2])
                    # clip: x on the waist's side of the deck's edge, z above the gun deck, top no higher than the deck
                    C = np.array([[xe + d * 0.1 * IN, zf - 0.2 * IN], [xe + d * 5.0, zf - 0.2 * IN],
                                  [xe + d * 5.0, zt], [xe + d * 0.1 * IN, zt]])
                    Q = clip_convex(P, C)
                    ring0 = np.column_stack([Q[:, 0], np.full(len(Q), yy - st / 2), Q[:, 1]])
                    ring1 = ring0 + [0.0, st, 0.0]
                    solid(part, [ring0, ring1], "Rail")
                # the treads, level, every rise down from the deck
                n = int(round(drop / rise))
                rr = drop / n
                for k in range(1, n):
                    z = zt - k * rr
                    x = xe + d * (zt - z) / math.tan(ang)
                    vbox(part, [x - td / 2, y0 - wi / 2 - 0.4 * IN, z - tt], [x + td / 2, y0 + wi / 2 + 0.4 * IN, z],
                         "Rail")
                # the hand ropes on iron stanchions along each stringer's outside
                for side in (-1.0, 1.0):
                    yy = y0 + side * (wi / 2 + st + 0.6 * IN)
                    tops = []
                    for f in (0.12, 0.5, 0.88):
                        z = zt - f * drop
                        x = xe + d * (zt - z) / math.tan(ang)
                        zs = z + 0.6 * sd                          # on the stringer's top edge
                        tube(part, np.array([[x, yy, zs - 0.03], [x, yy, zs + rh]]), 0.4 * IN, "Iron", 6)
                        tops.append([x, yy, zs + rh])
                    # made fast at the top to an eyebolt in the breast rail's post at the gap's edge (its face toward
                    # the waist), whose round iron plate stands a little proud of the post
                    xp = self.breast_x[name] + d * self.c["breast_rails"]["post_in"] / 2 * IN
                    zr = zt + rh * 0.95
                    lathe(part, [xp - d * 0.1 * IN, yy, zr], d * EX, EZ, [(0.0, 1.0 * IN), (0.5 * IN, 1.0 * IN),
                                                                         (0.7 * IN, 0.6 * IN)], "Iron", 10)
                    P = np.array([[xp + d * 0.3 * IN, yy, zr]] + tops + [[xf + d * 0.05, yy, zf + rh * 0.8]])
                    tube(part, P, 0.75 * IN, "Hemp", 6)
                self.ladder_info.append({"break": name, "y_m": round(y0, 3), "top_x_m": round(xe, 3),
                                         "foot_x_m": round(xf, 3), "drop_m": round(drop, 3), "treads": n - 1})

    # --- hatchways, companion, skylights, chimney -------------------------------------------------------------------------
    def coaming(self, part, v, high=None, mat="Oak"):
        """a coaming round an opening: its inside the opening, its outside the deck's hole, from the underside up"""
        high = v["high"] if high is None else high
        x0, L, W, t = v["x"], v["L"], v["W"], v["t"]
        xs = [x0 - L / 2 - t, x0 - L / 2, x0 + L / 2, x0 + L / 2 + t]
        ys = [-W / 2 - t, -W / 2, W / 2, W / 2 + t]
        zt = lambda x: float(self.z(x)) + high          # noqa: E731
        zb = lambda x: float(self.zu(x)) - 0.01         # noqa: E731
        # four sides as boxes that follow the deck's sheer: aft, fore (full width), and the two sides between
        for xa, xb_ in ((xs[0], xs[1]), (xs[2], xs[3])):
            rings = [np.array([[x, ys[0], zb(x)], [x, ys[3], zb(x)], [x, ys[3], zt(x)], [x, ys[0], zt(x)]])
                     for x in (xa, xb_)]
            solid(part, rings, mat)
        for ya, yb in ((ys[0], ys[1]), (ys[2], ys[3])):
            xx = np.linspace(xs[1], xs[2], 5)
            rings = [np.array([[x, ya, zb(x)], [x, yb, zb(x)], [x, yb, zt(x)], [x, ya, zt(x)]]) for x in xx]
            solid(part, rings, mat)
        return zt

    def grating(self, part, v, zt):
        """a fair-weather grating in a hatchway's coaming: ledges fore and aft, battens across, halved together, its
        top cambered athwartships"""
        g = self.c["hatchways"]["grating"]
        hole, b = g["hole_in"] * IN, g["bar_in"] * IN
        dl, db = g["ledge_deep_in"] * IN, g["batten_deep_in"] * IN
        cam = g["camber_in"] * IN
        under = g["under_top_in"] * IN
        x0, L, W = v["x"], v["L"] - 0.2 * IN, v["W"] - 0.2 * IN
        us, ubar = bars_and_gaps(-L / 2, L / 2, b, hole)        # the battens (across) at these x
        vs, vbar = bars_and_gaps(-W / 2, W / 2, b, hole)        # the ledges (fore and aft) at these y
        D = np.zeros((len(us) - 1, len(vs) - 1))
        for i in range(D.shape[0]):
            for j in range(D.shape[1]):
                D[i, j] = dl if vbar[j] else (db if ubar[i] else 0.0)
        P = lambda u, w: np.array([x0 + u, w, zt(x0 + u) - under + cam * (1 - (2 * w / W) ** 2)])  # noqa: E731
        N = lambda u, w: EZ                                       # noqa: E731
        cell_solid(part, us, vs, D, P, N, "Oak")

    def hatches(self, part):
        for k, v in self.items.items():
            if v["kind"] == "hatch":
                zt = self.coaming(part, v)
                self.grating(part, v, zt)

    def companion(self, part):
        """the companion: its coaming and a hood over it, the roof sloping aft, two doors in its forward face"""
        cp = self.c["companion"]
        v = self.items["Companion"]
        self.coaming(part, v)
        x0, Lo, Wo = v["x"], v["Lo"], v["Wo"]
        hf, ha = (h * IN for h in cp["hood_high_in"])
        dw, dh = (d * IN for d in cp["door_in"])
        xa, xf = x0 - Lo / 2, x0 + Lo / 2
        rec = 1.0 * IN
        za = lambda x: float(self.z(x)) + v["high"]                       # noqa: E731
        zr = lambda x: float(self.z(x)) + ha + (hf - ha) * (x - xa) / (xf - xa)   # noqa: E731
        # the hood's body (behind the door frame) and the frame round the doors
        rings = [np.array([[x, -Wo / 2, za(x)], [x, Wo / 2, za(x)], [x, Wo / 2, zr(x)], [x, -Wo / 2, zr(x)]])
                 for x in (xa, xf - rec)]
        solid(part, rings, "Oak")
        zdt = za(xf) + dh
        for ya, yb in ((-Wo / 2, -dw / 2), (dw / 2, Wo / 2)):
            vbox(part, [xf - rec, ya, za(xf)], [xf, yb, zr(xf) - 0.1 * IN], "Oak")
        vbox(part, [xf - rec, -dw / 2, zdt], [xf, dw / 2, zr(xf) - 0.1 * IN], "Oak")
        # the doors: the split between the leaves and their knobs
        vbox(part, [xf - rec - 0.05 * IN, -0.15 * IN, za(xf) + 0.5 * IN], [xf - rec + 0.08 * IN, 0.15 * IN, zdt - 0.5 * IN],
             "Shadow")
        for sy in (-1.0, 1.0):
            lathe(part, [xf - rec, sy * 1.6 * IN, za(xf) + 0.55 * dh], EX, EZ,
                  [(0.0, 0.25 * IN), (0.5 * IN, 0.2 * IN), (0.9 * IN, 0.55 * IN), (1.3 * IN, 0.3 * IN)], "Bronze", 8)
        # the roof: boards over the hood with an overhang, arched athwartships
        ov, rt, arch = 1.5 * IN, 1.25 * IN, 1.5 * IN
        ys = np.linspace(-Wo / 2 - ov, Wo / 2 + ov, 9)
        xs = np.array([xa - ov, xf + ov])
        D = np.full((1, len(ys) - 1), rt)
        P = lambda u, w: np.array([u, w, zr(min(max(u, xa), xf)) + (zr(xf) - zr(xa)) / (xf - xa) * (  # noqa: E731
            u - min(max(u, xa), xf)) + rt + arch * (1 - (2 * w / (Wo + 2 * ov)) ** 2)])
        slope = (hf - ha) / (xf - xa)
        N = lambda u, w: unit(np.array([-slope, 0.0, 1.0]))            # noqa: E731
        cell_solid(part, xs, ys, D, P, N, "Oak")

    def skylights(self, part):
        """each skylight: its coaming and a pitched roof of two glazed lids (the ridge athwartships), each lid a frame
        round its panes with iron guard bars over the glass, the gable ends boarded"""
        sl = self.c["skylights"]
        rid = sl["ridge_in"] * IN
        fw, ft = 2.0 * IN, 1.5 * IN
        mw = 1.0 * IN
        for k, v in self.items.items():
            if v["kind"] != "skylight":
                continue
            zt = self.coaming(part, v)
            x0, Lo, Wo = v["x"], v["Lo"], v["Wo"]
            zc = zt(x0)
            for sx in (-1.0, 1.0):                             # each lid from its eave to the ridge
                eave = np.array([x0 + sx * Lo / 2, 0.0, zt(x0 + sx * Lo / 2)])
                ridge = np.array([x0, 0.0, zc + rid])
                S = float(np.linalg.norm(ridge - eave))
                dirn = (ridge - eave) / S
                nrm = unit(np.array([sx * rid, 0.0, Lo / 2]))
                us = np.array([0.0, fw, S - fw / 2, S])
                n_p = sl["panes"]
                ys = [-Wo / 2, -Wo / 2 + fw]
                pane = (Wo - 2 * fw - (n_p - 1) * mw) / n_p
                for p in range(n_p):
                    ys.append(ys[-1] + pane)
                    if p < n_p - 1:
                        ys.append(ys[-1] + mw)
                ys.append(Wo / 2)
                ys = np.array(ys)
                D = np.full((len(us) - 1, len(ys) - 1), ft)
                for j in range(1, len(ys) - 2, 2):
                    D[1, j] = 0.0
                P = lambda u, w, e=eave, dd=dirn, n_=nrm: e + u * dd + w * EY + n_ * ft      # noqa: E731
                N = lambda u, w, n_=nrm: n_                                            # noqa: E731
                cell_solid(part, us, ys, D, P, N, "Oak")
                # the glass, set half an inch under the frame's top
                for j in range(1, len(ys) - 2, 2):
                    a = eave + us[1] * dirn + nrm * (ft - 0.5 * IN)
                    b = eave + us[2] * dirn + nrm * (ft - 0.5 * IN)
                    Q = np.array([a + ys[j] * EY, b + ys[j] * EY, b + ys[j + 1] * EY, a + ys[j + 1] * EY])
                    F = [(0, 1, 2, 3)]
                    if np.cross(Q[1] - Q[0], Q[3] - Q[0]) @ nrm < 0:
                        F = [(3, 2, 1, 0)]
                    part.add(Q, F, "ClearGlass")
                # guard bars down the slope over the panes
                nb = sl["bars"]
                for y in np.linspace(-Wo / 2 + fw + 0.6 * pane / 2, Wo / 2 - fw - 0.6 * pane / 2, nb):
                    a = eave + (fw * 0.5) * dirn + nrm * (ft + 0.5 * IN) + y * EY
                    b = eave + (S - fw * 0.75) * dirn + nrm * (ft + 0.5 * IN) + y * EY
                    # (each leg into the frame long enough to bend round on more than the bar's own radius)
                    tube(part, fillet(np.array([a - nrm * 1.0 * IN, a, b, b - nrm * 1.0 * IN]), 0.4 * IN), 0.25 * IN,
                         "Iron", 6)
            # the gable ends and the ridge board
            for sy in (-1.0, 1.0):
                y = sy * (Wo / 2 - 0.3 * IN)
                tri = np.array([[x0 - Lo / 2 + 0.3 * IN, y, zt(x0 - Lo / 2) - 0.1 * IN],
                                [x0 + Lo / 2 - 0.3 * IN, y, zt(x0 + Lo / 2) - 0.1 * IN], [x0, y, zc + rid + 0.5 * ft]])
                solid(part, [tri, tri + [0.0, -sy * 1.0 * IN, 0.0]], "Oak")
            vbox(part, [x0 - 1.0 * IN, -Wo / 2 - 0.5 * IN, zc + rid + ft - 0.5 * IN],
                 [x0 + 1.0 * IN, Wo / 2 + 0.5 * IN, zc + rid + ft + 1.5 * IN], "Oak")

    def chimney(self, part):
        """the galley's funnel: a coaming, an iron plate over it, the funnel and its cowl turned aft"""
        ch = self.c["chimney"]
        v = self.items["Chimney"]
        zt = self.coaming(part, v)
        x0, L, W = v["x"], v["L"], v["W"]
        pt = 0.5 * IN
        lap = 1.5 * IN                                         # the plate laps onto the coaming's top
        rings = [np.array([[x, -W / 2 - lap, zt(x) - 0.05 * IN], [x, W / 2 + lap, zt(x) - 0.05 * IN],
                           [x, W / 2 + lap, zt(x) + pt], [x, -W / 2 - lap, zt(x) + pt]])
                 for x in (x0 - L / 2 - lap, x0 + L / 2 + lap)]
        solid(part, rings, "Iron")
        r = ch["funnel_in"] / 2 * IN
        hs = ch["funnel_high_in"] * IN
        bend = ch["cowl_bend_in"] * IN
        zb = zt(x0) + pt
        # a flange at the foot with a collar round the funnel (proud of it, so no face of it lies on the funnel's), the
        # straight funnel, the bend aft and the flared mouth, open, dark inside
        lathe(part, [x0, 0.0, zb - 0.1 * IN], EZ, EX, [(0.0, r + 1.5 * IN), (0.6 * IN, r + 1.5 * IN),
                                                         (0.6 * IN, r + 0.25 * IN), (1.4 * IN, r + 0.25 * IN)], "Iron", 24)
        path = [np.array([x0, 0.0, zb]), np.array([x0, 0.0, zb + hs])]
        for a in np.linspace(0, math.pi / 2, 13)[1:]:
            path.append(np.array([x0 - bend + bend * math.cos(a), 0.0, zb + hs + bend * math.sin(a)]))
        end = np.array([x0 - bend - 4.0 * IN, 0.0, zb + hs + bend])
        path.append(end)
        tube(part, np.array(path), r, "Iron", 24)
        t = 0.2 * IN                                           # the mouth's plate
        lip = [(0.0, r), (1.0 * IN, r + 0.25 * IN), (2.0 * IN, r + 0.9 * IN), (2.8 * IN, r + 1.9 * IN),
               (3.3 * IN, r + 2.6 * IN)]
        o_m = end - EX * 0.1 * IN
        revolve(part, o_m, -EX, EZ, lip, "Iron", 24, want_out=True)
        revolve(part, o_m, -EX, EZ, [(h, rr - t) for h, rr in lip], "Iron", 24, want_out=False)
        h1, r1 = lip[-1]
        revolve(part, o_m, -EX, EZ, [(h1, r1 - t), (h1, r1)], "Iron", 24, want_out=True)    # the rim
        disc = np.array([end - EX * 0.3 * IN + (r - t) * (math.cos(a) * EY + math.sin(a) * EZ)
                         for a in np.arange(24) * 2 * math.pi / 24])
        F = [tuple(range(24))]
        if newell(disc) @ (-EX) < 0:
            F = [tuple(reversed(range(24)))]
        part.add(disc, F, "Shadow")
        self.info["chimney_top_z_m"] = round(float(zb + hs + bend + r), 3)

    # --- the capstan's head -----------------------------------------------------------------------------------------------
    def capstan(self, part, pawls):
        """the main capstan's head, in its own frame (origin on its axis at the deck's top, Z up): the barrel down
        through the deck, eight whelps, the drumhead with its bar holes and iron hoops; the pawl ring on the deck (pawls,
        built in place: it doesn't turn)"""
        cs = self.c["capstan"]
        x0 = self.x_capstan
        z0 = float(self.z(x0))
        R = cs["drumhead_diam_in"] / 2 * IN
        Td = cs["drumhead_thick_in"] * IN
        Ht = cs["top_high_in"] * IN
        rb = cs["barrel_diam_in"][1] / 2 * IN
        rt = cs["barrel_diam_in"][0] / 2 * IN
        z_dh = Ht - Td                                         # the drumhead's underside (local)
        z_low = float(self.zu(x0)) - z0 - 0.15                 # the barrel runs on below the deck (slice 12's)
        # (its stations from z_low: the top one at the drumhead's underside)
        lathe(part, [0.0, 0.0, z_low], EZ, EX, [(0.0, rb), (-z_low + 2 * IN, rb), (z_dh - z_low, rt)], "Oak", 32)
        # the whelps: ribs standing out of the barrel, an hourglass along their outer edge
        wo = cs["whelp_out_in"] * IN
        nw = cs["whelps"]
        z_w0 = 3.0 * IN
        prof = [(z_w0, 1.0), (z_w0 + 0.25 * (z_dh - z_w0), 0.8), (z_w0 + 0.55 * (z_dh - z_w0), 0.62),
                (z_dh, 0.85)]
        ww = 3.0 * IN
        for k in range(nw):
            a = 2 * math.pi * k / nw
            rad = np.array([math.cos(a), math.sin(a), 0.0])
            tan = np.array([-math.sin(a), math.cos(a), 0.0])
            rings = []
            for z, f in prof:
                rr = rb + (rt - rb) * (z / z_dh)
                ri, ro = rr - 0.6 * IN, rr + wo * f + (1.0 * IN if z == z_w0 else 0.0)
                c = np.array([0.0, 0.0, z])
                rings.append(np.array([c + rad * ri - tan * ww / 2, c + rad * ro - tan * ww / 2, c + rad * ro + tan * ww / 2,
                                       c + rad * ri + tan * ww / 2]))
            solid(part, rings, "Oak")
        # the drumhead: a slightly crowned top, hoops at both edges, the bar holes round its side
        nd = 3 * cs["bar_holes"]                               # each bar hole on one of the drumhead's faces
        lathe(part, [0.0, 0.0, z_dh], EZ, EX, [(0.0, R - 0.3 * IN), (0.3 * IN, R), (Td - 0.3 * IN, R),
                                               (Td, R - 0.5 * IN), (Td + 0.8 * IN, 0.6 * R), (Td + 1.1 * IN, 0.25 * R)],
              "Oak", nd)
        for zz in (z_dh + 1.0 * IN, z_dh + Td - 1.0 * IN):
            ring_band(part, np.array([0.0, 0.0, 0.0]), EZ, EX, zz, R, 1.75 * IN, 0.4 * IN, "Iron", nd)
        lathe(part, [0.0, 0.0, z_dh + Td + 0.9 * IN], EZ, EX, [(0.0, 4.0 * IN), (0.6 * IN, 4.0 * IN),
                                                               (0.9 * IN, 3.0 * IN)], "Iron", 16)
        bh = cs["bar_hole_in"]
        nb = cs["bar_holes"]
        for k in range(nb):
            a = 2 * math.pi * (k + 0.5) / nb
            rad = np.array([math.cos(a), math.sin(a), 0.0])
            tan = np.array([-math.sin(a), math.cos(a), 0.0])
            c = np.array([0.0, 0.0, z_dh + Td / 2]) + rad * (R * math.cos(math.pi / nd) + 0.0005)
            Q = np.array([c - tan * bh[0] / 2 * IN - EZ * bh[1] / 2 * IN, c + tan * bh[0] / 2 * IN - EZ * bh[1] / 2 * IN,
                          c + tan * bh[0] / 2 * IN + EZ * bh[1] / 2 * IN, c - tan * bh[0] / 2 * IN + EZ * bh[1] / 2 * IN])
            F = [(0, 1, 2, 3)] if np.cross(Q[1] - Q[0], Q[3] - Q[0]) @ rad > 0 else [(3, 2, 1, 0)]
            part.add(Q, F, "Shadow")
        self.frames["Capstan"] = (np.array([x0, 0.0, z0]), np.eye(3))
        # the pawl ring let into the deck, and four pawls on it lying back clear of the whelps (in the ship's frame; so
        # the capstan can turn in the game, the pawls are not shown dropped against the whelps' feet), all laid along
        # the deck's sheer
        r_ring = rb + wo + 2.0 * IN
        k0 = len(pawls.V)
        ring_band(pawls, np.array([x0, 0.0, z0]), EZ, EX, 0.5 * IN, r_ring, 1.4 * IN, 3.0 * IN, "Iron", 40)
        for k in range(4):
            a = 2 * math.pi * (k + 0.3) / 4
            p0 = np.array([x0 + (r_ring + 1.5 * IN) * math.cos(a), (r_ring + 1.5 * IN) * math.sin(a), z0 + 1.6 * IN])
            tgt = np.array([x0 + (rb + wo + 1.4 * IN) * math.cos(a + 0.22), (rb + wo + 1.4 * IN) * math.sin(a + 0.22),
                            z0 + 1.6 * IN])
            bar(pawls, p0, tgt, 1.5 * IN, 1.0 * IN, "Iron")
            lathe(pawls, p0 - EZ * 0.6 * IN, EZ, EX, [(0.0, 0.5 * IN), (1.4 * IN, 0.5 * IN)], "Iron", 8)
        self.drape(pawls, k0, z0)

    # --- the wheel and the binnacle ---------------------------------------------------------------------------------------
    def wheel(self, part, still, rope):
        """the double wheel, in its own frame (origin on the axle midway between the wheels, X forward along it, Z up):
        the axle, two wheels (nave, ten spokes ending in handles, the rim) and the barrel between them. still (in the
        ship's frame, it doesn't turn): the standards the axle turns in and the iron plates in the deck the tiller rope
        goes down through. rope (in the ship's frame, it doesn't turn either): the tiller rope's turns round the barrel
        and its legs down through the deck; as the wheel turns, the barrel turns under the turns, which look the same"""
        wh = self.c["wheel"]
        xw = self.x_wheel
        zd = float(self.z(xw))
        ha = wh["axle_high_in"] * IN
        o = np.array([xw, 0.0, zd + ha])
        sep = wh["between_wheels_in"] / 2 * IN
        Rr = wh["rim_diam_in"] / 2 * IN
        rim_r, rim_t = (v * IN for v in wh["rim_in"])
        nd, nl = (v * IN for v in wh["nave_in"])
        rs = wh["spoke_diam_in"] / 2 * IN
        hout = wh["handle_out_in"] * IN
        rb = wh["barrel_diam_in"] / 2 * IN
        r_ax = 1.25 * IN
        lathe(part, [-(sep + nl / 2 + 1.0 * IN), 0.0, 0.0], EX, EZ, [(0.0, r_ax), (2 * (sep + nl / 2 + 1.0 * IN), r_ax)],
              "Iron", 10)
        for sx in (-1.0, 1.0):
            c = np.array([sx * sep, 0.0, 0.0])
            lathe(part, c - EX * nl / 2, EX, EZ, [(0.0, 0.42 * nd), (0.4 * IN, nd / 2), (nl - 0.4 * IN, nd / 2),
                                                  (nl, 0.42 * nd)], "Oak", 20)
            ring_band(part, c, EX, EZ, 0.0, Rr - rim_r, rim_t, rim_r, "Oak", 48)
            for k in range(wh["spokes"]):
                a = 2 * math.pi * k / wh["spokes"]
                d = np.array([0.0, math.cos(a), math.sin(a)])
                q = np.cross(EX, d)
                st = [(nd / 2 - 0.5 * IN, rs * 1.1), (nd / 2 + 1.0 * IN, rs * 1.15), (0.55 * Rr, rs * 0.95),
                      (Rr - 0.5 * IN, rs * 0.9), (Rr + 0.6 * IN, rs * 0.9), (Rr + 1.2 * IN, rs * 0.7),
                      (Rr + 0.35 * hout, rs * 1.05), (Rr + 0.75 * hout, rs * 1.15), (Rr + 0.95 * hout, rs * 0.75),
                      (Rr + hout, rs * 0.35)]
                spar(part, c, d, q, st, "Oak", 8)
        hb = sep - nl / 2 - 4.0 * IN                    # the barrel's half-length, clear of the standards' bearings
        lathe(part, [-hb, 0.0, 0.0], EX, EZ, [(0.0, rb * 1.08), (0.4 * IN, rb), (2 * hb - 0.4 * IN, rb), (2 * hb, rb * 1.08)],
              "Oak", 20)
        # the tiller rope: its turns round the barrel, coming up the starboard leg at the after end, over the top and
        # round, and leaving it at the forward end down the port leg (a turn of the wheel's top to port hauls in the
        # starboard leg), a hair off the barrel so the barrel turns inside them (its chords too, 24 a turn). The legs
        # stand where the card puts them (legs_x_m: in the bay between the gun deck's overhead ledge and beam there)
        rr = rope_r(wh["tiller_rope_in"])
        xa_, xf_ = (float(v) - xw for v in wh["legs_x_m"])
        turns = wh["rope_turns"]
        if not (-hb + rr + 0.5 * IN <= xa_ < xf_ <= hb - rr - 0.5 * IN):
            raise SystemExit(f"deck: the tiller rope's legs (wheel legs_x_m) must stand in order on the barrel, half an "
                             f"inch in from its ends (its half-length {hb:.3f} m about x {xw})")
        if (xf_ - xa_) / (turns - 0.5) < 2 * rr + 0.001:
            raise SystemExit("deck: the tiller rope's turns on the barrel would lie on each other (wheel legs_x_m too "
                             "close together for rope_turns)")
        th = np.linspace(0.0, (turns - 0.5) * 2 * math.pi, int(turns * 24) + 1)
        xx = xa_ + (xf_ - xa_) * th / th[-1]
        R0 = rb + rr + 0.08 * IN
        helix = np.stack([xx, R0 * np.cos(th), R0 * np.sin(th)], 1)
        tube(rope, helix + o, rr, "Hemp", 8)
        self.frames["Wheel"] = (o, np.eye(3))
        # the legs, from the barrel's sides down into the iron plates' holes in the deck, ending a hair into it: the gun
        # deck's slice takes them on from the deck's underside to the leading sheaves under it (gundeck.py tiller_ropes)
        self.tiller_legs = []
        for x_, y_ in ((xa_, R0), (xf_, -R0)):
            p = o + np.array([x_, y_, 0.0])
            zl = float(self.z(p[0]))
            tube(rope, np.array([p + EZ * 0.002, [p[0], p[1], zl - 0.1 * IN]]), rr, "Hemp", 8)
            self.tiller_legs.append((float(p[0]), float(p[1]), rr))
            k0 = len(still.V)
            for dx, dy, hx, hy in ((0.0, 2.2 * IN, 3.0 * IN, 1.0 * IN), (0.0, -2.2 * IN, 3.0 * IN, 1.0 * IN),
                                   (2.2 * IN, 0.0, 1.0 * IN, 1.2 * IN), (-2.2 * IN, 0.0, 1.0 * IN, 1.2 * IN)):
                vbox(still, [p[0] + dx - hx, p[1] + dy - hy, zl - 0.2 * IN], [p[0] + dx + hx, p[1] + dy + hy, zl + 0.6 * IN],
                     "Iron")
            vbox(still, [p[0] - 1.2 * IN, p[1] - 1.2 * IN, zl - 0.2 * IN], [p[0] + 1.2 * IN, p[1] + 1.2 * IN, zl + 0.05 * IN],
                 "Shadow")
            self.seat(still, k0, zl - 0.2 * IN, 0.2 * IN)
        # the standards: an A-frame each side of the barrel, a bearing round the axle at its head, a sill on the deck
        sw, stt = (v * IN for v in wh["standard_in"])
        spread = wh["standard_spread_in"] / 2 * IN
        xs_ = sep - nl / 2 - 2.0 * IN
        for sx in (-1.0, 1.0):
            x = xw + sx * xs_
            zs = float(self.z(x))
            k0 = len(still.V)
            for sy in (-1.0, 1.0):
                strut(still, [x, sy * spread, zs - 0.2 * IN], [x, sy * 1.6 * IN, zd + ha + 2.5 * IN], sw, stt, "Oak", up=EX)
            vbox(still, [x - stt / 2 - 0.75 * IN, -spread - 3.0 * IN, zs - 0.2 * IN],
                 [x + stt / 2 + 0.75 * IN, spread + 3.0 * IN, zs + 3.0 * IN], "Oak")
            self.seat(still, k0, zs - 0.2 * IN, 0.2 * IN)
            vbox(still, [x - stt / 2 - 0.3 * IN, -3.0 * IN, zd + ha - 3.0 * IN], [x + stt / 2 + 0.3 * IN, 3.0 * IN, zd + ha + 4.0 * IN],
                 "Oak")
            vbox(still, [x - stt / 2 - 0.1 * IN, -0.6 * IN, zd + ha - 2.0 * IN], [x + stt / 2 + 0.1 * IN, 0.6 * IN, zd + ha - 1.5 * IN],
                 "Shadow")
        self.info["wheel"] = {"axle_m": np.round(o, 4).tolist(), "top_z_m": round(float(o[2] + Rr + hout), 3),
                              "wheels_x_m": [round(xw - sep, 3), round(xw + sep, 3)]}

    def binnacle(self, part):
        """the binnacle: a cabinet of three compartments, the compasses either side of the lamp, glazed aft toward the
        wheel, under a pitched roof with the lamp's vent"""
        bc = self.c["binnacle"]
        L, W, Hh = (v * IN for v in bc["size_in"])
        x0 = self.x_binnacle
        zd = float(self.z(x0))
        xa, xf = x0 - L / 2, x0 + L / 2
        ww, wh_ = (v * IN for v in bc["window_in"])
        zw = zd + 0.62 * Hh                                     # the windows' middle
        rec = 0.5 * L                                           # each compartment's depth behind its window
        xg = xa + 0.8 * IN                                      # the glass
        xm = 0.5 * (xg + xa + rec)                              # a compass (or the lamp) midway between glass and back
        k0 = len(part.V)
        # the cabinet, a recess behind each window (dark), its glass, the compass bowls and cards inside
        cells = [(-W / 3, ww), (0.0, 0.55 * ww), (W / 3, ww)]
        vbox(part, [xa + rec, -W / 2, zd - 0.1 * IN], [xf, W / 2, zd + Hh], "Oak")
        ys = [-W / 2]
        for yc, w in cells:
            ys += [yc - w / 2, yc + w / 2]
        ys.append(W / 2)
        for j in range(0, len(ys) - 1, 2):                      # the posts between the windows
            vbox(part, [xa, ys[j], zd - 0.1 * IN], [xa + rec, ys[j + 1], zd + Hh], "Oak")
        for yc, w in cells:
            h = wh_ if w == ww else 0.8 * wh_
            vbox(part, [xa, yc - w / 2, zd - 0.1 * IN], [xa + rec, yc + w / 2, zw - h / 2], "Oak")
            vbox(part, [xa, yc - w / 2, zw + h / 2], [xa + rec, yc + w / 2, zd + Hh], "Oak")
            # the compartment's dark back and sides
            Q = np.array([[xa + rec - 0.02 * IN, yc - w / 2, zw - h / 2], [xa + rec - 0.02 * IN, yc + w / 2, zw - h / 2],
                          [xa + rec - 0.02 * IN, yc + w / 2, zw + h / 2], [xa + rec - 0.02 * IN, yc - w / 2, zw + h / 2]])
            part.add(Q, [(3, 2, 1, 0)] if np.cross(Q[1] - Q[0], Q[3] - Q[0]) @ (-EX) < 0 else [(0, 1, 2, 3)], "Shadow")
            G = Q + [-(rec - 0.8 * IN), 0.0, 0.0]
            part.add(G, [(3, 2, 1, 0)] if np.cross(G[1] - G[0], G[3] - G[0]) @ (-EX) < 0 else [(0, 1, 2, 3)], "Glass")
            if w == ww:
                c = np.array([xm, yc, zw - h / 2 + 0.1 * IN])
                lathe(part, c, EZ, EX, [(0.0, 0.6 * w / 2), (1.6 * IN, 0.7 * w / 2), (1.8 * IN, 0.66 * w / 2)], "Bronze", 16)
                lathe(part, c + EZ * 1.5 * IN, EZ, EX, [(0.0, 0.62 * w / 2), (0.1 * IN, 0.62 * w / 2)], "CompassCard", 16)
            else:
                lathe(part, [xm, yc, zw - h / 2 + 0.1 * IN], EZ, EX,
                      [(0.0, 1.2 * IN), (2.5 * IN, 1.0 * IN), (3.0 * IN, 0.4 * IN)], "Bronze", 10)
        self.seat(part, k0, zd - 0.1 * IN, 0.1 * IN)            # the cabinet's foot on the deck's sheer
        # the roof, pitched athwartships, with an overhang, and the vent
        ov, rh = 1.0 * IN, bc["roof_in"] * IN
        ring = lambda x: np.array([[x, -(W / 2 + ov), zd + Hh - 0.2 * IN], [x, 0.0, zd + Hh + rh - 0.2 * IN],  # noqa
                                   [x, W / 2 + ov, zd + Hh - 0.2 * IN], [x, W / 2 + ov, zd + Hh + 0.9 * IN],
                                   [x, 0.0, zd + Hh + rh + 0.9 * IN], [x, -(W / 2 + ov), zd + Hh + 0.9 * IN]])
        chevron(part, ring(xa - ov), ring(xf + ov), "Oak")
        lathe(part, [x0, 0.0, zd + Hh + rh], EZ, EX, [(0.0, 1.4 * IN), (3.5 * IN, 1.4 * IN), (3.6 * IN, 2.4 * IN),
                                                       (4.6 * IN, 2.2 * IN), (5.2 * IN, 0.6 * IN)], "Iron", 12)

    # --- forward ---------------------------------------------------------------------------------------------------------
    def belfry(self, part):
        """the belfry at the forecastle's break: two posts with a headstock between them, a roof over, braced forward;
        the bell hung under the headstock with its clapper and lanyard"""
        bf = self.c["belfry"]
        xb = self.breast_x["forecastle"]
        zd = float(self.z(xb))
        ps = bf["post_in"] * IN
        yp = bf["posts_apart_in"] / 2 * IN
        Hh = bf["height_in"] * IN
        hs = bf["headstock_in"] * IN
        k0 = len(part.V)
        z_ft = zd - 0.2 * IN                                    # the feet, let into the deck (then laid on its sheer)
        bw, bt = 3.5 * IN, 3.0 * IN                             # each brace: across its slope, and athwartships
        A = np.array([xb + ps / 2 + 14 * IN, z_ft])             # the brace's foot and head (x, z) on its centre line
        B = np.array([xb + ps / 2 - 0.5 * IN, zd + 26 * IN])
        d2 = unit(B - A)
        n2 = np.array([-d2[1], d2[0]])
        foot = [A[0] + k * bw / 2 * n2[0] + d2[0] * (z_ft - A[1] - k * bw / 2 * n2[1]) / d2[1] for k in (-1.0, 1.0)]
        head = [A[1] + k * bw / 2 * n2[1] + d2[1] * (B[0] - A[0] - k * bw / 2 * n2[0]) / d2[0] for k in (-1.0, 1.0)]
        for sy in (-1.0, 1.0):
            vbox(part, [xb - ps / 2, sy * yp - ps / 2, z_ft], [xb + ps / 2, sy * yp + ps / 2, zd + Hh], "Oak")
            # the brace forward of the post, its foot cut level on the deck and its head square against the post
            y0, y1 = sy * yp - bt / 2, sy * yp + bt / 2
            solid(part, [np.array([[foot[0], y0, z_ft], [foot[1], y0, z_ft], [foot[1], y1, z_ft], [foot[0], y1, z_ft]]),
                         np.array([[B[0], y0, head[0]], [B[0], y0, head[1]], [B[0], y1, head[1]], [B[0], y1, head[0]]])],
                  "Oak")
        self.seat(part, k0, z_ft, 0.2 * IN)
        vbox(part, [xb - ps / 2 + 0.5 * IN, -yp - ps / 2 - 1.5 * IN, zd + hs - 3.0 * IN],
             [xb + ps / 2 - 0.5 * IN, yp + ps / 2 + 1.5 * IN, zd + hs + 3.0 * IN], "Oak")     # through the posts
        vbox(part, [xb - ps / 2 - 1.0 * IN, -yp - ps / 2 - 2.0 * IN, zd + Hh - 0.1 * IN],
             [xb + ps / 2 + 1.0 * IN, yp + ps / 2 + 2.0 * IN, zd + Hh + 2.0 * IN], "Oak")
        rf = 8.0 * IN
        e = ps / 2 + 4.0 * IN
        ring = lambda y: np.array([[xb - e, y, zd + Hh + 1.5 * IN], [xb, y, zd + Hh + rf], [xb + e, y, zd + Hh + 1.5 * IN],  # noqa
                                   [xb + e, y, zd + Hh + 2.5 * IN], [xb, y, zd + Hh + rf + 1.0 * IN],
                                   [xb - e, y, zd + Hh + 2.5 * IN]])
        chevron(part, ring(-yp - ps / 2 - 3.0 * IN), ring(yp + ps / 2 + 3.0 * IN), "Oak")
        # the bell: hollow, of revolution, its crown under the headstock
        M = bf["bell_mouth_in"] * IN
        top = zd + hs - 3.0 * IN - 1.8 * IN
        outer = [(0.5, 0.0), (0.53, 0.035), (0.5, 0.1), (0.42, 0.3), (0.36, 0.55), (0.34, 0.72), (0.31, 0.8),
                 (0.22, 0.85), (0.0, 0.87)]
        inner = [(0.0, 0.8), (0.24, 0.76), (0.3, 0.6), (0.34, 0.35), (0.42, 0.1), (0.46, 0.0)]
        prof = [(r * M, (h - 0.87) * M) for r, h in outer] + [(r * M, (h - 0.87) * M) for r, h in inner]
        th = np.linspace(0, 2 * math.pi, 28, endpoint=False)
        rings = [np.stack([xb + r * np.cos(th), r * np.sin(th), np.full(len(th), top + h)], 1) for r, h in prof]
        nr = len(rings)
        V = np.concatenate([rr if r > 1e-9 else rr[:1] for (r, _), rr in zip(prof, rings)])
        # build as a revolved closed loop (the lip joins the outer and inner faces)
        idx, k = [], 0
        for (r, _), rr in zip(prof, rings):
            n_ = len(rr) if r > 1e-9 else 1
            idx.append(list(range(k, k + n_)))
            k += n_
        F = []
        nth = len(th)
        for a, b in zip(idx[:-1], idx[1:]):
            for q in range(nth):
                q1 = (q + 1) % nth
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    F.append((a[0], b[q1], b[q]))
                elif len(b) == 1:
                    F.append((a[q], a[q1], b[0]))
                else:
                    F.append((a[q], a[q1], b[q1], b[q]))
        a, b = idx[-1], idx[0]                                   # the lip
        F += [(a[q], a[(q + 1) % nth], b[(q + 1) % nth], b[q]) for q in range(nth)]
        Vc = V - [xb, 0.0, top - 0.4 * M]
        nrm = sum(np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]]) @ Vc[f[0]] for f in F[:nth])
        if nrm < 0:
            F = [f[::-1] for f in F]
        del nr
        part.add(V, F, "Bronze")
        lathe(part, [xb, 0.0, top - 0.02 * IN], EZ, EX, [(0.0, 1.2 * IN), (1.0 * IN, 0.9 * IN), (1.9 * IN, 1.1 * IN)],
              "Bronze", 10)
        # the clapper and its lanyard: the rod from the crown's inside down to the ball, which hangs just inside the mouth
        cz = top - 0.87 * M + 1.2 * IN
        z_crown = top - 0.07 * M                                # the inside of the crown (the profile's inner top)
        lathe(part, [xb, 0.0, cz + 1.0 * IN], EZ, EX, [(0.0, 0.3 * IN), (z_crown - cz - 1.0 * IN, 0.3 * IN)], "Iron", 6)
        lathe(part, [xb, 0.0, cz + 1.0 * IN], -EZ, EX, [(0.0, 0.3 * IN), (0.5 * IN, 1.0 * IN), (1.5 * IN, 1.2 * IN),
                                                       (2.4 * IN, 0.5 * IN)], "Iron", 10)
        tube(part, np.array([[xb, 0.0, cz - 1.2 * IN], [xb, 0.0, top - 0.87 * M - 5.0 * IN]]), 0.35 * IN, "Hemp", 6)
        self.info["bell_mouth_above_deck_m"] = round(float(top - 0.87 * M - zd), 3)

    def bowsprit_step(self, part):
        """the bowsprit's heel: a step chock across abaft it, its fore face square to the bowsprit just clear of the
        heel's end, between two bitts"""
        bs_c = self.c["bowsprit_step"]
        bs = self.rig.bs
        H, ub, up = (np.asarray(bs[k], float) for k in ("H", "ub", "up"))
        r0 = float(bs["R"](0.0))
        gap = bs_c["gap_in"] * IN
        bt = bs_c["bitt_in"] * IN
        sd = bs_c["step_in"][0] * IN
        top_z = float((H + r0 * up)[2]) + 2.0 * IN
        k = float(H @ ub) - 0.15 * IN                            # the chock's fore face: (p . ub) = k
        x_at = lambda z: (k - z * ub[2]) / ub[0]                 # noqa: E731
        xd = x_at(float(self.z(x_at(float(self.z(H[0]))))))
        yb = r0 + gap
        Pl = []
        z0 = float(self.z(xd)) - 0.2 * IN
        k0 = len(part.V)
        for y in (-yb, yb):
            Pl.append([[xd, y, z0], [x_at(top_z), y, top_z], [x_at(top_z) - sd, y, top_z], [x_at(top_z) - sd, y, z0]])
        solid(part, [np.array(Pl[0]), np.array(Pl[1])], "Oak")
        self.seat(part, k0, z0, 0.2 * IN)                       # its foot along the deck's sheer, which rises fast here
        bh = bs_c["bitt_high_in"] * IN
        xc = x_at(top_z) - sd / 2 + 0.25 * (xd - x_at(top_z))
        zb = float(self.z(xc)) - 0.2 * IN
        k0 = len(part.V)
        for sy in (-1.0, 1.0):
            yc = sy * (yb + bt / 2)
            vbox(part, [xc - bt / 2, yc - bt / 2, zb], [xc + bt / 2, yc + bt / 2, float(self.z(xc)) + bh], "Oak")
            lathe(part, [xc, yc, float(self.z(xc)) + bh], EZ, EX, [(0.0, 0.5 * bt), (1.5 * IN, 0.42 * bt),
                                                                   (2.5 * IN, 0.2 * bt)], "Oak", 12)
        self.seat(part, k0, zb, 0.2 * IN)
        self.info["bowsprit_step"] = {"fore_face_x_m_at_deck": round(xd, 3), "bitts_x_m": round(xc, 3),
                                      "foot_x_m": [round(float(x_at(top_z) - sd), 3), round(xd, 3)]}

    def mast_coats(self, part):
        """a tarred canvas coat round each mast at the deck, pleated, lashed round the mast at its top: a hollow collar
        (its inner face a little off the mast all the way down into the deck, so nothing of it crosses the mast)"""
        mc = self.c["mast_coats"]
        hi, out = mc["high_in"] * IN, mc["out_in"] * IN
        gap, top = 0.2 * IN, 0.45 * IN                          # off the mast inside; the gathered top's thickness
        n = 48
        th = np.linspace(0, 2 * math.pi, n, endpoint=False)
        for name in ("fore", "main", "mizzen"):
            x0 = float(self.rig.masts[name]["O"][0])
            zd = float(self.z(x0))
            prof = [(-0.3 * IN, 1.0), (0.0, 1.0), (0.12, 0.8), (0.3, 0.55), (0.55, 0.32), (0.8, 0.12), (1.0, 0.02)]

            def ring(h, r_of, o):
                # its height follows the deck's sheer at the skirt (o = 1) and is level at the gathered top (o = 0)
                c, R, _ = self.mast_at(name, zd + h)
                rr = r_of(R)
                x, y = c[0] + rr * np.cos(th), c[1] + rr * np.sin(th)
                return np.stack([x, y, zd + h + o * (self.z(x) - zd)], 1)
            rings = []
            for f, o in prof:                                   # the outside, from the deck up
                h = f * hi if f > 0 else f
                rings.append(ring(h, lambda R, o=o: R + top + (out - top) * o + 0.5 * IN * o * np.sin(8 * th) * (o > 0.05),
                                  o))
            for f, o in prof[::-1]:                             # the inside, from the top down
                h = f * hi if f > 0 else f
                rings.append(ring(h, lambda R: R + gap, o))
            V = np.concatenate(rings)
            m = len(rings)
            F = [(r * n + j, r * n + (j + 1) % n, ((r + 1) % m) * n + (j + 1) % n, ((r + 1) % m) * n + j)
                 for r in range(m) for j in range(n)]
            f0 = F[2 * n]                                       # a face of the outside: it must face away from the mast
            c0 = V[list(f0)].mean(0)
            away = c0 - np.array([float(self.mast_at(name, c0[2])[0][0]), 0.0, c0[2]])
            if np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]]) @ away < 0:
                F = [f[::-1] for f in F]
            part.add(V, F, "Tarred")
            c, R, _ = self.mast_at(name, zd + hi - 1.0 * IN)
            ring_band(part, np.array([c[0], c[1], 0.0]), EZ, EX, zd + hi - 1.0 * IN, R + 0.5 * IN, mc["lashing_in"] * IN,
                      0.6 * IN, "Tarred", n)
            self.info.setdefault("mast_coats", {})[name] = {"deck_z_m": round(zd, 4), "top_z_m": round(zd + hi, 4)}

    # --- all of it ---------------------------------------------------------------------------------------------------------
    def build(self):
        self.layout()
        P = {n: Part() for n in ("SparDeck", "Waterways", "WaistFrame", "BreastRails", "Ladders", "Hatches", "Companion",
                                 "Skylights", "Capstan", "CapstanPawls", "Wheel", "WheelStandards", "TillerRope", "Binnacle",
                                 "Belfry", "Chimney", "BowspritStep", "MastCoats")}
        self.surface(P["SparDeck"])
        self.waterways(P["Waterways"])
        self.waist(P["WaistFrame"])
        self.breast_rails(P["BreastRails"])
        self.ladders(P["Ladders"])
        self.hatches(P["Hatches"])
        self.companion(P["Companion"])
        self.skylights(P["Skylights"])
        cap_local = Part()
        self.capstan(cap_local, P["CapstanPawls"])
        P["Capstan"] = cap_local
        wheel_local = Part()
        self.wheel(wheel_local, P["WheelStandards"], P["TillerRope"])
        P["Wheel"] = wheel_local
        self.binnacle(P["Binnacle"])
        self.belfry(P["Belfry"])
        self.chimney(P["Chimney"])
        self.bowsprit_step(P["BowspritStep"])
        self.mast_coats(P["MastCoats"])
        self.parts_ = P
        return self

    def parts(self):
        """name -> (V, faces, materials, frame, uv): frame (origin, R) for a part built in its own frame (R's columns
        its axes in the ship: the vertices are in that frame), else None (in the ship's frame); uv the 'Planking' UV
        per vertex (the deck's top) or None"""
        out = {}
        for name, p in self.parts_.items():
            V, F, M, U = p.arrays()
            out[name] = (V, F, M, self.frames.get(name), U if name in ("SparDeck", "Nettings") else None)
        return out

    def world(self, name):
        """a part's vertices in the ship's frame"""
        V, F, M, U = self.parts_[name].arrays()
        fr = self.frames.get(name)
        if fr is not None:
            o, R = fr
            V = o + V @ np.asarray(R).T
        return V, F

    def planking(self):
        """the material's planking terms' parameters (planking_terms' P)"""
        pk = self.c["deck"]["planking"]
        return {"w": pk["width_in"] * IN, "seam": pk["seam_in"] * IN, "x0": self.e1, "bp": self.beam_pitch,
                "Lb": pk["length_beams"], "stagger": pk["butt_stagger_beams"], "plug_r": pk["plug_in"] / 2 * IN,
                "plug_off": pk["plug_off_butt_in"] * IN, "nib": pk["nib_of_width"]}

    # --- the hammock nettings ------------------------------------------------------------------------------------------------
    def rail_runs(self):
        """the rail caps the nettings stand on, each side: [(name, side sign, x (n,), top centre (n, 3), outward unit
        (n, 3))]: the quarterdeck's and forecastle's caps (skin.rail_caps) and the waist's rail (skin.waist_rail)"""
        sk, pr, SKM = self.sk, self.sk.pr, self.SKM
        nt = self.c["nettings"]
        rs = sk.sp["rail"]
        t = rs["thick_in"] * IN
        top = sk.byname[f"b{sk.nb}"]
        runs = []
        end = 0.06

        def cap(O, I):
            u = O - I
            u[:, 2] = 0.0
            u /= np.linalg.norm(u, axis=1)[:, None]
            c = 0.5 * (O + I)
            c[:, 2] = np.maximum(O[:, 2], I[:, 2]) - 0.5 * IN + t
            return c, u
        for name, a, b in (("quarterdeck", nt["aft_end_m"], self.e0 - end), ("forecastle", self.fc + end,
                                                                              nt["fore_end_m"])):
            X = np.array([self.xpx(x) for x in np.arange(a, b, 0.05)] + [self.xpx(b)])
            I, _ = sk.surf(X, pr.R1(X), True, 0, SKM.BUL)
            O, _ = sk.surf(X, top.z(X), True, top.side, SKM.OUT)
            c, u = cap(O, I)
            runs.append((name, c[:, 0], c, u))
        X = np.array([self.xpx(x) for x in np.arange(self.e1 + end, self.fc - end, 0.05)] + [self.xpx(self.fc - end)])
        O, _ = sk.surf(X, pr.H(X), True, 0, SKM.OUT)
        I, _ = sk.surf(X, pr.H(X), True, 0, SKM.BUL)
        c, u = cap(O, I)
        runs.append(("waist", c[:, 0], c, u))
        return runs

    def netting_box(self, margin=0.15):
        """a box (lo, hi: corners in x, |y|, z) round every rail the nettings stand on, with their height and margin
        to spare: only what passes through it can touch a netting (surface_points' box)"""
        nt = self.c["nettings"]
        up = (nt["high_in"] + nt["cloth_crown_in"]) * IN
        hw = nt["wide_in"] / 2 * IN
        C = np.concatenate([c for _, _, c, _ in self.rail_runs()])
        lo = np.array([C[:, 0].min() - margin, np.abs(C[:, 1]).min() - hw - margin, C[:, 2].min() - margin])
        hi = np.array([C[:, 0].max() + margin, np.abs(C[:, 1]).max() + hw + margin, C[:, 2].max() + up + margin])
        return lo, hi

    def nettings(self, obstacles, clear_in=1.0):
        """the hammock nettings on the rail caps, each side, built round the obstacles: [(points (n, 3), radius (n,) or
        a number, label)] (the ropes' paths sampled, the standing rigging, every fitting's vertices, the spanker boom
        swept through its swing). A netting keeps its inner side at the cap's inner half (wide_in) and narrows from
        either side, tapering, where something comes within clear_in of it (of the netting's sides and the hammock
        cloth hanging outside them), from the cap's top to the cloth's crown; where less than min_wide_in is left it
        breaks (gap_pad_in either side). Returns the Part, and records the gaps, the narrowings and each run's measured
        least clearance (its mesh against the obstacles) in info['nettings']"""
        try:
            from mathutils.bvhtree import BVHTree
        except ImportError:                             # the bpy module registers mathutils when it is imported
            import bpy  # noqa: F401
            from mathutils.bvhtree import BVHTree
        nt = self.c["nettings"]
        H = nt["high_in"] * IN
        hw = nt["wide_in"] / 2 * IN
        crown = nt["cloth_crown_in"] * IN
        rr = nt["rail_diam_in"] / 2 * IN
        ov = max(CLOTH_OVER, rr)                        # what stands outside the netting's sides: the cloth, the rails
        top_h = H + rr + 0.3 * IN + crown               # the cloth's crown (_netting)
        clr = clear_in * IN
        pad = nt["gap_pad_in"] * IN
        wmin = nt["min_wide_in"] * IN
        taper = nt["taper"]
        part = Part()
        report = []
        allP, allR, allL = [], [], []
        for k, (P, r, lab) in enumerate(obstacles):
            P = np.asarray(P, float).reshape(-1, 3)
            allP.append(P)
            allR.append(np.broadcast_to(np.asarray(r, float), (len(P),)).astype(float))
            allL.append(np.full(len(P), k))
        allP, allR, allL = np.concatenate(allP), np.concatenate(allR), np.concatenate(allL)
        for name, xs, C, U in self.rail_runs():
            # each side's room, then the two combined, so the nettings are the same both sides (each as narrow as the
            # narrower side wants: the rigging and the ropes' plan are symmetric, but a lanyard's reeving is not)
            sides = {}
            for sgn in (1.0, -1.0):
                f = np.array([1.0, sgn, 1.0])
                Cs, Us = C * f, U * f
                # obstacles near this run: rail coordinates (x, outward offset, height over the cap's top)
                near = (allP[:, 0] >= xs[0] - allR - clr) & (allP[:, 0] <= xs[-1] + allR + clr) & (allP[:, 1] * sgn > 0.5)
                Q, Rq, Lq = allP[near], allR[near], allL[near]
                cx = np.interp(Q[:, 0], xs, Cs[:, 0])
                cy = np.interp(Q[:, 0], xs, Cs[:, 1])
                cz = np.interp(Q[:, 0], xs, Cs[:, 2])
                ux = np.interp(Q[:, 0], xs, Us[:, 0])
                uy = np.interp(Q[:, 0], xs, Us[:, 1])
                lat = (Q[:, 0] - cx) * ux + (Q[:, 1] - cy) * uy
                h = Q[:, 2] - cz
                inband = (h > -Rq - clr - 0.01) & (h < top_h + Rq + clr) & (np.abs(lat) < hw + ov + Rq + clr + 0.01)
                Q, Rq, Lq, lat, h = Q[inband], Rq[inband], Lq[inband], lat[inband], h[inband]
                lo = np.full(len(xs), -hw)
                hi = np.full(len(xs), hw)
                who = {}
                if len(Q):
                    # each point bears on the stations within its reach (else on the nearest one): the netting's
                    # outer side must stay under up_side there, or its inner side over dn_side, whichever leaves more
                    reach = Rq + clr
                    i0 = np.searchsorted(xs, Q[:, 0] - reach - rr, side="left")       # the rails run on past the ends
                    i1 = np.searchsorted(xs, Q[:, 0] + reach + rr, side="right") - 1
                    a_ = np.clip(np.searchsorted(xs, Q[:, 0]), 0, len(xs) - 1)
                    b_ = np.clip(a_ - 1, 0, len(xs) - 1)
                    nearest = np.where(np.abs(xs[b_] - Q[:, 0]) < np.abs(xs[a_] - Q[:, 0]), b_, a_)
                    none = i1 < i0
                    i0, i1 = np.where(none, nearest, i0), np.where(none, nearest, i1)
                    up_side, dn_side = lat - reach - ov, lat + reach + ov
                    to_hi = (up_side + hw) >= (hw - dn_side)
                    cnt = i1 - i0 + 1
                    rep = np.repeat(np.arange(len(Q)), cnt)
                    idx = i0[rep] + np.arange(len(rep)) - np.repeat(np.cumsum(cnt) - cnt, cnt)
                    th = to_hi[rep]
                    np.minimum.at(hi, idx[th], up_side[rep][th])
                    np.maximum.at(lo, idx[~th], dn_side[rep][~th])
                    for i, lq in np.unique(np.stack([idx, Lq[rep]], 1), axis=0):
                        who.setdefault(int(i), set()).add(obstacles[int(lq)][2])
                sides[sgn] = (Cs, Us, lo, hi, who)
            lo = np.maximum(sides[1.0][2], sides[-1.0][2])
            hi = np.minimum(sides[1.0][3], sides[-1.0][3])
            # taper the narrowings: each side eases back at 'taper' (m across per m along)
            for i in range(len(xs)):
                d = np.abs(xs - xs[i]) * taper
                hi[i] = np.min(hi + d)
                lo[i] = np.max(lo - d)
            blocked = (hi - lo) < wmin
            # gaps: the blocked stations and gap_pad either side
            gap = np.zeros(len(xs), bool)
            for x in xs[blocked]:
                gap |= np.abs(xs - x) <= pad
            segs, i = [], 0
            while i < len(xs):
                if gap[i]:
                    i += 1
                    continue
                j = i
                while j + 1 < len(xs) and not gap[j + 1]:
                    j += 1
                if xs[j] - xs[i] >= nt["min_run_m"]:
                    segs.append((i, j))
                i = j + 1
            # where it is narrowed (by more than 1 cm), as stretches
            nar = (hi - lo) < 2 * hw - 0.01
            narrow, k = [], 0
            while k < len(xs):
                if not nar[k]:
                    k += 1
                    continue
                m = k
                while m + 1 < len(xs) and nar[m + 1]:
                    m += 1
                narrow.append([round(float(xs[k]), 2), round(float(xs[m]), 2)])
                k = m + 1
            for sgn in (1.0, -1.0):
                Cs, Us, _, _, who = sides[sgn]
                gaps = []
                prev = xs[0]
                for i, j in segs:
                    if xs[i] - prev > 0.04:
                        names = sorted(set().union(*[who.get(k, set()) for k in range(len(xs)) if prev <= xs[k] <= xs[i]]))
                        gaps.append({"x_m": [round(prev, 2), round(float(xs[i]), 2)], "for": names[:6]})
                    prev = xs[j]
                if xs[-1] - prev > 0.04:
                    names = sorted(set().union(*[who.get(k, set()) for k in range(len(xs)) if xs[k] >= prev]))
                    gaps.append({"x_m": [round(prev, 2), round(float(xs[-1]), 2)], "for": names[:6]})
                least_w, least_c, closest = 2 * hw, None, None
                for i, j in segs:
                    run = Part()
                    Lo, Hi = self._netting(run, xs[i:j + 1], Cs[i:j + 1], Us[i:j + 1], lo[i:j + 1], hi[i:j + 1])
                    least_w = min(least_w, float(np.min(Hi - Lo)))
                    # the clearance as built: the run's mesh against every obstacle point near it, less its radius; a
                    # point inside the netting (over the cap, the topmost face straight above it looking up: the cloth
                    # seen from under it) counts as its depth inside, negative
                    V, F, _, _ = run.arrays()
                    tree = BVHTree.FromPolygons(V.tolist(), [list(f) for f in F])
                    b0, b1 = V.min(0) - clr - 0.1, V.max(0) + clr + 0.1
                    sel = np.all((allP >= b0) & (allP <= b1), axis=1)
                    cap = np.interp(allP[sel][:, 0], xs[i:j + 1], Cs[i:j + 1, 2])
                    for q, rq, lq, zc in zip(allP[sel], allR[sel], allL[sel], cap):
                        c = None
                        hit = tree.find_nearest(q.tolist(), float(rq + clr + 0.02))
                        if hit[0] is not None:
                            c = float(hit[3] - rq)
                        if q[2] > zc and self._under(tree, q):
                            c = -float(tree.find_nearest(q.tolist())[3]) - float(rq)
                        if c is not None and (least_c is None or c < least_c):
                            least_c, closest = c, obstacles[int(lq)][2]
                    part.extend(run)
                report.append({"rail": name, "side": "starboard" if sgn > 0 else "port",
                               "runs_m": [[round(float(xs[i]), 2), round(float(xs[j]), 2)] for i, j in segs],
                               "gaps": gaps,
                               "narrowed_m": narrow,
                               "least_wide_in": round(least_w / IN, 1),
                               "least_clear_in": None if least_c is None else round(least_c / IN, 2),
                               "closest": closest})
        self.info["nettings"] = report
        self.parts_["Nettings"] = part
        return part

    @staticmethod
    def _under(tree, q):
        """whether point q is under a surface of the BVH tree that looks up at its top (inside a netting: the topmost
        face straight above it is the cloth's, seen from under it); a point beside or over the netting has nothing
        above it"""
        p, last = np.asarray(q, float).copy(), None
        for _ in range(64):
            co, nrm, _, _ = tree.ray_cast(p.tolist(), (0.0, 0.0, 1.0))
            if co is None:
                break
            last = nrm
            p = np.array(co) + np.array([0.0, 0.0, 1e-5])
        return last is not None and last[2] > 0.0

    def _netting(self, part, xs, C, U, lo, hi):
        """one run of netting: iron cranes, the rails along their heads, the netting each side and at the ends (UV:
        along, up; the material draws the mesh), the hammocks stowed on end and the hammock cloth over the top. Returns
        the sides' offsets (Lo, Hi) at the stations it kept"""
        nt = self.c["nettings"]
        H = nt["high_in"] * IN
        cw, ct = (v * IN for v in nt["crane_in"])
        rr = nt["rail_diam_in"] / 2 * IN
        rd = nt["roll_diam_in"] / 2 * IN
        crown = nt["cloth_crown_in"] * IN
        down = nt["cloth_down_in"] * IN
        # thin the stations to every ~0.25 m (keeping the ends) for the long surfaces, keeping every station needed so
        # that the sides, drawn straight between the kept ones, are nowhere wider than computed (by over 0.5 mm)
        keep = np.zeros(len(xs), bool)
        keep[::5] = True
        keep[-1] = True
        for _ in range(len(xs)):
            k_ = np.nonzero(keep)[0]
            err = np.maximum(np.interp(xs, xs[k_], hi[k_]) - hi, lo - np.interp(xs, xs[k_], lo[k_]))
            bad = (err > 0.0005) & ~keep
            if not bad.any():
                break
            # the worst station between each two kept ones
            seg = np.searchsorted(k_, np.arange(len(xs)))
            for g in np.unique(seg[bad]):
                m_ = bad & (seg == g)
                keep[np.nonzero(m_)[0][np.argmax(err[m_])]] = True
        idx = np.nonzero(keep)[0]
        X, Cc, Uu, Lo, Hi = xs[idx], C[idx], U[idx], lo[idx], hi[idx]
        L_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Cc, axis=0), axis=1))])

        def at(k, lat, h):
            return Cc[k] + Uu[k] * lat + EZ * h
        # the netting's two sides and its ends (UV: arc length along, height)
        for side in ("lo", "hi"):
            A = np.array([at(k, (Lo if side == "lo" else Hi)[k], 0.05 * IN) for k in range(len(X))])
            B = np.array([at(k, (Lo if side == "lo" else Hi)[k], H) for k in range(len(X))])
            n = len(A)
            V = np.concatenate([A, B])
            F = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
            out = -Uu[0] if side == "lo" else Uu[0]
            nrm = np.cross(V[F[0][1]] - V[F[0][0]], V[F[0][3]] - V[F[0][0]])
            if nrm @ out < 0:
                F = [f[::-1] for f in F]
            uv = np.concatenate([np.column_stack([L_, np.zeros(n)]), np.column_stack([L_, np.full(n, H)])])
            part.add(V, F, "Netting", uv=uv)
        for k, out in ((0, -EX), (len(X) - 1, EX)):
            Q = np.array([at(k, Lo[k], 0.05 * IN), at(k, Hi[k], 0.05 * IN), at(k, Hi[k], H), at(k, Lo[k], H)])
            F = [(0, 1, 2, 3)] if np.cross(Q[1] - Q[0], Q[3] - Q[0]) @ out > 0 else [(3, 2, 1, 0)]
            part.add(Q, F, "Netting", uv=np.array([[0, 0], [Hi[k] - Lo[k], 0], [Hi[k] - Lo[k], H], [0, H]]))
        # the rails along the cranes' heads
        for side in (Lo, Hi):
            P = np.array([at(k, side[k], H) for k in range(len(X))])
            P[0] -= unit(P[1] - P[0]) * 0.5 * IN
            P[-1] += unit(P[-1] - P[-2]) * 0.5 * IN
            tube(part, P, rr, "Iron", 6)
        # cranes: at each end and every crane_pitch between: a stem up the middle, forked to the two rails
        n_c = max(1, int(math.ceil(L_[-1] / (nt["crane_pitch_in"] * IN))))
        for s in np.linspace(1.0 * IN, L_[-1] - 1.0 * IN, n_c + 1):
            k = int(np.clip(np.searchsorted(L_, s), 1, len(L_) - 1))
            t = (s - L_[k - 1]) / max(L_[k] - L_[k - 1], 1e-9)
            c = Cc[k - 1] + (Cc[k] - Cc[k - 1]) * t
            u = unit(Uu[k - 1] + (Uu[k] - Uu[k - 1]) * t)
            lo_, hi_ = Lo[k - 1] + (Lo[k] - Lo[k - 1]) * t, Hi[k - 1] + (Hi[k] - Hi[k - 1]) * t
            mid = 0.5 * (lo_ + hi_)
            fork = c + u * mid + EZ * 0.45 * H
            bar(part, c + u * mid - EZ * 0.3 * IN, fork, cw, ct, "Iron", up=u)
            for lat in (lo_, hi_):
                bar(part, fork, c + u * lat + EZ * (H - rr), cw, ct, "Iron", up=u)
        # the hammocks, rolled and stowed on end, two staggered rows where the netting is wide enough
        pitch = 2 * rd + 0.3 * IN
        n_r = int(L_[-1] // pitch)
        for q in range(n_r):
            s = (q + 0.5) * L_[-1] / n_r
            k = int(np.clip(np.searchsorted(L_, s), 1, len(L_) - 1))
            t = (s - L_[k - 1]) / max(L_[k] - L_[k - 1], 1e-9)
            c = Cc[k - 1] + (Cc[k] - Cc[k - 1]) * t
            u = unit(Uu[k - 1] + (Uu[k] - Uu[k - 1]) * t)
            lo_, hi_ = Lo[k - 1] + (Lo[k] - Lo[k - 1]) * t, Hi[k - 1] + (Hi[k] - Hi[k - 1]) * t
            room = hi_ - lo_ - 2 * rd - 0.6 * IN
            if room < 0:
                continue
            lat = 0.5 * (lo_ + hi_) + (0.5 * room * (1 if q % 2 else -1) * 0.8)
            ht = H - 0.6 * IN - (0.3 * IN if q % 3 == 1 else 0.0)
            lathe(part, c + u * lat + EZ * 0.1 * IN, EZ, u, [(0.0, 0.85 * rd), (0.8 * IN, rd), (ht - 1.2 * IN, rd),
                                                             (ht - 0.2 * IN, 0.8 * rd), (ht, 0.5 * rd)], "Canvas", 8)
        # the hammock cloth: over the rails with a crown, hanging down outside each side
        nac = 7
        rings = []
        for k in range(len(X)):
            w = Hi[k] - Lo[k]
            # the eaves just over the rails' tops, so the cloth clears them
            pts = [at(k, Lo[k] - CLOTH_OVER, H - down), at(k, Lo[k] - CLOTH_OVER, H + rr + 0.1 * IN)]
            for j in range(1, nac):
                f = j / nac
                pts.append(at(k, Lo[k] + f * w, H + rr + 0.3 * IN + crown * math.sin(math.pi * f)))
            pts += [at(k, Hi[k] + CLOTH_OVER, H + rr + 0.1 * IN), at(k, Hi[k] + CLOTH_OVER, H - down)]
            rings.append(np.array(pts))
        m = len(rings[0])
        V = np.concatenate(rings)
        F = []
        for k in range(len(rings) - 1):
            for j in range(m - 1):
                F.append((k * m + j, k * m + j + 1, (k + 1) * m + j + 1, (k + 1) * m + j))
        mid = (m - 1) // 2
        f0 = F[mid]
        if np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])[2] < 0:
            F = [f[::-1] for f in F]
        part.add(V, F, "Tarpaulin")
        return Lo, Hi

    # --- for the game ------------------------------------------------------------------------------------------------------
    def game_data(self):
        """deck.json: where each fitting is, the capstan's and wheel's frames and how they turn, the nettings' runs"""
        wh = self.c["wheel"]
        fr = {k: {"origin_m": np.round(o, 4).tolist(), "axes": np.round(R, 5).tolist()} for k, (o, R) in self.frames.items()}
        fr["Wheel"]["turns"] = ("about its own +X (forward along the axle): a positive turn takes the top of the wheels "
                                "to port, and the ship's head to port (tiller ropes led as the period's ships led them); "
                                "the standards (WheelStandards) and the tiller rope (TillerRope) stay: the barrel turns "
                                "under the rope's turns, which look the same")
        fr["Wheel"]["spokes"] = wh["spokes"]
        fr["Capstan"]["turns"] = "about its own +Z (up): the drumhead heaves either way; the pawls (CapstanPawls) stay"
        return {"frames": fr, "layout": self.info.get("layout"), "waist": self.info.get("waist"),
                "ladders": getattr(self, "ladder_info", []), "beams_x_m": getattr(self, "beams_x", []),
                "nettings": self.info.get("nettings"), "planking": {k: (round(v, 5) if isinstance(v, float) else v)
                                                                    for k, v in self.planking().items()}}
