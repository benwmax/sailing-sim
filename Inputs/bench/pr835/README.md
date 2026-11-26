# PR #835 at c2fed053 (logbook local time): PC build and tests (Nov 26 2026)

**Branch:** `claude/project-thread-6i4sx0` at c2fed053, "Logbook: name and list sails by the world's local clock, not UTC".
It's in the new worktree `D:\dev\ss-fix-wt\pr835`.

**MSVC build:** succeeded, 0 project warnings.

**`SailingSim.Smoke`, headless:** 37 tests, 36 passed, 1 passed with warnings, **0 failed**, 0 not run
(`smoke-results.tsv`).

| Test | Result |
|---|---|
| `SailingSim.Smoke.LogbookWritesEntries` | **Success**, 0 warnings |
| `SailingSim.Smoke.LogbookListsLocalTime` | **Success**, 0 warnings |
| `SailingSim.Smoke.KeyRebinding` | **Success**, 0 warnings |

**The one test with warnings:** `SailingSim.Smoke.AsyncPhysicsMatchesSync` (13). It's the same one that has warnings on #839 f186aa47.
