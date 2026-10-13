# Visual V4: water

On Medium and High the water is redrawn:
- **Waves:** the physics' own long waves, plus an FFT of the same sea for everything shorter.
- **Whitecaps:** where the drawn crests fold.
- **Wakes:** the waves every hull pushes up.
- **Light:** the water's own colour and clarity per water body (Single Layer Water).

The physics is unchanged. `FWaveField` still floats the boat; the polar gate is untouched. Low keeps the Phase 8 water.

![Beam reach, High](bench/beam8-high.png)

## Waves (`M_WaterV4`, `WaveDetail.h`)

- **Long waves are the physics' trains.** FWaveField's first eight frequency bands (24 trains, 3.6 m and longer: the ones
  that lift and pitch the boat) are drawn exactly. They use Gerstner choppiness 1.5: vertices move toward the crests, so
  crests sharpen and troughs flatten. Per vertex, the shader computes height, displacement, slopes and the fold
  (Jacobian), then interpolates them to the pixels.
- **Short waves from an FFT of the same spectrum.** `FWaveDetail` (SailingPhysics, standalone) lays the same fetch-limited
  JONSWAP spectrum and cos² spreading on FFT grids, with the physics' normalization:
  - chop from 3.6 m down to 0.4 m on a 128² grid over 23 m;
  - on High, capillary-gravity ripples on a 64² grid over 3.1 m.

  Thousands of modes with random phases replace the 24 short physics trains, three per band; their crisscross was what
  gave the water away in blind test round 1.
- **Filtering.** The grids are evaluated off the game thread at 30 Hz, blended to the frame and uploaded as mip-mapped
  half-float textures. Distant short waves average out instead of sparkling. The textures also carry squared slopes, so
  the slope variance a mip averages away comes back as roughness (LEAN mapping) and the glitter path keeps its width.
- **Shelter.** In a lee the short waves and ripples shrink with the local wind (the shelter map and puffs, from the
  cat's-paw map).
- **Why not Niagara.** The brief said a Niagara GPU FFT. I did it on the CPU instead, for three reasons:
  - it is the same code the test runs, so the drawn surface is checked against the physics;
  - it costs 0.2 ms of game-thread time on a worker-fed path (`water_cpu_ms` 0.35–0.67 in total);
  - Niagara's GPU simulation stages can't be authored from scripts here.

  The GPU only samples textures.

### Match with the physics (`SailingSim.Visual.WaveMatch`)

The test mirrors the vertex formula on the CPU, inverting the choppy displacement to find the drawn height at a point,
and compares it with `FWaveField::Height` over 4,500 points at three times. The match is **exact for the long waves
and statistical for the whole surface**:

| Wind | Hs physics | Hs drawn | Long waves' share of variance | Long part, no choppiness | Long part, choppiness 1.5 | Whole surface, point by point |
| --- | --- | --- | --- | --- | --- | --- |
| 8 kn | 0.230 m | 0.230 m (0%) | 87% | exact (2.5e-6 m) | 0.6 cm RMS | 3.2 cm RMS |
| 15 kn | 0.426 m | 0.426 m (0%) | 94% | exact | 1.5 cm RMS | 4.3 cm RMS |
| 22 kn | 0.629 m | 0.634 m (+1%) | 96% | exact | 2.5 cm RMS | 5.3 cm RMS |

- **Within tolerance.** The drawn significant height is within the Phase 8 tolerance for the lake's waves (±20%) at
  every wind.
- **Choppiness.** It moves the long waves only at second order (crest sharpening).
- **The remaining 3–5 cm.** This is the short waves (under 3.6 m), a different random draw from the same spectrum.

### Whitecaps (`SailingSim.Visual.Whitecaps`)

Foam forms where the drawn crests fold: the Jacobian of the long × short choppy map falls under 0.6. The Beaufort scale
is now a check, not the source. Coverage against Monahan's whitecap law (W = 3.84e-6 U^3.41):

| Wind | 6 kn | 10 kn | 14 kn | 20 kn | 25 kn |
| --- | --- | --- | --- | --- | --- |
| Drawn | 0.01% | 0.09% | 0.36% | 1.18% | 2.04% |
| Monahan | 0.02% | 0.10% | 0.32% | 1.09% | 2.33% |

How the foam looks:
- **Crests.** Crest foam is lacy, not flat patches.
- **Residue.** Thin streaks of residue lie along the wind behind the crests.
- **Far away.** Whitecaps become their average whiteness from the same law.
- **Spray (High).** Droplets are thrown up where a bow slams into a wave, and the wind tears them off breaking crests. They are CPU particles drawn as instanced droplets.

## The water the boats push around (`WakeGrid.h`, `SailingSim.Visual.WakeGrid`)

A grid around the player's boat (38 m on Medium, 64 m on High) solves the linear deep-water wave equation **exactly, mode
by mode in Fourier space**, on a worker thread.
- **Forcing.** Every hull in range presses on it: the player, the AI sailboats (their physics hulls, heeled and heaved)
  and the power vessels.
- **Patterns.** A moving pressure is what makes ship waves, so these come by themselves:
  - the bow wave;
  - the transverse and diverging waves of the Kelvin wake;
  - the stern wave;
  - the hollow along a heeled hull.

  Test at 6 kn: 99% of the wake's energy lies inside a 24° wedge. Once the boat stops the wake dies away.
- **Why not iWave.** I tried Tessendorf's iWave first. On a 25 cm grid its truncated kernel gives every wavelength
  nearly the same frequency, so a 6 kn boat left 1.7 m waves instead of 6 m; the spectral solver fixes that.
- **Foam.** It forms where the surface moves fast and in the transom's turbulence, as a narrow bubbly band that fades
  within a couple of lengths.

## Light (Substrate Single Layer Water)

The water absorbs and scatters light itself (`WaterBodyFor`). The colour was calibrated against the reference clips:
from a boat the sky's reflection dominates, and the body only tints it.

| Water body | Look | Visibility |
| --- | --- | --- |
| Ray Hubbard | Olive grey-green | About half a metre |
| Galveston Bay | Grey-green silt | About half a metre |
| Gulf off Galveston | Slate blue-green | Several metres |

- **Shallows and hull.** The shallows show the bed, and the hull shows through below the waterline (refraction).
- **Sun glint.** It sharpens on a calm morning and broadens with the wind (plus the LEAN term above).
- **Puffs.** Ruffled water in a puff reflects less sky.
- **Rain.** It rings the surface and, heavy, beats down the short waves and greys it with splashes.
- **Shore.** A shore depth map built on a worker around the boat (512 m at 1 m) drives three effects:
  - waves shoal and steepen;
  - waves die on the beach;
  - foam laps at the waterline, the riprap and the docks.

Frame rate:
- **The bed.** The terrain no longer meshes the lake bed deeper than the water lets you see (`HideBelow`: 3.5 m on the lake and bay, 15 m offshore). Drawn behind the water it cost about 6 fps on High, in shading and in extra shadow pages.
- **Reflections.** Water reflections are traced at half resolution on Medium and High.

## Frame rate and GPU (packaged build, `bench.csv`)

| View | Low | Medium (V3) | High (V3) | Medium GPU ms (base / Lumen / water / clouds+fog) | Water CPU ms (Medium / High) |
| --- | --- | --- | --- | --- | --- |
| beam8 | 118.5 | 82.4 (82.6) | 49.0 (45.6) | 11.55 (3.31 / 1.39 / 1.57 / 4.12) | 0.362 / 0.633 |
| beat15 | 118.4 | 84.0 (85.5) | 52.7 (46.7) | 9.76 (3.07 / 1.5 / 1.65 / 2.41) | 0.365 / 0.623 |
| storm | 118.7 | 118.7 (118.8) | 78.2 (65.3) | 7.71 (2.82 / 1.45 / 1.64 / 0.61) | 0.376 / 0.609 |
| marina | 118.3 | 86.9 (89.2) | 56.7 (55.2) | 12.03 (4.34 / 1.55 / 1.59 / 3.53) | 0.348 / 0.572 |
| coast-day | 118.3 | 77.0 (80.2) | 47.6 (46.6) | 12.07 (3.89 / 1.74 / 1.59 / 3.74) | 0.357 / 0.583 |
| coast-night | 119.5 | 92.3 (98.8) | 60.3 (60.4) | 10.15 (2.12 / 1.65 / 1.44 / 3.63) | 0.365 / 0.545 |
| gulf-sea | 118.6 | 94.7 (100.1) | 60.1 (56.8) | 9.78 (2.35 / 1.32 / 1.63 / 3.32) | 0.395 / 0.599 |
| helm-eye | 118.5 | 83.2 (88.2) | 50.7 (47.1) | 12.29 (3.52 / 2.08 / 1.4 / 4.3) | 0.354 / 0.629 |

Every view clears both bars: Medium is at or above 60 (77–119) and High at or above 45 (47.6–78). The water costs 1.4–1.7 ms
of GPU on Medium, against a 2.5 ms budget. Water CPU is the game-thread share: the FFT frames blend and upload; the wake
grid and the shore map step on workers.

How the water was paid for (High beam view, which was the tightest):
1. A first pass cost about 2 ms more than V3, almost all in the vertex shader. Fixes:
   - The long waves now come straight from the band edges, with no branches.
   - Their slopes are computed per vertex instead of per pixel.
   - High uses five rings instead of six.
   - Water reflections are traced at half resolution.
2. The rest was the lake bed. Behind Single Layer Water it gets shaded and marks its own shadow pages, so the terrain no
   longer meshes the bed the water hides. The High beam view went from 41.6 fps (first V4 pass) to 49.0 fps; V3 was 45.6.

## Comparison (`compare/index.html`) and blind test (`blind/`)

The 12 reference scenes were recaptured beside V3 (`compare/index.html`, scores in `compare/scores.csv`, 1 = same as the
reference, 5 = obviously wrong):

- **Gulf passage:** water improves from 3 to 2. The flat grey sea is now slate blue-green with the FFT ocean and chop.
- **Every scene:** water is now at 2 or better.
  - The V3 regular diagonal ripple pattern (the round 1 giveaway) is gone from the drone, helm and chase views.
  - The storm's dark blotches became a rain-flattened grey surface.
  - The Ray Hubbard drone view stays at 1.
- **Remaining:**
  - The lake's body colour is a calibration from the reference clips, not a measurement.
  - Dark patches show where the shallow bed shows through in the Sunfish scene.

Blind test round 3 is in `blind/` and has the same ten Commons photos with ten new game frames under a new shuffle. Its marking page is
https://claude.ai/artifact/LAoWBRiqvmVLcCC61wr9UL; the answer key is `blind/answer-key.csv` (don't open it before marking).
Round 2 (https://claude.ai/artifact/SobrKzreqUPoVPXayNUVjU) hasn't been marked yet.

## Partial or left for later

- Spray is CPU droplets, not a Niagara system. It is visible close up in a breeze and modest in volume.
- Lapping is a foam line driven by the shore depth map (1 m cells). There is no breaking-wave geometry on the beach.
- The wake grid is visual only. Boats don't feel each other's wakes; the physics never reads the grid.
