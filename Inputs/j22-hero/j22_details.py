"""Fine fittings for keelboat models, sized from small-boat hardware (29-40 mm blocks, 5 mm shackles, 1/4 in
turnbuckles): blocks with sheaves, axle rivets and shackles; shackles; clevis pins with split rings; turnbuckles with
toggles, swages and rigging tape; gooseneck; vang; masthead crane with sheaves and windex; spreader roots and taped
tips; boom end; sail rings, headboard and telltales; rope coils, stopper knots and whippings; screw heads.

Every part is built in a local frame (X along the part, Z up from its base) and placed with a 4x4 matrix, so the same
library dresses any boat. Sizes are in metres. Functions return lists of objects.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from j22_geom import box, cyl, mesh_obj, tube


def frame(origin, x_axis, z_hint=(0, 0, 1)):
    """A matrix whose X is x_axis and whose Z is as close to z_hint as possible, at origin."""
    x = Vector(x_axis).normalized()
    z = Vector(z_hint)
    y = z.cross(x)
    if y.length < 1e-6:
        y = Vector((0, 1, 0)) if abs(x.z) > 0.9 else Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def _place(objs, M):
    for o in objs:
        o.matrix_world = M @ o.matrix_world
    return objs


def lbox(name, c, s, mat, bev=0.0):
    return box(name, c[0] - s[0] / 2, c[0] + s[0] / 2, c[1] - s[1] / 2, c[1] + s[1] / 2, c[2] - s[2] / 2, c[2] + s[2] / 2, mat, bev=bev)


def torus(name, r_major, r_minor, mat, segs=24, rsegs=10, arc=2 * math.pi):
    bm = bmesh.new()
    rings = []
    n = segs if arc >= 2 * math.pi - 1e-6 else segs + 1
    for i in range(n):
        a = arc * i / segs
        c, s = math.cos(a), math.sin(a)
        ring = []
        for k in range(rsegs):
            b = 2 * math.pi * k / rsegs
            rr = r_major + r_minor * math.cos(b)
            ring.append(bm.verts.new((rr * c, rr * s, r_minor * math.sin(b))))
        rings.append(ring)
    pairs = list(zip(rings, rings[1:] + ([rings[0]] if n == segs else [])))
    for a, b in pairs:
        for k in range(rsegs):
            bm.faces.new((a[k], a[(k + 1) % rsegs], b[(k + 1) % rsegs], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)


# ------------------------------------------------------------------ small parts

def screws(name, pts, normal, M):
    """Pan-head screws (6 mm head) with a cross slot hint, on a surface with the given normal."""
    out = []
    n = Vector(normal).normalized()
    for i, p in enumerate(pts):
        p = Vector(p)
        out.append(cyl(f"{name}_scr{i}", p - n * 0.0005, p + n * 0.0018, 0.003, M["Stainless"], 10, r1=0.0024))
    return out


def shackle(name, at, axis, M, size=1.0):
    """D-shackle: bow along local +Z from the pin, pin along local Y. axis = direction the bow points."""
    s = size
    objs = []
    w, L, d = 0.007 * s, 0.020 * s, 0.0022 * s
    pts = []
    for k in range(13):
        a = math.pi * k / 12
        pts.append((0, -w * math.cos(a), L - w + w * math.sin(a) if a else L - w))
    pts = [(0, -w, 0)] + pts + [(0, w, 0)]
    objs.append(tube(f"{name}_bow", pts, d, M["Stainless"], smooth_path=True))
    objs.append(cyl(f"{name}_pin", (0, -w - 0.003 * s, 0), (0, w + 0.004 * s, 0), d * 1.15, M["Stainless"], 10))
    objs.append(cyl(f"{name}_pinhead", (0, w + 0.003 * s, 0), (0, w + 0.0055 * s, 0), d * 1.9, M["Stainless"], 10))
    return _place(objs, frame(at, Vector(axis).cross(Vector((0, 0, 1))) if abs(Vector(axis).normalized().z) < 0.95 else (1, 0, 0), axis))


def clevis(name, at, axis, M, length=0.02, r=0.0025, ring=True):
    """Clevis pin through a fitting, with a split ring on the far end (optionally taped over)."""
    a = Vector(axis).normalized()
    p = Vector(at)
    objs = [cyl(f"{name}_pin", p - a * length / 2, p + a * length / 2, r, M["Stainless"], 12),
            cyl(f"{name}_head", p - a * (length / 2 + 0.0015), p - a * length / 2, r * 1.8, M["Stainless"], 12)]
    if ring:
        t = torus(f"{name}_ring", r * 2.2, 0.0006, M["Stainless"], 16, 6)
        t.matrix_world = frame(p + a * (length / 2 - 0.001), a.orthogonal(), a)
        objs.append(t)
    return objs


def block(name, at, axle, toward, M, sheave_d=0.029, cheek="BlackPlastic", becket=False, with_shackle=True):
    """Ball-bearing block: rounded cheeks, grooved sheave, axle rivets, a head shackle pointing `toward`."""
    R = sheave_d * 0.65
    W = sheave_d * 0.55
    ax = Vector(axle).normalized()
    up = Vector(toward).normalized()
    up = (up - ax * up.dot(ax)).normalized()
    M4 = frame(at, up, ax)          # local X toward the shackle, local Z along the axle
    objs = []
    for sgn in (-1, 1):
        c = cyl(f"{name}_cheek{sgn}", (0, 0, sgn * W * 0.35), (0, 0, sgn * W * 0.5), R, M[cheek], 28)
        objs.append(c)
        objs.append(cyl(f"{name}_rivet{sgn}", (0, 0, sgn * W * 0.5), (0, 0, sgn * (W * 0.5 + 0.0015)), 0.0035, M["Stainless"], 12))
        # cheek "nose" toward the head
        objs.append(lbox(f"{name}_nose{sgn}", (R * 0.95, 0, sgn * W * 0.42), (R * 0.7, R * 0.9, W * 0.16), M[cheek], bev=0.002))
    sh = cyl(f"{name}_sheave", (0, 0, -W * 0.33), (0, 0, W * 0.33), sheave_d / 2, M["SheaveGrey"], 28)
    objs.append(sh)
    objs.append(torus(f"{name}_groove", sheave_d / 2 - 0.0005, W * 0.18, M["SheaveGrey"], 28, 8))
    _place(objs, M4)
    if with_shackle:
        objs += shackle(f"{name}_sh", Vector(at) + up * R * 1.25, up, M, size=sheave_d / 0.029)
    if becket:
        b = torus(f"{name}_becket", 0.006, 0.0018, M["Stainless"], 16, 6)
        b.matrix_world = frame(Vector(at) - up * R * 1.15, ax, up)
        objs.append(b)
    return objs


def cam_cleat(name, at, out_normal, along, M, length=0.065):
    """Cam cleat on its riser: base, two toothed cams with springs, fairlead, two screws."""
    n = Vector(out_normal).normalized()
    a = Vector(along).normalized()
    M4 = frame(at, a, n)
    objs = [lbox(f"{name}_base", (0, 0, 0.004), (length, 0.030, 0.008), M["CamBase"], bev=0.002),
            lbox(f"{name}_lead", (length / 2 - 0.004, 0, 0.012), (0.010, 0.026, 0.012), M["CamBase"], bev=0.003)]
    for sgn in (-1, 1):
        objs.append(cyl(f"{name}_cam{sgn}", (-0.006, sgn * 0.0095, 0.008), (-0.006, sgn * 0.0095, 0.022), 0.0105, M["RedPlastic"], 18))
        for t in range(9):                         # teeth
            ang = math.pi * (0.25 + 0.5 * t / 8) * (-sgn)
            objs.append(lbox(f"{name}_t{sgn}{t}", (-0.006 + 0.0108 * math.cos(ang), sgn * 0.0095 + 0.0108 * math.sin(ang) * -1, 0.015),
                             (0.0018, 0.0018, 0.013), M["RedPlastic"]))
        objs.append(cyl(f"{name}_ax{sgn}", (-0.006, sgn * 0.0095, 0.022), (-0.006, sgn * 0.0095, 0.024), 0.003, M["Stainless"], 8))
    _place(objs, M4)
    objs += screws(f"{name}", [M4 @ Vector((-length / 2 + 0.006, 0, 0.008)), M4 @ Vector((length / 2 - 0.012, 0, 0.008))], n, M)
    return objs


def padeye(name, at, normal, M):
    n = Vector(normal).normalized()
    M4 = frame(at, n.orthogonal(), n)
    objs = [lbox(f"{name}_base", (0, 0, 0.002), (0.040, 0.018, 0.004), M["Stainless"], bev=0.0015)]
    t = torus(f"{name}_loop", 0.007, 0.0022, M["Stainless"], 16, 8, arc=math.pi)
    t.matrix_world = Matrix.Rotation(math.pi / 2, 4, "X")
    objs.append(t)
    _place(objs, M4)
    return objs + screws(name, [M4 @ Vector((-0.015, 0, 0.004)), M4 @ Vector((0.015, 0, 0.004))], n, M)


# ------------------------------------------------------------------ standing rigging

def turnbuckle(name, base, wire_dir, M, tape_hex_mat="RigTape", length=0.17):
    """Toggle on the chainplate, open-body turnbuckle, threaded studs, swage up into the wire, tape over the pins."""
    d = Vector(wire_dir).normalized()
    p = Vector(base)
    objs = []
    # toggle: fork around the chainplate with a clevis pin
    M4 = frame(p, d.orthogonal(), d)
    for sgn in (-1, 1):
        objs.append(_place([lbox(f"{name}_tog{sgn}", (0, sgn * 0.0065, 0.012), (0.012, 0.003, 0.03), M["Stainless"], bev=0.001)], M4)[0])
    objs += clevis(f"{name}_tpin", p + d * 0.004, (M4.to_3x3() @ Vector((0, 1, 0))), M, 0.02, 0.0025)
    s0 = p + d * 0.027
    s1 = s0 + d * 0.025
    objs.append(cyl(f"{name}_stud_lo", s0, s1, 0.003, M["Chrome"], 12))
    b0 = s1
    b1 = b0 + d * 0.085
    # open body: two side bars and end bosses
    side = d.orthogonal().normalized()
    for sgn in (-1, 1):
        objs.append(cyl(f"{name}_bar{sgn}", b0 + side * sgn * 0.0055, b1 + side * sgn * 0.0055, 0.0022, M["Chrome"], 10))
    objs.append(cyl(f"{name}_boss_lo", b0, b0 + d * 0.012, 0.0065, M["Chrome"], 16))
    objs.append(cyl(f"{name}_boss_hi", b1 - d * 0.012, b1, 0.0065, M["Chrome"], 16))
    objs.append(cyl(f"{name}_stud_hi", b1, b1 + d * 0.03, 0.003, M["Chrome"], 12))
    sw0 = b1 + d * 0.03
    objs.append(cyl(f"{name}_swage", sw0, sw0 + d * 0.05, 0.0042, M["Chrome"], 14, r1=0.0024))
    # rigging tape over the toggle pin and the lock nuts
    objs.append(cyl(f"{name}_tape_lo", p - d * 0.004, p + d * 0.026, 0.0105, M[tape_hex_mat], 18))
    objs.append(cyl(f"{name}_tape_hi", b1 - d * 0.004, b1 + d * 0.02, 0.0072, M[tape_hex_mat], 16))
    return objs, sw0 + d * 0.05


def chainplate(name, at, M, normal=(0, 0, 1), along=(1, 0, 0), span=0.032):
    """Cover plate and strap through the deck; span is the strap's length along the deck (wider for two shroud holes)."""
    n = Vector(normal).normalized()
    M4 = frame(at, along, n)
    c = max(0.07, span + 0.04)
    objs = [lbox(f"{name}_cover", (0, 0, 0.002), (c, 0.03, 0.004), M["Stainless"], bev=0.0015),
            lbox(f"{name}_strap", (0, 0, 0.03), (span, 0.0048, 0.055), M["Stainless"], bev=0.002)]
    _place(objs, M4)
    objs += screws(name, [M4 @ Vector((-c / 2 + 0.007, 0, 0.004)), M4 @ Vector((c / 2 - 0.007, 0, 0.004))], n, M)
    return objs


# ------------------------------------------------------------------ spar fittings

def gooseneck(name, mast_aft, boom_z, M):
    """Mast-side casting riveted to the mast's aft face, vertical hinge pin, boom-end fork with horizontal pin,
    reef hook and cunningham hook. mast_aft = point on the mast's aft face at boom height."""
    p = Vector(mast_aft)
    objs = []
    # mast plate with 6 rivets
    objs.append(box(f"{name}_plate", p.x - 0.006, p.x + 0.002, -0.022, 0.022, boom_z - 0.07, boom_z + 0.06, M["CastAlu"], bev=0.003))
    for k in range(3):
        for sgn in (-1, 1):
            z = boom_z - 0.055 + 0.05 * k
            objs.append(cyl(f"{name}_riv{k}{sgn}", (p.x - 0.007, sgn * 0.014, z), (p.x - 0.0085, sgn * 0.014, z), 0.0028, M["Stainless"], 10))
    # hinge lugs and vertical pin
    for dz in (-0.03, 0.03):
        objs.append(box(f"{name}_lug{dz}", p.x - 0.045, p.x - 0.006, -0.012, 0.012, boom_z + dz - 0.006, boom_z + dz + 0.006, M["CastAlu"], bev=0.004))
    objs.append(cyl(f"{name}_vpin", (p.x - 0.034, 0, boom_z - 0.045), (p.x - 0.034, 0, boom_z + 0.045), 0.004, M["Stainless"], 12))
    objs.append(cyl(f"{name}_vpinhead", (p.x - 0.034, 0, boom_z + 0.045), (p.x - 0.034, 0, boom_z + 0.049), 0.0075, M["Stainless"], 12))
    # swivel knuckle and boom fork with horizontal pin
    objs.append(box(f"{name}_knuckle", p.x - 0.060, p.x - 0.024, -0.009, 0.009, boom_z - 0.022, boom_z + 0.022, M["CastAlu"], bev=0.005))
    for sgn in (-1, 1):
        objs.append(box(f"{name}_fork{sgn}", p.x - 0.095, p.x - 0.050, sgn * 0.010 - 0.003, sgn * 0.010 + 0.003, boom_z - 0.02, boom_z + 0.02, M["CastAlu"], bev=0.003))
    objs += clevis(f"{name}_hpin", (p.x - 0.066, 0, boom_z), (0, 1, 0), M, 0.03, 0.004)
    # boom end casting
    objs.append(box(f"{name}_boomcap", p.x - 0.13, p.x - 0.085, -0.03, 0.03, boom_z - 0.04, boom_z + 0.035, M["CastAlu"], bev=0.008))
    # reef hook (port) and cunningham hook (starboard) as bent rods
    for sgn, nm in ((1, "reef"), (-1, "cunn")):
        objs.append(tube(f"{name}_{nm}hook", [(p.x - 0.11, sgn * 0.03, boom_z + 0.02), (p.x - 0.11, sgn * 0.045, boom_z + 0.04),
                                                (p.x - 0.11, sgn * 0.045, boom_z + 0.075), (p.x - 0.11, sgn * 0.035, boom_z + 0.085)],
                         0.0025, M["Stainless"], smooth_path=True))
    return objs


def vang(name, mast_base, boom_pt, M, rope_mat, cam=True):
    """4:1 kicker: tang on the mast, swivel block with cam cleat at the bottom, fiddle block at the boom bail."""
    a, b = Vector(mast_base), Vector(boom_pt)
    d = (b - a).normalized()
    objs = [box(f"{name}_tang", a.x - 0.012, a.x + 0.012, -0.01, 0.01, a.z - 0.03, a.z + 0.03, M["CastAlu"], bev=0.004)]
    objs += clevis(f"{name}_tangpin", (a.x - 0.01, 0, a.z), (0, 1, 0), M, 0.03, 0.003)
    lo = a + d * 0.06
    hi = b - d * 0.06
    objs += block(f"{name}_lo", lo, (0, 1, 0), -d, M, 0.040, becket=True)
    objs += block(f"{name}_hi", hi, (0, 1, 0), d, M, 0.040)
    objs += block(f"{name}_hi2", hi + d * 0.0 + Vector((0, 0.022, 0)), (0, 1, 0), d, M, 0.029, with_shackle=False)
    if cam:
        objs += cam_cleat(f"{name}_cam", lo - d * 0.0 + Vector((0, -0.03, 0)), (0, -1, 0), d, M, 0.055)
    # boom bail
    objs.append(tube(f"{name}_bail", [(b.x - 0.03, -0.03, b.z + 0.02), (b.x - 0.03, -0.03, b.z - 0.01), (b.x, 0, b.z - 0.03),
                                       (b.x + 0.03, 0.03, b.z - 0.01), (b.x + 0.03, 0.03, b.z + 0.02)], 0.003, M["Stainless"], smooth_path=True))
    # four parts of line
    for k, off in enumerate((-0.012, -0.004, 0.004, 0.012)):
        objs.append(tube(f"{name}_part{k}", [tuple(lo + Vector((0, off, 0))), tuple(hi + Vector((0, off, 0)))], 0.0035, rope_mat))
    # tail from the cam, falling to the deck
    objs.append(tube(f"{name}_tail", [tuple(lo + Vector((0, -0.035, 0.02))), tuple(lo + Vector((0.05, -0.08, -0.06))),
                                       tuple(lo + Vector((0.10, -0.10, -0.10)))], 0.0035, rope_mat, smooth_path=True))
    return objs


def masthead(name, top, M, windex=True):
    """Crane casting aft with two halyard sheaves, backstay tang, cap, windex with reference tabs."""
    t = Vector(top)
    objs = [box(f"{name}_cap", t.x - 0.055, t.x + 0.05, -0.036, 0.036, t.z - 0.035, t.z + 0.005, M["CastAlu"], bev=0.008),
            box(f"{name}_crane", t.x - 0.20, t.x - 0.04, -0.018, 0.018, t.z - 0.02, t.z + 0.015, M["CastAlu"], bev=0.006)]
    for k, dx in enumerate((-0.015, 0.025)):
        objs.append(cyl(f"{name}_sheave{k}", (t.x + dx, -0.006, t.z - 0.02), (t.x + dx, 0.006, t.z - 0.02), 0.022, M["SheaveGrey"], 20))
    objs.append(box(f"{name}_bstang", t.x - 0.205, t.x - 0.185, -0.004, 0.004, t.z - 0.06, t.z - 0.015, M["Stainless"], bev=0.002))
    objs += clevis(f"{name}_bspin", (t.x - 0.195, 0, t.z - 0.045), (0, 1, 0), M, 0.016, 0.0025)
    if windex:
        w0 = Vector((t.x - 0.03, 0, t.z + 0.005))
        objs.append(cyl(f"{name}_wxpole", w0, w0 + Vector((0.12, 0, 0.30)), 0.0025, M["BlackPlastic"], 8))
        hub = w0 + Vector((0.12, 0, 0.30))
        objs.append(cyl(f"{name}_wxhub", hub, hub + Vector((0, 0, 0.01)), 0.005, M["BlackPlastic"], 10))
        objs.append(cyl(f"{name}_wxarm", hub + Vector((0.06, 0, 0.005)), hub + Vector((-0.17, 0, 0.005)), 0.0018, M["BlackPlastic"], 6))
        objs.append(box(f"{name}_wxvane", hub.x - 0.2, hub.x - 0.12, -0.0008, 0.0008, hub.z - 0.01, hub.z + 0.05, M["RedPlastic"]))
        objs.append(box(f"{name}_wxcw", hub.x + 0.055, hub.x + 0.07, -0.004, 0.004, hub.z, hub.z + 0.01, M["BlackPlastic"], bev=0.002))
        for sgn in (-1, 1):   # reference tabs, set for close hauled
            a = math.radians(30) * sgn
            objs.append(cyl(f"{name}_wxtab{sgn}", hub + Vector((-0.02, 0, -0.02)), hub + Vector((-0.12 * math.cos(a), 0.12 * math.sin(a), -0.02)), 0.0012, M["BlackPlastic"], 6))
            objs.append(box(f"{name}_wxtabend{sgn}", -0.012, 0.012, -0.0006, 0.0006, -0.006, 0.006, M["RedPlastic"]))
            objs[-1].matrix_world = Matrix.Translation(hub + Vector((-0.12 * math.cos(a), 0.12 * math.sin(a), -0.02)))
    return objs


def spreader_root(name, mast_pt, side, M):
    p = Vector(mast_pt)
    objs = [box(f"{name}_root", p.x - 0.03, p.x + 0.01, side * 0.02, side * 0.06, p.z - 0.03, p.z + 0.03, M["CastAlu"], bev=0.006)]
    for k in range(2):
        objs.append(cyl(f"{name}_bolt{k}", (p.x - 0.01, side * 0.065, p.z - 0.015 + 0.03 * k), (p.x - 0.01, side * 0.07, p.z - 0.015 + 0.03 * k), 0.004, M["Stainless"], 10))
    return objs


def spreader_tip(name, tip, along, M):
    """End fitting clamping the upper shroud, wrapped in rigging tape (or a boot) so it does not chafe the sail."""
    a = Vector(along).normalized()
    t = Vector(tip)
    objs = [cyl(f"{name}_end", t - a * 0.03, t, 0.011, M["CastAlu"], 14),
            cyl(f"{name}_tape", t - a * 0.06, t + a * 0.012, 0.0145, M["RigTape"], 16),
            cyl(f"{name}_tape2", t - Vector((0, 0, 0.03)), t + Vector((0, 0, 0.03)), 0.009, M["RigTape"], 14)]
    return objs


def hounds_tang(name, pt, M):
    p = Vector(pt)
    objs = [box(f"{name}_tang", p.x - 0.01, p.x + 0.06, -0.004, 0.004, p.z - 0.05, p.z + 0.01, M["Stainless"], bev=0.002)]
    for sgn in (-1, 1):
        objs.append(box(f"{name}_t{sgn}", p.x - 0.05, p.x - 0.01, sgn * 0.035 - 0.003, sgn * 0.035 + 0.003, p.z - 0.04, p.z + 0.0, M["Stainless"], bev=0.002))
    objs += clevis(f"{name}_fpin", (p.x + 0.045, 0, p.z - 0.03), (0, 1, 0), M, 0.016, 0.0025)
    return objs


def boom_end(name, end, M):
    e = Vector(end)
    objs = [box(f"{name}_cap", e.x - 0.03, e.x + 0.02, -0.031, 0.031, e.z - 0.045, e.z + 0.035, M["CastAlu"], bev=0.008)]
    objs.append(cyl(f"{name}_outhaul", (e.x - 0.01, -0.006, e.z + 0.012), (e.x - 0.01, 0.006, e.z + 0.012), 0.012, M["SheaveGrey"], 16))
    objs.append(cyl(f"{name}_axle", (e.x - 0.01, -0.033, e.z + 0.012), (e.x - 0.01, 0.033, e.z + 0.012), 0.003, M["Stainless"], 8))
    return objs


# ------------------------------------------------------------------ rope work

def coil(name, centre, radius, turns, mat, r=0.0045, seed=0, flat_z=None, tail=None):
    """A loosely flaked coil of line lying on a surface: overlapping, slightly irregular loops."""
    rng = random.Random(seed)
    c = Vector(centre)
    pts = []
    n = int(turns * 24)
    for i in range(n + 1):
        a = 2 * math.pi * i / 24
        rr = radius * (1 + 0.15 * math.sin(a * 0.5 + rng.random()) + rng.uniform(-0.04, 0.04))
        z = (flat_z if flat_z is not None else c.z) + r + 0.003 * (i / n) + 0.0015 * math.sin(a * 3)
        pts.append((c.x + rr * math.cos(a) * 1.3, c.y + rr * math.sin(a), z))
    if tail:
        pts += [tuple(p) for p in tail]
    # Boat fidelity 4: the game draws these coils as live rope (bake_j22_hero.py keeps them out of the game mesh, so only
    # their baked shadows were there); build_j22_hero.py writes them to J22H_coils.json for BoatModelVisuals.cpp.
    COILS.append({"name": name, "radius_m": r, "material": mat.name if mat else "", "points_m": [[round(c, 5) for c in p] for p in pts]})
    return [tube(name, pts, r, mat, smooth_path=True)]


COILS = []


def stopper_knot(name, at, axis, mat, r=0.0045):
    """Figure-eight stopper knot on a line end: a lumpy double loop."""
    a = Vector(axis).normalized()
    M4 = frame(at, a)
    pts = []
    for i in range(41):
        t = 2 * math.pi * i / 40
        pts.append(Vector((0.012 * math.sin(2 * t) + 0.006 * t / math.pi, 0.010 * math.sin(t), 0.008 * math.cos(t) * math.sin(t))))
    ob = tube(name, [tuple(M4 @ p) for p in pts], r, mat, smooth_path=True)
    return [ob]


def whipping(name, at, axis, M, r=0.0048):
    a = Vector(axis).normalized()
    p = Vector(at)
    return [cyl(name, p - a * 0.006, p + a * 0.006, r, M["Whipping"], 12)]


# ------------------------------------------------------------------ sail hardware

def ring(name, at, normal, M, r=0.012, wire=0.0022, mat="Stainless"):
    t = torus(name, r, wire, M[mat], 24, 8)
    n = Vector(normal).normalized()
    t.matrix_world = frame(at, n.orthogonal(), n)
    return [t]


def headboard(name, corner_pts, normal, M):
    """Aluminium headboard riveted to both sides of the head: a thin plate with a rivet grid."""
    a, b, c = (Vector(p) for p in corner_pts)
    n = Vector(normal).normalized()
    bm = bmesh.new()
    vs = [bm.verts.new(p + n * 0.002) for p in (a, b, c)] + [bm.verts.new(p - n * 0.002) for p in (a, b, c)]
    bm.faces.new(vs[:3])
    bm.faces.new(vs[3:][::-1])
    for i in range(3):
        j = (i + 1) % 3
        bm.faces.new((vs[i], vs[j], vs[3 + j], vs[3 + i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    objs = [mesh_obj(f"{name}_plate", bm, M["CastAlu"], smooth_shade=False)]
    for k in range(5):
        for m in range(3 - k // 2):
            u, v = 0.15 + 0.15 * k, 0.2 + 0.25 * m
            p = a + (b - a) * u + (c - a) * v * (1 - u)
            objs.append(cyl(f"{name}_r{k}{m}", p - n * 0.003, p + n * 0.003, 0.0025, M["Stainless"], 8))
    return objs


def telltale(name, at, flow_dir, M, mat="TelltaleRed", length=0.11, seed=0):
    """A ribbon telltale streaming downwind with a little flutter."""
    rng = random.Random(seed)
    d = Vector(flow_dir).normalized()
    side = d.cross(Vector((0, 0, 1))).normalized()
    bm = bmesh.new()
    prev = None
    for i in range(9):
        t = i / 8
        p = Vector(at) + d * length * t + side * 0.008 * math.sin(t * 6 + rng.random()) * t + Vector((0, 0, -0.01 * t * t))
        v0, v1 = bm.verts.new(p + Vector((0, 0, 0.0035))), bm.verts.new(p - Vector((0, 0, 0.0035)))
        if prev:
            bm.faces.new((prev[0], prev[1], v1, v0))
        prev = (v0, v1)
    ob = mesh_obj(name, bm, M[mat])
    return [ob]
