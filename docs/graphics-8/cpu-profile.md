# CPU profile of the packaged game on the PC

The PC (i9-9900K, 8 cores, RTX 4090) is CPU-bound on every view. The 4090 renders an Ultra 1080p frame in about 9 ms,
but the frame takes 14.7 to 16.4 ms. That caps every later round on the PC near 60-70 fps whatever the GPU work.

## How it was measured

These were run on the packaged Development build of graphics-8-pc (G8 materials, MetaHuman crew), Ultra 1920x1080, the
autopilot sailing (`-SailingDemo`), and three bench-visual views: beam8 (open lake), marina (Rush Creek's slips) and
coast-day (Galveston Bay).

- **Per-frame thread times:** the CSV profiler (`bench-win.ps1 ... -GameArgs "<view> -csvCaptureFrames=1400
  -csvCategories=Exclusive,Basic,GPU"`; the CSV lands in `Packaged\Windows\SailingSim\Saved\Profiling\CSV`). The first
  third of each run (loading, warm-up) is dropped.
- **Who spends the game thread:** an Unreal Insights trace (`-trace=cpu,frame,gpu,bookmark -statnamedevents
  -tracefile=<path>`), exported headless with the new `scripts\windows\profile-export.ps1` (Insights'
  `TimingInsights.ExportTimerStatistics` per thread). With `-statnamedevents` each actor's tick carries its class
  name. The trace's thread filter folds render work into the game thread's list, so only the actor and Slate timers
  are read from it. Per-frame figures are totals over the trace divided by its 1,078 frames.

## Where the frame goes

| View | Frame | Game thread | Render thread | RHI thread | GPU |
|---|---|---|---|---|---|
| beam8 | 14.7 ms | 12.3 ms | 14.2 ms | 8.6 ms | 9.0 ms |
| marina | 14.7 ms | 11.3 ms | 14.6 ms | 8.4 ms | 9.4 ms |
| coast-day | 16.4 ms | 12.0 ms | 15.8 ms | 9.0 ms | 9.8 ms |

The **render thread** is the critical path: it takes the whole frame. The **game thread** is about 2.5 ms behind it.
It spends 2-4 ms a frame waiting (`EventWait`) and would take over as soon as the render thread got quicker. The GPU
has 5-6 ms to spare at Ultra 1080p. Both CPU threads have to come down for the PC to go faster.

### Game thread (beam8, ms per frame)

| What | Inclusive | Exclusive | Notes |
|---|---|---|---|
| `TickActors` (all actor ticks) | 9.5 | | the CSV's category |
| `ASailboatPawn` tick | 5.9 | 4.7 | 4 tick calls a frame. Has no internal scopes, so physics (`Boat.Step` at 120 Hz, two steps a frame at 60 fps), `UpdateRigVisuals` (sail meshes, cloth, crew pose, rig lines), sound and capture are mixed together |
| `ALakeTerrainActor` tick | 2.5 | 1.4 | chunk streaming and the trees' near/mid/far rebinning (`UpdateModelTrees`) |
| `AWaterSurface` tick | 1.8 | 1.7 | matches bench.json's `water_cpu_ms` (1.9): wave-detail, wake and shore uploads and the hull clip |
| `ATrafficManager` tick | 0.9 | 0.9 | beam8 has no traffic |
| Slate (HUD, `SSailHud`) | 0.9 | | tick 0.74, draw 0.74 (both include waits) |
| Groom components (crew hair) | 0.38 | | 29 components a frame for three sailors |
| Poseable meshes (crew) | 0.29 | | 38 components |
| Procedural meshes (sails, telltales) | 0.35 | | 31 a frame, `Create Mesh Section` 2.3 a frame |
| `ASailingEnvironment`, `ASailingHUD`, `ASailingGameMode` | 0.19 / 0.19 / 0.15 | | |

### Render thread (ms per frame, from the CSV)

| What | beam8 | marina | coast-day |
|---|---|---|---|
| `RenderOther` + `RenderThreadOther` (uncategorised: visibility, GPU scene, dynamic mesh elements, draw command setup) | 7.1 | 6.7 | 7.7 |
| `RDG_CollectResources` + `RDG` + `RDG_Execute` | 2.5 | 2.4 | 2.6 |
| Shadows (`RenderShadows`, waits) | 0.7 | 1.6 | 0.8 |
| Lighting | 0.6 | 0.6 | 0.7 |
| Distance fields (`PrepareDistanceFieldScene`) | | | 0.7 |

From the trace, the render-thread items that are ours to change, per frame: `HairCardsInterpolation` about 0.5 ms (the
crew's grooms), `FXSystemPreRender` about 0.75 ms, `RayTracingDynamicGeometryUpdate` about 0.45 ms (dynamic meshes
rebuilt into the ray-tracing scene each frame: sails, crew, telltales), and `FrontLayerTranslucency` about 0.5 ms.

## Proposed fixes, in order

| # | Fix | Thread | Expected gain | Effort |
|---|---|---|---|---|
| 1 | **Instrument first.** `TRACE_CPUPROFILER_EVENT_SCOPE` around the physics loop, `UpdateRigVisuals` (and inside it: sails, cloth, crew, rig lines), `UpdateSound`, `UpdateCapture` and the learning/drill updates in `ASailboatPawn::Tick`. The same for `AWaterSurface::Tick` (per upload), `ALakeTerrainActor::Tick` (streaming vs trees) and `ATrafficManager::Tick`. The scopes cost nothing measurable. | GT | none, it's the map | one-liners, about 15 of them |
| 2 | **Physics off the game thread.** The fixed 120 Hz `Boat.Step` is plain C++ (`SailingPhysics`, no UObjects). Kick it as a task at the start of the tick with this frame's controls and wind, do the rest of the tick, then join before `ApplyStateToTransform`. The traffic sim's boats likewise, in parallel. | GT | most of the physics share of the 4.7 ms (to confirm with 1). If physics is half, about 2 ms | medium. Wind and waves must be read-only during the step; they are owned by the game mode and advanced before the pawns tick |
| 3 | **Sails: update, don't recreate.** `Create Mesh Section` runs about 2.3 times a frame. `UpdateMeshSection` (same topology) or a dynamic mesh with only positions and normals updated halves the CPU and the render-thread proxy rebuild. | GT + RT | 0.2-0.4 ms GT, part of `RenderOther` | small |
| 4 | **Keep dynamic meshes out of the ray-tracing scene.** `bVisibleInRayTracing = false` on sails' procedural meshes, telltales, rig lines and the crew's poseable meshes and grooms. Lumen's hardware traces barely see them, and each is rebuilt into a BLAS every frame. | RT + GPU | about 0.45 ms RT (`RayTracingDynamicGeometryUpdate`), some GPU | one-liners per component |
| 5 | **Water uploads at 30 Hz, on the render thread.** If `AWaterSurface` uploads detail, wake and shore textures every frame, upload when a new 30 Hz result lands, with `ENQUEUE_RENDER_COMMAND` + `RHIUpdateTexture2D` from the worker's buffer, not a game-thread copy. | GT | up to 1.5 ms of the 1.7 | small to medium |
| 6 | **Traffic manager early-out** when there are no traffic boats, ships or races. | GT | 0.9 ms on views with no traffic | one-liner-sized |
| 7 | **Terrain tick throttle.** Re-bin the trees and stream chunks only when the camera has moved a set distance or every N frames (`UpdateModelTrees` already gates on distance; the remaining 1.4 ms exclusive is the rest of the tick). | GT | about 1 ms | small, after 1 |
| 8 | **Crew grooms.** Drop peach fuzz and eyelash grooms past 3 m, and all grooms past 25 m (the cards LOD covers the hair). 29 groom components for 3 sailors. | GT + RT | about 0.3 ms GT, about 0.4 ms RT (`HairCardsInterpolation`) | small |
| 9 | **HUD at 10 Hz for real.** `SSailHud`'s text updates at 10 Hz, but Slate still prepasses and paints it every frame. An invalidation panel (`SInvalidationPanel`) or global invalidation for the HUD would cut the paint. | GT | about 0.4 ms | small |

Fixes 3-9 together: about 4-5 ms off the game thread and about 1-1.5 ms off the render thread. The render thread then
leads at 13-14.5 ms, so the frame would go from about 68 to about 72-75 fps at Ultra 1080p on this PC. Fix 2 matters
once the render thread is lower. The rest of the render thread's 7 ms of `RenderOther` is the scene's object and
draw-call count (marina boats, houses, trees, the shore kit), so more of the world baked into Nanite tiles and fewer
dynamic components is the long-term lever there. The same work runs on the Mac, so it should gain
too (not measured there).

No code was changed for this profile. The one-liners (1, 4, 6) can go in with the next round's first build.
