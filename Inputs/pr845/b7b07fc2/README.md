# PR #845 at b7b07fc2 on the PC (Nov 27 2026)

**Head:** b7b07fc2 "Wildlife Phase 1: each bird keeps its own instance, sent with its previous transform, so TSR sees it
move", parent main 2479e9cf. The diff is 6 files, +208/-47, under `Source/` and `docs/` only. Its own worktree
(`D:\dev\ss-fix-wt\pr845-b7b07fc2`, clean, crew linked).

| Step | Result |
|---|---|
| MSVC editor build (`scripts\windows\build.ps1`) | Succeeded, 0 project warnings, 0 errors |
| `test.ps1 -Filter SailingSim.Wildlife` | 11 tests: 11 passed, 0 failed, 0 not run; `SailingSim.Wildlife.Keys` passed |
| `test.ps1 -Filter SailingSim.Smoke` | 38 tests: 37 passed, 1 passed with warnings, 0 failed, 0 not run |

**The one warning** is `SailingSim.Smoke.AsyncPhysicsMatchesSync`: `Failed to find object 'SoundBase
/Game/Audio/Samples/S_Wind.S_Wind'` (also `S_GustRumble`, `S_SailFlog`). That's the audio samples missing from this fresh
worktree's content, not the PR's code.

`wildlife-tests.json` and `smoke-tests.json` are the reports. Not run: a package or an in-game look at the birds under
TSR. The W20b AA test (`Inputs/reel-rehearsal/wildlife-w20b/aa-test/`) can be repeated on a package of it.
