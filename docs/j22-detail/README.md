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

## 3. Gooseneck, boom end, vang and outhaul (`Inputs/j22-hero/j22_boomgear.py`)

From the photos `mast-boom-gooseneck-connector`, `boom-end`, `boom-vang-closeup` and `outhaul-sheet-cleet`.

| Part | Before | Now |
| --- | --- | --- |
| Gooseneck | a block on a pin | a stainless mast plate with rounded corners and eight countersunk screws, two welded tangs, the vertical pin with hex head and nylock, a black knuckle, the boom's cast end sleeve with fork cheeks, the horizontal quick-release pin with its ring, the reef and cunningham hooks |
| Boom end | a box | the angled cast end cap, the outhaul sheave on its axle, cap screws, the topping-lift lug with a shackle and pin |
| Vang | a small block | the photo's large upper block: perforated cheeks, three sheaves, a swivel on the boom bail |
| Outhaul | none | the grey cam cleat under the boom aft of the vang bail, with its throat and screws |

The sockets the bake reads (`Gooseneck_vpin`, `Vang_bail`, `BoomEnd_outhaul`, and the rest) keep their names and
centres; all 52 sockets are unchanged. Slots: the boom has 2, the mast 3, the hull 6.

Spar colour: the photos show white painted spars with black tape. That is the next change, as a livery parameter.

Renders: `boom-goose.jpg`, `boom-vang.jpg`, `boom-boomend.jpg`.

Correction to 3: the vang's upper block was first named `Vang_upper`, and the bake treats `Vang_` objects as live rope,
so it never reached the game. It is now `VangBlock`, on the boom (`BOOM_PARTS`), and swings with it. Render:
`boom-vang.jpg`.

## Spars: white with black tape, or anodised (`Inputs/g3/boat-catalogue.json`)

Bean chose a mix. The catalogue's J/22 `spars.finishes` are painted white (weight 0.5) and clear anodised (0.5), and
`Tools/fleet/make_liveries.py` turns them into `FLiverySpar` rows. Seed 0, the player's boat, takes the first: white.
AI boats draw their own finish. Marina J/22s draw theirs from their slip seed, and each spar part is drawn by two
components, anodised and painted. `PaintSpars` (`BoatLivery.h`) sets the library's painted-aluminium values (roughness
0.35, clear coat 0.6, surface 5) on the mast's and boom's aluminium, whether it is their own slot or a pack's
`Aluminium` entry. Nothing is geometry: change the catalogue to change the mix. The black tape bands are geometry on the
hero (assembly 4).

## 4. Mast step, turning blocks, exits, cunningham, spreaders, chainplates (`Inputs/j22-hero/j22_mastgear.py`)

From the photos `mast-bottom-closeup`, `mast-sheetsandhardware`, `mast-cunningham`, `mast-and-spreader`,
`shroud-mounts` and `mast-boom-gooseneck-connector`.

| Part | Before | Now |
| --- | --- | --- |
| Mast step | an aluminium box and a collar | a rounded stainless base plate with countersunk screws; the dark grey heel casting rising round the mast's foot; two white halyard sheaves in a pocket in its aft face on one axle; a hex bolt and nylock across; ring pins through its fore and aft ears |
| Turning blocks | six small blocks | six blocks with perforated cheeks on swivels and shackles, standing on padeyes |
| Halyard exits | flat plates | stainless exit boxes: rounded plate, the sheave in a dark slot, four screws |
| Cunningham | none | a plate low on the mast's port side with a fairlead block and a cam cleat; a block hung under the gooseneck on a strop; the blue line |
| Tape | none | a black band round the mast at the gooseneck, centred on the game's resting mast bend (`M_BoatMast` bends the mast but not its fittings) |
| Spreaders | a box root and dark tape | a cast saddle with four rivets and a bolted socket at the root; a white boot over the tip, and white tape round the shroud |
| Chainplates and shrouds | open-body turnbuckles | rounded cover plates with four countersunk screws; closed-body turnbuckles on toggles with lock nuts and scale rings; ribbed grey boots over the upper studs; white tape at the toggles |

The cunningham's line is a flat entry (`CunnLine`) in the plastic pack, so the mast stays at 3 slots. All 52 sockets
are unchanged. Slots: hull 6, mast 3, boom 2. Not modelled: the shroud's quick-tension lever in `shroud-mounts`.

Renders: `mast-cunn.jpg`, `mast-shroud.jpg`, `mast-goose.jpg`.

## 5. Deck hardware at real detail (`Tools/boatkit/bk_parts.py`, `j22_details.py`, `build_j22_hero.py`)

The fleet's kit (`/Game/Boats/Kit`, reimported: `Block29`, `Block40`, `FiddleCam`, `Ratchet57`, `CamCleat`, `Winch16`):

- **Blocks:** six lightening holes cut through the outer cheeks, so the sheave shows through (the badge's cheek keeps
  its lower holes clear); raised hubs; bearing races on the sheaves.
- **Cam cleats:** cams with raked sawtooth teeth on an eccentric lobe toward the line.
- **Winch:** five cap screws on the top and a stainless edge ring.

The kit's sockets are unchanged.

The hero:

- **Blocks:** perforated cheeks showing the grey sheave, raised hubs and rivets, a moulded head bridging the cheeks,
  bearing races. `{name}_sheave` keeps its centre.
- **Cam cleats:** black base, raked eccentric cams on stainless axles at the old cams' centres (the `JibCam` and
  `MainsheetCam` sockets read them), a red fairlead hoop, three screws.
- **Horn cleats:** one swept horn of elliptic section, tapering to its tips, over a cast base. It is set so `BowCleat`
  (the horn's top) stays put.
- **Winches:** the kit's.

Renders: `kit-parts.jpg` (Blender), `kit-bowcleat.jpg`, `kit-cams.jpg`, `kit-winch.jpg`, `kit-mainblk.jpg`.
