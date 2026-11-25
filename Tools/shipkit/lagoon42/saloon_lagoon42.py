"""The Lagoon 42's hull decks, saloon walls and roof from saloon_lagoon42.json: pure geometry, no Blender
(docs/lagoon42-4).

The hull decks span each hull between its inboard and outboard sheer (hull_lagoon42.half_beam), crowned over the
hull's centre; the saloon's walls stand on the foredeck and the hulls' decks and run up into the roof; the roof is one
moulding over the saloon and the cockpit, a rounded rectangle in plan with a thick rounded edge. build_lagoon42.py
meshes them.

    python3 -I saloon_lagoon42.py      prints the main numbers and writes nothing

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the game's waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_lagoon42 as H  # noqa: E402

SD = json.load(open(os.path.join(HERE, "saloon_lagoon42.json")))
SAL, ROOF, DECK = SD["saloon"], SD["roof"], SD["deck"]
WALL_TOP = ROOF["under_z"] + 0.04            # the walls run 4 cm up into the roof


# ---- the hulls' decks ----

def deck_z(x, t):
    """A hull's deck at station x, t across it from -1 (one sheer) to 1 (the other): the sheer plus the crown."""
    return H.sheer_z(x) + DECK["camber"] * (1 - t * t)


def deck_stations():
    """The deck's stations: the hull's own from the sugar scoop's last riser to the stem."""
    return [x for x in H.stations(220) if x >= H.SCOOP_END + 0.0005]


def deck_rows(cy, n=12):
    """One hull's deck as rows across (inboard to outboard of the hull centred at cy), aft to forward."""
    rows = []
    xs = deck_stations()
    for x in xs:
        hb = 0.0 if x == xs[-1] else H.half_beam(x)
        rows.append([(x, cy + hb * (2 * j / n - 1), deck_z(x, 2 * j / n - 1)) for j in range(n + 1)])
    return rows


def toe_rail_rows(cy, out_sign):
    """The toe rail on a hull's outboard sheer: rows of its profile (deck side, top inside, top outside, the topsides'
    line) along the stations between from_x and to_x."""
    tr = DECK["toe_rail"]
    rows = []
    for x in deck_stations():
        if not tr["from_x"] <= x <= tr["to_x"]:
            continue
        hb = H.half_beam(x)
        t_in = (hb - tr["width"]) / hb
        z0, zi = H.sheer_z(x), deck_z(x, t_in)
        yo, yi = cy + out_sign * hb, cy + out_sign * (hb - tr["width"])
        rows.append([(x, yi, zi - 0.005), (x, yi, z0 + tr["height"]), (x, yo, z0 + tr["height"]), (x, yo, z0 - 0.01)])
    return rows


def hatches(cy):
    """Each hatch on a hull centred at cy: (x0, x1, y0, y1, z0, z1), the frame's footprint and heights."""
    out = []
    for h in DECK["hatches"]:
        lx, ly = h["size"]
        z0 = deck_z(h["x"], 0.0) - 0.01
        out.append((h["x"] - lx / 2, h["x"] + lx / 2, cy - ly / 2, cy + ly / 2, z0, z0 + 0.01 + DECK["hatch_height"]))
    return out


# ---- the saloon ----

def _bezier(a, c, b, n):
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]) for t in (k / n for k in range(n + 1))]


def _line(a, b, n):
    return [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]


def saloon_half(n_front=14, n_corner=10, n_side=16, n_back=6, n_aft=14):
    """The starboard half of the saloon's plan from the front's centre round to the aft bulkhead's centre:
    [(x, y, glazed)], glazed telling whether the wall from this point to the next is glass between the plinth and
    the windows' top."""
    fx, (cx, cy), r = SAL["front_x"], SAL["corner"], SAL["corner_round"]
    swa, aft = SAL["side_window_aft"], SAL["aft"]
    front_x = lambda y: cx + (fx - cx) * (1 - (y / cy) ** 2)
    ya = cy - r * 0.8                                         # the corner's rounding starts here on the front...
    a = (front_x(ya), ya)
    d = math.hypot(swa[0] - cx, swa[1] - cy)
    b = (cx + (swa[0] - cx) * r / d, cy + (swa[1] - cy) * r / d)   # ...and ends here on the side
    pts = [(front_x(ya * k / n_front), ya * k / n_front, True) for k in range(n_front)]
    pts += [(x, y, True) for x, y in _bezier(a, (cx, cy), b, n_corner)[:-1]]
    pts += [(x, y, True) for x, y in _line(b, swa, n_side)[:-1]]
    pts += [(x, y, False) for x, y in _line(swa, aft, n_back)[:-1]]
    pts += [(x, y, abs(y) < SAL["door_half_width"] + 1e-6) for x, y in _line(aft, (aft[0], 0.0), n_aft)]
    return pts


def saloon_plan():
    """The whole saloon's plan as one closed loop [(x, y, glazed)]: the front's centre, the starboard side, the aft
    bulkhead, the port side and back (counter-clockwise seen from above with X forward and Y starboard)."""
    stbd = saloon_half()
    port = [(x, -y, None) for x, y, _ in reversed(stbd)]
    # the port half runs the other way: a wall's glazing belongs to the point it starts from
    port = [(x, y, stbd[len(stbd) - 2 - i][2]) for i, (x, y, _) in enumerate(port)][1:]
    loop = stbd + port[:-1]
    return loop


def _normals(loop):
    n = len(loop)
    out = []
    for i in range(n):
        x0, y0 = loop[i - 1][:2]
        x1, y1 = loop[(i + 1) % n][:2]
        tx, ty = x1 - x0, y1 - y0
        L = math.hypot(tx, ty)
        out.append((ty / L, -tx / L))
    return out


def wall_levels():
    """The heights of the saloon walls' rows: under the deck, the plinth's top, the windows' top, inside the roof."""
    return ["base", SAL["plinth_z"], SAL["window_top_z"], WALL_TOP]


def wall_point(x, y, n, z):
    """A wall point over plan point (x, y) at height z (or 'base': 3 cm under the sheer there), leaning in above the
    plinth: the front by rake_front, the sides by tumblehome, by the wall's facing n."""
    if z == "base":
        return (x, y, H.sheer_z(x) - 0.03)
    h = max(0.0, (z - SAL["plinth_z"]) / (WALL_TOP - SAL["plinth_z"]))
    lean = (abs(n[0]) * SAL["rake_front"] + abs(n[1]) * SAL["tumblehome"]) * h
    return (x - n[0] * lean, y - n[1] * lean, z)


def wall_rows():
    """The walls as rows (one per level) round the loop, and the loop's glazing flags."""
    loop = saloon_plan()
    ns = _normals(loop)
    rows = [[wall_point(x, y, n, z) for (x, y, _), n in zip(loop, ns)] for z in wall_levels()]
    return rows, [g for _, _, g in loop]


# ---- the roof ----

def roof_outline(d, nf=12, nc=8, ns=18, na=12):
    """The roof's plan inset d from its outermost line: a rounded rectangle, the front bowed forward, every inset the
    same number of points (counter-clockwise from the front's centre)."""
    R = ROOF
    xf, xa, w = R["front_x"] - d, R["aft_x"] + d, R["half_width"] - d
    rf, ra, bow = max(R["corner_front"] - d, 0.05), max(R["corner_aft"] - d, 0.05), R["bow"]
    xc = xf - bow
    L = w - rf
    front = lambda y: xc + bow * (1 - (y / L) ** 2) ** 2
    P = [(front(L * k / nf), L * k / nf) for k in range(nf)]
    P += [(xc - rf + rf * math.cos(a), L + rf * math.sin(a)) for a in (math.pi / 2 * k / nc for k in range(nc))]
    P += _line((xc - rf, w), (xa + ra, w), ns)[:-1]
    P += [(xa + ra + ra * math.cos(a), w - ra + ra * math.sin(a))
          for a in (math.pi / 2 + math.pi / 2 * k / nc for k in range(nc))]
    P += _line((xa, w - ra), (xa, -(w - ra)), na)[:-1]
    P += [(xa + ra + ra * math.cos(a), -(w - ra) + ra * math.sin(a))
          for a in (math.pi + math.pi / 2 * k / nc for k in range(nc))]
    P += _line((xa + ra, -w), (xc - rf, -w), ns)[:-1]
    P += [(xc - rf + rf * math.cos(a), -L + rf * math.sin(a))
          for a in (1.5 * math.pi + math.pi / 2 * k / nc for k in range(nc))]
    P += [(front(-L + L * k / nf), -L + L * k / nf) for k in range(nf)]
    return P


def roof_top_z(y):
    return ROOF["top_z"] - ROOF["crown"] * (y / ROOF["half_width"]) ** 2


def roof_rings(n_brow=10):
    """The roof as rings from the top's centre out over the edge and back under to the underside's centre:
    [[(x, y, z)]], every ring the same length. The first and last are nearly closed (a thin rounded slot)."""
    R = ROOF
    deep = R["half_width"] - 0.05
    top_d = [deep, 2.7, 2.4, 2.0, 1.6, 1.2, 0.85, 0.6, 0.42, 0.32]
    under_d = [0.45, 0.6, 0.85, 1.2, 1.6, 2.0, 2.4, 2.7, deep]
    rings = [[(x, y, roof_top_z(y)) for x, y in roof_outline(d)] for d in top_d]
    for k in range(n_brow + 1):                                # over the edge: a quarter ellipse out, one back under
        phi = math.pi * k / n_brow
        if phi <= math.pi / 2:
            d = R["top_inset"] * (1 - math.sin(phi))
            zf = lambda y, c=math.cos(phi): R["edge_z"] + (roof_top_z(y) - R["edge_z"]) * c
        else:
            d = R["under_inset"] * (1 - math.sin(phi))
            zf = lambda y, c=math.cos(phi): R["edge_z"] + (R["edge_z"] - R["under_z"]) * c
        rings.append([(x, y, zf(y)) for x, y in roof_outline(d)])
    rings += [[(x, y, R["under_z"]) for x, y in roof_outline(d)] for d in under_d]
    return rings


if __name__ == "__main__":
    H.solve_depth()
    loop = saloon_plan()
    glass = sum(1 for p in loop if p[2])
    print(f"saloon: front {SAL['front_x']:.2f} on the centreline, corners at x {SAL['corner'][0]:.2f} y +-{SAL['corner'][1]:.2f}, "
          f"side windows to x {SAL['side_window_aft'][0]:.2f}, aft bulkhead x {SAL['aft'][0]:.2f}; windows "
          f"{SAL['plinth_z']:.2f}..{SAL['window_top_z']:.2f} m; {len(loop)} wall columns, {glass} glazed")
    print(f"roof: x {ROOF['aft_x']:.2f}..{ROOF['front_x']:.2f} ({ROOF['front_x'] - ROOF['aft_x']:.2f} m), "
          f"{2 * ROOF['half_width']:.2f} m wide, top {ROOF['top_z']:.2f} m (the mast's foot), edge {ROOF['edge_z']:.2f}, "
          f"underside {ROOF['under_z']:.2f}; overhang at the centreline {ROOF['front_x'] - SAL['front_x']:.2f} m")
    print(f"decks: camber {DECK['camber']:.2f}, {len(DECK['hatches'])} hatches a hull, sheer at the saloon's front "
          f"{H.sheer_z(SAL['corner'][0]):.3f}")
