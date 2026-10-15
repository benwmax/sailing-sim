# Mac polish

Two pieces on the Mac while the PC works on W2. Neither touches `M_WaterV4`, `make_materials.py` or `WaterSurface.cpp`.
1. The lake's wave periods above 18 kn, which were short against SWAN (left open in `docs/physics-gaps`).
2. Real hulls for the moored power boats in Galveston. In the round-10 Clear Lake still they were plain white boxes.

## 1. Wave periods at high wind

**What was at fault: the peak-period relation, not the spectral shape.** The game's Tp is the growth law's target
(`FWaveField::TargetPeakPeriod`). The JONSWAP shape only spreads energy around that peak and doesn't move it, so the
shape can't make Tp short. The relation was the problem. Physics gaps steepened the sea above 18 kn by growing it in a
stronger "stress wind" (`GrowthStressWind`, U_A x (U / 18 kn)^0.43), and the SPM period law takes that wind's cube
root. Hs therefore rose by s = (U / 18 kn)^0.43 while Tp rose only by s^(1/3).

The extra height isn't a stronger wind, though. SWAN's young, strongly forced sea is further along its growth at the
same wind stress, which in effect is a longer fetch. The SPM's height and period laws together are Toba's 3/2 law,
Hs ~ U_A^(1/2) Tp^(3/2). At the same U_A, a higher sea therefore has Tp ~ Hs^(2/3), which is s^(2/3) and not s^(1/3).
SWAN's own lake medians follow Toba within 3% from 18 to 28 kn: Hs x2.09 and Tp x1.41, where Toba gives x1.37.

**The change** (`Waves.cpp`, `TargetPeakPeriod`):
- The period is the SPM law in U_A, times (Hs / Hs in U_A)^(2/3).
- It equals U_A's own law up to 18 kn, so nothing at or below 18 kn moves.
- Hs is untouched.
- The polar, scenario and reference runs keep their calibration sea (`bCalibrationSea` uses `GrowthLawPeriod` directly).

**The SWAN comparison** comes from `scripts/wave-check.sh`, a new standalone tool (`Tools/WaveCheck`) built with clang
over the physics sources and the bake's `swan-compare.csv` from `w3-swan-bake`.
- The statistic is the same as in `SailingSim.Physics.WaveGrowthSwan`: per direction, the median over the lake's water
  every 250 m, then the median over the 16 directions.
- SWAN's Tp is the bake's median SWAN / game period ratio times the median period of the game the bake compared
  against.
- This tool's SWAN Hs medians differ from the test's table (`swan-compare.csv`'s overall medians) by up to 3%.

| Wind | SWAN Hs | Game Hs | SWAN Tp | Tp, main | Tp, this branch |
|---|---|---|---|---|---|
| 5 kn | 0.048 m | 0.048 m (+1%) | 0.91 s | 0.98 s (+8%) | 0.98 s (+8%) |
| 8 kn | 0.085 m | 0.086 m (+0%) | 1.14 s | 1.19 s (+5%) | 1.19 s (+5%) |
| 11 kn | 0.125 m | 0.127 m (+1%) | 1.33 s | 1.36 s (+2%) | 1.36 s (+2%) |
| 14 kn | 0.167 m | 0.170 m (+2%) | 1.49 s | 1.50 s (+1%) | 1.50 s (+1%) |
| 18 kn | 0.238 m | 0.232 m (-3%) | 1.70 s | 1.66 s (-3%) | 1.66 s (-3%) |
| 22 kn | 0.335 m | 0.324 m (-3%) | 1.99 s | 1.86 s (-7%) | **1.91 s (-4%)** |
| 28 kn | 0.493 m | 0.484 m (-2%) | 2.38 s | 2.12 s (-11%) | **2.26 s (-5%)** |

Hs is identical to main at every speed. `WaveGrowthSwan` now also holds Tp within 10% of SWAN at every speed the bake
ran, and checks the Toba factor at 28 kn. Its Hs medians are those of physics gaps (0.484 m against 0.485 m at 28 kn).

**Still open.** The 28 kn period is still 5% short. Toba's law in U_A gives x1.37 from 18 to 28 kn where SWAN has
x1.41; closing that would take a period-only factor, which nothing in the growth laws justifies. The lee-shore period at
Rush Creek (14 kn) and the shallow arms are unchanged.

## 2. Moored power boats in Galveston

**Before.** The piers pack's lidar finds 490 power boats on the coast, from 5 to 39 m long (median 12 m).
`ACoastMarinasActor::PlaceBoats` drew each one as one of two models:
- under 9.5 m, the 6.4 m runabout;
- over that, the 11 m committee trawler, scaled up to 1.6 times. That model's house was three boxes.

Only 48% of the boats were drawn within 25% of their measured length.

**After.**
- **Three new models** come from the world kit's vessel generator (`Tools/blender/build_vessels.py`). The generator
  gained `prism`/`deckhouse` (a house lofted between plans, with leaning sides, a raked front and a window band),
  `rail` and `rubrail`.
  - `SM_Vessel_Express`: a 34 ft express cruiser with a raked wrap-round windscreen, a hardtop on posts, cockpit seats
    and a swim platform.
  - `SM_Vessel_Sportfish`: a 46 ft sportfisherman with a flybridge, hardtop, tuna tower, stowed outriggers and a
    fighting chair.
  - `SM_Vessel_MotorYacht`: a 60 ft flybridge motor yacht with two decks of house, long window bands, hull windows and
    a radar arch.

  Their topsides are the `Paint` slot (`M_VehiclePaint`), coloured per instance by `FBerthedBoat::PowerHullColour`:
  two thirds white, the rest navy, dark blue, ivory, grey, black and sea green. The trawler yacht's house (also the
  traffic's committee boat and the shrimper's wheelhouse) is now lofted the same way, at the same heights, so the
  traffic's lights still sit on it.
- **Class by length**, scaled from the nearest model:
  - under 8 m: the runabout;
  - 8-12 m: the express cruiser (a fifth of those 9.5 m and over are trawler yachts);
  - 12-16 m: the sportfisherman (a third of those over 13.5 m are motor yachts);
  - 16 m and over: the motor yacht.

  Of the 490, 470 are now drawn within 25% of their length: 56 runabouts, 133 express cruisers, 17 trawlers, 116
  sportfishermen and 168 motor yachts. The boats are instanced static meshes in `SpawnBerthedBoats`, like the marina
  neighbours.
- **A bug fixed along the way.** Each neighbour's hash was `uint32(X * 13 + Y * 7)` on a double. A negative double
  converted to uint32 is undefined, and on arm64 it gives 0. So 994 of the coast's 1,163 moored boats shared one seed:
  - the same class pick, the same paint and the same berthed dress;
  - and, on the lake, the same dress and livery for every slip south-west of the club's origin.

  Both hashes now go through int32. The lake marina's neighbours vary more than before.

New test: `SailingSim.Coast.MooredPowerClasses`. It checks five classes, at least nine in ten boats within 25% of their
length, a mostly white paint mix with several other colours, and that every model is imported.

**Stills** (High, uncooked, the capture mode; `scenes.csv` reproduces them:
`SCENES=docs/mac-polish/scenes.csv OUT=docs/mac-polish scripts/capture-scenes.sh 14`):

| Before (round 10, main 3634333) | After |
|---|---|
| ![before](../round-10/game/r10-galv-clearlake.png) | ![after](mp-galv-clearlake.png) |

`mp-galv-clearlake-row.png` is a new view: a row of eleven moored boats 400 m west of the drone, seen from 100 m across
the basin.

## Gate

- `scripts/build.sh`: succeeded. `scripts/test.sh`: **127 passed, 0 failed** (new: `SailingSim.Coast.MooredPowerClasses`;
  `WaveGrowthSwan` gained the Tp checks).
- `scripts/polar.sh --quick` and `scripts/reference-checks.sh --quick`: identical to main, line for line.
- `scripts/package-mac.sh`: succeeded.
- **bench-visual**, Medium and High, packaged, 12 s per view (`bench-visual.csv`, screenshots in `bench/`). The main
  column is physics gaps' run (`docs/physics-gaps/bench-visual.csv`). Every view holds Medium 60 and High 45:

| View | Medium fps (main) | p99 | High fps (main) | p99 |
|---|---|---|---|---|
| beam8 | 93.0 (93.2) | 11.51 ms | 55.1 (57.0) | 20.21 ms |
| beat15 | 91.3 (91.6) | 12.24 ms | 54.9 (54.6) | 22.21 ms |
| storm | 69.0 (69.1) | 16.37 ms | 48.4 (48.2) | 23.46 ms |
| marina | 88.9 (88.7) | 12.40 ms | 51.2 (51.4) | 21.34 ms |
| coast-day | 87.6 (86.9) | 11.98 ms | 49.9 (50.1) | 21.43 ms |
| coast-night | 105.2 (104.5) | 10.46 ms | 52.4 (51.7) | 20.48 ms |
| gulf-sea | 111.0 (112.5) | 9.52 ms | 61.1 (61.0) | 17.45 ms |
| helm-eye | 92.2 (91.3) | 11.76 ms | 54.6 (54.3) | 20.03 ms |
| slip | 74.0 (73.8) | 15.61 ms | 46.3 (46.1) | 24.05 ms |
| bridge | 97.8 (98.2) | 10.88 ms | 56.3 (56.3) | 19.02 ms |
| crew | 118.5 (118.5) | 8.53 ms | 68.8 (68.9) | 15.85 ms |
| marina-night | 91.0 (91.4) | 12.82 ms | 58.8 (58.8) | 18.98 ms |

- **bench-phase5** (Medium, packaged, 12 s; `phase5-bench.csv`). The main column is galveston-2's run
  (`docs/galveston-2/phase5-bench.csv`, Oct 15):

| View | fps (main) | p99 |
|---|---|---|
| coast-day | 86.9 (87.3) | 12.01 ms |
| coast-bay | 80.2 (80.7) | 13.37 ms |
| coast-night | 103.4 (103.1) | 10.66 ms |
| coast-dusk | 111.3 (114.1) | 9.75 ms |
| chart | 119.7 (119.8) | 8.87 ms |
| chart-bay | 119.7 (119.6) | 8.78 ms |

  coast-dusk reads 2.8 fps under galveston-2's number, so I measured it again with and without the moored boats
  (`-SailingPiersSkip=boats`, two runs each, alternating). Without them it ran at 110.3 and 111.5 fps; with them, at 111.7
  and 110.6, plus 113.2 in a separate rerun. The boats cost nothing measurable in that view, and today's runs sit
  about 2 fps under galveston-2's. Every other view is within 0.5 fps.
