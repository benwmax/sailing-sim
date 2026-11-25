"""The moth's wear renders (docs/moth-10): each wear view at every level, lit, as albedo and once as material ids.

    blender -b -P Tools/shipkit/moth/render_wear.py -- <work>/moth.blend <out dir> [--res 640] [--only bow,wing]
        [--levels L0,L4] [--samples 48] [--ids-only | --albedo-only]

The views are textures_moth.json's (views.shots: [camera, target, lens mm] in Blender's frame). Writes, per view,
wear_<view>_<level>.png (lit: a soft overcast sky with a low sun, as a club dock at four in the afternoon; in a
ladder's view only that ladder's material is aged, the rest new),
wear_<view>_<level>_albedo.png (each material's colour alone, unlit: what wear_check.py measures) and wear_<view>_id.png
(material ids, weathering_moth.material_id), and wear_ids.json (the ids). Cycles on the CPU; needs Blender's Python.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weathering_moth as WE  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 640
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else 48
VIEWS = WE.CARDS["views"]["shots"]
SHEET_OF = {view: sheet for sheet, (view, _) in WE.CARDS["views"]["ladder"].items()}
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else list(VIEWS)
LEVELS = ARGS[ARGS.index("--levels") + 1].split(",") if "--levels" in ARGS else list(WE.LEVELS)
if "--ids-only" in ARGS:
    LEVELS = []
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
SC = bpy.context.scene
for o in list(SC.objects):
    if o.type not in ("MESH",):
        o.hide_render = True

SC.render.engine = "CYCLES"
SC.cycles.device = "CPU"
SC.render.resolution_x = SC.render.resolution_y = RES
SC.render.film_transparent = False
SC.render.use_compositing = False
SC.render.use_sequencer = False
SC.display_settings.display_device = "sRGB"
SC.view_settings.view_transform = "Standard"
SC.view_settings.look = "None"
SC.view_settings.exposure = 0.0
SC.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("WearWorld")
SC.world = world
world.use_nodes = True
WN = world.node_tree
for n in list(WN.nodes):
    if n.type != "OUTPUT_WORLD":
        WN.nodes.remove(n)
out = [n for n in WN.nodes if n.type == "OUTPUT_WORLD"][0]
bg = WN.nodes.new("ShaderNodeBackground")
tc = WN.nodes.new("ShaderNodeTexCoord")
sep = WN.nodes.new("ShaderNodeSeparateXYZ")
ramp = WN.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.45          # the ground: a grey-brown dock and water
ramp.color_ramp.elements[0].color = (0.22, 0.21, 0.19, 1)  # a pale concrete dock under her trolley (the mesh's gaps show)
ramp.color_ramp.elements[1].position = 0.62          # the sky: an overcast grey-blue
ramp.color_ramp.elements[1].color = (0.75, 0.80, 0.88, 1)
mr = WN.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
WN.links.new(tc.outputs["Generated"], sep.inputs[0])
WN.links.new(sep.outputs["Z"], mr.inputs["Value"])
WN.links.new(mr.outputs[0], ramp.inputs[0])
WN.links.new(ramp.outputs[0], bg.inputs[0])
WN.links.new(bg.outputs[0], out.inputs[0])
sun = bpy.data.objects.new("WearSun", bpy.data.lights.new("WearSun", "SUN"))
SC.collection.objects.link(sun)
sun.data.angle = math.radians(2.0)
sun.data.energy = 2.5
sun.rotation_euler = Vector((-0.45, 0.55, -0.7)).to_track_quat("-Z", "Y").to_euler()

cam_data = bpy.data.cameras.new("WearCam")
cam = bpy.data.objects.new("WearCam", cam_data)
SC.collection.objects.link(cam)
SC.camera = cam
cam_data.clip_start, cam_data.clip_end = 0.005, 200


def look(loc, target, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens


def mode(kind):
    WE.albedo_mode(None if kind == "lit" else kind)
    lit = kind == "lit"
    bg.inputs[1].default_value = 1.0 if lit else 0.0
    sun.hide_render = not lit
    SC.cycles.samples = SAMPLES if lit else (8 if kind == "albedo" else 1)
    SC.cycles.use_denoising = lit
    SC.cycles.max_bounces = 6 if lit else 0
    SC.cycles.transparent_max_bounces = 16
    SC.cycles.filter_width = 1.5 if lit else 0.01


def shot(path, kind):
    mode(kind)
    SC.render.filepath = path
    bpy.ops.render.render(write_still=True)


json.dump({"ids": WE.material_ids(), "surfaces": {n: "/".join(sk) for n, sk in WE.material_index().items()}},
          open(os.path.join(OUT, "wear_ids.json"), "w"), indent=1)
for v in ONLY:
    loc, tgt, lens = VIEWS[v]
    look(loc, tgt, lens)
    shot(os.path.join(OUT, f"wear_{v}_id.png"), "id")
    for lv in LEVELS:
        if "--albedo-only" not in ARGS:
            WE.apply_level(lv, only=SHEET_OF.get(v))     # a ladder's view ages only its own material
            shot(os.path.join(OUT, f"wear_{v}_{lv}.png"), "lit")
        WE.apply_level(lv)                               # the albedo: every material, measured by its id
        shot(os.path.join(OUT, f"wear_{v}_{lv}_albedo.png"), "albedo")
