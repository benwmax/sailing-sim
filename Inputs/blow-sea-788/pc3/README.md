# Blow sea + storm water (#788) on the PC, pc3: head d59e3e00

## Build and how it was run

- **Head:** **d59e3e00**. The lake's whitecap scale now rises from 0.4 toward 0.8 in a blow; this head changes C++ only.
- **Materials:** the 9c22eac0 ones, real after `git lfs pull` (M_WaterV4 168,501 B; M_FarCap 26,444 B). No local rebuild.
- **Merge:** the head lacked main **424b580b**, so it was merged locally and never pushed.
- **Build and package:** MSVC clean; Development package to the new `Packaged/Windows-d59e3e0`, warmed once.
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).
- **Base args:** `-SailingWorld=ray-hubbard -SailingBoat=J22 -SailingStartAt=8917,240,137 -SailingWeather=Thunderstorm -SailingWeatherTime=300 -SailingWind=26 -SailingWindFrom=158 -SailingNoLightning -SailingQuality=Ultra`
- **Stills also used:** `-SailingBenchWarmup=60 -SailingScreenPct=100 -SailingNoHud -SailingNoGpuSlices`, `-Seconds 8`.
- **The two variants:**
  - (a) `a-old`: `-SailingClassicBlowSea -SailingClassicStormWater`
  - (c) `c-default`
- **The two views:** `chase` is the default view; `helm` adds `-SailingCapture=HelmEye`.
- **Command lines:** `stills/args.csv`.

| Still | fps pc3 | p99 ms | foreground | fps pc2 (9c22eac0) | foreground pc2 |
| --- | --- | --- | --- | --- | --- |
| blow-a-old-chase | 73 | 17.71 | 0 | 75.2 | 0 |
| blow-a-old-helm | 76.4 | 17.76 | 0 | 77 | 0 |
| blow-c-default-chase | 76.6 | 16.28 | 1 | 76 | 0 |
| blow-c-default-helm | 68.9 | 21.47 | 1 | 75.3 | 0 |

**1:1 crops:** `stills/crops/crop-<variant>-<view>.png`, at the same rectangles as pc2 (chase x 1060-1900, y 380-760; helm x 0-960, y 380-780). `compare-chase.png` and `compare-helm.png` stack (a) over (c).

## What I see at 1:1

- **Cap count (chase crop):** (a) about **4**, (c) about **6 to 7**.
  - Across the full chase frame, (c) has a few more small caps on the open water right of the boat.
  - That is about 1.5 times (a), **not the expected three times**.
  - (c) here looks close to pc2's default (9c22eac0, about 6 caps in the same crop). On this one frame each, the higher lake whitecap scale doesn't show a clear rise at this view.
  - **Caveat:** caps live about a second, and this is one frame per variant. A count over a recorded sequence would be the firmer test.
- **Grey vs white:** both read dark slate; the open water doesn't whiten.
- **Storm-water look:** (c)'s near chop is a little more broken than (a)'s, as in pc2.
- **Puff patches:** present in both.
- **Helm view:** the rain rings dominate the near water in both. (c) reads slightly smoother and darker there than (a).

## Frame rate

- **Chase:** (c) default 76.6 fps against pc2's 76.0. No change.
- **Helm:** (c) default **68.9** fps against pc2's 75.3. That is a visible drop, with p99 21.5 against 19.1 ms.
- **Foreground:** both (c) runs report **`foreground: 1`**, the game window in front. Every other run today, these (a) runs included, reports 0. I didn't send input or move windows, so something else on the desktop changed.
- **Whether the drop is real:** one run with a different foreground state can't say.
- **Next:** a repeat of both helm stills plus the 4K (a)-against-(c) A/B, queued after the #787 follow-up.

## Repeat of the helm stills and the 4K A/B (same session as the #787 follow-up)

- **Package:** the existing `Packaged/Windows-d59e3e0`, with the bench scripts from d59e3e00 and the same args.
- **Saved:** held aside and restored (B57AA3AF).
- **Foreground:** **1 on every run here**, as in the #787 follow-up just before.

**Helm stills again** (`stills-repeat/`):

| Still | fps | p99 ms | foreground |
| --- | --- | --- | --- |
| blow-a-old-helm | 68.0 | 21.24 | 1 |
| blow-c-default-helm | 64.2 | 22.73 | 1 |

- **With the window in front:** the *old* sea's helm view also runs at 68.0 here, against 76.4 in the first pc3 pass, which had the window behind.
- **So most of the first pass's 75.3 to 68.9 helm "drop"** went with the foreground state, not the change.
- **Like for like (both foreground 1):** default is 3.8 fps below old in this one pair. That is single runs and close to the spread.

**4K Ultra A/B:** 3840x2160, `-SailingScreenPct=100`, 60 s warm-up, 20 s measured, (a), (c), (a), (c) back to back.

| Run | fps | p99 ms | game ms | render ms | GPU frame ms | water GPU ms / water CPU ms | foreground |
| --- | --- | --- | --- | --- | --- | --- | --- |
| a-old-1 | 51.4 | 23.08 | 9.4 | 19.45 | 18.93 | 1.62 / 1.348 | 1 |
| c-default-1 | 49.7 | 22.66 | 9.4 | 20.11 | 19.59 | 1.64 / 1.318 | 1 |
| a-old-2 | 50.4 | 22.85 | 9.42 | 19.81 | 19.28 | 1.57 / 1.297 | 1 |
| c-default-2 | 51.6 | 22.9 | 9.28 | 19.37 | 18.85 | 1.68 / 1.338 | 1 |

- **Means:**
  - (a) old: 50.9 fps (51.4, 50.4)
  - (c) default: 50.65 fps (49.7, 51.6)
- **Cost:** no measurable cost at 4K. The pairs cross over, and GPU frame and water time are within run-to-run spread.
