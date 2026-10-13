"""Visual V7: what a boat in its slip wears, for the marina's neighbours (AMarinaActor): the standing rigging (the
sailing boat draws its own, live), the jib furled on its forestay with its sun strip, the main flaked on the boom under
a sail cover, halyards along the mast, fenders over the side and dock lines to the finger and the dock. Built from the
class model's own sockets (<Tag>_sockets.json from build_j22.py / build_fleet.py) so it fits the hull and mast exactly.

    blender -b --factory-startup -P Tools/blender/build_berthed.py -- <Tag> <boat.json> <models dir>

Writes <models>/SM_<Tag>_Berthed.fbx in the boat frame (origin at the hull's), slots Stainless, SailCover (covers and
sun strip), Deck (fenders), Rope, BlackPlastic. Prints "Berthed: <Tag> <tris>".
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

TAG, CFG_PATH, MODELS = sys.argv[sys.argv.index("--") + 1:]
CFG = json.load(open(CFG_PATH))
META = json.load(open(os.path.join(MODELS, f"{TAG}_sockets.json")))
S = {k: Vector(v) / 100.0 for k, v in META["sockets"].items()}       # boat frame, metres (Unreal axes)
SLOTS = ["Stainless", "SailCover", "Deck", "Rope", "BlackPlastic"]

bm = bmesh.new()


def P(v):
    return (v[0], -v[1], v[2])                                        # Unreal's starboard +Y -> Blender's -Y


def tube(path, radius, slot, sides=6, radius_end=None):
    pts = [Vector(p) for p in path]
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(a).normalized()
        w = t.cross(u).normalized()
        r = radius if radius_end is None else radius + (radius_end - radius) * i / max(len(pts) - 1, 1)
        rings.append([bm.verts.new(P(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * r)) for k in range(sides)])
    m = SLOTS.index(slot)
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            f = bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
            f.material_index = m
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        f = bm.faces.new(list(reversed(ring)) if rev else ring)
        f.material_index = m


def sag(a, b, droop, n=10):
    a, b = Vector(a), Vector(b)
    return [a + (b - a) * (k / n) - Vector((0, 0, droop * 4 * (k / n) * (1 - k / n))) for k in range(n + 1)]


wire = 0.004 if CFG["rig"]["masthead_z"] < 10 else 0.006
# Standing rigging (straight, under tension).
if "Hounds" in S and "ForestayTack" in S:
    tube([S["ForestayTack"], S["Hounds"]], wire, "Stainless")
    for tag in ("S", "P"):
        up, tip = S.get(f"ChainplateUpper_{tag}"), S.get(f"SpreaderTip_{tag}")
        if up is None:
            continue
        if tip is not None:
            tube([up, tip, S["Hounds"]], wire, "Stainless")
            tube([S[f"ChainplateLower_{tag}"], S["LowerTang"]], wire, "Stainless")
        else:
            tube([up, S["Hounds"]], wire, "Stainless")
    if "BackstayPlate" in S:
        tube([S["BackstayPlate"], S["MastheadAft"]], wire * 0.9, "Stainless")
    # The jib rolled on its forestay: a tapering spiral roll with the sun strip outermost.
    a, b = S["ForestayTack"], S["Hounds"]
    roll = [a + (b - a) * t for t in [0.06 + 0.86 * k / 16 for k in range(17)]]
    tube(roll, 0.075 if CFG["loa"] > 8 else 0.055, "SailCover", 10, 0.02)
# Halyards along the mast, slapping distance off it, cleated at the base.
if "MastStep" in S:
    top = S["MastStep"].z + (CFG["rig"]["masthead_z"] - S["MastStep"].z) * 0.98
    for dy in (0.03, -0.03):
        base = S["MastStep"] + Vector((0.08, dy, 0.6))
        tube(sag(base, Vector((S["MastStep"].x - 0.05, dy, top)), -0.12 if dy > 0 else -0.06, 8), 0.004, "Rope", 4)
# Main flaked on the boom under a cover, from the gooseneck to near the clew.
gx, gz = CFG["rig"]["main_luff_x"], CFG["rig"]["boom_z"]
clew = S.get("Boom_Clew", Vector((gx - CFG["rig"]["main_foot_chord"], 0, gz)))
L = gx - clew.x
cover = [Vector((gx - 0.05 - L * 0.88 * k / 10, 0, gz + 0.1 - 0.05 * k / 10)) for k in range(11)]
tube(cover, 0.15 if CFG["loa"] > 8 else 0.11, "SailCover", 10, 0.07 if CFG["loa"] > 8 else 0.05)
# Fenders over both sides (the side against a finger and the side toward the neighbour), on their lines.
H = CFG["hulls"][0]


def half_beam(x):
    if x > H["max_beam_x"]:
        u = (x - H["max_beam_x"]) / (H["bow_x"] - H["max_beam_x"] + 0.02)
        return H["max_half_beam"] * math.sqrt(max(0.0, 1 - u * u))
    u = (H["max_beam_x"] - x) / H["aft_length"]
    return max(H["max_half_beam"] - H["transom_beam_loss"] * u * u, 0.02)


sheer = H["sheer_z"]
fr = 0.09 if CFG["loa"] > 8 else 0.07
for side in (1, -1):
    for x in (H["max_beam_x"] + 0.9, H["max_beam_x"] - 0.6):
        y = side * (half_beam(x) + fr + 0.01)
        tube([Vector((x, y, sheer - 0.75)), Vector((x, y, sheer - 0.25))], fr, "Deck", 10)
        tube([Vector((x, side * (half_beam(x) - 0.05), sheer + 0.02)), Vector((x, y, sheer - 0.25))], 0.004, "Rope", 4)
# Dock lines: bow lines forward and out to the dock's cleats, stern lines aft to the finger ends, all with a little sag.
bow, stern = H["bow_x"], H["stern_x"]
for side in (1, -1):
    tube(sag((bow - 0.25, side * 0.2, sheer + 0.06), (bow + 0.7, side * 1.25, 0.5), 0.12), 0.006, "Rope", 5)
    tube(sag((stern + 0.3, side * (half_beam(stern + 0.3) - 0.08), sheer + 0.05), (stern - 0.35, side * 1.75, 0.5), 0.1), 0.006, "Rope", 5)
    tube(sag((bow - 0.6, side * (half_beam(bow - 0.6) - 0.05), sheer + 0.08), (stern + 1.2, side * 1.75, 0.5), 0.15, 12), 0.006, "Rope", 5)  # spring

mesh = bpy.data.meshes.new(f"SM_{TAG}_Berthed")
bm.to_mesh(mesh)
tris = sum(len(f.verts) - 2 for f in bm.faces)
bm.free()
for s in SLOTS:
    mesh.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
obj = bpy.data.objects.new(mesh.name, mesh)
bpy.context.scene.collection.objects.link(obj)
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.fbx(filepath=os.path.join(MODELS, mesh.name + ".fbx"), use_selection=True, axis_forward="X", axis_up="Z",
                         apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE", add_leaf_bones=False, bake_space_transform=True)
print(f"Berthed: {TAG} {tris}")
