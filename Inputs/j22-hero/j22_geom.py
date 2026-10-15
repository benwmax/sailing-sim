"""Geometry helpers shared by the J/22 hero scripts (meshes from bmesh, tubes from curves, joins, bevels)."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

SC = bpy.context.scene



def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_obj(name, bm, mat=None, smooth_shade=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob)
    if mat:
        ob.data.materials.append(mat)
    if smooth_shade:
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def apply_mods(ob):
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def bevel(ob, width, segs=3, angle=35, weighted=True):
    b = ob.modifiers.new("bevel", "BEVEL")
    b.width, b.segments, b.limit_method = width, segs, "ANGLE"
    b.angle_limit = math.radians(angle)
    b.harden_normals = False
    if weighted:
        ob.modifiers.new("wn", "WEIGHTED_NORMAL").keep_sharp = True
    return ob


def boolean(ob, cutter, op="DIFFERENCE"):
    m = ob.modifiers.new("bool", "BOOLEAN")
    m.operation, m.object, m.solver = op, cutter, "EXACT"
    apply_mods(ob)
    bpy.data.objects.remove(cutter, do_unlink=True)


def box(name, x0, x1, y0, y1, z0, z1, mat=None, bev=0.0, segs=3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.y * (y1 - y0), (z0 + z1) / 2 + v.co.z * (z1 - z0)))
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    if bev:
        bevel(ob, bev, segs)
    return ob


def cyl(name, p0, p1, r, mat=None, segs=24, r1=None, cap=True):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, segments=segs, radius1=r, radius2=r if r1 is None else r1, depth=d.length)
    ob = mesh_obj(name, bm, mat)
    ob.matrix_world = Matrix.Translation((p0 + p1) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return ob


def tube(name, pts, r, mat=None, res=10, smooth_path=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution = r, max(2, res // 4)
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS" if smooth_path else "POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1.0)
    if smooth_path:
        sp.order_u, sp.use_endpoint_u = min(4, len(pts)), True
    ob = link(bpy.data.objects.new(name, cu))
    if mat:
        cu.materials.append(mat)
    return ob


def to_mesh(ob):
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active


def join(name, obs):
    obs = [o for o in obs if o]
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in obs:
        if o.type != "MESH":
            to_mesh(o)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


def mirror_y(ob):
    m = ob.modifiers.new("mir", "MIRROR")
    m.use_axis = (False, True, False)
    m.use_bisect_axis = (False, False, False)
    m.mirror_object = None
    return ob


def side_pair(fn, *a, **k):
    """Build a part on the port side and its starboard copy."""
    p = fn(1, *a, **k)
    s = fn(-1, *a, **k)
    return [p, s]


