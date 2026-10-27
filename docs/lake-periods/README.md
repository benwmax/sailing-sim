# The lake's wave periods at short fetch (Oct 27 2026)

`docs/mac-next/` candidate 3. In `docs/physics-gaps/`, the lake's periods ran short against SWAN: 28 kn 11% under, and the 14
kn Rush Creek lee shore 28% under (1.34 s against 1.86).

## Where the error is now

The lake-wide medians (`scripts/wave-check.sh`) had come within 5% of SWAN since then:
- at 28 kn, -4.9%;
- at 5 kn, +8%, the light-air end.

SWAN's own periods at its ten points (`--map`, 1050 cases) show what is left. The error depends on fetch: the shorter
the point's effective fetch, the longer SWAN's period is against the law, at 8 kn and up. These are the medians of SWAN /
law by wind and effective fetch, before → after this change:

| Wind | 200–400 m | 400–1000 m | 1000–2500 m | 2500–6000 m |
|---|---|---|---|---|
| 5 kn | 1.00 → 1.00 | 1.03 → 1.03 | 0.98 → 0.98 | 0.96 → 0.96 |
| 8 kn | 1.25 → 1.05 | 1.08 → 0.97 | 1.02 → 0.98 | 1.03 → 1.00 |
| 11 kn | 1.21 → 0.96 | 1.10 → 0.97 | 1.02 → 0.96 | 1.01 → 0.97 |
| 14 kn | 1.32 → 1.02 | 1.09 → 0.96 | 1.05 → 0.98 | 1.04 → 1.00 |
| 18 kn | 1.31 → 1.02 | 1.15 → 1.03 | 1.06 → 0.99 | 1.07 → 1.02 |
| 22 kn | 1.25 → 0.94 | 1.28 → 1.07 | 1.09 → 1.02 | 1.02 → 0.97 |
| 28 kn | 1.29 → 0.96 | 1.31 → 1.14 | 1.11 → 1.04 | 1.03 → 0.98 |

At 5 kn there is no bias, and the fit leaves it alone.

There are two likely causes. A young sea on a short fetch is driven harder than the SPM law, which was fitted to older
seas, allows. And part of the period at a lee point is the open lake's sea reaching round into it, which no local law
can reproduce. The 90th percentiles (1.4–1.9× SWAN / law) are lee directions of the second kind, and they remain.

## The change

`FWaveField::TargetPeakPeriod` is multiplied by `ShortFetchPeriodFactor`:

`1 + (50 m / F)^0.75 (U / 14 kn)^0.125`, blended in from 5 to 10 kn, with F floored at 200 m (the bake's floor).

- **The fit:** to the binned medians, as #41 fitted the height. The rms binned bias in log period falls from 0.128 to
  0.037.
- **What follows it:** the sea map's band tables (`BandAmplitudeFactor`), the game's sea and the renderer's components.
- **The calibration sea** keeps `GrowthLawPeriod` directly, so PolarGate and every polar are byte-identical.

The other statistics, before → after:
- SWAN's points, median |log error| of the map's period: 0.12 → 0.10.
- Rush Creek in a 14 kn northerly: 1.34 s from the SPM law alone (physics-gaps) against SWAN's 1.86. The map now gives
  1.40; the point is a lee one, and most of its 1.86 s comes from across the lake.
- The lake-wide medians, which derive SWAN's period from the bake's median ratio times the old law, read longer now:
  +2.4% at 28 kn, +9.3% at 11 kn (before: -4.9% and +2.3%). Both statistics are kept here. The points are SWAN's own
  periods, so the fit follows them.

## The caps

Longer periods change how deep the drawn fold runs against its CPU solve, so `AWaterSurface::DrawnFoldScaleAt` is refitted
on W8's crest masks (`docs/water-8/capshape-mac/`). That is the lake, open water, crests only, no AA, four headings, counted
by `count_caps.py`. The target is 0.4 × Monahan.

| Wind | Target | Main | This branch, the old scale | Refitted |
|---|---|---|---|---|
| 12 kn | 0.076% | 0.138% | 0.071% | 0.071% (scale unchanged, 0.94) |
| 16 kn | 0.20% | 0.206% | 0.196% | 0.197% |
| 19 kn (the "20 kn" set's mean wind) | 0.44% | 0.507% | 0.621%, 0.603% (two runs) | **0.470%** |

- **The scale direction:** a larger scale folds less. At 0.8725 the 20 kn cover rose to 0.731%.
- **The refit:** 0.94 at 12 kn, 0.915 at 16, then 0.0015 a knot down to 0.909 at 20. It still falls with the wind
  (`SailingSim.Visual` holds that) and stays above W8's 0.85 floor.
- **`SailingSim.Visual.Whitecaps`** (the grid against Monahan) runs in the gate.

## The sea numbers, main → this branch

| | Main | This branch | Band |
|---|---|---|---|
| ORC band: maxi upwind loss in the gale | 6.6% | 6.2% | 1–10% |
| GaleTack: median, 90th percentile, keeping 40% | 10.5 s, 21.8 s, 20 of 24 | 11.0 s, 19.0 s, 19 of 24 | under 15 s, under 30 s, 18 or more |
| SurfingFlow: J/22 steep faces (standalone) | 10.35 kn | 10.42 kn | 1.5–2x hull speed |
| SurfingFlow: maxi at TWA 120 (standalone) | 23.92 kn | 21.18 kn | over 20 kn |
| Surfing: maxi running in the gale | 18.29 kn | 19.71 kn | faster than flat (17.94) |
| Reference checks: Ray Hubbard peak period, 15 kn over 8 mi | 3.02 s | 3.06 s | 1.80–3.10 s |

The gale trials carry a 200 m chop under the Mistral's sea, and in 32 kn the factor makes its period 42% longer. That is
where the maxi's numbers move.

These are byte-identical to main:
- `polar.sh --quick`;
- `--easy` (the Easy mode runs);
- `--sea checks` (adrift creep 0.24 kn, the ORC sea);
- `--scenarios`;
- `traffic.sh 98`.

The Seawall and squall numbers and the lake drills come from the gate's tests.

## Stills

Helm eye at 14 kn on the lake, TWA 50, the same seed and conditions. Main is left, this branch right. In open water the
factor is about 1.03–1.04, so the difference here is small. The change is near the shores.

![helm eye 14 kn](helm14-compare.jpg)
