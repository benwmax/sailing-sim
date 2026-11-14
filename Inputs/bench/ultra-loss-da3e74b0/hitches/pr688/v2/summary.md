# PR #688 v2 (head 24392579) on the PC

24392579 rebuilds a tile only when it truly cannot carry the cover, and adds a `Sailing_FarCapBuild` trace scope. I
merged it locally with main 62a84cc7 as `local/pr688v2-check` a84dea01 (not pushed). Against 62a84cc7 it differs only
in WaterSurface.cpp/.h and WaterTests.cpp, so B = A + #688.

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **SailingSim.Visual:** 86 passed, 0 failed, 3 with warnings; `SailingSim.Visual.FarCapSprites` Success (`test-visual.json`).
- **Packages:** Packaged\Windows-24392579-merge is new and was warmed once. A reuses Packaged\Windows-62a84cc7, already warm.
- **Runs:** storm at 4K Ultra fullscreen, 30 s, `-SailingBenchTrace` plus an Insights CPU trace, A/B/A back to back.
  The .utrace files stay on the PC.
- **What is counted:** game-thread figures come from the trace after 8.7 s. On #688, a build frame is a
  `Sailing_FarCapBuild` that built at least one tile. That scope runs once per plan (every 0.5 s, or every frame while
  tiles wait), and 13 of its 100 events built nothing. On main, which has no scope, a build frame is a
  `Sailing_Water` with `RegisterComponent` calls; tiles are counted per `RegisterComponent`.

| run | fps | p99 ms | GPU ms | game ms | GT frames > 40 ms | largest Sailing_Water | build frames / Sailing_Water frames | tiles built | most tiles in a frame | Sailing_Water median | Sailing_Water > 15 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a 62a84cc7 | 36.1 | 37.5 | 27.48 | 15.79 | 20 | 97.6 ms (29 tiles + a 33.9 ms reconfigure) | 69 / 1171 | 876 | 31 | 3.80 ms | 29 |
| b #688 v2 | 36.4 | 34.8 | 27.66 | 18.43 | 20 | 74.2 ms (first frame of the window: a 32.2 ms reconfigure + 29.2 ms ParallelFor; 2 tiles, FarCapBuild 2.1 ms) | 87 / 1180 (100 scope events) | 200 | 10 | 4.06 ms | 11 |
| c 62a84cc7 | 36.0 | 38.3 | 27.61 | 17.70 | 25 | 100.5 ms (29 tiles + a 29.4 ms reconfigure) | 70 / 1168 | ~880 | 31 | 4.00 ms | 31 |

Tiles per build frame:
- **#688 v2:** 31 frames with 1 tile, 30 with 2, 11 with 3, 7 with 4, 5 with 5, and one each with 6, 8 and 10.
  `Sailing_FarCapBuild` takes at most 4.1 ms, median 0.69 ms.
- **main:** 26 to 31 tiles in 13-15 frames per run; the rest of its build frames have 4 to 11 tiles.

On #688 v2, `Sailing_Water` has a median of 5.39 ms on its 87 build frames and 4.00 ms on the others.

**Results:**
- **No more 30-tile frames.** The largest build frame has 10 tiles, and the build scope never passes 4.1 ms.
- **The median is back to main's,** 4.06 ms against 3.80-4.00 ms; the first #688 run was 5.3 ms.
- **Build frames are 87, not well under main's 69-70.** They are small: #688 builds 200 tiles in all, against about 880
  on main.
- **Large water frames:** `Sailing_Water` over 15 ms falls from 29-31 to 11. Its large frames are now the wave-detail
  reconfigure (`Sailing_WaterUploads` 29-44 ms), fix 3's target.
- **Frame rate:** p99 is 34.8 ms against 37.5-38.3 ms, and fps is unchanged.

This session's GPU time (27.5 ms) and fps (36) differ from the first #688 runs (23.7 ms, 33.5 fps). Compare A/B/A only
within one set.
