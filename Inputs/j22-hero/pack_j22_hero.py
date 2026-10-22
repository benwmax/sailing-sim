"""pc/boat-slots: folds the hero J/22's flat hardware slots into J22H_packs.json's packs (Tools/blender/boat_packs.py),
one slot each with the entry in UV1. bake_j22_hero.py calls pack_part before it exports each game part; run alone, it
packs the committed fbx/ in place (no rebake: the baked maps and their UVs are untouched):

    blender -b --factory-startup -P Inputs/j22-hero/pack_j22_hero.py

then scripts/import_j22_hero.py."""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "Tools", "blender"))
from boat_packs import load_packs, pack_slots  # noqa: E402

PACKS = load_packs(os.path.join(HERE, "J22H_packs.json"))
PARTS = ("SM_J22H_Hull", "SM_J22H_Rudder", "SM_J22H_Boom", "SM_J22H_Mast")
# As bake_j22_hero.py exports the game parts.
EXPORT = dict(use_selection=True, axis_forward="X", axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
              mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False, bake_space_transform=True, path_mode="STRIP")


def pack_part(me, part):
    """Packs one game part's mesh (its baked groups, and the mast's aluminium, which M_BoatMast bends, keep their slots)."""
    if part not in PARTS:
        return None
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")   # the mast has no UV set: UV0 stays all zeros, as the import made it
    if any(u.name == "Pack" for u in me.uv_layers):
        return None                      # packed already
    return pack_slots(me, keep=("Aluminium",) if part == "SM_J22H_Mast" else (), packs=PACKS)


if __name__ == "__main__":
    for part in PARTS:
        path = os.path.join(HERE, "fbx", part + ".fbx")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=path, axis_forward="X", axis_up="Z")
        ob = next(o for o in bpy.context.scene.objects if o.type == "MESH")
        # As the bake leaves a part before export: its transform in the mesh (the exporter doesn't carry an object's
        # rotation onto custom normals under bake_space_transform).
        ob.data.transform(ob.matrix_world)
        ob.matrix_world.identity()
        slots = pack_part(ob.data, part)
        for o in bpy.context.scene.objects:
            o.select_set(o == ob)
        bpy.context.view_layer.objects.active = ob
        if slots is not None:
            bpy.ops.export_scene.fbx(filepath=path, **EXPORT)
        print("PACKED", part, slots)
