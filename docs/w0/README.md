# W0: water fixes and measurements

Water and weather round, phase W0 (Mac, Oct 14 2026). Four fixes from the water and weather plan, no GPU budget spent.

## Fixes

1. **Far streaks (cat's-paw map edge).** The 64x64 gust map covers 1.6 km around the boat and the sampler clamps, so
   its border texels smeared across the far water and its square edge showed as a hard seam 800 m out (the diagonal
   line in `w0-drone-before.png`). `AWaterSurface::UpdateGustMap` now blends the outer 20% of the radius (smoothstep from
   0.78 to 0.97 of the half-width) to `FWindField::MeanSurfaceRoughnessAt`: the mean wind with a gust front's outflow
   where it has passed, no gusts and no lee. Every border texel is the mean, so the clamp carries the mean out to the
   horizon with no streaks and no seam.
2. **Puff whitecaps.** `WindParams.z` is now the sea's mean wind (what the drawn waves were grown for) instead of the wind
   at the boat, so cat's-paw darkness reads against the lake's mean; `WindParams.w` (the unused `Caps`) is now the
   water body's whitecap scale. In M_WaterV4 the folding threshold moves by `CapSlope * ln(scale * (U_local/U_mean)^3.41)`
   (Monahan's exponent), so caps gather in puffs and thin in lulls; the far, sub-pixel caps take the same scale.
   `AWaterSurface::WhitecapThreshold` mirrors the shader. CapSlope = 0.045 is the measured threshold shift per e-fold of
   coverage on the drawn waves (0.034 at 10 kn to 0.069 at 25 kn).
3. **Fresh-water foam.** `AWaterSurface::WhitecapScaleFor(World)`, beside `WaterBodyFor`: lake 0.4, Galveston Bay 0.7,
   Gulf 1.0 of Monahan. The Phase 8 lake references are videos with no lake stills of whitecaps at a known wind (the
   12 kn and 17 kn J/22 chase clips that set the current look are salt water), so 0.4 stays the literature value rather
   than a photo fit. M_Water (Low) scales its caps the same way.
4. **Per-band wave growth.** `FWaveField::Update(Dt)` moves each band toward its target with its own time constant,
   `GrowthSeconds(T) = clamp(8 T^2, 5, 300)` s (exact exponential per step): the 0.5 s ripples in 5 s, the 2.5 s peak of a
   12 kn lake near the old 40 s, the 4 s waves in about two minutes. Targets are unchanged and M_Water still gets the
   amplitudes pushed each frame, so `FWaveField::Height` and the material stay matched.

## Tests

`scripts/test.sh`: 103 passed, 0 failed.

- `SailingSim.Physics.WaveBandGrowth` (new): after a 6 to 18 kn step, the 0.53 s band reaches 90% in 11.5 s, the
  3.71 s band in 253 s; steady state equals the snapped sea (Hs 0.335 m both).
- `SailingSim.Visual.Whitecaps` (extended): sea coverage unchanged; lake and bay within a factor of three of 0.4 and
  0.7 Monahan; a 1.3x puff caps more than the mean, a 0.7x lull less.

| wind | sea | Monahan | lake (0.4) | lake puff 1.3x | lake lull 0.7x | bay (0.7) |
|---|---|---|---|---|---|---|
| 10 kn | 0.12% | 0.10% | 0.03% | 0.12% | 0.01% | 0.08% |
| 14 kn | 0.47% | 0.32% | 0.16% | 0.46% | 0.04% | 0.29% |
| 20 kn | 1.41% | 1.09% | 0.57% | 1.39% | 0.19% | 1.03% |
| 25 kn | 2.55% | 2.33% | 1.37% | 2.51% | 0.46% | 2.03% |

## Screenshots

Lake, 12 kn AfternoonBreeze, 15:00, uncooked (`scripts/run-game.sh`).

| | before | after |
|---|---|---|
| Low camera (8 m, pitch -2) | ![](w0-low-before.png) | ![](w0-low-after.png) |
| Drone at 400 m (`-SailingCapture=Drone -SailingCamWorld=0,0,400,290,-22`) | ![](w0-drone-before.png) | ![](w0-drone-after.png) |

The drone view's hard diagonal seam (the gust map's edge) is gone; the near water fades into the mean. From the low
camera the change is small: the far water past 800 m was already near the mean at this wind, and the lake's caps are
fewer (0.4 of the sea's).

## Bench (packaged Development, `scripts/bench-visual.sh 12 <label> Medium High`)

`visual-bench-w0-before.csv` (main at 790f0eb) and `visual-bench-w0-after.csv`, plus the game-thread `-gt` files.

| tier | min avg fps before | after | gate | water slice mean before | after | per-view delta range |
|---|---|---|---|---|---|---|
| Medium | 72.4 | 72.1 | 60 | 1.53 ms | 1.53 ms | -0.10 to +0.23 ms |
| High | 46.4 | 46.5 | 45 | 1.85 ms | 1.87 ms | -0.12 to +0.30 ms |

The water slice is flat within run-to-run noise: the shader adds a log and a pow per pixel and the CPU edge fade
touches 64^2 texels at the map's update rate.
