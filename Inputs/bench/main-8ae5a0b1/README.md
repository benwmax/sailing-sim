# Main 8ae5a0b1: 16-view Ultra bench against 412440c8 (PC, Nov 26 2026)

**Package and setup:**
- `Packaged\Windows-8ae5a0b1` (Development, main with #835, #838 and #841). It was warm: the R08b take and a 2 h soak.
- `bench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100'` at 1920x1080. These are the same 16 views as
  `../main-412440c8/`. Files are in `bench/`.

Bean's Saved was held aside and restored (7B5CA7BE).

| View | fps 8ae5a0b1 | fps 412440c8 | change | GPU ms (new / old) | game ms (new / old) | render ms (new / old) |
|---|---|---|---|---|---|---|
| beam8 | 70.1 | 64.5 | +5.6 | 6.98 / 6.7 | 10.78 / 11.29 | 14.25 / 15.50 |
| beat15 | 67.7 | 63.5 | +4.2 | 7.46 / 7.1 | 11.41 / 12.25 | 14.74 / 15.71 |
| storm | 64.5 | 61.9 | +2.6 | 7.67 / 7.59 | 13.45 / 14.25 | 15.41 / 16.06 |
| marina | 68.1 | 69.4 | -1.3 | 7.12 / 7.29 | 10.05 / 9.80 | 14.67 / 14.39 |
| coast-day | 70.6 | 65.4 | +5.2 | 7.56 / 7.52 | 10.72 / 12.02 | 14.15 / 15.28 |
| coast-night | 65 | 70 | -5.0 **(down >2)** | 7.56 / 7.46 | 12.21 / 11.02 | 15.36 / 14.26 |
| gulf-sea | 71 | 72.9 | -1.9 | 6.18 / 6.26 | 10.97 / 10.67 | 14.07 / 13.69 |
| helm-eye | 71.7 | 72.4 | -0.7 | 6.78 / 6.98 | 9.59 / 9.45 | 13.95 / 13.81 |
| slip | 77.3 | 75.5 | +1.8 | 7.67 / 7.57 | 9.48 / 9.68 | 12.92 / 13.23 |
| bridge | 73 | 71.1 | +1.9 | 6.77 / 6.73 | 9.73 / 9.88 | 13.69 / 14.05 |
| crew | 60.1 | 60.2 | -0.1 | 8.64 / 8.9 | 11.13 / 11.18 | 16.64 / 16.59 |
| marina-night | 86.2 | 86.9 | -0.7 | 7.13 / 7.05 | 8.10 / 8.10 | 11.58 / 11.48 |
| far-coast | 67.4 | 67.6 | -0.2 | 6.85 / 6.78 | 11.43 / 11.45 | 14.81 / 14.78 |
| far-coast-night | 76 | 76.9 | -0.9 | 5.6 / 5.41 | 10.72 / 10.83 | 13.12 / 12.97 |
| marseille-port | 67.4 | 71.8 | -4.4 **(down >2)** | 7.63 / 7.09 | 11.34 / 10.42 | 14.82 / 13.90 |
| stream-run | 63.6 | 67.2 | -3.6 **(down >2)** | 8.22 / 8.28 | 12.67 / 11.52 | 15.70 / 14.85 |

Mean 70.0 vs 69.8 fps.

**Rerun** (`rerun/`): slip, and the three views down more than 2 fps. It ran about 50 minutes after the first pass,
with #834's runs in between.

| View | First pass | Rerun | 412440c8 | Better of the two, change |
|---|---|---|---|---|
| coast-night | 65.0 | 75.8 | 70.0 | +5.8 |
| slip | 77.3 | 76.3 | 75.5 | +1.8 |
| marseille-port | 67.4 | 73.5 | 71.8 | +1.7 |
| stream-run | 63.6 | 67.9 | 67.2 | +0.7 |

**Result: no view is down more than 2 fps.**
- On the better of the two runs, every flagged view is at or above 412440c8.
- slip is back to 76-77, up from 412440c8's 75.5.
- **The spread is noise:** coast-night moved 10.8 fps between the two runs.
