"""The Catalina 22's light copy against the detailed boat (slice 9, docs/c22-10): the shots the J-Class's
light_compare.py measures (Tools/shipkit/jclass/light_compare.py, docs/jclass-12), and wireframes close to.

    blender -b -P render_light_c22.py -- <c22.blend with its twins> <out dir> [--only a,b]

Shots, under main and genoa (state Up, the boom swung to its angle), the cabin below left out of both as the game leaves
it out unless the camera is below:
  light_<dist>_<bearing>_{hero,light}      at a 4K screen's own pixels with the game's narrowest field of view (60
                                           degrees), from an eye 3 m over the water on her port side, abeam and 40
                                           degrees off the bow, 50 and 100 m from a point 4 m up her mast; cropped to the
                                           box round both boats, so a pair shares one frame
  light_<dist>_<bearing>_{hero,light}_id   the same, each material a flat colour, unlit (light_compare's outline and
                                           material test)
  light_noise                              light_100_abeam_hero again with another seed: the renderer's own noise
  light_wire_<view>_{hero,light}           clay with every triangle's edges a pixel wide, close to: quarter and mast_foot
Frame: Blender's (X forward, Y to port, Z up). Cycles on the CPU.
"""
import colorsys
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hardware_c22 as HC                              # noqa: E402
import rig_c22 as RC                                   # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
SC = bpy.context.scene
STATE, SAILS = "Up", ("Main_Set", "Genoa_Set")
ALT = ("C22_KeelUp", "C22_RudderUp", "C22_PopTopRaised", "C22_LidRailsRaised")
MESHES = [o for o in SC.objects if o.type == "MESH"]
for o in SC.objects:
    if o.type != "MESH":
        o.hide_render = True
TWIN = {o["light_of"]: o for o in MESHES if o.get("light_of") is not None}
if not TWIN:
    raise SystemExit(f"{SRC} has no light twins: run light_c22.py on it first")


def shown(o):
    """A detailed part shown in state Up from outside (light_c22.shown_in's rules, the cabin below left out)."""
    n = o.name
    if o.get("light_of") is not None or n.startswith("C22_Interior") or n in ALT:
        return False
    if n.startswith("C22_Sail_"):
        return n[len("C22_Sail_"):] in SAILS
    if n.startswith("C22_Lines_"):
        return n == "C22_Lines_" + STATE
    return True


HERO = [o for o in MESHES if shown(o)]
LIGHT = [TWIN.get(o.name, o) for o in HERO]
missing = [o.name for o in HERO if o.name not in TWIN]
if missing:
    print(f"render_light_c22: no twin for {missing} (drawn as they are in the light shots)")

# the boom swung to the state's angle, its twin with it
GX, _, GZ = RC.gooseneck()
piv = Vector((GX, 0.0, GZ))
swing = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-HC.BOOM_DEG["up"]), 4, "Z") @ Matrix.Translation(-piv)
for n in ("C22_Boom", "C22_Boom_Light"):
    if n in bpy.data.objects:
        bpy.data.objects[n].matrix_world = swing @ bpy.data.objects[n].matrix_world

SC.render.engine = "CYCLES"
SC.cycles.device = "CPU"
SC.cycles.max_bounces = 3
SC.render.use_compositing = SC.render.use_sequencer = False
SC.render.film_transparent = False
world = bpy.data.worlds.new("LtWorld")
SC.world = world
world.use_nodes = True
WN = world.node_tree
for n in list(WN.nodes):
    if n.type != "OUTPUT_WORLD":
        WN.nodes.remove(n)
wout = [n for n in WN.nodes if n.type == "OUTPUT_WORLD"][0]
bg, tc, sep, ramp, mr = (WN.nodes.new(t) for t in ("ShaderNodeBackground", "ShaderNodeTexCoord", "ShaderNodeSeparateXYZ",
                                                    "ShaderNodeValToRGB", "ShaderNodeMapRange"))
ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.35, (0.25, 0.27, 0.3, 1)
ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.75, (0.85, 0.9, 1.0, 1)
mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
WN.links.new(tc.outputs["Generated"], sep.inputs[0])
WN.links.new(sep.outputs["Z"], mr.inputs["Value"])
WN.links.new(mr.outputs[0], ramp.inputs[0])
WN.links.new(ramp.outputs[0], bg.inputs[0])
WN.links.new(bg.outputs[0], wout.inputs[0])

METAL = ("Stainless", "Aluminium", "Wire", "Lifeline", "Bronze", "Chrome")
ID = {}                                                # material -> (its shader's link, its flat id emission)
for k, m in enumerate(sorted({s.material for o in HERO + LIGHT for s in o.material_slots if s.material},
                             key=lambda m: m.name)):
    m.use_nodes = True
    nt = m.node_tree
    pb = nt.nodes.get("Principled BSDF")
    if pb:                                             # each slot's colour (build_c22.SLOT_RGB), metals a little shiny
        pb.inputs["Base Color"].default_value = m.diffuse_color
        metal = m.name.split(".")[0] in METAL
        pb.inputs["Roughness"].default_value = 0.35 if metal else 0.7
        pb.inputs["Metallic"].default_value = 0.6 if metal else 0.0
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
    em = nt.nodes.new("ShaderNodeEmission")
    h = (k * 0.6180339887) % 1.0                       # well-spread hues, two lightnesses
    em.inputs[0].default_value = (*colorsys.hsv_to_rgb(h, 0.9, 1.0 if k % 2 else 0.6), 1)
    ID[m.name] = (src, em, out)


def ids_mode(on):
    for src, em, out in ID.values():
        nt = out.id_data
        for l in list(out.inputs["Surface"].links):
            nt.links.remove(l)
        if on:
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        elif src is not None:
            nt.links.new(src, out.inputs["Surface"])


def wire_material():
    m = bpy.data.materials.new("LtWire")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
    e = nt.nodes.new("ShaderNodeBsdfDiffuse")
    e.inputs[0].default_value = (0.03, 0.05, 0.12, 1)
    w = nt.nodes.new("ShaderNodeWireframe")
    w.use_pixel_size, w.inputs[0].default_value = True, 1.0
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(w.outputs[0], mx.inputs[0])
    nt.links.new(d.outputs[0], mx.inputs[1])
    nt.links.new(e.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    return m


WIRE = wire_material()
sun_d = bpy.data.lights.new("LtSun", "SUN")
sun_d.energy, sun_d.angle = 3.0, math.radians(3.0)
sun = bpy.data.objects.new("LtSun", sun_d)
SC.collection.objects.link(sun)
sun.rotation_euler = Vector((0.5, 0.55, 0.67)).to_track_quat("Z", "Y").to_euler()
cd = bpy.data.cameras.new("LtCam")
cam = bpy.data.objects.new("LtCam", cd)
SC.collection.objects.link(cam)
SC.camera = cam


def shot(name, eye, target, light, fov=None, lens=35, res=(3840, 2160), crop=False, ids=False, wire=False, seed=0,
         samples=48):
    if ONLY and not any(name.startswith(p) for p in ONLY):
        return
    for o in MESHES:
        o.hide_render = True
    for o in (LIGHT if light else HERO):
        o.hide_render = False
    cam.location = eye
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    cd.type, cd.clip_start, cd.clip_end = "PERSP", 0.05, 2000.0
    cd.sensor_fit, cd.sensor_width = "HORIZONTAL", 36.0
    cd.lens = 18.0 / math.tan(math.radians(fov) / 2) if fov else lens
    SC.render.resolution_x, SC.render.resolution_y = res
    SC.render.use_border = SC.render.use_crop_to_border = crop
    if crop:                                           # the box round both boats: a pair shares one frame
        bpy.context.view_layer.update()
        pts = [world_to_camera_view(SC, cam, o.matrix_world @ Vector(c)) for o in HERO + LIGHT for c in o.bound_box]
        pad = 0.01
        SC.render.border_min_x = max(0.0, min(p.x for p in pts) - pad)
        SC.render.border_max_x = min(1.0, max(p.x for p in pts) + pad)
        SC.render.border_min_y = max(0.0, min(p.y for p in pts) - pad)
        SC.render.border_max_y = min(1.0, max(p.y for p in pts) + pad)
    ids_mode(ids)
    bpy.context.view_layer.material_override = WIRE if wire else None
    bg.inputs[1].default_value = 0.0 if ids else 1.0
    sun.hide_render = ids
    SC.cycles.seed = seed
    SC.cycles.samples = 1 if ids else samples
    SC.cycles.use_denoising = not ids
    SC.render.filter_size = 0.01 if ids else 1.5     # an id pixel is one material, not a blend at the edges
    SC.render.dither_intensity = 0.0 if ids else 1.0
    SC.view_settings.view_transform = "Standard"
    SC.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    ids_mode(False)


AIM = Vector((RC.MAST_X, 0.0, 4.0))
for dist in (50, 100):
    for bname, deg in (("abeam", 90.0), ("bow", 40.0)):
        a = math.radians(deg)
        eye = (AIM.x + dist * math.cos(a), dist * math.sin(a), 3.0)
        for which in ("hero", "light"):
            kw = dict(fov=60.0, crop=True, light=which == "light")
            shot(f"light_{dist}_{bname}_{which}", eye, AIM, **kw)
            shot(f"light_{dist}_{bname}_{which}_id", eye, AIM, ids=True, **kw)
        if dist == 100 and bname == "abeam":
            shot("light_noise", eye, AIM, fov=60.0, crop=True, light=False, seed=7)
for vname, eye, target, lens in (("quarter", (-5.5, 4.8, 3.2), (0.2, 0.0, 1.0), 30),
                                 ("mast_foot", (3.4, 2.0, 2.4), (1.0, 0.0, 1.3), 28)):
    for which in ("hero", "light"):
        shot(f"light_wire_{vname}_{which}", eye, target, light=which == "light", lens=lens, res=(1200, 800), wire=True,
             samples=16)
print("render_light_c22: done")
