# Blow sea (#788, feedback #27) on the PC: head 10b10e26

## Build and how it was run

- **Package:** a Development package of #788's **10b10e26** (the QA fixes), built on its own with main not merged, into the new `Packaged/Windows-10b10e2`.
- **Check reports:**
  - 80f98165: `Inputs/bench/pr-checks-nov15/pr788-80f9816.md`
  - 4b544cea, the newest head (MSVC check only): `pr788-4b544ce.md`
  - 4b544cea's one change, the lift fading across the ocean mask, is coast-only, so these lake stills stand.
- **Runs:** through the branch's own `bench-win.ps1` with the PID-only stop, one warm-up run first.
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).
- **Foreground:** 0 on every run. The window wasn't in front; I don't move windows or send input.
- **Base args (every run):** `-SailingWorld=ray-hubbard -SailingBoat=J22 -SailingStartAt=8917,240,137 -SailingWeather=Thunderstorm -SailingWeatherTime=300 -SailingWind=26 -SailingWindFrom=158 -SailingNoLightning -SailingQuality=Ultra`
- **Sea growth:** `-SailingBenchWarmup=60` gives the sea about 60 s to grow before the measured window and the screenshot.

## Stills: Ultra 1920x1080, `-SailingScreenPct=100`

- **Stills runs also used:** `-SailingNoHud -SailingNoGpuSlices`, `-Seconds 8`.
- **The three variants:**
  - `classic`: `-SailingClassicBlowSea`, the before.
  - `default`: the after, lift 0.15.
  - `lift25`: `-SailingBlowSea=0.25`.
- **The two views:** `chase` is the default view; `helm` adds `-SailingCapture=HelmEye`.
- **Command lines:** full ones are in `stills-10b10e2/args.csv`.

| Still | fps | p99 ms |
| --- | --- | --- |
| blow-classic-chase | 73 | 17.87 |
| blow-classic-helm | 75.4 | 16.62 |
| blow-default-chase | 76.4 | 15.85 |
| blow-default-helm | 76.7 | 17.07 |
| blow-lift25-chase | 74.6 | 16.69 |
| blow-lift25-helm | 77.8 | 16.4 |

**1:1 crops** in `stills-10b10e2/crops/`:

- `crop-<variant>-chase.png`: x 1060-1900, y 380-760 of the chase still, the open water right of the boat.
- `crop-<variant>-helm.png`: x 0-960, y 380-780 of the helm still.
- `compare-chase.png` and `compare-helm.png` stack the three variants.

### What differs (inspected at 1:1)

- **Cap count (chase crop):**
  - classic: about 3 small caps
  - default: about 6, small white tufts on the crests
  - lift25: about 1 or 2 in this frame
  - **Caveat:** caps come and go within a second, so one frame per variant can't rank lift 0.15 against 0.25. The default frame happens to catch more caps than the 0.25 frame. A count over a recorded sequence would settle it.
- **Grey vs white:**
  - All three seas are the same dark slate grey under the Thunderstorm sky, with no whitening of the open water.
  - The chop in `default` and `lift25` reads slightly rougher and more broken in the helm view's near water than `classic`, but only slightly.
  - At these two views the sea still reads small and grey in all three, with the lift's change modest.
- **Spray:**
  - The wake and quarter wave behind the boat look much the same in all three.
  - `lift25`'s chase frame has two extra spray bursts: one off the quarter (about x 1140, y 750) and one far right (about x 1500, y 1020).
  - `default`'s frame has none beyond the wake. As with the caps, one frame each.
- **Puff patches (QA ask):**
  - In both `classic` and `default` the water carries darker, rougher patches among lighter, smoother streaks. The darker patches are the puffs.
  - In the chase frames there is a broad darker area right of the boat and lighter streaks left of it.
  - I see no sign that the lift washed them out in `default` (lift 0.15). They darken the water about as much as in `classic`.
  - **Hedge:** the puffs drift, so the patches aren't in the same places frame to frame.

## 4K storm bench: 3840x2160 Ultra, `-SailingScreenPct=100`

- **Order:** classic, default, classic, default, back to back.
- **Settings:** `-SailingBenchWarmup=60`, 20 s measured.
- **Files:** `bench4k-10b10e2/*.bench.json`, with the command lines in `args.csv`.

| Run | fps | p99 ms | game ms | render ms | GPU frame ms | water ms | foreground | render_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| classic-1 | 48.5 | 22.64 | 9.49 | 20.63 | 20.06 |  | 0 | 100 |
| default-1 | 49 | 22.64 | 9.42 | 20.4 | 19.84 |  | 0 | 100 |
| classic-2 | 50.2 | 22.1 | 9.32 | 19.92 | 19.36 |  | 0 | 100 |
| default-2 | 49.4 | 22.84 | 10.16 | 20.22 | 19.64 |  | 0 | 100 |

- **Means:**
  - classic: 49.35 fps (48.5, 50.2)
  - default: 49.2 fps (49.0, 49.4)
- **Reading:** no measurable cost. The difference is well inside run-to-run spread, and GPU and water time are the same.
