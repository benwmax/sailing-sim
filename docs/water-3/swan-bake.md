# Water W3: a SWAN bake of the game's waters

The game's lake chop (`FWaveField`) takes its height and period from deep-water fetch-limited growth laws
(`TargetSignificantHeight`, `TargetPeakPeriod`: the SPM forms, Hs = min(0.0016 sqrt(gF/U^2), 0.243) U^2/g with U the
10 m wind) on the fetch the game marches straight upwind to the first land (`FLakeTerrain::FetchToward`, capped at 15
km). This bake runs a spectral wave model over the same waters to see where that holds.

## Method

- **Model:** SWAN (TU Delft's GitLab, built from source with gfortran under WSL2 Ubuntu 24.04; this build runs on one core whatever `OMP_NUM_THREADS` says, so `swan_bake.py run --jobs N` runs N cases at once instead), stationary,
  third-generation physics (`GEN3 WESTHUYSEN`, the whitecapping formulation calibrated for fetch-limited growth),
  depth-induced breaking, JONSWAP bottom friction (0.038), triads. 36 directions, 40 frequencies from 0.08 to 3 Hz.
- **Grids:** 50 m, averaged from the game's own height grids (`Content/TerrainData/<World>.height`). A cell is water if
  most of it is, with its depth the mean over its water.
  - Ray Hubbard at the 435.5 ft pool (the game's Z = 0): 543 x 327 cells, 33,265 wet.
  - Galveston Bay at mean tide (half the MHW above MLLW): 730 x 871 cells, 337,430 wet.
- **Cases:** wind from 16 directions x 5, 8, 11, 14, 18, 22 and 28 kn, uniform, as the game sets it.
- **Outputs:** Hs, peak period, mean direction and directional spread on every wet cell, plus 2D spectra at ten points
  per world (the bake's launch spots and checkpoints first). The outputs stay in WSL (`/root/swan-runs`) and are not in
  git; `summary.npz` and `spectra.json` per world are made by `swan_bake.py collect`.
- **Comparison:** `Tools/water/swan_compare.py` computes the game's fetch on the game's own 5 m / 10 m grid for every
  wet 50 m cell and direction, applies the game's laws, and writes `swan-compare.csv` (per world, direction and speed),
  `points.csv` (the ten points) and the figures.
- **Cost on the PC (i9-9900K, 16 threads):** Ray Hubbard 35 s a case at 5 kn up to about 8 min at 28 kn (112 cases in
  about 4 h). Galveston Bay about 5 min a case at 5 kn up to about an hour at 22-28 kn: 112 cases in about 30 h of wall time with two to four runners (`--jobs`; 28 kn cases 3,600-4,800 s each in parallel, 18 kn about 1,600 s run alone).

## Lake Ray Hubbard

Hs over every wet cell, all 16 directions (medians of each case's numbers, then the median over directions):

| Wind | SWAN Hs | Game Hs | SWAN / game (p10, median, p90) | Tp SWAN / game |
|---|---|---|---|---|
| 5 kn | 0.047 m | 0.052 m | 0.64, 0.85, 1.24 | 0.90 |
| 8 kn | 0.084 m | 0.082 m | 0.74, 0.95, 1.38 | 0.97 |
| 11 kn | 0.123 m | 0.113 m | 0.79, 1.02, 1.49 | 1.01 |
| 14 kn | 0.164 m | 0.143 m | 0.84, 1.08, 1.57 | 1.05 |
| 18 kn | 0.232 m | 0.184 m | 0.94, 1.16, 1.74 | 1.10 |
| 22 kn | 0.325 m | 0.225 m | 1.10, 1.35, 2.11 | 1.21 |
| 28 kn | 0.485 m | 0.286 m | 1.26, 1.61, 2.59 | 1.34 |

At the points, wind from the north and from the south at 14 kn (`points.csv` has every case):

| Point | Wind from | Game's fetch | SWAN Hs | Game Hs | SWAN Tp | Game Tp |
|---|---|---|---|---|---|---|
| Rush Creek Yacht Club | N | 135 m | 0.13 m | 0.04 m | 1.9 s | 0.6 s |
| Off Rush Creek, open water | N | 605 m | 0.17 m | 0.09 m | 2.0 s | 1.0 s |
| South lake, near the dam | N | 6.1 km | 0.26 m | 0.29 m | 2.2 s | 2.2 s |
| Off Rush Creek, open water | S | 3.0 km | 0.20 m | 0.20 m | 1.7 s | 1.7 s |
| North lake, below SH-66 | S | 2.9 km | 0.14 m | 0.20 m | 1.7 s | 1.7 s |
| Chandlers Landing | S | 640 m | 0.16 m | 0.09 m | 1.9 s | 1.0 s |

![Ray Hubbard: SWAN Hs / game Hs, wind from 225 deg at 14 kn](RayHubbard-ratio.png)

![Hs against the game's fetch](growth.png)

### What it says about the game

1. **In a moderate breeze over open water the game is right.** From 8 to 14 kn the median over the whole lake is
   within 5-8% of SWAN, for both height and period. On a long fetch it matches SWAN at the points (off Rush Creek 0.20
   against 0.20 m).
2. **In a strong wind the game's waves are too small.** SWAN is 16% higher at 18 kn, 35% at 22 kn and 61% at 28 kn.
   The SPM laws use the wind speed itself. The Coastal Engineering Manual's form of them uses the "adjusted" wind
   U_A = 0.71 U^1.23 (U in m/s), because wind stress on the water grows faster than the speed. That scales Hs by about
   0.98 at 8 kn, 1.10 at 14 kn, 1.19 at 18 kn and 1.31 at 28 kn: most of the gap. **Proposed:** use U_A in
   `TargetSignificantHeight` and `TargetPeakPeriod`.
3. **Near a lee shore the game's chop is far too small.** With a short fetch straight upwind (135 m at Rush Creek) the
   game gives 4 cm and SWAN 13 cm. The game's period there drops to 0.6 s against SWAN's 1.9 s. Real waves arrive
   from a spread of directions, so a spot sheltered dead upwind still sees chop grown along the lake. **Proposed:** an
   effective fetch, Saville's cosine-weighted mean of the fetch over +/-45 deg of the wind (the
   `FetchToward` march at nine directions), instead of the single ray.
4. **Shallow, sheltered bays the other way.** In the north arm below SH-66, with 2.9 km of fetch, SWAN is 30% lower
   than the game: the shallow water and the narrow arm limit growth. An effective fetch accounts for the narrowness;
   the depth limit could follow (`FLakeTerrain` has the depths).

## Galveston Bay

All 112 cases finished on Oct 16 2026 (the PC's runners died once at a reboot; finished cases were kept and the rest
resumed with `swan_bake.py run --jobs 2`). Hs over every wet cell, all 16 directions, the same way as the lake:

| Wind | SWAN Hs | Game Hs | SWAN / game (p10, median, p90) | Tp SWAN / game |
|---|---|---|---|---|
| 5 kn | 0.068 m | 0.118 m | 0.38, 0.60, 1.05 | 0.74 |
| 8 kn | 0.129 m | 0.189 m | 0.44, 0.73, 1.21 | 0.83 |
| 11 kn | 0.188 m | 0.259 m | 0.46, 0.77, 1.28 | 0.87 |
| 14 kn | 0.247 m | 0.330 m | 0.48, 0.80, 1.34 | 0.89 |
| 18 kn | 0.336 m | 0.424 m | 0.50, 0.84, 1.45 | 0.91 |
| 22 kn | 0.432 m | 0.518 m | 0.54, 0.88, 1.57 | 0.94 |
| 28 kn | 0.579 m | 0.659 m | 0.54, 0.91, 1.71 | 1.01 |

"Game" here is the law this bake set out to test: the deep-water SPM forms on the single upwind ray, U not U_A (the
same columns as the lake's table). W3 has since replaced it with the sea map (Saville fetch, U_A, sqrt TMA); comparing
SWAN with the sea map itself is the Mac's next step (`scripts/wave-check.sh --map`).

At the points, 14 kn from the north, south-east and south (`points.csv` has every case):

| Point | Wind from | Game's fetch | SWAN Hs | Game Hs | SWAN Tp | Game Tp |
|---|---|---|---|---|---|---|
| Galveston Bay, off Clear Lake | N | 15.0 km | 0.30 m | 0.45 m | 2.2 s | 3.0 s |
| Red Fish Bar | N | 15.0 km | 0.35 m | 0.45 m | 2.5 s | 3.0 s |
| Kemah channel, outbound | N | 3.6 km | 0.23 m | 0.22 m | 1.9 s | 1.8 s |
| Bolivar Roads | N | 1.1 km | 0.16 m | 0.12 m | 1.3 s | 1.2 s |
| Galveston Bay, off Clear Lake | SE | 3.5 km | 0.27 m | 0.22 m | 2.5 s | 1.8 s |
| Red Fish Bar | SE | 14.3 km | 0.34 m | 0.44 m | 2.5 s | 2.9 s |
| Bolivar Roads | SE | 3.3 km | 0.25 m | 0.21 m | 2.5 s | 1.8 s |
| Kemah, Clear Lake channel | S | 0.6 km | 0.16 m | 0.09 m | 1.7 s | 1.0 s |
| Clear Lake, off the yacht clubs | S | 0.4 km | 0.07 m | 0.07 m | 0.9 s | 0.9 s |

![Galveston Bay: SWAN Hs / game Hs, wind from 225 deg at 14 kn](GalvestonBay-ratio.png)

### What it says about the game

1. **The bay is depth-limited.** Unlike the lake, SWAN is 10-40% under the deep-water law over most of the bay, most of
   all in light air (median 0.60 at 5 kn, 0.80 at 14 kn) and on long fetches: off Clear Lake and on Red Fish Bar with
   15 km of fetch from the north SWAN gives 0.30-0.35 m against the law's 0.45 m, and 2.2-2.5 s against 3.0 s. The bay
   is 2-3 m deep; bottom friction and depth-limited growth (TMA) hold the sea down. W3's sqrt(TMA) factor on the sea map
   is the right correction; the numbers here say how much it must take off.
2. **Short fetches are still too small in the old law,** as on the lake (Kemah channel from the south: 0.16 against
   0.09 m; the "open" points with under 2 km of fetch: 0.27 against 0.10-0.16 m). W3's Saville effective fetch is the fix.
3. **In strong winds the two meet** (median 0.91 at 28 kn): the depth limit and the adjusted wind cancel out.
4. **Periods follow heights:** SWAN's Tp is 0.74-0.94 of the law's below 22 kn, longer than the law on short fetches.

**The grid is still the old one** (main before Galveston 2, #42): the southern boundary predates the Seawall, the
jetties and the Gulf front pack, so cases with wind from 112.5 to 202.5 deg near Bolivar Roads and the Texas City Dike
don't see the new coast. **Planned re-run:** those 49 cases on the #42 grid (main at or after 17a7da78), in a separate
work folder with `--jobs 4`, with the entrance points compared across both bakes.

The raw outputs stay in WSL (`/root/swan-runs/GalvestonBay`: `summary.npz` 391 MB, `spectra.json` 8.5 MB); this
commit carries `swan-compare.csv`, `points.csv` and the figures.
