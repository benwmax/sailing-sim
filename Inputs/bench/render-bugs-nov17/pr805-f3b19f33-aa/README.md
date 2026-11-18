# #805 at f3b19f33: anti-aliasing off and slow-motion check (PC)

**Build:**

- `f3b19f33` merged locally with main `df3bca26` as `9dff9aa5` (not pushed), fresh worktree, `git lfs pull` after the merge.
- MSVC build: Succeeded.
- M_WaterV4 rebuilt with `-Only build_water_v4`. Clean: no "Failed to compile Material".
- Shot uncooked at Ultra 1920x1080 with the same args as `../pr805-f3b19f33/` plus one extra arg (`args.csv`).
- Bean's Saved was held aside and restored. The worktree was removed; nothing was committed.

## (a) `-SailingAA=0` (temporal AA off): the bulkhead chevrons and the dock checker band are both still there

- `bulkhead-near-20-aa0.png`: **chevrons still there**, sharper, in rows along the wall strip.
- `private-dock-05m-aa0.png`: **checker band still there** on the water along the dock's shadow edge, sharper.
- **Crops:** `crops/compare-<scene>.png` set the f3b19f33 "after" still (TSR on) above the AA-off still, at the usual boxes.

Pattern energy, TSR on against AA off:

| Scene | TSR on | AA off |
|---|---|---|
| bulkhead-near-20 | 7.59 | 11.50 |
| private-dock-05m | 4.98 | 8.25 |

TSR softens the pattern but doesn't make it: it's in the material's shading.

## (b) `-SailingSlowMo=0.001`: no stills

- **What went wrong:** the slow-motion factor also slows the bench's own clock, so the 8-second bench would take about 8,000 s of real time.
- **What happened:** both runs reached `run-game.ps1`'s limit (bench seconds + 300 s) and were stopped by PID with no screenshot (`status.txt`: "png False").
- **Getting it later:** a milder factor (e.g. 0.05, about 160 s) or a shorter bench would produce one. Not run.
