# Main a3f81854, with #834's birds: 16-view Ultra bench, the new baseline (PC, Nov 26 2026)

**Package:** `Packaged\Windows-a3f81854` (Development, warm).

**Bench:** `bench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100'` at 1920x1080, the same as the 8ae5a0b1
baseline (`../../main-8ae5a0b1/`), so the two compare directly. Bean's Saved was held aside and restored (7B5CA7BE).

| View | fps a3f81854 | fps 8ae5a0b1 | change | GPU ms (new / old) | game ms (new / old) | render ms (new / old) |
|---|---|---|---|---|---|---|
| beam8 | 65.7 | 70.1 | -4.4 **(down >2)** | 7.12 / 6.98 | 11.39 / 10.78 | 15.22 / 14.25 |
| beat15 | 65.7 | 67.7 | -2.0 | 7.51 / 7.46 | 11.92 / 11.41 | 15.16 / 14.74 |
| storm | 68.1 | 64.5 | +3.6 | 7.61 / 7.67 | 12.94 / 13.45 | 14.63 / 15.41 |
| marina | 67.2 | 68.1 | -0.9 | 7.19 / 7.12 | 10.46 / 10.05 | 14.88 / 14.67 |
| coast-day | 65.8 | 70.6 | -4.8 **(down >2)** | 8.03 / 7.56 | 11.34 / 10.72 | 15.19 / 14.15 |
| coast-night | 73.4 | 65 | +8.4 | 7.69 / 7.56 | 10.33 / 12.21 | 13.60 / 15.36 |
| gulf-sea | 72 | 71 | +1.0 | 6.4 / 6.18 | 11.00 / 10.97 | 13.87 / 14.07 |
| helm-eye | 70.2 | 71.7 | -1.5 | 7.75 / 6.78 | 10.11 / 9.59 | 14.23 / 13.95 |
| slip | 76 | 77.3 | -1.3 | 7.89 / 7.67 | 10.10 / 9.48 | 13.13 / 12.92 |
| bridge | 74 | 73 | +1.0 | 6.77 / 6.77 | 10.49 / 9.73 | 13.50 / 13.69 |
| crew | 59.4 | 60.1 | -0.7 | 8.62 / 8.64 | 11.58 / 11.13 | 16.81 / 16.64 |
| marina-night | 85.8 | 86.2 | -0.4 | 7.08 / 7.13 | 8.22 / 8.10 | 11.64 / 11.58 |
| far-coast | 68.7 | 67.4 | +1.3 | 6.79 / 6.85 | 11.61 / 11.43 | 14.54 / 14.81 |
| far-coast-night | 73.7 | 76 | -2.3 **(down >2)** | 5.43 / 5.6 | 10.99 / 10.72 | 13.55 / 13.12 |
| marseille-port | 72.2 | 67.4 | +4.8 | 7.6 / 7.63 | 10.67 / 11.34 | 13.84 / 14.82 |
| stream-run | 66.3 | 63.6 | +2.7 | 8.79 / 8.22 | 11.75 / 12.67 | 15.06 / 15.70 |

Mean 70.3 vs 70.0 fps.

**Rerun of the views down more than 2 fps** (`rerun/`):

| View | First pass | Rerun | 8ae5a0b1 | Better of the two, change |
|---|---|---|---|---|
| beam8 | 65.7 | 68.8 | 70.1 | -1.3 |
| coast-day | 65.8 | 67.2 | 70.6 | **-3.4** |
| far-coast-night | 73.7 | 72.0 | 76.0 | **-2.3** |

**Reading:**
- **coast-day** (Galveston, 11:00) stays down 3.4 fps after the rerun.
  - GPU is +0.2-0.5 ms and the game thread +0.6 ms. That's the birds: Galveston's pelicans and gulls, with the nearest
    drawn as bodies.
  - The #834 A/B on this view (`../../pr834/50cc95bc/`, 4K) also measured the game thread up 0.45 ms.
- **far-coast-night** is down 2.3. It's a night view with no birds drawn, and it moves 2-4 fps between runs, so I read
  it as noise.
- **beam8** is back within 1.3 fps.
- **Overall:** the mean is level (70.3 vs 70.0). The birds cost about 1 fps on the busiest bird view, as the #834 runs
  showed.
