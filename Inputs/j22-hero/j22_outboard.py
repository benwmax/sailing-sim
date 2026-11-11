"""Boat fidelity (pc/j22-detail, assembly 2; part detail loop Nov 9 2026, docs/part-detail-loop/outboard.md): the hero
J/22's outboard and its transom bracket. The club's lesson boats carry a 4-6 hp single-cylinder long-shaft four-stroke
(Bean's lesson photos IMG_9273, IMG_9266, 1000032829: a black cowl, the tiller arm folded up beside it while sailing, a
red coiled kill cord, a white transom bracket). The maker here is the kit's made-up TERNWAY; no real maker's marks.

What the loop changed from the October build (a squat domed cowl, the tiller lying forward over the deck, a 0.62 m
shaft, a stainless bracket): a taller cowl with a near-vertical sides, a sloped front face carrying a big knurled fuel
cap and the choke knob, a carry handle in a recess at the back of the top, the pan with its shift lever and kill switch,
the coiled red lanyard, the tiller arm folded up (aluminium arm, ribbed black twist grip), a 20 in (508 mm) shaft, the
bracket in light anodised aluminium on a white pad, and a satin (not glossy) black finish.

Sizes: shaft (clamp top to cavitation plate) 508 mm, the catalogue's 20 in long shaft; cowl 0.43 m long, 0.29 m wide,
0.38 m from the clamp's top to the cowl's top (proportions read off IMG_9273 against the shaft and the cowl's width);
7.8 in three-blade prop. The cavitation plate stays where the October build put it (0.10 m under the waterline), so the
clamp drops 0.11 m and the bracket's arms run down to it. Blender frame (x forward, z up; the hero's y as
build_j22_hero.py)."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from j22_geom import apply_mods, cyl, link, mesh_obj, tube
from j22_steering import hex_head, lathe, nylock, plate

STERN = -3.41
Y = 0.42                  # the bracket's centre across the transom, on the port quarter (0.55 until the hull took Plan E's
                          # 1.23 m transom, docs/shape-loop wave 1: there the plate ran 2.5 cm past the corner)
CAV_Z = -0.10             # the anti-cavitation plate (unchanged from the October build)
CLAMP_Z = CAV_Z + 0.508   # the clamp's top on the bracket's pad: a 20 in shaft
AXIS_X = STERN - 0.205    # the motor's steering axis (the swivel bracket's tube)
CX = AXIS_X - 0.12        # the cowl's centre, fore and aft
PAN_TOP = CLAMP_Z + 0.10  # the parting line between the pan and the upper cowl
COWL_H = 0.27             # the upper cowl's height above the parting line
A_FWD, A_AFT, B = 0.215, 0.215, 0.145   # the cowl's half-length forward and aft of CX, and half-width


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


def asym_ring(bm, cx, cy, z, af, aa, b, n=3.4, segs=48):
    """A superellipse ring with different half-lengths forward (af, +x) and aft (aa) of cx; half-width b."""
    out = []
    for k in range(segs):
        t = 2 * math.pi * k / segs
        c, s = math.cos(t), math.sin(t)
        x = math.copysign(abs(c) ** (2 / n), c)
        y = b * math.copysign(abs(s) ** (2 / n), s)
        out.append(bm.verts.new((cx + x * (af if x > 0 else aa), cy + y, z)))
    return out


def front_af(f):
    """The upper cowl's forward half-length at height fraction f: vertical to 0.30, then the raked front face."""
    return A_FWD if f < 0.30 else A_FWD - 0.12 * (f - 0.30) / 0.70


def cowl_surface(f):
    """(z, forward half-length, aft half-length, half-width) of the upper cowl at height fraction f (0..1)."""
    return PAN_TOP + 0.008 + COWL_H * f, front_af(f), A_AFT - 0.015 * f, B - 0.012 * f


def side_y(dx, f, n=3.6):
    """The upper cowl's half-width at dx forward of CX and height fraction f (on the superellipse)."""
    z, af, aa, b = cowl_surface(f)
    a = af if dx > 0 else aa
    return b * max(0.0, 1 - abs(dx / a) ** n) ** (1 / n)


def cowl(MAT):
    """The lower cowl (pan), the parting line, the tall upper cowl with its sloped front, the fittings on it."""
    cx, cy = CX, Y
    out = []
    # the pan: from the swivel housing's top widening into the cowl's footprint
    bm = bmesh.new()
    rings = [asym_ring(bm, cx, cy, z, af, aa, b, 3.2) for z, af, aa, b in (
        (CLAMP_Z - 0.035, 0.12, 0.11, 0.075), (CLAMP_Z - 0.008, 0.18, 0.17, 0.118), (CLAMP_Z + 0.035, 0.208, 0.205, 0.140),
        (PAN_TOP - 0.01, 0.214, 0.212, 0.144), (PAN_TOP, 0.212, 0.210, 0.143))]
    out.append(loft_rings("OBo_pan", rings, MAT["OutboardBlack"], bm))
    # the parting line: a slim dark gasket a little inside the shells
    b2 = bmesh.new()
    out.append(loft_rings("OBo_gasket", [asym_ring(b2, cx, cy, PAN_TOP, 0.206, 0.204, 0.139), asym_ring(b2, cx, cy, PAN_TOP + 0.008, 0.206, 0.204, 0.139)],
                          MAT["BlackPlastic"], b2))
    # the upper cowl: straight sides, the sloped front face, a rounded edge rolling over into a near-flat top
    bm = bmesh.new()
    rings = []
    R = 0.045                                      # the top edge's radius
    for i in range(14):
        f = 0.85 * i / 13
        z, af, aa, b = cowl_surface(f)
        rings.append(asym_ring(bm, cx, cy, z, af, aa, b, 3.6))
    for i in range(1, 8):
        t = (math.pi / 2) * i / 7
        z, af, aa, b = cowl_surface(0.85)
        zz = PAN_TOP + 0.008 + COWL_H - R * (1 - math.sin(t))
        inset = R * (1 - math.cos(t))
        rings.append(asym_ring(bm, cx, cy, zz, af - inset, aa - inset, b - inset, 3.6 - 1.2 * i / 7))
    z_top = PAN_TOP + 0.008 + COWL_H
    rings.append(asym_ring(bm, cx - 0.01, cy, z_top + 0.006, (af - R) * 0.55, (aa - R) * 0.55, (b - R) * 0.55, 2.4))
    out.append(loft_rings("OBo_cowl", rings, MAT["OutboardBlack"], bm))
    # the carry handle at the back of the top: a dark recess and the moulded grip over it
    hx = cx - (A_AFT - 0.075)
    bm = bmesh.new()
    rec = asym_ring(bm, hx, cy, z_top + 0.0015, 0.036, 0.036, 0.082, 4.0, 32)
    bm.faces.new(rec)
    out.append(mesh_obj("OBo_handlerecess", bm, MAT["DecalBlack"], smooth_shade=False))
    out.append(cyl("OBo_handle", Vector((hx - 0.022, cy - 0.074, z_top + 0.006)), Vector((hx - 0.022, cy + 0.074, z_top + 0.006)), 0.011, MAT["OutboardBlack"], 20))
    # the fuel cap on the sloped front: a big knurled cap with a vent screw in its middle
    f = 0.74
    z, af, aa, b = cowl_surface(f)
    nrm = Vector((0.70 * COWL_H, 0, 0.12)).normalized()     # the slope's outward normal (rise over run of the face)
    capo = Vector((cx + af - 0.006, cy, z))
    out.append(lathe("OBo_capwell", [(0.0, 0.0), (0.047, 0.0), (0.047, 0.0015), (0.0, 0.0015)], capo + nrm * 0.0035, nrm, MAT["DecalBlack"], 40))
    out.append(knurled_cap("OBo_fuelcap", capo, nrm, 0.036, 0.022, 14, MAT["BlackPlastic"]))
    out.append(lathe("OBo_capvent", [(0.0, 0.0), (0.011, 0.0), (0.011, 0.012), (0.009, 0.014), (0.0, 0.014)], capo + nrm * 0.021, nrm, MAT["BlackPlastic"], 6))
    # the choke / stop lever on the raked face below the cap, in its dark slot
    def on_face(f, out_by):
        z, af, _, _ = cowl_surface(f)
        return cx + af + out_by, z
    s0, s1 = on_face(0.38, 0.0018), on_face(0.56, 0.0018)
    t0, t1 = on_face(0.38, -0.004), on_face(0.56, -0.004)
    out.append(plate("OBo_chokepanel", [t0, s0, s1, t1], cy + 0.012, cy + 0.062, MAT["DecalBlack"], bev=0.001))
    k0, k1 = on_face(0.41, 0.0), on_face(0.53, 0.0)
    k2, k3 = on_face(0.53, 0.024), on_face(0.44, 0.024)
    out.append(plate("OBo_chokeknob", [k0, k1, k2, k3], cy + 0.03, cy + 0.044, MAT["BlackPlastic"], bev=0.002))
    fx = cx + A_FWD
    b0, b1 = on_face(0.18, 0.0012), on_face(0.28, 0.0012)
    out.append(plate("OBo_badge", [(b0[0] - 0.003, b0[1]), b0, b1, (b1[0] - 0.003, b1[1])], cy - 0.075, cy + 0.075, MAT["SheaveGrey"], bev=0))
    # the maker's name along both sides (the kit's made-up TERNWAY), the horsepower at the back, the engine type on the front
    fz = 0.45
    zt = PAN_TOP + 0.008 + COWL_H * fz
    for sgn in (1, -1):
        out.append(text(MAT, f"OBo_brand{sgn}", "TERNWAY", 0.042, Vector((cx + 0.02, cy + sgn * (side_y(0.02, fz) + 0.0004), zt)), sgn, MAT["WhitePlastic"]))
        out.append(text(MAT, f"OBo_hp{sgn}", "5", 0.050, Vector((cx - 0.135, cy + sgn * (side_y(-0.135, fz) + 0.0012), zt)), sgn, MAT["WhitePlastic"]))
        out.append(plate(f"OBo_stripe{sgn}", [(cx - 0.19, PAN_TOP + 0.03), (cx + 0.20, PAN_TOP + 0.03), (cx + 0.20, PAN_TOP + 0.036), (cx - 0.19, PAN_TOP + 0.036)],
                         cy + sgn * (B - 0.0004) - 0.0006, cy + sgn * (B - 0.0004) + 0.0006, MAT["SheaveGrey"], bev=0))
    out.append(text_front(MAT, "OBo_type", "4-STROKE", 0.030, Vector((fx + 0.0012, cy - 0.005, PAN_TOP + 0.038)), MAT["WhitePlastic"]))
    # on the pan's front: the shift lever (inboard side) and the kill switch with its clip (outboard side)
    px = cx + 0.212
    out.append(plate("OBo_shiftboss", [(px - 0.01, CLAMP_Z + 0.03), (px + 0.012, CLAMP_Z + 0.03), (px + 0.012, CLAMP_Z + 0.07), (px - 0.01, CLAMP_Z + 0.07)],
                     cy - 0.10, cy - 0.07, MAT["BlackPlastic"], bev=0.003))
    out.append(plate("OBo_shiftlever", [(px + 0.004, CLAMP_Z + 0.04), (px + 0.008, CLAMP_Z + 0.06), (px + 0.058, CLAMP_Z + 0.072), (px + 0.060, CLAMP_Z + 0.058)],
                     cy - 0.094, cy - 0.080, MAT["BlackPlastic"], bev=0.003))
    out.append(text_front(MAT, "OBo_shiftN", "N", 0.016, Vector((px + 0.0125, cy - 0.065, CLAMP_Z + 0.05)), MAT["WhitePlastic"]))
    ks = Vector((px + 0.004, cy + 0.035, CLAMP_Z + 0.045))
    out.append(lathe("OBo_killswitch", [(0.0, 0.0), (0.016, 0.0), (0.016, 0.012), (0.012, 0.016), (0.0, 0.016)], ks, (1, 0, 0), MAT["BlackPlastic"], 20))
    out.append(plate("OBo_killclip", [(ks.x + 0.014, ks.z - 0.012), (ks.x + 0.022, ks.z - 0.012), (ks.x + 0.022, ks.z + 0.010), (ks.x + 0.014, ks.z + 0.010)],
                     ks.y - 0.011, ks.y + 0.011, MAT["RedPlastic"], bev=0.002))
    out.append(kill_cord(MAT, Vector((ks.x + 0.020, ks.y, ks.z - 0.012))))
    return out


def knurled_cap(name, origin, axis, r, h, lobes, mat, segs=56):
    """A screw cap: a short cylinder whose rim is scalloped into lobes, its top domed a little."""
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    w = axis.cross(u)
    bm = bmesh.new()
    prof = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.8), (0.93, 0.97), (0.6, 1.0), (0.0, 1.03)]
    rings = []
    for rr, hh in prof:
        ring = []
        for k in range(segs):
            t = 2 * math.pi * k / segs
            knurl = 1 - 0.09 * max(0.0, math.cos(lobes * t)) ** 0.6 if rr > 0.9 else 1.0
            ring.append(bm.verts.new(origin + axis * (hh * h) + (u * math.cos(t) + w * math.sin(t)) * max(r * rr * knurl, 1e-5)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)


def kill_cord(MAT, top):
    """The engine stop lanyard: a red coiled cord hanging from the clip, a short straight tail and a snap hook at its end."""
    pts = [top + Vector((0.004, 0, -0.012 * t / 0.04)) for t in (0.0, 0.02, 0.04)]
    c0 = pts[-1] + Vector((0, 0, -0.004))
    turns, segs, pitch, rad = 22, 8, 0.0125, 0.014
    for i in range(turns * segs + 1):
        a = 2 * math.pi * i / segs
        drift = Vector((0.035 * math.sin(i / (turns * segs) * math.pi * 0.8), 0.015 * i / (turns * segs), 0))   # it bows forward, clear of the clamp
        pts.append(c0 + drift + Vector((rad * math.cos(a) - rad, rad * math.sin(a), -pitch * i / segs)))
    end = pts[-1]
    pts += [end + Vector((0.0, 0.0, -0.015)), end + Vector((-0.004, 0.0, -0.04))]
    cord = tube("OBo_killcord", [tuple(p) for p in pts], 0.0030, MAT["TelltaleRed"], res=6)
    from j22_geom import to_mesh
    cord = to_mesh(cord)
    cord.name = "OBo_killcord"
    return cord


def text(MAT, name, body, size, at, sgn, mat):
    """Raised lettering on a cowl side (local XY of the text stood up on the side, reading forward on both sides)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = 0.0007
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    link(ob)
    ob.matrix_world = Matrix.Translation(at) @ Matrix.Rotation(math.radians(90), 4, "X") @ (Matrix.Rotation(math.pi, 4, "Y") if sgn > 0 else Matrix.Identity(4))
    ob.data.materials.append(mat)
    return _convert(ob)


def text_front(MAT, name, body, size, at, mat):
    """Raised lettering on the cowl's front face, read from forward (from the cockpit)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = 0.0006
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    link(ob)
    ob.matrix_world = Matrix.Translation(at) @ Matrix.Rotation(math.radians(90), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
    ob.data.materials.append(mat)
    return _convert(ob)


def _convert(ob):
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
    # midsection (driveshaft and exhaust housing): a slim streamlined column flaring into the pan at the top
    bm = bmesh.new()
    rings = []
    for z, chord, th in ((CAV_Z + 0.004, 0.15, 0.27), (CAV_Z + 0.10, 0.135, 0.27), (CLAMP_Z - 0.16, 0.125, 0.30), (CLAMP_Z - 0.07, 0.14, 0.38),
                         (CLAMP_Z - 0.035, 0.17, 0.44)):
        rings.append(foil_ring(bm, cx, cy, z, chord, th))
    out.append(loft_rings("OBo_midsection", rings, MAT["OutboardBlack"], bm))
    # the anti-cavitation plate: flat, wider than the leg, rounded aft, with its anode tab under it
    pl = [(cx + 0.06, -0.055), (cx - 0.02, -0.09), (cx - 0.15, -0.085), (cx - 0.185, -0.05), (cx - 0.19, 0.0), (cx - 0.185, 0.05), (cx - 0.15, 0.085),
          (cx - 0.02, 0.09), (cx + 0.06, 0.055)]
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
    rings = [foil_ring(bm, cx, cy, z, 0.13, 0.28) for z in (gz + 0.03, CAV_Z - 0.002)]
    out.append(loft_rings("OBo_strut", rings, MAT["OutboardBlack"], bm))
    out.append(lathe("OBo_gearcase", [(0.0, 0.0), (0.020, 0.006), (0.033, 0.03), (0.039, 0.07), (0.039, 0.16), (0.034, 0.22), (0.027, 0.245), (0.0, 0.25)],
                     Vector((cx + 0.11, cy, gz)), (-1, 0, 0), MAT["OutboardBlack"], 32))
    for sgn in (1, -1):
        for k in range(5):
            out.append(plate(f"OBo_intake{sgn}{k}", [(cx + 0.02 - 0.012 * k, gz + 0.012), (cx + 0.016 - 0.012 * k, gz + 0.012), (cx + 0.016 - 0.012 * k, gz + 0.032), (cx + 0.02 - 0.012 * k, gz + 0.032)],
                             cy + sgn * 0.038 - 0.0015, cy + sgn * 0.038 + 0.0015, MAT["BlackPlastic"], bev=0))
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
    """The motor's own clamp and swivel brackets on the pad, and the transom bracket the pad hangs from (lowered)."""
    out = []
    BR = MAT["CastAlu"]                       # light anodised aluminium (the photos' white-silver bracket)
    out.append(plate("OBb_plate", [(STERN - 0.007, 0.30), (STERN, 0.30), (STERN, 0.56), (STERN - 0.007, 0.56)], Y - 0.10, Y + 0.10, BR, bev=0.0015))
    for z in (0.33, 0.53):
        for dy in (-0.075, 0.075):
            out += hex_head(f"OBb_bolt{z}{dy}", Vector((STERN - 0.007, Y + dy, z)), (-1, 0, 0), 0.013, 0.006, MAT["Stainless"])
    pad_x = STERN - 0.165
    drop = 0.04 + (0.52 - CLAMP_Z)            # the arms run down aft to the lowered pad
    for side in (1, -1):
        # the side cheeks the arms pivot on, at the plate and at the pad
        out.append(plate(f"OBb_cheek{side}", [(STERN - 0.006, 0.33), (STERN - 0.045, 0.33), (STERN - 0.045, 0.51), (STERN - 0.006, 0.51)],
                         Y + side * 0.098 - 0.003, Y + side * 0.098 + 0.003, BR, bev=0.0015))
        for k, z in enumerate((0.36, 0.48)):
            zp = z - drop
            arm = [(STERN - 0.02, z - 0.013), (pad_x + 0.03, zp - 0.013), (pad_x + 0.03, zp + 0.013), (STERN - 0.02, z + 0.013)]
            out.append(plate(f"OBb_arm{side}{k}", arm, Y + side * 0.088 - 0.006, Y + side * 0.088 + 0.006, BR, bev=0.002))
            for ppx, pz in ((STERN - 0.02, z), (pad_x + 0.03, zp)):
                out.append(cyl(f"OBb_pin{side}{k}{ppx:.2f}", Vector((ppx, Y + side * 0.078, pz)), Vector((ppx, Y + side * 0.104, pz)), 0.006, MAT["Stainless"], 12))
    # the lift spring between the plate and the lower arms, and the lock lever
    z0, z1 = 0.40, 0.36 - drop + 0.03
    pts = [Vector((STERN - 0.03 - 0.10 * t, Y + 0.008 * math.cos(t * 50), z0 + (z1 - z0) * t + 0.008 * math.sin(t * 50))) for t in [i / 120 for i in range(121)]]
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
    out.append(cyl("OBb_lockpin", Vector((STERN - 0.035, Y - 0.105, 0.45)), Vector((STERN - 0.035, Y + 0.105, 0.45)), 0.004, MAT["Stainless"], 10))
    # the lift lever: a long pale bar from the upper arm's pivot, up and aft to a black knob (the photos' white arm)
    out.append(plate("OBb_lever", [(STERN - 0.02, 0.468), (STERN - 0.02, 0.492), (STERN - 0.15, 0.62), (STERN - 0.166, 0.606)],
                     Y - 0.112, Y - 0.104, BR, bev=0.002))
    out.append(lathe("OBb_leverknob", [(0.0, 0.0), (0.011, 0.0), (0.011, 0.024), (0.0, 0.027)], Vector((STERN - 0.16, Y - 0.108, 0.614)), (-0.7, 0, 0.7), MAT["BlackPlastic"], 12))
    # the pad: white HDPE board the motor clamps to, carried by the arms' aft ends
    out.append(plate("OBb_pad", [(pad_x + 0.035, CLAMP_Z - 0.22), (pad_x - 0.015, CLAMP_Z - 0.22), (pad_x - 0.015, CLAMP_Z), (pad_x + 0.035, CLAMP_Z)],
                     Y - 0.12, Y + 0.12, MAT["WhitePlastic"], bev=0.004))
    # the motor's clamp bracket: a cast hook over the pad's top, two clamp screws with T-handles pressing its front
    hook = [(pad_x + 0.049, CLAMP_Z - 0.10), (pad_x + 0.039, CLAMP_Z - 0.10), (pad_x + 0.039, CLAMP_Z + 0.004), (pad_x - 0.022, CLAMP_Z + 0.004),
            (pad_x - 0.022, CLAMP_Z - 0.06), (pad_x - 0.034, CLAMP_Z - 0.06), (pad_x - 0.034, CLAMP_Z + 0.018), (pad_x + 0.049, CLAMP_Z + 0.018)]
    for side in (1, -1):
        out.append(plate(f"OBc_hook{side}", hook, Y + side * 0.075 - 0.012, Y + side * 0.075 + 0.012, MAT["OutboardBlack"], bev=0.003))
        sx = pad_x + 0.049
        out.append(cyl(f"OBc_screw{side}", Vector((sx - 0.015, Y + side * 0.075, CLAMP_Z - 0.07)), Vector((sx + 0.035, Y + side * 0.075, CLAMP_Z - 0.07)), 0.0065, MAT["Stainless"], 12))
        out.append(cyl(f"OBc_tbar{side}", Vector((sx + 0.035, Y + side * 0.075 - 0.04, CLAMP_Z - 0.07)), Vector((sx + 0.035, Y + side * 0.075 + 0.04, CLAMP_Z - 0.07)), 0.0055, MAT["BlackPlastic"], 12))
        out.append(lathe(f"OBc_foot{side}", [(0.0, 0.0), (0.016, 0.0), (0.016, 0.006), (0.0, 0.006)], Vector((pad_x + 0.037, Y + side * 0.075, CLAMP_Z - 0.07)), (-1, 0, 0), MAT["BlackPlastic"], 20))
    # the tilt tube across the hooks' backs, the tilt lever, and the swivel bracket the motor turns in
    out.append(cyl("OBc_tilttube", Vector((pad_x - 0.03, Y - 0.10, CLAMP_Z - 0.03)), Vector((pad_x - 0.03, Y + 0.10, CLAMP_Z - 0.03)), 0.014, MAT["Stainless"], 20))
    for side in (1, -1):
        out += nylock(f"OBc_tiltnut{side}", Vector((pad_x - 0.03, Y + side * 0.10, CLAMP_Z - 0.03)), (0, side, 0), 0.019, MAT["Stainless"])
    out.append(cyl("OBc_tiltlever", Vector((pad_x - 0.03, Y - 0.115, CLAMP_Z - 0.03)), Vector((pad_x + 0.02, Y - 0.14, CLAMP_Z - 0.01)), 0.005, MAT["BlackPlastic"], 10))
    # the swivel yoke: the black casting joining the swivel to the pan, with the steering friction knob
    out.append(plate("OBc_yoke", [(AXIS_X + 0.05, CLAMP_Z - 0.045), (AXIS_X - 0.07, CLAMP_Z - 0.045), (AXIS_X - 0.09, CLAMP_Z - 0.01), (AXIS_X + 0.07, CLAMP_Z - 0.01)],
                     Y - 0.07, Y + 0.07, MAT["OutboardBlack"], bev=0.006))
    out.append(lathe("OBc_frictionknob", [(0.0, 0.0), (0.014, 0.0), (0.015, 0.012), (0.012, 0.016), (0.0, 0.017)], Vector((AXIS_X + 0.04, Y - 0.07, CLAMP_Z - 0.03)), (0, -1, 0), MAT["BlackPlastic"], 14))
    out.append(lathe("OBc_swivel", [(0.0, 0.0), (0.032, 0.0), (0.035, 0.02), (0.035, 0.14), (0.03, 0.16), (0.0, 0.16)],
                     Vector((AXIS_X, Y, CLAMP_Z - 0.17)), (0, 0, 1), MAT["OutboardBlack"], 28))
    return out


def tiller_arm(MAT):
    """The motor's tiller folded up as it is stowed under sail (photos IMG_9273, IMG_9266): its pivot casting at the pan's
    front outboard corner, an open aluminium channel (two rails and a web, the photos' ladder look) leaning a little
    outboard, the ribbed black twist grip on top."""
    out = []
    piv = Vector((CX + 0.20, Y + 0.12, CLAMP_Z + 0.045))
    out.append(plate("OBt_pivot", [(piv.x - 0.05, piv.z - 0.03), (piv.x + 0.02, piv.z - 0.03), (piv.x + 0.026, piv.z + 0.025), (piv.x - 0.05, piv.z + 0.035)],
                     piv.y - 0.026, piv.y + 0.016, MAT["OutboardBlack"], bev=0.005))
    out += hex_head("OBt_pivotbolt", piv + Vector((0, 0.016, 0)), (0, 1, 0), 0.013, 0.006, MAT["Stainless"])
    d = Vector((0.0, 0.20, 1.0)).normalized()          # leaning outboard, as the photos show
    side = Vector((1, 0, 0))                           # the channel's rails sit fore and aft of each other
    depth = d.cross(side).normalized()
    L = 0.31
    a0 = piv + Vector((0, 0.03, 0.01))
    for k, sx in enumerate((-0.014, 0.014)):
        p0 = a0 + side * sx
        bm = bmesh.new()
        corners = [(-0.0025, -0.012), (0.0025, -0.012), (0.0025, 0.012), (-0.0025, 0.012)]
        rings = [[bm.verts.new(p0 + d * t + side * cx_ + depth * cy_) for cx_, cy_ in corners] for t in (0.0, L)]
        for ra, rb in zip(rings[:-1], rings[1:]):
            for j in range(4):
                bm.faces.new((ra[j], ra[(j + 1) % 4], rb[(j + 1) % 4], rb[j]))
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        out.append(mesh_obj(f"OBt_rail{k}", bm, MAT["CastAlu"], smooth_shade=False))
    # the web along the back of the channel, with the throttle cable showing in the open front, and a cross brace
    out.append(cyl("OBt_web", a0 - depth * 0.010, a0 - depth * 0.010 + d * L, 0.006, MAT["OutboardBlack"], 10))
    out.append(cyl("OBt_cable", a0 + depth * 0.002 + d * 0.02, a0 + depth * 0.002 + d * (L - 0.02), 0.003, MAT["BlackPlastic"], 8))
    for t in (0.10, 0.22):
        out.append(cyl(f"OBt_brace{t}", a0 + d * t - side * 0.016, a0 + d * t + side * 0.016, 0.003, MAT["Stainless"], 8))
    a1 = a0 + d * L
    out.append(lathe("OBt_stop", [(0.0, 0.0), (0.008, 0.0), (0.008, 0.008), (0.0, 0.01)], a0 + d * 0.05 + depth * 0.012, depth, MAT["RedPlastic"], 16))
    # the twist grip: ribbed rubber, a collar at its root, a rounded end
    grip = [(0.0, 0.0), (0.022, 0.0), (0.022, 0.012)] + [(0.0205 if k % 2 == 0 else 0.0188, 0.012 + 0.008 * k) for k in range(15)] + [(0.018, 0.13), (0.011, 0.136), (0.0, 0.138)]
    out.append(lathe("OBt_grip", grip, a1, d, MAT["BlackPlastic"], 24))
    return out


def build(MAT):
    """Every part of the outboard and its bracket (game part: the hull)."""
    return brackets(MAT) + cowl(MAT) + lower_unit(MAT) + tiller_arm(MAT)
