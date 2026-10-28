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
