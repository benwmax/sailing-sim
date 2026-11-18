# 4K Lake soak, main 8a768667 (Dev package Windows-8a768667), Nov 18 2026

A two-hour run on Bean's PC (RTX 4090):

- **Build:** Development, 3840x2160 windowed (`-ForceRes`), Ultra, 100% screen percentage, Ray Hubbard, launch 1, autopilot demo.
- **Args:** `-SailingBench=7200 -windowed -ResX=3840 -ResY=2160 -ForceRes -SailingShot=soak-4k -SailingQuality=Ultra
-SailingWorld=Lake -SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingScreenPct=100`.
- **Saved:** Bean's Saved was held aside and restored afterwards (profile hash checked).
- **Run:** 00:19:47 to 02:20:08 local (120 min). The launcher exited 0 and the game wrote bench.json.

## Result

| | |
|---|---|
| Crashes | **none**. The two crash folders are the frame-0 handled-ensure reports (CrashType Ensure), the same two as in the Galveston soak. |
| Ensures | 2, both at frame 0, both engine code: `PSOPrecache.cpp:296` and `DoubleFloat.cpp:19` (`OriginX <= OriginMax`). No asserts or fatals. |
| Frames | 389,759 over 7,201 s after the 3 s warm-up |
| fps | mean **54.1** (18.48 ms), median 18.32 ms; every 10-minute block 53.3 to 54.6 |
| p99 | **23.46 ms** |
| GPU | 17.87 ms per frame. The slices are clouds and fog 3.66, base 4.23, post 2.42, Lumen 1.40, water 1.05. |
| Frames over 250 ms | **1**: 1,061 ms at 7,203 s, the shutdown (the measured max in bench.json is 181.7 ms) |
| Frames over 100 ms | 7, all after minute 70, all on the game thread |
| Frames over 30 ms | 1,888 (`dev/frames-over-30ms.csv`). 1,867 of them have game_ms above render_ms. |
| Memory (working set) | 4,225 MB at minute 1, then 3,652 MB at minute 10, 3,737 MB at minute 60 and 3,781 MB at minute 119. |
| Memory (private) | 14,846 MB at minute 1, 14,271 MB at minute 10 and 14,461 MB at minute 119. **No growth** after the first minutes. |
| Threads | 80-83 |

## Game-thread hitches in the second hour, with the boat aground

Frames over 30 ms by ten minutes: 1, 5, 1, 6, 3, 10, **88, 490, 333, 297, 311, 201** (plus 142 in the last minute and the shutdown).
Almost all are game-thread frames. The worst are 60 to 167 ms, for example at 5,346.7 s (167 ms) and 5,384.6 s (133 ms), while the GPU stays at 17-19 ms.

**What the boat did:** the demo boat sailed south down the lake (about 100 m a minute to 1,200 s). It slowed against the south shore from about 1,800 s and reached -2,510 N 42 E by 3,600 s. From then it stayed within about 25 m of -2,518 N 75 E for the last hour (8 to 40 m a minute of shuffling).

**End screenshot:**

- The boat is on the bank, with the Learning tip "Safety: Aground" and the HUD's "Shallow water ahead".
- Depth reads 6 ft (keel 3.8 ft) at 0.6 kn, 242 °T.
- The sun is near setting: 17:00, with sunset at 17:24.

The hitches start with the grounding and go on for as long as the boat sits on the shore, so the grounding is the likely cause. The run doesn't show it directly: the log has no grounding line, and no trace was taken. The sun going down over the same hour is the other thing that changed.

The fps of a sailing boat at 4K is the first 50 minutes: 53.3 to 54.6 per ten minutes, with 1 to 10 frames over 30 ms per ten minutes.

This is the second soak in a night where the demo autopilot ran aground; the Galveston one is sailing-feedback #31.

## Files

- `dev/bench.json`: the game's own result
- `dev-memory.csv`: working set and private MB each minute, from outside the game
- `dev/fps-per-minute.csv`, `dev/frames-over-30ms.csv`, `dev/frames-over-250ms.csv`: from `soak-4k.frames.csv`. That file is 17 MB and kept on the PC in `Artifacts/bench/soak-8a768667-4k/dev/`, with game.log and the minidumps.
- `dev/crashes.txt`, `dev/ensures.txt`, `dev/crash-*/CrashContext.runtime-xml`
- `dev/soak-4k.png`: the end screenshot (3840x2160)
