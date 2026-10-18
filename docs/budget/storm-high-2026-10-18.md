# Storm view on High: where the 5 fps went (Mac, 2026-10-18)

The storm view (`bench-visual.sh` `storm`, High, M5 Pro, 1440x1080) measured 50.7 fps on main this afternoon and
45.2-45.5 on the C2 gate. That is one merge from failing the High floor (45). All runs below are packaged Development
builds of first-parent merges, benched in one session (`APP=<copy> ONLY=storm bench-visual.sh 12 <label> High`), one run
per line, in the order they ran.

## Bisection by merge (High's resolution governor on, as the gates run it)

Only three merges since the afternoon touch rendering: #125 (C1 clouds), #126 (T1 trees) and #132 (C2 sky cache).
#127-#131 and #133 change docs, UI or nothing that draws.

| Build | Commit | fps (each run) | GPU frame ms | render thread ms |
|---|---|---|---|---|
| base (before #125) | e07fdb2a | 51.4, 51.6, 49.4, 51.5, 51.6, 51.6 | 18.7 | 19.1 |
| #125 C1 clouds | c903d152 | 51.5, 51.2, 51.3 | 18.8 | 19.2 |
| #126 T1 trees | b37178d1 | 46.4, 45.9, 45.7, **51.0** (traced run) | 21.0 | 21.4 |
| before #132 | 9a985462 | 46.8, 45.7 | 20.9 | 21.3 |
| main (#132 C2) | 84a3d73f | 45.3, 45.2, 45.6, 45.5, 45.1 | 21.3 | 21.7 |

**The drop arrived with #126 (T1 trees).** #125 costs nothing. #132 adds about 0.3-0.5 fps on top: under this storm the
cache stands aside as designed (the storm is in the sky from launch, so `bCacheReady` never goes true, the clouds keep
their 15 km `DistanceToSampleMaxCount` and the full tracing distance). `-SailingNoSkyCache` on main measured 45.3 and 45.5,
the same as with the cache.

## The same at a fixed resolution

The governor (`ASailingGameMode::UpdateResolutionGovernor`) steps High down 3% every 0.5 s while the smoothed frame is over
21.6 ms, to a floor of 82%, and back up only under 18.5 ms. Logged on this branch: every storm launch reaches 82% during
the 3 s warm-up (load hitches), on base and on main alike. So all the gate numbers above are at 82%.

| Build | fixed 100% (`-SailingScreenPct=100`) | fixed 82% | governor (ends at 82%) |
|---|---|---|---|
| base e07fdb2a | 46.0, 46.1 | 48.5, 48.0 | 51.5 (median of 6) |
| #125 c903d152 | 46.5 | 47.7 | 51.3 |
| #126 b37178d1 | 45.2 | 45.7 | 45.9 (median of 4) |
| main 84a3d73f | 44.9, 44.7 | 45.7, 45.9 | 45.5 |

At native resolution T1 costs about 1 fps (0.5-0.6 ms). The big loss is that **after T1 the view no longer gets faster
at a lower resolution**: base gains 2-5.5 fps from 100% to 82%, main gains 1. Main is held at about 21.3 ms of GPU frame
by something that doesn't scale with resolution, so the governor (the gates' only lever on High) can't help.

## What it is (and isn't)

- **Not the trees' own drawing.** The storm view looks out over open water (no tree in the frame; screenshots of a
  fast and a slow launch are the same picture).
- **The cloud march.** Unreal Insights GPU traces (`-trace=cpu,frame,gpu`) of a fast launch (t1 at 51.0) and a slow one
  (main at 45.9), both at 82%: every pass is within 0.1 ms except `VolumetricCloud`, the march itself, 6.17 against 7.82 ms
  a frame (+1.65 ms; reconstruction and compose are unchanged). Same image, same cloud cvars
  (`ViewRaySampleMaxCount` 80, `DistanceToSampleMaxCount` 15, shadow samples 80).
- **Not ray tracing** (`-dpcvars=r.RayTracing.Geometry.InstancedStaticMeshes=0`: 45.0 on main, 50.9 with T1's switches
  off), **not async compute overlap** (`-dpcvars=r.RDG.AsyncCompute=0`: main 45.8 and 45.5, base 51.5).
- **Not one T1 feature.** On main, `-SailingNoTreeLight` alone 45.2/45.8 and `-SailingNoTreeLooks` alone 46.5/46.3. Both
  together 51.0, 51.1, 50.9, then 47.0. With this branch's finer switches the result flips between launches: proxies
  only 45.4; custom data only 45.7; crowns in Lumen only 51.1, then 45.5; lean only 50.9, then 46.8; crowns plus lean
  50.9, then 45.8. So the launch lands in a fast or a slow state for the cloud pass. Before T1 almost every launch is fast
  (8 of 9 governor runs). After it almost every launch is slow (13 of 14). Turning T1's additions off brings back mostly
  fast launches, but not reliably.

So the culprit merge is #126, but the mechanism is a bimodal cost in the volumetric cloud march (+1.65 ms GPU) that T1's
extra instances and per-instance data make the common case. Lighting-only proxies, crowns in Lumen's scene and three
custom floats on every tree ISM don't touch the clouds directly. The candidates left are things that move with GPU memory
or the scene's size (texture-cache behaviour of the cloud noise and weather map, a render-target allocation, the GPU
scene's buffers), and they need a Metal GPU capture to separate. There is no cheap, clearly right fix: removing a
T1 switch doesn't reliably bring the fast state back.

## Measuring switches on this branch

- `-SailingNoTreeLean`, `-SailingNoTreeData` (looks without the lean / without the custom data), `-SailingNoTreeProxy`
  (lighting without the near proxies), `-SailingNoCrownLight` (lighting without the mid and far crowns). These sit beside
  T1's `-SailingNoTreeLight` and `-SailingNoTreeLooks`.
- The resolution governor logs each step (`Resolution governor: 100% -> 97% (frame 62.70 ms smoothed)`).

## Suggested next steps

1. An Xcode Metal GPU capture of the storm view on main, one fast launch and one slow (both at a fixed 82%), comparing
   the cloud march's counters (texture cache hit rate, memory bandwidth, occupancy).
2. For the gates in the meantime: the storm view sits at 45.5 against a floor of 45 on High, with T1 and C2 in.
   Nothing else on main costs it more than 0.5 fps.

## Metal capture: what the slow state is (Mac, 2026-10-18 night)

Tools: Instruments' Metal System Trace from the command line (`xcrun xctrace record --template 'Metal System Trace'`,
attached to the bench's game or launched by xctrace), and ProfileGPU dumps every 4 s through
`-SailingExecAt=4:ProfileGPU;8:ProfileGPU;...` on the packaged base (e07fdb2a) and main (aa471309) apps, storm view,
High, governor on (all at 82%: `CloudView (PS) 296x222`). Each line below is one launch, cloud march ms per dump in
order; the last three are the bench's own GPU-slice dumps after the measured window.

| Launch | fps | cloud march (ms) at 4, 8, 12 ... s, then the three end-of-bench dumps |
|---|---|---|
| base | 52.4 | 5.56 5.91 5.84 5.75 5.68 5.67 5.67 5.84 5.66, then 7.95 7.89 8.06 |
| base, `r.TextureStreaming=0` | 51.9 | 5.69 5.92 5.88 5.57, then 8.52 8.22 8.18 |
| base, extra dumps at 17.4/18.4/18.8 s | 48.8 | 7.46 5.49 7.81 7.36 7.95 5.38 5.25, then 5.50 8.34 8.12 |
| main, T1 off (`-SailingNoTreeLight -SailingNoTreeLooks`) | 51.5 | 7.91 5.75 5.89 5.79, then 8.90 8.80 8.58 |
| main | 46.0 | 7.70 7.87 8.65 8.31 8.84 8.86 8.65 8.73 8.40, then 8.56 8.49 8.45 |
| main | 45.4 | 8.53 7.73 8.63 8.33, then 8.90 9.05 8.54 |
| main, `-SailingNoTreeData` | 45.6 | 8.43 7.78 8.71 8.23, then 8.90 8.70 8.45 |

What differs between the two states, and what doesn't:

- **One draw.** The whole difference is the view march, `CloudView (PS) 296x222`, a single fragment kick in its own
  render encoder: 5.3-5.9 ms fast, 7.7-9.0 ms slow (more under Instruments). Reconstruction and compose are unchanged.
  Same viewport, same encoder, every frame.
- **Not the GPU clock.** In the 40 s trace of a slow launch (1,100 cloud kicks), the other encoders of a slow frame are
  no slower than those of the rare fast frames (Lumen, VSM, base pass, reconstruction all within 0.1 ms). A lower
  performance state would slow them too.
- **Not other GPU work.** The cloud kick overlaps none of the game's own encoders (Apple runs encoders concurrently;
  this one runs alone) and, traced with `--all-processes` during a run, no other process's GPU work at all.
  (With no game in front, the Claude desktop app and WindowServer keep the GPU 30-50% busy; they stop when the game
  window covers them, so benches are not affected.)
- **No register spill.** The Metal compiler's spill events (per encoder, in the trace) name no cloud encoder, fast or slow.
- **Not texture streaming** (`r.TextureStreaming=0`: the same pattern), **not the screenshot** (a `shot` at 6 s does
  nothing; dumps just after the bench's own screenshot are still fast).
- **Not a per-launch property.** The state changes within a launch, in phases of seconds: base and T1-off launches start
  slow for the first few seconds, turn fast, and turn slow again as soon as the measured window ends (every launch, fast
  or slow, reads 7.9-9.0 ms in the three end-of-bench dumps). With T1 on, main stays in the slow phase the whole run;
  the trace of a slow launch shows only isolated fast frames (12 of 1,100).
- **Per-instance custom data alone keeps it slow** (`-SailingNoTreeData`: 45.6, slow throughout), matching the earlier
  finding that only T1 off as a whole brings the fast phase back.

Consequence for the gates: **the bench's `gpu` slices (`clouds_fog_ms`) are always taken in the slow phase**, after
the measured window, so a fast run's slices overstate its clouds by 2-3 ms. The fps and `gpu_frame_ms` are right.

What this leaves: the march's cost changes with something that is not its inputs' content (same image), not the clock,
not overlap and not its pipeline's register use, and that flips while the game runs. The candidates are its texture
reads' memory behaviour (the weather map, 1024^2 half floats re-uploaded by blit every 2 s; the noise volumes;
`CloudShadowTexture`, the sky LUTs) and which pipeline the draw binds (the PS path picks its permutation in the mesh
processor each frame). Telling those apart needs the GPU's own counters on that draw (texture cache misses, L1/last
level, ALU and occupancy limiters), and xctrace on this M5 Pro exports only "RT Unit Active" from the counter
instrument. That takes Xcode's frame capture (Debug > Attach to Process > SailingSim, then Capture GPU Workload), one
capture in each phase: easiest in a T1-off launch, which is slow for its first ~5 s and fast from ~8 s. No fix here.

Scripts: the capture helpers (`run.sh`, `tl.sh`, `xproc.py`, ...) live in git-ignored `Artifacts/cap/`; the traces
there carry the session environment, so they stay off git.

## GPU slices inside the measured window (branch gpu-slices-in-window)

The bench's three `ProfileGPU` frames are now taken **spread through the measured window**, at 40, 60 and 80% of it
(`ASailingGameMode::Tick`), not in the 2.4 s after it, so `gpu` slices see the same phase as the frames measured. The bench
also ends 2.4 s sooner. To keep the frame times clean, the 16 frames after each request are left out of the frame and thread
times. On the storm view the profiled frame shows as 3 frames of +2-4 ms, 8 to 13 frames after the request. bench.json
reports the count as `gpu_skipped_frames` (48 for three dumps). The game thread's named slices (`gt`) still sum over the
whole window.

Storm view on High, packaged, 12 s, governor on (82% in every run), one launch per line:

| Launch | fps | gpu_frame_ms | slices total ms | clouds_fog_ms |
|---|---|---|---|---|
| main, in-window slices (8 skipped frames) | 45.1, 45.2, 45.1 | 21.4 | 20.4-20.5 | 9.43-9.48 |
| main, in-window slices (16 skipped) | 44.3 | 21.8 | 21.7 | 9.75 |
| main, T1 off, in-window slices | 45.2, 45.2, 44.0 | 21.3-21.9 | 20.3-22.1 | 9.57-9.70 |
| main, T1 off, `-SailingNoGpuSlices` | 45.1, 45.2 | 21.3-21.4 | - | - |
| main, `-SailingNoGpuSlices` | 43.7 | 22.1 | - | - |

Frame rates with and without the in-window dumps agree to within launch-to-launch noise, so the dumps don't shift the
measurement. Tonight every launch on this Mac was in the slow phase, including the T1-off launches that were mostly fast
earlier. So no run here shows a fast launch's slices. In every slow launch the slices now agree with `gpu_frame_ms`
(about 1 ms apart, which is the work between passes). A fast launch should now report a `clouds_fog_ms` about 2-3 ms lower
than before, matching its fps.
