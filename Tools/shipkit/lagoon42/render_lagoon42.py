"""The Lagoon 42 rebuild's own views (docs/lagoon42-2 on): her parts in their colours, from where a person sees a cat.

    blender -b -P render_lagoon42.py -- <lagoon42.blend> <out dir> [--res 1200] [--only a,b]

The shape loop's fixed views (Tools/shapeloop/render_set.py) frame a monohull: their close perspective cameras sit on
the centreline, which on a cat is the open water between her hulls. These add the views her slices are judged by,
each in the slot colours build_lagoon42.py gives (white topsides, dark antifouling under the boot top, dark windows)
over a pale blue-grey sea plane at the game's waterline, so the boot top and her trim read as on the water:
  bow_quarter     from off her starboard bow, 8 m up: the one CC BY photo's kind of view (refs.json)
  stern_quarter   from off her port quarter, 4 m up: the sugar scoops, their steps and the raked skirts
  profile         her starboard side, orthographic, at the waterline
  head_on         from ahead, low: the two plumb stems and the knuckle
  bow_close       one bow from outboard and ahead: the stem, the forefoot and the knuckle's run forward
  under           from below and aft of her starboard quarter, without the sea: the canoe bodies
  foredeck        from above and ahead of her starboard bow: the trampolines, crossbeam, centre beam and bowsprit
  bridge_under    from ahead, just over the water between the bows: the bridge deck's nose and underside
  drone           from the CC BY drone photo's solved camera (match_two_canoes.camera.json, 4:3): to lay over the photo
Cycles on the CPU, as render_set.py. Frame: Blender's (X forward, Y to port, Z up).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1200
ONLY = set(ARGS[ARGS.index("--only") + 1].split(",")) if "--only" in ARGS else None
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene

LOOKS = {"Topsides": ((0.86, 0.86, 0.84), 0.35), "Antifouling": ((0.05, 0.055, 0.07), 0.6),
         "CabinWindow": ((0.02, 0.025, 0.03), 0.08), "Teak": ((0.45, 0.30, 0.17), 0.7),
         "Trampoline": ((0.05, 0.05, 0.055), 0.8), "Spar": ((0.6, 0.61, 0.63), 0.3)}
for m in bpy.data.materials:
    if m.name not in LOOKS:
        continue
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    col, rough = LOOKS[m.name]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    nt.links.new(b.outputs[0], out.inputs[0])

sea_me = bpy.data.meshes.new("Sea")
sea_me.from_pydata([(-200, -200, 0), (200, -200, 0), (200, 200, 0), (-200, 200, 0)], [], [(0, 1, 2, 3)])
sea = bpy.data.objects.new("Sea", sea_me)
sc.collection.objects.link(sea)
sm = bpy.data.materials.new("SeaLook")
sm.use_nodes = True
p = sm.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.20, 0.30, 0.36, 1)
p.inputs["Roughness"].default_value = 0.25
p.inputs["Alpha"].default_value = 0.82
sea_me.materials.append(sm)

world = bpy.data.worlds.new("L42World")
sc.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    if n.type != "OUTPUT_WORLD":
        wn.nodes.remove(n)
tc = wn.nodes.new("ShaderNodeTexCoord")      # a pale sky over a darker horizon (pip bpy has no sky texture node)
sep = wn.nodes.new("ShaderNodeSeparateXYZ")
ramp = wn.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.45
ramp.color_ramp.elements[0].color = (0.30, 0.34, 0.38, 1)
ramp.color_ramp.elements[1].position = 0.8
ramp.color_ramp.elements[1].color = (0.62, 0.74, 0.92, 1)
mr = wn.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
bg = wn.nodes.new("ShaderNodeBackground")
bg.inputs[1].default_value = 0.8
wn.links.new(tc.outputs["Generated"], sep.inputs[0])
wn.links.new(sep.outputs["Z"], mr.inputs["Value"])
wn.links.new(mr.outputs[0], ramp.inputs[0])
wn.links.new(ramp.outputs[0], bg.inputs[0])
wn.links.new(bg.outputs[0], [n for n in wn.nodes if n.type == "OUTPUT_WORLD"][0].inputs[0])
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 3.0
sun_d.angle = math.radians(3)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = Vector((0.5, -0.4, 0.75)).to_track_quat("Z", "Y").to_euler()
sc.collection.objects.link(sun)

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.render.resolution_x = RES
sc.render.resolution_y = int(RES * 0.6)
sc.render.use_compositing = False
sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in
                                                    sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
cam_d = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam_d.clip_start, cam_d.clip_end = 0.05, 500


def look(loc, target, lens=35, ortho=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam_d.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam_d.ortho_scale = ortho
    else:
        cam_d.lens = lens


VIEWS = {   # name: camera, target, lens (or ortho width), sea shown
    "bow_quarter": ((17.0, -13.0, 8.0), (0.5, 0.0, 0.6), 40, True),
    "stern_quarter": ((-16.0, 9.0, 4.0), (-4.0, 0.0, 0.5), 38, True),
    "profile": ((0.0, -40.0, 0.7), (0.0, 0.0, 0.7), ("ortho", 14.2), True),
    "head_on": ((24.0, 0.0, 1.2), (0.0, 0.0, 0.5), 50, True),
    "bow_close": ((9.5, -6.2, 1.6), (4.6, -2.9, 0.2), 35, True),
    "under": ((-12.0, -9.0, -5.0), (0.0, 0.0, -0.2), 35, False),
    "foredeck": ((11.0, -4.5, 6.5), (3.5, 0.0, 1.0), 32, True),
    "bridge_under": ((9.0, -1.2, 0.35), (-2.0, 0.0, 0.9), 30, True),
}
VIEWS["drone"] = (None, None, None, True)
for name, (loc, tgt, lens, show_sea) in VIEWS.items():
    if ONLY and name not in ONLY:
        continue
    sea.hide_render = not show_sea
    sc.render.resolution_y = int(RES * 0.6)
    if name == "drone":
        c = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "match_two_canoes.camera.json")))
        cam.location = c["location"]
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = c["rotation_quaternion"]
        cam_d.type, cam_d.lens, cam_d.sensor_fit, cam_d.sensor_width = "PERSP", c["lens_mm"], "HORIZONTAL", 36.0
        sc.render.resolution_y = int(RES * c["resolution"][1] / c["resolution"][0])
    elif isinstance(lens, tuple):
        cam.rotation_mode = "XYZ"
        look(loc, tgt, ortho=lens[1])
    else:
        cam.rotation_mode = "XYZ"
        look(loc, tgt, lens=lens)
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
print("render_lagoon42:", sorted(f for f in os.listdir(OUT) if f.endswith(".png")))
