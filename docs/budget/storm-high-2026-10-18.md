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
