"""Part detail loop: the J/22 hero's boom gear in place (docs/part-detail-loop/boomgear.md). Renders a built hero
(build_j22_hero.py's j22_hero.blend, best built without --sails) from the same views every round, so before and after
compare like for like:

    python3 Tools/boatkit/partloop/render_boomgear.py <j22_hero.blend> <out dir> [--samples N]
    (or blender -b <j22_hero.blend> -P Tools/boatkit/partloop/render_boomgear.py -- <j22_hero.blend> <out dir> ...)

Views (the camera on the starboard side, +Y being port): goose (the gooseneck from aft and a little above, where the
crew sees it), gooseside (square to the side), goosetop (from above and aft), vang (the vang's top block and bail, from
below and aft), boomend (the boom's aft end), boomendtop (from above and aft: the outhaul sheave's slot), outhaul (the
outhaul cleat from below), clay (goose, shape only). Writes stats.json: triangles and object count per group
(Gooseneck, BoomEnd, BoomOuthaulCleat, VangBlock, the vang's lower block)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_render as R  # noqa: E402

GROUPS = ("Gooseneck", "BoomEnd", "BoomOuthaulCleat", "VangBlock", "VangLow", "Vang_lo", "Vang_cam")


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
    return os.path.abspath(a[0]), os.path.abspath(a[1]), samples


def centre(prefix):
    pts = [o.matrix_world @ Vector(c) for o in bpy.data.objects if o.name.startswith(prefix) and o.type == "MESH"
           for c in o.bound_box]
    assert pts, prefix
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return (lo + hi) / 2


def tris(prefix):
    n, k = 0, 0
    dg = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(prefix):
            me = o.evaluated_get(dg).to_mesh()
            me.calc_loop_triangles()
            n += len(me.loop_triangles)
            k += 1
            o.evaluated_get(dg).to_mesh_clear()
    return n, k


def lights(c, size):
    for o in list(bpy.data.objects):
        if o.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(o, do_unlink=True)
    for nm, off, k, spread in (("Key", (-1, -1.2, 1.6), 26, 2.0), ("Rim", (1.5, 1.2, 0.8), 12, 1.5),
                               ("Fill", (1.2, -2.0, -0.3), 6, 3.0), ("Under", (-0.3, -0.6, -1.4), 4, 3.0)):
        pos = c + Vector(off).normalized() * size * 4
        R._light(nm, "AREA", pos, c, k * (pos - c).length_squared, size * spread)


def main():
    blend, out, samples = args()
    if bpy.data.filepath != blend:
        bpy.ops.wm.open_mainfile(filepath=blend)
    os.makedirs(out, exist_ok=True)
    for o in bpy.data.objects:          # sails and their battens would hide the boom: never in these views
        if any(c.name == "Sails" for c in o.users_collection):
            o.hide_render = True
    world = bpy.context.scene.world or bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.62, 0.70, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    R.SAMPLES = samples
    R._engine(1200, 900)
    bpy.context.scene.cycles.samples = samples
    g = centre("Gooseneck_vpin")
    be = centre("BoomEnd")
    oc = centre("BoomOuthaulCleat")
    vb = centre("VangBlock")
    views = {
        "goose":     (g + Vector((-0.06, 0, 0)), (-1.0, -0.8, 0.35), 0.42, 70),
        "gooseside": (g + Vector((-0.06, 0, 0)), (0.0, -1.0, 0.02), 0.36, 70),
        "goosetop":  (g + Vector((-0.06, 0, 0)), (-0.8, -0.35, 1.0), 0.42, 70),
        "vang":      (vb + Vector((0, 0, 0.02)), (-0.9, -1.0, -0.35), 0.45, 70),
        "boomend":   (be, (-1.0, -0.9, 0.25), 0.38, 70),
        "boomendtop": (be, (-0.7, -0.35, 1.0), 0.30, 70),
        "outhaul":   (oc, (-0.35, -0.6, -1.0), 0.26, 70),
    }
    for view, (c, d, dist, lens) in views.items():
        lights(c, dist)
        R._camera(c + Vector(d).normalized() * dist * (lens / 50), c, lens)
        bpy.context.scene.render.filepath = os.path.join(out, f"{view}.png")
        bpy.ops.render.render(write_still=True)
    clay = bpy.data.materials.new("Clay")
    clay.use_nodes = True
    clay.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(GROUPS + ("Boom", "Mast")):
            for i in range(len(o.data.materials)):
                o.data.materials[i] = clay
    c, d, dist, lens = views["goose"]
    lights(c, dist)
    R._camera(c + Vector(d).normalized() * dist * (lens / 50), c, lens)
    bpy.context.scene.render.filepath = os.path.join(out, "clay.png")
    bpy.ops.render.render(write_still=True)
    stats = {}
    for p in GROUPS:
        n, k = tris(p)
        if k:
            stats[p] = {"tris": n, "objects": k}
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print("Boomgear:", json.dumps(stats))


if __name__ == "__main__":
    main()
