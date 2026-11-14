"""Clay, zebra, afloat and paint renders of Bluebonnet for the docs and the blind reviews (docs/jclass-1, jclass-2).

    python render_jclass.py <jclass.blend> <out dir> [--res 1600] [--only name,name]

Cameras are placed from the yacht's own size (she is 40 m long: the shape loop's render_set.py frames J/22-sized
boats), the same every round so before and after line up:
  clay_profile, clay_plan                    orthographic, starboard side (bow on the right) and from above
  clay_bow34, clay_stern34                   three-quarter views from above the sheer
  clay_bow, clay_stern                       end-on, long lens, the sections' shape and flare
  clay_under                                 low quarter from below the waterline: keel, garboards, run
  zebra_bow34, zebra_under, zebra_profile    stripes in a mirror hull: a fair surface shows smooth bands
  afloat_34, afloat_profile                  on a flat sea at her load waterline, eye at 1.7 m in the first
  paint_*                                    slice 2's finish in its own materials under a low sun: profile, bow and
                                             stern quarters, underside, afloat, the rudder (and turned 15 degrees in
                                             its slot, seen from port), the transom's lettering, the
                                             plating close to in a raking light, the boot top at the bow
The cameras look from Blender's -Y for the starboard side: build_jclass.py puts the hull's frame (starboard +y) into
Blender's right-handed one as (x, -y, z), so the pictures are the boat as she is, not her mirror image.
Cycles on the CPU (no GPU needed), with a material override for the clay and zebra views. Needs Blender's Python (pip bpy).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

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


sun = bpy.data.objects.new("JSun", bpy.data.lights.new("JSun", "SUN"))
SC.collection.objects.link(sun)
sun.data.angle = math.radians(0.6)


def set_sun(direction, strength):
    """direction: where the light travels (from the sun toward the boat); strength 0 turns it off."""
    sun.hide_render = strength <= 0
    sun.data.energy = strength
    sun.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()


def turn_rudder(deg):
    """Turn the rudder and its stock about the stock line (their own Z): positive moves the trailing edge to starboard,
    which turns the bow to starboard (the game's positive rudder)."""
    for nm in ("Rudder", "RudderStock"):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        if "frame" not in ob:
            ob["frame"] = [c for row in ob.matrix_world for c in row]
        M = Matrix([ob["frame"][k:k + 4] for k in range(0, 16, 4)])
        ob.matrix_world = M @ Matrix.Rotation(math.radians(deg), 4, "Z")


def shot(name, kind, loc, target, lens=50, ortho=None, sea=False, sun_dir=None, sun=0.0, samples=32, rudder=0.0):
    """kind: clay (one grey material), zebra (mirror hull in a striped world), paint (the model's own materials).
    rudder: the rudder's turn for this shot, degrees (positive: trailing edge to starboard)."""
    if ONLY and name not in ONLY:
        return
    turn_rudder(rudder)
    world_kind("zebra" if kind == "zebra" else "shade")
    WN.nodes["Background"].inputs[1].default_value = 0.55 if kind == "paint" else 1.0
    set_sun(sun_dir or (0.3, 0.5, -0.8), sun if kind == "paint" else 0.0)
    set_water(sea)
    saved = {}
    bpy.context.view_layer.material_override = None
    if sea and kind == "clay":
        for o in meshes:
            idx = [0] * len(o.data.polygons)
            o.data.polygons.foreach_get("material_index", idx)
            saved[o.name] = (list(o.data.materials), idx)
        for o in meshes:
            o.data.materials.clear()
            o.data.materials.append(material("clay"))
    elif kind != "paint":
        bpy.context.view_layer.material_override = material("zebra" if kind == "zebra" else "clay")
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd = cam.data
    cd.clip_start, cd.clip_end = 0.05, 2000
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    else:
        cd.type, cd.lens = "PERSP", lens
    SC.cycles.samples = samples
    SC.cycles.max_bounces = 2 if kind == "zebra" else 3
    SC.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    for o in meshes:                      # put the model's own materials back (clearing them resets the faces' slots)
        if o.name in saved:
            mats, idx = saved[o.name]
            o.data.materials.clear()
            for mt in mats:
                o.data.materials.append(mt)
            o.data.polygons.foreach_set("material_index", idx)


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
# slice 2: the finish in its own materials (no water unless afloat), a low sun for the plating's relief
SUN = (0.45, 0.55, -0.55)
shot("paint_profile", "paint", (MID.x, -60, MID.z), MID, ortho=1.05 * max(L, (HI.z - LO.z) * ASPECT), sun_dir=SUN,
     sun=3.5)
shot("paint_bow34", "paint", (HI.x + 0.55 * L, -0.75 * L, 0.32 * L), (MID.x + 0.12 * L, 0, -0.6), lens=50,
     sun_dir=SUN, sun=3.5)
shot("paint_stern34", "paint", (LO.x - 0.55 * L, -0.25 * L, 0.12 * L), (LO.x + 0.4 * L, 0, -0.8), lens=55,
     sun_dir=SUN, sun=3.5)
shot("paint_under", "paint", (MID.x + 0.35 * L, -0.6 * L, -0.28 * L), (MID.x - 0.05 * L, 0, -2.0), lens=40,
     sun_dir=(0.2, 0.6, 0.6), sun=3.0)
shot("paint_afloat34", "paint", (HI.x + 0.9 * L, -1.1 * L, 1.7), (MID.x + 0.05 * L, 0, 0.6), lens=55, sea=True,
     sun_dir=SUN, sun=3.5)
# the rudder from abeam (starboard), then turned 15 degrees to starboard seen from port aft (its nose turning in the
# keel's groove, its head under the deadwood's shoulder); drawings_jclass.py draws its sections hard over
shot("paint_rudder", "paint", (-6.0, -13.0, -2.9), (-6.6, 0, -3.2), lens=40, sun_dir=(0.35, 0.75, -0.45), sun=3.0,
     samples=48)
shot("paint_slot", "paint", (-9.8, 4.6, -3.6), (-6.0, 0, -3.2), lens=40, sun_dir=(0.45, -0.7, -0.45), sun=3.0,
     samples=48, rudder=15.0)
shot("paint_transom", "paint", (LO.x - 7.0, -1.2, 2.4), (LO.x + 0.3, 0, 1.68), lens=70, sun_dir=(0.6, 0.35, -0.7),
     sun=3.5, samples=48)
# the plating close to, where the topside strake's seam meets a butt 2.6 m away (x 6.1 m, 0.47 m up), in a sun raking
# along the side from forward and above: flush rivets under the paint show only as faint dimples (the relief fades past 6 m)
shot("paint_plating", "paint", (4.5, -4.75, 0.95), (6.25, -2.7, 0.5), lens=35, sun_dir=(-0.7, 0.3, -0.65), sun=4.0,
     samples=64)
# the boot top rising toward the bow, where the hull leaves the water at a shallow angle; low, from abeam
shot("paint_bowline", "paint", (HI.x - 5.0, -14.5, 0.5), (HI.x - 7.5, 0, 0.2), lens=35, sun_dir=SUN, sun=3.5,
     samples=48)
print("render_jclass: done")
