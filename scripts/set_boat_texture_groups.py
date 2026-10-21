"""Boat texture budget (docs/boat-tex-medium): puts the hero J/22's baked maps (/Game/Boats/J22Hero/Textures) and the boats'
close-up detail maps (/Game/Boats/Detail) in the Vehicle texture groups without reimporting them (the import scripts set
the same groups on a fresh import). ASailingGameMode drops those groups' top mip on Medium and Low.

    scripts\\windows\\run-python.ps1 set_boat_texture_groups.py
"""
import unreal

N, OTHER = unreal.TextureGroup.TEXTUREGROUP_VEHICLE_NORMAL_MAP, unreal.TextureGroup.TEXTUREGROUP_VEHICLE
changed = 0
for folder in ("/Game/Boats/J22Hero/Textures", "/Game/Boats/Detail"):
    for path in unreal.EditorAssetLibrary.list_assets(folder, recursive=True):
        tex = unreal.load_asset(path.split(".")[0])
        if not isinstance(tex, unreal.Texture2D):
            continue
        normal = tex.get_editor_property("compression_settings") == unreal.TextureCompressionSettings.TC_NORMALMAP
        want = N if normal else OTHER
        if tex.get_editor_property("lod_group") != want:
            tex.set_editor_property("lod_group", want)
            unreal.EditorAssetLibrary.save_loaded_asset(tex)
            changed += 1
unreal.log(f"Boat texture groups: {changed} textures moved to the Vehicle groups")
