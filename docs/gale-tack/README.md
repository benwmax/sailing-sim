# The maxi's tack in the gale (Oct 27 2026)

The prologue's gale (the Mistral preset: 32 kn, Hs 3.5 m at 7 s, two reefs) had a known gap: the maxi would not tack in
that sea. With the orbital flow in (docs/surfing/) she went through 6 of 6, but slowly. Several tacks took 33 to 75 s,
and most dropped well under 40% of her upwind speed. The reference is a 100 ft maxi in 3.5 m seas: she tacks by timing
it on a back with way on, inside about 25 s, without falling under 40% of her upwind speed.

## Why she stalled

The worst tacks were on flat water, so it wasn't the waves. A yaw-moment trace of the 75 s tack (flat water, seed 5):

- She hung 20 to 40 deg off the wind for a minute with the rudder hard over. At 4 to 5 kn the rudder made +10 to +100 kN m.
- The sails made -100 to -385 kN m of lee helm. The main was eased and the jib was still drawing.
- The crew's trim (`FAutoTrim`) eases the main whenever she heels past her limit, and it kept doing that while she headed
  up. Its sheet and traveller swung end to end every couple of seconds with her roll (-8 to +31 deg).
- The hull, keel, Munk and heel-yaw terms looked physical, and so did the rudder losing angle to the turn's own rotation.
  Added resistance, the slope push and the orbital flow were not involved.

So the fix is crew technique, not forces.

## What the crew do now

- **The main trimmer holds the main.**
  - `FStationControls::CallTack()` ("ready about") sets `FAutoTrim::bHoldMain` from the helm's call until she has held the
    new tack (|TWA| 30 to 100 on the other side) for a second.
  - It also ends if she bears away again on the old tack, or after 40 s.
  - While held there is no easing for heel, the traveller goes no further to leeward than the centre, and a dinghy doesn't
    dump. She heads up on her weather helm.
  - The player at the helm putting the wheel hard to windward (over 0.5, |TWA| under 70) calls it too.
  - A player at the main station keeps their own sheet and traveller (`Merge`).
- **The helm times the tack (`FAutopilot::bTimeTacks`).**
  - When told to tack in a sea (Hs at her 0.5 m or more, not the calibration sea), the helm waits up to one mean wave
    period, holding the old tack's angle.
  - The wait ends when she is on a back with way on. A back is the waves' slope push along her bow against her (going
    uphill, SeaTrials' bins). Way on is forward speed at least `TackSpeedShare` (0.7) of her upwind speed, the last 20 s's
    mean close-hauled.
  - On flat water and in lake chop she tacks at once, as before. It is in `FAutopilot`, so AI boats and the drills get it.
- **The trial's helm (`RunGaleTackDetail`) and the prologue tests' helm turn the wheel to 0.6 (19 deg of rudder), not
  0.8 (25 deg) past the stall.** At 25 deg the stalled rudder braked her.

## The 12 tacks (seeds 1 to 6; seconds, slowest speed as a share of her upwind speed)

| Seed | Before, sea | Before, flat | Main held + timing, sea | Main held + timing, flat | + helm short of the stall, sea | + helm short of the stall, flat |
|---|---|---|---|---|---|---|
| 1 | 14.5 s, 35% | 13.9 s, 38% | 12.1 s, 65% | 9.6 s, 63% | 12.0 s, 68% | 9.4 s, 80% |
| 2 | 20.4 s, 16% | 10.5 s, 49% | 11.5 s, 62% | 9.7 s, 59% | 11.3 s, 67% | 7.7 s, 72% |
| 3 | 24.9 s, 13% | 12.9 s, 18% | 24.0 s, 39% | 11.4 s, 53% | 10.1 s, 53% | 11.3 s, 61% |
| 4 | 40.4 s, 18% | 61.4 s, 17% | 16.9 s, 45% | 16.9 s, 34% | 16.4 s, 58% | 16.5 s, 46% |
| 5 | 33.0 s, 4% | 74.9 s, 27% | 11.0 s, 49% | 25.2 s, 11% | 11.9 s, 61% | 25.0 s, 11% |
| 6 | 10.5 s, 31% | 9.5 s, 44% | 8.8 s, 52% | 6.6 s, 70% | 8.6 s, 69% | 6.5 s, 82% |

All 12 now go through inside 30 s, 11 inside 25 s, and 11 keep 40% or more.

The one left is flat seed 5, and the cause is the weather. As she comes head to wind, a 44 kn gust veers about 25 deg in
10 s. She follows it round head to wind for 15 s and falls to 1.2 kn before she is through. A crew tacking into that
shift would be caught too.

`SailingSim.Physics.GaleTack` holds this:
- all 12 through inside 30 s;
- 11 of 12 inside 25 s;
- 10 of 12 keeping 40% or more;
- the rest listed.

The ORC upwind-loss band from #347 is unchanged. `scripts/polar.sh --boat maxi --sea gale` prints each tack's speed
before the call and her slowest through it.

## Unchanged

These come out byte-identical to main:
- `polar.sh --quick` (PolarGate's points);
- `--scenarios` (the J/22's tacks and irons, in the calibration sea);
- `reference-checks.sh --quick`;
- `polar.sh --sea checks`;
- `traffic.sh 98` (16 races; the lake's chop is under 0.5 m, so the AI helms don't wait).

## Follow-up: the trimmer chases the roll

This PR doesn't change it. `FAutoTrim` re-trims each sail to its angle of attack every step, and the angle of attack
swings with the masthead's motion as she rolls. So the sheet and traveller follow the roll, faster than any crew would
or could.

Measured on the J/22 at 15 kn for 10 minutes after a minute's settling. A swing is a 3 s window over which the traveller
covers 1.5 of its 2, or the sheet 0.4. Travel is the summed movement, in full travels of each control.

| Sea | Course | Wind | Traveller swings/min | Traveller travel/min | Sheet swings/min | Sheet travel/min |
|---|---|---|---|---|---|---|
| Flat | TWA 45 | steady | 0 | 0.2 | 0 | 0.03 |
| Flat | TWA 45 | gusty (W1 climate) | 0 | 8.4 | 0 | 4.3 |
| Lake chop (5 km) | TWA 45 | steady | 0 | 16.4 | 0 | 22.6 |
| Lake chop (5 km) | TWA 45 | gusty | 0 | 12.5 | 0.8 | 22.0 |
| Flat | TWA 90 | gusty | 0 | 0 | 0 | 4.0 |
| Lake chop (5 km) | TWA 90 | gusty | 0 | 0.3 | 0.2 | 14.7 |

The J/22 doesn't swing end to end the way the maxi did in the gale. But in lake chop her mainsheet moves 15 to 23 full
travels a minute, about half the time at its top rate (0.8 a second). A human trimmer works the sheet for the puffs and
lulls, a few times a minute, and doesn't follow each wave's roll.

The fix would be a trimmer with a reaction time and a dead band: trim to the angle of attack averaged over a few seconds,
and move only when the error passes a threshold. It needs its own check against the polars, since `FAutoTrim` sails every
polar.
