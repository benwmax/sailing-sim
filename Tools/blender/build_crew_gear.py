"""Visual V7: what the MetaHuman crew wear over the default shirt and shorts, in unit size; the game scales each piece to
the character's own skeleton (shoulder span, torso height, head size) and hangs it on the chest and head bones.

  SM_CrewPFD  a foam life jacket: a vest open at the neck and arms, X forward, Y right, Z up, from the waist (z 0) to the
              shoulders (z 1); width 1 at the chest (y -0.5..0.5), depth 0.62; the zip and two buckle straps (slot PFD)
  SM_CrewCap  a peaked cap on a head of radius 1, the crown's centre at the origin, the peak forward (slot Cap)

    blender -b --factory-startup -P Tools/blender/build_crew_gear.py -- <out dir>
Prints "Gear: <name> <tris>".
"""
import math
import os
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index("--") + 1]


def export(name, bm, slots):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            c = loop.vert.co
            loop[uv].uv = (math.atan2(c.y, c.x), c.z)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.to_mesh(me)
    bm.free()
    for s in slots:
        me.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                             mesh_smooth_type="FACE")
    bpy.data.objects.remove(obj)
    print(f"Gear: {name} {tris}")


def ring(bm, z, half_w, half_d, n=28, power=2.6, gap=None):
    """A superellipse ring at height z (Blender's Y is Unreal's -Y; the vest is symmetric, so it doesn't matter)."""
    vs = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        x = half_d * math.copysign(abs(c) ** (2 / power), c)
        y = half_w * math.copysign(abs(s) ** (2 / power), s)
        vs.append(bm.verts.new((x, y, z)))
    return vs


def loft(bm, rings, slot_index, closed=True):
    for a, b in zip(rings, rings[1:]):
        n = len(a)
        for k in range(n if closed else n - 1):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            f.material_index = slot_index


def pfd():
    bm = bmesh.new()
    # Outer and inner shells (foam 2.5 cm thick in a 0.38 m-wide jacket), waist to shoulders: snug at the waist,
    # fullest at the chest, narrowing over the shoulders to leave the arms free.
    prof = [(0.0, 0.47, 0.30), (0.25, 0.49, 0.31), (0.55, 0.5, 0.31), (0.8, 0.46, 0.27), (0.92, 0.36, 0.2), (1.0, 0.22, 0.13)]
    outer = [ring(bm, z, w, d) for z, w, d in prof]
    inner = [ring(bm, z, w - 0.065, d - 0.065) for z, w, d in prof]
    loft(bm, outer, 0)
    loft(bm, list(reversed(inner)), 0)
    for a, b in ((outer[0], inner[0]), (inner[-1], outer[-1])):
        n = len(a)
        for k in range(n):
            f = bm.faces.new((a[k], b[k], b[(k + 1) % n], a[(k + 1) % n]))
            f.material_index = 0
    # Two buckle straps around the front and a zip line (a slightly proud band, slot Straps).
    for z in (0.18, 0.42):
        lo = ring(bm, z - 0.03, 0.495, 0.305)
        hi = ring(bm, z + 0.03, 0.495, 0.305)
        loft(bm, [lo, hi], 1)
    zip_ = [bm.verts.new(v) for v in ((0.312, -0.012, 0.05), (0.312, 0.012, 0.05), (0.312, 0.012, 0.88), (0.312, -0.012, 0.88))]
    f = bm.faces.new(zip_)
    f.material_index = 1
    export("SM_CrewPFD", bm, ["PFD", "Straps"])


def cap():
    bm = bmesh.new()
    n, m = 24, 7
    # Crown: a dome over the top of the head, sitting a little proud of it.
    rings = []
    for j in range(m):
        t = j / (m - 1)
        el = math.radians(-8 + 90 * t)
        r = 1.06 * math.cos(el)
        z = 1.06 * math.sin(el) - 0.05
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z)) for k in range(n)])
    loft(bm, rings, 0)
    top = bm.faces.new(rings[-1])
    top.material_index = 0
    # Peak: a curved bill forward.
    bill = []
    for j in range(3):
        r = 1.06 + 0.32 * j / 2
        bill.append([bm.verts.new((r * math.cos(a), r * math.sin(a), -0.19 - 0.06 * (j / 2) ** 2)) for a in [math.radians(-62 + 124 * k / 12) for k in range(13)]])
    for a, b in zip(bill, bill[1:]):
        for k in range(12):
            f = bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
            f.material_index = 0
    export("SM_CrewCap", bm, ["Cap"])


bpy.ops.wm.read_factory_settings(use_empty=True)
pfd()
cap()
