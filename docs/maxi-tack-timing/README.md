# The maxi's tack timing in the gale

On main (13cb19e9), two of the six tacks `scripts/polar.sh --boat maxi --sea gale` sails were slow:

- seed 2 took 32 s and fell to 27% of her upwind speed;
- seed 5 took 24 s and fell to 13%.

`docs/gale-tack/` aims for inside about 25 s, keeping 40%. Over 24 seeds in the sea, 15 kept 40% and seed 23 never got
through (90 s). Only the helm changed here (`FAutopilot`'s timed tack). The hull, sails, `AddedResistanceCoef` and the
GaleTack test are untouched.

## What those seeds met

Traces every 0.5 s of seeds 2, 5, 12 and 23 (speed, TWA, wheel, sheets, the waves' push):

- **Seed 23: a restarted tack.** A face knocked her back across head to wind. The helm read that as a new order to tack:
  it waited again, steered back for the old tack's angle (tiller -0.6 for 4 s), and then started over at 4 kn. She hung
  for 90 s. Seed 5 did the same for a moment at 16 s.
- **The slow ones: too little way on at the call.** She reached head to wind at 6-8 kn, crossed slowly, and sat at TWA
  -10 to -25 on the new tack at 3-4 kn. The wheel was hard over, the main held in and the new jib not yet ground in.
- **Not the main hold.** Releasing the held main 10 deg past head to wind changed nothing (the trimmer keeps it in) or
  made it worse (seeds 2, 14, 24).
- **Not the waves in the turn.** 192 tacks: seeds 1-24, each called at eight times 0-14 s apart. The sea's rms height at
  her position over the 10 s after the call does not predict the outcome:
  - correlation -0.05 with the share she keeps;
  - 66-77% keep 40% in every quartile of rms height.
  The prediction itself works (the height 5 s ahead is exact), so the look-ahead would have been possible.
- **Her speed at the call decides it.** Over the same 192 tacks, the share of her upwind speed she had at the call
  correlates +0.31 with the share she keeps through the wind. The share keeping 40%, by quartile of call speed: 58%
  (0.7-0.9x), 60%, 77%, 89% (1.1x and up). The wind's speed counts too (54% in the lowest quartile, a lull, against
  75-83%).

## The fix (`FAutopilot`, `AutoTrim.h/.cpp`)

- **A tack once started is held** until the order changes. A face knocking her back across the wind no longer restarts
  the wait (`TackOrderSide`).
- **Way on means her upwind speed or more:** `TackSpeedShare` 1.1 (was 0.7) of the last 20 s's close-hauled mean, still
  on a back.
- **While she waits she foots 10 deg** (`TackFootDeg`) off the old tack's angle, as a crew builds speed before tacking in
  a seaway.
- The wait is still at most one mean wave period. On flat water and lake chop she tacks at once, as before.

The grid behind those values, sea tacks keeping 40% / p90:

| Bar | Foot | Seeds 1-24 | Seeds 25-48 |
|---|---|---|---|
| 0.7 | 0 | 15 / 23.9 s | 16 / 29.0 s |
| 1.0 | 5 | 18 / 23.8 s | 18 / 18.1 s |
| 1.0 | 10 | 19 / 23.7 s | 18 / 18.3 s |
| 1.1 | 0 | 20 / 18.8 s | 19 / 24.7 s |
| 1.1 | 10 | **23 / 18.3 s** | **20 / 19.4 s** |

These rows already have the restart fix. Waiting two or three periods made the tacks later and no better (1.1, two
periods: p90 28.6 s).

## Before and after: 48 seeds, the trial's wheel (`RunGaleTackDetail`)

| | Main, seeds 1-24 | Fix, seeds 1-24 | Main, seeds 25-48 | Fix, seeds 25-48 |
|---|---|---|---|---|
| Median | 13.0 s | 12.8 s | 13.2 s | 13.2 s |
| 90th percentile | 24.9 s | 18.3 s | 27.2 s | 19.4 s |
| Inside 25 s | 22 of 24 | 24 of 24 | 21 of 24 | 23 of 24 |
| Keeping 40% | 15 of 24 | 23 of 24 | 16 of 24 | 20 of 24 |
| Not through in 90 s | 1 (seed 23) | 0 | 0 | 0 |

- Seed 2: 32.0 s at 27% became 16.1 s at 42%.
- Seed 5: 23.9 s at 13% became 15.5 s at 55%.
- Seed 14 stays slow (23.7 s, 38%), and seeds 29 and 43 of the second set too (21.5 s at 25%, 31.6 s at 35%).
- Flat water is identical, seed for seed (seeds 1-24: median 9.3 s, p90 11.3 s, all keeping 40%).

## Test

`SailingSim.Physics.GaleTackTiming` (new) checks seeds 1-24 in the sea: every tack through, the median under 15 s, the
90th percentile under 22 s, and 21 of 24 keeping 40%. Main's helm fails it (seed 23 not through; 15 of 24).
`SailingSim.Physics.GaleTack` is unchanged.

The harness for the traces and sweeps is plain C++ over SailingPhysics, like `Tools/PolarSweep`. It is not kept; the
numbers above are its output.
