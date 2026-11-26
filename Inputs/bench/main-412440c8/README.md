# Main 412440c8: Development package and 16-view Ultra bench, the pre-freeze baseline (PC, Nov 26 2026)

**Build and package:**
- New worktree `D:\dev\ss-fix-wt\main-412440c8`. MSVC build succeeded, 0 project warnings.
- Development package in the new `Packaged\Windows-412440c8` (4 min). **It's kept for the Nov 27 Friday build.**
- The package was warm before the bench: 3 Galveston runs and the bench's own warm-up.

**Bench:** `bench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100'`, 412440c8's own script and views, at
1920x1080. These are the same 16 views as 0b212e8a (main 91c8c80d, `../main-91c8c80d/`). Files are in `bench/`.
Bean's Saved was held aside and restored (7B5CA7BE).

| View | fps 412440c8 | fps 91c8c80d | change | GPU ms (new / old) | game ms (new / old) | render ms (new / old) |
|---|---|---|---|---|---|---|
| beam8 | 64.5 | 71 | -6.5 **(down >2)** | 6.7 / 6.63 | 11.29 / 9.98 | 15.50 / 14.08 |
| beat15 | 63.5 | 66 | -2.5 **(down >2)** | 7.1 / 6.96 | 12.25 / 11.53 | 15.71 / 15.10 |
| storm | 61.9 | 66.8 | -4.9 **(down >2)** | 7.59 / 7.38 | 14.25 / 12.93 | 16.06 / 14.92 |
| marina | 69.4 | 68.2 | +1.2 | 7.29 / 7.14 | 9.80 / 9.74 | 14.39 / 14.65 |
| coast-day | 65.4 | 65.3 | +0.1 | 7.52 / 7.48 | 12.02 / 11.49 | 15.28 / 15.29 |
| coast-night | 70 | 72.2 | -2.2 **(down >2)** | 7.46 / 7.32 | 11.02 / 10.59 | 14.26 / 13.83 |
| gulf-sea | 72.9 | 67.9 | +5.0 | 6.26 / 6.15 | 10.67 / 11.68 | 13.69 / 14.70 |
| helm-eye | 72.4 | 71.2 | +1.2 | 6.98 / 7.09 | 9.45 / 9.58 | 13.81 / 13.79 |
| slip | 75.5 | 77.7 | -2.2 **(down >2)** | 7.57 / 7.64 | 9.68 / 9.25 | 13.23 / 12.84 |
| bridge | 71.1 | 73 | -1.9 | 6.73 / 6.58 | 9.88 / 9.47 | 14.05 / 13.68 |
| crew | 60.2 | 59.9 | +0.3 | 8.9 / 8.79 | 11.18 / 10.93 | 16.59 / 16.68 |
| marina-night | 86.9 | 86.6 | +0.3 | 7.05 / 7.08 | 8.10 / 7.84 | 11.48 / 11.52 |
| far-coast | 67.6 | 67.4 | +0.2 | 6.78 / 6.63 | 11.45 / 11.44 | 14.78 / 14.83 |
| far-coast-night | 76.9 | 73.7 | +3.2 | 5.41 / 5.42 | 10.83 / 10.93 | 12.97 / 13.54 |
| marseille-port | 71.8 | 71.4 | +0.4 | 7.09 / 7.42 | 10.42 / 10.60 | 13.90 / 13.99 |
| stream-run | 67.2 | 63.9 | +3.3 | 8.28 / 8.06 | 11.52 / 12.72 | 14.85 / 15.61 |
mean 69.8 vs 70.1

**Rerun of the five views down more than 2 fps** (`rerun/`, the same package, straight after):

| View | fps | GPU ms |
|---|---|---|
| beam8 | 72.5 | 6.98 |
| beat15 | 67.6 | 7.61 |
| storm | 64.9 | 7.66 |
| coast-night | 70.8 | 7.4 |
| slip | 73.6 | 7.77 |

**Views down more than 2 fps:**
- **First pass:** beam8 -6.5, storm -4.9, beat15 -2.5, coast-night -2.2, slip -2.2.
- **Rerun, against 91c8c80d:**
  - beam8 72.5 (+1.5);
  - beat15 67.6 (+1.6);
  - storm 64.9 (-1.9);
  - coast-night 70.8 (-1.4);
  - **slip 73.6 (-4.1)**.
- **Better of the two runs:** only **slip** is still down more than 2 fps (75.5 against 77.7, -2.2).
- **GPU time doesn't move:** the GPU column is within 0.2 ms on every view, so none of this is GPU work.
- **These drops are run-to-run noise:**
  - views move 2-5 fps between runs (gulf-sea +5.0, stream-run +3.3 here);
  - the first pass's lake drops came with game- and render-thread time up 1 ms that the rerun didn't repeat.
- **slip:** game 9.68 against 9.25 ms, render 13.23 against 12.84 in the first pass. Worth one more look if it repeats in
  Friday's gate.

**Mean over 16 views:** 69.8 fps against 70.1.
