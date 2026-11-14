"""Bluebonnet's sails (docs/jclass-6): the mainsail, the genoa, the quadrilateral jib, the staysail and the parachute
spinnaker, each in its states, on slice 4's spars and slice 5's stays.

    parts, rep = sails.build(rig, pts, rr, obstacles)

Sizes and cuts come from sails_bluebonnet.json (each with its source). Units as spars.py: metres in the hull's frame
(X forward, Y starboard, Z up). The sails:

  Mainsail       bent to the mast's track by slides on its luff rope and to the boom's by its foot, between the black
                 bands; a headboard, a roach held by four short battens in pockets, two reef bands with their points
                 and cringles. Cut with the cloths parallel to the leech.
  Genoa          a big overlapping headsail hanked to the forestay, mitre cut.
  Quadrilateral  the 1934 Js' double-clewed jib on the forestay: a jib with its clew cut off, four sides, two clews.
  Staysail       on the staysail stay, mitre cut.
  Spinnaker      a parachute spinnaker hoisted from the masthead, its tack at the pole's end: two halves joined down a
                 centre seam, the cloths square to it.

The states, one object each (Sail.State):

  Set            full of wind on starboard tack (the boom and the sails to port; the port tack is the mirror about the
                 centreline): the mainsail close-hauled with the headsails, and 'Run' squared off under the spinnaker.
                 Each is pressed off whatever it would otherwise touch (the genoa lies on the lee spreader tips and
                 shrouds, the squared mainsail on the lee shrouds): see press().
  Lowered        hauled down: the mainsail in loose folds on the boom (its slides stacked on the tracks), a headsail in
                 a heap on the foredeck still hanked to its stay.
  Flaked         the mainsail flaked on the boom and tied with sail ties.
  Bagged         a headsail or the spinnaker in its bag on deck.
  Stack          the mainsail's luff slides and headboard stacked at the foot of the mast's track (with Lowered or
                 Flaked).

The mainsail's Lowered and Flaked objects are in the boom's frame (they swing with it); everything else is in the
hull's frame. Each set state records the boom's and the pole's pose it was built for (the suits in the json).

The cloth is one sheet (two-sided), its grid's rows parallel to the foot (the spinnaker's square to its centre seam),
carrying the sail cloth material's UVs (FSailCloth, Source/SailingSim/Public/SailCloth.h; the frigate's sails.py): UV0
metres (x along the row from the luff, y up from the foot), UV1 the normalized planform, UV2.x metres along the row from
the leech (on the spinnaker from the clew's luff), so UV0.x + UV2.x is the row's length, as the game's M_SailCloth
reads it. UV2.y carries what the cut needs: on the mainsail and the mitre-cut headsails the distance in from the
leech's straight line (the main's cloths run parallel to it, so a seam is a line of constant UV2.y; a headsail's run
parallel to it above the mitre and to the foot below it, the mitre being where UV2.y = UV0.y), on the spinnaker the
distance from the centre seam. The cloth's face points to starboard on the
working sails (windward on starboard tack), aft on the spinnaker. Ropes, slides, hanks, battens' pockets, the
headboard, sail ties and bags are closed solids.
"""
import json
import math
import os
import sys
import zlib

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter
from scipy.spatial import ConvexHull, cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck  # noqa: E402
import loft  # noqa: E402
import rigging  # noqa: E402
import shell  # noqa: E402
import spars  # noqa: E402

SL = json.load(open(os.path.join(HERE, "sails_bluebonnet.json")))
FT = spars.FT
IN = 0.0254
EX, EY, EZ = np.eye(3)
unit = spars.unit
OZ_G = 28.349523125
DUR = spars.MAT["duralumin"]
BRZ = spars.MAT["bronze"]
ASH = 680.0                                         # the battens' wood, kg/m^3
SAILS = ("Mainsail", "Genoa", "Quadrilateral", "Staysail", "Spinnaker")
# each set sail's cloth has its own material (slot "Cloth<Sail>": its seams from its UVs); folded cloth, pockets and
# bunched luffs are "SailHeap"; bags "SailBag"; reef points, sail ties and the spinnaker's tapes "SailLine"


def seed_of(key):
    return zlib.crc32(key.encode()) & 0xFFFFFFFF


def rot(axis, ang):
    """The rotation by ang (radians) about axis: R @ v (numpy's cross product's sense: about +Z, -X turns to -Y)."""
    a = unit(axis)
    K = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
    return np.eye(3) + math.sin(ang) * K + (1.0 - math.cos(ang)) * (K @ K)


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def table(tab):
    """A smooth function of a share (0..1) through the json's [[share, value]] rows."""
    t = np.asarray(tab, float)
    if len(t) == 1:
        return lambda x: np.full(np.shape(x), t[0, 1])
    if len(t) == 2:
        return lambda x: np.interp(x, t[:, 0], t[:, 1])
    f = PchipInterpolator(t[:, 0], t[:, 1])
    return lambda x: f(np.clip(x, t[0, 0], t[-1, 0]))


def camber(f, p):
    """The camber line, 1 at its deepest (f = p), 0 at the luff and leech (the NACA four-digit mean line's shape)."""
    f = np.asarray(f, float)
    return np.where(f < p, (2 * p * f - f * f) / (p * p), ((1 - 2 * p) + 2 * p * f - f * f) / ((1 - p) ** 2))


def arc_factor(m, p, n=400):
    """The camber line's length over its chord at depth m (share of the chord), deepest at p."""
    f = np.linspace(0.0, 1.0, n + 1)
    y = m * camber(f, p)
    return float(np.sum(np.hypot(np.diff(f), np.diff(y))))


def poly_area2(P):
    P = np.asarray(P, float)
    return 0.5 * abs(float(np.dot(P[:, 0], np.roll(P[:, 1], -1)) - np.dot(P[:, 1], np.roll(P[:, 0], -1))))


def tri_faces(nu, nv, collapse=False):
    """Triangles of the grid (i across, 0..nu; j up, 0..nv; vertex i * (nv + 1) + j), each facing (d/di) x (d/dj).
    collapse: the top row (j = nv) is one vertex, the last (index (nu + 1) * nv)."""
    F = []
    top = (nu + 1) * nv

    def vi(i, j):
        if collapse and j == nv:
            return top
        return i * (nv + 1 - (1 if collapse else 0)) + j
    for i in range(nu):
        for j in range(nv):
            a, b, c, d = vi(i, j), vi(i + 1, j), vi(i + 1, j + 1), vi(i, j + 1)
            if collapse and j == nv - 1:
                F.append((a, b, top))
            else:
                F += [(a, b, c), (a, c, d)]
    return F


def surface_points(V, F, step, seed=0):
    """Points over a mesh: its vertices, points every `step` along each triangle's edges and about two to each step^2
    of its area inside (scattered by a seeded generator), so no part of a surface is further than about a step from
    a point."""
    V = np.asarray(V, float)
    T = np.array([(f[0], f[k], f[k + 1]) for f in F for k in range(1, len(f) - 1)], int)
    if not len(T):
        return V.copy()
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    out = [V]
    for P0, P1 in ((A, B), (B, C), (C, A)):
        m = np.ceil(np.linalg.norm(P1 - P0, axis=1) / step).astype(int) - 1
        k = np.nonzero(m > 0)[0]
        if len(k):
            mk = m[k]
            idx = np.repeat(k, mk)
            j = np.arange(idx.size) - np.repeat(np.cumsum(mk) - mk, mk)
            t = (j + 1) / np.repeat(mk + 1, mk)
            out.append(P0[idx] + t[:, None] * (P1 - P0)[idx])
    n = np.floor(np.linalg.norm(np.cross(B - A, C - A), axis=1) / step ** 2).astype(int)
    k = np.nonzero(n > 0)[0]
    if len(k):
        rng = np.random.default_rng(seed)
        idx = np.repeat(k, n[k])
        r1, r2 = rng.random(idx.size), rng.random(idx.size)
        flip = r1 + r2 > 1.0
        r1[flip], r2[flip] = 1.0 - r1[flip], 1.0 - r2[flip]
        out.append(A[idx] + r1[:, None] * (B - A)[idx] + r2[:, None] * (C - A)[idx])
    return np.concatenate(out)


class SailPart(deck.Part):
    """deck.Part with the sail cloth's three UV maps (UV0, UV1, UV2), each face's label, and the sail and state it
    shows; the cloth is an open sheet, everything else closed solids."""

    def __init__(self, name, frame=None, sail=None, state=None):
        super().__init__(name, frame)
        self.uv = {"UV0": [], "UV1": [], "UV2": []}
        self.labels = []
        self.sail, self.state = sail, state
        self.pose = {}
        self.free = []          # the cloth's vertices the press may move (not its luff and corners): the build's room check

    def add(self, V, F, slot, label, uv=None, orient=True, mass=None):
        V = np.asarray(V, float)
        F = [tuple(int(i) for i in f) for f in F]
        if orient and deck.signed_volume(V, F) < 0:
            F = [f[::-1] for f in F]
        off = len(self.V)
        self.V.extend(V.tolist())
        self.F.extend([tuple(i + off for i in f) for f in F])
        self.slot.extend(slot if isinstance(slot, list) else [slot] * len(F))
        self.labels.extend([label] * len(F))
        U = np.zeros((len(V), 6)) if uv is None else np.asarray(uv, float).reshape(-1, 6)
        self.uv["UV0"].extend(U[:, 0:2].tolist())
        self.uv["UV1"].extend(U[:, 2:4].tolist())
        self.uv["UV2"].extend(U[:, 4:6].tolist())
        if mass:
            kg, cen, _ = deck.mass_of(V, F, mass[0], mass[1], mass[2] if len(mass) > 2 else None)
            self.masses.append({"part": label, "kg": round(float(kg), 2), "centre": [round(float(c), 3) for c in cen],
                                "how": mass[0]})

    def weight(self, label, kg, centre, how="estimate"):
        self.masses.append({"part": label, "kg": round(float(kg), 2), "centre": [round(float(c), 3) for c in centre],
                            "how": how})


# ------------------------------------------------------------------------------------------------ small solids
def tube(part, P, r, slot, label, n=8, closed=False, mass=None):
    rings, u = rigging.tube_rings(P, r, n, closed=closed)
    V, F = deck.loft_rings(rings, closed=closed)
    part.add(V, F, slot, label, mass=mass)
    return float(u[-1])


def torus(part, c, nrm, R, r, slot, label, n=12, m=6, kg=None):
    a = spars.unit(np.cross(nrm, EZ if abs(unit(nrm) @ EZ) < 0.9 else EX))
    b = np.cross(unit(nrm), a)
    th = 2 * math.pi * np.arange(n) / n
    P = c[None, :] + R * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b)
    tube(part, P, r, slot, label, n=m, closed=True)
    if kg:
        part.weight(label, kg, c)


def box(part, c, X, Y, Z, half, slot, label, mass=None):
    """A box centred at c, its axes X, Y, Z (unit), half sizes half."""
    X, Y, Z = unit(X), unit(Y), unit(Z)
    pts = []
    for k in (-1, 1):
        ring = [c + k * half[2] * Z + sx * half[0] * X + sy * half[1] * Y for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        pts.append(np.array(ring))
    V, F = deck.loft_rings(pts)
    part.add(V, F, slot, label, mass=mass)


# ------------------------------------------------------------------------------------------------ the cloth's sheet
class Sheet:
    """A sail's cloth: rows j = 0..nv up the sail (Y, the flat height of each), each of nu + 1 points from the luff
    (f = i / nu, the share of the row), G (nu+1, nv+1, 3); UV (nu+1, nv+1, 6). collapse: the top row is one point."""

    def __init__(self, G, Y, UV, collapse=False):
        self.G, self.Y, self.UV, self.collapse = np.asarray(G, float), np.asarray(Y, float), np.asarray(UV, float), collapse
        self.nu, self.nv = self.G.shape[0] - 1, self.G.shape[1] - 1

    def at(self, f, y):
        """Points at matched shares f and heights y (bilinear in the grid)."""
        f, y = np.atleast_1d(np.asarray(f, float)), np.atleast_1d(np.asarray(y, float))
        fi = np.clip(f * self.nu, 0.0, self.nu - 1e-9)
        i0 = np.floor(fi).astype(int)
        a = fi - i0
        j0 = np.clip(np.searchsorted(self.Y, y, side="right") - 1, 0, self.nv - 1)
        b = np.clip((y - self.Y[j0]) / (self.Y[j0 + 1] - self.Y[j0]), 0.0, 1.0)
        G = self.G
        return ((1 - a) * (1 - b))[:, None] * G[i0, j0] + (a * (1 - b))[:, None] * G[i0 + 1, j0] + \
            (a * b)[:, None] * G[i0 + 1, j0 + 1] + ((1 - a) * b)[:, None] * G[i0, j0 + 1]

    def normal(self, f, y, eps=0.01):
        """Unit normals (d/df x d/dy: to starboard on a working sail) at matched f, y."""
        f, y = np.atleast_1d(np.asarray(f, float)), np.atleast_1d(np.asarray(y, float))
        h = max(eps, 0.5 / self.nu)
        dy = max(eps * (self.Y[-1] - self.Y[0]), 0.05)
        Pf = self.at(np.clip(f + h, 0, 1), y) - self.at(np.clip(f - h, 0, 1), y)
        Py = self.at(f, np.clip(y + dy, self.Y[0], self.Y[-1])) - self.at(f, np.clip(y - dy, self.Y[0], self.Y[-1]))
        n = np.cross(Pf, Py)
        return n / np.linalg.norm(n, axis=1)[:, None]

    def vertex_normals(self):
        G = self.G
        di = np.gradient(G, axis=0)
        dj = np.gradient(G, axis=1)
        n = np.cross(di, dj)
        ln = np.linalg.norm(n, axis=2)
        bad = ln < 1e-12
        if bad.any():                                 # the collapsed head: borrow the row below's
            n[bad] = n[np.where(bad)[0], np.maximum(np.where(bad)[1] - 1, 0)]
            ln = np.linalg.norm(n, axis=2)
        return n / np.maximum(ln, 1e-12)[..., None]

    def mesh(self):
        """Vertices, faces and UVs (the head one vertex where the grid collapses)."""
        nu, nv = self.nu, self.nv
        if self.collapse:
            V = np.concatenate([self.G[:, :nv].reshape(-1, 3), self.G[:1, nv]])
            U = np.concatenate([self.UV[:, :nv].reshape(-1, 6), self.UV[:1, nv]])
        else:
            V, U = self.G.reshape(-1, 3), self.UV.reshape(-1, 6)
        return V, tri_faces(nu, nv, self.collapse), U

    def free_vertices(self, fixed):
        """The indices into mesh()'s vertices of the grid points not in `fixed` (nu+1, nv+1)."""
        fx = np.asarray(fixed, bool)
        if self.collapse:
            return np.nonzero(~fx[:, :self.nv].ravel())[0].tolist()
        return np.nonzero(~fx.ravel())[0].tolist()


def edge_lengths(G):
    """Each grid point's longest step to a neighbour (along a row, up, or across either diagonal of a cell)."""
    out = np.zeros(G.shape[:2])
    for a, b in (((slice(0, -1), slice(None)), (slice(1, None), slice(None))),
                 ((slice(None), slice(0, -1)), (slice(None), slice(1, None))),
                 ((slice(0, -1), slice(0, -1)), (slice(1, None), slice(1, None))),
                 ((slice(0, -1), slice(1, None)), (slice(1, None), slice(0, -1)))):
        d = np.linalg.norm(G[b] - G[a], axis=-1)
        out[a] = np.maximum(out[a], d)
        out[b] = np.maximum(out[b], d)
    return out


BUMP_SLOPE = 1.5396                # the steepest slope of (1 - r^2)^2 on 0..1 (at r = 1/sqrt 3)


def bump_field(G0, req, fixed, spread, slope, hold, hinge):
    """The lift of each grid point (nu+1, nv+1) that gives every asking point at least its req: each raises a smooth
    bump req (1 - (r/R)^2)^2 round it (flat on top, so the cloth does not crease over an obstacle), R wide enough that
    the cloth's slope stays under `slope` (R = max(spread, 1.54 req / slope)), and the field is the bumps' greatest.
    The held points stay put, and the cloth hinges at them (the luff rope on its slides, the foot on the boom, a
    corner's ring): it leaves them at a slope of `hinge` at most and eases into the bumps' height, flat by `hold`
    metres from them or as far as that slope needs."""
    shp = req.shape
    Pf = G0.reshape(-1, 3)
    r = req.ravel()
    out = np.zeros(len(Pf))
    ask = np.nonzero(r > 1e-5)[0]
    if not len(ask):
        return out.reshape(shp)
    tree = cKDTree(Pf)
    for i in ask[np.argsort(-r[ask])]:
        if out[i] >= r[i] - 1e-6:
            continue
        R = max(spread, BUMP_SLOPE * r[i] / slope)
        idx = np.asarray(tree.query_ball_point(Pf[i], R), int)
        q = np.linalg.norm(Pf[idx] - Pf[i], axis=1) / R
        np.maximum.at(out, idx, r[i] * (1.0 - q * q) ** 2)
    fx = fixed.ravel()
    if fx.any():
        d, _ = cKDTree(Pf[fx]).query(Pf)
        x = np.clip(d / np.maximum(hold, 2.0 * out / hinge), 0.0, 1.0)
        out *= 1.0 - (1.0 - x) ** 2
    return out.reshape(shp)


def turning(G, skip=None):
    """The cloth's greatest turn between neighbouring cells' normals, degrees, and where (each cell's normal from its
    diagonals; `skip` (nu+1, nv+1) marks grid points whose cells are left out, as the collapsed head)."""
    a = G[1:, 1:] - G[:-1, :-1]
    b = G[:-1, 1:] - G[1:, :-1]
    n = np.cross(a, b)
    ln = np.linalg.norm(n, axis=-1)
    ok = ln > 1e-9
    n = n / np.where(ok, ln, 1.0)[..., None]
    if skip is not None:
        ok &= ~(skip[1:, 1:] | skip[:-1, :-1] | skip[:-1, 1:] | skip[1:, :-1])
    best, at = 0.0, None
    for sl0, sl1 in (((slice(0, -1), slice(None)), (slice(1, None), slice(None))),
                     ((slice(None), slice(0, -1)), (slice(None), slice(1, None)))):
        c = np.clip(np.einsum("ijk,ijk->ij", n[sl0], n[sl1]), -1.0, 1.0)
        m = ok[sl0] & ok[sl1]
        if m.any():
            ang = np.degrees(np.arccos(np.where(m, c, 1.0)))
            k = np.unravel_index(int(np.argmax(ang)), ang.shape)
            if ang[k] > best:
                best = float(ang[k])
                ij = (k[0] + 1, k[1] + 1)
                at = G[min(ij[0], G.shape[0] - 1), min(ij[1], G.shape[1] - 1)]
    return best, at


PRESS_TURN_ADDED_DEG = 10.0     # the most the press may sharpen a sail's greatest turn between neighbouring cells


def press(sheet, push, obstacles, fixed, spread, rounds, reach=1.2, slope=0.25, hold=0.1, hinge=1.0, label="sail"):
    """Press a set sail's cloth off its obstacles, the way a genoa lies on the lee spreader tips and shrouds and clear of
    the mast. `push` (nu+1, nv+1, 3) is the unit direction each grid point may move (the cloth's normal turned to
    leeward, say); obstacles [(points (m, 3), clearance, name, side)]: side +1 must end up behind the cloth (on the side
    away from push: the mast and the mainsail to windward of a genoa), side -1 in front of it (on push's side: the lee
    shrouds outside it). A point of an obstacle less than its clearance on the wrong side's edge, or through the cloth
    by up to `reach`, within three quarters of a cell of a grid point in the cloth's plane, asks that grid point to
    move (along push, or against it) until the obstacle is its clearance clear; the moves each way are smooth bumps
    (bump_field: at least `spread` wide, wider for a bigger move so the cloth's slope stays under `slope`), the `fixed`
    points (the luff, the corners) held and the cloth hinging at them (at a slope of `hinge` at most, flat by `hold`
    metres or as far as that needs). Where the obstacle lies beyond the grid's edge (outward of an edge point), it asks
    nothing. Repeats `rounds` times on the moved cloth. Changes sheet.G; returns a report, with the cloth's greatest
    turn between neighbouring cells before and after (away from the held edges, and with them). Fails if the press
    adds more than PRESS_TURN_ADDED_DEG to that turn away from the held edges: a crease, not a bend."""
    G0 = sheet.G.copy()
    nu1, nv1 = G0.shape[:2]
    el = edge_lengths(G0)
    cell = float(np.median(el))
    foot = (0.75 * el).ravel()
    skip = el < 0.25 * cell                              # the collapsed head's points, left out of the turn
    hinged = skip | fixed                                # and the cells on a held edge (the cloth hinges there)
    turn0, _ = turning(G0, hinged)
    up, dn = np.zeros((nu1, nv1)), np.zeros((nu1, nv1))
    req = {1: np.zeros((nu1, nv1)), -1: np.zeros((nu1, nv1))}
    # outward directions at the grid's edges, to tell an obstacle beyond the edge from one over the cloth
    out_dir = np.zeros((nu1, nv1, 3))
    out_dir[0] += G0[0] - G0[1]
    out_dir[-1] += G0[-1] - G0[-2]
    out_dir[:, 0] += G0[:, 0] - G0[:, 1]
    out_dir[:, -1] += G0[:, -1] - G0[:, -2]
    on_edge = np.zeros((nu1, nv1), bool)
    on_edge[0], on_edge[-1], on_edge[:, 0], on_edge[:, -1] = True, True, True, True
    Ef, edge_f = out_dir.reshape(-1, 3), on_edge.ravel()
    asked = {}
    rmax = float(foot.max()) + reach + 0.2
    rnd, left, k_left = 0, 0.0, 0
    for rnd in range(rounds + 1):
        t = up - dn
        Pf = (G0 + t[..., None] * push).reshape(-1, 3)
        Nf = push.reshape(-1, 3)
        tree = cKDTree(Pf)
        need = {1: np.zeros(len(Pf)), -1: np.zeros(len(Pf))}
        for ob in obstacles:
            Q, c, name = ob[0], ob[1], ob[2]
            side = ob[3] if len(ob) > 3 else 1
            if not len(Q):
                continue
            d, _ = tree.query(Q, distance_upper_bound=rmax)
            Qn = Q[np.isfinite(d)]
            if not len(Qn):
                continue
            # each obstacle point against its nearest grid points (the cloth's normal through it lands among them)
            dk, ik = tree.query(Qn, k=min(9, len(Pf)), distance_upper_bound=rmax)
            m = np.isfinite(dk)
            qi = np.nonzero(m)[0]
            vi = ik[m]
            if not len(qi):
                continue
            w = Qn[qi] - Pf[vi]
            a = side * np.einsum("ij,ij->i", w, Nf[vi])           # how far through (on the side it must not be)
            lat = w - (side * a)[:, None] * Nf[vi]
            b = np.linalg.norm(lat, axis=1)
            ok = (b < foot[vi]) & (a > -c) & (a < reach)
            beyond = edge_f[vi] & (np.einsum("ij,ij->i", lat, Ef[vi]) > 0.5 * b * np.linalg.norm(Ef[vi], axis=1))
            ok &= ~beyond
            if ok.any():
                np.maximum.at(need[side], vi[ok], a[ok] + c)
                if rnd < rounds:
                    asked[name] = max(asked.get(name, 0.0), float((a[ok] + c).max()))
        left = float(max(need[1].max(), need[-1].max()))
        k_left = int(np.argmax(np.maximum(need[1], need[-1])))
        if left < 1e-4 or rnd == rounds:
            break
        for sd, fld in ((1, up), (-1, dn)):
            req[sd] = np.maximum(req[sd], fld + need[sd].reshape(nu1, nv1))
        up = bump_field(G0, req[1], fixed, spread, slope, hold, hinge)
        dn = bump_field(G0, req[-1], fixed, spread, slope, hold, hinge)
    t = up - dn
    sheet.G = G0 + t[..., None] * push
    turn1, at1 = turning(sheet.G, hinged)
    turn_h, at_h = turning(sheet.G, skip)
    if turn1 > turn0 + PRESS_TURN_ADDED_DEG:
        raise SystemExit(f"{label}: the press creases the cloth ({turn0:.1f} to {turn1:.1f} degrees between "
                         f"neighbouring cells at {None if at1 is None else at1.round(2)}): spread it wider")
    both = (up > 1e-3) & (dn > 1e-3)
    return {"rounds": rnd, "most_moved_m": round(float(np.abs(t).max()), 3),
            "most_moved_with_push_m": round(float(up.max()), 3), "most_moved_against_push_m": round(float(dn.max()), 3),
            "moved_points": int((np.abs(t) > 1e-3).sum()), "points": int(t.size),
            "asked_by": {k: round(v, 3) for k, v in sorted(asked.items(), key=lambda kv: -kv[1])},
            "held_points_asked_m": round(float(max((req[1] * fixed).max(), (req[-1] * fixed).max())), 3),
            "still_asked_m": round(left, 3),
            "still_asked_at": [round(float(v), 3) for v in sheet.G.reshape(-1, 3)[k_left]] if left > 1e-4 else None,
            "points_pushed_both_ways": int(both.sum()), "cell_m": round(cell, 3),
            "turn_deg_shaped": round(turn0, 1), "turn_deg_pressed": round(turn1, 1),
            "turn_at": None if at1 is None else [round(float(v), 3) for v in at1],
            "turn_deg_pressed_with_hinges": round(turn_h, 1),
            "hinge_at": None if at_h is None else [round(float(v), 3) for v in at_h]}


# ------------------------------------------------------------------------------------------------ the boom and the luff
def boom_geom(pts, rig):
    """The gooseneck pin G, the boom's swing axis Zb (the pin's, the mast's axis), its top line (D aft along it, N up
    square to it, top0 over the pin, t_a where it meets the mast's after face) and E."""
    G, s_pin = np.asarray(pts["gooseneck_pin"], float), pts["s_pin"]
    D, N, top0, t_a = spars.boom_line(G, s_pin)
    return {"G": G, "Zb": spars.A.copy(), "D": D, "N": N, "top0": top0, "t_a": t_a, "E": rig["measures"]["E_m"]}


def mast_luff(s, off):
    """The mainsail's luff rope's centre at s along the mast: off abaft the mast's after face."""
    s = np.atleast_1d(np.asarray(s, float))
    return np.array([spars.at(v, -(spars.half_depth(v) + off)) for v in s])


def stay_of(rr, name):
    """A stay's wire (upper end a, lower end b, radius) from the rigging's report."""
    w = next(w for w in rr["wires"] if w["name"] == name)
    P = np.asarray(w["path"], float)
    return P[0], P[-1], w["r"]


# ------------------------------------------------------------------------------------------------ the mainsail
class Mainsail:
    def __init__(self, pts, rig):
        self.sp = sp = SL["mainsail"]
        self.bg = bg = boom_geom(pts, rig)
        self.pts = pts
        D, N, top0 = bg["D"], bg["N"], bg["top0"]
        off = sp["luff_off"]
        foot0 = top0 + sp["foot_off"] * N
        # the tack: where the luff line meets the foot line
        lo, hi = 0.0, spars.s_at(5.0)
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if (mast_luff(mid, off)[0] - foot0) @ N < 0:
                lo = mid
            else:
                hi = mid
        self.s_T = 0.5 * (lo + hi)
        self.T0 = mast_luff(self.s_T, off)[0]
        s_band = spars.S_TOP - spars.M["black_band"]["below_top"]
        self.s_H = s_band - sp["head_below_band"]
        ss = np.linspace(self.s_T, self.s_H, 600)
        L = mast_luff(ss, off)
        self.luff_s, self.luff_x, self.luff_y = ss, (L - self.T0) @ D, (L - self.T0) @ N
        self.yH = float(self.luff_y[-1])
        self.xH = float(self.luff_x[-1])
        t_T = float((self.T0 - top0) @ D)
        t_C = bg["t_a"] + bg["E"] - sp["clew_inside_band"]
        self.t_T, self.xC = t_T, t_C - t_T
        self.track_from = rig["boom"]["track_from_pin_m"]               # the boom's track's forward end, from the pin
        self.H2 = np.array([self.xH + sp["headboard"], self.yH])
        self.C2 = np.array([self.xC, 0.0])
        e = self.H2 - self.C2
        self.leech_len = float(np.linalg.norm(e))
        self.e_l = e / self.leech_len                                  # up the leech's line
        self.n_out = np.array([self.e_l[1], -self.e_l[0]])             # out of the sail, square to it (aft and up)
        p = math.log(0.5) / math.log(sp["roach_at"])
        self.p_roach = p
        u = np.linspace(0.0, 1.0, 4001)
        r = self.roach(u)
        E = self.C2[None] + u[:, None] * e[None] + r[:, None] * self.n_out[None]
        self.leech_u, self.leech_x, self.leech_yv = u, E[:, 0], E[:, 1]
        if np.any(np.diff(E[:, 1]) <= 0):
            raise SystemExit("the mainsail's leech doubles back on itself: less roach")

    def roach(self, u):
        u = np.clip(np.asarray(u, float), 0.0, 1.0)
        return self.sp["roach"] * np.sin(math.pi * u ** self.p_roach)

    def xL(self, y):
        return np.interp(y, self.luff_y, self.luff_x)

    def xE(self, y):
        return np.interp(y, self.leech_yv, self.leech_x)

    def s_of_y(self, y):
        return np.interp(y, self.luff_y, self.luff_s)

    def flat_to_rest(self, x, y):
        """A flat point (x aft along the foot from the tack, y up square to it) on the sail at rest (amidships)."""
        bg = self.bg
        return self.T0[None] + np.atleast_1d(x)[:, None] * bg["D"][None] + np.atleast_1d(y)[:, None] * bg["N"][None]

    def rows(self):
        cell = SL["grid"]["cell"]
        n = int(math.ceil(self.yH / cell))
        Y = np.linspace(0.0, self.yH, n + 1)
        for h in self.sp["reefs"]:
            Y[int(np.argmin(np.abs(Y - h)))] = h
        return np.unique(Y)

    def uv(self, X, Y, f):
        """UVs at flat points X, Y (shares f along their rows)."""
        xl = self.xL(Y)
        d_line = (X - self.C2[0]) * (-self.n_out[0]) + (Y - self.C2[1]) * (-self.n_out[1])   # in from the leech's line
        return np.stack([X - xl, Y, f, Y / self.yH, self.xE(Y) - X, d_line], -1)

    def sheet(self, trim):
        """The set mainsail's cloth for a trim ('Set' or 'Run'), before it is pressed."""
        tr = self.sp["trims"][trim]
        bg = self.bg
        Y = self.rows()
        cell = SL["grid"]["cell"]
        nu = int(math.ceil((self.xE(0.0) - self.xL(0.0)) / cell))
        f = np.linspace(0.0, 1.0, nu + 1)
        psi0, tw = math.radians(tr["boom_deg"]), math.radians(tr["twist_deg"])
        depth, draft = table(tr["depth"]), table(tr["draft"])
        R0 = rot(bg["Zb"], psi0)
        T_rot = bg["G"] + R0 @ (self.T0 - bg["G"])
        G = np.zeros((nu + 1, len(Y), 3))
        UV = np.zeros((nu + 1, len(Y), 6))
        for j, y in enumerate(Y):
            h = y / self.yH
            L3 = mast_luff(self.s_of_y(y), self.sp["luff_off"])[0]
            L3 = L3 + (1.0 - smooth01(y / 1.2)) * (T_rot - self.T0)
            R = rot(bg["Zb"], psi0 + tw * h ** 1.2)
            d, nl = R @ bg["D"], R @ (-EY)
            xl, xe = float(self.xL(y)), float(self.xE(y))
            c = xe - xl
            m, p = float(depth(h)), float(draft(h))
            c3 = c / arc_factor(m, p)
            G[:, j] = L3[None] + (f * c3)[:, None] * d[None] + (m * c3 * camber(f, p))[:, None] * nl[None]
            UV[:, j] = self.uv(xl + f * c, np.full(nu + 1, y), f)
        return Sheet(G, Y, UV), f

    def lee_dirs(self, sheet, trim):
        """Each grid point's leeward direction (to port on starboard tack): the cloth's normal turned to port's side."""
        n = sheet.vertex_normals()
        psi = math.radians(self.sp["trims"][trim]["boom_deg"])
        lee = rot(self.bg["Zb"], psi) @ (-EY)
        return n * np.sign(np.einsum("ijk,k->ij", n, lee))[..., None]

    def fixed(self, sheet):
        fx = np.zeros(sheet.G.shape[:2], bool)
        fx[0, :] = True
        fx[:, 0] = True
        fx[-1, -1] = True
        return fx

    def area(self):
        y = np.linspace(0.0, self.yH, 2001)
        return float(np.trapezoid(self.xE(y) - self.xL(y), y))

    def roach_area(self):
        u = np.linspace(0, 1, 2001)
        return float(np.trapezoid(self.roach(u), u) * self.leech_len)

    def backstay_room(self, backstay):
        """The roach's room under the backstay with the boom amidships: the least distance aft of the leech (in the
        centreline plane, at each height) to the backstay's line."""
        a, b, r = backstay
        u = self.leech_u
        P = self.flat_to_rest(self.leech_x, self.leech_yv)
        out = []
        for p in P[::20]:
            # the backstay's x at this point's height, less its radius
            t = (p[2] - b[2]) / (a[2] - b[2])
            xb = b[0] + t * (a[0] - b[0])
            out.append((p[0] - xb - r, p[2]))
        k = int(np.argmin([o[0] for o in out]))
        return {"least_m": round(out[k][0], 3), "at_z_m": round(out[k][1], 2), "points": len(out), "u_samples": len(u)}

    # -- the parts on the cloth ------------------------------------------------------------------------------------
    def dress(self, part, sh, trim, R_boom):
        """The set sail's ropes, slides, headboard, battens, reef points and cringles (R_boom: the boom's pose)."""
        ro = SL["ropes"]
        # bolt ropes on the luff and the foot
        tube(part, sh.G[0], ro["main_bolt"], "Rope", "Mainsail bolt rope")
        tube(part, sh.G[:, 0], ro["main_bolt"], "Rope", "Mainsail bolt rope")
        nluff = self.slides_luff(part)
        nfoot = self.slides_foot(part, R_boom)
        self.headboard(part, sh)
        self.battens(part, sh)
        self.reef_gear(part, sh)
        for f_, y_ in ((0.0, 0.0), (1.0, 0.0)):
            P = sh.at([f_], [y_])[0]
            inward = sh.at([0.5], [min(y_ + 1.0, self.yH)])[0] - P
            torus(part, P + unit(inward) * 0.05, sh.normal([f_], [y_])[0], 0.035, 0.009, "Bronze", "Mainsail cringle",
                  kg=0.3)
        return nluff, nfoot

    def slide_at(self, part, c, along, aft, out_len, label):
        """A slide on a track: a bronze body astride the track's flange (c its centre, `along` the track, `aft` away
        from the spar) and an eye out to the bolt rope."""
        sl = self.sp["slide"]
        side = np.cross(aft, along)
        box(part, c, along, side, aft, (sl["height"] / 2, sl["width"] / 2, sl["depth"] / 2), "Bronze",
            f"{label} slide")
        e = c + aft * (sl["depth"] / 2 + out_len / 2)
        box(part, e, along, side, aft, (0.018, 0.006, out_len / 2 + 0.002), "Bronze", f"{label} slide")
        part.weight(f"{label} slides", sl["kg"], c)

    def slides_luff(self, part, s_list=None):
        sp = self.sp
        sl = sp["slide"]
        if s_list is None:
            s_list = list(np.arange(self.s_T + 0.45, self.s_H - 0.25, sp["slide_every"])) + [self.s_H - 0.1]
        tk = spars.RG["track"]
        for s in s_list:
            a = spars.half_depth(s)
            c = spars.at(s, -(a + tk["proud"] + 0.001 + sl["depth"] / 2))
            out_len = sp["luff_off"] - (tk["proud"] + 0.001 + sl["depth"]) - SL["ropes"]["main_bolt"] * 0.5
            self.slide_at(part, c, spars.A, -spars.FW, out_len, "Mainsail luff")
        return len(s_list)

    def foot_ts(self):
        """The foot's slides along it from the tack: the first on the boom's track (whose forward end is just abaft
        the jaw's socket) with its whole length, then every 'slide_every', the last by the clew."""
        t0 = max(0.45, self.track_from - self.t_T + 0.5 * self.sp["slide"]["height"] + 0.02)
        return list(np.arange(t0, self.xC - 0.3, self.sp["slide_every"])) + [self.xC - 0.12]

    def slides_foot(self, part, R_boom, ts=None):
        sp, bg = self.sp, self.bg
        sl = sp["slide"]
        tk = spars.RG["track"]
        ts = self.foot_ts() if ts is None else ts
        for t in ts:
            c = bg["top0"] + (self.t_T + t) * bg["D"] + (tk["proud"] + 0.001 + sl["depth"] / 2) * bg["N"]
            c = bg["G"] + R_boom @ (c - bg["G"])
            out_len = sp["foot_off"] - (tk["proud"] + 0.001 + sl["depth"]) - SL["ropes"]["main_bolt"] * 0.5
            self.slide_at(part, c, R_boom @ bg["D"], R_boom @ bg["N"], out_len, "Mainsail foot")
        return len(ts)

    def headboard(self, part, sh):
        sp = self.sp
        y0 = self.yH - sp["headboard_depth"]
        ys = np.linspace(y0, self.yH, 6)
        fr = []
        for y in ys:
            xl, xe = float(self.xL(y)), float(self.xE(y))
            top_share = (y - y0) / (self.yH - y0)
            x_end = xl + (sp["headboard"] * 0.55 + 0.45 * sp["headboard"] * top_share)
            fr.append((min(1.0, (x_end - xl) / (xe - xl)), y))
        F_ = np.array([q[0] for q in fr])
        ring_f = np.concatenate([np.zeros(len(ys)) + 0.003, F_[::-1]])
        ring_y = np.concatenate([ys, ys[::-1]])
        P = sh.at(ring_f, ring_y)
        Nn = sh.normal(ring_f, ring_y)
        # the plate 'headboard_t' thick riveted between the cloth's two layers (2 mm each): the solid is all three,
        # weighed as the plate's share of it
        t = sp["headboard_t"]
        V, F = deck.loft_rings([P - Nn * (t / 2 + 0.002), P + Nn * (t / 2 + 0.002)])
        part.add(V, F, "Spar", "Headboard", mass=("solid", DUR * t / (t + 0.004)))

    def battens(self, part, sh):
        bt = self.sp["battens"]
        for u, ln in zip(bt["at"], bt["length"]):
            E0 = self.C2 + u * (self.H2 - self.C2) + float(self.roach(u)) * self.n_out
            k = np.linspace(0.0, 1.0, 9)
            Q = E0[None] - (k * ln)[:, None] * self.n_out[None]
            y = Q[:, 1]
            xl, xe = self.xL(y), self.xE(y)
            f = np.clip((Q[:, 0] - xl) / (xe - xl), 0.0, 0.999)
            P = sh.at(f, y)
            Nn = sh.normal(f, y)
            along = np.gradient(P, axis=0)
            side = np.cross(Nn, along)
            side /= np.linalg.norm(side, axis=1)[:, None]
            w = bt["pocket_w"] / 2
            rings = [np.array([p - n * 0.0015 - s * w, p - n * bt["proud"] - s * w * 0.8, p - n * bt["proud"] + s * w * 0.8,
                               p - n * 0.0015 + s * w]) for p, n, s in zip(P, Nn, side)]
            V, F = deck.loft_rings(rings)
            part.add(V, F, "SailHeap", "Batten pocket")
            part.weight("Battens", ASH * ln * 0.045 * 0.009, P.mean(0))

    def reef_gear(self, part, sh):
        sp = self.sp
        r = SL["ropes"]["reef_point"]
        n_pts = 0
        for h in sp["reefs"]:
            xl, xe = float(self.xL(h)), float(self.xE(h))
            xs = np.arange(xl + 0.6, xe - 0.5, sp["point_every"])
            for x in xs:
                f0 = (x - xl) / (xe - xl)
                for side in (1.0, -1.0):
                    ys = h - np.array([0.0, 0.33, 0.66, 1.0]) * sp["point_hang"]
                    xls, xes = self.xL(ys), self.xE(ys)
                    fs = np.clip((x - xls) / (xes - xls), 0, 1)
                    P = sh.at(fs, ys)
                    Nn = sh.normal(fs, ys)
                    lift = side * (r + 0.004 + np.array([0.0, 0.004, 0.009, 0.015]))
                    top = sh.at([f0], [h + 0.01])[0] + sh.normal([f0], [h])[0] * side * (r + 0.004)
                    tube(part, np.vstack([top, P + Nn * lift[:, None]]), r, "SailLine", "Reef point", n=4)
                n_pts += 1
            for f_ in (0.0, 1.0):
                P = sh.at([f_], [h])[0]
                inward = sh.at([0.5], [h])[0] - P
                torus(part, P + unit(inward) * 0.045, sh.normal([f_], [h])[0], 0.032, 0.008, "Bronze", "Reef cringle",
                      kg=0.25)
        return n_pts

    # -- stowed ------------------------------------------------------------------------------------------------------
    def stack(self, part):
        """The luff's slides stacked at the foot of the mast's track, the headboard on top, the luff rope between."""
        sp = self.sp
        n = self.slides_count()
        if sp["stow"]["stack_pitch"] < sp["slide"]["height"]:
            raise SystemExit("the stacked slides would overlap: stack_pitch under a slide's height")
        s0 = self.s_T + 0.03
        ss = s0 + np.arange(n) * sp["stow"]["stack_pitch"]
        self.slides_luff(part, list(ss))
        top = ss[-1] + 0.08
        a = spars.half_depth(top)
        c = spars.at(top + 0.25, -(a + sp["luff_off"]))
        hb = sp["headboard"]
        box(part, c - spars.FW * (hb / 2 - 0.01), spars.A, spars.Y, spars.FW, (0.25, sp["headboard_t"] / 2, hb / 2 - 0.004),
            "Spar", "Headboard", mass=("solid", DUR))
        # the bunched luff abaft the slides: the tube's forward side 3 mm behind their eyes' ends
        r_b = 0.045
        P = mast_luff(np.linspace(self.s_T, top + 0.2, 8), sp["luff_off"] - 0.5 * SL["ropes"]["main_bolt"] + 0.005 + r_b)
        tube(part, P, r_b, "SailHeap", "Mainsail luff bunched", n=10)
        return float(top - self.s_T)

    def slides_count(self):
        return len(list(np.arange(self.s_T + 0.45, self.s_H - 0.25, self.sp["slide_every"]))) + 1


# ------------------------------------------------------------------------------------------------ headsails
class Headsail:
    def __init__(self, key, rr):
        hs = SL["headsails"]
        self.key = key
        self.sp = sp = hs[key]
        stay_name = {"forestay": "Forestay", "staysail": "Staysail stay"}[sp["stay"]]
        a, b, r = stay_of(rr, stay_name)
        self.stay = (a, b, r)
        self.stay_name = stay_name
        self.u = unit(a - b)
        self.Ls = float(np.linalg.norm(a - b))
        self.pa = unit(np.cross(self.u, EY))                         # square to the stay, aft and down
        if self.pa[0] > 0:
            self.pa = -self.pa
        self.off = hs["luff_off"]
        self.T = b + sp["tack_up"] * self.u + self.off * self.pa
        self.H = b + (self.Ls - sp["head_below"]) * self.u + self.off * self.pa
        xc, hc = sp["clew"]
        self.C = np.array([xc, 0.0, float(shell.deck_z(np.array([xc]), np.array([0.0]))[0]) + hc])
        self.xh_ = unit(self.C - self.T)                              # along the foot, aft
        v = self.H - self.T
        self.yh_ = unit(v - (v @ self.xh_) * self.xh_)                # up, square to the foot, in the centreline plane
        self.Hf = np.array([v @ self.xh_, v @ self.yh_])
        self.Cf = np.array([(self.C - self.T) @ self.xh_, 0.0])
        self.yH = float(self.Hf[1])
        self.quad = "upper_clew" in sp
        if self.quad:
            self.UCf = self.Cf + sp["upper_clew"] * (self.Hf - self.Cf)
            self.LCf = self.Cf * (1.0 - sp["lower_clew"])
        e = self.Hf - self.Cf
        self.leech_len = float(np.linalg.norm(e))
        self.e_l = e / self.leech_len
        self.n_in = np.array([-self.e_l[1], self.e_l[0]])            # into the sail from the leech's line
        if self.n_in @ (np.zeros(2) - self.Cf) < 0:
            self.n_in = -self.n_in

    def xL(self, y):
        return np.asarray(y, float) * self.Hf[0] / self.yH

    def xA(self, y):
        """The after edge's x at height y: the leech, or on the quadrilateral jib below its upper clew the cut."""
        y = np.asarray(y, float)
        xl = self.Cf[0] + (self.Hf[0] - self.Cf[0]) * y / self.yH
        if not self.quad:
            return xl
        cut = self.LCf[0] + (self.UCf[0] - self.LCf[0]) * np.clip(y / self.UCf[1], 0, 1)
        return np.where(y < self.UCf[1], cut, xl)

    def rows(self):
        cell = SL["grid"]["cell"]
        n = int(math.ceil(self.yH / cell))
        Y = np.linspace(0.0, self.yH, n + 1)
        if self.quad:
            Y[int(np.argmin(np.abs(Y - self.UCf[1])))] = self.UCf[1]
        return np.unique(Y)

    def flat_to_rest(self, x, y):
        return self.T[None] + np.atleast_1d(x)[:, None] * self.xh_[None] + np.atleast_1d(y)[:, None] * self.yh_[None]

    def uv(self, X, Y, f):
        d_leech = (X - self.Cf[0]) * self.n_in[0] + (Y - self.Cf[1]) * self.n_in[1]
        return np.stack([X - self.xL(Y), Y, f, Y / self.yH, self.xA(Y) - X, d_leech], -1)

    def row_at(self, y, psi):
        """Row y's luff point, its chord's direction and its lee normal turned psi (radians) off the centreline."""
        Ll = float(np.linalg.norm(self.H - self.T))
        R = rot(EZ, psi)
        return self.T + (y / self.yH * Ll) * unit(self.H - self.T), R @ self.xh_, R @ (-EY)

    def trim_rows(self, Y, lee, inside, clear, half_band):
        """Each row's angle off the centreline: the trim's (psi_deg, twist_deg more by the head), sheeted in where the
        cloth would pass outside the lee rigging (lee points must stay `clear` to leeward of it) and out where it
        would come inside the mast, the mainsail or the windward rigging (inside points `clear` to windward), the
        rows' angles then smoothed within those limits. A row that cannot be both is made flatter (its depth less)
        until it can. Returns (psi per row, depth factor per row, a report)."""
        tr = self.sp["trim"]
        psi0, tw = math.radians(tr["psi_deg"]), math.radians(tr["twist_deg"])
        depth, draft = table(tr["depth"]), table(tr["draft"])
        nY = len(Y)
        psi_t = psi0 + tw * Y / self.yH
        lo, hi, kd = np.zeros(nY), psi_t.copy(), np.ones(nY)
        flat = 0
        for j, y in enumerate(Y):
            h = y / self.yH
            c = float(self.xA(y) - self.xL(y))
            if c < 0.3:
                # the head's last rows, too short to meet anything: they follow the rows below
                lo[j], hi[j] = 0.0, psi_t[j] + math.radians(12.0)
                continue
            p_ = float(draft(h))
            L3, d, nl = self.row_at(y, float(psi_t[j]))
            w_ = np.cross(d, nl)
            near_l = lee[np.abs((lee - L3[None]) @ w_) < half_band + 0.3] if len(lee) else lee
            near_i = inside[np.abs((inside - L3[None]) @ w_) < half_band + 0.3] if len(inside) else inside

            def worst(psi, P, m, sign):
                L3, d, nl = self.row_at(y, psi)
                c3 = c / arc_factor(m, p_)
                w_ = np.cross(d, nl)
                Q = P - L3[None]
                u, v, w = Q @ d, Q @ nl, Q @ w_
                k = (np.abs(w) < half_band) & (u > 0.0) & (u < c3)
                if not k.any():
                    return 1.0
                vc = m * c3 * camber(u[k] / c3, p_)
                return float(np.min(sign * (v[k] - vc)) - clear)
            for _ in range(8):
                m = float(depth(h)) * kd[j]
                ok_lee = (lambda ps: worst(ps, near_l, m, 1.0) >= 0.0) if len(near_l) else (lambda ps: True)
                ok_in = (lambda ps: worst(ps, near_i, m, -1.0) >= 0.0) if len(near_i) else (lambda ps: True)
                # the most it may be eased (lee) and the least it may be sheeted (inside), within 12 degrees of the trim
                top = psi_t[j] + math.radians(12.0)
                if ok_lee(top):
                    hi[j] = top
                elif not ok_lee(0.0):
                    hi[j] = -1.0
                else:
                    a_, b_ = 0.0, top
                    for _ in range(30):
                        mid = 0.5 * (a_ + b_)
                        a_, b_ = (mid, b_) if ok_lee(mid) else (a_, mid)
                    hi[j] = a_
                if ok_in(0.0):
                    lo[j] = 0.0
                elif not ok_in(top):
                    lo[j] = top + 1e-6          # no room within the search: the build fails on it (rows_without_room)
                else:
                    a_, b_ = 0.0, top
                    for _ in range(30):
                        mid = 0.5 * (a_ + b_)
                        a_, b_ = (a_, mid) if ok_in(mid) else (mid, b_)
                    lo[j] = b_
                if lo[j] <= hi[j]:
                    break
                kd[j] *= 0.85
                flat += 1
        bad = lo > hi
        # the rows' angles within their limits, smoothed, and never less by the head than below it: a sail's leech
        # twists off steadily up the sail, so a row eased past an obstacle eases every row above it as much
        hi_ = np.maximum(hi, lo)
        psi = np.maximum.accumulate(np.clip(psi_t, lo, hi_))
        for _ in range(40):
            psi = np.maximum.accumulate(np.clip(gaussian_filter(psi, 2.0, mode="nearest"), lo, hi_))
        bad |= psi > hi_ + 1e-6
        k_e = int(np.argmax(psi - psi_t))
        rep = {"rows": nY, "rows_sheeted_in": int((psi < psi_t - 1e-3).sum()),
               "rows_eased": int((psi > psi_t + 1e-3).sum()),
               "most_sheeted_in_deg": round(math.degrees(float(np.max(psi_t - psi))), 2),
               "most_eased_deg": round(math.degrees(float(psi[k_e] - psi_t[k_e])), 2),
               "most_eased_at_share": round(float(Y[k_e] / self.yH), 2),
               "rows_made_flatter": int((kd < 1).sum()), "least_depth_factor": round(float(kd.min()), 3),
               "rows_without_room": int(bad.sum()),
               "psi_deg_foot_mid_head": [round(math.degrees(float(psi[k])), 2) for k in (0, nY // 2, nY - 1)]}
        return psi, kd, rep

    def sheet(self, lee=np.zeros((0, 3)), inside=np.zeros((0, 3)), clear=0.05):
        tr = self.sp["trim"]
        Y = self.rows()
        cell = SL["grid"]["cell"]
        nu = int(math.ceil(float(np.max(self.xA(Y) - self.xL(Y))) / cell))
        f = np.linspace(0.0, 1.0, nu + 1)
        depth, draft = table(tr["depth"]), table(tr["draft"])
        band = 0.5 * float(np.max(np.diff(Y)))
        psi, kd, self.trim_rep = self.trim_rows(Y, lee, inside, clear, band)
        self.psi_rows = psi
        G = np.zeros((nu + 1, len(Y), 3))
        UV = np.zeros((nu + 1, len(Y), 6))
        for j, y in enumerate(Y):
            h = y / self.yH
            L3, d, nl = self.row_at(y, float(psi[j]))
            xl, xa = float(self.xL(y)), float(self.xA(y))
            c = xa - xl
            m, p = float(depth(h)) * kd[j], float(draft(h))
            c3 = c / arc_factor(m, p) if c > 1e-6 else 0.0
            G[:, j] = L3[None] + (f * c3)[:, None] * d[None] + (m * c3 * camber(f, p))[:, None] * nl[None]
            UV[:, j] = self.uv(xl + f * c, np.full(nu + 1, y), f)
        return Sheet(G, Y, UV, collapse=True), f

    def lee_dirs(self, sheet):
        n = sheet.vertex_normals()
        lee = np.stack([rot(EZ, float(ps)) @ (-EY) for ps in self.psi_rows])
        return n * np.sign(np.einsum("ijk,jk->ij", n, lee))[..., None]

    def fixed(self, sheet):
        fx = np.zeros(sheet.G.shape[:2], bool)
        fx[0, :] = True
        fx[:, -1] = True
        fx[-1, 0] = True
        if self.quad:
            j = int(np.argmin(np.abs(sheet.Y - self.UCf[1])))
            fx[-1, j] = True
        return fx

    def outline(self):
        if self.quad:
            return np.array([[0.0, 0.0], self.LCf, self.UCf, self.Hf])
        return np.array([[0.0, 0.0], self.Cf, self.Hf])

    def area(self):
        return poly_area2(self.outline())

    def lp(self):
        """The clew's (the virtual clew's) distance square to the luff, the 'LP'."""
        lu = unit(self.Hf)
        c = self.Cf
        return float(abs(c[0] * lu[1] - c[1] * lu[0]))

    def dress(self, part, sh):
        hs = SL["headsails"]
        a, b, r_st = self.stay
        ro = SL["ropes"]
        tube(part, sh.G[0], ro["headsail_luff"], "Rope", f"{self.key.capitalize()} luff rope")
        n = self.hanks(part, np.arange(0.35, float(np.linalg.norm(self.H - self.T)) - 0.1, hs["hank_every"]))
        corners = [(0.0, 0.0), (1.0, 0.0), (0.0, self.yH)]
        if self.quad:
            corners.append((1.0, float(self.UCf[1])))
        for f_, y_ in corners:
            P = sh.at([f_], [y_])[0]
            inward = sh.at([0.35], [min(max(y_, 0.6), self.yH - 0.6)])[0] - P
            torus(part, P + unit(inward) * 0.05, sh.normal([f_], [min(y_, self.yH - 0.05)])[0], 0.035, 0.009, "Bronze",
                  f"{self.key.capitalize()} cringle", kg=0.3)
        return n

    def hanks(self, part, ds):
        """Piston hanks round the stay at ds along the luff from the tack, each with a tongue to the luff rope."""
        hk = SL["headsails"]["hank"]
        a, b, r_st = self.stay
        n = 0
        for d in ds:
            P = self.T + d * self.u
            c = P - self.off * self.pa                                # on the stay
            torus(part, c, self.u, r_st + hk["clear"] + hk["r"], hk["r"], "Bronze", "Hank", n=12, m=5)
            # the tongue: from the hank's aft side to the luff rope
            e0 = c + self.pa * (r_st + hk["clear"] + 2 * hk["r"])
            e1 = P - self.pa * SL["ropes"]["headsail_luff"] * 0.4
            mid = 0.5 * (e0 + e1)
            box(part, mid, self.u, EY, self.pa, (0.012, 0.004, float(np.linalg.norm(e1 - e0)) / 2 + 0.002), "Bronze", "Hank")
            part.weight("Hanks", hk["kg"], c)
            n += 1
        return n


# ------------------------------------------------------------------------------------------------ the spinnaker
class Spinnaker:
    def __init__(self, pts, rig):
        self.sp = sp = SL["spinnaker"]
        crane = np.asarray(pts["masthead_crane_tip"], float)
        self.crane = crane
        self.H = crane + sp["head_fwd"] * EX - sp["head_below_crane"] * EZ
        pl = spars.RG["pole"]
        Ph = np.asarray(pts["pole_heel_pin"], float)
        self.dz_pole = (sp["pole_heel_above_deck"] - pl["heel_above_deck"]) / math.cos(spars.RAKE)
        Ph = Ph + self.dz_pole * spars.A
        ang = math.radians(sp["pole_deg"])
        self.pole_dir = np.array([math.cos(ang), math.sin(ang), 0.0])
        self.L_pole = pl["length"]
        self.A = Ph + (self.L_pole + 0.1) * self.pole_dir
        self.B = np.asarray(sp["clew"], float)
        self.Ll = sp["luff_over_chord"] * max(np.linalg.norm(self.H - self.A), np.linalg.norm(self.H - self.B))
        self.W_of = table(sp["girth"])
        self.Gw = sp["girth_of_pole"] * self.L_pole
        self.Fl = sp["foot_of_pole"] * self.L_pole
        if abs(self.W_of(0.0) * self.Gw - self.Fl) > 0.05:
            raise SystemExit("the spinnaker's girth table does not start at its foot")
        # the flat pattern's centre height: its luffs (half the girth out from the centre seam) as long as Ll
        lo, hi = 1.0, 3.0 * self.Ll
        v = np.linspace(0.0, 1.0, 2001)
        for _ in range(80):
            Hc = 0.5 * (lo + hi)
            x = 0.5 * self.Gw * self.W_of(v)
            ln = float(np.sum(np.hypot(np.diff(v * Hc), np.diff(x))))
            if ln > self.Ll:
                hi = Hc
            else:
                lo = Hc
        self.Hc = 0.5 * (lo + hi)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(v * self.Hc), np.diff(0.5 * self.Gw * self.W_of(v))))])
        self.lam_v, self.lam = v, cum / cum[-1]                       # each height's share of the way up the luff

    def width(self, v):
        return self.Gw * self.W_of(v)

    def sheet(self):
        sp = self.sp
        cell = SL["grid"]["spinnaker_cell"]
        nv = int(math.ceil(self.Hc / cell))
        V_ = np.linspace(0.0, 1.0, nv + 1)
        nu = int(math.ceil(self.Gw / cell))
        f = np.linspace(0.0, 1.0, nu + 1)
        H, A, B = self.H, self.A, self.B
        n0 = unit(np.cross(A - H, B - H))
        if n0[0] < 0:
            n0 = -n0                                                   # downwind: forward, out of the boat
        # the luffs: from the tack and the clew up to the head, spread apart (the sail's shoulders) so each girth spans
        # its chord in an arc no deeper than 'arc_ratio' (girth over chord); near the head, where the luffs cannot
        # spread that far within their length, no more than 'head_spread' times their distance down from the head
        lam = np.interp(V_, self.lam_v, self.lam)
        e_ab = unit(A - B)
        c_lin = (1.0 - lam) * float(np.linalg.norm(A - B))
        down = (1.0 - lam) * self.Ll
        c_want = np.minimum(self.width(V_) / sp["arc_ratio"], sp["head_spread"] * down)
        spread = 0.5 * np.maximum(c_want - c_lin, 0.0)
        side = unit(e_ab + sp["shoulder_fwd"] * n0)
        PA = A[None] + lam[:, None] * (H - A)[None] + spread[:, None] * side[None]
        PB = B[None] + lam[:, None] * (H - B)[None] + spread[:, None] * (side - 2 * (side @ e_ab) * e_ab)[None]
        self.luff_len = (float(np.sum(np.linalg.norm(np.diff(PA, axis=0), axis=1))),
                         float(np.sum(np.linalg.norm(np.diff(PB, axis=0), axis=1))))
        G = np.zeros((nu + 1, nv + 1, 3))
        UV = np.zeros((nu + 1, nv + 1, 6))
        for j, v in enumerate(V_):
            W = float(self.width(v))
            pa, pb = PA[j], PB[j]
            c = float(np.linalg.norm(pb - pa))
            if j == nv or W < 1e-6:
                G[:, j] = H
            else:
                e1 = (pb - pa) / c
                bd = n0 + sp["lift"] * (1.0 - v) * EZ
                b = unit(bd - (bd @ e1) * e1)
                ratio = min(max(W / c, 1.0 + 1e-6), sp["max_arc_ratio"])
                lo, hi = 1e-6, math.pi - 1e-6
                for _ in range(80):
                    th = 0.5 * (lo + hi)
                    if th / math.sin(th) < ratio:
                        lo = th
                    else:
                        hi = th
                th = 0.5 * (lo + hi)
                R = c / (2 * math.sin(th))
                M = 0.5 * (pa + pb)
                O = M - R * math.cos(th) * b
                phi = -th + 2 * th * f
                G[:, j] = O[None] + R * (np.sin(phi)[:, None] * e1[None] + np.cos(phi)[:, None] * b[None])
            UV[:, j] = np.stack([f * W, np.full(nu + 1, v * self.Hc), f, np.full(nu + 1, v), (1 - f) * W,
                                 np.abs(f - 0.5) * W], -1)
        self.n0 = n0
        return Sheet(G, V_ * self.Hc, UV, collapse=True), f

    def out_dirs(self, sheet):
        n = sheet.vertex_normals()
        return n * np.sign(np.einsum("ijk,k->ij", n, self.n0))[..., None]

    def fixed(self, sheet):
        fx = np.zeros(sheet.G.shape[:2], bool)
        fx[:, -1] = True
        fx[0, 0] = True
        fx[-1, 0] = True
        return fx

    def area(self):
        v = np.linspace(0.0, 1.0, 2001)
        return float(np.trapezoid(self.width(v), v * self.Hc))

    def dress(self, part, sh):
        r = SL["ropes"]["spinnaker_tape"]
        tube(part, sh.G[0], r, "SailLine", "Spinnaker tape", n=6)
        tube(part, sh.G[-1], r, "SailLine", "Spinnaker tape", n=6)
        tube(part, sh.G[:, 0], r, "SailLine", "Spinnaker tape", n=6)
        for i, j in ((0, 0), (sh.nu, 0)):
            P = sh.G[i, j]
            inward = sh.G[sh.nu // 2, 3] - P
            n_ = sh.normal([i / sh.nu], [0.0])[0]
            torus(part, P + unit(inward) * 0.05, n_, 0.04, 0.01, "Bronze", "Spinnaker cringle", kg=0.4)
        # the head's swivel: a bronze ring and its eye
        P = sh.G[0, -1]
        torus(part, P + EZ * 0.06, EX, 0.035, 0.01, "Bronze", "Spinnaker head swivel")
        box(part, P + EZ * 0.13, EZ, EX, EY, (0.04, 0.015, 0.015), "Bronze", "Spinnaker head swivel")
        # hoisted to its halyard's block, which hangs on a pendant from the masthead crane's tip (the pendant's eye
        # 6 mm under the crane's plate: its shackle through the plate is not modelled)
        cr = spars.M["masthead_crane"]
        top = np.asarray(self.crane, float) - (0.5 * cr["height"] + 0.006) * spars.A
        cb = P + EZ * 0.36
        d = unit(top - cb)
        side = unit(np.cross(d, EX))
        box(part, cb, d, side, np.cross(d, side), (0.08, 0.026, 0.06), "Bronze", "Spinnaker halyard block",
            mass=("solid", BRZ * 0.35))
        tube(part, np.array([P + EZ * 0.15, cb - 0.07 * d]), 0.009, "SailLine", "Spinnaker halyard")
        tube(part, np.array([cb + 0.07 * d, top - 0.02 * d]), 0.008, "Rope", "Spinnaker halyard pendant")
        torus(part, top - 0.035 * d, side, 0.022, 0.006, "Bronze", "Spinnaker halyard pendant eye")


# ------------------------------------------------------------------------------------------------ heaps and bags
def bundle(part, cen, side, up, half_w, half_h, rng, slot, label, lumpy=1.0, floor=None, post=None, n_ring=16):
    """A closed roll or heap of cloth along cen (n, 3): at each station an oval half_w across (along side) and half_h
    high (along up) about it, made lumpy by folds; floor(P) gives, for ring points P (m, 3), the least height each may
    have measured along up (P @ up: a deck's, a boom's top), and points below it are laid on it; post(k, P) may then
    move station k's ring points (a fold drooping over a boom's side). Ends closed. Returns the rings (n, n_ring, 3)."""
    n = len(cen)
    th = np.linspace(0, 2 * math.pi, n_ring, endpoint=False)
    u = np.linspace(0, 1, n)
    c = rng.uniform(0, 2 * math.pi, 6)
    fq = rng.uniform(2.0, 6.0, 3)
    ph1 = 4.0 * np.sin(2 * math.pi * fq[0] * u + c[0])
    ph2 = 4.0 * np.sin(2 * math.pi * fq[1] * u + c[1])
    amp = 1.0 + 0.5 * np.sin(2 * math.pi * fq[2] * u + c[2])
    lump = lumpy * amp[:, None] * (0.07 * np.sin(3 * th[None, :] + ph1[:, None]) +
                                   0.05 * np.sin(5 * th[None, :] + ph2[:, None]) +
                                   0.03 * np.sin(8 * th[None, :] + c[3] + 9 * u[:, None]))
    S = np.broadcast_to(side, (n, 3))
    U = np.broadcast_to(up, (n, 3))
    hw = np.broadcast_to(np.asarray(half_w, float), (n,))
    hh = np.broadcast_to(np.asarray(half_h, float), (n,))
    P = cen[:, None, :] + ((hw[:, None] * np.cos(th)[None]) * (1 + lump))[..., None] * S[:, None, :] + \
        ((hh[:, None] * np.sin(th)[None]) * (1 + lump))[..., None] * U[:, None, :]
    P = np.array(P)
    for k in range(n):
        if floor is not None:
            z0 = floor(P[k])
            h = P[k] @ U[k]
            low = h < z0
            P[k][low] += ((z0 - h)[low])[:, None] * U[k][None]
        if post is not None:
            P[k] = post(k, P[k])
    V = list(P.reshape(-1, 3)) + [cen[0], cen[-1]]
    F = []
    m = n_ring
    for i in range(n - 1):
        for j in range(m):
            a, b = i * m + j, i * m + (j + 1) % m
            F += [(a, b, b + m), (a, b + m, a + m)]
    c0, c1 = n * m, n * m + 1
    for j in range(m):
        F += [(c0, (j + 1) % m, j), (c1, (n - 1) * m + j, (n - 1) * m + (j + 1) % m)]
    part.add(np.array(V), F, slot, label)
    return P


def deck_floor(let=0.003):
    """A floor for a heap on the deck: each point's least height above the heap's own line, from the deck under it
    (points with their (x, y) over the deck), the heap let `let` into it."""
    def fl(P):
        return shell.deck_z(P[:, 0], P[:, 1]) - let
    return fl


def gasket(part, P3, axis, r, gap=0.004, slot="SailLine", label="Sail tie"):
    """A tie of radius r round the convex hull of the points P3, square to axis, gap clear all round."""
    axis = unit(axis)
    a = unit(np.cross(axis, EZ if abs(axis @ EZ) < 0.9 else EX))
    b = np.cross(axis, a)
    c0 = P3.mean(0)
    Q = np.stack([(P3 - c0) @ a, (P3 - c0) @ b], 1)
    H = Q[ConvexHull(Q).vertices]
    d = r + gap
    path = []
    for i in range(len(H)):
        e0, e1 = H[i] - H[i - 1], H[(i + 1) % len(H)] - H[i]
        a0, a1 = math.atan2(-e0[0], e0[1]), math.atan2(-e1[0], e1[1])
        if a1 < a0:
            a1 += 2 * math.pi
        for ang in np.linspace(a0, a1, max(2, int((a1 - a0) / 0.25) + 2)):
            path.append(H[i] + d * np.array([math.cos(ang), math.sin(ang)]))
    path = np.array(path)
    keep = [0]
    for k in range(1, len(path)):
        if np.linalg.norm(path[k] - path[keep[-1]]) > 0.012:
            keep.append(k)
    path = path[keep]
    if np.linalg.norm(path[-1] - path[0]) < 0.012:
        path = path[:-1]
    s = ((P3 - c0) @ axis).mean()
    P = c0[None] + path[:, :1] * a[None] + path[:, 1:] * b[None] + s * axis
    tube(part, P, r, slot, label, n=6, closed=True)
    return float(np.sum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)))


def polyline_stations(plan, step):
    """Stations every ~step along a plan polyline [(x, y)], with the unit direction at each."""
    P = np.asarray(plan, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    s = np.linspace(0.0, cum[-1], max(int(cum[-1] / step), 2) + 1)
    X = np.interp(s, cum, P[:, 0])
    Y = np.interp(s, cum, P[:, 1])
    Q = np.stack([X, Y], 1)
    d = np.gradient(Q, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    return Q, d, s


def deck_heap(part, plan, volume, width, rng, slot, label, lumpy=1.6, step=0.12, taper=0.25, bag=False, dry=False):
    """A heap (or a bag) of cloth lying on the deck along the plan polyline: 0.6 as high as it is wide at most,
    `width` across where the deck allows (in from the toe rail by 0.2 m), its bulk `volume` (less where the height is
    capped), its ends tapered over `taper` of its length (a bag's ends rounded). dry: only the volume it would hold."""
    Q, d, s = polyline_stations(plan, step)
    Ls = float(s[-1])
    x = Q[:, 0]
    hb = deck_hb(x)
    w = np.minimum(width, 2 * (hb - np.abs(Q[:, 1]) - 0.2))
    if (w < 0.15).any():
        raise SystemExit(f"{label}: the heap does not fit on the deck at x {x[w < 0.15]}")
    sh = s / Ls
    end = np.minimum(sh, 1 - sh) / taper
    prof = np.sqrt(np.clip(1 - (1 - np.clip(end, 0, 1)) ** 2, 0.02, 1.0)) if bag else 0.35 + 0.65 * smooth01(end)
    w = w * (prof if bag else np.clip(prof, 0.35, 1.0))
    # sections ~ ellipses: area = pi/4 w h, following the ends' profile; heights fill the volume, no more than 0.6 of
    # the width
    area = volume / (step * float(np.sum(prof))) * prof
    hgt = np.minimum(area / (math.pi / 4 * np.maximum(w, 1e-3)), 0.6 * w)
    if dry:
        return float(np.sum(math.pi / 4 * w * hgt) * step)
    z = shell.deck_z(x, Q[:, 1])
    cen = np.stack([x, Q[:, 1], z + 0.5 * hgt - 0.003], 1)
    side = np.stack([-d[:, 1], d[:, 0], np.zeros(len(d))], 1)
    P = bundle(part, cen, side, EZ, 0.5 * w, 0.5 * hgt, rng, slot, label, lumpy=lumpy, floor=deck_floor())
    vol = float(np.sum(math.pi / 4 * w * hgt) * step)
    return P, cen, w, hgt, vol


def bag_width(plan, volume, taper=0.12):
    """The width a bag along the plan needs to hold `volume` (its height capped at 0.6 of its width, its ends rounded:
    98% of it, since the cap always binds at the very ends)."""
    lo, hi = 0.05, 2.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if deck_heap(None, plan, volume, mid, None, None, None, taper=taper, bag=True, dry=True) < 0.98 * volume:
            lo = mid
        else:
            hi = mid
    return hi


def deck_hb(x):
    xc = np.clip(np.asarray(x, float), *shell.DECK_X)
    return loft.DECK_HB(xc)


# ------------------------------------------------------------------------------------------------ build
_SURF = {}


def obstacle_points(sources, box_lo, box_hi, step=0.03):
    """Surface points of the obstacle meshes inside the box, one to each cube of side `step`: sources [(V, F)] in the
    hull's frame (each mesh sampled once and kept)."""
    out = []
    for V, F in sources:
        key = (id(V), step)
        if key not in _SURF:
            _SURF[key] = (V, surface_points(V, F, step))           # V kept with its points, so its id stays its own
        P = _SURF[key][1]
        P = P[np.all((P > box_lo) & (P < box_hi), axis=1)]
        if len(P):
            out.append(P)
    if not out:
        return np.zeros((0, 3))
    P = np.concatenate(out)
    _, keep = np.unique(np.floor(P / step).astype(np.int64), axis=0, return_index=True)
    return P[np.sort(keep)]


def sub_mesh(p, keep):
    """The faces of part p (V, F, labels) whose label and centre pass keep(label, centre), with only their vertices:
    (V, F), or None."""
    V = np.asarray(p.V, float)
    labels = getattr(p, "labels", None) or [p.name] * len(p.F)
    F = [f for f, lab in zip(p.F, labels) if keep(lab, V[list(f)].mean(0))]
    if not F:
        return None
    used = sorted({i for f in F for i in f})
    m = {i: k for k, i in enumerate(used)}
    return V[used], [tuple(m[i] for i in f) for f in F]


def obstacles_from(hull_parts, sp_parts, rg_parts):
    """The obstacles the sails are pressed off and checked against, from the parts built so far (hull's frame, at
    rest): {'boom', 'pole', 'mast_tube' (the mast and what hugs it), 'crane', 'rig_port', 'rig_starboard' (each
    side's shrouds, spreaders, jumper struts and stays, and its runners' fittings), 'forestay', 'staysail_stay',
    'backstay', 'runners' {state: ...}, 'hull'}: lists of (V, F); 'boom_frame' the boom's frame."""
    def side_of(lab, c, out=0.15):
        if "starboard" in lab:
            return "starboard"
        if "port" in lab:
            return "port"
        if abs(c[1]) > out:
            return "starboard" if c[1] > 0 else "port"
        return None

    def add(d, k, vf):
        if vf is not None:
            d.setdefault(k, []).append(vf)
    obs = {}
    mast = sp_parts["Mast"]
    sided = ("Spreaders", "Spreader tips", "Jumper struts", "Jumper strut tips")
    add(obs, "crane", sub_mesh(mast, lambda lab, c: lab in ("Masthead crane", "Truck", "Masthead band")))
    add(obs, "mast_tube", sub_mesh(mast, lambda lab, c: lab not in sided or side_of(lab, c) is None))
    for side in ("port", "starboard"):
        add(obs, f"rig_{side}", sub_mesh(mast, lambda lab, c, side=side: lab in sided and side_of(lab, c) == side))
        for k in ("Shrouds", "RunnerFittings"):
            add(obs, f"rig_{side}", sub_mesh(rg_parts[k], lambda lab, c, side=side: side_of(lab, c, 1e9) == side))
        add(obs, f"rig_{side}", sub_mesh(rg_parts["Stays"], lambda lab, c, side=side: lab.startswith(
            f"Jumper stay, {side}")))
    add(obs, "mast_tube", sub_mesh(rg_parts["Shrouds"], lambda lab, c: side_of(lab, c, 1e9) is None))
    for k, name in (("forestay", "Forestay"), ("staysail_stay", "Staysail stay"), ("backstay", "Backstay")):
        add(obs, k, sub_mesh(rg_parts["Stays"], lambda lab, c, name=name: lab.split(" |")[0] == name))
    obs["runners"] = {k: [(np.asarray(rg_parts[k].V, float), rg_parts[k].F)] for k in rigging.STATES}
    obs["hull"] = [(np.asarray(p.V, float), p.F) for p in hull_parts]
    obs["boom"] = [(np.asarray(sp_parts["Boom"].V, float), sp_parts["Boom"].F)]
    obs["pole"] = [(np.asarray(sp_parts["SpinnakerPole"].V, float), sp_parts["SpinnakerPole"].F)]
    obs["boom_frame"] = sp_parts["Boom"].frame
    return obs


def pole_stowed(pts, pole_vfs):
    """The spinnaker pole unshipped and lashed down on the deck (SL 'pole_stowed'): its heel pin over the plan point
    'heel', the pole lying toward 'toward', pitched to the deck's chord under it and let down until its lowest point
    is 'gap' above the deck. pole_vfs: the pole as built [(V, F)]. Returns (R, t), taking the pole as built to it stowed
    (p -> R p + t, hull's frame), and a report."""
    ps = SL["pole_stowed"]
    pl = spars.RG["pole"]
    L = pl["length"]
    Ph = np.asarray(pts["pole_heel_pin"], float)
    a = np.asarray(ps["heel"], float)
    up_ = unit(np.asarray(ps["toward"], float) - a)
    b = a + L * up_
    za, zb = (float(shell.deck_z(np.array([q[0]]), np.array([q[1]]))[0]) for q in (a, b))
    pitch = math.atan2(zb - za, L)
    u = np.array([up_[0] * math.cos(pitch), up_[1] * math.cos(pitch), math.sin(pitch)])
    z_ = unit(EZ - (EZ @ u) * u)
    y_ = np.cross(z_, u)
    phi = math.radians(pl["set_deg"])
    X0 = np.array([math.cos(phi), math.sin(phi), 0.0])
    R = np.stack([u, y_, z_], 1) @ np.stack([X0, np.cross(EZ, X0), EZ], 0)
    t = np.array([a[0], a[1], za]) - R @ Ph
    V = np.concatenate([np.asarray(V, float) for V, F in pole_vfs]) @ R.T + t
    least = float(np.min(V[:, 2] - shell.deck_z(V[:, 0], V[:, 1])))
    t = t + (ps["gap"] - least) * EZ
    V = V + (ps["gap"] - least) * EZ
    hb = deck_hb(V[:, 0]) - np.abs(V[:, 1])
    rep = {"heel_pin": [round(float(v), 3) for v in R @ Ph + t], "end": [round(float(v), 3) for v in R @ (Ph + L * X0) + t],
           "pitch_deg": round(math.degrees(pitch), 2), "least_above_deck_m": ps["gap"],
           "least_inboard_of_deck_edge_m": round(float(hb.min()), 3), "R": R.round(6).tolist(),
           "t": t.round(5).tolist()}
    if hb.min() < 0.3:
        raise SystemExit(f"the stowed pole comes within {hb.min():.2f} m of the deck's edge: lay it further inboard")
    return R, t, rep


def build(rig, pts, rr, obs):
    """{object name: SailPart} and a report. obs: obstacles_from()'s, the obstacles for the press."""
    clr = SL["press"]["clear"]
    spread, rounds = SL["press"]["spread"], SL["press"]["rounds"]
    parts, rep = {}, {"sails": {}, "press": {}, "trim": {}, "suits": SL["suits"]}
    main = Mainsail(pts, rig)
    bg = main.bg

    def posed(VFs, R, o):
        return [(o[None] + (np.asarray(V, float) - o[None]) @ R.T, F) for V, F in VFs]

    def pole_pose(deg, heel):
        dz = (heel - spars.RG["pole"]["heel_above_deck"]) / math.cos(spars.RAKE)
        Ph = np.asarray(pts["pole_heel_pin"], float)
        # the pole is built set_deg to starboard; turn it about the vertical through its heel to deg, then raise it
        R = rot(EZ, math.radians(deg - spars.RG["pole"]["set_deg"]))
        return [(Ph[None] + (np.asarray(V, float) - Ph[None]) @ R.T + dz * spars.A[None], F) for V, F in obs["pole"]]

    stow_R, stow_t, rep["pole_stowed"] = pole_stowed(pts, obs["pole"])

    def suit_pole(name):
        su = SL["suits"][name]
        if su.get("pole") == "stowed":
            return [(np.asarray(V, float) @ stow_R.T + stow_t[None], F) for V, F in obs["pole"]]
        return pole_pose(su["pole_deg"], su["pole_heel_above_deck"])

    starboard = ("Runner.Starboard.Set", "Runner.Port.LetOff", "Checkstay.Starboard.Set", "Checkstay.Port.LetOff")
    runners = [vf for k in starboard for vf in obs["runners"][k]]

    def new(name, sail, state, frame=None):
        p = SailPart(name, frame, sail, state)
        parts[name] = p
        return p

    # -- the mainsail: set close-hauled and squared off for the run
    room = main.backstay_room(stay_of(rr, "Backstay"))
    if room["least_m"] < main.sp["backstay_clear"]:
        raise SystemExit(f"the mainsail's roach comes within {room['least_m']} m of the backstay amidships "
                         f"(at z {room['at_z_m']}): less roach or a narrower headboard")
    sheets = {}
    for trim in ("Set", "Run"):
        sh, f = main.sheet(trim)
        psi = main.sp["trims"][trim]["boom_deg"]
        R_b = rot(bg["Zb"], math.radians(psi))
        lo, hi = sh.G.reshape(-1, 3).min(0) - 1.5, sh.G.reshape(-1, 3).max(0) + 1.5
        if trim == "Set":
            # close-hauled: only the windward runner and checkstay and the backstay could come near (they must stay
            # on the cloth's windward side); everything to leeward is checked by the build, not pressed
            src = [vf for k in ("Runner.Starboard.Set", "Checkstay.Starboard.Set") for vf in obs["runners"][k]]
            src += obs["backstay"]
            ob = [(obstacle_points(src, lo, hi), clr["rig"], "windward runner, checkstay, backstay", 1)]
            push = main.lee_dirs(sh, trim)
        else:
            # squared off: the lee shrouds, spreaders and the let-off runner and checkstay hold the cloth back
            src = obs["rig_port"] + [vf for k in ("Runner.Port.LetOff", "Checkstay.Port.LetOff")
                                     for vf in obs["runners"][k]]
            ob = [(obstacle_points(src, lo, hi), clr["rig"], "lee shrouds, spreaders, let-off runner", 1)]
            push = -main.lee_dirs(sh, trim)
        rep["press"][f"Mainsail.{trim}"] = press(sh, push, ob, main.fixed(sh), spread, rounds, reach=0.8,
                                                 label=f"Mainsail.{trim}")
        sheets[f"Mainsail.{trim}"] = sh
        p = new(f"Mainsail.{trim}", "Mainsail", trim)
        p.pose = {"boom_deg_to_port": psi}
        V, F, U = sh.mesh()
        p.add(V, F, "ClothMainsail", "Mainsail cloth", uv=U, orient=False)
        p.free = sh.free_vertices(main.fixed(sh))
        main.dress(p, sh, trim, R_b)
    # -- the mainsail lowered and flaked on the boom (the boom's frame), and its luff's stack on the mast
    area_m = main.area()
    cm = SL["cloth"]["main"]
    boomV = np.concatenate([np.asarray(V, float) for V, F in obs["boom"]])
    for state in ("Lowered", "Flaked"):
        st = main.sp["stow"][state]
        p = new(f"Mainsail.{state}", "Mainsail", state, frame=obs["boom_frame"])
        main.slides_foot(p, np.eye(3))
        tube(p, np.array([main.T0 + t * bg["D"] for t in (0.0, main.xC)]), SL["ropes"]["main_bolt"], "Rope",
             "Mainsail bolt rope")
        t0, t1 = st["from"], st["to"] * main.xC
        ts = np.linspace(t0, t1, max(int((t1 - t0) / 0.12), 2) + 1)
        vol = area_m * cm["thick_mm"] / 1000 * st["packing"]
        wa, wb = st["width"]
        w = wa + (wb - wa) * (ts - t0) / (t1 - t0)
        h = vol / (t1 - t0) * w / np.mean(w) / (math.pi / 4 * w)
        h = np.minimum(h, 0.9 * w)
        base = bg["top0"] + (main.t_T + ts)[:, None] * bg["D"][None]
        floor_h = SL["mainsail"]["foot_off"] + SL["ropes"]["main_bolt"] + 0.004
        cen = base + (floor_h + 0.5 * h)[:, None] * bg["N"][None]
        bw_half = 0.5 * spars.RG["boom"]["section_mid"][1]
        droop = st["droop"]

        def floor(P, base=base):
            # no lower than the foot's rope over the boom's top (the heap's own station's height)
            k = int(np.argmin(np.linalg.norm(base - P.mean(0)[None], axis=1)))
            return np.full(len(P), base[k] @ bg["N"] + floor_h)

        def post(k, P, cen=cen):
            # beyond the boom's sides the folds hang down over it
            rel = P - cen[k]
            yy = np.abs(rel @ EY)
            below = rel @ bg["N"] < 0
            d = droop * smooth01((yy - bw_half - 0.03) / 0.18)
            return P - (d * below)[:, None] * bg["N"][None]
        rng = np.random.default_rng(seed_of(f"Mainsail.{state}"))
        ring = bundle(p, cen, EY, bg["N"], 0.5 * w, 0.5 * h, rng, "SailHeap", f"Mainsail {state.lower()}",
                      lumpy=st["lumpy"], floor=floor, post=post)
        if state == "Flaked":
            for t in np.arange(t0 + 0.5, t1 - 0.2, st["tie_every"]):
                k = int(np.argmin(np.abs(ts - t)))
                c = base[k]
                # round the heap and the boom's section there (its points within 0.3 m along it: the rings of its
                # skin are farther apart than a tie is wide)
                sl_ = np.abs((boomV - c) @ bg["D"]) < 0.3
                if sl_.sum() < 24:
                    raise SystemExit(f"a sail tie at {t:.2f} m along the boom finds only {sl_.sum()} of its points")
                gasket(p, np.concatenate([ring[k], boomV[sl_]]), bg["D"], SL["ropes"]["sail_tie"])
    stk = new("Mainsail.Stack", "Mainsail", "Stack")
    stack_h = main.stack(stk)
    # -- the headsails: the staysail first (the quadrilateral jib is set outside it), then the jibs
    hs = {k: Headsail(k, rr) for k in ("staysail", "quadrilateral", "genoa")}
    beat_R = rot(bg["Zb"], math.radians(SL["suits"]["Genoa"]["boom_deg"]))
    beat_boom = posed(obs["boom"], beat_R, bg["G"])
    beat_pole = suit_pole("Genoa")
    main_set = sheets["Mainsail.Set"]
    Mpts = main_set.G.reshape(-1, 3)
    for key in ("staysail", "quadrilateral", "genoa"):
        h_ = hs[key]
        name = {"staysail": "Staysail", "quadrilateral": "Quadrilateral", "genoa": "Genoa"}[key]
        sh0, _ = h_.sheet()
        lo, hi = sh0.G.reshape(-1, 3).min(0) - 2.5, sh0.G.reshape(-1, 3).max(0) + 2.5
        # The staysail sets inside the rigging: to windward of it the mast, the boom and the mainsail; to leeward the lee
        # shrouds. The genoa and the quadrilateral jib, whose leeches reach well abaft the mast, are sheeted outside
        # the rigging to the rail (the chainplates are on the rail, so an overlapping headsail cannot pass inside the
        # shrouds and the spreaders): the whole rig, both runners, the staysail stay (and the staysail), the boom, the
        # pole, the mainsail and the rail are to windward of them.
        runs = [vf for k in starboard for vf in obs["runners"][k]]
        if key == "staysail":
            inside = obs["mast_tube"] + obs["rig_starboard"] + beat_boom + \
                [vf for k in ("Runner.Starboard.Set", "Checkstay.Starboard.Set") for vf in obs["runners"][k]]
            outside = obs["rig_port"] + [vf for k in ("Runner.Port.LetOff", "Checkstay.Port.LetOff")
                                         for vf in obs["runners"][k]]
        else:
            inside = obs["mast_tube"] + obs["crane"] + obs["rig_port"] + obs["rig_starboard"] + runs + \
                obs["staysail_stay"] + beat_boom + beat_pole
            outside = []
        ob = [(obstacle_points(inside, lo, hi), clr["rig"], "rig", 1),
              (Mpts[np.all((Mpts > lo) & (Mpts < hi), axis=1)], clr["sail"], "mainsail", 1),
              (obstacle_points(obs["hull"], lo, hi, step=0.06), clr["hull"], "hull and deck",
               -1 if key == "staysail" else 1)]
        if outside:
            ob.append((obstacle_points(outside, lo, hi), clr["rig"], "lee rigging", -1))
        if key == "quadrilateral":
            ob.append((sheets["Staysail.Set"].G.reshape(-1, 3), clr["sail"], "staysail", 1))
        # sheet each row in or out so the cloth passes between them, then press what is left
        lee_p = obstacle_points(outside, lo, hi) if outside else np.zeros((0, 3))
        in_p = np.concatenate([o[0] for o in ob if o[3] == 1 and o[2] != "hull and deck"])
        sh, f = h_.sheet(lee_p, in_p, clear=2.0 * clr["rig"])
        rep["trim"][f"{name}.Set"] = h_.trim_rep
        if h_.trim_rep["rows_without_room"]:
            raise SystemExit(f"the {name}'s rows cannot pass between the rigging inside it and outside it within the "
                             f"trim's reach: {h_.trim_rep}")
        rep["press"][f"{name}.Set"] = press(sh, h_.lee_dirs(sh), ob, h_.fixed(sh), spread, rounds, reach=1.0,
                                             label=f"{name}.Set")
        sheets[f"{name}.Set"] = sh
        p = new(f"{name}.Set", name, "Set")
        p.pose = {"boom_deg_to_port": SL["suits"]["Genoa"]["boom_deg"]}
        V, F, U = sh.mesh()
        p.add(V, F, f"Cloth{name}", f"{name} cloth", uv=U, orient=False)
        p.free = sh.free_vertices(h_.fixed(sh))
        h_.dress(p, sh)
    # lowered (on deck, still hanked on) and bagged
    bags = {}
    for key, h_ in hs.items():
        name = {"staysail": "Staysail", "quadrilateral": "Quadrilateral", "genoa": "Genoa"}[key]
        sp = h_.sp
        cl = SL["cloth"]["headsail"]
        area = h_.area()
        rng = np.random.default_rng(seed_of(f"{name}.Lowered"))
        p = new(f"{name}.Lowered", name, "Lowered")
        n_h = int(round(float(np.linalg.norm(h_.H - h_.T)) / SL["headsails"]["hank_every"]))
        h_.hanks(p, 0.12 + np.arange(n_h) * 0.042)
        top = h_.T + (0.12 + n_h * 0.042) * h_.u
        lp = np.array([h_.T - 0.05 * h_.u, top]) + 0.03 * h_.pa
        tube(p, lp, 0.05, "SailHeap", f"{name} luff bunched", n=10)
        deck_heap(p, sp["heap"], area * cl["thick_mm"] / 1000 * sp["heap_packing"], sp["heap_width"], rng,
                  "SailHeap", f"{name} lowered", lumpy=2.0)
        p = new(f"{name}.Bagged", name, "Bagged")
        rng = np.random.default_rng(seed_of(f"{name}.Bagged"))
        bag_vol = area * cl["thick_mm"] / 1000 * sp["bag_packing"]
        *_, held = deck_heap(p, sp["bag"], bag_vol, bag_width(sp["bag"], bag_vol), rng, "SailBag", f"{name} bag",
                             lumpy=0.35, taper=0.12, bag=True)
        bags[name] = {"cloth_m3": round(area * cl["thick_mm"] / 1000, 3), "bag_m3": round(held, 3)}
    # -- the spinnaker, set with the mainsail squared off, and bagged
    spn = Spinnaker(pts, rig)
    sh, f = spn.sheet()
    if max(abs(x - spn.Ll) for x in spn.luff_len) > 0.01 * spn.Ll:
        raise SystemExit(f"the spinnaker's luffs as set are {[round(x, 2) for x in spn.luff_len]} m against "
                         f"{round(spn.Ll, 2)} cut: move its clew")
    run_pole = suit_pole("Spinnaker")
    Vr = np.concatenate([V for V, F in run_pole])
    tip = Vr[int(np.argmax(Vr @ spn.pole_dir))]
    if np.linalg.norm(tip - (spn.A - 0.1 * spn.pole_dir)) > 0.03:
        raise SystemExit(f"the pole as posed ends at {tip.round(3)}, not under the spinnaker's tack at "
                         f"{(spn.A - 0.1 * spn.pole_dir).round(3)}: the pole's turn is the wrong way")
    lo, hi = sh.G.reshape(-1, 3).min(0) - 1.5, sh.G.reshape(-1, 3).max(0) + 1.5
    src = obs["mast_tube"] + obs["crane"] + obs["rig_port"] + obs["rig_starboard"] + obs["forestay"] + \
        obs["staysail_stay"] + runners + run_pole
    ob = [(obstacle_points(src, lo, hi), clr["rig"], "rig", 1),
          (obstacle_points(obs["hull"], lo, hi, step=0.06), clr["hull"], "hull and deck", 1)]
    rep["press"]["Spinnaker.Set"] = press(sh, spn.out_dirs(sh), ob, spn.fixed(sh), spread, rounds, reach=1.5,
                                         label="Spinnaker.Set")
    sheets["Spinnaker.Set"] = sh
    p = new("Spinnaker.Set", "Spinnaker", "Set")
    p.pose = {"boom_deg_to_port": SL["suits"]["Spinnaker"]["boom_deg"], "pole_deg": spn.sp["pole_deg"],
              "pole_heel_above_deck": spn.sp["pole_heel_above_deck"]}
    V, F, U = sh.mesh()
    p.add(V, F, "ClothSpinnaker", "Spinnaker cloth", uv=U, orient=False)
    p.free = sh.free_vertices(spn.fixed(sh))
    spn.dress(p, sh)
    p = new("Spinnaker.Bagged", "Spinnaker", "Bagged")
    rng = np.random.default_rng(seed_of("Spinnaker.Bagged"))
    cs = SL["cloth"]["spinnaker"]
    bag_vol = spn.area() * cs["thick_mm"] / 1000 * spn.sp["bag_packing"]
    *_, held = deck_heap(p, spn.sp["bag"], bag_vol, bag_width(spn.sp["bag"], bag_vol), rng, "SailBag", "Spinnaker bag",
                         lumpy=0.35, taper=0.12, bag=True)
    bags["Spinnaker"] = {"cloth_m3": round(spn.area() * cs["thick_mm"] / 1000, 3), "bag_m3": round(held, 3)}
    rep["bags"] = bags
    # -- each sail's measures, cut and weight (its set state's fittings; cloth by area at its weight, with 'finish'
    # added for tablings, linings and patches; ropes and tapes by length)
    cl, ro = SL["cloth"], SL["ropes"]

    def cloth_kg(area, kind):
        c = cl[kind]
        return area / cl["sailmakers_yard_m2"] * c["oz"] * OZ_G / 1000.0 * (1.0 + c["finish"])

    def fit_kg(name):
        return sum(m["kg"] for m in parts[name].masses)
    sr = {}
    m_luff, m_foot = float(main.s_H - main.s_T), float(main.xC)
    s_band = spars.S_TOP - spars.M["black_band"]["below_top"]
    # the rule's limits, measured on the set sails' meshes as built (their fittings too): the mainsail's highest point
    # up the mast below the black band's lower edge, its farthest aft along the boom inside the boom's band; each
    # jib's highest point below the forestay's hounds; the pole's end, set fore and aft, no farther from the mast's
    # forward face than J
    Vm = np.asarray(parts["Mainsail.Set"].V, float)
    rel = Vm - spars.P0[None]
    s_m = rel @ spars.A
    off_axis = np.linalg.norm(rel - s_m[:, None] * spars.A[None], axis=1)
    head_room = float(s_band - s_m[off_axis < 1.0].max())
    R_set = rot(bg["Zb"], math.radians(main.sp["trims"]["Set"]["boom_deg"]))
    Vb = bg["G"][None] + (Vm - bg["G"][None]) @ R_set                     # back on the boom at rest
    relb = Vb - bg["top0"][None]
    t_m = relb @ bg["D"]
    off_boom = np.linalg.norm(relb - t_m[:, None] * bg["D"][None], axis=1)
    clew_room = float(bg["t_a"] + bg["E"] - t_m[off_boom < 1.0].max())
    pl = spars.RG["pole"]
    s_c = spars.s_at(pl["heel_above_deck"])
    face_x = float(spars.at(s_c, spars.half_depth(s_c))[0])
    pole_reach = float(max(np.asarray(V, float)[:, 0].max() for V, F in pole_pose(0.0, pl["heel_above_deck"]))) - face_x
    a_m = main.area()
    em = main.sp["emblem"]
    ey = em["at"][1] * main.yH
    sr["Mainsail"] = {"kind": "main", "cloth": "main", "area_m2": round(a_m, 1), "area_ft2": round(a_m / FT ** 2, 0),
                      "roach_m2": round(main.roach_area(), 1), "luff_m": round(m_luff, 3), "foot_m": round(m_foot, 3),
                      "leech_line_m": round(main.leech_len, 3), "head_y_m": round(main.yH, 3),
                      "head_below_band_m": main.sp["head_below_band"], "head_below_band_as_built_m": round(head_room, 4),
                      "clew_inside_band_as_built_m": round(clew_room, 4), "within_P": bool(head_room >= 0.0),
                      "within_E": bool(clew_room >= 0.0), "reefs_m": main.sp["reefs"],
                      "luff_slides": main.slides_count(), "foot_slides": len(main.foot_ts()),
                      "emblem": {"at": [round(float(em["at"][0] * (main.xE(ey) - main.xL(ey))), 3), round(float(ey), 3)],
                                 "radius_m": em["radius"]},
                      "cloth_kg": round(cloth_kg(a_m, "main"), 1),
                      "ropes_kg": round((m_luff + m_foot) * ro["bolt_kg_per_m"], 1),
                      "fittings_kg": round(fit_kg("Mainsail.Set"), 1)}
    I_z = float(np.asarray(pts["forestay_hounds"], float)[2])
    for key, h_ in hs.items():
        name = {"staysail": "Staysail", "quadrilateral": "Quadrilateral", "genoa": "Genoa"}[key]
        a_h = h_.area()
        luff = float(np.linalg.norm(h_.H - h_.T))
        o = h_.outline()
        sr[name] = {"kind": "mitre", "cloth": "headsail", "stay": h_.stay_name, "area_m2": round(a_h, 1),
                    "area_ft2": round(a_h / FT ** 2, 0), "luff_m": round(luff, 3),
                    "foot_m": round(float(np.linalg.norm(o[1] - o[0])), 3),
                    "leech_m": round(float(np.sum(np.linalg.norm(np.diff(o[1:], axis=0), axis=1))), 3),
                    "lp_m": round(h_.lp(), 3), "head_y_m": round(h_.yH, 3),
                    "head_z_m": round(float(h_.H[2]), 3),
                    "highest_z_as_built_m": round(float(np.asarray(parts[f"{name}.Set"].V, float)[:, 2].max()), 3),
                    "forestay_hounds_z_m": round(I_z, 3),
                    "head_below_forestay_hounds": bool(np.asarray(parts[f"{name}.Set"].V, float)[:, 2].max() <= I_z),
                    "hanks": len(np.arange(0.35, luff - 0.1, SL["headsails"]["hank_every"])),
                    "cloth_kg": round(cloth_kg(a_h, "headsail"), 1), "ropes_kg": round(luff * ro["bolt_kg_per_m"], 1),
                    "fittings_kg": round(fit_kg(f"{name}.Set"), 1), "trim": rep["trim"].get(f"{name}.Set")}
        if h_.quad:
            sr[name]["upper_clew_y_m"] = round(float(h_.UCf[1]), 3)
            sr[name]["lower_clew_x_m"] = round(float(h_.LCf[0]), 3)
    a_s = spn.area()
    sr["Spinnaker"] = {"kind": "spin", "cloth": "spinnaker", "area_m2": round(a_s, 1), "area_ft2": round(a_s / FT ** 2, 0),
                       "luff_m": round(spn.Ll, 3), "luffs_as_set_m": [round(x, 3) for x in spn.luff_len],
                       "foot_m": round(spn.Fl, 3), "widest_girth_m": round(spn.Gw, 3), "head_y_m": round(spn.Hc, 3),
                       "pole_m": spn.L_pole, "pole_reach_from_mast_face_as_built_m": round(pole_reach, 3),
                       "J_m": rig["measures"]["J_m"], "pole_within_J": bool(pole_reach <= rig["measures"]["J_m"]),
                       "cloth_kg": round(cloth_kg(a_s, "spinnaker"), 1),
                       "ropes_kg": round((2 * spn.Ll + spn.Fl) * ro["tape_kg_per_m"], 1),
                       "fittings_kg": round(fit_kg("Spinnaker.Set"), 1)}
    for v in sr.values():
        v["total_kg"] = round(v["cloth_kg"] + v["ropes_kg"] + v["fittings_kg"], 1)
    tot = sum(v["total_kg"] for v in sr.values())
    rep["sails"] = sr
    rep["wardrobe"] = {"sails": list(sr), "total_kg": round(tot, 1), "total_long_tons": round(tot / deck.LT_KG, 3),
                       "card_long_tons": loft.SPECS["weights"]["sails_aboard"],
                       "note": "the five sails built; the size card's 'sails_aboard' stands for her whole wardrobe "
                               "(spare and light-weather sails too), so it stays the weight check's estimate"}
    rep["_sheets"] = sheets
    rep["_main"], rep["_headsails"], rep["_spinnaker"] = main, hs, spn
    rep["stack_height_m"] = round(stack_h, 3)
    rep["backstay_room"] = room
    return parts, rep
