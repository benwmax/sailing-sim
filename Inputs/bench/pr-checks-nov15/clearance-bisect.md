# RigClearance / SheetClearance on the PC: not a regression, a missing crew folder

**Result:** there is no first bad merge. Both tests fail on the PC whenever the checkout has no MetaHuman crew. `Content/Crew/MetaHumans/` is git-ignored, so a fresh worktree never gets it from `git lfs pull`. With the crew present, both tests pass on the PC at both ends of the range. The Mac's checkout has the crew, which is why it passes.

## Steps (PC, MSVC, `test.ps1 -Filter` one test at a time; headless; no package or game)

| # | commit | checkout | crew present | build | RigClearance | SheetClearance |
|---|---|---|---|---|---|---|
| 1 | 75ed143f (the "last green") | fresh worktree `D:\dev\ss-fix-wt\bisect` | no | Succeeded | **Fail**: Catalina 22 lazy jib sheet through crew 0's spine, 2.2 cm | **Fail**: Catalina 22 mainsheet tail through crew 2's spine, 4.9 cm; Maxi 100 lazy jib sheet through crew 4's spine, 4.7 cm |
| 2 | 40226d1c (#708, inside the range) | main checkout `D:\dev\ss-fix` | yes | Succeeded (up to date) | **Success** | **Success** |
| 3 | 0da7d6ea (#724, the bad end) | fresh worktree, `Content/Crew/MetaHumans` a junction to the main checkout's (541 files) | yes | Succeeded | **Success** | **Success** |
| ref | 0da7d6ea, this morning (#727 round 1) | fresh worktree | no | Succeeded | Fail, 2.4 cm (same line and crew) | Fail, 4.9 cm and 4.7 cm (same lines) |

- Step 1 already fails, so the bisect stopped there: the good end isn't good without the crew.
- Steps 2 and 3 then show that the crew folder alone decides the result, at the start of the range and at its end.
- Without the MetaHumans, the crew presumably falls back to SK_Sailor (`LoadMetaCrew`'s fallback, per CLAUDE.md). I didn't check that in the test's log.

## What follows

- **Earlier PC reports:** every clearance failure from a fresh worktree (`prcheck.ps1` runs and #727 round 1) comes from this missing folder. None of them is a code change.
- **Future PC checks of SailingSim.Visual:** I'll link the main checkout's `Content/Crew/MetaHumans` into each fresh worktree. Otherwise these two tests will always fail there.
- **A question for the thread:** should these tests hold the SK_Sailor fallback clear too? Low quality, AI boats and `-SailingBlenderCrew` use that crew, so the 2.2 to 4.9 cm overlaps are real on those paths.

Nothing was pushed or fixed. The worktree was removed (only the junction was unlinked; the target folder is intact), and the main checkout is clean at 40226d1c.
