# 2 h 4K Ultra Galveston soak on Windows-02eea166, main with #836 and #838 (PC, Nov 26 2026)

**Package:** Development `Packaged\Windows-02eea166` (main 02eea166). It was warmed by the R06 take.

**Run:** 09:32 to 11:32 UTC, 3840x2160 Ultra, 100% screen percentage, the deep-water Bolivar Roads start, demo autopilot:

```
-SailingBench=7200 -SailingWorld=1 "-SailingStartAt=-20900,23500,120" -SailingDemo -SailingBenchTrace -SailingHour=15
```

The command also had the ray-tracing geometry dumps at 300 s and 6900 s. Bean's Saved was held aside and restored
(7B5CA7BE).

## Result: the full 2 h, exit 0, no crash

**Whole run:**
- 50.6 fps, p99 27.0 ms, max 96.4 ms;
- game thread 13.2 ms, render thread 19.8 ms, GPU 19.1 ms;
- memory used 4,189 MB, peak 5,875.

**Crash folder:** one, the frame-0 PSO-precache ensure every run on this PC logs. No other ensure, fatal or assert.

| Minutes | fps | p99 ms | frames > 50 ms | longest ms |
|---|---|---|---|---|
| 0-10 | 51.4 | 28.2 | 1 | 58.4 |
| 10-20 | 51.6 | 27.9 | 0 | 39.9 |
| 20-30 | 52.0 | 25.6 | 1 | 55.6 |
| 30-40 | 52.2 | 26.7 | 1 | 54.0 |
| 40-50 | 53.1 | 26.0 | 0 | 35.0 |
| 50-60 | 53.1 | 26.4 | 0 | 49.8 |
| 60-70 | 51.1 | 26.8 | 1 | 54.8 |
| 70-80 | 48.5 | 27.1 | 1 | 53.0 |
| 80-90 | 49.3 | 26.3 | 0 | 36.7 |
| 90-100 | 48.2 | 27.5 | 0 | 47.1 |
| 100-110 | 48.2 | 27.5 | 1 | 54.3 |
| 110-120 | 48.4 | 28.0 | 39 | 96.4 |
| 120-130 | 36.2 | 35.7 | 1 | 1147.4 |

(The 120-130 row is the last seconds and the shutdown frame.)

## The tide fix over a long run: 8 real steps, no flapping

The followers went from -22 cm to -38 cm in eight 2 cm steps, one at a time (`tide-steps.txt`):
- at 3, 21, 35, 51, 61, 78, 103 and 118 minutes;
- never back, and no step within minutes of another.

**Each step is one frame of 53-58 ms,** the single frames over 50 ms in minutes 20-110. That matches the forced-step
runs (`../pr836/0d2ac23a-forced/`, `../pr841/`).

## Two things to look at

**1. The last minute (7141-7203 s): 39 frames over 50 ms, up to 96 ms.**
- They're game-thread frames (game 50-73 ms, render about 25, GPU about 20), in bursts. The run was about 29 fps for
  that minute.
- Nothing in the log explains it:
  - no tide step;
  - not the 6900 s dump, which was 4 minutes earlier;
  - no streaming lines.
- The boat was sailing south past -21,100 N, 18,170 E.
- It wasn't traced. A short traced run started from that spot would say what the game thread is doing.

**2. fps drifts from about 53 to about 48 after minute 70, and memory grows:**
- working set 3,882 MB at minute 10, 4,178 at minute 116 (+7.6%);
- private 14,774 to 15,566 MB (+5.4%);
- the lake soak on 412440c8 stayed flat (`../soak-412440c8/`).
- Galveston's route moves through the bay, so some of this may be where she is rather than time. A rerun that holds her
  in one spot would separate the two.
