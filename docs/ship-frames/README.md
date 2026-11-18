# A ship's moving parts

The frigate *Commonwealth*'s tiller swings under the great cabin's beams with her rudder, its ropes run with it to the
wheel on the quarterdeck, which turns two and a half times from amidships to hard over; the cabin doors swing open for a
walker and shut behind him; the capstans' heads stand (no order turns them yet). The model's parts come from the build
(`docs/shipkit-12`, the tiller PR #799): each one exported alone at its own pivot. The yards and sails are
`docs/ship-rig/`; this page is the rest of what moves on her.

## The table

`Tools/shipkit/frigate/frames_table.py <build dir> Source/SailingPhysics/Private/CommonwealthFramesData.inl` turns the
build's `gundeck.json` (`frames`, `tiller`, `tiller_ropes`, `cabin_doors`) and `deck.json` (`frames`: the wheel, the
capstan head) into the table the game reads (`ShipFrames.h`, `CommonwealthFrames()`). Edit the build or the script, never
the `.inl`. For each part (`FShipFrame`): its name (the export's object name), its kind, its pivot and axes in the ship
frame (metres, X forward, Y starboard, Z up, the helm amidships and the doors shut), a door's swing sign, a rope part's
column in the pose rows, and whether it is exported with the decks below (`Decks/`) or the outside model (`Outside/`).

| Part | Kind | Moves |
| --- | --- | --- |
| `Tiller` (rudder head and iron tiller, one mesh) | Tiller | turns about its own Z, the rudder's axis, by the helm's degree |
| `TillerEye_S/P`, `TillerRun_S/P`, `TillerWrap_S/P` | Rope | posed from the table's rows by the helm's degree; a run stretches along its own X |
| `CabinDoor_P`, `CabinDoor_S` | Door | swings aft into the cabin about its own Z, by its sign, up to 90 deg |
| `Wheel` | Wheel | turns about its axle (its X), 2.5 turns at hard over |
| `GunCapstan`, `Capstan` | Capstan | stands |

The rope rows (`FRopePoseRow`, one per whole degree of helm from -35 to 35) are the build's poses: for each of the six
parts its origin, its axes as the columns of `R` and the run's stretch `ScaleX`. The row at 0 is the parts as built,
so a part rests in it (the tests hold the residual under a millimetre).

## Signs

The physics' rudder angle is positive with the bow to starboard. The tiller, forward of the rudder head, then goes to
port, so the helm's degree (`TillerHelmDeg`) is the rudder's angle negated and held inside hard over (35 deg): positive
helm is the tiller to starboard and her head to port, and the wheel's top goes to port with it (`WheelTurns`, the
helm's sign). The starboard rope run pays out as the tiller goes to port (its stretch 1.8 at hard over) and shortens to
0.19 as it comes to starboard; the port run mirrors it.

## The pose

`FShipFramesPose::Update` takes the physics' rudder angle and, while someone walks her decks, the walker's feet (ship
frame). A door opens for feet within 1.6 m of its hinge in plan on its own deck (not the quarterdeck 1.8 m over it:
`ShipDoorNear`), swinging open in a second (eased into its stop), and swings shut two seconds after he has gone.
`Motion(Frame)` gives each part's motion from its rest (`FRigMotion`, as the rig's): the tiller's turn, the rope row
blended between the two nearest whole degrees, the door's eased swing, the wheel's turns, identity for a capstan.

## On the model

`ShipModelVisuals.cpp` (`BindShipFrames`, `UpdateShipFrames`) finds each part on the boat by its object name, or loads
`/Game/Boats/Frigate/<Decks|Outside>/SM_Frigate_<Name>` (the table's folder first, then the other) and attaches it under
`BoatRoot`. A part exported at its own pivot rests at its frame's origin and axes (`FrameRest`), so a rope run's stretch
along its own X is an exact scale of the component; one exported in the ship frame instead rests at the identity (logged).
Each part gets `Posed(Rest, Motion)` only when its transform changes, as the rig's parts do. The gun deck's parts (the
tiller, its ropes, the doors, the capstan head) show only while the gun deck's mesh is loaded (`docs/ship-walk/`): outside
her nothing sees them, and without the deck they would float in her hull.

The walk map (`Content/TerrainData/Ships/Commonwealth.walk`) has no overhead for the tiller yet: it hangs 1.47 m over the
cabin deck at the rudder head and 1.67 m at its end, sweeping 35 deg each way (its end 2.6 m out hard over), so the walker
should duck or stay forward of it. That is the walk map's rebake (`walk.py`, the Tools PR), not this page.

## Tests

`SailingSim.ShipFrames.Table`, `.Helm`, `.Ropes`, `.Doors`, `.Pose` (`Source/SailingSimTests/Private/ShipFramesTests.cpp`).
