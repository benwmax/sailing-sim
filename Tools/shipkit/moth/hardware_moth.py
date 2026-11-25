"""The moth's hardware and lines from hardware_moth.json: pure geometry, no Blender (docs/moth-7).

Frame: Blender's (x forward, y to PORT, z up, metres, z = 0 the design waterline at rest); hull_moth.STATE must be
solved first. parts() returns {name: [("tube", points, d, d_end) | ("pod", start, length, d) | ("box", centre, size)]}
for build_moth.py, sockets() the attach points the game needs (Unreal frame, cm).
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
K = json.load(open(os.path.join(HERE, "hardware_moth.json")))


def _mods():
    import hull_moth as H
    import foils_moth as F
    import rig_moth as RG
    return H, F, RG


def _detail():
    import detail_moth as DT
    return DT


def deck_z(x):
    H, _, _ = _mods()
    return H.sheer_z(min(max(x, H.TRANSOM_X), H.STEM_X)) + H.SEC["deck_crown_m"]


def tiller_line():
    """(rudder head, universal joint, grip end) of the tiller and its extension."""
    _, F, _ = _mods()
    _, info = F.geometry()
    t, e = K["tiller"], K["extension"]
    head = np.array([info["x_rudder"], 0.0, info["z_gantry"] + F.F["rudder"]["head_above_gantry_m"]])
    a = math.radians(t["rise_deg"])
    joint = head + np.array([math.cos(a), 0.0, math.sin(a)]) * t["length_m"]
    b, o = math.radians(e["rise_deg"]), math.radians(e["out_deg"])
    end = joint + np.array([math.cos(b) * math.cos(o), math.cos(b) * math.sin(o), math.sin(b)]) * e["length_m"]
    return head, joint, end


def geometry():
    H, F, RG = _mods()
    parts, pts = {}, {}
    head, joint, end = tiller_line()
    t, e = K["tiller"], K["extension"]
    DK = _detail().D
    tdir = (joint - head) / np.linalg.norm(joint - head)
    j = DK["joint"]
    # the tiller, its clamp on the rudder's stock, and the rubber universal joint at its end (docs/moth-9)
    parts["MOTH_Tiller"] = [("tube", [head, joint - tdir * j["length_m"] * 0.5], t["d_m"], t["d_m"] * 0.85),
                            ("tube", [head - tdir * 0.035, head + tdir * 0.03], t["d_m"] + 0.012, t["d_m"] + 0.01)]
    u = (end - joint) / np.linalg.norm(end - joint)
    ujd = joint - tdir * j["length_m"] * 0.5
    parts["MOTH_Tiller"] += [("tube", [ujd, joint, joint + u * j["length_m"] * 0.5], j["d_m"], j["d_m"])]
    for f in (0.2, 0.5, 0.8):
        q = ujd + (joint + u * j["length_m"] * 0.5 - ujd) * f
        parts["MOTH_Tiller"].append(("ring", q, (joint - ujd) if f < 0.5 else u, j["d_m"] / 2, 0.0025))
    grip0 = end - u * e["grip_m"]
    parts["MOTH_TillerExtension"] = [("tube", [joint, grip0], e["d_m"], e["d_end_m"])]
    g = DK["grip"]
    grip = [("tube", [grip0, end], e["grip_d_m"], e["grip_d_m"] * 0.95),
            ("pod", None, None, None)]                                          # the end cap, set below
    for i in range(g["ribs"]):
        q = grip0 + (end - grip0) * (0.12 + 0.76 * i / max(g["ribs"] - 1, 1))
        grip.append(("ring", q, u, e["grip_d_m"] / 2 * 0.98, g["rib_r_m"]))
    grip[1] = ("tube", [end - u * 0.004, end + u * g["cap_m"] * 0.7, end + u * g["cap_m"]], e["grip_d_m"] * 1.05,
               e["grip_d_m"] * 0.88)                                              # a rubber end, rounded by the ring
    grip.append(("ring", end + u * g["cap_m"] * 0.97, u, e["grip_d_m"] * 0.3, e["grip_d_m"] * 0.16))
    parts["MOTH_TwistGrip"] = grip
    # the boom's points
    goose, bend = RG.boom_line()
    ms = K["mainsheet"]
    bpt = goose + (bend - goose) * ms["boom_frac"]
    bblock = bpt - np.array([0, 0, 0.05])
    dblock = np.array([ms["deck_block_x"], 0.0, deck_z(ms["deck_block_x"]) + 0.04])
    ratchet = np.array([ms["ratchet_x"], 0.0, deck_z(ms["ratchet_x"]) + 0.045])
    lines = [("tube", [bblock + np.array([0, 0.012, 0]), dblock + np.array([0, 0.012, 0])], ms["d_m"], None),
             ("tube", [bblock - np.array([0, 0.012, 0]), dblock - np.array([0, 0.012, 0])], ms["d_m"], None),
             ("tube", [dblock + np.array([0.02, 0, 0.0]), ratchet - np.array([0.03, 0, 0])], ms["d_m"], None),
             ("tube", [ratchet + np.array([0.0, 0.0, 0.0]), ratchet + np.array([0.12, 0.10, 0.01]), ratchet + np.array([0.25, 0.26, 0.0])], ms["d_m"], None)]
    fittings = []                       # the blocks are drawn in detail_moth.py (MOTH_Blocks)
    # the vang: mast foot to the boom
    v = K["vang"]
    mb = RG.mast_point(0.0)
    vfoot = np.array([mb[0] + v["deck_fwd_of_mast_m"], 0.0, deck_z(mb[0] + v["deck_fwd_of_mast_m"]) + 0.03])
    vboom = goose + (bend - goose) / np.linalg.norm(bend - goose) * v["boom_from_goose_m"] - np.array([0, 0, 0.03])
    vmid = vfoot + (vboom - vfoot) * 0.55
    for dy in (0.02, -0.02):
        lines.append(("tube", [vfoot + np.array([0, dy, 0]), vmid + np.array([0, dy, 0])], v["d_m"], None))
        lines.append(("tube", [vmid + np.array([0, dy, 0]), vboom + np.array([0, dy, 0])], v["d_m"], None))
    if v.get("ram_d_m"):
        # the vang's strut beside the cascade, mast foot to boom (Milestone B)
        fittings.append(("tube", [vfoot + np.array([0.0, 0.0, 0.01]), vboom], v["ram_d_m"], v["ram_d_m"] * 0.8))
    # the cunningham: tack to the mast foot, then both control tails aft along the deck to the sailor
    _, tack, _, _ = RG.sail_outline(RG.solve_roach())
    cfoot = np.array([mb[0] + 0.05, 0.0, deck_z(mb[0] + 0.05) + 0.02])
    lines.append(("tube", [tack + np.array([-0.01, 0, 0]), cfoot], K["cunningham"]["d_m"], None))
    for dy, src in ((0.02, cfoot), (-0.02, vfoot)):
        lines.append(("tube", [src, np.array([mb[0] - 0.25, dy, deck_z(mb[0] - 0.25) + 0.008]),
                               np.array([ms["ratchet_x"] - 0.15, dy * 3, deck_z(ms["ratchet_x"] - 0.15) + 0.008])],
                      K["cunningham"]["d_m"], None))
    # the fairing on the foredeck round the mast's foot (Milestone B)
    fa = K.get("fairing")
    if fa:
        fittings.append(("pod", np.array([fa["aft_x"], 0.0, deck_z(0.5 * (fa["aft_x"] + fa["fwd_x"])) + fa["d_m"] / 2 - fa["sink_m"]]),
                         fa["fwd_x"] - fa["aft_x"], fa["d_m"]))
    # the mast's step collar
    r = K["ram"]
    fittings.append(("tube", [mb - np.array([0, 0, 0.01]), mb + np.array([0, 0, r["h_m"]])], r["d_m"], r["d_m"] * 0.9))
    # the wand's pushrod along the deck to the strut head, and the adjusters
    _, info = F.geometry()
    piv = np.array(info["wand_pivot"])
    sx = F.F["strut"]["x_quarter_chord"]
    hc, hs = _detail().strut_housing()
    shead = hc + np.array([hs[0] / 2, 0.0, 0.0])                       # into the bellcrank's housing (docs/moth-9)
    rod = [_detail().lever_end()]
    for x in np.linspace(piv[0] - 0.15, sx + 0.12, 8):
        rod.append(np.array([x, 0.0, deck_z(x) + 0.022]))
    rod.append(shead)
    fittings.append(("tube", rod, K["pushrod"]["d_m"], None))
    parts["MOTH_Fittings"] = fittings
    parts["MOTH_Lines"] = lines
    pts.update({"TillerJoint": joint, "TwistGrip": end, "MainsheetBoom": bblock, "MainsheetDeck": dblock,
                "MainsheetRatchet": ratchet, "VangBoom": vboom, "VangMid": vmid, "VangDeck": vfoot, "Cunningham": cfoot,
                "PushrodStrut": shead})
    return parts, pts


def sockets():
    _, pts = geometry()
    cm = lambda p: [round(float(p[0]) * 100, 2), round(-float(p[1]) * 100, 2), round(float(p[2]) * 100, 2)]  # noqa: E731
    return {k: cm(v) for k, v in pts.items() if k != "VangMid"}         # VangMid only places the vang's block
