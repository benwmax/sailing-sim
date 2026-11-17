# Catalina 22 rebuild, slice 8: her textures and wear

Slice 8 of the Catalina 22 rebuild (plan: <https://claude.ai/artifact/3oMiRWywPhitATHvGxs51a>) gives every surface of
the boat a look and the texture loop's five wear levels ([docs/texture-loop](../texture-loop/README.md)), from launched
new to twenty years left on a trailer. Outside: the hull's gelcoat and the lake's clay line, the deck and its non-skid,
the blue bottom paint and the iron swing keel, the oiled teak and the varnished tiller, the pop-top's canvas and the
sail cover, the vinyl rubrail. Below: the moulded liner, the vinyl headliner, the teak and holly sole, the oiled veneer
joinery, the tweed cushions and the curtain, the white plastic, the stainless, the aluminium and the smoked windows. Two
close-up maps of her own (grained vinyl and woven tweed) join the boats' shared library.

The page is `docs/c22-9` because slice 9 (the cabin's second half) was planned before this slice was split off to run
beside it; the numbers in the plan are unchanged. Like the other slices it is tools and docs only: nothing is imported
into Unreal and nothing in the game changes. The cabin thread calls `weathering_c22.dress(level)` from `build_c22.py`
once this is on main; the game's material entries come in a separate small pull request (below). The new files are
under `Tools/` and `Inputs/`, so the pull request needs Bean's `bean-approved` label.

![Contact sheet: each wear view new, six years half kept and twenty years neglected](sheet.jpg)

## Words used here

- **Gelcoat**: the hard, glossy outer skin of a fibreglass boat. In the sun it goes chalky (a white powder that rubs off),
  then yellow, and fine **crazing** (spider cracks) opens at corners and round fittings.
- **Non-skid**: the moulded diamond pattern on the deck where you walk, so feet grip when it is wet.
- **Antifouling** or **bottom paint**: soft paint below the waterline that stops weed and slime growing.
- **Lake mustache**: the brown band of clay and slime a boat on a muddy lake gets at the waterline, thickest at the bow.
- **Headliner**: the vinyl ceiling of the cabin; **liner**: the moulded white fibreglass of the cabin's inside.
- **Sole**: the cabin floor; on the Catalina 22, teak strips with thin pale holly strips between them.
- **Tweed** or **plaid**: the woollen check cloth the period's cushions were covered in.

## The five levels

The loop's levels (`Tools/texloop/levels.json`), as they read on her. She lives on Lake Ray Hubbard, fresh water: no
barnacles or salt, rust and stainless tea staining at a third of the salt-water rate, and the lake's red-brown clay at
the waterline instead.

| Level | Age, care | On the Catalina 22 |
| --- | --- | --- |
| L0 | new | launched new: glossy white gelcoat, crisp beige non-skid, a deep even blue bottom, golden oiled teak, fresh tan canvas, white vinyl, bright cushions and curtains |
| L1 | 0.3 years, 0.9 | her first season on the lake: the gelcoat's gloss a touch softer, a faint tan clay line at the waterline, dust in the non-skid, the teak paling, the cushions just used |
| L2 | 6 years, 0.5 | six years a club or family boat, half kept: chalky topsides with black streaks under the fittings and windows, a brown clay mustache and slime at the waterline, grey teak, faded canvas, brown water stains on the headliner, worn varnish in the cabin's walkway, faded cushions |
| L3 | 30 years, 0.9 | thirty years old and well kept: polished but faded and faintly yellow gelcoat with spider cracks at the stanchions and corners, the windows hazed and crazed, oiled teak, newer canvas, the vinyl yellowed, the sole's varnish deep amber |
| L4 | 20 years, 0.1 | twenty years left on a trailer or a mooring: heavy chalk, black streaks everywhere, green slime and clay over a pale worn bottom, the keel's iron rusting through, black teak, rotten canvas, a stained and mildewed headliner, mildew on every surface below, the sole's varnish gone grey and black |

## What slice 8 builds

### The cards

One card per surface (`Tools/shipkit/catalina22/textures/textures_c22.json`). Each says which of her materials it
covers (by kind), how close a camera comes, the pattern's real size, the detail maps it draws, its colour targets, and
what each level looks like on her. Every material the build makes is in a card or in `unweathered` with its reason (the
sails' cloth, drawn by `M_SailCloth` with its own `Age` and `Care`; the live ropes, drawn by `M_RigRope`; the name and
graphics, which are the boat kit's lettering); `dress()` stops otherwise.

| Surface | Her materials (by kind) | Closest camera | Detail maps | Colour targets (CC0 scans) |
| --- | --- | --- | --- | --- |
| Gelcoat | topsides: GelcoatHull, Topsides; deck: Deck; liner: Liner | 0.6 m | Gelcoat (shared) | none: every CC0 "white plastic" is lit, not an albedo |
| Non-skid | nonskid: NonSkid | 0.5 m | NonSkid (shared) | none |
| Bottom | antifouling: Antifouling (and the hull below the paint line); iron: Keel | 0.8 m | Gelcoat (shared) | rust: Poly Haven rusty_painted_metal, ambientCG Rust009 |
| Teak | oiled: Teak; varnish: Wood (the tiller) | 0.5 m | TeakWeathered, WoodVarnish (shared) | Poly Haven teak_veneer (L0), wood_planks_grey (L2), weathered_planks (L4) |
| Canvas | acrylic: SailCover (the pop-top's skirt and the main's cover); bag: SailBag | 0.6 m | Canvas (shared) | none |
| Vinyl | headliner: Headliner; rubrail: Rubrail, Lifeline | 0.4 m | Vinyl (hers) | none |
| Sole | sole: Sole | 0.4 m | WoodVarnish (shared) | none |
| Veneer | laminate: Laminate | 0.4 m | WoodVarnish (shared) | none |
| Fabric | cushion: Cushion; curtain: Curtain | 0.4 m | Tweed (hers) | none: no CC0 scan of a 1970s plaid |
| Plastic | white: WhitePlastic; black: BlackPlastic, Rubber | 0.4 m | none | none |
| Metal | stainless: Stainless, Wire; aluminium: Aluminium; painted: PaintedAluminium | 0.4 m | Metal (shared) | none |
| Acrylic | window: CabinWindow | 0.6 m | none | none |

The scans are measured only (their mean albedo), never shipped, and kept in the git-ignored
`Data/Reference/raw/textures/C22`.

Each card also gives every slot its new finish (`finish`): colour, roughness, metal and clear coat, from the game's
`BOAT_LIBRARY` where the slot exists there, so the Blender looks and the game's match. Eight slots have no library entry
yet; they are listed under "The game's side" below.

### The wear

`Tools/shipkit/catalina22/textures/weathering_c22.py` turns a level into wear terms and puts them on her, in the same
way as Bluebonnet's ([docs/jclass-11](../jclass-11/README.md)), whose node helpers and measuring modes it reuses.
`amounts()` gives each surface's terms from the loop's own time and dirt numbers (`Tools/texloop/wear.py`); neglect's
own terms (rust, rot, mildew, crazing past a few cracks) start past a threshold of dirt a kept boat never reaches; a
first season's marks grow as the square root of dirt, so L1 is not new; and a kept boat's routine renews what owners
renew (bottom paint every season and a half, the canvas every four years, cushions every three, the curtain every five,
the sole's varnish and the teak's oil each spring).

- **Gelcoat.** The gloss and clear coat go; chalk lifts the white to a flat dead white, most on what faces the sky; it
  yellows with age. Black streaks run down from the fittings, the ports and the rubrail's ends, and a dirty film settles
  in the corners. Scuffs gather in a band along the topsides where fenders and docks rub. Crazing opens at the
  stanchion bases and the moulding's corners. At the waterline the lake leaves its mark: a tan clay line in the first
  season, a brown clay mustache with green slime by six years, thick clay and slime when neglected; a kept boat's
  waterline is scrubbed clean. Inside, the liner greys where hands go (aft, round the companionway) and grows mildew low
  down where damp lies.
- **Non-skid.** Dust, then grey-brown dirt packed into the pattern along the walking paths; chalky and faded elsewhere;
  worn smooth on the paths of a kept old boat; dark grey-green with mildew and stains when neglected.
- **Bottom.** The blue fades and chalks, a clay film and soft slime smears gather (most toward the waterline), and the
  paint wears thin to the grey primer and white gelcoat at the edges and the keel stub. The iron swing keel rusts
  through its paint: soft brown bleeds, runs down from the edges and blisters.
- **Teak.** Oiled teak silvers within a season or two and goes black and green with mildew, its checks opening, when
  neglected; a kept boat's teak is oiled back to golden brown. The tiller's varnish dulls and wears where hands go, ambers
  with the years and peels to grey wood.
- **Canvas.** The acrylic fades on top, gathers dirty streaks along the lower edges and folds, and spots with mildew;
  neglected it is bleached and rotten with black mildew and green streaks.
- **Vinyl.** The headliner yellows, grimes round the hatch and handholds, and spreads brown leak stains from the
  windows and fittings, with black mildew dots when neglected. The rubrail chalks and scuffs.
- **Sole.** Teak strips 50 mm wide with 6 mm holly between them. The varnish wears grey down the middle where feet go,
  water stains the edges and the step dark, and the holly goes from cream to honey to grey-black.
- **Veneer.** Dries pale, darkens where hands hold the edges, and black water lines rise from the sole; re-oiled it
  deepens.
- **Fabric.** The tweed fades on top, wears at the seat fronts, and stains; neglected, washed-out with dark stains and
  mildew specks. The curtain fades in the light from the windows.
- **Plastic, metal, acrylic.** The white plastic creams and scuffs, the black greys and chalks. Stainless dulls and,
  only when neglected, tea-stains and rust-spots (slowly, in fresh water). Aluminium dulls, grimes and blooms white
  oxide. The smoked windows haze, craze and grime.

Each term is a value node named `wear:<surface>.<term>` in the material; `apply_level()` sets them for a level (or any
age and care), so one build renders every level.

### Her own detail maps

`Tools/shipkit/catalina22/textures/textures_c22.py` makes two close-up maps with numpy (no photos), using Bluebonnet's
generator's noise, normal-map and measuring helpers, written to `Inputs/c22-detail` as plain PNGs (the folder's
`.gitattributes` keeps them out of Git LFS, which the cloud cannot push): a normal map and a mask map each, tileable,
sized from the card's real pattern.

| Map | Tile | Pixels | Pixels a mm | Mask channels | Pattern (measured on the map, against the card) |
| --- | --- | --- | --- | --- | --- |
| Vinyl | 60 x 60 mm | 512 x 512 | 8.5 | cavity, roughness, height | grain 0.76 mm (card 0.6 to 1.6) |
| Tweed | 60 x 60 mm | 1024 x 1024 | 17.1 | plaid tone, weave gaps, height | weave 1.2 mm (card 0.8 to 1.6), plaid 60 mm (card 60) |

The vinyl is a pebbled leather grain for the headliner and rubrail; the tweed is a 2/2 twill of thick woollen yarns in a
6 cm plaid of three tones, the period's olive and brown. The shared library's maps (`Inputs/boat-detail`: Gelcoat,
NonSkid, TeakWeathered, WoodVarnish, Metal, Canvas) are already resident for the J/22, so they cost her nothing.

### The budget

Her own maps only, block compressed with mips (BC5 normals, BC1 masks):

| Tier | Budget (set here) | Her maps |
| --- | --- | --- |
| High and Ultra | 3 MB | 2.5 MB: Vinyl 0.5, Tweed 2.0 |
| Medium | 0 MB | none: Medium draws no detail maps, only the colour and roughness math |

RESULTS

## The game's side

The game draws her through the shared `M_BoatSurface` and `BOAT_LIBRARY` in `scripts/make_materials.py`. Most of her
slots map to library entries that exist (Topsides, Deck, NonSkid, Teak, Wood, SailCoverTan, SailCover, WhitePlastic,
BlackPlastic, Rubber, Stainless, Aluminium, CabinWindow). Eight are new, and come in a separate small pull request once
this one is on main, since `make_materials.py` is shared by every material and needs the Mac's rebuilt assets committed
with it:

| New entry | Surface kind | From her slot |
| --- | --- | --- |
| Liner | 1 gelcoat | Liner |
| Headliner | 0 (plain) | Headliner |
| Sole | 6 varnished wood, grain | Sole |
| Laminate | 6 varnished wood, grain | Laminate |
| Cushion | 11 canvas | Cushion |
| Curtain | 11 canvas | Curtain |
| RubrailWhite | 8 rubber | Rubrail |
| AntifoulingBlue | 0 (plain) | Antifouling, Keel |

## How to run

The same venv as slices 1 to 7 (Python with pip `bpy`, numpy, scipy, pillow). From the repo root:

```
python3 -I Tools/shipkit/catalina22/textures/textures_c22.py              # her two maps into Inputs/c22-detail
<venv>/bin/python Tools/shipkit/catalina22/build_c22.py <out>              # the boat (slices 1 to 7)
blender -b -P Tools/shipkit/catalina22/textures/render_wear_c22.py -- <out>/c22.blend <out>/wear
python3 -I Tools/shipkit/catalina22/textures/wear_check_c22.py <out>/wear --fetch --sheets docs/c22-9
```

With the pip `bpy` module, `<venv>/bin/python Tools/shipkit/catalina22/textures/render_wear_c22.py <blend> <out>` runs
the same. `weathering_c22.py` can also dress a build and save it: `blender -b -P weathering_c22.py -- <c22.blend>
<out.blend> [--level L2]`. The render is eight views at five levels, lit and as albedo, plus an id shot each: 88 renders,
about 45 minutes at 900 pixels on the cloud's CPU. `--fetch` downloads the CC0 colour targets once.

## Files

| File | What it is |
| --- | --- |
| `Tools/shipkit/catalina22/textures/textures_c22.json` | new: the twelve cards, the unweathered materials and why, each slot's finish and its game entry, her maps' cards, the budget |
| `Tools/shipkit/catalina22/textures/weathering_c22.py` | new: the wear terms by level (`amounts`), the Blender dressers per surface, `dress()`, `apply_level()`, the id and albedo modes, the texture report |
| `Tools/shipkit/catalina22/textures/textures_c22.py` | new: her two detail maps (vinyl, tweed) and their measures |
| `Tools/shipkit/catalina22/textures/render_wear_c22.py` | new: the eight wear views at five levels, lit, as albedo and as ids |
| `Tools/shipkit/catalina22/textures/wear_check_c22.py` | new: the ladder, colour, maps, budget and blind checks, and the ladder and blind sheets |
| `Tools/shipkit/catalina22/textures/reviews_c22.json` | new: the blind reviewers' answers and least-real notes |
| `Inputs/c22-detail/` | new: the two maps (normal and mask PNGs, plain git) and `c22_detail.json` |
| `docs/licences/assets.csv` | a row for `Inputs/c22-detail` (generated, our own) |
| `docs/c22-9/` | this page, the contact sheet, the ladder sheets, the blind sheets and their key, `wear_check.json` |
