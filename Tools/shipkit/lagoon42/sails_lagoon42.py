"""The Lagoon 42's sails from sails_lagoon42.json on slice 6's rig (rig_lagoon42): cloth grids, their states' shapes,
the lazy bag and lazy jacks, every trim and fitting as parts, and the checks. Numpy, no Blender (docs/lagoon42-8);
build_lagoon42.py meshes objects().

    python3 -I sails_lagoon42.py     prints each sail's sizes, areas and clearances; fails on a sail off its area by
                                     more than 3%, a set sail closer than 1 cm to a wire, a spreader, the mast or what
                                     is under it, a crease in a pressed sail, or the main's foot outside its bag

A set sail is a Sheet: rows j = 0..nv up the sail, each of nu + 1 points from the luff (i = 0) to the leech; G is the
(nu + 1, nv + 1, 3) grid in the game's frame (X forward, Y starboard, Z up, metres) and UV its (nu + 1, nv + 1, 6)
texture coordinates as the game's sail cloth reads them (SailCloth.h; the Catalina 22's sails_c22.py): UV0 metres in
the flat sail (along the row from the luff, up), UV1 the same normalized (0..1 both ways), UV2.x metres along the row
from the leech, UV2.y the distance in from the leech's straight line (negative in the roach). Rows run parallel to the
foot. Every set sail is drawn on starboard tack (the boom and sails to port); its cloth faces starboard.

Objects (build_lagoon42.py builds each as named; all hidden but the boat at her mooring, SHOWN):
  L42_Sail_Main_Set, _Reach, _Run, _Reefed   the main hoisted, its boom at the state's angle (property boom_deg): the
            cloth, its tapes, battens and pockets, the cars and slides on the track, the headboard and its car, the
            patches, the reefs' cringles and lines, the clew and tack, the halyard's run and the lazy jacks as they lie
            with the sail up (the lee ones bowed round it), the mainsheet's four parts eased to the boom (the car
            amidships; L42_Mainsheet, the boom amidships's, is hidden with any of them); _Reefed with the first reef
            in, its bunt in the bag
  L42_Sail_Main_Luff   what the three hoisted states share, because it does not move when the boom swings: the slides,
            the batten cars and the headboard's car on the track and the halyard's run. Shown with _Set, _Reach, _Run
  L42_LazyBag_Zipped   the bag closed over the flaked main (the drone photo's), the slides and cars stacked at the
            track's foot, the halyard down to them, the lazy jacks to the bag's top. Origin at the gooseneck's pin
  L42_LazyBag_Open     the bag open, its sides up: shown with a hoisted main, swung with the boom. Origin at the pin
  L42_Sail_Jib_Set     the self-tacking jib set, its sheet round the car's swivel block (the car at the port lead) and up
            into the mast; L42_Sail_Jib_Furled rolled round the foil, the car on the track's middle
  L42_Sail_Code0_Set   the Code 0 on a reach, its tack on its furler's drum on the bowsprit, its head on the top swivel,
            its sheet to the port quarter's block; L42_Sail_Code0_Furled rolled round its cable, still hoisted
Parts are rig_lagoon42's kinds (rings, cyl, torus, box, kit) plus 'cloth' (a sheet's grid with its UVs, faced toward
'face') and 'layer' (rows of points, a sewn-on layer or patch: one-sided, faced toward 'face').
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bridgedeck_lagoon42 as B  # noqa: E402
import hull_lagoon42 as H  # noqa: E402
import rig_lagoon42 as R  # noqa: E402
import saloon_lagoon42 as S  # noqa: E402

SJ = json.load(open(os.path.join(HERE, "sails_lagoon42.json")))
CL, MS, JB, C0, BG, LJ = SJ["cloth"], SJ["mainsail"], SJ["jib"], SJ["code0"], SJ["lazy_bag"], SJ["lazy_jacks"]
CLEAR = 0.01                  # the least gap a set sail keeps to a wire, a spreader, the mast or what is under it
PRESS = 0.025                 # what press() aims for, so the check passes with room
KINK = 0.06                   # the largest second difference a pressed grid may have, metres
HOLD_M = 0.5                  # how far from what holds it (the luff, the clew) the cloth is free to be pressed

PIN = np.array([R.PIN_X, 0.0, R.PIN_Z])
BOOM_TOP = R.PIN_Z + R.BO["height"] / 2
LUFF_X = R.aft_x() - R.MS["track"]["depth"] - MS["luff_off_track"]
TACK_Z = BOOM_TOP + MS["foot_over_boom"]
CLEW_X = R.boom_clew()[0]
P_M = MS["head_z"] - TACK_Z                 # the main's luff
E_M = LUFF_X - CLEW_X                       # its foot
LEE = np.array([0.0, -1.0, 0.0])            # starboard tack: the sails to port


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


def boom_rot(beta):
    """Game-frame points turned about the gooseneck's pin by beta (radians, the boom's angle to port)."""
    cb, sb = math.cos(beta), math.sin(beta)

    def f(p):
        p = np.asarray(p, float)
        q = p - PIN
        return PIN + np.stack([q[..., 0] * cb - q[..., 1] * sb, q[..., 0] * sb + q[..., 1] * cb, q[..., 2]], axis=-1)
    return f


def blur(a, passes=2):
    a = np.asarray(a, float)
    for _ in range(passes):
        b = a.copy()
        b[1:-1, :] = 0.25 * a[:-2, :] + 0.5 * a[1:-1, :] + 0.25 * a[2:, :]
        c = b.copy()
        c[:, 1:-1] = 0.25 * b[:, :-2] + 0.5 * b[:, 1:-1] + 0.25 * b[:, 2:]
        a = c
    return a


def tup(p):
    return tuple(float(c) for c in p)


def floor_z(x, y):
    """What lies under (x, y): the roof over the saloon and cockpit, a hull's deck, the foredeck between the hulls or
    the trampolines and the crossbeam; -1 over open water."""
    z = -1.0
    if S.roof_inset(x, y) >= 0:
        z = max(z, S.roof_top_z(y))
    for cy in (H.HULL_Y, -H.HULL_Y):
        if H.TRANSOM_X < x < H.STEM_X:
            hb = H.half_beam(x)
            if abs(y - cy) <= hb:
                z = max(z, S.deck_z(x, (y - cy) / hb))
    if abs(y) < B.deck_span(x) and x < B.CB["x"] + B.CB["chord"] / 2:
        v = y / max(B.deck_span(x), 1e-6)
        if x <= B.nose_x(v, True):
            z = max(z, B.deck_z(x, y))
        elif x < B.CB["x"] - B.CB["chord"] / 2:
            z = max(z, B.TR["z"])
        else:
            z = max(z, B.CB["z"] + B.CB["depth"] / 2)
    return z


class Sheet:
    """A sail's cloth grid G (nu + 1, nv + 1, 3), its UVs (nu + 1, nv + 1, 6), the points press() may not move
    (fixed), the side its cloth faces (face) and its flat planform (nu + 1, nv + 1, 2) for its area."""

    def __init__(self, name, G, UV, fixed, face, flat):
        self.name, self.G, self.UV, self.fixed, self.face, self.flat = name, G, UV, fixed, np.asarray(face, float), flat
        self.nu, self.nv = G.shape[0] - 1, G.shape[1] - 1
        self.extras = {}

    def normals(self, side):
        """Unit normals at every grid point, turned to the side `side` points."""
        di = np.gradient(self.G, axis=0)
        dj = np.gradient(self.G, axis=1)
        n = np.cross(di, dj)
        n = n / np.maximum(np.linalg.norm(n, axis=2), 1e-12)[..., None]
        n[(n @ np.asarray(side, float)) < 0] *= -1
        return n

    def row_normals(self, side):
        """One normal per row (square to its chord and to the luff there), turned to `side`."""
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

    def at(self, fi, fj, A=None):
        """The grid (or the array A of the grid's shape) at fractional indices fi (along the rows) and fj (up)."""
        A = self.G if A is None else A
        i = int(np.clip(math.floor(fi), 0, self.nu - 1))
        j = int(np.clip(math.floor(fj), 0, self.nv - 1))
        a, b = fi - i, fj - j
        return ((1 - a) * (1 - b) * A[i, j] + a * (1 - b) * A[i + 1, j] + a * b * A[i + 1, j + 1] +
                (1 - a) * b * A[i, j + 1])

    def area(self):
        P = self.flat
        a = 0.0
        for i in range(self.nu):
            for j in range(self.nv):
                p0, p1, p2, p3 = P[i, j], P[i + 1, j], P[i + 1, j + 1], P[i, j + 1]
                cr = lambda u, v: abs(u[0] * v[1] - u[1] * v[0])
                a += 0.5 * (cr(p1 - p0, p2 - p0) + cr(p2 - p0, p3 - p0))
        return a


# ------------------------------------------------------------------ the obstacles

def rig_segments():
    """{name: [(a, b, radius)]}: the rig's wires, spreaders and mast as straight pieces (game frame)."""
    out = {}
    rc, rl = R.WR["cap"] / 2, R.WR["lower"] / 2
    for s, tag in ((1, "S"), (-1, "P")):
        root, tip, _ = R.spreader_tip(s)
        _, start = R.tball(R.mast_t_toward(tip, R.HOUNDS_Z), R.HOUNDS_Z - 0.03, tip, rc)
        wend = R.chainplate((R.CP["cap"][0], s * R.CP["cap"][1]), tip, R.WR["cap"])[2]
        out["Cap_" + tag] = [(np.array(start), np.array(tip), rc), (np.array(tip), np.array(wend), rc)]
        lxy = (R.CP["lower"][0], s * R.CP["lower"][1])
        far = (lxy[0], lxy[1], S.deck_z(lxy[0], 0.8))
        _, ls = R.tball(R.mast_t_toward(far, R.RG["lower_tang_z"]), R.RG["lower_tang_z"], far, rl)
        lend = R.chainplate(lxy, ls, R.WR["lower"])[2]
        out["Lower_" + tag] = [(np.array(ls), np.array(lend), rl)]
        out["Spreader_" + tag] = [(np.array(root), np.array(tip), R.SP["chord"][0] / 2)]
    tack, hounds = np.array(R.forestay_tack()), np.array(R.hounds_pin())
    ftop = np.array(R.forestay_at(R.FS["foil_top_z"]))
    out["Forestay"] = [(tack, ftop, R.FS["foil"][0] / 2), (ftop, hounds, R.WR["forestay"] / 2)]
    out["Mast"] = [(np.array([R.MAST_X, 0.0, R.HEEL_Z]), np.array([R.MAST_X, 0.0, R.TRUCK_Z]), R.MS["chord"] / 2)]
    return out


def closest_on(G, a, b):
    ab = b - a
    t = np.clip(((G - a) @ ab) / max(ab @ ab, 1e-18), 0.0, 1.0)
    return a + t[..., None] * ab


def press(sheet, segs, lee, side, clr=PRESS, sigma=0.3, rounds=6, floor=True, vspread=0):
    """Push the cloth clear of the obstacles segs [(a, b, r)]: each must end up clr on the cloth's `side` (+1: the cloth
    to its lee, as a Code 0 outside the shrouds; -1: the cloth to windward of it, a main squared off onto the lee cap),
    lee the leeward direction. A point's push is what it lacks, along its row's normal, spread over a few cells and faded
    to nothing at the fixed points. The floor (the roof, decks and nets) lifts the cloth the same way."""
    G = sheet.G
    P = G.reshape(-1, 3)
    F = P[sheet.fixed.reshape(-1)]
    d = np.min(np.linalg.norm(P[:, None, :] - F[None, :, :], axis=2), axis=1).reshape(G.shape[:2])
    hold = smooth01(d / HOLD_M)
    hold[sheet.fixed] = 0.0
    N = sheet.row_normals(lee)
    acc = np.zeros(G.shape[:2])
    for _ in range(rounds):
        need = np.zeros(G.shape[:2])
        ch = G[-1] - G[0]
        rlen = np.linalg.norm(ch, axis=1)[None, :]
        rdir = (ch / np.maximum(rlen[0], 1e-9)[:, None])[None, :, :]
        row0 = G[0][None, :, :]
        for a, b, r in segs:
            w = closest_on(G, a, b)
            q = G - w
            s = np.sum(q * N, axis=2)
            tang = np.linalg.norm(q - s[..., None] * N, axis=2)
            lack = (clr + r) - side * s
            wgt = np.exp(-(tang / sigma) ** 2)
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
        w = vspread
        pad = np.pad(acc, ((0, 0), (w, w)), mode="edge")
        dil = np.max(np.stack([pad[:, i:i + acc.shape[1]] for i in range(2 * w + 1)]), axis=0)
        k = np.exp(-0.5 * (np.arange(-2 * w, 2 * w + 1) / (w / 2)) ** 2)
        pad = np.pad(dil, ((0, 0), (2 * w, 2 * w)), mode="edge")
        sm = np.maximum(acc, np.array([np.convolve(r, k / k.sum(), mode="valid") for r in pad]) * hold)
        G += (side * (sm - acc))[..., None] * N
    return sheet


def triangles(sheet):
    G = sheet.G
    a, b, c, d = G[:-1, :-1].reshape(-1, 3), G[1:, :-1].reshape(-1, 3), G[1:, 1:].reshape(-1, 3), G[:-1, 1:].reshape(-1, 3)
    return np.vstack([a, a]), np.vstack([b, c]), np.vstack([c, d])


def crossings(sheet, a, b):
    """How many times the segment a-b passes through the cloth (Moller-Trumbore on every triangle)."""
    A, Bv, C = triangles(sheet)
    e1, e2 = Bv - A, C - A
    d = b - a
    h = np.cross(d, e2)
    det = np.sum(e1 * h, axis=1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = a - A
    u = np.sum(s * h, axis=1) * inv
    qv = np.cross(s, e1)
    v = (qv @ d) * inv
    t = np.sum(e2 * qv, axis=1) * inv
    return int(np.sum(ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= 1)))


def _seg_pts(P, a, b):
    ab = b - a
    ap = P[:, None, :] - a[None]
    t = np.clip(np.sum(ap * ab[None], axis=2) / np.maximum(np.sum(ab * ab, axis=1), 1e-18)[None], 0.0, 1.0)
    return np.linalg.norm(ap - t[..., None] * ab[None], axis=2)


def tri_dist(P, A, Bv, C):
    """The least distance from each point of P (m, 3) to the triangles A, B, C (k, 3 each)."""
    n = np.cross(Bv - A, C - A)
    nn = np.maximum(np.sum(n * n, axis=1), 1e-24)
    out = np.empty(len(P))
    for s in range(0, len(P), 64):
        Q = P[s:s + 64]
        ap = Q[:, None, :] - A[None]
        h = np.sum(ap * n[None], axis=2) / nn[None]
        X = Q[:, None, :] - h[..., None] * n[None]
        u = np.sum(np.cross(Bv - X, C - X) * n[None], axis=2) / nn[None]
        v = np.sum(np.cross(C - X, A - X) * n[None], axis=2) / nn[None]
        inside = (u >= 0) & (v >= 0) & (u + v <= 1) & (nn > 1e-14)[None]
        plane = np.abs(h) * np.sqrt(nn)[None]
        edge = np.minimum(np.minimum(_seg_pts(Q, A, Bv), _seg_pts(Q, Bv, C)), _seg_pts(Q, C, A))
        out[s:s + 64] = np.where(inside, plane, edge).min(axis=1)
    return out


def clearance(sheet, obstacles, floor=True):
    """{obstacle: least gap (m) from the cloth's triangles to it (-1 if it passes through)}, and to what is under the
    cloth ('Floor'). Each piece is sampled every centimetre and measured to every triangle near it."""
    A, Bv, C = triangles(sheet)
    lo = np.minimum(np.minimum(A, Bv), C)
    hi = np.maximum(np.maximum(A, Bv), C)
    out = {}
    for name, segs in obstacles.items():
        best = 1.0
        for a, b, r in segs:
            S_ = a + np.linspace(0.0, 1.0, max(2, int(np.linalg.norm(b - a) / 0.01) + 1))[:, None] * (b - a)
            near = np.all((lo < S_.max(axis=0) + 0.3) & (hi > S_.min(axis=0) - 0.3), axis=1)
            if not near.any():
                continue
            box_lo, box_hi = lo[near].min(axis=0) - 0.3, hi[near].max(axis=0) + 0.3
            S_ = S_[np.all((S_ > box_lo) & (S_ < box_hi), axis=1)]
            if not len(S_):
                continue
            if crossings(sheet, a, b):
                best = -1.0
                break
            best = min(best, tri_dist(S_, A[near], Bv[near], C[near]).min() - r)
        out[name] = best
    if floor:
        out["Floor"] = min(p[2] - floor_z(p[0], p[1]) for p in sheet.G.reshape(-1, 3))
    return out


def sharpest(sheet):
    """The largest second difference of the free cloth (m): no creases from press()."""
    G, free = sheet.G, ~sheet.fixed
    return max((np.linalg.norm(G[2:] - 2 * G[1:-1] + G[:-2], axis=2) * free[1:-1]).max(),
               (np.linalg.norm(G[:, 2:] - 2 * G[:, 1:-1] + G[:, :-2], axis=2) * free[:, 1:-1]).max())


# ------------------------------------------------------------------ the mainsail

def main_planform(hb, n=400):
    """The main's leech as chord at height v (metres up the luff from the tack): from the clew (E, 0) to the head's
    aft corner (hb, P), the roach out of the straight line between them."""
    s = np.linspace(0.0, 1.0, n)
    a, b = np.array([E_M, 0.0]), np.array([hb, P_M])
    out = unit(np.array([(b - a)[1], -(b - a)[0]]))
    if out[0] < 0:
        out = -out
    L = a + s[:, None] * (b - a) + (MS["roach"] * np.sin(np.pi * s))[:, None] * out
    return lambda h: np.interp(h, L[:, 1], L[:, 0])


def main_area(hb):
    v = np.linspace(0.0, P_M, 2001)
    c = main_planform(hb)(v)
    return float(np.sum(0.5 * (c[1:] + c[:-1]) * np.diff(v)))


def solve_head():
    lo, hi = 0.2, 4.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if main_area(mid) < MS["area"] else (lo, mid)
    return (lo + hi) / 2


HB = solve_head()


def reef_v(k):
    """How far up the luff (from the tack) reef k's cringles are (k = 1, 2, 3)."""
    return (1.0 - MS["reefs"][k - 1]) * P_M


def main_sheet(state, nu=36, nv=72):
    st = MS["states"][state]
    reef = reef_v(st["reef"]) if st.get("reef") else 0.0
    beta, twist = math.radians(st["boom_deg"]), math.radians(st["twist_deg"])
    depth, draft = table(st["depth"]), table(st["draft_at"])
    chord = main_planform(HB)
    rotb = boom_rot(beta)
    clew = rotb(np.array([LUFF_X - float(chord(reef)), 0.0, TACK_Z]))
    G = np.zeros((nu + 1, nv + 1, 3))
    UV = np.zeros((nu + 1, nv + 1, 6))
    flat = np.zeros((nu + 1, nv + 1, 2))
    vs = reef + (P_M - reef) * np.linspace(0.0, 1.0, nv + 1)
    fs = np.linspace(0.0, 1.0, nu + 1) ** 1.3
    bend = MS["luff_bend"]
    d0 = None
    for j, v in enumerate(vs):
        tau = (v - reef) / (P_M - reef)
        c = float(chord(v))
        L = np.array([LUFF_X, 0.0, TACK_Z + v - reef])
        phi = beta + twist * tau ** 1.3
        n = np.array([math.sin(phi), -math.cos(phi), 0.0])
        m, p = float(depth(tau)), float(draft(tau))
        ss = np.linspace(0.0, c, 400)
        th = phi * smooth01(ss / bend)
        dx = np.concatenate([[0.0], np.cumsum(-np.cos(0.5 * (th[1:] + th[:-1])) * np.diff(ss))])
        dy = np.concatenate([[0.0], np.cumsum(-np.sin(0.5 * (th[1:] + th[:-1])) * np.diff(ss))])
        end = L + np.array([dx[-1], dy[-1], 0.0])
        if d0 is None:
            d0 = clew - end                                  # the foot's row to the clew on the outhaul's car
        wf = float(smooth01(1.0 - tau / 0.06))
        for i, f in enumerate(fs):
            base = L + np.array([np.interp(f * c, ss, dx), np.interp(f * c, ss, dy), 0.0]) + d0 * (wf * f)
            G[i, j] = base + m * c * float(camber(f, p)) * n
            flat[i, j] = (f * c, v)
            UV[i, j] = (f * c, v, f * c / E_M, v / P_M, (1 - f) * c, 0.0)
    a, b = np.array([E_M, 0.0]), np.array([HB, P_M])
    nrm = unit(np.array([(b - a)[1], -(b - a)[0]]))
    if nrm[0] < 0:
        nrm = -nrm
    UV[..., 5] = -((flat - a) @ nrm)
    fixed = np.zeros((nu + 1, nv + 1), bool)
    fixed[0, :] = True
    fixed[-1, 0] = True
    sh = Sheet("Main" + state, G, UV, fixed, face=(0.0, 1.0, 0.0), flat=flat)
    sh.extras = {"beta": beta, "reef": reef, "chord": chord, "rotb": rotb, "clew": clew}
    return sh


def main_point(sh, f, v):
    """The point on a main's sheet at chord share f (of the planform's chord), planform height v."""
    vs = sh.UV[0, :, 1]
    fj = float(np.interp(v, vs, np.arange(len(vs))))
    fs = sh.flat[:, 0, 0] / max(sh.flat[-1, 0, 0], 1e-9)
    fi = float(np.interp(f, fs, np.arange(len(fs))))
    return sh.at(fi, fj)


def main_normal(sh, f, v, side=(0.0, 1.0, 0.0)):
    vs = sh.UV[0, :, 1]
    fj = float(np.interp(v, vs, np.arange(len(vs))))
    fs = sh.flat[:, 0, 0] / max(sh.flat[-1, 0, 0], 1e-9)
    fi = float(np.interp(f, fs, np.arange(len(fs))))
    return unit(sh.at(fi, fj, sh.normals(side)))


# ------------------------------------------------------------------ the headsails: one cut for the jib and the Code 0

def coons(F, Lc, Hd, Lu, f, t):
    """A planform point by the transfinite patch between the foot F(f), leech Lc(t), head Hd(f) and luff Lu(t)."""
    return ((1 - t) * F(f) + t * Hd(f) + (1 - f) * Lu(t) + f * Lc(t) -
            ((1 - f) * (1 - t) * F(0.0) + f * (1 - t) * F(1.0) + (1 - f) * t * Hd(0.0) + f * t * Hd(1.0)))


def headsail_plan(T, Hd, C, sp, head_w=0.04):
    """The flat sail: its basis (e1 square to the luff toward the clew, e2 up the luff) and its edges in it."""
    e2 = unit(Hd - T)
    e1 = unit((C - T) - e2 * ((C - T) @ e2))
    Lluff = float(np.linalg.norm(Hd - T))
    c2 = np.array([(C - T) @ e1, (C - T) @ e2])
    h2 = np.array([head_w, Lluff])
    l2 = np.array([0.0, Lluff])
    foot_len, leech_len = float(np.linalg.norm(c2)), float(np.linalg.norm(h2 - c2))
    nf = unit(np.array([c2[1], -c2[0]]))                    # square to the foot, away from the head
    if nf[1] > 0:
        nf = -nf
    nl = unit(np.array([(h2 - c2)[1], -(h2 - c2)[0]]))      # square to the leech, away from the luff
    if nl[0] < 0:
        nl = -nl
    F = lambda f: f * c2 + sp["foot_round"] * foot_len * math.sin(math.pi * f) * nf
    Lc = lambda t: c2 + t * (h2 - c2) + sp["leech_roach"] * leech_len * math.sin(math.pi * t) * nl
    Hf = lambda f: l2 + f * (h2 - l2)
    Lu = lambda t: np.array([0.0, t * Lluff])
    return e1, e2, Lluff, c2, h2, nl, F, Lc, Hf, Lu


def headsail_area(T, Hd, C, sp, n=200):
    _, _, _, _, _, _, F, Lc, Hf, Lu = headsail_plan(T, Hd, C, sp)
    edge = [Lu(1 - k / n) for k in range(n)] + [F(k / n) for k in range(n)] + [Lc(k / n) for k in range(n)] + \
           [Hf(1 - k / n) for k in range(n)]
    e = np.array(edge)
    return 0.5 * abs(float(np.sum(e[:, 0] * np.roll(e[:, 1], -1) - np.roll(e[:, 0], -1) * e[:, 1])))


def headsail_sheet(name, T, Hd, C, sp, nu=32, nv=64, sag=None, lee=LEE):
    """A headsail's cloth from its tack T, head Hd and clew C (game frame): the planform's rows parallel to the foot,
    each turned about the luff by its twist and cambered to leeward; sag(t) shifts each row with its luff (a Code 0's
    luff sags off the straight line under load)."""
    e1, e2, Lluff, c2, h2, nl, F, Lc, Hf, Lu = headsail_plan(T, Hd, C, sp)
    twist = math.radians(sp["twist_deg"])
    depth, draft = table(sp["depth"]), table(sp["draft_at"])
    fs = np.linspace(0.0, 1.0, nu + 1)
    ts = np.linspace(0.0, 1.0, nv + 1)
    G = np.zeros((nu + 1, nv + 1, 3))
    UV = np.zeros((nu + 1, nv + 1, 6))
    flat = np.array([[coons(F, Lc, Hf, Lu, f, t) for t in ts] for f in fs])
    sgn = 1.0 if rotate(e1, e2, 0.1) @ lee > e1 @ lee else -1.0     # the twist that opens the leech to leeward
    for j, t in enumerate(ts):
        ang = sgn * twist * t ** sp.get("twist_power", 1.3)
        rows = np.array([rotate(flat[i, j][0] * e1, e2, ang) + flat[i, j][1] * e2 for i in range(nu + 1)])
        ch = rows[-1] - rows[0]
        c = float(np.linalg.norm(flat[-1, j] - flat[0, j]))
        n = unit(np.cross(e2, ch)) if np.linalg.norm(ch) > 1e-6 else lee
        if n @ lee < 0:
            n = -n
        m, pd = float(depth(t)), float(draft(t))
        off = sag(t) if sag else 0.0
        for i, f in enumerate(fs):
            G[i, j] = T + rows[i] + m * c * float(camber(f, pd)) * n + off
            UV[i, j, 0:4] = (flat[i, j][0] - flat[0, j][0], flat[i, j][1], f, t)
            UV[i, j, 4] = float(np.linalg.norm(flat[-1, j] - flat[i, j]))
    UV[..., 5] = -((flat - c2) @ nl)
    fixed = np.zeros((nu + 1, nv + 1), bool)
    fixed[0, :] = True
    fixed[-1, 0] = True
    fixed[:, -1] = True
    sh = Sheet(name, G, UV, fixed, face=(0.0, 1.0, 0.0), flat=flat)
    sh.extras = {"T": T, "H": Hd, "C": C, "e1": e1, "e2": e2, "c2": c2, "h2": h2, "luff": Lluff, "F": F, "Lc": Lc}
    return sh


def solve_clew_x(T, Hd, y, z, sp, lo, hi):
    """The clew's x (its y and z given) that gives the sail its area."""
    for _ in range(50):
        mid = (lo + hi) / 2
        a = headsail_area(T, Hd, np.array([mid, y, z]), sp)
        lo, hi = (mid, hi) if a > sp["area"] else (lo, mid)
    return (lo + hi) / 2


def stay_aft():
    """The unit vector square to the forestay in the centreplane, pointing aft (the foil's groove faces it)."""
    d = unit(np.array(R.hounds_pin()) - np.array(R.forestay_tack()))
    return unit(np.cross(d, np.array([0.0, 1.0, 0.0])))


def jib_corners():
    head_eye, hal_eye, tack_eye = (np.array(p) for p in R.forestay_eyes())
    aft = stay_aft()
    if aft[0] > 0:
        aft = -aft
    d = unit(np.array(R.hounds_pin()) - np.array(R.forestay_tack()))
    on = lambda p: np.array(R.forestay_at(float(p[2]))) + aft * JB["luff_aft_of_stay"]
    T = on(np.array([0.0, 0.0, tack_eye[2] + JB["tack_above_eye"] * d[2]]))
    Hd = on(np.array([0.0, 0.0, head_eye[2] - JB["head_below_eye"] * d[2]]))
    y, z = JB["clew"]
    x = solve_clew_x(T, Hd, y, z, JB, -0.5, 3.0)
    return T, Hd, np.array([x, y, z]), tack_eye, head_eye


def jib_sheet():
    T, Hd, C, _, _ = jib_corners()
    return headsail_sheet("JibSet", T, Hd, C, JB)


def code0_corners():
    tip = np.array([B.SP["tip_x"], 0.0, B.CB["z"] + B.SP["rise"] + B.SP["tip_radius"]])
    dr = C0["drum"]
    xd = B.SP["tip_x"] - dr["in_from_tip"]
    _, az, ar = B.bowsprit_axis((xd - B.CB["x"]) / (B.SP["tip_x"] - B.CB["x"]))
    drum0 = np.array([xd, 0.0, az + ar + dr["over_tip"]])
    T = drum0 + np.array([0.0, 0.0, dr["height"] + C0["tack_over_drum"]])
    zb = R.MH["code0_z"]
    Hd = np.array([R.front_x(zb) + C0["head_out"], 0.0, zb - C0["head_below_box"]])
    y, z = C0["clew"]
    x = solve_clew_x(T, Hd, y, z, C0, -4.0, 4.0)
    return T, Hd, np.array([x, y, z]), tip, drum0


def code0_sag(T, Hd, share=1.0):
    e2 = unit(Hd - T)
    aft = unit(np.array([-1.0, 0.0, 0.0]) - e2 * (e2 @ np.array([-1.0, 0.0, 0.0])))
    s_lee, s_aft = C0["luff_sag"]
    return lambda t: share * math.sin(math.pi * t) * (s_lee * LEE + s_aft * aft)


def code0_sheet():
    T, Hd, C, _, _ = code0_corners()
    return headsail_sheet("Code0Set", T, Hd, C, C0, nu=40, nv=64, sag=code0_sag(T, Hd),
                          lee=unit(np.array([0.2, -1.0, 0.0])))


def mid_girth(sh):
    """The distance from the luff's middle to the leech's middle in the flat sail, and the foot's length."""
    Lu = sh.extras["luff"]
    mid_l = np.array([0.0, Lu / 2])
    mid_r = sh.extras["Lc"](0.5)
    return float(np.linalg.norm(mid_r - mid_l)), float(np.linalg.norm(sh.extras["c2"]))


# ------------------------------------------------------------------ furled rolls

def roll(sh, r0, t_mm, axis_pts):
    """A headsail rolled round its luff: for stations up the luff (shares s of its length), the roll's radius and the
    angle its outer edge has turned through. The cloth wrapped at a station is the flat sail's width square to the luff
    there (the foot below the clew's station, the leech above), wound in turns of the cloth's thickness times the
    roll's bulk. axis_pts(s) is the roll's axis. Returns (stations, axis points, radii, edge angles, clew's station)."""
    Lu = sh.extras["luff"]
    F, Lc = sh.extras["F"], sh.extras["Lc"]
    edge = np.array([F(k / 200) for k in range(201)] + [Lc(k / 200) for k in range(1, 201)])
    yc = sh.extras["c2"][1]
    ss = np.concatenate([np.linspace(0.0, yc, 30, endpoint=False), np.linspace(yc, Lu, 80)])
    w = np.interp(ss, edge[:, 1], edge[:, 0])
    t = t_mm / 1000 * CL["bulk_rolled"]
    r = np.sqrt(r0 * r0 + w * t / math.pi)
    th = w / (0.5 * (r0 + r))
    return ss / Lu, np.array([axis_pts(s / Lu) for s in ss]), r, th, yc / Lu


# ------------------------------------------------------------------ the lazy bag (boom frame at 0: on the centreline)

def bag_share(x):
    x0, x1 = BG["x"]
    return float(np.clip((x0 - x) / (x0 - x1), 0.0, 1.0))


def lerp2(ab, f):
    return ab[0] + (ab[1] - ab[0]) * f


def bag_zipped_section(x, n=32):
    """The zipped bag's section at x: (y, z) round it, from the boom's starboard side up over the zip and down to port,
    then across inside the boom. A superellipse loaf that narrows to the boom's sides where it is laced to them."""
    f = bag_share(x)
    h, w = lerp2(BG["zipped"]["height"], f), lerp2(BG["zipped"]["half_width"], f)
    z0 = BOOM_TOP - BG["wrap"]
    zc = BOOM_TOP + 0.42 * h
    hh = h - 0.42 * h
    bw = R.BO["width"] / 2 + BG["thick"]
    pts = []
    for k in range(n):
        a = -math.pi / 2 + 2 * math.pi * k / n                # from the bottom, starboard first
        c, s = math.cos(a), math.sin(a)
        y = w * math.copysign(abs(c) ** 0.75, c)
        top = s > 0
        z = zc + (hh if top else (zc - z0)) * math.copysign(abs(s) ** (0.9 if top else 0.6), s)
        if top:
            z += 0.012 * math.exp(-(y / 0.03) ** 2)           # the zip's ridge
        if z < BOOM_TOP + 0.02:
            y = math.copysign(max(abs(y), bw), y if abs(y) > 1e-9 else 1.0)
        pts.append((y, max(z, z0)))
    return pts, h, w


def bag_open_dims(x):
    """(lip height over the boom's top, lip half width) of the open bag at x: drooping between the jacks' points."""
    f = bag_share(x)
    h, w = lerp2(BG["open"]["height"], f), lerp2(BG["open"]["half_width"], f)
    pts = [BG["x"][0]] + BG["jack_points"] + [BG["x"][1]]
    for a, b in zip(pts[:-1], pts[1:]):
        if b <= x <= a:
            k = 1.4 if a == BG["x"][0] or b == BG["x"][1] else 1.0
            h -= k * BG["open"]["droop"] * math.sin(math.pi * (a - x) / (a - b))
    return h, w


def bag_open_section(x, n_side=10):
    """The open bag's cloth (its thickness) at x as one closed ring: up the outer starboard side, round its hemmed lip,
    down the inner side, across the bottom, up and over the port side, and across inside the boom."""
    h, w = bag_open_dims(x)
    th = BG["thick"]
    z0 = BOOM_TOP - BG["wrap"]
    bw = R.BO["width"] / 2 + th
    zl = BOOM_TOP + h

    def side(u, inset):
        y = bw + (w - bw) * u ** 0.6 - inset
        z = z0 + (zl - z0) * u
        return y, z
    star = [side(k / n_side, 0.0) for k in range(n_side + 1)]
    lip = [(w + 0.006 * math.cos(a) - 0.004, zl + 0.006 * math.sin(a)) for a in (math.pi * k / 4 for k in range(1, 4))]
    inner = [side(1 - k / n_side, th) for k in range(n_side + 1)]
    inner[-1] = (inner[-1][0], BOOM_TOP + 0.003)
    half = star + lip + inner
    ring = half + [(-y, z) for y, z in half[::-1]]
    ring += [(-bw, z0 - 0.005), (bw, z0 - 0.005)]
    return ring, h, w


def bag_jack_points(state):
    """The lazy jacks' points on the bag, boom frame at 0: {side: [(x, y, z) forward to aft]}. Zipped: rings either
    side of the zip on its top; open: on each side's lip."""
    out = {}
    for s in (1, -1):
        pts = []
        for x in BG["jack_points"]:
            if state == "Zipped":
                _, h, _ = bag_zipped_section(x)
                pts.append(np.array([x, s * 0.05, BOOM_TOP + h + 0.005]))
            else:
                h, w = bag_open_dims(x)
                pts.append(np.array([x, s * (w - 0.004), BOOM_TOP + h + 0.016]))
        out[s] = pts
    return out


def jack_tree(top, pts):
    """One side's lazy jack: the line from the mast's block to ring A, which splits into a leg to the forward point and
    a line to ring B, which splits to the middle and aft points. Returns [(a, b) legs], A, B."""
    P1, P2, P3 = pts
    Bp = (P2 + P3) / 2 + np.array([0.0, 0.0, 1.0])
    for _ in range(8):
        A = (P1 + Bp) / 2 + LJ["ring_A"] * (top - (P1 + Bp) / 2)
        Bp = (P2 + P3) / 2 + LJ["ring_B"] * (A - (P2 + P3) / 2)
    return [(top, A), (A, P1), (A, Bp), (Bp, P2), (Bp, P3)], A, Bp


def drape(pts, sheet, side_dir, clr):
    """A line's points kept clr on the side_dir side of the cloth wherever it passes over it (a lazy jack lying on the
    sail), its ends held."""
    P = np.array(pts, float)
    G = sheet.G.reshape(-1, 3)
    N = sheet.normals(side_dir).reshape(-1, 3)
    nu, nv = sheet.nu, sheet.nv
    ii, jj = np.meshgrid(np.arange(nu + 1), np.arange(nv + 1), indexing="ij")
    inner = ((ii > 0) & (ii < nu) & (jj > 0) & (jj < nv)).reshape(-1)
    for _ in range(6):
        d = np.linalg.norm(P[:, None, :] - G[None], axis=2)
        k = d.argmin(axis=1)
        g, n = G[k], N[k]
        s = np.sum((P - g) * n, axis=1)
        lack = np.where(inner[k] & (d[np.arange(len(P)), k] < 1.0), np.maximum(0.0, clr - s), 0.0)
        lack[0] = lack[-1] = 0.0
        P += lack[:, None] * n
        Q = P.copy()
        Q[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
        P = Q
        P[0], P[-1] = pts[0], pts[-1]
    return P


# ------------------------------------------------------------------ all of them

def set_sheets():
    """{name: Sheet} for every set state, pressed clear of what it would touch."""
    rs = rig_segments()
    lee_rig = [seg for n in ("Cap_P", "Lower_P", "Spreader_P") for seg in rs[n]]
    out = {}
    for st in ("Set", "Reach", "Reefed"):
        out["Main" + st] = press(main_sheet(st), lee_rig, LEE, -1, floor=False)
    run = main_sheet("Run")
    b = run.extras["beta"]
    out["MainRun"] = press(run, lee_rig, np.array([math.sin(b), -math.cos(b), 0.0]), -1, clr=0.03, floor=False, vspread=4)
    out["JibSet"] = press(jib_sheet(), [], LEE, -1)
    c0 = code0_sheet()
    fs_ = rs["Forestay"]
    out["Code0Set"] = press(c0, [seg for n in ("Cap_P", "Lower_P", "Spreader_P", "Mast") for seg in rs[n]] + fs_,
                            unit(np.array([0.2, -1.0, 0.0])), +1, sigma=0.5, vspread=6, clr=0.05)
    return out


def bag_inside_gap(sh):
    """The least gap (m) between a main's cloth and its open bag's inner sides, over the rows inside the bag (in the
    boom's frame: the cloth turned back by the boom's angle)."""
    back = boom_rot(-sh.extras["beta"])
    P = back(sh.G.reshape(-1, 3))
    worst = 1.0
    for p in P:
        if not (BG["x"][1] < p[0] < BG["x"][0] - 0.05):
            continue
        h, w = bag_open_dims(p[0])
        if p[2] > BOOM_TOP + h:
            continue
        u = (p[2] - (BOOM_TOP - BG["wrap"])) / (h + BG["wrap"])
        y_in = R.BO["width"] / 2 + BG["thick"] + (w - R.BO["width"] / 2 - BG["thick"]) * max(u, 0.0) ** 0.6 - BG["thick"]
        worst = min(worst, y_in - abs(p[1]))
    return worst


# ------------------------------------------------------------------ parts: small makers (game frame)

def p_rope(pts, r, mat="Rope", sides=8):
    pts = [tup(p) for p in pts]
    return {"kind": "rings", "rings": R.tube(pts, r, sides), "mat": mat, "smooth": True}


def p_torus(c, axis, Rr, r, mat="Stainless", n=None, m=6):
    n = n or (12 if Rr < 0.02 else 16)      # small rings and cringles: 12 round
    return {"kind": "torus", "centre": tup(c), "axis": tup(unit(axis)), "R": Rr, "r": r, "mat": mat, "n": n, "m": m}


def p_cyl(a, b, r, mat, seg=12):
    return {"kind": "cyl", "a": tup(a), "b": tup(b), "radius": r, "mat": mat, "segments": seg}


def p_block(c, u, v, w, size, mat, rnd=0.004):
    """A rounded box centred at c: size[0] along u, size[1] along v (its rounded profile), size[2] along w."""
    c, u, v, w = (np.asarray(a, float) for a in (c, u, v, w))
    prof = R.rrect(size[0], size[1], min(rnd, size[0] / 2 - 1e-4, size[1] / 2 - 1e-4))
    return {"kind": "rings", "mat": mat, "smooth": False,
            "rings": [[tup(c + w * z + u * a + v * b) for a, b in prof] for z in (-size[2] / 2, size[2] / 2)]}


def p_kit(name, origin, ax, az, **kw):
    k = R.kit(name, tup(origin), tup(unit(ax)), tup(unit(az)), **kw)
    return k


def p_heap(path, half_w, half_h, seed, n=16, lump=0.12, fold=0.0, fold_len=0.3, mat="ClothMainHeap", layers=0,
           layer_amp=0.0):
    """A soft heap of cloth along a path (game frame points): at each point an oval half_w across and half_h tall, its
    bottom flat at the path's z, its outline bent in slow waves that wander along it (cloth, not noise); `fold` bulges
    its sides every fold_len (a heap's gathers), `layers` stacks flakes up its sides."""
    rng = np.random.default_rng(seed)
    P = np.asarray(path, float)
    knots = max(2, len(P) // 4 + 2)
    keys = np.concatenate([rng.uniform(-1, 1, (knots, 4)), rng.uniform(0, 2 * math.pi, (knots, 2))], axis=1)
    rings = []
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    for k, p in enumerate(P):
        u = k / max(len(P) - 1, 1) * (knots - 1)
        i = min(int(u), knots - 2)
        f = float(smooth01(u - i))
        a1, a2, h1, h2, p1, p2 = keys[i] + (keys[i + 1] - keys[i]) * f
        t = P[min(k + 1, len(P) - 1)] - P[max(k - 1, 0)]
        t[2] = 0.0
        t = unit(t)
        side = np.array([-t[1], t[0], 0.0])
        fl = 1 + fold * math.sin(2 * math.pi * s[k] / fold_len)
        ring = []
        for j in range(n):
            th = 2 * math.pi * j / n - math.pi / 2
            c, sn = math.cos(th), math.sin(th)
            wob = 1 + lump * (a1 * math.sin(2 * th + p1) + 0.6 * a2 * math.sin(3 * th + p2))
            wid = half_w[k] * fl * wob * (1 + 0.12 * max(0.0, -sn))
            if layers and sn > -0.3:
                band = (sn + 0.3) / 1.3 * layers
                wid *= 1 + layer_amp * (abs(math.sin(math.pi * band)) - 0.5)
            z = (sn + 1) * half_h[k] * (1 + lump * 0.5 * (h1 * math.cos(th + p1) + 0.5 * h2))
            if sn < -0.6:
                z = min(z, 0.15 * half_h[k])
            ring.append(tup(p + side * (c * wid) + np.array([0.0, 0.0, z])))
        rings.append(ring)
    return {"kind": "rings", "rings": rings, "mat": mat, "smooth": True}


def p_cloth(sh, mat):
    return {"kind": "cloth", "G": sh.G.tolist(), "UV": sh.UV.tolist(), "face": tup(sh.face), "mat": mat}


def layer_rows(sh, fis, fjs, side, off):
    """Rows of the cloth at fractional indices (fis[k], fjs[k] are lists, one per row), offset off along its normals
    toward side: a sewn-on layer (a patch, a UV strip)."""
    N = sh.normals(side)
    rows = []
    for fi_row, fj_row in zip(fis, fjs):
        rows.append([tup(sh.at(a, b) + unit(sh.at(a, b, N)) * off) for a, b in zip(fi_row, fj_row)])
    return rows


def p_layer(rows, side, mat):
    mid = rows[len(rows) // 2][len(rows[0]) // 2]
    return {"kind": "layer", "rows": rows, "probe": mid, "face": tup(side), "mat": mat}


def corner_patch(sh, corner, a, b, mat="SailPatch", n=8, off=0.002, sides=(1, -1)):
    """A reinforcing patch at a corner, both faces: a quarter ellipse a cells along the rows and b cells up (or down)
    the sail from the corner ('tack', 'clew', 'head', 'head_aft')."""
    i0, j0, di, dj = {"tack": (0, 0, 1, 1), "clew": (sh.nu, 0, -1, 1), "head": (0, sh.nv, 1, -1),
                      "head_aft": (sh.nu, sh.nv, -1, -1)}[corner]
    fis, fjs = [], []
    for k in range(n + 1):
        u = 0.98 * k / n
        e = a * math.sqrt(1 - u * u)
        fjs.append([j0 + dj * b * u] * (n + 1))
        fis.append([i0 + di * e * m / n for m in range(n + 1)])
    out = []
    for s in sides:
        side = sh.face * s
        out.append(p_layer(layer_rows(sh, fis, fjs, side, off), side, mat))
    return out


def edge_patch(sh, edge, fj, a, b, mat="SailPatch", n=8, off=0.002):
    """A half-ellipse patch on the luff (edge 0) or the leech (edge 1) about row fj (fractional), a cells in, b cells up
    and down: under a reef's cringle."""
    i0, di = (0, 1) if edge == 0 else (sh.nu, -1)
    fis, fjs = [], []
    for k in range(n + 1):
        u = -1 + 2 * k / n
        e = a * math.sqrt(max(0.0, 1 - (0.98 * u) ** 2))
        fjs.append([fj + b * u] * (n + 1))
        fis.append([i0 + di * e * m / n for m in range(n + 1)])
    return [p_layer(layer_rows(sh, fis, fjs, sh.face * s, off), sh.face * s, mat) for s in (1, -1)]


def strip_layers(sh, w_leech, w_foot, off, mat="SailUV", n=6):
    """The UV strip on the cloth's starboard face: along the leech w_leech wide (square to it) and the foot w_foot."""
    side = sh.face
    UV5, flat = sh.UV[..., 5], sh.flat
    fis, fjs = [], []
    for j in range(sh.nv + 1):
        d = UV5[:, j] - UV5[-1, j]                    # in from the leech, square to it
        ii = np.arange(sh.nu + 1)
        i_w = float(np.interp(w_leech, d[::-1], ii[::-1])) if d[0] > w_leech else 0.0
        fis.append([i_w + (sh.nu - i_w) * m / n for m in range(n + 1)])
        fjs.append([float(j)] * (n + 1))
    out = [p_layer(layer_rows(sh, fis, fjs, side, off), side, mat)]
    c = flat[-1, 0] - flat[0, 0]
    up = unit(np.array([-c[1], c[0]]))
    if up[1] < 0:
        up = -up
    fis, fjs = [], []
    for m in range(n + 1):
        jw = []
        for i in range(sh.nu + 1):
            d = (flat[i, :] - flat[i, 0]) @ up
            jw.append(float(np.interp(w_foot, d, np.arange(sh.nv + 1))))
        fjs.append([jw[i] * m / n for i in range(sh.nu + 1)])
        fis.append([float(i) for i in range(sh.nu + 1)])
    out.append(p_layer(layer_rows(sh, fis, fjs, side, off * 1.4), side, mat))
    return out


def sheet_normal(sh, fi, fj, side=None):
    return unit(sh.at(fi, fj, sh.normals(sh.face if side is None else side)))


def into_sail(sh, corner_fi, corner_fj, toward_fi, toward_fj, d):
    """A point d metres into the sail from a corner, toward another grid place."""
    p = sh.at(corner_fi, corner_fj)
    q = sh.at(toward_fi, toward_fj)
    return p + unit(q - p) * d


def ring_at(sh, fi, fj, ti, tj, d, Rr, r, mat="Stainless"):
    """A cringle or corner ring d into the sail toward (ti, tj), lying in the cloth."""
    c = into_sail(sh, fi, fj, ti, tj, d)
    return p_torus(c, sheet_normal(sh, fi, fj), Rr, r, mat, 18, 6), c


# ------------------------------------------------------------------ the mainsail's trims

def fi_of(sh, f):
    fs = sh.flat[:, 0, 0] / max(sh.flat[-1, 0, 0], 1e-9)
    return float(np.interp(f, fs, np.arange(len(fs))))


def fj_of(sh, v):
    vs = sh.UV[0, :, 1]
    return float(np.interp(v, vs, np.arange(len(vs))))


def luff_stations(reef=0.0):
    """Up the luff from the tack (planform heights): ('car', v) at each batten, ('slide', v) between them
    slide_spacing apart, ('head', v) at the head; reef cringles' heights are left clear."""
    out = []
    bats = [h * P_M for h in MS["battens"]]
    edges = [MS["foot_over_boom"] + (R.MS["track"]["z"][0] - BOOM_TOP - MS["foot_over_boom"]) + 0.05] + bats
    for a, b in zip(edges[:-1], edges[1:]):
        n = max(1, int(round((b - a) / MS["slide_spacing"])))
        for k in range(1 if a in bats else 0, n):
            v = a + (b - a) * k / n
            if all(abs(v - reef_v(q)) > 0.09 for q in (1, 2, 3)):
                out.append(("slide", v))
        out.append(("car", b))
    out.append(("head", P_M))
    return [(k, v) for k, v in out if v > reef + 0.04]


TRACK_AFT = R.aft_x() - R.MS["track"]["depth"]


def track_car(kind, z, toward):
    """A slide or batten car on the track at z, and its webbing aft to the luff (toward: the luff's point)."""
    P = []
    xa = TRACK_AFT
    if kind == "slide":
        P.append(p_block((xa + 0.004, 0.0, z), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.026, 0.03, 0.055), "BlackPlastic", 0.006))
        P.append(p_block(((xa - 0.006 + toward[0]) / 2, 0.0, z), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                         (abs(toward[0] - xa) + 0.006, 0.008, 0.02), "Webbing", 0.002))
    elif kind == "car":
        P.append(p_block((xa + 0.002, 0.0, z), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.03, 0.044, 0.13), "Aluminium", 0.008))
        for dz in (-0.045, 0.045):
            P.append(p_cyl((xa + 0.016, -0.026, z + dz), (xa + 0.016, 0.026, z + dz), 0.009, "BlackPlastic", 12))
        P.append(p_block((xa - 0.022, 0.0, z), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.03, 0.03, 0.06), "Stainless", 0.006))
    else:                                               # the headboard car: long, with a link to the headboard
        P.append(p_block((xa + 0.002, 0.0, z - 0.11), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.03, 0.046, 0.3), "Aluminium", 0.01))
        for dz in (-0.22, -0.11, 0.0):
            P.append(p_cyl((xa + 0.016, -0.027, z + dz), (xa + 0.016, 0.027, z + dz), 0.009, "BlackPlastic", 12))
        P.append(p_block(((xa - 0.01 + toward[0]) / 2, 0.0, z - 0.12), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                         (abs(toward[0] - xa) + 0.012, 0.016, 0.2), "Stainless", 0.004))
    return P


def batten_parts(sh, v):
    """A full batten's pocket along the row at planform height v, luff to leech, both faces, its receptacle at the luff
    and the tensioner's cover at the leech."""
    P = []
    fj = fj_of(sh, v)
    hw = MS["batten_pocket_w"] / 2
    fj_w = hw / (sh.UV[0, 1, 1] - sh.UV[0, 0, 1])
    rings = []
    prof = ((-1, 0), (-0.75, -1), (0.75, -1), (1, 0), (0.75, 1), (-0.75, 1))    # flat faces, its edges sewn down
    for f in np.linspace(0.015, 0.995, 20):
        fi = fi_of(sh, f)
        p = sh.at(fi, fj)
        up = unit(sh.at(fi, fj + 0.3) - sh.at(fi, fj - 0.3))
        n = sheet_normal(sh, fi, fj)
        rings.append([tup(p + up * (hw * a) + n * (0.0045 * b)) for a, b in prof])
    P.append({"kind": "rings", "rings": rings, "mat": "SailPatch", "smooth": True})
    a, b = sh.at(fi_of(sh, 0.0), fj), sh.at(fi_of(sh, 0.035), fj)
    P.append(p_cyl(a + unit(b - a) * 0.01, b, 0.012, "BlackPlastic", 12))
    e0, e1 = sh.at(fi_of(sh, 0.97), fj), sh.at(sh.nu, fj)
    up = unit(sh.at(sh.nu, fj + 0.3) - sh.at(sh.nu, fj - 0.3))
    n = sheet_normal(sh, sh.nu, fj)
    u = unit(e1 - e0)
    P.append(p_block((e0 + e1) / 2, u, up, n, (float(np.linalg.norm(e1 - e0)) + 0.01, 2 * hw + 0.02, 0.012), "Webbing", 0.004))
    return P, fj_w


def main_trim(sh, state):
    """Every trim of a hoisted main: tapes, battens, cars and slides, the headboard, patches, cringles, clew and tack,
    the reef lines and the halyard."""
    P = []
    G = sh.G
    reef = sh.extras["reef"]
    P.append(p_rope(G[0, :], 0.007, "SailTape", 8))
    P.append(p_rope(G[-1, :], 0.0035, "SailTape", 6))
    P.append(p_rope(G[:, 0], 0.0045, "SailTape", 6))
    P.append(p_rope(G[:, -1], 0.006, "SailTape", 8))
    for h in MS["battens"]:
        v = h * P_M
        if v > reef + 0.15:
            P += batten_parts(sh, v)[0]
    # the cars and slides up the track, each to its place on the luff
    for kind, v in luff_stations(reef):
        z = TACK_Z + v - reef
        luff = sh.at(0, fj_of(sh, v))
        P += track_car(kind, z, luff)
    # the headboard: a plate each side of the head's forward corner, riveted through
    top = sh.nv
    hb_i = fi_of(sh, 0.32 / float(sh.extras["chord"](P_M)))
    out_fv = [(hb_i * a, top - 1.35 * b) for a, b in
              ((0.0, 0.0), (1.0, 0.0), (1.0, 0.25), (0.55, 0.85), (0.0, 1.0))]
    for s in (1, -1):
        side = sh.face * s
        N = sh.normals(side)
        rings = [[tup(sh.at(a, b) + unit(sh.at(a, b, N)) * d) for a, b in out_fv] for d in (0.002, 0.006)]
        P.append({"kind": "rings", "rings": rings, "mat": "Aluminium", "smooth": False})
    head = np.array([LUFF_X, 0.0, MS["head_z"] - reef])
    P.append(p_torus(head + np.array([0.012, 0.0, 0.06]), (0, 1, 0), 0.016, 0.005))
    P.append(p_rope([R.main_halyard_from(), head + np.array([0.012, 0.0, 0.075])], R.HL["rope"]["halyard"] / 2))
    # patches at the corners and under the reefs' cringles; the cringles; the clew's and tack's rings
    P += corner_patch(sh, "clew", 6.5, 6)
    P += corner_patch(sh, "tack", 6, 4)
    P += corner_patch(sh, "head", 7, 5)
    P += corner_patch(sh, "head_aft", 5, 4)
    for k in (1, 2, 3):
        v = reef_v(k)
        if v <= reef + 0.05:
            continue
        fj = fj_of(sh, v)
        for edge in (0, 1):
            P += edge_patch(sh, edge, fj, 3.0, 1.2)
            i0, ti = (0, 3) if edge == 0 else (sh.nu, sh.nu - 3)
            P.append(ring_at(sh, i0, fj, ti, fj, 0.05, 0.022, 0.006)[0])
    P.append(p_torus(sh.extras["clew"], sh.extras["rotb"](np.array([0.0, 1.0, 0.0]) + PIN) - PIN, 0.028, 0.007))
    P.append(ring_at(sh, 0, 0, 2, 2, 0.04, 0.024, 0.006)[0])
    tk = np.array([LUFF_X - 0.004, 0.0, BOOM_TOP + 0.012])
    P.append(p_torus(tk, (0, 1, 0), 0.02, 0.005))
    # the reef lines: out of the boom's top, up through the leech's cringle and down to their dead ends
    rotb = sh.extras["rotb"]
    for k, ((sx, sy, sz), (ex, ey, ez)) in zip((1, 2), R.reef_exits()[:MS["reef_lines"]]):
        v = reef_v(k)
        out_pt, dead = rotb(np.array([sx, sy, sz])), rotb(np.array([ex, ey, ez]))
        if v <= reef + 0.05:                           # this reef is tied in: its cringle is on the boom
            c = sh.at(sh.nu, 0) + np.array([0.0, 0.0, 0.02])
        else:
            c = into_sail(sh, sh.nu, fj_of(sh, v), sh.nu - 3, fj_of(sh, v), 0.05)
        n = sheet_normal(sh, sh.nu, fj_of(sh, v) if v > reef + 0.05 else 0)
        P.append(p_rope([out_pt, c - n * 0.01, c + np.array([0.0, 0.0, 0.03]), c + n * 0.01, dead], 0.006))
    return P


def jack_lines(top_pts, bag_pts, rotb, sheet=None, lee=LEE):
    """The lazy jacks (both sides) from their mast blocks to the bag's points (boom frame at 0, turned by rotb), the lee
    ones draped round the sail when it is up. Returns parts."""
    P = []
    r = R.FM["lazy_jack_rope"] / 2
    for s in (1, -1):
        pts = [rotb(p) for p in bag_pts[s]]
        legs, A, Bp = jack_tree(np.array(top_pts[s]), pts)
        for a, b in legs:
            n = max(2, int(np.linalg.norm(b - a) / 0.08))
            line = [a + (b - a) * k / n for k in range(n + 1)]
            if sheet is not None:
                side_dir = lee if s < 0 else -lee
                line = drape(line, sheet, side_dir, r + 0.012)
            P.append(p_rope(line, r, "Rope", 6))
        for c in (A, Bp):
            P.append(p_torus(c, (1, 0, 0), 0.012, 0.0035))
    return P


def open_bag_on(beta):
    return bag_jack_points("Open"), boom_rot(beta)


def bunt_parts(beta, reef):
    """The reef's bunt: the lower panel lying folded in the open bag along the boom (turned by the boom's angle)."""
    rotb = boom_rot(beta)
    xs = np.linspace(BG["x"][0] - 0.12, BG["x"][1] + 0.12, 30)
    hw, hh = [], []
    for x in xs:
        h, w = bag_open_dims(x)
        hw.append(0.75 * (R.BO["width"] / 2 + (w - R.BO["width"] / 2) * 0.35 ** 0.6))
        hh.append(0.5 * min(0.2, 0.32 * h))
    path = [rotb(np.array([x, 0.0, BOOM_TOP + 0.004])) for x in xs]
    return [p_heap(path, hw, hh, seed=7, lump=0.18, fold=0.1, fold_len=0.5, mat="ClothMain")]


def main_state_parts(sh, state):
    P = [p_cloth(sh, "ClothMain")] + main_trim(sh, state)
    beta, reef = sh.extras["beta"], sh.extras["reef"]
    _, tops = R.lazy_jack_parts()
    P += jack_lines(tops, bag_jack_points("Open"), boom_rot(beta), sh)
    if reef:
        P += bunt_parts(beta, reef)
        P += slide_stack(reef_count(reef))[0]
    _, _, low, top = R.traveller_parts()
    P += R.mainsheet_tackle(low, top, beta, obj="sail")
    return P


def reef_count(reef):
    return [k for k, v in luff_stations(0.0) if v <= reef + 0.04]


def slide_stack(kinds, z0=None):
    """Slides and cars stacked up the track from its foot (a lowered main's, or a reef's below its tack); the luff tape
    zigzags aft between them into the bag. Returns parts."""
    P = []
    z = (R.MS["track"]["z"][0] + 0.03) if z0 is None else z0
    prev = None
    for kind in kinds:
        h = {"slide": 0.058, "car": 0.135, "head": 0.31}[kind]
        zc = z + h / 2 if kind != "head" else z + 0.19
        P += track_car(kind, zc, (LUFF_X, 0.0, zc))
        lp = np.array([LUFF_X, 0.0, zc])
        if prev is not None:
            mid = (prev + lp) / 2 + np.array([-0.16, 0.0, 0.0])
            P.append(p_rope([prev, mid, lp], 0.007, "SailTape", 6))
        prev = lp
        z += h + 0.004
    return P, z


# ------------------------------------------------------------------ the lazy bag objects (boom frame at 0)

def bag_xs(step=0.12):
    x0, x1 = BG["x"]
    n = int(round((x0 - x1) / step))
    return [x0 - (x0 - x1) * k / n for k in range(n + 1)]


def end_round(x, r=0.09):
    """1 inside the bag, easing to 0.55 at its ends over r: the ends' rounded seams."""
    x0, x1 = BG["x"]
    d = min(x0 - x, x - x1)
    return 0.55 + 0.45 * math.sqrt(max(0.0, 1 - (max(0.0, r - d) / r) ** 2))


def zipped_bag_parts():
    P = []
    rings = []
    for x in bag_xs():
        sec, h, w = bag_zipped_section(x)
        k = end_round(x)
        zc = BOOM_TOP + 0.42 * h
        rings.append([(x, y * k, zc + (z - zc) * k) for y, z in sec])
    P.append({"kind": "rings", "rings": rings, "mat": "SailBag", "smooth": True})
    zx = [x for x in bag_xs(0.2)][1:-1]
    P.append(p_rope([(x, 0.0, BOOM_TOP + bag_zipped_section(x)[1] + 0.012) for x in zx], 0.0055, "BlackPlastic", 6))
    xs0 = zx[0]
    zs = BOOM_TOP + bag_zipped_section(xs0)[1] + 0.018
    P.append(p_block((xs0 - 0.02, 0.0, zs), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.05, 0.022, 0.014), "BlackPlastic", 0.004))
    P.append(p_rope([(xs0 + 0.002, 0.0, zs + 0.005), (xs0 + 0.05, 0.0, zs - 0.03), (xs0 + 0.06, 0.0, zs - 0.09)], 0.003, "Rope", 6))
    P += bag_edges(lambda x: bag_zipped_section(x)[2])
    for s, pts in bag_jack_points("Zipped").items():
        for p in pts:
            P.append(p_block(p - np.array([0.0, 0.0, 0.01]), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.05, 0.03, 0.012), "Webbing", 0.004))
            P.append(p_torus(p + np.array([0.0, 0.0, 0.01]), (1, 0, 0), 0.012, 0.0035))
    # the lowered main: its slides and cars stacked at the track's foot with the headboard on top, the halyard down to
    # it, the clew out of the bag's aft end on the outhaul's car, the tack at the gooseneck
    stack, ztop = slide_stack([k for k, v in luff_stations(0.0)])
    P += stack
    P.append(p_rope([R.main_halyard_from(), (LUFF_X + 0.012, 0.0, ztop - 0.02)], R.HL["rope"]["halyard"] / 2))
    P.append(p_torus((LUFF_X + 0.012, 0.0, ztop - 0.035), (0, 1, 0), 0.016, 0.005))
    clew = np.array(R.boom_clew())
    xe = BG["x"][1]
    hw = [0.13, 0.1, 0.07, 0.045]
    hh = [0.1, 0.08, 0.055, 0.035]
    path = [np.array([xe + 0.04 - (xe + 0.04 - clew[0] - 0.05) * k / 3, 0.0, BOOM_TOP + 0.004]) for k in range(4)]
    P.append(p_heap(path, hw, hh, seed=3, lump=0.15, mat="ClothMain"))
    P.append(p_torus(clew + np.array([0.0, 0.0, 0.004]), (0, 1, 0), 0.028, 0.007))
    path = [np.array([BG["x"][0] + 0.05 - 0.08 * k, 0.0, BOOM_TOP + 0.004]) for k in range(4)]
    P.append(p_heap(path, [0.03, 0.06, 0.09, 0.12], [0.04, 0.07, 0.1, 0.12], seed=4, lump=0.12, mat="ClothMain"))
    P.append(p_torus((LUFF_X - 0.004, 0.0, BOOM_TOP + 0.012), (0, 1, 0), 0.02, 0.005))
    _, tops = R.lazy_jack_parts()
    P += jack_lines(tops, bag_jack_points("Zipped"), boom_rot(0.0))
    return P


def bag_edges(width_at):
    """The bag's lacing along the boom's sides: a bolt rope each side in the boom's slot."""
    P = []
    bw = R.BO["width"] / 2 + BG["thick"] + 0.002
    zl = BOOM_TOP - BG["wrap"] + 0.006
    xs = bag_xs(0.25)
    for s in (1, -1):
        P.append(p_rope([(x, s * bw, zl) for x in xs], 0.005, "SailBag", 6))
    return P


def open_bag_parts():
    P = []
    rings = []
    xs = bag_xs(0.15)
    for x in xs:
        sec, h, w = bag_open_section(x)
        rings.append([(x, y, z) for y, z in sec])
    P.append({"kind": "rings", "rings": rings, "mat": "SailBag", "smooth": True})
    for s in (1, -1):
        P.append(p_rope([(x, s * (bag_open_dims(x)[1] - 0.004), BOOM_TOP + bag_open_dims(x)[0] + 0.006) for x in xs[1:-1]],
                        0.0045, "BlackPlastic", 6))
    P += bag_edges(lambda x: bag_open_dims(x)[1])
    for s, pts in bag_jack_points("Open").items():
        for p in pts:
            P.append(p_block(p - np.array([0.0, 0.0, 0.022]), (1, 0, 0), (0, 0, 1), (0, 1, 0), (0.05, 0.05, 0.012), "Webbing", 0.004))
            P.append(p_torus(p, (1, 0, 0), 0.012, 0.0035))
    return P


# ------------------------------------------------------------------ the jib

def jib_car_parts(y, clew_pt, box):
    """The self-tacking car on the track at y with a swivel block on it whose sheave lies in the sheet's plane, and the
    sheet from the clew round it and up into the mast's box."""
    car = R.jib_car(y)[0][0]                              # the car's body on the track
    r = JB_TRACK_R
    p = math.asin(y / r)
    c = np.array([B.CB["x"] - r * math.cos(p), y, S.roof_top_z(y) + R.JT["height"]])
    P = [car, p_cyl(c + np.array([0, 0, 0.026]), c + np.array([0, 0, 0.05]), 0.014, "Stainless", 14)]
    head = c + np.array([0.0, 0.0, 0.062])
    k = R.KIT_SIZE[("Block40", "57")]
    rs = R.HL["rope"]["sheet"] / 2
    u_in, u_out = unit(clew_pt - head), unit(np.array(box) - head)
    pull = unit(u_in + u_out)
    axle = unit(np.cross(u_in, u_out))
    ax, az = np.cross(axle, -pull), -pull
    blk = p_kit("Block40", head, ax, az, light=0.1, size="57")
    P.append(blk)
    C = np.array(blk["expect"]["Axle"])
    arc = R.wrap(tup(clew_pt), tup(C), tup(axle), 0.02 * k + rs - 0.002, tup(box))
    P.append(p_rope([clew_pt] + [np.array(q) for q in arc] + [np.array(box)], rs, "Rope", 8))
    return P


JB_TRACK_R = R.JT["radius"]


def jib_set_parts(sh):
    P = [p_cloth(sh, "ClothJib")]
    G = sh.G
    P += strip_layers(sh, JB["uv_strip"]["leech"], JB["uv_strip"]["foot"], JB["uv_strip"]["offset"])
    P.append(p_rope(G[0, :], 0.006, "SailTape", 8))
    P.append(p_rope(G[-1, :], 0.0035, "SailTape", 6))
    P.append(p_rope(G[:, 0], 0.0035, "SailTape", 6))
    P += corner_patch(sh, "clew", 6, 7)
    P += corner_patch(sh, "tack", 5, 5)
    P += corner_patch(sh, "head", 4, 6)
    clew_ring, cc = ring_at(sh, sh.nu, 0, sh.nu - 2, 2, 0.04, 0.026, 0.0065)
    P.append(clew_ring)
    _, _, _, te, he = jib_corners()
    for (fi, fj, ti, tj), eye in (((0, 0, 1, 2), te), ((0, sh.nv, 2, sh.nv - 3), he)):
        ring, c = ring_at(sh, fi, fj, ti, tj, 0.03, 0.016, 0.005)
        P.append(ring)
        P.append(p_rope([c, eye], 0.006, "Webbing", 6))
    P += jib_car_parts(JB["car_y"], cc, R.jib_sheet_box())
    return P


def roll_parts(sh, axis_pts, r0, t_mm, mat="SailUV", sides=16):
    """A furled sail: the roll round its axis, its outer edge's helix (the leech and foot wrapping round), the clew's
    ring on the outside. Returns (parts, the clew's ring centre)."""
    s, A, r, th, sc = roll(sh, r0, t_mm, axis_pts)
    P = []
    d = unit(A[-1] - A[0])
    ea, eb = (np.array(v) for v in R.perp(tup(d)))
    rings = []
    for k in range(len(s)):
        rr = r[k] + 0.0015
        rings.append([tup(A[k] + rr * (math.cos(a) * ea + math.sin(a) * eb)) for a in (2 * math.pi * m / sides for m in range(sides))])
    P.append({"kind": "rings", "rings": rings, "mat": mat, "smooth": True})
    # the helix: eight points a turn (45 deg a step: 4 mm off the true curve at the roll's 5 cm)
    ss = [0.0]
    while ss[-1] < 1.0:
        k = np.searchsorted(s, ss[-1])
        k = min(max(k, 1), len(s) - 1)
        dth = abs(th[k] - th[k - 1]) / max(s[k] - s[k - 1], 1e-9)
        ss.append(min(1.0, ss[-1] + math.radians(45) / max(dth, 1e-3)))
    ss = np.array(ss)
    rr = np.interp(ss, s, r) + 0.0025
    tt = np.interp(ss, s, th)
    AA = np.array([np.interp(ss, s, A[:, c]) for c in range(3)]).T
    hel = [AA[k] + rr[k] * (math.cos(tt[k]) * ea + math.sin(tt[k]) * eb) for k in range(len(ss))]
    P.append(p_rope(hel, 0.003, "SailTape", 4))
    kc = float(np.interp(sc, s, np.arange(len(s))))
    ac = np.array([np.interp(sc, s, A[:, c]) for c in range(3)])
    rc, tc = float(np.interp(sc, s, r)), float(np.interp(sc, s, th))
    radial = math.cos(tc) * ea + math.sin(tc) * eb
    cring = ac + radial * (rc + 0.02)
    P.append(p_torus(cring, np.cross(radial, d), 0.026, 0.0065))
    P.append(p_block(ac + radial * (rc + 0.004), d, np.cross(radial, d), radial, (0.16, 0.09, 0.008), mat, 0.02))
    return P, cring


def jib_furled_parts():
    sh = jib_sheet()
    T, Hd, C, te, he = jib_corners()
    z0, z1 = T[2], Hd[2]
    P, cring = roll_parts(sh, lambda u: np.array(R.forestay_at(z0 + (z1 - z0) * u)), R.FS["foil"][0] / 2 + 0.004,
                          CL["dacron_mm"])
    for corner, eye in ((T, te), (Hd, he)):
        c = np.array(R.forestay_at(float(corner[2]))) + stay_aft_signed() * 0.03
        P.append(p_torus(c, (0, 1, 0), 0.016, 0.005))
        P.append(p_rope([c, eye], 0.006, "Webbing", 6))
    P += jib_car_parts(0.0, cring, R.jib_sheet_box())
    return P


def stay_aft_signed():
    a = stay_aft()
    return -a if a[0] > 0 else a


# ------------------------------------------------------------------ the Code 0

def code0_fittings(T, Hd, tip, drum0):
    """The Code 0's furler: the bowsprit's end fitting and padeye, the drum with its continuous line, the tack swivel;
    the top swivel at the head and the halyard to its box."""
    P = []
    dr = C0["drum"]
    rt = B.SP["tip_radius"]
    x, xd = tip[0], drum0[0]
    z_ax = tip[2] - rt
    seat = drum0[2] - dr["over_tip"]
    P.append(p_cyl((xd - 0.08, 0.0, z_ax), (x + 0.025, 0.0, z_ax), rt + 0.006, "Stainless", 20))
    P.append(p_block((x - 0.015, 0.0, tip[2] + 0.012), (1, 0, 0), (0, 0, 1), (0, 1, 0), (0.03, 0.04, 0.012), "Stainless", 0.008))
    P.append(p_torus((x - 0.015, 0.0, tip[2] + 0.026), (0, 1, 0), 0.012, 0.004))
    P.append(p_cyl((xd, 0.0, seat + 0.012), drum0, 0.012, "Stainless", 12))
    ra, rf = dr["diameter"] / 2, dr["diameter"] / 2 + 0.012
    prof = [(0.0, 0.02), (0.0, rf), (0.01, rf), (0.016, ra * 0.7), (dr["height"] - 0.016, ra * 0.7),
            (dr["height"] - 0.01, rf), (dr["height"], rf), (dr["height"], 0.025)]
    P.append({"kind": "rings", "mat": "Aluminium", "smooth": True,
              "rings": [[tup(drum0 + np.array([r * math.cos(a), r * math.sin(a), h])) for a in
                         (2 * math.pi * k / 36 for k in range(36))] for h, r in prof]})
    zm = drum0[2] + dr["height"] / 2
    loop = [np.array([xd + (ra * 0.7 + 0.006) * math.cos(a), (ra * 0.7 + 0.006) * math.sin(a), zm]) for a in
            np.linspace(math.radians(200), math.radians(520), 26)]
    P.append(p_rope(loop, 0.005, "Rope", 6))
    for s in (1, -1):
        a0 = np.array([xd - (ra * 0.7 + 0.006), s * 0.02, zm])
        P.append(p_rope([a0, np.array([xd - 0.3, s * 0.035, zm - 0.04]), np.array([B.CB["x"] + 0.15, s * 0.05, B.CB["z"] + 0.12])],
                        0.005, "Rope", 6))
    P.append(p_cyl(drum0 + np.array([0, 0, dr["height"]]), T - np.array([0, 0, 0.02]), 0.022, "Aluminium", 16))
    P.append(p_torus(T, (0, 1, 0), 0.016, 0.005))
    # the top swivel and the halyard up to its box on the mast's front
    sw0, sw1 = Hd + np.array([0, 0, 0.02]), Hd + np.array([0, 0, 0.17])
    P.append(p_cyl(sw0, sw1, 0.02, "Aluminium", 16))
    P.append(p_torus(Hd, (0, 1, 0), 0.014, 0.0045))
    P.append(p_torus(sw1 + np.array([0, 0, 0.018]), (0, 1, 0), 0.013, 0.0045))
    zb = R.MH["code0_z"]
    box = np.array([R.front_x(zb) + 0.006, 0.0, zb - 0.03])
    P.append(p_rope([sw1 + np.array([0, 0, 0.03]), box], R.HL["rope"]["halyard"] / 2))
    return P


def quarter_block_parts(clew_pt, slack=0.0):
    """The Code 0's sheet from its clew aft to a block on a padeye on the port quarter's deck, and a short tail on
    forward (slice 8 leads it to a winch). slack sags the sheet (furled)."""
    qx, qy = C0["quarter_block"]
    hb = H.half_beam(qx)
    zd = S.deck_z(qx, (qy + H.HULL_Y) / hb)
    P = [p_block((qx, qy, zd + 0.004), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.06, 0.04, 0.008), "Stainless", 0.01),
         p_torus((qx, qy, zd + 0.02), (1, 0, 0), 0.012, 0.004)]
    head = np.array([qx, qy, zd + 0.03])
    fwd = np.array([qx + 0.8, qy + 0.12, zd + 0.02])
    rs = R.HL["rope"]["sheet"] / 2
    u_in, u_out = unit(clew_pt - head), unit(fwd - head)
    pull = unit(u_in + u_out)
    axle = unit(np.cross(u_in, u_out))
    blk = p_kit("Block40", head, np.cross(axle, -pull), -pull, light=0.1, size="57")
    P.append(blk)
    C = np.array(blk["expect"]["Axle"])
    k = R.KIT_SIZE[("Block40", "57")]
    arc = [np.array(q) for q in R.wrap(tup(clew_pt), tup(C), tup(axle), 0.02 * k + rs - 0.002, tup(fwd))]
    n = 16
    run = [clew_pt + (arc[0] - clew_pt) * (j / n) - np.array([0.0, 0.0, slack * 4 * (j / n) * (1 - j / n)]) for j in range(n)]
    P.append(p_rope(run + arc + [fwd, fwd + np.array([0.35, 0.03, 0.0])], rs, "Rope", 8))
    return P


def code0_set_parts(sh):
    T, Hd, C, tip, drum0 = code0_corners()
    P = [p_cloth(sh, "ClothCode0")]
    G = sh.G
    P += strip_layers(sh, C0["uv_strip"]["leech"], C0["uv_strip"]["foot"], C0["uv_strip"]["offset"])
    P.append(p_rope(G[0, :], C0["cable_d"] / 2 + 0.003, "SailTape", 10))
    P.append(p_rope(G[-1, :], 0.0035, "SailTape", 6))
    P.append(p_rope(G[:, 0], 0.0035, "SailTape", 6))
    P += corner_patch(sh, "clew", 6, 7)
    P += corner_patch(sh, "tack", 5, 5)
    P += corner_patch(sh, "head", 5, 6)
    ring, cc = ring_at(sh, sh.nu, 0, sh.nu - 2, 2, 0.04, 0.026, 0.0065)
    P.append(ring)
    P += code0_fittings(T, Hd, tip, drum0)
    P += quarter_block_parts(cc)
    return P


def code0_furled_parts():
    T, Hd, C, tip, drum0 = code0_corners()
    sh = headsail_sheet("Code0Furled", T, Hd, C, C0, nu=24, nv=48)
    sag = code0_sag(T, Hd, 0.25)
    P, cring = roll_parts(sh, lambda u: T + (Hd - T) * u + sag(u), C0["cable_d"] / 2 + 0.006, CL["laminate_mm"])
    P += code0_fittings(T, Hd, tip, drum0)
    P += quarter_block_parts(cring, slack=0.35)
    return P


# ------------------------------------------------------------------ every object

SHOWN = ("L42_LazyBag_Zipped", "L42_Sail_Jib_Furled")
HOISTED = ("Set", "Reach", "Run")
STATES = {   # what each of the renders' sail states shows (the mainsheet's own object is hidden with any hoisted main)
    "Moored": SHOWN,
    "Beat": ("L42_Sail_Main_Set", "L42_Sail_Main_Luff", "L42_LazyBag_Open", "L42_Sail_Jib_Set"),
    "Reach": ("L42_Sail_Main_Reach", "L42_Sail_Main_Luff", "L42_LazyBag_Open", "L42_Sail_Code0_Set", "L42_Sail_Jib_Furled"),
    "Run": ("L42_Sail_Main_Run", "L42_Sail_Main_Luff", "L42_LazyBag_Open", "L42_Sail_Jib_Furled", "L42_Sail_Code0_Furled"),
    "Reefed": ("L42_Sail_Main_Reefed", "L42_LazyBag_Open", "L42_Sail_Jib_Set"),
}


def state_boom_deg(state):
    """The boom's angle to port (degrees) in a sail state: its main's, else amidships."""
    for name in STATES[state]:
        if name.startswith("L42_Sail_Main_") and name != "L42_Sail_Main_Luff":
            return MS["states"][name[len("L42_Sail_Main_"):]]["boom_deg"]
    return 0.0


def part_key(p):
    return json.dumps(p, sort_keys=True, default=float)


def objects():
    """{object name: {'parts', 'origin' (game frame: the build moves the object's origin there), 'boom_deg' (the
    boom's angle the object was built for, or None)}}."""
    sh = set_sheets()
    out = {}
    for st in ("Set", "Reach", "Run", "Reefed"):
        s = sh["Main" + st]
        out["L42_Sail_Main_" + st] = {"parts": main_state_parts(s, st), "origin": (0.0, 0.0, 0.0),
                                      "boom_deg": MS["states"][st]["boom_deg"]}
    # the hoisted main's luff on the track (slides, batten cars, the headboard's car, the halyard's run) does not move
    # when the boom swings: the three hoisted states share one copy
    keys = [[(part_key(p), p) for p in out["L42_Sail_Main_" + st]["parts"]] for st in HOISTED]
    common = set(k for k, _ in keys[0]).intersection(*[set(k for k, _ in ks) for ks in keys[1:]])
    seen = set()
    luff = []
    for k, p in keys[0]:
        if k in common and k not in seen:
            seen.add(k)
            luff.append(p)
    for st, ks in zip(HOISTED, keys):
        out["L42_Sail_Main_" + st]["parts"] = [p for k, p in ks if k not in common]
    out["L42_Sail_Main_Luff"] = {"parts": luff, "origin": (0.0, 0.0, 0.0), "boom_deg": None}
    out["L42_LazyBag_Zipped"] = {"parts": zipped_bag_parts(), "origin": tup(PIN), "boom_deg": 0.0}
    out["L42_LazyBag_Open"] = {"parts": open_bag_parts(), "origin": tup(PIN), "boom_deg": 0.0}
    out["L42_Sail_Jib_Set"] = {"parts": jib_set_parts(sh["JibSet"]), "origin": (0.0, 0.0, 0.0), "boom_deg": None}
    out["L42_Sail_Jib_Furled"] = {"parts": jib_furled_parts(), "origin": (0.0, 0.0, 0.0), "boom_deg": None}
    out["L42_Sail_Code0_Set"] = {"parts": code0_set_parts(sh["Code0Set"]), "origin": (0.0, 0.0, 0.0), "boom_deg": None}
    out["L42_Sail_Code0_Furled"] = {"parts": code0_furled_parts(), "origin": (0.0, 0.0, 0.0), "boom_deg": None}
    return out, sh


def main():
    fails = []
    sh = set_sheets()
    print(f"mainsail: luff {P_M:.3f} m (tack {TACK_Z:.2f} to head {MS['head_z']}), foot {E_M:.3f} m, head {HB:.3f} m "
          f"(the physics' head chord 1.8), roach {MS['roach']} m; reefs at {', '.join(f'{reef_v(k):.2f}' for k in (1, 2, 3))} m "
          f"up the luff")
    for name, target in (("MainSet", MS["area"]), ("JibSet", JB["area"]), ("Code0Set", C0["area"])):
        a = sh[name].area()
        ok = abs(a / target - 1) <= 0.03
        print(f"  {name:10s} area {a:6.2f} m^2 against {target:5.2f} ({a / target - 1:+.1%}) {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(name + " area")
    T, Hd, C, te, he = jib_corners()
    print(f"jib: tack {np.round(T, 3)}, head {np.round(Hd, 3)}, clew {np.round(C, 3)}; luff {np.linalg.norm(Hd - T):.2f} m, "
          f"foot {np.linalg.norm(C - T):.2f}, leech {np.linalg.norm(Hd - C):.2f}")
    T, Hd, C, _, _ = code0_corners()
    g, ft = mid_girth(sh["Code0Set"])
    print(f"code 0: tack {np.round(T, 3)}, head {np.round(Hd, 3)}, clew {np.round(C, 3)}; luff {np.linalg.norm(Hd - T):.2f} m, "
          f"foot {ft:.2f}, middle girth {g:.2f} ({g / ft:.0%} of the foot)")
    rs = rig_segments()
    for name, s in sh.items():
        names = [n for n in rs if not (n == "Mast" and name.startswith("Main")) and not (n == "Forestay" and name.startswith("Jib"))]
        c = clearance(s, {n: rs[n] for n in names}, floor=not name.startswith("Main"))
        low = {k: v for k, v in c.items() if v < 0.15}
        worst = min(c.values())
        flag = "ok" if worst >= CLEAR else "FAIL"
        print(f"  {name:10s} least gap {worst * 100:6.1f} cm  " + ", ".join(f"{k} {v * 100:.1f}" for k, v in sorted(low.items()))
              + f"  {flag}")
        if worst < CLEAR:
            fails.append(name + " clearance")
        k = sharpest(s)
        print(f"  {name:10s} sharpest bend {k * 100:4.1f} cm  {'ok' if k <= KINK else 'FAIL'}")
        if k > KINK:
            fails.append(name + " crease")
    for st in ("MainSet", "MainReach", "MainRun", "MainReefed"):
        g = bag_inside_gap(sh[st])
        print(f"  {st:10s} foot inside the open bag: least gap to its sides {g * 100:.1f} cm {'ok' if g > 0 else 'FAIL'}")
        if g <= 0:
            fails.append(st + " bag")
    if fails:
        print("FAIL: " + ", ".join(fails))
        sys.exit(1)
    print("pass")


if __name__ == "__main__":
    main()
