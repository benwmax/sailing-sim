# Galveston Bay soak, main 8a768667 (Dev package Windows-8a768667), Nov 17-18 2026

One hour on Bean's PC (RTX 4090), Development build, 1920x1080 windowed, Ultra, 100% screen percentage, autopilot demo.
Args: `-SailingBench=3600 -windowed -ResX=1920 -ResY=1080 -SailingShot=soak-galveston -SailingQuality=Ultra
-SailingWorld=1 -SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingScreenPct=100`. Bean's Saved was held aside
and restored afterwards (profile hash checked).

Ran 22:59:18 to 00:00:30 local (61 min). The launcher exited 0 and the game wrote bench.json.

## Result

| | |
|---|---|
| Crashes | **none**. The two crash folders are the two handled-ensure reports at frame 0 (CrashType Ensure). |
| Ensures | 2, both at frame 0, both engine code: `PSOPrecache.cpp:296` (`bPSOPrecacheCalled`) and `DoubleFloat.cpp:19` (`OriginX <= OriginMax`, from `FDistanceFieldSceneData::UpdateDistanceFieldObjectBuffers`). No asserts or fatals. |
| Frames | 243,099 over 3,601 s after the 3 s warm-up |
| fps | mean **67.5** (14.81 ms), median 14.48 ms |
| p99 | **21.77 ms** |
| Frames over 250 ms | **2**: 352 ms at 2,890 s (render thread 358 ms, GPU 10 ms; nothing in the log there) and 315 ms at 3,603 s (shutdown) |
| Frames over 30 ms | 10 (`dev/frames-over-30ms.csv`) |
| Memory (working set) | 3,841 MB at minute 1, 3,722 MB at minute 60, peak 3,841 MB. Private 10,534 MB at minute 1, 10,384 MB at minute 60. **No growth.** |
| Threads | 80-82 throughout |
| Sentry | not configured in a Dev package ("DSN is not configured"); no events |

fps by ten minutes: 65.7, 68.7, 68.0, 67.3, 67.5, 67.8.

## The boat went aground at minute 11

The demo autopilot sailed south from the launch spot at about 1.8 kn (100-118 m per minute), then stopped at
about -1,400 N 1,190 E between 600 s and 660 s. It stayed there, within 1 m a minute, for the remaining 50 minutes.
The end screenshot shows depth 4 ft against a keel of 3.8 ft (alarm 5.8 ft), speed 0.0 kn, GPS 0.3 kn, on the minimap
just off the shore. The log does not name the cause (it has no grounding line).

So minutes 11 to 60 measure a boat sitting still on Galveston's west-side shallows, not one sailing the bay.
The memory and crash results hold for that hour; the fps of a sailing boat is minutes 0-10 (65.7 fps).
If a moving soak is wanted, a launch spot or a demo course that stays in deep water is needed.

## Also seen

The Dev build prints an on-screen engine warning on the end screenshot: "RAY TRACING GEOMETRY - ALWAYS RESIDENT
MEMORY EXCEEDS 20% OF THE BUDGET (88.816 MiB / 400 MiB)". It is a Development-only message (not in Shipping).

## Files

- `dev/bench.json`: the game's own result (game-thread slices, GPU slices, memory)
- `dev-memory.csv`: working set and private bytes each minute (from outside the game)
- `dev/fps-per-minute.csv`, `dev/frames-over-30ms.csv`, `dev/frames-over-250ms.csv`: from `soak-galveston.frames.csv`
  (10 MB, kept on the PC in `Artifacts/bench/soak-8a768667-galveston/dev/`, with game.log and the minidumps)
- `dev/crashes.txt`, `dev/ensures.txt`, `dev/crash-*/CrashContext.runtime-xml`
- `dev/soak-galveston.png`: the end screenshot
