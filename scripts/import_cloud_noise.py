"""Graphics G1: imports the cloud noise (Tools/clouds/make_cloud_noise.py) into /Game/Materials/Clouds: each atlas as a
linear 2D texture, then the 3D ones as volume textures built from it (Source2DTexture + tile size), uncompressed so the
Worley octaves keep their contrast. Run by scripts/make-content.sh before make_materials.py."""
import os
import sys

import unreal

SRC = sys.argv[-1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Artifacts", "clouds")
DEST = "/Game/Materials/Clouds"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.EditorAssetLibrary


def import_2d(name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(SRC, name + ".png"))
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", name + "_Atlas" if name != "T_CloudCurl" else name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    TOOLS.import_asset_tasks([task])
    tex = unreal.load_asset(f"{DEST}/{task.get_editor_property('destination_name')}")
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS if name != "T_CloudCurl" else unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    LIB.save_loaded_asset(tex)
    return tex


def make_volume(name, tile):
    atlas = import_2d(name)
    path = f"{DEST}/{name}"
    # Updated in place when it exists (materials reference it). An atlas imported in the same session isn't ready for a
    # new volume: it came out 186 x 93 x 121, not 128^3, so make-content.sh runs this twice (SailingSim.Visual.CloudNoise
    # checks the sizes).
    vt = unreal.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name, DEST, unreal.VolumeTexture, unreal.VolumeTextureFactory())
    vt.set_editor_property("source2d_tile_size_x", tile)
    vt.set_editor_property("source2d_tile_size_y", tile)
    vt.set_editor_property("source2d_texture", atlas)
    vt.set_editor_property("srgb", False)
    vt.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    vt.set_editor_property("address_mode", unreal.TextureAddress.TA_WRAP)
    vt.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    LIB.save_loaded_asset(vt)
    unreal.log(f"Cloud noise: {path} from {atlas.blueprint_get_size_x()}x{atlas.blueprint_get_size_y()} in {tile}^2 tiles")


# CLOUD_NOISE_ONLY=T_CloudBillow,... imports just those (the others' assets stay byte for byte).
ONLY = [n for n in os.environ.get("CLOUD_NOISE_ONLY", "").split(",") if n]
for name, tile in (("T_CloudShape", 128), ("T_CloudDetail", 64), ("T_CloudBillow", 128), ("T_CloudCurl", 0)):
    if ONLY and name not in ONLY:
        continue
    if tile:
        make_volume(name, tile)
    else:
        import_2d(name)
unreal.log("Cloud noise imported")
