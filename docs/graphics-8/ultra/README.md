# Ultra showcase (graphics-8/ultra)

These changes apply on Ultra only (`ESailingQuality::Ultra`), so the Mac's Medium and High gates don't move. `gate.ps1 -Scope water`
passes on High and Ultra, and High's numbers are unchanged: 4.2-5.0 ms GPU, 65-76 fps.

## What ships on by default (Ultra)

- **Denser bow spray:** 1,500 droplets instead of 600, emitted 2.5x as fast. These are still CPU droplets in the same ISM,
  so High's look and cost don't move.
- **Vessel exhaust** (`APowerVesselActor::UpdateExhaust`, `M_Smoke`): soft lit puffs from the stack. Ships, towboats and
  shrimpers give black diesel; runabouts a pale haze low at the stern. Puffs are emitted with the throttle, carried by
  `FWindField` at the stack's height, and rise, spread and fade. 64 puffs a vessel, within 3 km of the camera.
  `-SailingNoExhaust` turns it off. The asset is loaded per actor, not held in a function static. **Not yet confirmed in a still:** the
  traffic spawns away from the free cameras tried so far; each vessel logs `Exhaust: <kind> <id> at <n>, <e> m` to help
  frame one.

## Opt-in: `-SailingUltraDetail`

The drawn wave detail at four times the area, with the same texel size (chop 256^2 over 46 m, ripples 128^2 over 6.2 m),
and a 512-cell wake grid over 128 m. The physics never reads this FFT, so PolarGate and the Hs tests don't move.

It is off by default because the game thread waits for it. The 4x FFT, the cap-threshold solve and the mip packing
outran the 30 Hz worker budget, so `UpdateDetail` blocked. On helm-eye at 1440p, water CPU was 9.8 ms and Ultra ran at
44 fps, against 1.0 ms and 70 fps without it; the 512 wake alone cost about 2.5 ms. It needs a detail pipeline that
never waits (skip a frame instead) before it can be the default.

## Not done

- Niagara: the project has no Niagara systems, and they can't be authored reliably from headless Python. The spray and
  exhaust follow the existing CPU-instanced pattern; a Niagara port needs the editor GUI.
- Wake foam that lingers: folded into W4 (foam persistence).

## Bench (PC, RTX 4090, Ultra, 2560x1440, packaged, `bench-visual-win.ps1`, main bec89c54)

| View | fps natural | GPU ms natural | fps cinematic | GPU ms cinematic |
|---|---|---|---|---|
| beam8 | 63.2 | 8.23 | 58.9 | 8.37 |
| beat15 | 64.6 | 8.4 | 58.9 | 8.71 |
| storm | 65.3 | 10.48 | 58.3 | 10.29 |
| marina | 64.3 | 8.47 | 59.8 | 8.8 |
| coast-day | 62.5 | 9.17 | 57.5 | 9.44 |
| coast-night | 70.2 | 8.41 | 66.6 | 8.6 |
| gulf-sea | 67.8 | 7.84 | 66.9 | 8.12 |
| helm-eye | 69.7 | 8.04 | 69.3 | 8.28 |
| slip | 69.6 | 9.39 | 68.2 | 9.67 |
| bridge | 67.6 | 8.06 | 67 | 8.42 |
| crew | 58 | 10.08 | 55.9 | 10.36 |
| marina-night | 74.2 | 9.52 | 70.9 | 9.97 |

At 1440p every view is between 56 and 74 fps. The game thread (13-16 ms) is the limit, not the GPU (8-10.5 ms). The 4K
runs (`-ResX 3840 -ResY 2160`) came back with *less* GPU time than 1440p, so the window was clamped to the desktop's size
and 4K is not measured here.
