# The waves' inertia on the foils (Oct 27 2026)

`docs/mac-next/` candidate 2, and the gap #347 left (`docs/surfing/`). With the orbital flow, the keels and rudders met
the water's velocity but not its acceleration.

## The change

- **`FWaveField::OrbitalFlow`** returns the orbital velocity and its acceleration together.
  - For each component `du/dt = -a omega^2 profile cos(Arg)` along its travel, with the same depth profile and sea-map
    ratio as the velocity.
  - The ocean's is the slope of its 30 Hz grids' blend in time (`FOcean::OrbitalAcceleration`).
  - `SailingSim.Physics.FoilInertia` holds it to the flow's central difference: 0.00007 m/s^2 off on 0.72 rms.
- **`FBoatModel`** samples it with the flow at her bow and stern at two depths (`OrbitalAccelerationAt`).
- **Each wet foil gets Morison's inertia term** from the water's acceleration in its body frame:
  - **Across the fin:** `rho (V + Ca V_R) a_y`, with `Ca = 1` on `V_R = pi (c/2)^2 span`. That is a flat plate's added
    mass per length, `rho pi a^2` with `a` the half chord (DNV-RP-C205 table A-1; Newman, *Marine Hydrodynamics*,
    4.13).
  - **Along the chord:** `rho V a_x`, its volume only. A NACA section of t/c 0.12 holds 0.68 t c per length.
  - **The bulb** (`AppendageVolume`): `rho V (1 + k) a`, with Lamb's coefficients for a 4:1 prolate spheroid, `k2 = 0.86`
    across and `k1 = 0.08` along (Newman, table 4.3).
- **The other half of Morison's term,** the added mass the fin drags when it moves itself, is already in the boat's sway
  and yaw (`AddedMassRatio` 0.75 of her mass in sway, `AddedInertiaRatio` 0.6 in yaw). Adding it per foil would count it
  twice, so only the wave's push is new.
- **`WaveFoilInertiaScale`** (1) is gated like the flow: never in the calibration sea, so PolarGate is exact.
  Telemetry: `WaveFoilSurge`.

## Before (main 22ff7b3d) and after

| | Main | This branch |
|---|---|---|
| **ORC band** (GaleTack, maxi upwind loss in the gale, 1–10%) | 3.9% (10.75 kn against 11.19) | **7.1%** (10.40) |
| **Seawall** (GalvestonSwell, under 98.5% of flat) | 97.8% | **98.1%** (5.83 against 5.94) |
| **Squall** (Prologue.Gale, within 4 s of its cue) | 3.3 s late (#347; within 4 since) | **0.2 s early** (91.3 against 91.5 s) |
| **The prologue's tack on the wheel** | 15.0 s from the call (#349) | **11.6 s** |
| **Surfing:** J/22 on the Gulf swell, TWA 150 | 5.42 kn, best second 7.87 | 5.42, 7.86 |
| **Surfing:** maxi running in the gale | 18.60 kn, 14.9–25.4 | 19.17, 13.8–27.2 |
| **Surfing:** ILCA in lake chop | 8.60, best 9.77 | 8.60, 9.77 (the lake's short chop barely reaches her fin) |
| **SurfingFlow:** J/22 steep faces, 2 m sea, TWA 150 | 10.26 kn (1.76x hull speed), best 13.16 | **10.39 (1.78x)**, best 13.86 |
| **SurfingFlow:** TWA 165, off course on the faces | 15.3 deg (5.8 in still water) | **6.7** (5.8) |
| **SurfingFlow:** maxi in the gale, TWA 120 | 23.22 kn | 22.71 |
| **Adrift beam-on to the 1.2 m swell** (made good) | 0.43 kn | **0.49** (without the slope push: 0.76 → 0.57) |
| **GaleTack:** 12 tacks inside 30 s / 25 s / keeping 40% | 12 / 11 / 10 | 12 / 11 / 10 |
| **GaleTack sea seed 5** (a face head to wind) | 19.4 s, 19% | 20.1 s, 17% |
| **GaleTack sea seed 6** | 28.8 s, 40% | 28.7 s, 40% |
| **GaleTack sea seeds 2 and 4** | 42%, 70% | 36%, 53% |

`polar.sh --quick` (J/22), `--scenarios`, `reference-checks.sh --quick` and `traffic.sh 98` are byte-identical to main,
since all of them sail the calibration sea or flat water.

## What did and didn't improve, and why

- **The broach onset is no longer exaggerated.** #347's flow alone took the rudder's water away on a face and left the
  wave's push on the fins out. Off course on the faces at TWA 165 went from 15.3 deg to 6.7, against 5.8 in still water.
  That is still more than in still water, as it should be, but no longer by a factor of 2.6.
- **The prologue's tack** is quicker (11.6 s) and the squall reaches her on cue (0.2 s). Her track through the gale
  moved.
- **The adrift creep did not fall** (0.43 → 0.49 kn), and the two sea tacks that meet a face head to wind did not
  improve (seed 5: 19% → 17%; seed 6: 28.8 → 28.7 s). Morison's inertia is linear in the wave: it pushes the fin to and
  fro with the water and averages to zero over a wave. It can't make or remove a mean creep, and a tack stopped by a face
  is the face's push on the hull (Froude-Krylov) and the wind, not the fin.
  - What still sculls her along adrift is the foils' quasi-steady lift at near-zero speed. As she rolls and sways, the
    fin meets the water at large, fast-changing angles and makes thrust like a flapping foil.
  - A real fin's lift lags such changes: Theodorsen's function at the fin's reduced frequency (about 0.3 to 1 here)
    halves the lift and turns it, and Wagner's for the start. That unsteady lift was the next gap; `docs/foil-lag/`
    (Oct 27) built it, and gap 7 measured it (Oct 29).
  - The seeds 2 and 4 tacks are chaotic in this sea; any change moves them both ways (see `docs/gale-tack/`).

## Gate

`scripts/gate.sh --scope water --merge foil-inertia` (origin/main + 982068eb):
- All 242 tests passed with the heavy set, including the new `SailingSim.Physics.FoilInertia`.
- The game packaged.
- Every view is ok. High: beam8 58.6, beat15 53.1, storm 46.8, marina 56.4, coast-day 52.9, gulf-sea 62.0, helm-eye
  58.0, bridge 59.4 fps. Medium: storm 68.6 fps.
