# A ship's rig on the model

The frigate *Commonwealth*'s yards brace and hoist, her spanker's boom and gaff swing, and each sail shows set, clewed up
or furled, following the physics (`docs/frigate-physics/`). The model's parts come from the build (`docs/shipkit-3`,
`docs/shipkit-5`): one mesh per spar and per sail state, all in the ship's frame.

## The table

`Tools/shipkit/frigate/rig_table.py <build dir> Source/SailingPhysics/Private/CommonwealthRigData.inl` turns the build's
`rig.json` and `sails.json` into the table the game reads (`ShipRig.h`, `CommonwealthRig()`). Edit the build or the script,
never the `.inl`. For each moving spar: its pivot and axis, how far it lowers, its brace limits (hoisted, and by hoist for
the yards that lower), how far its truss or parrel lets it come forward as it braces (hoisted and lowered), and what
turns it. For each sail: the spar it rides on, its objects (`Head` in every state, then one of `Set`, `Clewed`,
`Furled`), the plane its `Set` is mirrored about for the starboard tack, and its yard's limits and ease with it set.

The eleven square sails are the physics' (`FSquareRig::Sails`) in the same order. Spars with no sail of their own: the
crossjack braces with the mizzen topsail above it, the spanker's boom and gaff go with the main boom, the spritsail yard
stays square.

## The pose

`FShipRigPose::Update` takes the physics' state (`FShipRigInput`: each yard's angle, how much of each sail is out, which
are asked furled, the boom, the fore-and-aft sails' share set and side):

- A yard turns by the physics' angle, the model's way round (the physics' + is the starboard arm forward, the model's +
  the starboard arm aft), held inside the rigging's limits at its hoist and, with its sail set, the sail's. It comes
  forward by its ease table at that angle, then turns.
- A sail shows `Set` from half out, `Furled` when it is asked furled and in, and `Clewed` between (being clewed up or
  set, or loosed and waiting on its yard).
- A topsail, topgallant or royal asked furled is clewed up first; then its yard comes down its mast (30 s for the whole
  travel, braced nearly square by the lowered limits) and the sail shows furled on it. Loosed, the yard goes back up.
- The headsails, staysails and spanker are modelled on the port tack (lying to starboard); on the starboard tack the
  `Set` is mirrored about the plane through its stay (the gaff's for the spanker). They show `Clewed` while coming down
  and `Furled` when down.
- The boom and gaff turn with the physics' boom angle (+ to starboard in the physics, + to port in the model).

## In the game

`ShipModelVisuals.cpp`: when the boat is built, a ship with a rig (`ShipRigFor` her config name) binds her parts: a mesh
already on the boat named `SM_Frigate_<object>` (or its `_Light` twin) is used where it is, the rest are loaded from
`/Game/Boats/Frigate/Outside/` when they are in the project. Each frame after the physics, each part is put at its rest
transform moved by its spar's motion (a sail after its mirror), and only the sail's shown state is visible. A part is
moved only when its transform changes, so still spars keep their cached shadows.

Her crew: the pawn makes no small-boat crew figures for a square-rigged ship (`FBoatConfig::HasSquareRig`): placed along
a cockpit, her company of 450 would be 450 figures in a line 250 m long. Her deck watch stands at its stations instead
(to come).

## Known gaps

- A square sail's `Set` turns rigidly with its own yard; braced, its clews part from the yard below by up to 0.7 m at
  30 deg (sails.json's note). Drawing the foot to the yard below needs the cloth (`FSailCloth`) or a vertex offset.
- The cloth set sharper than its yard (`FSquareSailDef::SetsPastYardDeg`, a few degrees at full brace) isn't shown.
- A sail held aback (heaving to) shows as drawing; the model has no backed state.
- Reefs aren't shown.

## Tests

`SailingSim.ShipRig.Table`, `.Motion`, `.Pose` (`Source/SailingSimTests/Private/ShipRigTests.cpp`).
