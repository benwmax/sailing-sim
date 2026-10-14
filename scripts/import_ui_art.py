"""Graphics G4: imports the front end's baked art (Tools/ui/make_ui_art.py, Artifacts/ui) to /Game/UI as UI textures
(sRGB, no mips, UserInterface2D compression, never streamed: menus show them at once). Run by scripts/make-content.sh."""
import os
import unreal

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Artifacts", "ui")
DEST = "/Game/UI"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
for f in sorted(os.listdir(SRC)):
    name, ext = os.path.splitext(f)
    if ext.lower() not in (".png", ".jpg"):
        continue
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(SRC, f))
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    TOOLS.import_asset_tasks([task])
    tex = unreal.load_asset(f"{DEST}/{name}")
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
    tex.set_editor_property("never_stream", True)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    unreal.log(f"UI art: {name} {tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()}")
unreal.log("UI art imported")
