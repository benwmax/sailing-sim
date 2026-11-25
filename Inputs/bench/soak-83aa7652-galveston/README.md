# 2 h 4K Ultra Galveston soak on Windows-83aa7652, Nov 25 2026

**Package:** Development `Packaged\Windows-83aa7652` (main 83aa7652).

**Run:** 14:37 to 16:38 UTC, 3840x2160 Ultra, 100% screen percentage. It used the same route and arguments as the fa51d3a6
Galveston soak (`Inputs/bench/` earlier): the deep-water start in Bolivar Roads, the demo autopilot and clock 15:00.

```
-SailingBench=7200 -SailingWorld=1 "-SailingStartAt=-20900,23500,120" -SailingDemo -SailingBenchTrace -SailingHour=15
"-SailingExecAt=300:r.RayTracing.DumpUnreferencedAlwaysResidentGeometries;6900:...;1795:stat+namedevents;
1800:Trace.File+<abs>.utrace+cpu,frame;2700:Trace.Stop"
```

The trace covers 30-45 min of the bench. Bean's Saved was held aside and restored (7B5CA7BE).

## Result: the full 2 h, exit 0, no crash

- **Whole run:** 50.6 fps, p99 24.4 ms, GPU 19.3 ms, game thread 13.6 ms, render thread 19.8 ms. Memory used 4,060 MB (peak
  5,347 MB).
- **Crash folders:** the usual two frame-0 ensures (groom PSO precache, matrix precision). No crash.
- **The boat:** no grounding. She made 15-248 m per minute (mean 111).

## The ~350 ms render-thread spikes DO recur on Galveston (the lake has none)

| Bench minute | frame ms | render ms | game ms | GPU ms | cause |
|---|---|---|---|---|---|
| 5.0 | 367 | 371 | 40 | 19 | the soak's own `r.RayTracing.DumpUnreferenced...` at 300 s |
| **33.8** | **493** | **501** | 50 | 19 | **traced:** distance-field scene update after a tide step (below) |
| 59.7 | 517 | 521 | 46 | 21 | same shape |
| 70.5 | 385 | 393 | 43 | 19 | same shape |
| 84.5 | 390 | 395 | 42 | 20 | same shape |
| 95.4 | 377 | 383 | 46 | 19 | same shape |
| 115.3 | 364 | 371 | 47 | 20 | the second `DumpUnreferenced...` at 6900 s |

Apart from these, the load and the exit, no frame is over 100 ms, and 8 are between 50 and 100 ms.

- **Pattern:** every real spike is all render thread. The GPU is flat and the game thread only waits on the render thread.
  The spikes come every 11-26 min.
- **fa51d3a6 had the same:** single spikes at 33, 61, 87 and 103 min.
- **The lake soak on this package** (`Inputs/bench/soak-83aa7652-lake/`) had none.

### What the trace shows (the 33.8 min spike, a 493 ms frame at trace time 2039.0 s)

**Render thread** (`trace/spike-RenderThread.csv`, a 0.8 s window): `FDeferredShadingSceneRenderer_Render` took 468 ms. Of that, **`FSceneRenderer::PrepareDistanceFieldScene` took 443 ms**:

| Timer | ms |
|---|---|
| UpdateDistanceFieldObjectBuffers | 317 (202 exclusive) |
| GlobalDistanceFieldUpdate | 125 (173 exclusive over the window) |
| UploadDistanceFieldObjectDataAndBounds | 120 |

In the 8 s before the spike, no frame comes near that (`trace/normal-RenderThread.csv`).

**Game thread** (`trace/spike-GameThread.csv`): in the same window, each of these roots moves **once**:
- `BridgesActor.Root` (its 677 static mesh components follow);
- `LakeTerrainActor.Root` (twice);
- `NavaidsActor.Fixed`.

**What moves those roots:** the coast's tide offset. On Galveston the bridges, landmarks, navaids and terrain follow the tide in
**2 cm steps**:
- `BridgesActor.cpp:231`, `LandmarksActor.cpp:106` and `NavaidsActor.cpp:308` move their actors;
- `SailingGameMode.cpp:491` rounds the tide shown to the same 2 cm.

Each step moves those actors. Every component under them, with its distance-field instances, is re-sent to the
distance-field (and Lumen) scene in one frame. This is the hitch `docs/recentre-hitch/` describes for re-centres, here
set off by the tide.

**Why the timing fits:**
- A 2 cm step every 11-26 min fits a bay tide of a few decimetres changing at varying rates.
- The lake has no tide, and no spikes.

**Ways to fix it (for whoever picks it up; not changed here):**
- Leave the offset out of the actors' transforms and apply it in their materials (WPO) instead.
- Or set `bAffectDistanceFieldLighting = false` on the big followers (BridgesActor's 677 components, the terrain chunks)
  where it doesn't show.
- Or spread the step's re-registration over several frames.

To check a fix:
1. Run `-SailingWorld=1` with a fast tide, or a forced step through a console command.
2. Look for `PrepareDistanceFieldScene` over 50 ms.

## Frame rate per 10 min

| Minutes | fps | frames over 30 ms | longest ms |
|---|---|---|---|
| 0-10 | 51.8 | 13 | 922 (load); 367 at 5.0 (RT dump) |
| 10-20 | 53.0 | 1 | 31.5 |
| 20-30 | 52.5 | 0 | 27.6 |
| 30-40 | 52.6 | 4 | 493 (tide step) |
| 40-50 | 52.9 | 1 | 33.5 |
| 50-60 | 49.4 | 8 | 517 (tide step) |
| 60-70 | 47.7 | 0 | 29.8 |
| 70-80 | 48.2 | 7 | 385 (tide step) |
| 80-90 | 48.2 | 5 | 390 (tide step) |
| 90-100 | 51.2 | 8 | 377 (tide step) |
| 100-110 | 49.5 | 1 | 30.3 |
| 110-120 | 49.5 | 4 | 364 (RT dump) |

The dip to 48-49 fps from 50 to 90 min follows the route (more shore in view); it isn't a trend.

## Memory (game process, every minute)

- **Working set:** 4,036 MB at 10 min and 4,037 MB at 116 min (range 3,973-4,269).
- **Private bytes:** 15,133 MB at 10 min and 15,103 MB at 116 min.
- **No leak.**

## Files

- `galveston-memory.csv`, `bench.json` and `trace/*.csv`: Insights timer statistics for the spike window and the 8 s
  before it.
- The 4.7 GB `.utrace` stays on the PC at
  `D:\dev\ss-fix\Artifacts\bench\soak2h-83aa7652\galveston-30min.utrace`.
