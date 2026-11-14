"""Bluebonnet's finished shell: paint lines, lead casting, the rudder cut out and its stock (docs/jclass-2).

    python shell.py [out dir]        writes shell.json (the checks); build_jclass.py imports it for the Blender build

Pure geometry (numpy and scipy, no Blender), on top of slice 1's surface (loft.py), which is the outside of the
plating: nothing here moves the hull, so slice 1's lines, rule and hydrostatics stand.

How the shell is meshed
-----------------------
The surface is sampled on a (u, v) grid as in slice 1 and split into triangles. Each line the finish needs is the zero
of a "field" over the hull (finish_bluebonnet.json):

  rudder     in the rudder's own frame (x_l aft square to the stock, h up it, r from its axis): aft of the axis, and
             below a flat shoulder square to the stock or outside a cone about it (the head)
  keel cut   aft of the keel's after face ('slot' forward of the axis) up to 'head_gap' over the shoulder, and outside
             the cone less 'head_gap' above it: the keel and deadwood cut away round the rudder
  lead       z less the lead casting's top (solved on this mesh: build)
  boot top   z less the boot top's lower and upper lines (heights above the load waterline, rising toward the ends)
  cove       z less the sheer's height less the cove line's two edges

Every triangle a field crosses is split along the field's zero, the new vertex found by bisection along the edge's
(u, v) so it lies on the surface itself, and shared edges split once, so the mesh stays closed. The lines come out
exact and crisp whatever the grid, and each triangle is then labelled by the fields' signs: rudder, slot (dropped),
lead ('Keel'), bottom ('Antifouling'), boot top ('Bootstripe'), cove ('CoveStripe') or topsides ('Topsides'), the
game's hull slot names (BoatModelVisuals.cpp, boat skins).

The rudder and the keel are closed across their cuts by strips of curves square to the stock, one curve per vertex of
the cut's edge, so they meet the surface's triangles edge to edge. Every curve is a circle about the stock's axis or
lies in a plane square to it, so the rudder turns along its own closing and never into the keel's: its leading edge is
a half circle about the axis as wide as the rudder there (the nose), in a groove 'gap' wider in the keel's after face;
its head is the shoulder (straight across) and then the cone (arcs about the axis), under the deadwood's own.

The plating is not modelled: each face corner carries a 'Plating' UV, (x, girth below the sheer) in metres, from which
the paint's material draws the plate seams, butts and rivets (build_jclass.py's node group; the game's material later).
"""
import json
import math
import os
import sys

import numpy as np
from scipy.interpolate import BSpline, RegularGridInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402

FIN = json.load(open(os.path.join(HERE, "finish_bluebonnet.json")))
PAINT, PLATE, RUD = FIN["paint"], FIN["plating"], FIN["rudder"]

NU, NV = 460, 120              # the shell's grid before the cuts (slice 1's was 420 x 104)
ARC_NU, ARC_NV = 500, 700      # the girth table for the plating UV
NOSE_J = 10                    # segments across the rudder's nose and the keel's groove (port to starboard)
NO_PLATING = -1.0              # the plating UV's V where there is no plating (lead, rudder, closings, transom)
DECK_CAMBER = 0.11             # m of crown at the widest beam (about 4 in, the period's figure for a deck this wide)
DECK_X = (loft.END["transom_top"][0], loft.END["stem_head"][0])
HDM = float(loft.DECK_HB(np.linspace(*DECK_X, 4000)).max())     # the deck's widest half-breadth


def deck_z(x, y):
    """The deck's height at (x, y): the sheer plus the beam camber. Every deck beam is cut from one mould (a parabola
    DECK_CAMBER high over the widest beam), so the deck rises less where it is narrower: z = sheer + K (hd^2 - y^2),
    K = DECK_CAMBER / HDM^2, with hd the deck's half-breadth at x (slice 3; slice 2's placeholder rose in proportion to
    hd instead)."""
    xc = np.clip(x, *DECK_X)
    hd = loft.DECK_HB(xc)
    return loft.SHEER(xc) + DECK_CAMBER * (hd * hd - np.asarray(y, float) ** 2) / (HDM * HDM)


# ------------------------------------------------------------------------------------------------- the surface
class Surface:
    """Slice 1's B-spline hull surface at any (u, v): u from the transom to the stem, v from the keel to the sheer."""

    def __init__(self):
        self.P = loft.control_net()
        nr, nc, _ = self.P.shape
        self.ku, self.kv = loft._knots(nr), loft._knots(nc)

    @staticmethod
    def _basis(knots, t):
        t = np.atleast_1d(np.asarray(t, float))
        end = t >= 1.0 - 1e-12
        N = BSpline.design_matrix(np.clip(t, 0.0, 1.0 - 1e-12), knots, loft.DEG).toarray()
        N[end] = 0.0
        N[end, -1] = 1.0
        return N

    def at(self, u, v):
        """Points at paired parameters: (n,), (n,) -> (n, 3)."""
        return np.einsum("ni,ijk,nj->nk", self._basis(self.ku, u), self.P, self._basis(self.kv, v))

    def grid(self, us, vs):
        return np.einsum("ui,ijk,vj->uvk", self._basis(self.ku, us), self.P, self._basis(self.kv, vs))

    def normals(self, u, v, h=1e-5):
        """Unit normals (unoriented) at paired parameters by central differences; NaN where the surface collapses (the
        stem head, where every control point of the last row is the same point)."""
        u, v = np.asarray(u, float), np.asarray(v, float)
        u0, u1 = np.clip(u - h, 0, 1), np.clip(u + h, 0, 1)
        v0, v1 = np.clip(v - h, 0, 1), np.clip(v + h, 0, 1)
        Pu = (self.at(u1, v) - self.at(u0, v)) / (u1 - u0)[:, None]
        Pv = (self.at(u, v1) - self.at(u, v0)) / (v1 - v0)[:, None]
        n = np.cross(Pu, Pv)
        L = np.linalg.norm(n, axis=1, keepdims=True)
        return np.where(L > 1e-9 * np.maximum(np.linalg.norm(Pu, axis=1, keepdims=True)
                                              * np.linalg.norm(Pv, axis=1, keepdims=True), 1e-30), n / np.maximum(L, 1e-30),
                        np.nan)


def base_params(nu=NU, nv=NV):
    """Slice 1's parameter spacing: closer toward the ends and near the keel's bottom."""
    s = np.linspace(0, 1, nu)
    t = np.linspace(0, 1, nv)
    return s - 0.35 * np.sin(2 * math.pi * s) / (2 * math.pi), 0.35 * 0.5 * (1 - np.cos(math.pi * t)) + 0.65 * t


# ------------------------------------------------------------------------------------------- the rudder's shape
(HX, HZ), (PX, PZ) = loft.KEEL["post"]          # the heel and the post's top: the rudder's trailing edge
SLOPE = loft.POST_SLOPE                          # dz/dx of the post and the stock line (both rake aft going up)
SX = HX + loft.KEEL["rudder_chord"]             # the stock line passes through (SX, HZ)
A = np.array([SX + (RUD["top_edge"]["stock_z"] - HZ) / SLOPE, RUD["top_edge"]["stock_z"]])   # head meets stock
B = np.array([HX + (RUD["top_edge"]["post_z"] - HZ) / SLOPE, RUD["top_edge"]["post_z"]])     # head meets the post
UP_STOCK = np.array([-1.0, -SLOPE]) / math.hypot(1.0, SLOPE)          # along the stock line, upward (and aft)
N_STOCK = np.array([-SLOPE, 1.0]) / math.hypot(1.0, SLOPE)            # out of the rudder across the stock line
# The rudder's own frame (stock_frame): h up the stock from its head's foot A, x_l square to the stock toward the
# trailing edge, y the hull's own; r = hypot(x_l, y) is the distance from the stock's axis. The head and the deadwood's
# underside are surfaces of revolution about the axis (a flat shoulder square to the stock, then a cone up to the post),
# so turning the rudder moves its head along them and never into the deadwood.
R0 = RUD["shoulder_radius"]                      # the shoulder's radius
XB_L = float((B - A) @ -N_STOCK)                 # the head's after end B in the frame
HB = float((B - A) @ UP_STOCK)
CONE_K = (XB_L - R0) / HB                        # the cone's radius grows CONE_K per metre up the stock
CONE_COS = 1.0 / math.hypot(1.0, CONE_K)         # (c - r) * CONE_COS is the distance to the cone
H_TOP = HB + 0.6                                 # nothing higher up the stock is rudder or slot (keeps the cone off the counter)
W_SIDE = RUD["lateral_limit"]                    # nor anything further than this off the centreline


def stock_frame(P):
    """Hull-frame points (n, 3) -> (x_l, y, h, r) in the rudder's frame."""
    d = np.asarray(P, float) - np.array([A[0], 0.0, A[1]])
    xl = d[:, 0] * -N_STOCK[0] + d[:, 2] * -N_STOCK[1]
    h = d[:, 0] * UP_STOCK[0] + d[:, 2] * UP_STOCK[1]
    y = d[:, 1]
    return xl, y, h, np.hypot(xl, y)


def from_stock_frame(xl, y, h):
    """(x_l, y, h) -> hull-frame points (n, 3)."""
    xl, y, h = (np.asarray(a, float) for a in (xl, y, h))
    x = A[0] - xl * N_STOCK[0] + h * UP_STOCK[0]
    z = A[1] - xl * N_STOCK[1] + h * UP_STOCK[1]
    return np.stack([x, y, z], -1)


def cone(h, inset=0.0):
    """The head's cone radius at height h up the stock (less 'inset': the deadwood's, inset by the head gap)."""
    return R0 + CONE_K * np.asarray(h, float) - inset


def sd_rudder(P):
    """< 0 inside the rudder: aft of the stock's axis, and below the shoulder or outside the cone (near the
    centreline, below H_TOP). Each term is a distance (the cone's nearly), so the cut's tolerances are in metres."""
    xl, y, h, r = stock_frame(P)
    head = np.minimum(h, (cone(h) - r) * CONE_COS)
    return np.maximum.reduce([-xl, np.abs(y) - W_SIDE, h - H_TOP, head])


def sd_keel_cut(P):
    """< 0 where the keel and the deadwood are cut away round the rudder: aft of the keel's after face ('slot' forward
    of the stock's axis) up to the shoulder's underside ('head_gap' over the rudder's shoulder), and outside the cone
    less 'head_gap' above that. The rudder is inside it with the gaps to spare."""
    xl, y, h, r = stock_frame(P)
    g = RUD["head_gap"]
    below = np.maximum(-(xl + RUD["slot"]), h - g)
    above = np.maximum.reduce([-xl, (cone(h, g) - r) * CONE_COS, np.abs(y) - W_SIDE, h - H_TOP])
    return np.minimum(below, above)


def z_stock(x):
    return HZ + SLOPE * (np.asarray(x, float) - SX)


# ----------------------------------------------------------------------------------------------- the fields
def _ends_rise(spec, x):
    xe = loft.END["lwl_ends"][1]
    return spec["mid"] + spec["rise_at_lwl_ends"] * (np.asarray(x, float) / xe) ** 2


LT = 1.016047                  # tonnes per long ton
RHO_LEAD = 11340.0             # kg/m^3


def lead_top_guess(S, tons):
    """A first guess at the lead casting's top from slice 1's sections: the depth whose keel volume below it, forward
    of the keel's after face, holds `tons` long tons (the groove round the rudder's nose is not in the sections; the
    build then measures the casting on its own mesh and moves the top until it holds the lead: lead_on_mesh)."""
    need = tons * LT * 1000.0 / RHO_LEAD
    off = RUD["slot"] * math.hypot(1.0, SLOPE)   # the after face is the stock line moved 'slot' square to it
    floor = lambda x: z_stock(x) + off            # noqa: E731
    lo, hi = float(S[..., 2].min()), 0.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if loft.volume_below(S, mid, 200, floor)[0] > need:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _clip_below(P, c):
    """The part of triangle P (3, 3) below z = c, as triangles (a fan of the clipped polygon)."""
    poly = []
    for i in range(3):
        a, b = P[i], P[(i + 1) % 3]
        if a[2] < c:
            poly.append(a)
        if (a[2] < c) != (b[2] < c):
            t = (c - a[2]) / (b[2] - a[2])
            poly.append(a + t * (b - a))
    return [(poly[0], poly[k], poly[k + 1]) for k in range(1, len(poly) - 1)]


def _tris(V, faces):
    """Fan-triangulated faces as an (n, 3, 3) array of corners."""
    V = np.asarray(V, float)
    idx = [(f[0], f[k], f[k + 1]) for f in faces for k in range(1, len(f) - 1)]
    return V[np.array(idx, int).reshape(-1, 3)]


def _moments(T, c):
    """Volume and first moments (x, z) under triangles T (n, 3, 3) wholly below z = c (see volume_below_mesh)."""
    az = 0.5 * ((T[:, 1, 0] - T[:, 0, 0]) * (T[:, 2, 1] - T[:, 0, 1]) - (T[:, 1, 1] - T[:, 0, 1]) * (T[:, 2, 0] - T[:, 0, 0]))
    dz = T[:, :, 2] - c
    hz = 0.5 * (T[:, :, 2] + c)
    x = T[:, :, 0]

    def prod(f, g):
        return (az / 12.0 * ((f * g).sum(1) + f.sum(1) * g.sum(1))).sum()

    return float((az * dz.mean(1)).sum()), float(prod(x, dz)), float(prod(dz, hz))


def volume_below_mesh(T, c):
    """Volume and centroid (x, z) of a closed mesh's solid below z = c (T: its triangles), by the divergence theorem
    with fields that vanish on the plane, so the plane's cap adds nothing and only the faces below it count. On each
    flat triangle the integral of a product of two linear functions is (A_z / 12) (sum f_i g_i + sum f_i sum g_i)."""
    zmin, zmax = T[:, :, 2].min(1), T[:, :, 2].max(1)
    v, mx, mz = _moments(T[zmax <= c], c)
    cut = []
    for P in T[(zmin < c) & (zmax > c)]:
        cut += _clip_below(P, c)
    if cut:
        dv, dx, dzm = _moments(np.array(cut, float), c)
        v, mx, mz = v + dv, mx + dx, mz + dzm
    return v, (mx / v if v > 0 else 0.0), (mz / v if v > 0 else 0.0)


def lead_on_mesh(T, tons):
    """The lead casting on the finished shell's own mesh (groove and all; T its triangles): the top whose solid below it
    holds `tons` long tons of lead. Below the casting's top the shell is all lead (the rudder is its own piece and the
    slot is open water), so the solid below the plane is the casting."""
    need = tons * LT * 1000.0 / RHO_LEAD
    T = T[T[:, :, 2].min(1) < -1.5]
    lo, hi = float(T[:, :, 2].min()), -1.5
    for _ in range(36):
        mid = 0.5 * (lo + hi)
        if volume_below_mesh(T, mid)[0] > need:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi), need


def _signed_volume(V, faces):
    """Signed volume under a set of outward faces (fans from each face's first corner): a closed set gives its volume,
    two open sets with the same edge give the volume between them by difference."""
    V = np.asarray(V)
    tot = 0.0
    for f in faces:
        a = V[f[0]]
        for i in range(1, len(f) - 1):
            tot += float(np.dot(a, np.cross(V[f[i]], V[f[i + 1]]))) / 6.0
    return tot


def _wet_area(V, faces):
    """Area of the faces whose centre is below the load waterline."""
    V = np.asarray(V)
    tot = 0.0
    for f in faces:
        a = V[f[0]]
        for i in range(1, len(f) - 1):
            b, c = V[f[i]], V[f[i + 1]]
            if (a[2] + b[2] + c[2]) < 0.0:
                tot += 0.5 * float(np.linalg.norm(np.cross(b - a, c - a)))
    return tot


def make_fields(z_lead):
    c_hi, c_lo = sorted(PAINT["cove_below_sheer"])
    sheer = lambda P: loft.SHEER(np.clip(P[:, 0], loft.END["transom_top"][0], loft.END["stem_head"][0]))  # noqa
    return {
        "rudder": sd_rudder,
        "keel_cut": sd_keel_cut,
        "lead": lambda P: P[:, 2] - z_lead,
        "boot_bottom": lambda P: P[:, 2] - _ends_rise(PAINT["boot_top_bottom"], P[:, 0]),
        "boot_top": lambda P: P[:, 2] - _ends_rise(PAINT["boot_top_top"], P[:, 0]),
        "cove_low": lambda P: P[:, 2] - (sheer(P) - c_lo),
        "cove_high": lambda P: P[:, 2] - (sheer(P) - c_hi),
    }


def label_of(f):
    """A face's label from its fields' signs (dict of arrays, one value per face)."""
    lab = np.full(len(f["rudder"]), "Topsides", dtype=object)
    lab[f["cove_high"] < 0] = "CoveStripe"
    lab[f["cove_low"] < 0] = "Topsides"
    lab[f["boot_top"] < 0] = "Bootstripe"
    lab[f["boot_bottom"] < 0] = "Antifouling"
    lab[f["lead"] < 0] = "Keel"
    lab[f["keel_cut"] < 0] = "Slot"
    lab[f["rudder"] < 0] = "Rudder"
    return lab


# --------------------------------------------------------------------------------------- cutting the triangles
class TriMesh:
    """Starboard half: vertices with their (u, v), triangles."""

    def __init__(self, surf, nu=NU, nv=NV):
        self.surf = surf
        us, vs = base_params(nu, nv)
        U, V = np.meshgrid(us, vs, indexing="ij")
        self.uv = np.stack([U.ravel(), V.ravel()], 1)
        self.P = surf.grid(us, vs).reshape(-1, 3)
        self.n_grid = len(self.P)
        idx = np.arange(nu * nv).reshape(nu, nv)
        tris = []
        for i in range(nu - 1):
            for j in range(nv - 1):
                a, b, c, d = idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]
                # outward (+y) is a -> d -> c -> b; split along the shorter diagonal
                if np.linalg.norm(self.P[a] - self.P[c]) <= np.linalg.norm(self.P[b] - self.P[d]):
                    tris += [(a, d, c), (a, c, b)]
                else:
                    tris += [(a, d, b), (d, c, b)]
        self.T = np.array(tris)

    def cut(self, field, iters=48):
        """Split every triangle the field's zero crosses; new vertices on the surface, exactly on the zero."""
        f = field(self.P)
        pos = f >= 0
        T = self.T
        sp = pos[T]
        mixed = np.where(sp.any(1) & ~sp.all(1))[0]
        edges = {}
        for t in mixed:
            for k in range(3):
                a, b = T[t, k], T[t, (k + 1) % 3]
                if pos[a] != pos[b]:
                    edges.setdefault((min(a, b), max(a, b)), None)
        keys = list(edges)
        if not keys:
            return 0
        ka = np.array([k[0] for k in keys])
        kb = np.array([k[1] for k in keys])
        ua, ub = self.uv[ka], self.uv[kb]
        lo, hi = np.zeros(len(keys)), np.ones(len(keys))
        sa = pos[ka]
        for _ in range(iters):
            m = 0.5 * (lo + hi)
            uvm = ua + m[:, None] * (ub - ua)
            fm = field(self.surf.at(uvm[:, 0], uvm[:, 1]))
            same = (fm >= 0) == sa
            lo = np.where(same, m, lo)
            hi = np.where(same, hi, m)
        tm = 0.5 * (lo + hi)
        uvn = ua + tm[:, None] * (ub - ua)
        Pn = self.surf.at(uvn[:, 0], uvn[:, 1])
        n0 = len(self.P)
        new_uv, new_P = [], []
        for k, key in enumerate(keys):
            if tm[k] < 2e-4:                     # snap to the end: no sliver triangles
                edges[key] = key[0]
            elif tm[k] > 1 - 2e-4:
                edges[key] = key[1]
            else:
                edges[key] = n0 + len(new_P)
                new_uv.append(uvn[k])
                new_P.append(Pn[k])
        if new_P:
            self.uv = np.concatenate([self.uv, np.array(new_uv)])
            self.P = np.concatenate([self.P, np.array(new_P)])
        keep = np.ones(len(T), bool)
        keep[mixed] = False
        out = [T[keep]]
        add = []
        for t in mixed:
            a, b, c = T[t]
            s = pos[[a, b, c]]
            # rotate so the lone vertex (the one whose sign differs) comes first
            if s[0] != s[1] and s[0] != s[2]:
                lone, x1, x2 = a, b, c
            elif s[1] != s[0] and s[1] != s[2]:
                lone, x1, x2 = b, c, a
            else:
                lone, x1, x2 = c, a, b
            p = edges[(min(lone, x1), max(lone, x1))]
            q = edges[(min(lone, x2), max(lone, x2))]
            for tri in ((lone, p, q), (p, x1, x2), (p, x2, q)):
                if len(set(tri)) == 3:
                    add.append(tri)
        out.append(np.array(add, int).reshape(-1, 3))
        self.T = np.concatenate(out)
        return len(keys)


    def weld(self, tol=5e-4):
        """Collapse edges shorter than tol that a cut made (where two cuts' lines pass within a fraction of a millimetre
        of each other, or of a grid vertex), and drop the triangles that go with them. An edge is collapsed only if
        both ends are on the same edge of the surface (the centreline, the transom's edge, the sheer, or neither) and
        the collapse keeps the mesh a manifold (the two ends share no neighbours but the edge's own triangles'). The
        older (lower) index stays, so a cut's vertex goes to the grid's; the grid's own short edges (where the rows
        close in on the stem head) are left alone."""
        T = [list(t) for t in self.T]
        uv = self.uv
        cls = np.where(np.abs(self.P[:, 1]) < 1e-9, 1, 0) + np.where(uv[:, 0] < 1e-12, 2, 0) \
            + np.where(uv[:, 1] > 1 - 1e-12, 4, 0)
        vt = {}
        for k, t in enumerate(T):
            for v in t:
                vt.setdefault(v, set()).add(k)
        cand = set()
        for t in T:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                if max(a, b) >= self.n_grid and np.linalg.norm(self.P[a] - self.P[b]) < tol:
                    cand.add((min(a, b), max(a, b)))
        dead = set()
        done = 0
        for a, b in sorted(cand, key=lambda e: np.linalg.norm(self.P[e[0]] - self.P[e[1]])):
            if a not in vt or b not in vt or cls[a] != cls[b]:
                continue
            shared = [k for k in vt[a] & vt[b] if k not in dead]
            opp = {v for k in shared for v in T[k] if v not in (a, b)}
            na = {v for k in vt[a] if k not in dead for v in T[k]} - {a}
            nb = {v for k in vt[b] if k not in dead for v in T[k]} - {b}
            if (na & nb) != opp or not shared:
                continue
            for k in shared:
                dead.add(k)
            for k in vt[b]:
                if k in dead:
                    continue
                T[k] = [a if v == b else v for v in T[k]]
                vt[a].add(k)
            del vt[b]
            done += 1
        self.T = np.array([t for k, t in enumerate(T) if k not in dead])
        return done


# ------------------------------------------------------------------------------------------- girth (plating UV)
class Girth:
    """Girth below the sheer at any (u, v), along the section: the plating UV's V."""

    def __init__(self, surf):
        us = np.linspace(0, 1, ARC_NU)
        vs = np.linspace(0, 1, ARC_NV)
        G = surf.grid(us, vs)
        seg = np.linalg.norm(np.diff(G, axis=1), axis=2)
        arc = np.concatenate([np.zeros((ARC_NU, 1)), np.cumsum(seg, axis=1)], axis=1)
        self.below = RegularGridInterpolator((us, vs), arc[:, -1:] - arc)

    def __call__(self, uv):
        return self.below(np.clip(uv, 0.0, 1.0))


# --------------------------------------------------------------------------------------------- building pieces
class Piece:
    """A mesh piece: vertices, faces (index tuples), each face's slot, each face corner's plating UV, and its kind:
    'surface' (on the hull's surface, shaded with the surface's own normals) or 'strip:<part>' (a closing strip; each
    part of one, such as the rudder's nose or its shoulder, is shaded on its own, so the corners between them stay
    crisp)."""

    def __init__(self, name):
        self.name = name
        self.V = []
        self.F, self.slot, self.uv, self.kind = [], [], [], []
        self.vn = {}                 # vertex -> the surface's normal there (surface vertices)

    def vert(self, p):
        self.V.append(tuple(float(c) for c in p))
        return len(self.V) - 1

    def face(self, idx, slot, uvs=None, kind="surface"):
        idx = list(idx)
        # drop repeated corners (collapsed strips), keep it only if it still has an area
        clean = [k for i, k in enumerate(idx) if k != idx[i - 1]]
        if len(clean) < 3 or len(set(clean)) < 3:
            return
        self.F.append(tuple(clean))
        self.slot.append(slot)
        self.uv.append(uvs if uvs is not None else [(self.V[k][0], NO_PLATING) for k in clean])
        self.kind.append(kind)

    def corner_normals(self):
        """Each face corner's normal: the surface's own on surface faces (so the shading is the smooth hull's, whatever
        the cuts did to the triangles), the strip's averaged normal on the closing strips (a crisp edge between them)."""
        V = np.asarray(self.V)
        acc = {}
        fn = []
        for f, kd in zip(self.F, self.kind):
            P = V[list(f)]
            n = np.zeros(3)
            for i in range(len(f)):                      # Newell: area-weighted, any polygon
                a, b = P[i], P[(i + 1) % len(f)]
                n += np.cross(a, b)
            n *= 0.5
            fn.append(n)
            for v in f:
                acc.setdefault(kd, {})[v] = acc.setdefault(kd, {}).get(v, 0) + n
        out = []
        for f, kd in zip(self.F, self.kind):
            row = []
            for v in f:
                n = self.vn.get(v) if kd == "surface" else None
                if n is None or not np.all(np.isfinite(n)):
                    n = acc[kd][v]
                n = np.asarray(n, float)
                row.append(tuple(n / max(np.linalg.norm(n), 1e-30)))
            out.append(row)
        return out


def _mirror_pieces(mesh, girth, labels, want):
    """Starboard triangles with a label in `want`, plus their port mirror, as one piece's vertices and faces."""
    sel = np.where(np.isin(labels, list(want)))[0]
    T = mesh.T[sel]
    used = np.unique(T)
    on_cl = np.abs(mesh.P[used, 1]) < 1e-9
    stb = {int(v): i for i, v in enumerate(used)}
    V = [mesh.P[v] for v in used]
    port = {}
    for v, cl in zip(used, on_cl):
        if cl:
            port[int(v)] = stb[int(v)]
        else:
            port[int(v)] = len(V)
            V.append(mesh.P[v] * np.array([1, -1, 1]))
    d = girth(mesh.uv[used])
    gd = {int(v): float(g) for v, g in zip(used, d)}
    return T, sel, stb, port, V, gd


def _chain(edges):
    """Order a set of edges (pairs) that form one open chain; returns the vertex list."""
    nb = {}
    for a, b in edges:
        nb.setdefault(a, []).append(b)
        nb.setdefault(b, []).append(a)
    ends = [v for v, n in nb.items() if len(n) == 1]
    if len(ends) != 2 or any(len(n) > 2 for n in nb.values()):
        raise ValueError(f"the cut's edge is not one open chain ({len(ends)} ends)")
    out = [min(ends, key=lambda v: v)]
    prev = None
    while True:
        nxt = [w for w in nb[out[-1]] if w != prev]
        if not nxt:
            break
        prev = out[-1]
        out.append(nxt[0])
    if len(out) != len(nb):
        raise ValueError("the cut's edge has more than one piece")
    return out


def boundary_edges(T):
    """Edges used by exactly one triangle, as directed (a, b) in the triangle's own winding."""
    count = {}
    for t in T:
        for k in range(3):
            a, b = int(t[k]), int(t[(k + 1) % 3])
            key = (min(a, b), max(a, b))
            count[key] = count.get(key, 0) + 1
    return [k for k, c in count.items() if c == 1]


def cut_chain(mesh, T, field, tol=2e-3):
    """The vertices along a field's zero (within tol: a later cut puts its vertices on the surface, a fraction of a
    millimetre off an earlier cut's line) on the open edge of a set of starboard triangles, ordered up the stock, from
    the centreline at the keel's bottom to the centreline at the post."""
    f = field(mesh.P)
    edges = [e for e in boundary_edges(T) if abs(f[e[0]]) < tol and abs(f[e[1]]) < tol
             and not (abs(mesh.P[e[0], 1]) < 1e-9 and abs(mesh.P[e[1], 1]) < 1e-9)]
    ch = _chain(edges)
    h = stock_frame(mesh.P[[ch[0], ch[-1]]])[2]
    return ch if h[0] <= h[1] else ch[::-1]


def rudder_zone(P):
    """Which part of the rudder's cut each point on it lies on: 'stock' (the axis' plane, below the shoulder),
    'shoulder' (square to the stock at the head's foot) or 'cone'."""
    _, _, h, r = stock_frame(P)
    return np.where(h < -1e-4, "stock", np.where(r < R0 - 1e-4, "shoulder", "cone"))


def keel_zone(P):
    """The same for the keel's cut: 'face' (its after face, 'slot' forward of the axis, up to the head gap over the
    rudder's shoulder), 'shoulder' (the deadwood's underside over the rudder's shoulder) or 'cone'."""
    g = RUD["head_gap"]
    xl, _, h, r = stock_frame(P)
    face = (h < g - 1e-4) | (xl < -RUD["slot"] + 1e-4)          # the after face's top corner is on the face
    return np.where(face, "face", np.where(r < cone(h, g) - 1e-4, "shoulder", "cone"))


KEPT = {"Keel", "Antifouling", "Bootstripe", "Topsides", "CoveStripe"}     # the shell's labels


def _keel_corner(mesh, labels):
    """Put a vertex at the keel cut's inside corner, where the after face meets the deadwood's underside over the
    shoulder. A cut leaves a corner inside a triangle, so the cut's edge would run straight across it there and the
    keel would reach a little way into the gap the rudder's shoulder turns in; the corner's own vertex (on the surface)
    and a triangle filling the notch to it put the edge round the corner. Returns the new triangle's index."""
    kept = np.isin(labels, list(KEPT))
    ch = cut_chain(mesh, mesh.T[kept], sd_keel_cut)
    z = keel_zone(mesh.P[ch])
    hits = [k for k in range(len(ch) - 1) if z[k] == "face" and z[k + 1] == "shoulder"]
    if len(hits) != 1:
        raise ValueError(f"the keel's cut should turn from its after face to the shoulder once, not {len(hits)} times")
    p1, p2 = ch[hits[0]], ch[hits[0] + 1]
    g, slot = RUD["head_gap"], RUD["slot"]

    def fn(uv):
        xl, _, h, _ = stock_frame(mesh.surf.at(np.array([uv[0]]), np.array([uv[1]])))
        return np.array([xl[0] + slot, h[0] - g])

    uv = 0.5 * (mesh.uv[p1] + mesh.uv[p2])
    for _ in range(40):
        F = fn(uv)
        J = np.stack([(fn(uv + d) - F) / 1e-7 for d in (np.array([1e-7, 0.0]), np.array([0.0, 1e-7]))], 1)
        step = np.linalg.solve(J, -F)
        uv = uv + step
        if np.abs(step).max() < 1e-13:
            break
    c = mesh.surf.at(np.array([uv[0]]), np.array([uv[1]]))[0]
    if np.abs(fn(uv)).max() > 1e-6 or np.linalg.norm(c - 0.5 * (mesh.P[p1] + mesh.P[p2])) > 0.1:
        raise ValueError("the keel cut's corner is not where its edge turns")
    # the shell's triangle on the edge p1-p2: the corner's triangle runs the edge the other way
    for k in np.where(kept)[0]:
        t = list(mesh.T[k])
        if p1 in t and p2 in t:
            i = t.index(p1)
            a, b = (p1, p2) if t[(i + 1) % 3] == p2 else (p2, p1)
            break
    else:
        raise ValueError("no shell triangle on the keel cut's corner edge")
    mesh.P = np.concatenate([mesh.P, c[None]])
    mesh.uv = np.concatenate([mesh.uv, uv[None]])
    mesh.T = np.concatenate([mesh.T, [[b, a, len(mesh.P) - 1]]])
    return len(mesh.T) - 1, labels[k]


def rudder_curve(p, zone, n=NOSE_J):
    """The rudder's closing curve at a point p (starboard) of its cut, n + 1 points to its port twin, square to the
    stock: a half circle round the axis as wide as the rudder there (the nose), straight across (the shoulder) or an
    arc round the axis (the cone)."""
    xl, y, h, r = (float(a[0]) for a in stock_frame(np.asarray(p)[None]))
    j = np.arange(n + 1) / n
    if zone == "stock":
        q = (-y * np.sin(j * math.pi), y * np.cos(j * math.pi))
    elif zone == "shoulder":
        q = (np.full(n + 1, xl), y * (1 - 2 * j))
    else:
        ph = math.atan2(y, xl) * (1 - 2 * j)
        q = (r * np.cos(ph), r * np.sin(ph))
    return from_stock_frame(q[0], q[1], np.full(n + 1, h))


def keel_half_curve(p, zone, nose, n=NOSE_J):
    """The starboard half of the keel's closing curve at a point p of its cut, n + 1 points from p to the centreplane:
    on the after face, in from the side and round the groove (a circle about the axis 'gap' wider than the rudder's
    nose there; nose(h) is the nose's radius), else straight across (the shoulder) or round the cone."""
    xl, y, h, r = (float(a[0]) for a in stock_frame(np.asarray(p)[None]))
    s = np.arange(n + 1) / n
    if zone == "face":
        rho = float(nose(h)) + RUD["gap"]
        d0 = -xl
        if d0 < rho:
            ps = np.linspace(math.asin(min(d0 / rho, 1.0)), math.pi / 2, 24)
            arc = np.stack([rho * np.sin(ps), np.minimum(rho * np.cos(ps), y)], 1)
            poly = np.concatenate([[[d0, y]], arc])
        else:
            poly = np.array([[d0, y], [d0, 0.0]])
        pts = _resample(poly, n + 1)
        q = (-pts[:, 0], pts[:, 1])
    elif zone == "shoulder":
        q = (np.full(n + 1, xl), y * (1 - s))
    else:
        ph = math.atan2(y, xl) * (1 - s)
        q = (r * np.cos(ph), r * np.sin(ph))
    out = from_stock_frame(q[0], q[1], np.full(n + 1, h))
    out[-1, 1] = 0.0
    return out


def _strip_kind(z0, z1):
    """A strip between two closing curves is shaded with its part: between two parts it is flat, on the shoulder."""
    return "strip:" + (z0 if z0 == z1 else "shoulder")


def build(nu=NU, nv=NV, extra_lead_tons=0.0):
    """The finished shell's pieces and a report: {'Shell', 'Rudder', 'Stock'} pieces and the checks.

    The lead casting's top is solved on the finished shell itself: a first guess from slice 1's sections, then the
    shell is built, the casting (everything below its top: the keel forward of the slot, less the groove) measured on
    it, and the top moved until the casting holds the size card's lead plus what the plating and the slot change in her
    displacement (measured on the same build), plus `extra_lead_tons`: what the later slices' parts weigh less than the
    size card's estimate for them (slice 3's deck), so she still floats on her lines. Two builds usually settle it to
    a fraction of a millimetre.

    From slice 4 finish_bluebonnet.json fixes the casting's top (lead.casting_top_z, where slice 3's solve put it) and
    _build_cast builds at it: the same weight goes on, the casting's share fixed and the rest as trimming ballast, so a
    later slice's weights move the ballast in the bilge, not the casting's top line (moving it had brought the top to a
    height where the keel's slot cut fails). The solve above still runs when casting_top_z is taken out."""
    surf = Surface()
    lead_card = loft.SPECS["weights"]["lead_keel"]
    cast = FIN["lead"].get("casting_top_z")
    if cast is not None:
        return _build_cast(surf, cast, nu, nv, lead_card, extra_lead_tons)
    S = loft.surface(420, 104)                                  # slice 1's grid
    z = lead_top_guess(S, lead_card + 1.2 + extra_lead_tons)
    passes = []
    for _ in range(4):
        pieces, report, T_shell = _build_at(surf, z, nu, nv)
        tons = lead_card + report["displacement"]["_added_long_tons"] + extra_lead_tons
        z_new, need = lead_on_mesh(T_shell, tons)
        passes.append({"top_z_m": round(z, 5), "solved_top_z_m": round(z_new, 5)})
        if abs(z_new - z) < 3e-4:
            break
        z = z_new
    else:
        raise ValueError(f"the lead's top does not settle: {passes}")
    v, cx, cz = volume_below_mesh(T_shell, z)
    placed = v * RHO_LEAD / 1000.0 / LT
    if abs(placed - tons) > 0.05:
        raise ValueError(f"the lead casting holds {placed:.2f} long tons, not {tons:.2f}")
    report["lead"] = {"long_tons": round(tons, 2), "top_z_m": round(z, 4), "lead_m3": round(need, 4),
                      "lead_m3_placed": round(v, 4), "long_tons_placed": round(placed, 3),
                      "centroid_x_m": round(cx, 3), "centroid_z_m": round(cz, 3),
                      "measured_on": "the finished shell's mesh, below the casting's top", "builds": passes,
                      "card_long_tons": lead_card, "for_the_finish_long_tons": round(tons - lead_card - extra_lead_tons, 3),
                      "for_the_deck_long_tons": round(extra_lead_tons, 3)}
    report["displacement"]["lead_long_tons"] = round(tons, 2)
    del report["displacement"]["_added_long_tons"]
    return pieces, report


def _build_cast(surf, z, nu, nv, lead_card, extra_lead_tons):
    """The shell with the casting's top fixed at z (finish_bluebonnet.json's lead.casting_top_z): what the lead must
    weigh to float her on her lines, less what the casting holds, goes into the bilge as trimming ballast (lead pigs
    on the floors, lead.trim_ballast), so later slices change the trimming ballast, not the casting."""
    pieces, report, T_shell = _build_at(surf, z, nu, nv)
    tons = lead_card + report["displacement"]["_added_long_tons"] + extra_lead_tons
    v, cx, cz = volume_below_mesh(T_shell, z)
    placed = v * RHO_LEAD / 1000.0 / LT
    trim = tons - placed
    tb = FIN["lead"]["trim_ballast"]
    if trim < -0.005:
        raise ValueError(f"the casting holds {placed:.3f} long tons, {-trim:.3f} more than she needs to float on her "
                         "lines: the parts built so far weigh more than the size card's estimate for them, so she "
                         "would float deeper unless the casting is made smaller (lower lead.casting_top_z)")
    W = placed + max(trim, 0.0)
    report["lead"] = {"long_tons": round(W, 2), "top_z_m": round(z, 4), "casting_fixed": True,
                      "casting_long_tons": round(placed, 3), "lead_m3_placed": round(v, 4),
                      "casting_centroid_x_m": round(cx, 3), "casting_centroid_z_m": round(cz, 3),
                      "trim_ballast_long_tons": round(max(trim, 0.0), 3), "trim_ballast_centre": tb["centre"],
                      "centroid_x_m": round((placed * cx + max(trim, 0.0) * tb["centre"][0]) / W, 3),
                      "centroid_z_m": round((placed * cz + max(trim, 0.0) * tb["centre"][1]) / W, 3),
                      "measured_on": "the finished shell's mesh, below the casting's top",
                      "builds": [{"top_z_m": round(z, 5), "fixed": True}], "card_long_tons": lead_card,
                      "for_the_finish_long_tons": round(tons - lead_card - extra_lead_tons, 3),
                      "for_the_later_slices_long_tons": round(extra_lead_tons, 3)}
    report["displacement"]["lead_long_tons"] = round(W, 2)
    del report["displacement"]["_added_long_tons"]
    return pieces, report


def _build_at(surf, z_lead, nu, nv):
    """The shell with the lead's top at z_lead: pieces, report, and the shell's triangles (for the lead)."""
    fields = make_fields(z_lead)
    mesh = TriMesh(surf, nu, nv)
    n_cut = {k: mesh.cut(fn) for k, fn in fields.items()}
    n_cut["welded_slivers"] = mesh.weld()
    # each triangle's label from its corners' field values (the corners on a cut sit on that field's zero)
    fv = {k: fn(mesh.P) for k, fn in fields.items()}
    cen = mesh.P[mesh.T].mean(1)
    fc = {k: fn(cen) for k, fn in fields.items()}
    face_f = {}
    for k in fields:
        s = fv[k][mesh.T].sum(1)
        face_f[k] = np.where(np.abs(s) > 1e-9, s, fc[k])
    labels = label_of(face_f)
    corner, corner_label = _keel_corner(mesh, labels)
    labels = np.append(labels, corner_label)
    girth = Girth(surf)
    # the surface's normals at every vertex, turned outward like the triangles (starboard)
    an = surf.normals(mesh.uv[:, 0], mesh.uv[:, 1])
    tri = mesh.P[mesh.T]
    tn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    gn = np.zeros_like(mesh.P)
    for k in range(3):
        np.add.at(gn, mesh.T[:, k], tn)
    sgn = np.sign(np.einsum("ij,ij->i", np.nan_to_num(an), gn))
    an = an * np.where(sgn == 0, 1.0, sgn)[:, None]

    # ---- the shell (everything but the rudder and the slot)
    hull = Piece("Shell")
    T, sel, stb, port, V, gd = _mirror_pieces(mesh, girth, labels, KEPT)
    hull.V = [tuple(map(float, p)) for p in V]
    for v in stb:
        hull.vn[stb[v]] = an[v]
        hull.vn[port[v]] = an[v] * np.array([1, -1, 1])
    corner_faces = []
    for t, k in zip(T, sel):
        lab = labels[k]
        plated = lab != "Keel"
        for side in (0, 1):
            ids = [stb[int(v)] for v in t] if side == 0 else [port[int(v)] for v in t][::-1]
            src = list(t) if side == 0 else list(t)[::-1]
            uvs = [(mesh.P[v, 0], gd[int(v)] if plated else NO_PLATING) for v in src]
            hull.face(ids, lab, uvs)
            if k == corner:
                corner_faces.append(hull.F[-1])
    hull_T = T
    # ---- the rudder
    rud = Piece("Rudder")
    Tr, selr, stbr, portr, Vr, _ = _mirror_pieces(mesh, girth, labels, {"Rudder"})
    rud.V = [tuple(map(float, p)) for p in Vr]
    for v in stbr:
        rud.vn[stbr[v]] = an[v]
        rud.vn[portr[v]] = an[v] * np.array([1, -1, 1])
    for t in Tr:
        rud.face([stbr[int(v)] for v in t], "Antifouling")
        rud.face([portr[int(v)] for v in t][::-1], "Antifouling")

    # ---- the rudder's closing: one curve across the cut per vertex of the cut's edge, square to the stock
    rch = cut_chain(mesh, Tr, fields["rudder"])
    rP = mesh.P[rch]
    rz = rudder_zone(rP)
    rows = []
    for k, v in enumerate(rch):
        if rP[k, 1] < 1e-7:
            rows.append([stbr[v]] * (NOSE_J + 1))
            continue
        pts = rudder_curve(rP[k], rz[k])
        rows.append([stbr[v]] + [rud.vert(p) for p in pts[1:-1]] + [portr[v]])
    faces, kinds = [], []
    for k in range(len(rows) - 1):
        for j in range(NOSE_J):
            faces.append([rows[k][j], rows[k + 1][j], rows[k + 1][j + 1], rows[k][j + 1]])
            kinds.append(_strip_kind(rz[k], rz[k + 1]))
    _add_oriented(rud, faces, "Antifouling", kinds)
    # the nose's radius up the stock (the rudder's half-thickness on the axis' plane), for the keel's groove
    st = rz == "stock"
    h_st = stock_frame(rP[st])[2]
    t_st = rP[st, 1]

    def nose(h):
        return np.interp(h, h_st, t_st)

    # ---- the keel's after face and groove, and the deadwood's underside over the rudder's head
    kch = cut_chain(mesh, hull_T, fields["keel_cut"])
    kP = mesh.P[kch]
    kz = keel_zone(kP)
    curves = []
    for k, v in enumerate(kch):
        if kP[k, 1] < 1e-7:
            curves.append([stb[v]] * (2 * NOSE_J + 1))
            continue
        pts = keel_half_curve(kP[k], kz[k], nose)
        half = [stb[v]] + [hull.vert(p) for p in pts[1:]]
        # the port half mirrors the starboard one; the curve's middle (on the centreplane) is shared
        port_half = [hull.vert((hull.V[i][0], -hull.V[i][1], hull.V[i][2])) for i in half[1:-1]]
        curves.append(half + port_half[::-1] + [port[v]])
    faces, kinds = [], []
    for k in range(len(curves) - 1):
        a, b = curves[k], curves[k + 1]
        for j in range(len(a) - 1):
            faces.append([a[j], b[j], b[j + 1], a[j + 1]])
            kinds.append(_strip_kind(kz[k], kz[k + 1]))
    n_before = len(hull.F)
    _add_oriented(hull, faces, lambda f: "Keel" if np.mean([hull.V[i][2] for i in f]) < z_lead else "Antifouling",
                  kinds)
    groove_added = hull.F[n_before:]

    # ---- her displacement as built (slice 1's known gap): the plating stands 'thickness' outside the moulded surface
    # below the waterline (not on the lead, cast to the moulded line, nor on the closing strips: the slot's faces are
    # the plates' edges); the slot and the groove take away the keel between the rudder and the keel's cut. The
    # region's moulded surface less the keel's closing (and the corner's triangle, which covers a little of the
    # region's surface) is the volume cut out.
    Ts, _, stb_s, port_s, Vs, _ = _mirror_pieces(mesh, girth, labels, {"Rudder", "Slot"})
    region = [[stb_s[int(v)] for v in t] for t in Ts] + [[port_s[int(v)] for v in t][::-1] for t in Ts]
    cut_out = _signed_volume(Vs, region) - _signed_volume(hull.V, groove_added) - _signed_volume(hull.V, corner_faces)
    rud_vol = _signed_volume(rud.V, rud.F)
    plated = [f for f, s_, kd in zip(hull.F, hull.slot, hull.kind) if s_ != "Keel" and kd == "surface"]
    plated_wet = _wet_area(hull.V, plated)
    thick = FIN["plating"]["thickness"]
    lt_per_m3 = loft.RHO_SEA / 1000.0 / LT
    added = (plated_wet * thick - (cut_out - rud_vol)) * lt_per_m3

    # ---- the stock: a bronze shaft on the stock line, from inside the rudder up through the counter to the deck
    stock = _stock_piece()
    pieces = {"Shell": hull, "Rudder": rud, "Stock": stock}
    # the shell's open edges that the transom and the deck close: its aft edge (u = 0) and the sheer (v = 1), starboard
    used = np.unique(hull_T)
    tr = used[mesh.uv[used, 0] < 1e-12]
    sh = used[mesh.uv[used, 1] > 1 - 1e-12]
    hull.transom_edge = mesh.P[tr[np.argsort(mesh.uv[tr, 1])]]
    hull.sheer = mesh.P[sh[np.argsort(mesh.uv[sh, 0])]]

    # ---- the report
    rud_area = _profile_area(mesh, Tr)
    rt = rP[st, 1]
    report = {
        "grid": [nu, nv], "cuts": n_cut,
        "rudder": {"stock_line": {"through": [round(SX, 3), HZ], "dz_dx": round(SLOPE, 4)},
                   "head_from": [round(float(A[0]), 3), round(float(A[1]), 3)],
                   "head_to": [round(float(B[0]), 3), round(float(B[1]), 3)],
                   "shoulder_radius_m": R0, "cone_radius_per_m_up_the_stock": round(CONE_K, 4),
                   "head_to_in_stock_frame": {"aft_m": round(XB_L, 3), "up_m": round(HB, 3)},
                   "area_m2": round(rud_area, 3), "area_ft2": round(rud_area / loft.FT ** 2, 1),
                   "nose_radius_m": [round(float(rt.min()), 3), round(float(np.percentile(rt, 50)), 3),
                                     round(float(rt.max()), 3)],
                   "gaps_m": {"groove": RUD["gap"], "head": RUD["head_gap"], "slot": RUD["slot"]}},
        "displacement": {"plating_thickness_m": thick, "plated_wetted_m2": round(plated_wet, 2),
                         "plating_m3": round(plated_wet * thick, 3), "slot_and_groove_m3": round(cut_out - rud_vol, 3),
                         "rudder_m3": round(rud_vol, 3), "added_long_tons": round(added, 2),
                         "_added_long_tons": added},
        "chains": {"rudder": len(rch), "keel": len(kch),
                   "rudder_zones": {z_: int((rz == z_).sum()) for z_ in ("stock", "shoulder", "cone")},
                   "keel_zones": {z_: int((kz == z_).sum()) for z_ in ("face", "shoulder", "cone")}},
        "labels": {k: int((labels == k).sum()) for k in sorted(set(labels))},
    }
    return pieces, report, _tris(hull.V, hull.F)


def _resample(poly, n):
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < 1e-12:
        return np.repeat(poly[:1], n, axis=0)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, poly[:, 0]), np.interp(t, s, poly[:, 1])], 1)


def _add_oriented(piece, faces, slot, kinds):
    """Add closing faces to a piece wound to match its existing faces: a shared edge must run the other way in each."""
    have = set()
    for f in piece.F:
        for k in range(len(f)):
            have.add((f[k], f[(k + 1) % len(f)]))
    flip = None
    for f in faces:
        c = [k for i, k in enumerate(f) if k != f[i - 1]]
        for k in range(len(c)):
            e = (c[k], c[(k + 1) % len(c)])
            if e in have:
                flip = True
            elif (e[1], e[0]) in have:
                flip = False
            if flip is not None:
                break
        if flip is not None:
            break
    if flip is None:
        raise ValueError(f"{piece.name}: the closing strip shares no edge with the piece")
    for f, kd in zip(faces, kinds):
        f = f[::-1] if flip else f
        piece.face(f, slot(f) if callable(slot) else slot, kind=kd)


def _profile_area(mesh, T):
    """Area of the starboard triangles projected on the centreplane (the rudder's profile area)."""
    P = mesh.P[T]
    a = P[:, 1] - P[:, 0]
    b = P[:, 2] - P[:, 0]
    return float(np.abs(0.5 * (a[:, 0] * b[:, 2] - a[:, 2] * b[:, 0])).sum())


def rudder_frame():
    """The rudder's (and stock's) pivot: origin on the stock's axis at the rudder's head (A), X square to the stock
    toward the trailing edge, Z up the stock (the hull's frame; the build adds Y = Z x X in Blender's)."""
    o = np.array([A[0], 0.0, A[1]])
    return o, np.array([-N_STOCK[0], 0.0, -N_STOCK[1]]), np.array([UP_STOCK[0], 0.0, UP_STOCK[1]])


def stock_axis():
    """The stock's axis: a point on it (the rudder's head on the stock line), its unit direction (up), and where it
    meets the deck's centreline (deck_z)."""
    p0 = np.array([A[0], 0.0, A[1]])
    up = np.array([UP_STOCK[0], 0.0, UP_STOCK[1]])
    lo, hi = 0.0, 20.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        p = p0 + m * up
        zd = float(deck_z(p[0], 0.0))
        if p[2] < zd:
            lo = m
        else:
            hi = m
    return p0, up, p0 + lo * up


def _stock_piece(sides=24):
    p0, up, deck = stock_axis()
    r = RUD["stock_radius"]
    bottom = np.array([SX, 0.0, HZ]) + up * (RUD["stock_from_bottom"] / up[2])
    top = deck - up * (0.03 + r * math.tan(math.acos(up[2])) + 0.02)   # the tilted top disc stays under the deck
    side = np.array([0.0, 1.0, 0.0])
    fwd = np.cross(side, up)
    pc = Piece("Stock")
    rings = []
    for c in (bottom, top):
        rings.append([pc.vert(c + r * (math.cos(2 * math.pi * k / sides) * fwd + math.sin(2 * math.pi * k / sides)
                                       * side)) for k in range(sides)])
    for k in range(sides):
        k1 = (k + 1) % sides
        pc.face([rings[0][k], rings[0][k1], rings[1][k1], rings[1][k]], "Bronze")
    pc.face(rings[0][::-1], "Bronze")
    pc.face(rings[1], "Bronze")
    return pc


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    pieces, report = build()
    report["pieces"] = {k: {"vertices": len(p.V), "faces": len(p.F)} for k, p in pieces.items()}
    with open(os.path.join(out, "shell.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
