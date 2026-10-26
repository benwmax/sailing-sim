# Benches at full resolution, in front (Oct 26 2026)

## What was wrong after the macOS 27.0.1 update

1. **The window was not in front.** Before the update every bench reported `foreground` 1.000. After it, single-view runs
   reported 0.0. The game's request to be activated is made at BeginPlay, before its window is up, and macOS 27 drops
   it; the list runs, which ask again once the app is running, stayed in front. A window that isn't frontmost may be
   throttled, which matches the day's one-off slow runs (stream-run in the sweep, far-coast's p99, bridge on Low).
2. **High was measured at reduced resolution.** High's resolution governor (`UpdateResolutionGovernor`) steps the render
   scale down while the smoothed frame is over 21.6 ms and back up under 18.5 ms. Before the update High benches sat at
   100%; after it they sat at 82-97%. So the gates showed about 2 fps of slowdown where at full resolution it was more.

## What changed

- **The window.** `ASailingGameMode` raises its own window again every half second through the warm-up until the game is
  the frontmost app.
- **Resolution.** `bench-visual.sh` takes `PIN_HIGH=1` (exported by `gate.sh`, so every gate and the sweep, including the
  reruns and the main baseline): High runs get `-SailingScreenPct=100`, which also turns the governor off. Medium (67%)
  and Low keep their tiers' own scale.
- **Columns and reruns.** The bench CSVs carry `render_pct` and `foreground`. A run that wasn't in front for its whole
  measured window is run once more (singly, and out of a list).
- **Gate state.** The gate's bench key includes the pin, and the main-check history is a new file,
  `Artifacts/gate/main-bench-fullres.csv`, so older unpinned results aren't reused.

## The new baseline (main 7c1c7ce4 + this, `--scope all --force`, Oct 26 2026)

Tests 239/239. On High every view rendered at 100%. Every view was in front except coast-night (0.04 even after its
rerun). "Before" is the same day's sweep at the governor's 82-97%.

One view is under its floor: **storm on High, 42.1 fps** (GPU 23.4 ms: base 8.3, clouds and fog 7.4, water 3.7). The floors
are unchanged; that is for Bean to decide. The other High views are 46.6 to 74.4 fps; crew (46.6), slip (47.6),
coast-day (47.1) and stream-run (48.2) are within 4 fps of the floor.
| View | fps at 100% | fps before (governed) | p99 ms | GPU ms | base | lumen | water | clouds/fog | post | other | foreground |
|---|---|---|---|---|---|---|---|---|---|---|---|
| beam8 | 53.4 | 56.5 | 23.08 | 17.23 | 7.53 | 1.9 | 3.63 | 1.89 | 0.9 | 1.38 | 1.0 |
| beat15 | 50.9 | 54.9 | 25.43 | 17.8 | 7.67 | 1.94 | 3.94 | 1.68 | 1.06 | 1.51 | 1.0 |
| storm | **42.1** | 47.4 | 27.75 | 23.35 | 8.29 | 1.91 | 3.74 | 7.36 | 1.07 | 0.99 | 1.0 |
| marina | 52.2 | 55.8 | 20.74 | 18.2 | 7.5 | 2.39 | 3.48 | 2.68 | 0.98 | 1.16 | 1.0 |
| coast-day | 47.1 | 53.0 | 23.06 | 19.79 | 9.9 | 2.61 | 3.04 | 2.32 | 0.9 | 1.02 | 1.0 |
| coast-night | 56.3 | 61.3 | 18.79 | 16.64 | 6.58 | 2.57 | 3.33 | 2.0 | 1.01 | 1.15 | 0.041 |
| gulf-sea | 55.5 | 59.9 | 19.51 | 16.76 | 6.88 | 2.43 | 3.87 | 1.39 | 1.0 | 1.18 | 1.0 |
| helm-eye | 49.9 | 53.4 | 24.54 | 19.19 | 10.22 | 3.33 | 2.62 | 1.03 | 0.76 | 1.23 | 1.0 |
| slip | 47.6 | 50.4 | 22.14 | 20.27 | 9.19 | 3.93 | 2.97 | 1.86 | 0.87 | 1.46 | 1.0 |
| bridge | 56.2 | 57.8 | 19.33 | 16.74 | 6.98 | 2.23 | 3.8 | 1.56 | 0.89 | 1.28 | 1.0 |
| crew | 46.6 | 52.2 | 26.58 | 19.75 | 10.64 | 3.06 | 2.61 | 1.17 | 0.85 | 1.42 | 1.0 |
| marina-night | 53.0 | 56.3 | 19.98 | 17.79 | 8.03 | 3.45 | 2.96 | 1.12 | 0.91 | 1.33 | 1.0 |
| far-coast | 56.4 | 57.6 | 19.38 | 16.44 | 6.81 | 2.05 | 3.42 | 2.1 | 0.83 | 1.24 | 1.0 |
| far-coast-night | 74.4 | 74.7 | 14.6 | 11.93 | 3.38 | 1.9 | 3.5 | 1.44 | 0.83 | 0.89 | 1.0 |
| marseille-port | 49.4 | 53.5 | 24.96 | 18.55 | 7.48 | 2.61 | 4.19 | 1.87 | 0.87 | 1.53 | 1.0 |
| stream-run | 48.2 | 52.0 | 22.62 | 19.5 | 9.63 | 2.66 | 3.45 | 1.86 | 0.88 | 1.03 | 1.0 |

| View | Medium fps | Low fps |
|---|---|---|
| beam8 | 85.1 | 93.1 |
| beat15 | 82.8 | 97.5 |
| storm | 65.4 | 106.6 |
| marina | 81.5 | 94.6 |
| coast-day | 76.9 | 93.6 |
| coast-night | 98.2 | 87.8 |
| gulf-sea | 94.0 | 115.5 |
| helm-eye | 88.3 | 94.8 |
| slip | 76.1 | 93.4 |
| bridge | 92.9 | 114.8 |
| crew | 74.1 | 103.8 |
| marina-night | 87.1 | 86.1 |
| far-coast | 85.2 | 109.9 |
| far-coast-night | 112.7 | 106.3 |
| marseille-port | 77.0 | 88.2 |
| stream-run | 77.0 | 105.0 |
