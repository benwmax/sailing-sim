"""Track B (shore plan, docs/envloop/grass/README.md): builds the grass and ground-plant meshes from grass_geo.py.

    python Tools/envloop/grass/build_grass.py --out DIR [--only SM_Grass_Lawn_0,...]
    blender -b --factory-startup -P Tools/envloop/grass/build_grass.py -- --out DIR

Needs Blender's Python (the `bpy` module: pip install bpy==5.3.0 on Python 3.13, or Blender 5.x). Writes DIR/<mesh>.fbx
(metres, X forward, Z up, origin at the plant's foot; slots Grass and GrassSeed; the colour attribute and UV0 described
in grass_geo.py; custom normals) and DIR/grass_meshes.json (triangles, bounds and blade sizes per mesh, for the checks).
Nothing here is imported by the game yet: the import, the material and the placement come after the 21 Nov slice.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grass_geo as G  # noqa: E402

import bpy  # noqa: E402


def to_object(pl, name, collection=None):
    """A Blender object from a Plant: positions, triangles, slots, UV0, the colour attribute (byte colour, linear
    values: FBX carries them as written) and the custom normals."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(pl.v, [], pl.tris)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    col = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="CORNER")
    for poly, slot in zip(me.polygons, pl.slot):
        poly.material_index = slot
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uv.data[li].uv = pl.uv[vi]
            col.data[li].color = pl.c[vi]
    normals = [pl.n[me.loops[li].vertex_index] for li in range(len(me.loops))]
    me.normals_split_custom_set(normals)
    for s in G.SLOTS:
        me.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
    obj = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def export_fbx(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             axis_forward="X", axis_up="Z", bake_space_transform=True, mesh_smooth_type="OFF",
                             colors_type="LINEAR")


def stats(pl):
    lo, hi = pl.bounds()
    by_part = {}
    for part, length, width in pl.blades:
        k = {0.0: "leaf", 0.5: "stem", 1.0: "seed"}.get(part, str(part))
        d = by_part.setdefault(k, {"n": 0, "length_m": [9.0, 0.0], "width_mm": [999.0, 0.0]})
        d["n"] += 1
        d["length_m"] = [round(min(d["length_m"][0], length), 3), round(max(d["length_m"][1], length), 3)]
        d["width_mm"] = [round(min(d["width_mm"][0], width * 1000), 2), round(max(d["width_mm"][1], width * 1000), 2)]
    return {"tris": pl.tri_count, "verts": len(pl.v), "height_m": round(hi[2], 3),
            "spread_m": [round(hi[0] - lo[0], 3), round(hi[1] - lo[1], 3)], "parts": by_part}


def main(argv):
    out = argv[argv.index("--out") + 1]
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {}
    for name, (card, fn, kind) in G.catalogue().items():
        if only and name not in only:
            continue
        pl = fn()
        obj = to_object(pl, name)
        export_fbx(obj, os.path.join(out, name + ".fbx"))
        bpy.data.objects.remove(obj)
        report[name] = {"card": card, "kind": kind, **stats(pl)}
        print(f"Grass: {name} {pl.tri_count}")
    with open(os.path.join(out, "grass_meshes.json"), "w") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(args)
