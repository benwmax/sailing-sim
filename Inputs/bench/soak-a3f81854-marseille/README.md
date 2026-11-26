# 1 h 4K Ultra Marseille soak on Windows-a3f81854 (PC, Nov 26 2026)

**Package:** Development `Packaged\Windows-a3f81854`, warmed once. It's main a3f81854 with #834, #835, #837, #838, #840
and #841, the freeze base.

**Run:** 18:18 to 19:19 UTC, 3840x2160 Ultra, 100% screen percentage, the demo autopilot from launch 9, "Offshore, past
Planier (gale)" (90 m deep), clock 13:00:

```
-SailingWorld=Marseille -SailingLaunch=9 -SailingDemo -SailingHour=13 -SailingBench=3600 -SailingBenchTrace
```

- She sailed in open water, with no grounding.
- The wildlife was running: 17 flocks, 241 birds (gannets), drawn as quads.

Bean's Saved was held aside and restored (7B5CA7BE).

## Result: the full hour, exit 0, no crash; not one frame over 50 ms

**Whole run:**
- 54.1 fps, p99 22.4 ms, **max 49.3 ms**;
- game thread 12.0 ms, render thread 18.5 ms, GPU 18.0 ms;
- memory used 10,664 MB, peak 13,871.

**Crash folder:** one, the frame-0 PSO ensure. No other ensure, fatal or assert.

| Minutes | fps | p99 ms | frames > 50 ms | longest ms |
|---|---|---|---|---|
| 0-10 | 54.4 | 22.4 | 0 | 46.8 |
| 10-20 | 54.0 | 22.4 | 0 | 45.1 |
| 20-30 | 54.6 | 22.2 | 0 | 43.9 |
| 30-40 | 54.3 | 22.2 | 0 | 48.2 |
| 40-50 | 53.6 | 22.2 | 0 | 48.5 |
| 50-60 | 53.4 | 22.6 | 0 | 49.3 |
| 60-70 | 37.6 | 31.2 | 1 | 1125.8 |

(The 60-70 row is the last seconds and the shutdown frame.)

**Memory is flat:**

| Minute | 10 | 30 | 50 | 60 |
|---|---|---|---|---|
| Working set (MB) | 10,582 | 10,577 | 10,607 | 10,595 |
| Private (MB) | 23,467 | 23,470 | 23,507 | 23,526 |

That's +0.1% in the working set over 50 minutes. Marseille holds about 7.5 GB more than the Gulf: its town, harbours and
far coast.
