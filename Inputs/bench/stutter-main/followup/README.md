# Stutter follow-ups on main d8f2a3dc (PC, Nov 26 2026)

**The run:** 60 s of lake chase-camera sailing, the same as `../`. 4K Ultra, the demo at TWA 60, 12 kn, crew off.
`Packaged\Windows-d8f2a3dc`, every run alone on the PC.

**Discarded:** two earlier attempts ran while other Unreal work was open, so their numbers aren't used.

## 1. Fullscreen with VSync on: what the display does

- **The display:** a Samsung Odyssey G7 at 3840x2160, currently 120 Hz, with a range of 29-165 Hz from Windows' video
  controller. The GPU is an RTX 4090 on driver 621.40.
- **What nvidia-smi can say:** on this driver it reports the display mode as deprecated and can't say whether G-Sync is
  on. I didn't open or change any NVIDIA setting.
- **What the frame times show:** fullscreen (`-fullscreen`) with `r.VSync 1` has a median of **20.8 ms**, not a multiple
  of 8.33 ms. With fixed 120 Hz VSync, frames would snap to 16.7 or 25 ms.
- **So** the display is almost certainly presenting with variable refresh (G-Sync / FreeSync, which the G7 supports):
  frames show when ready, and VSync doesn't quantise them.

| Run | p50 | p95 | p99 | Frames > 2 ms off median | Frame-to-frame change > 2 ms | Game / render / GPU p50 |
|---|---|---|---|---|---|---|
| Fullscreen, VSync on | 20.80 | 23.38 | 24.94 | 20.8% | 39.8% (mean 2.61 ms) | 10.7 / 20.8 / 20.3 |
| Windowed, VSync on, **t.MaxFPS 40** | **25.00** | **25.00** | **25.05** | **0.0%** | **0.1%** (mean 0.77 ms) | 9.5 / 12.7 / 20.7 |
| Windowed, VSync on, t.MaxFPS 60 | 20.23 | 22.50 | 24.12 | 13.6% | 26.6% (mean 2.16 ms) | 9.7 / 20.2 / 19.6 |
| Windowed, VSync off (traced) | 20.59 | 22.84 | 24.08 | 14.4% | 29.4% (mean 2.24 ms) | 10.1 / 20.6 / 19.9 |

## 2. Frame caps

- **A 40 fps cap makes the frames perfectly even:** every frame is 25.0 ms, a third of 120 Hz.
- **A 60 fps cap changes nothing:** at about 49 fps the game never reaches it.
- **For a player at 4K Ultra on this PC:** a 40 cap, or a lower render scale to hold 60, gives even motion. Uncapped, the
  frame time wanders 18-24 ms.
- **This run against the first:** the uncapped VSync-off run here is calmer than the first measurement (29% of frames
  changing by over 2 ms, against 56%). That's run-to-run variation, so the first run was the noisier one.

## 3. What makes the render thread alternate (Insights: cpu, frame, gpu, statnamedevents; VSync off; 40-46 s)

**The comparison:** 287 render-thread frames, 37 slow (over 22.5 ms, mean 23.2) against 22 fast (under 19 ms, mean
18.3). The output is in `render-thread-slow-vs-fast.txt` and `workers-slow-vs-fast.txt`; the scripts are beside them.

- **It's waiting, not work.**
  - Of the 4.9 ms difference, **4.4 ms is inside `FDeferredShadingSceneRenderer_Render`**, and **3.3 ms of that is
    `InitViews` -> `WaitForVisibilityTasks`**: the render thread waiting for the visibility tasks to finish.
  - Everything else differs by under 0.3 ms: UpdateSection (proc mesh) 2.3 / 2.1, RDG execute, texture uploads, Lumen
    scene update, VSM, Nanite.
- **The visibility tasks wait because the background workers are full.**
  - In slow frames, background tasks fill **90.5 ms** of worker time per render frame, against **26.6 ms** in fast ones.
    That's +64 ms, several cores' worth.
  - Almost all of it is unnamed **background `ParallelFor` tasks: 59.8 ms against 5.4 ms**. Named jobs barely move:
    OcclusionCull +2.7, Sailing_WaterDetailBlend +1.5, Sailing_WaterFoamGrid +1.1.
- **The game's `ParallelFor` calls:** `WakeGrid.cpp` (the wake's spectral FFT and its passes, run on a worker),
  `WaterSurface.cpp:1465` and `:2565`, `SailVisuals.cpp:269`, `Traffic.cpp:884` and `WorldStreaming.cpp:141`.
  - The likeliest is **`FWakeGrid`**: its FFT fans out across every worker in row and column passes from a background
    task, in bursts.
  - When a burst lands on a frame, the visibility tasks queue behind it and the frame grows by about 3-5 ms.
- **Next step:** to confirm, put a `TRACE_CPUPROFILER_EVENT_SCOPE` in each of those `ParallelFor` bodies (or give the
  calls a name) and take one more 60 s trace. To fix, cap how many workers the wake FFT may take (a batch size, or
  `EParallelForFlags::BackgroundPriority` with fewer tasks), or run it at a lower priority than the visibility tasks.

The traced run exited with code 777003 after writing its frames and bench.json; the trace itself is complete. Bean's
Saved was held aside and restored for every run (7B5CA7BE).
