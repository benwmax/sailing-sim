# #808 demo shoal guard: 60-minute repro soak on Ray Hubbard (PC), head c5688f4d

**Build:**

- #808 head `c5688f4d` merged locally with main `df3bca26` as `021b1d39` (not pushed), fresh worktree, `git lfs pull` after the merge.
- MSVC build: Succeeded.
- Development package `Packaged\Windows-808-c5688f4d`. The worktree was removed.

**Run:**

- The course of the earlier soaks that grounded on the south shore: lake, launch 1, `-SailingDemo`, Ultra 1920x1080 windowed, 100% screen percentage, game clock from 15:00, `-SailingBenchTrace`.
- Args: `-SailingBench=3600 -windowed -ResX=1920 -ResY=1080 -SailingShot=soak-808 -SailingQuality=Ultra -SailingWorld=Lake -SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingScreenPct=100 -SailingHour=15`.
- 11:26:53 to 12:28:15 local. The launcher exited 0. Bean's Saved was held aside and restored (profile hash checked).

## Result: no grounding; the hitch bursts are gone

- **No grounding.** The log has no "aground" line. The boat never went further south than about -2,177 N; the earlier soaks grounded at -2,519 N, 75 E, about 340 m further south.
  - She sailed 99-114 m a minute in every logged minute except one (52 m at 1,800 s, turning).
  - The end screenshot: 5.1 kn on a broad reach, depth 42 ft (keel 3.8, alarm 5.8), heading 287 °T, well off the shore on the minimap.
- **The guard fired 8 times**, alternating sides (`dev/log-excerpt.txt`):

```
Demo: shallow water ahead at -2109 N -601 E (t 1638 s), bearing away to TWA 150
Demo: shallow water ahead at -2177 N -392 E (t 1915 s), bearing away to TWA -150
Demo: shallow water ahead at -2072 N -683 E (t 2205 s), bearing away to TWA 150
Demo: shallow water ahead at -2107 N -530 E (t 2491 s), bearing away to TWA -150
Demo: shallow water ahead at -2119 N -644 E (t 2791 s), bearing away to TWA 150
Demo: shallow water ahead at -2134 N -473 E (t 3091 s), bearing away to TWA -150
Demo: shallow water ahead at -2088 N -654 E (t 3355 s), bearing away to TWA -150
Demo: shallow water ahead at -2069 N -810 E (t 3596 s), bearing away to TWA -150
```

- **Telemetry:** `dev/telemetry-per-minute.csv` has position and metres moved each minute, from the bench's per-minute line. The game doesn't log depth each minute; the depth at the end is from the HUD in the screenshot.

## Frame time

| | |
|---|---|
| fps | 69.5 mean (14.40 ms), median 14.10 ms, p99 **21.59 ms**; per 10 minutes 64.8, 71.0, 69.5, 69.8, 72.0, 69.6 |
| Frames over 30 ms per 10 min | **20, 2, 3, 6, 4, 3** (+1 in the shutdown second) |
| Frames over 100 ms | 1 in play: **166.7 ms at 62.7 s** (game 166 ms, render 150 ms), in the first minute; plus the shutdown frame (312 ms) |
| Crashes | none (the two frame-0 engine handled ensures, as in every run) |
| Memory | working set 3,386 MB at minute 10, 3,424 MB at minute 59; private 9,211 and 9,285 MB. Flat. |

**Against the grounded soaks:**

- The 4K and 1080p traced runs had 88-490 frames over 30 ms per 10 minutes once aground, with game-thread frames up to 174 ms. Here the boat stays off the shore and every 10-minute block after the first has 2-6.
- The first block's 20 include the 166.7 ms frame at 62.7 s. That is about when the 1080p traced run had its first-use font load (sailing-feedback #33), though this run has no trace to confirm it.

## Files

- `dev/bench.json`, `dev/crashes.txt`, `dev/ensures.txt`
- `dev/log-excerpt.txt`: the shoal lines and the per-minute bench lines
- `dev/telemetry-per-minute.csv`
- `dev/fps-per-minute.csv`, `dev/frames-over-30ms.csv`, `dev/frames-over-250ms.csv`
- `dev-memory.csv`
- `dev/soak-808.png`: the end screenshot
