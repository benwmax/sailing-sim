# PR #805 (feedback #30 near-water moire) on the PC: tip 18f58e2b

**Build:**

- Tip `18f58e2b` lacks main `c7f1b59c`, so it was merged locally as `d704c178` (not pushed). Fresh worktree, `git lfs pull` after the merge, crew linked.
- MSVC build: Succeeded, 0 errors.
- The worktree was removed afterwards; nothing was committed.

## Compile verdict: clean

- **Rebuild:** `scripts\windows\run-python.ps1 make_materials.py -Only build_water_v4` (MATERIALS_ONLY=build_water_v4) rebuilt and saved `/Game/Materials/M_WaterV4`: "Materials built: 1 builders", "Python script executed successfully". The .uasset changed.
- **Editor log:** no "Failed to compile Material" line (`make_materials-excerpt.txt`).
- **Game log:** the game log of the last "after" run (env-bridge-05m) has no "Failed to compile Material" and no M_WaterV4 default-material line. M_WaterV4 compiles on PCD3D_SM6.

## Stills and crops

**The four #30 stills, uncooked, Ultra 1920x1080, with the render-bugs-nov17 args (`args.csv`):**

- **before:** the branch's committed M_WaterV4, the same as main's, since the PR changes only make_materials.py.
- **after:** M_WaterV4 rebuilt from the PR's make_materials.py.

**Crops (`crops/`):** 1:1 at the render-bugs-nov17 boxes (bulkhead-05m x 0-960 y 880-1080; near-20 x 0-960 y 600-900; near-35 x 0-960 y 140-700; bridge-05m x 880-1500 y 800-900). Each `compare-<scene>.png` stacks three crops: the Nov 17 `ecd4ed1c` package, before and after.

## Result: the moire is not fixed

- **bulkhead-near-20, near-35, bridge-05m:** the chevron pattern on the near water is unchanged after the rebuild.
- **bulkhead-05m:** the pattern changes direction, from horizontal chevrons to diagonal stripes, but is just as strong.

Pixel-scale pattern energy (mean absolute second difference in x and y, grey levels):

| Scene | Nov 17 package | before | after |
|---|---|---|---|
| bulkhead-05m | 9.66 | 9.06 | 9.32 |
| bulkhead-near-20 | 9.61 | 9.35 | 9.69 |
| bulkhead-near-35 | 7.37 | 7.16 | 7.20 |
| bridge-05m | 1.82 | 2.04 | 2.02 |

The uncooked "before" matches the Nov 17 packaged stills closely, so the uncooked runs reproduce the bug faithfully.
