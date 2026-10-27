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
