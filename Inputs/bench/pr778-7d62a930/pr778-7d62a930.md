# PR #778 (AI boat rig rebuild rate), head 7d62a930, on the PC

- **Head:** 7d62a930 contains main 687f777c: used as is.
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr778`, at 7d62a930. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main 687f777c:** `Source/SailingSim/Private/BoatModelVisuals.cpp`, `Source/SailingSim/Private/SailboatPawn.cpp`, `Source/SailingSim/Public/SailboatPawn.h`, `Source/SailingSim/Public/TrafficRigRate.h`, `Source/SailingSimTests/Private/TrafficTests.cpp`, `docs/traffic-rig-rate/README.md`.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.Visual.RopeLay`: 10 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.RopeLay.BlockTangent | Success |  |
| SailingSim.Visual.RopeLay.Deterministic | Success |  |
| SailingSim.Visual.RopeLay.DrapeOverTrunk | Success |  |
| SailingSim.Visual.RopeLay.FreeLine | Success |  |
| SailingSim.Visual.RopeLay.Knots | Success |  |
| SailingSim.Visual.RopeLay.ManyCases | Success |  |
| SailingSim.Visual.RopeLay.NoShimmer | Success |  |
| SailingSim.Visual.RopeLay.OverALifeline | Success |  |
| SailingSim.Visual.RopeLay.OverASailor | Success |  |
| SailingSim.Visual.RopeLay.WinchTurns | Success |  |

## `SailingSim.Traffic`: 7 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Traffic.AiGybesDownwind | Success |  |
| SailingSim.Traffic.BusyBayNoCollisions | Success | LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr778/Content/TerrainData/GalvestonBay.detail' error. |
| SailingSim.Traffic.CoachScoresThePlayer | Success |  |
| SailingSim.Traffic.HobieUprightOnAGustyRun | Success |  |
| SailingSim.Traffic.ParallelStep | Success |  |
| SailingSim.Traffic.RigRebuildRate | Success |  |
| SailingSim.Traffic.RightOfWayDecisions | Success |  |
| SailingSim.Traffic.RulesScenarios | Success |  |

## `SailingSim.Race`: 2 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Race.AiFleetRace | Success |  |
| SailingSim.Race.ScoringRules | Success |  |

## Benches

- **Build:** a Development package of the merged-as-is head to the new `Packaged/Windows-7d62a930` (3 min), warmed once. Then back to back at Ultra 1920x1080 with `-SailingScreenPct=100 -SailingBenchTrace -SailingDemo`, 12 s each.
- **The crew view:** bench-visual's `crew` view.
- **The traffic view:** `lake-busy` from `scripts/bench-phase6.sh`: `-SailingWorld=0 -SailingLaunch=1 -SailingHour=13 -SailingCamYaw=200 -SailingCamPitch=-12 -SailingCamDist=60`. The PC's `views.ps1` has no traffic view, and last night's run had no matching view, so I ran it on `Windows-687f777c` too, as the baseline.
- **Traffic:** each view with `-SailingTraffic=1` and `-SailingTraffic=0`.
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Files:** `runs.csv` with the exact args, and `bench.json` and `frames.csv` per run.

| Run | Package | fps | p99 ms | game ms | render ms | RHI ms | GPU frame | GPU total | foreground |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| crew-traffic1 | Windows-7d62a930 | 59.1 | 21.46 | 11.32 | 16.92 | 8.34 | 11.26 | 8.43 | 0 |
| crew-traffic0 | Windows-7d62a930 | 60.7 | 20.62 | 9.45 | 16.46 | 8.03 | 11.21 | 8.18 | 0 |
| busy-traffic1 | Windows-7d62a930 | 69.5 | 18.18 | 10.12 | 14.37 | 7.66 | 9.04 | 7.36 | 0 |
| busy-traffic0 | Windows-7d62a930 | 70.5 | 18.64 | 8.59 | 14.17 | 7.47 | 8.99 | 7.41 | 0 |
| main-busy-traffic1 | Windows-687f777c | 52.9 | 23.36 | 13.86 | 18.88 | 8.32 | 9.34 | 7.67 | 0 |
| main-busy-traffic0 | Windows-687f777c | 72.7 | 17.93 | 8.65 | 13.75 | 7.45 | 9 | 7.24 | 0 |

Every run reports `foreground: 0`: the window was not in front, and I don't move windows or send input.

## What comes back

- **Crew view:** main 687f777c's control was **49.1 fps** with traffic, and **58.2** with `-SailingTraffic=0` (`profile-main-nov17/split`). #778 gives **59.1 with traffic on** and 60.7 with it off.
  - **Gap closed:** of main's 9.1 fps gap, **all but 1.6 fps** comes back.
  - **Threads:** game 14.8 to 11.3 ms, render 20.4 to 16.9 ms.
- **Traffic view (lake-busy):** on main, **52.9 fps** with traffic against 72.7 without. #778 gives **69.5** with traffic against 70.5 without. Of a 19.8 fps gap, 1.0 is left (game 13.9 to 10.1 ms, render 18.9 to 14.4 ms).
  - **Caveat:** #778's traffic-off run (70.5) is 2.2 fps under main's (72.7). That's within this desktop's run-to-run spread, since the window wasn't in front.

## Rebuilds in the crew view, traffic on (Insights)

The trace is at `D:\dev\ss-fix\Artifacts\profile\crew-pr778-7d62a930.utrace` on the PC. The window is the last 12 s, **11.89 to 23.89 s**, 634 frames, with `-SailingNoGpuSlices`. The CSVs are `default-*.csv`.

| Build | UpdateSection RT calls/frame | RT ms/frame | UpdateSection GT ms/frame | Sailing_BoatVisuals runs/frame | Sailing_RigLines calls/frame (incl ms) |
| --- | --- | --- | --- | --- | --- |
| main 687f777c (control trace) | 16.5 | 5.30 | 1.82 | 4.0 | 4.0 (2.62) |
| main 687f777c, traffic off (run i) | 6.0 | 1.74 | 0.66 | 1.0 | 1.0 (0.72) |
| **#778 7d62a930, traffic on** | **7.0** | **2.39** | **0.75** | **4.0** | **1.1 (2.42)** |

- **The AI boats now rebuild about 1 section a frame between them**, down from about 10. The total is 7.0 a frame against the player-only 6.0.
- **They still tick their visuals every frame:** `Sailing_BoatVisuals` runs 4 times a frame. But `Sailing_RigLines` runs about 1.1 times a frame, so it's mostly the player's boat now.
- **The render thread's top items in this trace:** UpdateSection RT 2.39 ms, `WaitForTasks` 1.58, RDG allocation 0.87, texture-region uploads 0.66, task waits 0.54, RDG collection 0.43.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.
