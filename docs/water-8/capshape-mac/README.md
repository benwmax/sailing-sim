# Whitecap shape check on the Mac (the physics side)

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
wind. Not fixed here; waiting for the coordinator, since the PC's W4 owns the cap edge and texture.

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
- `cap{12,16,20}-open{,30,120,210}-crest-noaa.png`, `cap{12,16}-start*-crest-noaa.png`: the counted masks.
- `cap{12,16}-open.png`: beauty frames of the 300 deg open view; `cap16-beauty-vs-mask.png`: the side by side.
