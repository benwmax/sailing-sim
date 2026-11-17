# CPU profile of main 687f777c, crew view (PC)

## How it was captured

- **Build:** the existing `Packaged/Windows-687f777c` (Development).
- **The run:** one `bench-win.ps1 -Seconds 12 -ResX 1920 -ResY 1080 -Quality Ultra -Demo` run of bench-visual's `crew` view, with `-SailingNoGpuSlices -trace=cpu,frame -statnamedevents -tracefile=D:\dev\ss-fix\Artifacts\profile\crew-687f777c.utrace`.
- **Result:** 47.7 fps. bench.json shows game 14.9 ms, render 20.9 ms, RHI 8.9 ms and gpu_frame 11.7 ms, with `foreground: 0`.
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).

## How it was exported

UnrealInsights.exe ran headless (`-NoUI -AutoQuit`, `-ExecOnAnalysisCompleteCmd="@=<rsp>"`) in two passes:

1. `TimingInsights.ExportTimingEvents` of the game thread's `FEngineLoop::Tick`, to place the window (`frames.csv`).
2. `TimingInsights.ExportTimerStatistics` for `GameThread`, `RenderThread*` and `RHIThread` over the window.

**The measured window** is the last 12 s of the trace before the game quits: **11.51 to 23.51 s** of the 23.81 s trace, 556 frames with a mean `FEngineLoop::Tick` of 21.56 ms. That leaves out the load and the 3 s warm-up; the bench measures for 12 s and then quits. Per-frame figures are totals over the window divided by 556.

**Files here:** the three per-thread CSVs (Insights' columns `Incl` and `Excl` are seconds over the window), `frames.csv` and `crew.bench.json`. The full trace (106 MB) stays on the PC at `D:\dev\ss-fix\Artifacts\profile\crew-687f777c.utrace`.

## Render thread: top 15 by exclusive time

| # | Event | Calls (calls/frame) | Inclusive ms/frame | Exclusive ms/frame |
| --- | --- | --- | --- | --- |
| 1 | `UpdateSection RT` | 9179 (16.5) | 5.47 | 5.3 |
| 2 | `WaitForTasks` | 727 (1.3) | 1.83 | 1.83 |
| 3 | `FRDGBuilder::AllocateTransientResources` | 1636 (2.9) | 0.86 | 0.82 |
| 4 | `UpdateTextureRegionsData` | 31145 (56) | 0.64 | 0.64 |
| 5 | `FTaskBase::WaitImpl_StateChangeEvent_WaitFor` | 2213 (4) | 0.53 | 0.53 |
| 6 | `AddPass_Rasterize` | 2782 (5) | 0.53 | 0.39 |
| 7 | `FRDGBuilder::CollectResources` | 1636 (2.9) | 1.31 | 0.38 |
| 8 | `Scene` | 2943 (5.3) | 8.69 | 0.37 |
| 9 | `LumenReflections` | 1671 (3) | 0.3 | 0.3 |
| 10 | `UpdateAllPrimitiveSceneInfos` | 556 (1) | 0.94 | 0.28 |
| 11 | `NodeAndClusterCull` | 2782 (5) | 0.28 | 0.28 |
| 12 | `LumenScreenProbeGather` | 1113 (2) | 0.48 | 0.27 |
| 13 | `FWaitingQueue_Unpark_SignalWaitingThread` | 35316 (63.5) | 0.25 | 0.25 |
| 14 | `GlobalDistanceFieldUpdate` | 1112 (2) | 0.42 | 0.24 |
| 15 | `FShadowSceneRenderer_DispatchVirtualShadowMapViewAndCullingSetup` | 556 (1) | 0.2 | 0.2 |

## Render thread: top 15 by inclusive time

| # | Event | Calls (calls/frame) | Inclusive ms/frame | Exclusive ms/frame |
| --- | --- | --- | --- | --- |
| 1 | `Frame` | 562 (1) | 21.57 | 0.08 |
| 2 | `SceneRenderBuilder_Render` | 557 (1) | 12.78 | 0.01 |
| 3 | `SceneRender` | 558 (1) | 12.77 | 0.03 |
| 4 | `RenderViewFamily` | 557 (1) | 10.67 | 0 |
| 5 | `FDeferredShadingSceneRenderer_Render` | 557 (1) | 10.66 | 0.13 |
| 6 | `Scene` | 2943 (5.3) | 8.69 | 0.37 |
| 7 | `FRHIBreadcrumbScope_GameThread_Begin` | 1113 (2) | 7.6 | 0.13 |
| 8 | `FProcMeshSectionUpdate` | 9179 (16.5) | 5.48 | 0.01 |
| 9 | `UpdateSection RT` | 9179 (16.5) | 5.47 | 5.3 |
| 10 | `RenderGraphExecute` | 1640 (2.9) | 2.44 | 0.09 |
| 11 | `WaitForTasks` | 727 (1.3) | 1.83 | 1.83 |
| 12 | `Dynamic shadow setup` | 1112 (2) | 1.55 | 0 |
| 13 | `FSceneRenderer::FinishInitDynamicShadows` | 556 (1) | 1.54 | 0 |
| 14 | `Init dynamic shadows` | 556 (1) | 1.54 | 0 |
| 15 | `WaitUntilTasksComplete` | 3345 (6) | 1.41 | 0.01 |

## Game thread: top 15 by exclusive time

| # | Event | Calls (calls/frame) | Inclusive ms/frame | Exclusive ms/frame |
| --- | --- | --- | --- | --- |
| 1 | `Game thread idle time` | 554 (1) | 5.41 | 5.41 |
| 2 | `ParallelFor Task` | 3857 (6.9) | 3.4 | 3.4 |
| 3 | `Sailing_RigLines` | 2225 (4) | 2.62 | 2.21 |
| 4 | `UpdateSection GT` | 9170 (16.5) | 1.82 | 1.82 |
| 5 | `Sailing_Terrain` | 557 (1) | 1.14 | 0.87 |
| 6 | `ParallelFor.Wait` | 2927 (5.3) | 0.85 | 0.85 |
| 7 | `Sailing_Water` | 557 (1) | 2.08 | 0.74 |
| 8 | `Sailing_WaterUploads` | 557 (1) | 0.47 | 0.46 |
| 9 | `FPngImageWrapper::Compress` | 1 (0) | 0.41 | 0.41 |
| 10 | `Sailing_Crew` | 2225 (4) | 0.4 | 0.38 |
| 11 | `UInstancedStaticMeshComponent::BatchUpdateInstancesTransforms` | 3897 (7) | 0.22 | 0.22 |
| 12 | `Sailing_BoatVisuals` | 2225 (4) | 6.69 | 0.19 |
| 13 | `Create ProcMesh Proxy` | 3707 (6.7) | 0.18 | 0.16 |
| 14 | `WaitForTasks` | 772 (1.4) | 0.15 | 0.15 |
| 15 | `SWidget_FastPathUpdate` | 556 (1) | 0.15 | 0.14 |

## Game thread: top 15 by inclusive time

| # | Event | Calls (calls/frame) | Inclusive ms/frame | Exclusive ms/frame |
| --- | --- | --- | --- | --- |
| 1 | `FEngineLoop::Tick` | 558 (1) | 21.58 | 0.01 |
| 2 | `Frame` | 558 (1) | 21.58 | 0 |
| 3 | `FrameTime` | 1115 (2) | 21.56 | 0.03 |
| 4 | `Tick_Engine` | 557 (1) | 15.41 | 0 |
| 5 | `GameEngine Tick` | 557 (1) | 15.41 | 0.07 |
| 6 | `UWorld_Tick` | 557 (1) | 13.44 | 0.01 |
| 7 | `World Tick Time` | 557 (1) | 13.42 | 0.02 |
| 8 | `Tick Time` | 2226 (4) | 13.19 | 0.01 |
| 9 | `ReleaseTickGroup Block` | 3340 (6) | 13.12 | 0 |
| 10 | `TickCompletionEvents` | 3897 (7) | 13.12 | 0.01 |
| 11 | `ProcessUntilTasksComplete` | 3897 (7) | 13.11 | 0.1 |
| 12 | `FTickFunctionTask` | 43051 (77.4) | 12.69 | 0.06 |
| 13 | `TG_PostPhysics` | 557 (1) | 11.39 | 0 |
| 14 | `Sailing_BoatVisuals` | 2225 (4) | 6.69 | 0.19 |
| 15 | `Sync_RenderingThread` | 558 (1) | 5.42 | 0 |

## What dominates

- **The render thread is the critical path.** It spends 21.6 ms a frame, the whole frame, while the game thread idles about 5.4 ms a frame waiting on it (`Game thread idle time`, `Sync_RenderingThread`).
- **The single biggest render-thread cost is procedural mesh section updates.**
  - **Render thread:** `FProcMeshSectionUpdate` / `UpdateSection RT` takes **5.3 ms a frame exclusive**, over 9,179 calls, about 16.5 section uploads a frame.
  - **Game thread:** the matching `UpdateSection GT` costs another 1.8 ms a frame.
  - **The cause:** these are `UProceduralMeshComponent` sections rebuilt every frame. In this view that's the boat's rig lines, the sail cloth and similar live geometry: `Sailing_RigLines` alone is 2.6 ms inclusive on the game thread, and `Sailing_BoatVisuals` 6.7 ms.
  - **Why it's expensive:** each update reallocates and re-uploads the section's buffers on the render thread. A path that updates vertices in place, or fewer, bigger sections, would cut most of it.
- **The rest of the render thread is ordinary scene rendering.** `SceneRender` is 12.8 ms inclusive. The visible pieces are dynamic shadow setup (1.5), the RDG transient allocation and collection (0.8 + 0.4), texture region uploads (0.6 over 56 calls a frame; the water and wind maps' strip updates), Lumen and Nanite culling. Each is small.
- **Game thread:**
  - **Actor ticks:** about 12.7 ms of `FTickFunctionTask`, mostly in `TG_PostPhysics` (11.4).
  - **Boat visuals:** `Sailing_BoatVisuals` is 6.7 ms inclusive. Rig lines, crew posing (`Sailing_Crew` 0.4 exclusive) and the procedural section updates are inside it.
  - **Water and terrain:** `Sailing_Water` 2.1 and `Sailing_Terrain` 1.1.
  - **Parallel work:** the game thread itself runs `ParallelFor` tasks for about 3.4 ms, plus 0.85 ms waiting on them.
  - **Once the render thread speeds up**, the game thread (about 15 ms busy) becomes the limit next.
- **A one-off:** `FPngImageWrapper::Compress` at 0.41 ms a frame is the bench's end screenshot, taken once (226 ms) inside the window. It isn't a per-frame cost.

No code changes.
