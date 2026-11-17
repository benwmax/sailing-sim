"""The Catalina 22's cabin below (docs/c22-8): where every piece of it goes, from cabin_c22.json, and the checks. Pure
geometry, no Blender: build_cabin_c22.py meshes it.

    python3 -I cabin_c22.py         prints the layout's sizes and checks, and fails if any check does

The cabin is the inside of slices 1 and 2's mouldings: the hull's, deck's and trunk's skins drawn again inside their
laminate (the liner), then the sole, bulkhead, berths, dinette, galley, steps, porta-potti and the keel's winch fitted
to that inside. A piece against the hull is a "fitted" one: its outboard edge follows the liner at each height, `clear`
inside it. Every piece is a list of solids (closed, axis-aligned but for the fitted outboard edge) so the checks can
test them against the liner and against each other.

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the design waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_c22 as H  # noqa: E402
import deck_c22 as D  # noqa: E402
import keel_c22 as KC  # noqa: E402

C = json.load(open(os.path.join(HERE, "cabin_c22.json")))
LN, SO, BH, VB = C["liner"], C["sole"], C["bulkhead"], C["vberth"]
DN, ST, QB, GL, STP, KW = C["dinette"], C["settee"], C["quarter_berth"], C["galley"], C["steps"], C["keel_winch"]
CLEAR = C["clear"]
LID_THICK = 0.006        # build_deck_c22.LID_THICK: the closed lid's underside under its skin (keep in step)
SEAT_THICK = LN["deck"]  # the cockpit's well is lined as the deck is: what the quarter berth and galley keep under
GALLEY_HANDLE = 0.037    # build_cabin_c22.build_galley: the handle stands this far proud of the galley's front


# ------------------------------------------------------------------ the inside of the mouldings

def inner_hb(x, z):
    """The hull liner's half-breadth at height z on station x: the hull's skin moved its thickness in along its
    normal, read across at z (where the bottom is flat that moves it far in). 0 under the bottom."""
    t, dz = LN["hull"], 0.01
    a, b = D.hull_half_breadth(x, z - dz), D.hull_half_breadth(x, z + dz)
    y = D.hull_half_breadth(x, z)
    if y is None:
        return 0.0
    if a is None or b is None:
        return max(0.0, y - t)
    slope = (b - a) / (2 * dz)
    return max(0.0, y - t * math.sqrt(1 + slope * slope))


def deck_under(x, y):
    return D.deck_z(x, y) - LN["deck"]


def top_under(x, y):
    """The trunk top's underside, or the closed pop-top lid's where it covers the opening."""
    if D.PT["x"][0] <= x <= D.PT["x"][1] and abs(y) < D.hole_v() * D.trunk_edge(x):
        return D.top_z(x, y) + D.PT["lid_rise"] - LID_THICK
    return D.top_z(x, y) - LN["cabin"]


def trunk_inner(x, z):
    """The trunk side liner's half-width at height z (its side leans in as it rises), or None outside the trunk."""
    if not (D.CB["x"][0] <= x <= D.front_foot_x(1.0)):
        return None
    b, e = D.trunk_base(x), D.trunk_edge(x)
    z0, z1 = D.deck_z(x, b), D.top_z(x, e)
    t = min(max((z - z0) / (z1 - z0), 0.0), 1.0)
    return b + (e - b) * t - LN["cabin"]


def ceiling(x, y):
    """The underside over (x, y): the trunk's top inside the trunk; under the cockpit, the well's liner (the footwell's
    sole inboard of its sides, the seats out to the coamings); the deck's elsewhere."""
    if D.CB["x"][0] <= x <= D.front_top_x(0.0) and abs(y) <= D.trunk_edge(x) - LN["cabin"]:
        return top_under(x, y)
    CK = D.CK
    if CK["x"][0] <= x < D.CB["x"][0]:
        if abs(y) < CK["footwell_half_width"] + SEAT_THICK:
            return CK["sole_z"] - SEAT_THICK
        if abs(y) < CK["half_width"] + SEAT_THICK:
            return D.seat_z(x) - SEAT_THICK
    return deck_under(x, y)


def fit(x, z):
    """Where a fitted piece's outboard edge stands at (x, z): the liner, `clear` in."""
    return max(0.0, inner_hb(x, z) - CLEAR)


def headroom(raised=False, x=None):
    """The headroom under the pop-top, sole to the lid's underside on the centreline, at the lid's middle."""
    x = 0.5 * (D.PT["x"][0] + D.PT["x"][1]) if x is None else x
    return top_under(x, 0.0) + (D.PT["lift"] if raised else 0.0) - SO["z"]


def trunk_out_top(x):
    """The keel trunk's outside top in the cabin (build_keel_c22: the slot's top plus its wall), None off its ends."""
    if not (KC.SL["x"][0] <= x <= KC.SL["x"][1]):
        return None
    return KC.trunk_top(x) + KC.SL["wall"]


TRUNK_W = KC.SL["half_width"] + KC.SL["wall"]


# ------------------------------------------------------------------ the pieces

class Solid:
    """A block from x0 to x1 and z0 to z1; across, from y_in to y_out, where either may be a number or 'fit' (the
    liner, `clear` in, at that x and z). side +1 puts it to starboard, -1 to port, 0 across the centreline (y_in is
    then ignored: -fit to +fit)."""

    def __init__(self, name, slot, x, z, y_in, y_out="fit", side=1, kind="board"):
        self.name, self.slot, self.kind = name, slot, kind
        self.x0, self.x1 = x
        self.z0, self.z1 = z
        self.y_in, self.y_out, self.side = y_in, y_out, side

    def across(self, x, z):
        """(y_lo, y_hi) at (x, z), game frame."""
        yo = fit(x, z) if self.y_out == "fit" else self.y_out
        if self.side == 0:
            return -yo, yo
        yi = self.y_in
        lo, hi = sorted((yi, yo))
        return (lo, hi) if self.side > 0 else (-hi, -lo)

    def stations(self, n=None):
        n = n or max(2, int(math.ceil((self.x1 - self.x0) / 0.05)) + 1)
        return [self.x0 + (self.x1 - self.x0) * i / (n - 1) for i in range(n)]


def layout(galley_out=False, table_down=False):
    """Every solid of the cabin, in one list."""
    S = []
    zs = SO["z"]
    # the sole: around the keel trunk where it stands, across the boat elsewhere
    t0, t1 = KC.SL["x"]
    for x0, x1, yin in ((SO["x"][0], t0 - 0.002, None), (t0 - 0.002, t1 + 0.002, TRUNK_W), (t1 + 0.002, SO["x"][1], None)):
        if yin is None:
            S.append(Solid("Sole", "Sole", (x0, x1), (zs - 0.02, zs), 0, side=0))
        else:
            for sd in (1, -1):
                S.append(Solid("Sole", "Sole", (x0, x1), (zs - 0.02, zs), yin, side=sd))
    # the V-berth: its top board, its front with the porta-potti's opening, its cushions
    vx0, vx1, vt = VB["x"][0], VB["x"][1], VB["top"]
    ix0, ix1 = VB["insert_x"]
    ih = VB["insert_half_width"]
    S.append(Solid("VBerthTop", "Laminate", (ix1, vberth_end(vt - 0.02, 0.04)), (vt - 0.02, vt), 0, side=0))
    for sd in (1, -1):                                  # beside the insert's lift-out board
        S.append(Solid("VBerthTop", "Laminate", (vx0, ix1), (vt - 0.02, vt), ih + 0.003, side=sd))
    S.append(Solid("VBerthLid", "Laminate", (vx0 + 0.003, ix1 - 0.003), (vt - 0.02, vt), -ih, ih, kind="box"))
    for sd in (1, -1):                                  # the front, open in the middle to the porta-potti
        S.append(Solid("VBerthFront", "Laminate", (vx0, vx0 + 0.02), (zs, vt - 0.02), VB["front_opening"], side=sd,
                       kind="front"))
    zc = (vt, vt + VB["cushion"])
    S.append(Solid("VBerthCushionFwd", "Cushion", (ix1 + 0.005, vberth_end()), zc, 0, side=0, kind="cushion"))
    for sd in (1, -1):
        S.append(Solid("VBerthCushionAft", "Cushion", (ix0, ix1), zc, ih + 0.005, side=sd, kind="cushion"))
    S.append(Solid("VBerthInsert", "Cushion", (ix0, ix1), zc, ih, side=1, kind="cushion"))
    S[-1].y_in, S[-1].y_out = -ih, ih
    PP = C["porta_potti"]
    S.append(Solid("PottiFloor", "Sole", (vx0, PP["x"] + PP["size"][0] + PP["floor_past"]), (zs - 0.02, zs), 0, side=0))
    S.append(Solid("PortaPotti", "WhitePlastic", (PP["x"], PP["x"] + PP["size"][0]), (zs, zs + PP["size"][2]),
                   -PP["size"][1] / 2, PP["size"][1] / 2, kind="box"))
    # the starboard settee and the quarter berth
    sx0, sx1 = ST["x"]
    S.append(Solid("SetteeBase", "Laminate", (sx0, sx1), (zs, ST["top"]), ST["front_y"], side=1, kind="front"))
    S.append(Solid("SetteeCushion", "Cushion", (sx0, sx1), (ST["top"], ST["top"] + ST["cushion"]), ST["front_y"] - 0.01,
                   side=1, kind="cushion"))
    qx0, qx1 = QB["x"]
    S.append(Solid("QuarterBerth", "Laminate", (qx0, qx1), (QB["top"] - 0.02, QB["top"]), QB["inboard_y"], side=1))
    S.append(Solid("QuarterBerthCushion", "Cushion", (qx0 + 0.01, qx1), (QB["top"], QB["top"] + QB["cushion"]),
                   QB["inboard_y"], side=1, kind="cushion"))
    # the dinette to port
    for nm, (x0, x1) in (("DinetteAft", DN["aft_seat"]), ("DinetteFwd", DN["fwd_seat"])):
        S.append(Solid(nm + "Base", "Laminate", (x0, x1), (zs, DN["seat_top"]), DN["inboard_y"], side=-1, kind="front"))
        S.append(Solid(nm + "Cushion", "Cushion", (x0 + 0.005, x1 - 0.005),
                       (DN["seat_top"], DN["seat_top"] + DN["cushion"]), DN["inboard_y"] + 0.005, side=-1, kind="cushion"))
    xa = DN["aft_seat"][0]
    S.append(Solid("DinetteBack", "Laminate", (xa - DN["back_thick"], xa),
                   (zs, DN["seat_top"] + DN["cushion"] + DN["back_height"]), DN["inboard_y"], side=-1, kind="front"))
    tz = DN["table_down_z"] if table_down else DN["table_z"]
    t0x, t1x = DN["table"]
    S.append(Solid("Table", "Laminate", (t0x + 0.01, t1x - 0.01), (tz - 0.025, tz), DN["inboard_y"],
                   min(fit(t0x, tz), fit(t1x, tz), 0.8), side=-1, kind="box"))
    if table_down:
        S.append(Solid("TableCushion", "Cushion", (t0x + 0.01, t1x - 0.01), (tz, tz + DN["cushion"]), DN["inboard_y"] + 0.005,
                       side=-1, kind="cushion"))
    # the steps, galley and keel winch
    S.append(Solid("Step", "Laminate", tuple(STP["x"]), (zs, STP["top"]), -STP["half_width"], STP["half_width"], kind="box"))
    gx0, gx1 = GL["x"]
    sl = GL["slide"] if galley_out else 0.0
    S.append(Solid("Galley", "Laminate", (gx0 + sl, gx1 + sl), tuple(GL["z"]), -GL["y"][1], -GL["y"][0], side=-1,
                   kind="box"))
    return S


def vberth_end(z=None, width=None):
    """Where the V-berth's cushions end forward: where the platform is min_width across at the cushion's top (or
    `width` across at z: where its top board ends)."""
    z = VB["top"] + VB["cushion"] if z is None else z
    width = VB["min_width"] if width is None else width
    x = VB["x"][0]
    while x < VB["x"][1] and 2 * fit(x, z) > width:
        x += 0.005
    return x


# ------------------------------------------------------------------ the checks

def corners(s):
    out = []
    for x in s.stations():
        for z in (s.z0, s.z1):
            lo, hi = s.across(x, z)
            out += [(x, lo, z), (x, hi, z)]
    return out


def inside_liner(s):
    """The least room between the solid and the liner (hull at its height, deck or top over it), m; negative is in."""
    worst = 9.0
    for x, y, z in corners(s):
        worst = min(worst, inner_hb(x, z) - abs(y), ceiling(x, y) - z)
    return worst


def overlap(a, b):
    """True if two solids share volume (more than a millimetre each way), sampled at a's and b's stations."""
    lo_x, hi_x = max(a.x0, b.x0), min(a.x1, b.x1)
    lo_z, hi_z = max(a.z0, b.z0), min(a.z1, b.z1)
    if hi_x - lo_x < 0.001 or hi_z - lo_z < 0.001:
        return False
    for x in [lo_x + (hi_x - lo_x) * i / 8 for i in range(9)]:
        for z in (lo_z + 0.0005, hi_z - 0.0005):
            al, ah = a.across(x, z)
            bl, bh = b.across(x, z)
            if min(ah, bh) - max(al, bl) > 0.001:
                return True
    return False


def trunk_clash(s):
    """True if the solid stands in the keel trunk (its walls and top in the cabin)."""
    for x in s.stations():
        t = trunk_out_top(x)
        if t is None:
            continue
        lo, hi = s.across(x, s.z0)
        if s.z0 < t - 0.001 and min(hi, TRUNK_W) - max(lo, -TRUNK_W) > 0.001:
            return True
    return False


ALLOWED = {frozenset(p) for p in (("Sole", "VBerthFront"), ("Sole", "SetteeBase"), ("Sole", "DinetteAftBase"),
                                  ("Sole", "DinetteFwdBase"), ("Sole", "DinetteBack"), ("Sole", "Step"),
                                  ("PottiFloor", "VBerthFront"), ("VBerthInsert", "VBerthCushionAft"))}


def checks(report, fails, galley_out=False, table_down=False):
    n0 = len(fails)
    S = layout(galley_out, table_down)
    tag = ("galley out" if galley_out else "") + (" table down" if table_down else "")
    for s in S:
        room = inside_liner(s)
        ok = room >= CLEAR - 0.0015                       # fitted edges sit at CLEAR exactly, to the sampling
        if not ok:
            fails.append(f"{s.name} {room * 1000:.0f} mm into the liner {tag}")
        if trunk_clash(s):
            fails.append(f"{s.name} in the keel trunk {tag}")
    for i, a in enumerate(S):
        for b in S[i + 1:]:
            if a.name == b.name or frozenset((a.name, b.name)) in ALLOWED:
                continue
            if overlap(a, b):
                fails.append(f"{a.name} through {b.name} {tag}")
    report.append(f"  {len(S)} pieces {tag or 'as moored'}: clear of the liner, the keel trunk and each other "
                  f"{'ok' if len(fails) == n0 else 'FAIL'}")


def measures():
    """The layout's sizes, each with its limits: (name, value, lo, hi, note)."""
    zs = SO["z"]
    vb_len = vberth_end() - VB["x"][0]
    vb_w = 2 * fit(VB["x"][0] + 0.45, VB["top"] + VB["cushion"])
    qb_len = QB["x"][1] - QB["x"][0]
    qb_w = fit(QB["x"][1] - 0.45, QB["top"] + QB["cushion"]) - QB["inboard_y"]
    qb_head = min(D.seat_z(x) - SEAT_THICK for x in (QB["x"][0], QB["x"][1])) - (QB["top"] + QB["cushion"])
    seat = ST["top"] + ST["cushion"] - zs
    dn_seat = DN["seat_top"] + DN["cushion"] - zs
    dn_len = DN["fwd_seat"][1] - DN["aft_seat"][0]
    table = DN["table_z"] - zs
    sit_v = min(deck_under(x, 0.3) for x in (VB["x"][0] + 0.2, VB["x"][0] + 0.8)) - (VB["top"] + VB["cushion"])
    sill = D.bridge_z()
    rises = (STP["top"] - zs, sill - STP["top"])
    g_top = GL["z"][1]
    g_room = min(D.seat_z(x) - SEAT_THICK for x in GL["x"]) - g_top
    g_out = (GL["x"][1] + GL["slide"] + GALLEY_HANDLE) - (DN["aft_seat"][0] - DN["back_thick"])
    return [
        ("headroom, pop-top closed", headroom(False), 1.30, 1.34, "the card's 4 ft 4 in (1.32 m), sole to the lid's underside"),
        ("headroom, pop-top raised", headroom(True), 1.68, 1.72, "the card's 5 ft 7 in (1.70 m)"),
        ("V-berth length", vb_len, 1.78, 2.1, "bulkhead to where the cushions are 22 cm across"),
        ("V-berth width at the shoulders", vb_w, 1.2, 2.0, "45 cm forward of its aft edge, cushion top"),
        ("V-berth sitting room", sit_v, 0.48, 1.0, "cushion top to the deck's underside, 30 cm off the centreline"),
        ("quarter berth length", qb_len, 1.83, 2.1, ""),
        ("quarter berth width at the shoulders", qb_w, 0.5, 0.8, "45 cm aft of its head, cushion top"),
        ("quarter berth room under the seat", qb_head, 0.3, 0.6, "cushion top to the cockpit seat's underside"),
        ("settee seat height", seat, 0.4, 0.48, "over the sole, cushion top"),
        ("settee length", ST["x"][1] - ST["x"][0], 1.75, 2.1, ""),
        ("dinette seat height", dn_seat, 0.4, 0.48, ""),
        ("dinette berth length", dn_len, 1.42, 2.0, "aft seat to the bulkhead with the table down: a short double"),
        ("table height", table, 0.68, 0.76, "over the sole"),
        ("companionway rises", max(rises), 0.0, 0.32, f"sole {zs:.2f} to step {STP['top']:.2f} to sill {sill:.3f}"),
        ("galley under the seat", g_room, 0.03, 0.3, "its top to the cockpit seat's underside, stowed"),
        ("galley out, clear of the dinette", -g_out, 0.0, 0.3, "its handle to the dinette's back, pulled out"),
    ]


def run():
    fails, report = [], []
    for name, v, lo, hi, note in measures():
        ok = lo <= v <= hi
        report.append(f"  {name:38s} {v:6.3f} m  ({lo:.2f} to {hi:.2f})  {note}  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(name)
    for go, td in ((False, False), (True, False), (False, True)):
        checks(report, fails, go, td)
    return report, fails


def main():
    H.CANOE_D[0] = H.solve_depth()
    report, fails = run()
    print("Catalina 22 cabin below (slice 7)")
    for r in report:
        print(r)
    if fails:
        print("FAIL: " + "; ".join(fails))
        sys.exit(1)
    print("pass")


if __name__ == "__main__":
    main()
