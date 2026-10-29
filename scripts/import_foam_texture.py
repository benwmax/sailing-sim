"""Storm water step 2: imports T_FoamLace (Tools/water/make_foam_texture.py -> Artifacts/foam) into /Game/Materials/Foam as a
linear, uncompressed, wrapping texture with mips (BC compression blurred the fine lace into blocks), replacing it in place
(M_WaterV4 references it). Run it before make_materials.py's water."""
import os
import sys

import unreal

SRC = sys.argv[-1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Artifacts", "foam")
DEST = "/Game/Materials/Foam"
NAME = "T_FoamLace"

task = unreal.AssetImportTask()
task.set_editor_property("filename", os.path.join(SRC, NAME + ".png"))
task.set_editor_property("destination_path", DEST)
task.set_editor_property("destination_name", NAME)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", False)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
tex = unreal.load_asset(f"{DEST}/{NAME}")
tex.set_editor_property("srgb", False)
tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
tex.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
tex.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
unreal.EditorAssetLibrary.save_loaded_asset(tex)
unreal.log(f"Foam texture: {DEST}/{NAME} {tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()}")
