# Blow sea + storm water (#788) on the PC: head 9c22eac0

## Build and how it was run

- **Head:** **9c22eac0**, the Mac's M_WaterV4 and M_FarCap committed at fa1c159b.
- **LFS:** both materials are real files after `git lfs pull` (M_WaterV4 168,501 B; M_FarCap 26,444 B). No local material rebuild.
- **Merge:** the head lacked main **424b580b**, so it was merged locally and never pushed.
- **Build and package:** MSVC clean; Development package to the new `Packaged/Windows-9c22eac`.
- **Runs:** through the branch's own `bench-win.ps1` with the PID-only stop, one warm-up first. Foreground was 0 on every run.
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).
- **Base args (every run):** `-SailingWorld=ray-hubbard -SailingBoat=J22 -SailingStartAt=8917,240,137 -SailingWeather=Thunderstorm -SailingWeatherTime=300 -SailingWind=26 -SailingWindFrom=158 -SailingNoLightning -SailingQuality=Ultra`
- **Sea growth:** `-SailingBenchWarmup=60`.
- **Stills also used:** `-SailingScreenPct=100 -SailingNoHud -SailingNoGpuSlices`, `-Seconds 8`.
- **The four variants:**
  - (a) `a-old`: `-SailingClassicBlowSea -SailingClassicStormWater`
  - (b) `b-waves`: `-SailingClassicStormWater`, taller waves only
  - (c) `c-default`: both
  - (d) `d-lift30`: `-SailingBlowSea=0.3`
- **The two views:** `chase` is the default view; `helm` adds `-SailingCapture=HelmEye`.
- **Command lines:** full ones are in `stills/args.csv` and `bench4k/args.csv`.

| Still | fps | p99 ms |
| --- | --- | --- |
| blow-a-old-chase | 75.2 | 16.65 |
| blow-a-old-helm | 77 | 16.23 |
| blow-b-waves-chase | 74.9 | 16.95 |
| blow-b-waves-helm | 77.3 | 16.35 |
| blow-c-default-chase | 76 | 15.79 |
| blow-c-default-helm | 75.3 | 19.14 |
| blow-d-lift30-chase | 77.6 | 16.16 |
| blow-d-lift30-helm | 78.4 | 16.49 |

**1:1 crops** in `stills/crops/`:

- `crop-<variant>-chase.png`: x 1060-1900, y 380-760 of the chase still, the open water right of the boat.
- `crop-<variant>-helm.png`: x 0-960, y 380-780.
- `compare-chase.png` and `compare-helm.png` show the four variants two by two.

## What I see at 1:1

- **Wave size:** the chase crops of (b), (c) and (d) show a slightly more broken, rougher near chop than (a). It is a small step at this camera height; the sea is still mostly low chop.
- **Cap count (chase crop):**
  - (a) about 3
  - (b) about 5
  - (c) about 6
  - (d) about 2 in this frame
  - **Caveat:** caps live about a second, so one frame each can't rank (c) against (d); a count over a recorded sequence would settle it.
- **Grey vs white:** all four read dark slate under the Thunderstorm sky. The open water doesn't whiten.
- **Storm-water look:**
  - At these two views, (c) and (d) look a little more textured and slightly greyer-green in the near water than (a).
  - I can't clearly tell (c) from (b), taller waves alone, in these frames, so the storm-water term is subtle here.
  - In the helm view the rain rings dominate the near water in all four.
- **Puff patches:** the darker, rougher puff patches among lighter streaks are there in all four, including (c) and (d). Nothing washes them out.
- **Against the Mac's `blow-sea-788/mac-9c22eac0/blow-sea.png`** (inputs 51bdb836): that is a High still from a different camera and moment. It has the HUD, 25 kn gusting 28 and the boat head to wind with a big quarter wave, so it isn't frame-matched.
  - Its sea reads darker and more broken than these PC chase stills, which may be the different view and the lower tier. I can't make a like-for-like comparison from it.

## 4K storm bench: 3840x2160 Ultra, `-SailingScreenPct=100`

- **Order:** (a), (c), (a), (c), back to back.
- **Settings:** `-SailingBenchWarmup=60`, 20 s measured.

| Run | fps | p99 ms | game ms | render ms | GPU frame ms | water GPU ms / water CPU ms | foreground | render_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a-old-1 | 48.6 | 22.71 | 9.57 | 20.55 | 19.97 | 1.56 / 1.399 | 0 | 100 |
| c-default-1 | 47.7 | 23.22 | 10.49 | 20.97 | 20.38 | 1.57 / 1.546 | 0 | 100 |
| a-old-2 | 48 | 23.32 | 9.65 | 20.82 | 20.26 | 1.72 / 1.401 | 0 | 100 |
| c-default-2 | 47.9 | 23.45 | 9.62 | 20.88 | 20.31 | 1.7 / 1.431 | 0 | 100 |

- **Means:**
  - (a) old: 48.3 fps (48.6, 48.0)
  - (c) default: 47.8 fps (47.7, 47.9)
- **Cost:** about **-0.5 fps** for the storm water and taller waves, roughly 0.2 ms more GPU frame time, in both pairs. The water slice itself is the same (about 1.6 to 1.7 ms GPU). It is small and close to run-to-run spread, but it points the same way twice.
