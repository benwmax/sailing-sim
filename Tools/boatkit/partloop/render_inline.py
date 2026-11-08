"""Part detail loop: extra stills for a part a line runs straight through (a rope clutch, a jammer, a fairlead).

render_views.py dresses blocks and cleats with a line; this adds the same for a part with LineIn and LineOut sockets and
no sheave: a 10 mm line through both, leaving the deck at a shallow angle each side (render-only, never exported). It
writes in_use_side.png and in_use.png into the round's folder, where make_sheet.py picks them up, and, when the round has
a photo_outline.json (photo_outline.py score), matched.png: the part in full materials from the angle that best matched
the reference photo, for a photo-against-render tile.

    python3 Tools/boatkit/partloop/render_inline.py <Part> <round dir> [--samples N]     # the bpy module (or blender -b -P ... --)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402
import render_views as RV  # noqa: E402


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    name, out = a[0], os.path.abspath(a[1])
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 32
    G.clear_scene()
    ob = P.build(name)
    socks = {c.name.split(".")[0][7:]: Vector(c.location) for c in ob.children}
    if "LineIn" in socks and "LineOut" in socks:
        p_in, p_out = socks["LineIn"], socks["LineOut"]
        d = (p_out - p_in).normalized()
        run = 0.16
        # the line leaves each end and drops toward the deck a little, as it does running to a winch and a turning block
        path = [p_in - d * run + Vector((0, 0, -p_in.z * 0.6)), p_in - d * 0.02, p_in, p_out, p_out + d * 0.02,
                p_out + d * run + Vector((0, 0, -p_out.z * 0.6))]
        rope = G.tube("RenderRope", [tuple(p) for p in path], 0.005, None, 16)
        rm = bpy.data.materials.new("RenderRopeMat")
        rm.use_nodes = True
        b = rm.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.02, 0.12, 0.25, 1)
        b.inputs["Roughness"].default_value = 0.8
        rope.data.materials.append(rm)
        for view, dv in (("in_use_side", (0.0, -1.0, 0.15)), ("in_use", (-1.0, -1.0, 0.7))):
            c, size = RV.studio(ob, 900, 900, samples)
            R._camera(c + Vector(dv).normalized() * size * 2.2 * 1.7, c, 85)
            RV.shoot(os.path.join(out, f"{view}.png"))
        bpy.data.objects.remove(rope, do_unlink=True)
        print(f"Inline: in-use stills -> {out}")
    po = os.path.join(out, "photo_outline.json")
    if os.path.exists(po):
        m = json.load(open(po))
        az, el = math.radians(m["azimuth"]), math.radians(m["elevation"])
        dv = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
        c, size = RV.studio(ob, 900, 900, samples)
        R._camera(c + dv * size * 2.2 * (85 / 50), c, 85)          # as photo_outline.render
        RV.shoot(os.path.join(out, "matched.png"))
        print(f"Inline: matched view at azimuth {m['azimuth']}, elevation {m['elevation']} -> {out}")


if __name__ == "__main__":
    main()
