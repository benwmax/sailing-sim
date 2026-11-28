# The long-sail memory test

Draft for after the Dec 11 release: groundwork for the big Florida to Bahamas map (plan: "Huge maps without memory
growth"). This draft changes Source/ and docs/ only. A one-command script for each machine comes later, as a separate
change that needs Bean's label.

## In plain English

A big map only works if the game holds about the same memory at hour 6 of a passage as at hour 1, wherever the boat
is. This test sails a long way (or slides the world under the boat to cover the distance fast) and writes down the
game's memory once a minute. At the end it draws a straight line through those numbers and gives a verdict:

- **flat:** growth after the first 10 minutes is under the budget, 50 MB an hour by default.
- **growing:** over the budget. The report says whether the growth follows the **time** (a leak every frame, which
  shows even with the boat parked) or the **distance** (something loaded along the way and never dropped).

## What's in it

- With `-SailingBenchTrace`, the bench already logs the boat's position once a minute. It now also writes a row to
  `Saved/Bench/<shot>.mem.csv`:
  - time, the boat's position on the map, and the distance travelled
  - used and peak memory, and texture memory
  - the number of UObjects
  - the world streamer's resident tiles and their MB, the terrain chunks, and the re-centres

  The file is saved every 10 minutes too, so a crash still leaves the rows up to it.
- At the end, `bench.json` gets `soak_mem`: the rows after the warm-up, MB/h, MB per 100 km, first, last and peak MB,
  km travelled, the budget and the verdict. The log gets one line:
  `SailingBench memory: flat, +3.1 MB/h and +0.4 MB per 100 km after the warm-up (...)`.
  The MB per 100 km figure needs at least 10 km sailed after the warm-up, and is 0 below that. A 2 km lake run once
  fitted -3,451 MB per 100 km from a small dip.
- `-SailingMemBudget=<MB/h>` sets the budget.
- `Source/SailingSim/Public/SoakMemory.h` holds the fit, and `SailingSim.Smoke.SoakMemory.Fit` tests it.

## The three parts (from the plan)

1. **Tide check (PC, Galveston, parked):** the tide baseline with the memory rows. This is also the #846 merge gate.

       ARGS="-SailingWorld=GalvestonBay -SailingKeepStart -SailingTideStepEvery=20 -SailingBenchTrace"   # 30 min

2. **Fast course (both machines):** the world slides under the boat at 25 m/s, so 2 hours covers 180 km. Two versions:
   - the Texas coast out and back over 40 km, which is what `scripts/soak-streaming.sh` runs, and now gets the verdict
     too;
   - the Gulf passage world, crossing its whole 66 km in one direction before turning.

       ARGS="-SailingWorld=GulfPassage -SailingKeepStart -SailingRun=25,90,60000 -SailingBenchTrace -SailingQuality=High"

   The verdict should be **flat** in both. Rising MB per 100 km points at what stays loaded behind the boat.
3. **Real passage (later, on the big map):** the autopilot sailing a multi-hour passage (`-SailingDemo`) with real
   wind, tide and current, for 6 hours. This needs the Florida to Bahamas map and a route.

## Known limits

- "Used memory" is the process's physical memory, as the platform reports it. On the Mac it doesn't include the
  compressed pages that `footprint` counts, so the Mac soaks should keep `footprint` beside it, as
  `soak-streaming.sh` does.
- GPU memory isn't in the rows yet: texture memory only. The PC soak's `nvidia-smi` column stays the GPU measure.
