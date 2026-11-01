"""Shore dressing (pc/shore-polyhaven): splits the fetched Poly Haven FBX files (Data/Shore/raw, Tools/shore/fetch_polyhaven.py)
into one mesh per piece for scripts/import_shore.py: each file's LOD0 only (Nanite needs no LOD chain), each piece of a
set (the mossy rocks, the grass and fern clumps) on its own, origin at the piece's base centre so it stands on the ground.
Writes Artifacts/models/shore/SM_Shore_<Name>.fbx and shore.json (piece -> its material and texture files, size in m).
The coast rock "patches" (20-60 m slabs of shore rock laid as a scene) are left out: the club's shore wants pieces.
Prints "Shore: <name> <tris>".
Usage: blender -b --factory-startup -P prep_polyhaven.py
"""
import glob
import json
import os
import re

import bpy
from mathutils import Vector

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(REPO, "Data", "Shore", "raw")
OUT = os.path.join(REPO, "Artifacts", "models", "shore")
SKIP = {"coast_rocks_01", "coast_rocks_03", "coast_land_rocks_03"}   # 60, 28 and 9 m scene patches
# Grass Bermuda's clumps are a few centimetres: too small to read from a boat.
SKIP_PIECES = re.compile(r"grass_bermuda")


def camel(s):
    return "".join(w.capitalize() for w in re.split(r"[_\s]+", s) if w)


def textures_for(asset_dir):
    tex = {}
    for p in glob.glob(os.path.join(asset_dir, "textures", "*")):
        n = os.path.basename(p).lower()
        for key, tag in (("diff", "_diff_"), ("normal", "_nor_gl_"), ("rough", "_rough_"), ("arm", "_arm_"), ("alpha", "_alpha_")):
            if tag in n:
                mat = os.path.basename(p)[: n.index(tag)]
                tex.setdefault(mat, {})[key] = os.path.relpath(p, REPO).replace("\\", "/")
    return tex


os.makedirs(OUT, exist_ok=True)
manifest = {}
for fbx in sorted(glob.glob(os.path.join(RAW, "*", "*.fbx"))):
    asset = os.path.basename(os.path.dirname(fbx))
    if asset in SKIP:
        continue
    tex = textures_for(os.path.dirname(fbx))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        if re.search(r"_LOD[1-9]$", o.name) or SKIP_PIECES.search(o.name):
            continue
        piece = re.sub(r"_LOD0$", "", o.name)
        name = "SM_Shore_" + camel(piece)
        # Bake its transform, then put the origin at the base centre.
        me = o.data.copy()
        me.transform(o.matrix_world)
        lo = Vector((min(v.co.x for v in me.vertices), min(v.co.y for v in me.vertices), min(v.co.z for v in me.vertices)))
        hi = Vector((max(v.co.x for v in me.vertices), max(v.co.y for v in me.vertices), max(v.co.z for v in me.vertices)))
        base = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        for v in me.vertices:
            v.co -= base
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                                 mesh_smooth_type="FACE")
        me.calc_loop_triangles()
        mats = [s.material.name for s in o.material_slots if s.material]
        # A material named otherwise than its textures (the picnic table's "table" wears the "top" set) takes the one
        # texture set no other material of the asset claims.
        spare = [k for k in tex if k not in mats]
        bound = {m: tex.get(m) or (tex[spare[0]] if len(spare) == 1 else {}) for m in mats}
        manifest[name] = {"asset": asset, "materials": bound,
                          "size_m": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)],
                          "tris": len(me.loop_triangles)}
        print(f"Shore: {name} {len(me.loop_triangles)}")
        bpy.data.objects.remove(ob)
json.dump(manifest, open(os.path.join(OUT, "shore.json"), "w"), indent=1)
print(f"Shore: {len(manifest)} pieces in {OUT}")
