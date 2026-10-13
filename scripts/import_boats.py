"""Visual V2: imports the boat models built by Tools/blender (Artifacts/models/*.fbx) into /Game/Boats/<Boat>, with
Nanite on the rigid parts, the MI_Boat_* material library assigned by slot name, and the rig's attachment points as
sockets (from <Boat>_sockets.json). Run by scripts/make-boat-models.sh after scripts/make-content.sh."""
import json
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(REPO, "Artifacts", "models")
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MATERIALS = "/Game/Boats/Materials"


def import_fbx(path, dest, name):
    asset_path = f"{dest}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("remove_degenerates", True)
    data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    ASSETS.import_asset_tasks([task])
    mesh = unreal.load_asset(asset_path)
    if not mesh:
        raise RuntimeError(f"import failed: {path}")
    return mesh


def setup(mesh, nanite, slot_map, sockets):
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", nanite)
    mesh.set_editor_property("nanite_settings", ns)
    for index, m in enumerate(mesh.get_editor_property("static_materials")):
        slot = str(m.get_editor_property("material_slot_name")).split(".")[0]
        slot = slot_map.get(slot, slot)
        mi = unreal.load_asset(f"{MATERIALS}/MI_Boat_{slot}")
        if not mi:
            raise RuntimeError(f"No boat material for slot {slot}")
        mesh.set_material(index, mi)
    for m in mesh.get_editor_property("static_materials"):
        if "MI_Boat_" not in m.get_editor_property("material_interface").get_name():
            raise RuntimeError(f"{mesh.get_name()}: slot {m.get_editor_property('material_slot_name')} kept {m.get_editor_property('material_interface').get_name()}")
    for name, loc in sockets.items():
        sock = unreal.StaticMeshSocket(mesh)
        sock.set_editor_property("socket_name", name)
        sock.set_editor_property("relative_location", unreal.Vector(*loc))
        mesh.add_socket(sock)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)


def import_boat(tag, dest):
    meta = json.load(open(os.path.join(MODELS, f"{tag}_sockets.json")))
    for name, nanite in ((f"SM_{tag}_Hull", True), (f"SM_{tag}_Mast", False), (f"SM_{tag}_Boom", True), (f"SM_{tag}_Rudder", True)):
        mesh = import_fbx(os.path.join(MODELS, name + ".fbx"), dest, name)
        origin = meta["origins"][name]
        sockets = {s: [p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]] for s, p in meta["sockets"].items() if meta["owner"][s] == name}
        setup(mesh, nanite, {"Aluminium": "MastAluminium"} if name.endswith("Mast") else {}, sockets)
        b = mesh.get_bounding_box()
        unreal.log(f"Imported {name}: {len(sockets)} sockets, Nanite {nanite}, bounds {b.min} .. {b.max}")
    json.dump(meta["origins"], open(os.path.join(MODELS, f"{tag}_origins.json"), "w"))


def import_crew():
    """SK_Sailor (Tools/blender/build_crew.py): a skeletal mesh posed by the game; the MI_Boat_Crew* materials by slot."""
    dest, name = "/Game/Crew", "SK_Sailor"
    for asset in (f"{dest}/{name}", f"{dest}/{name}_Skeleton", f"{dest}/{name}_PhysicsAsset"):
        if unreal.EditorAssetLibrary.does_asset_exist(asset):
            unreal.EditorAssetLibrary.delete_asset(asset)
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("create_physics_asset", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(MODELS, name + ".fbx"))
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("options", ui)
    ASSETS.import_asset_tasks([task])
    mesh = unreal.load_asset(f"{dest}/{name}")
    if not mesh:
        raise RuntimeError("crew import failed")
    mats = mesh.get_editor_property("materials")
    for m in mats:
        slot = str(m.get_editor_property("material_slot_name")).split(".")[0]
        mi = unreal.load_asset(f"{MATERIALS}/MI_Boat_Crew{slot}")
        if not mi:
            raise RuntimeError(f"No crew material for slot {slot}")
        m.set_editor_property("material_interface", mi)
    mesh.set_editor_property("materials", mats)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    skel = mesh.get_editor_property("skeleton")
    if skel:
        unreal.EditorAssetLibrary.save_loaded_asset(skel)
    unreal.log(f"Imported {name}: {len(mats)} materials, skeleton {skel.get_name() if skel else None}")


import_boat("J22", "/Game/Boats/J22")
import_crew()
