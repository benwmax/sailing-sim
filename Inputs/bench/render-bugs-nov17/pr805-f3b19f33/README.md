# #805 at f3b19f33 (lapping term on WB_NOISE bubbles) on the PC

**Build:**

- `f3b19f33` merged locally with main `df3bca26` as `7cf1a53c` (not pushed), fresh worktree, `git lfs pull` after the merge.
- MSVC build: Succeeded.
- **Shots:** the same six scenes and args as `../pr805-c25fc326/`, uncooked at Ultra 1920x1080, before (committed M_WaterV4) and after the rebuild (`run-python.ps1 make_materials.py -Only build_water_v4`).
- Bean's Saved was held aside and restored. The worktree was removed; nothing was committed.

## Compile: clean

"Materials built: 1 builders". There is no "Failed to compile Material" in the editor log or the last game log.

## Per scene

Pattern energy is the mean absolute second difference of the grey 1:1 crop, at the same boxes as before. `crops/compare-<scene>.png` stack the Nov 17 package (where there is one), before and after.

| Scene | Nov 17 pkg | before | after | Verdict |
|---|---|---|---|---|
| bulkhead-05m | 9.66 | 9.66 | 6.37 | **reduced:** a band at the wall, as at c25fc326 |
| bulkhead-near-20 | 9.61 | 9.54 | 7.59 | **reduced:** the blocks are confined to about the first metre off the wall, as at c25fc326 |
| bulkhead-near-35 | 7.37 | 6.88 | 5.96 | **reduced:** a thin strip along the wall |
| bridge-05m | 1.82 | 1.98 | 1.99 | **bridge-bank chevrons NOT gone:** unchanged |
| private-dock-05m | — | 5.51 | 4.98 | **dock checker band NOT gone:** the band on the water along the dock's shadow edge is still there. Little lapping shows at the posts now. |
| club-beach-05m | — | 2.17 | 1.43 | **lapping still shows**, but changed: the white lace is gone, replaced by a soft pale haze along the waterline; looks smoother |

## Reading

- **What changed:** the bubble pattern removes the lace at the beach.
- **What didn't:** it doesn't change the chevrons at the bulkhead wall or the bridge bank, or the checker band under the dock. They look the same as at c25fc326.
- **So:** those blocks don't come from the lace texture. Since the bisect cleared them with the lapping term or the shore depth off, they likely come from how the shore-depth map is sampled.
