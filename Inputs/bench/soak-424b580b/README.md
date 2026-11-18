# 60-minute soaks of main 424b580b at Ultra 1080p (PC, Nov 17)

**Summary:** no crash and no memory growth in either hour.

| | Shipping, 60 min (shot-only) | Development, 60 min (`-SailingDemo`, tacking) |
| --- | --- | --- |
| Crashes | none | none |
| Ensures | none | 2 at startup (second 0-1), both handled; then none |
| Working set (MB): minute 1 / end / peak | 3,244.9 / 3,190.4 / 3,244.9 (min 3,060.3) | 3,955.7 / 3,377.8 / 3,955.7 (min 3,230.2) |
| Private bytes (MB): minute 1 / end / peak | 9,459.7 / 9,387.6 / 9,459.7 | 10,163.2 / 9,625.6 / 10,163.2 |
| Memory growth over the hour | none (end 55 MB under minute 1) | none (end 578 MB under minute 1; settles by minute 10, then flat within 160 MB) |
| fps mean | not measurable (Shipping writes no bench here; see below) | **72.8** (p99 17.65 ms, 261893 frames over 3599 s) |
| Frames over 250 ms in play | not measurable | **none** (only the load frame at 0.45 s and the bench's end capture at 3603.3 s) |
| Frames over 50 ms in play | not measurable | **1**: 63.9 ms at 3074.4 s, game thread |

**What the Dev hour confirms:**

- With the autopilot tacking every 12 s for an hour, there are no tack hitches. That matches the tack-hitch finding (`Inputs/bench/tack-hitch-main-424b580b/`): the 60-140 ms hitches came from capture mode's synchronous `camera.json` write, and this run had no capture mode.
- The only frame over 50 ms, a 64 ms game-thread spike, is a single event.

## How it was run

- **Shipping package:** `Packaged/Shipping-424b580b-soak`, from a fresh worktree at 424b580b, built the way `friday.ps1` does:
  - editor build first, MSVC clean;
  - the version line;
  - the Sentry DSN appended to `Config/Windows/WindowsEngine.ini` for the cook from the PC's own file, by variable only, never printed or written elsewhere. The staged line read back as a quoted https URL; release `sailing-sim@424b580b-soak`, environment `soak`;
  - the slice switch;
  - a full cook, 4 min.
  - The ini was restored byte for byte, and Config and Content were clean. **No zip.** The worktree was removed, and nothing was committed or pushed from it. The Friday candidate `Shipping-ecd4ed1c` was not touched.
- **Development package:** the existing `Packaged/Windows-424b580b`.
- **Saved:** Bean's Saved was held aside for each run and restored with the profile hash checked (B57AA3AF). Both runs started with a fresh Saved.
- **Memory logging:** the game process's working set and private bytes, by PID, every minute (`*-memory.csv`).
- **Foreground:** the Dev bench reports foreground 1.

### Shipping: why it is a shot-only run with no frame data

- **What Shipping reads:** a Shipping build reads only `-SailingUIScript`, `-SailingWorld`, `-SailingLaunch`, `-SailingShot`, `-SailingBench` and `-SailingSlice`, and only with `-SailingShippingSmoke` (`BenchRunner.cpp:64`, `ShippingSmokeArgs`). **`-SailingDemo` and `-SailingBenchTrace` are dropped**, so the boat sails without the autopilot and there is no per-frame list.
- **The bench is capped:** Shipping also **clamps `-SailingBench` to 60 s** (`BenchRunner.cpp:79`). The first Shipping run with `-SailingBench=3600` measured only one minute: Ultra **83.6** fps, p99 18.44 ms, no crash, no ensures (`shipping-60s/`).
- **So the Shipping hour** (`shipping60/`) ran as `-SailingShippingSmoke -SailingWorld=Lake -SailingLaunch=1 -SailingShot=soak-shipping60 -windowed -ResX=1920 -ResY=1080 -NoCrashReporter`. A shot-only run skips the front end and doesn't quit by itself; I stopped its own two PIDs at 60 minutes. Ultra is the packaged game's default.
- **What it logs:** crashes and ensures come from the held-aside Saved's `Crashes` folder and the game log, which is 45 lines; Shipping logs little.

### Development

- **Args:** `Packaged/Windows-424b580b/SailingSim.exe -SailingBench=3600 -windowed -ResX=1920 -ResY=1080 -SailingShot=soak-dev -SailingQuality=Ultra -SailingWorld=Lake -SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingScreenPct=100`.
- **The two startup ensures** are written as crash-report folders. Both are handled ensures in the first second, before play, and the game then ran the full hour and exited 0:
  1. `Ensure condition failed: !IsComponentPSOPrecachingEnabled() || bPSOPrecacheCalled [PSOPrecache.cpp:296]`
  2. `Ensure condition failed: OriginX <= OriginMax && OriginY <= OriginMax && OriginZ <= OriginMax [DoubleFloat.cpp:19]`. This is the known distance-field precision ensure CLAUDE.md mentions.
  - `dev/crash-*/CrashContext.runtime-xml` has their contexts; the minidumps stay on the PC.
- **Files:**
  - `dev/frames-over-250ms.csv`, `dev/frames-over-30ms.csv` (62 frames in an hour), `dev/fps-per-minute.csv`.
  - The full 262,000-frame `soak-dev.frames.csv` (10.5 MB) stays on the PC at `D:\dev\ss-fix\Artifacts\bench\soak-424b580b\dev\`.

## Per minute

| minute | Dev working set MB | Dev private MB | Dev fps | Shipping working set MB | Shipping private MB |
| --- | --- | --- | --- | --- | --- |
| 0 | 54.5 | 39.3 |  | 94.6 | 58.8 |
| 1 | 3955.7 | 10163.2 | 73.7 | 3244.9 | 9459.7 |
| 2 | 3910.4 | 10085.8 | 72.9 | 3212.9 | 9427.6 |
| 3 | 3925.2 | 10105.8 | 69.6 | 3099.3 | 9311.6 |
| 4 | 3905.7 | 10087.6 | 69.7 | 3142.9 | 9361.2 |
| 5 | 3912.2 | 10093.9 | 70.5 | 3179.8 | 9399.5 |
| 6 | 3905.5 | 10119.3 | 74.2 | 3174.6 | 9398.2 |
| 7 | 3262.1 | 9447.2 | 74.4 | 3060.3 | 9276.8 |
| 8 | 3265 | 9449.9 | 71.6 | 3065.1 | 9283.1 |
| 9 | 3268.8 | 9421.7 | 67.7 | 3086.1 | 9302.5 |
| 10 | 3246.7 | 9399.6 | 67.4 | 3136.9 | 9354.1 |
| 11 | 3246.8 | 9399.8 | 68.9 | 3137.8 | 9356.3 |
| 12 | 3250.6 | 9403.4 | 73.4 | 3137 | 9355.2 |
| 13 | 3235.4 | 9388.1 | 74.2 | 3131 | 9353.7 |
| 14 | 3232.6 | 9385.7 | 73.6 | 3108.1 | 9334.5 |
| 15 | 3233.4 | 9386.3 | 74.5 | 3174.3 | 9403.3 |
| 16 | 3236.2 | 9389.1 | 74.1 | 3184.6 | 9413.2 |
| 17 | 3233 | 9385.8 | 72.7 | 3145.8 | 9370.5 |
| 18 | 3237.8 | 9390.6 | 74 | 3152 | 9378.3 |
| 19 | 3232.7 | 9385.5 | 74.4 | 3104.3 | 9332.1 |
| 20 | 3230.2 | 9383.4 | 71.9 | 3104.8 | 9331.8 |
| 21 | 3239.5 | 9392.4 | 68.6 | 3105.3 | 9335.6 |
| 22 | 3237.3 | 9390.1 | 71.5 | 3125.4 | 9357.9 |
| 23 | 3244.4 | 9397.1 | 71.7 | 3150.4 | 9377 |
| 24 | 3258.5 | 9411.2 | 67.7 | 3146.6 | 9372.4 |
| 25 | 3257.8 | 9410.3 | 67.9 | 3097.3 | 9322.7 |
| 26 | 3277.1 | 9430.1 | 70.1 | 3096.6 | 9321.7 |
| 27 | 3302.3 | 9487 | 74.1 | 3149.9 | 9374.8 |
| 28 | 3319.2 | 9503.9 | 74.2 | 3151.4 | 9375.2 |
| 29 | 3343.5 | 9560.2 | 73.7 | 3156.8 | 9385.5 |
| 30 | 3374 | 9590.7 | 76.1 | 3153.4 | 9381.5 |
| 31 | 3372.6 | 9589.2 | 75 | 3101.5 | 9329.3 |
| 32 | 3375.8 | 9592.4 | 74.4 | 3154.7 | 9382 |
| 33 | 3353.8 | 9570.4 | 75.8 | 3165.2 | 9390.4 |
| 34 | 3348.6 | 9565 | 74.3 | 3174.1 | 9404.6 |
| 35 | 3356.4 | 9572.8 | 74.7 | 3119.3 | 9348.6 |
| 36 | 3357.8 | 9574.2 | 76.3 | 3118.6 | 9345.6 |
| 37 | 3354.9 | 9571.3 | 74.3 | 3105.8 | 9328.5 |
| 38 | 3340.4 | 9556.6 | 72.7 | 3106.9 | 9329.1 |
| 39 | 3355.9 | 9572.3 | 69.8 | 3153.8 | 9381.3 |
| 40 | 3362.8 | 9579.2 | 68.8 | 3155.8 | 9383.5 |
| 41 | 3342.5 | 9558.8 | 71.8 | 3153.3 | 9380.7 |
| 42 | 3363.8 | 9580 | 74.4 | 3160.9 | 9390 |
| 43 | 3362.9 | 9579.1 | 75.8 | 3152 | 9380.6 |
| 44 | 3361.4 | 9577.6 | 72.7 | 3154.3 | 9382.4 |
| 45 | 3342.4 | 9558.7 | 75.6 | 3152.8 | 9382.6 |
| 46 | 3339.4 | 9555.6 | 74.7 | 3150.9 | 9380.3 |
| 47 | 3360.2 | 9576.3 | 74.1 | 3100.2 | 9328.5 |
| 48 | 3366.1 | 9582.7 | 75.8 | 3086.8 | 9315.3 |
| 49 | 3365.8 | 9582 | 74.6 | 3110.4 | 9341.7 |
| 50 | 3384.5 | 9632.6 | 74 | 3098.3 | 9329.1 |
| 51 | 3385.9 | 9634 | 75.5 | 3164.6 | 9395.1 |
| 52 | 3385 | 9633.3 | 74.3 | 3159.8 | 9390 |
| 53 | 3384 | 9632.2 | 72.3 | 3158.4 | 9389.6 |
| 54 | 3363.7 | 9611.7 | 69.4 | 3223.5 | 9428.7 |
| 55 | 3364.6 | 9612.6 | 68 | 3221.2 | 9420 |
| 56 | 3364.3 | 9612.4 | 70.6 | 3169.6 | 9400.7 |
| 57 | 3345.2 | 9593.2 | 74.6 | 3187.3 | 9384.7 |
| 58 | 3344.3 | 9592.2 | 74.9 | 3188.5 | 9386.4 |
| 59 | 3369 | 9616.9 | 72.8 | 3138.1 | 9335.6 |
| 60 | 3377.8 | 9625.6 | 74.4 | 3190.4 | 9387.6 |

**Note:** minute 0 is taken at launch, before the game has loaded.
