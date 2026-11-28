# The Mac's memory climb: a pool a frame (experiment)

Draft for after the Dec 11 release. Nothing changes unless the game is launched with `-SailingMetalPools`.

## In plain English

On the Mac the game's memory grows by roughly 0.6 to 0.9 GB an hour, in every world. The October soaks found the
growth: small graphics objects are made every frame (one "drawable" a frame, plus three ray-tracing builder objects a
frame on High) and never thrown away.

On Apple systems, objects like these are put in a "pool" to be freed later, and the pool is emptied at a known point.
Each of the engine's threads has a single pool for its whole life. The parts of the engine that make these objects
don't always open a smaller pool of their own, so their objects wait in the thread's big pool until the game quits.

The switch gives the render thread and the RHI thread (the one that talks to the graphics card) a fresh pool each frame.
At the end of the frame the pool is emptied. If the October diagnosis is right, the climb from those objects stops.

## What the switch does

`Source/SailingSim/Private/MetalPools.cpp`, compiled on the Mac only:

- **The render thread:** a pool is made at the start of each frame (`FCoreDelegates::OnBeginFrameRT`) and released at
  its end (`OnEndFrameRT`).
- **The RHI thread:** once a frame, a lambda on the immediate command list releases that thread's pool from the last
  frame and makes a new one.
- **Elsewhere:** a lambda that lands on another thread does nothing and is counted. Every 3600 frames the log gives
  `Metal pools: ... RHI-thread swaps N, lambdas on the render thread N, on other threads N`. If "other threads" is
  large, the immediate list runs on task threads, and that half of the switch reaches nothing.

The engine code it relies on (UE 5.8, read on the Mac):

- `ApplePlatformRunnableThread.h`: the one pool a thread holds for its whole life.
- `MetalRayTracing.cpp`: `BuildAccelerationStructure` has no `MTL_SCOPED_AUTORELEASE_POOL`.
- `MetalViewport.cpp`: `nextDrawable` is inside one, so the drawable probably leaks somewhere else.

## The risk

Releasing a pool also releases every pool made after it on the same thread. If the engine ever kept a pool of its own
open across the lambda, its later release would crash the game. The engine's own pools are all scoped inside single
calls, so this shouldn't happen, but it hasn't been run yet. That is why this is a switch.

## To check (Mac, after the freeze)

1. Build (clang), `SailingSim.*`, and Smoke with and without `-SailingMetalPools`.
2. The soak-3 pair from `docs/budget/mac-soak-parked-2026-10-17.md`: parked on High for 30 min, with `heap` and
   `footprint` at 100 s and 1790 s. Run it with and without the switch.
   - Watch the growth in `CAMetalDrawable`, `AGXG17XFamilyRayTracingGPUBuilder`, `MTLInstanceAccelerationStructureDescriptor`
     and `NSMutableArray`.
   - Watch the LLM tags `RHIMisc/CommandList/ExecuteAndDestruct` and `SceneRender`.
   - Record the log's `Metal pools:` lines.
3. The frame rate (bench.json) of the same pair, with p99 no worse.
4. If the builders stop but the drawables don't, the drawable is autoreleased on another thread, such as the main
   thread's present handler. The next step is `MallocStackLogging=1` and `malloc_history` on one leaked drawable to
   name the thread.

If the switch works and is safe, a follow-up turns it on by default on the Mac, still with a switch to turn it off. In
any case the engine-side fix belongs in a bug report to Epic, with Bean's OK.
