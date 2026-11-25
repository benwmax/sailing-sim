# Hydrofoil moth, slice 0: size card, class rules, references and the physics spec

Bean asked for a hydrofoil moth on Nov 25 2026, the first boat of the post-slice "fun boats" list, built by the
process the Catalina 22, the frigate, the Lagoon 42 and the Hobie 16 went through. Unlike those, she is a **new
boat**: the game has no moth, so there is no "before" model to measure. Slice 0 is the size card, the class rules,
the licence-checked photos, the size check and the spec for the physics she needs (`physics.md`).

This is post-slice work: nothing here is imported into Unreal and nothing in the game changes. The new files are
under `Tools/`, so the pull request needs Bean's `bean-approved` label (the Sensitive files check), and it stays a
draft until after the Dec 11 release.

## What she is

An 11-foot single-hander that flies. At rest and in light air she floats on a very narrow hull like a canoe. From
about 7 knots two underwater wings, the **main foil** under the middle and the **elevator** on the rudder, lift the
whole boat clear and she sails 0.4 to 0.5 m above the water, 15 to 20 knots upwind and 25 to 30 downwind. A **wand**
at the bow, a stick that drags on the water, holds her height by working a flap on the main foil. The sailor sits on
two **hiking wings** (racks) out to the side, flies her heeled to windward, and steers with a tiller extension
whose **twist grip** trims the elevator.

The real class is the International Moth, a development class: its rules limit only the hull's length, the beam,
the sail area and the mast and sail's length, and every builder's boat is different inside them. The game's boat is
an invented design inside those limits, under an invented class name, **Lacewing 11** (Bean may rename her), with
no builder's name or logo. Several reference photos carry builders' logos and sail graphics: they are looked at for
shape only.

## The class rules she is built to

International Moth Class Rules 2017 (only the limits; the rest of the rule book is racing and measurement):

| Rule | Limit |
| --- | --- |
| 6.1 Hull length, without the removable rudder gantry and bow fittings | 3,355 mm |
| 6.1.5 Gantry or bow fittings more than 500 mm past the hull count toward its length | so LOA 4.355 m at most |
| 6.2 Overall beam, wings included | 2,250 mm |
| 6.3.2 No hollow in the bottom over 75 mm deep in the aft 2.7 m | |
| 6.3.3 Every foil but the rudder's leaves the hull below the waterline | the main strut goes through the hull |
| 8.1 Mast | 6,250 mm (boats sail 5,100 today) |
| 9.1, 9.2 One sail; rig area with the mast's top 5,185 mm; sail within 5,185 mm of the throat | 8.25 m² |
| 10.1, 11 One person; no trapeze, no moving seat, no multihull | |
| 12.2 No stored-power remote controls (springs and shock cord are allowed) | the wand is purely mechanical |

## The size card

`Tools/shipkit/moth/specs_moth.json` holds the targets, the rules' limits (`limits`: the check fails anything over a
limit at all, whatever the 3% tolerance), the source of each number, how the check measures each, the triangle
budgets per slice and what the game will float her with.

| Measure | Target | Where it comes from |
| --- | ---: | --- |
| Hull length | 3.355 m | the rule's limit: every moth is built to it |
| Beam over the wings | 2.25 m | the rule's limit |
| Hull beam / depth | 0.38 / 0.45 m | slice 1 (`docs/moth-2`): the depth raised from 0.36 after the afloat photo |
| Rigged weight | 35 kg | the class site's 30-45 kg for foilers |
| Mast / luff | 5.1 / 5.1 m | a sailmaker's tuning guide (today's standard mast) |
| Sail area | 8.25 m² | the rule's limit |
| Main foil span / area | 1.0 m / 0.12 m² | typical "big foil"; slice 3 checks by photo |
| Elevator span / area | 0.72 m / 0.065 m² | typical; slice 3 |
| Strut and rudder below the hull | 1.05 m | enough to fly 0.5 m clear with the foil 0.55 m under |
| Wand / gantry | 0.95 / 0.45 m | typical; slice 3 |
| Sailor | 80 kg | the class's 70-100 kg; at rest the hull floats 115 kg (0.115 m³) |

## The size check

`python3 -I Tools/shipkit/moth/moth_check.py --card` checks the card (all targets inside the rules) and prints the
lift each foil needs from 5 to 30 knots (the table is in `physics.md`). From slice 1 on,
`moth_check.py <stats.json> [<sockets.json>] [--slice N]` measures the built model as the Hobie's check does: hull
length and beam from the hull object, beam over the wings, each foil's span, how far the strut and rudder reach below
the hull, the wand and gantry from sockets, and areas and weight from the build report. Today:

```
length_hull_m 3.355 (limit 3.355) ok · beam_m 2.250 (limit 2.250) ok · mast 5.100 (limit 6.250) ok
luff 5.100 (limit 5.185) ok · sail 8.250 (limit 8.250) ok · design volume 0.115 m^3
take-off at 7-8 knots needs CL 1.23-0.94 on the main foil; at 20 knots 0.15
pass
```

## References

`Tools/shipkit/moth/refs.json`: eleven photos from Commons' Category:Moth (dinghy), public domain or plain CC BY
only, licence and author read from Commons' own metadata (13 CC BY-SA files left out, among them the only view from
underneath). The best ones:

- **Sunday Flying!** (Mark Robinson, CC BY 2.0): a flying quarter view: ride height (the gap under the hull is about
  the hull's own depth at the bow, 0.4-0.5 m), the struts and the wand.
- **Moth-dinghy** (Mark Robinson, CC BY 2.0): a boat laid on its side ashore, foils in the air: strut, main foil,
  rudder gantry, elevator, wand pivot.
- **Moth-dinghy (1)** (CC BY 2.0): afloat before take-off: how low the hull sits at rest.
- **Traunsee 2024** (Tigerente, CC BY 4.0): two current boats on trolleys, broadside, with a person for scale.

`python3 -I Tools/shipkit/fetch_refs.py Tools/shipkit/moth/refs.json Data/Reference/raw/boats/Moth` downloads them
into the git-ignored folder. No photo is in the repo. Photos from Bean (a foiler at Rush Creek, if one ever turns up:
the foils and the bow wand close up) would go in the same folder.

## The physics

`physics.md`: what the Mac must add (foils that lift, the flap, the wand loop, elevator trim, surface and
ventilation effects, crash states, a hull that leaves the water, her reference polar and tests) and the risks. The
short version: the game's foils all stand upright today, so the moth needs new physics before she can sail at all,
and it touches code every boat uses.

## The slices

| Slice | What | Who |
| --- | --- | --- |
| 0 | Size card, rules, references, check, physics spec (this page) | cloud |
| 1 | Hull | cloud |
| 2 | Hiking wings and their deck | cloud |
| 3 | Foils: main strut and foil with flap, rudder and elevator on the gantry, the wand and its linkage | cloud |
| 4 | Rig: mast, shrouds, boom, deck-sweeper sail | cloud |
| A | Blind review of the whole boat | cloud |
| 5 | Hardware and lines: tiller and twist grip, vang, cunningham, mainsheet, hiking straps | cloud |
| B | Blind review | cloud |
| 6 | Textures: carbon, wing cloth, clear film sail | cloud |
| 7 | Light copy, sockets, the build report's weight | cloud |
| 8 | Physics (`physics.md`), a new `EBoatType`, her polar and tests | Mac, after Dec 11, behind the Lagoon 42 and Hobie 16 |
| 9 | Import, gates, stills | PC, after Dec 11 (needs Bean's "resume pc") |

Budget: about 0.45M triangles outside (the boat cap is 3M) and $0 planned.
