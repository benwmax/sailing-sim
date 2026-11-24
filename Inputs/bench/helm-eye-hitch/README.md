# The helm-eye hitch on Windows-9291fbf6 (PC, Nov 24 2026)

**The view:** `helm-eye` from 9291fbf6's `views.ps1`: `-SailingShowCrew=1 -SailingWorld=Lake -SailingLaunch=1
-SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingHoldTWA=45`.

**Runs:** Ultra 1920x1080 100%, the sweep's 12 s bench (3 s warm-up, measured from about 3 s to 15 s), with
`-SailingBenchTrace`. Three runs, then one with an Insights trace. Each run's `frames.csv` and `bench.json` are here.

## Where it lands

Frames over 25 ms inside the measured window (frame index counted from the first frame of the run):

| Run | fps | max ms | Slow frames: index, time, frame ms, game-thread ms |
|---|---|---|---|
| r1 | 72.9 | 115.6 | **#120** 3.40 s 92.7 (game 92.8); **#840** 13.24 s 115.6 (game 115.3) |
| r2 | 70.0 | 137.6 | **#480** 8.55 s 86.5 (game 86.8); **#600** 10.21 s 29.3 (game 28.8); **#720** 11.97 s 137.6 (game 137.3); #100 3.03 s 34.6 (render 34.5) |
| r3 | 71.5 | 142.8 | **#240** 4.90 s 35.8 (game 35.9); **#960** 14.93 s 142.8 (game 142.2) |
| trace | 69.4 | 19.5 | none |

- **Always on the game thread.** In every hitch the frame time equals the game-thread time; render, RHI and GPU are
  normal.
- **The time differs from run to run (3.4 to 14.9 s), but the frame doesn't: every game-thread hitch lands on a frame
  index that is an exact multiple of 120.** Most multiples of 120 are clean (the game thread's median is about 9.2 ms),
  and one to three per run stall for 29-143 ms. The one other slow frame, r2's #100, is on the render thread.
- **The traced run had no hitch**, so the Insights capture (57 MB, kept on the PC at
  `D:\dev\ss-fix\Artifacts\bench\helm-eye-hitch\helm-eye.utrace`) can't name a scope for it. Its game thread shows no
  instrumented flush or file scope over 5 ms in the measured window.

## The likely cause: the capture telemetry's flush every 120 rows

- helm-eye is a capture view (`-SailingCapture=HelmEye`). The capture writes `<shot>.telemetry.csv` one row per frame
  from the game thread: `ASailboatPawn` calls `CaptureTelemetry.Add` (SailboatPawn.cpp:5339).
- In `ReferenceCapture.cpp`, `FCaptureTelemetry::Add` ends with `if (++Count % 120 == 0) File->Flush();`. That is a
  synchronous flush of the file to disk on the game thread.
- **The rows match the frames one for one:** r1 has 1,029 telemetry rows and 1,029 frames, r2 996 and 996, r3 1,016 and
  1,016, the trace 984 and 984. So the flush runs on frames 120, 240, 360 and so on, exactly where the hitches land.
- Usually the flush returns at once. Sometimes the disk stalls it for 30-140 ms, which is why the size varies and why
  some runs (and last night's 52 ms) are milder. The traced run's flushes were all fast.
- **Other capture views get the same flush:** ShoreTele, Path, Tripod, film mode and the env stills. In-game play outside
  capture mode doesn't.

## Suggestion

Take the telemetry write off the game thread: buffer the rows and flush from a worker, or only at the end. Or at least
don't `Flush()` mid-run. A quick check would be to bench helm-eye with that flush removed, where the multiples-of-120
spikes should go.

Bean's Saved was held aside and restored (7B5CA7BE).
