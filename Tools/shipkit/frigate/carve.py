"""Carved relief (docs/shipkit-9): a running scroll's strokes and leaves drawn in a band's own coordinates, and laid as
half-round mouldings and low leaves on a surface; used on the head's trailboards and the stern's frieze.
    band = Band(lower_xz, upper_xz)                 the strip between two edges (elevation), by its middle line
    design = running_scroll(band.length, band.half_min, cfg)
    relief(mesh, design, band.to_xz, place, mat)     place(XZ (n, 2)) -> (points (n, 3), outward normals (n, 3))
A design is {"strokes": [(points (n, 2) in (s, w) metres along and across the band, radius (n,))], "leaves": [(base
(2,), direction (2,), length, width, height)], "berries": [(centre (2,), radius)]}.
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


def leaf_draped(base, d, length, width, height, mat, to_xz, place, nu=7, nv=5):
    """leaf_mesh laid over a curved surface: its outline drawn in the design's plane (base, d: 2D) and each of its
    points set on the surface there (to_xz, then place) and raised along the surface's normal, so a long leaf follows
    a surface that curves away under it."""
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


def berry_mesh(c, nrm, r, mat, n=8):
    """A small half-round boss (the spiral's eye)."""
    nrm = unit(nrm)
    a = unit(np.cross(nrm, [0.0, 0.0, 1.0] if abs(nrm[2]) < 0.9 else [1.0, 0.0, 0.0]))
    b = np.cross(nrm, a)
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


def relief(mesh, design, to_xz, place, mat, drape=False):
    """Lay a design on a surface: strokes as half-round mouldings, leaves and berries. to_xz maps the design's (s, w)
    to elevation (x, z); place(XZ) gives the surface's points and outward normals there. drape: each leaf follows
    the surface under it (leaf_draped) rather than lying flat on its tangent plane at its base"""
    n_tri = 0
    for P2, rad in design["strokes"]:
        XZ = to_xz(P2)
        P3, N3 = place(XZ)
        V, F, M = stroke_mesh(P3, N3, rad, mat)
        mesh.add(V, F, M)
        n_tri += tri_count(F)
    for base, d, L, W, H in design["leaves"]:
        if drape:
            V, F, M = leaf_draped(base, d, L, W, H, mat, to_xz, place)
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
        V, F, M = berry_mesh(P3[0], N3[0], r, mat)
        mesh.add(V, F, M)
        n_tri += tri_count(F)
    return n_tri
