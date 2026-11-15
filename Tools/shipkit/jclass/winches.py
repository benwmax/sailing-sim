"""Bluebonnet's winches and cleats (docs/jclass-7), from running_bluebonnet.json: the parts, and the ropework that goes
round them (turns on a drum, a cleat hitch, a flemished coil).

  capstan(part, at, size, pad, group)   a bronze capstan winch on its teak pad: a skirted base flange bolted down, the
                                        pawls' band, a ribbed drum flaring at its foot, a domed cap with the handle's
                                        square socket. Returns its geometry (axis, drum radius, the turns' heights).
  reel(part, at, pad, group)            a reel winch for a wire halyard: the same base, a brake drum, a flanged reel
                                        with the wire stored on it, the cap and socket.
  cleat(part, at, heading, size, group) a bronze horn cleat on two feet. Returns its frame.
  turns(...), cleat_hitch(...), coil(...)  centrelines of a rope's turns round a drum, its hitch on a cleat (the kit's
                                        Tools/boatkit/bk_ropework.cleat_hitch, in numpy) and its tail flemished down.

Each part is a set of closed solids labelled "<group> | <kind>" (kinds: winch, drum, pad, socket, reel, wire on reel,
cleat), weighed by the material's density ('winch_fill' of solid bronze for a winch's hollow body). Units are metres in
the hull's frame (X forward, Y starboard, Z up). Plain Python: no Blender needed.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck  # noqa: E402
import shell  # noqa: E402
import spars  # noqa: E402
from spars import unit, BRZ, UP  # noqa: E402

RN = json.load(open(os.path.join(HERE, "running_bluebonnet.json")))
W = RN["winch"]
FILL = RN["material"]["winch_fill"]
TEAK = RN["material"]["teak"]
X = np.array([1.0, 0.0, 0.0])


def lab(group, kind):
    return f"{group} | {kind}"


def deck_z(x, y):
    return float(shell.deck_z(np.array([x]), np.array([y]))[0])


def cw(v):
    """v (plan) turned 90 degrees clockwise seen from above: +X (forward) to +Y (starboard). The hull's frame is
    left-handed seen from above, so an angle measured from +X toward +Y grows clockwise seen from above."""
    return np.array([-v[1], v[0], 0.0])


def _solid(part, V, F, slot, label, mass):
    V = np.asarray(V, float)
    if deck.signed_volume(V, F) < 0:
        F = [tuple(f[::-1]) for f in F]
    part.add(V, F, slot, None, label)
    if mass:
        part.weigh(V, F, mass, mass[2] if len(mass) > 2 else label)


def _rev(part, prof, origin, slot, label, n, mass, axis=UP, ref=X):
    V, F = deck.revolve(prof, origin, axis, ref, n)
    _solid(part, V, F, slot, label, mass)


def pad(part, c, radius, height, group):
    """A round teak pad on the deck at plan point c: its foot follows the deck, let in, its top level `height` above
    the deck at its centre (where the winch's flange sits). Returns the top's height."""
    n = 48
    a = 2 * math.pi * np.arange(n) / n
    ring = np.column_stack([c[0] + radius * np.cos(a), c[1] + radius * np.sin(a)])
    zt = deck_z(c[0], c[1]) + height
    lo = np.column_stack([ring, shell.deck_z(ring[:, 0], ring[:, 1]) - W["pad"]["let_in"]])
    ch = 0.006
    ring2 = np.column_stack([c[0] + (radius - ch) * np.cos(a), c[1] + (radius - ch) * np.sin(a)])
    mid = np.column_stack([ring, np.full(n, zt - ch)])
    top = np.column_stack([ring2, np.full(n, zt)])
    V, F = deck.loft_rings([lo, mid, top])
    _solid(part, V, F, "Wood", lab(group, "pad"), ("solid", TEAK, "Winch pads (teak)"))
    return zt


def _socket(part, o, group, mass_cat):
    s_out, s_in, h = W["socket"]
    sq = lambda s: np.array([(s / 2, s / 2), (-s / 2, s / 2), (-s / 2, -s / 2), (s / 2, -s / 2)])  # noqa: E731
    Yd = np.cross(UP, X)
    V, F = deck.ring_slab(sq(s_out), sq(s_in), o, X, Yd, UP, -0.004, h)
    _solid(part, V, F, "Bronze", lab(group, "socket"), ("solid", BRZ * FILL, mass_cat))
    V, F = deck.slab(sq(s_in + 0.001), o, X, Yd, UP, -0.006, h - 0.008)
    _solid(part, V, F, "Black", lab(group, "socket"), None)


def _base(part, o, sz, group, n, top_r):
    """The flange, its bolts' heads and the skirt up to the pawls' band (radius top_r at skirt_h)."""
    br, sh = sz["base_r"], sz["skirt_h"]
    prof = [(0.0, 0.0), (br - 0.004, 0.0), (br, 0.004), (br, 0.012), (br - 0.006, 0.016)]
    for k in range(1, 9):
        t = k / 8
        r = (br - 0.02) + (top_r - (br - 0.02)) * (1 - (1 - t) ** 2.2)
        prof.append((r, 0.016 + (sh - 0.016) * t))
    prof += [(top_r, sh + 0.018), (0.0, sh + 0.018)]
    _rev(part, prof, o, "Bronze", lab(group, "winch"), n, ("solid", BRZ * FILL, "Winches (bronze)"))
    for k in range(sz["bolts"]):
        a = 2 * math.pi * (k + 0.5) / sz["bolts"]
        c = o + (br - 0.028) * (math.cos(a) * X + math.sin(a) * np.cross(UP, X))
        _rev(part, [(0.0, 0.012), (0.011, 0.012), (0.011, 0.017), (0.007, 0.022), (0.0, 0.0235)], c, "Bronze",
             lab(group, "winch"), 12, ("solid", BRZ, "Winches (bronze)"))
    return sh + 0.018


def capstan(part, at, size, pad_h, group):
    """A capstan winch at plan point `at` on a pad `pad_h` high. Returns its axis's foot, the drum's radius at the ribs'
    tops, the height range of the drum the turns may use, and the cap's top."""
    sz = W["sizes"][size]
    c = np.asarray(at, float)
    z0 = pad(part, c, sz["base_r"] + W["pad"]["over"], pad_h, group)
    o = np.array([c[0], c[1], z0])
    n = 8 * sz["ribs"]
    R, rib, lip = sz["drum_r"], sz["rib"], sz["lip"]
    rb = R - rib
    zd0 = _base(part, o, sz, group, 64, R + lip + 0.012)
    zd1 = zd0 + sz["drum_h"]
    # the drum: its foot flaring out (a quarter round of `lip`), the barrel under the ribs, a small rim at its head
    prof = [(0.0, zd0 - 0.004), (R + lip, zd0 - 0.004), (R + lip, zd0)]
    for k in range(1, 7):
        q = math.pi / 2 * k / 6
        prof.append((rb + lip * (1 - math.sin(q)), zd0 + lip * (1 - math.cos(q)) + 0.006 * math.sin(q)))
    prof += [(rb, zd1 - 0.006), (R + 0.006, zd1), (R + 0.006, zd1 + 0.01)]
    # the cap: a dome over the drum's head to a flat round the socket
    ch = sz["cap_h"]
    for k in range(1, 8):
        q = math.pi / 2 * k / 7
        prof.append((max(0.03, (R + 0.004) * math.cos(q) * 0.95 + 0.0), zd1 + 0.01 + ch * math.sin(q)))
    prof.append((0.0, zd1 + 0.01 + ch))
    _rev(part, prof, o, "Bronze", lab(group, "drum"), 64, ("solid", BRZ * FILL, "Winches (bronze)"))
    # the ribs: a sleeve over the barrel whose radius rises to R in each rib (narrow rounded ridges)
    ang = 2 * math.pi * np.arange(n) / n
    w = (0.5 + 0.5 * np.cos(sz["ribs"] * ang)) ** 6
    rr = rb - 0.002 + (rib + 0.002) * w
    Yd = np.cross(UP, X)
    rings = []
    for z in np.linspace(zd0 + lip * 0.7, zd1 - 0.004, 6):
        rings.append(o + z * UP + rr[:, None] * (np.cos(ang)[:, None] * X + np.sin(ang)[:, None] * Yd))
    V, F = deck.loft_rings(rings)
    _solid(part, V, F, "Bronze", lab(group, "drum"), None)
    top = zd1 + 0.01 + ch
    _socket(part, o + top * UP, group, "Winches (bronze)")
    return {"foot": o, "R": R, "z_lo": float(z0 + zd0 + lip + 0.004), "z_hi": float(z0 + zd1 - 0.008),
            "top": float(z0 + top), "base_r": sz["base_r"], "size": size, "kind": "capstan"}


def reel(part, at, pad_h, group, stored_m=0.0, d=0.012):
    """A reel winch at plan point `at`, `stored_m` of wire `d` thick wound on it. Returns its axis's foot, the reel's
    radii and the wound wire's height range."""
    sz = W["sizes"]["reel"]
    c = np.asarray(at, float)
    z0 = pad(part, c, sz["base_r"] + W["pad"]["over"], pad_h, group)
    o = np.array([c[0], c[1], z0])
    n = 64
    R, fr, bh = sz["drum_r"], sz["flange_r"], sz["brake_h"]
    zb = _base(part, o, sz, group, n, R + 0.03)
    z1 = zb + bh                                                 # the brake drum's top: the bottom flange
    zt = z1 + 0.01 + sz["drum_h"]                                # the top flange
    prof = [(0.0, zb - 0.004), (R + 0.03, zb - 0.004), (R + 0.03, z1), (fr, z1), (fr, z1 + 0.01), (R, z1 + 0.01),
            (R, zt), (fr, zt), (fr, zt + 0.01), (R + 0.01, zt + 0.016)]
    ch = sz["cap_h"]
    for k in range(1, 7):
        q = math.pi / 2 * k / 6
        prof.append((max(0.03, (R + 0.01) * math.cos(q)), zt + 0.016 + ch * math.sin(q)))
    prof.append((0.0, zt + 0.016 + ch))
    _rev(part, prof, o, "Bronze", lab(group, "reel"), n, ("solid", BRZ * FILL, "Winches (bronze)"))
    # the brake band round the brake drum, its lever's boss
    _rev(part, [(R + 0.034, zb + 0.004), (R + 0.034, z1 - 0.004)], o, "Iron", lab(group, "reel"), n,
         ("solid", 7850.0 * 0.3, "Winches (bronze)"))
    # the wire stored on the reel: a solid whose UVs draw it as turns of wire rope (u round the reel, v once per
    # turn's height), so the wire's paint draws the lay on each turn
    wr = wound_radius(stored_m, d)
    if wr > fr - 0.008:
        raise ValueError(f"{group}: {stored_m:.1f} m of {1000 * d:.0f} mm wire is wound to {wr:.3f} m, past the reel's "
                         f"flanges ({fr} m)")
    ang = 2 * math.pi * np.arange(n) / n
    Yd = np.cross(UP, X)
    zs = np.linspace(z1 + 0.011, zt - 0.001, 12)
    rings = [o + z * UP + wr * (np.cos(ang)[:, None] * X + np.sin(ang)[:, None] * Yd) for z in zs]
    V, F = deck.loft_rings(rings)
    sp = [(a * wr, (z - zs[0]) / d) for z in zs for a in ang] + [(0.0, 0.0), (0.0, 0.0)]
    sg = [(math.pi * d, 1.0)] * (len(zs) * n) + [spars.PLAIN, spars.PLAIN]
    if deck.signed_volume(np.asarray(V), F) < 0:
        F = [tuple(f[::-1]) for f in F]
    part.add(V, F, "WireRope", None, lab(group, "wire on reel"), uv={"Spar": np.array(sp), "SparG": np.array(sg)})
    _socket(part, o + (zt + 0.016 + ch) * UP, group, "Winches (bronze)")
    return {"foot": o, "R": R, "wound_r": wr, "z_lo": float(z0 + z1 + 0.011), "z_hi": float(z0 + zt - 0.001),
            "flange_r": fr, "top": float(z0 + zt + 0.016 + ch), "base_r": sz["base_r"], "size": "reel",
            "kind": "reel"}


def wound_radius(stored_m, d):
    """The radius a reel's wire is wound out to for `stored_m` of wire `d` thick, at the reel's packing."""
    sz = W["sizes"]["reel"]
    area = stored_m * d * d / sz["packing"]
    return math.sqrt(sz["drum_r"] ** 2 + area / (math.pi * sz["drum_h"]))


# ------------------------------------------------------------------------------------------------ cleats
def cleat(part, at, heading_deg, size, group, cat="Cleats (bronze)"):
    """A bronze horn cleat at plan point `at`, its horns along `heading_deg` from forward (to starboard positive): the
    bar with its horns, slimmer and turned up a little at the tips, on two feet let into the deck. `size` names one of
    the json's sizes or is a size itself (slice 8's mooring cleats); `cat` its weights' row. Returns its frame."""
    cs = size if isinstance(size, dict) else RN["cleat"]["sizes"][size]
    L, hu, ht, hw, fx = cs["L"], cs["h_under"], cs["h_top"], cs["half_w"], cs["foot_x"]
    h = math.radians(heading_deg)
    Xc = np.array([math.cos(h), math.sin(h), 0.0])
    Yc = np.cross(UP, Xc)
    c = np.asarray(at, float)
    z0 = deck_z(c[0], c[1])
    O = np.array([c[0], c[1], z0])
    m = 20
    q = 2 * math.pi * np.arange(m) / m
    cq, sq = np.cos(q), np.sin(q)
    p = 2.6
    rings = []
    for x in np.linspace(-L / 2, L / 2, 25):
        t = abs(x) / (L / 2)
        top = ht + 0.006 * t ** 6
        bot = hu + (ht - hu) * 0.42 * t ** 2.5
        zc, hz = 0.5 * (top + bot), 0.5 * (top - bot)
        hy = hw * (1.0 - 0.35 * t ** 2)
        if t > 0.999:                                            # the tips rounded off
            hz, hy = 0.35 * hz, 0.35 * hy
        y = hy * np.sign(sq) * np.abs(sq) ** (2 / p)
        z = zc + hz * np.sign(cq) * np.abs(cq) ** (2 / p)
        rings.append(O + x * Xc + y[:, None] * Yc + z[:, None] * UP)
    V, F = deck.loft_rings(rings)
    _solid(part, V, F, "Bronze", lab(group, "cleat"), ("solid", BRZ, cat))
    for sg in (1, -1):
        xc = sg * 0.68 * fx
        rr = []
        for zz, grow in ((-0.003, 1.18), (0.004, 1.12), (0.35 * hu, 1.0), (hu + 0.006, 0.92)):
            P2 = deck.rrect(0.0, 0.0, 0.64 * fx * grow, 2.0 * hw * grow, 0.006)
            pts = O + xc * Xc + P2[:, :1] * Xc + P2[:, 1:2] * Yc
            if zz < 0:
                pts[:, 2] = shell.deck_z(pts[:, 0], pts[:, 1]) + zz
            else:
                pts[:, 2] = z0 + zz
            rr.append(pts)
        V, F = deck.loft_rings(rr)
        _solid(part, V, F, "Bronze", lab(group, "cleat"), ("solid", BRZ, cat))
    return {"O": O, "X": Xc, "Y": Yc, "size": size, **cs}


# ------------------------------------------------------------------------------------------------ ropework
def resample(P, step):
    P = np.asarray(P, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(2, int(math.ceil(s[-1] / step)) + 1)
    t = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(t, s, P[:, k]) for k in range(3)])


def relax(P, step, iters=6):
    """Waypoints joined straight, resampled every `step`, corners rounded by neighbour averaging (the kit's relax)."""
    Q = resample(P, step)
    for _ in range(iters):
        Q[1:-1] = (Q[:-2] + 2 * Q[1:-1] + Q[2:]) / 4
    return Q


def length(P):
    return float(np.linalg.norm(np.diff(np.asarray(P, float), axis=0), axis=1).sum())


def tangent_from(Q, c, R, sense=1):
    """The point where a rope from plan point Q meets (or leaves) the circle centre c, radius R tangentially, for a
    drum turning clockwise seen from above (its surface moving along cw(p - c)): `sense` +1 for a rope coming in from Q
    (the drum draws it on), -1 for one going out to Q (the tail hauled off it). Returns the plan point and its angle
    (from +X toward +Y, so growing as the drum turns)."""
    d = np.asarray(Q[:2], float) - np.asarray(c[:2], float)
    D = float(np.linalg.norm(d))
    if D <= R + 1e-6:
        raise ValueError(f"the rope's lead ({Q}) is inside the drum's circle (centre {c}, radius {R})")
    a = math.atan2(d[1], d[0])
    b = math.acos(R / D)
    for th in (a + b, a - b):
        p = np.asarray(c[:2]) + R * np.array([math.cos(th), math.sin(th)])
        mv = unit(np.r_[p - np.asarray(Q[:2]), 0.0]) * sense       # the rope's motion there, onto or off the drum
        if float(mv @ cw(p - np.asarray(c[:2]))) > 0:
            return p, th
    raise ValueError("no tangent")


def turns(c, R, z_lo, th_in, th_out, n, d, gap=0.002):
    """The turns round a drum (axis vertical through plan point c, the rope's centre at R): from th_in at z_lo
    clockwise (seen from above: the angle grows, see cw) n whole turns and on to th_out, rising one diameter and `gap`
    a turn."""
    span = 2 * math.pi * n + ((th_out - th_in) % (2 * math.pi))
    k = max(8, int(math.ceil(span / math.radians(8.0))))
    th = th_in + span * np.arange(k + 1) / k
    z = z_lo + (d + gap) * (span * np.arange(k + 1) / k) / (2 * math.pi)
    return np.column_stack([c[0] + R * np.cos(th), c[1] + R * np.sin(th), z])


def cleat_hitch(cl, d, lead, tail=0.22, gap=0.002):
    """A rope made fast on cleat `cl` (cleat()'s frame): the standing part comes in beside the near half of the cleat
    and under the far horn; a turn round the base (along the far side, under the near horn and up beside it), a
    figure of eight over the top and a locking turn over that, the tail off the far horn's end onto the deck. `lead`
    (plan) is the direction from the cleat toward the load (the winch). Each later turn round a foot lies outside the
    one before (a diameter and `gap` further out), each crossing over the top a diameter and `gap` above the one under
    it, and the rope climbs to the top only beside the horns (clear of the standing part, which runs further out), so
    it never passes through itself or the cleat (running.self_clearance holds it). Returns the centreline in the hull's
    frame, from where the rope arrives at the cleat to the tail's end on the deck (each point's height above the deck
    under it)."""
    L, ht, hw, fx = cl["L"], cl["h_top"], cl["half_w"], cl["foot_x"]
    lx, ly = float(np.asarray(lead) @ cl["X"]), float(np.asarray(lead) @ cl["Y"])
    r = d / 2
    p = d + gap
    Ls = -1.0 if ly <= 0 else 1.0                     # the side the rope comes in on
    Fh = -1.0 if lx >= 0 else 1.0                     # the far horn, away from the load
    Nh = -Fh
    cx = fx * 0.68                                    # the turns' centres, at the feet's (cleat()'s)
    hx, hy, rc = 0.32 * fx * 1.18, hw * 1.18, 0.006   # a foot's half length and width where it meets the deck
    R1 = math.hypot(hx - rc, hy - rc) + rc + r + 0.004   # the first turn's radius: clear of the foot's corners
    z0 = r + 0.0025                                   # on the deck
    zt = ht + r + 0.001                               # the first crossing over the top
    side = hw + r + 0.003                             # beside the horns: clear of them at any height
    sy = side + 0.001                                 # where a crossing leaves the top for a horn
    a = cx + 0.45 * R1
    Yi = max(R1, side) + p + 0.002                    # the standing part's run beside the near half, outside the climbs
    P = []

    def arc(sgn, y_from, R, t1=math.pi, n=13):
        """Round a foot from side y_from (its angle 0) toward the other side, to angle t1."""
        for i in range(n):
            t = t1 * i / (n - 1)
            P.append((sgn * (cx + R * math.sin(t)), y_from * R * math.cos(t), z0))

    def to_side(sgn, y_to, R):
        """Round the near foot from side -y_to until beside the horn on side y_to (not all the way round): from there
        the rope climbs to the top."""
        t1 = math.pi - math.acos(min(1.0, side / R))
        arc(sgn, -y_to, R, t1)

    def land(sgn, y_on, R):
        """Down onto the deck beside a foot, outside what is under it there, then round under the horn."""
        P.append((sgn * cx, y_on * R, z0 + 0.7 * p))

    # the standing part comes in beside the near foot, outside where the rope climbs past the near horn
    P.append((Nh * cx, Ls * Yi, z0 + 0.002))
    arc(Fh, Ls, R1)                                   # under the far horn,
    to_side(Nh, Ls, R1)                               # along the side and under the near one, up beside it
    P.append((Nh * a, Ls * sy, zt))                   # the figure of eight: over the top,
    P.append((Fh * a, -Ls * sy, zt))
    land(Fh, -Ls, R1 + p)                         # down outside the first turn,
    arc(Fh, -Ls, R1 + p)                              # under the far horn outside it,
    land(Fh, Ls, R1 + p)
    P.append((Fh * a, Ls * sy, zt + p))               # back over the top, across the first crossing,
    P.append((Nh * a, -Ls * sy, zt + p))
    land(Nh, -Ls, R1 + p)
    to_side(Nh, Ls, R1 + p)                           # under the near horn, up beside it clear of the first climb
    P.append((P[-1][0], P[-1][1], zt + 2 * p))
    P.append((Nh * a, Ls * sy, zt + 2 * p))           # the locking turn over both
    P.append((Fh * (a + 0.3 * R1), -Ls * sy, zt + 2 * p))
    e = (Fh * (0.5 * L + 0.02), -Ls * (sy + 0.01), zt + p)
    P.append(e)
    P.append((e[0] + Fh * 0.05, e[1] - Ls * 0.01, r + 0.004))
    P.append((e[0] + Fh * tail, e[1] - Ls * 0.04, r + 0.001))
    Q = relax(np.array(P), d * 0.3, 16)
    return to_deck(cl, Q)


def to_deck(cl, Q):
    """Cleat-frame points (z above the deck) to the hull's frame, each on the deck under it."""
    H = cl["O"][None] + Q[:, :1] * cl["X"][None] + Q[:, 1:2] * cl["Y"][None]
    H[:, 2] = shell.deck_z(H[:, 0], H[:, 1]) + Q[:, 2]
    return H


def coil(c, d, L, a0, r_in, r_out, gap=0.001, step_deg=12.0):
    """A tail of length L flemished down round plan point c: from its outer edge at the angle a0 a flat spiral
    clockwise seen from above (the angle growing, see cw) in to r_in, then the next layer on top back out, and so on,
    each layer one diameter up, until the length is used. Returns the centreline (heights on the deck under it) and
    the layers."""
    p = d + gap
    # the turns a diameter and `gap` apart, plus what a chord of `step_deg` falls inside its circle at the outer turn
    pr = p + r_out * (1.0 - math.cos(math.radians(step_deg) / 2))
    pts, used, layer = [], 0.0, 0
    nturn = max(1.0, (r_out - r_in) / pr)
    while used < L - 1e-6:
        out_in = layer % 2 == 0
        k = int(math.ceil(nturn * 360.0 / step_deg))
        for j in range(0 if layer == 0 else 1, k + 1):
            f = j / k
            rr = r_out - (r_out - r_in) * f if out_in else r_in + (r_out - r_in) * f
            th = a0 + 2 * math.pi * nturn * f + layer * 2 * math.pi * nturn
            # up onto the layer below: over the turn it climbs past (a turn back, half a turn's spacing away when it is
            # half a turn on), at least as high as a rope's diameter clears it, so it rides over the turn
            u = f * nturn
            rise = 1.0 if layer == 0 or u >= 0.5 else min(1.0, 1.15 * 2.0 * math.sqrt(u * (1.0 - u)))
            q = np.array([c[0] + rr * math.cos(th), c[1] + rr * math.sin(th),
                          d / 2 + gap + (layer - 1 + rise) * p if layer else d / 2 + gap])
            if pts:
                used += float(np.linalg.norm(q[:2] - pts[-1][:2]))
                if used >= L:
                    pts.append(q)
                    break
            pts.append(q)
        layer += 1
    P = np.array(pts)
    P[:, 2] += shell.deck_z(P[:, 0], P[:, 1])
    return P, layer
