"""Part detail loop, JibTrack extras (docs/part-detail-loop/jibtrack.md): close views of the car and the track in use.

    python3 Tools/boatkit/partloop/render_jibtrack.py <out dir> [--samples N] [--part JibTrack]

(bpy module, or blender -b --factory-startup -P ... -- <out dir>.) render_views.py frames the whole 600 mm track, so the
car is a few pixels; these frame the car and a hand's width of track either side, on a patch of white deck:
  car_threeq, car_side, car_above, car_aft   the car from forward-outboard high, abeam, above and from aft low
  in_use, in_use_side                        an 8 mm jib sheet coming down from the clew, under the sheave, aft
  track_wide                                 the whole track from the helm's height
Run it from a checkout of main for the "before" round (it builds whatever bk_parts registers as JibTrack).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402
import render_views as RV  # noqa: E402

SHEET_R = 0.004          # 8 mm jib sheet
EXPOSURE = -1.6          # the studio's lights are set for a part on its own; the white deck patch bounces a lot more


def _mat(name, col, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def _frame_box(lo, hi):
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    s = [b - a for a, b in zip(lo, hi)]
    return G.box("RenderFrame", c, s)


def _shoot_set(ob, out, frame_lo, frame_hi, views, samples, dist=2.2):
    for view, d, lens in views:
        fb = _frame_box(frame_lo, frame_hi)
        c, size = RV.studio(fb, 1000, 1000, samples, floor=False)
        bpy.context.scene.view_settings.exposure = EXPOSURE
        bpy.data.objects.remove(fb, do_unlink=True)
        R._camera(c + Vector(d).normalized() * size * dist * (lens / 50), c, lens)
        RV.shoot(os.path.join(out, f"{view}.png"))


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = os.path.abspath(a[0])
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 32
    name = a[a.index("--part") + 1] if "--part" in a else "JibTrack"
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    ob = P.build(name)
    # a patch of white deck under the track
    deck = G.box("RenderDeck", (0, 0, -0.0015), (1.4, 0.5, 0.003))
    deck.data.materials.append(_mat("RenderDeckMat", (0.62, 0.60, 0.54), 0.6))
    car_lo, car_hi = (-0.075, -0.03, 0.0), (0.075, 0.03, 0.066)
    _shoot_set(ob, out, car_lo, car_hi, [
        ("car_threeq", (1.0, -1.1, 0.75), 85),
        ("car_side", (0.0, -1.0, 0.08), 85),
        ("car_above", (0.25, -0.35, 1.0), 85),
        ("car_aft", (-1.0, -0.55, 0.35), 85)], samples)
    # whole track from about the helm's eye (aft, outboard, above)
    lo, hi = RV.bounds(ob)
    _shoot_set(ob, out, tuple(lo), tuple(hi), [("track_wide", (-1.0, -0.9, 0.75), 50)], samples, dist=1.6)
    # in use: the sheet comes down from the clew (forward, up, a little inboard), wraps under the sheave and runs aft
    sock = {c.name.split(".")[0][7:]: c.location.copy() for c in ob.children}
    lead = sock.get("Lead", sock["Sheave"] - Vector((0, 0, 0.0235)))
    sv = sock["Sheave"]
    r = sv.z - lead.z
    path = [Vector((0.42, 0.06, 0.40))]
    for k in range(7):                               # round the sheave's forward-lower quarter
        ang = math.radians(-35 - 55 * k / 6)
        path.append(Vector((sv.x + r * math.cos(ang), 0, sv.z + r * math.sin(ang))))
    path += [Vector((sv.x - 0.04, 0, lead.z + 0.0005)), Vector((-0.30, -0.01, lead.z + 0.006))]
    sheet = G.tube("RenderSheet", [tuple(p) for p in path], SHEET_R, None, 16)
    sheet.data.materials.append(_mat("RenderSheetMat", (0.55, 0.06, 0.05), 0.7))
    _shoot_set(ob, out, car_lo, car_hi, [("in_use", (1.0, -1.0, 0.45), 85), ("in_use_side", (0.0, -1.0, 0.05), 85)], samples)
    print("JibTrack extras ->", out)


if __name__ == "__main__":
    main()
