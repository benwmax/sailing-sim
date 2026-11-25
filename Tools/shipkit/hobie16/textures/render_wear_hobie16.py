"""The Hobie 16's wear views (docs/hobie16-8): a built hobie16.blend dressed by weathering_hobie16.py and rendered at
each of the texture loop's five levels, for the ladders, the blind rounds and wear_check_hobie16.py.

    blender -b -P render_wear_hobie16.py -- <hobie16.blend> <out dir> [--res 900] [--samples 32] [--only a,b]
        [--levels L0,L4] [--no-measure]

Writes, for each view and level, wear_<view>_<level>.png (lit), wear_<view>_<level>_albedo.png (each material's colour
alone, no light: what the checks measure) and wear_<view>_id.png (each dressed material in its own flat colour) with
wear_ids.json naming them. --no-measure skips the albedo and id passes. The sails are hidden (they age in
M_SailCloth, not here) so the views see the platform.

Views (Blender's frame: X forward, Y to port, Z up from the design waterline with her crew aboard):
  hull     the port hull's outboard side amidships from the water: topsides gelcoat, the line where she floats
  keel     low under the port bow: the keel line and forefoot, where the beach and the dolly scrape
  deck     over the port bow: the deck's gelcoat, a pylon and corner casting, the bow tang, the front crossbar
  tramp    from high astern: the trampoline, the hiking straps, the crossbars, the mainsheet's blocks
  corner   the port aft corner close: the rear crossbar's anodising, the corner casting, the pylon's gelcoat
  mast     the mast's foot from the port bow: the mast and its base casting, the front crossbar, the jib car, blocks
  rudder   the port rudder from astern: the blade, the castings, the tiller arm and crossbar, the extension
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weathering_hobie16 as WH  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 900
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else 32
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
LEVELS = ARGS[ARGS.index("--levels") + 1].split(",") if "--levels" in ARGS else list(WH.LEVELS)
MEASURE = "--no-measure" not in ARGS
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
for o in sc.objects:
    if o.type not in ("MESH", "CURVE") or o.name.startswith("H16Sail_"):
        o.hide_render = True
DRESSED = WH.dress("L0")
ids = {str(k): m.name for k, m in enumerate(WH.dressed(), 1)}
json.dump(ids, open(os.path.join(OUT, "wear_ids.json"), "w"), indent=1)
json.dump(WH.report(WH.used_materials()), open(os.path.join(OUT, "wear_report.json"), "w"), indent=1)

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.render.use_compositing = sc.render.use_sequencer = False
sc.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("WearWorld")
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.62, 0.66, 0.72, 1)        # an overcast-to-hazy Texas sky, as the Catalina's
bg.inputs[1].default_value = 1.0
sd = bpy.data.lights.new("WearSun", "SUN")
sd.energy, sd.angle = 3.5, math.radians(3)
sun = bpy.data.objects.new("WearSun", sd)
sc.collection.objects.link(sun)
sun.rotation_euler = Vector((0.45, 0.55, 0.7)).to_track_quat("Z", "Y").to_euler()
cd = bpy.data.cameras.new("WearCam")
cam = bpy.data.objects.new("WearCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam

VIEWS = {
    "hull": ((0.6, 3.6, 0.1), (0.4, 1.0, -0.03), 70),
    "keel": ((2.7, 2.3, -0.75), (1.3, 1.0, -0.22), 50),
    "deck": ((2.6, 1.9, 1.35), (1.0, 1.0, 0.32), 30),
    "tramp": ((-3.3, 0.0, 2.7), (-0.6, 0.0, 0.3), 30),
    "corner": ((-1.2, 1.5, 0.95), (-1.75, 0.98, 0.38), 35),
    "mast": ((1.5, 0.9, 1.05), (0.55, 0.0, 0.55), 35),
    "rudder": ((-3.9, 1.9, 0.1), (-2.6, 0.95, -0.25), 30),
}


def frame(loc, target, lens):
    sc.render.resolution_x, sc.render.resolution_y = RES, RES * 2 // 3
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.type, cd.lens = "PERSP", lens
    cd.clip_start, cd.clip_end = 0.01, 1000


def render(path, samples):
    sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


for view, (loc, target, lens) in VIEWS.items():
    if ONLY and view not in ONLY:
        continue
    frame(loc, target, lens)
    if MEASURE:
        WH.albedo_mode("id")
        sc.cycles.use_denoising = False
        sc.view_settings.view_transform = "Standard"
        render(os.path.join(OUT, f"wear_{view}_id.png"), 1)
    for lv in LEVELS:
        WH.apply_level(lv)
        if MEASURE:
            WH.albedo_mode("albedo")
            sc.cycles.use_denoising = False
            sc.view_settings.view_transform = "Standard"
            render(os.path.join(OUT, f"wear_{view}_{lv}_albedo.png"), 4)
        WH.albedo_mode(False)
        sc.cycles.use_denoising = True
        sc.view_settings.view_transform = "AgX"
        render(os.path.join(OUT, f"wear_{view}_{lv}.png"), SAMPLES)
print("wear views written to", OUT)
