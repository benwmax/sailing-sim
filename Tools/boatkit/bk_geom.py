"""Geometry helpers for the boat kit: every part is built from a few clean primitives, then bevelled and given weighted
normals so its edges catch light the way cast and machined hardware does.

Conventions: metres, Z up, X forward along the part. A part's origin is its mount point on the surface it sits on, with
the mount normal along +Z, so a layout can place it with one matrix. Sockets are empties named "SOCKET_<name>" parented
to the part (exported as UCX-free FBX empties; scripts read them back by name).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

TAU = 2 * math.pi


def scene():
    return bpy.context.scene


def link(ob):
    scene().collection.objects.link(ob)
    return ob


def mesh_obj(name, bm, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    if mat is not None:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return link(ob)


def finish(ob, bevel=0.0, segs=3, angle=30.0, weighted=True, sharp=35.0):
    """Bevel hard edges (angle-limited), harden and weight the normals, mark the rest smooth, then apply.

    A bevel of 0 keeps the shape and only fixes the shading (sharp edges above `sharp` degrees)."""
    me = ob.data
    me.set_sharp_from_angle(angle=math.radians(sharp))
    if bevel > 0:
        b = ob.modifiers.new("bevel", "BEVEL")
        b.width, b.segments, b.limit_method = bevel, segs, "ANGLE"
        b.angle_limit = math.radians(angle)
        b.profile = 0.5
        b.harden_normals = True
        b.use_clamp_overlap = True
    if weighted:
        w = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
        w.keep_sharp = True
        w.weight = 50
    apply(ob)
    return ob


def apply(ob):
    if not ob.modifiers:
        return ob
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


# ------------------------------------------------------------------ primitives

def lathe(name, profile, mat=None, segs=32, arc=TAU, axis_mat=None):
    """Revolve a (radius, z) profile around Z. Radius 0 points close the ends."""
    bm = bmesh.new()
    n = segs if arc >= TAU - 1e-6 else segs + 1
    rings = []
    for (r, z) in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
            continue
        rings.append([bm.verts.new((r * math.cos(arc * i / segs), r * math.sin(arc * i / segs), z)) for i in range(n)])
    closed = n == segs
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(len(b) - (0 if closed else 1)):
                bm.faces.new((a[0], b[i], b[(i + 1) % len(b)]))
        elif len(b) == 1:
            for i in range(len(a) - (0 if closed else 1)):
                bm.faces.new((a[(i + 1) % len(a)], a[i], b[0]))
        else:
            for i in range(len(a) - (0 if closed else 1)):
                j = (i + 1) % len(a)
                bm.faces.new((a[i], a[j], b[j], b[i]))
    if closed:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 2:
                bm.faces.new(ring)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if axis_mat is not None:
        bmesh.ops.transform(bm, matrix=axis_mat, verts=bm.verts)
    return mesh_obj(name, bm, mat)


def rrect(w, d, r, segs=6):
    """Rounded rectangle outline (w along X, d along Y), counter-clockwise."""
    r = min(r, w / 2 - 1e-5, d / 2 - 1e-5)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90), (-w / 2 + r, -d / 2 + r, 180), (w / 2 - r, -d / 2 + r, 270)):
        for k in range(segs + 1):
            a = math.radians(a0 + 90 * k / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def ellipse(rx, ry, segs=16):
    return [(rx * math.cos(TAU * i / segs), ry * math.sin(TAU * i / segs)) for i in range(segs)]


def prism(name, outline, z0, z1, mat=None, taper=1.0):
    """Extrude a 2D outline (list of (x, y)) from z0 to z1; the top is scaled by `taper` about the centroid."""
    bm = bmesh.new()
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    lo = [bm.verts.new((x, y, z0)) for x, y in outline]
    hi = [bm.verts.new((cx + (x - cx) * taper, cy + (y - cy) * taper, z1)) for x, y in outline]
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bm.faces.new(list(reversed(lo)))
    bm.faces.new(hi)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)


def box(name, c, s, mat=None):
    x, y, z = c
    w, d, h = s
    return prism(name, [(x - w / 2, y - d / 2), (x + w / 2, y - d / 2), (x + w / 2, y + d / 2), (x - w / 2, y + d / 2)],
                 z - h / 2, z + h / 2, mat)


def cyl(name, p0, p1, r, mat=None, segs=24, r1=None):
    """Capped cylinder (or cone with r1) from p0 to p1."""
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    ob = lathe(name, [(0, 0), (r, 0), (r if r1 is None else r1, L), (0, L)], mat, segs)
    ob.matrix_world = along(p0, p1 - p0)
    bake_xform(ob)
    return ob


def along(origin, direction, up=(0, 0, 1)):
    """Matrix taking local Z to `direction` at `origin`."""
    z = Vector(direction).normalized()
    upv = Vector(up)
    if abs(z.dot(upv)) > 0.99:
        upv = Vector((1, 0, 0))
    x = upv.cross(z).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def frame(origin, x_axis, z_hint=(0, 0, 1)):
    """Matrix whose X is x_axis and Z is as close to z_hint as possible."""
    x = Vector(x_axis).normalized()
    z = Vector(z_hint)
    y = z.cross(x)
    if y.length < 1e-6:
        y = Vector((0, 1, 0))
    y.normalize()
    z = x.cross(y).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def bake_xform(ob):
    # matrix_basis, not matrix_world: the world matrix only refreshes on a depsgraph update, so it is stale right after
    # setting .location or .matrix_world on a fresh object.
    ob.data.transform(ob.matrix_basis)
    ob.matrix_basis = Matrix.Identity(4)
    return ob


def sweep(name, path, section, mat=None, radii=None, closed=False, cap=True, twist_up=(0, 0, 1)):
    """Sweep a 2D section (list of (u, v), u across, v up) along a polyline path, scaled per point by radii.

    The section's v axis follows `twist_up` projected off the path tangent (rotation-minimising enough for fittings)."""
    path = [Vector(p) for p in path]
    radii = radii or [1.0] * len(path)
    bm = bmesh.new()
    rings = []
    tans = []
    for i in range(len(path)):
        if closed:
            t = path[(i + 1) % len(path)] - path[i - 1]
        else:
            t = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
        tans.append(t.normalized())
    # first frame from twist_up, then parallel transport (rotation-minimising) so tubes never twist or flip
    up = Vector(twist_up)
    u = up.cross(tans[0])
    if u.length < 1e-6:
        u = Vector((1, 0, 0)).cross(tans[0])
        if u.length < 1e-6:
            u = Vector((0, 1, 0)).cross(tans[0])
    u.normalize()
    for i, p in enumerate(path):
        t = tans[i]
        if i > 0:
            q = tans[i - 1].rotation_difference(t)
            u = (q @ u)
            u = (u - t * u.dot(t)).normalized()
        v = t.cross(u)
        s_ = radii[i]
        rings.append([bm.verts.new(p + u * (a * s_) + v * (b * s_)) for a, b in section])
    n = len(section)
    pairs = list(zip(rings, rings[1:] + ([rings[0]] if closed else [])))
    for a, b in pairs:
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    if cap and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)


def tube(name, path, r, mat=None, segs=12, closed=False, radii=None):
    return sweep(name, path, ellipse(r, r, segs), mat, radii=radii, closed=closed)


def arc_pts(c, r, a0, a1, n, plane="xz"):
    out = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        ca, sa = math.cos(a), math.sin(a)
        if plane == "xz":
            out.append((c[0] + r * ca, c[1], c[2] + r * sa))
        elif plane == "yz":
            out.append((c[0], c[1] + r * ca, c[2] + r * sa))
        else:
            out.append((c[0] + r * ca, c[1] + r * sa, c[2]))
    return out


def bezier(p0, p1, p2, p3, n=16):
    p0, p1, p2, p3 = map(Vector, (p0, p1, p2, p3))
    out = []
    for i in range(n + 1):
        t = i / n
        a = 1 - t
        out.append(p0 * a ** 3 + p1 * 3 * a * a * t + p2 * 3 * a * t * t + p3 * t ** 3)
    return out


def boolean(ob, cutter, op="DIFFERENCE"):
    m = ob.modifiers.new("bool", "BOOLEAN")
    m.operation, m.object, m.solver = op, cutter, "EXACT"
    apply(ob)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return ob


def join(name, obs):
    """Join objects into one mesh (materials kept per face)."""
    obs = [o for o in obs if o is not None]
    bm = bmesh.new()
    mats = []
    for o in obs:
        me = o.data.copy()
        me.transform(o.matrix_basis)
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        for p in me.polygons:
            p.material_index = remap[p.material_index] if remap else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    target = bpy.data.meshes.new(name)
    bm.to_mesh(target)
    bm.free()
    # custom normals do not survive bmesh; recompute from the joined sources instead
    for m in mats:
        target.materials.append(m)
    ob = bpy.data.objects.new(name, target)
    link(ob)
    # Custom normals do not survive the bmesh join, so weight them again on the joined mesh: the parts are separate
    # islands, so each keeps its own flat faces and rolled bevels.
    finish(ob, 0.0, sharp=35.0)
    for o in obs:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return ob


def _transfer_normals(ob, sources):
    """Copy the sources' finished (weighted) normals onto the joined mesh, loop by loop, in join order."""
    loops = []
    for o in sources:
        me = o.data
        rot = o.matrix_basis.to_3x3()
        try:
            ns = [ (rot @ Vector(cn.vector)).normalized() for cn in me.corner_normals]
        except AttributeError:
            ns = [(rot @ l.normal).normalized() for l in me.loops]
        loops.extend(ns)
    me = ob.data
    if len(loops) == len(me.loops):
        me.normals_split_custom_set([tuple(n) for n in loops])
    for p in me.polygons:
        p.use_smooth = True


def socket(parent, name, loc, rot=(0, 0, 0)):
    e = bpy.data.objects.new(f"SOCKET_{name}", None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = 0.02
    e.location = loc
    e.rotation_euler = rot
    link(e)
    e.parent = parent
    return e


def screw_heads(name, pts, mat, r=0.0028, h=0.0015):
    out = []
    for i, p in enumerate(pts):
        o = lathe(f"{name}_s{i}", [(0, 0), (r, 0), (r * 0.92, h * 0.6), (r * 0.6, h), (0, h)], mat, 12)
        o.location = p
        bake_xform(o)
        out.append(finish(o, 0, weighted=False))
    return out


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
