# Flag isolation of the two shore render bugs, main ecd4ed1c (PC)

**Moiré (sailing-feedback #30): it's the water material.** `-SailingClassicWater` removes both the chevrons and the blocky glints, at the bulkhead and at the bridge bank. No other flag tested removes them. It doesn't scale with screen resolution or AA, so it is drawn in the water's own shading (M_WaterV4), not screen-space aliasing.

**Glow (sailing-feedback #29): no flag tested removes it.** It is not the water material, Lumen's hardware ray tracing, the GI level, the trees, the houses, body transmission or the tier.

- `-SailingNoShoreDetail` takes the blob off the bridge bank, but it also changes the bank and moves the waterline.
- On the wooded bank, a glow strip is still there at the new waterline with the shore detail off.
- So the glow follows wherever the terrain meets the water in shade, not the 1 m shore detail itself.

## How it was run

- **Package:** the Development package `Packaged/Windows-ecd4ed1c`. The stations and camera args are exactly those of the stills in `../` (`../args.csv`).
- **Settings:** Ultra 1920x1080, `-SailingScreenPct=100`, Drone capture, 8 s each, one warm-up first.
- **Runs:** each station's baseline, then one run per flag. The other args are unchanged.
  - `Medium` runs `bench-win.ps1 -Quality Medium` in place of Ultra.
  - `ScreenPct67` replaces `-SailingScreenPct=100` with 67, so no arg appears twice.
  - `GI2` is one level under Ultra's GI scalability, which is 3 (`QualityGIScalabilityLevel`).
- **Command lines:** every run's full command line is in `args.csv`.
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).
- **Crops:** 1:1 at the stills' crop rectangles, in `crops/<artefact>-<station>-<flag>.png`, each inspected at 1:1.

**Crop rectangles** (x0, y0, x1, y1 on 1920x1080):

| Crop | Rectangle |
| --- | --- |
| glow-bridge-05m | 480, 640, 960, 900 |
| glow-wooded-15m | 480, 580, 900, 700 |
| moire-bulkhead-near-20 | 0, 600, 960, 900 |
| moire-bulkhead-near-35 | 0, 140, 960, 700 |
| moire-bridge-05m | 880, 800, 1500, 900 |

## Glow: flag x station

| Flag | bridge-05m | wooded-15m | Note |
| --- | --- | --- | --- |
| baseline | present | present | Bridge: a large blob at the waterline left of centre. Wooded: a bright strip along the waterline in the trees' shade. |
| `-SailingNoShoreDetail` | **gone** | **changed** | The bank is the 5 m grid. It is lower, its shape differs, and the waterline moves. Bridge: only a faint pale patch at the new waterline (x 380-560, y 690-730), outside the crop. Wooded: a bright strip is still at the new waterline (x 480-700, y 690-715; see the full frame `iso-wooded-15m-NoShoreDetail`), so the crop misses it. |
| `-SailingClassicTrees` | present | present | The tree and bush cards change. The glow is the same at both. |
| `-SailingClassicHouses` | present | present | No change. |
| `-SailingLumenHW=0` | present | present | No change. |
| `-SailingGI=2` | present | present | No change. |
| `-SailingNoBodyTransmission` | present | present | No change. |
| `-SailingQuality=Medium` | present | present | The whole frame is Medium's look, and the glow is just as strong. |
| `-SailingClassicWater` (from the moiré set) | present | not run | Bridge only. The water changes completely and the blob doesn't change (`crops/glow-bridge-05m-ClassicWater.png`). |

## Moiré: flag x station

**Chevrons**

| Flag | bulkhead-near-20 | bulkhead-near-35 | bridge-05m | Note |
| --- | --- | --- | --- | --- |
| baseline | present | present | present | A herringbone band along the wall, and along the bank's waterline at the bridge. |
| `-SailingClassicWater` | **gone** | **gone** | **gone** | M_Water: smooth olive water, no chevrons. |
| `-SailingNoBodyTransmission` | present | present | present | No change. |
| `-SailingClassicHullClip` | present | present | present | No change. |
| `-SailingNoFarCaps` | present | present | present | No change. |
| `-SailingAA=2` (TAA) | present | present | present | Same pattern and period. |
| `-SailingAA=4` (TSR) | present | present | present | Same pattern and period. |
| `-SailingScreenPct=67` | present | present | present | The chevrons are the same size on screen, only softer. So the pattern isn't tied to the pixel grid. |

**Blocky glints** (near-35's lower left)

| Flag | bulkhead-near-35 | Note |
| --- | --- | --- |
| baseline | present | Hard stair-stepped sun glints, 10 to 30 px. |
| `-SailingClassicWater` | **gone** | Smooth water. |
| `-SailingNoBodyTransmission` | present | No change. |
| `-SailingClassicHullClip` | present | No change. |
| `-SailingNoFarCaps` | present | No change. |
| `-SailingAA=2` | present | Same. |
| `-SailingAA=4` | fewer | Fewer and smaller in this frame. The glints move with the ripples, so one frame can't tell. |
| `-SailingScreenPct=67` | fewer | Fewer in this frame, same caveat. |

## What this hands the fix thread

- **Moiré:** look inside M_WaterV4's near-water shading. The candidates are the short-wave detail and normal sampling (`FWaveDetail` textures), and anything driven by the shore band (the shore depth map, `glass`, the W2 wind map), since it is worst at the wall and bank.
  - Not the hull clip, the far caps, body transmission, AA or resolution.
- **Glow:** it is on the terrain at the waterline, brightest in shade, and survives the water material, Lumen HW, GI level, tier, trees, houses and body transmission.
  - Next to test (not done here, by the brief): the terrain or shore material's wet band and anything that brightens the terrain at the water's edge, and the skylight or AO in shadow at the waterline.
