# #839 at f186aa47: SailingSim.Visual and SailingSim.Smoke, the PC half (Nov 26 2026)

**Setup:** worktree `D:\dev\ss-fix-wt\pr839` at f186aa47 ("Wake grid: the FFT's columns in contiguous blocks (again)").
- The incremental MSVC build succeeded, so the editor binaries are current.
- `scripts\windows\test.ps1` runs each filter headless.

| Filter | Tests | Passed | Passed with warnings | Failed | Not run | Time |
|---|---|---|---|---|---|---|
| `SailingSim.Visual` | 109 | 104 | 5 | **0** | 0 | 13 min |
| `SailingSim.Smoke` | 36 | 35 | 1 | **0** | 0 | 1 min |

**All pass.** The six tests that pass with warnings:

| Test | Warnings |
|---|---|
| `SailingSim.Visual.ChaseCamera.Pawn` | 13 |
| `SailingSim.Visual.FarCapFlecks` | 1 |
| `SailingSim.Visual.J22HeroMesh` | 2 |
| `SailingSim.Visual.TreeSpecies` | 1 |
| `SailingSim.Visual.WakeGridShip` | 1 |
| `SailingSim.Smoke.AsyncPhysicsMatchesSync` | 13 |

**Per-test states:** `*-results.tsv` (state, warning count, test).
