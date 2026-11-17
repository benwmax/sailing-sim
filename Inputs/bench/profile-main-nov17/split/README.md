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
