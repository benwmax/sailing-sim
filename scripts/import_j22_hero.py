"""Boats 10: imports the script-built hero J/22 (Inputs/j22-hero: fbx/SM_J22H_{Hull,Mast,Boom,Rudder}.fbx, J22H_sockets.json,
the baked textures and materials.json) into /Game/Boats/J22Hero beside the game's J/22, which it leaves untouched.
The four parts are imported as import_boats.py imports a boat (Nanite on the rigid parts, sockets measured off the
hero's fittings, relative to each part's pivot). Materials:
  - textured groups (Hull, DeckMould, Rudder, Teak): MI_J22H_<group> on M_J22HeroSurface, the baked base colour, roughness and
    normal maps (OpenGL normals: green flipped on import);
  - flat ones (hardware, ropes, gelcoat): MI_J22H_<name> on M_BoatSurface with the values from materials.json;
  - the mast's aluminium: MI_Boat_MastAluminium, so the game's mast bend (M_BoatMast) still works.
The game draws it as the player's J/22 (ASailboatPawn::ModelMeshesFor; -SailingClassicJ22 for the older model). Run in the editor: scripts\\windows\\run-python.ps1
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
// Boat fidelity 1 (docs/boat-fidelity-1), as M_BoatSurface does it: the boat's age and care (Age -1 = unset: the livery's
// oxidation channel, Wear.x, at half weight, since the bake carries the club boat's own wear) chalk the smooth gelcoat
// (more on the sun-facing tops), and the hull is wet up to the splash line and the deck with rain and spray (MPC_Boat):
// darker by each surface's porosity (gelcoat 0.1, non-skid 0.5, teak 0.6), water standing in the non-skid's grooves,
// glossy. (A sunlit white deck sits on the tone curve's shoulder, so these read smaller on screen than in albedo.)
float ageK = Age >= 0.0 ? saturate(Age / 20.0) * (1.0 - 0.6 * saturate(Care)) : 0.5 * Wear.x;
float3 nw = normalize(NW);
nw *= dot(nw, V) < 0.0 ? -1.0 : 1.0;          // two-sided: the generated shells (the cockpit sole) aren't all wound outward
float up = saturate((nw.z - 0.4) * 2.5);
float gcAll = X.b * (1.0 - X.r) * (1.0 - X.g);
float ox = ageK * gcAll * (0.55 + 0.45 * up);
float lum = dot(c, float3(0.3, 0.59, 0.11));
c = lerp(c, lerp(float3(lum, lum, lum), float3(0.80, 0.77, 0.66), 0.6), 0.6 * ox);   // chalky and a little yellowed
Rough = lerp(Rough, 0.75, ox);
c *= 1.0 - 0.3 * ageK * X.r * up;                  // grime worked into the non-skid where feet go
c *= 1.0 - 0.25 * ageK * X.g;                      // teak greys and darkens
float streak = 0.5 + 0.5 * sin(WP.x * 0.21 + sin(WP.x * 0.047) * 3.0);
// (Clipping audit 2, as M_BoatSurface: at most 6 cm of ragged edge, half of it slow noise, softer as the band grows.)
float wlx = WP.x / 110.0, wli = floor(wlx), wlf = frac(wlx);
wlf = wlf * wlf * (3.0 - 2.0 * wlf);
float wln = lerp(frac(sin(wli * 37.13) * 43758.5), frac(sin((wli + 1.0) * 37.13) * 43758.5), wlf);
float wetLine = WaterZ + WetBand * 0.8 + min(WetBand * 0.4, 6.0) * (1.2 * streak + 0.8 * wln - 1.0);
float wetEdge = 3.0 + 0.1 * WetBand;
float wet = (1.0 - smoothstep(wetLine - wetEdge, wetLine + wetEdge, WP.z)) * (1.0 - up);
float wetAll = saturate(max(wet, saturate(DeckWet) * up * 0.8));
// Spray hull (docs/spray-hull), as M_BoatSurface: a water film below the wet line (a fifth darker), beads in its top
// 8 cm and spattered above it after spray (SprayWet), drips running down from the line; glossy where wet.
float below = wetLine - WP.z;
float2 bq = float2(WP.x + WP.y, WP.z) / 0.9;
float2 bf = frac(bq) - 0.5;
float bh = frac(sin(dot(floor(bq), float2(17.31, 91.7))) * 43758.5), br = 0.18 + 0.2 * frac(bh * 7.13);
float beadAt = (1.0 - smoothstep(br - 0.06, br, length(bf))) * step(0.4, bh);
float spatter = saturate(SprayWet) * (1.0 - smoothstep(0.0, 30.0 + 40.0 * saturate(SprayWet), -below)) * step(below, 0.0);
float bead = beadAt * (1.0 - up) * max(wet * (1.0 - smoothstep(0.0, 8.0, below)), spatter * step(0.8, bh));
float dlane = (WP.x + WP.y * 0.7) / 1.6;
float dh = frac(sin(floor(dlane) * 37.7) * 4375.5);
float drip = wet * step(0.7, dh) * (1.0 - smoothstep(0.04, 0.14, abs(frac(dlane) - 0.5))) * (1.0 - smoothstep(3.0, 3.0 + 14.0 * frac(dh * 3.7), below));
c *= 1.0 - 0.20 * wet - 0.10 * drip;
wetAll = saturate(max(wetAll, max(bead, drip)));
float porosity = lerp(lerp(0.1, 0.5, X.r), 0.6, X.g);
c *= lerp(1.0, 1.0 - 0.55 * porosity, wetAll) * (1.0 - 0.45 * ns * (1.0 - NSM.r) * wetAll);
Rough = lerp(Rough, lerp(0.06, Rough, 0.25 + 0.4 * X.r), wetAll);
// Rain deck (docs/rain-deck), as M_BoatSurface: puddles in the deck's and sole's low spots (value noise lows on level
// surfaces, filling with Puddle) are dark mirrors; rain rings them and the wet deck, and beads level gelcoat.
float2 pq = WP.xy / 37.0;
float2 pci = floor(pq), pf = frac(pq);
pf = pf * pf * (3.0 - 2.0 * pf);
float p00 = frac(sin(dot(pci, float2(12.99, 78.23))) * 43758.5), p10 = frac(sin(dot(pci + float2(1, 0), float2(12.99, 78.23))) * 43758.5);
float p01 = frac(sin(dot(pci + float2(0, 1), float2(12.99, 78.23))) * 43758.5), p11 = frac(sin(dot(pci + float2(1, 1), float2(12.99, 78.23))) * 43758.5);
float pn = lerp(lerp(p00, p10, pf.x), lerp(p01, p11, pf.x), pf.y);
float level = saturate((nw.z - 0.92) * 12.5);
float pudK = level * (1.0 - smoothstep(Puddle * 0.62 - 0.04, Puddle * 0.62 + 0.02, pn)) * step(0.02, Puddle);
float rainK = saturate(Rain);
NormalOut = normalize(lerp(NormalOut, float3(0.0, 0.0, 1.0), pudK));   // a puddle is flat water
// rain-fade, as M_BoatSurface: rings and beads fade out from 2 to 3 m and are skipped past it; puddles stay.
float rfade = rainK * (1.0f - saturate((Depth - 200.0f) / 100.0f));
float rring = 0.0f, rbead = 0.0f;
[branch] if (rfade > 0.0f)
{
    // (A drop every 14 cm cell, its ring out to 5 cm and 6 mm wide: at 22 cm, 7 cm and 3.5 mm they were under a pixel from the
    // cockpit.) The ring bends the normal outward, which is what shows on a puddle: the reflection wobbles.
    float2 rc = WP.xy / 14.0;
    float2 rcf = frac(rc) - 0.5;
    float rh = frac(sin(dot(floor(rc), float2(41.7, 19.3))) * 43758.5);
    float rph = frac(Time * (1.1 + 0.5 * rh) + rh * 7.0);
    float2 rto = rcf - (float2(frac(rh * 13.1), frac(rh * 5.7)) * 0.5 - 0.25);
    float rdist = length(rto) * 14.0;
    rring = exp(-pow((rdist - rph * 5.0) / 0.6, 2.0)) * (1.0 - rph) * rfade * max(pudK, 0.5 * saturate(DeckWet) * up);
    NormalOut = normalize(NormalOut + float3(rto / max(length(rto), 1e-3) * rring * 1.2, 0.0));
    float2 rbf = frac(WP.xy / 0.8) - 0.5;
    float rbh = frac(sin(dot(floor(WP.xy / 0.8), float2(23.17, 61.3))) * 43758.5);
    rbead = (1.0 - smoothstep(0.14 + 0.16 * rbh, 0.2 + 0.16 * rbh, length(rbf))) * step(0.5, rbh) * rfade * (1.0 - pudK) * level * gcAll;
}
c *= (1.0 - 0.3 * pudK) * (1.0 + 0.6 * rring);
Rough = lerp(Rough, 0.015, saturate(pudK + rbead));
Rough = lerp(Rough, 0.12, rring);
Rough = lerp(Rough, 0.02, bead);                                  // a bead is a lens: a sharp glint
// docs/lee-topside-patch/: Lumen's screen traces run before the sea (Single Layer Water) is drawn, so a mirror reflection
// pointing down into it found the hull and keel under the water: a dark dome on the lee topsides of a heeled boat. Where
// the reflection points below the horizon the gelcoat is rough enough (0.45) that Lumen takes its radiance cache, the
// sea's soft sky light, instead.
float3 rv = reflect(-V, nw);
Rough = lerp(Rough, max(Rough, 0.45), saturate(-rv.z * 3.0));
return c;
"""

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "Inputs", "j22-hero")
DEST = "/Game/Boats/J22Hero"
TEX = f"{DEST}/Textures"
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
META = json.load(open(os.path.join(SRC, "materials.json")))
PACKS = {k: v for k, v in json.load(open(os.path.join(SRC, "J22H_packs.json"))).items() if not k.startswith("_")}
MATERIALS_ONLY = os.environ.get("HERO_MATERIALS_ONLY") == "1"


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
    # Boat texture budget (docs/boat-tex-medium): the Vehicle groups (their device-profile sizes keep the hero boat inside Medium's 24 MB).
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_VEHICLE_NORMAL_MAP if kind == "N" else unreal.TextureGroup.TEXTUREGROUP_VEHICLE)
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
    # Boat fidelity 1: the wear (the pawn's per-boat Wear on every hull slot, Age and Care) and MPC_Boat's wetness.
    extra = {}
    for pname, default, y in (("Age", -1.0, 1900), ("Care", 0.5, 1980)):
        p = node(mat, unreal.MaterialExpressionScalarParameter, -900, y)
        p.set_editor_property("parameter_name", pname)
        p.set_editor_property("default_value", default)
        extra[pname] = (p, "")
    wear = node(mat, unreal.MaterialExpressionVectorParameter, -900, 2060)
    wear.set_editor_property("parameter_name", "Wear")
    wear.set_editor_property("default_value", unreal.LinearColor(0, 0, 0, 0))
    extra["Wear"] = (wear, "RGBA")
    mpc = unreal.load_asset("/Game/Boats/MPC_Boat")
    for i, pname in enumerate(("WaterZ", "WetBand", "DeckWet", "SprayWet", "Rain", "Puddle")):
        cp = node(mat, unreal.MaterialExpressionCollectionParameter, -900, 2160 + i * 80)
        cp.set_editor_property("collection", mpc)
        cp.set_editor_property("parameter_name", pname)
        extra[pname] = (cp, "")
    # World position (make_materials.py's node() adds MPC_World.RenderOrigin: the boat's wet line is in the map frame).
    wp = node(mat, unreal.MaterialExpressionWorldPosition, -1100, 2400)
    origin = node(mat, unreal.MaterialExpressionCollectionParameter, -1300, 2480)
    origin.set_editor_property("collection", unreal.load_asset("/Game/World/MPC_World"))
    origin.set_editor_property("parameter_name", "RenderOrigin")
    mask = node(mat, unreal.MaterialExpressionComponentMask, -1150, 2480)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        mask.set_editor_property(ch, on)
    MEL.connect_material_expressions(origin, "", mask, "")
    wp_map = node(mat, unreal.MaterialExpressionAdd, -950, 2400)
    MEL.connect_material_expressions(wp, "", wp_map, "A")
    MEL.connect_material_expressions(mask, "", wp_map, "B")
    extra["WP"] = (wp_map, "")
    extra["NW"] = (node(mat, unreal.MaterialExpressionVertexNormalWS, -900, 2560), "")
    extra["V"] = (node(mat, unreal.MaterialExpressionCameraVectorWS, -900, 2640), "")
    extra["Time"] = (node(mat, unreal.MaterialExpressionTime, -900, 2720), "")
    c = node(mat, unreal.MaterialExpressionCustom, -500, 400)
    c.set_editor_property("code", DETAIL_CODE)
    c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = ["Base", "R", "N", "X", "Depth", "NSN", "NSM", "GCN", "GCM", "TKN", "TKM"] + list(extra)
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
                          (detail["TeakWeatheredN"], "RGB", "TKN"), (detail["TeakWeatheredM"], "RGB", "TKM")) \
            + tuple((src, out, pin) for pin, (src, out) in extra.items()):
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


# Boat fidelity 1: the flat materials' kinds in M_BoatSurface's shared library (make_materials.py BOAT_SURFACE: 1 gelcoat,
# 3 stainless, 4 anodised aluminium, 6 varnished wood, 7 bare wood, 8 rubber, 10 sailcloth, 11 canvas; 0 none), and how
# much each darkens wet.
HERO_SURFACE = {
    "Gelcoat": 1, "GelcoatHull": 1, "CabinGelcoat": 1, "InteriorLiner": 1, "InteriorSole": 1,
    "Stainless": 3, "Chrome": 3, "Galvanised": 3, "KeelBoltSteel": 3, "Bronze": 3, "Aluminium": 4, "CastAlu": 4,
    "TeakVarnish": 6, "PlywoodVarnish": 6, "AshVarnish": 6, "TeakWeathered": 7, "RubRail": 8, "ExtensionBlack": 8, "RigTape": 10,
    "Cushion": 11, "SailBag": 11, "PFDNylon": 11, "Webbing": 11,
}
HERO_POROSITY = {6: 0.2, 7: 0.5, 8: 0.05, 10: 0.3, 11: 0.6, 3: 0.0, 4: 0.0}


def instance(name, parent):
    path = f"{DEST}/{name}"
    mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
        ASSETS.create_asset(name, DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    return mi


def materials():
    names = {"D": "BaseColor", "R": "Roughness", "N": "Normal", "X": "DetailMask"}
    # HERO_MATERIALS_ONLY=1 rebuilds the materials over the textures already imported (no mesh or texture reimport).
    get = (lambda f, k: unreal.load_asset(f"{TEX}/{os.path.splitext(f)[0]}")) if MATERIALS_ONLY else \
        (lambda f, k: import_texture(os.path.join(SRC, "textures", f), k))
    textures = {group: {names[k]: get(f, k) for k, f in maps.items() if f and k in names}
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
    def flat_values(name):
        v = META["flat_materials"][name]
        gel = "Gelcoat" in name or name in ("HatchAcrylic", "TeakVarnish")
        return v["base_color_linear"], {"Roughness": v["roughness"], "Metallic": v["metallic"], "ClearCoat": 1.0 if gel else 0.0, "NonSkid": 0.0,
                                        "Porosity": HERO_POROSITY.get(HERO_SURFACE.get(name, 0), 0.1), "IsHull": 0.0,
                                        "Surface": float(HERO_SURFACE.get(name, 0)), "Grain": 0.0}

    for name in META["flat_materials"]:
        if name in out:
            continue
        mi = instance(f"MI_J22H_{name}", surface)
        c, values = flat_values(name)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(c[0], c[1], c[2], 1.0))
        for pname, value in values.items():
            if pname != "Grain":
                MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[name] = mi
    # pc/boat-slots: the flat slots folded into packs (J22H_packs.json, pack_j22_hero.py): MI_J22H_<Pack> on M_BoatPacked
    # carries each entry's values as P<k>C, P<k>A (roughness, metallic, clear coat, non-skid), P<k>B (porosity, surface,
    # hull, grain), as make_materials.py builds MI_Boat_<Pack>.
    packed = unreal.load_asset("/Game/Boats/Materials/M_BoatPacked")
    for pack, entries in PACKS.items():
        mi = instance(f"MI_{pack}", packed)
        for k, name in enumerate(entries):
            c, v = flat_values(name)
            for s, value in (("C", (c[0], c[1], c[2], 1.0)), ("A", (v["Roughness"], v["Metallic"], v["ClearCoat"], v["NonSkid"])),
                             ("B", (v["Porosity"], v["Surface"], v["IsHull"], v["Grain"]))):
                MEL.set_material_instance_vector_parameter_value(mi, f"P{k}{s}", unreal.LinearColor(*value))
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[pack[len("J22H_"):]] = mi
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
if MATERIALS_ONLY:
    materials()
    unreal.log("Hero materials done")
else:
    main()
