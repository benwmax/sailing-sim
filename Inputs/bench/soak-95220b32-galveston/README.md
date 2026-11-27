# 1 h 4K Ultra Galveston soak on Windows-95220b32 (PC, Nov 27 2026)

**Package:** Development `Packaged\Windows-95220b32` (main with #844), warmed by the W20b takes.

**Run:** 07:19 to 08:19 UTC, the 8ae5a0b1 soak's arguments (`../soak-8ae5a0b1-galveston/`) for 60 min: Bolivar Roads
start, demo autopilot, clock 15:00, 3840x2160 Ultra at 100%, ray-tracing dump at 300 s. Bean's Saved held aside and
restored (7B5CA7BE).

## Result: the full hour, exit 0, no crash

**Whole run:** 50.8 fps, p99 24.3 ms, max 74.4 ms; game thread 13.9 ms, render thread 19.7 ms, GPU 19.1 ms; memory
used 3,945 MB, peak 5,366 (bench.json).

**Crash folder:** one, the frame-0 PSO ensure (`PSOPrecache.cpp` line 296), as in every soak.

| Minutes | fps | p99 ms | frames > 50 ms | longest ms |
|---|---|---|---|---|
| 0-10 | 50.2 | 25.5 | 43 | 639.1 (first frame) |
| 10-20 | 50.8 | 24.0 | 0 | 31.3 |
| 20-30 | 49.9 | 24.6 | 1 | 73.8 |
| 30-40 | 50.7 | 24.3 | 2 | 56.2 |
| 40-50 | 52.0 | 23.9 | 2 | 54.0 |
| 50-60 | 51.4 | 24.0 | 2 | 60.7 |
(The last row's 1,251 ms shutdown frame is left out.)

**Frames over 50 ms:**
- **44 to 55 s:** 33 game-thread frames at 50-74 ms (game 45-62 ms, render about 20, GPU 19). The log has nothing in
  that window but the usual 5 s lines (wildlife update 0.06 ms). The 8ae5a0b1 soak had 2 frames over 50 ms in its
  first 10 min, so this is new or chance; a trace of the first minute would name it.
- **After that:** one to three per 10 min, 51-74 ms, render-bound (render 54-76 ms), at or near the tide steps
  (`tide-steps.txt`: 8 steps of 2 cm), as before.

## Memory: private bytes climb on this route

From `galveston-memory.csv` (the game process, every minute):

| Minute | working set MB | private MB |
|---|---|---|
| 5 | 3,832 | 14,856 |
| 20 | 3,745 | 14,787 |
| 30 | 3,904 | 14,946 |
| 40 | 3,908 | 15,115 |
| 50 | 3,924 | 15,258 |
| 58 | 3,935 | 15,369 |

- **Private:** +513 MB from minute 5 to 58 (9.7 MB/min), almost all after minute 20: 15 MB/min from 20 to 58.
- **Working set:** flat (+103 MB).
- **8ae5a0b1, same route:** private 15,214 at minute 5, 15,261 at minute 58, flat.
- **This morning's lake check on this package** (`memchk`, 30 min at High, wildlife on and off): no climb.

So on Windows the growth shows on the Galveston route and not the lake, near the Mac's ~12 MB/min. The boat ends at
-22,552 N, 24,675 E (1.8 km south and 1.2 km east of the start). The 1 h Gulf soak runs next on the same package.
