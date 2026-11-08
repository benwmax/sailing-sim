"""Part detail loop: the turnbuckle in use, for its sheet (docs/part-detail-loop/turnbuckle.md). The kit's Chainplate
with the Turnbuckle stood on its Pin socket (as build_fleet.py places them on the Catalina 22) and a 3/16 in wire running
up from the turnbuckle's Wire socket (render-only), shot as in_use_side.png and in_use.png beside a round's other views.

    python3 Tools/boatkit/partloop/render_turnbuckle_in_use.py <round dir> [--samples N]

Reuses render_views.py's studio, so the light matches the round's other stills.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import render_views as RV  # noqa: E402  (first: it imports bpy, which bmesh needs)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = os.path.abspath(a[0])
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 32
    G.clear_scene()
    cp = P.build("Chainplate")
    pin = next(c for c in cp.children if c.name.startswith("SOCKET_Pin")).location.copy()
    tb = P.build("Turnbuckle")
    wire_top = next(c for c in tb.children if c.name.startswith("SOCKET_Wire")).location.copy()
    tb.data.transform(Matrix.Translation(pin))
    top = pin + wire_top
    wire = G.tube("RenderWire", [tuple(top - Vector((0, 0, 0.004))), tuple(top + Vector((0, 0, 0.12)))], 3 / 16 * 0.0254 / 2, P.M("Stainless"), 16)
    deck = G.prism("RenderDeck", G.rrect(0.16, 0.10, 0.01), -0.004, 0.0, None)
    dm = bpy.data.materials.new("RenderDeckMat")
    dm.use_nodes = True
    dm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.86, 0.84, 1)
    dm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.35
    deck.data.materials.append(dm)
    ob = G.join("InUse", [cp, tb, wire, deck])
    for view, d in (("in_use_side", (0.0, -1.0, 0.15)), ("in_use", (1.0, -1.0, 0.6))):
        c, size = RV.studio(ob, 900, 900, samples)
        R._camera(c + Vector(d).normalized() * size * 2.2 * 1.25, c, 85)
        RV.shoot(os.path.join(out, f"{view}.png"))


if __name__ == "__main__":
    main()
