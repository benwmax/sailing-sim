"""The frigate's running rigging (docs/shipkit-6): the ropes that move the yards and work the sails, with their blocks,
bull's eyes, thimbles and the sheaves in the spars and the side, belayed to pins in the pin and fife rails or to kevels.

    from running import Running;  rn = Running(rig, sk, st, sv).gear();  rn.settle(C, places);  rn.objects()

Each square-rigged mast's lifts, halyards and topsail tyes, braces, sheets, the courses' tacks, clew garnets,
clewlines, buntlines, footropes and stirrups; the headsails' and staysails' sheets and the mizzen staysail's halyard;
the spanker's halyards, vangs, topping lifts and boom sheet; the spritsail yard's slings, lifts and braces. A line is
its stations (made fast, round a sheave, through a bull's eye, thimble or hole, belayed) and, between them, a straight
span or a drape (along a yard, over the cloth, slack). Running.solve() lays every line in each of the sails' states
(Set, Clewed, Furled; the yards square, the upper yards lowered when furled) and hangs the free blocks along their
ropes' pull; settle() gives the falls their pins and puts the bull's eyes and thimbles where their ropes stand clearest
(or loads an earlier placement, running_places_1797.json); check() and check_blocks() measure every rope and block
against the ship (World.soup: hull, spars, standing rigging, ratlines, sails), each other and the bull's eyes.
objects() makes the meshes and game_data() running.json. Sizes, leads and rails are running_1797.json's, each with its
source. Units as spars.py: metres in the ship frame (X forward, Y to starboard, Z up)."""
import json
import math
import os
import types

import numpy as np
from mathutils.bvhtree import BVHTree

import loft
from rigging import rope_r, nsides, tube, dedupe
from spars import Mesh, unit
import sails as SA

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)
STATES = SA.STATES


def to_axis(a):
    """the rotation taking +Z to the unit vector a (the least turn)"""
    a = unit(np.asarray(a, float))
    c = float(a[2])
    if c > 1.0 - 1e-9:
        return np.eye(3)
    if c < -1.0 + 1e-9:
        return np.diag([1.0, -1.0, -1.0])
    v = np.cross(EZ, a)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1.0 + c)


def rot(axis, deg):
    a = unit(np.asarray(axis, float))
    th = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)


class Pose:
    """Where each moving spar is: brace (deg about its axis, rig.json's sign) and hoist (0 lowered .. 1 hoisted). A
    state's pose: the yards square; hoisted, except the topsail, topgallant and royal yards lowered when furled."""

    def __init__(self, rig, state="Set", brace=None, hoist=None):
        self.rig, self.state = rig, state
        self.brace = dict(brace or {})
        self.hoist = dict(hoist or {})
        if state == "Furled":
            for n, m in rig.meta.items():
                if m["hoist_m"][0] != 0.0:
                    self.hoist.setdefault(n, 0.0)

    def frame(self, name):
        """(origin, R) of a moving spar in this pose (R's columns its axes in the ship), or the ship's"""
        if name in (None, "ship"):
            return np.zeros(3), np.eye(3)
        o, R = self.rig.parts_[name]["frame"]
        m = self.rig.meta[name]
        ax = np.asarray(m["axis"], float)
        h = self.hoist.get(name, 1.0)
        o = np.asarray(o, float) + ax * (1.0 - h) * m["hoist_m"][0]
        deg = self.brace.get(name, 0.0)
        if deg:
            tb = np.asarray(m.get("ease_m") or [[0.0, 0.0]], float)
            o = o + R[:, 0] * float(np.interp(abs(deg), tb[:, 0], tb[:, 1]))
            R = rot(ax, deg) @ R
        return o, np.asarray(R, float)

    def world(self, name, p):
        o, R = self.frame(name)
        return o + np.asarray(p, float) @ R.T


def mirrored(V, F):
    V = np.asarray(V, float)
    n = len(V)
    return np.concatenate([V, V * np.array([1.0, -1.0, 1.0])]), list(F) + [tuple(n + i for i in f[::-1]) for f in F]


def tris_of(F):
    T = []
    for f in F:
        for k in range(1, len(f) - 1):
            T.append((f[0], f[k], f[k + 1]))
    return np.array(T, dtype=np.int64).reshape(-1, 3)


class World:
    """The ship's meshes as triangles in the ship's frame for a pose and a sails' state, labelled by part, and a BVH of
    them for clearance queries (everything the running rigging must stand clear of)."""

    def __init__(self, rig, sk, st, sv):
        self.rig, self.sk, self.st, self.sv = rig, sk, st, sv
        self.static = []                                       # (label, V, T) that never move
        for name, (V, F, M, side) in sk.parts().items():
            if name.startswith("Lid_"):
                continue
            if side == "stbd":
                V, F = mirrored(V, F)
            self.static.append((name, np.asarray(V, float), tris_of(F)))
        self.moving = []                                       # (label, frame name, V local, T)
        for name, (V, F, M, frame) in rig.parts().items():
            if frame is None:
                self.static.append((name, np.asarray(V, float), tris_of(F)))
            else:                                              # built in the spar's own frame
                self.moving.append((name, name, np.asarray(V, float), tris_of(F)))
        for name, (V, F, M, _) in st.parts().items():
            self.static.append((name, np.asarray(V, float), tris_of(F)))
        self.sails = {}                                        # state -> [(label, frame name, V local, T)]
        for name, (V, F, M, U, frame, parent, key, state) in sv.objects().items():
            T = tris_of(F)
            V = np.asarray(V, float)
            if frame is not None:                              # into the parent's own (rest) frame
                o, R = frame
                V = o + V @ np.asarray(R, float).T
                po, PR = rig.parts_[parent]["frame"]
                V = (V - np.asarray(po, float)) @ np.asarray(PR, float)
            for s in (STATES if state == "Head" else (state,)):
                self.sails.setdefault(s, []).append((name, parent if frame is not None else None, V, T))

    def soup(self, pose, state=None, sails=True, extra=()):
        """[(label, V world, T)] for the pose (and the state's sails)"""
        out = list(self.static)
        for label, fr, V, T in self.moving:
            o, R = pose.frame(fr)
            out.append((label, o + V @ R.T, T))
        if sails:
            for label, fr, V, T in self.sails.get(state or pose.state, []):
                if fr is None:
                    out.append((label, V, T))
                else:
                    o, R = pose.frame(fr)
                    out.append((label, o + V @ R.T, T))
        out += list(extra)
        return out


class Clearance:
    """A BVH over labelled triangles: nearest distances from points and what is nearest"""

    def __init__(self, soup):
        Vs, Ts, lab, n0 = [], [], [], 0
        self.labels = []
        for k, (label, V, T) in enumerate(soup):
            if not len(T):
                continue
            Vs.append(np.asarray(V, float))
            Ts.append(np.asarray(T) + n0)
            lab.append(np.full(len(T), len(self.labels)))
            self.labels.append(label)
            n0 += len(V)
        self.V = np.concatenate(Vs)
        self.T = np.concatenate(Ts)
        self.lab = np.concatenate(lab)
        self.bvh = BVHTree.FromPolygons(self.V.tolist(), self.T.tolist(), all_triangles=True)

    def local(self, lo, hi, drop=(), only=None):
        """the triangles whose bounds meet the box lo..hi, less those labelled in drop (or only those labelled in only),
        as a Clearance of their own (for a line led through what drop names: a brace's fall in between two shrouds,
        through their ladder's sheet; or one that may press into what only names: a clewline into the cloth)"""
        if not hasattr(self, "_tlo"):
            W = self.V[self.T]
            self._tlo, self._thi = W.min(axis=1), W.max(axis=1)
        keep = np.array([(lb not in drop) and (only is None or lb in only) for lb in self.labels])
        sel = keep[self.lab] & np.all(self._tlo <= hi, axis=1) & np.all(self._thi >= lo, axis=1)
        sub = Clearance.__new__(Clearance)
        sub.labels = self.labels
        T = self.T[sel]
        if not len(T):                                          # nothing near: one far triangle stands in
            sub.V = np.array([[0.0, 0.0, -1e4], [1.0, 0.0, -1e4], [0.0, 1.0, -1e4]])
            sub.T = np.array([[0, 1, 2]])
            sub.lab = np.array([0])
        else:
            used, inv = np.unique(T, return_inverse=True)
            sub.V = self.V[used]
            sub.T = inv.reshape(T.shape)
            sub.lab = self.lab[sel]
        sub.bvh = BVHTree.FromPolygons(sub.V.tolist(), sub.T.tolist(), all_triangles=True)
        return sub

    def nearest(self, P, reach=10.0):
        """distances (inf beyond reach) and labels of the nearest triangle for each point"""
        P = np.atleast_2d(P)
        d = np.full(len(P), np.inf)
        who = np.full(len(P), -1)
        for i, p in enumerate(P):
            loc, nrm, idx, dist = self.bvh.find_nearest(p, reach)
            if idx is not None:
                d[i], who[i] = dist, self.lab[idx]
        return d, who

    def label(self, k):
        return self.labels[k] if k >= 0 else None


# ---- parts: blocks, pins, coils ---------------------------------------------------------------------------------------
BLOCK, SHEAVE, PINWOOD, RAIL = "Block", "Sheave", "Pin", "Rail"
STROP, RUN, IRON = "Tarred", "Hemp", "Iron"


def superellipse(n, a, b, p=2.6):
    """n points round a superellipse of semi-axes a, b (exponent p: squarer than an ellipse)"""
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    return np.stack([a * np.sign(c) * np.abs(c) ** (2 / p), b * np.sign(s) * np.abs(s) ** (2 / p)], 1)


def block_dims(L, sheaves):
    """a block's shell (m) from its length L (m): width in the sheave plane, thickness along the pin, sheave radius to
    the rope's bed, and the sheaves' offsets along the pin"""
    w = 0.78 * L
    t = 0.42 * L + 0.30 * L * (sheaves - 1)
    rs = 0.27 * L
    cheek = 0.11 * L
    pitch = (t - 2 * cheek) / sheaves
    offs = [(k - (sheaves - 1) / 2) * pitch for k in range(sheaves)]
    return w, t, rs, offs


def block_mesh(L, sheaves, r_strop, eye=True):
    """A block in its own frame (origin the sheave's centre, X across the shell, Y along the pin, Z up to the crown):
    the shell (squared oval, rounded cheeks), the pin's iron ends on both cheeks, the rope strop in its score round the
    shell and its eye over the crown (eye False: none, the block lashed by its strop round a spar). Returns the Mesh and
    the eye's top (local; without an eye, the seizing's)."""
    w, t, rs, _ = block_dims(L, sheaves)
    M = Mesh()
    n, m = 20, 7
    out2 = superellipse(n, w / 2, L / 2)[::-1]                   # in X (across), Z (along): clockwise in (X, Z), so
    #                                                              counter-clockwise seen from +Y, the loft's far end
    rings = []
    for j, ph in enumerate(np.linspace(-math.pi / 2, math.pi / 2, m)):
        k = math.cos(ph) ** 0.55                                # the cheeks round off to the edges
        y = t / 2 * math.sin(ph)
        P = np.stack([out2[:, 0] * (0.55 + 0.45 * k), np.full(n, y), out2[:, 1] * (0.75 + 0.25 * k)], 1)
        rings.append(P)
    loft_solid_(M, rings, BLOCK)
    # the pin's ends, a little proud of each cheek
    for sg in (1.0, -1.0):
        th = np.linspace(0, 2 * math.pi, 8, endpoint=False)
        r_p = 0.075 * L
        ring0 = np.stack([r_p * np.cos(th), np.full(8, sg * (t / 2 - 0.01 * L)), -r_p * np.sin(th)], 1)
        ring1 = ring0.copy()
        ring1[:, 1] = sg * (t / 2 + 0.012 * L)
        loft_solid_(M, [ring0, ring1] if sg > 0 else [ring1, ring0], IRON)
    # the strop: in a score round the shell's edge in the sheave plane, closing over the crown into an eye
    sc = superellipse(28, w / 2 + r_strop * 0.35, L / 2 + r_strop * 0.35)
    P = np.stack([sc[:, 0], np.zeros(len(sc)), sc[:, 1]], 1)
    tube(M, P, r_strop, STROP, n=6, closed=True)
    r_eye = max(1.6 * r_strop, 0.12 * L)
    ce = np.array([0.0, 0.0, L / 2 + 2 * r_strop + r_eye])
    th = np.linspace(0, 2 * math.pi, 14, endpoint=False)
    if eye:
        tube(M, ce[None] + r_eye * np.stack([np.zeros(14), np.cos(th), np.sin(th)], 1), r_strop * 0.85, STROP, n=6,
             closed=True)
    # the seizing between the shell and the eye
    seize = np.array([[0.0, 0.0, L / 2 + 0.3 * r_strop], [0.0, 0.0, L / 2 + 2.2 * r_strop]])
    tube(M, seize, 1.6 * r_strop, STROP, n=6)
    return M, (ce + np.array([0.0, 0.0, r_eye])) if eye else seize[1]


def loft_solid_(mesh, rings, mat):
    from spars import loft_solid
    loft_solid(mesh, rings, mat)


def pin_mesh(h_handle, d, h_shank):
    """A belaying pin, its axis along Z, the rail's top at Z = 0: the turned handle above, the collar, the shank below"""
    M = Mesh()
    prof = [(h_handle + 0.0, 0.0), (h_handle, 0.30 * d), (h_handle - 0.04 * h_handle, 0.42 * d),
            (0.62 * h_handle, 0.30 * d), (0.18 * h_handle, 0.38 * d), (0.08 * h_handle, 0.62 * d),
            (0.0, 0.62 * d), (-0.02, 0.45 * d), (-h_shank, 0.36 * d), (-h_shank - 0.01, 0.0)]
    th = np.linspace(0, 2 * math.pi, 10, endpoint=False)
    rings = [np.stack([r * np.cos(th), r * np.sin(th), np.full(10, z)], 1) for z, r in prof[1:-1]]
    V = np.concatenate([[[0.0, 0.0, prof[0][0]]]] + rings + [[[0.0, 0.0, prof[-1][0]]]])
    F = []
    last = 1 + 10 * len(rings)                                  # the shank's end; the handle's top is vertex 0
    for i in range(10):
        i1 = (i + 1) % 10
        F.append((0, 1 + i, 1 + i1))
        F.append((last, last - 10 + i1, last - 10 + i))
    for j in range(len(rings) - 1):
        a, b = 1 + j * 10, 1 + (j + 1) * 10
        for i in range(10):
            i1 = (i + 1) % 10
            F.append((a + i, b + i, b + i1, a + i1))
    M.add(V, F, PINWOOD)
    return M


# ---- sheaves and tangents ----------------------------------------------------------------------------------------------
def tangent_points(P, c, n, rho):
    """the two points where lines from P touch the circle (centre c, axis n, radius rho), each with its sense: +1 if the
    rope from P to the point runs counter-clockwise about n there"""
    e1 = P - c
    e1 = e1 - (e1 @ n) * n
    d = np.linalg.norm(e1)
    if d <= rho * 1.0001:                                       # inside: touch where it points
        e = unit(e1) if d > 1e-9 else unit(np.cross(n, EX if abs(n[0]) < 0.9 else EY))
        return [(c + rho * e, 1), (c + rho * e, -1)]
    e = e1 / d
    f = np.cross(n, e)
    beta = math.acos(rho / d)
    out = []
    for sg in (1.0, -1.0):
        T = c + rho * (math.cos(beta) * e + sg * math.sin(beta) * f)
        dvec = T - P
        sense = 1 if np.cross(T - c, dvec) @ n > 0 else -1
        out.append((T, sense))
    return out


def wrap(P_in, P_out, c, n, rho, step_deg=15.0, sense=None):
    """the rope round a sheave (centre c, axis n, the rope's centre at radius rho) from P_in to P_out, the shorter way
    round (or round in the given sense about n): its points from the touch point on P_in's side to the one on P_out's
    side, and the whole length"""
    pts, L, _ = wrap_s(P_in, P_out, c, n, rho, step_deg, sense)
    return pts, L


def wrap_s(P_in, P_out, c, n, rho, step_deg=15.0, sense=None):
    """wrap, and the sense it went round in"""
    tin = tangent_points(P_in, c, n, rho)
    tout = tangent_points(P_out, c, n, rho)
    e1 = unit(np.cross(n, EX if abs(n[0]) < 0.9 else EY))
    e2 = np.cross(n, e1)

    def ang(T):
        v = T - c
        return math.atan2(v @ e2, v @ e1)
    best = None
    for sense in ((1, -1) if sense is None else (sense,)):
        Ti = next(T for T, s in tin if s == sense)
        # leaving, the rope runs on in the same sense: from To toward P_out counter-clockwise if sense is +1
        To = next((T for T, _ in tout if np.cross(T - c, P_out - T) @ n * sense > 0), tout[0][0])
        a0 = ang(Ti)
        da = ((ang(To) - a0) * sense) % (2 * math.pi)
        L = np.linalg.norm(Ti - P_in) + rho * da + np.linalg.norm(P_out - To)
        if best is None or L < best[0]:
            best = (L, a0, da, sense)
    L, a0, da, sense = best
    k = max(1, int(math.ceil(math.degrees(da) / step_deg)))
    th = a0 + sense * da * np.arange(k + 1) / k
    return c[None] + rho * (np.cos(th)[:, None] * e1[None] + np.sin(th)[:, None] * e2[None]), L, sense


# ---- blocks and lines --------------------------------------------------------------------------------------------------
class Block:
    """A block: its sheaves, length (m) and strop's rope, and how it hangs. Free (fixed None): its eye hangs from attach
    (frame, local point) on a pendant of length pendant (m), and it swings to lie along the pull of its ropes. Fixed:
    (frame, local centre, local axis a from the crown to the tail, local pin axis n), seized where it is."""

    def __init__(self, bid, sheaves, L, r_strop, attach=None, pendant=0.0, fixed=None, hint=None, mount=None,
                 group=None):
        self.bid, self.sheaves, self.L, self.r_strop = bid, sheaves, L, r_strop
        self.attach, self.pendant, self.fixed, self.hint, self.mount, self.group = \
            attach, pendant, fixed, hint, mount, group
        self.w, self.t, self.rs, self.offs = block_dims(L, sheaves)
        r_eye = max(1.6 * r_strop, 0.12 * L)
        self.eye_drop = L / 2 + 2 * r_strop + 2 * r_eye           # from the eye's top to the sheave's centre
        self.pose = {}                                          # state -> (C, a, n) in the ship


class Line:
    """A rope: its name, group (an object per group and state), size (circumference, in), and for each state its
    stations from the standing part to the fall: {"k": "end", "at": (frame, p)} made fast there (or "b": a block id,
    its tail: a becket), {"k": "sheave", "b": id, "i": sheave}, {"k": "thru", "at": (frame, p), "r": bend radius}
    through a fairlead or a sheave in a spar or the side, {"k": "pin", "pin": id} belayed; and per span between them
    None (straight), ("slack", sag share of the span) or ("drape", fn) where fn(A, B) returns the points between."""

    def __init__(self, name, group, circ_in, note=""):
        self.name, self.group, self.circ, self.note = name, group, circ_in, note
        self.r = rope_r(circ_in)
        self.st, self.sp = {}, {}
        self.path = {}                                          # state -> points (m, ship)
        self.soft = {}                                          # state -> {label: how far it may press into it, m}

    def set(self, state, stations, spans=None):
        self.st[state] = stations
        self.sp[state] = spans or [None] * (len(stations) - 1)
        return self


class Pins:
    """Belaying places: pins in rails (zones), each a point (the rail's top, ship frame) and its axis (up the pin)"""

    def __init__(self):
        self.pins = {}                                          # id -> {"p", "axis", "zone", "h", "d", "line"}
        self.zones = {}                                         # zone -> [ids in order along the rail]

    def add(self, zone, pid, p, axis=EZ, h=0.25, d=0.035):
        self.pins[pid] = {"p": np.asarray(p, float), "axis": unit(np.asarray(axis, float)), "zone": zone, "h": h,
                          "d": d, "line": None}
        self.zones.setdefault(zone, []).append(pid)
        return pid

    def belay_point(self, pid, came_from, r):
        """where a line from came_from meets the pin: round its waist, on the side it comes from"""
        pn = self.pins[pid]
        c = pn["p"] + pn["axis"] * 0.45 * pn["h"]
        d = came_from - c
        d = d - (d @ pn["axis"]) * pn["axis"]
        dn = np.linalg.norm(d)
        e = d / dn if dn > 1e-6 else EX
        return c + e * (0.4 * pn["d"] + r)


class Solver:
    """Hangs every free block along the pull of its ropes and lays every line's path, for one pose"""

    def __init__(self, pose, blocks, lines, pins, gravity=0.12):
        self.pose, self.blocks, self.lines, self.pins = pose, blocks, lines, pins
        self.state = pose.state
        self.gravity = gravity

    def at(self, ref):
        frame, p = ref
        return self.pose.world(frame, p)

    def vec(self, ref):
        frame, v = ref
        return self.pose.frame(frame)[1] @ np.asarray(v, float)

    def centre(self, st, line=None, came=None):
        """a station's point for the solver: an end's or fairlead's point, a sheave's centre, a pin's waist"""
        k = st["k"]
        if k in ("end", "thru", "kevel"):
            if "b" in st:
                b = self.blocks[st["b"]]
                C, a, n = b.pose[self.state]
                if st.get("eye"):                               # spliced into the block's strop over its crown
                    return C - a * b.eye_drop
                return C + a * (b.L / 2)
            return self.at(st["at"])
        if k == "sheave":
            b = self.blocks[st["b"]]
            C, a, n = b.pose[self.state]
            return C + n * b.offs[st["i"]]
        if k == "pin":
            if st.get("pin") is None:                           # not yet allocated: the middle of its zones
                if "_prov" not in st:
                    side = "s" if st.get("side", 1.0) > 0 else "p"
                    P = [pn["p"] for pn in self.pins.pins.values() if pn["zone"] in st["zones"] and
                         pn.get("side", side) in (side, "c")]
                    st["_prov"] = np.mean(P, axis=0) if P else np.zeros(3)
                return st["_prov"]
            pn = self.pins.pins[st["pin"]]
            return pn["p"] + pn["axis"] * 0.45 * pn["h"]
        raise ValueError(k)

    def solve(self, iters=40):
        S = self.state
        passes = {bid: [] for bid in self.blocks}               # bid -> [(line, j)]
        for ln in self.lines:
            for j, st in enumerate(ln.st.get(S, [])):
                if "b" in st:
                    passes[st["b"]].append((ln, j))
        def pend(b):
            return getattr(b, "pendant_by", {}).get(S, b.pendant)
        for b in self.blocks.values():
            fx = getattr(b, "fixed_by", {}).get(S, b.fixed)
            if fx is not None:
                fr, c, a, n = fx
                a = unit(self.vec((fr, a)))
                n = self.vec((fr, n))
                b.pose[S] = (self.at((fr, c)), a, unit(n - (n @ a) * a))
            else:
                A = self.at(getattr(b, "attach_by", {}).get(S, b.attach))
                b.pose[S] = (A - EZ * (pend(b) + b.eye_drop), -EZ, EX)
        free = [b for b in self.blocks.values() if b.fixed is None and S not in getattr(b, "fixed_by", {}) and
                passes[b.bid]]
        for it in range(iters):
            moved = 0.0
            for b in free:
                C, a, n = b.pose[S]
                A = self.at(getattr(b, "attach_by", {}).get(S, b.attach))
                pull = np.zeros(3)
                for ln, j in passes[b.bid]:
                    sts = ln.st[S]
                    if sts[j]["k"] == "sheave":
                        for jj in (j - 1, j + 1):
                            pull += unit(self.centre(sts[jj]) - C)
                    else:                                       # a becket: the standing part pulls from the tail
                        pull += unit(self.centre(sts[j + 1] if j == 0 else sts[j - 1]) - C)
                pull = pull - EZ * self.gravity * max(1, len(passes[b.bid]))
                a_new = unit(pull) if np.linalg.norm(pull) > 1e-6 else -EZ
                C_new = A + a_new * (pend(b) + b.eye_drop)
                moved = max(moved, float(np.linalg.norm(C_new - C)))
                b.pose[S] = (C_new, a_new, n)
            if moved < 1e-5:
                break
        # each block's pin square to the plane its ropes turn in. A block whose ropes all run to and fro to one other
        # block (a tackle's: their legs nearly parallel, so the plane is ill-defined) takes the other's pin, so the two
        # are parallel and the tackle has no turn in it (both, if neither turns its rope: square to the tackle)
        tk = self.tackles()
        weak = {}
        for b in self.blocks.values():
            if b.fixed is not None or S in getattr(b, "fixed_by", {}):
                continue
            C, a, _ = b.pose[S]
            nn = np.zeros(3)
            k = 0
            for ln, j in passes[b.bid]:
                sts = ln.st[S]
                if sts[j]["k"] == "sheave":
                    u0 = unit(self.centre(sts[j - 1]) - C)
                    u1 = unit(self.centre(sts[j + 1]) - C)
                    c = np.cross(u0, u1)
                    if c @ nn < 0:
                        c = -c
                    nn += c
                    k += 1
            if b.bid in tk and np.linalg.norm(nn - (nn @ a) * a) < 0.05 * max(k, 1):
                weak[b.bid] = True
            if np.linalg.norm(nn - (nn @ a) * a) < 1e-3:
                h = self.vec(b.hint) if b.hint is not None else np.cross(a, EZ if abs(a[2]) < 0.9 else EX)
                nn = h
            nn = unit(nn - (nn @ a) * a)
            b.pose[S] = (C, a, nn)
        for bid in weak:
            b, o = self.blocks[bid], self.blocks[tk[bid]]
            C, a, _ = b.pose[S]
            if tk[bid] in weak:                                 # neither turns its rope: square to the tackle, level
                u = unit(o.pose[S][0] - C)
                h = self.vec(b.hint) if b.hint is not None else np.cross(u, EZ)
                if np.linalg.norm(h - (h @ u) * u) < 0.2:
                    h = np.cross(u, EX)
                if bid > tk[bid]:                               # the pair's one direction, whichever is first
                    h = o.pose[S][2]
            else:
                h = o.pose[S][2]
            b.pose[S] = (C, a, unit(h - (h @ a) * a))
        self._tk, self._weak = tk, weak
        for ln in self.lines:
            if S in ln.st:
                ln.path[S] = self.lay(ln)

    def tackles(self):
        """the blocks rove together as a tackle (a rope going to and fro between the same two blocks at least twice):
        each one's partner, by id"""
        cnt = {}
        for ln in self.lines:
            sts = ln.st.get(self.state, [])
            for x, y in zip(sts[:-1], sts[1:]):
                if x["k"] == "sheave" and y["k"] == "sheave" and x["b"] != y["b"]:
                    k = tuple(sorted((x["b"], y["b"])))
                    cnt[k] = cnt.get(k, 0) + 1
        out = {}
        for (p, q), c in cnt.items():
            if c >= 2:
                out[p], out[q] = q, p
        return out

    def lay(self, ln):
        """the line's centre as points: straight between stations, round each sheave from touch point to touch point.
        Round a tackle's sheaves the rope goes the same way about their (parallel) pins, as a belt round two pulleys:
        the way it turns at the one that bends it most (the fall's lead off to its pin)"""
        S = self.state
        sts, sps = ln.st[S], ln.sp[S]
        n = len(sts)
        cen = [self.centre(st) for st in sts]
        tk = getattr(self, "_tk", {})

        def pair_of(j):
            st = sts[j]
            if st["k"] != "sheave" or st["b"] not in tk:
                return None
            o = tk[st["b"]]
            if any(0 <= jj < n and sts[jj]["k"] == "sheave" and sts[jj]["b"] == o for jj in (j - 1, j + 1)):
                return tuple(sorted((st["b"], o)))
            return None
        belt, bend = {}, {}
        for j in range(1, n - 1):                               # the sheave that bends the rope most sets the way round
            pr = pair_of(j)
            if pr is not None:
                c_ = float(np.linalg.norm(np.cross(unit(cen[j - 1] - cen[j]), unit(cen[j + 1] - cen[j]))))
                if pr not in bend or c_ > bend[pr][0] + 1e-9:
                    bend[pr] = (c_, j)
        for pr, (c_, j) in bend.items():
            b = self.blocks[sts[j]["b"]]
            _, _, belt[pr] = wrap_s(cen[j - 1], cen[j + 1], cen[j], b.pose[S][2], b.rs + ln.r)
        # each station's contact points (in, out): ends and fairleads a single point, sheaves their touch points
        cont = [None] * n
        for rnd in range(3):
            for j, st in enumerate(sts):
                if st["k"] == "sheave" or (st["k"] == "thru" and st.get("r", 0.0) > 0.0):
                    pin = cont[j - 1][1][-1] if (rnd and cont[j - 1] is not None) else cen[j - 1]
                    pout = cont[j + 1][0][0] if (rnd and cont[j + 1] is not None) else cen[j + 1]
                    if st["k"] == "sheave":
                        b = self.blocks[st["b"]]
                        C, a, nb = b.pose[S]
                        pts, _ = wrap(pin, pout, cen[j], nb, b.rs + ln.r, sense=belt.get(pair_of(j)))
                    else:
                        u0, u1 = unit(pin - cen[j]), unit(pout - cen[j])
                        nb = np.cross(u0, u1)
                        if np.linalg.norm(nb) < 1e-6:
                            pts = cen[j][None]
                        else:
                            nb = unit(nb)
                            # the sheave's centre: inside the bend, so the rope's centre passes at r from it
                            bis = unit(u0 + u1)
                            c = cen[j] + bis * st["r"]
                            pts, _ = wrap(pin, pout, c, nb, st["r"])
                    cont[j] = (pts[:1], pts)
                elif st["k"] == "pin" and st.get("pin") is not None:
                    came = cont[j - 1][1][-1] if (rnd and cont[j - 1] is not None) else cen[j - 1]
                    p = self.pins.belay_point(st["pin"], came, ln.r)
                    cont[j] = (p[None], p[None])
                else:
                    cont[j] = (cen[j][None], cen[j][None])
        out = [cont[0][1]]
        for j in range(1, n):
            A, B = out[-1][-1], cont[j][1][0]
            sp = sps[j - 1]
            if sp is not None and sp[0] == "slack":
                span = float(np.linalg.norm(B - A))
                P = SA.catenary(A, B, span * (1.0 + sp[1]), 24)
                out.append(P[1:-1])
            elif sp is not None and sp[0] == "drape":
                out.append(sp[1](A, B)[1:-1])
            out.append(cont[j][1])
        return dedupe(np.concatenate(out))


# ---- the deck, its sides and the rails the pins stand in -----------------------------------------------------------------
class Deck:
    """The spar deck's top by x (flat across), the bulwark's inner face and the hull's outside at any height, the
    waist's stanchions, the spar deck's ports (a pin rail runs only between them), the channels, in metres."""

    def __init__(self, sk):
        import skin as SKM
        self.sk = sk
        pr = sk.pr
        P, _, _ = sk.row_points("w_Pd")
        o = np.argsort(P[:, 0])
        self.xd, self.yd, self.zd = P[o, 0], P[o, 1], P[o, 2]
        self.e0, self.e1, self.fc = (self.xm(v) for v in (pr.x_e0, pr.x_e1, pr.x_fc))
        _, spar = sk.port_rects()
        self.ports = [(self.xm(a), self.xm(b)) for a, b, _, _ in spar]
        self.channels = {k: (self.xm(a), self.xm(b)) for k, (a, b, za, zf) in pr.channels.items()}
        self.BUL, self.OUT = SKM.BUL, SKM.OUT
        # the waist's stanchions (skin.waist_rail's places)
        ws = sk.sp["waist_rail"]
        xa, xf = pr.x_e1, pr.x_fc
        n = max(2, int(round((xf - xa) / (ws["stanchion_spacing_ft"] * sk.L.ppf))) + 1)
        end = 0.5 * ws["stanchion_in"] * IN / sk.m.sx + 1.0
        self.stanchions = [self.xm(x) for x in np.linspace(xa + end, xf - end, n)]
        self.stanchion_half = 0.5 * ws["stanchion_in"] * IN

    def xm(self, xpx):
        return float((xpx - self.sk.L.mid_px) * self.sk.m.sx)

    def xpx(self, x):
        return float(x) / self.sk.m.sx + self.sk.L.mid_px

    def z(self, x):
        """the deck's top at x"""
        return float(np.interp(x, self.xd, self.zd))

    def surf(self, x, z, kind):
        """the point (starboard) and its normal on the bulwark's inner face (kind BUL) or the skin (OUT) at x, height z"""
        X = np.array([self.xpx(x)])
        zp = z / FT * self.sk.L.ppf_y
        for _ in range(3):
            P, N = self.sk.surf(X, np.array([zp]), True, 0, kind)
            zp += (z - P[0][2]) / FT * self.sk.L.ppf_y
        return P[0], N[0]

    def inboard(self, x, z, kind=None):
        """the face's point and the horizontal unit vector square to it, pointing inboard (starboard side)"""
        P, N = self.surf(x, z, self.BUL if kind is None else kind)
        n = np.array([N[0], N[1], 0.0])
        n = unit(n)
        if n[1] > 0:
            n = -n
        return P, n

    def in_port(self, x, margin=0.0):
        return any(a - margin < x < b + margin for a, b in self.ports)

    def free_runs(self, xa, xb, margin):
        """the stretches of [xa, xb] clear of the spar ports by margin"""
        cuts = sorted((a - margin, b + margin) for a, b in self.ports if b + margin > xa and a - margin < xb)
        out, x = [], xa
        for a, b in cuts:
            if a > x:
                out.append((x, a))
            x = max(x, b)
        if x < xb:
            out.append((x, xb))
        return out

    def stanchion_face(self, x, z):
        """the inboard face of a waist stanchion at height z (the stanchion's centre is midway between the skin and the
        bulwark's inner face, as skin.waist_rail stands it)"""
        po, _ = self.surf(x, z, self.OUT)
        pi, _ = self.surf(x, z, self.BUL)
        c = 0.5 * (po + pi)
        return np.array([x, c[1] - self.stanchion_half, z])


def box_rail(M, P, inward, w, d, mat):
    """a rail along the polyline P (its top outer edge, starboard), w wide inboard along inward (unit vectors per point,
    horizontal) and d deep: a swept rectangle"""
    rings = []
    for p, n in zip(P, inward):
        rings.append(np.array([p, p + n * w, p + n * w - EZ * d, p - EZ * d]))
    from spars import loft_solid
    loft_solid(M, rings, mat)


def post(M, base, top, half, mat, cap=0.0):
    """a square post from base to top (vertical), half its side; cap: a rounded knob above the top"""
    sq = np.array([[-half, -half], [half, -half], [half, half], [-half, half]])
    rings = [np.c_[base[0] + sq[:, 0], base[1] + sq[:, 1], np.full(4, base[2])],
             np.c_[top[0] + sq[:, 0], top[1] + sq[:, 1], np.full(4, top[2])]]
    from spars import loft_solid
    loft_solid(M, rings, mat)
    if cap > 0:
        th = np.linspace(0, 2 * math.pi, 8, endpoint=False)
        prof = [(0.0, 0.8 * half), (0.35 * cap, 0.9 * half), (0.75 * cap, 0.7 * half), (cap, 0.0)]
        R = [np.c_[top[0] + r * np.cos(th), top[1] + r * np.sin(th), np.full(8, top[2] + h)] for h, r in prof]
        loft_solid(M, R, mat)


class Rails:
    """The pin rails: along the bulwark's inner face on the quarterdeck and forecastle (between the spar deck ports),
    along the waist's stanchions over the gangways, and a fife rail round each mast's foot; the pins in them (every
    spacing along each rail's middle, numbered from aft forward, starboard and port). Pin ids: <rail>:<k>."""

    def __init__(self, deck, rig, cfg):
        self.deck, self.rig, self.cfg = deck, rig, cfg
        self.mesh = Mesh()                                      # the rails and posts (both sides)
        self.pins = Pins()
        self.rails = {}                                         # rail -> {"kind", "pins": [ids], "side"}

    def build(self):
        pc = self.cfg["pins"]
        d = self.deck
        w, t = (v * IN for v in pc["rail_in"])
        over = pc["rail_over_deck_ft"] * FT
        sp = pc["spacing_in"] * IN
        # along the bulwark: the quarterdeck from the taffrail's corner to the break, the forecastle from its break to
        # the bow's turn; between the ports
        runs = [("qd", -29.0, d.e0 - 0.08), ("fc", d.fc + 0.08, 22.6)]
        for name, xa, xb in runs:
            for k, (a, b) in enumerate(d.free_runs(xa, xb, 0.12)):
                if b - a < 0.6:
                    continue
                self.bulwark_rail(f"{name}{k}", a, b, w, t, over, sp)
        # over the gangways: on knees off the waist's stanchions (inboard of the rail cap's overhang), from the entry to
        # the forecastle
        self.gangway_rail("gw", d.e1 + 0.15, d.fc - 0.15, w, t, over, sp, pc.get("gangway_inset_in", 0.0) * IN)
        # in the tops: pins through the top's after rail (the masts in pins.top)
        for mast in pc.get("top", []):
            self.top_pins(mast, pc["fife_spacing_in"] * IN)
        # the fife rails
        fo = pc["fife_over_deck_ft"] * FT
        fs = pc["fife_spacing_in"] * IN
        for mast, v in self.cfg["fife"].items():
            if mast != "note":
                self.fife_rail(mast, *v, w, t, fo, fs)
        return self

    def _pins_along(self, rail, P, inward, w, sp, side):
        """pins every sp along the rail's middle line (P its outer top edge)"""
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        n = int((s[-1] - 0.5 * sp) // sp)
        if n < 1:
            return []
        s0 = 0.5 * (s[-1] - (n - 1) * sp)
        ids = []
        for k in range(n):
            sk_ = s0 + k * sp
            p = np.array([np.interp(sk_, s, P[:, i]) for i in range(3)])
            nn = unit(np.array([np.interp(sk_, s, inward[:, i]) for i in range(3)]))
            c = p + nn * (0.5 * w)
            for sg, tag in ((1.0, "s"), (-1.0, "p")):
                if side is not None and tag != side:
                    continue
                cc = c * np.array([1.0, sg, 1.0])
                ids.append(self.pins.add(rail + tag, f"{rail}{tag}:{k}", cc, EZ, h=self.cfg["pins"]["handle_in"] * IN,
                                         d=self.cfg["pins"]["diam_in"] * IN))
                self.pins.pins[ids[-1]]["out"] = unit((nn - (nn @ EZ) * EZ) * np.array([1.0, sg, 1.0]))
        return ids

    def bulwark_rail(self, name, a, b, w, t, over, sp):
        xs = np.linspace(a, b, max(2, int(math.ceil((b - a) / 0.25)) + 1))
        P, Nn = [], []
        for x in xs:
            z = self.deck.z(x) + over
            p, n = self.deck.inboard(x, z - 0.5 * t)
            P.append(np.array([p[0], p[1], z]))
            Nn.append(n)
        P, Nn = np.array(P), np.array(Nn)
        for sg in (1.0, -1.0):
            f = np.array([1.0, sg, 1.0])
            Q = P * f
            M = Mesh()
            box_rail(M, Q, Nn * f, w, t, RAIL)
            V, F, Mm = M.arrays()
            if sg < 0:
                F = [f_[::-1] for f_ in F]
            self.mesh.add(V, F, RAIL)
        ids = self._pins_along(name, P, Nn, w, sp, None)
        self.rails[name] = {"kind": "bulwark", "x": (a, b), "pins": ids}

    def gangway_rail(self, name, a, b, w, t, over, sp, inset=0.0):
        xs = np.linspace(a, b, max(2, int(math.ceil((b - a) / 0.25)) + 1))
        P0 = []
        for x in xs:
            z = self.deck.z(x) + over
            P0.append(self.deck.stanchion_face(x, z))
        P0 = np.array(P0)
        Nn = np.tile(np.array([0.0, -1.0, 0.0]), (len(P0), 1))
        P = P0 + Nn * inset
        for sg in (1.0, -1.0):
            f = np.array([1.0, sg, 1.0])
            M = Mesh()
            box_rail(M, P * f, Nn * f, w, t, RAIL)
            if inset > 0.0:                                     # its knees: one every 1.2 m, off the stanchions
                xk = np.linspace(a + 0.1, b - 0.1, max(2, int(math.ceil((b - a - 0.2) / 1.2)) + 1))
                for x in xk:
                    p0 = np.array([np.interp(x, P0[:, 0], P0[:, i]) for i in range(3)])
                    pa = p0 - EZ * t
                    ring = lambda q, hw=0.35 * w: np.array([q + EX * hw, q - EX * hw, q - EX * hw - EZ * 1.6 * t,
                                                              q + EX * hw - EZ * 1.6 * t])
                    from spars import loft_solid
                    loft_solid(M, [ring(pa * f), ring((pa - EY * (inset + 0.5 * w)) * f)], RAIL)
            V, F, Mm = M.arrays()
            if sg < 0:
                F = [f_[::-1] for f_ in F]
            self.mesh.add(V, F, RAIL)
        ids = self._pins_along(name, P, Nn, w, sp, None)
        self.rails[name] = {"kind": "gangway", "x": (a, b), "pins": ids}

    def top_pins(self, mast, sp):
        """belaying pins through a top's after rail (slice 3's rail: a bar on five stanchions along the top's after
        edge), between the stanchions, up the mast's axis: zone top_<mast> + s/p"""
        m = self.rig.masts[mast]
        O, u, f = (np.asarray(m[k], float) for k in ("O", "u", "f"))
        Y = np.cross(u, f)
        h = self.rig.fit["top_rail_ft"] * FT
        Bt = m["Bt"]
        st = 3.5 * IN
        ys = np.linspace(-0.47 * Bt, 0.47 * Bt, 5)
        ids = []
        for sg, tag in ((1.0, "s"), (-1.0, "p")):
            k_all = 0
            for y0, y1 in zip(ys[2:-1], ys[3:]):                 # the gaps between the stanchions, outward
                a, b = y0 + 0.5 * st + 0.06, y1 - 0.5 * st - 0.06
                n = int((b - a) // sp) + 1 if b > a else 0
                c0 = 0.5 * (a + b) - 0.5 * (n - 1) * sp
                for k in range(n):
                    y = c0 + k * sp
                    p = O + (m["s_plat"] + h + 3.0 * IN) * u + (m["fa"] + 2.5 * IN) * f + sg * y * Y
                    ids.append(self.pins.add(f"top_{mast}{tag}", f"top_{mast}{tag}:{k_all}", p, u,
                                             h=self.cfg["pins"]["handle_in"] * IN, d=self.cfg["pins"]["diam_in"] * IN))
                    self.pins.pins[ids[-1]]["out"] = unit(f - (f @ EZ) * EZ) * float(np.sign(m["fa"]))
                    k_all += 1
        self.rails[f"top_{mast}"] = {"kind": "top", "mast": mast, "pins": ids}

    def fife_rail(self, mast, x_fwd, x_aft, half, open_, w, t, over, sp):
        """a horseshoe round the mast's foot: two arms along the ship at +-half (y, their middle) from x_fwd to x_aft
        (relative to the mast's axis at the deck) and the bar across the closed end; open_ "fwd" or "aft": the open
        end. Posts at the corners and arms' ends, and between where a span would be over 1.2 m."""
        m = self.rig.masts[mast]
        x0 = float(m["O"][0])
        xa, xf = x0 + x_aft, x0 + x_fwd
        xc = xa if open_ == "fwd" else xf                       # the closed end
        xo = xf if open_ == "fwd" else xa                       # the open end
        z = self.deck.z(x0) + over
        # the rail's middle line: the starboard arm from the open end to the corner, the bar to the port corner, the
        # port arm back to the open end
        Pm = np.array([[xo, half, z], [xc, half, z], [xc, -half, z], [xo, -half, z]])
        segs = [(Pm[0], Pm[1]), (Pm[1], Pm[2]), (Pm[2], Pm[3])]
        hw = 0.5 * w
        for j, (A, B) in enumerate(segs):
            e = unit(B - A)
            nrm = np.cross(EZ, e)
            # the arms run on into the corners by half the width, and the bar stops at their inner faces: they meet
            # square, with no faces lying on each other (Cycles draws those black)
            A2, B2 = (A + e * hw, B - e * hw) if j == 1 else (A - e * hw, B + e * hw)
            ring = lambda p: np.array([p + nrm * hw, p - nrm * hw, p - nrm * hw - EZ * t, p + nrm * hw - EZ * t])
            from spars import loft_solid
            loft_solid(self.mesh, [ring(A2), ring(B2)], RAIL)
        # posts: at the four ends and corners, and between
        places = []
        for A, B in segs:
            L = float(np.linalg.norm(B - A))
            k = max(1, int(math.ceil(L / 1.2)))
            for j in range(k + 1):
                places.append(A + (B - A) * j / k)
        uniq = []
        for p in places:
            if all(np.linalg.norm(p - q) > 0.05 for q in uniq):
                uniq.append(p)
        for p in uniq:
            post(self.mesh, np.array([p[0], p[1], self.deck.z(p[0]) - 0.02]), np.array([p[0], p[1], z - t]),
                 0.5 * w, RAIL)
            post(self.mesh, np.array([p[0], p[1], z]), np.array([p[0], p[1], z + 0.02]), 0.42 * w, RAIL,
                 cap=0.06)
        # pins along each arm and the bar, clear of the posts
        ids = []
        k_all = 0
        for j, (A, B) in enumerate(segs):
            L = float(np.linalg.norm(B - A))
            e = unit(B - A)
            n = int((L - 0.6 * sp) // sp)
            s0 = 0.5 * (L - (n - 1) * sp)
            for k in range(n):
                p = A + e * (s0 + k * sp)
                if any(np.linalg.norm(p - q) < 0.6 * sp for q in uniq):
                    continue
                side = "s" if p[1] > 0.3 * half else "p" if p[1] < -0.3 * half else "c"
                ids.append(self.pins.add(f"fife_{mast}", f"fife_{mast}:{k_all}", p + EZ * 0.0, EZ,
                                         h=self.cfg["pins"]["handle_in"] * IN, d=self.cfg["pins"]["diam_in"] * IN))
                self.pins.pins[ids[-1]]["side"] = side
                nrm = np.cross(EZ, e)
                self.pins.pins[ids[-1]]["out"] = nrm if (p - np.array([x0, 0.0, p[2]])) @ nrm > 0 else -nrm
                k_all += 1
        self.rails[f"fife_{mast}"] = {"kind": "fife", "mast": mast, "pins": ids}


# ---- the masts' and yards' frames ------------------------------------------------------------------------------------------
class MastGeo:
    """A mast's frames in the ship: the lower mast's (x forward from its axis, y to starboard, s up its axis from the spar
    deck), the topmast's and the topgallant's (x from their own axes, s from the same deck level)"""

    def __init__(self, rig, name):
        self.name, self.m = name, rig.masts[name]
        m = self.m
        self.O, self.u, self.f = (np.asarray(m[k], float) for k in ("O", "u", "f"))
        self.Y = np.cross(self.u, self.f)
        self.Otm, self.Otg = np.asarray(m["Otm"], float), np.asarray(m["Otg"], float)
        self.cap = name.capitalize()

    def lo(self, x, y, s):
        return self.O + x * self.f + y * self.Y + s * self.u

    def tm(self, x, y, s):
        return self.Otm + x * self.f + y * self.Y + s * self.u

    def tg(self, x, y, s):
        return self.Otg + x * self.f + y * self.Y + s * self.u

    def rel(self, P):
        """(x, y, s) of ship points in the lower mast's frame"""
        Q = np.atleast_2d(P) - self.O
        return np.stack([Q @ self.f, Q @ self.Y, Q @ self.u], -1)


class YardGeo:
    """A yard in its own frame (x forward, y along it to starboard, z up its mast): its centre line at x = x_off, z = 0"""

    def __init__(self, rig, pname):
        self.rig, self.name = rig, pname
        g = rig.yard_geom[pname]
        self.g = g
        self.x_off, self.half, self.arm, self.d = g["x_off"], g["half"], g["arm"], g["d"]
        self.cleat_y = g["cleat_y"]

    def R(self, y):
        return float(self.rig.yard_radius(self.name, abs(y)))

    def at(self, y, dx=0.0, dz=0.0):
        return np.array([self.x_off + dx, y, dz])

    def top(self, y, out=0.0):
        return self.at(y, 0.0, self.R(y) + out)

    def bottom(self, y, out=0.0):
        return self.at(y, 0.0, -(self.R(y) + out))

    def back(self, y, out=0.0):
        return self.at(y, -(self.R(y) + out), 0.0)

    def front(self, y, out=0.0):
        return self.at(y, self.R(y) + out, 0.0)


# ---- small fittings ------------------------------------------------------------------------------------------------------
def bullseye_mesh(r_rope):
    """a bull's eye (a wooden thimble: a ring with a score for its strop, the rope through its hole), its hole's axis along
    local Z, centred at the origin. Returns the Mesh and its outer radius."""
    ri = r_rope * 1.35 + 0.25 * IN
    ro = ri + max(0.9 * IN, 1.3 * r_rope)
    h = 0.9 * (ro - ri) + 0.3 * IN
    th = np.linspace(0, 2 * math.pi, 14, endpoint=False)
    prof = [(ri, -0.35 * h), (ri + 0.15 * (ro - ri), -0.5 * h), (ro - 0.1 * (ro - ri), -0.5 * h), (ro, -0.2 * h),
            (ro - 0.12 * (ro - ri), 0.0), (ro, 0.2 * h), (ro - 0.1 * (ro - ri), 0.5 * h), (ri + 0.15 * (ro - ri), 0.5 * h),
            (ri, 0.35 * h)]
    rings = [np.stack([r * np.cos(th), r * np.sin(th), np.full(len(th), z)], 1) for r, z in prof]
    V = np.concatenate(rings)
    F = []
    n = len(th)
    for j in range(len(rings)):
        a, b = j * n, ((j + 1) % len(rings)) * n
        for i in range(n):
            i1 = (i + 1) % n
            F.append((a + i, a + i1, b + i1, b + i))
    M = Mesh()
    M.add(V, F, BLOCK)
    return M, ro


def eyebolt_mesh(r_eye, r_bar):
    """an eyebolt's eye standing out of a surface: a ring in the local XZ plane, its foot at the origin, standing up Z"""
    M = Mesh()
    th = np.linspace(0, 2 * math.pi, 12, endpoint=False)
    c = np.array([0.0, 0.0, r_eye + r_bar])
    P = c[None] + r_eye * np.stack([np.cos(th), np.zeros(12), np.sin(th)], 1)
    tube(M, P, r_bar, IRON, n=6, closed=True)
    tube(M, np.array([[0.0, 0.0, -0.01], [0.0, 0.0, r_bar * 0.5]]), r_bar * 1.6, IRON, n=6)
    return M


def ring_mesh(ri, ro, h, mat, n=14):
    """a ring (a bull's eye's or a thimble's shape: a round score outside for its strop), its axis along local Z"""
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    prof = [(ri, -0.35 * h), (ri + 0.15 * (ro - ri), -0.5 * h), (ro - 0.1 * (ro - ri), -0.5 * h), (ro, -0.2 * h),
            (ro - 0.12 * (ro - ri), 0.0), (ro, 0.2 * h), (ro - 0.1 * (ro - ri), 0.5 * h), (ri + 0.15 * (ro - ri), 0.5 * h),
            (ri, 0.35 * h)]
    rings = [np.stack([r * np.cos(th), r * np.sin(th), np.full(len(th), z)], 1) for r, z in prof]
    F = []
    for j in range(len(rings)):
        a, b = j * n, ((j + 1) % len(rings)) * n
        for i in range(n):
            i1 = (i + 1) % n
            F.append((a + i, a + i1, b + i1, b + i))
    M = Mesh()
    M.add(np.concatenate(rings), F, mat)
    return M


def box_mesh(M, c, ax, ay, az, mat):
    """a box centred at c with half-axis vectors ax, ay, az (either handedness: its faces face out)"""
    c, ax, ay, az = (np.asarray(v, float) for v in (c, ax, ay, az))
    r0 = np.array([c - ax - ay - az, c + ax - ay - az, c + ax + ay - az, c - ax + ay - az])
    if float(np.cross(ax, ay) @ az) < 0.0:
        r0 = r0[::-1]
    loft_solid_(M, [r0, r0 + 2 * az], mat)


def disc_mesh(r, t, mat, n=12):
    """a sheave: a disc of radius r and thickness t, its pin along local Z, a groove round its rim"""
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    prof = [(0.25 * r, -t / 2), (r, -t / 2), (0.86 * r, 0.0), (r, t / 2), (0.25 * r, t / 2)]
    rings = [np.stack([q * np.cos(th), q * np.sin(th), np.full(n, z)], 1) for q, z in prof]
    M = Mesh()
    loft_solid_(M, rings, SHEAVE)
    return M


def kevel_mesh(L, h):
    """a kevel: an oak cleat bolted inside the bulwark, its two horns standing up and out (local X along the bulwark, Y
    inboard out of it, Z up; its back on the bulwark at Y = 0)"""
    M = Mesh()
    t = KEVEL_T
    box_mesh(M, (0.0, t / 2, 0.0), (L / 2 - 0.06, 0.0, 0.0), (0.0, t / 2, 0.0), (0.0, 0.0, h / 2), RAIL)
    for sx in (1.0, -1.0):                                       # the horns, out from the waist and up
        c = np.array([sx * (L / 2 - 0.07), 0.62 * t, 0.42 * h])
        box_mesh(M, c, np.array([sx * 0.07, 0.0, 0.05]), np.array([0.0, 0.42 * t, 0.0]),
                 np.array([-sx * 0.02, 0.0, 0.035]), RAIL)
    return M


EYE_HOLDS = ("Mast_", "Top_", "Topmast_", "Topgallant_", "Rigging_", "Stays", "Bowsprit", "BowspritCap", "Jibboom",
             "SpankerBoom", "SpankerGaff", "Channels", "BulwarkTop", "RailCap")    # what a bull's eye is stropped to


def eye_outer(fit, r_rope):
    """a bull's eye's (or thimble's) outer radius as drawn, for a rope of radius r_rope"""
    if fit == "thimble":
        return r_rope * 1.25 + 0.1 * IN + max(0.35 * IN, 0.6 * r_rope)
    ri = r_rope * 1.35 + 0.25 * IN
    return ri + max(0.9 * IN, 1.3 * r_rope)


def strop_r(r_rope):
    """the radius of a bull's eye's strop (or a thimble's seizing) for a rope of radius r_rope"""
    return max(0.6 * r_rope, 0.2 * IN)


def by_material(F, Mt):
    """faces split by material, each set with only the vertices it uses: [(vertex indices, faces renumbered, material)]"""
    out = []
    for mat in sorted(set(Mt)):
        Fm = [F[i] for i, m_ in enumerate(Mt) if m_ == mat]
        used = sorted({v for f in Fm for v in f})
        nu = {v: k for k, v in enumerate(used)}
        out.append((np.array(used, int), [tuple(nu[v] for v in f) for f in Fm], mat))
    return out


def clean_faces(V, F, Mt, eps=1e-9):
    """a mesh with each face's coincident corners closed up (a quad with two corners the same is a triangle), the faces
    left with no area dropped and the vertices no face uses dropped: (V, F, Mt)"""
    V = np.asarray(V, float)
    F2, M2 = [], []
    for f, m in zip(F, Mt):
        g = []
        for v in f:
            if not g or float(np.abs(V[v] - V[g[-1]]).max()) > eps:
                g.append(v)
        while len(g) > 1 and float(np.abs(V[g[0]] - V[g[-1]]).max()) <= eps:
            g.pop()
        if len(g) < 3:
            continue
        P = V[g]
        if float(np.linalg.norm(np.cross(P[1:-1] - P[0], P[2:] - P[0]).sum(0))) <= eps:
            continue
        F2.append(tuple(g))
        M2.append(m)
    used = sorted({v for f in F2 for v in f})
    nu = {v: k for k, v in enumerate(used)}
    return V[used], [tuple(nu[v] for v in f) for f in F2], M2


def to_frame(z, x_hint):
    """a rotation (columns its axes) whose Z is z and X as near x_hint as square to it allows"""
    z = unit(np.asarray(z, float))
    x = np.asarray(x_hint, float) - (np.asarray(x_hint, float) @ z) * z
    if np.linalg.norm(x) < 1e-6:
        x = np.cross(z, EX if abs(z[0]) < 0.9 else EY)
    x = unit(x)
    return np.stack([x, np.cross(z, x), z], 1)


def simplify(P, tol):
    """Douglas-Peucker: the points of the polyline P that keep it within tol of itself"""
    P = np.asarray(P, float)
    if len(P) < 3:
        return P
    keep = np.zeros(len(P), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(P) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, ab = P[i], P[j] - P[i]
        L2 = float(ab @ ab)
        Q = P[i + 1:j]
        if L2 < 1e-12:
            dd = np.linalg.norm(Q - a, axis=1)
        else:
            t = np.clip((Q - a) @ ab / L2, 0.0, 1.0)
            dd = np.linalg.norm(Q - (a + t[:, None] * ab), axis=1)
        k = int(np.argmax(dd))
        if dd[k] > tol:
            mm = i + 1 + k
            keep[mm] = True
            stack += [(i, mm), (mm, j)]
    return P[keep]


# ---- the running rigging --------------------------------------------------------------------------------------------------
SQUARE_LEVELS = ("course", "topsail", "topgallant", "royal")
ROBAND = 0.045                                                  # the robands round a yard (m)
KEVEL_T = 0.09                                                  # a kevel's thickness off the bulwark (m)
MIRROR = np.array([1.0, -1.0, 1.0])                            # ship port <-> starboard


class Running:
    """Every working line, its blocks and fairleads, the rails and pins they belay to; solved for each sail state"""

    def __init__(self, rig, sk, st, sv, cfg=None):
        self.rig, self.sk, self.st, self.sv = rig, sk, st, sv
        self.cfg = cfg or json.load(open(os.path.join(HERE, "running_1797.json")))
        self.deck = Deck(sk)
        self.rails = Rails(self.deck, rig, self.cfg).build()
        self.pins = self.rails.pins
        self.blocks, self.lines, self.fits = {}, [], []
        self.yg = {n: YardGeo(rig, n) for n in rig.yard_geom}
        self.mg = {n: MastGeo(rig, n) for n in rig.masts}
        self.free = []                                          # (line, station index, box) fairleads to place
        self.kevels = []                                        # (name, point on the bulwark's face, inboard normal)
        self._sailV = None

    # -- sizes -------------------------------------------------------------------------------------------------------
    def circ(self, mast, group, what):
        c = self.cfg["rope_in"][group][what] * self.cfg["mast_scale"].get(mast, 1.0)
        return max(1.0, round(c * 2.0) / 2.0)

    def block_L(self, circ):
        b = self.cfg["block"]
        return max(b["min_in"], round(b["length_of_circ"] * circ)) * IN

    def add_block(self, bid, sheaves, circ, **kw):
        b = Block(bid, sheaves, self.block_L(circ), rope_r(circ * self.cfg["block"]["strop_of_rope"]), **kw)
        b.circ = circ
        self.blocks[bid] = b
        return b

    def new_line(self, name, group, circ, note=""):
        ln = Line(name, group, circ, note)
        self.lines.append(ln)
        return ln

    # -- the sails' corners in each state (in their yard's frame) --------------------------------------------------------
    def sailV(self, key, state):
        if self._sailV is None:
            self._sailV = {}
            for name, (V, F, M, U, frame, parent, k, s) in self.sv.objects().items():
                V = np.asarray(V, float)
                if frame is not None:
                    o, R = frame
                    V = o + V @ np.asarray(R, float).T
                    po, PR = self.rig.parts_[parent]["frame"]
                    V = (V - np.asarray(po, float)) @ np.asarray(PR, float)
                self._sailV[(k, s)] = np.concatenate([self._sailV[(k, s)], V]) if (k, s) in self._sailV else V
        return self._sailV[(key, state)]

    @staticmethod
    def sail_obj(key, state):
        """a sail's object name in a state (as sails.py names them)"""
        return "Sail_" + "".join(w.capitalize() for w in key.split("_")) + "_" + state

    def roll_at(self, key, y):
        """the furled roll's centre (yard frame) and radius at y along the yard"""
        V = self.sailV(key, "Furled")
        sel = np.abs(V[:, 1] - y) < 0.06
        if sel.sum() < 4:
            sel = np.abs(V[:, 1] - y) < 0.2
        P = V[sel]
        c = np.array([P[:, 0].mean(), y, P[:, 2].mean()])
        r = float(np.max(np.hypot(P[:, 0] - c[0], P[:, 2] - c[2])))
        return c, r

    def foot_set(self, key, y):
        """the set sail's foot (its lowest point, the foot rope's underside) near y"""
        V = self.sailV(key, "Set")
        sel = np.abs(V[:, 1] - y) < 0.08
        P = V[sel]
        return P[np.argmin(P[:, 2])]

    def clew(self, key, state, sg):
        """a square sail's clew (yard frame, sg the side), set or clewed up under its block (furled, it is two-blocked
        at its clewline block's tail: the ropes bent to it end on the block)"""
        inf = self.sv.info[key]
        f = np.array([1.0, sg, 1.0])
        if state == "Set":
            return np.asarray(inf["clew_local_m"], float) * f
        if state == "Clewed":
            return np.asarray(inf["clew_block_local_m"], float) * f
        raise ValueError(state)

    def clew_end(self, key, S, sg, toward):
        """where a clewline is bent to the clew (yard frame), set (a little abaft the clew: it runs up abaft the sail) or
        clewed up (furled, the clew is two-blocked at the clewline block's tail: an end on the block)"""
        if S == "Set":
            return self.clew(key, S, sg) + np.array([-0.04, 0.0, 0.0])
        return self.clew(key, S, sg)

    def cloth_bvh(self, key, state):
        """the sail key's cloth in a state as a BVH in its yard's frame (to find the cloth's fore side under a rope)"""
        self._cloth = getattr(self, "_cloth", {})
        if (key, state) not in self._cloth:
            Vs, Fs, n0 = [], [], 0
            for name, (V, F, M, U, frame, parent, k, s) in self.sv.objects().items():
                if (k, s) != (key, state):
                    continue
                V = np.asarray(V, float)
                if frame is not None:
                    o, R = frame
                    V = o + V @ np.asarray(R, float).T
                    po, PR = self.rig.parts_[parent]["frame"]
                    V = (V - np.asarray(po, float)) @ np.asarray(PR, float)
                Vs.append(V)
                Fs += [tuple(int(i) + n0 for i in f) for f in F]
                n0 += len(V)
            V = np.concatenate(Vs)
            self._cloth[(key, state)] = BVHTree.FromPolygons([tuple(map(float, v)) for v in V], Fs)
        return self._cloth[(key, state)]

    def cloth_front(self, key, S, L, r):
        """for points L (yard frame), the foremost x of the cloth within r of each across (y, z): -inf where none"""
        bvh = self.cloth_bvh(key, S)
        from mathutils import Vector
        offs = [(0.0, 0.0), (r, 0.0), (-r, 0.0), (0.0, r), (0.0, -r)]
        out = np.full(len(L), -np.inf)
        for i, q in enumerate(L):
            for dy, dz in offs:
                loc, nrm, idx, dist = bvh.ray_cast(Vector((float(q[0]) + 8.0, float(q[1]) + dy, float(q[2]) + dz)),
                                                   Vector((-1.0, 0.0, 0.0)), 16.0)
                if loc is not None:
                    out[i] = max(out[i], loc[0])
        return out

    @staticmethod
    def _span_points(A, B, slack=0.0):
        span = float(np.linalg.norm(B - A))
        n = max(8, int(span / 0.05))
        if slack > 0:
            return SA.catenary(A, B, span * (1.0 + slack), n + 1)
        return A[None] + np.linspace(0.0, 1.0, n + 1)[:, None] * (B - A)[None]

    @staticmethod
    def _drape(onp, slack=0.0):
        """a span function fn(A, B) -> points from a push on points (onp), with the push itself as fn.onp (to chain)"""
        def fn(A, B):
            return onp(Running._span_points(A, B, slack))
        fn.onp = onp
        return fn

    @staticmethod
    def chain(*fns):
        """drapes one after another: the first lays the span, each next pushes its points further"""
        def onp(P):
            for f in fns:
                P = f.onp(P)
            return P

        def fn(A, B):
            P = fns[0](A, B)
            for f in fns[1:]:
                P = f.onp(P)
            return P
        fn.onp = onp
        return fn

    def drape_front(self, key, S, yn, r, slack=0.0, extra=0.0):
        """a span's points (between A and B, ship) laid forward of the sail key's cloth where it would pass through it:
        a slack rope hanging over a clewed or furled sail (extra: further forward still, to lie before another rope that
        is laid over the same cloth)"""
        o, Rm = Pose(self.rig, S).frame(yn)
        clear = r + self.cfg["check"]["gap_in"] * IN + 0.03 + extra

        def onp(P):
            L = (P - o) @ Rm
            need = self.cloth_front(key, S, L, r + 0.02) + clear
            push = np.maximum(need - L[:, 0], 0.0)
            if push.max() > 0:
                k = 3                                           # spread the push so the rope eases over the cloth
                pp = np.array([push[max(0, i - k):i + k + 1].max() for i in range(len(push))])
                sm = np.convolve(np.pad(pp, 2, mode="edge"), np.ones(5) / 5, mode="valid")
                pp = np.maximum(sm, push)
                pp[0] = pp[-1] = 0.0
                L[:, 0] += pp
            return o + L @ Rm.T
        return self._drape(onp, slack)

    def drape_yard(self, yn, S, r, fade=(0.15, 0.8)):
        """a span laid along a yard's underside where its straight line would pass through the yard or the robands round
        it (a sheet or clewline lying along the yard to its quarter block, as they did): each point under the yard's
        breadth pushed down (yard frame) to the robands' underside, the rope and the gap; the push fades in over fade
        (m) from the span's start (the rope comes out of a sheave hole or off a block there)"""
        Y = self.yg[yn]
        o, Rm = Pose(self.rig, S).frame(yn)
        gap = self.cfg["check"]["gap_in"] * IN

        def onp(P):
            L = (P - o) @ Rm
            Rr = np.array([Y.R(y) for y in L[:, 1]])
            lim = -(Rr + ROBAND + r + gap + 0.004)
            under = np.abs(L[:, 0] - Y.x_off) < Rr + ROBAND + r + gap
            w = np.clip((np.linalg.norm(P - P[0][None], axis=1) - fade[0]) / (fade[1] - fade[0]), 0.0, 1.0)
            push = np.where(under, np.maximum(L[:, 2] - lim, 0.0), 0.0) * w
            push[-1] = 0.0
            L[:, 2] -= push
            return o + L @ Rm.T
        return self._drape(onp)

    def head_rim(self, key, yn):
        """the head of sail key bent to its yard (its roping and lacing, slice 5's Head piece) as a radius about the
        yard's axis in the yard's frame, by y (5 cm bins) and angle (5 degree bins): a function (y, angle in degrees) ->
        the largest radius there and in the bins beside it (0 where there is no head)"""
        cache = self.__dict__.setdefault("_head_rim", {})
        if (key, yn) in cache:
            return cache[(key, yn)]
        Y = self.yg[yn]
        Vs = []
        for name, (V, F, M, U, frame, parent, k, state) in self.sv.objects().items():
            if k != key or state != "Head":
                continue
            V = np.asarray(V, float)
            ext = []                                            # points every 2 cm along each face's edges
            for f_ in F:
                for i_ in range(len(f_)):
                    a_, b_ = V[f_[i_]], V[f_[(i_ + 1) % len(f_)]]
                    n_ = int(np.linalg.norm(b_ - a_) / 0.02)
                    if n_ > 1:
                        ext.append(a_[None] + np.linspace(0.0, 1.0, n_ + 1)[1:-1, None] * (b_ - a_)[None])
            if ext:
                V = np.concatenate([V] + ext)
            if frame is not None:
                fo, fR = frame
                V = np.asarray(fo, float) + V @ np.asarray(fR, float).T
                po, PR = self.rig.parts_[parent]["frame"]
            else:
                po, PR = self.rig.parts_[yn]["frame"]
            Vs.append((V - np.asarray(po, float)) @ np.asarray(PR, float))
        table = {}
        if Vs:
            V = np.concatenate(Vs)
            ang = np.degrees(np.arctan2(V[:, 2], V[:, 0] - Y.x_off))
            rr = np.hypot(V[:, 0] - Y.x_off, V[:, 2])
            for i, j, rv in zip(np.floor(V[:, 1] / 0.05).astype(int), np.floor((ang + 180.0) / 5.0).astype(int) % 72, rr):
                if rv > table.get((i, j), 0.0):
                    table[(i, j)] = float(rv)

        def dil(i, j):
            return max(table.get((i + di, (j + dj) % 72), 0.0) for di in (-1, 0, 1) for dj in (-1, 0, 1))

        def rim(y, a):                                  # between the bins' centres linearly, so a rope pushed out
            fy, fa = y / 0.05 - 0.5, (a + 180.0) / 5.0 - 0.5    # onto it never steps
            i, j = int(math.floor(fy)), int(math.floor(fa))
            ty, ta = fy - i, fa - j
            return ((1 - ty) * ((1 - ta) * dil(i, j % 72) + ta * dil(i, (j + 1) % 72)) +
                    ty * ((1 - ta) * dil(i + 1, j % 72) + ta * dil(i + 1, (j + 1) % 72)))
        cache[(key, yn)] = rim
        return rim

    def drape_over(self, yn, S, r, key=None):
        """a span laid over a yard where its straight line would cut it (a buntline's leg from its block above and abaft
        the yard, over the yard's top to the sail's fore side), taut: near the yard (within 0.8 m of its axis) the rope
        takes the shortest way, in the yard's section, round the yard's round and robands (and sail key's head bent to
        it), what stands on it there (its sling cleats, the studding sail booms in their irons) and the points it came
        in with (laid over the cloth before), on the side its straight line passes; along the yard it goes on evenly
        with that way's length, as a taut rope round a spar does. A straight run on to the span's end is part of the way
        (the rope leads from there); the ends stay"""
        Y = self.yg[yn]
        rim = self.head_rim(key, yn) if key else (lambda y, a: 0.0)
        o, Rm = Pose(self.rig, S).frame(yn)
        c = r + self.cfg["check"]["gap_in"] * IN + 0.01               # and the chord between points cutting the bend
        sol = Y.g.get("solids", [])
        ang = np.radians(np.arange(0.0, 360.0, 2.0))
        ring = np.stack([np.cos(ang[::4]), np.sin(ang[::4])], 1)

        def outline(ylo, yhi):
            """what the rope must pass outside of in the yard's section, for a run between ylo and yhi along the yard:
            (the round's clearance by angle, [each solid's section as points (x, z)])"""
            yy = np.linspace(ylo, yhi, 3)
            need = np.array([max(max(Y.R(y) + ROBAND, rim(y, math.degrees(a_))) for y in yy) for a_ in ang]) + c
            polys = []
            for so in sol:
                if so["kind"] == "cyl":                         # a capsule: its round where it reaches the run
                    a_, b_ = np.asarray(so["a"], float), np.asarray(so["b"], float)
                    R_ = so["r"] + c
                    for t in np.linspace(0.0, 1.0, 17):
                        q = a_ + t * (b_ - a_)
                        dy = abs(q[1] - min(max(q[1], ylo), yhi))
                        if dy < R_:
                            polys.append(q[[0, 2]][None] + math.sqrt(R_ ** 2 - dy ** 2) * ring)
                else:
                    cc, ax, h = (np.asarray(so[k_], float) for k_ in ("c", "axes", "half"))
                    h = h + c
                    cn = np.array([cc + (sx * h[0]) * ax[0] + (sy * h[1]) * ax[1] + (sz * h[2]) * ax[2]
                                   for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
                    if cn[:, 1].max() >= ylo and cn[:, 1].min() <= yhi:
                        polys.append(cn[:, [0, 2]])
            return need, polys

        def cuts(Lr, need, polys):
            """whether the run passes inside what it must clear (each segment tested every 5 mm)"""
            from scipy.spatial import ConvexHull
            seg = np.linalg.norm(np.diff(Lr, axis=0), axis=1)
            pts = [Lr[:1, [0, 2]]]
            for i_ in range(len(Lr) - 1):
                n_ = max(1, int(math.ceil(seg[i_] / 0.005)))
                pts.append(Lr[i_][None, [0, 2]] + np.linspace(0.0, 1.0, n_ + 1)[1:, None] * (Lr[i_ + 1] - Lr[i_])[None, [0, 2]])
            p_ = np.concatenate(pts)
            a_ = np.degrees(np.arctan2(p_[:, 1], p_[:, 0] - Y.x_off)) % 360.0
            if (np.hypot(p_[:, 0] - Y.x_off, p_[:, 1]) < np.interp(a_, np.degrees(ang), need, period=360.0) - 1e-4).any():
                return True
            for Pg in polys:
                try:
                    eq = ConvexHull(Pg).equations
                except Exception:
                    continue
                if ((p_ @ eq[:, :2].T + eq[:, 2][None]) < -1e-4).all(1).any():
                    return True
            return False

        def taut(Lr):
            """the run Lr (yard frame; its first and last points stay) laid the shortest way round the section, if it
            passes inside it (else as it came)"""
            from scipy.spatial import ConvexHull
            need, polys = outline(float(Lr[:, 1].min()), float(Lr[:, 1].max()))
            if not cuts(Lr, need, polys):
                return Lr
            E, X = Lr[0], Lr[-1]
            e, x = E[[0, 2]], X[[0, 2]]
            ch = e[None] + np.linspace(0.0, 1.0, 65)[:, None] * (x - e)[None]
            dn = np.hypot(ch[:, 0] - Y.x_off, ch[:, 1])
            j = int(np.argmin(dn))
            w = (ch[j] - np.array([Y.x_off, 0.0])) / max(dn[j], 1e-9)     # the side the straight line passes on
            t_ = x - e
            nrm = np.array([-t_[1], t_[0]]) / max(np.linalg.norm(t_), 1e-12)
            if nrm @ w < 0.0:
                nrm = -nrm
            pts = np.concatenate([e[None], x[None], np.stack([Y.x_off + need * np.cos(ang), need * np.sin(ang)], 1)]
                                 + polys + [Lr[1:-1][:, [0, 2]]])
            try:
                hv = list(ConvexHull(pts).vertices)             # counter-clockwise
            except Exception:
                return Lr
            if 0 not in hv or 1 not in hv:                      # an end in a hollow of what it clears: as it came
                return Lr
            k0 = hv.index(0)
            hv = hv[k0:] + hv[:k0]
            k1 = hv.index(1)
            ways = (hv[:k1 + 1], [0] + hv[k1:][::-1])           # the two ways round, each from the first end
            way = max(ways, key=lambda wy: float(((pts[wy] - e) @ nrm).max()))
            W = pts[way]
            seg = np.linalg.norm(np.diff(W, axis=0), axis=1)
            out = [W[:1]]
            for i_ in range(len(W) - 1):                        # a point every centimetre
                n_ = max(1, int(math.ceil(seg[i_] / 0.01)))
                out.append(W[i_][None] + np.linspace(0.0, 1.0, n_ + 1)[1:, None] * (W[i_ + 1] - W[i_])[None])
            W = np.concatenate(out)
            s_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(W, axis=0), axis=1))])
            yv = E[1] + (X[1] - E[1]) * s_ / max(s_[-1], 1e-12)
            Lw = np.stack([W[:, 0], yv, W[:, 1]], 1)
            Lw[0], Lw[-1] = E, X
            return Lw

        def straight(L, i, j):
            """whether L[i..j] lies along the line from L[i] to L[j] (within a millimetre)"""
            if j - i < 2:
                return True
            a_, b_ = L[i], L[j]
            ab = b_ - a_
            t = np.clip(((L[i:j + 1] - a_) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
            return float(np.linalg.norm(L[i:j + 1] - (a_[None] + t[:, None] * ab[None]), axis=1).max()) < 0.001

        def onp(P):
            L = (P - o) @ Rm
            near = np.hypot(L[:, 0] - Y.x_off, L[:, 2]) < 0.8
            near[0] = near[-1] = False
            if not near.any():
                return P
            idx = np.where(near)[0]
            runs, i0 = [], idx[0]
            for a_, b_ in zip(idx[:-1], idx[1:]):
                if b_ != a_ + 1:
                    runs.append((i0, a_))
                    i0 = b_
            runs.append((i0, idx[-1]))
            out, last = [], 0
            for k, (i0, i1) in enumerate(runs):
                lo = runs[k - 1][1] + 1 if k else 0
                hi = runs[k + 1][0] - 1 if k + 1 < len(runs) else len(L) - 1
                a_ = lo if straight(L, lo, i0) else i0 - 1      # a straight lead on to the span's end is the way's
                b_ = hi if straight(L, i1, hi) else i1 + 1
                a_ = max(a_, last)
                out.append(L[last:a_])
                out.append(taut(L[a_:b_ + 1]))
                last = b_ + 1
            out.append(L[last:])
            return o + np.concatenate(out) @ Rm.T
        return self._drape(onp)

    def drape_mast(self, mast, spar, r, near_b=0.3):
        """a span laid outside a mast's round where its straight line would pass inside it (a rope from a sheave in the
        mast down its face to a yard lowered well below): each point pushed out square to the axis to the mast's radius,
        the rope and the gap; the push fades to nothing over near_b at the span's end (the sheave's hole)"""
        MG = self.mg[mast]
        m = MG.m
        org = {"lo": MG.O, "tm": MG.Otm, "tg": MG.Otg}[spar]
        Rf = {"lo": m["R_lower"], "tm": m["R_tm"], "tg": m["R_tg"]}[spar]
        clear = r + self.cfg["check"]["gap_in"] * IN + 0.006

        def onp(P):
            Q = P - org
            x, y, s = Q @ MG.f, Q @ MG.Y, Q @ MG.u
            rho = np.maximum(np.hypot(x, y), 1e-6)
            need = np.array([float(Rf(si)) for si in s]) + clear
            w = np.clip((np.linalg.norm(P - P[-1][None], axis=1) - 0.1) / max(near_b - 0.1, 1e-6), 0.0, 1.0)
            push = np.maximum(need - rho, 0.0) * w
            push[0] = 0.0
            return P + (push * x / rho)[:, None] * MG.f[None] + (push * y / rho)[:, None] * MG.Y[None]
        return self._drape(onp)

    # -- names -------------------------------------------------------------------------------------------------------
    @staticmethod
    def yard_of(mast, k):
        Mn = mast.capitalize()
        if k == 0:
            return "Yard_Crossjack" if mast == "mizzen" else f"Yard_{Mn}"
        return f"Yard_{Mn}{SQUARE_LEVELS[k].capitalize()}"

    @staticmethod
    def sail_of(mast, k):
        return None if (k == 0 and mast == "mizzen") else f"{mast}_{SQUARE_LEVELS[k]}"

    def group_of(self, mast, k):
        return "crossjack" if (mast == "mizzen" and k == 0) else SQUARE_LEVELS[k]

    # -- where the gear is made fast on a yard (yard frame, starboard; y along the yard) -------------------------------
    def arm_places(self, mast, k):
        """the yardarm's places: the sheave for the sheet of the sail above (at its clew's y), the lift's and the brace's
        strops outside it, the footrope's outer end inside it"""
        yn = self.yard_of(mast, k)
        Y = self.yg[yn]
        tip = Y.half
        above = self.sail_of(mast, k + 1) if k < 3 else None
        if above:
            sh = float(self.sv.info[above]["clew_local_m"][1])
            room = tip - 0.05 - sh
            return {"sheave": sh, "lift": tip - 0.06 - 0.25 * min(room, 0.4), "brace": tip - 0.03,
                    "foot": min(sh - 0.22, Y.cleat_y + 0.6 * (sh - Y.cleat_y))}
        return {"sheave": None, "lift": tip - 0.06 * Y.arm - 0.05, "brace": tip - 0.03,
                "foot": Y.cleat_y + 0.25 * Y.arm}

    def lane_box(self, mast):
        """the box (lower mast's frame: x, |y|, s ranges) where the falls from aloft may pass through a bull's eye under
        the top: forward of the lower shrouds' eyes, outside the trestletrees, inside the lubber's hole"""
        m = self.mg[mast].m
        hs, ttb = m["hs"], m["tt_b"]
        hw = m["hole"][2]
        x_ct = min(x for x in m["ct_xs"] if x > 0) - m["ct_b"] / 2 - 0.06
        return ((1.36 * hs, min(x_ct, m["hole"][1] - 0.08)), (hs + ttb + 0.03, hw - 0.06),
                (m["s_h"] - 0.5 * hs, m["s_tt1"] - 0.02))

    def fair(self, mast, sg, box=None):
        """a bull's eye station whose place the optimiser picks inside box (lower mast frame; default the lane under the
        top), on the side sg"""
        box = box or self.lane_box(mast)
        (x0, x1), (y0, y1), (s0, s1) = box
        MG = self.mg[mast]
        P = MG.lo(0.5 * (x0 + x1), sg * 0.5 * (y0 + y1), 0.5 * (s0 + s1))
        return {"k": "thru", "at": ("ship", P), "r": 0.0, "fit": "bullseye", "box": (mast, sg, box)}

    # -- pins --------------------------------------------------------------------------------------------------------
    def pin_station(self, mast, sg, prefer):
        """a pin to be picked later (the nearest free one in the zones prefer, on side sg), as a station"""
        tag = "s" if sg > 0 else "p"
        zones = [z if z.startswith("fife") else z + tag for z in prefer]
        return {"k": "pin", "pin": None, "zones": zones, "side": sg}

    def ends(self, frame, p):
        return {"k": "end", "at": (frame, np.asarray(p, float))}

    def sheave(self, bid, i=0):
        return {"k": "sheave", "b": bid, "i": i}

    def hidden_sheave(self, bid, frame, c, n, rs, circ):
        """a sheave in a spar (no block drawn): fixed at c (frame), its pin along n, radius rs to the rope's bed"""
        b = self.add_block(bid, 1, circ, fixed=(frame, np.asarray(c, float), np.array([0.0, 0.0, -1.0]),
                                                 np.asarray(n, float)))
        b.rs = rs
        b.hidden = True
        b.touch = 1.0                                           # the rope lies along the yardarm in its score
        return b

    # -- the square gear of a mast -----------------------------------------------------------------------------------------
    def caps(self, mast):
        """the lower cap's and the topmast cap's outlines: (x0, x1, half, s0, s1) in their masts' frames"""
        m = self.mg[mast].m
        cm = 0.35 * m["D_tm"]
        low = (-m["hs"] - cm, m["off_tm"] + m["D_tm"] / 2 + cm, m["hs"] + cm, m["s_top"], m["s_cap1"])
        cm2 = 0.35 * m["D_tg"]
        top = (-m["hs_tm"] - cm2, m["off_tg"] + m["D_tg"] / 2 + cm2, m["hs_tm"] + cm2, m["s_tm_top"], m["s_tmcap1"])
        return low, top

    def tm_box(self, mast):
        """where the falls from the topgallant mast pass the topmast's head (lower mast frame): a bull's eye beside the
        topmast's trestletrees, abaft the topsail yard hoisted and before the topmast shrouds' eyes"""
        m = self.mg[mast].m
        k = m["hs_tm"] / 0.199
        o, h, b = m["off_tm"], m["hs_tm"], m["hs_tm"] + m["tt2_b"]
        return ((o + 0.18 * h, o + 1.29 * h), (b + 0.05, b + 0.05 + 0.14 * k), (m["s_tmh"] - 0.37 * k, m["s_tmh"] + 0.08))

    # -- the square gear of a mast -----------------------------------------------------------------------------------------
    def lt_box(self, mast, fam, ymin=None):
        """the part of the lane under the top a family of falls comes down through: the further forward a fall comes
        down, the further aft its pin must be for the fall to pass abaft the lower yard"""
        (x0, x1), (y0, y1), (s0, s1) = self.lane_box(mast)
        a, b = {"near": (0.0, 0.19), "mid": (0.21, 0.40), "ubunt": (0.43, 0.62), "far": (0.81, 1.0),
                "bunt": (0.64, 0.79)}[fam]
        # the far falls come through low and the mid ones high, so a far fall on its way aft passes under the mid eyes;
        # the course's buntlines come in from forward under the top, low; the topsail's come down from above, low
        c, d = {"near": (0.0, 1.0), "mid": (0.45, 1.0), "ubunt": (0.0, 0.45), "far": (0.0, 0.35),
                "bunt": (0.0, 0.4)}[fam]
        k = self.mg[mast].m["hs_tm"] / 0.199
        if fam == "far":                                        # inside the foremost topmast shroud as it spreads, and
            y1 = min(y1, y0 + 0.07 * k)                         # inside the mid falls (they come down from outboard)
        elif fam == "mid":
            y0 = y0 + 0.08 * k
        return ((x0 + a * (x1 - x0), x0 + b * (x1 - x0)), (y0 if ymin is None else max(y0, ymin), y1),
                (s0 + c * (s1 - s0), s0 + d * (s1 - s0)))

    def in_top(self, mast):
        return mast in self.cfg["pins"].get("top", [])

    def top_pin(self, mast, sg):
        """a pin in the top's after rail, as a station (a fall from above the top belayed in it)"""
        return self.pin_station(mast, sg, [f"top_{mast}"])

    def falls(self, mast, sg, fam, ymin=None):
        """the shared tail of a fall from aloft: the bull's eye under the top (in its family's part of the lane, outside
        ymin), the pin (in its family's rails)"""
        return [self.fair(mast, sg, self.lt_box(mast, fam, ymin)), self.pin_station(mast, sg, self.rails_of[mast][fam])]

    def rail_plan(self, mast):
        """the rails each family of falls belays to, by where the fall comes down through the top: near (the after part
        of the lane) to the fife rail and the rail beside the mast, mid to the next rail aft, far further aft"""
        if mast == "main":
            near, mid, far, bunt, ubunt = ["fife_main", "qd8"], ["qd7"], ["qd6", "qd5"], ["qd7", "qd6"], ["qd6", "qd5"]
        elif mast == "fore":
            near, mid, far, bunt, ubunt = ["fife_fore", "fc1"], ["fc1", "fife_fore"], ["fc1", "gw"], \
                ["fife_fore", "fc1"], ["fife_fore", "fc1"]
        else:
            near, mid, far, bunt, ubunt = ["fife_mizzen", "qd3"], ["qd3", "qd4"], ["qd4", "qd2", "qd5"], ["qd4", "qd3"], \
                ["qd4", "qd2"]
        return {"near": near, "mid": mid, "far": far, "bunt": bunt, "ubunt": ubunt}

    def cap_box(self, mast):
        """the throat forward of the topmast head every fall from forward above the topmast cap passes: a thimble beside
        the cap, forward of the topmast shrouds' eyes, abaft the topsail yard's middle hoisted, outside the trestletrees
        and inside the foremost topmast shroud as it spreads (lower mast frame)"""
        m = self.mg[mast].m
        Y = self.yg[self.yard_of(mast, 1)]
        k = m["hs_tm"] / 0.199
        x0 = m["off_tm"] + m["hs_tm"] + 0.03
        x1 = m["off_tm"] + Y.x_off - Y.R(0.0) - 0.035
        y0 = m["hs_tm"] + m["tt2_b"] + 0.025
        return ((x0, max(x1, x0 + 0.03)), (y0, y0 + 0.06 * k), (m["s_tmct1"] + 0.45 * k, m["s_tm_top"] - 0.05))

    def cap_side_box(self, mast, part=None):
        """under the lower cap's side, outside it: a bull's eye the falls from the topsail yard's quarter blocks pass
        through, so they come down well abaft the lower lifts' legs (which leave the cap's fore face) when the topsail
        yard is lowered onto the cap (lower mast frame). part 0: its after half (the sheet, off the quarter block's
        after sheave), 1: its fore half (the clewline, off the fore sheave), so the two falls don't cross"""
        m = self.mg[mast].m
        k = m["hs_tm"] / 0.199
        low, _ = self.caps(mast)
        lx0, lx1, lhb, ls0, ls1 = low
        x0, x1 = lx1 - 0.4 * k, lx1 - 0.23 * k
        if part is not None:
            xm = 0.5 * (x0 + x1)
            x0, x1 = ((x0, xm - 0.004) if part == 0 else (xm + 0.004, x1))
        return ((x0, x1), (lhb + 0.15 * k, lhb + 0.23 * k), (ls0 - 0.24 * k, ls0 - 0.07 * k))

    def aft_box(self, mast):
        """the chimney abaft the topmast head: a thimble abaft the topmast's after crosstree, outside the trestletrees,
        between the crosstrees and the cap (lower mast frame); the falls through it pass inside the topmast backstays"""
        m = self.mg[mast].m
        k = m["hs_tm"] / 0.199
        xa = m["off_tm"] + m["ct2_xs"][0] - m["ct2_b"] / 2
        y0 = m["hs_tm"] + m["tt2_b"] + 0.025
        return ((xa - 0.2 * k, xa - 0.025), (y0, y0 + 0.05 * k), (m["s_tmct1"] + 0.2 * k, m["s_tm_top"] - 0.05))

    def cap_thimble(self, mast, sg, r=0.0, part=None):
        """an iron thimble seized beside the topmast cap, its place picked in the throat (part 0: its after half, 1: its
        fore half, for the two ropes off a double block's sheaves, so they keep their sheaves' distance apart down to
        the cap); r: the bend round it"""
        (x0, x1), ys, ss = self.cap_box(mast)
        if part is not None:
            xm = 0.5 * (x0 + x1)
            x0, x1 = ((x0, xm - 0.004) if part == 0 else (xm + 0.004, x1))
        return {"k": "thru", "at": ("ship", self.mg[mast].lo(0, 0, 0)), "r": r, "fit": "thimble",
                "box": (mast, sg, ((x0, x1), ys, ss))}

    def aft_thimble(self, mast, sg, r=0.0):
        """an iron thimble on a lanyard abaft the topmast head, its place picked in the after chimney"""
        return {"k": "thru", "at": ("ship", self.mg[mast].lo(0, 0, 0)), "r": r, "fit": "thimble",
                "box": (mast, sg, self.aft_box(mast))}

    def aft_ymin(self, mast):
        """how far out a fall from the after chimney must come down through the top to pass outside the lower cap"""
        low, _ = self.caps(mast)
        return low[2] + 0.15 * self.mg[mast].m["hs_tm"] / 0.199

    def cap_slot(self, mast, sg, i):
        """the i-th place along the topmast cap's side (forward of the topmast shrouds' eyes, abaft its fore edge), for a
        lead block's eyebolt or a bull's eye: lower mast frame, ship point"""
        MG = self.mg[mast]
        m = MG.m
        _, (tx0, tx1, thb, ts0, ts1) = self.caps(mast)
        x_eyes = m["off_tm"] + m["hs_tm"] + 0.06                 # forward of the shrouds' eyes round the topmast head
        x_fwd = m["off_tm"] + tx1 - 0.05
        xs = np.linspace(x_fwd, x_eyes, 5)
        x = xs[min(i, 4)]
        return MG.lo(x, sg * (thb + 0.015), m["s_tm_top"] - 0.02)

    def cap_eye(self, mast, sg, i):
        """a bull's eye seized under the topmast cap's side at slot i, the fall from above through it"""
        P = self.cap_slot(mast, sg, i) + self.mg[mast].Y * sg * 0.05 - self.mg[mast].u * 0.06
        return {"k": "thru", "at": ("ship", P), "r": 0.0, "fit": "bullseye"}

    def square_gear(self, mast):
        MG = self.mg[mast]
        m = MG.m
        Mn = mast.capitalize()
        grp = Mn
        low_cap, top_cap = self.caps(mast)
        lx0, lx1, lhb, ls0, ls1 = low_cap
        tx0, tx1, thb, ts0, ts1 = top_cap
        rails = self.rail_plan(mast)
        self.rails_of = getattr(self, "rails_of", {})
        self.rails_of[mast] = rails
        for sg in (1.0, -1.0):
            tag = "S" if sg > 0 else "P"
            side = "starboard" if sg > 0 else "port"
            for k in range(3):
                yn = self.yard_of(mast, k)
                Y = self.yg[yn]
                ap = self.arm_places(mast, k)
                g = self.group_of(mast, k)
                lvl = g
                c = self.circ(mast, g, "lift")
                ln = self.new_line(f"{mast} {lvl} lift {side}", grp, c)
                Rl = Y.R(ap["lift"])
                arm = Y.at(sg * ap["lift"], -0.9 * Rl, 0.45 * Rl)
                if k == 0:
                    # a double lift: standing part at the cap's fore face, through a block at the yardarm, a block at
                    # the cap beside the standing part, down through the top
                    # the yardarm block seized abaft the yardarm (its pin fore and aft), clear of the yard and of the
                    # topsail's clew coming down to the sheave just inside it
                    arm_b = Y.at(sg * ap["lift"], -(Rl + 0.1), 0.25 * Rl)
                    yb = self.add_block(f"{Mn}{lvl}LiftArm{tag}", 1, c, attach=(yn, arm_b), pendant=0.0, group=grp,
                                        hint=(yn, EX))
                    # the standing part and the block at the cap's fore face, so the legs run out forward of the
                    # topmast shrouds
                    E = MG.lo(lx1 + 0.015, sg * 0.06, 0.5 * (ls0 + ls1))
                    cb = self.add_block(f"{Mn}{lvl}LiftCap{tag}", 1, c,
                                        attach=("ship", MG.lo(lx1 + 0.07, sg * 0.15, ls0 + 0.03)), pendant=0.03,
                                        group=grp)
                    head = [self.ends("ship", E), self.sheave(yb.bid), self.sheave(cb.bid)]
                    tail = self.falls(mast, sg, "near")
                elif k == 1:
                    # from the yardarm in over the topmast shrouds' heads to a thimble abaft the topmast head, down
                    head = [self.ends(yn, arm), self.aft_thimble(mast, sg, r=0.035)]
                    tail = [self.top_pin(mast, sg)] if self.in_top(mast) else \
                        self.falls(mast, sg, "near", self.aft_ymin(mast))
                else:
                    # a block on a strop round the topgallant masthead above the shrouds' eyes, swinging out over the
                    # yardarm's side; the fall down abaft the topmast head (royals are set flying: no royal lifts)
                    s_b = m["s_stop"] + 0.9
                    R_p = float(m["R_tg"](s_b))
                    hb_ = self.add_block(f"{Mn}{lvl}LiftHead{tag}", 1, c, attach=("ship", MG.tg(0.0, sg * (R_p + 0.01), s_b)),
                                         pendant=0.25, group=grp)
                    head = [self.ends(yn, arm), self.sheave(hb_.bid), self.aft_thimble(mast, sg)]
                    tail = [self.top_pin(mast, sg)] if self.in_top(mast) else \
                        self.falls(mast, sg, "near", self.aft_ymin(mast))
                for S in STATES:
                    ln.set(S, head + tail)
            self._sheets_clewlines(mast, sg, tag, side, grp, rails)
            if mast != "mizzen":
                self.course_gear(mast, sg, tag, side, grp, rails)
            self.topsail_buntlines(mast, sg, tag, side, grp)
            if mast == "main":
                self.course_braces(mast, sg, tag, side, grp)
            self.brace_gear(mast, sg, tag, side, grp)
        self.upper_halyards(mast, grp, rails)
        self.topsail_halyard(mast, grp, -1.0 if mast == "main" else 1.0)
        return self

    def mast_sheave(self, bid, P, circ, rs):
        """a sheave let into a mast fore and aft (its pin athwartships) at the ship point P: no block drawn"""
        b = self.add_block(bid, 1, circ, fixed=("ship", np.asarray(P, float), np.array([0.0, 0.0, -1.0]), EY))
        b.rs = rs
        b.hidden = True
        b.touch = 0.35 + 4.0 * rope_r(circ)                     # the rope lies in the mast's sheave hole
        return b

    def top_aft_box(self, mast):
        """just abaft the top's after rim: a bull's eye seized to it; the halyards from the mastheads come down abaft the
        topmast head and through it, then down to the fife rail's after bar (lower mast frame)"""
        m = self.mg[mast].m
        k = m["Bt"] / 5.029
        return ((m["fa"] - 0.32 * k, m["fa"] - 0.12 * k), (0.25 * k, 0.6 * k),
                (m["s_plat"] - 0.25 * k, m["s_plat"] + 0.03 * k))

    def upper_halyards(self, mast, grp, rails):
        """the topgallant's and royal's halyards: bent to the yard's slings, up the mast's fore side to a sheave in the
        masthead just over the yard hoisted, down abaft the topmast head and the top (the topgallant's to starboard, the
        royal's to port), through a bull's eye at the top's after rim, down to the fife rail's after bar"""
        MG = self.mg[mast]
        m = MG.m
        Mn = mast.capitalize()
        for k, s_sh, sg in ((2, m["s_stop"] - 0.12, 1.0), (3, m["s_pole"] - 0.2, -1.0)):
            yn = self.yard_of(mast, k)
            Y = self.yg[yn]
            g = SQUARE_LEVELS[k]
            c = self.circ(mast, g, "halyard")
            R_m = float(m["R_tg"](s_sh))
            P_sh = MG.tg(0.0, 0.0, s_sh)
            sh = self.mast_sheave(f"{Mn}{g}HalyardSheave", P_sh, c, 0.75 * R_m)
            ln = self.new_line(f"{mast} {g} halyard", grp, c)
            R0 = Y.R(0.0)
            e = Y.at(0.0, -0.95 * R0, 0.3 * R0)
            tail = [self.fair(mast, sg, self.top_aft_box(mast)), self.pin_station(mast, sg, [f"fife_{mast}"])]
            for S in STATES:
                P_t = P_sh + MG.f * (0.75 * R_m + rope_r(c))   # the fore leg leaves the sheave about here
                sts = [self.ends(yn, self.bunt_exit(self.sail_of(mast, k), yn, S, P_t, e, rope_r(c))),
                       self.sheave(sh.bid)] + tail
                sp = [None] * (len(sts) - 1)
                sp[0] = ("drape", self.drape_mast(mast, "tg", rope_r(c)))      # lowered, it lies down the mast's face
                ln.set(S, sts, sp)

    def bunt_exit(self, key, yn, S, P_from, e, r):
        """furled, a tie bent round the slings comes out through the bunt on the yard's top: where the straight line
        from P_from (ship) to the bend e (yard frame) first meets the furled cloth, a rope's radius out (yard frame);
        e itself in the other states, or where the line misses the cloth"""
        if S != "Furled" or key is None:
            return np.asarray(e, float)
        from mathutils import Vector
        o, R = Pose(self.rig, S).frame(yn)
        A = (np.asarray(P_from, float) - o) @ R
        e = np.asarray(e, float)
        dv = e - A
        L = float(np.linalg.norm(dv))
        u = dv / L
        a1 = unit(np.cross(u, EZ if abs(u[2]) < 0.9 else EX))
        a2 = np.cross(u, a1)
        d = r + self.cfg["check"]["gap_in"] * IN + 0.004
        bvh = self.cloth_bvh(key, S)
        t_hit = None
        for off in (np.zeros(3), a1 * d, -a1 * d, a2 * d, -a2 * d):
            loc, nrm, idx, dist = bvh.ray_cast(Vector(tuple(map(float, A + off))), Vector(tuple(map(float, u))), L)
            if loc is not None and (t_hit is None or dist < t_hit):
                t_hit = dist
        if t_hit is None:
            return e
        return A + u * max(t_hit - 0.01, 0.0)

    def halyard_deck_x(self, mast):
        """where a topsail halyard's standing block is hooked in the deck: the middle of the pier between two spar deck
        ports nearest the channel's after end (abaft the backstays)"""
        d = self.deck
        xa = d.channels[mast][0]
        runs = [r_ for r_ in d.free_runs(xa - 4.0, xa + 3.0, 0.3) if r_[1] - r_[0] > 0.8]
        return float(min((0.5 * (a_ + b_) for a_, b_ in runs), key=lambda x: abs(x - (xa + 0.5))))

    def rail_at(self, x, kind="bulwark"):
        """the pin rail (its zone's stem) along the side at x"""
        for name, rl in self.rails.rails.items():
            if rl.get("kind") == kind and rl["x"][0] - 0.05 <= x <= rl["x"][1] + 0.05:
                return name
        return None

    def topsail_halyard(self, mast, grp, sg):
        """the topsail's tye and halyard: the tye bent round the yard's slings, up the topmast's fore side through a
        sheave in the topmast under its hounds, down abaft it to the fly block (double) spliced into its end; the
        halyard rove four-fold between it and a double block hooked to an eyebolt in the deck by the side sg (between
        the guns, abaft the backstays), its fall to the rail over the block. Hoisted, the fly block hangs a third of the
        way down; lowered, close under the masthead"""
        MG = self.mg[mast]
        m = MG.m
        Mn = mast.capitalize()
        k = m["hs_tm"] / 0.199
        yn = self.yard_of(mast, 1)
        Y = self.yg[yn]
        c_t = self.circ(mast, "topsail", "tye")
        c_h = self.circ(mast, "topsail", "halyard")
        r_t = rope_r(c_t)
        s_sh = m["s_tmh"] - 0.5 * k
        R_m = float(m["R_tm"](s_sh))
        P_sh = MG.tm(0.0, 0.0, s_sh)
        sh = self.mast_sheave(f"{Mn}TopsailTyeSheave", P_sh, c_t, 0.75 * R_m)
        d = self.deck
        x_e = self.halyard_deck_x(mast)
        z_d = d.z(x_e)
        pi, _ = d.surf(x_e, z_d + 0.5, d.BUL)
        E = np.array([x_e, sg * (abs(pi[1]) - 1.0 * k), z_d + 0.02])      # its fall rises to the rail over it
        std = self.add_block(f"{Mn}TopsailHalyardStanding", 2, c_h, attach=("ship", E), pendant=0.0, group=grp)
        std.hook = True                                         # hooked to the eyebolt
        R0 = Y.R(0.0)
        e_y = Y.at(0.0, -0.95 * R0, 0.3 * R0)                   # the tye round the slings, up their after side (clear
        #                                                         of the bunt furled on the yard's top)
        P_t = P_sh + MG.f * (0.75 * R_m + r_t)                  # its fore leg leaves the sheave about here
        e_by = {S: self.bunt_exit(self.sail_of(mast, 1), yn, S, P_t, e_y, r_t) for S in STATES}
        up = {S: float(np.linalg.norm(Pose(self.rig, S).world(yn, e_by[S]) - P_t)) for S in STATES}
        D_f = 1.2 * k                                           # lowered, the fly block's eye this far from the sheave
        P_a = P_sh - MG.f * (0.75 * R_m + r_t)                  # the tye's after leg leaves the sheave here
        fly = self.add_block(f"{Mn}TopsailFly", 2, c_h, attach=("ship", P_a), pendant=D_f, group=grp,
                             hint=("ship", EY))
        fly.pendant_by = {S: D_f + up["Furled"] - up[S] for S in STATES}
        fly.pendant_drawn = False                               # the tye is its pendant
        tye = self.new_line(f"{mast} topsail tye", grp, c_t)
        for S in STATES:
            tye.set(S, [self.ends(yn, e_by[S]), self.sheave(sh.bid), {"k": "end", "b": fly.bid, "eye": True}],
                    [("drape", self.drape_mast(mast, "tm", r_t)), None])
        hal = self.new_line(f"{mast} topsail halyard", grp, c_h)
        pin = self.pin_station(mast, sg, [self.rail_at(x_e)])
        for S in STATES:
            hal.set(S, [{"k": "end", "b": std.bid}, self.sheave(fly.bid, 0), self.sheave(std.bid, 0),
                        self.sheave(fly.bid, 1), self.sheave(std.bid, 1), pin])

    def side_hole(self, x, z, sg, proud=0.025):
        """a rope's way in through the ship's side at x, height z: a sheave just outside the skin (proud: how far its
        rope's bed stands out from it), and the hole's inboard end just inside the bulwark (ship points, side sg)"""
        d = self.deck
        po, _ = d.surf(x, z, d.OUT)
        pi, _ = d.surf(x, z, d.BUL)
        return (np.array([x, sg * (po[1] + proud), po[2]]), np.array([x, sg * (pi[1] - 0.03), pi[2]]))

    def hole(self, x, z, sg, fit="side_sheave", proud=0.025):
        """the two stations of a rope's way in through the side: the sheave outside and the hole's inboard end; the
        rope lies in the hole between them, so it may touch the side anywhere along it"""
        Sv, Sh = self.side_hole(x, z, sg, proud)
        t = 0.5 * float(np.linalg.norm(Sv - Sh)) + 0.06
        return ({"k": "thru", "at": ("ship", Sv), "r": 0.0, "fit": fit, "touch": t},
                {"k": "thru", "at": ("ship", Sh), "r": 0.0, "fit": None, "touch": t})

    def kevel(self, name, x, z, sg, r):
        """a kevel (a horned oak cleat bolted inside the bulwark) at x, height z, side sg: a heavy rope from a hole in
        the side belays to it; its belaying point a rope's radius off the kevel's inboard face"""
        p, n = self.deck.inboard(x, z)
        f = np.array([1.0, sg, 1.0])
        self.kevels.append((name, p * f, n * f))
        return {"k": "kevel", "at": ("ship", (p + n * (KEVEL_T + r)) * f), "name": name}

    def foot_point(self, key, S, share, sg):
        """where a buntline is bent to the foot (yard frame): share of the half foot from the middle; set, the foot's
        lowest point there (on its fore side); clewed, hauled up under the yard; furled, the roll's fore underside"""
        inf = self.sv.info[key]
        q = float(inf["clew_block_local_m"][1])
        if S == "Set":
            y = sg * share * abs(float(inf["clew_local_m"][1]))
            return self.foot_set(key, y) + np.array([0.03, 0.0, 0.0])
        y = sg * share * q
        if S == "Clewed":
            V = self.sailV(key, "Clewed")
            sel = np.abs(V[:, 1] - y) < 0.06
            P = V[sel]
            return P[np.argmin(P[:, 2])] + np.array([0.03, 0.0, 0.0])
        c, r = self.roll_at(key, y)
        return c + np.array([0.6, 0.0, -0.75]) * r

    def bunt_end(self, yn, key, S, share, sg):
        """a buntline's end, bent to the foot (foot_point): clewed up, it is in the bunt, the cloth gathered round it
        within in_cloth_m"""
        e = self.ends(yn, self.foot_point(key, S, share, sg))
        if S == "Clewed":
            e["touch"] = self.cfg["check"]["in_cloth_m"]
        return e

    def course_gear(self, mast, sg, tag, side, grp, rails):
        """the course's clew garnets (in along the yard to the quarter block, down to the rail round the mast), sheets
        (aft to the side at the quarterdeck's break), tacks (forward to the chesstree) and buntlines (up the sail's fore
        side to blocks under the top's fore part, aft under the top and down abaft the yard)"""
        MG = self.mg[mast]
        m = MG.m
        Mn = mast.capitalize()
        key = self.sail_of(mast, 0)
        yn = self.yard_of(mast, 0)
        Y = self.yg[yn]
        inf = self.sv.info[key]
        sl = self.cfg["slack"]
        d = self.deck
        # -- the clew garnet: as a clewline, its block under the yard's fore side over the clew clewed up
        c = self.circ(mast, "course", "clew_garnet")
        yc = sg * inf["clew_block_local_m"][1]
        cat = Y.at(yc, 0.8 * Y.R(yc), -0.6 * Y.R(yc))
        cg = self.add_block(f"{Mn}CourseClewGarnet{tag}", 1, c, attach=(yn, cat), pendant=0.06, group=grp)
        cg.rests_on = {"Clewed": self.sail_obj(key, "Clewed")}
        cg.touch_by = {"Clewed": self.cfg["check"]["in_cloth_m"]}
        soft = {"Clewed": {self.sail_obj(key, "Clewed"): self.cfg["check"]["cloth_give_m"]}}
        q = f"{Mn}courseQuarter{tag}"
        qp = self.blocks[q].fixed[1]
        # furled, the clew is two-blocked at the block's tail, the block hanging from the yard: the clew garnet comes
        # up from the clew into the block and in along the yard (the sheet block and the tack hang from the clew)
        C_f = cat - np.array([0.0, 0.0, 0.02 + cg.eye_drop])
        cg.fixed_by = {"Furled": (yn, C_f, np.array([0.0, 0.0, -1.0]),
                                  unit(np.cross(np.array([0.0, 0.0, -1.0]), unit(np.asarray(qp, float) - C_f))))}
        tail_f = C_f - np.array([0.0, 0.0, cg.L / 2])
        ln = self.new_line(f"{mast} course clew garnet {side}", grp, c)
        ln.soft = soft                                          # along the yard over the bags of cloth clewed up
        pin = self.pin_station(mast, sg, rails["near"])
        for S in STATES:
            sp = [None, ("drape", self.drape_yard(yn, S, rope_r(c), fade=(0.1, 0.4))), None]
            e = {"k": "end", "b": cg.bid} if S == "Furled" else self.ends(yn, self.clew_end(key, S, sg, cat))
            ln.set(S, [e, self.sheave(cg.bid), self.sheave(q, 1), pin], sp)
        # -- the clew in each state (yard frame): set, clewed up under the clew garnet block, furled two-blocked to it
        clew = {S: self.clew(key, S, sg) for S in ("Set", "Clewed")}
        clew["Furled"] = tail_f
        # -- the sheet: standing part at an eyebolt in the side at the quarterdeck's break, through the sheet block at
        # the clew, in through a sheave in the side just forward of it, belayed to the rail inside
        c = self.circ(mast, "course", "sheet")
        cq = self.cfg["course"][mast]
        if mast == "main":
            xb = d.e0                                           # the quarterdeck's break
            x_e, x_s = xb - 0.42, xb - 0.12
        else:                                                   # under the clew, forward of the fore channel
            xc_ = float(Pose(self.rig, "Set").world(yn, clew["Set"])[0])
            x_e, x_s = xc_ + cq["sheet_eyebolt_dx"], xc_ + cq["sheet_hole_dx"]
            xb = x_s
        z0 = d.z(xb)
        po, _ = d.surf(x_e, z0 + 0.38, d.OUT)
        E = np.array([x_e, sg * (po[1] + 0.02), po[2]])
        th1, th2 = self.hole(x_s, z0 + 0.32, sg)
        sb = self.add_block(f"{Mn}CourseSheet{tag}", 1, c, attach=(yn, clew["Set"] + np.array([-0.05, 0.0, -0.04])),
                            group=grp, hint=(yn, EX))
        sb.attach_by = {S: (yn, clew[S] + np.array([-0.05, 0.0, -0.04])) for S in ("Clewed", "Furled")}
        sb.rests_on = {"Clewed": self.sail_obj(key, "Clewed")}
        ln = self.new_line(f"{mast} course sheet {side}", grp, c)
        sheet_x = 2.0 * rope_r(c) + self.cfg["check"]["gap_in"] * IN + 0.01    # the hauling part before the standing
        kv = self.kevel(f"{Mn}CourseSheet{tag}", x_s + cq["sheet_kevel_dx"], z0 + 0.32, sg, rope_r(c))
        eb = (np.array([x_e, sg * po[1], po[2]]), np.array([0.0, sg, 0.0]))     # its eyebolt in the side
        for S in STATES:
            sts = [dict(self.ends("ship", E), eyebolt=eb), self.sheave(sb.bid), th1, th2, kv]
            sp = [None] * (len(sts) - 1)
            if S == "Clewed":                                    # overhauled: the legs hang in bights over the bags
                sp[0] = ("drape", self.drape_front(key, S, yn, rope_r(c), sl["clewed_sheet"]))   # standing part, and
                sp[1] = ("drape", self.drape_front(key, S, yn, rope_r(c), sl["clewed_sheet"], extra=sheet_x))  # hauling
            elif S == "Furled":
                sp[0] = sp[1] = ("slack", sl["clewed_sheet"])
            ln.set(S, sts, sp)
        # -- the tack: forward to the chesstree's sheave on the topside, in to the gangway's rail
        c = self.circ(mast, "course", "tack")
        x_c = xb + cq["tack_dx"]
        z_c = d.z(x_c) + cq["tack_over_deck"]
        th1, th2 = self.hole(x_c, z_c, sg, "chesstree", cq["chesstree_proud"])
        ln = self.new_line(f"{mast} course tack {side}", grp, c)
        kv = self.kevel(f"{Mn}CourseTack{tag}", x_c + cq["tack_kevel_dx"], z_c, sg, rope_r(c))
        for S in STATES:
            # clewed up or furled, the tack is bent to the clew forward of the sheet block, and hangs before the
            # sheet's bights over the clewed sail
            e = self.ends(yn, clew[S] + np.array([0.22 if S != "Set" else cq["tack_clew_dx"], 0.0, -0.03]))
            sts = [e, th1, th2, kv]
            sp = [None] * (len(sts) - 1)
            if S == "Clewed":
                sp[0] = ("drape", self.drape_front(key, S, yn, rope_r(c), sl["clewed_sheet"], extra=0.09 + sheet_x))
            elif S == "Furled":
                sp[0] = ("slack", sl["clewed_sheet"])
            ln.set(S, sts, sp)
        # -- buntlines: up the sail's fore side to blocks under the top's fore part, the falls aft under the top
        c = self.circ(mast, "course", "buntline")
        k_ = m["Bt"] / 5.029
        for i, share in enumerate(self.sv.sp["square"]["clewed"]["buntlines"]["course"]):
            P_b = MG.lo(m["ff"] - 0.55 * k_, sg * (0.85 + 0.4 * i) * k_, m["s_ct1"])
            bb = self.add_block(f"{Mn}CourseBunt{i}{tag}", 1, c, attach=("ship", P_b), pendant=0.33 * k_, group=grp)
            ln = self.new_line(f"{mast} course buntline {i + 1} {side}", grp, c)
            tail = self.falls(mast, sg, "bunt")
            for S in STATES:
                sts = [self.bunt_end(yn, key, S, share, sg), self.sheave(bb.bid)] + tail
                sp = [None] * (len(sts) - 1)
                sp[0] = ("drape", self.drape_front(key, S, yn, rope_r(c), 0.0))
                ln.set(S, sts, sp)

    def course_braces(self, mast, sg, tag, side, grp):
        """the main yard's braces: a pendant from the yardarm with a single block; the standing part at an eyebolt in
        the quarter, through the pendant's block, back in through a sheave in the side just abaft it, belayed to the
        pin under it (a pin set aside for it)"""
        Mn = mast.capitalize()
        yn = self.yard_of(mast, 0)
        Y = self.yg[yn]
        ap = self.arm_places(mast, 0)
        d = self.deck
        q = self.cfg["brace"]["course"]
        c = self.circ(mast, "course", "brace")
        zone = "qd0" + ("s" if sg > 0 else "p")
        ln = self.new_line(f"{mast} course brace {side}", grp, c)
        pid = self.reserve_pin(zone, q["pin_x"], ln.name)
        P = self.pins.pins[pid]["p"]
        x_h = P[0] - q["hole_aft"]
        z_h = d.z(x_h) + q["hole_over_deck"]
        th1, th2 = self.hole(x_h, z_h, sg)
        x_e = x_h + q["eyebolt_fwd"]
        po, _ = d.surf(x_e, z_h, d.OUT)
        E = np.array([x_e, sg * (po[1] + 0.02), po[2]])
        y_a = ap["brace"]
        A = Y.at(sg * y_a, -0.9 * Y.R(y_a), 0.0)
        pb = self.add_block(f"{Mn}CourseBrace{tag}", 1, c, attach=(yn, A), pendant=q["pendant_ft"] * FT, group=grp,
                            hint=("ship", EZ))
        pin = {"k": "pin", "pin": pid, "side": sg}
        eb = (np.array([x_e, sg * po[1], po[2]]), np.array([0.0, sg, 0.0]))     # its eyebolt in the quarter
        for S in STATES:
            ln.set(S, [dict(self.ends("ship", E), eyebolt=eb), self.sheave(pb.bid), th1, th2, pin])

    def standing_rope(self, kind, mast, sg, which):
        """a standing rope as (upper end, lower end, radius), ship: a mast's lower shroud on side sg (which: its place
        from forward, -1 the aftmost), or a stay by its name"""
        if kind == "shroud":
            a, b, r = self.st.shroud_lines[(mast, "lower", 1)][which][:3]
            f = np.array([1.0, sg, 1.0])
            return np.asarray(a, float) * f, np.asarray(b, float) * f, float(r)
        for nm, a, b, r in self.st.spans:
            if nm == which:
                return np.asarray(a, float), np.asarray(b, float), float(r)
        raise KeyError(which)

    @staticmethod
    def on_rope(rope, i, v, toward, out):
        """the point on a standing rope's axis where its coordinate i (0: ship x, 2: height) is v, moved out from the
        axis by out toward the direction toward (made square to the rope)"""
        a, b, r = rope
        t = (v - a[i]) / (b[i] - a[i])
        P = a + t * (b - a)
        ax = unit(b - a)
        w = np.asarray(toward, float)
        w = w - (w @ ax) * ax
        return P + unit(w) * out

    def brace_gear(self, mast, sg, tag, side, grp):
        """the braces of every yard but the main yard's (course_braces): a pendant from the yardarm with a single block
        (the royals: a single brace, its eye round the yardarm), the standing part and a lead block on the next mast's
        standing rigging (or the main top's after rail), the fall down to the rails (running_1797.json's brace leads)"""
        q = self.cfg["brace"]
        leads = q["leads"][mast]
        Mn = mast.capitalize()
        for k in range(4):
            spec = leads.get(str(k))
            yn = self.yard_of(mast, k)
            if spec is None or yn not in self.yg:
                continue
            Y = self.yg[yn]
            g = self.group_of(mast, k)
            G = g.capitalize()
            ap = self.arm_places(mast, k)
            c = self.circ(mast, g, "brace")
            r = rope_r(c)
            r_st = rope_r(c * self.cfg["block"]["strop_of_rope"])
            pend = q["pendant_ft"][g] * FT
            y_a = ap["brace"]
            o, Rm = Pose(self.rig, "Set").frame(yn)
            arm_w = o + Y.at(sg * y_a, 0.0, 0.0) @ Rm.T            # the yardarm, braced square, hoisted
            kind = spec[0]
            opt = spec[-1] if isinstance(spec[-1], dict) else {}
            through = None
            if kind == "shroud":
                rope = self.standing_rope("shroud", spec[1], sg, spec[2])
                z = spec[3]
                if "toward" in opt:                             # the strop's side of the shroud (ship, y mirrored)
                    toward = np.array(opt["toward"], float) * np.array([1.0, sg, 1.0])
                else:                                           # toward the yardarm
                    P0 = self.on_rope(rope, 2, z, arm_w - self.on_rope(rope, 2, z, EX, 0.0), rope[2] + r_st)
                    toward = unit(arm_w - P0)
                P = self.on_rope(rope, 2, z, toward, rope[2] + r_st + opt.get("off_m", q["lead_off_m"]))
                Ps = self.on_rope(rope, 2, z + q["standing_m"], toward, rope[2] + r)
                pend_lead = q["lead_pendant_m"]
                if opt.get("between", True):                    # the fall comes in between two shrouds
                    through = {f"Ladder_{spec[1]}_lower_{'s' if sg > 0 else 'p'}"}
            elif kind == "stay" or kind == "tg_stay":
                nm = "main topgallant stay" if kind == "tg_stay" else ("main stay" if sg > 0 else "main preventer stay")
                rope = self.standing_rope("stay", None, sg, nm)
                x = spec[1]
                toward = np.array([0.0, sg, -0.5])
                P = self.on_rope(rope, 0, x, toward, rope[2] + r_st)
                Ps = self.on_rope(rope, 0, x + q["standing_m"], np.array([0.0, sg, 0.0]), rope[2] + r)
                pend_lead = q["lead_pendant_m"]
            else:                                               # the main top's after rail
                TM = self.mg[spec[1]]
                m = TM.m
                s_cap = m["s_plat"] + self.rig.fit["top_rail_ft"] * FT + 1.5 * IN
                P = TM.lo(m["fa"] - r_st - 0.01, sg * spec[2], s_cap)
                Ps = TM.lo(m["fa"] - r - 0.01, sg * (spec[2] + 0.22), s_cap)
                pend_lead = 0.06
            fwd = 1.0 if (P[0] > arm_w[0]) else -1.0             # the lead is forward of the yard
            R_a = Y.R(y_a)
            lead = self.add_block(f"{Mn}{G}BraceLead{tag}", 1, c, attach=("ship", P), pendant=pend_lead, group=grp)
            ln = self.new_line(f"{mast} {g} brace {side}", grp, c)
            if through:                                         # its fall comes in between two shrouds
                ln.through = through
            pin = self.pin_station(mast, sg, opt.get("rails", leads["rails"]))
            if pend > 0:
                pb = self.add_block(f"{Mn}{G}Brace{tag}", 1, c, attach=(yn, Y.at(sg * y_a, fwd * 0.9 * R_a, 0.0)),
                                    pendant=pend, group=grp, hint=("ship", EZ))
                sts = [self.ends("ship", Ps), self.sheave(pb.bid), self.sheave(lead.bid), pin]
            else:
                sts = [self.ends(yn, Y.at(sg * y_a, fwd * (R_a + r), 0.0)), self.sheave(lead.bid), pin]
            for S in STATES:
                ln.set(S, sts)

    def tsb_box(self, mast, part=None, ro=0.0):
        """under the topmast's trestletree beside its head, forward of the cheek and abaft the falls coming down the
        cap's throat: a bull's eye the topsail buntlines' falls come aft to from their blocks and turn down through,
        inside the topmast shrouds, low enough that the fall from the block slopes down under the trestletree's edge
        (lower mast frame). part 1: its fore half (the inner block's fall), 0: its after half (the outer block's,
        which then passes abaft the inner one's). ro: the eye's outer radius, to stand clear of the cheek"""
        m = self.mg[mast].m
        k = m["hs_tm"] / 0.199
        o, h, b = m["off_tm"], m["hs_tm"], m["hs_tm"] + m["tt2_b"]
        x_ch = o + 0.5 * self.rig.fit["cheek"]["broad"] * m["D_tm"]   # the cheek's fore end
        x0 = max(o + 0.84 * h, x_ch + ro + 0.008)                       # the eye clear of it
        x1 = max(o + 1.06 * h, x0 + 2.2 * ro + 0.016)                   # and room for the pair
        if part is not None:
            xm = 0.5 * (x0 + x1)
            x0, x1 = ((x0, xm - 0.004) if part == 0 else (xm + 0.004, x1))
        return ((x0, x1), (b - 0.07 * k, b - 0.005 * k), (m["s_tt2a"] - 0.3 * k, m["s_tt2a"] - 0.16 * k))

    def topsail_buntlines(self, mast, sg, tag, side, grp):
        """the topsail's buntlines, two a side: bent to the foot, up the sail's fore side and over the yard to a block
        under the topmast's middle crosstree; the fall aft under the trestletrees through a bull's eye, down inside the
        topmast shrouds, outside the lower cap and through the lubber's hole to the rails abaft the mast"""
        MG = self.mg[mast]
        m = MG.m
        Mn = mast.capitalize()
        k_ = m["hs_tm"] / 0.199
        key = self.sail_of(mast, 1)
        yn = self.yard_of(mast, 1)
        c = self.circ(mast, "topsail", "buntline")
        low, _ = self.caps(mast)
        ymin = low[2] + 0.15 * k_
        for i, share in enumerate(self.sv.sp["square"]["clewed"]["buntlines"]["topsail"]):
            y_b = m["hs_tm"] + m["tt2_b"] + (0.11 + 0.22 * i) * k_
            P_b = MG.tm(m["ct2_xs"][1], sg * y_b, m["s_tt2b"] - 0.01)
            bb = self.add_block(f"{Mn}TopsailBunt{i}{tag}", 1, c, attach=("ship", P_b), pendant=0.04, group=grp)
            ln = self.new_line(f"{mast} topsail buntline {i + 1} {side}", grp, c)
            tail = [self.fair(mast, sg, self.tsb_box(mast, part=1 - i, ro=eye_outer("bullseye", rope_r(c))))] + \
                ([self.top_pin(mast, sg)] if self.in_top(mast) else self.falls(mast, sg, "ubunt", ymin))
            for S in STATES:
                sts = [self.bunt_end(yn, key, S, share, sg), self.sheave(bb.bid)] + tail
                sp = [None] * (len(sts) - 1)
                sp[0] = ("drape", self.chain(self.drape_front(key, S, yn, rope_r(c), 0.0),
                                             self.drape_over(yn, S, rope_r(c), key)))
                ln.set(S, sts, sp)

    def _sheets_clewlines(self, mast, sg, tag, side, grp, rails):
        MG = self.mg[mast]
        Mn = mast.capitalize()
        sl = self.cfg["slack"]
        sheets = []
        for k in range(0, 3):
            above = self.sail_of(mast, k + 1)
            yn = self.yard_of(mast, k)
            Y = self.yg[yn]
            ap = self.arm_places(mast, k)
            g_above = SQUARE_LEVELS[k + 1]
            c = self.circ(mast, g_above, "sheet")
            # the sheave in the yardarm (pin fore and aft) and the quarter block under the slings
            y_sh = sg * ap["sheave"]
            r_sheet = rope_r(c)
            rs = Y.R(ap["sheave"]) - 0.7 * r_sheet
            arm = self.hidden_sheave(f"{Mn}{g_above}SheetArm{tag}", yn, Y.at(y_sh), EX, rs, c)
            arm.touch = max(0.3, ap["sheave"] - Y.cleat_y + 0.1)
            nq = 1 if (k == 0 and mast == "mizzen") else 2
            q = self.quarter_block(mast, k, sg, f"{Mn}{SQUARE_LEVELS[k]}Quarter{tag}", nq, c, ap["sheave"], rs,
                                   r_sheet, grp)
            ln = self.new_line(f"{mast} {g_above} sheet {side}", grp, c)
            tail = [self.pin_station(mast, sg, rails["near"])] if k == 0 else \
                [self.fair(mast, sg, self.cap_side_box(mast, part=0))] + self.falls(mast, sg, "mid") if k == 1 else \
                [self.cap_thimble(mast, sg, part=0)] + self.falls(mast, sg, "far")
            sheets.append((k, above, g_above, ln, arm, q, tail, c))
        for k in range(1, 4):
            key = self.sail_of(mast, k)
            yn = self.yard_of(mast, k)
            Y = self.yg[yn]
            g = SQUARE_LEVELS[k]
            c = self.circ(mast, g, "clewline")
            inf = self.sv.info[key]
            yc = sg * inf["clew_block_local_m"][1]
            # the clewline block under the yard's fore side, over the clew clewed up; furled, it hangs straight down
            # with the clew two-blocked at its tail (the sheet hangs from there)
            cat = Y.at(yc, 0.55 * Y.R(yc), -0.84 * Y.R(yc))
            cb = self.add_block(f"{Mn}{g}Clewline{tag}", 1, c, attach=(yn, cat), pendant=0.02, group=grp)
            cb.rests_on = {"Clewed": self.sail_obj(key, "Clewed")}       # the clew two-blocked: the cloth round it
            cb.touch_by = {"Clewed": self.cfg["check"]["in_cloth_m"]}
            if k < 3:
                q, qi = f"{Mn}{g}Quarter{tag}", 1
                qp = self.blocks[q].fixed[1]
            else:
                # a lead block lashed under the royal yard abaft it, outside the parrel
                yq = MG.m["D_tg"] / 2 * 0.8 + 0.22 + 0.16
                L = self.block_L(c)
                qp = Y.at(sg * yq, -(Y.R(yq) + 0.07), -(Y.R(yq) + 0.5 * L + 0.06))
                self.add_block(f"{Mn}{g}Quarter{tag}", 1, c, fixed=(yn, qp, np.array([0.0, 0.0, -1.0]), EX), group=grp)
                q, qi = f"{Mn}{g}Quarter{tag}", 0
            C_f = cat - np.array([0.0, 0.0, 0.02 + cb.eye_drop])
            n_f = unit(np.cross(np.array([0.0, 0.0, -1.0]), unit(np.asarray(qp, float) - C_f)))
            cb.fixed_by = {"Furled": (yn, C_f, np.array([0.0, 0.0, -1.0]), n_f)}
            ln = self.new_line(f"{mast} {g} clewline {side}", grp, c)
            ln.soft = {"Clewed": {self.sail_obj(key, "Clewed"): self.cfg["check"]["cloth_give_m"]}}
            tail = [self.fair(mast, sg, self.cap_side_box(mast, part=1))] + self.falls(mast, sg, "mid") if k == 1 else \
                [self.cap_thimble(mast, sg, part=1)] + self.falls(mast, sg, "far") if k == 2 else \
                [self.aft_thimble(mast, sg), self.top_pin(mast, sg)] if self.in_top(mast) else \
                [self.aft_thimble(mast, sg)] + self.falls(mast, sg, "near", self.aft_ymin(mast))
            for S in STATES:
                e = {"k": "end", "b": cb.bid} if S == "Furled" else self.ends(yn, self.clew_end(key, S, sg, cat))
                sts = [e, self.sheave(cb.bid), self.sheave(q, qi)] + tail
                sp = [None] * (len(sts) - 1)
                sp[1] = ("drape", self.drape_yard(yn, S, rope_r(c), fade=(0.1, 0.4)))
                ln.set(S, sts, sp)
        for k, above, g_above, ln, arm, q, tail, c in sheets:
            cbid = f"{Mn}{g_above}Clewline{tag}"
            for S in STATES:
                # furled, the clew is hauled close up to its clewline block: the sheet hangs from under the block
                e = {"k": "end", "b": cbid} if S == "Furled" else \
                    self.ends(self.yard_of(mast, k + 1), self.clew(above, S, sg))
                sts = [e, self.sheave(arm.bid), self.sheave(q.bid, 0)] + tail
                sp = [None] * (len(sts) - 1)
                if S == "Clewed":
                    sp[0] = ("drape", self.drape_front(above, S, self.yard_of(mast, k + 1), rope_r(c),
                                                       sl["clewed_sheet"]))
                sp[1] = ("drape", self.drape_yard(self.yard_of(mast, k), S, rope_r(c)))   # along the yard's underside
                ln.set(S, sts, sp)

    def quarter_block(self, mast, k, sg, bid, nq, circ, y_arm, rs_arm, r, grp):
        """the quarter block for the sheet of the sail above (and its clewline): lashed under the yard just outside the
        slings (outside the parrel on an upper yard, the slings' cleats on a lower one), its pin fore and aft, close
        under the yard: the sheet lies along the yard's underside from the yardarm's sheave in"""
        yn = self.yard_of(mast, k)
        Y = self.yg[yn]
        gap = self.cfg["check"]["gap_in"] * IN
        m = self.mg[mast].m
        L = self.block_L(circ)
        w, t, rs_q, _ = block_dims(L, nq)
        if k == 0:
            yq = 0.45 * Y.half / 6.0 + 0.35
        else:
            # outside the parrel, and clear of the cap the yard comes down onto when it is lowered
            Rm = (m["D_tm"] if k == 1 else m["D_tg"]) / 2
            low, top = self.caps(mast)
            yq = max(Rm + 0.22 + 0.04 * k, (low if k == 1 else top)[2] + 0.5 * w + 0.03)
        # the sheet comes in along the yard's underside (drape_yard) over the sheave's top: the block just under the
        # robands, its crown close under the yard
        lim = -(Y.R(yq) + ROBAND + r + gap + 0.004)
        zc = min(lim - rs_q - r - 0.003, -(Y.R(yq) + 0.5 * L + 0.02))
        b = self.add_block(bid, nq, circ, fixed=(yn, Y.at(sg * yq, 0.0, zc), np.array([0.0, 0.0, -1.0]), EX),
                           group=grp)
        rim = self.head_rim(self.sail_of(mast, k), yn)
        rho = max([Y.R(sg * yq) + 0.004] + [rim(sg * yq, a_) for a_ in range(-180, 180, 10)]) + b.r_strop
        b.ring = (yn, np.array([Y.x_off, sg * yq, 0.0]), EY, rho)      # its strop round the yard
        return b

    # -- the fore-and-aft sails' gear ------------------------------------------------------------------------------------
    def gear(self):
        """every line: the square sails' gear on each mast, then the fore-and-aft sails'"""
        for mast in ("main", "fore", "mizzen"):
            self.square_gear(mast)
        self.fa_gear()
        self.footropes()
        return self

    def footropes(self):
        """each yard's footropes (horses) and their stirrups (running_1797.json's footrope): a footrope from the yard's
        back just outside the quarter block (or the royal's parrel) out to the yardarm, hanging drop below the yard and
        just abaft it on stirrups seized round the yard, evenly spaced between its ends; the same in every state (they
        go with the yard)"""
        q = self.cfg["footrope"]
        lvl_of = {"course": "lower", "crossjack": "lower", "topsail": "topmast", "topgallant": "topgallant",
                  "royal": "pole"}
        for mast in ("main", "fore", "mizzen"):
            Mn = mast.capitalize()
            m = self.mg[mast].m
            for k in range(4):
                yn = self.yard_of(mast, k)
                Y = self.yg[yn]
                g = self.group_of(mast, k)
                lvl = lvl_of[g]
                cf = self.circ(mast, g, "footrope")
                rf = rope_r(cf)
                ns = int(q["stirrups"][lvl])
                cs = self.circ(mast, g, "stirrup") if ns else cf
                rs = rope_r(cs)
                drop = q["drop_ft"][lvl] * FT
                y_f = self.arm_places(mast, k)["foot"]
                qb = self.blocks.get(f"{Mn}{SQUARE_LEVELS[k]}QuarterS")
                if qb is not None:
                    y_i = abs(float(qb.fixed[1][1])) + 0.5 * qb.w + 0.12
                else:
                    y_i = float(m["R_tg"](m["s_pole"] - 0.5)) + 0.25
                cb = self.blocks.get(f"{Mn}{SQUARE_LEVELS[k]}ClewlineS")
                if k == 3 and cb is not None:                   # the royal's clewline crosses under the yard to its
                    y_i = max(y_i, abs(float(cb.attach[1][1])) + 0.5 * cb.w + 0.12)    # lead block abaft it
                if k == 1:
                    y_i = max(y_i, self.shroud_reach(mast, yn, drop) + rf + q["shroud_clear_m"])
                for sg in (1.0, -1.0):
                    side = "starboard" if sg > 0 else "port"
                    ys = [y_i + (y_f - y_i) * (j + 1) / (ns + 1) for j in range(ns)]

                    def low(y):                                 # the footrope's place under a stirrup
                        return Y.at(sg * y, -max(q["aft_in"] * IN, 0.95 * Y.R(y)), -drop)
                    E_i = Y.at(sg * y_i, -(Y.R(y_i) + rf + 0.004), -0.3 * Y.R(y_i))
                    E_o = Y.at(sg * y_f, -(Y.R(y_f) + rf + 0.004), -0.3 * Y.R(y_f))
                    sts = [self.ends(yn, E_i)]
                    sps = []
                    for y in ys:
                        sts.append({"k": "thru", "at": (yn, low(y)), "r": 0.0, "fit": None})
                        sps.append(("slack", 0.01 if len(sps) == 0 else 0.004))
                    sts.append(self.ends(yn, E_o))
                    if ns:
                        sps.append(("slack", 0.01))
                    else:                                       # one bight between its ends, drop deep
                        span = float(np.linalg.norm(E_o - E_i))
                        sps.append(("slack", 8.0 * drop ** 2 / (3.0 * span ** 2)))
                    ln = self.new_line(f"{mast} {g} footrope {side}", Mn, cf)
                    for S in STATES:
                        ln.set(S, sts, sps)
                    for j, y in enumerate(ys):
                        st = self.new_line(f"{mast} {g} stirrup {side} {j}", Mn, cs)
                        top = Y.at(sg * y, -(Y.R(y) + rs + 0.004), 0.0)
                        for S in STATES:
                            st.set(S, [self.ends(yn, top), self.ends(yn, low(y) + np.array([0.0, 0.0, rf + rs]))])

    def shroud_reach(self, mast, yn, drop):
        """how far out along the yard (m) the foremost topmast shroud comes within drop under the yard lowered onto
        the cap (furled), where the footropes hang among the topmast shrouds"""
        a, b, _ = self.st.shroud_lines[(mast, "topmast", 1)][0][:3]
        a, b = np.asarray(a, float), np.asarray(b, float)
        o, Rm = Pose(self.rig, "Furled").frame(yn)
        z0 = float((o + self.yg[yn].at(0.0, 0.0, 0.0) @ Rm.T)[2])
        out = 0.0
        for z in np.linspace(z0 - drop - 0.1, z0 + 0.1, 9):
            t = (z - a[2]) / (b[2] - a[2])
            if 0.0 <= t <= 1.0:
                out = max(out, float(((a + t * (b - a)) - o) @ Rm[:, 1]))
        return out

    def spar_at(self, name, xl):
        """a boom's or gaff's centre line point (its own frame: x along it, forward; z up the mast) and its radius at xl,
        fitted to the middle of its mesh (the jaws and the end's cleats left out)"""
        self._spar_fit = getattr(self, "_spar_fit", {})
        if name not in self._spar_fit:
            V = np.asarray(self.rig.parts_[name]["mesh"].arrays()[0], float)
            x0, x1 = float(V[:, 0].min()), float(V[:, 0].max())
            L = x1 - x0
            xs, zs, rs = [], [], []
            for a in np.linspace(x0 + 0.06 * L, x1 - 0.12 * L, 24):
                P = V[np.abs(V[:, 0] - a) < 0.02 * L]
                if len(P) >= 6:
                    xs.append(a)
                    zs.append(0.5 * (P[:, 2].max() + P[:, 2].min()))
                    rs.append(0.5 * (P[:, 1].max() - P[:, 1].min()))
            self._spar_fit[name] = (x0, x1, np.polyfit(xs, zs, 1), np.polyfit(xs, rs, 1))
        x0, x1, kz, kr = self._spar_fit[name]
        return np.array([xl, 0.0, float(np.polyval(kz, xl))]), float(np.polyval(kr, xl))

    def spar_ends(self, name):
        """a boom's or gaff's outer end and jaws (x along it, its own frame)"""
        self.spar_at(name, 0.0)
        return self._spar_fit[name][:2]

    def fa_head(self, key, S):
        """where a staysail's halyard is bent to its head (ship): set, the head; hauled down or stowed, the head on top
        of the heap along the stay's foot (sails.py's hauled-down heap, stowed 0.85 of it)"""
        inf = self.sv.info[key]
        H0, T0 = np.asarray(inf["head_m"], float), np.asarray(inf["tack_m"], float)
        a, b, r_st = self.sv.stays[inf["stay"]]
        u = unit(np.asarray(a, float) - np.asarray(b, float))
        hang = unit(-EZ - (-EZ @ u) * u)                        # the head's cringle hangs under the stay
        if S == "Set":
            return H0 + hang * (r_st + 0.05)
        L = self.sv.sp["fore_and_aft"]["hauled_down"]["share_of_luff"] * float(np.linalg.norm(H0 - T0))
        L *= 0.85 if S == "Furled" else 1.0
        return T0 + u * L + hang * (r_st + 0.05)

    def drape_side(self, key, S, frame, sg, r):
        """a span laid outside a fore-and-aft sail's cloth on the side sg of its spar's frame, where its straight line
        would pass through it (a topping lift lying against the spanker's belly, or beside the brailed-up sail): each
        point pushed out across the frame to the cloth's (or its hoops' and lacing's) outer side, the rope and the gap"""
        o, Rm = Pose(self.rig, S).frame(frame)
        clear = r + self.cfg["check"]["gap_in"] * IN + 0.02
        bvhs = [self.cloth_bvh(key, S), self.cloth_bvh(key, "Head")]
        from mathutils import Vector
        offs = [(0.0, 0.0), (r, 0.0), (-r, 0.0), (0.0, r), (0.0, -r)]

        def onp(P):
            L = (P - o) @ Rm
            need = np.full(len(L), -np.inf)
            for i, q_ in enumerate(L):
                for bvh in bvhs:
                    for dx, dz in offs:
                        loc, nrm, idx, dist = bvh.ray_cast(Vector((float(q_[0]) + dx, sg * 8.0, float(q_[2]) + dz)),
                                                           Vector((0.0, -sg, 0.0)), 16.0)
                        if loc is not None:
                            need[i] = max(need[i], sg * loc[1])
            push = np.where(np.isfinite(need), np.maximum(need + clear - sg * L[:, 1], 0.0), 0.0)
            if push.max() > 0:
                k = 3
                pp = np.array([push[max(0, i - k):i + k + 1].max() for i in range(len(push))])
                sm = np.convolve(np.pad(pp, 2, mode="edge"), np.ones(5) / 5, mode="valid")
                pp = np.maximum(sm, push)
                pp[0] = pp[-1] = 0.0
                L[:, 1] += sg * pp
            return o + L @ Rm.T
        return self._drape(onp)

    def fa_gear(self):
        """the fore-and-aft sails' gear (running_1797.json's fore_and_aft): each headsail's and staysail's lee sheet (set
        only: the sails are drawn on the port tack, the lee to starboard; hauled down, a sheet is stopped in on the
        heap), the staysail halyards whose falls come down clear of the square sails (the mizzen staysail's), then the
        spanker's and the spritsail yard's gear"""
        q = self.cfg["fore_and_aft"]
        d = self.deck
        for key, sp in q["sheets"].items():
            if key == "note":
                continue
            inf = self.sv.info[key]
            head = inf["kind"] == "headsail"
            grp = "Headsails" if head else "Staysails"
            c = self.circ(sp.get("mast"), "headsail" if head else "staysail", "sheet")
            ln = self.new_line(f"{key.replace('_', ' ')} sheet", grp, c)
            if "x" in sp:                                       # in through the bow's side to a kevel inside
                z = d.z(sp["x"]) + sp["over_deck"]
                th1, th2 = self.hole(sp["x"], z, 1.0, proud=sp["proud"])
                cam = "".join(w.capitalize() for w in key.split("_"))
                tail = [th1, th2, self.kevel(f"{cam}Sheet", sp["x"] + sp["kevel_dx"], z, 1.0, rope_r(c))]
            else:
                tail = [self.pin_station(None, 1.0, sp["rails"])]
            ln.set("Set", [self.ends("ship", np.asarray(inf["clew_m"], float))] + tail)
        for key, sp in q["halyards"].items():
            if key == "note":
                continue
            inf = self.sv.info[key]
            c = self.circ(sp.get("mast"), "staysail", "halyard")
            a, b, r_st = self.sv.stays[inf["stay"]]
            a, b = np.asarray(a, float), np.asarray(b, float)
            P = a + unit(b - a) * sp["block_down_m"]                # a block on a pendant from the stay below its eye
            cam = "".join(w.capitalize() for w in key.split("_"))
            hb = self.add_block(f"{cam}Halyard", 1, c, attach=("ship", P - EZ * (r_st + 0.01)),
                                pendant=sp["pendant_m"], group="Staysails")
            ln = self.new_line(f"{key.replace('_', ' ')} halyard", "Staysails", c)
            pin = self.pin_station(None, float(sp["side"]), sp["rails"])
            for S in STATES:
                ln.set(S, [self.ends("ship", self.fa_head(key, S)), self.sheave(hb.bid), pin])
        self.spanker_gear(q["spanker"])
        self.spritsail_gear(q["spritsail"])
        return self

    def spanker_gear(self, q):
        """the spanker's gear: the throat halyard (a tackle from under the mizzen trestletrees to the gaff's jaws), the
        peak halyard (a block on the gaff, one at the masthead, the fall down abaft the top's rim), the vangs from the
        gaff's end to the quarters, the topping lifts from the boom's end up to blocks under the top's after rim and
        down (each over the cloth where it lies against it) and the boom sheet's tackle from the boom to the taffrail"""
        MG = self.mg["mizzen"]
        m = MG.m
        grp = "Spanker"
        G, B = "SpankerGaff", "SpankerBoom"
        # -- the throat halyard
        c = self.circ(None, "spanker", "throat_halyard")
        sg = float(q["throat_side"])
        ub = self.add_block("SpankerThroatMast", 1, c,
                            attach=("ship", MG.lo(q["throat_block"][0], sg * q["throat_block"][1],
                                                  m["s_h"] + q["throat_block"][2])), pendant=0.03, group=grp)
        P_j, R_j = self.spar_at(G, q["throat_gaff_x"])
        lb = self.add_block("SpankerThroatGaff", 1, c, attach=(G, P_j + np.array([0.0, 0.0, R_j])), pendant=0.0,
                            group=grp)
        ln = self.new_line("spanker throat halyard", grp, c)
        pin = self.pin_station("mizzen", sg, q["throat_rails"])
        for S in STATES:
            ln.set(S, [{"k": "end", "b": ub.bid}, self.sheave(lb.bid), self.sheave(ub.bid), pin])
        # -- the peak halyard
        c = self.circ(None, "spanker", "peak_halyard")
        sg = float(q["peak_side"])
        s_m = m["s_cap1"] - q["peak_block_below_cap"]
        R_m = float(m["R_lower"](s_m))
        mb = self.add_block("SpankerPeakMast", 1, c, attach=("ship", MG.lo(-(R_m + 0.03), sg * 0.12, s_m)),
                            pendant=0.12, group=grp)
        x0g, x1g = self.spar_ends(G)
        P_g, R_g = self.spar_at(G, x1g + q["peak_at"] * (x0g - x1g))
        gb = self.add_block("SpankerPeakGaff", 1, c, attach=(G, P_g + np.array([0.0, 0.0, R_g])),
                            pendant=q["peak_pendant_m"], group=grp)
        gb.ring = (G, P_g, EX, R_g + 0.004 + gb.r_strop)        # its pendant from a strop round the gaff
        E = MG.lo(-(R_m + 0.03), -sg * 0.1, s_m + 0.05)
        ln = self.new_line("spanker peak halyard", grp, c)
        tail = [self.fair("mizzen", sg, self.top_aft_box("mizzen")), self.pin_station("mizzen", sg, q["peak_rails"])]
        for S in STATES:
            ln.set(S, [self.ends("ship", E), self.sheave(gb.bid), self.sheave(mb.bid)] + tail)
        # -- the vangs
        c = self.circ(None, "spanker", "vang")
        P_e, R_e = self.spar_at(G, x0g + q["vang_in_m"])
        for sg in (1.0, -1.0):
            side = "starboard" if sg > 0 else "port"
            ln = self.new_line(f"spanker vang {side}", grp, c)
            pin = self.pin_station("mizzen", sg, q["vang_rails"])
            e = P_e + np.array([0.0, sg * (R_e + rope_r(c)), 0.0])
            for S in STATES:
                ln.set(S, [self.ends(G, e), pin])
        # -- the topping lifts
        c = self.circ(None, "spanker", "topping_lift")
        x0b, x1b = self.spar_ends(B)
        P_b, R_b = self.spar_at(B, x0b + q["lift_in_m"])
        for sg in (1.0, -1.0):
            tag, side = ("S", "starboard") if sg > 0 else ("P", "port")
            bx, by, bds = q["lift_block"]
            kb = self.add_block(f"SpankerLift{tag}", 1, c, attach=("ship", MG.lo(m["fa"] + bx, sg * by, m["s_h"] + bds)),
                                pendant=0.04, group=grp)
            ln = self.new_line(f"spanker topping lift {side}", grp, c)
            e = P_b + np.array([0.0, sg * (R_b + rope_r(c)), 0.0])
            pin = self.pin_station("mizzen", sg, q["lift_rails"])
            for S in STATES:
                sp = [("drape", self.drape_side("spanker", S, G, sg, rope_r(c))), None]
                ln.set(S, [self.ends(B, e), self.sheave(kb.bid), pin], sp)
        # -- the boom sheet: a double block under the boom over the taffrail, a single on the taffrail
        c = self.circ(None, "spanker", "boom_sheet")
        xs = q["sheet_x"]
        o_b, Rb_ = Pose(self.rig, "Set").frame(B)
        xl = float((xs - o_b[0]) / Rb_[0, 0])
        P_s, R_s = self.spar_at(B, xl)
        L = self.block_L(c)
        TV = np.asarray(self.sk.parts()["TransomTop"][0], float)
        z_t = float(TV[np.abs(TV[:, 1]) < 0.4][:, 2].max())
        ubk = self.add_block("SpankerSheetBoom", 2, c, fixed=(B, P_s - np.array([0.0, 0.0, R_s + 0.5 * L + 0.05]),
                                                              np.array([0.0, 0.0, -1.0]), EX), group=grp)
        ubk.ring = (B, P_s, EX, R_s + 0.004 + ubk.r_strop)      # its strop round the boom
        lbk = self.add_block("SpankerSheetTaffrail", 1, c, fixed=("ship", np.array([xs, 0.0, z_t + 0.07 + 0.5 * L]),
                                                                  np.array([0.0, 0.0, 1.0]), EX), group=grp)
        lbk.eyebolt = True
        ln = self.new_line("spanker boom sheet", grp, c)
        pin = self.pin_station("mizzen", 1.0, q["sheet_rails"])
        for S in STATES:
            ln.set(S, [{"k": "end", "b": lbk.bid}, self.sheave(ubk.bid, 0), self.sheave(lbk.bid, 0),
                       self.sheave(ubk.bid, 1), pin])

    def spritsail_gear(self, q):
        """the spritsail yard's gear (it carries no sail here): its slings round the bowsprit, a lift from each yardarm
        to the bowsprit cap's side, a brace from each yardarm in through the bow's side to a kevel"""
        Y = "Yard_Spritsail"
        grp = "Spritsail"
        d = self.deck
        V = np.asarray(self.rig.parts_[Y]["mesh"].arrays()[0], float)

        def sec(y):
            for w in (0.06, 0.15, 0.3, 0.6):
                P = V[np.abs(V[:, 1] - y) < w]
                if len(P) >= 6:
                    break
            return (np.array([0.5 * (P[:, 0].max() + P[:, 0].min()), y, 0.5 * (P[:, 2].max() + P[:, 2].min())]),
                    0.5 * (P[:, 2].max() - P[:, 2].min()))
        half = float(V[:, 1].max())
        bs = self.rig.bs
        Rb = float(bs["R"](bs["sy_s"]))
        # -- the slings: from the yard's top up round the bowsprit's sides (over the iron hoop there, if there is one)
        c = self.circ(None, "spritsail", "sling")
        r = rope_r(c)
        ub = np.asarray(bs["ub"], float)
        Vb = np.asarray(self.rig.parts_["Bowsprit"]["mesh"].arrays()[0], float) - np.asarray(bs["H"], float)
        sb = Vb @ ub
        near = np.abs(sb - bs["sy_s"]) < r + 0.08                 # (a hoop's edges, 2 in either side of its middle)
        if near.any():
            Rb = max(Rb, float(np.linalg.norm(Vb[near] - np.outer(sb[near], ub), axis=1).max()))
        rho = Rb + r + 0.006
        for sg in (1.0, -1.0):
            side = "starboard" if sg > 0 else "port"
            C0, R0 = sec(sg * 0.12)
            Q = C0 + np.array([0.0, 0.0, R0 + r])
            # up to where it meets the bowsprit's round (tangent from the yard's top), then round its side
            q2 = np.array([Q[1], Q[2]])
            dq = float(np.linalg.norm(q2))
            ph = math.acos(min(1.0, rho / dq))
            a0 = math.atan2(q2[1], q2[0])
            T = max((np.array([math.cos(a0 + s_ * ph), math.sin(a0 + s_ * ph)]) * rho for s_ in (1.0, -1.0)),
                    key=lambda t: sg * t[0])
            a1 = math.atan2(T[1], T[0])
            ln = self.new_line(f"spritsail sling {side}", grp, c)
            n_ = 5                                              # round the side in five turns whose chords touch the round
            ro_ = rho / math.cos(0.25 / n_)
            arc = [{"k": "thru", "at": (Y, np.array([0.0, ro_ * math.cos(a1 + sg * 0.5 * (i + 0.5) / n_),
                                                     ro_ * math.sin(a1 + sg * 0.5 * (i + 0.5) / n_)])),
                    "r": 0.0, "fit": None} for i in range(n_)]
            sts = [self.ends(Y, Q), {"k": "thru", "at": (Y, np.array([0.0, T[0], T[1]])), "r": 0.0, "fit": None}] + \
                arc + [self.ends(Y, np.array([0.0, rho * math.cos(a1 + sg * 0.5), rho * math.sin(a1 + sg * 0.5)]))]
            for S in STATES:
                ln.set(S, sts)
        # -- the lifts: from the yardarm up to the cap's side
        c = self.circ(None, "spritsail", "lift")
        r = rope_r(c)
        cap = np.asarray(bs["cap"], float)
        for sg in (1.0, -1.0):
            side = "starboard" if sg > 0 else "port"
            Ca, Ra = sec(sg * (half - q["lift_in_m"]))
            ln = self.new_line(f"spritsail lift {side}", grp, c)
            E = cap + np.array([q["lift_cap"][0], sg * q["lift_cap"][1], q["lift_cap"][2]])
            for S in STATES:
                ln.set(S, [self.ends(Y, Ca + np.array([0.0, 0.0, Ra + r])), self.ends("ship", E)])
        # -- the braces: from the yardarm aft, in through the bow's side to a kevel
        c = self.circ(None, "spritsail", "brace")
        r = rope_r(c)
        for sg in (1.0, -1.0):
            tag, side = ("S", "starboard") if sg > 0 else ("P", "port")
            Ca, Ra = sec(sg * (half - q["brace_in_m"]))
            z = d.z(q["brace_x"]) + q["brace_over_deck"]
            th1, th2 = self.hole(q["brace_x"], z, sg)
            kv = self.kevel(f"SpritsailBrace{tag}", q["brace_x"] + q["brace_kevel_dx"], z, sg, r)
            ln = self.new_line(f"spritsail brace {side}", grp, c)
            for S in STATES:
                ln.set(S, [self.ends(Y, Ca + np.array([-(Ra + r), 0.0, 0.0])), th1, th2, kv])

    # -- solving, pins, fairleads ----------------------------------------------------------------------------------------
    def stations(self):
        """every distinct station dict (fairleads and pins are shared by the states)"""
        seen, out = set(), []
        for ln in self.lines:
            for S in STATES:
                for st in ln.st.get(S, []):
                    if id(st) not in seen:
                        seen.add(id(st))
                        out.append((ln, st))
        return out

    def solve(self, states=STATES):
        self.solvers = getattr(self, "solvers", {})
        for S in states:
            sv = Solver(Pose(self.rig, S), self.blocks, self.lines, self.pins)
            sv.solve()
            self.solvers[S] = sv
        return self

    def came_from(self, ln, j, S="Set"):
        """the point a line comes from into its station j (the station before's centre)"""
        sv = self.solvers[S]
        return sv.centre(ln.st[S][j - 1])

    def reserve_pin(self, zone, x, line):
        """a pin set aside at build time for a line whose lead is made for it: the free one in zone nearest x"""
        ids = [i for i in self.pins.zones[zone] if not self.pins.pins[i].get("reserved")]
        pid = min(ids, key=lambda i: abs(self.pins.pins[i]["p"][0] - x))
        self.pins.pins[pid]["reserved"] = True
        self.pins.pins[pid]["line"] = line
        return pid

    def allocate_pins(self, C=None, keep=False):
        """each line's pin: the assignment of lines to free pins (in their zones, on their side) that makes the falls'
        total length least (no two falls then cross in plan, near enough). keep: the falls that have a pin keep it, and
        only those without one are given one of the pins still free"""
        from scipy.optimize import linear_sum_assignment
        want = []                                                # (line, station)
        for ln, st in self.stations():
            if st["k"] == "pin" and st.get("zones") and not (keep and st.get("pin")):
                want.append((ln, st))
        if not want:
            return []
        for pn in self.pins.pins.values():
            if not pn.get("reserved") and not keep:
                pn["line"] = None
        ids = list(self.pins.pins)
        P = np.array([self.pins.pins[i]["p"] for i in ids])
        BIG = 1e6
        Cm = np.full((len(want), len(ids)), BIG)
        for a, (ln, st) in enumerate(want):
            j = next(i_ for i_, x_ in enumerate(ln.st["Set"]) if x_ is st)
            q = self.came_from(ln, j)
            for b, pid in enumerate(ids):
                pn = self.pins.pins[pid]
                z = pn["zone"]
                if z not in st["zones"] or pn.get("reserved") or (keep and pn.get("line")):
                    continue
                if z.startswith("fife") and pn.get("side") not in ("c", "s" if st["side"] > 0 else "p"):
                    continue
                Cm[a, b] = float(np.linalg.norm(P[b] - q))
        if C is not None:                                       # a fall that would foul something on its way down
            skip = self.cfg["check"]["skip_end_in"] * IN
            gap = self.cfg["check"]["gap_in"] * IN
            for a, (ln, st) in enumerate(want):
                j = next(i_ for i_, x_ in enumerate(ln.st["Set"]) if x_ is st)
                near = np.argsort(Cm[a])[:40]
                for S in STATES:
                    if S not in ln.st:
                        continue
                    q = self.solvers[S].centre(ln.st[S][j - 1])
                    for b in near:
                        if Cm[a, b] >= BIG:
                            continue
                        pn = self.pins.pins[ids[b]]
                        w = pn["p"] + pn["axis"] * 0.45 * pn["h"]
                        d, _, _ = trace(self.clearance_for(C, S, ln).bvh, q, w, ln.r + gap, skip, skip)
                        if d - ln.r < gap:
                            Cm[a, b] += 50.0
        r, c = linear_sum_assignment(Cm)
        short = []
        for a, b in zip(r, c):
            ln, st = want[a]
            if Cm[a, b] >= BIG:
                short.append(ln.name)
                st["pin"] = None
                continue
            st["pin"] = ids[b]
            self.pins.pins[ids[b]]["line"] = ln.name
        return short

    def untangle_pins(self, C=None, rounds=3):
        """swap the pins of two falls whose leads down from their last fairlead pass too close (in any state), when
        the swap leaves both clear (of each other and, with C, of the ship)"""
        gap = self.cfg["check"]["gap_in"] * IN
        skip = self.cfg["check"]["skip_end_in"] * IN
        falls = [(ln, st) for ln, st in self.stations() if st["k"] == "pin" and st.get("pin") and st.get("zones")]
        def seg(ln, st, pid, S):
            j = next(i_ for i_, x_ in enumerate(ln.st[S]) if x_ is st)
            a = self.solvers[S].centre(ln.st[S][j - 1])
            return a, self.pins.belay_point(pid, a, ln.r)
        def worst(ln1, st1, p1, ln2, st2, p2):
            w = np.inf
            for S in STATES:
                if S not in ln1.st or S not in ln2.st:
                    continue
                a, b = seg(ln1, st1, p1, S)
                c, d = seg(ln2, st2, p2, S)
                w = min(w, float(seg_seg(a, b, c[None], d[None])[0]) - ln1.r - ln2.r)
                if C is not None:
                    for (x, y), ln_ in (((a, b), ln1), ((c, d), ln2)):
                        dd, _, _ = trace(self.clearance_for(C, S, ln_).bvh, x, y, ln_.r + gap, skip, skip)
                        w = min(w, dd - ln_.r + 0.0)
            return w
        swaps = 0
        for _ in range(rounds):
            changed = False
            for i in range(len(falls)):
                for j in range(i + 1, len(falls)):
                    (l1, s1), (l2, s2) = falls[i], falls[j]
                    if s1.get("side") != s2.get("side"):
                        continue
                    p1, p2 = s1["pin"], s2["pin"]
                    z1, z2 = self.pins.pins[p1]["zone"], self.pins.pins[p2]["zone"]
                    if z2 not in s1["zones"] or z1 not in s2["zones"]:
                        continue
                    now = worst(l1, s1, p1, l2, s2, p2)
                    if now >= gap:
                        continue
                    alt = worst(l1, s1, p2, l2, s2, p1)
                    if alt > now + 1e-4:
                        s1["pin"], s2["pin"] = p2, p1
                        self.pins.pins[p1]["line"], self.pins.pins[p2]["line"] = l2.name, l1.name
                        changed = True
                        swaps += 1
            if not changed:
                break
        return swaps

    def pin_fits(self, st, pid):
        """whether a fall (its pin station st) may belay to pin pid: not set aside, in one of its zones, and on a fife
        rail on its own side of the mast (or the middle)"""
        pn = self.pins.pins[pid]
        if pn.get("reserved") or pn["zone"] not in (st.get("zones") or ()):
            return False
        return not (pn["zone"].startswith("fife") and pn.get("side") not in ("c", "s" if st["side"] > 0 else "p"))

    def _pin_kit(self, C):
        """what repin and repin_pairs share: the falls and the pins they hold, a fall's lead down to a pin (from its last
        fairlead), how clear that lead is (in every state, of the ship, the other lines, bull's eyes and blocks: as the
        check measures it, skip_end_in clear of its ends against the other lines), and put (a fall to a pin)"""
        skip = self.cfg["check"]["skip_end_in"] * IN
        gap = self.cfg["check"]["gap_in"] * IN
        target = gap + 0.006
        falls = [(ln, st) for ln, st in self.stations() if st["k"] == "pin" and st.get("pin") and st.get("zones")]
        segs = {S: {} for S in STATES}
        for S in STATES:
            for ln in self.lines:
                if S in ln.st:
                    P = ln.path[S] if S in ln.path else self.centres(ln, S)
                    segs[S][ln.name] = (P[:-1], P[1:], ln.r, (P.min(0) - ln.r, P.max(0) + ln.r))
        eyes = [(np.asarray(st["at"][1], float), self.bullseye_r(ln, st.get("fit")), ln.name)
                for ln, st in self.stations() if st.get("box") is not None]
        blocks = {S: self.block_shapes(S) for S in STATES}
        by_pin = {st["pin"]: (ln, st) for ln, st in falls}

        ok_pin = self.pin_fits

        def lead(ln, st, pid, S):
            sts = ln.st[S]
            j = next(i_ for i_, x_ in enumerate(sts) if x_ is st)
            a = self.solvers[S].centre(sts[j - 1])
            return a, self.pins.belay_point(pid, a, ln.r)

        def trim(a, b):
            L = float(np.linalg.norm(b - a))
            if L <= 2 * skip + 1e-3:
                return None
            u = (b - a) / L
            return a + u * skip, b - u * skip

        def clear(ln, st, pid, ignore=()):
            w = np.inf
            for S in STATES:
                if S not in ln.st:
                    continue
                a, b = lead(ln, st, pid, S)
                d, _, _ = trace(self.clearance_for(C, S, ln).bvh, a, b, ln.r + 0.12, skip, skip)
                w = min(w, d - ln.r)
                ab = trim(a, b)
                if ab is not None:
                    sg_ = {k: v for k, v in segs[S].items() if k not in ignore} if ignore else segs[S]
                    w = min(w, line_gap(ab[0], ab[1], ln.r, sg_, ln.name))
                for q, r_, nm in eyes:
                    if nm != ln.name and nm not in ignore:
                        w = min(w, pt_seg_d(q, a, b) - r_ - ln.r)
                for shp in blocks[S]:
                    if ln.name not in shp[3]:
                        w = min(w, ell_seg_clear(shp, a, b, ln.r))
            return w

        def pair(l1, s1, p1, l2, s2, p2):
            w = np.inf
            for S in STATES:
                if S in l1.st and S in l2.st:
                    ab, cd = trim(*lead(l1, s1, p1, S)), trim(*lead(l2, s2, p2, S))
                    if ab is not None and cd is not None:
                        w = min(w, float(seg_seg(ab[0], ab[1], cd[0][None], cd[1][None])[0]) - l1.r - l2.r)
            return w

        def put(ln, st, pid):
            old = st["pin"]
            if old and self.pins.pins[old].get("line") == ln.name:
                self.pins.pins[old]["line"] = None
                by_pin.pop(old, None)
            st["pin"] = pid
            self.pins.pins[pid]["line"] = ln.name
            by_pin[pid] = (ln, st)
            for S in STATES:
                if S not in ln.st:
                    continue
                a, b = lead(ln, st, pid, S)
                P = ln.path[S] if S in ln.path else self.centres(ln, S)
                k = len(P) - 2 - int(np.argmin(np.linalg.norm(P[:-1][::-1] - a, axis=1)))
                P = np.concatenate([P[:k + 1], b[None]])
                segs[S][ln.name] = (P[:-1], P[1:], ln.r, (P.min(0) - ln.r, P.max(0) + ln.r))

        return types.SimpleNamespace(target=target, falls=falls, by_pin=by_pin, ok_pin=ok_pin, lead=lead, clear=clear,
                                     pair=pair, put=put)

    def repin(self, C, rounds=2, log=None, shortlist=6, only=None):
        """move each fall whose lead down from its last fairlead passes too close (in any state) to the ship, another
        line, a bull's eye or a block, to the pin in its zones that leaves it clearest: a free pin, or another fall's
        whose own lead then moves to a free pin of its zones (or to this one's) and comes out no worse. only: the names
        of the lines that may move (the others keep their pins)"""
        k_ = self._pin_kit(C)
        target, falls, by_pin, ok_pin, clear, pair, put = (k_.target, k_.falls, k_.by_pin, k_.ok_pin, k_.clear, k_.pair,
                                                           k_.put)
        moves = 0
        for _ in range(rounds):
            changed = False
            for ln, st in falls:
                if only is not None and ln.name not in only:
                    continue
                p0 = st["pin"]
                now = clear(ln, st, p0)
                if now >= target:
                    continue
                best, plan = now, None
                cands = []
                for pid, pn in self.pins.pins.items():
                    if pid == p0 or not ok_pin(st, pid):
                        continue
                    holder = by_pin.get(pid)
                    if holder is None and pn.get("line"):
                        continue                                # a pin a fixed rope (no zones) belays to
                    if holder is not None and only is not None and holder[0].name not in only:
                        continue
                    ign = (holder[0].name,) if holder else ()
                    cands.append((clear(ln, st, pid, ignore=ign), pid, holder))
                cands.sort(key=lambda c_: -c_[0])
                for c1, pid, holder in cands:
                    if c1 <= best + 1e-4:
                        break
                    if holder is None:
                        best, plan = c1, (pid, None)
                        break
                for c1, pid, holder in [c_ for c_ in cands if c_[2] is not None][:shortlist]:
                    if c1 <= best + 1e-4:
                        continue
                    l2, s2 = holder
                    keep2 = clear(l2, s2, pid, ignore=(ln.name,))
                    for q in [p0] + [x for x, xn in self.pins.pins.items() if not xn.get("line") and x not in by_pin]:
                        if q == pid or not ok_pin(s2, q):
                            continue
                        c2 = clear(l2, s2, q, ignore=(ln.name,))
                        sc = min(c1, c2, pair(ln, st, pid, l2, s2, q))
                        if sc > best + 1e-4 and c2 >= min(keep2, target) - 1e-4:
                            best, plan = sc, (pid, (l2, s2, q))
                if plan is not None:
                    pid, ch = plan
                    put(ln, st, pid)
                    if ch is not None:
                        put(*ch)
                    moves += 1
                    changed = True
                    if log is not None:
                        log.append((ln.name, p0, pid, ch[0].name + " -> " + ch[2] if ch else None, round(now, 4),
                                    round(best, 4)))
            if not changed:
                break
        return moves

    def twin_lines(self):
        """each port line's starboard twin and each starboard line's port twin, by name (a line built for both sides is
        named "... port" and "... starboard"; a halyard or a staysail sheet has no twin)"""
        by = {ln.name: ln for ln in self.lines}
        out = {}
        for nm, ln in by.items():
            if nm.endswith(" starboard") and nm[:-len(" starboard")] + " port" in by:
                ln2 = by[nm[:-len(" starboard")] + " port"]
                out[nm], out[ln2.name] = ln2, ln
        return out

    def pin_mirror(self):
        """each pin's mirror image across the centreline (the pin there, within 3 cm), or None"""
        from scipy.spatial import cKDTree
        ids = list(self.pins.pins)
        X = np.array([self.pins.pins[i]["p"] for i in ids])
        d_, j_ = cKDTree(X).query(X * MIRROR)
        return {pid: (ids[j] if d < 0.03 else None) for pid, d, j in zip(ids, d_, j_)}

    def mirror_twins(self, C=None):
        """make each pair of port and starboard lines mirror images, as a ship's belaying plan is: the port rope's
        bull's eyes and pin go to the mirror of the starboard rope's. A single line (a halyard, say) on a pin a port rope
        now takes is given another free pin; returns the lines moved so and those left without a pin"""
        P = self.pins.pins
        mir = self.pin_mirror()
        tw = self.twin_lines()
        by = {ln.name: ln for ln in self.lines}
        want = []
        for nm, lp in tw.items():
            if not nm.endswith(" starboard"):
                continue
            ls = by[nm]                                         # the starboard rope, lp its port twin
            A, B = ls.st["Set"], lp.st["Set"]
            assert len(A) == len(B), nm
            for a, b in zip(A, B):
                if a.get("box") is not None and b.get("box") is not None:
                    b["at"] = ("ship", MIRROR * np.asarray(a["at"][1], float))
                    b["loaded"], b["score"] = True, a.get("score", 0.0)
                    a["loaded"] = True
                if a["k"] == "pin" and a.get("zones") and a.get("pin") and b.get("zones"):
                    want.append((lp, b, mir.get(a["pin"])))
        for ln, st, pid in want:
            if st.get("pin") and P[st["pin"]].get("line") == ln.name:
                P[st["pin"]]["line"] = None
            st["pin"] = None
        holder = {st["pin"]: (ln, st) for ln, st in self.stations() if st["k"] == "pin" and st.get("pin")}
        bumped = []
        for ln, st, pid in want:
            if pid is None or not self.pin_fits(st, pid):
                continue                                        # no pin there for it: allocate_pins gives it one
            h = holder.get(pid)
            if h is not None and h[1] is not st:
                if not h[1].get("zones") or h[0].name in tw:
                    continue                                    # a fixed rope's pin, or a twin's
                h[1]["pin"] = None
                bumped.append(h[0].name)
            st["pin"] = pid
            P[pid]["line"] = ln.name
            holder[pid] = (ln, st)
        short = self.allocate_pins(C, keep=True)
        return bumped, short

    def repin_pairs(self, C, rounds=2, log=None):
        """repin for the pairs of port and starboard falls on mirrored pins, keeping them mirrored: a pair whose lead
        down to a pin passes too close (on either side, in any state) moves to the free mirrored pins in its zones that
        leave both clearest, or swaps pins with another mirrored pair when that leaves all four leads no worse"""
        k_ = self._pin_kit(C)
        P = self.pins.pins
        mir = self.pin_mirror()
        tw = self.twin_lines()
        fall = {ln.name: (ln, st) for ln, st in k_.falls}
        pairs = []
        for nm, lp in tw.items():
            if nm.endswith(" port") and nm in fall and tw[nm].name in fall:
                (lp, sp), (ls, ss) = fall[nm], fall[tw[nm].name]
                if mir.get(sp["pin"]) == ss["pin"]:
                    pairs.append((lp, sp, ls, ss))

        def free(pid):
            return pid not in k_.by_pin and not P[pid].get("line")

        def both(A, pp, ps, ign=()):
            return min(k_.clear(A[0], A[1], pp, ignore=ign), k_.clear(A[2], A[3], ps, ignore=ign))
        moves = 0
        for _ in range(rounds):
            changed = False
            for A in pairs:
                pp, ps = A[1]["pin"], A[3]["pin"]
                now = both(A, pp, ps)
                if now >= k_.target:
                    continue
                best, plan = now, None
                for q in P:
                    m = mir.get(q)
                    if not m or m == q or q == pp or not (free(q) and free(m)):
                        continue
                    if k_.ok_pin(A[1], q) and k_.ok_pin(A[3], m):
                        sc = both(A, q, m)
                        if sc > best + 1e-4:
                            best, plan = sc, (q, m, None)
                for B in pairs:
                    if B is A:
                        continue
                    bp, bs = B[1]["pin"], B[3]["pin"]
                    if not (k_.ok_pin(A[1], bp) and k_.ok_pin(A[3], bs) and k_.ok_pin(B[1], pp) and k_.ok_pin(B[3], ps)):
                        continue
                    ia, ib = (B[0].name, B[2].name), (A[0].name, A[2].name)
                    c1 = both(A, bp, bs, ia)
                    if c1 <= best + 1e-4:
                        continue
                    keep = both(B, bp, bs)
                    c2 = both(B, pp, ps, ib)
                    sc = min(c1, c2, k_.pair(A[0], A[1], bp, B[0], B[1], pp), k_.pair(A[2], A[3], bs, B[2], B[3], ps))
                    if sc > best + 1e-4 and c2 >= min(keep, k_.target) - 1e-4:
                        best, plan = sc, (bp, bs, B)
                if plan is not None:
                    q, m, B = plan
                    k_.put(A[0], A[1], q)
                    k_.put(A[2], A[3], m)
                    if B is not None:
                        k_.put(B[0], B[1], pp)
                        k_.put(B[2], B[3], ps)
                    moves += 1
                    changed = True
                    if log is not None:
                        log.append((A[0].name[:-len(" port")], (pp, ps), (q, m), B[0].name if B else None,
                                    round(now, 4), round(best, 4)))
            if not changed:
                break
        return moves

    def rail_side(self, pid):
        """the side ("s" or "p") of a pin in a side rail (the forecastle's, the gangways' and the quarterdeck's), or
        None (a fife rail's, a top's)"""
        zn = self.pins.pins[pid]["zone"] if pid else ""
        return zn[-1] if zn.startswith(("fc", "gw", "qd")) and zn[-1:] in ("s", "p") else None

    def crossings(self):
        """the falls that don't lead fair: two to one side's rails whose leads down from their last fairlead cross, seen
        from inboard, within cross_above_m above the higher of their pins. In each state, the two lines, their pins and
        where they cross (x, z), measured on the centre lines running.json gives"""
        above = self.cfg["check"]["cross_above_m"]
        out = []
        for S in STATES:
            leads = []
            for ln, st in self.stations():
                if (st["k"] == "pin" and st.get("pin") and ln.st.get(S) and ln.st[S][-1] is st
                        and self.rail_side(st["pin"])):
                    P = simplify(ln.path[S], max(0.001, self.cfg["mesh"]["simplify_of_r"] * ln.r))
                    leads.append((self.rail_side(st["pin"]), ln.name, st["pin"], P[-2], P[-1]))
            for i, (s1, n1, p1, a1, b1) in enumerate(leads):
                for s2, n2, p2, a2, b2 in leads[i + 1:]:
                    X = side_cross(a1, b1, a2, b2, above) if s1 == s2 else None
                    if X is not None:
                        out.append([S, n1, p1, n2, p2, round(float(X[0]), 2), round(float(X[1]), 2)])
        return out

    def uncross_pins(self, C, rounds=3, log=None, only=None):
        """trade pins where two falls to one side's rails would cross just above them, seen from inboard (crossings): a
        pair of twins moves to free mirrored pins or trades pins with another pair, a single fall (a staysail's sheet,
        say) to a free pin or with another single, when that crosses fewer falls and leaves each lead it moves as clear
        as it was, or clear by the target. only: the names of the lines that may move"""
        k_ = self._pin_kit(C)
        P = self.pins.pins
        mir = self.pin_mirror()
        tw = self.twin_lines()
        above = self.cfg["check"]["cross_above_m"]
        fall = {ln.name: (ln, st) for ln, st in k_.falls}
        units, seen = [], set()             # what moves together: twins on mirrored pins (starboard first), or a single
        for nm, (ln, st) in fall.items():
            if nm in seen or not self.rail_side(st["pin"]) or (only is not None and nm not in only):
                continue
            t = tw.get(nm)
            if t is None:
                units.append(((ln, st),))
                seen.add(nm)
            elif t.name in fall and mir.get(st["pin"]) == fall[t.name][1]["pin"]:
                u = ((ln, st), fall[t.name]) if nm.endswith(" starboard") else (fall[t.name], (ln, st))
                if only is None or t.name in only:
                    units.append(u)
                seen |= {nm, t.name}
        memo = {}

        def lead(ln, st, pid, S):
            key = (ln.name, pid, S)
            if key not in memo:
                memo[key] = k_.lead(ln, st, pid, S)
            return memo[key]

        def crosses(f1, p1, f2, p2):
            sd = self.rail_side(p1)
            if not sd or sd != self.rail_side(p2):
                return False
            (l1, s1), (l2, s2) = f1, f2
            for S in STATES:
                if S in l1.st and S in l2.st:
                    if side_cross(*lead(l1, s1, p1, S), *lead(l2, s2, p2, S), above) is not None:
                        return True
            return False

        def count(moved):
            """the crossings a set of falls makes on the pins given ({name: ((line, station), pin)}), the rest on
            theirs"""
            n = 0
            for nm, (f, p) in moved.items():
                n += sum(crosses(f, p, (ln, st), st["pin"]) for ln, st in k_.falls if ln.name not in moved)
            it = list(moved.values())
            return n + sum(crosses(*it[i], *it[j]) for i in range(len(it)) for j in range(i + 1, len(it)))

        def free(pid):
            return pid not in k_.by_pin and not P[pid].get("line")

        def clear_of(u, pins, ign=()):
            return min(k_.clear(ln, st, p, ignore=ign) for (ln, st), p in zip(u, pins))
        moves = 0
        for _ in range(rounds):
            changed = False
            for A in units:
                pa = [st["pin"] for _, st in A]
                now = count({ln.name: ((ln, st), st["pin"]) for ln, st in A})
                if not now:
                    continue
                keep = clear_of(A, pa)
                best, plan = (0, -np.inf), None
                opts = []
                for q in P:                                                 # to free pins
                    qs = [q] if len(A) == 1 else [q, mir.get(q)]
                    if qs[-1] and len(set(qs)) == len(A) and all(free(x) for x in qs) and all(
                            k_.ok_pin(st, x) for (_, st), x in zip(A, qs)):
                        opts.append((qs, None))
                for B in units:                                             # or a trade with another unit like it
                    if B is not A and len(B) == len(A):
                        pb = [st["pin"] for _, st in B]
                        if all(k_.ok_pin(st, x) for (_, st), x in zip(A, pb)) and all(
                                k_.ok_pin(st, x) for (_, st), x in zip(B, pa)):
                            opts.append((pb, B))
                for qs, B in opts:
                    mv = {ln.name: ((ln, st), x) for (ln, st), x in zip(A, qs)}
                    before = now
                    if B is not None:
                        mv.update({ln.name: ((ln, st), x) for (ln, st), x in zip(B, pa)})
                        before += count({ln.name: ((ln, st), st["pin"]) for ln, st in B}) - sum(
                            crosses((l1, s1), s1["pin"], (l2, s2), s2["pin"]) for l1, s1 in A for l2, s2 in B)
                    gain = before - count(mv)
                    if gain <= 0 or gain < best[0]:
                        continue
                    floor = min(keep, k_.target) - 1e-4         # each lead moved: no worse, or clear by the target
                    sc = clear_of(A, qs, tuple(ln.name for ln, _ in B) if B is not None else ())
                    if sc < floor:
                        continue
                    if B is not None:
                        floor_b = min(clear_of(B, [st["pin"] for _, st in B]), k_.target) - 1e-4
                        c2 = clear_of(B, pa, tuple(ln.name for ln, _ in A))
                        c3 = min(k_.pair(la, sa, xa, lb, sb, xb) for (la, sa), xa in zip(A, qs)
                                 for (lb, sb), xb in zip(B, pa))
                        if c2 < floor_b or c3 < min(floor, floor_b):
                            continue
                        sc = min(sc, c2, c3)
                    if (gain, sc) > best:
                        best, plan = (gain, sc), (qs, B)
                if plan is not None:
                    qs, B = plan
                    for (ln, st), x in zip(A, qs):
                        k_.put(ln, st, x)
                    if B is not None:
                        for (ln, st), x in zip(B, pa):
                            k_.put(ln, st, x)
                    moves += 1
                    changed = True
                    if log is not None:
                        log.append(("uncross", A[0][0].name, pa, qs, B[0][0].name if B else None, best[0]))
            if not changed:
                break
        return moves

    def box_points(self, box, n=(3, 3, 3)):
        mast, sg, ((x0, x1), (y0, y1), (s0, s1)) = box
        MG = self.mg[mast]
        out = []
        for x in np.linspace(x0, x1, n[0]):
            for y in np.linspace(y0, y1, n[1]):
                for s in np.linspace(s0, s1, n[2]):
                    out.append(MG.lo(x, sg * y, s))
        return np.array(out)

    def bullseye_r(self, ln, fit="bullseye"):
        """a bull's eye's or thimble's outer radius as drawn, for the line through it: what the placement and the
        checks keep the other ropes clear of"""
        return eye_outer(fit, ln.r)

    def clearance_for(self, C, S, ln, soft=False):
        """C[S], or for a line led through one of the soup's no-pass sheets (ln.through: a brace's fall in between two
        shrouds) or that may press into something soft (ln.soft: a clewline into the cloth gathered under its yard) the
        soup round the line and the pins it may take, without those (the ratlines and shrouds themselves stay). soft:
        only the soft things instead (None if there are none)"""
        thr = set(getattr(ln, "through", None) or ())
        sf = set(getattr(ln, "soft", {}).get(S, {}))
        if soft and not sf:
            return None
        if not soft and not thr and not sf:
            return C[S]
        cache = self.__dict__.setdefault("_through_c", {})
        key = (id(C[S]), ln.name, soft)
        if key not in cache:
            pts = [self.solvers[S_].centre(st) for S_ in ln.st for st in ln.st[S_] if st["k"] != "pin"]
            zones = {z for st in ln.st["Set"] if st["k"] == "pin" for z in (st.get("zones") or ())}
            pts += [pn["p"] for pn in self.pins.pins.values() if pn["zone"] in zones]
            P = np.array(pts, float)
            cache[key] = C[S].local(P.min(0) - 1.0, P.max(0) + 1.0, only=sf) if soft else \
                C[S].local(P.min(0) - 1.0, P.max(0) + 1.0, thr | sf)
        return cache[key]

    def centres(self, ln, S):
        sv = self.solvers[S]
        return np.array([self.pins.pins[st["pin"]]["p"] if (st["k"] == "pin" and st.get("pin")) else sv.centre(st)
                         for st in ln.st[S]])

    def block_shapes(self, S):
        """(centre, axes (rows: across the shell, along the pin, crown to tail), semi-axes, names of the lines through
        it) for each drawn block in state S: an ellipsoid round the shell, its strop and the strop's eye"""
        through = {}
        for ln in self.lines:
            for st in ln.st.get(S, []):
                if "b" in st:
                    through.setdefault(st["b"], set()).add(ln.name)
        out = []
        for bid, b in self.blocks.items():
            if getattr(b, "hidden", False) or S not in b.pose:
                continue
            C, a, n = b.pose[S]
            e = unit(np.cross(a, n))
            n = unit(np.cross(e, a))
            za = 0.5 * (b.L / 2 - b.eye_drop)
            sa = 0.5 * (b.L / 2 + b.eye_drop)
            out.append((C + a * za, np.array([e, n, a]), np.array([b.w / 2 + b.r_strop, b.t / 2 + b.r_strop, sa]),
                        through.get(bid, set())))
        return out

    def place_fairleads(self, C, passes=2, log=None, only=None, warm=False, pair=False):
        """put each free bull's eye where the rope through it stands clearest (in every state) of the ship, the other
        lines, their bull's eyes and blocks: the best of a grid over its box, then of a finer grid round the best.
        Gauss-Seidel: each line against the others as they now lie; a second pass sees them all. warm: a place given
        before (loaded from an earlier placement, or a twin's mirror image) stays while it is clear by the target. pair:
        each port rope's eye is the mirror image of its starboard twin's, put where both ropes stand clearest"""
        skip = self.cfg["check"]["skip_end_in"] * IN
        gap = self.cfg["check"]["gap_in"] * IN
        target = gap + 0.012                                    # clear enough: a later pass leaves it be
        segs = {S: {} for S in STATES}
        for S in STATES:
            for ln in self.lines:
                if S not in ln.st:
                    continue
                P = ln.path[S] if S in ln.path else self.centres(ln, S)
                segs[S][ln.name] = (P[:-1], P[1:], ln.r, (P.min(0) - ln.r, P.max(0) + ln.r))
        eyes = {}                                                # id(st) -> (P, ro, line)
        for ln, st in self.stations():
            if st.get("box") is not None:
                eyes[id(st)] = (np.asarray(st["at"][1], float), self.bullseye_r(ln, st.get("fit")), ln.name)
        blocks = {S: self.block_shapes(S) for S in STATES}
        twin = self.twin_lines() if pair else {}
        order = sorted(self.lines, key=lambda l: -sum(1 for st in l.st["Set"] if st.get("box") is not None))
        if pair:                                                 # a port rope's eyes follow its starboard twin's
            order = [ln for ln in order if not (ln.name in twin and ln.name.endswith(" port"))]
        if only is not None:
            order = [ln for ln in order if ln.name in only or (twin.get(ln.name) and twin[ln.name].name in only)]

        def scorer(ln, j, st, ro, mine):
            oth = [(q, r_, nm) for k_, (q, r_, nm) in eyes.items() if k_ not in mine]
            OQ = np.array([q for q, _, _ in oth]) if oth else np.zeros((0, 3))
            OR = np.array([r_ for _, r_, _ in oth]) if oth else np.zeros(0)
            other_eyes = [(q, r_) for q, r_, nm in oth if nm != ln.name]
            ro_d = eye_outer(st.get("fit"), ln.r)                # as drawn

            def score(P):
                if len(OQ):
                    dd = np.linalg.norm(OQ - P, axis=1) - OR - ro
                    if dd.min() < 0.01:
                        return -1.0 + dd.min()
                best = np.inf
                for S in STATES:
                    if S not in ln.st:
                        continue
                    sts = ln.st[S]
                    sv = self.solvers[S]
                    A = sv.centre(sts[j - 1])
                    nx = sts[j + 1]
                    B = self.pins.belay_point(nx["pin"], P, ln.r) if (nx["k"] == "pin" and nx.get("pin")) \
                        else sv.centre(nx)
                    legs = ((A, P), (P, B))
                    if st.get("r", 0.0) > 0.0:              # the rope bends round the thimble: its legs
                        u0, u1 = unit(A - P), unit(B - P)
                        nb = np.cross(u0, u1)
                        if np.linalg.norm(nb) > 1e-6:
                            pts, _ = wrap(A, B, P + unit(u0 + u1) * st["r"], unit(nb), st["r"])
                            legs = ((A, pts[0]), (pts[-1], B))
                    for a, b in legs:
                        d, _, _ = trace(C[S].bvh, a, b, ln.r + 0.12, skip, skip)
                        best = min(best, d - ln.r)
                        best = min(best, line_gap(a, b, ln.r, segs[S], ln.name))
                        for q, r_ in other_eyes:
                            best = min(best, pt_seg_d(q, a, b) - r_ - ln.r)
                        for shp in blocks[S]:
                            if ln.name not in shp[3]:
                                best = min(best, ell_seg_clear(shp, a, b, ln.r))
                    # this bull's eye (a ball of its outer radius) against the ship
                    loc, nrm, idx, dist = C[S].bvh.find_nearest(P, ro + 0.12)
                    best = min(best, (dist if idx is not None else ro + 0.12) - ro_d)
                    # this bull's eye against the other lines' ropes
                    for name, (A2, B2, r2, bb) in segs[S].items():
                        if name != ln.name and len(A2) and np.all(bb[0] < P + 0.3) and np.all(bb[1] > P - 0.3):
                            best = min(best, float(pt_segs_d(P, A2, B2).min()) - ro - r2)
                return best
            return score

        for p_ in range(passes):
            for ln in order:
                ln2 = twin.get(ln.name)
                for j, st in enumerate(ln.st["Set"]):
                    if st.get("box") is None:
                        continue
                    ro = self.bullseye_r(ln, st.get("fit"))
                    st2 = ln2.st["Set"][j] if ln2 is not None else None
                    if st2 is not None and st2.get("box") is None:
                        st2 = None
                    mine = {id(st)} | ({id(st2)} if st2 is not None else set())
                    s1 = scorer(ln, j, st, ro, mine)
                    if st2 is None:
                        score = s1
                    else:
                        ro2 = self.bullseye_r(ln2, st2.get("fit"))
                        s2 = scorer(ln2, j, st2, ro2, mine)

                        def score(P, s1=s1, s2=s2, ro=ro, ro2=ro2):
                            own = 2.0 * abs(float(P[1])) - ro - ro2     # the pair's eyes across the centreline
                            if own < 0.01:
                                return -1.0 + own
                            return min(s1(P), s2(MIRROR * P))

                    def put(Pb, sb):
                        st["at"] = ("ship", Pb)
                        st["score"] = sb
                        eyes[id(st)] = (Pb, ro, ln.name)
                        if st2 is not None:
                            st2["at"] = ("ship", MIRROR * Pb)
                            st2["score"] = sb
                            eyes[id(st2)] = (MIRROR * Pb, ro2, ln2.name)
                    mast, sg, box = st["box"]
                    (x0, x1), (y0, y1), (s0, s1_) = box
                    if (p_ > 0 or (warm and st.get("loaded"))) and st.get("score") is not None:
                        # a later pass, or a place given before: keep it while it is clear by the target
                        sc0 = score(np.asarray(st["at"][1], float))
                        if sc0 >= target:
                            put(np.asarray(st["at"][1], float), sc0)
                            if log is not None and p_ == passes - 1:
                                log.append((ln.name, j, round(float(sc0), 3)))
                            continue
                    cands = self.box_points(st["box"], (3, 3, 4))
                    sc = [score(P) for P in cands]
                    i = int(np.argmax(sc))
                    MG = self.mg[mast]
                    Pbest, sbest = cands[i], sc[i]
                    dx, dy, ds = (x1 - x0) / 4, (y1 - y0) / 4, (s1_ - s0) / 6
                    for refine in range(2):                     # a finer grid round the best, twice
                        q = MG.rel(Pbest)[0]
                        fine = []
                        for a in (-1, 0, 1):
                            for b in (-1, 0, 1):
                                for c in (-1, 0, 1):
                                    if a == b == c == 0:
                                        continue
                                    x = min(max(q[0] + a * dx, x0), x1)
                                    y = min(max(abs(q[1]) + b * dy, y0), y1)
                                    s = min(max(q[2] + c * ds, s0), s1_)
                                    fine.append(MG.lo(x, sg * y, s))
                        fs = [score(P) for P in fine]
                        k_ = int(np.argmax(fs))
                        if fs[k_] > sbest:
                            Pbest, sbest = fine[k_], fs[k_]
                        dx, dy, ds = dx / 2, dy / 2, ds / 2
                    put(Pbest, sbest)
                    if log is not None and p_ == passes - 1:
                        log.append((ln.name, j, round(float(sbest), 3)))
                for L in ((ln, ln2) if ln2 is not None else (ln,)):
                    for S in STATES:
                        if S not in L.st:
                            continue
                        P = self.centres(L, S)
                        segs[S][L.name] = (P[:-1], P[1:], L.r, (P.min(0) - L.r, P.max(0) + L.r))
        return self

    # -- what the lines must clear besides the ship: the rails and pins, and "no pass" sheets across each shroud ladder ---
    def extras(self):
        out = []
        V, F, M = self.rails.mesh.arrays()
        out.append(("PinRails", np.asarray(V, float), tris_of(F)))
        pm = pin_mesh(self.cfg["pins"]["handle_in"] * IN, self.cfg["pins"]["diam_in"] * IN,
                      self.cfg["pins"]["shank_in"] * IN)
        pv, pf, _ = pm.arrays()
        pv, pT = np.asarray(pv, float), tris_of(pf)
        Vs, Ts, n0 = [], [], 0
        for pid, pn in self.pins.pins.items():
            Vs.append(pv @ to_axis(pn["axis"]).T + pn["p"])
            Ts.append(pT + n0)
            n0 += len(pv)
        out.append(("Pins", np.concatenate(Vs), np.concatenate(Ts)))
        out += ladders(self.st)
        return out

    # -- a placement kept between builds ----------------------------------------------------------------------------------
    def places(self):
        """where the bull's eyes were put and which pin each fall was given, by line name and station index: written by
        a full placement so a later build starts from it ({"eyes": {line: {j: [x, y, z]}}, "pins": {line: {j: id}}})"""
        eyes, pins = {}, {}
        for ln in self.lines:
            for j, st in enumerate(ln.st["Set"]):
                if st.get("box") is not None:
                    eyes.setdefault(ln.name, {})[str(j)] = [round(float(v), 4) for v in st["at"][1]]
                if st["k"] == "pin" and st.get("zones") and st.get("pin"):
                    pins.setdefault(ln.name, {})[str(j)] = st["pin"]
        return {"note": "running.py's placement of the bull's eyes (ship, m) and the pins given out (by line name and "
                        "station index), kept so a build starts from it: build_frigate.py <out> --place-running places "
                        "everything afresh and rewrites this file", "eyes": eyes, "pins": pins}

    def load_places(self, P):
        """put the bull's eyes and pins back where an earlier placement left them (a station whose line or index is new,
        or whose place has left its box or whose pin is gone, keeps its default and is placed afresh); returns how many
        of each were missing (and the lines they are on, "lines")"""
        miss = {"eyes": 0, "pins": 0, "lines": set()}
        taken = set()
        for ln in self.lines:
            for j, st in enumerate(ln.st["Set"]):
                if st.get("box") is not None:
                    q = P["eyes"].get(ln.name, {}).get(str(j))
                    mast, sg, ((x0, x1), (y0, y1), (s0, s1)) = st["box"]
                    if q is not None:
                        x, y, s_ = self.mg[mast].rel(np.asarray(q, float))[0]
                        e = 1e-3
                        if x0 - e <= x <= x1 + e and y0 - e <= sg * y <= y1 + e and s0 - e <= s_ <= s1 + e:
                            st["at"] = ("ship", np.asarray(q, float))
                            st["loaded"], st["score"] = True, 0.0
                            continue
                    miss["eyes"] += 1
                    miss["lines"].add(ln.name)
                if st["k"] == "pin" and st.get("zones"):
                    pid = P["pins"].get(ln.name, {}).get(str(j))
                    pn = self.pins.pins.get(pid) if pid else None
                    tag = "s" if st["side"] > 0 else "p"
                    if pn is not None and pid not in taken and pn["zone"] in st["zones"] and not pn.get("reserved") \
                            and (not pn["zone"].startswith("fife") or pn.get("side") in ("c", tag)):
                        st["pin"] = pid
                        pn["line"] = ln.name
                        taken.add(pid)
                    else:
                        miss["pins"] += 1
                        miss["lines"].add(ln.name)
        return miss

    def symmetrize(self, C, log=None):
        """the port ropes made mirror images of their starboard twins (mirror_twins), then each pair's bull's eyes put
        together where both ropes stand clear, the single lines repinned, and the pairs repinned in mirrored pairs"""
        self.mirror_twins(C)
        self.solve()
        self.place_fairleads(C, passes=2, log=log, warm=True, pair=True)
        self.solve()
        tw = self.twin_lines()
        self.repin(C, log=log, only={ln.name for ln in self.lines if ln.name not in tw})
        self.repin_pairs(C, log=log)
        self.solve()
        return self

    def settle(self, C, places=None, replace=False, log=None):
        """solve every state, give each fall its pin and place the bull's eyes: from the placement in places (a json
        file) where it still fits, afresh where it doesn't (everywhere with replace, which then writes places), the
        pins traded last so that no two falls cross just above a side rail. A placement that fits everywhere is taken
        as it is, so a build is the same each time"""
        self.solve()
        P = json.load(open(places)) if (places and os.path.exists(places) and not replace) else None
        miss = self.load_places(P) if P else None
        if P is None:
            self.allocate_pins(C)
            self.solve()
            self.place_fairleads(C, passes=3, log=log)
            self.solve()
            self.allocate_pins(C)
            self.solve()
            self.place_fairleads(C, passes=1, log=log)
            self.solve()
            self.allocate_pins(C)
            self.solve()
            self.untangle_pins(C)
            self.solve()
            self.repin(C, log=log)
            self.solve()
            self.symmetrize(C, log=log)
            self.uncross_pins(C, log=log)
            self.solve()
            if places:
                json.dump(self.places(), open(places, "w"), indent=1)
        elif miss["pins"] or miss["eyes"]:
            # only the lines that lost a pin or a bull's eye's place (and their twins) are placed again: a pin each where
            # theirs is gone, the port twin mirrored, their eyes put where both twins stand clear, the single lines
            # among them repinned; then the placement is written, so the next build takes it as it is
            tw = self.twin_lines()
            aff = set(miss["lines"]) | {tw[n].name for n in miss["lines"] if n in tw}
            if miss["pins"]:
                self.allocate_pins(C, keep=True)
                self.solve()
            self.mirror_twins(C)
            self.solve()
            self.place_fairleads(C, passes=2, log=log, warm=True, pair=True, only=aff)
            self.solve()
            single = {n for n in aff if n not in tw}
            if single:
                self.repin(C, log=log, only=single)
                self.solve()
            if self.uncross_pins(C, log=log, only=aff):
                self.solve()
            if places:
                json.dump(self.places(), open(places, "w"), indent=1)
        else:
            self.solve()
        miss = {k: (sorted(v) if isinstance(v, set) else v) for k, v in miss.items()} if miss else miss
        return miss

    # -- what the game reads (running.json) and the build reports --------------------------------------------------------
    def game_data(self):
        """every line (group, size; in each state its centre line in the ship's frame and its stations, a bull's eye's
        or thimble's with its strop), every block (sheaves, length; in each state what it hangs from and on how long a
        pendant, or what it is fixed to, and its pose), the pins and kevels, and the coils hung on them"""
        def ref(at):
            fr, p_ = at
            return {"frame": fr or "ship", "p": [round(float(v), 4) for v in p_]}

        def vec(v):
            return [round(float(x), 4) for x in v]
        lines = []
        for ln in self.lines:
            d = {"name": ln.name, "group": ln.group, "circ_in": ln.circ, "radius_m": round(ln.r, 4), "states": {}}
            for S, sts in ln.st.items():
                stations = []
                for st in sts:
                    e = {"kind": st["k"]}
                    if "b" in st:
                        e["block"] = st["b"]
                        if st["k"] == "sheave":
                            e["sheave"] = st["i"]
                    elif st["k"] == "pin":
                        e["pin"] = st.get("pin")
                    elif "at" in st:
                        e.update(ref(st["at"]))
                    if st.get("fit"):
                        e["fit"] = st["fit"]
                    sp = st.get("strop", {}).get(S)
                    if sp is not None:
                        e["strop"] = {"from": vec(sp[0]), "to": vec(sp[1]), "holds": sp[2]}
                    stations.append(e)
                P = simplify(ln.path[S], max(0.001, self.cfg["mesh"]["simplify_of_r"] * ln.r))
                d["states"][S] = {"points": [vec(q) for q in P], "stations": stations}
            lines.append(d)
        blocks = []
        for bid, b in self.blocks.items():
            d = {"id": bid, "group": b.group, "sheaves": b.sheaves, "length_m": round(b.L, 4),
                 "drawn": not getattr(b, "hidden", False)}
            d["held"] = {}
            for S in b.pose:
                fx = getattr(b, "fixed_by", {}).get(S, b.fixed)
                if fx is not None:
                    fr, c, a, n = fx
                    d["held"][S] = {"fixed": {"frame": fr or "ship", "centre": vec(c), "crown_to_tail": vec(a),
                                              "pin": vec(n)}}
                else:
                    d["held"][S] = {"hangs_from": ref(getattr(b, "attach_by", {}).get(S, b.attach)),
                                    "pendant_m": round(float(getattr(b, "pendant_by", {}).get(S, b.pendant)), 3)}
            d["pose"] = {S: {"centre": vec(C), "crown_to_tail": vec(a), "pin": vec(n)} for S, (C, a, n) in b.pose.items()}
            blocks.append(d)
        pins = [{"id": pid, "zone": pn["zone"], "p": vec(pn["p"]), "axis": vec(pn["axis"]), "line": pn["line"]}
                for pid, pn in self.pins.pins.items()]
        kevels = [{"name": nm, "p": vec(p_), "normal": vec(n_)} for nm, p_, n_ in self.kevels]
        fit = getattr(self, "_coil_fit", {})
        coils = []
        for key, ln, st in self.coil_falls():
            sh, ws, lay = fit.get(key, (0.0, 1.0, 0.0))
            coils.append({"on": key, "line": ln.name, "shift_m": round(float(sh), 3), "width": round(float(ws), 2),
                          "off_rail_m": round(float(lay), 4)})
        return {"lines": lines, "blocks": blocks, "pins": pins, "kevels": kevels, "coils": coils}

    def summary(self):
        """counts for build.json"""
        groups = {}
        for ln in self.lines:
            groups[ln.group] = groups.get(ln.group, 0) + 1
        fits = {}
        for ln, st in self.stations():
            if st["k"] == "thru" and st.get("fit"):
                fits[st["fit"]] = fits.get(st["fit"], 0) + 1
        drawn = [b for b in self.blocks.values() if not getattr(b, "hidden", False)]
        return {"lines": len(self.lines), "lines_by_group": groups,
                "footropes_and_stirrups": sum(1 for ln in self.lines if " footrope " in ln.name or " stirrup " in ln.name),
                "blocks": len(drawn), "sheaves_in_spars": len(self.blocks) - len(drawn),
                "block_sheaves": sum(b.sheaves for b in drawn), "fittings": fits,
                "pins": len(self.pins.pins), "pins_used": sum(1 for pn in self.pins.pins.values() if pn["line"]),
                "kevels": len(self.kevels)}

    # -- meshes ----------------------------------------------------------------------------------------------------------
    def objects(self):
        """the running rigging's meshes, in the ship's frame: name -> (V, F, M, state). For each group (a mast's square
        gear, the headsails', the staysails', the spanker's, the spritsail yard's) and state, its ropes
        ("Running_<Group>_<State>") and its blocks with their pendants, the bull's eyes, thimbles and the sheaves in the
        side the ropes run through ("Blocks_<Group>_<State>"); the pin rails, pins, kevels, eyebolts and the coils on
        them, which never move ("PinRails", state None). Call after solve() and allocate_pins()."""
        out = {}
        tol = self.cfg["mesh"]["simplify_of_r"]
        for S in STATES:
            sv = self.solvers[S]
            ropes, gear = {}, {}
            for ln in self.lines:
                if S not in ln.path:
                    continue
                M = ropes.setdefault(ln.group, Mesh())
                P = simplify(ln.path[S], max(0.001, tol * ln.r))
                tube(M, P, ln.r, RUN, n=nsides(ln.r))
                G = gear.setdefault(ln.group, Mesh())
                self.mesh_fits(G, ln, S, sv)
            for b in self.blocks.values():
                if getattr(b, "hidden", False) or S not in b.pose:
                    continue
                self.mesh_block(gear.setdefault(b.group or "Main", Mesh()), b, S, sv)
            for g, M in ropes.items():
                out[f"Running_{g}_{S}"] = (*M.arrays(), S)
            for g, M in gear.items():
                if M.F:
                    out[f"Blocks_{g}_{S}"] = (*M.arrays(), S)
        out["PinRails"] = (*clean_faces(*self.mesh_static().arrays()), None)
        return out

    def _block_mesh(self, b):
        self._bm = getattr(self, "_bm", {})
        eye = not (getattr(b, "ring", None) is not None and b.fixed is not None)    # lashed: its strop round the spar
        k = (round(b.L, 4), b.sheaves, round(b.r_strop, 4), eye)
        if k not in self._bm:
            M, eye_top = block_mesh(b.L, b.sheaves, b.r_strop, eye=eye)
            V, F, Mt = M.arrays()
            self._bm[k] = (V, F, Mt, float(eye_top[2]))
        return self._bm[k]

    def mesh_block(self, out, b, S, sv):
        """a block in its pose in state S (its local Z up to the crown, Y along its pin), and its pendant from what it
        hangs from to its eye"""
        C, a, n = b.pose[S]
        Rm = np.stack([np.cross(n, -a), n, -a], 1)
        V, F, Mt, z_eye = self._block_mesh(b)
        for used, Fm, mat in by_material(F, Mt):
            out.add(C + V[used] @ Rm.T, Fm, mat)
        E = C - a * z_eye                                       # its eye's top (or its seizing's)
        ring = None
        if getattr(b, "ring", None) is not None:                # a strop round the spar it hangs from or is lashed to
            fr, c_, ax_, rho = b.ring
            o_, R_ = Pose(self.rig, S).frame(fr) if fr != "ship" else (np.zeros(3), np.eye(3))
            c_, ax_ = o_ + R_ @ np.asarray(c_, float), unit(R_ @ np.asarray(ax_, float))
            dn = (E - c_) - ((E - c_) @ ax_) * ax_                 # toward the block
            dn = unit(dn) if np.linalg.norm(dn) > 1e-6 else unit(np.cross(ax_, EX if abs(ax_[0]) < 0.9 else EY))
            e1 = np.cross(ax_, dn)
            th = np.linspace(0.0, 2.0 * math.pi, 16, endpoint=False)
            tube(out, c_[None] + rho * (np.cos(th)[:, None] * dn[None] + np.sin(th)[:, None] * e1[None]), b.r_strop,
                 STROP, n=6, closed=True)
            ring = c_ + rho * dn                                # its lowest turn, over the block
        if b.fixed is not None and ring is not None:
            if np.linalg.norm(ring - E) > 0.003:
                tube(out, np.array([E, ring]), 1.1 * b.r_strop, STROP, n=6)
        elif b.fixed is None and S not in getattr(b, "fixed_by", {}) and getattr(b, "pendant_drawn", True):
            pend = getattr(b, "pendant_by", {}).get(S, b.pendant)
            if pend > 0.02:
                A = ring if ring is not None else sv.at(getattr(b, "attach_by", {}).get(S, b.attach))
                tube(out, np.array([A, E]), 1.1 * b.r_strop, STROP, n=6)

    def mesh_fits(self, out, ln, S, sv):
        """the fittings a line runs through in state S: bull's eyes and thimbles turned along it, the sheaves in the side
        (a chesstree's in its oak chock)"""
        sts = ln.st[S]
        for j, st in enumerate(sts):
            fit = st.get("fit")
            if st["k"] != "thru" or fit is None or j == 0 or j == len(sts) - 1:
                continue
            P = sv.centre(st)
            u0 = unit(P - sv.centre(sts[j - 1]))
            u1 = unit(sv.centre(sts[j + 1]) - P)
            if fit in ("bullseye", "thimble"):
                key = (fit, round(ln.r, 4))
                self._fm = getattr(self, "_fm", {})
                if key not in self._fm:
                    if fit == "bullseye":
                        M_, ro = bullseye_mesh(ln.r)
                    else:
                        ri = ln.r * 1.25 + 0.1 * IN
                        M_ = ring_mesh(ri, eye_outer(fit, ln.r), 1.6 * ln.r, IRON)
                    self._fm[key] = M_.arrays()
                V, F, Mt = self._fm[key]
                P, Rm, ro = self.eye_frame(ln, sts, j, sv)
                out.add(P + V @ Rm.T, F, Mt[0])
                sp = st.get("strop", {}).get(S)
                if sp is not None and np.linalg.norm(sp[1] - sp[0]) > 0.003:   # its strop to what holds it
                    tube(out, np.array([sp[0], sp[1]]), strop_r(ln.r), STROP, n=6)
            elif fit in ("side_sheave", "chesstree"):
                nb = np.cross(u0, u1)
                if np.linalg.norm(nb) < 1e-4:
                    nb = np.cross(u0, EZ)
                nb = unit(nb)
                rs = 2.2 * ln.r + 0.02
                bis = unit(u1 - u0) if np.linalg.norm(u1 - u0) > 1e-4 else unit(np.cross(nb, u0))
                half = math.sqrt(max((1.0 + float(u0 @ u1)) / 2.0, 0.09))   # cos of half the turn
                c = P + bis * (rs + ln.r) / half                # inside the turn: both legs tangent to the groove
                D = disc_mesh(rs, 2.4 * ln.r + 0.01, SHEAVE)
                V, F, Mt = D.arrays()
                Rm = to_frame(nb, bis)
                out.add(c + V @ Rm.T, F, SHEAVE)
                if fit == "chesstree":                          # the oak chock bolted to the side round the sheave
                    side = np.array([0.0, np.sign(P[1]), 0.0])
                    yo = float((P - c) @ side) + 0.03          # its face just outboard of the rope's turn
                    yi = -0.06                                  # its back let into the planking
                    box_mesh(out, c + side * (yo + yi) / 2, EX * (rs + 0.07), side * (yo - yi) / 2,
                             EZ * (rs + 0.25), RAIL)

    @staticmethod
    def is_eye(st, j, sts):
        """whether station j of sts is a bull's eye or thimble the rope runs through"""
        return st["k"] == "thru" and st.get("fit") in ("bullseye", "thimble") and 0 < j < len(sts) - 1

    def eye_frame(self, ln, sts, j, sv):
        """a bull's eye's or thimble's place, its frame (its hole along local Z, turned along the rope) and outer radius"""
        st = sts[j]
        P = sv.centre(st)
        u0 = unit(P - sv.centre(sts[j - 1]))
        u1 = unit(sv.centre(sts[j + 1]) - P)
        Rm = to_frame(u0 + u1, np.cross(u0, u1) if np.linalg.norm(np.cross(u0, u1)) > 1e-3 else EZ)
        return P, Rm, eye_outer(st["fit"], ln.r)

    def seat_fairleads(self, C, gap=None):
        """strop each bull's eye and thimble a rope runs through to what can hold it (a mast, its top, cap, trestle- and
        crosstrees, a shroud or stay, the bowsprit, the spanker's boom or gaff, the channels or the rail). The strop is
        seized at one point for every state (the eye turns on it as its rope leads): the nearest such point seen from the
        eye or from round its rim, else where a ray from the eye meets one within a metre; the shortest that stands clear
        (by the gap, in every state) of the ship and the ropes, else the clearest. A port rope's eye takes the mirror
        image of its starboard twin's strop. st["strop"][state] = (rim point, point held, what)"""
        from mathutils import Vector
        gap = self.cfg["check"]["gap_in"] * IN if gap is None else gap
        CS = C["Set"]
        only = {lb for lb in CS.labels if lb.startswith(EYE_HOLDS)}
        sub = CS.local(CS.V.min(0) - 1.0, CS.V.max(0) + 1.0, only=only)
        segs = self.coil_line_segs()
        th = np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)
        k_ = np.arange(96) + 0.5                                 # rays spread evenly over the sphere
        zc = 1.0 - 2.0 * k_ / 96
        ph = math.pi * (1.0 + 5 ** 0.5) * k_
        rays = np.stack([np.cos(ph) * np.sqrt(1 - zc ** 2), np.sin(ph) * np.sqrt(1 - zc ** 2), zc], 1)
        twin = self.twin_lines()
        ok = gap + 0.001

        def clear(ln, S, P, Rm, ro, Q):
            """the strop held at Q in state S: its rim point, its clearance from the ship and the ropes, its length"""
            z = Rm[:, 2]
            d = (Q - P) - ((Q - P) @ z) * z
            R0 = P + (unit(d) if np.linalg.norm(d) > 1e-6 else Rm[:, 0]) * ro
            rs_ = strop_r(ln.r)
            nm, A, B, rr, tree, hmax = segs[S]
            L_ = float(np.linalg.norm(Q - R0))
            cl = np.inf
            if L_ > 0.031:                                      # the ship, but where it holds
                dd, _, ix = trace(C[S].bvh, R0, Q, rs_ + gap, 0.0, 0.03)
                if ix is not None:
                    cl = dd - rs_
            ids = np.array(tree.query_ball_point(0.5 * (R0 + Q), 0.5 * L_ + hmax + rs_ + 0.05), int)
            if len(ids):                                        # the ropes, but its own within the eye
                dl, _, p2 = seg_seg_closest(np.repeat(R0[None], len(ids), 0), np.repeat(Q[None], len(ids), 0),
                                            A[ids], B[ids])
                own = (nm[ids] == ln.name) & (np.linalg.norm(p2 - P[None], axis=1) < 2.5 * ro)
                cl = min(cl, float(np.where(own, np.inf, dl - rs_ - rr[ids]).min()))
            return R0, cl, L_

        def seat(ln, j):
            """the strop for ln's eye j: (key, {state: rim point}, point held, what)"""
            fr = {S: self.eye_frame(ln, ln.st[S], j, self.solvers[S]) for S in STATES if S in ln.st}
            P, Rm, ro = fr["Set"]

            def rate(Q, ix):
                R0s, worst, Lw = {}, np.inf, 0.0
                for S, (P_, Rm_, ro_) in fr.items():
                    R0s[S], cl, L_ = clear(ln, S, P_, Rm_, ro_, Q)
                    worst, Lw = min(worst, cl), max(Lw, L_)
                return ((min(worst, ok), -Lw), R0s, Q, sub.label(int(sub.lab[ix])))
            best = None
            for F_ in [P] + [P + ro * (math.cos(t) * Rm[:, 0] + math.sin(t) * Rm[:, 1]) for t in th]:
                loc, nrm, idx, dist = sub.bvh.find_nearest(Vector(tuple(map(float, F_))))
                if idx is not None:
                    c = rate(np.array(loc, float), idx)
                    if best is None or c[0] > best[0]:
                        best = c
            if best is None or best[0][0] < ok:                 # none clear: look round the eye
                for D in rays:
                    loc, nrm, idx, dist = sub.bvh.ray_cast(Vector(tuple(map(float, P))), Vector(tuple(map(float, D))), 1.0)
                    if idx is not None:
                        c = rate(np.array(loc, float), idx)
                        if best is None or c[0] > best[0]:
                            best = c
            return best

        done = set()
        for ln in self.lines:
            if ln.name in twin and ln.name.endswith(" port"):
                continue
            ln2 = twin.get(ln.name)
            for j, st in enumerate(ln.st["Set"]):
                if not self.is_eye(st, j, ln.st["Set"]):
                    continue
                best = seat(ln, j)
                if best is None:
                    continue
                _, R0s, Q, what = best
                st["strop"] = {S: (R0s[S], Q, what) for S in R0s}
                done.add(id(st))
                if ln2 is None or j >= len(ln2.st["Set"]) or not self.is_eye(ln2.st["Set"][j], j, ln2.st["Set"]):
                    continue
                st2 = ln2.st["Set"][j]
                if set(ln2.st) == set(ln.st) and all(np.linalg.norm(MIRROR * self.eye_frame(ln, ln.st[S], j, self.solvers[S])[0]
                                                                   - self.eye_frame(ln2, ln2.st[S], j, self.solvers[S])[0])
                                                    < 1e-3 for S in R0s):
                    st2["strop"] = {S: (MIRROR * R0s[S], MIRROR * Q, what) for S in R0s}
                    done.add(id(st2))
        for ln in self.lines:                                   # a port eye that is not its twin's mirror image
            for j, st in enumerate(ln.st["Set"]):
                if self.is_eye(st, j, ln.st["Set"]) and id(st) not in done:
                    best = seat(ln, j)
                    if best is not None:
                        st["strop"] = {S: (best[1][S], best[2], best[3]) for S in best[1]}
        return self

    def check_fittings(self, C, gap=None):
        """every bull's eye and thimble (as a ball of its outer radius) against the ship and the other ropes, and its
        strop against the ship (but its last 3 cm, where it holds) and the ropes (but its own within the eye): [(state,
        line, what, clearance m, where)] under the gap"""
        gap = self.cfg["check"]["gap_in"] * IN if gap is None else gap
        out = []
        segs = self.coil_line_segs()
        for S in STATES:
            CS, sv = C[S], self.solvers[S]
            nm, A, B, rr, tree, hmax = segs[S]
            for ln in self.lines:
                if S not in ln.st:
                    continue
                sts = ln.st[S]
                for j, st in enumerate(sts):
                    if not self.is_eye(st, j, sts):
                        continue
                    P, Rm, ro = self.eye_frame(ln, sts, j, sv)
                    d, who = CS.nearest(P[None], reach=ro + gap + 0.05)
                    if d[0] - ro < gap:
                        out.append((S, ln.name, f"{st['fit']} in {CS.label(int(who[0]))}", round(float(d[0] - ro), 4),
                                    np.round(P, 2)))
                    ie = np.array(tree.query_ball_point(P, ro + hmax + gap + 0.05), int)
                    if len(ie):                                 # the other ropes
                        de = np.where(nm[ie] == ln.name, np.inf, pt_segs_d(P, A[ie], B[ie]) - rr[ie] - ro)
                        k = int(np.argmin(de))
                        if de[k] < gap:
                            out.append((S, ln.name, f"{st['fit']} on {nm[ie[k]]}", round(float(de[k]), 4),
                                        np.round(P, 2)))
                    sp = st.get("strop", {}).get(S)
                    if sp is None:
                        continue
                    R0, Q = sp[0], sp[1]
                    rs_ = strop_r(ln.r)
                    if np.linalg.norm(Q - R0) > 0.031:
                        dd, p, idx = trace(CS.bvh, R0, Q, rs_ + gap, 0.0, 0.03)
                        if idx is not None and dd - rs_ < gap:
                            out.append((S, ln.name, f"{st['fit']}'s strop in {CS.label(int(CS.lab[idx]))}",
                                        round(float(dd - rs_), 4), np.round(p, 2)))
                    c_, h_ = 0.5 * (R0 + Q), 0.5 * float(np.linalg.norm(Q - R0))
                    idx = np.array(tree.query_ball_point(c_, h_ + hmax + rs_ + 0.05), int)
                    if not len(idx):
                        continue
                    dl, p1, p2 = seg_seg_closest(np.repeat(R0[None], len(idx), 0), np.repeat(Q[None], len(idx), 0),
                                                 A[idx], B[idx])
                    own = (nm[idx] == ln.name) & (np.linalg.norm(p2 - P[None], axis=1) < 2.5 * ro)
                    cl = np.where(own, np.inf, dl - rs_ - rr[idx])
                    k = int(np.argmin(cl))
                    if cl[k] < gap:
                        out.append((S, ln.name, f"{st['fit']}'s strop on {nm[idx[k]]}", round(float(cl[k]), 4),
                                    np.round(p1[k], 2)))
        return out

    def mesh_static(self):
        """the pin rails, pins, kevels, the eyebolts in the side and the coils hanging on every belayed pin and kevel"""
        M = Mesh()
        V, F, Mt = self.rails.mesh.arrays()
        for used, Fm, mat in by_material(F, Mt):
            M.add(np.asarray(V, float)[used], Fm, mat)
        pm = pin_mesh(self.cfg["pins"]["handle_in"] * IN, self.cfg["pins"]["diam_in"] * IN,
                      self.cfg["pins"]["shank_in"] * IN)
        pv, pf, _ = pm.arrays()
        for pid, pn in self.pins.pins.items():
            M.add(pv @ to_axis(pn["axis"]).T + pn["p"], pf, PINWOOD)
        q = self.cfg["mesh"]
        kv, kf, km = kevel_mesh(q["kevel_m"][0], q["kevel_m"][1]).arrays()
        for name, p, n in self.kevels:
            x = unit(np.cross(n, EZ))                           # (x, n, up) right-handed
            Rm = np.stack([x, n, EZ], 1)
            for mat in sorted(set(km)):
                idx = [i for i, m_ in enumerate(km) if m_ == mat]
                M.add(p + kv @ Rm.T, [kf[i] for i in idx], mat)
        for P, n, r in self.eyebolts():
            ev, ef, _ = eyebolt_mesh(max(1.6 * r, 0.03), max(0.6 * r, 0.012)).arrays()
            Rm = to_frame(n, EX if abs(n[0]) < 0.9 else EZ)
            M.add(P + ev @ Rm.T, ef, IRON)
        self.mesh_coils(M)
        return M

    def eyebolts(self):
        """(point, normal out of the surface, rope radius) of each eyebolt a rope's standing part is made fast to"""
        out = []
        S = "Set"
        sv = self.solvers[S]
        for ln in self.lines:
            if S not in ln.st:
                continue
            st = ln.st[S][0]
            if st.get("eyebolt") is not None:
                P, n = st["eyebolt"]
                out.append((np.asarray(P, float), unit(np.asarray(n, float)), ln.r))
        for b in self.blocks.values():
            if getattr(b, "eyebolt", False):                    # a block standing on an eyebolt (crown down)
                C, a, n = b.pose[S]
                out.append((C - a * (b.L / 2 + 0.07), a, b.r_strop))
            elif getattr(b, "hook", False):                     # a block hooked to an eyebolt in the deck
                out.append((sv.at(b.attach) - EZ * 0.05, EZ, b.r_strop))
        return out

    def coil_falls(self):
        """the belayed falls that end in a coil: [(key, line, station)] (one per pin or kevel)"""
        S = "Set"
        out, done = [], set()
        for ln in self.lines:
            if S not in ln.st:
                continue
            st = ln.st[S][-1]
            if st["k"] not in ("pin", "kevel"):
                continue
            key = st.get("pin") or st.get("name")
            if key in done or key is None:
                continue
            done.add(key)
            out.append((key, ln, st))
        return sorted(out, key=lambda o: pin_order(o[0]))

    def coil(self, ln, st, shift=0.0, ws=1.0, lay=0.0):
        """a fall's tail coiled down and hung on its pin (or kevel), as it came off: two loops hanging against the
        rail's face on the side away from what the rail stands on (inboard of a side rail, outside a fife rail, abaft a
        top's rail), each hung by a bight over the rail's edge round the pin's waist, as deep as the rope is heavy (and
        clear of the deck); shift: along the rail, ws: the loops' width, lay: hung that much further off the rail (over
        a neighbour's coil). [(points, radius, closed)]"""
        q = self.cfg["mesh"]["coil"]
        hw = 0.5 * self.cfg["pins"]["rail_in"][0] * IN           # the rail's half width (a top's rail bar's too)
        r = ln.r
        if st["k"] == "pin":
            pn = self.pins.pins[st["pin"]]
            up = pn["axis"]
            base = pn["p"]                                      # the rail's top at the pin
            o = pn.get("out", -EY * np.sign(base[1]))
            waist = base + up * (0.45 * pn["h"])
            w_out = 0.4 * pn["d"] + r
            off0 = hw + r + 0.015
        else:
            up = EZ
            base = self.solvers["Set"].centre(st)
            o = -EY * np.sign(base[1])
            waist = base
            w_out = 0.0
            off0 = 0.015 + r                                    # its belaying point is already off the kevel
        off0 += lay
        along = unit(np.cross(up, o))
        h0 = min(q["drop_max_m"], q["drop_of_circ"] * ln.circ + 0.15)
        if not pn_zone_aloft(st, self.pins):                    # on deck: clear of the deck under it
            h0 = min(h0, float(base[2] - self.deck.z(float(base[0]))) - 0.06 - 2 * r)
        th = np.linspace(0, 2 * math.pi, q["points"], endpoint=False)
        out = []
        for k in range(2):
            h = h0 - 0.04 * k
            w = 0.32 * h * ws
            off = off0 + k * (2 * r + 0.004)
            top = base + o * off - up * (0.015 + r)
            c = top - up * (0.5 * h) + along * (shift + 0.03 * k * ws)
            P = c[None] + (0.5 * h) * np.sin(th)[:, None] * up[None] + w * np.cos(th)[:, None] * along[None]
            out.append((P, r, True))
            # the bight up from the loop's top, over the rail's edge, round the pin's waist
            lift = float((waist - base) @ up)
            hook = np.array([c + up * (0.5 * h), base + o * off + along * (shift + 0.03 * k * ws) + up * (0.5 * lift),
                             base + o * (0.5 * (off + w_out)) + along * (0.5 * shift) + up * lift, waist + o * w_out])
            out.append((hook, r, False))
        return out

    def place_coils(self, C, gap=None):
        """hang each coil where it stands clear (by the gap) of the ship, the rails, pins and kevels, the ropes (in every
        state) and the coils hung before it along its rail: as drawn, or shifted a little along its rail, or hung over its
        neighbour's coil, or narrower (by a corner or a post of a fife rail)"""
        gap = self.cfg["check"]["gap_in"] * IN if gap is None else gap
        self._coil_fit = {}
        segs = self.coil_line_segs()
        hung = []                                               # (key, parts) of the coils hung so far
        for key, ln, st in self.coil_falls():
            best = None
            step = 4 * ln.r + gap + 0.008                       # over a neighbour's coil of the same rope
            for ws in (1.0, 0.75, 0.55):
                for lay in (0.0, step, 2 * step):
                    for shift in (0.0, 0.04, -0.04, 0.08, -0.08):
                        parts = self.coil(ln, st, shift, ws, lay)
                        w_ = min(min(coil_clear(C, parts, gap)), coil_ropes_clear(parts, ln.name, segs),
                                 coil_coils_clear(parts, hung))
                        if best is None or w_ > best[0] + 1e-4:
                            best = (w_, shift, ws, lay, parts)
                        if w_ >= gap + 0.003:
                            break
                    if best[0] >= gap + 0.003:
                        break
                if best[0] >= gap + 0.003:
                    break
            self._coil_fit[key] = best[1:4]
            hung.append((key, best[4]))
        return self

    def coil_line_segs(self):
        """the ropes' segments in each state, for the coils' check: {state: (names, A, B, radii, tree of midpoints,
        greatest half length)}"""
        from scipy.spatial import cKDTree
        out = {}
        for S in STATES:
            nm, A, B, rr = [], [], [], []
            for ln in self.lines:
                if S not in ln.path:
                    continue
                P = ln.path[S]
                nm += [ln.name] * (len(P) - 1)
                A.append(P[:-1])
                B.append(P[1:])
                rr += [ln.r] * (len(P) - 1)
            A, B = np.concatenate(A), np.concatenate(B)
            out[S] = (np.array(nm), A, B, np.array(rr), cKDTree(0.5 * (A + B)),
                      float(0.5 * np.linalg.norm(B - A, axis=1).max()))
        return out

    def coils(self):
        """every coil's parts, hung as place_coils fitted them: [(points, radius, closed)]"""
        fit = getattr(self, "_coil_fit", {})
        out = []
        for key, ln, st in self.coil_falls():
            out += self.coil(ln, st, *fit.get(key, (0.0, 1.0, 0.0)))
        return out

    def mesh_coils(self, M):
        """the coils (coils) as tubes"""
        for P, r, closed in self.coils():
            tube(M, P, r, RUN, n=5, closed=closed)

    def check_coils(self, C, gap=None):
        """every coil against the ship, the rails and pins (its bight may touch its own pin, within 5 cm of the pin's
        waist), the ropes in every state but its own, and the other coils: [(what, clearance m, where)] under the gap"""
        gap = self.cfg["check"]["gap_in"] * IN if gap is None else gap
        fit = getattr(self, "_coil_fit", {})
        segs = self.coil_line_segs()
        out, hung = [], []
        for key, ln, st in self.coil_falls():
            parts = self.coil(ln, st, *fit.get(key, (0.0, 1.0, 0.0)))
            out += [(ln.name + " coil: " + w, d, p) for w, d, p in coil_hits(C, parts, gap)]
            d = coil_ropes_clear(parts, ln.name, segs, what=True)
            if d[0] < gap:
                out.append((ln.name + " coil: " + d[1], round(d[0], 4), np.round(d[2], 2)))
            for k2, p2 in hung:
                d = coil_coils_clear(parts, [(k2, p2)])
                if d < gap:
                    out.append((ln.name + " coil: the coil on " + k2, round(d, 4), np.round(parts[0][0].mean(0), 2)))
            hung.append((key, parts))
        return out

    def check_blocks(self, C, gap=None, only=None):
        """every drawn block's shell (its ellipsoid below the crown: the strop's eye may touch what it hangs from)
        against the ship, the rails and pins, the ladders, and the other blocks: [(state, block, what, clearance m,
        where)] under the gap"""
        gap = self.cfg["check"]["gap_in"] * IN if gap is None else gap
        out = []
        u, v = np.meshgrid(np.linspace(0, 2 * math.pi, 16, endpoint=False), np.linspace(-1.0, 1.0, 9))
        u, v = u.ravel(), v.ravel()
        sph = np.stack([np.sqrt(1 - v ** 2) * np.cos(u), np.sqrt(1 - v ** 2) * np.sin(u), v], 1)
        for S in STATES:
            shapes = []
            for bid, b in self.blocks.items():
                if getattr(b, "hidden", False) or S not in b.pose:
                    continue
                C0, a, n = b.pose[S]
                e = unit(np.cross(a, n))
                n = unit(np.cross(e, a))
                za = 0.5 * (b.L / 2 - b.eye_drop)
                sa = 0.5 * (b.L / 2 + b.eye_drop)
                E = np.array([e, n, a])
                sem = np.array([b.w / 2 + b.r_strop, b.t / 2 + b.r_strop, sa])
                c = C0 + a * za
                Q = c[None] + (sph * sem[None]) @ E
                Q = Q[(Q - C0[None]) @ a > -b.L / 2]              # the shell and its strop, not the eye over the crown
                shapes.append((bid, c, E, sem, Q))
                if only is not None and bid not in only:
                    continue
                d, who = C[S].nearest(Q, reach=0.2)
                rest = getattr(b, "rests_on", {}).get(S)
                if rest is not None:
                    d = np.where(np.array([C[S].label(int(w)) == rest for w in who]), np.inf, d)
                i = int(np.argmin(d))
                if d[i] < gap:
                    out.append((S, bid, C[S].label(int(who[i])), round(float(d[i]), 4), np.round(Q[i], 2)))
            for i in range(len(shapes)):
                for j in range(i + 1, len(shapes)):
                    b1, c1, E1, s1, Q1 = shapes[i]
                    b2, c2, E2, s2, Q2 = shapes[j]
                    if only is not None and b1 not in only and b2 not in only:
                        continue
                    if np.linalg.norm(c1 - c2) > s1.max() + s2.max() + gap:
                        continue
                    rho = np.sqrt(np.sum((((Q1 - c2[None]) @ E2.T) / (s2 + gap)[None]) ** 2, axis=1))
                    k = int(np.argmin(rho))
                    if rho[k] < 1.0:
                        out.append((S, b1, "block " + b2, round(float((rho[k] - 1.0) * s2.min()), 4), np.round(Q1[k], 2)))
        return out

    def check(self, C, gap=None, skip=None, only=None):
        """every line against the ship (and rails, pins, the shroud ladders) and against the other lines, in each state:
        [(state, line, what, clearance m, where)] under the gap"""
        gap = self.cfg["check"]["gap_in"] * IN if gap is None else gap
        skip = self.cfg["check"]["skip_end_in"] * IN if skip is None else skip
        out = []
        from scipy.spatial import cKDTree
        for S in STATES:
            sv = self.solvers[S]
            samp, own, stns = [], [], {}
            obst = []                                            # (point, radius, (owner line or None, label))
            for ln_, st in self.stations():
                if st.get("box") is not None:
                    obst.append((np.asarray(st["at"][1], float), self.bullseye_r(ln_, st.get("fit")),
                                 (ln_.name, st.get("fit", "fairlead") + " of " + ln_.name)))
            shapes = self.block_shapes(S)
            for li, ln in enumerate(self.lines):
                if S not in ln.path:
                    continue
                P = ln.path[S]
                stn = np.array([sv.centre(st) for st in ln.st[S]])
                touch = np.array([max(skip, getattr(self.blocks.get(st.get("b")), "touch", 0.0), st.get("touch", 0.0),
                                      getattr(self.blocks.get(st.get("b")), "touch_by", {}).get(S, 0.0))
                                  for st in ln.st[S]])
                mine = only is None or ln.name in only
                # the ship
                CS = self.clearance_for(C, S, ln) if mine else C[S]
                worst = (np.inf, None, None)
                for a, b in (zip(P[:-1], P[1:]) if mine else ()):
                    d, p, idx = trace(CS.bvh, a, b, ln.r + gap, 0.0, 0.0, stations=stn, skip=touch)
                    if d < worst[0]:
                        worst = (d, p, idx)
                if worst[0] - ln.r < gap:
                    out.append((S, ln.name, CS.label(int(CS.lab[worst[2]])) if worst[2] is not None else None,
                                round(float(worst[0] - ln.r), 4), np.round(worst[1], 2)))
                # what it may press into (cloth), as far as that gives
                CF = self.clearance_for(C, S, ln, soft=True) if mine else None
                if CF is not None:
                    give = ln.soft[S]
                    worst = (np.inf, None, None)
                    for a, b in zip(P[:-1], P[1:]):
                        d, p, idx = trace(CF.bvh, a, b, ln.r + gap, 0.0, 0.0, stations=stn, skip=touch)
                        if d < worst[0]:
                            worst = (d, p, idx)
                    if worst[2] is not None:                    # into it by its give, and half its radius at most
                        lab = CF.label(int(CF.lab[worst[2]]))
                        if worst[0] - ln.r < -min(give.get(lab, 0.0), 0.5 * ln.r):
                            out.append((S, ln.name, lab, round(float(worst[0] - ln.r), 4), np.round(worst[1], 2)))
                # the other lines' bull's eyes and every block the line doesn't run through
                for q, r_, what in obst:
                    if what[0] == ln.name or (isinstance(what[0], set) and ln.name in what[0]):
                        continue
                    if not mine and what[0] not in only:
                        continue
                    d = float(pt_segs_d(q, P[:-1], P[1:]).min()) - r_ - ln.r
                    if d < gap:
                        out.append((S, ln.name, what[1], round(d, 4), np.round(q, 2)))
                for shp in shapes:
                    if ln.name in shp[3]:
                        continue
                    if not mine and not (shp[3] & only):
                        continue
                    if float(pt_segs_d(shp[0], P[:-1], P[1:]).min()) > shp[2].max() + ln.r + gap:
                        continue
                    d = min(ell_seg_clear(shp, a, b, ln.r) for a, b in zip(P[:-1], P[1:]))
                    if d < gap:
                        out.append((S, ln.name, "a block of " + ", ".join(sorted(shp[3])), round(float(d), 4),
                                    np.round(shp[0], 2)))
                # the line against itself: a part doubled back on, or across, another part of it
                if mine:
                    sc = self_clear(P, ln.r, stn, skip, gap)
                    if sc is not None:
                        out.append((S, ln.name, "itself", round(sc[0], 4), np.round(sc[1], 2)))
                # samples every 3 cm (beyond skip of its stations) to find the other lines' segments near each segment
                seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
                for k_, (a, b, L) in enumerate(zip(P[:-1], P[1:], seg)):
                    n = max(1, int(math.ceil(L / 0.03)))
                    t = (np.arange(n) + 0.5) / n
                    Q = a[None] + t[:, None] * (b - a)[None]
                    dmin = np.min(np.linalg.norm(Q[:, None] - stn[None], axis=2), axis=1)
                    keep = dmin > skip
                    samp.append(Q[keep])
                    own.append(np.stack([np.full(int(keep.sum()), li), np.full(int(keep.sum()), k_)], 1))
                stns[li] = stn
            Q = np.concatenate(samp)
            O = np.concatenate(own)
            Rr = np.array([ln.r for ln in self.lines])
            tree = cKDTree(Q)
            # two samples each within 1.5 cm of their segments' nearest points: look 3 cm further, then measure exactly
            pairs = tree.query_pairs(2 * Rr.max() + gap + 0.031, output_type="ndarray")
            if len(pairs):
                a, b = pairs[:, 0], pairs[:, 1]
                keep = O[a, 0] != O[b, 0]
                A_, B_ = O[a[keep]], O[b[keep]]
                sw = A_[:, 0] > B_[:, 0]
                A_[sw], B_[sw] = B_[sw].copy(), A_[sw].copy()
                U = np.unique(np.concatenate([A_, B_], 1), axis=0)
                if len(U):
                    Pth = {li: self.lines[li].path[S] for li in set(U[:, 0]) | set(U[:, 2])}
                    P1 = np.array([Pth[i][k] for i, k in zip(U[:, 0], U[:, 1])])
                    Q1 = np.array([Pth[i][k + 1] for i, k in zip(U[:, 0], U[:, 1])])
                    P2 = np.array([Pth[i][k] for i, k in zip(U[:, 2], U[:, 3])])
                    Q2 = np.array([Pth[i][k + 1] for i, k in zip(U[:, 2], U[:, 3])])
                    d, C1, C2 = seg_seg_closest(P1, Q1, P2, Q2)
                    d = d - Rr[U[:, 0]] - Rr[U[:, 2]]
                    seen = {}
                    for m_ in np.nonzero(d < gap)[0]:
                        i, j_ = int(U[m_, 0]), int(U[m_, 2])
                        # within skip of one of either line's own stations: where it is held, it may touch
                        if np.min(np.linalg.norm(stns[i] - C1[m_], axis=1)) <= skip or \
                                np.min(np.linalg.norm(stns[j_] - C2[m_], axis=1)) <= skip:
                            continue
                        if (i, j_) not in seen or d[m_] < seen[(i, j_)][0]:
                            seen[(i, j_)] = (float(d[m_]), C1[m_])
                    for (i, j_), (dd, p) in seen.items():
                        if only is not None and self.lines[i].name not in only and self.lines[j_].name not in only:
                            continue
                        out.append((S, self.lines[i].name, "line " + self.lines[j_].name, round(dd, 4), np.round(p, 2)))
        return out


# ---- clearance helpers -------------------------------------------------------------------------------------------------
def trace(bvh, A, B, m, skip_a=0.0, skip_b=0.0, reach=3.0, step_min=0.01, stations=None, skip=0.0):
    """the least distance from the segment A..B's points (beyond skip_a from A and skip_b from B, and beyond skip of
    any of stations) to the BVH's triangles, exact where it is under m (sphere tracing): (distance, point, triangle)"""
    v = np.asarray(B, float) - A
    L = float(np.linalg.norm(v))
    if L < 1e-9:
        return np.inf, None, None
    e = v / L
    t, t1 = min(skip_a, L), L - skip_b
    best = (np.inf, None, None)
    while t <= t1 + 1e-9:
        p = A + e * t
        if stations is not None and len(stations) and np.any(np.linalg.norm(stations - p, axis=1) < skip):
            t += step_min
            continue
        loc, nrm, idx, dist = bvh.find_nearest(p, reach)
        if idx is None:
            dist = reach
        if dist < best[0]:
            best = (dist, p, idx)
        t += max(dist - m, step_min)
    return best


def pn_zone_aloft(st, pins):
    """whether a fall's pin is aloft (in a top)"""
    return st["k"] == "pin" and pins.pins[st["pin"]]["zone"].startswith("top_")


def coil_hits(C, parts, gap):
    """a coil's parts (points, radius, closed) against the ship set, the bight's last 5 cm (round its pin) let off:
    [(what, clearance m, where)] under the gap"""
    CS = C["Set"]
    out = []
    for P, r, closed in parts:
        Q = np.concatenate([P, P[:1]]) if closed else P
        for i in range(len(Q) - 1):
            last = not closed and i == len(Q) - 2
            d, p, idx = trace(CS.bvh, Q[i], Q[i + 1], r + gap, 0.0, 0.05 if last else 0.0)
            if idx is not None and d - r < gap:
                out.append((CS.label(int(CS.lab[idx])), round(float(d - r), 4), np.round(p, 2)))
    return out


def pin_order(key):
    """a pin's (or kevel's) place in its rail's order: (rail, number)"""
    a, _, b = str(key).rpartition(":")
    return (a, int(b)) if a and b.isdigit() else (str(key), -1)


def coil_ropes_clear(parts, name, segs, what=False):
    """how clear a coil's parts stand of the ropes (but its own) in every state (coil_line_segs): the least clearance,
    or with what (clearance, rope and state, where)"""
    best = (np.inf, None, None)
    for S, (nm, A, B, rr, tree, hmax) in segs.items():
        for P, r, closed in parts:
            Q = np.concatenate([P, P[:1]]) if closed else P
            a, b = Q[:-1], Q[1:]
            c, h = 0.5 * (a + b), 0.5 * np.linalg.norm(b - a, axis=1)
            for i, idx in enumerate(tree.query_ball_point(c, h + hmax + r + 0.05)):
                idx = np.array([j for j in idx if nm[j] != name], int)
                if not len(idx):
                    continue
                d, p, _ = seg_seg_closest(np.repeat(a[i][None], len(idx), 0), np.repeat(b[i][None], len(idx), 0),
                                          A[idx], B[idx])
                cl = d - r - rr[idx]
                k = int(np.argmin(cl))
                if cl[k] < best[0]:
                    best = (float(cl[k]), f"{nm[idx[k]]} ({S})", p[k])
    return best if what else best[0]


def coil_coils_clear(parts, hung):
    """how clear a coil's parts stand of the coils hung before it [(key, parts)]: the least clearance"""
    best = np.inf
    Qs = [(np.concatenate([P, P[:1]]) if closed else P, r) for P, r, closed in parts]
    lo = np.min([Q.min(0) for Q, _ in Qs], 0) - 0.1
    hi = np.max([Q.max(0) for Q, _ in Qs], 0) + 0.1
    for _, p2 in hung:
        for P2, r2, closed2 in p2:
            Q2 = np.concatenate([P2, P2[:1]]) if closed2 else P2
            if (Q2.max(0) < lo).any() or (Q2.min(0) > hi).any():
                continue
            a2, b2 = Q2[:-1], Q2[1:]
            for Q, r in Qs:
                for a, b in zip(Q[:-1], Q[1:]):
                    d, _, _ = seg_seg_closest(np.repeat(a[None], len(a2), 0), np.repeat(b[None], len(a2), 0), a2, b2)
                    best = min(best, float(d.min()) - r - r2)
    return best


def coil_clear(C, parts, gap):
    """how clear a coil's parts stand of the ship set (as coil_hits measures): each part's least clearance"""
    CS = C["Set"]
    out = []
    for P, r, closed in parts:
        Q = np.concatenate([P, P[:1]]) if closed else P
        w = np.inf
        for i in range(len(Q) - 1):
            last = not closed and i == len(Q) - 2
            d, p, idx = trace(CS.bvh, Q[i], Q[i + 1], r + gap + 0.01, 0.0, 0.05 if last else 0.0)
            w = min(w, d - r)
        out.append(w)
    return out


def seg_seg_closest(P1, Q1, P2, Q2):
    """the nearest points of segments P1..Q1 and P2..Q2 (arrays of N): (distances, points on the first, on the second)"""
    eps = 1e-12
    d1, d2, r = Q1 - P1, Q2 - P2, P1 - P2
    a, e = (d1 * d1).sum(1), (d2 * d2).sum(1)
    b, c, f = (d1 * d2).sum(1), (d1 * r).sum(1), (d2 * r).sum(1)
    a_ok, e_ok = a > eps, e > eps
    a1, e1 = np.where(a_ok, a, 1.0), np.where(e_ok, e, 1.0)
    den = a * e - b * b
    s = np.where(den > eps, np.clip((b * f - c * e) / np.where(den > eps, den, 1.0), 0.0, 1.0), 0.0)
    t = (b * s + f) / e1
    s = np.where(t < 0.0, np.clip(-c / a1, 0.0, 1.0), np.where(t > 1.0, np.clip((b - c) / a1, 0.0, 1.0), s))
    t = np.clip(t, 0.0, 1.0)
    s = np.where(a_ok, np.where(e_ok, s, np.clip(-c / a1, 0.0, 1.0)), 0.0)
    t = np.where(e_ok, np.where(a_ok, t, np.clip(f / e1, 0.0, 1.0)), 0.0)
    C1 = P1 + d1 * s[:, None]
    C2 = P2 + d2 * t[:, None]
    return np.linalg.norm(C1 - C2, axis=1), C1, C2


def self_clear(P, r, stn, skip, gap, step=0.005):
    """the least clearance between two parts of one rope that are more than 4 r + 5 cm apart along it (a hairpin, or a
    part across another: a tackle with a turn in it), away from its stations (skip): (clearance m, where) when it is
    under gap, else None"""
    from scipy.spatial import cKDTree
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = int(s[-1] / step) + 2
    ss = np.linspace(0.0, s[-1], n)
    Q = np.stack([np.interp(ss, s, P[:, i]) for i in range(3)], 1)
    ok = np.min(np.linalg.norm(Q[:, None] - np.asarray(stn)[None], axis=2), axis=1) > skip
    pairs = cKDTree(Q).query_pairs(2 * r + gap, output_type="ndarray")
    if not len(pairs):
        return None
    i, j = pairs[:, 0], pairs[:, 1]
    sel = (np.abs(ss[i] - ss[j]) > 4 * r + 0.05) & ok[i] & ok[j]
    if not sel.any():
        return None
    d = np.linalg.norm(Q[i[sel]] - Q[j[sel]], axis=1) - 2 * r
    k = int(np.argmin(d))
    return (float(d[k]), Q[i[sel][k]]) if d[k] < gap else None


def ell_seg_clear(shp, a, b, r):
    """about how far the rope a..b (radius r) stands clear of the ellipsoid shp (negative: inside it): along the
    segment's points nearest the centre, the normalised radius less one, times the least semi-axis"""
    c, E, sem = shp[0], shp[1], shp[2]
    v = b - a
    L = float(np.linalg.norm(v))
    if pt_seg_d(c, a, b) > sem.max() + r + 0.05:
        return 1.0
    n = max(2, int(math.ceil(L / 0.01)))
    t = np.linspace(0.0, 1.0, n + 1)
    Q = a[None] + t[:, None] * v[None] - c[None]
    loc = Q @ E.T
    rho = np.sqrt(np.sum((loc / (sem + r)[None]) ** 2, axis=1))
    return float((rho.min() - 1.0) * (sem.min() + r))


def pt_seg_d(q, a, b):
    """distance from the point q to the segment a..b"""
    v = b - a
    L2 = float(v @ v)
    t = 0.0 if L2 < 1e-12 else min(max(float((q - a) @ v) / L2, 0.0), 1.0)
    return float(np.linalg.norm(a + t * v - q))


def pt_segs_d(q, A, B):
    """distances from the point q to each segment A[i]..B[i]"""
    V = B - A
    L2 = np.einsum("ij,ij->i", V, V)
    t = np.clip(np.einsum("ij,ij->i", q[None] - A, V) / np.where(L2 > 1e-12, L2, 1.0), 0.0, 1.0)
    return np.linalg.norm(A + t[:, None] * V - q[None], axis=1)


def line_gap(a, b, r, segs, me, reach=0.3):
    """the least gap between the rope a..b (radius r) and the other lines' segments (those within reach of it; beyond
    reach, the gap is reported as reach)"""
    best = reach
    lo = np.minimum(a, b) - reach - r
    hi = np.maximum(a, b) + reach + r
    for name, v in segs.items():
        if name == me or not len(v[0]):
            continue
        A, B, r2 = v[:3]
        bb = v[3] if len(v) > 3 else None
        if bb is not None and (np.any(bb[1] < lo) or np.any(bb[0] > hi)):
            continue
        d = seg_seg(a, b, A, B) - r - r2
        best = min(best, float(d.min()))
    return best


def side_cross(a1, b1, a2, b2, above):
    """where two falls (a: from the fairlead, b: to the pin) cross seen from inboard (on x and z), if they do within
    above of the higher pin: the point (x, z), else None"""
    A1, B1, A2, B2 = (np.asarray(v, float)[[0, 2]] for v in (a1, b1, a2, b2))
    u, v, w = B1 - A1, B2 - A2, A1 - A2
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < 1e-12:
        return None
    s = (v[0] * w[1] - v[1] * w[0]) / den
    t = (u[0] * w[1] - u[1] * w[0]) / den
    if not (0.0 < s < 1.0 and 0.0 < t < 1.0):
        return None
    X = A1 + s * u
    return X if X[1] < max(B1[1], B2[1]) + above else None


def seg_seg(a, b, C, D):
    """the least distances between the segment a..b and each segment C[i]..D[i]"""
    d1 = b - a
    d2 = D - C
    r = a[None] - C
    A_ = float(d1 @ d1)
    E = np.einsum("ij,ij->i", d2, d2)
    F = np.einsum("ij,ij->i", d2, r)
    c = r @ d1
    bb = d2 @ d1
    den = A_ * E - bb * bb
    s = np.where(den > 1e-12, np.clip((bb * F - c * E) / np.where(den > 1e-12, den, 1.0), 0.0, 1.0), 0.0)
    t = (bb * s + F) / np.where(E > 1e-12, E, 1.0)
    lo, hi = t < 0.0, t > 1.0
    s = np.where(lo, np.clip(-c / max(A_, 1e-12), 0.0, 1.0), np.where(hi, np.clip((bb - c) / max(A_, 1e-12), 0.0, 1.0), s))
    t = np.clip(t, 0.0, 1.0)
    P = a[None] + s[:, None] * d1[None]
    Q = C + t[:, None] * d2
    return np.linalg.norm(P - Q, axis=1)


def ladders(st):
    """a sheet across each shroud set's ladder (between neighbouring shrouds, deadeye to masthead), both sides: no line
    may pass between two shrouds"""
    out = []
    for (mast, sset, sgn), lines in st.shroud_lines.items():
        V, T = [], []
        f = np.array([1.0, float(sgn), 1.0])
        for a, b in zip(lines[:-1], lines[1:]):
            n0 = len(V)
            for P in (a[1], a[0], b[0], b[1]):
                V.append(np.asarray(P, float) * f)
            T += [(n0, n0 + 1, n0 + 2), (n0, n0 + 2, n0 + 3)]
        if T:
            out.append((f"Ladder_{mast}_{sset}_{'s' if sgn > 0 else 'p'}", np.array(V), np.array(T)))
    return out
