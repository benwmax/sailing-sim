# Glow, second flag pass, main ecd4ed1c (PC)

**The glow needs direct sun, and it sits on the terrain at the waterline.**

- **Direct sun:** it is gone under Overcast and at 16:00, and at 12:00 it is down to a small spot at the bridge and gone on the wooded bank.
- **On the terrain:** from a camera 0.4 m above the water looking level at the bank, the blob lies flat on the bank face with its lower edge exactly on the waterline. It doesn't float in front of the bank.
- **Where:** it appears where the waterline runs through the shade of a bush or trees, and stays there when the waterline moves. On the wooded bank at gauge level, it is at the new waterline.
- **Ruled out:** the volumetric haze, the atmosphere's haze share, the skyline, tree wind and the whole Low tier (no Lumen, no VSM, M_Water). With the first pass, the water material, Lumen HW, GI level, trees, houses and body transmission are also ruled out.

## How it was run

- **Package:** the Development package `Packaged/Windows-ecd4ed1c`, with the bridge-05m and wooded-15m stations and camera args of the stills (`../args.csv`).
- **Settings:** Ultra 1920x1080, `-SailingScreenPct=100`, Drone capture, 8 s each, one warm-up first.
- **Runs:** each station's baseline, then one flag per run. Every command line is in `args.csv`.
  - **Swapped values:** where a flag changes a value the baseline already sets, it replaces it, so no arg appears twice. The baseline is 15:00, AfternoonBreeze, pool level and Ultra.
  - **Lake level:** the baseline already has `-SailingLakeLevel=pool`. To move the waterline, the run uses **`-SailingLakeLevel=gauge`** in its place.
  - **Low:** runs `bench-win.ps1 -Quality Low`.
  - **Water-side stills:** the 5 m station's camera (`-SailingCamWorld` north, east and heading kept) lowered to **0.4 m above the water** with **pitch 0**. CamWorld's height is relative to the water surface. This is the same as `-SailingCamPitch=0` with the lens near the water.
    - `bridge-water`: `-SailingStartAt=7200.8,786.9,327.2 -SailingCamWorld=29.4,-18.9,0.4,327.2,0.0`
    - `wooded-water`: `-SailingStartAt=2473.9,-3680.0,291.3 -SailingCamWorld=12.7,-32.6,0.4,291.3,0.0`
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).
- **Crops:** 1:1, inspected at 1:1, in `crops/glow-<station>-<flag>.png`.
  - Rectangles (x0, y0, x1, y1 on 1920x1080): bridge-05m 480, 640, 960, 900; wooded-15m 480, 580, 900, 700; bridge-water 380, 480, 900, 660; wooded-water 480, 500, 900, 660.
- **Full frames:** where a flag moves the glow out of the crop, the full frame is here too: `iso2-bridge-05m-LakeGauge.png`, `iso2-wooded-15m-LakeGauge.png` and `iso2-bridge-05m-Hour12.png`. The two water-side stills are also here.

## Flag x station

| Flag | bridge-05m | wooded-15m | Note |
| --- | --- | --- | --- |
| baseline (15:00, AfternoonBreeze, pool, Ultra) | present | present | As in the stills. |
| `-SailingClassicVolumetricHaze` | present | present | No change. |
| `-SailingAtmoHaze=0` | present | present | No change. |
| `-SailingLakeLevel=gauge` (in place of pool) | **gone** | **changed: moved** | The water drops and the camera, which keeps its height above the water, sees a different bank. Bridge: no glow anywhere at the new waterline (full frame). Wooded: a pale strip at the **new** waterline, x 430-790, y 715-740, in the trees' shade (full frame). |
| `-SailingHour=12` (in place of 15) | **changed: small** | **gone** | Bridge: only a small bright spot at the waterline, about x 820-860, y 820-850 (full frame). Wooded: the tree shade has moved off that stretch of waterline, the bank is sunlit there, and there is no glow. |
| `-SailingHour=16` (in place of 15) | **gone** | **gone** | The bank is in shade. Wooded has at most a trace. |
| `-SailingWeather=Overcast` (in place of AfternoonBreeze) | **gone** | **gone** | No direct sun. The bank at the waterline is evenly lit. |
| `-SailingNoSkyline` | present | present | No change. |
| `-SailingNoTreeWind` | present | present | No change. |
| `-SailingQuality=Low` (no Lumen, no VSM, M_Water) | present | present | Just as strong on Low, and wider and brighter on the wooded bank. Low's water also shows a regular ripple pattern; I didn't judge it here. |
| **Water-side, 0.4 m, pitch 0** | **on the terrain** | **on the terrain** | Bridge: the blob lies flat on the bank face, x 430-800, y 540-625, its lower edge exactly on the waterline. Its light doesn't go out over the water, and it doesn't float. Wooded: the reeds hide most of it, but the glow is on the bank at the waterline, x 600-760, y 560-625. |

## What this hands the fix thread

The glow is light on the **terrain**, just above the waterline, that needs the **direct sun**. It shows where that strip of bank is in **shadow** from a bush or trees. It is on every tier, including Low, so it is not Lumen, VSM, GI, haze, fog or the water material.

Candidates to look at, which this pass doesn't test:

- **A sun term in the terrain or shore material's wet band at the waterline** that ignores the shadow, such as a wet-sand sun specular or a fake reflected-sun bounce.
- **A sun-driven light or emissive placed along the shore.**

I made no code changes and did no further digging.
