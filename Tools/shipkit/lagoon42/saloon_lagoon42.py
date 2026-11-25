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
import bridgedeck_lagoon42 as B  # noqa: E402
import hull_lagoon42 as H  # noqa: E402

SD = json.load(open(os.path.join(HERE, "saloon_lagoon42.json")))
SAL, ROOF, DECK = SD["saloon"], SD["roof"], SD["deck"]
SOLE_Z = json.load(open(os.path.join(HERE, "cockpit_lagoon42.json")))["sole"]["z"]
WALL_TOP = ROOF["under_z"] + 0.04            # the front and sides' lean is reached here (the lip's underside + 4 cm)
WINDOW, DOOR = 1, 2                          # a wall column's glazing: the window band, or the door from the sole up


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
    [(x, y, glazing)], glazing telling what the wall from this point to the next is: 0 white, WINDOW glass between
    the plinth and the windows' top, DOOR glass from the floor up as well (the aft bulkhead's sliding door)."""
    fx, (cx, cy), r = SAL["front_x"], SAL["corner"], SAL["corner_round"]
    swa, aft = SAL["side_window_aft"], SAL["aft"]
    front_x = lambda y: cx + (fx - cx) * (1 - (y / cy) ** 2)
    ya = cy - r * 0.8                                         # the corner's rounding starts here on the front...
    a = (front_x(ya), ya)
    d = math.hypot(swa[0] - cx, swa[1] - cy)
    b = (cx + (swa[0] - cx) * r / d, cy + (swa[1] - cy) * r / d)   # ...and ends here on the side
    pts = [(front_x(ya * k / n_front), ya * k / n_front, WINDOW) for k in range(n_front)]
    pts += [(x, y, WINDOW) for x, y in _bezier(a, (cx, cy), b, n_corner)[:-1]]
    pts += [(x, y, WINDOW) for x, y in _line(b, swa, n_side)[:-1]]
    pts += [(x, y, 0) for x, y in _line(swa, aft, n_back)[:-1]]
    pts += [(aft[0], y, glazing_aft(y)) for y in aft_ys(n_aft)]
    return pts


def cockpit_edge(x):
    """Where the cockpit ends at station x: 5 mm into the hull's inboard topsides at the sole and at the sheer (they
    lean inboard as they rise, so the sole's is the wider), so what stands on the sole and against the hull meets it
    without a gap."""
    return max(B.span(x, SOLE_Z), B.deck_span(x)) + 0.005


def aft_ys(n):
    """The aft bulkhead's columns from its outboard corner to the centreline, through the cockpit's edge (the wall's
    foot drops from the deck to the sole there, between two columns 5 mm apart) and the glass and door edges."""
    y0, ye = SAL["aft"][1], cockpit_edge(SAL["aft"][0])
    keys = sorted({y0, ye, ye - 0.005, SAL["door_half_width"], SAL["sliding_door_half_width"], 0.0}, reverse=True)
    ys = []
    for a, b in zip(keys[:-1], keys[1:]):
        k = max(1, round((a - b) / (y0 / n)))
        ys += [a + (b - a) * i / k for i in range(k)]
    return ys + [0.0]


def glazing_aft(y):
    """The aft bulkhead's wall from y to the next column inboard: the door, the window band or white."""
    y = abs(y)
    return DOOR if y < SAL["sliding_door_half_width"] + 1e-6 else WINDOW if y < SAL["door_half_width"] + 1e-6 else 0


def saloon_plan():
    """The whole saloon's plan as one closed loop [(x, y, glazing)]: the front's centre, the starboard side, the aft
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


def wall_point(x, y, n, z):
    """A wall point over plan point (x, y) at height z, leaning in above the plinth by the wall's facing n: the front
    (facing forward) aft by rake_front, the sides in by tumblehome, all of it reached at WALL_TOP and none above it
    (the aft bulkhead stands upright)."""
    h = min(max(0.0, (z - SAL["plinth_z"]) / (WALL_TOP - SAL["plinth_z"])), 1.0)
    lean = (max(n[0], 0.0) * SAL["rake_front"] + abs(n[1]) * SAL["tumblehome"]) * h
    return (x - n[0] * lean, y - n[1] * lean, z)


def over_cockpit(x, y):
    """Whether a plan point of the aft bulkhead stands on the cockpit sole rather than a hull's deck."""
    return x <= SAL["aft"][0] + 1e-6 and abs(y) < cockpit_edge(x) - 1e-4


def wall_rows():
    """The walls as rows round the loop: the foot (3 cm under the deck, or under the cockpit sole on the aft
    bulkhead between the hulls), the plinth, the glass's top (higher on the aft bulkhead, under the cockpit's
    ceiling) and the top, 4 cm up into the roof's underside wherever it is over the wall. And the loop's glazing."""
    loop = saloon_plan()
    ns = _normals(loop)
    rows = [[], [], [], []]
    for (x, y, _), n in zip(loop, ns):
        aft = x <= SAL["aft"][0] + 1e-6
        base = (SOLE_Z if over_cockpit(x, y) else H.sheer_z(x)) - 0.03
        glass = SAL["aft_glass_top_z"] if aft else SAL["window_top_z"]
        rows[0].append((x, y, base))
        rows[1].append(wall_point(x, y, n, SAL["plinth_z"]))
        rows[2].append(wall_point(x, y, n, glass))
        tx, ty, _ = wall_point(x, y, n, WALL_TOP)
        rows[3].append((tx, ty, max(roof_under_z(tx, ty), glass + 0.05) + 0.04))
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


def _smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lip_t(x):
    """1 where the roof's lip is at its deepest (over the saloon, forward of lip_x[1]), 0 over the cockpit."""
    a, b = ROOF["lip_x"]
    return _smooth((x - a) / (b - a))


def edge_at(x):
    """The roof's outermost line's height at station x."""
    return ROOF["edge_z_aft"] + (ROOF["edge_z"] - ROOF["edge_z_aft"]) * lip_t(x)


def lip_at(x):
    """The underside of the roof's lip at station x."""
    return ROOF["under_z_aft"] + (ROOF["under_z"] - ROOF["under_z_aft"]) * lip_t(x)


def ceiling_z(y):
    """The roof's underside inside the lip and the cove: the top less the roof's thickness."""
    return roof_top_z(y) - ROOF["thickness"]


def under_at(x, y, d):
    """The roof's underside at plan point (x, y), d in from its outermost line: the brow's lower curve, the lip, the
    cove rising to the ceiling, the ceiling."""
    ui, lw, cv = ROOF["under_inset"], ROOF["lip_width"], ROOF["cove"]
    e, u = edge_at(x), lip_at(x)
    if d < ui:
        return e - (e - u) * math.sqrt(max(0.0, 1 - (1 - d / ui) ** 2))
    if d <= lw:
        return u
    return u + (ceiling_z(y) - u) * _smooth((d - lw) / cv)


def roof_inset(x, y):
    """How far plan point (x, y) is in from the roof's outermost line (its corners taken square: the walls and posts
    this is asked for are clear of them)."""
    R = ROOF
    xc, L = R["front_x"] - R["bow"], R["half_width"] - R["corner_front"]
    yy = min(abs(y), L)
    front = xc + R["bow"] * (1 - (yy / L) ** 2) ** 2
    return min(front - x, x - R["aft_x"], R["half_width"] - abs(y))


def roof_under_z(x, y):
    return under_at(x, y, roof_inset(x, y))


def roof_rings(n_brow=10):
    """The roof as rings from the top's centre out over the edge and back under to the underside's centre:
    [[(x, y, z)]], every ring the same length. The first and last are nearly closed (a thin rounded slot)."""
    R = ROOF
    deep = R["half_width"] - 0.06                             # the middle rings: a slot 12 cm wide, 1.8 m long
    top_d = [deep, 2.7, 2.4, 2.0, 1.6, 1.2, 0.85, 0.6, 0.42, 0.32]
    lw, cv = R["lip_width"], R["cove"]
    under_d = [0.45, lw] + [lw + cv * k / 5 for k in range(1, 6)] + [1.2, 1.6, 2.0, 2.4, 2.7, deep]
    rings = [[(x, y, roof_top_z(y)) for x, y in roof_outline(d)] for d in top_d]
    for k in range(n_brow + 1):                                # over the edge: a quarter ellipse out, one back under
        phi = math.pi * k / n_brow
        if phi <= math.pi / 2:
            d = R["top_inset"] * (1 - math.sin(phi))
            zf = lambda x, y, c=math.cos(phi): edge_at(x) + (roof_top_z(y) - edge_at(x)) * c
        else:
            d = R["under_inset"] * (1 - math.sin(phi))
            zf = lambda x, y, c=math.cos(phi): edge_at(x) + (edge_at(x) - lip_at(x)) * c
        rings.append([(x, y, zf(x, y)) for x, y in roof_outline(d)])
    rings += [[(x, y, under_at(x, y, d)) for x, y in roof_outline(d)] for d in under_d]
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
