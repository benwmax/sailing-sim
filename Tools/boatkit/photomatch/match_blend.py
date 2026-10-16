"""Render a saved .blend (the hero J/22, or any boat build) from a photo's solved camera and write the compare image.
The photo match loop for models that are not dressed by dress_boat.py.

    blender -b -P Tools/boatkit/photomatch/match_blend.py -- <model.blend> <photo>.camera.json <photo.jpg> <out dir>
        [--hide Sails,Rigging]   collections left out of the render (the photo shows the boat without sails)

Writes <out>/match_<photo>.png (transparent background) and <out>/compare_<photo>.jpg (photo, render, blend, outline).
The compare image contains the photo, so it stays out of the public repo when the photo shows people.
"""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:]
BLEND, CAMERA, PHOTO, OUT = ARGS[:4]
HIDE = ARGS[ARGS.index("--hide") + 1].split(",") if "--hide" in ARGS else ["Sails"]
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
for name in HIDE:
    coll = bpy.data.collections.get(name)
    if coll:
        coll.hide_render = True

cam = json.load(open(CAMERA))
for c in [o for o in bpy.data.objects if o.type == "CAMERA"]:
    bpy.data.objects.remove(c, do_unlink=True)
cd = bpy.data.cameras.new("MatchCam")
co = bpy.data.objects.new("MatchCam", cd)
sc.collection.objects.link(co)
co.location = cam["location"]
co.rotation_mode = "QUATERNION"
co.rotation_quaternion = cam["rotation_quaternion"]
cd.lens = cam["lens_mm"]
cd.sensor_fit = "HORIZONTAL"
cd.sensor_width = cam["sensor_width_mm"]
cd.clip_start, cd.clip_end = 0.05, 500.0
sc.camera = co

# an overcast sky like the dock photo: soft even light, no sun disc
if sc.world is None:
    sc.world = bpy.data.worlds.new("MatchSky")
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.75, 0.78, 0.82, 1.0)
bg.inputs["Strength"].default_value = 1.0
for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
    o.hide_render = True
sun = bpy.data.objects.new("MatchSun", bpy.data.lights.new("MatchSun", "SUN"))
sun.data.energy = 1.5
sun.data.angle = math.radians(30)
sun.rotation_euler = (math.radians(35), 0, math.radians(40))
sc.collection.objects.link(sun)

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = int(os.environ.get("BK_SAMPLES", "16"))
sc.view_settings.view_transform = "AgX"
w, h = cam["resolution"]
s = min(1.0, 1600 / w)
sc.render.resolution_x, sc.render.resolution_y = int(w * s), int(h * s)
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
stem = os.path.splitext(os.path.basename(cam["photo"]))[0]
path = os.path.join(OUT, f"match_{stem}.png")
sc.render.filepath = path
bpy.ops.render.render(write_still=True)
print(f"Photomatch: match render {path}")
sys.path.insert(0, HERE)
import compare  # noqa: E402
compare.compose(PHOTO, path, os.path.join(OUT, f"compare_{stem}.jpg"))
