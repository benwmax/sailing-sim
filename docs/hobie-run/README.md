# The Hobie 16 capsizing on a deep run (in progress, paused Oct 27 2026)

The report, from the PC: the Hobie 16 capsized within 25 s running deep, at TWA 170 in 14 kn, on the demo autopilot.

## Standalone: no capsize

`Tools/HobieRun/main.cpp` runs on the physics alone, built with clang against `Source/SailingPhysics` like
`scripts/polar.sh`, from the repo root. The setup:
- `FAutopilot` holding TWA 170;
- `FAutoTrim` with the crew's hands, and again with ideal trim;
- flat water and 5 km of lake chop;
- steady wind and W1's climate gusts.

All 8 runs stay upright for 120 s, with heel at most 15 deg and pitch at most 8 deg.

## Not tried yet

The game itself was paused before it ran. In the game the run differs:
- `-SailingDemo`, the pawn's demo autopilot, may gybe;
- the pawn's `TrimAssist`;
- the lake's real wind field, shelter and sea map.

The planned check is `scripts/capture-scenes.sh` on `-SailingBoat=Hobie -SailingTWA=170 -SailingHoldTWA=170
-SailingWind=14`, gusty and steady, reading the capsize column of its telemetry.

## In the game (Mac, Oct 28 2026)

The lake at (5500, 600), heading 135, AfternoonBreeze at 15:30, 14 kn, `-SailingBoat=Hobie -SailingTWA=170`, High, the
Chase capture (uncooked, `scripts/capture-scenes.sh`), on hobie-run (main b167e016):

| Run | Args | Time | Max heel | Max pitch | Capsized |
|---|---|---|---|---|---|
| hobie-gusty | `-SailingDemo -SailingHoldTWA=170` | 44 s | 12.6 deg | 5.2 deg | no |
| hobie-steady | same, `-SailingGust=0` | 44 s | 16.2 | 4.4 | no |
| hobie-easy | same, `-SailingEasy=1` | 44 s | 15.8 | 5.7 | no |
| hobie-real | same, `-SailingEasy=0` | 44 s | 13.1 | 4.8 | no |
| nodemo-easy | no demo (no autopilot, the pawn's trim assist), `-SailingEasy=1` | 64 s | 12.7 | 5.6 | no |
| nodemo-real | no demo, `-SailingEasy=0` | 64 s | 23.4 | 5.6 | no |

The true wind crosses her stern 25 to 47 times a run at TWA 170 (by the lee and back), and nothing capsizes her. On the
Mac it is neither the demo autopilot, the trim assist, Easy mode nor the lake's wind and sea map. Closed here as a PC-only
artefact. What the PC should check, in this order: the same args with `-SailingCapture=Chase` (the telemetry CSV, heel
and `capsized` per frame); then `-SailingCrewFalls=0` (the crew's ragdolls are on by default on Ultra only); then
`-SailingQuality=High` (Ultra's other differences); and the frame rate (the boat steps at most 12 physics steps a frame).

## The PC's capsize, and the fix (Oct 28 2026)

The PC reproduces it on main f91c8660 in every run (`pc/README.md`, its four CSVs here) off the I-30 bridge
(`-SailingStartAt=6400,877,0`, AfternoonBreeze at 13:00, gusting 18). The Mac with the same args, High, uncooked:
capsized at 15.2 s (the PC's 15.4 s). My six earlier runs started at the launch spot in steadier air.

What tips her is not a gybe first. In the PC's trace the heel grows to windward from 5 to 43 deg while the TWA is still
-164 to -178 and the tiller is hard over to head up; she gybes only past 50 deg. Standalone (`Tools/HobieRun`, 120 s
holds at TWA +-170 in 14 kn with a 1.3 gust factor on 5 km of chop) shows the start: a hard bear-away to answer a
wave's yaw rolls the cat to windward, and with the rig over to windward she keeps bearing away. And a fast cat at 0.4 of
the wind's speed runs on a weak apparent wind from astern that swings 100 deg in half a second, so the boom comes across
with the true wind still on one side.

`FAutopilot`'s run guard (AutoTrim.h) is what a sailor does on a run: keep off dead downwind by a margin that grows with
the gusts and with her speed over the wind's, a light hand on the tiller (half the gain, little bear-away), and a smart
head-up past 175 deg, by the lee, or with the apparent wind deep. A gybe she is told to make goes through. It acts only
where the helm is given the wind: the demo autopilot now (`-SailingNoRunGuard` compares). The polars, scenarios and sea
trials don't give it, so PolarGate and `polar.sh --quick` (0 of 39 outside tolerance) can't move. The traffic AI is left
without it: with it, the AI races (`traffic.sh 98`) went from a mean 1,751 s with every boat finishing to 2,712 s with 14
of 32 races short, because the AI's route doesn't gybe downwind to make up the angle. That is a follow-up.

| 48 holds, TWA +-170, 120 s | Capsized | The boom across | Deepest TWA |
|---|---|---|---|
| No guard | 8 | 48 | 180 |
| Guard | 0 | 1 | 167.7 |

In the game, with the PC's args (High, the final code, 64 s each):

| Run | Capsized | Max heel | Deepest TWA | Across dead downwind |
|---|---|---|---|---|
| `-SailingNoRunGuard` | at 15.2 s | 87.7 deg | 179.9 | twice |
| Guard | no | 15.3 deg | 160.7 | never |
| Guard, again | no | 15.2 deg | 160.7 | never |

Gate: `scripts/gate.sh --scope water --merge hobie-run` (origin/main + 75df07a4): all 254 tests passed (the physics changed,
so the whole suite with the heavy set, PolarGate and the new HobieRunGuard among them); the game packaged (full recook);
every view ok: High beam8 59.9, beat15 54.8, storm 49.4, marina 57.8, coast-day 53.4, gulf-sea 63.1, helm-eye 60.0,
bridge 59.1 fps; Medium storm 68.8.

### A controlled gybe (physics, not tuned)

Told to gybe after 30 s from TWA -160 to +160 in 14 kn gusting to about 18, she goes round once and stays up: max heel 9
deg on flat water, 22 deg in the chop. The same gybe with the old helm in the chop capsized 4 s after the call (the same
windward roll, from the full-gain helm). So a controlled gybe in this breeze survives, as a real Hobie 16's does with
the crew across; no realism question about the hull or sails from it.

`SailingSim.Physics.HobieRunGuard` holds this: four seeds each side upright for 120 s, never across dead downwind and
deepest under 175, and the ordered gybe through and upright.
