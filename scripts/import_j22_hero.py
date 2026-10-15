"""Boats 10: imports the script-built hero J/22 (Inputs/j22-hero: fbx/SM_J22H_{Hull,Mast,Boom,Rudder}.fbx, J22H_sockets.json,
the baked textures and materials.json) into /Game/Boats/J22Hero beside the game's J/22, which it leaves untouched.
The four parts are imported as import_boats.py imports a boat (Nanite on the rigid parts, sockets measured off the
hero's fittings, relative to each part's pivot). Materials:
  - textured groups (Hull, DeckMould, Rudder, Teak): MI_J22H_<group> on M_J22HeroSurface, the baked base colour, roughness and
    normal maps (OpenGL normals: green flipped on import);
  - flat ones (hardware, ropes, gelcoat): MI_J22H_<name> on M_BoatSurface with the values from materials.json;
  - the mast's aluminium: MI_Boat_MastAluminium, so the game's mast bend (M_BoatMast) still works.
The game draws it with -SailingJ22Hero (ASailboatPawn::ModelMeshesFor). Run in the editor: scripts\\windows\\run-python.ps1
import_j22_hero.py (after a build; make_materials.py's boat library must exist)."""
import json
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "Inputs", "j22-hero")
DEST = "/Game/Boats/J22Hero"
TEX = f"{DEST}/Textures"
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
META = json.load(open(os.path.join(SRC, "materials.json")))


def import_texture(path, kind):
    name = os.path.splitext(os.path.basename(path))[0]
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", TEX)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    ASSETS.import_asset_tasks([task])
    tex = unreal.load_asset(f"{TEX}/{name}")
    if kind == "N":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("flip_green_channel", True)   # baked OpenGL style (green up)
    elif kind == "R":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
        tex.set_editor_property("srgb", False)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return tex


def node(mat, cls, x, y):
    return MEL.create_material_expression(mat, cls, x, y)


def hero_material(defaults):
    """M_J22HeroSurface: the baked maps (a slab via the legacy pins; Substrate converts them). Each texture parameter needs a
    default of its own sampler type or the material fails to compile (and draws the engine's grid): the hull's maps."""
    path = f"{DEST}/M_J22HeroSurface"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset("M_J22HeroSurface", DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("two_sided", True)   # like M_BoatSurface: the generated shells aren't all wound outward
    samplers = {}
    for i, (pname, stype) in enumerate((("BaseColor", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
                                         ("Roughness", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE),
                                         ("Normal", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL))):
        t = node(mat, unreal.MaterialExpressionTextureSampleParameter2D, -600, i * 260)
        t.set_editor_property("parameter_name", pname)
        t.set_editor_property("sampler_type", stype)
        t.set_editor_property("texture", defaults[pname])
        samplers[pname] = t
    MEL.connect_material_property(samplers["BaseColor"], "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(samplers["Roughness"], "R", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(samplers["Normal"], "RGB", unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


def instance(name, parent):
    path = f"{DEST}/{name}"
    mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
        ASSETS.create_asset(name, DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    return mi


def materials():
    names = {"D": "BaseColor", "R": "Roughness", "N": "Normal"}
    textures = {group: {names[k]: import_texture(os.path.join(SRC, "textures", f), k) for k, f in maps.items() if f}
                for group, maps in META["groups"].items()}
    hero = hero_material(textures["Hull"])
    out = {}
    for group in META["groups"]:
        mi = instance(f"MI_J22H_{group}", hero)
        for pname, tex in textures[group].items():
            MEL.set_material_instance_texture_parameter_value(mi, pname, tex)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[group] = mi
    surface = unreal.load_asset("/Game/Boats/Materials/M_BoatSurface")
    for name, v in META["flat_materials"].items():
        mi = instance(f"MI_J22H_{name}", surface)
        c = v["base_color_linear"]
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(c[0], c[1], c[2], 1.0))
        gel = "Gelcoat" in name or name in ("HatchAcrylic", "TeakVarnish")
        for pname, value in (("Roughness", v["roughness"]), ("Metallic", v["metallic"]), ("ClearCoat", 1.0 if gel else 0.0),
                             ("NonSkid", 0.0), ("Porosity", 0.1), ("IsHull", 0.0)):
            MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[name] = mi
    return out


def import_fbx(path, name):
    asset_path = f"{DEST}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("remove_degenerates", True)
    data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", DEST)
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


def main():
    mats = materials()
    mast_alu = unreal.load_asset("/Game/Boats/Materials/MI_Boat_MastAluminium")
    meta = json.load(open(os.path.join(SRC, "J22H_sockets.json")))
    missing = set()
    for part, nanite in (("Hull", True), ("Mast", False), ("Boom", True), ("Rudder", True)):
        name = f"SM_J22H_{part}"
        mesh = import_fbx(os.path.join(SRC, "fbx", name + ".fbx"), name)
        ns = mesh.get_editor_property("nanite_settings")
        ns.set_editor_property("enabled", nanite)
        mesh.set_editor_property("nanite_settings", ns)
        for index, m in enumerate(mesh.get_editor_property("static_materials")):
            slot = str(m.get_editor_property("material_slot_name")).split(".")[0]
            key = slot[len("J22H_"):] if slot.startswith("J22H_") else slot   # the textured groups' slots are J22H_<group>
            mi = mast_alu if (part == "Mast" and slot == "Aluminium") else mats.get(key)
            if mi is None:
                mi = unreal.load_asset(f"/Game/Boats/Materials/MI_Boat_{slot}")
            if mi is None:
                missing.add(slot)
                continue
            mesh.set_material(index, mi)
        origin = meta["origins"][name]
        n = 0
        for sname, p in meta["sockets"].items():
            if meta["owner"][sname] != name:
                continue
            sock = unreal.StaticMeshSocket(mesh)
            sock.set_editor_property("socket_name", sname)
            sock.set_editor_property("relative_location", unreal.Vector(p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]))
            mesh.add_socket(sock)
            n += 1
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        b = mesh.get_bounding_box()
        unreal.log(f"Hero imported {name}: {n} sockets, Nanite {nanite}, {len(mesh.get_editor_property('static_materials'))} slots, bounds {b.min} .. {b.max}")
    if missing:
        raise RuntimeError(f"Hero J/22: no material for slots {sorted(missing)}")
    unreal.log("Hero import done")


# No os._exit here: on Windows it trips the crash reporter, and an editor killed in that state lingers holding its files
# until a reboot. The import is small; the commandlet exits on its own.
main()
