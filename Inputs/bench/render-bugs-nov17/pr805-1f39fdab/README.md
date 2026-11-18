# #805 at 1f39fdab (foam laid along the sea's mean wind) on the PC

**Build:**

- `1f39fdab` (confirmed with `gh pr view 805`) merged locally with main `518e3f9f` as `589ee35f` (not pushed), fresh worktree, `git lfs pull` after the merge.
- MSVC build: Succeeded, 0 errors.
- **Shots:** seven scenes uncooked at Ultra 1920x1080, 100% screen percentage, before (the committed materials, the same as main's) and after the rebuild (`args.csv`):
  - the six #30 scenes, with the same args as the earlier heads;
  - `helm-eye-16kn`: lake launch 1, `-SailingWind=16 -SailingHour=14 -SailingCapture=HelmEye`, open water at mid distance.
- Bean's Saved was held aside and restored (B57AA3AF). The worktree was removed; nothing was committed.

## Compile: clean

- `run-python.ps1 make_materials.py -Only build_water,build_water_v4` rebuilt both `/Game/Materials/M_Water` and `/Game/Materials/M_WaterV4` ("Materials built: 2 builders").
- No "Failed to compile Material" and no "missing usage flag" line in the editor log or in the last game log (`make_materials-excerpt.txt`).

## Per scene

Pattern energy is the mean absolute second difference of the grey 1:1 crop, at the Nov 17 boxes; dock x 480-1440 y 560-1080, beach x 480-1440 y 700-1080. `crops/compare-<scene>.png` stack the Nov 17 package (where there is one), before and after.

| Scene | Nov 17 pkg | c25fc326 after | f3b19f33 after | **1f39fdab before -> after** | Verdict |
|---|---|---|---|---|---|
| bulkhead-05m | 9.66 | 6.37 | 6.37 | 8.55 -> **4.46** | **gone:** the wall strip is plain water |
| bulkhead-near-20 | 9.61 | 7.47 | 7.59 | 9.53 -> **6.27** | **gone:** no chevrons or blocks; the near water shows soft ripples (`compare-bulkhead-near-20.png`) |
| bulkhead-near-35 | 7.37 | 6.01 | 5.96 | 7.21 -> **5.13** | **gone** |
| bridge-05m | 1.82 | 2.12 | 1.99 | 2.23 -> **1.31** | **gone:** the bank's waterline chevrons are gone (`compare-bridge-05m.png`) |
| private-dock-05m | — | 4.85 | 4.98 | 5.44 -> **4.53** | **gone:** the checker band along the dock's shadow edge is gone |
| club-beach-05m | — | 1.88 | 1.43 | 2.14 -> **1.47** | **lapping kept:** soft foam along the waterline, no lace. A few faint straight-edged facets show in it at the left end (x 480-900 of the full still), worth a look. |

The "before" energies vary a little from head to head (8.55-9.66 at bulkhead-05m), because each run catches the waves at a different moment.

## Whitecaps: unchanged

`helm-eye-16kn` before and after (`crops/compare-helm-eye-16kn.png`, half size; `crops/helm-eye-16kn-*.png` 1:1):

- **Same:** the sea's texture, the scattered caps and the far water look the same.
- **Fine detail:** the change is to the foam's orientation only, and nothing in the caps' shape or spread changes visibly.
- **Not a heavy-cap check:** at 16 kn on the lake at the helm the caps are sparse in both, so this checks the open-water look rather than a cap-heavy sea.
