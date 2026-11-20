# 60-min Ultra 4K soak on Galveston Bay from deep water: main 76a41ea4 (Dev package Windows-76a41ea4), Nov 20 2026

Bean's PC (RTX 4090), 3840x2160 windowed (`-ForceRes`), Ultra, 100% screen percentage, autopilot demo.

**Start:** deep water in Bolivar Roads, not launch 1's south shoal: `-SailingStartAt=-20900,23500,120`, which is
29.356 N, 94.777 W, heading 120. A 25 s probe there read 19 ft on the HUD (keel 3.8 ft, alarm 5.8); an upper-bay spot
at 29.45 N, 94.80 W read only 9 ft.

**Args:** `-SailingBench=3600 -windowed -ResX=3840 -ResY=2160 -ForceRes -SailingShot=soak76a-galveston
-SailingQuality=Ultra -SailingWorld=1 "-SailingStartAt=-20900,23500,120" -SailingDemo -SailingBenchTrace
-SailingScreenPct=100 -SailingHour=15
"-SailingExecAt=300:r.RayTracing.DumpUnreferencedAlwaysResidentGeometries;3300:r.RayTracing.DumpUnreferencedAlwaysResidentGeometries"`.

**Run:** 13:26:40 to 14:27:04 local. The game exited 0 and wrote bench.json. Bean's Saved was held aside and restored;
profile 7B5CA7BE before and after.

## Result

| | |
|---|---|
| Crashes | **none**. Two crash folders, the frame-0 handled ensures as always: `PSOPrecache.cpp:296` and `DoubleFloat.cpp:19`. No asserts or fatals. |
| Frames | 191,769 over 3,600 s after the 3 s warm-up |
| fps | mean **53.2** (18.79 ms), median 18.72 ms |
| p99 | **21.97 ms** |
| Mean thread times | GPU 18.26 ms, game 12.54 ms, render 18.76 ms |
| Frames over 100 ms in play | **2**, both on the render thread: **359 ms at 574 s** (render 368.5, game 43.8, GPU 18.1) and **382 ms at 2,712 s** (render 381.1, game 41.6, GPU 18.3). Nothing in the log near either. Plus the shutdown frame (1,108 ms). |
| Grounding | **none**. The shoal guard bore away 8 times. The boat stayed within about 1.3 km of the start, between -22,398 and -20,900 N, 21,674 and 23,518 E. At the end she was on a broad reach on port at 4.6 kn, depth 26 ft. |

### Per 10 minutes

| Minutes | fps | p99 ms | Frames >30 ms | >100 ms |
|---|---|---|---|---|
| 0-10 | 53.1 | 22.36 | 4 | 1 (574 s) |
| 10-20 | 53.3 | 22.03 | 0 | 0 |
| 20-30 | 52.9 | 22.05 | 0 | 0 |
| 30-40 | 52.3 | 22.25 | 0 | 0 |
| 40-50 | 53.7 | 21.61 | 5 | 1 (2,712 s) |
| 50-60 | 54.3 | 21.27 | 0 | 0 |

That makes 9 frames over 30 ms in play, plus 2 in the shutdown second.

## Memory (game process, every minute: `game-memory.csv`)

- Working set: 4,623 MB at minute 1, 3,745 MB at minute 60.
- Private bytes: 15,890 MB at minute 1, 15,170 MB at minute 60. **No growth:** it settles about 0.7 GB lower after
  the first minutes.
- Threads: 79-84.

## Ray tracing always-resident memory (the #32 warning)

- **The warning is on screen only:** "RAY TRACING GEOMETRY - ALWAYS RESIDENT MEMORY EXCEEDS 20% OF THE BUDGET
  (92.1 MiB / 400 MiB)", red text at the top left. The log has no line for it, so there is no count to give. It was up
  in the 25 s probe and is still up in the end screenshot (under the HUD's top bar), so it stood the whole hour.
- **The dumps measure it:** `UnreferencedAlwaysResidentGeometries` at 300 s holds 1,966 geometries, 87.67 MB; at
  3,300 s, 1,965 geometries, 87.66 MB. **Flat**, and about what the Nov 18 dump read on Galveston (88.8 MiB, #32).
  Neither dump made a slow frame (no frame over 30 ms at 300 s or 3,300 s).

## Against the Nov 17-18 1080p soak (8a768667, launch 1)

That run gave 67.5 fps, p99 21.77 ms, 10 frames over 30 ms, and one render-thread hitch (352 ms at 2,890 s) with
nothing in the log. This 4K run's two hitches look the same: render thread about 370 ms, GPU normal, nothing logged.
