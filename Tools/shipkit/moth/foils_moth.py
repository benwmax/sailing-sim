"""The moth's foils, gantry and wand from foils_moth.json: pure geometry, no Blender (docs/moth-4).

Every foil is lofted from NACA four-digit symmetric sections (rings of points), every tube is a centreline. Frame:
Blender's (x forward, y to PORT, z up, metres, z = 0 the design waterline at rest); hull_moth.STATE must be solved first
(build_moth.py calls hull_moth.report()). parts() returns what build_moth.py meshes; sockets() the attach points the
game needs (in the game's frame: Unreal's x forward, y to starboard, z up, centimetres); areas() the planform areas the
size check reads.
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "foils_moth.json")))
N_PROFILE = 24          # points a side of each section
TIP = F.get("tips", {"frac": 0.04, "min": 0.2, "rake": 0.0})


def _h():
    import hull_moth as H
    return H


def naca(t, n=N_PROFILE):
    """A closed NACA 00xx section, chord 1 from the leading edge (0) to the trailing edge (1): (u, v) points, upper
    surface from the trailing edge to the leading edge then the lower back, cosine-spaced (fine at the nose)."""
    us = (1 - np.cos(np.linspace(0, math.pi, n))) / 2
    yt = 5 * t * (0.2969 * np.sqrt(us) - 0.1260 * us - 0.3516 * us ** 2 + 0.2843 * us ** 3 - 0.1036 * us ** 4)
    upper = list(zip(us[::-1], yt[::-1]))
    lower = list(zip(us[1:-1], -yt[1:-1]))
    return upper + lower


def hull_bottom():
    H = _h()
    return min(H.keel_z(float(x)) for x in np.linspace(H.TRANSOM_X, H.STEM_X, 400))


def vertical_foil(x_qc, chord, t, z_top, z_bot, n_span=16, y=0.0):
    """A vertical blade (strut or rudder): rings at heights from z_bot to z_top, chord along -x from the leading edge
    (quarter chord at x_qc), thickness along y."""
    rings = []
    for z in np.linspace(z_bot, z_top, n_span):
        le = x_qc + 0.25 * chord
        rings.append([(le - u * chord, y + v * chord, float(z)) for u, v in naca(t)])
    return rings


def tip_chord(a, c_root, c_tip):
    """(chord, how far the leading edge has come back) at a = |y| / half-span: straight taper, then over the last
    TIP["frac"] of the half-span an elliptical tip whose leading edge sweeps back (rake 1: the trailing edge stays
    straight)."""
    c = c_root + (c_tip - c_root) * a
    f = TIP["frac"]
    if a <= 1 - f:
        return c, 0.0
    k = min((a - (1 - f)) / f, 1.0)
    c1 = c * math.sqrt(max(1 - k * k, TIP["min"] ** 2))
    return c1, (c - c1) * TIP["rake"]


def horizontal_foil(x_qc, z, span, c_root, c_tip, t_root, t_tip, n_span=24, u0=0.0, u1=1.0, span_frac=1.0, cut=None):
    """A horizontal wing centred on y = 0: rings across the span (y from -span/2 to +span/2), chord along -x with a
    straight quarter-chord line, thickness along z. u0..u1 keeps only that slice of the chord (the flap is 0.7..1),
    span_frac only the middle of the span; cut = (u, span_frac) stops the chord at u inside that middle part (where the
    flap sits, so its hinge line shows as a gap). Tips by tip_chord()."""
    rings = []
    half = span / 2 * span_frac
    ys = list(np.linspace(-1.0, 1.0, n_span) * half)
    if cut:
        e = span / 2 * cut[1]
        ys = sorted([y for y in ys if abs(abs(y) - e) > 0.004] + [-e - 0.001, -e + 0.001, e - 0.001, e + 0.001])
    for y in ys:
        y = float(y)
        a = abs(y) / (span / 2)
        c, back = tip_chord(a, c_root, c_tip)
        t = t_root + (t_tip - t_root) * a
        le = x_qc + 0.25 * (c_root + (c_tip - c_root) * a) - back
        hi = u1 if not (cut and abs(y) < span / 2 * cut[1]) else min(u1, cut[0])
        sec = naca(t)
        ring = []
        for u, v in sec:
            uu = u0 + (hi - u0) * u
            vv = np.interp(uu, [p[0] for p in sec[:N_PROFILE]][::-1], [p[1] for p in sec[:N_PROFILE]][::-1])
            sign = 1 if v >= 0 else -1
            ring.append((le - uu * c, float(y), z + sign * abs(vv) * c))
        rings.append(ring)
    return rings


def tube(points):
    return [tuple(map(float, p)) for p in points]


def geometry():
    """Every part: {name: ("loft", rings) | ("tube", points, d0, d1) | ("pod", centre, length, d)}, and the numbers
    the report and sockets need."""
    H = _h()
    bottom = hull_bottom()
    s, m, g, r, e, w = F["strut"], F["main_foil"], F["gantry"], F["rudder"], F["elevator"], F["wand"]
    parts, info = {}, {}
    # the main strut and foil
    z_foot = bottom - s["below_hull_m"]
    z_top = H.sheer_z(s["x_quarter_chord"]) + s["top_above_deck_m"]
    parts["MOTH_Strut"] = ("loft", vertical_foil(s["x_quarter_chord"], s["chord_m"], s["thickness"], z_top, z_foot + 0.01))
    zf = z_foot
    gap = m.get("hinge_gap_frac", 0.0)
    cut = (1.0 - m["flap_chord_frac"] - gap / 2, m["flap_span_frac"]) if gap else None
    parts["MOTH_MainFoil"] = ("loft", horizontal_foil(s["x_quarter_chord"], zf, m["span_m"], m["root_chord_m"],
                                                      m["tip_chord_m"], m["thickness_root"], m["thickness_tip"],
                                                      cut=cut))
    # the flap: the aft 30% of the middle 82% of the span, its own part behind a hinge gap (docs/moth-9; before it
    # was drawn over the whole foil, slightly proud)
    grow = 1.0 if gap else 1.004
    fl = horizontal_foil(s["x_quarter_chord"], zf, m["span_m"], m["root_chord_m"] * grow, m["tip_chord_m"] * grow,
                         m["thickness_root"] * (1.0 if gap else 1.06), m["thickness_tip"] * (1.0 if gap else 1.06),
                         n_span=18, u0=1.0 - m["flap_chord_frac"] + gap / 2, u1=1.0, span_frac=m["flap_span_frac"])
    parts["MOTH_Flap"] = ("loft", fl)
    p = F["pod"]
    parts["MOTH_Pod"] = ("pod", (s["x_quarter_chord"] + p["fwd_of_quarter_chord_m"] - p["length_m"] / 2, 0.0, zf),
                         p["length_m"], p["diameter_m"])
    # the gantry and rudder
    x_tr = H.TRANSOM_X
    x_r = x_tr - g["aft_of_transom_m"]
    z_g = H.sheer_z(x_tr) + g["z_at_rudder_above_sheer_m"]
    feet_y = H.PLAN(x_tr) - g["foot_y_m"] * 0
    for side, name in ((1, "MOTH_GantryL"), (-1, "MOTH_GantryR")):
        foot = (x_tr + 0.12, side * (feet_y - 0.025), H.sheer_z(x_tr + 0.12) - 0.01)
        knee = (x_tr - 0.04, side * (feet_y - 0.02), H.sheer_z(x_tr))
        head = (x_r + 0.035, side * 0.022, z_g)
        parts[name] = ("tube", tube([foot, knee, head]), g["tube_d_m"], g["tube_d_m"] * 0.8)
        if g.get("lower_tubes"):
            # the truss's lower member: from the transom's lower corner up to the rudder head (Milestone B)
            lo = (x_tr + 0.01, side * H.PLAN(x_tr) * 0.55, H.keel_z(x_tr) + 0.07)
            parts[name + "Low"] = ("tube", tube([lo, (x_r + 0.04, side * 0.024, z_g - 0.03)]), g["tube_d_m"] * 0.85,
                                   g["tube_d_m"] * 0.7)
    z_rfoot = bottom - r["below_hull_m"]
    parts["MOTH_Rudder"] = ("loft", vertical_foil(x_r, r["chord_m"], r["thickness"], z_g + r["head_above_gantry_m"],
                                                  z_rfoot + 0.008))
    # MOTH_RudderHead (the gantry's end block and gudgeons) is drawn by detail_moth.py (docs/moth-9)
    parts["MOTH_Elevator"] = ("loft", horizontal_foil(x_r, z_rfoot, e["span_m"], e["root_chord_m"], e["tip_chord_m"],
                                                      e["thickness_root"], e["thickness_tip"], n_span=20))
    # the wand on its bow fitting, in the flying pose
    x_piv = H.STEM_X + w["fitting_fwd_of_stem_m"]
    z_piv = H.sheer_z(H.STEM_X) + w["fitting_above_sheer_m"]
    parts["MOTH_BowFitting"] = ("tube", tube([(H.STEM_X - 0.10, 0.0, H.sheer_z(H.STEM_X - 0.1) + 0.012),
                                              (x_piv, 0.0, z_piv)]), 0.022, 0.018)
    water = bottom - F["flying_gap_m"]
    drop = z_piv - water
    L = w["length_m"]
    ang = math.acos(min(1.0, drop / L))          # from straight down, the tip forward
    if w.get("trail") == "aft":
        ang = -ang                               # the paddle trails behind the pivot (Milestone B)
    tip = (x_piv + L * math.sin(ang), 0.0, z_piv - L * math.cos(ang))
    parts["MOTH_Wand"] = ("tube", tube([(x_piv, 0.0, z_piv), tip]), w["diameter_root_m"], w["diameter_tip_m"])
    pl, pw = w["paddle_m"]
    d = np.array([math.sin(ang), 0.0, -math.cos(ang)])
    a = np.array(tip) - d * pl
    # the paddle: a small blade with its lower corners rounded (docs/moth-9), in the plane of the wand and y
    rc = min(pw / 2, pl / 3) * 0.9
    outline = [a + np.array([0, pw / 2, 0])]
    for side, ang0 in ((1, 0.0), (-1, math.pi / 2)):
        cen = np.array(tip) - d * rc + np.array([0, side * (pw / 2 - rc), 0])
        for k in range(7):
            t = ang0 + (math.pi / 2) * k / 6
            outline.append(cen + d * rc * (math.sin(t) if side == 1 else math.cos(t - math.pi / 2)) +
                           np.array([0, rc * (math.cos(t) if side == 1 else -math.sin(t - math.pi / 2)), 0]))
    outline.append(a - np.array([0, pw / 2, 0]))
    parts["MOTH_WandPaddle"] = ("plate", [tuple(map(float, q)) for q in outline])
    info.update({"z_main_foil": zf, "z_elevator": z_rfoot, "x_rudder": x_r, "z_gantry": z_g, "wand_pivot": (x_piv, 0, z_piv),
                 "wand_tip": tip, "wand_angle_deg": math.degrees(ang), "flying_water_z": water, "strut_top": z_top,
                 "hull_bottom": bottom})
    return parts, info


def areas():
    """Planform areas (m^2): the main foil (flap included) and the elevator, integrated over the drawn chords."""
    def wing(span, c0, c1):
        ys = np.linspace(0, 1, 401)
        c = np.array([tip_chord(float(a), c0, c1)[0] for a in ys])
        return float(np.trapezoid(c, ys) * span)
    m, e = F["main_foil"], F["elevator"]
    return {"main_foil_area_m2": wing(m["span_m"], m["root_chord_m"], m["tip_chord_m"]),
            "elevator_area_m2": wing(e["span_m"], e["root_chord_m"], e["tip_chord_m"]),
            "flap_area_m2": wing(m["span_m"] * m["flap_span_frac"], m["root_chord_m"],
                                 m["root_chord_m"] + (m["tip_chord_m"] - m["root_chord_m"]) * m["flap_span_frac"]) * m["flap_chord_frac"]}


def sockets(info):
    """The game's attach points (Unreal frame: x forward, y starboard, z up, cm). Blender's y is to port, so y flips;
    every point here is on the centreline anyway."""
    s, m = F["strut"], F["main_foil"]
    cm = lambda p: [round(p[0] * 100, 2), round(-p[1] * 100, 2), round(p[2] * 100, 2)]  # noqa: E731
    x_flap = s["x_quarter_chord"] + 0.25 * m["root_chord_m"] - (1 - m["flap_chord_frac"]) * m["root_chord_m"]
    return {
        "StrutTop": cm((s["x_quarter_chord"], 0, info["strut_top"])),
        "MainFoilCentre": cm((s["x_quarter_chord"], 0, info["z_main_foil"])),
        "FlapHinge": cm((x_flap, 0, info["z_main_foil"])),
        "RudderPivot": cm((info["x_rudder"], 0, info["z_gantry"])),
        "ElevatorPivot": cm((info["x_rudder"], 0, info["z_elevator"])),
        "WandPivot": cm(info["wand_pivot"]),
        "WandTip": cm(info["wand_tip"]),
    }
