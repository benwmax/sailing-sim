"""Bluebonnet's running rigging (docs/jclass-7), from running_bluebonnet.json, the sails' corners (sails.py's cringles),
the spars' eyes (spars.py) and the runners' tackles (rigging.py).

Objects (spars.SparPart: closed solids and rope tubes, in the hull's frame, X forward, Y starboard, Z up, metres):
  Winches          the capstans and reel winches on their teak pads and the capstans' horn cleats (winches.py)
  RunningFittings  the lead blocks' padeyes on deck, the halyards' sheave boxes on the mast (aloft and at its foot), and
                   each wire halyard's lead from its foot box to its reel (the same in every suit)
  Running.<Suit>   one for each of sails_bluebonnet.json's suits, on starboard tack (the lee, where the sheets lead, is
                   port): the sheets, guy, foreguy and halyards in use with their shackles; the lead blocks, each hanging
                   on its padeye's link toward its rope's pulls with its sheave in their plane; the mainsheet's tackle at
                   the suit's boom; the runners' and checkstays' tails from slice 5's tackles; each loaded rope's turns
                   on its capstan, its hitch on the cleat and its tail flemished down on the deck; the halyards out of use
                   hauled up to their boxes aloft. Show one, with the suit's sails.

Every rope is one tube along its centreline (spars.py's 'Spar' map on it, u metres along it, so the paint draws the
lay). The report lists each rope's centreline in pieces, each with what it may touch by design (its blocks' sheaves,
its drum, its cleat, the deck under its coil) for the build's room check, each lead's rise onto its drum, each part's
angle to its sheave's plane, each rope's lead against its cut length (the rest is in its coil), and the weights: the
ropes from their cut lengths (both sides' sheets), the wire halyards from their length at full hoist and on their
reels, the blocks, shackles, padeyes and boxes from their solids, each once.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck  # noqa: E402
import shell  # noqa: E402
import spars  # noqa: E402
import rigging  # noqa: E402
import winches  # noqa: E402
import sails  # noqa: E402
from spars import SparPart, unit, UP  # noqa: E402

RN = winches.RN
SR = rigging.SR
STEEL = SR["material"]["steel"]
MANILA = SR["material"]["manila"]
BLK = SR["runners"]["block"]
X = np.array([1.0, 0.0, 0.0])
Y = np.array([0.0, 1.0, 0.0])
LEE = -1                     # starboard tack: the lee side, where the sheets lead, is port
SUITS = [k for k in sails.SL["suits"] if k != "note"]
MAIN_HALYARD = RN["halyards"]["main"]["label"]     # rides up the slides' lane above the headboard
CAT_ROPE = "Running rigging: rope"
CAT_WIRE = "Running rigging: wire halyards"
CAT_FIT = "Running rigging: shackles"
CAT_BLOCK = "Running rigging: blocks, padeyes and boxes"
CAT_TRACK = "Sheet tracks and cars (bronze)"           # slice 8's deck hardware: weighed apart from the rigging


def lab(group, kind):
    return f"{group} | {kind}"


def side_name(sd):
    return "starboard" if sd > 0 else "port"


def deck_z(x, y):
    return winches.deck_z(x, y)


def rope_spec(key):
    rp = RN["ropes"][key]
    d = rp["d"]
    if rp["kind"] == "manila":
        kgm, slot = MANILA * math.pi * d * d / 4, "Rope"
    else:
        c = SR["constructions"][rp["kind"]]
        kgm, slot = STEEL * c["fill"] * math.pi * d * d / 4, "WireRope"
    return {"key": key, "d": d, "r": d / 2, "kgm": kgm, "slot": slot, "kind": rp["kind"]}


def plan(p, sd=1):
    """A plan point from the json, mirrored to side sd (+1 starboard, -1 port)."""
    return np.array([p[0], sd * p[1]], float)


def on_deck(p, lift):
    q = np.asarray(p, float)
    return np.array([q[0], q[1], deck_z(q[0], q[1]) + lift])


def smooth01(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def seg_len(P):
    P = np.asarray(P, float)
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum()) if len(P) > 1 else 0.0


# ------------------------------------------------------------------------------------------------ a rope's centreline
class Line:
    """A rope's centreline built piece by piece: each piece keeps what it may touch by design, as (object, label prefix)
    patterns the room check leaves out."""

    def __init__(self, group, spec, obj):
        self.group, self.spec, self.obj = group, spec, obj
        self.P = []
        self.pieces = []

    def add(self, pts, allow=(), name=None):
        pts = [np.asarray(p, float) for p in pts]
        if self.P and len(pts) and np.linalg.norm(pts[0] - self.P[-1]) < 1e-7:
            pts = pts[1:]
        if not pts:
            return
        i0 = max(len(self.P) - 1, 0)
        self.P.extend(pts)
        self.pieces.append({"i": (i0, len(self.P) - 1), "allow": list(allow), "name": name})

    def length(self):
        return seg_len(self.P)

    def record(self):
        return {"name": self.group, "group": self.group, "object": self.obj, "key": self.spec["key"],
                "r": self.spec["r"], "rope": True,
                "pieces": [{"path": np.array(self.P[a["i"][0]:a["i"][1] + 1]), "allow": a["allow"], "name": a["name"]}
                           for a in self.pieces]}


def through(line, prev, a, nxt, allow, lead_allow=(), name="lead", s=0.12):
    """A part from `prev` into a block's sheave arc `a`, round it and out toward `nxt` (the next arc's first point, or
    the drum): for a hand's breadth `s` either side of the sheave the rope runs between the block's cheeks, so those
    pieces may touch the block (`allow`) as the arc does; the lead before them may touch `lead_allow`."""
    prev, nxt = np.asarray(prev, float), np.asarray(nxt, float)
    a0, a1 = np.asarray(a[0], float), np.asarray(a[-1], float)
    if float(np.linalg.norm(a0 - prev)) > 2 * s:
        line.add([a0 - s * unit(a0 - prev)], allow=lead_allow, name=name)
    line.add([a0], allow=list(allow) + list(lead_allow), name="into the block")
    line.add(a, allow=allow, name="round the sheave")
    line.add([a1 + min(s, 0.45 * float(np.linalg.norm(nxt - a1))) * unit(nxt - a1)], allow=allow,
             name="out of the block")


def tube(part, P, r, slot, label, n=10, closed=False):
    """A tube along P (a rope, a wire, an eye's loop), its lay painted from its 'Spar' map. Returns its length."""
    rings, u = rigging.tube_rings(P, r, n, closed=closed)
    V, F = deck.loft_rings(rings, closed=closed)
    if closed:
        uv = {"Spar": np.array([(uu, j / n) for uu in u for j in range(n)]),
              "SparG": np.tile((2 * math.pi * r, -1.0), (len(V), 1))}
        L = float(u[-1] + np.linalg.norm(np.asarray(P[0]) - np.asarray(P[-1])))
    else:
        uv = spars.ring_uv(rings, u, plated=False)
        L = float(u[-1])
    part.add(V, F, slot, None, label, uv=uv)
    return L


def lay(part, line):
    sp = line.spec
    return tube(part, np.array(line.P), sp["r"], sp["slot"], line.group, n=10 if sp["d"] >= 0.016 else 8)


class Weighed:
    """Each block, shackle and fitting weighed once, though it is drawn in several suits: masses a part gains while
    building `key` are kept the first time and dropped after."""

    def __init__(self):
        self.by_key = {}

    @property
    def done(self):
        return set(self.by_key)

    @property
    def rows(self):
        return [m for v in self.by_key.values() for m in v]

    def __call__(self, part, key, fn):
        n0 = len(part.masses)
        out = fn()
        new = part.masses[n0:]
        del part.masses[n0:]
        self.by_key.setdefault(key, list(new))
        return out

    def mirrored(self):
        """Rows for the gear that is aboard on both sides but drawn on one only (the lazy sheets' blocks and shackles,
        a side's tackle never set in any suit): each key (kind, (name, side)) drawn on one side and never on the other
        is weighed again, mirrored."""
        out = []
        for (kind, k), rows in self.by_key.items():
            if not (isinstance(k, tuple) and len(k) == 2 and k[1] in (1, -1)):
                continue
            if (kind, (k[0], -k[1])) in self.by_key:
                continue
            for m in rows:
                c = np.asarray(m["centre"], float)
                out.append(dict(m, centre=[float(c[0]), float(-c[1]), float(c[2])], mirrored=True))
        return out


SETTLE_TOL = 5e-4          # every fixed-point loop's last pass moves its points less than this (m)
SETTLED = {}               # each loop's worst last-pass move, for the report


def settled(name, before, after):
    """A fixed-point loop's last pass: how far its points (`before` -> `after`) still moved; over SETTLE_TOL fails."""
    r = max(float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float))) for a, b in zip(before, after))
    SETTLED[name] = max(SETTLED.get(name, 0.0), r)
    if r > SETTLE_TOL:
        raise ValueError(f"{name}: its lead has not settled ({r * 1000:.2f} mm on the last pass)")


# ------------------------------------------------------------------------------------------------ shackles and eyes
def shackle_geom(pin_c, pin_ax, lead, spec, hold):
    """A bronze D shackle's frame: its pin along pin_ax through pin_c (through something that takes `hold` of its jaw
    beyond the pin), its bow toward `lead`, the rope's eye round its crown; the eye's throat is where the rope's
    standing part starts."""
    d, r = spec["d"], spec["r"]
    a = unit(pin_ax)
    lead = unit(lead)
    b = lead - (lead @ a) * a
    if np.linalg.norm(b) < 0.2:
        raise ValueError("the lead is almost along the shackle's pin")
    b = unit(b)
    br = max(0.0055, 0.3 * d + 0.002)                     # the bow's bar
    pr = 1.15 * br                                        # the pin
    half = (2 * r + 0.012) / 2 + br                       # the jaw takes the rope's eye with 6 mm to spare
    rho = br + r + 0.0015                                 # the eye's centreline round the crown's bar
    Ls = max(pr + hold + 0.003 + rho + r, half + 0.01)    # the pin's centre to the crown's centreline
    K = pin_c + Ls * b
    eye_len = max(3.0 * d, 0.05)
    T = K + (rho + eye_len) * b
    return {"pin": np.asarray(pin_c, float), "a": a, "b": b, "c": np.cross(a, b), "br": br, "pr": pr, "half": half,
            "rho": rho, "Ls": Ls, "K": K, "T": T, "eye_len": eye_len}


def shackle_build(part, g, spec, group, cat=CAT_FIT):
    a, b, c, pin_c = g["a"], g["b"], g["c"], g["pin"]
    half, Ls, br, pr = g["half"], g["Ls"], g["br"], g["pr"]
    gs = lab(group, "shackle")
    st = Ls - half
    pts = [pin_c + half * a + t * b for t in np.linspace(0.0, st, 4)]
    pts += [pin_c + st * b + half * (math.cos(q) * a + math.sin(q) * b) for q in np.linspace(0.0, math.pi, 13)[1:]]
    pts += [pin_c - half * a + t * b for t in np.linspace(st, 0.0, 4)[1:]]
    rings, _ = rigging.tube_rings(np.array(pts), br, 10)
    V, F = deck.loft_rings(rings)
    rigging.solid(part, V, F, "Bronze", gs, cat)
    rigging.rev(part, [(pr * 1.5, -half - br - 0.006), (pr * 1.5, -half - br), (pr, -half - br), (pr, half + br + 0.005)],
                pin_c, a, b, "Bronze", gs, cat, 12)
    K, rho, T = g["K"], g["rho"], g["T"]
    ph0 = math.acos(rho / (rho + g["eye_len"]))
    loop = [T] + [K + rho * (math.cos(q) * b + math.sin(q) * c) for q in np.linspace(ph0, 2 * math.pi - ph0, 19)]
    tube(part, np.array(loop), spec["r"], spec["slot"], lab(group, "eye"), n=8, closed=True)
    part.masses.append({"part": CAT_ROPE if spec["slot"] == "Rope" else CAT_WIRE,
                        "kg": round(spec["kgm"] * seg_len(loop + [T]), 3),
                        "centre": [round(float(v), 3) for v in K], "how": "length"})


def ring_shackle(cr, lead, spec):
    """A shackle through a sail's cringle (cr: centre, axis, radii) toward `lead`: its pin through the hole, bearing on
    the ring's inside toward the lead (2 mm clear), its axis the ring's squared to the lead."""
    n = unit(cr["n"])
    ell = unit(lead)
    q = unit(ell - (ell @ n) * n)
    br = max(0.0055, 0.3 * spec["d"] + 0.002)
    pin_c = cr["c"] + (cr["R"] - cr["r"] - 1.15 * br - 0.002) * q
    return shackle_geom(pin_c, unit(n - (n @ ell) * ell), ell, spec, hold=2 * cr["r"] + 0.003)


def eye_shackle(eye, lead, spec, hold=0.03):
    """A shackle through a spar's eye (spars.eye_lug's hole and axis) or a block's becket toward `lead`."""
    ell = unit(lead)
    ax = np.asarray(eye["axis"], float)
    return shackle_geom(np.asarray(eye["hole"], float), unit(ax - (ax @ ell) * ell), ell, spec, hold=hold)


def head_shackle(cr, lead, spec):
    """A shackle through the mainsail's headboard, 45 mm under its top and 25 mm aft of its luff."""
    n = unit(cr["n"])
    ell = unit(lead)
    q = unit(ell - (ell @ n) * n)
    side = unit(np.cross(n, q))
    side = side if side[0] < 0 else -side                 # aft, into the board
    return shackle_geom(cr["c"] - 0.045 * q + 0.025 * side, unit(n - (n @ ell) * ell), ell, spec, hold=0.05)


def link_ring(part, hole, H, axis, group, cat=CAT_BLOCK):
    """The galvanised link from a padeye's (or an eye's) hole to a block's lug: a ring through both holes."""
    lr = SR["runners"]["padeye"]["link_r"]
    d = unit(H - hole)
    ax = np.cross(d, axis)
    ax = unit(ax) if np.linalg.norm(ax) > 0.1 else rigging.perp(d)
    lp = rigging.ring_path(0.5 * (hole + H), ax, d, 0.5 * float(np.linalg.norm(H - hole)))
    rigging.loop(part, lp, lr, lab(group, "link"), cat, STEEL * math.pi * lr * lr, slot="Galvanised")


# ------------------------------------------------------------------------------------------------ sheaves
def wrap(C, ax, e, R, P_in, P_out, k_deg=8.0):
    """A rope's turn round a sheave (centre C, in the plane (e, ax), its centreline at R) from P_in to P_out: the
    tangent point toward P_in, the arc, the tangent point toward P_out. Of the two ways round, the open one: the arc on
    the side away from both ends (its middle against the sum of the directions to them), so the two parts leaving the
    sheave never cross. Returns the points and the angle turned."""
    def q2(P):
        d = np.asarray(P, float) - C
        return np.array([d @ e, d @ ax])
    q1, q2_ = q2(P_in), q2(P_out)
    away = -(q1 / max(np.linalg.norm(q1), 1e-9) + q2_ / max(np.linalg.norm(q2_), 1e-9))
    best = None
    for sense in (1, -1):
        a1, b1 = math.atan2(q1[1], q1[0]), math.acos(min(1.0, R / max(np.linalg.norm(q1), R + 1e-9)))
        a2, b2 = math.atan2(q2_[1], q2_[0]), math.acos(min(1.0, R / max(np.linalg.norm(q2_), R + 1e-9)))
        if sense > 0:                                   # anticlockwise in (e, ax)
            t_in, t_out = a1 + b1, a2 - b2
            span = (t_out - t_in) % (2 * math.pi)
        else:
            t_in, t_out = a1 - b1, a2 + b2
            span = (t_in - t_out) % (2 * math.pi)
        mid = t_in + sense * span / 2
        far = (math.cos(mid) * away[0] + math.sin(mid) * away[1]) if np.linalg.norm(away) > 0.05 else 0.0
        score = (-round(far, 9), span)                  # the arc's middle away from the ends (else the shorter way)
        if best is None or score < best[0]:
            best = (score, sense, t_in, span)
    _, sense, t_in, span = best
    k = max(3, int(math.ceil(math.degrees(span) / k_deg)))
    th = t_in + sense * span * np.arange(k + 1) / k
    pts = C[None] + R * (np.cos(th)[:, None] * e[None] + np.sin(th)[:, None] * ax[None])
    return list(pts), math.degrees(span)


def fleet_deg(n, d):
    """A rope's angle (degrees) to a sheave's plane (n the sheave's axle)."""
    return abs(math.degrees(math.asin(min(1.0, abs(float(unit(d) @ unit(n)))))))


class Lead:
    """A bronze block on a link from a fixed hole (a padeye's on deck, an eye's on the boom), one sheave (a becket at
    its tail if asked). It hangs toward the resultant of its ropes' pulls, its sheave in the plane of the two parts
    round it."""

    def __init__(self, hole, hole_axis, sheave_d, rope_d, group, becket=False):
        self.hole = np.asarray(hole, float)
        self.hole_axis = unit(hole_axis)
        self.Rs = sheave_d / 2
        self.rope_d, self.sheave_d = rope_d, sheave_d
        self.Rc = self.Rs + BLK["cheek_over"]
        self.reach = self.Rc + 0.03 + BLK["lug"] - BLK["lug_height"] / 2
        self.link = SR["runners"]["padeye"]["link"]
        self.group = group
        self.becket = becket
        self.ax = UP.copy()
        self.n = Y.copy()
        self.e = np.cross(self.n, self.ax)

    @property
    def C(self):
        return self.hole + (self.link + self.reach) * self.ax

    def becket_eye(self):
        bl = BLK["becket"][0]
        return {"hole": self.C + (self.Rc + bl - 0.0175) * self.ax, "axis": self.e}

    def orient(self, a, b, extra=()):
        """Hang toward the pulls toward points a and b (the parts round the sheave) and `extra` (a becket's part)."""
        def want(C):
            s = unit(a - C) + unit(b - C) + sum((unit(p - C) for p in extra), np.zeros(3))
            return unit(s if np.linalg.norm(s) > 1e-6 else unit(a - C) - unit(b - C))
        # the block's centre moves as it turns on its link, so the pulls on it change: a damped fixed point (a block
        # close to its ropes' far ends would swing past it undamped)
        L = self.link + self.reach
        ax = want(self.hole)
        for _ in range(400):
            nxt = ax + 0.5 * (want(self.hole + L * ax) - ax)
            nxt = unit(nxt) if np.linalg.norm(nxt) > 1e-6 else want(self.hole + L * ax)
            done = np.linalg.norm(nxt - ax) < 1e-11
            ax = nxt
            if done:
                break
        else:
            raise ValueError(f"{self.group}: the block finds no way to hang")
        self.ax = ax
        C = self.C
        n = np.cross(unit(a - C), unit(b - C))
        if np.linalg.norm(n) < 0.05:
            n = np.cross(self.ax, UP) if abs(self.ax @ UP) < 0.9 else np.cross(self.ax, X)
        self.n = unit(n - (n @ self.ax) * self.ax)
        self.e = np.cross(self.n, self.ax)

    def turn(self, P_in, P_out):
        return wrap(self.C, self.ax, self.e, self.Rs, P_in, P_out)

    def build(self, part, cat=CAT_BLOCK):
        H = self.hole + self.link * self.ax
        B = rigging.Block(part, H, self.ax, self.e, 1, self.rope_d, self.sheave_d, self.group, becket=self.becket,
                          lug_axis=self.hole_axis, cat=cat)
        if np.linalg.norm(B.C - self.C) > 1e-6:
            raise ValueError(f"{self.group}: the block's centre moved")
        link_ring(part, self.hole, H, self.hole_axis, self.group, cat)
        return B


# ------------------------------------------------------------------------------------------------ the plan mask
class PlanMask:
    """What stands on the deck up to `zmax` above it, on a plan grid (`cell`), and the deck's edge: where a coil may
    lie."""

    def __init__(self, sheer, cell=0.02, zmax=0.25, margin=0.12):
        self.c, self.zmax = cell, zmax
        self.x0, self.y0 = -22.0, -3.6
        self.nx, self.ny = int(41.0 / cell), int(7.2 / cell)
        sheer = np.asarray(sheer, float)
        o = np.argsort(sheer[:, 0])
        xs = self.x0 + (np.arange(self.nx) + 0.5) * cell
        ys = self.y0 + (np.arange(self.ny) + 0.5) * cell
        hb = np.interp(xs, sheer[o, 0], np.abs(sheer[o, 1]), left=0.0, right=0.0)
        self.occ = np.abs(ys)[None, :] > (hb - margin)[:, None]

    def _mark(self, xy):
        xy = np.asarray(xy, float).reshape(-1, 2)
        i = np.floor((xy[:, 0] - self.x0) / self.c).astype(int)
        j = np.floor((xy[:, 1] - self.y0) / self.c).astype(int)
        ok = (i >= 0) & (i < self.nx) & (j >= 0) & (j < self.ny)
        self.occ[i[ok], j[ok]] = True

    def add_mesh(self, V, F):
        V = np.asarray(V, float)
        if not len(V) or not len(F):
            return
        T = deck.tris_of(F)
        a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        cen = (a + b + c) / 3
        near = (np.abs(cen[:, 1]) < 3.6) & (cen[:, 0] > -22.0) & (cen[:, 0] < 19.0)
        lo = np.minimum(np.minimum(a[:, 2], b[:, 2]), c[:, 2])
        hi = np.maximum(np.maximum(a[:, 2], b[:, 2]), c[:, 2])
        dz = shell.deck_z(cen[:, 0], np.clip(cen[:, 1], -3.3, 3.3))
        keep = near & (lo < dz + self.zmax + 0.05) & (hi > dz + 0.004)
        a, b, c = a[keep], b[keep], c[keep]
        if not len(a):
            return
        L = np.maximum(np.maximum(np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1)),
                       np.linalg.norm(a - c, axis=1))
        k = np.clip(np.ceil(L / (0.7 * self.c)).astype(int), 1, 80)
        for kk in np.unique(k):
            sel = k == kk
            u, v = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1))
            m = (u + v) <= kk
            u, v = u[m] / kk, v[m] / kk
            P = (a[sel][:, None] * (1 - u - v)[None, :, None] + b[sel][:, None] * u[None, :, None]
                 + c[sel][:, None] * v[None, :, None]).reshape(-1, 3)
            dzp = shell.deck_z(P[:, 0], np.clip(P[:, 1], -3.3, 3.3))
            self._mark(P[(P[:, 2] < dzp + self.zmax) & (P[:, 2] > dzp + 0.003)][:, :2])

    def add_poly(self, poly):
        from matplotlib.path import Path
        poly = np.asarray(poly, float)[:, :2]
        lo, hi = poly.min(0), poly.max(0)
        xs = np.arange(lo[0] - self.c, hi[0] + self.c, self.c / 2)
        ys = np.arange(lo[1] - self.c, hi[1] + self.c, self.c / 2)
        G = np.array(np.meshgrid(xs, ys)).reshape(2, -1).T
        self._mark(G[Path(poly).contains_points(G)])

    def add_path(self, P, r):
        P = np.asarray(P, float)
        for p0, p1 in zip(P[:-1], P[1:]):
            L = float(np.linalg.norm((p1 - p0)[:2]))
            for t in np.linspace(0.0, 1.0, max(2, int(L / (self.c / 2)) + 2)):
                q = p0 + t * (p1 - p0)
                if q[2] - r < deck_z(q[0], q[1]) + self.zmax:
                    self.add_disc(q[:2], r + self.c)

    def disc(self, c, R):
        g = np.arange(-R, R + self.c / 2, self.c / 2)
        G = np.array(np.meshgrid(g, g)).reshape(2, -1).T
        return G[np.linalg.norm(G, axis=1) <= R] + np.asarray(c[:2], float)[None]

    def add_disc(self, c, R):
        self._mark(self.disc(c, R))

    def free(self, c, R):
        G = self.disc(c, R)
        i = np.floor((G[:, 0] - self.x0) / self.c).astype(int)
        j = np.floor((G[:, 1] - self.y0) / self.c).astype(int)
        if (i < 0).any() or (i >= self.nx).any() or (j < 0).any() or (j >= self.ny).any():
            return False
        return not self.occ[i, j].any()


def coil_radius(L, d, layers=4):
    co = RN["coil"]
    p = d + co["gap"]
    return min(max(math.sqrt(co["r_in"] ** 2 + L * p / (layers * math.pi)), 0.14), co["r_out"])


def place_coil(mask, want, near, R, reach):
    """The free plan point nearest `want` for a coil of radius R, its edge no further than `reach` from `near` and at
    least a hand's breadth from it (the rope comes to the coil from outside)."""
    want, near = np.asarray(want[:2], float), np.asarray(near[:2], float)
    for rad in np.arange(0.0, 2.0, 0.03):
        m = max(1, int(2 * math.pi * rad / 0.03))
        for k in range(m):
            a = 2 * math.pi * k / m
            c = want + rad * np.array([math.cos(a), math.sin(a)])
            if not 0.06 <= np.linalg.norm(c - near) - R <= reach:
                continue
            if mask.free(c, R + 0.015):
                return c
    raise ValueError(f"no room on deck for a coil of radius {R:.2f} m near {np.round(want, 2)}")


# ------------------------------------------------------------------------------------------------ the deck's gear
class Deckwork:
    """The winches and cleats, each winch's geometry for the ropes."""

    def __init__(self, stored):
        self.parts = {"Winches": SparPart("Winches"), "RunningFittings": SparPart("RunningFittings")}
        self.w, self.cleats = {}, {}
        wp = self.parts["Winches"]
        for name, wn in RN["winches"].items():
            if name == "note":
                continue
            for sd in ((1, -1) if wn.get("both_sides") else (1,)):
                at = plan(wn["at"], sd)
                group = f"{name} winch" + (f", {side_name(sd)}" if wn.get("both_sides") else "")
                if wn["size"] == "reel":
                    hk = wn["halyard"]
                    g = winches.reel(wp, at, wn["pad"], group, stored_m=stored[hk],
                                     d=rope_spec(RN["halyards"][hk]["rope"])["d"])
                else:
                    g = winches.capstan(wp, at, wn["size"], wn["pad"], group)
                g.update(name=name, sd=sd, group=group, at=at, pad=wn["pad"])
                self.w[(name, sd)] = g
                if "cleat" in wn:
                    dx, dy, hd = wn["cleat"]
                    O = at + np.array([dx, sd * dy])
                    cl = winches.cleat(wp, O, sd * hd, wn["size"], f"{group} cleat")
                    cl["group"] = f"{group} cleat"
                    self.cleats[(name, sd)] = cl

    def padeyes(self, pulls, sheer):
        """Each lead block's padeye (both sides where asked), or its car on a sheet track (track_car), its eye's plane
        along the mean plan pull on it over the suits and both tacks (`pulls`: {(name, sd): [plan directions]}; the
        other side's come mirrored)."""
        fp = self.parts["RunningFittings"]
        out = {}
        for name, bl in RN["blocks"].items():
            if name in ("note", "boom"):
                continue
            for sd in ((1, -1) if bl.get("both_sides") else (0,)):
                P = plan(bl["padeye"], sd if sd else 1)
                ds = list(pulls.get((name, sd), []))
                if sd:
                    ds += [np.array([v[0], -v[1]]) for v in pulls.get((name, -sd), [])]
                else:                                     # a centreline block works both tacks
                    ds += [np.array([v[0], -v[1]]) for v in ds]
                toward = unit(np.r_[np.mean(ds, axis=0), 0.0]) if ds else X
                group = f"{bl['name']} {'car' if 'track' in bl else 'padeye'}" + (f", {side_name(sd)}" if sd else "")
                n0 = len(fp.masses)
                if "track" in bl:
                    hole, pnrm = track_car(fp, P, toward, group, bl["track"], sheer)
                    cat = CAT_TRACK
                else:
                    hole, pnrm = rigging.padeye(fp, P, toward, group)
                    cat = CAT_BLOCK
                for m in fp.masses[n0:]:
                    m["part"] = cat
                out[(name, sd)] = {"hole": hole, "axis": pnrm, "group": group, "toward": toward[:2]}
        return out


def track_car(part, P, toward, group, span, sheer):
    """A bronze sheet track on the deck parallel to its edge (as far in from the sheer as the plan point P), from
    span[0] m abaft P to span[1] m forward of it, with a car at P carrying an eye in the plane of `toward`: the eye's
    hole is where rigging.padeye's would be (its height above the deck at P, its axis square to `toward`), so a lead
    from it is the same as from a padeye. The track is labelled 'track' (it lies on the deck), the car and its eye
    'padeye' (the block's link goes through the eye). Returns the hole and its axis."""
    tk = RN["track"]
    pe = SR["runners"]["padeye"]
    s = np.asarray(sheer, float)
    o = np.argsort(s[:, 0])

    def half(x):
        return np.interp(x, s[o, 0], np.abs(s[o, 1]))
    sd = 1.0 if P[1] > 0 else -1.0
    inb = float(half(P[0])) - abs(float(P[1]))
    W, h, let = tk["width"], tk["height"], tk["let_in"]
    xs = np.linspace(P[0] - span[0], P[0] + span[1], 31)
    path = np.column_stack([xs, sd * (half(xs) - inb)])
    t2 = np.gradient(path, axis=0)
    t2 /= np.linalg.norm(t2, axis=1)[:, None]
    n2 = np.column_stack([-t2[:, 1], t2[:, 0]])
    # the bar's section, its ends sloped down to the deck over 'end' m
    r = 0.004
    c45 = r * (1 - math.sqrt(0.5))
    sec = [(-W / 2, -let - 0.003), (W / 2, -let - 0.003), (W / 2, h - r), (W / 2 - c45, h - c45), (W / 2 - r, h),
           (-W / 2 + r, h), (-W / 2 + c45, h - c45), (-W / 2, h - r)]
    rings = []
    for k, (q, nn) in enumerate(zip(path, n2)):
        e = min(abs(xs[k] - xs[0]), abs(xs[-1] - xs[k]))
        f = min(1.0, 0.35 + 0.65 * e / 0.03)
        pts = np.array([[q[0] + w * nn[0], q[1] + w * nn[1]] for w, _ in sec])
        zd = shell.deck_z(pts[:, 0], pts[:, 1])
        z = [zd[j] + (hh if hh < 0 else hh * f) for j, (_, hh) in enumerate(sec)]
        rings.append(np.column_stack([pts, z]))
    V, F = deck.loft_rings(rings)
    rigging.solid(part, V, F, "Bronze", lab(group, "track"), CAT_TRACK)
    # the car on the track at P, square to the track there
    tp = np.array([0.02, sd * float(half(P[0] + 0.01) - half(P[0] - 0.01))])
    tp /= np.linalg.norm(tp)
    t = np.r_[tp, 0.0]
    nn = np.r_[-tp[1], tp[0], 0.0]
    zd = deck_z(P[0], P[1])
    cl, cwid, ch = tk["car"]
    base = deck.rrect(0.0, 0.0, cl, cwid, 0.012)
    Oc = np.array([P[0], P[1], zd])
    lo = Oc + (h - 0.003) * UP + base[:, :1] * t + base[:, 1:2] * nn
    hi = Oc + (h + ch) * UP + 0.94 * (base[:, :1] * t + base[:, 1:2] * nn)
    V, F = deck.loft_rings([lo, Oc + (h + ch - 0.006) * UP + base[:, :1] * t + base[:, 1:2] * nn, hi])
    rigging.solid(part, V, F, "Bronze", lab(group, "padeye"), CAT_TRACK)
    # the eye on the car, in the padeye's plane: its foot no wider than the car's top along `toward`
    d = unit(np.array([toward[0], toward[1], 0.0]))
    nrm = np.cross(UP, d)
    hole = pe["hole_above_deck"]
    rr = pe["height"] - hole
    reach = min(abs(0.47 * cl / max(abs(float(d @ t)), 1e-6)), abs(0.47 * cwid / max(abs(float(d @ nn)), 1e-6)))
    wb = min(reach, rr + 0.004)
    q = np.linspace(0.0, math.pi, 11)
    zf = h + ch - 0.004
    poly = [(wb, zf)] + [(rr * math.cos(a), hole + rr * math.sin(a)) for a in q] + [(-wb, zf)]
    et = pe["thickness"]
    rigging.flat(part, poly, Oc, d, UP, nrm, -et / 2, et / 2, "Bronze", lab(group, "padeye"), CAT_TRACK)
    return np.array([P[0], P[1], zd + hole]), nrm


# ------------------------------------------------------------------------------------------------ the mast's boxes
def box_frame(h, out_dir):
    """A sheave box's frame on the mast's surface `h` above the deck, facing `out_dir` (square to the mast's axis): the
    halyard runs over its sheave between the inside of the mast and the outside."""
    mb = RN["mast_boxes"]
    s = spars.s_at(h)
    A = spars.A
    d = np.asarray(out_dir, float)
    d = unit(d - (d @ A) * A)
    Ps = spars.surface_toward(s, d)
    out = Ps - spars.at(s)
    out = unit(out - (out @ A) * A)
    return {"surface": Ps, "out": out, "A": A, "side": np.cross(A, out), "C": Ps + mb["sheave_out"] * out,
            "R": mb["sheave_r"], "h": h}


def build_box(part, fr, group):
    """The bronze box: a rounded slab let into the mast's skin and proud of it, weighed as an 8 mm casting."""
    mb = RN["mast_boxes"]
    V, F = deck.slab(deck.rrect(0.0, 0.0, mb["height"], mb["width"], 0.015), fr["surface"], fr["A"], fr["side"],
                     fr["out"], -mb["sunk"], mb["proud"])
    part.add(V, F, "Bronze", None, lab(group, "halyard box"))
    part.weigh(V, F, ("cast", spars.BRZ, 0.008), CAT_BLOCK)         # a hollow casting round its sheave
    return fr


def face_dir(deg):
    a = math.radians(deg)
    return math.cos(a) * spars.FW + math.sin(a) * Y


def over_sheave(box, P, down):
    """The halyard's turn over a box's sheave from the inside of the mast to where it leaves toward P: at a foot box
    (`down`) it comes down inside and turns out under the sheave, aloft it comes up inside and turns out over it.
    Returns the points (inside first) and the lead's angle to the sheave's plane."""
    C, R, e, a = box["C"], box["R"], box["out"], box["A"]
    d = np.asarray(P, float) - C
    q = np.array([d @ e, d @ a])
    phi, beta = math.atan2(q[1], q[0]), math.acos(min(1.0, R / np.linalg.norm(q)))
    th = phi - beta if down else phi + beta
    if down:
        span = (th - math.pi) % (2 * math.pi)
        ts = math.pi + span * np.linspace(0.0, 1.0, max(4, int(span / math.radians(10))))
    else:
        span = (math.pi - th) % (2 * math.pi)
        ts = math.pi - span * np.linspace(0.0, 1.0, max(4, int(span / math.radians(10))))
    pts = [C + R * (math.cos(t) * e + math.sin(t) * a) for t in ts]
    return pts, fleet_deg(np.cross(a, e), np.asarray(P, float) - pts[-1])


# ------------------------------------------------------------------------------------------------ ropework at a winch
def drum_entry(w, Q, r):
    """Where a rope from Q meets the capstan's drum (its centreline at the ribs' radius plus r) on its bottom turn."""
    Rr = w["R"] + r + 0.0005
    p, th = winches.tangent_from(Q, w["foot"], Rr, 1)
    return np.array([p[0], p[1], w["z_lo"] + r]), th, Rr


def reel_entry(w, Q, r):
    """Where a wire from Q meets the wire wound on a reel, halfway up it."""
    Rr = w["wound_r"] + r
    p, th = winches.tangent_from(Q, w["foot"], Rr, 1)
    return np.array([p[0], p[1], 0.5 * (w["z_lo"] + w["z_hi"])]), th


def rise_deg(Q, D):
    return math.degrees(math.atan2(D[2] - Q[2], float(np.linalg.norm((D - Q)[:2]))))


def turns_to_cleat(line, w, cl, th_in, Rr):
    """The rope's turns up the drum from its bottom turn at th_in, the tail off its top turn to the cleat, the hitch.
    Returns the turns' top and the angle round the drum."""
    sp = line.spec
    d, r = sp["d"], sp["r"]
    # the hitch's side and far horn follow where the tail comes from: the point it leaves the drum, which itself
    # follows where the hitch starts
    def sides(v):
        return (float(v @ cl["Y"]) <= 0, float(v @ cl["X"]) >= 0)
    lead = unit(np.r_[w["foot"][:2] - cl["O"][:2], 0.0])
    for _ in range(4):
        hitch = winches.cleat_hitch(cl, d, lead)
        first = hitch[0]
        Pt, th_out = winches.tangent_from(first, w["foot"], Rr, -1)
        nxt = unit(np.r_[Pt - cl["O"][:2], 0.0])
        if sides(nxt) == sides(lead):
            break
        lead = nxt
    else:
        raise ValueError(f"{line.group}: no side of {cl['group']} for its tail to come in on")
    tw = winches.turns(w["foot"], Rr, w["z_lo"] + r, th_in, th_out, RN["winch"]["sizes"][w["size"]]["turns"], d)
    if tw[-1][2] + r > w["z_hi"]:
        raise ValueError(f"{line.group}: its turns climb past the head of the drum on {w['group']}")
    drum = ("Winches", lab(w["group"], "drum"))
    line.add(tw, allow=[drum], name="turns")
    E = tw[-1]
    # off the top turn level for a hand's breadth (clear of the turns under it), then down to the cleat
    L = float(np.linalg.norm((first - E)[:2]))
    s1 = min(0.14, 0.4 * L)
    pts = []
    for s in np.linspace(0.0, L, max(6, int(L / 0.02))):
        xy = E[:2] + (first[:2] - E[:2]) * (s / L)
        f = smooth01((s - s1) / max(L - s1, 1e-6))
        pts.append(np.array([xy[0], xy[1], E[2] + (first[2] - E[2]) * f]))
    line.add(pts, allow=[drum], name="tail to the cleat")
    line.add(hitch, allow=[("Winches", lab(cl["group"], "cleat")), ("Deck", "Deck")], name="hitch")
    return {"turns_top_z": round(float(E[2]), 3), "drum_z_hi": round(float(w["z_hi"]), 3)}


def coil_down(line, mask, length, reach=1.0):
    """What is left of the rope flemished down on the deck: the coil laid just beyond where the rope ends, to the side
    its winding comes round from, so the rope runs straight on into the coil's outer turn (or, where the deck has no
    room there, at the nearest free spot); the rope goes on along the deck from its own direction into the coil's in a
    smooth curve. Returns the coil's report."""
    sp = line.spec
    d, r = sp["d"], sp["r"]
    P = np.asarray(line.P, float)
    H = P[-1]
    k = len(P) - 2
    while k > 0 and np.linalg.norm((H - P[k])[:2]) < 2 * d:
        k -= 1
    t = unit(np.r_[(H - P[k])[:2], 0.0])[:2]          # the rope's heading where it ends, in plan
    R = coil_radius(max(length, 0.5), d)
    run = max(0.08, 3 * d)
    ideal = H[:2] + run * t + R * winches.cw(t)[:2]    # the outer turn's winding (clockwise) runs on along t
    c = place_coil(mask, ideal, H, R, reach)
    S, a0 = winches.tangent_from(H, c, R, 1)
    tS = unit(winches.cw(S - c))[:2]
    H2 = H[:2]
    kc = max(0.03, 0.4 * float(np.linalg.norm(S - H2)))
    B = [H2, H2 + kc * t, S - kc * tS, S]
    lie = r + RN["coil"]["gap"]
    n = max(4, int(float(np.linalg.norm(S - H2)) / 0.02))
    path = []
    for q in np.linspace(0.0, 1.0, n):
        xy = ((1 - q) ** 3 * B[0] + 3 * (1 - q) ** 2 * q * B[1] + 3 * (1 - q) * q * q * B[2] + q ** 3 * B[3])
        z_lie = deck_z(xy[0], xy[1]) + lie
        path.append(np.array([xy[0], xy[1], H[2] + (z_lie - H[2]) * smooth01(q / 0.35)]))
    line.add(path, allow=[("Deck", "Deck")], name="to its coil")
    left = length - seg_len(path)
    if left < 0.3:
        raise ValueError(f"{line.group}: the rope is {0.3 - left:.2f} m too short to reach its coil")
    Pc, layers = winches.coil(c, d, left, a0, RN["coil"]["r_in"], R, RN["coil"]["gap"])
    line.add(Pc, allow=[("Deck", "Deck")], name="coil")
    mask.add_disc(c, R + 0.01)
    return {"centre": [round(float(c[0]), 3), round(float(c[1]), 3)], "radius_m": round(R, 3), "layers": layers,
            "length_m": round(left, 2), "moved_m": round(float(np.linalg.norm(c - ideal)), 3)}


# ------------------------------------------------------------------------------------------------ the whole
def build(pts, rr, sl_parts, footprints, sheer, obstacles):
    """{object name: SparPart} and the report. `sl_parts`: the sails' parts (their cringles); `obstacles(suit)`: [(V,
    F)] of everything else on deck in that suit, for where the coils may lie (the hull's frame, spars posed)."""
    zp = spars.Z_P
    SETTLED.clear()
    stored = {k: round(hy["aloft_z"] - zp - 1.0, 2) for k, hy in RN["halyards"].items() if k != "note"}
    dw = Deckwork(stored)
    parts = dict(dw.parts)
    fit = parts["RunningFittings"]
    weighed = Weighed()
    G = np.asarray(pts["gooseneck_pin"], float)
    suits = sails.SL["suits"]

    def boom_R(suit):
        return sails.rot(spars.A, math.radians(suits[suit].get("boom_deg", 0.0)))

    def boom_eye(suit, key):
        R = boom_R(suit)
        ey = pts["boom"]["eyes"][key]
        return {"hole": G + R @ (np.asarray(ey["hole"], float) - G), "axis": R @ np.asarray(ey["axis"], float)}

    pole_eyes = {k: {a: np.asarray(b, float) for a, b in v.items()} for k, v in pts["pole"]["eyes"].items()}

    # -- the halyards' boxes on the mast, and each wire's lead from its foot box to its reel (fixed)
    hal = {}
    fixed_lines = []
    for k, hy in RN["halyards"].items():
        if k == "note":
            continue
        spec = rope_spec(hy["rope"])
        w = dw.w[(hy["winch"], 1)]
        if w["kind"] != "reel":
            raise ValueError(f"{hy['label']}: every halyard is wire on a reel winch")
        aloft = build_box(fit, box_frame(hy["aloft_z"] - zp, face_dir(hy["face_deg"])), hy["label"])
        # the foot box faces where the wire meets the wire on its reel, so the wire leaves its sheave square
        fh = hy["foot_h"]
        D = np.r_[w["at"], w["z_lo"]]
        for _ in range(12):
            D0 = D
            foot = box_frame(fh, D - spars.at(spars.s_at(fh)))
            pts_f, fl = over_sheave(foot, D, True)
            D, _ = reel_entry(w, pts_f[-1], spec["r"])
        settled(f"{hy['label']} (foot box to its reel)", [D0], [D])
        build_box(fit, foot, hy["label"])
        h = {"spec": spec, "group": hy["label"], "w": w, "aloft": aloft, "foot": foot, "cfg": hy,
             "inside_m": float(np.linalg.norm(aloft["C"] - foot["C"]))}
        own = [("Mast", ""), ("RunningFittings", lab(hy["label"], "halyard box"))]
        line = Line(hy["label"], spec, "RunningFittings")
        line.add(pts_f, allow=own, name="over the foot box's sheave")
        line.add([D], allow=[("Winches", lab(w["group"], "wire on reel"))], name="to the reel")
        lay(fit, line)
        fixed_lines.append(line)
        h["foot_m"] = line.length()
        h["foot_fleet_deg"] = round(fl, 2)
        h["own"] = own
        hal[k] = h

    # -- each suit's ropes; the padeyes' planes come from a first pass's pulls
    pulls = {}
    pad = None
    out = {}
    for pass_ in (0, 1):
        if pass_:
            pad = dw.padeyes(pulls, sheer)
            # the halyards' and padeyes' fixed parts weigh once; the sheet tracks and their cars are deck hardware
            tracks = [m for m in fit.masses if m["part"] == CAT_TRACK]
            weighed.by_key[("fixed", "boxes and padeyes")] = [m for m in fit.masses if m["part"] != CAT_TRACK]
            fit.masses = []
        for sname in SUITS:
            sp = SparPart(f"Running.{sname}")
            mask = None
            if pass_:
                mask = PlanMask(sheer)
                for poly in footprints.values():
                    mask.add_poly(poly)
                for V, F in list(obstacles(sname)) + [(parts["Winches"].V, parts["Winches"].F), (fit.V, fit.F)]:
                    mask.add_mesh(V, F)
            out[sname] = _suit(sname, sp, dw, pad, pulls, hal, sl_parts, rr, boom_eye, pole_eyes, mask, weighed)
            if pass_:
                parts[sp.name] = sp
    fixed_recs = [dict(ln.record(), name=f"{ln.group} (foot box to its reel)") for ln in fixed_lines]
    rep = {"suits": {k: v["report"] for k, v in out.items()},
           "ropes": {k: [ln.record() for ln in v["lines"]] + fixed_recs for k, v in out.items()},
           "padeyes": {v["group"]: {"hole": [round(float(a), 3) for a in v["hole"]],
                                    "toward": [round(float(a), 3) for a in v["toward"]]} for v in pad.values()},
           "winches": {g["group"]: {"size": g["size"], "at": [round(float(a), 3) for a in g["at"]], "pad_m": g["pad"],
                                    "top_z": round(g["top"], 3)} for g in dw.w.values()},
           "halyards": {k: {"stored_on_reel_m": stored[k],
                            "inside_mast_m": round(h["inside_m"], 2), "foot_box_fleet_deg": h.get("foot_fleet_deg")}
                        for k, h in hal.items()}}
    rep["weights"] = weights(parts, weighed, out, hal, stored, tracks)
    rep["settled"] = {"tolerance_mm": SETTLE_TOL * 1000,
                      "worst_last_pass_mm": round(max(SETTLED.values()) * 1000, 4),
                      "loops": {k: round(v * 1000, 4) for k, v in sorted(SETTLED.items())}}
    return parts, rep


def _suit(sname, sp, dw, pad, pulls, hal, sl_parts, rr, boom_eye, pole_eyes, mask, weighed):
    """One suit's ropes. Without `pad` (the first pass) only the lead blocks' pulls on their padeyes are gathered."""
    first = pad is None
    cfg = sails.SL["suits"][sname]
    rep = {"ropes": {}, "rise_deg": {}, "fleet_deg": {}, "coils": {}, "pairs": []}
    lines = []
    pending = []                                  # (line, length, reach, report key): coiled once all are led

    def pole_eye(k):
        """The pole's eyes as built (set at set_deg): the suit must pose it there, or its ropes would miss it."""
        if cfg.get("pole") == "stowed" or abs(cfg.get("pole_deg", math.nan) - spars.RG["pole"]["set_deg"]) > 1e-6:
            raise ValueError(f"the {sname} suit leads a rope to the pole but does not set it at the built "
                             f"{spars.RG['pole']['set_deg']} degrees")
        return pole_eyes[k]

    def hole_of(name, sd):
        bl = RN["blocks"][name]
        key = (name, sd if bl.get("both_sides") else 0)
        if first:
            P = plan(bl["padeye"], sd if bl.get("both_sides") else 1)
            return on_deck(P, SR["runners"]["padeye"]["hole_above_deck"]), Y.copy(), key
        return pad[key]["hole"], pad[key]["axis"], key

    def note_pull(key, ld):
        if first:
            v = (ld.C - ld.hole)[:2]
            pulls.setdefault(key, []).append(v / max(float(np.linalg.norm(v)), 1e-9))

    def pair(a, b):
        """Two fittings that meet by design (a block's link through its padeye, a shackle in a becket)."""
        if [a, b] not in rep["pairs"]:
            rep["pairs"].append([a, b])

    def build_block(ld, key):
        if key is not None and pad is not None:
            pair(ld.group, pad[key]["group"])
        # one block per padeye (several ropes lead through some of them, suit by suit); the boom's by name
        return weighed(sp, ("block", key if key is not None else ld.group), lambda: ld.build(sp))

    def build_shackle(g, spec, group, key=None):
        weighed(sp, ("shackle", key if key is not None else group), lambda: shackle_build(sp, g, spec, group))

    def sheave_fleet(name, B, P_prev, arc, P_next):
        rep["fleet_deg"][name] = [round(fleet_deg(B.n, arc[0] - P_prev), 2), round(fleet_deg(B.n, P_next - arc[-1]), 2)]

    # ---------------------------------------------------------------- sheets, guy and foreguy
    for sk, sh in RN["sheets"].items():
        if sk == "note" or sname not in sh["suits"]:
            continue
        spec = rope_spec(sh["rope"])
        sd = -LEE if sh.get("side") == "windward" else LEE
        group = f"{sh['label']}, {side_name(sd)}"
        src, corner = sh["from"]
        if src == "pole":
            eye = pole_eye(corner)
            anchor = eye["hole"]
            allow0 = [("SpinnakerPole", "Pole end")]
            shk = lambda lead: eye_shackle(eye, lead, spec)  # noqa: E731
        else:
            cr = sl_parts[src].cringles[corner]
            anchor = cr["c"]
            allow0 = [(src, "")]
            shk = lambda lead: ring_shackle(cr, lead, spec)  # noqa: E731
        w, cl = dw.w[(sh["winch"], sd)], dw.cleats[(sh["winch"], sd)]
        leads = []
        for via in sh["via"]:
            hole, hax, key = hole_of(via, sd)
            bl = RN["blocks"][via]
            leads.append((Lead(hole, hax, bl["sheave_d"], spec["d"], f"{sh['label']} {bl['label']}, {side_name(sd)}"),
                          key))
        T = anchor.copy()
        D = np.r_[w["foot"][:2], w["z_lo"] + spec["r"]]
        arcs = []
        for _ in range(14):
            T0, D0 = T, D
            targets = [ld.C for ld, _ in leads] + [D]
            prev = T
            arcs = []
            for i, (ld, _) in enumerate(leads):
                ld.orient(prev, targets[i + 1])
                a, _ = ld.turn(prev, targets[i + 1])
                arcs.append(a)
                prev = a[-1]
            D, th_in, Rr = drum_entry(w, prev, spec["r"])
            g = shk((arcs[0][0] if arcs else D) - anchor)
            T = g["T"]
        settled(f"{group} ({sname}{', first pass' if first else ''})", [T0, D0], [T, D])
        for ld, key in leads:
            note_pull(key, ld)
        if first:
            continue
        build_shackle(g, spec, group, key=(sh["label"], sd))
        line = Line(group, spec, sp.name)
        u0 = unit((arcs[0][0] if arcs else D) - T)
        line.add([T, T + min(0.3, 0.5 * float(np.linalg.norm((arcs[0][0] if arcs else D) - T))) * u0],
                 allow=allow0 + [(sp.name, lab(group, ""))], name="from the corner")
        prev = T
        for i, ((ld, key), a) in enumerate(zip(leads, arcs)):
            B = build_block(ld, key)
            through(line, line.P[-1], a, arcs[i + 1][0] if i + 1 < len(arcs) else D, [(sp.name, lab(ld.group, ""))])
            nxt = leads[i + 1][0].C if i + 1 < len(leads) else D
            sheave_fleet(ld.group, B, prev, a, nxt)
            prev = a[-1]
        u1 = unit(D - prev)
        line.add([D - 0.06 * u1], name="lead to the drum")
        line.add([D], allow=[("Winches", lab(w["group"], "drum"))], name="onto the drum")
        rep["rise_deg"][group] = [round(rise_deg(prev, D), 2), round(float(np.linalg.norm((D - prev)[:2])), 2)]
        rep["ropes"][group] = {"winch": w["group"], "cut_m": sh["cut_m"],
                               **turns_to_cleat(line, w, cl, th_in, Rr)}
        pending.append((line, sh["cut_m"] - line.length() - 0.2, 1.0, group))
    # the spinnaker's tack lashed to the pole's end eye (the guy has its own eye on the end fitting's sleeve)
    if sname == "Spinnaker" and not first:
        weighed(sp, ("lashing", "tack"), lambda: tack_lashing(sp, sl_parts["Spinnaker.Set"].cringles["tack"],
                                                              pole_eye("end")))

    # ---------------------------------------------------------------- the mainsheet
    ms = RN["mainsheet"]
    spec = rope_spec(ms["rope"])
    group = "Mainsheet"
    w, cl = dw.w[(ms["winch"], LEE)], dw.cleats[(ms["winch"], LEE)]
    bk = RN["blocks"]
    e0, e1 = boom_eye(sname, "mainsheet_0"), boom_eye(sname, "mainsheet_1")
    hA, aA, kA = hole_of("MainsheetAft", 0)
    hF, aF, kF = hole_of("MainsheetFwd", 0)
    BA = Lead(e0["hole"], e0["axis"], bk["boom"]["sheave_d"], spec["d"], "Mainsheet after boom block")
    BF = Lead(e1["hole"], e1["axis"], bk["boom"]["sheave_d"], spec["d"], "Mainsheet forward boom block")
    DA = Lead(hA, aA, bk["MainsheetAft"]["sheave_d"], spec["d"], "Mainsheet after deck block", becket=True)
    DF = Lead(hF, aF, bk["MainsheetFwd"]["sheave_d"], spec["d"], "Mainsheet forward deck block")
    BA.ax = BF.ax = -UP
    D = np.r_[w["foot"][:2], w["z_lo"] + spec["r"]]
    T = DA.becket_eye()["hole"]
    aBA = aDA = aBF = aDF = None
    for _ in range(40):
        T0, D0 = T, D
        BA.orient(T, DA.C if aDA is None else aDA[0])
        DA.orient(BA.C if aBA is None else aBA[-1], BF.C if aBF is None else aBF[0], extra=[BA.C])
        BF.orient(DA.C if aDA is None else aDA[-1], DF.C if aDF is None else aDF[0])
        DF.orient(BF.C if aBF is None else aBF[-1], D)
        aBA, _ = BA.turn(T, DA.C if aDA is None else aDA[0])
        aDA, _ = DA.turn(aBA[-1], BF.C if aBF is None else aBF[0])
        aBF, _ = BF.turn(aDA[-1], DF.C if aDF is None else aDF[0])
        aDF, _ = DF.turn(aBF[-1], D)
        D, th_in, Rr = drum_entry(w, aDF[-1], spec["r"])
        g = eye_shackle(DA.becket_eye(), aBA[0] - DA.becket_eye()["hole"], spec, hold=0.02)
        # damped: undamped, the becket's shackle and the after boom block swing each other to and fro
        T = T0 + 0.5 * (g["T"] - T0)
    settled(f"{group} ({sname}{', first pass' if first else ''})", [T0, D0], [T, D])
    note_pull(kA, DA)
    note_pull(kF, DF)
    if not first:
        for ld, key in ((BA, None), (BF, None), (DA, kA), (DF, kF)):
            ld._B = build_block(ld, key)
        build_shackle(g, spec, group)
        pair(group, DA.group)
        line = Line(group, spec, sp.name)
        line.add([T], name="from the becket")
        line.pieces[-1]["allow"] = [(sp.name, lab(DA.group, ""))]
        seq = [(BA, aBA, T), (DA, aDA, aBA[-1]), (BF, aBF, aDA[-1]), (DF, aDF, aBF[-1])]
        for i, (ld, a, prev) in enumerate(seq):
            nxt = seq[i + 1][1][0] if i + 1 < len(seq) else D
            # each part leaves the block before it (the first, the after deck block's becket), so its lead may touch
            # that block; the becket stands up between the parts that leave the after deck block, so every part may
            # touch the becket, and nothing else of the tackle
            before = seq[i - 1][0] if i else DA
            through(line, line.P[-1], a, nxt, [(sp.name, lab(ld.group, ""))],
                    lead_allow=[(sp.name, lab(before.group, "")), (sp.name, lab(DA.group, "becket"))], name="a part")
            sheave_fleet(ld.group, ld._B, prev, a, nxt)
        u1 = unit(D - aDF[-1])
        line.add([D - 0.06 * u1], name="the fall")
        line.add([D], allow=[("Winches", lab(w["group"], "drum"))], name="onto the drum")
        rep["rise_deg"][group] = [round(rise_deg(aDF[-1], D), 2), round(float(np.linalg.norm((D - aDF[-1])[:2])), 2)]
        rep["ropes"][group] = {"winch": w["group"], "cut_m": ms["cut_m"], **turns_to_cleat(line, w, cl, th_in, Rr),
                               "boom_deg_to_port": cfg.get("boom_deg", 0.0)}
        pending.append((line, ms["cut_m"] - line.length() - 0.2, 1.0, group))
    if first:
        return {"report": rep, "lines": lines}

    # ---------------------------------------------------------------- halyards
    for k, h in hal.items():
        hy, spec = h["cfg"], h["spec"]
        target = hy["suits"].get(sname)
        aloft = h["aloft"]
        own = h["own"][:1] + [("RunningFittings", lab(h["group"], "halyard box"))]
        line = Line(h["group"], spec, sp.name)
        if k == "spinnaker" and target:
            # from the head's block at the crane (slice 6's) into the box under the crane
            hb = sl_parts["Spinnaker.Set"].cringles["halyard_block"]
            cb, dd, side = hb["c"], hb["d"], hb["side"]
            t3 = np.cross(dd, side)
            Rb = 0.045
            P_in = cb - 0.5 * dd
            Q = aloft["C"]
            for _ in range(8):
                Q0 = Q
                arc, _ = wrap(cb, -dd, t3, Rb, P_in, Q)
                pts_a, fl = over_sheave(aloft, arc[-1], False)
                Q = pts_a[-1]
            settled(f"{h['group']} ({sname})", [Q0], [Q])
            line.add([arc[-1]], name="from the block")
            line.add([arc[-1] + 0.08 * unit(Q - arc[-1])], allow=[("Spinnaker.Set", "Spinnaker halyard")],
                     name="out of the block")
            line.add(pts_a[::-1], allow=own + [("Spinnaker.Set", "Spinnaker halyard")], name="over the box's sheave")
        else:
            if target:
                if target == "pole":
                    att = pole_eye("lift")
                    mk = lambda lead: eye_shackle(att, lead, spec)  # noqa: E731
                    anchor, allow0 = att["hole"], [("SpinnakerPole", "Pole end")]
                elif target == "boom":
                    att = boom_eye(sname, "topping_lift")
                    mk = lambda lead: eye_shackle(att, lead, spec)  # noqa: E731
                    anchor, allow0 = att["hole"], [("Boom", "Topping lift eye")]
                else:
                    cr = sl_parts[target].cringles["head"]
                    anchor, allow0 = cr["c"], [(target, "")]
                    if cr["R"] == 0.0:
                        mk = lambda lead: head_shackle(cr, lead, spec)  # noqa: E731
                    else:
                        mk = lambda lead: ring_shackle(cr, lead, spec)  # noqa: E731
                Q = anchor
                for _ in range(8):
                    Q0 = Q
                    pts_a, fl = over_sheave(aloft, Q, False)
                    g = mk(pts_a[-1] - anchor)
                    Q = g["T"]
                settled(f"{h['group']} ({sname})", [Q0], [Q])
            else:
                # out of use: hauled up, its shackle hanging closed a hand under the box's sheave
                pts_a, fl = over_sheave(aloft, aloft["C"] + aloft["R"] * aloft["out"] - aloft["A"], False)
                T = pts_a[-1] - 0.04 * aloft["A"]
                g0 = shackle_geom(np.zeros(3), aloft["side"], aloft["A"], spec, hold=0.0)
                g = shackle_geom(T - (g0["T"] - g0["pin"]), aloft["side"], aloft["A"], spec, hold=0.0)
                allow0 = []
            build_shackle(g, spec, h["group"])
            line.add(pts_a, allow=own, name="over the box's sheave")
            if target:
                line.add([g["T"] + min(0.25, 0.5 * seg_len([g["T"], pts_a[-1]])) * unit(pts_a[-1] - g["T"])],
                         allow=own[1:], name="down from aloft")
            line.add([g["T"]], allow=allow0 + own[1:] + [(sp.name, lab(h["group"], "eye"))], name="to its shackle")
        rep["fleet_deg"][f"{h['group']} box aloft"] = [round(fl, 2)]
        h["aloft_m"] = max(h.get("aloft_m", 0.0), line.length())
        h["aloft_min_m"] = min(h.get("aloft_min_m", math.inf), line.length())
        lay(sp, line)
        lines.append(line)
        mask.add_path(line.P, spec["r"])

    # ---------------------------------------------------------------- the runners' and checkstays' tails
    for kind in ("runner", "checkstay"):
        tl = RN["tails"][kind]
        for sd, state in ((1, "Set"), (-1, "LetOff")):
            side = side_name(sd)
            rec = rr["runners"][kind][side]
            fs = rec[state]["fall_sheave"]
            spec = {"key": f"{kind}_fall", "d": fs["rope_d"], "r": fs["rope_d"] / 2, "kgm": 0.0, "slot": "Rope",
                    "kind": "manila"}
            sgroup = f"{SR['wires'][kind]['label'][:-1]}, {side}, {state.lower()}"
            obj = f"{'Runner' if kind == 'runner' else 'Checkstay'}.{side.capitalize()}.{state}"
            group = f"{'Runner' if kind == 'runner' else 'Checkstay'} tackle's fall, {side}"
            w, cl = dw.w[(tl["winch"], sd)], dw.cleats[(tl["winch"], sd)]
            C, ax, e, Rs = (np.asarray(fs[a], float) for a in ("centre", "ax", "e", "R"))
            Rs = float(Rs)
            P_in = np.asarray(fs["enters"], float) - 0.3 * np.asarray(fs["arrives"], float)
            line = Line(group, spec, sp.name)
            allow_t = [(obj, lab(sgroup, k)) for k in ("sheave", "fall", "becket", "block")]
            if state == "Set":
                D = np.r_[w["foot"][:2], w["z_lo"] + spec["r"]]
                for _ in range(8):
                    D0 = D
                    arc, _ = wrap(C, ax, e, Rs, P_in, D)
                    D, th_in, Rr = drum_entry(w, arc[-1], spec["r"])
                settled(f"{group} ({sname})", [D0], [D])
                line.add(arc, allow=allow_t, name="round the lower block's sheave")
                rep["fleet_deg"][f"{group} (lower block)"] = [round(fleet_deg(np.cross(ax, e), D - arc[-1]), 2)]
                u1 = unit(D - arc[-1])
                line.add([arc[-1] + 0.12 * u1], allow=allow_t, name="out of the block")
                line.add([D - 0.06 * u1], name="lead to the drum")
                line.add([D], allow=[("Winches", lab(w["group"], "drum"))], name="onto the drum")
                rep["rise_deg"][group] = [round(rise_deg(arc[-1], D), 2), round(float(np.linalg.norm((D - arc[-1])[:2])), 2)]
                rep["ropes"][group] = {"winch": w["group"], "rope_m": round(rec["rope_m"], 2),
                                       "falls_m": round(rec[state]["falls_m"], 2),
                                       **turns_to_cleat(line, w, cl, th_in, Rr)}
            else:
                # let off: cast off its winch, the tail lies along the deck from the block to its coil by the winch
                # slack, it leaves the sheave square to the tackle on the inboard side (as it does set), clear of the
                # block's cheeks and head, before it falls away to the deck toward its coil
                inb = e if (np.asarray(w["foot"], float) - C)[:2] @ e[:2] > 0 else -e
                Tside = C + 0.6 * inb
                arc, _ = wrap(C, ax, e, Rs, P_in, Tside)
                line.add(arc, allow=allow_t, name="round the lower block's sheave")
                line.add([arc[-1] + 0.15 * unit(Tside - np.asarray(arc[-1]))], allow=allow_t, name="out of the block")
                rep["ropes"][group] = {"winch": w["group"], "rope_m": round(rec["rope_m"], 2),
                                       "falls_m": round(rec[state]["falls_m"], 2), "cast_off": True}
            pending.append((line, rec["rope_m"] - rec[state]["falls_m"] - line.length(), 1.2, group))

    # ---------------------------------------------------------------- the coils, once everything is led
    for line, _, _, _ in pending:
        mask.add_path(line.P, line.spec["r"])
    for line, left, reach, key in sorted(pending, key=lambda p: -p[1]):
        rep["coils"][key] = coil_down(line, mask, left, reach)
        lay(sp, line)
        lines.append(line)
        mask.add_path(line.P, line.spec["r"])
    return {"report": rep, "lines": lines}


def tack_lashing(part, cr, eye):
    """The spinnaker's tack lashed to the pole's end eye: three turns of small manila through the cringle, round the
    ring's bar nearest the eye, and through the eye (each end's turns square to its own hole, twisting between)."""
    r = 0.005
    Q = cr["c"] + cr["R"] * unit(np.asarray(eye["hole"], float) - cr["c"])
    P2 = np.asarray(eye["hole"], float)
    u = unit(P2 - Q)
    n1 = unit(cr["n"] - (cr["n"] @ u) * u)
    a2 = np.asarray(eye["axis"], float)
    n2 = unit(a2 - (a2 @ u) * u)
    n2 = n2 if n2 @ n1 >= 0 else -n2
    m1, m2 = np.cross(u, n1), np.cross(u, n2)
    rho1 = cr["r"] + r + 0.001
    rho2 = 0.012 + r
    for k in (-1, 0, 1):
        path = [Q + k * 2.2 * r * m1 + rho1 * (math.cos(t) * -u + math.sin(t) * n1)
                for t in np.linspace(-math.pi / 2, math.pi / 2, 9)]
        path += [P2 + k * 2.2 * r * m2 + rho2 * (math.cos(t) * u + math.sin(t) * n2)
                 for t in np.linspace(math.pi / 2, -math.pi / 2, 9)]
        rigging.loop(part, np.array(path)[::-1], r, lab("Spinnaker tack lashing", "lashing"), CAT_ROPE,
                     MANILA * math.pi * r * r)


def weights(parts, weighed, out, hal, stored, tracks=()):
    """The running rigging's weight: the ropes aboard from their cut lengths (both sides' sheets, centred where they are
    led), the wire halyards from their full length (on the reel, at the foot, inside the mast, aloft), and each block,
    shackle, padeye and box once. The winches and cleats, and the sheet tracks with their cars (`tracks`: their
    masses), are reported apart: they are deck hardware (slice 8's)."""
    rows = list(weighed.rows) + weighed.mirrored()
    seen = {}
    for sname, o in out.items():
        for ln in o["lines"]:
            P = np.array(ln.P)
            seen.setdefault(ln.group, (ln, P.mean(0)))
    for sk, sh in RN["sheets"].items():
        if sk == "note":
            continue
        spec = rope_spec(sh["rope"])
        names = [g for g in seen if g.startswith(sh["label"] + ",")]
        c = seen[names[0]][1] if names else np.zeros(3)
        for sd in (1, -1):
            cc = np.array([c[0], sd * abs(c[1]), c[2]])
            rows.append({"part": CAT_ROPE, "kg": round(spec["kgm"] * sh["cut_m"], 2), "centre": cc.tolist(),
                         "how": "cut length", "rope": f"{sh['label']}, {side_name(sd)}"})
    ms = RN["mainsheet"]
    spec = rope_spec(ms["rope"])
    rows.append({"part": CAT_ROPE, "kg": round(spec["kgm"] * ms["cut_m"], 2), "centre": seen["Mainsheet"][1].tolist(),
                 "how": "cut length", "rope": "Mainsheet"})
    for k, h in hal.items():
        spec = h["spec"]
        # the reel stores what the hoist does not use, so the wire is the hoisted suit's: its least length aloft
        L = stored[k] + h["foot_m"] + h["inside_m"] + h.get("aloft_min_m", 0.0)
        mid = 0.5 * (h["aloft"]["C"] + h["foot"]["C"])
        rows.append({"part": CAT_WIRE if spec["slot"] == "WireRope" else CAT_ROPE, "kg": round(spec["kgm"] * L, 2),
                     "centre": mid.tolist(), "how": "length", "rope": h["group"], "length_m": round(L, 2)})
    tot = {}
    for m in rows:
        t = tot.setdefault(m["part"], {"kg": 0.0, "mom": np.zeros(3)})
        t["kg"] += m["kg"]
        t["mom"] += m["kg"] * np.asarray(m["centre"], float)
    cats = {k: {"kg": round(v["kg"], 1), "centre": [round(float(a), 3) for a in v["mom"] / max(v["kg"], 1e-9)]}
            for k, v in tot.items()}
    kg = sum(v["kg"] for v in tot.values())
    mom = sum((v["mom"] for v in tot.values()), np.zeros(3))
    wrow = {}
    for m in parts["Winches"].masses:
        t = wrow.setdefault(m["part"], {"kg": 0.0, "mom": np.zeros(3)})
        t["kg"] += m["kg"]
        t["mom"] += m["kg"] * np.asarray(m["centre"], float)
    wkg = sum(v["kg"] for v in wrow.values())
    wmom = sum((v["mom"] for v in wrow.values()), np.zeros(3))
    tkg = sum(m["kg"] for m in tracks)
    tmom = sum((m["kg"] * np.asarray(m["centre"], float) for m in tracks), np.zeros(3))
    return {"running_rigging": {"rows": cats, "total_kg": round(kg, 1), "total_long_tons": round(kg / deck.LT_KG, 3),
                                "centre": [round(float(a), 3) for a in mom / max(kg, 1e-9)],
                                "ropes": [m for m in rows if "rope" in m]},
            "winches_and_cleats": {"rows": {k: {"kg": round(v["kg"], 1),
                                                "centre": [round(float(a), 3) for a in v["mom"] / max(v["kg"], 1e-9)]}
                                            for k, v in wrow.items()},
                                   "total_kg": round(wkg, 1), "total_long_tons": round(wkg / deck.LT_KG, 3),
                                   "centre": [round(float(a), 3) for a in wmom / max(wkg, 1e-9)]},
            "sheet_tracks": {"total_kg": round(tkg, 1), "total_long_tons": round(tkg / deck.LT_KG, 3),
                             "centre": [round(float(a), 3) for a in tmom / max(tkg, 1e-9)]}}

def lead_checks(rep):
    """Every loaded rope's rise onto its capstan's drum within the json's 'rise_deg', and every part's angle to the
    sheave it runs over within 'fleet_deg' (the blocks, the mainsheet's, the tails' lower blocks, the halyards' foot
    boxes) or 'fleet_aloft_deg' (the halyards' boxes aloft, whose leads move with the sail's head), less the json's
    'fleet_exempt'."""
    ck = RN["checks"]
    lo, hi = ck["rise_deg"]
    failing, rises, fleets = [], [], []
    for sname, r in rep["suits"].items():
        for g, (deg, _) in r["rise_deg"].items():
            rises.append(deg)
            if not lo <= deg <= hi:
                failing.append({"suit": sname, "rope": g, "rise_deg": deg})
        for g, v in r["fleet_deg"].items():
            if g in ck["fleet_exempt"]:
                continue
            lim = ck["fleet_aloft_deg"] if g.endswith("box aloft") else ck["fleet_deg"]
            fleets.append(max(v))
            if max(v) > lim:
                failing.append({"suit": sname, "sheave": g, "fleet_deg": max(v), "limit": lim})
    for k, h in rep["halyards"].items():
        fleets.append(h["foot_box_fleet_deg"])
        if h["foot_box_fleet_deg"] > ck["fleet_deg"]:
            failing.append({"halyard": k, "foot_box_fleet_deg": h["foot_box_fleet_deg"]})
    exempt = {g: {"fleet_deg": max(max(r["fleet_deg"][g]) for r in rep["suits"].values() if g in r["fleet_deg"]),
                  "why": why} for g, why in ck["fleet_exempt"].items() if g != "note"}
    return {"ok": not failing, "failing": failing, "rise_deg_range": [min(rises), max(rises)],
            "fleet_deg_max": max(fleets), "exempt": exempt}


# ------------------------------------------------------------------------------------------------ the ropes' own shape
KINK_EXEMPT = ("round the sheave", "round the lower block's sheave", "over the box's sheave",
               "over the foot box's sheave", "turns", "hitch", "coil")


def _rope_polyline(rec):
    """A record's centreline as one polyline, each vertex's arc length and the piece it belongs to."""
    P, names = [], []
    for pc in rec["pieces"]:
        Q = np.asarray(pc["path"], float)
        if P and len(Q) and np.linalg.norm(Q[0] - P[-1]) < 1e-7:
            Q = Q[1:]
        P.extend(Q)
        names.extend([pc["name"]] * len(Q))
    P = np.asarray(P, float)
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    return P, s, names


def _seg_seg(p1, q1, p2, q2):
    """The least distance between segments p1-q1 and p2-q2 (arrays of them, row by row)."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a = np.einsum("ij,ij->i", d1, d1)
    e = np.einsum("ij,ij->i", d2, d2)
    f = np.einsum("ij,ij->i", d2, r)
    c = np.einsum("ij,ij->i", d1, r)
    b = np.einsum("ij,ij->i", d1, d2)
    den = np.maximum(a * e - b * b, 1e-18)
    sc = np.clip((b * f - c * e) / den, 0.0, 1.0)
    tc = np.clip((b * sc + f) / np.maximum(e, 1e-18), 0.0, 1.0)
    sc = np.clip((b * tc - c) / np.maximum(a, 1e-18), 0.0, 1.0)
    return np.linalg.norm(r + sc[:, None] * d1 - tc[:, None] * d2, axis=1)


def self_clearance(recs, h=0.003, fail_mm=1.0):
    """Each rope against itself: its centreline resampled every `h`, every two of its segments more than four
    diameters apart along it (a turn on the drum against the next, the hitch's crossing turns, a coil's turns, a part
    of the mainsheet against another) at least a diameter apart, less `fail_mm`. Returns the rows, worst first."""
    from scipy.spatial import cKDTree
    rows = []
    for rec in recs:
        r = float(rec["r"])
        d = 2 * r
        P, s, names = _rope_polyline(rec)
        if len(P) < 2:
            continue
        n = max(2, int(math.ceil(s[-1] / h)) + 1)
        u = np.linspace(0.0, s[-1], n)
        Q = np.c_[[np.interp(u, s, P[:, k]) for k in range(3)]].T
        piece = [names[min(int(np.searchsorted(s, x, side="right")) - 1, len(names) - 1)] for x in u]
        tree = cKDTree(Q[:-1])
        pairs = tree.query_pairs(d + 2 * h, output_type="ndarray")
        worst = (math.inf, None)
        if len(pairs):
            pairs = pairs[np.abs(u[pairs[:, 0]] - u[pairs[:, 1]]) > 4 * d]
        if len(pairs):
            i, j = pairs[:, 0], pairs[:, 1]
            dist = _seg_seg(Q[i], Q[i + 1], Q[j], Q[j + 1])
            k = int(np.argmin(dist))
            worst = (float(dist[k]), (int(i[k]), int(j[k])))
        row = {"rope": rec["name"], "object": rec["object"], "samples": int(n)}
        if worst[1] is not None:
            i, j = worst[1]
            row.update(least_gap_mm=round((worst[0] - d) * 1000, 2), pieces=[piece[i], piece[j]],
                       at=[round(float(v), 3) for v in Q[i]])
        rows.append(row)
    tight = [r for r in rows if r.get("least_gap_mm") is not None and r["least_gap_mm"] < -fail_mm]
    have = [r for r in rows if r.get("least_gap_mm") is not None]
    return {"rows": sorted(have, key=lambda r: r["least_gap_mm"]), "step_m": h, "fail_overlap_mm": fail_mm,
            "apart_along_m": "4 diameters", "tight": tight, "ok": not tight}


def kinks(recs, over_d=1.5, fail_deg=60.0):
    """Each rope's turn at every vertex over +-`over_d` diameters along it (the angle between its direction coming in
    and going out there), outside the pieces that bend round something by design (a sheave, the drum's turns, the
    hitch, the coil); over `fail_deg` (a bend tighter than about three diameters' radius, or the rope doubling back on
    itself) is a kink. Returns the worst bend per rope."""
    rows = []
    for rec in recs:
        d = 2 * float(rec["r"])
        P, s, names = _rope_polyline(rec)
        if len(P) < 3:
            continue
        w = over_d * d
        worst = (0.0, None)
        for k in range(1, len(P) - 1):
            if names[k] in KINK_EXEMPT or s[k] - w < 0 or s[k] + w > s[-1]:
                continue
            a = np.array([np.interp(s[k] - w, s, P[:, c]) for c in range(3)])
            b = np.array([np.interp(s[k] + w, s, P[:, c]) for c in range(3)])
            u1, u2 = P[k] - a, b - P[k]
            n1, n2 = np.linalg.norm(u1), np.linalg.norm(u2)
            if n1 < 1e-9 or n2 < 1e-9:
                continue
            ang = math.degrees(math.acos(max(-1.0, min(1.0, float(u1 @ u2) / (n1 * n2)))))
            if ang > worst[0]:
                worst = (ang, k)
        row = {"rope": rec["name"], "object": rec["object"], "worst_deg": round(worst[0], 1)}
        if worst[1] is not None:
            row.update(piece=names[worst[1]], at=[round(float(v), 3) for v in P[worst[1]]])
        rows.append(row)
    bad = [r for r in rows if r["worst_deg"] > fail_deg]
    return {"rows": sorted(rows, key=lambda r: -r["worst_deg"]), "over_diameters": over_d, "fail_deg": fail_deg,
            "exempt_pieces": list(KINK_EXEMPT), "kinked": bad, "ok": not bad}


def shape_checks(rep):
    """self_clearance and kinks over every suit's ropes."""
    sc = {k: self_clearance(v) for k, v in rep["ropes"].items()}
    kk = {k: kinks(v) for k, v in rep["ropes"].items()}
    return {"self_clearance": sc, "kinks": kk,
            "ok": all(v["ok"] for v in sc.values()) and all(v["ok"] for v in kk.values())}


def summary(rep):
    """The report for build.json: the ropes' centrelines left out (their lengths kept)."""
    out = {k: v for k, v in rep.items() if k != "ropes"}
    out["rope_lengths_m"] = {s: {r["name"]: round(sum(seg_len(p["path"]) for p in r["pieces"]), 2) for r in rows}
                             for s, rows in rep["ropes"].items()}
    return out
