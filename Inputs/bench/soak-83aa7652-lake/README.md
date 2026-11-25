# 2 h 4K Ultra lake soak on Windows-83aa7652, Nov 25 2026

**Package:** Development `Packaged\Windows-83aa7652` (main 83aa7652, #827 in).

**Run:** 12:02 to 14:03 UTC, 3840x2160 Ultra, 100% screen percentage.

```
-SailingBench=7200 -SailingWorld=Lake -SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingHour=15
```

It's the grounding-free lake start used by the earlier soaks. Bean's Saved was held aside and restored (7B5CA7BE).

## Result: the full 2 h, exit 0, no crash

- **Whole run:** 53.7 fps, p99 23.0 ms, max 48.7 ms, GPU 18.1 ms, game thread 9.8 ms, render thread 18.6 ms.
- **Crash folders:** the two frame-0 ensures every run on this PC logs (groom PSO precache, matrix precision). No crash.

| Minutes | fps | frames over 30 ms | longest ms |
|---|---|---|---|
| 0-10 | 53.2 | 15 | 960.5 (load) |
| 10-20 | 54.1 | 3 | 35.6 |
| 20-30 | 54.2 | 5 | 36.7 |
| 30-40 | 53.7 | 6 | 35.5 |
| 40-50 | 53.4 | 9 | 48.7 |
| 50-60 | 53.6 | 3 | 41.1 |
| 60-70 | 53.2 | 5 | 38.3 |
| 70-80 | 53.1 | 4 | 34.4 |
| 80-90 | 53.7 | 0 | 29.8 |
| 90-100 | 53.9 | 5 | 33.8 |
| 100-110 | 53.8 | 1 | 31.2 |
| 110-120 | 54.1 | 6 | 37.1 |

- **Frame rate:** flat at 53-54 fps for the whole 2 h.
- **The ~350 ms render-thread spikes from the Galveston soak did NOT recur.** After the load, no frame over 50 ms; the
  longest was 48.7 ms.
- 0-9 frames over 30 ms per 10 min, nearly all 30-41 ms.
- The last bucket's 1.1 s frame is the bench writing its results at exit.

## Memory (game process, every minute)

- **Working set:** 3,490 MB at 10 min and 3,546 MB at 110 min (range 3,427-3,548).
- **Private bytes:** 14,296 MB at 10 min and 14,352 MB at 110 min, so +57 MB over 100 min.
- **No leak trend.**

## The boat

- **No grounding.** She made 80-130 m per minute throughout (mean 108). There's no grounding line in the log.
- Two slow minutes, both at the start while she settles.

## Against the Galveston soak (fa51d3a6)

The Galveston soak had four single render-thread spikes of about 350 ms, at 33, 61, 87 and 103 min. The lake run on
83aa7652 has none. Either they're specific to Galveston (the coast's world) or something between fa51d3a6 and 83aa7652
changed them. A 2 h Galveston soak on 83aa7652 would tell which.
