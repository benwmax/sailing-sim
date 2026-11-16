"""The Catalina 22's deck, cockpit and cabin trunk from deck_c22.json: pure geometry, no Blender (docs/c22-3).

The deck is a cambered surface over the hull's sheer (hull_c22): its height at (x, y) is the sheer's plus a parabola
of the crown across the deck's edge. The cockpit is a rectangle cut from it, with a bench seat each side and the
footwell between. The cabin trunk stands on the deck. Its sides start at a half-width that keeps a side deck where she
narrows, and they lean in as they rise. Its top is crowned and rises to the companionway. Its front rakes aft and is
rounded in plan. The pop-top is the part of the top between pop_top.x, inset from its edges. build_c22.py meshes all of
it; this module only answers where things are.

    python3 -I deck_c22.py          prints the main heights and checks the mast step against today's socket

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the design waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_c22 as H  # noqa: E402

D = json.load(open(os.path.join(HERE, "deck_c22.json")))
CK, CB, PT, CW = D["cockpit"], D["cabin"], D["pop_top"], D["companionway"]
MAST_X = H.CARD["game"]["mast_x_m"]
CROWN_FULL_HB = 0.6     # forward of where the half-beam falls under this, the deck's crown shrinks with the beam


def deck_z(x, y):
    """The deck's height at (x, y): the sheer at the deck's edge, crown more on the centreline."""
    hb = H.half_beam(x)
    v = min(abs(y) / hb, 1.0)
    return H.sheer_z(x) + D["deck"]["crown"] * min(1.0, hb / CROWN_FULL_HB) * (1 - v * v)


def smooth_min(a, b, k=0.08):
    """min(a, b), rounded over k so a line that follows it has no corner."""
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


def trunk_base(x):
    """Half-width where the trunk's side stands on the deck."""
    return smooth_min(CB["half_width_max"], H.half_beam(x) - CB["side_deck_min"])


def trunk_edge(x):
    """Half-width of the trunk top's edge (the side leans in)."""
    return trunk_base(x) - CB["side_lean"]


def trunk_height(x):
    """The top's height over the deck's centreline: aft_height at the companionway, height_at_mast at the mast, on a
    straight line through both."""
    x0 = CB["x"][0]
    return CB["aft_height"] + (CB["height_at_mast"] - CB["aft_height"]) * (x - x0) / (MAST_X - x0)


def top_z(x, y):
    """The trunk top's height at (x, y): crowned, top_crown lower at its edges than on the centreline."""
    e = trunk_edge(x)
    v = min(abs(y) / e, 1.0)
    return deck_z(x, 0.0) + trunk_height(x) - CB["top_crown"] * v * v


def front_foot_x(v):
    """Where the front meets the deck, at v (-1 port edge .. 1 starboard edge): its middle forward of its corners."""
    return CB["x"][1] - CB["front_round"] * v * v


def front_top_x(v):
    """Where the front meets the top: raked aft of its foot."""
    return front_foot_x(v) - CB["front_rake"]


def side_point(x, t, side):
    """A point on the trunk's side at x, t of the way up (0 on the deck, 1 at the top's edge), side +1 starboard."""
    b, e = trunk_base(x), trunk_edge(x)
    y = side * (b + (e - b) * t)
    z0, z1 = deck_z(x, b), top_z(x, e)
    return (x, y, z0 + (z1 - z0) * t)


def seat_z(x):
    return deck_z(x, CK["half_width"]) - CK["seat_drop"]


def bridge_z():
    """The companionway's sill: the seats' height at the bulkhead."""
    return seat_z(CB["x"][0])


def hole_v():
    """The pop-top opening's edge across the top, as a share of the top's half-width (inset from its edge)."""
    return 1 - PT["inset"] / trunk_edge(0.5 * (PT["x"][0] + PT["x"][1]))


def top_x(s, v):
    """Where the top's grid lines run: s 0..1 from the companionway to the front's top edge. Up to S1 they stand at
    fixed x (so the pop-top opening's forward edge, x = pop_top.x[1], is one of them); beyond, they run to the raked,
    rounded front."""
    x0, p1 = CB["x"][0], PT["x"][1]
    if s <= S1:
        return x0 + (p1 - x0) * s / S1
    return p1 + (front_top_x(v) - p1) * (s - S1) / (1 - S1)


def side_x(u, t):
    """The same grid lines on the side, t of the way up: at fixed x to the pop-top's front, then to the raked corner."""
    x0, p1 = CB["x"][0], PT["x"][1]
    if u <= S1:
        return x0 + (p1 - x0) * u / S1
    xf = front_foot_x(1.0) - CB["front_rake"] * t
    return p1 + (xf - p1) * (u - S1) / (1 - S1)


def trunk_point(x, v, t):
    """A point on the trunk's skin at x, across v (-1 port edge .. 1 starboard edge), t of the way up from the deck (0)
    to the top (1). The sides are v = +-1, the front is x = front_foot_x(v) - front_rake * t, the top is t = 1: one
    formula, so their shared edges meet exactly."""
    b, e = trunk_base(x), trunk_edge(x)
    y = v * (b + (e - b) * t)
    z0, z1 = deck_z(x, v * b), top_z(x, v * e)
    return (x, y, z0 + (z1 - z0) * t)


def fillet(prev, corner, nxt, r, n=6):
    """Points of a circular arc of radius r rounding the corner of the polyline prev-corner-nxt (2D), from its tangent
    point on the incoming leg to the one on the outgoing leg. r is cut to fit if a leg is too short."""
    ux, uy = prev[0] - corner[0], prev[1] - corner[1]
    vx, vy = nxt[0] - corner[0], nxt[1] - corner[1]
    lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
    ux, uy, vx, vy = ux / lu, uy / lu, vx / lv, vy / lv
    cosang = max(-1.0, min(1.0, ux * vx + uy * vy))
    half = math.acos(cosang) / 2
    if half < 1e-6 or half > math.pi / 2 - 1e-6:
        return [corner]
    d = min(r / math.tan(half), 0.45 * lu, 0.45 * lv)
    r = d * math.tan(half)
    p0 = (corner[0] + ux * d, corner[1] + uy * d)
    p1 = (corner[0] + vx * d, corner[1] + vy * d)
    bx, by = ux + vx, uy + vy
    bl = math.hypot(bx, by)
    c = (corner[0] + bx / bl * r / math.sin(half), corner[1] + by / bl * r / math.sin(half))
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    return [(c[0] + r * math.cos(a0 + da * i / n), c[1] + r * math.sin(a0 + da * i / n)) for i in range(n + 1)]


def round_polygon(pts, r, n=6):
    """A closed polygon (2D) with every corner rounded on radius r."""
    out = []
    for i, p in enumerate(pts):
        out += fillet(pts[i - 1], p, pts[(i + 1) % len(pts)], r, n)
    return out


def port_outline(k, n=6):
    """Window k's outline on the starboard side as (x, t): its aft end upright, its forward end raked parallel to the
    cabin front, its corners rounded; its length the window's share of the side at its height, centred at z_share of
    the side's height."""
    W = D["windows"]
    a, b = W["ports"][k]
    tc = W["z_share"]
    x0 = CB["x"][0]
    L = side_x(1.0, tc) - x0
    xa, xb = x0 + a * L, x0 + b * L
    xm = 0.5 * (xa + xb)
    h = top_z(xm, trunk_edge(xm)) - deck_z(xm, trunk_base(xm))       # the side's height there
    k_rake = CB["front_rake"] / h                                      # the front's lean aft per metre up
    hh = 0.5 * W["height"]
    quad = [(xa, -hh), (xb + k_rake * hh, -hh), (xb - k_rake * hh, hh), (xa, hh)]
    return [(x, tc + z / h) for x, z in round_polygon(quad, W["corner_radius"], n)]


def hull_half_breadth(x, z, m=400):
    """The hull's half-breadth at height z on station x (None under her bottom)."""
    prev = H.section(x, 0.0)
    if prev[1] > z:
        return None
    for k in range(1, m + 1):
        cur = H.section(x, k / m)
        if prev[1] <= z <= cur[1]:
            t = (z - prev[1]) / max(cur[1] - prev[1], 1e-9)
            return prev[0] + (cur[0] - prev[0]) * t
        prev = cur
    return H.half_beam(x)


def well_clearance():
    """The least room (m) between the cockpit's well and the hull's inside, along the cockpit: the footwell's corners
    at the sole and the seats' outer corners. A negative number means the well pokes through her skin."""
    worst = (9.0, None)
    for i in range(41):
        x = CK["x"][0] + (CK["x"][1] - CK["x"][0]) * i / 40
        for y, z in ((CK["footwell_half_width"], CK["sole_z"]), (CK["half_width"], seat_z(x))):
            hb = hull_half_breadth(x, z)
            room = -1.0 if hb is None else hb - y
            if room < worst[0]:
                worst = (room, (round(x, 3), y, round(z, 3)))
    return worst


S1 = 0.6     # share of the top's grid lines aft of the pop-top's front edge


def main():
    mz = top_z(MAST_X, 0.0)
    sock = H.CARD["game"]
    print(f"deck at the centreline: aft {deck_z(H.TRANSOM_X, 0):.3f}, mast {deck_z(MAST_X, 0):.3f}, "
          f"bow {deck_z(H.STEM_X - 0.3, 0):.3f}")
    print(f"trunk: base half-width aft {trunk_base(CB['x'][0]):.3f}, front {trunk_base(CB['x'][1]):.3f}; "
          f"top at the companionway {top_z(CB['x'][0], 0):.3f}, at the mast {mz:.3f} (MastStep socket z 1.188), "
          f"at the front {top_z(front_top_x(0), 0):.3f}")
    print(f"cockpit: seats {seat_z(CK['x'][0]):.3f} aft, {seat_z(CK['x'][1]):.3f} fwd; sole {CK['sole_z']:.3f}; "
          f"bridge {bridge_z():.3f}; the game's boom at z {sock['boom_z_m']}")
    H.solve_depth()
    room, where = well_clearance()
    print(f"cockpit well: least room to the hull's skin {room * 1000:.0f} mm at {where}")
    raised = top_z(PT['x'][1], 0) + PT['lid_rise'] + PT['lift']
    print(f"pop-top opening edge at v {hole_v():.3f}; raised lid at its forward end {raised:.3f}, over the boom's "
          f"{sock['boom_z_m']}: {'clears' if raised < sock['boom_z_m'] - 0.07 else 'only with the boom topped up or off'}")
    if room < 0.01:
        sys.exit("the cockpit's well comes within 1 cm of the hull's skin")
    if abs(mz - 1.188) > 0.01:
        sys.exit("the trunk top at the mast is more than 1 cm from today's MastStep socket")


if __name__ == "__main__":
    main()
