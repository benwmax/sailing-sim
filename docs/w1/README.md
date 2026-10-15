# W1: Wind 2.0

The wind used to be a sum of sines: gust bands and shift bands sliding downwind at the mean speed. It is now three
seeded layers. Each is a function of place and time only, so it is the same at any frame rate, and each sits in a frame
that drifts with the air. When the wind changes direction, that frame is re-anchored at the boat, not at the map origin.
The calibration comes from free station data.

![The puff field and the whole field, 4 km square](puff-map.png)

`Tools/wind/plot_field.sh 7 15 12`: Lake Ray Hubbard, July, 15:00, 12 kn from the south. North is up and the arrows
show where the air goes. In the left panel each puff is veered and its east side fans further right, its west side to
the left (since the follow-up below, the puffs are 550 m streaks inside kilometre cells; W1 had 1.5 km puffs, about 45 %
over the mean). The right panel adds the fine turbulence and the slow shifts.

## The field (`Wind.h`, `Wind.cpp`)

| Layer | What it is | Frame |
|---|---|---|
| Convective puffs | Cells on a lattice. Each cell hosts one puff per generation, with its own lifetime (240 to 1440 s) and phase. A puff lands, grows over 20 to 40 s, holds, then fades over the last 45 % of its life. Its shape is (1 − r²)², elliptic. Strength varies 0.7 to 1.3. | The lattice lies along the surface wind. It drifts with the wind aloft: 1.25× the 10 m wind (+0.25 stable, −0.1 unstable), veered 6° (12° in stable air). A point on the water is therefore crossed by lane after lane. |
| Fine turbulence | A Mann (1994) slice from DTU's Hipersim: L = 30 m, Γ = 3.9, 256 × 256 at 2 m (a 512 m tile), u and v. Each along-wind line's mean is removed. Stored in `Content/TerrainData/Wind.mann` (256 KB, LFS, staged with TerrainData). | Frozen flow at the mean 10 m wind. It is read on a line slanted 1 in 7.3 across the tile, so a fixed point never sees the tile repeat. |
| Slow shifts | Oscillating shifts: three incommensurate sines over a wavelength of U × `ShiftPeriodSeconds`, a little ragged across the wind. Persistent shifts: a swing over about an hour, the same everywhere. | Oscillating shifts drift with the mean wind; persistent shifts depend on time only. |

- **Puff sizes:** across, the geometric mean of 0.6 × the mixed-layer depth and (drift speed × calibrated puff interval) ÷ (1.3 × elongation), held to 0.3–3 km. Streets: puffs are elongated along the wind by 1 + 1.5 × smoothstep(4.5, 8.5 m/s), less so in stable air. The lattice spacing is 1.3 puffs.
- **Puff veer and fan:** a puff veers by `PuffVeerDegrees` (7) times its strength over its mean. Each side fans outward by `PuffFanDegrees` (20) at the flank's peak. Lulls back slightly (−0.8° on average). Both scale down for weak puffs.
- **Normalisation:** the puff field's spatial mean and spread come from closed-form integrals, so the gust factor averages to 1. Over the water it measures 1.001–1.006. The puff amplitude is capped at 0.45 (the strongest puffs reach about +50 %).
- **Stability:** air minus water temperature gives a bulk Richardson number, then z/L by Businger-Dyer. This sets:
  - the height profile, ln(z/z0) − ψm(z/L), normalised at 10 m. Warm over cool: 20 m/10 m = 1.156; neutral 1.064; cold over warm 1.034. At zero difference it is exactly the old log profile, so the polars are unchanged.
  - puff strength: +40 % unstable, −40 % stable, but no stable damping when the mixed layer is deep. On a hot afternoon over a small lake the puffs come down from the land's convection overhead.
  - the drift speed and veer aloft.
- **Gust front and storm outflow:** blended over everything as before.
- **Shore effects (`FShelterMap`):**
  - **Lee:** behind terrain, the tree canopy and houses (the G6 footprints, ridge above ground). The deficit is 0.62 × (1 − smoothstep(4, 30, distance/height)): deepest within 4 heights, about half at 10, gone by 30.
  - **Open-water build:** 0.8 + 0.2 × (1 − e^(−fetch/800 m)) from the upwind shore.
  - The march reaches 1 km for lee and 3 km for fetch, and stops at the edge of the bake. The shelter map builds in about 40 ms on a worker. WindNinja is skipped, as asked.
- **What a sailor reads:** `ReadableAt` gives puffs, shifts and lee, without the seconds-long turbulence. The AI uses it.

## Calibration (`WindClimate.h`, `WindClimate.cpp`, `Tools/wind`)

`Tools/wind/fetch_wind.sh` fetches 2024 data into `Data/Wind/raw` (git-ignored); `Tools/wind/fit_gusts.py` fits it (full
table in `gust-calibration.csv`):

**Lake: NCEI ASOS one-minute data** (TD-6405 page 1: 2-minute mean and the highest 5 s wind each minute):
- Stations: Dallas Love Field (KDAL), Terrell (KTRL) and Dallas Executive (KRBD). Mesquite (KHQZ) is not in the one-minute archive.
- Gust factor = Σ 5 s peaks / Σ 2-minute means, over minutes with a mean of 8 kn or more.
- The stations are over grass, so this is an upper bound. (GF − 1) is scaled by ln(10/0.03)/ln(10/0.0002) = 0.54 for open water.
- Puff strength = RMS of the 2-minute mean around its 31-minute running mean, times √0.54.
- Puff timing = median minutes between peaks of the 2-minute mean (more than half a running SD above the running mean, at least 2 minutes apart).

**Coast: NOAA CO-OPS** Galveston Bay stations 8771341 (North Jetty), 8771013 (Eagle Point) and 8770613 (Morgans Point):
- Their 6-minute reports already measure over water.
- The gust is a 6-minute peak, so (GF − 1) is scaled by the Gaussian peak-factor ratio √(2 ln 12) / √(2 ln 72) = 0.76 to match a 1-minute window.

| Season | Lake GF (water) | Coast GF (1 min) | Puff strength (lake, water) | Minutes between puffs |
|---|---|---|---|---|
| Dec–Feb | 1.178–1.192 | 1.166–1.195 | 0.076–0.092 (peak 12–15 h) | 6 |
| Mar–May | 1.182–1.190 | 1.164–1.177 | 0.079–0.100 | 6–7 |
| Jun–Aug | 1.165–1.188 | 1.151–1.178 | 0.071–0.119 (peak 12–15 h) | 6–7 |
| Sep–Nov | 1.175–1.188 | 1.152–1.180 | 0.075–0.106 | 6–7 |

With a mean of 8 kn or more, the gust factor hardly changes through the day; the puffs carry the daily cycle.

**How the table reaches the field:**
- The field's gust factor rises with its fine turbulence as GF = 1 + 1.50 σ (measured with `MeasureGustStats` over 6–14 kn, ±4 °C and two mixed layers; `GustIntensityForFactor`).
- Its 2-minute spread is 0.83 × the puff layer's σ.
- The weather sets `GustIntensity` and `PuffIntensity` from the table for the month, hour and water, times the preset's gustiness: calm morning 1.75, afternoon breeze 1, overcast 0.6, rain 1.25, thunderstorm 0.75 → 1.25.
- **Stability inputs:**
  - Air: NOAA 1991–2020 normals (DFW and Galveston highs and lows) on a daily cycle, coldest 06:30, warmest 15:30. Cloud holds it near the daily mean.
  - Water: monthly means for north Texas reservoirs and NOAA's Galveston coastal water guide.
  - Mixed layer: 250 m at night up to 0.85–2.2 km on afternoons (by month); shallower and flatter at sea.
- The game passes the session month and the world (`FWeatherSystem::SetClimate`).

Measured against the stations (`SailingSim.Physics.WindPuffStatistics`, weather wind at 12 kn, 6 points × 6 h):

| Case | GF field / stations | 2-min spread | Puffs every |
|---|---|---|---|
| Lake, July 15:00 (air − water +5 °C, layer 2.2 km) | 1.178 / 1.180 | 0.089 / 0.111 | 10 / 7 min |
| Lake, January 10:00 (−3.5 °C, 370 m) | 1.191 / 1.188 | 0.076 / 0.083 | 7 / 6 min |
| Bay, April 13:00 (+1.4 °C, 960 m) | 1.178 / 1.176 | 0.081 / 0.099 | 8 / 6 min |

The Mann tile is made by `Tools/wind/make_mann_slice.py`. It has a numpy fallback (the same tensor without Hipersim's
high-frequency compensation, `--numpy`); that fallback is only approximate (v/u 0.87 against Hipersim's 0.92).

## AI sailboats

`FTrafficSim` boats now steer by the wind where they are (`LocalWindFrom`, the readable wind): close-hauled in a lift
they point higher, and the autopilot holds the TWA in that wind. Laylines stay against the median wind. Upwind they
tack:
- on a header of more than 7° from the median,
- or for 12 % more pressure 200 m along the other tack,

with at least 45 s between tacks (60 s for pressure), and never onto a tack that leads away from the mark. Race tactics keep the course axis for
the start and the finish.

`scripts/traffic.sh 98` now runs the 16 races twice: in the old steady 12 kn, and in an afternoon breeze with the
calibrated puffs and shifts.

| | Finished | Race time | Collisions | Tacks per boat |
|---|---|---|---|---|
| Steady (as before, unchanged) | 16 of 16, 5 of 5 each | 1473–2096 s | 0–2 | about 13 |
| Shifty (W1) | 16 of 16, 5 of 5 each | 1668–2006 s | 0–1 | about 19 |

## Tests

- **Rewritten:**
  - `Physics.WindField`: profile and stability; spatial mean 1.006; frozen fine flow exact; puffs drift at 1.25× and 6° veered.
  - `Physics.DeterministicAndFrameRateIndependent`: the full W1 field re-applied every frame at 30 and 120 fps gives an identical boat.
  - `Weather.GustsVisibleBeforeTheyArrive`: a puff 400 m up its track arrives within 0.01; a 150 m patch of water there now correlates 0.82 with the boat's wind 52 s later.
  - `Weather.ThunderstormSequence` (11.8 kn before, outflow 24.3 kn gusting 32.1).
  - `Lake.WindShadowAndFetch`.
  - `Physics.ReferenceChecks` (top speed and capsize, below).
- **New:**
  - `Physics.WindPuffStatistics`: the table above. Also: unstable air is puffier (0.45 against 0.34); streets at 18 kn; round cells at 6 kn.
  - `Physics.WindPuffVeersAndFans`: strongest puff +46 %, veered 7.8°, +27.9° on its right and −18.2° on its left, lulls −0.8°, twice the veer turns twice as far.
  - `Physics.WindSameAtAnyFrameRate`: 30 against 144 fps is exact while steady, and within 0.14 % and 0.07° while the breeze builds 3 kn and veers 10°. A 10° swing 12 km from the origin leaves the puff at the boat unchanged.
  - `Lake.ShelterBandBehindTrees`: 12 m treeline: lee 0.38 at 3 heights, 0.48 at 10, 0.85 at 20, 1.00 at 32. Open-water build 0.81 at 40 m, 0.96 at 1.2 km. A row of houses gives 0.46 at 100 m, against 1.00 for the bare bank.
- **Reference checks:**
  - The J/22 gusty spinnaker run (a known gap since V3 at 12.1 kn) is in range at 11.24 kn.
  - The ILCA 7 top-speed check now sails 16 kn gusting 22 at 120° (peak 13.3 kn). The autopilot and auto-trim capsize her on a 22 kn broad reach even in steady wind; main only passed because its first 30 s fell in a lull, so the peak was taken before she went over.
  - Still out, as on main: Catalina 22 DPN2 and Hobie 16 DPN4.
- `scripts/polar.sh --quick`: 0 of 39 points out (unchanged: the polars run in neutral, steady air).
- `scripts/test.sh`: 107 of 107.

## Cost

One `VelocityAt` costs 107 ns against 58 ns before (standalone, 4 M calls). The cat's-paw map samples 4,096 points a
frame across worker threads; the boats sample a few hundred per physics step.

On `scripts/bench-visual.sh 12 <label> Medium High` (packaged Development; main 3fb925a against this branch, the same
evening), the game thread is +0.016 ms on average on Medium and +0.021 ms on High (at most +0.04). No GPU work was added.

| View | Tier | Game ms before | After | fps before | After |
|---|---|---|---|---|---|
| beam8 | Medium | 1.92 | 1.94 | 93.0 | 90.6 |
| beam8 | High | 2.69 | 2.71 | 56.9 | 56.5 |
| beat15 | Medium | 1.93 | 1.95 | 91.6 | 91.0 |
| beat15 | High | 2.61 | 2.63 | 55.3 | 55.3 |
| storm | Medium | 2.19 | 2.19 | 72.9 | 72.1 |
| storm | High | 2.92 | 2.96 | 47.3 | 47.2 |
| marina | Medium | 1.92 | 1.94 | 89.0 | 89.8 |
| marina | High | 2.44 | 2.44 | 51.8 | 51.7 |
| coast-day | Medium | 2.10 | 2.13 | 84.7 | 85.3 |
| coast-day | High | 3.10 | 3.08 | 50.4 | 49.8 |
| coast-night | Medium | 1.96 | 1.99 | 104.7 | 103.2 |
| coast-night | High | 2.75 | 2.79 | 53.3 | 55.8 |
| gulf-sea | Medium | 1.93 | 1.95 | 110.9 | 112.3 |
| gulf-sea | High | 2.82 | 2.84 | 62.6 | 62.0 |
| helm-eye | Medium | 1.98 | 1.99 | 83.9 | 84.5 |
| helm-eye | High | 2.94 | 2.96 | 48.7 | 48.5 |
| slip | Medium | 2.01 | 2.01 | 76.2 | 77.1 |
| slip | High | 2.71 | 2.74 | 47.1 | 47.0 |
| bridge | Medium | 1.92 | 1.92 | 100.0 | 102.4 |
| bridge | High | 2.74 | 2.78 | 55.8 | 58.9 |
| crew | Medium | 2.16 | 2.17 | 74.4 | 74.7 |
| crew | High | 2.87 | 2.88 | 47.2 | 47.6 |
| marina-night | Medium | 1.83 | 1.86 | 82.7 | 82.6 |
| marina-night | High | 2.27 | 2.30 | 54.1 | 54.3 |

Gate: every view is at or above 72 fps on Medium (gate 60) and 47 fps on High (gate 45). The CSVs and per-system
game-thread `-gt` files are `visual-bench-w1-before*.csv` and `visual-bench-w1-after*.csv`.

## Screenshots

Lake, 12 kn afternoon breeze from the south, 15:00, High, uncooked (`scripts/run-game.sh`, `-SailingCapture=Drone`).

| | Before (main) | After (W1) |
|---|---|---|
| Low camera, 8 m, looking upwind (`-SailingCamWorld=0,0,8,180,-2`) | ![](w1-low-before.png) | ![](w1-low-after.png) |
| Drone at 400 m (`-SailingCamWorld=0,0,400,180,-22`) | ![](w1-drone-before.png) | ![](w1-drone-after.png) |

The cat's-paw map reads the new field without changes; the W0 edge fade still blends it to the mean at 800 m. From the
low camera the puffs are broad darker bands in the middle distance. The fine turbulence breaks up the near water. From
the drone, the lee band along the upwind shore lies glassy (it reflects the clouds) before the wind builds over open
water. The fanning is in the direction field, not in the roughness map, so the map above shows it.

## Skipped or changed, and why

- Mesquite (KHQZ) is not in NCEI's one-minute archive; Dallas Executive (KRBD) took its place.
- WindNinja was skipped, as the brief said; shore effects are analytic.
- The ILCA 7 top-speed check was moved to 16 kn gusting 22 (reason above). The handling gap belongs on the fix list.
- `GustLengthMeters` is gone; puff sizes come from the mixed layer and the timing.
- `GustIntensity` now means the fine turbulence's σ when `PuffIntensity` is set, which the weather always does.
  `-SailingGust` / the session's gust knots convert through the same gust factor.
- Easy mode halves both intensities and the shifts.
- `scripts/polar.sh`, `traffic.sh` and `reference-checks.sh` now run their binaries from the repository root, so the
  standalone tools find the Mann tile.

## Follow-ups: kilometre cells, Laser heavy-air handling

**Kilometre cells.** The PC's first LES (a North Texas summer afternoon, `docs/water-6/les-pilot.md` on `w6-les-pilot`)
put most of the gust energy in lulls and puffs 2 to 5 km across, with the 250 to 500 m streaks inside them. The field
now has that layer:

![The field over 12 km: kilometre lulls and gust patches, streak puffs inside them](puff-map-cells.png)

`Tools/wind/plot_field.sh 7 15 12 6000 docs/w1/puff-map-cells.png`: the same July afternoon over a 12 km square.

- **Cells:** 12 seeded waves with wavelengths spread evenly (in log) over 1 to 2.5 mixed-layer depths, held to 2 to 5 km,
  in all directions (stretched along a breeze like the streets). The sum is band-limited by construction, which value
  noise is not: interpolated lattice noise put half its variance beyond 8 km. Each wave's phase drifts, so the pattern
  re-forms in 20 to 40 min. The cells sit in the puffs' frame, drifting with the wind aloft.
- **Share:** `CellShare` (0.65, the LES's "about two thirds") of the puffs' variance; 0 gives the W1 field. The stations'
  2-minute spread splits between the cells and the puffs, and each converts to its own field spread by how much of it a
  2-minute mean keeps (`kCellSlowRms` 0.80, `kPuffSlowRms` 0.83).
- **Puffs inside them:** with cells on, the puffs are the streaks: a quarter of the mixed layer across (0.3 to 1 km), and
  they are scaled by 1 + 0.6 n inside the cells (n the cell field, unit spread; held to 0.2 to 1.8). A big gust patch
  veers by 0.15 × `PuffVeerDegrees` per unit, and a lull backs.
- **Calibration kept:** the gust factor's slope on the fine turbulence went from 1.50 to 1.58 (the streaks pass within a
  minute). Gust factor, field and stations, now: July afternoon 1.184 / 1.180, January morning 1.188 / 1.188, April bay
  1.175 / 1.176. Puffs every 6 to 8 min (stations 6 to 7).
- **Test:** `SailingSim.Physics.WindPuffsAtTwoScales`: along the wind, the puff layer's variance is 62 % at 2 to 8 km
  wavelengths and 12 % at 250 m to 1 km (the W1 field: 68 % and 0 %).

**Laser heavy-air handling.** The autopilot and auto-trim capsized the ILCA 7 on a 22 kn broad reach in steady wind.
The traces showed four faults: the trimmer sheeted *in* as she rounded up (the apparent wind came forward); a late,
slow ease with the sailor still fully hiked whipped her over to windward; the eased main then death-rolled her on the
bear-away; and at 13 to 14 kn she overruns the 10-knot lake waves, buries the bow 12 to 17°, the rudder comes out and
she spins out. A dinghy sailor fixes these with the sheet in the hand and their weight. Dinghy-only knobs
(`DinghyEasePerHeelDeg`, `DinghySheetRate`, `CrewAftRange`, 0 for the keelboats, so the J/22 polar is untouched):

- dump 2° of boom per degree of heel past the limit (and of the roll toward it) at once, at 2.5 sheet travel per second;
- never trim in while still overpowered, and after a dump trim back on at 0.25 per second, not in step with the roll;
- sheet in hard (never ease) as she rolls to windward;
- come in off the hike twice as fast;
- slide aft as she gets on the plane (Froude 0.5 to 0.9), up to 0.5 m: a new fore-and-aft crew position in the model
  (`FBoatControls::CrewAft`, `FBoatState::CrewOffsetX`).

Steering under the heel (bear away past the limit, luff on a windward roll) was tried and made the gusty runs worse, so
it was left out. Over 16 runs each (100 to 130°, four wave seeds), main capsized 12 in a steady 22 kn and 11 at 16 kn
gusting 22; this branch capsizes 1 and 2. `scripts/polar.sh --quick` is 0 of 39 out; the ILCA's own polar is 0 of 15
(worst 12.7 %, was 12.0 %).

The reference checks now measure top speed the way GPS does (the best one-second mean, not one 120 Hz step) and require
the boat to stay up (under 70° of heel, where the model counts a capsize). "ILCA 7 broad reach, 22 kn" is back (steady
wind, 15.5 kn peak). "16 kn gusting 22" now uses gust intensity 0.14, which is what puts the 99th percentile of the
one-second wind at 22 kn; 0.25 put it at 27 (and the J/22's "20 kn gusting 25" run likewise went from 0.2 to 0.10:
with the cells, 0.2 meant gusts to 31 kn and a 12.2 kn peak against the 12 kn cap; at 0.10 it peaks at 11.5). The
Laser's gusty check stays a known gap: W1's biggest puffs (25 to 27 kn) drive her
past 16 kn, where the planing drag is uncalibrated (the residuary table is flat above Froude 1.3). She buries the bow and
the rudder comes out.
