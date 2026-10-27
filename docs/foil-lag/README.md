# The foils' lift lags (Oct 27 2026)

The gap #353 named (`docs/foil-inertia/`): adrift beam-on to the swell, the quasi-steady foils sculled the J/22 along at
0.4–0.8 kn. A fin's circulation builds over the chords it travels, not at once. At almost no way, with the angle swinging
round every roll and wave, the lift hardly builds.

## The change

Each foil's angle of attack gets Wagner's indicial lift, using R. T. Jones's (1940) two-term fit:

`phi(s) = 1 - 0.165 e^(-0.0455 s) - 0.335 e^(-0.3 s)`, with `s = 2 U t / c` the semi-chords travelled.

Following Leishman (*Principles of Helicopter Aerodynamics*, 8.14) and Katz and Plotkin (*Low-Speed Aerodynamics*, 13.10):
- `alpha_eff = alpha (1 - A1 - A2) + A1 x1 + A2 x2`;
- each `x_i` follows `alpha` at `b_i 2U/c` per second;
- the flow is turned to `alpha_eff` before the foil reads it (`FBoatModel::Step`'s `LagFlow`).

Steady, `alpha_eff = alpha` exactly, and the faster she sails the quicker it catches up. The lags reset with the boat.
`FoilLiftLagScale` (1) is gated with the orbital flow: never in the calibration sea or on flat water.

## The creep

Adrift beam-on to the Gulf's 1.2 m, 9 s swell with no wind (`polar.sh --sea checks`), the J/22 made good:

| | #353 | This branch |
|---|---|---|
| With the slope push | 0.49 kn | **0.24 kn** |
| Without it | 0.57 kn | **0.38 kn** |

There is no measured figure for a keelboat adrift beam-on, so the sub-0.3 kn target is a plausibility target, not a
reference. For scale, the swell's own Stokes drift at the surface is `a^2 omega k`, about 0.02 kn.

## The other numbers, #353 against this branch

| | #353 | This branch | Band |
|---|---|---|---|
| ORC band: maxi upwind loss in the gale | 7.1% | 6.6% | 1–10% |
| Seawall: close-hauled against flat | 98.1% | 98.1% | under 98.5% |
| Squall timing | 0.2 s early | 0.6 s early | within 4 s |
| The prologue's tack on the wheel | 11.6 s | 14.9 s | under 25 s |
| SurfingFlow: off course on faces at TWA 165 (still water 5.8) | 6.7 deg | 6.7 deg | more than still water |
| SurfingFlow: J/22 steep faces | 10.39 kn | 10.24 kn | 1.5–2x hull speed (8.8–11.7 kn) |
| SurfingFlow: maxi at TWA 120 | 22.71 kn | 24.35 kn | over 20 kn |
| Surfing: maxi running in the gale | 19.17 kn | 18.29 kn | faster than flat (17.94), past 23 kn |
| Surfing: J/22 on the Gulf swell, ILCA in chop | 5.42 / 8.60 kn | 5.43 / 8.60 kn | |

These are byte-identical to main:
- `polar.sh --quick` (J/22 PolarGate);
- `--scenarios`;
- `reference-checks.sh --quick`;
- `traffic.sh 98`.

## GaleTack, now a distribution

The sea tacks are chaotic. Each seed's time and slowest speed swing both ways with any change to the physics, as with
#349, #350 and #353. Here sea seed 6 went from 28.7 s / 40% to 6.7 s / 70%, while sea seed 2 went from 15.6 s to 32.2 s.

So `SailingSim.Physics.GaleTack` holds the distribution over 24 tacks (seeds 1–12, sea and flat water) and lists the
outliers:
- the median under 15 s;
- the 90th percentile under 30 s;
- at least 18 of 24 keeping 40% of her speed.

| Tacks, seeds 1–12, sea and flat | Median | 90th percentile | Keeping 40% |
|---|---|---|---|
| Main aa8c7953 (#353) | 11.3 s | 18.7 s | 21 of 24 |
| This branch | 10.5 s | 21.8 s | 20 of 24 |

On average tacking is no worse: the median is shorter and the tail a little longer, and the flat-water tacks are
identical. Per seed in the sea (seconds, slowest share), main against this branch:

| Sea seed | Main | This branch |
|---|---|---|
| 1 | 10.5 s, 59% | 9.2 s, 53% |
| 2 | 15.6 s, 36% | 32.2 s, 24% |
| 3 | 9.0 s, 68% | 10.4 s, 52% |
| 4 | 13.0 s, 53% | 9.6 s, 68% |
| 5 | 20.1 s, 17% | 23.9 s, 2% |
| 6 | 28.7 s, 40% | 6.7 s, 70% |
| 7 | 7.8 s, 72% | 10.8 s, 42% |
| 8 | 11.8 s, 52% | 11.2 s, 54% |
| 9 | 11.5 s, 49% | 17.0 s, 37% |
| 10 | 12.9 s, 55% | 10.6 s, 65% |
| 11 | 12.0 s, 52% | 12.9 s, 58% |
| 12 | 35.8 s, 32% | 31.9 s, 18% |

Of the two #349 tacks that meet a face head to wind, seed 6 is fixed and seed 5 still stalls. Seed 5 is stopped by the
face's push on the hull and the wind, not by the fin.
