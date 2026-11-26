# Frame pacing: the wake solve and the visibility tasks (Nov 26 2026)

Bean, Nov 25: "a general stutter overall, not just the water". PC measurements on main d8f2a3dc, 4K Ultra, 60 s of
chase-camera lake sailing (inputs branch `Inputs/bench/stutter-main/` and `followup/`):

- The camera follows the boat to 0.3-0.5 px (p95): it isn't the camera.
- The GPU is flat (p50 about 20 ms); the render thread wanders (16-32 ms with VSync off).
- VSync on (the G7 runs variable refresh) narrows it; `t.MaxFPS=40` makes every frame 25.0 ms.
- Insights (VSync off, 287 frames): slow render frames are 4.9 ms longer, 3.3 ms of it in `InitViews` ->
  `WaitForVisibilityTasks`. In those frames the workers carry 90 ms of background tasks per frame against 27 ms, almost
  all of it unnamed `ParallelFor` tasks (60 against 5 ms). The likeliest source is `FWakeGrid`: run on a worker, its FFT
  and passes fan out over every worker in bursts, and the visibility tasks queue behind them.

## The change

- `FWakeGrid`'s parallel passes (`WakeParallel`) run at `EParallelForFlags::BackgroundPriority`, and so does the shore
  depth rebuild (`AWaterSurface::BuildShoreDepth`, on a worker). Both are polled (`IsReady`), never waited on while
  sailing, so frame work now goes first and they finish a little later.
- Every game `ParallelFor` body is named for traces: `Sailing_WakeGridRows`, `Sailing_ShoreDepthRows`,
  `Sailing_WindMapRows`, `Sailing_SailClothRender`, `Sailing_StreamTileRead`, `Sailing_TrafficBoatStep`.
- #839 (bow wave): `Fft2`'s column pass copies the columns out 16 at a time and transforms them as contiguous lines (each
  column walked in place at a stride of the grid's width missed the cache: 27-32 ms of worker time a frame against 2 ms
  for the rows). Bit-identical. PC trace on f186aa47 (Nov 26): background worker time in the slow
  frames 11.4 ms against 40.0 without it, p99 29.9 ms against 33.9.

## Proof (to do)

PC: the same 60 s run, VSync off, traced: the share of frames changing by more than 2 ms, p99, and the named scopes
in the slow frames. If the slow frames remain, the trace now names the burst.
