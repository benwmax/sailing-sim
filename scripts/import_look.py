"""Graphics G8 cinematic look: imports the generated grade LUT and bloom kernel (Tools/look/make_grade_lut.py,
make_bloom_kernel.py -> Inputs/look) into /Game/Look. Run after regenerating either:

    scripts/windows/run-python.ps1 scripts/import_look.py      (or the editor's -run=pythonscript on the Mac)

The LUT is Unreal's 256x16 colour-grading strip: the ColorLookupTable group, no mips, uncompressed, not sRGB. The
kernel is linear grey, uncompressed half floats, no mips. ASailingEnvironment::ApplyCinematicLook loads both by path
and falls back to no grade and the engine's kernel when they are missing."""
import os

import unreal

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Inputs", "look")
DEST = "/Game/Look"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.EditorAssetLibrary


def import_png(name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(SRC, name + ".png"))
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    TOOLS.import_asset_tasks([task])
    return unreal.load_asset(f"{DEST}/{name}")


def main():
    lut = import_png("T_CinematicLUT")
    lut.set_editor_property("srgb", False)
    lut.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_COLOR_LOOKUP_TABLE)
    lut.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    lut.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    lut.set_editor_property("never_stream", True)
    LIB.save_loaded_asset(lut)

    k = import_png("T_BloomKernel")
    k.set_editor_property("srgb", False)
    k.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_HDR)
    k.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    k.set_editor_property("never_stream", True)
    LIB.save_loaded_asset(k)
    unreal.log("Look import done: T_CinematicLUT, T_BloomKernel")


main()
