"""Part detail loop, bow fittings (docs/part-detail-loop/bow.md): the Sunfish's bow handle in place.

Builds the Sunfish with Tools/blender/build_fleet.py in this same Blender (as render_sunfish.py does), gives every slot
the kit's preview material (bk_materials, the game's MI_Boat_* values) and renders the bow from off the starboard bow,
square-on from starboard and from above. The same views for any checkout, so a "before" from main and an "after" from
the branch line up.

    python3 Tools/boatkit/partloop/render_sunfish_bow.py <boat.json from Tools/BoatExport> <out dir> [--samples N]
"""
import math
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
CFG, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
SAMPLES = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
os.makedirs(OUT, exist_ok=True)

sys.argv = [os.path.join(ROOT, "Tools", "blender", "build_fleet.py"), "--", CFG, "Sunfish", os.path.join(OUT, "model")]
runpy.run_path(sys.argv[0], run_name="__main__")

import bk_materials as BM  # noqa: E402

hull = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("SM_Sunfish_Hull"))
for o in list(bpy.data.objects):
    if o.type in ("LIGHT", "CAMERA") or (o.type == "MESH" and not o.name.startswith("SM_Sunfish_Hull")):
        bpy.data.objects.remove(o, do_unlink=True)
for i, slot in enumerate(hull.material_slots):
    if slot.material:
        try:
            slot.material = BM.get(slot.material.name.split(".")[0])
        except Exception:
            pass
pts = [hull.matrix_world @ v.co for v in hull.data.vertices]
bow = max(p.x for p in pts)
deck = max(p.z for p in pts if p.x > bow - 0.3 and abs(p.y) < 0.03)
print("Sunfish bow x", round(bow, 3), "deck z", round(deck, 3))

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 900
sc.view_settings.view_transform = "AgX"
w = bpy.data.worlds.new("sky")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.70, 0.78, 0.88, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.world = w
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy, sun.data.angle = 3.0, math.radians(8)
sun.rotation_euler = (math.radians(40), 0, math.radians(-40))
sc.collection.objects.link(sun)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.01
hx = bow - 0.21            # the handle (build_fleet: bow_x - 0.22 + 0.01)
VIEWS = {
    "photo": ((hx + 0.55, -0.55, deck + 0.42), (hx, 0.0, deck + 0.01), 50),
    "side": ((hx, -0.70, deck + 0.06), (hx, 0.0, deck + 0.02), 50),
    "above": ((hx + 0.18, -0.20, deck + 0.55), (hx, 0.0, deck), 50),
}
for name, (loc, at, lens) in VIEWS.items():
    cam.location = loc
    cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
print("Sunfish bow:", OUT)
