# Crew view: splitting UpdateSection RT by source (main 687f777c, PC)

## Setup

- **Build:** `Packaged/Windows-687f777c`. All runs are bench-visual's `crew` view at Ultra 1920x1080, with `-SailingScreenPct=100 -SailingBenchTrace -SailingDemo`, 12 s each, back to back in one session.
- **Crew setting:** the view's `-SailingShowCrew=1` was replaced by each run's own setting.
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Files:** each run's `bench.json` and `frames.csv`, and `runs.csv` with the exact args.

| Run | Flags | fps | p99 ms | game ms | render ms | RHI ms | GPU frame | GPU total | base | lumen | water | clouds/fog | niagara | post | other | foreground |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a-default | `-SailingShowCrew=1 -SailingScreenPct=100 -SailingBenchTrace` | 49.1 | 25.6 | 14.82 | 20.36 | 9.01 | 11.49 | 8.39 | 3.79 | 0.97 | 0.39 | 0.93 | 0.01 | 0.74 | 1.57 | 0 |
| b-classicropes | `-SailingShowCrew=1 -SailingClassicRopes -SailingScreenPct=100 -SailingBenchTrace` | 48.1 | 25.38 | 13.89 | 20.78 | 9.32 | 11.48 | 8.46 | 3.91 | 0.97 | 0.39 | 0.93 | 0.01 | 0.73 | 1.52 | 0 |
| c-nocoils | `-SailingShowCrew=1 -SailingNoCoils -SailingScreenPct=100 -SailingBenchTrace` | 47.2 | 26.14 | 15.17 | 21.16 | 9.24 | 11.47 | 8.83 | 3.92 | 0.98 | 0.4 | 1.02 | 0.01 | 0.73 | 1.77 | 0 |
| d-flatrope | `-SailingShowCrew=1 -SailingFlatRope -SailingScreenPct=100 -SailingBenchTrace` | 47.6 | 25.85 | 15.35 | 20.99 | 9.41 | 11.51 | 8.72 | 4.04 | 1.06 | 0.45 | 0.95 | 0.01 | 0.75 | 1.46 | 0 |
| e-nocrew | `-SailingShowCrew=0 -SailingScreenPct=100 -SailingBenchTrace` | 52.7 | 23.28 | 13.56 | 18.96 | 8.49 | 9.78 | 7.59 | 3.06 | 0.76 | 0.38 | 1.05 | 0.01 | 0.78 | 1.55 | 0 |
| f-all-three | `-SailingClassicRopes -SailingNoCoils -SailingShowCrew=0 -SailingScreenPct=100 -SailingBenchTrace` | 58.7 | 21.14 | 11.59 | 17.03 | 7.75 | 9.7 | 7.6 | 3.09 | 0.76 | 0.38 | 1.11 | 0.01 | 0.77 | 1.48 | 0 |

All runs report `render_pct` 100 and `foreground: 0`: the game window was not in front, and I don't move windows or send input. The control (a) at 49.1 fps matches the profiled run's 47.7.

## Which flag buys how much

- **(b) `-SailingClassicRopes`, (c) `-SailingNoCoils` and (d) `-SailingFlatRope` each buy nothing on their own.** Each is within about 2 fps of the control, all slightly lower, and their render thread is 20.8 to 21.2 ms against the control's 20.4. With the crew shown, the laid ropes, coils and rope materials are not where the time goes.
- **(e) `-SailingShowCrew=0` buys about 3.6 fps:** 52.7. Game thread -1.3 ms, render -1.4, RHI -0.5, GPU total -0.8 (base -0.7).
- **(f) all three together buy about 9.6 fps:** 58.7. Game thread -3.2 ms, render -3.3, RHI -1.3, GPU about the same as (e).
  - So classic ropes and no coils save about 2 ms of game thread and 2 ms of render thread, but **only once the crew is hidden**.
  - The likely reason: with the crew shown, the laid ropes still route to the crew's hands (the helm's tiller extension and mainsheet, the trimmer's jib tail), so the laid-rope path keeps running.
  - That's a guess from the numbers, not something the trace shows directly.

## What is left in (f) (Insights trace, same window method)

I ran (f) again with `-SailingNoGpuSlices -trace=cpu,frame -statnamedevents`. The trace stays on the PC at `D:\dev\ss-fix\Artifacts\profile\crew-687f777c-f.utrace`, 110 MB.

- **Window:** the last 12 s, **11.33 to 23.33 s**, 693 frames.
- **Exports:** `f-RenderThread.csv`, `f-GameThread.csv` and `f-trace-frames.csv` (the frame events used to place the window).
- **It took about 1 minute**, well inside the 15.

- **UpdateSection RT is still there: 11,076 calls, 16.0 a frame, 4.05 ms a frame exclusive.** The control trace had 16.5 a frame and 5.3 ms.
  - **The count barely changed.** None of the three flags removes those section updates. Each update just got cheaper, about 0.25 ms against 0.32, because the sections are smaller.
  - **The game thread's side:** `UpdateSection GT` is still 1.53 ms a frame over the same 16 calls.
  - **So most of the procedural mesh churn isn't the player's ropes, coils or crew.** `Sailing_BoatVisuals` runs 4 times a frame (2,776 calls in 693 frames), meaning four boats each rebuild their visuals every frame. `Sailing_Traffic` is 1.2 ms of game thread, so AI traffic boats are in this view.
  - **Best guess:** about 4 sections per boat on 4 boats: sails and rig lines from the AI boats plus the player's sails. Telling them apart needs per-component names in the profile, or runs with `-SailingTraffic=0` and with sail cloth off.
- **The next render-thread items in (f)**, per frame (calls, inclusive ms, exclusive ms):

| Event | Calls/frame | Inclusive ms | Exclusive ms |
| --- | --- | --- | --- |
| `UpdateSection RT` | 16 | 4.18 | 4.05 |
| `WaitForTasks` | 1.4 | 1.64 | 1.64 |
| `UpdateTextureRegionsData` | 55.9 | 0.61 | 0.61 |
| `FRDGBuilder::AllocateTransientResources` | 2.9 | 0.6 | 0.59 |
| `FTaskBase::WaitImpl_StateChangeEvent_WaitFor` | 4.8 | 0.42 | 0.42 |
| `AddPass_Rasterize` | 5 | 0.48 | 0.35 |
| `Scene` | 5 | 6.9 | 0.34 |
| `FRDGBuilder::CollectResources` | 2.9 | 0.95 | 0.29 |
| `LumenReflections` | 3 | 0.28 | 0.28 |
| `NodeAndClusterCull` | 5 | 0.26 | 0.26 |
| `LumenScreenProbeGather` | 2 | 0.45 | 0.25 |
| `FWaitingQueue_Unpark_SignalWaitingThread` | 56.5 | 0.22 | 0.22 |

- **Game thread in (f):**
  - **Idle:** waiting on the render thread, 4.4 ms.
  - **Work:** `ParallelFor` tasks 3.0 ms, `UpdateSection GT` 1.5, `Sailing_Water` 1.8 inclusive, `Sailing_Traffic` 1.2 inclusive, `Sailing_Terrain` 0.9 and `Sailing_RigLines` 0.8 inclusive.
  - **Crew:** `Sailing_Crew` is 0.4 ms, still ticking with the crew hidden.

**Suggested next splits:** `-SailingTraffic=0` (AI boats off), and a run without sail cloth if a flag exists, to name the 16 updates a frame. No code changes were made.

## Second set: AI traffic off (g to j)

Same package, view and settings as above, back to back. (j) ran at `-Quality Low`, everything else at Ultra. Their rows are appended to `runs.csv`.

| Run | Flags | fps | p99 ms | game ms | render ms | RHI ms | GPU frame | GPU total | foreground |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| g-notraffic | `-SailingShowCrew=1 -SailingTraffic=0 -SailingScreenPct=100 -SailingBenchTrace` | 58.2 | 21.96 | 10.17 | 17.18 | 8.5 | 11.46 | 8.58 | 0 |
| h-notraffic-nocrew | `-SailingTraffic=0 -SailingShowCrew=0 -SailingScreenPct=100 -SailingBenchTrace` | 68.5 | 18.89 | 8.77 | 14.59 | 7.37 | 9.68 | 7.25 | 0 |
| i-notraffic-all | `-SailingTraffic=0 -SailingShowCrew=0 -SailingClassicRopes -SailingNoCoils -SailingScreenPct=100 -SailingBenchTrace` | 72.3 | 17.7 | 7.51 | 13.81 | 7.11 | 9.44 | 7.88 | 0 |
| j-low-notraffic | `-SailingShowCrew=1 -SailingTraffic=0 -SailingScreenPct=100 -SailingBenchTrace` | 121.8 | 10.9 | 5.02 | 8.2 | 4.49 | 4.14 | 3.24 | 0 |

### Which flag buys how much

- **`-SailingTraffic=0` is the biggest single win: 49.1 to 58.2 fps** (g against a). Game thread -4.7 ms, render -3.2, RHI -0.5. The AI boats (three, besides the player's) cost more than her crew does.
- **With traffic off, hiding the crew adds about 10 fps: 68.5** (h). Game -1.4 ms, render -2.6, RHI -1.1.
- **Classic ropes and no coils on top add about 4 fps: 72.3** (i). Game -1.3 ms, render -0.8.
- **Low quality, traffic off, crew shown: 121.8 fps** (j). Low changes much else (no Lumen, no cloth, cheaper shadows and water), so I compare its rebuild count, not its fps.

### What the rebuilds are

I traced (i) and (j) the same way as (f): the last 12 s before the quit, with `-SailingNoGpuSlices`. Their CSVs are `i-*.csv` and `j-*.csv`. The traces stay on the PC at `D:\dev\ss-fix\Artifacts\profile\crew-687f777c-i.utrace` and `-j.utrace`.

| Trace | Frames | UpdateSection RT calls/frame | RT ms/frame | UpdateSection GT ms/frame | Sailing_BoatVisuals calls/frame | Sailing_RigLines incl ms |
| --- | --- | --- | --- | --- | --- | --- |
| control (from the first trace) | 556 | 16.5 | 5.30 | 1.82 | 4.0 | 2.62 |
| (f) traffic on, crew off, classic ropes, no coils | 693 | 16.0 | 4.05 | 1.53 | 4.0 | 0.81 |
| (i) traffic off, crew off, classic ropes, no coils | 590 | **6.0** | **1.74** | 0.66 | **1.0** | 0.72 |
| (j) Low, traffic off, crew shown, default ropes | 1430 | **5.1** | 1.85 | 0.45 | 1.0 | 1.17 |

- **The AI traffic boats account for about 10 of the 16 rebuilds a frame.**
  - **The evidence:** `Sailing_BoatVisuals` drops from 4 calls a frame to 1, and UpdateSection RT from 16 to 6 a frame (from 4.05 to 1.74 ms).
  - **Per boat:** each AI boat rebuilds about 3 to 4 procedural sections every frame, its rig lines and sails.
- **The player's boat alone rebuilds about 6 sections a frame** at Ultra, with the crew hidden and classic ropes.
  - **At Low (j), without sail cloth,** it's about 5 a frame, even with the crew shown and the default laid ropes.
  - **So sail cloth is about 1 of the player's ~6 sections.** The rest are the rig-line sections (`Sailing_RigLines`, 0.7 to 1.2 ms of game thread), rebuilt every frame.
  - **Caveat:** (j) also differs from (i) in crew and ropes, so the cloth's share is approximate.
- **After traffic, crew and ropes, (i)'s render thread is about 13.8 ms**, and UpdateSection RT is now only its second-biggest item (1.74 ms). The top items are:
  - `WaitForTasks` 2.4 ms
  - the RDG builder (allocation 1.0, collection 0.5)
  - texture-region uploads 0.9

**In short:** in this view, AI traffic is the largest cost (about 9 fps), then the MetaHuman crew, then the laid ropes and coils. Most of the procedural-mesh churn is the traffic boats' rig lines and sails, rebuilt every frame, about 3 to 4 sections a boat. The player's own boat rebuilds about 6 a frame, about 5 of them rig lines and about 1 sail cloth.
