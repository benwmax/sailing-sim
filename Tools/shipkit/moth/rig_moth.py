"""The moth's rig from rig_moth.json: pure geometry, no Blender (docs/moth-5).

Frame: Blender's (x forward, y to PORT, z up, metres, z = 0 the design waterline at rest); hull_moth.STATE must be
solved first. The sail is drawn on the centreline, sheeted in, with a little camber to port (the game's sail is the
physics' cloth, FSailCloth: this one is for the showroom and the light copy).
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "rig_moth.json")))


def _h():
    import hull_moth as H
    return H


def mast_axis():
    """(base point, unit direction up the mast)."""
    H = _h()
    m = R["mast"]
    base = np.array([m["step_x"], 0.0, H.sheer_z(m["step_x"]) + H.SEC["deck_crown_m"] + m["step_above_deck_m"]])
    a = math.radians(m["rake_deg"])
    return base, np.array([-math.sin(a), 0.0, math.cos(a)])


def mast_point(s):
    base, d = mast_axis()
    return base + d * s


def mast_rings(n=40, sides=14):
    """The mast's section along its length: a teardrop, chord along the boat (perpendicular to the mast axis in the
    xz plane), tapering from base to top."""
    m = R["mast"]
    base, d = mast_axis()
    fwd = np.array([d[2], 0.0, -d[0]])           # perpendicular to the mast, pointing forward
    side = np.array([0.0, 1.0, 0.0])
    rings = []
    for s in np.linspace(0.0, m["length_m"], n):
        u = s / m["length_m"]
        c = m["chord_base_m"] + (m["chord_top_m"] - m["chord_base_m"]) * u ** 1.3
        w = c * m["width_ratio"]
        ring = []
        for k in range(sides):
            t = 2 * math.pi * k / sides
            # teardrop: round nose forward, tapering tail aft
            x = math.cos(t)
            y = math.sin(t) * (0.5 + 0.5 * (1 + x) / 2) ** 0.8
            ring.append(tuple(base + d * s + fwd * (x * c / 2) + side * (y * w / 2)))
        rings.append(ring)
    return rings


def boom_line():
    m, b = R["mast"], R["boom"]
    H = _h()
    base, d = mast_axis()
    s_goose = b["gooseneck_above_deck_m"] / d[2]
    goose = base + d * s_goose - np.array([d[2], 0, -d[0]]) * (m["chord_base_m"] / 2)
    a = math.radians(b["droop_deg"])
    end = goose + np.array([-math.cos(a), 0.0, -math.sin(a)]) * b["length_m"]
    return goose, end


def sail_outline(roach=None, n=60):
    """The sail's outline in its own plane (the xz plane through the centreline): luff from tack to head along the
    mast's back, leech from the head over the roach to the clew, foot from the clew back to the tack sweeping down to
    the deck. Returns (points, tack, head, clew)."""
    H = _h()
    m, sl = R["mast"], R["sail"]
    roach = sl["roach"] if roach is None else roach
    base, d = mast_axis()
    back = -np.array([d[2], 0, -d[0]]) * (m["chord_base_m"] * 0.45)
    s_tack = sl["foot_tack_above_deck_m"] / d[2]
    tack = base + d * s_tack + back
    head = tack + d * sl["luff_m"]
    goose, clew = boom_line()
    head_aft = head + np.array([-1, 0, 0]) * sl["head_width_m"] * math.cos(math.radians(m["rake_deg"])) \
        + np.array([0, 0, -1]) * sl["head_width_m"] * math.sin(math.radians(m["rake_deg"])) * 0.0
    luff = [tack + (head - tack) * t for t in np.linspace(0, 1, n)]
    # leech: head_aft to clew, bulged aft by the roach (a sine bow, fullest 45% up from the clew)
    leech = []
    chord = clew - head_aft
    normal = np.array([-chord[2], 0.0, chord[0]])
    normal /= np.linalg.norm(normal)
    if normal[0] > 0:
        normal = -normal                          # bulge aft
    L = np.linalg.norm(chord)
    for t in np.linspace(0, 1, n):
        bulge = roach * L * 0.25 * math.sin(math.pi * t) ** 1.2 * (1 + 0.3 * (t - 0.55))
        leech.append(head_aft + chord * t + normal * bulge)
    # foot: clew back to the tack, sweeping down to the deck in front
    foot = []
    for t in np.linspace(0, 1, n):
        p = clew + (tack - clew) * t
        x = p[0]
        deck = H.sheer_z(min(max(x, H.TRANSOM_X), H.STEM_X)) + H.SEC["deck_crown_m"] + sl["foot_tack_above_deck_m"]
        line_z = p[2]
        z = line_z + (deck - line_z) * sl["foot_sweep"] * math.sin(math.pi * min(1.0, t * 1.05)) ** 0.7
        foot.append(np.array([x, 0.0, min(line_z, max(z, deck))]))
    pts = luff + [head_aft] + leech[1:] + foot[1:-1]
    return pts, tack, head, clew


def area(pts):
    return abs(sum(a[0] * b[2] - b[0] * a[2] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def solve_roach():
    """The roach that gives the card's area."""
    target = R["sail"]["area_m2"]
    lo, hi = -0.5, 2.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if area(sail_outline(mid)[0]) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def point_in(poly, x, z):
    inside = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if (a[2] > z) != (b[2] > z) and x < a[0] + (z - a[2]) * (b[0] - a[0]) / (b[2] - a[2]):
            inside = not inside
    return inside


def sail_grid(roach, nu=36, nv=48):
    """A grid over the sail for the mesh: rows across the sail (luff to leech) at heights from the foot to the head,
    each point inside the outline, with camber to port (y) peaking at camber_pos of each row's chord."""
    pts, tack, head, clew = sail_outline(roach)
    sl = R["sail"]
    zs = [p[2] for p in pts]
    z0, z1 = min(zs), max(zs)
    rows = []
    for z in np.linspace(z0 + 0.004, z1 - 0.004, nv):
        xs = []
        for a, b in zip(pts, pts[1:] + pts[:1]):
            if (a[2] - z) * (b[2] - z) < 0:
                xs.append(a[0] + (z - a[2]) * (b[0] - a[0]) / (b[2] - a[2]))
        if len(xs) < 2:
            continue
        xa, xb = max(xs), min(xs)           # luff (forward) and leech (aft)
        c = xa - xb
        row = []
        for u in np.linspace(0, 1, nu):
            x = xa - u * c
            k = sl["camber_pos"]
            f = u / k * (2 - u / k) if u <= k else 1 - ((u - k) / (1 - k)) ** 2
            y = sl["camber"] * c * f
            row.append((float(x), float(y), float(z)))
        rows.append(row)
    return rows


def battens(roach, n=None):
    """Batten lines across the sail at even heights between the boom and the head (top batten nearly at the head)."""
    rows = sail_grid(roach, nu=24, nv=200)
    n = R["sail"]["battens"] if n is None else n
    goose, clew = boom_line()
    zs = [r[0][2] for r in rows]
    out = []
    for i in range(n):
        z = clew[2] + (max(zs) - clew[2]) * (i + 0.6) / (n + 0.1)
        row = min(rows, key=lambda r: abs(r[0][2] - z))
        out.append([(p[0], p[1] + 0.006, p[2]) for p in row[1:-1]])
    return out


def wires():
    """Shrouds and forestay: {name: (a, b)}."""
    import wings_moth as WG
    H = _h()
    m, rg = R["mast"], R["rigging"]
    hounds = mast_point(m["length_m"] - m["hounds_from_top_m"])
    y = WG.W["shroud_y_m"]
    fx = WG.W["root"]["front_x"] + (WG.W["tip"]["front_x"] - WG.W["root"]["front_x"]) * \
        (y - WG.root_y(WG.W["root"]["front_x"])) / (WG.tip_y() - WG.root_y(WG.W["root"]["front_x"]))
    out = {}
    for side, nm in ((1, "L"), (-1, "R")):
        base = np.array([fx, side * y, WG.z_at(fx, y) + 0.016])
        out["Shroud" + nm] = (hounds, base)
    fs = np.array([rg["forestay_tack_x"], 0.0, H.sheer_z(rg["forestay_tack_x"]) + H.SEC["deck_crown_m"]])
    out["Forestay"] = (hounds, fs)
    return out


def sockets(roach):
    m = R["mast"]
    pts, tack, head, clew = sail_outline(roach)
    goose, bend = boom_line()
    w = wires()
    cm = lambda p: [round(float(p[0]) * 100, 2), round(-float(p[1]) * 100, 2), round(float(p[2]) * 100, 2)]  # noqa: E731
    return {"MastBase": cm(mast_point(0.0)), "Masthead": cm(mast_point(m["length_m"])),
            "Hounds": cm(mast_point(m["length_m"] - m["hounds_from_top_m"])),
            "ShroudBase_L": cm(w["ShroudL"][1]), "ShroudBase_R": cm(w["ShroudR"][1]), "ForestayTack": cm(w["Forestay"][1]),
            "Gooseneck": cm(goose), "BoomEnd": cm(bend), "Tack": cm(tack), "Head": cm(head), "Clew": cm(clew)}
