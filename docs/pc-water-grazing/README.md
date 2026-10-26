# Why the PC's water is darker at grazing views (Oct 26 2026, for the PC)

The Ultra re-audit's gap 2 says the chase "sits dark". It isn't exposure. The view is side-lit (the camera faces 111 deg
from the sun), and in it the PC's water reflects about half as much of the low sky as the Mac's. This note is from a
code-only pass and Mac runs; the tests at the end are for the PC.

## Measured (linear luminance; water from patches in the lower corners, clear of the boat; low sky just over the horizon)

| Run (the chase, AfternoonBreeze 14:00, 14 kn) | Water | Low sky | Water / low sky |
|---|---|---|---|
| PC Ultra, audit on c9b7e9f1 | 0.011-0.014 | 0.151 | **0.09** |
| PC Ultra, audit on ad0a1d72 | 0.014-0.021 | 0.216 | **0.10** |
| Mac Ultra, main 0bf6624c | 0.023-0.031 | 0.148 | 0.16 |
| Mac High, main | 0.025-0.040 | 0.151 | 0.17 |
| Mac Ultra (another run, the boat nearer) | 0.048-0.070 | 0.241 | 0.20 |
| ... with `r.RayTracing.Geometry.ProceduralMeshes 0` | 0.050-0.068 | 0.250 | 0.20 |
| ... with `r.Lumen.HardwareRayTracing 0` | 0.051-0.068 | 0.249 | 0.21 |

The sky is about the same on both machines. The PC's water is about half the Mac's, relative to the sky. (My first
estimate, 3.4x, counted the hull in the "water" band.) At 3-15 deg below the horizon, Fresnel on a flat surface reflects
35-70% of the sky; tilted wave facets bring that down, so the Mac's 0.16-0.21 is plausible and the PC's 0.09-0.10 is low.

## What is the same on both

`QualityCVars(Ultra)` and the scalability levels (everything Cinematic except GI, which is Epic) are shared, and both
log "ray tracing supported 1 enabled 1, Lumen HW 1". The only per-platform settings are hair voxelization
(`Config/Windows/WindowsEngine.ini`), the shader formats (Metal SM6, DX12 SM6) and the Mac's groom cards. `M_WaterV4`,
its reflection inputs and `r.Water.SingleLayer.Reflection.DownsampleFactor` 2 are the same. Hit lighting is allowed on
Ultra on both (`r.Lumen.HardwareRayTracing.HitLighting.Allowed 1`).

On the Mac the grazing reflection doesn't depend on ray tracing at all: hardware Lumen, software Lumen and procedural
meshes out of the RT scene give the same water. So the Mac's reflection there comes from screen traces and the sky
light, and the difference is most likely in what DX12's ray traces hit.

## Suspects, most likely first

1. **The water rings and the far plane are in the ray-tracing scene, flat.** `AWaterSurface`'s `WaterRing<n>` and
   `FarPlane` are `UProceduralMeshComponent`s that never clear `bVisibleInRayTracing`. Their RT geometry is the
   undisplaced ring: the waves are WPO in `M_WaterV4`, and procedural meshes don't evaluate WPO in RT. A reflection ray
   leaving a trough (below the flat plane) hits the plane's underside; one from a crest grazes the next flat ring. Either
   way it returns the water's own dark surface cache instead of the sky. Grazing views have the most troughs facing the
   camera. Metal shows no effect from the flag (above), so its traces either don't reach here or skip these meshes.
   - PC test: the chase on Ultra with `-ExecCmds="r.RayTracing.Geometry.ProceduralMeshes 0"`. If water / low sky
     rises from 0.10 toward 0.2, this is it.
   - Fix: `Ring->bVisibleInRayTracing = false` and `FarPlane->bVisibleInRayTracing = false` in `AWaterSurface`. The
     hull is the other procedural mesh, and `KeepDynamicMeshesOutOfRayTracing` already keeps it in.
   - Check after the fix: RT reflections in the gelcoat then miss the lake and fall through to the sky light's lower
     hemisphere, which the water-bounce probe sets to the water's light. Look at the topsides in the close-bow view.
2. **DX12's hardware traces replacing the screen traces at grazing angles** (any hit, not just the rings: the far ring,
   the terrain tiles or the shore riprap at low angles).
   - PC test: the chase with `-ExecCmds="r.Lumen.HardwareRayTracing 0"`. If the water then matches the Mac's ratio
     and test 1 didn't, read which geometry the rays hit with `r.Lumen.Visualize` (reflection view) or
     `r.RayTracing.Debug` instance mode.
3. **The sky light's lower hemisphere from the water-bounce probe** (#320, readback #330, sun term #333). The readback
   copy (`SailingShaders`' `SailingProbeCopy.usf`) was only verified on Metal. If it reads zeros on DX12, the lower
   hemisphere goes black, and rough grazing lobes straddling the horizon darken. Unlikely to be the main cause: the
   PC's water was just as dark on c9b7e9f1, before the probe.
   - PC test: check that the log's "Water bounce: ... (probe r, g, b) ... lower hemisphere (...)" values are non-zero
     and close to the Mac's; then `-SailingNoWaterBounce`.
4. **Real-time sky capture differences** (the sky light's cube on DX12 against Metal). The low sky in frame matches, but
   the captured cube is what rough reflections read.
   - PC test: `r.SkyLight.RealTimeReflectionCapture` on and off, and compare the water only.

A Mac run can't reproduce 0.09: none of the settings the PC uses differ, and the Mac's water doesn't respond to the RT
switches.
