"""Snap shackle (part detail loop, Nov 2026: docs/part-detail-loop/snapshackle.md).

A 70 mm stainless snap shackle with a fixed eye, the kind on a small keelboat's spinnaker sheets, guys and halyard:
one forged body (a fixed oval eye at the bottom, a diagonal crossbar and a column that houses the spring plunger, ending
in a round latch boss at the top), a hinged bail of round bar that swings open from the crossbar's end and snaps shut
into the latch boss, a cross pin at the hinge and a pull ring on the plunger's lug that opens it under load.

Kept in its own file so several part threads can work at once; bk_parts imports every bk_part_*.py at the end.
Frame (bk_parts' rule): the origin is where the load bears inside the bail (a sail's clew ring sits there), the part
hangs along -Z from it with the eye at the bottom, X runs across the bail (hinge on +X, latch and pull ring on -X),
Y is through the thickness. Sizes are the photo's proportions scaled to the catalogue's 70 mm.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

# Side profile in mm, measured on the square-on reference photo (Bean's hardware sheet, scaled so its height is the
# catalogue's 70 mm): x across, z up from the bottom of the eye. Shifted to the bail's load point at the end.
Z_LOAD = 61.0           # inside top of the bail
X_LOAD = 3.0


def _ring_sweep(name, path, half_y, half_p, mat, closed=False, segs=20, sq=2.0):
    """A tube along a path in the XZ plane, its oval section half_y through the thickness (Y) and half_p in the plane.
    The in-plane axis is the tangent crossed with Y, so a closed loop never flips. sq > 2 squares the section off
    (a superellipse: the flat faces of a forging)."""
    def se(a):
        c, s_ = math.cos(a), math.sin(a)
        return math.copysign(abs(c) ** (2 / sq), c), math.copysign(abs(s_) ** (2 / sq), s_)
    bm = bmesh.new()
    pts = [Vector(p) for p in path]
    n = len(pts)
    hy = half_y if isinstance(half_y, list) else [half_y] * n
    hp = half_p if isinstance(half_p, list) else [half_p] * n
    rings = []
    for i, p in enumerate(pts):
        if closed:
            t = pts[(i + 1) % n] - pts[i - 1]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        u = Vector((0, 1, 0))
        v = t.cross(u).normalized()
        rings.append([bm.verts.new(p + u * (hy[i] * se(G.TAU * k / segs)[0]) + v * (hp[i] * se(G.TAU * k / segs)[1]))
                      for k in range(segs)])
    pairs = list(zip(rings, rings[1:] + ([rings[0]] if closed else [])))
    for a, b in pairs:
        for k in range(segs):
            bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _smooth_path(key, per=6, closed=False):
    """Catmull-Rom through key points (mm), returned in metres."""
    k = [Vector(p) for p in key]
    n = len(k)
    out = []
    segs = n if closed else n - 1
    for i in range(segs):
        if closed:
            p0, p1, p2, p3 = k[i - 1], k[i], k[(i + 1) % n], k[(i + 2) % n]
        else:
            p0, p1, p2, p3 = k[max(i - 1, 0)], k[i], k[i + 1], k[min(i + 2, n - 1)]
        for j in range(per):
            t = j / per
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    if not closed:
        out.append(k[-1])
    return [tuple(c * 0.001 for c in p) for p in out]


def _xz(x, z, y=0.0):
    return ((x - X_LOAD) * 0.001, y * 0.001, (z - Z_LOAD) * 0.001)


# eye: an oval loop round a 15 x 18 mm hole, its long axis leaning a little toward the hinge
EYE_C, EYE_A, EYE_B, EYE_TILT = (-0.2, 15.8), 11.0, 12.4, math.radians(-10)


def eye_bottom():
    """Centre of the eye's bottom bar (mm, photo frame)."""
    return EYE_C[0] + EYE_B * math.sin(EYE_TILT), EYE_C[1] - EYE_B * math.cos(EYE_TILT)


# bail: round bar from the hinge up the open side, over the top and down into the latch boss
BAIL_KEY = [(19.0, 19.5), (21.0, 27.0), (21.4, 37.0), (20.6, 47.0), (18.0, 56.0), (13.0, 63.0), (6.0, 66.6), (-1.0, 66.6),
            (-6.0, 63.6), (-9.0, 59.5)]
HINGE = (19.0, 19.5)
LATCH = (-10.9, 57.4)
COLUMN_KEY = [(-11.6, 24.0), (-11.6, 32.0), (-11.3, 42.0), (-11.0, 50.0), (-10.9, 56.0)]
CROSS_KEY = [(-11.0, 27.6), (-3.0, 27.0), (6.0, 24.6), (14.0, 21.4), (19.0, 19.5)]


def snap_shackle_parts(voxel=0.00022, tris=11000, bar_r=3.1):
    ss = P.M("Stainless")
    # --- forged body: eye, crossbar and plunger column fused into one piece with soft fillets
    ca, sa = math.cos(EYE_TILT), math.sin(EYE_TILT)
    eye_key = []
    for i in range(12):
        a = G.TAU * i / 12
        x, z = EYE_A * math.cos(a), EYE_B * math.sin(a)
        # a little fuller at the bottom, like the forging's teardrop
        if z < 0:
            x *= 1.0 - 0.10 * (-z / EYE_B)
        eye_key.append((EYE_C[0] + x * ca - z * sa, 0.0, EYE_C[1] + x * sa + z * ca))
    eye_path = [_xz(p[0] * 1000, p[2] * 1000) for p in _smooth_path(eye_key, 6, closed=True)]
    eye = _ring_sweep("eye", eye_path, 0.0044, 0.0040, ss, closed=True, sq=2.4)
    cross_path = [_xz(p[0] * 1000, p[2] * 1000) for p in _smooth_path([(x, 0, z) for x, z in CROSS_KEY], 6)]
    nc = len(cross_path)
    cross = _ring_sweep("cross", cross_path, [0.0045] * nc, [0.0060 - 0.0016 * i / (nc - 1) for i in range(nc)], ss, sq=3.2)
    col_path = [_xz(p[0] * 1000, p[2] * 1000) for p in _smooth_path([(x, 0, z) for x, z in COLUMN_KEY], 6)]
    ncl = len(col_path)
    column = _ring_sweep("column", col_path, [0.0045] * ncl, [0.0062 - 0.0014 * i / (ncl - 1) for i in range(ncl)], ss, sq=3.2)
    # the hinge knuckle: the crossbar's end, a rounded drum the bail's fork straddles
    knuck = G.cyl("knuckle", _xz(HINGE[0], HINGE[1], -3.0), _xz(HINGE[0], HINGE[1], 3.0), 0.0042, ss, 32)
    # the web between the column and the crossbar: the bail's opening has a sloping inner edge, not a square corner
    web_mm = [(-15.0, 25.0), (12.0, 21.6), (11.0, 28.5), (6.0, 33.5), (0.5, 39.0), (-3.5, 45.0), (-5.6, 51.0), (-15.0, 51.0)]
    web = G.prism("web", [((x - X_LOAD) * 0.001, (z - Z_LOAD) * 0.001) for x, z in web_mm], -0.0030, 0.0030, ss)
    web.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")
    G.bake_xform(web)
    body = G.join("body", [eye, cross, column, knuck, web])
    m = body.modifiers.new("fuse", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", voxel, 0.0
    sm = body.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.6, 14
    G.apply(body)
    # the plunger's slot up the column's outer face (the ring's lug rides in it)
    slot = G.box("slot", _xz(-17.4, 38.8), (0.0040, 0.0024, 0.0110))
    G.boolean(body, slot)
    d = body.modifiers.new("budget", "DECIMATE")
    me = body.data
    me.calc_loop_triangles()
    d.ratio = min(1.0, tris / max(1, len(me.loop_triangles)))
    G.apply(body)
    G.finish(body, 0.0, sharp=70)
    body.name = "body"
    objs = [body]

    # --- latch boss: the round head of the plunger housing the bail's tip seats against
    latch = G.lathe("latch", [(0, 0), (0.0046, 0), (0.0050, 0.0008), (0.0050, 0.0082), (0.0046, 0.0090), (0, 0.0090)], ss, 40)
    latch.matrix_world = Matrix.Translation(_xz(LATCH[0], LATCH[1], -4.5)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    G.bake_xform(latch)
    objs.append(G.finish(latch, 0.0, sharp=40))
    # the plunger's dished end in the boss face (what you see head-on in the photo)
    dish = G.cyl("latch_pin", _xz(LATCH[0], LATCH[1], -4.6), _xz(LATCH[0], LATCH[1], -4.2), 0.0024, ss, 32)
    objs.append(G.finish(dish, 0.0, sharp=40))

    # --- bail: round bar, flattening into a fork at the hinge and a tongue at the latch
    bpath = _smooth_path([(x, 0, z) for x, z in BAIL_KEY], 7)
    bpath = [_xz(p[0] * 1000, p[2] * 1000) for p in bpath]
    nb = len(bpath)
    hy, hp = [], []
    for i in range(nb):
        t = i / (nb - 1)
        fork = max(0.0, 1 - t / 0.10)          # wide fork over the knuckle at the hinge end
        tip = max(0.0, (t - 0.88) / 0.12)       # flattened tongue into the latch
        thick = 0.25 * max(0.0, 1 - t / 0.35)    # stouter toward the hinge, as the forging tapers
        hy.append(bar_r * 0.001 * (1 + thick + 0.40 * fork + 0.15 * tip))
        hp.append(bar_r * 0.001 * (1 + thick + 0.15 * fork - 0.20 * tip))
    bail = _ring_sweep("bail", bpath, hy, hp, ss, segs=24)
    objs.append(G.finish(bail, 0.0, sharp=60))
    # fork cheeks either side of the knuckle
    for s in (-1, 1):
        ch = G.cyl(f"bail_fork{s}", _xz(HINGE[0], HINGE[1], s * 3.1), _xz(HINGE[0], HINGE[1], s * 4.7), 0.0043, ss, 32)
        objs.append(G.finish(ch, 0.0003, segs=2))

    # --- hinge pin: through the fork, a domed head on the near side and a peened end with a cross hole on the far side
    pin = G.cyl("pin", _xz(HINGE[0], HINGE[1], -5.6), _xz(HINGE[0], HINGE[1], 5.6), 0.0019, ss, 24)
    objs.append(G.finish(pin, 0.0, sharp=40))
    for s in (-1, 1):
        hd = G.lathe(f"pin_head{s}", [(0, 0), (0.0034, 0), (0.0032, 0.0007), (0.0022, 0.0013), (0, 0.0015)], ss, 28)
        hd.matrix_world = Matrix.Translation(_xz(HINGE[0], HINGE[1], s * 4.7)) @ Matrix.Rotation(math.radians(-90 * s), 4, "X")
        G.bake_xform(hd)
        objs.append(G.finish(hd, 0.0, sharp=50))

    # --- plunger lug and pull ring
    lug_a, lug_b = _xz(-15.5, 38.4), _xz(-18.6, 39.4)
    lug = G.cyl("plunger", lug_a, lug_b, 0.0016, ss, 20)
    objs.append(G.finish(lug, 0.0, sharp=40))
    leye = _ring_sweep("plunger_eye", [_xz(-19.6 + 1.3 * math.cos(G.TAU * i / 16), 39.6 + 1.3 * math.sin(G.TAU * i / 16)) for i in range(16)],
                       0.0008, 0.0008, ss, closed=True, segs=10)
    leye.data.transform(Matrix.Translation(Vector(_xz(-19.6, 39.6))) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation(-Vector(_xz(-19.6, 39.6))))
    objs.append(G.finish(leye, 0.0, sharp=60))
    # split ring, 14 mm across, hanging off the lug's eye and turned a little toward the camera
    rc = Vector(_xz(-23.2, 39.2))
    ring_pts = [(rc.x + 0.0050 * math.cos(G.TAU * i / 40), 0.0, rc.z + 0.0050 * math.sin(G.TAU * i / 40)) for i in range(40)]
    ring = _ring_sweep("ring", ring_pts, 0.0010, 0.0010, ss, closed=True, segs=12)
    ring.data.transform(Matrix.Translation(rc) @ Matrix.Rotation(math.radians(25), 4, "Z") @ Matrix.Translation(-rc))
    objs.append(G.finish(ring, 0.0, sharp=60))

    # --- maker's mark on the crossbar's face (TERNWAY: made up, the kit's rule is no real maker's logo)
    face = Matrix.Translation(_xz(3.0, 26.0, -4.75)) @ Matrix.Rotation(math.radians(-10), 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "X")
    objs.append(P.badge("mark", "Plate16", 0.0110, 0.0028, face, ss))

    socks = [("Bail", (0, 0, 0)),
             ("Eye", _xz(eye_bottom()[0], eye_bottom()[1] + 3.4)),      # inside the eye's bottom bar, where a splice bears
             ("Hinge", _xz(*HINGE)), ("Latch", _xz(*LATCH)), ("Ring", tuple(rc))]
    return objs, socks


@P.part("SnapShackle", "fastener", "70 mm stainless snap shackle: fixed eye, hinged bail, plunger with pull ring")
def snap_shackle():
    objs, socks = snap_shackle_parts()
    return P.done("SnapShackle", objs, socks)


P.SIZES["SnapShackle"] = {"dim": "length mm", "default": "70", "scale": {"50": 0.714, "70": 1.0, "90": 1.286}}
