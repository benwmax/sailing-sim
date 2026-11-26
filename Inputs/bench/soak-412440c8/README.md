# 2 h 4K Ultra lake soak on Windows-412440c8, the pre-freeze main (PC, Nov 26 2026)

**Package:** Development `Packaged\Windows-412440c8` (main 412440c8, #836 in). It was warm: 8 earlier launches.

**Run:** 07:17 to 09:17 UTC, 3840x2160 Ultra, 100% screen percentage. It's the same grounding-free lake start as the
83aa7652 soak (`../soak-83aa7652-lake/`):

```
-SailingBench=7200 -SailingWorld=Lake -SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingHour=15
```

Bean's Saved was held aside and restored (7B5CA7BE).

## Result: the full 2 h, exit 0, no crash

**Whole run:**
- 52.7 fps, p99 23.2 ms;
- max 134.9 ms, at load in the first minute;
- GPU 18.4 ms, game thread 9.8 ms, render thread 19.0 ms.

**Crash folders:** two, at frame 0. They're the two ensures every run on this PC logs (component PSO precache, double-float
origin), not crashes. Nothing else in the log is an ensure, fatal or assert.

| Minutes | fps | p99 ms | frames > 50 ms | longest ms |
|---|---|---|---|---|
| 0-10 | 52.4 | 23.1 | 2 | 134.9 |
| 10-20 | 53.2 | 22.9 | 0 | 37.9 |
| 20-30 | 53.2 | 22.9 | 0 | 39.5 |
| 30-40 | 52.7 | 23.4 | 0 | 37.2 |
| 40-50 | 52.6 | 23.3 | 0 | 35.1 |
| 50-60 | 52.2 | 23.5 | 0 | 38.2 |
| 60-70 | 52.2 | 23.4 | 0 | 38.2 |
| 70-80 | 52.2 | 23.4 | 0 | 37.1 |
| 80-90 | 52.8 | 23.3 | 0 | 34.0 |
| 90-100 | 52.9 | 23.2 | 0 | 40.4 |
| 100-110 | 52.8 | 23.1 | 0 | 38.3 |
| 110-120 | 52.8 | 23.1 | 0 | 35.5 |
(The 120-130 row is the last few seconds and the shutdown frame, not play.)

**Frames over 50 ms:** none after the first 10 minutes. The 2 in minutes 0-10 are the load.

**Memory is flat:**

| Minute | 10 | 30 | 60 | 90 | 116 |
|---|---|---|---|---|---|
| Working set (MB) | 3,386 | 3,446 | 3,476 | 3,488 | 3,467 |
| Private (MB) | 14,193 | 14,222 | 14,319 | 14,302 | 14,313 |

That's under 1% growth after the first 10 minutes. bench.json: memory used 3,474 MB, peak 4,080.

**Against 83aa7652's lake soak (Nov 25):**

| | 83aa7652 | 412440c8 |
|---|---|---|
| fps | 53.7 | 52.7 |
| p99 | 23.0 ms | 23.2 ms |
| Longest frame after load | 48.7 ms | 40.4 ms |

That's 1 fps lower across the run with a steadier tail. A 1 fps drop is within this PC's run-to-run spread on the lake.
