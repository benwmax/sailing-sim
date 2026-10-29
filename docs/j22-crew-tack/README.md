# The J/22's crew in a heavy-air tack

## What was wrong, and what wasn't

The gap list said the J/22 could not tack on the helm alone in 25 kn. That came from the `RunTack` scenario: a steady
wind, ideal trim and a 0.8 tiller. There she hangs at TWA 20-40 for 25 s while the trimmer eases and trims every step,
which gives her lee helm.

**With a player on the helm she already got through on main, at every wind.** `RunPlayerTack` (`SeaTrials.h`) measures
that tack:

- lake chop (5 km of fetch), gusts 0.08;
- the crew helper trimming with hands, as in normal play;
- the tiller to windward at the keys' ramp, held until she is 30 deg through, then steered for TWA -42.

On main she got through 8 of 8 at 14, 20, 22, 25 and 28 kn, with the tiller at 1.0, 0.8 or 0.6.

What a blow cost her was speed: she nearly stopped head to wind. With a full helm her slowest speed was 52% of her speed
before the call at 14 kn, 24% at 22, 21% at 25 and 11% at 28. With a gentle helm (0.6) at 28 kn the tack took 20 s on
average.

## What the crew do now

`FAutoTrimSettings::bCrewTacks`, on monohull keelboats only. It is off by default, so `RunTack`, the scenarios, the polars
and the AI are untouched. The pawn turns it on for the player's boat, in either mode, but not in measured runs, on
traffic boats or on the ghost.

- **The call.** The tiller held over to windward (past 0.5) for 0.6 s while she comes up 8 deg from where it went over. A
  luff in a puff is let go sooner, so it is not a call. A first version took any tiller over 0.5 as a call: in the gusts
  the crew then held the main on a luff and pinned her head to wind before any tack.
- **The hold.** The main is held as the prologue's stations hold it (`bHoldMain`: no easing for heel, the traveller no
  further to leeward than the centre). It lasts until she is 15 deg past head to wind, or until the helm lets go before
  she is through.

That matches what a crew does in a blow: the main in through head to wind.

Two other parts were measured and left out:

- **Backing the jib** to 15 deg through braked her (2 kn to 0.5 kn in one trace). The J/22 turns in about 4 s on the
  helm; backing is a light-air and dinghy move.
- **Carrying the old tack's trim across** (main where it was, new jib sheet to the old mark, held until she had 80% of
  her speed) left eased sails that didn't drive her.

With a full helm, all three parts together kept 14% at 25 kn and 6% at 28 (main: 21% and 11%).

## Before and after (8 seeds per wind; seconds through, the share of her speed kept at the slowest)

| Wind | Tiller 1.0, main | Tiller 1.0, crew hold | Tiller 0.6, main | Tiller 0.6, crew hold |
|---|---|---|---|---|
| 14 kn | 8/8, 4.5 s, 52% | 8/8, 4.5 s, 52% | 8/8, 5.0 s, 58% | 8/8, 5.0 s, 58% |
| 20 kn | 8/8, 4.3 s, 41% | 8/8, 4.3 s, 42% | 8/8, 5.8 s, 38% | 8/8, 5.4 s, 44% |
| 22 kn | 8/8, 5.3 s, 24% | 8/8, 4.7 s, 29% | 8/8, 7.2 s, 16% | 8/8, 6.5 s, 26% |
| 25 kn | 8/8, 5.7 s, 21% | 8/8, 5.7 s, 28% | 8/8, 8.2 s, 12% | 8/8, 6.6 s, 26% |
| 28 kn | 8/8, 6.1 s, 11% | 8/8, 5.9 s, 18% | 8/8, 20.2 s, 6% | 7/8, 7.1 s, 23% |

With a 0.8 tiller: 28 kn goes from 12.2 s and 10% to 6.8 s and 18%. 14 kn is unchanged at every helm.

Over 24 seeds at 28 kn with the tiller at 0.6, she gets through 20 of 24 on main and 23 of 24 with the crew. One seed (3)
goes the other way: on main she gets through in 51.7 s; with the hold she doesn't get through in 60 s.

There were no false calls in any of these runs (each has a minute's gusty beat before the call).

## Tests

`SailingSim.Physics.CrewTack` checks:

- off by default;
- at 28 kn with a 0.6 tiller over 24 tacks, more get through with the crew, quicker (median) and keeping more speed (by
  5 points or more);
- no false calls in the gusty beats before the calls and in eight full-helm tacks at 20 kn;
- the ILCA's tack identical with the switch on.

`RunTack`, the tack scenarios and PolarGate don't use the switch.

## The crew under the held boom

The first gate failed `SailingSim.Visual.SheetClearance`. With the main held in, the boom sat at 4 deg while she was still
on the old tack, and the traveller car came up toward the centre. Crew 1 was still sitting up beside the helm, because the
crossing only began at TWA 28, and their head was 6.7 cm into the mainsheet's tail in 3 samples. Now a called tack
(`FCrewPlaceInput::bTackCalled`, from `FAutoTrim::IsHoldingForTack`) starts the crossing as she comes up, as a crew gets
down under a centred boom when the helm calls it. What's left is one forearm sample at 2.4 cm, listed and not failed.
`CrewHullClearance`, `CrewClipTack` and `RigClearance` are green.

## Gate (`scripts/gate.sh --scope water`, packaged, the Mac)

Pass: 277 tests, every view over its floor. On High: beam8 56.4, beat15 52.4, storm 47.1, marina 55.5, coast-day 50.4,
gulf-sea 59.2, helm-eye 59.1, bridge 55.9. Storm on Medium: 67.8.
