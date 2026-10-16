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
