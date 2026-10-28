# AI gybing and the run guard for AI sailboats (Oct 28 2026)

This is the follow-up to #367 (`docs/hobie-run/`). That PR gave the demo autopilot a run guard so it doesn't crash-gybe
on a deep run. It left the traffic and race AI without it: with the guard, the AI races (`scripts/traffic.sh 98`) went
from a mean 1,751 s with every boat finishing to 2,712 s with 14 of 32 races short. The AI can crash-gybe, and a Hobie
can capsize in a race.

## Why the AI slowed

The AI already sails downwind in gybes (`FTrafficSim::Navigate`, on the laylines at its deepest angle). What broke was
the guard's **light hand**: half the gain and a 0.08 tiller cap on bearing away. It applied to any target past 90 deg,
so a rounding onto the run, which needs a hard bear-away, crawled round.

## The change

- **The run guard's extras are a multihull's** (`FAutopilot`, `AutoTrim.h`): the light hand, the margin for her speed
  over the wind's, and the head-up on a deep apparent wind. They exist because a hard bear-away rolls a cat to windward
  and a fast cat's weak apparent wind swings across.
- **A monohull keeps her own helm.** She also keeps the gust margin from dead downwind and the smart head-up past 175 deg
  or by the lee. So a J/22's guard is nearly idle at her 155 deg run, and it catches the accident only.
- **The traffic AI's helm has the wind** (`V.Pilot.Wind`), so its run guard is on.
- **The AI's deepest angle** is `FTrafficSim::RunAngleFor`, no deeper than her guard allows:
  - a multihull sails her polar's best VMG angle in this wind (`BestRunAngle`: the non-spinnaker reference points,
    interpolated, held to 130-160 deg, a table built once);
  - a monohull keeps the 155 deg she had. The polars' downwind VMG is nearly flat from 150 to 172 deg, so the polar's
    angle put the J/22s deeper and made the races slower (1,840 s over the 32).
- **Gybes** stay where the AI decides them: on the layline, against the median wind. They are told to the helm, which
  takes them as ordered gybes (`bGybeOrdered`), not as by-the-lee accidents.
- **They are controlled gybes, sailed with the crew's timing.** While she goes round (`FAutopilot::IsGybing`) the main is
  held sheeted in (`FAutoTrim::bHoldMain`), then eased once she is on the new gybe. A multihull also turns at a quarter
  of full tiller (`GybeTillerMax`) at most.
  - Before this, the AI Hobie's own gybe was a crash gybe. The route switched gybes at 9 kn and the helm swung her round
    85 deg at full tiller with the main fully eased; the heel went from 3 to 87 deg in 3 s, and she capsized.

## Numbers

All measured on this Mac holding the lock.

| `scripts/traffic.sh 98` (32 races, 5 J/22s) | Mean | Finished | Collisions |
|---|---|---|---|
| main 050b6817 (no guard for the AI) | 1,751 s | 160 of 160 | 16 |
| #367's guard on the AI as it was | 2,712 s | 136 of 160 | |
| This branch | **1,734 s** | **160 of 160** | **13** |

The steps in between, all with every boat finishing:

| Variant | Mean |
|---|---|
| Polar angles, no guard | 1,877 s |
| Polar angles, with the guard | 1,841 s |
| 155 deg, with the guard | 1,779 s |
| 155 deg, the guard's extras multihull-only | 1,738 s |
| ... and the crew's gybe (main in through it) | 1,734 s |

The Navigation Rules scenarios (`scripts/traffic.sh`) all pass with the same distances. One metric moved: scenario 8's
give-way slow factor, 0.31 to 0.32.

The Hobie standalone sweep (`Tools/HobieRun seeds 24`: TWA +-170, 14 kn gusting about 18, 5 km of chop, 120 s): 0 of
48 capsized, the boom across in 1, deepest TWA 167.7. These are #367's numbers; an intermediate scope of the light hand
had regressed it to 1 capsize and 6. An ordered gybe in the same air goes through and she stays up (max heel 13 deg in
the chop with the main held in; 22 before).

## Tests

- **`SailingSim.Traffic.AiGybesDownwind`**: a J/22 AI boat sent 2 km dead downwind in 12 kn gybes on the way, gets
  there, never deeper than her run angle, upright.
- **`SailingSim.Traffic.HobieUprightOnAGustyRun`**: a Hobie 16 AI boat sent 3 km dead downwind in 14 kn gusting about
  18 stays upright through her own gybes, kept off dead downwind, and gets there (20 min allowed).
- **Unchanged:** `SailingSim.Physics.HobieRunGuard` (#367) and PolarGate. The polars give the helm no wind, so the guard
  can't touch them.
