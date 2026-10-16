"""Rope that looks like rope: the braid textures from Tools/rope/make_rope_textures.py on lines with real UVs.

Every line in the hero scripts is a bevelled curve (j22_geom.tube). Blender gives a curve's mesh a UV map whose U
runs along the curve's parameter and V round it; rope_uv() converts the curve to a mesh and rewrites U as true arc
length over one lay of the cover (5 diameters for the braids), so the weave keeps its size along the whole line, round
coils and knots too. rope_material() reads a colourway from Inputs/rope/colourways.json: base colour, tracer colour and
which tracer mask, then fades and dirties it from the style.

The game's live lines (FRigLine, BoatModelVisuals.cpp) use the same textures and the same UV rule, so a sheet in a
still and the same sheet in the game look alike.
"""
import json
import os

import bpy

ROPE_DIR = os.environ.get("J22H_ROPE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rope"))
_CW = None


def colourways():
    global _CW
    if _CW is None:
        _CW = {c["name"]: c for c in json.load(open(os.path.join(ROPE_DIR, "colourways.json")))["colourways"]}
    return _CW


# the style's old rope pairs map onto the colourways (j22_style.ROPE_COLOURS keys)
STYLE_TO_COLOURWAY = {
    "white_red": "white_red_fleck", "red_white": "red_white_fleck", "white_green": "white_green_fleck",
    "green_white": "green_white_fleck", "white_blue": "white_blue_fleck", "blue_white": "blue_white_mix",
    "black_white": "black_white_fleck", "grey_red": "grey_red_fleck", "yellow_black": "yellow_black_fleck",
    "blue_solid": "blue_solid",
}


def _img(name, colour=False):
    path = os.path.join(ROPE_DIR, name)
    img = bpy.data.images.get(name) or bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    return img


def _rgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (1.0,)


def rope_material(name, colourway, fade=0.3, dirt=0.3, kind="Braid24", seed=0):
    """A braided line: tracer pattern from the mask, the weave's cavity darkening, sun fade toward a chalky grey,
    dirt worked into the low parts, fuzz (sheen) on the high ones, and a normal map from the braid's height."""
    cw = colourways()[STYLE_TO_COLOURWAY.get(colourway, colourway)]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    tm = nt.nodes.new("ShaderNodeTexImage")
    tm.image = _img(f"T_Rope_{kind}_M.png")
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _img(f"T_Rope_{kind}_N.png")
    for t in (tm, tn):
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tm.outputs["Color"], sep.inputs[0])
    mask = {"fleck": sep.outputs[1], "spiral": sep.outputs[2], "mix": tm.outputs["Alpha"]}[cw["pattern"]]
    cav = sep.outputs[0]

    def mix(fac, a, b, blend="MIX"):
        n = nt.nodes.new("ShaderNodeMix")
        n.data_type, n.blend_type = "RGBA", blend
        if isinstance(fac, float):
            n.inputs["Factor"].default_value = fac
        else:
            nt.links.new(fac, n.inputs["Factor"])
        for slot, v in ((6, a), (7, b)):
            if isinstance(v, tuple):
                n.inputs[slot].default_value = v
            else:
                nt.links.new(v, n.inputs[slot])
        return n.outputs[2]

    def math(op, a, b):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, float):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    c = mix(mask, _rgb(cw["base"]), _rgb(cw["tracer"]))
    c = mix(0.3 * fade, c, _rgb("#CFCBC0"))                        # UV fade: colours chalk toward grey
    # dirt sits in the weave: stronger where the cavity is deep, patchy along the line
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 0.6
    noise.inputs["W"].default_value = seed * 0.37 % 10
    nt.links.new(uv.outputs["UV"], noise.inputs["Vector"])
    deep = math("SUBTRACT", 1.0, cav)
    d = math("MULTIPLY", math("ADD", math("MULTIPLY", deep, 1.2), math("MULTIPLY", noise.outputs["Fac"], 0.6)), dirt * 0.35)
    c = mix(math("MINIMUM", d, 1.0), c, _rgb("#5F574A"))
    c = mix(math("MULTIPLY", deep, 0.55), c, _rgb("#2A2824"))         # shadowed gaps between the carriers
    nt.links.new(c, bsdf.inputs["Base Color"])
    nt.links.new(math("ADD", 0.62, math("MULTIPLY", deep, 0.25)), bsdf.inputs["Roughness"])
    bsdf.inputs["Sheen Weight"].default_value = 0.6 + 0.3 * fade        # polyester fuzz, more on old line
    bsdf.inputs["Sheen Roughness"].default_value = 0.45
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nm.inputs["Strength"].default_value = 1.0
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = _rgb(cw["base"])
    m["rope_colourway"] = cw["name"]
    m["rope_kind"] = kind
    return m


def rope_uv(ob, diameter, lay_diameters=5.0):
    """Curve -> mesh with U = arc length / (lay_diameters x diameter). Returns the mesh object (same name)."""
    if ob.type == "CURVE":
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        name, mats, parent, mw = ob.name, list(ob.data.materials), ob.parent, ob.matrix_world.copy()
        colls = list(ob.users_collection)
        bpy.data.objects.remove(ob, do_unlink=True)
        ob = bpy.data.objects.new(name, me)
        for c in colls:
            c.objects.link(ob)
        ob.parent, ob.matrix_world = parent, mw
        if not me.materials:
            for mt in mats:
                me.materials.append(mt)
        for p in me.polygons:
            p.use_smooth = True
    me = ob.data
    if "UVMap" not in me.uv_layers:
        return ob
    uv = me.uv_layers["UVMap"].data
    rings = {}
    for lp in me.loops:
        rings.setdefault(round(uv[lp.index].uv[0], 6), set()).add(lp.vertex_index)
    keys = sorted(rings)
    cents = []
    for k in keys:
        vs = rings[k]
        c = sum((me.vertices[i].co for i in vs), me.vertices[next(iter(vs))].co * 0) / len(vs)
        cents.append(c)
    arc = [0.0]
    for a, b in zip(cents, cents[1:]):
        arc.append(arc[-1] + (b - a).length)
    lay = lay_diameters * diameter
    remap = {k: a / lay for k, a in zip(keys, arc)}
    for lp in me.loops:
        u = uv[lp.index].uv
        uv[lp.index].uv = (remap[round(u[0], 6)], u[1])
    return ob


def wire_material(name, tea_stain=0.2):
    """1x19 stainless rigging wire: the strand lay from T_Wire_1x19_N (U = arc length / 11 d), bright and slightly
    anisotropic, a little brown tea-staining in the grooves on an older boat."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _img("T_Wire_1x19_N.png")
    tm = nt.nodes.new("ShaderNodeTexImage")
    tm.image = _img("T_Wire_1x19_M.png")
    for t in (tn, tm):
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "MULTIPLY_ADD"
    inv.inputs[1].default_value = -tea_stain
    inv.inputs[2].default_value = tea_stain
    nt.links.new(tm.outputs["Color"], inv.inputs[0])
    nt.links.new(inv.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = _rgb("#C4C7CA")
    mix.inputs[7].default_value = _rgb("#7A6448")
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.24
    bsdf.inputs["Anisotropic"].default_value = 0.5
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = _rgb("#B9BCBF")
    m["rope_kind"] = "Wire1x19"
    return m
