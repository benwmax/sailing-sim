# PR #690 (wave-detail reconfigure on a worker), head ae9d8ade, on the PC

ae9d8ade already contains main 0d2c4802, so there is no merge. Against main it changes only WaterSurface.cpp/.h, so
B = A + #690. B's package is `Packaged\Windows-ae9d8ade`, with no `-merge` suffix since nothing was merged.

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **SailingSim.Visual:** 86 passed, 0 failed, 3 with warnings (`test-visual.json`).
- **Packages:** Windows-ae9d8ade and Windows-0d2c4802 are both new and were warmed once each.
- **Runs:** storm at 4K Ultra fullscreen, 30 s, `-SailingBenchTrace` plus Insights (`-trace=cpu,frame,bookmark
  -statnamedevents`), A/B/A back to back. Game-thread figures come from the trace after 8.7 s; the .utrace files stay on
  the PC.
- **Files here:** `storm-ultra.json` (bench), `storm-ultra.png` (end screenshot), `frames.csv` per run, and `table.txt`.

| run | fps | p99 ms | max ms | GPU ms | game ms | GT frames > 40 ms | GT frames > 60 ms | largest Sailing_Water | Sailing_Water median | Sailing_Water > 15 ms | Sailing_WaterUploads > 20 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a 0d2c4802 | 35.6 | 35.7 | 54.3 | 28.04 | 17.98 | 23 | 11 | 84.8 ms (startup frame, 11.0 s) | 4.02 ms | 12 | 11 (27.9-39.0 ms, through the run) |
| b #690 | 36.3 | 32.6 | 46.1 | 27.46 | 17.40 | 14 | 8 | 73.6 ms (startup frame, 11.0 s) | 3.98 ms | 6 | 3 (31.1, 41.0, 34.5 ms, all in the first 0.8 s) |
| c 0d2c4802 | 35.0 | 36.3 | 51.4 | 28.38 | 16.41 | 17 | 6 | 73.6 ms (startup frame, 9.3 s) | 3.79 ms | 11 | 10 (28.0-41.0 ms, through the run) |

**Uploads.** After its first second, #690 has no `Sailing_WaterUploads` over 20 ms; main has 7-8 there. The three
early ones (10.97-11.76 s) are the first detail configure and the cascade-size change at the start. #690 keeps
those on the game thread on purpose (`bSyncConfigure`: no detail yet, or a new cascade size).

**Worker thread.** `Sailing_WaterDetailConfigure` runs 6 times in #690's run, about every 5 s at 19.61, 24.94, 29.79,
34.67, 39.34 and 44.66 s. It runs on the task graph's background workers (Background Worker #5, #7 twice, #8 twice
and #9), taking 32.8-42.0 ms each. It is never on the GameThread. In the frames it spans, the game ticks stay at
25.7-28.3 ms. Main ran the same work on the game thread, for example a 54.3 ms tick at 19.64 s in run a.

**The detail keeps animating.**
- `Sailing_WaterDetailBlend`, the per-frame detail work on the workers, runs once a frame straight through each
  configure and after each swap.
- Around 19.61 s, blends land at 19.608, 19.634, 19.663, 19.691 and 19.714 s, one per frame. The same holds around
  every other configure.
- After 12 s the median gap between blends is 27.4 ms against main's 27.8 ms, with p99 40.1 ms against 46.3 ms. The
  last blend falls at the end of the run (45.03 s).
- The end screenshots of A and B show the same sea: the streaks, near chop, caps and rain rings look alike, with no
  frozen or flat detail on B.

**Largest Sailing_Water frame.** In every run it is the first frame after the window opens: the startup reconfigure
plus a 29-31 ms ParallelFor and far-cap PSO precaching. That frame is the same on main.
