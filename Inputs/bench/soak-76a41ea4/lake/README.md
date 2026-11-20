# 60-min Ultra 4K soak on the lake: main 76a41ea4 (Dev package Windows-76a41ea4), Nov 20 2026

**Run:** Bean's PC (RTX 4090), from the start #808's 60-min soak used: Ray Hubbard launch 1, `-SailingDemo`, which is
grounding-free now that the demo shoal guard is in main.

- **Settings:** 3840x2160 windowed (`-ForceRes`), Ultra, 100% screen percentage.
- **Args:** `-SailingBench=3600 -windowed -ResX=3840 -ResY=2160 -ForceRes -SailingShot=soak76a-lake -SailingQuality=Ultra
  -SailingWorld=Lake -SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingScreenPct=100 -SailingHour=15`.
- **Time:** 12:26:19 to 13:26:38 local. The game exited 0 and wrote bench.json.
- **Saved:** Bean's Saved was held aside and restored; profile 7B5CA7BE before and after.

## Result

| | |
|---|---|
| Crashes | **none**. The two crash folders are the frame-0 handled-ensure reports, as in every run: `PSOPrecache.cpp:296` and `DoubleFloat.cpp:19`. No asserts or fatals. |
| Frames | 192,881 over 3,600 s after the 3 s warm-up |
| fps | mean **53.6** (18.67 ms), median 18.62 ms |
| p99 | **21.43 ms** |
| Max in play | 42.05 ms (bench.json). The only frame over 100 ms is the shutdown frame (1,082 ms at 3,603 s). |
| Mean thread times | GPU 18.13 ms, game 10.12 ms, render 18.66 ms (GPU-bound) |
| Grounding | **none**. The shoal guard bore away 7 times (log-excerpt.txt). At the end she was on starboard tack at 4.4 kn, depth 41 ft. |

### Per 10 minutes

| Minutes | fps | p99 ms | Frames >30 ms | >100 ms |
|---|---|---|---|---|
| 0-10 | 53.0 | 21.88 | 4 | 0 |
| 10-20 | 53.8 | 21.44 | 3 | 0 |
| 20-30 | 54.1 | 20.93 | 5 | 0 |
| 30-40 | 53.6 | 21.28 | 6 | 0 |
| 40-50 | 53.6 | 21.22 | 7 | 0 |
| 50-60 | 53.3 | 21.46 | 7 | 0 |

That makes 32 frames over 30 ms in play, plus the shutdown frame (`frames-over-30ms.csv`).

## Memory

The soak script's own per-minute log sampled the Development launcher rather than the game process, which is its
child. I found this at minute 34 and logged the game process from then on (`game-memory.csv`, 27 samples).

- Working set: 3,591 MB at minute 34, 3,640 MB at minute 60.
- Private bytes: 14,201 MB at minute 34 and 14,258 MB at minute 60; the range was 14,172 to 14,374 MB.
- Threads: 80-81.
- **No growth** over the last 26 minutes. For comparison, the Nov 18 4K soak of 8a768667 held 14,271 to 14,461 MB
  private for two hours.

## Against the Nov 18 4K soak (8a768667, launch 1, before the shoal guard)

That run averaged 54.1 fps, p99 23.46 ms, with 1,888 frames over 30 ms in 2 h; it grounded, and its game-thread
hitches came after that. Here the fps is the same (53.6), the p99 is better (21.43) and there are only 3-7 frames over
30 ms per 10 minutes.
