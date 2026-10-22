"""Boat fidelity (pc/j22-detail, assembly 3): the boom's fittings as Bean's photos show them (mast-boom-gooseneck-
connector, boom-end, boom-vang-closeup, outhaul-sheet-cleet). Replaces j22_details' gooseneck, boom_end and the vang's
upper block:

- the gooseneck: a stainless plate on the mast's aft face (rounded corners, eight countersunk screws) with two tangs
  welded on, a hex bolt down through both (the boom's swing) with its nylock under, a swivel knuckle between them, the
  boom's end casting (grey cast aluminium, screwed into the boom) reaching forward in a fork, a quick-release pin with
  its ring across the fork and knuckle (the boom's lift); the reef and cunningham hooks;
- the boom's aft end: an angled cast cap screwed on, the outhaul sheave in its slot, a shackle on top for the mainsheet's
  topping lift;
- the outhaul's fairlead cleat under the boom;
- the vang's upper block: a big block with perforated cheeks on a stainless strap from the boom's bail.

The parts the bake reads keep their names and centres (Gooseneck_vpin: the boom's pivot; BoomEnd_outhaul: Boom_Clew;
Vang_bail; MainsheetHigh), so no socket moves. Blender frame, as build_j22_hero.py."""
import math

import bmesh
from mathutils import Vector

from j22_geom import cyl, mesh_obj, tube
from j22_steering import carriage_head, hex_head, lathe, nylock, plate


def rounded(x0, x1, z0, z1, r, n=6):
    """A rounded rectangle's outline in (x, z)."""
    pts = []
    for cx, cz, a0 in ((x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180), (x1 - r, z0 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def plate_yz(name, outline_yz, x0, x1, mat, bev=0.001):
    """A plate lying in a y-z plane (on the mast's aft face): outline (y, z) extruded x0..x1."""
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in outline_yz]
    b = [bm.verts.new((x1, y, z)) for y, z in outline_yz]
    k = len(outline_yz)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    if bev:
        from j22_geom import apply_mods
        m = ob.modifiers.new("bev", "BEVEL")
        m.width, m.segments, m.limit_method, m.angle_limit = bev, 2, "ANGLE", math.radians(40)
        apply_mods(ob)
    return ob


def plate_xy(name, outline_xy, z0, z1, mat, bev=0.001):
    """A flat plate in plan: outline (x, y) extruded z0..z1."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for x, y in outline_xy]
    b = [bm.verts.new((x, y, z1)) for x, y in outline_xy]
    k = len(outline_xy)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    if bev:
        from j22_geom import apply_mods
        m = ob.modifiers.new("bev", "BEVEL")
        m.width, m.segments, m.limit_method, m.angle_limit = bev, 2, "ANGLE", math.radians(40)
        apply_mods(ob)
    return ob


def countersunk(name, p, axis, d, mat):
    """A countersunk machine screw's head, flush with a dimple and a cross slot."""
    axis = Vector(axis).normalized()
    out = [lathe(name, [(0.0, 0.0), (d / 2, 0.0), (d * 0.44, 0.0008), (0.0, 0.0008)], p, axis, mat, 16)]
    return out


def gooseneck(name, mast_aft, boom_z, M):
    p = Vector(mast_aft)
    out = []
    # the mast plate: stainless, rounded corners, on the mast's aft face, eight countersunk screws
    out.append(plate_yz(f"{name}_plate", rounded(-0.028, 0.028, boom_z - 0.08, boom_z + 0.08, 0.008),
                        p.x - 0.003, p.x + 0.001, M["Stainless"]))
    for zz in (-0.065, -0.045, 0.045, 0.065):
        for sgn in (1, -1):
            out += countersunk(f"{name}_scr{zz:+.3f}{sgn}", Vector((p.x - 0.003, sgn * 0.018, boom_z + zz)), (-1, 0, 0), 0.008, M["Stainless"])
    # two tangs welded on, top and bottom, round-ended aft, a bead of weld where they meet the plate
    px = p.x - 0.034
    for dz in (0.0275, -0.0275):
        outline = [(p.x - 0.003, -0.013), (px, -0.013)] + [(px - 0.013 * math.sin(math.pi * k / 10), -0.013 * math.cos(math.pi * k / 10)) for k in range(1, 10)] + [(px, 0.013), (p.x - 0.003, 0.013)]
        out.append(plate_xy(f"{name}_tang{dz:+.3f}", outline, boom_z + dz - 0.0025, boom_z + dz + 0.0025, M["Stainless"], bev=0.0008))
        out.append(tube(f"{name}_weld{dz:+.3f}", [(p.x - 0.004, -0.013, boom_z + dz + 0.0025 * (1 if dz > 0 else -1)),
                                                     (p.x - 0.004, 0.013, boom_z + dz + 0.0025 * (1 if dz > 0 else -1))], 0.0018, M["Stainless"]))
    # the bolt through both tangs (the boom's swing): the game reads Gooseneck_vpin's centre as the boom's pivot
    out.append(cyl(f"{name}_vpin", (px, 0, boom_z - 0.045), (px, 0, boom_z + 0.045), 0.004, M["Stainless"], 12))
    out += hex_head(f"{name}_vpinhead", Vector((px, 0, boom_z + 0.030)), (0, 0, 1), 0.013, 0.006, M["Stainless"])
    out += nylock(f"{name}_vpinnut", Vector((px, 0, boom_z - 0.030)), (0, 0, -1), 0.013, M["Stainless"])
    # the swivel knuckle between the tangs, round about the bolt, its tongue aft into the boom casting's fork
    out.append(lathe(f"{name}_knucklehub", [(0.0, -0.0225), (0.014, -0.0225), (0.0145, -0.02), (0.0145, 0.02), (0.014, 0.0225), (0.0, 0.0225)],
                     Vector((px, 0, boom_z)), (0, 0, 1), M["BlackPlastic"], 28))
    out.append(plate_xy(f"{name}_knuckle", [(px - 0.012, -0.009), (px - 0.066, -0.009), (px - 0.072, -0.004), (px - 0.072, 0.004), (px - 0.066, 0.009), (px - 0.012, 0.009)],
                        boom_z - 0.016, boom_z + 0.016, M["BlackPlastic"], bev=0.0025))
    # the boom's end casting: a sleeve shaped to the boom, two fork cheeks forward round the knuckle's tongue
    bx0, bx1 = p.x - 0.088, p.x - 0.135
    bm = bmesh.new()
    rings = []
    for x in (bx0, bx0 - 0.006, bx1):
        r_scale = 1.04 if x == bx0 - 0.006 else 1.0
        rings.append([bm.verts.new((x, 0.0285 * r_scale * math.sin(2 * math.pi * k / 32), boom_z + 0.0385 * r_scale * math.cos(2 * math.pi * k / 32))) for k in range(32)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(32):
            bm.faces.new((a[k], a[(k + 1) % 32], b[(k + 1) % 32], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out.append(mesh_obj(f"{name}_boomcap", bm, M["CastAlu"]))
    for sgn in (1, -1):
        fork = [(bx0 + 0.002, boom_z - 0.024), (px - 0.058, boom_z - 0.016)] + \
               [(px - 0.066 + 0.016 * math.cos(math.pi * k / 10 - math.pi / 2), boom_z + 0.016 * math.sin(math.pi * k / 10 - math.pi / 2)) for k in range(11)] + \
               [(px - 0.058, boom_z + 0.016), (bx0 + 0.002, boom_z + 0.024)]
        out.append(plate(f"{name}_fork{sgn}", fork, min(sgn * 0.0095, sgn * 0.0135), max(sgn * 0.0095, sgn * 0.0135), M["CastAlu"], bev=0.0015))
    # the quick-release pin across the fork (the boom's lift), its ring hanging
    hx = px - 0.066
    out.append(cyl(f"{name}_hpin", (hx, -0.022, boom_z), (hx, 0.019, boom_z), 0.004, M["Stainless"], 12))
    out.append(lathe(f"{name}_hpinhead", [(0.0, 0.0), (0.0065, 0.0), (0.0065, 0.004), (0.004, 0.006), (0.0, 0.0065)], Vector((hx, 0.019, boom_z)), (0, 1, 0), M["Stainless"], 16))
    out.append(lathe(f"{name}_hpinring", [(0.0105, -0.0009), (0.0125, -0.0009), (0.0125, 0.0009), (0.0105, 0.0009), (0.0105, -0.0009)],
                     Vector((hx, -0.024, boom_z - 0.012)), (0, 1, 0.35), M["Stainless"], 24))
    # screws through the boom into the casting, each side
    for sgn in (1, -1):
        for dx in (-0.012, -0.030):
            out.append(lathe(f"{name}_boomcapscr{sgn}{dx}", [(0.0, 0.0), (0.0045, 0.0), (0.0042, 0.0015), (0.0025, 0.0025), (0.0, 0.0027)],
                             Vector((bx1 + dx + 0.04, sgn * 0.0275, boom_z - 0.012)), (0, sgn, 0), M["Stainless"], 16))
    # the reef hook (port) and cunningham hook (starboard), bent rod on a small plate
    for sgn, nm in ((1, "reef"), (-1, "cunn")):
        out.append(tube(f"{name}_{nm}hook", [(bx1 + 0.02, sgn * 0.026, boom_z + 0.015), (bx1 + 0.02, sgn * 0.042, boom_z + 0.035),
                                               (bx1 + 0.02, sgn * 0.042, boom_z + 0.07), (bx1 + 0.02, sgn * 0.033, boom_z + 0.082)],
                        0.0025, M["Stainless"], smooth_path=True))
    return out


def boom_end(name, end, M):
    """The boom's aft cap: an angled casting over the boom's end, the outhaul sheave in its slot (Boom_Clew reads the
    sheave's centre), a shackle on top, two screws a side."""
    e = Vector(end)
    out = []
    prof = [(e.x + 0.03, e.z - 0.040), (e.x - 0.012, e.z - 0.040), (e.x - 0.045, e.z - 0.005), (e.x - 0.045, e.z + 0.022),
            (e.x - 0.030, e.z + 0.036), (e.x + 0.03, e.z + 0.036)]
    out.append(plate(f"{name}_cap", prof, -0.0305, 0.0305, M["CastAlu"], bev=0.006))
    out.append(cyl(f"{name}_outhaul", (e.x - 0.01, -0.006, e.z + 0.012), (e.x - 0.01, 0.006, e.z + 0.012), 0.012, M["SheaveGrey"], 24))
    out.append(cyl(f"{name}_axle", (e.x - 0.01, -0.033, e.z + 0.012), (e.x - 0.01, 0.033, e.z + 0.012), 0.003, M["Stainless"], 10))
    for sgn in (1, -1):
        out.append(lathe(f"{name}_axlehead{sgn}", [(0.0, 0.0), (0.0055, 0.0), (0.005, 0.002), (0.0, 0.0025)], Vector((e.x - 0.01, sgn * 0.0305, e.z + 0.012)), (0, sgn, 0), M["Stainless"], 12))
        for dx, dz in ((0.018, -0.02), (0.018, 0.018)):
            out.append(lathe(f"{name}_scr{sgn}{dz}", [(0.0, 0.0), (0.0042, 0.0), (0.004, 0.0014), (0.0024, 0.0024), (0.0, 0.0026)],
                             Vector((e.x + dx, sgn * 0.0305, e.z + dz)), (0, sgn, 0), M["Stainless"], 16))
    # a D-shackle on the top lug (the topping lift's wire)
    sx, sz = e.x - 0.035, e.z + 0.036
    out.append(plate(f"{name}_lug", [(sx - 0.012, sz - 0.002), (sx + 0.012, sz - 0.002), (sx + 0.006, sz + 0.012), (sx - 0.006, sz + 0.012)], -0.003, 0.003, M["CastAlu"], bev=0.001))
    pts = [(sx + 0.011 * math.cos(math.pi * k / 12), 0.0, sz + 0.008 + 0.011 * math.sin(math.pi * k / 12) * 1.3) for k in range(13)]
    out.append(tube(f"{name}_shackle", pts, 0.0025, M["Stainless"], smooth_path=True))
    out.append(cyl(f"{name}_shacklepin", (sx - 0.011, -0.006, sz + 0.008), (sx - 0.011, 0.006, sz + 0.008), 0.0025, M["Stainless"], 10))
    return out


def outhaul_cleat(name, at, M):
    """The outhaul's grey fairlead cleat under the boom (photo outhaul-sheet-cleet): a low saddle, a jaw at the aft end."""
    a = Vector(at)
    out = []
    prof = [(a.x + 0.05, a.z), (a.x - 0.05, a.z), (a.x - 0.055, a.z - 0.006), (a.x - 0.045, a.z - 0.022), (a.x - 0.02, a.z - 0.026),
            (a.x + 0.03, a.z - 0.016), (a.x + 0.05, a.z - 0.008)]
    out.append(plate(f"{name}_body", prof, -0.017, 0.017, M["SheaveGrey"], bev=0.004))
    out.append(cyl(f"{name}_throat", (a.x - 0.058, 0, a.z - 0.013), (a.x - 0.03, 0, a.z - 0.013), 0.0055, M["BlackPlastic"], 12))
    for dx in (0.03, -0.03):
        out.append(lathe(f"{name}_scr{dx}", [(0.0, 0.0), (0.0035, 0.0), (0.003, 0.0012), (0.0, 0.0016)], Vector((a.x + dx, 0.0, a.z - 0.016)), (0, 0, -1), M["Stainless"], 12))
    return out


def big_block(name, p, along, M, sheave_r=0.040):
    """The vang's upper block (photo boom-vang-closeup): long cheeks with lightening holes (dark rings set in), several
    sheaves inside, a swivel and a stainless strap up to the boom's bail."""
    p = Vector(p)
    d = Vector(along).normalized()
    side = Vector((0, 1, 0))
    u = d.cross(side).normalized()
    out = []
    L, H = 0.12, 0.044
    outline = []
    for k in range(13):
        a = math.pi / 2 + math.pi * k / 12
        outline.append(p + d * (L / 2 - H / 2) + (d * math.cos(a) * -1 + u * math.sin(a)) * H / 2 * 1.0)
    for k in range(13):
        a = -math.pi / 2 + math.pi * k / 12
        outline.append(p - d * (L / 2 - H / 2) + (d * math.cos(a) * -1 + u * math.sin(a)) * H / 2)
    for sgn in (1, -1):
        bm = bmesh.new()
        a = [bm.verts.new(q + side * sgn * 0.010) for q in outline]
        b = [bm.verts.new(q + side * sgn * 0.0135) for q in outline]
        n = len(outline)
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
        bm.faces.new(a[::-1])
        bm.faces.new(b)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        out.append(mesh_obj(f"{name}_cheek{sgn}", bm, M["BlackPlastic"], smooth_shade=False))
        for i in range(6):
            for j in (-1, 1):
                c = p + d * (-0.045 + 0.018 * i) + u * (j * 0.0105) + side * sgn * 0.0137
                out.append(lathe(f"{name}_hole{sgn}{i}{j}", [(0.0035, 0.0), (0.0052, 0.0), (0.0052, 0.0006), (0.0035, 0.0006)], c, side * sgn, M["Stainless"], 14))
    for i in range(3):
        c = p + d * (-0.035 + 0.035 * i)
        out.append(cyl(f"{name}_sheave{i}", c - side * 0.008, c + side * 0.008, 0.017, M["SheaveGrey"], 20))
    # the swivel and the strap up to the bail
    top = p + d * (L / 2 + 0.008)
    out.append(lathe(f"{name}_swivel", [(0.0, 0.0), (0.008, 0.0), (0.0075, 0.016), (0.0, 0.018)], top, d, M["Stainless"], 16))
    return out
