"""The frigate's guns (docs/shipkit-8): the long 24-pounders on their truck carriages along the gun deck and the
32-pounder carronades on their slides along the quarterdeck and forecastle, with their breechings, side tackles and
train tackles, the ringbolts they are made fast to, the long guns' housing bolts and muzzle lashings, and their falls
coiled down on deck.

    from guns import Guns;  gn = Guns(sk, dk, skin_parts).build();  gn.meshes;  gn.instances();  gn.game_data()

Sizes are guns_1797.json's, each with its source or marked an estimate. Units: metres in the ship's frame (X forward,
Y starboard, Z up), as the other slices. This module runs in Blender's Python (the brackets' faces are cut with
Blender's constrained Delaunay triangulation, the checks use its BVH trees).

Each kind of gun, its carriage (or bed and slide), quoin and trucks are one set of meshes placed at every port it
serves (Blender's linked duplicates, the game's instanced meshes); each gun's gear and ironwork are its own, rigged at
its own port (the side's lean and curve and the deck's sheer and camber differ from port to port and side to side), and
so are the carronades' chocks (each fitted to its own waterway):

* a port's frame: origin on the deck under the point where the port's middle line meets the side's inner face at the
  ringbolts' height (ring_height_in), X out through the port (level, along the side's outward normal there), Z square
  to the deck (on the gun deck, to the plane fitted to the deck under the gun's trucks: seat()), Y = Z x X: the gun's
  right as the game shows it (the ship's frame is Unreal's, Y to starboard). A port side gun is its starboard twin
  turned, not mirrored, so the lock stays on the gun's right; its surroundings are its twin's mirrored (env());
* each gun's ringbolts (and on the gun deck its housing bolts over the port and the train tackle's ringbolt in the
  deck) are fitted to its own side and deck: each eye stands standoff_in off the face where it comes nearest, its shank
  driven into it (fit_irons); each port's frame is turned a fraction of a degree about Z so that the side stands as
  far from its ringbolts on either side of the port (balance(): yaw_deg);
* the long gun's carriage frame: origin on the deck under the middle of the trunnions, X toward the muzzle, Z up; in
  its port's frame it stands housed (hauled out with the quoin out and the breech on the bed until the muzzle comes up
  against the side over the port's head, lashed there, the lid shut), run in (where the recoil brings it and it is
  loaded: the muzzle a foot inside the port, the barrel level on its quoin) or run out (its front an inch off the
  side); the barrel's frame: origin on the trunnions' axis, X along the bore, elevated about its Y (the quoin's place
  for each elevation: Long24.quoin_x); each truck's frame: origin at its centre, Y along its axletree arm;
* the carronade's slide frame: origin on the deck on the fighting bolt's axis, X along the slide toward the port; it
  turns about its Z to train the gun (train_deg each way); the bed's frame: origin on the slide's top under the lug's
  bolt, X along the slide (run out at the slide's fore end, recoiled along it by the breeching's play); the barrel's
  frame: origin on the lug's bolt, X along the bore.

The gear (breeching, tackles, falls, coils, the side rings, the housed gun's muzzle lashing) is drawn for each pose:
the long guns housed (lids shut, shown), run in and run out, the carronades run out (shown) and recoiled. A rope's
length is the same in every pose: the long gun's breeching taut when run in (the shortest path round the breech,
through the loop) hangs slack in bights housed and run out, the carronade's slack when run out is taut when it
recoils; each tackle's fall is coiled down in a Flemish coil that holds whatever the tackle doesn't. The coils and the
ropes lying on deck follow the gun's own deck (deck_field), which bends away from a port's plane with the sheer;
rests() measures how each coil lies on it.
"""
import json
import math
import os
import re

import numpy as np

import loft
from deck import Part, in_poly, newell, solid
from rigging import dedupe, fillet, tube
from spars import box, loft_solid, unit

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)

IRON, WOOD, ROPE, BLOCK, SHADOW, OAK = "Iron", "Carriage", "Hemp", "Block", "Shadow", "Oak"
BLACK = "Blacking"                    # the barrels' black: lamp black in oil over the cast iron
POSES24 = ("housed", "run_in", "run_out")
POSES32 = ("run_out", "recoil")
TAG = {"housed": "Housed", "run_in": "RunIn", "run_out": "RunOut", "recoil": "Recoil"}
COLL24 = {"housed": "Guns_Housed", "run_in": "Guns_RunIn", "run_out": "Guns_RunOut"}
COLL32 = {"run_out": "Carronades_RunOut", "recoil": "Carronades_Recoil"}


def I(v):
    """inches (a number or a list) to metres"""
    return np.asarray(v, float) * IN


# ---- frames (4x4: the columns are the frame's axes and origin in its parent) -------------------------------------
def frame(o, X, Z):
    """origin o, X made square to Z, Y = Z x X"""
    Z = unit(Z)
    X = unit(np.asarray(X, float) - (np.asarray(X, float) @ Z) * Z)
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = X, np.cross(Z, X), Z, o
    return T


def tr(v):
    T = np.eye(4)
    T[:3, 3] = v
    return T


def rot(axis, deg):
    a = unit(axis)
    th = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    T = np.eye(4)
    T[:3, :3] = np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)
    return T


def pts(T, P):
    return np.asarray(P, float) @ T[:3, :3].T + T[:3, 3]


def vecs(T, D):
    return np.asarray(D, float) @ T[:3, :3].T


def inv(T):
    R = T[:3, :3]
    Ti = np.eye(4)
    Ti[:3, :3] = R.T
    Ti[:3, 3] = -R.T @ T[:3, 3]
    return Ti


# ---- meshes --------------------------------------------------------------------------------------------------------
class GPart(Part):
    """deck.Part with a label on every face (what it is: 'bracket', 'truck', 'breeching'...) for the checks; cur is the
    label the next pieces get."""

    def __init__(self):
        super().__init__()
        self.lab = []
        self.cur = "part"

    def add(self, V, F, mat, uv=None):
        super().add(V, F, mat, uv)
        self.lab += [self.cur] * len(F)

    def add_m(self, V, F, mats):
        """vertices once, faces each with its own material"""
        V = np.array(V, float).reshape(-1, 3)
        self.V.append(V)
        self.F += [tuple(self.n + int(i) for i in f) for f in F]
        self.M += list(mats)
        self.U.append(np.zeros((len(V), 4)))
        self.n += len(V)
        self.lab += [self.cur] * len(F)

    def extend(self, other):
        super().extend(other)
        self.lab += other.lab

    def moved(self, T):
        """a copy taken through T (4x4)"""
        out = GPart()
        out.V = [pts(T, V) for V in self.V]
        out.F, out.M, out.U, out.lab, out.n = list(self.F), list(self.M), [U.copy() for U in self.U], list(self.lab), self.n
        return out

    def mirrored_y(self):
        """a copy mirrored across its XZ plane, faces turned to face out"""
        out = GPart()
        out.V = [V * np.array([1.0, -1.0, 1.0]) for V in self.V]
        out.F = [tuple(f[::-1]) for f in self.F]
        out.M, out.U, out.lab, out.n = list(self.M), [U.copy() for U in self.U], list(self.lab), self.n
        return out

    def tri_arrays(self):
        """vertices and triangles (fans of each face), with each triangle's label"""
        V, F, _, _ = self.arrays()
        T, L = [], []
        for f, lab in zip(F, self.lab):
            for k in range(1, len(f) - 1):
                T.append((f[0], f[k], f[k + 1]))
                L.append(lab)
        return V, np.array(T, int).reshape(-1, 3), np.array(L)


def lathe_closed(M, prof, mats, n, T=np.eye(4), closed=False):
    """A solid of revolution about the local X axis: prof [(s, r)] round its meridian (s along X, r out from the axis),
    from the axis back to the axis (r 0 at both ends), or a loop that never reaches it (closed: a ring); mats the
    material of each segment. The angle starts at local +Z and turns toward +Y. Faces outward: walking the profile, the
    solid is on the right. T places it."""
    prof = np.asarray(prof, float)
    th = (np.arange(n) + 0.5) * 2 * math.pi / n
    c, s_ = np.cos(th), np.sin(th)
    idx, V = [], []
    for s, r in prof:
        if r < 1e-9:
            idx.append([len(V)])
            V.append((s, 0.0, 0.0))
        else:
            idx.append(list(range(len(V), len(V) + n)))
            V += [(s, r * s_[i], r * c[i]) for i in range(n)]
    V = np.array(V)
    F, Mt = [], []
    segs = list(range(len(prof) - 1)) + ([len(prof) - 1] if closed else [])
    for k in segs:
        k1 = (k + 1) % len(prof)
        a, b = idx[k], idx[k1]
        ds, dr = prof[k1] - prof[k]
        if (len(a) == 1 and len(b) == 1) or abs(ds) + abs(dr) < 1e-12:
            continue
        if len(a) == 1:
            sf = [(a[0], b[(i + 1) % n], b[i]) for i in range(n)]
        elif len(b) == 1:
            sf = [(a[i], a[(i + 1) % n], b[0]) for i in range(n)]
        else:
            sf = [(a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]) for i in range(n)]
        thm = math.pi / n * 2                                 # face 0 lies between the first two angles
        want = np.array([-dr, ds * math.sin(thm), ds * math.cos(thm)])
        if newell(V[list(sf[0])]) @ want < 0:
            sf = [f[::-1] for f in sf]
        F += sf
        Mt += [mats[k] if not isinstance(mats, str) else mats] * len(sf)
    M.add_m(pts(T, V), F, Mt)


def cylinder(M, a, b, r, mat, n=12):
    """a round bar from a to b, its ends capped flat"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = unit(b - a)
    ref = EZ if abs(u @ EZ) < 0.9 else EX
    ref = unit(ref - (ref @ u) * u)
    v = np.cross(u, ref)
    t = np.arange(n) * 2 * math.pi / n
    ring = np.cos(t)[:, None] * ref + np.sin(t)[:, None] * v
    solid(M, [a + r * ring, b + r * ring], mat)


def torus(M, c, ax1, ax2, R, r, mat, n=16, m=8):
    """a ring: centre c, in the plane of ax1 and ax2, centre-line radius R, bar radius r"""
    t = np.arange(n) * 2 * math.pi / n
    P = np.asarray(c, float) + R * (np.cos(t)[:, None] * unit(ax1) + np.sin(t)[:, None] * unit(ax2))
    tube(M, P, r, mat, n=m, closed=True)


def obox(M, c, X, Y, Z, h, mat):
    """an oriented box: centre c, axes X, Y, Z (made square), half sizes h"""
    Z = unit(Z)
    X = unit(np.asarray(X, float) - (np.asarray(X, float) @ Z) * Z)
    Y = np.cross(Z, X)
    box(M, np.asarray(c, float), X, Y, Z, h[0], h[1], h[2], mat)


def hexa(M, P8, mat):
    """a six-sided solid from its corners: P8 = bottom four then top four, each counter-clockwise from above"""
    P8 = np.asarray(P8, float)
    solid(M, [P8[:4], P8[4:]], mat)


def slab(M, outline, holes, yin, yout, mat, n_hole=14):
    """A plank standing in the XZ plane: outline (k, 2) of (x, z) points, holes [(cx, cz, r)] through it, its faces the
    planes y = yin(x) and y = yout(x) (yout > yin everywhere). The faces are cut with Blender's constrained Delaunay
    triangulation; the walls round the outline and each hole are quads."""
    try:
        from mathutils import Vector, geometry
    except ImportError:
        import bpy  # noqa: F401
        from mathutils import Vector, geometry
    O = np.asarray(outline, float)
    if 0.5 * np.sum(O[:, 0] * np.roll(O[:, 1], -1) - np.roll(O[:, 0], -1) * O[:, 1]) < 0:
        O = O[::-1]                                             # counter-clockwise in (x, z)
    rings = [O]
    for cx, cz, r in holes:
        t = np.arange(n_hole) * 2 * math.pi / n_hole
        rings.append(np.stack([cx + r * np.cos(t), cz + r * np.sin(t)], 1))
    P2 = np.concatenate(rings)
    E, k0 = [], 0
    for rg in rings:
        m = len(rg)
        E += [(k0 + k, k0 + (k + 1) % m) for k in range(m)]
        k0 += m
    out = geometry.delaunay_2d_cdt([Vector((float(a), float(b))) for a, b in P2], E, [], 0, 1e-9, True)
    if len(out[0]) != len(P2):
        raise ValueError(f"slab: the triangulation added or merged points ({len(out[0])} for {len(P2)})")
    to_in = [ids[0] for ids in out[3]]
    T = np.array([[to_in[i] for i in f] for f in out[2]])
    cen = P2[T].mean(1)
    keep = in_poly(cen, O)
    for rg in rings[1:]:
        keep &= ~in_poly(cen, rg)
    T = T[keep]
    k = len(P2)
    Vi = np.stack([P2[:, 0], yin(P2[:, 0]), P2[:, 1]], 1)
    Vo = np.stack([P2[:, 0], yout(P2[:, 0]), P2[:, 1]], 1)
    V = np.concatenate([Vi, Vo])
    F = []
    for t in T:                                                 # the outer face looks +y, the inner -y
        fo = (k + t[0], k + t[1], k + t[2])
        F.append(fo if newell(V[list(fo)])[1] > 0 else fo[::-1])
        fi = (t[0], t[1], t[2])
        F.append(fi if newell(V[list(fi)])[1] < 0 else fi[::-1])
    k0 = 0
    for j, rg in enumerate(rings):
        m = len(rg)
        cen2 = rg.mean(0)
        for a in range(m):
            b = (a + 1) % m
            q = (k0 + a, k0 + b, k + k0 + b, k + k0 + a)
            e = rg[b] - rg[a]
            nrm2 = np.array([e[1], -e[0]])                      # right of the edge: out of a counter-clockwise outline
            if j > 0:                                           # a hole: its wall faces its middle
                mid = 0.5 * (rg[a] + rg[b])
                nrm2 = cen2 - mid
            want = np.array([nrm2[0], 0.0, nrm2[1]])
            F.append(q if newell(V[list(q)]) @ want > 0 else q[::-1])
        k0 += m
    M.add(V, F, mat)


def strap(M, P_xz, yc, broad, thick, mat):
    """an iron strap of rectangular section (broad along y, thick across the path) along a path in the XZ plane at y=yc"""
    P = np.asarray(P_xz, float)
    n = len(P)
    T = np.empty_like(P)
    T[0], T[-1] = unit(P[1] - P[0]), unit(P[-1] - P[-2])
    for i in range(1, n - 1):
        T[i] = unit(unit(P[i] - P[i - 1]) + unit(P[i + 1] - P[i]))
    rings = []
    for p, t in zip(P, T):
        nn = np.array([-t[1], t[0]])
        c = np.array([p[0], yc, p[1]])
        w = np.array([nn[0], 0.0, nn[1]]) * thick / 2
        b = EY * broad / 2
        rings.append(np.array([c - w - b, c - w + b, c + w + b, c + w - b]))
    solid(M, rings, mat)


def coil_points(c, X, Y, r_rope, r0, length, step_deg=12.0, sense=1.0):
    """a Flemish coil: a flat spiral of rope (radius r_rope) on the plane through c spanned by X and Y (lying on it),
    from radius r0 outward, turns touching, holding the given length of rope. Returns its centre line from the inside
    end to the outside end and the outer end's tangent."""
    pitch = 2.05 * r_rope
    pts_, s, th = [], 0.0, 0.0
    dth = math.radians(step_deg)
    prev = None
    Zc = np.cross(X, Y)
    while True:
        rho = r0 + pitch * th / (2 * math.pi)
        p = c + rho * (math.cos(sense * th) * X + math.sin(sense * th) * Y) + r_rope * Zc
        if prev is not None:
            s += float(np.linalg.norm(p - prev))
        pts_.append(p)
        prev = p
        if s >= length:
            break
        th += dth
    P = np.array(pts_)
    return P, unit(P[-1] - P[-2])


# ---- rope solvers --------------------------------------------------------------------------------------------------
class Revolved:
    """a solid of revolution as an obstacle for a rope: profile [(s, r)] about the axis through o along ax (ref: where
    the angle starts, for points on the axis). push(P, r) moves points within r of it out to r from its surface, each in
    its own meridian plane (the nearest point of a solid of revolution lies in it)."""

    def __init__(self, o, ax, ref, prof):
        self.o, self.ax = np.asarray(o, float), unit(ax)
        self.ref = unit(np.asarray(ref, float) - (np.asarray(ref, float) @ self.ax) * self.ax)
        P = np.asarray(prof, float)
        self.P = P
        self.A, self.B = P[:-1], P[1:]

    def R(self, s):
        """the radius at s (the larger where the profile steps)"""
        out = np.zeros_like(s)
        for (s0, r0), (s1, r1) in zip(self.A, self.B):
            lo, hi = min(s0, s1), max(s0, s1)
            m = (s >= lo) & (s <= hi)
            if not m.any():
                continue
            if abs(s1 - s0) < 1e-12:
                out[m] = np.maximum(out[m], max(r0, r1))
            else:
                out[m] = np.maximum(out[m], r0 + (r1 - r0) * (s[m] - s0) / (s1 - s0))
        return out

    def push(self, Q, r):
        Q = np.asarray(Q, float)
        d = Q - self.o
        s = d @ self.ax
        radial = d - s[:, None] * self.ax
        rho = np.linalg.norm(radial, axis=1)
        dirn = np.where(rho[:, None] > 1e-9, radial / np.maximum(rho, 1e-12)[:, None], self.ref)
        q = np.stack([s, rho], 1)
        AB = self.B - self.A
        L2 = np.maximum((AB ** 2).sum(1), 1e-18)
        t = np.clip(((q[:, None, :] - self.A[None]) * AB[None]).sum(2) / L2[None], 0, 1)
        C = self.A[None] + t[..., None] * AB[None]                     # nearest point on each segment
        dd = np.linalg.norm(q[:, None, :] - C, axis=2)
        k = dd.argmin(1)
        near = C[np.arange(len(q)), k]
        dist = dd[np.arange(len(q)), k]
        inside = (rho < self.R(s)) & (s > self.P[:, 0].min()) & (s < self.P[:, 0].max())
        move = inside | (dist < r)
        if not move.any():
            return Q
        out = Q.copy()
        for i in np.nonzero(move)[0]:
            v = q[i] - near[i]
            nv = float(np.linalg.norm(v))
            if nv < 1e-9:                                              # on the surface: the profile's left is out
                seg = AB[k[i]]
                v = np.array([-seg[1], seg[0]])
                nv = float(np.linalg.norm(v))
            elif inside[i]:                                            # inside: out is away from the point
                v = -v
            qn = near[i] + v / nv * r
            out[i] = self.o + qn[0] * self.ax + max(qn[1], 0.0) * dirn[i]
        return out


class Boxed:
    """an oriented box as an obstacle (T: its frame, h: half sizes): a point within r of it is moved out through the
    nearest face"""

    def __init__(self, T, h):
        self.T, self.Ti, self.h = T, inv(T), np.asarray(h, float)

    def push(self, Q, r):
        L = pts(self.Ti, Q)
        hh = self.h + r
        inside = np.all(np.abs(L) < hh, axis=1)
        if not inside.any():
            return Q
        out = L.copy()
        for i in np.nonzero(inside)[0]:
            gap = hh - np.abs(L[i])
            a = int(gap.argmin())
            out[i, a] = math.copysign(hh[a], L[i, a] if L[i, a] != 0 else 1.0)
        return pts(self.T, out)


class Cyl:
    """a short cylinder (a truck) as an obstacle: axis through o along ax from -h to +h, radius R"""

    def __init__(self, o, ax, R, h):
        self.o, self.ax, self.Rr, self.h = np.asarray(o, float), unit(ax), R, h

    def push(self, Q, r):
        d = Q - self.o
        s = d @ self.ax
        rad = d - s[:, None] * self.ax
        rho = np.linalg.norm(rad, axis=1)
        inside = (np.abs(s) < self.h + r) & (rho < self.Rr + r)
        if not inside.any():
            return Q
        out = Q.copy()
        for i in np.nonzero(inside)[0]:
            g_side = self.Rr + r - rho[i]
            g_end = self.h + r - abs(s[i])
            if g_side < g_end:
                u = rad[i] / rho[i] if rho[i] > 1e-9 else unit(np.cross(self.ax, EX))
                out[i] = self.o + s[i] * self.ax + (self.Rr + r) * u
            else:
                out[i] = self.o + math.copysign(self.h + r, s[i]) * self.ax + rad[i]
        return out


class Floor:
    """the deck as a plane through o with normal n: points come up to r above it"""

    def __init__(self, o, n):
        self.o, self.n = np.asarray(o, float), unit(n)

    def push(self, Q, r):
        h = (Q - self.o) @ self.n
        low = h < r
        if not low.any():
            return Q
        out = Q.copy()
        out[low] += (r - h[low])[:, None] * self.n
        return out

    def h(self, x, y):
        """the deck's height at (x, y) (a level plane through o)"""
        return np.full(np.shape(x), float(self.o[2]))


class DeckField:
    """the deck as a height over the plane z = 0 of a port's frame, sampled on a grid (inches; Guns.deck_field): the
    deck's own shape where it bends away from that plane. h(x, y) by bilinear interpolation (held at the grid's edge);
    points come up to r above it"""

    def __init__(self, xs, ys, H):
        self.xs, self.ys, self.H = np.asarray(xs, float), np.asarray(ys, float), np.asarray(H, float)

    def h(self, x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        fx = np.clip((x - self.xs[0]) / (self.xs[1] - self.xs[0]), 0.0, len(self.xs) - 1.000001)
        fy = np.clip((y - self.ys[0]) / (self.ys[1] - self.ys[0]), 0.0, len(self.ys) - 1.000001)
        i, j = np.floor(fx).astype(int), np.floor(fy).astype(int)
        u, v = fx - i, fy - j
        H = self.H
        return ((1 - u) * (1 - v) * H[i, j] + u * (1 - v) * H[i + 1, j] + (1 - u) * v * H[i, j + 1]
                + u * v * H[i + 1, j + 1])

    def push(self, Q, r):
        z = self.h(Q[:, 0], Q[:, 1]) + r
        low = Q[:, 2] < z
        if not low.any():
            return Q
        out = Q.copy()
        out[low, 2] = z[low]
        return out


def resample(P, step):
    """a polyline resampled at about step apart (its corners kept)"""
    P = dedupe(np.asarray(P, float))
    out = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        L = float(np.linalg.norm(b - a))
        k = max(1, int(math.ceil(L / step)))
        for j in range(1, k + 1):
            out.append(a + (b - a) * j / k)
    return np.array(out)


def length(P):
    return float(np.linalg.norm(np.diff(np.asarray(P, float), axis=0), axis=1).sum())


def taut(A, B, bodies, r, n=48, iters=3000):
    """a taut rope from A to B: the shortest way round the bodies (each with push(P, r)), by shortening a polyline and
    pushing it out of them in turns"""
    P = A + (B - A) * np.linspace(0, 1, n)[:, None]
    for b in bodies:
        P[1:-1] = b.push(P[1:-1], r)
    for _ in range(iters):
        P[1:-1] = 0.5 * (P[:-2] + P[2:])
        for b in bodies:
            P[1:-1] = b.push(P[1:-1], r)
    return P


def taut_from(P, bodies, r, iters=3000):
    """a taut rope from a first guess P (its ends held): shortened and pushed out of the bodies in turns"""
    P = np.asarray(P, float).copy()
    for b in bodies:
        P[1:-1] = b.push(P[1:-1], r)
    for _ in range(iters):
        P[1:-1] = 0.5 * (P[:-2] + P[2:])
        for b in bodies:
            P[1:-1] = b.push(P[1:-1], r)
    return P


def _keep_lengths(P, seg):
    """one pass of the segments' length constraint, the ends held: the even segments then the odd (each set at once,
    none sharing a point)"""
    n = len(P)
    for par in (0, 1):
        i = np.arange(par, n - 1, 2)
        if not len(i):
            continue
        d = P[i + 1] - P[i]
        dl = np.linalg.norm(d, axis=1)
        c = ((dl - seg) / np.maximum(dl, 1e-12))[:, None] * d
        wa = np.where(i == 0, 0.0, np.where(i + 1 == n - 1, 1.0, 0.5))
        wb = np.where(i + 1 == n - 1, 0.0, np.where(i == 0, 1.0, 0.5))
        P[i] += wa[:, None] * c
        P[i + 1] -= wb[:, None] * c


def hang(A, B, L, r, bodies, n=56, iters=900, bias=None, g=None, start=None):
    """a slack rope of length L from A to B under gravity (g: the down direction, a step per iteration), resting on what
    it meets (bodies: the deck among them) and pushed by bias (a small sideways step, so a bight lies to one side):
    position-based dynamics, the segments kept their length (a last settling without gravity or bias puts it back
    to its length where pushing stretched it). start: the first guess (n points)"""
    A, B = np.asarray(A, float), np.asarray(B, float)
    g = -EZ * 0.004 if g is None else g
    seg = L / (n - 1)
    if start is None:
        chord = float(np.linalg.norm(B - A))
        t = np.linspace(0, 1, n)
        side = unit(bias) if bias is not None else -EZ
        lo, hi = 0.0, L
        for _ in range(60):                                      # a sine bight toward side, of the rope's length
            amp = 0.5 * (lo + hi)
            P = A + (B - A) * t[:, None] + amp * np.sin(math.pi * t)[:, None] * side
            if length(P) < L:
                lo = amp
            else:
                hi = amp
        P = A + (B - A) * t[:, None] + lo * np.sin(math.pi * t)[:, None] * side
        if chord < 1e-6:
            P = A + lo * np.sin(math.pi * t)[:, None] * side
    else:
        P = np.asarray(start, float).copy()
    for it in range(iters + 300):
        settle = it >= iters
        if not settle:
            P[1:-1] += g
            if bias is not None:
                P[1:-1] += bias
        for _ in range(8 if settle else 4):
            _keep_lengths(P, seg)
            for b in bodies:
                P[1:-1] = b.push(P[1:-1], r)
    return P


def scaled(M, f):
    """a copy of a GPart with its vertices scaled by f (inches to metres)"""
    out = GPart()
    out.V = [V * f for V in M.V]
    out.F, out.M, out.U, out.lab, out.n = list(M.F), list(M.M), [U.copy() for U in M.U], list(M.lab), M.n
    return out


def eyebolt(M, face, n, along, eye, bar, shank, into, standoff, collar=True):
    """an eyebolt driven into a face (point face, outward normal n): its shank into the face by into, its eye standing
    off it by standoff in the plane of n and along. Returns the eye's centre and the eye plane's normal."""
    n, along = unit(n), unit(along)
    along = unit(along - (along @ n) * n)
    c = face + n * (standoff + bar + eye)
    torus(M, c, n, along, eye, bar, IRON, n=14, m=6)
    cylinder(M, face - n * into, face + n * (standoff + 1.2 * bar), shank, IRON, n=8)
    if collar:
        cylinder(M, face - n * 0.05, face + n * 0.12, shank + 0.35, IRON, n=10)
    return c, unit(np.cross(n, along))


def block_dims(L):
    """an iron-bound single block's sizes (inches) for its length L: the shell's breadth (w, across in the sheave's
    plane) and thickness (t, along the pin), the sheave's radius to the rope's centre (rs), the strap's breadth and
    thickness and how far it stands off the shell, the becket's eye and bar, the swivel's height over the strap"""
    return {"w": 0.78 * L, "t": 0.42 * L, "rs": 0.27 * L, "broad": 0.12 * L, "thick": 0.05 * L, "off": 0.02,
            "r_e": 0.09 * L, "bar_e": 0.031 * L, "swivel": 0.14 * L}


def block_top(L):
    """the swivel's top over a block's centre (where its hook's shank meets it)"""
    d = block_dims(L)
    return L / 2 + d["off"] + d["thick"] + d["swivel"] + 0.02 * L


def block_shell(M, L, mat=BLOCK, g2=None, a=None):
    """a single block's shell in its frame (origin the sheave's centre, X across the shell in the sheave's plane, Y
    along the pin, Z toward the crown): a squared oval rounded off at the cheeks, as running.block_mesh draws it.
    g2, a: its mortise, the slot between the cheeks (|y| < g2) the sheave turns in, cut as a U of half-width a round
    the sheave's centre and open at the tail (the swallow the rope's two parts run out of); without them solid"""
    w, t = 0.78 * L, 0.42 * L
    n, p = 20, 2.6
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    out2 = np.stack([w / 2 * np.sign(c) * np.abs(c) ** (2 / p), L / 2 * np.sign(s) * np.abs(s) ** (2 / p)], 1)[::-1]

    def ring(ph):
        k = abs(math.cos(ph)) ** 0.55
        return np.stack([out2[:, 0] * (0.55 + 0.45 * k), np.full(n, t / 2 * math.sin(ph)),
                         out2[:, 1] * (0.75 + 0.25 * k)], 1)
    if g2 is None:
        loft_solid(M, [ring(ph) for ph in np.linspace(-math.pi / 2, math.pi / 2, 7)], mat)
        return w, t
    ph_g = math.asin(min(0.9, 2 * g2 / t))
    for sg in (1.0, -1.0):                                       # the cheeks
        solid(M, [ring(sg * ph) for ph in np.linspace(ph_g, math.pi / 2, 5)], mat)
    k = math.cos(ph_g) ** 0.55
    W, H = w / 2 * (0.55 + 0.45 * k), L / 2 * (0.75 + 0.25 * k)
    if a >= 0.95 * W:
        raise SystemExit(f"guns: a {L:.1f} in block's mortise ({a:.2f} in each side) is too wide for its shell")
    al = math.acos((a / W) ** (p / 2))
    tau = np.linspace(-al, math.pi + al, 33)
    ct, st = np.cos(tau), np.sin(tau)
    outer = np.stack([W * np.sign(ct) * np.abs(ct) ** (2 / p), H * np.sign(st) * np.abs(st) ** (2 / p)], 1)
    zt = float(outer[0, 1])
    up_l = np.stack([np.full(4, -a), np.linspace(zt, 0.0, 5)[1:]], 1)
    ang = np.linspace(math.pi, 0.0, 15)[1:-1]
    arc = np.stack([a * np.cos(ang), a * np.sin(ang)], 1)
    dn_r = np.stack([np.full(4, a), np.linspace(0.0, zt, 5)[:-1]], 1)
    slab(M, np.concatenate([outer, up_l, arc, dn_r]), [], lambda x: np.full_like(x, -g2 - 0.01),
         lambda x: np.full_like(x, g2 + 0.01), mat)
    return w, t


def loop_band(M, P, axis, broad, thick, mat):
    """an iron band of rectangular section round the closed path P (lying in a plane square to axis): broad along
    axis, thick across the path in its plane"""
    P = np.asarray(P, float)
    n = len(P)
    ax = unit(axis)
    rings = []
    for i in range(n):
        t = unit(P[(i + 1) % n] - P[i - 1])
        nn = unit(np.cross(t, ax))
        w, b = nn * thick / 2, ax * broad / 2
        rings.append([P[i] - w - b, P[i] - w + b, P[i] + w + b, P[i] + w - b])
    V = np.array(rings).reshape(-1, 3)
    F = []
    for i in range(n):
        j = (i + 1) % n
        pc = 0.5 * (P[i] + P[j])
        for k in range(4):
            k1 = (k + 1) % 4
            f = (4 * i + k, 4 * i + k1, 4 * j + k1, 4 * j + k)
            Q = V[list(f)]
            F.append(f if newell(Q) @ (Q.mean(0) - pc) > 0 else f[::-1])
    M.add(V, F, mat)


def iron_block(M, T, L, r_rope, becket=False):
    """an iron-bound single block at frame T (origin the sheave's centre, X across the shell in the sheave's plane, Y
    along the pin, Z toward the crown): the shell with its mortise cut for a rope of radius r_rope (open at the tail:
    the swallow), the sheave on its pin, the iron strap round the shell in the pin's plane (over the crown, down the
    cheeks with the pin through it, under the tail between the rope's two parts), a swivel on the strap's crown for its
    hook and (becket) an eye forged under the strap's tail, in its plane, for a rope's standing part (clinched round
    its bar, the rope's two parts lie in the sheave's plane and lead fair to the other block). Returns the points in T's frame the
    ropes and hook meet: the sheave's two sides (+X, -X), the becket's eye and the swivel's top, and the sizes"""
    d = block_dims(L)
    B = GPart()
    B.cur = M.cur
    w, t, rs = d["w"], d["t"], d["rs"]
    th, off, br = d["thick"], d["off"], d["broad"]
    g2 = r_rope + 0.06
    block_shell(B, L, g2=g2, a=rs + r_rope + 0.08)
    cylinder(B, [0, -(g2 - 0.03), 0], [0, g2 - 0.03, 0], rs - r_rope - 0.05, BLOCK, n=20)      # the sheave
    yp = t / 2 + off + th
    cylinder(B, [0, -yp - 0.04, 0], [0, yp + 0.04, 0], 0.055 * L, IRON, n=8)                 # the pin
    for sg in (1.0, -1.0):                                                                   # its heads
        cylinder(B, [0, sg * (yp - 0.02), 0], [0, sg * (yp + 0.04 * L), 0], 0.1 * L, IRON, n=10)
    zc = lambda ph: L / 2 * (0.75 + 0.25 * abs(math.cos(ph)) ** 0.55)                        # noqa: E731
    phs = np.linspace(-math.pi / 2, math.pi / 2, 17)
    S2 = np.array([(t / 2 * math.sin(ph), zc(ph)) for ph in phs]
                  + [(t / 2, z) for z in np.linspace(0.375 * L, -0.375 * L, 7)[1:-1]]
                  + [(t / 2 * math.sin(ph), -zc(ph)) for ph in phs[::-1]]
                  + [(-t / 2, z) for z in np.linspace(-0.375 * L, 0.375 * L, 7)[1:-1]])
    area = 0.5 * np.sum(S2[:, 0] * np.roll(S2[:, 1], -1) - np.roll(S2[:, 0], -1) * S2[:, 1])
    N2 = []
    for i in range(len(S2)):
        e = S2[(i + 1) % len(S2)] - S2[i - 1]
        nv = np.array([e[1], -e[0]]) * (1.0 if area > 0 else -1.0)
        N2.append(nv / np.linalg.norm(nv))
    S2 = S2 + np.array(N2) * (off + th / 2)
    loop_band(B, np.stack([np.zeros(len(S2)), S2[:, 0], S2[:, 1]], 1), EX, br, th, IRON)    # the strap
    zs = L / 2 + off + th
    top = np.array([0.0, 0.0, zs + d["swivel"]])
    cylinder(B, [0, 0, zs - 0.5 * th], top, 0.07 * L, IRON, n=8)                             # the swivel
    cylinder(B, top - [0, 0, 0.04 * L], top + [0, 0, 0.02 * L], 0.1 * L, IRON, n=8)
    bk = None
    if becket:
        r_e, bar_e = d["r_e"], d["bar_e"]
        bk = np.array([0.0, 0.0, -zs - r_e - 0.5 * bar_e])
        torus(B, bk, EY, EZ, r_e, bar_e, IRON, n=12, m=6)          # forged on the strap, in its plane
    M.extend(B.moved(T))
    out = {"sheave+": np.array([rs, 0, 0]), "sheave-": np.array([-rs, 0, 0]), "top": top + [0, 0, 0.02 * L],
           "becket": bk, "becket_r": d["r_e"], "becket_bar": d["bar_e"], "w": w, "t": t, "rs": rs, "tail": zs}
    return {k: (pts(T, v[None])[0] if isinstance(v, np.ndarray) else v) for k, v in out.items()}


def hook(M, F, t, v, r_h, rho, shank):
    """a hook whose throat holds the bar through F (the bar's tangent t there) and pulls toward v (its block): the
    centre line in the plane square to t, the throat's bottom rho beyond F away from v, the back running up to the
    swivel shank + rho toward v, the bill turned up on the other side. Returns the shank's top and the pull's direction"""
    t = unit(t)
    v = unit(v - (v @ t) * t)
    w = np.cross(t, v)
    a = np.linspace(0.0, math.pi, 12)
    cup = F[None] + rho * (-np.cos(a)[:, None] * w[None] - np.sin(a)[:, None] * v[None])
    top = F + v * (rho + shank)
    P = np.concatenate([[top, F - w * rho * 0.55 + v * (0.5 * shank + rho)], [F - w * rho + v * 0.45 * rho], cup,
                        [F + w * rho + v * 0.55 * rho, F + w * rho * 0.75 + v * 1.05 * rho]])
    tube(M, fillet(P, 0.5 * rho), r_h, IRON, n=8)
    return top, v


# ---- the gear: ringbolts, hooks, blocks and ropes ---------------------------------------------------------------------
TARRED = "Tarred"


class Torus:
    """a ring's bar as an obstacle for a rope: centre C, in the plane of a1 and a2, centre-line radius R, bar radius bar"""

    def __init__(self, C, a1, a2, R, bar):
        self.C, self.n, self.ref = np.asarray(C, float), unit(np.cross(a1, a2)), unit(a1)
        self.R, self.bar = R, bar

    def push(self, Q, r):
        d = Q - self.C
        ip = d - (d @ self.n)[:, None] * self.n
        rho = np.linalg.norm(ip, axis=1)
        dirn = np.where(rho[:, None] > 1e-9, ip / np.maximum(rho, 1e-12)[:, None], self.ref)
        near = self.C + self.R * dirn
        v = Q - near
        dist = np.linalg.norm(v, axis=1)
        m = dist < self.bar + r
        if not m.any():
            return Q
        out = Q.copy()
        vv = np.where(dist[:, None] > 1e-9, v / np.maximum(dist, 1e-12)[:, None], -dirn)
        out[m] = near[m] + vv[m] * (self.bar + r)
        return out


class Plane:
    """a flat face as an obstacle (the side's inner face): points come out to r in front of it (o on it, n out)"""

    def __init__(self, o, n):
        self.o, self.n = np.asarray(o, float), unit(n)

    def push(self, Q, r):
        h = (Q - self.o) @ self.n
        low = h < r
        if not low.any():
            return Q
        out = Q.copy()
        out[low] += (r - h[low])[:, None] * self.n
        return out


def taut_via(A, B, k, proj, bodies, r, start, iters=6000):
    """a taut rope from A to B through a ring: point k of the first guess (start, n points) is held in the ring's
    opening by proj; the rest are pulled straight and pushed out of the bodies in turns"""
    P = np.asarray(start, float).copy()
    P[0], P[-1] = A, B
    for _ in range(iters):
        P[1:-1] = 0.5 * (P[:-2] + P[2:])
        P[k] = proj(P[k])
        for b in bodies:
            P[1:-1] = b.push(P[1:-1], r)
        P[k] = proj(P[k])
    return P


def on_circle(C, nn, R, v):
    """the point of a circle (centre C, its plane's normal nn, radius R) furthest toward v, and the circle's tangent
    there: where a hook or a rope pulled toward v bears on a ring's bar"""
    nn = unit(nn)
    v = np.asarray(v, float)
    rad = v - (v @ nn) * nn
    if np.linalg.norm(rad) < 1e-9:
        rad = np.cross(nn, EX if abs(nn @ EX) < 0.9 else EY)
    rad = unit(rad)
    return np.asarray(C, float) + R * rad, unit(np.cross(nn, rad))


def bolt_eye(M, eye_c, n_face, up, depth, sp):
    """an eyebolt's eye standing out of a face (outward normal n_face), in the plane of n_face and up, centred at eye_c;
    its shank running back along -n_face to depth behind the eye's centre. Returns the eye's hole axis"""
    n_face = unit(n_face)
    up = unit(np.asarray(up, float) - (np.asarray(up, float) @ n_face) * n_face)
    torus(M, eye_c, n_face, up, sp["eye"], sp["bar"], IRON, n=14, m=6)
    cylinder(M, eye_c - n_face * sp["eye"], eye_c - n_face * depth, sp["shank"], IRON, n=8)
    return unit(np.cross(n_face, up))


def ring_in(M, eye_c, b, n_face, pull, sp):
    """the ring hanging in an eye (centre eye_c, hole axis b) swung toward pull, never back into the face (outward
    normal n_face), and drawn by it until its bar bears on the inside of the eye's bar (0.06 in off it). Returns the
    ring as a circle: (centre, its plane's normal, radius, bar)"""
    pull = np.asarray(pull, float)
    u = pull - (pull @ b) * b
    u = unit(u) if np.linalg.norm(u) > 1e-9 else unit(n_face)
    if u @ n_face < 0.2:                                        # it lies back against the face at the most
        u = unit(u - (u @ n_face) * n_face + 0.2 * unit(n_face))
    C = eye_c + u * (sp["ring"] + sp["eye"] - sp["bar"] - sp["ring_bar"] - 0.06)
    torus(M, C, u, b, sp["ring"], sp["ring_bar"], IRON, n=20, m=6)
    return C, unit(np.cross(u, b)), sp["ring"], sp["ring_bar"]


def seizing(M, c, d, w, b, rho, r):
    """a seizing: turns of small stuff round two ropes (radius r, centres c +- rho w, running along d), drawn as a
    band round both"""
    R = r + max(0.1, 0.18 * r)
    a = np.linspace(-math.pi / 2, math.pi / 2, 7)
    ring = np.concatenate([c + rho * w + R * (np.cos(a)[:, None] * w + np.sin(a)[:, None] * b),
                           c - rho * w + R * (-np.cos(a)[:, None] * w - np.sin(a)[:, None] * b)])
    width = 1.3 * r
    solid(M, [ring - d * width / 2, ring + d * width / 2], TARRED)


def clinch(M, F, b, d, rho, r, lc):
    """a rope's end turned back round a bar and seized to its own standing part: the bar at F (its direction b), the
    rope leaving along d, rho the bight's radius (the bar's radius and the rope's). Returns the rope's centre line from
    the end's tip round the bar to where the standing part leaves the seizings, past them along d (so whatever way the
    rope then leads, both its parts lie in both seizings); the two seizings go into M"""
    b = unit(b)
    d = unit(d - (d @ b) * b)
    w = np.cross(d, b)
    ph = np.linspace(math.pi, 0.0, 13)
    bight = F[None] + rho * (-np.sin(ph)[:, None] * d[None] + np.cos(ph)[:, None] * w[None])
    out = np.concatenate([[F - rho * w + d * lc, F - rho * w + d * 0.5 * lc], bight,
                          [F + rho * w + d * 0.5 * lc, F + rho * w + d * 1.15 * lc]])
    cur = M.cur
    M.cur = "seizing"
    for s in (0.4, 0.8):
        seizing(M, F + d * s * lc, d, w, b, rho, r)
    M.cur = cur
    return out


def rim(c_face, n_face, X, R, r, k=7):
    """a rope's centre line round the rim of a hole's mouth (the hole's centre on the face c_face, n_face out of the
    face, radius R), the rope pulled along the face toward X: from inside the hole, pressed against its wall, round the
    rim's edge to just off the face"""
    n_face = unit(n_face)
    X = unit(X - (X @ n_face) * n_face)
    E = c_face + X * R
    rr = r + 0.05
    a = np.linspace(0, math.pi / 2, k)
    return E[None] + rr * (-np.cos(a)[:, None] * X[None] + np.sin(a)[:, None] * n_face[None])


def hooked_block(M, circ, v, L, r_h, xup, becket, r_rope):
    """a single block hooked into a ring or an eye (circ: centre, plane normal, radius, bar), hanging toward v, its
    sheave's plane holding v and xup, its mortise cut for a rope of radius r_rope. Returns iron_block's points and the
    block's frame"""
    C, nn, R, bar = circ
    F, t = on_circle(C, nn, R, v)
    M.cur = "hook"
    top, vv = hook(M, F, t, v, r_h, bar + r_h + 0.06, 0.14 * L)
    Zb = -vv
    T = frame(top + vv * block_top(L), np.asarray(xup, float) - (np.asarray(xup, float) @ Zb) * Zb, Zb)
    M.cur = "block"
    return iron_block(M, T, L, r_rope, becket=becket), T


def sheave_arc(T, rs, b0, b1, k=13):
    """a rope's centre line round a block's sheave (frame T: X across, Z to the crown) from angle b0 to b1 (0: +X)"""
    be = np.linspace(b0, b1, k)
    return pts(T, np.stack([rs * np.cos(be), np.zeros(k), rs * np.sin(be)], 1))


def flemish(c, r, r0, length, toward, sense=1.0, floor=None):
    """a Flemish coil on the deck (the plane z = 0 of the frame, or floor: a DeckField it lies on) centred at c, turned
    so its outer end leads off toward the point toward. Returns its centre line from the outer end to the inner, the
    outer end's lead (outward), its turns and its outer radius (to the rope's centre)"""
    P, t = coil_points(np.array([c[0], c[1], 0.0]), EX, EY, r, r0, length, sense=sense)
    want = math.atan2(toward[1] - c[1], toward[0] - c[0])
    a = want - math.atan2(t[1], t[0])
    T = tr([c[0], c[1], 0.0]) @ rot(EZ, math.degrees(a)) @ tr([-c[0], -c[1], 0.0])
    turns = (len(P) - 1) * 12.0 / 360.0
    Q = pts(T, P)[::-1]
    if floor is not None:
        Q[:, 2] = floor.h(Q[:, 0], Q[:, 1]) + r
    return Q, vecs(T, t[None])[0], turns, float(np.linalg.norm(P[-1, :2] - np.asarray(c[:2], float)))


def tackle(M, circ_a, circ_b, L, r, r_h, xup, coil_c, coil_len, coil_r0, sense=1.0, bodies=(), g=None, dry=False,
           floor=None, coils=None):
    """A gun tackle purchase (two single blocks): A hooked into circ_a, B into circ_b. The rope's standing part is made
    fast to A's becket, rove through B, back through A, and its fall leaves A for the deck (the frame's z = 0, or floor:
    a DeckField), where it lies coiled down in a Flemish coil centred at coil_c holding coil_len of rope. Returns the
    rope's length outside the coil and where things are; dry: measure only (the fall's hang is a given length, so
    nothing needs solving); coils: a list the coil's centre line is added to (for Guns.rests)"""
    va = unit(circ_b[0] - circ_a[0])
    for _ in range(3):                                         # each block hangs toward the other's hook
        Fa, _ = on_circle(*circ_a[:3], va)
        Fb, _ = on_circle(*circ_b[:3], -va)
        va = unit(Fb - Fa)
    M = GPart() if dry else M
    A, TA = hooked_block(M, circ_a, va, L, r_h, xup, True, r)
    B, TB = hooked_block(M, circ_b, -va, L, r_h, xup, False, r)
    rs = A["rs"]
    M.cur = "tackle_rope"
    arcA = sheave_arc(TA, rs, 0.0, math.pi)                     # in at A's +X, out at -X: the fall
    bk = A["becket"]
    TBi = inv(TB)

    def becket_at(aim):
        """where the standing part's clinch bears on A's becket (its eye in the strap's plane), the bar's direction
        there turned so the standing part leaves on B's entry side (-X)"""
        F, t = on_circle(bk, TA[:3, 0], A["becket_r"], aim - bk)
        d = aim - F
        d = d - (d @ t) * t
        return F, (t if np.cross(unit(d), t) @ TA[:3, 0] < 0 else -t)
    th0 = math.pi
    for _ in range(4):                    # the standing part from A's becket meets B's sheave where it is tangent to it
        aim = pts(TB, np.array([[rs * math.cos(th0), 0.0, rs * math.sin(th0)]]))[0]
        Fk, tk = becket_at(aim)
        cl = clinch(GPart(), Fk, tk, aim - Fk, A["becket_bar"] + r + 0.03, r, 3.5 * r)
        p = pts(TBi, cl[-1][None])[0]
        D = math.hypot(p[0], p[2])
        if D <= rs + 0.1:
            raise SystemExit(f"guns: a tackle's blocks stand too close ({D:.2f} in from the sheave's centre)")
        th0 = (math.atan2(p[2], p[0]) - math.acos(rs / D)) % (2 * math.pi)
        if th0 < 0.5 * math.pi:
            raise SystemExit("guns: a tackle's standing part comes to its block from over the crown")
    aim = pts(TB, np.array([[rs * math.cos(th0), 0.0, rs * math.sin(th0)]]))[0]
    Fk, tk = becket_at(aim)
    cl = clinch(M, Fk, tk, aim - Fk, A["becket_bar"] + r + 0.03, r, 3.5 * r)
    arcB = sheave_arc(TB, rs, th0, 0.0, k=max(13, int(13 * th0 / math.pi)))   # round B's crown, out at its +X
    S = arcA[-1] + va * (0.5 * L + 1.0)
    coil, lead, turns, r_out = flemish(coil_c, r, coil_r0, coil_len, S, sense, floor)
    E = coil[0]
    E2 = E + lead * 1.5
    if floor is not None:
        E2[2] = float(floor.h(E2[0], E2[1])) + r
    Lh = float(np.linalg.norm(E2 - S) + 0.3 * max(float(S[2]), 0.0))
    head = np.concatenate([cl, arcB, arcA, [S]])
    outside = float(length(head) + Lh + 1.5)
    shells = float(np.linalg.norm(TB[:3, 3] - TA[:3, 3]) - L)
    irons = shells - 2.0 * (A["tail"] - L / 2) - 2.0 * A["becket_r"] - 1.5 * A["becket_bar"]
    info = {"A": TA[:3, 3], "B": TB[:3, 3], "span": float(np.linalg.norm(Fb - Fa)), "fall_hang": Lh,
            "coil": {"centre": [float(coil_c[0]), float(coil_c[1])], "turns": round(turns, 1), "radius": round(r_out + r, 2)},
            "gap_between_blocks": {"shells": round(shells, 2), "irons": round(irons, 2)}}
    if dry:
        return outside, info
    g = -EZ * 0.12 if g is None else g
    shells = [Boxed(Tk_, [0.5 * A["w"], 0.5 * A["t"], 0.5 * L]) for Tk_ in (TA, TB)]   # the fall clears both blocks
    fall = hang(S, E2, Lh, r, [floor if floor is not None else Floor([0, 0, 0], EZ)] + list(bodies) + shells, n=48,
                iters=700, g=g)
    rope = np.concatenate([head, fall[1:], [E], coil[1:]])
    if coils is not None:
        coils.append(coil)
    tube(M, rope, r, ROPE, n=8)
    return outside, info


def flintlock(M, lk, vent, Rf, axis_z, s0):
    """a gun's flintlock (the US Navy fitted them from 1797): its pan on the vent's patch on the gun's right,
    pan_gap_in from the vent's edge with a priming channel cut between, the steel (frizzen) shut over the pan with its
    face standing at the pan's after end, the plate further round the barrel joined to the pan by a bridle, and the cock
    on the plate's fore part reaching back to hold its flint just forward of the steel's face (the lanyard pulls it
    aft). Rf(s): the barrel's radius at s from the base ring's back; its axis at height axis_z over its frame's origin,
    s0 the origin's s. Returns the pan's top middle and the vent's mouth in the barrel's frame"""
    M.cur = "lock"
    sv, rv = vent["x_in"], vent["radius_in"]
    ptop = axis_z + Rf(sv) + vent["patch_in"][2]                 # the vent patch's top
    xv = sv - s0
    pl_, pw, ph = 1.0, 0.8, 0.35                                 # the pan: along, across, high
    yp = rv + lk["pan_gap_in"] + pw / 2
    obox(M, [xv, yp, ptop + ph / 2 - 0.05], EX, EY, EZ, [pl_ / 2, pw / 2, ph / 2], IRON)
    y0, y1 = 0.6 * rv, yp - pw / 2 + 0.1                          # the priming channel, from the vent to the pan
    obox(M, [xv, 0.5 * (y0 + y1), ptop + 0.008], EX, EY, EZ, [0.08, 0.5 * (y1 - y0), 0.012], SHADOW)
    pt = ptop + ph - 0.05                                        # the pan's top
    obox(M, [xv - 0.02, yp, pt + 0.04], EX, EY, EZ, [pl_ / 2 + 0.02, pw / 2 + 0.03, 0.04], IRON)       # the steel's cover
    xf = xv - pl_ / 2 + 0.1
    obox(M, [xf, yp, pt + 0.5], EX, EY, EZ, [0.1, pw / 2 - 0.04, 0.5], IRON)                          # its face
    obox(M, [xf + 0.27, yp, pt + 0.62], EX, EY, EZ, [0.13, 0.26, 0.11], SHADOW)                       # the flint
    jaw = np.array([xf + 0.68, yp, pt + 0.62])
    obox(M, jaw, EX, EY, EZ, [0.28, 0.3, 0.26], IRON)                                                 # the cock's jaws
    # the plate, around_deg round the barrel toward +Y, its middle at x_in
    phi = math.radians(lk["around_deg"])
    rho = np.array([0.0, math.sin(phi), math.cos(phi)])
    tang = np.array([0.0, math.cos(phi), -math.sin(phi)])
    s = lk["x_in"]
    R = Rf(s)
    ax = lambda ss: np.array([ss - s0, 0.0, axis_z])            # noqa: E731
    lx, lw, lt = lk["plate_in"]
    obox(M, ax(s) + rho * (R + lt / 2 - 0.12), EX, tang, rho, [lx / 2, lw / 2, lt / 2 + 0.12], IRON)
    # the bridle from the pan's outer side to the plate's inner edge
    phi_i = phi - (lw / 2 - 0.15) / Rf(sv)
    pin = ax(sv) + (Rf(sv) + lt / 2) * np.array([0.0, math.sin(phi_i), math.cos(phi_i)])
    cylinder(M, [xv, yp + pw / 2 - 0.08, ptop + 0.12], pin, 0.13, IRON, n=8)
    # the cock: its tumbler on the plate's fore part, its neck curving up and back to the jaws
    sc = s + lx / 2 - 1.0
    c0 = ax(sc) + rho * (Rf(sc) + lt)
    cylinder(M, c0 - rho * 0.1, c0 + rho * 0.3, 0.42, IRON, n=10)
    c1 = jaw + np.array([0.25, 0.0, -0.1])
    mid = 0.5 * (c0 + c1) + rho * 0.6 + EZ * 0.9
    tube(M, fillet(np.array([c0 + rho * 0.25, mid, c1]), 0.6), 0.2, IRON, n=6)
    return np.array([xv, yp, pt]), np.array([xv, 0.0, ptop])


def vent_patch(M, v, Rf, axis_z, s0):
    """the vent's raised patch on top of the barrel and its hole"""
    M.cur = "vent"
    px, py, pz = v["patch_in"]
    top = axis_z + Rf(v["x_in"]) + pz
    obox(M, [v["x_in"] - s0, 0, top - (pz + 0.15) / 2], EX, EY, EZ, [px / 2, py / 2, (pz + 0.15) / 2], BLACK)
    cylinder(M, [v["x_in"] - s0, 0, top - 0.03], [v["x_in"] - s0, 0, top + 0.012], v["radius_in"], SHADOW, n=10)


class Long24:
    """the long 24-pounder and its truck carriage (guns_1797.json long24 and carriage24), built in inches in their own
    frames (barrel: origin on the trunnions' axis, X along the bore; carriage: origin on the deck under the trunnions;
    trucks: origin at the truck's centre, Y along its axle)"""

    def __init__(self, c):
        self.c, self.g, self.k = c, c["long24"], c["carriage24"]
        g, k = self.g, self.k
        self.prof = np.array(g["profile"], float)
        tn = g["trunnion"]
        self.s_t, self.up = tn["x_in"], tn["below_axis_in"]           # the trunnions' s, the bore's axis over them
        self.zt = k["trunnion_over_deck_in"]
        bi = k["bracket_inner_y_in"]
        x0 = tn["rimbase_radius_in"]                                  # the inner face clears the rimbase's fore edge
        self.slope = (bi["rear"] - bi["at_trunnion"]) / (k["bracket_x_in"][0] - x0)
        self.y_in = lambda x: bi["at_trunnion"] + self.slope * (np.asarray(x, float) - x0)
        self.y_out = lambda x: self.y_in(x) + k["bracket_thick_in"]
        self.axles = {}
        for nm in ("fore_axle", "hind_axle"):
            a = k[nm]
            arm_z = a["truck_radius_in"]
            bot = arm_z - a["below_arm_in"]
            self.axles[nm] = dict(x=a["x_in"], x0=a["x_in"] - a["body_in"][0] / 2, x1=a["x_in"] + a["body_in"][0] / 2,
                                  bot=bot, top=bot + a["body_in"][1], arm_z=arm_z, r_arm=a["arm_radius_in"],
                                  R=a["truck_radius_in"])
        fa, ha = self.axles["fore_axle"], self.axles["hind_axle"]
        self.zb_f, self.zb_h = fa["top"] - k["axle_let_in"], ha["top"] - k["axle_let_in"]
        self.e_bed = k["breech_on_bed_deg"]
        tk = k["truck"]
        for a in (fa, ha):
            a["truck_y0"] = float(self.y_out(a["x"])) + 0.25 + tk["gap_in"]      # the truck's inner face
            a["truck_y"] = a["truck_y0"] + tk["thick_in"] / 2
            a["washer_y"] = a["truck_y0"] + tk["thick_in"] + 0.05
            a["pin_y"] = a["washer_y"] + k["washer_in"][1] + k["linch_pin_in"]["radius"] + 0.12
            a["arm_end"] = a["pin_y"] + k["linch_pin_in"]["radius"] + k["linch_pin_in"]["out"]
        self.bed_top = self._bed_top()
        q = k["quoin"]
        self.q_thin, self.q_thick = q["high_in"]
        self.q_slope = (self.q_thick - self.q_thin) / q["length_in"]
        self.e_home = self._elev_at_quoin(self.q_thick)           # the quoin home: its thick end under the breech
        self.e_thin = self._elev_at_quoin(self.q_thin)            # drawn out to its thin end; past it the breech drops
        self._check_quoin()                                       # onto the bed (e_bed)

    # --- the barrel ------------------------------------------------------------------------------------------------
    def R(self, s):
        """the barrel's outside radius at s (from the base ring's back)"""
        return float(np.interp(s, self.prof[:, 0], self.prof[:, 1]))

    def under(self, x):
        """the barrel's underside (in) over the deck at carriage x, level"""
        return self.zt + self.up - self.R(x + self.s_t)

    def barrel(self):
        g = self.g
        M = GPart()
        M.cur = "barrel"
        L, rb = g["length_in"], g["bore_in"] / 2
        out = [tuple(p) for p in self.prof]
        inside = [(L, g["mouth_in"]), (L - 0.35, rb), (L - g["bore_shown_in"], rb), (L - g["bore_shown_in"], 0.0)]
        mats = [BLACK] * (len(out) - 1) + [BLACK, IRON, IRON, SHADOW]
        lathe_closed(M, out + inside, mats, g["sides"], tr([-self.s_t, 0.0, self.up]))
        tn = g["trunnion"]
        M.cur = "trunnion"
        for sg in (1.0, -1.0):
            cylinder(M, [0, sg * 5.5, 0], [0, sg * tn["rimbase_face_in"], 0], tn["rimbase_radius_in"], BLACK, n=28)
            cylinder(M, [0, sg * (tn["rimbase_face_in"] - 0.6), 0], [0, sg * (tn["rimbase_face_in"] + tn["length_in"]), 0],
                     tn["radius_in"], BLACK, n=24)
        lp = g["loop"]
        M.cur = "loop"
        torus(M, [lp["x_in"] - self.s_t, 0, self.up + lp["z_in"]], EX, EZ, lp["ring_in"], lp["bar_in"], BLACK, n=20, m=10)
        vent_patch(M, g["vent"], self.R, self.up, self.s_t)
        self.pan, self.vent_mouth = flintlock(M, g["lock"], g["vent"], self.R, self.up, self.s_t)
        return M

    # --- elevating it: the quoin --------------------------------------------------------------------------------
    def barrel_T(self, e=0.0):
        """the barrel's frame in the carriage's, elevated e degrees (muzzle up): a turn about the trunnions' axis"""
        return tr([0.0, 0.0, self.zt]) @ rot(EY, -e)

    def _bottom(self, e):
        """the barrel's under side (each profile point straight below the bore's axis) in the carriage's frame at
        elevation e: (x, z) of each"""
        P = np.array([[s - self.s_t, 0.0, self.up - r] for s, r in self.prof])
        return pts(self.barrel_T(e), P)[:, [0, 2]]

    def corner(self, e):
        """the base ring's lower back edge (what bears on the quoin or the bed) in the carriage's frame at elevation e"""
        rb = float(self.prof[(self.prof[:, 0] >= 0.0) & (self.prof[:, 0] <= 0.5), 1].max())
        return pts(self.barrel_T(e), np.array([[-self.s_t, 0.0, self.up - rb]]))[0]

    def _elev_at_quoin(self, h):
        """the elevation at which the base ring's lower back edge stands h over the bed's top"""
        lo, hi = -20.0, 20.0
        for _ in range(60):
            m = 0.5 * (lo + hi)
            if self.corner(m)[2] - self.bed_top > h:
                lo = m
            else:
                hi = m
        return 0.5 * (lo + hi)

    def quoin_x(self, e):
        """the quoin's back (its thick end) along the carriage's X with the gun elevated e degrees, or None past
        e_thin (the quoin drawn out: the breech on the bed)"""
        if e > self.e_thin + 1e-6:
            return None
        if e < self.e_home - 1e-6:
            raise ValueError(f"guns: the long gun depresses only to {self.e_home:.2f} deg (the quoin home)")
        c = self.corner(e)
        return float(c[0] - (self.q_thick - (c[2] - self.bed_top)) / self.q_slope)

    def _check_quoin(self):
        """the base ring's edge is what bears on the quoin at every elevation it serves: nothing of the barrel's under
        side lies below the quoin's face"""
        q = self.k["quoin"]
        for e in np.linspace(self.e_home, self.e_thin, 9):
            x_r = self.quoin_x(e)
            B = self._bottom(e)
            m = (B[:, 0] >= x_r) & (B[:, 0] <= x_r + q["length_in"])
            face = self.bed_top + self.q_thick - (B[m, 0] - x_r) * self.q_slope
            if m.any() and float((face - B[m, 1]).max()) > 0.01:
                raise SystemExit(f"guns: the barrel's under side meets the quoin's face at {e:.1f} deg")

    def quoin(self):
        """the quoin in its frame: origin on the bed's top under its thick end's back, X toward the muzzle; its handle
        out behind"""
        q = self.k["quoin"]
        Lq, hw = q["length_in"], q["width_in"] / 2
        M = GPart()
        M.cur = "quoin"
        hexa(M, [[0, -hw, 0], [Lq, -hw, 0], [Lq, hw, 0], [0, hw, 0], [0, -hw, self.q_thick], [Lq, -hw, self.q_thin],
                 [Lq, hw, self.q_thin], [0, hw, self.q_thick]], WOOD)
        hz = 0.5 * self.q_thick
        cylinder(M, [0.3, 0, hz], [-q["handle_in"][0], 0, hz], q["handle_in"][1], WOOD, n=10)
        return M

    def quoin_body(self, x_c, e):
        """the quoin as an obstacle for the breeching (a box whose top is the quoin's face), or None (drawn out)"""
        x_r = self.quoin_x(e)
        if x_r is None:
            return None
        Lq = self.k["quoin"]["length_in"]
        X = unit(np.array([Lq, 0.0, self.q_thin - self.q_thick]))
        Z = unit(np.array([self.q_thick - self.q_thin, 0.0, Lq]))
        top = np.array([x_c + x_r + Lq / 2, 0.0, self.bed_top + 0.5 * (self.q_thick + self.q_thin)])
        hz = 0.5 * self.q_thick
        return Boxed(frame(top - Z * hz, X, Z), [0.5 * math.hypot(Lq, self.q_thick - self.q_thin), self.k["quoin"]["width_in"] / 2, hz])

    # --- the carriage ----------------------------------------------------------------------------------------------
    def _bed_top(self):
        """the bed's top: where the barrel's under side comes down on it at breech_on_bed_deg, the quoin drawn out"""
        bx0, bx1 = self.k["bed"]["x_in"]
        B = self._bottom(self.e_bed)
        m = (B[:, 0] >= bx0) & (B[:, 0] <= bx1)
        return float(B[m, 1].min()) - 0.02

    def bracket_outline(self):
        k = self.k
        zt = self.zt
        xr, xf = k["bracket_x_in"]
        fa, ha = self.axles["fore_axle"], self.axles["hind_axle"]
        rn = self.g["trunnion"]["radius_in"] + 0.04
        ar = k["arch"]
        P = [(xr, self.zb_h), (ha["x0"], self.zb_h), (ha["x0"], ha["top"]), (ha["x1"], ha["top"]), (ha["x1"], self.zb_h)]
        for x in np.linspace(ha["x1"], fa["x0"], 26)[1:-1]:
            z = self.zb_h + (self.zb_f - self.zb_h) * (x - ha["x1"]) / (fa["x0"] - ha["x1"])
            if ar["x_in"][0] <= x <= ar["x_in"][1]:
                z += ar["rise_in"] * math.sin(math.pi * (x - ar["x_in"][0]) / (ar["x_in"][1] - ar["x_in"][0]))
            P.append((x, z))
        P += [(fa["x0"], self.zb_f), (fa["x0"], fa["top"]), (fa["x1"], fa["top"]), (fa["x1"], self.zb_f), (xf, self.zb_f),
              (xf, zt)]
        for a in np.linspace(0, math.pi, 13):
            P.append((rn * math.cos(a), zt - rn * math.sin(a)))
        z = zt
        for xs_, drop in k["steps"]:
            P += [(xs_, z), (xs_, zt - drop)]
            z = zt - drop
        rt = k["tail_radius_in"]
        for a in np.linspace(math.pi / 2, math.pi, 7):
            P.append((xr + rt + rt * math.cos(a), z - rt + rt * math.sin(a)))
        return np.array(P)

    def anchors(self):
        """the points the gear meets, in the carriage's frame (inches)"""
        k = self.k
        bh = k["breeching_hole"]
        xb, zb = bh["x_in"], self.zt - bh["z_below_trunnion_in"]
        es, eb = k["eyebolt_side"], k["eyebolt_in"]
        ha = self.axles["hind_axle"]
        lp = self.g["loop"]
        A = {"hole_out": np.array([xb, float(self.y_out(xb)), zb]), "hole_in": np.array([xb, float(self.y_in(xb)), zb]),
             "hole_r": bh["radius_in"],
             "loop": np.array([lp["x_in"] - self.s_t, 0.0, self.zt + self.up + lp["z_in"]]),
             "loop_ring": lp["ring_in"], "loop_bar": lp["bar_in"]}
        nrm = unit(np.array([-self.slope, 1.0, 0.0]))                  # the bracket's outer face's normal (+y side)
        face = np.array([es["x_in"], float(self.y_out(es["x_in"])), es["z_in"]])
        A["side_face"], A["side_n"] = face, nrm
        A["side_eye"] = face + nrm * (0.15 + eb["bar"] + eb["eye"])
        A["side_eye_n"] = EZ                                          # the eye lies flat: its plane's normal is up
        tf = np.array([ha["x0"], 0.0, k["train_eyebolt"]["z_in"]])
        A["train_face"] = tf
        A["train_eye"] = tf - EX * (0.15 + eb["bar"] + eb["eye"])
        A["train_eye_n"] = EY                                         # the eye stands up in the XZ plane
        A["eye_R"], A["eye_bar"] = eb["eye"], eb["bar"]
        return A

    def carriage(self):
        k = self.k
        zt = self.zt
        M = GPart()
        # the brackets
        M.cur = "bracket"
        A = self.anchors()
        hole = (A["hole_out"][0], A["hole_out"][2], k["breeching_hole"]["radius_in"])
        br = GPart()
        br.cur = "bracket"
        slab(br, self.bracket_outline(), [hole], self.y_in, self.y_out, WOOD)
        M.extend(br)
        M.extend(br.mirrored_y())
        # the axletrees: body under the brackets, arms, washers, linch pins
        lp = k["linch_pin_in"]
        for nm, a in self.axles.items():
            M.cur = "axletree"
            ye = float(self.y_out(a["x"])) + 0.25
            hexa(M, [[a["x0"], -ye, a["bot"]], [a["x1"], -ye, a["bot"]], [a["x1"], ye, a["bot"]], [a["x0"], ye, a["bot"]],
                     [a["x0"], -ye, a["top"]], [a["x1"], -ye, a["top"]], [a["x1"], ye, a["top"]], [a["x0"], ye, a["top"]]],
                 WOOD)
            for sg in (1.0, -1.0):
                M.cur = "axletree"
                cylinder(M, [a["x"], sg * (ye - 0.3), a["arm_z"]], [a["x"], sg * a["arm_end"], a["arm_z"]], a["r_arm"], WOOD, n=16)
                M.cur = "linch"
                lathe_closed(M, [(0.0, a["r_arm"] + 0.1), (0.0, a["r_arm"] + k["washer_in"][0]),
                                 (k["washer_in"][1], a["r_arm"] + k["washer_in"][0]), (k["washer_in"][1], a["r_arm"] + 0.1)],
                             IRON, 16, tr([a["x"], sg * a["washer_y"], a["arm_z"]]) @ rot(EZ, 90 * sg), closed=True)
                py = sg * a["pin_y"]
                cylinder(M, [a["x"], py, a["arm_z"] - a["r_arm"] - 0.7], [a["x"], py, a["arm_z"] + a["r_arm"] + 0.25],
                         lp["radius"], IRON, n=8)
                cylinder(M, [a["x"], py, a["arm_z"] + a["r_arm"] + 0.15], [a["x"], py, a["arm_z"] + a["r_arm"] + 0.45],
                         lp["head"], IRON, n=10)
        # the transom over the fore axletree, the bed on its stool and bolt (the quoin is its own mesh: it moves)
        fa, ha = self.axles["fore_axle"], self.axles["hind_axle"]
        tx0, tx1 = k["transom"]["x_in"]
        t_top = min(self.under(x) for x in np.linspace(tx0, tx1, 19)) - k["transom"]["under_barrel_in"]
        M.cur = "transom"
        self._between(M, tx0, tx1, fa["top"], t_top, WOOD)
        bd = k["bed"]
        bx0, bx1 = bd["x_in"]
        bt = self.bed_top
        M.cur = "bed"
        self._between(M, bx0, bx1, bt - bd["thick_in"], bt, WOOD)
        M.cur = "stool"
        hy = bd["stool_half_y_in"]
        hexa(M, [[ha["x0"], -hy, ha["top"]], [ha["x1"], -hy, ha["top"]], [ha["x1"], hy, ha["top"]], [ha["x0"], hy, ha["top"]],
                 [ha["x0"], -hy, bt - bd["thick_in"]], [ha["x1"], -hy, bt - bd["thick_in"]], [ha["x1"], hy, bt - bd["thick_in"]],
                 [ha["x0"], hy, bt - bd["thick_in"]]], WOOD)
        bz = bt - bd["thick_in"] - bd["bolt_radius_in"]
        bxb = bd["bolt_x_in"]
        M.cur = "bolt"
        cylinder(M, [bxb, -float(self.y_out(bxb)) - 0.1, bz], [bxb, float(self.y_out(bxb)) + 0.1, bz], bd["bolt_radius_in"], IRON, n=10)
        # the cap squares over the trunnions
        cs = k["cap_square"]
        rn = self.g["trunnion"]["radius_in"] + 0.04
        th = cs["thick_in"]
        rho = rn + th / 2
        a0 = math.asin(min(0.99, (th / 2) / rho))
        arc = [(rho * math.cos(a), zt + rho * math.sin(a)) for a in np.linspace(a0, math.pi - a0, 15)]
        path = [(cs["reach_in"], zt + th / 2), (rho + 0.3, zt + th / 2)] + arc + [(-rho - 0.3, zt + th / 2),
                                                                                (-cs["reach_in"], zt + th / 2)]
        M.cur = "capsquare"
        for sg in (1.0, -1.0):
            yc = sg * (float(self.y_in(0.0)) + k["bracket_thick_in"] / 2)
            strap(M, path, yc, cs["broad_in"], th, IRON)
            cylinder(M, [cs["reach_in"] - 0.6, yc - sg * (cs["broad_in"] / 2 + 0.25), zt + th + 0.35],
                     [cs["reach_in"] - 0.6, yc + sg * (cs["broad_in"] / 2 + 0.25), zt + th + 0.35], 0.42, IRON, n=10)
            obox(M, [-cs["reach_in"] + 0.8, yc, zt + th + 0.25], EX, EY, EZ, [0.5, 0.5, 0.3], IRON)
            obox(M, [-cs["reach_in"] + 0.8, yc + sg * 0.95, zt + th + 0.25], EX, EY, EZ, [0.12, 0.45, 0.4], IRON)
        # the bolt heads on the brackets' outsides
        M.cur = "bolt"
        bh_ = k["bolt_head_in"]
        heads = [(0.5 * (tx0 + tx1), 0.5 * (fa["top"] + t_top)), (bxb, bz), (ha["x"], ha["top"] + 2.5),
                 (k["bracket_x_in"][1] - 2.5, zt - 6.0), (-14.0, zt - 6.5)]
        nrm = unit(np.array([-self.slope, 1.0, 0.0]))
        for x, z in heads:
            for sg in (1.0, -1.0):
                n_ = nrm * np.array([1.0, sg, 1.0])
                c = np.array([x, sg * float(self.y_out(x)), z]) + n_ * (bh_[1] / 2 - 0.05)
                obox(M, c, EX - (EX @ n_) * n_, n_, EZ, [bh_[0] / 2, bh_[1] / 2 + 0.05, bh_[0] / 2], IRON)
        # the eyebolts: the side tackles' on the brackets, the train tackle's in the hind axletree
        eb = k["eyebolt_in"]
        M.cur = "eyebolt"
        for sg in (1.0, -1.0):
            f = A["side_face"] * np.array([1.0, sg, 1.0])
            n_ = A["side_n"] * np.array([1.0, sg, 1.0])
            eyebolt(M, f, n_, EX, eb["eye"], eb["bar"], eb["shank"], eb["into"], 0.15)
        eyebolt(M, A["train_face"], -EX, EZ, eb["eye"], eb["bar"], eb["shank"], eb["into"], 0.15)
        return M

    def _between(self, M, x0, x1, z0, z1, mat):
        """a timber across between the brackets' inner faces, from x0 to x1 and z0 to z1"""
        y0, y1 = float(self.y_in(x0)), float(self.y_in(x1))
        hexa(M, [[x0, -y0, z0], [x1, -y1, z0], [x1, y1, z0], [x0, y0, z0],
                 [x0, -y0, z1], [x1, -y1, z1], [x1, y1, z1], [x0, y0, z1]], mat)

    def truck(self, which):
        """a truck in its frame: origin at its centre, Y along its axle (both faces alike, so one mesh serves both sides)"""
        a = self.axles[which]
        tk = self.k["truck"]
        t, ch, R = tk["thick_in"], tk["chamfer_in"], a["R"]
        rh = a["r_arm"] + tk["hole_clear_in"]
        M = GPart()
        M.cur = "truck"
        prof = [(-t / 2, rh), (-t / 2, R - ch), (-t / 2 + ch, R), (t / 2 - ch, R), (t / 2, R - ch), (t / 2, rh)]
        lathe_closed(M, prof, WOOD, tk["sides"], rot(EZ, 90.0), closed=True)
        return M

    def truck_frames(self):
        """each truck's frame in the carriage's frame: {(axle, side): 4x4}"""
        out = {}
        for nm, a in self.axles.items():
            for sg, sd in ((1.0, "R"), (-1.0, "L")):                 # +Y: the gun's right as the game shows it
                out[(nm, sd)] = tr([a["x"], sg * a["truck_y"], a["arm_z"]])
        return out


    # --- the gear --------------------------------------------------------------------------------------------------
    def bodies(self, x_c, e=0.0):
        """the carriage and barrel (elevated e degrees) as obstacles for the ropes, the carriage's origin at x_c along
        the frame's X (inches)"""
        T = tr([x_c, 0.0, 0.0])
        Tb = T @ self.barrel_T(e)
        out = [Revolved(pts(Tb, np.array([[-self.s_t, 0.0, self.up]]))[0], vecs(Tb, EX[None])[0], vecs(Tb, EZ[None])[0],
                        [tuple(p) for p in self.prof] + [(self.g["length_in"], 0.0)])]
        for nm, a in self.axles.items():
            for sg in (1.0, -1.0):
                out.append(Cyl(pts(T, np.array([[a["x"], sg * a["truck_y"], a["arm_z"]]]))[0], EY, a["R"],
                               self.k["truck"]["thick_in"] / 2 + 0.6))
        xr, xf = self.k["bracket_x_in"]
        for sg in (1.0, -1.0):                                  # each bracket as a box, square to its slanting faces
            xm = 0.5 * (xr + xf)
            ym = sg * float(self.y_in(xm) + self.y_out(xm)) / 2
            X = unit(np.array([1.0, sg * self.slope, 0.0]))
            Tb_ = frame(np.array([x_c + xm, ym, 0.5 * (self.zb_h + self.zt)]), X, EZ)
            out.append(Boxed(Tb_, [0.5 * (xf - xr) / X[0], self.k["bracket_thick_in"] / 2, 0.5 * (self.zt - self.zb_h)]))
        return out

    def barrel_body(self, x_c=0.0, e=0.0):
        """the barrel's outside as an obstacle, the carriage at x_c, the barrel elevated e degrees"""
        return self.bodies(x_c, e)[0]

    def rims(self):
        """the breeching's centre line through each bracket's hole, in the carriage's frame: {side: {"in": round the
        inside face's rim (from inside the hole out between the brackets), "out": round the outside face's rim (from
        inside the hole out along the bracket's face toward the port)}}"""
        A = self.anchors()
        r = self.c["ropes"]["breeching24_circ_in"] / (2 * math.pi)
        R = A["hole_r"]
        lp = A["loop"]
        out = {}
        for sd, sg in (("L", -1.0), ("R", 1.0)):
            f = np.array([1.0, sg, 1.0])
            ho, hi = A["hole_out"] * f, A["hole_in"] * f
            n_o = unit(np.array([-self.slope, 1.0, 0.0]) * f)
            toward_loop = np.array([lp[0], 0.0, self.zt + self.up]) - hi
            out[sd] = {"out": rim(ho, n_o, EX, R, r), "in": rim(hi, -n_o, toward_loop, R, r)}
        return out

    def breeching_inner(self, e=0.0):
        """the breeching's middle with the barrel elevated e degrees: from the left bracket's hole (inside face) round
        the breech, through the loop, to the right's, taut; in the carriage's frame. Cached for each elevation."""
        cache = self.__dict__.setdefault("_inner", {})
        key = round(float(e), 4)
        if key in cache:
            return cache[key]
        A = self.anchors()
        r = self.c["ropes"]["breeching24_circ_in"] / (2 * math.pi)
        move = self.barrel_T(e) @ inv(self.barrel_T(0.0))       # carries what is fixed to the level barrel
        lp = pts(move, A["loop"][None])[0]
        room = A["loop_ring"] - A["loop_bar"] - r - 0.03
        if room <= 0:
            raise SystemExit(f"guns: the breeching (radius {r:.2f} in) does not pass through the loop")
        hl, hr = self.rims()["L"]["in"][-1], self.rims()["R"]["in"][-1]

        def proj(p):                                             # held in the loop's opening (its plane is y = 0)
            q = np.array([p[0] - lp[0], 0.0, p[2] - lp[2]])
            d = float(np.linalg.norm(q))
            if d > room:
                q *= room / d
            return lp + q
        zt = self.zt + self.up
        L0 = A["loop"]
        w1 = pts(move, np.array([[-49.0, -10.8, zt + 1.0], [L0[0] - 1.5, -3.5, L0[2] + 0.5]]))
        w2 = pts(move, np.array([[L0[0] - 1.5, 3.5, L0[2] + 0.5], [-49.0, 10.8, zt + 1.0]]))
        way = [hl, w1[0], w1[1], lp, w2[0], w2[1], hr]
        start = resample(np.array(way, float), 0.8)
        k = int(np.argmin(np.linalg.norm(start - lp, axis=1)))
        bodies = self.bodies(0.0, e) + [Torus(lp, vecs(move, EX[None])[0], vecs(move, EZ[None])[0], A["loop_ring"],
                                              A["loop_bar"])]
        qb = self.quoin_body(0.0, e)
        if qb is not None:
            bodies.append(qb)
        P = taut_via(hl, hr, k, proj, bodies, r, start, iters=6000)
        cache[key] = P
        return P

    def train_x(self, x_run_in, pl):
        """the train tackle's ringbolt along the port's X: train_span inboard of the carriage's back when run in"""
        return x_run_in + self.k["bracket_x_in"][0] - pl["train_span_in"]

    def neck(self):
        """the chase's neck behind the muzzle's swell, where a lashing lies: (s of its middle, its floor's ends)"""
        ss = np.linspace(100.0, 110.0, 401)
        Rs = np.array([self.R(s) for s in ss])
        low = ss[Rs <= Rs.min() + 0.01]
        return float(0.5 * (low[0] + low[-1])), (float(low[0]), float(low[-1]))

    def lashing(self, M, x_c, e, eyes, r, turns):
        """The housed gun's muzzle lashing (inches, the port's frame): turns of rope, each down through one housing
        bolt's eye over the port, round under the chase's neck behind the muzzle's swell, up through the other eye and
        back over both eyes' inner bars; the turns lie side by side (across the eyes, along the neck). eyes: {"L",
        "R": (centre, hole axis, spec)}. Returns each turn's length"""
        Tb = tr([x_c, 0.0, 0.0]) @ self.barrel_T(e)
        body = self.barrel_body(x_c, e)
        u, v = vecs(Tb, EY[None])[0], vecs(Tb, EZ[None])[0]
        s_n, _ = self.neck()
        M.cur = "lashing"
        out = []
        spread = 2.0 * r + 0.1
        sp = {sd: eyes[sd][2] for sd in ("L", "R")}
        tori = [Torus(eyes[sd][0], *self._eye_axes(eyes[sd][1]), sp[sd]["eye"], sp[sd]["bar"]) for sd in ("L", "R")]
        # the turns' tops over the eyes' inner bars: one taut path, each turn's laid beside it along X (drawn taut each
        # on its own, the tops would close on each other)
        lift = max(sp["L"]["bar"], sp["R"]["bar"]) + r + 1.5
        E = {sd: eyes[sd][0] for sd in ("L", "R")}
        mid = 0.5 * (E["L"] + E["R"])
        way = np.array([E["R"], E["R"] + EZ * lift, mid + EZ * lift, E["L"] + EZ * lift, E["L"]])
        top0 = taut_from(resample(way, 1.0), tori + [body], r + 0.02, iters=2500)
        for j in range(turns):
            dlt = (j - 0.5 * (turns - 1)) * spread
            s = s_n + dlt
            rho = max(self.R(x) for x in np.linspace(s - r, s + r, 9)) + r + 0.03
            C = pts(Tb, np.array([[s - self.s_t, 0.0, self.up]]))[0]
            H = {sd: eyes[sd][0] + EX * dlt for sd in ("L", "R")}
            tp = {}
            for sd, pick in (("L", 1.0), ("R", -1.0)):
                q = H[sd] - C
                A_, B_ = float(q @ u), float(q @ v)
                D = math.hypot(A_, B_)
                if D <= rho + 0.5:
                    raise SystemExit(f"guns: a housing bolt's eye stands too near the housed gun's chase ({D:.2f} in)")
                ph = math.atan2(B_, A_) + pick * math.acos(rho / D)
                tp[sd] = ph
            p0, p1 = tp["L"], tp["R"]
            while p1 < p0:
                p1 += 2 * math.pi
            ang = np.linspace(p0, p1, 25)
            arc = C + rho * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
            legL = taut(H["L"], arc[0], [body] + tori, r + 0.02, n=24, iters=500)
            legR = taut(arc[-1], H["R"], [body] + tori, r + 0.02, n=24, iters=500)
            top = top0 + EX * dlt
            P = np.concatenate([top[len(top) // 2:], legL[1:-1], arc, legR[1:-1], top[:len(top) // 2 + 1]])
            P = fillet(P, 0.35)
            tube(M, P[:-1], r, ROPE, n=8, closed=True)
            out.append(round(length(P), 1))
        return out

    @staticmethod
    def _eye_axes(b):
        """two axes spanning the plane of an eye whose hole runs along b"""
        b = unit(b)
        a1 = unit(np.cross(b, EZ if abs(b @ EZ) < 0.9 else EX))
        return a1, np.cross(b, a1)

    def rig(self, x_c, pl, ir, depth, eye_at, floor, elev):
        """The gear at one gun deck gun in each pose, in its port's frame (inches): {pose: GPart}, the irons (the
        ringbolts' and housing bolts' eyes and shanks, the same in every pose) and info. x_c[pose]: the carriage's
        origin along the port's X (housed, run_in, run_out); elev[pose]: the barrel's elevation (deg); depth[name]: each
        bolt's shank's reach behind its eye's centre; eye_at[name]: each eye's centre (Guns.fit_irons); floor: the deck
        the coils and the ropes on it lie on (this gun's own: a DeckField). The breeching is taut run in (the recoil
        brings the gun up there) and its slack hangs in the other poses; housed, the muzzle is lashed to the housing
        bolts. info["coil_lines"][pose]: each coil's centre line."""
        ro = self.c["ropes"]
        rb_r = ro["breeching24_circ_in"] / (2 * math.pi)
        tk_r = ro["tackle24_circ_in"] / (2 * math.pi)
        Lb = ro["block_of_circ"] * ro["tackle24_circ_in"]
        sp_b, sp_t, sp_h = ir["ringbolt24"], ir["tackle_ring24"], ir["housing24"]
        so = ir["standoff_in"]
        r_h = ir["hook_bar_in"]["long24"]
        r0 = ro["coil_inner_in"]
        nf = -EX                                                    # the side's inner face looks inboard
        eyes = {}
        for sd, sg in (("L", -1.0), ("R", 1.0)):
            eyes["breeching_" + sd] = (np.array([-(so + sp_b["bar"] + sp_b["eye"]), sg * pl["breeching_bolt_y_in"],
                                                 pl["breeching_bolt_z_in"]]), nf, EZ, sp_b)
            eyes["tackle_" + sd] = (np.array([-(so + sp_t["bar"] + sp_t["eye"]), sg * pl["tackle_bolt_y_in"],
                                              pl["tackle_bolt_z_in"]]), nf, EZ, sp_t)
            eyes["housing_" + sd] = (np.array([-(so + sp_h["bar"] + sp_h["eye"]), sg * pl["housing_bolt_y_in"],
                                               pl["housing_bolt_z_in"]]), nf, EY, sp_h)
        x_tr = self.train_x(x_c["run_in"], pl)
        eyes["train"] = (np.array([x_tr, 0.0, so + sp_t["bar"] + sp_t["eye"]]), EZ, EX, sp_t)
        for nm, c_ in eye_at.items():
            eyes[nm] = (np.asarray(c_, float),) + eyes[nm][1:]
        irons = GPart()
        irons.cur = "ringbolt"
        holes = {nm: bolt_eye(irons, c_, n_, up, depth[nm], sp) for nm, (c_, n_, up, sp) in eyes.items()}
        A0 = self.anchors()
        cx, cy = pl["coil_in"]
        tx, ty = pl["train_coil_in"]
        coil_at = {"tackle_L": np.array([cx, -cy]), "tackle_R": np.array([cx, cy]), "train": np.array([x_tr + tx, ty])}
        lines = {}
        deck = floor

        def tackles(M, pose, coil_len, dry):
            M = GPart() if M is None else M
            T = tr([x_c[pose], 0.0, 0.0])
            bodies = [b for b in self.bodies(x_c[pose]) if isinstance(b, Cyl)] + [Plane([0, 0, 0], -EX)]
            coils = None if dry else lines.setdefault(pose, [])
            out = {}
            for sd, sg in (("L", -1.0), ("R", 1.0)):
                eb = pts(T, (A0["side_eye"] * np.array([1.0, sg, 1.0]))[None])[0]
                c_, n_, up, sp = eyes["tackle_" + sd]
                M.cur = "ring"
                ring = ring_in(GPart() if dry else M, c_, holes["tackle_" + sd], n_, eb - c_, sp)
                out["tackle_" + sd] = tackle(M, ring, (eb, A0["side_eye_n"], A0["eye_R"], A0["eye_bar"]), Lb, tk_r,
                                             r_h, EZ, coil_at["tackle_" + sd], coil_len["tackle_" + sd], r0,
                                             bodies=bodies, dry=dry, floor=floor, coils=coils)
            et = pts(T, A0["train_eye"][None])[0]
            c_, n_, up, sp = eyes["train"]
            M.cur = "ring"
            ring = ring_in(GPart() if dry else M, c_, holes["train"], n_, et - c_, sp)
            out["train"] = tackle(M, ring, (et, A0["train_eye_n"], A0["eye_R"], A0["eye_bar"]), Lb, tk_r, r_h, EY,
                                  coil_at["train"], coil_len["train"], r0, bodies=bodies, dry=dry, floor=floor,
                                  coils=coils)
            return out
        # each tackle's rope is as long in every pose: what the tackle takes in its longest pose and a coil's worth
        coil_min = 40.0
        names = ("tackle_L", "tackle_R", "train")
        poses = POSES24
        guess = {pose: {nm: 60.0 for nm in names} for pose in poses}
        for _ in range(4):
            meas = {pose: tackles(None, pose, guess[pose], True) for pose in poses}
            total = {nm: max(meas[pose][nm][0] for pose in poses) + coil_min for nm in names}
            guess = {pose: {nm: total[nm] - meas[pose][nm][0] for nm in names} for pose in poses}
        # the breeching: taut run in; its middle round the breech and through the loop follows the barrel's elevation
        inner = {pose: self.breeching_inner(elev[pose]) for pose in poses}
        L_in = {pose: length(inner[pose]) for pose in poses}
        out, info = {}, {"ropes_in": {}, "tackles": {}, "breeching": {}, "lashing_in": None}
        legs = {}
        for pose in ("run_in",) + tuple(p for p in poses if p != "run_in"):
            taut_pose = pose == "run_in"
            M = GPart()
            T = tr([x_c[pose], 0.0, 0.0])
            res = tackles(M, pose, guess[pose], False)
            for nm, (o_, inf) in res.items():
                info["tackles"].setdefault(nm, {})[pose] = {k: (np.round(v, 2).tolist() if isinstance(v, np.ndarray)
                                                                else (round(v, 2) if isinstance(v, float) else v))
                                                            for k, v in inf.items()}
                info["ropes_in"].setdefault(nm, {})[pose] = round(o_ + guess[pose][nm], 1)
            mid = pts(T, inner[pose])
            rims = {sd: {k_: pts(T, v_) for k_, v_ in rr.items()} for sd, rr in self.rims().items()}
            parts = []
            for sd, sg in (("L", -1.0), ("R", 1.0)):
                ho = rims[sd]["out"][-1]
                c_, n_, up, sp = eyes["breeching_" + sd]
                pull = unit(ho - c_) + (0.0 if taut_pose else 0.9) * (-EZ)
                M.cur = "ring"
                C, nn, R, bar = ring_in(M, c_, holes["breeching_" + sd], n_, pull, sp)
                F, t = on_circle(C, nn, R, pull)
                M.cur = "breeching"
                d = unit(ho - F) if taut_pose else unit(pull)
                cl = clinch(M, F, t, d, bar + rb_r + 0.05, rb_r, 5.0 * rb_r)
                s0 = cl[-1]
                if taut_pose:
                    leg = resample(np.array([s0, ho]), 2.0)
                    legs[sd] = length(leg)
                else:
                    Lleg = legs[sd] + 0.5 * (L_in["run_in"] - L_in[pose])
                    if float(np.linalg.norm(ho - s0)) > Lleg - 1.0:
                        raise SystemExit(f"guns: the long gun's breeching is too short for it to stand {pose}")
                    bodies = self.bodies(x_c[pose], elev[pose]) + [Plane([0, 0, 0], -EX)]
                    leg = hang(s0, ho, Lleg, rb_r, [deck] + bodies, n=72, iters=1200,
                               bias=sg * EY * 0.004 - EX * 0.012, g=-EZ * 0.12)
                parts.append((cl, leg, ho))
            (clL, legL, hoL), (clR, legR, hoR) = parts
            thru = {sd: np.concatenate([rims[sd]["out"][::-1], rims[sd]["in"]]) for sd in ("L", "R")}
            rope = np.concatenate([clL, legL[1:-1], thru["L"], mid[1:-1], thru["R"][::-1], legR[::-1][1:-1], clR[::-1]])
            M.cur = "breeching"
            tube(M, rope, rb_r, ROPE, n=10)
            info["breeching"][pose] = {"length_in": round(length(rope), 1), "legs_in": [round(length(legL), 1),
                                                                                         round(length(legR), 1)]}
            if pose == "housed":
                hz = {sd: (eyes["housing_" + sd][0], holes["housing_" + sd], sp_h) for sd in ("L", "R")}
                info["lashing_in"] = self.lashing(M, x_c[pose], elev[pose], hz,
                                                  ro["muzzle_lashing24_circ_in"] / (2 * math.pi),
                                                  ro["muzzle_lashing_turns"])
            out[pose] = M
        info["coil_min_in"] = coil_min
        info["coil_lines"] = lines
        return out, irons, info


def box8(x0, x1, y0, y1, z0, z1):
    """an axis-aligned box's corners for hexa"""
    return [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]


class Carr32:
    """the 32-pounder carronade, its bed and its slide (guns_1797.json carronade32, bed, slide), built in inches in their
    own frames (slide: origin on the deck on the fighting bolt's axis, X along the slide toward the port; bed: origin on
    the slide's top under the lug's bolt; barrel: origin on the lug's bolt, X along the bore)"""

    def __init__(self, c):
        self.c, self.g, self.b, self.s = c, c["carronade32"], c["bed"], c["slide"]
        self.prof = np.array(self.g["profile"], float)
        lg = self.g["lug"]
        self.s_l, self.drop = lg["x_in"], lg["drop_in"]          # the lug's s; the bore's axis over its bolt
        sl, bd = self.s, self.b
        self.rail_lo = sl["under_rails_in"]
        self.top = sl["under_rails_in"] + sl["rail_in"][1]       # the slide's top over the deck
        self.bolt_z = bd["high_in"] + bd["head_in"][1] - bd["bolt_below_head_in"]   # the lug's bolt over the bed's foot
        self.front = bd["bolt_from_front_in"]
        self.x_run = sl["front_in"] - self.front                  # the bed's origin along the slide when run out
        self.hw = bd["width_in"] / 2
        self.chock_top = 0.0                                      # the front transom's foot (Guns sets the chock's top)

    def Rc(self, s):
        """the barrel's outside radius at s (from the base ring's back)"""
        return float(np.interp(s, self.prof[:, 0], self.prof[:, 1]))

    def axis_z(self):
        """the bore's axis over the deck"""
        return self.top + self.bolt_z + self.drop

    # --- the barrel ------------------------------------------------------------------------------------------------
    def barrel(self):
        g = self.g
        M = GPart()
        M.cur = "barrel"
        L, rb = g["length_in"], g["bore_in"] / 2
        out = [tuple(p) for p in self.prof]
        inside = [(L, g["cup_rim_in"]), (L - g["cup_in"], g["mouth_in"]), (L - g["cup_in"] - 0.4, rb),
                  (L - g["bore_shown_in"], rb), (L - g["bore_shown_in"], 0.0)]
        mats = [BLACK] * (len(out) - 1) + [BLACK, BLACK, IRON, IRON, SHADOW]
        lathe_closed(M, out + inside, mats, g["sides"], tr([-self.s_l, 0.0, self.drop]))
        lg = g["lug"]
        hl, rr = lg["length_in"] / 2, lg["round_in"]
        zt_ = self.drop - self.Rc(self.s_l) + 0.9                   # the lug's top, cast into the barrel
        arc = [(rr * math.cos(a), rr * math.sin(a)) for a in np.linspace(-math.radians(15), -math.radians(165), 13)]
        outline = [(-hl, zt_), (hl, zt_), (hl, 1.2), (hl - 0.6, 0.45)] + arc + [(-hl + 0.6, 0.45), (-hl, 1.2)]
        M.cur = "lug"
        t2 = lg["thick_in"] / 2
        slab(M, outline, [(0.0, 0.0, self.b["bolt_radius_in"] + 0.05)], lambda x: np.full_like(x, -t2),
             lambda x: np.full_like(x, t2), BLACK, n_hole=16)
        lp = g["loop"]
        M.cur = "loop"
        torus(M, [lp["x_in"] - self.s_l, 0, self.drop + lp["z_in"]], EX, EZ, lp["ring_in"], lp["bar_in"], BLACK, n=20, m=10)
        sb = g["screw_boss"]
        M.cur = "boss"
        zb = self.drop - self.Rc(sb["x_in"])
        cylinder(M, [sb["x_in"] - self.s_l, 0, zb + 1.2], [sb["x_in"] - self.s_l, 0, zb - sb["drop_in"]], sb["radius_in"],
                 BLACK, n=16)
        vent_patch(M, g["vent"], self.Rc, self.drop, self.s_l)
        self.pan, self.vent_mouth = flintlock(M, g["lock"], g["vent"], self.Rc, self.drop, self.s_l)
        return M

    def barrel_body(self, T):
        """the barrel as an obstacle for the breeching, its frame at T"""
        return Revolved(pts(T, np.array([[-self.s_l, 0.0, self.drop]]))[0], vecs(T, EX[None])[0], vecs(T, EZ[None])[0],
                        [tuple(p) for p in self.prof] + [(self.g["length_in"], 0.0)])

    # --- the bed ---------------------------------------------------------------------------------------------------
    def screw_top(self):
        """the elevating screw's top (bed frame): under the boss"""
        sb = self.g["screw_boss"]
        return np.array([sb["x_in"] - self.s_l, 0.0, self.bolt_z + self.drop - self.Rc(sb["x_in"]) - sb["drop_in"] - 0.03])

    def anchors(self):
        """the points the gear meets, in the bed's frame (inches)"""
        bd, lp = self.b, self.g["loop"]
        eb = bd["eyebolt"]
        x = self.front - eb["from_front_in"]
        face = np.array([x, self.hw, eb["z_in"]])
        return {"loop": np.array([lp["x_in"] - self.s_l, 0.0, self.bolt_z + self.drop + lp["z_in"]]),
                "loop_ring": lp["ring_in"], "loop_bar": lp["bar_in"],
                "side_face": face, "side_n": EY, "side_eye": face + EY * (0.15 + eb["bar"] + eb["eye"]),
                "side_eye_n": EZ, "eye_R": eb["eye"], "eye_bar": eb["bar"]}

    def bed(self):
        bd = self.b
        M = GPart()
        L, H, hw = bd["length_in"], bd["high_in"], self.hw
        x1 = self.front
        x0 = x1 - L
        M.cur = "bed"
        hexa(M, box8(x0, x1, -hw, hw, 0.0, H), WOOD)
        hl, hh = bd["head_in"]
        yi = self.g["lug"]["thick_in"] / 2 + 0.1
        M.cur = "cheek"
        for sg in (1.0, -1.0):
            y0, y1 = sorted((sg * yi, sg * hw))
            hexa(M, box8(x1 - hl, x1, y0, y1, H, H + hh), WOOD)
        M.cur = "bolt"
        br = bd["bolt_radius_in"]
        cylinder(M, [0, -hw - 0.55, self.bolt_z], [0, hw + 0.55, self.bolt_z], br, IRON, n=12)
        for sg in (1.0, -1.0):                                       # the head and the nut
            obox(M, [0, sg * (hw + 0.3), self.bolt_z], EX, EY, EZ, [1.0, 0.3, 1.0], IRON)
        kw, kd = bd["keel_in"]
        M.cur = "keel"
        hexa(M, box8(x0 + 2.0, x1 - 2.0, -kw / 2, kw / 2, -kd, 0.0), WOOD)
        M.cur = "screw"
        st = self.screw_top()
        cylinder(M, [st[0], 0, H - 2.5], st, bd["screw_radius_in"], IRON, n=12)
        obox(M, [st[0], 0, H + 0.15], EX, EY, EZ, [1.5, 1.5, 0.15], IRON)                          # its nut plate
        hlen, hr = bd["screw_handle_in"]
        zh = st[2] - 1.0
        cylinder(M, [st[0], -hlen / 2, zh], [st[0], hlen / 2, zh], hr, IRON, n=8)
        M.cur = "eyebolt"
        A = self.anchors()
        eb = bd["eyebolt"]
        for sg in (1.0, -1.0):
            eyebolt(M, A["side_face"] * np.array([1.0, sg, 1.0]), EY * sg, EX, eb["eye"], eb["bar"], eb["shank"],
                    eb["into"], 0.15)
        return M

    # --- the slide -------------------------------------------------------------------------------------------------
    def slide(self):
        sl = self.s
        M = GPart()
        xf = sl["front_in"]
        xr = xf - sl["length_in"]
        rw = sl["rail_in"][0]
        so = sl["slot_in"] / 2
        zlo, ztop = self.rail_lo, self.top
        M.cur = "rail"
        for sg in (1.0, -1.0):
            y0, y1 = sorted((sg * so, sg * (so + rw)))
            hexa(M, box8(xr, xf, y0, y1, zlo, ztop), WOOD)
        M.cur = "transom"
        zb = zlo - sl["transom_drop_in"]
        for nm, (a, b) in sl["transoms"].items():
            hexa(M, box8(xf - b, xf - a, -(so + rw), so + rw, self.chock_top if nm == "front" else zb, zlo), WOOD)
        M.cur = "fighting_bolt"
        cylinder(M, [0, 0, -4.0], [0, 0, zlo + 0.6], sl["bolt_radius_in"], IRON, n=12)
        cylinder(M, [0, 0, zlo], [0, 0, zlo + 0.6], sl["bolt_radius_in"] + 0.7, IRON, n=12)
        tk = sl["truck_in"]
        a, b = sl["transoms"]["rear"]
        xc = xf - (a + b) / 2
        R, t, gap = tk["radius"], tk["thick"], tk["gap"]
        ra = 0.55
        for sg in (1.0, -1.0):
            yc = sg * tk["y"]
            M.cur = "truck"
            lathe_closed(M, [(-t / 2, ra + 0.06), (-t / 2, R - 0.3), (-t / 2 + 0.3, R), (t / 2 - 0.3, R), (t / 2, R - 0.3),
                             (t / 2, ra + 0.06)], WOOD, 32, tr([xc, yc, R]), closed=True)
            M.cur = "truck_cheek"
            for s2 in (1.0, -1.0):
                xa, xb = sorted((xc + s2 * (t / 2 + gap), xc + s2 * (t / 2 + gap + 1.2)))
                hexa(M, box8(xa, xb, yc - 2.0, yc + 2.0, R - 1.6, zb), WOOD)
            M.cur = "axle"
            cylinder(M, [xc - t / 2 - gap - 1.5, yc, R], [xc + t / 2 + gap + 1.5, yc, R], ra, IRON, n=10)
        return M

    def bed_frame(self, x_bed):
        """the bed's frame in the slide's, its origin at x_bed along the slide"""
        return tr([x_bed, 0.0, self.top])

    def barrel_frame(self):
        """the barrel's frame in the bed's"""
        return tr([0.0, 0.0, self.bolt_z])

    # --- the gear --------------------------------------------------------------------------------------------------
    def bodies(self, Ts, x_bed):
        """the slide, bed and barrel as obstacles for the ropes, the slide's frame at Ts, the bed at x_bed along it"""
        sl, bd = self.s, self.b
        Tb = Ts @ self.bed_frame(x_bed)
        out = [self.barrel_body(Tb @ self.barrel_frame())]
        xf = sl["front_in"]
        xr = xf - sl["length_in"]
        w2 = sl["slot_in"] / 2 + sl["rail_in"][0]
        out.append(Boxed(Ts @ tr([0.5 * (xf + xr), 0.0, 0.5 * (self.rail_lo + self.top)]),
                         [0.5 * (xf - xr), w2, 0.5 * (self.top - self.rail_lo)]))
        x1 = self.front
        x0 = x1 - bd["length_in"]
        out.append(Boxed(Tb @ tr([0.5 * (x0 + x1), 0.0, bd["high_in"] / 2]), [0.5 * (x1 - x0), self.hw, bd["high_in"] / 2]))
        hl, hh = bd["head_in"]
        out.append(Boxed(Tb @ tr([x1 - hl / 2, 0.0, bd["high_in"] + hh / 2]), [hl / 2, self.hw, hh / 2]))
        return out

    def rig(self, x_f, x_bed, pl, ir, depth, eye_at=None, floor=None):
        """The gear at a quarterdeck or forecastle port in each pose (run_out, recoil), in the port's frame (inches):
        {pose: GPart}, the irons (the ringbolts' eyes and shanks) and info. x_f: the fighting bolt along the port's X
        (the slide square to the side, not trained); x_bed[pose]: the bed's origin along the slide; depth[name]: each
        ringbolt's shank's reach behind its eye's centre; eye_at[name]: each ringbolt's eye's centre (Guns.fit_irons)
        or the nominal place; floor: the deck the coils and the ropes on it lie on (a DeckField; z = 0 if None).
        info["coil_lines"][pose]: each coil's centre line."""
        ro = self.c["ropes"]
        rb_r = ro["breeching32c_circ_in"] / (2 * math.pi)
        tk_r = ro["tackle32c_circ_in"] / (2 * math.pi)
        Lb = ro["block_of_circ"] * ro["tackle32c_circ_in"]
        sp_b, sp_t = ir["ringbolt32c"], ir["tackle_ring32c"]
        so = ir["standoff_in"]
        r_h = ir["hook_bar_in"]["carronade32"]
        r0 = ro["coil_inner_in"]
        nf = -EX
        eyes = {}
        for sd, sg in (("L", -1.0), ("R", 1.0)):
            eyes["breeching_" + sd] = (np.array([-(so + sp_b["bar"] + sp_b["eye"]), sg * pl["breeching_bolt_y_in"],
                                                 pl["breeching_bolt_z_in"]]), nf, EZ, sp_b)
            eyes["tackle_" + sd] = (np.array([-(so + sp_t["bar"] + sp_t["eye"]), sg * pl["tackle_bolt_y_in"],
                                              pl["tackle_bolt_z_in"]]), nf, EZ, sp_t)
        for nm, c_ in (eye_at or {}).items():
            eyes[nm] = (np.asarray(c_, float),) + eyes[nm][1:]
        irons = GPart()
        irons.cur = "ringbolt"
        holes = {nm: bolt_eye(irons, c_, n_, up, depth[nm], sp) for nm, (c_, n_, up, sp) in eyes.items()}
        A0 = self.anchors()
        Ts = tr([x_f, 0.0, 0.0])
        Tb = {pose: Ts @ self.bed_frame(x_bed[pose]) for pose in x_bed}
        cx, cy = pl["coil_in"]
        coil_at = {"tackle_L": np.array([cx, -cy]), "tackle_R": np.array([cx, cy])}
        poses = tuple(x_bed)
        lines = {}
        deck = floor if floor is not None else Floor([0, 0, 0], EZ)

        def tackles(M, pose, coil_len, dry):
            M = GPart() if M is None else M
            bodies = [Plane([0, 0, 0], -EX)]
            coils = None if dry else lines.setdefault(pose, [])
            out = {}
            for sd, sg in (("L", -1.0), ("R", 1.0)):
                eb = pts(Tb[pose], (A0["side_eye"] * np.array([1.0, sg, 1.0]))[None])[0]
                c_, n_, up, sp = eyes["tackle_" + sd]
                M.cur = "ring"
                ring = ring_in(GPart() if dry else M, c_, holes["tackle_" + sd], n_, eb - c_, sp)
                out["tackle_" + sd] = tackle(M, ring, (eb, A0["side_eye_n"], A0["eye_R"], A0["eye_bar"]), Lb, tk_r, r_h,
                                             EZ, coil_at["tackle_" + sd], coil_len["tackle_" + sd], r0, bodies=bodies,
                                             dry=dry, floor=floor, coils=coils)
            return out
        coil_min = 36.0
        names = ("tackle_L", "tackle_R")
        guess = {pose: {nm: 50.0 for nm in names} for pose in poses}
        for _ in range(4):
            meas = {pose: tackles(None, pose, guess[pose], True) for pose in poses}
            total = {nm: max(meas[pose][nm][0] for pose in poses) + coil_min for nm in names}
            guess = {pose: {nm: total[nm] - meas[pose][nm][0] for nm in names} for pose in poses}
        # the breeching: taut when recoiled (the bed brought up by it), through the loop
        lp = {pose: pts(Tb[pose], A0["loop"][None])[0] for pose in poses}
        room = A0["loop_ring"] - A0["loop_bar"] - rb_r - 0.03
        if room <= 0:
            raise SystemExit(f"guns: the carronade's breeching (radius {rb_r:.2f} in) does not pass through its loop")

        def ends(M, pose, slack):
            """each side's ring and the clinch at it: (clinch's centre line, where the standing part leaves)"""
            out = {}
            for sd, sg in (("L", -1.0), ("R", 1.0)):
                c_, n_, up, sp = eyes["breeching_" + sd]
                pull = unit(lp[pose] - c_) + slack * (-EZ)
                M.cur = "ring"
                C, nn, R, bar = ring_in(M, c_, holes["breeching_" + sd], n_, pull, sp)
                F, t = on_circle(C, nn, R, pull)
                M.cur = "breeching"
                out[sd] = clinch(M, F, t, unit(pull), bar + rb_r + 0.05, rb_r, 5.0 * rb_r)
            return out
        out, info = {}, {"ropes_in": {}, "tackles": {}, "breeching": {}}
        taut_pose = "recoil" if "recoil" in poses else poses[-1]
        order = [taut_pose] + [p for p in poses if p != taut_pose]
        legs_len = {}
        for pose in order:
            M = GPart()
            res = tackles(M, pose, guess[pose], False)
            for nm, (o_, inf) in res.items():
                info["tackles"].setdefault(nm, {})[pose] = {k: (np.round(v, 2).tolist() if isinstance(v, np.ndarray)
                                                                else (round(v, 2) if isinstance(v, float) else v))
                                                            for k, v in inf.items()}
                info["ropes_in"].setdefault(nm, {})[pose] = round(o_ + guess[pose][nm], 1)
            L_ = lp[pose]

            def proj(p, L_=L_):
                q = np.array([p[0] - L_[0], 0.0, p[2] - L_[2]])
                d = float(np.linalg.norm(q))
                if d > room:
                    q *= room / d
                return L_ + q
            bodies = self.bodies(Ts, x_bed[pose]) + [Torus(L_, EX, EZ, A0["loop_ring"], A0["loop_bar"]),
                                                     Plane([0, 0, 0], -EX)]
            if pose == taut_pose:
                cl = ends(M, pose, 0.0)
                s0L, s0R = cl["L"][-1], cl["R"][-1]
                way = [s0L, L_ + np.array([2.0, -3.0, 1.0]), L_, L_ + np.array([2.0, 3.0, 1.0]), s0R]
                start = resample(np.array(way), 0.6)
                k = int(np.argmin(np.linalg.norm(start - L_, axis=1)))
                P = taut_via(s0L, s0R, k, proj, bodies, rb_r, start, iters=6000)
                legL, legR = P[:k + 1], P[k:][::-1]
                total = length(cl["L"]) + length(cl["R"]) + length(P)
                legs_len = {"L": length(legL), "R": length(legR)}
            else:
                cl = ends(M, pose, 0.2)
                spare = total - length(cl["L"]) - length(cl["R"]) - legs_len["L"] - legs_len["R"]
                legL = hang(cl["L"][-1], L_, legs_len["L"] + spare / 2, rb_r, [deck] + bodies, n=56,
                            iters=1000, bias=-EY * 0.002 - EX * 0.05, g=-EZ * 0.1)
                legR = hang(cl["R"][-1], L_, legs_len["R"] + spare / 2, rb_r, [deck] + bodies, n=56,
                            iters=1000, bias=EY * 0.002 - EX * 0.05, g=-EZ * 0.1)
            rope = np.concatenate([cl["L"], legL[1:], legR[::-1][1:-1], cl["R"][::-1]])
            M.cur = "breeching"
            tube(M, rope, rb_r, ROPE, n=10)
            info["breeching"][pose] = {"length_in": round(length(rope), 1),
                                       "legs_in": [round(length(legL), 1), round(length(legR), 1)]}
            out[pose] = M
        info["coil_min_in"] = coil_min
        info["coil_lines"] = lines
        return out, irons, info


# ---- the guns at their ports ---------------------------------------------------------------------------------------
def in_m(T):
    """a frame with its origin in inches, in metres"""
    T = np.array(T, float)
    T[:3, 3] *= IN
    return T


def mirror_frame(T):
    """a starboard port's frame carried to its port side twin: origin and axes mirrored across the middle line, Y made
    again Z x X (the gun turned, not mirrored: its lock stays on its right)"""
    f = np.array([1.0, -1.0, 1.0])
    return frame(T[:3, 3] * f, T[:3, 0] * f, T[:3, 2] * f)


def tree_of(parts):
    """one BVH tree of [(V, F)] (faces of any size)"""
    from mathutils.bvhtree import BVHTree
    Vs, Fs, n = [], [], 0
    for V, F in parts:
        V = np.asarray(V, float).reshape(-1, 3)
        Vs.append(V)
        Fs += [[n + int(i) for i in f] for f in F]
        n += len(V)
    return BVHTree.FromPolygons(np.concatenate(Vs).tolist(), Fs)


def behind(V, tree, near):
    """how deep any of the points V lies behind the surface in tree (measured to its nearest face, where that face lies
    square to it: a point buried whole counts, one beside an edge doesn't)"""
    d = 0.0
    for v in V:
        co, nrm, _, dist = tree.find_nearest(v.tolist(), near)
        if co is None:
            continue
        s_ = float((v - np.array(co)) @ np.array(nrm))
        if s_ < 0 and -s_ >= 0.95 * dist:
            d = max(d, -s_)
    return d


def crossings(part, near=3.0):
    """the pairs of labels whose surfaces cross in a GPart (inches): {(a, b): (count, depth in inches)}"""
    from mathutils.bvhtree import BVHTree
    V, T, L = part.tri_arrays()
    labs = sorted(set(L))
    trees = {}
    for l in labs:
        u, k = np.unique(T[L == l].ravel(), return_inverse=True)
        trees[l] = BVHTree.FromPolygons(V[u].tolist(), k.reshape(-1, 3).tolist(), all_triangles=True)
    verts = {l: V[np.unique(T[L == l].ravel())] for l in labs}
    out = {}
    for i, a in enumerate(labs):
        for b in labs[i + 1:]:
            ov = trees[a].overlap(trees[b])
            if ov:
                out[(a, b)] = (len(ov), round(max(behind(verts[a], trees[b], near), behind(verts[b], trees[a], near)), 2))
    return out


# what meets by design inside a gun and its gear: (label, label): (why, how far either may go into the other, inches)
LOCAL_MEETS = {
    # the long gun and its carriage
    ("barrel", "trunnion"): ("the trunnions and their rimbases are cast on the barrel", 3.5),
    ("barrel", "loop"): ("the breeching loop is cast on the cascabel", 1.6),
    ("barrel", "vent"): ("the vent's patch is cast on the barrel", 0.3),
    ("barrel", "lock"): ("the lock's plate is let into the barrel beside the vent", 0.35),
    ("lock", "vent"): ("the lock's pan sits on the vent's patch, its priming channel let into it", 0.3),
    ("barrel", "quoin"): ("the breech's base ring bears on the quoin", 0.1),
    ("barrel", "boss"): ("the elevating screw's boss is cast under the carronade's breech", 2.0),
    ("barrel", "lug"): ("the carronade's lug is cast under its barrel", 1.0),
    ("axletree", "bracket"): ("the axletrees are let into the brackets' undersides", 0.1),
    ("axletree", "linch"): ("the washers ride on the axletrees' arms, the linch pins through them", 4.6),
    ("axletree", "eyebolt"): ("the train tackle's eyebolt is driven into the hind axletree", 3.6),
    ("axletree", "stool"): ("the bed's stool stands on the hind axletree", 0.1),
    ("axletree", "transom"): ("the transom stands on the fore axletree", 0.1),
    ("bed", "bracket"): ("the bed lies between the brackets", 0.1),
    ("bed", "stool"): ("the bed lies on its stool", 0.1),
    ("bed", "bolt"): ("the bed bolt runs across under the bed's fore end", 0.1),
    ("bed", "quoin"): ("the quoin lies on the bed", 0.1),
    ("bracket", "transom"): ("the transom is let between the brackets", 0.1),
    ("bracket", "capsquare"): ("the cap squares are let into the brackets' tops", 0.6),
    ("bolt", "bracket"): ("the transverse bolts pass through the brackets, their heads let into the outsides", 5.7),
    ("bracket", "eyebolt"): ("the side tackles' eyebolts are driven into the brackets", 3.6),
    # the carronade, its bed and slide
    ("bed", "cheek"): ("the bed's cheeks stand on it", 0.1),
    ("bed", "keel"): ("the keel is fastened under the bed", 0.1),
    ("bed", "screw"): ("the elevating screw passes down through the bed", 7.1),
    ("bed", "eyebolt"): ("the side tackles' eyebolts are driven into the bed's sides", 3.1),
    ("bolt", "cheek"): ("the loop's bolt passes through the bed's cheeks", 8.1),
    ("fighting_bolt", "transom"): ("the fighting bolt passes down through the slide's front transom", 12.0),
    ("transom", "truck_cheek"): ("the rear trucks' cheeks are bolted under the rear transom", 0.1),
    ("axle", "truck_cheek"): ("the rear trucks' axles pass through their cheeks", 1.5),
    # the gear
    ("barrel", "breeching"): ("the breeching bears on the breech", 0.1),
    ("breeching", "loop"): ("the breeching is rove through the loop", 0.1),
    ("breeching", "seizing"): ("each breeching's end is clinched round its ring and seized to its standing part", 0.5),
    ("block", "hook"): ("each block's hook passes through its eye", 0.2),
    ("block", "seizing"): ("the becket's seizing lies against the block's strop", 0.1),
    ("block", "tackle_rope"): ("the falls run round the sheaves in the blocks' mortises", 0.1),
    ("seizing", "tackle_rope"): ("each tackle's standing end is clinched round the becket and seized", 0.2),
    ("barrel", "lashing"): ("the housed gun's muzzle lashing bears on its chase", 0.1),
    ("lashing", "ringbolt"): ("the muzzle lashing is rove through the housing bolts' eyes", 0.1),
}

# what meets by design between a gun's parts (by label) and the ship's objects: (label, object): (why, inches)
SHIP_MEETS = {
    # (a gun's part, a ship's object): what meets by design, and the deepest it may go (in). A depth is measured at
    # every vertex of either part near where they meet, behind the other's nearest face: a shank buried in the side
    # counts its whole length, a rope or a truck on the deck how far it is pressed in
    ("ringbolt", "GunWall"): ("the gun deck's ringbolts driven into the side", 4.0),
    ("ringbolt", "BulwarkIn"): ("the carronades' ringbolts driven into the bulwark", 4.0),
    ("ringbolt", "GunDeck"): ("the train tackles' ringbolts driven into the gun deck", 3.0),
    ("fighting_bolt", "SparDeck"): ("the fighting bolt driven down through the chock into the deck", 4.5),
    ("fighting_bolt", "Waterways"): ("the fighting bolt through the waterway's inner edge", 0.5),
    ("fighting_bolt", "Carr32_Chocks"): ("the fighting bolt through its chock (the depth counts the chock's points "
                                         "inside the bolt)", 1.0),
    ("transom", "Carr32_Chocks"): ("the slide's front transom on its chock (the depth counts the chock's points inside "
                                   "the fighting bolt through it)", 1.0),
    ("chock", "SparDeck"): ("the chocks let into the deck", 0.2),
    ("chock", "Waterways"): ("the chocks let into the waterway", 0.2),
    ("truck", "GunDeck"): ("the trucks on the deck, where its sheer bends under them", 0.15),
    ("truck", "SparDeck"): ("the slides' trucks on the deck", 0.1),
    ("tackle_rope", "GunDeck"): ("the falls and their coils on the deck (each gun's on its own deck: "
                                 "guns.coils_on_deck)", 0.3),
    ("tackle_rope", "SparDeck"): ("the falls and their coils on the deck", 0.3),
    ("breeching", "GunDeck"): ("the housed and run-out long guns' breechings, slack in bights on the deck", 0.3),
    ("breeching", "SparDeck"): ("the run-out carronades' breechings, slack on the deck", 0.3),
}


def allowed(table, a, b):
    return table.get((a, b)) or table.get((b, a))


class Guns:
    """The frigate's guns at their ports: build() places them (each port's frame, where each long gun's carriage stands
    in each pose, each carronade's fighting bolt, each gun's ringbolts fitted to its own side and deck, the carronades'
    chocks) and makes the meshes (self.meshes: metres, each in its own frame; the guns, carriages, quoin, trucks, beds
    and slides are shared by every port, each gun's gear and irons are its own), instances() says where each copy
    stands, room() checks them against the ship, game_data() is guns.json."""

    DECKS = ("gun_deck", "spar_deck")
    SHOWN = ("Guns", "Guns_Housed", "Carronades_RunOut")

    def __init__(self, sk, dk, skin_parts, path=os.path.join(HERE, "guns_1797.json")):
        import skin as SKM
        self.sk, self.dk, self.SKM, self.sp = sk, dk, SKM, skin_parts
        self.c = json.load(open(path))
        self.L24, self.C32 = Long24(self.c), Carr32(self.c)
        self.elev24 = {"housed": self.L24.e_bed, "run_in": 0.0, "run_out": 0.0}
        self.info = {}
        self.lid_fit = {}

    # --- each port's frame --------------------------------------------------------------------------------------
    def port_frame(self, deck, i):
        """a starboard port's frame (metres) and where its jambs are: origin on the deck under the point where the
        port's middle line meets the side's inner face at ring_height, X out (level across, along the face's outward
        normal there), Z the deck's normal, Y = Z x X (aft on the starboard side)"""
        sk, dk, S = self.sk, self.dk, self.SKM
        pr = sk.pr
        if deck == "gun_deck":
            a, f = pr.gun[i - 1][:2]
            kind, zdeck = S.GUN, dk.zg
        else:
            a, f = pr.spar[i - 1][:2]
            kind, zdeck = S.BUL, dk.z
        ring = self.c["placement"][deck]["ring_height_in"] * IN
        ppm = sk.L.ppf_y / FT                                  # the sheet's pixels per metre up it

        def at(xpx):
            zp = (float(zdeck(dk.xm(xpx))) + ring) * ppm
            for _ in range(12):
                P, N = sk.surf(np.array([xpx]), np.array([zp]), True, 0, kind)
                err = float(zdeck(P[0][0])) + ring - P[0][2]
                zp += err * ppm
                if abs(err) < 1e-7:
                    break
            return P[0], N[0]
        P, N = at(0.5 * (a + f))
        h = 0.05
        s = (float(zdeck(P[0] + h)) - float(zdeck(P[0] - h))) / (2 * h)
        Z = unit(np.array([-s, 0.0, 1.0]))
        O = P - ring * Z
        O[2] = float(zdeck(O[0]))
        T = frame(O, np.array([N[0], N[1], 0.0]), Z)
        Ti = inv(T)
        jambs = [float(pts(Ti, at(x)[0][None])[0][1]) / IN for x in (a, f)]   # y (in) of the aft and fore jambs
        return T, {"x_m": [round(dk.xm(a), 4), round(dk.xm(f), 4)], "jambs_y_in": [round(v, 2) for v in jambs],
                   "deck_slope": round(s, 5)}

    def trees(self):
        """BVH trees (starboard; the port side is its mirror): each deck's wall (the side's inner face and the ports'
        linings), what a ray along a port's X meets (the wall and, on the spar deck, the waterway) and the floor (the
        deck's top and the waterway)"""
        sp, dk = self.sp, self.dk
        ww = dk.world("Waterways")
        self.wall = {"gun_deck": tree_of([sp["GunWall"][:2], sp["PortLinings"][:2]]),
                     "spar_deck": tree_of([sp["BulwarkIn"][:2], sp["PortLinings"][:2]])}
        self.side = {"gun_deck": self.wall["gun_deck"],
                     "spar_deck": tree_of([sp["BulwarkIn"][:2], sp["PortLinings"][:2], ww])}
        self.floor = {"gun_deck": tree_of([sp["GunDeck"][:2]]), "spar_deck": tree_of([ww, dk.world("SparDeck")])}

    def face_x(self, tree, T, y, z, x0=-90.0):
        """where along a port's X (inches) a ray from x0 inboard at (y, z) meets the tree, or None"""
        o = pts(T, I([[x0, y, z]]))[0]
        hit = tree.ray_cast(o.tolist(), T[:3, 0].tolist(), 4.0)
        return None if hit[0] is None else x0 + hit[3] / IN

    def floor_z(self, deck, T, x, y, z0=30.0):
        """the deck's (or waterway's) top under (x, y) of a port's frame, along its -Z (inches)"""
        o = pts(T, I([[x, y, z0]]))[0]
        hit = self.floor[deck].ray_cast(o.tolist(), (-T[:3, 2]).tolist(), 2.0)
        return None if hit[0] is None else z0 - hit[3] / IN

    # --- one gun's surroundings ---------------------------------------------------------------------------------
    def env(self, deck, i, sd):
        """a gun's surroundings are its starboard twin's mirrored (the ship is alike on both sides): the starboard
        port's frame, and the sign that carries a point's y in the gun's own port frame to that frame (mirror_frame:
        a port side gun's point (x, y, z) is its twin's (x, -y, z) mirrored)"""
        return self.frames[deck][i][0], (1.0 if sd == "S" else -1.0)

    def wall_x(self, deck, i, sd, y, z):
        """where along X (inches) the side's inner face (or a port's lining) stands at (y, z) of a gun's own frame"""
        T, e = self.env(deck, i, sd)
        return self.face_x(self.wall[deck], T, e * y, z)

    def deck_zs(self, deck, i, sd, XY, z0=30.0):
        """the deck's (or waterway's) top (inches) under the points XY of a gun's own port frame (nan where none)"""
        T, e = self.env(deck, i, sd)
        XY = np.asarray(XY, float).reshape(-1, 2)
        O = pts(T, I(np.c_[XY[:, 0], e * XY[:, 1], np.full(len(XY), z0)]))
        d = (-T[:3, 2]).tolist()
        out = np.full(len(XY), np.nan)
        for k, o in enumerate(O):
            hit = self.floor[deck].ray_cast(o.tolist(), d, 2.0)
            if hit[0] is not None:
                out[k] = z0 - hit[3] / IN
        return out

    def reach(self, deck, P, x0, ports=None):
        """how far points P (inches, a port's frame, placed x0 further in along X) may go out along X before one meets
        the side, the least over the ports (every one if None) and both sides (y mirrored), and where (the port and
        the point, in the starboard port's frame)"""
        best, at = np.inf, None
        Q = np.concatenate([P, P * np.array([1.0, -1.0, 1.0])]) + np.array([x0, 0.0, 0.0])
        for i, (T, _) in self.frames[deck].items():
            if ports is not None and i not in ports:
                continue
            O = pts(T, I(Q))
            X = T[:3, 0].tolist()
            for k, o in enumerate(O):
                hit = self.side[deck].ray_cast(o.tolist(), X, 3.0)
                if hit[0] is not None and hit[3] / IN < best:
                    best, at = hit[3] / IN, (i, np.round(Q[k] - [x0, 0, 0], 2).tolist())
        return best, at

    def head(self, i):
        """a gun deck port's head (the inner edge of its upper sill): the least height over the deck (inches, at the
        port's middle line) at which a ray out along its X meets the side rather than passing out through the port"""
        T = self.frames["gun_deck"][i][0]

        def through(z):
            v = self.face_x(self.wall["gun_deck"], T, 0.0, z)
            return v is None or v > 6.0
        lo, hi = 40.0, 66.0                                # the bore's height; under the wall's top over the port
        if not through(lo) or through(hi):
            raise SystemExit(f"guns: no head found over gun deck port {i}")
        for _ in range(40):
            m = 0.5 * (lo + hi)
            if through(m):
                lo = m
            else:
                hi = m
        return hi

    def pl24(self, i):
        """the gun deck's placement at port i: the common values and the port's own (port_overrides)"""
        pl = self.c["placement"]["gun_deck"]
        out = {k: v for k, v in pl.items() if k != "port_overrides"}
        for o in pl.get("port_overrides", []):
            if i in o["ports"]:
                out.update({k: v for k, v in o.items() if k not in ("ports", "why")})
        return out

    # --- placing them -------------------------------------------------------------------------------------------
    def fit_irons(self, deck, i, sd, bolts, train=None):
        """one gun's ringbolts fitted to its own side and deck: each eye stands standoff_in off the side (or the deck)
        where its surface comes nearest it (sampled all round the eye), its shank driven into_side_in into the face
        behind the eye's centre. bolts: {name: (y, z, spec, up)} (inches, the gun's own port frame; _L names at -y; the
        eye's plane holds the face's normal and up: EZ stands it on edge, EY lays it flat); train: (x, spec) for the
        ringbolt in the deck at (x, 0). Returns each eye's centre, its shank's reach behind it, and how far its centre
        stands from the face (the eye's size and standoff where the face is square to it, more where it leans)"""
        ir = self.c["irons"]
        so, into = ir["standoff_in"], ir["into_side_in"]
        eye_at, depth, fit = {}, {}, {}
        for nm, (y, z, sp, up) in bolts.items():
            y = -y if nm.endswith("_L") else y
            Q = eye_points(-EX, up, sp)
            xw = [self.wall_x(deck, i, sd, y + q[1], z + q[2]) for q in Q]
            xc = self.wall_x(deck, i, sd, y, z)
            if xc is None or any(v is None for v in xw):
                raise SystemExit(f"guns: no side behind the {deck} ringbolt {nm} at port {i} ({sd})")
            x = min(v - q[0] for v, q in zip(xw, Q)) - so
            eye_at[nm] = [x, y, z]
            depth[nm] = xc - x + into
            fit[nm] = round(xc - x, 2)
        if train is not None:
            x, sp = train
            Q = eye_points(EZ, EX, sp)
            zs = self.deck_zs(deck, i, sd, Q[:, :2] + [x, 0.0])
            zc = float(self.deck_zs(deck, i, sd, [[x, 0.0]])[0])
            if np.isnan(zs).any() or np.isnan(zc):
                raise SystemExit(f"guns: no deck under the train ringbolt at port {i} ({sd})")
            z = float((zs - Q[:, 2]).max()) + so
            eye_at["train"] = [x, 0.0, z]
            depth["train"] = z - zc + into
            fit["train"] = round(z - zc, 2)
        return eye_at, depth, fit

    def place_long(self):
        """the long guns' places along their ports' X (inches; a port's two guns alike, the ship being so):

        * run_in, where the recoil brings a gun and it is loaded: the muzzle muzzle_inboard_in inside the side's face
          beside the port's jambs at the bore's height, the barrel level on its quoin;
        * run_out: the carriage's front, trucks or level barrel run_out_gap_in off the side or the port's linings;
        * housed for sea (the lid shut): hauled out with the quoin out and the breech down on the bed
          (breech_on_bed_deg) until the muzzle's upper part comes housed_gap_in off the side over the port's head,
          where it is lashed to the housing bolts;

        then each gun's ringbolts and housing bolts fitted to its own side and deck (fit_irons)"""
        g, ir = self.L24, self.c["irons"]
        zb = g.zt + g.up
        B = np.concatenate(g.barrel().V)
        P = [np.concatenate(g.carriage().V), pts(g.barrel_T(0.0), B)]
        for (w, sd), Tt in g.truck_frames().items():
            P.append(pts(Tt, np.concatenate(g.truck(w).V)))
        P = np.concatenate(P)
        front = P[P[:, 0] > -20.0]
        chase = pts(g.barrel_T(g.e_bed), B[B[:, 0] + g.s_t > 60.0])
        top = float(chase[:, 2].max())                     # the housed muzzle's top over the deck
        self.x24, self.g24, ports = {}, {}, {}
        for i in self.c["placement"]["gun_deck"]["ports"]:
            pl = self.pl24(i)
            T, meta = self.frames["gun_deck"][i]
            ya, yf = meta["jambs_y_in"]
            ref = [v for v in (self.face_x(self.wall["gun_deck"], T, y, zb)
                               for y in (ya + 2.0, yf - 2.0, -(ya + 2.0), -(yf - 2.0))) if v is not None]
            x_in = min(ref) - pl["muzzle_inboard_in"] - (g.g["length_in"] - g.s_t)
            d, at = self.reach("gun_deck", front, -40.0, ports=[i])
            x_out = -40.0 + d - pl["run_out_gap_in"]
            dh, ath = self.reach("gun_deck", chase, -70.0, ports=[i])
            x_h = -70.0 + dh - pl["housed_gap_in"]
            head = self.head(i)
            if ath[1][2] < head or top < head + pl["housed_gap_in"]:
                raise SystemExit(f"guns: the housed gun at gun deck port {i} would go out through its port (its muzzle's "
                                 f"top {top:.2f} in, the port's head {head:.2f} in, it meets the side at {ath[1]})")
            if x_h < x_in:
                raise SystemExit(f"guns: the housed gun at gun deck port {i} stands inboard of run in")
            x_c = {"housed": round(x_h, 2), "run_in": round(x_in, 2), "run_out": round(x_out, 2)}
            self.x24[i] = x_c
            dev = []                                        # how far the deck lies off the frame's foot under each truck
            for xc in x_c.values():
                for nm, a in g.axles.items():
                    for sg in (1.0, -1.0):
                        dev.append(self.floor_z("gun_deck", T, xc + a["x"], sg * a["truck_y"]))
            ports[i] = {"carriage_x_in": x_c, "run_out_meets": at[1], "housed_meets": ath[1],
                        "head_in": round(head, 2), "housed_muzzle_top_in": round(top, 2),
                        "muzzle_ref_in": round(min(ref), 2), "trucks_deck_off_in": [round(min(dev), 3), round(max(dev), 3)]}
            for sd in ("S", "P"):
                bolts = {}
                for s2 in ("L", "R"):
                    bolts["breeching_" + s2] = (pl["breeching_bolt_y_in"], pl["breeching_bolt_z_in"], ir["ringbolt24"], EZ)
                    bolts["tackle_" + s2] = (pl["tackle_bolt_y_in"], pl["tackle_bolt_z_in"], ir["tackle_ring24"], EZ)
                    bolts["housing_" + s2] = (pl["housing_bolt_y_in"], pl["housing_bolt_z_in"], ir["housing24"], EY)
                eyes, depth, fit = self.fit_irons("gun_deck", i, sd, bolts, (g.train_x(x_in, pl), ir["tackle_ring24"]))
                self.g24[(i, sd)] = {"eyes": eyes, "depth": depth, "fit": fit}
        self.info["long24"] = {"ports": ports, "irons_off_face_in": {f"{sd}{i:02d}": G["fit"]
                                                                     for (i, sd), G in sorted(self.g24.items())}}

    def seat(self):
        """each gun deck port's frame set square to the deck under its gun: turned (a fraction of a degree about its X
        and Y) and moved along its Z (a fraction of an inch) onto the least squares plane through the deck under its
        eight trucks in each pose (place_long's), the origin kept under the same point of the side. The deck's sheer
        bends, so the plane at the side alone can leave a truck a third of an inch into the deck at the bow"""
        g = self.L24
        for i, x_c in self.x24.items():
            T, meta = self.frames["gun_deck"][i]
            P = []
            for xc in x_c.values():
                for nm, a in g.axles.items():
                    for sg in (1.0, -1.0):
                        x, y = xc + a["x"], sg * a["truck_y"]
                        P.append([x, y, self.floor_z("gun_deck", T, x, y)])
            P = np.array(P, float)
            c = np.linalg.lstsq(np.c_[np.ones(len(P)), P[:, 0], P[:, 1]], P[:, 2], rcond=None)[0]
            Tn = T @ in_m(frame(np.array([0.0, 0.0, c[0]]), EX, np.array([-c[1], -c[2], 1.0])))
            self.frames["gun_deck"][i] = (Tn, dict(meta, seat=[round(float(c[0]), 3), round(math.degrees(c[1]), 4),
                                                              round(math.degrees(c[2]), 4)]))

    def deck_field(self, deck, i, sd, x0=-222.0, x1=-2.0, y0=-84.0, y1=84.0, step=3.0):
        """the deck's height (inches) over the plane z = 0 of one gun's own port frame, on a grid over where its gear
        lies: a DeckField for its coils and the ropes lying on deck (the deck's sheer and camber differ from port to
        port, and a port side gun's left lies aft where its starboard twin's lies forward)"""
        xs = np.arange(x0, x1 + 1e-9, step)
        ys = np.arange(y0, y1 + 1e-9, step)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        H = self.deck_zs(deck, i, sd, np.c_[X.ravel(), Y.ravel()]).reshape(len(xs), len(ys))
        for a in range(len(xs)):                                  # past the deck's end: the nearest deck along y
            ok = ~np.isnan(H[a])
            if ok.any():
                H[a] = np.interp(ys, ys[ok], H[a][ok])
        rows = np.where(~np.isnan(H[:, 0]))[0]
        for a in range(len(xs)):                                  # then along x
            if np.isnan(H[a, 0]):
                H[a] = H[rows[np.argmin(np.abs(rows - a))]]
        return DeckField(xs, ys, H)

    COILS24 = ("tackle_L", "tackle_R", "train")
    COILS32 = ("tackle_L", "tackle_R")

    def rests(self):
        """how every gun's coils lie on its own deck: each coil's centre line, less the rope's radius, over the deck
        under it (inches: + clear of it, - into it), the least and the most over each kind's guns, poses and coils, and
        where; by_gun: each gun's least and most"""
        out = {}
        r24 = self.c["ropes"]["tackle24_circ_in"] / (2 * math.pi)
        r32 = self.c["ropes"]["tackle32c_circ_in"] / (2 * math.pi)
        for kind, deck, r, recs, names in (("long24", "gun_deck", r24, self.rig24, self.COILS24),
                                           ("carronade32", "spar_deck", r32, self.rig32, self.COILS32)):
            lo, hi, by = None, None, {}
            for (i, sd), info in sorted(recs.items()):
                gid = f"{sd}{i:02d}"
                g_lo, g_hi = np.inf, -np.inf
                for pose, L in info["coil_lines"].items():
                    for nm, P in zip(names, L):
                        z = self.deck_zs(deck, i, sd, P[::2, :2])
                        gap = P[::2, 2] - r - z
                        a, b = float(np.nanmin(gap)), float(np.nanmax(gap))
                        g_lo, g_hi = min(g_lo, a), max(g_hi, b)
                        if lo is None or a < lo[0]:
                            lo = (a, [gid, pose, nm])
                        if hi is None or b > hi[0]:
                            hi = (b, [gid, pose, nm])
                by[gid] = [round(g_lo, 3), round(g_hi, 3)]
            out[kind] = {"least_in": round(lo[0], 3), "at": lo[1], "most_in": round(hi[0], 3), "at_most": hi[1],
                         "by_gun": by}
        return out

    def balance(self):
        """turn each port's X about its Z (within a degree or so) so the side stands as far off the ringbolts on one
        side of the port as on the other: a least squares fit of the side's slope across the port at the ringbolts'
        places"""
        self.yaw_deg = {}
        for deck in self.DECKS:
            pl = self.c["placement"][deck]
            places = [(pl["breeching_bolt_y_in"], pl["breeching_bolt_z_in"]), (pl["tackle_bolt_y_in"], pl["tackle_bolt_z_in"])]
            for i, (T, meta) in list(self.frames[deck].items()):
                num = den = 0.0
                for y, z in places:
                    a, b = self.face_x(self.wall[deck], T, y, z), self.face_x(self.wall[deck], T, -y, z)
                    num += (a - b) * y
                    den += 2.0 * y * y
                deg = -math.degrees(num / den)
                self.frames[deck][i] = (T @ rot(EZ, deg), dict(meta, yaw_deg=round(deg, 3)))
                self.yaw_deg[(deck, i)] = deg

    def place_carr(self):
        """the carronades: the chock under each slide's fore end (its top a little over the waterway's highest point
        under any port's chock, its outboard end off_face_in off the bulwark at the chock's top), then each port's
        fighting bolt where its slide, bed and barrel run out, turned through train_deg each way, come no nearer that
        port's side (or the waterway, or the port's linings) than run_out_gap_in; each gun's ringbolts fitted to its own
        bulwark"""
        k, pl, ir = self.C32, self.c["placement"]["spar_deck"], self.c["irons"]
        sl = k.s
        ch = sl["chock"]
        B, D = k.barrel(), k.bed()
        Tb = k.bed_frame(k.x_run)
        hy = ch["half_y_in"]
        ys = np.linspace(-hy, hy, 7)
        ports = sorted(self.frames["spar_deck"])

        def plans(x_f, top):
            """each gun's chock plan: a grid of (x, y, the floor's height) under it, in the gun's own frame"""
            out = {}
            for i in ports:
                for sd in ("S", "P"):
                    xs = [self.wall_x("spar_deck", i, sd, y, z) for y in ys for z in (top - 0.3, top)]
                    xs = [v for v in xs if v is not None]
                    if not xs:
                        raise SystemExit(f"guns: no bulwark beside the chock at spar deck port {i} ({sd})")
                    x_out = min(xs) - ch["off_face_in"]
                    X, Y = np.meshgrid(np.linspace(x_f[i] - ch["behind_bolt_in"], x_out, 9), ys, indexing="ij")
                    Z = self.deck_zs("spar_deck", i, sd, np.c_[X.ravel(), Y.ravel()]).reshape(X.shape)
                    if np.isnan(Z).any():
                        raise SystemExit(f"guns: no deck under the chock at spar deck port {i} ({sd})")
                    out[(i, sd)] = np.stack([X, Y, Z], 2)
            return out
        x_f, top, at = {i: -6.0 for i in ports}, 6.0, {}
        for _ in range(8):
            self.chock_plans = plans(x_f, top)
            k.chock_top = round(max(G[:, :, 2].max() for G in self.chock_plans.values()) + ch["over_waterway_in"], 2)
            Sl = k.slide()
            P = np.concatenate([np.concatenate(Sl.V), pts(Tb, np.concatenate(D.V)),
                                pts(Tb @ k.barrel_frame(), np.concatenate(B.V))])
            P = P[(P[:, 0] > sl["front_in"] - 14.0) & (P[:, 2] > k.chock_top + 0.01)]
            new = {}
            for i in ports:
                best = np.inf
                for a in np.linspace(-sl["train_deg"], sl["train_deg"], 13):
                    d, w = self.reach("spar_deck", pts(rot(EZ, a), P), -40.0, ports=[i])
                    if d < best:
                        best, at[i] = d, (w[1], round(float(a), 1))
                new[i] = round(-40.0 + best - pl["run_out_gap_in"], 2)
            done = abs(k.chock_top - top) < 0.01 and all(abs(new[i] - x_f[i]) < 0.01 for i in ports)
            x_f, top = new, k.chock_top
            if done:
                break
        else:
            raise SystemExit("guns: the carronades' chocks and fighting bolts did not settle")
        self.x_f = x_f
        self.chock_plans = plans(x_f, k.chock_top)
        hi = max(G[:, :, 2].max() for G in self.chock_plans.values())
        if hi + ch["over_waterway_in"] > k.chock_top + 0.01:
            raise SystemExit(f"guns: the chocks' plan moved onto higher waterway ({hi:.2f} in)")
        self.x_bed = {"run_out": k.x_run, "recoil": k.x_run - pl["recoil_in"]}
        sp_b, sp_t = ir["ringbolt32c"], ir["tackle_ring32c"]
        self.c32 = {}
        for i in ports:
            for sd in ("S", "P"):
                bolts = {}
                for s2 in ("L", "R"):
                    bolts["breeching_" + s2] = (pl["breeching_bolt_y_in"], pl["breeching_bolt_z_in"], sp_b, EZ)
                    bolts["tackle_" + s2] = (pl["tackle_bolt_y_in"], pl["tackle_bolt_z_in"], sp_t, EZ)
                eyes, depth, fit = self.fit_irons("spar_deck", i, sd, bolts)
                self.c32[(i, sd)] = {"eyes": eyes, "depth": depth, "fit": fit}
        lo = min(G[:, :, 2].min() for G in self.chock_plans.values())
        self.info["carronade32"] = {
            "chock_top_in": k.chock_top, "chock_foot_in": [round(lo, 2), round(hi, 2)],
            "ports": {i: {"fighting_bolt_x_in": x_f[i], "front_meets": {"point_in": at[i][0], "train_deg": at[i][1]},
                          "muzzle_x_in": round(x_f[i] + k.x_run + k.g["length_in"] - k.s_l, 2)} for i in ports},
            "irons_off_face_in": {f"{sd}{i:02d}": G["fit"] for (i, sd), G in sorted(self.c32.items())}}

    def chocks(self):
        """every gun's chock, in the ship's frame (metres): a block on the waterway and deck (its foot each point's
        floor less let_in), its top level at the chock's top"""
        ch = self.c["slide"]["chock"]
        M = GPart()
        M.cur = "chock"
        top = self.C32.chock_top
        for (i, sd), G in sorted(self.chock_plans.items()):
            T = self.frames["spar_deck"][i][0]
            if sd == "P":
                T = mirror_frame(T)
            nx, ny = G.shape[:2]
            Bt = G.copy()
            Bt[:, :, 2] -= ch["let_in"]
            Tp = Bt.copy()
            Tp[:, :, 2] = top
            V = np.concatenate([Tp.reshape(-1, 3), Bt.reshape(-1, 3)])
            n = nx * ny
            idx = lambda a, b, lay: lay * n + a * ny + b      # noqa: E731
            F = []
            for a in range(nx - 1):
                for b in range(ny - 1):
                    F.append((idx(a, b, 0), idx(a + 1, b, 0), idx(a + 1, b + 1, 0), idx(a, b + 1, 0)))   # top
                    F.append((idx(a, b, 1), idx(a, b + 1, 1), idx(a + 1, b + 1, 1), idx(a + 1, b, 1)))   # foot
            ring = [(a, 0) for a in range(nx)] + [(nx - 1, b) for b in range(1, ny)] + \
                   [(a, ny - 1) for a in range(nx - 2, -1, -1)] + [(0, b) for b in range(ny - 2, 0, -1)]
            for q in range(len(ring)):
                (a0, b0), (a1, b1) = ring[q], ring[(q + 1) % len(ring)]
                F.append((idx(a0, b0, 1), idx(a1, b1, 1), idx(a1, b1, 0), idx(a0, b0, 0)))
            # faces out: fix each face's winding by its centre's side
            Vm = pts(T, I(V))
            c0 = Vm.mean(0)
            Fo = []
            for f in F:
                nrm = newell(Vm[list(f)])
                cen = Vm[list(f)].mean(0)
                Fo.append(f if nrm @ (cen - c0) >= 0 else f[::-1])
            M.add(Vm, Fo, OAK)
        return M

    def build(self):
        self.frames = {d: {i: self.port_frame(d, i) for i in self.c["placement"][d]["ports"]} for d in self.DECKS}
        self.trees()
        self.balance()
        self.place_long()              # where the trucks stand, then each port's plane fitted to the deck under them
        self.seat()
        self.place_long()
        self.place_carr()
        self.make()
        self.info["coils_on_deck"] = self.rests()
        return self

    # --- the meshes and their copies --------------------------------------------------------------------------
    def make(self):
        """the meshes in metres, each in its own frame (self.meshes): the shared parts, and each gun's gear in each pose
        and its irons, rigged at its own port (its own ringbolts, its own deck under its coils); the same in inches
        (self.parts, self.gear) for the local checks"""
        g, k, ir = self.L24, self.C32, self.c["irons"]
        self.parts = {"Gun24_Barrel": g.barrel(), "Gun24_Carriage": g.carriage(), "Gun24_Quoin": g.quoin(),
                      "Gun24_TruckFore": g.truck("fore_axle"), "Gun24_TruckHind": g.truck("hind_axle"),
                      "Carr32_Barrel": k.barrel(), "Carr32_Bed": k.bed(), "Carr32_Slide": k.slide()}
        M = {n: scaled(p, IN) for n, p in self.parts.items()}
        self.gear, self.rig24, self.rig32 = {}, {}, {}
        for (i, sd), G in sorted(self.g24.items()):
            gid = f"Gun24_{sd}{i:02d}"
            gear, irons, info = g.rig(self.x24[i], self.pl24(i), ir, G["depth"], G["eyes"],
                                      self.deck_field("gun_deck", i, sd), self.elev24)
            self.rig24[(i, sd)] = info
            for pose in POSES24:
                self.gear[(gid, pose)] = gear[pose]
                M[gid + "_Gear" + TAG[pose]] = scaled(gear[pose], IN)
            self.gear[(gid, "irons")] = irons
            M[gid + "_Irons"] = scaled(irons, IN)
        pl = self.c["placement"]["spar_deck"]
        for (i, sd), G in sorted(self.c32.items()):
            gid = f"Carr32_{sd}{i:02d}"
            gear, irons, info = k.rig(self.x_f[i], self.x_bed, pl, ir, G["depth"], G["eyes"],
                                      floor=self.deck_field("spar_deck", i, sd))
            self.rig32[(i, sd)] = info
            for pose in POSES32:
                self.gear[(gid, pose)] = gear[pose]
                M[gid + "_Gear" + TAG[pose]] = scaled(gear[pose], IN)
            self.gear[(gid, "irons")] = irons
            M[gid + "_Irons"] = scaled(irons, IN)
        M["Carr32_Chocks"] = self.chocks()
        self.meshes = M

    def assembly(self, gid, pose):
        """one gun with its carriage (or bed and slide) and gear in one pose, in its port's frame (inches)"""
        kind, sid = gid.split("_")
        i = int(sid[1:])
        P = self.parts
        a = GPart()
        if kind == "Gun24":
            g = self.L24
            e = self.elev24[pose]
            Tc = tr([self.x24[i][pose], 0.0, 0.0])
            a.extend(P["Gun24_Carriage"].moved(Tc))
            a.extend(P["Gun24_Barrel"].moved(Tc @ g.barrel_T(e)))
            xq = g.quoin_x(e)
            if xq is not None:
                a.extend(P["Gun24_Quoin"].moved(Tc @ tr([xq, 0.0, g.bed_top])))
            for (w, s2), Tt in g.truck_frames().items():
                a.extend(P["Gun24_Truck" + ("Fore" if w == "fore_axle" else "Hind")].moved(Tc @ Tt))
        else:
            k = self.C32
            Ts = tr([self.x_f[i], 0.0, 0.0])
            Tb = Ts @ k.bed_frame(self.x_bed[pose])
            a.extend(P["Carr32_Slide"].moved(Ts))
            a.extend(P["Carr32_Bed"].moved(Tb))
            a.extend(P["Carr32_Barrel"].moved(Tb @ k.barrel_frame()))
        a.extend(self.gear[(gid, pose)])
        a.extend(self.gear[(gid, "irons")])
        return a

    def gun_frames(self):
        """every gun: (kind, deck, port, side, the port's frame in the ship)"""
        out = []
        for kind, deck in (("Gun24", "gun_deck"), ("Carr32", "spar_deck")):
            for i, (T, _) in self.frames[deck].items():
                out += [(kind, deck, i, "S", T), (kind, deck, i, "P", mirror_frame(T))]
        return sorted(out, key=lambda r: (r[0], r[3], r[2]))

    def instances(self):
        """every copy: [(object name, mesh, 4x4 in the ship's frame (metres), collection)]. Collections: Guns (each
        gun's irons, the carronades' slides and chocks), Guns_Housed, Guns_RunIn and Guns_RunOut (the long guns:
        carriage, barrel, quoin (but housed: it is out), trucks and gear in each pose), Carronades_RunOut and
        Carronades_Recoil (each carronade's bed, barrel and gear). The housed long guns and the run-out carronades are
        shown; the other poses are hidden."""
        g, k = self.L24, self.C32
        out = [("Carr32_Chocks", "Carr32_Chocks", np.eye(4), "Guns")]
        for kind, deck, i, sd, T in self.gun_frames():
            gid = f"{kind}_{sd}{i:02d}"
            out.append((gid + "_Irons", gid + "_Irons", T, "Guns"))
            if kind == "Gun24":
                for pose in POSES24:
                    tag = "" if pose == "housed" else "_" + TAG[pose]
                    cn, e = COLL24[pose], self.elev24[pose]
                    Tc = T @ in_m(tr([self.x24[i][pose], 0.0, 0.0]))
                    out.append((gid + "_Carriage" + tag, "Gun24_Carriage", Tc, cn))
                    out.append((gid + "_Barrel" + tag, "Gun24_Barrel", Tc @ in_m(g.barrel_T(e)), cn))
                    xq = g.quoin_x(e)
                    if xq is not None:
                        out.append((gid + "_Quoin" + tag, "Gun24_Quoin", Tc @ in_m(tr([xq, 0.0, g.bed_top])), cn))
                    for (w, s2), Tt in g.truck_frames().items():
                        nm = "TruckFore" if w == "fore_axle" else "TruckHind"
                        out.append((f"{gid}_{nm}{s2}{tag}", "Gun24_" + nm, Tc @ in_m(Tt), cn))
                    out.append((gid + "_Gear" + TAG[pose], gid + "_Gear" + TAG[pose], T, cn))
            else:
                Ts = T @ in_m(tr([self.x_f[i], 0.0, 0.0]))
                out.append((gid + "_Slide", "Carr32_Slide", Ts, "Guns"))
                for pose in POSES32:
                    tag = "" if pose == "run_out" else "_" + TAG[pose]
                    cn = COLL32[pose]
                    Tb = Ts @ in_m(k.bed_frame(self.x_bed[pose]))
                    out.append((gid + "_Bed" + tag, "Carr32_Bed", Tb, cn))
                    out.append((gid + "_Barrel" + tag, "Carr32_Barrel", Tb @ in_m(k.barrel_frame()), cn))
                    out.append((gid + "_Gear" + TAG[pose], gid + "_Gear" + TAG[pose], T, cn))
        return out

    def triangles(self):
        """the meshes' triangles (shared: the guns, carriages and their parts; per gun: each gun's gear and irons) and
        the copies' as drawn (the shown poses) and in all"""
        uni = {n: m.tris() for n, m in self.meshes.items()}
        drawn = {"gun_deck": 0, "spar_deck": 0}
        every = 0
        inst = self.instances()
        for nm, mesh, _, coll in inst:
            every += uni[mesh]
            if coll in self.SHOWN:
                drawn["spar_deck" if mesh.startswith("Carr32") else "gun_deck"] += uni[mesh]
        own = {n: v for n, v in uni.items() if re.match(r"(Gun24|Carr32)_[SP]\d\d_", n)}
        return {"unique": uni, "unique_total": sum(uni.values()), "shared_total": sum(uni.values()) - sum(own.values()),
                "per_gun_total": sum(own.values()), "as_drawn": dict(drawn, total=sum(drawn.values())),
                "all_poses": every, "copies": len(inst)}

    def rig_stats(self):
        """each gun's gear measured (build.json): its ropes' lengths, the breeching, the tackles (where their blocks
        and coils lie, the gaps between their blocks) and the long guns' muzzle lashing, by kind and gun"""
        out = {"ropes_in": {}, "breeching_in": {}, "tackles": {}, "lashing_in": {}}
        for kind, recs in (("long24", self.rig24), ("carronade32", self.rig32)):
            for key in out:
                out[key][kind] = {}
            for (i, sd), info in sorted(recs.items()):
                gid = f"{sd}{i:02d}"
                out["ropes_in"][kind][gid] = info["ropes_in"]
                out["breeching_in"][kind][gid] = info["breeching"]
                out["tackles"][kind][gid] = info["tackles"]
                if info.get("lashing_in"):
                    out["lashing_in"][kind][gid] = info["lashing_in"]
        return out

    # --- checks -------------------------------------------------------------------------------------------------
    def local_room(self):
        """inside each gun and its gear (every gun and pose, in its port's frame): the pairs of labels whose surfaces
        cross, less those that meet by design (LOCAL_MEETS) within their depth; by_design: each such pair's deepest"""
        meet, worst = [], {}
        for kind, deck, i, sd, T in self.gun_frames():
            gid = f"{kind}_{sd}{i:02d}"
            for pose in (POSES24 if kind == "Gun24" else POSES32):
                for (a, b), (n, d) in sorted(crossings(self.assembly(gid, pose), near=8.0).items()):
                    a, b = str(a), str(b)
                    why = allowed(LOCAL_MEETS, a, b)
                    if why and d <= why[1]:
                        key = (kind, a, b)
                        if key not in worst or d > worst[key][-1]:
                            worst[key] = [kind, a, b, why[0], gid, pose, d]
                    else:
                        meet.append([gid, pose, a, b, n, d] + (["deeper than " + str(why[1]) + " in"] if why else []))
        return {"meet": meet, "by_design": [v for _, v in sorted(worst.items())]}

    def fat_chase(self, s0=60.0, fat=1.0):
        """the long gun's chase from s0 (from the base ring's back) to the muzzle, fat inches fatter all round: what an
        open lid must clear, in the barrel's frame (metres; V, T)"""
        g = self.L24
        V, T, _ = self.parts["Gun24_Barrel"].tri_arrays()
        T = T[np.all(V[T][:, :, 0] + g.s_t >= s0, axis=1)]
        V = V.copy()
        r = np.hypot(V[:, 1], V[:, 2] - g.up)
        m = r > 1e-6
        f = (r[m] + fat) / r[m]
        V[m, 1] *= f
        V[m, 2] = g.up + (V[m, 2] - g.up) * f
        return V * IN, T

    def room(self, objs, lids, near=0.15):
        """The guns' clearance check (build.json guns.room). objs: {name: (V (n, 3), T (m, 3))}, every mesh of the ship
        but the guns' own and the reference, in the ship's frame (metres; the sails and running rigging in every
        state); lids: {name: (V (n, 3) in the lid's frame, T (m, 3), 4x4 frame)}, the gun deck's port lids (a turn
        about the frame's +X opens one). Returns:

        * local: local_room();
        * ship: each copy, in each pose, against the ship (the chocks too): the pairs (a gun's part, an object) whose
          surfaces cross, less those that meet by design (SHIP_MEETS) within their depth; a long gun run out has its lid
          open (left out here: lids);
        * elevated: each long gun run out with its barrel at the least and the most elevation (quoin home, breech on
          the bed), against the ship but the lids, as ship;
        * by_design: those that meet by design, each with the deepest any copy goes;
        * guns: copies that cross other copies (every pose against the same pose);
        * train: the carronades' slides, beds and barrels (both poses) turned through train_deg each way (steps of a
          third) against the ship: as ship, for the turned parts (the gear is drawn square to the side only);
        * lids: each gun deck lid's swing (lid_max_deg: the last 5 deg step from 30 to 180 before it meets the ship
          more than 0.12 in deep, the hinge's knuckles left out), the least opening (5 deg steps, lid_open_deg) at which
          its gun run out clears it by an inch (its chase, from 60 in, made an inch fatter) at every elevation from
          quoin home to breech on the bed, or lid_max_deg if none does, and the elevations the run-out gun then has
          (run_out_elevation_deg: the most to 0.05 deg)."""
        from mathutils.bvhtree import BVHTree
        objs = dict(objs)
        V, T, L = self.meshes["Carr32_Chocks"].tri_arrays()
        objs["Carr32_Chocks"] = (V, T)
        names = sorted(objs)
        own, Vs, Ts, nv, toff = [], [], [], 0, {}
        for n in names:
            V, T = objs[n]
            toff[n] = len(own)
            own += [n] * len(T)
            Vs.append(np.asarray(V, float))
            Ts.append(np.asarray(T, int) + nv)
            nv += len(V)
        own = np.array(own)
        ship = BVHTree.FromPolygons(np.concatenate(Vs).tolist(), np.concatenate(Ts).tolist(), all_triangles=True)
        otrees = {}

        def otree(n):
            if n not in otrees:
                V, T = objs[n]
                otrees[n] = BVHTree.FromPolygons(np.asarray(V).tolist(), np.asarray(T).tolist(), all_triangles=True)
            return otrees[n]
        tri = {n: m.tri_arrays() for n, m in self.meshes.items()}

        def kind(o):
            return "Lid" if o.startswith("Lid_") else o

        def meets(V, T, L, skip=()):
            """{(label, object): (count, depth in inches)} for one placed part against the ship"""
            t = BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True)
            pairs = {}
            for i, j in t.overlap(ship):
                o = own[j]
                if o in skip:
                    continue
                pairs.setdefault((L[i], o), ([], []))
                pairs[(L[i], o)][0].append(i)
                pairs[(L[i], o)][1].append(j)
            out = {}
            for (lab, o), (I_, J_) in pairs.items():
                Vo, To = objs[o]
                J_ = np.array(J_) - toff[o]
                P = np.asarray(Vo)[np.asarray(To)[np.unique(J_)]].reshape(-1, 3)
                mine = np.unique(T[L == lab].ravel())
                Vm = V[mine]
                Vm = Vm[np.all((Vm >= P.min(0) - near) & (Vm <= P.max(0) + near), axis=1)]
                Q = V[T[np.unique(I_)]].reshape(-1, 3)
                Vt = np.asarray(Vo)
                Vt = Vt[np.all((Vt >= Q.min(0) - near) & (Vt <= Q.max(0) + near), axis=1)]
                d = max(behind(Vm, otree(o), near), behind(Vt, t, near))
                k_ = (lab, kind(o))
                prev = out.get(k_, (0, 0.0))
                out[k_] = (prev[0] + len(I_), max(prev[1], round(d / IN, 2)))
            return out
        ship_meet, by_design, train, elevated = [], {}, [], []

        def record(where, res, dest):
            for (lab, o), (n, d) in sorted(res.items()):
                why = allowed(SHIP_MEETS, lab, o)
                if why and d <= why[1]:
                    k_ = (lab, o)
                    by_design[k_] = [lab, o, why[0], max(d, by_design.get(k_, [0, 0, 0, 0.0])[3])]
                else:
                    dest.append(where + [lab, o, n, d] + (["deeper than " + str(why[1]) + " in"] if why else []))
        # each copy in each pose; the long guns run out with their lids open
        per_gun = {}
        for nm, mesh, Mx, coll in self.instances():
            V, T, L = tri[mesh]
            if mesh == "Carr32_Chocks":
                record(["chocks", ""], meets(V, T, L, skip=("Carr32_Chocks",)), ship_meet)
                continue
            Vw = pts(Mx, V)
            skip = tuple(lids) if coll == "Guns_RunOut" else ()
            record([nm, coll], meets(Vw, T, L, skip), ship_meet)
            gid = "_".join(nm.split("_")[:2])
            per_gun.setdefault((gid, coll if coll != "Guns" else None), []).append((Vw, T, L, mesh))
        # copies against copies, pose by pose (the always-shown parts with each pose)
        groups = {}
        for (gid, coll), items in per_gun.items():
            if coll is None:
                continue
            parts = items + per_gun.get((gid, None), [])
            V = np.concatenate([p[0] for p in parts])
            offs = np.cumsum([0] + [len(p[0]) for p in parts])[:-1]
            T = np.concatenate([p[1] + o for p, o in zip(parts, offs)])
            groups.setdefault(coll, []).append((gid, V, T))
        guns_meet = []
        for coll, items in groups.items():
            for a in range(len(items)):
                ga, Va, Ta = items[a]
                ta = BVHTree.FromPolygons(Va.tolist(), Ta.tolist(), all_triangles=True)
                lo, hi = Va.min(0), Va.max(0)
                for gb, Vb, Tb in items[a + 1:]:
                    if np.any(Vb.min(0) > hi) or np.any(Vb.max(0) < lo):
                        continue
                    ov = ta.overlap(BVHTree.FromPolygons(Vb.tolist(), Tb.tolist(), all_triangles=True))
                    if ov:
                        guns_meet.append([coll, ga, gb, len(ov)])
        # the carronades trained
        g, k = self.L24, self.C32
        sl = k.s
        steps = [a for a in np.linspace(-sl["train_deg"], sl["train_deg"], 7) if abs(a) > 1e-9]
        for kind_, deck, i, sd, T0 in self.gun_frames():
            if kind_ != "Carr32":
                continue
            for a in steps:
                Ts = T0 @ in_m(tr([self.x_f[i], 0.0, 0.0]) @ rot(EZ, a))
                for pose in POSES32:
                    Tb = Ts @ in_m(k.bed_frame(self.x_bed[pose]))
                    for mesh, Mx in (("Carr32_Slide", Ts), ("Carr32_Bed", Tb), ("Carr32_Barrel", Tb @ in_m(k.barrel_frame()))):
                        if mesh == "Carr32_Slide" and pose == "recoil":
                            continue
                        V, T, L = tri[mesh]
                        record([f"Carr32_{sd}{i:02d}", pose, round(float(a), 1)], meets(pts(Mx, V), T, L), train)
        # the long guns run out, elevated and depressed
        Vb, Tb_, Lb = tri["Gun24_Barrel"]
        for kind_, deck, i, sd, T0 in self.gun_frames():
            if kind_ != "Gun24":
                continue
            for e in (g.e_home, g.e_bed):
                Mx = T0 @ in_m(tr([self.x24[i]["run_out"], 0.0, 0.0]) @ g.barrel_T(e))
                record([f"Gun24_{sd}{i:02d}", "run_out", round(e, 2)], meets(pts(Mx, Vb), Tb_, Lb, tuple(lids)), elevated)
        # each lid: how far it swings, how far it must open for its gun run out to elevate
        Vf, Tf = self.fat_chase()
        sweep = [g.e_home] + [float(e) for e in np.arange(-1.0, 10.01, 1.0)] + [g.e_bed]
        fit = {}
        for kind_, deck, i, sd, T0 in self.gun_frames():
            if kind_ != "Gun24":
                continue
            ln = f"Lid_{i:02d}_{sd}"
            if ln not in lids:
                fit[ln] = {"lid_max_deg": None, "lid_open_deg": None, "why": "no lid"}
                continue
            Vl, Tl, Ml = (np.asarray(v) for v in lids[ln])
            Vl, Tl, Ml = Vl.astype(float), Tl.astype(int), Ml.astype(float)
            Tk = Tl[~np.all(np.hypot(Vl[Tl][:, :, 1], Vl[Tl][:, :, 2]) < 1.3 * IN, axis=1)]
            Lk = np.array(["lid"] * len(Tk))

            def lid_at(a):
                return pts(Ml @ rot(EX, a), Vl)
            lid_max, hit = None, None
            for a in range(30, 181, 5):
                res = meets(lid_at(a), Tk, Lk, skip=(ln,))
                deep = [[o, d] for (_, o), (n, d) in res.items() if d > 0.12]
                if deep:
                    hit = [a] + max(deep, key=lambda r: r[1])
                    break
                lid_max = a
            x_out = self.x24[i]["run_out"]

            def chase_tree(e):
                Mx = T0 @ in_m(tr([x_out, 0.0, 0.0]) @ g.barrel_T(e))
                return BVHTree.FromPolygons(pts(Mx, Vf).tolist(), Tf.tolist(), all_triangles=True)
            ctrees = {e: chase_tree(e) for e in sweep}
            lid_tree = {}

            def clear(a, e):
                if a not in lid_tree:
                    lid_tree[a] = BVHTree.FromPolygons(lid_at(a).tolist(), Tl.tolist(), all_triangles=True)
                t = ctrees[e] if e in ctrees else chase_tree(e)
                return not lid_tree[a].overlap(t)
            lid_open = None
            for a in range(5, (lid_max or 0) + 1, 5):
                if all(clear(a, e) for e in sweep):
                    lid_open = a
                    break
            rec = {"lid_max_deg": lid_max, "meets_past_it": hit}
            if lid_open is not None:
                rec.update(lid_open_deg=lid_open, run_out_elevation_deg=[round(g.e_home, 2), round(g.e_bed, 2)])
            elif lid_max is not None:
                rec["lid_open_deg"] = lid_max
                ok = [clear(lid_max, e) for e in sweep]
                if ok[0]:
                    j = ok.index(False)                     # the first elevation the lid stops (one does: no lid_open)
                    lo_, hi_ = sweep[j - 1], sweep[j]
                    while hi_ - lo_ > 0.05:
                        m_ = 0.5 * (lo_ + hi_)
                        if clear(lid_max, m_):
                            lo_ = m_
                        else:
                            hi_ = m_
                    rec["run_out_elevation_deg"] = [round(g.e_home, 2), round(lo_, 2)]
                else:
                    rec["run_out_elevation_deg"] = None
            else:
                rec["lid_open_deg"] = None
            fit[ln] = rec
        self.lid_fit = fit
        return {"local": self.local_room(), "ship": ship_meet, "elevated": elevated,
                "by_design": [v for _, v in sorted(by_design.items())], "guns": guns_meet, "train": train, "lids": fit}

    # --- for the game ---------------------------------------------------------------------------------------------
    def game_data(self):
        """guns.json: the meshes, each gun's port frame and how its parts stand in each pose (metres, the ship's frame:
        X forward, Y starboard, Z up)"""
        g, k = self.L24, self.C32

        def fr(T):
            return {"origin_m": np.round(T[:3, 3], 5).tolist(), "x": np.round(T[:3, 0], 6).tolist(),
                    "y": np.round(T[:3, 1], 6).tolist(), "z": np.round(T[:3, 2], 6).tolist()}

        def m(v):
            return round(float(v) * IN, 5)
        tris = self.triangles()["unique"]
        desc = {
            "Gun24_Barrel": "the long 24-pounder's barrel: origin on the trunnions' axis, X along the bore (the bore's "
                            "axis bore_over_trunnions_m above the origin), Y along the trunnions (it elevates about Y)",
            "Gun24_Carriage": "its truck carriage: origin on the deck under the trunnions' middle, X toward the muzzle",
            "Gun24_Quoin": "its quoin, the wedge under the breech that sets the elevation: origin on the bed's top under "
                           "its thick end's back, X toward the muzzle",
            "Gun24_TruckFore": "a fore truck (the same either side): origin at its centre, Y along its axle",
            "Gun24_TruckHind": "a hind truck",
            "Gun24 GearHoused": "this gun's breeching (its slack hanging), side tackles and train tackle hooked, its "
                                "muzzle lashed to the housing bolts, the rings and the coiled falls, housed for sea; in "
                                "its port's frame",
            "Gun24 GearRunIn": "the same run in for loading (the breeching taut, where the recoil brings the gun up; no "
                               "lashing)",
            "Gun24 GearRunOut": "the same run out (the breeching's slack in bights on the deck, the coils holding what "
                                "the tackles let go)",
            "Gun24 Irons": "this gun's ringbolts (four in the side, one in the deck) and its two housing bolts over the "
                           "port, fitted to its own side and deck; in its port's frame",
            "Carr32_Barrel": "the 32-pounder carronade's barrel: origin on the loop's bolt, X along the bore (elevates "
                             "about Y)",
            "Carr32_Bed": "its bed: origin on the slide's top under the loop's bolt, X along the slide",
            "Carr32_Slide": "its slide: origin on the deck on the fighting bolt's axis, X toward the port; trains about "
                            "its Z",
            "Carr32 GearRunOut": "this carronade's breeching and side tackles run out (the slide square to the side), in "
                                 "its port's frame",
            "Carr32 GearRecoil": "the same recoiled (the breeching taut)",
            "Carr32 Irons": "its ringbolts, fitted to its own bulwark; in its port's frame",
            "Carr32_Chocks": "the chocks under the slides' fore ends, every port and both sides, in the ship's frame "
                             "(each fitted to its own waterway: not a copy)"}
        out_m = {}
        for n in sorted(self.meshes):
            mt = re.match(r"(Gun24|Carr32)_([SP]\d\d)_(\w+)$", n)
            out_m[n] = {"frame": desc[mt.group(1) + " " + mt.group(3)] if mt else desc[n], "triangles": tris[n]}
        long_guns, carrs = [], []
        for kind, deck, i, sd, T in self.gun_frames():
            gid = f"{kind}_{sd}{i:02d}"
            rec = {"id": f"{sd}{i:02d}", "port": i, "side": "starboard" if sd == "S" else "port", "frame": fr(T),
                   "yaw_deg": round(self.yaw_deg[(deck, i)], 3) * (1 if sd == "S" else -1), "irons": gid + "_Irons"}
            if kind == "Gun24":
                rec["carriage_x_m"] = {p: m(v) for p, v in self.x24[i].items()}
                rec["gear"] = {p: gid + "_Gear" + TAG[p] for p in POSES24}
                rec["lid"] = f"Lid_{i:02d}_{sd}"
                lf = self.lid_fit.get(rec["lid"])
                if lf:
                    rec.update({kk: lf.get(kk) for kk in ("lid_open_deg", "lid_max_deg", "run_out_elevation_deg")})
                long_guns.append(rec)
            else:
                rec["fighting_bolt_x_m"] = m(self.x_f[i])
                rec["gear"] = {p: gid + "_Gear" + TAG[p] for p in POSES32}
                carrs.append(rec)
        trucks = {f"{'fore' if w == 'fore_axle' else 'hind'}_{s2}": {"mesh": "Gun24_Truck" + ("Fore" if w == "fore_axle" else "Hind"),
                                                                    "origin_m": np.round(Tt[:3, 3] * IN, 5).tolist()}
                  for (w, s2), Tt in g.truck_frames().items()}
        es = list(np.arange(math.ceil(g.e_home * 2) / 2, g.e_thin, 0.5))
        quoin = [[round(g.e_home, 2), m(g.quoin_x(g.e_home))]] + [[round(float(e), 2), m(g.quoin_x(e))] for e in es
                                                                  if e > g.e_home + 1e-6] + \
                [[round(g.e_thin, 2), m(g.quoin_x(g.e_thin))]]
        return {
            "frames_note": "a gun's port frame: origin on the deck under the point where the port's middle line meets "
                           "the side's inner face at the ringbolts' height, X out through the port, Z the deck's normal, "
                           "Y = Z x X (the gun's right). A port side gun is its starboard twin turned (not mirrored). "
                           "yaw_deg: how far X was turned from the side's normal to fit the ringbolts",
            "meshes": out_m,
            "long24": {
                "note": "the gun deck's long 24-pounders. Each gun: its carriage's origin at carriage_x_m[pose] along its "
                        "port's X (the carriage's axes the port's); the barrel at barrel_in_carriage_m in the carriage's "
                        "frame, turned about its own Y (the trunnions) to the pose's elevation (positive raises the "
                        "muzzle: a turn of -elevation about +Y); the quoin under the breech where quoin.x_m_by_deg puts "
                        "it for that elevation (along the carriage's X, at quoin.z_m), but housed (out: the breech on "
                        "the bed); the trucks at their origin_m (turn each about its Y as the carriage moves: radius "
                        "truck_radius_m); the gun's own gear mesh for the pose and its irons, in its port's frame. "
                        "Housed (the pose for sea, shown): the lid shut, the barrel at breech_on_bed_deg, its muzzle "
                        "against the side over the port's head and lashed there. Run in: the lid shut or open, the "
                        "barrel level; where the recoil brings it and it is loaded (slice 17 fires it from run out to "
                        "here). Run out: open the lid to lid_open_deg (a turn about the lid's own +X); the gun elevates "
                        "within run_out_elevation_deg (as far as the lid lets it where lid_open_deg is the lid's own "
                        "limit, lid_max_deg)",
                "barrel_in_carriage_m": [0.0, 0.0, m(g.zt)], "bore_over_trunnions_m": m(g.up),
                "elevation": {"quoin_home_deg": round(g.e_home, 2), "quoin_thin_deg": round(g.e_thin, 2),
                              "breech_on_bed_deg": round(g.e_bed, 2),
                              "poses_deg": {p: round(v, 2) for p, v in self.elev24.items()},
                              "note": "with the quoin under the breech the barrel elevates from quoin_home_deg (its "
                                      "thick end under the base ring) to quoin_thin_deg (its thin end); drawn right "
                                      "out, the breech comes down on the bed at breech_on_bed_deg, the most it "
                                      "elevates (housed it lies so)"},
                "quoin": {"mesh": "Gun24_Quoin", "z_m": m(g.bed_top), "x_m_by_deg": quoin},
                "pan_in_barrel_m": np.round(np.asarray(g.pan) * IN, 5).tolist(),
                "vent_in_barrel_m": np.round(np.asarray(g.vent_mouth) * IN, 5).tolist(),
                "truck_radius_m": {"fore": m(g.axles["fore_axle"]["R"]), "hind": m(g.axles["hind_axle"]["R"])},
                "trucks": trucks, "guns": long_guns},
            "carronade32": {
                "note": "the quarterdeck's and forecastle's 32-pounder carronades: each gun's slide with its origin at "
                        "fighting_bolt_x_m along its port's X, turned about its Z within train_deg; the bed's origin at "
                        "bed_x_m along the slide and bed_z_m over the deck (the slide's top), the barrel at "
                        "barrel_in_bed_m; the gun's own gear mesh for the pose and its irons in its port's frame (drawn "
                        "with the slide square to the side)",
                "train_deg": [-k.s["train_deg"], k.s["train_deg"]],
                "bed_x_m": {p: m(v) for p, v in self.x_bed.items()}, "bed_z_m": m(k.top),
                "barrel_in_bed_m": [0.0, 0.0, m(k.bolt_z)], "bore_over_bolt_m": m(k.drop),
                "pan_in_barrel_m": np.round(np.asarray(k.pan) * IN, 5).tolist(),
                "vent_in_barrel_m": np.round(np.asarray(k.vent_mouth) * IN, 5).tolist(),
                "chocks": "Carr32_Chocks", "guns": carrs}}


def eye_points(n_face, up, sp, k1=24, k2=12):
    """points all over an eyebolt's eye (centred on the origin, its plane holding n_face and up; spec sp: eye, bar):
    where it comes nearest a face it stands off"""
    a1 = unit(n_face)
    a2 = unit(np.asarray(up, float) - (np.asarray(up, float) @ a1) * a1)
    b = np.cross(a1, a2)
    al = np.linspace(0.0, 2 * math.pi, k1, endpoint=False)[:, None, None]
    be = np.linspace(0.0, 2 * math.pi, k2, endpoint=False)[None, :, None]
    Q = (sp["eye"] + sp["bar"] * np.cos(be)) * (np.cos(al) * a1 + np.sin(al) * a2) + sp["bar"] * np.sin(be) * b
    return Q.reshape(-1, 3)
