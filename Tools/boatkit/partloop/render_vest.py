"""Part detail loop, crew life vest: the same views of the vest on the stand-in sailor every round (vest_standin.py).

    python3 Tools/boatkit/partloop/render_vest.py <stand-in.fbx> <vest.fbx> <polo-open.fbx> <out dir> [--samples N]

Views: front, three-quarter front (the angle of Bean's lesson photo), side, back, a close-up of the buckles and strap
tails, and the front in clay (every slot grey, so only shape shows). Writes stats.json (triangles, slots, sizes in mm:
vest length shoulder to hem, width, depth, front foam). The colours are the club's royal blue foam vest from the lesson
photos (the game recolours the shell per sailor); the stand-in's skin is a plain grey.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_render as R  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
if "--samples" in args:
    i = args.index("--samples")
    os.environ["BK_SAMPLES"] = args[i + 1]
    R.SAMPLES = int(args[i + 1])
    del args[i:i + 2]
STANDIN, VEST, POLO, OUT = args[:4]
os.makedirs(OUT, exist_ok=True)

COL = {"PFD": ((0.010, 0.060, 0.62), 0.55, 0.25), "Straps": ((0.30, 0.31, 0.32), 0.75, 0.0), "Buckle": ((0.015, 0.015, 0.016), 0.4, 0.0),
       "Piping": ((0.03, 0.30, 0.85), 0.5, 0.25), "Polo": ((0.020, 0.075, 0.10), 0.85, 0.3), "Skin": ((0.45, 0.45, 0.46), 0.6, 0.0)}


def setup_materials(objs, clay=False):
    made = {}
    for ob in objs:
        for slot in ob.material_slots:
            key = slot.material.name.split(".")[0] if slot.material else "Skin"
            if (key, clay) not in made:
                m = bpy.data.materials.new(f"{key}_{'clay' if clay else 'col'}")
                m.use_nodes = True
                p = m.node_tree.nodes["Principled BSDF"]
                c, rough, sheen = COL.get(key, COL["Skin"])
                p.inputs["Base Color"].default_value = (*((0.5, 0.5, 0.5) if clay else c), 1)
                p.inputs["Roughness"].default_value = 0.6 if clay else rough
                if not clay and "Sheen Weight" in p.inputs:
                    p.inputs["Sheen Weight"].default_value = sheen
                made[(key, clay)] = m
            slot.material = made[(key, clay)]


bpy.ops.wm.read_factory_settings(use_empty=True)
objs = {}
for name, path in (("standin", STANDIN), ("vest", VEST), ("polo", POLO)):
    bpy.ops.import_scene.fbx(filepath=path)
    ob = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
    ob.name = name
    objs[name] = ob
# The stand-in's own shirt is replaced by the cut-away polo (as the game imports it): hide its Polo faces.
sd = objs["standin"]
import bmesh  # noqa: E402
bm = bmesh.new()
bm.from_mesh(sd.data)
polo_idx = [i for i, m in enumerate(sd.data.materials) if m and m.name.split(".")[0] == "Polo"]
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in polo_idx], context="FACES")
bm.to_mesh(sd.data)
bm.free()
for ob in objs.values():
    for p in ob.data.polygons:
        p.use_smooth = True

# Stats (world space).
vest = objs["vest"]
mw = vest.matrix_world
pts = [mw @ v.co for v in vest.data.vertices]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
slots = [s.material.name.split(".")[0] for s in vest.material_slots if s.material]
tris = sum(len(p.vertices) - 2 for p in vest.data.polygons)
# Front foam: the vest's front surface ahead of the stand-in's shirt at the chest (ray along +Y from the front).
from mathutils.bvhtree import BVHTree  # noqa: E402
deps = bpy.context.evaluated_depsgraph_get()
st = objs["standin"]
bm_s = bmesh.new()
bpy.ops.import_scene.fbx(filepath=STANDIN)
full = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
bm_s.from_mesh(full.data)
bm_s.transform(full.matrix_world)
tree_s = BVHTree.FromBMesh(bm_s)
bm_v = bmesh.new()
bm_v.from_mesh(vest.data)
bm_v.transform(mw)
tree_v = BVHTree.FromBMesh(bm_v)
foam = []
for z in (lo.z + 0.12, lo.z + 0.2, lo.z + 0.3):
    for x in (-0.09, -0.06, 0.06, 0.09):
        a = tree_v.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 3.0)[0]
        b = tree_s.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 3.0)[0]
        if a is not None and b is not None:
            foam.append((b - a).length)
bpy.data.objects.remove(full)
foam.sort()
stats = {"tris": tris, "slots": slots, "length_mm": round((hi.z - lo.z) * 1000), "width_mm": round((hi.x - lo.x) * 1000),
         "depth_mm": round((hi.y - lo.y) * 1000), "front_foam_mm": round(foam[len(foam) // 2] * 1000, 1) if foam else None}
with open(os.path.join(OUT, "stats.json"), "w") as f:
    json.dump(stats, f, indent=1)
print("stats", stats)

R._engine(720, 900)
bpy.context.scene.view_settings.exposure = float(os.environ.get("VEST_EXPOSURE", "-2.2"))
R._floor(0.0, 8)
R._light("Key", "AREA", (-1.6, -2.4, 2.6), (0, 0, 1.2), 420, 2.0)
R._light("Fill", "AREA", (2.2, -1.6, 1.6), (0, 0, 1.2), 160, 2.5)
R._light("Rim", "AREA", (0.8, 2.6, 2.4), (0, 0, 1.3), 260, 1.5)
C = Vector((0, 0, 1.18))
VIEWS = {"front": ((0, -2.4, 1.25), C, 60), "threequarter": ((1.35, -1.95, 1.4), C, 60), "side": ((2.4, 0, 1.25), C, 60),
         "back": ((0, 2.4, 1.25), C, 60), "buckles": ((0.35, -0.95, 1.2), Vector((0.0, -0.1, 1.12)), 70)}
cam = None


def shot(name, loc, target, lens):
    global cam
    if cam:
        bpy.data.objects.remove(cam)
    cam = R._camera(loc, target, lens)
    bpy.context.scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


setup_materials(objs.values())
for name, (loc, tgt, lens) in VIEWS.items():
    shot(name, loc, tgt, lens)
setup_materials(objs.values(), clay=True)
shot("clay", *VIEWS["threequarter"])
print("rendered", OUT)
