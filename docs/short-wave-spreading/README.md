# One spreading law for the long and short waves (Oct 24 2026)

The lake's sea was cos^2 about the wind at every frequency: 90 deg wide at half height. Measured wind seas are much
narrower at the peak and widen away from it. Both halves of the sea now follow the measured spreading:

- **Long waves (`FWaveField`).** Donelan, Hamilton and Hui (1985), `D = 0.5 beta sech^2(beta theta)`:
  - `beta = 2.61 (f/fp)^1.3` below 0.95 fp (held at its 0.56 fp value further down);
  - `beta = 2.28 (f/fp)^-1.3` from 0.95 to 1.6 fp;
  - Banner (1990) beyond 1.6 fp.

  The result is 44 deg wide at half height at the peak, 105 deg at 2 fp and 145 deg at 3 fp. The code is
  `FWaveField::SpreadingBeta` and `DirectionalSpreading`.
- **Short waves (`FWaveDetail`).** The FFT uses the same function. It keeps its 10% floor in every direction.

## The long waves' directions

Each band has three components. Before, they were 120 deg apart at a random offset, so a band's main direction could be
60 deg off the wind, and the band's offset differed from band to band. A narrower law can't make long crests out of
that.

`FWaveField::AnchorDirections` now lays each band out at -Delta, 0 and +Delta about the wind, each with up to 3 deg of
seeded jitter:

- Delta is `SideAngle(beta)`: the angle at which three weighted directions carry the spreading's mean cos(theta). It is
  37 deg at the peak and is capped at 75 deg.
- Frequencies are kept. Wavenumbers follow the water's depth.

`SetWind` lays the directions out on the first wind. After that, a wind shift only reweights energy over them. A turn
past 45 deg (`kReanchorRadians`, for example a storm's outflow) lays them out again about the new wind:

- The phases are chosen so the surface at `FWaveParams::HoldX/HoldY` doesn't move. The game mode puts that point at the
  boat.
- The renderer re-uploads `Wave%02d` when `GetDirectionGeneration` changes. The game mode rebuilds the sea map when it
  changes.
- Nothing is baked into M_Water or M_WaterV4, so no material rebuild is needed.

**The calibration sea is unchanged.** It keeps the constructor's directions and cos^2. Polar, scenario and reference runs
set `bCalibrationSea`, so the fleet's polars and reference checks don't move.

## The sea map

`FSeaMap::Build` weights the short-wave scale by the same spreading, normalized within each band as the field is. The
normalization matters with anchored directions. With the old 120 deg layout, cos^2 summed to 1.5 in every band, so
leaving it out was harmless. With anchored directions the sum differs from band to band, and leaving it out put the lake
median 9% low at 5 kn. `kSeaTowardWind` stays at 0.75: with the directions anchored, any value from 0 to 0.75 gives the
same medians to within 1%.

`scripts/wave-check.sh --map` (`wave-check.txt` here; `wave-check-main.txt` is main), lake median Hs against SWAN:

| kn | main | now |
|---:|---:|---:|
| 5 | -2.2% | +0.1% |
| 8 | +1.6% | +0.1% |
| 11 | +2.8% | +0.7% |
| 14 | +1.4% | +1.0% |
| 18 | -3.0% | -3.4% |
| 22 | -7.4% | -5.2% |
| 28 | -5.7% | -5.8% |

The median |log Hs error| over the 1050 point cases goes from 0.08 to 0.07.

## The calm shore (G5)

The g5-shore scene at 9 kn, measured as the reflection's up-down detail over the shore's:

| | up-down ratio |
|---|---:|
| the photo | 3.40 |
| main | 0.72 |
| this change | 0.70 |

`shore-9kn.jpg` shows the photo, then main, then this change. The near wavelets line up a little more across the wind,
but the reflection's measure barely moves. The photo's long regular streaks are not a matter of directional spreading.

`sea-16kn.jpg` shows the same scene at 16 kn: main on the left, this change on the right.

## Checks

These are unchanged:

- `SailingSim.Physics.PolarGate`
- `scripts/polar.sh --scenarios`
- `scripts/reference-checks.sh` (both identical to main)

These pass:

- `SailingSim.Lake.SeaStateSwan`
- `Visual.WaveMatch`
- the whitecap tests

`SailingSim.Physics.WaveSpreading` is new. `WaveBandGrowth` now snaps its target from the same field, because a field's
directions are set by the wind it started in.

## Follow-up: the 10 kn whitecaps on the PC

After the merge, `SailingSim.Visual.Whitecaps` failed on the PC at 10 kn: coverage 0.03% against Monahan's 0.10%, a
ratio of 3.3 against the test's factor of three. The Mac passed, at 18 of 40 000 vertices (2.3).

There were two causes.

1. **`SideAngle` was not deterministic across platforms.** It stepped Delta in 0.5 deg steps and stopped at the first
   step past the target. A last-bit difference in libm can stop a step earlier or later on another platform, which
   turns a band's side directions by half a degree. It is now a continuous solve: golden section for the least of the
   three-direction mean cos, then bisection below it. Platforms now differ in the last bits only. The side angle at the
   peak is 37.1 deg.
2. **The test's sample was too small for 10 kn.** Only about 0.06% of the surface folds at 10 kn. The chop is one
   periodic FFT tile, so each evaluation time is about one independent draw of it, and the test sampled four times. Its
   10 kn count ranged from 12 to 24 folds between builds and platforms, a quarter's noise around the limit.

   The test now samples 64 moments of 2 500 vertices each, the same 160 000 vertices in all. At 10 kn that gives 82
   folds and a ratio of 2.0. A separate fit on 320 000 vertices gave 1.7. At 12 to 25 kn the ratio is 1.16 to 1.35.
   The bound is unchanged.

The fallback curve (`FoamThresholdAt`, mirrored in M_WaterV4) is not refitted. On the larger sample it sits 0.004 to
0.013 under Monahan's threshold from 10 to 16 kn, as it did before. The game solves the threshold on the sea it draws
(`FWaveDetail::CapThreshold`) and uses the curve only as a fallback.
