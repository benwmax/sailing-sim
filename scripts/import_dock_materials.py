"""Dock materials: imports the CC0 texture sets (Tools/dock/fetch_dock_materials.py -> Data/Dock/raw, git-ignored) into
/Game/World/Dock as T_Dock_<Set>_{D,N,R,AO}. Run after fetching; make_materials.py's world library reads them by name.

    scripts/windows/run-python.ps1 scripts/import_dock_materials.py     (or the editor's -run=pythonscript on the Mac)

The 4K sets (<Set>_4k) import as T_Dock_<Set>_4k_*; the game uses them on Ultra only. Base colour is sRGB, the normal a
DirectX normal map, roughness and occlusion linear greyscale. Displacement is not imported (the docks aren't tessellated)."""
import json
import os

import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "Data", "Dock", "raw")
DEST = "/Game/World/Dock"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.EditorAssetLibrary
MAPS = {"diff": ("D", "color"), "nor": ("N", "normal"), "rough": ("R", "grey"), "ao": ("AO", "grey")}


def import_texture(src, name, kind):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    TOOLS.import_asset_tasks([task])
    tex = unreal.load_asset(f"{DEST}/{name}")
    if kind == "normal":
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
    elif kind == "grey":
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
    LIB.save_loaded_asset(tex)


def main():
    manifest_path = os.path.join(RAW, "manifest.json")
    if not os.path.exists(manifest_path):
        unreal.log_warning("Dock materials: no Data/Dock/raw/manifest.json (run Tools/dock/fetch_dock_materials.py); skipped")
        return
    manifest = json.load(open(manifest_path))
    count = 0
    for key in sorted(manifest):
        folder = os.path.join(RAW, key)
        base = key[:-3] if key.endswith("_4k") else key
        for suffix, (tag, kind) in MAPS.items():
            src = os.path.join(folder, f"{base}_{suffix}.jpg")
            if os.path.exists(src):
                import_texture(src, f"T_Dock_{key}_{tag}", kind)
                count += 1
    unreal.log(f"Dock materials imported: {count} textures from {len(manifest)} sets into {DEST}")


main()
