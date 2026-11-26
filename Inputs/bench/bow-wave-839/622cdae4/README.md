# #839 at 622cdae4 (main merged in; Fft2 on #837's WakeParallel): PC build and tests (Nov 26 2026)

**Worktree:** `D:\dev\ss-fix-wt\pr839`, moved from f186aa47 to a clean 622cdae4, "Frame pacing doc: the wake FFT's column
pass (#839)". `WakeGrid.cpp` calls `WakeParallel` from `Fft2` for both passes, including the blocked column pass.

**MSVC build:** succeeded with 0 errors and 0 project warnings. `WakeGrid.cpp` has no warnings or errors in the log
(`build.log`).

**`SailingSim.Smoke`:** 38 tests, 37 passed, 1 with warnings (`AsyncPhysicsMatchesSync`), **0 failed**
(`test-smoke.json`).

**`SailingSim.Visual`: the run crashed, out of memory, in `SailingSim.Visual.SheetClearance`.**
- **Before the crash:** 83 tests completed, all **Success** (`visual-run1-completed.tsv`). That includes every
  `WakeGrid*` and `BowCrest` test that sorts before `SheetClearance`.
- **The crash:** `SheetClearance` cycles every boat with her crew. It got through the J/22, Sunfish, ILCA, Catalina 22 and
  30, Hobie 16, Corsair, Lagoon, Maxi and Bluebonnet. Then the editor died:
  ```
  Ran out of memory allocating 1048576 bytes ... The paging file is too small for this operation to complete.
  ```
- **Memory at that point:** used virtual 145 GB, used physical 45.9 GB (peak 52.2 GB). The system's commit limit is
  96 GB, on 64 GB RAM.
- **On f186aa47** (`../f186aa47-suite/`) the same test passed in 2 min, and Visual was 109 of 109.
- **The difference is main's merge,** not the FFT: `SheetClearance` doesn't run the wake.
  - It could be a leak or growth from something main brought in, or memory pressure on the PC at the time.
  - Nothing else of mine was running; the soak had ended at 11:07.

**Next:** I'm rerunning `SheetClearance` alone, then the full `SailingSim.Visual`, with the editor's commit and the
system's free commit sampled every 5 s. That runs after #834 21b89105's job. The results will be added here.
