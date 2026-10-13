"""Builds the Phase 2 materials in /Game/Materials from code, so they can be regenerated and reviewed.

- M_Water: water surface. Vertex shader displaces by the same 48-wave sum the physics uses (FWaveField), plus on
  the open sea the FFT ocean's two cascades (FOcean, uploaded as float textures each frame, masked where the sea
  reaches);
  pixel shader adds per-pixel wave normals, wind ripples from the cat's-paw map (the wind field's surface
  roughness), rain ripples, whitecaps and wake foam.
- M_Rain: translucent falling streaks for cylinders around the camera.
- M_Emissive: unlit glow (lightning).
- M_Sail: two-sided lit cloth.
- M_BoatSurface, M_BoatMast and the MI_Boat_* library (Visual V2): gelcoat with clear coat, antifouling, non-skid,
  metals, plastic and varnished wood; wet below the splash line and on deck in rain and spray (MPC_Boat).
Run with scripts/make-content.sh.
"""
import unreal

NUM_WAVES = 48
MEL = unreal.MaterialEditingLibrary
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
FOLDER = "/Game/Materials"


def new_material(name):
    path = f"{FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    return ASSETS.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())


def node(mat, cls, x, y, **props):
    n = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def scalar(mat, name, default, x, y):
    return node(mat, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=default)


def vector(mat, name, default, x, y):
    return node(mat, unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name, default_value=unreal.LinearColor(*default))


def custom(mat, code, inputs, output_type, x, y, extra_outputs=()):
    c = node(mat, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", code)
    c.set_editor_property("output_type", output_type)
    def make_input(name):
        i = unreal.CustomInput()
        i.set_editor_property("input_name", name)
        return i

    def make_output(name, kind):
        o = unreal.CustomOutput()
        o.set_editor_property("output_name", name)
        o.set_editor_property("output_type", kind)
        return o

    c.set_editor_property("inputs", [make_input(n) for n in inputs])
    if extra_outputs:
        c.set_editor_property("additional_outputs", [make_output(n, t) for n, t in extra_outputs])
    return c


def linear_default():
    """A tiny black texture without sRGB: the default for the float-data texture parameters (linear samplers)."""
    path = f"{FOLDER}/T_LinearBlack"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.load_asset(path)
    import os, struct, tempfile, zlib
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * 4 for _ in range(4))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    file = os.path.join(tempfile.gettempdir(), "T_LinearBlack.png")
    open(file, "wb").write(png)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", file)
    task.set_editor_property("destination_path", FOLDER)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    ASSETS.import_asset_tasks([task])
    tex = unreal.load_asset(path)
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return tex


def connect(a, a_out, b, b_in):
    if not MEL.connect_material_expressions(a, a_out, b, b_in):
        raise RuntimeError(f"connect failed: {a.get_name()}.{a_out} -> {b.get_name()}.{b_in}")


# ---------------------------------------------------------------- water
def wave_terms(kind):
    lines = []
    for i in range(NUM_WAVES):
        amp = f"A{i // 4}.{'xyzw'[i % 4]}"
        arg = f"W{i}.x * p.x + W{i}.y * p.y - W{i}.z * T + W{i}.w"
        # Components with no energy in the current sea are skipped (a uniform branch: cheap on the GPU).
        if kind == "height":
            lines.append(f"[branch] if ({amp} > 1e-5) h += {amp} * sin({arg});")
        else:
            lines.append(f"[branch] if ({amp} > 1e-5) {{ float s, c; sincos({arg}, s, c); float a = {amp} * fade; h += a * s; sx += a * W{i}.x * c; sy += a * W{i}.y * c; }}")
    return "\n".join(lines)


WPO_CODE = """
float3 p = P * 0.01;
float3 cam = Cam * 0.01;
float fade = saturate(1.0 - distance(p.xy, cam.xy) / Fade);
float h = 0.0;
""" + wave_terms("height") + """
float ho = 0.0;
[branch] if (OceanP.z > 0.0)
{
    // The FFT ocean: two cascades (texel i,j = the grid point at x = i * cell north, y = j * cell east), masked where
    // the open sea reaches and faded far out.
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    float om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
    float of = om * saturate(1.0 - distance(p.xy, cam.xy) / OceanP.w);
    float4 oa = OceanA.SampleLevel(OceanASampler, float2(p.y, p.x) / OceanP.x + 0.5 / 64.0, 0);
    float4 ob = OceanB.SampleLevel(OceanBSampler, float2(p.y, p.x) / OceanP.y + 0.5 / 64.0, 0);
    ho = (oa.r + ob.r) * of;
}
return float3(0.0, 0.0, (h * fade + ho) * 100.0);
"""

SHADE_CODE = """
float3 p = P * 0.01;
float3 cam = Cam * 0.01;
float dist = distance(p.xy, cam.xy);
float fade = saturate(1.0 - dist / Fade);
float h = 0.0, sx = 0.0, sy = 0.0;
[branch] if (fade > 0.0)
{
""" + wave_terms("normal") + """
}
float ho = 0.0;
[branch] if (OceanP.z > 0.0)
{
    // The FFT ocean: two cascades (texel i,j = the grid point at x = i * cell north, y = j * cell east), masked where
    // the open sea reaches and faded far out.
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    float om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
    float of = om * saturate(1.0 - distance(p.xy, cam.xy) / OceanP.w);
    float4 oa = OceanA.SampleLevel(OceanASampler, float2(p.y, p.x) / OceanP.x + 0.5 / 64.0, 0);
    float4 ob = OceanB.SampleLevel(OceanBSampler, float2(p.y, p.x) / OceanP.y + 0.5 / 64.0, 0);
    ho = (oa.r + ob.r) * of;
    sx += (oa.g + ob.g) * of;
    sy += (oa.b + ob.b) * of;
    h += ho;
}
// Cat's paws: local wind relative to 15 kn, from the same wind field the sails feel (CPU-filled map).
float2 guv = (p.xy - GustRect.xy) / GustRect.z + 0.5;
float rough = Gust.SampleLevel(GustSampler, guv, 0).r * 2.5;
float near = saturate(1.0 - dist / 1500.0);
// Wind ripples: short capillary-gravity waves along the wind, stronger where it blows harder.
float2 d = normalize(WindP.xy + float2(1e-4, 0.0));
float2 n = float2(-d.y, d.x);
float u = dot(p.xy, d), v = dot(p.xy, n);
float rip = saturate(rough - 0.12) * 0.075 * near;
float rx = 0.0, ry = 0.0;
{ float k = 9.0;  float c = cos(k * u + 2.0 * v - T * 9.4 + 1.3);  rx += k * c; ry += 2.0 * c; }
{ float k = 14.0; float c = cos(k * u - 5.0 * v - T * 11.7 + 4.1); rx += k * c * 0.6; ry -= 5.0 * c * 0.6; }
{ float k = 6.0;  float c = cos(k * u + 7.5 * v - T * 7.7 + 2.2);  rx += k * c * 0.8; ry += 7.5 * c * 0.8; }
{ float k = 21.0; float c = cos(k * u + 9.0 * v - T * 14.3 + 0.7); rx += k * c * 0.35; ry += 9.0 * c * 0.35; }
float2 rs = (d * rx + n * ry) * rip * 0.1;
sx += rs.x; sy += rs.y;
// Rain: a fine, busy roughness on the surface.
float rr = Rain * 0.06 * near;
sx += rr * (sin(p.x * 61.0 + T * 23.0) * cos(p.y * 47.0 - T * 17.0) + sin(p.y * 83.0 + T * 31.0));
sy += rr * (cos(p.x * 53.0 - T * 29.0) * sin(p.y * 71.0 + T * 19.0) + cos(p.x * 97.0 - T * 27.0));
// Whitecaps on the crests, by the Beaufort scale: the first scattered ones at 7-10 kn (Force 3), numerous at 11-16,
// many at 17-21, everywhere from 22. They follow the local wind (from the cat's-paw map), so a gust front shows as a
// band of breaking crests and a puff shows as a patch of them.
float slope = length(float2(sx, sy));
float localKnots = rough * 15.56;
float capsLevel = saturate((localKnots - 7.0) / 15.0);
// Wind sets how much of the water is breaking (about 1% at Force 3, 5% at Force 4, 20% at Force 6); each cap is
// bright white. Caps are short along the wind and long across it, drift downwind, and sit on the crests.
float cover = 0.2 * pow(capsLevel, 1.5);
float2 q = float2(dot(p.xy, d), dot(p.xy, n));
float n1 = 0.5 + 0.5 * sin(q.x * 1.3 - T * 1.6 + sin(q.y * 0.5) * 2.0);
float n2 = 0.5 + 0.5 * sin(q.y * 0.45 + sin(q.x * 0.7 + T * 0.4) * 2.0);
float n3 = 0.5 + 0.5 * sin(p.x * 0.23 + p.y * 0.31 + T * 0.2 + sin(p.y * 0.17) * 1.5);
float blob = n1 * lerp(0.55, 1.0, n2) * lerp(0.6, 1.0, n3);
float thr = 1.0 - 2.2 * cover;
float sharp = smoothstep(thr, thr + 0.06, blob) * (cover > 0.0 ? 1.0 : 0.0) * lerp(0.6, saturate(h * 6.0 + 0.6), fade)
    * (1.0 + 0.5 * saturate((slope - 0.12) * 5.0));
// Far off the caps are smaller than a pixel: show their average whiteness instead of shimmering flecks.
float caps = lerp(saturate(sharp) * 0.9, cover * 0.9, saturate((dist - 250.0) / 1200.0));
// Wake and bow wave foam from the boat (CPU-filled map around the boat).
float2 wuv = (p.xy - WakeRect.xy) / WakeRect.z + 0.5;
float inside = step(0.0, wuv.x) * step(wuv.x, 1.0) * step(0.0, wuv.y) * step(wuv.y, 1.0);
float wake = Wake.SampleLevel(WakeSampler, saturate(wuv), 0).r * inside;
// Break the foam into streaks and patches rather than a smooth white band.
float breakup = saturate(0.35 + 0.65 * (0.5 + 0.5 * sin(p.x * 3.1 + sin(p.y * 2.3) * 2.0)) * (0.5 + 0.5 * sin(p.y * 2.7 + sin(p.x * 1.9 + T * 0.3) * 2.0)));
wake *= breakup;
Foam = saturate(caps + wake);
// Debug view (DebugGust > 0): show the cat's-paw map as foam.
Foam = DebugGust > 1.5 ? frac(guv.x * 8.0) * step(0.5, frac(guv.y * 8.0)) : lerp(Foam, saturate(rough / 2.5), saturate(DebugGust));
// Sailors read puffs relative to the wind around them: compare local wind with the mean wind at the boat.
float gustRatio = (rough * 8.0) / max(WindP.z, 1.0);
Dark = saturate((gustRatio - 0.95) * 2.5);
// Ruffled water reflects less of the bright sky: cat's paws read as dark patches, the gust front as a dark line.
Rough = lerp(0.02, 0.3, saturate((rough - 0.4) * 0.8)) + 0.08 * saturate((gustRatio - 1.0) * 3.0) + Rain * 0.08;
return normalize(float3(-sx, -sy, 1.0));
"""


def build_water():
    mat = new_material("M_Water")
    mat.set_editor_property("tangent_space_normal", False)
    pos = node(mat, unreal.MaterialExpressionWorldPosition, -1600, 0)
    pos.set_editor_property("world_position_shader_offset", unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    cam = node(mat, unreal.MaterialExpressionCameraPositionWS, -1600, 100)
    time = scalar(mat, "WaveTime", 0.0, -1600, 200)
    fade = scalar(mat, "WaveFadeMeters", 900.0, -1600, 300)
    waves = [vector(mat, f"Wave{i:02d}", (0, 0, 0, 0), -1400, -2000 + i * 60) for i in range(NUM_WAVES)]
    amps = [vector(mat, f"WaveAmp{i:02d}", (0, 0, 0, 0), -1200, -2000 + i * 60) for i in range(NUM_WAVES // 4)]

    common = ["P", "Cam", "T", "Fade"] + [f"W{i}" for i in range(NUM_WAVES)] + [f"A{i}" for i in range(NUM_WAVES // 4)] \
        + ["OceanA", "OceanB", "OceanMask", "OceanP", "OceanMaskRect"]
    linear = linear_default()
    ocean_a = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 1300, parameter_name="OceanA", texture=linear,
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    ocean_b = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 1450, parameter_name="OceanB", texture=linear,
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    ocean_mask = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 1600, parameter_name="OceanMask", texture=linear,
                      sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    # x, y: tile sizes of the two cascades (m); z: 1 on the open sea, 0 elsewhere; w: fade distance (m).
    ocean_p = vector(mat, "OceanParams", (480, 60, 0, 6000), -1600, 1750)
    ocean_rect = vector(mat, "OceanMaskRect", (0, 0, 1, 1), -1600, 1850)
    wpo = custom(mat, WPO_CODE, common, unreal.CustomMaterialOutputType.CMOT_FLOAT3, -600, -400)

    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    gust_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 500, parameter_name="GustMap", texture=white)
    wake_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 650, parameter_name="WakeMap", texture=white)
    gust_rect = vector(mat, "GustRect", (0, 0, 1600, 0), -1600, 800)
    wake_rect = vector(mat, "WakeRect", (0, 0, 64, 0), -1600, 900)
    wind = vector(mat, "WindParams", (1, 0, 5, 0), -1600, 1000)
    rain = scalar(mat, "Rain", 0.0, -1600, 1100)
    debug = scalar(mat, "DebugGust", 0.0, -1600, 1200)
    shade = custom(mat, SHADE_CODE, common + ["Gust", "Wake", "GustRect", "WakeRect", "WindP", "Rain", "DebugGust"],
                   unreal.CustomMaterialOutputType.CMOT_FLOAT3, -600, 400,
                   extra_outputs=[("Foam", unreal.CustomMaterialOutputType.CMOT_FLOAT1), ("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
                                  ("Dark", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])

    for c in (wpo, shade):
        connect(pos, "", c, "P")
        connect(cam, "", c, "Cam")
        connect(time, "", c, "T")
        connect(fade, "", c, "Fade")
        # Vector parameters carry four floats: wire their RGBA output, not the default RGB.
        for i, w in enumerate(waves):
            connect(w, "RGBA", c, f"W{i}")
        for i, a in enumerate(amps):
            connect(a, "RGBA", c, f"A{i}")
        connect(ocean_a, "", c, "OceanA")
        connect(ocean_b, "", c, "OceanB")
        connect(ocean_mask, "", c, "OceanMask")
        connect(ocean_p, "RGBA", c, "OceanP")
        connect(ocean_rect, "RGBA", c, "OceanMaskRect")
    connect(gust_tex, "", shade, "Gust")
    connect(wake_tex, "", shade, "Wake")
    connect(gust_rect, "RGBA", shade, "GustRect")
    connect(wake_rect, "RGBA", shade, "WakeRect")
    connect(wind, "RGBA", shade, "WindP")
    connect(rain, "", shade, "Rain")
    connect(debug, "", shade, "DebugGust")

    # Turbid olive-green Texas lake water (Ray Hubbard, White Rock, Galveston Bay from above: Phase 8 RH-004, TXL-005,
    # GB-008): green and red come back from the suspended silt, blue is absorbed. Foam is white and rough.
    water_color = vector(mat, "WaterColor", (0.048, 0.054, 0.028, 1), -300, 600)
    foam_color = node(mat, unreal.MaterialExpressionConstant3Vector, -300, 700, constant=unreal.LinearColor(0.85, 0.88, 0.9, 1))
    base = node(mat, unreal.MaterialExpressionLinearInterpolate, -100, 650)
    connect(water_color, "", base, "A")
    connect(foam_color, "", base, "B")
    connect(shade, "Foam", base, "Alpha")
    rough_mix = node(mat, unreal.MaterialExpressionLinearInterpolate, -100, 800)
    foam_rough = node(mat, unreal.MaterialExpressionConstant, -300, 850, r=0.7)
    connect(shade, "Rough", rough_mix, "A")
    connect(foam_rough, "", rough_mix, "B")
    connect(shade, "Foam", rough_mix, "Alpha")

    MEL.connect_material_property(wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    MEL.connect_material_property(shade, "", unreal.MaterialProperty.MP_NORMAL)
    # Darken ruffled water a little more (less sky reflection, deeper colour).
    shade_mul = node(mat, unreal.MaterialExpressionOneMinus, 100, 900)
    dark_scale = node(mat, unreal.MaterialExpressionMultiply, 0, 900)
    dark_k = node(mat, unreal.MaterialExpressionConstant, -100, 950, r=0.45)
    connect(shade, "Dark", dark_scale, "A")
    connect(dark_k, "", dark_scale, "B")
    connect(dark_scale, "", shade_mul, "")
    darker = node(mat, unreal.MaterialExpressionMultiply, 200, 650)
    connect(base, "", darker, "A")
    connect(shade_mul, "", darker, "B")
    MEL.connect_material_property(darker, "", unreal.MaterialProperty.MP_BASE_COLOR)
    # Ruffled water also reflects less of the sky (specular occlusion), which is what makes a puff or a gust
    # front read as a dark patch at the low angles you see it from a boat.
    ao_scale = node(mat, unreal.MaterialExpressionMultiply, 0, 1050)
    ao_k = node(mat, unreal.MaterialExpressionConstant, -100, 1100, r=1.1)
    connect(shade, "Dark", ao_scale, "A")
    connect(ao_k, "", ao_scale, "B")
    ao = node(mat, unreal.MaterialExpressionOneMinus, 100, 1050)
    connect(ao_scale, "", ao, "")
    MEL.connect_material_property(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    MEL.connect_material_property(rough_mix, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


# ---------------------------------------------------------------- rain
RAIN_CODE = """
float2 uv = UV * float2(Columns, 1.0);
float col = floor(uv.x);
float rnd = frac(sin(col * 12.9898 + 4.1) * 43758.5453);
float rnd2 = frac(sin(col * 78.233 + 1.7) * 12543.123);
float y = frac(uv.y * Stretch + T * Speed * (0.75 + 0.5 * rnd) + rnd2);
float streak = smoothstep(0.0, 0.015, y) * (1.0 - smoothstep(0.015, 0.09, y));
float x = frac(uv.x);
float thin = smoothstep(0.42, 0.5, x) * (1.0 - smoothstep(0.5, 0.58, x));
return streak * thin * step(0.35, rnd);
"""


def build_rain():
    mat = new_material("M_Rain")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -800, 0)
    t = node(mat, unreal.MaterialExpressionTime, -800, 100)
    cols = scalar(mat, "Columns", 180.0, -800, 200)
    stretch = scalar(mat, "Stretch", 3.0, -800, 300)
    speed = scalar(mat, "Speed", 2.2, -800, 400)
    c = custom(mat, RAIN_CODE, ["UV", "T", "Columns", "Stretch", "Speed"], unreal.CustomMaterialOutputType.CMOT_FLOAT1, -500, 100)
    for a, b in ((uv, "UV"), (t, "T"), (cols, "Columns"), (stretch, "Stretch"), (speed, "Speed")):
        connect(a, "", c, b)
    amount = scalar(mat, "Rain", 0.0, -500, 300)
    op = node(mat, unreal.MaterialExpressionMultiply, -250, 200)
    connect(c, "", op, "A")
    connect(amount, "", op, "B")
    tint = vector(mat, "RainColor", (0.55, 0.58, 0.62, 1), -500, 400)
    em = node(mat, unreal.MaterialExpressionMultiply, -250, 350)
    connect(tint, "", em, "A")
    connect(op, "", em, "B")
    MEL.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_emissive():
    mat = new_material("M_Emissive")
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    # Navigation lights are drawn as instanced meshes (and the lightning bolt as a procedural mesh).
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    color = vector(mat, "Color", (1, 1, 1, 1), -500, 0)
    intensity = scalar(mat, "Intensity", 1.0, -500, 150)
    m = node(mat, unreal.MaterialExpressionMultiply, -250, 50)
    connect(color, "", m, "A")
    connect(intensity, "", m, "B")
    MEL.connect_material_property(m, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_sail():
    mat = new_material("M_Sail")
    mat.set_editor_property("two_sided", True)
    color = vector(mat, "Color", (0.92, 0.91, 0.88, 1), -500, 0)
    rough = node(mat, unreal.MaterialExpressionConstant, -500, 150, r=0.65)
    MEL.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_ghost():
    """M_Ghost: a translucent, two-sided, faintly glowing copy of a boat (replays: your last run beside you)."""
    mat = new_material("M_Ghost")
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    color = vector(mat, "Color", (0.55, 0.8, 1.0, 1), -500, 0)
    opacity = scalar(mat, "Opacity", 0.38, -500, 150)
    glow = node(mat, unreal.MaterialExpressionMultiply, -250, 250)
    k = node(mat, unreal.MaterialExpressionConstant, -500, 300, r=0.25)
    connect(color, "", glow, "A")
    connect(k, "", glow, "B")
    MEL.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_spray():
    """M_Spray (Visual V4, High): droplets of spray, instanced; a dithered half opacity the temporal AA blends to mist."""
    mat = new_material("M_Spray")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    color = node(mat, unreal.MaterialExpressionConstant3Vector, -500, 0, constant=unreal.LinearColor(0.82, 0.86, 0.88, 1))
    rough = node(mat, unreal.MaterialExpressionConstant, -500, 150, r=0.35)
    alpha = node(mat, unreal.MaterialExpressionConstant, -500, 300, r=0.55)
    # Interleaved-gradient noise per pixel, shifted each frame: the temporal AA averages it to the alpha.
    dither = custom(mat, """float2 px = Parameters.SvPosition.xy + float(View.StateFrameIndexMod8) * float2(7.0, 3.0);
float n = frac(52.9829189 * frac(dot(px, float2(0.06711056, 0.00583715))));
return Alpha - n + 0.3333;""", ["Alpha"], unreal.CustomMaterialOutputType.CMOT_FLOAT1, -300, 300)
    connect(alpha, "", dither, "Alpha")
    MEL.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(dither, "", unreal.MaterialProperty.MP_OPACITY_MASK)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_terrain():
    """Terrain colored by the vertex colors the terrain builder computes (mud, clay and sand banks, rock, grass,
    woods), with world-space variation so large areas don't look flat."""
    mat = new_material("M_Terrain")
    vc = node(mat, unreal.MaterialExpressionVertexColor, -800, 0)
    pos = node(mat, unreal.MaterialExpressionWorldPosition, -800, 200)
    code = """
float3 p = P * 0.01;
float n = sin(p.x * 0.11 + sin(p.y * 0.07) * 2.0) * sin(p.y * 0.13 + sin(p.x * 0.05) * 2.0);
float m = sin(p.x * 1.3 + p.y * 0.7) * sin(p.y * 1.7 - p.x * 0.4);
return C * (0.88 + 0.12 * n + 0.05 * m);
"""
    c = custom(mat, code, ["C", "P"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -400, 100)
    connect(vc, "", c, "C")
    connect(pos, "", c, "P")
    rough = node(mat, unreal.MaterialExpressionConstant, -400, 300, r=0.92)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_lens_distortion():
    """M_LensDistortion: barrel distortion for the action-cam reference preset (a GoPro's wide lens). The image is
    rendered rectilinear at the camera's full field of view; this pulls the middle in so straight lines bow outward
    the way they do in action-cam footage, keeping the edges (and so the field of view) where they were."""
    mat = new_material("M_LensDistortion")
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    strength = scalar(mat, "Strength", 0.35, -900, 0)
    code = """
float2 uv = GetViewportUV(Parameters);
float aspect = View.ViewSizeAndInvSize.x * View.ViewSizeAndInvSize.w;
float2 d = (uv - 0.5) * 2.0 * float2(1.0, 1.0 / aspect);
float s = (1.0 + K * dot(d, d)) / (1.0 + K);
return 0.5 + d * s * 0.5 * float2(1.0, aspect);
"""
    c = custom(mat, code, ["K"], unreal.CustomMaterialOutputType.CMOT_FLOAT2, -600, 0)
    connect(strength, "", c, "K")
    tex = node(mat, unreal.MaterialExpressionSceneTexture, -300, 0)
    tex.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    connect(c, "", tex, "UVs")
    MEL.connect_material_property(tex, "Color", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


# ---------------------------------------------------------------- boats (Visual V2)
BOAT_FOLDER = "/Game/Boats/Materials"

BOAT_CODE = r"""
// Visual V2 boat surfaces: gelcoat (clear coat), antifouling, non-skid, metals, plastic, varnished wood.
// LP: local position (cm, boat frame), WP: world position (cm), N: world normal, LX/LY: world axes of the boat's X/Y.
float3 n = normalize(N);
// Non-skid: a raised diamond pattern anchored to the boat (8 mm pitch), only where NonSkid > 0.
float k = 6.2831853 / 0.8;
float gx = cos(LP.x * k) * sin(LP.y * k), gy = sin(LP.x * k) * cos(LP.y * k);
float3 grad = (gx * LX + gy * LY) * 0.35 * NonSkid;
// Wet below the splash line: the water level plus the band the waves and heel throw spray to; a ragged, dripping
// edge (streaks along the hull) rather than a ruled line.
float streak = 0.5 + 0.5 * sin(LP.x * 0.21 + sin(LP.x * 0.047) * 3.0);
float wetLine = WaterZ + WetBand * (0.6 + 0.4 * streak);
float wet = 1.0 - smoothstep(wetLine - 3.0, wetLine + 3.0, WP.z);
// Deck wetness from rain and spray: up-facing surfaces darken a little, gloss up and carry droplets.
float up = saturate((n.z - 0.4) * 2.5);
float2 cell = floor(LP.xy / 0.9);
float h = frac(sin(dot(cell, float2(12.9898, 78.233))) * 43758.5453);
float2 f = frac(LP.xy / 0.9) - 0.5;
float drop = h > 0.72 ? saturate(1.0 - length(f) * 4.0) : 0.0;
float deckWet = saturate(DeckWet) * up;
grad += (f.x * LX + f.y * LY) * drop * deckWet * 1.2;
float wetAll = saturate(max(wet, deckWet * 0.8));
float3 base = C.rgb * lerp(1.0, 1.0 - 0.55 * Porosity, wetAll);
AlbedoOut = base * (1.0 - Metal);
F0Out = lerp(float3(0.04, 0.04, 0.04), base, Metal);
RoughOut = lerp(R, lerp(0.06, R, 0.25), wetAll * (1.0 - Metal));
// A water film is a clear coat of its own: the second (gloss) lobe grows where the surface is wet.
CoatOut = saturate(Coat * 0.6 + wetAll * 0.5 * (1.0 - Metal));
return normalize(n - grad);
"""


def collection():
    path = "/Game/Boats/MPC_Boat"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.load_asset(path)
    mpc = ASSETS.create_asset("MPC_Boat", "/Game/Boats", unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    params = []
    for name, default in (("WaterZ", 0.0), ("WetBand", 6.0), ("DeckWet", 0.0)):
        p = unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        params.append(p)
    mpc.set_editor_property("scalar_parameters", params)
    unreal.EditorAssetLibrary.save_loaded_asset(mpc)
    return mpc


def build_boat_surface(name, bend):
    """M_BoatSurface / M_BoatMast: one lit surface for every part of a boat model, set by material instances;
    the mast's variant bends fore and aft (BendCm at mid-height, a half-sine over BendHeightCm)."""
    path = f"{BOAT_FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset(name, BOAT_FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("used_with_skeletal_mesh", True)  # the crew (Visual V3) wear these materials too
    mpc = collection()
    color = vector(mat, "Color", (0.85, 0.85, 0.82, 1), -1400, -200)
    rough = scalar(mat, "Roughness", 0.35, -1400, -50)
    metal = scalar(mat, "Metallic", 0.0, -1400, 50)
    coat = scalar(mat, "ClearCoat", 1.0, -1400, 150)
    coat_r = scalar(mat, "ClearCoatRoughness", 0.05, -1400, 250)
    nonskid = scalar(mat, "NonSkid", 0.0, -1400, 350)
    porosity = scalar(mat, "Porosity", 0.15, -1400, 450)
    lp = node(mat, unreal.MaterialExpressionLocalPosition, -1400, 550)
    wp = node(mat, unreal.MaterialExpressionWorldPosition, -1400, 650)
    nrm = node(mat, unreal.MaterialExpressionVertexNormalWS, -1400, 750)
    axes = []
    for i, (vx, vy) in enumerate(((1.0, 0.0), (0.0, 1.0))):
        c = node(mat, unreal.MaterialExpressionConstant3Vector, -1600, 850 + i * 120, constant=unreal.LinearColor(vx, vy, 0.0, 0.0))
        t = node(mat, unreal.MaterialExpressionTransform, -1400, 850 + i * 120)
        t.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
        t.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        connect(c, "", t, "")
        axes.append(t)
    params = {}
    for i, pname in enumerate(("WaterZ", "WetBand", "DeckWet")):
        cp = node(mat, unreal.MaterialExpressionCollectionParameter, -1400, 1100 + i * 100)
        cp.set_editor_property("collection", mpc)
        cp.set_editor_property("parameter_name", pname)
        params[pname] = cp
    F3, F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT3, unreal.CustomMaterialOutputType.CMOT_FLOAT1
    c = custom(mat, BOAT_CODE, ["C", "R", "Metal", "Coat", "NonSkid", "Porosity", "LP", "WP", "N", "LX", "LY", "WaterZ", "WetBand", "DeckWet"],
               F3, -900, 200, extra_outputs=[("AlbedoOut", F3), ("F0Out", F3), ("RoughOut", F1), ("CoatOut", F1)])
    for src, pin in ((color, "C"), (rough, "R"), (metal, "Metal"), (coat, "Coat"), (nonskid, "NonSkid"), (porosity, "Porosity"), (lp, "LP"),
                     (wp, "WP"), (nrm, "N"), (axes[0], "LX"), (axes[1], "LY"), (params["WaterZ"], "WaterZ"), (params["WetBand"], "WetBand"),
                     (params["DeckWet"], "DeckWet")):
        connect(src, "RGBA" if src is color else "", c, pin)
    # Substrate slab: the gelcoat's clear coat (and a wet film) as the slab's second, glossier specular lobe.
    slab = node(mat, unreal.MaterialExpressionSubstrateSlabBSDF, -400, 200)
    connect(c, "AlbedoOut", slab, "Diffuse Albedo")
    connect(c, "F0Out", slab, "F0")
    connect(c, "RoughOut", slab, "Roughness")
    # Substrate's slab takes a tangent-space normal: the custom node works in world space, so transform it.
    to_tangent = node(mat, unreal.MaterialExpressionTransform, -600, 400)
    to_tangent.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
    to_tangent.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
    connect(c, "", to_tangent, "")
    connect(to_tangent, "", slab, "Normal")
    connect(coat_r, "", slab, "Second Roughness")
    connect(c, "CoatOut", slab, "Second Roughness Weight")
    MEL.connect_material_property(slab, "", unreal.MaterialProperty.MP_FRONT_MATERIAL)
    if bend:
        b = scalar(mat, "BendCm", 0.0, -900, 600)
        hgt = scalar(mat, "BendHeightCm", 800.0, -900, 700)
        code = "float t = saturate(LP.z / max(Hgt, 1.0)); return LX * (Bend * sin(3.14159265 * t) - 0.35 * Bend * t * t);"
        w = custom(mat, code, ["LP", "Bend", "Hgt", "LX"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -600, 650)
        connect(lp, "", w, "LP")
        connect(b, "", w, "Bend")
        connect(hgt, "", w, "Hgt")
        connect(axes[0], "", w, "LX")
        MEL.connect_material_property(w, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


# The boat material library: slot name -> (parent, colour, roughness, metallic, clear coat, non-skid, porosity).
BOAT_LIBRARY = {
    "Topsides": ("M_BoatSurface", (0.80, 0.80, 0.77), 0.30, 0.0, 1.0, 0.0, 0.10),     # white gelcoat
    "Deck": ("M_BoatSurface", (0.80, 0.80, 0.76), 0.35, 0.0, 1.0, 0.0, 0.10),
    "NonSkid": ("M_BoatSurface", (0.70, 0.70, 0.66), 0.62, 0.0, 0.3, 1.0, 0.30),
    "Bootstripe": ("M_BoatSurface", (0.010, 0.018, 0.080), 0.25, 0.0, 1.0, 0.0, 0.05),  # navy gelcoat stripes
    "CoveStripe": ("M_BoatSurface", (0.010, 0.018, 0.080), 0.25, 0.0, 1.0, 0.0, 0.05),
    "Antifouling": ("M_BoatSurface", (0.015, 0.022, 0.050), 0.80, 0.0, 0.0, 0.0, 0.60),  # ablative bottom paint
    "Keel": ("M_BoatSurface", (0.015, 0.022, 0.050), 0.75, 0.0, 0.0, 0.0, 0.60),
    "CabinWindow": ("M_BoatSurface", (0.006, 0.008, 0.010), 0.04, 0.0, 1.0, 0.0, 0.0),  # smoked acrylic
    "Stainless": ("M_BoatSurface", (0.72, 0.72, 0.74), 0.14, 1.0, 0.0, 0.0, 0.0),
    "Aluminium": ("M_BoatSurface", (0.78, 0.79, 0.81), 0.32, 1.0, 0.0, 0.0, 0.0),        # clear anodized spars
    "BlackPlastic": ("M_BoatSurface", (0.018, 0.018, 0.020), 0.45, 0.0, 0.0, 0.0, 0.05),
    "Wood": ("M_BoatSurface", (0.30, 0.17, 0.07), 0.30, 0.0, 1.0, 0.0, 0.15),           # varnished ash tiller
    "Graphics": ("M_BoatSurface", (0.45, 0.015, 0.02), 0.28, 0.0, 1.0, 0.0, 0.05),
    "Rubrail": ("M_BoatSurface", (0.03, 0.03, 0.03), 0.5, 0.0, 0.0, 0.0, 0.1),
    # The crew (Visual V3): foul-weather jacket (recoloured per sailor), PFD, trousers, deck boots, skin, cap, glasses.
    "CrewJacket": ("M_BoatSurface", (0.45, 0.03, 0.03), 0.55, 0.0, 0.2, 0.0, 0.20),
    "CrewPFD": ("M_BoatSurface", (0.02, 0.03, 0.10), 0.60, 0.0, 0.0, 0.0, 0.30),
    "CrewTrousers": ("M_BoatSurface", (0.03, 0.03, 0.035), 0.70, 0.0, 0.0, 0.0, 0.50),
    "CrewBoots": ("M_BoatSurface", (0.55, 0.55, 0.57), 0.50, 0.0, 0.0, 0.0, 0.10),
    "CrewSkin": ("M_BoatSurface", (0.42, 0.28, 0.21), 0.55, 0.0, 0.0, 0.0, 0.10),
    "CrewCap": ("M_BoatSurface", (0.72, 0.72, 0.72), 0.80, 0.0, 0.0, 0.0, 0.40),
    "CrewGlasses": ("M_BoatSurface", (0.01, 0.01, 0.012), 0.05, 0.0, 1.0, 0.0, 0.0),
    "CrewHair": ("M_BoatSurface", (0.05, 0.04, 0.03), 0.60, 0.0, 0.0, 0.0, 0.30),
    "Rope": ("M_BoatSurface", (0.62, 0.64, 0.68), 0.75, 0.0, 0.0, 0.0, 0.50),         # braided polyester sheets
    "MastAluminium": ("M_BoatMast", (0.78, 0.79, 0.81), 0.32, 1.0, 0.0, 0.0, 0.0),
}


def build_boat_library():
    parents = {"M_BoatSurface": build_boat_surface("M_BoatSurface", False), "M_BoatMast": build_boat_surface("M_BoatMast", True)}
    for slot, (parent, col, rough, metal, coat, nonskid, porosity) in BOAT_LIBRARY.items():
        name = f"MI_Boat_{slot}"
        path = f"{BOAT_FOLDER}/{name}"
        # Updated in place (never deleted): the boat meshes reference these instances.
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            mi = unreal.load_asset(path)
        else:
            mi = ASSETS.create_asset(name, BOAT_FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, parents[parent])
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(col[0], col[1], col[2], 1.0))
        for pname, value in (("Roughness", rough), ("Metallic", metal), ("ClearCoat", coat), ("NonSkid", nonskid), ("Porosity", porosity)):
            MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)


# ---------------------------------------------------------------- sails (Visual V3)
SAIL_CODE = r"""
// Visual V3 sail cloth. UV0: metres (x along the chord from the luff, y up from the foot); UV1: normalized planform;
// UV2.x: metres from the leech. Crosscut seams every 0.9 m, batten pockets on the main's leech, the class insignia and
// sail number from the marks atlas (top half insignia, bottom half number).
float seamDist = abs(frac(UV0.y / 0.9 + 0.5) - 0.5) * 0.9;
float seam = 1.0 - smoothstep(0.006, 0.010, seamDist);
float batten = 0.0;
for (int i = 1; i <= 4; i++)
{
    float vb = 0.2 * i;
    float len = 0.45 + 0.25 * (i == 2 || i == 3);
    batten = max(batten, (1.0 - smoothstep(0.018, 0.026, abs(UV1.y - vb) * Height)) * (1.0 - smoothstep(len - 0.02, len, UV2.x)));
}
batten *= Battens;
float mark = 0.0;
float3 ink = float3(0.0, 0.0, 0.0);
if (Marks > 0.5)
{
    float2 r0 = (UV1 - float2(0.30, 0.79)) / float2(0.46, 0.09);
    float2 r1 = (UV1 - float2(0.24, 0.62)) / float2(0.58, 0.12);
    if (all(r0 >= 0.0) && all(r0 <= 1.0)) { float4 t = Tex.SampleLevel(TexSampler, float2(r0.x, 0.5 - r0.y * 0.5), 0); mark = t.a; ink = t.rgb; }
    if (all(r1 >= 0.0) && all(r1 <= 1.0)) { float4 t = Tex.SampleLevel(TexSampler, float2(r1.x, 1.0 - r1.y * 0.5), 0); mark = t.a; ink = t.rgb; }
}
// A faint weave and the panels' slight tone differences.
float weave = 0.5 + 0.5 * sin(UV0.x * 1400.0) * sin(UV0.y * 1400.0);
float panel = frac(sin(floor(UV0.y / 0.9) * 12.9898) * 43758.5453);
float3 cloth = C.rgb * (0.97 + 0.03 * weave) * (0.985 + 0.03 * panel);
float3 col = lerp(cloth * (1.0 - 0.12 * seam), C.rgb * 0.93, batten);
col = lerp(col, ink, mark);
// Against the sun the cloth glows; seams (double layer), batten pockets and ink are darker from behind.
Transmit = C.rgb * 0.7 * (1.0 - 0.55 * seam) * (1.0 - 0.75 * batten) * (1.0 - 0.9 * mark);
return col;
"""


def sail_marks_texture():
    import os
    path = f"{FOLDER}/T_SailMarks"
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Artifacts", "textures", "T_SailMarks.png")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", FOLDER)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    ASSETS.import_asset_tasks([task])
    return unreal.load_asset(path)


def build_sail_cloth():
    """M_SailCloth: two-sided Dacron that lets the sun through (two-sided foliage: lit from behind it glows), with the
    seams, batten pockets, insignia and number drawn from the cloth mesh's UVs (FSailCloth)."""
    mat = new_material("M_SailCloth")
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    color = vector(mat, "Color", (0.82, 0.82, 0.80, 1), -1200, -100)
    battens = scalar(mat, "Battens", 0.0, -1200, 50)
    marks = scalar(mat, "Marks", 0.0, -1200, 150)
    height = scalar(mat, "Height", 7.6, -1200, 250)
    rough = scalar(mat, "Roughness", 0.62, -400, 300)
    tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1200, 350, parameter_name="SailMarks", texture=sail_marks_texture())
    uv = [node(mat, unreal.MaterialExpressionTextureCoordinate, -1200, 500 + 100 * i, coordinate_index=i) for i in range(3)]
    c = custom(mat, SAIL_CODE, ["C", "Battens", "Marks", "Height", "Tex", "UV0", "UV1", "UV2"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, 100,
               extra_outputs=[("Transmit", unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    for src, pin in ((color, "C"), (battens, "Battens"), (marks, "Marks"), (height, "Height"), (tex, "Tex"), (uv[0], "UV0"), (uv[1], "UV1"), (uv[2], "UV2")):
        connect(src, "RGBA" if src is color else "", c, pin)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Transmit", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    # Instances: the J/22 main (battens, insignia, number), the jib, the spinnaker (nylon, red).
    for name, col, bat, mk, h in (("MI_Sail_Main", (0.82, 0.82, 0.80), 1.0, 1.0, 7.6), ("MI_Sail_Jib", (0.82, 0.82, 0.80), 0.0, 0.0, 7.5),
                                  ("MI_Sail_Spinnaker", (0.55, 0.03, 0.03), 0.0, 0.0, 7.0)):
        path = f"{FOLDER}/{name}"
        mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
            ASSETS.create_asset(name, FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, mat)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(col[0], col[1], col[2], 1.0))
        for pname, value in (("Battens", bat), ("Marks", mk), ("Height", h), ("Roughness", 0.62 if name != "MI_Sail_Spinnaker" else 0.45)):
            MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)


def build_telltale():
    """M_Telltale: two-sided ribbons coloured by vertex colour (red to port, green to starboard)."""
    mat = new_material("M_Telltale")
    mat.set_editor_property("two_sided", True)
    vc = node(mat, unreal.MaterialExpressionVertexColor, -500, 0)
    rough = node(mat, unreal.MaterialExpressionConstant, -500, 200, r=0.7)
    MEL.connect_material_property(vc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


# ---------------------------------------------------------------- water, Visual V4 (Medium and High)
NUM_LONG = 24  # FWaveField's first eight bands (under AWaterSurface::SplitHz, 3.6 m and longer)


def long_wave_terms():
    """The physics' wave trains longer than 3.6 m (its first eight bands), drawn exactly, with Gerstner choppiness:
    vertices move toward the crests (crests sharpen, troughs flatten); the Jacobian of that map is where crests fold.
    Straight-line code (no branches): the vertex shader runs it for every ring vertex."""
    lines = []
    for i in range(NUM_LONG):
        amp = f"A{i // 4}.{'xyzw'[i % 4]}"
        w = f"W{i}"
        arg = f"{w}.x * p.x + {w}.y * p.y - {w}.z * T + {w}.w"
        lines.append(f"{{ float s, c; sincos({arg}, s, c); float k = length({w}.xy); float2 kd = {w}.xy / k; h += {amp} * s; d += Chop * {amp} * kd * c; "
                     f"float a = {amp} * saturate(6.2832 / (k * spacing) / 4.0 - 1.0); lsx += a * {w}.x * c; lsy += a * {w}.y * c; "
                     f"float q = Chop * a * s / k; ljxx -= q * {w}.x * {w}.x; ljyy -= q * {w}.y * {w}.y; ljxy -= q * {w}.x * {w}.y; }}")
    return "\n".join(lines)


V4_WPO = """
// The vertex: the long waves (their height and choppy displacement; and their slopes and fold, which the pixels get
// interpolated: at 3.6 m and longer the mesh carries them, each train fading before the mesh spacing would alias it).
float3 p = P * 0.01;
float3 cam = Cam * 0.01;
float dist = distance(p.xy, cam.xy);
float fade = saturate(1.0 - dist / Fade);
float spacing = max(0.5, dist / 64.0);
float h = 0.0;
float2 d = float2(0.0, 0.0);
float lsx = 0.0, lsy = 0.0, ljxx = 1.0, ljyy = 1.0, ljxy = 0.0;
""" + long_wave_terms() + """
h *= fade; d *= fade;
lsx *= fade; lsy *= fade;
ljxx = lerp(1.0, ljxx, fade); ljyy = lerp(1.0, ljyy, fade); ljxy *= fade;
// The short waves (FFT of the same spectrum, FWaveDetail), near the camera.
float df = saturate(1.0 - dist / DetailP.z);
[branch] if (df > 0.0)
{
    float4 da = DetailA.SampleLevel(DetailASampler, float2(p.y, p.x) / DetailP.x + 0.5 / 128.0, 0);
    h += da.r * df;
    d += da.gb * df;
}
// The water the boats push around (FWakeGrid).
float2 wg = (p.xy - WakeGridRect.xy) / WakeGridRect.z;
[branch] if (all(wg > 0.0) && all(wg < 1.0)) h += WakeGrid.SampleLevel(WakeGridSampler, float2(wg.y, wg.x), 0).r;
float ho = 0.0;
[branch] if (OceanP.z > 0.0)
{
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    float om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
    float of = om * saturate(1.0 - dist / OceanP.w);
    float4 oa = OceanA.SampleLevel(OceanASampler, float2(p.y, p.x) / OceanP.x + 0.5 / 64.0, 0);
    float4 ob = OceanB.SampleLevel(OceanBSampler, float2(p.y, p.x) / OceanP.y + 0.5 / 64.0, 0);
    ho = (oa.r + ob.r) * of;
}
// The long waves' slopes and fold for the pixels (interpolated), from the same sincos.
LongN = float3(lsx, lsy, ljxx * ljyy - ljxy * ljxy);
// The shore: waves grow a little as they feel the bottom (shoaling) and die on the beach.
float2 su = (p.xy - ShoreRect.xy) / ShoreRect.z;
[branch] if (ShoreRect.w > 0.0 && all(su > 0.0) && all(su < 1.0))
{
    float sd = ShoreMap.SampleLevel(ShoreMapSampler, float2(su.y, su.x), 0).r;
    float k = saturate(sd / 0.6) * (1.0 + 0.25 * saturate(1.0 - sd / 2.0));
    h *= k; d *= k; ho *= k;
}
return float3(d.x * 100.0, d.y * 100.0, (h + ho) * 100.0);
"""

V4_SHADE = """
float3 p = P * 0.01;
float3 cam = Cam * 0.01;
float dist = distance(p.xy, cam.xy);
float fade = saturate(1.0 - dist / Fade);
// The long waves, from the vertices (V4_WPO).
float sx = LongN.x, sy = LongN.y;
float J = LongN.z;
// Cat's paws: the wind's surface roughness map (local wind relative to 15 kn). In a lee (the shelter map, a puff's
// edge) the short waves and ripples the local wind raises are smaller.
float2 guv = (p.xy - GustRect.xy) / GustRect.z + 0.5;
float rough = Gust.SampleLevel(GustSampler, guv, 0).r * 2.5;
float gustRatio = (rough * 8.0) / max(WindP.z, 1.0);
float calm = saturate(0.25 + 0.75 * gustRatio);
// Heavy rain beats down the short waves (and greys the surface: below).
calm *= 1.0 - 0.5 * Rain;
// The shore: depth from the shore map (deep where it doesn't reach).
float2 su = (p.xy - ShoreRect.xy) / ShoreRect.z;
float sd = 100.0;
[branch] if (ShoreRect.w > 0.0 && all(su > 0.0) && all(su < 1.0)) sd = ShoreMap.SampleLevel(ShoreMapSampler, float2(su.y, su.x), 0).r;
float shoal = saturate(1.0 - sd / 2.0) * saturate(sd / 0.1);
// Short waves and ripples: slopes for the normals, the Jacobian for the foam. Mip-mapped and filtered by the hardware
// (anisotropic at grazing angles), so they never sparkle in the distance; the slope variance a mip averages away (the
// textures carry the squared slopes too: LEAN mapping) becomes roughness, so the sun's glitter path keeps its width.
float2 duv = float2(p.y, p.x) / DetailP.x + 0.5 / 128.0;
float4 da = Texture2DSample(DetailA, DetailASampler, duv);
float4 db = Texture2DSample(DetailB, DetailBSampler, duv);
sx += db.r * calm; sy += db.g * calm;
float jd = lerp(1.0, da.a, calm);
float slopeVar = (max(db.b - db.r * db.r, 0.0) + max(db.a - db.g * db.g, 0.0)) * calm * calm;
if (DetailP.w > 0.0)
{
    float4 rb = Texture2DSample(RippleB, RippleBSampler, float2(p.y, p.x) / DetailP.y + 0.5 / 64.0);
    sx += rb.r * calm; sy += rb.g * calm;
    slopeVar += (max(rb.b - rb.r * rb.r, 0.0) + max(rb.a - rb.g * rb.g, 0.0)) * calm * calm;
}
float far = saturate((dist - 0.5 * DetailP.z) / (2.0 * DetailP.z));
// The boats' own waves: slopes by finite differences, and their foam.
float2 wg = (p.xy - WakeGridRect.xy) / WakeGridRect.z;
float wakeFoam = 0.0;
[branch] if (all(wg > 0.001) && all(wg < 0.999))
{
    float e = 1.0 / WakeGridRect.w;
    float2 uv = float2(wg.y, wg.x);
    float2 c = WakeGrid.SampleLevel(WakeGridSampler, uv, 0).rg;
    float hx = WakeGrid.SampleLevel(WakeGridSampler, uv + float2(0.0, e), 0).r - WakeGrid.SampleLevel(WakeGridSampler, uv - float2(0.0, e), 0).r;
    float hy = WakeGrid.SampleLevel(WakeGridSampler, uv + float2(e, 0.0), 0).r - WakeGrid.SampleLevel(WakeGridSampler, uv - float2(e, 0.0), 0).r;
    float cell = WakeGridRect.z / WakeGridRect.w;
    sx += hx / (2.0 * cell); sy += hy / (2.0 * cell);
    wakeFoam = c.g;
}
[branch] if (OceanP.z > 0.0)
{
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    float om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
    float of = om * saturate(1.0 - dist / OceanP.w);
    float4 oa = OceanA.SampleLevel(OceanASampler, float2(p.y, p.x) / OceanP.x + 0.5 / 64.0, 0);
    float4 ob = OceanB.SampleLevel(OceanBSampler, float2(p.y, p.x) / OceanP.y + 0.5 / 64.0, 0);
    sx += (oa.g + ob.g) * of; sy += (oa.b + ob.b) * of;
}
// Rain: rings spreading from drops, a fresh set every few tenths of a second in each 40 cm cell, by the rain rate.
[branch] if (Rain > 0.01 && dist < 80.0)
{
    for (int layer = 0; layer < 2; layer++)
    {
        float2 q = p.xy / 0.4 + layer * 0.37;
        float2 cellId = floor(q);
        float rnd = frac(sin(dot(cellId, float2(12.9898, 78.233)) + layer) * 43758.5453);
        float2 centre = cellId + 0.5 + 0.35 * float2(frac(rnd * 13.1) - 0.5, frac(rnd * 7.7) - 0.5);
        float life = frac(T * 1.6 + rnd);
        float2 off = q - centre;
        float r = length(off);
        float ring = sin((r - life * 0.55) * 50.0) * saturate(1.0 - abs(r - life * 0.55) * 8.0) * (1.0 - life) * step(rnd, Rain * 1.2);
        float2 g = off / max(r, 1e-3) * ring * 0.35;
        sx += g.x; sy += g.y;
    }
}
// Whitecaps: where the crests fold (the Jacobian of the choppy waves drops under 0.6), as many as the Monahan
// law gives for the wind (SailingSim.Visual.Whitecaps); the foam they leave lingers on the back of the wave in
// streaks along the wind, and breaks up as it fades.
// Shoaling waves steepen; in the last half metre they die on the beach.
sx *= (1.0 + 0.6 * shoal) * saturate(sd / 0.4 + 0.2); sy *= (1.0 + 0.6 * shoal) * saturate(sd / 0.4 + 0.2);
float Jt = J * jd - 0.25 * shoal;
// Lacy, broken foam rather than flat patches: two crossed wavy bands at foam-bubble scale.
float lace = (0.5 + 0.5 * sin(p.x * 9.1 + sin(p.y * 7.3) * 1.7)) * (0.5 + 0.5 * sin(p.y * 8.3 + sin(p.x * 6.1 + T * 0.2) * 1.9));
float crest = saturate((FoamThreshold - Jt) / 0.05) * saturate(0.35 + 1.3 * lace);
float2 wd = normalize(WindP.xy + float2(1e-4, 0.0));
float2 wn = float2(-wd.y, wd.x);
float streak = 0.5 + 0.5 * sin(dot(p.xy, wn) * 7.0 + sin(dot(p.xy, wd) * 0.6) * 2.5);
float residue = saturate((FoamThreshold + 0.08 - Jt) / 0.08) * smoothstep(0.55, 0.95, streak * lace) * 0.25;
float caps = max(crest, residue) * fade;
// Far off whitecaps are sub-pixel: their average whiteness, from the same law.
float knots = rough * 15.56;
float farCover = 3.0 * 3.84e-6 * pow(max(knots * 0.5144, 0.0), 3.41); // Monahan's coverage, with the foam it leaves
caps = lerp(caps, saturate(farCover), far);
// Foam the boats make.
float bubbles = (0.5 + 0.5 * sin(p.x * 13.1 + sin(p.y * 9.7) * 2.1)) * (0.5 + 0.5 * sin(p.y * 11.3 + sin(p.x * 8.9 + T * 0.4) * 2.3));
float wakeBreak = saturate(wakeFoam * 2.0 - (1.0 - bubbles) * 1.1) * 0.85;
// Lapping: a line of foam where the wavelets run up the shore, the riprap and the docks, coming and going with them.
float swash = saturate(1.0 - sd / 0.35) * saturate(WindP.z / 4.0);
float lap = swash * saturate(0.35 + 0.65 * sin(T * 1.7 + dot(p.xy, wd) * 1.3 + lace * 2.5)) * (0.45 + 0.55 * lace);
// Heavy rain: splashes and mist grey the surface.
Foam = saturate(max(caps + wakeBreak, 0.85 * lap) + 0.10 * Rain);
Dark = saturate((gustRatio - 0.95) * 2.5);
// Glint: a calm morning's sharp sun path, broadening with the wind and the ripples it raises; rain flattens and greys.
float r0 = lerp(0.015, 0.22, saturate((rough - 0.3) * 0.7));
// GGX alpha = roughness^2; the unresolved slope variance adds to it (scaled down: the engine's GGX has no multiple
// scattering, so a fully rough grazing reflection comes out darker than the sky sheen real water shows).
float alpha = sqrt(r0 * r0 * r0 * r0 + 0.3 * slopeVar);
Rough = sqrt(alpha) + 0.08 * saturate((gustRatio - 1.0) * 3.0) + Rain * 0.12;
return normalize(float3(-sx, -sy, 1.0));
"""


def build_water_v4():
    """M_WaterV4 (Visual V4, Medium and High): the physics' long waves drawn exactly with Gerstner choppiness, the short
    waves from the FFT of the same spectrum, whitecaps from folding crests, the boats' own waves (iWave), rain rings,
    and Single Layer Water: light absorbed and scattered by the water body itself (olive-brown and murky on the lake,
    grey-green on the bay, blue-green offshore), the bottom showing through in the shallows, the hull refracted below."""
    mat = new_material("M_WaterV4")
    pos = node(mat, unreal.MaterialExpressionWorldPosition, -1800, 0)
    pos.set_editor_property("world_position_shader_offset", unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    cam = node(mat, unreal.MaterialExpressionCameraPositionWS, -1800, 100)
    time = scalar(mat, "WaveTime", 0.0, -1800, 200)
    fade = scalar(mat, "WaveFadeMeters", 900.0, -1800, 300)
    chop = scalar(mat, "Choppiness", 1.5, -1800, 460)
    thr = scalar(mat, "FoamThreshold", 0.6, -1800, 540)
    waves = [vector(mat, f"Wave{i:02d}", (0, 0, 0, 0), -1600, -2000 + i * 60) for i in range(NUM_WAVES)]
    amps = [vector(mat, f"WaveAmp{i:02d}", (0, 0, 0, 0), -1400, -2000 + i * 60) for i in range(NUM_WAVES // 4)]
    linear = linear_default()
    def tex(name, y):
        return node(mat, unreal.MaterialExpressionTextureObjectParameter, -1800, y, parameter_name=name, texture=linear,
                    sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    tx = {n: tex(n, 1300 + 150 * i) for i, n in enumerate(("OceanA", "OceanB", "OceanMask", "DetailA", "DetailB", "RippleB", "WakeGrid", "ShoreMap"))}
    ocean_p = vector(mat, "OceanParams", (480, 60, 0, 6000), -1800, 2400)
    ocean_rect = vector(mat, "OceanMaskRect", (0, 0, 1, 1), -1800, 2500)
    # x: chop tile (m), y: ripple tile (m), z: distance the short waves fade over (m), w: 1 = ripples on (High).
    detail_p = vector(mat, "DetailParams", (23, 3.1, 300, 0), -1800, 2600)
    wake_rect = vector(mat, "WakeGridRect", (0, 0, 25.6, 128), -1800, 2700)
    # Shore map (water depth, m): x0, y0, size (m), w = 1 when bound.
    shore_rect = vector(mat, "ShoreRect", (0, 0, 1, 0), -1800, 2800)
    common = ["P", "Cam", "T", "Fade", "Chop"] + [f"W{i}" for i in range(NUM_LONG)] + [f"A{i}" for i in range(NUM_LONG // 4)] \
        + ["OceanA", "OceanB", "OceanMask", "OceanP", "OceanMaskRect", "DetailA", "DetailP", "WakeGrid", "WakeGridRect", "ShoreMap", "ShoreRect"]
    wpo = custom(mat, V4_WPO, common, unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, -400,
                 extra_outputs=[("LongN", unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    interp = node(mat, unreal.MaterialExpressionVertexInterpolator, -400, -900)
    connect(wpo, "LongN", interp, "")
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    gust_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1800, 700, parameter_name="GustMap", texture=white)
    gust_rect = vector(mat, "GustRect", (0, 0, 1600, 0), -1800, 800)
    wind = vector(mat, "WindParams", (1, 0, 5, 0), -1800, 900)
    rain = scalar(mat, "Rain", 0.0, -1800, 1000)
    F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    shade_common = ["P", "Cam", "T", "Fade", "OceanA", "OceanB", "OceanMask", "OceanP", "OceanMaskRect", "DetailA", "DetailP", "WakeGrid", "WakeGridRect", "ShoreMap", "ShoreRect"]
    shade = custom(mat, V4_SHADE, shade_common + ["LongN", "DetailB", "RippleB", "Gust", "GustRect", "WindP", "Rain", "FoamThreshold"],
                   unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, 400, extra_outputs=[("Foam", F1), ("Rough", F1), ("Dark", F1)])
    for c in (wpo,):
        connect(chop, "", c, "Chop")
        for i, w in enumerate(waves[:NUM_LONG]):
            connect(w, "RGBA", c, f"W{i}")
        for i, a in enumerate(amps[:NUM_LONG // 4]):
            connect(a, "RGBA", c, f"A{i}")
    for c in (wpo, shade):
        connect(pos, "", c, "P")
        connect(cam, "", c, "Cam")
        connect(time, "", c, "T")
        connect(fade, "", c, "Fade")
    connect(interp, "", shade, "LongN")
    for c in (wpo, shade):
        for n in ("OceanA", "OceanB", "OceanMask", "DetailA", "WakeGrid", "ShoreMap"):
            connect(tx[n], "", c, n)
        connect(shore_rect, "RGBA", c, "ShoreRect")
        connect(ocean_p, "RGBA", c, "OceanP")
        connect(ocean_rect, "RGBA", c, "OceanMaskRect")
        connect(detail_p, "RGBA", c, "DetailP")
        connect(wake_rect, "RGBA", c, "WakeGridRect")
    connect(tx["DetailB"], "", shade, "DetailB")
    connect(tx["RippleB"], "", shade, "RippleB")
    connect(gust_tex, "", shade, "Gust")
    connect(gust_rect, "RGBA", shade, "GustRect")
    connect(wind, "RGBA", shade, "WindP")
    connect(rain, "", shade, "Rain")
    connect(thr, "", shade, "FoamThreshold")

    # Surface: foam on top (opaque, white, rough); the water body itself is light the water absorbs and scatters.
    albedo = vector(mat, "WaterAlbedo", (0.16, 0.18, 0.11, 1), -400, 900)        # Ray Hubbard: olive grey-green silt
    extinction = vector(mat, "WaterExtinction", (2.6, 2.4, 3.2, 1), -400, 1000)  # 1/m: about half a metre of visibility
    phase = scalar(mat, "WaterPhaseG", 0.3, -400, 1100)
    foam_col = node(mat, unreal.MaterialExpressionConstant3Vector, -400, 1200, constant=unreal.LinearColor(0.85, 0.88, 0.9, 1))
    foam_rough = node(mat, unreal.MaterialExpressionConstant, -400, 1300, r=0.7)
    rough_mix = node(mat, unreal.MaterialExpressionLinearInterpolate, -200, 1300)
    connect(shade, "Rough", rough_mix, "A")
    connect(foam_rough, "", rough_mix, "B")
    connect(shade, "Foam", rough_mix, "Alpha")
    to_tangent = node(mat, unreal.MaterialExpressionTransform, -300, 500)
    to_tangent.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
    to_tangent.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
    connect(shade, "", to_tangent, "")
    # Ruffled water (a puff, the gust front) reflects less of the sky: scale the scattering a little darker there.
    dark_k = node(mat, unreal.MaterialExpressionMultiply, -200, 950)
    dk = node(mat, unreal.MaterialExpressionConstant, -400, 1450, r=-0.35)
    connect(shade, "Dark", dark_k, "A")
    connect(dk, "", dark_k, "B")
    dark_scale = node(mat, unreal.MaterialExpressionAdd, -100, 950)
    one = node(mat, unreal.MaterialExpressionConstant, -400, 1500, r=1.0)
    connect(one, "", dark_scale, "A")
    connect(dark_k, "", dark_scale, "B")
    albedo_dark = node(mat, unreal.MaterialExpressionMultiply, 0, 900)
    connect(albedo, "", albedo_dark, "A")
    connect(dark_scale, "", albedo_dark, "B")
    slw = node(mat, unreal.MaterialExpressionSubstrateSingleLayerWaterBSDF, 200, 600)
    connect(foam_col, "", slw, "BaseColor")
    connect(rough_mix, "", slw, "Roughness")
    connect(to_tangent, "", slw, "Normal")
    connect(shade, "Foam", slw, "TopMaterialOpacity")
    connect(albedo_dark, "", slw, "WaterAlbedo")
    connect(extinction, "", slw, "WaterExtinction")
    connect(phase, "", slw, "WaterPhaseG")
    MEL.connect_material_property(slw, "", unreal.MaterialProperty.MP_FRONT_MATERIAL)
    MEL.connect_material_property(wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


build_water()
build_water_v4()
build_spray()
build_terrain()
build_rain()
build_emissive()
build_sail()
build_ghost()
build_lens_distortion()
build_boat_library()
build_sail_cloth()
build_telltale()
unreal.log("Materials built")
