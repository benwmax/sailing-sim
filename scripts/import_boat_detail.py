"""Boat detail pass: braided rope and 1x19 wire for the live rig lines, and the close-up detail textures for the hero
boats' surfaces. Run in the editor after make_materials.py: scripts\\windows\\run-python.ps1 import_boat_detail.py
(or the editor's -ExecutePythonScript).

  /Game/Boats/Rope: T_Rope_Braid24_N/_M, T_Rope_Braid16_N/_M, T_Wire_1x19_N/_M, T_RopeColourways (Inputs/rope, made by
    Tools/rope/make_rope_textures.py), and
    - M_RigRope: the live ropes (FRigLine, BoatModelVisuals.cpp). UV0 U is arc length over one lay of the cover
      (5 diameters), V once round; the vertex colour's red is the rope's look, a column of T_RopeColourways (base colour,
      tracer colour, which tracer mask of T_Rope_Braid24_M). Fade and Dirt are scalar parameters (club boat defaults).
    - M_RigWire: the standing rigging, 1x19 strand normals (U over 11 diameters). Look 255 (the tiller extension, drawn
      with the wires) is a plain black tube.
  /Game/Boats/Detail: T_Detail_NonSkid/_Gelcoat/_TeakWeathered/_Canvas (Inputs/boat-detail, made by
    Tools/boats/make_detail_textures.py), used by import_j22_hero.py's M_J22HeroSurface, and (boat fidelity 1) those
    plus _Metal/_WoodVarnish/_Rubber/_Braid/_Sailcloth, read by make_materials.py's M_BoatSurface: rerun
    `run-python.ps1 make_materials.py -Only build_boat_library` after importing them.

The pawn picks M_RigRope and M_RigWire up at BeginPlay when they exist (-SailingFlatRope keeps the old flat ones).
"""
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROPE_SRC = os.path.join(REPO, "Inputs", "rope")
DETAIL_SRC = os.path.join(REPO, "Inputs", "boat-detail")
ROPE = "/Game/Boats/Rope"
DETAIL = "/Game/Boats/Detail"
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary


def import_texture(path, dest, kind):
    """kind: N (normal, OpenGL: green flipped), M (linear data), LUT (linear, nearest, no mips, uncompressed)."""
    name = os.path.splitext(os.path.basename(path))[0]
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    ASSETS.import_asset_tasks([task])
    tex = unreal.load_asset(f"{dest}/{name}")
    if kind == "N":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("flip_green_channel", True)
    elif kind == "M":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        tex.set_editor_property("srgb", False)
    elif kind == "LUT":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
        tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    if dest == DETAIL:
        # Boat texture budget (docs/boat-tex-medium): the Vehicle groups (their device-profile sizes keep the hero boat inside Medium's 24 MB).
        tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_VEHICLE_NORMAL_MAP if kind == "N" else unreal.TextureGroup.TEXTUREGROUP_VEHICLE)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return tex


def new_material(name, folder):
    path = f"{folder}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    return ASSETS.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())


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


ROPE_CODE = r"""
float look = round(VC.r * 255.0);
float4 m = Texture2DSample(BraidM, BraidMSampler, UV);
float u = (min(look, 15.0) + 0.5) / 16.0;
float3 base = pow(Texture2DSample(Lut, LutSampler, float2(u, 0.125)).rgb, 2.2);
float3 tracer = pow(Texture2DSample(Lut, LutSampler, float2(u, 0.375)).rgb, 2.2);
float3 pattern = Texture2DSample(Lut, LutSampler, float2(u, 0.625)).rgb;
float mask = dot(pattern, m.gba);
float3 c = lerp(base, tracer, mask);
float deep = 1.0 - m.r;
// Texture loop (docs/texture-loop/rope.md): wear from the boat's Age (years) and Care (0 neglected .. 1 kept), split into
// time (sun fade: care can't undo it) and dirt (grime, fuzz, mildew: care removes it). Rope is a consumable: a kept boat
// replaces her lines every few seasons, so the rope's own age is capped by care. Age < 0 (unset): the old look from the
// Fade and Dirt parameters. Tools/rope/rope_wear.py is this code's numpy twin: change one, change the other.
float fuzz = 0.4 * Fade;
if (Age >= 0.0)
{
    float cr = saturate(Care);
    float ra = min(Age, 3.0 + 12.0 * (1.0 - cr));       // the rope's own age: replaced every 3 years kept, 15 not
    float tK = saturate(0.25 * (1.0 - exp(-ra / 0.75)) + 0.75 * (1.0 - exp(-ra / 18.0)));    // wear.py time_k
    float dK = saturate((1.0 - exp(-ra)) * (0.15 + 0.85 * (1.0 - cr)));                        // wear.py dirt_k
    float fade = saturate(0.35 * tK + 0.1 * dK);      // polyester dyes hold: a club boat's red is still red
    fuzz = saturate(0.45 * tK + 0.75 * dK);
    float mildew = max((dK - 0.6) / 0.4, 0.0) * (1.0 - cr);
    // sun fade: dyes go pale and grey (red toward pink, blue toward slate, white toward ivory grey)
    float lumR = dot(c, float3(0.2126, 0.7152, 0.0722));
    c = lerp(c, saturate(lumR * 0.75 + 0.12) * float3(1.0, 0.985, 0.94), 0.55 * fade);
    // grime: grey-brown in the whole cover, darker in the weave and in patches along the line (cleats, fairleads)
    float2 pq = float2(UV.x * 0.9, 3.1 * look);
    float2 pci = floor(pq), pf = frac(pq);
    pf = pf * pf * (3.0 - 2.0 * pf);
    float h00 = frac(sin(dot(pci, float2(12.9898, 78.233)) + 1.7) * 43758.5453), h10 = frac(sin(dot(pci + float2(1, 0), float2(12.9898, 78.233)) + 1.7) * 43758.5453);
    float h01 = frac(sin(dot(pci + float2(0, 1), float2(12.9898, 78.233)) + 1.7) * 43758.5453), h11 = frac(sin(dot(pci + float2(1, 1), float2(12.9898, 78.233)) + 1.7) * 43758.5453);
    float patch = lerp(lerp(h00, h10, pf.x), lerp(h01, h11, pf.x), pf.y);
    float2 sq = float2(UV.x * 4.0, UV.y * 2.0 + 7.0 * look);                 // dark smudges a hand or cleat left
    float2 si = floor(sq), sf = frac(sq);
    sf = sf * sf * (3.0 - 2.0 * sf);
    float s00 = frac(sin(dot(si, float2(12.9898, 78.233)) + 2.9) * 43758.5453), s10 = frac(sin(dot(si + float2(1, 0), float2(12.9898, 78.233)) + 2.9) * 43758.5453);
    float s01 = frac(sin(dot(si + float2(0, 1), float2(12.9898, 78.233)) + 2.9) * 43758.5453), s11 = frac(sin(dot(si + float2(1, 1), float2(12.9898, 78.233)) + 2.9) * 43758.5453);
    float smudge = saturate(lerp(lerp(s00, s10, sf.x), lerp(s01, s11, sf.x), sf.y) * 2.2 - 1.2);
    float g = saturate(0.8 * dK * (0.45 + 0.6 * patch + 1.2 * smudge));
    c = lerp(c, c * float3(0.52, 0.50, 0.45) + float3(0.012, 0.011, 0.008), g);
    c *= 1.0 - 0.5 * sqrt(0.8 * dK) * deep;                // dirt in the weave first: visible after a few months
    // mildew: dark grey-green specks in the weave of a neglected line
    float sp = frac(sin(dot(floor(UV * float2(90.0, 60.0)), float2(12.9898, 78.233)) + 5.3) * 43758.5453);
    float mil = mildew * step(0.93, sp) * saturate(deep * 2.0);
    c = lerp(c, float3(0.035, 0.040, 0.028), 0.7 * mil);
    c = lerp(c, float3(0.19, 0.20, 0.16), 0.45 * mildew);   // a grey-green film over a line left out for years
}
else
{
    c = lerp(c, float3(0.62, 0.60, 0.55), 0.3 * Fade);             // sun fade toward chalky grey
    c = lerp(c, float3(0.11, 0.095, 0.07), saturate((deep * 1.2 + 0.3) * Dirt * 0.35));
}
// Boat fidelity 4 ("readable at arm's reach"): the yarns inside each carrier, fine streaks along the cover's two helices
// (S and Z, a lay of U over 5 diameters, 24 carriers round), so a strand reads as twisted fibre and not a smooth ribbon.
float sS = sin(6.2831853 * (UV.x * 36.0 + UV.y * 48.0)), sZ = sin(6.2831853 * (UV.x * 36.0 - UV.y * 48.0));
float yarn = 0.5 + 0.5 * lerp(sS, sZ, step(0.5, frac(UV.x * 6.0 + UV.y * 12.0)));
c *= 0.9 + 0.16 * yarn * (1.0 - deep);
float wearOn = Age >= 0.0 ? 1.0 : 0.0;
c = lerp(c, float3(0.023, 0.021, 0.018), deep * 0.62 * (1.0 - 0.45 * fuzz * wearOn));   // shadow in the weave (fuzz fills it)
// Polyester fuzz: loose fibres stand off a used rope and catch the light along its silhouette.
float rim = pow(1.0 - saturate(abs(dot(normalize(N), normalize(V)))), 3.0);
c = lerp(c, c * 1.35 + 0.035, rim * lerp(0.25 + 0.35 * Fade, 0.12 + 0.6 * fuzz, wearOn));
Rough = lerp(0.62, 0.5 + 0.3 * sqrt(fuzz), wearOn) + 0.25 * deep - 0.06 * yarn * (1.0 - deep);
// pc/rig-lines ("a lay seen close up"): the cover's carriers as the eye reads them at arm's length, a diamond of S and Z
// helices at 45 deg, 4 round (U runs 5 diameters, V once round: a period along the rope of 0.8 diameter), the carrier on
// top alternating at each crossing. Ridged in colour and normal, faded where a carrier falls under about a pixel (its own
// screen derivative), so it never aliases into crawl. Below it the braid map's finer pattern carries on.
float pS = 4.0 * UV.y - UV.x * 4.0 * 5.0 / 3.14159265, pZ = 4.0 * UV.y + UV.x * 4.0 * 5.0 / 3.14159265;
float layFw = 1.0;
#if !RAYHITGROUPSHADER
layFw = max(fwidth(pS), fwidth(pZ));
#endif
float layK = saturate(2.0 - 2.5 * layFw);
float onS = step(0.5, frac(0.5 * (floor(pS) + floor(pZ))));
float ridge = lerp(abs(cos(3.14159265 * pZ)), abs(cos(3.14159265 * pS)), onS);
c *= lerp(1.0, 0.7 + 0.36 * ridge, layK);
Rough = lerp(Rough, Rough + 0.12 * (1.0 - ridge), layK);
// Texture loop: fuzz veil: broken filaments stand off the cover and soften it, contrast and colour both
c = lerp(c, 0.5 * c + 0.5 * float3(0.30, 0.295, 0.28), 0.3 * sqrt(fuzz) * wearOn * saturate(2.0 * dot(c, float3(0.2126, 0.7152, 0.0722))));   // pale carriers only
float2 tilt = lerp(float2(0.85, 0.53) * sin(6.2831853 * pZ), float2(-0.85, 0.53) * sin(6.2831853 * pS), onS);
float nStr = 1.0 - 0.4 * fuzz * wearOn;                       // fuzz softens the weave's relief
NormalOut = normalize(float3((NM.xy - 0.35 * layK * tilt) * nStr, NM.z));
return c;
"""


def rope_material(tex):
    mat = new_material("M_RigRope", ROPE)
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -900, 0)
    vc = node(mat, unreal.MaterialExpressionVertexColor, -900, 150)
    tm = node(mat, unreal.MaterialExpressionTextureObject, -900, 300, texture=tex["T_Rope_Braid24_M"])
    lut = node(mat, unreal.MaterialExpressionTextureObject, -900, 450, texture=tex["T_RopeColourways"])
    fade = node(mat, unreal.MaterialExpressionScalarParameter, -900, 600, parameter_name="Fade", default_value=0.4)
    dirt = node(mat, unreal.MaterialExpressionScalarParameter, -900, 700, parameter_name="Dirt", default_value=0.5)
    # Texture loop: the boat's Age (years, -1 unset: Fade and Dirt above) and Care, as the hull's (BoatModelVisuals sets both).
    age = node(mat, unreal.MaterialExpressionScalarParameter, -1100, 600, parameter_name="Age", default_value=-1.0)
    care = node(mat, unreal.MaterialExpressionScalarParameter, -1100, 700, parameter_name="Care", default_value=0.5)
    nws = node(mat, unreal.MaterialExpressionVertexNormalWS, -900, 800)
    cam = node(mat, unreal.MaterialExpressionCameraVectorWS, -900, 900)
    c = custom(mat, ROPE_CODE, ["UV", "VC", "BraidM", "Lut", "Fade", "Dirt", "N", "V", "NM", "Age", "Care"],
               unreal.CustomMaterialOutputType.CMOT_FLOAT3, -450, 200, [("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
                                                                         ("NormalOut", unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    nrm = node(mat, unreal.MaterialExpressionTextureSample, -700, 500, texture=tex["T_Rope_Braid24_N"],
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    MEL.connect_material_expressions(uv, "", nrm, "UVs")
    for src, out, pin in ((uv, "", "UV"), (vc, "", "VC"), (tm, "", "BraidM"), (lut, "", "Lut"), (fade, "", "Fade"), (dirt, "", "Dirt"),
                          (nws, "", "N"), (cam, "", "V"), (nrm, "RGB", "NM"), (age, "", "Age"), (care, "", "Care")):
        MEL.connect_material_expressions(src, out, c, pin)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(c, "NormalOut", unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


WIRE_CODE = r"""
float plain = VC.r > 0.99 ? 1.0 : 0.0;
float cav = Texture2DSample(WireM, WireMSampler, UV).r;
Metal = 1.0 - plain;
Rough = lerp(0.22 + 0.15 * (1.0 - cav), 0.6, plain);
NormalWeight = 1.0 - plain;
return lerp(float3(0.56, 0.58, 0.60) * (0.75 + 0.25 * cav), float3(0.012, 0.012, 0.012), plain);
"""


def wire_material(tex):
    mat = new_material("M_RigWire", ROPE)
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -900, 0)
    vc = node(mat, unreal.MaterialExpressionVertexColor, -900, 150)
    tm = node(mat, unreal.MaterialExpressionTextureObject, -900, 300, texture=tex["T_Wire_1x19_M"])
    c = custom(mat, WIRE_CODE, ["UV", "VC", "WireM"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -450, 150,
               [("Metal", unreal.CustomMaterialOutputType.CMOT_FLOAT1), ("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
                ("NormalWeight", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    for src, pin in ((uv, "UV"), (vc, "VC"), (tm, "WireM")):
        MEL.connect_material_expressions(src, "", c, pin)
    nrm = node(mat, unreal.MaterialExpressionTextureSample, -700, 500, texture=tex["T_Wire_1x19_N"],
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    MEL.connect_material_expressions(uv, "", nrm, "UVs")
    flat = node(mat, unreal.MaterialExpressionConstant3Vector, -700, 700, constant=unreal.LinearColor(0, 0, 1, 1))
    lerp = node(mat, unreal.MaterialExpressionLinearInterpolate, -300, 550)
    MEL.connect_material_expressions(flat, "", lerp, "A")
    MEL.connect_material_expressions(nrm, "RGB", lerp, "B")
    MEL.connect_material_expressions(c, "NormalWeight", lerp, "Alpha")
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Metal", unreal.MaterialProperty.MP_METALLIC)
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(lerp, "", unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


def main():
    # ROPE_MATERIAL_ONLY=1 (boat fidelity 4) rebuilds M_RigRope and M_RigWire over the textures already imported, nothing else.
    if os.environ.get("ROPE_MATERIAL_ONLY") == "1":
        tex = {n: unreal.load_asset(f"{ROPE}/{n}") for n in ("T_Rope_Braid24_M", "T_Rope_Braid24_N", "T_RopeColourways", "T_Wire_1x19_M", "T_Wire_1x19_N")}
        rope_material(tex)
        wire_material(tex)
        unreal.log("Boat detail import done: M_RigRope and M_RigWire only")
        return
    # DETAIL_NEW_ONLY=1 imports only the detail textures not yet in /Game/Boats/Detail (the rope and wire stay as they are).
    new_only = os.environ.get("DETAIL_NEW_ONLY") == "1"
    if not new_only:
        tex = {}
        for f in sorted(os.listdir(ROPE_SRC)):
            if f.startswith(("T_Rope_", "T_Wire_")) and f.endswith(("_N.png", "_M.png")):
                tex[f[:-4]] = import_texture(os.path.join(ROPE_SRC, f), ROPE, f[-5])
        tex["T_RopeColourways"] = import_texture(os.path.join(ROPE_SRC, "T_RopeColourways.png"), ROPE, "LUT")
        rope_material(tex)
        wire_material(tex)
    for f in sorted(os.listdir(DETAIL_SRC)):
        if f.startswith("T_Detail_") and f.endswith(("_N.png", "_M.png")):
            if new_only and unreal.EditorAssetLibrary.does_asset_exist(f"{DETAIL}/{f[:-4]}"):
                continue
            import_texture(os.path.join(DETAIL_SRC, f), DETAIL, f[-5])
    unreal.log("Boat detail import done: M_RigRope, M_RigWire and the detail textures")


main()
