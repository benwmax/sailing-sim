# Rig clearance: sheets, rig lines and sails (Bean's job 3, the clipping half)

`SailingSim.Visual.RigClearance` spawns each of the nine boats and checks the lines that boat actually draws. The autopilot
holds each point of sail and the trim assist trims:

- close-hauled on both tacks, in 7 kn and in 16 kn;
- reaching on both tacks, in 12 kn;
- running on both gybes, in 12 kn.

`ASailboatPawn::HoldForTests` sets this up: a steady breeze in a bare world, and the rig lines recorded as
`UpdateModelRig` builds them.

Each line is sampled along the centreline it is drawn with, after its sag and drape. It is checked against:

- the solid boat (`CrewInsideBoat`: hull, deck, cabin trunk, cockpit, coachroof);
- the lifelines;
- the crew's flesh (bone segments with CrewHullClearance's radii);
- the sails' cloth (segment against triangle).

The shrouds, the spreaders and the trapeze wire are also checked against the sails. The test lists everything it finds.
It fails on these:

- a shroud led across the boat;
- a rope more than 10 cm into the solid boat, away from its fittings;
- a wire through the jib's cloth, away from its luff and head, in 3 or more of the 32 samples per boat.

About 109,000 line points are checked, in 17 s.

## What was wrong, and the fixes

| Before | Fix |
| --- | --- |
| The Corsair 880's upper shrouds ran from each float to the *other* side's spreader tip, crossing in front of the main. `build_fleet.py` took `HS[1]` as the starboard float, but it is the port one. | The chainplates are picked by the side the float is on. The Corsair model was rebuilt and reimported. |
| Every keelboat's jib sheets, the lazy sheet in particular, ran straight through the cabin trunk or coachroof. The J/22's went 18 cm in. | Ropes drape over the boat: each ring of the tube is lifted onto the solid's surface, taking the most lift needed anywhere within half a span of it (`FRigLine::Lift`, `BoatModelVisuals.cpp`). The vertex count is unchanged. The mainsheet drapes over a coaming when it is eased far. The vang is never draped. |
| The sails passed through the shrouds and spreaders: the main when running, a genoa close-hauled. | `FSailCloth::KeepClear` (`SailCloth.cpp`) keeps the cloth off the wires (the main's turn is capped; see Known gaps). The wires are the shrouds along their sag (a leeward shroud goes slack), the spreaders and the trapeze wire, handed over by the pawn each frame. Each row of a jib turns about its luff, smoothed over its neighbours, until an overlapping genoa passes outside the shrouds and forward of the spreader tips. The main turns as one, eased over 0.3 s and capped at 11°, like a boom stopped at the shroud. The boom is drawn turned with it (`GetFootTurn`). The rotation is applied to the target shape; the cloth follows it. |
| The Sunfish's mainsheet tail ran from the bridle along the deck under the sailor's hips. | It now runs from the boom's end block forward along the boom to a block over the cockpit, then down to the hand, as on the boat. |

The stills are before (left) and after (right), High, on the lake:

- `j22-run`: the main eased onto the shrouds, intact.
- `cat30-run`: the same on the Catalina 30.
- `c22-beat`: the genoa outside the shrouds.
- `corsair-rig`: the shrouds on their own sides.
- `j22-lazy`: the lazy sheet over the cabin top.
- `lagoon-winch`: no change (see Known gaps).
- `sunfish-sheet`: the Sunfish mainsheet.

The before stills are main 2d46177e plus #206, which doesn't touch these views.

A first try at the main turned each row as far as that row needed, up to 34°. It tore a running main into steps. Turning
the main as one piece, with a small cap, looks right.

## Known gaps (listed by the test, not failed)

- **A running main pressing on its shrouds near the mast.** Where the belly of an eased main bellies forward around a lower or
  upper shroud close to the mast, the wire still shows through the cloth. That happens in about 8 of the 32 samples on
  most keelboats, only when running. Turning the main further looks worse than the contact. A real fix needs the cloth to
  wrap the wire, or a finer grid.
- **The Lagoon 42's jib.** The physics jib is an overlapping sail. Its clew is aft, by the mast, and lower than the saloon
  roof. The model leads its sheet to a self-tacking track 4.5 m forward (`build_fleet.py`). Whatever the route, the sheet
  crosses the roof or the jib's foot. Lifted over the roof, it hung in the air, so her jib sheets are left as they were.
  The sail geometry (Fleet.cpp, its polar) and the lead need to agree first.
- **The mainsheet across the helm when running.** On the Catalina 30, the Corsair 880 and the maxi, the traveler is
  where the helm sits, at the aft end of the cockpit. A sheet eased square sweeps the helm's back (2 to 5 cm).
  That's crew placement against an end-boom traveler, not routing.
- **Small cases, a few centimetres:**
  - lines lying on a deck or trampoline under a resting calf (the Hobie's jib sheets);
  - the dinghies' tiller extension alongside the hip in light air;
  - the ILCA's sheet over its cockpit edge when eased;
  - the Catalina 22's mainsheet touching the pushpit at 21° of heel.
