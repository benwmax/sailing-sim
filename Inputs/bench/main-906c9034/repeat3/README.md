# The three "CPU-side drops" at 906c9034, repeated 3x against 91c8c80d (PC, Nov 20 2026)

**How:** far-coast, far-coast-night and marseille-port, three rounds each, interleaved (round, then view, then build),
on `Packaged\Windows-906c9034` and `Packaged\Windows-91c8c80d`.

- **Settings:** the 16-view bench's own (`bench-visual-win.ps1 -Tiers Ultra -Only <view> -Package <pkg> -Extra
  '-SailingScreenPct=100'`, 1920x1080, 12 s), with 906c9034's view list for both builds.
- **Bean's Saved:** held aside and restored; profile 7B5CA7BE.
- **Desktop:** Chrome (18-23 processes), Spotify (7) and Steam (8) were open and nothing was closed. Their CPU seconds rose
  only 3-4 s over the 10 minutes (`status.txt`), so they were light.

## Medians (3 runs each)

| View | Build | fps (runs) | Median fps | Game ms | Render ms | RHI ms | GPU ms | p99 ms |
|---|---|---|---|---|---|---|---|---|
| far-coast | 906c9034 | 66.3 / 68.3 / 67.6 | **67.6** | 11.38 | 14.76 | 7.07 | 8.40 | 22.96 |
| far-coast | 91c8c80d | 66.0 / 67.7 / 67.5 | **67.5** | 11.38 | 14.80 | 7.08 | 8.39 | 22.36 |
| far-coast-night | 906c9034 | 73.5 / 74.7 / 76.7 | **74.7** | 10.84 | 13.37 | 6.10 | 6.96 | 19.79 |
| far-coast-night | 91c8c80d | 74.9 / 75.6 / 75.0 | **75.0** | 10.78 | 13.32 | 6.06 | 6.96 | 20.16 |
| marseille-port | 906c9034 | 71.9 / 75.5 / 71.4 | **71.9** | 10.47 | 13.89 | 6.90 | 9.25 | 18.88 |
| marseille-port | 91c8c80d | 73.2 / 72.1 / 62.0 | **72.1** | 10.44 | 13.85 | 7.04 | 9.25 | 20.55 |

## Result: no regression

- The median gaps are +0.1, -0.3 and -0.2 fps, all well inside the run-to-run spread. The thread times match to
  within 0.1 ms and the GPU to within 0.01 ms.
- The 4-5 fps drops in the single 16-view run were noise: those single runs landed on a slow side of these views'
  spread. For example, 91c8c80d's own marseille-port here ranges from 62.0 to 73.2.
- The gap is under 2 fps, so no `-trace` capture was made.
- Files: every run's `bench.json` (`<build>-<view>-r<n>.json`), `runs.csv`, `medians.csv`, `status.txt`.
