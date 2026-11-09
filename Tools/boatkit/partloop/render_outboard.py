"""Part detail loop: the J/22 hero's outboard and its transom bracket in place (docs/part-detail-loop/outboard.md).
Renders a built hero (build_j22_hero.py's j22_hero.blend, best built without --sails) from the same views every round:

    python3 Tools/boatkit/partloop/render_outboard.py <j22_hero.blend> <out dir> [--samples N]
    (or blender -b <j22_hero.blend> -P Tools/boatkit/partloop/render_outboard.py -- <j22_hero.blend> <out dir> ...)

Views (hero frame: +x forward, +y port; the motor is on the port quarter): cockpit (from the helm, above and forward,
as Bean's lesson photo IMG_9273 sees it), side (square to the port side), aft (from astern and a little to port),
front (square from forward: the cowl's face), bracket (the transom bracket and clamp from above and inboard),
lower (the leg, cavitation plate, gearcase and prop from the side and below), clay (cockpit, shape only).
Writes stats.json: triangles and object count per group (OBo_ cowl and leg, OBb_ bracket, OBc_ clamp, OBt_ tiller)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_render as R  # noqa: E402

GROUPS = ("OBo_", "OBb_", "OBc_", "OBt_")


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
    return os.path.abspath(a[0]), os.path.abspath(a[1]), samples


def bounds(prefixes):
    pts = [o.matrix_world @ Vector(c) for o in bpy.data.objects if o.name.startswith(prefixes) and o.type == "MESH"
           for c in o.bound_box]
    assert pts, prefixes
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


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
    for nm, off, k, spread in (("Key", (1.0, -1.2, 1.6), 26, 2.0), ("Rim", (-1.5, 1.2, 0.8), 12, 1.5),
                               ("Fill", (1.2, 2.0, -0.3), 6, 3.0), ("Under", (0.3, -0.6, -1.4), 4, 3.0)):
        pos = c + Vector(off).normalized() * size * 4
        R._light(nm, "AREA", pos, c, k * (pos - c).length_squared, size * spread)


def main():
    blend, out, samples = args()
    if bpy.data.filepath != blend:
        bpy.ops.wm.open_mainfile(filepath=blend)
    os.makedirs(out, exist_ok=True)
    for o in bpy.data.objects:
        if any(c.name == "Sails" for c in o.users_collection):
            o.hide_render = True
    world = bpy.context.scene.world or bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.62, 0.70, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    R.SAMPLES = samples
    R._engine(int(os.environ.get('OB_W', 1200)), int(os.environ.get('OB_H', 900)))
    bpy.context.scene.cycles.samples = samples
    lo, hi = bounds(("OBo_", "OBt_", "OBc_"))
    c = (lo + hi) / 2
    top = Vector((c.x, c.y, hi.z - 0.25))
    blo, bhi = bounds(("OBb_", "OBc_"))
    br = (blo + bhi) / 2
    leg = Vector((c.x, c.y, lo.z + 0.18))
    views = {
        "cockpit": (top + Vector((0, 0, -0.15)), (1.0, -0.55, 0.85), 1.9, 50),
        "side":    (c, (0.0, 1.0, 0.05), 2.1, 50),
        "aft":     (top + Vector((0, 0, -0.15)), (-1.0, 0.45, 0.3), 1.7, 50),
        "front":   (top, (1.0, 0.0, 0.35), 1.2, 50),
        "bracket": (br, (-0.6, 0.9, 0.5), 0.9, 50),
        "lower":   (leg, (0.1, 1.0, -0.1), 0.9, 50),
    }
    only = os.environ.get('OB_ONLY')
    for view, (cc, d, dist, lens) in views.items():
        if only and view not in only.split(','):
            continue
        lights(cc, dist)
        R._camera(cc + Vector(d).normalized() * dist * (lens / 50), cc, lens)
        bpy.context.scene.render.filepath = os.path.join(out, f"{view}.png")
        bpy.ops.render.render(write_still=True)
    clay = bpy.data.materials.new("Clay")
    clay.use_nodes = True
    clay.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(GROUPS):
            for i in range(len(o.data.materials)):
                o.data.materials[i] = clay
    if not only or "clay" in only:
        cc, d, dist, lens = views["cockpit"]
        lights(cc, dist)
        R._camera(cc + Vector(d).normalized() * dist * (lens / 50), cc, lens)
        bpy.context.scene.render.filepath = os.path.join(out, "clay.png")
        bpy.ops.render.render(write_still=True)
    stats = {}
    for p in GROUPS:
        n, k = tris(p)
        if k:
            stats[p] = {"tris": n, "objects": k}
    stats["bounds"] = {"lo": list(lo), "hi": list(hi)}
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print("Outboard:", json.dumps(stats))


if __name__ == "__main__":
    main()
