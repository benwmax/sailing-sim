"""The Hobie 16's rudders and steering (docs/hobie16-4, slice 3) as plain geometry: no Blender, so it can be checked.

    python3 -I rudder_hobie16.py          prints the rudders' numbers: draft, wetted blade, crossbar

rudder_hobie16.json holds the sizes; hull_hobie16 the transoms they hang on (call hull_hobie16.solve_depth() first).
build() returns Parts (platform_hobie16.Part: vertices, faces, a material slot a face) in Blender's frame, X forward,
Y to PORT, Z up, metres, each with the origin its object takes in build_hobie16.py:
  Rudder_P, Rudder_S   what turns with each rudder: the upper casting, the tiller arm, the lower casting and the blade.
                       Origin on the pivot line at the waterline, so the game turns the mesh about it.
  Gudgeons             the four gudgeons on the transoms (fixed to the hulls)
  Tiller               the tiller crossbar, its end fittings, the universal joint and the tiller extension
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_hobie16 as H  # noqa: E402
import platform_hobie16 as PL  # noqa: E402

R = json.load(open(os.path.join(HERE, "rudder_hobie16.json")))
CY = H.CARD["game"]["hull_center_y_m"]
N_FOIL = 18          # points a side of the blade's section


def naca(t, n=N_FOIL):
    """A closed symmetric NACA four-digit section of chord 1 and thickness ratio t: (2n-2, 2) points (u aft from the
    leading edge, v across), the trailing edge closed, from the trailing edge over the + side to the leading edge and
    back along the - side."""
    u = 0.5 * (1 - np.cos(np.linspace(0, math.pi, n)))
    v = 5 * t * (0.2969 * np.sqrt(u) - 0.1260 * u - 0.3516 * u ** 2 + 0.2843 * u ** 3 - 0.1036 * u ** 4)
    v[-1] = 0.0
    up = np.stack([u[::-1], v[::-1]], axis=1)          # TE -> LE on +v
    lo = np.stack([u[1:-1], -v[1:-1]], axis=1)         # LE -> TE on -v, the ends not repeated
    return np.concatenate([up, lo])


def blade_rings(B, ax):
    """The blade's sections from its head down to the rounded tip: [(points (m, 3))], in the boat's frame about the
    pivot line x = ax (y added by the caller)."""
    top, tip = B["top_z"], B["tip_z"]
    rake = math.tan(math.radians(B["rake_deg"]))
    t_end = tip + 0.051
    rings = []
    zs = list(np.linspace(top, tip + B["tip_round_m"], 14)) + \
        [tip + B["tip_round_m"] * (1 - math.sin(a)) for a in np.linspace(0.0, math.pi / 2 * 0.92, 7)[1:]]
    for z in zs:
        s = (top - z) / (top - tip)
        chord = B["chord_top_m"] + (B["chord_tip_m"] - B["chord_top_m"]) * s
        thick = B["thickness_tip_m"] + (B["thickness_top_m"] - B["thickness_tip_m"]) * \
            min(max((z - t_end) / B["taper_length_m"], 0.0), 1.0)
        le = ax + B["balance"] * chord - (top - z) * rake   # the leading edge, raking aft down the blade
        d = z - tip
        if d < B["tip_round_m"]:          # the rounded tip: the trailing edge sweeps forward to the leading edge's foot
            f = math.sqrt(max(1 - ((B["tip_round_m"] - d) / B["tip_round_m"]) ** 2, 0.0))
            f = max(f, 0.12)
            anchor = le - B.get("tip_anchor", 0.45) * chord
            chord *= f
            le = anchor + B.get("tip_anchor", 0.45) * chord
            thick *= max(f, 0.5)
        sec = naca(thick / chord)
        rings.append(np.array([(le - u * chord, v * chord, z) for u, v in sec]))
    return rings


def loft_shifted(part, cy, rings, power, slot):
    """platform_hobie16.loft with each ring's own centre x: rings [(cx, half length, half width, z)]."""
    t = np.linspace(0, 2 * math.pi, PL.RING_N, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    ex = 2.0 / power
    out = []
    for cx, a, b, z in rings:
        out.append(part.add_verts([(cx + a * np.sign(ci) * abs(ci) ** ex, cy + b * np.sign(si) * abs(si) ** ex, z)
                                   for ci, si in zip(c, s)]))
    for p, q in zip(out[:-1], out[1:]):
        for j in range(PL.RING_N):
            k = (j + 1) % PL.RING_N
            part.face((p + j, p + k, q + k, q + j), slot)
    part.face([out[0] + j for j in range(PL.RING_N)][::-1], slot, flat=True)
    part.face([out[-1] + j for j in range(PL.RING_N)], slot, flat=True)


def loft_rings(part, rings, slot):
    """Quads between equal rings (closed), the first and last capped."""
    idx = [part.add_verts(r) for r in rings]
    m = len(rings[0])
    for a, b in zip(idx[:-1], idx[1:]):
        for j in range(m):
            k = (j + 1) % m
            part.face((a + j, a + k, b + k, b + j), slot)
    part.face([idx[0] + j for j in range(m)][::-1], slot, flat=True)
    part.face([idx[-1] + j for j in range(m)], slot, flat=True)


def transom_span(y_off):
    """The transom's bottom and top z at y_off from the hull's centre (positive outboard)."""
    p = H.section(float(H.TRANSOM_X), 96)
    zs = []
    for i in range(len(p)):
        q, r = p[i], p[(i + 1) % len(p)]
        if (q[0] - y_off) * (r[0] - y_off) <= 0 and q[0] != r[0]:
            zs.append(q[1] + (r[1] - q[1]) * (y_off - q[0]) / (r[0] - q[0]))
    return min(zs), max(zs)


def layout():
    ax = R["axis"]["x"]
    yr = CY                                   # on the transom's middle (rudder_hobie16.json axis.note_y)
    zb, zt = transom_span(0.0)
    G = R["gudgeons"]
    g_hi, g_lo = zt - G["below_deck_m"], zb + G["above_foot_m"]
    U = R["upper_casting"]
    uc_top = zt + U["top_over_deck_m"]
    uc_bot = g_lo - U["bottom_under_gudgeon_m"]
    T = R["tiller_crossbar"]
    tz = H.top_z(T["x"]) + T["over_deck_m"]
    return {"ax": ax, "yr": yr, "transom": (zb, zt), "gudgeons": (g_lo, g_hi), "uc": (uc_bot, uc_top),
            "tiller_z": tz, "tiller_x": T["x"], "tiller_y": T["length_m"] / 2}


def build():
    L = layout()
    ax, yr = L["ax"], L["yr"]
    U, LC, B, G = R["upper_casting"], R["lower_casting"], R["blade"], R["gudgeons"]
    parts = []
    for s, name in ((1, "Rudder_P"), (-1, "Rudder_S")):
        p = PL.Part(name)
        y = s * yr
        ub, ut = L["uc"]
        # the upper casting: a tall rounded body aft of the pivot line, the pintles' line just inside its front face
        cx = ax - U["half_length_m"] + 0.012
        hl, hw = U["half_length_m"], U["half_width_m"]
        PL.loft(p, cx, y, [(hl * 0.9, hw * 0.85, ub), (hl, hw, ub + 0.015), (hl, hw, ut - 0.02),
                           (hl * 0.92, hw * 0.92, ut - 0.004), (hl * 0.7, hw * 0.7, ut)], 3.0, "Cast")
        # the tiller arm: from the casting's head forward and inboard to the tiller crossbar's end
        tx, tz, ty = L["tiller_x"], L["tiller_z"], s * L["tiller_y"]
        a0 = np.array([cx, y, ut - 0.02])
        a1 = np.array([tx - 0.02, ty, tz])
        PL.sweep(p, [a0, a1], PL.circle(R["tiller_arm"]["radius_m"], 10), "Arm")     # a straight tube
        # the lower casting round the blade's head, and the kick-up pin through both castings
        top = B["top_z"]
        lcx = ax + B["balance"] * B["chord_top_m"] - 0.5 * B["chord_top_m"]
        lh, lw = LC["half_length_m"], LC["half_width_m"]
        lt = ub + 0.012
        # one cast head: from the upper casting's foot (overlapping it) down round the blade's head
        PL.loft(p, cx, y, [(hl * 0.98, hw * 0.98, lt + 0.02), (hl * 0.98, hw * 0.98, lt - 0.01)], 3.0, "Cast")
        n = 6
        rings_lc = []
        for k in range(n + 1):
            u = k / n
            z = lt - 0.01 - u * (LC["height_m"] - 0.01)
            e = 0.5 - 0.5 * math.cos(math.pi * min(u * 1.6, 1.0))
            ccx = cx + (lcx - cx) * e
            a = hl * 0.98 + (lh - hl * 0.98) * e
            b = hw * 0.98 + (lw - hw * 0.98) * e
            if k == n:
                a, b = a * 0.9, b * 0.8
            rings_lc.append((ccx, a, b, z))
        loft_shifted(p, y, rings_lc, 3.0, "Cast")
        PL.sweep(p, [(ax - 0.02, y - 0.038, ub + 0.01), (ax - 0.02, y + 0.038, ub + 0.01)], PL.circle(0.008, 10), "Cast",
                 up=(1.0, 0.0, 0.0))
        # the blade
        rings = [r + np.array([0.0, y, 0.0]) for r in blade_rings(B, ax)]
        loft_rings(p, rings, "Blade")
        assert top < lt
        parts.append((p, (ax, y, 0.0)))
    # gudgeons on the transoms: a plate on the transom and an eye on the pivot line
    g = PL.Part("Gudgeons")
    pl = G["plate_m"]
    for s in (1, -1):
        for z in L["gudgeons"]:
            PL.box(g, (H.TRANSOM_X - pl[0] / 2 + 0.002, s * yr, z), pl, "Cast")
            PL.box(g, ((H.TRANSOM_X + ax) / 2, s * yr, z), (H.TRANSOM_X - ax + 0.004, 0.02, 0.016), "Cast")
            PL.lathe(g, ax, s * yr, [(G["eye_radius_m"], z - 0.012), (G["eye_radius_m"], z + 0.012)], "Cast", n=16)
    parts.append((g, (0.0, 0.0, 0.0)))
    # the tiller crossbar, its end fittings, the universal joint and the extension
    t = PL.Part("Tiller")
    T, E = R["tiller_crossbar"], R["tiller_extension"]
    tx, tz, ty = L["tiller_x"], L["tiller_z"], L["tiller_y"]
    PL.sweep(t, [(tx, -ty, tz), (tx, ty, tz)], PL.circle(T["radius_m"], 12), "Arm")
    for s in (1, -1):
        PL.lathe(t, tx - 0.01, s * ty, [(0.0, tz - 0.026), (0.02, tz - 0.024), (0.022, tz + 0.018), (0.0, tz + 0.022)],
                 "Corner", n=14)
    PL.box(t, (tx + 0.01, 0.0, tz + 0.012), (0.05, 0.035, 0.03), "Corner")
    rise = math.radians(E["rise_deg"])
    e0 = np.array([tx + 0.03, 0.0, tz + 0.026])
    e1 = e0 + E["length_m"] * np.array([math.cos(rise), 0.0, math.sin(rise)])
    PL.sweep(t, [e0, e1], PL.circle(E["radius_m"], 10), "Extension")
    PL.sweep(t, [e1 - 0.16 * (e1 - e0) / np.linalg.norm(e1 - e0), e1], PL.circle(E["radius_m"] * 1.35, 12), "Corner")
    parts.append((t, (0.0, 0.0, 0.0)))
    return parts, L


def blade_area_below(z_cut, n=200):
    """The blade's lateral area under z_cut (the water) from its sections' chords."""
    B = R["blade"]
    zs = np.linspace(B["tip_z"], min(z_cut, B["top_z"]), n)
    rings = blade_rings(B, 0.0)
    rz = np.array([r[0, 2] for r in rings])
    rc = np.array([r[:, 0].max() - r[:, 0].min() for r in rings])
    order = np.argsort(rz)
    trap = getattr(np, "trapezoid", None) or np.trapz        # numpy 2 renamed it
    return float(trap(np.interp(zs, rz[order], rc[order]), zs))


def report(L):
    hy = H.hydrostatics()
    B = R["blade"]
    ze = hy["empty_z"]
    return {"rudder_pivot": [L["ax"], round(L["yr"], 3)], "blade_tip_z": B["tip_z"],
            "draft_rudders_down_m": round(ze - B["tip_z"], 3), "draft_rudders_down_crew_m": round(-B["tip_z"], 3),
            "blade_area_wet_m2": round(blade_area_below(0.0), 4),
            "blade_area_wet_empty_m2": round(blade_area_below(ze), 4),
            "tiller_crossbar": [L["tiller_x"], round(2 * L["tiller_y"], 3), round(L["tiller_z"], 3)],
            "transom_z": [round(v, 3) for v in L["transom"]], "gudgeons_z": [round(v, 3) for v in L["gudgeons"]]}


if __name__ == "__main__":
    H.solve_depth()
    parts, L = build()
    print(json.dumps(report(L), indent=1))
    for p, o in parts:
        print(f"{p.name}: {len(p.v)} verts, {p.tris()} triangles, origin {o}")
