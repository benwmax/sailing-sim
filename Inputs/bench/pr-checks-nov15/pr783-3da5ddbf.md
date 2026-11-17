# PR #783 (ship rig and orders), head 3da5ddbf, on the PC

- **Head:** 3da5ddbf contains main ecd4ed1c: used as is.
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr783`, at 3da5ddbf. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main ecd4ed1c:** `Source/SailingPhysics/Private/CommonwealthRigData.inl`, `Source/SailingPhysics/Private/ShipOrders.cpp`, `Source/SailingPhysics/Private/ShipRig.cpp`, `Source/SailingPhysics/Public/ShipOrders.h`, `Source/SailingPhysics/Public/ShipRig.h`, `Source/SailingSim/Private/SailboatPawn.cpp`, `Source/SailingSim/Private/ShipModelVisuals.cpp`, `Source/SailingSim/Private/ShipWalkVisuals.cpp`, `Source/SailingSim/Public/SailboatPawn.h`, `Source/SailingSimTests/Private/ShipOrdersTests.cpp`, `Source/SailingSimTests/Private/ShipRigTests.cpp`, `docs/ship-orders/README.md`, `docs/ship-rig/README.md`.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.ShipRig`: 3 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.ShipRig.Motion | Success |  |
| SailingSim.ShipRig.Pose | Success |  |
| SailingSim.ShipRig.Table | Success |  |

## `SailingSim.ShipOrders`: 3 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.ShipOrders.Panel | Success |  |
| SailingSim.ShipOrders.Rules | Success |  |
| SailingSim.ShipOrders.SailPlan | Success |  |

## `SailingSim.UI`: 43 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.UI.CertificateOpens | Success |  |
| SailingSim.UI.ChoiceKeepsFocus | Success |  |
| SailingSim.UI.ContinueKeepsItsDifficulty | Success |  |
| SailingSim.UI.Credits | Success |  |
| SailingSim.UI.DeepKeelStarts | Success |  |
| SailingSim.UI.EscOpensMenu | Success |  |
| SailingSim.UI.Feedback.DefaultTitle | Success |  |
| SailingSim.UI.Feedback.Jpeg | Success | LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr783/Saved/Automation/Tmp/SailFeedbackJpeg/missing.png' error. |
| SailingSim.UI.Feedback.Recorder | Success |  |
| SailingSim.UI.Feedback.Report | Success |  |
| SailingSim.UI.Feedback.SendsWithCrashReportsOff | Success |  |
| SailingSim.UI.FirstLaunch | Success |  |
| SailingSim.UI.Gallery.Index | Success |  |
| SailingSim.UI.Gallery.Registry | Success |  |
| SailingSim.UI.GamepadBindings | Success |  |
| SailingSim.UI.GraphicsRows | Success |  |
| SailingSim.UI.JobPause | Success |  |
| SailingSim.UI.KeyboardOnlyRows | Success |  |
| SailingSim.UI.LessonKeepsFreeSail | Success |  |
| SailingSim.UI.LoadingStill | Success |  |
| SailingSim.UI.MeasuringIgnoresSave | Success |  |
| SailingSim.UI.MiniMapMarks | Success |  |
| SailingSim.UI.OneCoach | Success |  |
| SailingSim.UI.Overhaul.Mode | Success |  |
| SailingSim.UI.Overhaul.Paper | Success |  |
| SailingSim.UI.Overhaul.Tokens | Success |  |
| SailingSim.UI.Overhaul.Type | Success |  |
| SailingSim.UI.PadCoversLessonKeys | Success |  |
| SailingSim.UI.PadGlyphs | Success |  |
| SailingSim.UI.PadNoCollisions | Success |  |
| SailingSim.UI.PaperGrain | Success |  |
| SailingSim.UI.PhotoFreeFly.Camera | Success |  |
| SailingSim.UI.PhotoFreeFly.Input | Success |  |
| SailingSim.UI.PhotoFreeFly.Limits | Success |  |
| SailingSim.UI.PhotoPanel | Success |  |
| SailingSim.UI.SessionFlow | Success |  |
| SailingSim.UI.Showroom.Logic | Success |  |
| SailingSim.UI.Showroom.Orbit | Success |  |
| SailingSim.UI.Showroom.WorldBehindMenus | Success |  |
| SailingSim.UI.SliceBuild | Success |  |
| SailingSim.UI.StillArgs.LastValueWins | Success |  |
| SailingSim.UI.StillArgs.PhotoPanelNoHud | Success |  |
| SailingSim.UI.TitleFocus | Success |  |
| SailingSim.UI.TrimVerdict | Success |  |

## Since f6779657

- **The link error is gone.** `FShipRigData` is now exported, and MSVC links clean.
- **The earlier error, also gone:** the C4458 'Children' shadowing from 5195f847.
- **Tests:** ShipRig, ShipOrders and UI all pass (49 tests). The only warning is Feedback.Jpeg's deliberate missing.png.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.
