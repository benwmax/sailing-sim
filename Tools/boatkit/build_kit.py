"""Build the boat kit: every part in bk_parts.PARTS, exported one FBX per part with its sockets, a kit.json manifest
(triangles, size, sockets, material slots, catalogue sizes) and, with --render, the review renders.

Boat fidelity 2 (docs/boat-fidelity-2): each part is exported twice, both on the shared trim sheet (bk_trim):
  SM_Kit_<Part>.fbx        the hero, imported as Nanite;
  SM_Kit_<Part>_Light.fbx  a decimated copy (about a quarter of the triangles, at most 8 slots) for the Mac's Medium and Low.
--render renders the catalogue tiles (_tiles) and each sized part's sizes side by side (_sizes); make_review_sheet.py
(a system Python with Pillow) lays them out as the review sheets.

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
from mathutils import Matrix, Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_materials as BM  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402
import bk_trim as BT  # noqa: E402

LIGHT_SHARE = 0.25          # the light version keeps about this share of the hero's triangles
LIGHT_MIN_TRIS = 160
MAX_SLOTS = 8               # phase 0's budget for a non-Nanite boat part


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
    # Object names are global in Blender, so a later part's SOCKET_Head reads SOCKET_Head.001: the real name is before the dot.
    socks = {c.name.split(".")[0][len("SOCKET_"):]: [round(x, 4) for x in c.location] for c in ob.children if c.name.startswith("SOCKET_")}
    return {"tris": len(me.loop_triangles), "size_m": [round(x, 4) for x in (hi - lo)], "min_m": [round(x, 4) for x in lo],
            "slots": [m.name for m in me.materials], "sockets": socks}


def light_version(ob):
    """A decimated copy with its own sockets: collapse to LIGHT_SHARE of the triangles, smooth shading by angle."""
    me = ob.data.copy()
    lo = bpy.data.objects.new(f"{ob.name}_Light", me)
    bpy.context.scene.collection.objects.link(lo)
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    target = max(LIGHT_MIN_TRIS, int(tris * LIGHT_SHARE))
    if target < tris:
        d = lo.modifiers.new("decimate", "DECIMATE")
        d.decimate_type = "COLLAPSE"
        d.ratio = target / tris
        d.use_collapse_triangulate = True
        G.apply(lo)
        me = lo.data                     # apply swaps in a new mesh
    with bpy.context.temp_override(object=lo, active_object=lo, selected_objects=[lo], selected_editable_objects=[lo]):
        if me.has_custom_normals:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me.set_sharp_from_angle(angle=math.radians(40))
    for p in me.polygons:
        p.use_smooth = True
    if len(me.materials) > MAX_SLOTS:
        raise RuntimeError(f"{ob.name}: {len(me.materials)} slots, the light budget is {MAX_SLOTS}")
    for c in ob.children:
        e = bpy.data.objects.new(c.name, None)       # Blender names it SOCKET_Pin.001 beside the hero's; export_fbx fixes that
        bpy.context.scene.collection.objects.link(e)
        e.location, e.rotation_euler = c.location.copy(), c.rotation_euler.copy()
        e.parent = lo
    return lo


def export_fbx(ob, path):
    """Export a part with its sockets. A socket Blender has suffixed (SOCKET_Pin.001: another part, or the light copy, has
    SOCKET_Pin) is exported under its real name: the clashing one is renamed for the export and both are put back after."""
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    swaps = []
    for c in ob.children:
        c.select_set(True)
        base = c.name.split(".")[0]
        if c.name != base:
            other = bpy.data.objects.get(base)
            if other is not None:
                other.name = base + "__hold"
            c.name = base
            swaps.append((c, other, base))
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH", "EMPTY"}, apply_unit_scale=True,
                             mesh_smooth_type="OFF", use_custom_props=False, add_leaf_bones=False, bake_anim=False,
                             axis_forward="X", axis_up="Z")
    for c, other, base in swaps:
        c.name = base + "__light"
        if other is not None:
            other.name = base


def size_renders(out, only):
    """Each sized part's catalogue sizes side by side at true relative scale, one render per part (_sizes/<Part>.png)."""
    tmp = os.path.join(out, "_sizes")
    os.makedirs(tmp, exist_ok=True)
    for name, spec in P.SIZES.items():
        if only and name not in only:
            continue
        G.clear_scene()
        keys = list(spec.get("scale") or spec.get("kw"))
        objs = [P.build(name, size=k) for k in keys]
        R.group_render(objs, os.path.join(tmp, f"{name}.png"))
        json.dump({"part": name, "dim": spec["dim"], "sizes": keys}, open(os.path.join(tmp, f"{name}.json"), "w"))


def main():
    out, render, only = args()
    os.makedirs(os.path.join(out, "fbx"), exist_ok=True)
    BM.TRIM = True
    G.clear_scene()
    manifest = {}
    built = []
    for name, (fn, info) in P.PARTS.items():
        if only and name not in only:
            continue
        ob = P.build(name)
        light = light_version(ob)
        BT.assign(ob)
        BT.assign(light)
        st = stats(ob)
        lt = stats(light)
        manifest[name] = {**info, **st, "light": {"tris": lt["tris"], "slots": lt["slots"], "sockets": sorted(lt["sockets"])},
                          "sizes": P.SIZES.get(name)}
        export_fbx(ob, os.path.join(out, "fbx", f"{ob.name}.fbx"))
        export_fbx(light, os.path.join(out, "fbx", f"{ob.name}_Light.fbx"))
        light.hide_render = True
        built.append((name, ob))
        print(f"Kit: {name:16s} {st['tris']:6d} tris (light {lt['tris']:5d})  {st['size_m']}  sockets {len(st['sockets'])}")
    json.dump(manifest, open(os.path.join(out, "kit.json"), "w"), indent=1)
    print(f"Kit: {len(built)} parts, {sum(m['tris'] for m in manifest.values())} tris "
          f"(light {sum(m['light']['tris'] for m in manifest.values())}) -> {out}")
    if render:
        R.contact_sheet(built, os.path.join(out, "kit_catalogue.png"))
        size_renders(out, only)


if __name__ == "__main__":
    main()
