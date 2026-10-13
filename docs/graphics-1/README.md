# Graphics G1: the sky

The first phase of the Graphics, UI and Levels plan. The clouds are rebuilt:
- **Noise:** our own baked noise, so no cloud repeats.
- **Grain:** traced to aliasing under coarse ray steps and fixed at the source.
- **Shapes:** cumulus built the way Guerrilla's Nubis builds them.
- **Ultra:** a new quality tier for Bean's RTX 4090 PC.

Medium and High still clear their gates on every view.

![Afternoon cumulus](captures/j22-heavy-chase.png)

## What was wrong (blind round 6)

Bean caught all 20 stills, and the sky gave the game away in 4 of the 10 game frames. Two causes:

- **Repetition.** The clouds took their shape from one engine noise volume sampled at two sizes, so the same puff came back every 0.6 to 1.25 km.
- **Grain.** Three things, measured one at a time (high-frequency energy in a sky crop, `/tmp` grain script in the session notes):
    1. The noise was sampled at full detail (3 m texels) under ray-march steps of about 190 m (80 samples over 15 km), which aliased into speckle.
    2. The storm's shelf tiers and the old V5 banding varied every 115 to 140 m in altitude. That is finer than a step, so they could only alias; they are gone.
    3. The engine's default cloud reconstruction (quarter-resolution trace, bilateral upsampling) left the rest.

## What changed

### Noise (`Tools/clouds/make_cloud_noise.py`, `scripts/import_cloud_noise.py`)

- `T_CloudShape` 128³ RGBA: Perlin-Worley plus three Worley fBm octaves (the Nubis layout).
- `T_CloudDetail` 64³: three Worley octaves.
- `T_CloudCurl` 128²: a curl field.
- All tile in every axis. They are imported as volume textures from 2D atlases; `make-content.sh` bakes them when missing.

The shader:
- samples the shape at 0.25 cycles/km, warped by the curl field at 0.077 cycles/km (±1.3 km);
- samples the detail at 1.5 cycles/km;
- chooses each mip from what a sample covers (never finer than a march step, 160 m).

`SailingSim.Visual.CloudNoise` replays that sampling on the CPU along a 40 km line. Autocorrelation at 2–15 km lags is 1.00 for the unwarped volume, 0.31 for the warped field and 0.40 for the weather map.

### Shapes

- **Weather map:** 1024² over 64 km, 62.5 m cells (was 256², 250 m), uploaded as half floats.
- **Cumulus:**
    - cells line up in streets along a steady wind aloft;
    - more grow over the heated land;
    - presence ramps over a whole standard deviation, so the shader raises each cell's top with it: domes, not prisms;
    - the shader uses the Nubis coverage remap, so the billow noise's iso-surface is the outline;
    - erosion is wispy at the base and billowed at the top.
- **Lighting:**
    - extinction 0.045 to 0.065 per metre (real cumulus, was 0.02);
    - a sharper forward lobe (silver linings);
    - less multiple-scattering brightening (grey bases);
    - a third scattering octave.
- **Storm:**
    - the anvil is a thin ice veil, not a second dark lid;
    - its walls bulge by about 600 m;
    - the shelf is shaded smoothly: a dark base and a lighter front;
    - `-SailingStormDelay=<s>` holds the front back for stills.

### Rendering, per tier (`VisualPipeline.cpp`, `SailingEnvironment.cpp`)

| | Medium | High | Ultra (desktop GPU) |
| --- | --- | --- | --- |
| Cloud trace | quarter res + reconstruction | quarter res + reconstruction | half res (mode 1) |
| Upsampling | bilinear + jitter, closest (3), clamped history | same | same |
| View samples | 72 | 80 | 160, scale 2 |
| Shadow rays | over 4 km (was 15) | over 4 km | over 4 km, scale 4 |
| Anti-aliasing | TAA, 67% | TAA, native | TSR, native |
| Other | | Lumen HW RT, MegaLights, governor | Epic scalability, Lumen HW RT at Epic GI, MegaLights, no governor |

Upsampling mode 3 with clamped reprojection measured 60% less grain than the engine defaults in a storm sky, with no halo on the rig against the sky.

Half-resolution tracing is the cleanest but costs about 4x. On the Mac it doesn't fit High: with fewer samples to pay for it, it was grainier than mode 0.

## Frame rate (`bench.csv`, packaged build, 12 s per view)

V7 → G1, with the clouds-and-fog GPU slice in ms. The gate is Medium ≥ 60 and High ≥ 45 on every view.

| View | Medium fps | Medium clouds+fog | High fps | High clouds+fog |
| --- | --- | --- | --- | --- |
| beam8 | 92.8 → 93.7 | 1.76 | 52.1 → 52.3 | 4.03 |
| beat15 | 86.9 → 93.3 | 1.78 | 49.2 → 50.4 | 3.42 |
| storm | 83.2 → 87.0 | 3.40 | 49.4 → 51.8 | 6.36 |
| marina | 88.9 → 89.5 | 1.50 | 47.1 → 47.3 | 2.98 |
| coast-day | 87.9 → 86.4 | 1.68 | 49.5 → 48.8 | 2.43 |
| coast-night | 117.4 → 118.9 | 1.64 | 65.8 → 64.7 | 3.13 |
| gulf-sea | 113.7 → 116.2 | 1.27 | 67.2 → 67.1 | 2.89 |
| helm-eye | 86.0 → 90.4 | 1.74 | 48.6 → 51.3 | 2.31 |
| slip | 75.7 → 76.4 | 1.51 | 46.7 → 48.3 | 3.40 |
| bridge | 95.7 → 96.9 | 1.26 | 52.0 → 52.5 | 2.45 |
| marina-night | 89.1 → 89.7 | 2.30 | 56.9 → 56.5 | 4.22 |

The gate is met: the lowest views are 76.4 (Medium, slip) and 47.3 (High, marina). The storm view is faster than V7 on High (49.4 → 51.8): the shadow rays' shorter distance pays for the rest.

**Ultra on the Mac** (only to confirm it runs; the 4090 is its target):
- beam8: 23.6 fps, clouds 26.3 ms;
- storm: 12.1 fps, clouds 62.2 ms.
These ran while the test suite was also running.

## Comparison (`compare/index.html`) and the skies blind pack (`blind/`)

Before is V7's capture of the same scene. Light and sky shown; the other categories are unchanged from V7.

| Scene | Light | Sky | Note |
| --- | --- | --- | --- |
| j22-heavy-chase | 2 → 2 | 2 → 2 | Cumulus from the baked noise: varied cauliflower puffs, flat grey bases, no repeated puff (V7 drew the same one every 1.25 km). |
| j22-light-chase | 2 → 2 | 2 → 2 | A scattered fair-weather field over the far shore; each cloud different. |
| j22-moderate-chase | 2 → 2 | 2 → 2 | Cumulus with lit tops and shadowed undersides; the old pancake layering is gone. |
| j22-helm-reservoir | 2 → 2 | 2 → 2 | Broken cumulus through the rig; edges smooth (the speckle was aliasing of 3 m noise under 190 m ray steps). |
| j22-actioncam-lake | 2 → 2 | 2 → 2 | Cumulus and their reflections; unchanged otherwise. |
| rh-drone-cat | 2 → 2 | 2 → 2 | No sky in frame; cloud shadows on the lake from the new field. |
| rh-c30-evening | 2 → 2 | 2 → 2 | Late-day cumulus lit warm from the side, darker bases. |
| storm-lake | 3 → 2 | 3 → 3 | Rebuilt from the water facing the storm (the old scene looked away from it): a lit storm band over a dark base and the bright gap above the lake. Not met (sky 3): the lit storm cloud still looks frosted at full size (grain 6.6 to 4.1 on the measure) and the shelf reads as a cumulonimbus band, not laminar tiers. |
| squall-lake | 2 → 2 | 2 → 2 | Storm towers and the dark base behind the Catalina 30; grain down by a third. |
| gulf-passage | 2 → 2 | 2 → 2 | Offshore cumulus; unchanged otherwise. |
| bay-hobie | 2 → 2 | 2 → 2 | Overcast deck; unchanged. |
| sunfish-reach | 2 → 2 | 2 → 2 | Overcast deck; unchanged. |

storm-lake's definition changed (`docs/phase-8/reference-scenes.csv`): the old camera looked away from the storm. It now stands on the water facing it, with the front held back 300 s.

**Skies blind pack** (https://claude.ai/artifact/K9agAvuTVSx2vQPMvSTh4Q): ten stills, five Commons cloud photos (two shelf clouds, a cumulonimbus, two fair-weather fields) and five game frames. The answer key is in `blind/answer-key.csv`. My own read: the game's storm clouds are still lumpy where real shelves are laminar, and some cumulus look too sculpted. Expect most game frames to be caught.

## Tests

- 89 of 89 pass, including the new `SailingSim.Visual.CloudNoise` and Ultra checks in `SailingSim.Visual.TierSettings`.
- Physics unchanged: the anvil density only feeds the sunlight transmittance.

## Open items

- **storm-lake sky (3):**
    - the lit storm cloud still looks frosted at full size (grain 6.6 → 4.1);
    - the shelf reads as a cumulonimbus band without laminar tiers. Tiers finer than the march step can't be drawn volumetrically, so this needs a hero shelf (a sculpted volume) or a denoiser.
- **Distant cumulonimbus:** the tower and rain shafts still show vertical bars from the rain-streak noise. It was left out of the blind pack.
- **Cloud streets seen edge-on** can still read as rows.
