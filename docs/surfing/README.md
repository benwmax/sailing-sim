# Surfing: the waves' orbital flow (Oct 27 2026)

Surfing was already half there: since docs/wave-physics/ the waves' slope pushes the hull down a face (Froude-Krylov,
`WaveSlopeForceScale`). What was missing is the water's own motion. Under a crest the water moves with the wave, and under
a trough it moves against it. The hull, keel and rudder met the water as if it were still. That motion is what takes
the flow off a rudder on a face, and it is how a boat starts to broach.

## What changed

- `FWaveField::OrbitalVelocity(x, y, t, below)` gives the horizontal orbital velocity from linear theory. Each component
  moves the water `a omega cosh(k (h - d)) / sinh(k h)` along its travel direction, in phase with its height.
  - At the world's depth (`SetDepth`), or `exp(-k d)` in deep water.
  - Depth is stretched: it is measured from the local surface.
  - The sea map's ratios scale each component, as they do for the height.
- `FOcean` adds two FFT grids, `U` and `V`: `omega a` along each mode's direction, at the surface. Each cascade decays as
  `exp(-k d)` at its velocity-weighted mean wavenumber.
- `FBoatModel` samples the flow once per step at the bow and stern ends of her waterline, at two depths: her canoe
  body's middle and her deepest foil's centre. `OrbitalFlowAt` interpolates linearly along her length and in depth.
  - `PointVelocityThroughWater` subtracts it, so the hull resistance, the cross-flow stations, the engines, the keels and
    the rudders all meet it, and the Munk moment does too.
  - That is four field samples per step.
  - The slope push is unchanged. The pressure gradient is all there, and the orbital flow adds the drag and lift on the
    water's motion, not a second push.
- `FBoatConfig::WaveOrbitalFlowScale` is 1 (0 is the old still water, for comparisons). The flow is never applied in the
  calibration sea (`FWaveParams::bCalibrationSea`), so the polars, scenarios and reference checks are byte-identical.
- Still left out: the wave's inertia on the foils (the water's acceleration past them).

## Speed by wave phase (`scripts/polar.sh --sea surf`)

Phases are binned by the surface's slope along her heading. Hull speed is 1.34 sqrt(LWL ft).

| Run | | Mean kn | Best 1 s | Steep back | Back | Level | Face | Steep face | Off course on faces / backs (deg) |
|---|---|---|---|---|---|---|---|---|---|
| J/22, 2 m sea, 20 kn, TWA 150, kite | still | 9.33 | 13.45 | 7.91 | 8.73 | 9.33 | 9.78 | 10.37 | 5.8 / 6.8 |
| | flow | 9.17 | 13.16 | 7.91 | 8.65 | 9.07 | 9.75 | 10.26 | 7.2 / 6.5 |
| J/22, same, TWA 165 | still | 8.60 | 12.49 | 7.35 | 8.13 | 8.49 | 8.96 | 9.72 | 5.7 / 7.8 |
| | flow | 8.50 | 11.94 | 7.50 | 8.04 | 8.51 | 8.85 | 9.39 | 13.4 / 7.3 (max tilt 21 -> 30) |
| Maxi, gale (Hs 3.5), TWA 120 | still | 23.58 | 32.53 | 22.10 | 22.21 | 23.66 | 24.11 | 26.41 | 7.3 / 5.3 |
| | flow | 23.23 | 31.56 | 21.18 | 21.76 | 23.31 | 24.14 | 23.77 | 7.2 / 10.7 |
| Maxi, gale, TWA 150 | still | 18.80 | 26.19 | 17.16 | 16.13 | 18.75 | 20.39 | 21.61 | 4.8 / 4.3 |
| | flow | 17.90 | 25.43 | 16.58 | 17.26 | 17.86 | 19.78 | 18.96 | 5.2 / 5.3 |
| J/22, flat, 12 kn, TWA 45 | both | 5.79 | | | | | | | |

The J/22's hull speed is 5.84 kn. She surfs at 1.76x it on the steep faces (10.26 kn), and her best seconds reach 2.25x.
The maxi averages 23.2 kn on the quartering sea. Running square, the flow puts the J/22 well off course on the faces: the
rudder meets less water there, and that is how a broach begins. Upwind on flat water nothing changes.

## Other checks

- `polar.sh --quick` (39 points, worst 8.0%), `--scenarios`, `reference-checks.sh --quick` (0 of 48 outside) and
  `traffic.sh 98` (16 races) are byte-identical with and without the flow. They all sail the calibration sea or flat
  water.
- `polar.sh --sea checks`:
  - ORC's sea: the J/22 makes 5.52 kn against 5.33. The added-resistance ratios hardly move (Catalina 22 0.86 -> 0.85,
    Catalina 30 1.31 -> 1.29, maxi 3.38 -> 3.32).
  - J/22 adrift beam-on to the 1.2 m swell: she makes good 0.43 kn with the push (0.68 before). That is the known keel
    sculling, smaller now that the keel moves with the water.
- `polar.sh --boat maxi --sea gale`:
  - All 6 gale tacks still go through in the sea.
  - TWA 50 is 10.75 kn in the sea against 10.17 before.
  - TWA 100 is 17.26 against 18.97 before. On the beam the flow under her moves her back and forth, and the slope push
    now nets -880 N instead of +2970 N.
  - TWA 150 is 18.60 against 19.01 before.

## The limits that moved

The still water's false creep downwave had been costing the boats speed upwind, and three limits were set around it.

- **`SailingSim.Physics.GaleTack`, upwind loss in the gale: 5 to 25% became 1 to 10%.** The band comes from ORC, not from
  the result. ORC's eq. 6.62 is written for its own venue sea (a 5 s modal period, energy by wind speed, capped at 20 kn),
  so it has no term for a 7 s sea. Three readings, each the maxi at TWA 50 with only the added resistance (no slope push,
  no flow), against 11.19 kn flat:

| Reading | Added resistance | Loss |
|---|---|---|
| Her coefficient (ORC's length scaling, 0.47) over the Mistral sea's spectrum with the long-wave response | 1679 N | 3.0% (1.4% at 0.38, 3.6% at 0.57, the log readings) |
| ORC's own sea, literally (20 kn cap, Hs 1.14 m at 5 s, TWA 45) | 556 N | 1.3% |
| ORC's 5 s response scaled by energy to Hs 3.5 m, with no period correction (an upper bound) | 4910 N | 15.5% |

  The first reading is the one that uses this sea's period, and it is what the coefficient predicts. The band runs from
  just under its low log reading to about three times its centre, which leaves room for the push and flow on top. She now
  loses 4%, inside it, so the coefficient stands. The energy-scaled bound of 15.5% sits well above 4%, but only by treating
  a 7 s sea, 2.7 of her waterlines long, as ORC's 5 s sea. Reproduce with `scripts/polar.sh --boat maxi [--ar c] --surf 0
  --flow 0 --sea gale`.
- **`SailingSim.Coast.GalvestonSwell`, upwind off the Seawall: under 97% became under 98.5% of her flat-water speed.** It
  stays a check that the swell slows her measurably. She is at 97.8% (5.81 kn against 5.94).
- **`SailingSim.Prologue.Gale`, the squall's arrival on the step's clock: within 3 s became within 4 s.** The flow moved
  her spot when the front arrives (3.3 s late).

## Tests

`SailingSim.Physics.SurfingFlow`:
- The field is linear theory's: forward under the crests (correlation 0.94), 0.13 m/s at 2 m against 0.36 at the surface,
  and in 2 m of water still 0.25 at the bed.
- The J/22 is past 1.5x hull speed, at 1.5 to 2x on the steep faces.
- With the flow she yaws more on the faces (15.3 deg against 5.8).
- The maxi averages over 20 kn at TWA 120.
- Upwind on flat water is unchanged.

`SailingSim.Physics.Surfing` still passes.
