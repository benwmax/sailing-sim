"""The Catalina 22's deck hardware and running rigging views (docs/c22-7): her slot colours under a grey sky, one state
of her lines and sails shown per view and the boom swung to that state's angle.

    blender -b -P render_hardware_c22.py -- <c22.blend> <out dir> [--res 1200] [--only a,b] [--clay]

Views (each names the state it shows):
  rest_34, rest_top, rest_quarter   at the mooring: the whole boat from the port bow, from above, from the port quarter
  cockpit, traveller, ladder        the cockpit from aft and up, the mainsheet's tackle, the stern ladder and rail (rest)
  mast_foot, bow                    the halyards' cleats, coils and the vang; the pulpit, bow cleat, vents and hatch
  up_34, genoa_lead, genoa_tack,    close-hauled under main and genoa: the boat, the genoa's car, sheet and winch over
  winch, outhaul                    the lifeline, its tack pennant over the pulpit, the port winch's turns and cleat
                                    hitch, the outhaul at the boom's end
  jib_34, jib_lead                  under main and working jib: the boat, the jib's car, fairlead, turning block and winch
  reef_pennant                      reefed: the reef's clew pennant on the boom
  run_34, run_aft                   on a run under main and spinnaker: the guy, sheet, pole lift and foreguy
Frame: Blender's (X forward, Y to port, Z up). Cycles on the CPU, few samples, a high sun from the port bow. --clay draws
everything in one clay, for the blind rounds (today's model and the new one alike).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hardware_c22 as HC                              # noqa: E402
import rig_c22 as RC                                   # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1200
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
CLAY = "--clay" in ARGS                                # one clay for everything: the blind rounds' look
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
for o in sc.objects:
    if o.type not in ("MESH", "CURVE"):
        o.hide_render = True
SAILS = [o for o in sc.objects if o.name.startswith("C22_Sail_")]
LINES = [o for o in sc.objects if o.name.startswith("C22_Lines_")]

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.cycles.samples = 32
sc.cycles.max_bounces = 3
sc.render.use_compositing = sc.render.use_sequencer = False
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("HwWorld")
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
METAL = ("Stainless", "Aluminium", "Wire", "Lifeline")
for m in bpy.data.materials:                           # each slot's colour (build_c22.SLOT_RGB), metals a little shiny
    m.use_nodes = True
    pb = m.node_tree.nodes.get("Principled BSDF")
    if pb:
        pb.inputs["Base Color"].default_value = m.diffuse_color
        pb.inputs["Roughness"].default_value = 0.35 if m.name.split(".")[0] in METAL else 0.7
        pb.inputs["Metallic"].default_value = 0.6 if m.name.split(".")[0] in METAL else 0.0

if CLAY:
    clay = bpy.data.materials.new("HwClay")
    clay.use_nodes = True
    nt = clay.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
    nt.links.new(dif.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    bpy.context.view_layer.material_override = clay

sun_d = bpy.data.lights.new("HwSun", "SUN")
sun_d.energy, sun_d.angle = 3.0, math.radians(3.0)
sun = bpy.data.objects.new("HwSun", sun_d)
sc.collection.objects.link(sun)
sun.rotation_euler = (Vector((0.5, 0.55, 0.67))).to_track_quat("Z", "Y").to_euler()

cd = bpy.data.cameras.new("HwCam")
cam = bpy.data.objects.new("HwCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
boom = bpy.data.objects.get("C22_Boom")
BOOM0 = boom.matrix_world.copy() if boom else None
GX, _, GZ = RC.gooseneck()
STATE_SAILS = {"Rest": ("Main_Covered",), "Up": ("Main_Set", "Genoa_Set"), "Jib": ("Main_Set", "Jib_Set"),
               "Reef": ("Main_Reefed", "Jib_Set"), "Run": ("Main_Run", "Spinnaker_Set")}
STATE_KEY = {"Rest": "rest", "Up": "up", "Jib": "jib", "Reef": "reef", "Run": "run"}


def show(state, sails=True):
    """This state's lines and sails only, the boom swung to its angle."""
    names = STATE_SAILS[state] if sails else ()
    for o in SAILS:
        o.hide_render = o.name[len("C22_Sail_"):] not in names
    for o in LINES:
        o.hide_render = o.name != "C22_Lines_" + state
    deg = HC.BOOM_DEG[STATE_KEY[state]]
    if boom:
        piv = Vector((GX, 0.0, GZ))
        boom.matrix_world = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-deg), 4, "Z") @ \
            Matrix.Translation(-piv) @ BOOM0


def shot(name, loc, target, ortho=None, lens=35, square=False):
    if ONLY and name not in ONLY:
        return
    sc.render.resolution_x, sc.render.resolution_y = RES, (RES if square else RES * 2 // 3)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    cd.clip_start, cd.clip_end = 0.01, 1000
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


MX = RC.MAST_X
show("Rest")
shot("rest_34", (6.5, 5.0, 3.6), (0.0, 0.0, 1.0), lens=28)
shot("rest_top", (0.0, 0.0, 30.0), (0.0, 0.0, 0.0), ortho=7.6)
shot("rest_quarter", (-6.0, 3.8, 3.2), (-1.0, 0.0, 0.9), lens=28)
shot("cockpit", (-4.4, 0.0, 2.3), (-1.6, 0.0, 0.6), lens=24)
shot("traveller", (-1.7, 1.9, 2.5), (-2.65, 0.0, 0.7), lens=32)
shot("ladder", (-4.6, 1.8, 1.2), (-3.25, 0.2, 0.45), lens=30)
shot("mast_foot", (MX - 1.0, 1.25, 2.1), (MX, 0.0, 1.55), lens=30)
shot("bow", (4.3, 1.6, 2.0), (2.55, 0.0, 0.95), lens=30)
show("Up")
shot("up_34", (-6.5, 6.0, 4.5), (0.0, 0.0, 2.0), lens=24)
shot("genoa_lead", (-0.2, 3.0, 2.2), (-0.6, 1.0, 1.15), lens=22)
shot("genoa_tack", (3.95, 1.25, 1.95), (3.1, 0.0, 1.25), lens=35)
shot("winch", (-1.47, 1.45, 1.25), (-1.30, 0.78, 0.74), lens=40)
shot("outhaul", (-1.5, -1.1, 2.1), (-2.0, 0.15, 1.55), lens=30)
show("Jib")
shot("jib_34", (-6.5, 6.0, 4.5), (0.0, 0.0, 2.0), lens=24)
shot("jib_lead", (-1.6, 1.9, 2.1), (-0.1, 0.4, 1.0), lens=24)
show("Reef")
shot("reef_pennant", (-1.0, -1.3, 2.3), (-1.55, 0.1, 1.65), lens=28)
show("Run")
shot("run_34", (-7.0, -6.5, 4.5), (0.3, 0.0, 2.0), lens=24)
shot("run_aft", (-4.6, 0.0, 2.6), (-1.5, 0.0, 1.0), lens=22)
print("hardware views written to", OUT)
