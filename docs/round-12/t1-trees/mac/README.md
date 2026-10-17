# T1 trees: Mac stills and cost (High, M5 Pro, 1080p)

Before is main c903d152; after is `t1-tree-lighting` 16753abb. Stills are the same scene, hour, weather and seed
(`scenes.csv`, `scripts/capture-scenes.sh` uncooked). `shore150` is the Mac's stand-in for the PC's shore150 still
(its arguments weren't saved): the east shore south of Chandlers Landing, about 150 m off, sun behind the camera.
Compare with `real-shore.jpg` (real-10) and `real-lakeopen.jpg` (standing in for real-03); credits in `credits.md`.

| Scene | Before | After |
|---|---|---|
| Lake towers | `r12-lake-towers-before.jpg` | `r12-lake-towers-after.jpg` |
| North lake shore | `r12-lake-north-shore-before.jpg` | `r12-lake-north-shore-after.jpg` |
| Shore 150 m | `shore150-before.jpg` | `shore150-after.jpg` |

## Cost (packaged Development, 12 s per view)

`gate.sh --scope world` passes (Medium 60, High 45). GPU time is unchanged within the noise. On High, though, the
render thread is 2 to 3.5 ms longer per frame, and the frame is bound by it:

| View (High) | fps main / branch | GPU ms | Lumen ms | render thread ms |
|---|---|---|---|---|
| marina | 61.6 / 52.8 | 14.42 / 14.19 | 1.97 / 2.06 | 15.99 / 18.65 |
| coast-day | 53.6 / 45.1 | 15.40 / 15.87 | 2.12 / 2.09 | 18.32 / 21.78 |
| coast-night | 59.6 / 49.2 | 16.51 / 14.71 | 2.23 / 2.00 | 16.53 / 20.00 |
| helm-eye | 53.0 / 45.2 | 18.58 / 18.53 | 3.19 / 3.20 | 18.53 / 21.67 |
| slip | 52.9 / 47.3 | 18.11 / 17.64 | 3.92 / 3.48 | 18.61 / 20.79 |
| bridge | 64.2 / 53.3 | 14.12 / 14.23 | 2.06 / 1.99 | 15.34 / 18.47 |
| marina-night | 53.2 / 48.2 | 18.21 / 17.11 | 3.23 / 3.05 | 18.52 / 20.42 |
| lake-towers | 69.0 / 56.1 | 14.06 / 14.37 | 1.79 / 1.81 | 14.24 / 17.52 |
| shore150 | 57.1 / 48.0 | 16.73 / 17.22 | 2.29 / 2.34 | 17.23 / 20.47 |

On Medium every view is within 2 fps of main. With `-SailingNoTreeLight` on the branch, lake-towers is 69.2 fps
(render thread 14.19 ms) and shore150 57.1 (17.22 ms): the same as main. So the cost is the lighting part (the crowns
and the hidden proxies in ray tracing and Lumen's scene), and on Metal it is CPU-side, not GPU. The looks (custom data
0-2) cost nothing measurable. They don't collide with E1's slots 10-15, which are on the house and marina ISMs only.
