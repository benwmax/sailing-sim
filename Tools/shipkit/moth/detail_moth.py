"""The moth's close-range details from detail_moth.json: pure geometry, no Blender (docs/moth-9).

Frame: Blender's (x forward, y to PORT, z up, metres, z = 0 the design waterline at rest); hull_moth.STATE must be
solved first. geometry() returns {object name: [spec, ...]} where a spec is
    ("tube", points, d, d_end)                    a round tube along a polyline (d_end None: constant)
    ("pod", tail, length, d)                       a slim body of revolution along +x
    ("box", centre, (ex, ey, ez), (sx, sy, sz), bevel)   a box on those unit axes, its edges rounded by bevel
    ("ring", centre, axis, R, r)                   a torus round axis: R to the tube's centre, r the tube's radius
An object that build_moth.py has already made takes the extra geometry (it then moves with that part in the game);
any other is made new with its slot from detail_moth.json's "objects".
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "detail_moth.json")))
X, Y, Z = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])


def _mods():
    import hull_moth as H
    import foils_moth as F
    import rig_moth as RG
    import wings_moth as WG
    import hardware_moth as HW
    return H, F, RG, WG, HW


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def axes(ez, hint):
    """Unit axes (ex, ey, ez): ez given, ex as near hint as it can be."""
    ez = unit(ez)
    ex = unit(np.asarray(hint, float) - ez * float(np.dot(hint, ez)))
    return ex, np.cross(ez, ex), ez


def disc(c, axis, d, t):
    """A short capped cylinder (a nut, a sheave, a cheek) of diameter d and thickness t along axis."""
    a = unit(axis)
    return ("tube", [tuple(c - a * t / 2), tuple(c + a * t / 2)], d, d)


def box(c, ax, size, bevel):
    return ("box", tuple(map(float, c)), tuple(tuple(map(float, a)) for a in ax), tuple(size), bevel)


def ring(c, axis, R, r):
    return ("ring", tuple(map(float, c)), tuple(map(float, unit(axis))), R, r)


# ---- the wand ---------------------------------------------------------------------------------------------------

def wand_frame():
    """(pivot, unit vector down the wand to its tip, unit vector along the carbon arm toward the pivot)."""
    H, F, _, _, _ = _mods()
    _, info = F.geometry()
    p = np.array(info["wand_pivot"], float)
    u = unit(np.array(info["wand_tip"], float) - p)
    arm0 = np.array([H.STEM_X - 0.10, 0.0, H.sheer_z(H.STEM_X - 0.1) + 0.012])
    return p, u, unit(p - arm0), arm0


def lever_end():
    """The top of the wand's lever above the pivot, where the pushrod takes hold."""
    p, u, _, _ = wand_frame()
    return p - u * D["wand_fitting"]["lever_m"]


def wand_parts():
    _, F, _, _, HW = _mods()
    k = D["wand_fitting"]
    w = F.F["wand"]
    p, u, a, arm0 = wand_frame()
    ex, ey, ez = axes(np.cross(a, Y), a)          # ex along the arm, ez up from it
    fit, wand, lines = [], [], []
    hd = k["head"]
    hc = p - a * (hd[0] / 2 - 0.018)                 # the head: a compact housing round the pivot, on the arm's end
    fit.append(box(hc, (ex, Y, ez), hd, 0.008))
    for s_ in (1, -1):                               # the axle's ends standing out of it
        fit.append(disc(p + Y * s_ * (hd[1] / 2 + 0.003), Y, 0.014, 0.006))
    bp = k["base_plate"]
    xb = arm0[0] + 0.03
    fit.append(box((xb, 0.0, HW.deck_z(xb) + bp[2] / 2 - 0.002), (X, Y, Z), bp, 0.003))
    # the ride-height knob on top of the head
    r1 = hc + ez * (hd[2] / 2)
    fit.append(("tube", [tuple(r1 - ez * 0.004), tuple(r1 + ez * 0.008)], k["knob_rod_d_m"] * 2, None))
    fit.append(disc(r1 + ez * (0.008 + k["knob_h_m"] / 2), ez, k["knob_d_m"], k["knob_h_m"]))
    for dz in (0.011, 0.005 + k["knob_h_m"]):
        fit.append(ring(r1 + ez * dz, ez, k["knob_d_m"] / 2, 0.0018))
    # the lever above the pivot (it turns with the wand), the ferrule and the paddle's clamp
    le = lever_end()
    wand.append(("tube", [tuple(p - u * 0.004), tuple(le)], k["lever_d_m"], k["lever_d_m"] * 0.8))
    wand.append(("pod", tuple(le - X * 0.008), 0.016, 0.014))
    L = w["length_m"]
    dw = w["diameter_root_m"] + (w["diameter_tip_m"] - w["diameter_root_m"]) * k["ferrule_at"]
    wand.append(ring(p + u * L * k["ferrule_at"], u, dw / 2 + 0.001, 0.0022))
    # the shock cord: from a horn on the fitting's nose to the wand below the pivot, holding it forward
    horn0 = p + a * (hd[0] / 2 - 0.02)
    nose = p + a * k["horn_m"] - ez * 0.01
    fit.append(("tube", [tuple(horn0), tuple(nose)], 0.01, 0.007))
    on = p + u * k["shock_cord_on_wand_m"]
    lines.append(("tube", [tuple(nose), tuple(0.5 * (nose + on) + a * 0.01), tuple(on)], k["shock_cord_d_m"], None))
    lines.append(ring(on, u, w["diameter_root_m"] / 2 + 0.003, 0.0025))
    return fit, wand, lines


# ---- the main strut's head ----------------------------------------------------------------------------------------

def strut_housing():
    """(centre, size) of the bellcrank's housing on top of the main strut."""
    _, F, _, _, _ = _mods()
    _, info = F.geometry()
    s = F.F["strut"]
    xc = s["x_quarter_chord"] - 0.25 * s["chord_m"] + s["chord_m"] / 2
    h = D["strut_head"]["housing"]
    return np.array([xc, 0.0, info["strut_top"] + h[2] / 2 - 0.012]), h


def strut_parts():
    _, F, _, _, HW = _mods()
    k = D["strut_head"]
    s = F.F["strut"]
    out = []
    xc = s["x_quarter_chord"] - 0.25 * s["chord_m"] + s["chord_m"] / 2
    out.append(box((xc, 0.0, HW.deck_z(xc) + k["flange"][2] / 2 - 0.003), (X, Y, Z), k["flange"], 0.004))
    c, h = strut_housing()
    out.append(box(c, (X, Y, Z), h, 0.008))
    a = math.radians(k["arm_rise_deg"])
    d = np.array([-math.cos(a), 0.0, math.sin(a)])
    root = c + np.array([-h[0] / 2 + 0.015, 0.0, h[2] / 2 - 0.01])
    ex, ez = d, np.cross(d, Y)
    for sgn in (1, -1):                            # the slotted arm: two plates with the slot between them
        out.append(box(root + d * k["arm"][0] / 2 + Y * sgn * (k["arm_gap_m"] / 2 + k["arm"][1] / 2),
                       (ex, Y, ez), k["arm"], 0.0012))
    kn = root + d * k["arm"][0] * 0.55
    out.append(disc(kn, Y, k["knob_d_m"], k["arm_gap_m"] + 2 * k["arm"][1] + 0.016))
    out.append(disc(kn, Y, 0.008, k["arm_gap_m"] + 0.04))
    return out


# ---- the gantry's end and the rudder -------------------------------------------------------------------------------

def rudder_parts():
    _, F, _, _, _ = _mods()
    _, info = F.geometry()
    k = D["rudder_head"]
    xr, zg = info["x_rudder"], info["z_gantry"]
    xp = xr + 0.25 * F.F["rudder"]["chord_m"] + 0.006          # the pin just ahead of the blade's leading edge
    head = [box((xr + 0.06, 0.0, zg - 0.012), (X, Y, Z), k["block"], 0.01)]
    for dz in (k["gudgeon_dz_m"], -k["gudgeon_dz_m"]):
        c = np.array([xp, 0.0, zg + dz])
        head.append(disc(c, Z, k["gudgeon_d_m"], k["gudgeon_h_m"]))
        head.append(box(c + X * 0.02, (X, Y, Z), (0.04, 0.02, k["gudgeon_h_m"] * 0.8), 0.004))   # the gudgeon's web
    head.append(("tube", [(xp, 0.0, zg - k["gudgeon_dz_m"] - 0.02), (xp, 0.0, zg + k["gudgeon_dz_m"] + 0.02)],
                 k["pin_d_m"], None))
    head.append(disc(np.array([xp, 0.0, zg + k["gudgeon_dz_m"] + k["gudgeon_h_m"] / 2 + 0.005]), Z, 0.014, 0.01))
    # the rudder's own stock above the upper gudgeon, and the bulb at its foot where the elevator pivots
    rud = [box((xr - 0.012, 0.0, zg + F.F["rudder"]["head_above_gantry_m"] + 0.004), (X, Y, Z), k["stock"],
               k.get("stock_bevel_m", 0.006))]
    e = D["elevator_pod"]
    rud.append(("pod", (xr + e["fwd_of_quarter_chord_m"] - e["length_m"] / 2, 0.0, info["z_elevator"]),
                e["length_m"], e["diameter_m"]))
    # the gantry's feet: a saddle under each tube's end on the deck and on the transom
    parts, _ = F.geometry()
    H = _mods()[0]
    fs = k["foot"]
    for nm, spec in parts.items():
        if nm.startswith("MOTH_Gantry"):
            f0 = np.array(spec[1][0])
            if nm.endswith("Low"):                   # on the transom's face
                head.append(box((H.TRANSOM_X - 0.002, f0[1], f0[2]), (X, Y, Z), (fs[2], fs[1], fs[0]), 0.005))
            else:                                    # on the deck
                head.append(box(f0 - Z * 0.004, (X, Y, Z), fs, 0.005))
    return head, rud


# ---- the blocks ------------------------------------------------------------------------------------------------------

def block(c, axis, up, d, sheaves=(0.0,)):
    """A block: cheeks, sheaves at the given offsets along its axle, the axle's caps, a shackle toward up."""
    k = D["blocks"]
    a, up = unit(axis), unit(up)
    out = []
    span = (max(sheaves) - min(sheaves)) if len(sheaves) > 1 else 0.0
    w = 0.009                                       # a sheave's width
    edges = sorted({min(sheaves) - w / 2 - k["cheek_t_m"] / 2, max(sheaves) + w / 2 + k["cheek_t_m"] / 2} |
                   ({0.5 * (s0 + s1) for s0, s1 in zip(sorted(sheaves)[:-1], sorted(sheaves)[1:])} if span else set()))
    for e in edges:
        out.append(disc(c + a * e, a, d, k["cheek_t_m"]))
    for s in sheaves:
        out.append(disc(c + a * s, a, d * k["sheave_frac"], w))
    lo, hi = min(edges) - 0.004, max(edges) + 0.004
    out.append(("tube", [tuple(c + a * lo), tuple(c + a * hi)], 0.007, None))
    top = c + up * (d / 2 + k["becket_R_m"] * 0.8)
    out.append(ring(top, np.cross(a, up), k["becket_R_m"], k["becket_r_m"]))
    return out


def block_parts():
    _, _, _, _, HW = _mods()
    _, pts = HW.geometry()
    ms, v = HW.K["mainsheet"], HW.K["vang"]
    k = D["blocks"]
    out = []
    out += block(pts["MainsheetBoom"], Y, Z, ms["block_d_m"], (-0.012, 0.012))
    out += block(pts["MainsheetDeck"], Y, -Z, ms["block_d_m"], (-0.012, 0.012))
    r = pts["MainsheetRatchet"]
    out += block(r + Z * 0.012, Y, -Z, 0.056, (0.0,))
    out.append(box(r - Z * 0.03 + Z * k["ratchet_base"][2] / 2, (X, Y, Z), k["ratchet_base"], 0.004))
    vm, vb, vf = pts["VangMid"], pts["VangBoom"], pts["VangDeck"]
    out += block(vm, Y, vb - vm, 0.03, (-0.02, 0.02))
    out += block(vf + Z * 0.012, Y, -Z, 0.03, (-0.02, 0.02))
    out += block(pts["Cunningham"] + Z * 0.01, Y, -Z, 0.026, (0.0,))
    return out


# ---- the rig's fittings ----------------------------------------------------------------------------------------------

def rig_parts():
    H, _, RG, WG, HW = _mods()
    k = D["rig"]
    m = RG.R["mast"]
    base, dm = RG.mast_axis()
    fwd = np.array([dm[2], 0.0, -dm[0]])
    fit, wires = [], []

    def clamp(s, h, grow=k["clamp_grow"]):
        u = s / m["length_m"]
        c = m["chord_base_m"] + (m["chord_top_m"] - m["chord_base_m"]) * u ** 1.3
        return box(RG.mast_point(s) - fwd * 0.004, (fwd, Y, dm), (c * grow, c * m["width_ratio"] * grow, h), 0.006)

    sp = k["step_plate"]
    fit.append(box((base[0], 0.0, HW.deck_z(base[0]) + sp[2] / 2 - 0.002), (X, Y, Z), sp, 0.004))
    goose, _ = RG.boom_line()
    sg = float(np.dot(goose - base, dm))
    fit.append(clamp(sg, k["clamp_h_m"]))
    fit.append(("tube", [tuple(goose - Y * 0.022), tuple(goose + Y * 0.022)], 0.008, None))     # the gooseneck's pin
    fit.append(clamp(RG.R["spreaders"]["height_m"], 0.06))
    for root, tip in RG.spreaders().values():
        dv = unit(tip - root)
        fit.append(("tube", [tuple(tip - dv * k["spreader_cap"][0]), tuple(tip + dv * 0.006)],
                    k["spreader_cap"][1], k["spreader_cap"][1] * 0.8))
    sh = m["length_m"] - m["hounds_from_top_m"]
    fit.append(clamp(sh, k["hounds_h_m"]))
    top = RG.mast_point(m["length_m"])
    fit.append(("tube", [tuple(top - dm * 0.05), tuple(top + dm * 0.012)], m["chord_top_m"] * 1.05, m["chord_top_m"] * 0.7))
    hounds = RG.mast_point(sh)
    for name, pts in RG.wires().items():
        p0, p1, pe = np.array(pts[0]), np.array(pts[1]), np.array(pts[-1])
        d0, d1 = unit(p1 - p0), unit(pe - np.array(pts[-2]))
        wires.append(("tube", [tuple(p0 + d0 * 0.03), tuple(p0 + d0 * (0.03 + k["swage_m"]))], k["swage_d_m"], k["swage_d_m"] * 0.7))
        wires.append(("tube", [tuple(pe - d1 * (0.035 + k["swage_m"])), tuple(pe - d1 * 0.035)], k["swage_d_m"] * 0.7, k["swage_d_m"]))
        # the tang at the bottom: a strip along the wire down to a shackle on a saddle (shrouds) or a deck plate
        tg = k["tang"]
        ex, ey, ez = axes(d1, Y)
        fit.append(box(pe - d1 * (tg[2] / 2 + 0.004), (ex, ey, ez), tg, 0.0015))
        fit.append(ring(pe - d1 * 0.004, ey, k["shackle_R_m"], k["shackle_r_m"]))
        if name.startswith("Shroud"):
            fit.append(box(pe - Z * 0.016, (X, Y, Z), k["saddle"], 0.006))
        else:
            fit.append(box((pe[0], 0.0, HW.deck_z(pe[0]) + 0.002), (X, Y, Z), (0.05, 0.025, 0.006), 0.0025))
        # the hounds end: a small shackle into the tang
        fit.append(ring(hounds + d0 * 0.018, np.cross(d0, Y) if abs(d0[1]) < 0.9 else X, 0.007, 0.002))
    return fit, wires


# ---- the wings -----------------------------------------------------------------------------------------------------

def wing_parts():
    H, _, _, WG, _ = _mods()
    k = D["wing_sockets"]
    rf, rr = WG.W["root"]["front_x"], WG.W["root"]["rear_x"]
    out = []
    for side in (1, -1):
        for x in (rf, rr):
            y = WG.root_y(x)
            out.append(box((x, side * (y - 0.01), H.sheer_z(x) - 0.004), (X, Y, Z), k["size"], 0.008))
    return out


def lacing():
    """The mesh's lacing round each wing: a zigzag from over the frame's tube to the mesh's edge."""
    _, _, _, WG, _ = _mods()
    k = D["lacing"]
    ins = WG.W["mesh"]["inset_m"]
    out = []
    for side in (1, -1):
        rf, rr = WG.W["root"]["front_x"], WG.W["root"]["rear_x"]
        poly = WG.outline() + [(float(x), WG.root_y(float(x))) for x in np.linspace(rr, rf, 24)[1:-1]]
        P = np.array(poly)
        seg = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1))]
        n = int(seg[-1] / k["pitch_m"])
        pts = []
        cen = P.mean(axis=0)
        for i in range(2 * n):
            s = seg[-1] * i / (2 * n)
            j = min(int(np.searchsorted(seg, s, side="right") - 1), len(P) - 1)
            a, b = P[j], P[(j + 1) % len(P)]
            t = (s - seg[j]) / max(seg[j + 1] - seg[j], 1e-9)
            q = a + (b - a) * t
            tang = unit(b - a)
            nrm = np.array([-tang[1], tang[0]])
            if np.dot(nrm, cen - q) < 0:
                nrm = -nrm
            r = (WG.W["tube"]["rail_d_m"] if j < len(WG.outline()) - 1 else WG.W["tube"]["inner_d_m"]) / 2 + k["d_m"] / 2
            zc = lambda xy: WG.z_at(float(xy[0]), float(xy[1]))      # noqa: E731
            if i % 2 == 0:                          # round the tube: over its top, down its outside, under it
                for off, dz in ((0.35, 1.0), (-1.0, 0.0), (0.0, -1.0), (0.6, -0.8)):
                    xy = q + nrm * r * off
                    pts.append((float(xy[0]), side * float(xy[1]), zc(q) + dz * r))
            else:                                   # the mesh's edge
                xy = q + nrm * ins
                pts.append((float(xy[0]), side * float(xy[1]), zc(xy) - 0.001))
        out.append(("tube", pts + [pts[0]], k["d_m"], None))
    return out


def luff_sleeve():
    """The sail's luff sleeve round the mast from the tack to the head: the mast's teardrop grown a little, its tail
    carried aft into the sail."""
    _, _, RG, _, _ = _mods()
    k = D["luff_sleeve"]
    m = RG.R["mast"]
    base, d = RG.mast_axis()
    fwd = np.array([d[2], 0.0, -d[0]])
    _, tack, head, _ = RG.sail_outline(RG.solve_roach())
    s0, s1 = float(np.dot(tack - base, d)), float(np.dot(head - base, d))
    rings = []
    for s in np.linspace(s0, s1, k["rings"]):
        u = s / m["length_m"]
        c = (m["chord_base_m"] + (m["chord_top_m"] - m["chord_base_m"]) * u ** 1.3) * k["grow"] + k["tail_m"]
        w = (m["chord_base_m"] + (m["chord_top_m"] - m["chord_base_m"]) * u ** 1.3) * m["width_ratio"] * k["grow"]
        ring = []
        for j in range(k["sides"]):
            t = 2 * math.pi * j / k["sides"]
            x = math.cos(t)
            y = math.sin(t) * (0.5 + 0.5 * (1 + x) / 2) ** 0.8
            ring.append(tuple(base + d * s + fwd * (x * c / 2 - k["tail_m"] / 2 + 0.002) + Y * (y * w / 2)))
        rings.append(ring)
    return [("loft", rings)]


def boom_parts():
    _, _, RG, _, _ = _mods()
    goose, end = RG.boom_line()
    b = RG.R["boom"]
    dv = unit(end - goose)
    ex, ey, ez = dv, Y, np.cross(dv, Y)
    out = [box(goose + dv * 0.03, (ex, ey, ez), (0.05, b["d_m"] * 1.1, b["d_m"] * 0.9), 0.005),      # the gooseneck's toggle
           ("tube", [tuple(goose + dv * 0.01 - Z * 0.03), tuple(goose + dv * 0.01 + Z * 0.03)], 0.01, None),
           ("tube", [tuple(end - dv * 0.05), tuple(end + dv * 0.012)], b["d_end_m"] * 1.18, b["d_end_m"] * 0.9),  # end cap
           box(end - dv * 0.02 - ez * (b["d_end_m"] / 2 + 0.006), (ex, ey, ez), (0.05, 0.016, 0.012), 0.003)]   # the clew's car
    return out


def geometry():
    fit, wand, lines = wand_parts()
    head, rud = rudder_parts()
    rfit, wires = rig_parts()
    return {
        "MOTH_WandFitting": fit,
        "MOTH_Wand": wand,
        "MOTH_Lines": lines,
        "MOTH_Fittings": strut_parts(),
        "MOTH_RudderHead": head,
        "MOTH_Rudder": rud,
        "MOTH_Blocks": block_parts(),
        "MOTH_RigFittings": rfit,
        "MOTH_Rigging": wires,
        "MOTH_WingFrame": wing_parts(),
        "MOTH_Lacing": lacing(),
        "MOTH_LuffSleeve": luff_sleeve(),
        "MOTH_Boom": boom_parts(),
    }
