# Main 91c8c80d: package, Ultra bench and shore eye check (PC, Nov 19)

**Build and package:**

- The kept worktree D:\dev\ss-fix-wt\main at 91c8c80d, from the pre-candidate check: MSVC clean, 6 filters green (../pr-checks-nov15/main-91c8c80d.md).
- Development package to the new Packaged\Windows-91c8c80d (kept, 4 min), warmed once.

**Bench:** ench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100' (91c8c80d's own script and views), 1920x1080, the same 16 views as the 8a768667 run (inputs e200466a). Files: ench/ (CSV and bench.json per view). Bean's Saved was held aside and restored (B57AA3AF).

| View | fps 91c8c80d | fps 8a768667 | change | GPU ms (new / old) | base ms (new / old) | water ms (new / old) |
|---|---|---|---|---|---|---|
| beam8 | 71 | 69.4 | 1.6 | 6.63 / 6.83 | 2.51 / 2.62 | 0.52 / 0.52 |
| beat15 | 66 | 65.3 | 0.7 | 6.96 / 7.18 | 2.75 / 2.77 | 0.54 / 0.56 |
| storm | 66.8 | 69.1 | -2.3 **(down >2)** | 7.38 / 7.57 | 2.75 / 2.91 | 0.57 / 0.58 |
| marina | 68.2 | 67 | 1.2 | 7.14 / 7.03 | 2.74 / 2.69 | 0.48 / 0.49 |
| coast-day | 65.3 | 69.4 | -4.1 **(down >2)** | 7.48 / 7.32 | 3.25 / 3 | 0.52 / 0.54 |
| coast-night | 72.2 | 67.1 | 5.1 | 7.32 / 7.3 | 3.12 / 3.12 | 0.46 / 0.47 |
| gulf-sea | 67.9 | 69.5 | -1.6 | 6.15 / 6.26 | 2.16 / 2.21 | 0.51 / 0.52 |
| helm-eye | 71.2 | 73.3 | -2.1 **(down >2)** | 7.09 / 7.2 | 2.79 / 3.14 | 0.38 / 0.43 |
| slip | 77.7 | 76.9 | 0.8 | 7.64 / 7.37 | 3.45 / 3.33 | 0.44 / 0.45 |
| bridge | 73 | 71.1 | 1.9 | 6.58 / 6.58 | 2.47 / 2.46 | 0.48 / 0.47 |
| crew | 59.9 | 59 | 0.9 | 8.79 / 8.79 | 3.87 / 3.82 | 0.39 / 0.39 |
| marina-night | 86.6 | 90.1 | -3.5 **(down >2)** | 7.08 / 6.97 | 3.16 / 3.09 | 0.52 / 0.52 |
| far-coast | 67.4 | 66.5 | 0.9 | 6.63 / 6.86 | 2.53 / 2.65 | 0.49 / 0.49 |
| far-coast-night | 73.7 | 75 | -1.3 | 5.42 / 5.51 | 1.64 / 1.65 | 0.45 / 0.46 |
| marseille-port | 71.4 | 70.7 | 0.7 | 7.42 / 6.94 | 2.59 / 2.57 | 0.53 / 0.6 |
| stream-run | 63.9 | 66.4 | -2.5 **(down >2)** | 8.06 / 7.9 | 2.97 / 2.89 | 0.49 / 0.48 |

**Means:** **70.1 fps** against **70.4**.

**Views down more than 2 fps:** storm -2.3, coast-day -4.1, helm-eye -2.1, marina-night -3.5, stream-run -2.5. Their thread times, 91c8c80d / 8a768667 (ms):

| View | game | render | GPU |
|---|---|---|---|
| storm | 12.93 / 13.11 | 14.92 / 14.40 | 9.43 / 9.51 |
| coast-day | 11.49 / 10.90 | 15.29 / 14.40 | 9.50 / 9.28 |
| helm-eye | 9.58 / 9.65 | 13.79 / 13.41 | 8.79 / 8.91 |
| marina-night | 7.84 / 8.02 | 11.52 / 11.08 | 8.23 / 8.24 |
| stream-run | 12.72 / 11.51 | 15.61 / 15.04 | 10.08 / 9.95 |

**Reading the drops:**

- **The GPU slices hardly move.** Base +0.1 to +0.3 ms where the textured ground is in view; Lumen and water a few tenths up on most views.
- **The render thread is +0.4 to +0.9 ms** on the five flagged views.
- **coast-day and stream-run** also have game-thread rises (+0.6 and +1.2 ms).
- **Noise:** the 8a768667 run swung -4.5 to +6.6 fps against its own predecessor, so these are within that spread. coast-day (-4.1) and stream-run (-2.5) are the ones to watch in the next bench.

## Shore eye check (uncooked Ultra 1080p)

**Stills:**

- In stills/: env-bridge-15m, env-wooded-05m, env-wooded-15m, env-club-beach-05m, env-clay-bank-05m (render-bugs or stations args).
- From the pre-candidate check: bridge-05m, bulkhead-05m and private-dock-05m.
- stills/contact.png shows all of them.

**#29 glow: gone on main.**

stills/crops/glow-<scene>.png stack #804's PR "after" still above main, at the #29 boxes. Mean luma inside the glow rectangles:

| Scene | #804 PR after | main 91c8c80d |
|---|---|---|
| bridge-05m | 104.7 | 71.7 |
| bridge-15m | 94.3 | 64.2 |
| wooded-05m | 92.2 | 68.8 |
| wooded-15m | 80.1 | 61.6 |

There's no cream blob at any of the four. Main reads darker still, because the #797 ground textures are now under it.

**Track A ground: textured everywhere.**

- **Banks:** sand, pebbles, soil and grass on the banks, gravel and rocky soil on the bridge bank, with darker wet bands at the waterline.
- **To look at:** on nv-club-beach-05m the lawn above the sand shows a straight, slightly lighter colour step about halfway across (full still about x 1400). It looks like a texture tile or blend edge.

## Lawn step on the club beach: triage (Nov 19, `lawn-step/`)

**Stills:** three more uncooked Ultra 1080p stills of `env-club-beach-05m` in the same worktree, same camera as the job 3 still (`lawn-step/args.csv`).

**Compare sheet:** `lawn-step/crops/compare-lawn-step.png` stacks the job 3 still and the three new ones, 1:1 at x 1050-1750, y 330-620. The step sits at about x 1400.

| Still | Step |
|---|---|
| job 3 (M_Ground, Ultra detail) | **present** |
| `-SailingClassicGround` (the old M_Terrain path) | **gone:** uniform grass |
| `-SailingGroundDetail=0` (High's near path) | **present**, same place |
| heading +1 deg (`-SailingCamWorld` 69.8 -> 70.8) | **present**. It moves left with the scene by about 23 px, the same as the houses behind it. |

**Verdict:**

- **Fixed in the world, not on screen:** it moves with the ground when the camera turns, so it isn't a screen-aligned Lumen or shadow step.
- **From M_Ground's path:** it goes away with the classic ground, and the near-detail switch doesn't touch it. So it comes from M_Ground's own inputs, most likely a chunk or tile boundary in its masks or textures at that spot.
