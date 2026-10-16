# Ultra showcase (graphics-8/ultra)

These changes apply on Ultra only (`ESailingQuality::Ultra`), so the Mac's Medium and High gates don't move. `gate.ps1 -Scope water`
passes on High and Ultra, and High's numbers are unchanged: 4.2-5.0 ms GPU, 65-76 fps.

## What ships on by default (Ultra)

- **Denser bow spray:** 1,500 droplets instead of 600, emitted 2.5x as fast. These are still CPU droplets in the same ISM,
  so High's look and cost don't move.
- **Vessel exhaust** (`APowerVesselActor::UpdateExhaust`, `M_Smoke`): soft lit puffs from the stack. Ships, towboats and
  shrimpers give black diesel; runabouts a pale haze low at the stern. Puffs are emitted with the throttle, carried by
  `FWindField` at the stack's height, and rise, spread and fade. 64 puffs a vessel, within 3 km of the camera.
  `-SailingNoExhaust` turns it off. The asset is loaded per actor, not held in a function static. Confirmed in `exhaust-ultra-vs-high.jpg`, framed with `-SailingNearShip=150`: the container ship's stacks trail black smoke downwind on Ultra (top) and none on High (bottom).

## Opt-in: `-SailingUltraDetail`

The drawn wave detail at four times the area, with the same texel size (chop 256^2 over 46 m, ripples 128^2 over 6.2 m),
and a 512-cell wake grid over 128 m. The physics never reads this FFT, so PolarGate and the Hs tests don't move.

It is off by default because the game thread waits for it. The 4x FFT, the cap-threshold solve and the mip packing
outran the 30 Hz worker budget, so `UpdateDetail` blocked. On helm-eye at 1440p, water CPU was 9.8 ms and Ultra ran at
44 fps, against 1.0 ms and 70 fps without it; the 512 wake alone cost about 2.5 ms. It needs a detail pipeline that
never waits (skip a frame instead) before it can be the default.

## Measuring

- `-SailingUltraDetail`: the 4x drawn detail and the 512 wake (above).
- `-SailingNoExhaust`: no exhaust plumes.
- `-SailingNearShip=<m>`: when traffic spawns its first ship, the player is moved this far abeam of her, on her heading
  (`ATrafficManager::AddPower` sets `ASailingGameMode::NearShipStart`, which `GetLaunchSpot` returns, then resets the
  boat). Use it with `-SailingTraffic=2 -SailingTrafficNear` to frame a ship's exhaust; the ships' spawn varies from run
  to run.

## Pre-existing on main (not this branch)

At Galveston from Launch 3, the drawn water ends 1-2 km out and a flat brown band shows before the far shore, on High as
well as Ultra: `Inputs/water-edge/` on the inputs branch (a7435e24). It is reported to the Mac.

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

At 1440p every view is between 56 and 74 fps. The game thread (13-16 ms) is the limit, not the GPU (8-10.5 ms). True 4K runs (`-ResX 3840 -ResY 2160`) came back with *less* GPU time than 1440p, because the window was clamped to the desktop's size.
The 4K figures below are a **proxy**: 2560x1440 at `-SailingScreenPct=150` (3840x2160 internal):

| View | fps natural | GPU ms natural | fps cinematic | GPU ms cinematic |
|---|---|---|---|---|
| beam8 | 55.2 | 13.33 | 52.1 | 13.45 |
| beat15 | 51.9 | 13.59 | 49.1 | 13.71 |
| storm | 44.1 | 17.24 | 42.7 | 17.27 |
| marina | 55.1 | 13.42 | 51.7 | 13.67 |
| coast-day | 52.4 | 14.65 | 49.3 | 14.75 |
| coast-night | 53.6 | 14.42 | 52.2 | 14.26 |
| gulf-sea | 57.6 | 12.91 | 53.8 | 13.07 |
| helm-eye | 57.1 | 13.47 | 53.9 | 13.23 |
| slip | 50.3 | 15.74 | 47.8 | 15.89 |
| bridge | 56.7 | 13.18 | 52.9 | 13.2 |
| crew | 44.7 | 15.58 | 43.2 | 15.95 |
| marina-night | 48.8 | 17.28 | 48.2 | 15.55 |

At that proxy every view runs 43-58 fps on 13-17 ms GPU. A 4K desktop would give the real numbers.
