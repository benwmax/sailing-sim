"""Visual V6: imports the world models built by Tools/blender (Artifacts/models/world/*.fbx) into /Game/World/<Kind>,
Nanite on, materials by slot name from WORLD_SLOTS. Run by scripts/make-world-models.sh after scripts/make-content.sh."""
import glob
import os
import re
import sys

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(REPO, "Artifacts", "models", "world")
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
WORLD = "/Game/World"
# Slot name -> material (under /Game/World unless a full path).
WORLD_SLOTS = {"Bark": "M_TreeBark", "Leaves": "M_TreeLeaves", "Crown": "M_TreeCrown", "Rock": "MI_World_Rock",
               "Paint": "M_VehiclePaint", "Glass": "MI_World_Glass", "Tyre": "MI_World_Tyre", "HeadLight": "MI_World_HeadLight",
               "TailLight": "MI_World_TailLight", "Trailer": "MI_World_Trailer",
               "Dark": "MI_World_Tyre", "Steel": "MI_World_Steel", "Wood": "MI_World_Pilings", "Lantern": "MI_World_Glass",
               "Reflective": "MI_World_Reflective", "ContainerPaint": "MI_World_ContainerPaint", "Trim": "MI_World_Trim"}
for _slot in ("Reed", "ReedHead", "Door", "Decking", "White", "Concrete", "Roof", "Gelcoat", "Antifouling", "TrimGreen", "Deck", "Cushion", "Net", "Barge", "Cargo", "Pilothouse", "Funnel", "ShipHull", "Lifeboat", "AviationRed", "Limestone", "StoneGreen", "RoofTile", "Gold"):
    WORLD_SLOTS[_slot] = f"MI_World_{_slot}"
KINDS = (("SM_LiveOak", "Trees"), ("SM_PostOak", "Trees"), ("SM_CedarElm", "Trees"), ("SM_RedCedar", "Trees"), ("SM_Sugarberry", "Trees"), ("SM_BlackWillow", "Trees"), ("SM_Cottonwood", "Trees"), ("SM_SaltCedar", "Trees"),
         ("SM_Rock", "Props"), ("SM_Car", "Vehicles"), ("SM_Pickup", "Vehicles"), ("SM_Semi", "Vehicles"),
         ("SM_Buoy", "Navaids"), ("SM_Beacon", "Navaids"), ("SM_Dayboard", "Navaids"), ("SM_Light_Tower", "Navaids"), ("SM_Light_MoleTower", "Navaids"),
         ("SM_Vessel", "Vessels"), ("SM_Barge", "Vessels"), ("SM_Container", "Vessels"),
         ("SM_House", "Houses"), ("SM_Landmark", "Landmarks"), ("SM_Reeds", "Props"))


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


# Per-folder slot overrides: a navaid's Paint weathers (rust, growth line); a vehicle's is glossy.
FOLDER_SLOTS = {"Navaids": {"Paint": "M_NavaidPaint"}, "Houses": {"Walls": "M_HouseWall", "Roof": "M_HouseRoof"},
                "Landmarks": {"Paint": "MI_World_PlatformPaint", "Red": "MI_World_AviationRed", "Brick": "MI_World_Brick"}}


def setup(mesh, nanite=True, overrides=None):
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", nanite)
    mesh.set_editor_property("nanite_settings", ns)
    for index, m in enumerate(mesh.get_editor_property("static_materials")):
        slot = re.sub(r"_\d+$", "", str(m.get_editor_property("material_slot_name")).split(".")[0])  # Blender's .001 copies
        target = (overrides or {}).get(slot) or WORLD_SLOTS.get(slot)
        if not target:
            raise RuntimeError(f"{mesh.get_name()}: no material for slot {slot}")
        mat = unreal.load_asset(target if target.startswith("/") else f"{WORLD}/{target}")
        if not mat:
            raise RuntimeError(f"missing material {target}")
        mesh.set_material(index, mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)


# ONLY=<prefix>[,<prefix>...] imports just those models and skips the bakes (iterating on one generator).
ONLY = os.environ.get("ONLY", "")
for path in sorted(glob.glob(os.path.join(MODELS, "SM_*.fbx"))):
    name = os.path.splitext(os.path.basename(path))[0]
    if ONLY and not any(name.startswith(o) for o in ONLY.split(",")):
        continue
    folder = next((k for prefix, k in KINDS if name.startswith(prefix)), "Misc")
    mesh = import_fbx(path, f"{WORLD}/{folder}", name)
    setup(mesh, overrides=FOLDER_SLOTS.get(folder))
    b = mesh.get_bounding_box()
    unreal.log(f"Imported {name}: bounds {b.min} .. {b.max}")

# The generated structures (WorldKit.h): bake the marina into Nanite tiles. Stale tiles from an older layout are removed.
BAKED = f"{WORLD}/Baked"
old = set(a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets(BAKED, recursive=False)) if unreal.EditorAssetLibrary.does_directory_exist(BAKED) else set()
BAKES = {"marina": unreal.WorldKitLibrary.bake_marina, "bridges": unreal.WorldKitLibrary.bake_bridges, "shore": unreal.WorldKitLibrary.bake_shore,
         "houses": unreal.WorldKitLibrary.bake_houses}
for what, lake in () if ONLY else (("marina", "RayHubbard"), ("bridges", "RayHubbard"), ("bridges", "GalvestonBay"), ("bridges", "GulfPassage"),
                   ("shore", "RayHubbard"), ("shore", "GalvestonBay"), ("shore", "GulfPassage"), ("houses", "RayHubbard"), ("houses", "GalvestonBay")):
    meshes = BAKES[what](lake)
    for m in meshes:
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        old.discard(m.get_path_name().split(".")[0])
    unreal.log(f"Imported the {lake} {what}: {len(meshes)} Nanite tiles")
    meshes = None
for path in ([] if ONLY else sorted(old)):  # never with ONLY: no bake ran, so every tile would look stale
    unreal.EditorAssetLibrary.delete_asset(path)
    unreal.log(f"Removed stale {path}")

# Everything is saved. Leave without finalizing the interpreter: its last garbage collection crashes (a weak reference
# to one of the baked meshes) and the crash reporter then hangs the commandlet.
unreal.log("Import done")
# With ONLY no bake ran (no baked mesh for that collection to trip on), and on Windows os._exit leaves a zombie editor
# holding the module DLLs (docs/windows): return normally there.
if not (ONLY and sys.platform == "win32"):
    os._exit(0)
