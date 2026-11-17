# Bluebonnet frame rate on the PC: #758 at 59c099e0

## Setup

- **The branch on its own.** #758's head 59c099e0, **without main merged**. A local merge with main 687f777c conflicts in `docs/licences/assets.csv` and `scripts/import_boats.py`, the same conflict as #763, so the branch was checked on its own. MSVC build clean.
- **Package:** a Development package to the new `Packaged/Windows-59c099e0` (3 min), warmed once, then five runs back to back.
- **How each run was made:** `bench-win.ps1 -Seconds 12 -ResX 1920 -ResY 1080 -Quality Ultra -Demo` on bench-visual's `helm-eye` view, with `-SailingScreenPct=100` and the view's `-SailingShowCrew=1` replaced by each run's own setting. The bench script was a temporary copy that stops its own game by PID.
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Files:** the full `bench.json` of each run, `runs.csv` (every column below, with the exact game args) and `end-shots.jpg`, the end shot of each run: a to e, left to right and top to bottom.

Run (a)'s full args: `-SailingWorld=Lake -SailingLaunch=1 -SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingHoldTWA=45 -SailingBoat=Blue -SailingShowCrew=1 -SailingScreenPct=100`

| Run | Args | fps | p99 ms | game ms | render ms | RHI ms | GPU frame ms | GPU total | base | lumen | water | clouds/fog | niagara | post | other |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a-blue-crew | `-SailingBoat=Blue -SailingShowCrew=1` | 40.8 | 34.65 | 23.49 | 24.13 | 11.55 | 11.11 | 8.28 | 3.91 | 0.95 | 0.38 | 0.7 | 0.01 | 0.73 | 1.6 |
| b-blue-nocrew | `-SailingBoat=Blue -SailingShowCrew=0` | 60.5 | 21.64 | 12.36 | 16.22 | 7.49 | 9.27 | 7.02 | 3 | 0.89 | 0.3 | 0.77 | 0.01 | 0.77 | 1.28 |
| c-blue-blendercrew | `-SailingBoat=Blue -SailingShowCrew=1 -SailingBlenderCrew` | 60.6 | 21.11 | 11.84 | 16.4 | 7.73 | 9.14 | 7.03 | 3.02 | 0.96 | 0.27 | 0.76 | 0.01 | 0.71 | 1.29 |
| d-j22-crew | `-SailingBoat=J22 -SailingShowCrew=1` | 58.8 | 21.56 | 12.15 | 16.98 | 7.99 | 9.08 | 6.83 | 2.75 | 0.77 | 0.37 | 0.86 | 0.01 | 0.74 | 1.32 |
| e-maxi-crew | `-SailingBoat=Maxi -SailingShowCrew=1` | 35.7 | 35.7 | 26.89 | 26.84 | 11.92 | 11.93 | 7.91 | 3.64 | 1 | 0.34 | 0.71 | 0.01 | 0.69 | 1.53 |

All five runs report `render_pct` 100. Every run also reports `foreground: 0`: the game window was not the foreground window, and I don't move windows or send input. Read small differences with care; the big ones below are far outside that.

## What it shows

- **The cost is her 12 MetaHuman crew figures, not her mesh.**
  - **(a) against (b):** hiding the crew takes her from **40.8 to 60.5 fps**. The game thread drops from 23.5 to 12.4 ms (-11.1), the render thread from 24.1 to 16.2 (-7.9), and RHI from 11.6 to 7.5 (-4.1). The GPU only drops from 8.3 to 7.0 ms total (base 3.9 to 3.0).
  - **On the PC it's CPU-bound:** the 4090 has room to spare, and the frame is the game and render threads' time.
- **(c), the Blender stand-in crew (SK_Sailor):** **60.6 fps**, the same as no crew at all (game 11.8, render 16.4 ms). The cost is specific to the MetaHuman figures: their skeletal meshes, grooms, cloth and animation, not to having 12 sailors drawn. The stand-ins show up on her rail in the end shot.
- **(d) the J/22 against (b):** with her crew hidden, the Bluebonnet (60.5 fps, render 16.2 ms) is as fast as the J/22 with its own crew of 3 (58.8 fps, render 17.0 ms). Her 507k-triangle Nanite hull and rig cost nothing measurable on the CPU, and about 0.2 ms on the GPU.
- **(e) the maxi, crewed: 35.7 fps,** even slower than her (game 26.9, render 26.8 ms). The maxi's larger MetaHuman crew shows the same per-figure cost.

**Against the Mac's High helm-eye** (42.9 fps; GPU 22.5 ms, RHI 11.7 ms): her RHI here, at 11.6 ms with the crew, matches the Mac's 11.7. That's consistent with the extra draw and skinning work for 12 MetaHuman figures, and it goes back to 7.5 ms without them. On the Mac the GPU binds, on the PC the CPU threads do, but in both cases the crew is the difference.

**Ways out:** draw fewer MetaHuman figures for her, for example the helm and a few trimmers, with the rest as SK_Sailor or hidden at range. Or give MetaHumans beyond the first few the stand-in at helm-eye distances, or tick their animation less often. Run (c) shows the stand-ins cost nothing measurable.
