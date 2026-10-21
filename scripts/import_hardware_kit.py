"""Boat fidelity 2 (docs/boat-fidelity-2): imports the deck hardware kit (Tools/boatkit/build_kit.py's FBX, built by
scripts/make-boatkit.sh or scripts\\windows\\make-boatkit.ps1 into Artifacts/boatkit/kit) into /Game/Boats/Kit:

  SM_Kit_<Part>         the hero, Nanite
  SM_Kit_<Part>_Light   the decimated copy, not Nanite (the Mac's Medium and Low)
  M_BoatKit             one lit material over the shared trim sheet (Inputs/boat-kit/T_KitTrim_N/_M, 10 px/cm, by UV0):
                        the slot's colour darkened in the sheet's cavities, white in paint-filled engravings (the made-up
                        TERNWAY plates), roughness nudged by the sheet, the sheet's normal
  MI_Kit_<Slot>         one instance per slot name the kit uses, with that slot's colour, roughness and metalness from
                        make_materials.py's BOAT_LIBRARY (phase 1's surface kinds)

Sockets come from the FBX's SOCKET_* empties; any the importer missed are added from kit.json. Inputs/boat-kit/kit.json
(copied from the build) is what SailingSim.Visual.HardwareKit checks the import against. Nothing is placed on a boat yet:
fitting the kit to the J/22 is phase 3.

Run in the editor after a build: scripts\\windows\\run-python.ps1 import_hardware_kit.py   (KIT_DIR overrides the source;
KIT_ONLY=A,B imports just those parts).
"""
import ast
import json
import os
import shutil

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("KIT_DIR") or os.path.join(REPO, "Artifacts", "boatkit", "kit")
INPUTS = os.path.join(REPO, "Inputs", "boat-kit")
DEST = "/Game/Boats/Kit"
TEX = f"{DEST}/Textures"
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
ONLY = [n for n in os.environ.get("KIT_ONLY", "").split(",") if n]


def boat_library():
    tree = ast.parse(open(os.path.join(REPO, "scripts", "make_materials.py")).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "BOAT_LIBRARY":
            return ast.literal_eval(node.value)
    raise RuntimeError("BOAT_LIBRARY not found in make_materials.py")


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
    tex.set_editor_property("srgb", False)
    if kind == "N":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("flip_green_channel", True)      # made OpenGL style (green up)
    else:
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return tex


def node(mat, cls, x, y, **props):
    n = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def connect(a, a_out, b, b_in):
    if not MEL.connect_material_expressions(a, a_out, b, b_in):
        raise RuntimeError(f"connect failed: {a.get_name()}.{a_out} -> {b.get_name()}.{b_in}")


KIT_CODE = r"""
// Boat fidelity 2: the hardware kit on its trim sheet (Tools/boatkit/make_trim_sheet.py). M: R cavity, G roughness offset,
// B paint fill (engraved maker's plates).
float3 c = C.rgb * lerp(1.0, M.r, 0.6);
c = lerp(c, float3(0.85, 0.85, 0.82), M.b);
Rough = saturate(R + (M.g - 0.5) * 0.5);
return c;
"""


def kit_material(normal, mask):
    path = f"{DEST}/M_BoatKit"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset("M_BoatKit", DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("two_sided", True)       # like M_BoatSurface: a few kit shells are open (the handle pocket)
    mat.set_editor_property("used_with_nanite", True)
    col = node(mat, unreal.MaterialExpressionVectorParameter, -900, -100, parameter_name="Color", default_value=unreal.LinearColor(0.6, 0.6, 0.62, 1))
    rough = node(mat, unreal.MaterialExpressionScalarParameter, -900, 50, parameter_name="Roughness", default_value=0.35)
    metal = node(mat, unreal.MaterialExpressionScalarParameter, -900, 150, parameter_name="Metallic", default_value=0.0)
    tn = node(mat, unreal.MaterialExpressionTextureSampleParameter2D, -900, 300, parameter_name="TrimNormal", texture=normal,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    tm = node(mat, unreal.MaterialExpressionTextureSampleParameter2D, -900, 560, parameter_name="TrimMask", texture=mask,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    c = node(mat, unreal.MaterialExpressionCustom, -500, 0, code=KIT_CODE, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    ins = []
    for pn in ("C", "R", "M"):
        i = unreal.CustomInput()
        i.set_editor_property("input_name", pn)
        ins.append(i)
    c.set_editor_property("inputs", ins)
    o = unreal.CustomOutput()
    o.set_editor_property("output_name", "Rough")
    o.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    c.set_editor_property("additional_outputs", [o])
    connect(col, "RGBA", c, "C")
    connect(rough, "", c, "R")
    connect(tm, "RGBA", c, "M")
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    MEL.connect_material_property(tn, "RGB", unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


def kit_instances(parent, slots):
    lib = boat_library()
    out = {}
    for slot in sorted(slots):
        _, col, rough, metal, _, _, _ = lib[slot]
        name = f"MI_Kit_{slot}"
        path = f"{DEST}/{name}"
        mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
            ASSETS.create_asset(name, DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, parent)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(col[0], col[1], col[2], 1.0))
        MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", metal)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[slot] = mi
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


def finish_mesh(mesh, nanite, mats, sockets):
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", nanite)
    mesh.set_editor_property("nanite_settings", ns)
    for index, m in enumerate(mesh.get_editor_property("static_materials")):
        slot = str(m.get_editor_property("material_slot_name")).split(".")[0]
        if slot not in mats:
            raise RuntimeError(f"{mesh.get_name()}: no MI_Kit_ for slot {slot}")
        mesh.set_material(index, mats[slot])
    have = {name for name in sockets if mesh.find_socket(name)}
    added = 0
    for name, p in sockets.items():
        if name in have:
            continue
        # Blender's +Y is the kit's port side; the FBX import mirrors Y into Unreal's left-handed frame.
        sock = unreal.StaticMeshSocket(mesh)
        sock.set_editor_property("socket_name", name)
        sock.set_editor_property("relative_location", unreal.Vector(p[0] * 100.0, -p[1] * 100.0, p[2] * 100.0))
        mesh.add_socket(sock)
        added += 1
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    return len(have), added


def main():
    kit = json.load(open(os.path.join(SRC, "kit.json")))
    normal = import_texture(os.path.join(INPUTS, "T_KitTrim_N.png"), "N")
    mask = import_texture(os.path.join(INPUTS, "T_KitTrim_M.png"), "M")
    parent = kit_material(normal, mask)
    mats = kit_instances(parent, {s for info in kit.values() for s in info["slots"]})
    for part, info in kit.items():
        if ONLY and part not in ONLY:
            continue
        for suffix, nanite in (("", True), ("_Light", False)):
            name = f"SM_Kit_{part}{suffix}"
            mesh = import_fbx(os.path.join(SRC, "fbx", name + ".fbx"), name)
            had, added = finish_mesh(mesh, nanite, mats, info["sockets"])
            unreal.log(f"Kit imported {name}: Nanite {nanite}, {len(mesh.get_editor_property('static_materials'))} slots, "
                       f"{had} sockets from the FBX, {added} added from kit.json")
    if not ONLY:
        shutil.copyfile(os.path.join(SRC, "kit.json"), os.path.join(INPUTS, "kit.json"))
    unreal.log(f"Kit import done: {len(kit)} parts")


# No os._exit (it leaves zombie editors on Windows): the commandlet exits on its own.
main()
