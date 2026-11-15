"""Carved relief (docs/shipkit-9): a running scroll's strokes and leaves drawn in a band's own coordinates, and laid as
half-round mouldings and low leaves on a surface; used on the head's trailboards and the stern's frieze.
    band = Band(lower_xz, upper_xz)                 the strip between two edges (elevation), by its middle line
    design = running_scroll(band.length, band.half_min, cfg)
    relief(mesh, design, band.to_xz, place, mat)     place(XZ (n, 2)) -> (points (n, 3), outward normals (n, 3))
A design is {"strokes": [(points (n, 2) in (s, w) metres along and across the band, radius (n,))], "leaves": [(base
(2,), direction (2,), length, width, height)], "berries": [(centre (2,), radius)]}.
    relief(..., seat=Seat(V, F))                    leaves (draped) and berries set down on a curved surface's faces
    seated(parts, carriers)                         the build's check that every piece is on what it is carved on
"""
import math

import numpy as np
from scipy.interpolate import CubicSpline

from skin import sweep


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


class Band:
    """The strip between a lower and an upper edge in elevation (each (n, 2) (x, z), x increasing): its middle line
    by arc length s, the normal across it (upward) and the half height there; to_xz maps (s, w) to (x, z)."""

    def __init__(self, lower, upper, step=0.02):
        lower, upper = np.asarray(lower, float), np.asarray(upper, float)
        x0 = max(lower[0, 0], upper[0, 0])
        x1 = min(lower[-1, 0], upper[-1, 0])
        xs = np.linspace(x0, x1, max(8, int((x1 - x0) / step)))
        zl = np.interp(xs, lower[:, 0], lower[:, 1])
        zu = np.interp(xs, upper[:, 0], upper[:, 1])
        C = np.stack([xs, 0.5 * (zl + zu)], -1)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
        self.s, self.C = s, C
        self.cs = CubicSpline(s, C)
        T = unit(self.cs(s, 1))
        self.N = np.stack([-T[:, 1], T[:, 0]], -1)                  # across, pointing up (T runs forward)
        self.half = 0.5 * (zu - zl) * T[:, 0]                       # the half height measured square to the middle
        self.length = float(s[-1])
        self.half_min = float(self.half.min())

    def to_xz(self, P):
        """(s, w) points (n, 2) -> (x, z)."""
        P = np.atleast_2d(np.asarray(P, float))
        s = np.clip(P[:, 0], 0.0, self.length)
        C = self.cs(s)
        T = unit(self.cs(s, 1))
        N = np.stack([-T[:, 1], T[:, 0]], -1)
        return C + P[:, 1:2] * N

    def half_at(self, s):
        return np.interp(s, self.s, self.half)


def spiral(c, R, r_end, turns, phi0, sense, step=0.012):
    """A spiral about c from radius R at angle phi0 (radians) inward to r_end over turns, turning by sense (+1
    anticlockwise, -1 clockwise in (s, w)): points (n, 2)."""
    span = 2 * math.pi * turns
    n = max(12, int(span * 0.6 * R / step))
    t = np.linspace(0.0, 1.0, n)
    r = R * (r_end / R) ** t                                         # a logarithmic spiral
    ph = phi0 + sense * span * t
    return np.stack([c[0] + r * np.cos(ph), c[1] + r * np.sin(ph)], -1)


def bezier(P0, T0, P1, T1, n=24):
    """A cubic from P0 leaving along T0 to P1 arriving along T1, its handles a third of the chord."""
    P0, P1 = np.asarray(P0, float), np.asarray(P1, float)
    d = np.linalg.norm(P1 - P0) / 3.0
    A, B = P0 + unit(T0) * d, P1 - unit(T1) * d
    t = np.linspace(0.0, 1.0, n)[:, None]
    return (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * A + 3 * (1 - t) * t ** 2 * B + t ** 3 * P1


def running_scroll(length, half, c):
    """A running scroll along a band length long and half (its least half height) each side of its middle: a stem
    waving along it, and from each wave a branch curling back into the bay under (or over) its crest, ending in a
    berry, with leaves along stem and branch; the stem ends forward in a curl of its own. c: the design's sizes
    (decor_1797.json's carving)."""
    m = c["margin_m"]
    n_half = max(2, int(round((length - 2 * m - c["end_curl"] * half) / (0.5 * c["wave_m"]))))
    lam = 2 * (length - 2 * m - c["end_curl"] * half) / n_half      # the wave stretched to fit a whole number of humps
    amp = c["amp"] * half
    R = c["spiral_r"] * half
    s0 = m
    s1 = s0 + n_half * 0.5 * lam
    ss = np.linspace(s0, s1, max(40, int((s1 - s0) / 0.015)))
    stem = np.stack([ss, amp * np.sin(2 * math.pi * (ss - s0) / lam)], -1)
    # the stem's forward end: on into a curl over the band's middle
    end_c = np.array([s1 + 0.55 * c["end_curl"] * half, 0.0])
    T_end = np.array([1.0, 2 * math.pi * amp / lam * math.cos(2 * math.pi * (s1 - s0) / lam)])
    sense_end = 1.0 if T_end[1] >= 0 else -1.0
    r_e = 0.5 * c["end_curl"] * half
    phi_e = -sense_end * math.pi / 2                                 # enter the curl at its bottom (top) moving forward
    curl = spiral(end_c, r_e, 0.12 * r_e, c["spiral_turns"], phi_e, sense_end)
    lead = bezier(stem[-1], T_end, curl[0], [math.cos(phi_e + sense_end * math.pi / 2),
                                              math.sin(phi_e + sense_end * math.pi / 2)], 16)
    main = np.concatenate([stem, lead[1:-1], curl])
    r0, r1 = c["stem_r_m"], c["branch_r_m"][1]
    rmain = np.concatenate([np.full(len(stem) + len(lead) - 2, r0), np.linspace(r0, r1, len(curl))])
    strokes, leaves, berries = [(main, rmain)], [], [(curl[-1], 1.3 * r1)]
    rng = np.random.default_rng(c.get("seed", 9))
    for k in range(n_half):
        sg = 1.0 if k % 2 == 0 else -1.0                             # a crest (+) or a trough (-)
        sk = s0 + (k + 0.5) * 0.5 * lam
        cc = np.array([sk + c["spiral_shift"] * R, -sg * c["spiral_w"] * half])
        # leave the stem past the crest and come down (up) into the spiral's after side, turning back into the bay
        sb = sk + c["branch_at"] * 0.5 * lam
        Pb = np.array([sb, amp * math.sin(2 * math.pi * (sb - s0) / lam)])
        Tb = unit(np.array([1.0, 2 * math.pi * amp / lam * math.cos(2 * math.pi * (sb - s0) / lam)]))
        Tb = unit(Tb + np.array([0.0, -sg * 0.9]))
        phi0 = 0.0                                                   # the spiral's start: its forward side
        sense = -sg                                                  # crest: clockwise; trough: anticlockwise
        sp = spiral(cc, R, c["spiral_end"] * R, c["spiral_turns"], phi0, sense)
        T1 = np.array([-math.sin(phi0) * sense, math.cos(phi0) * sense])
        br = bezier(Pb, Tb, sp[0], T1, 20)
        P = np.concatenate([br[:-1], sp])
        rr = np.interp(np.arange(len(P)), [0, len(br) - 1, len(P) - 1], [c["branch_r_m"][0], c["branch_r_m"][0],
                                                                         c["branch_r_m"][1]])
        strokes.append((P, rr))
        berries.append((sp[-1], 1.4 * c["branch_r_m"][1]))
        # leaves: along the branch's lead and the spiral's outer turn, each pointing on along it, alternate sides
        Lf, Wf, Hf = c["leaf_m"]
        for j, f in enumerate(np.linspace(0.18, 0.62, c["leaves_per_scroll"])):
            i = int(f * len(P))
            d = unit(P[min(i + 2, len(P) - 1)] - P[max(i - 2, 0)])
            side = 1.0 if j % 2 == 0 else -1.0
            nrm = np.array([-d[1], d[0]]) * side
            a = math.radians(c["leaf_angle_deg"] + rng.uniform(-8, 8))
            dl = unit(math.cos(a) * d + math.sin(a) * nrm)
            leaves.append((P[i] + nrm * rr[i] * 0.6, dl, Lf * rng.uniform(0.85, 1.1), Wf, Hf))
        # a leaf at the stem where the branch springs, pointing back over the crest
        d = -Tb
        leaves.append((Pb, unit(d + np.array([0.0, sg * 0.6])), 0.8 * Lf, Wf, Hf))
    return {"strokes": strokes, "leaves": leaves, "berries": berries}


def tube(secs, mat):
    """sweep's closed tube through the sections, its two end caps each turned along its own end's direction (sweep
    turns both by the first-to-last chord, which faces a cap inward where the path curls back on itself, as a scroll's
    stroke does)."""
    S = np.asarray(secs, float)
    V, F, M = sweep(S, mat, closed=True, caps=False)
    n, m = S.shape[:2]
    c = S.mean(1)
    k0 = next((k for k in range(1, n) if np.linalg.norm(c[k] - c[0]) > 1e-9), 1)
    k1 = next((k for k in range(n - 2, -1, -1) if np.linalg.norm(c[k] - c[-1]) > 1e-9), n - 2)
    for end, d in ((0, c[0] - c[k0]), (n - 1, c[-1] - c[k1])):
        P = S[end]
        nrm = sum(np.cross(P[k] - P[0], P[k + 1] - P[0]) for k in range(1, m - 1))
        cap = list(range(end * m, end * m + m))
        F.append(tuple(cap if nrm @ d > 0 else cap[::-1]))
        M.append(mat)
    return V, F, M


def stroke_mesh(P3, N3, rad, mat, sides=8, sink=0.3):
    """A half-buried round moulding along P3 (n, 3) on a surface whose outward normals are N3, of radius rad (n,): its
    centre sink radii out of the surface (0.3: a little over half of it shows)."""
    P3, N3 = np.asarray(P3, float), unit(N3)
    T = np.gradient(P3, axis=0)
    T = unit(T)
    Nn = unit(N3 - (N3 * T).sum(1)[:, None] * T)
    B = np.cross(T, Nn)
    a = np.arange(sides) * 2 * math.pi / sides
    secs = []
    for p, n, b, r in zip(P3, Nn, B, rad):
        c = p + n * sink * r
        secs.append(c + r * (np.cos(a)[:, None] * b + np.sin(a)[:, None] * n))
    return tube(secs, mat)


def leaf_mesh(base, d, nrm, length, width, height, mat, nu=7, nv=5):
    """A leaf in low relief on a surface: a pointed blade from base along d (both 3D, square to nrm), its middle
    ridged; the top only (it lies on the surface)."""
    d = unit(d)
    nrm = unit(nrm)
    w_ax = np.cross(nrm, d)
    V, F = [], []
    for i in range(nu + 1):
        t = i / nu
        hw = width * 0.5 * math.sin(math.pi * min(1.0, t * 1.08)) ** 0.8 * (1.0 - 0.25 * t)
        for j in range(nv):
            v = -1.0 + 2.0 * j / (nv - 1)
            h = height * (1.0 - v * v) ** 0.6 * math.sin(math.pi * t) ** 0.5 + 0.004
            V.append(base + d * (t * length) + w_ax * (v * hw) + nrm * (h - 0.006))
    for i in range(nu):
        for j in range(nv - 1):
            a = i * nv + j
            F.append((a, a + nv, a + nv + 1, a + 1))
    V = np.array(V)
    # every face out along nrm
    f = F[0]
    fn = np.cross(V[f[1]] - V[f[0]], V[f[3]] - V[f[0]])
    if fn @ nrm < 0:
        F = [q[::-1] for q in F]
    return V, F, [mat] * len(F)


def leaf_draped(base, d, length, width, height, mat, to_xz, place, nu=7, nv=5, seat=None):
    """leaf_mesh laid over a curved surface: its outline drawn in the design's plane (base, d: 2D) and each of its
    points set on the surface there (to_xz, then place) and raised along the surface's normal, so a long leaf follows
    a surface that curves away under it; on a seat, each point set on the faces themselves, so its rim stays sunk."""
    base = np.asarray(base, float)
    d = np.asarray(d, float) / np.linalg.norm(d)
    w_ax = np.array([-d[1], d[0]])
    P2, H = [], []
    for i in range(nu + 1):
        t = i / nu
        hw = width * 0.5 * math.sin(math.pi * min(1.0, t * 1.08)) ** 0.8 * (1.0 - 0.25 * t)
        for j in range(nv):
            v = -1.0 + 2.0 * j / (nv - 1)
            P2.append(base + d * (t * length) + w_ax * (v * hw))
            H.append(height * (1.0 - v * v) ** 0.6 * math.sin(math.pi * t) ** 0.5 + 0.004 - 0.006)
    P3, N3 = place(to_xz(np.array(P2)))
    N3 = unit(N3)
    if seat is not None:
        H = np.array(H) + seat.along(P3, N3)
    V = P3 + N3 * np.array(H)[:, None]
    F = []
    for i in range(nu):
        for j in range(nv - 1):
            a = i * nv + j
            F.append((a, a + nv, a + nv + 1, a + 1))
    f = F[len(F) // 2]
    fn = np.cross(V[f[1]] - V[f[0]], V[f[3]] - V[f[0]])
    if fn @ N3[f[0]] < 0:
        F = [q[::-1] for q in F]
    return V, F, [mat] * len(F)


class Seat:
    """The surface the work is laid on as it is meshed: its flat faces lie inside a curved surface by their chords'
    sag, so a leaf or a berry set on the curve itself can stand off them, its open underside showing. along() says how
    far the faces lie under the curve, and the work is set down onto them (leaf_draped, berry_mesh)."""

    def __init__(self, V, F, reach=0.05):
        from mathutils.bvhtree import BVHTree
        self.tree = BVHTree.FromPolygons(np.asarray(V, float).tolist(), [tuple(int(i) for i in f) for f in F])
        self.reach = reach

    def along(self, P3, N3):
        """for each point P3 with its outward normal N3: how far under it the faces lie along N3 (negative): of the
        faces a line along the normal crosses within reach either way, the one nearest the point; 0 where that one lies
        over it (the work is only sunk deeper there) or none is found"""
        out = np.zeros(len(P3))
        for i, (p, n) in enumerate(zip(np.asarray(P3, float), unit(N3))):
            start, gone, best = p + self.reach * n, 0.0, None
            while gone < 2.0 * self.reach:
                hit = self.tree.ray_cast(start.tolist(), (-n).tolist(), 2.0 * self.reach - gone)
                if hit[0] is None:
                    break
                gone += hit[3]
                h = self.reach - gone                       # the face's height over the point along the normal
                if best is None or abs(h) < abs(best):
                    best = h
                gone += 1e-5
                start = p + (self.reach - gone) * n
            if best is not None:
                out[i] = min(best, 0.0)
        return out


def berry_mesh(c, nrm, r, mat, n=8, seat=None):
    """A small half-round boss (the spiral's eye), its rim sunk a fifth of its radius; on a seat, set down so the rim is
    sunk so far under the faces wherever they lie lowest beneath it."""
    nrm = unit(nrm)
    a = unit(np.cross(nrm, [0.0, 0.0, 1.0] if abs(nrm[2]) < 0.9 else [1.0, 0.0, 0.0]))
    b = np.cross(nrm, a)
    if seat is not None:
        th = np.arange(n) * 2 * math.pi / n
        under = np.concatenate([[c], c + r * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b)])
        c = c + nrm * float(seat.along(under, np.tile(nrm, (len(under), 1))).min())
    rings = []
    for k in range(4):
        el = math.pi / 2 * k / 4
        rr, hh = r * math.cos(el), r * math.sin(el)
        th = np.arange(n) * 2 * math.pi / n
        rings.append(c + nrm * (hh - 0.2 * r) + rr * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b))
    V = np.concatenate(rings + [np.array([c + nrm * 0.8 * r])])
    F = []
    for k in range(3):
        for j in range(n):
            a0, a1 = k * n + j, k * n + (j + 1) % n
            F.append((a0, a1, a1 + n, a0 + n))
    top = len(V) - 1
    for j in range(n):
        F.append((3 * n + j, 3 * n + (j + 1) % n, top))
    # out from the boss's axis
    f = F[0]
    fn = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
    out = V[list(f)].mean(0) - c
    if fn @ out < 0:
        F = [q[::-1] for q in F]
    return V, F, [mat] * len(F)


def tri_count(F):
    """the triangles faces make: a face of n corners is n - 2 of them"""
    return sum(len(f) - 2 for f in F)


def relief(mesh, design, to_xz, place, mat, drape=False, seat=None):
    """Lay a design on a surface: strokes as half-round mouldings, leaves and berries. to_xz maps the design's (s, w)
    to elevation (x, z); place(XZ) gives the surface's points and outward normals there. drape: each leaf follows
    the surface under it (leaf_draped) rather than lying flat on its tangent plane at its base. seat: the surface as
    meshed (Seat), on whose faces the draped leaves and the berries are set down"""
    n_tri = 0
    for P2, rad in design["strokes"]:
        XZ = to_xz(P2)
        P3, N3 = place(XZ)
        V, F, M = stroke_mesh(P3, N3, rad, mat)
        mesh.add(V, F, M)
        n_tri += tri_count(F)
    for base, d, L, W, H in design["leaves"]:
        if drape:
            V, F, M = leaf_draped(base, d, L, W, H, mat, to_xz, place, seat=seat)
            mesh.add(V, F, M)
            n_tri += tri_count(F)
            continue
        XZ = to_xz(np.array([base, np.asarray(base) + 0.05 * np.asarray(d)]))
        P3, N3 = place(XZ)
        d3 = P3[1] - P3[0]
        d3 = d3 - (d3 @ N3[0]) * N3[0]
        V, F, M = leaf_mesh(P3[0], d3, N3[0], L, W, H, mat)
        mesh.add(V, F, M)
        n_tri += tri_count(F)
    for c, r in design["berries"]:
        P3, N3 = place(to_xz(np.array([c])))
        V, F, M = berry_mesh(P3[0], N3[0], r, mat, seat=seat)
        mesh.add(V, F, M)
        n_tri += tri_count(F)
    return n_tri


def seated(parts, carriers, min_m=0.0005, rim_m=0.0001):
    """Is the carving on what it is carved on? parts: {name: (V (n, 3), triangles (m, 3))} of the carving; carriers:
    {name: [(V, triangles), ...]} what each may lie on. Every piece of it (a stroke, a leaf, a berry: its connected
    pieces) must reach into a carrier, and every vertex of an open rim (a leaf or a berry is open underneath) lie in a
    carrier, or within rim_m of its faces, or in another piece of the same carving that reaches in (a berry in a
    scroll's eye). In a carrier: min_m behind its nearest face (by that face's normal), or, where carriers' closed
    blocks overlap (a roof slab let into a cornice), inside one of them by the faces a ray crosses on its way out
    (entries less exits, the middle of three rays). Returns {name: report}; a report's loose pieces and standing rims
    are what fails."""
    from mathutils.bvhtree import BVHTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    def tree(V, T):
        return BVHTree.FromPolygons(np.asarray(V, float).tolist(), np.asarray(T, np.int64).tolist(), all_triangles=True)

    def joined(items):
        Vs, Ts, base = [], [], 0
        for Vc, Tc in items:
            Vs.append(np.asarray(Vc, float))
            Ts.append(np.asarray(Tc, np.int64) + base)
            base += len(Vc)
        return np.concatenate(Vs), np.concatenate(Ts)

    def closed(T):
        e = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), 1)
        return not (np.unique(e, axis=0, return_counts=True)[1] == 1).any()

    def signed(t, P):
        out = np.empty(len(P))
        for i, p in enumerate(P):
            q, n, _, _ = t.find_nearest(p.tolist())
            out[i] = np.dot(p - np.asarray(q), np.asarray(n)) if q is not None else np.inf
        return out
    RAYS = unit(np.array([[0.267, 0.534, 0.802], [-0.6, 0.31, -0.737], [0.11, -0.913, 0.393]]))

    def within(t, p):
        """inside a closed block: of three rays out from p, the middle count of exits less entries is positive"""
        if t is None:
            return False
        counts = []
        for d in RAYS:
            o, w = np.asarray(p, float), 0
            for _ in range(200):
                loc, n, _, _ = t.ray_cast(o.tolist(), d.tolist(), 100.0)
                if loc is None:
                    break
                w += 1 if np.dot(d, n) > 0 else -1
                o = np.asarray(loc) + d * 1e-6
            counts.append(w)
        return sorted(counts)[1] > 0
    report = {}
    for name, (V, T) in parts.items():
        V, T = np.asarray(V, float), np.asarray(T, np.int64)
        tc = tree(*joined(carriers[name]))
        shut = [(Vc, Tc) for Vc, Tc in carriers[name] if closed(np.asarray(Tc, np.int64))]
        tw = tree(*joined(shut)) if shut else None
        n = len(V)
        E = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
        k, lab = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(n, n)), directed=False)
        sd = signed(tc, V)
        deep = np.full(k, np.inf)
        np.minimum.at(deep, lab, sd)
        seat = deep <= -min_m
        for j in np.where(~seat)[0]:
            seat[j] = any(within(tw, p) for p in V[lab == j][::4])
        loose = [{"at_m": np.round(V[lab == j].mean(0), 3).tolist(), "nearest_mm": round(float(deep[j]) * 1000, 1)}
                 for j in np.where(~seat)[0]]
        u, cnt = np.unique(np.sort(E, 1), axis=0, return_counts=True)
        rim = np.unique(u[cnt == 1])
        tp = tree(V, T)
        tlab = lab[T[:, 0]]
        off = []
        for vi in rim[sd[rim] > rim_m]:
            p = V[vi]
            if within(tw, p):
                continue
            others = [h for h in tp.find_nearest_range(p.tolist(), 0.04)
                      if tlab[h[2]] != lab[vi] and seat[tlab[h[2]]]]
            if others:
                q, nn, _, _ = min(others, key=lambda h: h[3])
                if np.dot(p - np.asarray(q), np.asarray(nn)) <= rim_m:
                    continue
            off.append((float(sd[vi]), np.round(p, 3).tolist()))
        off.sort(reverse=True)
        report[name] = {"pieces": int(k), "loose": loose, "rim_vertices": int(len(rim)), "rims_standing": len(off),
                        "rim_most_off_mm": round(off[0][0] * 1000, 2) if off else None,
                        "rims_at_m": [p for _, p in off[:6]]}
    return report
