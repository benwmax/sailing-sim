# PR #725 (UI phase 9 typefaces), head 7dbdd14a, on the PC

Head 7dbdd14a contains main 0da7d6ea: used as is, built in a fresh worktree of its own (`D:\dev\ss-fix-wt\pr725`, at 7dbdd14a;
never pushed; removed afterwards). Changed against main 0da7d6ea: `CREDITS.md`, `Content/UI/Fonts/AtkinsonHyperlegibleNext-Medium.ttf`, `Content/UI/Fonts/AtkinsonHyperlegibleNext-Regular.ttf`, `Content/UI/Fonts/AtkinsonHyperlegibleNext-SemiBold.ttf`, `Content/UI/Fonts/B612-Bold.ttf`, `Content/UI/Fonts/B612-Regular.ttf`, `Content/UI/Fonts/Besley-Bold.ttf`, `Content/UI/Fonts/Besley-SemiBold.ttf`, `Content/UI/Fonts/OFL-AtkinsonHyperlegibleNext.txt`, `Content/UI/Fonts/OFL-B612.txt`, `Content/UI/Fonts/OFL-Besley.txt`, `Source/SailingSim/Private/UI/SailCatalog.cpp`, `Source/SailingSim/Private/UI/SailCustomize.cpp`, `Source/SailingSim/Private/UI/SailFrontEnd.cpp`, `Source/SailingSim/Private/UI/SailGallery.cpp`, `Source/SailingSim/Private/UI/SailHud.cpp`, `Source/SailingSim/Private/UI/SailUIStyle.cpp`, `Source/SailingSim/Private/UI/SailWidgets.cpp`, `Source/SailingSim/Public/UI/SailUIStyle.h`, `docs/licences/assets.csv`, `docs/ui-overhaul/README.md`, `docs/ui-overhaul/faces/boat.jpg`, `docs/ui-overhaul/faces/briefing.jpg`, `docs/ui-overhaul/faces/conditions.jpg`, `docs/ui-overhaul/faces/controls.jpg`, `docs/ui-overhaul/faces/hud-natural.jpg`, `docs/ui-overhaul/faces/hud.jpg`, `docs/ui-overhaul/faces/launch.jpg`, `docs/ui-overhaul/faces/loading.jpg`, `docs/ui-overhaul/faces/logbook.jpg`, `docs/ui-overhaul/faces/pause.jpg`, `docs/ui-overhaul/faces/quiz.jpg`, `docs/ui-overhaul/faces/settings.jpg`, `docs/ui-overhaul/faces/title.jpg`, `docs/ui-overhaul/faces/world.jpg`.

**MSVC build:** Succeeded, **0 errors, 0 warnings in our Source**. A from-scratch build in a fresh worktree also prints the engine headers' own C4996 deprecations, as every full build does.

**`test.ps1 -Filter SailingSim.UI`:** 40 passed, 0 failed, 1 with warnings, 0 not run.

- SailingSim.UI.CertificateOpens Success
- SailingSim.UI.ChoiceKeepsFocus Success
- SailingSim.UI.ContinueKeepsItsDifficulty Success
- SailingSim.UI.Credits Success
- SailingSim.UI.EscOpensMenu Success
- SailingSim.UI.Feedback.DefaultTitle Success
- SailingSim.UI.Feedback.Jpeg Success (Warning: LogStreaming: Failed to read file 'D:/dev/ss-fix-wt/pr725/Saved/Automation/Tmp/SailFeedbackJpeg/missing.png' error.)
- SailingSim.UI.Feedback.Recorder Success
- SailingSim.UI.Feedback.Report Success
- SailingSim.UI.Feedback.SendsWithCrashReportsOff Success
- SailingSim.UI.FirstLaunch Success
- SailingSim.UI.Gallery.Index Success
- SailingSim.UI.Gallery.Registry Success
- SailingSim.UI.GamepadBindings Success
- SailingSim.UI.GraphicsRows Success
- SailingSim.UI.JobPause Success
- SailingSim.UI.KeyboardOnlyRows Success
- SailingSim.UI.LessonKeepsFreeSail Success
- SailingSim.UI.LoadingStill Success
- SailingSim.UI.MeasuringIgnoresSave Success
- SailingSim.UI.MiniMapMarks Success
- SailingSim.UI.OneCoach Success
- SailingSim.UI.Overhaul.Mode Success
- SailingSim.UI.Overhaul.Paper Success
- SailingSim.UI.Overhaul.Tokens Success
- SailingSim.UI.Overhaul.Type Success
- SailingSim.UI.PadCoversLessonKeys Success
- SailingSim.UI.PadNoCollisions Success
- SailingSim.UI.PhotoFreeFly.Camera Success
- SailingSim.UI.PhotoFreeFly.Input Success
- SailingSim.UI.PhotoFreeFly.Limits Success
- SailingSim.UI.PhotoPanel Success
- SailingSim.UI.SessionFlow Success
- SailingSim.UI.Showroom.Logic Success
- SailingSim.UI.Showroom.Orbit Success
- SailingSim.UI.Showroom.WorldBehindMenus Success
- SailingSim.UI.SliceBuild Success
- SailingSim.UI.StillArgs.LastValueWins Success
- SailingSim.UI.StillArgs.PhotoPanelNoHud Success
- SailingSim.UI.TitleFocus Success
- SailingSim.UI.TrimVerdict Success

Feedback.Jpeg's warning is the test's own check of a missing picture (it asks for one on purpose); main gives the same.

**Fonts:** after `git lfs pull` in the worktree, `Content/UI/Fonts` holds real files: AtkinsonHyperlegibleNext-Medium.ttf 67080 B, AtkinsonHyperlegibleNext-Regular.ttf 65068 B, AtkinsonHyperlegibleNext-SemiBold.ttf 66680 B, B612-Bold.ttf 100932 B, B612-Regular.ttf 153192 B, Besley-Bold.ttf 154392 B, Besley-SemiBold.ttf 155648 B, OFL-AtkinsonHyperlegibleNext.txt 4524 B, OFL-B612.txt 4470 B, OFL-Besley.txt 4486 B, OFL-Saira.txt 4496 B, OFL-SourceSans3.txt 4579 B, SairaCondensed-Bold.ttf 96428 B, SairaCondensed-SemiBold.ttf 96028 B, SairaSemiCondensed-Medium.ttf 95548 B, SairaSemiCondensed-Regular.ttf 95184 B, SairaSemiCondensed-SemiBold.ttf 96160 B, SourceSans3.ttf 646340 B.

The test log has no font-loading warnings or errors.

Built at exactly 7dbdd14a. Since 0645320a (which passed: `pr725-0645320a.md`), only SailFrontEnd.cpp and SailCatalog.cpp changed.

No package, bench or game launch.
