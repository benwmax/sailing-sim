"""The moth's close-ups (docs/moth-9): grey clay renders of named views a metre or so from the boat.

    CLOSE="$(cat Tools/shipkit/moth/close_views.json)" blender -b -P Tools/shipkit/moth/render_close.py -- \
        <work>/moth.blend Tools/shapeloop/sections_moth.json <out dir> [--res 600]

CLOSE maps a view's name to [camera, target, lens mm] (Blender frame: x forward, y to port, z up, metres); HIDE takes
object names to leave out. Writes <out dir>/close_<name>.png, square. The lighting and clay are the shape loop's
(Tools/shapeloop/render_set.py). Cycles on the CPU; needs Blender's Python (pip bpy).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shapeloop"))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, SECTIONS, OUT = ARGS[0], ARGS[1], ARGS[2]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1600
OTHER = "--with-other" in ARGS
os.makedirs(OUT, exist_ok=True)
SC = C.load_scene(SRC)
SEC = C.load_sections(SECTIONS)
HULL = bpy.data.objects[SEC.get("hull_object", "Hull")]

for o in list(SC.objects):
    if o.type in ("MESH", "CURVE", "FONT"):
        hide = C.section_of(o.name, SEC) == "other" and not OTHER
        o.hide_render = hide
        o.hide_viewport = hide
    else:                    # cameras, lights, and empties that might instance geometry
        o.hide_render = True

# frame on everything drawn (hull, keel, rudder, cabin...), not the hull alone, so nothing runs off the edge
pts = [o.matrix_world @ Vector(c) for o in SC.objects if o.type in ("MESH", "CURVE", "FONT") and not o.hide_render
       for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
mid = (lo + hi) / 2
size = hi - lo
hpts = [HULL.matrix_world @ Vector(c) for c in HULL.bound_box]
hlo = Vector([min(p[i] for p in hpts) for i in range(3)])
hhi = Vector([max(p[i] for p in hpts) for i in range(3)])

sc = SC
# Cycles on the CPU: the cloud and CI have no GPU or EGL for Workbench. Few samples: shape, not looks.
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.render.resolution_x = RES
sc.render.resolution_y = RES // 2
sc.render.film_transparent = False
sc.render.use_compositing = False   # the hero blend carries no compositor we want
sc.render.use_sequencer = False
sc.display_settings.display_device = "sRGB"
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
world = bpy.data.worlds.new("ShapeWorld")
sc.world = world
world.use_nodes = True
WN = world.node_tree
for n in list(WN.nodes):
    if n.type != "OUTPUT_WORLD":
        WN.nodes.remove(n)


def world_kind(kind):
    for n in list(WN.nodes):
        if n.type != "OUTPUT_WORLD":      # (bpy wrappers are not stable: compare types, never identity)
            WN.nodes.remove(n)
    out = [n for n in WN.nodes if n.type == "OUTPUT_WORLD"][0]
    bg = WN.nodes.new("ShaderNodeBackground")
    WN.links.new(bg.outputs[0], out.inputs[0])
    if kind == "sil":
        bg.inputs[0].default_value = (1, 1, 1, 1)
        bg.inputs[1].default_value = 1.0
    elif kind == "shade":
        # bright sky over a darker ground: soft clay light that shows form
        tc = WN.nodes.new("ShaderNodeTexCoord")
        sep = WN.nodes.new("ShaderNodeSeparateXYZ")
        ramp = WN.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.25, 0.25, 0.26, 1)
        ramp.color_ramp.elements[1].position = 0.75
        ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.02, 1)
        mr = WN.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
        WN.links.new(tc.outputs["Generated"], sep.inputs[0])
        WN.links.new(sep.outputs["Z"], mr.inputs["Value"])
        WN.links.new(mr.outputs[0], ramp.inputs[0])
        WN.links.new(ramp.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 1.0
    else:   # zebra: horizontal stripes all round the sky, reflected in a mirror-glossy boat
        tc = WN.nodes.new("ShaderNodeTexCoord")
        sep = WN.nodes.new("ShaderNodeSeparateXYZ")
        mul = WN.nodes.new("ShaderNodeMath")
        mul.operation, mul.inputs[1].default_value = "MULTIPLY", 22.0
        sn = WN.nodes.new("ShaderNodeMath")
        sn.operation = "SINE"
        gt = WN.nodes.new("ShaderNodeMath")
        gt.operation, gt.inputs[1].default_value = "GREATER_THAN", 0.0
        WN.links.new(tc.outputs["Generated"], sep.inputs[0])
        WN.links.new(sep.outputs["Z"], mul.inputs[0])
        WN.links.new(mul.outputs[0], sn.inputs[0])
        WN.links.new(sn.outputs[0], gt.inputs[0])
        WN.links.new(gt.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 1.0


def override(kind):
    m = bpy.data.materials.get("Shape_" + kind) or bpy.data.materials.new("Shape_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if kind == "sil":
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs[0].default_value = (0, 0, 0, 1)
        nt.links.new(e.outputs[0], out.inputs[0])
    elif kind == "shade":
        d = nt.nodes.new("ShaderNodeBsdfDiffuse")
        d.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
        nt.links.new(d.outputs[0], out.inputs[0])
    else:
        g = nt.nodes.new("ShaderNodeBsdfGlossy")
        g.inputs[0].default_value = (1, 1, 1, 1)
        g.inputs[1].default_value = 0.0
        nt.links.new(g.outputs[0], out.inputs[0])
    return m


cam_data = bpy.data.cameras.new("ShapeCam")
cam = bpy.data.objects.new("ShapeCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(loc, target, ortho=None, lens=35):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = "PERSP"
        cam_data.lens = lens
    cam_data.clip_start, cam_data.clip_end = 0.01, 200


def mode(kind):
    world_kind(kind)
    bpy.context.view_layer.material_override = override(kind)
    sc.cycles.samples = 1 if kind == "sil" else 24
    sc.cycles.max_bounces = 0 if kind == "sil" else (2 if kind == "zebra" else 3)


def shot(name, kind):
    mode(kind)
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)




CLOSE = json.loads(os.environ["CLOSE"])
HIDE = os.environ.get("HIDE", "").split(",")
for o in SC.objects:
    if o.name in HIDE:
        o.hide_render = True
for v, (loc, tgt, lens) in CLOSE.items():
    look(loc, tgt, lens=lens)
    cam_data.clip_start = 0.005
    sc.render.resolution_x = RES
    sc.render.resolution_y = RES
    shot(f"close_{v}", "shade")
