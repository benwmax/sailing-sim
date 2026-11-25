"""Holds the Hobie 16's sockets to her parts (slice 8, docs/hobie16-9): each socket in the build's hobie16_sockets.json
must lie within its 'near' distance of the build object it names (the nearest point of that object's surface), and
that object must belong to the socket's part (PARTS: which build objects slice 10's export puts in each of the game's
parts); every socket the game reads (the file's 'required') must be there.

    python sockets_check_hobie16.py -- <build dir> [--json out.json]    # Blender's Python, on a built hobie16.blend
"""
import json
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# the build's objects in each of the game's parts (the fleet's names; slice 10 renames them to the hero's)
PARTS = {
    "SM_Hobie16_Hull": ("H16_Hull", "H16Platform_", "H16Rig_Stays", "H16Hw_", "H16Rudder_Gudgeons", "H16Tiller_",
                        "H16Mast", "H16Boom", "H16Rudder_"),
    "SM_Hobie16_Mast": ("H16Mast", "H16Rig_Trapeze"),
    "SM_Hobie16_Boom": ("H16Boom", "H16Hw_Mainsheet", "H16Sail_Main"),
    "SM_Hobie16_Rudder": ("H16Rudder_P",),
}
# (a hull socket may name the mast, the boom or a rudder as what it sits by: the lazy sheet's via bears on the mast,
# the gooseneck is the boom's pivot, a rudder pivot is a blade's axis; it stays a point fixed in the hull)


def surface_distance(ob, p):
    me = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    tree = BVHTree.FromPolygons([ob.matrix_world @ v.co for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
    hit = tree.find_nearest(p)
    return (hit[0] - p).length if hit[0] is not None else float("inf")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    d = os.path.abspath(args[0])
    out = args[args.index("--json") + 1] if "--json" in args else None
    bpy.ops.wm.open_mainfile(filepath=os.path.join(d, "hobie16.blend"))
    S = json.load(open(os.path.join(d, "hobie16_sockets.json")))
    rows, fails = [], []
    for name, cm in S["sockets"].items():
        part, near = S["owner"].get(name), S["near"].get(name)
        if not part or not near:
            fails.append(f"{name}: no part or no 'near'")
            continue
        p = Vector((cm[0] / 100.0, -cm[1] / 100.0, cm[2] / 100.0))     # back to Blender's frame (Y to port, metres)
        ob = bpy.data.objects.get(near["object"])
        if ob is None:
            fails.append(f"{name}: no object {near['object']}")
            continue
        dist = surface_distance(ob, p)
        in_part = any(ob.name.startswith(pre) for pre in PARTS.get(part, ()))
        ok = dist <= near["within_m"] and in_part
        rows.append({"socket": name, "part": part, "object": ob.name, "distance_m": round(dist, 4),
                     "within_m": near["within_m"], "in_part": in_part, "pass": ok})
        print(f"socket {name:18s} {part:20s} {ob.name:20s} {dist * 1000:7.1f} mm (<= {near['within_m'] * 1000:.0f})"
              f"  {'pass' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{name}: {dist * 1000:.1f} mm from {ob.name}" + ("" if in_part else f", not in {part}"))
    for part, names in S["required"].items():
        for n in names:
            if S["owner"].get(n) != part:
                fails.append(f"required {n} missing on {part}")
    rep = {"sockets": rows, "fails": fails, "pass": not fails}
    if out:
        json.dump(rep, open(out, "w"), indent=1)
    print("FAILS: " + "; ".join(fails) if fails else f"all {len(rows)} sockets pass")


main()
