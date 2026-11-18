# #805 M_WaterV4 bisect (feedback #30 near-water chevrons) on the PC: 7c8d3f57

**Build:**

- `7c8d3f57` (the #805 head with the V4_DBG_MODE switch) merged locally with main `df3bca26` as `ae3bdee8` (not pushed), fresh worktree, `git lfs pull` after the merge.
- MSVC build: Succeeded.
- The worktree was removed afterwards; nothing was committed.

**Runs:**

- For each mode, `V4_DBG_MODE=<n>` was set in the environment and M_WaterV4 rebuilt (`run-python.ps1 make_materials.py -Only build_water_v4`, MATERIALS_ONLY=build_water_v4). Then `env-bulkhead-near-35` and `env-bulkhead-near-20` were shot uncooked at Ultra 1920x1080 with the render-bugs-nov17 args (`args.csv`).
- All 12 rebuilds compiled clean: no "Failed to compile Material" line in any `make_materials` log.
- **Cleanup:** V4_DBG_MODE was unset and M_WaterV4 rebuilt at the default before the worktree was removed.
- Bean's Saved was held aside and restored.

**Contents:**

- `contact-bulkhead-near-20.png`, `contact-bulkhead-near-35.png`: all 12 runs side by side, half size.
- `crops/`: 1:1 at the render-bugs-nov17 boxes (near-35 x 0-960 y 140-700, near-20 x 0-960 y 600-900).
- `stills/`.

## Verdict per mode

| Mode | Chevrons | Blocks | Energy near-35 / near-20 |
|---|---|---|---|
| 0 baseline | present | present | 6.88 / 9.07 |
| 0 + `-SailingDebugFoam=1` | the debug view is black over the near water: no whitecap foam there | — | 6.24 / 7.26 |
| 1 no foam | **gone** | **gone** | 4.99 / 5.92 |
| 2 flat normal | same | same | 6.86 / 9.22 |
| 3 no wake-grid slopes | same | same | 6.83 / 8.93 |
| 4 no capillaries | same | same | 6.94 / 9.11 |
| 5 no ripples | same | same | 6.91 / 9.22 |
| 6 no chop | same | same | 6.67 / 8.98 |
| 7 roughness >= 0.35 | same | same | 7.09 / 9.47 |
| 8 no foam bump | same | same | 7.16 / 8.86 |
| 9 no shore depth | **gone** | **gone** | 5.46 / 6.07 |
| 10 no lapping foam | **gone** | **gone** | 5.21 / 6.27 |

"Energy" is the mean absolute second difference in x and y of the grey crop. The grass in the crops keeps it from going near zero, so read the contact sheets for the verdict.

## Reading

- **The source:** the pattern is the near-shore **lapping foam**.
  - It vanishes when all foam is off (1), when only the lapping foam is off (10), and when the shore depth that drives it is off (9).
  - It is untouched by the normal, the wave and ripple terms, the wake slopes, roughness and the foam bump (2-8).
- **Not whitecaps:** `-SailingDebugFoam=1`, which draws the whitecaps alone, shows nothing over this water.
- **Where to look next:** the lapping foam's pattern or its sampling of the shore-depth map. Blocky texels with chevron banding look like a coarse depth map magnified at the bulkhead.
