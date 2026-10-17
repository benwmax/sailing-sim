"""Builds the Phase 2 materials in /Game/Materials from code, so they can be regenerated and reviewed.

- M_Water: water surface. Vertex shader displaces by the same 48-wave sum the physics uses (FWaveField), plus on
  the open sea the FFT ocean's two cascades (FOcean, uploaded as float textures each frame, masked where the sea
  reaches);
  pixel shader adds per-pixel wave normals, wind ripples from the cat's-paw map (the wind field's surface
  roughness), rain ripples, whitecaps and wake foam.
- M_Rain: translucent falling streaks for cylinders around the camera.
- M_RainCurtain (W5b): a storm's rain curtains and rain foot seen from afar, instanced cards facing the camera.
- M_Emissive: unlit glow (lightning).
- M_Sail: two-sided lit cloth.
- M_BoatSurface, M_BoatMast and the MI_Boat_* library (Visual V2): gelcoat with clear coat, antifouling, non-skid,
  metals, plastic and varnished wood; wet below the splash line and on deck in rain and spray (MPC_Boat).
Run with scripts/make-content.sh.
"""
import os
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


CURVATURE_CODE = """
// Visual V6: the earth's curvature as the eye sees it over water: everything drops d^2 / 2R below the camera's tangent
// plane, with R the earth's radius stretched by standard refraction (7/6 of 6371 km). 8 m at 10 km, 31 m at 20 km: far
// shores sink behind the horizon and a tower's foot is lost before its top.
float2 d = (WP - Cam).xy;
return float3(0.0, 0.0, -dot(d, d) / (2.0 * 7.433e8));
"""


def curvature(mat, x, y):
    """A WPO node (cm) for the earth's curvature; add it to the material's other offsets."""
    c = custom(mat, CURVATURE_CODE, ["WP", "Cam"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, x, y)
    connect(node(mat, unreal.MaterialExpressionWorldPosition, x - 300, y), "", c, "WP")
    connect(node(mat, unreal.MaterialExpressionCameraPositionWS, x - 300, y + 80), "", c, "Cam")
    return c


def with_curvature(mat, wpo, x, y):
    """wpo + the curvature drop."""
    add = node(mat, unreal.MaterialExpressionAdd, x, y)
    connect(wpo, "", add, "A")
    connect(curvature(mat, x - 300, y + 100), "", add, "B")
    return add


# ---------------------------------------------------------------- water
# W3, sea state by direction (SeaState.h, docs/water-3): how much of each wave train there is at a point. The atlas
# (AWaterSurface::UploadSeaMap) is seven tiles side by side, each Cols x Rows texels of RGBA half floats: tile t's channel
# c scales component 4t + c (the long waves, as the WaveAmp vectors pack them), tile 6's R the short waves (the rest of
# the components and the FFT detail). SeaRect: origin north, east (m), cell (m), rows; SeaP: cols, atlas width, height,
# 1 when bound (else every ratio is 1). The index is clamped inside a tile, as FSeaMap::Sample clamps at the edge, so
# the bilinear filter never reads the next tile. Mirrors FSeaMap::Sample.
SEA_ATLAS = """
float2 seaI = clamp(float2((p.x - SeaRect.x) / SeaRect.z, (p.y - SeaRect.y) / SeaRect.z), 0.0, float2(SeaRect.w - 1.0, SeaP.x - 1.0));
float2 seaUV = float2(seaI.y + 0.5, seaI.x + 0.5) / SeaP.yz;
float seaTile = SeaP.x / SeaP.y;
float4 S0 = lerp(1.0, Sea.SampleLevel(SeaSampler, seaUV, 0), SeaP.w);
float4 S1 = lerp(1.0, Sea.SampleLevel(SeaSampler, seaUV + float2(seaTile, 0.0), 0), SeaP.w);
float4 S2 = lerp(1.0, Sea.SampleLevel(SeaSampler, seaUV + float2(2.0 * seaTile, 0.0), 0), SeaP.w);
float4 S3 = lerp(1.0, Sea.SampleLevel(SeaSampler, seaUV + float2(3.0 * seaTile, 0.0), 0), SeaP.w);
float4 S4 = lerp(1.0, Sea.SampleLevel(SeaSampler, seaUV + float2(4.0 * seaTile, 0.0), 0), SeaP.w);
float4 S5 = lerp(1.0, Sea.SampleLevel(SeaSampler, seaUV + float2(5.0 * seaTile, 0.0), 0), SeaP.w);
float SShort = lerp(1.0, Sea.SampleLevel(SeaSampler, seaUV + float2(6.0 * seaTile, 0.0), 0).r, SeaP.w);
"""

# The short scale alone (the pixels' FFT detail).
SEA_SHORT = """
float2 seaI = clamp(float2((p.x - SeaRect.x) / SeaRect.z, (p.y - SeaRect.y) / SeaRect.z), 0.0, float2(SeaRect.w - 1.0, SeaP.x - 1.0));
float SShort = lerp(1.0, Sea.SampleLevel(SeaSampler, float2(seaI.y + 0.5 + 6.0 * SeaP.x, seaI.x + 0.5) / SeaP.yz, 0).r, SeaP.w);
"""


def sea_amps(n):
    """The amplitude vectors scaled by the sea map: A<i>s."""
    return "\n".join(f"float4 A{i}s = A{i} * " + (f"S{i}" if i < 6 else "SShort") + ";" for i in range(n // 4))


def sea_params(mat, x, y):
    """The sea atlas and its rectangles (unbound: SeaP.w = 0, every ratio 1)."""
    linear = linear_default()
    t = node(mat, unreal.MaterialExpressionTextureObjectParameter, x, y, parameter_name="SeaMap", texture=linear,
             sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    return t, vector(mat, "SeaRect", (0, 0, 50, 1), x, y + 150), vector(mat, "SeaParams", (1, 7, 1, 0), x, y + 250)


def connect_sea(sea, c):
    connect(sea[0], "", c, "Sea")
    connect(sea[1], "RGBA", c, "SeaRect")
    connect(sea[2], "RGBA", c, "SeaP")


def wave_terms(kind):
    lines = []
    for i in range(NUM_WAVES):
        amp = f"A{i // 4}s.{'xyzw'[i % 4]}"
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
""" + SEA_ATLAS + sea_amps(NUM_WAVES) + wave_terms("height") + """
float ho = 0.0;
float om = 0.0;
[branch] if (OceanP.z > 0.0)
{
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
}
// W2 (the gulf-swell handoff): the FFT ocean only where the mask lets the open sea in (in the bay it cost 0.1 to
// 0.17 ms for nothing). Two cascades (texel i,j = the grid point at x = i * cell north, y = j * cell east), faded far out.
[branch] if (om > 0.001)
{
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
""" + SEA_ATLAS + sea_amps(NUM_WAVES) + """
[branch] if (fade > 0.0)
{
""" + wave_terms("normal") + """
}
float ho = 0.0;
float om = 0.0;
[branch] if (OceanP.z > 0.0)
{
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
}
// W2 (the gulf-swell handoff): the FFT ocean only where the mask lets the open sea in (in the bay it cost 0.1 to
// 0.17 ms for nothing). Two cascades (texel i,j = the grid point at x = i * cell north, y = j * cell east), faded far out.
[branch] if (om > 0.001)
{
    float of = om * saturate(1.0 - distance(p.xy, cam.xy) / OceanP.w);
    float4 oa = OceanA.SampleLevel(OceanASampler, float2(p.y, p.x) / OceanP.x + 0.5 / 64.0, 0);
    float4 ob = OceanB.SampleLevel(OceanBSampler, float2(p.y, p.x) / OceanP.y + 0.5 / 64.0, 0);
    ho = (oa.r + ob.r) * of;
    sx += (oa.g + ob.g) * of;
    sy += (oa.b + ob.b) * of;
    h += ho;
}
// Cat's paws: local wind relative to 15 kn, from the same wind field the sails feel (CPU-filled map).
// W2: the two-level wind map (AWaterSurface: near 3.2 km round the boat, far 16 km; both wrap-around, sampled at the
// world position over their size). Each fades into the coarser one towards its edge, the far one into the sea's mean
// wind (WindP) beyond. R: the roughness the water shows (x 2.5 = local wind / 8 m/s); G, B: the local downwind direction;
// A: the slow wind (x 20 m/s), for slicks and windrows.
float4 wNear = Gust.SampleLevel(GustSampler, p.xy / GustRect.z, 0);
float4 wFar = WindFar.SampleLevel(WindFarSampler, p.xy / WindFarRect.z, 0);
float2 eN = abs(p.xy - GustRect.xy) / (0.5 * GustRect.z);
float2 eF = abs(p.xy - WindFarRect.xy) / (0.5 * WindFarRect.z);
float4 wMean = float4(WindP.z / 20.0, 0.5 + 0.5 * WindP.x, 0.5 + 0.5 * WindP.y, WindP.z / 20.0);
float4 wMap = lerp(lerp(wMean, wFar, 1.0 - smoothstep(0.75, 0.95, max(eF.x, eF.y))), wNear, 1.0 - smoothstep(0.72, 0.92, max(eN.x, eN.y)));
float rough = wMap.r * 2.5;
float2 ldir = normalize(wMap.gb * 2.0 - 1.0 + float2(1e-4, 0.0));
float slowMs = wMap.a * 20.0;
float2 guv = p.xy / GustRect.z;
float near = saturate(1.0 - dist / 1500.0);
// Wind ripples: short capillary-gravity waves along the wind, stronger where it blows harder; W2: along the local wind.
float2 d = ldir;
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
float cover = 0.2 * pow(capsLevel, 1.5) * WindP.w; // W0: the water body's share of the sea's caps (fresh water 0.4)
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
OceanShare = om;
// Debug view (DebugGust > 0): show the cat's-paw map as foam.
Foam = DebugGust > 1.5 ? frac(guv.x * 8.0) * step(0.5, frac(guv.y * 8.0)) : lerp(Foam, saturate(rough / 2.5), saturate(DebugGust));
// Sailors read puffs relative to the wind around them: compare local wind with the lake's mean wind (W0: not the wind at
// the boat, which turned the whole lake into a lull whenever she sat in a puff).
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
        + ["OceanA", "OceanB", "OceanMask", "OceanP", "OceanMaskRect", "Sea", "SeaRect", "SeaP"]
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
    sea = sea_params(mat, -1600, 2200)
    wpo = custom(mat, WPO_CODE, common, unreal.CustomMaterialOutputType.CMOT_FLOAT3, -600, -400)

    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    gust_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 500, parameter_name="GustMap", texture=white)
    wake_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 650, parameter_name="WakeMap", texture=white)
    gust_rect = vector(mat, "GustRect", (0, 0, 3200, 1), -1600, 800)
    wake_rect = vector(mat, "WakeRect", (0, 0, 64, 0), -1600, 900)
    wind = vector(mat, "WindParams", (1, 0, 5, 0), -1600, 1000)
    rain = scalar(mat, "Rain", 0.0, -1600, 1100)
    debug = scalar(mat, "DebugGust", 0.0, -1600, 1200)
    far_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 1950, parameter_name="WindFar", texture=white)
    far_rect = vector(mat, "WindFarRect", (0, 0, 16000, 0), -1600, 2050)
    shade = custom(mat, SHADE_CODE, common + ["Gust", "Wake", "GustRect", "WakeRect", "WindP", "Rain", "DebugGust", "WindFar", "WindFarRect"],
                   unreal.CustomMaterialOutputType.CMOT_FLOAT3, -600, 400,
                   extra_outputs=[("Foam", unreal.CustomMaterialOutputType.CMOT_FLOAT1), ("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
                                  ("Dark", unreal.CustomMaterialOutputType.CMOT_FLOAT1), ("OceanShare", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    connect(far_tex, "", shade, "WindFar")
    connect(far_rect, "RGBA", shade, "WindFarRect")

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
        connect_sea(sea, c)
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
    # W2 (the gulf-swell handoff): the open sea's blue-green where the swell mask lets the sea in, the body's own colour
    # elsewhere (it tinted the whole of Galveston Bay on Low).
    ocean_color = vector(mat, "OceanColor", (0.012, 0.05, 0.06, 1), -500, 600)
    body = node(mat, unreal.MaterialExpressionLinearInterpolate, -200, 600)
    connect(water_color, "", body, "A")
    connect(ocean_color, "", body, "B")
    connect(shade, "OceanShare", body, "Alpha")
    foam_color = node(mat, unreal.MaterialExpressionConstant3Vector, -300, 700, constant=unreal.LinearColor(0.85, 0.88, 0.9, 1))
    base = node(mat, unreal.MaterialExpressionLinearInterpolate, -100, 650)
    connect(body, "", base, "A")
    connect(foam_color, "", base, "B")
    connect(shade, "Foam", base, "Alpha")
    rough_mix = node(mat, unreal.MaterialExpressionLinearInterpolate, -100, 800)
    foam_rough = node(mat, unreal.MaterialExpressionConstant, -300, 850, r=0.7)
    connect(shade, "Rough", rough_mix, "A")
    connect(foam_rough, "", rough_mix, "B")
    connect(shade, "Foam", rough_mix, "Alpha")

    MEL.connect_material_property(with_curvature(mat, wpo, 200, 1300), "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
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


# ---------------------------------------------------------------- rain curtains (W5b)
RAIN_CURTAIN_CODE = """
// W5b: a storm's rain seen from afar: vertical cards facing the camera (ASailingEnvironment::UpdateRainCurtains), placed
// where the rain field (FStormRain, or a real day's radar) says it rains. Per instance: amount, foot, seed. Curtains are
// veils of falling rain from the cloud base to the water; feet are the spray and mist the downdraft throws up off the
// water ahead of them (the rain foot).
float alt = WP.z / 100.0;   // m above the water
// The rain slants a little across the card as it falls through the shear (the veils lean).
float u = UV.x + 0.12 * (1.0 - saturate(alt / max(Base, 1.0))) * (Seed - 0.5);
float edge = smoothstep(0.0, 0.3, u) * smoothstep(1.0, 0.7, u);
float x = u * 9.0 + Seed * 17.0;
float a;
if (Foot < 0.5)
{
    // Veils: soft streaks a few hundred metres apart, slowly changing, finer striations in them (what reads as falling
    // rain from a distance), the fall a faint ripple running down; a little denser toward the water.
    float veil = 0.55 + 0.45 * sin(x * 2.1 + sin(x * 0.7 + T * 0.05)) * sin(x * 0.37 + 1.3);
    float striae = 0.8 + 0.2 * sin(u * 170.0 + Seed * 40.0) * sin(u * 61.0 + 2.0);
    float fall = 0.85 + 0.15 * sin(alt * 0.02 + T * 3.0 + x);
    float top = 1.0 - smoothstep(Base * 0.7, Base, alt);
    float low = 1.0 + 0.3 * exp(-max(alt, 0.0) / 150.0);
    a = Amount * 0.6 * veil * striae * fall * top * low * edge;
}
else
{
    // The foot: densest on the water, billowing outward.
    float low = exp(-max(alt, 0.0) / 55.0);
    float billow = 0.7 + 0.3 * sin(u * 23.0 + T * 0.4 + Seed * 9.0) * sin(u * 7.0 - T * 0.3);
    a = Amount * 0.55 * low * billow * edge;
}
return saturate(a);
"""


def build_rain_curtain():
    """M_RainCurtain (W5b): lit translucent veils of rain and their foot, instanced, on the curved water."""
    mat = new_material("M_RainCurtain")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    inputs = {"UV": node(mat, unreal.MaterialExpressionTextureCoordinate, -900, 0),
              "WP": node(mat, unreal.MaterialExpressionWorldPosition, -900, 100),
              "T": node(mat, unreal.MaterialExpressionTime, -900, 200),
              "Base": scalar(mat, "RainBase", 750.0, -900, 300)}
    for k, (name, y) in enumerate((("Amount", 400), ("Foot", 500), ("Seed", 600))):
        inputs[name] = node(mat, unreal.MaterialExpressionPerInstanceCustomData, -900, y, data_index=k)
    c = custom(mat, RAIN_CURTAIN_CODE, list(inputs.keys()), unreal.CustomMaterialOutputType.CMOT_FLOAT1, -500, 200)
    for name, n in inputs.items():
        connect(n, "", c, name)
    color = vector(mat, "RainColor", (0.62, 0.64, 0.68, 1), -700, 0)
    # Storm sky fix: the curtain's share of the sun through the deck above it (per instance, 4th float); the sky light
    # under a storm deck is a fifth of the open sky's, so a curtain in full shade is about that dark.
    shade = node(mat, unreal.MaterialExpressionPerInstanceCustomData, -900, 700, data_index=3, const_default_value=1.0)
    lit = node(mat, unreal.MaterialExpressionLinearInterpolate, -500, 0, const_a=0.2, const_b=1.0)
    connect(shade, "", lit, "Alpha")
    tinted = node(mat, unreal.MaterialExpressionMultiply, -350, 0)
    connect(color, "", tinted, "A")
    connect(lit, "", tinted, "B")
    rough = node(mat, unreal.MaterialExpressionConstant, -500, 450, r=1.0)
    MEL.connect_material_property(tinted, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.connect_material_property(curvature(mat, -500, 650), "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_smoke():
    """M_Smoke (Graphics G8 Ultra showcase): an exhaust puff from APowerVesselActor::UpdateExhaust. Instanced spheres,
    lit translucent (volumetric, non-directional: cheap, and smoke has no surface to shade), shade and opacity per instance
    (custom data 0 and 1), the edge softened by the view angle so a puff reads as a blob of smoke, not a ball."""
    mat = new_material("M_Smoke")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_VOLUMETRIC_NON_DIRECTIONAL)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    shade = node(mat, unreal.MaterialExpressionPerInstanceCustomData, -900, 0, data_index=0, const_default_value=0.1)
    alpha = node(mat, unreal.MaterialExpressionPerInstanceCustomData, -900, 200, data_index=1, const_default_value=0.5)
    # Diesel soot is near black and brown-tinted; an outboard's haze a pale blue-grey (shade 0.6).
    col = node(mat, unreal.MaterialExpressionLinearInterpolate, -600, 0)
    connect(node(mat, unreal.MaterialExpressionConstant3Vector, -900, -150, constant=unreal.LinearColor(0.03, 0.028, 0.025, 1)), "", col, "A")
    connect(node(mat, unreal.MaterialExpressionConstant3Vector, -900, -80, constant=unreal.LinearColor(0.55, 0.58, 0.62, 1)), "", col, "B")
    connect(shade, "", col, "Alpha")
    fres = node(mat, unreal.MaterialExpressionFresnel, -900, 350, exponent=1.5, base_reflect_fraction=0.0)
    soft = node(mat, unreal.MaterialExpressionOneMinus, -650, 350)
    connect(fres, "", soft, "")
    op = node(mat, unreal.MaterialExpressionMultiply, -400, 250)
    connect(alpha, "", op, "A")
    connect(soft, "", op, "B")
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(node(mat, unreal.MaterialExpressionConstant, -400, 450, r=1.0), "", unreal.MaterialProperty.MP_ROUGHNESS)
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
// Graphics G2: finer mottling (gravel, tufts, bare patches) so a bank isn't flat paint up close.
float f = sin(p.x * 4.1 + sin(p.y * 3.3) * 1.7) * sin(p.y * 4.7 + sin(p.x * 2.9) * 1.9) * sin(p.x * 9.3 - p.y * 7.1);
float3 col = C * (0.88 + 0.12 * n + 0.05 * m) * (0.93 + 0.07 * f);
// The wet band: banks are dark and glossy from the water up the swash, about half a metre (ragged); just under the
// surface the bed takes the water's olive cast.
float h = (P.z - WaterZ) * 0.01;
float wet = (1.0 - smoothstep(0.05, 0.45 + 0.2 * n + 0.08 * f, h)) * CA;   // CA: open water within 14 m (Graphics G6)
float under = smoothstep(0.0, -0.35, h);
col = lerp(col, col * 0.55, wet);
col = lerp(col, col * float3(0.55, 0.6, 0.45), under);
Rough = lerp(0.92, 0.32, wet * (1.0 - under));
return col;
"""
    c = custom(mat, code, ["C", "CA", "P", "WaterZ"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -400, 100,
               extra_outputs=[("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    connect(vc, "", c, "C")
    connect(vc, "A", c, "CA")
    connect(pos, "", c, "P")
    wz = node(mat, unreal.MaterialExpressionCollectionParameter, -800, 350)
    wz.set_editor_property("collection", world_collection())
    wz.set_editor_property("parameter_name", "WaterZ")
    connect(wz, "", c, "WaterZ")
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(curvature(mat, -400, 450), "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


def build_lens_distortion():
    """M_LensDistortion: barrel distortion for the action-cam reference preset (a GoPro's wide lens). The image is
    rendered rectilinear at the camera's full field of view; this pulls the middle in so straight lines bow outward
    the way they do in action-cam footage. Round 11: normalised at the frame's corners, not its side edges, so no pixel
    samples outside the rendered frame (the clamp smeared the side edges into streaks); the preset renders wider
    (ReferenceCapture.cpp) so the middle of each side edge still sees 118 deg."""
    mat = new_material("M_LensDistortion")
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    strength = scalar(mat, "Strength", 0.35, -900, 0)
    code = """
float2 uv = GetViewportUV(Parameters);
float aspect = View.ViewSizeAndInvSize.x * View.ViewSizeAndInvSize.w;
float2 d = (uv - 0.5) * 2.0 * float2(1.0, 1.0 / aspect);
float rc = 1.0 + 1.0 / (aspect * aspect);
float s = (1.0 + K * dot(d, d)) / (1.0 + K * rc);
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
// The splash line wets the hull's sides, not the cockpit sole inside it (low cockpits sit near the outside water level).
wet *= 1.0 - up;
float2 cell = floor(LP.xy / 0.9);
float h = frac(sin(dot(cell, float2(12.9898, 78.233))) * 43758.5453);
float2 f = frac(LP.xy / 0.9) - 0.5;
float drop = h > 0.72 ? saturate(1.0 - length(f) * 4.0) : 0.0;
float deckWet = saturate(DeckWet) * up;
grad += (f.x * LX + f.y * LY) * drop * deckWet * 1.2;
float wetAll = saturate(max(wet, deckWet * 0.8));
// Graphics G3: the boat's own livery and wear (BoatLivery.h, from the catalogue): the hull colour and four wear channels,
// per boat (Wear, on the player's and the AI boats' materials) or per instance (the marina's neighbours: custom data 0-3
// wear, 4-6 hull colour; -1 = none).
float4 wear = CD0 >= 0.0 ? float4(CD0, CD1, CD2, CD3) : Wear;
float3 col = (IsHull > 0.5 && CD4 >= 0.0) ? float3(CD4, CD5, CD6) : C.rgb;
float zcm = LP.z;
float gel = (1.0 - Metal) * saturate(Coat) * (1.0 - saturate(NonSkid));
float rough = R, coat = Coat;
// E1 (docs/environment-1): the rest of the berthed boats' wear seed, per instance (custom data 12-15; -1 = none, as on
// the player's and the AI boats, which keep the look above). Sun 0-1 (a south-west-facing hull bleaches), Wet = metres
// of stain band above the waterline, Site 0 lake / 1 bay / 2 Gulf, Variant (the boat's cover set).
bool seeded = CD12 >= 0.0;
float sunF = seeded ? 0.6 + 0.8 * saturate(CD12) : 1.0;
float salt = seeded ? step(0.5, CD14) : 0.0;
// Variant: one gelcoat batch is never quite another's, plus or minus 3%.
col *= seeded ? 1.0 + gel * 0.03 * (frac(CD15 * 0.618 + 0.31) * 2.0 - 1.0) : 1.0;
// Oxidation: gelcoat chalks under the Texas sun, decks and tops first: paler, flatter, the clear coat gone.
float ox = saturate(wear.x * sunF) * gel * (0.55 + 0.45 * up);
float lum = dot(col, float3(0.3, 0.59, 0.11));
// Pale gelcoat goes toward chalk; dark paint (linear polyurethane, slower to chalk) only greys and loses depth.
float3 chalk = lerp(lerp(float3(lum, lum, lum), float3(0.82, 0.80, 0.74), 0.5) * 1.02, col * 1.25 + lum * 0.35 + 0.01, saturate(1.0 - lum * 2.5));
col = lerp(col, chalk, 0.4 * ox);
rough = lerp(rough, 0.72, ox);
coat *= 1.0 - 0.85 * ox;
// Worn, grimy non-skid.
col = lerp(col, col * 0.78 + 0.02, wear.x * saturate(NonSkid) * 0.7);
// Round 12 ("lack of texture on surfaces", "no wear and tear"): three octaves of value noise anchored to the boat (37 cm,
// 9 cm, 2.2 cm) for grime ground into decks and non-skid where feet and water go, and a faint mottle in every gelcoat.
float vn = 0.0, amp = 0.6, sc = 37.0;
for (int o = 0; o < 3; ++o)
{
    float2 q = (LP.xy + LP.zz * float2(0.6, -0.4)) / sc + o * 17.3;
    float2 qi = floor(q), qf = frac(q);
    qf = qf * qf * (3.0 - 2.0 * qf);
    float a00 = frac(sin(dot(qi, float2(12.99, 78.23))) * 43758.5), a10 = frac(sin(dot(qi + float2(1, 0), float2(12.99, 78.23))) * 43758.5);
    float a01 = frac(sin(dot(qi + float2(0, 1), float2(12.99, 78.23))) * 43758.5), a11 = frac(sin(dot(qi + float2(1, 1), float2(12.99, 78.23))) * 43758.5);
    vn += amp * lerp(lerp(a00, a10, qf.x), lerp(a01, a11, qf.x), qf.y);
    amp *= 0.5;
    sc /= 4.1;
}
vn /= 1.05;
float deckish = up * (1.0 - Metal) * (1.0 - IsHull) * (1.0 - Grain);
// How dirty: E1's seeded Age (years) and Care (0 neglected .. 1 tidy): per instance (custom data 10 and 11 on the marina's
// berthed boats, docs/environment-1) or per boat (the Age and Care parameters; Age -1 = unset), else the livery's
// oxidation channel.
float age = CD10 >= 0.0 ? CD10 : Age, care = CD10 >= 0.0 ? CD11 : Care;
float dirt = age >= 0.0 ? saturate(0.15 + age / 18.0) * (1.0 - 0.65 * saturate(care)) : 0.3 + 0.7 * wear.x;
float grime = saturate(vn * 1.8 - 0.6) * deckish * dirt * (0.45 + 0.55 * saturate(NonSkid));
col = lerp(col, col * 0.76 + float3(0.014, 0.011, 0.007), grime);
rough = lerp(rough, min(rough + 0.18, 0.9), grime);
coat *= 1.0 - 0.6 * grime;
col *= 1.0 + 0.05 * (vn - 0.5) * (1.0 - Metal) * (1.0 - Grain);
// Wood (Grain 1): straight grain along the part's length with slow wander, a varnished tiller's or a weathered toe rail's.
float gw = LP.y * 0.9 + LP.z * 1.3 + 2.5 * sin(LP.x * 0.021) + 1.2 * sin(LP.x * 0.083 + LP.y);
float ring = 0.5 + 0.5 * sin(gw * 6.0 + 4.0 * vn);
float fleck = saturate(vn * 3.0 - 1.9);
col = lerp(col, col * lerp(0.72, 1.12, ring) * (1.0 - 0.25 * fleck), Grain);
rough = lerp(rough, rough * lerp(0.85, 1.25, ring), Grain);
// The waterline "mustache": a brown band from the waterline up a few centimetres, ragged, strongest forward.
float scumBand = (1.0 - smoothstep(2.0, 6.0 + 4.0 * streak, zcm)) * smoothstep(-4.0, 0.0, zcm);
float scum = wear.y * IsHull * scumBand * (0.6 + 0.4 * saturate(LP.x / 300.0 + 0.5));
col = lerp(col, float3(0.24, 0.15, 0.07), 0.6 * scum);
// Dock rash and fender marks: soft, sparse smudges in the fender band of the topsides (an ellipse per cell, faded
// edges: hard-edged cells read as camouflage on a big hull).
float2 cs = float2(LP.x / 45.0, zcm / 16.0);
float2 cellS = floor(cs);
float patchS = frac(sin(dot(cellS, float2(41.3, 17.7))) * 4375.5);
float2 fs = frac(cs) - 0.5;
float smudge = 1.0 - smoothstep(0.12, 0.45, length(fs * float2(1.0, 1.8)));
float scuff = wear.z * IsHull * step(abs(n.z), 0.6) * smoothstep(25.0, 40.0, zcm) * (1.0 - smoothstep(70.0, 95.0, zcm)) * step(0.82, patchS) * smudge;
col = lerp(col, col * 0.78 + float3(0.01, 0.01, 0.008), scuff);
// Rust streaks from fittings: thin, tapering runs down vertical faces, few and far between.
float laneX = LP.x / 9.0 + LP.y / 23.0;
float lane = frac(sin(floor(laneX) * 91.7) * 437.5);
float thin = 1.0 - smoothstep(0.02, 0.10, abs(frac(laneX) - 0.5));
float runLen = 20.0 + 60.0 * frac(lane * 7.3);
float top = 60.0 + 40.0 * frac(lane * 3.1);
float rust = wear.w * gel * step(abs(n.z), 0.7) * step(0.93 - 0.05 * salt, lane) * thin * saturate((zcm - (top - runLen)) / runLen) * step(zcm, top);
col = lerp(col, float3(0.30, 0.13, 0.05), 0.5 * rust * (1.0 + 0.6 * salt));
// E1: the stain band a berthed hull carries above her waterline (Wet metres), heavier on an old, neglected boat: green-brown
// algae on the lake, a tan band on salt water with a thin crust of dried salt along its top edge.
float wetCm = seeded ? max(CD13, 0.0) * 100.0 : 0.0;
float bandTop = wetCm * (0.75 + 0.25 * streak);
float stainBand = IsHull * step(abs(n.z), 0.8) * smoothstep(-2.0, 1.0, zcm) * (1.0 - smoothstep(bandTop - 3.0, bandTop, zcm)) * step(0.5, wetCm);
float stainK = stainBand * (age >= 0.0 ? saturate(0.2 + age / 20.0) * (1.0 - 0.7 * saturate(care)) : 0.4) * (0.75 + 0.25 * vn);
col = lerp(col, lerp(float3(0.16, 0.17, 0.08), float3(0.42, 0.36, 0.24), salt), 0.65 * stainK);
float crust = salt * IsHull * stainK * exp(-pow((zcm - bandTop + 1.5) / 1.2, 2.0)) * step(0.5, frac(sin(floor(LP.x / 1.5) * 12.7) * 437.5) + 0.3);
col = lerp(col, float3(0.74, 0.73, 0.69), crust);
rough = lerp(rough, 0.8, saturate(stainK + crust));
coat *= 1.0 - 0.7 * saturate(stainK + crust);
// Graphics G8 (round 8: "the boat is not detailed enough/looks flat"): what a real hull carries that a clean one doesn't.
// Black streaks: grey runs washed down the topsides from the toe rail and the stanchion bases by rain, many and faint,
// each its own width and length, strongest just under the sheer and fading toward the waterline.
float sx = LP.x / 6.0 + LP.y / 37.0;
float sh = frac(sin(floor(sx) * 57.31) * 4375.5), sh2 = frac(sin(floor(sx) * 13.7 + 3.0) * 4375.5);
float sw = exp(-pow((frac(sx) - 0.5) * (5.0 + 10.0 * sh2), 2.0));
float sLen = 25.0 + 70.0 * sh;
float sTop = 55.0 + 70.0 * sh2;
float blk = IsHull * step(abs(n.z), 0.75) * step(0.45, sh) * sw * saturate((zcm - (sTop - sLen)) / sLen) * smoothstep(sTop + 15.0, sTop - 5.0, zcm);
col = lerp(col, col * float3(0.62, 0.61, 0.58), saturate(blk * (0.25 + 0.9 * wear.y)));
// Large, faint tone differences across a hull or deck (gelcoat batches, sun on one side, old repairs): plus or minus 3%.
float2 tp = LP.xz / 160.0;
float2 ti = floor(tp), tf = smoothstep(0.0, 1.0, frac(tp));
float t00 = frac(sin(dot(ti, float2(12.99, 78.23))) * 43758.5), t10 = frac(sin(dot(ti + float2(1, 0), float2(12.99, 78.23))) * 43758.5);
float t01 = frac(sin(dot(ti + float2(0, 1), float2(12.99, 78.23))) * 43758.5), t11 = frac(sin(dot(ti + float2(1, 1), float2(12.99, 78.23))) * 43758.5);
float tone = lerp(lerp(t00, t10, tf.x), lerp(t01, t11, tf.x), tf.y);
col *= 1.0 + gel * 0.06 * (tone - 0.5);
// Fairness: a laid-up hull is never quite flat. Long, shallow undulations (print-through over the bulkheads and the
// core) bend the clear coat's reflections of the sky and the shore the way they wobble along a real hull.
float fair = sin(LP.x * 0.045 + sin(LP.z * 0.031 + LP.x * 0.007) * 2.2) + 0.5 * sin(LP.x * 0.113 + LP.z * 0.05);
grad += LX * (0.018 * gel * (1.0 - up) * fair);
float3 base = col * lerp(1.0, 1.0 - 0.55 * Porosity, wetAll);
AlbedoOut = base * (1.0 - Metal);
F0Out = lerp(float3(0.04, 0.04, 0.04), base, Metal);
RoughOut = lerp(rough, lerp(0.06, rough, 0.25 + 0.4 * saturate(NonSkid)), wetAll * (1.0 - Metal)); // wet non-skid stays satin
// A water film is a clear coat of its own: the second (gloss) lobe grows where the surface is wet.
CoatOut = saturate(coat * 0.6 + wetAll * 0.5 * (1.0 - Metal));
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
    mat.set_editor_property("used_with_instanced_static_meshes", True)  # the boats berthed in the marina (Visual V6)
    mat.set_editor_property("used_with_nanite", True)  # the Nanite boat models (the J/22 hero, the fleet, the berthed boats)
    # Two-sided (Visual V7): the generated cockpits, cabins, dodgers and nets are open shells whose faces aren't all
    # wound outward; culled, a cockpit sole showed the water under the boat. The hull's outside never shows its back.
    mat.set_editor_property("two_sided", True)
    mpc = collection()
    color = vector(mat, "Color", (0.85, 0.85, 0.82, 1), -1400, -200)
    rough = scalar(mat, "Roughness", 0.35, -1400, -50)
    metal = scalar(mat, "Metallic", 0.0, -1400, 50)
    coat = scalar(mat, "ClearCoat", 1.0, -1400, 150)
    coat_r = scalar(mat, "ClearCoatRoughness", 0.05, -1400, 250)
    nonskid = scalar(mat, "NonSkid", 0.0, -1400, 350)
    porosity = scalar(mat, "Porosity", 0.15, -1400, 450)
    grain = scalar(mat, "Grain", 0.0, -1600, 450)
    # E1 (docs/environment-1): the seeded age and care, by name; bound to per-instance custom data when E1 lands.
    age = scalar(mat, "Age", -1.0, -1600, 550)
    care = scalar(mat, "Care", 0.5, -1600, 650)
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
    c = custom(mat, BOAT_CODE, ["C", "R", "Metal", "Coat", "NonSkid", "Porosity", "Grain", "Age", "Care", "LP", "WP", "N", "LX", "LY", "WaterZ", "WetBand", "DeckWet",
                                "Wear", "IsHull"] + [f"CD{k}" for k in list(range(7)) + list(range(10, 16))],
               F3, -900, 200, extra_outputs=[("AlbedoOut", F3), ("F0Out", F3), ("RoughOut", F1), ("CoatOut", F1)])
    # Graphics G3: per-boat livery and wear (BoatLivery.h).
    connect(vector(mat, "Wear", (0, 0, 0, 0), -1400, 1450), "RGBA", c, "Wear")
    connect(scalar(mat, "IsHull", 0.0, -1400, 1550), "", c, "IsHull")
    for k in list(range(7)) + list(range(10, 16)):   # E1's seed: 10 age, 11 care, 12 sun, 13 wet, 14 site, 15 variant (FWearSeed, docs/environment-1)
        cd = node(mat, unreal.MaterialExpressionPerInstanceCustomData, -1400, 1650 + 60 * k)
        cd.set_editor_property("data_index", k)
        cd.set_editor_property("const_default_value", -1.0)
        connect(cd, "", c, f"CD{k}")
    for src, pin in ((color, "C"), (rough, "R"), (metal, "Metal"), (coat, "Coat"), (nonskid, "NonSkid"), (porosity, "Porosity"), (grain, "Grain"), (age, "Age"), (care, "Care"), (lp, "LP"),
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
    # Graphics G6: the club J/22s' non-skid is beige with grime worked into it (Bean's lesson photos), not white.
    "NonSkid": ("M_BoatSurface", (0.56, 0.52, 0.43), 0.66, 0.0, 0.0, 1.0, 0.35),  # the raised pattern breaks up any clear-coat gloss: a mirror lobe read as water in shaded cockpits
    "Bootstripe": ("M_BoatSurface", (0.010, 0.018, 0.080), 0.25, 0.0, 1.0, 0.0, 0.05),  # navy gelcoat stripes
    "CoveStripe": ("M_BoatSurface", (0.010, 0.018, 0.080), 0.25, 0.0, 1.0, 0.0, 0.05),
    "Antifouling": ("M_BoatSurface", (0.015, 0.022, 0.050), 0.80, 0.0, 0.0, 0.0, 0.60),  # ablative bottom paint
    "Keel": ("M_BoatSurface", (0.015, 0.022, 0.050), 0.75, 0.0, 0.0, 0.0, 0.60),
    "CabinWindow": ("M_BoatSurface", (0.006, 0.008, 0.010), 0.04, 0.0, 1.0, 0.0, 0.0),  # smoked acrylic
    "Stainless": ("M_BoatSurface", (0.62, 0.62, 0.63), 0.30, 1.0, 0.0, 0.0, 0.0),        # round 12: weathered 316, not chrome
    "Aluminium": ("M_BoatSurface", (0.78, 0.79, 0.81), 0.32, 1.0, 0.0, 0.0, 0.0),        # clear anodized spars
    "BlackPlastic": ("M_BoatSurface", (0.018, 0.018, 0.020), 0.45, 0.0, 0.0, 0.0, 0.05),
    "Wood": ("M_BoatSurface", (0.30, 0.17, 0.07), 0.30, 0.0, 1.0, 0.0, 0.15),           # varnished ash tiller
    "Teak": ("M_BoatSurface", (0.22, 0.19, 0.15), 0.85, 0.0, 0.0, 0.0, 0.5),           # weathered grey teak toe rails (G6)
    "Graphics": ("M_BoatSurface", (0.45, 0.015, 0.02), 0.28, 0.0, 1.0, 0.0, 0.05),
    "Rubrail": ("M_BoatSurface", (0.03, 0.03, 0.03), 0.5, 0.0, 0.0, 0.0, 0.1),
    # The crew (Visual V3): foul-weather jacket (recoloured per sailor), PFD, trousers, deck boots, skin, cap, glasses.
    "CrewJacket": ("M_BoatSurface", (0.45, 0.03, 0.03), 0.55, 0.0, 0.2, 0.0, 0.20),
    "CrewPFD": ("M_BoatSurface", (0.02, 0.03, 0.10), 0.60, 0.0, 0.0, 0.0, 0.30),
    "CrewTrousers": ("M_BoatSurface", (0.03, 0.03, 0.035), 0.70, 0.0, 0.0, 0.0, 0.50),
    "CrewBoots": ("M_BoatSurface", (0.55, 0.55, 0.57), 0.50, 0.0, 0.0, 0.0, 0.10),
    "CrewSkin": ("M_BoatSurface", (0.42, 0.28, 0.21), 0.55, 0.0, 0.0, 0.0, 0.10),
    "CrewCap": ("M_BoatSurface", (0.72, 0.72, 0.72), 0.80, 0.0, 0.0, 0.0, 0.40),
    # Graphics G3: the life jacket's webbing and buckles, its reflective patches (glass-bead tape: grey, a broad bright
    # lobe), the cap's brim underside and sweatband.
    "CrewStraps": ("M_BoatSurface", (0.26, 0.27, 0.28), 0.75, 0.0, 0.0, 0.0, 0.45),     # Graphics G6: grey webbing (the club vests)
    "CrewPiping": ("M_BoatSurface", (0.05, 0.28, 0.72), 0.6, 0.0, 0.0, 0.0, 0.3),        # lighter blue nylon piping
    "CrewBuckle": ("M_BoatSurface", (0.012, 0.012, 0.013), 0.38, 0.0, 0.3, 0.0, 0.02),
    "CrewReflective": ("M_BoatSurface", (0.55, 0.56, 0.58), 0.30, 0.0, 0.6, 0.0, 0.05),
    "CrewCapUnder": ("M_BoatSurface", (0.07, 0.09, 0.07), 0.85, 0.0, 0.0, 0.0, 0.40),
    # The polo (cotton pique, recoloured per sailor), its ribbed collar and cuffs, its buttons.
    "CrewPolo": ("M_BoatSurface", (0.05, 0.10, 0.30), 0.88, 0.0, 0.0, 0.0, 0.55),
    "CrewPoloRib": ("M_BoatSurface", (0.05, 0.10, 0.30), 0.80, 0.0, 0.0, 0.0, 0.55),
    "CrewButton": ("M_BoatSurface", (0.75, 0.74, 0.70), 0.30, 0.0, 0.5, 0.0, 0.02),
    "CrewSole": ("M_BoatSurface", (0.80, 0.80, 0.77), 0.70, 0.0, 0.0, 0.0, 0.20),      # white non-marking rubber
    "CrewLace": ("M_BoatSurface", (0.22, 0.13, 0.06), 0.65, 0.0, 0.0, 0.0, 0.40),      # rawhide lace
    "CrewGlasses": ("M_BoatSurface", (0.01, 0.01, 0.012), 0.05, 0.0, 1.0, 0.0, 0.0),
    "CrewHair": ("M_BoatSurface", (0.05, 0.04, 0.03), 0.60, 0.0, 0.0, 0.0, 0.30),
    "SailCover": ("M_BoatSurface", (0.02, 0.05, 0.14), 0.8, 0.0, 0.0, 0.0, 0.6),      # navy acrylic canvas: sail covers, sun strips (V7)
    "Rope": ("M_BoatSurface", (0.62, 0.64, 0.68), 0.75, 0.0, 0.0, 0.0, 0.50),         # braided polyester sheets
    # Graphics G6: the marina's variety (build_berthed.py variants): cover canvases, a poly tarp, a flaked Dacron main,
    # fender covers, a cooler lid.
    "SailCoverRed": ("M_BoatSurface", (0.13, 0.016, 0.022), 0.8, 0.0, 0.0, 0.0, 0.6),   # burgundy acrylic canvas
    "SailCoverGreen": ("M_BoatSurface", (0.014, 0.06, 0.03), 0.8, 0.0, 0.0, 0.0, 0.6),  # forest green
    "SailCoverTan": ("M_BoatSurface", (0.30, 0.25, 0.17), 0.85, 0.0, 0.0, 0.0, 0.6),    # sun-faded tan
    "Tarp": ("M_BoatSurface", (0.07, 0.085, 0.10), 0.8, 0.0, 0.0, 0.0, 0.5),           # grey canvas cockpit cover
    "Dacron": ("M_BoatSurface", (0.68, 0.66, 0.60), 0.55, 0.0, 0.0, 0.0, 0.3),          # off-white sailcloth
    "FenderBlue": ("M_BoatSurface", (0.02, 0.04, 0.12), 0.95, 0.0, 0.0, 0.0, 0.6),      # navy fleece fender covers
    "CoolerLid": ("M_BoatSurface", (0.04, 0.14, 0.42), 0.45, 0.0, 0.0, 0.0, 0.05),
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
        for pname, value in (("Roughness", rough), ("Metallic", metal), ("ClearCoat", coat), ("NonSkid", nonskid), ("Porosity", porosity),
                             ("IsHull", 1.0 if slot == "Topsides" else 0.0), ("Grain", 1.0 if slot in ("Wood", "Teak") else 0.0)):
            MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)


# ---------------------------------------------------------------- sails (Visual V3)
SAIL_CODE = r"""
// Visual V3 sail cloth. UV0: metres (x along the chord from the luff, y up from the foot); UV1: normalized planform;
// UV2.x: metres from the leech. Crosscut seams every 0.9 m, batten pockets on the main's leech, the class insignia and
// sail number from the marks atlas (top half insignia, bottom half number).
// Visual V7: per-class layouts (Layout 0 crosscut, 1 the Sunfish's striped sail, 2 the Hobie's coloured panels, 3 tri-radial
// panels for the bigger multihulls), BattenCount pockets (FullBattens: luff to leech).
float seamDist = abs(frac(UV0.y / 0.9 + 0.5) - 0.5) * 0.9;
if (Layout > 2.5)
{
    // Tri-radial: seams fan out from the clew (UV1 (1, 0)) and the head, crossing at the sail's middle.
    float2 fromClew = float2(1.0 - UV1.x, UV1.y);
    float ang = atan2(fromClew.y, fromClew.x + 1e-3);
    float fan = abs(frac(ang / 0.16 + 0.5) - 0.5) * 0.16 * length(fromClew) * Height;
    seamDist = lerp(fan, seamDist, step(0.55, UV1.y));
}
float seam = 1.0 - smoothstep(0.006, 0.010, seamDist);
float batten = 0.0;
int nb = (int)BattenCount;
for (int i = 1; i <= 8; i++)
{
    if (i > nb) break;
    float vb = float(i) / (BattenCount + 1.0);
    float len = FullBattens > 0.5 ? 50.0 : 0.45 + 0.25 * (i == 2 || i == 3);
    batten = max(batten, (1.0 - smoothstep(0.018, 0.026, abs(UV1.y - vb) * Height)) * (1.0 - smoothstep(len - 0.02, len, UV2.x)));
}
batten *= Battens;
float mark = 0.0;
float through = 0.0;
float3 ink = float3(0.0, 0.0, 0.0);
if (Marks > 0.5)
{
    // Graphics G3: the number is SailDigits digits of SailNum, each from the atlas's digit strip (bottom half: ten cells).
    // Both sides carry the insignia and the number, each reading right from its own side (before, the starboard side
    // read mirrored): the starboard set is looked up mirrored along the chord, the port set's number a row below it (the
    // class rule, so the two don't show through each other; the insignia are back to back). Face is +1 on the starboard
    // face. Set 0 is this face's (its ink), set 1 the other side's (only its shadow against the light).
    float nd = max(SailDigits, 1.0);
    float bw = min(0.58, 0.145 * nd);
    for (int s = 0; s < 2; s++)
    {
        bool stbd = (s == 0) == (Face > 0.0);
        float a = 0.0;
        float3 c = float3(0.0, 0.0, 0.0);
        float2 r0 = (UV1 - float2(0.30, 0.79)) / float2(0.46, 0.09);
        float2 r1 = (UV1 - float2(0.53 - 0.5 * bw, stbd ? 0.62 : 0.48)) / float2(bw, 0.12);
        if (Marks < 1.5 && all(r0 >= 0.0) && all(r0 <= 1.0))
        {
            float4 t = Tex.SampleLevel(TexSampler, float2(stbd ? 1.0 - r0.x : r0.x, 0.5 - r0.y * 0.5), 0); a = t.a; c = t.rgb;
        }
        if (all(r1 >= 0.0) && all(r1 <= 0.999))
        {
            float x = stbd ? 0.999 - r1.x : r1.x;
            float i = floor(x * nd);
            float d = fmod(floor(SailNum / pow(10.0, nd - 1.0 - i) + 0.01), 10.0);
            float4 t = Tex.SampleLevel(TexSampler, float2((d + frac(x * nd)) / 10.0, 1.0 - r1.y * 0.5), 0); a = t.a; c = t.rgb;
        }
        if (s == 0) { mark = a; ink = c; }
        else through = a;
    }
}
// A faint weave and the panels' slight tone differences.
float weave = 0.5 + 0.5 * sin(UV0.x * 1400.0) * sin(UV0.y * 1400.0);
float panel = frac(sin(floor(UV0.y / 0.9) * 12.9898) * 43758.5453);
float3 base = C.rgb;
if (Layout > 0.5 && Layout < 1.5)
{
    // The Sunfish's sail: bands of colour, from the foot up.
    int band = (int)floor(UV0.y / 0.42);
    float3 pal[6] = { float3(0.60, 0.04, 0.03), float3(0.75, 0.30, 0.02), float3(0.80, 0.62, 0.05), float3(0.05, 0.35, 0.10), float3(0.02, 0.12, 0.45), float3(0.80, 0.80, 0.78) };
    base = pal[band % 6];
}
else if (Layout > 1.5 && Layout < 2.5)
{
    // The Hobie 16's main and jib: wide panels of colour between white ones.
    int band = (int)floor(UV0.y / 0.9);
    float3 pal[4] = { float3(0.02, 0.10, 0.45), float3(0.80, 0.80, 0.78), float3(0.70, 0.08, 0.04), float3(0.85, 0.65, 0.05) };
    base = pal[band % 4];
}
float3 cloth = base * (0.97 + 0.03 * weave) * (0.985 + 0.03 * panel);
// Graphics G6: a club boat's Dacron is off-white and shows its age (round 7: "too white"). The leech and the head take the
// most sun and yellow first, each panel a little differently; the foot is greyed from the deck and from being flaked
// there; a few mildew specks low down. Only on the white cloth (the Sunfish and Hobie colours keep theirs).
float2 gp = UV0 / 0.6;
float2 gi = floor(gp);
float2 gf = frac(gp);
gf = gf * gf * (3.0 - 2.0 * gf);
float n00 = frac(sin(dot(gi, float2(127.1, 311.7))) * 43758.5);
float n10 = frac(sin(dot(gi + float2(1.0, 0.0), float2(127.1, 311.7))) * 43758.5);
float n01 = frac(sin(dot(gi + float2(0.0, 1.0), float2(127.1, 311.7))) * 43758.5);
float n11 = frac(sin(dot(gi + float2(1.0, 1.0), float2(127.1, 311.7))) * 43758.5);
float mott = lerp(lerp(n00, n10, gf.x), lerp(n01, n11, gf.x), gf.y);
float whiteish = saturate((min(base.r, min(base.g, base.b)) - 0.4) * 4.0);
float age = saturate(0.3 + 0.45 * exp(-UV2.x / 0.6) + 0.25 * UV1.y + 0.35 * (panel - 0.5) + 0.15 * (mott - 0.5));
cloth *= lerp(float3(1.0, 1.0, 1.0), float3(1.0, 0.95, 0.83), age * 0.6 * whiteish);
float foot = (1.0 - smoothstep(0.05, 0.55 + 0.3 * mott, UV0.y)) * (0.6 + 0.4 * mott);
cloth *= lerp(float3(1.0, 1.0, 1.0), float3(0.80, 0.78, 0.72), foot * 0.5 * whiteish);
float2 sp = UV0 / 0.045;
float sr = frac(sin(dot(floor(sp), float2(41.3, 289.1))) * 15731.7);
float speck = step(0.993, sr) * (1.0 - smoothstep(0.0, 2.5, UV0.y)) * step(length(frac(sp) - 0.5), 0.3);
cloth *= 1.0 - 0.35 * speck * whiteish;
float3 col = lerp(cloth * (1.0 - 0.12 * seam), base * 0.93, batten);
col = lerp(col, ink, mark);
// Against the sun the cloth glows; seams (double layer), batten pockets and ink are darker from behind.
Transmit = base * 0.7 * (1.0 - 0.55 * seam) * (1.0 - 0.75 * batten) * (1.0 - 0.9 * max(mark, through));
// Graphics G6: the creases a used sail carries (a height field in metres, its slopes into the normal): fold lines from
// flaking, roughly parallel to the foot every 0.75 m (each its own strength along the chord); stress wrinkles fanning
// from the clew; the seams' pucker. The vinyl of the number and insignia is glossier than the Dacron.
float dhdu = 0.0, dhdv = 0.0;
float yk = UV0.y / 0.75;
float k = floor(yk + 0.5);
float jit = frac(sin(k * 91.7) * 4375.5) - 0.5;
float dy = (yk - k - 0.2 * jit) * 0.75;
float strength = 0.0018 * (0.35 + 0.65 * (0.5 + 0.5 * sin(UV0.x * 1.7 + k * 2.3))) * (frac(k * 0.5) > 0.25 ? 1.0 : -0.7) * (1.0 - batten);
float w = 0.014;
dhdv += strength * (-2.0 * dy / (w * w)) * exp(-dy * dy / (w * w));
float ca = UV2.x, cb = UV0.y;
float cr2 = max(ca * ca + cb * cb, 1e-3);
float cth = atan2(cb, max(ca, 1e-3));
float camp = 0.0012 * exp(-sqrt(cr2) / 0.7) * step(Layout, 0.5);
float dth = camp * 34.0 * cos(34.0 * cth);
dhdu += dth * (cb / cr2);      // UV2.x runs from the leech toward the luff: d/du = -d/da
dhdv += dth * (ca / cr2);
float pucker = (1.0 - smoothstep(0.01, 0.05, seamDist)) * 0.0005;
dhdu += pucker * 55.0 * cos(UV0.x * 55.0);
NormalTS = normalize(float3(-dhdu, -dhdv, 1.0));
// The resin cracks along a fold: the line reads a shade darker and rougher than the sheen around it.
float fold = exp(-dy * dy / (w * w)) * abs(strength) / 0.0018;
col *= 1.0 - 0.05 * fold * whiteish * (1.0 - mark);
Rough = lerp(lerp(R, 0.75, 0.5 * fold), 0.28, mark);
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
    color = vector(mat, "Color", (0.70, 0.68, 0.63, 1), -1200, -100)
    battens = scalar(mat, "Battens", 0.0, -1200, 50)
    marks = scalar(mat, "Marks", 0.0, -1200, 150)
    sailnum = scalar(mat, "SailNum", 1288.0, -1400, 350)
    saildig = scalar(mat, "SailDigits", 4.0, -1400, 450)
    height = scalar(mat, "Height", 7.6, -1200, 250)
    layout = scalar(mat, "Layout", 0.0, -1400, 50)
    bcount = scalar(mat, "BattenCount", 4.0, -1400, 150)
    full = scalar(mat, "FullBattens", 0.0, -1400, 250)
    rough = scalar(mat, "Roughness", 0.62, -400, 300)
    tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1200, 350, parameter_name="SailMarks", texture=sail_marks_texture())
    uv = [node(mat, unreal.MaterialExpressionTextureCoordinate, -1200, 500 + 100 * i, coordinate_index=i) for i in range(3)]
    # The face (+1 starboard): the cloth grid's winding (FSailCloth::Triangles) puts its front face to starboard on every class.
    face = node(mat, unreal.MaterialExpressionTwoSidedSign, -1400, 600)
    c = custom(mat, SAIL_CODE, ["C", "Battens", "Marks", "Height", "Tex", "UV0", "UV1", "UV2", "Layout", "BattenCount", "FullBattens", "SailNum", "SailDigits", "Face", "R"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, 100,
               extra_outputs=[("Transmit", unreal.CustomMaterialOutputType.CMOT_FLOAT3), ("NormalTS", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                              ("Rough", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    for src, pin in ((color, "C"), (battens, "Battens"), (marks, "Marks"), (height, "Height"), (tex, "Tex"), (uv[0], "UV0"), (uv[1], "UV1"), (uv[2], "UV2"),
                     (layout, "Layout"), (bcount, "BattenCount"), (full, "FullBattens"), (sailnum, "SailNum"), (saildig, "SailDigits"), (face, "Face")):
        connect(src, "RGBA" if src is color else "", c, pin)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Transmit", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    connect(rough, "", c, "R")
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(c, "NormalTS", unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    # Instances: the J/22 main (battens, insignia, number), the jib, the spinnaker (nylon, red).
    # Graphics G6: off-white Dacron (0.82 read as paper white in the blind test), a resin sheen (roughness 0.5).
    for name, col, bat, mk, h in (("MI_Sail_Main", (0.70, 0.68, 0.63), 1.0, 1.0, 7.6), ("MI_Sail_Jib", (0.71, 0.69, 0.64), 0.0, 0.0, 7.5),
                                  ("MI_Sail_Spinnaker", (0.55, 0.03, 0.03), 0.0, 0.0, 7.0)):
        path = f"{FOLDER}/{name}"
        mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
            ASSETS.create_asset(name, FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, mat)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(col[0], col[1], col[2], 1.0))
        for pname, value in (("Battens", bat), ("Marks", mk), ("Height", h), ("Roughness", 0.5 if name != "MI_Sail_Spinnaker" else 0.45)):
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
        amp = f"A{i // 4}s.{'xyzw'[i % 4]}"
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
""" + SEA_ATLAS + sea_amps(NUM_LONG) + long_wave_terms() + """
h *= fade; d *= fade;
lsx *= fade; lsy *= fade;
ljxx = lerp(1.0, ljxx, fade); ljyy = lerp(1.0, ljyy, fade); ljxy *= fade;
// The short waves (FFT of the same spectrum, FWaveDetail), near the camera.
float df = saturate(1.0 - dist / DetailP.z);
[branch] if (df > 0.0)
{
    float4 da = DetailA.SampleLevel(DetailASampler, float2(p.y, p.x) / DetailP.x + 0.5 / 128.0, 0);
    h += da.r * df * SShort;
    d += da.gb * df * SShort;
}
// The water the boats push around (FWakeGrid).
float2 wg = (p.xy - WakeGridRect.xy) / WakeGridRect.z;
[branch] if (all(wg > 0.0) && all(wg < 1.0)) h += WakeGrid.SampleLevel(WakeGridSampler, float2(wg.y, wg.x), 0).r;
float ho = 0.0;
float om = 0.0;
[branch] if (OceanP.z > 0.0)
{
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
}
// W2 (the gulf-swell handoff): the FFT ocean only where the mask lets the open sea in.
[branch] if (om > 0.001)
{
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
// Inside the player's hull (Visual V7): the water drops 2 m below its deck so it never shows in the cockpit. The plan
// view is the physics' FHullShape (ellipse forward of the widest station, taper aft), 80% of the beam so the dip stays
// behind the topsides when she heels.
float2 hr = p.xy - HullClipA.xy;
float hbx = hr.x * HullClipA.z + hr.y * HullClipA.w;
float hby = -hr.x * HullClipA.w + hr.y * HullClipA.z - HullClipC.z;
float hfu = (hbx - HullClipB.z) / max(HullClipB.x - HullClipB.z, 0.1);
float hau = (HullClipB.z - hbx) / max(HullClipC.x, 0.1);
float hhb = hbx > HullClipB.z ? HullClipB.w * sqrt(saturate(1.0 - hfu * hfu)) : HullClipB.w - HullClipC.y * hau * hau;
float hin = saturate((0.8 * hhb - abs(hby)) / 0.1) * step(HullClipB.y + 0.2, hbx) * step(hbx, HullClipB.x - 0.3) * HullClipC.w;
return float3(d.x * 100.0, d.y * 100.0, (h + ho - 2.0 * hin) * 100.0);
"""

V4_SHADE = """
FoamTone = 1.0;
float3 p = P * 0.01;
float3 cam = Cam * 0.01;
float dist = distance(p.xy, cam.xy);
float fade = saturate(1.0 - dist / Fade);
// The long waves, from the vertices (V4_WPO).
float sx = LongN.x, sy = LongN.y;
float J = LongN.z;
// Cat's paws: the wind's surface roughness map (local wind relative to 15 kn), against the sea's mean wind (WindP.z, what
// the drawn waves were grown for). In a lee (the shelter map, a puff's edge) the short waves and ripples the local wind
// raises are smaller.
// W2: the two-level wind map (AWaterSurface: near 3.2 km round the boat, far 16 km; both wrap-around, sampled at the
// world position over their size). Each fades into the coarser one towards its edge, the far one into the sea's mean
// wind (WindP) beyond. R: the roughness the water shows (x 2.5 = local wind / 8 m/s); G, B: the local downwind direction;
// A: the slow wind (x 20 m/s), for slicks and windrows.
float4 wNear = Gust.SampleLevel(GustSampler, p.xy / GustRect.z, 0);
float4 wFar = WindFar.SampleLevel(WindFarSampler, p.xy / WindFarRect.z, 0);
float2 eN = abs(p.xy - GustRect.xy) / (0.5 * GustRect.z);
float2 eF = abs(p.xy - WindFarRect.xy) / (0.5 * WindFarRect.z);
float4 wMean = float4(WindP.z / 20.0, 0.5 + 0.5 * WindP.x, 0.5 + 0.5 * WindP.y, WindP.z / 20.0);
float4 wFarMean = lerp(wMean, wFar, 1.0 - smoothstep(0.75, 0.95, max(eF.x, eF.y)));
// (The roughness and direction hand off over the near map's outer half: over its outer 20% the two maps' different
// readings of the wind drew the map's square edge 1.6 km out as a line in the glint, seen from 300 m.)
float4 wMap = lerp(wFarMean, wNear, 1.0 - smoothstep(0.5, 0.95, max(eN.x, eN.y)));
float rough = wMap.r * 2.5;
float2 ldir = normalize(wMap.gb * 2.0 - 1.0 + float2(1e-4, 0.0));
// W2 follow-up (Mac gate, 7 kn from 300 m): the slow wind that switches slicks and windrows on hands over from the near
// map to the far one over most of the near map's half-width, not its outer 20%. The two levels read the wind differently
// (the full wind against the readable one), and at 7 kn the slow wind sits on the slick threshold, so a hand-off over
// 300 m drew the slicks starting along a sharp line 1.2-1.5 km out.
float slowMs = lerp(wFarMean.a, wNear.a, 1.0 - smoothstep(0.3, 0.92, max(eN.x, eN.y))) * 20.0;
float2 guv = p.xy / GustRect.z;
float gustRatio = (rough * 8.0) / max(WindP.z, 1.0);
float calm = saturate(0.25 + 0.75 * gustRatio);
// Heavy rain beats down the short waves (and greys the surface: below).
calm *= 1.0 - 0.5 * Rain;
// The shore: depth from the shore map (deep where it doesn't reach).
float2 su = (p.xy - ShoreRect.xy) / ShoreRect.z;
float sd = 100.0;
[branch] if (ShoreRect.w > 0.0 && all(su > 0.0) && all(su < 1.0)) sd = ShoreMap.SampleLevel(ShoreMapSampler, float2(su.y, su.x), 0).r;
float shoal = saturate(1.0 - sd / 2.0) * saturate(sd / 0.1);
// W4: shoaling waves break where they are high for the depth (McCowan: H over about 0.78 d), not wherever the bed is near:
// the marina's shallow slips folded into "caps" at 6 kn (white water round the docks in the slip view). The fold the shoal adds
// comes in with the wind, over the same 7.2-16 kn as the whitecaps' onset (#76), when the lake's sea is high enough to break
// in a metre or two of water.
float shoalBreak = shoal * smoothstep(3.7, 8.2, WindP.z);
// Short waves and ripples: slopes for the normals, the Jacobian for the foam. Mip-mapped and filtered by the hardware
// (anisotropic at grazing angles), so they never sparkle in the distance; the slope variance a mip averages away (the
// textures carry the squared slopes too: LEAN mapping) becomes roughness, so the sun's glitter path keeps its width.
float2 duv = float2(p.y, p.x) / DetailP.x + 0.5 / 128.0;
float4 da = Texture2DSample(DetailA, DetailASampler, duv);
float4 db = Texture2DSample(DetailB, DetailBSampler, duv);
// W3: the chop as its fetch grew it here (the ripples below are the local wind's).
""" + SEA_SHORT + """
float chopK = calm * SShort;
sx += db.r * chopK; sy += db.g * chopK;
float jd = lerp(1.0, da.a, min(chopK, 2.0));
float slopeVar = (max(db.b - db.r * db.r, 0.0) + max(db.a - db.g * db.g, 0.0)) * chopK * chopK;
if (DetailP.w > 0.0)
{
    // W2: the ripples face the local wind, not the sea's. The ripple tile (its spectrum faces the sea's wind) is sampled
    // in two frames turned by the 15 degree steps either side of the local turn, and their slopes turned back into the
    // world and blended. A frame turned about the world origin is seamless in itself, and the turn changes over hundreds
    // of metres, so the blend doesn't show. The chop stays the sea's: it doesn't turn with a single puff.
    float2 gd = normalize(WindP.xy + float2(1e-4, 0.0));
    float turn = atan2(gd.x * ldir.y - gd.y * ldir.x, dot(gd, ldir));
    float kf = turn / 0.2618;
    float k0 = floor(kf);
    float2 rsum = float2(0.0, 0.0);
    float rvar = 0.0;
    for (int k = 0; k < 2; k++)
    {
        float a = (k0 + k) * 0.2618;
        float ca = cos(a), sa = sin(a);
        float2 q = float2(ca * p.x + sa * p.y, -sa * p.x + ca * p.y);
        float4 rb = Texture2DSample(RippleB, RippleBSampler, float2(q.y, q.x) / DetailP.y + 0.5 / 64.0);
        float wgt = k == 0 ? 1.0 - (kf - k0) : kf - k0;
        rsum += float2(ca * rb.r - sa * rb.g, sa * rb.r + ca * rb.g) * wgt;
        rvar += (max(rb.b - rb.r * rb.r, 0.0) + max(rb.a - rb.g * rb.g, 0.0)) * wgt;
    }
    sx += rsum.x * calm; sy += rsum.y * calm;
    slopeVar += rvar * calm * calm;
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
float om = 0.0;
[branch] if (OceanP.z > 0.0)
{
    float2 mr = (p.xy - OceanMaskRect.xy) / OceanMaskRect.zw;
    om = (all(mr >= 0.0) && all(mr <= 1.0)) ? OceanMask.SampleLevel(OceanMaskSampler, float2(mr.y, mr.x), 0).r : 1.0;
}
// W2 (the gulf-swell handoff): the FFT ocean only where the mask lets the open sea in.
[branch] if (om > 0.001)
{
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
float Jt = J * jd - 0.25 * shoalBreak;
// Lacy, broken foam rather than flat patches: two crossed wavy bands at foam-bubble scale.
float lace = (0.5 + 0.5 * sin(p.x * 9.1 + sin(p.y * 7.3) * 1.7)) * (0.5 + 0.5 * sin(p.y * 8.3 + sin(p.x * 6.1 + T * 0.2) * 1.9));
// W0: the threshold moves so coverage follows Monahan's law for the local wind against the mean (caps gather in puffs and
// thin in lulls) times the water body's share (WindP.w: fresh water 0.4); AWaterSurface::WhitecapThreshold mirrors it.
// W8: the threshold is solved on the sea being drawn (CapCal: the threshold that caps Monahan's cover for the mean wind
// times the body's share, and its shift per e-fold; AWaterSurface, FWaveDetail::CapThreshold): fitted to one sea, it
// capped the lake's shorter-fetch sea at a fraction of its share. Until the first solve, the fit on the test's sea
// (AWaterSurface::FoamThresholdAt, CapSlopeAt). The FoamThreshold parameter is an offset from its default 0.6.
float meanKn = clamp(WindP.z / 0.5144, 4.0, 40.0);
bool solved = CapCal.y > 0.0;
float capGain = (solved ? 1.0 : WindP.w) * pow(clamp(gustRatio, 0.05, 4.0), 3.41);
float capSlope = solved ? CapCal.y : 0.018 * pow(meanKn / 10.0, 1.25);
// By the mesh's vertex spacing here (V4_WPO: max(0.5, dist / 64)): the long waves' fold fades with it.
float spK = clamp(log2(max(dist / 64.0, 0.5) / 0.5), 0.0, 3.0);
float capSolved = spK < 1.0 ? lerp(CapCal.x, CapCalFar.x, spK) : (spK < 2.0 ? lerp(CapCalFar.x, CapCalFar.y, spK - 1.0) : lerp(CapCalFar.y, CapCalFar.z, spK - 2.0));
float capBase = solved ? capSolved : 0.63 + 0.083 * exp(-(max(meanKn, 10.0) - 10.0) / 5.0) - 0.042 * exp(-(max(meanKn, 10.0) - 10.0) / 2.0) - 0.03 * max(10.0 - meanKn, 0.0);
float capThr = clamp(capBase + (FoamThreshold - 0.6) + capSlope * log(max(capGain, 1e-4)), 0.3, 0.85);
float2 wd = ldir; // W2: the foam streaks lie along the local wind
float2 wn = float2(-wd.y, wd.x);
float streak = 0.5 + 0.5 * sin(dot(p.xy, wn) * 7.0 + sin(dot(p.xy, wd) * 0.6) * 2.5);
// W8 (docs/water-8/whitecaps): what the camera sees is the cover the test measures. A mip of the chop's Jacobian averages
// toward 1 (flat water), so thresholding it lost every cap from about 40 m out (a 2 m eye's pixel spans several chop
// texels there), and the far fill only began at 150 m: the round 11 lake at 20 kn showed almost no caps while its grid
// measured twice the target. Past the first texels the cover comes from the fold table (DetailC: per texel, how folded
// it is against four thresholds, AWaterSurface::CapTableEntry), whose mips average cover, read at this pixel's threshold
// (AWaterSurface::CapCover). The lace and streak patterns fade to their means before they alias, and the caps no
// longer fade with the long waves (WaveFadeMeters): whitecaps show to the horizon.
float foot = length(fwidth(p.xy));                 // m a pixel spans (its long axis)
// The mip the sampler reads: its short axis, or a sixteenth of its long one (16x anisotropic filtering). Grazing views
// keep a sharp texture far out, and the caps stay discrete there.
float2 fdx = ddx(p.xy), fdy = ddy(p.xy);
float footMip = max(min(length(fdx), length(fdy)), max(length(fdx), length(fdy)) / 16.0);
float useTable = smoothstep(1.0, 2.5, footMip * 128.0 / DetailP.x);
float patFade = smoothstep(0.08, 0.3, foot);
float laceE = lerp(lace, 0.09, patFade);   // far: the near caps' mean whiteness (0.92), below
float patternE = lerp(smoothstep(0.55, 0.95, streak * lace), 0.06, patFade);
// The threshold on the chop's own Jacobian: Jt = J (1 - k (1 - jChop)) - 0.25 shoal.
float kC = max(min(chopK, 2.0), 1e-3);
float tC = 1.0 - (1.0 - (capThr + 0.25 * shoalBreak) / max(J, 0.05)) / kC;
float tR = 1.0 - (1.0 - (capThr + 0.08 + 0.25 * shoalBreak) / max(J, 0.05)) / kC;
float crest, residue;
[branch] if (useTable > 0.0)
{
float4 ct = Texture2DSample(DetailC, DetailCSampler, duv);
float4 lct = log(max(ct, 1e-6));   // cover is about exponential in the threshold: interpolate it in log
// (A single texel's cover is a step in the threshold, a coarse mip's about exponential: linear at mip 0, in log from mip
// 3, as AWaterSurface::CapCover.)
float capMip = saturate(log2(max(footMip * 128.0 / DetailP.x, 1.0)) / 3.0);
// The table's thresholds: CapT.x + k CapT.y, k = 0..3 (AWaterSurface::CapTable: centred on the mean wind's threshold).
#define W8_U(t_) (((t_) - CapT.x) / CapT.y)
#define W8_SEL(v_, t_) (W8_U(t_) < 1.0 ? v_.r : (W8_U(t_) < 2.0 ? v_.g : v_.b))
#define W8_SEL2(v_, t_) (W8_U(t_) < 1.0 ? v_.g : (W8_U(t_) < 2.0 ? v_.b : v_.a))
#define W8_W(t_) saturate(W8_U(t_) - clamp(floor(W8_U(t_)), 0.0, 2.0))
#define W8_CAPCOVER(t_) (lerp(lerp(W8_SEL(ct, t_), W8_SEL2(ct, t_), W8_W(t_)), exp(lerp(W8_SEL(lct, t_), W8_SEL2(lct, t_), W8_W(t_))) * step(1.5e-6, W8_SEL2(ct, t_)), capMip) * (W8_U(t_) < 0.0 ? exp(W8_U(t_) * CapT.y / max(capSlope, 0.02)) : 1.0))
// Near, the fold itself (a ramp 0.05 wide centred on the threshold, as the table's entries: AWaterSurface::CapRamp).
// The lace breaks a cap up but keeps most of it white (mean 0.92; was 0.62 with a floor of 0.35): the white area is the
// folded area SailingSim.Visual.Whitecaps holds to Monahan.
crest = lerp(saturate((capThr - Jt) / 0.05 + 0.5), W8_CAPCOVER(tC), useTable);
residue = lerp(saturate((capThr + 0.08 - Jt) / 0.08 + 0.5), W8_CAPCOVER(tR), useTable);
}
else
{
// (Near, the fold alone: the table's branch never runs, so nothing of it can leak into the blend.)
crest = saturate((capThr - Jt) / 0.05 + 0.5);
residue = saturate((capThr + 0.08 - Jt) / 0.08 + 0.5);
}
crest *= saturate(0.8 + 1.3 * laceE);
residue *= patternE * 0.25;
float caps = max(crest, residue);
// Foam the boats make.
float bubbles = (0.5 + 0.5 * sin(p.x * 13.1 + sin(p.y * 9.7) * 2.1)) * (0.5 + 0.5 * sin(p.y * 11.3 + sin(p.x * 8.9 + T * 0.4) * 2.3));
float wakeBreak = saturate(wakeFoam * 2.0 - (1.0 - bubbles) * 1.1) * 0.85;
// Lapping: a line of foam where the wavelets run up the shore, the riprap and the docks, coming and going with them.
float swash = saturate(1.0 - sd / 0.35) * saturate(WindP.z / 4.0);
float lap = swash * saturate(0.35 + 0.65 * sin(T * 1.7 + dot(p.xy, wd) * 1.3 + lace * 2.5)) * (0.45 + 0.55 * lace);
// Heavy rain: splashes and mist grey the surface.
// W4 (docs/water-4): how the foam is drawn, not how much there is (caps is the mask the tests and -SailingDebugFoam
// measure; it is not touched here). Drawn straight as opacity over albedo 0.85, a cap at 0.3-0.5 cover read nearly as
// white as a solid one, flat to its edge: the decal look. Real foam isn't one white: an active crest is dense bubbly white
// (reflectance about 0.5-0.6, Frouin, Schwindling and Deschamps 1996), the residue it leaves is thin and dimmer (about
// half; Koepke 1984's effective whitecap albedo is 0.22 across both), and both break into cells. So:
// - FoamTone scales the foam's white: 1 on an active crest, 0.5 on residue, broken by bubble cells (0.7-1);
// - the opacity follows cover to the power 1.5, so a pixel half covered is a third opaque and only the dense core of a cap
//   is solid white; its edge thins out instead of stopping.
float fresh = saturate(crest / max(caps, 1e-3));
float cells = (0.5 + 0.5 * sin(p.x * 23.7 + sin(p.y * 19.1) * 2.3)) * (0.5 + 0.5 * sin(p.y * 21.3 + sin(p.x * 17.9 + T * 0.6) * 2.7));
float cellsE = lerp(cells, 0.25, patFade);
FoamTone = lerp(0.5, 1.0, fresh) * lerp(0.7, 1.0, saturate(cellsE * 2.0));
FoamTone = lerp(FoamTone, 1.0, saturate(wakeBreak * 2.0) * (1.0 - saturate(caps * 4.0)));   // boats' wash: fresh foam
// A cap's interior isn't solid either: bubble cells and the gaps between them (opacity 0.4-1 by cell), and its edge feathers
// over a wider fold ramp (0.15 of J against the mask's 0.05) so the outline thins out instead of stopping.
float soft = saturate((capThr - Jt) / 0.15 + 0.35) * (1.0 - useTable) + crest * useTable;
// W4 step 2: the foam a cap leaves behind (AWaterSurface's foam grid, FoamGridRect: x0, y0, size m, on). It decays on
// Monahan's residual-whitecap timescale and drifts downwind on the worker, so a cap that has stopped breaking leaves a
// thinning, streaked patch instead of vanishing. Drawn thin and lacy along the wind, at the residue's tone.
float persist = 0.0;
float2 fg = (p.xy - FoamGridRect.xy) / max(FoamGridRect.z, 1.0);
[branch] if (FoamGridRect.w > 0.0 && all(fg > 0.0) && all(fg < 1.0))
    persist = FoamGrid.SampleLevel(FoamGridSampler, float2(fg.y, fg.x), 0).r * saturate(min(min(fg.x, 1.0 - fg.x), min(fg.y, 1.0 - fg.y)) * 12.0);
float trail = saturate(persist - max(caps, wakeBreak));   // what outlives the cap or the boat's wash
float trailDrawn = pow(trail, 1.2) * 0.85 * lerp(0.45, 1.0, smoothstep(0.3, 0.85, lerp(streak * lace, 0.5, patFade)));
float capsDrawn = pow(saturate(max(soft * crest > 0.0 ? lerp(crest, soft, 0.5) : 0.0, residue)), 1.5) * lerp(0.4, 1.0, smoothstep(0.15, 0.75, cellsE));
FoamTone = lerp(FoamTone, 0.5, saturate(trailDrawn / max(capsDrawn + trailDrawn, 1e-3)));
capsDrawn = max(capsDrawn, trailDrawn);
Foam = saturate(max(capsDrawn + wakeBreak, 0.85 * lap) + 0.10 * Rain);
Dark = saturate((gustRatio - 0.95) * 2.5);
// Glassy calm: W2: where the local wind falls under about 3 m/s the capillaries die, and under 1.5 m/s the water is a
// mirror (a lull on a light day, the lake at dawn); a puff ruffles it again within seconds (the map's roughness rises in
// about 2 s and settles over 10). Was under about 2 kn only.
float glass = (1.0 - smoothstep(1.5, 3.0, rough * 8.0)) * (1.0 - Dark);
// W2: slicks: in light air (the slow wind under about 6 m/s) bands of smooth water lie along the wind where surface films
// gather: tens of metres across, hundreds long, wandering. They follow the wind's direction over minutes (WindSlow).
float2 sw = normalize(WindSlow.xy + float2(1e-4, 0.0));
float2 sn = float2(-sw.y, sw.x);
float across = dot(p.xy, sn), along = dot(p.xy, sw);
// W2 follow-up (Mac gate still, 7 kn from 300 m; PC pre-screen): slicks as they look from the air: long filaments along
// the wind that meander, part and rejoin, a few to tens of metres across, a hundred or more apart, patchy. Bands cut from
// a lattice read as ruled lines in perspective however they are hashed, so: the ridge of a value noise stretched along
// the wind (900 m along, 160 m across), its domain warped by a coarser one so the filaments bend; the ridge's threshold
// wanders (wider and thinner filaments) and a third, slower noise leaves about half the water without any. Faded out
// where a filament would be under a few pixels.
#define SLK_H(c) frac(sin(dot(c, float2(12.9898, 78.233))) * 43758.5453)
#define SLK_VN(q_) lerp(lerp(SLK_H(floor(q_)), SLK_H(floor(q_) + float2(1, 0)), smoothstep(0.0, 1.0, frac(q_).x)), lerp(SLK_H(floor(q_) + float2(0, 1)), SLK_H(floor(q_) + float2(1, 1)), smoothstep(0.0, 1.0, frac(q_).x)), smoothstep(0.0, 1.0, frac(q_).y))
float2 sq0 = float2(along / 900.0, across / 160.0);
float2 sw1 = sq0 * float2(0.6, 0.45) + 11.3, sw2 = sq0 * float2(0.5, 0.4) + 3.7;
float2 sq = sq0 + float2(0.35, 0.9) * (float2(SLK_VN(sw1), SLK_VN(sw2)) - 0.5);
float2 sq2 = sq * float2(2.1, 1.9) + 5.1, sq3 = sq * 0.7 + 21.0, sq4 = sq * float2(0.25, 0.3) + 7.9;
float sN = 0.65 * SLK_VN(sq) + 0.35 * SLK_VN(sq2);
float ridge = 1.0 - abs(2.0 * sN - 1.0);
float sEdge = lerp(0.8, 0.93, SLK_VN(sq3));
float band = smoothstep(sEdge, sEdge + 0.05, ridge) * smoothstep(0.38, 0.62, SLK_VN(sq4));
float slick = band * (1.0 - smoothstep(3.5, 6.0, slowMs)) * (1.0 - glass) * saturate(1.0 - fwidth(sq.y) * 10.0);
// W2: windrows (Langmuir circulation) from about 3 m/s: thin lines of foam and smoother water along the wind, a few to
// 20 m apart (here about 14 m: each row's spacing jittered, the rows bending), broken into dashes, some rows faint or
// missing; faded out before they alias.
float wx = across / 14.0 + 0.35 * sin(along / 90.0) + 0.2 * sin(across / 47.0) + 0.5 * sin(along / 230.0 + across / 170.0);
float wk = floor(wx);
float wh = frac(sin(wk * 12.9898 + 3.7) * 43758.5453), wh2 = frac(sin(wk * 78.233 + 1.9) * 24634.6345);
float wdash = 0.5 + 0.5 * sin(along / lerp(3.5, 6.5, wh) + wk * 2.3 + 1.7 * sin(along / 17.0 + wk));
float ww = lerp(0.6, 1.8, wh2);   // each row its own width
float wline = (1.0 - smoothstep(0.008 * ww, 0.025 * ww, abs(frac(wx) - (0.35 + 0.3 * wh)))) * smoothstep(0.35, 0.8, wdash) * lerp(0.3, 1.0, step(0.25, wh));
float wrow = wline * smoothstep(3.0, 4.5, slowMs) * saturate(1.0 - dist / 260.0) * saturate(1.0 - fwidth(wx) * 8.0);
float smoothing = max(glass, max(0.65 * slick, 0.5 * wrow));
sx *= 1.0 - 0.85 * smoothing; sy *= 1.0 - 0.85 * smoothing;
slopeVar *= 1.0 - 0.92 * smoothing;
Foam = saturate(Foam + 0.05 * wrow * lace); // a faint, lacy line of bubbles and scum; mostly they read as smoother water
// Glint: a calm morning's sharp sun path, broadening with the wind and the ripples it raises; rain flattens and greys.
float r0 = lerp(lerp(0.015, 0.22, saturate((rough - 0.3) * 0.7)), 0.004, smoothing);
// GGX alpha = roughness^2; the unresolved slope variance adds to it (scaled down: the engine's GGX has no multiple
// scattering, so a fully rough grazing reflection comes out darker than the sky sheen real water shows).
float alpha = sqrt(r0 * r0 * r0 * r0 + 0.3 * slopeVar);
// Graphics G6: never smoother than the wind allows. Cox and Munk's mean square slope (0.003 + 0.00512 U, U in m/s at 10 m)
// is mostly in waves shorter than any texel here: unresolved, it is roughness. Without it a 16 kn bay mirrored the boats
// like a calm (round 7's race start) and the far lake from the drone read as a glossy sheet. A little over half of it
// (the resolved slopes carry the rest), none on glassy water.
float cm = 0.003 + 0.00512 * rough * 8.0;
alpha = max(alpha, sqrt(2.0 * cm) * 0.55 * (1.0 - smoothing) * (1.0 - 0.4 * Glitter));
// Graphics G8 cinematic look (AWaterSurface: Glitter, High and Ultra): a sharper lobe toward the sun, so the glitter
// path breaks into the dense sparkle of a sunset photo instead of a soft sheen. Only the unresolved floor is cut: the
// resolved slopes and their mip variance (LEAN) still set its width.
// W2: polarized sunglasses (AWaterSurface: -SailingPolarized, sailing.Polarized): they cut the sky's glare most near
// Brewster's angle (53 degrees from the vertical), so the water's own texture (puffs, lulls, slicks) stands out.
float3 vdir = normalize(cam - p);
float inc = acos(saturate(vdir.z));
Spec = 0.5 * (1.0 - 0.8 * Polarized * exp(-pow((inc - 0.93) / 0.42, 2.0)));
OceanShare = om;
Rough = sqrt(alpha) + 0.08 * saturate((gustRatio - 1.0) * 3.0) + Rain * 0.12;
// W8: -SailingDebugFoam: the whitecaps alone, for counting on a screenshot (docs/water-8/whitecaps). A pixel is foam with
// the probability of its whitecap cover (a fixed hash of the pixel, so the temporal AA keeps it binary); the water is
// black (no reflection, albedo cut through Dark), flat.
[branch] if (DebugFoam > 0.0)
{
    float hsh = frac(sin(dot(floor(Parameters.SvPosition.xy), float2(12.9898, 78.233))) * 43758.5453);
    // 1: the whitecaps (crests and their residue); 2: the crests alone; 3: where the fold is under the threshold.
    Foam = DebugFoam > 3.5 ? persist : (DebugFoam > 2.5 ? step(Jt, capThr) : step(hsh + 1e-4, DebugFoam > 1.5 ? crest : caps));   // 4: the W4 foam grid
    FoamTone = 1.0;
    Spec = 0.0;
    Dark = 1.0 / 0.35;
    Rough = 1.0;
    return float3(0.0, 0.0, 1.0);
}
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
    tx = {n: tex(n, 1300 + 150 * i) for i, n in enumerate(("OceanA", "OceanB", "OceanMask", "DetailA", "DetailB", "RippleB", "WakeGrid", "ShoreMap", "DetailC", "FoamGrid"))}
    ocean_p = vector(mat, "OceanParams", (480, 60, 0, 6000), -1800, 2400)
    ocean_rect = vector(mat, "OceanMaskRect", (0, 0, 1, 1), -1800, 2500)
    # x: chop tile (m), y: ripple tile (m), z: distance the short waves fade over (m), w: 1 = ripples on (High).
    detail_p = vector(mat, "DetailParams", (23, 3.1, 300, 0), -1800, 2600)
    wake_rect = vector(mat, "WakeGridRect", (0, 0, 25.6, 128), -1800, 2700)
    # Shore map (water depth, m): x0, y0, size (m), w = 1 when bound.
    shore_rect = vector(mat, "ShoreRect", (0, 0, 1, 0), -1800, 2800)
    sea = sea_params(mat, -2000, 2400)
    common = ["P", "Cam", "T", "Fade", "Chop"] + [f"W{i}" for i in range(NUM_LONG)] + [f"A{i}" for i in range(NUM_LONG // 4)] \
        + ["OceanA", "OceanB", "OceanMask", "OceanP", "OceanMaskRect", "DetailA", "DetailP", "WakeGrid", "WakeGridRect", "ShoreMap", "ShoreRect",
           "Sea", "SeaRect", "SeaP"]
    wpo = custom(mat, V4_WPO, common + ["HullClipA", "HullClipB", "HullClipC"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, -400,
                 extra_outputs=[("LongN", unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    # The player's hull (AWaterSurface): A (x, y m, cos, sin heading), B (bow x, stern x, widest x, half beam), C (aft
    # length, transom beam loss, hull centre y, on).
    for i, (n, v) in enumerate((("HullClipA", (0, 0, 1, 0)), ("HullClipB", (3, -3, 0, 1)), ("HullClipC", (3, 0.2, 0, 0)))):
        connect(vector(mat, n, v, -1800, 3000 + 100 * i), "RGBA", wpo, n)
    interp = node(mat, unreal.MaterialExpressionVertexInterpolator, -400, -900)
    connect(wpo, "LongN", interp, "")
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    gust_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1800, 700, parameter_name="GustMap", texture=white)
    gust_rect = vector(mat, "GustRect", (0, 0, 3200, 1), -1800, 800)
    far_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, -2000, 700, parameter_name="WindFar", texture=white)
    far_rect = vector(mat, "WindFarRect", (0, 0, 16000, 1), -2000, 800)
    wind_slow = vector(mat, "WindSlow", (1, 0, 0, 0), -2000, 900)
    polarized = scalar(mat, "Polarized", 0.0, -2000, 1000)
    wind = vector(mat, "WindParams", (1, 0, 5, 0), -1800, 900)
    rain = scalar(mat, "Rain", 0.0, -1800, 1000)
    F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    shade_common = ["P", "Cam", "T", "Fade", "OceanA", "OceanB", "OceanMask", "OceanP", "OceanMaskRect", "DetailA", "DetailP", "WakeGrid", "WakeGridRect", "ShoreMap", "ShoreRect", "Sea", "SeaRect", "SeaP"]
    shade = custom(mat, V4_SHADE, shade_common + ["LongN", "DetailB", "RippleB", "Gust", "GustRect", "WindP", "Rain", "FoamThreshold",
                                                  "WindFar", "WindFarRect", "WindSlow", "Polarized", "Glitter", "DebugFoam", "DetailC", "CapT", "CapCal", "CapCalFar", "FoamGrid", "FoamGridRect"],
                   unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, 400,
                   extra_outputs=[("Foam", F1), ("Rough", F1), ("Dark", F1), ("Spec", F1), ("OceanShare", F1), ("FoamTone", F1)])
    connect(far_tex, "", shade, "WindFar")
    connect(far_rect, "RGBA", shade, "WindFarRect")
    connect(wind_slow, "RGBA", shade, "WindSlow")
    connect(polarized, "", shade, "Polarized")
    connect(scalar(mat, "Glitter", 0.0, -2000, 1050), "", shade, "Glitter")
    connect(scalar(mat, "DebugFoam", 0.0, -2000, 1100), "", shade, "DebugFoam")
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
        connect_sea(sea, c)
    connect(tx["DetailB"], "", shade, "DetailB")
    connect(tx["DetailC"], "", shade, "DetailC")
    connect(tx["FoamGrid"], "", shade, "FoamGrid")  # W4: the foam the caps leave (AWaterSurface's foam grid)
    connect(vector(mat, "FoamGridRect", (0, 0, 64, 0), -2000, 1500), "RGBA", shade, "FoamGridRect")
    connect(vector(mat, "CapTable", (0.5, 0.05, 0, 0), -2000, 1200), "RGBA", shade, "CapT")
    connect(vector(mat, "CapCalib", (0, 0, 0, 0), -2000, 1300), "RGBA", shade, "CapCal")
    connect(vector(mat, "CapCalibFar", (0, 0, 0, 0), -2000, 1400), "RGBA", shade, "CapCalFar")
    connect(tx["RippleB"], "", shade, "RippleB")
    connect(gust_tex, "", shade, "Gust")
    connect(gust_rect, "RGBA", shade, "GustRect")
    connect(wind, "RGBA", shade, "WindP")
    connect(rain, "", shade, "Rain")
    connect(thr, "", shade, "FoamThreshold")

    # Surface: foam on top (opaque, white, rough); the water body itself is light the water absorbs and scatters.
    body_albedo = vector(mat, "WaterAlbedo", (0.16, 0.18, 0.11, 1), -600, 900)        # Ray Hubbard: olive grey-green silt
    body_ext = vector(mat, "WaterExtinction", (2.6, 2.4, 3.2, 1), -600, 1000)        # 1/m: about half a metre of visibility
    # W2 (the gulf-swell handoff): the open sea's body where the swell mask lets it in (the Gulf front of Galveston),
    # blended by the mask; the same as the body where there is no sea.
    sea_albedo = vector(mat, "WaterAlbedoSea", (0.08, 0.16, 0.13, 1), -600, 1100)
    sea_ext = vector(mat, "WaterExtinctionSea", (0.62, 0.32, 0.42, 1), -600, 1200)
    albedo = node(mat, unreal.MaterialExpressionLinearInterpolate, -400, 900)
    connect(body_albedo, "", albedo, "A")
    connect(sea_albedo, "", albedo, "B")
    connect(shade, "OceanShare", albedo, "Alpha")
    extinction = node(mat, unreal.MaterialExpressionLinearInterpolate, -400, 1000)
    connect(body_ext, "", extinction, "A")
    connect(sea_ext, "", extinction, "B")
    connect(shade, "OceanShare", extinction, "Alpha")
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
    foam_tinted = node(mat, unreal.MaterialExpressionMultiply, -100, 1200)  # W4: FoamTone (active crest 1, residue 0.5)
    connect(foam_col, "", foam_tinted, "A")
    connect(shade, "FoamTone", foam_tinted, "B")
    connect(foam_tinted, "", slw, "BaseColor")
    connect(rough_mix, "", slw, "Roughness")
    connect(shade, "Spec", slw, "Specular")
    connect(to_tangent, "", slw, "Normal")
    connect(shade, "Foam", slw, "TopMaterialOpacity")
    connect(albedo_dark, "", slw, "WaterAlbedo")
    connect(extinction, "", slw, "WaterExtinction")
    connect(phase, "", slw, "WaterPhaseG")
    MEL.connect_material_property(slw, "", unreal.MaterialProperty.MP_FRONT_MATERIAL)
    MEL.connect_material_property(with_curvature(mat, wpo, 200, 1300), "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


# ---------------------------------------------------------------- sky, Visual V5
# FStormShape (CloudSky.h): keep these in step with the C++ (SailingSim.Visual.ShelfCloud checks the C++).
STORM = dict(ShelfLeadM=250.0, ShelfBaseM=520.0, ShelfLipM=180.0, ShelfSlope=0.85, ShelfDepthM=3500.0, ShelfTierM=700.0, CoreBehindM=700.0,
             CoreBaseM=750.0, CoreTopM=6500.0, AnvilBaseM=4800.0, AnvilAheadM=9000.0,
             # W8 (storm from the sunshine): cumulus fade near the front; the shelf's crisp edge and lit rolled face.
             CumulusFadeFarM=5000.0, CumulusFadeNearM=1500.0, ShelfEdgeM=60.0, ShelfFaceM=450.0)

# Graphics G6: extinction of cumulus, stratus, storm and rain relative to CloudDensity (-SailingCloudLayerExt overrides).
CLOUD_EXT = (1.0, 1.0, 1.0, 1.0)
# Graphics G6: the most optical depth one march step of storm, stratus or rain may hold (fair cumulus twice that; see the
# caps in CLOUD_CODE). 1 measured smoothest on the storm stills; -SailingCloudStepDepth overrides.
MAX_STEP_DEPTH = 1.0

CLOUD_CODE = """
// Visual V5: the cloud layers from the weather map (FWeatherMap: cumulus, stratus, cirrus, storm extent), each with its
// own base, top, density profile and noise; the storm's built structure (shelf cloud, rain core, anvil) from the gust
// front (FStormShape); lightning lighting the cloud from inside.
float3 p = P * 0.01;            // m, map frame
float alt = Alt * 0.01;         // m above the water
// The map lies in the clouds' drifting frame (world = field + Drift).
float2 wuv = (p.xy - Drift.xy - WRect.xy) / WRect.z;
float4 w = Wx.SampleLevel(WxSampler, float2(wuv.y, wuv.x), 0);
// Graphics G2: no cloud past the map's edge (32 km out): its clamped edge texels smeared into streaks toward the horizon.
w *= saturate(min(min(wuv.x, 1.0 - wuv.x), min(wuv.y, 1.0 - wuv.y)) * 25.0);
float altKm = alt * 0.001;
// Layer profiles: flat bases, rounded tops.
float hCu = (altKm - Cu.y) / max(Cu.z - Cu.y, 0.05);
float hSt = (altKm - St.y) / max(St.z - St.y, 0.05);
float hCi = (altKm - Ci.y) / max(Ci.z - Ci.y, 0.05);
// Graphics G1: a cumulus cell's top rises with its presence in the map (domes, taller in the middle of a cell and over
// the heated land), its base stays flat.
// C1 (round 12): a dome, not a cone. The top rose linearly with the cell's presence, which falls off toward its edge, so
// every cell came out as a pointed cone; a low power (0.3) keeps the sides steep and the top round.
float cuTop = max(pow(saturate(w.r * 1.25), 0.3), 0.3);   // W5a: small cells are low puffs, not 150 m pancakes
// C1: one flat base for every cell (the day's condensation level), softened over its lowest 12%; the top fades over its
// last quarter only (fading over 70% of the height tapered every tower).
float pCu = smoothstep(0.0, 0.12, hCu) * (1.0 - smoothstep(0.75 * cuTop, cuTop, hCu));
float pSt = smoothstep(0.0, 0.12, hSt) * (1.0 - smoothstep(0.7, 1.0, hSt));
float pCi = smoothstep(0.0, 0.3, hCi) * (1.0 - smoothstep(0.6, 1.0, hCi));
// Storm structure along the front (D: metres ahead of the outflow).
float D = dot(p.xy - FrontA.xy, FrontA.zw) - FrontB.x;
// The front isn't ruler-straight: its line wanders a few hundred metres along its length (zero on the start line).
float L = dot(p.xy - FrontA.xy, float2(-FrontA.w, FrontA.z));
D += 300.0 * sin(L / 2300.0) + 150.0 * sin(L / 900.0);
// Graphics G1: the storm's walls bulge in and out by a few hundred metres (a straight-sided core read as a block from afar).
float2 sw = Curl.SampleLevel(CurlSampler, (p.xy - Drift.xy) * 0.00035, 0).rg * 2.0 - 1.0;
D += 600.0 * sw.x + 250.0 * sw.y * sin(alt * 0.0012);
float storm = 0.0, shelf = 0.0, shelfH = 0.0, shelfX = 1e6;
[branch] if (FrontB.y > 0.0 && w.a > 0.0)
{
    float x = SHELF_LEAD - D;
    if (x >= 0.0 && x <= SHELF_DEPTH)
    {
        float base = SHELF_BASE - 120.0 * smoothstep(0.0, 800.0, x);
        // W5a: the face climbs in two or three broad tiers (ledges SHELF_TIER apart, hundreds of metres tall, so the march
        // resolves them), then evenly into the storm: a smooth staircase in x (FStormShape::TierX).
        float tierA = 1.0 - smoothstep(2.0 * SHELF_TIER, 3.0 * SHELF_TIER, x);
        float xt = x - tierA * SHELF_TIER / 6.2831853 * sin(6.2831853 * x / SHELF_TIER);
        float top = base + SHELF_LIP + xt * SHELF_SLOPE;
        // W8: a crisp leading edge (the arcus), full density SHELF_EDGE behind the lip (FStormShape::Density).
        shelfX = x;
        shelf = smoothstep(0.0, SHELF_EDGE, x) * smoothstep(base, base + 25.0, alt) * (1.0 - smoothstep(top - 150.0, top, alt)) * (1.0 - smoothstep(SHELF_DEPTH - 600.0, SHELF_DEPTH, x));
        // Graphics G1: no tiers in the density: anything finer than the march step (about 190 m) aliased into grain
        // (the V5 bands too). The face is shaded smoothly instead: dark at the base, brighter up the face.
        shelfH = saturate((alt - base) / max(top - base, 1.0));
        storm = shelf;
    }
    float core = smoothstep(-CORE_BEHIND, -CORE_BEHIND - 1500.0, D) * (1.0 - smoothstep(-CORE_BEHIND - 14000.0, -CORE_BEHIND - 20000.0, D));
    float coreTop = CORE_BASE + (CORE_TOP - CORE_BASE) * FrontB.z;
    storm = max(storm, core * smoothstep(CORE_BASE, CORE_BASE + 200.0, alt) * (1.0 - smoothstep(coreTop - 1500.0, coreTop, alt)));
    if (D > -CORE_BEHIND - 15000.0 && D < ANVIL_AHEAD)
    {
        float ahead = saturate(1.0 - max(D, 0.0) / ANVIL_AHEAD);
        float lower = ANVIL_BASE + (1.0 - ahead) * 2000.0;
        // The anvil is thin ice cloud: a light veil overhead, not a second dark lid (it hid the shelf's edge, Graphics G1).
        // W8: thinning as the square of what is left ahead (FStormShape::AnvilDensity): the sun reaches the water under it.
        storm = max(storm, 0.12 * ahead * ahead * FrontB.z * smoothstep(lower, lower + 400.0, alt) * (1.0 - smoothstep(CORE_TOP - 800.0, CORE_TOP, alt)));
    }
    // W5a: no rain here. The rain under the core (and a real day's radar rain) is drawn by M_RainCurtain (W5b,
    // ASailingEnvironment::UpdateRainCurtains), so the march no longer fills the air below the cloud base.
    storm *= w.a;
    shelf *= w.a;
}
// W8: the fair cumulus fade out near the front and under the storm (FStormShape::CumulusFade): inside the deck's shade
// they were flat grey towers (round 11). nearF: how near the front this is (the deck's shade on the cloud's colour).
float nearF = FrontB.y > 0.0 ? (1.0 - smoothstep(CU_FADE_NEAR, CU_FADE_FAR, D)) * smoothstep(-CORE_BEHIND - 20000.0, -CORE_BEHIND - 14000.0, D) : 0.0;
float cu = w.r * pCu * Cu.w * (1.0 - w.a * saturate(FrontB.z) * nearF);
float st = w.g * pSt * St.w;
float ci = w.b * pCi * Ci.w;
// Conservative density: what the noise can at most leave (lets the tracer skip empty sky quickly).
Cons = saturate(cu + st + ci + storm);
float d = 0.0;
// Graphics G6: the length of this view ray's march step (m). UE's tracer spreads up to Tracer.y samples over the ray's run
// through the cloud slab (Tracer.x km thick), capped at Tracer.w km; runs under Tracer.z km get proportionally fewer.
float3 vd = normalize(p - Cam * 0.01);
float runM = min(Tracer.x * 1000.0 / max(abs(vd.z), 1e-3), Tracer.w * 1000.0);
float stepM = max(runM, Tracer.z * 1000.0) / max(Tracer.y, 1.0);
// The same sample feeds the shadow rays toward the sun, whose steps are Shadow.x km over Shadow.y samples: the light
// they carry must not jump from lit to black within one of their steps either.
float capStepM = max(stepM, Shadow.x * 1000.0 / max(Shadow.y, 1.0));
Albedo = float3(0.95, 0.95, 0.95);
Emit = float3(0.0, 0.0, 0.0);
AO = 1.0;
[branch] if (Cons > 0.001)
{
    // Graphics G1: the baked noise (Tools/clouds/make_cloud_noise.py), drifting with the wind aloft. A curl field 13 km
    // across (incommensurate with the shape's 4 km tile) warps the shape volume by up to 1.3 km, so no cloud repeats
    // within tens of kilometres (SailingSim.Visual.CloudNoise); the Worley detail
    // (667 m tile) erodes the edges.
    float3 q = (p - float3(Drift.xy, 0.0)) * 0.001;   // km
    // Filter by what a sample covers: a pixel's footprint at this distance, but never finer than the march step
    // (100-200 m): mip 0 everywhere aliased into speckle (the V5 grain).
    // Graphics G6: and never finer than this ray's actual step. Rays near the horizon cross tens of kilometres of the slab
    // in the same sample count (steps of 600 m at 50 km), where noise filtered at 160 m aliased into grain.
    // W5a: the floor follows the march instead of a fixed 160 m (set when every step was about 190 m): with the tracer
    // fitted to the layers present and the samples Ultra spends, steps near a cloud are 10-50 m, and filtering at 160 m
    // blurred every near cloud into cotton. Not below 110 m: at 50 the salt-white frosting (G8) came back on the near
    // clouds overhead.
    float foot = max(distance(p, Cam * 0.01) * 0.0022, max(110.0, stepM * 0.85));
    float shapeMip = clamp(log2(foot / 31.0), 0.0, 6.0);        // shape texel: 4 km / 128
    // Graphics G8 (round 8: "the clouds have noise"): one mip coarser. Edge erosion finer than the step frosted every
    // cloud's outline with salt-white speckle where jittered samples landed either side of a fine billow.
    float detailMip = clamp(log2(foot / 10.4) + 1.0, 0.0, 5.0);   // detail texel: 667 m / 64
    float2 cw = Curl.SampleLevel(CurlSampler, q.xy * 0.077, 0).rg * 2.0 - 1.0;
    float3 qw = q + float3(cw * 1.3, 0.0) + float3(0.0, 0.0, 0.2 * cw.x);
    // Vertically the shape varies 2.4 times faster than across (a cloud is a few hundred metres to 2 km deep): at one rate a
    // lone peak of the noise stood as a thin column under thin cloud.
    // C1 (round 12: "stacked pancakes, contour lines"): 2 times, not 2.4: squeezed that hard the noise's own layers
    // stacked into flat plates through every tower (at 1.4 they stood as columns instead).
    float4 sh = Shape.SampleLevel(ShapeSampler, qw * float3(0.25, 0.25, 0.5), shapeMip);
    float lowFbm = sh.g * 0.5 + sh.b * 0.3 + sh.a * 0.2;     // the 500 m and 250 m octaves carry the billows
    // Perlin-Worley remapped by the low Worley octaves (Nubis): billows packed into cells, 0..1. C1: a little gentler (at 1.9 the
    // remap clipped into flat plateaus whose rims read as contour lines; at 1.5 the billows went smooth as balloons).
    float base = saturate((sh.r - (lowFbm - 1.0)) / (2.0 - lowFbm) * 1.75 - 0.62);
    float3 dq = qw * 1.5 + float3(0.0, 0.0, -0.4 * q.z);
    float3 dt = Detail.SampleLevel(DetailSampler, dq, detailMip).rgb;
    float hf = dt.r * 0.625 + dt.g * 0.25 + dt.b * 0.125;
    float n1 = base;
    float n2 = hf;
    // Cumulus: the weather map's cells, shaped by the base noise (narrowing upward into cauliflower tops over a flat
    // base), then eroded: wispy, torn edges low down, billowed ones higher up.
    // Coverage remap (Nubis): the billow noise's iso-surface is the cloud's outline, so cells are cauliflowered all round
    // rather than the map's footprint extruded; coverage narrows toward the top.
    // C1: the cumulus height profile (Nubis): full coverage over the flat base and up the sides, narrowing near the top so towers
    // round off into domes instead of standing as extruded footprints.
    float covCu = saturate(cu * (1.0 - 0.35 * smoothstep(0.5, 1.0, saturate(hCu / max(cuTop, 0.3)))));
    // W5a: billows scale with the cloud. The weather map's cells come in many sizes (FWeatherMap::Paint) and a small cell
    // never builds past a low presence: it takes billows at twice the frequency, a big tower the full-size ones (the
    // same noise blended, never a warped frequency).
    float baseCu = base;
    [branch] if (covCu > 0.001 && w.r < 0.9)
    {
        float4 sh2 = Shape.SampleLevel(ShapeSampler, qw * float3(0.5, 0.5, 1.0) + 0.37, min(shapeMip + 1.0, 6.0));
        float low2 = sh2.g * 0.5 + sh2.b * 0.3 + sh2.a * 0.2;
        float base2 = saturate((sh2.r - (low2 - 1.0)) / (2.0 - low2) * 1.75 - 0.62);
        baseCu = lerp(base2, base, smoothstep(0.35, 0.9, w.r));
    }
    float shapeCu = saturate((baseCu - (1.0 - covCu)) / max(covCu, 0.08)) * step(0.001, covCu);
    // Graphics G8: eroded by the detail's coarse octaves (the 16- and 32-cell ones speckled the edges), and a crisper
    // ramp from edge to body: fair cumulus has a hard, sunlit outline, not a feathered, painted one.
    float hfCu = dt.r * 0.8 + dt.g * 0.2;
    // C1: the billows build upward (Nubis): next to nothing eaten from the base (one flat base for every cell), wispy
    // erosion just above it, billowed (inverted Worley) higher up where the bubbles rise.
    float ero = lerp(0.15 * hfCu, 0.55 * (1.0 - hfCu), smoothstep(0.05, 0.45, hCu));
    // Crisp, sunlit tops and soft bases: the edge-to-body ramp steepens with height.
    float dCu = saturate((shapeCu - ero * saturate(1.0 - shapeCu * 1.5)) * lerp(2.5, 6.0, saturate(hCu * 1.5))) * 1.6;
    float dSt = saturate((st - (1.0 - n1) * 0.3) * 1.6 - (1.0 - n2) * 0.15 * smoothstep(0.25, 0.0, hSt));
    float dCi = saturate((ci - (1.0 - n1) * 0.6) * 1.5);
    // The storm: the shelf cloud's underside smooth and banded, the core dense, the anvil fibrous.

    // W8: all of the storm's own shaping under one branch (fair-weather samples skip it: Mac gate, helm-eye High).
    float nearBase = 0.0, lip = 0.0, faceS = 0.0, dSm = 0.0, nS = 0.5;
    [branch] if (storm > 0.0)
    {
        // The storm's base is turbulent: lumpy, sagging, torn (strong small-scale erosion in its lowest few hundred metres).
        nearBase = 1.0 - smoothstep(CORE_BASE, CORE_BASE + 500.0, alt);
        // Storm cloud uses the coarser shape octaves (a big dense mass at 100-200 m steps speckled with the fine ones); the
        // shelf's face is smooth, its base and the core's ragged.
        nS = saturate(lerp(sh.g * 1.25 - 0.1, base, 0.5));   // the billows too: a tower's cauliflower sides
        // The lip (the shelf's first few hundred metres) keeps a clean edge.
        lip = shelf * (1.0 - smoothstep(0.0, 500.0, SHELF_LEAD - D));
        // W5a: the storm's interior is smooth: the billow erosion bites only near its outline (where the built density ramps
        // off) and underneath; the fine detail only underneath, so the shelf's face reads as broad smooth tiers over a torn
        // base (round 10: the storm's mass was frosted all through).
        float edgeS = max(saturate((1.0 - storm) * 2.5), nearBase);
        // W8: under the shelf the torn base takes the coarse billows only (nS), never the fine detail: the detail varied
        // faster than the march step there and frosted the base with speckle (round 11's bay storm). The core keeps it.
        float torn = lerp(1.0 - n2, 1.0 - nS, saturate(shelf * 2.0));
        // W8: the shelf's sloping face above its base (FStormShape::ShelfShade) is a smooth, sunlit surface, the rolled lip
        // (SHELF_FACE deep behind the leading edge) brightest: almost no erosion there, so its edge is a clean arc, not froth.
        [branch] if (shelf > 0.0) faceS = smoothstep(0.08, 0.35, shelfH) * lerp(0.6, 1.0, 1.0 - smoothstep(0.33 * SHELF_FACE, SHELF_FACE, shelfX));
        dSm = saturate((storm - (1.0 - nS) * lerp(0.2, 0.35, saturate(alt / 6000.0)) * (1.0 - 0.7 * max(lip, 0.85 * shelf * (1.0 - nearBase))) * lerp(0.25, 1.0, edgeS) * (1.0 - 0.85 * faceS * shelf) - torn * 0.35 * nearBase * (1.0 - lip)) * 1.6);
    }
    // Graphics G6: each layer's extinction relative to the full CloudDensity (Ext: cumulus, stratus, storm; w, the rains, unused since W5a). The grain
    // in the storm skies was optical depth per march step: at 0.1 /m over a 190 m step every ray went opaque inside one
    // step, so each pixel was lit at whatever depth its jittered sample landed (bright skin or dark interior). A storm's
    // mass and a stratus deck at a fifth of that take several steps to close and the march averages the light; the
    // contrast comes from the shading below (dark bases, lit faces), not from the edge's opacity.
    // Graphics G6: no more than MaxStepDepth of optical depth in one march step. Denser than that, a ray goes opaque within a step and
    // the pixel is lit at whatever depth its jittered sample landed (bright skin or dark core): the frosted grain. Capped,
    // cloud closes over two or three steps and the march averages its light; thick cloud stays opaque. The storm and rain
    // are capped by the longer of the view and shadow steps (their light came through 400 m shadow steps that were
    // all-or-nothing); fair cumulus only by the view step, so its sunlit tops keep their shaded bases.
    // Cumulus: 1.5 times the storm's (G8: at 2 its skin frosted). W5a: it is the step that's fitted now, not the cap
    // (QualityCVars: on Ultra near rays keep all their samples, 19 m steps under a deck), so near cumulus keep their real
    // density and the cap binds only on long runs (at 4 the grain came straight back at the engine's 94 m near steps).
    float cV = Tracer.y > 0.0 ? 1.5 * MaxStepDepth / (stepM * Density) : 1e6;
    // Graphics G8 (round 8: "the clouds have noise"): storm and rain at 0.6 of it. Measured on game-08 (-SailingCloudStepDepth):
    // 0.6 smoothed the storm's grain and kept its dark mass, 0.4 washed it grey; more view samples (160) didn't help.
    float cS = Tracer.y > 0.0 ? 0.6 * MaxStepDepth / (capStepM * Density) : 1e6;
    // A stratus deck is flat and even (little for the jitter to catch): three times the storm's by the view step, so an
    // overcast stays thick and grey (capped by the shadow step it thinned to an optical depth under 2 and went beige).
    float cT = Tracer.y > 0.0 ? 3.0 * MaxStepDepth / (stepM * Density) : 1e6;
    // W8: the shelf's rolled front face (FStormShape::ShelfShade), lit and pale below.
    float face = faceS * shelf;
    d = max(max(min(dCu * Ext.x, cV), min(dSt * Ext.y, cT)), max(dCi, min(dSm * Ext.z, cS)));
    // Darker, wetter storm cloud scatters less to the eye; bases sit in their own shadow (height ambient occlusion).
    // Only the low storm cloud (shelf, core) is dark and wet; the anvil's ice stays bright.
    // The fade sits under the anvil (ANVIL_BASE 4.8 km): from 3 km the shelf's upper tiers and the core's flanks read as pale ice.
    // Wet by the storm's own density, not only its share of d: where the stratus deck runs into the storm it took the
    // larger share and the storm's mass came out white (game-08's pale band over the shelf).
    // Cloud inside the storm's extent (the map's w.a), cumulus and stratus too, sits in the deck's shade: lit white, the
    // fair cells under it made game-08's pale band in front of the shelf.
    // W8: only near the front (nearF): far ahead, fair cells in the storm's lateral extent stay sunlit white.
    float wet = saturate(max(max(dSm / max(d, 1e-3), dSm * 2.0), max(storm * 3.0, w.a * 2.0 * nearF))) * (1.0 - smoothstep(4500.0, 5500.0, alt));
    // Storm sky fix (Oct 15 2026, docs/storm-prescreen): the storm's own cloud is dark wherever the viewer stands. It was
    // darkened by the camera's cloud darkness (FrontB.w), so a storm seen from the sunshine ahead of its front (blind-test
    // game-04: a sunlit boat against what should be a dark storm sky) kept a white, pale-grey wall. Slate, a little blue.
    Albedo = lerp(float3(0.96, 0.96, 0.96), float3(0.19, 0.21, 0.26), wet);
    // The storm's base sits in deep shadow.
    // Graphics G8 ("clouds look like a cartoon"): fair cumulus sits on flat, grey bases in its own shade, the sunlit
    // domes white above them; at 0.75 the whole cloud read as one evenly white, painted shape.
    // W5a: darkened by depth into the cloud, not by altitude: the painted-on height gradient made every cloud the same.
    // The outline (shapeCu near 0) takes the sky's light from all sides and glows; deep inside, the occlusion grows with
    // the cell's build (cuTop), so a towering cell has a dark, heavy base and a small puff stays light all through;
    // the upper half of a cell, open to the sky above, keeps most of it.
    float depthIn = saturate(shapeCu * 1.4);
    float under = 1.0 - smoothstep(0.0, 0.5, saturate(hCu));
    float aoCu = 1.0 - 0.12 * depthIn - under * lerp(0.15, 0.5, saturate(cuTop)) * (0.4 + 0.6 * depthIn);
    AO = lerp(1.0, 0.2, wet * saturate(1.0 - alt / 4000.0)) * lerp(1.0, aoCu, saturate(min(dCu * Ext.x, cV) / max(d, 1e-3)));
    // The shelf (Graphics G1): its base in its own shadow, its face brighter as it rises.
    // Its front faces the clear sky behind the observer and reads lighter than the underside (the lip's pale roll over a
    // dark base): both over hundreds of metres, which the march resolves.
    // W8: the rolled front face (SHELF_FACE deep, above the base) is pale and lit, the underside behind it dark slate
    // (FStormShape::ShelfShade, SailingSim.Visual.ShelfCloud).
    AO *= lerp(1.0, lerp(0.25, 0.8, shelfH), shelf);
    // Its sunlit face glows by emission, not by the march's scattering: the scattered light jumps between the lit skin
    // and the dark interior from one jittered sample to the next (the grain), while light emitted in proportion to the
    // extinction (here d * Density, per metre) integrates to the same radiance wherever the ray closes. SunLum: the sun's
    // luminance on a white diffuser (rgb), w the sun's direction's elevation sine; SunDir its direction (map frame).
    // The face looks along the front's travel and leans back up its slope; wrapped Lambert, pale grey (0.5: with the
    // march's own scattering on top, 0.7 clipped to white).
    // (Only where there is shelf: fair-weather samples skip it, Mac gate helm-eye High.)
    [branch] if (face > 0.0)
    {
    float3 faceN = normalize(float3(FrontA.zw, 0.75));
    float faceLit = saturate(0.25 + 0.75 * dot(faceN, SunDir.xyz));
    // Structure, all of it at the march's scale or coarser (the G1 rule): the tiers' risers (steep, facing out) lit
    // brighter than their ledges, the coarse billows (nS, filtered at the step), and the face dimming back into the storm
    // as the deck above shades it.
    float riser = 0.5 - 0.5 * cos(6.2831853 * shelfX / SHELF_TIER) * (1.0 - smoothstep(2.0 * SHELF_TIER, 3.0 * SHELF_TIER, shelfX));
    float faceTone = lerp(0.75, 1.1, riser) * lerp(0.7, 1.15, nS) * lerp(1.0, 0.3, smoothstep(SHELF_FACE, 1800.0, shelfX)) * lerp(0.8, 1.2, shelfH);
    Emit += SunLum.rgb * (FACE_PALE * faceLit * faceTone) * face * d * Density;
    Albedo *= 1.0 - FACE_SCATTER_CUT * face;
    }
    // Lightning inside the cloud: lights it from within around the strike.
    float r = distance(p, Flash.xyz);
    Emit += float3(0.75, 0.8, 1.0) * Flash.w * exp(-r / 1800.0) * d * 40.0 + DEBUGSTORM;
}
return d * Density;
"""


def cloud_code():
    import os
    c = CLOUD_CODE.replace("DEBUGSTORM", "float3(dSm * 50.0, 0.0, 0.0)" if os.environ.get("SAILING_DEBUG_STORM") else "0.0")
    if os.environ.get("SAILING_DEBUG_LAYERS"):
        # Which layer is which: cumulus red, stratus green, storm blue (albedo, so exposure is untouched).
        c = c.replace("    // Lightning inside the cloud", "    Albedo = normalize(float3(dCu, dSt, dSm) + 1e-4) * 0.9;\n    // Lightning inside the cloud")
    import os as _os
    c = c.replace("FACE_PALE", _os.environ.get("W8_FACE_PALE", "0.3")).replace("FACE_SCATTER_CUT", _os.environ.get("W8_FACE_CUT", "0.9"))
    for k, v in (("SHELF_LEAD", STORM["ShelfLeadM"]), ("SHELF_BASE", STORM["ShelfBaseM"]), ("SHELF_LIP", STORM["ShelfLipM"]),
                 ("SHELF_SLOPE", STORM["ShelfSlope"]), ("SHELF_DEPTH", STORM["ShelfDepthM"]), ("SHELF_TIER", STORM["ShelfTierM"]), ("CORE_BEHIND", STORM["CoreBehindM"]),
                 ("CORE_BASE", STORM["CoreBaseM"]), ("CORE_TOP", STORM["CoreTopM"]), ("ANVIL_BASE", STORM["AnvilBaseM"]),
                 ("ANVIL_AHEAD", STORM["AnvilAheadM"]), ("CU_FADE_FAR", STORM["CumulusFadeFarM"]),
                 ("CU_FADE_NEAR", STORM["CumulusFadeNearM"]), ("SHELF_EDGE", STORM["ShelfEdgeM"]), ("SHELF_FACE", STORM["ShelfFaceM"])):
        c = c.replace(k, repr(float(v)))
    return c


def build_cloud_layers():
    """M_CloudLayers (Visual V5, Medium and High): the volumetric clouds from the weather map and the storm's structure."""
    mat = new_material("M_CloudLayers")
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    mat.set_editor_property("used_with_volumetric_cloud", True)
    pos = node(mat, unreal.MaterialExpressionWorldPosition, -1600, 0)
    attr = node(mat, unreal.MaterialExpressionCloudSampleAttribute, -1600, 100)
    linear = linear_default()
    wx = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 200, parameter_name="WeatherMap", texture=linear,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    # Graphics G1: the baked noise volumes and curl field (scripts/import_cloud_noise.py).
    tex = {n: node(mat, unreal.MaterialExpressionTextureObjectParameter, -1600, 350 + 60 * i, parameter_name=n,
                   texture=unreal.load_asset(f"/Game/Materials/Clouds/T_Cloud{n}"))
           for i, n in enumerate(("Shape", "Detail", "Curl"))}
    vecs = {n: vector(mat, n, d, -1600, 500 + 90 * i) for i, (n, d) in enumerate((
        ("WeatherRect", (-32000, -32000, 64000, 0)), ("LayerCumulus", (0.3, 1.4, 2.6, 1)), ("LayerStratus", (0, 0.9, 1.6, 0.8)),
        ("LayerCirrus", (0, 8.5, 10, 0.25)), ("FrontA", (0, 0, 1, 0)), ("FrontB", (0, 0, 0, 0)), ("Flash", (0, 0, 0, 0)),
        ("Drift", (0, 0, 0, 0)), ("LayerExtinction", CLOUD_EXT), ("Tracer", (0, 80, 15, 50)), ("TracerShadow", (4, 10, 0, 0)),
        ("SunLum", (0, 0, 0, 0)), ("SunDir", (0, 0, 1, 0))))}
    dens = scalar(mat, "CloudDensity", 0.02, -1600, 1300)
    F1, F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT1, unreal.CustomMaterialOutputType.CMOT_FLOAT3
    c = custom(mat, cloud_code(), ["P", "Cam", "Alt", "Wx", "Shape", "Detail", "Curl", "WRect", "Cu", "St", "Ci", "FrontA", "FrontB", "Flash", "Drift", "Density", "Ext", "Tracer", "Shadow", "MaxStepDepth", "SunLum", "SunDir"], F1,
               -900, 300, extra_outputs=[("Albedo", F3), ("Emit", F3), ("Cons", F1), ("AO", F1)])
    connect(pos, "", c, "P")
    connect(node(mat, unreal.MaterialExpressionCameraPositionWS, -1600, -100), "", c, "Cam")
    connect(attr, "Altitude", c, "Alt")
    connect(wx, "", c, "Wx")
    for n, t in tex.items():
        connect(t, "", c, n)
    for n, pin in (("WeatherRect", "WRect"), ("LayerCumulus", "Cu"), ("LayerStratus", "St"), ("LayerCirrus", "Ci"), ("FrontA", "FrontA"),
                   ("FrontB", "FrontB"), ("Flash", "Flash"), ("Drift", "Drift"), ("LayerExtinction", "Ext"), ("Tracer", "Tracer"), ("TracerShadow", "Shadow"),
                   ("SunLum", "SunLum"), ("SunDir", "SunDir")):
        connect(vecs[n], "RGBA", c, pin)
    connect(dens, "", c, "Density")
    connect(scalar(mat, "MaxStepDepth", MAX_STEP_DEPTH, -1600, 1400), "", c, "MaxStepDepth")
    # Extinction (per metre) in the subsurface pin; albedo in base colour; height AO; lightning as emission.
    MEL.connect_material_property(c, "Albedo", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    MEL.connect_material_property(c, "Emit", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(c, "AO", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    adv = node(mat, unreal.MaterialExpressionVolumetricAdvancedMaterialOutput, -400, 600)
    cons = node(mat, unreal.MaterialExpressionMultiply, -600, 600)
    connect(c, "Cons", cons, "A")
    connect(dens, "", cons, "B")
    connect(cons, "", adv, "ConservativeDensity")
    # Two-lobe phase (a bright silver lining toward the sun, some back-scatter) and the multiple-scattering approximation
    # that keeps thick cloud white inside instead of dark at the base.
    # Graphics G1: a sharper forward lobe (silver linings), less multiple-scattering brightening (grey, self-shadowed bases),
    # a third octave so thick cloud stays luminous inside, and the ground's bounce lighting the bases.
    for k, v in (("const_phase_g", 0.72), ("const_phase_g2", -0.3), ("const_phase_blend", 0.3), ("const_multi_scattering_contribution", 0.55),
                 ("const_multi_scattering_occlusion", 0.5), ("const_multi_scattering_eccentricity", 0.55), ("multi_scattering_approximation_octave_count", 3), ("gray_scale_material", True)):
        adv.set_editor_property(k, v)
    for k in ("ground_contribution", "b_ground_contribution"):
        try:
            adv.set_editor_property(k, True)
            break
        except Exception:
            pass
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


SKY_CODE = """
// Visual V5: the sky dome (Medium and High). The atmosphere's own sky, plus: the sun's disc with limb darkening; the
// night sky (stars and the Milky Way placed for the date, the time and the lake's latitude); the moon with its phase and
// the dark limb in earthshine; and the cirrus layer from the weather map, a thin sheet 9 km up.
float3 dir = -CamVec;
float3 col = ViewLum;
// The sun: limb darkening (Eddington, u = 0.6), normalised so the disc's total light is unchanged.
float cosT = dot(dir, SunDir);
float th = acos(clamp(cosT, -1.0, 1.0));
float mu = sqrt(saturate(1.0 - (th / 0.00467) * (th / 0.00467)));
col += SunDisk * (1.0 - 0.6 * (1.0 - mu)) / 0.8;
float up = saturate(dir.z * 10.0 + 0.05);
// Cirrus: where the view ray meets a sheet 9 km up, the weather map's cirrus channel (in the clouds' drifting frame),
// drawn out in streaks; whiter than the sky around it, bright near the sun (forward scattering).
float cirrus = 0.0;
[branch] if (Cirrus.x > 0.0 && dir.z > 0.02)
{
    float t = (9000.0 - CamPos.z * 0.01) / dir.z;
    float2 hit = CamPos.xy * 0.01 + dir.xy * t - Cirrus.yz;
    float2 cuv = (hit - WRect.xy) / WRect.z;
    float c = Wx.SampleLevel(WxSampler, float2(cuv.y, cuv.x), 0).b;
    float2 wd = normalize(Cirrus.yz + float2(1e-3, 0.0));
    float a = dot(hit, wd), b = dot(hit, float2(-wd.y, wd.x));
    // Graphics G5: fibres from value noise stretched along the wind (four octaves, no fixed period). The sine streaks
    // before read as brush strokes in the blind test. The fine octaves fade with distance, where they would shimmer.
    // Only where the map has cirrus (most of a sky has none), three octaves (a fourth faded out at distance anyway).
    float fib = 0.0;
    [branch] if (c > 0.005)
    {
    float2 q = float2(a * 0.00012, b * 0.0011);
    float amp = 0.5;
    float far = saturate(t / 40000.0);
    [unroll] for (int o = 0; o < 3; o++)
    {
        float2 ci = floor(q), cf = frac(q);
        float2 u = cf * cf * (3.0 - 2.0 * cf);
        float h00 = frac(sin(dot(ci, float2(127.1, 311.7))) * 43758.5453);
        float h10 = frac(sin(dot(ci + float2(1.0, 0.0), float2(127.1, 311.7))) * 43758.5453);
        float h01 = frac(sin(dot(ci + float2(0.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
        float h11 = frac(sin(dot(ci + float2(1.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
        float nv = lerp(lerp(h00, h10, u.x), lerp(h01, h11, u.x), u.y);
        fib += amp * nv * (o < 2 ? 1.0 : 1.0 - far);
        q = float2(q.x * 2.03 + 3.1, q.y * 2.11 - 1.7);
        amp *= 0.5;
    }
    fib *= 1.071;   // the three octaves' sum to the four's range
    }
    float streak = saturate((fib - 0.32) * 2.2);
    streak *= streak;
    cirrus = c * streak * saturate(1.0 - t / 60000.0) * Cirrus.w;
    float lum = dot(ViewLum, float3(0.3, 0.59, 0.11));
    col = lerp(col, float3(lum, lum, lum) * 2.2 * (1.0 + 2.5 * pow(saturate(cosT), 12.0)), cirrus * 0.45);
}
// The night sky, in equatorial coordinates.
[branch] if (Night.x > 0.0)
{
    float3 e = float3(dot(dir, Rot0.xyz), dot(dir, Rot1.xyz), dot(dir, Rot2.xyz));
    float dec = asin(clamp(e.z, -1.0, 1.0));
    float ra = atan2(e.y, e.x);
    float2 g = float2(ra * cos(dec), dec) / 0.006;
    float2 cid = floor(g);
    float2 f = frac(g);
    float h = frac(sin(dot(cid, float2(127.1, 311.7))) * 43758.5453);
    float h2 = frac(sin(dot(cid, float2(269.5, 183.3))) * 43758.5453);
    float star = 0.0;
    if (h > 0.82)
    {
        float mag = pow(frac(h * 91.3), 7.0);
        float2 c2 = float2(frac(h * 13.7), h2) * 0.6 + 0.2;
        float d2 = dot(f - c2, f - c2);
        star = (0.03 + 4.0 * mag) * exp(-d2 * 350.0) * (0.75 + 0.25 * sin(Night.w * (3.0 + h2 * 7.0) + h * 40.0));
    }
    // The Milky Way: galactic latitude and longitude from the equatorial direction (IAU J2000 rotation).
    float3 gal = float3(dot(e, float3(-0.0548756, -0.8734371, -0.4838350)), dot(e, float3(0.4941094, -0.4448296, 0.7469822)),
                        dot(e, float3(-0.8676661, -0.1980764, 0.4559838)));
    float b = asin(clamp(gal.z, -1.0, 1.0));
    float l = atan2(gal.y, gal.x);
    float band = exp(-b * b / 0.035) * (0.4 + 0.6 * pow(0.5 + 0.5 * cos(l), 2.0));
    float rift = 1.0 - 0.45 * exp(-pow((b - 0.03 * sin(l * 3.0)) / 0.04, 2.0)) * (0.6 + 0.4 * sin(l * 4.0 + 1.3)); // the Great Rift's dust lane
    float mw = band * rift;
    col += (float3(1.0, 0.97, 0.93) * star + float3(0.8, 0.85, 1.0) * mw * 0.12) * Night.x * up * (1.0 - cirrus);
}
// Light pollution (Visual V6): the sodium-and-LED dome over the nearest big city (Night.y its strength, Night.z its
// azimuth in the map frame), brightest on the horizon toward it, and a fainter glow all round.
[branch] if (Night.y > 0.0)
{
    float az = atan2(dir.y, dir.x);
    float da = abs(atan2(sin(az - Night.z), cos(az - Night.z)));
    float h = max(dir.z, 0.0);
    float glow = Night.y * (0.12 + 1.6 * exp(-da * da / 0.5)) * exp(-h * 7.0) * saturate(dir.z * 30.0 + 1.0);
    col += float3(1.0, 0.70, 0.42) * glow;
}
// The moon: lit by the sun (its phase), the dark part faintly lit by the earth.
float cm = dot(dir, MoonDir.xyz);
[branch] if (MoonDir.w > 0.0 && cm > 0.99997)
{
    float3 mx = normalize(cross(MoonDir.xyz, float3(0.0, 0.0, 1.0)));
    float3 my = cross(mx, MoonDir.xyz);
    float2 uv = float2(dot(dir, mx), dot(dir, my)) / 0.0045;
    float rr = dot(uv, uv);
    if (rr < 1.0)
    {
        float3 n = uv.x * mx + uv.y * my - sqrt(1.0 - rr) * MoonDir.xyz;
        float lit = saturate(dot(n, SunTrue.xyz));
        float maria = 0.82 + 0.18 * sin(uv.x * 5.0 + 1.0) * sin(uv.y * 4.0 + 2.0 + uv.x * 3.0);
        col += MoonDir.w * (lit + SunTrue.w) * maria * saturate(dir.z * 6.0 + 0.2);
    }
}
return col;
"""


def build_sky_dome():
    """M_SkyDome (Visual V5, Medium and High): the sky behind everything (a sky material: clouds and fog draw over it)."""
    mat = new_material("M_SkyDome")
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("is_sky", True)
    camvec = node(mat, unreal.MaterialExpressionCameraVectorWS, -1400, 0)
    campos = node(mat, unreal.MaterialExpressionCameraPositionWS, -1400, 100)
    view_lum = node(mat, unreal.MaterialExpressionSkyAtmosphereViewLuminance, -1400, 200)
    sun_dir = node(mat, unreal.MaterialExpressionSkyAtmosphereLightDirection, -1400, 300)
    sun_disk = node(mat, unreal.MaterialExpressionSkyAtmosphereLightDiskLuminance, -1400, 400)
    linear = linear_default()
    wx = node(mat, unreal.MaterialExpressionTextureObjectParameter, -1400, 500, parameter_name="WeatherMap", texture=linear,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    vecs = {n: vector(mat, n, d, -1400, 650 + 90 * i) for i, (n, d) in enumerate((
        ("WeatherRect", (-32000, -32000, 64000, 0)), ("CirrusParams", (0, 0, 0, 0)), ("NightParams", (0, 0, 0, 0)), ("StarRot0", (1, 0, 0, 0)),
        ("StarRot1", (0, 1, 0, 0)), ("StarRot2", (0, 0, 1, 0)), ("MoonDir", (0, 0, 1, 0)), ("SunTrue", (0, 0, 1, 0))))}
    c = custom(mat, SKY_CODE, ["CamVec", "CamPos", "ViewLum", "SunDir", "SunDisk", "Wx", "WRect", "Cirrus", "Night", "Rot0", "Rot1", "Rot2", "MoonDir", "SunTrue"],
               unreal.CustomMaterialOutputType.CMOT_FLOAT3, -800, 300)
    connect(camvec, "", c, "CamVec")
    connect(campos, "", c, "CamPos")
    connect(view_lum, "", c, "ViewLum")
    connect(sun_dir, "", c, "SunDir")
    connect(sun_disk, "", c, "SunDisk")
    connect(wx, "", c, "Wx")
    for n, pin in (("WeatherRect", "WRect"), ("CirrusParams", "Cirrus"), ("NightParams", "Night"), ("StarRot0", "Rot0"), ("StarRot1", "Rot1"),
                   ("StarRot2", "Rot2"), ("MoonDir", "MoonDir"), ("SunTrue", "SunTrue")):
        connect(vecs[n], "RGBA", c, pin)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


LENS_CODE = """
// Visual V5 (High): water on the lens. Raindrops land and run across the glass with the apparent wind (WindScreen: the
// screen direction the air pushes them, gravity included); spray after a wave leaves a burst of larger spots. Each drop
// refracts the scene behind it (a small lens: the image inside is shifted and slightly dimmed). Returns the UV shift
// (xy) and the drop mask (z).
float2 uv = GetViewportUV(Parameters);
float aspect = View.ViewSizeAndInvSize.x * View.ViewSizeAndInvSize.w;
float2 wdir = normalize(Wind.xy + float2(0.0, 1e-3));
float2 offset = float2(0.0, 0.0);
float mask = 0.0;
for (int layer = 0; layer < 3; layer++)
{
    float scale = 9.0 + 9.0 * layer;
    float speed = Wind.z * (0.08 + 0.05 * layer);
    float2 p = uv * float2(aspect, 1.0) * scale - wdir * T * speed * scale;
    float2 cell = floor(p);
    float2 f = frac(p);
    float h = frac(sin(dot(cell + layer * 17.0, float2(127.1, 311.7))) * 43758.5453);
    float chance = Rain * (0.18 + 0.06 * layer) + Spray * (layer == 0 ? 0.5 : 0.15);
    if (h < chance)
    {
        float2 c = float2(frac(h * 13.1), frac(h * 7.3)) * 0.6 + 0.2;
        float2 d = f - c;
        // Streaked along the way it runs (longer the harder the air pushes).
        float along = dot(d, wdir), across = dot(d, float2(-wdir.y, wdir.x));
        float stretch = 1.0 + 2.0 * saturate(Wind.z * 0.15) * saturate(along * 4.0 + 0.5);
        float r = length(float2(along / stretch, across)) / (0.1 + 0.12 * frac(h * 3.3));
        float drop = smoothstep(1.0, 0.6, r) * (1.0 - 0.6 * frac(T * 0.2 + h));
        // A drop is a little lens: it shows the scene flipped and shrunk (a large shift), its rim catches the light.
        offset += d * drop * 1.6 / (scale * float2(aspect, 1.0));
        mask = max(mask, drop);
    }
}
return float3(offset, mask);
"""


def build_lens_water():
    """M_LensWater (Visual V5, High): rain and spray on the camera's glass."""
    mat = new_material("M_LensWater")
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    rain = scalar(mat, "Rain", 0.0, -1000, 0)
    spray = scalar(mat, "Spray", 0.0, -1000, 100)
    wind = vector(mat, "WindScreen", (0, 1, 0, 0), -1000, 200)
    t = node(mat, unreal.MaterialExpressionTime, -1000, 300)
    c = custom(mat, LENS_CODE, ["Rain", "Spray", "Wind", "T"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, 100)
    connect(rain, "", c, "Rain")
    connect(spray, "", c, "Spray")
    connect(wind, "RGBA", c, "Wind")
    connect(t, "", c, "T")
    vp = custom(mat, "return GetViewportUV(Parameters);", [], unreal.CustomMaterialOutputType.CMOT_FLOAT2, -700, 400)
    off = node(mat, unreal.MaterialExpressionComponentMask, -450, 100, r=True, g=True, b=False, a=False)
    connect(c, "", off, "")
    uv2 = node(mat, unreal.MaterialExpressionSubtract, -300, 200)
    connect(vp, "", uv2, "A")
    connect(off, "", uv2, "B")
    refr = node(mat, unreal.MaterialExpressionSceneTexture, -150, 200)
    refr.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    connect(uv2, "", refr, "UVs")
    scene = node(mat, unreal.MaterialExpressionSceneTexture, -150, 0)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    m = node(mat, unreal.MaterialExpressionComponentMask, -450, 300, r=False, g=False, b=True, a=False)
    connect(c, "", m, "")
    dim = node(mat, unreal.MaterialExpressionMultiply, 0, 250)
    k = node(mat, unreal.MaterialExpressionConstant, -150, 350, r=1.06)
    connect(refr, "Color", dim, "A")
    connect(k, "", dim, "B")
    mix = node(mat, unreal.MaterialExpressionLinearInterpolate, 150, 100)
    connect(scene, "Color", mix, "A")
    connect(dim, "", mix, "B")
    connect(m, "", mix, "Alpha")
    MEL.connect_material_property(mix, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


# ---------------------------------------------------------------- world, Visual V6
WORLD_FOLDER = "/Game/World"

TREE_WIND_CODE = """
// Visual V6: trees in the wind (MPC_World.Wind: direction xy, speed m/s, gust 0..1). The whole tree leans downwind and
// sways (more toward the crown and the limb tips: vertex colour R), each tree in its own phase (from its position); the
// leaves flutter on top (G: the card's phase). A learner can read the wind's strength and direction off the shore.
float3 inst = ObjPos * 0.01;
float phase = dot(inst.xy, float2(0.0131, 0.0173));
float speed = Wind.z * (1.0 + 0.5 * Wind.w);
float2 wdir = Wind.xy;
// W2: each tree reads the wind where it stands, from the water's far wind map (AWaterSurface binds it when the trees are
// in the world: WindFarRect.w = 1): the puffs crossing the shore, the lee, the shifts; the camera's wind beyond the map.
[branch] if (WindFarRect.w > 0.5)
{
    float2 e = abs(inst.xy - WindFarRect.xy) / (0.5 * WindFarRect.z);
    float a = 1.0 - smoothstep(0.75, 0.95, max(e.x, e.y));
    float4 w = WindFar.SampleLevel(WindFarSampler, inst.xy / WindFarRect.z, 0);
    wdir = normalize(lerp(Wind.xy, w.gb * 2.0 - 1.0, a) + float2(1e-4, 0.0));
    speed = lerp(speed, w.r * 20.0, a);
}
float s = VC.r;
float lean = speed * speed * 0.0022;
float osc = 0.6 * sin(T * (0.9 + 0.25 * sin(phase)) + phase) + 0.3 * sin(T * 2.3 + phase * 1.7);
float sway = lean * (0.75 + 0.35 * osc) * s;
float3 off = float3(wdir * sway, -0.25 * sway * s);
float flutter = Leaf * saturate(speed * 0.12) * 0.035;
off += float3(sin(T * 9.0 + VC.g * 40.0), cos(T * 7.3 + VC.g * 31.0), sin(T * 8.1 + VC.g * 17.0)) * flutter;
return off * 100.0;
"""


def world_collection():
    path = f"{WORLD_FOLDER}/MPC_World"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mpc = unreal.load_asset(path)
    else:
        mpc = ASSETS.create_asset("MPC_World", WORLD_FOLDER, unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
        p = unreal.CollectionVectorParameter()
        p.set_editor_property("parameter_name", "Wind")
        p.set_editor_property("default_value", unreal.LinearColor(1, 0, 4, 0))
        mpc.set_editor_property("vector_parameters", [p])
    # Night (0 day .. 1 full night): lamps, lit windows and vehicle lights (Visual V6), set by ASailingEnvironment.
    scalars = list(mpc.get_editor_property("scalar_parameters"))
    # WaterZ (Graphics G2): the water surface's world height (cm), for the wet band along every shore.
    # Site (E1): the world's wear site, 0 lake / 1 bay / 2 Gulf (WearSiteFor), for the baked tiles that carry no seed.
    for name in ("Night", "WaterZ", "Site"):
        if not any(str(x.get_editor_property("parameter_name")) == name for x in scalars):
            n = unreal.CollectionScalarParameter()
            n.set_editor_property("parameter_name", name)
            n.set_editor_property("default_value", 0.0)
            scalars.append(n)
    mpc.set_editor_property("scalar_parameters", scalars)
    unreal.EditorAssetLibrary.save_loaded_asset(mpc)
    return mpc


def import_texture(src, folder, srgb=True):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    ASSETS.import_asset_tasks([task])
    tex = unreal.load_asset(f"{folder}/{os.path.splitext(os.path.basename(src))[0]}")
    tex.set_editor_property("srgb", srgb)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return tex


def tree_wind(mat, leaf, x=-1200, y=600):
    mpc = world_collection()
    wind = node(mat, unreal.MaterialExpressionCollectionParameter, x, y, collection=mpc, parameter_name="Wind")
    vc = node(mat, unreal.MaterialExpressionVertexColor, x, y + 100)
    obj = node(mat, unreal.MaterialExpressionObjectPositionWS, x, y + 200)
    t = node(mat, unreal.MaterialExpressionTime, x, y + 300)
    lf = node(mat, unreal.MaterialExpressionConstant, x, y + 400, r=1.0 if leaf else 0.0)
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    far_tex = node(mat, unreal.MaterialExpressionTextureObjectParameter, x, y + 500, parameter_name="WindFar", texture=white)
    far_rect = vector(mat, "WindFarRect", (0, 0, 16000, 0), x, y + 600)
    c = custom(mat, TREE_WIND_CODE, ["VC", "ObjPos", "Wind", "T", "Leaf", "WindFar", "WindFarRect"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, x + 400, y)
    connect(far_tex, "", c, "WindFar")
    connect(far_rect, "RGBA", c, "WindFarRect")
    connect(vc, "", c, "VC")
    connect(obj, "", c, "ObjPos")
    connect(wind, "", c, "Wind")
    connect(t, "", c, "T")
    connect(lf, "", c, "Leaf")
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mat.set_editor_property("max_world_position_offset_displacement", 120.0)


def world_material(name):
    path = f"{WORLD_FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset(name, WORLD_FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    mat.set_editor_property("used_with_nanite", True)
    return mat


def build_trees_materials():
    """M_TreeLeaves / M_TreeBark (Visual V6): leaf cards cut from the atlas (two-sided foliage, lit through), bark, wind."""
    import os as _os
    atlas_src = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "Artifacts", "models", "world", "T_LeafAtlas.png")
    # The PC has no venv to draw the atlas (make-content.sh does): keep the imported one when there is no fresh PNG.
    atlas = import_texture(atlas_src, WORLD_FOLDER) if _os.path.exists(atlas_src) else unreal.load_asset(f"{WORLD_FOLDER}/T_LeafAtlas")
    leaves = world_material("M_TreeLeaves")
    leaves.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    leaves.set_editor_property("two_sided", True)
    leaves.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    tex = node(leaves, unreal.MaterialExpressionTextureSample, -800, 0, texture=atlas)
    vc = node(leaves, unreal.MaterialExpressionVertexColor, -800, 250)
    code = """
// Each card a little different: yellower, darker, bluer (B: the card's tint); the crown's sunny outside paler.
float3 c = Tex.rgb;
float t = VC.b;
c *= lerp(float3(0.82, 0.86, 0.78), float3(1.15, 1.1, 0.9), t);
c = lerp(c, c * float3(1.15, 1.08, 0.85), VC.r * 0.35);
return c;
"""
    tint = custom(leaves, code, ["Tex", "VC"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -500, 0)
    connect(tex, "RGB", tint, "Tex")
    connect(vc, "", tint, "VC")
    sss = node(leaves, unreal.MaterialExpressionMultiply, -300, 150)
    k = node(leaves, unreal.MaterialExpressionConstant3Vector, -500, 200, constant=unreal.LinearColor(0.55, 0.65, 0.3, 1))
    connect(tint, "", sss, "A")
    connect(k, "", sss, "B")
    rough = node(leaves, unreal.MaterialExpressionConstant, -300, 300, r=0.62)
    MEL.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(sss, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    MEL.connect_material_property(tex, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    tree_wind(leaves, True)
    MEL.recompile_material(leaves)
    unreal.EditorAssetLibrary.save_loaded_asset(leaves)

    # The distant crowns: opaque, leafy in colour and shading (dappled by world-space noise), swaying with the rest.
    crown = world_material("M_TreeCrown")
    wp = node(crown, unreal.MaterialExpressionWorldPosition, -900, 0)
    vc2 = node(crown, unreal.MaterialExpressionVertexColor, -900, 150)
    code = """
float3 p = WP * 0.01;
float n = frac(sin(dot(floor(p * 1.7), float3(12.9898, 78.233, 37.719))) * 43758.5453);
float m = 0.5 + 0.5 * sin(p.x * 2.1 + sin(p.y * 1.7) * 2.0) * sin(p.y * 2.3 + p.z * 1.9);
float3 c = lerp(float3(0.045, 0.085, 0.03), float3(0.10, 0.16, 0.06), m * 0.6 + n * 0.4);
// Graphics G8 (round 8: "trees are too round"): the blobs were lit as the smooth spheres they are, a bright top shading
// round to a dark underside. A crown is leaf clumps facing every way: the normal is the facet's (position derivatives:
// VertexNormalWS isn't world space on Nanite instances here) bent hard toward a clump field of two scales, and the
// clumps' hollows darker. A near tree's core (vertex alpha 0) is its deep inside, darker still and lit mostly by the
// clump field, so it reads as shade between the cards rather than a ball behind them.
float3 gn = normalize(cross(ddy(p), ddx(p)));
gn = dot(gn, V) < 0.0 ? -gn : gn;
float3 j = sin(p * float3(5.3, 4.7, 6.1) + sin(p.yzx * 3.1) * 1.7) + 0.6 * sin(p.zxy * float3(13.1, 11.7, 12.3) + sin(p * 7.3) * 1.3);
float hollow = saturate(0.5 + 0.35 * (j.x + j.y + j.z) / 2.4);
Nrm = normalize(lerp(gn, normalize(j + float3(0.0, 0.0, 0.9)), lerp(0.85, 0.6, VA)));
return c * lerp(0.85, 1.15, VC.b) * lerp(0.32, 1.0, VA) * lerp(0.6, 1.1, hollow);
"""
    cc = custom(crown, code, ["WP", "VC", "VA", "V"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -600, 0,
                extra_outputs=[("Nrm", unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    connect(wp, "", cc, "WP")
    connect(vc2, "", cc, "VC")
    connect(vc2, "A", cc, "VA")
    connect(node(crown, unreal.MaterialExpressionCameraVectorWS, -900, 300), "", cc, "V")
    crown.set_editor_property("tangent_space_normal", False)
    MEL.connect_material_property(cc, "Nrm", unreal.MaterialProperty.MP_NORMAL)
    rr = node(crown, unreal.MaterialExpressionConstant, -300, 200, r=0.75)
    MEL.connect_material_property(cc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rr, "", unreal.MaterialProperty.MP_ROUGHNESS)
    tree_wind(crown, False)
    MEL.recompile_material(crown)
    unreal.EditorAssetLibrary.save_loaded_asset(crown)

    bark = world_material("M_TreeBark")
    uv = node(bark, unreal.MaterialExpressionTextureCoordinate, -800, 0)
    code = """
// Grey-brown bark with vertical furrows and lichen.
float f = 0.5 + 0.5 * sin(UV.x * 6.2832 * 7.0 + sin(UV.y * 9.0) * 1.5);
float n = frac(sin(dot(floor(UV * float2(24.0, 6.0)), float2(12.9898, 78.233))) * 43758.5453);
float3 c = lerp(float3(0.16, 0.13, 0.11), float3(0.30, 0.27, 0.23), f * 0.7 + n * 0.3);
c = lerp(c, float3(0.35, 0.38, 0.30), step(0.92, n) * 0.6);
return c;
"""
    bc = custom(bark, code, ["UV"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -500, 0)
    connect(uv, "", bc, "UV")
    r = node(bark, unreal.MaterialExpressionConstant, -300, 200, r=0.85)
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    tree_wind(bark, False)
    MEL.recompile_material(bark)
    unreal.EditorAssetLibrary.save_loaded_asset(bark)


WORLD_SURFACE_CODE = """
// Visual V6: one surface for the generated world (docks, buildings, bridges), set by instance parameters. UV is in
// metres along the part. Pattern: 0 plain, 1 deck planks, 2 shingles, 3 lap siding, 4 concrete, 5 weathered metal,
// 6 asphalt with lane markings (U across from the left edge, V along). Night lights the windows and anything with Glow.
float2 uv = UV;
float3 c = Color.rgb;
float r = Rough;
float n = frac(sin(dot(floor(uv * float2(7.0, 7.0)), float2(12.9898, 78.233))) * 43758.5453);
// Smooth value noise (blotches about 1.4 m across), for concrete and weathered steel.
float2 p = uv * 0.7;
float2 i0 = floor(p), f0 = smoothstep(0.0, 1.0, frac(p));
float h00 = frac(sin(dot(i0, float2(12.99, 78.23))) * 43758.5), h10 = frac(sin(dot(i0 + float2(1, 0), float2(12.99, 78.23))) * 43758.5);
float h01 = frac(sin(dot(i0 + float2(0, 1), float2(12.99, 78.23))) * 43758.5), h11 = frac(sin(dot(i0 + float2(1, 1), float2(12.99, 78.23))) * 43758.5);
float blot = lerp(lerp(h00, h10, f0.x), lerp(h01, h11, f0.x), f0.y);
float3 bump = float3(0, 0, 0);  // tangent-space slope (x along U, y along V) from the patterns that have relief
// Environment E1 (docs/environment-1): the structure's seeded wear (FWearSeed), per instance on the private docks and
// boathouses (custom data 10-15). The baked kit tiles are one mesh per tile with no instance data, so they hash it per
// 4 m of world plan, with the README's ranges (Fixed water contact) and the world's site from MPC_World.
float2 wcell = floor(WP.xy / 400.0);
float wh1 = frac(sin(dot(wcell, float2(12.9898, 78.233))) * 43758.5453);
float wh2 = frac(sin(dot(wcell, float2(39.346, 11.135))) * 43758.5453);
float wh3 = frac(sin(dot(wcell, float2(73.156, 52.235))) * 43758.5453);
bool seeded = CD10 >= 0.0;
float site = seeded ? CD14 : Site;
float age = seeded ? CD10 : 25.0 * wh1;
float care = seeded ? saturate(CD11) : saturate(0.25 + 0.75 * wh2 - 0.3 * age / 25.0);
float sun = seeded ? saturate(CD12) : 0.5 + 0.3 * (wh3 - 0.5);
float2 wetRange = site < 0.5 ? float2(0.3, 0.9) : (site < 1.5 ? float2(0.5, 1.0) : float2(0.9, 1.6));
float wetM = seeded ? max(CD13, 0.0) : lerp(wetRange.x, wetRange.y, frac(wh1 * 7.31));
float variant = seeded ? CD15 : floor(frac(wh2 * 13.7) * 8.0);
float salt = step(0.5, site);
float aged = saturate(age / 25.0);
float zw = WP.z * 0.01;  // metres above the datum (the pool, or MLLW): fixed structures' bands span the level's range
// Variant: each structure's own batch of timber or paint, plus or minus 4%.
c *= 1.0 + 0.04 * (frac(variant * 0.618 + 0.31) * 2.0 - 1.0);
if (Pattern > 0.5 && Pattern < 1.5)
{
    // Graphics G8 (round 8: "the pier elements lack textures and details"): weathered wooden decking. 14 cm boards with
    // 1 cm gaps, cut to lengths with staggered butt joints; each board its own silver-grey to brown; grain lines that
    // wander, checks (drying splits) along it, knots, rows of screws over the joists every 40 cm, dirt in the gaps and
    // at the ends, and relief at the gaps.
    float vb = uv.y / 0.15;
    float board = floor(vb), fv = frac(vb);
    float b = frac(sin(board * 91.7) * 4375.5);
    float len = 2.4 + 1.2 * frac(b * 7.1);
    float ux = uv.x / len + b * 3.7;
    float piece = floor(ux), fu = frac(ux);
    float pb = frac(sin(board * 91.7 + piece * 37.3) * 4375.5);
    float gap = smoothstep(0.915, 0.935, fv);
    float buttMask = 1.0 - smoothstep(0.0, 0.004 / len, min(fu, 1.0 - fu));
    // Grain: fine lines along the board, bent by a slow wobble, and a few darker late-wood lines.
    float wob = sin(uv.x * 1.3 + pb * 20.0) * 0.35 + sin(uv.x * 4.1 + pb * 7.0) * 0.08;
    float g1 = sin((fv + wob) * 62.8 + pb * 11.0);
    float g2 = sin((fv + wob * 1.7) * 151.0 + pb * 5.0);
    float grain = 0.5 + 0.3 * g1 + 0.2 * g2;
    float late = smoothstep(0.82, 0.98, abs(sin((fv + wob) * 25.1 + pb * 3.0)));
    // Checks: thin dark splits along the grain, a few per board, of their own length.
    float ck = frac(sin(floor(uv.x / 0.7 + pb * 5.0) * 17.1 + board * 3.3) * 4375.5);
    float ckLine = exp(-pow((fv - (0.2 + 0.6 * frac(ck * 13.0))) * 140.0, 2.0)) * step(0.55, ck) * smoothstep(0.0, 0.3, frac(uv.x / 0.7 + pb * 5.0)) * (1.0 - smoothstep(0.6, 0.9, frac(uv.x / 0.7 + pb * 5.0)));
    // Knots: dark ovals stretched along the grain.
    float2 kq = float2(uv.x / 0.55, fv);
    float kh = frac(sin(floor(kq.x) * 61.7 + board * 12.9) * 4375.5);
    float knot = step(0.8, kh) * (1.0 - smoothstep(0.03, 0.09, length((float2(frac(kq.x) - 0.5, (fv - 0.25 - 0.5 * frac(kh * 9.0)) * 3.0)) * float2(0.55, 0.25))));
    // Screws over the joists: pairs across each board, 40 cm apart along it.
    float jx = frac(uv.x / 0.4);
    float scr = (1.0 - smoothstep(0.004, 0.009, length(float2((jx - 0.5) * 0.4, (abs(fv - 0.45) - 0.27) * 0.15))));
    // The colour: weathered cedar and pine go silver; some boards are newer (browner), some darker with mildew.
    float3 silver = float3(0.50, 0.48, 0.44), brown = float3(0.46, 0.33, 0.21), dark = float3(0.27, 0.25, 0.22);
    // E1: timber silvers within a few years, faster facing the sun; an old dock that is kept has had boards replaced
    // (still brown), a neglected one goes dark with mildew where the sun doesn't reach.
    float silvering = saturate(age / 4.0) * (0.6 + 0.4 * sun);
    float replaced = step(1.0 - (0.06 + 0.3 * aged * care), frac(pb * 5.3 + 0.17));
    float3 wood = lerp(brown, silver, silvering * (1.0 - 0.75 * replaced) * (1.0 - 0.6 * saturate(pb * 1.6 - 0.9)));
    wood = lerp(wood, dark, saturate(saturate(blot - 0.55) * 0.9 + 0.25 * step(0.85, pb) + 0.45 * (1.0 - sun) * (1.0 - care) * aged));
    wood *= 0.88 + 0.16 * grain - 0.14 * late;
    wood *= (c / max(dot(Color.rgb, float3(0.3, 0.59, 0.11)), 0.05)) * 0.45 + 0.55;
    wood = lerp(wood, wood * 0.35, saturate(ckLine * 0.9 + knot * 0.7));
    wood = lerp(wood, float3(0.12, 0.12, 0.12), scr * 0.8);
    // Dirt and wet rot creep in from the gaps and the board ends.
    float edgeDirt = saturate(1.0 - min(fv, 1.0 - fv) / 0.12) * 0.25 + buttMask * 0.5;
    c = lerp(wood * (1.0 - 0.3 * edgeDirt), float3(0.04, 0.035, 0.03), max(gap, buttMask));
    r = saturate(r + 0.08 * (1.0 - grain) + 0.1 * gap);
    // Relief: boards cupped a little, eased edges, the grain raised by the weather.
    float cup = (fv - 0.45) * 0.25;
    float ease = smoothstep(0.78, 0.86, fv) - (1.0 - smoothstep(0.0, 0.05, fv));
    bump = float3(0.02 * g2 * 0.3, -cup - 0.6 * ease + 0.05 * g1 + 0.3 * ckLine, 0);
}
else if (Pattern > 8.5 && Pattern < 9.5)
{
    // Graphics G8: treated pine and creosoted pilings (U around in metres, V up from the base): long vertical grain and
    // drying cracks, the wood going grey above, dark and stained in the tide/wave band, green-black algae and mud below.
    float a = uv.x, z = WP.z * 0.01;
    float colH = frac(sin(floor(a / 0.9 + 0.5) * 7.3 + floor(WP.x * 0.005) * 1.7 + floor(WP.y * 0.005) * 3.1) * 4375.5);
    float wob = sin(z * 0.9 + colH * 20.0) * 0.04;
    float grain = 0.5 + 0.3 * sin((a + wob) * 140.0 + colH * 9.0) + 0.2 * sin((a + wob * 2.0) * 330.0);
    float crack = exp(-pow((frac((a + wob) * 6.3 + colH) - 0.5) * 30.0, 2.0)) * step(0.35, frac(colH * 5.3 + floor((a + wob) * 6.3) * 0.37));
    crack *= 0.6 + 0.4 * sin(z * 2.3 + colH * 9.0);
    // Silver-grey where the sun and rain have had it, the treated brown showing through in places.
    float3 wood = lerp(float3(0.40, 0.38, 0.34), float3(0.33, 0.24, 0.15), colH * 0.6 * (0.6 + 0.4 * blot) * (1.0 - 0.6 * saturate(age / 6.0) * sun));
    wood *= 0.72 + 0.42 * grain;
    crack *= 0.6 + 0.8 * (1.0 - care) * (0.4 + 0.6 * aged);
    wood = lerp(wood, float3(0.05, 0.045, 0.04), saturate(crack * 0.85));
    // E1: the stain band reaches Wet metres up (the lake's drawdown ring, the bay's tide and splash, the Gulf's surf),
    // ragged around the piling.
    float bandTop = wetM * (0.85 + 0.15 * sin(a * 9.0 + colH * 20.0));
    float wet = 1.0 - smoothstep(bandTop * 0.45, bandTop, z);
    float under = 1.0 - smoothstep(-0.3, 0.05, z);     // below the water line: algae and mud
    wood = lerp(wood, wood * float3(0.55, 0.52, 0.48), wet * 0.7);
    // Below: fresh water grows green-black algae and mud; salt water a crust of barnacles and oysters, pale and rough,
    // thickest in the low band.
    float bq = frac(sin(dot(floor(float2(a, z) / 0.035), float2(12.99, 78.23))) * 43758.5);
    float barn = salt * (1.0 - smoothstep(-0.6, bandTop * 0.4, z)) * step(0.45 - 0.25 * aged, bq) * (0.6 + 0.4 * blot);
    wood = lerp(wood, float3(0.07, 0.085, 0.05) * (0.8 + 0.4 * blot), under * 0.9 * (1.0 - 0.5 * salt));
    wood = lerp(wood, float3(0.56, 0.54, 0.49) * (0.75 + 0.35 * bq), saturate(barn));
    c = wood;
    r = lerp(lerp(r, 0.55, wet * 0.6), 0.9, saturate(barn));
    bump = float3(0.25 * crack + 0.04 * sin((a + wob) * 140.0) + 0.3 * barn * (bq - 0.5), 0.3 * barn * (frac(bq * 7.0) - 0.5), 0);
}
else if (Pattern > 9.5 && Pattern < 10.5)
{
    // Graphics G8: dock boxes and power pedestals (moulded white polyethylene and fibreglass): chalky, yellowed, with
    // grime collecting low down and green-grey mildew at the base, scuffed corners, and dark streaks run down from the lid.
    float lane = floor(uv.x / 0.09);
    float hl = frac(sin(lane * 41.3) * 4375.5);
    float runs = step(0.6, hl) * exp(-pow((frac(uv.x / 0.09) - 0.5) * 6.0, 2.0)) * saturate(uv.y / 0.6);
    // E1: polyethylene yellows and chalks with years in the sun; a neglected box greens at the base.
    c *= lerp(float3(1.0, 1.0, 1.0), float3(1.0, 0.95, 0.82), aged * (0.4 + 0.6 * sun));
    c *= float3(0.95, 0.92, 0.84) * (0.86 + 0.2 * blot);
    c = lerp(c, c * float3(0.5, 0.52, 0.45), saturate(saturate(1.0 - uv.y / 0.3) * (0.55 + 0.45 * (1.0 - care))));
    c = lerp(c, c * 0.6, runs * 0.7);
    r = saturate(r + 0.2 * blot);
}
else if (Pattern > 1.5 && Pattern < 2.5)
{
    float row = floor(uv.y / 0.14);
    float tab = frac(uv.x / 0.33 + 0.5 * fmod(row, 2.0));
    float b = frac(sin(row * 31.1 + floor(uv.x / 0.33) * 17.3) * 4375.5);
    c *= (0.85 + 0.2 * b) * (1.0 - 0.35 * step(0.96, tab)) * (1.0 - 0.3 * step(0.9, frac(uv.y / 0.14)));
}
else if (Pattern > 2.5 && Pattern < 3.5)
{
    float lap = frac(uv.y / 0.18);
    c *= 0.9 + 0.12 * lap;
    // Windows: a band at sill height, panes every 2.4 m (only on walls tall enough).
    float wx = frac(uv.x / 2.4), wy = uv.y;
    float win = step(0.25, wx) * step(wx, 0.75) * step(0.9, wy) * step(wy, 2.3) * Windows;
    c = lerp(c, float3(0.04, 0.05, 0.06), win);
    r = lerp(r, 0.08, win);
}
else if (Pattern > 3.5 && Pattern < 4.5)
{
    // Concrete: smooth blotches, darker run-off streaks down from the top, form-tie lines every 1.2 m.
    float streak = frac(sin(floor(uv.x * 3.0) * 91.3) * 4375.5) * saturate(1.0 - frac(uv.y * 0.25));
    float form = 1.0 - 0.06 * step(0.97, frac(uv.y / 1.2));
    c *= (0.86 + 0.22 * blot) * (1.0 - 0.12 * streak) * form * (0.97 + 0.06 * n);
    // E1: bulkheads and bridge piers carry the water's ring up to Wet metres: dark and green on the lake, darker with a
    // pale salt line at its top on salt water. Buildings stand well above it.
    float ringTop = wetM * (0.9 + 0.1 * sin(WP.x * 0.013 + WP.y * 0.017));
    float ringK = (1.0 - smoothstep(ringTop - 0.08, ringTop, zw)) * smoothstep(-1.5, -0.2, zw) * (0.55 + 0.45 * blot) * (0.6 + 0.4 * aged);
    c = lerp(c, c * lerp(float3(0.55, 0.6, 0.5), float3(0.5, 0.48, 0.45), salt), ringK);
    c = lerp(c, float3(0.78, 0.77, 0.73), salt * exp(-pow((zw - ringTop + 0.03) / 0.03, 2.0)) * 0.6 * (0.6 + 0.4 * aged));
}
else if (Pattern > 4.5 && Pattern < 5.5)
{
    // Weathered painted steel: blotchy fading, and rust weeping down in streaks from seams.
    float lane = floor(uv.x * 1.5);
    float hl = frac(sin(lane * 91.7) * 4375.5);
    // E1: more seams weep with age and near salt, and the paint fades where it faces the sun.
    float weep = step(0.6 - 0.2 * salt - 0.2 * aged * (1.0 - care), hl) * saturate(1.0 - frac(uv.y * 0.35 + hl)) * 0.8;
    c *= (0.9 + 0.2 * blot) * (1.0 + 0.12 * aged * sun);
    c = lerp(c, float3(0.30, 0.14, 0.06), saturate((weep + 0.25 * saturate(blot - 0.6)) * (0.7 + 0.5 * aged)) * 0.6);
}
else if (Pattern > 7.5)
{
    // Graphics G6: a ship's topsides (UV: x along the hull; the FBX import flips V, so height above the waterline is 1 - y).
    // Rust weeps from the deck edge and the scuppers in streaks of their own lengths; fender and tug scrapes along the
    // waterline band; blotchy fading.
    uv.y = 1.0 - uv.y;
    float lane = floor(uv.x * 0.9);
    float hl = frac(sin(lane * 91.7) * 4375.5), hl2 = frac(sin(lane * 17.3 + 7.0) * 4375.5);
    float src = 10.4 + 3.0 * hl2;
    float len = 3.0 + 8.0 * hl;
    float wx = frac(uv.x * 0.9);
    float thin = exp(-pow((wx - 0.5) * (9.0 + 12.0 * hl2), 2.0));
    float below = src - uv.y;
    float weep = step(0.35, hl) * thin * saturate(below / 0.3) * pow(saturate(1.0 - below / len), 0.7);
    // The deck edge itself: a band of rust and chipped paint where the mooring lines and the sea work it.
    float edge = saturate(1.0 - abs(uv.y - (src + 0.3)) / 0.6) * (0.4 + 0.6 * blot);
    c *= 0.86 + 0.24 * blot;
    c = lerp(c, float3(0.32, 0.14, 0.05), saturate(weep * 0.9 + 0.5 * edge + 0.15 * saturate(blot - 0.7)));
    float band = saturate(1.0 - abs(uv.y - 2.0) / 1.6) * step(0.75, frac(sin(floor(uv.x * 0.12) * 12.1) * 4375.5));
    c = lerp(c, float3(0.22, 0.20, 0.18), band * 0.6 * blot);
    r = lerp(r, 0.75, weep);
}
else if (Pattern > 5.5)
{
    // Asphalt: aggregate speckle, oil down the lane centres, a solid edge line and 3 m dashes every 12 m between lanes.
    c *= 0.85 + 0.3 * n;
    float lane = frac((uv.x - 0.6) / 3.6);
    c *= 1.0 - 0.15 * exp(-pow((lane - 0.5) * 6.0, 2.0));
    float edge = step(0.3, uv.x) * step(uv.x, 0.45);
    float dash = step(abs(lane - 0.0) * 3.6, 0.07) * step(frac(uv.y / 12.0), 0.25) * step(1.0, uv.x);
    c = lerp(c, float3(0.75, 0.74, 0.70), saturate(edge + dash));
}
else if (Pattern > 6.5)
{
    // Riprap: blocks about a metre across (jittered cells), each its own shade of granite or limestone, dark gaps between,
    // darker and greener toward the water (UV.y 0 at the toe).
    float2 q = uv * 1.1;
    float2 cell = floor(q);
    float best = 9.0, second = 9.0;
    float shade = 0.0;
    for (int j = -1; j <= 1; j++)
        for (int i = -1; i <= 1; i++)
        {
            float2 g = cell + float2(i, j);
            float2 o = frac(sin(float2(dot(g, float2(127.1, 311.7)), dot(g, float2(269.5, 183.3)))) * 43758.5);
            float d = length(g + o - q);
            if (d < best) { second = best; best = d; shade = frac(o.x * 7.3 + o.y * 3.1); }
            else if (d < second) second = d;
        }
    float gap = 1.0 - smoothstep(0.02, 0.12, second - best);
    c *= (0.7 + 0.5 * shade) * (0.9 + 0.2 * blot);
    c = lerp(c, c * 0.25, gap);
    c = lerp(c * float3(0.55, 0.6, 0.45), c, saturate(uv.y / 2.5));
}
Out = r;
Emit = float3(0, 0, 0);
if (Pattern > 2.5 && Pattern < 3.5)
{
    // Some windows lit at night, warm.
    float wx = frac(uv.x / 2.4), wy = uv.y;
    float win = step(0.25, wx) * step(wx, 0.75) * step(0.9, wy) * step(wy, 2.3) * Windows;
    float lit = step(0.45, frac(sin(floor(uv.x / 2.4) * 37.7) * 4375.5));
    Emit = float3(1.0, 0.72, 0.42) * 6.0 * win * lit * Night;
}
Emit += c * Glow * Night;
Nrm = normalize(float3(-bump.x, -bump.y, 1.0));
return c;
"""


def build_world_surface():
    mat = world_material("M_WorldSurface")
    mat.set_editor_property("used_with_static_lighting", False)
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -900, 0)
    color = vector(mat, "Color", (0.6, 0.6, 0.58, 1), -900, 100)
    rough = scalar(mat, "Roughness", 0.8, -900, 200)
    pattern = scalar(mat, "Pattern", 0.0, -900, 300)
    windows = scalar(mat, "Windows", 0.0, -900, 400)
    metal = scalar(mat, "Metallic", 0.0, -900, 500)
    glow = scalar(mat, "Glow", 0.0, -900, 600)
    night = node(mat, unreal.MaterialExpressionCollectionParameter, -900, 700)
    night.set_editor_property("collection", world_collection())
    night.set_editor_property("parameter_name", "Night")
    F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    c = custom(mat, WORLD_SURFACE_CODE, ["UV", "Color", "Rough", "Pattern", "Windows", "Glow", "Night", "WP", "Site"] + [f"CD{k}" for k in range(10, 16)],
               unreal.CustomMaterialOutputType.CMOT_FLOAT3, -500, 100,
               extra_outputs=[("Out", F1), ("Emit", unreal.CustomMaterialOutputType.CMOT_FLOAT3), ("Nrm", unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    connect(node(mat, unreal.MaterialExpressionWorldPosition, -900, 800), "", c, "WP")
    connect(glow, "", c, "Glow")
    connect(night, "", c, "Night")
    site = node(mat, unreal.MaterialExpressionCollectionParameter, -900, 900)
    site.set_editor_property("collection", world_collection())
    site.set_editor_property("parameter_name", "Site")
    connect(site, "", c, "Site")
    for k in range(10, 16):   # E1's wear seed (FWearSeed, docs/environment-1); -1 = none: the baked tiles hash their own
        connect(node(mat, unreal.MaterialExpressionPerInstanceCustomData, -1100, 1000 + 60 * k, data_index=k, const_default_value=-1.0), "", c, f"CD{k}")
    connect(uv, "", c, "UV")
    connect(color, "RGBA", c, "Color")
    connect(rough, "", c, "Rough")
    connect(pattern, "", c, "Pattern")
    connect(windows, "", c, "Windows")
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Out", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(c, "Emit", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(c, "Nrm", unreal.MaterialProperty.MP_NORMAL)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    # Instances for the world kit's static meshes (slot name -> MI_World_<slot>); updated in place like the boat library.
    for slot, (col, rough, pattern, windows, metallic, *rest) in WORLD_LIBRARY.items():
        name = f"MI_World_{slot}"
        path = f"{WORLD_FOLDER}/{name}"
        mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
            ASSETS.create_asset(name, WORLD_FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, mat)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(col[0], col[1], col[2], 1.0))
        MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        MEL.set_material_instance_scalar_parameter_value(mi, "Pattern", pattern)
        MEL.set_material_instance_scalar_parameter_value(mi, "Windows", windows)
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", metallic)
        MEL.set_material_instance_scalar_parameter_value(mi, "Glow", rest[0] if rest else 0.0)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)


def build_vehicle_paint():
    """The bridge traffic's paint: colour per instance (custom data 0..2, set by ABridgesActor), glossy clear-coated."""
    mat = world_material("M_VehiclePaint")
    chans = [node(mat, unreal.MaterialExpressionPerInstanceCustomData, -900, i * 120, data_index=i, const_default_value=0.5) for i in range(3)]
    rg = node(mat, unreal.MaterialExpressionAppendVector, -650, 60)
    connect(chans[0], "", rg, "A")
    connect(chans[1], "", rg, "B")
    rgb = node(mat, unreal.MaterialExpressionAppendVector, -450, 120)
    connect(rg, "", rgb, "A")
    connect(chans[2], "", rgb, "B")
    MEL.connect_material_property(rgb, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(scalar(mat, "Roughness", 0.28, -450, 300), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(scalar(mat, "Metallic", 0.35, -450, 400), "", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    # Containers on the ship: the same per-instance colour, matte weathered paint.
    path = f"{WORLD_FOLDER}/MI_World_ContainerPaint"
    mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
        ASSETS.create_asset("MI_World_ContainerPaint", WORLD_FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, mat)
    MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", 0.7)
    MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", 0.15)
    MEL.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mi)


NAVAID_CODE = """
// Visual V6: an aid's paint (colour per instance) weathered the way steel buoys and treated piles are: rust weeping in
// streaks down from seams and fittings, sun-faded chalky paint on top, and a band of green-brown growth from the waterline
// up (with slime below it). LP: local position (cm, origin at the waterline or the pile's foot); UV.x runs round the part.
float z = LP.z / 100.0;
float3 c = Col;
float r = 0.55;
float lane = floor(UV.x * 5.0);
float h = frac(sin(lane * 91.7 + 3.1) * 4375.5);
float run = saturate(1.0 - frac(z * 0.6 + h)) * step(0.55, h) * saturate(z * 2.0);
c = lerp(c, float3(0.28, 0.13, 0.05), run * 0.55);
c = lerp(c, c * 1.15 + 0.04, saturate((z - 1.0) * 0.3));
float edge = 0.14 + 0.03 * sin(UV.x * 9.0 + h * 6.0);
float growth = 1.0 - smoothstep(edge - 0.04, edge, z);
c = lerp(c, float3(0.07, 0.09, 0.04), growth * 0.85);
r = lerp(r, 0.35, growth);
Out = r;
return c;
"""


def build_navaid_paint():
    mat = world_material("M_NavaidPaint")
    chans = [node(mat, unreal.MaterialExpressionPerInstanceCustomData, -1100, i * 120, data_index=i, const_default_value=0.5) for i in range(3)]
    rg = node(mat, unreal.MaterialExpressionAppendVector, -850, 60)
    connect(chans[0], "", rg, "A")
    connect(chans[1], "", rg, "B")
    rgb = node(mat, unreal.MaterialExpressionAppendVector, -650, 120)
    connect(rg, "", rgb, "A")
    connect(chans[2], "", rgb, "B")
    lp = node(mat, unreal.MaterialExpressionLocalPosition, -650, 300)
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -650, 400)
    F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    c = custom(mat, NAVAID_CODE, ["Col", "LP", "UV"], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -400, 200, extra_outputs=[("Out", F1)])
    connect(rgb, "", c, "Col")
    connect(lp, "", c, "LP")
    connect(uv, "", c, "UV")
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Out", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)


HOUSE_WALL_CODE = """
// Visual V6: the walls of the OSM buildings (Tools/blender/build_houses.py archetypes scaled to each footprint). Per instance:
// D0 wall colour, D1 (pattern 0 brick, 1 lap siding, 2 stucco; height m; seed). Windows are laid out in world space so
// they keep their size: storeys of 2.9 m, a window every 3.2 m along the wall, some lit at night. The face normal comes from
// the position's screen derivatives (the vertex-normal input is not in world space on these Nanite instances); the
// ray-tracing hit and compute shaders have none, so they take the vertex normal.
#if RAYHITGROUPSHADER || COMPUTESHADER
float3 n = normalize(N);
#else
float3 n = normalize(cross(ddy(WP), ddx(WP)));
#endif
float2 t = normalize(float2(-n.y, n.x) + 1e-4);
float u = dot(WP.xy, t) / 100.0;
float3 c = D0;
float pat = D1.x, height = D1.y, seed = D1.z;
// Graphics G2: pattern + 10 = a near house with modelled windows (Tools/blender/build_houses_near.py): no painted ones.
float modelled = step(9.5, pat);
pat -= 10.0 * modelled;
// G: the instance's ground height (m, custom data 9).
float v = WP.z / 100.0 - G;
float r = 0.8;
if (pat < 0.5)
{
    float row = floor(v / 0.075);
    float bu = frac(u / 0.22 + 0.5 * fmod(row, 2.0));
    float mortar = max(step(0.88, frac(v / 0.075)), step(0.95, bu));
    float b = frac(sin(row * 17.1 + floor(u / 0.22 + 0.5 * fmod(row, 2.0)) * 31.7) * 4375.5);
    c *= (0.85 + 0.25 * b);
    c = lerp(c, float3(0.55, 0.53, 0.5), mortar * 0.8);
}
else if (pat < 1.5)
{
    c *= 0.88 + 0.14 * frac(v / 0.17);
    r = 0.6;
}
else
{
    c *= 0.94 + 0.08 * frac(sin(dot(floor(float2(u, v) * 3.0), float2(12.9, 78.2))) * 43758.5);
}
float wu = frac(u / 3.2 + seed);
float wv = frac(v / 2.9);
float win = step(0.25, wu) * step(wu, 0.6) * step(0.3, wv) * step(wv, 0.76) * step(floor(v / 2.9) * 2.9 + 2.3, height * 0.62) * step(0.4, v) * step(abs(n.z), 0.5);
win *= 1.0 - modelled;
float3 glass = float3(0.03, 0.035, 0.04);
c = lerp(c, glass, win);
r = lerp(r, 0.05, win);
float lit = step(0.55, frac(sin(floor(u / 3.2 + seed) * 37.7 + floor(v / 2.9) * 11.3 + seed * 91.0) * 4375.5));
Emit = float3(1.0, 0.7, 0.4) * 5.0 * win * lit * Night;
Out = r;
return c;
"""

HOUSE_ROOF_CODE = """
// Asphalt shingles in world space: courses every 14 cm up the roof, tabs 33 cm along, each tab its own shade.
// The face's normal from position derivatives (VertexNormalWS isn't world space on Nanite instances), except in the
// ray-tracing hit shaders and compute shaders (Lumen's card capture), which have no derivatives: without this guard the
// cooked game has no roof shader.
#if RAYHITGROUPSHADER || COMPUTESHADER
float3 n = normalize(N);
#else
float3 n = normalize(cross(ddy(WP), ddx(WP)));
#endif
float2 t = normalize(float2(-n.y, n.x) + 1e-4);
float u = dot(WP.xy, t) / 100.0;
float v = WP.z / 100.0 / max(0.25, 1.0 - abs(n.z)) * 0.6;
float row = floor(v / 0.14);
float tab = floor(u / 0.33 + 0.5 * fmod(row, 2.0));
float b = frac(sin(row * 31.1 + tab * 17.3) * 4375.5);
float3 c = D0 * (0.8 + 0.3 * b) * (1.0 - 0.3 * step(0.9, frac(v / 0.14)));  // D0: the roof colour (custom data 6-8)
return c;
"""


def build_house_materials():
    for name, code, chans in (("M_HouseWall", HOUSE_WALL_CODE, ((0, 1, 2), (3, 4, 5))), ("M_HouseRoof", HOUSE_ROOF_CODE, ((6, 7, 8),))):
        mat = world_material(name)
        ins = ["WP", "OP", "N"]
        c = custom(mat, code, ins + [f"D{k}" for k in range(len(chans))] + (["Night", "G"] if name == "M_HouseWall" else []),
                   unreal.CustomMaterialOutputType.CMOT_FLOAT3, -300, 100,
                   extra_outputs=[("Out", unreal.CustomMaterialOutputType.CMOT_FLOAT1), ("Emit", unreal.CustomMaterialOutputType.CMOT_FLOAT3)]
                   if name == "M_HouseWall" else [])
        connect(node(mat, unreal.MaterialExpressionWorldPosition, -900, 0), "", c, "WP")
        connect(node(mat, unreal.MaterialExpressionObjectPositionWS, -900, 80), "", c, "OP")
        connect(node(mat, unreal.MaterialExpressionVertexNormalWS, -900, 160), "", c, "N")
        for k, idx in enumerate(chans):
            d = [node(mat, unreal.MaterialExpressionPerInstanceCustomData, -1300, 260 + k * 300 + j * 90, data_index=i, const_default_value=0.5) for j, i in enumerate(idx)]
            ab = node(mat, unreal.MaterialExpressionAppendVector, -1100, 300 + k * 300)
            connect(d[0], "", ab, "A")
            connect(d[1], "", ab, "B")
            abc = node(mat, unreal.MaterialExpressionAppendVector, -950, 320 + k * 300)
            connect(ab, "", abc, "A")
            connect(d[2], "", abc, "B")
            connect(abc, "", c, f"D{k}")
        MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
        if name == "M_HouseWall":
            night = node(mat, unreal.MaterialExpressionCollectionParameter, -900, 900)
            night.set_editor_property("collection", world_collection())
            night.set_editor_property("parameter_name", "Night")
            connect(night, "", c, "Night")
            connect(node(mat, unreal.MaterialExpressionPerInstanceCustomData, -900, 1000, data_index=9, const_default_value=0.0), "", c, "G")
            MEL.connect_material_property(c, "Out", unreal.MaterialProperty.MP_ROUGHNESS)
            MEL.connect_material_property(c, "Emit", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        else:
            MEL.connect_material_property(scalar(mat, "Roughness", 0.85, -300, 300), "", unreal.MaterialProperty.MP_ROUGHNESS)
        MEL.recompile_material(mat)
        unreal.EditorAssetLibrary.save_loaded_asset(mat)


# ---------------------------------------------------------------- houses from the G2 footprints (Graphics G6)
# WorldKit's HouseWall and HouseRoof looks (HouseKit.cpp): the colour per vertex (sRGB bytes, undecoded by the vertex
# factory), the finish in its alpha, UV0 in metres (along the wall, height above the ground), UV1 the eave height and a
# seed (+2: windows painted, for the reduced-detail band and commercial blocks).
HOUSE_KIT_WALL_CODE = """
float3 c = pow(saturate(VC.rgb), 2.2);
float code = floor(VA * 255.0 + 0.5);
float u = UV.x, v = UV.y;
float eave = Tag.x, seed = frac(Tag.y), painted = step(1.5, Tag.y);
float r = 0.8;
float3 e = float3(0.0, 0.0, 0.0);
if (code < 0.5)
{
    // Brick: 7.5 cm courses, 22 cm bricks in running bond, each its own shade; grey mortar.
    float row = floor(v / 0.075);
    float bu = frac(u / 0.22 + 0.5 * fmod(row, 2.0));
    float mortar = max(step(0.88, frac(v / 0.075)), step(0.95, bu));
    float b = frac(sin(row * 17.1 + floor(u / 0.22 + 0.5 * fmod(row, 2.0)) * 31.7) * 4375.5);
    c *= 0.85 + 0.25 * b;
    c = lerp(c, float3(0.55, 0.53, 0.5), mortar * 0.8);
    r = 0.85;
}
else if (code < 1.5)
{
    // Lap siding: 17 cm boards, each lip throwing a thin shadow line.
    float f = frac(v / 0.17);
    c *= (0.9 + 0.08 * f) * lerp(0.62, 1.0, smoothstep(0.0, 0.06, f));
    r = 0.6;
}
else if (code < 2.5)
{
    // Stucco: a fine trowelled mottle.
    float2 g = floor(float2(u, v) * 3.0);
    c *= 0.93 + 0.09 * frac(sin(dot(g, float2(12.9, 78.2))) * 43758.5);
    r = 0.9;
}
else if (code < 3.5)
{
    // Window glass: dark, glossy; some lit at night (warm), by window.
    c = float3(0.018, 0.02, 0.024);
    r = 0.04;
    // Graphics G8 (round 8: "buildings ... not detailed"): white vinyl frames and muntins (sashes 0.9 m wide, a meeting
    // rail at 0.75 m), blinds half drawn in some, and the sky's brighter reflection in the upper panes.
    float fu = frac(u / 0.9), fv2 = frac(v / 1.5);
    float frame = max(1.0 - smoothstep(0.03, 0.05, min(fu, 1.0 - fu)), 1.0 - smoothstep(0.03, 0.05, min(fv2, 1.0 - fv2)));
    frame = max(frame, 1.0 - smoothstep(0.015, 0.03, abs(fv2 - 0.5)));
    float blind = step(0.5, frac(sin(floor(u / 0.9) * 13.7 + floor(v / 1.5) * 7.9 + WP.x * 0.0001) * 4375.5)) * step(1.0 - 0.6 * frac(sin(floor(u / 0.9) * 3.1) * 437.5), fv2);
    c = lerp(c, float3(0.42, 0.40, 0.36), blind * 0.6);
    c += float3(0.03, 0.04, 0.05) * smoothstep(0.3, 1.0, fv2);
    c = lerp(c, float3(0.80, 0.80, 0.77), frame);
    r = lerp(r, 0.5, frame);
    float lit = step(0.55, frac(sin(dot(floor(WP.xy / 150.0), float2(37.7, 11.3)) + floor(WP.z / 290.0) * 7.1) * 4375.5));
    e = float3(1.0, 0.7, 0.4) * 1.5 * lit * smoothstep(0.4, 0.95, Night);   // G6: lights on at dusk, not in a storm's gloom
}
else if (code < 4.5)
{
    // A front door: raised panels.
    float2 q = float2(frac(u / 0.48), frac(v / 0.7));
    float inset = step(0.15, q.x) * step(q.x, 0.85) * step(0.12, q.y) * step(q.y, 0.88);
    c *= lerp(1.0, 0.82, inset);
    r = 0.45;
}
else
{
    // A sectional garage door: four horizontal panels with grooves.
    float f = frac(v / 0.53);
    c *= lerp(0.7, 1.0, smoothstep(0.0, 0.04, f) * smoothstep(1.0, 0.94, f)) * (0.96 + 0.04 * step(0.5, frac(u / 0.6)));
    r = 0.5;
}
// Windows painted on the plain walls far from the water (and on commercial blocks): 2.9 m storeys, one every 3.2 m.
if (painted > 0.5 && code < 2.5)
{
    float wu = frac(u / 3.2 + seed);
    float wv = frac(v / 2.9);
    float win = step(0.25, wu) * step(wu, 0.6) * step(0.3, wv) * step(wv, 0.76) * step(floor(v / 2.9) * 2.9 + 2.3, eave) * step(0.4, v);
    // Graphics G8: a white frame round each painted window, a muntin across, the sky in the top half.
    float wf = step(0.23, wu) * step(wu, 0.62) * step(0.28, wv) * step(wv, 0.78) * step(floor(v / 2.9) * 2.9 + 2.3, eave) * step(0.4, v);
    float mun = (1.0 - smoothstep(0.004, 0.008, abs(wu - 0.425))) + (1.0 - smoothstep(0.006, 0.012, abs(wv - 0.53)));
    c = lerp(c, float3(0.80, 0.80, 0.77), saturate(wf - win + saturate(mun) * win));
    c = lerp(c, float3(0.03, 0.035, 0.04) + float3(0.03, 0.04, 0.05) * smoothstep(0.53, 0.76, wv), win * (1.0 - saturate(mun)));
    r = lerp(r, 0.05, win);
    float lit = step(0.55, frac(sin(floor(u / 3.2 + seed) * 37.7 + floor(v / 2.9) * 11.3 + seed * 91.0) * 4375.5));
    e += float3(1.0, 0.7, 0.4) * 1.8 * win * lit * smoothstep(0.4, 0.95, Night);
}
// Weathering: splash-back near the ground, a little grime under the eaves.
c *= lerp(0.78, 1.0, saturate(v / 0.5)) * lerp(1.0, 0.9, saturate((v - eave + 0.6) / 0.6) * step(code, 2.5));
// Graphics G8: the soffit's shadow band and a white fascia line at the eave, and a downspout at each end of a wall run
// (every 9 m along it), on walls.
float wallish = step(code, 2.5);
c = lerp(c, c * 0.55, wallish * saturate(1.0 - abs(v - eave + 0.18) / 0.18) * step(v, eave));
float spout = (1.0 - smoothstep(0.03, 0.045, abs(frac(u / 9.0 + seed * 0.37) - 0.5) * 9.0)) * step(v, eave) * wallish;
c = lerp(c, float3(0.78, 0.78, 0.75), spout);
Emit = e;
Out = r;
return c;
"""

HOUSE_KIT_ROOF_CODE = """
float3 c = pow(saturate(VC.rgb), 2.2);
float code = floor(VA * 255.0 + 0.5);
float u = UV.x, v = UV.y;   // along the eave, up the slope (m)
float r = 0.85;
if (code < 0.5)
{
    // Asphalt shingles: 14 cm courses, 33 cm tabs, each its own shade; the course lines in shadow.
    float row = floor(v / 0.14);
    float tab = floor(u / 0.33 + 0.5 * fmod(row, 2.0));
    float b = frac(sin(row * 31.1 + tab * 17.3 + Tag.x * 91.0) * 4375.5);
    c *= (0.8 + 0.3 * b) * (1.0 - 0.3 * step(0.9, frac(v / 0.14)));
    // Streaks and weathering over the whole roof (tens of metres): no two roofs alike.
    c *= 0.9 + 0.12 * frac(sin(floor(u / 3.0) * 12.7 + Tag.x * 47.0) * 4375.5);
    // Graphics G8: granule speckle on every tab, black algae streaks (Gloeocapsa) running down from the ridge on the
    // shaded slopes, darker at the eave's drip edge, and patchy replacement shingles.
    c *= 0.9 + 0.2 * frac(sin(dot(floor(float2(u, v) * 40.0), float2(12.9, 78.2))) * 43758.5);
    float lane = frac(sin(floor(u / 0.7) * 41.3 + Tag.x * 13.0) * 4375.5);
    float algae = step(0.55, lane) * exp(-pow((frac(u / 0.7) - 0.5) * (3.0 + 4.0 * lane), 2.0)) * saturate(1.0 - v / (3.0 + 5.0 * lane) + 0.6);
    c = lerp(c, c * float3(0.45, 0.47, 0.45), algae * 0.6);
    c *= lerp(0.75, 1.0, saturate(v / 0.25));
    float patch = step(0.93, frac(sin(floor(u / 1.0) * 7.7 + floor(v / 0.7) * 19.3 + Tag.x * 3.0) * 4375.5));
    c = lerp(c, c * 1.25, patch);
}
else if (code < 1.5)
{
    // A flat roof's membrane or gravel: mottled, a seam every 3 m.
    float2 g = floor(float2(u, v) * 2.0);
    c *= (0.9 + 0.12 * frac(sin(dot(g, float2(12.9, 78.2))) * 43758.5)) * (1.0 - 0.15 * step(0.97, frac(u / 3.0)));
    r = 0.9;
}
else
{
    // Standing-seam metal: ribs every 45 cm.
    c *= 0.9 + 0.1 * step(0.92, frac(u / 0.45));
    r = 0.4;
}
Out = r;
return c;
"""


def build_house_kit_materials():
    F1, F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT1, unreal.CustomMaterialOutputType.CMOT_FLOAT3
    for name, code, slot in (("M_HouseKitWall", HOUSE_KIT_WALL_CODE, "HouseWall"), ("M_HouseKitRoof", HOUSE_KIT_ROOF_CODE, "HouseRoof")):
        mat = world_material(name)
        wall = name == "M_HouseKitWall"
        ins = ["UV", "Tag", "VC", "VA"] + (["WP", "Night"] if wall else [])
        c = custom(mat, code, ins, F3, -300, 100, extra_outputs=[("Out", F1)] + ([("Emit", F3)] if wall else []))
        connect(node(mat, unreal.MaterialExpressionTextureCoordinate, -900, 0, coordinate_index=0), "", c, "UV")
        connect(node(mat, unreal.MaterialExpressionTextureCoordinate, -900, 100, coordinate_index=1), "", c, "Tag")
        vc = node(mat, unreal.MaterialExpressionVertexColor, -900, 200)
        connect(vc, "", c, "VC")
        connect(vc, "A", c, "VA")
        if wall:
            connect(node(mat, unreal.MaterialExpressionWorldPosition, -900, 300), "", c, "WP")
            night = node(mat, unreal.MaterialExpressionCollectionParameter, -900, 400)
            night.set_editor_property("collection", world_collection())
            night.set_editor_property("parameter_name", "Night")
            connect(night, "", c, "Night")
            MEL.connect_material_property(c, "Emit", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
        MEL.connect_material_property(c, "Out", unreal.MaterialProperty.MP_ROUGHNESS)
        MEL.recompile_material(mat)
        unreal.EditorAssetLibrary.save_loaded_asset(mat)
        # The kit's look instance (WorldKit KitMaterial: MI_World_<slot>).
        path = f"{WORLD_FOLDER}/MI_World_{slot}"
        mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
            ASSETS.create_asset(f"MI_World_{slot}", WORLD_FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, mat)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)


# Slot -> (colour, roughness, pattern, windows, metallic). Rock: the pale Austin-chalk limestone riprap of the lake's shore.
# The rest are the generated structures' looks and must match KitLook() in Source/SailingSim/Private/WorldKit.cpp.
WORLD_LIBRARY = {
    "Rock": ((0.52, 0.49, 0.43), 0.9, 4.0, 0.0, 0.0),
    "Decking": ((0.42, 0.40, 0.36), 0.85, 1.0, 0.0, 0.0),
    "Floats": ((0.05, 0.05, 0.05), 0.6, 0.0, 0.0, 0.0),
    "Pilings": ((0.32, 0.27, 0.21), 0.9, 9.0, 0.0, 0.0),    # Graphics G8: wood (pattern 9), was concrete
    "Metal": ((0.75, 0.76, 0.78), 0.3, 0.0, 0.0, 1.0),
    "White": ((0.85, 0.86, 0.84), 0.45, 10.0, 0.0, 0.0),   # Graphics G8: weathered dock boxes (pattern 10)
    "Siding": ((0.78, 0.74, 0.64), 0.75, 3.0, 1.0, 0.0),
    "Roof": ((0.20, 0.20, 0.21), 0.8, 2.0, 0.0, 0.0),
    "Concrete": ((0.62, 0.60, 0.56), 0.85, 4.0, 0.0, 0.0),
    "PoolWater": ((0.10, 0.45, 0.55), 0.05, 0.0, 0.0, 0.0),
    "Trim": ((0.88, 0.88, 0.86), 0.5, 0.0, 0.0, 0.0),
    "Lamp": ((0.15, 0.15, 0.15), 0.5, 5.0, 0.0, 0.5),
    "Asphalt": ((0.11, 0.11, 0.11), 0.9, 6.0, 0.0, 0.0),
    "Steel": ((0.30, 0.36, 0.40), 0.55, 5.0, 0.0, 0.6),
    "LampGlow": ((1.0, 0.78, 0.50), 0.4, 0.0, 0.0, 0.0, 40.0),
    "Riprap": ((0.50, 0.47, 0.42), 0.9, 7.0, 0.0, 0.0),
    # Shore plants (Graphics G2, Tools/blender/build_reeds.py): cattail and rush blades, cattail heads.
    "Reed": ((0.17, 0.21, 0.08), 0.75, 2.0, 0.0, 0.0),
    "ReedHead": ((0.20, 0.12, 0.06), 0.85, 0.0, 0.0, 0.0),
    # Near houses (Graphics G2): front doors.
    "Door": ((0.30, 0.10, 0.06), 0.45, 0.0, 0.0, 0.0),
    # Landmarks (Tools/blender/build_landmarks.py slots).
    "PlatformPaint": ((0.62, 0.45, 0.03), 0.6, 5.0, 0.0, 0.2),
    "AviationRed": ((0.55, 0.06, 0.02), 0.5, 0.0, 0.0, 0.0),
    "Brick": ((0.36, 0.15, 0.09), 0.85, 4.0, 0.0, 0.0),
    # Vehicles (Tools/blender/build_props.py slots).
    "Glass": ((0.03, 0.035, 0.04), 0.06, 0.0, 0.0, 0.0),
    "Tyre": ((0.03, 0.03, 0.03), 0.85, 0.0, 0.0, 0.0),
    "HeadLight": ((0.9, 0.9, 0.85), 0.2, 0.0, 0.0, 0.0, 60.0),
    "TailLight": ((0.6, 0.03, 0.02), 0.3, 0.0, 0.0, 0.0, 30.0),
    "Trailer": ((0.80, 0.80, 0.78), 0.5, 5.0, 0.0, 0.3),
    # Navaids (Tools/blender/build_navaids.py slots): retroreflective tape.
    "Reflective": ((0.85, 0.85, 0.82), 0.3, 0.0, 0.0, 0.0),
    # Vessels (Tools/blender/build_vessels.py slots).
    "Gelcoat": ((0.80, 0.80, 0.78), 0.3, 0.0, 0.0, 0.0),
    "Antifouling": ((0.33, 0.04, 0.03), 0.8, 0.0, 0.0, 0.0),
    "TrimGreen": ((0.03, 0.14, 0.08), 0.45, 0.0, 0.0, 0.0),
    "Deck": ((0.55, 0.55, 0.52), 0.8, 0.0, 0.0, 0.0),
    "Cushion": ((0.62, 0.56, 0.44), 0.7, 0.0, 0.0, 0.0),
    "Net": ((0.05, 0.06, 0.05), 0.95, 0.0, 0.0, 0.0),
    "Barge": ((0.22, 0.10, 0.05), 0.85, 5.0, 0.0, 0.3),
    "Cargo": ((0.40, 0.36, 0.30), 0.95, 4.0, 0.0, 0.0),
    "Pilothouse": ((0.80, 0.80, 0.78), 0.4, 3.0, 1.0, 0.0),
    "Funnel": ((0.08, 0.08, 0.09), 0.6, 0.0, 0.0, 0.0),
    "ShipHull": ((0.03, 0.06, 0.12), 0.55, 8.0, 0.0, 0.2),     # Graphics G6: pattern 8, rust weeping from the deck edge
    "Lifeboat": ((0.75, 0.22, 0.02), 0.45, 0.0, 0.0, 0.0),      # SOLAS orange
}


# MATERIALS_ONLY=build_sky_dome,build_terrain rebuilds just those (the rest stay as they are, unsaved and untouched).
ONLY = [n for n in os.environ.get("MATERIALS_ONLY", "").split(",") if n]


def builder_hashes():
    """Each build_* passed to build(): a hash of its code and of every top-level function and constant it reaches (line
    numbers and comments don't count), so a change anywhere a material comes from changes its hash."""
    import ast
    import hashlib
    with open(os.path.abspath(__file__), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    nodes, uses = {}, {}
    for node in tree.body:
        names = [node.name] if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else \
            [t.id for t in getattr(node, "targets", [getattr(node, "target", None)]) if isinstance(t, ast.Name)]
        for n in names:
            nodes[n] = ast.dump(node, include_attributes=False)
            uses[n] = {x.id for x in ast.walk(node) if isinstance(x, ast.Name)}
    builders = [c.args[0].id for c in ast.walk(tree) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "build"
                and c.args and isinstance(c.args[0], ast.Name)]
    out = {}
    for b in builders:
        seen, todo = set(), [b]
        while todo:
            n = todo.pop()
            if n in seen or n not in nodes:
                continue
            seen.add(n)
            todo.extend(uses[n])
        out[b] = hashlib.sha1("".join(nodes[n] for n in sorted(seen)).encode()).hexdigest()
    return out


# MATERIALS_AUTO=1 (scripts/windows/run-python.ps1 sets it; FULL=1 there turns it off): only the builders whose hash
# differs from the last run's (Saved/MaterialsBuilt.json, per checkout), so one material change rebuilds one material.
# Everything is rebuilt when there's no stamp yet (a fresh clone) or when the assets this script writes changed since
# its last run some other way (a git checkout, merge or reset of Content: their names, sizes and times are stamped).
# Inputs outside this file (the fabric scans, the cloud noise) aren't hashed: run with FULL=1 after changing them.
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = os.path.join(REPO_DIR, "Saved", "MaterialsBuilt.json")
OUTPUT_DIRS = ("Materials", "Boats", "Boats/Materials", "World", "Crew/Fabric")   # where the builders save (top level)


def outputs_digest():
    import hashlib
    h = hashlib.sha1()
    for d in OUTPUT_DIRS:
        folder = os.path.join(REPO_DIR, "Content", d)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if name.endswith(".uasset"):
                st = os.stat(os.path.join(folder, name))
                h.update(f"{d}/{name} {st.st_size} {st.st_mtime_ns}\n".encode())
    return h.hexdigest()


HASHES = builder_hashes()   # every run stamps what it built (a full run too), so the next auto run starts from it
if os.environ.get("MATERIALS_AUTO") == "1" and not ONLY and os.path.exists(STAMP):
    import json
    with open(STAMP) as f:
        _last = json.load(f)
    if _last.get("_outputs") != outputs_digest():
        unreal.log("Materials: the assets changed outside this script since its last run: rebuilding all")
    else:
        ONLY = [b for b, h in HASHES.items() if _last.get(b) != h] or ["(none)"]
        unreal.log(f"Materials: changed since the last build: {', '.join(ONLY)}")
BUILT = []


def build(fn):
    if not ONLY or fn.__name__ in ONLY:
        fn()
        BUILT.append(fn.__name__)


def write_stamp():
    """Records the hashes of what this run built (and keeps the rest) and the assets as it leaves them."""
    import json
    last = {}
    if os.path.exists(STAMP):
        with open(STAMP) as f:
            last = json.load(f)
    last.update({b: HASHES[b] for b in BUILT if b in HASHES})
    last["_outputs"] = outputs_digest()
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    with open(STAMP, "w") as f:
        json.dump(last, f, indent=1, sort_keys=True)


build(build_water)
build(build_water_v4)
build(build_spray)
build(build_cloud_layers)
build(build_sky_dome)
build(build_lens_water)
build(build_trees_materials)
build(build_world_surface)
build(build_vehicle_paint)
build(build_navaid_paint)
build(build_house_materials)
build(build_house_kit_materials)
build(build_terrain)
build(build_rain)
build(build_rain_curtain)
build(build_smoke)
build(build_emissive)
build(build_sail)
build(build_ghost)
build(build_lens_distortion)

# ---------------------------------------------------------------- crew cloth (Graphics G3)
FABRIC_FOLDER = "/Game/Crew/Fabric"
FABRIC_RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Data", "Fabrics", "raw")
# CC0 scans from ambientCG (Data/Fabrics/raw, fetched by Tools/fabrics/fetch_fabrics.sh): the knit or weave's relief and
# roughness; the colour is the sailor's, modulated by the scan's own light and dark (its mean luminance, measured in the
# venv, normalises it to 1). Fabric070: sportswear knit (the polo's pique); Fabric048: polyester vest (the life jacket's
# shell); Fabric036: smooth woven cotton (cap).
FABRIC_SETS = {"Fabric070": 0.4114, "Fabric048": 0.9051, "Fabric036": 0.4931, "Leather038": 0.2911}
FABRIC_CODE = r"""
// Graphics G3 crew cloth: the sailor's colour over the scan's knit (its luminance, normalised by its mean), a slow dye
// variation, the scan's normal faded with distance (past a few metres the knit is under a pixel and only shimmers), and
// fuzz: cotton and polyester scatter light at grazing angles (the sheen on a shoulder against the sun).
float lumA = dot(A, float3(0.3, 0.59, 0.11));
float detail = lerp(1.0, lumA / max(AvgLum, 0.05), DetailAmount);
float dye = 1.0 + 0.05 * sin(WP.x * 0.031 + WP.z * 0.017) * sin(WP.y * 0.027 - WP.z * 0.011);
AlbedoOut = saturate(C.rgb * detail * dye);
float fade = saturate(1.0 - (Depth - 150.0) / 600.0);
float3 tn = normalize(lerp(float3(0, 0, 1), Nt, saturate(Strength * fade)));
// Graphics G8: a life jacket's foam is sewn into vertical channels (ChanPeriod along U, in metres; 0 off): each panel a
// low pillow (4 mm), the seams between them darker. Round 11 (the channels all round read as a pool toy): the two front
// panels are flat foam, so the channels run only on the back and sides, where |U| (0 at the front's centre, build_vest.py)
// is past ChanFront.
if (ChanPeriod > 0.0)
{
    float cmask = saturate((abs(UV0.x) - ChanFront) / 0.02);
    float f = frac(UV0.x / ChanPeriod) - 0.5;
    float slope = -0.004 * 3.14159 * sin(3.14159 * f) / ChanPeriod;
    float cfade = saturate(1.0 - (Depth - 600.0) / 1200.0) * cmask;
    tn = normalize(float3(tn.xy + float2(-slope * 2.5 * cfade, 0.0), tn.z));
    AlbedoOut *= 1.0 - 0.22 * cmask * pow(saturate(abs(2.0 * f)), 10.0);
}
RoughOut = saturate(lerp(RoughBase, R, 0.6 * fade + 0.2));
FuzzOut = Sheen;
return tn;
"""


def fabric_texture(name, src, kind):
    path = f"{FABRIC_FOLDER}/{name}"
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", FABRIC_FOLDER)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    ASSETS.import_asset_tasks([task])
    tex = unreal.load_asset(path)
    if kind == "normal":
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
    elif kind == "rough":
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return tex


def build_crew_fabric():
    """M_CrewFabric and its instances: the crew's polo, collar and cuffs, life jacket shell and cap."""
    if not all(os.path.isdir(os.path.join(FABRIC_RAW, k)) for k in FABRIC_SETS):
        unreal.log_warning("Crew fabric: no scans in Data/Fabrics/raw (Tools/fabrics/fetch_fabrics.sh); skipped")
        return
    texs = {}
    for k in FABRIC_SETS:
        base = os.path.join(FABRIC_RAW, k, f"{k}_2K-JPG")
        texs[k] = (fabric_texture(f"T_{k}_C", base + "_Color.jpg", "color"), fabric_texture(f"T_{k}_N", base + "_NormalDX.jpg", "normal"),
                   fabric_texture(f"T_{k}_R", base + "_Roughness.jpg", "rough"))
    path = f"{FABRIC_FOLDER}/M_CrewFabric"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset("M_CrewFabric", FABRIC_FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("used_with_skeletal_mesh", True)
    mat.set_editor_property("two_sided", True)
    first = texs["Fabric070"]
    color = vector(mat, "Color", (0.05, 0.10, 0.30, 1), -1600, -300)
    tiling = scalar(mat, "Tiling", 8.0, -1900, 0)
    uv0 = node(mat, unreal.MaterialExpressionTextureCoordinate, -1900, -100)
    mul = node(mat, unreal.MaterialExpressionMultiply, -1700, -50)
    connect(uv0, "", mul, "A")
    connect(tiling, "", mul, "B")
    ta = node(mat, unreal.MaterialExpressionTextureSampleParameter2D, -1450, -150, parameter_name="AlbedoMap", texture=first[0])
    tn = node(mat, unreal.MaterialExpressionTextureSampleParameter2D, -1450, 100, parameter_name="NormalMap", texture=first[1])
    tn.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    tr = node(mat, unreal.MaterialExpressionTextureSampleParameter2D, -1450, 350, parameter_name="RoughMap", texture=first[2])
    tr.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    for t in (ta, tn, tr):
        connect(mul, "", t, "UVs")
    depth = node(mat, unreal.MaterialExpressionPixelDepth, -1450, 600)
    wp = node(mat, unreal.MaterialExpressionWorldPosition, -1450, 700)
    F3, F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT3, unreal.CustomMaterialOutputType.CMOT_FLOAT1
    c = custom(mat, FABRIC_CODE, ["C", "A", "Nt", "R", "AvgLum", "DetailAmount", "Strength", "RoughBase", "Sheen", "Depth", "WP", "UV0", "ChanPeriod", "ChanFront"], F3, -900, 100,
               extra_outputs=[("AlbedoOut", F3), ("RoughOut", F1), ("FuzzOut", F1)])
    connect(color, "RGBA", c, "C")
    connect(ta, "RGB", c, "A")
    connect(tn, "RGB", c, "Nt")
    connect(tr, "R", c, "R")
    for i, (pname, default) in enumerate((("AvgLum", 0.41), ("DetailAmount", 0.8), ("Strength", 1.0), ("RoughBase", 0.85), ("Sheen", 0.5))):
        connect(scalar(mat, pname, default, -1200, 800 + 90 * i), "", c, pname)
    connect(depth, "", c, "Depth")
    connect(wp, "", c, "WP")
    connect(uv0, "", c, "UV0")
    connect(scalar(mat, "ChanPeriod", 0.0, -1200, 1300), "", c, "ChanPeriod")
    connect(scalar(mat, "ChanFront", 0.19, -1200, 1390), "", c, "ChanFront")
    slab = node(mat, unreal.MaterialExpressionSubstrateSlabBSDF, -400, 100)
    connect(c, "AlbedoOut", slab, "Diffuse Albedo")
    connect(node(mat, unreal.MaterialExpressionConstant3Vector, -700, 400, constant=unreal.LinearColor(0.04, 0.04, 0.04, 1)), "", slab, "F0")
    connect(c, "RoughOut", slab, "Roughness")
    connect(c, "", slab, "Normal")
    connect(c, "FuzzOut", slab, "Fuzz Amount")
    connect(c, "AlbedoOut", slab, "Fuzz Color")
    MEL.connect_material_property(slab, "", unreal.MaterialProperty.MP_FRONT_MATERIAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    # Instances: (scan, colour, tiling, normal strength, base roughness, sheen). Tiling is per UV unit: the polo keeps the
    # T-shirt's UVs (about a metre of garment per unit), the gear's are in its unit size scaled to the sailor.
    for name, (k, col, tile, strength, rough, sheen) in {
        "MI_Crew_Polo": ("Fabric070", (0.05, 0.10, 0.30), 9.0, 0.55, 0.85, 0.45),     # round 11: a quieter knit
        "MI_Crew_PoloRib": ("Fabric070", (0.05, 0.10, 0.30), 16.0, 1.0, 0.85, 0.45),
        "MI_Crew_PFDShell": ("Fabric048", (0.02, 0.05, 0.25), 30.0, 0.35, 0.66, 0.25),  # round 11: less shiny
        "MI_Crew_Webbing": ("Fabric036", (0.13, 0.135, 0.14), 40.0, 1.0, 0.62, 0.3),     # Graphics G8: the vest's nylon webbing
        "MI_Crew_CapCloth": ("Fabric036", (0.72, 0.72, 0.72), 20.0, 0.5, 0.85, 0.5),
        "MI_Crew_Shorts": ("Fabric036", (0.30, 0.25, 0.16), 10.0, 0.7, 0.85, 0.45),     # cotton twill shorts (colour per sailor)
        "MI_Crew_ShoeLeather": ("Leather038", (0.28, 0.14, 0.06), 8.0, 0.8, 0.55, 0.1),  # oiled leather deck shoe uppers
    }.items():
        mpath = f"{FABRIC_FOLDER}/{name}"
        mi = unreal.load_asset(mpath) if unreal.EditorAssetLibrary.does_asset_exist(mpath) else \
            ASSETS.create_asset(name, FABRIC_FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, mat)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(col[0], col[1], col[2], 1.0))
        chan = 0.10 if name == "MI_Crew_PFDShell" else 0.0   # Graphics G8: the vest's foam channels (its UVs are in metres round the torso)
        for pname, value in (("Tiling", tile), ("Strength", strength), ("RoughBase", rough), ("Sheen", sheen), ("AvgLum", FABRIC_SETS[k]), ("ChanPeriod", chan)):
            MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        for pname, t in zip(("AlbedoMap", "NormalMap", "RoughMap"), texs[k]):
            MEL.set_material_instance_texture_parameter_value(mi, pname, t)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)

build(build_boat_library)
build(build_crew_fabric)
build(build_sail_cloth)
build(build_telltale)
write_stamp()
unreal.log(f"Materials built: {len(BUILT)} builders")
