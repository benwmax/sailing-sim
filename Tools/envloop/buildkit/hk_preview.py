"""Preview materials and lighting for the building kit's review renders (Blender only; the game's materials are built
in Unreal by the integration step after Nov 21, and the wall, roof and glass looks are the materials thread's).

  setup_materials(palette, trim_dir)   Trim reads the trim sheet (colour, normal, cavity/roughness/paint/alpha) and
                                        multiplies the paint role's colour (vertex colour R) where the sheet's paint
                                        mask is 1. Glass is a dark reflective pane with a dim room tone. Wall and Roof
                                        draw a stand-in pattern per finish id (vertex colour G) at the size card's
                                        dimensions: courses and joints line up, the surfaces are flat colour.
  light(kind)                           "midday", "low" (8 deg sun, warm), "overcast"
"""
import math
import os

import bpy

import hk_core as K

WALL_PREVIEW = {   # finish id: (base colour, joint colour, pattern)
    0: ((0.36, 0.13, 0.08), (0.55, 0.53, 0.50), "brick"),
    1: ((0.28, 0.15, 0.09), (0.50, 0.48, 0.45), "brick"),
    2: ((0.62, 0.50, 0.36), (0.66, 0.63, 0.58), "brick"),
    3: ((0.70, 0.64, 0.53), (0.60, 0.57, 0.52), "stone"),
    4: ((0.80, 0.80, 0.78), (0.0, 0.0, 0.0), "lap"),
    5: ((0.80, 0.80, 0.78), (0.0, 0.0, 0.0), "batten"),
    6: ((0.80, 0.76, 0.68), (0.0, 0.0, 0.0), "stucco"),
}
ROOF_PREVIEW = {0: (0.24, 0.21, 0.18), 1: (0.11, 0.11, 0.115), 2: (0.20, 0.15, 0.11), 3: (0.30, 0.31, 0.32)}


def _hex(c):
    c = c.lstrip("#")
    srgb = [int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb) + (1.0,)


def _nodes(m):
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return nt, bsdf, out


def _ramp(nt, src, stops, constant=True):
    """Pick a colour by thresholds: stops [(pos, rgba)] sorted, the first at 0; the result is the last stop whose pos
    is at or below src. Built from compare and mix nodes (exact, unlike a constant colour ramp near its stops)."""
    first = nt.nodes.new("ShaderNodeRGB")
    first.outputs[0].default_value = stops[0][1]
    cur = first.outputs[0]
    for pos, c in stops[1:]:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = c
        cmp_ = nt.nodes.new("ShaderNodeMath")
        cmp_.operation = "GREATER_THAN"
        nt.links.new(src, cmp_.inputs[0])
        cmp_.inputs[1].default_value = pos
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        nt.links.new(cmp_.outputs[0], mx.inputs["Factor"])
        nt.links.new(cur, mx.inputs[6])
        nt.links.new(rgb.outputs[0], mx.inputs[7])
        cur = mx.outputs[2]

    class _R:
        outputs = {"Color": cur}
    return _R()


def _math(nt, op, a, b=None, val=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    if val is not None:
        n.inputs[1].default_value = val
    return n.outputs[0]


def trim_material(palette, trim_dir):
    m = K.mat("Trim")
    nt, bsdf, out = _nodes(m)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    tex = {}
    for key, cs in (("C", "sRGB"), ("N", "Non-Color"), ("M", "Non-Color")):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(os.path.join(trim_dir, f"T_HouseTrim_{key}.png"), check_existing=True)
        t.image.colorspace_settings.name = cs
        t.interpolation = "Cubic"
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
        tex[key] = t
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tex["M"].outputs["Color"], sep.inputs["Color"])
    va = nt.nodes.new("ShaderNodeVertexColor")
    va.layer_name = "Col"
    vsep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(va.outputs["Color"], vsep.inputs["Color"])
    # paint role (R * 255) -> colour; the ramp's stops sit half a step below each role
    roles = ["trim", "door", "shutter", "sash", "garage", "metal"]
    stops = [(0.0, _hex(palette[roles[0]]))] + [((i - 0.5) / 255.0, _hex(palette[r])) for i, r in enumerate(roles) if i > 0]
    stops.append(((6 - 0.5) / 255.0, (1.0, 1.0, 1.0, 1.0)))
    ramp = _ramp(nt, vsep.outputs["Red"], stops)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    nt.links.new(sep.outputs["Blue"], mix.inputs["Factor"])
    nt.links.new(tex["C"].outputs["Color"], mix.inputs[6])
    nt.links.new(ramp.outputs["Color"], mix.inputs[7])
    cav = nt.nodes.new("ShaderNodeMix")
    cav.data_type = "RGBA"
    cav.blend_type = "MULTIPLY"
    cav.inputs["Factor"].default_value = 1.0
    nt.links.new(mix.outputs[2], cav.inputs[6])
    nt.links.new(sep.outputs["Red"], cav.inputs[7])
    nt.links.new(cav.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nt.links.new(tex["N"].outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(tex["M"].outputs["Alpha"], bsdf.inputs["Alpha"])
    # metal bands: galvanised, black iron, bronze read as metal; the sheet does not carry metalness, so take it from
    # the band row (v) through a ramp
    sepuv = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sepuv.inputs["Vector"])
    bands = K.TRIM["bands"]
    mstops = [(0.0, (0, 0, 0, 1))]
    for name in sorted(bands, key=lambda b: bands[b]["v0"]):
        b = bands[name]
        metal = 1.0 if name in ("galvanised", "aluminium", "bronze") else 0.0
        mstops.append((b["v0"] + 1e-4, (metal, metal, metal, 1)))
    mramp = _ramp(nt, sepuv.outputs["Y"], mstops)
    nt.links.new(mramp.outputs["Color"], bsdf.inputs["Metallic"])
    return m


def glass_material():
    m = K.mat("Glass")
    nt, bsdf, out = _nodes(m)
    va = nt.nodes.new("ShaderNodeVertexColor")
    va.layer_name = "Col"
    vsep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(va.outputs["Color"], vsep.inputs["Color"])
    # room tone behind the glass varies by window seed; obscure glass is milky
    ramp = _ramp(nt, vsep.outputs["Green"], [(0.0, (0.020, 0.018, 0.016, 1)), (0.33, (0.032, 0.026, 0.020, 1)),
                                             (0.66, (0.016, 0.018, 0.022, 1))])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(vsep.outputs["Blue"], mix.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.45, 0.46, 0.46, 1)
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["IOR"].default_value = 1.52
    bsdf.inputs["Specular IOR Level"].default_value = 0.6
    return m


def _pattern_wall(nt, uvv, fid, bsdf):
    """Stand-in wall: brick, stone, lap, batten or stucco chosen by the finish id."""
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uvv, sep.inputs["Vector"])
    # brick: 254 mm module, 76 mm courses, half bond
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Brick Width"].default_value = 0.254
    brick.inputs["Row Height"].default_value = 0.076
    brick.inputs["Mortar Size"].default_value = 0.010
    brick.offset = 0.5
    nt.links.new(uvv, brick.inputs["Vector"])
    stone = nt.nodes.new("ShaderNodeTexBrick")
    stone.inputs["Scale"].default_value = 1.0
    stone.inputs["Brick Width"].default_value = 0.42
    stone.inputs["Row Height"].default_value = 0.14
    stone.inputs["Mortar Size"].default_value = 0.012
    stone.offset = 0.37
    stone.squash = 0.6
    stone.squash_frequency = 3
    nt.links.new(uvv, stone.inputs["Vector"])
    # lap: a shadow line every 150 mm (v), batten: a raised 64 mm strip every 305 mm (u)
    lapv = _math(nt, "FRACT", _math(nt, "DIVIDE", sep.outputs["Y"], 0.150))
    lap = _math(nt, "MINIMUM", _math(nt, "MULTIPLY", lapv, 6.0), 1.0)
    batu = _math(nt, "FRACT", _math(nt, "DIVIDE", sep.outputs["X"], 0.305))
    batten = _math(nt, "LESS_THAN", batu, 0.21)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 40.0
    nt.links.new(uvv, noise.inputs["Vector"])
    # colours per id
    stops_base = [(0.0, WALL_PREVIEW[0][0] + (1,))] + [((i - 0.5) / 255.0, WALL_PREVIEW[i][0] + (1,)) for i in range(1, 7)]
    stops_joint = [(0.0, WALL_PREVIEW[0][1] + (1,))] + [((i - 0.5) / 255.0, WALL_PREVIEW[i][1] + (1,)) for i in range(1, 7)]
    base = _ramp(nt, fid, stops_base)
    joint = _ramp(nt, fid, stops_joint)
    isbrick = _math(nt, "LESS_THAN", fid, 2.5 / 255.0)
    isstone = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", fid, 2.5 / 255.0), _math(nt, "LESS_THAN", fid, 3.5 / 255.0))
    islap = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", fid, 3.5 / 255.0), _math(nt, "LESS_THAN", fid, 4.5 / 255.0))
    isbat = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", fid, 4.5 / 255.0), _math(nt, "LESS_THAN", fid, 5.5 / 255.0))
    # mortar factor 1 in joints (brick and stone), 0 elsewhere
    mort = _math(nt, "ADD", _math(nt, "MULTIPLY", isbrick, brick.outputs["Fac"]), _math(nt, "MULTIPLY", isstone, stone.outputs["Fac"]))
    col = nt.nodes.new("ShaderNodeMix")
    col.data_type = "RGBA"
    nt.links.new(mort, col.inputs["Factor"])
    # per-brick tone from the brick node's colour output (varies brick to brick)
    tone = nt.nodes.new("ShaderNodeMix")
    tone.data_type = "RGBA"
    tone.blend_type = "MULTIPLY"
    tone.inputs["Factor"].default_value = 1.0
    brick.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1)
    brick.inputs["Color2"].default_value = (0.78, 0.74, 0.72, 1)
    stone.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1)
    stone.inputs["Color2"].default_value = (0.86, 0.84, 0.80, 1)
    bc = nt.nodes.new("ShaderNodeMix")
    bc.data_type = "RGBA"
    nt.links.new(isbrick, bc.inputs["Factor"])
    nt.links.new(stone.outputs["Color"], bc.inputs[6])
    nt.links.new(brick.outputs["Color"], bc.inputs[7])
    nt.links.new(base.outputs["Color"], tone.inputs[6])
    nt.links.new(bc.outputs[2], tone.inputs[7])
    nt.links.new(tone.outputs[2], col.inputs[6])
    nt.links.new(joint.outputs["Color"], col.inputs[7])
    nt.links.new(col.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    # relief: mortar recessed, lap shadow line, battens proud, stucco noise
    h = _math(nt, "ADD", _math(nt, "MULTIPLY", mort, -0.006),
              _math(nt, "ADD", _math(nt, "MULTIPLY", islap, _math(nt, "MULTIPLY", lap, 0.008)),
                    _math(nt, "ADD", _math(nt, "MULTIPLY", isbat, _math(nt, "MULTIPLY", batten, 0.012)),
                          _math(nt, "MULTIPLY", noise.outputs["Fac"], 0.0015))))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 1.0
    bump.inputs["Strength"].default_value = 1.0
    nt.links.new(h, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def wall_material():
    m = K.mat("Wall")
    nt, bsdf, out = _nodes(m)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    va = nt.nodes.new("ShaderNodeVertexColor")
    va.layer_name = "Col"
    vsep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(va.outputs["Color"], vsep.inputs["Color"])
    _pattern_wall(nt, uv.outputs["UV"], vsep.outputs["Green"], bsdf)
    return m


def roof_material():
    m = K.mat("Roof")
    nt, bsdf, out = _nodes(m)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    va = nt.nodes.new("ShaderNodeVertexColor")
    va.layer_name = "Col"
    vsep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(va.outputs["Color"], vsep.inputs["Color"])
    fid = vsep.outputs["Green"]
    sh = nt.nodes.new("ShaderNodeTexBrick")
    sh.inputs["Scale"].default_value = 1.0
    sh.inputs["Brick Width"].default_value = 0.333
    sh.inputs["Row Height"].default_value = 0.143
    sh.inputs["Mortar Size"].default_value = 0.004
    sh.offset = 0.5
    sh.inputs["Color1"].default_value = (1, 1, 1, 1)
    sh.inputs["Color2"].default_value = (0.8, 0.8, 0.8, 1)
    nt.links.new(uv.outputs["UV"], sh.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])
    rib = _math(nt, "LESS_THAN", _math(nt, "FRACT", _math(nt, "DIVIDE", sep.outputs["X"], 0.406)), 0.06)
    row = _math(nt, "FRACT", _math(nt, "DIVIDE", sep.outputs["Y"], 0.143))
    ismetal = _math(nt, "GREATER_THAN", fid, 2.5 / 255.0)
    base = _ramp(nt, fid, [(0.0, ROOF_PREVIEW[0] + (1,))] + [((i - 0.5) / 255.0, ROOF_PREVIEW[i] + (1,)) for i in (1, 2, 3)])
    grit = nt.nodes.new("ShaderNodeTexNoise")
    grit.inputs["Scale"].default_value = 300.0
    nt.links.new(uv.outputs["UV"], grit.inputs["Vector"])
    tone = nt.nodes.new("ShaderNodeMix")
    tone.data_type = "RGBA"
    tone.blend_type = "MULTIPLY"
    nt.links.new(_math(nt, "SUBTRACT", 1.0, ismetal), tone.inputs["Factor"])
    nt.links.new(base.outputs["Color"], tone.inputs[6])
    nt.links.new(sh.outputs["Color"], tone.inputs[7])
    nt.links.new(tone.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(_math(nt, "ADD", _math(nt, "MULTIPLY", ismetal, -0.5), 0.9), bsdf.inputs["Roughness"])
    nt.links.new(ismetal, bsdf.inputs["Metallic"])
    h = _math(nt, "ADD", _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, ismetal),
                                _math(nt, "ADD", _math(nt, "MULTIPLY", row, 0.006), _math(nt, "MULTIPLY", sh.outputs["Fac"], -0.004))),
              _math(nt, "ADD", _math(nt, "MULTIPLY", ismetal, _math(nt, "MULTIPLY", rib, 0.02)), _math(nt, "MULTIPLY", grit.outputs["Fac"], 0.001)))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 1.0
    nt.links.new(h, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def setup_materials(palette, trim_dir):
    trim_material(palette, trim_dir)
    glass_material()
    wall_material()
    roof_material()


def light(kind, yaw_deg=210.0):
    sc = bpy.context.scene
    for o in [o for o in sc.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    w = sc.world or bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    elev = {"midday": 62.0, "low": 8.0, "overcast": 40.0}[kind]
    if kind == "overcast":
        bg.inputs["Color"].default_value = (0.55, 0.57, 0.60, 1)
        bg.inputs["Strength"].default_value = 1.6
    else:
        sky = nt.nodes.new("ShaderNodeTexSky")
        try:
            sky.sky_type = "NISHITA"
        except TypeError:
            pass
        sky.sun_elevation = math.radians(elev)
        sky.sun_rotation = math.radians(yaw_deg)
        sky.sun_disc = False
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.25 if kind == "midday" else 0.35
        ld = bpy.data.lights.new("Sun", "SUN")
        ld.energy = 4.5 if kind == "midday" else 2.6
        ld.color = (1.0, 0.97, 0.92) if kind == "midday" else (1.0, 0.72, 0.48)
        ld.angle = math.radians(0.53)
        so = bpy.data.objects.new("Sun", ld)
        sc.collection.objects.link(so)
        so.rotation_euler = (math.radians(90 - elev), 0.0, math.radians(yaw_deg))
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = {"midday": -0.3, "low": 0.5, "overcast": 0.2}[kind]


def render_setup(res=(1280, 720), samples=48):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    sc.cycles.max_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
