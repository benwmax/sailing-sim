# 1 h 4K Ultra Gulf soak on Windows-8ae5a0b1 (PC, Nov 26 2026)

**Package:** Development `Packaged\Windows-8ae5a0b1`, warm.

**Run:** 16:06 to 17:06 UTC, 3840x2160 Ultra, 100% screen percentage, the demo autopilot from launch 2, "Offshore, 15 nm
south of Galveston" (18 m deep), clock 13:00:

```
-SailingWorld=Gulf -SailingLaunch=2 -SailingDemo -SailingHour=13 -SailingBench=3600 -SailingBenchTrace
```

- **Grounding-free:** she sailed south, from -31,050 to -34,443 N, in open water the whole hour.

Bean's Saved was held aside and restored (7B5CA7BE).

## Result: the full hour, exit 0, no crash

**Whole run:**
- 55.3 fps, p99 22.0 ms, max 154 ms;
- game thread 11.4 ms, render thread 18.0 ms, GPU 17.5 ms;
- memory used 3,204 MB, peak 3,836.

**Crash folder:** one, the frame-0 PSO ensure. No other ensure, fatal or assert.

| Minutes | fps | p99 ms | frames > 50 ms | longest ms |
|---|---|---|---|---|
| 0-10 | 53.9 | 23.0 | 36 | 154.1 |
| 10-20 | 55.1 | 23.8 | 4 | 64.8 |
| 20-30 | 55.6 | 21.6 | 0 | 42.8 |
| 30-40 | 55.9 | 20.7 | 0 | 43.2 |
| 40-50 | 56.1 | 21.1 | 0 | 46.0 |
| 50-60 | 55.4 | 21.2 | 0 | 48.7 |
| 60-70 | 41.4 | 29.3 | 1 | 1129.0 |

(The 60-70 row is the last seconds and the shutdown frame.)

**Frames over 50 ms:** none from minute 20 to the end. The longest frames there were 43-49 ms.

**The early slow frames are from my own disk scans, not the game.** The 36 frames over 50 ms in minutes 0-10 and the 4 in
10-20 came in patches:
- 5 frames at about 210 s;
- 30 frames at about 420 s, up to 154 ms with the game thread at 91 ms;
- 1 frame at 480 s;
- 4 frames at 660-690 s.
- Those times (16:10-16:18 UTC) are when I ran recursive size scans over about 400 GB of builds, worktrees and reel
  frames on the same D: drive, for the disk cleanup list.
- The game log has nothing at those times, and they're game-thread stalls with GPU normal, the pattern of a thread waiting
  on disk.
- **So treat minutes 0-20 as contaminated.** From minute 20 on it ran undisturbed. The 380 GB delete at about 16:30 UTC
  (minute 24) didn't show.

**Memory is flat:**

| Minute | 10 | 30 | 50 | 59 |
|---|---|---|---|---|
| Working set (MB) | 3,096 | 3,111 | 3,117 | 3,118 |
| Private (MB) | 13,473 | 13,587 | 13,599 | 13,601 |

That's +0.7% in the working set over 49 minutes.
