# PR #813 (bilinear canopy sampling in BuildChunk) on the PC: head d887d809

**Build:**

- Head d887d809, confirmed with gh pr view 813. It contains main 91c8c80d, so it was used as is.
- Fresh worktree, git lfs pull, crew linked. MSVC build: **Succeeded, 0 errors**.
- The worktree was removed afterwards.

**Test:** SailingSim.Lake passed 18 of 18, 0 failed (1 with the standing warning). The new test ran: SailingSim.Lake.CanopySmooth Success.

## Views

The two lawn-step views from main 91c8c80d, uncooked Ultra 1080p, same args (rgs.csv). Bean's Saved was held aside and restored.

| View | Verdict |
|---|---|
| nv-club-beach-05m (job 3 camera) | **step unchanged:** still there, same place (about x 1400), same strength (crops/compare-beach.png, 1:1 at x 1050-1750, y 330-620) |
| backyards top-down ("-SailingCamWorld=128,40,60,0,-89", map N 240.3 E 1.4, 60 m) | **rectangles unchanged:** the lighter straight-edged patches are all still there, at most marginally softer at the edges (crops/compare-topdown.png, 1:1 at x 1000-1700, y 0-600) |

The rest of the ground looks the same (crops/full-*.png, half size). **The rectangles and the step are not removed by this change.** Whatever makes them isn't (only) the canopy sampling in BuildChunk.
