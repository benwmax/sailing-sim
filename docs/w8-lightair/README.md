# Whitecaps in light air (Oct 16 2026)

The PC's stills at 10 kn showed metre-long white flecks on the lake. There were two causes:

- **Monahan's law runs too high below 12 kn.** It is fitted in a breeze, and still gives 0.04% cover on the lake at
  10 kn (0.4 of the sea's 0.1%), enough for a few metre-long caps in view. Callaghan et al. (2008, GRL 35, L23609)
  put the onset of breaking at 3.7 m/s, with cover growing as the cube of the wind above it.
  `AWaterSurface::WhitecapOnset` now scales the solved target by ((U - 3.7) / (U12 - 3.7))^3 below 12 kn. That is 0.2
  at 10 kn and 0 under 7.2 kn. From 12 kn up, nothing changes.
- **The solved threshold could not go under the lowest sample.** `FWaveDetail::CapThreshold` took a quantile of
  4,096 samples, so any target under a few samples landed on the lowest few, and the cover floored near 1/N whatever
  the target was. A target under eight samples is now extrapolated down the tail, linear in the normal quantile. An
  e-fold slope capped a fifth of the target, because the fold's tail falls faster than an exponential.

`SailingSim.Visual.WhitecapOnset` checks the onset and the extrapolation. At 10 kn on the lake, the threshold solved
like the renderer's (12 frames) caps 0.0036% of other water against a 0.0082% target, within the test's factor of
three. `Whitecaps` and `WhitecapsSeen` are unchanged and pass.

## Look

`ilca-10kn-before-after-14kn.jpg`: main at 10 kn, this branch at 10 kn, this branch at 14 kn (High, AfternoonBreeze,
uncooked). The before still is from the sail-number branch, which is why the numbers differ. The after stills
predate that fix.

`caps-only-10kn-before-after.jpg` (`-SailingDebugFoam`): the caps alone at 10 kn. White pixels on the water beside
the boat:

| wind | main | this branch |
|---|---|---|
| 10 kn | 0.58% | 0.032% |
| 12 kn | 0.17% | 0.15% |
| 14 kn | 0.18% | 0.12% |

From 12 kn the code path is the same, so those rows differ by frame noise only.

## Gate

`scripts/gate.sh --scope water` passes: 145 of 145 tests. Every view is at or above the sweep baseline on Medium and
High (helm-eye High 54.6 fps, slip High 52.0, storm High 51.3).
