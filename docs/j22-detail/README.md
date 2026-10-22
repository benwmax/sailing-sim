# J/22 hero, assembly by assembly (boat fidelity: pc/j22-detail)

Bean's review of the J/22 rebuild was that little had changed: the rudder and tiller didn't look like the photos, the
outboard was blocks, and the mast gear was unchanged. That was right. Each pass had added small parts to the old
primitive assemblies. This branch rebuilds the hero one assembly at a time from the 62 photos, at Nanite hero detail:
separate mechanical parts, real curvature, fasteners.

The side-by-sides with Bean's photos are in `compare/`. They are kept local and never committed, because the photos are
private and partly watermarked. The renders here are the game at Ultra.

## 1. Rudder and tiller (`Inputs/j22-hero/j22_steering.py`)

From the photos `tiller`, `tiller-2`, `tiller-transom-attachemnt`, `tiller-transom-attachemnt-2`, `transom-worn` and
`aft-transom`.

| Part | Before | Now |
| --- | --- | --- |
| Rudder head | two guessed cast-aluminium cheeks | the blade's own head rising above the deck, its aft top corner on a large radius, 44 mm thick where the straps hug it, clean moulded gelcoat |
| Tiller to head | a pin through the cheeks | two stainless side straps on one through-bolt (hex head, washer, nylock), running into the tiller under three carriage bolts |
| Tiller | a round tube | laminated ash and mahogany, deeper than wide (74 x 46 mm at the root, 44 x 36 at the grip), an open channel along the top by the head, a pronounced S, a rounded grip, its cam cleat |
| Extension | a cylinder | a ribbed rubber universal joint on a screwed plate, the tube with a foam grip and an end cap, folded aft |
| Pintles | boxes | a polished strap down both faces of the blade following its section, round-ended, four staggered through-bolts, a square block round the barrel |
| Gudgeons | boxes | two lugs each: a barrel round the pin, the strap's legs folded flat onto the transom, two hex bolts a side, the pin's head above and a keeper below |

The rudder's sockets (`RudderPivot`, `RudderStock`, `TillerEnd`, `TillerExtTip`, `TillerExtUJ`) are unchanged. The
parts are built to meet them, and `anchor_<Name>` empties carry them to the bake. The pintles' axis is now exactly the
rudder's pivot; the old blade's leading edge sat ahead of it. All 52 sockets are unchanged. Slots: the rudder has 4
(the baked blade plus three hero packs), within 8. Of the baked maps, only the Rudder group's are new; the blade's UVs
changed.

Renders: `steering-tiller2.jpg`, `steering-pintle.jpg`, `steering-tiller.jpg`, `steering-quarter.jpg`.
