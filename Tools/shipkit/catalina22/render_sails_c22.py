"""The Catalina 22's sail views (docs/c22-6): the shape loop's clay look, as render_rig_c22.py, with one set of sails
shown per view and the boom swung to the angle they were built for.

    blender -b -P render_sails_c22.py -- <c22.blend> <out dir> [--res 1200] [--only a,b]

Views (each names the sails it shows):
  up_profile, up_bow, up_34       Main_Set and Genoa_Set, close-hauled on starboard tack (orthographic from port, from
                                  ahead, and from the port bow)
  run_profile, run_34             Main_Run and Spinnaker_Set, on a run
  jib_34, reef_profile            Main_Set and Jib_Set; Main_Reefed and Jib_Set
  head, hanks, clew, reef, battens  close-ups of the set sails
  flaked, covered, lowered, bags  the mainsail flaked and covered, the genoa down on the foredeck, the bags
  far_up, far_up_abeam, far_up_windward, far_run, far_run_abeam
                                  Milestone A's silhouettes: the boat in her colours from 200 m at eye height (3 m), from
                                  the lee bow, abeam to leeward and to windward; running, from the bow and abeam
Frame: Blender's (X forward, Y to port, Z up). Cycles on the CPU, few samples, a grey sky and a high sun from the port
bow: shape, not looks.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig_c22 as RC                                   # noqa: E402  (the rig's numbers, not copies)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1200
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
for o in sc.objects:
    if o.type not in ("MESH", "CURVE"):
        o.hide_render = True
SAILS = [o for o in sc.objects if o.name.startswith("C22_Sail_")]

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.cycles.samples = 32
sc.cycles.max_bounces = 3
sc.render.resolution_x, sc.render.resolution_y = RES, RES // 2
sc.render.use_compositing = sc.render.use_sequencer = False
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("SailWorld")
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
clay = bpy.data.materials.new("SailClay")
clay.use_nodes = True
nt = clay.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
d = nt.nodes.new("ShaderNodeBsdfDiffuse")
d.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
nt.links.new(d.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
bpy.context.view_layer.material_override = clay

sun_d = bpy.data.lights.new("SailSun", "SUN")       # a high sun from the port bow: the cloth's curve reads in its shading
sun_d.energy, sun_d.angle = 2.5, math.radians(3.0)
sun = bpy.data.objects.new("SailSun", sun_d)
sc.collection.objects.link(sun)
sun.rotation_euler = (Vector((0.5, 0.55, 0.67))).to_track_quat("Z", "Y").to_euler()

cd = bpy.data.cameras.new("SailCam")
cam = bpy.data.objects.new("SailCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
boom = bpy.data.objects.get("C22_Boom")
BOOM0 = boom.matrix_world.copy() if boom else None
GX, _, GZ = RC.gooseneck()                             # the boom's pivot


def show(*names):
    """Show these sails (C22_Sail_<name>) only, and swing the boom to the first set one's angle."""
    deg = 0.0
    for o in SAILS:
        on = o.name[len("C22_Sail_"):] in names
        o.hide_render = not on
        if on and "boom_deg" in o:
            deg = o["boom_deg"]
    if boom:
        piv = Vector((GX, 0.0, GZ))
        boom.matrix_world = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-deg), 4, "Z") @ \
            Matrix.Translation(-piv) @ BOOM0


def shot(name, loc, target, ortho=None, lens=35, square=False):
    if ONLY and name not in ONLY:
        return
    sc.render.resolution_x, sc.render.resolution_y = RES, (RES if square else RES // 2)
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


def far(name, loc, target, lens=450):
    """A Milestone A view: the boat in her slot colours on a grey sea, the camera at eye height (3 m) about 200 m off.
    A long lens only enlarges: at 200 m it draws what the eye sees, as a crop of a 50 mm view would."""
    if ONLY and name not in ONLY:
        return
    bpy.context.view_layer.material_override = None
    sea.hide_render = False
    shot(name, loc, target, lens=lens, square=True)
    sea.hide_render = True
    bpy.context.view_layer.material_override = clay


for m in bpy.data.materials:                      # the far views' colours: each slot's (build_c22.SLOT_RGB)
    if m.use_nodes and m.name not in ("SailClay",):
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Base Color"].default_value = m.diffuse_color
bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, 0))
sea = bpy.context.active_object
sea.name = "Sea"
sm = bpy.data.materials.new("Sea")
sm.use_nodes = True
pb = sm.node_tree.nodes.get("Principled BSDF")
pb.inputs["Base Color"].default_value = (0.08, 0.11, 0.13, 1)
pb.inputs["Roughness"].default_value = 0.25
sea.data.materials.append(sm)
sea.hide_render = True

MX, TOP = RC.MAST_X, RC.top_z()
show("Main_Set", "Genoa_Set")
shot("up_profile", (0.5, 30, 4.6), (0.5, 0, 4.6), ortho=10.5, square=True)
shot("up_bow", (30, 0, 4.6), (0, 0, 4.6), ortho=10.5, square=True)
shot("up_34", (9.0, 7.5, 2.4), (0.3, 0, 4.2), lens=24)
shot("hanks", (3.3, -0.5, 2.45), (2.86, 0, 2.37), lens=50)
shot("clew", (-0.2, 2.4, 2.2), (0.0, 0.9, 1.3), lens=30)
shot("head", (MX + 1.2, 1.4, TOP + 0.1), (MX, 0, TOP - 0.5), lens=40)
shot("battens", (-2.0, 3.2, 5.0), (-0.9, 0.3, 4.6), lens=30)
shot("reef", (-1.2, 3.0, 2.4), (-0.4, 0.2, 2.6), lens=30)
far("far_up", (141, 141, 3.0), (0.3, 0, 4.3))
far("far_up_abeam", (0.3, 200, 3.0), (0.3, 0, 4.3))
far("far_up_windward", (0.3, -200, 3.0), (0.3, 0, 4.3))
show("Main_Set", "Jib_Set")
shot("jib_34", (9.0, 7.5, 2.4), (0.3, 0, 4.2), lens=24)
show("Main_Reefed", "Jib_Set")
shot("reef_profile", (0.5, 30, 4.6), (0.5, 0, 4.6), ortho=10.5, square=True)
show("Main_Run", "Spinnaker_Set")
shot("run_profile", (0.5, 30, 4.6), (0.5, 0, 4.6), ortho=10.5, square=True)
shot("run_34", (10.0, -6.0, 2.6), (0.5, 0, 4.2), lens=24)
far("far_run", (141, 141, 3.0), (0.5, 0, 4.3))
far("far_run_abeam", (0.5, 200, 3.0), (0.5, 0, 4.3))
show("Main_Flaked")
shot("flaked", (-0.6, 2.4, 2.6), (-0.6, 0, 1.6), lens=28)
show("Main_Covered")
shot("covered", (-0.6, 2.4, 2.6), (-0.6, 0, 1.6), lens=28)
show("Genoa_Lowered", "Main_Covered")
shot("lowered", (3.9, 1.6, 2.2), (2.5, 0, 1.0), lens=30)
show("Genoa_Bagged")
shot("bags", (3.5, 1.2, 1.9), (2.62, 0, 1.1), lens=35)
print("sail views written to", OUT)
