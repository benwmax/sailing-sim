# #805 at c25fc326 (lapping foam held to the waterline) on the PC

**Build:**

- `c25fc326` merged locally with main `df3bca26` as `fe769cb1` (not pushed), fresh worktree, `git lfs pull` after the merge.
- MSVC build: Succeeded.
- **Shots:** six scenes uncooked at Ultra 1920x1080, before (the committed M_WaterV4, the same as main's) and after the rebuild (`run-python.ps1 make_materials.py -Only build_water_v4`):
  - the four #30 scenes, with the render-bugs-nov17 args;
  - `env-private-dock-05m` (a dock at the waterline) and `env-club-beach-05m` (a beach), with main's `stations.csv` args plus `-SailingCapture=Drone -SailingScreenPct=100`.
- **Command lines:** `args.csv`. Bean's Saved was held aside and restored. The worktree was removed; nothing was committed.

## Compile: clean

`make_materials.py -Only build_water_v4` rebuilt M_WaterV4 ("Materials built: 1 builders"). There is no "Failed to compile Material" in the editor log or the last game log.

## Per scene

Pattern energy is the mean absolute second difference of the grey 1:1 crop. Crops are at the Nov 17 boxes for the four #30 scenes; dock x 480-1440 y 560-1080; beach x 480-1440 y 700-1080. `crops/compare-<scene>.png` stack the Nov 17 package (where there is one), before and after.

| Scene | Nov 17 pkg | before | after | Verdict |
|---|---|---|---|---|
| bulkhead-05m | 9.66 | 9.04 | 6.37 | **reduced:** the chevrons are now a band at the wall, not the whole near water |
| bulkhead-near-20 | 9.61 | 9.23 | 7.47 | **reduced:** the blocks are confined to about the first metre off the wall; the water beyond is clean |
| bulkhead-near-35 | 7.37 | 7.20 | 6.01 | **reduced:** the same, a thin chevron strip along the wall |
| bridge-05m | 1.82 | 2.11 | 2.12 | **unchanged:** the chevrons along the bank's waterline stay |
| private-dock-05m | — | 5.60 | 4.85 | **lapping foam still shows** at the posts; a checker band remains on the water under the dock |
| club-beach-05m | — | 2.04 | 1.88 | **lapping foam still shows** at the waterline, slightly less of it; looks right |

## Reading

- **What the fix does:** it confines the foam to the waterline as intended, so the open near water is clean.
- **What remains:** the chevron and block look survives where the foam still is, right at the bulkhead wall and the bridge bank. So the foam's own pattern, or its sampling of the shore-depth map, still aliases there.
- **Next:** a smoother lapping-foam pattern or a finer shore-depth sample at walls.
