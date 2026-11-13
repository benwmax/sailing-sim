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
// Boat fidelity 1 (docs/boat-fidelity-1), as M_BoatSurface does it: the boat's age and care (below) weather the surfaces,
// and the hull is wet up to the splash line and the deck with rain and spray (MPC_Boat):
// darker by each surface's porosity (gelcoat 0.1, non-skid 0.5, teak 0.6), water standing in the non-skid's grooves,
// glossy. (A sunlit white deck sits on the tone curve's shoulder, so these read smaller on screen than in albedo.)
// Texture loop (docs/texture-loop, as M_BoatSurface and Tools/texloop/wear.py): timeK (the years: yellowing, dock rash)
// and dirtK (what care removes: chalk, grime, scum, grey teak) from the same Age and Care.
// Hero ageing (docs/hero-ageing, Nov 9 2026): the bake used to carry the club boat's own wear (streaks, scum line, grimy
// non-skid, silvered teak), so -SailingBoatAge=0 could not make her new and Age 15 only added a little chalk on top. The
// game's bake is now clean (build_j22_hero.py --clean-bake) and every bit of wear comes from here, by the fleet's lines.
// Unset (Age -1, the player's boat in play) she is the club boat she was baked as: the texture loop's L2 (6 years, Care 0.5).
// The cabin interior (Exterior 0) keeps its own baked dirt and mildew and takes no weather; only the hull and the rudder
// (Waterline 1) carry the lake's line, and only the hull's topsides (IsHull 1) the dock rash.
float hAge = Exterior < 0.5 ? 0.0 : Age >= 0.0 ? Age : 6.0, hCare = Age >= 0.0 ? Care : 0.5;
float timeK = saturate(0.25 * (1.0 - exp(-hAge / 0.75)) + 0.75 * (1.0 - exp(-hAge / 18.0)));
float dirtK = saturate((1.0 - exp(-hAge)) * (0.15 + 0.85 * (1.0 - saturate(hCare))));
float3 nw = normalize(NW);
nw *= dot(nw, V) < 0.0 ? -1.0 : 1.0;          // two-sided: the generated shells (the cockpit sole) aren't all wound outward
float up = saturate((nw.z - 0.4) * 2.5);
float gcAll = X.b * (1.0 - X.r) * (1.0 - X.g);
float zcm = LP.z;                             // the hull's and the rudder's pivots sit on the design waterline
// Boat skins (docs/skins): a skin's paint over the bake. Each Paint* is a colour with alpha 1 where the skin names one
// (0, the default: the bake as it is, so a boat without a skin is unchanged). The bake's own shading and marks stay:
// the paint is scaled by the bake's brightness against that zone's clean colour (the style's gelcoat #F2F0EA, grey
// bottom #8E918F, non-skid #CDC5AE, bare teak), and the wear below then weathers the paint as it weathers the gelcoat.
// Zones: the hull group above the taped line (topsides) and below it (bottom), a boot stripe 7 to 9.5 cm over the
// waterline (j22_materials.py's band), the deck moulding's smooth gelcoat, its non-skid, and the teak.
float pLum = dot(c, float3(0.3, 0.59, 0.11));
float pExt = step(0.5, Exterior), pHull = step(0.5, IsHull) * pExt;
float pBelow = 1.0 - smoothstep(-0.3, 0.0, zcm);
c = lerp(c, PaintHull.rgb * min(pLum / 0.871, 1.2), PaintHull.a * pHull * (1.0 - pBelow));
c = lerp(c, PaintBottom.rgb * min(pLum / 0.278, 1.3), PaintBottom.a * pHull * pBelow);
float pBoot = smoothstep(6.85, 7.0, zcm) * (1.0 - smoothstep(9.5, 9.65, zcm));
c = lerp(c, PaintBoot.rgb * min(pLum / 0.871, 1.2), PaintBoot.a * pHull * pBoot);
float pDeckGroup = (1.0 - step(0.5, IsHull)) * (1.0 - step(0.5, Waterline)) * pExt;
c = lerp(c, PaintDeck.rgb * min(pLum / 0.871, 1.2), PaintDeck.a * pDeckGroup * gcAll);
c = lerp(c, PaintNonSkid.rgb * min(pLum / 0.559, 1.3), PaintNonSkid.a * pDeckGroup * X.r);
c = lerp(c, PaintTrim.rgb * min(pLum / 0.22, 1.5), PaintTrim.a * pDeckGroup * X.g);
// Chalk, as M_BoatSurface: the tops first, in 40 cm blotches (wear.BLOT), pale gelcoat toward chalk.
float ox = max(dirtK, 0.3 * timeK) * gcAll * (0.55 + 0.45 * up);
float2 blq = LP.xz / 40.0 + LP.yy / 55.0, blqi = floor(blq), blqf = smoothstep(0.0, 1.0, frac(blq));
float bl00 = frac(sin(dot(blqi, float2(12.99, 78.23))) * 43758.5), bl10 = frac(sin(dot(blqi + float2(1, 0), float2(12.99, 78.23))) * 43758.5);
float bl01 = frac(sin(dot(blqi + float2(0, 1), float2(12.99, 78.23))) * 43758.5), bl11 = frac(sin(dot(blqi + float2(1, 1), float2(12.99, 78.23))) * 43758.5);
ox = saturate(ox * (0.55 + 0.9 * lerp(lerp(bl00, bl10, blqf.x), lerp(bl01, bl11, blqf.x), blqf.y)));
float lum = dot(c, float3(0.3, 0.59, 0.11));
float3 chalk = lerp(lerp(float3(lum, lum, lum), float3(0.82, 0.80, 0.74), 0.5) * 1.02, c * 1.25 + lum * 0.35 + 0.01, saturate(1.0 - lum * 2.5));
c = lerp(c, chalk, 0.4 * ox);
float whiteG = saturate((min(c.r, min(c.g, c.b)) - 0.45) * 4.0);
c *= lerp(float3(1.0, 1.0, 1.0), float3(1.0, 0.965, 0.86), timeK * gcAll * whiteG);   // the years yellow it, kept or not
Rough = lerp(Rough, 0.72, ox);
// Grime, as M_BoatSurface: three octaves of value noise on the boat (37, 9 and 2.2 cm) ground into the decks where feet
// and water go, and a faint mottle in all the gelcoat.
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
float deckish = up * (1.0 - X.g) * (1.0 - IsHull);
float grime = saturate(vn * 1.8 - 0.6) * deckish * dirtK * (0.45 + 0.55 * X.r);
c = lerp(c, c * 0.76 + float3(0.014, 0.011, 0.007), grime);
Rough = lerp(Rough, min(Rough + 0.18, 0.9), grime);
c *= 1.0 + 0.05 * (vn - 0.5) * (1.0 - X.g);
// Non-skid, as M_BoatSurface (docs/texloop-nonskid): the years yellow the moulding a little; dirt gathers in grey-tan
// blotches with a 1.5 cm scuff mottle where feet go, and past the detail layer's reach as an even dust in the pattern.
float nsK = X.r * up;
c *= lerp(float3(1.0, 1.0, 1.0), float3(1.0, 0.975, 0.90), 0.5 * timeK * nsK);
float2 sq = LP.xy / 1.5 + float2(11.0, 0.0), sqi = floor(sq), sqf = frac(sq);
sqf = sqf * sqf * (3.0 - 2.0 * sqf);
float sc00 = frac(sin(dot(sqi, float2(12.99, 78.23))) * 43758.5), sc10 = frac(sin(dot(sqi + float2(1, 0), float2(12.99, 78.23))) * 43758.5);
float sc01 = frac(sin(dot(sqi + float2(0, 1), float2(12.99, 78.23))) * 43758.5), sc11 = frac(sin(dot(sqi + float2(1, 1), float2(12.99, 78.23))) * 43758.5);
float nsScuff = saturate((lerp(lerp(sc00, sc10, sqf.x), lerp(sc01, sc11, sqf.x), sqf.y) - 0.5) * 1.6 + 0.5);
float nsBlot = saturate((vn - 0.60 + 0.22 * dirtK) * 3.0) * smoothstep(0.2, 0.6, dirtK) * (0.35 + 1.3 * nsScuff);
const float3 nsDirt = float3(0.205, 0.198, 0.178);       // grey-tan lake dust and clay (Bean's foredeck photo)
c = lerp(c, nsDirt, saturate((0.3 + 0.45 * dirtK) * nsBlot) * nsK);
c = lerp(c, nsDirt, 0.55 * sqrt(dirtK) * 0.35 * (1.0 - fade) * nsK);
Rough = lerp(Rough, min(Rough + 0.1, 0.9), nsBlot * nsK);
// Teak (the bake is fresh bare teak now): it silvers as it's left, and darkens in the grain; oiling brings it back, so
// mostly dirt, but years of sun grey even a kept rail a little.
float tkGrey = saturate(max(dirtK, 0.35 * timeK)) * X.g;
float tkLum = dot(c, float3(0.3, 0.59, 0.11));
c = lerp(c, float3(tkLum, tkLum, tkLum) * float3(0.98, 0.97, 0.93) * 1.05, 0.85 * tkGrey);
c *= 1.0 - 0.2 * dirtK * X.g;
Rough = lerp(Rough, max(Rough, 0.62), tkGrey);
// Lake waterline, as M_BoatSurface (Tools/texloop/waterline/waterline.py): the scum line, the olive slime and the bottom
// film, from Dirt only (care scrubs it off). Fresh water: no barnacles. Below the deck only (up < 1), so a level sole
// never takes it.
float wlD = dirtK;
float wlK = (0.4 * pow(max(wlD, 1e-4), 0.3) + 0.3 * smoothstep(0.6, 1.0, wlD)) * step(1e-3, wlD);
float wlClay = smoothstep(0.45, 0.9, wlD);
float wlH = 1.0 + 1.6 * wlD + 5.0 * smoothstep(0.55, 1.0, wlD);
float wlSlimeK = 0.85 * smoothstep(0.4, 0.95, wlD), wlDepth = 4.0 + 16.0 * smoothstep(0.4, 1.0, wlD);
float3 wlX = float3(LP.x / 23.0, LP.x / 1.5, (LP.x + 0.3 * zcm) / 3.5);
float3 wlI = floor(wlX), wlF = frac(wlX);
wlF = wlF * wlF * (3.0 - 2.0 * wlF);
float3 wlN = lerp(frac(sin(wlI * 12.99 + float3(0.0, 7.1, 14.2)) * 43758.5), frac(sin((wlI + 1.0) * 12.99 + float3(0.0, 7.1, 14.2)) * 43758.5), wlF);
float wlTop = wlH + (0.25 + 0.08 * wlH) * (2.0 * (0.6 * wlN.x + 0.4 * wlN.y) - 1.0);
float wlLine = smoothstep(-0.6, -0.1, zcm) * (1.0 - smoothstep(wlTop - 0.2 - 0.06 * wlH, wlTop, zcm));
float wlU = saturate(zcm / max(wlTop, 0.1));
float wlDens = 0.75 + 0.45 * wlClay + 0.35 * smoothstep(0.6, 0.95, wlU);
wlLine *= clamp(wlDens * (1.0 + (1.0 - 0.85 * wlClay) * (0.6 * (wlN.z - 0.5) + 0.4 * (vn - 0.5))), 0.0, 1.3);
float wlFresh = Waterline * (1.0 - up);
float wlLineK = wlFresh * wlK * wlLine;
c = lerp(c, lerp(float3(0.179, 0.171, 0.147), float3(0.171, 0.119, 0.04), wlClay), wlLineK);
float wlBelow = wlFresh * (1.0 - smoothstep(-1.0, 0.0, zcm));
float wlFilm = wlBelow * 0.45 * wlD * (0.6 + 0.4 * vn);
c = lerp(c, float3(0.171, 0.187, 0.133), wlFilm);
float2 wlQ = float2(LP.x / 14.0, zcm / 3.0), wlQi = floor(wlQ), wlQf = smoothstep(0.0, 1.0, frac(wlQ));
float wlBlot = 0.65 * lerp(lerp(frac(sin(dot(wlQi, float2(12.99, 78.23))) * 43758.5), frac(sin(dot(wlQi + float2(1, 0), float2(12.99, 78.23))) * 43758.5), wlQf.x),
                           lerp(frac(sin(dot(wlQi + float2(0, 1), float2(12.99, 78.23))) * 43758.5), frac(sin(dot(wlQi + float2(1, 1), float2(12.99, 78.23))) * 43758.5), wlQf.x), wlQf.y) + 0.35 * vn;
float wlDp = saturate(-zcm / wlDepth);
float wlSlime = wlFresh * wlSlimeK * (1.0 - smoothstep(-0.5, 0.2, zcm)) * pow(1.0 - wlDp, 1.5) * smoothstep(0.3 + 0.25 * wlDp, 0.65, wlBlot);
c = lerp(c, float3(0.073, 0.089, 0.025), wlSlime);
float wlCover = saturate(wlLineK + wlSlime + 0.5 * wlFilm);
Rough = lerp(Rough, 0.8, wlCover);
// Dock rash and fender marks, as M_BoatSurface: soft sparse smudges in the topsides' fender band, most of them in the
// first year of use (timeK); care can't polish them out.
float2 cs = float2(LP.x / 45.0, zcm / 16.0);
float patchS = frac(sin(dot(floor(cs), float2(41.3, 17.7))) * 4375.5);
float2 fs = frac(cs) - 0.5;
float smudge = 1.0 - smoothstep(0.12, 0.45, length(fs * float2(1.0, 1.8)));
float scuff = 0.7 * saturate(4.0 * timeK) * IsHull * gcAll * step(abs(nw.z), 0.6) * smoothstep(25.0, 40.0, zcm) * (1.0 - smoothstep(70.0, 95.0, zcm)) * step(0.82, patchS) * smudge;
c = lerp(c, c * 0.78 + float3(0.01, 0.01, 0.008), scuff);
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
// Gelcoat (docs/gelcoat), as M_BoatSurface: the smooth gelcoat's clear coat (0.05; folded into the one lobe at the end), so the hull
// and deck mirror the sky and the shore; chalk and wet film as in M_BoatSurface. The rounded sheer and other convex
// edges (curvature from the normal's screen derivatives: under ~3 cm radius) take a crisp highlight.
float Coat = saturate(0.85 * gcAll * (1.0 - ox) * (1.0 - 0.7 * wlCover) * (1.0 - 0.6 * grime) + 0.5 * wetAll + 0.4 * pudK);   // hero ageing: scum and grime are matte
// docs/gelcoat-cost: the curvature and the corner grime below are close-up detail, so Lumen's surface-cache capture and the
// ray-traced hits (LUMEN_CARD_CAPTURE, RAYHITGROUPSHADER) skip them, and the base pass works them out only within reach.
float edgeK = 0.0;
#if !RAYHITGROUPSHADER && !defined(LUMEN_CARD_CAPTURE)
edgeK = length(fwidth(nw)) / max(length(fwidth(WP)), 0.01);
#endif
float sheer = smoothstep(0.12, 0.35, edgeK) * (1.0 - smoothstep(150.0, 900.0, Depth)) * max(gcAll, X.b) * (1.0 - ox);
Rough = lerp(Rough, min(Rough, 0.1), sheer);
Coat = max(Coat, sheer);
// Lumen's screen traces run before the sea (Single Layer Water) is drawn, so a reflection pointing steeply down found the
// hull and keel under the water: a dark dome on the lee topsides of a heeled boat (docs/lee-topside-patch/). Past 15 deg
// below the horizon the lobe is rough enough (0.45) that Lumen takes its radiance cache, and the coat fades. Above it the
// trace finds no water and returns the sky, so the reflection is dimmed to what the water would show there: its own
// Fresnel at that grazing angle (Spec scales F0 and F90).
float3 rv = reflect(-V, nw);
// docs/gelcoat-rt: rough enough for the radiance cache by 12 deg under the horizon, as before docs/gelcoat (Lumen traces
// every pixel under 0.4); the water's olive keeps its later start (seeW).
float guard = saturate((-rv.z - 0.08) * 6.0) * (1.0 - sheer), seeW = saturate((-rv.z - 0.25) * 4.0) * (1.0 - sheer);
Rough = lerp(Rough, max(Rough, 0.45), guard);
Coat *= 1.0 - guard;
float fw = 0.02 + 0.98 * pow(1.0 - saturate(-rv.z), 5.0);
Spec = lerp(1.0, fw + 0.04, saturate(-rv.z * 8.0));
// Realism audit 9 (the hull's half), as M_BoatSurface: a contact band darkening the topsides' last 25 cm over the water,
// and the water's dark olive in the gelcoat where its reflection points steeply down at it (the traced reflection is
// skipped there, above), most at a grazing look.
float aboveW = WP.z - WaterZ;
float contact = (1.0 - up) * (1.0 - smoothstep(0.0, 25.0, aboveW)) * step(-4.0, aboveW);
c *= 1.0 - 0.45 * contact;
float seeWater = seeW * (1.0 - up) * (1.0 - smoothstep(0.0, 120.0, aboveW));
float fresW = 0.04 + 0.96 * pow(1.0 - saturate(abs(dot(nw, V))), 5.0);
c = lerp(c, float3(0.045, 0.06, 0.05), seeWater * (0.18 + 0.6 * fresW) * max(gcAll, 0.3));
// Corner grime (docs/gelcoat): the global distance field just off the surface (AO 0 in a corner, 1 in the open) darkens
// the gelcoat and non-skid where dirt settles and the sky can't reach, and dulls the coat there. docs/gelcoat-cost: the
// two samples are taken only within 8 m (the grime fades out from 4 m) and never in the surface cache or RT hits; GDF is
// unused (a DistanceToNearestSurface node wired in so the material includes the global distance field).
float AO = 1.0;
#if !RAYHITGROUPSHADER && !defined(LUMEN_CARD_CAPTURE)
[branch] if (Depth < 800.0)
{
    float3 tw = GetTranslatedWorldPosition(Parameters);
    AO = sqrt(saturate(GetDistanceToNearestSurfaceGlobal(tw + nw * 8.0) / 8.0) * saturate(GetDistanceToNearestSurfaceGlobal(tw + nw * 24.0) / 24.0));
}
#endif
float cornerK = (1.0 - AO) * (1.0 - smoothstep(400.0, 800.0, Depth)) * (1.0 - X.g);
c *= 1.0 - 0.45 * cornerK;
Rough = lerp(Rough, max(Rough, 0.55), cornerK);
Coat *= 1.0 - cornerK;
// docs/gelcoat-cost: the clear coat folded into the one lobe's roughness (a 0.05 coat over the bake's ~0.22, weighted),
// not a hazy second lobe: the hero stays a simple slab, as it was before the gelcoat pass.
Rough = lerp(Rough, 0.05, Coat);
Rough = lerp(Rough, max(Rough, 0.45), guard);   // docs/gelcoat-rt: the fold mustn't pull the guarded band back under 0.4
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
    for pname, default, y in (("Age", -1.0, 1900), ("Care", 0.5, 1980), ("Exterior", 1.0, 1700), ("Waterline", 0.0, 1780), ("IsHull", 0.0, 1620)):
        p = node(mat, unreal.MaterialExpressionScalarParameter, -900, y)
        p.set_editor_property("parameter_name", pname)
        p.set_editor_property("default_value", default)
        extra[pname] = (p, "")
    wear = node(mat, unreal.MaterialExpressionVectorParameter, -900, 2060)
    wear.set_editor_property("parameter_name", "Wear")
    wear.set_editor_property("default_value", unreal.LinearColor(0, 0, 0, 0))
    extra["Wear"] = (wear, "RGBA")
    # Boat skins (docs/skins): a skin's paint per zone (alpha 0: the bake as it is), set by the pawn on the player's boat.
    for i, pname in enumerate(("PaintHull", "PaintBottom", "PaintBoot", "PaintDeck", "PaintNonSkid", "PaintTrim")):
        pv = node(mat, unreal.MaterialExpressionVectorParameter, -1300, 1620 + i * 80)
        pv.set_editor_property("parameter_name", pname)
        pv.set_editor_property("default_value", unreal.LinearColor(1, 1, 1, 0))
        extra[pname] = (pv, "RGBA")
    # Hero ageing (docs/hero-ageing): the waterline, blotches and grime are anchored to the part (cm; the hull's and the
    # rudder's pivots sit on the design waterline), as M_BoatSurface's LP.
    extra["LP"] = (node(mat, unreal.MaterialExpressionLocalPosition, -900, 2120), "")
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
    # Gelcoat (docs/gelcoat): DETAIL_CODE samples the global distance field itself (within 8 m, docs/gelcoat-cost); this node,
    # wired into an unused pin, is what makes the material include it.
    extra["GDF"] = (node(mat, unreal.MaterialExpressionDistanceToNearestSurface, -900, 2800), "")
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
    F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    for on, ot in (("Rough", F1), ("NormalOut", unreal.CustomMaterialOutputType.CMOT_FLOAT3), ("Spec", F1)):
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
    # Gelcoat (docs/gelcoat): a Substrate slab; Spec dims the reflection where it looks at the water (F0 0.04 and F90 1 at
    # Spec 1, the legacy pins' dielectric). docs/gelcoat-cost: one lobe (the coat is folded into Rough), no haze.
    slab = node(mat, unreal.MaterialExpressionSubstrateSlabBSDF, -200, 400)
    f0 = node(mat, unreal.MaterialExpressionMultiply, -350, 600)
    f0.set_editor_property("const_b", 0.04)
    MEL.connect_material_expressions(c, "Spec", f0, "A")
    for src, out, pin in ((c, "", "Diffuse Albedo"), (f0, "", "F0"), (c, "Spec", "F90"), (c, "Rough", "Roughness"), (c, "NormalOut", "Normal")):
        MEL.connect_material_expressions(src, out, slab, pin)
    MEL.connect_material_property(slab, "", unreal.MaterialProperty.MP_FRONT_MATERIAL)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


GLASS_CODE = r"""
// Texture loop, acrylic (docs/texloop-acrylic): the smoked portlights and fore hatch weather with the boat's Age and Care
// by BOAT_CODE's ACRYLIC_WEAR lines (copied from make_materials.py at import), and haze makes them less see-through.
// Age unset (-1, the player's boat in play) or the bilge water (Acrylic 0): as before.
float3 n = normalize(N);
float3 col = C.rgb;
float rough = 0.04, coat = 0.0, acHaze = 0.0;
float age = Acrylic > 0.5 ? Age : -1.0, care = Care;
float timeK = age >= 0.0 ? saturate(0.25 * (1.0 - exp(-age / 0.75)) + 0.75 * (1.0 - exp(-age / 18.0))) : 0.0;
float dirtK = age >= 0.0 ? saturate((1.0 - exp(-age)) * (0.15 + 0.85 * (1.0 - saturate(care)))) : 0.0;
float sunF = 1.0;
float3 lnA = abs(LN);
float2 acP = lnA.z >= max(lnA.x, lnA.y) ? LP.xy : lnA.y >= lnA.x ? LP.xz : LP.yz;
@ACRYLIC_WEAR@
Rough = rough;
Op = lerp(Opacity, 0.97, acHaze);
return col;
"""


def acrylic_wear():
    """BOAT_CODE's smoked acrylic lines (between the ACRYLIC_WEAR markers), so the hero's glass and the fleet's portlights
    weather alike."""
    import ast
    tree = ast.parse(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_materials.py")).read())
    code = next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "BOAT_CODE")
    return code[code.index("// ACRYLIC_WEAR >>>"):code.index("// ACRYLIC_WEAR <<<")]


def glass_material():
    """M_J22HeroGlass: smoked acrylic portlights and hatch, and the bilge water (translucent, lit at the surface).
    Texture loop, acrylic: Age, Care (Age -1 = unset) and Acrylic (1 the panes, 0 the bilge water) drive GLASS_CODE."""
    path = f"{DEST}/M_J22HeroGlass"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = ASSETS.create_asset("M_J22HeroGlass", DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    mat.set_editor_property("two_sided", True)
    col = node(mat, unreal.MaterialExpressionVectorParameter, -900, 0)
    col.set_editor_property("parameter_name", "Color")
    col.set_editor_property("default_value", unreal.LinearColor(0.03, 0.028, 0.025, 1.0))
    scalars = {}
    for i, (pname, default) in enumerate((("Opacity", 0.55), ("Age", -1.0), ("Care", 0.5), ("Acrylic", 1.0))):
        sp = node(mat, unreal.MaterialExpressionScalarParameter, -900, 200 + 80 * i)
        sp.set_editor_property("parameter_name", pname)
        sp.set_editor_property("default_value", default)
        scalars[pname] = sp
    nrm = node(mat, unreal.MaterialExpressionVertexNormalWS, -1100, 600)
    to_local = node(mat, unreal.MaterialExpressionTransform, -900, 600)
    to_local.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
    to_local.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_LOCAL)
    MEL.connect_material_expressions(nrm, "", to_local, "")
    geo = {"C": col, "N": nrm, "LN": to_local, "LP": node(mat, unreal.MaterialExpressionLocalPosition, -900, 700),
           "V": node(mat, unreal.MaterialExpressionCameraVectorWS, -900, 780), "Depth": node(mat, unreal.MaterialExpressionPixelDepth, -900, 860)}
    geo.update(scalars)
    c = node(mat, unreal.MaterialExpressionCustom, -500, 0)
    c.set_editor_property("code", GLASS_CODE.replace("@ACRYLIC_WEAR@", acrylic_wear()))
    c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    ins = []
    for pin in geo:
        i = unreal.CustomInput()
        i.set_editor_property("input_name", pin)
        ins.append(i)
    c.set_editor_property("inputs", ins)
    outs = []
    for oname in ("Rough", "Op"):
        o = unreal.CustomOutput()
        o.set_editor_property("output_name", oname)
        o.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        outs.append(o)
    c.set_editor_property("additional_outputs", outs)
    for pin, src in geo.items():
        MEL.connect_material_expressions(src, "", c, pin)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(c, "Op", unreal.MaterialProperty.MP_OPACITY)
    MEL.connect_material_property(c, "Rough", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


# Boat fidelity 1: the flat materials' kinds in M_BoatSurface's shared library (make_materials.py BOAT_SURFACE: 1 gelcoat,
# 3 stainless, 4 anodised aluminium, 6 varnished wood, 7 bare wood, 8 rubber, 10 sailcloth, 11 canvas, 12 galvanised or
# plain steel, 13 black moulded plastic, 14 woven webbing; 0 none), and how
# much each darkens wet.
HERO_SURFACE = {
    "Gelcoat": 1, "GelcoatHull": 1, "CabinGelcoat": 1, "InteriorLiner": 1, "InteriorSole": 1,
    "Stainless": 3, "Chrome": 3, "Galvanised": 12, "KeelBoltSteel": 12, "Bronze": 3, "Aluminium": 4, "CastAlu": 4,
    "TeakVarnish": 6, "PlywoodVarnish": 6, "AshVarnish": 6, "CunnLine": 9, "TeakWeathered": 7, "RubRail": 8, "ExtensionBlack": 8, "RigTape": 10, "BlackPlastic": 13, "CamBase": 13,
    "Cushion": 11, "SailBag": 11, "PFDNylon": 11, "Webbing": 14,
    "HatchAcrylic": 15, "TravLine": 9,   # packed with the woods since hero ageing (J22H_packs.json)
}
HERO_POROSITY = {6: 0.2, 7: 0.5, 8: 0.05, 10: 0.3, 11: 0.6, 3: 0.0, 4: 0.0, 12: 0.0, 13: 0.05, 14: 0.5}


def instance(name, parent):
    path = f"{DEST}/{name}"
    mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
        ASSETS.create_asset(name, DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    return mi


flat_instance = None   # set by materials(): MI_J22H_<name> on M_BoatSurface from the bake's flat values (main() uses it too)


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
        # Hero ageing (docs/hero-ageing): the lake's line on the hull and the rudder only; the cabin takes no weather.
        MEL.set_material_instance_scalar_parameter_value(mi, "Waterline", 1.0 if group in ("Hull", "Rudder") else 0.0)
        MEL.set_material_instance_scalar_parameter_value(mi, "Exterior", 0.0 if group == "Interior" else 1.0)
        MEL.set_material_instance_scalar_parameter_value(mi, "IsHull", 1.0 if group == "Hull" else 0.0)   # topsides: dock rash, no deck grime
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
            MEL.set_material_instance_scalar_parameter_value(mi, "Acrylic", 0.0)     # water: no acrylic wear
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[name] = mi
    # pc/boats-closeup (Nov 4): the hero's woods take M_BoatSurface's grain (BOAT_CODE, Grain 1) and the varnished ones its
    # clear coat; from the helm the companionway's varnished plywood hatch had read as a flat tan board, the ash tiller
    # and the weathered teak trims as paint.
    wood = ("PlywoodVarnish", "AshVarnish", "TeakVarnish", "TeakWeathered")

    def flat_values(name):
        # A pack entry whose material no longer reaches the bake (RigTape since the mast gear's turnbuckles took over
        # from j22_details', #550) keeps its pack index with a plain grey: the packs' indices are baked into the meshes.
        # A rope slot the bake did not report (an older bake) gets a plain grey line.
        v = META["flat_materials"].get(name)
        if v is None:
            unreal.log_warning(f"import_j22_hero: {name} is not in the bake's flat materials; plain grey")
            v = {"base_color_linear": [0.5, 0.5, 0.5], "roughness": 0.75 if name.startswith("Rope") else 0.5, "metallic": 0.0}
        gel = "Gelcoat" in name or name in ("HatchAcrylic", "TeakVarnish", "PlywoodVarnish", "AshVarnish")
        kind = HERO_SURFACE.get(name, 9 if name.startswith("Rope") else 0)   # fixed lengths of line (the tack strop) are rope
        return v["base_color_linear"], {"Roughness": v["roughness"], "Metallic": v["metallic"], "ClearCoat": 1.0 if gel else 0.0, "NonSkid": 0.0,
                                        "Porosity": HERO_POROSITY.get(kind, 0.1), "IsHull": 0.0,
                                        "Surface": float(kind), "Grain": 1.0 if name in wood else 0.0}

    global flat_instance

    def flat_instance(name):
        mi = instance(f"MI_J22H_{name}", surface)
        c, values = flat_values(name)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(c[0], c[1], c[2], 1.0))
        for pname, value in values.items():
            MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        return mi

    for name in META["flat_materials"]:
        # A bake before Nov 9 2026 also listed Blender's duplicates (Aluminium.001): their faces export as the base name's
        # slot, and a '.' in an asset name fails the save (the import exited 1), so they are skipped.
        if name in out or "." in name:
            continue
        out[name] = flat_instance(name)
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
    for part, nanite in (("Hull", True), ("Mast", False), ("Boom", True), ("Rudder", True), ("Interior", True), ("Glass", False), ("TillerExt", True)):
        name = f"SM_J22H_{part}"
        if part in ("Interior", "Glass", "TillerExt") and not os.path.exists(os.path.join(SRC, "fbx", name + ".fbx")):
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
            if mi is None and key.startswith("Rope"):
                # Fixed lengths of line on a game part (#561's jib tack strop, the interior's sail bag tie) keep their rope
                # material's slot; the game's live ropes never reach it. bake_j22_hero.py reports rope materials with the
                # others since Nov 9 2026; an older bake gets a plain grey line here rather than a failed import.
                mi = mats[key] = flat_instance(key)
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
