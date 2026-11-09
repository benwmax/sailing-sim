"""Part detail loop, bow fittings (docs/part-detail-loop/bow.md): the hero J/22's bow in place, from the angle of Bean's
photo IMG_9224 (TX 7295 EC on its lift, from the dock off the starboard bow), square-on from starboard, and down on the
foredeck. Renders any saved hero .blend, so the same views serve the before (main) and after builds.

  python3 Tools/boatkit/partloop/render_bow.py <j22_hero.blend> <out dir> [--samples N]   (bpy module)
  blender -b <j22_hero.blend> -P Tools/boatkit/partloop/render_bow.py -- <j22_hero.blend> <out dir>

Hero frame: metres, +X forward, +Y port, the stem at x = 3.45, the deck edge there at z = 0.79.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

BOW = 3.45
VIEWS = {   # name: (camera, look at, lens mm)
    "photo": ((BOW + 0.50, -0.62, 0.98), (BOW - 0.04, 0.0, 0.73), 50),
    "side": ((BOW - 0.06, -0.85, 0.76), (BOW - 0.06, 0.0, 0.70), 50),
    "deck": ((BOW + 0.22, -0.30, 1.10), (BOW - 0.08, 0.0, 0.80), 50),
}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
    return a[0], os.path.abspath(a[1]), samples


def main():
    blend, out, samples = args()
    if bpy.data.filepath != os.path.abspath(blend):
        bpy.ops.wm.open_mainfile(filepath=blend)
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 900
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    # an overcast sky like the photo's: an even grey-white world and a soft sun
    w = bpy.data.worlds.new("bow_sky")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.78, 0.80, 0.83, 1)
    bg.inputs[1].default_value = 1.1
    sc.world = w
    for o in list(sc.objects):
        if o.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(o, do_unlink=True)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy, sun.data.angle = 1.6, math.radians(25)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.01
    for name, (loc, at, lens) in VIEWS.items():
        cam.location = loc
        cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        sc.render.filepath = os.path.join(out, f"{name}.png")
        bpy.ops.render.render(write_still=True)
    print("Bow:", out)


main()
