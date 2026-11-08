"""Part detail loop: the masthead fly where it lives (docs/part-detail-loop/mastheadfly.md).

Renders a masthead fly part on the top 1.2 m of a J/22-size mast (a 95 x 65 mm section, a cap, the crane, stubs of the
forestay and backstay; render-only dressing, never exported), looking up from the cockpit (in_use.png) and from abeam
at the masthead (in_use_side.png), at the same -1 stop exposure as partloop/render_metal.py. It also registers
MastheadFlyGameBoxes, the game's fly before this loop (SailboatPawn's FlyArrow and FlyVane boxes, 80 mm above the
masthead with no stalk), so the "before" round can be rendered here and with render_views/render_metal from a wrapper.

    python3 Tools/boatkit/partloop/render_masthead.py <Part> <out dir> [--samples N]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402


@P.part("MastheadFlyGameBoxes", "render-only", "before: SailboatPawn's FlyArrow + FlyVane boxes (not a kit part)")
def game_boxes():
    blk = P.M("BlackPlastic")
    z = 0.08
    objs = [G.box("FlyArrow", (0.18, 0, z), (0.45, 0.025, 0.025), blk), G.box("FlyVane", (-0.08, 0, z), (0.12, 0.01, 0.10), blk)]
    return P.done("MastheadFlyGameBoxes", objs, [("Mount", (0, 0, 0))])


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    name, out = a[0], os.path.abspath(a[1])
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 32
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    P.build(name)
    alu, blk, ss = P.M("MastAluminium"), P.M("BlackPlastic"), P.M("Stainless")
    G.prism("mast", [(x / 1000, y / 1000) for x, y in G.ellipse(47.5, 32.5, 32)], -1.2, -0.03, alu)
    G.prism("cap", [(x / 1000, y / 1000) for x, y in G.rrect(120, 72, 30, 6)], -0.03, 0.0, blk)
    G.box("crane", (-0.09, 0, -0.012), (0.10, 0.03, 0.03), blk)
    G.cyl("backstay", (-0.13, 0, -0.03), (-0.75, 0, -1.2), 0.002, ss, 8)
    G.cyl("forestay", (0.05, 0, -0.25), (0.65, 0, -1.2), 0.002, ss, 8)
    for view, cam, tgt, lens in (("in_use", (2.2, -3.4, -6.5), (0, 0, 0.1), 300),
                                 ("in_use_side", (0.15, -2.6, 0.05), (-0.03, 0, -0.05), 85)):
        for o in list(bpy.data.objects):
            if o.type in ("LIGHT", "CAMERA"):
                bpy.data.objects.remove(o, do_unlink=True)
        R._engine(900, 900)
        bpy.context.scene.cycles.samples = samples
        bpy.context.scene.view_settings.exposure = -1.0
        R._light("Sun", "SUN", (3, -4, 6), (0, 0, 0), 3.5, 0.02)
        R._light("Fill", "AREA", (-2, -3, -2), (0, 0, 0), 120, 2)
        R._camera(cam, tgt, lens)
        bpy.context.scene.render.filepath = os.path.join(out, f"{view}.png")
        bpy.ops.render.render(write_still=True)
    print(f"Masthead: {name} -> {out}")


if __name__ == "__main__":
    main()
