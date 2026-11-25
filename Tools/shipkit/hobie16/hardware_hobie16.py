"""The Hobie 16's running rigging and deck hardware (docs/hobie16-7, slice 6) as plain geometry: no Blender.

    python3 -I hardware_hobie16.py          prints where the sheets, blocks and cars land and the lines' lengths

hardware_hobie16.json holds the sizes and their sources. The parts hang on slices 2-5: platform_hobie16 (the crossbars'
tracks, the trampoline, the bridle plate), rig_hobie16 (the mast, hounds and masthead) and sails_hobie16 (the tacks,
clews, heads and the boom), so call hull_hobie16.solve_depth() first. Sheeted for upwind on starboard tack, like the
sails. build() returns platform_hobie16.Part meshes in Blender's frame, X forward, Y to PORT, Z up:
  Mainsheet   the traveller car, both mainsheet blocks, the six parts and tail, the traveller line
  JibSheet    the jib cars and their cleats, the working and lazy sheets and the tail between the cars
  Lines       the downhauls' tackles, the outhaul, the halyards' tails (coiled on the mast base's cleats)
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
    """A cam cleat on its base: two toothed cams on posts either side of the rope's lead, a fairlead bridge at the tail
    end. `normal` is the face it stands on, `along` the way the rope runs out through it toward the tail. Returns where
    the rope leaves the fairlead."""
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
        cc = c + 0.008 * n + side * 0.0125 * s - 0.006 * t
        cylinder(part, cc, cc + 0.019 * n, 0.003, "Cast", n=10)
        prof = np.array([[px, side * py] for px, py in teeth])
        # the cam: its toothed edge toward the rope (-side across), standing 0.016 off the base
        prof2 = np.stack([-side * prof[:, 1], prof[:, 0]], axis=1)
        PL.sweep(part, [cc + 0.003 * n, cc + 0.017 * n], prof2[::side], slot, up=tuple(t))
    fl = c + 0.008 * n + (length / 2 - 0.008) * t
    bridge = [fl + 0.009 * (math.cos(th) * s + math.sin(th) * n) for th in np.linspace(0, math.pi, 11)]
    PL.sweep(part, bridge, PL.circle(0.0025, 8), "Cast", up=tuple(t))
    return fl + 0.006 * n + 0.01 * t


def shackle(part, centre, m, A, r=0.011, wire=0.0028, legs=0.012, slot="Cast"):
    """A D-shackle: its bow a half ring toward `m` (what it hooks), legs back, the pin across `A` with a head."""
    c = np.asarray(centre, float)
    m, A = unit(m), unit(A)
    bow = [c - legs * m + r * A] + [c + r * (math.cos(t) * A + math.sin(t) * m) for t in np.linspace(0, math.pi, 13)]
    bow += [c - legs * m - r * A]
    PL.sweep(part, bow, PL.circle(wire, 8), slot, up=tuple(unit(np.cross(m, A))))
    pin = c - legs * m
    cylinder(part, pin - (r + 0.004) * A, pin + (r + 0.004) * A, wire * 1.1, slot, n=10)
    revolve(part, pin + (r + 0.004) * A, A, [(0.0055, 0.0), (0.0055, 0.003)], slot, n=10)


def block_height(radius):
    """A block's cheeks' height for its sheaves' radius."""
    return 2 * radius * 1.12 + 0.03


def head_reach(radius, head="shackle"):
    """A block's centre to its shackle's centre (strap, swivel and shackle), or to the foot of its swivel base."""
    return block_height(radius) / 2 + (0.040 if head == "shackle" else 0.024)


def block(part, centre, lead, mount, sheaves, radius, width, cam=None, becket=False, slot="Block", axle=Y,
          head="shackle", cam_tilt_deg=30.0, cam_top=False):
    """A block: `sheaves` grooved sheaves side by side on an `axle` (athwartships by default), cheek plates between and
    outside them, the axle's pins and, toward `mount` (what it hangs from), a strap, swivel and D-shackle (head
    'shackle') or a strap on a swivel base (head 'swivel'); a becket opposite when the sheet's dead end ties to it. With
    `cam` (the way the tail leaves) a cam cleat with its fairlead: on an arm off the cheeks, tilted cam_tilt_deg away
    from the mount toward the crew, or (cam_top) on a bridge over the sheaves. Returns the tail's exit point and lead."""
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
    top = c + (h_ch / 2 + 0.012) * m
    plate(part, top - 0.006 * m, m, A, span + 0.01, 0.006, 0.012, 0.003, "Cast")
    if head == "shackle":
        cylinder(part, top, top + 0.016 * m, 0.008, "Cast", n=12)
        shackle(part, top + 0.028 * m, m, A)
    else:
        revolve(part, top, m, [(0.009, 0.0), (0.009, 0.006), (0.012, 0.008), (0.012, 0.012)], "Cast", n=16)
    if becket:
        loop(part, c - (h_ch / 2 - 0.004) * m - 0.008 * m, unit(np.cross(m, A)), 0.008, 0.0025, "Cast",
             arc=(0.15 * math.pi + math.pi, 1.85 * math.pi + math.pi))
    if cam is None:
        return None
    f = unit(cam)
    ang = math.radians(cam_tilt_deg)
    t = unit(f * math.cos(ang) - m * math.sin(ang))
    n = unit(-m - float(-m @ t) * t)
    if cam_top:
        base = c - (radius * 1.12 + 0.004) * m + 0.012 * f
        plate(part, base, -m, f, span + 0.012, 0.03, 0.005, 0.004, "Cast")
        cc = base - 0.002 * m + 0.02 * t
    else:
        arm0 = c - 0.01 * m + (w_ch / 2) * f
        plate(part, arm0 + 0.018 * f, n, t, 0.03, 0.04, 0.006, 0.006, "Cast")
        cc = arm0 + 0.032 * f + 0.004 * n
    return cam_cleat(part, cc, n, t), t


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


def helix(part, a, b, radius, turns, wire, slot="Cast"):
    """A coil spring from a to b about their line (the stand-up spring under a block)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ax = unit(b - a)
    e1, e2 = basis(ax)
    n = int(turns * 16)
    pts = [a + (b - a) * k / n + radius * (math.cos(2 * math.pi * turns * k / n) * e1
                                           + math.sin(2 * math.pi * turns * k / n) * e2) for k in range(n + 1)]
    PL.sweep(part, pts, PL.circle(wire, 6), slot, up=tuple(ax))


def knot(part, at, along, r, slot):
    """A stopper knot (a figure eight's lump) on a rope at `at`."""
    t = unit(along)
    revolve(part, np.asarray(at, float) - 2.2 * r * t, t,
            [(r * 1.05, 0.0), (r * 2.1, 0.8 * r), (r * 2.3, 2.2 * r), (r * 2.1, 3.6 * r), (r * 1.05, 4.4 * r)], slot, n=12)


def coil_hanging(part, top, out, r, loops, size, slot):
    """A rope's tail coiled and hung from a cleat: `loops` long loops below `top`, splayed a little toward `out`."""
    top, out = np.asarray(top, float), unit(out)
    side = unit(np.cross(Z, out))
    for k in range(loops):
        spread = (k - (loops - 1) / 2) * 2.4 * r
        pts = [top + spread * side + out * (0.02 + 0.004 * k)
               + size * (0.45 * math.sin(th) * side - (1 - math.cos(th)) * 0.5 * Z) + 0.006 * k * out * math.sin(th / 2)
               for th in np.linspace(0, 2 * math.pi, 22)]
        PL.sweep(part, pts, PL.circle(r, 8), slot, up=tuple(out))


def coil_flat(part, centre, r, loops, radius, slot, L):
    """A rope's spare tail flaked in loose loops on the trampoline round `centre`."""
    c = np.asarray(centre, float)
    pts = []
    for k in range(loops * 24 + 1):
        th = 2 * math.pi * k / 24
        rr = radius * (1 - 0.06 * k / 24) * (1 + 0.08 * math.sin(3 * th + k * 0.3))
        p = c + np.array([rr * math.cos(th) * 1.25, rr * math.sin(th), 0.0])
        lie = PL.tramp_top(L, p[0], p[1]) + r
        p[2] = lie + 1.6 * r * (k / 24) / loops * (1 + math.sin(th + k)) * 0.5
        pts.append(p)
    PL.sweep(part, pts, PL.circle(r, 8), slot, up=(0.0, 0.0, 1.0))
    return pts[0]


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
    # each block's D-shackle hooks through its fitting, the bow round the fitting's wire: the lower one's round the top
    # of the eye on the traveller's swivel post, the upper one's round the bottom of the bail under the boom
    eye = swivel_top + MS["eye_m"] * Z
    sh = MS["shackle_m"]
    lo_sh = eye + MS["eye_m"] * Z - 0.004 * Z + sh * lead
    lo_c = lo_sh + head_reach(Rl) * lead
    bail_bottom = hanger - MS["bail_m"] * 0.6 * Z
    up_sh = bail_bottom + 0.004 * Z - sh * lead
    up_c = up_sh - head_reach(Ru) * lead
    lo_top, up_bot = lo_c + Rl * lead, up_c - Ru * lead
    jtrack_z = L["zf"] + fc["height_m"] / 2 + fc["track_height_m"] / 2
    jx = L["fx"] - fc["track_aft_m"]
    jcar = {side: np.array([jx, side * JS["car_y_m"], jtrack_z + JS["car"][2] / 2]) for side in (1, -1)}
    jclew = j["tack"] + SL.SA["jib"]["foot_m"] * j["foot_dir"]
    mclew = m["tack"] + SL.SA["main"]["foot_m"] * d
    return {"L": L, "S": S, "hanger": hanger, "car": car, "swivel_top": swivel_top, "up_bot": up_bot, "lead": lead,
            "lo_c": lo_c, "up_c": up_c, "eye": eye, "lo_top": lo_top, "jcar": jcar, "jclew": jclew, "mclew": mclew,
            "bar_top": bar_top, "boom_under": boom_under}


def build(Sv=None):
    Sv = Sv or SL.solve()
    K = layout(Sv)
    MS, TR, JS, DH = HW["mainsheet"], HW["traveller"], HW["jib_sheet"], HW["downhauls"]
    L, S = K["L"], K["S"]
    ms, js, ln = Part("Mainsheet"), Part("JibSheet"), Part("Lines")
    X = np.array([1.0, 0.0, 0.0])

    # ---- the traveller: the car in the rear crossbar's track with its swivel post and eye; end stops on the track;
    # the control line from each end of the car along the crossbar's top, through a cam cleat near each corner, a
    # stopper knot inboard of it, the tail lying forward on the trampoline
    tr = TR["line_radius_m"]
    car(ms, K["car"], Y, TR["car"][1], TR["car"][0], TR["car"][2])
    cylinder(ms, K["car"] + TR["car"][2] / 2 * Z, K["swivel_top"], 0.010, "Cast")
    loop(ms, K["eye"], Y, MS["eye_m"], 0.0032, "Cast", n=14)
    for side in (1, -1):
        stop = np.array([K["car"][0], side * TR["stop_y_m"], K["bar_top"] + 0.012])
        PL.box(ms, stop, (0.03, 0.03, 0.024), "Block")
        cl = np.array([K["car"][0] + 0.012, side * TR["line_to_y_m"], K["bar_top"]])
        out = cam_cleat(ms, cl, Z, side * Y, length=0.065)
        a = K["car"] + np.array([0.0, side * (TR["car"][1] / 2 + 0.004), 0.004])
        lift = K["bar_top"] + tr + 0.016
        into = cl + np.array([0.0, -side * 0.032, 0.0]) + 0.012 * Z
        rope(ms, [a, a + side * 0.03 * Y + np.array([0.0, 0.0, lift - a[2]]) * 0.6, into - side * 0.1 * Y, into, out],
             tr, "Control")
        knot(ms, into - side * 0.05 * Y, Y, tr, "Control")
        tail = [out, out + side * 0.04 * Y - 0.004 * Z,
                np.array([K["car"][0] + 0.12, side * (TR["line_to_y_m"] + 0.05), K["bar_top"] - 0.01]),
                np.array([K["car"][0] + 0.3, side * (TR["line_to_y_m"] - 0.02), 0.0]),
                np.array([K["car"][0] + 0.5, side * (TR["line_to_y_m"] - 0.12), 0.0])]
        for p in tail[3:]:
            p[2] = PL.tramp_top(L, p[0], p[1]) + tr
        rope(ms, smooth(tail, 2), tr, "Control")

    # ---- the mainsheet's 6:1
    lead = K["lead"]
    Rl, Ru = MS["lower_sheave_radius_m"], MS["upper_sheave_radius_m"]
    W, NS = MS["sheave_width_m"], MS["sheaves"]
    rm = MS["rope_radius_m"]
    fwd = unit(np.cross(Y, lead))
    lo_ex, lo_t = block(ms, K["lo_c"], lead, -lead, NS, Rl, W, cam=fwd, cam_tilt_deg=MS["cam_tilt_deg"])
    block(ms, K["up_c"], lead, lead, NS, Ru, W, becket=True)
    # the stand-up spring round the swivel, eye and shackle, holding the lower block upright
    car_top = K["car"] + TR["car"][2] / 2 * Z
    helix(ms, car_top + 0.002 * Z, K["lo_c"] - (block_height(Rl) / 2 + 0.006) * lead, 0.017, 7, 0.0016)
    # the bail: a strap riveted under the boom, its loop hanging for the upper block's shackle
    hb = K["hanger"]
    rb = MS["bail_m"] * 0.6
    loop(ms, hb, Y, rb, 0.0032, "Cast", arc=(math.pi, 2 * math.pi), n=12)
    for side in (1, -1):
        foot = hb + side * (rb + 0.008) * X + 0.002 * Z
        plate(ms, foot, Z, X, 0.026, 0.02, 0.004, 0.004, "Cast")
        for r_ in (1, -1):
            cylinder(ms, foot + r_ * 0.007 * Y + 0.002 * Z, foot + r_ * 0.007 * Y + 0.0045 * Z, 0.0035, "Cast", n=10)
    span = NS * W + (NS + 1) * 0.003
    for k in range(NS):
        off = (-span / 2 + 0.003 + W / 2 + k * (W + 0.003)) * Y
        for fa in (1, -1):
            rope(ms, [K["lo_c"] + off + fa * Rl * 0.84 * fwd, K["up_c"] + off + fa * Ru * 0.84 * fwd], rm, "SheetMain")
    # the tail: out of the cam's fairlead toward the crew, falling to the trampoline, forward, and the spare flaked in a
    # loose pile
    tail = [lo_ex, lo_ex + 0.04 * lo_t, lo_ex + 0.09 * lo_t - 0.07 * Z]
    x0 = lo_ex[0] + 0.3
    for k in range(5):
        x = x0 + k * MS["tail_m"] / 4 * 0.7
        y = 0.1 * math.sin(k * 0.9 + 0.4)
        tail.append(np.array([x, y, PL.tramp_top(L, x, y) + rm]))
    pile = np.array([tail[-1][0] + 0.1, tail[-1][1] - 0.3, 0.0])
    start = coil_flat(ms, pile, rm, MS["pile_loops"], MS["pile_radius_m"], "SheetMain", L)
    tail.append(start)
    rope(ms, smooth(tail, 3), rm, "SheetMain")

    # ---- the jib sheet, 2:1 a side and one line: from the becket on one car up to its sheave in the clew's double
    # block, back down round the car's ratchet block and out through the cam over it, across the trampoline to the other
    # car, and the same way up and back to that car's becket. The working (port) side tight, the lazy side slack.
    clew = K["jclew"]
    Rc, Rj, wj, rj = JS["clew_sheave_radius_m"], JS["car_sheave_radius_m"], JS["sheave_width_m"], JS["rope_radius_m"]
    work = unit(K["jcar"][1] + np.array([0.0, 0.0, 0.12]) - clew)       # the clew block leans toward the working car
    c_axle = unit(np.cross(work, X))
    c_axle = c_axle if c_axle[1] > 0 else -c_axle
    sh = MS["shackle_m"]
    ring = clew + 0.010 * work                                          # the clew's ring, sewn into the sail
    loop(js, ring, unit(np.cross(work, c_axle)), 0.010, 0.003, "Cast", n=12)
    cb = ring + (0.010 - 0.004 + sh) * work + head_reach(Rc) * work     # its shackle's bow round the ring
    block(js, cb, work, -work, 2, Rc, wj, axle=c_axle)
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
        loop(js, beck, X, 0.008, 0.0025, "Cast", arc=(0.0, math.pi), n=10)
        # the car's ratchet block on a swivel base, its sheave square to the pull, the cam on a bridge over it
        post = cc + (JS["car"][2] / 2) * Z
        up = unit(clew + sheave_off - (post + 0.05 * Z))
        hp = np.array([up[0], up[1], 0.0])
        b_axle = unit(np.cross(Z, hp))
        inboard = unit(np.array([-0.35, -side, 0.0]))
        bc = post + head_reach(Rj, "swivel") * Z
        j_ex, j_t = block(js, bc, Z, -Z, 1, Rj, wj, cam=inboard, axle=b_axle, head="swivel", cam_top=True,
                          cam_tilt_deg=0.0)
        top_c = cb + sheave_off
        p1 = [beck + 0.008 * Z, top_c + Rc * 0.9 * c_side]
        p2 = [top_c - Rc * 0.9 * c_side, bc + Rj * 0.9 * up]
        if side == 1:
            rope(js, p1, rj, "SheetJib")
            rope(js, p2, rj, "SheetJib")
        else:
            # the lazy side runs from the starboard car to the clew behind the mast, so it bears on the mast's aft
            # face and hangs slack either side of it
            for k, (s0, s1) in enumerate((p1, p2)):
                h = (s0[2] + s1[2]) / 2 - 0.08
                mp = mast_aft(S, h) + (k - 0.5) * 0.012 * Y
                rope(js, sagged(s0, mp, JS["lazy_sag_m"] * 0.15, 7)[:-1] + sagged(mp, s1, JS["lazy_sag_m"] * 0.35, 7),
                     rj, "SheetJib")
        tails[side] = (j_ex, j_t)
    # the tail across the trampoline: out of each cam's fairlead, falling onto the trampoline aft of the front
    # crossbar, a loose bight between the cars
    (a, da), (b, db) = tails[1], tails[-1]
    x_on = L["fx"] - JS["tail_on_tramp_aft_m"]
    ctrl = [a, a + 0.05 * da, a + 0.1 * da - 0.06 * Z, np.array([x_on, a[1] * 0.55, 0.0]),
            np.array([x_on - JS["tail_aft_m"], 0.0, 0.0]),
            np.array([x_on, b[1] * 0.55, 0.0]), b + 0.1 * db - 0.06 * Z, b + 0.05 * db, b]
    for c_ in ctrl:
        if c_[2] == 0.0:
            c_[2] = PL.tramp_top(L, c_[0], c_[1]) + rj
    out = []
    for p in smooth(ctrl, 3):
        out.append(np.array([p[0], p[1], max(p[2], PL.tramp_top(L, p[0], p[1]) + rj)]))
    rope(js, out, rj, "SheetJib")

    # ---- the jib's tack downhaul to the bridle plate
    r = DH["rope_radius_m"]
    jt = Sv["jib"]["tack"]
    J = np.array(S["junction"]) + np.array([0.0, 0.0, 0.03])
    for k in range(DH["jib_parts"]):
        off = (k - (DH["jib_parts"] - 1) / 2) * 0.012 * Y
        rope(ln, [jt + off, J + off], r, "Control")

    # ---- the main's downhaul (cunningham): a double block with a becket hooked to the gooseneck's ring under the tack,
    # a double with a cam shackled to the eye on the mast's foot, four parts between, the tail out of the cam
    t, s, u = RG.frame(S["rake"])
    tack = Sv["main"]["tack"]
    G = RG.G["mast"]
    Rd, wd = DH["sheave_radius_m"], DH["sheave_width_m"]
    ring = tack - DH["ring_below_tack_m"] * t
    loop(ln, ring, s, 0.009, 0.003, "Cast", n=12)
    foot_eye = mast_aft(S, S["heel"][2] + DH["foot_eye_up_m"]) - 0.004 * u
    loop(ln, foot_eye, s, 0.009, 0.003, "Cast", n=12)
    dl = unit(ring - foot_eye)
    dh_up = ring - (0.009 - 0.004 + sh) * dl - head_reach(Rd) * dl
    dh_lo = foot_eye + (0.009 - 0.004 + sh) * dl + head_reach(Rd) * dl
    block(ln, dh_up, dl, dl, 2, Rd, wd, becket=True, axle=s)
    d_ex, d_t = block(ln, dh_lo, dl, -dl, 2, Rd, wd, cam=-u, axle=s)
    d_fwd = unit(np.cross(s, dl))
    dspan = 2 * wd + 3 * 0.003
    for k in range(2):
        off = (-dspan / 2 + 0.003 + wd / 2 + k * (wd + 0.003)) * s
        for fa in (1, -1):
            rope(ln, [dh_lo + off + fa * Rd * 0.84 * d_fwd, dh_up + off + fa * Rd * 0.84 * d_fwd], r, "Control")
    dtail = [d_ex, d_ex + 0.04 * d_t, d_ex + 0.08 * d_t - 0.12 * Z]
    x = dtail[-1][0] - 0.1
    dtail.append(np.array([x, 0.05, PL.tramp_top(L, x, 0.05) + r]))
    x -= 0.2
    dtail.append(np.array([x, 0.12, PL.tramp_top(L, x, 0.12) + r]))
    rope(ln, [dtail[0]] + smooth(dtail[1:], 2), r, "Control")

    # ---- the outhaul: from the clew's ring aft round a sheave in the boom's end cap, forward along the boom's port
    # side to a cam cleat on it, the tail hanging in a bight
    clew = K["mclew"]
    d = Sv["main"]["foot_dir"]
    OH = HW["outhaul"]
    ro = OH["rope_radius_m"]
    B = SL.SA["boom"]
    a_end = SL.SA["main"]["foot_m"] + B["end_cap_m"]
    boom_c = lambda a_: Sv["main"]["tack"] + a_ * d - 0.05 * Z
    sv = boom_c(a_end - 0.02) + (B["height_m"] / 2 - 0.004) * Z
    sheave(ln, sv, Y, 0.012, 0.008)
    loop(ln, clew - 0.008 * Z, Y, 0.009, 0.003, "Cast", n=12)
    side_y = (B["width_m"] / 2 + ro + 0.002) * Y
    cleat_c = boom_c(a_end - OH["cleat_from_end_m"]) + (B["width_m"] / 2) * Y
    o_ex = cam_cleat(ln, cleat_c, Y, -d, length=0.06)
    rope(ln, [clew - 0.014 * Z, sv + 0.012 * Z - 0.012 * d, sv + 0.012 * d + 0.004 * Z, sv + 0.016 * d - 0.012 * Z,
              boom_c(a_end - 0.06) + side_y, cleat_c + 0.03 * d + 0.012 * Y + 0.008 * Y], ro, "Control")
    rope(ln, sagged(o_ex, o_ex - 0.16 * d - 0.01 * Z, 0.06, 15), ro, "Control")

    # ---- the halyards: the jib's head on a short wire from the hounds; both tails down the mast's sides to the cam
    # cleats on its foot, each tail coiled and hung from its cleat
    HL = HW["halyards"]
    jhead = Sv["jib"]["tack"] + SL.SA["jib"]["luff_m"] * Sv["jib"]["luff_dir"]
    fwd_h = G["axis_from_le"] * G["chord_m"] * RG.mast_scale(S["hounds_along"]) * 1.08
    RG.wire(ln, jhead, S["hounds"] + (fwd_h + 0.03) * u - 0.03 * t, 0.0016)
    hr = HL["rope_radius_m"]
    mast_len = G["length_m"]
    for side, top_a in ((1, S["hounds_along"] - 0.04), (-1, mast_len - 0.12)):
        w = lambda a_: (G["width_m"] / 2) * RG.mast_scale(a_) + hr + 0.002
        c = S["heel"] + HL["cleat_along_m"] * t + side * (G["width_m"] / 2 + 0.012) * s
        h_ex = cam_cleat(ln, c - side * 0.012 * s, side * s, -t)
        path = [S["heel"] + a_ * t + side * w(a_) * s + 0.01 * u for a_ in np.linspace(top_a, HL["cleat_along_m"] + 0.08, 10)]
        rope(ln, path + [h_ex + 0.03 * t], hr)
        coil_hanging(ln, h_ex - 0.004 * t, side * s, hr, 3, HL["coil_m"], "Line")
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
