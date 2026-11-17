# Track H: yard and shore clutter (cloud half)

Shore plan of Nov 16 2026, Track H: about thirty small props that lakefront lots, docks and the club's boat yard are
dressed with, sparse and placed by seed (Bean's choice on Oct 16 2026). **Nothing here is loaded by the game yet**;
Track I places them before the Nov 27 feature freeze (`docs/slice/README.md`).

## What is built (`Tools/envloop/yard/build_yard_props.py`, cards in `Tools/envloop/yard/cards.json`)

32 meshes, all under 5,000 triangles but the fire pit (5k):

| Group | Props |
| --- | --- |
| Patio and dock | patio table set (48 in, four sling chairs), Adirondack pair with side table, chaise lounge, market umbrella open and furled, picnic table, garden bench, cooler, fire pit with benches, hammock |
| Cooking | kettle grill (22 in), three-burner gas grill with tank |
| On the water | sit-on-top kayak (10 ft), paddleboard (10 ft 6 in) with paddle, canoe (16 ft) turned over on sawhorses |
| Driveway | generic SUV (no badges), golf cart, boat trailer (19-21 ft, empty), double PWC trailer |
| Family | swing set with fort and slide, 14 ft trampoline with net, portable basketball hoop |
| Garden | planter with boxwood, raised bed, bird bath, hose reel, wheelbarrow, push mower |
| Edges | 20 ft flagpole (a plain flag until Bean picks), pool safety fence panel, wheeled refuse cart, rural mailbox (USPS height) |

Origin on the ground at the footprint's centre, +X the front. Colours that vary from yard to yard are per-instance
(`Plastic`, `Canvas`, `Paint`); nothing carries a logo, badge, plate or brand shape.

## Placement (proposal for Track I)

- 0 to 4 props a lot by seed from the houses bake, weighted by what the lot has: lawn to the water (chairs, fire pit,
  kayaks, swing set), a dock (umbrella and chairs on the deck, kayaks on the rack), a drive (SUV, trailer, golf cart,
  bins on collection day only if Bean wants it).
- The docks' sockets (`kayak_N`, `umbrella_0`, `chairs_0`) take the kayak, umbrella and Adirondack pair.
- Near band only (to 150 m): too small for the mid-distance house tiles. Medium gets the dock props only.

## Results (Nov 16 2026)

Checks: every prop within 5% of its card's real size, under budget, slots known or listed as new: 0 failures. Renders at
3, 15 and 60 m in three lights are in the project files (`envloop-docks-yard/`). Weakest by eye: the SUV's glasshouse
(a box), the gas grill's lid, the swing set's slide; next round. No blind round yet for props: there is no "before" (the
game has none), so the first blind question is "photo or game" once Track A's lawn exists.
