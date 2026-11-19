"""Shore Track C (docs/envloop/shore-edges): imports the kit shore edge pieces (Tools/envloop/shore-edges/export_edges.py ->
Artifacts/models/edges/SM_Edge_*.fbx) into /Game/World/Edges with Nanite, builds M_ShoreEdge there from edge_layer.py's HLSL
(the same text the cloud renders run: the surface looks and the water's marks from height), and gives MPC_World the lake's
marks (PoolZ, HighZ, LowZ, WrackZ, Swash, metres) from the region pack. Its own script, never scripts/make_materials.py
(coordinator rule Nov 16 2026); the pack is data: EDGE_PACK=<name> (default north-texas-lake) picks the marks and colours.
Run by scripts/make-shore-edges.sh; EDGE_MATERIAL_ONLY=1 (its --material-only) rebuilds the material and the marks and puts the
material on the pieces already in /Game/World/Edges. Returns normally (on Windows os._exit leaves a zombie editor: docs/windows/README.md).
"""
import json
import os
import sys

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "Tools", "envloop", "shore-edges")
sys.path.insert(0, TOOLS)
import edge_layer as L  # noqa: E402  (no numpy at import: the editor's Python has none)

MODELS = os.path.join(REPO, "Artifacts", "models", "edges")
DEST = "/Game/World/Edges"
MPC = "/Game/World/MPC_World"
PACK = os.environ.get("EDGE_PACK", "north-texas-lake")
MATERIAL_ONLY = os.environ.get("EDGE_MATERIAL_ONLY") == "1"   # rebuild M_ShoreEdge and the marks on the pieces already imported
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary

MARKS = ("PoolZ", "HighZ", "LowZ", "WrackZ", "Swash")
NOISES = (("n003", "0.03", 3), ("n01", "0.10", 5), ("n05", "0.5", 7), ("n2", "2.0", 9), ("ns", "float3(0.04, 0.04, 0.7)", 13))


def load_pack(name):
    with open(os.path.join(TOOLS, "packs", name, "pack.json")) as f:
        return json.load(f)


def world_marks(pack):
    """MPC_World gets the pack's lake marks beside WaterZ (appended if missing, as make_materials.world_collection does; the
    defaults are the pack's: a region's marks are data)."""
    mpc = unreal.load_asset(MPC)
    if not mpc:
        raise RuntimeError(f"{MPC} missing: run scripts/make-content.sh first")
    scalars = list(mpc.get_editor_property("scalar_parameters"))
    for name in MARKS:
        value = float(pack["marks"][name])
        found = [x for x in scalars if str(x.get_editor_property("parameter_name")) == name]
        if found:
            found[0].set_editor_property("default_value", value)
        else:
            p = unreal.CollectionScalarParameter()
            p.set_editor_property("parameter_name", name)
            p.set_editor_property("default_value", value)
            scalars.append(p)
    mpc.set_editor_property("scalar_parameters", scalars)
    EAL.save_loaded_asset(mpc)
    return mpc


def node(mat, cls, x, y, **props):
    n = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def custom(mat, code, inputs, output_type, x, y, extra_outputs=()):
    c = node(mat, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", code)
    c.set_editor_property("output_type", output_type)
    ins = []
    for n in inputs:
        i = unreal.CustomInput()
        i.set_editor_property("input_name", n)
        ins.append(i)
    c.set_editor_property("inputs", ins)
    outs = []
    for n, t in extra_outputs:
        o = unreal.CustomOutput()
        o.set_editor_property("output_name", n)
        o.set_editor_property("output_type", t)
        outs.append(o)
    if outs:
        c.set_editor_property("additional_outputs", outs)
    return c


def edge_material(pack, mpc):
    """M_ShoreEdge: EDGE_LAYER_CODE in a Custom node. World position in metres (the map frame: MPC_World.RenderOrigin added
    back, as make_materials.node() does for every world position), the pieces' normal and vertex colour, metre UVs, five
    gradient noises computed in their own Custom nodes, the lake's marks from MPC_World (WaterZ is cm) and the pack's
    colours as vector parameters (a material instance per region could change them)."""
    path = f"{DEST}/M_ShoreEdge"
    if EAL.does_asset_exist(path):
        mat = unreal.load_asset(path)   # rebuilt in place: the imported pieces keep their reference to it
        MEL.delete_all_material_expressions(mat)
    else:
        mat = ASSETS.create_asset("M_ShoreEdge", DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("used_with_nanite", True)                     # the pieces are Nanite (the _Light twins are not)
    mat.set_editor_property("used_with_instanced_static_meshes", True)   # ALakeTerrainActor::PlaceShoreEdges lays them in ISMs
    # World position in map metres: (WorldPosition + RenderOrigin) * 0.01.
    wpos = node(mat, unreal.MaterialExpressionWorldPosition, -2000, -400)
    origin = node(mat, unreal.MaterialExpressionCollectionParameter, -2000, -300, collection=mpc, parameter_name="RenderOrigin")
    # A collection vector is float4; masked to rgb before the add, as make_materials.node() does (the position is LWC float3:
    # unmasked, D3D SM6 refuses "Arithmetic between types LWCVector3 and float4" and the pieces draw the default checker).
    omask = node(mat, unreal.MaterialExpressionComponentMask, -1900, -300, r=True, g=True, b=True, a=False)
    MEL.connect_material_expressions(origin, "", omask, "")
    add = node(mat, unreal.MaterialExpressionAdd, -1800, -350)
    MEL.connect_material_expressions(wpos, "", add, "A")
    MEL.connect_material_expressions(omask, "", add, "B")
    cm = node(mat, unreal.MaterialExpressionConstant, -1800, -250, r=0.01)
    wp = node(mat, unreal.MaterialExpressionMultiply, -1600, -350)
    MEL.connect_material_expressions(add, "", wp, "A")
    MEL.connect_material_expressions(cm, "", wp, "B")
    nrm = node(mat, unreal.MaterialExpressionVertexNormalWS, -1600, -150)
    vc = node(mat, unreal.MaterialExpressionVertexColor, -1600, -50)
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -1600, 50)
    inputs = ["WP", "Nw", "VC", "UVm"]
    wires = [(wp, "", "WP"), (nrm, "", "Nw"), (vc, "", "VC"), (uv, "", "UVm")]
    # The noises: one Custom node a scale on the same position.
    for k, (name, scale, seed) in enumerate(NOISES):
        n = custom(mat, L.EDGE_NOISE_CODE.format(scale=scale, seed=seed), ["P"], unreal.CustomMaterialOutputType.CMOT_FLOAT1, -1300, -400 + 120 * k)
        MEL.connect_material_expressions(wp, "", n, "P")
        inputs.append(name)
        wires.append((n, "", name))
    # The lake's marks (metres) and the water now (cm in MPC_World: the prelude scales it).
    for k, name in enumerate(("WaterZ",) + MARKS):
        p = node(mat, unreal.MaterialExpressionCollectionParameter, -1300, 300 + 80 * k, collection=mpc, parameter_name=name)
        inputs.append(name + "_in" if name == "WaterZ" else name)
        wires.append((p, "", name + "_in" if name == "WaterZ" else name))
    # The colours: vector parameters with the pack's values (linear albedo).
    prelude = ["float3 WP = WPin;", "float WaterZ = WaterZ_in * 0.01;"]
    inputs[0] = "WPin"
    wires[0] = (wp, "", "WPin")
    for k, (name, rgb) in enumerate(sorted(pack["colours"].items())):
        p = node(mat, unreal.MaterialExpressionVectorParameter, -1000 + 200 * (k % 3), 400 + 60 * (k // 3), parameter_name=name,
                 default_value=unreal.LinearColor(float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0))
        inputs.append(name + "_in")
        wires.append((p, "", name + "_in"))   # the RGBA output: a vector parameter wired as float4, taken .rgb in the prelude
        prelude.append(f"float3 {name} = {name}_in.rgb;")
    code = "\n".join(prelude) + "\n" + L.EDGE_LAYER_CODE + "\nRough = r;\nWet = wet;\nreturn c;\n"
    c = custom(mat, code, inputs, unreal.CustomMaterialOutputType.CMOT_FLOAT3, -300, 0,
               [("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1), ("Wet", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    for src, out, pin in wires:
        MEL.connect_material_expressions(src, out, c, pin)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    unreal.log(f"Built M_ShoreEdge from pack {pack['pack']} ({len(pack['colours'])} colours)")
    return mat


def import_fbx(path, dest, name):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    ASSETS.import_asset_tasks([task])
    mesh = unreal.load_asset(f"{dest}/{name}")
    if not mesh:
        raise RuntimeError(f"import failed: {path}")
    return mesh


def rematerial(mat):
    """EDGE_MATERIAL_ONLY: the imported pieces get the rebuilt material on every slot and are saved (a belt to the braces of
    rebuilding it in place); no Blender, no FBX."""
    count = 0
    for path in EAL.list_assets(DEST, recursive=False, include_folder=False):
        name = path.rsplit("/", 1)[-1].split(".")[0]
        if not name.startswith("SM_Edge_"):
            continue
        mesh = unreal.load_asset(path)
        for index in range(len(mesh.get_editor_property("static_materials"))):
            mesh.set_material(index, mat)
        EAL.save_loaded_asset(mesh)
        count += 1
    unreal.log(f"Gave {count} shore edge pieces in {DEST} the rebuilt M_ShoreEdge")


def main():
    pack = load_pack(PACK)
    mpc = world_marks(pack)
    mat = edge_material(pack, mpc)
    if MATERIAL_ONLY:
        rematerial(mat)
        return
    count = 0
    for f in sorted(os.listdir(MODELS)) if os.path.isdir(MODELS) else []:
        if not (f.startswith("SM_Edge_") and f.endswith(".fbx")):
            continue
        name = f[:-4]
        mesh = import_fbx(os.path.join(MODELS, f), DEST, name)
        ns = mesh.get_editor_property("nanite_settings")
        ns.set_editor_property("enabled", not name.endswith("_Light"))
        mesh.set_editor_property("nanite_settings", ns)
        for index in range(len(mesh.get_editor_property("static_materials"))):
            mesh.set_material(index, mat)
        EAL.save_loaded_asset(mesh)
        count += 1
    unreal.log(f"Imported {count} shore edge pieces into {DEST}")


main()
