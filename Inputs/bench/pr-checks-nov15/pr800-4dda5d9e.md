# PR #800 (Frigate wiring 11: the fleet's tests run on her; shorten sail down the officers' ladder), head 4dda5d9e, on the PC

- **Head:** 4dda5d9e contains main ad60911e: used as is.
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr800`, at 4dda5d9e. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main ad60911e:** `Source/SailingPhysics/Private/ShipOrders.cpp`, `Source/SailingPhysics/Public/ShipOrders.h`, `Source/SailingSim/Private/CrewMotion.cpp`, `Source/SailingSim/Private/SailboatPawn.cpp`, `Source/SailingSim/Private/ShipModelVisuals.cpp`, `Source/SailingSim/Private/ShipWalkVisuals.cpp`, `Source/SailingSim/Public/CrewMotion.h`, `Source/SailingSim/Public/SailboatPawn.h`, `Source/SailingSimTests/Private/ChaseCameraTests.cpp`, `Source/SailingSimTests/Private/CrewCostTests.cpp`, `Source/SailingSimTests/Private/CrewMotionTests.cpp`, `Source/SailingSimTests/Private/HullClipTests.cpp`, `Source/SailingSimTests/Private/ReferenceTests.cpp`, `Source/SailingSimTests/Private/RigClearanceTests.cpp`, `Source/SailingSimTests/Private/SailClothTests.cpp`, `Source/SailingSimTests/Private/ShipOrdersTests.cpp`, `Source/SailingSimTests/Private/VisualTests.cpp`, `docs/ship-orders/README.md`, `docs/ship-rig/README.md`.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.Visual.HullClip`: 0 passed, 1 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.HullClip | Fail | Expected 'Commonwealth: map bottom off the hull by > 3 cm (worst 0.398 m)' to be 0, but it was 46. |

**SailingSim.Visual.HullClip**, errors verbatim (2 distinct):

```
Expected 'Commonwealth: map bottom off the hull by > 3 cm (worst 0.398 m)' to be 0, but it was 46.
Expected 'Commonwealth: water left above the bottom inside a hull' to be 0, but it was 14.
```

## `SailingSim.Visual.ChaseCamera`: 3 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.ChaseCamera.Controls | Success |  |
| SailingSim.Visual.ChaseCamera.Mounts | Success |  |
| SailingSim.Visual.ChaseCamera.Pawn | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |
| SailingSim.Visual.ChaseCamera.Rig | Success |  |

## `SailingSim.Smoke.ReferenceCapture`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Smoke.ReferenceCapture | Success |  |

## `SailingSim.Visual.Spinnaker`: 2 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.SpinnakerClew | Success |  |
| SailingSim.Visual.SpinnakerHead | Success |  |

## `SailingSim.Visual.JibHead`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.JibHead | Success |  |

## `SailingSim.Visual.Crew`: 14 passed, 2 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.CrewBalanceStep | Success |  |
| SailingSim.Visual.CrewCapture | Success |  |
| SailingSim.Visual.CrewClipLimits | Success |  |
| SailingSim.Visual.CrewClipTack | Success |  |
| SailingSim.Visual.CrewClipVariety | Success |  |
| SailingSim.Visual.CrewClothLooseness | Success |  |
| SailingSim.Visual.CrewElbow | Success |  |
| SailingSim.Visual.CrewFalls | Success |  |
| SailingSim.Visual.CrewFeet | Fail | Commonwealth, Helm crew 0 (stance 7, starboard tack, hike 0.0): left toe at (19.39, -4.59, 4.46) m is inside the boat |
| SailingSim.Visual.CrewHeadLevel | Success |  |
| SailingSim.Visual.CrewHeldLine | Success |  |
| SailingSim.Visual.CrewHullClearance | Success |  |
| SailingSim.Visual.CrewMotionFeet | Fail | Commonwealth, Helm crew 0 (starboard rail, stance 7): right toe inside the boat at (18.87, -4.61, 4.44) m |
| SailingSim.Visual.CrewOutfit | Success |  |
| SailingSim.Visual.CrewPose | Success |  |
| SailingSim.Visual.CrewTack | Success |  |

**SailingSim.Visual.CrewFeet**, errors verbatim (24 distinct):

```
Commonwealth, Helm crew 0 (stance 7, starboard tack, hike 0.0): left toe at (19.39, -4.59, 4.46) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, starboard tack, hike 0.0): right toe at (18.88, -4.66, 4.44) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, starboard tack, hike 0.5): left toe at (19.39, -4.59, 4.46) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, starboard tack, hike 0.5): right toe at (18.88, -4.66, 4.44) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, starboard tack, hike 1.0): left toe at (19.39, -4.59, 4.46) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, starboard tack, hike 1.0): right toe at (18.88, -4.66, 4.44) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, port tack, hike 0.0): left toe at (19.39, -4.59, 4.46) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, port tack, hike 0.0): right toe at (18.88, -4.66, 4.44) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, port tack, hike 0.5): left toe at (19.39, -4.59, 4.46) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, port tack, hike 0.5): right toe at (18.88, -4.66, 4.44) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, port tack, hike 1.0): left toe at (19.39, -4.59, 4.46) m is inside the boat
Commonwealth, Helm crew 0 (stance 7, port tack, hike 1.0): right toe at (18.88, -4.66, 4.44) m is inside the boat
...
```

**SailingSim.Visual.CrewMotionFeet**, errors verbatim (86 distinct):

```
Commonwealth, Helm crew 0 (starboard rail, stance 7): right toe inside the boat at (18.87, -4.61, 4.44) m
Commonwealth, Helm crew 0 (starboard rail, stance 7): left toe inside the boat at (19.30, -4.66, 4.46) m
Commonwealth, Helm crew 0 (starboard rail, stance 7): left toe inside the boat at (19.36, -4.66, 4.46) m
Commonwealth, Helm crew 0 (starboard rail, stance 7): right toe inside the boat at (18.86, -4.72, 4.44) m
Commonwealth, Helm crew 0 (starboard rail, stance 7): right toe inside the boat at (18.89, -4.60, 4.44) m
Commonwealth, Helm crew 0 (starboard rail, stance 7): left toe inside the boat at (19.35, -4.59, 4.46) m
Commonwealth, Helm crew 0 (starboard rail, stance 7): right toe inside the boat at (18.86, -4.64, 4.44) m
Commonwealth, Helm crew 0 (starboard rail, stance 7): left toe inside the boat at (19.26, -4.59, 4.46) m
Commonwealth, Helm crew 0 (port rail, stance 7): left toe inside the boat at (19.28, -4.58, 4.46) m
Commonwealth, Helm crew 0 (port rail, stance 7): left toe inside the boat at (19.36, -4.59, 4.46) m
Commonwealth, Helm crew 0 (port rail, stance 7): right toe inside the boat at (18.85, -4.65, 4.44) m
Commonwealth, Helm crew 0 (port rail, stance 7): right toe inside the boat at (18.86, -4.60, 4.44) m
...
```

## `SailingSim.Visual.ShipWatch`: 2 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.ShipWatch.Deck | Success |  |
| SailingSim.Visual.ShipWatch.Stations | Success |  |

## `SailingSim.ShipOrders`: 4 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.ShipOrders.Guns | Success |  |
| SailingSim.ShipOrders.Panel | Success |  |
| SailingSim.ShipOrders.Rules | Success |  |
| SailingSim.ShipOrders.SailPlan | Success |  |

## `SailingSim.Visual.MetaHumanCrewCap`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.MetaHumanCrewCap | Success |  |

## Notes on the three failures

All three are on the **Commonwealth** (the frigate) only. Every other boat passed in the same tests. #800 removes the `if (IsSquareRigged(...)) continue;` skip from `HullClipTests.cpp` (1 line) and from three loops in `CrewMotionTests.cpp` (now `CrewFigureCount(Cfg)`, her deck watch). So these tests check the frigate for the first time in this PR. These are new checks failing on her, not existing boats regressing.

- **`SailingSim.Visual.HullClip`:**
  - The hull-clip map's bottom is more than 3 cm off the hull in 46 cells (worst 0.398 m).
  - Water is left above the bottom inside a hull in 14 cells.
- **`SailingSim.Visual.CrewFeet`:** 24 errors.
  - All are Helm crew 0, stance 7, on both tacks and at every hike.
  - The left toe is at about (19.39, -4.59, 4.46) m and the right toe at about (18.88, -4.66, 4.44) m, both "inside the boat".
- **`SailingSim.Visual.CrewMotionFeet`:** 87 errors, again Helm crew 0, stance 7, on both rails, toes inside the boat at about x 18.9 to 19.4 m.
  - It passed on #796's merged head `3ee6a5d1` (main `ad60911e`'s second parent; pr796 check, Nov 17 22:43), but that run still skipped the frigate.


## Full suite

**Superseded:** #800 moved to d37eb38f (the frigate's HullClip and feet fixes) before its full suite ran. The full suite runs on d37eb38f instead: see `pr800-d37eb38f.md`.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.
