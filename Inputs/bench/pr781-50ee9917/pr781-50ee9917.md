# PR #781 (MetaHumans aft on a big crew), head 50ee9917, on the PC

- **Head:** 50ee9917 merged locally with main ecd4ed1c (not pushed).
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr781`, at 4c5dfdfa. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main ecd4ed1c:** `Source/SailingSim/Private/SailboatPawn.cpp`, `Source/SailingSim/Public/CrewPose.h`, `Source/SailingSim/Public/SailboatPawn.h`, `Source/SailingSimTests/Private/CrewCostTests.cpp`, `docs/crew-cost/README.md`.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.Visual.MetaHumanCrewCap`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.MetaHumanCrewCap | Success |  |

## `SailingSim.Smoke.MetaHumanCrewMix`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Smoke.MetaHumanCrewMix | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

## `SailingSim.Smoke.ShowCrew`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Smoke.ShowCrew | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

## `SailingSim.Visual.MetaHumanCrew`: 2 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.MetaHumanCrew | Success |  |
| SailingSim.Visual.MetaHumanCrewCap | Success |  |

## `SailingSim.Visual.CrewFalls`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.CrewFalls | Success |  |

## `SailingSim.Visual.RigClearance`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.RigClearance | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

## `SailingSim.Visual.CrewHullClearance`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.CrewHullClearance | Success |  |

## Bench: helm-eye, Ultra 1920x1080, `-SailingScreenPct=100`

- **Setup:** Development package of the local merge into the new `Packaged/Windows-50ee9917` (3 min). Warmed once, then each run once, 12 s.
- **Shared args:** `-SailingWorld=Lake -SailingLaunch=1 -SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingHoldTWA=45`.
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).

| Run | Args | fps | p99 ms | game ms | render ms | RHI ms | GPU total ms | base | foreground |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| blue-default | `-SailingBoat=Bluebonnet -SailingShowCrew=1` | 53.4 | 24.89 | 15.6 | 18.34 | 9.96 | 7.64 | 3.5 | 0 |
| blue-metacrew12 | `-SailingBoat=Bluebonnet -SailingShowCrew=1 -SailingMetaCrew=12` | 43.9 | 30.8 | 21.78 | 22.66 | 12.29 | 8.17 | 4.04 | 0 |
| maxi-default | `-SailingBoat=Maxi -SailingShowCrew=1` | 57 | 22.41 | 14.9 | 17.47 | 9.17 | 8.1 | 3.8 | 0 |
| maxi-metacrew12 | `-SailingBoat=Maxi -SailingShowCrew=1 -SailingMetaCrew=12` | 42.4 | 33.97 | 22.86 | 21.82 | 11.08 | 8.91 | 3.82 | 0 |

**The cap, in one build** (the default's 5 MetaHumans against `-SailingMetaCrew=12`, everything else equal):

- **Bluebonnet:** 43.9 to **53.4 fps** (+9.5). Game thread 21.8 to 15.6 ms, render thread 22.7 to 18.3, RHI 12.3 to 10.0. GPU 8.2 to 7.6.
- **Maxi:** 42.4 to **57.0 fps** (+14.6). Game thread 22.9 to 14.9 ms, render thread 21.8 to 17.5.
- **Against the doc's estimate:** about 6 to 8 ms of game thread saved, more than the README's 5 ms estimate. Bluebonnet lands at 53, above its "near 50".

**Against #758's numbers** (`pr758-bluebonnet-fps`, an older main, without the cap):

| Boat | crewed then | crew hidden then | now, cap of 5 |
| --- | --- | --- | --- |
| Bluebonnet | 40.8 | 60.5 | 53.4 |
| Maxi | 35.7 | — | 57.0 |

- **What else changed:** main has gained 5 to 11 fps on every view since then (`main-ecd4ed1c-bench`, mostly #778).
- **What that means:** read the like-for-like pair above for the cap itself, not the change from 40.8. The all-12 runs at 43.9 and 42.4 are today's equivalent of the old 40.8 and 35.7.
- **Foreground:** 0 on every run, as in recent benches.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.


