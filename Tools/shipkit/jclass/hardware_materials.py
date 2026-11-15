"""Bluebonnet's deck hardware's materials in Blender (docs/jclass-8): the flags drawn from their UVs with no image
textures, the lanterns' coloured lenses, the deck prisms' glass and the cowls' red insides.

    mats = hardware_materials.make()

The flags' faces carry (x, y) in metres in their "Spar" UV map (hardware.flag): x along the fly from the hoist, y down
the hoist (from its top on the ensign, from its middle on the burgee).

  Ensign     the 48-star flag of 1912-59: thirteen stripes, red at the top and the foot, and the blue canton over
             seven of them, 0.76 of the hoist along the fly, with six rows of eight white stars (each 0.0616 of the
             hoist across), set evenly in it
  Burgee     our invented club's: navy, a white five-pointed star near the hoist
"""
import bpy

import hardware
from sail_materials import Nodes, srgb, star

RED, WHITE, BLUE = (178, 34, 52), (255, 255, 255), (60, 59, 110)
NAVY = (28, 40, 82)


def bunting(name, rgb_fn):
    """A flag's cloth: wool bunting (rough, a little sheen, a little light through it), its colour from
    rgb_fn(G, x, y) (a colour socket) on the flag's (x, y)."""
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    G = Nodes(nt)
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Sheen Weight"].default_value = 0.4
    x, y = G.uv("Spar")
    col = rgb_fn(G, x, y)
    G.link(col, b.inputs["Base Color"])
    tr = G.N.new("ShaderNodeBsdfTranslucent")
    G.link(col, tr.inputs["Color"])
    mix = G.N.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.15
    G.link(b.outputs[0], mix.inputs[1])
    G.link(tr.outputs[0], mix.inputs[2])
    G.link(mix.outputs[0], nt.nodes.get("Material Output").inputs["Surface"])
    return mt


def ensign_rgb(G, x, y):
    A = hardware.HW["ensign"]["hoist"]
    stripe = G.m("FLOOR", G.m("DIVIDE", G.m("MAXIMUM", y, 0.0), A / 13.0))
    red = G.m("LESS_THAN", G.m("FLOORED_MODULO", stripe, 2.0), 0.5)        # stripes 0, 2, .. 12 red
    col = G.rgb_mix(red, srgb(WHITE), srgb(RED))
    C, D = 7.0 / 13.0 * A, 0.76 * A
    canton = G.m("MULTIPLY", G.lt(x, D), G.lt(y, C))
    # the stars: one in each cell of an 8 x 6 grid over the canton, upright (the star's point toward the hoist's top)
    dx, dy = D / 8.0, C / 6.0
    cx = G.m("MULTIPLY", G.m("ADD", G.m("FLOOR", G.m("DIVIDE", x, dx)), 0.5), dx)
    cy = G.m("MULTIPLY", G.m("ADD", G.m("FLOOR", G.m("DIVIDE", y, dy)), 0.5), dy)
    st = star(G, x, G.m("MULTIPLY", y, -1.0), cx, G.m("MULTIPLY", cy, -1.0), 0.0616 * A / 2)
    blue = G.rgb_mix(st, srgb(BLUE), srgb(WHITE))
    return G.rgb_mix(canton, col, blue)


def burgee_rgb(G, x, y):
    bg = hardware.HW["burgee"]
    st = star(G, x, G.m("MULTIPLY", y, -1.0), 0.3 * bg["fly"], 0.0, 0.32 * bg["hoist"])
    return G.rgb_mix(st, srgb(NAVY), srgb(WHITE))


def glass(name, rgb, transmission, rough=0.05):
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    b = mt.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*srgb(rgb), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = 1.52
    return mt


def paint(name, rgb, rough):
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    b = mt.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*srgb(rgb), 1)
    b.inputs["Roughness"].default_value = rough
    return mt


def make():
    """{slot name: material} for the slots hardware.py uses that the hull's materials do not have."""
    return {"Ensign": bunting("Ensign", ensign_rgb), "Burgee": bunting("Burgee", burgee_rgb),
            "LensGreen": glass("LensGreen", (40, 170, 90), 0.85), "LensRed": glass("LensRed", (200, 30, 30), 0.85),
            "LensClear": glass("LensClear", (235, 238, 240), 0.9),
            "DeckGlass": glass("DeckGlass", (200, 225, 215), 0.8),
            "CowlRed": paint("CowlRed", (170, 32, 28), 0.45)}
