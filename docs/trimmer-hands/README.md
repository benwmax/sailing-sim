# The trimmers' hands (Oct 27 2026)

`FAutoTrim` is the crew on the sheets for the AI boats, the drills, Easy mode and the station crew. It used to re-trim each
sail to its angle of attack every physics step. As a boat rolled, the angle of attack swung with the masthead's motion,
and the sheets followed it. On the J/22 at 15 kn upwind in the lake's chop the mainsheet moved 23 times its length a
minute and the traveller 16 units a minute (docs/gale-tack/). No crew can do that, and none would.

## What the hands do now (`FAutoTrimSettings`)

- **They see the sail over a reaction time.** The foot angle each sail wants is averaged over `ReactionSeconds` (1.5 s)
  in a breeze. In light air the trimmer plays the sheets, watching the telltales, at `LightReactionSeconds` (0.2 s). The
  two blend from `LightAirKnots` (8) to `BreezeKnots` (14).
  - Light air needs it: the J/22's light-air polar came from tracking the apparent wind's small swings, and any smoothing
    over half a second cost 3 to 4% at 6 kn.
- **They read the heel's trend, not each roll.**
  - `HeelTrendSeconds` is 0.5 s at a 6 m waterline. It grows as the square root of the waterline for bigger boats, which
    roll more slowly: the maxi's is 1.1 s.
  - Under a spinnaker anything slower than about 0.8 s let her roll before anyone answered. The J/22's steady 20 kn kite
    reach fell from 9.75 to 8.57 kn at 1.5 s.
  - A sheet in the hand (a dinghy, or a boat under `HandSheetMassKg`, 500 kg: Sunfish, ILCA, Hobie) answers the heel at
    once. With a lagged heel the ILCA and Sunfish capsized in the reference checks.
- **A keelboat crew leaves the heel ease alone within `HeelDeadBandDeg` (1 deg) of the limit.** Without that the ease
  servoed on the limit in a steady wind, the traveller cycling 0.2 to 0.95 every 14 s.
- **They move a control only when it is off by more than a dead band.**
  - The band is in degrees of the sail's angle: `LightDeadBandDeg` 0.75 in light air, `DeadBandDeg` 2 in a breeze.
  - The control then moves at its own rate until it is close.
  - In a breeze the hand rests `RestSeconds` (1.5 s) before the next move; there is no rest in light air or with a sheet
    in the hand.
  - Below the band it only creeps, at `CreepDegPerSecond` (1 deg/s), so a steady wind still trims exactly.
- **Rates come from the boat's hardware.**
  - A sheet eased runs out through the hand at the old 0.8 of its travel a second; the traveller does twice that.
  - Trimmed in, the main and traveller move at the main trimmer's station rates (`FStationConfig`: the J/22's 0.35/0.8,
    the maxi's 0.18/0.4).
  - The jib trims in no faster than one grinder brings the sheet home against its load: fast while it luffs, slow once it
    fills. The same formula is used for the player's grinding.
  - Slow easing as well put the J/22's 30 kn running peak at 16.1 kn (her limit is 16).
- **The mainsheet follows the traveller car where it is,** not where it is going, so the two hands don't fight.
- **Kept:**
  - the dinghy sailor's puff easing (0.4 s, physics-gaps);
  - `bHoldMain` from #349, under which the main is trimmed in at the hardware rate.

## Ideal hands for the physics

`bHands = false` is the old trimmer, exactly: every step, at the target. The reference polars (`SailSteady`) and the sea
trials (`RunInSea`) use it. They measure the boat, the way a VPP trims, and the ORC bands from #347 are built on them.

PolarGate and every boat's `polar.sh --quick` are byte-identical to main. The crews in the game, the AI boats, the drills,
Easy mode, the station crew and the reference checks sail with hands.

## The J/22 at 15 kn (`scripts/polar.sh --sea trim`, 10 minutes after a minute's settling)

Each figure is a control's travel in whole travels a minute (the traveller's is 2). Adjustments are moves started past
the dead band, summed over main, traveller and jib.

| Sea | Course | Wind | Ideal: main / traveller / jib | Hands: main / traveller / jib | Adjustments/min | Speed, ideal / hands (kn) |
|---|---|---|---|---|---|---|
| Flat | TWA 45 | steady | 0.03 / 0.19 / 0.03 | 0 / 0 / 0 | 0 | 6.01 / 6.02 |
| Flat | TWA 45 | gusty | 4.39 / 8.43 / 4.48 | 0.68 / 4.86 / 0.70 | 9.7 | 5.97 / 5.95 |
| Lake chop | TWA 45 | steady | 23.06 / 16.80 / 23.61 | 0.92 / 4.32 / 0.92 | 11.8 | 5.36 / 5.39 |
| Lake chop | TWA 45 | gusty | 22.20 / 12.92 / 22.90 | 1.17 / 3.28 / 1.22 | 31.9 | 5.26 / 5.17 |
| Flat | TWA 90 | gusty | 4.16 / 0 / 4.31 | 0.56 / 0 / 0.79 | 3.6 | 6.87 / 6.82 |
| Lake chop | TWA 90 | steady | 13.15 / 0.18 / 12.54 | 0.71 / 0 / 0.79 | 0.6 | 6.74 / 6.62 |
| Lake chop | TWA 90 | gusty | 15.00 / 0.38 / 14.40 | 0.91 / 0.04 / 1.12 | 18.7 | 6.74 / 6.63 |

In chop the mainsheet travels 4% of what it did, the traveller about a quarter, and the jib 4%. Upwind the hands make
about 12 adjustments a minute across three controls in a steady breeze, about 32 in gusty air. Speed is within 2% of
ideal.

`SailingSim.Physics.TrimmerHands` holds these:
- nothing moves on flat water in a steady wind;
- in the chop, under 20 adjustments a minute, the main and jib under 3 travels and the traveller under 6, against ideal
  trim's 10+;
- more adjustments in gusty air;
- within 3% of ideal speed.
