"""Shore dressing (pc/shore-polyhaven): imports the Poly Haven pieces (Tools/shore/prep_polyhaven.py ->
Artifacts/models/shore, textures from Data/Shore/raw) into /Game/World/Shore: the meshes (SM_Shore_*, Nanite), their
textures (Textures/), and an instance per material (MI_Shore_*) of two small parents made here: M_ShorePBR (opaque:
base colour, normal, roughness) and M_ShoreFoliage (masked and two-sided, its alpha the mask: grass and ferns).
Poly Haven's normals are OpenGL's, so their green channel is flipped on import. Returns normally (on Windows os._exit
crashes the editor's exit: docs/windows/README.md).
Usage: scripts\\windows\\run-python.ps1 import_shore.py
"""
import json
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(REPO, "Artifacts", "models", "shore")
DEST = "/Game/World/Shore"
TEX = f"{DEST}/Textures"
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary


def import_file(path, dest, name, options=None):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    if options:
        task.set_editor_property("options", options)
    ASSETS.import_asset_tasks([task])
    asset = unreal.load_asset(f"{dest}/{name}")
    if not asset:
        raise RuntimeError(f"import failed: {path}")
    return asset


TEXTURES = {}


def texture(rel, kind):
    """A texture once, set up for its use: colour (sRGB), normal (OpenGL's green flipped), or a linear grey map."""
    if rel in TEXTURES:
        return TEXTURES[rel]
    name = "T_Shore_" + os.path.splitext(os.path.basename(rel))[0]
    t = import_file(os.path.join(REPO, rel), TEX, name)
    if kind == "normal":
        t.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        t.set_editor_property("srgb", False)
        t.set_editor_property("flip_green_channel", True)
    elif kind in ("rough", "alpha"):
        t.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
        t.set_editor_property("srgb", False)
    else:
        t.set_editor_property("srgb", True)
    EAL.save_loaded_asset(t)
    TEXTURES[rel] = t
    return t


def parent(name, foliage):
    """M_ShorePBR / M_ShoreFoliage: texture parameters into base colour, normal and roughness (and the opacity mask)."""
    path = f"{DEST}/{name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    m = ASSETS.create_asset(name, DEST, unreal.Material, unreal.MaterialFactoryNew())
    if foliage:
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        m.set_editor_property("two_sided", True)
    def sample(pname, sampler, y):
        e = MEL.create_material_expression(m, unreal.MaterialExpressionTextureSampleParameter2D, -500, y)
        e.set_editor_property("parameter_name", pname)
        e.set_editor_property("sampler_type", sampler)
        return e
    base = sample("BaseColor", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR, -300)
    normal = sample("Normal", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL, 0)
    rough = sample("Roughness", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, 300)
    MEL.connect_material_property(base, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(normal, "RGB", unreal.MaterialProperty.MP_NORMAL)
    MEL.connect_material_property(rough, "R", unreal.MaterialProperty.MP_ROUGHNESS)
    if foliage:
        alpha = sample("Alpha", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, 600)
        MEL.connect_material_property(alpha, "R", unreal.MaterialProperty.MP_OPACITY_MASK)
    m.set_editor_property("used_with_nanite", True)
    m.set_editor_property("used_with_instanced_static_meshes", True)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


manifest = json.load(open(os.path.join(MODELS, "shore.json")))
pbr = parent("M_ShorePBR", False)
foliage = parent("M_ShoreFoliage", True)
instances = {}
for name, piece in sorted(manifest.items()):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    mesh = import_file(os.path.join(MODELS, name + ".fbx"), DEST, name, ui)
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    mesh.set_editor_property("nanite_settings", ns)
    for index, sm in enumerate(mesh.get_editor_property("static_materials")):
        slot = str(sm.get_editor_property("material_slot_name"))
        key = next((k for k in piece["materials"] if slot.startswith(k)), None) or next(iter(piece["materials"]))
        if key not in instances:
            tex = piece["materials"][key]
            mi_name = "MI_Shore_" + "".join(w.capitalize() for w in key.split("_"))
            mi_path = f"{DEST}/{mi_name}"
            mi = unreal.load_asset(mi_path) if EAL.does_asset_exist(mi_path) else \
                ASSETS.create_asset(mi_name, DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            MEL.set_material_instance_parent(mi, foliage if "alpha" in tex else pbr)
            for pname, kind in (("BaseColor", "diff"), ("Normal", "normal"), ("Roughness", "rough"), ("Alpha", "alpha")):
                if kind in tex:
                    MEL.set_material_instance_texture_parameter_value(mi, pname, texture(tex[kind], kind))
            MEL.update_material_instance(mi)
            EAL.save_loaded_asset(mi)
            instances[key] = mi
        mesh.set_material(index, instances[key])
    EAL.save_loaded_asset(mesh)
    b = mesh.get_bounding_box()
    unreal.log(f"Imported {name}: {piece['tris']} tris, bounds {b.min} .. {b.max}")
unreal.log(f"Shore import done: {len(manifest)} meshes, {len(instances)} materials, {len(TEXTURES)} textures")
