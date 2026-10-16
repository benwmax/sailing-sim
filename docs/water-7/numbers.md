# W7 Proof: the numbers against real data

This page is the numbers half of W7 Proof. It checks the game's wind, whitecaps, waves and boats against measured or
published values. Each row gives the real value and its source, the game's value and the command that produced it,
the difference, and a verdict. Everything here was run on main 4c2584ca (W3 merged) on the Mac, on Oct 15 2026.

Raw output in this folder:
- `reference-checks.csv`: `scripts/reference-checks.sh --csv`, the full set.
- `tests.txt`: the automation tests' own messages.
- `puffs.txt`: `scripts/w7-numbers.sh`.
- `wave-check.txt`: `scripts/wave-check.sh --map`.

## Known gaps

1. **Puffs veer in the game but not at the stations.** At a puff's peak, the stations' 2-minute wind backs slightly
   (median -0.4 deg, -0.36 deg per +10 % of strength). The game's veers (median +1.4 deg, +1.27 deg per +10 %). The
   veer is designed in: `PuffVeerDegrees` (7) times strength, from momentum brought down from aloft. Two things weaken
   the station side as a reference. These are land airports, not the lake, and a 2-minute mean blurs a puff that
   passes in under a minute. Even so, the records don't support a systematic veer. Verdict: **gap**. Either the veer
   should shrink, or it needs over-water evidence (a buoy or a club's anemometer).
2. **Portsmouth:** two classes are out of band. The Hobie 16 is too fast in DPN4 (12+ kn): 0.69 against 0.74-0.87.
   The Catalina 22 is too fast in DPN2 (4-7 kn): 0.93 against 0.96-1.13. Both are known from Phase 8. The
   `SailingSim.Physics.ReferenceChecks` test lists the Hobie as a known gap; the quick set doesn't run DPN2.
3. **Whitecaps measure high but read low.** The drawn sea's foam coverage is about twice Monahan at 14-25 kn. The lake
   is 2.2x its own fresh-water target at 20 kn, which is inside the test's factor of three. Yet the 20 kn open-lake
   still in round 11 (`docs/round-11/game/r11-lake-beat20.png`) shows almost no caps. So the coverage measured on the
   test's grid isn't what the camera shows. The blind round will say which one the eye agrees with.
4. **Lake 2-minute spread:** closed (Oct 16 2026). The day's stability was scaling the puffs on top of the station
   calibration, which already carries the season's. The puffs now scale by the day's departure from the month and
   hour's normal air (`FWindParams::ClimateAirMinusWaterC`, `ClimateMixedLayerMeters`, set by the weather). The January
   morning went from 0.104 to 0.085 (0.083 at the stations), the bay's April midday from 0.080 to 0.096 (0.099), and
   July stays 0.113 (0.111). A front's cold air still makes bigger puffs. `SailingSim.Physics.WindPuffStatistics` now
   holds each case within 10 %.
5. **Wave period at light wind:** the lake-wide Tp is +8 % at 5 kn. The 24 short components share one scale (W3).
   Heights are within 3 %.
6. **North lake below the SH-66 causeway:** Hs is 1.38x SWAN. The causeway's openings aren't in the fetch march.
7. **Galveston Bay has no SWAN comparison yet.** The PC's bake was at 91 of 112 cases. The bay rows follow when it
   lands.

## Wind: gusts and lulls against the IEM stations

Real data: ASOS one-minute records for 2024 from IEM, for KDAL, KRBD and KTRL around Ray Hubbard (`Tools/wind/
fetch_wind.sh`). The fits come from `Tools/wind/fit_gusts.py` (`docs/w1/gust-calibration.csv`) and the puff shapes from
`Tools/wind/puff_shape.py`. The game is the weather's wind field at 12 kn, measured the same way.

| Quantity | Real (source) | Game (command) | Difference | Verdict |
|---|---|---|---|---|
| Gust factor, lake, July afternoon | 1.180 (stations, over water) | 1.184 (`SailingSim.Physics.WindPuffStatistics`) | +0.3 % | ok |
| Gust factor, lake, January morning | 1.188 | 1.188 (same test) | 0 | ok |
| Gust factor, bay, April midday | 1.176 | 1.175 (same test) | -0.1 % | ok |
| 2-minute spread, lake, July afternoon | 0.111 | 0.113 | +2 % | ok |
| 2-minute spread, lake, January morning | 0.083 | 0.085 (was 0.104) | +2 % | ok (gap 4 closed) |
| 2-minute spread, bay, April midday | 0.099 | 0.096 (was 0.080) | -3 % | ok (gap 4 closed) |
| Minutes between puffs (lake July / Jan, bay April) | 7 / 6 / 6 | 7 / 8 / 6 (same test) | 0 / +2 / 0 min | ok |
| Puff duration, median (p25-p75) | 2 min (1-4), 41,411 puffs | 2 min (2-3), 942 puffs (`scripts/w7-numbers.sh`) | median equal; game's spread narrower | ok |
| Puff strength at the peak, median | +13.1 % | +11.2 % (same) | -1.9 points | ok |
| Veer at the puff's peak, median | -0.4 deg | +1.4 deg (same) | +1.8 deg | gap (1) |
| Veer per +10 % of strength | -0.36 deg | +1.27 deg (same) | +1.6 deg | gap (1) |

The puff runs sample four cases (January 09:00, April 12:00, July 15:00, October 15:00) for 6 hours each, at six points
2.7 km apart. They use the stations' rule: a puff is a run of 2-minute means at least half a running standard deviation
above the 31-minute mean, with the mean at 8 kn or more.

## Whitecaps against Monahan, scaled for fresh water

Real data: Monahan and O'Muircheartaigh (1980), W = 3.84e-6 U^3.41 (U in m/s at 10 m), for salt water. Fresh water
foams less. W0 took 0.4 of Monahan for the lake and 0.7 for Galveston Bay, as literature values: there were no lake
photos of whitecaps at a known wind to tune against. The game's numbers come from `SailingSim.Visual.Whitecaps`
(coverage on the drawn waves, with M_WaterV4's threshold mirrored by `AWaterSurface::WhitecapThreshold`).

| Wind | Monahan, salt | Game, sea | Lake target (0.4) | Game, lake | Bay target (0.7) | Game, bay | Verdict |
|---|---|---|---|---|---|---|---|
| 10 kn | 0.10 % | 0.14 % | 0.04 % | 0.06 % | 0.07 % | 0.10 % | ok (1.4-1.5x) |
| 14 kn | 0.32 % | 0.67 % | 0.13 % | 0.26 % | 0.22 % | 0.46 % | ok (2.0-2.1x) |
| 20 kn | 1.09 % | 2.29 % | 0.44 % | 0.96 % | 0.76 % | 1.70 % | ok in the test's 3x; see gap 3 |
| 25 kn | 2.33 % | 3.95 % | 0.93 % | 1.76 % | 1.63 % | 2.93 % | ok (1.7-1.9x) |

Since W3's steeper growth above 18 kn, the sea makes about twice the foam W0 measured (W0: 1.41 % at 20 kn, now
2.29 %). Puffs and lulls still bracket the mean: on the lake at 20 kn, a 1.3x puff gives 2.25 % and a 0.7x lull 0.24 %.

## Waves against the SWAN bake (Ray Hubbard)

Real data: the PC's SWAN bake of Ray Hubbard (16 directions x 7 speeds on a 50 m grid; `swan-bake.md` on
w3-swan-bake). It's a model, not buoy data, but it is the best spectral reference the lake has. The game's numbers come
from `scripts/wave-check.sh --map` (`wave-check.txt`) and `SailingSim.Lake.SeaStateSwan`.

| Wind | SWAN Hs | Game sea map Hs | Error | SWAN Tp | Game Tp | Error | Verdict |
|---|---|---|---|---|---|---|---|
| 5 kn | 0.048 m | 0.047 m | -2.2 % | 0.91 s | 0.98 s | +8.2 % | ok; Tp gap (5) |
| 8 kn | 0.085 m | 0.087 m | +1.6 % | 1.14 s | 1.19 s | +4.6 % | ok |
| 11 kn | 0.125 m | 0.129 m | +2.8 % | 1.33 s | 1.36 s | +2.3 % | ok |
| 14 kn | 0.167 m | 0.170 m | +1.4 % | 1.49 s | 1.50 s | +0.5 % | ok |
| 18 kn | 0.238 m | 0.231 m | -3.0 % | 1.70 s | 1.66 s | -2.6 % | ok |
| 22 kn | 0.335 m | 0.311 m | -7.4 % | 1.99 s | 1.91 s | -4.1 % | ok |
| 28 kn | 0.493 m | 0.465 m | -5.7 % | 2.38 s | 2.26 s | -4.9 % | ok |

These are lake-wide medians over directions. The Tp column is the effective-fetch sea at the same medians (the first
table in `wave-check.txt`).

At the ten spectrum points, over all 112 cases (1,050 with SWAN Hs above 5 mm), the median absolute log error is 0.08
in Hs and 0.12 in Tp. The point medians, game over SWAN:

| Point | Game / SWAN | Verdict |
|---|---|---|
| Rush Creek Yacht Club | 1.11 | ok |
| Off Rush Creek, open water | 1.03 | ok |
| South lake, near the dam | 1.04 | ok |
| Chandlers Landing | 1.00 | ok |
| Harry Myers Park | 0.98 | ok |
| North lake, below the SH-66 causeway | 1.38 | gap (6) |
| Open water, three points | 0.89-1.03 | ok |

There's also a handbook check from Phase 8 (`reference-checks.csv`). At 15 kn over 8 miles, CEM/SPM shallow-water
gives Hs 0.43-0.47 m and Tp 2.2-2.6 s. The game gives 0.51 m and 3.02 s, both inside the 20 % tolerance. Tp is near
its top.

**Galveston Bay:** the bay rows are pending the PC's SWAN bake (91 of 112 cases at the time of writing).

## Tacking, heel and the rest of the Phase 8 checks

From `scripts/reference-checks.sh --csv` (the full set, `reference-checks.csv`). `SailingSim.Physics.ReferenceChecks`
runs the quick set, and it agrees row for row (`tests.txt`). The sources are in the CSV's last column.

| Check | Real (source) | Game | Difference | Verdict |
|---|---|---|---|---|
| J/22 heel close-hauled, 6 / 8 kn | 3-4 deg (North Sails J/22 guide) | 4.0 / 3.9 deg | within | ok |
| J/22 heel close-hauled, 10 / 12 / 14 kn | nearly flat, under 12 deg, to about 14 kn (North, Quantum) | 6.7 / 11.3 / 12.3 deg | 14 kn is 0.3 over 12, inside the 3 deg tolerance | ok |
| Catalina 30 heel, 6 / 10 / 12 / 16 kn | owners' table (4 / 15 / 17 / 21 deg, ±3) | 4.0 / 13.9 / 19.4 / 22.5 deg | within | ok |
| Catalina 30 heel, 20 kn, one reef | 22 deg ±3 | 22.6 deg | +0.6 | ok |
| J/22 tacking angle, 10 kn | 75-90 deg | 76.1 deg | within | ok |
| Hobie 16 tacking angle, 10 kn | 90-100 deg | 91.1 deg | within | ok |
| ILCA 7 best upwind TWA, 10 kn | 40-46 deg (Day 2017 VPP) | 42.8 deg | within | ok |
| J/22 natural roll period | 2.0 s (IMO A.562 from the ORC righting moment) | 1.87 s | -6.5 % | ok |
| Ray Hubbard Hs / Tp, 15 kn over 8 mi | 0.43-0.47 m / 2.2-2.6 s (CEM/SPM) | 0.51 m / 3.02 s | +9 % / +16 % | ok (inside 20 %) |
| J/22 spinnaker 135 deg, 20 kn steady | 9.40 kn (ORC certificate) | 9.79 kn | +4.1 % | ok |
| J/22 spinnaker run, 20 gusting 25: peak | 9-12 kn bursts | 11.53 kn | within | ok |
| J/22 running, 30 kn reefed: peak | about 14-15 kn, 16 record | 12.39 kn | within 9-16 | ok |
| ILCA 7 broad reach, 22 kn: peak | about 15 kn GPS | 15.51 kn | within | ok |
| Capsize and recovery (11 rows) | see the CSV | all within | | ok |
| Portsmouth ratios to the ILCA (16 rows) | US Sailing 2017 D-PN | 14 within | Hobie 16 DPN4 0.69 (0.74-0.87), Catalina 22 DPN2 0.93 (0.96-1.13) | 2 gaps (2) |

## Reproduce

```bash
scripts/reference-checks.sh --csv
```

```bash
scripts/w7-numbers.sh 6
```

```bash
scripts/wave-check.sh --map
```

```bash
scripts/test.sh "SailingSim.Physics.ReferenceChecks+SailingSim.Physics.WindPuffStatistics+SailingSim.Physics.WindPuffVeersAndFans+SailingSim.Physics.WindPuffsAtTwoScales+SailingSim.Visual.Whitecaps+SailingSim.Lake.SeaStateSwan"
```

`scripts/w7-numbers.sh` is new. It builds `Tools/wind/PuffShape.cpp` with SailingPhysics standalone and runs both sides
through `Tools/wind/puff_shape.py`. The stations need `Data/Wind/raw/asos` (`Tools/wind/fetch_wind.sh`; git-ignored).
