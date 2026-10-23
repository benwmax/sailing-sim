"""Graphics G2: shore plants, built from code (run by scripts/make-world-models.sh), placed by ALakeTerrainActor in the
shallows and at the water's edge.

  SM_Reeds_0  a cattail clump (Typha): 64 strap leaves 1.1 to 2.1 m, eight stems with brown heads and spikes
  SM_Reeds_1  a rush and sedge clump: 110 thin arching blades 0.5 to 1.2 m
  SM_Reeds_2  bank grass and weeds at the waterline: 140 arching blades 0.25 to 0.8 m, seed stalks (realism audit 10)
  SM_Reeds_3  a weed mat floating in the shallows: 260 small oval leaves, 1.6 m across (realism audit 10)
Origin at the clump's foot, metres, Z up. Blades are double-faced strips (no two-sided material). Slots: Reed, ReedHead.
Prints "Reeds: <name> <tris>".
    blender -b --factory-startup -P Tools/blender/build_reeds.py -- <out dir>
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]


def blade(bm, slot_index, base, height, width, lean, yaw, curl, segs=6):
    """A strap leaf: a ribbon rising from base, leaning and curling over toward its tip, tapering to a point."""
    dirx, diry = math.cos(yaw), math.sin(yaw)
    side = Vector((-diry, dirx, 0.0))
    pts = []
    for i in range(segs + 1):
        t = i / segs
        bend = lean * t * t + curl * t ** 3
        c = Vector((base.x + dirx * bend * height, base.y + diry * bend * height, base.z + height * t * (1.0 - 0.25 * curl * t * t)))
        w = width * (1.0 - t) ** 0.7 * 0.5
        pts.append((c - side * w, c + side * w))
    for face_side in (0, 1):
        off = Vector((dirx, diry, 0.0)) * (0.0008 if face_side else -0.0008)
        vs = [(bm.verts.new(a + off), bm.verts.new(b + off)) for a, b in pts]
        for (a0, b0), (a1, b1) in zip(vs, vs[1:]):
            q = (a0, b0, b1, a1) if face_side else (a0, a1, b1, b0)
            f = bm.faces.new(q)
            f.material_index = slot_index


def stem(bm, base, height, rng):
    """A cattail stem with its brown head and the thin spike above it."""
    def tube(z0, z1, r0, r1, slot, sides=6):
        rings = []
        for z, r in ((z0, r0), (z1, r1)):
            rings.append([bm.verts.new((base.x + r * math.cos(2 * math.pi * k / sides), base.y + r * math.sin(2 * math.pi * k / sides), z)) for k in range(sides)])
        for k in range(sides):
            f = bm.faces.new((rings[0][k], rings[0][(k + 1) % sides], rings[1][(k + 1) % sides], rings[1][k]))
            f.material_index = slot
        top = bm.faces.new(rings[1])
        top.material_index = slot
    head_len = rng.uniform(0.13, 0.2)
    tube(0.0, height - head_len, 0.006, 0.004, 0)
    tube(height - head_len, height, 0.022, 0.02, 1, 8)
    tube(height, height + rng.uniform(0.1, 0.2), 0.004, 0.001, 1, 4)


def export(name, bm):
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    me = bpy.data.meshes.new(name)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x + loop.vert.co.y, loop.vert.co.z)
    bm.to_mesh(me)
    bm.free()
    for s in ("Reed", "ReedHead"):
        me.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                             mesh_smooth_type="FACE")
    bpy.data.objects.remove(obj)
    print(f"Reeds: {name} {tris}")


def cattails():
    rng = random.Random(7)
    bm = bmesh.new()
    for _ in range(64):
        r, a = 0.45 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
        base = Vector((r * math.cos(a), r * math.sin(a), 0.0))
        blade(bm, 0, base, rng.uniform(1.1, 2.1), rng.uniform(0.018, 0.03), rng.uniform(0.05, 0.3), a + rng.uniform(-0.6, 0.6), rng.uniform(0.0, 0.4))
    for _ in range(8):
        r, a = 0.25 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
        stem(bm, Vector((r * math.cos(a), r * math.sin(a), 0.0)), rng.uniform(1.5, 2.1), rng)
    export("SM_Reeds_0", bm)


def rushes():
    rng = random.Random(11)
    bm = bmesh.new()
    for _ in range(110):
        r, a = 0.3 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
        base = Vector((r * math.cos(a), r * math.sin(a), 0.0))
        blade(bm, 0, base, rng.uniform(0.5, 1.2), rng.uniform(0.004, 0.009), rng.uniform(0.15, 0.5), a + rng.uniform(-0.4, 0.4), rng.uniform(0.2, 0.7), segs=5)
    export("SM_Reeds_1", bm)


def bank_grass():
    """Realism audit 10 (docs/realism-audit-1022): the rank grass and weeds at a reservoir's waterline, where the mowing
    stops: a loose tuft of 140 thin arching blades 0.25 to 0.8 m, a few taller seed stalks."""
    rng = random.Random(23)
    bm = bmesh.new()
    for _ in range(140):
        r, a = 0.42 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
        base = Vector((r * math.cos(a), r * math.sin(a), 0.0))
        blade(bm, 0, base, rng.uniform(0.25, 0.8), rng.uniform(0.004, 0.008), rng.uniform(0.2, 0.7), a + rng.uniform(-0.5, 0.5), rng.uniform(0.3, 0.9), segs=4)
    for _ in range(10):
        r, a = 0.3 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
        base = Vector((r * math.cos(a), r * math.sin(a), 0.0))
        blade(bm, 1, base, rng.uniform(0.7, 1.1), 0.006, rng.uniform(0.05, 0.25), a, 0.1, segs=4)
    export("SM_Reeds_2", bm)


def weed_mat():
    """Realism audit 10: the green weed lying in the shallows at the edge (water primrose, pondweed): a loose mat about
    1.6 m across of small oval leaves floating at the surface, a few rising a little at the middle."""
    rng = random.Random(31)
    bm = bmesh.new()
    for _ in range(260):
        r, a = 0.8 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
        cx, cy = r * math.cos(a), r * math.sin(a)
        L, W = rng.uniform(0.05, 0.11), rng.uniform(0.025, 0.05)
        yaw = rng.uniform(0, 2 * math.pi)
        z = 0.004 + 0.05 * max(0.0, 1.0 - r / 0.5) * rng.random()
        tilt = rng.uniform(-0.25, 0.25)
        dx, dy = math.cos(yaw), math.sin(yaw)
        pts = []
        for k in range(6):
            t = 2 * math.pi * k / 6
            u, v = 0.5 * L * math.cos(t), 0.5 * W * math.sin(t)
            pts.append(Vector((cx + u * dx - v * dy, cy + u * dy + v * dx, z + tilt * u)))
        for face_side in (0, 1):
            off = Vector((0.0, 0.0, 0.0006 if face_side else -0.0006))
            vs = [bm.verts.new(p + off) for p in pts]
            f = bm.faces.new(vs if face_side else vs[::-1])
            f.material_index = 0
    export("SM_Reeds_3", bm)


bpy.ops.wm.read_factory_settings(use_empty=True)
cattails()
rushes()
bank_grass()
weed_mat()
