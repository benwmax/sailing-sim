# T1 trees: Mac stills and cost (High, M5 Pro, 1080p)

Before is main c903d152; after is `t1-tree-lighting` (lake towers and north shore at 16753abb, shore150 at 72e00da0). Stills are the same scene, hour, weather and seed
(`scenes.csv`, `scripts/capture-scenes.sh` uncooked). `shore150` now uses the PC's camera (`-SailingCamWorld=60,260,2,80,0`, 17:00, 1440x1080), so the
stills match the PC's.
Compare with `real-shore.jpg` (real-10) and `real-lakeopen.jpg` (standing in for real-03); credits in `credits.md`.

| Scene | Before | After |
|---|---|---|
| Lake towers | `r12-lake-towers-before.jpg` | `r12-lake-towers-after.jpg` |
| North lake shore | `r12-lake-north-shore-before.jpg` | `r12-lake-north-shore-after.jpg` |
| Shore 150 m | `shore150-before.jpg` | `shore150-after.jpg` |

## Cost (re-gate at 72e00da0, packaged Development, 12 s per view)

On 72e00da0 the crowns and the hidden proxies are in the ray-tracing scene on Ultra only; on High they are in Lumen's
scene and the distance fields alone. `gate.sh --scope world` passes (Medium 60, High 45). Main c903d152 was re-benched
in the same session, because this Mac runs some launches in a faster state (lake-towers 69 fps on main in the first
gate and in one launch today, 64 in the others): compare within a session, not across them.

| View (High) | fps main / branch | GPU ms | Lumen ms | render thread ms |
|---|---|---|---|---|
| marina | 60.4 / 60.0 | 14.62 / 14.74 | 1.93 / 1.98 | 16.32 / 16.42 |
| coast-day | 52.5 / 52.6 | 15.67 / 15.65 | 2.25 / 2.20 | 18.75 / 18.72 |
| coast-night | 59.0 / 58.1 | 16.54 / 17.24 | 2.17 / 2.20 | 16.71 / 16.89 |
| helm-eye | 52.3 / 51.3 | 18.18 / 18.43 | 3.17 / 3.33 | 18.76 / 19.14 |
| slip | 52.4 / 51.6 | 17.49 / 17.47 | 3.93 / 3.81 | 18.78 / 19.07 |
| bridge | 63.0 / 62.7 | 14.43 / 14.58 | 2.04 / 2.31 | 15.65 / 15.71 |
| marina-night | 52.5 / 52.5 | 17.19 / 17.23 | 3.51 / 3.38 | 18.75 / 18.75 |
| lake-towers | 64.2 / 63.1 | 14.98 / 15.99 | 2.15 / 2.25 | 15.32 / 15.58 |
| shore150 | 51.9 / 51.0 | 18.31 / 19.44 | 2.72 / 2.54 | 18.94 / 19.26 |

The render thread is within 0.4 ms of main on every view (it was 2 to 3.5 ms longer at 16753abb). On Medium every view
is within 3 fps and 0.4 ms of main. lake-towers and shore150 (the bench used the earlier Mac stand-in camera,
`-SailingLaunch=3 -SailingHour=16 -SailingCamWorld=5000,1650,2,90,1`) in the three states, fps / render thread ms:

| View (High) | main | branch `-SailingNoTreeLight` | branch (High default) | branch `-SailingTreeRayTracing=1` |
|---|---|---|---|---|
| lake-towers | 64.2 / 15.32 | 64.0 / 15.35 | 63.1 / 15.58 | 52.3 / 18.76 |
| shore150 | 51.9 / 18.94 | 51.4 / 19.11 | 51.0 / 19.26 | 43.4 / 22.62 |

So the crowns in Lumen's scene alone cost 0.15 to 0.25 ms of render thread; in the ray-tracing scene they cost 3.4 ms,
which is what Ultra-only now keeps off the Mac. The looks (custom data 0-2) and the new tree materials cost nothing
measurable (with main's four tree assets swapped in, the branch measured the same). They don't collide with E1's slots
10-15, which are on the house and marina ISMs only.
