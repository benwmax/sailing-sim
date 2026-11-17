"""The Catalina 22's cabin below, the views in docs/c22-8: her slot colours under a grey sky, with cabin lights on
inside (a dome light under the top, one in the V-berth and two low ones aft), since the cabin is dark with the hatch shut.

    blender -b -P render_cabin_c22.py -- <c22.blend> <out dir> [--res 1200] [--only a,b] [--clay]

Views:
  plan                  from above with the deck, trunk and headliner hidden: the layout
  cutaway_port          from high on the starboard quarter with the deck and trunk off: the port side (dinette, galley)
  cutaway_stbd          from high on the port bow, the same: the starboard side (settee, quarter berth), galley out
  companionway          from the cockpit, down through the companionway with the drop boards out
  forward               standing under the raised pop-top, looking forward to the V-berth
  aft                   from the V-berth's doorway, looking aft: the step, keel winch, galley pulled out, quarter berth
  dinette_down          the dinette's table lowered with its filler cushion: the berth
  window                from outside, the starboard ports with the cabin behind them
Frame: Blender's (X forward, Y to port, Z up). --clay draws everything in one clay, for the blind rounds.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1200
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
CLAY = "--clay" in ARGS
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
for o in sc.objects:
    if o.type not in ("MESH", "CURVE"):
        o.hide_render = True
OB = {o.name: o for o in sc.objects}
START = {o.name: o.hide_render for o in sc.objects}

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.cycles.samples = 48
sc.cycles.max_bounces = 4
sc.render.use_compositing = sc.render.use_sequencer = False
sc.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("CabWorld")
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.62, 0.64, 0.66, 1)
bg.inputs[1].default_value = 1.0
METAL = ("Stainless", "Aluminium", "Wire", "Lifeline")
for m in bpy.data.materials:
    m.use_nodes = True
    pb = m.node_tree.nodes.get("Principled BSDF")
    if pb:
        base = m.name.split(".")[0]
        pb.inputs["Base Color"].default_value = m.diffuse_color
        pb.inputs["Roughness"].default_value = 0.35 if base in METAL else (0.9 if base in ("Cushion", "Curtain") else 0.6)
        pb.inputs["Metallic"].default_value = 0.6 if base in METAL else 0.0
        if base == "CabinWindow":                          # tinted acrylic: the cabin shows through
            pb.inputs["Transmission Weight"].default_value = 0.85
            pb.inputs["Roughness"].default_value = 0.05
            pb.inputs["Base Color"].default_value = (0.35, 0.36, 0.33, 1)
if CLAY:
    clay = bpy.data.materials.new("CabClay")
    clay.use_nodes = True
    nt = clay.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
    nt.links.new(dif.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    bpy.context.view_layer.material_override = clay


def light(name, kind, loc, energy, size=0.1, rot=None):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    if kind == "SUN":
        d.angle = math.radians(3)
    else:
        d.shadow_soft_size = size
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    if rot is not None:
        o.rotation_euler = Vector(rot).to_track_quat("Z", "Y").to_euler()
    return o


SUN = light("CabSun", "SUN", (0, 0, 10), 3.0, rot=(0.4, -0.5, 0.75))
INSIDE = [light("CabDome", "POINT", (0.1, 0.0, 1.05), 12.0, 0.08), light("CabVBerth", "POINT", (1.9, 0.0, 0.7), 5.0, 0.06),
          light("CabQuarter", "POINT", (-1.2, -0.45, 0.33), 2.0, 0.05),
          light("CabGalley", "POINT", (-0.7, 0.5, 0.3), 1.5, 0.05)]

cd = bpy.data.cameras.new("CabCam")
cam = bpy.data.objects.new("CabCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam

OUTSIDE = ("C22_Deck", "C22_Cabin", "C22_PopTop", "C22_PopTopRaised", "C22_LidRails", "C22_LidRailsRaised",
           "C22_Interior_Headliner", "C22_ForeHatch", "C22_Ports", "C22_DropBoards", "C22_Hardware", "C22_Lifelines", "C22_MastHardware", "C22_Halyards",
           "C22_Mast", "C22_Boom", "C22_Wires", "C22_RigFittings", "C22_Sail_Main_Covered", "C22_Lines_Rest",
           "C22_Rubrail", "C22_Well")


def setup(hide=(), show=(), raised=False, galley_out=False, table_down=False, lights=True):
    for n, o in OB.items():
        if o.type in ("MESH", "CURVE"):
            o.hide_render = START.get(n, False)
    for n in hide:
        if n in OB:
            OB[n].hide_render = True
    for n in show:
        if n in OB:
            OB[n].hide_render = False
    OB["C22_PopTop"].hide_render = raised or "C22_PopTop" in hide
    OB["C22_PopTopRaised"].hide_render = not raised or "C22_PopTopRaised" in hide
    OB["C22_LidRails"].hide_render = raised or "C22_PopTop" in hide
    OB["C22_LidRailsRaised"].hide_render = not raised or "C22_PopTopRaised" in hide
    OB["C22_Interior_Galley"].hide_render = galley_out
    OB["C22_Interior_GalleyOut"].hide_render = not galley_out
    OB["C22_Interior_Table"].hide_render = table_down
    OB["C22_Interior_TableDown"].hide_render = not table_down
    for li in INSIDE:
        li.hide_render = not lights


def shot(name, loc, target, ortho=None, lens=24, clip=0.01, aspect=(3, 2)):
    if ONLY and name not in ONLY:
        return
    sc.render.resolution_x, sc.render.resolution_y = RES, RES * aspect[1] // aspect[0]
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    cd.clip_start, cd.clip_end = clip, 1000
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


setup(hide=OUTSIDE)
shot("plan", (0.1, 0.0, 12.0), (0.1, 0.0, 0.0), ortho=6.4, aspect=(2, 1))
shot("cutaway_port", (-2.2, -2.1, 2.9), (0.3, 0.15, 0.0), lens=28)
setup(hide=OUTSIDE, galley_out=True)
shot("cutaway_stbd", (2.6, 2.0, 2.8), (-0.2, -0.15, 0.0), lens=28)
setup(hide=("C22_DropBoards",))
shot("companionway", (-1.75, 0.0, 1.3), (0.4, 0.0, 0.25), lens=18)
setup(raised=True)
shot("forward", (-0.6, 0.0, 1.45), (2.0, 0.0, 0.35), lens=14)
setup(raised=True, galley_out=True)
shot("aft", (0.72, -0.18, 0.95), (-1.6, 0.05, 0.15), lens=14)
setup(raised=True, table_down=True)
shot("dinette_down", (0.25, -0.35, 0.95), (0.35, 0.55, 0.15), lens=16)
setup()
shot("window", (0.15, -2.6, 1.25), (0.15, 0.0, 0.85), lens=32)
print("cabin views written to", OUT)
