# Main 91c8c80d: pre-candidate check on the PC (Nov 18-19)

**Build:**

- Worktree D:\dev\ss-fix-wt\main at origin/main 91c8c80d. It contains efe30335: #805's water fix with M_Water and M_WaterV4 rebuilt, plus #808 and #811.
- git lfs pull, crew linked (541 files). MSVC build: Succeeded, 0 errors.
- The worktree is **kept** for the Nov 20 candidate, since nothing failed.

**First attempt:** it stalled for 48 minutes inside git worktree add, with git-lfs's smudge stuck at 3.6 GB. I stopped those processes (all mine) and redid the checkout with smudge skipped and a separate git lfs pull (exit 0, about 8 minutes).

## Tests (scripts\windows\test.ps1, one run per filter)

| Filter | Tests | Passed | Failed | Passed with warnings |
|---|---|---|---|---|
| `SailingSim.Visual` | 106 | 106 | 0 | 3 |
| `SailingSim.Smoke` | 32 | 32 | 0 | 1 |
| `SailingSim.Fleet` | 19 | 19 | 0 | 6 |
| `SailingSim.World` | 8 | 8 | 0 | 7 |
| `SailingSim.Lake` | 18 | 18 | 0 | 1 |
| `SailingSim.Physics.PolarGate` | 1 | 1 | 0 | 0 |

**All passed; none failed.** The warnings are the standing ones: missing `S_*` sound samples, and `.detail` and TexasCoast loose files that aren't in a fresh worktree.

## Water eye check

ulkhead-05m, ridge-05m and private-dock-05m, uncooked Ultra 1080p. Stills and crops: Inputs/bench/render-bugs-nov17/main-91c8c80d/. The last game log has no "Failed to compile Material" or "missing usage flag" line.

| Scene | pr805 1f39fdab after | main 91c8c80d | Verdict |
|---|---|---|---|
| bulkhead-05m | 4.46 | 4.38 | **matches:** plain water at the wall, no chevrons |
| bridge-05m | 1.31 | 10.75 | **matches on the water:** no chevrons. The higher number is #797's textured bank (rocky soil) inside the crop box above the waterline (compare-bridge-05m.png) |
| private-dock-05m | 4.53 | 4.63 | **matches:** no checker band along the dock's shadow edge |

Bean's Saved was held aside and restored (B57AA3AF).
