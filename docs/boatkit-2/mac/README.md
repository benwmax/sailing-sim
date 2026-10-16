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

## PR #83 on the Mac: the tail on the cabin top (pass)

PR head 93a60b01 merged with main 0cba4771 (clean; merge commit 5db9c611). The PC's re-imported `SM_J22H_Hull` was
used as committed (no local re-import). Tests: J22Mesh, J22HeroMesh, FleetMesh, MetaHumanCrew, J22RigPosition,
PolarGate pass; `gate.sh --scope boats` passes (135/135 tests; every view within 0.6 fps of the #78 table above, so no A/B):

| View | Medium fps | High fps |
| --- | --- | --- |
| beam8 | 90.5 | 60.6 |
| beat15 | 86.1 | 55.3 |
| marina | 96.2 | 62.1 |
| coast-day | 83.9 | 53.9 |
| helm-eye | 88.4 | 55.0 |
| slip | 82.5 | 52.0 |
| crew | 70.8 | 51.4 |

Stills (`run-game.sh`, High, `-SailingJ22Hero`, TWA 45 wind from starboard, so the jib and its red working sheet are to
port; `-SailingCamTarget=-0.2,-0.55,1.0` on the port winch):

- 12 kn, crew hiking to starboard, tail unheld: `pr83_lee_top` (from above), `pr83_lee_b` (from the port quarter),
  `pr83_lee_a` (from forward). The tail leaves the self-tailer and runs forward and inboard, lying on the cabin top
  just inboard of the jib track. It no longer reaches the trunk's aft edge, nothing hangs in the air beside the cabin's
  aft face, and it is clear of the coaming. Compare `tail_floating_crop` above.
- Windward side, 12 kn: `pr83_wind_a`. Only the lazy (green) sheet runs to the starboard winch, as before; no tail is
  drawn there (the tail is the working side's only). `pr83_cockpit` (`-SailingCockpit`) looks over the starboard winch:
  nothing changed there.
- Held: at 4 kn the crew sit to leeward and the tail runs aft from the winch into the trimmer's hand (`pr83_held4_top`);
  at 7 kn the trimmer sits in the cockpit and the tail drops from the winch over the coaming to the hand
  (`pr83_held7_b`). Same as before the change: the rest point is only used when no hand is in reach.
