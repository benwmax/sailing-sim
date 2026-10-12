"""Builds the Phase 2 materials in /Game/Materials from code, so they can be regenerated and reviewed.

- M_Water: lake surface. Vertex shader displaces by the same 48-wave sum the physics uses (FWaveField);
  pixel shader adds per-pixel wave normals, wind ripples from the cat's-paw map (the wind field's surface
  roughness), rain ripples, whitecaps and wake foam.
- M_Rain: translucent falling streaks for cylinders around the camera.
- M_Emissive: unlit glow (lightning).
- M_Sail: two-sided lit cloth.
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
return float3(0.0, 0.0, h * fade * 100.0);
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
// Whitecaps on steep crests once the wind is up.
float slope = length(float2(sx, sy));
// Whitecaps follow the local wind (from the cat's-paw map), so a gust front shows as a band of breaking crests.
float localKnots = rough * 15.56;
float capsLevel = saturate((localKnots - 11.0) / 7.0);
float capNoise = saturate(sin(p.x * 1.7 + sin(p.y * 1.3 + T * 0.7) * 2.0) * sin(p.y * 2.1 - T * 0.9 + sin(p.x * 0.9)) * 2.0);
float caps = saturate((slope - 0.26) * 4.0) * saturate(h * 6.0) * capsLevel * (0.4 + 0.6 * capNoise) * 0.7;
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

    common = ["P", "Cam", "T", "Fade"] + [f"W{i}" for i in range(NUM_WAVES)] + [f"A{i}" for i in range(NUM_WAVES // 4)]
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
    connect(gust_tex, "", shade, "Gust")
    connect(wake_tex, "", shade, "Wake")
    connect(gust_rect, "RGBA", shade, "GustRect")
    connect(wake_rect, "RGBA", shade, "WakeRect")
    connect(wind, "RGBA", shade, "WindP")
    connect(rain, "", shade, "Rain")
    connect(debug, "", shade, "DebugGust")

    # Turbid green-brown Texas lake water; foam is white and rough.
    water_color = vector(mat, "WaterColor", (0.018, 0.045, 0.042, 1), -300, 600)
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


build_water()
build_terrain()
build_rain()
build_emissive()
build_sail()
unreal.log("Materials built")
