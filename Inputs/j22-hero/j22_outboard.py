"""Boat fidelity (pc/j22-detail, assembly 2): the hero J/22's outboard and its transom bracket, at hero detail. A
generic 5 hp long-shaft four-stroke (the class's usual 4-6 hp kicker) with a made-up maker, TERNWAY (the boat kit's
brand); no real maker's shapes or marks. Replaces build_j22_hero.outboard()'s seven boxes. Bean's photos transom-worn
and aft-transom show the bracket on the port quarter: a stainless transom plate, two pairs of parallel arms that lift
the motor clear, a pad the motor clamps to.

Sizes (GUESS from typical 4-6 hp long shafts): cowl 0.40 m long, 0.27 m wide; 20 in shaft (cavitation plate 0.62 m
under the clamp's top); 7.8 in three-blade prop. Blender frame (x forward, z up; the hero's y as build_j22_hero.py)."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from j22_geom import apply_mods, cyl, link, mesh_obj
from j22_steering import hex_head, lathe, nylock, plate

STERN = -3.41
Y = 0.55                  # the bracket's centre across the transom (the port quarter, as before)
CLAMP_Z = 0.52            # the clamp's top on the bracket's pad
CAV_Z = CLAMP_Z - 0.62    # 20 in shaft
AXIS_X = STERN - 0.205    # the motor's steering axis (the swivel bracket's tube)


def superellipse_ring(bm, cx, cy, z, a, b, n=3.0, segs=40, front_bulge=0.0):
    """Points round a superellipse of half-axes a (x) and b (y) at height z; front_bulge pushes the +x half forward."""
    out = []
    for k in range(segs):
        t = 2 * math.pi * k / segs
        c, s = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(c) ** (2 / n), c)
        y = b * math.copysign(abs(s) ** (2 / n), s)
        if x > 0:
            x *= 1 + front_bulge
        out.append(bm.verts.new((cx + x, cy + y, z)))
    return out


def loft_rings(name, rings, mat, bm, cap_bottom=True, cap_top=True, smooth=True):
    segs = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]))
    if cap_bottom:
        bm.faces.new(rings[0][::-1])
    if cap_top:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat, smooth_shade=smooth)


def cowl(MAT):
    """The lower cowl (pan), the parting line, the upper cowl domed over the powerhead."""
    cx, cy = AXIS_X - 0.13, Y
    out = []
    # lower pan: from the swivel housing's top widening into the cowl's footprint
    bm = bmesh.new()
    rings = []
    for z, a, b in ((CLAMP_Z - 0.035, 0.11, 0.07), (CLAMP_Z - 0.01, 0.17, 0.115), (CLAMP_Z + 0.03, 0.20, 0.135), (CLAMP_Z + 0.095, 0.205, 0.138)):
        rings.append(superellipse_ring(bm, cx, cy, z, a, b, 3.2, 48, 0.05))
    out.append(loft_rings("OBo_pan", rings, MAT["OutboardBlack"], bm))
    # the parting line: a slim dark gasket a little inside the shells
    out.append(loft_rings("OBo_gasket", [superellipse_ring(b2 := bmesh.new(), cx, cy, CLAMP_Z + 0.095, 0.199, 0.133, 3.2, 48, 0.05),
                                          superellipse_ring(b2, cx, cy, CLAMP_Z + 0.104, 0.199, 0.133, 3.2, 48, 0.05)], MAT["BlackPlastic"], b2))
    # upper cowl: straight-sided, then rolling over into a domed top, a little narrower aft
    bm = bmesh.new()
    rings = []
    z0 = CLAMP_Z + 0.104
    for i in range(12):
        f = i / 11
        z = z0 + 0.20 * math.sin(f * math.pi / 2) ** 0.8
        shrink = math.cos(f * math.pi / 2) ** 0.55
        a = 0.205 * (0.55 + 0.45 * shrink) if f > 0.6 else 0.205
        b = 0.138 * (0.30 + 0.70 * shrink) if f > 0.5 else 0.138
        rings.append(superellipse_ring(bm, cx - 0.01 * f, cy, z, a, b, 3.2 - 0.8 * f, 48, 0.05))
    top = rings[-1][0].co.z            # (before the loft frees the bmesh)
    out.append(loft_rings("OBo_cowl", rings, MAT["OutboardBlack"], bm))
    # the latch lever at the back of the parting line, the recoil starter's handle at the front
    out.append(plate("OBo_latch", [(cx - 0.215, CLAMP_Z + 0.075), (cx - 0.232, CLAMP_Z + 0.08), (cx - 0.232, CLAMP_Z + 0.13), (cx - 0.215, CLAMP_Z + 0.135)],
                     cy - 0.025, cy + 0.025, MAT["BlackPlastic"], bev=0.003))
    hx = cx + 0.205 * 1.05 + 0.01
    out.append(cyl("OBo_startrope", Vector((hx - 0.02, cy, CLAMP_Z + 0.17)), Vector((hx + 0.004, cy, CLAMP_Z + 0.17)), 0.003, MAT["BlackPlastic"], 8))
    out.append(cyl("OBo_starthandle", Vector((hx + 0.004, cy - 0.045, CLAMP_Z + 0.17)), Vector((hx + 0.004, cy + 0.045, CLAMP_Z + 0.17)), 0.011, MAT["BlackPlastic"], 16))
    # the integral tank's filler cap and vent on top
    out.append(lathe("OBo_fuelcap", [(0.0, 0.0), (0.028, 0.0), (0.03, 0.006), (0.028, 0.016), (0.02, 0.019), (0.0, 0.02)],
                     Vector((cx - 0.06, cy, top - 0.004)), (0, 0, 1), MAT["BlackPlastic"], 32))
    out.append(cyl("OBo_vent", Vector((cx - 0.06, cy, top + 0.016)), Vector((cx - 0.06, cy, top + 0.026)), 0.006, MAT["BlackPlastic"], 12))
    # the maker's name on both sides (the kit's made-up TERNWAY), and a grey stripe under it
    for sgn in (1, -1):
        out.append(brand(MAT, Vector((cx + 0.02, cy + sgn * 0.139, CLAMP_Z + 0.17)), sgn))
        out.append(plate(f"OBo_stripe{sgn}", [(cx - 0.17, CLAMP_Z + 0.135), (cx + 0.19, CLAMP_Z + 0.135), (cx + 0.19, CLAMP_Z + 0.142), (cx - 0.17, CLAMP_Z + 0.142)],
                         cy + sgn * 0.1385 - 0.0006, cy + sgn * 0.1385 + 0.0006, MAT["SheaveGrey"], bev=0))
    return out


def brand(MAT, at, sgn):
    cu = bpy.data.curves.new(f"OBo_brand{sgn}", "FONT")
    cu.body = "TERNWAY"
    cu.size = 0.036
    cu.extrude = 0.0007
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(f"OBo_brand{sgn}", cu)
    link(ob)
    # the text's plane is its local XY: stand it up on the cowl's side, reading forward on both sides
    ob.matrix_world = Matrix.Translation(at) @ Matrix.Rotation(math.radians(90), 4, "X") @ (Matrix.Rotation(math.pi, 4, "Y") if sgn > 0 else Matrix.Identity(4))
    ob.data.materials.append(MAT["WhitePlastic"])
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active


def foil_ring(bm, cx, cy, z, chord, thick, segs=28):
    """A symmetric section (chord along x, nose forward at cx + chord/2) at height z."""
    out = []
    for k in range(segs):
        a = 2 * math.pi * k / segs
        xc = 0.5 * (1 + math.cos(a))
        t = 5 * thick * (0.2969 * math.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1036 * xc ** 4)
        out.append(bm.verts.new((cx + chord / 2 - xc * chord, cy + t * chord * (1 if a < math.pi else -1), z)))
    return out


def lower_unit(MAT):
    out = []
    cx, cy = AXIS_X - 0.075, Y
    # midsection (driveshaft and exhaust housing): a streamlined column, wider at the top, the exhaust relief at the back
    bm = bmesh.new()
    rings = []
    for z, chord, th in ((CAV_Z + 0.004, 0.15, 0.30), (CAV_Z + 0.12, 0.14, 0.32), (CLAMP_Z - 0.12, 0.13, 0.36), (CLAMP_Z - 0.04, 0.15, 0.42)):
        rings.append(foil_ring(bm, cx, cy, z, chord, th))
    out.append(loft_rings("OBo_midsection", rings, MAT["OutboardBlack"], bm))
    # the anti-cavitation plate: flat, wider than the leg, rounded aft, with its anode tab under it
    pl = [(cx + 0.06, -0.06), (cx - 0.02, -0.10), (cx - 0.17, -0.09), (cx - 0.20, -0.05), (cx - 0.205, 0.0), (cx - 0.20, 0.05), (cx - 0.17, 0.09),
          (cx - 0.02, 0.10), (cx + 0.06, 0.06)]
    bm = bmesh.new()
    a = [bm.verts.new((x, cy + y, CAV_Z - 0.003)) for x, y in pl]
    b = [bm.verts.new((x, cy + y, CAV_Z + 0.003)) for x, y in pl]
    n = len(pl)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cav = mesh_obj("OBo_cavplate", bm, MAT["OutboardBlack"], smooth_shade=False)
    m = cav.modifiers.new("bev", "BEVEL")
    m.width, m.segments = 0.0025, 2
    apply_mods(cav)
    out.append(cav)
    out.append(plate("OBo_anode", [(cx - 0.12, CAV_Z - 0.003), (cx - 0.05, CAV_Z - 0.003), (cx - 0.05, CAV_Z - 0.016), (cx - 0.12, CAV_Z - 0.016)],
                     cy - 0.012, cy + 0.012, MAT["CastAlu"], bev=0.002))
    # the strut and the gearcase: a torpedo along x, nose forward, the water intake grilles on its sides
    gz = CAV_Z - 0.085
    bm = bmesh.new()
    rings = [foil_ring(bm, cx, cy, z, 0.13, 0.30) for z in (gz + 0.03, CAV_Z - 0.002)]
    out.append(loft_rings("OBo_strut", rings, MAT["OutboardBlack"], bm))
    out.append(lathe("OBo_gearcase", [(0.0, 0.0), (0.022, 0.006), (0.036, 0.03), (0.043, 0.07), (0.043, 0.16), (0.037, 0.22), (0.028, 0.245), (0.0, 0.25)],
                     Vector((cx + 0.11, cy, gz)), (-1, 0, 0), MAT["OutboardBlack"], 32))
    for sgn in (1, -1):
        for k in range(5):
            out.append(plate(f"OBo_intake{sgn}{k}", [(cx + 0.02 - 0.012 * k, gz + 0.012), (cx + 0.016 - 0.012 * k, gz + 0.012), (cx + 0.016 - 0.012 * k, gz + 0.032), (cx + 0.02 - 0.012 * k, gz + 0.032)],
                             cy + sgn * 0.041 - 0.0015, cy + sgn * 0.041 + 0.0015, MAT["BlackPlastic"], bev=0))
    # the skeg below
    out.append(plate("OBo_skeg", [(cx + 0.02, gz - 0.03), (cx - 0.10, gz - 0.035), (cx - 0.08, gz - 0.115), (cx - 0.035, gz - 0.112)], cy - 0.0045, cy + 0.0045, MAT["OutboardBlack"], bev=0.002))
    # the prop: a hub and three blades with pitch, the thrust washer and nut aft
    px = cx - 0.14
    out.append(lathe("OBo_prophub", [(0.0, 0.0), (0.026, 0.0), (0.028, 0.012), (0.026, 0.05), (0.018, 0.062), (0.0, 0.064)], Vector((px, cy, gz)), (-1, 0, 0), MAT["BlackPlastic"], 28))
    out.append(lathe("OBo_propnut", [(0.0, 0.0), (0.012, 0.0), (0.012, 0.012), (0.0, 0.016)], Vector((px - 0.064, cy, gz)), (-1, 0, 0), MAT["Stainless"], 6))
    for k in range(3):
        out.append(prop_blade(MAT, f"OBo_blade{k}", Vector((px - 0.03, cy, gz)), 2 * math.pi * k / 3))
    return out


def prop_blade(MAT, name, hub, phase):
    """One blade: a rounded outline twisted to the pitch, thin, root at the hub."""
    bm = bmesh.new()
    rows = []
    R, root = 0.099, 0.026
    for i in range(9):
        r = root + (R - root) * i / 8
        w = 0.055 * math.sin(math.pi * (0.15 + 0.85 * i / 8)) + 0.012
        pitch = math.atan(0.19 / (2 * math.pi * r))              # a 7.5 in pitch
        row = []
        for j in range(5):
            s = (j / 4 - 0.5) * w
            local = Vector((s * math.sin(pitch), s * math.cos(pitch), r))
            row.append(local)
        rows.append(row)
    vs = []
    for row in rows:
        top = [bm.verts.new(Matrix.Rotation(phase, 3, "X") @ (p + Vector((0.0015, 0, 0)))) for p in row]
        bot = [bm.verts.new(Matrix.Rotation(phase, 3, "X") @ (p - Vector((0.0015, 0, 0)))) for p in row]
        vs.append((top, bot))
    for (t0, b0), (t1, b1) in zip(vs[:-1], vs[1:]):
        for j in range(len(t0) - 1):
            bm.faces.new((t0[j], t0[j + 1], t1[j + 1], t1[j]))
            bm.faces.new((b0[j + 1], b0[j], b1[j], b1[j + 1]))
        bm.faces.new((t0[0], t1[0], b1[0], b0[0]))
        bm.faces.new((t1[-1], t0[-1], b0[-1], b1[-1]))
    t, b = vs[-1]
    for j in range(len(t) - 1):
        bm.faces.new((t[j], t[j + 1], b[j + 1], b[j]))
    bmesh.ops.translate(bm, verts=bm.verts, vec=hub)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, MAT["BlackPlastic"])


def brackets(MAT):
    """The motor's own clamp and swivel brackets on the pad, and the transom bracket the pad hangs from."""
    out = []
    # the transom bracket: a stainless plate on the transom, two pairs of parallel arms, the pad
    out.append(plate("OBb_plate", [(STERN - 0.006, 0.30), (STERN, 0.30), (STERN, 0.56), (STERN - 0.006, 0.56)], Y - 0.10, Y + 0.10, MAT["Stainless"], bev=0.0015))
    for z in (0.33, 0.53):
        for dy in (-0.075, 0.075):
            out += hex_head(f"OBb_bolt{z}{dy}", Vector((STERN - 0.006, Y + dy, z)), (-1, 0, 0), 0.013, 0.006, MAT["Stainless"])
    pad_x = STERN - 0.165
    for side in (1, -1):
        for k, z in enumerate((0.36, 0.48)):
            arm = [(STERN - 0.004, z - 0.012), (pad_x + 0.015, z - 0.012 - 0.04), (pad_x + 0.015, z + 0.012 - 0.04), (STERN - 0.004, z + 0.012)]
            out.append(plate(f"OBb_arm{side}{k}", arm, Y + side * 0.088 - 0.005, Y + side * 0.088 + 0.005, MAT["Stainless"], bev=0.0015))
            for px, pz in ((STERN - 0.02, z), (pad_x + 0.03, z - 0.038)):
                out.append(cyl(f"OBb_pin{side}{k}{px:.2f}", Vector((px, Y + side * 0.075, pz)), Vector((px, Y + side * 0.098, pz)), 0.0055, MAT["Stainless"], 12))
    # the lift spring between the plate and the lower arms, and the lock pin on its lanyard
    pts = [Vector((STERN - 0.03 - 0.10 * t, Y + 0.008 * math.cos(t * 50), 0.40 - 0.05 * t + 0.008 * math.sin(t * 50))) for t in [i / 120 for i in range(121)]]
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        tg = (pts[min(i + 1, 120)] - pts[max(i - 1, 0)]).normalized()
        u = tg.orthogonal().normalized()
        w = tg.cross(u)
        rings.append([bm.verts.new(p + 0.0018 * (u * math.cos(2 * math.pi * k / 6) + w * math.sin(2 * math.pi * k / 6))) for k in range(6)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(6):
            bm.faces.new((a[k], a[(k + 1) % 6], b[(k + 1) % 6], b[k]))
    out.append(mesh_obj("OBb_spring", bm, MAT["Stainless"]))
    out.append(cyl("OBb_lockpin", Vector((STERN - 0.08, Y - 0.10, 0.45)), Vector((STERN - 0.08, Y + 0.10, 0.45)), 0.004, MAT["Stainless"], 10))
    out.append(lathe("OBb_lockring", [(0.009, -0.0015), (0.012, -0.0015), (0.012, 0.0015), (0.009, 0.0015), (0.009, -0.0015)], Vector((STERN - 0.08, Y + 0.106, 0.45)), (0, 1, 0), MAT["Stainless"], 16))
    # the pad: HDPE board the motor clamps to
    out.append(plate("OBb_pad", [(pad_x + 0.02, CLAMP_Z - 0.22), (pad_x - 0.015, CLAMP_Z - 0.22), (pad_x - 0.015, CLAMP_Z), (pad_x + 0.02, CLAMP_Z)], Y - 0.12, Y + 0.12, MAT["BlackPlastic"], bev=0.004))
    # the motor's clamp bracket: a cast hook over the pad's top, two clamp screws with T-handles pressing its front
    hook = [(pad_x + 0.034, CLAMP_Z - 0.10), (pad_x + 0.024, CLAMP_Z - 0.10), (pad_x + 0.024, CLAMP_Z + 0.004), (pad_x - 0.022, CLAMP_Z + 0.004),
            (pad_x - 0.022, CLAMP_Z - 0.06), (pad_x - 0.034, CLAMP_Z - 0.06), (pad_x - 0.034, CLAMP_Z + 0.018), (pad_x + 0.034, CLAMP_Z + 0.018)]
    for side in (1, -1):
        out.append(plate(f"OBc_hook{side}", hook, Y + side * 0.075 - 0.012, Y + side * 0.075 + 0.012, MAT["OutboardBlack"], bev=0.003))
        sx = pad_x + 0.034
        out.append(cyl(f"OBc_screw{side}", Vector((sx - 0.015, Y + side * 0.075, CLAMP_Z - 0.07)), Vector((sx + 0.035, Y + side * 0.075, CLAMP_Z - 0.07)), 0.0065, MAT["Stainless"], 12))
        out.append(cyl(f"OBc_tbar{side}", Vector((sx + 0.035, Y + side * 0.075 - 0.04, CLAMP_Z - 0.07)), Vector((sx + 0.035, Y + side * 0.075 + 0.04, CLAMP_Z - 0.07)), 0.0055, MAT["Stainless"], 12))
        out.append(lathe(f"OBc_foot{side}", [(0.0, 0.0), (0.016, 0.0), (0.016, 0.006), (0.0, 0.006)], Vector((pad_x + 0.022, Y + side * 0.075, CLAMP_Z - 0.07)), (-1, 0, 0), MAT["BlackPlastic"], 20))
    # the tilt tube across the hooks' backs and the swivel bracket the motor turns in
    out.append(cyl("OBc_tilttube", Vector((pad_x - 0.03, Y - 0.10, CLAMP_Z - 0.03)), Vector((pad_x - 0.03, Y + 0.10, CLAMP_Z - 0.03)), 0.014, MAT["Stainless"], 20))
    for side in (1, -1):
        out += nylock(f"OBc_tiltnut{side}", Vector((pad_x - 0.03, Y + side * 0.10, CLAMP_Z - 0.03)), (0, side, 0), 0.019, MAT["Stainless"])
    out.append(lathe("OBc_swivel", [(0.0, 0.0), (0.032, 0.0), (0.035, 0.02), (0.035, 0.14), (0.03, 0.16), (0.0, 0.16)],
                     Vector((AXIS_X, Y, CLAMP_Z - 0.17)), (0, 0, 1), MAT["OutboardBlack"], 28))
    return out


def tiller_arm(MAT):
    """The motor's tiller: from the lower cowl's front, toward the boat and up a little, a ribbed twist grip, the stop button."""
    out = []
    base = Vector((AXIS_X + 0.06, Y - 0.02, CLAMP_Z + 0.06))
    tip = base + Vector((0.40, -0.10, 0.07))
    d = (tip - base).normalized()
    out.append(lathe("OBt_arm", [(0.0, 0.0), (0.03, 0.0), (0.028, 0.06), (0.02, 0.20), (0.018, 0.25), (0.0, 0.25)], base, d, MAT["OutboardBlack"], 24))
    grip = [(0.0, 0.0)] + [(0.0215 if k % 2 == 0 else 0.0195, 0.25 + 0.009 * k) for k in range(17)] + [(0.018, 0.405), (0.0, 0.41)]
    out.append(lathe("OBt_grip", [(r, h - 0.25) for r, h in grip], base + d * 0.25, d, MAT["BlackPlastic"], 24))
    out.append(lathe("OBt_stop", [(0.0, 0.0), (0.008, 0.0), (0.008, 0.008), (0.0, 0.01)], base + d * 0.09 + Vector((0, 0, 0.024)), (0, 0, 1), MAT["RedPlastic"], 16))
    out.append(cyl("OBt_shift", Vector((AXIS_X - 0.02, Y + 0.13, CLAMP_Z + 0.02)), Vector((AXIS_X + 0.04, Y + 0.16, CLAMP_Z + 0.07)), 0.006, MAT["BlackPlastic"], 10))
    return out


def build(MAT):
    """Every part of the outboard and its bracket (game part: the hull)."""
    return brackets(MAT) + cowl(MAT) + lower_unit(MAT) + tiller_arm(MAT)
