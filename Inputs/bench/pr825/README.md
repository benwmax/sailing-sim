# #825 ray tracing, no always-resident geometry (bcb91c2b) on the PC, Nov 24 2026

**Head:** `claude/project-thread-18f1pj` at **bcb91c2b**, on main 9291fbf6. I compared it with `Packaged\Windows-9291fbf6`.
Nothing was pushed to the branch.

- **MSVC build:** Succeeded, 0 errors.
- **Package:** Development `Packaged\Windows-pr825-bcb91c2b` (kept); cook 0 errors, 1 warning.

Every run was Ultra at 1920x1080, 100% screen percentage. The arguments are in `runs/args.csv` and every bench.json is
in `runs/`.

## The #32 warning is gone

The Galveston deep-water view (`galv-deep`) ran on both packages, with the always-resident geometry dumped.

| | 9291fbf6 | bcb91c2b |
|---|---|---|
| Unreferenced always-resident RT geometries | **1,978, 89.54 MB** | **0** |
| On-screen warning | "RAY TRACING GEOMETRY - ALWAYS RESIDENT MEMORY EXCEEDS 20% OF THE BUDGET (92.172 MiB / 400 MiB)" | none |
| fps / p99 / GPU ms | 65.3 / 19.97 / 9.55 | 65.3 / 20.30 / 9.53 |

- The dumps are `runs/*-galv-deep.unreferenced.csv`. Their first rows on 9291fbf6 include `SM_C22Hero_Mast` and
  `SM_CrewPFD`; the bcb91c2b dump has only its header row.
- `galv-deep-top.jpg` shows the top of both frames: 9291fbf6 on top with the red warning, bcb91c2b below without it.

## Shore stills: no Lumen holes

Two Ultra drone views of Galveston were shot on both packages: Clear Lake (launch 0) and the dike (launch 4). The
conditions were the afternoon breeze, 8 kn and 15:00.

- `drone-compare.jpg` shows 9291fbf6 on the left and bcb91c2b on the right.
- **The frames match.** The mean luminance difference is 1.3 and 2.4 of 255, which is the boat's small movement
  between runs.
- **No dark patches, missing bounce or black reflections** show on the water, the boat, the boat's shadow or the
  post at the lower left of the Clear Lake view.

| View | 9291fbf6 fps (GPU ms, Lumen) | bcb91c2b fps (GPU ms, Lumen) |
|---|---|---|
| clearlake-drone | 70.6 (9.44, 0.86) | 62.2 (9.43, 0.85) |
| dike-drone | 71.2 (9.05, 0.80) | 64.9 (9.09, 0.84) |
| coast-day | 71.7 (9.02, 0.61) | 73.3 (9.05, 0.62) |
| far-coast | 71.6 (9.03, 0.62) | 72.4 (9.03, 0.62) |
| bolivar-shore | 74.4 (9.03, 0.58) | 74.2 (9.02, 0.63) |

- **GPU time and Lumen are the same on every view.**
- The two drone fps drops on bcb91c2b came with a load hitch in the window, on the CPU side: max frames 122 ms and
  91 ms. 9291fbf6's clearlake run also had one, at 146 ms. A repeat would settle these single runs if wanted.
- The coast-day, far-coast and bolivar-shore views framed open water only, so they say little about Lumen on the
  shore. The drone views are the real shore check.
- My first bcb91c2b drone runs went out with no view arguments (the default lake view), so I reran them. The table and
  pictures use the rerun.

Bean's Saved was held aside for every run and restored (7B5CA7BE).
