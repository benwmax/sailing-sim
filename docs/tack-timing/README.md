# Timing a tack to the sea ahead

Gap 6 from the Oct 28 list: the maxi's three slow gale tacks after #382 and #387. Seeds 14, 29 and 43 in `RunGaleTack`
took 21-32 s and kept 25-38% of her speed. #387 found them decided by the wave she meets head to wind. The sim's sea is
exactly predictable (`FWaveField::Sample` at a later time), so the brief was a look-ahead helm. It waits, within a period
or two, for the start that puts her bow through the wind on a back or a flat spot, as a real helm times a tack to a flat
spot.

## The look (`FAutopilot::TackFaceAhead`)

For a start Delay seconds from now, she sails on, turns, and is head to wind `TackTurnSeconds` after the start: 15 deg/s
on a 6 m waterline, slower as the square root of her length (the maxi about 7 deg/s, 6-7 s from TWA 45). The look reads
the slope along the wind's direction from 1 s before head to wind to 2 s after, at her position then. Positive is uphill:
a face.

## What didn't work

**First version: pick the best start in the next two periods.** This replaced #382's rule (go on a back with way on) by
"now is within 0.01 of the best start over the next two periods". Everything got worse:

| 24 seeds | #382 | First version |
|---|---|---|
| Maxi, seeds 1-24 | median 12.8 s, p90 18.3, 23 keeping 40% | 15.0 s, 28.4, 17 |
| Maxi, seeds 25-48 | 13.2 s, 19.4, 20 | 15.6 s, 39.3, 16 |
| J/22 | 7.2 s, 17.3, all through | 17.7 s, 44.7, 1 not through |
| Catalina 30 | 22.4 s, 6 not through | 48.3 s, 7 not through |

The wait costs her the speed #382 waits for, and the look alone is a weak guide.

**Testing the predictor alone.** 192 tacks: seeds 1-24, each started at once (no timing) at eight call times 2 s apart,
with the predicted slope at head to wind against the share of speed she kept:
- the correlation is -0.12 (a face ahead, a little worse);
- by quartile of the slope, she keeps 40% in 34 of 48 (a strong back), 41 of 48 (flat), 31 and 31 (faces);
- by its size alone (flatness), 39, 34, 30 and 34.

So a flat spot is a little better than a face, and a strong back no better than a face. Tacking at once she keeps 40% in
137 of 192 (71%). #382's rule (way on, on a back) reaches about 90%, mostly by waiting for her speed.

## The change: a veto on #382's rule

When #382's rule says go, the helm still waits (within the same period) if the bow would come through the wind into a
face: `TackFaceAhead(0) > TackLookMaxFace` (0.04). `bTackLookAhead`, on, in the same seas as `bTimeTacks` (Hs 0.5 m and
up, not the calibration sea).

| 24 seeds | #382 | With the veto |
|---|---|---|
| Maxi, seeds 1-24 | median 12.8 s, p90 18.3 s, 24 inside 25 s, 23 keeping 40% | unchanged |
| Maxi, seeds 25-48 | 13.2 s, 19.4 s, 23 inside 25 s, 20 keeping 40% | unchanged |
| J/22 | 7.2 s, **p90 17.3 s**, 23 inside 25 s | 7.2 s, **p90 12.9 s**, 23 inside 25 s |
| Catalina 30 | **median 22.4 s**, 14 inside 25 s, 6 not through | **17.2 s**, 15 inside 25 s, 5 not through |

The maxi's slow seeds are not cleared: 14 is 23.7 s at 38%, 29 is 21.5 s at 25%, 43 is 31.6 s at 35%, as before. A
veto at 0.02 or at 0 (no climb at all) leaves her 48 seeds the same. Her timed tacks almost never go on the ready rule
the veto filters; they go when the period's wait runs out. Waiting longer (the first version) only made her later. Of
`polar.sh --boat maxi --sea gale`'s six seeds two move a little: seed 2 keeps 44% (was 42%), seed 4 70% (was 67%).

**What I'd look at next for her three:** the tack's own course, not its start. #382's trace of seed 5 had a 40-44 kn gust
veering with her through the turn. The look reads waves; a helm could also read the wind's shifts ahead (the wind field
is seeded, so as predictable as the sea).

## Unchanged (byte-identical to main 5077810d)

- `scripts/polar.sh`, `--scenarios`, `--sea`, `--easy`;
- the ILCA's, Hobie's, Catalina's, Sunfish's, Corsair's and Lagoon's polars;
- `reference-checks.sh --quick`;
- the J/22's player tack and crew tack: the player steers those, not `FAutopilot`'s timed tack (`SailingSim.Physics.CrewTack`
  passes).

## Test

`SailingSim.Physics.TackLookAhead` checks:
- over 24 gale tacks the J/22's 90th percentile is over 2 s quicker reading the sea ahead;
- the maxi's seeds 1 and 14 are step for step unchanged.

`GaleTack` and `GaleTackTiming` pass unchanged.

## Gate (`scripts/gate.sh --scope boats`, packaged, the Mac)

Pass: 281 tests, every view over its floor on High: beam8 56.3, beat15 52.3, marina 54.8, helm-eye 59.1, slip 49.0,
crew 46.8.
