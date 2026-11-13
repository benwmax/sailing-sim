# Cloud shimmer on Ultra (feedback #22)

A tester on Ultra at 3840x2160 (RTX 4090) saw fine grain on the cumulus that keeps changing while you watch it.
This follows `docs/ultra-cloud-tops/`, `docs/near-cloud-grain/` and `docs/ultra-cloud-fullres/`.

## Why the samples did nothing before

Ultra asked for twice the view samples (`ViewSampleCountScale` 2), but `r.VolumetricCloud.ViewRaySampleMaxCount` was
160, which is already the most that 2 can reach. The `ultra-cloud-tops` sweep found the same thing: x3 samples changed
nothing until the cap rose. Each frame the march jitters where its samples land. Too few samples, and that jitter shows
up as speckle that changes every frame.

## What changed (Ultra only)

- `r.VolumetricCloud.ViewRaySampleMaxCount` goes from 160 to 320, and the view scale from 2 to 3
  (`CloudViewSampleScale`, `VisualPipeline.h`).
- The cumulus step-cap floor goes from 76 m to 150 m (`CloudCapStepFloorM`). A cloud base now closes over more steps, so
  the march averages its light instead of each pixel landing on one jittered depth.
- Low, Medium and High are unchanged: same cap (48, 72, 80), scale 1, and no floor. `SailingSim.Visual.TierSettings`
  holds both the Ultra values and the unchanged ones.

## The sweep (Mac M5 Pro, uncooked, Ultra, 3840x2160, main 2f8e31f6)

The feedback #22 repro is the Thunderstorm preset at Ray Hubbard, with fair cumulus before the front. The stills and CSV
are on the `inputs` branch under `fb22-sweep/`.

How each column was measured:

- **Cloud mask:** the low-saturation bright pixels above the horizon (30% of the frame), the same mask for every variant.
- **Grain:** the std of luma minus its 2 px blur.
- **Shimmer:** the mean absolute difference between held frames (`-SailingPhoto`), averaged over five pairs. Held
  water reads 0.5-1.3.

| Variant | Grain | Shimmer | Clouds ms (Mac, relative only) |
| --- | --- | --- | --- |
| Main | 1.60 | 0.88 | 157 |
| Upsampling mode 4 | 1.62 | 0.92 | 154 |
| Reprojection box constraint 0 | 1.56 | 0.91 | 157 |
| Samples: cap 320, scale 3 | 1.64 | **0.65** | 230 |
| Cap step floor 150 m | **1.48** | 0.84 | 192 |
| Footprint floor 110 m | 1.63 | 0.88 | 179 |
| Shadow samples 160 | 1.50 | 0.90 | 169 |

What the sweep showed:

- **Samples** are the only lever that clearly cuts the shimmer, by about a quarter.
- **The cap step floor** is the best on still grain.
- **The other levers** either did nothing or made the shimmer worse.

This change ships the two best levers together. The Mac runs Ultra at about 4 fps, so its milliseconds show only how
the variants compare with each other. The cost on the 4090 has to be measured once the PC is back. The
`ultra-cloud-tops` sweep measured a cap of 320 at about +0.5-0.7 ms at 1080p. At 4K, Ultra traces at 1920x1080 (half
resolution), so expect about that much again, plus the cap step's share.

## Not taken

- **Full-resolution tracing** (`r.VolumetricRenderTarget.Mode` 3) removes most of the speckle on the cloud overhead. It
  also breaks the clouds' composite over the mast (`docs/ultra-cloud-fullres/`). It stays the next lever if this isn't
  enough, after the mast composite is fixed.
- **Medium and High.** They trace at a quarter resolution under the Mac's 60/45 gates, and no lever here is free.

## To check

- Before and after stills on the 4090 at 4K, plus the cloud slice's cost.
- The sky cache's seam at 5 km. `kSkyCacheSunUltra` and `kSkyCacheSkyUltra` were matched to the live clouds at view
  scale 2. A brightness step there means they need refitting.
