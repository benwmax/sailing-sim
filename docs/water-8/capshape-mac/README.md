# Whitecap shape on the Mac: the check, then the mask fix

## The fix (the mask; the shading is the PC's W4)

Two physics changes, nothing in the beauty pass (the foam's opacity, albedo, lace, streaks and residue are as they were):

- **Cover by wind.** `AWaterSurface::DrawnFoldScaleAt(MeanKnots)` replaces the constant `DrawnFoldScale` (0.85, fitted at
  20 kn only). The drawn fold ran deeper than its CPU copy as the wind fell: the hard fold alone (`-SailingDebugFoam=3`,
  no ramp, no lace, no hash) capped 3.3x the lake's target at 12 kn, 2.4x at 16, 1.55x at 20, the same excess as the
  crest masks, so the shading's 0.05 ramp is not the cause. Each wind's excess over its logged solve slope
  (`-SailingDebugCaps`: 0.021-0.032 per e-fold) gives the scale that lands it: 0.94 at 12 kn, 0.915 at 16, 0.88 at 20.
  Now 0.94 - 0.0075 (U - 12 kn), held at 0.94 below 12 kn (Callaghan's onset from #76 sets the target there, unchanged)
  and never under W8's 0.85. Likely cause, not isolated: the long trains lose depth to the mesh's vertex interpolation
  where the chop's blurred fold loses little to the texture filter, and the long trains carry more of the fold as the
  wind rises.
- **Cap size by wind.** `FWaveDetail::CapBlurMeters(WindMs)` replaces the fixed 2-texel (0.36 m) blur of the displacement
  behind `JCap`: 0.36 m x (U / 20 kn)^0.85 under 20 kn, down to one texel (0.18 m, about 9 kn), held at 0.36 m from
  20 kn up (the fold table and `CapSlopeAt` are fitted on it; a 0.43 m blur at 25 kn read the table's mip 1 30-60 % over
  the grid). A fractional box (end taps weighted by the fraction), so the caps grow smoothly. The exponent: Monahan's
  cover falls 5.8x from 20 to 12 kn (U^3.41); splitting that fall evenly in log between the caps' number and their area
  gives area as U^1.7 and length as U^0.85, anchored at W8's 20 kn fit (about 1 m caps, 0.44 m^2 each). Breaking
  crests slow with the wind (Phillips's Lambda(c), Melville and Matusov 2002), which is the direction, not the exponent.
- The finer light-air blur folds deeper, so the pre-solve fallback `FoamThresholdAt` drops 0.042 at 10 kn, easing out
  by 16 kn (0.671 at 10 kn, was 0.713; mirrored in M_WaterV4's `capBase`). It only draws until the first solve.
- M_Water (Low) has its own procedural caps (no fold, no `JCap`): it doesn't share the mask and is unchanged.

### Cover, 10-80 m, open water (crests only, no AA, four headings a run)

| Wind | Lake target (0.4 x Monahan) | Before | After, run 1 | After, run 2 | After, pooled (8 stills) | Pooled / target |
|---|---|---|---|---|---|---|
| 12 kn | 0.076 % | 0.281 % (3.7x) | 0.058 % | 0.117 % | 0.088 % | 1.16x |
| 16 kn | 0.20 % | 0.462 % (2.3x) | 0.221 % | 0.212 % | 0.217 % | 1.07x |
| 20 kn | 0.44 % | 0.645 % (1.5x) | 0.501 % | 0.497 % | 0.499 % | 1.14x |

At 12 kn four stills hold only 27-34 caps, so a run swings by 2x; 16 and 20 kn repeat within 5 %. Hard fold
(`-SailingDebugFoam=3`) before 0.252 / 0.472 / 0.682 %, after 0.053 / 0.230 / 0.517 %. Run 1 was the build before the
fallback refit and the 20 kn hold, which don't touch 12-20 kn once the threshold is solved.

### Cap size (5-60 m, crests)

| Wind | Caps, before / after (4 stills) | Length area-weighted, before / after | Length p90, before / after |
|---|---|---|---|
| 12 kn | 76 / 27 | 2.38 / 1.41 m | 2.09 / 1.61 m |
| 16 kn | 88 / 57 | 2.48 / 2.20 m | 2.05 / 1.72 m |
| 20 kn | 86 / 76 | 3.34 / 3.26 m | 2.44 / 1.97 m |

12 kn caps are now about 40 % shorter than 20 kn ones and a third as many, where before they were 70 % as long and
as many. On the grid (`SailingSim.Visual.WhitecapSize`, the chop at each wind's lake cover): 3.2 caps a 23 m tile of
0.13 m^2 each at 12 kn, 5.8 of 0.18 m^2 at 16, 9.9 of 0.23 m^2 at 20.

### Tests

- `SailingSim.Visual.WhitecapsSeen`: 12 and 16 kn added (the table's mips and the solved threshold on other water).
- `SailingSim.Visual.Whitecaps`: 12 and 16 kn added; the fallback refit keeps 10 kn at 0.8x Monahan (was 3.9x with the
  finer blur).
- `SailingSim.Visual.WhitecapOnset`: at 12, 16 and 20 kn the full law, and the threshold solved as the renderer does
  (samples scaled by `DrawnFoldScaleAt`) caps the target on other water within 35 %; the scale's shape.
- `SailingSim.Visual.WhitecapSize` (new): the blur's law, and caps smaller and rarer at 12 kn than at 16 and 20.

### Files added for the fix

`cap{12,16,20}-open{300,30,120,210}-crest-after.png` (+ `.camera.json`): the final crest masks;
`cap{12,16,20}-open-after.png`: beauty frames of the 300 deg view; `cap{12,16}-open-before.png`: the same before;
`before-after.png`: beauty at 12 and 16 kn and the 12 kn crest mask, before and after. The `*-fold-*` and `*-after1`
rows in `scenes.csv` are the hard-fold and first-pass runs (stills not kept). Counts: `count_caps.py <stills>`.

# The check (before the fix)

Question from the PC's Ultra and High stills after #76 (crops on `ultra-showcase`,
`docs/graphics-8/ultra/caps-16kn-lake-crop.png`, `caps-12kn-lake-high-crop.png`): each cap reads as a flat, opaque white
ellipse with a hard edge. Are the caps' size, cover and placement right against W8 (`docs/water-8/whitecaps`), and is the
decal look the mask (physics) or the shading (look)?

Main bec89c54, High, the lake, AfternoonBreeze at 15:30, gust intensity 0.06. Uncooked runs (`scripts/capture-scenes.sh
16`, rows in `scenes.csv`), counted by `count_caps.py` (each pixel on the plane z = 0 from `camera.json`; cover by water
area; caps are 8-connected clusters measured along their major axis on the water).

## Answer

**Placement: yes. Cover: no at 12 kn, marginal at 16 kn. Size: about right at 20 kn but it doesn't shrink with the wind.
The decal look is the shading, not the mask.**

| Wind | Lake target (0.4 x Monahan) | Drawn crest cover, 10-80 m | Ratio | Caps counted (4 stills each) | Cap length p90 | Area-weighted length |
|---|---|---|---|---|---|---|
| 12 kn | 0.076 % | 0.28 % (north lake), 0.25 % (by the start) | 3.3-3.7x | 76, 62 | 2.1, 2.5 m | 2.4, 2.6 m |
| 16 kn | 0.20 % | 0.46 %, 0.48 % | 2.3-2.4x | 88, 69 | 2.1, 3.0 m | 2.5, 3.2 m |
| 20 kn | 0.44 % | 0.65 % (north lake) | 1.5x | 86 | 2.4 m | 3.3 m |

Each row pools four headings (300, 30, 120, 210 deg) of a free camera 6 m over open water looking 20 deg down, about
10,900 m^2 of water from 10 to 80 m; crests only (`-SailingDebugFoam=2`), anti-aliasing off (`-SailingAA=0`) so every
pixel is binary. "North lake" is 10.9 km north of the club (W8's open-water spot), "by the start" 5.3 km north. Crests
plus residue (`-SailingDebugFoam`, the `*-open*-debug-noaa` stills) gives the same within 2 %: the residue adds almost
nothing.

- **Cover.** At 20 kn the screen is 1.5x its target, as W8 found (its 20 kn bands were 0.3-1.4 %). Below that, the
  excess grows: 2.3x at 16 kn and 3.5x at 12 kn, past the test's factor of 3. Monahan's law grows 5.8x from 12 to
  20 kn; the drawn cover grows 2.3x. The CPU solve holds 14 kn on the grid (`WhitecapsSeen`, 0.163 % against 0.129 %),
  so what drifts is the drawn fold against its CPU copy. `DrawnFoldScale` (0.85) was fitted at 20 kn only. Cover is
  exponential in the threshold, with a slope (`CapCal.y`) of about 0.012-0.018 per e-fold at 12 kn against 0.028 at
  20 kn. So a fold bias of 0.02 that costs 2x at 20 kn costs 3-4x at 12 kn. This is a likely cause, not isolated.
- **Size.** The caps that hold most of the white are 2-3 m long (area-weighted) at every wind, with a p90 of 2-3 m.
  W8's "about 1 m caps at 20 kn" (0.44 m^2 each) agrees at 20 kn: 86 caps, 0.8 m^2 each. But the blur behind
  `FWaveDetail::JCap` is a fixed 0.36 m (`CapBlurTexels`), so 12 kn caps come out as big as 20 kn ones. Real caps
  shrink with the breaking wave, and at 12 kn they are small and occasional.
- **Placement.** The caps sit on crest tops, lying along the crests (median aspect 1.7-2.4). This holds by
  construction: the choppy displacement's Jacobian is lowest at the crests.
- **The decal look is the shading.** `cap16-beauty-vs-mask.png` sets the beauty pass beside the binary mask, same frame,
  16 kn. In the mask a near cap is a dense core with a dithered fringe about a third of its radius wide (probability
  falling off), elongated and ragged. The beauty pass draws the same cap, core and fringe, as one uniform sheet of white
  with a hard edge. The foam is `TopMaterialOpacity = Foam` with a constant 0.85 albedo and roughness 0.7. Against water
  of albedo about 0.05, even 0.3-0.5 opacity tonemaps near white (the fringe pixels measure 150 of 255 against 72 for
  the water and 186-218 for a full cap). The lace floor of 0.8 keeps the interior flat. Nothing gives it thickness,
  normals, a leading edge or a trailing streak (the residue is 0.25 x pattern and barely shows). The mask's ellipse
  comes from the box-blurred Jacobian: rounder than a real cap, but softer than what is drawn.

So two physics items: the cover's wind dependence at 12-16 kn (too many caps), and cap size that doesn't scale with
wind. Both fixed above; the PC's W4 owns the cap edge and texture.

## Views asked for (helm-eye and chase)

`cap{12,16}-twa{50,110}-{helm,chase}.png` and their `-debug` masks (crests plus residue, with TAA). These views see
little water near the camera, and TAA blurs the debug view's hashed pixels (salt spreads into crosses, and moving caps
dim below the count threshold). So their counts run low and noisy: 12 kn 0.01-0.06 %, 16 kn 0.08-0.30 %. They are
stills for the eye; the cover above comes from the open-water set.

## Debug-view artefact

Every binary debug still has a uniform floor of isolated white pixels: 0.27-0.29 % of the screen, the same per screen
row at any distance. It sits on the shader's per-pixel hash (half of these pixels have a hash under 0.01, against 1 % of
all pixels), so it isn't cover on the water. `count_caps.py` drops one- and two-pixel clusters and reports them as
`isolated_pixel_floor_pct`. W8's TAA counts included it in part.

## Files

- `scenes.csv`: every run's arguments. `count_caps.py <stills>` prints per-still bands and a pooled line per wind.
- Here: the counted open-water masks `cap{12,16,20}-open{300,30,120,210}-crest-noaa.png` (+ `.camera.json`) and the
  beauty frames `cap{12,16}-open-before.png`. The rest of the check's stills (helm-eye and chase views, the start-area
  masks, `cap16-beauty-vs-mask.png`, telemetry) are on `claude/project-thread-b1sd6t`.
