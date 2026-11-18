"""Shore edge looks and the shared water-edge layer (shore plan Track C, docs/envloop/shore-edges/).

EDGE_LAYER_CODE is HLSL in the subset Tools/texloop/dock/hlsl_np.py runs on numpy, so the cloud renders (render_edges.py)
are the shader's own text and the in-game material (after Nov 21, in its own script, never scripts/make_materials.py)
pastes the same code into a Custom node. It does two things:

1. The base look of each surface the kit marks in vertex colour R (edge_kit.SURF): concrete with panel joints and
   pinholes, rusting steel, bedded limestone, weathered boards, layered clay, mud that cracks as it dries, gravel with
   shell, sand, the ramp's V-grooves and tyre tracks, roots and sticks, leaves, reeds, dry grass.
2. The water's marks, worked out from height, so one mesh is right at any lake level:
   - wet line: dark and glossy from the water up the swash (porous ground wicks higher);
   - stain band: silt tan on hard faces between the lowest and highest recent water, darker and ringed lower down;
   - scum line: a pale dried line at the band's top;
   - algae: what is under the water most of the time is slimy olive under it and a grey-green crust when a low
     lake leaves it dry (the ramp's slick toe);
   - run-off: streaks under weep holes and bolts (vertex colour B), rust from steel;
   - wrack: a dark organic stain on the ground at the high-water line (the sticks and leaves are geometry).

Inputs (per pixel): WP world position in metres, Nw world normal, VC vertex colour, UVm metre UVs (u along, v up or
across), n003 n01 n05 n2 noise in 0..1 at 3 cm, 10 cm, 0.5 m and 2 m (in game: one tiling noise texture at four
scales, mipped; here value noise faded by the pixel's footprint), ns streak noise (narrow vertical cells).
Uniforms (MPC_World in game): WaterZ the lake now, PoolZ the conservation pool, HighZ the top of the stain band,
LowZ the lowest recent water, WrackZ the debris line, Swash the wet height above the water. The colours (SoilA,
Concrete, StainHigh, ...) are named parameters too: their values, like the levels, come from the region pack
(packs/<name>/pack.json "marks" and "colours"), so another region changes data, not shader.
Outputs: c (linear albedo), r (roughness), wet.

Colours are linear albedo, first estimates from typical published values and the rock loop's measures; the grey-card
club photos (Bean's) replace them in the pack through the colour check.
"""

EDGE_LAYER_CODE = """
float sid = floor(VC.x * 16.0);
float shade = VC.y;
float runoff = VC.z;
float zz = WP.z;
float up = saturate(Nw.z);
// One weight per surface (edge_kit.SURF); the in-game material fixes the surface per mesh section instead.
float wSoil = saturate(1.0 - abs(sid - 0.0) * 2.0);
float wLawn = saturate(1.0 - abs(sid - 1.0) * 2.0);
float wConc = saturate(1.0 - abs(sid - 2.0) * 2.0);
float wSteel = saturate(1.0 - abs(sid - 3.0) * 2.0);
float wLime = saturate(1.0 - abs(sid - 4.0) * 2.0);
float wTimb = saturate(1.0 - abs(sid - 5.0) * 2.0);
float wClay = saturate(1.0 - abs(sid - 6.0) * 2.0);
float wMud = saturate(1.0 - abs(sid - 7.0) * 2.0);
float wGrav = saturate(1.0 - abs(sid - 8.0) * 2.0);
float wShell = saturate(1.0 - abs(sid - 9.0) * 2.0);
float wSand = saturate(1.0 - abs(sid - 10.0) * 2.0);
float wRamp = saturate(1.0 - abs(sid - 11.0) * 2.0);
float wWood = saturate(1.0 - abs(sid - 12.0) * 2.0);
float wLeaf = saturate(1.0 - abs(sid - 13.0) * 2.0);
float wReed = saturate(1.0 - abs(sid - 14.0) * 2.0);
float wDry = saturate(1.0 - abs(sid - 15.0) * 2.0);
float hard = wConc + wSteel + wLime + wTimb + wRamp;
float ground = wSoil + wClay + wMud + wGrav + wShell + wSand;
float r2 = frac(n003 * 7.13 + n01 * 3.1);

// Blackland clay topsoil: dark grey-brown, crumbly.
float3 cSoil = lerp(SoilA, SoilB, n05) * (0.85 + 0.3 * n01);
// Mown bermuda, browner in patches.
float3 cLawn = lerp(lerp(LawnA, LawnB, n05), LawnBrown, 0.6 * smoothstep(0.75, 0.95, n2)) * (0.7 + 0.6 * n003);
// Poured concrete: mottled by pour and weather, panel joints every 2.44 m, pinholes.
float jx = frac(UVm.x / 2.44 + 0.5);
float jd = min(jx, 1.0 - jx) * 2.44;
float joint = 1.0 - smoothstep(0.004, 0.012, jd);
float3 cConc = Concrete * (0.82 + 0.28 * n2) * (0.9 + 0.15 * n01) * (1.0 - 0.5 * joint) * (1.0 - 0.2 * step(0.95, n003));
// Steel sheet pile: dark mill scale and paint going to rust, each pair its own.
float rust = saturate(0.45 + (n05 - 0.5) * 0.9 + (n01 - 0.5) * 0.5 + (shade - 0.5) * 0.3 + (1.0 - smoothstep(PoolZ, PoolZ + 0.5, zz)) * 0.3);
float3 cSteel = lerp(SteelScale, lerp(RustDark, RustLight, n01), rust) * (0.85 + 0.3 * n003);
// Cream limestone: bedding lines, pits, dark lichen above the high water.
float bed = 1.0 - smoothstep(0.02, 0.06, abs(frac(zz * 7.0 + n05 * 0.8) - 0.5));
float3 cLime = Limestone * (0.78 + 0.3 * n05) * (0.9 + 0.2 * n003) * (0.75 + 0.5 * shade) * (1.0 - 0.12 * bed) * (1.0 - 0.4 * step(0.84, n003));
cLime = lerp(cLime, Lichen, 0.5 * smoothstep(0.6, 0.78, n05 * 0.65 + n01 * 0.35) * step(HighZ + 0.1, zz));
// Weathered treated pine: grey, grain along the board, each board its own.
float grain = 0.88 + 0.12 * sin(UVm.y * 700.0 + n01 * 18.0);
float3 cTimb = lerp(TimberDark, TimberLight, shade) * grain * (0.85 + 0.25 * n05);
// The cut clay face: tan-grey layers, pale calcareous nodules, rain rills down the face.
float lay = frac(zz * 2.5 + n2 * 0.6 + n05 * 0.35);
float3 cClay = lerp(ClayA, ClayB, smoothstep(0.45, 0.85, lay)) * (0.85 + 0.25 * n01);
cClay = lerp(cClay, ClayNodule, 0.7 * step(0.975, n003));
cClay = cClay * (1.0 - 0.18 * (1.0 - smoothstep(0.08, 0.2, ns)));
// Mud: dark and smooth where wet, pale and cracked as it dries (the cracks: isolines of the noise make the network).
float dry = smoothstep(WaterZ + 0.04, WaterZ + 0.5, zz);
float crack = (1.0 - smoothstep(0.0, 0.03, abs(n01 - 0.5))) * 0.7 + (1.0 - smoothstep(0.0, 0.02, abs(n05 - 0.5))) * 0.5;
float3 cMud = lerp(MudWet, MudDry * (0.9 + 0.2 * n05), dry) * (1.0 - 0.65 * saturate(crack) * dry);
// Gravel: pale limestone, dark chert, rusty ironstone, a few clam shells.
float3 cGrav = lerp(lerp(GravelDark, GravelMid, step(0.2, n003)), GravelPale, step(0.75, n003)) * (0.88 + 0.24 * n01);
cGrav = lerp(cGrav, ShellBleached, step(0.96, r2));
// Shell hash: Asian clam valves, bleached, over the gravel.
float3 cShell = lerp(cGrav, ShellHash * (0.85 + 0.3 * n003), step(0.7, r2));
// Lake sand: brown, fine.
float3 cSand = Sand * (0.9 + 0.15 * n01) * (0.95 + 0.1 * n003);
// The ramp: broom-and-groove concrete; V-grooves 25 mm wide every 150 mm in a chevron up the slope; tyre tracks.
float gg = frac((UVm.y + abs(UVm.x) * 0.577) / 0.15);
float groove = 1.0 - smoothstep(0.008, 0.016, min(gg, 1.0 - gg) * 0.15);
float tyre = (1.0 - smoothstep(0.12, 0.3, abs(abs(UVm.x) - 0.85))) * step(WaterZ, zz);
float3 cRamp = RampConcrete * (0.85 + 0.25 * n2) * (0.92 + 0.12 * n01) * (1.0 - 0.45 * groove) * (1.0 - 0.3 * tyre);
// Sticks and roots, leaves, reeds (stand-ins for Track B's), dry grass.
float3 cWood = lerp(WoodDark, WoodLight, shade);
float3 cLeaf = lerp(LeafA, LeafB, shade);
float3 cReed = lerp(ReedGreen, ReedStraw, shade);
float3 cDry = lerp(DryGrassA, DryGrassB, n05) * (0.85 + 0.3 * n01);

float3 c = (wSoil * cSoil + wLawn * cLawn + wConc * cConc + wSteel * cSteel + wLime * cLime + wTimb * cTimb + wClay * cClay
         + wMud * cMud + wGrav * cGrav + wShell * cShell + wSand * cSand + wRamp * cRamp + wWood * cWood + wLeaf * cLeaf
         + wReed * cReed + wDry * cDry);
float r = (wSoil * 0.92 + wLawn * 0.85 + wConc * 0.85 + wSteel * lerp(0.55, 0.8, rust) + wLime * 0.8 + wTimb * 0.8 + wClay * 0.9
        + wMud * lerp(0.35, 0.92, dry) + wGrav * 0.8 + wShell * 0.6 + wSand * 0.9 + wRamp * 0.8 + wWood * 0.8 + wLeaf * 0.7
        + wReed * 0.7 + wDry * 0.85);

// The stain band: silt tan on hard faces between the lowest and highest recent water, ringed, darker lower down.
float band = 1.0 - smoothstep(HighZ - 0.03, HighZ + 0.02, zz + (n01 - 0.5) * 0.04);
band = band * smoothstep(LowZ - 0.2, LowZ + 0.1, zz);
float deep = saturate((HighZ - zz) / max(HighZ - LowZ, 0.1));
float rings = 0.8 + 0.2 * sin((zz - LowZ) * 45.0 + n05 * 3.0);
float3 stainCol = lerp(StainHigh, StainLow, deep);
c = lerp(c, stainCol * (0.85 + 0.3 * n05), saturate(band * rings * (0.6 * hard + 0.2 * ground) * (0.75 + 0.5 * n2)));
// The scum line at its top: pale, thin, broken.
float scum = (1.0 - smoothstep(0.0, 0.012 + 0.012 * n01, abs(zz - HighZ + 0.015 + (n05 - 0.5) * 0.03))) * step(0.3, n01);
c = lerp(c, Scum, 0.65 * scum * hard);
// Algae: whatever is under the pool most of the year. Slimy olive in the water, a grey-green crust left dry.
float algae = (1.0 - smoothstep(PoolZ - 0.25, PoolZ - 0.03, zz + (n05 - 0.5) * 0.06)) * smoothstep(LowZ - 0.6, LowZ, zz);
float exposed = step(WaterZ + 0.02, zz);
float3 algaeCol = lerp(AlgaeWet, AlgaeDry * (0.8 + 0.4 * n01), exposed);
float algaeAmt = algae * (0.85 * hard + 0.35 * ground) * (0.7 + 0.3 * n05);
c = lerp(c, algaeCol, algaeAmt);
r = lerp(r, lerp(0.25, 0.9, exposed), algaeAmt);
// Run-off under weep holes and bolts: dark on concrete, rust from steel.
float streak = runoff * smoothstep(0.2, 0.6, ns) * (0.7 + 0.3 * n05);
c = lerp(c, lerp(RunOff, RunRust, wSteel), 0.8 * streak);
// Wrack: the organic stain where the sticks and leaves come to rest.
float wrack = (1.0 - smoothstep(0.0, 0.07 + 0.05 * n05, abs(zz - WrackZ + (n2 - 0.5) * 0.08))) * ground * up;
c = lerp(c, Wrack, 0.55 * wrack * step(0.35, n01));
// Wet: from the water up the swash; porous ground wicks a little higher; steel just darkens a touch.
float wetTop = WaterZ + Swash * (0.75 + 0.5 * n2) + 0.1 * ground * (0.5 + n05) + 0.03 * (n01 - 0.5);
float wet = 1.0 - smoothstep(wetTop - 0.03, wetTop + 0.04, zz);
float porous = 1.0 - 0.6 * wSteel - wReed - wLeaf;
c = c * lerp(1.0, 0.5, wet * porous);
r = lerp(r, 0.22, wet * saturate(porous + 0.3));
"""


def values(pack, level="pool"):
    """The uniforms for a region pack (packs/<name>/pack.json: its marks and colours) at a lake level (a name from the
    pack's levels, or metres from the pool). In game these are MPC_World (levels) and the material instance (colours)."""
    import numpy as np   # here, not at the top: scripts/import_shore_edges.py reads this module in the editor's Python
    u = dict(pack["marks"])
    u["WaterZ"] = pack["levels"][level] if isinstance(level, str) else float(level)
    u.update({k: np.array(v, float) for k, v in pack["colours"].items()})
    return u


# The game's noise (scripts/import_shore_edges.py): the four scales and the streak noise are gradient noise computed in the
# material from the world position, one Custom node a scale (no texture, so nothing to import; the pieces are a small part
# of any frame). Two octaves, as render_edges.grad_noise, and the same lattice hash, so the stills and the renders agree.
# `{scale}` is the cell in metres (a float3 for the streak noise), `{seed}` an integer. Output 0..1 (clamped; the
# renders equalise instead, which the thresholds were set on: the Mac's stills check the difference).
EDGE_NOISE_CODE = """
float3 q = P / {scale};
float acc = 0.0;
float amp = 1.0;
float sd = {seed};
for (int oct = 0; oct < 2; ++oct)
{{
    float3 i = floor(q);
    float3 f = q - i;
    float3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    float n = 0.0;
    for (int k = 0; k < 8; ++k)
    {{
        float3 d = float3(k & 1, (k >> 1) & 1, (k >> 2) & 1);
        float3 c = i + d;
        float h = frac(sin(dot(c, float3(127.1, 311.7, 74.7)) + sd * 0.37) * 43758.5453);
        float th = h * 6.2831853;
        float z = frac(h * 57.31) * 2.0 - 1.0;
        float s = sqrt(max(1.0 - z * z, 0.0));
        float3 g = float3(s * cos(th), s * sin(th), z);
        float w = (d.x > 0.5 ? u.x : 1.0 - u.x) * (d.y > 0.5 ? u.y : 1.0 - u.y) * (d.z > 0.5 ? u.z : 1.0 - u.z);
        n += w * dot(g, f - d);
    }}
    acc += amp * n;
    amp = 0.45;
    q = q * 2.03 + 11.7;
    sd += 31.0;
}}
return saturate(0.5 + acc * 0.9);
"""
