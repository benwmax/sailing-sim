# Galveston soak follow-ups (Windows-02eea166, Ultra 4K, warm), PC, Nov 26 2026

## 1. Burst hunt: 5 min from the soak's last position, traced

**Run:**
```
-SailingWorld=1 "-SailingStartAt=-21100,18175,184" -SailingDemo -SailingHour=16.92 -SailingBench=300
-trace=cpu,frame -statnamedevents
```
- The start, heading 184, is the soak's last position and course, from its 7140 s and 7200 s position lines.
- The clock is the soak's clock then: 15:00 plus 1 h 55 min.

**Result: the bursts don't reproduce.**
- 47.5 fps, p99 25.3 ms, game thread 13.3 ms (game p99 20.6 ms).
- Only 2 frames over 50 ms in 5 min: the tide step at 138 s (-36 to -38 cm), 56 ms each in **render**, not game.
- 1 frame over 40 ms of game thread.
- In the soak's last minute, 39 frames over 50 ms had **game** thread at 50-73 ms. None here.
- Exit 0. One crash folder: the frame-0 PSO ensure.

**What differs from minute 119 of the soak:**
- **Time in the process:** 5 minutes here, 2 hours there. This is the main difference, and the soak's memory had grown
  7.6% by then.
- **Tide:** the followers stood at -36/-38 cm here; the soak was at -38 then. It's the same height, so not a factor.
- **Course:** the same start and heading. She sailed south to -21,380 N, then tacked at about 230 s; the soak held south
  for its last minute.
- **Traffic:** the default traffic in both. After 2 h the AI boats and ships are wherever they've got to, so their
  positions differ.
- **Clock:** the same 16:55 to 17:00.

**Since the trace has no slow game-thread frames,** there's nothing to name. The trace is kept locally
(`burst-hunt.utrace`, 1 GB, not pushed).

**Reading:** the bursts look tied to a long process, not to the place. The 60 min run held in one spot (part 2) is next
and logs memory and fps every minute.
