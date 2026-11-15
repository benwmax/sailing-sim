"""Bluebonnet's deck hardware (docs/jclass-8), from hardware_bluebonnet.json: what stands on her deck besides the
winches and the leads (slice 7's), and her flags.

  stem_head      a bronze casting over the deck's tip, taking both ends of the toe rail, cast round the forestay's plate
  cleats         bronze mooring cleats at the bow, amidships (springs) and on the quarters, each with a closed fairlead
                 on the toe rail its line leads through
  cowls          bronze cowl vents, red inside, over the fo'c'sle and the after accommodation: standing in their
                 flanges in harbour, struck below at sea and the flanges capped
  deck prisms    glass prisms let into the planking over the cabins, flush on deck, their pendants below
  anchor         a fisherman's anchor stowed flat on the port foredeck on teak chocks, lashed; the chain pipe's cap
  bow chock      the anchor cable's open chock on the port bow's toe rail (slice 9, with the cable below)
  lights         the side lights on their light boards by the shrouds and the stern light on the counter: bronze
                 lanterns with coloured lenses over their arcs
  ensign         the staff's socket on the counter; in harbour (the Moored suit) the staff and a 48-star ensign
  burgee         the club's burgee on a stick on the mast's truck, flying down each suit's apparent wind

    parts, rep = hardware.build(sheer, pts)

Objects: "DeckHardware" (everything fixed, the cowls' flanges among it), "Ensign.Moored" (the staff and ensign, in
harbour only), "Cowls.Moored" (the cowls standing, in harbour), one "CowlCaps.<suit>" for each other suit (the flanges'
caps) and one "Burgee.<suit>" per suit (the stick and the burgee as it flies in that suit). Each is a set of closed
solids labelled "<group> | <kind>" (kinds: stem head, cleat, fairlead, cowl, cowl cap, deck prism, anchor, chock,
lashing, chain pipe, bow chock, lantern, lens, light board, bracket, standard, socket, staff, ensign, stick, spindle,
burgee), weighed from its geometry and the json's densities; the ground tackle below (the bower, her cable and the
windlass) is the interior's (interior.py, slice 9). The flags' faces
carry their pattern's coordinates in metres in the "Spar" UV map (x along the fly from the hoist, y down the hoist:
from its top on the ensign, from its middle on the burgee); hardware_materials.py draws them. Units are metres in the
hull's frame (X forward, Y starboard, Z up). Plain Python: no Blender needed.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck  # noqa: E402
import rigging  # noqa: E402
import shell  # noqa: E402
import spars  # noqa: E402
import sails  # noqa: E402
import winches  # noqa: E402
from spars import SparPart, unit, BRZ, UP  # noqa: E402

HW = json.load(open(os.path.join(HERE, "hardware_bluebonnet.json")))
MT = HW["material"]
TR = deck.DK["toe_rail"]
X = np.array([1.0, 0.0, 0.0])
Y = np.array([0.0, 1.0, 0.0])
SIDES = ((1, "starboard"), (-1, "port"))
SUITS = [k for k in sails.SL["suits"] if k != "note"]

CAT_STEM = "Stem head fitting (bronze)"
CAT_MOOR = "Mooring cleats and fairleads (bronze)"
CAT_COWL = "Cowl vents (bronze)"
CAT_PRISM = "Deck prisms (glass)"
CAT_ANCHOR = "Anchor (iron), chocks and lashings"
CAT_PIPE = "Chain pipe (bronze)"
CAT_CHOCK = "Bow chock (bronze)"
CAT_NAV = "Side and stern lights, light boards"
CAT_ENSIGN = "Ensign staff, socket and ensign"
CAT_BURGEE = "Burgee and its stick"


def lab(group, kind):
    return f"{group} | {kind}"


def deck_z(x, y):
    return float(shell.deck_z(np.array([x]), np.array([y]))[0])


def plan_dir(deg):
    """A plan direction `deg` from forward, to starboard positive."""
    a = math.radians(deg)
    return np.array([math.cos(a), math.sin(a), 0.0])


def solid(part, V, F, slot, label, cat, rho):
    """A closed solid, weighed as rho x its volume under `cat` (rho None: not weighed, the weight is elsewhere)."""
    V = np.asarray(V, float)
    if deck.signed_volume(V, F) < 0:
        F = [tuple(f[::-1]) for f in F]
    part.add(V, F, slot, None, label)
    if rho:
        part.weigh(V, F, ("solid", rho), cat)


def cast(part, V, F, slot, label, cat, wall=None):
    """A thin casting drawn as a closed solid, weighed as bronze `wall` thick over its skin."""
    V = np.asarray(V, float)
    if deck.signed_volume(V, F) < 0:
        F = [tuple(f[::-1]) for f in F]
    part.add(V, F, slot, None, label)
    part.weigh(V, F, ("cast", BRZ, wall or MT["wall"]), cat)


def rounded_rect(hu, hv, r, n=4):
    """A rounded rectangle's outline (half sizes hu, hv, corner radius r), counter-clockwise, as (u, v)."""
    r = min(r, hu * 0.999, hv * 0.999)
    out = []
    for cu, cv, a0 in ((hu - r, hv - r, 0.0), (-hu + r, hv - r, 90.0), (-hu + r, -hv + r, 180.0),
                       (hu - r, -hv + r, 270.0)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            out.append((cu + r * math.cos(a), cv + r * math.sin(a)))
    return np.array(out)


def section_rings(path, frames, sections):
    """Rings along `path`: at each point its section (an outline (m, 2) in the frame's (A, B)) laid in that frame."""
    return [P + S[:, :1] * A + S[:, 1:2] * B for P, (A, B), S in zip(path, frames, sections)]


# ------------------------------------------------------------------------------------------------ the sheer and rail
class Sheer:
    """The deck's edge: half breadth and height at x, and the toe rail's top along it."""

    def __init__(self, sheer):
        s = np.asarray(sheer, float)
        o = np.argsort(s[:, 0])
        self.x, self.hb, self.z = s[o, 0], np.abs(s[o, 1]), s[o, 2]

    def half(self, x):
        return float(np.interp(x, self.x, self.hb))

    def height(self, x):
        return float(np.interp(x, self.x, self.z))

    def slope(self, x, h=0.02):
        return (self.half(x + h) - self.half(x - h)) / (2 * h)

    def rail(self, x, sd, h=0.02):
        """The toe rail's top at x on side sd: its middle (on the rail's crown), the rail's direction (forward along it
        and rising with the sheer), the rail's up (square to it) and the plan normal outboard."""
        sl = self.slope(x)
        dz = (self.height(x + h) - self.height(x - h)) / (2 * h)
        t = unit(np.array([1.0, sd * sl, dz]))
        out = unit(np.array([-sl, sd * 1.0, 0.0]))
        up = unit(UP - (UP @ t) * t)
        mid = TR["inset"] + 0.5 * TR["top_width"]               # the crown of the rail's top, in from the sheer
        p = np.array([x, sd * self.half(x), self.height(x) + TR["height"]]) - mid * out
        return p, t, up, out


# ------------------------------------------------------------------------------------------------ the stem head
def stem_head(part, sh):
    """The casting over the deck's tip: its plan the deck's edge `inset` in, its top level `height` above the deck's
    centreline at each x, the edges rounded by `bevel`."""
    sp = HW["stem_head"]
    x0 = sp["from_x"]
    xs = np.linspace(x0, sh.x.max(), 400)
    w = np.array([sh.half(x) for x in xs]) - sp["inset"]
    x1 = float(xs[w >= sp["tip_half_width"]].max())

    def shape(o):
        """The plan `o` m out from the casting's foot (o < 0: in), counter-clockwise from the after end to port."""
        xa = np.linspace(x0, x1, 26)
        ha = np.maximum(np.array([sh.half(x) for x in xa]) - sp["inset"] + o, 0.004)
        rr = float(ha[-1])
        xa = xa.copy()
        xa[0] -= o
        tip = [(x1 + rr * math.sin(a), -rr * math.cos(a)) for a in np.linspace(0.0, math.pi, 9)[1:-1]]
        aft = [(x0 - o, h) for h in np.linspace(ha[0], -ha[0], 7)[1:-1]]
        P = [(x, -h) for x, h in zip(xa, ha)] + tip + [(x, h) for x, h in zip(xa[::-1], ha[::-1])] + aft
        return np.array(P)

    # where the toe rail's ends come in under its after end, the casting rises clear over them: its top there (less
    # its rounded edge) 'over_rail' above the rail's top, easing down to its own height 'rise_length' forward of them
    xr = float(xs[np.array([sh.half(x) for x in xs]) >= TR["ends_at_half_breadth"]].max())
    xq = np.linspace(x0, xr, 12)
    need = max(sh.height(x) + TR["height"] + sp["bevel"] + sp["over_rail"]
               - float(shell.deck_z(np.array([x]), np.zeros(1))[0]) - sp["height"] for x in xq)
    lift = max(need, 0.0)

    def z_top(xx):
        xx = np.asarray(xx, float)
        f = np.clip((xr + 0.005 + sp["rise_length"] - xx) / sp["rise_length"], 0.0, 1.0)
        return shell.deck_z(xx, np.zeros(len(xx))) + sp["height"] + lift * (0.5 - 0.5 * np.cos(math.pi * f))
    tmp = SparPart("tmp")
    deck.on_deck_prism(shape, z_top, "Bronze", None, None, tmp, bevel=sp["bevel"])
    cast(part, tmp.V, tmp.F, "Bronze", lab("Stem head", "stem head"), CAT_STEM, sp["wall"])
    return {"from_x": x0, "tip_x": round(x1 + sh.half(x1) - sp["inset"], 3), "height_m": sp["height"],
            "rail_ends_x": round(xr, 3), "rises_over_rail_m": round(lift, 3)}


# ------------------------------------------------------------------------------------------------ mooring
def fairlead(part, sh, x, sd, group, toward):
    """A closed fairlead on the toe rail at x: a base along the rail's top, let into it, and a ring over the line's
    hole. The hole is bored at an angle through the ring (its body stays along the rail): its axis halves the angle
    between square out from the rail and the line's lead in to `toward` (its cleat), so the line bends half as much
    at each mouth. Returns the hole's centre, its axis (outboard), the inboard lead's angle off that axis and the
    hole's skew from square to the rail (degrees)."""
    fl = HW["fairlead"]
    p, t, up, out = sh.rail(x, sd)
    L, Hh, W = fl["length"], fl["height"], fl["width"]
    hl, hh, hu = fl["hole_length"], fl["hole_height"], fl["hole_up"]
    a, b = (hl - hh) / 2, hh / 2
    T = Hh - (hu + b)                                       # the ring's thickness over the hole
    C = p + hu * up
    # the line in, reversed (from the cleat out through the hole), in the rail's plan frame
    r = np.asarray(C, float) - np.asarray(toward, float)
    beta = math.atan2(float(r @ t), float(r @ out))
    k = math.tan(beta / 2)                                  # the hole's skew: along the rail per unit across it
    axis = unit(out + k * t)

    def bend(V):
        """Lay the casting, drawn in the rail's frame at x, along the rail as it curves in plan and rises with the
        sheer: each point at its own place along the rail, the same distance out and up from its crown."""
        d = np.asarray(V, float) - p
        out_V = []
        for (u, v, w) in zip(d @ t, d @ out, d @ up):
            pu, _, upu, outu = sh.rail(x + u * t[0], sd)
            out_V.append(pu + v * outu + w * upu)
        return np.array(out_V)
    # the base: a rounded block along the rail from inside it up to the hole's bottom, as wide as the casting
    base = rounded_rect(L / 2, W / 2, 0.03, 5)
    lo = p + (-fl["let_in"]) * up
    V, F = deck.loft_rings([lo + base[:, :1] * t + base[:, 1:2] * out,
                            p + (hu - b + 0.004) * up + base[:, :1] * t * 0.92 + base[:, 1:2] * out])
    solid(part, bend(V), F, "Bronze", lab(group, "fairlead"), CAT_MOOR, BRZ)
    # the ring: the hole's outline (a slot a long, b round) swept by a rounded section T thick and a millimetre inside
    # the base's sides, sheared along the rail across its width so the hole runs along `axis`
    loop_pts, loop_n = [], []
    for j in range(40):
        q = 2 * math.pi * j / 40
        c, s = math.cos(q), math.sin(q)
        cx = a if c >= 0 else -a
        loop_pts.append(C + (cx + b * c) * t + b * s * up)
        loop_n.append(c * t + s * up)
    sec = rounded_rect(T / 2, W / 2 - 0.001, 0.009, 3)
    rings = [P + (T / 2 + sec[:, :1]) * nrm + sec[:, 1:2] * (out + k * t) for P, nrm in zip(loop_pts, loop_n)]
    V, F = deck.loft_rings(rings, closed=True)
    solid(part, bend(V), F, "Bronze", lab(group, "fairlead"), CAT_MOOR, BRZ)
    lin = unit(np.asarray(toward, float) - C)
    off = math.degrees(math.acos(min(1.0, abs(float(lin @ axis)))))
    return C, axis, off, math.degrees(beta / 2)


def mooring(part, sh):
    """The mooring cleats and their fairleads, both sides. Returns each pair's report and each line's lead (from
    outboard along the fairlead's hole, through it, to the cleat's horns) for the build's room check: the part in the
    hole may touch only its fairlead, the part from the hole's inboard mouth to the cleat only its cleat."""
    cs = HW["cleats"]
    fl = HW["fairlead"]
    rep, leads = {}, []
    for name, pl in cs["places"].items():
        for sd, side in SIDES:
            cg = f"{name} cleat, {side}"
            fg = f"{name} fairlead, {side}"
            at = np.array([pl["at"][0], sd * pl["at"][1]])
            cl = winches.cleat(part, at, sd * pl["deg"], cs["size"], cg, cat=CAT_MOOR)
            horn = cl["O"] + 0.5 * (cs["size"]["h_under"] + cs["size"]["h_top"]) * UP
            hole, axis, off, skew = fairlead(part, sh, pl["fairlead"], sd, fg, horn)
            # the inboard mouth: where the line in crosses the ring's inboard face (half its width in from the hole's
            # centre, along the axis)
            lin = unit(horn - hole)
            mouth = hole + lin * ((0.5 * fl["width"] - 0.001) / max(abs(float(lin @ axis)), 1e-6))
            leads.append({"name": f"{name} line, {side}", "group": f"{name} line, {side}", "object": "",
                          "r": 0.012, "rope": True,
                          "pieces": [{"name": "through the fairlead", "path": [list(hole + 0.15 * axis), list(hole),
                                                                               list(mouth)],
                                      "allow": [("DeckHardware", fg)]},
                                     {"name": "to the cleat", "path": [list(mouth), list(horn)],
                                      "allow": [("DeckHardware", cg)]}]})
            rep[f"{name}, {side}"] = {"cleat": [round(float(v), 3) for v in at], "cleat_deg": sd * pl["deg"],
                                      "fairlead_x": pl["fairlead"],
                                      "hole": [round(float(v), 3) for v in hole],
                                      "hole_skew_deg": round(abs(skew), 1),
                                      "lead_off_hole_axis_deg": round(off, 1),
                                      "lead_m": round(float(np.linalg.norm(horn - hole)), 2)}
    return rep, leads


def bow_chock(part, sh):
    """The anchor cable's chock on the bow (slice 9): an open bronze chock let into the toe rail's top, laid along it
    as a fairlead is, its throat a U across the rail as wide as a link stands (rounded at its floor and lips), the
    cable dropped in from above. Moored, the cable leads 'cable_out_deg' outboard of ahead to the anchor and aft from
    the chock to the chain pipe, both nearly fore and aft while the rail here runs aft and out at about 27 degrees: so
    the throat is bored along the anchor's lead, across the rail at a slant, the U kept a link wide square to that
    axis and the body long enough to carry it, its floor falling away at both mouths. Returns the report and the
    cable's leads for the room checks: through the throat to the chain pipe's mouth (bearing on the inboard mouth),
    lifted clear of the throat, and over the outboard mouth at each dip tested."""
    bc = HW["bow_chock"]
    sd = -1.0 if bc["side"] == "port" else 1.0
    x = bc["x"]
    p, t, up, out = sh.rail(x, sd)
    L, W, H = bc["length"], bc["width"], bc["height"]
    g, hb, let, rl, rc = bc["throat"], bc["floor"], bc["let_in"], bc["lip_r"], bc["corner_r"]
    cp = HW["chain_pipe"]
    c = np.asarray(cp["at"], float)
    mouth = np.array([c[0], c[1], deck_z(c[0], c[1]) + cp["height"]])
    r = bc["cable_r"]
    th = math.radians(bc["cable_out_deg"])
    to_anchor = np.array([math.cos(th), sd * math.sin(th), 0.0])
    # the throat is bored along the anchor's lead, so the cable riding to her runs fair through it; it turns aft to
    # the chain pipe at the inboard mouth, where it is slack (or under the windlass's pull)
    ax_h = to_anchor
    k = float(ax_h @ t) / float(ax_h @ out)                 # its run along the rail for each metre across it
    sc = math.hypot(1.0, k)                                 # a width square to the axis, measured along the rail
    if L < sc * (g + 2 * rl) + 2 * (rc + 0.01):
        raise ValueError(f"the bow chock is too short for its throat slanted {math.degrees(math.atan(k)):.0f} deg: "
                         f"it needs {sc * (g + 2 * rl) + 2 * (rc + 0.01):.3f} m along the rail")

    def arc(cu, cw, rad, a0, a1, n=6, s_u=1.0, mark=False):
        return [(cu + s_u * rad * math.cos(a), cw + rad * math.sin(a), mark)
                for a in np.radians(np.linspace(a0, a1, n))]

    # the section along the rail (u along it, w up from its top), counter-clockwise from the foot's after end; the
    # throat's U and lips stretched along u by sc, so square to the slanted axis they are round and a link wide (the
    # U's points marked: its floor falls away at the mouths)
    base = np.array([(-L / 2, -let, False), (L / 2, -let, False)] + arc(L / 2 - rc, H - rc, rc, 0, 90)
                    + arc(sc * (g / 2 + rl), H - rl, rl, 90, 180, s_u=sc)
                    + arc(0.0, hb + g / 2, g / 2, 0, -180, 13, s_u=sc, mark=True)
                    + arc(-sc * (g / 2 + rl), H - rl, rl, 0, 90, s_u=sc) + arc(-L / 2 + rc, H - rc, rc, 90, 180),
                    dtype=float)
    is_u = base[:, 2] > 0.5
    # the mouths: along the axis the U's floor rounds down on 'mouth_r' from level to the steepest dip tested (to the
    # chain pipe's lead inboard, 'mouth_in_deg'), then falls at that slope, square to the axis (so the cable bending
    # over it meets it the same right across), to 2 mm above the rail's top; the middle line's bend meets the face
    rm = bc["mouth_r"]
    A_face = sc * W / 2                                     # where the throat's middle line meets each face

    def fall(A, dmax):                                      # the floor's drop A along the axis past the bend's start
        if A <= 0.0:
            return 0.0
        a_arc = rm * math.sin(dmax)
        if A <= a_arc:
            return rm - math.sqrt(rm * rm - A * A)
        return rm * (1.0 - math.cos(dmax)) + (A - a_arc) * math.tan(dmax)
    d_out, d_in = math.radians(max(bc["dips_deg"] + bc["steep_dips_deg"])), math.radians(bc["mouth_in_deg"])
    A0_out, A0_in = A_face - rm * math.sin(d_out), A_face - rm * math.sin(d_in)

    flare = bc["mouth_flare"]

    def section(s_):
        Q = base[:, :2].copy()
        for i in np.where(is_u)[0]:
            A = s_ * sc + k * Q[i, 0] / sc                  # its distance along the axis from the middle
            dr = min(fall(A - A0_out, d_out) if A > 0 else fall(-A - A0_in, d_in), hb - 0.002)
            Q[i] = (Q[i, 0] * (1.0 + flare * dr / (g / 2)), Q[i, 1] - dr)   # widening as it falls ('mouth_flare')
        return Q
    to3 = lambda Q, s: p + Q[:, :1] * t + Q[:, 1:2] * up + s * (out + k * t)  # noqa: E731

    def bend(V):
        d = np.asarray(V, float) - p
        res = []
        for (u, v, w) in zip(d @ t, d @ out, d @ up):
            pu, _, upu, outu = sh.rail(x + u * t[0], sd)
            res.append(pu + v * outu + w * upu)
        return np.array(res)
    ss = np.linspace(-W / 2, W / 2, 23)
    V, F = deck.loft_section([to3(section(sv), sv) for sv in ss], section(ss[0]), section(ss[-1]))
    g_ = f"Bow chock, {bc['side']}"
    solid(part, bend(V), F, "Bronze", lab(g_, "bow chock"), CAT_CHOCK, BRZ)
    on = lambda A_, w_: bend([p + w_ * up + (A_ / sc) * (out + k * t)])[0]  # noqa: E731
    Cb = on(0.0, hb + r)
    inner = on(-A_face, hb + r)
    # past the inboard face the cable turns down and aft, bearing on the throat's inboard mouth: its first 'bears_m'
    # may touch the chock, the rest only the chain pipe
    bears = inner + bc["bears_m"] * unit(mouth - inner)
    leads = [{"name": "Anchor cable on deck", "group": "Anchor cable on deck", "object": "", "r": r, "rope": False,
              "step_m": 0.004,
              "pieces": [{"name": "through the chock", "path": [list(on(A_face, hb + r)), list(Cb), list(inner),
                                                                list(bears)],
                          "allow": [("DeckHardware", g_)]},
                         {"name": "to the chain pipe", "path": [list(bears), list(mouth)],
                          "allow": [("DeckHardware", "Chain pipe")]}]}]
    # the throat's room: the cable lifted 'lift' off the floor it lies on must clear everything (the U, its lips, the
    # rail) by the room check's margin; then the cable bending over the outboard mouth (lifted the same) and running
    # out 'out_m' toward the anchor at each of 'dips_deg' below the level
    lift = bc["lift"]
    lw = hb + r + lift
    throat = [list(on(-A_face, lw)), list(Cb + lift * up), list(on(A_face, lw))]
    leads.append({"name": "Anchor cable in the throat", "group": "Anchor cable in the throat", "object": "", "r": r,
                  "rope": False, "step_m": 0.004, "pieces": [{"name": "the throat", "allow": [], "path": throat}]})
    cen = on(A0_out, hb - rm)
    up_m = unit(on(A0_out, 1.0) - on(A0_out, 0.0))
    ax_m = unit(on(A_face, hb) - on(-A_face, hb))
    Rb = rm + r + lift
    for dip in bc["dips_deg"] + bc["steep_dips_deg"]:
        dq = math.radians(dip)
        D = unit(math.cos(dq) * to_anchor - math.sin(dq) * np.array([0.0, 0.0, 1.0]))
        th_end = dq + math.asin(max(-1.0, min(1.0, float(ax_m[2]))))     # the axis rises a little with the sheer
        bendp = [cen + Rb * (math.sin(a) * ax_m + math.cos(a) * up_m) for a in np.linspace(0.0, th_end, 9)]
        path = [Cb + lift * up] + bendp + [bendp[-1] + bc["out_m"] * D]
        leads.append({"name": f"Anchor cable, {dip:g} deg down", "group": f"Anchor cable, {dip:g} deg down",
                      "object": "", "r": r, "rope": False, "step_m": 0.004,
                      "report_only": dip in bc["steep_dips_deg"],
                      "pieces": [{"name": "over the mouth", "allow": [], "path": [list(q) for q in path]}]})
    lin = unit(mouth - Cb)
    off_in = math.degrees(math.acos(min(1.0, abs(float(unit(lin * np.array([1.0, 1.0, 0.0])) @ ax_h)))))
    off_in3 = math.degrees(math.acos(min(1.0, abs(float(lin @ ax_m)))))
    off_out = math.degrees(math.acos(min(1.0, float(to_anchor @ ax_h))))
    return ({"x": x, "side": bc["side"], "throat": [round(float(v), 3) for v in Cb],
             "throat_skew_deg": round(abs(math.degrees(math.atan(k))), 1), "length_m": L,
             "throat_along_rail_m": round(sc * g, 3), "cable_out_deg": bc["cable_out_deg"],
             "turn_at_inboard_mouth_deg": {"in_plan": round(off_in, 1), "in_all": round(off_in3, 1),
                                           "down": round(math.degrees(math.asin(-float(lin[2]))), 1)},
             "turn_at_outboard_mouth_deg": {"in_plan": round(off_out, 1)}, "mouth_r_m": rm,
             "dips_tested_deg": bc["dips_deg"], "steep_dips_reported_deg": bc["steep_dips_deg"],
             "lift_in_tests_m": lift,
             "lead_to_chain_pipe_m": round(float(np.linalg.norm(mouth - Cb)), 2)}, leads)


# ------------------------------------------------------------------------------------------------ cowls, deck prisms
def cowl_flange(part, at, group, bored=False):
    """A cowl's bronze deck flange (always on deck): a ring let into the deck round the pipe's hole. Weighed as the
    ring (less its bore). `bored` (slice 9, where the deck is opened under it): drawn with its bore open, carried down
    through the deck as a collar and finished under the deckhead by a backing ring; weighed the same."""
    cw = HW["cowls"]
    c = np.asarray(at, float)
    z0 = deck_z(c[0], c[1])
    fr, pr = cw["flange_r"], cw["pipe_r"]
    n = 40
    ang = 2 * math.pi * np.arange(n) / n
    ring = lambda r: np.column_stack([c[0] + r * np.cos(ang), c[1] + r * np.sin(ang)])  # noqa: E731
    R0 = ring(fr)
    rings = [np.column_stack([R0, shell.deck_z(R0[:, 0], R0[:, 1]) - deck.LET]),
             np.column_stack([R0, np.full(n, z0 + 0.007)]),
             np.column_stack([ring(fr - 0.01), np.full(n, z0 + 0.013)]),
             np.column_stack([ring(pr + 0.012), np.full(n, z0 + 0.02)])]
    V, F = deck.loft_rings(rings)
    if bored:
        rb = pr - 0.004
        under = deck.PL["thickness"]
        dz = lambda r, h: np.column_stack([ring(r), shell.deck_z(*ring(r).T) + h])  # noqa: E731
        # the collar fills the deck's hole (its radius pr + 6 mm) and the flange keeps its flat foot outside it
        rc = pr + 0.007
        Vb, Fb = deck.loft_rings(rings + [np.column_stack([ring(rb), np.full(n, z0 + 0.02)]),
                                          dz(rb, -under - 0.06), dz(rc, -under - 0.06),
                                          dz(rc, -under - 0.004), dz(fr - 0.01, -under - 0.004),
                                          dz(fr - 0.01, -under), dz(rc, -under), dz(rc, -deck.LET)], closed=True)
        part.add(Vb, Fb, "Bronze", None, lab(group, "cowl"))
        part.weigh(V, F, ("solid", BRZ), CAT_COWL)
    else:
        solid(part, V, F, "Bronze", lab(group, "cowl"), CAT_COWL, BRZ)
    bore = math.pi * (pr - 0.004) ** 2 * (0.02 + deck.LET)
    part.masses[-1]["kg"] = round(part.masses[-1]["kg"] - BRZ * bore, 1)
    part.masses[-1]["how"] = "solid less its bore"
    return z0


def cowl_cap(part, at, group):
    """The screw cap on a cowl's flange while the cowl is struck (at sea)."""
    cw = HW["cowls"]
    c = np.asarray(at, float)
    z0 = deck_z(c[0], c[1])
    rc = cw["pipe_r"] + 0.016
    prof = [(0.0, 0.018), (rc, 0.018), (rc, 0.026), (rc - 0.004, 0.031)]
    for k in range(1, 6):
        q = math.pi / 2 * k / 5
        prof.append(((rc - 0.004) * math.cos(q), 0.031 + 0.008 * math.sin(q)))
    V, F = deck.revolve(prof, np.array([c[0], c[1], z0]), UP, X, 40)
    solid(part, V, F, "Bronze", lab(group, "cowl cap"), CAT_COWL, BRZ)


def cowl(part, at, deg, group):
    """A cowl vent standing in its flange at plan point `at` (in harbour), its mouth facing `deg` from forward."""
    cw = HW["cowls"]
    c = np.asarray(at, float)
    z0 = deck_z(c[0], c[1])
    o = np.array([c[0], c[1], z0])
    m = plan_dir(deg)
    pr, rise, br = cw["pipe_r"], cw["rise"], cw["bend_r"]
    # the pipe up and round its bend to level
    path = [o + 0.01 * UP, o + rise * UP]
    for k in range(1, 10):
        q = math.pi / 2 * k / 9
        path.append(o + (rise + br * math.sin(q)) * UP + br * (1 - math.cos(q)) * m)
    V, F = deck.tube(path, pr, 32)
    cast(part, V, F, "Bronze", lab(group, "cowl"), CAT_COWL)
    # the bell: a wall `wall` thick flaring from the pipe to the mouth, rolled at the lip; red inside
    end = path[-1]
    Lb, mr, wl = cw["bell_length"], cw["mouth_r"], 0.006
    hs = np.linspace(-0.03, Lb, 12)
    ro = [pr + 0.003 + (mr - pr - 0.003) * max(h, 0.0) ** 1.8 / Lb ** 1.8 for h in hs]
    outer = [(r, h) for r, h in zip(ro, hs)]
    lip = [(mr + 0.004, Lb + 0.003), (mr + 0.001, Lb + 0.008), (mr - wl + 0.001, Lb + 0.006)]
    inner = [(r - wl, h) for r, h in zip(ro[::-1], hs[::-1])]
    prof = outer + lip + inner
    nseg = len(prof)
    V, F = deck.revolve(prof, end, m, UP, 40, ring=True)
    slots = []
    for i in range(40):
        for k in range(nseg):
            slots.append("CowlRed" if len(outer) + len(lip) - 1 <= k < nseg - 1 else "Bronze")
    if deck.signed_volume(np.asarray(V), F) < 0:
        F = [tuple(f[::-1]) for f in F]
    part.add(V, F, slots, None, lab(group, "cowl"))
    part.weigh(V, F, ("solid", BRZ), CAT_COWL)
    # the throat: dark, a little inside the bell
    V, F = deck.revolve([(0.0, 0.0), (pr - wl - 0.002, 0.0), (pr - wl - 0.002, 0.004), (0.0, 0.004)],
                        end + 0.004 * m, m, UP, 24)
    solid(part, V, F, "Black", lab(group, "cowl"), CAT_COWL, None)
    top = end + (mr + 0.004) * UP
    return {"at": [round(float(v), 3) for v in c], "mouth_deg": deg,
            "top_above_deck_m": round(float(top[2] - z0), 3)}


def deck_prism(part, at, group):
    """A deck prism let into the planking: its flat top flush with the deck (a hair proud), its pendant a ridge below
    the deck's underside that spreads the daylight in the cabin."""
    dp = HW["deck_prisms"]
    c = np.asarray(at, float)
    L, W = dp["top"]
    under = deck.DK["deck"]["planking"]["thickness"]
    top = rounded_rect(L / 2, W / 2, 0.006, 2)
    ridge = rounded_rect(0.36 * L, 0.004, 0.002, 2)

    def ring(P2, dz):
        """The outline P2 `dz` above the deck under each of its points (the top follows the deck's camber and sheer,
        flush all round)."""
        x, y = c[0] + P2[:, 0], c[1] + P2[:, 1]
        return np.column_stack([x, y, shell.deck_z(x, y) + dz])
    V, F = deck.loft_rings([ring(ridge, -dp["pendant"]), ring(top, -under), ring(top, dp["proud"])])
    solid(part, V, F, "DeckGlass", lab(group, "deck prism"), CAT_PRISM, MT["glass"])


# ------------------------------------------------------------------------------------------------ the anchor
def anchor(part):
    """The fisherman's anchor flat on its chocks, stock folded along the shank, lashed. Returns its report."""
    an = HW["anchor"]
    g = "Anchor"
    cr = np.asarray(an["crown"], float)
    Ls = an["shank_length"]
    # she lies in the deck's own plane under her (the deck climbs 13 cm along the shank with the sheer): fit it
    S0 = plan_dir(an["deg"])
    L0 = np.cross(UP, S0)
    gu, gv = np.meshgrid(np.linspace(-0.1, Ls + 0.1, 9), np.linspace(-0.5, 0.5, 7))
    P2 = cr + gu.reshape(-1, 1) * S0[:2] + gv.reshape(-1, 1) * L0[:2]
    zs = shell.deck_z(P2[:, 0], P2[:, 1])
    (a0, bx, by), *_ = np.linalg.lstsq(np.column_stack([np.ones(len(P2)), P2]), zs, rcond=None)
    N = unit(np.array([-bx, -by, 1.0]))                    # the deck plane's normal: "up" for the anchor
    S = unit(S0 + (bx * S0[0] + by * S0[1]) * UP)          # along the shank, in that plane
    Lt = np.cross(N, S)                                    # to starboard of the shank (its left seen from above)
    Oc = np.array([cr[0], cr[1], a0 + bx * cr[0] + by * cr[1]]) + an["lie_height"] * N
    (w0, d0), (w1, d1) = an["shank_section"]
    iron = MT["iron"]
    iron_pts = []

    def piece(V, F):
        iron_pts.append(np.asarray(V, float))
        solid(part, V, F, "Galvanised", lab(g, "anchor"), CAT_ANCHOR, iron)

    def depth(s):
        f = min(max(s / Ls, 0.0), 1.0)
        return d0 + (d1 - d0) * f, w0 + (w1 - w0) * f
    # the shank, from inside the crown to its eye, tapering
    ss = np.linspace(-0.02, Ls + 0.01, 16)
    path = [Oc + s * S for s in ss]
    secs = []
    for s in ss:
        f = min(max(s / Ls, 0.0), 1.0)
        secs.append(rounded_rect((w0 + (w1 - w0) * f) / 2, (d0 + (d1 - d0) * f) / 2, 0.01, 3))
    V, F = deck.loft_rings(section_rings(path, [(Lt, N)] * len(ss), secs))
    piece(V, F)
    # the eye's boss at the shank's head (its hole athwartships; the ring passes through it)
    V, F = deck.revolve([(0.0, -w1 / 2 - 0.004), (0.036, -w1 / 2 - 0.004), (0.04, -w1 / 2 + 0.002),
                         (0.04, w1 / 2 - 0.002), (0.036, w1 / 2 + 0.004), (0.0, w1 / 2 + 0.004)],
                        Oc + (Ls - 0.01) * S, Lt, S, 24)
    piece(V, F)
    # the crown's boss
    V, F = deck.revolve([(0.0, -0.034), (0.04, -0.03), (0.058, -0.012), (0.058, 0.012), (0.04, 0.03), (0.0, 0.034)],
                        Oc + 0.01 * S, N, S, 24)
    piece(V, F)
    # the arms: one bar on a circle from one bill through the crown to the other, tapering to the bills
    Rc, qm = an["arm_radius"], math.radians(an["arm_deg"])
    (aw0, ad0), (aw1, ad1) = an["arm_section"]
    qs = list(np.linspace(-qm - 0.09, qm + 0.09, 41))
    path, frames, secs = [], [], []
    for q in qs:
        path.append(Oc + Rc * math.sin(q) * Lt + Rc * (1 - math.cos(q)) * S)
        tg = unit(math.cos(q) * Lt + math.sin(q) * S)
        frames.append((np.cross(N, tg), N))
        f = min(abs(q) / qm, 1.0)
        k = 1.0 if abs(q) <= qm else max(0.25, 1.0 - (abs(q) - qm) / 0.09 * 0.75)
        secs.append(rounded_rect(k * (aw0 + (aw1 - aw0) * f) / 2, k * (ad0 + (ad1 - ad0) * f) / 2, 0.008, 3))
    V, F = deck.loft_rings(section_rings(path, frames, secs))
    piece(V, F)
    # the palms: spade-shaped plates on the arms near the bills, standing across the arms (the arms lie flat)
    pl, pw, pt = an["palm"]
    bills = []
    for sg in (1, -1):
        q = sg * (qm - 0.45 * pl / Rc)
        P = Oc + Rc * math.sin(q) * Lt + Rc * (1 - math.cos(q)) * S
        tg = unit(math.cos(q) * Lt + math.sin(q) * S) * sg
        poly = np.array([(-0.55 * pl, 0.0), (-0.12 * pl, 0.5 * pw), (0.3 * pl, 0.3 * pw), (0.5 * pl, 0.0),
                         (0.3 * pl, -0.3 * pw), (-0.12 * pl, -0.5 * pw)])
        nrm = np.cross(N, tg)
        V, F = deck.slab(poly, P, tg, N, nrm, -pt / 2, pt / 2)
        piece(V, F)
        bills.append(P + 0.5 * pl * tg)
    # the stock, folded down beside the shank from the bolt it pivots on at the shank's head, resting on the forward
    # chock's saddle (bedded in it as the shank is), and the bolt
    sl, sr, sb = an["stock"]
    so = an["stock_off"]
    s0 = Ls - 0.06 - sl
    fwd = max(an["chocks"], key=lambda c: c[0])
    ns = -depth(fwd[0])[0] / 2 + sr                         # the stock's line, along N from the shank's
    P0, P1 = Oc + s0 * S - so * Lt + ns * N, Oc + (Ls - 0.06) * S - so * Lt + ns * N
    V, F = deck.revolve([(0.0, -sb), (0.6 * sb, -0.8 * sb), (sb, -0.25 * sb), (sb, 0.2 * sb), (sr, sb * 0.9),
                         (sr, sl - sb * 0.9), (sb, sl - 0.2 * sb), (sb, sl + 0.25 * sb), (0.6 * sb, sl + 0.8 * sb),
                         (0.0, sl + sb)], P0, S, N, 20)
    piece(V, F)
    V, F = deck.revolve([(0.0, -0.004), (0.011, -0.004), (0.011, so + 0.004), (0.0, so + 0.004)],
                        P1 - 0.04 * S - ns * N, Lt, S, 12)
    piece(V, F)
    # the ring, flat, through the eye
    rr, rb = an["ring"]
    rp = rigging.ring_path(Oc + (Ls - 0.01 + rr) * S, N, S, rr, 28)
    rings, _ = rigging.tube_rings(rp, rb, 12, closed=True)
    V, F = deck.loft_rings(rings, closed=True)
    piece(V, F)
    # the chocks under the shank and the stock (set over toward the stock), and a lashing over both at each, rove
    # through a hole in the chock under them
    lash = []
    for s, cl, cwid, off, ls in an["chocks"]:
        dep, wid = depth(s)
        top = -dep / 2 + 0.002                             # the chock's top, along N from the shank's line
        C = Oc + s * S + off * Lt
        base = rounded_rect(cl / 2, cwid / 2, 0.02, 3)
        Pt = np.array([C + u * S + v * Lt + (top - 0.01) * N for u, v in base])
        rings = [np.column_stack([Pt[:, :2], shell.deck_z(Pt[:, 0], Pt[:, 1]) - deck.LET]), Pt]
        inner = rounded_rect(cl / 2 - 0.01, cwid / 2 - 0.01, 0.012, 3)
        rings.append(np.array([C + u * S + v * Lt + top * N for u, v in inner]))
        V, F = deck.loft_rings(rings)
        solid(part, V, F, "Wood", lab(g, "chock"), CAT_ANCHOR, MT["teak"])
        # the lashing at s = ls: up the shank's starboard side, round its corner (concentric with the section's
        # 10 mm rounding), across its top and the stock's, down round the stock to the chock, and back through it
        dl, wl = depth(ls)
        r = an["lashing_d"] / 2
        g0 = r + 0.001
        Cl = Oc + ls * S
        zb = top - 0.04
        P = [(wl / 2 + g0, zb), (wl / 2 + g0, dl / 2 - 0.01)]
        for k in range(1, 7):
            q = math.pi / 2 * k / 6
            P.append((wl / 2 - 0.01 + (0.01 + g0) * math.cos(q), dl / 2 - 0.01 + (0.01 + g0) * math.sin(q)))
        for k in range(0, 13):
            q = math.pi / 2 + math.pi / 2 * k / 12
            P.append((-so + (sr + g0) * math.cos(q), ns + (sr + g0) * math.sin(q)))
        P.append((-so - sr - g0, zb))
        lp = np.array([Cl + v * Lt + n * N for v, n in P])
        rigging.loop(part, lp, r, lab(g, "lashing"), CAT_ANCHOR, rigging.MANILA * math.pi * r * r)
        lash.append(round(float(ls), 3))
    pts = np.concatenate(iron_pts)
    lowest = float((pts[:, 2] - shell.deck_z(pts[:, 0], pts[:, 1])).min())
    return {"crown": [round(float(v), 3) for v in cr], "shank_m": Ls, "arms_span_m": round(2 * Rc * math.sin(qm), 3),
            "shank_centre_above_deck_m": an["lie_height"], "lowest_iron_above_deck_m": round(lowest, 4),
            "lashings_at_s_m": lash, "bills": [[round(float(v), 3) for v in b] for b in bills]}


def chain_pipe(part, bored=False):
    """The chain pipe's casting and its cap. `bored` (slice 9, where the deck is opened under it): the neck drawn
    hollow down through the deck (the forepeak's spurling pipe carries on from its foot), weighed the same."""
    cp = HW["chain_pipe"]
    c = np.asarray(cp["at"], float)
    z0 = deck_z(c[0], c[1])
    fr, nr, h = cp["flange_r"], cp["neck_r"], cp["height"]
    prof = [(0.0, -0.012), (fr, -0.012), (fr, 0.005), (fr - 0.01, 0.011), (nr, 0.016), (nr, h - 0.022)]
    for k in range(1, 7):
        q = math.pi / 2 * k / 6
        prof.append((nr * math.cos(q) + 0.004, h - 0.022 + 0.022 * math.sin(q)))
    prof.append((0.0, h))
    V, F = deck.revolve(prof, np.array([c[0], c[1], z0]), UP, X, 40)
    if bored:
        # the neck's collar fills the deck's hole (its radius neck_r + 2 mm) down to a backing flange under the
        # deckhead, which follows the deck's sheer and camber; the casting's let-in foot stays as it was
        rb, under, n = nr - 0.008, deck.PL["thickness"], 40
        ang = 2 * math.pi * np.arange(n) / n
        ring = lambda r: np.column_stack([c[0] + r * np.cos(ang), c[1] + r * np.sin(ang)])  # noqa: E731
        flat = lambda r, dh: np.column_stack([ring(r), np.full(n, z0 + dh)])  # noqa: E731
        dz = lambda r, dh: np.column_stack([ring(r), shell.deck_z(*ring(r).T) + dh])  # noqa: E731
        rc = nr + 0.003
        Vb, Fb = deck.loft_rings([flat(rb, h - 0.024), dz(rb, -under - 0.012), dz(fr, -under - 0.012), dz(fr, -under),
                                  dz(rc, -under), flat(rc, -0.012), flat(fr, -0.012), flat(fr, 0.005),
                                  flat(fr - 0.01, 0.011), flat(nr, 0.016), flat(nr, h - 0.024)], closed=True)
        part.add(Vb, Fb, "Bronze", None, lab("Chain pipe", "chain pipe"))
        cap = [(0.0, h - 0.026), (nr + 0.004, h - 0.026), (nr + 0.004, h - 0.022)]
        cap += [(nr * math.cos(math.pi / 2 * k / 6) + 0.004, h - 0.022 + 0.022 * math.sin(math.pi / 2 * k / 6))
                for k in range(1, 7)] + [(0.0, h)]
        Vc, Fc = deck.revolve(cap, np.array([c[0], c[1], z0]), UP, X, 40)
        part.add(Vc, Fc, "Bronze", None, lab("Chain pipe", "chain pipe"))
        part.weigh(V, F, ("solid", BRZ), CAT_PIPE)
    else:
        solid(part, V, F, "Bronze", lab("Chain pipe", "chain pipe"), CAT_PIPE, BRZ)
    # weighed as the casting it is: the neck's bore (the chain's way below, 8 mm in from its outside) is empty
    bore = math.pi * (nr - 0.008) ** 2 * (h - 0.022 + 0.012)
    part.masses[-1]["kg"] = round(part.masses[-1]["kg"] - BRZ * bore, 1)
    part.masses[-1]["how"] = "solid less its bore"
    return {"at": [round(float(v), 3) for v in c]}


# ------------------------------------------------------------------------------------------------ lights
def lantern(part, c, z, a0, a1, lens_slot, group):
    """A bronze lantern with its lamp at (c, z): the body, its hood and vent, and the lens over plan angles a0 to a1
    (degrees from forward, to starboard positive). Returns the lamp's point."""
    R, H = HW["sidelights"]["lantern"]
    lh = HW["sidelights"]["lens_h"]
    o = np.array([c[0], c[1], z])
    zb = -0.55 * H
    prof = [(0.0, zb), (R + 0.004, zb), (R + 0.004, zb + 0.012), (R, zb + 0.016), (R, zb + H), (R + 0.008, zb + H),
            (R + 0.008, zb + H + 0.008), (0.62 * R, zb + H + 0.035), (0.3 * R, zb + H + 0.045),
            (0.3 * R, zb + H + 0.07), (0.38 * R, zb + H + 0.074), (0.0, zb + H + 0.08)]
    V, F = deck.revolve(prof, o, UP, X, 40)
    cast(part, V, F, "Bronze", lab(group, "lantern"), CAT_NAV, 0.003)
    # the lens: a band of glass over its arc, a little proud of the body
    qs = np.radians(np.linspace(a0, a1, max(8, int(abs(a1 - a0) / 4) + 1)))
    sec = [(R - 0.004, -lh / 2), (R + 0.003, -lh / 2), (R + 0.003, lh / 2), (R - 0.004, lh / 2)]
    rings = [np.array([o + r * (math.cos(q) * X + math.sin(q) * Y) + h * UP for r, h in sec]) for q in qs]
    V, F = deck.loft_rings(rings)
    solid(part, V, F, lens_slot, lab(group, "lens"), CAT_NAV, MT["glass"])
    return o


def sidelights(part, sh):
    """The side lights on their boards. Returns each lamp's point and arc, and its board's screening across the bow."""
    sl = HW["sidelights"]
    x = sl["at_x"]
    bl, bh, bt = sl["board"]
    out = {}
    for sd, side in SIDES:
        g = f"Side light, {side}"
        y = sd * (sh.half(x) - sl["from_sheer"])
        z0 = deck_z(x, y)
        R = sl["lantern"][0]
        arc = (0.0, sd * sl["arc_deg"])
        lamp = lantern(part, (x, y), z0 + sl["lamp_up"], min(arc), max(arc),
                       "LensGreen" if sd > 0 else "LensRed", g)
        # the board: from just abaft the lantern forward, its outboard face board_in inboard of the lamp
        yf = y - sd * sl["board_in"]
        xa = x - R - 0.02
        poly = rounded_rect(bl / 2, bh / 2, 0.02, 3) + np.array([xa + bl / 2, 0.0])
        zb = z0 + sl["board_bottom"] + bh / 2
        V, F = deck.slab(poly - np.array([0.0, 0.0]), np.array([0.0, yf, zb]), X, UP, Y, -sd * bt if sd > 0 else 0.0,
                         0.0 if sd > 0 else bt)
        solid(part, V, F, "Wood", lab(g, "light board"), CAT_NAV, MT["teak"])
        # two bronze brackets: a foot on the deck and a strap up the board's inboard face
        yi = yf - sd * bt
        for xb in (xa + 0.12, xa + bl - 0.12):
            zd = deck_z(xb, yi - sd * 0.03)
            foot = rounded_rect(0.03, 0.035, 0.008, 2)
            V, F = deck.slab(foot, np.array([xb, yi - sd * 0.035, zd]), X, Y, UP, -0.004, 0.006)
            solid(part, V, F, "Bronze", lab(g, "bracket"), CAT_NAV, BRZ)
            strap = np.array([(-0.018, zd - 0.002), (0.018, zd - 0.002), (0.018, zb + 0.06), (-0.018, zb + 0.06)])
            V, F = deck.slab(strap - np.array([0.0, 0.0]), np.array([xb, yi, 0.0]), X, UP, Y,
                             -0.006 if sd > 0 else 0.0, 0.0 if sd > 0 else 0.006)
            solid(part, V, F, "Bronze", lab(g, "bracket"), CAT_NAV, BRZ)
        # the lantern's back plate, from its body to the board's face
        H = sl["lantern"][1]
        plate = rounded_rect(0.03, 0.4 * H, 0.008, 2)
        V, F = deck.slab(plate, np.array([x, yf, lamp[2] - 0.05 * H]), X, UP, Y,
                         0.0 if sd > 0 else -(sl["board_in"] - R + 0.004),
                         sl["board_in"] - R + 0.004 if sd > 0 else 0.0)
        solid(part, V, F, "Bronze", lab(g, "bracket"), CAT_NAV, BRZ)
        out[side] = {"lamp": [round(float(v), 3) for v in lamp], "arc_deg": [0.0, sd * sl["arc_deg"]],
                     "lamp_above_deck_m": sl["lamp_up"], "board_forward_of_lamp_m": round(xa + bl - x, 3),
                     "_lamp": lamp, "_arc": arc, "_side": sd, "group": g}
    return out


def stern_light(part):
    st = HW["stern_light"]
    g = "Stern light"
    c = np.asarray(st["at"], float)
    z0 = deck_z(c[0], c[1])
    pr, fr = st["post"]
    R, H = HW["sidelights"]["lantern"]
    zl = z0 + st["lamp_up"]
    V, F = deck.revolve([(0.0, -0.01), (fr, -0.01), (fr, 0.005), (fr - 0.008, 0.01), (pr + 0.006, 0.016),
                         (pr, 0.03), (pr, zl - z0 - 0.5 * H), (0.0, zl - z0 - 0.5 * H)],
                        np.array([c[0], c[1], z0]), UP, X, 24)
    solid(part, V, F, "Bronze", lab(g, "standard"), CAT_NAV, BRZ)
    half = st["arc_deg"] / 2
    lamp = lantern(part, c, zl, 180.0 - half, 180.0 + half, "LensClear", g)
    return {"lamp": [round(float(v), 3) for v in lamp], "arc_deg": [180.0 - half, 180.0 + half],
            "lamp_above_deck_m": st["lamp_up"], "_lamp": lamp, "_arc": (180.0 - half, 180.0 + half), "_side": 0,
            "group": g}


# ------------------------------------------------------------------------------------------------ flags
def sheet_solid(Pf, Pb):
    """A closed thin solid between two grids of points (nu, nv, 3) (a flag's two faces): the faces, and the edges
    closed by strips."""
    nu, nv, _ = Pf.shape
    V = np.concatenate([Pf.reshape(-1, 3), Pb.reshape(-1, 3)])
    off = nu * nv

    def vi(i, j, b):
        return b * off + i * nv + j
    F = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            F.append((vi(i, j, 0), vi(i + 1, j, 0), vi(i + 1, j + 1, 0), vi(i, j + 1, 0)))
            F.append((vi(i, j, 1), vi(i, j + 1, 1), vi(i + 1, j + 1, 1), vi(i + 1, j, 1)))
    edge = ([(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)]
            + [(i, nv - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nv - 2, 0, -1)])
    for k in range(len(edge)):
        a, b = edge[k], edge[(k + 1) % len(edge)]
        F.append((vi(*a, 0), vi(*a, 1), vi(*b, 1), vi(*b, 0)))
    return V, F


def flag(part, top, down, fly_dir, fly, hoist, taper, wave, droop, slot, label, cat, ny=12, nx=28):
    """A flag hung from its hoist (from `top` down `down` for `hoist` m) streaming along the level `fly_dir`: its fly
    `fly` m, narrowing to `taper` of its hoist at the fly's end (a burgee's point), waving across itself (amplitude
    growing to wave[0] at the fly, wavelength wave[1]) and drooping `droop` m at the fly. Its faces' UVs ('Spar') are
    (x along the fly, y down from the hoist's top) in metres; for a burgee (taper < 1) y is from the middle."""
    down, fly_dir = unit(down), unit(fly_dir)
    nrm = unit(np.cross(fly_dir, down))
    th = HW["flag_thickness"]
    us = np.linspace(0.0, 1.0, nx + 1)
    vs = np.linspace(0.0, 1.0, ny + 1)
    P, uv = np.zeros((len(us), len(vs), 3)), np.zeros((len(us), len(vs), 2))
    for i, u in enumerate(us):
        k = 1.0 - (1.0 - taper) * u
        for j, v in enumerate(vs):
            vv = 0.5 + (v - 0.5) * k if taper < 1 else v
            d = u * fly
            P[i, j] = (top + vv * hoist * down + d * fly_dir
                       + wave[0] * u * math.sin(2 * math.pi * d / wave[1] + 0.8 * vv) * nrm - droop * u * u * UP)
            uv[i, j] = (d, (vv - 0.5) * hoist if taper < 1 else vv * hoist)
    # each face's normal: the grid's own (so the cloth's thickness stays square to it)
    du = np.gradient(P, axis=0)
    dv = np.gradient(P, axis=1)
    n = np.cross(du, dv)
    n /= np.linalg.norm(n, axis=2)[..., None]
    V, F = sheet_solid(P + 0.5 * th * n, P - 0.5 * th * n)
    U = np.concatenate([uv.reshape(-1, 2), uv.reshape(-1, 2)])
    if deck.signed_volume(V, F) < 0:
        F = [tuple(f[::-1]) for f in F]
    part.add(V, F, slot, None, label, uv={"Spar": U, "SparG": np.tile(spars.PLAIN, (len(V), 1))})
    area = fly * hoist * (1.0 + taper) / 2
    part.masses.append({"part": cat, "kg": round(MT["bunting_kg_m2"] * area, 2),
                        "centre": [round(float(v), 3) for v in P.reshape(-1, 3).mean(0)], "how": "area"})
    return P


def ensign_socket(part):
    en = HW["ensign"]
    c = np.asarray(en["at"], float)
    z0 = deck_z(c[0], c[1])
    ax = unit(np.array([-math.sin(math.radians(en["rake_deg"])), 0.0, math.cos(math.radians(en["rake_deg"]))]))
    sr, fr, h = en["socket"]
    # the flange flat on the deck, the barrel raked with the staff
    V, F = deck.revolve([(0.0, -0.01), (fr, -0.01), (fr, 0.005), (fr - 0.008, 0.01), (sr + 0.012, 0.016),
                         (0.0, 0.016)], np.array([c[0], c[1], z0]), UP, X, 28)
    solid(part, V, F, "Bronze", lab("Ensign staff", "socket"), CAT_ENSIGN, BRZ)
    V, F = deck.revolve([(0.0, 0.0), (sr + 0.004, 0.0), (sr + 0.004, 0.012), (sr, 0.026), (sr, h), (0.0, h)],
                        np.array([c[0], c[1], z0]), ax, X, 28)
    solid(part, V, F, "Bronze", lab("Ensign staff", "socket"), CAT_ENSIGN, BRZ)
    return np.array([c[0], c[1], z0]), ax


def ensign(part, foot, ax):
    """The staff in its socket and the ensign streaming aft from it (head to wind, in harbour)."""
    en = HW["ensign"]
    L, r0, r1 = en["staff"]
    V, F = deck.revolve([(0.0, 0.0), (r0, 0.0), (r1, L), (0.0, L)], foot + 0.014 * ax, ax, X, 16)
    solid(part, V, F, "Wood", lab("Ensign staff", "staff"), CAT_ENSIGN, MT["spruce"])
    tr = en["truck_r"]
    head = foot + (L + 0.014 + 0.8 * tr) * ax
    prof = [(tr * math.sin(q), -tr * math.cos(q)) for q in np.linspace(0.0, math.pi, 10)]
    V, F = deck.revolve(prof, head, ax, X, 16)
    solid(part, V, F, "Gilt", lab("Ensign staff", "staff"), CAT_ENSIGN, BRZ)
    # the hoist along the staff, clear of it by 2 mm square to its axis where it is thickest (the hoist's foot)
    sb = L - en["below_truck"] - en["hoist"]
    aft = unit(-X - float((-X) @ ax) * ax)
    top = foot + (L + 0.014 - en["below_truck"]) * ax + (r0 + (r1 - r0) * sb / L + 0.002) * aft
    P = flag(part, top, -ax, -X, en["fly"], en["hoist"], 1.0, en["wave"], en["droop"], "Ensign",
             lab("Ensign staff", "ensign"), CAT_ENSIGN)
    return {"staff_head": [round(float(v), 3) for v in head], "fly_m": en["fly"], "hoist_m": en["hoist"],
            "lowest_above_deck_m": round(float((P[..., 2] - shell.deck_z(P[..., 0], P[..., 1])).min()), 3),
            "aftmost_x": round(float(P[..., 0].min()), 3)}


def burgee(part, pts, deg):
    """The burgee's stick on the truck and the burgee streaming toward `deg` (from forward, to starboard positive)."""
    bg = HW["burgee"]
    A = spars.A
    T = np.asarray(pts["truck_top"], float)
    L, r0, r1 = bg["stick"]
    V, F = deck.revolve([(0.0, -0.03), (r0, -0.03), (r1, L), (0.0, L)], T, A, X, 12)
    solid(part, V, F, "Wood", lab("Burgee", "stick"), CAT_BURGEE, MT["spruce"])
    sl, sr = bg["spindle"]
    V, F = deck.revolve([(0.0, -0.02), (sr, -0.02), (sr, sl), (2 * sr, sl + 0.004), (2 * sr, sl + 0.012),
                         (0.0, sl + 0.016)], T + L * A, A, X, 12)
    solid(part, V, F, "Bronze", lab("Burgee", "spindle"), CAT_BURGEE, BRZ)
    d = plan_dir(deg)
    top = T + (L + sl - 0.01) * A + 0.004 * d
    flag(part, top, -A, d, bg["fly"], bg["hoist"], 0.04, bg["wave"], bg["droop"], "Burgee", lab("Burgee", "burgee"),
         CAT_BURGEE, ny=8, nx=20)
    return {"flies_deg": deg, "top": [round(float(v), 3) for v in top]}


# ------------------------------------------------------------------------------------------------ the whole
def deck_holes(opened):
    """The deck's holes under the fittings that pass through it (slice 9): {name: plan outline}. `opened` is the
    interior's openings: the deck prisms by their index, the cowls by their place, and the chain pipe. Each hole lies
    inside its fitting's solid (a prism's top less 2 mm, a bore plus 10 mm), so its edge never shows."""
    out = {}
    dp = HW["deck_prisms"]
    for k in opened.get("prisms", []):
        at = dp["at"][k]
        for sd, side in SIDES:
            P = rounded_rect(dp["top"][0] / 2 - 0.002, dp["top"][1] / 2 - 0.002, 0.004, 2)
            out[f"Deck prism {k + 1}, {side}"] = P + np.array([at[0], sd * at[1]])
    ang = 2 * math.pi * np.arange(24) / 24
    circle = np.column_stack([np.cos(ang), np.sin(ang)])
    for name in opened.get("cowls", []):
        at = HW["cowls"]["places"][name]["at"]
        for sd, side in SIDES:
            out[f"{name} cowl, {side}"] = np.array([at[0], sd * at[1]]) + (HW["cowls"]["pipe_r"] + 0.006) * circle
    if opened.get("chain_pipe"):
        out["Chain pipe"] = np.asarray(HW["chain_pipe"]["at"], float) + (HW["chain_pipe"]["neck_r"] + 0.002) * circle
    return out


def build(sheer, pts, opened=None):
    """{object name: SparPart} and the report. `opened`: the interior's openings (deck_holes), whose fittings are
    drawn bored through the deck."""
    opened = opened or {}
    sh = Sheer(sheer)
    hw = SparPart("DeckHardware")
    rep = {"stem_head": stem_head(hw, sh)}
    rep["mooring"], rep["mooring_leads"] = mooring(hw, sh)
    cowls = [(f"{name} cowl, {side}", (pl["at"][0], sd * pl["at"][1]), pl["deg"], name in opened.get("cowls", []))
             for name, pl in HW["cowls"]["places"].items() for sd, side in SIDES]
    for g, at, deg, bored in cowls:
        cowl_flange(hw, at, g, bored)
    rep["deck_prisms"] = []
    for k, at in enumerate(HW["deck_prisms"]["at"]):
        for sd, side in SIDES:
            deck_prism(hw, (at[0], sd * at[1]), f"Deck prism {k + 1}, {side}")
            rep["deck_prisms"].append([at[0], sd * at[1]])
    rep["anchor"] = anchor(hw)
    rep["chain_pipe"] = chain_pipe(hw, bool(opened.get("chain_pipe")))
    if opened.get("chain_pipe"):
        rep["bow_chock"], rep["cable_leads"] = bow_chock(hw, sh)
    rep["through_deck"] = sorted([g for g, _, _, bored in cowls if bored] +
                                 (["Chain pipe"] if opened.get("chain_pipe") else []))
    rep["lights"] = sidelights(hw, sh)
    rep["lights"]["stern"] = stern_light(hw)
    foot, ax = ensign_socket(hw)
    parts = {"DeckHardware": hw}
    # the cowls stand in their flanges in harbour; at sea they are struck below and the flanges capped
    rep["cowls"] = {}
    for s in SUITS:
        cp = SparPart(f"Cowls.{s}" if s in HW["cowls"]["standing_in"] else f"CowlCaps.{s}")
        for g, at, deg, _ in cowls:
            if s in HW["cowls"]["standing_in"]:
                rep["cowls"][g] = cowl(cp, at, deg, g)
            else:
                cowl_cap(cp, at, g)
        parts[cp.name] = cp
    en = SparPart("Ensign.Moored")
    rep["ensign"] = ensign(en, foot, ax)
    parts[en.name] = en
    rep["burgee"] = {}
    for s in SUITS:
        bp = SparPart(f"Burgee.{s}")
        rep["burgee"][s] = burgee(bp, pts, HW["burgee"]["flies_deg"][s])
        parts[bp.name] = bp
    rep["weights"] = weights(parts)
    return parts, rep


def weights(parts):
    """The hardware's weight by row: the fixed hardware, the ensign and its staff (aboard: stowed below at sea), the
    cowls and their caps (one set stowed below while the other is up: weighed where they stand) and one burgee."""
    up = HW["cowls"]["standing_in"][0]
    capped = next(s for s in SUITS if s not in HW["cowls"]["standing_in"])
    rows = (list(parts["DeckHardware"].masses) + list(parts["Ensign.Moored"].masses)
            + list(parts[f"Burgee.{SUITS[0]}"].masses) + list(parts[f"Cowls.{up}"].masses)
            + list(parts[f"CowlCaps.{capped}"].masses))
    tot = {}
    for m in rows:
        t = tot.setdefault(m["part"], {"kg": 0.0, "mom": np.zeros(3)})
        t["kg"] += m["kg"]
        t["mom"] += m["kg"] * np.asarray(m["centre"], float)
    kg = sum(v["kg"] for v in tot.values())
    mom = sum((v["mom"] for v in tot.values()), np.zeros(3))
    return {"rows": {k: {"kg": round(v["kg"], 1), "centre": [round(float(a), 3) for a in v["mom"] / max(v["kg"], 1e-9)]}
                     for k, v in tot.items()},
            "total_kg": round(kg, 1), "total_long_tons": round(kg / deck.LT_KG, 3),
            "centre": [round(float(a), 3) for a in mom / max(kg, 1e-9)]}


def summary(rep):
    """The report for build.json: without its working keys (those starting with '_', at any depth) and the mooring
    lines' leads (their room is reported)."""
    def strip(v):
        if isinstance(v, dict):
            return {k: strip(a) for k, a in v.items() if not str(k).startswith("_")}
        if isinstance(v, (list, tuple)):
            return [strip(a) for a in v]
        return v
    return strip({k: v for k, v in rep.items() if k not in ("mooring_leads", "cable_leads")})
