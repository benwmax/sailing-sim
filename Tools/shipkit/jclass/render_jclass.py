"""Clay, zebra, afloat, paint, deck and rig renders of Bluebonnet for the docs and the blind reviews (docs/jclass-1 to
jclass-4).

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
  deck_*                                     slice 3's deck: from aloft, a bow quarter from above, the bow's nibbed
                                             planking, the skylight and companionway, the doghouse, the helm (wheel,
                                             binnacle, cockpit), the stern's after margin, and the helmsman's eye
  rig_*                                      slice 4's spars: profile and from ahead (orthographic), a quarter view
                                             afloat, the masthead, the hounds and jumpers, the spreaders seen from the
                                             deck, the gooseneck, the pole's car, and the boom and pole set for a run
                                             (boom to starboard, pole to port) and a reach (boom to port, pole to
                                             starboard)
Each shot shows the objects of its own slice and the ones before it (an object's "slice" property), so the earlier
slices' shots stay as they were and are framed on the hull as before; what the build hid (slice 1's moulded hull, kept
as the measured reference) stays hidden in every shot.
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
HIDDEN = {o.name for o in meshes if o.hide_render}       # what the build hid (slice 1's moulded hull) stays hidden


def bounds(obs):
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi, (lo + hi) / 2


LO, HI, MID = bounds([o for o in meshes if o.get("slice", 1) < 4])      # the hull and deck: the earlier slices' frame
L = HI.x - LO.x
LOA, HIA, MIDA = bounds(meshes)                                            # with the rig

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


def turn_about_z(name, deg):
    """Turn an object about its own Z from where the build put it (its "frame"), degrees, right-handed in Blender."""
    ob = bpy.data.objects.get(name)
    if ob is None:
        return
    if "frame" not in ob:
        ob["frame"] = [c for row in ob.matrix_world for c in row]
    M = Matrix([ob["frame"][k:k + 4] for k in range(0, 16, 4)])
    ob.matrix_world = M @ Matrix.Rotation(math.radians(deg), 4, "Z")


def swing_boom(deg):
    """Swing the boom about its gooseneck pin: positive takes its end to starboard (build.json's rig frames: a positive
    turn about the boom's own Z in Blender moves its end to starboard)."""
    turn_about_z("Boom", deg)


def set_pole(deg):
    """Set the spinnaker pole deg from the bow, positive to starboard, negative to port. The build sets it 70 degrees
    to starboard, and a positive turn about its own Z in Blender takes its end to port."""
    turn_about_z("SpinnakerPole", 70.0 - deg)


def shot(name, kind, loc, target, lens=50, ortho=None, sea=False, sun_dir=None, sun=0.0, samples=32, rudder=0.0,
         upto=3, boom=0.0, pole=70.0):
    """kind: clay (one grey material), zebra (mirror hull in a striped world), paint (the model's own materials).
    rudder: the rudder's turn for this shot, degrees (positive: trailing edge to starboard). upto: the last slice whose
    objects show. boom: the boom's swing, degrees (positive: to starboard); pole: the pole's set from the bow (positive:
    to starboard)."""
    if ONLY and name not in ONLY:
        return
    for o in meshes:
        o.hide_render = o.name in HIDDEN or o.get("slice", 1) > upto
    turn_rudder(rudder)
    swing_boom(boom)
    set_pole(pole)
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
# slice 3: the deck in its own materials under a sun at about 45 degrees from forward of the starboard beam; the seams
# fade to the deck's average tone past 14 m (gone by 48 m), so the far views show the planks' tints, the near ones
# their seams, nibs and butts
DSUN = (0.35, 0.55, -0.75)
shot("deck_aloft", "paint", (9.0, 0.6, 21.0), (-7.0, 0.0, 1.5), lens=28, sun_dir=DSUN, sun=2.4, samples=48)
shot("deck_34", "paint", (HI.x + 0.22 * L, -0.42 * L, 0.33 * L), (MID.x + 0.08 * L, 0, 1.0), lens=36, sun_dir=DSUN,
     sun=2.4, samples=48)
shot("deck_bow", "paint", (15.0, 0.9, 3.5), (17.6, -0.55, 1.75), lens=30, sun_dir=DSUN, sun=2.4, samples=64)
shot("deck_skylight", "paint", (2.3, -2.5, 3.1), (-1.3, 0.0, 1.75), lens=30, sun_dir=DSUN, sun=2.4, samples=64)
shot("deck_doghouse", "paint", (-1.2, -3.1, 3.0), (-6.0, 0.0, 1.85), lens=30, sun_dir=DSUN, sun=2.4, samples=64)
shot("deck_helm", "paint", (-14.0, -2.5, 3.3), (-9.5, 0.0, 1.7), lens=30, sun_dir=DSUN, sun=2.4, samples=64)
shot("deck_stern", "paint", (-17.3, -1.9, 3.4), (-20.6, 0.0, 1.55), lens=30, sun_dir=DSUN, sun=2.4, samples=64)
# the helmsman's eye: standing on the cockpit's sole abaft the wheel, 1.6 m up, looking forward along the deck
shot("deck_eye", "paint", (-10.6, 0.25, 2.59), (2.0, 0.0, 1.9), lens=24, sun_dir=DSUN, sun=2.4, samples=48)
# slice 4: the spars (Blender's -Y is starboard). The mast steps at x 3.0; the hounds are 36 m above the deck (z about
# 37.6), the truck's top at z 47.8; the boom's top at the mast 2.45 m above the deck; the pole's heel 2.0 m up.
RSUN = (-0.35, 0.5, -0.8)
HA = HIA.z - LOA.z
shot("rig_profile", "paint", (MIDA.x, -150, MIDA.z), MIDA, ortho=1.05 * max(HIA.x - LOA.x, HA * ASPECT), sun_dir=RSUN,
     sun=3.0, upto=4)
shot("rig_ahead", "paint", (150, 0, MIDA.z), (0, 0, MIDA.z), ortho=1.05 * HA * ASPECT, sun_dir=(-0.6, 0.3, -0.75),
     sun=3.0, upto=4)
shot("rig_afloat34", "paint", (46.0, -54.0, 5.0), (-1.0, 0.0, 22.0), lens=24, sea=True, sun_dir=RSUN, sun=3.0,
     samples=48, upto=4)
shot("rig_masthead", "paint", (6.0, -4.2, 49.4), (1.85, 0.0, 46.9), lens=50, sun_dir=RSUN, sun=3.0, samples=64,
     upto=4)
shot("rig_hounds", "paint", (8.5, -6.0, 39.6), (3.2, 0.0, 37.4), lens=40, sun_dir=RSUN, sun=3.0, samples=64, upto=4)
shot("rig_spreaders", "paint", (7.0, -3.6, 2.9), (2.4, 0.0, 30.0), lens=22, sun_dir=RSUN, sun=3.0, samples=64,
     upto=4, pole=10.0)
shot("rig_gooseneck", "paint", (-0.6, -2.7, 4.7), (2.55, 0.0, 3.7), lens=35, sun_dir=RSUN, sun=3.0, samples=64,
     upto=4)
shot("rig_polecar", "paint", (6.6, -2.6, 4.5), (3.2, 0.0, 3.4), lens=35, sun_dir=(-0.6, 0.35, -0.7), sun=3.0,
     samples=64, upto=4)
# from high astern: running (the boom squared off to starboard, the pole squared to port) and reaching on starboard
# tack (the boom eased to port, the pole forward to starboard)
shot("rig_run", "paint", (-62.0, -9.0, 46.0), (-5.0, 0.0, 2.0), lens=38, sun_dir=RSUN, sun=3.0, samples=48, upto=4,
     boom=80.0, pole=-85.0)
shot("rig_reach", "paint", (-62.0, -9.0, 46.0), (-5.0, 0.0, 2.0), lens=38, sun_dir=RSUN, sun=3.0, samples=48,
     upto=4, boom=-30.0, pole=60.0)
print("render_jclass: done")
