# Storm hitches on da3e74b0: what they are and what to fix

Storm view, 4K Ultra fullscreen, Development packages on the PC, warm runs. Unreal Insights CPU traces
(`-trace=cpu,frame,bookmark -statnamedevents`; the .utrace files, 97-182 MB, stay on the PC), GameThread timing events
exported headless (`TimingInsights.ExportTimingEvents ... -columns=ThreadId,TimerName,StartTime,EndTime,Duration,Depth`).
Traces: one 12 s run on da3e74b0 (run 1), then 30 s runs on 2f8e31f6, da3e74b0, 2f8e31f6. Line numbers are at da3e74b0.

## Three causes

### 1. Far-cap tiles rebuilt all at once (`AWaterSurface::UpdateFarCaps`, WaterSurface.cpp:1451, called at 825)
The 28-106 ms `Sailing_Water` frames that are not item 2 each hold about 29-31 tile rebuilds:
- `ConstructObject` 58-62 times
- `RegisterComponent` / `OnRegister` 29-31 times
- `UInstancedStaticMeshComponent::AddInstancesInternal` 29-31 times (5-9 ms)
- `UPrimitiveComponent::PrecachePSOs` 58-62 times (1,032 on one frame)
- 20-24 ms of self time: the per-slot loop with up to five `Terrain->HeightAt` calls each (1590-1594)

That is `NewObject<UInstancedStaticMeshComponent>` (1558), `RegisterComponent` (1580) and `AddInstances` (1603) for every
tile in view, in one frame. Every tile rebuilds when `SizeStep` moves (`Tile->Size != SizeStep`, 1545).

`SizeStep` is the quarter-stepped "fewer, bigger caps" factor that applies once the planned slots pass `FarCapBudget`
(1536-1537). In a storm the cover sits above the budget, so as it wanders across a quarter boundary at a replan (every
0.5 s or an 8 deg turn, 1477), the whole cone of tiles (about 30) is rebuilt at once. Spray (one ISM made once, 1677),
drips, the bow wave and the wake are not in these frames.

### 2. Wave-detail reconfigure on the game thread (`AWaterSurface::UpdateDetail`, 831; scope `Sailing_WaterUploads` at 817)
The 26-39 ms `Sailing_WaterUploads` frames are all self time; their only child is one `UTexture2D::UpdateResource` of
0.16 ms. They are not a texture upload. They are the reconfigure:
- When `bReconfigure` trips (wind more than 0.25 m/s, direction 0.05 rad, fetch 10 % or development 30 % off the
  configured, 857-858), the game thread runs `New->Configure(P, Specs)` for four cascades (870-874).
- The frames are then reset, so it evaluates two full detail frames itself:
  `FramePrev = Evaluate(T0); FrameNext = Evaluate(T0 + kDetailStep)` (899-902).

### 3. The session log's flush every line (`SailSessionLog::Write` -> `Raw`, SessionLog.cpp:109 / 47-61)
`FarLightsActor`'s 16-103 ms ticks fall exactly 5.0 s apart and each holds one `STAT_FMsgLogf`. That is its every-5-s
`SAIL_LOG(Display, "Far lights: ...")` (FarLightsActor.cpp:275-279).

`SAIL_LOG` also writes the session log, and `Raw` does `File->Write` then `File->Flush()` on every line, on the game
thread, under the log's lock. A flush to disk while the bench writes its frames and the trace streams costs 16-103 ms.
Any game-thread `SAIL_LOG(Display/Warning/Error)` can hitch the same way; the far-lights line is simply the one that
fires every 5 s.

## Item 3: #677 made it worse, it didn't create it

These are 30 s storm traces in the measured window. Spike sizes are in ms; "/29t" means the frame rebuilt 29 far-cap
tiles. Per-frame lists are in `hitch-compare.csv`.

| | 2f8e31f6 (i2) | 2f8e31f6 (i4) | da3e74b0 (i3) |
|---|---|---|---|
| game-thread frames > 40 ms | 19 | 17 | 27 |
| `Sailing_Water` median | 2.0 ms | 2.0 ms | 4.2 ms |
| `Sailing_Water` > 15 ms | 16 | 13 | 32 |
| far-cap rebuild spikes (~29 tiles) | 9 | 9 | 5 of the top 14 |
| reconfigure spikes (`Sailing_WaterUploads` > 15 ms) | 5 | 4 | 10 |
| `FarLightsActor` > 10 ms | 1 (103 ms) | 3 (66, 66, 23 ms) | 1 (16 ms) |

The 12 s run 1 on da3e74b0 had 5 reconfigure spikes and `FarLightsActor` 96 and 54 ms.

All three mechanisms are on 2f8e31f6 too. #677 doubles the reconfigures: its bigger storm sea under the outflow and burst
moves `WindMs` and `Development` past the thresholds twice as often. It also doubles `Sailing_Water`'s median (2.0 to
4.2 ms, a steady part of storm's +2.7 ms game thread). The far-cap rebuilds stay at about one every 3-4 s on both builds.
The log flush is unchanged by #677.

## Item 4: FarLightsActor
It repeats on every run on both builds, every 5.0 s exactly (13.96 -> 18.97 s; 13.55 -> 18.57 s). The call is the
`SAIL_LOG` at FarLightsActor.cpp:278, and inside it the session log's per-line `Flush()` (SessionLog.cpp:55/60).
Nothing in `UpdateLights`, `UpdateShore` or `UpdateShips` shows up in those frames.

## Proposed fixes

**Session log (cause 3, any SAIL_LOG on the game thread)**
- In `SailSessionLog::Write` / `Raw`, drop the per-line `File->Flush()`. Buffer lines and flush from a background task
  (say every second), and at once only for Warning, Error and Fatal and at exit or crash.
  `SailCrashReports` already flushes `GLog` on a crash (CrashReports.cpp:69): add the session log there.
- Alternatively move the write itself to a worker queue.
- Also make the far-lights status line `UE_LOG(LogSailing, Log, ...)` or Verbose. It is diagnostics; at Log level it
  stays out of the session log.

**Far caps (cause 1)**
- In `UpdateFarCaps`, never rebuild every tile on one replan:
  - Give `SizeStep` hysteresis, so it changes only when the planned total is past the next quarter by a margin, and
    holds for a few seconds.
  - Cap the rebuilds per replan to a few tiles (nearest or most-changed first), carrying the rest to the next replan.
  - Reuse a tile's component instead of DestroyComponent + NewObject + RegisterComponent: `ClearInstances` plus
    `AddInstances`, or `BatchUpdateInstancesTransforms` when the slot count is unchanged and only the size steps. Better
    still, put the cap size in per-instance custom data or a material parameter, so a `SizeStep` change needs no rebuild.
- Move the per-slot placement (positions, seeds and the five `HeightAt` checks, 1585-1600) to a worker that returns the
  transform arrays, leaving the game thread only `AddInstances`.

**Wave detail reconfigure (cause 2)**
- Configure the new `FWaveDetail` and evaluate its first two frames on a worker, as `PendingFrame` already does for later
  frames. Keep drawing the old detail until the new one is ready, then swap in one frame (`Detail`, `FramePrev`,
  `FrameNext` together).
- Also widen the thresholds under a building storm sea, or blend between configurations, so a ramping storm wind
  reconfigures less often.
