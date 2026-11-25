# 2 h 4K Ultra soak on Windows-fa51d3a6 (Galveston deep water), Nov 25 2026

**Package:** Development `Packaged\Windows-fa51d3a6` (main fa51d3a6).

**Run:** 07:38 to 09:38 UTC, 3840x2160 Ultra, 100% screen percentage.

```
-SailingBench=7200 -SailingWorld=1 "-SailingStartAt=-20900,23500,120" -SailingDemo -SailingBenchTrace -SailingHour=15
```

It's soak76a's deep-water start in Bolivar Roads, with
`r.RayTracing.DumpUnreferencedAlwaysResidentGeometries` at 300 s and 6900 s. Bean's Saved was held aside and restored
(7B5CA7BE).

## Result: ran the full 2 h, exit 0, no crash

- **Whole run:** 50.7 fps, p99 25.1 ms, GPU 19.2 ms, game thread 12.65 ms, render thread 19.7 ms.
- **Crash folders:** two, both from frame 0. They're the two ensures every run on this PC logs: the groom PSO precache
  and "precision loss converting matrix". There was no crash.
- **Always-resident RT geometry dumps:** both are empty (0 unreferenced), at 5 and 115 min.

## Per 10 minutes (from `-SailingBenchTrace`, 365,240 frames)

| Minutes | fps | frames over 30 ms | longest ms |
|---|---|---|---|
| 0-10 | 52.2 | 17 | 856.8 (load) |
| 10-20 | 52.4 | 8 | 32.2 |
| 20-30 | 52.0 | 2 | 31.2 |
| 30-40 | 52.9 | 8 | **353.5** |
| 40-50 | 54.4 | 6 | 30.7 |
| 50-60 | 49.1 | 7 | 32.4 |
| 60-70 | 48.3 | 7 | **349.3** |
| 70-80 | 48.6 | 3 | 31.1 |
| 80-90 | 49.8 | 6 | **341.6** |
| 90-100 | 49.5 | 4 | 32.3 |
| 100-110 | 49.5 | 8 | **351.7** |
| 110-120 | 49.8 | 4 | 33.1 |

- **Frame rate:** steady, but about 3 fps lower in the second hour (49-50 against 52-54). That follows the boat into
  different scenery and later light; it isn't drift in memory.
- **Hitches:** besides the load and the dump at 5 min, there are **4 single render-thread hitches of about 350 ms**,
  at 33, 61, 87 and 103 min.
  - Each is the render thread at 340-356 ms, with the game thread at about 40 ms and the GPU normal at 19 ms.
  - I couldn't tie them to anything in the log: no recentre, no streaming lines. The 5 min one lines up with the RT
  geometry dump command.
  - A trace across one would name it.
- Otherwise there are only 2-8 frames over 30 ms per 10 min, all of them 30-33 ms.

## Memory (game process, every minute)

- **Working set:** 3,966 MB at 10 min and 4,092 MB at 110 min (peak 4,768). Flat within about ±60 MB after the first
  10 min.
- **Private bytes:** 15,180 MB at 10 min and 15,254 MB at 110 min, so +74 MB over 100 min. **No leak trend.** The
  15 GB private figure is the commit, steady from the start.

## The boat

- She stayed afloat and **never grounded.** The position line every minute shows 80-120 m per minute throughout (mean
  112).
- The slow minutes, 31-39 m, are the first 9 minutes while she settles and tacks. There was one more at 86 min (21 m),
  a tack.
- There's no grounding line in the log. She ended at -21,091 N, 18,266 E, 3.8 kn.
