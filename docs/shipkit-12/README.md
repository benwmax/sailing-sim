# Shipkit 12: the gun deck

Slice 12 of the frigate *Commonwealth* (plan: <https://claude.ai/artifact/8y6hW8vHjjUPJRovJEuxY7>; slices 0-11 are in
`docs/shipkit-1` to `docs/shipkit-11`). Slice 11 gave her boats. This slice takes her below for the first time: the
gun deck, the deck under the spar deck where her long guns stand. It builds the planked deck under the guns and the
spar deck's framing over it; the hatchways with their coamings, gratings, wells and ladders; the gun deck's capstan,
the pumps, the riding bitts and the galley stove; the manger at the bow, with the bowers' cables led in through the
hawse holes and down the cable scuttles; the captain's great cabin aft, under the stern windows; the lanterns, each a
light in the game data; and the guns' own gear that slice 8 left for here: tompions and lead aprons, sponges,
rammers, ladles, worms and handspikes hung overhead, shot in garlands along the sides, and the lanyards that hold
each port lid open. It also stows the sheet anchor outside, on the starboard fore channel, as Bean chose. It is still
post-slice art: nothing here is imported into Unreal or wired into the game.

Every render on this page is flipped left to right, so it shows her as the game will (docs/shipkit-9 says why).

TODO hero render: the gate view, along the gun deck with daylight through the ports.

## What slice 12 builds

### Twenty-eight guns, not thirty

The plan says thirty guns on this deck. She has fifteen ports a side, but the foremost each side is the bridle port at
the bow, a chase port the foremost guns were shifted into and too far forward to house a gun in. Bean chose
twenty-eight long 24-pounders, fourteen a side, with the bridle ports empty and their lids shut (`guns_1797.json`).
Slice 8 built the guns, their carriages and tackles in three poses (housed for sea, run in, run out); this slice
builds the deck under them and their gear about it.

### The deck, from the 1849 plan

Her drawings of 1849, the Navy Yard Boston gun deck plan (NARA 75841364) and spar deck plan (NARA 75841368), place the
deck's fittings: the hatchways with their inside sizes written on them, the pumps either side of the main mast, the
capstan between the after hatchways, the riding bitts and the galley between the fore hatchway and the fore mast, the
scuttle forward of them, the manger, and the bulkhead and cabins aft. The plan is carried to her the way slice 7
carried the spar deck's: by the masts where they pass this deck, each item keeping its share of the way from one mast
to the next (and its distance at the plan's scale aft of the mizzen and forward of the fore mast). The scans are
public domain, measured only, and not in the repository.

* **The deck** is flat across, its top 24 in under the port sills (`specs_1795.json`), and planked in 7 in planks
  4 in thick, their butts staggered over the beams and their bolts plugged (`GunDeck`, drawn by the material from the
  deck's `Planking` and `Margin` UVs, as the spar deck's). Slice 8's known gap is closed: the traced sills left a kink
  where the deck climbed 4 in in 5 m by port 10, and the line under them is now faired between 7 and 12 m
  (`specs_1795.json` `gun_deck_fair_m`).
* **The waterways** along each side, a hollow cove where the deck meets the side, run from the after wall forward
  until the bow narrows, stopping 2 in short of the hawse holes' linings where the bores come in at the deck.
* **The hatchways**: the spirit room hatch, after hatch, main hatch, fore hatch and the hatch forward of it, the
  scuttle and the wardroom's skylight, each at its plan size with a coaming 10 in high and 5 in thick (4 in round the
  skylight, narrowed to clear the second guns' train tackle bolts). The after and fore hatches are ladderways, the rest
  gratings. Under each opening a **well** goes down to where the berth deck will be (slice 13), 7 ft 2 in under this
  deck's top, lined dark, with a ladder down each ladderway. That is the 1926 midship section's spacing, and it puts
  the berth deck 17 ft over the rabbet amidships, where the 1795 section drawn from Humphreys' specifications has it.
* **The ladders**: one down each ladderway, and the companion's from the quarterdeck down to this deck forward of the
  cabin. The spar deck's four ladders at the breaks land on this deck in the waist, and nothing stands within a foot
  of their feet.

TODO render: the deck from aft, guns run out.

### The spar deck's framing overhead

What a man on the gun deck sees over him is the spar deck's framing. Its planks are 3 in thick on beams 14 in sided
and 10 in moulded at every other beam station, with a ledge (6 by 5 in) between each two. Where a beam would cross an
opening above (a hatchway, the companion, a skylight, the chimney, a mast's partners, the capstan) it is cut, and half
beams run from the side to a carling either side of the opening, with head ledges across its ends. In the waist the
gangways' beams run out to a carling under the opening's coaming, and a breast beam stands under each break. The
beams' ends rest on **a clamp** along each side (10 by 5 in), which steps up over each port so its lower edge stands
7.5 in over the port's head, clear of the bolts the housed gun's muzzle is lashed to. **Hanging knees** (7 in sided,
30 in arms) hold each beam end that comes between two ports; one that would foul a lid lanyard's cleat slides along
under its beam. **Stanchions** (6 in, turned) stand on the middle line under the whole beams where the deck is clear
of fittings. The beams' and ledges' lower edges are chamfered (an inch on the beams), the chamfers stopped short of
the side where the knees and the clamp take the ends; the carlings' are chamfered their whole length. **Lodging
knees** lie flat in the angle between a beam's face and the side under the planks, one at each end of each beam
forward of the cabin, on the face toward the ship's middle where that bay is clear of the ports (the bays over the
ports hold the implements and the lids' lanyards): an arm 30 in along the beam's face and one along the side, stopping
short of the next ledge, the throat rounded (TODO count from the final build).

### Fittings

* **The capstan**: the double capstan's lower head under the spar deck's, on the same axis: its barrel up through the
  gap between the decks to the spar capstan's, eight whelps, a 56 in drumhead with twelve bar holes, and pawls on the
  deck. It is its own object, on a frame on its axis, so the game can turn it. **Its twelve bars** (12 ft, square at
  the inner end for the hole, then round and tapering to the hand) are stowed overhead athwartships, three to a bay
  in the bays nearest it that are clear of the ports and lanterns, each set in two iron stirrups from the planks.
* **The pumps**: the chain pumps aft of the main mast (two chains in one case over the well, a crank across the ship
  with a winch handle at each end) and a pair of common pumps forward of it, their brakes pointing forward.
* **The riding bitts** abaft the fore mast: two posts through the deck, their edges chamfered and their heads rounded
  over, a cross piece on their fore faces with its fore edges chamfered and its ends rounded down, a standard (a knee)
  behind each, and round-headed iron bolts through the cross piece into the posts and down through the standards.
* **The galley**: an iron stove of the period's patent kind (Brodie's) on a brick hearth under the forecastle, with an
  iron kerb round the hearth: cast plates bolted at angle irons up the corners, a band round it at half height and a
  rib up each side, every joint on round bolt heads; a fiddle bar round the top to keep the pots on, and the boilers'
  lids in it; on its fore face the fire's open mouth with its grate, the ash pit's door under it and the oven's door
  on two strap hinges with a latch. A rail runs round it, and its flue goes up into the forecastle's chimney with a
  band and the damper's handle.
* **The masts' wedges**: a ring of wedges round each mast where it passes the deck, 3 in proud. The masts' iron hoops
  stop clear of both decks' partners (`spars_1795.json`).

TODO renders: capstan, galley.

### The bow

The bowers' cables (slice 10) now come in through the hawse holes, whose bores run through to the side's inner face,
lined with lead all the way and lapped over the inner mouth as over the outer. Each cable lies on the lining at the
inner mouth, runs over **the manger** (a low board across the bow abaft the holes, 10 in high, that keeps the water
coming in with the cables from running aft, a scupper through it), and turns down **a cable scuttle** (20 in, a lead
collar round it) into a short well toward the cable tiers (slice 14). The course is the shortest that clears the
manger, the deck, the collar and the scuttle's lining, each turn no tighter than one and a half times the cable's
thickness. The holes with no cable in them are stopped with **hawse plugs**, oak plugs driven in from inboard.

TODO render: bow.

### The great cabin

The captain's cabin under the quarterdeck, from the 1849 plan's bulkhead and state rooms (the 1797 cabin was the
captain's, on this deck):

* **The bulkhead** across the ship abaft the first guns, panelled both faces, with a door either side of the tiller
  ropes' legs (each door its own object, hinged on its outboard post, opening aft into the cabin).
* **The after wall**: the stern's inside, raked with her stern, with the stern windows opened through it and each
  window's reveal lined with board. The transom's rows are cut round the windows, so daylight comes in through them.
  Between the state rooms it is panelled on its rake: a sill rail along the seat under the windows, a pilaster on a
  base under a capital between each two windows, a stile at each end, a head moulding and a raised and fielded panel
  over each window, and a cornice under the planks.
* **A state room in each quarter**, its wall stepped round the beams over it and its door opening into the stern cabin.
* **The window seat** across the stern under the windows between the state rooms, the rudder's head boxed inside it:
  a hinge rail let into the after wall, four lids on brass hinges (the piece over the rudder's head is fixed), each
  with its nosing rounded over, and the front framed with raised and fielded panels.
* **The floor cloth**: painted canvas over the cabin's deck in black and white squares a foot across.
* **The furniture**, mahogany: a table 72 by 40 in, six chairs and a sideboard against the bulkhead.
* **The lead bushes** where the tiller ropes' legs pass down through the deck.

TODO renders: cabin_aft, cabin_fwd.

### Lanterns and light

A horn lantern hangs between each second pair of guns a side (seven a side): between the spar deck's beams on a hook
in the planks' underside, in the bay nearest the middle between the two ports that stands clear of both (the bays
over the ports hold the guns' implements), 1.15 m in from the side, over the room between the two guns and outboard
of the walk inboard of them, its dish 1.37 to 1.42 m over the deck. One more hangs over the middle of the cabin's
table from an oak bar across between the skylight's carlings. Each has a screw eye and hook, a ring on its cone roof,
a six-sided body of tin posts and horn panes, and its dish.

Each is a light in the game data (`gundeck.json` `lights`), warm (2200 K) and in a zone:

* **The deck's fourteen** (`gun_deck`) are unshadowed and reach 6 m, the aftmost pair only as far as the cabin's
  bulkhead (3.1 m).
* **The cabin's** (`great_cabin`) casts shadows and reaches 4 m.
* In the game a light should light only its own zone's objects (lighting channels; `gundeck.json` `below` gives each
  object's zones), so neither side shines through the bulkhead.
* **180 lumens** is chosen for the game's exposure below decks, not a candle's: a tallow candle gives about 12 lumens
  and horn passes less, so a period lantern lit only a few feet round it.
* **Fifteen lights** in all against the slice's budget of sixteen. The daylight comes in through the open ports, the
  hatchways and the stern windows. No light probes are set below in this slice: that is the PC lighting lane's, if the
  frame allows.

### The guns' gear

* **Housed for sea**, each gun has a wooden tompion in its muzzle and a lead apron over its vent and lock, beaten down
  over them (`Guns_Housed` only: they come out and off when the guns are cast loose).
* **The implements**: over each gun, in the bay between the spar deck's beams over its port, its two staffs (the
  sponge and rammer on one, the worm and ladle on the other, as sea service carried them) and its two handspikes, each
  on two iron hangers with a hook, under the beams so they pass below the carlings. In the waist, where there are no
  beams over a gun, its set hangs fore and aft under the gangway beside it.
* **The shot garlands**: an oak rail on the deck along the waterway forward of each port, cupped for eight 24 lb shot.
* **The lids' lanyards**: two to a lid, from a ring at the end of each hinge strap up the side to a lead-lined hole
  over the port, in through the side and the clamp, and down to a cleat beside it. Outside they lie down the shut lid
  with the guns housed, and run taut to the open lid with them run in or out. The bridle ports' lids stay shut.

TODO renders: housed, implements, lanyards_out.

### The sheet anchor

Slice 10 planned the sheet anchor (5,400 lb) for the gun deck, but its stock, 17.85 ft long, needs 2.4 m and the gun
deck has 1.8 m under the beams. Bean chose (16 Nov) to stow it outside, abaft the starboard fore chains, as frigates
did (`anchors.py` `sheet`):

* **Its shank** rises forward at 14 degrees, from its crown low on the side over its own billboard to its ring at the
  fore channel's after end, and its stock stands up the side. The bill of its inner fluke rests on the billboard, a
  plank on the side shaped to it.
* **Its ring** is lashed (three turns) to an eyebolt in the channel's after end, the lashing led from the ring's
  nearest point.
* **Its shank painter** comes from the waist rail's cap, its two legs steep enough (44 and 40 degrees) to take the
  anchor's weight with a safety of 3.8 on the rope.
* **Heeled 15 degrees** to starboard, its lowest point stays 0.15 m over the sea, the card's least; the build stops if
  it would dip.
* **Port 10's lid** opens under its shank; every lid's sweep out to its gun's angle is checked clear of it (TODO
  confirm from the final build).

TODO render: sheet.

## Clearance

TODO from the final build: the room checks (`gundeck_room`), the designed contacts with allowed and deepest, the
folds and the layout check.

## Triangles

TODO from the final build.

## For the game

TODO: `gundeck.json`: frames (the capstan, the cabin doors), layout, lights and their budget, copies (tompions and
aprons), the lids' open angles, what loads when below.

## Sources and estimates

* **NARA 75841364**, the gun deck plan in the Navy Yard Boston set of 1849, public domain: the hatchways and their
  written inside sizes, the pumps, capstan, bitts, galley, scuttle, manger, bulkhead and cabins. Measured only.
* **NARA 75841368**, the spar deck plan of the same set (slice 7): the capstan's head, companion, skylights and
  chimney over this deck.
* **The 1927 lines** (slices 1-2): the gun deck's sheer, the ports and the stern windows.
* **Period practice** for an American or British frigate of the 1790s where neither drawing shows a part, each value
  so marked in `gundeck_1797.json`: the framing's sizes, the pumps, the stove, the cabin's joinery and furniture, the
  lanterns, the guns' implements and the lids' lanyards.

## Checks

```
python Tools/shipkit/frigate/build_frigate.py <out>
```

(Blender's Python, pip `bpy`; about TODO minutes and 7 GB of memory.) The gun deck is built after the anchors and the
spar deck and before the guns' room check, the boats, the sails and the ropes, which all see it. The build fails if:

* a part of the gun deck or a piece of the guns' gear meets anything else in the ship, or another, except where they
  meet by design, or goes deeper than that contact allows, or a fitting stands off the deck as it rises along the
  sheer (`gundeck_room`); a pair of parts is named twice in the meets, or a pattern in them matches nothing;
* a designed contact no longer meets, so a part meant to rest on, be let into or driven into another hangs clear of
  it (`unmet`, for the gun deck's card and the anchors');
* any piece of either deck or of the guns' gear crosses itself (`gundeck.folds`, `deck.folds`);
* two of the gun deck's fittings stand closer than 0.15 m in plan (`gundeck.layout_close`), or something stands within
  a foot of a ladder's foot;
* a lid cannot open, or a gun run out cannot be elevated, or a lid's swing is stopped by an anchor (`guns.room.lids`);
* the cable bends tighter than one and a half times its thickness outside the clinch, or the sheet anchor's stock does
  not bear on the side;
* the lanterns' lights are more than the slice's budget, or a lantern has nothing over it to hang from;
* the clamp is less than 2 in deep over a port, the window seat is too low over the rudder's head, a reveal's lining
  would show past its window's sash, or no course for a cable over the manger and down its scuttle clears them;
* a gun's implements, its garland or its tompion and apron cannot be placed: no bay over its port to hang its set in,
  no room for its garland before the next port, a tompion that does not clear the bore, or a barrel through its apron.

## Review

TODO

## Known gaps

TODO

## Files

TODO
