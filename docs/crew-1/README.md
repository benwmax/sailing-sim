# C1: crew motion node and physics reaction layer

The crew used to be `UPoseableMeshComponent`s posed on the game thread every frame: a stance from `CrewPose.h`
blended at a fixed 7/s, then the hand and foot IK. Now each sailor is a `USkeletalMeshComponent` with its own
`UCrewAnimInstance`. Its proxy runs one custom node, `FAnimNode_CrewMotion`, so the posing happens on the animation
worker threads. The game thread only places the figure and hands the node its frame (`FCrewMotionInput`).

## What the node does

| Layer | How |
|---|---|
| Base | Today's stance joints (`CrewJointRotations`). A change of stance blends by minimum jerk over its own time (0.45 s into a tack's crossing, 0.6 s out of it, 0.8 s between seats), from wherever the last change had got to. The figure's place moves on the same curve. |
| Felt gravity | The physics step now exports the boat's acceleration and angular acceleration (`FBoatTelemetry::AccelBody`, `AngularAccelBody`, 25 ms means). The turn rate is `FBoatState::AngularVelocity`. At each seat, `g - (a + alpha x r + omega x (omega x r))`, with `r` the seat's offset from the centre of gravity (`CrewFeltGravity`). |
| Balance | `FCrewBalance` sees the felt gravity's tilt and load after a reaction time of 0.1 to 0.3 s (seeded per sailor). It tracks them with critically damped springs, stepped exactly, so they settle without overshoot (2 % in about 0.65 s after the lag). The trunk leans toward the felt "up", shared over the pelvis, spine and chest. |
| Head | Levelled to the world's up after everything else. A tenth of the trunk's lean gets through, because a dead-level head reads as a gimbal. It is turned to the gaze, within 75 degrees of the chest and 35 up or down, split over the neck and the head. |
| Gaze | Glances of about 2.4 s each. The helm and trimmer mostly watch the jib's luff telltales, then the water upwind for the next puff, ahead, and the next mark when racing or the nearest boat. The bow looks ahead and upwind. When crossing they look ahead. The head follows the target on a spring. |
| Never still | Breathing in the chest (about 15 a minute) and a slow two-tone sway in the spine, each sailor on their own phase. |
| Arm tension | Each hand's load: the helm force at the tiller end, the sails' load on the sheets. It closes the grip and leans the chest back against the pull. |
| Bracing | Past the tipping limit (the felt tilt's tangent beyond half the support's width over the centre of mass height: seated 0.20 m across, 0.30 m fore and aft, 0.35 m high; crouched crossing 0.16 / 0.14 / 0.55), a free hand takes the nearest handhold in reach. That is the cockpit coaming or the cabin-top handrail: the lesson J/22 has no lifelines. One foot pushes the far seat. The brace holds for at least 0.8 s and lets go below 0.8 of the limit. |
| Bow slam | The load channel (extra g) has its own faster spring. The knees and spine give and come back. |
| Tacks and gybes | Timed to the boom. Turning through the eye of the wind (or the boom swinging across dead downwind), the crew under the boom's sweep cross as it comes over. They go into the middle of the cockpit and crouch lower the closer the boom is to the centreline, never below a deep crouch over the floor. They face forward. A crew-model move through the middle of the boat is also a crossing; hiking in or out is not. |
| Feet and hands | The existing IK (`CrewSolver`: plant the feet on the deck, seats or sole; reach for the tiller extension, the mainsheet, the jib sheet's tail; hands on the knees) now runs inside the node. |

The attach points follow the names in `J22H_sockets.json` (`Inputs/j22-hero` on `j22-hero-poc`): `HandholdCabin_S/P`,
`HandholdCoaming_S/P`, `Seat_S/P`, `FootBrace_S/P`, `SideDeck_S/P`, `CockpitSole`, plus the existing `TillerEnd` and
`JibTailer_S/P`. Where the boat's model has the socket the pawn uses it. Today's models have none of the new ones, so
`CrewDerivedAttachPoints` builds them from the physics geometry, as the pose fix did: the cockpit well, the deck edge,
and the cabin top 0.35 m forward of the companionway.

AI boats' crew run the same node at 15 Hz (`SetComponentTickInterval`) and only while they are rendered.

`ASailboatPawn::UpdateCrewFigures` and the tests now share the stance placement (`CrewPlacement`); the test used to
keep its own copy.

## Args

- `-SailingCrewStill`: the stance alone, without the reaction layer (the C1 before and after).
- `-SailingDebugCrew`: a log line a second per sailor (stance, duck, felt gravity, tip ratio, bracing, head tilt, the boat's accelerations).
- `-SailingShotCrew=<name>`: saves `Saved/Bench/<name>.png` once the helm is crouched under the boom (stills of a tack).

## Tests

- `SailingSim.Physics.BoatAcceleration`: afloat at rest the exported acceleration reads zero. In a steady turn the lateral acceleration is the centripetal one.
- `SailingSim.Visual.CrewBalanceStep`: a 15 degree heel step at 60 and 15 Hz, with lags of 0.1 and 0.3 s. Still through the reaction time, no overshoot, within 2 % by 1 s. A slam gives and recovers without bouncing.
- `SailingSim.Visual.CrewHeadLevel`: in a lake chop (roll 8 + 3 degrees, pitch 4, heave) on a heeled J/22, on SK_Sailor and the MetaHumans, each sailor's eye line stays within 5 degrees of level. Where the stance alone tilts the eyes, the reaction layer cuts that by more than three times.
- `SailingSim.Visual.CrewMotionFeet`: every boat's crew, sitting up, hiked, knocked down to 42 degrees (they brace), tacking under the boom and gybing, in chop. No heel or toe inside the boat.
- `SailingSim.Smoke.CrewAnimation`: in a world each sailor is posed by the node and sits. An AI boat's crew tick at 15 Hz.
- `SailingSim.Visual.CrewFeet` (G8) still passes, now through `CrewPlacement`.

## Stills

Mid-tack (taken by `-SailingShotCrew` as the helm crouches): the jib is luffing and the boom is on the centreline.
The crew are low in the middle of the cockpit under it, facing forward.

![Mid-tack](midtack.png)

Close-reaching in 18 kn of lake chop. Left, the stance alone (`-SailingCrewStill`): the heads tilt with the boat. Right,
C1: the trunks lean against the heel, the heads stay near level, and the trimmer glances forward at the telltales.

![Chop, before and after](chop-before-after.png)

## Gate

Build OK; tests 119 passed, 0 failed; package OK. Before is main with #33 merged in (the Part A gate run); C1 is this
branch. Both are `scripts/bench-visual.sh 12` on the packaged build. The game ms column is the game thread's frame
time; the crew slice is `PerfScopes`' `Crew` (`visual-bench-*-gt.csv`).

| View | Tier | fps before | fps C1 | game ms before | game ms C1 | crew slice before | crew slice C1 |
|---|---|---|---|---|---|---|---|
| beam8 | Medium | 94.3 | 93.7 | 1.99 | 1.98 | 0.182 | 0.054 |
| beam8 | High | 55.1 | 57.0 | 2.83 | 2.74 | 0.197 | 0.059 |
| beat15 | Medium | 88.3 | 90.9 | 2.07 | 2.05 | 0.183 | 0.052 |
| beat15 | High | 53.4 | 54.1 | 2.73 | 2.72 | 0.195 | 0.057 |
| storm | Medium | 68.3 | 69.1 | 2.46 | 2.5 | 0.185 | 0.056 |
| storm | High | 48.5 | 48.3 | 3.08 | 3.1 | 0.198 | 0.061 |
| marina | Medium | 88.2 | 88.6 | 2.01 | 2.06 | 0.184 | 0.054 |
| marina | High | 51.7 | 52.1 | 2.63 | 2.51 | 0.19 | 0.055 |
| coast-day | Medium | 87.8 | 83.3 | 2.2 | 2.19 | 0.186 | 0.055 |
| coast-day | High | 51.3 | 51.4 | 3.12 | 3.07 | 0.227 | 0.068 |
| coast-night | Medium | 102.9 | 102.8 | 2.04 | 1.98 | 0.181 | 0.054 |
| coast-night | High | 52.9 | 56.1 | 2.94 | 2.89 | 0.2 | 0.06 |
| gulf-sea | Medium | 110.6 | 110.7 | 2.03 | 2.0 | 0.186 | 0.055 |
| gulf-sea | High | 60.3 | 60.9 | 3.0 | 2.95 | 0.205 | 0.064 |
| helm-eye | Medium | 90.2 | 92.3 | 2.05 | 2.08 | 0.181 | 0.054 |
| helm-eye | High | 54.2 | 54.2 | 2.88 | 2.85 | 0.198 | 0.06 |
| slip | Medium | 73.2 | 74.3 | 2.2 | 2.16 | 0.188 | 0.055 |
| slip | High | 46.6 | 46.7 | 2.69 | 2.57 | 0.195 | 0.057 |
| bridge | Medium | 97.0 | 98.4 | 2.04 | 2.0 | 0.185 | 0.054 |
| bridge | High | 55.7 | 56.0 | 2.87 | 2.77 | 0.208 | 0.061 |
| crew | Medium | 118.5 | 118.5 | 1.72 | 1.74 | 0.175 | 0.052 |
| crew | High | 67.9 | 68.9 | 2.56 | 2.48 | 0.192 | 0.058 |
| marina-night | Medium | 90.1 | 90.9 | 1.98 | 1.93 | 0.185 | 0.054 |
| marina-night | High | 59.4 | 59.6 | 2.41 | 2.33 | 0.188 | 0.055 |

Medium's lowest view is 69.1 fps (storm) against the 60 gate, High's 46.7 (slip) against 45. The crew's slice of the
game thread falls from about 0.19 ms to 0.06 ms in every view; what is left is the placement, the hand targets and the
input. The game thread's mean over the views falls from 2.07 to 2.06 ms on Medium and from 2.81 to 2.75 ms on High.
The posing now runs on the animation workers.

## Left for later

- Today's models have no `HandholdCabin`/`HandholdCoaming`/`Seat`/`FootBrace`/`SideDeck`/`CockpitSole` sockets; the hero J/22 does. When it replaces the model, the pawn picks its sockets up by name.
- The tiller and sheet holds are still chosen on the game thread, from the shoulders as last posed (one frame behind), so the rig lines can be drawn there. The IK itself is in the node.
- No animation clips: everything is procedural. A clip layer (CMU, Epic's Game Animation Sample, Mixamo) would go under the reaction layer.
