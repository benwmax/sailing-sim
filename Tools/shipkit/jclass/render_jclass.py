"""Clay, zebra, afloat, paint, deck, rig, rigging, sails, running rigging, deck hardware and below-decks renders of
Bluebonnet for the docs and the blind reviews (docs/jclass-1 to jclass-9).

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
  rigging_*                                  slice 5's standing rigging and runners, sailed on starboard tack (the
                                             starboard runner and checkstay set, the port pair let off): profile and
                                             from ahead, a quarter view afloat, the hounds, a lower spreader's tip, the
                                             chainplates, the let-off pair lashed to the shroud, a set runner's tackle,
                                             the masthead's backstay crane, the jumpers, the backstay at the counter,
                                             the forestay at the stem head, the boom squared off past the let-off pair,
                                             and running on each tack
  sails_*                                    slice 6's sails: Milestone A's silhouettes at 200 m (main and genoa from
                                             the lee bow, abeam to leeward and to windward; the quadrilateral and
                                             staysail; the spinnaker from the bow and abeam), the profile, quarter
                                             views of each suit, the main backlit, the headboard, the clew and reef
                                             points, the luff slides on the track, the hanks, the genoa's clew, the
                                             spinnaker's head, and the sails stowed: moored (flaked and bagged),
                                             lowered on deck, and the main's slides stacked at the foot of the track
  running_*                                  slice 7's winches and running rigging, on starboard tack: the after deck
                                             from the lee quarter, a primary winch's turns, cleat and coil, the
                                             mainsheet's tackle, a runner's tail onto its winch, the reels round the
                                             mast's foot, the halyards' boxes aloft, the genoa's lead, the
                                             quadrilateral's and the spinnaker's suits, the pole's end, moored with the
                                             topping lift on, and an idle capstan and reel close to (the part loop's
                                             views)
  hardware_*                                 slice 8's deck hardware: the foredeck moored from aloft, the profile with
                                             the ensign flying (framed to the burgee), the stem head, a bow cleat and
                                             its fairlead, the anchor on its chocks, a cowl's red mouth in harbour and
                                             its flange capped at sea, a deck prism, both side lights on their boards
                                             (under main and genoa), the genoa's sheet track and car, the counter with
                                             the stern light and the ensign's socket, the ensign, and the burgee at the
                                             masthead
  below_*                                    slice 9's cabins forward, lit by work lights under the deck (the render's,
                                             not the model's: lighting below is slice 10's): a plan cut at 1.25 m and
                                             the two halves cut at the centreline (the camera's clipping does the
                                             cutting), the forepeak cut in the gypsy's plane, views in the fo'c'sle,
                                             the galley, the bins round the mast, the sail locker, the washroom and the
                                             forepeak, close views of a cot, the range and the windlass, and on deck the
                                             bow chock and the cable's lead to the chain pipe
Each shot shows the objects of its own slice and the ones before it (an object's "slice" property), so the earlier
slices' shots stay as they were and are framed on the hull as before; what the build hid (slice 1's moulded hull, kept
as the measured reference) stays hidden in every shot.
The cameras look from Blender's -Y for the starboard side: build_jclass.py puts the hull's frame (starboard +y) into
Blender's right-handed one as (x, -y, z), so the pictures are the boat as she is, not her mirror image.
Cycles on the CPU (no GPU needed), with a material override for the clay and zebra views. Needs Blender's Python (pip bpy).
"""
import json
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
LOA, HIA, MIDA = bounds([o for o in meshes if o.get("slice", 1) < 6])       # with the rig (not the sails)
LOH, HIH, MIDH = bounds([o for o in meshes if o.get("slice", 1) < 6 or o.name in ("Burgee.Moored", "Ensign.Moored")])
SUITS = {k: v for k, v in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      "sails_bluebonnet.json")))["suits"].items() if k != "note"}

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


def set_water(on, size=1.0):
    """on: a flat sea at the load waterline, `size` times the usual 12 boat lengths across (the far views want
    its edge past the horizon)."""
    global water
    if on and water is None:
        bpy.ops.mesh.primitive_plane_add(size=L * 12, location=(MID.x, 0, 0))
        water = bpy.context.active_object
        water.name = "JWater"
        water.data.materials.append(material("water"))
    if water is not None:
        water.hide_render = not on
        water.scale = (size, size, 1.0)


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
    turn about the boom's own Z in Blender moves its end to starboard). The mainsail lowered or flaked on it goes with
    it (built in the boom's frame)."""
    turn_about_z("Boom", deg)
    for o in meshes:
        if o.get("on_boom"):
            turn_about_z(o.name, deg)


def set_pole(deg):
    """Set the spinnaker pole deg from the bow, positive to starboard, negative to port. The build sets it 70 degrees
    to starboard, and a positive turn about its own Z in Blender takes its end to port. "stowed": lashed down on the
    starboard side deck (the build's "stowed" matrix)."""
    ob = bpy.data.objects.get("SpinnakerPole")
    if deg == "stowed":
        ob.matrix_world = Matrix([ob["stowed"][k:k + 4] for k in range(0, 16, 4)])
        return
    turn_about_z("SpinnakerPole", 70.0 - deg)


def shown(o, upto, tack, suit=None):
    """Whether an object shows in a shot: its slice is no later than `upto`, the build did not hide it, a runner's or
    a checkstay's state shows set on the tack's side (windward) and let off on the other, and a sail's state shows
    when it is in the shot's suit (sails_bluebonnet.json's suits)."""
    if o.get("slice", 1) > upto:
        return False
    if o.get("sail") is not None:
        return suit is not None and suit in o["suits"].split(",")
    if o.get("suit") is not None:                          # slice 7's running rigging and slice 8's flags, by suit
        return o["suit"] == suit
    if o.get("state") is not None:
        return (o["state"] == "Set") == (o["side"] == tack)
    return o.name not in HIDDEN


WORK = []          # slice 9's work lights below: lamps under the deckhead, shining down, at (x, z) on the centreline
# (z 3 cm under each room's lowest beam), watts; the camera does not see them, nor do glossy rays (no hot spots on the
# varnish), and the below shots use AgX, whose highlights roll off instead of clipping white
for x_, z_, w_ in ((2.3, 1.29, 22), (3.9, 1.29, 22), (5.6, 1.33, 22), (7.4, 1.33, 22), (9.3, 1.42, 20),
                   (10.6, 1.42, 20), (11.9, 1.54, 14), (12.9, 1.54, 12), (13.9, 1.67, 8), (15.0, 1.67, 8)):
    lt = bpy.data.lights.new(f"JWork{x_}", "AREA")
    lt.shape, lt.size, lt.energy = "DISK", 0.35, w_
    lt.color = (1.0, 0.93, 0.82)
    lo = bpy.data.objects.new(f"JWork{x_}", lt)
    lo.location = (x_, 0.0, z_)                    # an area light shines down its -Z: no turn needed
    lo.visible_camera, lo.visible_glossy = False, False
    SC.collection.objects.link(lo)
    WORK.append(lo)


def shot(name, kind, loc, target, lens=50, ortho=None, sea=False, sun_dir=None, sun=0.0, samples=32, rudder=0.0,
         upto=3, boom=0.0, pole=70.0, tack="starboard", suit=None, sea_size=1.0, clip=None, work=False,
         view="Standard", exposure=0.0):
    """kind: clay (one grey material), zebra (mirror hull in a striped world), paint (the model's own materials).
    rudder: the rudder's turn for this shot, degrees (positive: trailing edge to starboard). upto: the last slice whose
    objects show. boom: the boom's swing, degrees (positive: to starboard); pole: the pole's set from the bow (positive:
    to starboard; "stowed" on deck). tack: which side the runners are set on (slice 5). suit: the sails set (slice 6),
    with the boom and the pole posed as the suit has them. clip: the camera's near clip (a cut through the model, for
    the sections below); work: slice 9's work lights on below. view, exposure: the colour management's view transform
    and exposure (stops); the earlier slices' shots keep Standard at 0."""
    if ONLY and name not in ONLY:
        return
    if suit is not None:
        boom = -SUITS[suit]["boom_deg"]
        pole = "stowed" if SUITS[suit].get("pole") == "stowed" else SUITS[suit]["pole_deg"]
    for o in meshes:
        o.hide_render = not shown(o, upto, tack, suit)
    turn_rudder(rudder)
    swing_boom(boom)
    set_pole(pole)
    world_kind("zebra" if kind == "zebra" else "shade")
    WN.nodes["Background"].inputs[1].default_value = 0.55 if kind == "paint" else 1.0
    set_sun(sun_dir or (0.3, 0.5, -0.8), sun if kind == "paint" else 0.0)
    set_water(sea, sea_size)
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
    cd.clip_start, cd.clip_end = clip or 0.05, 6000
    for lo in WORK:
        lo.hide_render = not work
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    else:
        cd.type, cd.lens = "PERSP", lens
    SC.cycles.samples = samples
    SC.cycles.max_bounces = 2 if kind == "zebra" else 3
    SC.view_settings.view_transform, SC.view_settings.look, SC.view_settings.exposure = view, "None", exposure
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
# slice 5: the standing rigging and the runners, sailed on starboard tack (the wind from starboard: the starboard runner
# and checkstay set, the port pair let off and lashed to the aftermost shroud, the boom to port) unless a shot says
# otherwise. Blender's +Y is port. The chainplates are abreast the mast at x 2.9 to 3.3, y 3.15 out; the lower
# spreaders' tips at z 12.0; the hounds at z 37.6; the backstay's crane at z 47.4; its chainplate at x -20.8.
shot("rigging_profile", "paint", (MIDA.x, -150, MIDA.z), MIDA, ortho=1.05 * max(HIA.x - LOA.x, HA * ASPECT),
     sun_dir=RSUN, sun=3.0, upto=5, boom=-15.0)
shot("rigging_ahead", "paint", (150, 0, MIDA.z), (0, 0, MIDA.z), ortho=1.05 * HA * ASPECT, sun_dir=(-0.6, 0.3, -0.75),
     sun=3.0, upto=5, boom=-15.0)
shot("rigging_afloat34", "paint", (46.0, -54.0, 5.0), (-1.0, 0.0, 22.0), lens=24, sea=True, sun_dir=RSUN, sun=3.0,
     samples=48, upto=5, boom=-25.0)
shot("rigging_hounds", "paint", (-3.6, -6.6, 39.9), (2.0, 0.0, 37.6), lens=85, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5)
shot("rigging_tip", "paint", (5.4, -5.6, 13.1), (2.73, -2.93, 11.95), lens=110, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5)
shot("rigging_chainplates", "paint", (6.6, -5.8, 3.2), (3.05, -3.1, 1.8), lens=35, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5)
shot("rigging_lashing", "paint", (5.0, 5.0, 3.4), (2.8, 3.1, 2.5), lens=35, sun_dir=(-0.35, -0.5, -0.8), sun=3.0,
     samples=64, upto=5, boom=-25.0)
shot("rigging_tackle", "paint", (-9.4, -5.3, 3.7), (-12.3, -2.43, 2.0), lens=35, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5, boom=-25.0)
shot("rigging_masthead", "paint", (-4.2, -4.8, 49.8), (1.6, 0.0, 47.2), lens=70, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5)
shot("rigging_jumpers", "paint", (10.5, -7.5, 40.5), (3.0, -0.2, 38.8), lens=30, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5)
shot("rigging_counter", "paint", (-17.3, -2.9, 3.6), (-20.6, 0.0, 2.3), lens=35, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5, boom=-25.0)
shot("rigging_stemhead", "paint", (15.5, -2.9, 3.7), (18.6, 0.0, 2.7), lens=35, sun_dir=RSUN, sun=3.0, samples=64,
     upto=5)
# the boom squared off to port (85 degrees) past the let-off runner and checkstay, seen from aft on the port side
shot("rigging_boom_lee", "paint", (-4.6, 7.6, 4.3), (2.6, 3.2, 2.6), lens=30, sun_dir=(-0.35, -0.5, -0.8), sun=3.0,
     samples=64, upto=5, boom=-85.0)
# running on starboard tack (the boom squared off to port, the pole to starboard) and on port tack (the other way)
shot("rigging_run", "paint", (-62.0, -9.0, 46.0), (-5.0, 0.0, 2.0), lens=38, sun_dir=RSUN, sun=3.0, samples=48, upto=5,
     boom=-80.0, pole=85.0)
shot("rigging_run_port", "paint", (-62.0, -9.0, 46.0), (-5.0, 0.0, 2.0), lens=38, sun_dir=RSUN, sun=3.0, samples=48,
     upto=5, boom=80.0, pole=-85.0, tack="port")
# slice 6: the sails, sailed on starboard tack (the wind from starboard: the sails to port, Blender's +Y) under each
# suit, and stowed. Milestone A's silhouettes are from 200 m on a sea that reaches past the horizon, a 50 mm lens at
# 3 m above the water: under main and genoa from the lee bow, abeam to leeward and to windward; under main and
# quadrilateral jib with the staysail; under the spinnaker from the bow and abeam.
LEE_SUN = (-0.35, -0.5, -0.8)            # from the port bow: lights the sails' lee (convex) faces seen from port
WW_SUN = (-0.35, 0.5, -0.8)              # from the starboard bow: their windward faces, and backlights the lee side
far = dict(lens=50, sea=True, sea_size=30.0, samples=48, upto=6)
shot("sails_200m_genoa", "paint", (110.0, 167.0, 3.0), (0.0, 0.0, 19.0), suit="Genoa", sun_dir=LEE_SUN, sun=3.0, **far)
shot("sails_200m_genoa_abeam", "paint", (-1.0, 200.0, 3.0), (-1.0, 0.0, 21.0), suit="Genoa", sun_dir=LEE_SUN, sun=3.0,
     **far)
shot("sails_200m_genoa_windward", "paint", (-1.0, -200.0, 3.0), (-1.0, 0.0, 21.0), suit="Genoa", sun_dir=WW_SUN,
     sun=3.0, **far)
shot("sails_200m_quad", "paint", (110.0, 167.0, 3.0), (0.0, 0.0, 19.0), suit="Quadrilateral", sun_dir=LEE_SUN, sun=3.0,
     **far)
shot("sails_200m_spin", "paint", (185.0, 76.0, 3.0), (6.0, 0.0, 21.0), suit="Spinnaker", sun_dir=(-0.6, -0.3, -0.75),
     sun=3.0, **far)
shot("sails_200m_spin_abeam", "paint", (2.0, 200.0, 3.0), (2.0, 0.0, 21.0), suit="Spinnaker", sun_dir=LEE_SUN, sun=3.0,
     **far)
# nearer: the profile (orthographic, from starboard), the lee quarter, against the light, each suit three-quarters
shot("sails_profile", "paint", (MIDA.x, -150, MIDA.z), MIDA, ortho=1.05 * max(HIA.x - LOA.x, HA * ASPECT), sun_dir=WW_SUN,
     sun=3.0, upto=6, suit="Genoa")
shot("sails_lee34", "paint", (-42.0, 58.0, 12.0), (1.0, 0.0, 19.0), lens=30, sea=True, sun_dir=LEE_SUN, sun=3.0,
     samples=48, upto=6, suit="Genoa")
shot("sails_backlit", "paint", (-26.0, 44.0, 3.0), (-2.0, 0.0, 19.0), lens=24, sea=True, sun_dir=(0.15, 0.5, -0.7),
     sun=4.0, samples=64, upto=6, suit="Genoa")
shot("sails_quad34", "paint", (60.0, 70.0, 10.0), (2.0, 0.0, 17.0), lens=30, sea=True, sun_dir=LEE_SUN, sun=3.0,
     samples=48, upto=6, suit="Quadrilateral")
shot("sails_spin34", "paint", (80.0, 48.0, 8.0), (4.0, 0.0, 21.0), lens=30, sea=True, sun_dir=(-0.6, -0.3, -0.75),
     sun=3.0, samples=48, upto=6, suit="Spinnaker")
# close to: the mainsail's head and headboard, its clew at the boom's end, its luff's slides and reef bands, the
# genoa's hanks at the tack, the spinnaker's head; then stowed: moored (the main flaked under its ties, the bags on
# deck), lowered (the main on the boom with its slides stacked, the jibs hauled down still hanked on)
shot("sails_head", "paint", (-1.0, 10.0, 46.0), (1.5, 0.2, 45.4), lens=50, sun_dir=LEE_SUN, sun=3.0, samples=64,
     upto=6, suit="Genoa")
shot("sails_clew", "paint", (-9.5, 8.5, 8.5), (-16.0, 1.3, 6.3), lens=30, sun_dir=LEE_SUN, sun=3.0, samples=64,
     upto=6, suit="Genoa")
shot("sails_luff", "paint", (-5.0, -7.0, 7.0), (1.5, 0.3, 8.5), lens=30, sun_dir=WW_SUN, sun=3.0, samples=64, upto=6,
     suit="Genoa")
shot("sails_hanks", "paint", (16.0, -2.2, 5.5), (17.6, 0.0, 5.0), lens=35, sun_dir=WW_SUN, sun=3.0, samples=64, upto=6,
     suit="Genoa")
shot("sails_genoa_clew", "paint", (-0.5, 7.5, 4.5), (-3.5, 3.0, 3.0), lens=35, sun_dir=LEE_SUN, sun=3.0, samples=64,
     upto=6, suit="Genoa")
shot("sails_spin_head", "paint", (9.0, 7.0, 46.0), (2.7, 0.0, 45.6), lens=50, sun_dir=(-0.6, -0.3, -0.75), sun=3.0,
     samples=64, upto=6, suit="Spinnaker")
shot("sails_moored", "paint", (-7.0, -15.0, 13.0), (1.0, 0.0, 3.0), lens=28, sun_dir=WW_SUN, sun=3.0, samples=48,
     upto=6, suit="Moored")
shot("sails_lowered", "paint", (21.0, 12.0, 10.0), (5.0, 0.0, 2.6), lens=28, sun_dir=LEE_SUN, sun=3.0, samples=48,
     upto=6, suit="Lowered")
shot("sails_stack", "paint", (-1.0, 5.5, 6.5), (2.4, 0.0, 6.2), lens=24, sun_dir=LEE_SUN, sun=3.0, samples=64, upto=6,
     suit="Lowered")
# slice 7: the winches and running rigging under each suit on starboard tack (the sheets to port, Blender's +Y); the
# coils lie where the build found room for them
run = dict(sun_dir=LEE_SUN, sun=3.0, samples=64, upto=7)
shot("running_afterdeck", "paint", (-25.0, 9.0, 8.0), (-10.0, 0.5, 1.6), lens=28, suit="Genoa", **run)
shot("running_primary", "paint", (-6.6, 3.3, 2.6), (-8.1, 2.1, 1.75), lens=35, suit="Genoa", **run)
shot("running_mainsheet", "paint", (-20.5, 3.5, 4.0), (-15.5, 0.2, 2.6), lens=28, suit="Genoa", **run)
shot("running_runner", "paint", (-10.5, -5.0, 3.2), (-12.6, -1.8, 1.8), lens=30, suit="Genoa",
     **dict(run, sun_dir=WW_SUN))
shot("running_mast_foot", "paint", (6.5, 2.8, 3.2), (2.9, 0.0, 1.8), lens=28, suit="Genoa", **run)
shot("running_reel", "paint", (0.6, 2.1, 2.5), (2.2, 0.55, 1.85), lens=40, suit="Genoa", **run)
shot("running_masthead", "paint", (-1.0, 8.0, 47.2), (1.65, 0.0, 46.85), lens=70, suit="Genoa", **run)
shot("running_genoa_lead", "paint", (-3.0, 6.0, 4.0), (-6.5, 2.9, 1.9), lens=30, suit="Genoa", **run)
shot("running_quad", "paint", (-14.0, 8.0, 9.0), (-3.0, 1.8, 2.0), lens=28, suit="Quadrilateral", **run)
shot("running_spin34", "paint", (-14.0, -14.0, 14.0), (3.0, -6.0, 2.5), lens=28, suit="Spinnaker",
     **dict(run, sun_dir=WW_SUN))
shot("running_pole_end", "paint", (5.0, -16.5, 4.6), (8.5, -14.1, 3.7), lens=50, suit="Spinnaker",
     **dict(run, sun_dir=WW_SUN))
shot("running_spin_quarter", "paint", (-24.0, 10.0, 7.0), (-13.0, 2.0, 2.0), lens=28, suit="Spinnaker", **run)
shot("running_moored", "paint", (-26.0, -9.0, 10.0), (-8.0, 0.0, 4.0), lens=28, suit="Moored",
     **dict(run, sun_dir=WW_SUN))
shot("running_profile", "paint", (MIDA.x, -150, MIDA.z), MIDA, ortho=1.05 * max(HIA.x - LOA.x, HA * ASPECT),
     sun_dir=WW_SUN, sun=3.0, upto=7, suit="Genoa")
# the part loop's views: an idle capstan (the starboard mainsheet winch, free on starboard tack) and an idle reel (the
# topping lift's, its wire wound on)
shot("running_capstan", "paint", (-14.2, -2.15, 2.7), (-15.6, -0.85, 1.98), lens=50, suit="Genoa",
     **dict(run, sun_dir=WW_SUN))
shot("running_reel_close", "paint", (1.05, -1.5, 2.3), (2.0, -0.66, 1.72), lens=60, suit="Genoa",
     **dict(run, sun_dir=WW_SUN))
# slice 8: the deck hardware; moored (the sails bagged, the cowls up, the ensign flying) for the foredeck, the bow and a
# cowl, sailing in the genoa's suit for a capped cowl flange, the deck prisms, the side lights, the sheet track and the
# burgee, and lowered (the ensign's staff unshipped) for the counter
hw = dict(sun_dir=WW_SUN, sun=3.0, samples=64, upto=8)
AFT_SUN = (0.55, 0.4, -0.75)              # from the starboard quarter, for the views from aft
AFT_SUN_PORT = (0.55, -0.4, -0.75)        # from the port quarter
shot("hardware_foredeck", "paint", (24.0, -7.0, 9.0), (12.0, 0.0, 2.0), lens=30, suit="Moored", **hw)
shot("hardware_profile", "paint", (MIDH.x, -150, MIDH.z), MIDH,
     ortho=1.05 * max(HIH.x - LOH.x, (HIH.z - LOH.z) * ASPECT), sun_dir=WW_SUN, sun=3.0, upto=8, suit="Moored")
shot("hardware_stem_head", "paint", (19.9, -1.1, 3.0), (18.55, 0.0, 2.42), lens=50, suit="Moored", **hw)
shot("hardware_bow_cleat", "paint", (15.2, -2.9, 3.2), (16.75, -1.4, 2.15), lens=40, suit="Moored", **hw)
shot("hardware_anchor", "paint", (12.6, 3.4, 3.4), (14.75, 1.22, 1.97), lens=35, suit="Moored",
     **dict(hw, sun_dir=AFT_SUN_PORT))
shot("hardware_cowl", "paint", (-6.0, -2.6, 2.5), (-3.55, -0.85, 1.65), lens=45, suit="Moored",
     **dict(hw, sun_dir=AFT_SUN))
shot("hardware_cowl_capped", "paint", (-5.0, -2.0, 2.2), (-3.55, -0.85, 1.6), lens=55, suit="Genoa",
     **dict(hw, sun_dir=AFT_SUN))
shot("hardware_deck_prism", "paint", (7.4, -1.5, 2.4), (8.3, -0.75, 1.59), lens=60, suit="Genoa", **hw)
shot("hardware_sidelight", "paint", (6.5, -5.4, 2.4), (4.6, -2.95, 1.6), lens=45, suit="Genoa", **hw)
shot("hardware_sidelight_port", "paint", (6.5, 5.4, 2.4), (4.6, 2.95, 1.6), lens=45, suit="Genoa",
     **dict(hw, sun_dir=LEE_SUN))
shot("hardware_track", "paint", (-9.0, 1.2, 2.9), (-6.9, 2.95, 1.38), lens=45, suit="Genoa", **hw)
shot("hardware_stern", "paint", (-25.0, -4.0, 3.6), (-21.0, 0.0, 2.4), lens=40, suit="Lowered",
     **dict(hw, sun_dir=AFT_SUN))
shot("hardware_ensign", "paint", (-30.0, -12.0, 5.5), (-22.6, 0.0, 3.7), lens=35, suit="Moored",
     **dict(hw, sun_dir=AFT_SUN))
shot("hardware_burgee", "paint", (-3.5, -9.0, 49.3), (1.5, 0.3, 48.6), lens=70, suit="Genoa", **hw)
# slice 9: below decks forward, moored (the sails bagged), by the work lights; Blender's y is the hull's turned over,
# so the port side is +y here
bl = dict(sun_dir=WW_SUN, sun=1.5, samples=96, upto=9, suit="Moored", work=True, view="AgX")
CUT = 1.25                                     # the plan's cut, under every beam (the galley's lowest is at 1.32)
shot("below_plan", "paint", (9.1, 0.0, CUT + 40.0), (9.1, 0.0, 0.0), ortho=16.4, clip=40.0, **bl)
shot("below_half_port", "paint", (9.1, -40.0, 0.6), (9.1, 0.0, 0.6), ortho=16.4, clip=40.0, **bl)
shot("below_half_starboard", "paint", (9.1, 40.0, 0.6), (9.1, 0.0, 0.6), ortho=16.4, clip=40.0, **bl)
shot("below_forepeak_section", "paint", (15.0, -40.0, 1.45), (15.0, 0.0, 1.45), ortho=3.9, clip=40.21, **bl)
shot("below_fcsl_forward", "paint", (5.15, 0.0, 1.15), (8.6, 0.0, 0.35), lens=16, **bl)
shot("below_fcsl_aft", "paint", (8.35, -0.25, 1.15), (5.0, 0.35, 0.3), lens=16, **bl)
shot("below_galley", "paint", (4.55, -0.35, 1.0), (2.7, 2.0, 0.3), lens=18, **bl)
shot("below_galley_bins", "paint", (4.55, 0.3, 1.0), (2.8, -1.9, -0.1), lens=18, **bl)
shot("below_sail_locker", "paint", (8.8, 0.0, 1.25), (11.2, 0.0, 0.35), lens=16, **bl)
shot("below_washroom", "paint", (11.45, 0.1, 1.6), (13.35, -0.15, 0.75), lens=16, **bl)
shot("below_forepeak", "paint", (13.55, -0.35, 1.6), (15.2, 0.25, 1.15), lens=18, **bl)
shot("below_cot", "paint", (6.0, -0.9, 0.85), (5.45, -1.9, 0.35), lens=24, **bl)
shot("below_range", "paint", (3.75, 1.15, 0.95), (3.1, 2.25, 0.3), lens=24, **bl)
shot("below_windlass", "paint", (14.3, -0.55, 1.62), (14.95, 0.2, 1.3), lens=24, **bl)
deckv = dict(sun_dir=WW_SUN, sun=3.0, samples=64, upto=9, suit="Moored")
shot("below_bow_chock", "paint", (17.25, 1.2, 2.78), (17.69, 0.58, 2.37), lens=45, **deckv)
shot("below_cable_lead", "paint", (14.6, 0.15, 3.0), (16.6, 0.66, 2.15), lens=28, **deckv)
print("render_jclass: done")
