"""The Catalina 22's rig views (docs/c22-5): the shape loop's clay look (Tools/shapeloop/render_set.py), framed on the
mast and its rigging instead of the hull.

    blender -b -P render_rig_c22.py -- <c22.blend> <out dir> [--res 1200]

Draws every mesh the build leaves visible. Views:
  rig_profile, rig_bow     orthographic, the whole boat and rig from port and from ahead
  rig_34                   the whole rig from the port bow, a little above the deck
  masthead                 the masthead's cap, tangs and crane, from forward and to port
  spreaders                the spreaders and the wires over their tips
  mastfoot                 the mast's foot, its step, the gooseneck and the boom's forward end
  chainplates              the port side deck's chainplates and turnbuckles
  stemhead                 the forestay's foot on the bow
  boomend                  the boom's after end and the backstay's foot on the transom
Frame: Blender's (X forward, Y to port, Z up), as the build writes it. Cycles on the CPU, few samples: shape, not looks.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1200
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
for o in sc.objects:
    if o.type not in ("MESH", "CURVE"):
        o.hide_render = True

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.cycles.samples = 32
sc.cycles.max_bounces = 3
sc.render.resolution_x, sc.render.resolution_y = RES, RES // 2
sc.render.use_compositing = sc.render.use_sequencer = False
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("RigWorld")
sc.world = world
world.use_nodes = True
WN = world.node_tree
for n in list(WN.nodes):
    if n.type != "OUTPUT_WORLD":
        WN.nodes.remove(n)
out = [n for n in WN.nodes if n.type == "OUTPUT_WORLD"][0]
bg, tc, sep, ramp, mr = (WN.nodes.new(t) for t in ("ShaderNodeBackground", "ShaderNodeTexCoord", "ShaderNodeSeparateXYZ",
                                                    "ShaderNodeValToRGB", "ShaderNodeMapRange"))
ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.35, (0.25, 0.25, 0.26, 1)
ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.75, (1.0, 1.0, 1.02, 1)
mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
WN.links.new(tc.outputs["Generated"], sep.inputs[0])
WN.links.new(sep.outputs["Z"], mr.inputs["Value"])
WN.links.new(mr.outputs[0], ramp.inputs[0])
WN.links.new(ramp.outputs[0], bg.inputs[0])
WN.links.new(bg.outputs[0], out.inputs[0])
clay = bpy.data.materials.new("RigClay")
clay.use_nodes = True
nt = clay.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
d = nt.nodes.new("ShaderNodeBsdfDiffuse")
d.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
nt.links.new(d.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
bpy.context.view_layer.material_override = clay

cd = bpy.data.cameras.new("RigCam")
cam = bpy.data.objects.new("RigCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam


def shot(name, loc, target, ortho=None, lens=35):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    cd.clip_start, cd.clip_end = 0.01, 200
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


def at(name, default):
    ob = bpy.data.objects.get(name)
    if ob is None:
        return Vector(default)
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return Vector([(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2 for i in range(3)])


MX, TOP = 0.86, 8.87          # the mast's x and its cap's height (rig_c22)
shot("rig_profile", (0.3, 30, 3.75), (0.3, 0, 3.75), ortho=20.5)
shot("rig_bow", (30, 0, 3.75), (0, 0, 3.75), ortho=20.5)
shot("rig_34", (6.2, 4.6, 1.3), (0.5, 0, 4.4), lens=20)
shot("masthead", (MX + 0.9, 0.7, TOP + 0.25), (MX, 0, TOP - 0.1), lens=50)
shot("spreaders", (MX + 2.6, 0.0, 5.12), (MX, 0, 5.0), lens=35)   # from ahead, so both tips read alike
shot("mastfoot", (MX + 0.2, 1.5, 1.9), (MX - 0.3, 0, 1.35), lens=30)
shot("chainplates", (0.85, 2.2, 1.9), (0.85, 1.0, 0.9), lens=28)
shot("stemhead", (3.9, 0.7, 1.4), (3.25, 0, 1.0), lens=40)
shot("boomend", (-2.0, 2.2, 2.2), (-2.8, 0.1, 1.2), lens=28)
print("rig views written to", OUT)
