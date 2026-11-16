"""The house wall and roof material's shader text (Track E2, docs/envloop/buildmat): one Custom node for M_HouseKit_Wall
and M_HouseKit_Roof, run here on numpy through the texture loop's HLSL translator (Tools/texloop/dock/hlsl_np.py), so the
renders in this folder come from the shader text itself, not a hand port that can drift.

The integration pull request (after 21 Nov) puts BUILDMAT_CODE in its own material script (never make_materials.py) with
these inputs, each a node in front of the Custom node:

  C     float3  the finish's colour map, linear (Texture2DSample of <name>_C at (UV.x / TS.x, -UV.y / TS.y))
  M     float3  the mask map's R ambient occlusion, G roughness, B unit id
  HT    float   the mask map's A: height, 0 = 8 mm deep .. 1 = 25 mm proud (PLANE = 0.2424 is the wall face)
  UV    float2  UV0: metres along the wall (or eave) and up from the ground line (or up the slope from the eave)
  TS    float2  the finish's tile size in metres (textures.json)
  Kind  float   the finish's class number (pack.CLASSES: brick 0, stone 3, lap 4, batten 5, render 6, shingle 10,
                standing_seam 13, membrane 14), looked up from the region pack by the finish id in vertex colour G
  Paint float3  the house's paint, linear: walls take paint role 7 body, roofs role 8 roof (slots.json per_house_paint;
                ignored by brick, stone and shingles)
  Bare  float   metal roof only: the house's galvalume flag, 1 bare Galvalume (role 8 ignored), 0 painted
  Age   float   years (E1's Age, as the boats); Care 0 neglected .. 1 kept
  Care  float
  North float   0 facing south (sun) .. 1 facing north (shade): from the normal, 0.5 - 0.5 * N.x in map frame (+X north)
  Sun   float   1 - North, kept separate so a roof can use its own slope (up-facing roofs get more sun)
  Eave  float   walls: eave height above the ground (m); roofs: slope length eave to ridge (m)
  N1    float3  T_BuildNoise at UV / NOISE1_M (7.31 m: R value noise, G spots, B vertical streaks); N1W its A (cracks)
  N2    float3  T_BuildNoise at UV / NOISE2_M (0.93 m) + (0.37, 0.61); N2W its A (fine cracks)
              The two scales are not whole multiples of each other or of any tile (about 4 m), so the wash and the
              texture never line up again inside a 40 m frame.

Outputs: return value base colour, Out roughness, Met metallic, AOo ambient occlusion. The normal is the finish's
normal map unchanged.

Wear: dT and dD are exactly Tools/texloop/wear.py's time_k and dirt_k (test_buildmat.py checks it), so a house and a boat
of the same Age and Care read the same five levels (Tools/texloop/levels.json: L0 new .. L4 neglected).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "texloop", "dock"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "texloop"))

BUILDMAT_CODE = """
float dT = saturate(0.25 * (1.0 - exp(-Age / 0.75)) + 0.75 * (1.0 - exp(-Age / 18.0)));
float dD = saturate((1.0 - exp(-Age / 1.0)) * (0.15 + 0.85 * (1.0 - saturate(Care))));
float ao = M.x;
float r = M.y;
float uid = M.z;
float unit = step(0.01, uid);
float tx = floor(UV.x / TS.x), ty = floor(UV.y / TS.y);
// Anti-tiling: every unit (brick, stone, board, tab, panel) takes a new shade in every tile, and a 1 m wash lies over all.
float jit = frac(sin(uid * 91.7 + tx * 12.9898 + ty * 78.233) * 43758.5);
float jit2 = frac(sin(uid * 47.3 + tx * 39.346 + ty * 11.135) * 24634.6);
float3 c = C;
float met = 0.0;
float wash = N1.x - 0.5;
if (Kind < 3.5)
{
    // Brick and limestone: their own colour. Per-unit shade, mortar that darkens with the years, white efflorescence
    // low on the wall where it stays damp, soot and lichen on old stone, a replaced brick here and there on an old wall.
    float stone = step(2.5, Kind);
    c = c * (1.0 + lerp(0.18, 0.30, stone) * (jit - 0.5) * unit) * (1.0 + lerp(0.10, 0.18, stone) * wash);
    c = lerp(c, c * lerp(float3(0.92, 0.95, 1.0), float3(1.05, 0.98, 0.88), jit2), stone * unit * 0.8);
    c = lerp(c, c * 0.78, (1.0 - unit) * dT * 0.6);
    // salt bloom: led by the mortar joints, in the bottom half metre where the wall wicks water from the ground
    float lowb = saturate(1.0 - UV.y / 0.6);
    float eff = dD * dD * lowb * lowb * smoothstep(0.35, 0.8, N1.y * 0.5 + N2.y * 0.5) * lerp(1.0, 0.35, unit);
    c = lerp(c, float3(0.66, 0.65, 0.61), eff * 0.55);
    // soiling washed down the face by rain, in long streaks (pale brick and stone show it most)
    float soil = dD * (0.4 + 0.6 * dT) * smoothstep(0.3, 0.85, 0.6 * N1.z + 0.4 * N2.z) * (0.6 + 0.4 * N2.x);
    c = c * (1.0 - 0.28 * soil);
    r = lerp(r, 0.95, eff);
    float swap = unit * step(0.992 - 0.015 * dT * Care, jit2);
    c = lerp(c, c * 1.18, swap);
    if (Kind > 2.5)
    {
        c = lerp(c, c * float3(0.70, 0.71, 0.73), saturate(dT * (1.0 - ao) * 4.0 + dD * 0.5 * N1.x));
        float lich = dT * (0.3 + 0.7 * dD) * smoothstep(0.70, 0.90, N2.y) * smoothstep(0.5, 0.8, N1.y) * (0.5 + 0.5 * North);
        c = lerp(c, lerp(float3(0.40, 0.42, 0.33), float3(0.12, 0.12, 0.11), step(0.5, N2.z)), lich * 0.75);
    }
}
else if (Kind < 9.5)
{
    // Painted siding, battens and stucco: the paint over the neutral grain; chalk and fade in the sun; mildew in the
    // laps and on north walls; peeling on a neglected old house (siding and battens), cracks in old stucco.
    c = Paint * (C / 0.8) * (1.0 + 0.06 * wash + 0.03 * (jit - 0.5) * unit);
    float lum = dot(c, float3(0.3, 0.59, 0.11));
    c = lerp(c, lum * 0.55 + c * 0.25 + 0.12, 0.40 * dT * (0.4 + 0.6 * Sun));
    r = lerp(r, 0.95, 0.5 * dT);
    float mil = dD * smoothstep(0.55, 0.85, N2.y) * (0.25 + 0.75 * North) * saturate(0.4 + (1.0 - ao) * 4.0);
    c = lerp(c, c * float3(0.32, 0.34, 0.28), mil * 0.75);
    float pk = dD * dT;
    // peeling only on a neglected old house: small flakes, most under the laps' drip edges and low on the wall
    float drip = saturate((1.0 - ao) * 6.0);
    float peel = smoothstep(0.90 - 0.3 * pk, 0.93 - 0.3 * pk, N2.y * 0.45 + N2.x * 0.2 + N1.x * 0.15 + drip * 0.35) * step(0.4, pk) * step(Kind, 5.5);
    c = lerp(c, lerp(float3(0.40, 0.39, 0.36), c * 0.8, 0.4 * N2.x), peel);
    r = lerp(r, 0.9, peel);
    if (Kind > 5.5)
    {
        // hairline cracks in patches a few metres apart (N1's spots pick the patches), from middle age on
        float crack = smoothstep(0.80 - 0.12 * dT, 0.86 - 0.12 * dT, N2W) * smoothstep(0.55, 0.75, N1.y) * step(0.5, dT) * (0.3 + 0.7 * dD);
        c = lerp(c, c * 0.45, crack);
        ao = ao * (1.0 - 0.5 * crack);
    }
}
else if (Kind < 12.5)
{
    // Asphalt shingles: per-tab shade, granules lost to bare black asphalt with the years (more in the sun), black algae
    // streaks running down the slope (more on north slopes), pale lichen spots, newer patches on a kept roof.
    c = c * (1.0 + 0.12 * (jit - 0.5) * unit) * (1.0 + 0.10 * wash);
    float loss = dT * dT * (0.5 + 0.5 * Sun) * smoothstep(0.6, 0.85, N2.x * 0.8 + N1.x * 0.2);
    c = lerp(c, float3(0.035, 0.033, 0.030), loss * 0.8);
    r = lerp(r, 0.78, loss);
    float alg = dD * (0.3 + 0.7 * North) * smoothstep(0.45, 0.8, N1.z) * saturate(1.15 - UV.y / (Eave + 0.01));
    c = lerp(c, c * float3(0.30, 0.31, 0.29), alg * 0.85);
    // lichen: small colonies gathered in a few places, soft-edged, darker grey-green than the granules' highlights
    float lich = dT * dD * smoothstep(0.84, 0.95, N2.y) * smoothstep(0.55, 0.8, N1.y);
    c = lerp(c, lerp(c, float3(0.30, 0.32, 0.26), 0.7), lich);
    float patch = step(0.95, frac(sin(floor(UV.x / 1.0) * 7.7 + floor(UV.y / 0.429) * 19.3) * 4375.5)) * dT * Care;
    c = lerp(c, C * 1.1, patch);
}
else if (Kind < 13.5)
{
    // Standing-seam steel: bare Galvalume (metallic, dulling and spotting with the years) or painted (chalk and fade);
    // a neglected old roof rusts along the seams and at the eave.
    if (Bare > 0.5)
    {
        c = float3(0.60, 0.62, 0.63) * (C / 0.8) * (1.0 + 0.06 * wash);
        met = 1.0;
        r = lerp(r, 0.62, dT * (0.5 + 0.5 * N1.x));
        float wr = dT * smoothstep(0.75, 0.9, N2.y);
        c = lerp(c, float3(0.50, 0.50, 0.48), wr * 0.6);
    }
    else
    {
        c = Paint * (C / 0.8) * (1.0 + 0.04 * wash);
        float lum = dot(c, float3(0.3, 0.59, 0.11));
        c = lerp(c, lum * 0.6 + c * 0.2 + 0.1, 0.45 * dT * (0.4 + 0.6 * Sun));
        r = lerp(r, 0.8, 0.6 * dT);
    }
    float rust = dT * dD * saturate(smoothstep(0.45, 0.6, HT) + saturate(1.0 - UV.y / 0.25)) * smoothstep(0.55, 0.75, N2.x);
    c = lerp(c, float3(0.22, 0.10, 0.045), rust);
    met = lerp(met, 0.0, rust);
    r = lerp(r, 0.85, rust);
}
else
{
    // A flat roof's membrane in the roof colour: it greys and yellows with the years; dirt dries in brown rings where
    // water ponds, and a neglected one grows dark patches.
    c = Paint * (C / 0.8) * (1.0 + 0.05 * wash);
    c = lerp(c, c * float3(0.86, 0.84, 0.76), 0.6 * dT);
    float pond = dD * smoothstep(0.55, 0.75, N1.x) * (1.0 - smoothstep(0.75, 0.9, N1.x) * 0.5);
    c = lerp(c, c * float3(0.62, 0.55, 0.45), pond * 0.7);
    float blk = dD * dT * smoothstep(0.55, 0.92, N2.y) * (0.5 + 0.5 * smoothstep(0.3, 0.7, N1.x));
    c = lerp(c, c * 0.45, blk * 0.8);
    r = lerp(r, 0.9, dT * 0.5);
}
if (Kind < 9.5)
{
    // Every wall: red clay splashed up from the bed by rain, a little grime under the eaves, green algae low on north walls.
    float sp = (0.1 + 0.8 * dD) * saturate(1.0 - UV.y / (0.2 + 0.35 * N1.z));
    c = lerp(c, c * float3(0.60, 0.48, 0.38) + float3(0.035, 0.022, 0.010), sp * 0.7);
    float eg = dD * saturate(1.0 - (Eave - UV.y) / 0.6) * 0.5;
    c = lerp(c, c * 0.7, eg);
    float alg = dD * North * saturate(1.0 - UV.y / 1.5) * smoothstep(0.4, 0.8, N1.x);
    c = lerp(c, c * float3(0.62, 0.68, 0.52), alg * 0.6);
}
else
{
    c = lerp(c, c * 0.9, dD * N1.x * 0.6);
}
Met = met;
AOo = ao;
Out = r;
return c;
"""

NOISE1_M, NOISE2_M = 7.31, 0.93

sys.path.insert(0, HERE)
import pack as P    # noqa: E402

CLASSES = P.CLASSES


def kind_of(name):
    """The shader's Kind for a finish of the chosen region pack."""
    return P.kind(P.finishes()[name])


def run_np(env):
    """Run BUILDMAT_CODE on numpy: env holds the inputs above as (H, W, 1) or (H, W, 3) arrays (scalars broadcast).
    Returns (colour, roughness, metallic, ao)."""
    import hlsl_np
    ns = hlsl_np.run(BUILDMAT_CODE, env)
    shp = env["uv"].shape[:2]
    full = lambda a, n: np.broadcast_to(np.asarray(a, float), shp + (n,)).astype(float)
    return full(ns["c"], 3), full(ns["Out"], 1)[..., 0], full(ns["Met"], 1)[..., 0], full(ns["AOo"], 1)[..., 0]
