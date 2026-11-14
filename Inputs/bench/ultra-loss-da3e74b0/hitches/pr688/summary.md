# PR #688 (far-cap tiles rebuilt gradually) on the PC

b3104404 is based on f3eacd59, so I merged it locally with main 62a84cc7 as `local/pr688-check` 4ed14560 (not pushed).
Against 62a84cc7 it differs only in #688's WaterSurface.cpp/.h and WaterTests.cpp, so B = A + #688.

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **SailingSim.Visual:** 86 passed, 0 failed, 3 with warnings; `SailingSim.Visual.FarCapSprites` Success (`test-visual.json`).
- **Packages:** Packaged\Windows-b3104404-merge and Packaged\Windows-62a84cc7, both new, warmed once each.
- **Runs:** storm at 4K Ultra fullscreen, 30 s, `-SailingBenchTrace` plus an Insights CPU trace, A/B/A back to back
  (62a84cc7, #688, 62a84cc7). The .utrace files stay on the PC.
- Far-cap tile builds are counted by the `RegisterComponent` calls inside `Sailing_Water` (#688 adds no scope of its own).

| run | fps | p99 ms | GPU ms | game ms | GT frames > 40 ms | largest Sailing_Water | largest far-cap frame | Sailing_Water > 15 ms |
|---|---|---|---|---|---|---|---|---|
| a 62a84cc7 | 33.4 | 43.5 | 23.63 | 18.55 | 29 | 98.9 ms (29 tiles + a 36 ms reconfigure) | 98.9 ms, 29 tiles | 30 (23 with tile builds) |
| b #688 | 33.5 | 38.9 | 23.71 | 18.96 | 21 | 75.8 ms (2 tiles + a 29 ms reconfigure) | 75.8 ms, 2 tiles | 10 (9 of them reconfigures) |
| c 62a84cc7 | 33.8 | 41.8 | 23.64 | 17.33 | 25 | 100.9 ms (29 tiles + a 34 ms reconfigure) | 100.9 ms, 29 tiles | 25 (17 with tile builds) |

Tiles built per frame, over each run:
- **62a84cc7:** 67 frames with builds, about 26 of them building 26-31 tiles at once. Those frames cost 17-33 ms of
  `Sailing_Water` each, without the reconfigure.
- **#688:** 494 frames with builds, 1-7 tiles each (193 frames with 1 tile, 105 with 2, 82 with 3, ... 6 with 7). There
  are no 26-31 tile frames.

**The ~30-tile, 17-33 ms far-cap frames are gone on #688.** Its `Sailing_Water` frames over 15 ms drop from 25-30 to 10.
Nine of those ten are the wave-detail reconfigure (`Sailing_WaterUploads` 29-40 ms, fix 3). Two smaller ones
(20.4 and 16.8 ms) build 2 tiles.

There is one 75.8 ms frame on #688: 2 tiles, a 28.8 ms reconfigure and 47 ms more inside `Sailing_Water` with no named
child; a one-off in this run.

`Sailing_Water`'s median rises from 4.0 to 5.3 ms, the build work now spread over frames. p99 is 3-5 ms lower; fps and
GPU are unchanged.
