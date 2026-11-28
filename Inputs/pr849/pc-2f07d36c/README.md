# PR #849 at 2f07d36c on the PC (Nov 28 2026)

**Head:** 2f07d36c "Soak meter: no per-100 km figure under 10 km sailed", parent 8a5768b3 (`../pc-8a5768b3/` has the
earlier head's 20-minute lake run). The reused worktree (`D:\dev\ss-fix-wt\pr852-30b9ea2f`, detached at 2f07d36c). Build
and tests only; no package or long run. Nothing pushed to the PR branch.

| Step | Result |
|---|---|
| MSVC editor build | Succeeded, 0 project warnings, 0 errors |
| `SailingSim.Smoke.SoakMemory` | 1 test (`.Fit`), passed (`soakmemory-tests.json`) |
| `SailingSim.Smoke` | 39 tests: 38 passed, 1 with warnings (`AsyncPhysicsMatchesSync`: the optional `/Game/Audio/Samples/S_*`), 0 failed, 0 not run (`smoke-tests.json`) |
