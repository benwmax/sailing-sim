# 1 h 4K Ultra Gulf soak on Windows-95220b32 (PC, Nov 27 2026)

**Package:** Development `Packaged\Windows-95220b32` (main with #844), warm.

**Run:** 08:20 to 09:20 UTC, the 8ae5a0b1 Gulf soak's arguments (`../soak-8ae5a0b1-gulf/`): 3840x2160 Ultra at 100%,
the demo from launch 2 (offshore, 15 nm south of Galveston), clock 13:00, 60 min. Bean's Saved held aside and restored
(7B5CA7BE).

## Result: the full hour, exit 0, no crash

**Whole run:** 54.2 fps, p99 22.9 ms, max 88.8 ms; game thread 12.4 ms, render thread 18.4 ms, GPU 17.9 ms; memory used
3,201 MB, peak 3,802 (8ae5a0b1: 55.3 fps, p99 22.0, peak 3,836).

**Crash folder:** one, the frame-0 PSO ensure. No other ensure, fatal or assert.

| Minutes | fps | p99 ms | frames > 50 ms | longest ms |
|---|---|---|---|---|
| 0-10 | 55.1 | 22.5 | 12 | 659.3 (first frame) |
| 10-20 | 54.2 | 23.0 | 1 | 51.5 |
| 20-30 | 53.9 | 23.0 | 1 | 54.2 |
| 30-40 | 53.4 | 23.2 | 0 | 49.1 |
| 40-50 | 54.5 | 22.7 | 1 | 50.4 |
| 50-60 | 54.0 | 22.9 | 2 | 50.1 |
(The 1,179 ms shutdown frame is left out.)

**Frames over 50 ms:** after the start, 7 render-bound frames at 569 s (51-89 ms, render 51-89 ms) on the first tide
step (`tide-steps.txt`, 08:29:45), then single frames at 50-54 ms.

## Memory: flat

| Minute | working set MB | private MB |
|---|---|---|
| 5 | 3,201 | 13,556 |
| 10 | 3,095 | 13,436 |
| 20 | 3,139 | 13,509 |
| 30 | 3,150 | 13,587 |
| 40 | 3,137 | 13,575 |
| 50 | 3,142 | 13,582 |
| 59 | 3,161 | 13,605 |

Private +96 MB from minute 20 to 59 (2.5 MB/min), +49 from minute 5. So the 95220b32 climb (+15 MB/min after minute 20,
`../soak-95220b32-galveston/`) does not show offshore; the Galveston-route bisect (`../membisect-galveston/`) follows.
