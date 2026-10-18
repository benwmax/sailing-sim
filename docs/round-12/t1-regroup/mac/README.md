# Tree regroup: Mac check (M5 Pro, Metal, packaged Development)

Branch `t1-regroup-bands` at 530e02cf against main 092cadc5 (`Artifacts/apps/main.app`, packaged at a58eb1ec: no game
change between the two).

## World gate (`scripts/gate.sh --scope world`, High; 5 min 41 s wall: build, 145 tests, package, bench)

| view | fps | p99 ms | GPU ms | gate |
|---|---|---|---|---|
| marina | 61.5 | 17.21 | 15.66 | ok |
| coast-day | 54.1 | 20.69 | 17.69 | ok |
| coast-night | 63.6 | 20.05 | 14.16 | ok |
| helm-eye | 60.7 | 20.96 | 15.46 | ok |
| slip | 53.7 | 19.91 | 18.05 | ok |
| bridge | 66.2 | 16.57 | 14.29 | ok |
| marina-night | 59.7 | 19.40 | 16.07 | ok |

Verdict: pass, every view above its floor on the first run (no re-bench against main needed).

## Regroup frames (one launch per side)

`scripts/bench-mac.sh 120` on High, 1440x1080, `-SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=17
-SailingWind=12 -SailingTWA=110 -SailingHoldTWA=110 -SailingBenchTrace` (the autopilot holds 110 deg; the camera passes
the 100 m regroup step). Frame times from the trace, from 5 s in to the end of the window (the last frame of each run,
177 ms on both, is the ProfileGPU capture after the window and is left out):

| | avg fps | p99 ms | max ms | 50-55 s max |
|---|---|---|---|---|
| main | 66.9 | 15.91 | 44.0 | 44.0 (two frames, 41.9 and 44.0, at 52.1 s: the regroup) |
| branch | 67.1 | 15.80 | 18.9 | 16.2 |

On main the regroup is a 42-44 ms pair of frames on Metal; on the branch no frame in the window passes 19 ms. The branch
logs `Trees: 265 components (257 tiles)` at the first placement (294,449 trees).

## Still

`lake-towers-{main,branch}-high.jpg`: the round-12 lake-towers camera (`docs/round-12/t1-trees/mac/scenes.csv`,
`-SailingCapture=Chase`) on each package. The trees are the same: mean difference 1.2 / 255 over the shore band, 0.15% of
its pixels differ by more than 16 (cloud and water noise).
