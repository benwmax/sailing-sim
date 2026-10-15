"""Renders the J/22 hero model in views matched to Bean's lesson photos (Cycles).

    blender -b -P render_j22_hero.py -- <j22_hero.blend> <out dir> [view ...]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
BLEND, OUT = ARGS[0], ARGS[1]
ONLY = ARGS[2:]
SAMPLES = int(os.environ.get("J22H_SAMPLES", "48"))
RES = os.environ.get("J22H_RES", "1280x720").split("x")
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = int(RES[0]), int(RES[1])
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.exposure = -0.9

# everything boat-side under one pivot so it can heel
pivot = bpy.data.objects.new("BoatPivot", None)
sc.collection.objects.link(pivot)
for o in list(sc.objects):
    if o is not pivot and o.parent is None:
        o.parent = pivot

world = bpy.data.worlds.new("World")
sc.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]


def set_sky(kind):
    for n in list(nt.nodes):
        if n.type not in ("BACKGROUND", "OUTPUT_WORLD"):
            nt.nodes.remove(n)
    for o in [o for o in sc.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    if kind == "overcast":
        # flat bright grey dome, brighter overhead
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.45
        ramp.color_ramp.elements[0].color = (0.42, 0.43, 0.45, 1)
        ramp.color_ramp.elements[1].position = 1.0
        ramp.color_ramp.elements[1].color = (1.05, 1.07, 1.10, 1)
        nt.links.new(sep.outputs["Z"], ramp.inputs[0])
        nt.links.new(ramp.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 1.6
    else:
        sky = nt.nodes.new("ShaderNodeTexSky")
        try:
            sky.sky_type = "NISHITA"
        except TypeError:
            pass
        sky.sun_elevation = math.radians(38)
        sky.sun_rotation = math.radians(200)
        nt.links.new(sky.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 0.25
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
        sun.data.energy = 3.0
        sun.data.angle = math.radians(0.6)
        sun.rotation_euler = (math.radians(52), 0, math.radians(200 + 90))
        sc.collection.objects.link(sun)


def water(on, rough=True):
    w = bpy.data.objects.get("Water")
    if not on:
        if w:
            w.hide_render = True
        return
    if not w:
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
        w = bpy.context.active_object
        w.name = "Water"
        w.location = (-132, -132, 0)
        oc = w.modifiers.new("ocean", "OCEAN")
        oc.geometry_mode = "GENERATE"
        oc.size, oc.spatial_size, oc.resolution = 1.0, 24, 16
        oc.wave_scale, oc.wind_velocity, oc.choppiness = 0.55, 7.0, 1.3
        oc.wave_alignment, oc.wave_direction = 0.3, math.radians(20)
        oc.repeat_x = oc.repeat_y = 12
        oc.use_foam, oc.foam_layer_name = True, "foam"
        oc.foam_coverage = 0.25
        m = bpy.data.materials.new("LakeWater")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.010, 0.020, 0.014, 1)
        b.inputs["Roughness"].default_value = 0.12
        b.inputs["IOR"].default_value = 1.333
        b.inputs["Transmission Weight"].default_value = 0.0
        m.diffuse_color = (0.02, 0.04, 0.03, 1)
        w.data.materials.append(m)
    w.hide_render = False


def look(cam, pos, tgt, lens):
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.sensor_width = 36

sails = bpy.data.collections.get("Sails")
rigging_sail = [o for o in sc.objects if o.name.startswith(("JibSheet", "Hank_"))]


def show_sails(on):
    if sails:
        for o in sails.objects:
            o.hide_render = not on
    for o in rigging_sail:
        o.hide_render = not on


# camera positions are the photo views solved by eye (photo name in brackets); fSpy solves come with the club shoot
VIEWS = {
    # [IMG_9224] on the lift, overcast, from the dock off the starboard bow
    "dock_bow": dict(sky="overcast", water=False, sails=False, heel=0, lift=0.45,
                     pos=(5.2, -3.6, 1.85), tgt=(0.2, 0.3, 0.9), lens=26),
    # [IMG_9273] from the forward cockpit looking aft at the tiller and outboard
    "cockpit_aft": dict(sky="sun", water=True, sails=True, heel=-8, lift=0.0,
                        pos=(-0.70, -0.35, 1.25), tgt=(-3.6, 0.45, 0.45), lens=16),
    # [IMG_9272] looking down over the leeward coaming
    "leeward_rail": dict(sky="sun", water=True, sails=True, heel=-14, lift=0.0,
                         pos=(-0.85, -0.25, 1.45), tgt=(-1.25, 1.35, 0.25), lens=18),
    # sailing three-quarter from off the bow, starboard tack
    "sailing": dict(sky="sun", water=True, sails=True, heel=-15, lift=0.0,
                    pos=(11.5, -9.0, 2.6), tgt=(0.0, 0.0, 3.2), lens=30),
    # profile, studio check of the hull and rig lines
    "profile": dict(sky="overcast", water=False, sails=True, heel=0, lift=0.0,
                    pos=(0.0, -22.0, 3.8), tgt=(0.0, 0.0, 3.8), lens=38),
    # cabin top and foredeck from above the stern quarter
    "deck_quarter": dict(sky="overcast", water=False, sails=False, heel=0, lift=0.0,
                         pos=(-5.6, -3.8, 3.4), tgt=(0.0, 0.0, 0.7), lens=28),
    # close-ups of the fine fittings
    "cu_gooseneck": dict(sky="sun", water=True, sails=True, heel=0, lift=0.0,
                         pos=(0.15, -0.95, 1.75), tgt=(0.88, 0.0, 1.42), lens=50),
    "cu_masthead": dict(sky="sun", water=True, sails=True, heel=0, lift=0.0,
                        pos=(0.25, -1.4, 9.0), tgt=(0.95, 0.0, 9.35), lens=50),
    "cu_shroud": dict(sky="sun", water=True, sails=False, heel=0, lift=0.0,
                      pos=(1.7, -1.9, 1.15), tgt=(0.9, -1.02, 0.85), lens=45),
    "cu_jibclew": dict(sky="sun", water=True, sails=True, heel=0, lift=0.0,
                       pos=(-0.1, 1.7, 1.35), tgt=(0.6, 0.8, 0.9), lens=38),
    "cu_cleats": dict(sky="sun", water=True, sails=True, heel=0, lift=0.0,
                      pos=(-0.55, 0.25, 1.1), tgt=(-1.3, -0.9, 0.5), lens=28),
    "cu_transom": dict(sky="sun", water=True, sails=False, heel=0, lift=0.0,
                       pos=(-5.2, 1.9, 1.25), tgt=(-3.3, 0.3, 0.5), lens=32),
}
for name, v in VIEWS.items():
    if ONLY and name not in ONLY:
        continue
    set_sky(v["sky"])
    water(v["water"])
    show_sails(v["sails"])
    pivot.rotation_euler = (math.radians(v["heel"]), 0, 0)
    pivot.location = (0, 0, v["lift"])
    look(cam, v["pos"], v["tgt"], v["lens"])
    sc.render.filepath = os.path.join(OUT, f"j22h_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)
