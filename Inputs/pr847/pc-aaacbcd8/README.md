# PR #847 at aaacbcd8 on the PC (Nov 27 2026): stopped part way, as asked

**Head:** aaacbcd8 "Shore edges are kept by the terrain actor, not attached", parent **d35690a0 (#846's head)**: the
branch is stacked on #846, not on main. A reused worktree (`D:\dev\ss-fix-wt\pr852-30b9ea2f`, detached at aaacbcd8).

- **MSVC editor build:** Succeeded, 0 project warnings, 0 errors.
- **Full `SailingSim` suite:** started at 20:04 local. Stopped at 20:07 when the coordinator said to skip #847 until
  it's rebased onto main after Dec 11; only my supervisor and its test editor were stopped. **34 tests had completed, all
  Success** (`tests-completed-before-stop.txt`); no report was written.
- **Not run:** the package, the 40 s "cannot attach" count against main, and the Kemah stills.

Bean's Saved was not held during the tests (editor runs don't touch it) and reads 7B5CA7BE.
