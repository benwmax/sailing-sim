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


def horizontal_foil(x_qc, z, span, c_root, c_tip, t_root, t_tip, n_span=24, u0=0.0, u1=1.0, span_frac=1.0):
    """A horizontal wing centred on y = 0: rings across the span (y from -span/2 to +span/2), chord along -x with a
    straight quarter-chord line, thickness along z. u0..u1 keeps only that slice of the chord (the flap is 0.7..1),
    span_frac only the middle of the span. Tips rounded by easing the chord over the last 4%."""
    rings = []
    half = span / 2 * span_frac
    for s in np.linspace(-1.0, 1.0, n_span):
        y = s * half
        a = abs(y) / (span / 2)
        c = c_root + (c_tip - c_root) * a
        t = t_root + (t_tip - t_root) * a
        if a > 0.96:
            c *= math.sqrt(max(1 - ((a - 0.96) / 0.04) ** 2, 0.04))
        le = x_qc + 0.25 * c
        sec = naca(t)
        ring = []
        for u, v in sec:
            uu = u0 + (u1 - u0) * u
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
    parts["MOTH_MainFoil"] = ("loft", horizontal_foil(s["x_quarter_chord"], zf, m["span_m"], m["root_chord_m"],
                                                      m["tip_chord_m"], m["thickness_root"], m["thickness_tip"],
                                                      u1=1.0 - 0.0))
    # the flap is the aft 30% of the middle 82% of the span: drawn as its own part over the same surface, slightly
    # proud so it reads as a separate piece (the foil under it stays whole: the game hides nothing)
    fl = horizontal_foil(s["x_quarter_chord"], zf, m["span_m"], m["root_chord_m"] * 1.004, m["tip_chord_m"] * 1.004,
                         m["thickness_root"] * 1.06, m["thickness_tip"] * 1.06, n_span=18,
                         u0=1.0 - m["flap_chord_frac"], u1=1.0, span_frac=m["flap_span_frac"])
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
    z_rfoot = bottom - r["below_hull_m"]
    parts["MOTH_Rudder"] = ("loft", vertical_foil(x_r, r["chord_m"], r["thickness"], z_g + r["head_above_gantry_m"],
                                                  z_rfoot + 0.008))
    parts["MOTH_RudderHead"] = ("pod", (x_r - 0.03, 0.0, z_g + 0.01), 0.12, 0.05)
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
    tip = (x_piv + L * math.sin(ang), 0.0, z_piv - L * math.cos(ang))
    parts["MOTH_Wand"] = ("tube", tube([(x_piv, 0.0, z_piv), tip]), w["diameter_root_m"], w["diameter_tip_m"])
    pl, pw = w["paddle_m"]
    d = np.array([math.sin(ang), 0.0, -math.cos(ang)])
    a = np.array(tip) - d * pl
    parts["MOTH_WandPaddle"] = ("plate", [tuple(a + np.array([0, pw / 2, 0])), tuple(np.array(tip) + np.array([0, pw / 2, 0])),
                                          tuple(np.array(tip) - np.array([0, pw / 2, 0])), tuple(a - np.array([0, pw / 2, 0]))])
    info.update({"z_main_foil": zf, "z_elevator": z_rfoot, "x_rudder": x_r, "z_gantry": z_g, "wand_pivot": (x_piv, 0, z_piv),
                 "wand_tip": tip, "wand_angle_deg": math.degrees(ang), "flying_water_z": water, "strut_top": z_top,
                 "hull_bottom": bottom})
    return parts, info


def areas():
    """Planform areas (m^2): the main foil (flap included) and the elevator, integrated over the drawn chords."""
    def wing(span, c0, c1):
        ys = np.linspace(0, 1, 401)
        c = c0 + (c1 - c0) * ys
        c = np.where(ys > 0.96, c * np.sqrt(np.clip(1 - ((ys - 0.96) / 0.04) ** 2, 0.04, 1)), c)
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
