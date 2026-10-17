# Budget ledger

`ledger.csv` holds one row per tier (Low, Medium, High, Ultra), gate view (helm-eye, slip, coast-day, beat15, storm,
marina, crew) and metric, with its cap and the latest value measured on each machine:

    tier, view, metric, cap, mac_value, mac_date, pc_value, pc_date, source

`scripts/budget-ledger.py --machine mac|pc <bench.json files and visual-bench CSVs> [--soak soak.csv --view V --tier T]`
fills the value and date columns and prints anything over its cap. It never changes a cap. Caps are set in review:
- fps: 60 on Medium and 45 on High (the Mac's gate), 60 on Ultra (the PC).
- GPU slices: the measured value plus 10%.
- Memory: 1.25 times the measured peak.
- RAM growth: under 100 MB/h.
- p99 drift: under 1 ms/h.

`--seed-caps` fills only empty caps by those rules, and takes measured caps only from the machine that gates the tier
(the Mac for Low to High, the PC for Ultra). The Medium and High GPU-slice and memory caps are therefore empty until the
Mac's gate bench fills them.

## Sources

- `bench.json` (one per view and tier; `scripts\windows\bench-visual-win.ps1` now keeps them as
  `Artifacts\bench\<view>-<tier>.json`): fps, p99, game ms, GPU total and slices, water and wind-map CPU ms, the
  player boat's physics ms, and the engine's peak RAM (`mem_peak_mb`).
- The soak (`scripts\windows\soak-win.ps1`): a packaged run with the autopilot sailing and tacking, sampled every 30 s.
  It gives RAM growth (the process's private bytes) and p99 drift as least-squares slopes after a 10 minute warm-up,
  and peak VRAM (`nvidia-smi` memory.used for the whole GPU: bench.json has no VRAM figure).

Not captured yet: shared GPU memory (Windows' "shared GPU memory" counter), the working set (the soak reads private
bytes), and per-boat physics for traffic boats (bench.json's `boat_physics` is the player's boat).

## First PC values (main af8de58c, 1920x1080, Oct 16 2026)

All 28 view and tier runs are inside their fps caps. beat15 on Medium was rerun: its first run (51.8 fps) was the
first Medium launch after packaging, and the rerun gave 76.7 fps.

The 2-hour Ultra soak on beat15 (`soak-pc-ultra-beat15.txt`):
- RAM: +46 MB/h. The 10-minute peaks move between 8.47 and 8.69 GB with no steady rise.
- VRAM: flat to slightly falling (7.39 GB in the first 10 minutes, 7.23 GB at the end).
- **p99 drift: 4.2 ms/h, over its 1 ms/h cap.** The median p99 goes from 18.3 ms in the first hour to 19.7 ms in the
  second, and two windows spike (26.8 ms at 70-80 min, 28.1 ms at 100-110 min). fps falls about 1.5 an hour
  (76 to 70.7).

## Perf notes

- `perf-sun-setters-2026-10-17.md` (#110): the sun's scattering and disc setters stepped by 0.04. Parked on High for
  20 min on the Mac, fps goes from 54.9 to 59.3, p99 drift from +2.8 to -2.0 ms/h, and the virtual shadow map pages
  redrawn per frame from 974 to about 100.
