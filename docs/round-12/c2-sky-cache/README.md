# C2: the sky cache (round 12, `Inputs/clouds-trees/plan.md`)

The third item of the clouds and trees plan, and the one meant to remove the grain. The live volumetric march spreads
its samples over rays up to 50 km long, so every step is hundreds of metres and the jitter turns into speckle. The sky
cache draws the far clouds (5 km and beyond) slowly and smoothly into a panorama; the live march keeps only the near
clouds, with its steps on short rays.

Everything is game code and materials. UE renders one volumetric cloud per scene and its tracing limits are global, so
the far band is our own march.

## How it works

- **`M_CloudCache`** (`CACHE_HEAD` / `CACHE_SHADOW` / `CACHE_TAIL` in `make_materials.py`) marches each texel of a
  4096 x 512 half-float panorama. A texel is a view ray from the camera: azimuth from north across, elevation from 33
  degrees down to -3 degrees. The march runs from 4.5 km (fading in until 5 km) to 40 km through the cloud slab, curved
  with the earth.
  - **The density is CLOUD_CODE's own,** pasted into the march as it is. The far clouds are exactly the shapes the live
    march would draw.
  - **Adaptive steps.** 96 coarse steps through clear air. On meeting cloud the march steps back and goes six times
    finer, then returns to coarse after eight empty fine steps. With coarse steps alone, a kilometre-deep cloud got two
    or three samples and came out flat.
  - **The sun.** Five shadow steps toward the sun, doubling from 50 m to 800 m (1.55 km), the live clouds' two-lobe
    phase, and two multiple-scattering octaves.
  - **What it stores.** Three numbers per texel, not a colour: the sunlight scattered toward the eye per unit of the
    sun's illuminance (R), the sky light per unit of the sky's radiance (G, with the cloud's AO), and the transmittance
    (B).
- **`ASailingEnvironment::UpdateSkyCache`** draws a strip of columns a frame with Canvas `DrawMaterial`, so a whole
  panorama takes 4 s. Each panorama uses one camera and one set of cloud parameters. When one is finished, the dome
  cross-fades to it over half a second, and the next goes into the other target. Each refresh replaces the last.
  Blending refreshes to average the grain stacked the clouds' drift into ghosts.
- **`M_SkyDome`** composites the panorama behind the live clouds, which cover it where they are. It lights the cached
  clouds now:
  - **The sun term** uses the atmosphere's own sun illuminance at the clouds' height (`SkyAtmosphereLightIlluminance`),
    reddened as the live clouds see it. With the plain `SunLum` the far clouds came out neutral grey beside warm beige
    live ones.
  - **The sky term** takes its brightness from the sky toward the view and its colour from the scene's sky light
    (`SkyLightEnvMapSample`, overhead). The sky light reads beige late in the day; as the sun climbs, the colour moves
    toward the blue sky's.
  - **The scales,** per tier: High sun 1.45, sky 2.1; Ultra 1.7, 1.2. Ultra's live clouds, with more samples, read
    brighter. As the sun climbs, both terms ease off: the sun from x1.09 at 25 degrees to x0.86 at 45, the sky from
    x1.04 to x0.72. These were fitted to the live clouds at two sun heights, lake-towers at 17:00 and Texas City at
    15:30. `-SailingSkyCacheLight=<sun>,<sky>` overrides the scales.
- **The live clouds** fade out over 4.5 to 5 km once the first panorama exists (`CacheSplit` in `CLOUD_CODE`), and
  trace only to 5 km from the camera (`TracingMaxDistance`, measured from the point of view).
- **Storms.** While a storm is in the sky, the cache steps aside and the live clouds take the whole sky back, exactly as
  on main. The shelf's lit face is emission in `CLOUD_CODE`, and the deck has a slate albedo; the cache's two lighting
  terms carry neither, and its storm came out as a black-brown deck. A storm cache is follow-up work.
- `-SailingNoSkyCache` compares.

## Stills (packaged, the PC, the saved round 12 cameras: `scenes.csv`)

`<scene>-high.jpg` and `<scene>-ultra.jpg`: the cache off (main's look) on the left, on on the right.

- **lake-towers, Kemah, Texas City, north shore.** The far clouds are free of grain, with solid form and their sunlit
  sides warm. They read smoother and more solid than the live clouds next to them; at a few kilometres the live ones
  show their fuzzy fringe. Texas City shows a few faint step lines inside the largest far cells.
- **storm-shelf.** The cache is off under the storm, so this one is the same as main. The grain is still there.

## How well the far clouds match the live ones

These are cloud pixels in the upper frame, from uncooked runs at High. Mean and 20th percentile are luminance; warmth
is red minus blue over all cloud pixels; shadow blue is blue minus red in the darkest 30%.

| | Mean | 20th pct | Warmth | Shadow blue |
|---|---|---|---|---|
| lake-towers (sun 25 degrees), live | 145 | 106 | 20 | -4 |
| lake-towers, cache | 139 | 103 | 18 | -10 |
| Texas City (sun about 45 degrees), live | 149 | 133 | -13 | 21 |
| Texas City, cache | 168 | 146 | -10 | 19 |

At lake-towers on Ultra the cache read 132 against 136, warmth 17 against 10.

The match is empirical, from two scenes. Texas City still reads about 13% bright, and part of that may be the measure
itself: the pale haze near the horizon passes the cloud mask. The cache's lighting is its own model, not the engine's,
so other times of day and other weathers will drift; the scales are where to fix them.

## Cost (GPU, 1080p, three ProfileGPU frames after 20 s, cache off / on, final build)

| View | clouds + fog, ms | GPU frame, ms |
|---|---|---|
| lake-towers, High | 0.57 / 0.29 | 4.99 / 4.89 |
| lake-towers, Ultra | 2.76 / 1.28 | 8.85 / 7.40 |
| galv-kemah, High | 0.47 / 0.29 | 6.34 / 6.28 |
| galv-kemah, Ultra | 1.81 / 1.10 | 9.43 / 8.73 |

The live clouds cost about half, because they march near rays only. The strip draw is about 0.25 ms a frame on the PC
(the `other` slice). On Ultra the frame is 0.7 to 1.5 ms cheaper; on High it is about even.

The Mac's own target is clouds and fog under 3 ms on High; they were 5.0 ms at lake-towers. To be measured there, along
with the strip's cost on Metal. Two things scale that cost: how many columns are drawn a frame (`kSkyCacheWidth` over 4
s), and the steps (`kSkyCacheSteps`).

## The settings test before C2 (no PR)

On main, the engine's cloud reconstruction was tried first: the reprojection clamp off, `UvNoiseSampleAcceptanceWeight`
at 5 instead of 20, and half-resolution tracing. Speckle was measured as the mean difference between each cloud pixel
and a 2-pixel blur of the image. At lake-towers it read 1.93 on main, 1.89 with the clamp off, 1.94 at weight 5, and
3.13 at half resolution (the storm-shelf readings went the same way). The grain is the march's own long steps, which
history can't average on a moving camera, and that is what the cache's short near rays address.

## Tests

155/155 on the PC (the final head with main merged).

## Not done

- **A measured pop check.** HighResShot didn't write frames during a bench run here, so the 60 s refresh sequence wasn't
  recorded. By design, every swap is a half-second cross-fade between two panoramas 4 s apart, in which the far clouds
  have moved a few pixels. The Mac's recording (`RECORD=`) is the way to check it.
- **The storm.** See above.
- **The real photos** (real-03/05/08/10) aren't on the PC.
