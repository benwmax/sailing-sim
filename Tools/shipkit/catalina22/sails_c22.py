"""The Catalina 22's sails from sails_c22.json, on slice 4's rig (rig_c22): cloth grids, their states' shapes and the
checks. Numpy only, no Blender (docs/c22-6). build_sails_c22.py meshes them.

    python3 -I sails_c22.py          prints each sail's sizes, areas and clearances; fails on a sail off its area by
                                     more than 5%, or any set sail closer than 1 cm to a wire, the mast or the deck

A set sail is a Sheet: rows j = 0..nv up the sail, each of nu + 1 points from the luff (i = 0) to the leech; G is the
(nu + 1, nv + 1, 3) grid in the game's frame (X forward, Y starboard, Z up, metres) and UV its (nu + 1, nv + 1, 6)
texture coordinates, as the game's sail cloth reads them (Source/SailingSim/Public/SailCloth.h, the J-Class's
sails.py): UV0 metres (along the row from the luff, up from the foot, flat), UV1 the planform normalized (0..1 both
ways), UV2.x metres along the row from the leech, UV2.y the distance in from the leech's straight line (the spinnaker:
from its centre seam). Rows run parallel to the foot. A working sail's cloth faces starboard (windward on starboard
tack), the spinnaker's aft.

Sails and states (build_sails_c22.py builds one object per sail and state):
  Main     Set (close-hauled), Run (squared off under the spinnaker), Reefed (one reef tied in), Flaked (on the boom,
           tied), Covered (flaked under its cover)
  Jib      the working jib (90%: sails_c22.json says why): Set, Lowered (in a heap on the foredeck, still hanked on),
           Bagged
  Genoa    the high-cut genoa (140% LP, tack pennant): Set, Lowered, Bagged
  Spinnaker  Set (on a run, with its pole), Bagged
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck_c22 as D  # noqa: E402
import hull_c22 as H  # noqa: E402
import rig_c22 as RC  # noqa: E402

S = json.load(open(os.path.join(HERE, "sails_c22.json")))
MS, HS, SP, CL = S["mainsail"], S["headsails"], S["spinnaker"], S["cloth"]
P_M, E_M, J_M = RC._card("P_m"), RC._card("E_m"), RC._card("J_m")
CLEAR = 0.01                     # the least gap a set sail keeps to a wire, the mast or the deck (the check's floor)
PRESS = 0.025                    # what press() aims for, so the check passes with room


# ------------------------------------------------------------------ small helpers

def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def table(tab):
    t = np.asarray(tab, float)
    return lambda x: np.interp(x, t[:, 0], t[:, 1])


def camber(f, p):
    """The camber line, 1 at its deepest (f = p), 0 at both ends (the NACA four-digit mean line's shape)."""
    f = np.asarray(f, float)
    p = np.asarray(p, float)
    return np.where(f < p, (2 * p * f - f * f) / (p * p), ((1 - 2 * p) + 2 * p * f - f * f) / ((1 - p) ** 2))


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def rotate(v, axis, ang):
    """Vectors v (..., 3) turned ang (radians, right-handed) about the unit axis."""
    k = unit(axis)
    v = np.asarray(v, float)
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(k, v) * s + np.outer(v @ k, k).reshape(v.shape) * (1 - c)


def blur(a, passes=2):
    """A light blur over a grid's both axes (edges held to themselves), for press's push."""
    a = np.asarray(a, float)
    for _ in range(passes):
        b = a.copy()
        b[1:-1, :] = 0.25 * a[:-2, :] + 0.5 * a[1:-1, :] + 0.25 * a[2:, :]
        c = b.copy()
        c[:, 1:-1] = 0.25 * b[:, :-2] + 0.5 * b[:, 1:-1] + 0.25 * b[:, 2:]
        a = c
    return a


def floor_z(x, y):
    """What lies under (x, y): the deck, or the cabin trunk's top and sides where it stands (pop-top closed)."""
    hb = H.half_beam(x) if -3.25 < x < 3.3 else 0.0
    if hb <= 0 or abs(y) > hb:
        return -1.0
    z = D.deck_z(x, y)
    x0, x1 = D.CB["x"]
    b = D.trunk_base(x)
    if x0 <= x <= x1 + 0.01 and abs(y) < b:
        e = D.trunk_edge(x)
        zt = D.top_z(x, min(abs(y), e))
        if abs(y) > e:
            zt = z + (zt - z) * (b - abs(y)) / (b - e)
        v = max(-1.0, min(1.0, y / b))
        ff, ft = D.front_foot_x(v), D.front_top_x(v)
        if x > ft:
            zt = z + (zt - z) * max(0.0, min(1.0, (ff - x) / (ff - ft)))
        z = max(z, zt)
    return z


class Sheet:
    """A sail's cloth grid G (nu + 1, nv + 1, 3), its UVs (nu + 1, nv + 1, 6), the points press() may not move
    (fixed), whether its top row is one point (collapse), and the side its cloth faces (face: a unit vector)."""

    def __init__(self, name, G, UV, fixed, face, collapse=False, flat=None):
        self.name, self.G, self.UV, self.fixed, self.face, self.collapse = name, G, UV, fixed, face, collapse
        self.flat = flat                     # the planform (nu + 1, nv + 1, 2), metres, for its area
        self.nu, self.nv = G.shape[0] - 1, G.shape[1] - 1
        self.extras = {}

    def normals(self, side):
        """Unit normals at every grid point, turned to the side `side` (a unit vector) points."""
        di = np.gradient(self.G, axis=0)
        dj = np.gradient(self.G, axis=1)
        n = np.cross(di, dj)
        ln = np.linalg.norm(n, axis=2)
        bad = ln < 1e-12
        if bad.any():
            n[bad] = n[np.where(bad)[0], np.maximum(np.where(bad)[1] - 1, 0)]
            ln = np.linalg.norm(n, axis=2)
        n = n / np.maximum(ln, 1e-12)[..., None]
        flip = (n @ np.asarray(side, float)) < 0
        n[flip] *= -1
        return n

    def row_normals(self, side):
        """One normal per row (square to its chord and to the luff there), turned to `side`, for every point of the
        row: steadier than the cloth's own where the rows close up at the head."""
        G = self.G
        n = np.zeros(G.shape)
        last = None
        for j in range(self.nv + 1):
            ch = G[-1, j] - G[0, j]
            up = G[0, min(j + 1, self.nv)] - G[0, max(j - 1, 0)]
            v = np.cross(up, ch)
            if np.linalg.norm(v) < 1e-9 or np.linalg.norm(ch) < 0.02:
                v = last if last is not None else np.asarray(side, float)
            v = unit(v)
            if v @ np.asarray(side, float) < 0:
                v = -v
            n[:, j] = v
            last = v
        return n

    def area(self):
        """The planform's area (flat, as a sailmaker measures it), else the cloth's."""
        P = self.flat if self.flat is not None else self.G
        a = 0.0
        for i in range(self.nu):
            for j in range(self.nv):
                p0, p1, p2, p3 = P[i, j], P[i + 1, j], P[i + 1, j + 1], P[i, j + 1]
                if P.shape[-1] == 2:
                    cr = lambda u, v: abs(u[0] * v[1] - u[1] * v[0])
                else:
                    cr = lambda u, v: np.linalg.norm(np.cross(u, v))
                a += 0.5 * (cr(p1 - p0, p2 - p0) + cr(p2 - p0, p3 - p0))
        return a


# ------------------------------------------------------------------ the obstacles

def wire_lines():
    """{name: (points (n, 3), radius)}: the rig's wires and the mast as polylines."""
    out = {n: (np.asarray(p, float), RC.SH["wire_d"] / 2) for n, (p, _) in RC.wires().items()}
    out["Mast"] = (np.array([(RC.MAST_X, 0.0, RC.heel_z()), (RC.MAST_X, 0.0, RC.top_z())]), RC.A / 2)
    return out


def seg_dist(P, a, b):
    """The distance from each point of P (m, 3) to the segment a-b."""
    ab = b - a
    t = np.clip(((P - a) @ ab) / (ab @ ab), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def triangles(sheet):
    """The cloth's triangles as three (k, 3) corner arrays."""
    G = sheet.G
    a, b, c, d = G[:-1, :-1].reshape(-1, 3), G[1:, :-1].reshape(-1, 3), G[1:, 1:].reshape(-1, 3), G[:-1, 1:].reshape(-1, 3)
    return np.vstack([a, a]), np.vstack([b, c]), np.vstack([c, d])


def crossings(sheet, pts):
    """How many times the polyline pts passes through the cloth (Moller-Trumbore on every triangle)."""
    A, B, C = triangles(sheet)
    e1, e2 = B - A, C - A
    n = 0
    for p, q in zip(pts[:-1], pts[1:]):
        d = q - p
        h = np.cross(d, e2)
        det = np.sum(e1 * h, axis=1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = p - A
        u = np.sum(s * h, axis=1) * inv
        qv = np.cross(s, e1)
        v = (qv @ d) * inv
        t = np.sum(e2 * qv, axis=1) * inv
        n += int(np.sum(ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= 1)))
    return n


def _seg_pts(P, a, b):
    """Distance from each point of P (m, 3) to each segment a[k]-b[k] (k, 3): (m, k)."""
    ab = b - a
    ap = P[:, None, :] - a[None]
    t = np.clip(np.sum(ap * ab[None], axis=2) / np.maximum(np.sum(ab * ab, axis=1), 1e-18)[None], 0.0, 1.0)
    return np.linalg.norm(ap - t[..., None] * ab[None], axis=2)


def tri_dist(P, A, B, C):
    """The least distance from each point of P (m, 3) to the triangles A, B, C (k, 3 each)."""
    n = np.cross(B - A, C - A)
    nn = np.maximum(np.sum(n * n, axis=1), 1e-24)
    out = np.empty(len(P))
    for s in range(0, len(P), 64):
        Q = P[s:s + 64]
        ap = Q[:, None, :] - A[None]
        h = np.sum(ap * n[None], axis=2) / nn[None]                     # along the normal, over |n|^2
        X = Q[:, None, :] - h[..., None] * n[None]                       # projected into each triangle's plane
        u = np.sum(np.cross(B - X, C - X) * n[None], axis=2) / nn[None]
        v = np.sum(np.cross(C - X, A - X) * n[None], axis=2) / nn[None]
        inside = (u >= 0) & (v >= 0) & (u + v <= 1) & (nn > 1e-14)[None]     # a collapsed triangle has only edges
        plane = np.abs(h) * np.sqrt(nn)[None]
        edge = np.minimum(np.minimum(_seg_pts(Q, A, B), _seg_pts(Q, B, C)), _seg_pts(Q, C, A))
        out[s:s + 64] = np.where(inside, plane, edge).min(axis=1)
    return out


def clearance(sheet, names):
    """{obstacle: least gap (m) from the cloth's triangles to it}, and to the floor ('Deck'). Each wire is sampled
    every centimetre and each sample measured to every triangle near it (not only to the grid's points, which can stand
    farther off than the faces between them)."""
    A, B, C = triangles(sheet)
    lo = np.minimum(np.minimum(A, B), C)
    hi = np.maximum(np.maximum(A, B), C)
    out = {}
    for n, (pts, r) in wire_lines().items():
        if n not in names:
            continue
        S = np.vstack([a + np.linspace(0.0, 1.0, max(2, int(np.linalg.norm(b - a) / 0.01) + 1))[:, None] * (b - a)
                       for a, b in zip(pts[:-1], pts[1:])])
        near = np.all((lo < S.max(axis=0) + 0.2) & (hi > S.min(axis=0) - 0.2), axis=1)
        if not near.any():
            out[n] = 1.0
            continue
        S = S[(S[:, 2] > lo[near, 2].min() - 0.2) & (S[:, 2] < hi[near, 2].max() + 0.2)]
        d = tri_dist(S, A[near], B[near], C[near]).min() if len(S) else 1.0
        out[n] = d - r if not crossings(sheet, pts) else -1.0            # a wire through the cloth
    out["Deck"] = min(p[2] - floor_z(p[0], p[1]) for p in sheet.G.reshape(-1, 3))
    return out


HOLD_M = 0.4
KINK = 0.045                                   # the largest second difference the grid may have, metres


def press(sheet, names, lee, side, clr=PRESS, sigma=0.3, rounds=6, floor=True, vspread=0):
    """Push the cloth clear of the obstacles in `names`: each must end up `clr` on the cloth's `side` (+1: the cloth
    to its lee, as a genoa over the shrouds; -1: the cloth to windward of it, as a jib inside them), where `lee` is the
    leeward direction. A point's push is what it lacks, along its normal; spread over a few cells and faded to nothing at
    the fixed points (the luff and the boom). The floor (deck and cabin) lifts the cloth the same way."""
    G = sheet.G
    P = G.reshape(-1, 3)
    F = P[sheet.fixed.reshape(-1)]
    d = (np.min(np.linalg.norm(P[:, None, :] - F[None, :, :], axis=2), axis=1).reshape(G.shape[:2]) if len(F) else
         np.full(G.shape[:2], HOLD_M))
    hold = np.vectorize(smooth01)(d / HOLD_M)                  # free to move only HOLD_M (metres) from what holds it
    hold[sheet.fixed] = 0.0
    obs = [(n, wire_lines()[n]) for n in names]
    N = sheet.row_normals(lee)                                 # pushed along the rows' own normals, taken once
    acc = np.zeros(G.shape[:2])                                # the whole push, for vspread
    for _ in range(rounds):
        need = np.zeros(G.shape[:2])
        ch = G[-1] - G[0]                                      # each row's chord, luff to leech
        rlen = np.linalg.norm(ch, axis=1)[None, :]
        rdir = (ch / np.maximum(rlen[0], 1e-9)[:, None])[None, :, :]
        row0 = G[0][None, :, :]
        for n, (pts, r) in obs:
            for a, b in zip(pts[:-1], pts[1:]):
                if abs(b[2] - a[2]) < 1e-9:
                    continue
                t = (G[..., 2] - a[2]) / (b[2] - a[2])
                tc = np.clip(t, 0.0, 1.0)
                dz = np.abs(t - tc) * abs(b[2] - a[2])                # how far past the wire's end, up or down
                w = a + tc[..., None] * (b - a)
                q = G - w
                q[..., 2] = 0.0
                nh = N.copy()
                nh[..., 2] = 0.0
                nh /= np.maximum(np.linalg.norm(nh, axis=2), 1e-9)[..., None]
                s = np.sum(q * nh, axis=2)
                tang = np.hypot(np.linalg.norm(q - s[..., None] * nh, axis=2), dz)
                lack = (clr + r) - side * s
                wgt = np.exp(-(tang / sigma) ** 2)
                # only where the wire stands within the row's span, luff to leech: a wire past the leech (or ahead of
                # the luff) is cleared by the edge, not pushed through the cloth
                along = np.sum((w - row0) * rdir, axis=2)
                over = smooth01((along + 0.15) / 0.15) * smooth01((rlen - along + 0.15) / 0.15)
                need = np.maximum(need, np.where((lack > 0) & (tang < 3 * sigma), lack * wgt * over, 0.0))
        need = np.maximum(need, blur(need, 4))
        acc += need * hold
        G += (side * need * hold)[..., None] * N
        if floor:
            fz = np.vectorize(floor_z)(G[..., 0], G[..., 1])
            lift = np.maximum(0.0, fz + clr - G[..., 2])
            lift = np.maximum(lift, blur(lift, 2))
            G[..., 2] += lift * hold
    if vspread:
        # the whole push spread up and down the sail over `vspread` rows (a Gaussian, never less than it was), so it
        # fades over a metre or so, not one row: the genoa's leech, pushed round the upper above the spreader, has no step
        w = vspread
        pad = np.pad(acc, ((0, 0), (w, w)), mode="edge")       # first the largest push within w rows (so the blur
        dil = np.max(np.stack([pad[:, i:i + acc.shape[1]] for i in range(2 * w + 1)]), axis=0)   # can't dip under it)
        k = np.exp(-0.5 * (np.arange(-2 * w, 2 * w + 1) / (w / 2)) ** 2)
        pad = np.pad(dil, ((0, 0), (2 * w, 2 * w)), mode="edge")
        sm = np.maximum(acc, np.array([np.convolve(r, k / k.sum(), mode="valid") for r in pad]) * hold)
        G += (side * (sm - acc))[..., None] * N
    return sheet


# ------------------------------------------------------------------ the mainsail

def main_planform(n=400):
    """The mainsail's flat outline: luff (0, 0)-(0, P), foot (0, 0)-(E, 0), headboard (0, P)-(hb, P), the leech from
    the clew to the headboard's aft corner with the roach out of it. Returns the leech as a function: chord at height v."""
    hb, roach = MS["head_board"], MS["roach"]
    s = np.linspace(0.0, 1.0, n)
    a, b = np.array([E_M, 0.0]), np.array([hb, P_M])
    out = unit(np.array([(b - a)[1], -(b - a)[0]]))          # away from the luff
    L = a + s[:, None] * (b - a) + (roach * np.sin(np.pi * s))[:, None] * out
    v = L[:, 1]
    return lambda h: np.interp(h, v, L[:, 0])


def main_sheet(state, nu=30, nv=60):
    st = MS["states"][state]
    reef = MS["reef"] * P_M if state == "Reefed" else 0.0
    beta, twist = math.radians(st["boom_deg"]), math.radians(st["twist_deg"])
    depth, draft = table(st["depth"]), table(st["draft_at"])
    chord = main_planform()
    xl = RC.MAST_X - RC.A / 2 + MS["luff_in_groove"]
    zb = RC.boom_top() + 0.004                                  # the foot's bolt rope in the boom's groove
    g = np.array(RC.gooseneck())
    cb, sb = math.cos(beta), math.sin(beta)
    rotb = lambda p: g + np.array([(p[0] - g[0]) * cb - (p[1] - g[1]) * sb, (p[0] - g[0]) * sb + (p[1] - g[1]) * cb,
                                   p[2] - g[2]])
    G = np.zeros((nu + 1, nv + 1, 3))
    UV = np.zeros((nu + 1, nv + 1, 6))
    flat = np.zeros((nu + 1, nv + 1, 2))
    vs = reef + (P_M - reef) * (np.linspace(0.0, 1.0, nv + 1) ** 1.0)
    fs = np.linspace(0.0, 1.0, nu + 1) ** 1.4                  # closer near the luff, where the rows turn
    bend = MS["luff_bend"]
    for j, v in enumerate(vs):
        tau = (v - reef) / (P_M - reef)
        c = float(chord(v))
        L = np.array([xl, 0.0, zb + v - reef])                  # the luff stays in the groove, the tack too
        phi = beta + twist * tau ** 1.3
        n = np.array([math.sin(phi), -math.cos(phi), 0.0])       # to leeward (port, and forward when squared off)
        m, p = float(depth(tau)), float(draft(tau))
        # the row leaves the groove straight aft and turns to its angle over 'luff_bend' (round the mast's after
        # side when squared off), then runs straight: its base line, integrated along the row
        ss = np.linspace(0.0, c, 400)
        th = phi * np.vectorize(smooth01)(ss / bend)
        dx = np.concatenate([[0.0], np.cumsum(-np.cos(0.5 * (th[1:] + th[:-1])) * np.diff(ss))])
        dy = np.concatenate([[0.0], np.cumsum(-np.sin(0.5 * (th[1:] + th[:-1])) * np.diff(ss))])
        w_boom = max(0.0, 1.0 - tau / 0.08)                     # the lowest rows ease onto the boom's own line
        for i, f in enumerate(fs):
            base = L + np.array([np.interp(f * c, ss, dx), np.interp(f * c, ss, dy), 0.0])
            if i and w_boom:
                on_boom = rotb(np.array([xl - f * c, 0.0, L[2]]))
                wb = w_boom * smooth01(f * c / bend)                # past the turn off the groove only
                base = (1 - wb) * base + wb * on_boom
            G[i, j] = base + m * c * float(camber(f, p)) * n
            flat[i, j] = (f * c, v)
            UV[i, j] = (f * c, v, f * c / E_M, v / P_M, (1 - f) * c, 0.0)
    # the foot along the boom exactly (its bolt rope is in the groove) aft of the tack, which stays at the luff
    for i, f in enumerate(fs[1:], start=1):
        G[i, 0] = rotb(np.array([xl - f * float(chord(reef)), 0.0, zb]))
    # UV2.y: how far in from the leech's straight line (clew to the headboard's corner), in the planform
    a, b = np.array([E_M, 0.0]), np.array([MS["head_board"], P_M])
    nrm = unit(np.array([(b - a)[1], -(b - a)[0]]))
    UV[..., 5] = -((flat - a) @ nrm)
    fixed = np.zeros((nu + 1, nv + 1), bool)
    fixed[0, :] = True
    fixed[:, 0] = True
    sh = Sheet("Main" + state, G, UV, fixed, face=np.array([0.0, 1.0, 0.0]), flat=flat)
    sh.extras = {"beta": beta, "reef": reef, "chord": chord, "xl": xl, "zb": zb, "rotb": rotb}
    return sh


def main_point(sh, f, v):
    """The point on a mainsail sheet at chord share f, planform height v (metres from the unreefed foot)."""
    vs = sh.UV[0, :, 1]
    j = int(np.clip(np.searchsorted(vs, v) - 1, 0, sh.nv - 1))
    b = (v - vs[j]) / (vs[j + 1] - vs[j])
    fi = f * sh.nu
    i = int(np.clip(math.floor(fi), 0, sh.nu - 1))
    a = fi - i
    G = sh.G
    return ((1 - a) * (1 - b) * G[i, j] + a * (1 - b) * G[i + 1, j] + a * b * G[i + 1, j + 1] + (1 - a) * b * G[i, j + 1])


# ------------------------------------------------------------------ the headsails

def stay():
    pts = np.asarray(RC.wires()["Forestay"][0], float)
    top, foot = pts[0], pts[-1]
    return foot, unit(top - foot), float(np.linalg.norm(top - foot))


def tack_fitting():
    """Where a headsail's tack shackles to the stemhead fitting (game frame): the headsails' own 'tack_over_deck' above the
    deck, down the stay's line. A sail cut with its own higher tack (the genoa) reaches it on a wire pennant."""
    foot, u, Ls = stay()
    aft = unit(np.array([-1.0, 0.0, 0.0]) - u * (u @ np.array([-1.0, 0.0, 0.0])))
    s = (floor_z(foot[0], 0.0) + HS["tack_over_deck"] - foot[2]) / u[2]
    return foot + u * s + aft * HS["luff_aft_of_stay"]


def headsail_corners(name):
    """Tack, head and clew of a headsail (game frame), its luff's plane basis and LP."""
    sp = HS[name]
    foot, u, Ls = stay()
    aft = unit(np.array([-1.0, 0.0, 0.0]) - u * (u @ np.array([-1.0, 0.0, 0.0])))
    o = HS["luff_aft_of_stay"]
    s_tack = (floor_z(foot[0], 0.0) + sp.get("tack_over_deck", HS["tack_over_deck"]) - foot[2]) / u[2]  # down the stay's line to the stemhead
    T = foot + u * s_tack + aft * o
    Hd = foot + u * (Ls - HS["head_below_hounds"]) + aft * o
    lp = sp["lp"] * J_M
    al = math.radians(sp["sheet_deg"])
    h = np.array([-math.cos(al), -math.sin(al), 0.0])
    luff = unit(Hd - T)

    def perp(r):
        C = np.array([T[0] + r * h[0], T[1] + r * h[1], sp["clew_z"]])
        w = C - T
        return np.linalg.norm(w - luff * (w @ luff))
    lo, hi = 0.5, 8.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if perp(mid) < lp else (lo, mid)
    C = np.array([T[0] + lo * h[0], T[1] + lo * h[1], sp["clew_z"]])
    return T, Hd, C, lp


def headsail_sheet(name, nu=30, nv=60):
    sp = HS[name]
    T, Hd, C, lp = headsail_corners(name)
    e2 = unit(Hd - T)
    e1 = unit((C - T) - e2 * ((C - T) @ e2))
    Lluff = float(np.linalg.norm(Hd - T))
    c2 = np.array([(C - T) @ e1, (C - T) @ e2])
    h2 = np.array([0.03, Lluff])                               # the head's width: a small board
    t2 = np.array([0.0, 0.0])
    l2 = np.array([0.0, Lluff])
    foot_len = float(np.linalg.norm(c2))
    leech_len = float(np.linalg.norm(h2 - c2))
    nf = unit(np.array([-c2[1], c2[0]]))                       # in the plane, square to the foot, toward the head
    if nf[1] < 0:
        nf = -nf
    nl = unit(np.array([(h2 - c2)[1], -(h2 - c2)[0]]))         # square to the leech, away from the luff
    if nl[0] < 0:
        nl = -nl
    twist = math.radians(sp["twist_deg"])
    depth, draft = table(sp["depth"]), table(sp["draft_at"])
    fs = np.linspace(0.0, 1.0, nu + 1)
    ts = np.linspace(0.0, 1.0, nv + 1)
    G = np.zeros((nu + 1, nv + 1, 3))
    UV = np.zeros((nu + 1, nv + 1, 6))
    flat = np.zeros((nu + 1, nv + 1, 2))
    # which way the twist turns: the one that sends the clew further to port
    sgn = 1.0 if rotate(e1, e2, 0.1)[1] < e1[1] else -1.0
    for j, t in enumerate(ts):
        Lp = t2 + t * (l2 - t2)
        Rp = c2 + t * (h2 - c2)
        for i, f in enumerate(fs):
            p = Lp + f * (Rp - Lp)
            p = p - sp["foot_round"] * foot_len * math.sin(math.pi * f) * (1 - t) ** 4 * nf
            p = p - sp["leech_hollow"] * leech_len * math.sin(math.pi * t) * f ** 4 * nl
            flat[i, j] = p
        c = float(np.linalg.norm(flat[-1, j] - flat[0, j]))
        ang = sgn * twist * t ** sp.get("twist_power", 1.3)
        rows = np.array([rotate(flat[i, j][0] * e1, e2, ang) + flat[i, j][1] * e2 for i in range(nu + 1)])
        ch = rows[-1] - rows[0]
        n = unit(np.cross(e2, ch))
        if n[1] > 0:
            n = -n                                             # to leeward: port
        m, pd = float(depth(t)), float(draft(t))
        for i, f in enumerate(fs):
            G[i, j] = T + rows[i] + m * c * float(camber(f, pd)) * n
            UV[i, j, 0:4] = (flat[i, j][0] - flat[0, j][0], flat[i, j][1], f, t)
            UV[i, j, 4] = float(np.linalg.norm(flat[-1, j] - flat[i, j]))
    UV[..., 5] = -((flat - c2) @ nl)
    fixed = np.zeros((nu + 1, nv + 1), bool)
    fixed[0, :] = True
    fixed[-1, 0] = True
    fixed[:, -1] = True
    sh = Sheet(name + "Set", G, UV, fixed, face=np.array([0.0, 1.0, 0.0]), flat=flat)
    sh.extras = {"T": T, "H": Hd, "C": C, "lp": lp, "e1": e1, "e2": e2}
    return sh


# ------------------------------------------------------------------ the spinnaker

def pole():
    """The spinnaker pole's mast end (its ring on the mast's front) and its outer end, where the tack is."""
    ring = np.array([RC.MAST_X + RC.A / 2 + 0.03, 0.0, RC.step_z() + SP["pole_ring_over_step"]])
    a = math.radians(SP["pole_deg"])
    return ring, ring + J_M * np.array([math.cos(a), math.sin(a), 0.0])


def spinnaker_head():
    """The head's ring: hung under the halyard's block on the masthead's forward face, 'head_drop' below it and
    swung 'head_out' forward of it."""
    return np.array([RC.MAST_X + RC.A / 2 + 0.04 + SP["head_out"], 0.0, RC.top_z() - 0.03 - SP["head_drop"]])


def halyard_block():
    return np.array([RC.MAST_X + RC.A / 2 + 0.04, 0.0, RC.top_z() - 0.03])


def bez(a, c, b, t):
    t = np.asarray(t, float)[:, None]
    return (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t * t * b


SH_Z = 0.1                                     # how far under the head the upper shoulder's control point stands, of the height


def bez3(a, c1, c2, b, t):
    t = np.asarray(t, float)[:, None]
    return (1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t * t * c2 + t ** 3 * b


def spinnaker_sheet(nu=36, nv=56):
    _, T = pole()
    Hh = spinnaker_head()
    C = np.array(SP["clew"], float)
    ts = np.linspace(0.0, 1.0, nv + 1)
    fs = np.linspace(0.0, 1.0, nu + 1)
    mid = (T + C) / 2
    fwd = np.array([1.0, 0.0, 0.0])
    s1, s2 = SP["shoulder"]

    def edge(a):
        """A luff or leech: out from its corner and up to broad shoulders ('shoulder': how far out the lower and upper
        control points stand), then in to the head."""
        out = unit((a - mid) * np.array([1, 1, 0]))
        h = Hh[2] - a[2]
        c1 = a + np.array([0.0, 0.0, 0.4 * h]) + out * s1 + fwd * SP["fly_fwd"] * 0.6
        c2 = Hh + np.array([0.0, 0.0, -SH_Z * h]) + out * s2 + fwd * SP["fly_fwd"]
        return c1, c2
    (l1, l2), (r1, r2) = edge(T), edge(C)
    luff = bez3(T, l1, l2, Hh, ts)
    leech = bez3(C, r1, r2, Hh, ts)
    depth = table(SP["depth"])
    widths = np.linalg.norm(leech - luff, axis=1)
    bulge = np.array([float(depth(t)) for t in ts]) * widths       # each row's forward bulge, metres
    k = np.exp(-0.5 * (np.arange(-12, 13) / 4.0) ** 2)
    pad = np.concatenate([np.full(12, bulge[0]), bulge, np.full(12, bulge[-1])])
    bulge = np.convolve(pad, k / k.sum(), mode="valid")            # smoothed up the sail: no crease where the table bends
    bulge *= np.array([smooth01((1.0 - t) / 0.12) for t in ts])    # and closing smoothly into the head
    G = np.zeros((nu + 1, nv + 1, 3))
    for j in range(nv + 1):
        a, b = luff[j], leech[j]
        w = float(np.linalg.norm(b - a))
        ch = (b - a) / max(w, 1e-9)
        n = fwd - ch * (fwd @ ch)
        n = unit(n) if np.linalg.norm(n) > 1e-9 else fwd
        up = np.array([0.0, 0.0, 1.0])
        for i, f in enumerate(fs):
            G[i, j] = a + f * (b - a) + bulge[j] * float(camber(f, 0.5)) * n + \
                0.06 * w * float(camber(f, 0.5)) * up * (1 - ts[j])
    G[:, -1] = Hh
    UV = np.zeros((nu + 1, nv + 1, 6))
    seg = np.linalg.norm(np.diff(G, axis=0), axis=2)                 # along each row
    acc = np.vstack([np.zeros((1, nv + 1)), np.cumsum(seg, axis=0)])
    up_len = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(G[nu // 2], axis=0), axis=1))])
    for i in range(nu + 1):
        for j in range(nv + 1):
            UV[i, j] = (acc[i, j], up_len[j], fs[i], ts[j], acc[-1, j] - acc[i, j], abs(acc[i, j] - acc[-1, j] / 2))
    fixed = np.zeros((nu + 1, nv + 1), bool)
    fixed[0, 0] = fixed[-1, 0] = True
    fixed[:, -1] = True
    sh = Sheet("SpinnakerSet", G, UV, fixed, face=np.array([-1.0, 0.0, 0.0]), collapse=True)
    sh.extras = {"T": T, "C": C, "H": Hh}
    return sh


# ------------------------------------------------------------------ all of them, pressed

LEE_P = ["Upper_P", "LowerFwd_P", "LowerAft_P"]


def set_sheets():
    """{name: Sheet} for every set state, pressed clear of what it would touch."""
    out = {}
    for st in ("Set", "Reefed"):
        out["Main" + st] = press(main_sheet(st), LEE_P, np.array([0.0, -1.0, 0.0]), -1, floor=False)
    run = main_sheet("Run")
    out["MainRun"] = press(run, LEE_P, np.array([0.3, -1.0, 0.0]), -1, clr=0.035, floor=False)   # lies on the lowers
    out["JibSet"] = press(headsail_sheet("Jib"), [], np.array([0.0, -1.0, 0.0]), -1)       # clear as cut: the floor only
    g = headsail_sheet("Genoa")
    out["GenoaSet"] = press(g, LEE_P, np.array([0.0, -1.0, 0.0]), +1, sigma=0.5, vspread=6,
                       clr=0.06)   # 3 in off the upper, with no dent or step at the spreader
    out["SpinnakerSet"] = press(spinnaker_sheet(), ["Forestay"], np.array([1.0, 0.0, 0.0]), +1)
    return out


def bag_size(area, nylon=False):
    """(length, radius) of a sail's bag: its cloth's volume times the bulk, in a bag 2.5 times as long as it is wide."""
    vol = area * (CL["nylon_mm"] if nylon else CL["dacron_mm"]) / 1000 * CL["bulk"]
    r = (vol / (math.pi * 5.0)) ** (1 / 3)
    return 5.0 * r, r


def main():
    fails = []
    sh = set_sheets()
    print(f"mainsail: luff P {P_M:.3f} m, foot E {E_M:.3f} m, roach {MS['roach']:.2f} m, one reef at {MS['reef']:.0%} "
          f"of the luff")
    tri = P_M * E_M / 2
    ok = abs(tri / MS["area"] - 1) <= 0.01
    print(f"  MainSet       triangle P E / 2 {tri:5.2f} m^2 against the physics' {MS['area']:.2f} {'ok' if ok else 'FAIL'}; "
          f"with its headboard and roach {sh['MainSet'].area():.2f}")
    if not ok:
        fails.append("MainSet area")
    strip = 6.4 * ((2.94 + 0.25) / 2 + 0.08 * 2 / np.pi)       # Fleet.cpp's SetMain strips: 6.4 m of luff, chords 2.94
    a = sh["MainSet"].area()                                   # to 0.25 with 0.08 of roach (sail_plan_c22.py draws them)
    ok = abs(a / strip - 1) <= 0.05
    print(f"  MainSet       cloth {a:5.2f} m^2 against the physics' strips {strip:5.2f} ({a / strip - 1:+.1%}) "
          f"{'ok' if ok else 'FAIL'}")
    if not ok:
        fails.append("MainSet strips")
    for name, target in (("GenoaSet", HS["Genoa"]["area"]), ("SpinnakerSet", SP["area"])):
        a = sh[name].area()
        ok = abs(a / target - 1) <= 0.05
        print(f"  {name:13s} area {a:6.2f} m^2 against the physics' {target:5.2f} ({a / target - 1:+.1%}) "
              f"{'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(name + " area")
    print(f"  JibSet        area {sh['JibSet'].area():6.2f} m^2 (the working jib: no physics figure)")
    for name in ("Jib", "Genoa"):
        T, Hd, C, lp = headsail_corners(name)
        print(f"{name}: tack {np.round(T, 3)}, head {np.round(Hd, 3)}, clew {np.round(C, 3)}, luff "
              f"{np.linalg.norm(Hd - T):.2f} m, foot {np.linalg.norm(C - T):.2f} m, leech {np.linalg.norm(Hd - C):.2f} m, "
              f"LP {lp:.2f} m ({lp / J_M:.0%} of J)")
    ring, tip = pole()
    print(f"spinnaker: head {np.round(spinnaker_head(), 3)}, pole {np.round(ring, 2)} to {np.round(tip, 2)}, "
          f"clew {SP['clew']}")
    for name, s in sh.items():
        names = [n for n in wire_lines() if not (n == "Mast" and name.startswith("Main"))]
        c = clearance(s, names)
        low = {k: v for k, v in c.items() if v < 0.1}
        worst = min(c.values())
        flag = "ok" if worst >= CLEAR else "FAIL"
        print(f"  {name:13s} least gap {worst * 100:5.1f} cm  " +
              ", ".join(f"{k} {v * 100:.1f}" for k, v in sorted(low.items())) + f"  {flag}")
        if worst < CLEAR:
            fails.append(name + " clearance")
    for name, s in sh.items():                                 # no creases from the press: the free cloth stays smooth
        G, free = s.G, ~s.fixed                                # (the corners and bolt ropes are cut, not pressed)
        k = max((np.linalg.norm(G[2:] - 2 * G[1:-1] + G[:-2], axis=2) * free[1:-1]).max(),
                (np.linalg.norm(G[:, 2:] - 2 * G[:, 1:-1] + G[:, :-2], axis=2) * free[:, 1:-1]).max())
        print(f"  {name:13s} sharpest bend {k * 100:4.1f} cm  {'ok' if k <= KINK else 'FAIL'}")
        if k > KINK:
            fails.append(name + " crease")
    for name, area, nyl in (("Main", MS["area"], False), ("Jib", sh["JibSet"].area(), False),
                            ("Genoa", HS["Genoa"]["area"], False), ("Spinnaker", SP["area"], True)):
        L, r = bag_size(area, nyl)
        print(f"  {name} bagged: {L:.2f} m long, {2 * r:.2f} m across")
    if fails:
        print("FAIL: " + ", ".join(fails))
        sys.exit(1)
    print("pass")


if __name__ == "__main__":
    main()
