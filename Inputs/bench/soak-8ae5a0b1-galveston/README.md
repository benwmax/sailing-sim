# 2 h 4K Ultra Galveston soak on Windows-8ae5a0b1, a repeat of the 02eea166 soak, traced from minute 105 (PC, Nov 26 2026)

**Package:** Development `Packaged\Windows-8ae5a0b1` (main with #835). It was warmed by the R08b take.

**Run:** 13:07 to 15:07 UTC. The 02eea166 soak's arguments exactly (`../soak-02eea166-galveston/`): Bolivar Roads
start, demo autopilot, clock 15:00, 120 min, with the ray-tracing dumps at 300 s and 6900 s.
- **The trace:** at 6295 s `stat namedevents`, then at 6300 s (minute 105) `Trace.File <abs path> cpu,frame`,
  through the end.
- **Result:** the trace is 4.6 GB, kept locally, not pushed.

Bean's Saved was held aside and restored (7B5CA7BE).

## Result: the full 2 h, exit 0, no crash; the late game-thread bursts did not come back

**Whole run:**
- 51.1 fps, p99 24.6 ms, max 64.5 ms;
- game thread 13.4 ms, render thread 19.5 ms, GPU 19.0 ms;
- memory used 4,157 MB, peak 5,740.

**Crash folder:** one, the frame-0 PSO ensure.

| Minutes | fps | p99 ms | frames > 50 ms | longest ms |
|---|---|---|---|---|
| 0-10 | 52.1 | 23.5 | 2 | 54.1 |
| 10-20 | 52.0 | 24.1 | 0 | 31.4 |
| 20-30 | 51.8 | 23.6 | 1 | 52.1 |
| 30-40 | 52.4 | 23.6 | 1 | 51.6 |
| 40-50 | 53.4 | 22.8 | 0 | 27.8 |
| 50-60 | 52.6 | 23.6 | 1 | 56.2 |
| 60-70 | 49.1 | 25.0 | 1 | 53.5 |
| 70-80 | 49.4 | 24.8 | 1 | 55.2 |
| 80-90 | 52.9 | 23.7 | 1 | 58.1 |
| 90-100 | 51.8 | 24.0 | 1 | 56.8 |
| 100-110 | 48.4 | 25.3 | 0 | 33.2 |
| 110-120 | 47.7 | 26.7 | 2 | 64.5 |
| 120-130 | 35.6 | 36.0 | 1 | 1238.5 |
(The 120-130 row is the last seconds and the shutdown frame.)

**Frames over 50 ms:** one or two per 10 min, 51-65 ms. Each is a tide step (10 `Tide step` lines, one at a time, no
flapping) and render-bound.

**The last minutes:**
- only 1 frame over 40 ms of game thread in 6000-7200 s, and that one is the shutdown frame;
- in the 02eea166 soak's last minute there were 39 frames over 50 ms at game 50-73 ms;
- **so there are no bursts to name in the trace.**

**But the course wasn't the same.** With the same start and arguments, the demo didn't sail the same track:
- at 7140 s she was at -20,820 N, 19,963 E;
- the 02eea166 soak was at -21,096 N, 18,177 E then, 1.8 km further west and 280 m south;
- the demo's tacks follow the gusty wind, which isn't the same run to run.
- So this run doesn't reach the spot of the earlier bursts at the same time.
- With the burst hunt there (`../soak-02eea166-galveston/followup/`), 5 min with no bursts, the bursts haven't been
  seen again either way.

**Memory and fps:**
- working set 3,910 MB at minute 10 and 4,090 at minute 116 (+4.6%);
- private 14,825 to 15,664 MB (+5.7%).
- fps sags to 48-49 in minutes 60-80 and 100-120 and recovers in between (52.9 at 80-90). That follows where she is in
  the bay, as the held run showed.
- Minutes 105-120 also carry the trace's own cost.
