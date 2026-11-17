"""The Catalina 22's wear views (docs/c22-9): a built c22.blend dressed by weathering_c22.py and rendered at each of the
texture loop's five levels, for the ladders, the blind rounds and wear_check_c22.py.

    blender -b -P render_wear_c22.py -- <c22.blend> <out dir> [--res 900] [--samples 32] [--only a,b] [--levels L0,L4]
        [--no-measure]

Writes, for each view and level, wear_<view>_<level>.png (lit), wear_<view>_<level>_albedo.png (each material's colour
alone, no light: what the checks measure) and wear_<view>_id.png (each dressed material in its own flat colour) with
wear_ids.json naming them. --no-measure skips the albedo and id passes.

Views (Blender's frame: X forward, Y to port, Z up from the design waterline):
  hull       the port topsides amidships from a dinghy alongside: gelcoat, the lake's line, the bottom paint, rubrail
  bottom     low on the port bow, under the waterline: the bottom paint, the keel stub and the swing keel
  deck       over the port side deck by the cabin: non-skid, deck gelcoat, ports, handrails, stainless, chainplates
  cockpit    from astern and up: the tiller, the drop boards, the seats' non-skid, the winches and the sail cover
  poptop     the pop-top raised, from the starboard bow: its canvas skirt, the trunk and its ports
  saloon     the cabin from high on the starboard quarter, deck and trunk off: sole, dinette, galley, liner, joinery
  vberth     under the raised pop-top looking forward: the V-berth, its curtain, the headliner, the bulkhead
  aft        from the V-berth's doorway looking aft: the headliner, the quarter berth, the step and the galley
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weathering_c22 as WC  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 900
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else 32
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
LEVELS = ARGS[ARGS.index("--levels") + 1].split(",") if "--levels" in ARGS else list(WC.LEVELS)
MEASURE = "--no-measure" not in ARGS
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
for o in sc.objects:
    if o.type not in ("MESH", "CURVE"):
        o.hide_render = True
OB = {o.name: o for o in sc.objects}
START = {o.name: o.hide_render for o in sc.objects}
DRESSED = WC.dress("L0")
ids = {str(k): m.name for k, m in enumerate(WC.dressed(), 1)}
json.dump(ids, open(os.path.join(OUT, "wear_ids.json"), "w"), indent=1)
json.dump(WC.report(WC.used_materials()), open(os.path.join(OUT, "wear_report.json"), "w"), indent=1)

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.render.use_compositing = sc.render.use_sequencer = False
sc.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("WearWorld")
sc.world = world
world.use_nodes = True
WN = world.node_tree
bg = WN.nodes.get("Background")
bg.inputs[0].default_value = (0.62, 0.66, 0.72, 1)        # an overcast-to-hazy Texas sky
bg.inputs[1].default_value = 1.0


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


SUN = light("WearSun", "SUN", (0, 0, 10), 3.5, rot=(0.45, 0.55, 0.7))
INSIDE = [light("WearDome", "POINT", (0.1, 0.0, 1.05), 14.0, 0.08), light("WearVBerth", "POINT", (1.9, 0.0, 0.7), 6.0, 0.06),
          light("WearQuarter", "POINT", (-1.2, -0.45, 0.33), 2.5, 0.05),
          light("WearGalley", "POINT", (-0.7, 0.5, 0.3), 2.0, 0.05)]
cd = bpy.data.cameras.new("WearCam")
cam = bpy.data.objects.new("WearCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
OUTSIDE = ("C22_Deck", "C22_Cabin", "C22_PopTop", "C22_PopTopRaised", "C22_LidRails", "C22_LidRailsRaised",
           "C22_Interior_Headliner", "C22_ForeHatch", "C22_Ports", "C22_DropBoards", "C22_Hardware", "C22_Lifelines",
           "C22_MastHardware", "C22_Halyards", "C22_Mast", "C22_Boom", "C22_Wires", "C22_RigFittings",
           "C22_Sail_Main_Covered", "C22_Lines_Rest", "C22_Rubrail", "C22_Well")


def setup(hide=(), raised=False, galley_out=False, inside=False):
    for n, o in OB.items():
        if o.type in ("MESH", "CURVE"):
            o.hide_render = START.get(n, False)
    for n in hide:
        if n in OB:
            OB[n].hide_render = True
    for n, up in (("C22_PopTop", False), ("C22_PopTopRaised", True), ("C22_LidRails", False),
                  ("C22_LidRailsRaised", True)):
        if n in OB and n not in hide:
            OB[n].hide_render = raised != up
    for n, out in (("C22_Interior_Galley", False), ("C22_Interior_GalleyOut", True)):
        if n in OB:
            OB[n].hide_render = galley_out != out
    for li in INSIDE:
        li.hide_render = not inside


VIEWS = {
    "hull": (dict(), (0.4, 3.0, 0.3), (0.2, 0.0, 0.15), 35),
    "bottom": (dict(), (2.2, 2.6, -1.1), (0.4, 0.0, -0.55), 30),
    "deck": (dict(), (1.7, 1.7, 2.15), (0.6, 0.35, 0.85), 30),
    "cockpit": (dict(), (-4.2, -0.7, 2.0), (-1.6, 0.0, 0.55), 32),
    "poptop": (dict(raised=True), (2.3, -2.1, 2.0), (0.0, 0.0, 1.3), 32),
    "saloon": (dict(hide=OUTSIDE, inside=True), (-2.2, -2.1, 2.9), (0.3, 0.15, 0.0), 28),
    "vberth": (dict(raised=True, inside=True), (-0.6, 0.0, 1.45), (2.0, 0.0, 0.35), 14),
    "aft": (dict(raised=True, galley_out=True, inside=True), (0.72, -0.18, 0.95), (-1.6, 0.05, 0.15), 14),
}


def frame(loc, target, lens):
    sc.render.resolution_x, sc.render.resolution_y = RES, RES * 2 // 3
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.type, cd.lens = "PERSP", lens
    cd.clip_start, cd.clip_end = 0.01, 1000


def render(path, samples):
    sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


for view, (state, loc, target, lens) in VIEWS.items():
    if ONLY and view not in ONLY:
        continue
    setup(**state)
    frame(loc, target, lens)
    if MEASURE:
        WC.albedo_mode("id")
        sc.cycles.use_denoising = False
        sc.view_settings.view_transform = "Standard"
        render(os.path.join(OUT, f"wear_{view}_id.png"), 1)
    for lv in LEVELS:
        WC.apply_level(lv)
        if MEASURE:
            WC.albedo_mode("albedo")
            render(os.path.join(OUT, f"wear_{view}_{lv}_albedo.png"), 4)
        WC.albedo_mode(False)
        sc.cycles.use_denoising = True
        sc.view_settings.view_transform = "AgX"
        render(os.path.join(OUT, f"wear_{view}_{lv}.png"), SAMPLES)
        sc.cycles.use_denoising = False
        sc.view_settings.view_transform = "Standard"
print("wear views written to", OUT)
