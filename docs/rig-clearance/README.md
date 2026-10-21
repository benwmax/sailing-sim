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
- **Small cases, a few centimetres:**
  - lines lying on a deck or trampoline under a resting calf (the Hobie's jib sheets);
  - the dinghies' tiller extension alongside the hip in light air;
  - the ILCA's sheet over its cockpit edge when eased;
  - the Catalina 22's mainsheet touching the pushpit at 21° of heel.

## Follow-up: the mainsheet across the helm

Running with the main eased square, the mainsheet swept a sailor's back on three boats.

- **Catalina 30:** her traveler was across the cockpit at the wheel. Most C30 hulls carry it on the cabin top, just
  forward of the companionway. `build_fleet.py` now puts it there, 1.0 m forward of the cabin's aft end, clear of the
  slide-hatch rails and forward of the dodger, and the boom is sheeted above it, mid-boom. The model is rebuilt and
  reimported.
- **Corsair 880:** her traveler really is at the aft end of the cockpit, behind the helm.
- **The maxi:** her traveler is in her cockpit, and her trimmers sit on the rail beside it.
- **The rule:** for every keelboat and multihull (not the dinghies), the crew sit on the windward side when the boom is
  out past 55°, away from the boom, as crews do (`CrewPlacement`). The J/22's light-air trimmer still takes the leeward
  seat by the working winch.

`SailingSim.Visual.RigClearance` now fails when the mainsheet's tackle passes through a sailor. Main fails it on the
Catalina 30, the Corsair 880 and the maxi.

The stills are before and after, High, 12 kn at 160°, from forward:

- `cat30-run-aft`: the C30's crew now to windward of her cockpit;
- `corsair-run-aft`: the Corsair's crew on the windward net;
- `maxi-run-aft`: the maxi's rail crew to windward.

Seen in passing: on the Corsair's windward net, one crew member's legs rise steeply onto the main hull's deck when
running. That pose was the same on the leeward net before, hidden behind the sail; it's left for a crew job.

## Follow-up: the Lagoon 42's self-tacking jib (Bean's pick)

Her physics jib had been placed as an overlapping sail. The comment always said it was her self-tacker, and the polar's
source is the stock boat, which has one. But the tack was at x 2.4 m, so the clew was aft by the mast and under the
saloon roof, while the model led the sheet to a track on the foredeck.

- **The sail** (`Fleet.cpp`): tack on the model's forestay, foot 3.15 m up (10 cm over the roof's crown), a 4.2 m foot
  with the clew at x 0.45, 0.7 m forward of the mast. Area 35 m², as published.
- **Aspect ratio:** induced aspect ratio 3.3, down from 3.8, because the foot is 1.6 m clear of the trampoline at the tack
  and no longer end-plated by the deck. Her polar is within 0.3% of the old one at every point, and her tack and irons
  scenarios are unchanged. `FleetReferencePolar` is unchanged. The J/22's PolarGate is unchanged.
- **The model** (`build_fleet.py`): the self-tacking track is an aluminium rail with end stops across the saloon roof's
  forward end, under the clew; the leads are on it.
- **The sheet:** one sheet, from the clew to its car and aft along the roof to the leeward winch. The second set of lines
  lies on it, and it drapes over the roof like the others.

`RigClearance` no longer lists her.

The stills are main and after, High, 12 kn at 45°:

- `lagoon-self-tacker`
- `lagoon-track`
