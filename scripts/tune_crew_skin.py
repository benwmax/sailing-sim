"""Graphics G8: the MetaHuman crew's skin at capture distance (round 8: "the crew close-up lacks texture and detail").

The optimized MetaHuman build (scripts/make_metahumans.py) bakes the face to MI_Face_Skin_Baked_LOD*_VT with the micro
skin detail (the tiling pore normal and cavity: T_SkinMicro3_N, T_skinMicro3_CAV) and the region pore normals (Scalable
Normals) switched off, so the face shades smooth like plastic; the body has the micro detail on. This turns them on for
every role's face and body skin instances, the way the full-quality MetaHuman ships, with the micro detail's mask set so it
covers the whole skin. It edits the git-ignored /Game/Crew/MetaHumans (rerun after scripts/make-metahumans.sh), and is run
by scripts/make-crew-clothes.sh. Prints "Crew skin: ...".

    UnrealEditor-Cmd SailingSim.uproject -run=pythonscript -script=scripts/tune_crew_skin.py
"""
import unreal

MEL = unreal.MaterialEditingLibrary
LIB = unreal.EditorAssetLibrary
ROLES = ("Helm", "Trimmer", "Bow")
BODY_MASK = "/Game/Crew/MetaHumans/Common/Optional/BodyTextures/T_Skin_Microtiling_M"


def log(m):
    unreal.log("Crew skin: " + m)


def tune(path, switches, scalars, textures=None):
    mi = unreal.load_asset(path)
    if not mi:
        log(f"{path} missing")
        return
    for name, value in switches.items():
        MEL.set_material_instance_static_switch_parameter_value(mi, name, value)
    for name, value in scalars.items():
        MEL.set_material_instance_scalar_parameter_value(mi, name, value)
    for name, tex in (textures or {}).items():
        t = unreal.load_asset(tex)
        if t:
            MEL.set_material_instance_texture_parameter_value(mi, name, t)
    MEL.update_material_instance(mi)
    LIB.save_loaded_asset(mi)
    log(f"{path.split('/')[-1]}: " + ", ".join(f"{k}={v}" for k, v in {**switches, **scalars}.items()))


for role in ROLES:
    face = f"/Game/Crew/MetaHumans/{role}/Face/Materials"
    # The face: the pores by region (the nose, the cheeks' vertical and the forehead's horizontal pores) and the tiling
    # micro normal and cavity over all of it (mask channel A, full strength); specular breaks up in the cavities.
    for lod in ("LOD1", "LOD3"):
        tune(f"{face}/MI_Face_Skin_Baked_{lod}_VT",
             {"Use Micro Skin Details": True, "Use Scalable Normals": True},
             {"Micro MaskA Strength": 1.0, "Micro MaskB Strength": 0.0, "Micro MaskC Strength": 0.0, "Micro MaskD Strength": 0.0,
              "Micro Skin Normal Strength": 0.9, "Micro Skin Cavity Specular Multiply": 0.6},
             {"Micro Skin Details Mask": BODY_MASK})
    # The body (arms, legs, hands): micro detail is on already; a little stronger, so forearms in the sun aren't smooth.
    tune(f"/Game/Crew/MetaHumans/{role}/Body/Materials/MI_Body_Baked_VT",
         {"Use Micro Skin Details": True},
         {"Micro Skin Normal Strength": 0.9})

# pc/skin-backlight (docs/skin-backlight): the shared skin profile's transmission, the light that comes through an ear, a
# nostril or a neck's edge against the sun. The optimized build's profile carries a near-black tint (0.1, 0.033, 0) at
# extinction 18.6, so even with the sun lighting transmission (ASailingEnvironment) the skin never glowed. Measured on the
# backlit helm: (0.6, 0.2, 0.06) at 8 is a red-orange edge; (1, 0.33, 0.1) at 6 painted a hard orange rim on the nose.
# pc/skin-side-light (docs/skin-side-light): with the sun to the side that tint also lit a broad orange patch on the temple
# and cheek. The engine gives the profile no real thickness there: under virtual shadow maps the transmission's thickness
# is decoded from the shadow term itself (lit reads as 0 cm), and cascades find a short path through the cheek's curve at
# the terminator; extinction (8 to 20) and the scattering distribution (0.5 to 0.9) don't change it. Half the tint keeps
# the rim in profile and halves the patch.
PROFILE = "/Game/Crew/MetaHumans/Common/Lookdev_UHM/Skin/Materials/SSP_skin_unified"
profile = unreal.load_asset(PROFILE)
if profile:
    settings = profile.get_editor_property("settings")
    settings.set_editor_property("transmission_tint_color", unreal.LinearColor(0.3, 0.1, 0.03, 1.0))
    settings.set_editor_property("extinction_scale", 8.0)
    settings.set_editor_property("normal_scale", 0.3)
    profile.set_editor_property("settings", settings)
    LIB.save_loaded_asset(profile)
    log("SSP_skin_unified: transmission tint (0.3, 0.1, 0.03), extinction 8, normal scale 0.3")
else:
    log(f"{PROFILE} missing")
log("done")
