# J-Class 14: Bluebonnet in the game (the code half)

Slice 14 of *Bluebonnet*, our own J-Class sloop of 1937 (plan and Bean's decisions:
<https://claude.ai/artifact/WdUKp8somgyNJZDyESCgyU>; her physics sheet and estimated polar are slice 13,
[docs/jclass-13](../jclass-13/README.md)). On November 17 Bean asked for her in the first slice release (since moved to
the end of November), and chose where she sails: Galveston's Bolivar Roads and the lake's deep south end, plus a Career
entry. This pull request is the code half: she is an `EBoatType` in the physics and the game, with her polar, her
tests, her wheel and crew places, a Boat screen card and the deep-water rule for launch spots. It changes only
`Source/` and this page.

Still to come, in their own pull requests: her model in the game (an export from her Blender build to
`/Game/Boats/Bluebonnet`, sockets included, and her `career.json` entry, both needing Bean's label; then the PC's
import). Until her model is imported she draws as the procedural stand-in every boat without a model gets
(`ModelMeshesFor` checks for `SM_Bluebonnet_Hull` first).

## What is in

- **Physics.** `EBoatType::Bluebonnet` (after the maxi). `Fleet.cpp`'s `Bluebonnet()` takes slice 13's baseline
  unchanged (`BluebonnetHullData.inl`, `BluebonnetConfig.inl`: 31 sections, 153,513 kg, the lead, the keel plane, the
  rig and sails, 30 crew at 2,321.5 kg), then three knobs, each with its reason in the code: the residuary table at
  0.6 of the J/22's scaled one (slice 13's tuning), `TrimRollSeconds` 8.0 (below) and 12 crew figures drawn.
- **Reference polar.** Slice 13's estimate (6, 10 and 16 knots; 52, 60, 90, 120 and 150 degrees; spinnaker from 120),
  at 20% tolerance as an estimate. `SailingSim.Fleet.Polar.Bluebonnet` sails it (a heavy test).
- **Wheel and crew.** She steers with a wheel on the centreline aft (the helm stands at x -10.85, 1.1 m off it). Her
  crew stand on deck like the maxi's (`bDeckCrew` in `CrewPlacement`); her cockpit well, doghouse and deck camber are in
  `CrewPose.cpp` from her deck plan (`deck_bluebonnet.json`). The Boat screen strip shows her (dark blue hull,
  flush-decked icon); her card says she draws 15 feet and has no engine.
- **Deep-water starts.** A launch spot now carries the bake's `depth_m` (`FLaunchSpot::DepthM`, `SailCatalog::FSpot`).
  `LaunchSpotFits` wants a fifth of the boat's draft under her keel: her 4.52 m needs 5.4 m. Every club boat fits every
  spot (the shallowest is 2.0 m, the deepest club keel 1.6 m); she fits Bolivar Roads (6.0 m) at Galveston and four of
  the lake's five spots (8.2 to 13.1 m; not the north lake's 2.2 m), and every Gulf passage spot. The Boat screen
  locks her card at a spot too shallow and names the deepest spot she can start from (`SailCatalog::DepthLockReason`);
  if she arrives there anyway (an old save, a lesson), `ASailingGameMode::GetLaunchSpot` starts her at the world's
  deepest spot. The maxi's 6 m keel follows the same rule: the prologue starts her in the Gulf (11 to 18 m), the lake's
  four deep spots fit her, and at Galveston, where nothing does, she now starts at Bolivar Roads instead of a marina.
- **Save.** Her save id is `Bluebonnet`.
- **Camera.** The overview and classic camera (`ChaseCamera::RigFor`) look a third of the way up the mast from at most
  40 m; with her 48 m rig that put her hull under the frame's bottom 8 degrees (`SailingSim.Visual.ChaseCamera.Rig`). Their
  arm now keeps that look-up within 21.2 degrees, which only she needs: 40.7 m instead of 40 for her, and the maxi
  (46.7 m rig, 21.1 degrees) and every other boat keep the old numbers.

## Her roll, and the trimmer's fix

Sailed upwind in the game's own crew logic, she rolled: from 13 knots she swung between 1 and 30 degrees of heel every
10 seconds and never settled. The trimmer (`FAutoTrim`, both the ideal one the polars use and the hands one) was
chasing her roll. As she rolls to windward, her masthead moves into the wind and the sails see a freer wind; the
trimmer sheets in; her heel builds; it eases, reading the heel 0.3 s ahead; she comes up, and so on. On the J/22 (roll
period 1.7 s) that loop is too fast to matter. On a boat that rolls once in 8 seconds it is a limit cycle.

Her crew wouldn't do that: no one trims a J to a single roll. So `FBoatConfig::TrimRollSeconds` (0 for every boat but
her: the others are byte-for-byte unchanged) sets her free roll period, and the trimmer sees the sails over half of it
and reads the heel a quarter of it ahead. Free roll periods measured in the physics: J/22 1.67 s, maxi 7.06 s,
Bluebonnet 7.99 s, so hers is 8.0.

After the fix, close-hauled (52 degrees), last 20 s of 90:

| Wind | Speed (ideal trimmer) | Heel range, ideal | Heel range, hands |
|---|---|---|---|
| 12 kn | 9.72 kn | 22.1 to 22.2 | 22.2 to 22.3 |
| 16 kn | 10.55 kn | 22.1 to 22.3 | 22.9 to 23.0 |
| 20 kn | 11.06 kn | 22.1 to 22.2 | 21.0 to 24.3 |
| 24 kn | 11.24 kn | 22.2 to 22.4 | 21.1 to 23.8 |

She tacks in 12.6 s in 8 knots, 9.3 in 12 and 8.9 in 16. `SailingSim.Physics.BluebonnetRoll` holds the heel range under
5 degrees with both trimmers and logs what she does without the fix.

## Her polar

`scripts/polar.sh --boat blue`: 0 of 15 points outside 20%, worst 12.4% (slice 13's trial had two points outside, at
-19.5 and -19.6%; the roll was most of that).

| TWS | 52 | 60 | 90 | 120 | 150 |
|---|---|---|---|---|---|
| 6 kn | -3.6% | -4.2% | -3.4% | +4.6% | +2.3% |
| 10 kn | -6.3% | -6.3% | -1.1% | -0.5% | +5.6% |
| 16 kn | -12.4% | -11.9% | -8.5% | -7.3% | +3.7% |

She is still slow upwind in a breeze, as slice 13 found; the knobs that close it (keel aspect ratio, main and genoa
induced aspect ratios) are listed there. The J/22 is unchanged: `scripts/polar.sh --quick` 0 of 39, worst 8.0%.

## Tests

- `SailingSim.Physics.BluebonnetHull`: her config against slice 13's `physics.json` (mass, canoe depth, displaced
  volume, length, beam, draft, crew, no engine, a wheel) and her stability (righting moment positive and rising to 45
  degrees, GM 1.9 to 2.3 m).
- `SailingSim.Physics.BluebonnetRoll`: above.
- `SailingSim.UI.DeepKeelStarts`: every spot of the lake and Galveston has a depth; every club boat fits each; she fits
  four lake spots and one at Galveston, and her lock names the dam or Bolivar Roads.
- `SailingSim.Fleet.*`: her entry in the fleet table (length, sail area, engine, reef) and her polar (heavy list).

Nothing here is compiled or run in the cloud except the physics (standalone, as CI does); the game code and every test
need the Mac's build, and the PC's MSVC build checks it on Windows.
