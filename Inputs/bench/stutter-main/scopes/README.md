# Stutter: naming the background ParallelFor (PC, Nov 26 2026)

**Setup:** a local worktree off main 8e5cbfce with **`scopes.patch`** (Source only, never pushed).
- **Scopes:** a named `TRACE_CPUPROFILER_EVENT_SCOPE` inside each game `ParallelFor` body:
  - the wake grid's FFT row and column passes and its five `StepOnce` passes;
  - `WaterSurface` (shore depth map, wind-map rows);
  - the sail cloth;
  - traffic (the injected lambda in `TrafficManager.cpp`, since `Traffic.cpp` is plain physics);
  - world tiles.
- **A cap switch,** opt-in: `-SailingWakeFftCap=<k>` runs each FFT pass as k chunks. It was never measured; see below.
- **Build:** MSVC, succeeded, 0 warnings in the project's `Source/`.
- **Run:** one 60 s traced run, `-trace=cpu,frame,gpu -statnamedevents`. The same lake chase as `../followup/` (4K Ultra,
  VSync off, the demo at TWA 60, 12 kn), at cap 0, so the game's own code path.

## Which body fills the background workers

**What I measured:** worker time per render-thread frame by scope over 40-46 s (`worker-scopes-slow-vs-fast.txt`). That's
97 slow frames over 22.5 ms and 25 fast frames under 19 ms.

| Scope | Slow | Fast |
|---|---|---|
| **`Sailing_PF_WakeFftCols`** (the wake FFT, column pass) | **27.6 ms** | **32.5 ms** |
| `Sailing_WaterDetailBlend` | 10.3 | 8.0 |
| `Sailing_PF_WakeFftRows` (the same FFT, row pass) | 2.1 | 2.5 |
| `Sailing_PF_WaterWindMapRows` | 2.8 | 4.7 |
| `Sailing_PF_TrafficSails` | 2.7 | 2.6 |
| `Sailing_PF_WakeSpectrum`, `WakePressure`, `WakeOut`, `WakeSlick`, `WakeDepth` | 0.8-2.4 each | 0.7-2.4 each |
| `Sailing_PF_SailCloth` | 1.0 | 1.0 |
| all background `ParallelFor Task` time | 39.3 | 46.0 |

- **The column pass of the wake FFT is the background `ParallelFor` load:** about **28-33 ms of worker time per frame**,
  roughly 1.5 cores all the time, and **about 70% of all background `ParallelFor` time**.
- **The row pass does the same arithmetic in 2-2.5 ms.** The 13x gap is memory access:
  - the columns walk the grid with a stride of N (`Fft(A + C, N, N, ...)`), so nearly every load misses cache;
  - the rows run contiguously.
- **The cheap fix:** transpose between the passes (FFT the rows, transpose, FFT the rows again, transpose back). It
  should cut that load by an order of magnitude, whatever its priority.

## What this trace couldn't settle

- **The trace itself distorted the frames.** With hundreds of thousands of extra named scope events, the traced run is
  slower than the earlier ones: p50 22.2 ms, p99 33.9 ms, 57% of frames changing by over 2 ms, game thread 16 ms. The
  untraced runs were about 20.6 / 24.1 ms.
- **So in this run the slow frames aren't the visibility wait seen before** (+0.5 ms here). They're spread over the render
  thread: breadcrumb/RHI begin +2.8, UpdateSection +1.1, RDG execute +1.0, and in the workers the FFT columns are, if
  anything, higher in the fast frames.
- **What's solid:** the attribution of worker time by scope.
- **What isn't:** frame by frame, which job delayed which frame, with this much tracing on.
- **Stopped here, as briefed:** #837's branch (f9349436) already names these bodies (`Sailing_WakeGridRows`, ...) and runs
  the wake grid's passes at BackgroundPriority. So the cap mitigation wasn't run: I stopped the job before the capped runs.
  The re-trace on #837's head will measure that change against `../followup/`.

Bean's Saved was held aside and restored (7B5CA7BE).
