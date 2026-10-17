# A rough min-spec stand-in on the PC

Bean has no slower GPU, so this is a stand-in, not a min-spec test. The Mac's Low tier remains the real low-end check.
The seven gate views ran on Low and Medium at 1280x720 on the packaged Development build of main cc03fb32 (with #110, re-run Oct 17; the first run was on a8ce8ed3), on
Bean's PC:
- CPU: i9-9900K (2018, 8 cores and 16 threads).
- GPU: RTX 4090.
- RAM: 64 GB.

No frame cap was applied, since the bench ignores the player's cap.

| View | Low fps | Low p99 ms | Medium fps | Medium p99 ms | Game ms (L/M) | Render ms (L/M) | RHI ms (L/M) | GPU ms (L/M) | Peak RAM MB (L/M) |
|---|---|---|---|---|---|---|---|---|---|
| helm-eye | 118.0 | 10.8 | 90.1 | 15.5 | 4.3 / 6.0 | 8.3 / 10.9 | 4.8 / 6.0 | 2.5 / 3.0 | 2753 / 3322 |
| slip | 127.2 | 10.6 | 87.2 | 15.6 | 4.7 / 6.5 | 7.8 / 11.3 | 5.1 / 6.0 | 2.6 / 3.3 | 2800 / 3376 |
| coast-day | 128.0 | 10.9 | 78.8 | 17.4 | 5.0 / 8.1 | 7.7 / 12.5 | 5.1 / 6.4 | 2.4 / 3.4 | 3321 / 4896 |
| beat15 | 113.1 | 12.1 | 84.1 | 15.8 | 4.8 / 7.2 | 8.7 / 11.7 | 5.0 / 6.7 | 2.6 / 3.0 | 2799 / 3381 |
| storm | 124.5 | 10.7 | 88.4 | 18.3 | 5.1 / 7.1 | 7.9 / 11.1 | 5.0 / 6.2 | 3.0 / 3.2 | 2796 / 3371 |
| marina | 114.8 | 12.0 | 91.6 | 14.5 | 4.7 / 6.6 | 8.6 / 10.7 | 4.8 / 6.2 | 2.5 / 3.0 | 2796 / 3381 |
| crew | 115.7 | 10.4 | 85.7 | 15.3 | 4.6 / 6.9 | 8.5 / 11.5 | 5.0 / 6.3 | 2.5 / 3.5 | 2783 / 3372 |

The per-view GPU slices are in `visual-bench-720.csv`.

## Reading it

- **Both tiers are CPU-bound here, on the render thread.** At 720p the GPU needs 2.4 to 3.5 ms a frame, while the
  render thread needs 7.7 to 8.7 ms on Low and 10.7 to 12.5 ms on Medium. The frame rate follows the render thread,
  not the GPU.
- **A slower GPU** (scaling the 4090's GPU time, an estimate only): a card a sixth to an eighth of a 4090 would need
  roughly 15 to 28 ms on Medium at 720p and 15 to 24 ms on Low. That is about 35 to 65 fps, around the Mac's Medium 60
  bar.
- **A slower CPU matters as much.** A CPU half the 9900K's single-thread speed would put Medium's render thread at
  22 to 25 ms (about 40 fps) whatever the GPU.
- **#110 changed little in these short runs.** It stopped the sun and atmosphere setters rebuilding the light every
  frame, and saved about 4 ms of render thread in the 30-minute parked soak (`docs/budget/`). In these 12 s benches the
  re-run on cc03fb32 shows render-thread times within about 1 ms of the first run on a8ce8ed3:
  - Low: 7.7 to 8.7 ms, before 7.6 to 8.8 ms. coast-day, storm and slip are each 0.6 to 0.9 ms cheaper.
  - Medium: 10.7 to 12.5 ms, before 10.9 to 12.6 ms.

  The rebuild cost depended on how much the cloud shade moved, so it showed in long runs more than in short ones.
  helm-eye on Low reads 118 fps against 130 fps; that is run-to-run noise in a CPU-bound 12 s run.
- **RAM:** Low peaks at 2.8 to 3.3 GB and Medium at 3.3 to 4.9 GB. coast-day on Medium is the largest, with Galveston's
  chart and piers loaded. 8 GB machines look fine; 16 GB is comfortable.

Re-run with `scripts\windows\bench-visual-win.ps1 -Label minspec-720 -ResX 1280 -ResY 720 -Tiers Low,Medium -Only
helm-eye,slip,coast-day,beat15,storm,marina,crew`.
