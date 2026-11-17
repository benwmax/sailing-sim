# Windows bench of main ecd4ed1c (PC)

- **Build:** main **ecd4ed1c** as a Development package to the new `Packaged/Windows-ecd4ed1c` (5 min). It was built in a fresh worktree at ecd4ed1c with the crew linked, not the main checkout, which stays at 40226d1c. MSVC clean.
- **Runs:** warmed once, then `bench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100'` (main's own script and views) on the 16 standard views at 1920x1080, 12 s each with `-SailingDemo`, once. The bench script was a temporary copy that stops its own game by PID.
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Files:** each view's `bench.json` and the CSV.

**Against nightly-win-2026-11-17** (main 687f777c, two passes, same views and settings except that the nightly had no explicit `-SailingScreenPct=100`; both report `render_pct` 100):

| View | fps ecd4ed1c | fps 687f777c p1 / p2 | change vs nightly mean | p99 ms | GPU ms | GPU ms 687f777c p1 | game ms | render ms | RHI ms | base | lumen | water | clouds/fog | post | foreground | render_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| beam8 | 67.6 | 53.9 / 59.5 | 10.9 | 18.21 | 6.99 | 6.88 | 11.06 | 14.77 | 7.67 | 2.76 | 0.57 | 0.51 | 1.2 | 0.77 | 0 | 100 |
| beat15 | 61.5 | 51.4 / 56.5 | 7.5 | 21.82 | 7.33 | 7.44 | 12.41 | 16.22 | 8.5 | 2.9 | 0.6 | 0.54 | 1.03 | 0.81 | 0 | 100 |
| storm | 63.2 | 56 / 58.1 | 6.2 | 21.77 | 8.28 | 7.51 | 13.92 | 15.77 | 7.96 | 3.26 | 0.71 | 0.58 | 1.8 | 0.95 | 0 | 100 |
| marina | 65.2 | 54.2 / 55.4 | 10.4 | 19.5 | 7.22 | 7.49 | 10.49 | 15.34 | 7.16 | 2.76 | 0.63 | 0.51 | 1.36 | 0.76 | 0 | 100 |
| coast-day | 63.6 | 55.6 / 54.5 | 8.6 | 20 | 7.73 | 7.55 | 12.05 | 15.71 | 7.29 | 3.18 | 0.73 | 0.53 | 1.16 | 0.78 | 0 | 100 |
| coast-night | 63.5 | 58.5 / 59 | 4.8 | 22.43 | 7.21 | 7.32 | 12.47 | 15.73 | 6.91 | 3 | 0.88 | 0.46 | 1.02 | 0.76 | 0 | 100 |
| gulf-sea | 64.4 | 60.3 / 60.7 | 3.9 | 21.1 | 6.52 | 6.28 | 13.16 | 15.49 | 7.32 | 2.34 | 0.59 | 0.53 | 1.28 | 0.77 | 0 | 100 |
| helm-eye | 61.2 | 59.2 / 57.9 | 2.7 | 22.85 | 7.08 | 7.54 | 11.64 | 16.33 | 8.22 | 3.02 | 0.8 | 0.37 | 0.95 | 0.72 | 0 | 100 |
| slip | 69.5 | 65.1 / 65 | 4.5 | 19.1 | 7.58 | 7.65 | 10.59 | 14.35 | 8.02 | 3.47 | 0.75 | 0.43 | 1.03 | 0.77 | 0 | 100 |
| bridge | 65.7 | 59.1 / 59.1 | 6.6 | 19.18 | 6.64 | 6.8 | 10.72 | 15.2 | 7.57 | 2.54 | 0.64 | 0.46 | 1.06 | 0.82 | 0 | 100 |
| crew | 55.3 | 50.3 / 50.6 | 4.8 | 22.23 | 9.26 | 9.05 | 12.07 | 18.06 | 8.55 | 4.14 | 0.98 | 0.39 | 0.93 | 0.73 | 0 | 100 |
| marina-night | 79.8 | 68.7 / 69.7 | 10.6 | 16.02 | 7.22 | 7.07 | 8.67 | 12.5 | 6.78 | 3.28 | 0.87 | 0.52 | 0.77 | 0.95 | 0 | 100 |
| far-coast | 62.5 | 50.9 / 53.9 | 10.1 | 21.15 | 6.82 | 6.82 | 12.58 | 15.99 | 7.6 | 2.55 | 0.6 | 0.48 | 1.09 | 0.77 | 0 | 100 |
| far-coast-night | 69.1 | 55.5 / 58.7 | 12 | 19.95 | 5.42 | 5.65 | 11.9 | 14.44 | 6.52 | 1.62 | 0.59 | 0.44 | 0.87 | 0.76 | 0 | 100 |
| marseille-port | 70.5 | 56.8 / 59.4 | 12.4 | 20.33 | 7.24 | 7.07 | 10.59 | 14.16 | 7.16 | 2.55 | 0.67 | 0.51 | 1.23 | 0.89 | 0 | 100 |
| stream-run | 68.2 | 56.1 / 55.7 | 12.3 | 20.93 | 7.92 | 8.47 | 11.23 | 14.64 | 6.93 | 2.85 | 0.72 | 0.51 | 1.87 | 0.79 | 0 | 100 |

## What changed

- **Every view is faster.** The gains run from about +5 fps (crew 55.3 against 50.5) to about +11 (beam8, marina-night, marseille-port, far-coast-night, stream-run, beat15).
- **The GPU slices barely move:** GPU total is 5.4 to 9.3 ms, as before. The gain is on the CPU.
  - **The likely source:** #778's AI rig rebuild rate, merged at 54f6e04b, since most views have AI traffic. On #778 alone the crew view went from 49.1 to 59.1 fps (`pr778-7d62a930`).
  - **The views without traffic** (marina-night, slip and so on) also gained 5 to 11 fps, so the rest of today's merges may help as well. Telling those apart needs per-merge runs.
- **Crew is still the slowest view at 55.3 fps:** game and render threads plus the GPU's heaviest base slice (4.1 ms). Its MetaHuman crew and the player's rig lines (`profile-main-nov17`) are what's left there.
- **Foreground:** every view still reports `foreground: 0`. The window wasn't the foreground window. I don't move windows or send input, and the desktop wasn't in use. Read 1 to 2 fps differences with care; the gains above are much larger than that.
