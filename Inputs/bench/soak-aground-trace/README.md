# Traced aground rerun, main 8a768667 (Dev package Windows-8a768667), Nov 18 2026

The 4K soak's demo course again, to see whether its second-hour game-thread hitches come from the grounding or the sunset.
See sailing-feedback #31 and `../soak-8a768667-4k/`.

**Setup:**

- Bean's PC (RTX 4090), Development build, **1920x1080** windowed (the 4K soak ran at 3840x2160), Ultra, 100% screen percentage. Ray Hubbard, launch 1, autopilot demo, game clock from **15:00** (the 4K soak's launch hour, from its session line). 90 minutes.
- **Args:** `-SailingBench=5400 -windowed -ResX=1920 -ResY=1080 -SailingShot=soak-aground -SailingQuality=Ultra -SailingWorld=Lake
-SailingLaunch=1 -SailingDemo -SailingBenchTrace -SailingScreenPct=100 -SailingHour=15 -trace=cpu,frame -statnamedevents
-tracefile=<run folder>\aground.utrace`.
- **Saved:** Bean's Saved was held aside and restored (profile hash checked).
- **Run:** 05:18:16 to 06:48:32 local. The game log ends with a normal "Exiting."; the launcher's exit code was 777003.

## Result

| | |
|---|---|
| Crashes | none (the two frame-0 engine handled ensures, as in the other soaks: PSOPrecache, DoubleFloat OriginMax) |
| fps | mean 69.1 (14.47 ms), median 14.25 ms, p99 19.45 ms. Every 10-minute block is 66.5 to 70.4 fps. |
| Memory | working set 3,392 MB at minute 1 and 3,390 MB at minute 89; private 9,631 and 9,695 MB. No growth. |
| Trace | `aground.utrace`, 35.3 GB, kept on the PC (`Artifacts/bench/soak-aground-trace/`), not pushed |

## Where it grounded

The same course as the 4K soak:

- **0 to 1,500 s:** the boat sailed south at 100-111 m a minute.
- **1,800 to 2,700 s:** it slowed along the south shore (35-57 m a minute).
- **By 3,000 s:** it was at **-2,518.9 N, 79.0 E**, the 4K soak's grounding spot. It stayed within about 30 m of there to the end, shuffling 3 to 35 m a minute.
- **When, on the game clock:** about 15:50, with sunset at 17:24. The run ended at 16:30.
- **End screenshot:** `dev/soak-aground.png`.

In the 4K soak, the boat reached the same spot later, between 3,000 and 3,600 s.

## Hitches: sailing against aground

Frames over 30 ms per 10 minutes (`dev/frames-over-30ms.csv`). 851 of the 864 have the game thread longer than the render thread.

| Minutes | Boat | Over 30 ms |
|---|---|---|
| 0-10 | sailing | 4 |
| 10-20 | sailing | 3 |
| 20-30 | sailing | 7 |
| 30-40 | slowing along the shore | **59**: a cluster at 2,103-2,108 s, 60-100 ms frames (game 43-61 ms) |
| 40-50 | at the shore | 1 |
| 50-60 | aground from about 3,000 s | 24 |
| 60-70 | aground | **352** |
| 70-80 | aground | 78 |
| 80-90 | aground | **329** |
| 90 | the last 4 s and the shutdown | 7 |

**Frames over 100 ms:**

- 122.8 ms at 3,841.3 s (game 121.3 ms)
- 174.4 ms at 5,125.6 s (game 173.4 ms)
- the shutdown frame, 300 ms at 5,403 s (game 9.6 ms)

**What this shows:**

- The hitches start when the boat reaches the shore and come in bursts while it sits there, as in the 4K soak.
- **Sunset is ruled out.** The game clock was 15:50 to 16:30 for the aground part, at least an hour before sunset (17:24), and the bursts are just as bad.
- **Resolution is ruled out.** The pattern holds at 1080p, so it isn't a 4K render cost: almost every slow frame is the game thread, with the GPU at 8-9 ms.

## The Insights breakdown did not complete

The plan was to name the top game-thread scopes in the >100 ms frames with headless Unreal Insights:

- `TimingInsights.ExportTimingEvents` on the game thread in windows around 2,105, 3,841, 4,860 and 5,125 s.
- `ExportTimerStatistics` for sailing against aground.

**Neither attempt exported anything:**

- The trace holds 1.61 billion CPU scopes (11.2 GB of scope data) on 53 threads.
- **First attempt:** Insights ended after 5 minutes with no log and no output.
- **Second attempt:** after 5 minutes it reported "High System Memory Usage Detected: 51 / 64 GiB (80%)" in a Slate window. The engine then exited ("Normal Slate Window Closed") before the exports ran. Peak working set was 37.7 GB.

A 90-minute `-statnamedevents` trace is too large for Insights on this 64 GB PC.

**Ways to get the scopes (not run, they need an OK):**

1. **A short traced run that starts beside the grounding spot.** For example, `-SailingStartAt` a few hundred metres north of -2,519 N 79 E heading for the shore. It would ground within minutes; trace 15-20 minutes of it. The trace would be about 6 GB, which Insights handles.
2. **The same course with tracing started late.** `-trace=` off at launch, then `Trace.Start cpu,frame` over the trace control port (1985) at about 2,900 s.
3. **The same course without `-statnamedevents`.** Fewer scopes, but the game's stat-named scopes would be missing.

## Files

- `dev/bench.json`: the game's own result
- `dev-memory.csv`: working set and private MB each minute
- `dev/fps-per-minute.csv`, `dev/frames-over-30ms.csv`, `dev/frames-over-250ms.csv`: from `soak-aground.frames.csv`. That file is 16 MB and kept on the PC with game.log and the minidumps.
- `dev/crashes.txt`, `dev/ensures.txt`, `dev/crash-*/CrashContext.runtime-xml`
- `dev/soak-aground.png`: the end screenshot

## Short traced run beside the grounding spot (Nov 18 07:02-07:23)

**Setup:**

- **Settings:** the same build and settings (Dev `Windows-8a768667`, Ultra 1080p, `-SailingDemo -SailingHour=15`, `-trace=cpu,frame -statnamedevents`), with `-SailingStartAt=-2219,79,135` (300 m north of the spot) and `-SailingBench=1200`.
- **Trace:** `aground-short.utrace`, 5.9 GB, kept on the PC.
- **Saved:** Bean's Saved was held aside and restored (profile hash checked).

**Grounding:** the boat sailed south at about 100 m a minute and **grounded at about 200 s** (-2,517 N 96 E at 180 s, 5.8 m in the next minute). It stayed within about 30 m of the 4K soak's spot to the end, shuffling 3 to 40 m a minute.

**Result:**

- 68.7 fps, p99 20.2 ms, no crashes.
- Frames over 30 ms (`short/frames-over-30ms.csv`): 11 in the 200 s sailing, 16 in the 1,000 s aground. Of the 16, 9 are one event at 598-600 s and 1 is the shutdown.
- **This run did not reproduce the bursts.** The long runs had 300 to 500 slow frames per 10 minutes aground; this one had about 6 in 17 minutes aground, outside the 598 s event.
- In the long runs the bursts began 10 to 20 minutes after the boat reached the spot (1080p: grounded by 3,000 s, bursts at 3,600-4,200 and 4,800-5,400 s). So 17 minutes aground may simply be too short.

**Insights export:** it worked this time, with a 30 GB peak and 4 minutes. It exported the game thread around every frame over 50 ms, plus timer statistics for the sailing and aground parts (`short/stats-*.csv`).

**The frames over 100 ms:**

**1. 598.8 s: 921 ms (with a 129 ms frame before and an 81 ms frame after).**

- Its top self times: `Frame Sync Time` 686.6 ms (the game thread waiting on the render thread: Sync_RenderingThread), `ProcessLocalPlayerSlateOperations` 167.4 ms, `Slate::DrawWindow` 32 ms, plus `QueryCursor` and `STAT_IsCursorDirectlyOverSlateWindow`.
- The frame before: `ProcessLocalPlayerSlateOperations` 65.9 ms.
- The frames after: `Sailing_WaterUploads` 21.6 ms and 28.2 ms, and `Sailing_BoatLearning` 10.4 ms.
- **Reading:** Slate window, focus and cursor work plus a long render-thread wait. This looks like something happening to the game window on the desktop at 07:12:46 local, not the boat. It is not the grounding pattern. The long runs' slow frames were game-thread work with no render wait.

**2. 64.4 s (sailing, before the grounding): 97.6 ms, then a 127 ms game-thread frame.**

- `Load Font` 83.5 ms self, under `SBox [SailHud.cpp(1010)] > Text Layout`.
- **Reading:** a font loaded the first time a HUD text was drawn. A first-use hitch, not the grounding.

**Game-thread cost per frame, sailing against aground (inclusive ms per frame, and the worst single call):**

| Scope | Sailing per frame | Aground per frame | Sailing worst | Aground worst |
|---|---|---|---|---|
| Sailing_BoatVisuals | 4.02 | 3.23 | 7.7 | 7.6 |
| Sailing_Water | 1.95 | 1.81 | 35.2 | 35.0 |
| Sailing_RigLines | 1.93 | 1.67 | 6.5 | 5.1 |
| Sailing_Traffic | 1.31 | 1.09 | 9.2 | 9.0 |
| Sailing_BoatPhysics | 0.45 | 0.32 | 3.4 | **10.6** |
| Sailing_BoatLearning | 0.03 | 0.07 | 1.2 | **15.1** |
| Sailing_WaterUploads | 0.39 | 0.35 | 34.2 | 33.7 |

Aground, nothing costs more per frame. The only scopes whose worst call grows are the boat's physics (10.6 ms against 3.4) and the learning coach (15.1 ms against 1.2). The aground tip fires there.

**Verdict:**

- The short run confirms the grounding spot and the course. It does not catch the bursts, so it names no system for them.
- The 4K and 1080p long runs still show the bursts only while aground.
- **Candidates from this trace:** the boat physics' and the learning coach's occasional long calls aground. They are too small and rare here to make 60 to 170 ms frames.
- **Next way to catch them (not run):** trace a long aground stretch with tracing started late. For example: the same start, `-trace=` off, `Trace.Start cpu,frame` over the trace control port after 15 minutes, then 20 minutes traced.
