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

## 2. Outboard and its bracket (`Inputs/j22-hero/j22_outboard.py`)

Before, this was seven boxes. Bean's photos `transom-worn` and `aft-transom` show the bracket on the port quarter but no
motor, so the motor is a generic 5 hp long-shaft four-stroke, the class's usual kicker (sizes GUESS). It carries a
made-up maker, TERNWAY, the boat kit's brand. No real maker's shapes or marks are used.

- **Transom bracket:** a stainless plate with four bolts, two pairs of parallel arms on pins, the lift spring, the lock
  pin and its ring, and the HDPE pad.
- **Motor:**
  - Clamp bracket: hooked over the pad, two clamp screws with T-bars and swivel feet.
  - Tilt tube and nuts, and the swivel housing.
  - Cowl: a superellipse lower pan, the parting-line gasket, and the domed upper cowl. It carries the latch, the recoil
    starter's handle, the integral tank's cap and vent, and the name and a stripe on both sides.
  - Lower unit: a streamlined midsection; the anti-cavitation plate with its anode; the strut and the gearcase torpedo
    with its water intakes; the skeg; and a pitched three-blade prop with hub and nut.
  - Tiller arm: a ribbed twist grip, the stop button and the shift lever.

The outboard is part of the hull (`SM_J22H_Hull`), and every part is a pack entry, so the hull stays at 6 slots.
Sockets are unchanged.

Renders: `outboard-ob-quarter.jpg`, `outboard-ob-top.jpg`.
