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

## 2. Drift: 60 min held in one spot

**Run:**
```
-SailingWorld=1 "-SailingStartAt=-20707,20215,320" -SailingKeepStart -SailingHour=16.17 -SailingBench=3600
```
- **No demo.** The start is the soak's minute-70 position, and the clock is the soak's clock then.
- **Where she ended up:** without the autopilot she drifted about 750 m south-west in the first few minutes to about
  -21,429 N, 19,961 E. She stayed there (0.5 m per minute) for the rest of the hour, so the view and the place held still
  after that.
- **Logging:** memory every minute (`held-60min-memory.csv`), and fps, p99 and game thread per minute from the frames
  (`held-60min-per-minute.csv`).

**Result: nothing drifts when she stays put.**
- **Whole run:** 49.9 fps, p99 24.8 ms, game thread 12.3 ms, render thread 20.0 ms, GPU 19.5 ms. Exit 0, one crash folder
  (the frame-0 PSO ensure).

| Minute | 1 | 10 | 20 | 30 | 40 | 50 | 55 |
|---|---|---|---|---|---|---|---|
| fps | 49.1 | 49.3 | 49.3 | 49.3 | 49.4 | 49.5 | 49.7 |
| Working set (MB) | 3,845 | 3,720 | 3,756 | 3,751 | 3,742 | 3,780 | 3,818 |
| Private (MB) | 14,766 | 14,618 | 14,720 | 14,732 | 14,774 | 14,879 | 14,984 |

- **fps is flat** at 49.1-49.7 from minute 1 to 55.
- **The working set is flat:** -0.7% from minute 1 to 55.
- **Private bytes are up 1.5%** over the hour.
- **In the soak, sailing the bay:**
  - fps fell from about 53 to about 48 after minute 70;
  - working set +7.6%, private +5.4% over 106 minutes.
- **Frames over 50 ms:**
  - the five tide steps (-32 to -42 cm), one frame each, 50-64 ms, render-bound;
  - one 155 ms frame at 3486 s with game 12 ms and render 20 ms, so a GPU or present stall; it didn't repeat;
  - no game-thread bursts.

**Reading:** the soak's fps drift and most of its memory growth follow the route, not time:
- held in one place, the process stays flat for an hour;
- the burst hunt (part 1) didn't reproduce the last minute's game-thread bursts either.
- **What's left unexplained:** the soak's last-minute bursts after 2 h. They need a long run that's both sailing and
  traced.
- **A candidate for the memory:** what grows along the route, such as terrain chunks, tiles, crowns and houses near the
  boat. The soak's bench.json shows 76 chunks dropped and 4,347 made.
