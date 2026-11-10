"""Shape loop, step 3 and 6: the fixed camera set (docs/shape-loop).

    python render_set.py <j22_hero.blend | fbx dir> <sections.json> <out dir> [--res 1600] [--with-other]

Renders the same views every round, so before and after line up pixel for pixel:
  sil_profile, sil_plan, sil_bow, sil_stern   orthographic silhouettes (black boat on white) for the outline check
  shade_profile, shade_plan, shade_34, shade_cockpit, shade_bow34, shade_stern34   grey clay under a soft sky
  zebra_34, zebra_profile, zebra_bow34          stripes reflected in the hull and deck: a fair surface shows smooth
                                                bands, a bump or flat bends or breaks them
Only the boat's shape sections are drawn (rig, sails, ropes, hardware and the interior are hidden) unless --with-other.
Cameras sit on the hull's own bounds, so a boat that grows keeps the same framing rule. Cycles on the CPU with a
material override (no GPU needed), no textures. Needs Blender's Python (pip bpy).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, SECTIONS, OUT = ARGS[0], ARGS[1], ARGS[2]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1600
OTHER = "--with-other" in ARGS
os.makedirs(OUT, exist_ok=True)
SC = C.load_scene(SRC)
SEC = C.load_sections(SECTIONS)
HULL = bpy.data.objects[SEC.get("hull_object", "Hull")]

for o in list(SC.objects):
    if o.type in ("MESH", "CURVE", "FONT"):
        hide = C.section_of(o.name, SEC) == "other" and not OTHER
        o.hide_render = hide
        o.hide_viewport = hide
    elif o.type in ("CAMERA", "LIGHT"):
        o.hide_render = True

pts = [HULL.matrix_world @ Vector(c) for c in HULL.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
mid = (lo + hi) / 2
size = hi - lo

sc = SC
# Cycles on the CPU: the cloud and CI have no GPU or EGL for Workbench. Few samples: shape, not looks.
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = True
sc.render.resolution_x = RES
sc.render.resolution_y = RES // 2
sc.render.film_transparent = False
sc.render.use_compositing = False   # the hero blend carries no compositor we want
sc.render.use_sequencer = False
sc.display_settings.display_device = "sRGB"
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
world = bpy.data.worlds.new("ShapeWorld")
sc.world = world
world.use_nodes = True
WN = world.node_tree
for n in list(WN.nodes):
    if n.type != "OUTPUT_WORLD":
        WN.nodes.remove(n)


def world_kind(kind):
    for n in list(WN.nodes):
        if n.type != "OUTPUT_WORLD":      # (bpy wrappers are not stable: compare types, never identity)
            WN.nodes.remove(n)
    out = [n for n in WN.nodes if n.type == "OUTPUT_WORLD"][0]
    bg = WN.nodes.new("ShaderNodeBackground")
    WN.links.new(bg.outputs[0], out.inputs[0])
    if kind == "sil":
        bg.inputs[0].default_value = (1, 1, 1, 1)
        bg.inputs[1].default_value = 1.0
    elif kind == "shade":
        # bright sky over a darker ground: soft clay light that shows form
        tc = WN.nodes.new("ShaderNodeTexCoord")
        sep = WN.nodes.new("ShaderNodeSeparateXYZ")
        ramp = WN.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.25, 0.25, 0.26, 1)
        ramp.color_ramp.elements[1].position = 0.75
        ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.02, 1)
        mr = WN.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
        WN.links.new(tc.outputs["Generated"], sep.inputs[0])
        WN.links.new(sep.outputs["Z"], mr.inputs["Value"])
        WN.links.new(mr.outputs[0], ramp.inputs[0])
        WN.links.new(ramp.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 1.0
    else:   # zebra: horizontal stripes all round the sky, reflected in a mirror-glossy boat
        tc = WN.nodes.new("ShaderNodeTexCoord")
        sep = WN.nodes.new("ShaderNodeSeparateXYZ")
        mul = WN.nodes.new("ShaderNodeMath")
        mul.operation, mul.inputs[1].default_value = "MULTIPLY", 22.0
        sn = WN.nodes.new("ShaderNodeMath")
        sn.operation = "SINE"
        gt = WN.nodes.new("ShaderNodeMath")
        gt.operation, gt.inputs[1].default_value = "GREATER_THAN", 0.0
        WN.links.new(tc.outputs["Generated"], sep.inputs[0])
        WN.links.new(sep.outputs["Z"], mul.inputs[0])
        WN.links.new(mul.outputs[0], sn.inputs[0])
        WN.links.new(sn.outputs[0], gt.inputs[0])
        WN.links.new(gt.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 1.0


def override(kind):
    m = bpy.data.materials.get("Shape_" + kind) or bpy.data.materials.new("Shape_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if kind == "sil":
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs[0].default_value = (0, 0, 0, 1)
        nt.links.new(e.outputs[0], out.inputs[0])
    elif kind == "shade":
        d = nt.nodes.new("ShaderNodeBsdfDiffuse")
        d.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
        nt.links.new(d.outputs[0], out.inputs[0])
    else:
        g = nt.nodes.new("ShaderNodeBsdfGlossy")
        g.inputs[0].default_value = (1, 1, 1, 1)
        g.inputs[1].default_value = 0.0
        nt.links.new(g.outputs[0], out.inputs[0])
    return m


cam_data = bpy.data.cameras.new("ShapeCam")
cam = bpy.data.objects.new("ShapeCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(loc, target, ortho=None, lens=35):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = "PERSP"
        cam_data.lens = lens
    cam_data.clip_start, cam_data.clip_end = 0.01, 200


def mode(kind):
    world_kind(kind)
    bpy.context.view_layer.material_override = override(kind)
    sc.cycles.samples = 1 if kind == "sil" else 24
    sc.cycles.max_bounces = 0 if kind == "sil" else (2 if kind == "zebra" else 3)


def shot(name, kind):
    mode(kind)
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


L = size.x * 1.08
far = 30.0
views = {
    "profile": ((mid.x, mid.y + far, mid.z), mid, L),            # port side, square on
    "plan": ((mid.x, mid.y, mid.z + far), mid, L),
    "bow": ((mid.x + far, mid.y, mid.z), mid, L / 2),
    "stern": ((mid.x - far, mid.y, mid.z), mid, L / 2),
}
for v, (loc, tgt, scale) in views.items():
    look(loc, tgt, ortho=scale)
    if v == "plan":
        cam.rotation_euler = (0, 0, 0)          # straight down, bow to the right as in the profile
    shot(f"sil_{v}", "sil")
    shot(f"shade_{v}", "shade")
    if v == "profile":
        shot("zebra_profile", "zebra")

persp = {
    "34": ((mid.x + size.x * 0.75, mid.y + size.x * 0.95, mid.z + size.x * 0.45), (mid.x, mid.y, mid.z + 0.2), 40),
    "bow34": ((hi.x + 1.6, mid.y + 1.9, mid.z + 1.0), (hi.x - 1.4, mid.y, mid.z + 0.4), 35),
    "stern34": ((lo.x - 1.8, mid.y + 1.9, mid.z + 1.2), (lo.x + 1.4, mid.y, mid.z + 0.4), 35),
    "cockpit": ((lo.x + 0.45, mid.y, hi.z + 0.75), (lo.x + 3.2, mid.y, hi.z + 0.10), 24),   # helm eye looking forward
}
for v, (loc, tgt, lens) in persp.items():
    look(loc, tgt, lens=lens)
    shot(f"shade_{v}", "shade")
    if v in ("34", "bow34"):
        shot(f"zebra_{v}", "zebra")
print("shapeloop render_set:", sorted(f for f in os.listdir(OUT) if f.endswith(".png") and not f.startswith("_")))
