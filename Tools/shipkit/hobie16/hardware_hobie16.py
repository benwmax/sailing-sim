"""The Hobie 16's running rigging and deck hardware (docs/hobie16-7, slice 6) as plain geometry: no Blender.

    python3 -I hardware_hobie16.py          prints where the sheets, blocks and cars land and the lines' lengths

hardware_hobie16.json holds the sizes and their sources. The parts hang on slices 2-5: platform_hobie16 (the crossbars'
tracks, the trampoline, the bridle plate), rig_hobie16 (the mast, hounds and masthead) and sails_hobie16 (the tacks,
clews, heads and the boom), so call hull_hobie16.solve_depth() first. Sheeted for upwind on starboard tack, like the
sails. build() returns platform_hobie16.Part meshes in Blender's frame, X forward, Y to PORT, Z up:
  Mainsheet   the traveller car, both mainsheet blocks, the six parts and tail, the traveller line
  JibSheet    the jib cars and their cleats, the working and lazy sheets and the tail between the cars
  Lines       the downhauls, the outhaul, the halyards' tails and the mast base's cleats
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
import rig_hobie16 as RG  # noqa: E402
import sails_hobie16 as SL  # noqa: E402

HW = json.load(open(os.path.join(HERE, "hardware_hobie16.json")))
Part = PL.Part
Z = np.array([0.0, 0.0, 1.0])
Y = np.array([0.0, 1.0, 0.0])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rope(part, pts, r, slot="Line", n=10):
    """A rope along the points (at least two), its frames' `up` the axis least along any of its segments."""
    pts = [np.asarray(p, float) for p in pts]
    segs = [unit(q - p) for p, q in zip(pts[:-1], pts[1:])]
    up = min((np.eye(3)[k] for k in range(3)), key=lambda e: max(abs(float(e @ d)) for d in segs))
    PL.sweep(part, pts, PL.circle(r, n), slot, up=tuple(up))


def sagged(a, b, sag, n=9):
    """Points from a to b hanging `sag` below the straight line at the middle (a parabola, close to a slack rope's)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return [a + (b - a) * t - Z * 4 * sag * t * (1 - t) for t in np.linspace(0, 1, n)]


def smooth(ctrl, iters=3):
    """The control polygon's corners cut (Chaikin), ends kept: a rope's lie, never overshooting its polygon."""
    P = [np.asarray(p, float) for p in ctrl]
    for _ in range(iters):
        Q = [P[0]]
        for p, q in zip(P[:-1], P[1:]):
            Q += [0.75 * p + 0.25 * q, 0.25 * p + 0.75 * q]
        P = Q + [P[-1]]
    return P


# ---- the fittings, each built round its own axes ------------------------------------------------------------------

def basis(axis):
    """Two unit vectors square to `axis` and to each other."""
    a = unit(axis)
    e1 = unit(np.cross(a, Z if abs(a[2]) < 0.9 else np.array([1.0, 0.0, 0.0])))
    return e1, np.cross(a, e1)


def revolve(part, centre, axis, prof, slot, n=20, caps=True):
    """The profile [(radius, height along axis)] turned about `axis` through `centre`; the ends capped flat."""
    c, a = np.asarray(centre, float), unit(axis)
    e1, e2 = basis(a)
    rings = []
    for r, h in prof:
        rings.append(part.add_verts([c + h * a + r * (math.cos(t) * e1 + math.sin(t) * e2)
                                     for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]))
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for j in range(n):
            k = (j + 1) % n
            part.face((r0 + j, r1 + j, r1 + k, r0 + k), slot)
    if caps:
        part.face([rings[0] + j for j in range(n)], slot, flat=True)
        part.face([rings[-1] + j for j in range(n)][::-1], slot, flat=True)


def cylinder(part, a, b, r, slot, n=16):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ln = float(np.linalg.norm(b - a))
    revolve(part, a, b - a, [(r, 0.0), (r, ln)], slot, n)


def loop(part, centre, normal, radius, tube, slot, arc=(0.0, 2 * math.pi), n=16):
    """A round bar bent into a ring (or an arc of one) about `normal`: shackles, eyes, fairleads."""
    e1, e2 = basis(normal)
    ts = np.linspace(arc[0], arc[1], n + (0 if arc[1] - arc[0] >= 2 * math.pi - 1e-6 else 1),
                     endpoint=arc[1] - arc[0] < 2 * math.pi - 1e-6)
    path = [np.asarray(centre, float) + radius * (math.cos(t) * e1 + math.sin(t) * e2) for t in ts]
    closed = arc[1] - arc[0] >= 2 * math.pi - 1e-6
    if closed:
        path.append(path[0])
    PL.sweep(part, path, PL.circle(tube, 8), slot, up=tuple(unit(normal)), caps=not closed)


def plate(part, centre, normal, up, w, h, thick, r, slot):
    """A flat plate `thick` through along `normal`, its rounded outline w across and h along `up`."""
    n = unit(normal)
    c = np.asarray(centre, float)
    PL.sweep(part, [c - thick / 2 * n, c + thick / 2 * n], PL.rrect(w, h, r, 4), slot, up=tuple(unit(up)))


def sheave(part, centre, axle, radius, width, slot="Sheave"):
    """A grooved sheave: its rim round, the groove a rope's bed, the hub proud of its faces."""
    hw = width / 2
    prof = [(0.006, -hw - 0.001), (radius * 0.45, -hw - 0.001), (radius * 0.5, -hw), (radius, -hw),
            (radius, -hw * 0.55), (radius * 0.86, -hw * 0.2), (radius * 0.84, 0.0), (radius * 0.86, hw * 0.2),
            (radius, hw * 0.55), (radius, hw), (radius * 0.5, hw), (radius * 0.45, hw + 0.001), (0.006, hw + 0.001)]
    revolve(part, centre, axle, prof, slot, n=24)


def cam_cleat(part, centre, normal, along, length=0.075, slot="Block"):
    """A cam cleat on its base: two toothed cams on posts either side of the rope's lead, a fairlead ring at the back.
    `normal` is the face it stands on, `along` the way the rope pulls through it."""
    n, t = unit(normal), unit(along)
    s = unit(np.cross(n, t))
    c = np.asarray(centre, float)
    plate(part, c + 0.004 * n, n, t, 0.042, length, 0.008, 0.01, slot)
    teeth = []
    for k in range(25):
        a = -0.9 * math.pi + 1.8 * math.pi * k / 24
        rr = 0.011 if k % 2 == 0 else 0.0085
        teeth.append((rr * math.cos(a), rr * math.sin(a)))
    teeth = np.array(teeth + [(-0.004, -0.003), (-0.004, 0.003)])
    for side in (1, -1):
        cc = c + 0.008 * n + side * 0.0125 * s + 0.006 * t
        cylinder(part, cc, cc + 0.019 * n, 0.003, "Cast", n=10)
        prof = np.array([[px, side * py] for px, py in teeth])
        # the cam: its toothed edge toward the rope (-side across), standing 0.016 off the base
        prof2 = np.stack([-side * prof[:, 1], prof[:, 0]], axis=1)
        PL.sweep(part, [cc + 0.003 * n, cc + 0.017 * n], prof2[::side], slot, up=tuple(t))
    loop(part, c + 0.014 * n - (length / 2 - 0.006) * t, t, 0.009, 0.0025, "Cast", arc=(0.0, math.pi), n=10)


def block_height(radius):
    """A block's cheeks' height for its sheaves' radius."""
    return 2 * radius * 1.12 + 0.03


def head_reach(radius):
    """A block's centre to its shackle's centre (the strap, swivel and shackle block() draws toward the mount)."""
    return block_height(radius) / 2 + 0.040


def block(part, centre, lead, mount, sheaves, radius, width, cam=None, becket=False, slot="Block", axle=Y):
    """A block: `sheaves` grooved sheaves side by side on an `axle` (athwartships by default), cheek plates between and outside
    them, the axle's pins, a swivel and shackle toward `mount` (the fitting it hangs from), a becket opposite when the
    sheet's dead end ties to it, and a cam cleat on an arm toward `cam` (the way the tail leaves) for the lower block."""
    c = np.asarray(centre, float)
    m = unit(mount)
    A = unit(axle)
    gap = 0.003
    span = sheaves * width + (sheaves + 1) * gap
    for k in range(sheaves):
        off = -span / 2 + gap + width / 2 + k * (width + gap)
        sheave(part, c + off * A, A, radius, width)
    w_ch = 2 * radius * 1.12
    h_ch = block_height(radius)
    for k in range(sheaves + 1):
        off = -span / 2 + gap / 2 + k * (width + gap)
        thick = 0.0035 if 0 < k < sheaves else 0.005
        plate(part, c + off * A + 0.012 * m, A, m, w_ch, h_ch, thick, radius * 0.9, slot)
    cylinder(part, c - (span / 2 + 0.004) * A, c + (span / 2 + 0.004) * A, 0.0055, "Cast", n=12)
    for side in (1, -1):
        revolve(part, c + side * (span / 2 + 0.004) * A, side * A, [(0.007, 0.0), (0.007, 0.002), (0.004, 0.003)],
                "Cast", n=12)
    # the head: a strap over the cheeks, a swivel and a shackle toward the mount
    top = c + (h_ch / 2 + 0.012) * m
    plate(part, top - 0.006 * m, m, A, span + 0.01, 0.006, 0.012, 0.003, "Cast")
    cylinder(part, top, top + 0.016 * m, 0.008, "Cast", n=12)
    loop(part, top + 0.016 * m + 0.012 * m, unit(np.cross(m, A)), 0.011, 0.0028, "Cast", arc=(-0.15 * math.pi, 1.15 * math.pi))
    if becket:
        loop(part, c - (h_ch / 2 - 0.004) * m - 0.008 * m, unit(np.cross(m, A)), 0.008, 0.0025, "Cast",
             arc=(0.15 * math.pi + math.pi, 1.85 * math.pi + math.pi))
    if cam is not None:
        f = unit(cam)
        arm0 = c - 0.01 * m + (w_ch / 2) * f
        plate(part, arm0 + 0.02 * f, m, f, 0.03, 0.045, 0.006, 0.006, "Cast")
        cam_cleat(part, arm0 + 0.035 * f - 0.003 * m, -m, f)      # its jaws open away from the mount


def cam_exit(centre, mount, cam, radius):
    """Where the tail leaves the jaws of the cam cleat block() puts on its arm (between the cams, at their far end)."""
    m, f = unit(mount), unit(cam)
    return np.asarray(centre, float) + (radius * 1.12 + 0.0725) * f - 0.025 * m


def car(part, centre, axis, length, width, height, rollers=True, slot="Cast"):
    """A track car: a rounded body `length` along the track (`axis`), its rollers' wheels at each end."""
    c = np.asarray(centre, float)
    ax = unit(axis)
    PL.sweep(part, [c - length / 2 * ax, c + length / 2 * ax], PL.rrect(width, height, min(width, height) * 0.35, 4),
             slot, up=(0.0, 0.0, 1.0))
    if rollers:
        across = unit(np.cross(Z, ax))
        for end in (1, -1):
            w0 = c + end * (length / 2 - 0.012) * ax - height * 0.45 * Z
            revolve(part, w0 - 0.008 * across, across, [(0.004, 0.0), (0.011, 0.001), (0.011, 0.015), (0.004, 0.016)],
                    "Sheave", n=16)


def mast_aft(S, z):
    """The point on the mast's aft face at height z (on its centre plane), a rope's width off it."""
    t, s, u = RG.frame(S["rake"])
    G = RG.G["mast"]
    a = (z - S["heel"][2]) / t[2]
    aft = (1 - G["axis_from_le"]) * G["chord_m"] * RG.mast_scale(a)
    return np.asarray(S["heel"], float) + a * t - (aft + 0.008) * u


def layout(Sv):
    """Where the hardware sits, from the solved sails Sv (sails_hobie16.solve)."""
    S, m, j = Sv["rig"], Sv["main"], Sv["jib"]
    L = PL.layout((S["hounds"][0], S["hounds"][2]))
    fc, rc = PL.P["front_crossbar"], PL.P["rear_crossbar"]
    MS, TR, JS = HW["mainsheet"], HW["traveller"], HW["jib_sheet"]
    B = SL.SA["boom"]
    d = m["foot_dir"]
    boom_under = lambda a: m["tack"] + a * d - (0.05 + B["height_m"] / 2) * Z
    bar_top = L["zr"] + rc["height_m"] / 2
    car = np.array([L["rx"], TR["car_y_m"], bar_top + TR["car"][2] / 2])
    swivel_top = car + (TR["car"][2] / 2 + MS["swivel_m"]) * Z
    # the hanger: the point under the boom the sheet reaches leaning hanger_lead_aft_deg aft of square from the car
    lean = math.tan(math.radians(MS["hanger_lead_aft_deg"]))
    a_h = SL.bisect(lambda a: (car[0] - lean * (boom_under(a)[2] - swivel_top[2])) - boom_under(a)[0], 0.5,
                    SL.SA["main"]["foot_m"])
    hanger = boom_under(a_h)
    Rl, Ru = MS["lower_sheave_radius_m"], MS["upper_sheave_radius_m"]
    lead = unit(hanger - swivel_top)
    # each block's shackle hooks through its fitting: the lower one's through the eye on the traveller's swivel post,
    # the upper one's through the bottom of the boom's bail
    eye = swivel_top + MS["eye_m"] * Z
    lo_c = eye + MS["eye_m"] * Z + head_reach(Rl) * lead
    bail_bottom = hanger - MS["bail_m"] * 0.6 * Z
    up_c = bail_bottom - head_reach(Ru) * lead
    lo_top, up_bot = lo_c + Rl * lead, up_c - Ru * lead
    jtrack_z = L["zf"] + fc["height_m"] / 2 + fc["track_height_m"] / 2
    jx = L["fx"] - fc["track_aft_m"]
    jcar = {side: np.array([jx, side * JS["car_y_m"], jtrack_z + JS["car"][2] / 2]) for side in (1, -1)}
    jclew = j["tack"] + SL.SA["jib"]["foot_m"] * j["foot_dir"]
    mclew = m["tack"] + SL.SA["main"]["foot_m"] * d
    return {"L": L, "S": S, "hanger": hanger, "car": car, "swivel_top": swivel_top, "up_bot": up_bot, "lead": lead,
            "lo_c": lo_c, "up_c": up_c, "eye": eye,
            "lo_top": lo_top, "jcar": jcar, "jclew": jclew, "mclew": mclew, "bar_top": bar_top, "boom_under": boom_under}


def build(Sv=None):
    Sv = Sv or SL.solve()
    K = layout(Sv)
    MS, TR, JS, DH = HW["mainsheet"], HW["traveller"], HW["jib_sheet"], HW["downhauls"]
    L, S = K["L"], K["S"]
    ms, js, ln = Part("Mainsheet"), Part("JibSheet"), Part("Lines")

    # the traveller car on the rear crossbar's track, its swivel post; the line along the crossbar to a cam cleat at
    # each end
    car(ms, K["car"], Y, TR["car"][1], TR["car"][0], TR["car"][2])
    cylinder(ms, K["car"] + TR["car"][2] / 2 * Z, K["swivel_top"], 0.011, "Cast")
    loop(ms, K["car"] + np.array([0.0, 0.0, TR["car"][2] / 2 + 0.006]), Y, 0.012, 0.003, "Cast", arc=(0.0, math.pi))
    for side in (1, -1):
        y_end = side * TR["line_to_y_m"]
        a = K["car"] + np.array([0.0, side * TR["car"][1] / 2, 0.0])
        cl = np.array([K["car"][0], y_end, K["bar_top"]])
        cam_cleat(ms, cl, Z, -side * Y)
        rope(ms, [a, cl + np.array([0.0, -side * 0.03, 0.016]), cl + np.array([0.0, side * 0.05, 0.016]),
                  cl + np.array([0.0, side * 0.09, 0.006])], TR["line_radius_m"])

    # the mainsheet: the lower block (its cam cleat forward) on the swivel, the upper block (with its becket) from the
    # boom's bail, and the six parts between them, each pair off its own sheave's fore and aft sides
    lead = K["lead"]
    Rl, Ru = MS["lower_sheave_radius_m"], MS["upper_sheave_radius_m"]
    W, NS = MS["sheave_width_m"], MS["sheaves"]
    fwd = unit(np.cross(Y, lead))
    # the swivel post's eye, which the lower block's shackle hooks through
    loop(ms, K["eye"], Y, MS["eye_m"], 0.0032, "Cast", n=14)
    block(ms, K["lo_c"], lead, -lead, NS, Rl, W, cam=fwd)
    block(ms, K["up_c"], lead, lead, NS, Ru, W, becket=True)
    # the bail: a strap riveted under the boom, its loop hanging for the upper block's shackle
    hb = K["hanger"]
    rb = MS["bail_m"] * 0.6
    loop(ms, hb, Y, rb, 0.0032, "Cast", arc=(math.pi, 2 * math.pi), n=12)
    X = np.array([1.0, 0.0, 0.0])
    for side in (1, -1):
        foot = hb + side * (rb + 0.008) * X + 0.002 * Z
        plate(ms, foot, Z, X, 0.026, 0.02, 0.004, 0.004, "Cast")
        for r_ in (1, -1):
            cylinder(ms, foot + r_ * 0.007 * Y + 0.002 * Z, foot + r_ * 0.007 * Y + 0.0045 * Z, 0.0035, "Cast", n=10)
    span = NS * W + (NS + 1) * 0.003
    for k in range(NS):
        off = (-span / 2 + 0.003 + W / 2 + k * (W + 0.003)) * Y
        for fa in (1, -1):
            rope(ms, [K["lo_c"] + off + fa * Rl * 0.84 * fwd, K["up_c"] + off + fa * Ru * 0.84 * fwd],
                 MS["rope_radius_m"])
    # the tail: out through the cam's jaws, down to the trampoline and forward along it
    jaw = cam_exit(K["lo_c"], -lead, fwd, Rl)
    tail = [jaw, jaw + 0.06 * fwd]
    x0 = jaw[0] + 0.2
    for k in range(7):
        x = x0 + k * MS["tail_m"] / 6 * 0.8
        y = 0.12 * math.sin(k * 0.9)
        tail.append(np.array([x, y, PL.tramp_top(L, x, y) + MS["rope_radius_m"]]))
    rope(ms, [tail[0]] + smooth(tail[1:], 2), MS["rope_radius_m"])

    # the jib sheet, 2:1 a side and one line: from the becket on one car up to its sheave in the clew's double block,
    # back down round the car's ratchet block and out through the cam above it, across the trampoline to the other
    # car, and the same way up and back to that car's becket. The working (port) side is tight, the lazy side slack.
    clew = K["jclew"]
    Rc, Rj, wj, rj = JS["clew_sheave_radius_m"], JS["car_sheave_radius_m"], JS["sheave_width_m"], JS["rope_radius_m"]
    work = unit(K["jcar"][1] + np.array([0.0, 0.0, 0.12]) - clew)       # the clew block leans toward the working car
    c_axle = unit(np.cross(work, np.array([1.0, 0.0, 0.0])))
    c_axle = c_axle if c_axle[1] > 0 else -c_axle
    cb = clew + (head_reach(Rc) + 0.008) * work
    block(js, cb, work, -work, 2, Rc, wj, axle=c_axle)
    loop(js, clew + 0.008 * work, unit(np.cross(work, c_axle)), 0.009, 0.0028, "Cast", n=12)  # the clew ring
    cspan = 2 * wj + 3 * 0.003
    c_side = unit(np.cross(c_axle, work))
    tails = {}
    for side, cc in K["jcar"].items():
        sheave_off = (side * (cspan / 4 + 0.0015)) * c_axle
        car(js, cc, Y, JS["car"][1], JS["car"][0], JS["car"][2], rollers=False)
        # the plunger that locks the car in the track, and the becket at its inboard end
        knob = cc + np.array([0.0, side * 0.024, JS["car"][2] / 2])
        cylinder(js, knob, knob + 0.012 * Z, 0.005, "Cast", n=12)
        revolve(js, knob + 0.012 * Z, Z, [(0.009, 0.0), (0.009, 0.006), (0.006, 0.009)], "Block", n=14)
        beck = cc + np.array([0.0, -side * 0.028, JS["car"][2] / 2 + 0.008])
        loop(js, beck, np.array([1.0, 0.0, 0.0]), 0.008, 0.0025, "Cast", arc=(0.0, math.pi), n=10)
        # the swivel post and the car's block, its sheave square to the pull, the cam over it toward the trampoline
        post = cc + (JS["car"][2] / 2) * Z
        cylinder(js, post, post + 0.012 * Z, 0.010, "Cast", n=14)
        up = unit(clew + sheave_off - (post + 0.06 * Z))
        hp = np.array([up[0], up[1], 0.0])
        b_axle = unit(np.cross(Z, hp))
        inboard = unit(np.array([-0.35, -side, 0.0]))
        bc = post + 0.012 * Z + (head_reach(Rj) - 0.02) * Z
        block(js, bc, Z, -Z, 1, Rj, wj, cam=inboard, axle=b_axle)
        # the two parts: becket to the clew block's sheave, then its other side down to the car's sheave
        top_c = cb + sheave_off
        p1 = [beck + 0.008 * Z, top_c + Rc * 0.9 * c_side]
        p2 = [top_c - Rc * 0.9 * c_side, bc + Rj * 0.9 * up]
        if side == 1:
            rope(js, p1, rj)
            rope(js, p2, rj)
        else:
            # the lazy side runs from the starboard car to the clew behind the mast, so it bears on the mast's aft
            # face and hangs slack either side of it
            for k, (s0, s1) in enumerate((p1, p2)):
                h = (s0[2] + s1[2]) / 2 - 0.08
                mp = mast_aft(S, h) + (k - 0.5) * 0.012 * Y
                rope(js, sagged(s0, mp, JS["lazy_sag_m"] * 0.15, 7)[:-1] + sagged(mp, s1, JS["lazy_sag_m"] * 0.35, 7), rj)
        tails[side] = (cam_exit(bc, -Z, inboard, Rj), inboard)
    # the tail across the trampoline: off each cam, down onto the trampoline aft of the front crossbar, a loose bight
    # between them
    (a, da), (b, db) = tails[1], tails[-1]
    x_on = L["fx"] - JS["tail_on_tramp_aft_m"]
    fc = PL.P["front_crossbar"]
    x_edge, z_edge = L["fx"] - fc["width_m"] / 2, L["zf"] + fc["height_m"] / 2 + rj + 0.004
    x_off = min(x_edge, a[0] - 0.04)
    ctrl = [a, a + 0.05 * da, np.array([x_off, a[1] * 0.82, z_edge]), np.array([x_on, a[1] * 0.6, 0.0]),
            np.array([x_on - JS["tail_aft_m"], 0.0, 0.0]),
            np.array([x_on, b[1] * 0.6, 0.0]), np.array([x_off, b[1] * 0.82, z_edge]), b + 0.05 * db, b]
    for c_ in ctrl:
        if c_[2] == 0.0:
            c_[2] = PL.tramp_top(L, c_[0], c_[1]) + rj
    out = []
    for p in smooth(ctrl, 3):
        out.append(np.array([p[0], p[1], max(p[2], PL.tramp_top(L, p[0], p[1]) + rj)]))
    rope(js, out, rj)

    # the jib's tack downhaul to the bridle plate
    r = DH["rope_radius_m"]
    jt = Sv["jib"]["tack"]
    J = np.array(S["junction"]) + np.array([0.0, 0.0, 0.03])
    for k in range(DH["jib_parts"]):
        off = (k - (DH["jib_parts"] - 1) / 2) * 0.012 * Y
        rope(ln, [jt + off, J + off], r)

    # the main's downhaul from the gooseneck's ring to its cleat on the mast base; the base's cleats
    t, s, u = RG.frame(S["rake"])
    tack = Sv["main"]["tack"]
    HL = HW["halyards"]
    G = RG.G["mast"]
    base_cleat = {side: S["heel"] + HL["cleat_along_m"] * t + side * (G["width_m"] / 2 + 0.012) * s for side in (1, -1)}
    for side, c in base_cleat.items():
        cam_cleat(ln, c - side * 0.012 * s, side * s, -t)
    for k in range(DH["main_parts"]):
        off = (k - 0.5) * 0.012 * s
        rope(ln, [tack + off - 0.03 * t, base_cleat[-1] + off * 0.5 + 0.03 * t], r)

    # the outhaul from the clew along the boom to its cleat near the end
    clew = K["mclew"]
    d = Sv["main"]["foot_dir"]
    OH = HW["outhaul"]
    rope(ln, [clew, clew - 0.03 * Z + 0.06 * d, K["boom_under"](SL.SA["main"]["foot_m"] - 0.25) + 0.012 * Z],
         OH["rope_radius_m"])

    # the halyards: the jib's head on a short wire from the hounds; both tails down the mast's sides to the base cleats
    jhead = Sv["jib"]["tack"] + SL.SA["jib"]["luff_m"] * Sv["jib"]["luff_dir"]
    fwd = G["axis_from_le"] * G["chord_m"] * RG.mast_scale(S["hounds_along"]) * 1.08
    RG.wire(ln, jhead, S["hounds"] + (fwd + 0.03) * u - 0.03 * t, 0.0016)
    hr = HL["rope_radius_m"]
    mast_len = G["length_m"]
    for side, top_a in ((1, S["hounds_along"] - 0.04), (-1, mast_len - 0.12)):
        w = lambda a: (G["width_m"] / 2) * RG.mast_scale(a) + hr + 0.002
        path = [S["heel"] + a * t + side * w(a) * s + 0.01 * u
                for a in np.linspace(top_a, HL["cleat_along_m"] + 0.06, 10)]
        rope(ln, path, hr)
    return [ms, js, ln], K


def report(K, Sv):
    MS = HW["mainsheet"]
    gap = float(np.linalg.norm(K["up_bot"] - K["lo_top"]))
    lead = K["lead"]
    jclew, jcar = K["jclew"], K["jcar"][1]
    r = lambda v: [round(float(x), 3) for x in v]
    return {"mainsheet_blocks_gap_m": round(gap, 3),
            "mainsheet_lead_from_vertical_deg": round(math.degrees(math.acos(float(lead @ Z))), 1),
            "mainsheet_in_use_m": round(MS["purchase"] * gap, 2), "mainsheet_line_m": MS["line_length_m"],
            "mainsheet_two_blocked_in_m": round(MS["purchase"] * gap, 2),
            "boom_hanger": r(K["hanger"]), "traveller_car": r(K["car"]),
            "hanger_aft_of_car_m": round(float(K["car"][0] - K["hanger"][0]), 3),
            "hanger_from_clew_m": round(float(K["hanger"][0] - K["mclew"][0]), 3),
            "jib_car_p": r(jcar), "jib_sheet_m": round(float(np.linalg.norm(jclew - jcar)), 3),
            "jib_sheet_lead_deg": round(math.degrees(math.atan2(jclew[2] - jcar[2],
                                                                math.hypot(jclew[0] - jcar[0], jclew[1] - jcar[1]))), 1)}


if __name__ == "__main__":
    H.solve_depth()
    Sv = SL.solve()
    parts, K = build(Sv)
    print(json.dumps(report(K, Sv), indent=1))
    for p in parts:
        print(f"{p.name}: {len(p.v)} verts, {p.tris()} triangles")
