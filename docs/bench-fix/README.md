# Bench fix: measuring runs sail the J/22 at the lake

The packaged game's `GameUserSettings.ini` held the player's last session (Galveston Bay, the Lagoon 42; saved Oct 14
20:34), and bench, capture, shot, demo and drill runs read it. Every bench since then sailed the Lagoon: views that
pass `-SailingWorld` were in the right world with the wrong boat, and views that didn't (bench-phase2..4) were at
Galveston. `-SailingBoat=J22` matched nothing either (the name is `J/22`), so bench-phase4's J22 row kept the Lagoon.

## What changed

- `USailingSettings::IgnoresSavedChoices()`: true for `-SailingBench=`, `-SailingCapture=`, `-SailingShot=`,
  `-SailingDrill=`, `-SailingDemo` and automation runs. `ASailingGameMode::InitGame` then calls `UseRunDefaults()`
  once per process: every config property goes back to the class default (snapshotted in the CDO constructor before
  the ini loads), so the run is the J/22 at Rush Creek, Lake Ray Hubbard, plus its own command line. The front end's
  off switch uses the same test.
- Those runs never write the ini: `USailingSettings::Save`, the Continue session, drills passed and key rebinds skip
  `SaveConfig`. After the bench below, the player's ini still reads `World=1`, `BoatType=7`.
- `-SailingBoat=<prefix>` (`USailingSettings::MatchBoatName`) ignores case, spaces and slashes on both sides and keeps
  prefix matching; an unknown name logs a warning.
- `scripts/bench-mac.sh` and `scripts/run-game.sh` (so bench-visual, bench-phase2..8 and capture-scenes) pass
  `-SailingBoat=J22 -SailingWorld=Lake` unless the run names its own.
- Tests: `SailingSim.Smoke.BoatNameMatch` (J22, j/22, J/22 match; J24 doesn't), `SailingSim.UI.MeasuringIgnoresSave`
  (a saved Galveston/Lagoon session is not written and the run defaults are the J/22 at spot 0 on the lake). All 131
  SailingSim tests pass.

## Bench (packaged, Mac, 12 s per view): the baseline from now on

Lowest view per tier: **Medium, storm 69.2 fps** (gate 60), **High, slip 46.8 fps** (gate 45; storm 47.5). These match
the earlier lows (storm 68.8, slip 46.7), which never had the Lagoon in a heavy frame. The views where the boat fills
the frame dropped once the J/22 and her MetaHuman crew were in it: crew 118.6 to 74.1 on Medium and 68.7 to 47.6 on High,
helm eye 91.9 to 83.7 / 54.2 to 49.0, marina at night 91.3 to 81.9 / 58.7 to 53.0. The earlier numbers in those
views were the Lagoon's (no MetaHumans), so they flattered the game.

| view | tier | fps | p99 ms | GPU ms | earlier (Lagoon), fps |
|---|---|---|---|---|---|
| beam8 | Medium | 90.9 | 11.88 | 10.8 | 93.5 |
| beam8 | High | 56.3 | 19.88 | 16.36 | 56.7 |
| beat15 | Medium | 89.5 | 12.37 | 10.52 | 89.8 |
| beat15 | High | 55.1 | 21.82 | 16.78 | 54.5 |
| storm | Medium | 69.2 | 16.08 | 14.25 | 68.8 |
| storm | High | 47.5 | 23.79 | 20.48 | 47.8 |
| marina | Medium | 90.7 | 12.39 | 10.29 | 88.7 |
| marina | High | 51.7 | 21.63 | 17.03 | 51.1 |
| coast-day | Medium | 82.6 | 12.75 | 11.9 | 86.5 |
| coast-day | High | 48.9 | 21.81 | 16.37 | 49.5 |
| coast-night | Medium | 103.2 | 10.61 | 9.52 | 102.6 |
| coast-night | High | 52.3 | 20.53 | 12.87 | 51.3 |
| gulf-sea | Medium | 110.1 | 9.66 | 8.68 | 111.2 |
| gulf-sea | High | 62.4 | 17.23 | 13.62 | 61.0 |
| helm-eye | Medium | 83.7 | 13.02 | 11.38 | 91.9 |
| helm-eye | High | 49.0 | 22.56 | 20.59 | 54.2 |
| slip | Medium | 75.8 | 15.25 | 13.05 | 73.8 |
| slip | High | 46.8 | 23.46 | 19.39 | 46.7 |
| bridge | Medium | 99.0 | 10.81 | 9.48 | 98.4 |
| bridge | High | 55.7 | 19.64 | 14.91 | 56.4 |
| crew | Medium | 74.1 | 14.45 | 12.79 | 118.6 |
| crew | High | 47.6 | 22.94 | 18.52 | 68.7 |
| marina-night | Medium | 81.9 | 13.77 | 12.56 | 91.3 |
| marina-night | High | 53.0 | 21.0 | 17.27 | 58.7 |

Earlier: `docs/gulf-swell/bench-visual.csv`. Full columns: `bench-visual.csv`; screenshots `<view>-<tier>.png`.
