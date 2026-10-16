"""Build the boat kit: every part in bk_parts.PARTS, exported one FBX per part with its sockets, a kit.json manifest
(triangles, size, sockets, material slots) and, with --render, a catalogue contact sheet.

Run headless:  blender -b --factory-startup -P Tools/boatkit/build_kit.py -- <out dir> [--render] [--only A,B]
or with the bpy module:  python3 Tools/boatkit/build_kit.py <out dir> [--render]
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = a[0] if a else os.path.join(HERE, "..", "..", "Artifacts", "boatkit")
    only = None
    for i, x in enumerate(a):
        if x == "--only":
            only = a[i + 1].split(",")
    return os.path.abspath(out), "--render" in a, only


def stats(ob):
    me = ob.data
    me.calc_loop_triangles()
    lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in me.vertices) for i in range(3)])
    socks = {c.name[len("SOCKET_"):]: [round(x, 4) for x in c.location] for c in ob.children if c.name.startswith("SOCKET_")}
    return {"tris": len(me.loop_triangles), "size_m": [round(x, 4) for x in (hi - lo)], "min_m": [round(x, 4) for x in lo],
            "slots": [m.name for m in me.materials], "sockets": socks}


def export_fbx(ob, path):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    for c in ob.children:
        c.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH", "EMPTY"}, apply_unit_scale=True,
                             mesh_smooth_type="OFF", use_custom_props=False, add_leaf_bones=False, bake_anim=False,
                             axis_forward="X", axis_up="Z")


def main():
    out, render, only = args()
    os.makedirs(os.path.join(out, "fbx"), exist_ok=True)
    G.clear_scene()
    manifest = {}
    built = []
    for name, (fn, info) in P.PARTS.items():
        if only and name not in only:
            continue
        ob = fn()
        st = stats(ob)
        manifest[name] = {**info, **st}
        export_fbx(ob, os.path.join(out, "fbx", f"{ob.name}.fbx"))
        built.append((name, ob))
        print(f"Kit: {name:16s} {st['tris']:6d} tris  {st['size_m']}  sockets {len(st['sockets'])}")
    json.dump(manifest, open(os.path.join(out, "kit.json"), "w"), indent=1)
    print(f"Kit: {len(built)} parts, {sum(m['tris'] for m in manifest.values())} tris -> {out}")
    if render:
        R.contact_sheet(built, os.path.join(out, "kit_catalogue.png"))


if __name__ == "__main__":
    main()
