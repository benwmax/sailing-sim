# Ray-tracing always-resident geometry (feedback #32) and the HUD font hitch

## The warning

Development builds on Galveston showed `RAY TRACING GEOMETRY - ALWAYS RESIDENT MEMORY EXCEEDS 20% OF THE BUDGET (88.816 MiB / 400 MiB)`.

In UE 5.8 (`Engine/Private/Rendering/RayTracingGeometryManager.cpp`) "always resident" is the last
`r.RayTracing.NumAlwaysResidentLODs` (default 1) LOD of every loaded mesh that supports ray tracing, built and kept whether
or not the ray-tracing scene references it. The warning fires past 20% of `r.RayTracing.ResidentGeometryMemoryPoolSizeInMB`.

The engine's `r.RayTracing.DumpUnreferencedAlwaysResidentGeometries` (run at 60 s and 170 s with `-SailingExecAt`, PC,
`Windows-8a768667` Dev Ultra; data `Inputs/bench/rt-resident-32/` on the inputs branch) listed what was resident but unused:

| Group | Galveston MB | Lake MB |
|---|---|---|
| baked shore tiles `SM_Shore_*` | 37.3 | 2.8 |
| baked house tiles `SM_Houses_*` | 35.8 | 20.5 |
| groom cards | 4.3 | 4.3 |
| bridges | 3.1 | 1.5 |
| trees, crew gear, the rest | 7.2 | 8.2 |
| **all (of 88.8 on Galveston)** | **87.7** | **37.3** |

Almost all of it was unreferenced. These meshes do need ray tracing near the boat (Lumen's hardware rays), so they keep
`bSupportRayTracing`; instead every tier sets `r.RayTracing.NumAlwaysResidentLODs=0` (`QualityCVars`): a mesh's
ray-tracing structure is built when the scene first references it and stays in the 400 MB pool, evicted only under
pressure. Test: `SailingSim.Visual.TierSettings`.

**Check on the PC:** the #32 Galveston line shows no warning; `stat RayTracingGeometry` (or the CSV stat
`RayTracingGeometry/TotalAlwaysResidentSizeMB`) reads about 0; Ultra stills near the shore match main (no Lumen holes as
tiles come into reach).

## The font hitch

A one-time 84 ms "Load Font" under the HUD's text layout at 64 s on the water (trace `Inputs/bench/soak-aground-trace/short/`):
the UI faces are lazy-loaded TTFs. `SailUI::PreloadFonts` measures a sample in every style (and the arrows Atkinson takes
from B612) from the loading screen and the HUD's construction, so the faces load before sailing. The log line
`UI fonts preloaded in N ms` shows the cost moved.
