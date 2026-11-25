"""The Lagoon 42's mast, boom, standing rigging and running rigging's paths from rig_lagoon42.json: pure geometry, no
Blender (docs/lagoon42-7).

    python3 -I rig_lagoon42.py      prints the main numbers and writes nothing

parts() lists every part, each a dict with its kind and the object it belongs to ('obj'):
  rings  rings (closed rings of points, each the same length: a solid capped at both ends), mat, smooth
  cyl    a, b (the axis' ends), radius, mat, segments
  torus  centre, axis (unit), R (to the tube's centre), r (the tube's), mat
  kit    one of the boat kit's parts (Tools/boatkit/bk_parts.py) by name, placed at origin with its local X, Y and Z axes
         on the game-frame unit vectors ax, ay, az (ay = ax x az by the plain cross product: the kit is built in
         Blender's right-handed frame and the game's is mirrored), scaled by scale, built with kw (size, count, length),
         collapsed to light of its triangles if light (the kit's own light copies' way), its sockets expected at
         'expect' (game frame: build_lagoon42.py checks them against the kit's own)
The objects (build_lagoon42.py meshes each as L42_<Obj>):
  mast      the extrusion, its track, masthead cap and crane, sheave boxes, tangs, T-ball plates, spreaders with their
            root sockets, end caps and boots, the gooseneck's bracket and reef horns, radar, lights and instruments.
            Origin at the step's top (the game's MastStep socket)
  boom      the boom with its castings, gooseneck tongue, mainsheet bail and upper block, outhaul car, topping lift.
            Origin at the gooseneck's pin: the game swings it about its z
  wires     the forestay and its furler's foil, the caps (bent over the spreaders' tips) and lowers, with their swaged
            terminals: the game draws live wires between the sockets today; slice 13 decides which it shows
  fittings  on the boat: the mast step, the turning blocks and their eye straps, the chainplates and turnbuckles, the
            forestay's tang, toggle and furler, the self-tacking track and car, the traveller with the mainsheet's lower
            block, the clutch banks and winches
  running   the lines: halyards, topping lift and sheets from the mast's exits round their turning blocks, across the
            roof through the clutches, the working ones round their winches and off the self-tailers; the mainsheet's
            tail, the traveller's control lines
  mainsheet the mainsheet's four parts between its fiddles, the boom amidships (L42_Mainsheet, slice 7): a hoisted main's
            object draws them again at its boom's angle (sails_lagoon42.py), and this one is hidden with it
sockets() gives the game's sockets (name: (point, owner)) for the sockets file build_lagoon42.py writes.

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the game's waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import appendages_lagoon42 as A  # noqa: E402
import bridgedeck_lagoon42 as B  # noqa: E402
import hull_lagoon42 as H  # noqa: E402
import saloon_lagoon42 as S  # noqa: E402

RG = json.load(open(os.path.join(HERE, "rig_lagoon42.json")))
MS, SP, CP, WR, FS = RG["mast"], RG["spreaders"], RG["chainplates"], RG["wire"], RG["forestay"]
MH, FM, BO, TR, JT, HL = RG["masthead"], RG["fittings_on_mast"], RG["boom"], RG["traveller"], RG["jib_track"], RG["helm_lines"]
MAST_X = MS["x"]
ROOF_Z = S.roof_top_z(0.0)
HEEL_Z = ROOF_Z + MS["step_height"]
TRUCK_Z = MS["air_draft"] + RG["light_waterline_z"]
HOUNDS_Z = RG["hounds_z"]
PIN_X, PIN_Z = BO["pin"]
PAINT = MS["paint"]
TAU = 2 * math.pi
STRAP = 0.004               # an eye strap's plate
KIT_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "boatkit")


# ---- vectors (tuples) ----

def add(a, b):
    return tuple(p + q for p, q in zip(a, b))


def sub(a, b):
    return tuple(p - q for p, q in zip(a, b))


def mul(a, s):
    return tuple(p * s for p in a)


def dot(a, b):
    return sum(p * q for p, q in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return mul(a, 1.0 / n) if n > 1e-12 else a


def lerp(a, b, t):
    return tuple(p + (q - p) * t for p, q in zip(a, b))


def perp(d):
    """Two unit vectors square to d and to each other."""
    d = unit(d)
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = unit(cross(d, ref))
    return u, cross(u, d)


def roof_z(y):
    return S.roof_top_z(y)


# ---- rings, tubes, wraps ----

def ring(c, u, v, prof):
    return [add(c, add(mul(u, a), mul(v, b))) for a, b in prof]


def circle(r, n):
    return [(r * math.cos(TAU * k / n), r * math.sin(TAU * k / n)) for k in range(n)]


def rrect(w, h, r, n=4):
    """A rounded rectangle w x h (corner radius r) about the origin, counter-clockwise: [(a, b)]."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 0.5 * math.pi),
                       (-w / 2 + r, -h / 2 + r, math.pi), (w / 2 - r, -h / 2 + r, 1.5 * math.pi)):
        for k in range(n + 1):
            a = a0 + 0.5 * math.pi * k / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def tube(points, r, sides=8):
    """Rings of a round tube along a polyline (parallel-transported frames; a sharp corner's ring is widened so the
    tube keeps its radius through it)."""
    pts = [points[0]]
    for p in points[1:]:
        if norm(sub(p, pts[-1])) > 1e-6:
            pts.append(p)
    n = len(pts)
    tans = []
    for i in range(n):
        a = unit(sub(pts[min(i + 1, n - 1)], pts[max(i - 1, 0)])) if 0 < i < n - 1 else None
        if i == 0:
            a = unit(sub(pts[1], pts[0]))
        elif i == n - 1:
            a = unit(sub(pts[-1], pts[-2]))
        else:
            a = unit(add(unit(sub(pts[i], pts[i - 1])), unit(sub(pts[i + 1], pts[i]))))
        tans.append(a)
    u, _ = perp(tans[0])
    rings = []
    for i, (p, t) in enumerate(zip(pts, tans)):
        u = unit(sub(u, mul(t, dot(u, t))))
        v = cross(t, u)
        k = 1.0
        if 0 < i < n - 1:
            c = dot(unit(sub(pts[i], pts[i - 1])), t)
            k = 1.0 / max(c, 0.5)
        rings.append(ring(p, mul(u, r * k), mul(v, r * k), circle(1.0, sides)))
    return rings


def rope(points, r, mat="Rope", obj="running", sides=8):
    return {"kind": "rings", "rings": tube(points, r, sides), "mat": mat, "smooth": True, "obj": obj}


def arc_pts(c, e1, e2, r, a0, a1, n):
    return [add(c, add(mul(e1, r * math.cos(a0 + (a1 - a0) * k / n)), mul(e2, r * math.sin(a0 + (a1 - a0) * k / n))))
            for k in range(n + 1)]


def wrap(p, c, axis, r, q, step=math.radians(10)):
    """A line from p round a sheave (centre c, its axle along axis, the line's centre r from it) on to q: the points
    from the tangent off p round the sheave to the tangent toward q, the sheave inside the bend. p and q are put on
    the sheave's plane."""
    e1, e2 = perp(axis)
    to2 = lambda w: (dot(sub(w, c), e1), dot(sub(w, c), e2))
    P, Q = to2(p), to2(q)
    best = None
    for s in (1, -1):
        def tangent(X, incoming):
            d = math.hypot(*X)
            phi = math.atan2(X[1], X[0])
            al = math.acos(min(1.0, r / d))
            for t in (phi + al, phi - al):
                T = (r * math.cos(t), r * math.sin(t))
                vel = (-s * math.sin(t), s * math.cos(t))
                along = (T[0] - X[0], T[1] - X[1]) if incoming else (X[0] - T[0], X[1] - T[1])
                if along[0] * vel[0] + along[1] * vel[1] > 0:
                    return t
            return phi
        t1, t2 = tangent(P, True), tangent(Q, False)
        sweep = ((t2 - t1) * s) % TAU
        mid = t1 + s * sweep / 2
        bis = unit(add(unit((P[0], P[1], 0.0)), unit((Q[0], Q[1], 0.0))))
        score = -(math.cos(mid) * bis[0] + math.sin(mid) * bis[1])
        if best is None or score > best[0]:
            best = (score, t1, t1 + s * sweep)
    _, a0, a1 = best
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return arc_pts(c, e1, e2, r, a0, a1, n)


# ---- the boat kit: its parts' sockets in their own frame (bk_parts.py; the build checks them) ----

KIT_SIZE = {("Block40", "57"): 1.425, ("Fiddle40", "57"): 1.425, ("Winch70", "50"): 0.85, ("Winch70", "70"): 1.0}


def kit_local(name, kw):
    """The sockets a kit part is built with (its own frame, metres) at its size (bk_parts.SIZES)."""
    k = KIT_SIZE.get((name, kw.get("size")), 1.0)
    if name == "Winch70":
        return {"Drum": (0, 0.098 * k, 0.13 * k), "Handle": (0, 0, 0.284 * k), "Tail": (0.150 * k, 0, 0.244 * k)}
    if name == "ClutchBank":
        n, pitch = kw.get("count", 4), kw.get("pitch", 0.072)
        w = n * pitch + 0.03
        return {f"Line{i}": (0.09, -w / 2 + 0.015 + pitch * (i + 0.5), 0.04) for i in range(n)}
    if name == "TravellerHeavy":
        L = kw.get("length", 4.4)
        return {"Car": (0, 0, 0.12), "EndP": (-L / 2, 0, 0.04), "EndS": (L / 2, 0, 0.04)}
    if name == "Block40":
        return {"Head": (0, 0, 0), "Axle": (0, 0, -0.0604 * k), "LineIn": (0.02 * k, 0, -0.0604 * k)}
    if name == "Fiddle40":
        return {"Head": (0, 0, 0), "Axle": (0, 0, -0.0604 * k), "Axle2": (0, 0, -0.0965 * k), "LineIn": (0.02 * k, 0, -0.0604 * k),
                "LineIn2": (0.013 * k, 0, -0.0965 * k)}
    if name == "Turnbuckle":
        return {"Toggle": (0, 0, 0), "Wire": (0, 0, 0.216)}
    if name == "Chainplate":
        return {"Pin": (0, 0, 0.035)}
    return {}


def kit(name, origin, ax, az, scale=1.0, light=False, obj="fittings", **kw):
    """One kit part with its local X on ax and Z on az (game frame, unit, square); its local Y is ax x az."""
    ax, az = unit(ax), unit(az)
    ay = cross(ax, az)
    to_game = lambda l: add(origin, mul(add(add(mul(ax, l[0]), mul(ay, l[1])), mul(az, l[2])), scale))
    return {"kind": "kit", "name": name, "origin": origin, "ax": ax, "ay": ay, "az": az, "scale": scale, "light": light,
            "kw": kw, "obj": obj, "expect": {s: to_game(p) for s, p in kit_local(name, kw).items()}}


def kit_axes_pin(pin, z):
    """(ax, az) for a part whose local Y is the pin and local Z is z (the chainplate's and turnbuckle's frame)."""
    z = unit(z)
    pin = unit(sub(pin, mul(z, dot(pin, z))))
    return cross(pin, z), z


# ---- the mast ----

def section(z):
    """The mast's section at height z: (centre x, half chord, half width). Above the hounds it tapers to the truck,
    its aft face straight."""
    a0, b0 = MS["chord"] / 2, MS["width"] / 2
    if z <= HOUNDS_Z:
        return MAST_X, a0, b0
    t = min(1.0, (z - HOUNDS_Z) / (TRUCK_Z - HOUNDS_Z))
    a = a0 + (MS["top_chord"] / 2 - a0) * t
    b = b0 + (MS["top_width"] / 2 - b0) * t
    return MAST_X - a0 + a, a, b


def se(c, p):
    return math.copysign(abs(c) ** p, c)


def mast_uv(t, z, grow=0.0):
    """The point at parameter t round the section at z (0 forward, pi/2 starboard), grown outward by grow."""
    cx, a, b = section(z)
    p = MS["power"]
    u, v = a * se(math.cos(t), p), b * se(math.sin(t), p)
    if grow:
        n = mast_normal(t, z)
        return (cx + u + n[0] * grow, v + n[1] * grow)
    return (cx + u, v)


def mast_point(t, z, grow=0.0):
    x, y = mast_uv(t, z, grow)
    return (x, y, z)


def mast_normal(t, z, h=1e-4):
    """The outward horizontal normal of the section at t."""
    x0, y0 = mast_uv(t - h, z)
    x1, y1 = mast_uv(t + h, z)
    return unit((y1 - y0, -(x1 - x0), 0.0))


def mast_t_toward(p, z):
    """The section's parameter t whose point lies on the ray from the mast's centre at z toward p (plan)."""
    cx, a, b = section(z)
    ang = math.atan2(p[1], p[0] - cx)
    lo, hi = ang - 1.0, ang + 1.0
    best = min((abs(((math.atan2(mast_uv(t, z)[1], mast_uv(t, z)[0] - cx) - ang + math.pi) % TAU) - math.pi), t)
               for t in [lo + (hi - lo) * k / 400 for k in range(401)])
    return best[1]


def mast_rings(n=48):
    zs = [HEEL_Z, HEEL_Z + 0.02, HOUNDS_Z] + [HOUNDS_Z + (TRUCK_Z - 0.05 - HOUNDS_Z) * k / 6 for k in range(1, 7)]
    return [[mast_point(TAU * k / n, z) for k in range(n)] for z in zs]


def front_x(z):
    cx, a, _ = section(z)
    return cx + a


def aft_x():
    return MAST_X - MS["chord"] / 2


def track_rings():
    """The main's T-track up the aft face: a base flange, a neck and the head the batten cars run on."""
    w, d = MS["track"]["width"], MS["track"]["depth"]
    prof = [(0.0, w / 2), (0.008, w / 2), (0.008, 0.006), (0.014, 0.006), (0.014, w / 2 - 0.003), (d, w / 2 - 0.003),
            (d, -(w / 2 - 0.003)), (0.014, -(w / 2 - 0.003)), (0.014, -0.006), (0.008, -0.006), (0.008, -w / 2), (0.0, -w / 2)]
    x0 = aft_x() + 0.002
    return [[(x0 - u, v, z) for u, v in prof] for z in MS["track"]["z"]]


def band(z0, z1, grow, t0=0.0, t1=TAU, n=48, mat=None):
    """A band round (part of) the mast's section from z0 to z1, grown outward: a sleeve, a collar or a plate."""
    if abs(t1 - t0 - TAU) < 1e-9:
        lo = [mast_point(t0 + TAU * k / n, z0, grow) for k in range(n)]
        hi = [mast_point(t0 + TAU * k / n, z1, grow) for k in range(n)]
        return {"kind": "rings", "rings": [lo, hi], "mat": mat or PAINT, "smooth": True, "obj": "mast"}
    ts = [t0 + (t1 - t0) * k / n for k in range(n + 1)]
    rings = []
    for z in (z0, z1):
        outer = [mast_point(t, z, grow) for t in ts]
        inner = [mast_point(t, z, -0.002) for t in ts[::-1]]
        rings.append(outer + inner)
    return {"kind": "rings", "rings": rings, "mat": mat or "Stainless", "smooth": False, "obj": "mast"}


def plate_on_mast(t, z, w, h, thick, mat="Stainless", r=0.008):
    """A rounded plate w across x h tall lying on the mast's face at t, z (a T-ball plate, a sheave box)."""
    c = mast_point(t, z)
    nrm = mast_normal(t, z)
    tan = cross((0, 0, 1), nrm)
    prof = rrect(w, h, min(r, w / 2 - 1e-3, h / 2 - 1e-3))
    rings = [[add(add(c, mul(nrm, d)), add(mul(tan, a), (0, 0, b))) for a, b in prof] for d in (-0.003, thick)]
    return {"kind": "rings", "rings": rings, "mat": mat, "smooth": False, "obj": "mast"}


def sheave_box(t, z, h=0.11, w=0.042):
    """A halyard's sheave box let into the mast: a stainless frame with the dark slot and the sheave's rim in it."""
    nrm = mast_normal(t, z)
    tan = cross((0, 0, 1), nrm)
    c = mast_point(t, z)
    out = [plate_on_mast(t, z, w, h, 0.004)]
    slot = [[add(add(c, mul(nrm, d)), add(mul(tan, a), (0, 0, b))) for a, b in rrect(w * 0.45, h * 0.7, 0.008)]
            for d in (0.0035, 0.0046)]
    out.append({"kind": "rings", "rings": slot, "mat": "BlackPlastic", "smooth": False, "obj": "mast"})
    return out


# ---- spreaders and the standing rigging's ends ----

def tball(t, z, toward, r_wire):
    """A T-ball terminal on the mast's face at t, z, its wire leaving toward 'toward': the backing plate, the
    terminal's neck and its swage sleeve. Returns (parts, the wire's start)."""
    nrm = mast_normal(t, z)
    base = mast_point(t, z, 0.004)
    d = unit(sub(toward, base))
    neck_end = add(base, mul(d, 0.03))
    sleeve_end = add(neck_end, mul(d, 0.09))
    parts = [plate_on_mast(t, z, 0.045, 0.075, 0.005),
             {"kind": "cyl", "a": add(base, mul(nrm, -0.002)), "b": neck_end, "radius": r_wire * 1.4, "mat": "Stainless",
              "segments": 12, "obj": "mast"},
             {"kind": "cyl", "a": neck_end, "b": sleeve_end, "radius": r_wire * 1.7, "mat": "Stainless", "segments": 12,
              "obj": "wires"}]
    return parts, sleeve_end


def chainplate(xy, toward, wire_d):
    """A chainplate on a hull's outboard deck at xy and its turnbuckle up toward the wire (wire_d across): the kit's
    Chainplate and Turnbuckle, scaled from their 5 mm wire to this wire. Returns (parts, pin, the wire's end)."""
    x, y = xy
    cy = math.copysign(H.HULL_Y, y)
    t = (y - cy) / H.half_beam(x)
    deck = S.deck_z(x, t)
    k = wire_d / 0.005
    up = (0.0, 0.0, 1.0)
    d_plan = unit((toward[0] - x, toward[1] - y, 0.0))
    pin_axis = cross(up, d_plan)
    ax, az = kit_axes_pin(pin_axis, up)
    cp = kit("Chainplate", (x, y, deck - 0.001), ax, az, scale=k)
    pin = cp["expect"]["Pin"]
    wdir = unit(sub(toward, pin))
    ax2, az2 = kit_axes_pin(pin_axis, wdir)
    tb = kit("Turnbuckle", pin, ax2, az2, scale=k, light=0.25)
    return [cp, tb], pin, tb["expect"]["Wire"]


def spreader_tip(s=1, bisect=False):
    """The starboard (s 1) or port spreader's tip where the photo puts it (bisect: its height instead so the spreader
    bisects the angle the cap makes over it, no sliding load at the tip). Returns (root on the mast, tip, the cap's
    upper end)."""
    tip_xy = (MAST_X - SP["tip_aft"], s * SP["tip_out"])
    t_root = mast_t_toward((tip_xy[0], tip_xy[1], 0), SP["root_z"])
    root = mast_point(t_root, SP["root_z"])
    t_h = mast_t_toward((tip_xy[0], tip_xy[1], 0), HOUNDS_Z)
    upper = mast_point(t_h, HOUNDS_Z, 0.13)
    z = SP["tip_z"]
    for _ in range(40 if bisect else 0):
        tip = (tip_xy[0], tip_xy[1], z)
        wend = chainplate((CP["cap"][0], s * CP["cap"][1]), tip, WR["cap"])[2]
        u1, u2 = unit(sub(upper, tip)), unit(sub(wend, tip))
        d = unit(mul(add(u1, u2), -1.0))
        horiz = math.hypot(tip[0] - root[0], tip[1] - root[1])
        z = root[2] + horiz * d[2] / math.hypot(d[0], d[1])
    return root, (tip_xy[0], tip_xy[1], z), upper


def spreader_parts(s):
    root, tip, _ = spreader_tip(s)
    ax = unit(sub(tip, root))
    side = unit(cross((0, 0, 1), ax))                    # the chord's way, square to the axis in plan
    up = cross(ax, side)
    if up[2] < 0:
        side, up = mul(side, -1), mul(up, -1)
    L = norm(sub(tip, root))
    parts = []
    m = 10
    us = A.chord_us(m)
    rings = []
    for k in range(9):
        f = k / 8
        c = add(root, mul(ax, -0.03 + (L - 0.045 + 0.03) * f))
        ch = SP["chord"][0] + (SP["chord"][1] - SP["chord"][0]) * f
        th = SP["thickness"][0] + (SP["thickness"][1] - SP["thickness"][0]) * f
        tr = th / ch
        sec = [(ch / 2 - ch * u, A.naca(u, tr) * ch) for u in us] + \
              [(ch / 2 - ch * u, -A.naca(u, tr) * ch) for u in us[1:-1]][::-1]
        sec = [(a, b if abs(b) > 1e-4 else math.copysign(1e-4, b or 1)) for a, b in sec]
        rings.append([add(c, add(mul(side, a * (1 if s > 0 else -1)), mul(up, b))) for a, b in sec])
    parts.append({"kind": "rings", "rings": rings, "mat": PAINT, "smooth": True, "obj": "mast"})
    # the root's cast socket on the mast's side: a rounded block the spreader goes into
    nrm = mast_normal(mast_t_toward(tip, root[2]), root[2])
    t_root = mast_t_toward(tip, root[2])
    sock = []
    for d in (-0.004, 0.035, 0.07):
        w = 0.16 - 0.5 * d
        h = 0.14 - 0.6 * d
        c = add(mast_point(t_root, root[2]), mul(nrm, d))
        tan = cross((0, 0, 1), nrm)
        sock.append([add(c, add(mul(tan, a), (0, 0, b))) for a, b in rrect(w, h, 0.03)])
    parts.append({"kind": "rings", "rings": sock, "mat": "Aluminium", "smooth": True, "obj": "mast"})
    parts += [{"kind": "cyl", "a": add(mast_point(t_root, root[2] + dz, 0.0), mul(nrm, 0.0)),
               "b": add(mast_point(t_root, root[2] + dz, 0.0), mul(nrm, 0.075)), "radius": 0.007, "mat": "Stainless",
               "segments": 8, "obj": "mast"} for dz in (-0.045, 0.045)]
    # the end cap clamping the cap wire, and the white boot over the tip
    e0, e1 = add(root, mul(ax, L - 0.05)), add(root, mul(ax, L + 0.012))
    parts.append({"kind": "cyl", "a": e0, "b": e1, "radius": 0.024, "mat": "Aluminium", "segments": 16, "obj": "mast"})
    boot = []
    for k in range(9):
        f = k / 8
        sx = L - 0.13 + 0.17 * f
        rr = 0.012 + 0.036 * math.sin(math.pi * min(1.0, 0.15 + f * 0.85)) ** 0.7
        c = add(root, mul(ax, sx))
        boot.append([add(c, add(mul(side, rr * 1.15 * math.cos(a)), mul(up, rr * math.sin(a)))) for a in
                     (TAU * j / 16 for j in range(16))])
    parts.append({"kind": "rings", "rings": boot, "mat": "WhitePlastic", "smooth": True, "obj": "mast"})
    return parts


# ---- the forestay ----

def hounds_pin():
    return (front_x(HOUNDS_Z) + 0.05, 0.0, HOUNDS_Z)


def forestay_tack():
    return (B.CB["x"], 0.0, FS["tack_z"] + 0.05)


def forestay_at(z):
    """The forestay's axis at height z."""
    a, b = forestay_tack(), hounds_pin()
    return lerp(a, b, (z - a[2]) / (b[2] - a[2]))


def forestay_parts():
    tack, head = forestay_tack(), hounds_pin()
    d = unit(sub(head, tack))
    e1, e2 = perp(d)
    P = []
    # the tang on the crossbeam: a strap either side of the pin, through a plate on the beam's top
    top = FS["tack_z"]
    P.append({"kind": "box", "lo": (tack[0] - 0.06, -0.05, top - 0.004), "hi": (tack[0] + 0.06, 0.05, top + 0.006),
              "round": 0.004, "mat": "Stainless", "obj": "fittings"})
    for s in (-1, 1):
        P.append({"kind": "rings", "obj": "fittings", "mat": "Stainless", "smooth": False,
                  "rings": [[(tack[0] + a, s * 0.017 + s * o, top + 0.004 + b) for a, b in
                             [(-0.035, 0), (0.035, 0), (0.035, 0.03), (0.0, 0.07), (-0.035, 0.03)]] for o in (0.0, 0.008)]})
    P.append({"kind": "cyl", "a": (tack[0], -0.03, tack[2]), "b": (tack[0], 0.03, tack[2]), "radius": 0.008,
              "mat": "Stainless", "segments": 12, "obj": "fittings"})
    # the toggle and the furler's drum, swivel and foil, along the stay
    zt = tack[2]
    P.append({"kind": "rings", "obj": "fittings", "mat": "Stainless", "smooth": True,
              "rings": [ring(add(tack, mul(d, f * FS["toggle"])), mul(e1, 0.022), mul(e2, 0.015), rrect(1, 1, 0.3))
                        for f in (0.0, 1.0)]})
    dr = FS["drum"]
    c0 = add(tack, mul(d, FS["toggle"]))
    c1 = add(tack, mul(d, FS["toggle"] + dr["lift"]))
    P.append({"kind": "cyl", "a": c0, "b": c1, "radius": 0.03, "mat": "Aluminium", "segments": 24, "obj": "fittings"})
    ra, rf = dr["diameter"] / 2, dr["flange"] / 2
    s0 = FS["toggle"] + dr["lift"]
    prof = [(0.0, 0.03), (0.0, rf), (0.008, rf), (0.012, ra * 0.82), (dr["height"] - 0.012, ra * 0.82),
            (dr["height"] - 0.008, rf), (dr["height"], rf), (dr["height"], 0.035)]
    P.append({"kind": "rings", "obj": "fittings", "mat": "Aluminium", "smooth": True,
              "rings": [ring(add(tack, mul(d, s0 + s)), mul(e1, r), mul(e2, r), circle(1.0, 40)) for s, r in prof]})
    # the furling line's turns on the drum
    P.append({"kind": "rings", "obj": "fittings", "mat": "Rope", "smooth": True,
              "rings": [ring(add(tack, mul(d, s0 + s)), mul(e1, ra * 0.82 + 0.012), mul(e2, ra * 0.82 + 0.012),
                             circle(1.0, 40)) for s in (0.03, dr["height"] - 0.03)]})
    # the line guide: an arm off the drum's flange aft and to starboard with a fairlead ring at its end
    g0 = add(tack, add(mul(d, s0 + 0.02), (0, 0, 0)))
    gdir = unit((-0.6, 0.8, 0.0))
    g1 = add(g0, mul(gdir, rf + 0.06))
    P.append({"kind": "cyl", "a": g0, "b": g1, "radius": 0.008, "mat": "Stainless", "segments": 8, "obj": "fittings"})
    P.append({"kind": "torus", "centre": g1, "axis": gdir, "R": 0.014, "r": 0.004, "mat": "Stainless", "n": 16, "m": 6,
              "obj": "fittings"})
    # the tack swivel over the drum, its shackle eye aft
    sw0 = s0 + dr["height"]
    sw1 = (FS["swivel_z"] + 0.08 - zt) / d[2]
    P.append({"kind": "cyl", "a": add(tack, mul(d, sw0)), "b": add(tack, mul(d, sw1)), "radius": 0.035, "mat": "Aluminium",
              "segments": 24, "obj": "fittings"})
    eye = add(add(tack, mul(d, (sw0 + sw1) / 2)), mul(e2 if e2[0] < 0 else mul(e2, -1), 0.045))
    P.append({"kind": "torus", "centre": eye, "axis": (0, 1, 0), "R": 0.014, "r": 0.005, "mat": "Stainless", "n": 16,
              "m": 6, "obj": "fittings"})
    # the foil up to its top cap, the top swivel on it, the bare wire to the hounds
    f0 = add(tack, mul(d, sw1))
    f1 = forestay_at(FS["foil_top_z"])
    fa, fb = FS["foil"]
    foil_prof = [(fa / 2 * math.cos(a), fb / 2 * math.sin(a) * (1 - 0.35 * max(0.0, -math.cos(a)))) for a in
                 (TAU * k / 16 for k in range(16))]
    fx = unit(cross((0, 1, 0), d))                       # the foil's chord fore and aft, square to the stay
    P.append({"kind": "rings", "obj": "wires", "mat": "Aluminium", "smooth": True,
              "rings": [ring(c, fx, (0, 1, 0), foil_prof) for c in (f0, f1)]})
    P.append({"kind": "rings", "obj": "wires", "mat": "BlackPlastic", "smooth": True,
              "rings": [ring(add(f1, mul(d, s)), fx, (0, 1, 0), [(a * k, b * k) for a, b in foil_prof])
                        for s, k in ((-0.04, 1.15), (0.0, 1.15), (0.02, 0.7))]})
    tsw = FS["top_swivel"]
    z_head = tsw["head_z"]
    t0, t1 = forestay_at(z_head - 0.06), forestay_at(z_head - 0.06 + tsw["length"])
    P.append({"kind": "cyl", "a": t0, "b": t1, "radius": tsw["diameter"] / 2, "mat": "Aluminium", "segments": 20,
              "obj": "wires"})
    aftv = mul(fx, -1.0) if fx[0] > 0 else fx
    head_eye = add(forestay_at(z_head), mul(aftv, tsw["diameter"] / 2 + 0.012))
    hal_eye = add(forestay_at(z_head - 0.06 + tsw["length"] - 0.03), mul(aftv, tsw["diameter"] / 2 + 0.012))
    for e in (head_eye, hal_eye):
        P.append({"kind": "torus", "centre": e, "axis": (0, 1, 0), "R": 0.012, "r": 0.004, "mat": "Stainless", "n": 16,
                  "m": 6, "obj": "wires"})
    # top toggle and swage at the hounds' tang
    tg = sub(head, mul(d, 0.06))
    sl = sub(tg, mul(d, 0.09))
    P.append({"kind": "rings", "obj": "wires", "mat": "Stainless", "smooth": True,
              "rings": [ring(c, mul(e1, 0.018), mul(e2, 0.012), rrect(1, 1, 0.3)) for c in (head, tg)]})
    P.append({"kind": "cyl", "a": tg, "b": sl, "radius": WR["forestay"] * 1.7, "mat": "Stainless", "segments": 12,
              "obj": "wires"})
    P.append(rope([f1, sl], WR["forestay"] / 2, mat="Stainless", obj="wires", sides=8))
    return P, head_eye, hal_eye, eye


def forestay_eyes():
    """The furler's eyes a jib hooks to (game frame): its head's (under the top swivel), the halyard's (over it) and
    its tack's (on the tack swivel, aft)."""
    _, head_eye, hal_eye, tack_eye = forestay_parts()
    return head_eye, hal_eye, tack_eye


def hounds_tang():
    """The forestay's tang: a strap down each side of the mast's front, riveted on, the pin between them."""
    P = []
    hx = hounds_pin()
    for s in (-1, 1):
        t = s * 0.55
        c = mast_point(t, HOUNDS_Z - 0.06)
        y = s * (abs(c[1]) + 0.003)
        outline = [(c[0] - 0.05, HOUNDS_Z - 0.2), (c[0] + 0.01, HOUNDS_Z - 0.2), (hx[0] + 0.022, HOUNDS_Z - 0.02),
                   (hx[0] + 0.022, HOUNDS_Z + 0.02), (hx[0] - 0.01, HOUNDS_Z + 0.035), (c[0] - 0.05, HOUNDS_Z + 0.02)]
        P.append({"kind": "rings", "obj": "mast", "mat": "Stainless", "smooth": False,
                  "rings": [[(x, y + s * o, z) for x, z in outline] for o in (0.0, 0.008)]})
    P.append({"kind": "cyl", "a": (hx[0], -0.075, HOUNDS_Z), "b": (hx[0], 0.075, HOUNDS_Z), "radius": 0.008,
              "mat": "Stainless", "segments": 12, "obj": "mast"})
    return P


def standing_rigging():
    P = []
    for s in (1, -1):
        root, tip, upper = spreader_tip(s)
        P += spreader_parts(s)
        # the cap: from its T-ball at the hounds over the tip to the turnbuckle
        t_h = mast_t_toward(tip, HOUNDS_Z)
        tb, start = tball(t_h, HOUNDS_Z - 0.03, tip, WR["cap"] / 2)
        P += tb
        cps, pin, wend = chainplate((CP["cap"][0], s * CP["cap"][1]), tip, WR["cap"])
        P += cps
        P.append(rope([start, tip, wend], WR["cap"] / 2, mat="Stainless", obj="wires"))
        # the lower: from its T-ball under the spreader to its turnbuckle
        lxy = (CP["lower"][0], s * CP["lower"][1])
        far = (lxy[0], lxy[1], S.deck_z(lxy[0], 0.8))
        t_l = mast_t_toward(far, RG["lower_tang_z"])
        tb, start = tball(t_l, RG["lower_tang_z"], far, WR["lower"] / 2)
        P += tb
        cps, pin, wend = chainplate(lxy, start, WR["lower"])
        P += cps
        P.append(rope([start, wend], WR["lower"] / 2, mat="Stainless", obj="wires"))
    return P


# ---- on the mast ----

def masthead_parts():
    P = []
    zc = TRUCK_Z - 0.06
    cx, a, b = section(zc)
    # the cap: a cast sleeve over the truck with a domed top plate
    P.append({"kind": "rings", "obj": "mast", "mat": "Aluminium", "smooth": True,
              "rings": [[mast_point(TAU * k / 40, z, g) for k in range(40)] for z, g in
                        ((zc, 0.004), (TRUCK_Z - 0.012, 0.004), (TRUCK_Z, -0.01))]})
    # the crane aft: a cantilever in side view, rounded about the sheaves' axle at its end
    ax0 = aft_x() + 0.02
    ex = aft_x() - MH["crane_aft"]
    hz = MH["crane_height"]
    sx, sz = ex + 0.05, TRUCK_Z - 0.05
    side = [(ax0, TRUCK_Z), (ax0, TRUCK_Z - hz - 0.04)]
    side += [(sx + 0.05 * math.cos(t), sz + 0.05 * math.sin(t)) for t in
             [-0.6 * math.pi - 0.4 * math.pi * k / 6 for k in range(7)]]
    side += [(sx + 0.05 * math.cos(t), sz + 0.05 * math.sin(t)) for t in [-math.pi + 0.9 * math.pi * k / 8 for k in range(1, 9)]]
    w = MH["crane_width"] / 2
    P.append({"kind": "rings", "obj": "mast", "mat": "Aluminium", "smooth": False,
              "rings": [[(x, y, z) for x, z in side] for y in (-w, w)]})
    sheaves = []
    for y in (-0.017, 0.017):
        P.append({"kind": "cyl", "a": (sx, y - 0.006, sz), "b": (sx, y + 0.006, sz), "radius": 0.046, "mat": "BlackPlastic",
                  "segments": 24, "obj": "mast"})
        sheaves.append((sx, y, sz))
    P.append({"kind": "cyl", "a": (sx, -w - 0.004, sz), "b": (sx, w + 0.004, sz), "radius": 0.008, "mat": "Stainless",
              "segments": 12, "obj": "mast"})
    # the all-round white light on the cap, the VHF whip aft, the wind instrument forward, a wind indicator to port
    ctop = (cx, 0.0, TRUCK_Z)
    P.append({"kind": "cyl", "a": ctop, "b": add(ctop, (0, 0, 0.03)), "radius": 0.03, "mat": "BlackPlastic", "segments": 16,
              "obj": "mast"})
    P.append({"kind": "cyl", "a": add(ctop, (0, 0, 0.03)), "b": add(ctop, (0, 0, 0.1)), "radius": 0.036,
              "mat": "WhitePlastic", "segments": 20, "obj": "mast"})
    P.append({"kind": "cyl", "a": add(ctop, (0, 0, 0.1)), "b": add(ctop, (0, 0, 0.115)), "radius": 0.038,
              "mat": "BlackPlastic", "segments": 20, "obj": "mast"})
    am = (ax0 - 0.08, 0.0, TRUCK_Z)
    P.append({"kind": "cyl", "a": am, "b": add(am, (0, 0, 0.05)), "radius": 0.014, "mat": "Stainless", "segments": 10,
              "obj": "mast"})
    whip = [add(am, (0, 0, 0.05 + MH["antenna"] * k / 6)) for k in range(7)]
    P.append({"kind": "rings", "obj": "mast", "mat": "WhitePlastic", "smooth": True,
              "rings": [ring(p, (1, 0, 0), (0, 1, 0), circle(0.009 - 0.0055 * k / 6, 8)) for k, p in enumerate(whip)]})
    fx = front_x(TRUCK_Z - 0.03)
    p0 = (fx - 0.01, 0.0, TRUCK_Z - 0.03)
    pd = unit((math.cos(math.radians(28)), 0.0, math.sin(math.radians(28))))
    p1 = add(p0, mul(pd, MH["wind_pole"]))
    P.append({"kind": "cyl", "a": p0, "b": p1, "radius": 0.011, "mat": "CarbonMatte", "segments": 10, "obj": "mast"})
    P.append({"kind": "cyl", "a": add(p1, (-0.03, 0, 0)), "b": add(p1, (0.1, 0, 0)), "radius": 0.022, "mat": "BlackPlastic",
              "segments": 14, "obj": "mast"})
    P.append({"kind": "rings", "obj": "mast", "mat": "BlackPlastic", "smooth": False,
              "rings": [[(p1[0] - 0.03 + a, y, p1[2] + 0.015 + b) for a, b in
                         [(0.0, 0.0), (-0.16, 0.02), (-0.17, 0.09), (-0.1, 0.1), (0.0, 0.04)]] for y in (-0.002, 0.002)]})
    hub = add(p1, (0.12, 0, 0.0))
    P.append({"kind": "cyl", "a": add(p1, (0.1, 0, 0)), "b": hub, "radius": 0.006, "mat": "BlackPlastic", "segments": 8,
              "obj": "mast"})
    for k in range(3):
        a = TAU * k / 3
        arm = add(hub, (0.0, 0.07 * math.cos(a), 0.07 * math.sin(a)))
        P.append({"kind": "cyl", "a": hub, "b": arm, "radius": 0.003, "mat": "BlackPlastic", "segments": 6, "obj": "mast"})
        P.append({"kind": "rings", "obj": "mast", "mat": "BlackPlastic", "smooth": True,
                  "rings": [ring(add(arm, (dx, 0, 0)), (0, math.cos(a + 1.57), math.sin(a + 1.57)), (0, math.cos(a), math.sin(a)),
                                 circle(r, 10)) for dx, r in ((-0.02, 0.004), (-0.012, 0.016), (0.012, 0.022), (0.014, 0.0))]})
    wi0 = mast_point(-math.pi / 2, TRUCK_Z - 0.02, 0.0)
    wi1 = add(wi0, (0.12, -0.2, 0.18))
    P.append({"kind": "cyl", "a": wi0, "b": wi1, "radius": 0.004, "mat": "Stainless", "segments": 6, "obj": "mast"})
    P.append({"kind": "rings", "obj": "mast", "mat": "RedPlastic", "smooth": False,
              "rings": [[(wi1[0] + a, wi1[1] + o, wi1[2] + b) for a, b in [(0.0, -0.02), (-0.13, -0.03), (-0.13, 0.03), (0.0, 0.02)]]
                        for o in (-0.001, 0.001)]})
    for s in (-1, 1):
        arm = add(wi1, (-0.04, 0, 0))
        P.append({"kind": "cyl", "a": arm, "b": add(arm, (-0.09, s * 0.08, 0)), "radius": 0.0025, "mat": "Stainless",
                  "segments": 6, "obj": "mast"})
    return P, sheaves


def code0_and_jib_boxes():
    P = []
    for z in (MH["code0_z"], MH["jib_halyard_z"]):
        P += sheave_box(0.0, z)
    zc = MH["code0_z"] + 0.07
    f = (front_x(zc), 0.0, zc)
    P.append({"kind": "torus", "centre": add(f, (0.035, 0, 0)), "axis": (0, 1, 0), "R": 0.025, "r": 0.006,
              "mat": "Stainless", "n": 18, "m": 6, "obj": "mast"})
    return P


def radar_and_lights():
    P = []
    z = FM["radar_z"]
    fx = front_x(z)
    depth = FM["radar_diameter"] / 2 + 0.07
    # a collar round the mast's front half, the platform, the strut under it, the dome
    P.append(band(z - 0.11, z - 0.005, 0.004, -0.65 * math.pi, 0.65 * math.pi, 32, "Aluminium"))
    P.append({"kind": "box", "lo": (fx - 0.02, -0.17, z - 0.015), "hi": (fx + depth + 0.16, 0.17, z), "round": 0.01,
              "mat": "Aluminium", "obj": "mast"})
    for s in (-1, 1):
        P.append({"kind": "cyl", "a": (fx + 0.003, s * 0.06, z - 0.48), "b": (fx + depth + 0.1, s * 0.1, z - 0.02),
                  "radius": 0.012, "mat": "Aluminium", "segments": 10, "obj": "mast"})
    P.append(band(z - 0.52, z - 0.44, 0.004, -0.6 * math.pi, 0.6 * math.pi, 32, "Aluminium"))
    rd, rh = FM["radar_diameter"] / 2, FM["radar_height"]
    c = (fx + depth, 0.0, z)
    prof = [(0.0, 0.11), (0.012, rd * 0.62), (0.03, rd * 0.99), (0.06, rd), (rh * 0.72, rd * 0.98), (rh * 0.86, rd * 0.85),
            (rh * 0.96, rd * 0.55), (rh, 0.05)]
    P.append({"kind": "rings", "obj": "mast", "mat": "WhitePlastic", "smooth": True,
              "rings": [ring(add(c, (0, 0, h)), (1, 0, 0), (0, 1, 0), circle(r, 36)) for h, r in prof]})
    # the deck light (and steaming light) under the platform, aimed forward and down at the foredeck
    zl = FM["deck_light_z"]
    fl = front_x(zl)
    P += [plate_on_mast(0.0, zl, 0.07, 0.12, 0.012, "Aluminium")]
    lo, hi = (fl + 0.012, -0.055, zl - 0.04), (fl + 0.09, 0.055, zl + 0.04)
    P.append({"kind": "box", "lo": lo, "hi": hi, "round": 0.012, "mat": "WhitePlastic", "obj": "mast"})
    P.append({"kind": "box", "lo": (hi[0] - 0.004, -0.045, zl - 0.03), "hi": (hi[0] + 0.003, 0.045, zl + 0.018),
              "round": 0.004, "mat": "CabinWindow", "obj": "mast"})
    return P


def gooseneck_parts():
    """The gooseneck's bracket on the mast's aft face, its cheeks and vertical pin, and a reef horn each side."""
    P = []
    ax = aft_x()
    P.append({"kind": "box", "lo": (ax - 0.012, -0.05, PIN_Z - 0.17), "hi": (ax + 0.004, 0.05, PIN_Z + 0.13),
              "round": 0.01, "mat": "Aluminium", "obj": "mast"})
    for dz in (-0.05, 0.045):
        P.append({"kind": "rings", "obj": "mast", "mat": "Aluminium", "smooth": False,
                  "rings": [[(x, y, PIN_Z + dz + o) for x, y in
                             [(ax - 0.01, -0.045), (PIN_X + 0.01, -0.035), (PIN_X - 0.025, -0.02), (PIN_X - 0.025, 0.02),
                              (PIN_X + 0.01, 0.035), (ax - 0.01, 0.045)]] for o in (0.0, 0.014)]})
    P.append({"kind": "cyl", "a": (PIN_X, 0, PIN_Z - 0.06), "b": (PIN_X, 0, PIN_Z + 0.075), "radius": 0.011,
              "mat": "Stainless", "segments": 12, "obj": "mast"})
    for s in (-1, 1):
        base = (ax - 0.01, s * 0.05, PIN_Z + 0.08)
        pts = [base] + [add(base, (-0.012 * k, s * 0.006 * k, 0.012 * k)) for k in range(1, 4)]
        # the horn: a quarter turn from the stem's aft run up to its upright tip, which the cringle drops over
        horn = [add(pts[-1], (-0.025 * math.sin(a), s * 0.006 * a, 0.025 * (1 - math.cos(a))))
                for a in (math.pi / 2 * k / 8 for k in range(9))]
        P.append({"kind": "rings", "obj": "mast", "mat": "Stainless", "smooth": True,
                  "rings": tube(pts + horn[1:], 0.006, 8)})
    return P


# ---- the boom ----

def boom_z():
    return PIN_Z


def boom_rings():
    h, w = BO["height"], BO["width"]
    prof = rrect(w, h, 0.04, 4)
    x0, x1 = PIN_X - 0.065, BO["end_x"] + 0.06
    return [[(x, a, PIN_Z + b) for a, b in prof] for x in (x0, x1)]


def boom_parts():
    P = [{"kind": "rings", "rings": boom_rings(), "mat": PAINT, "smooth": True, "obj": "boom"}]
    h, w = BO["height"], BO["width"]
    # the forward casting with the gooseneck's tongue round the pin and the fork's horizontal pin
    fx0, fx1 = PIN_X - 0.03, PIN_X - 0.2
    cast = rrect(w + 0.01, h + 0.01, 0.045, 4)
    P.append({"kind": "rings", "obj": "boom", "mat": "Aluminium", "smooth": True,
              "rings": [[(x, a * k, PIN_Z + b * k) for a, b in cast] for x, k in
                        ((fx0, 0.55), (fx0 - 0.025, 0.95), (fx1, 1.0))]})
    P.append({"kind": "box", "lo": (PIN_X - 0.045, -0.03, PIN_Z - 0.03), "hi": (PIN_X + 0.022, 0.03, PIN_Z + 0.03),
              "round": 0.012, "mat": "Aluminium", "obj": "boom"})
    P.append({"kind": "cyl", "a": (PIN_X - 0.04, -0.045, PIN_Z), "b": (PIN_X - 0.04, 0.045, PIN_Z), "radius": 0.009,
              "mat": "Stainless", "segments": 12, "obj": "boom"})
    # the reef lines' and outhaul's exits under the forward casting
    for y in (-0.03, 0.0, 0.03):
        P.append({"kind": "box", "lo": (fx1 + 0.03, y - 0.008, PIN_Z - h / 2 - 0.007), "hi": (fx1 + 0.11, y + 0.008, PIN_Z - h / 2 + 0.002),
                  "round": 0.003, "mat": "BlackPlastic", "obj": "boom"})
    # the end casting: rounded aft, the outhaul's sheave slot, the topping lift's eye
    ex = BO["end_x"]
    P.append({"kind": "rings", "obj": "boom", "mat": "Aluminium", "smooth": True,
              "rings": [[(x, a * k, PIN_Z + b * k) for a, b in cast] for x, k in
                        ((ex + 0.1, 1.0), (ex + 0.02, 0.98), (ex, 0.85), (ex - 0.012, 0.5))]})
    P.append({"kind": "box", "lo": (ex - 0.014, -0.008, PIN_Z - 0.06), "hi": (ex + 0.002, 0.008, PIN_Z + 0.04),
              "round": 0.004, "mat": "BlackPlastic", "obj": "boom"})
    eye = (ex + 0.05, 0.0, PIN_Z + h / 2 + 0.018)
    P.append({"kind": "torus", "centre": eye, "axis": (0, 1, 0), "R": 0.014, "r": 0.005, "mat": "Stainless", "n": 16,
              "m": 6, "obj": "boom"})
    # the outhaul's car on the boom's top track at the clew
    cx = BO["clew_x"]
    P.append({"kind": "box", "lo": (cx - 0.06, -0.025, PIN_Z + h / 2 - 0.002), "hi": (cx + 0.06, 0.025, PIN_Z + h / 2 + 0.02),
              "round": 0.008, "mat": "Aluminium", "obj": "boom"})
    P.append({"kind": "box", "lo": (BO["end_x"] + 0.1, -0.012, PIN_Z + h / 2 - 0.004), "hi": (PIN_X - 0.25, 0.012, PIN_Z + h / 2 + 0.006),
              "round": 0.003, "mat": "Aluminium", "obj": "boom"})
    for s in (-1, 1):
        P.append({"kind": "box", "lo": (cx - 0.01, s * 0.025 - 0.004, PIN_Z + h / 2 + 0.01), "hi": (cx + 0.03, s * 0.025 + 0.004, PIN_Z + h / 2 + 0.055),
                  "round": 0.003, "mat": "Stainless", "obj": "boom"})
    P.append({"kind": "cyl", "a": (cx + 0.01, -0.035, PIN_Z + h / 2 + 0.04), "b": (cx + 0.01, 0.035, PIN_Z + h / 2 + 0.04),
              "radius": 0.006, "mat": "Stainless", "segments": 10, "obj": "boom"})
    # the mainsheet's bail round the boom's underside and the upper fiddle hanging from it
    mx = BO["mainsheet_x"]
    bail = []
    for k in range(13):
        a = math.pi * k / 12
        bail.append((mx, (w / 2 + 0.006) * math.cos(a), PIN_Z - (h / 2 + 0.006) * math.sin(a) * 0.9 - 0.02))
    for x0 in (mx - 0.02, mx + 0.02):
        P.append({"kind": "rings", "obj": "boom", "mat": "Stainless", "smooth": True,
                  "rings": tube([(x0, p[1], p[2]) for p in bail], 0.006, 6)})
    eye = (mx, 0.0, PIN_Z - h / 2 - 0.035)
    P.append({"kind": "cyl", "a": (mx - 0.025, 0, eye[2] + 0.012), "b": (mx + 0.025, 0, eye[2] + 0.012), "radius": 0.007,
              "mat": "Stainless", "segments": 10, "obj": "boom"})
    top = kit("Fiddle40", (mx, 0.0, eye[2]), (1, 0, 0), (0, 0, 1), light=0.25, obj="boom", size="57")
    P.append(top)
    P += reef_exit_parts()
    return P, top


def reef_exits():
    """[(sheave's line point, dead end's eye)] on the boom's top for the reef lines (game frame, boom at 0): the line
    comes out of its box on the port half of the top and dead-ends on a padeye on the starboard half."""
    zt = PIN_Z + BO["height"] / 2
    return [((x, -0.025, zt + 0.012), (x + 0.04, 0.03, zt + 0.014)) for x in BO["reef_exits_x"]]


def reef_exit_parts():
    P = []
    zt = PIN_Z + BO["height"] / 2
    for (sx, sy, _), (ex, ey, ez) in reef_exits():
        P.append({"kind": "box", "lo": (sx - 0.05, sy - 0.013, zt - 0.004), "hi": (sx + 0.05, sy + 0.013, zt + 0.004),
                  "round": 0.003, "mat": "Stainless", "obj": "boom"})
        P.append({"kind": "box", "lo": (sx - 0.032, sy - 0.006, zt - 0.002), "hi": (sx + 0.032, sy + 0.006, zt + 0.0045),
                  "round": 0.002, "mat": "BlackPlastic", "obj": "boom"})
        P.append({"kind": "cyl", "a": (sx, sy - 0.004, zt + 0.004), "b": (sx, sy + 0.004, zt + 0.004), "radius": 0.022,
                  "mat": "BlackPlastic", "segments": 20, "obj": "boom"})
        P.append({"kind": "box", "lo": (ex - 0.022, ey - 0.012, zt - 0.002), "hi": (ex + 0.022, ey + 0.012, zt + 0.004),
                  "round": 0.004, "mat": "Stainless", "obj": "boom"})
        P.append({"kind": "torus", "centre": (ex, ey, zt + 0.014), "axis": (0, 1, 0), "R": 0.009, "r": 0.003,
                  "mat": "Stainless", "n": 14, "m": 6, "obj": "boom"})
    return P


def boom_clew():
    return (BO["clew_x"] + 0.01, 0.0, PIN_Z + BO["height"] / 2 + 0.04)


# ---- the fittings on the roof ----

def jib_track_pts(n=44):
    r, hs = JT["radius"], JT["half_span"]
    pm = math.asin(hs / r)
    return [(B.CB["x"] - r * math.cos(p), r * math.sin(p)) for p in (-pm + 2 * pm * k / n for k in range(n + 1))]


def jib_track_parts():
    P = []
    w, hgt = JT["width"], JT["height"]
    prof = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, 0.01), (0.012, 0.012), (0.014, hgt), (-0.014, hgt), (-0.012, 0.012),
            (-w / 2, 0.01)]
    pts = jib_track_pts()
    rings = []
    for x, y in pts:
        rad = unit((B.CB["x"] - x, -y, 0.0))
        z0 = roof_z(y) - 0.002
        rings.append([(x + rad[0] * a, y + rad[1] * a, z0 + b) for a, b in prof])
    P.append({"kind": "rings", "rings": rings, "mat": "Aluminium", "smooth": False, "obj": "fittings"})
    for (x, y), (x2, y2) in ((pts[0], pts[1]), (pts[-1], pts[-2])):
        d = unit((x2 - x, y2 - y, 0.0))
        c = (x - d[0] * 0.02, y - d[1] * 0.02, roof_z(y))
        P.append({"kind": "rings", "obj": "fittings", "mat": "BlackPlastic", "smooth": True,
                  "rings": [ring((c[0], c[1], c[2] + z), d, cross((0, 0, 1), d), rrect(0.07, 0.06, 0.015)) for z in (-0.002, 0.04)]})
    return P


def jib_car(y=0.0):
    """The self-tacking jib's car at y on its track: a body over the track, two cheeks and a sheave whose axle runs
    along the track (the sheet comes down from the clew and goes on aft and up to the mast). Returns (parts, sheave
    centre, the sheave's axle, its line radius)."""
    r = JT["radius"]
    p = math.asin(y / r)
    c = (B.CB["x"] - r * math.cos(p), y, roof_z(y) + JT["height"])
    along = unit((math.sin(p) * 1.0, math.cos(p), 0.0))
    rad = (-math.cos(p), math.sin(p), 0.0)
    P = [{"kind": "rings", "obj": "fittings", "mat": "Aluminium", "smooth": True,
          "rings": [ring(add(c, (0, 0, z)), along, (rad[0], rad[1], 0.0), rrect(0.17, 0.075, 0.02)) for z in (-0.012, 0.028)]}]
    sc = add(c, (0, 0, 0.075))
    for s in (-1, 1):
        o = add(sc, mul(along, s * 0.022))
        P.append({"kind": "rings", "obj": "fittings", "mat": "Stainless", "smooth": True,
                  "rings": [ring(add(o, mul(along, s * f)), (1, 0, 0), (0, 0, 1),
                                 [(0.052 * math.cos(a), 0.052 * math.sin(a) * (0.75 if math.sin(a) < 0 else 1.0)) for a in
                                  (TAU * k / 20 for k in range(20))]) for f in (-0.003, 0.003)]})
    P.append({"kind": "cyl", "a": add(sc, mul(along, -0.018)), "b": add(sc, mul(along, 0.018)), "radius": 0.042,
              "mat": "BlackPlastic", "segments": 28, "obj": "fittings"})
    P.append({"kind": "cyl", "a": add(sc, mul(along, -0.03)), "b": add(sc, mul(along, 0.03)), "radius": 0.008,
              "mat": "Stainless", "segments": 10, "obj": "fittings"})
    return P, sc, along, 0.042 + HL["rope"]["sheet"] / 2


def eye_strap(c, along):
    """A stainless eye strap on the roof at c, its loop along 'along' (the line of pull's plan direction)."""
    side = unit(cross((0, 0, 1), along))
    P = [{"kind": "rings", "obj": "fittings", "mat": "Stainless", "smooth": False,
          "rings": [ring((c[0], c[1], c[2] + z), along, side, rrect(0.055, 0.026, 0.01)) for z in (-0.002, STRAP)]}]
    P.append({"kind": "rings", "obj": "fittings", "mat": "Stainless", "smooth": True,
              "rings": tube([add(c, add(mul(along, -0.013 * math.cos(a)), (0, 0, STRAP + 0.013 * math.sin(a))))
                             for a in (math.pi * k / 10 for k in range(11))], 0.0035, 8)})
    return P


def step_parts():
    """The mast's cast step on the roof: a plate round the heel with a lip."""
    P = []
    rings = [[mast_point(TAU * k / 40, ROOF_Z - 0.003, 0.05)[:2] + (z,) for k in range(40)] for z in (ROOF_Z - 0.003,)]
    rings += [[mast_point(TAU * k / 40, ROOF_Z, g)[:2] + (z,) for k in range(40)] for z, g in
              ((ROOF_Z + 0.012, 0.05), (ROOF_Z + 0.022, 0.03), (HEEL_Z + 0.015, 0.008))]
    P.append({"kind": "rings", "rings": rings, "mat": "Aluminium", "smooth": True, "obj": "fittings"})
    return P


def winch(c, toward):
    """A winch on the roof at c (plan), its self-tailer's stripper arm toward 'toward' (plan)."""
    z = roof_z(c[1])
    ax = unit((toward[0] - c[0], toward[1] - c[1], 0.0))
    return kit("Winch70", (c[0], c[1], z - 0.002), ax, (0, 0, 1), size=HL["winch_size"])


def winch_wraps(w, come_from, r_rope, turns=3.0):
    """A line onto a winch from come_from (a point): on the drum's tangent, three turns clockwise seen from above
    (the game's frame: plan angle atan2(y, x) increasing) up the drum, up into the self-tailer's jaws and off its
    stripper arm. Returns (the line from come_from, the tail's start over the arm's end)."""
    k = KIT_SIZE[("Winch70", HL["winch_size"])]
    o = w["origin"]
    R = 0.098 * k + r_rope
    z0 = o[2] + 0.075 * k
    th = 0.0
    for _ in range(4):
        cpt = (o[0] + R * math.cos(th), o[1] + R * math.sin(th))
        d = unit((cpt[0] - come_from[0], cpt[1] - come_from[1], 0.0))
        th = math.atan2(-d[0], d[1])
    pts = [come_from]
    n = int(24 * turns)
    pitch = 2.1 * r_rope
    for i in range(n + 1):
        t = th + TAU * turns * i / n
        pts.append((o[0] + R * math.cos(t), o[1] + R * math.sin(t), z0 + pitch * turns * i / n))
    ts = math.atan2(w["ax"][1], w["ax"][0])
    t_end = th + TAU * turns
    while ts < t_end + 0.8 * math.pi:
        ts += TAU
    Rj = 0.106 * k
    zj = o[2] + 0.24 * k
    m = 16
    for i in range(1, m + 1):
        f = i / m
        t = t_end + (ts - t_end) * f
        rr = R + (Rj - R) * min(1.0, f * 2)
        pts.append((o[0] + rr * math.cos(t), o[1] + rr * math.sin(t), pts[-1][2] + (zj - pts[-1][2]) * min(1.0, f * 2.5)))
    arm = add(o, mul(w["ax"], 0.155 * k))
    arm = (arm[0], arm[1], zj + 0.004)
    pts.append(arm)
    return pts, arm


def tail_off(start, heading, z_roof, r_rope, length=0.35):
    """A line's tail from start, falling to the roof and lying along heading."""
    h = unit((heading[0], heading[1], 0.0))
    p1 = add(start, mul(h, 0.06))
    p2 = (p1[0] + h[0] * 0.1, p1[1] + h[1] * 0.1, z_roof + r_rope + 0.03)
    p3 = (p2[0] + h[0] * 0.08, p2[1] + h[1] * 0.08, z_roof + r_rope)
    p4 = (p3[0] + h[0] * length, p3[1] + h[1] * length, z_roof + r_rope)
    return [start, p1, p2, p3, p4]


# ---- the lines ----

MAST_LINES = ["main_halyard", "topping_lift", "jib_halyard", "code0_halyard", "jib_sheet"]
BOOM_LINES = ["reef_1", "reef_2", "outhaul"]


def helm_layout():
    """The forward winch, the mast base's row of turning blocks and the bank of eight clutches between them, all on
    one heading across the roof."""
    wf = tuple(HL["winch_fwd"])
    mc = (MAST_X, 0.0)
    head = unit((wf[0] - mc[0], wf[1] - mc[1], 0.0))
    row_c = (mc[0] + head[0] * HL["base_row"]["distance"], mc[1] + head[1] * HL["base_row"]["distance"])
    across = (-head[1], head[0], 0.0)
    bank_c = (row_c[0] + head[0] * HL["bank_from_row"], row_c[1] + head[1] * HL["bank_from_row"])
    return head, across, row_c, bank_c


def lines_and_blocks():
    """The mast's lines (exits, turning blocks, clutches, winch) and the aft lines (traveller, mainsheet), as parts."""
    P = []
    head, across, row_c, bank_c = helm_layout()
    rr = HL["rope"]
    n = len(MAST_LINES) + len(BOOM_LINES)
    sp = HL["base_row"]["spacing"]
    # the row of blocks, across the heading: the boom's three at the end nearest the boom's exits (aft)
    row = [(row_c[0] + across[0] * sp * (i - (n - 1) / 2), row_c[1] + across[1] * sp * (i - (n - 1) / 2)) for i in range(n)]
    boom_end = (PIN_X - 0.16, 0.0)
    if math.hypot(row[0][0] - boom_end[0], row[0][1] - boom_end[1]) < math.hypot(row[-1][0] - boom_end[0], row[-1][1] - boom_end[1]):
        row = row[::-1]
    names = MAST_LINES + BOOM_LINES                      # row[0..4] the mast's, row[5..7] the boom's
    # the bank: its slots in the row's order, its X toward the winch
    bank = kit("ClutchBank", (bank_c[0], bank_c[1], roof_z(bank_c[1]) - 0.002), head, (0, 0, 1), count=n)
    slot_pts = sorted(bank["expect"].items(), key=lambda kv: dot(sub(kv[1][:2] + (0,), bank_c + (0,)), across))
    row_order = sorted(range(n), key=lambda i: dot(sub(row[i] + (0,), row_c + (0,)), across))
    slot_of = {row_order[j]: slot_pts[j][1] for j in range(n)}
    P.append(bank)
    wfk = winch(tuple(HL["winch_fwd"]), (-2.36, -2.4))
    P.append(wfk)
    ends = {}
    boom_exits = [(PIN_X - 0.16 - 0.07, y, PIN_Z - BO["height"] / 2 - 0.004) for y in (-0.03, 0.0, 0.03)]
    k57 = KIT_SIZE[("Block40", "57")]
    for i, nm in enumerate(names):
        bx, by = row[i]
        rz = roof_z(by)
        out_slot = slot_of[i]
        in_pt = add(out_slot, mul(head, -0.18))
        if i < len(MAST_LINES):
            t_ex = mast_t_toward((bx, by, 0.0), HEEL_Z + 0.4)
            z_ex = HEEL_Z + 0.36 + (0.17 if i % 2 else 0.0)
            P += sheave_box(t_ex, z_ex, 0.1, 0.038)
            exit_pt = add(mast_point(t_ex, z_ex - 0.035, 0.012), (0, 0, 0))
        else:
            exit_pt = boom_exits[i - len(MAST_LINES)]
        eye = (bx, by, rz + STRAP + 0.012)
        r = rr["sheet"] if nm == "jib_sheet" else rr["reef"] if nm.startswith("reef") or nm == "outhaul" else rr["halyard"]
        u_in = unit(sub(exit_pt, eye))
        u_out = head
        pull = unit(add(u_in, u_out))
        axle = unit(cross(u_in, u_out))
        ax, az = cross(axle, mul(pull, -1.0)), mul(pull, -1.0)
        blk = kit("Block40", eye, ax, az, light=0.18, size="57")
        P.append(blk)
        P += eye_strap((bx, by, rz), unit((pull[0], pull[1], 0.0)))
        C = blk["expect"]["Axle"]
        arc = wrap(exit_pt, C, axle, 0.02 * k57 + r - 0.002, in_pt)
        pts = [exit_pt] + arc + [in_pt, add(out_slot, mul(head, -0.09)), add(out_slot, (0, 0, 0))]
        ends[nm] = (pts, r, out_slot)
    # the jib sheet onto the forward winch; the others' tails out of their clutches
    for nm, (pts, r, out_slot) in ends.items():
        if nm == "jib_sheet":
            wr, tail0 = winch_wraps(wfk, out_slot, r)
            P.append(rope(pts + wr[1:], r))
            P.append(rope(tail_off(tail0, wfk["ax"], roof_z(tail0[1]), r), r))
        else:
            tl = tail_off(out_slot, head, roof_z(out_slot[1]), r, 0.3)
            P.append(rope(pts + tl[1:], r))
    return P, ends


def traveller_parts():
    """The traveller on the roof's aft end, the mainsheet's lower fiddle on its car, the tackle's four parts to the
    upper fiddle under the boom, and the tail and control lines forward to their clutches and the aft winch."""
    P = []
    L = TR["length"]
    x = TR["x"]
    zr = roof_z(0.0)
    trav = kit("TravellerHeavy", (x, 0.0, zr - 0.002), (0, 1, 0), (0, 0, 1), length=L)
    P.append(trav)
    car_top = (x, 0.0, zr - 0.002 + 0.075)
    low = kit("Fiddle40", car_top, (1, 0, 0), (0, 0, -1), light=0.25, size="57")
    P.append(low)
    _, top = boom_parts()
    k = KIT_SIZE[("Fiddle40", "57")]
    R = 0.02 * k
    rm = HL["rope"]["sheet"] / 2
    la = low["expect"]["Axle"]
    P += mainsheet_tackle(low, top)
    # the tail off the lower fiddle's big sheave, along the track to the port end's control box
    box_in = (x, -(L / 2 - 0.09), zr + 0.05)
    box_fwd = (x + 0.065, -(L / 2 - 0.045), zr + 0.045)
    tail = [add(la, (R, 0, 0)), add(la, (R + 0.01, -0.03, -0.02)), (x + 0.02, -0.25, zr + 0.11), (x + 0.02, box_in[1], zr + 0.05)]
    ctrl_p = [(x - 0.03, -0.13, zr + 0.05), (x - 0.03, box_in[1], zr + 0.05)]
    ctrl_s = [(x - 0.03, 0.13, zr + 0.05), (x - 0.03, L / 2 - 0.09, zr + 0.05)]
    ret_s = [(x - 0.075, L / 2 - 0.09, zr + 0.03), (x - 0.075, -(L / 2 - 0.09), zr + 0.03)]
    rc = HL["rope"]["control"] / 2
    P.append(rope(ctrl_s, rc))
    P.append(rope(ret_s, rc))
    # forward from the port box through the aft bank to the aft winch
    wa = tuple(HL["winch_aft"])
    wak = winch(wa, (-2.36, -2.4))
    P.append(wak)
    bank_c = (HL["aft_bank_x"], wa[1] - 0.098 * KIT_SIZE[("Winch70", HL["winch_size"])] - rm)
    head = unit((wa[0] - bank_c[0], 0.0, 0.0))
    bank = kit("ClutchBank", (bank_c[0], bank_c[1], roof_z(bank_c[1]) - 0.002), head, (0, 0, 1), count=3)
    P.append(bank)
    slots = sorted(bank["expect"].values(), key=lambda p: p[1])
    starts = [(box_fwd[0], box_fwd[1] - 0.025, zr + 0.045), (box_fwd[0], box_fwd[1], zr + 0.045), (box_fwd[0], box_fwd[1] + 0.025, zr + 0.045)]
    lines = [("traveller_port", ctrl_p, rc), ("mainsheet", tail, rm), ("traveller_stbd", ret_s[1:], rc)]
    for (nm, before, r), st, sl in zip(lines, starts, slots):
        in_pt = add(sl, (-0.18, 0, 0))
        pts = before + [st, add(st, (0.08, 0, 0)), in_pt, add(sl, (-0.09, 0, 0)), sl]
        if nm == "mainsheet":
            wr, tail0 = winch_wraps(wak, sl, r)
            P.append(rope(pts + wr[1:], r))
            P.append(rope(tail_off(tail0, wak["ax"], roof_z(tail0[1]), r), r))
        else:
            P.append(rope(pts + tail_off(sl, head, roof_z(sl[1]), r, 0.3)[1:], r))
    return P, trav, low, top


def mainsheet_tackle(low, top, beta=0.0, obj="mainsheet"):
    """The mainsheet's four parts from the lower fiddle (low, on the traveller's car amidships) to the upper (top, under
    the boom), the boom swung beta (radians) to port about the gooseneck's pin. The boom amidships's are their own
    object (L42_Mainsheet); sails_lagoon42.py draws them with each hoisted main's boom, the car left amidships and the
    sheet eased (slice 7)."""
    k = KIT_SIZE[("Fiddle40", "57")]
    R_, r2 = 0.02 * k, 0.013 * k
    rm = HL["rope"]["sheet"] / 2
    cb, sb = math.cos(beta), math.sin(beta)

    def sw(p):
        dx, dy = p[0] - PIN_X, p[1]
        return (PIN_X + dx * cb - dy * sb, dx * sb + dy * cb, p[2])
    ta, ta2 = top["expect"]["Axle"], top["expect"]["Axle2"]
    la, la2 = low["expect"]["Axle"], low["expect"]["Axle2"]
    return [rope([sw(add(a, (off, 0, 0))), add(b, (off, 0, 0))], rm, obj=obj)
            for a, b, off in ((ta2, la2, -r2), (ta2, la2, r2), (ta, la, -R_), (ta, la, R_))]


def mast_lines_up():
    """The halyards' runs outside the mast at the top: the topping lift to the boom's end (on the boom: the game swings
    them together) and the jib halyard to the top swivel. The main halyard's run to the main's head, the jib's car and
    its sheet up to the mast's box change with the sails' states: sails_lagoon42.py draws them with each state (slice 7)."""
    P = []
    _, _, hal_eye, _ = forestay_parts()
    _, sheaves = masthead_parts()
    s_main, s_lift = sheaves
    rr = HL["rope"]
    a = add(s_lift, (-0.046 - 0.005, 0, 0))
    b = (BO["end_x"] + 0.05, 0.0, PIN_Z + BO["height"] / 2 + 0.032)
    sag = [add(lerp(a, b, f), (0, 0, -0.18 * 4 * f * (1 - f))) for f in (k / 16 for k in range(17))]
    P.append(rope(sag, 0.004, obj="boom", sides=6))
    jx = (front_x(MH["jib_halyard_z"]) + 0.006, 0.0, MH["jib_halyard_z"] - 0.03)
    P.append(rope([jx, add(hal_eye, (0.0, 0.0, 0.012))], rr["halyard"] / 2))
    P += sheave_box(0.0, FM["jib_sheet_z"], 0.12, 0.045)
    return P


def main_halyard_from():
    """Where the main halyard leaves its masthead sheave, down the mast's aft face (game frame)."""
    _, sheaves = masthead_parts()
    return add(sheaves[0], (-0.046 - HL["rope"]["halyard"] / 2, 0, 0))


def jib_sheet_box():
    """Where the jib sheet goes into its box on the mast's front (the game's JibSheetMast)."""
    zb = FM["jib_sheet_z"]
    return (front_x(zb) + 0.006, 0.0, zb - 0.035)


def lazy_jack_parts():
    """The lazy jacks' fittings on the mast: each side a plate and eye with a block hanging from it at lazy_jack_z, and
    the line's tail from the block's sheave down the mast's side to a horn cleat at lazy_jack_cleat_z, made fast with
    figure-eight turns. Returns (parts, {side: the point where the jack leaves its sheave aft, toward the bag})."""
    P = []
    out = {}
    z, zc = FM["lazy_jack_z"], FM["lazy_jack_cleat_z"]
    r = FM["lazy_jack_rope"] / 2
    for s in (1, -1):
        t = s * (math.pi / 2 + 0.35)                         # on the mast's side, a little aft of its widest
        n = mast_normal(t, z)
        fwd = unit(cross(n, (0, 0, s * 1.0)))                  # along the mast's face, forward
        if fwd[0] < 0:
            fwd = mul(fwd, -1.0)
        P.append(plate_on_mast(t, z + 0.03, 0.03, 0.08, 0.004))
        eye = add(mast_point(t, z + 0.02), mul(n, 0.018))
        P.append({"kind": "torus", "centre": eye, "axis": fwd, "R": 0.011, "r": 0.0032, "mat": "Stainless", "n": 14,
                  "m": 6, "obj": "mast"})
        blk = kit("Block40", add(eye, (0, 0, -0.011)), fwd, (0, 0, 1), light=0.25, obj="mast")
        P.append(blk)
        ax = blk["expect"]["Axle"]
        R_ = 0.02 + r
        out[s] = add(ax, mul(fwd, -R_))
        # the horn cleat on the mast's side, its line made fast
        c = mast_point(t, zc)
        cn = mast_normal(t, zc)
        P.append(plate_on_mast(t, zc, 0.034, 0.13, 0.006, "Aluminium"))
        stem = add(c, mul(cn, 0.006))
        horn = add(c, mul(cn, 0.028))
        P.append({"kind": "cyl", "a": stem, "b": horn, "radius": 0.009, "mat": "Aluminium", "segments": 10, "obj": "mast"})
        P.append({"kind": "rings", "obj": "mast", "mat": "Aluminium", "smooth": True,
                  "rings": tube([add(horn, (0, 0, -0.075)), add(horn, (0, 0, -0.03)), add(horn, (0, 0, 0.03)),
                                 add(horn, (0, 0, 0.075))], 0.007, 10)})
        over = arc_pts(ax, mul(fwd, -1.0), (0, 0, 1), R_, 0.0, math.pi, 8)      # over the sheave, aft to forward
        down = add(over[-1], (0, 0, -0.05))
        side = unit(cross(cn, (0, 0, 1)))
        fig = [add(horn, add(mul(cn, 0.013 + 0.004 * math.sin(2 * a)), add(mul(side, 0.017 * math.sin(a)),
                                                                           (0, 0, 0.055 * math.cos(a)))))
               for a in (math.pi / 2 + TAU * k / 20 for k in range(41))]
        lead = add(horn, add(mul(cn, 0.013), (0, 0, 0.09)))
        tail = [add(fig[-1], add(mul(cn, 0.01), (0, 0, -0.03))), add(horn, add(mul(cn, 0.03), (0, 0, -0.14))),
                add(horn, add(mul(cn, 0.045), (0, 0, -0.42)))]
        P.append(rope(over + [down, lead] + fig + tail, r, obj="running", sides=6))
    return P, out


def parts():
    P = []
    P.append({"kind": "rings", "rings": mast_rings(), "mat": PAINT, "smooth": True, "obj": "mast"})
    P.append({"kind": "rings", "rings": track_rings(), "mat": "Aluminium", "smooth": False, "obj": "mast"})
    P += step_parts()
    mh, _ = masthead_parts()
    P += mh
    P += code0_and_jib_boxes()
    P += hounds_tang()
    P += radar_and_lights()
    P += gooseneck_parts()
    P += standing_rigging()
    fp, _, _, _ = forestay_parts()
    P += fp
    P += jib_track_parts()
    bp, _ = boom_parts()
    P += bp
    lp, _ = lines_and_blocks()
    P += lp
    tp, _, _, _ = traveller_parts()
    P += tp
    P += mast_lines_up()
    P += lazy_jack_parts()[0]
    return P


# ---- sockets ----

def sockets():
    """The game's sockets (Lagoon42_sockets.json's names): name -> (point, owner) in the game frame, metres; and each
    owner's origin."""
    so = {}
    hull, mast, boom = "SM_Lagoon42_Hull", "SM_Lagoon42_Mast", "SM_Lagoon42_Boom"
    so["MastStep"] = ((MAST_X, 0.0, HEEL_Z), hull)
    so["MastBase"] = ((MAST_X, 0.0, HEEL_Z), mast)
    so["Masthead"] = ((section(TRUCK_Z)[0], 0.0, TRUCK_Z), mast)
    _, sheaves = masthead_parts()
    so["MastheadAft"] = (sheaves[0][:1] + (0.0,) + sheaves[0][2:], mast)
    so["Hounds"] = (hounds_pin(), mast)
    for s, tag in ((1, "S"), (-1, "P")):
        so["SpreaderTip_" + tag] = (spreader_tip(s)[1], mast)
        so["ChainplateUpper_" + tag] = (chainplate((CP["cap"][0], s * CP["cap"][1]), spreader_tip(s)[1], WR["cap"])[1], hull)
        lxy = (CP["lower"][0], s * CP["lower"][1])
        so["ChainplateLower_" + tag] = (chainplate(lxy, (MAST_X, s * 0.08, RG["lower_tang_z"]), WR["lower"])[1], hull)
    so["LowerTang"] = ((MAST_X, 0.0, RG["lower_tang_z"]), mast)
    so["ForestayTack"] = (forestay_tack(), hull)
    so["JibSheetMast"] = ((front_x(FM["jib_sheet_z"]) + 0.006, 0.0, FM["jib_sheet_z"] - 0.035), mast)
    for s, tag in ((1, "S"), (-1, "P")):
        so["JibLead_" + tag] = (jib_car(s * JT["lead_y"])[1], hull)
        w = HL["winch_fwd"]
        so["JibWinch_" + tag] = ((w[0], w[1], roof_z(w[1]) + 0.06), hull)
    so["LazySheetVia"] = (jib_car(0.0)[1], hull)
    x, L = TR["x"], TR["length"]
    zr = roof_z(0.0)
    so["Traveler_C"] = ((x, 0.0, zr + 0.073), hull)
    so["Traveler_S"] = ((x, L / 2 - 0.09 - 0.13, zr + 0.073), hull)
    k = KIT_SIZE[("Fiddle40", "57")]
    so["MainsheetBlock"] = ((x, 0.0, zr + 0.073 + 0.0965 * k), hull)
    so["Boom_Mainsheet"] = ((BO["mainsheet_x"], 0.0, PIN_Z - BO["height"] / 2 - 0.035 - 0.0965 * k), boom)
    so["Boom_Clew"] = (boom_clew(), boom)
    so["Gooseneck"] = ((PIN_X, 0.0, PIN_Z), mast)
    for name, cy in (("RudderPivot", -H.HULL_Y), ("RudderPivot_1", H.HULL_Y)):
        so[name] = (A.rudder_pivot(cy), hull)
    origins = {hull: (0.0, 0.0, 0.0), mast: (MAST_X, 0.0, HEEL_Z), boom: (PIN_X, 0.0, PIN_Z),
               "SM_Lagoon42_Rudder": A.rudder_pivot(-H.HULL_Y)}
    return so, origins


def boom_stop():
    """How far (deg off the centreline) the boom swings before its side meets the starboard cap or lower at the
    boom's height, and which. The mainsheet stops it first if this is past the physics' MainMaxEaseDeg (65)."""
    root, tip, _ = spreader_tip(1)
    cap = (tip, chainplate((CP["cap"][0], CP["cap"][1]), tip, WR["cap"])[2])
    lxy = (CP["lower"][0], CP["lower"][1])
    far = (lxy[0], lxy[1], S.deck_z(lxy[0], 0.8))
    start = tball(mast_t_toward(far, RG["lower_tang_z"]), RG["lower_tang_z"], far, WR["lower"] / 2)[1]
    lower = (start, chainplate(lxy, start, WR["lower"])[2])
    best = (180.0, None)
    for name, (a, b) in (("cap", cap), ("lower", lower)):
        t = (a[2] - PIN_Z) / (a[2] - b[2])
        p = lerp(a, b, t)
        r = math.hypot(p[0] - PIN_X, p[1])
        if r < PIN_X - BO["end_x"]:
            ang = math.degrees(math.atan2(p[1], PIN_X - p[0]) - math.asin((BO["width"] / 2 + WR[name] / 2) / r))
            best = min(best, (ang, name))
    return best


def numbers():
    root, tip, upper = spreader_tip(1)
    L = norm(sub(tip, root))
    tilt_of = lambda tp: math.degrees(math.atan2(tp[2] - root[2], math.hypot(tp[0] - root[0], tp[1] - root[1])))
    tilt, tilt_b = tilt_of(tip), tilt_of(spreader_tip(1, bisect=True)[1])
    sweep = math.degrees(math.atan2(root[0] - tip[0], tip[1] - root[1]))
    head, across, row_c, bank_c = helm_layout()
    fs = sub(hounds_pin(), forestay_tack())
    return {"heel_z": HEEL_Z, "truck_z": TRUCK_Z, "mast_length": TRUCK_Z - HEEL_Z, "hounds_z": HOUNDS_Z,
            "fraction": (HOUNDS_Z - HEEL_Z) / (TRUCK_Z - HEEL_Z), "spreader_length": L, "spreader_tilt_deg": tilt, "bisecting_tilt_deg": tilt_b,
            "spreader_sweep_deg": sweep, "spreader_tip": tip, "forestay_length": norm(fs),
            "forestay_angle_deg": math.degrees(math.atan2(fs[2], -fs[0])), "boom_over_roof": PIN_Z - ROOF_Z,
            "boom_length": PIN_X - BO["end_x"], "lines_heading_deg": math.degrees(math.atan2(head[1], head[0])),
            "bank_c": bank_c, "row_c": row_c, "boom_stop_deg": boom_stop()[0], "boom_stop_wire": boom_stop()[1]}


if __name__ == "__main__":
    n = numbers()
    print(f"mast: heel {n['heel_z']:.3f}, truck {n['truck_z']:.3f} ({n['mast_length']:.2f} m), hounds {n['hounds_z']:.2f} "
          f"({n['fraction']:.2f} of the mast)")
    print(f"spreaders: {n['spreader_length']:.3f} m, swept {n['spreader_sweep_deg']:.1f} deg, tilted up "
          f"{n['spreader_tilt_deg']:.1f} deg (bisecting the cap: {n['bisecting_tilt_deg']:.1f}), tip {tuple(round(c, 3) for c in n['spreader_tip'])}")
    print(f"forestay: {n['forestay_length']:.2f} m at {n['forestay_angle_deg']:.1f} deg; boom {n['boom_length']:.2f} m, "
          f"{n['boom_over_roof']:.2f} m over the roof, stopped by the {n['boom_stop_wire']} at {n['boom_stop_deg']:.0f} deg")
    print(f"lines: heading {n['lines_heading_deg']:.1f} deg, blocks' row at {tuple(round(c, 3) for c in n['row_c'])}, "
          f"clutches at {tuple(round(c, 3) for c in n['bank_c'])}")
    so, _ = sockets()
    for k, (p, o) in sorted(so.items()):
        print(f"  {k:16s} {tuple(round(c, 3) for c in p)}  {o}")
