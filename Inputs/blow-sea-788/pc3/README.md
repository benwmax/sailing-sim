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
