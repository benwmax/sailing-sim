# A rough min-spec stand-in on the PC

Bean has no slower GPU, so this is a stand-in, not a min-spec test. The Mac's Low tier remains the real low-end check.
The seven gate views ran on Low and Medium at 1280x720 on the packaged Development build of main a8ce8ed3, on
Bean's PC:
- CPU: i9-9900K (2018, 8 cores and 16 threads).
- GPU: RTX 4090.
- RAM: 64 GB.

No frame cap was applied, since the bench ignores the player's cap.

| View | Low fps | Low p99 ms | Medium fps | Medium p99 ms | Game ms (L/M) | Render ms (L/M) | RHI ms (L/M) | GPU ms (L/M) | Peak RAM MB (L/M) |
|---|---|---|---|---|---|---|---|---|---|
| helm-eye | 130.3 | 10.5 | 90.5 | 15.4 | 4.4 / 6.1 | 7.6 / 10.9 | 4.9 / 5.7 | 2.5 / 3.0 | 2762 / 3320 |
| slip | 117.6 | 10.9 | 86.4 | 15.6 | 4.5 / 6.5 | 8.4 / 11.4 | 5.0 / 6.3 | 2.6 / 3.3 | 2787 / 3394 |
| coast-day | 116.4 | 10.5 | 78.3 | 17.3 | 5.0 / 8.0 | 8.5 / 12.6 | 4.9 / 6.4 | 2.4 / 3.4 | 3313 / 4885 |
| beat15 | 113.4 | 11.7 | 83.5 | 15.6 | 4.8 / 6.7 | 8.7 / 11.8 | 4.9 / 6.2 | 2.6 / 3.2 | 2924 / 3428 |
| storm | 112.2 | 10.8 | 84.1 | 16.2 | 5.0 / 6.8 | 8.8 / 11.7 | 5.1 / 6.3 | 3.0 / 3.2 | 2807 / 3385 |
| marina | 113.8 | 11.4 | 86.0 | 15.7 | 4.7 / 6.5 | 8.7 / 11.5 | 5.1 / 6.0 | 2.5 / 3.1 | 2751 / 3393 |
| crew | 115.1 | 11.1 | 82.3 | 15.7 | 4.6 / 6.6 | 8.6 / 12.0 | 4.9 / 6.0 | 2.5 / 3.5 | 2812 / 3405 |

The per-view GPU slices are in `visual-bench-720.csv`.

## Reading it

- **Both tiers are CPU-bound here, on the render thread.** At 720p the GPU needs 2.4 to 3.5 ms a frame, while the
  render thread needs 7.6 to 8.8 ms on Low and 10.9 to 12.6 ms on Medium. The frame rate follows the render thread,
  not the GPU.
- **A slower GPU** (scaling the 4090's GPU time, an estimate only): a card a sixth to an eighth of a 4090 would need
  roughly 15 to 28 ms on Medium at 720p and 15 to 24 ms on Low. That is about 35 to 65 fps, around the Mac's Medium 60
  bar.
- **A slower CPU matters as much.** A CPU half the 9900K's single-thread speed would put Medium's render thread at
  22 to 25 ms (about 40 fps) whatever the GPU.
- **The render thread includes the cost #110 removes.** The sun and atmosphere setters rebuilt the light every frame
  as the cloud shade moved, which is the drift diagnosed in `docs/budget/`. With the sun frozen, the Ultra render
  thread was about 4 ms cheaper. Re-run this after #110 merges; Low and Medium should gain.
- **RAM:** Low peaks at 2.8 to 3.3 GB and Medium at 3.3 to 4.9 GB. coast-day on Medium is the largest, with Galveston's
  chart and piers loaded. 8 GB machines look fine; 16 GB is comfortable.

Re-run with `scripts\windows\bench-visual-win.ps1 -Label minspec-720 -ResX 1280 -ResY 720 -Tiers Low,Medium -Only
helm-eye,slip,coast-day,beat15,storm,marina,crew`.
