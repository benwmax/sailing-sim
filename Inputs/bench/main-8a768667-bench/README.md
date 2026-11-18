# Windows bench of main 8a768667 against 424b580b (PC, Nov 17-18 overnight)

- **Build:** origin/main's tip at run time was **8a768667** (9 first-parent merges after 424b580b). It was built in a fresh worktree (MSVC clean, removed afterwards) and packaged as Development to the new `Packaged/Windows-8a768667` (kept, 4 min), warmed once.
- **Runs:** `bench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100'` (8a768667's own script and views), 1920x1080, Windows-8a768667 and then `Windows-424b580b`, back to back.
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).
- **Foreground:** 0 on every view in both runs.

| View | fps 8a768667 | fps 424b580b | change | game ms (tip / 424b) | render ms (tip / 424b) | GPU ms (tip / 424b) |
| --- | --- | --- | --- | --- | --- | --- |
| beam8 | 69.4 | 73.9 | -4.5 | 10.1 / 10.08 | 14.39 / 13.52 | 6.83 / 6.7 |
| beat15 | 65.3 | 66.5 | -1.2 | 11.45 / 11.13 | 15.28 / 14.99 | 7.18 / 7.52 |
| storm | 69.1 | 73 | -3.9 | 13.11 / 12.32 | 14.4 / 13.61 | 7.57 / 7.48 |
| marina | 67 | 68 | -1 | 10.08 / 9.84 | 14.91 / 14.7 | 7.03 / 6.95 |
| coast-day | 69.4 | 62.8 | 6.6 | 10.9 / 12.06 | 14.4 / 15.91 | 7.32 / 7.44 |
| coast-night | 67.1 | 67.3 | -0.2 | 12.15 / 11.61 | 14.87 / 14.83 | 7.3 / 7 |
| gulf-sea | 69.5 | 70.5 | -1 | 11.92 / 11.67 | 14.37 / 14.15 | 6.26 / 6.26 |
| helm-eye | 73.3 | 67.5 | 5.8 | 9.65 / 10.65 | 13.41 / 14.6 | 7.2 / 6.65 |
| slip | 76.9 | 73.1 | 3.8 | 9.74 / 10.3 | 12.96 / 13.65 | 7.37 / 7.32 |
| bridge | 71.1 | 72.3 | -1.2 | 9.81 / 9.62 | 14.06 / 13.82 | 6.58 / 6.49 |
| crew | 59 | 59.6 | -0.6 | 11.19 / 11.08 | 16.94 / 16.76 | 8.79 / 9.16 |
| marina-night | 90.1 | 84.7 | 5.4 | 8.02 / 8.01 | 11.08 / 11.79 | 6.97 / 6.94 |
| far-coast | 66.5 | 67.3 | -0.8 | 11.63 / 11.62 | 15.02 / 14.85 | 6.86 / 6.72 |
| far-coast-night | 75 | 72.2 | 2.8 | 11.14 / 11.35 | 13.31 / 13.8 | 5.51 / 5.44 |
| marseille-port | 70.7 | 72.7 | -2 | 10.57 / 10.81 | 14.13 / 13.71 | 6.94 / 7.04 |
| stream-run | 66.4 | 66.8 | -0.4 | 11.51 / 11.54 | 15.04 / 14.95 | 7.9 / 7.88 |

- **Means:** **70.4 fps** against **69.9**.
- **No regression:** the per-view gaps go both ways (-4.5 to +6.6 fps), within the run-to-run spread seen in the #787 follow-up, and GPU time is unchanged.
- **Files:** each package's CSV and bench.json per view, under `main-8a768667/` and `main-424b580b/`.
