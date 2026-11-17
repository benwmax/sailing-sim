# #787 follow-up: splitting the 16-view drop (PC, Nov 17)

**Result: no measurable cost from #787.**

- **This session's 16 views:** 86c83fc averages **70.9 fps** against **70.2** for current main (**424b580b**).
- **Storm and helm-eye:** with `-SailingClassicClock` (the whole change off), 86c83fc gives 70.7 and 70.2 fps, the same as with the change on (70.8 and 70.8).
- **Insights, helm-eye game thread:** identical work. No #787-related scope differs by more than 0.05 ms per frame.
- **The tack hitches** are on main and with `-SailingClassicClock` too, so they are not from #787.
- **The earlier storm -9.8 and helm-eye -8.1 against ecd4ed1c** don't reproduce. Per-view run-to-run spread between two packages is several fps here (beam8 +8.1, storm +6.3, stream-run -3.8). Read single-view gaps of that size as noise.

## Setup

- **Main package:** origin/main's tip at run time was **424b580b**. Built in a fresh worktree (`D:\dev\ss-fix-wt\prmain-424b580b`, removed afterwards; MSVC clean), Development package to the new `Packaged/Windows-424b580b` (kept), warmed once.
- **First try lost its package:** the first try at 15:47 built and packaged the same commit, but a bug in my post-step script lost the package before any run.
- **Bean's Saved:** held aside for every run, restored with the profile hash checked (B57AA3AF).
- **Foreground: 1 on every run in this session**, the window in front, unlike the 0 of the earlier runs today. I sent no input. All the comparisons below are within this session, so they are like for like.

## 1. 16-view Ultra 1080p (`bench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100'`)

- **Order:** Windows-86c83fc, then Windows-424b580b, back to back. Then 86c83fc with `-SailingClassicClock` on storm and helm-eye only (`-Only storm,helm-eye`).

| View | fps 86c83fc | fps 86c83fc ClassicClock | fps main 424b580b | 86c83fc - main | game ms (787 / main) | render ms (787 / main) | GPU ms (787 / main) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| beam8 | 71.9 |  | 63.8 | 8.1 | 10.18 / 11.28 | 13.9 / 15.67 | 6.91 / 6.86 |
| beat15 | 67.1 |  | 61.6 | 5.5 | 11.18 / 12.73 | 14.84 / 16.18 | 7.58 / 7.72 |
| storm | 70.8 | 70.7 | 64.5 | 6.3 | 12.26 / 14.26 | 14.07 / 15.39 | 7.33 / 7.43 |
| marina | 69.8 |  | 70.3 | -0.5 | 9.79 / 9.78 | 14.31 / 14.21 | 7.69 / 7.11 |
| coast-day | 67.3 |  | 69.9 | -2.6 | 11.28 / 10.96 | 14.84 / 14.29 | 7.65 / 7.72 |
| coast-night | 74.7 |  | 69.4 | 5.3 | 10.56 / 11.78 | 13.36 / 14.38 | 7.29 / 7.5 |
| gulf-sea | 73.5 |  | 71.4 | 2.1 | 10.61 / 11.04 | 13.57 / 13.98 | 6.4 / 6.32 |
| helm-eye | 70.8 | 70.2 | 72.5 | -1.7 | 9.86 / 10.06 | 13.78 / 13.7 | 7.36 / 7.46 |
| slip | 78.6 |  | 77.3 | 1.3 | 9.62 / 9.49 | 12.7 / 12.92 | 7.57 / 7.54 |
| bridge | 71.9 |  | 73.5 | -1.6 | 9.84 / 9.92 | 13.9 / 13.59 | 6.7 / 6.74 |
| crew | 59.7 |  | 61.7 | -2 | 11.08 / 10.95 | 16.75 / 16.2 | 8.99 / 9.04 |
| marina-night | 85.3 |  | 85.7 | -0.4 | 8.18 / 8.14 | 11.71 / 11.65 | 7.37 / 7.24 |
| far-coast | 66.9 |  | 68.9 | -2 | 11.71 / 11.68 | 14.93 / 14.49 | 7.04 / 6.85 |
| far-coast-night | 75.5 |  | 76 | -0.5 | 11.09 / 11.15 | 13.21 / 13.13 | 5.49 / 5.48 |
| marseille-port | 68.6 |  | 70.5 | -1.9 | 11.19 / 10.84 | 14.57 / 14.18 | 7.47 / 7.91 |
| stream-run | 62 |  | 65.8 | -3.8 | 13.12 / 11.98 | 16.1 / 15.17 | 8.24 / 8.19 |

- **Means:** 86c83fc **70.9** fps, main 424b580b **70.2**.
- **Storm and helm-eye with ClassicClock:** 70.7 and 70.2. Within 0.6 fps of 86c83fc as is (70.8, 70.8), so the time math costs nothing measurable.
- **Against main:** storm is 6.3 fps *faster* on 86c83fc, and helm-eye 1.7 slower. Both are inside the spread seen elsewhere in this table.
- **Files:** `visual-*/` hold each run's CSV and the bench.json per view.

## 2. Tack hitches: High 1080p helm-eye `-SailingDemo`, `-SailingBenchTrace`, 20 s

- **Order:** 86c83fc as is, 86c83fc `-SailingClassicClock`, main 424b580b, back to back.
- **Files:** `tack/*.frames.csv`, `tack/args.csv`.
- **The table:** every frame over 50 ms in the measured window (3-23 s of trace time). Each run's final frame at about 23.3 s (300 ms or more) is the bench's own screenshot and profile capture, so it is left out.

| Run | When | frame ms | game ms | render ms | GPU ms |
| --- | --- | --- | --- | --- | --- |
| 86c83fc as is | 5.62 s | 125.9 | 124.8 | 11.5 | 5.8 |
| 86c83fc as is | 19.79 s | 67.9 | 67.6 | 10.4 | 6.1 |
| 86c83fc -SailingClassicClock | 10.93 s | 140.5 | 140.5 | 12.1 | 6 |
| 86c83fc -SailingClassicClock | 12.56 s | 59.7 | 59.5 | 12.4 | 5.9 |
| main 424b580b | 10.56 s | 85.4 | 85 | 10.8 | 5.6 |
| main 424b580b | 16.99 s | 124.8 | 124.4 | 13 | 6.3 |
| main 424b580b | 18.59 s | 59.5 | 58.7 | 11.3 | 6.2 |

| Run | mean ms | median ms | p99 ms | fps |
| --- | --- | --- | --- | --- |
| 86c83fc as is | 13.21 | 12.69 | 17.46 | 75.7 |
| 86c83fc ClassicClock | 13.44 | 12.94 | 17.65 | 74.4 |
| main 424b580b | 13.30 | 12.81 | 17.73 | 75.2 |

- **What they are:** all game-thread spikes (render, RHI and GPU normal), 2-3 per run at different times, on all three builds.
- **Where they come from:** not #787. A game-thread trace through the tack would find their source.

## 3. Unreal Insights: helm-eye, game thread, main against 86c83fc

- **Runs:** each package's helm-eye view (bench-visual's args, `-Demo`, Ultra 1080p, 20 s, `-SailingScreenPct=100 -SailingNoGpuSlices`) with `-trace=cpu,frame -statnamedevents -tracefile=<abs>`.
- **Export:** headless UnrealInsights (`-NoUI -AutoQuit -ExecOnAnalysisCompleteCmd="@=<rsp>"`) exported `FEngineLoop::Tick` frames, then GameThread timer statistics over the last 20 s of each trace:
  - main 13.806-33.806 s, 1424 frames
  - 86c83fc 11.774-31.774 s, 1404 frames
  - The commands are in `insights/*.rsp`.
- **Per frame:** each scope's `Incl` and `Excl` divided by the window's frame count.
- **The traces themselves are not pushed** (88 MB each). They are on the PC at `D:\dev\ss-fix\Artifacts\profile\helmeye-main-162929.utrace` and `helmeye-pr787-163006.utrace`.
- **The table:** the top 20 scopes by the difference in exclusive ms per frame (A = main 424b580b, B = 86c83fc):

| Scope | excl ms/frame A | excl ms/frame B | diff (B - A) | incl ms/frame A | incl ms/frame B | calls/frame A | calls/frame B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Game thread idle time | 3.615 | 3.809 | +0.194 | 3.615 | 3.809 | 1.0 | 1.0 |
| Sailing_BoatCapture | 0.245 | 0.198 | -0.047 | 0.247 | 0.200 | 1.0 | 1.0 |
| ParallelFor Task | 1.787 | 1.826 | +0.038 | 1.787 | 1.826 | 3.0 | 3.0 |
| Sailing_RigLines | 1.147 | 1.174 | +0.027 | 1.487 | 1.507 | 1.1 | 1.1 |
| UpdateSection GT | 0.650 | 0.638 | -0.011 | 0.650 | 0.638 | 6.8 | 6.8 |
| Sailing_WaterUploads | 0.292 | 0.302 | +0.010 | 0.297 | 0.307 | 1.0 | 1.0 |
| Sailing_Water | 0.783 | 0.776 | -0.007 | 1.657 | 1.676 | 1.0 | 1.0 |
| GameEngine Tick | 0.078 | 0.084 | +0.006 | 9.835 | 9.837 | 1.0 | 1.0 |
| Sailing_Crew | 0.305 | 0.309 | +0.005 | 0.316 | 0.321 | 4.0 | 4.0 |
| Create ProcMesh Proxy | 0.119 | 0.115 | -0.004 | 0.124 | 0.117 | 3.7 | 2.9 |
| AddPrimitive (GT) | 0.032 | 0.028 | -0.004 | 0.161 | 0.150 | 4.2 | 3.3 |
| ConstructObject | 0.029 | 0.025 | -0.004 | 0.081 | 0.073 | 6.5 | 5.7 |
| WaitForTasks | 0.143 | 0.139 | -0.004 | 0.143 | 0.139 | 1.1 | 1.1 |
| ParallelFor.Wait | 0.443 | 0.446 | +0.003 | 0.443 | 0.446 | 2.0 | 2.1 |
| UInstancedStaticMeshComponent::CalcBoundsImpl | 0.037 | 0.034 | -0.003 | 0.037 | 0.034 | 0.8 | 0.8 |
| Queue Ticks | 0.066 | 0.069 | +0.003 | 0.066 | 0.069 | 1.0 | 1.0 |
| Create Mesh Section | 0.044 | 0.042 | -0.002 | 0.078 | 0.075 | 2.6 | 2.6 |
| FTaskBase::WaitImpl_StateChangeEvent_WaitFor | 0.021 | 0.023 | +0.002 | 0.021 | 0.023 | 0.1 | 0.1 |
| UInstancedStaticMeshComponent::BatchUpdateInstancesTransforms | 0.204 | 0.202 | -0.002 | 0.204 | 0.202 | 7.0 | 7.0 |
| UpdateChildTransforms | 0.083 | 0.081 | -0.002 | 0.310 | 0.310 | 66.3 | 66.3 |

FEngineLoop::Tick inclusive per frame: A 14.044 ms, B 14.244 ms.


- **Reading:**
  - The tick is 0.2 ms longer per frame on 86c83fc. That is entirely **game thread idle time** (+0.19 ms), the game thread waiting on rendering.
  - Every working scope is within 0.05 ms: rig lines, water, crew, ProcMesh, the ISM transforms.
  - There are no new scopes for the render-time blend.
  - At this level the change is free on the game thread.
