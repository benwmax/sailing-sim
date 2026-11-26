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

- PC scopes (inputs a81cfb69, `Inputs/bench/stutter-main/scopes/`): the burst is the wake FFT's **column** pass,
  28-33 ms of worker time per render frame (about 1.5 cores, 70% of the background ParallelFor time) against 2 ms for
  the row pass: the columns were transformed in place with a stride of N. `Fft2` now gathers eight adjacent columns
  into contiguous lines, transforms them and scatters them back (bit-identical; standalone at N 512: 16.9 -> 4.3 ms,
  256: 1.5 -> 0.8 ms). Bow wave phase 3's second `Fft2` gets the same saving.

## Proof (to do)

PC: the same 60 s run, VSync off, traced: the share of frames changing by more than 2 ms, p99, and the named scopes
in the slow frames. If the slow frames remain, the trace now names the burst.
