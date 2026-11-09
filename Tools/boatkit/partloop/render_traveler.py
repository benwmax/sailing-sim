"""Part detail loop: the J/22 hero's mainsheet traveler in place (docs/part-detail-loop/traveler.md). Renders a built
hero (build_j22_hero.py's j22_hero.blend, best built without --sails) from the same views every round, so before and
after compare like for like:

    python3 Tools/boatkit/partloop/render_traveler.py <j22_hero.blend> <out dir> [--samples N]
    (or blender -b <j22_hero.blend> -P Tools/boatkit/partloop/render_traveler.py -- <j22_hero.blend> <out dir> ...)

Views: photo (from the port quarter, aft and above, looking forward to starboard across the cockpit: the angle of
Bean's photo), car (the car and the foot of the lower block, close), end (the starboard end of the track: end stop,
eye strap, cam cleat), block (the mainsheet's lower block on the car, from aft), section (the track where it spans the well, from forward and a little below: its depth), top (the starboard half from
above), clay (photo, shape only). Writes stats.json: triangles and object count per group."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_render as R  # noqa: E402
from render_boomgear import args, centre, lights  # noqa: E402

GROUPS = ("MainsheetLow", "MainSwivel", "MainSpring", "MainCam", "MainPlate", "MainBecket", "TravelerBar", "TravSlot", "TravChannel", "TravS_", "TravMark", "TravNum", "TravStop", "TravEnd", "TravCar",
          "TravTang", "TravBlock", "TravEye", "TravCam", "TravLine", "TravTail")


def tris(prefix):
    """Triangles and objects whose names start with prefix, curves (the control lines) included."""
    n, k = 0, 0
    dg = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE") and o.name.startswith(prefix):
            me = o.evaluated_get(dg).to_mesh()
            me.calc_loop_triangles()
            n += len(me.loop_triangles)
            k += 1
            o.evaluated_get(dg).to_mesh_clear()
    return n, k


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
    quick = "--quick" in sys.argv          # a fast look while modelling: 800 x 600
    R._engine(800 if quick else 1200, 600 if quick else 900)
    bpy.context.scene.cycles.samples = samples
    tb = centre("TravelerBar")
    lo = Vector([min((o.matrix_world @ Vector(c))[i] for o in bpy.data.objects if o.name == "TravelerBar" for c in o.bound_box) for i in range(3)])
    hi = Vector([max((o.matrix_world @ Vector(c))[i] for o in bpy.data.objects if o.name == "TravelerBar" for c in o.bound_box) for i in range(3)])
    top = hi.z
    stb = Vector((tb.x, lo.y + 0.06, top))            # the starboard end (-Y)
    views = {
        "photo":   (Vector((tb.x, -0.20, top + 0.06)), (0.75, 0.8, 0.95), 1.10, 50),
        "car":     (Vector((tb.x, 0.0, top + 0.02)), (1.0, 0.55, 0.65), 0.30, 70),
        "end":     (stb + Vector((-0.01, 0.02, 0.01)), (0.9, 0.7, 0.85), 0.30, 70),
        "section": (Vector((tb.x, -0.30, top - 0.008)), (1.0, -0.45, -0.08), 0.13, 70),
        "top":     (Vector((tb.x - 0.02, -0.45, top)), (-0.25, 0.0, 1.0), 0.55, 50),
        "block":   (Vector((tb.x, 0.0, top + 0.10)), (-1.0, -0.75, 0.45), 0.36, 70),
    }
    only = [a[len("--views="):].split(",") for a in sys.argv if a.startswith("--views=")]
    for view, (c, d, dist, lens) in views.items():
        if only and view not in only[0]:
            continue
        lights(c, dist)
        R._camera(c + Vector(d).normalized() * dist * (lens / 50), c, lens)
        bpy.context.scene.render.filepath = os.path.join(out, f"{view}.png")
        bpy.ops.render.render(write_still=True)
    if only and "clay" not in only[0]:
        return finish(out)
    clay = bpy.data.materials.new("Clay")
    clay.use_nodes = True
    clay.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE") and o.name.startswith(GROUPS + ("Main",)):
            for i in range(len(o.data.materials)):
                o.data.materials[i] = clay
    c, d, dist, lens = views["photo"]
    lights(c, dist)
    R._camera(c + Vector(d).normalized() * dist * (lens / 50), c, lens)
    bpy.context.scene.render.filepath = os.path.join(out, "clay.png")
    bpy.ops.render.render(write_still=True)
    finish(out)


def finish(out):
    stats = {}
    for p in GROUPS:
        n, k = tris(p)
        if k:
            stats[p] = {"tris": n, "objects": k}
    stats["_total"] = sum(v["tris"] for v in stats.values())
    bar = bpy.data.objects.get("TravelerBar")
    lo = Vector([min((o.matrix_world @ Vector(c))[i] for o in bpy.data.objects if o.name == "TravelerBar" for c in o.bound_box) for i in range(3)])
    hi = Vector([max((o.matrix_world @ Vector(c))[i] for o in bpy.data.objects if o.name == "TravelerBar" for c in o.bound_box) for i in range(3)])
    stats["_track"] = {"length_mm": round((hi.y - lo.y) * 1000, 1), "width_mm": round((hi.x - lo.x) * 1000, 1),
                       "height_mm": round((hi.z - lo.z) * 1000, 1), "section_mm2": bar.get("section_mm2") if bar else None}
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print("Traveler:", json.dumps(stats))


if __name__ == "__main__":
    main()
