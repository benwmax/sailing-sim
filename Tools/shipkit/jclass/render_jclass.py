"""Clay, zebra and afloat renders of Bluebonnet for the docs and the blind reviews (docs/jclass-1).

    python render_jclass.py <jclass.blend> <out dir> [--res 1600] [--only name,name]

Cameras are placed from the yacht's own size (she is 40 m long: the shape loop's render_set.py frames J/22-sized
boats), the same every round so before and after line up:
  clay_profile, clay_plan                    orthographic, port side (bow on the right) and from above
  clay_bow34, clay_stern34                   three-quarter views from above the sheer
  clay_bow, clay_stern                       end-on, long lens, the sections' shape and flare
  clay_under                                 low quarter from below the waterline: keel, garboards, run
  zebra_bow34, zebra_under, zebra_profile    stripes in a mirror hull: a fair surface shows smooth bands
  afloat_34, afloat_profile                  on a flat sea at her load waterline, eye at 1.7 m in the first
Cycles on the CPU with a material override (no GPU needed). Needs Blender's Python (pip bpy).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1600
ONLY = set(ARGS[ARGS.index("--only") + 1].split(",")) if "--only" in ARGS else None
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
SC = bpy.context.scene
SC.render.engine = "CYCLES"
SC.cycles.device = "CPU"
SC.cycles.use_denoising = True
SC.render.resolution_x, SC.render.resolution_y = RES, RES * 9 // 16
SC.render.use_compositing = False
SC.render.use_sequencer = False
SC.view_settings.view_transform = "Standard"
SC.view_settings.look = "None"

meshes = [o for o in SC.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
LO = Vector([min(p[i] for p in pts) for i in range(3)])
HI = Vector([max(p[i] for p in pts) for i in range(3)])
MID = (LO + HI) / 2
L = HI.x - LO.x

world = bpy.data.worlds.new("JWorld")
SC.world = world
world.use_nodes = True
WN = world.node_tree


def world_kind(kind):
    for n in list(WN.nodes):
        if n.type != "OUTPUT_WORLD":
            WN.nodes.remove(n)
    out = [n for n in WN.nodes if n.type == "OUTPUT_WORLD"][0]
    bg = WN.nodes.new("ShaderNodeBackground")
    WN.links.new(bg.outputs[0], out.inputs[0])
    tc = WN.nodes.new("ShaderNodeTexCoord")
    sep = WN.nodes.new("ShaderNodeSeparateXYZ")
    WN.links.new(tc.outputs["Generated"], sep.inputs[0])
    if kind == "zebra":
        mul = WN.nodes.new("ShaderNodeMath")
        mul.operation, mul.inputs[1].default_value = "MULTIPLY", 22.0
        sn = WN.nodes.new("ShaderNodeMath")
        sn.operation = "SINE"
        gt = WN.nodes.new("ShaderNodeMath")
        gt.operation, gt.inputs[1].default_value = "GREATER_THAN", 0.0
        WN.links.new(sep.outputs["Z"], mul.inputs[0])
        WN.links.new(mul.outputs[0], sn.inputs[0])
        WN.links.new(sn.outputs[0], gt.inputs[0])
        WN.links.new(gt.outputs[0], bg.inputs[0])
    else:      # bright sky over a darker ground: soft clay light that shows form
        ramp = WN.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.22, 0.23, 0.25, 1)
        ramp.color_ramp.elements[1].position = 0.78
        ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.03, 1)
        mr = WN.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
        WN.links.new(sep.outputs["Z"], mr.inputs["Value"])
        WN.links.new(mr.outputs[0], ramp.inputs[0])
        WN.links.new(ramp.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 1.0


def material(kind):
    m = bpy.data.materials.get("J_" + kind) or bpy.data.materials.new("J_" + kind)
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if kind == "zebra":
        g = nt.nodes.new("ShaderNodeBsdfGlossy")
        g.inputs[0].default_value = (1, 1, 1, 1)
        g.inputs[1].default_value = 0.0
        nt.links.new(g.outputs[0], out.inputs[0])
    elif kind == "water":
        p = nt.nodes.new("ShaderNodeBsdfPrincipled")
        p.inputs["Base Color"].default_value = (0.05, 0.12, 0.16, 1)
        p.inputs["Roughness"].default_value = 0.08
        nt.links.new(p.outputs[0], out.inputs[0])
    else:
        d = nt.nodes.new("ShaderNodeBsdfDiffuse")
        d.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
        nt.links.new(d.outputs[0], out.inputs[0])
    return m


cam = bpy.data.objects.new("JCam", bpy.data.cameras.new("JCam"))
SC.collection.objects.link(cam)
SC.camera = cam

water = None


def set_water(on):
    global water
    if on and water is None:
        bpy.ops.mesh.primitive_plane_add(size=L * 12, location=(MID.x, 0, 0))
        water = bpy.context.active_object
        water.name = "JWater"
        water.data.materials.append(material("water"))
    if water is not None:
        water.hide_render = not on


def shot(name, kind, loc, target, lens=50, ortho=None, sea=False):
    if ONLY and name not in ONLY:
        return
    world_kind("zebra" if kind == "zebra" else "shade")
    set_water(sea)
    if sea:
        bpy.context.view_layer.material_override = None
        for o in meshes:
            o.data.materials.clear()
            o.data.materials.append(material("clay"))
    else:
        bpy.context.view_layer.material_override = material("zebra" if kind == "zebra" else "clay")
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd = cam.data
    cd.clip_start, cd.clip_end = 0.05, 2000
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    else:
        cd.type, cd.lens = "PERSP", lens
    SC.cycles.samples = 32
    SC.cycles.max_bounces = 2 if kind == "zebra" else 3
    SC.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


up = Vector((0, 0, 1))
ASPECT = 16 / 9
shot("clay_profile", "clay", (MID.x, -60, MID.z), MID, ortho=1.05 * max(L, (HI.z - LO.z) * ASPECT))
shot("clay_plan", "clay", (MID.x, 0, 60), (MID.x, 0, 0), ortho=1.05 * L)
shot("clay_bow34", "clay", (HI.x + 0.55 * L, -0.75 * L, 0.32 * L), (MID.x + 0.12 * L, 0, -0.6), lens=50)
shot("clay_stern34", "clay", (LO.x - 0.55 * L, -0.75 * L, 0.30 * L), (MID.x - 0.12 * L, 0, -0.6), lens=50)
shot("clay_bow", "clay", (HI.x + 3.0 * L, 0, 0.5), (MID.x, 0, -1.2), lens=420)
shot("clay_stern", "clay", (LO.x - 3.0 * L, 0, 0.5), (MID.x, 0, -1.2), lens=420)
shot("clay_under", "clay", (MID.x + 0.45 * L, -0.7 * L, -0.30 * L), (MID.x, 0, -1.5), lens=45)
shot("zebra_bow34", "zebra", (HI.x + 0.55 * L, -0.75 * L, 0.32 * L), (MID.x + 0.12 * L, 0, -0.6), lens=50)
shot("zebra_under", "zebra", (MID.x + 0.45 * L, -0.7 * L, -0.30 * L), (MID.x, 0, -1.5), lens=45)
shot("zebra_profile", "zebra", (MID.x, -60, MID.z), MID, ortho=1.05 * max(L, (HI.z - LO.z) * ASPECT))
shot("afloat_34", "clay", (HI.x + 0.9 * L, -1.1 * L, 1.7), (MID.x + 0.05 * L, 0, 0.6), lens=55, sea=True)
shot("afloat_profile", "clay", (MID.x, -2.2 * L, 1.7), (MID.x, 0, 0.8), lens=60, sea=True)
print("render_jclass: done")
