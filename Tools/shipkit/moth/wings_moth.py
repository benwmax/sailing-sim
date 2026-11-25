"""The moth's hiking wings from wings_moth.json: pure geometry, no Blender (docs/moth-3).

Each wing is a frame of tubes (front bar, outer rail round two rounded corners, rear bar, and an inner rail along the
hull's deck edge) and a mesh deck inside it. frame(side) returns the tubes' centrelines as lists of (x, y, z) points,
deck(side) a grid of points for the mesh, both in the design-waterline frame (hull_moth.STATE must be solved first:
build_moth.py calls hull_moth.report()). side is +1 for port, -1 for starboard (Blender's y).
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
W = json.load(open(os.path.join(HERE, "wings_moth.json")))


def _h():
    import hull_moth as H
    return H


def tip_y():
    """The outer rail's centreline: its outside edge on the class's beam."""
    return W["beam_m"] / 2 - W["tube"]["rail_d_m"] / 2


def root_y(x):
    """The hull's deck edge at x (the bars' feet sit on it)."""
    return max(_h().PLAN(x), 0.0) - W["tube"]["inner_d_m"] / 2


def z_at(x, y):
    """Height of the wing's plane: the deck edge at the root, rising by the dihedral outboard."""
    H = _h()
    rx = min(max(x, W["root"]["rear_x"]), W["root"]["front_x"])
    z0 = H.sheer_z(rx) + W["tube"]["inner_d_m"] / 2
    return z0 + (y - root_y(rx)) * math.tan(math.radians(W["dihedral_deg"]))


def outline(n_corner=8):
    """The frame's outline in plan (x, y), port side: root front, out the front bar, round the front corner, along the
    outer rail, round the rear corner, back along the rear bar to the root."""
    rf, rr = W["root"]["front_x"], W["root"]["rear_x"]
    tf, tr = W["tip"]["front_x"], W["tip"]["rear_x"]
    r = W["tip"]["corner_r_m"]
    yt = tip_y()
    a = np.array([rf, root_y(rf)])
    b = np.array([tf, yt])                     # the front corner's sharp point
    c = np.array([tr, yt])                     # the rear corner's
    d = np.array([rr, root_y(rr)])

    def corner(p_prev, p, p_next):
        u = (p_prev - p) / np.linalg.norm(p_prev - p)
        v = (p_next - p) / np.linalg.norm(p_next - p)
        half = math.acos(max(-1.0, min(1.0, float(u @ v)))) / 2
        t = r / math.tan(half)
        s, e = p + u * t, p + v * t
        bis = (u + v) / np.linalg.norm(u + v)
        centre = p + bis * (r / math.sin(half))
        a0 = math.atan2(*(s - centre)[::-1])
        a1 = math.atan2(*(e - centre)[::-1])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        return [centre + r * np.array([math.cos(a0 + da * k / n_corner), math.sin(a0 + da * k / n_corner)])
                for k in range(n_corner + 1)]

    pts = [a] + corner(a, b, c) + corner(b, c, d) + [d]
    return [(float(p[0]), float(p[1])) for p in pts]


def frame(side):
    """{name: [(x, y, z), ...]} tube centrelines for one wing (side +1 port, -1 starboard)."""
    H = _h()
    out = outline()
    tubes = {"Rail": [(x, side * y, z_at(x, y)) for x, y in out]}
    rf, rr = W["root"]["front_x"], W["root"]["rear_x"]
    inner = [(float(x), side * root_y(float(x)), z_at(float(x), root_y(float(x)))) for x in np.linspace(rr, rf, 24)]
    tubes["Inner"] = inner
    # a diagonal brace under the mesh from the front bar's root to the rail's middle, as the photos show
    mid = out[len(out) // 2]
    tubes["Brace"] = [(rf - 0.05, side * root_y(rf - 0.05), z_at(rf - 0.05, root_y(rf - 0.05)) - 0.02),
                      (mid[0], side * mid[1] * 0.98, z_at(mid[0], mid[1] * 0.98) - 0.02)]
    return tubes


def point_in(poly, x, y):
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def deck(side, nx=40, ny=28):
    """The mesh deck: a grid over the wing's plan, points outside the frame (less the inset) pulled onto its edge.
    Returns (rows of (x, y, z) points, rows of inside flags)."""
    out = outline()
    poly = out + [(W["root"]["rear_x"], root_y(W["root"]["rear_x"]))]
    ins = W["mesh"]["inset_m"]
    xs = np.linspace(W["root"]["rear_x"] + ins, W["root"]["front_x"] - ins, nx)
    rows, flags = [], []
    for x in xs:
        y0 = root_y(float(x)) + ins
        # the frame's outer edge at this x: march out until leaving the outline
        y1 = y0
        while y1 < tip_y() and point_in(poly, float(x), y1 + 0.005):
            y1 += 0.005
        y1 = max(y0 + 0.01, y1 - ins)
        row, fl = [], []
        for v in np.linspace(0.0, 1.0, ny):
            y = y0 + (y1 - y0) * v
            u = (x - xs[0]) / (xs[-1] - xs[0])
            sag = W["mesh"]["sag_m"] * math.sin(math.pi * v) * math.sin(math.pi * u)
            row.append((float(x), side * float(y), z_at(float(x), float(y)) - sag))
            fl.append(True)
        rows.append(row)
        flags.append(fl)
    return rows, flags


def plan_area():
    """The wing frame's plan area (one side), m^2."""
    p = outline() + [(W["root"]["rear_x"], root_y(W["root"]["rear_x"]))]
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(p, p[1:] + p[:1]))) / 2
