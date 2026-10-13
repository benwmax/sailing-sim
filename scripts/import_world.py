"""Visual V6: imports the world models built by Tools/blender (Artifacts/models/world/*.fbx) into /Game/World/<Kind>,
Nanite on, materials by slot name from WORLD_SLOTS. Run by scripts/make-world-models.sh after scripts/make-content.sh."""
import glob
import os
import re

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(REPO, "Artifacts", "models", "world")
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
WORLD = "/Game/World"
# Slot name -> material (under /Game/World unless a full path).
WORLD_SLOTS = {"Bark": "M_TreeBark", "Leaves": "M_TreeLeaves", "Crown": "M_TreeCrown"}
KINDS = (("SM_LiveOak", "Trees"), ("SM_PostOak", "Trees"), ("SM_CedarElm", "Trees"), ("SM_RedCedar", "Trees"))


def import_fbx(path, dest, name):
    asset_path = f"{dest}/{name}"
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
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


def setup(mesh, nanite=True):
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", nanite)
    mesh.set_editor_property("nanite_settings", ns)
    for index, m in enumerate(mesh.get_editor_property("static_materials")):
        slot = re.sub(r"_\d+$", "", str(m.get_editor_property("material_slot_name")).split(".")[0])  # Blender's .001 copies
        target = WORLD_SLOTS.get(slot)
        if not target:
            raise RuntimeError(f"{mesh.get_name()}: no material for slot {slot}")
        mat = unreal.load_asset(target if target.startswith("/") else f"{WORLD}/{target}")
        if not mat:
            raise RuntimeError(f"missing material {target}")
        mesh.set_material(index, mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)


for path in sorted(glob.glob(os.path.join(MODELS, "SM_*.fbx"))):
    name = os.path.splitext(os.path.basename(path))[0]
    folder = next((k for prefix, k in KINDS if name.startswith(prefix)), "Misc")
    mesh = import_fbx(path, f"{WORLD}/{folder}", name)
    setup(mesh)
    b = mesh.get_bounding_box()
    unreal.log(f"Imported {name}: bounds {b.min} .. {b.max}")
