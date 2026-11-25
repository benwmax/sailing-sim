"""The Hobie 16's hulls from lines_hobie16.json: pure geometry, no Blender (docs/hobie16-2).

One hull, in its own frame: x forward from amidships, y outboard from the hull's centreline, z up from the game's
design waterline (the boat and her two crew, 295 kg). The design is a few curves along her length:

- the keel line, a banana rocker: from its lowest point it rises forward through a long soft forefoot into a stem that
  stands nearly upright at its head, and aft as a power curve to the transom's foot;
- the deck's top over the keel's lowest point (the card's floor-to-bow and floor-to-stern heights are drawn in), nearly
  flat;
- the greatest half-breadth at each station.

Each section is two superellipse quarters a face: above the greatest breadth a crowned deck rolling into the topsides,
below it a round-bilged V. The inboard face is drawn to a narrower breadth that runs straighter in plan from the stem to
the transom's corner, and fuller below the greatest breadth, so it stands flatter and more upright than the outboard
face: the asymmetric hull that holds her to windward without boards. Every blend along her length is a
smootherstep, so no line gains a kink from a seam in the design.

section(x) gives the closed section at station x as (y, z) points from the keel up the outboard face, over the deck and
down the inboard face; build_hobie16.py meshes it and hydrostatics() integrates it.

The keel's depth below the design waterline isn't drawn; solve_depth() finds it, so that the two hulls displace the
game's design volume (145 kg of boat and 150 kg of crew in the physics' 1,000 kg/m^3 water). empty_waterline() then
finds where the boat floats without her crew, which gives the empty draft the card's 10 in is compared with.

    python3 -I hull_hobie16.py         prints the hydrostatics and writes nothing
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = json.load(open(os.path.join(HERE, "lines_hobie16.json")))
CARD = json.load(open(os.path.join(HERE, "specs_hobie16.json")))

STEM_X = LINES["ends"]["stem_x"]
TRANSOM_X = LINES["ends"]["transom_x"]
KEEL = LINES["keel"]
SEC = LINES["section"]
WATER_KG_M3 = 1000.0
N_HULLS = 2


def smooth(t):
    """0 to 1 with no step in slope or curvature at either end (smootherstep)."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (6 * t - 15) + 10)


class Spline:
    """Natural cubic spline through (x, y) points, clamped to the end values outside them."""

    def __init__(self, pts):
        self.x = [p[0] for p in pts]
        self.y = [p[1] for p in pts]
        n = len(pts)
        h = [self.x[i + 1] - self.x[i] for i in range(n - 1)]
        m, c, d = [0.0] * n, [0.0] * n, [0.0] * n
        for i in range(1, n - 1):
            r = 6 * ((self.y[i + 1] - self.y[i]) / h[i] - (self.y[i] - self.y[i - 1]) / h[i - 1])
            piv = 2 * (h[i - 1] + h[i]) - h[i - 1] * c[i - 1]
            c[i] = h[i] / piv
            d[i] = (r - h[i - 1] * d[i - 1]) / piv
        for i in range(n - 2, 0, -1):
            m[i] = d[i] - c[i] * m[i + 1]
        self.m = m

    def __call__(self, x):
        xs, ys, m = self.x, self.y, self.m
        x = min(max(x, xs[0]), xs[-1])
        i = 0
        while i < len(xs) - 2 and xs[i + 1] < x:
            i += 1
        h = xs[i + 1] - xs[i]
        a, b = (xs[i + 1] - x) / h, (x - xs[i]) / h
        return a * ys[i] + b * ys[i + 1] + ((a ** 3 - a) * m[i] + (b ** 3 - b) * m[i + 1]) * h * h / 6


TOP = Spline(LINES["top"]["points"])
PLAN = Spline(LINES["plan"]["points"])
DEPTH = [0.30]          # the keel's lowest point below the design waterline: solved by solve_depth()


def z_lowest():
    return -DEPTH[0]


def keel_z(x):
    """Height of the keel at x: the banana rocker (lines_hobie16.json "keel")."""
    lo = KEEL["lowest_x"]
    if x >= lo:
        u = min((x - lo) / (STEM_X - lo), 1.0)
        rise = TOP(STEM_X) * (1 - (1 - u ** KEEL["forefoot_power"]) ** (1 / KEEL["stem_power"]))
    else:
        u = min((lo - x) / (lo - TRANSOM_X), 1.0)
        rise = KEEL["transom_foot_above_lowest_m"] * u ** KEEL["run_power"]
    return z_lowest() + rise


def top_z(x):
    """The deck's top on the hull's centreline at x."""
    return z_lowest() + TOP(x)


def half_beam(x):
    return max(PLAN(x), 0.0)


def inboard_plan(x):
    """The inboard face's half-breadth: the outboard's pulled toward the straight line from the stem to the transom's
    corner (inboard_flat)."""
    a = half_beam(x)
    line = half_beam(TRANSOM_X) * (STEM_X - x) / (STEM_X - TRANSOM_X)
    k = SEC["inboard_flat"]
    return (1 - k) * a + k * min(line, a)


def bottom_power(x):
    """The bottom's superellipse power across the breadth: the mid value, finer (lower: more V) toward the stem and
    fuller toward the transom."""
    p, pb, ps = SEC["bottom_power_y"], SEC["bow_bottom_power_y"], SEC["stern_bottom_power_y"]
    if x >= 0:
        return p + (pb - p) * float(smooth(x / STEM_X))
    return p + (ps - p) * float(smooth(x / TRANSOM_X))


def max_beam_z(x):
    """Height of the greatest breadth: max_beam_below_top under the deck's top, closer to it where the hull is
    shallow at its ends (a soft minimum with 0.35 of the depth, so the line has no corner where they cross)."""
    zt, zk = top_z(x), keel_z(x)
    h = SEC["max_beam_below_top_m"]
    return zt - h * (1 - math.exp(-0.35 * max(zt - zk, 0.0) / h))


def section(x, n=48):
    """The closed section at station x: an (m, 2) array of (y, z), y outboard, from the keel up the outboard face, over
    the deck to the inboard face's top and down it back to the keel (the keel point is not repeated). n points a
    quarter."""
    zk, zt, zm = keel_z(x), top_z(x), max_beam_z(x)
    a = half_beam(x)
    py, pz, pd = bottom_power(x), SEC["bottom_power_z"], SEC["deck_power"]
    th = np.linspace(0.0, math.pi / 2, n + 1)
    # outboard, keel to the greatest breadth (round-bilged V)
    yb = a * np.sin(th) ** (2 / py)
    zb = zm - (zm - zk) * np.cos(th) ** (2 / pz)
    # outboard, greatest breadth over the deck to the centreline (flat crowned deck)
    yd = a * np.cos(th[1:]) ** (2 / pd)
    zd = zm + (zt - zm) * np.sin(th[1:]) ** (2 / pd)
    y_out = np.concatenate([yb, yd])
    z_out = np.concatenate([zb, zd])
    # inboard: a narrower breadth, straighter in plan (inboard_plan), and a fuller bottom power (inboard_power), so
    # the face below the greatest breadth stands flatter and more upright than the outboard one
    a_in = inboard_plan(x)
    yb_in = a_in * np.sin(th) ** (2 / (py * SEC["inboard_power"]))
    y_in = -np.concatenate([yb_in, a_in * np.cos(th[1:]) ** (2 / pd)])
    # keel -> outboard -> deck centre, then deck centre -> inboard -> just above the keel
    ys = np.concatenate([y_out, y_in[-2:0:-1]])
    zs = np.concatenate([z_out, z_out[-2:0:-1]])
    return np.stack([ys, zs], axis=1)


def clip_area(poly, zcut):
    """Area of the closed polygon below z = zcut, its centroid's y and z (Sutherland-Hodgman against one plane)."""
    out = []
    m = len(poly)
    for i in range(m):
        p, q = poly[i], poly[(i + 1) % m]
        pin, qin = p[1] <= zcut, q[1] <= zcut
        if pin:
            out.append(p)
        if pin != qin:
            t = (zcut - p[1]) / (q[1] - p[1])
            out.append(p + (q - p) * t)
    if len(out) < 3:
        return 0.0, 0.0, 0.0
    pts = np.array(out)
    y, z = pts[:, 0], pts[:, 1]
    y1, z1 = np.roll(y, -1), np.roll(z, -1)
    cr = y * z1 - y1 * z
    area = cr.sum() / 2
    if abs(area) < 1e-12:
        return 0.0, 0.0, 0.0
    cy = ((y + y1) * cr).sum() / (6 * area)
    cz = ((z + z1) * cr).sum() / (6 * area)
    return abs(area), cy, cz


def stations(n):
    """Stations from the transom to the stem, closer together at both ends."""
    t = np.linspace(0.0, 1.0, n)
    t = 0.5 * (0.5 - 0.5 * np.cos(np.pi * t)) + 0.5 * t
    return TRANSOM_X + (STEM_X - TRANSOM_X) * t


def volume_below(zcut=0.0, n=240):
    """Both hulls' volume below zcut, and the centre of buoyancy (x, z) and the waterplane area there."""
    xs = np.linspace(TRANSOM_X, STEM_X, n + 1)
    xm = (xs[:-1] + xs[1:]) / 2
    dx = xs[1] - xs[0]
    vol = mx = mz = 0.0
    for x in xm:
        if keel_z(x) >= zcut:
            continue
        a, _, cz = clip_area(section(x), zcut)
        vol += a * dx
        mx += a * dx * x
        mz += a * dx * cz
    vol *= N_HULLS
    return vol, (mx * N_HULLS / vol if vol else 0.0), (mz * N_HULLS / vol if vol else 0.0)


def breadth_at(x, z):
    """The section's breadth (inboard face to outboard) at height z, 0 where it doesn't reach."""
    p = section(x)
    ys = []
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        if (a[1] - z) * (b[1] - z) <= 0 and a[1] != b[1]:
            ys.append(a[0] + (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]))
    return max(ys) - min(ys) if len(ys) >= 2 else 0.0


def waterline_ends(z=0.0):
    xs = np.linspace(TRANSOM_X, STEM_X, 4001)
    wet = [x for x in xs if keel_z(x) < z]
    return (min(wet), max(wet)) if wet else (0.0, 0.0)


def waterplane(z=0.0, n=200):
    """Both hulls' waterplane area at height z."""
    lo, hi = waterline_ends(z)
    xs = np.linspace(lo, hi, n + 1)
    b = [breadth_at(x, z) for x in (xs[:-1] + xs[1:]) / 2]
    return N_HULLS * sum(b) * (xs[1] - xs[0])


def design_volume():
    g = CARD["game"]
    return (g["hull_rig_kg"] + g["crew_kg"]) / WATER_KG_M3


def solve_depth():
    """The keel's depth below the design waterline that floats boat and crew there (bisection)."""
    want = design_volume()
    lo, hi = 0.15, 0.50
    for d in (lo, hi):
        DEPTH[0] = d
        v = volume_below(0.0, 120)[0]
        if (v < want) != (d == lo):
            raise ValueError(f"solve_depth: depth {d} gives {v:.4f} m^3, so {lo}..{hi} doesn't bracket {want:.4f}")
    for _ in range(36):
        DEPTH[0] = (lo + hi) / 2
        if volume_below(0.0, 120)[0] < want:
            lo = DEPTH[0]
        else:
            hi = DEPTH[0]
    DEPTH[0] = (lo + hi) / 2
    return DEPTH[0]


def empty_waterline():
    """Where the boat floats without her crew (145 kg): the height below the design waterline whose volume is the
    boat's alone (bisection)."""
    want = CARD["game"]["hull_rig_kg"] / WATER_KG_M3
    lo, hi = -DEPTH[0] + 0.01, 0.0
    for _ in range(36):
        z = (lo + hi) / 2
        if volume_below(z, 120)[0] < want:
            lo = z
        else:
            hi = z
    return (lo + hi) / 2


def hydrostatics():
    vol, cbx, cbz = volume_below(0.0)
    wl = waterline_ends(0.0)
    ze = empty_waterline()
    mid = max(np.linspace(wl[0], wl[1], 81), key=lambda x: breadth_at(x, 0.0))
    return {"volume_m3": vol, "cb": [cbx, cbz], "lwl": wl[1] - wl[0], "waterline_x": list(wl),
            "beam_wl_hull": breadth_at(mid, 0.0), "waterplane_m2": waterplane(0.0), "depth": DEPTH[0],
            "empty_z": ze, "crew_sink": -ze, "draft_empty": DEPTH[0] + ze, "lwl_empty": float(np.subtract(*waterline_ends(ze)[::-1])),
            "freeboard_mid": top_z(LINES["keel"]["lowest_x"]), "freeboard_mid_empty": top_z(LINES["keel"]["lowest_x"]) - ze,
            "height_bow": TOP(STEM_X), "height_stern": TOP(TRANSOM_X),
            "transom_height": TOP(TRANSOM_X) - KEEL["transom_foot_above_lowest_m"],
            "transom_foot_z": keel_z(TRANSOM_X)}


if __name__ == "__main__":
    d = solve_depth()
    h = hydrostatics()
    print(f"depth {d:.4f} m, volume {h['volume_m3']:.4f} m^3 (want {design_volume():.4f}), CB x {h['cb'][0]:+.3f} "
          f"z {h['cb'][1]:+.3f}, LWL {h['lwl']:.3f} m ({h['waterline_x'][0]:+.3f}..{h['waterline_x'][1]:+.3f}), "
          f"waterline breadth a hull {h['beam_wl_hull']:.3f} m, waterplane {h['waterplane_m2']:.3f} m^2")
    print(f"empty: floats {h['crew_sink']:.3f} m higher, draft {h['draft_empty']:.3f} m (card 0.254), LWL {h['lwl_empty']:.3f}")
    print(f"deck over the water at the keel's lowest point {h['freeboard_mid']:.3f} m with two crew, {h['freeboard_mid_empty']:.3f} "
          f"empty (the broadside photo: about 0.19 with one); "
          f"transom {h['transom_height']:.3f} m tall, its foot {h['transom_foot_z']:+.3f} m")
    sys.exit(0)
