# main, head a49fdbc5, on the PC

- **Head:** a49fdbc5 contains main a49fdbc5: used as is.
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\prmain`, at a49fdbc5. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main a49fdbc5:** ``.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.Fleet`: 9 passed, 0 failed, 8 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Fleet.ConfigsComplete | Success |  |
| SailingSim.Fleet.DinghyCapsizeAndRighting | Success |  |
| SailingSim.Fleet.DinghyPlanes | Success |  |
| SailingSim.Fleet.Engines | Success |  |
| SailingSim.Fleet.KeelboatsRecoverFromKnockdown | Success |  |
| SailingSim.Fleet.KnockdownIsNotACapsize | Success |  |
| SailingSim.Fleet.MultihullFliesAHullAndCapsizes | Success |  |
| SailingSim.Fleet.Polar.Bluebonnet | Success |  |
| SailingSim.Fleet.Polar.Catalina22 | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.Polar.Catalina30 | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.Polar.Corsair880 | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.Polar.Hobie16 | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.Polar.ILCA7 | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.Polar.J22 | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.Polar.Lagoon42 | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.Polar.Sunfish | Success | LogHttp: HTTP request timed out after 3.00 seconds URL=https://www.google.com/generate_204 |
| SailingSim.Fleet.SpinnakerAndReefing | Success |  |

## `SailingSim.Visual.FleetMesh`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.FleetMesh | Success |  |

## `SailingSim.Visual.RigClearance`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.RigClearance | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

## `SailingSim.Physics.Cannons`: 5 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Physics.Cannons.Drill | Success |  |
| SailingSim.Physics.Cannons.Params | Success |  |
| SailingSim.Physics.Cannons.Recoil | Success |  |
| SailingSim.Physics.Cannons.Smoke | Success |  |
| SailingSim.Physics.Cannons.Table | Success |  |

## `SailingSim.Career`: 15 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Career.Checkride | Success |  |
| SailingSim.Career.Content | Success |  |
| SailingSim.Career.DaySailorPlaythrough | Success |  |
| SailingSim.Career.DrillFinish | Success |  |
| SailingSim.Career.EasyMedal | Success |  |
| SailingSim.Career.FreeSail | Success |  |
| SailingSim.Career.Grading | Success |  |
| SailingSim.Career.Jobs | Success |  |
| SailingSim.Career.MedalLines | Success |  |
| SailingSim.Career.MedalWords | Success |  |
| SailingSim.Career.ReturnStartHeading | Success |  |
| SailingSim.Career.SaveRoundTrip | Success |  |
| SailingSim.Career.ScriptStepsGate | Success |  |
| SailingSim.Career.TexasCoastUnlock | Success |  |
| SailingSim.Career.Unlocks | Success |  |

## `SailingSim.UI.SessionFlow`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.UI.SessionFlow | Success |  |

**Note:** these ran in a fresh worktree at `a49fdbc5` (`D:\dev\ss-fix-wt\prmain`, crew linked), not in the main checkout. A standing rule keeps the main checkout at 40226d1c, so I didn't fast-forward it. It's the same tree. The Fleet suite's warnings are only the engine's online-check HTTP timeout.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.
