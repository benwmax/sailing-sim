"""Visual V3: the crew, built in Blender headless from code like the boats.

    blender -b --factory-startup -P Tools/blender/build_crew.py -- <out dir>

A proportioned sailor (1.78 m), stylised but with real proportions: foul-weather jacket, inflatable PFD harness with its
collar, sailing trousers, deck boots, cap and sunglasses, bare hands and face. A skeleton of 19 bones (pelvis, spine,
chest, neck, head, shoulders, arms, hands, legs, feet) skins it; the game poses it every frame from the physics crew
model (BoatModelVisuals: hiking over the rail, sitting to leeward, crossing on a tack, on the tiller extension, at the
winch, standing on the board to right a dinghy). The MetaHuman route needs the Creator's optional content and Epic's
cloud auto-rigging, neither available headless on this Mac (docs/visual-3/README.md).

Writes <out>/SK_Sailor.fbx. The character faces +X with Z up, feet at Z = 0 (Unreal's frame: the FBX import converts).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp"
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

SLOTS = ["Jacket", "PFD", "Trousers", "Boots", "Skin", "Cap", "Glasses", "Hair"]

# ---------------------------------------------------------------- skeleton (head, tail, parent), metres, +X forward, +Y left
BONES = {
    "pelvis": ((0, 0, 0.93), (0, 0, 1.03), None),
    "spine": ((0, 0, 1.03), (0, 0, 1.24), "pelvis"),
    "chest": ((0, 0, 1.24), (0, 0, 1.45), "spine"),
    "neck": ((0, 0, 1.45), (0, 0, 1.55), "chest"),
    "head": ((0, 0, 1.55), (0, 0, 1.78), "neck"),
}
for side, s in (("l", 1), ("r", -1)):
    BONES.update({
        f"shoulder_{side}": ((0, s * 0.04, 1.42), (0, s * 0.18, 1.42), "chest"),
        f"upperarm_{side}": ((0, s * 0.18, 1.42), (0, s * 0.47, 1.42), f"shoulder_{side}"),
        f"forearm_{side}": ((0, s * 0.47, 1.42), (0, s * 0.73, 1.42), f"upperarm_{side}"),
        f"hand_{side}": ((0, s * 0.73, 1.42), (0, s * 0.91, 1.42), f"forearm_{side}"),
        f"thigh_{side}": ((0, s * 0.095, 0.93), (0, s * 0.095, 0.51), "pelvis"),
        f"calf_{side}": ((0, s * 0.095, 0.51), (0, s * 0.095, 0.09), f"thigh_{side}"),
        f"foot_{side}": ((0, s * 0.095, 0.09), (0.17, s * 0.095, 0.02), f"calf_{side}"),
    })

bm = bmesh.new()
deform = bm.verts.layers.deform.verify()
bone_index = {name: i for i, name in enumerate(BONES)}


def add_ring_loft(rings, slot, weights_fn, cap=True):
    """rings: list of lists of points; weights_fn(point) -> {bone: weight}."""
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    for ring in vs:
        for v in ring:
            for b, w in weights_fn(v.co).items():
                v[deform][bone_index[b]] = w
    n = len(rings[0])
    for i in range(len(vs) - 1):
        for j in range(n):
            f = bm.faces.new((vs[i][j], vs[i][(j + 1) % n], vs[i + 1][(j + 1) % n], vs[i + 1][j]))
            f.material_index = SLOTS.index(slot)
            f.smooth = True
    if cap:
        for ring, rev in ((vs[0], True), (vs[-1], False)):
            f = bm.faces.new(list(reversed(ring)) if rev else ring)
            f.material_index = SLOTS.index(slot)
            f.smooth = True


def ellipse_ring(cx, cy, cz, ax, ay, n=16, axis="z", phase=0.0):
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n + phase
        if axis == "z":
            pts.append(Vector((cx + ax * math.cos(a), cy + ay * math.sin(a), cz)))
        elif axis == "y":
            pts.append(Vector((cx + ax * math.cos(a), cy, cz + ay * math.sin(a))))
        else:
            pts.append(Vector((cx, cy + ax * math.cos(a), cz + ay * math.sin(a))))
    return pts


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def torso_weights(p):
    z = p.z
    w_p = 1 - smooth((z - 0.98) / 0.10)
    w_c = smooth((z - 1.20) / 0.12)
    w_s = max(0.0, 1 - w_p - w_c)
    return {b: w for b, w in (("pelvis", w_p), ("spine", w_s), ("chest", w_c)) if w > 0.001}


def rigid(bone):
    return lambda p: {bone: 1.0}


# Torso: hips to shoulders, the jacket over the trousers' waist.
torso = [(0.86, 0.17, 0.115), (0.93, 0.175, 0.12), (1.02, 0.155, 0.11), (1.12, 0.16, 0.115), (1.24, 0.185, 0.125),
         (1.34, 0.195, 0.125), (1.42, 0.19, 0.11), (1.47, 0.12, 0.085)]
low = [ellipse_ring(0, 0, z, ax, ay) for z, ay, ax in torso if z <= 1.0]
high = [ellipse_ring(0, 0, z, ax, ay) for z, ay, ax in torso if z >= 0.93]
add_ring_loft(low, "Trousers", torso_weights)
add_ring_loft(high, "Jacket", torso_weights)
# PFD: an inflatable harness, a stiff collar band round the neck and down the chest, over the jacket.
pfd = [ellipse_ring(0.005, 0, z, ax + 0.012, ay + 0.012) for z, ay, ax in torso if 1.10 <= z <= 1.42]
add_ring_loft(pfd, "PFD", torso_weights)
add_ring_loft([ellipse_ring(0, 0, 1.44, 0.10, 0.13), ellipse_ring(0, 0, 1.52, 0.075, 0.09)], "PFD", lambda p: {"chest": 0.6, "neck": 0.4})
# Neck and head; cap with its brim; sunglasses.
add_ring_loft([ellipse_ring(0, 0, z, 0.052, 0.056) for z in (1.46, 1.56)], "Skin", lambda p: {"neck": 1.0})
head = []
for k in range(9):
    a = -math.pi / 2 + math.pi * k / 8
    z = 1.655 + 0.115 * math.sin(a)
    r = max(math.cos(a), 0.05)
    head.append(ellipse_ring(0.01, 0, z, 0.098 * r, 0.078 * r))
add_ring_loft(head, "Skin", rigid("head"))
cap = []
for k in range(6):
    a = math.pi * 0.08 + (math.pi / 2 - math.pi * 0.08) * k / 5
    z = 1.665 + 0.12 * math.sin(a)
    r = max(math.cos(a), 0.05)
    cap.append(ellipse_ring(0.01, 0, z, 0.104 * r, 0.084 * r))
add_ring_loft(cap, "Cap", rigid("head"))
brim = [ellipse_ring(0.10, 0, 1.70, 0.075, 0.072), ellipse_ring(0.13, 0, 1.693, 0.055, 0.065)]
add_ring_loft(brim, "Cap", rigid("head"))
# Sunglasses: a wraparound band across the eyes.
band = []
for z in (1.668, 1.638):
    band.append([Vector((0.012 + 0.104 * math.cos(a), 0.084 * math.sin(a), z)) for a in [math.radians(-70 + 140 * k / 8) for k in range(9)]])
gl = [[bm.verts.new(p) for p in row] for row in band]
for row in gl:
    for v in row:
        v[deform][bone_index["head"]] = 1.0
for k in range(8):
    f = bm.faces.new((gl[0][k], gl[1][k], gl[1][k + 1], gl[0][k + 1]))
    f.material_index = SLOTS.index("Glasses")
# Arms: sleeves to the wrist, bare hands (a mitten and a thumb).
for side, s in (("l", 1), ("r", -1)):
    add_ring_loft([ellipse_ring(0, s * y, 1.42, rz, rz, axis="x") for y, rz in ((0.15, 0.072), (0.30, 0.064), (0.47, 0.055))], "Jacket",
                  lambda p, side=side: {f"upperarm_{side}": 1.0} if abs(p.y) > 0.2 else {f"shoulder_{side}": 0.5, f"upperarm_{side}": 0.5})
    add_ring_loft([ellipse_ring(0, s * y, 1.42, rz, rz, axis="x") for y, rz in ((0.45, 0.056), (0.60, 0.05), (0.73, 0.043))], "Jacket", rigid(f"forearm_{side}"))
    add_ring_loft([ellipse_ring(0, s * y, 1.415, rz * 1.4, rz, axis="x") for y, rz in ((0.72, 0.03), (0.80, 0.034), (0.88, 0.026))], "Skin", rigid(f"hand_{side}"))
    add_ring_loft([ellipse_ring(0.03, s * y, 1.425, 0.012, 0.012, axis="x") for y in (0.74, 0.80)], "Skin", rigid(f"hand_{side}"))
    # Legs: trousers to the boot tops, boots.
    add_ring_loft([ellipse_ring(0, s * 0.095, z, r, r * 0.95) for z, r in ((0.95, 0.085), (0.75, 0.075), (0.53, 0.058))], "Trousers", rigid(f"thigh_{side}"))
    add_ring_loft([ellipse_ring(0, s * 0.095, z, r, r * 0.95) for z, r in ((0.54, 0.057), (0.32, 0.05), (0.16, 0.046))], "Trousers", rigid(f"calf_{side}"))
    add_ring_loft([ellipse_ring(0.01, s * 0.095, z, r, r * 0.9) for z, r in ((0.20, 0.050), (0.10, 0.052))], "Boots", rigid(f"calf_{side}"))
    boot = [ellipse_ring(x, s * 0.095, 0.05, 0.045 * max(0.35, 1 - abs(x - 0.06) / 0.16), 0.05, axis="x") for x in (-0.06, 0.0, 0.08, 0.17, 0.21)]
    add_ring_loft(boot, "Boots", rigid(f"foot_{side}"))

me = bpy.data.meshes.new("SK_Sailor")
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me)
bm.free()
mesh_obj = bpy.data.objects.new("SK_Sailor", me)
bpy.context.scene.collection.objects.link(mesh_obj)
for name in SLOTS:
    me.materials.append(bpy.data.materials.get(name) or bpy.data.materials.new(name))
for name in BONES:
    mesh_obj.vertex_groups.new(name=name)
# The bmesh deform layer indexes the vertex groups in BONES order.

arm_data = bpy.data.armatures.new("Sailor")
arm = bpy.data.objects.new("Sailor", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for name, (head_p, tail_p, parent) in BONES.items():
    b = arm_data.edit_bones.new(name)
    b.head, b.tail = head_p, tail_p
    if parent:
        b.parent = arm_data.edit_bones[parent]
        b.use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")
mesh_obj.parent = arm
mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
mod.object = arm
for p in me.polygons:
    p.use_smooth = True

bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
mesh_obj.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "SK_Sailor.fbx"), use_selection=True, axis_forward="X", axis_up="Z",
                         apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", add_leaf_bones=False, bake_anim=False,
                         mesh_smooth_type="FACE", armature_nodetype="NULL", primary_bone_axis="Y", secondary_bone_axis="X")
print(f"Crew: {len(me.vertices)} vertices, {sum(len(p.vertices) - 2 for p in me.polygons)} triangles, {len(BONES)} bones")
