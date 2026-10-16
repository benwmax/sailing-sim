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

# Boat detail pass: the baked groups also carry a detail mask (T_J22H_<group>_X: R non-skid, G teak, B smooth gelcoat)
# and their metres per UV unit (materials.json uv_m); M_J22HeroSurface tiles the close-up detail textures from
# /Game/Boats/Detail (scripts/import_boat_detail.py, run first) over the baked maps and fades them out by 6 m. The cabin
# interior (SM_J22H_Interior, Nanite) and the glass (SM_J22H_Glass: portlights, fore hatch, bilge water; translucent,
# not Nanite) are imported beside the four parts.
DETAIL = "/Game/Boats/Detail"
DETAIL_META = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Inputs", "boat-detail", "detail_textures.json")))

DETAIL_CODE = r"""
float fade = 1.0 - saturate((Depth - 150.0) / 450.0);       // cm: full detail to 1.5 m, gone by 6 m
float ns = X.r * fade, tk = X.g * fade, gc = X.b * fade;
float3 c = Base;
c *= lerp(1.0, lerp(0.70, 1.06, NSM.r), ns);                 // grime in the non-skid's grooves, clean tops
c *= lerp(1.0, lerp(0.72, 1.15, TKM.r), tk);                 // weathered teak: pale latewood, dark checks
Rough = saturate(R + ns * (0.12 * (1.0 - NSM.r) - 0.15 * NSM.g) + gc * (GCM.g - 0.5) * 0.15 + tk * 0.1 * TKM.g);
float3 d = float3(0.0, 0.0, 1.0);
d = lerp(d, NSN, ns);
d = lerp(d, GCN, gc);
d = lerp(d, TKN, tk);
NormalOut = normalize(float3(N.xy + d.xy, N.z * d.z));      // whiteout blend over the baked normal
return c;
"""

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
    elif kind == "X":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        tex.set_editor_property("srgb", False)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return tex


def node(mat, cls, x, y):
    return MEL.create_material_expression(mat, cls, x, y)


def hero_material(defaults):
    """M_J22HeroSurface: the baked maps (a slab via the legacy pins; Substrate converts them) with the close-up detail
    layer on top. Each texture parameter needs a default of its own sampler type or the material fails to compile (and
    draws the engine's grid): the hull's maps."""
    path = f"{DEST}/M_J22HeroSurface"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset("M_J22HeroSurface", DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("two_sided", True)   # like M_BoatSurface: the generated shells aren't all wound outward
    mat.set_editor_property("used_with_nanite", True)  # the hero meshes are Nanite
    samplers = {}
    for i, (pname, stype) in enumerate((("BaseColor", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
                                         ("Roughness", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE),
                                         ("Normal", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL),
                                         ("DetailMask", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS))):
        t = node(mat, unreal.MaterialExpressionTextureSampleParameter2D, -900, i * 260)
        t.set_editor_property("parameter_name", pname)
        t.set_editor_property("sampler_type", stype)
        t.set_editor_property("texture", defaults[pname])
        samplers[pname] = t
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -1500, 1100)
    uvm = node(mat, unreal.MaterialExpressionScalarParameter, -1500, 1250)
    uvm.set_editor_property("parameter_name", "UVMetres")
    uvm.set_editor_property("default_value", 1.0)
    detail = {}
    for k, (name, tile_key) in enumerate((("NonSkid", "NonSkid"), ("Gelcoat", "Gelcoat"), ("TeakWeathered", "TeakWeathered"))):
        tile = DETAIL_META[tile_key]["tile_m"]
        scale = node(mat, unreal.MaterialExpressionMultiply, -1300, 1100 + k * 300)
        MEL.connect_material_expressions(uv, "", scale, "A")
        per = node(mat, unreal.MaterialExpressionMultiply, -1300, 1200 + k * 300)
        MEL.connect_material_expressions(uvm, "", per, "A")
        inv = node(mat, unreal.MaterialExpressionConstant2Vector, -1500, 1400 + k * 300)
        inv.set_editor_property("r", 1.0 / tile[0])
        inv.set_editor_property("g", 1.0 / tile[1])
        MEL.connect_material_expressions(inv, "", per, "B")
        MEL.connect_material_expressions(per, "", scale, "B")
        for kind, stype in (("N", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL), ("M", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)):
            t = node(mat, unreal.MaterialExpressionTextureSample, -1100, 1100 + k * 300 + (0 if kind == "N" else 140))
            t.set_editor_property("texture", unreal.load_asset(f"{DETAIL}/T_Detail_{name}_{kind}"))
            t.set_editor_property("sampler_type", stype)
            MEL.connect_material_expressions(scale, "", t, "UVs")
            detail[name + kind] = t
    depth = node(mat, unreal.MaterialExpressionPixelDepth, -900, 1100)
    c = node(mat, unreal.MaterialExpressionCustom, -500, 400)
    c.set_editor_property("code", DETAIL_CODE)
    c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = ["Base", "R", "N", "X", "Depth", "NSN", "NSM", "GCN", "GCM", "TKN", "TKM"]
    ins = []
    for pn in pins:
        i = unreal.CustomInput()
        i.set_editor_property("input_name", pn)
        ins.append(i)
    c.set_editor_property("inputs", ins)
    outs = []
    for on, ot in (("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1), ("NormalOut", unreal.CustomMaterialOutputType.CMOT_FLOAT3)):
        o = unreal.CustomOutput()
        o.set_editor_property("output_name", on)
        o.set_editor_property("output_type", ot)
        outs.append(o)
    c.set_editor_property("additional_outputs", outs)
    for src, out, pin in ((samplers["BaseColor"], "RGB", "Base"), (samplers["Roughness"], "R", "R"), (samplers["Normal"], "RGB", "N"),
                          (samplers["DetailMask"], "RGB", "X"), (depth, "", "Depth"),
                          (detail["NonSkidN"], "RGB", "NSN"), (detail["NonSkidM"], "RGB", "NSM"),
                          (detail["GelcoatN"], "RGB", "GCN"), (detail["GelcoatM"], "RGB", "GCM"),
                          (detail["TeakWeatheredN"], "RGB", "TKN"), (detail["TeakWeatheredM"], "RGB", "TKM")):
        MEL.connect_material_expressions(src, out, c, pin)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(c, "NormalOut", unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


def glass_material():
    """M_J22HeroGlass: smoked acrylic portlights and hatch, and the bilge water (translucent, lit at the surface)."""
    path = f"{DEST}/M_J22HeroGlass"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset("M_J22HeroGlass", DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    mat.set_editor_property("two_sided", True)
    col = node(mat, unreal.MaterialExpressionVectorParameter, -500, 0)
    col.set_editor_property("parameter_name", "Color")
    col.set_editor_property("default_value", unreal.LinearColor(0.03, 0.028, 0.025, 1.0))
    op = node(mat, unreal.MaterialExpressionScalarParameter, -500, 200)
    op.set_editor_property("parameter_name", "Opacity")
    op.set_editor_property("default_value", 0.55)
    rough = node(mat, unreal.MaterialExpressionConstant, -500, 300)
    rough.set_editor_property("r", 0.04)
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
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
    names = {"D": "BaseColor", "R": "Roughness", "N": "Normal", "X": "DetailMask"}
    textures = {group: {names[k]: import_texture(os.path.join(SRC, "textures", f), k) for k, f in maps.items() if f and k in names}
                for group, maps in META["groups"].items()}
    hero = hero_material(textures["Hull"])
    out = {}
    for group in META["groups"]:
        mi = instance(f"MI_J22H_{group}", hero)
        for pname, tex in textures[group].items():
            MEL.set_material_instance_texture_parameter_value(mi, pname, tex)
        MEL.set_material_instance_scalar_parameter_value(mi, "UVMetres", META["groups"][group].get("uv_m", 1.0))
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[group] = mi
    surface = unreal.load_asset("/Game/Boats/Materials/M_BoatSurface")
    glass = glass_material()
    for name, opacity in (("PortlightAcrylic", 0.8), ("HatchAcrylic", 0.6), ("WaterBilge", 0.7)):
        mi = instance(f"MI_J22H_{name}", glass)
        MEL.set_material_instance_scalar_parameter_value(mi, "Opacity", opacity)
        if name == "WaterBilge":
            MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(0.06, 0.055, 0.03, 1.0))
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[name] = mi
    for name, v in META["flat_materials"].items():
        if name in out:
            continue
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
    for part, nanite in (("Hull", True), ("Mast", False), ("Boom", True), ("Rudder", True), ("Interior", True), ("Glass", False)):
        name = f"SM_J22H_{part}"
        if part in ("Interior", "Glass") and not os.path.exists(os.path.join(SRC, "fbx", name + ".fbx")):
            continue                     # an import from before the detail pass
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
        origin = meta["origins"].get(name, [0.0, 0.0, 0.0])
        n = 0
        for sname, p in meta["sockets"].items():
            # The game hangs the rudder from the hull's RudderPivot (BuildModelVisuals); the hero lists it on the rudder,
            # so it goes on the hull too. Socket positions in the JSON are in the boat's frame, so relative to the hull's
            # origin it is the same point.
            on_hull_too = sname == "RudderPivot" and name == "SM_J22H_Hull"
            if meta["owner"][sname] != name and not on_hull_too:
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
