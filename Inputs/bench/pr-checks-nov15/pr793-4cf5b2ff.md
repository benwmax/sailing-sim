# PR #793 (frigate start spots), head 4cf5b2ff, on the PC

- **Head:** 4cf5b2ff merged locally with main 3d21e2d4 (not pushed).
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr793`, at bf3653fd. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main 3d21e2d4:** `Content/TerrainData/GalvestonBay.json`, `Source/SailingSim/Private/LakeData.cpp`, `Source/SailingSim/Private/SailingGameMode.cpp`, `Source/SailingSim/Private/UI/SailCatalog.cpp`, `Source/SailingSim/Public/LakeData.h`, `Source/SailingSim/Public/UI/SailCatalog.h`, `Source/SailingSimTests/Private/BluebonnetTests.cpp`, `Tools/coast/worlds/GalvestonBay.json`, `docs/frigate-physics/README.md`.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.UI.DeepKeelStarts`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.UI.DeepKeelStarts | Success |  |

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
| SailingSim.UI.Feedback.Jpeg | Success | LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr793/Saved/Automation/Tmp/SailFeedbackJpeg/missing.png' error. |
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

## `SailingSim.Coast`: 17 passed, 0 failed, 4 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Coast.ChartSymbolsMatchNoaaChart | Success | LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr793/Content/TerrainData/GalvestonBay.detail' error. |
| SailingSim.Coast.CurrentSetsTheBoat | Success |  |
| SailingSim.Coast.CurrentTimesMatchNoaa | Success |  |
| SailingSim.Coast.DepthsMatchChartSoundings | Success |  |
| SailingSim.Coast.GalvestonSwell | Success | LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr793/Content/TerrainData/GalvestonBay.detail' error. |
| SailingSim.Coast.GulfFront | Success |  |
| SailingSim.Coast.KeptStaticFollowsTide | Success |  |
| SailingSim.Coast.Landmarks | Success |  |
| SailingSim.Coast.LightsFlashTheirCharacteristics | Success |  |
| SailingSim.Coast.LongPassageStable | Success | LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr793/Content/TerrainData/GulfPassage.detail' error. |
| SailingSim.Coast.MarseilleCassis | Success | LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr793/Content/TerrainData/Marseille.detail' error. |
| SailingSim.Coast.MarseilleLights | Success |  |
| SailingSim.Coast.MarseilleLoads | Success |  |
| SailingSim.Coast.MarseilleMooredBoatsAfloat | Success |  |
| SailingSim.Coast.MarseilleShoreAndSeams | Success |  |
| SailingSim.Coast.MooredBoatsAfloat | Success |  |
| SailingSim.Coast.MooredPowerClasses | Success |  |
| SailingSim.Coast.Piers | Success |  |
| SailingSim.Coast.PlottedFixesLandWithinTolerance | Success |  |
| SailingSim.Coast.SunRisesAndSetsOnTime | Success |  |
| SailingSim.Coast.TideTimesMatchNoaa | Success |  |

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.
