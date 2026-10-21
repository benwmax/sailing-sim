"""Preview materials for the boat kit, read from the game's own MI_Boat_* table (scripts/make_materials.py
BOAT_LIBRARY) so a kit part's slot names import straight onto the game library and its previews show the same base
colour, roughness and metalness. Previews add only micro-detail the game material also has (brushed grain on stainless,
moulded orange peel on plastic, wood grain), so a render reads like the in-game part.
"""
import ast
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
MATS_PY = os.path.join(HERE, "..", "..", "scripts", "make_materials.py")


def boat_library():
    src = open(MATS_PY).read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "BOAT_LIBRARY":
            return ast.literal_eval(node.value)
    raise RuntimeError("BOAT_LIBRARY not found in make_materials.py")


LIB = boat_library()
_cache = {}
# Boat fidelity 2: build_kit.py sets this so the previews read the shared trim sheet through the parts' UVs (normal,
# cavity, paint fill), as the game's M_BoatKit does, instead of procedural micro-detail.
TRIM = False
TRIM_DIR = os.path.join(HERE, "..", "..", "Inputs", "boat-kit")
_trim_images = {}


def _trim_image(name, colorspace):
    if name not in _trim_images:
        im = bpy.data.images.load(os.path.join(TRIM_DIR, f"{name}.png"))
        im.colorspace_settings.name = colorspace
        _trim_images[name] = im
    return _trim_images[name]


def _trim_nodes(nt, b, col, rough):
    uvn = nt.nodes.new("ShaderNodeUVMap")
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _trim_image("T_KitTrim_N", "Non-Color")
    tm = nt.nodes.new("ShaderNodeTexImage")
    tm.image = _trim_image("T_KitTrim_M", "Non-Color")
    for t in (tn, tm):
        nt.links.new(uvn.outputs["UV"], t.inputs["Vector"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tm.outputs["Color"], sep.inputs["Color"])
    # Base colour: darkened in the cavities, white where an engraving is paint-filled.
    cav = nt.nodes.new("ShaderNodeMix")
    cav.data_type = "RGBA"
    cav.blend_type = "MULTIPLY"
    cav.inputs["Factor"].default_value = 0.6
    cav.inputs["A"].default_value = _lin(col)
    nt.links.new(sep.outputs["Red"], cav.inputs["B"])
    paint = nt.nodes.new("ShaderNodeMix")
    paint.data_type = "RGBA"
    paint.inputs["B"].default_value = (0.85, 0.85, 0.82, 1)
    nt.links.new(cav.outputs["Result"], paint.inputs["A"])
    nt.links.new(sep.outputs["Blue"], paint.inputs["Factor"])
    nt.links.new(paint.outputs["Result"], b.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = max(0.02, rough - 0.25)
    rr.inputs["To Max"].default_value = min(1.0, rough + 0.25)
    nt.links.new(sep.outputs["Green"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])


def _lin(c):
    return (*c, 1.0)


def get(slot):
    """The preview material for a game slot name (MI_Boat_<slot>)."""
    if slot in _cache:
        return _cache[slot]
    if slot not in LIB:
        raise KeyError(f"No MI_Boat_{slot} in make_materials.py BOAT_LIBRARY")
    parent, col, rough, metal, coat, nonskid, porosity = LIB[slot]
    m = bpy.data.materials.new(slot)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = _lin(col)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat * 0.5
    if TRIM:
        _trim_nodes(nt, b, col, rough)
        _cache[slot] = m
        return m
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    mp = nt.nodes.new("ShaderNodeMapping")
    bump = nt.nodes.new("ShaderNodeBump")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    if slot in ("Stainless", "Aluminium"):
        mp.inputs["Scale"].default_value = (40, 2000, 40)     # brushed grain along local Y
        noise.inputs["Scale"].default_value = 1.0
        bump.inputs["Strength"].default_value = 0.05
        # rougher in the grain lines: a brushed lobe
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = rough * 0.8
        rr.inputs["To Max"].default_value = rough * 1.5
        nt.links.new(noise.outputs["Fac"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    elif slot in ("Wood", "Teak"):
        mp.inputs["Scale"].default_value = (6, 120, 120)      # grain along X
        noise.inputs["Scale"].default_value = 3.0
        noise.inputs["Detail"].default_value = 8
        bump.inputs["Strength"].default_value = 0.25 if slot == "Teak" else 0.05
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = _lin([c * 0.75 for c in col])
        mix.inputs["B"].default_value = _lin([min(1, c * 1.2) for c in col])
        nt.links.new(noise.outputs["Fac"], mix.inputs["Factor"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    else:
        mp.inputs["Scale"].default_value = (900, 900, 900)    # orange peel / moulded texture
        noise.inputs["Scale"].default_value = 1.0
        bump.inputs["Strength"].default_value = 0.03 + 0.2 * nonskid
    _cache[slot] = m
    return m
