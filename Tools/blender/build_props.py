"""Visual V6: the world kit's small props, built in Blender from code (run headless by scripts/make-world-models.sh).

Riprap rocks: three blocky limestone pieces (a subdivided cube pushed out by noise, with flattened bedding planes, the
way quarried chalk breaks), about 1 m across so the marina's breakwater scales them per instance. Box-projected UVs in
metres (the M_WorldSurface concrete pattern). Prints "Props: <name> <tris>".
Usage: blender -b --factory-startup -P build_props.py -- <out dir>
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector, noise

OUT = sys.argv[sys.argv.index("--") + 1]


def rock(index):
    rng = random.Random(9001 + index * 7919)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=5, use_grid_fill=True)
    scale = Vector((rng.uniform(0.9, 1.25), rng.uniform(0.75, 1.0), rng.uniform(0.5, 0.75)))
    seed = Vector((rng.uniform(0, 100), rng.uniform(0, 100), rng.uniform(0, 100)))
    for v in bm.verts:
        d = v.co.normalized()
        # Round the cube toward a pebble, then break it up.
        p = v.co.lerp(d * 0.62, 0.45)
        n = noise.noise(p * 2.2 + seed) * 0.16 + noise.noise(p * 6.0 + seed) * 0.05
        p = p + d * n
        # Bedding planes: quantize the height a little so the faces read as split layers.
        p.z = p.z * 0.75 + round(p.z * 4.0) / 4.0 * 0.25
        v.co = Vector((p.x * scale.x, p.y * scale.y, p.z * scale.z))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for loop in f.loops:
            c = loop.vert.co
            loop[uv].uv = (c.y, c.z) if ax == 0 else ((c.x, c.z) if ax == 1 else (c.x, c.y))
    name = f"SM_Rock_{index}"
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = False
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new("Rock")
    mesh.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                             mesh_smooth_type="FACE")
    bpy.data.objects.remove(obj)
    print(f"Props: {name} {tris}")


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
for i in range(3):
    rock(i)
