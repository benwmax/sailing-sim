"""Bluebonnet's standing rigging and her runners (docs/jclass-5), from standing_bluebonnet.json and the attachment
points spars.py reports.

Objects, each a set of closed solids, in the hull's frame (X forward, Y starboard, Z up, metres):
  Shrouds          the cap shrouds (V1) over the three spreaders and the diagonals (D3, D2, D1) in line with them,
                   with their tangs, tang bands, sockets, rigging screws and chainplates, both sides
  Stays            the forestay to the stem head, the staysail stay, the jumper stays over the jumper struts, and the
                   backstay from its crane at the masthead to the counter
  RunnerFittings   the runners' tangs at the hounds, the checkstays' tangs at the top spreaders, their padeyes on deck
  Runner.<Side>.Set, Runner.<Side>.LetOff, Checkstay.<Side>.Set, Checkstay.<Side>.LetOff
                   each pendant with its tackle: set (straight from its tang toward its padeye, the tackle taking up
                   the rest), or let off (the pendant lashed forward to the aftermost shroud, the tackle overhauled
                   along the deck). The pendant is the same length in both. Show one state a side: on starboard tack
                   the starboard pair set and the port pair let off.
The wires' lay is drawn, not modelled: each vertex carries spars.py's 'Spar' map (u metres along the wire, v round it)
and the paint draws the outer strands from it (build_jclass.py's WireLay groups).

Weights come from the same geometry: each wire from its length and its metal's area, the fittings from their volume,
the chainplates with the part hidden below the deck. The report lists every wire's free length (between its fittings)
for the build's clearance checks, the tackles' frames, and the strength sum.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import shell  # noqa: E402
import deck  # noqa: E402
import spars  # noqa: E402
from spars import SparPart, unit, at, A, FW, Y, UP, BRZ, rnd  # noqa: E402

SR = json.load(open(os.path.join(HERE, "standing_bluebonnet.json")))
STEEL = SR["material"]["steel"]
MANILA = SR["material"]["manila"]
FIT = SR["fittings"]
SIDES = ((1, "starboard"), (-1, "port"))
X = np.array([1.0, 0.0, 0.0])


def lab(group, kind):
    """A face label: the wire or rope's group and the kind of piece (a wire's own faces carry the bare group)."""
    return f"{group} | {kind}"


def kind_of(label):
    return label.split(" | ")[1] if " | " in label else "wire"


def group_of(label):
    return label.split(" | ")[0]


def deck_z(x, y):
    return float(shell.deck_z(np.array([x]), np.array([y]))[0])


def wire_r(key):
    return 0.5 * SR["wires"][key]["d"]


def slot_of(key):
    """The paint for a wire: 'Wire' for 1x19 strand, 'WireRope' for 7x19 (each draws its own lay)."""
    return "Wire" if SR["wires"][key]["construction"] == "1x19" else "WireRope"


def kg_per_m(key):
    w = SR["wires"][key]
    c = SR["constructions"][w["construction"]]
    return STEEL * c["fill"] * math.pi * w["d"] ** 2 / 4


def breaking_kn(key):
    w = SR["wires"][key]
    c = SR["constructions"][w["construction"]]
    return SR["material"]["steel_breaking_mpa"] * 1e6 * c["fill"] * c["efficiency"] * math.pi * w["d"] ** 2 / 4 / 1000


def perp(v):
    """A unit vector square to v (level where it can be)."""
    v = unit(v)
    p = np.cross(v, UP)
    if np.linalg.norm(p) < 1e-6:
        p = np.cross(v, X)
    return unit(p)


def hull2d(P):
    """The convex hull of 2D points, anticlockwise (monotone chain)."""
    P = sorted(set((round(float(a), 9), round(float(b), 9)) for a, b in P))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return np.array(lo[:-1] + hi[:-1])


# ------------------------------------------------------------------------------------------------ wire and rope
def fillet(P, rad, step=math.radians(6.0)):
    """The polyline P with each corner rounded to about `rad` (a quadratic curve between the tangent points)."""
    P = [np.asarray(p, float) for p in P]
    if rad <= 0.0:
        return np.array(P)
    out = [P[0]]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        d0, d1 = unit(b - a), unit(c - b)
        th = math.acos(max(-1.0, min(1.0, float(d0 @ d1))))
        if th < 1e-4:
            out.append(b)
            continue
        t = min(rad * math.tan(th / 2), 0.4 * float(np.linalg.norm(b - a)), 0.4 * float(np.linalg.norm(c - b)))
        p0, p1 = b - t * d0, b + t * d1
        k = max(2, int(math.ceil(th / step)))
        for j in range(k + 1):
            s = j / k
            out.append((1 - s) ** 2 * p0 + 2 * s * (1 - s) * b + s ** 2 * p1)
    out.append(P[-1])
    return np.array(out)


def tube_rings(P, r, n=12, closed=False):
    """Rings of radius r round the polyline P, carried along it without twisting; u, metres along it at each ring."""
    P = np.asarray(P, float)
    keep = [0] + [i for i in range(1, len(P)) if np.linalg.norm(P[i] - P[i - 1]) > 1e-6]
    P = P[keep]                                                    # no zero-length steps (their direction is undefined)
    m = len(P)
    seg = np.diff(np.vstack([P, P[:1]]) if closed else P, axis=0)
    d = seg / np.linalg.norm(seg, axis=1)[:, None]
    a = 2 * math.pi * np.arange(n) / n
    u = perp(d[0])
    rings, us, s = [], [], 0.0
    for i in range(m):
        if closed:
            t = unit(d[i - 1] + d[i])
        elif 0 < i < m - 1:
            t = unit(d[i - 1] + d[i])
        else:
            t = d[min(i, len(d) - 1)]
        u = unit(u - (u @ t) * t)
        v = np.cross(t, u)
        rings.append(P[i] + r * (np.cos(a)[:, None] * u + np.sin(a)[:, None] * v))
        if i:
            s += float(np.linalg.norm(P[i] - P[i - 1]))
        us.append(s)
    return rings, np.array(us)


def wire(part, pts, r, group, cat, kgm, slot="Wire", n=12, bend=None):
    """A wire (or a rope) along pts, its bends rounded: its weight from its length (kgm kg/m). Returns its length."""
    P = fillet(pts, bend if bend is not None else FIT["wire_bend"] * r)
    rings, u = tube_rings(P, r, n)
    V, F = deck.loft_rings(rings)
    part.add(V, F, slot, None, group, uv=spars.ring_uv(rings, u, plated=False))
    L = float(u[-1])
    mid = 0.5 * (P[1:] + P[:-1])
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    part.masses.append({"part": cat, "kg": round(kgm * L, 1),
                        "centre": [round(float(v), 3) for v in (mid * seg[:, None]).sum(0) / seg.sum()],
                        "how": "length"})
    return L


def loop(part, P, r, group, cat, kgm, slot="Rope", n=10):
    """A closed loop of rope round the closed polyline P (a lashing, a link)."""
    rings, u = tube_rings(P, r, n, closed=True)
    V, F = deck.loft_rings(rings, closed=True)
    part.add(V, F, slot, None, group, uv={"Spar": np.array([(uu, j / n) for uu in u for j in range(n)]),
                                          "SparG": np.tile((2 * math.pi * r, -1.0), (len(V), 1))})
    L = u[-1] + float(np.linalg.norm(P[0] - P[-1]))
    part.masses.append({"part": cat, "kg": round(float(kgm * L), 2), "centre": [round(float(v), 3) for v in P.mean(0)],
                        "how": "length"})


def ring_path(c, axis, ref, rho, k=20):
    a = 2 * math.pi * np.arange(k) / k
    U = perp(axis) if ref is None else unit(ref - (ref @ unit(axis)) * unit(axis))
    V = np.cross(unit(axis), U)
    return c + rho * (np.cos(a)[:, None] * U + np.sin(a)[:, None] * V)


# ------------------------------------------------------------------------------------------------ fittings
def solid(part, V, F, slot, group, cat, rho=BRZ):
    """A closed solid labelled `group` (the drawing's and the sweeps' name), weighed under `cat` (the weights' row)."""
    V = np.asarray(V, float)
    if deck.signed_volume(V, F) < 0:
        F = [tuple(f[::-1]) for f in F]
    part.add(V, F, slot, None, group)
    part.weigh(V, F, ("solid", rho), cat)


def flat(part, poly, origin, U, Vd, N, t0, t1, slot, group, cat, rho=BRZ):
    V, F = deck.slab(np.asarray(poly, float), origin, U, Vd, N, t0, t1)
    solid(part, V, F, slot, group, cat, rho)


def rev(part, prof, origin, axis, ref, slot, group, cat, n=16, rho=BRZ):
    V, F = deck.revolve(prof, origin, axis, ref, n)
    solid(part, V, F, slot, group, cat, rho)


def cheeks(part, H, u, Np, r, plate_t, back, ahead, group, cat):
    """A jaw's two cheeks straddling a plate (t thick) round the pin at H, Np the pin's axis, u along the fitting."""
    Np = unit(Np)
    up = unit(u - (u @ Np) * Np)
    w = np.cross(Np, up)
    h = FIT["terminal"]["cheek_half"] * r
    ct = FIT["terminal"]["cheek_t"] * r
    q = np.linspace(math.pi / 2, 3 * math.pi / 2, 9)
    poly = [(h * math.cos(a) * back / FIT["terminal"]["cheek_half"], h * math.sin(a)) for a in q]
    poly += [(ahead * r, -h), (ahead * r, h)]
    off = plate_t / 2 + 0.002
    for sg in (1, -1):
        flat(part, poly, H, up, w, Np, sg * off if sg > 0 else -off - ct, off + ct if sg > 0 else -off, "Bronze",
             lab(group, "jaw"), cat)
    span = off + ct
    tm = FIT["terminal"]
    rev(part, [(tm["head_r"] * r, -span - 0.006), (tm["head_r"] * r, -span), (tm["pin_r"] * r, -span),
               (tm["pin_r"] * r, span + 0.006)], H, Np, up, "Bronze", lab(group, "pin"), cat, 12)


def clear_of(plate_end, start, r):
    """How much longer a jaw must be (m) for the fitting behind it, starting `start` r from the pin, to clear the end
    of the plate it straddles (`plate_end` m past the pin) by 0.4 r."""
    return max(0.0, plate_end + 0.4 * r - start * r)


def terminal(part, H, u, Np, r, plate_t, group, plate_end=0.0):
    """A poured socket on a wire's end, its jaw on a plate's pin at H (Np the pin's axis), the wire leaving along u; the
    jaw lengthened where the plate reaches `plate_end` past the pin. Returns where the wire leaves the socket."""
    tm = FIT["terminal"]
    u = unit(u)
    cat = "Sockets, jaws and pins"
    sh = clear_of(plate_end, tm["body"][0], r)
    cheeks(part, H, u, Np, r, plate_t, tm["jaw_back"], tm["jaw"] + sh / r, group, cat)
    b0, b1 = tm["body"]
    rev(part, [(tm["body_r"] * r, b0 * r), (tm["body_r"] * r, b1 * r), (tm["neck_r"] * r, tm["cone_end"] * r)],
        H + sh * u, u, perp(u), "Bronze", lab(group, "socket"), cat)
    return H + (sh + (tm["cone_end"] - 0.5) * r) * u


def rigging_screw(part, C, u, Np, r, plate_t, group, plate_end=0.0):
    """A rigging screw from the pin at C (on a chainplate or a tang, Np its axis) up the wire's line u: a toggle, the
    lower stud, the open body, the upper stud and the wire's socket, the toggle's jaw lengthened where the plate reaches
    `plate_end` past the pin. Returns where the wire leaves the socket."""
    sc = FIT["screw"]
    u = unit(u)
    cat = "Rigging screws and toggles"
    sh = clear_of(plate_end, sc["toggle"][0], r)
    cheeks(part, C, u, Np, r, plate_t, FIT["terminal"]["jaw_back"], sc["jaw"] + sh / r, group, cat)
    C = C + sh * u
    ref = perp(u)
    t0, t1 = sc["toggle"]
    ls = lab(group, "screw")
    rev(part, [(sc["toggle_r"] * r, t0 * r), (sc["toggle_r"] * r, t1 * r)], C, u, ref, "Bronze", ls, cat)
    for a, b in (sc["lower_stud"], sc["upper_stud"]):
        rev(part, [(sc["stud_r"] * r, a * r), (sc["stud_r"] * r, b * r)], C, u, ref, "Bronze", ls, cat, 12)
    for a, b in sc["bosses"]:
        rev(part, [(sc["boss_r"] * r, a * r), (sc["boss_r"] * r, b * r)], C, u, ref, "Bronze", ls, cat)
    w2 = np.cross(u, ref)
    a0, a1 = sc["bosses"][0][1] - 0.4, sc["bosses"][1][0] + 0.4
    for sg in (1, -1):
        poly = [(a0 * r, -sc["bar_w"] / 2 * r), (a1 * r, -sc["bar_w"] / 2 * r), (a1 * r, sc["bar_w"] / 2 * r),
                (a0 * r, sc["bar_w"] / 2 * r)]
        o = C + sg * sc["bar_off"] * r * ref
        flat(part, poly, o, u, w2, ref, -sc["bar_t"] / 2 * r, sc["bar_t"] / 2 * r, "Bronze", ls, cat)
    s0, s1 = sc["socket"]
    rev(part, [(FIT["terminal"]["body_r"] * r, s0 * r), (FIT["terminal"]["body_r"] * r, s1 * r),
               (FIT["terminal"]["neck_r"] * r, sc["cone_end"] * r)], C, u, ref, "Bronze", ls, cat)
    return C + (sc["cone_end"] - 0.5) * r * u


def chainplate(part, C, u, Np, r, group, deck_plate=True):
    """A galvanised steel strap up through the deck to the pin at C (Np the pin's axis, u up the wire's line), with a
    bronze plate round it on the deck. Its part below the deck (hidden) is weighed too."""
    cp = FIT["chainplate"]
    u = unit(u)
    Np = unit(Np - (Np @ u) * u)
    w = np.cross(Np, u)
    hw, t = cp["width"] / 2 * r, cp["thickness"] * r
    zd = deck_z(C[0], C[1])
    s_foot = -(C[2] - zd + 0.04) / max(u[2], 0.2)                # 4 cm into the deck along the line
    q = np.linspace(0.0, math.pi, 9)
    top = cp["above_pin"] * r
    poly = [(s_foot, -hw)] + [(top - hw + hw * math.sin(a), -hw * math.cos(a)) for a in q] + [(s_foot, hw)]
    flat(part, poly, C, u, w, Np, -t / 2, t / 2, "Galvanised", lab(group, "chainplate"), "Chainplates and deck plates",
         STEEL)
    part.masses.append({"part": "Chainplates and deck plates", "kg": round(STEEL * 2 * hw * t * cp["below_deck"], 1),
                        "centre": [round(float(v), 3) for v in (C[0], C[1], zd - 0.5 * cp["below_deck"])],
                        "how": "below the deck"})
    if deck_plate:
        dp = cp["deck_plate"]
        P = C + ((zd - C[2]) / u[2]) * u                              # where the strap meets the deck
        U2 = unit(w - (w @ UP) * UP)
        V2 = np.cross(UP, U2)
        L, W = hw + dp[0], t / 2 + dp[1]
        poly = deck.rrect(0.0, 0.0, 2 * L, 2 * W, min(W, L) * 0.6)
        flat(part, poly, np.array([P[0], P[1], zd]), U2, V2, UP, -0.008, dp[2], "Bronze", lab(group, "deck plate"),
             "Chainplates and deck plates")
    return C


def plate2(part, origin, U, Vd, N, u0, u1, h, t, group, cat, slot="Bronze"):
    """A flat plate from u0 to u1 along U, its end at u1 rounded, h along Vd, t thick about N (spars.plate's shape)."""
    a = np.linspace(-math.pi / 2, math.pi / 2, 9)
    P = [(u0, -h / 2)] + [(u1 - h / 2 + h / 2 * math.cos(q), h / 2 * math.sin(q)) for q in a] + [(u0, h / 2)]
    flat(part, P, origin, U, Vd, N, -t / 2, t / 2, slot, group, cat)


def tang(part, s, radial, r, group, cat="Tangs and tang bands", reach=None):
    """A bronze tang off the mast at s toward `radial` (in the section's plane), in the plane of radial and the mast's
    axis. Returns its pin's centre and the pin's axis."""
    tg = FIT["tang"]
    h = tg["height"] * r
    radial = unit(radial - (radial @ A) * A)
    N = unit(np.cross(radial, A))
    surf = spars.surface_toward(s, radial)
    a = float((surf - at(s)) @ radial)
    reach = tg["reach"] * r if reach is None else reach
    plate2(part, at(s), radial, A, N, a - tg["root_in"], a + reach, h, tg["thickness"] * r, lab(group, "tang"), cat)
    return at(s) + (a + reach - h / 2) * radial, N, tg["thickness"] * r, h / 2


# ------------------------------------------------------------------------------------------------ the shrouds
def shrouds(part, rep, pts, sheer):
    sh = SR["shrouds"]
    sheer = np.asarray(sheer, float)
    o = np.argsort(sheer[:, 0])
    cp = spars.RG["chainplates"]
    s_bands = pts["spreader_band_s"]
    tb = sh["tang_band"]
    for k, s in enumerate(s_bands):
        spars.band(part, s - sh["tang_below"], tb["height"], tb["thickness"], "Bronze",
                   lab(f"Tang band {k + 1}", "tang band"), gap=spars.band_gap())
        part.masses[-1]["part"] = "Tangs and tang bands"
    rep["shrouds"], rep["wires"] = {}, rep.get("wires", [])
    rep["tang_band_s"] = [s - sh["tang_below"] for s in s_bands]
    for sd, side in SIDES:
        tips = [np.asarray(t, float) for t in pts["spreader_tips"][side]]
        chords = [np.asarray(c, float) for c in pts["spreader_chords"][side]]
        cap_chain = np.asarray(pts["chainplates"][side], float)     # slice 4's: on the deck, under the line to tip 1
        rows = {}
        for key in ("cap", "d3", "d2", "d1"):
            r = wire_r(key)
            group = f"{SR['wires'][key]['label']}, {side}"
            g = sh["groove"].get(key, 0.0)
            if key == "cap":
                ht = spars.RG["hounds"]["tang"]
                top, tN, tt, te = np.asarray(pts["shroud_tangs"][side], float), FW, ht["thickness"], ht["height"] / 2
                passes = tips[::-1]
            else:
                lvl = {"d3": 2, "d2": 1, "d1": 0}[key]
                top, tN, tt, te = tang(part, rep["tang_band_s"][lvl], sd * Y, r, group)
                passes = [tips[i] + g * chords[i] for i in range(lvl - 1, -1, -1)]
            # the chainplate's pin: up the line from the deck, 'x_offset' along the sheer from the cap shroud's
            x = cp["x"] + sh["x_offset"][key]
            hb = float(np.interp(x, sheer[o, 0], np.abs(sheer[o, 1]))) - cp["inboard_of_sheer"]
            foot = np.array([x, sd * hb, deck_z(x, sd * hb)]) if key != "cap" else cap_chain
            above = passes[-1] if passes else top
            u = unit(above - foot)
            C = foot + FIT["chainplate"]["pin_above_deck"] / u[2] * u
            Np = unit(np.cross(u, X))
            chainplate(part, C, u, Np, r, group)
            w_lo = rigging_screw(part, C, u, Np, r, FIT["chainplate"]["thickness"] * r, group,
                                 FIT["chainplate"]["above_pin"] * r)
            w_hi = terminal(part, top, (passes[0] if passes else C) - top, tN, r, tt, group, te)
            path = [w_hi] + passes + [w_lo]
            L = wire(part, path, r, group, SR["wires"][key]["label"], kg_per_m(key))
            rows[key] = {"top_pin": top, "chainplate_pin": C, "passes": passes, "wire_m": L}
            rep["wires"].append({"name": group, "group": group, "object": "Shrouds", "key": key, "r": r, "path": path,
                                 "passes": passes, "state": None})
        rep["shrouds"][side] = rows
    return rep


# ------------------------------------------------------------------------------------------------ the stays
def stays(part, rep, pts, sheer):
    st = SR["stays"]
    # the forestay: slice 4's tang at the hounds to a bronze plate on the stem head, on slice 4's line
    r = wire_r("forestay")
    fh = np.asarray(pts["forestay_hounds"], float)
    T0 = np.asarray(pts["stem_head_forestay_tack"], float)
    u = unit(fh - T0)
    C = T0 + st["pin_up_the_line"] * u
    group = "Forestay"
    t_stem = stem_plate(part, C, u, r, group, sheer)
    w_lo = rigging_screw(part, C, u, Y, r, t_stem, group, FIT["chainplate"]["above_pin"] * r)
    ht = spars.RG["hounds"]["tang"]
    w_hi = terminal(part, fh, -u, Y, r, ht["thickness"], group, ht["height"] / 2)
    L = wire(part, [w_hi, w_lo], r, group, "Forestay", kg_per_m("forestay"))
    rep["forestay"] = {"tang_pin": fh, "stem_pin": C, "wire_m": L,
                       "line_off_slice_4_mm": round(1000 * float(np.linalg.norm(np.cross(C - T0, u))), 3)}
    rep["wires"].append({"name": group, "group": group, "object": "Stays", "key": "forestay", "r": r,
                         "path": [w_hi, w_lo],
                         "passes": [], "state": None})
    # the staysail stay: a tang forward on the top spreaders' tang band to a deck plate on the centreline
    r = wire_r("staysail")
    group = "Staysail stay"
    s3 = rep["tang_band_s"][2]
    top, tN, tt, te = tang(part, s3, FW, r, group)
    xd = st["staysail"]["deck_x"]
    foot = np.array([xd, 0.0, deck_z(xd, 0.0)])
    u = unit(top - foot)
    C = foot + FIT["chainplate"]["pin_above_deck"] / u[2] * u
    chainplate(part, C, u, Y, r, group)
    w_lo = rigging_screw(part, C, u, Y, r, FIT["chainplate"]["thickness"] * r, group,
                         FIT["chainplate"]["above_pin"] * r)
    w_hi = terminal(part, top, -u, tN, r, tt, group, te)
    L = wire(part, [w_hi, w_lo], r, group, "Staysail stay", kg_per_m("staysail"))
    rep["staysail_stay"] = {"tang_pin": top, "deck_pin": C, "wire_m": L}
    rep["wires"].append({"name": group, "group": group, "object": "Stays", "key": "staysail", "r": r,
                         "path": [w_hi, w_lo],
                         "passes": [], "state": None})
    # the backstay: a crane aft at the masthead, to a chainplate on the counter
    r = wire_r("backstay")
    group = "Backstay"
    bc = st["backstay"]["crane"]
    sc = spars.S_TOP - bc["below_top"]
    a = spars.half_depth(sc)
    plate2(part, at(sc), -FW, A, Y, a - 0.04, a + bc["reach"], bc["height"], bc["thickness"], lab(group, "crane"),
           "Backstay crane")
    top = at(sc, -(a + bc["reach"] - bc["height"] / 2))
    xt, zt = loft.END["transom_top"]
    xd = xt + st["backstay"]["deck_from_transom_top"]
    foot = np.array([xd, 0.0, deck_z(xd, 0.0)])
    u = unit(top - foot)
    C = foot + FIT["chainplate"]["pin_above_deck"] / u[2] * u
    chainplate(part, C, u, Y, r, group)
    w_lo = rigging_screw(part, C, u, Y, r, FIT["chainplate"]["thickness"] * r, group,
                         FIT["chainplate"]["above_pin"] * r)
    w_hi = terminal(part, top, -u, Y, r, bc["thickness"], group, bc["height"] / 2)
    L = wire(part, [w_hi, w_lo], r, group, "Backstay", kg_per_m("backstay"))
    rep["backstay"] = {"crane_pin": top, "deck_pin": C, "wire_m": L, "crane_reach_m": bc["reach"]}
    rep["wires"].append({"name": group, "group": group, "object": "Stays", "key": "backstay", "r": r,
                         "path": [w_hi, w_lo],
                         "passes": [], "state": None})
    # the jumper stays: small tangs at slice 4's points, over the struts' tips, a rigging screw at the foot
    r = wire_r("jumper")
    rep["jumper_stays"] = {}
    out = spars.RG["jumpers"]["stay_pins_out"]
    for sd, side in SIDES:
        group = f"Jumper stay, {side}"
        js = pts["jumper_stays"][side]
        T = np.asarray(pts["jumper_tips"][side], float)
        ends = {}
        for k in ("top", "foot"):
            P = np.asarray(js[k], float)
            s = float((P - spars.P0) @ A)
            radial = unit(P - at(s))
            a = float((P - at(s)) @ radial)
            ends[k] = tang(part, s, radial, r, group, reach=out + FIT["tang"]["height"] * r / 2)
        top, tN, tt, te = ends["top"]
        foot, fN, ft, fe = ends["foot"]
        w_lo = rigging_screw(part, foot, T - foot, fN, r, ft, group, fe)
        w_hi = terminal(part, top, T - top, tN, r, tt, group, te)
        L = wire(part, [w_hi, T, w_lo], r, group, "Jumper stays", kg_per_m("jumper"))
        b = -unit(unit(top - T) + unit(foot - T))                  # the bend's bisector at the tip
        d = np.asarray(pts["jumper_strut_dirs"][side], float)
        # slice 4 solved the strut on the bisector of the stay between these pins
        off = math.degrees(math.acos(min(1.0, float(b @ unit(d)))))
        if off > 0.01:
            raise ValueError(f"the {side} jumper strut is {off:.3f} degrees off its stay's bisector")
        rep["jumper_stays"][side] = {"top_pin": top, "foot_pin": foot, "wire_m": L, "bisector": b,
                                     "strut_off_bisector_deg": round(off, 3)}
        rep["wires"].append({"name": group, "group": group, "object": "Stays", "key": "jumper", "r": r,
                             "path": [w_hi, T, w_lo], "passes": [T], "state": None})
    return rep


def stem_plate(part, C, u, r, group, sheer):
    """A bronze plate on the stem head in the centreplane, its pin at C, let into the stem, with a flange bedded on the
    deck aft of it: the flange follows the deck (its sheer and camber) and narrows with it, 'flange_margin' m inside
    the deck's edge, and stops where it would be narrower than the plate. Returns the plate's thickness."""
    cp = FIT["chainplate"]
    fl = FIT["stem_flange"]
    hw = cp["width"] / 2 * r
    t = fl["thickness"] * cp["thickness"] * r
    xs, zs = loft.END["stem_head"]
    w = np.cross(Y, u)
    q = np.linspace(0.0, math.pi, 9)
    top = cp["above_pin"] * r
    s_foot = -(C[2] - zs + 0.03) / max(u[2], 0.2)
    poly = [(s_foot, -hw - 0.04)] + [(top - hw + hw * math.sin(a), -hw * math.cos(a)) for a in q] + [(s_foot, hw)]
    flat(part, poly, C, u, w, Y, -t / 2, t / 2, "Bronze", lab(group, "stem plate"), "Stem head and deck plates")
    # the flange: its half width at x the deck's half breadth less the margin, at most half its width
    sheer = np.asarray(sheer, float)
    o = np.argsort(sheer[:, 0])

    def half(x):
        return np.minimum(fl["width"] / 2, np.interp(x, sheer[o, 0], np.abs(sheer[o, 1])) - fl["margin"])
    x0 = xs - fl["length"]
    xx = np.linspace(x0, xs, 400)
    ok = xx[half(xx) >= t / 2 + fl["beside_plate"]]
    x1 = float(ok.max())
    xr = x0 + float(half(np.array([x0]))[0])                      # the aft end rounded to a half circle
    xa = np.linspace(xr, x1, 24)
    ha = half(xa)
    rr = float(half(np.array([xr]))[0])
    arc = [(xr - rr * math.sin(a), rr * math.cos(a)) for a in np.linspace(0.0, math.pi, 13)[1:-1]]
    P2 = np.array([(x, h) for x, h in zip(xa, ha)] + [(x, -h) for x, h in zip(xa[::-1], ha[::-1])] + arc)

    def lift(dz):
        return lambda X_, Y_: shell.deck_z(np.asarray(X_), np.asarray(Y_)) + dz
    rings = [np.column_stack([P2, lift(dz)(P2[:, 0], P2[:, 1])]) for dz in (-fl["let_in"], fl["proud"])]
    V, F = deck.loft_rings(rings, cap0=(4, lift(-fl["let_in"])), cap1=(4, lift(fl["proud"])))
    solid(part, V, F, "Bronze", lab(group, "deck plate"), "Stem head and deck plates")
    return t


# ------------------------------------------------------------------------------------------------ runners
def best_plane(dirs, around):
    """The tang's heading (radial, in the mast's section) whose plane through the mast's axis takes the pulls `dirs`
    best: the least of the largest angle any of them makes with the plane. `around` is a first guess."""
    best = None
    for k in range(-90, 91):
        ph = math.radians(k * 0.5)
        rad = unit(math.cos(ph) * around + math.sin(ph) * np.cross(A, around))
        N = unit(np.cross(rad, A))
        worst = max(abs(math.degrees(math.asin(max(-1.0, min(1.0, float(unit(d) @ N)))))) for d in dirs)
        # the plane holds the pull on the tang's own side, not through the mast
        ok = all(float(unit(d) @ rad) > -0.2 for d in dirs)
        if ok and (best is None or worst < best[0]):
            best = (worst, rad)
    return best[1], best[0]


class Block:
    """A bronze block: the head's pin H, ax from the head toward the sheaves, e in the sheaves' plane, nsh sheaves on
    one axle along n = ax x e. Builds its cheeks, sheaves, axle, head bridge and lug (and a becket at its tail)."""

    def __init__(self, part, H, ax, e, nsh, rope_d, sheave_d, group, becket=False, lug_size=None, lug_axis=None,
                 cat="Runner and checkstay blocks"):
        b = SR["runners"]["block"]
        self.ax = unit(ax)
        self.e = unit(e - (e @ self.ax) * self.ax)
        self.n = np.cross(self.ax, self.e)
        self.Rs = sheave_d / 2
        Rc = self.Rs + b["cheek_over"]
        ct = b["cheek_t"]
        sw = rope_d + 0.004
        self.g = sw + 2 * b["sheave_side"] + ct
        lug, lh, lt = b["lug"], b["lug_height"], b["lug_thickness"]
        if lug_size is not None:                          # a pendant's own tang on the block (its height, thickness)
            lh, lt = lug_size
            lug = max(lug, lh)
        self.C = H + (Rc + 0.03 + lug - lh / 2) * self.ax
        self.reach = Rc + 0.03 + lug - lh / 2             # the pin to the sheaves' centre
        self.lug_h = lh
        self.H = H
        self.lug_t = lt
        self.offsets = [(j - (nsh - 1) / 2) * self.g for j in range(nsh)]
        gs = lab(group, "sheave")
        gk = lab(group, "becket")
        group = lab(group, "block")
        circ = [(Rc * math.cos(q), Rc * math.sin(q)) for q in np.linspace(0, 2 * math.pi, 28, endpoint=False)]
        poly = hull2d(circ + [(-(Rc + 0.03), -0.55 * Rc), (-(Rc + 0.03), 0.55 * Rc)])
        half = nsh / 2 * self.g
        for j in range(nsh + 1):
            c = -half + j * self.g
            flat(part, poly, self.C, self.ax, self.e, self.n, c - ct / 2, c + ct / 2, "Bronze", group, cat)
        for o in self.offsets:
            rev(part, [(self.Rs, o - sw / 2), (self.Rs, o + sw / 2)], self.C, self.n, self.ax, "Bronze", gs, cat, 24)
        ar = b["axle_r"]
        rev(part, [(ar * 1.5, -half - ct / 2 - 0.006), (ar * 1.5, -half - ct / 2), (ar, -half - ct / 2),
                   (ar, half + ct / 2), (ar * 1.5, half + ct / 2), (ar * 1.5, half + ct / 2 + 0.006)],
            self.C, self.n, self.ax, "Bronze", group, cat, 12)
        self.Rc = Rc
        self.half = half + ct / 2                                 # the outer cheeks' faces along n
        # the head: a bridge across the cheeks, clear of the rope where it wraps round the sheaves' head side (slice 7
        # draws the falls round them), and a lug forward to the head's pin, its hole along e or, on a swivel (a collar
        # between the bridge and the lug), along `lug_axis`
        top = max(Rc - 0.01, self.Rs + rope_d / 2 + 0.006)
        bridge = [(-(Rc + 0.035), -0.5 * Rc), (-top, -0.5 * Rc), (-top, 0.5 * Rc), (-(Rc + 0.035), 0.5 * Rc)]
        bh = max(half + ct / 2, lh / 2)                           # across the cheeks, and the lug's height
        flat(part, bridge, self.C, self.ax, self.e, self.n, -bh, bh, "Bronze", group, cat)
        la = self.e if lug_axis is None else unit(lug_axis - (lug_axis @ self.ax) * self.ax)
        plate2(part, self.C, -self.ax, np.cross(la, self.ax), la, Rc + 0.02, Rc + 0.03 + lug, lh, lt, group, cat)
        if lug_axis is not None:
            rev(part, [(0.55 * lh, Rc + 0.03), (0.55 * lh, Rc + 0.05)], self.C, -self.ax, la, "Bronze", group, cat, 16)
        self.lug_axis = la
        self.becket = None
        if becket:
            bl, bt = b["becket"]
            plate2(part, self.C, self.ax, self.n, self.e, Rc - 0.02, Rc + bl, 0.035, bt, gk, cat)
            self.becket = self.C + (Rc + bl - 0.0175) * self.ax

    def side(self, k, w):
        """Sheave k's rim on side w (+1 or -1 of e), where a part leaves it toward the other block."""
        return self.C + self.offsets[k] * self.n + w * self.Rs * self.e

    def clear(self):
        """How far along ax from a sheave's rim a part leaving along ax is clear of the cheeks (and 4 cm more)."""
        return math.sqrt(max(self.Rc ** 2 - self.Rs ** 2, 0.0)) + 0.04


def smooth01(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def drape(A, B, lane, lat, c0, c1, lift, drop, rise=0.6):
    """A slack part of a tackle from A (just below the upper block, where it has left it straight down) to B (just
    forward of the lower block lying on the deck, where it enters it level): it hangs from A to the deck over `drop` m
    (in plan), falling plumb at first and curving down to lie on the deck (a quarter ellipse), moving across to its lane
    (`lane` m across the line c0 to c1 between the blocks' centres, `lat` level and square to it) as it comes down; lies
    on the deck in its lane `lift` above the planking; and over its last `rise` m rises to B's height first and then
    moves across to B, so parts in neighbouring lanes bound for the same side of the block pass one over the other."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    Lp = float(np.linalg.norm((B - A)[:2]))
    s1, s2 = min(drop, 0.45 * Lp), min(rise, 0.3 * Lp)
    zA = deck_z(A[0], A[1]) + lift
    zB = deck_z(B[0], B[1]) + lift
    th = np.linspace(0.0, math.pi / 2, 24)
    ss = []
    for sv in sorted(np.r_[s1 * (1 - np.cos(th)), np.arange(s1, Lp - s2, 0.5), np.linspace(Lp - s2, Lp, 20)]):
        if not ss or sv - ss[-1] > 1e-4:
            ss.append(float(sv))
    pts = []
    for sv in ss:
        f = sv / Lp
        P = A + f * (B - A)
        cl = c0 + f * (c1 - c0)
        across = float((P - cl)[:2] @ lat[:2])
        t2 = (sv - (Lp - s2)) / max(s2, 1e-9)
        if sv < s1:
            w = smooth01(sv / s1)
        elif t2 > 0:
            w = 1.0 - smooth01((t2 - 0.4) / 0.6)
        else:
            w = 1.0
        xy = P[:2] + w * (lane - across) * lat[:2]
        zd = deck_z(xy[0], xy[1]) + lift
        if sv < s1:
            q = math.acos(max(-1.0, min(1.0, 1.0 - sv / s1)))      # sv = s1 (1 - cos q): plumb at A, level on deck
            z = zd + (A[2] - zA) * (1.0 - math.sin(q))
        elif t2 > 0:
            z = zd + (B[2] - zB) * smooth01(t2 / 0.5)
        else:
            z = zd
        pts.append(np.array([xy[0], xy[1], z]))
    pts[0], pts[-1] = A, B
    return pts


def seg_dist(p0, p1, q0, q1):
    """The least distance between segments p0-p1 and q0-q1."""
    d1, d2, r = p1 - p0, q1 - q0, p0 - q0
    a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    if a < 1e-12 and e < 1e-12:
        return float(np.linalg.norm(r))
    if a < 1e-12:
        s, t = 0.0, min(max(f / e, 0.0), 1.0)
    else:
        c = d1 @ r
        if e < 1e-12:
            t, s = 0.0, min(max(-c / a, 0.0), 1.0)
        else:
            b = d1 @ d2
            den = a * e - b * b
            s = min(max((b * f - c * e) / den, 0.0), 1.0) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(max(-c / a, 0.0), 1.0)
            elif t > 1.0:
                t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    return float(np.linalg.norm(p0 + d1 * s - (q0 + d2 * t)))


def parts_room(parts, r):
    """The least gap (m) between any two of a tackle's parts (polylines of rope of radius r)."""
    best = 1e9
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            P, Q = np.asarray(parts[i], float), np.asarray(parts[j], float)
            for a0, a1 in zip(P[:-1], P[1:]):
                for b0, b1 in zip(Q[:-1], Q[1:]):
                    best = min(best, seg_dist(a0, a1, b0, b1) - 2 * r)
    return best


def tackle(part, H_u, H_l, e, spec, group, ax_u=None, slack=False, lug_u=None):
    """Two double blocks, the upper's head pin at H_u, the lower's at H_l (on the padeye's link); the standing part on
    the lower block's becket, four parts. Set: both blocks on the line between their pins, sheaves in the plane of that
    line and e, the parts taut between them. Let off (`slack`, the tackle overhauled): the upper block hangs along ax_u
    (its pendant's line) with its sheaves in the plane of ax_u and the lead to the lower block, the lower block lies on
    its side along the line toward the upper, its sheaves level (the two at right angles, so the parts lead fair), and
    each part leaves and enters its block along it and drapes over the deck between, in a lane of its own. Returns the
    blocks, the parts' length and the parts' polylines."""
    rr = spec["rope_d"] / 2
    kgm = MANILA * math.pi * rr * rr
    if not slack:
        ax = unit(H_l - H_u)
        U = Block(part, H_u, ax, e, 2, spec["rope_d"], spec["sheave_d"], group, lug_size=lug_u)
        Lb = Block(part, H_l, -ax, e, 2, spec["rope_d"], spec["sheave_d"], group, becket=True)

        def at_n(B, o):                             # the lower block's sheave whose offset along U's n is o
            return int(np.argmin([abs(float((B.C + oo * B.n - U.C) @ U.n) - o) for oo in B.offsets]))
        a, b = U.offsets[0], U.offsets[1]
        l_a, l_b = at_n(Lb, a), at_n(Lb, b)
        parts = [[Lb.becket, U.side(0, 1)], [U.side(0, -1), Lb.side(l_a, -1)], [Lb.side(l_a, 1), U.side(1, 1)],
                 [U.side(1, -1), Lb.side(l_b, -1)]]
        fall_k, fall_w = l_b, -1
    else:
        U = Block(part, H_u, ax_u, H_l - H_u, 2, spec["rope_d"], spec["sheave_d"], group, lug_size=lug_u)
        ax_l = unit(H_u - H_l)
        Lb = Block(part, H_l, ax_l, np.cross(UP, ax_l), 2, spec["rope_d"], spec["sheave_d"], group, becket=True)
        lat = unit(np.cross(UP, Lb.C - U.C))
        if float(lat[1]) * float(U.C[1]) > 0:                       # inboard on either side, so the sides mirror
            lat = -lat
        # the reeving, laid so the parts lie on the deck in the order they leave the upper block: across the lead
        # (+lat first) the part from the becket and the next from the upper's +lat sheave, then the two from its other
        # sheave; each pair's outer part from the rim away from the lower block, so it passes under its neighbour
        a = 0 if float(U.offsets[0] * (U.n @ lat)) > 0 else 1
        b = 1 - a
        v = 1 if float(Lb.e @ lat) > 0 else -1
        l1, l2 = (0, 1) if Lb.offsets[0] > Lb.offsets[1] else (1, 0)    # the upper and the lower sheave
        ends = [(Lb.becket, U.side(a, 1)), (U.side(a, -1), Lb.side(l1, v)), (Lb.side(l1, -v), U.side(b, 1)),
                (U.side(b, -1), Lb.side(l2, -v))]
        fall_k, fall_w = l2, -v
        lanes = [2.0, 3.0, 1.0, 0.0]                                 # counted inboard from the lead, clear of the shroud
        pitch = spec["rope_d"] + SR["runners"]["lane_gap"]
        drop = SR["runners"]["slack_drop"] * float(U.C[2] - deck_z(U.C[0], U.C[1]))
        parts = []
        for (p, q), ln in zip(ends, lanes):
            hi, lo = (p, q) if np.linalg.norm(p - U.C) < np.linalg.norm(q - U.C) else (q, p)
            A1 = hi + U.clear() * U.ax
            B1 = lo + (0.04 if lo is Lb.becket else Lb.clear()) * Lb.ax
            path = [hi] + drape(A1, B1, ln * pitch, lat, U.C, Lb.C, rr + SR["runners"]["lie_above_deck"], drop) + [lo]
            parts.append(path if hi is p else path[::-1])
        room = parts_room(parts, rr)
        if room < 0.002:
            raise ValueError(f"{group}: two of the overhauled tackle's parts come within {1000 * room:.1f} mm")
    L = 0.0
    for p in parts:
        L += wire(part, p, rr, lab(group, "fall"), "Tackle falls (manila)", kgm, slot="Rope", n=10, bend=0.0)
    # where the last part enters the lower block: slice 7 takes the fall on round that sheave's head side to its winch
    Lb.fall = {"centre": Lb.C + Lb.offsets[fall_k] * Lb.n, "ax": Lb.ax, "e": Lb.e, "n": Lb.n, "R": Lb.Rs,
               "enters": Lb.side(fall_k, fall_w), "side": fall_w, "arrives": unit(parts[3][-1] - parts[3][-2]),
               "rope_d": spec["rope_d"], "half_gap": Lb.g / 2}
    return U, Lb, L, parts


def padeye(part, P, toward, group):
    """A bronze padeye on the deck at P (x, y), its eye's plane holding the direction `toward` (level part)."""
    pe = SR["runners"]["padeye"]
    zd = deck_z(P[0], P[1])
    d = unit(np.array([toward[0], toward[1], 0.0]))
    nrm = np.cross(UP, d)
    L, W, t = pe["base"]
    cat = "Padeyes and links"
    flat(part, deck.rrect(0.0, 0.0, L, W, 0.025), np.array([P[0], P[1], zd]), d, nrm, UP, -0.006, t, "Bronze",
         lab(group, "padeye"), cat)
    h, et = pe["height"], pe["thickness"]
    hole = pe["hole_above_deck"]
    q = np.linspace(0.0, math.pi, 11)
    rr = h - hole
    poly = [(0.06, -0.004)] + [(rr * math.cos(a), hole + rr * math.sin(a)) for a in q] + [(-0.06, -0.004)]
    flat(part, poly, np.array([P[0], P[1], zd]), d, UP, nrm, -et / 2, et / 2, "Bronze", lab(group, "padeye"), cat)
    return np.array([P[0], P[1], zd + hole]), nrm


def runner_rig(parts, rep, pts, sheer):
    """The runners and checkstays: their tangs, padeyes, and each side's set and let-off states."""
    rn = SR["runners"]
    fit = parts["RunnerFittings"]
    sheer = np.asarray(sheer, float)
    o = np.argsort(sheer[:, 0])
    rep["runners"] = {}
    s_h = pts["hounds_s"]
    for kind in ("runner", "checkstay"):
        spec = rn[kind]
        r = wire_r(kind)
        rep["runners"][kind] = {}
        for sd, side in SIDES:
            # the padeye
            xd = spec["deck_x"]
            if "deck_y" in spec:
                yd = sd * spec["deck_y"]
            else:
                yd = sd * (float(np.interp(xd, sheer[o, 0], np.abs(sheer[o, 1]))) - spec["inboard"])
            # the tang: on the hounds band (runner) or the top spreaders' tang band (checkstay)
            s_t = s_h + spars.s_at(spec["tang_above_hounds"]) if kind == "runner" else rep["tang_band_s"][2]
            d3 = rep["shrouds"][side]["d3"]
            lash_z = deck_z(d3["chainplate_pin"][0], d3["chainplate_pin"][1]) + spec["lashed_above_deck"]
            a, b = d3["passes"][-1], d3["chainplate_pin"]               # D3's run from the lower tip to its pin
            Q = a + (lash_z - a[2]) / (b[2] - a[2]) * (b - a)            # on D3 at the lashing's height
            # let off, the lashing holds the pendant aft of D3 (the runner) or inboard of it (the checkstay), and the
            # upper block hangs on the pendant's end below it
            W = Q - rn["lash_aft"] * X if spec["lash"] == "aft" else Q - sd * rn["lash_inboard"] * Y
            guess = unit(-FW + 0.15 * sd * Y)
            T_guess = at(s_t) + 0.3 * guess
            P_hole_guess = np.array([xd, yd, deck_z(xd, yd) + rn["padeye"]["hole_above_deck"]])
            rad, _ = best_plane([P_hole_guess - T_guess, W - T_guess], guess)
            group_t = f"{SR['wires'][kind]['label'][:-1]} tang, {side}"
            T, tN, tt, te = tang(fit, s_t, rad, r, group_t, reach=spec.get("tang_reach", FIT["tang"]["reach"]) * r)
            H_off = W + rn["block_hang"] * unit(W - T)
            Pd = np.array([xd, yd])
            set_dir = T - np.array([xd, yd, deck_z(xd, yd)])
            hole, pnrm = padeye(fit, Pd, set_dir, f"{SR['wires'][kind]['label'][:-1]} padeye, {side}")
            # the pendant is one wire, the same length in both states: let off, it reaches from the tang's pin to the
            # upper block's pin lashed on the shroud; set, it runs from the tang toward the padeye and the tackle takes
            # up the rest
            L_pend = float(np.linalg.norm(H_off - T))
            lug_u = (FIT["tang"]["height"] * r, FIT["tang"]["thickness"] * r)   # the upper block's lug: a tang's size
            # how far each pull, set and let off, is out of the tang's plane (tN its pin's axis)
            worst = max(math.degrees(math.asin(min(1.0, abs(float(unit(d) @ tN))))) for d in (hole - T, W - T))
            rec = {"tang_pin": T, "tang_off_plane_deg": round(worst, 2), "padeye_hole": hole, "lashed_to_d3_at": Q,
                   "pendant_pin_to_pin_m": round(L_pend, 3)}
            for state in ("Set", "LetOff"):
                name = f"{'Runner' if kind == 'runner' else 'Checkstay'}.{side.capitalize()}.{state}"
                p = parts.setdefault(name, SparPart(name))
                group = f"{SR['wires'][kind]['label'][:-1]}, {side}, {state.lower()}"
                lk = rn["padeye"]["link"]
                if state == "Set":
                    ut = unit(T - hole)
                    H_l = hole + lk * ut
                    blk = SR["runners"]["block"]
                    Rc = spec["tackle"]["sheave_d"] / 2 + blk["cheek_over"]
                    c_l = Rc + 0.03 + blk["lug"] - blk["lug_height"] / 2
                    c_u = Rc + 0.03 + max(blk["lug"], lug_u[0]) - lug_u[0] / 2
                    H_u = T - L_pend * ut
                    gap = float((H_u - H_l) @ ut) - c_u - c_l
                    if gap < spec["min_set_gap"]:
                        raise ValueError(f"the set {side} {kind}'s blocks are only {gap:.3f} m apart: its pendant is "
                                         f"too long for the lashing on the shroud")
                    e = perp(ut)
                    U, Lb, Lp, prt = tackle(p, H_u, H_l, e, spec["tackle"], group, lug_u=lug_u)
                else:
                    H_u = H_off
                    ut = unit(H_u - hole)
                    H_l = hole + lk * ut
                    U, Lb, Lp, prt = tackle(p, H_u, H_l, None, spec["tackle"], group, ax_u=unit(H_u - T),
                                            slack=True, lug_u=lug_u)
                    # the lashing: a loop round D3 and the pendant, square to D3
                    rl = 0.006
                    d3u = unit(a - b)
                    dd = W - Q
                    dd = unit(dd - (dd @ d3u) * d3u)
                    lat = np.cross(d3u, dd)
                    rho, rho2 = wire_r("d3") + rl + 0.003, r + rl + 0.003
                    Lq = float((W - Q) @ dd)
                    path = [Q + rho * (math.cos(t) * -dd + math.sin(t) * lat) for t in np.linspace(-math.pi / 2,
                                                                                                   math.pi / 2, 9)]
                    path += [Q + Lq * dd + rho2 * (math.cos(t) * dd + math.sin(t) * lat)
                             for t in np.linspace(math.pi / 2, -math.pi / 2, 9)]
                    loop(p, np.array(path)[::-1], rl, lab(group, "lashing"), "Lashings", MANILA * math.pi * rl * rl)
                # the link from the padeye to the lower block's lug
                mid = 0.5 * (hole + H_l)
                lr = rn["padeye"]["link_r"]
                lp = ring_path(mid, np.cross(unit(H_l - hole), pnrm) if np.linalg.norm(np.cross(unit(H_l - hole), pnrm))
                               > 0.1 else perp(H_l - hole), unit(H_l - hole), 0.5 * float(np.linalg.norm(H_l - hole)))
                loop(p, lp, lr, lab(group, "link"), "Padeyes and links", STEEL * math.pi * lr * lr, slot="Galvanised")
                # the pendant: from the tang's pin to the upper block's lug
                w_hi = terminal(p, T, H_u - T, tN, r, tt, group, te)
                w_lo = terminal(p, H_u, T - H_u, U.e, r, U.lug_t, group, U.lug_h / 2)
                Lw = wire(p, [w_hi, w_lo], r, group, SR["wires"][kind]["label"], kg_per_m(kind), slot=slot_of(kind))
                rep["wires"].append({"name": group, "group": group, "object": name, "key": kind, "r": r,
                                     "path": [w_hi, w_lo],
                                     "passes": [], "state": (side, state)})
                for k, pp in enumerate(prt):
                    rep["wires"].append({"name": f"{group}, fall {k + 1}", "group": group, "object": name,
                                         "key": "fall",
                                         "r": spec["tackle"]["rope_d"] / 2, "path": pp, "passes": [],
                                         "state": (side, state), "rope": True})
                rec[state] = {"pendant_m": Lw, "falls_m": Lp, "upper_block_pin": H_u, "lower_block_pin": H_l,
                              "fall_sheave": Lb.fall,
                              "tackle_axis": unit(H_u - H_l), "parts_least_room_mm": round(1000 * parts_room(
                                  prt, spec["tackle"]["rope_d"] / 2), 1)}
                if state == "Set":
                    rec[state]["blocks_apart_m"] = round(gap, 3)
            # the falls' rope is the same length in both states: the let-off parts plus the tail to the winch; weigh
            # it so in both (replacing what wire() weighed from the drawn parts)
            rope_m = rec["LetOff"]["falls_m"] + rn["tail_allowance_m"]
            rr = spec["tackle"]["rope_d"] / 2
            for state in ("Set", "LetOff"):
                name = f"{'Runner' if kind == 'runner' else 'Checkstay'}.{side.capitalize()}.{state}"
                p = parts[name]
                drawn = [m for m in p.masses if m["part"] == "Tackle falls (manila)"]
                kg = sum(m["kg"] for m in drawn)
                cen = sum(np.array(m["centre"]) * m["kg"] for m in drawn) / kg
                p.masses = [m for m in p.masses if m["part"] != "Tackle falls (manila)"]
                p.masses.append({"part": "Tackle falls (manila)",
                                 "kg": round(float(MANILA * math.pi * rr * rr * rope_m), 1),
                                 "centre": [round(float(v), 3) for v in cen], "how": "length"})
            rec["rope_m"] = rope_m
            rep["runners"][kind][side] = rec
    return rep


# ------------------------------------------------------------------------------------------------ the whole rigging
OBJECTS = ("Shrouds", "Stays", "RunnerFittings")
STATES = tuple(f"{k}.{s}.{t}" for k in ("Runner", "Checkstay") for s in ("Starboard", "Port")
               for t in ("Set", "LetOff"))
SAILING = ("Runner.Starboard.Set", "Runner.Port.LetOff", "Checkstay.Starboard.Set", "Checkstay.Port.LetOff")


def build(spars_rep, sheer=None):
    """{name: SparPart} for the rigging's objects and a report: each wire's pins and length, the free spans for the
    clearance checks, the runners' states, the weights against the size card's standing rigging, the strength sum."""
    sheer = deck.loft_sheer() if sheer is None else np.asarray(sheer, float)
    pts = spars_rep["_pts"]
    parts = {k: SparPart(k) for k in OBJECTS}
    rep = {"wires": []}
    shrouds(parts["Shrouds"], rep, pts, sheer)
    stays(parts["Stays"], rep, pts, sheer)
    runner_rig(parts, rep, pts, sheer)
    rep["weights"] = rigging_weights(parts)
    rep["strength"] = strength(rep)
    rep["sizes"] = {k: {"d_mm": round(1000 * v["d"], 1), "construction": v["construction"], "label": v["label"],
                        "kg_per_m": round(kg_per_m(k), 3), "breaking_kn": round(breaking_kn(k), 0)}
                    for k, v in SR["wires"].items() if k != "note"}
    return parts, rep


def rigging_weights(parts):
    """The weight of the rigging as sailed (on starboard tack: the starboard runner and checkstay set, the port pair
    let off) by kind, against the size card's standing rigging."""
    out = {"rows": [], "objects": {}}
    agg, tot, mom = {}, 0.0, np.zeros(3)
    for name in OBJECTS + SAILING:
        p = parts[name]
        kg = sum(m["kg"] for m in p.masses)
        m3 = sum((np.array(m["centre"]) * m["kg"] for m in p.masses), np.zeros(3))
        out["objects"][name] = {"kg": round(kg, 1), "centre": rnd(m3 / kg)}
        for m in p.masses:
            a = agg.setdefault(m["part"], {"kg": 0.0, "m": np.zeros(3), "pieces": 0})
            a["kg"] += m["kg"]
            a["m"] += m["kg"] * np.array(m["centre"])
            a["pieces"] += 1
        tot += kg
        mom += m3
    out["rows"] = [{"part": k, "kg": round(a["kg"], 1), "centre": rnd(a["m"] / a["kg"]), "pieces": a["pieces"]}
                   for k, a in agg.items()]
    out["sailing_state"] = list(SAILING)
    out["total_kg"] = round(tot, 1)
    out["total_long_tons"] = round(tot / deck.LT_KG, 3)
    out["centre"] = rnd(mom / tot)
    out["card_long_tons"] = loft.SPECS["weights"]["standing_rigging"]
    out["card_centre_xz"] = loft.SPECS["weight_positions"]["standing_rigging"]
    return out


def fittings_strength(rep):
    """Each fitting's strength against its wire's breaking load (kN), the fitting's over the wire's: its jaw's pin in
    double shear (0.6 x the bronze's breaking stress), the jaw's two cheeks across the pin's hole and beyond it (shear
    out along two planes each, 2 t e, e from the pin's centre to the end), the rigging screw's studs at the thread's
    root (0.8 of the stud's diameter) and its body's two bars, and the plate each end pins to (a tang, slice 4's tangs
    at the hounds, the backstay's crane, a chainplate, the stem plate, the runner's tang on its upper block) across
    its hole and beyond it. The runners' tackles (blocks, padeyes, links and falls) are drawn, not sized: slice 7's."""
    sb = SR["material"]["bronze_breaking_mpa"] * 1e3                 # kN per square metre / 1000: kN with m^2
    sc = SR["material"]["chainplate_steel_breaking_mpa"] * 1e3
    tm, sw, cp, tg = FIT["terminal"], FIT["screw"], FIT["chainplate"], FIT["tang"]
    ht, bc = spars.RG["hounds"]["tang"], SR["stays"]["backstay"]["crane"]
    rows = []

    def add(key, fitting, how, kn):
        rows.append({"wire": key, "fitting": fitting, "how": how, "kn": round(kn, 1),
                     "over_wire": round(kn / breaking_kn(key), 3)})

    def jaw(key, what):
        r = wire_r(key)
        rp, ct = tm["pin_r"] * r, tm["cheek_t"] * r
        add(key, what, "pin in double shear", 2 * math.pi * rp * rp * 0.6 * sb)
        add(key, what, "cheeks across the pin's hole", 2 * (2 * tm["cheek_half"] * r - 2 * rp) * ct * sb)
        add(key, what, "cheeks beyond the pin", 2 * 2 * ct * tm["jaw_back"] * r * 0.6 * sb)

    def plate(key, what, h, t, e, mpa):
        rp = tm["pin_r"] * wire_r(key)
        add(key, what, "across the pin's hole", (h - 2 * rp) * t * mpa)
        add(key, what, "beyond the pin", 2 * t * e * 0.6 * mpa)

    def screw(key):
        r = wire_r(key)
        jaw(key, "rigging screw's toggle")
        add(key, "rigging screw", "studs at the thread's root", math.pi * (0.8 * sw["stud_r"] * r) ** 2 * sb)
        add(key, "rigging screw", "body's two bars", 2 * sw["bar_w"] * r * sw["bar_t"] * r * sb)

    def own_tang(key, what="tang"):
        r = wire_r(key)
        plate(key, what, tg["height"] * r, tg["thickness"] * r, tg["height"] * r / 2, sb)

    def chain(key):
        r = wire_r(key)
        plate(key, "chainplate", cp["width"] * r, cp["thickness"] * r, cp["above_pin"] * r, sc)

    for key in [k for k in SR["wires"] if k != "note"]:
        jaw(key, "socket's jaw")
        if key in ("cap", "forestay"):
            plate(key, "slice 4's tang at the hounds", ht["height"], ht["thickness"], ht["height"] / 2, sb)
        elif key == "backstay":
            plate(key, "backstay crane", bc["height"], bc["thickness"], bc["height"] / 2, sb)
        else:
            own_tang(key)
        if key in ("runner", "checkstay"):
            jaw(key, "socket's jaw at the block")
            own_tang(key, "upper block's lug")
            continue
        screw(key)
        if key == "forestay":
            r = wire_r(key)
            plate(key, "stem plate", cp["width"] * r, FIT["stem_flange"]["thickness"] * cp["thickness"] * r,
                  cp["above_pin"] * r, sb)
        elif key == "jumper":
            own_tang(key, "tang at the foot")
        else:
            chain(key)
    least = min(rows, key=lambda q: q["over_wire"])
    return {"rows": rows, "least": least, "ok": least["over_wire"] >= 1.0}


def balance(rep):
    """Each running stay against the stay it balances: the runner's breaking load x the fore-and-aft share of its pull
    (set) against the forestay's, the checkstay's against the staysail stay's."""
    out = {}
    for kind, stay, a, b in (("runner", "forestay", "tang_pin", "stem_pin"),
                             ("checkstay", "staysail", "tang_pin", "deck_pin")):
        st = rep["forestay" if stay == "forestay" else "staysail_stay"]
        fs = abs(float(unit(np.asarray(st[a]) - np.asarray(st[b])) @ X))
        ru = rep["runners"][kind]["starboard"]
        fr = abs(float(unit(np.asarray(ru["tang_pin"]) - np.asarray(ru["padeye_hole"])) @ X))
        out[kind] = {"balances": stay, "fore_aft_share": round(fr, 3), "stay_fore_aft_share": round(fs, 3),
                     "fore_aft_kn": round(breaking_kn(kind) * fr, 0),
                     "stay_fore_aft_kn": round(breaking_kn(stay) * fs, 0),
                     "ratio": round(breaking_kn(kind) * fr / (breaking_kn(stay) * fs), 3)}
    out["ok"] = all(v["ratio"] >= 1.0 for v in out.values() if isinstance(v, dict))
    return out


def strength(rep):
    """The strength checks: each fitting against its wire, each running stay against the stay it balances, and a rough
    check of the windward shrouds: the moment of their breaking loads about the centreline at the deck (each wire's
    breaking load x the upright part of its pull x its chainplate's distance out), which build_jclass.py sets against
    her righting moment heeled 30 degrees (displacement x GM x sin 30, the small-angle figure)."""
    side = rep["shrouds"]["starboard"]
    mom = 0.0
    rows = []
    for key, row in side.items():
        C = row["chainplate_pin"]
        up = unit((row["passes"][-1] if row["passes"] else row["top_pin"]) - C)
        bk = breaking_kn(key)
        rows.append({"wire": key, "breaking_kn": round(bk, 0)})
        mom += bk * up[2] * float(C[1])                              # the upright pull's moment about the centreline
    fit, bal = fittings_strength(rep), balance(rep)
    if not fit["ok"]:
        raise ValueError(f"a fitting is weaker than its wire: {fit['least']}")
    if not bal["ok"]:
        raise ValueError(f"a running stay is weaker than the stay it balances: {bal}")
    return {"rows": rows, "breaking_moment_knm": round(mom, 0), "fittings": fit, "balance": bal}


if __name__ == "__main__":
    _, sr = spars.build()
    parts, r = build(sr)
    print(json.dumps({k: r[k] for k in ("sizes", "strength")}, indent=1, default=lambda v: rnd(v)))
    w = r["weights"]
    print(json.dumps(w, indent=1, default=lambda v: rnd(v)))
    print({k: (len(p.V), len(p.F)) for k, p in parts.items()})
