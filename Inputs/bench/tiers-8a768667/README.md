# Tier bench, High and Medium, main 8a768667 (PC)

**Setup:** Bean's PC (RTX 4090), Development package `Windows-8a768667`. Each tier ran 8a768667's own `bench-visual-win.ps1 -Tiers High,Medium -Label tiers-8a768667 -Package Windows-8a768667 -Extra '-SailingScreenPct=100'`, after one 12 s warm-up run on High.

**What it measured:** 16 views per tier at 1920x1080, 100% screen percentage, about 11 s each, 05:02 to 05:17 local, Nov 18. Every run had `render_pct` 100.

**Saved:** Bean's Saved was held aside and restored (profile hash checked).

**Means over the 16 views:** High **73.1 fps**, Medium **87.6 fps**.

| View | High fps | High p99 ms | High GPU ms | Medium fps | Medium p99 ms | Medium GPU ms |
|---|---|---|---|---|---|---|
| beam8 | 68 | 19.96 | 4.49 | 77.8 | 18 | 4.05 |
| beat15 | 62.3 | 21.49 | 4.94 | 75.7 | 17.66 | 4.22 |
| storm | 78.8 | 17.41 | 4.29 | 84.4 | 16.25 | 4.04 |
| marina | 70.2 | 18.29 | 4.68 | 87.3 | 15.45 | 4.04 |
| coast-day | 71 | 20.36 | 4.85 | 87.8 | 15.38 | 4.23 |
| coast-night | 76.7 | 18.77 | 4.52 | 96.4 | 14.41 | 3.25 |
| gulf-sea | 77.3 | 17.29 | 4.16 | 90 | 14.84 | 3.63 |
| helm-eye | 74.4 | 19.93 | 4.93 | 88.9 | 14.88 | 4.16 |
| slip | 80.1 | 15.93 | 5.21 | 92.3 | 13.98 | 4.49 |
| bridge | 74.1 | 17.8 | 4.46 | 91.3 | 14.19 | 3.81 |
| crew | 63 | 20.75 | 5.8 | 80.2 | 16.55 | 4.68 |
| marina-night | 88.4 | 14.65 | 4.38 | 96.9 | 13.14 | 3.55 |
| far-coast | 69.5 | 22.35 | 4.59 | 87.6 | 17.12 | 3.96 |
| far-coast-night | 75.5 | 19.31 | 3.7 | 93.2 | 15.01 | 3.21 |
| marseille-port | 70 | 30.58 | 4.93 | 84.7 | 26.4 | 4.22 |
| stream-run | 70.9 | 21.3 | 4.98 | 86.9 | 17.54 | 4.25 |


## Reading it

- **CPU-bound:** at 1080p this PC is limited by the CPU threads, not the GPU. The GPU frame is 3.2 to 5.8 ms on both tiers, while the frame is 10 to 16 ms. On High the render thread is the longest: for example beat15 game 11.7 / render 16.0 / RHI 8.5 ms against GPU 6.4 ms. Medium's gain is mostly lighter render-thread and game-thread work, not GPU time.
- **Slowest views on High:** beat15 (62.3) and crew (63.0), then beam8 (68.0). On Medium the slowest are beat15 (75.7) and beam8 (77.8).
- **marseille-port:** it has the highest p99 on both tiers (30.6 ms on High, 26.4 on Medium) while its mean is ordinary (70.0 and 84.7).
- **No view below 60 fps** on either tier.

## Files

- `visual-bench-tiers-8a768667.csv`: the script's table, with GPU slices
- `json/<view>-<tier>.json`: each run's bench.json, with thread times and game-thread slices
