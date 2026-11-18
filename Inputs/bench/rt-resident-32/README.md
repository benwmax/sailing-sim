# Ray tracing always-resident geometry dumps (feedback #32), Windows-8a768667 Dev (PC)

**Runs:**

- Two 3-minute Dev runs on `Packaged\Windows-8a768667`, Ultra 1920x1080 windowed, 100% screen percentage, `-SailingDemo`, `-SailingNoGpuSlices`.
- Each with `"-SailingExecAt=60:r.RayTracing.DumpUnreferencedAlwaysResidentGeometries;170:r.RayTracing.DumpUnreferencedAlwaysResidentGeometries"`.
- **galveston/:** the #32 command line (`-SailingWorld=1 -SailingLaunch=1`).
- **lake/:** the same without `-SailingWorld`.
- **Flag:** `-SailingExecAt` is known to this build: the log shows "SailingBench: at 60 s: r.RayTracing.DumpUnreferenced..." and LogRayTracingGeometryManager's "List of unreferenced always-resident ray tracing geometries written to file ..." at 60 s and 170 s in both runs.
- Exact command lines in `args.csv`. Bean's Saved was held aside and restored.

**Each folder:** the two `UnreferencedAlwaysResidentGeometries(<time>).csv` dumps (columns Name, Size (MBs), Prims, Segments, Update), `bench.json`, the end screenshot and `game.log`.

## What the dumps hold (first dump of each run, grouped by name)

| Group | Galveston, rows | Galveston, MB | Lake, rows | Lake, MB |
|---|---|---|---|---|
| `SM_Shore_*` shore pieces | 508 | 37.3 | 43 | 2.8 |
| houses (`SM_Houses_*`) | 1,211 | 35.8 | 562 | 20.5 |
| MetaHuman groom cards (hair, beards) | 32 | 4.3 | 32 | 4.3 |
| `SM_Bridges_*` | 125 | 3.1 | 93 | 1.5 |
| trees | 20 | 2.7 | 16 | 2.5 |
| crew gear (`SM_CrewPFD` 0.84 MB the biggest single item) | 2 | 1.1 | 2 | 1.1 |
| **All** | **1,964** | **87.7** | **856** | **37.3** |

- **Second dumps:** 85.9 MB (Galveston) and 35.6 MB (lake), much the same.
- **The #32 warning:** it read 88.816 MiB on Galveston, matching the Galveston total here. Almost all of it is unreferenced shore pieces and baked house tiles kept always resident for ray tracing; the lake carries less than half.
