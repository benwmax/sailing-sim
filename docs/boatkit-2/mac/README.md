# Boat kit 2 on the Mac (PR #78 gate)

PR #78 head merged with main 11b6038c (the merge was clean). Built, then `import_boat_detail.py` and
`import_j22_hero.py` run in the editor. The reimported assets are not committed: the branch keeps the PC's.
Stills are from `run-game.sh` (uncooked, High, AfternoonBreeze 10 kn, TWA 45, wind from starboard).

## Numbers

| Check | Result |
| --- | --- |
| `polar.sh --quick` | 0 of 39 outside, worst 6.9% (same as main and the PR's table) |
| `polar.sh --scenarios` | tacks 6.2 / 4.6 / 4.0 s at 6 / 10 / 15 kn (main 6.4 / 4.7 / 4.1); irons unchanged in kind |
| Tests | PolarGate, J22RigPosition, LeewayAndWeatherHelm, ReferenceChecks, J22Mesh, J22HeroMesh, FleetMesh, MetaHumanCrew, Crew* (9), Traffic (5): all pass; gate run: 146/146 |
| `gate.sh --scope boats` | pass (table below) |

| View | Medium fps | High fps |
| --- | --- | --- |
| beam8 | 90.6 | 61.2 |
| beat15 | 86.3 | 55.6 |
| marina | 95.8 | 61.7 |
| coast-day | 84.0 | 54.0 |
| helm-eye | 88.4 | 55.1 |
| slip | 82.5 | 52.3 |
| crew | 71.8 | 51.6 |

## What the stills show

- `player_side`: the default J/22's main luff runs up the mast and the jib sets ahead of it. The mast is in line with the sails.
- `slip`, `hero_slip_hoist`: the berthed J/22s' masts stand at the forward end of their cabins, like the player's boat.
- `race_fleet`: one AI J/22 far off, mast in line at that distance. I could not get an AI boat close: race and traffic
  both start them far away. They draw the same default meshes (`ModelMeshesFor`), so they get the same mast.
- `hero_helmeye`, `hero_cockpit`, `hero_winch_port`, `tail_c`, `tail_front`: the jib track and car are on the cabin
  top outboard of the handrail, with the winch on its aft outboard corner on both sides. There is one chainplate a side
  at the sheer, taking both shrouds. The gooseneck fitting is on the mast's aft face (`hero_mast_gooseneck`).
- Bow crew: no crew stance stands at the mast. On a beat the forward sailor hikes on the windward rail beside the
  cabin-top winch (`tail_top`, `tail_front`), well aft of the moved chainplate and shrouds. Nothing clips.

## The trimmer's hand on the jib sheet tail: not in the hand

On a starboard-tack beat the jib is to port. The working (red) sheet runs from the port car to the port cabin-top
winch. All three crew hike on the starboard rail, so the trimmer is about 1.5 m from the leeward winch. The
trimmer's hands are on their knee and the rail, not on any line (`tail_top`). `Hold` finds no grip in reach, so
`JibGripCm` is unset and the tail takes the fallback in `BoatModelVisuals.cpp` (`Tailer + (-30, +/-12, -16)` cm).
The winch sits about 13 cm from the cabin top's aft edge, so that point lands past the edge. The tail runs from the
winch over the aft corner and stops in mid-air beside the cabin's aft face, about 15 cm below the cabin top
(`tail_floating_crop`, `tail_a`). It does not clip, but it visibly floats.

The fallback was written for the coaming winches. On the cabin top it should lie on the cabin top (forward or
inboard of the winch, Z about the socket height) or drop to the cockpit sole. Better still, the trimmer should tail
across from the windward side, as J/22 crews do when hiking.
