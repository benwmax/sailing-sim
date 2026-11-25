"""The Hobie 16's mast and standing rig (docs/hobie16-5, slice 4) as plain geometry: no Blender, so it can be checked.

    python3 -I rig_hobie16.py          prints where it stands: the rake, the hounds, the wires' lengths as built

rig_hobie16.json holds the sizes and the wires' lengths; platform_hobie16 the step's ball, the sidebars and the bridle
it stands on (call hull_hobie16.solve_depth() first). solve() finds the mast's rake and the hounds' height from the
wires: the forestay (with its pigtail and adjuster) from the bridle plate and the shrouds (with their adjusters) from
the chainplates must both just reach the hounds, and the bridle plate rides where its wires line up with the
forestay (platform_hobie16.layout(hounds)). build() returns the parts as platform_hobie16.Part meshes in Blender's
frame, X forward, Y to PORT, Z up, metres:
  Mast    the extrusion with its luff track, the base casting on the ball, the hounds fitting and the masthead
  Stays   the forestay with its stay adjuster, the two shrouds with theirs and the chainplates at the hulls' deck edges
  Trapeze the four trapeze wires with their rings, handles and shock cords
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
import rudder_hobie16 as RU  # noqa: E402

G = json.load(open(os.path.join(HERE, "rig_hobie16.json")))
Part = PL.Part


def heel():
    """The mast's heel: the top of the step's ball (platform_hobie16.report's mast_step_ball_top)."""
    L = PL.layout()
    M, fc = PL.P["mast_step"], PL.P["front_crossbar"]
    z = L["zf"] + fc["height_m"] / 2 + M["plate_m"][2] - 0.004 + M["pedestal_height_m"] - 0.006 + 2 * M["ball_radius_m"]
    return np.array([L["fx"], 0.0, z])


def chainplate(side):
    """The shroud's pin on its chainplate, side +1 port, -1 starboard: on the hull's outboard side at the deck edge
    (rig_hobie16.json chainplate), the pin chainplate.over_deck_m over the deck there."""
    C = G["chainplate"]
    x = C["x"]
    sec = H.section(x, 96)
    a = H.half_beam(x)
    up = sec[(sec[:, 0] > 0) & (sec[:, 1] > H.max_beam_z(x))]
    up = up[np.argsort(up[:, 0])]
    yo = C["out_share"] * a
    z = float(np.interp(yo, up[:, 0], up[:, 1]))
    return np.array([x, side * (H.CARD["game"]["hull_center_y_m"] + yo), z + C["over_deck_m"]])


def axis(rake):
    """The mast's axis (unit vector) raked aft by `rake` radians."""
    return np.array([-math.sin(rake), 0.0, math.cos(rake)])


def solve():
    """The rake (radians, aft positive), the hounds' distance up the mast from the heel and the bridle plate: Newton on
    the forestay's and the shroud's lengths."""
    W = G["wires"]
    lf = W["forestay_m"] + W["pigtail_m"] + W["forestay_adjuster_m"]
    ls = W["shroud_m"] + W["shroud_adjuster_m"]
    h0, cp = heel(), chainplate(1)

    def resid(u):
        hd = h0 + u[1] * axis(u[0])
        J = np.array(PL.layout((hd[0], hd[2]))["junction"])
        return np.array([np.linalg.norm(hd - J) - lf, np.linalg.norm(hd - cp) - ls])

    u = np.array([0.1, 0.7 * G["mast"]["length_m"]])
    for _ in range(30):
        r = resid(u)
        if np.abs(r).max() < 1e-7:
            break
        Jm = np.zeros((2, 2))
        for k in range(2):
            du = np.zeros(2)
            du[k] = 1e-6
            Jm[:, k] = (resid(u + du) - r) / 1e-6
        u = u - np.linalg.solve(Jm, r)
    hd = h0 + u[1] * axis(u[0])
    return {"rake": float(u[0]), "hounds_along": float(u[1]), "heel": h0, "hounds": hd,
            "junction": np.array(PL.layout((hd[0], hd[2]))["junction"]), "lf": lf, "ls": ls}


def frame(rake):
    """The mast's frame: axis t, across s (to starboard) and forward u, both square to the axis."""
    t = axis(rake)
    return t, np.array([0.0, -1.0, 0.0]), np.array([math.cos(rake), 0.0, math.sin(rake)])


def section(scale=1.0):
    """The mast's section about its turning axis: [(across, forward)] in metres."""
    M = G["mast"]
    c, w = M["chord_m"] * scale, M["width_m"] * scale
    return [(v * c, (M["axis_from_le"] - u) * c) for u, v in RU.naca(w / c, 16)]


def mast_ring(S, along, scale):
    t, s, u = frame(S["rake"])
    o = S["heel"] + along * t
    return np.array([o + a * s + f * u for a, f in section(scale)])


def mast_scale(along):
    M = G["mast"]
    if along <= M["tip_from_m"]:
        return 1.0
    k = (along - M["tip_from_m"]) / (M["length_m"] - M["tip_from_m"])
    return 1.0 + (M["tip_scale"] - 1.0) * k


def oriented_box(part, centre, t, s, u, size, slot):
    """A box along the frame (t, s, u) with extents size (along t, s, u)."""
    c = np.asarray(centre, float)
    h = np.asarray(size, float) / 2
    vs = [c + a * h[0] * t + b * h[1] * s + d * h[2] * u for a, b, d in
          ((-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))]
    i0 = part.add_verts(vs)
    for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        part.face([i0 + k for k in q], slot, flat=True)


def wire(part, a, b, r, slot="Wire", n=6):
    PL.sweep(part, [a, b], PL.circle(r, n), slot, up=_up(a, b))


def _up(a, b):
    d = np.asarray(b, float) - np.asarray(a, float)
    d /= np.linalg.norm(d)
    return (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 0.0, 1.0)


def adjuster(part, a, b, length, slot="Cast"):
    """A stay adjuster: a flat plate `length` long along the wire from its lower end a toward b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = (b - a) / np.linalg.norm(b - a)
    PL.sweep(part, [a, a + length * d], PL.rrect(0.022, 0.005, 0.002, 2), slot, up=_up(a, b))


def build(S=None):
    S = S or solve()
    M, W, T, HD = G["mast"], G["wires"], G["trapeze"], G["hounds"]
    t, s, u = frame(S["rake"])
    mast, stays, trap = Part("Mast"), Part("Stays"), Part("Trapeze")
    L = M["length_m"]

    # the extrusion from the base casting to the head, narrowing into the comptip; the luff track along its back
    a0, a1 = M["base_height_m"] - 0.02, L - M["head_height_m"] + 0.02
    alongs = sorted(set([a0, a1] + list(np.linspace(a0, M["tip_from_m"], 4)) + list(np.linspace(M["tip_from_m"], a1, 6))))
    RU.loft_rings(mast, [mast_ring(S, a, mast_scale(a)) for a in alongs], "Mast")
    back = lambda a: (M["axis_from_le"] - 1.0) * M["chord_m"] * mast_scale(a) - M["track_radius_m"] * 0.4
    path = [S["heel"] + a * t + back(a) * u for a in np.linspace(a0, a1, 8)]
    PL.sweep(mast, path, PL.circle(M["track_radius_m"], 10), "Mast", up=tuple(u))

    # the base casting: a cup over the ball and a block flaring round the extrusion's foot, with its rotation stops
    b = M["base_scale"]
    RU.loft_rings(mast, [mast_ring(S, a, sc) for a, sc in ((0.0, 0.55), (0.012, 0.8), (0.03, b), (M["base_height_m"], b * 0.97),
                                                          (M["base_height_m"] + 0.012, 1.0))], "Cast")
    for side in (1, -1):
        oriented_box(mast, S["heel"] + 0.02 * t + side * 0.06 * s - 0.02 * u, t, s, u, (0.03, 0.03, 0.02), "Cast")

    # the hounds: a cast band with the forestay's tang forward and a tang each side for the shroud and trapezes
    ha = S["hounds_along"]
    sc = mast_scale(ha)
    RU.loft_rings(mast, [mast_ring(S, ha + d, sc * k) for d, k in ((-HD["band_height_m"] / 2 - 0.01, 1.0),
                                                                  (-HD["band_height_m"] / 2, 1.08),
                                                                  (HD["band_height_m"] / 2, 1.08),
                                                                  (HD["band_height_m"] / 2 + 0.01, 1.0))], "Cast")
    fwd = (M["axis_from_le"] * M["chord_m"] * sc * 1.08)
    oriented_box(mast, S["hounds"] + (fwd + HD["tang_out_m"] / 2) * u, t, s, u, (0.05, 0.006, HD["tang_out_m"] + 0.01),
                 "Cast")
    side_w = M["width_m"] * sc * 1.08 / 2
    for side in (1, -1):
        oriented_box(mast, S["hounds"] - 0.01 * t + side * (side_w + HD["tang_out_m"] / 2) * s, t, s, u,
                     (0.05, HD["tang_out_m"] + 0.01, 0.006), "Cast")

    # the masthead: the head casting, its sheave box aft and the halyard's lock
    RU.loft_rings(mast, [mast_ring(S, a, mast_scale(a1) * k) for a, k in ((a1 - 0.02, 1.0), (a1 - 0.01, 1.06),
                                                                          (L - 0.015, 1.06), (L, 0.8))], "Cast")
    aft = (M["axis_from_le"] - 1.0) * M["chord_m"] * mast_scale(a1)
    oriented_box(mast, S["heel"] + (L - 0.05) * t + (aft - 0.03) * u, t, s, u, (0.09, 0.022, 0.06), "Cast")

    # the forestay: hounds tang to the bridle plate, its pigtail's 10-hole stay adjuster at the foot
    top_f = S["hounds"] + (fwd + HD["tang_out_m"]) * u - 0.01 * t
    J = S["junction"] + np.array([0.0, 0.0, 0.03])
    wire(stays, top_f, J + 0.1 * (top_f - J) / np.linalg.norm(top_f - J), W["forestay_radius_m"])
    adjuster(stays, J, top_f, 0.1)

    # the shrouds: the side tangs to the chainplates, each with its 7-hole stay adjuster
    rings = []
    for side in (1, -1):
        tang = S["hounds"] - 0.015 * t - side * (side_w + HD["tang_out_m"]) * s
        cp = chainplate(side)
        wire(stays, tang, cp + 0.09 * (tang - cp) / np.linalg.norm(tang - cp), W["shroud_radius_m"])
        adjuster(stays, cp, tang, 0.09)
        PL.box(stays, cp - np.array([0.0, -side * 0.003, 0.03]), (0.04, 0.006, 0.07), "Cast")

        # two trapeze wires from the same tang, each to its ring, the handle above it, the shock cord to the sidebar
        for rx in T["ring_x_m"]:
            ry = side * T["ring_y_m"]
            d2 = (rx - tang[0]) ** 2 + (ry - tang[1]) ** 2
            rz = tang[2] - math.sqrt(W["trapeze_m"] ** 2 - d2)
            ring_top = np.array([rx, ry, rz])
            dirn = (ring_top - tang) / np.linalg.norm(ring_top - tang)
            wire(trap, tang, ring_top, W["trapeze_radius_m"])
            hc = ring_top - T["handle_above_ring_m"] * dirn
            PL.sweep(trap, [hc - np.array([T["handle_length_m"] / 2, 0, 0]), hc + np.array([T["handle_length_m"] / 2, 0, 0])],
                     PL.circle(0.013, 10), "Handle", up=(0.0, 0.0, 1.0))
            rr = T["ring_radius_m"]
            c = ring_top + np.array([0.0, 0.0, -rr])
            loop = [c + rr * np.array([math.sin(a), 0.0, math.cos(a)]) for a in np.linspace(0, 2 * math.pi, 13)]
            PL.sweep(trap, loop, PL.circle(0.005, 6), "Wire", up=(0.0, 1.0, 0.0), caps=False)
            L2 = PL.layout()
            foot = np.array([rx, side * (L2["yc"] - 0.01), PL.frame_z(L2, rx) + 0.03])
            PL.sweep(trap, [c - np.array([0.0, 0.0, rr]), foot], PL.circle(0.003, 6), "Cord", up=(1.0, 0.0, 0.0))
            rings.append(ring_top)
    S["rings"] = rings
    return [mast, stays, trap], S


def sockets(S):
    """The rig's sockets in the game's frame (Unreal: X forward, Y to STARBOARD, Z up, centimetres): the mast's heel
    and head (what the check measures), the hounds, the forestay's tack and each chainplate. Slice 8 writes the full
    set the game draws from."""
    ue = lambda p: [round(100 * p[0], 2), round(-100 * p[1], 2), round(100 * p[2], 2)]
    L = G["mast"]["length_m"]
    out = {"MastBase": ue(S["heel"]), "Masthead": ue(S["heel"] + L * axis(S["rake"])), "Hounds": ue(S["hounds"]),
           "ForestayTack": ue(S["junction"])}
    for side, tag in ((1, "P"), (-1, "S")):
        out[f"ChainplateUpper_{tag}"] = ue(chainplate(side))
    return {"note": "Slice 4's rig sockets (rig_hobie16.sockets): Unreal's frame, X forward, Y to starboard, Z up, cm.",
            "sockets": out}


def report(S):
    """The numbers the docs and the check read."""
    W, M = G["wires"], G["mast"]
    head = S["heel"] + M["length_m"] * axis(S["rake"])
    tr = RU.layout()
    transom = np.array([tr["ax"] + 0.05, 0.0, tr["transom"][1]])     # the transom's top on the hull's centreline plane
    hy = H.hydrostatics()
    tang = np.array(PL.layout()["tang"])
    dh = float(np.linalg.norm(head - tang))
    zmark = head[2] - math.sqrt(dh * dh - (head[0] - transom[0]) ** 2 - (head[1] - tang[1]) ** 2)
    halyard_in = (tr["transom"][0] - zmark) / 0.0254
    built = lambda a, b: round(float(np.linalg.norm(np.asarray(a) - np.asarray(b))), 3)
    return {"rake_deg": round(math.degrees(S["rake"]), 2), "hounds_along_m": round(S["hounds_along"], 3),
            "hounds_share": round(S["hounds_along"] / M["length_m"], 3), "hounds_z": round(float(S["hounds"][2]), 3),
            "heel": [round(float(v), 3) for v in S["heel"]], "masthead": [round(float(v), 3) for v in head],
            "masthead_z_empty": round(float(head[2]) + hy["crew_sink"], 3),
            "masthead_to_transom_m": built(head, transom),
            "halyard_rake_in": round(float(halyard_in), 1),
            "bridle_plate": [round(float(v), 3) for v in S["junction"]],
            "forestay_pin_to_pin_m": built(S["hounds"], S["junction"]), "forestay_target_m": round(S["lf"], 3),
            "shroud_pin_to_pin_m": built(S["hounds"], chainplate(1)), "shroud_target_m": round(S["ls"], 3),
            "trapeze_ring_z": round(float(S["rings"][0][2]), 3) if S.get("rings") else None,
            "mast_section_m": [M["chord_m"], M["width_m"]]}


if __name__ == "__main__":
    H.solve_depth()
    parts, S = build()
    print(json.dumps(report(S), indent=1))
    print(json.dumps(sockets(S), indent=1))
    for p in parts:
        print(f"{p.name}: {len(p.v)} verts, {p.tris()} triangles")
