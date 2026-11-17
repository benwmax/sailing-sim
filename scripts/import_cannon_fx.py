"""Cannon fire's effects (docs/cannon-fire/): imports the textures Tools/shipkit/frigate/make_cannon_textures.py made
(Artifacts/cannon-fx, or the folder given last) into /Game/Materials/CannonFx and builds the two materials ACannonBattery
draws with. Run by scripts/make-cannon-fx.sh (Mac) or scripts\\windows\\make-cannon-fx.ps1 (PC), after make-content.sh.

  M_CannonSmoke  lit translucent quads facing the camera (ACannonBattery::UpdateSmokeVisuals), one per Gaussian puff of
                 Sailing::FCannonSmoke. Per-instance data: 0 the puff's peak opacity (the near fade in it), 1 its glow
                 (lit by a flash, 0..1), 2 its seed (the atlas tile), 3 how fresh (1 at the muzzle, exp(-age / 6 s)).
  M_CannonFlash  additive unlit quads (UpdateFlashVisuals). Per-instance data: 0 intensity, 1 kind (0 the muzzle's
                 flame along the bore, 1 a burning grain streaked along its motion, 2 the pan's spurt, 3 the round bloom
                 at the mouth), 2 seed, 3 age over its life (0..1).

Both read the quad's own position (the engine's 1 m plane, -50..50 cm), not its UVs. Their scalar parameters are the look's
knobs in FCannonParams (FlameNits, SparkNits, SmokeGlowNits, SmokeAlbedo, SmokeForwardScatter, SmokeEdgeSoftness,
SmokeDepthFadeM), which ACannonBattery::PushLook sets on its instances: the defaults here are only for the editor's
preview (luminances already in the scene's units, real cd/m^2 x 2^-14.1). Edit this script, never the assets.
"""
import os
import sys

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[-1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) else os.path.join(REPO, "Artifacts", "cannon-fx")
TEX = "/Game/Materials/CannonFx"
FOLDER = "/Game/Materials"
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
LIB = unreal.EditorAssetLibrary
TO_SCENE = 2.0 ** -14.1   # VisualPipeline.cpp's kSceneEVOffset
F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3


def import_texture(name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(SRC, name + ".png"))
    task.set_editor_property("destination_path", TEX)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    ASSETS.import_asset_tasks([task])
    tex = unreal.load_asset(f"{TEX}/{name}")
    # Data, not colour: linear, four channels kept apart (BC7 holds them well enough at 256 a tile), clamped (an atlas).
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
    tex.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    LIB.save_loaded_asset(tex)
    return tex


def new_material(name):
    path = f"{FOLDER}/{name}"
    if LIB.does_asset_exist(path):
        # Rebuilt in place (ACannonBattery loads it by path; nothing else references it).
        LIB.delete_asset(path)
    return ASSETS.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())


def node(mat, cls, x, y, **props):
    n = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def scalar(mat, name, default, x, y):
    return node(mat, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=default)


def custom(mat, code, inputs, output_type, x, y, extra_outputs=()):
    c = node(mat, unreal.MaterialExpressionCustom, x, y, code=code, output_type=output_type)
    ins = []
    for n in inputs:
        i = unreal.CustomInput()
        i.set_editor_property("input_name", n)
        ins.append(i)
    c.set_editor_property("inputs", ins)
    outs = []
    for n, kind in extra_outputs:
        o = unreal.CustomOutput()
        o.set_editor_property("output_name", n)
        o.set_editor_property("output_type", kind)
        outs.append(o)
    if outs:
        c.set_editor_property("additional_outputs", outs)
    return c


def connect(a, a_out, b, b_in):
    if not MEL.connect_material_expressions(a, a_out, b, b_in):
        raise RuntimeError(f"connect failed: {a.get_name()}.{a_out} -> {b.get_name()}.{b_in}")


def wire(mat, code, inputs, output_type, x, y, extra_outputs=()):
    c = custom(mat, code, list(inputs.keys()), output_type, x, y, extra_outputs)
    for name, n in inputs.items():
        connect(n, "", c, name)
    return c


def instance_data(mat, names, x, y):
    return {n: node(mat, unreal.MaterialExpressionPerInstanceCustomData, x, y + 90 * k, data_index=k) for k, n in enumerate(names)}


SMOKE_CODE = r"""
// docs/cannon-fire/: one Gaussian puff of powder smoke (Sailing::FCannonSmoke), a quad spanning +-2.5 sigma.
// The quad's own position (the engine plane spans -50..50 cm): uv 0..1 with v down, as the atlas's rows run.
float2 q = Local.xy / 50.0;
float2 uv = float2(q.x * 0.5 + 0.5, 0.5 - q.y * 0.5);
// Seed picks one of the atlas's 4 x 4 puffs (an inset keeps the mips from bleeding the neighbours in).
float tile = floor(saturate(Seed) * 15.999);
float2 cell = float2(fmod(tile, 4.0), floor(tile / 4.0));
float2 tuv = (cell + 0.02 + 0.96 * saturate(uv)) / 4.0;
float4 t = Texture2DSample(Tex, TexSampler, tuv);
// Fresh smoke is billowed (R); old smoke spreads toward the soft Gaussian (B), as far as EdgeSoftness lets it.
float billowed = saturate(Fresh + (1.0 - EdgeSoftness));
float d = lerp(t.b, t.r, billowed);
// Wisps where it thins: the fine detail (A) eats the edge, never the core.
d *= lerp(1.0, saturate(t.a * 2.0), saturate(1.0 - d * 2.5) * 0.6);
// The puff's peak opacity is the column's 1 - exp(-tau) through its centre (FSmokePuff::Opacity, the near fade in it);
// the texture's density scales tau.
float tau = -log(max(1.0 - saturate(Op), 1e-3));
float alpha = 1.0 - exp(-tau * d);
// Colour: pale powder smoke, shaded by its own density from above (G), darker where thick.
float shade = lerp(0.55, 1.0, t.g);
Base = Albedo * shade * lerp(1.0, 0.8, saturate(tau * d * 0.5));
// The sun through it (Henyey-Greenstein, g ForwardScatter): looking sunward the thin edges glow. Only the excess over an
// isotropic phase (the volumetric lighting gives that); weighted by the light that gets through (thin smoke scatters, a
// thick core blocks). V points at the camera.
float mu = dot(-V, L);
float g = clamp(ForwardScatter, 0.0, 0.95);
float hg = (1.0 - g * g) / pow(max(1.0 + g * g - 2.0 * g * mu, 1e-3), 1.5) / 12.566;
float3 sun = E * Albedo * max(hg - 0.0796, 0.0) * exp(-tau * d) * 2.0;
// Lit from inside by a flash: warm, brightest in the core.
float3 glow = GlowNits * Glow * d * float3(1.0, 0.55, 0.22);
Emis = (sun + glow) * alpha;
return alpha;
"""


def build_smoke(tex):
    mat = new_material("M_CannonSmoke")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    # Lit per vertex from the translucency volume, directionally: sunlit sides bright, the shadow side dim, and the flash
    # lights' pool on it, for the cost of a quad's four vertices.
    mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_VOLUMETRIC_PER_VERTEX_DIRECTIONAL)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    ins = {"Local": node(mat, unreal.MaterialExpressionLocalPosition, -1100, 0)}
    ins.update(instance_data(mat, ("Op", "Glow", "Seed", "Fresh"), -1100, 100))
    ins["Tex"] = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1100, 500, parameter_name="Puffs", texture=tex,
                      sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    ins["EdgeSoftness"] = scalar(mat, "EdgeSoftness", 0.5, -1100, 650)
    ins["ForwardScatter"] = scalar(mat, "ForwardScatter", 0.6, -1100, 730)
    ins["Albedo"] = scalar(mat, "Albedo", 0.85, -1100, 810)
    ins["GlowNits"] = scalar(mat, "GlowNits", 4000.0 * TO_SCENE, -1100, 890)
    ins["V"] = node(mat, unreal.MaterialExpressionCameraVectorWS, -1100, 970)
    ins["L"] = node(mat, unreal.MaterialExpressionSkyAtmosphereLightDirection, -1100, 1050)
    ins["E"] = node(mat, unreal.MaterialExpressionSkyAtmosphereLightIlluminance, -1100, 1130)
    c = wire(mat, SMOKE_CODE, ins, F1, -600, 300, extra_outputs=(("Base", F3), ("Emis", F3)))
    # Faded where it meets the water, the hull and the sails (no hard line through a puff).
    fade = node(mat, unreal.MaterialExpressionDepthFade, -250, 300)
    connect(c, "", fade, "Opacity")
    connect(scalar(mat, "DepthFadeCm", 150.0, -600, 600), "", fade, "FadeDistance")
    MEL.connect_material_property(c, "Base", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Emis", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(node(mat, unreal.MaterialExpressionConstant, -250, 500, r=1.0), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(fade, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(mat)
    LIB.save_loaded_asset(mat)


FLASH_CODE = r"""
// docs/cannon-fire/: the muzzle's flame, the pan's spurt, the bloom and the burning grains, added to the scene (unlit).
// The quad's own position (-50..50 cm): x along the quad's axis (the bore, the spark's motion, up for the pan), y across.
float2 q = Local.xy / 50.0;
float u = q.x * 0.5 + 0.5;          // 0 at the muzzle .. 1 at the tip
float v = q.y * 0.5 + 0.5;
int k = (int)round(Kind);
float3 hot = float3(1.0, 0.92, 0.7), red = float3(1.0, 0.35, 0.08);
float3 c = 0;
if (k == 1)
{
    // A burning grain: a thin streak, its head bright, cooling from yellow to red as it dies (Age).
    float across = exp(-q.y * q.y * 30.0);
    float along = smoothstep(0.0, 0.35, u) * (1.0 - smoothstep(0.85, 1.0, u));
    c = lerp(hot, red, saturate(Age * 1.3)) * across * along * SparkNits;
}
else
{
    // A flame from the atlas (2 x 2 tongues; the seed picks one): R brightness, G heat, B grains, A the round bloom.
    float tile = floor(saturate(Seed) * 3.999);
    float2 cell = float2(fmod(tile, 2.0), floor(tile / 2.0));
    float2 fuv = (k == 3) ? float2(0.02, saturate(v)) : float2(saturate(u), saturate(v));
    float4 t = Texture2DSample(Tex, TexSampler, (cell + 0.02 + 0.96 * fuv) / 2.0);
    if (k == 3)
    {
        // The bloom at the mouth: round, white-hot, gone in the first third of the flash.
        float r = length(q);
        float b = exp(-r * r * 4.0) * (1.0 - smoothstep(0.0, 0.4, Age));
        c = hot * b * 0.8 * FlameNits;
    }
    else
    {
        // The tongue: the white core near the mouth cools to red at the tip and edges, and as it ages (the secondary
        // flash, burning in the air, is redder); the grains sparkle in it.
        float heat = saturate(t.g * (1.2 - Age));
        float bright = t.r * (1.0 + 0.6 * t.b);
        c = lerp(red, hot, heat) * bright * FlameNits * (k == 2 ? 0.5 : 1.0);
    }
}
return c * Intensity;
"""


def build_flash(tex):
    mat = new_material("M_CannonFlash")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    ins = {"Local": node(mat, unreal.MaterialExpressionLocalPosition, -1100, 0)}
    ins.update(instance_data(mat, ("Intensity", "Kind", "Seed", "Age"), -1100, 100))
    ins["Tex"] = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1100, 500, parameter_name="Flames", texture=tex,
                      sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    ins["FlameNits"] = scalar(mat, "FlameNits", 60000.0 * TO_SCENE, -1100, 650)
    ins["SparkNits"] = scalar(mat, "SparkNits", 20000.0 * TO_SCENE, -1100, 730)
    c = wire(mat, FLASH_CODE, ins, F3, -600, 300)
    # (Faded into what it touches over 30 cm: the flame starts at the muzzle, inside the port.)
    fade = node(mat, unreal.MaterialExpressionDepthFade, -250, 400)
    connect(node(mat, unreal.MaterialExpressionConstant, -450, 450, r=1.0), "", fade, "Opacity")
    connect(node(mat, unreal.MaterialExpressionConstant, -450, 520, r=30.0), "", fade, "FadeDistance")
    mul = node(mat, unreal.MaterialExpressionMultiply, -100, 300)
    connect(c, "", mul, "A")
    connect(fade, "", mul, "B")
    MEL.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    LIB.save_loaded_asset(mat)


ONLY = [n for n in os.environ.get("CANNON_FX_ONLY", "").split(",") if n]
if not ONLY or "textures" in ONLY:
    smoke_tex = import_texture("T_CannonSmoke")
    flame_tex = import_texture("T_CannonFlame")
else:
    smoke_tex = unreal.load_asset(f"{TEX}/T_CannonSmoke")
    flame_tex = unreal.load_asset(f"{TEX}/T_CannonFlame")
if not ONLY or "smoke" in ONLY:
    build_smoke(smoke_tex)
if not ONLY or "flash" in ONLY:
    build_flash(flame_tex)
unreal.log("Cannon fx: textures and materials built")
