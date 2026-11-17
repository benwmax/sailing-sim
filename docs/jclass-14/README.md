# J-Class 14: Bluebonnet in the game

Slice 14 of *Bluebonnet*, our own J-Class sloop of 1937 (plan and Bean's decisions:
<https://claude.ai/artifact/WdUKp8somgyNJZDyESCgyU>; her physics sheet and estimated polar are slice 13,
[docs/jclass-13](../jclass-13/README.md)). On November 17 Bean asked for her in the first slice release (since moved to
the end of November), and chose where she sails: Galveston's Bolivar Roads and the lake's deep south end, plus a Career
entry. Four steps, in this one pull request:

1. **The code** (below, "What is in"): she is an `EBoatType` in the physics and the game, with her polar, her tests,
   her wheel and crew places, a Boat screen card and the deep-water rule for launch spots.
2. **Her model's export and her Career entry** ("Her model in the game", "Career"): `Tools/shipkit/jclass/export_game.py`
   cuts her Blender build into the game's four parts with their sockets; her paint is a livery class; the Club Racer
   certificate opens her. These touch `Tools/`, `scripts/`, `Inputs/` and `Content/`, so the pull request needs Bean's
   label.
3. **The PC's import** ("Step 3 on the PC"): builds her, imports `/Game/Boats/Bluebonnet` and commits the assets (the
   cloud can't push Git LFS), then the Windows check.
4. **The Mac's gates**, then the merge.

Until her model is imported she draws as the procedural stand-in every boat without a model gets (`ModelMeshesFor`
checks for `SM_Bluebonnet_Hull` first).

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

## Her model in the game (step 2)

`Tools/shipkit/jclass/export_game.py` opens her build (`jclass.blend` from `build_jclass.py`, slices 1 to 12), poses it
and writes the four parts `ASailboatPawn::ModelMeshesFor` hangs a boat on, as FBX, and `Bluebonnet_sockets.json` (the
points the game reads, the part that owns each, each part's origin) into `Artifacts/models`. What goes in each part,
how the moving ones are posed, the game slot of each of the build's materials, what stays out and why, and every
socket are in `Tools/shipkit/jclass/game_bluebonnet.json`: edit that, never the FBX. `scripts/make-boat-models.sh` (and
`scripts\windows\make-boat-models.ps1`) rebuild her when a `Tools/shipkit/jclass` script or json is newer than the
build (`JCLASS_REBUILD=1` / `-RebuildJClass` forces it, `SKIP_JCLASS=1` skips her), export her, and
`scripts/import_boats.py bluebonnet` imports her (the default run imports her too when her sockets json is there).

| Part | Origin (body frame, m) | What is in it | Triangles | Slots |
|---|---|---|---|---|
| `SM_Bluebonnet_Hull` | 0, 0, 0 | shell, transom and its letters, deck, toe rail, hatches, skylights, companionway, doghouse, cockpit, steering, wheel, winches, running fittings, deck hardware, the cowls' caps, the stowed spinnaker pole | 510,758 | PackCanoe, PackDeck, WoodMahogany, Brass, PackFit, PackCanvas, RedPlastic, WhitePlastic |
| `SM_Bluebonnet_Mast` | 3.0, 0, 1.475 (the partners) | mast and spreaders, shrouds, stays, runners and checkstays let off | 94,828 | Aluminium, Brass, PackFit |
| `SM_Bluebonnet_Boom` | 2.578, 0, 3.730 (the physics' gooseneck) | the boom on the centreline | 15,380 | PackFit, Brass |
| `SM_Bluebonnet_Rudder` | -8.046, 0, 0 (stock axis at the waterline) | the rudder (the keel's after part) and its stock | 7,246 | PackCanoe, Brass |

Every part is Nanite with a fallback at 6% of its triangles, the mast too: her standing rigging is in it (the game
draws no live standing rigging for her), 95k triangles, past the 40k a non-Nanite boat part may have
(`SailingSim.Visual.BoatBudget`), and her mast bend is held at zero so nothing moves in M_BoatMast (which is
`used_with_nanite`). Her sails, sheets and the mainsheet are the game's own, drawn live from the physics; the build's
sails, running rigging, flags, the light copies and below decks stay out.

**What the export checks** (it stops, and the build is not imported, if any fails): the canoe as exported (the shell's
paint, the lead keel painted with the bottom, and the rudder, cut at the load waterline) against her physics' canoe and
keel; her length, beam and draft; the hounds above the genoa's head (else the game lowers the sail); the mast's
partners at `MastX`; every socket within its fitting's surface; every material with a game slot. On the slice 12 build:

| | Model | Physics |
|---|---|---|
| Displacement | 153.446 m³ | 153.513 m³ (canoe 128.048, keel and rudder 25.465): 0.04% |
| Centre of buoyancy | x -0.678, z -1.030 | x -0.675, z -1.035 (6 mm) |
| Length, beam, draft | 39.929, 6.556, 4.521 m | 39.929, 6.556, 4.521 m |

**Sockets** (21): on the hull `MastStep`, `RudderPivot` and `RudderAxis` (a second point 1 m up her raked stock),
`JibLead_S/P` (the genoa cars), `JibWinch_S/P`, `JibTailer_S/P`, `JibTailRest_S/P`, `LazySheetVia` (2.6 m up, over the
doghouse's roof), `Traveler_C` and `Traveler_S` (inside the mainsheet's after block on the counter: she has no traveller,
so the game's car hides in it); on the mast `MastBase`, `Hounds`, `SpreaderTip_S/P`; on the boom `Boom_Mainsheet`; on the
rudder `TillerEnd` (the helm's hand at the wheel's rim, on the stock's axis) and `RudderStock`. No `ForestayTack`,
`Chainplate*` or `BackstayPlate`, so nothing is drawn twice, and no crew sockets: her crew's places come from her deck.

**Game code for her model.**
- *A raked rudder.* Her stock leans 39 degrees aft. When a hull has a `RudderAxis` (or `RudderAxis_<n>`) socket the pawn
  turns that rudder about the line from its pivot to it (`ASailboatPawn::RudderAxes`); every other boat turns about
  the vertical as before.
- *No mast bend for her* (`MastBendCm` held at 0): her wires and fittings are in the mast's mesh and would not bend
  with it.
- *Her spars painted*, and the stowed pole on the hull's part with them (`PaintSpars` on the hull for her).

**Her paint** is a livery class (`Inputs/g3/boat-catalogue.json` class `bluebonnet`, `Tools/fleet/make_liveries.py`,
`BoatLiveryData.inl` regenerated): dark blue topsides (#1E3076), a cream boot stripe and a gold cove line, red-brown
bottom, buff deck and spars, teak trim; one scheme and three wear looks (the four `SailingSim.Skin.BuiltIn` wants), no
sail number (her club's star).

**Known gaps** (cosmetic; for after the release):
- The boom turns about the physics' gooseneck (x 2.578); the model's pin is 0.227 m aft of it, so its jaw moves off the
  mast as she eases.
- The spinnaker's head is placed by the config's mast front (x 3.19), about 1 m ahead of her raked masthead.
- The physics' genoa luff meets the deck 0.5 m ahead of the model's forestay (18.40 against 17.88), and with no live
  forestay there are no hanks.
- The main's cloth is kept off the lowest spreaders only, not her static shrouds above them.
- Her live sheets are J/22-sized rope, and no halyards are drawn.
- The helm stands 0.7 m aft of the wheel; the hand may fall short of the rim.

The Mac's rig tests that loop over every boat (`SailingSim.Visual.RigClearance`, `SailShrouds`, `SheetClearance`,
`TrimmerTailsJib`) now see her model and may list some of these.

## Career

The Club Racer certificate opens her, beside the ILCA 7 (`Content/Career/career.json`): the club's racing program
ends with a turn on its racing yacht. With it she sails from the lake's deep spots, and from Bolivar Roads once the Day
Sailor certificate has opened Galveston. Before it her Boat screen card says "Earn the Club Racer certificate"; Free
Sail has her from the start. `docs/career/README.md` lists her; `SailingSim.Career.Content` and `SailingSim.Career.Unlocks`
check it. (Moving her to the Day Sailor certificate is a one-line change in `career.json`, if Bean prefers.)

## Step 3 on the PC

```
scripts\windows\make-boat-models.ps1 -Parts bluebonnet
```

builds her (`build_jclass.py`, about 20 to 40 minutes the first time), exports her and imports `/Game/Boats/Bluebonnet`;
then commit `Content/Boats/Bluebonnet` (Git LFS) to this branch and run the Windows check. On the Mac the same is
`IMPORT_ARGS=bluebonnet scripts/make-boat-models.sh` (it rebuilds every boat's FBX, then imports only her).

## Tests

- `SailingSim.Physics.BluebonnetHull`: her config against slice 13's `physics.json` (mass, canoe depth, displaced
  volume, length, beam, draft, crew, no engine, a wheel) and her stability (righting moment positive and rising to 45
  degrees, GM 1.9 to 2.3 m).
- `SailingSim.Physics.BluebonnetRoll`: above.
- `SailingSim.UI.DeepKeelStarts`: every spot of the lake and Galveston has a depth; every club boat fits each; she fits
  four lake spots and one at Galveston, and her lock names the dam or Bolivar Roads.
- `SailingSim.Fleet.*`: her entry in the fleet table (length, sail area, engine, reef) and her polar (heavy list).
- `SailingSim.Visual.BluebonnetMesh` (step 2): her imported model against her physics as `FleetMesh` holds the fleet
  (displacement 2%, centre of buoyancy 5 cm, length, beam and draft 2 cm), the sockets on their parts, `MastStep` at
  `MastX`, the hounds over the genoa's head, the rudder's axis raked 39 degrees aft, no live-wire sockets, every part
  Nanite within 8 slots of `MI_Boat_*`, and the mast's `Aluminium` slot. Skipped with a warning until the PC imports her.
- `SailingSim.Career.Content`, `SailingSim.Career.Unlocks`: the Club Racer certificate opens her.

Nothing here is compiled or run in the cloud except the physics (standalone, as CI does) and the export (Blender's
`bpy` module, on the slice 12 build: the numbers above); the game code and every test need the Mac's build, and the
PC's MSVC build checks it on Windows. `python3 Tools/career/validate.py` and `scripts/licence-check.sh` pass (the
licence table's Track D bark row had an unquoted comma; it is quoted now).
