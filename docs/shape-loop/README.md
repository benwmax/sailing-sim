# Boat shape loop

Raises the boats' big shapes and features (hull and deck fairing, cabin, cockpit, companionway, rails, drains, transom,
keel and rudder), one section per PR, measured against class drawings and specs. Plan and Bean's decisions:
<https://claude.ai/artifact/LUQJog4e1veru9wwaQsxpn> (Nov 10 2026). It sits beside the part detail loop
(`docs/part-detail-loop`) and the texture loop (`docs/texture-loop`).

Bean's decisions (Nov 10 2026): J/22 hero and Sunfish only for now; hatches always closed (separate closed parts, no
open state, no Mac code); the underwater shape stays matched to the physics; club photos later; Ultra is measured at
4K on BEN-PC.

## Quality rule

Every boat is authored once at full quality; the lower tiers are derived from it (coarser Nanite error and texture
mips for High and Medium, a baked LOD mesh for Low, the quarter-size light copy for AI boats). The master is never cut
to rescue a lower tier: tune that tier's derivation instead.

| Gate | Where | Target | Floor (blocks a merge) |
| --- | --- | --- | --- |
| Ultra, average over the bench views | BEN-PC, 4K | 60 fps | 50 fps |
| Ultra, worst boats view | BEN-PC, 4K | 50 fps | 45 fps |
| Ultra, 1% lows in the worst view | BEN-PC, 4K | 40 fps | 35 fps |
| High | Mac gate | | 45 fps |
| Medium | Mac gate | | 60 fps |
| Any boats view vs main | Mac gate | | no more than 2 fps slower |

The 3M triangles per boat line is a checkpoint where we measure, not a ceiling.

## Sections

Sections follow the boat's real mouldings: `Tools/shapeloop/sections_j22.json` lists each section's objects (by name
prefix), the build functions it owns, its borders and the joins the seam check measures.

1. The hull is never sliced lengthwise; it is faired as one surface.
2. Every PR also gets a whole-boat pass: the fixed camera set, the outline check and the blind A/B always run on the
   whole boat, with close-ups of every join the section touches.
3. Joins overlap, they don't just meet: separate meshes simplify separately on the derived tiers, so edges that only
   touch can open at distance. Check joins at Medium in game, not just Ultra.
4. Only the hull section changes the shared curves (`sheer_z`, `half_beam`, `section`, `deck_z`); a PR that does re-runs
   every section's checks. The `moved` check lists every object centre that moved (the bake's sockets come from them).

`build_j22_hero.py` stays one file: the deck mould, cockpit and cabin share one baked atlas (`bake_j22_hero.py`
DeckMould), and the interior is built from the script's whole namespace, so splitting it would add hidden links for
little gain. Hero shape PRs go one at a time.

## The loop, per section

1. **Card**: `Tools/shapeloop/cards/<boat>-<section>.json`: targets with tier and source, outline views, feature list,
   moves allowed outside the section, triangle line, Mac wiring (none while hatches stay closed).
2. **References**: links and numbers in the card; drawings, manuals and photos in git-ignored
   `Data/Reference/raw/boats/<Boat>/shape/`. Tiers: A class rules and ORC, B builder and owner-manual drawings, C our
   measured reference models (Sunfish), D free-licence photos, E generic practice for the boat type (marked on the
   card), F Bean's photos only when a top-half feature's sources disagree by more than 10% or don't show it and a wrong
   guess would read as a different boat; those go on one shot list per club visit.
3. **Baseline**: build main, then run the four tools below into `<work>/base`.
4. **Rebuild** the section in the build script.
5. **Round**: build again and run the tools into `<work>/rN`; `score.py` against the baseline.
6. **Blind A/B**: 3 fresh reviewer agents see the reference and the two renders (unlabelled), pick the closer one; the
   round must win at least 2 of 3 with no "wrong boat". A round that loses is reverted.
7. **Sheet** for Bean: reference, before, after.
8. **QA review** by a separate critical agent: the diff, the card and `score.md` only.
9. **PR**, then PC: `--clean-bake`, import, in-game stills from the same views, 4K Ultra bench; Mac: `scripts/gate.sh
   --scope boats` (and `--scope crew` when seats or handholds moved) and the material rebuild on the branch.

## Tools

All in `Tools/shapeloop`, run with Blender's Python (pip `bpy`); `score.py` and `make_sheet.py` need only numpy, scipy
and Pillow (the pip-bpy venv has them).

```
B=<work>/base
python build_j22_hero.py -- $B                       # (via a wrapper that imports bpy first; J22H_FONT=<a .ttf>)
python Tools/shapeloop/measure.py   $B/j22_hero.blend Tools/shapeloop/sections_j22.json $B
python Tools/shapeloop/fairness.py  $B/j22_hero.blend $B
python Tools/shapeloop/seams.py     $B/j22_hero.blend Tools/shapeloop/sections_j22.json $B
python Tools/shapeloop/render_set.py $B/j22_hero.blend Tools/shapeloop/sections_j22.json $B
python Tools/shapeloop/score.py Tools/shapeloop/cards/j22-hull_shell.json $B <work>/r1 --refs <traced masks>
```

| Tool | Writes | Check |
| --- | --- | --- |
| `measure.py` | `stats.json`: objects with section, triangles, bounds, centre; triangles per section; hull LOA, beam, freeboards and 21 station cuts; the build's canoe volume and CB | size, budget, moved, physics |
| `fairness.py` | `fairness.json`: 10 waterline and 10 station cuts of the hull, resampled every 2 cm; inflections (sign changes of the 30 cm curvature) and kinks (peaks and dips of the 10 cm curvature standing out by 0.5 rad/m; `kinks_firm` at 0.7) per line; the ends and the transom face are left out | fairness (no line may gain inflections or firm kinks over the baseline's kinks, or go missing) |
| `seams.py` | `seams.json`: per join, the first part's surface sampled every 1 cm within 2 cm of the second; in 5 cm bins the closest approach (a sample more than 1 mm inside the second part counts as touching); bins 0.5-20 mm apart are open | seams (no join may lose contact, open a bin that touched (now over 3 mm) or get a gap 0.5 mm wider) |
| `render_set.py` | silhouettes (profile, plan, bow, stern; bow on the left; `sil_scale.json` gives metres per pixel), clay renders (those plus 3/4, bow and stern 3/4, helm eye), zebra stripes | outline, fairness by eye, blind A/B, sheet |
| `score.py` | `score.json`, `score.md` (goes in the PR) | all of the above; exits 1 on a hard fail |

Hard checks: fairness, seams, physics (canoe volume within 1% and CB within 2 cm of the baseline; a card with
`"physics_reference": "physics"` holds the round to the physics it ships with instead) and moved (nothing
outside the card's sections moves, appears or goes unless the card lists it; the hull card lists the sections built
on its curves). A missing tool output (a crash, a renamed hull) is a hard fail, never a silent pass. Outline masks
traced from a drawing go in the refs folder with `<view>.mask.json` giving the drawing's metres per pixel, so a boat
the wrong size scores lower.

Section rules in `sections_j22.json`: an entry ending in `_` or `*` is a name prefix, anything else an exact name.

## Baseline

`baseline/` holds the tools' output for main at the time of wave 0, so later rounds can see what the boat measured
before the loop began.

Main at `46d23774` (Nov 10 2026), built in the cloud with pip bpy 5.2:

| Measure | Value |
| --- | --- |
| Triangles in the build (all objects, sails off) | 1,080,328 |
| Shape sections | hull 61,164; joint and rails 43,184; deck 20,226; cabin 43,494; cockpit 20,216; transom and bow 19,434; keel and rudder 19,908 |
| Hull LOA, beam | 6.860 m, 2.448 m (class 6.858, 2.438) |
| Freeboard at bow, stern | 0.782 m, 0.569 m (ORC 0.774 at its point, 0.568) |
| Canoe body volume, CB | 1.088 m³ at (-0.226, -0.074); the physics floats 1.052 m³ at (-0.195, -0.080): the hero already displaces 3.4% more than the physics. Wave 1 closed the gap: the J/22 physics now floats the hero's own sections (see below). |
| Fairness | 19 lines, 0 inflections, 22 kinks (19 on the four lowest waterlines near the keel root and bow, 3 on stations); 29 by the wave 1 count (curvature peaks and dips) |

Tests run on copies of the baseline (QA review, Nov 10):

| Copy | Expected | Result |
| --- | --- | --- |
| Hull subdivided once (same shape, 4x the mesh); hull, deck, cabin and keel subdivided | pass | pass: fairness 22 → 22 kinks, no seam bin opened |
| 12 mm bump on the port topside, cabin raised 10 mm | fail | fail: fairness (waterline 5 and station 6 gain a kink), seams (deck-cabin gap 6.8 → 8.2 mm, cabin-cockpit 2.2 → 12.1 mm) |
| Cabin raised 80 mm | fail | fail: seams, deck-cabin and cabin-cockpit lose contact |
| Hull renamed | fail | fail: measure.py stops, score reports the missing stats |
| Keel lowered 50 mm | fail | fail: seams, the keel root opens (widest gap 0 → 7.5 mm) |
| Cabin raised 25 mm | fail | fail: seams, 14 deck-cabin bins that touched now open |
| A new object inside the boat whose name is in no section | listed | the "unsectioned" row names it for the QA review |

The physics check reads the build's own report, so it only sees real builds.

## Sunfish

The fleet build (`Tools/blender/build_fleet.py`) joins each boat into one hull mesh before exporting the fbx, so the
section split by object name doesn't apply to it yet. Wave 5 adds an option to save the pre-join scene as a .blend
(no change to the fbx), then a `sections_sunfish.json` (hull and deck, cockpit well, board and trunk, rudder, small
fittings). The Sunfish's underwater hull is the physics hull exactly, so its physics check is exact.

## Wave 1 changes to the tools (Nov 10)

- Fairness counts peaks and dips of the curvature instead of departures from its 50 cm average: making a bend tighter on
  purpose (the bilge when the plan narrows) no longer reads as a kink, a bump still does. Rechecked on the baseline
  copies: subdivided hull 29 → 29; the 12 mm bump fails (waterline 5 gains 2 firm kinks). A round is judged on firm
  kinks (0.7 rad/m) against the baseline's at 0.5, so a wiggle at the threshold doesn't flip a line either way.
- Seams skip bins past the second part's end along the join (the deck ahead of the cabin's nose measured the way to its
  face, not a gap). Hull|Deck is replaced by Joint_|Deck: the deck's top sits 0.4 mm over the hull's rim, so Hull|Deck
  read 47 of 138 bins open on the baseline and flickered with any change; the joint overlaps both and is the seam.
- The J/22's physics hull is now the hero's own sections (`Tools/boats/j22/make_j22_hull.py` writes
  `Source/SailingPhysics/Private/J22HullData.inl`), so the hull card checks the hero against the physics it ships with.
  Rerun the script whenever `keel_z`, `sheer_z`, `half_beam`, `section` or `CANOE_D` change.

## Wave 2 changes (Nov 11): the cockpit's footwell

- `measure.py` writes `features` to `stats.json`: the footwell's width (between the seat fronts' inner faces 10 cm over
  the sole's top, cut at 30, 50 and 70% of the Cockpit's length; the card reads the middle cut), the sole's height,
  the cockpit's aft end and the aft deck (transom to the cockpit). A card target may name any of them; `score.py` looks
  in `hull`, then `features`.
- Card `cards/j22-cockpit.json`: footwell 0.63 m ±0.04 (j22.org deck plan 0.62, the Commons overhead photo 0.29 of the
  deck beam = 0.64); the hero had 0.80. `SEAT_IN` 0.40 → 0.31 in `build_j22_hero.py`, and `CrewPose.cpp`'s hero well
  (`SeatIn`) with it, so the crew's feet stand on the sole the mesh draws. The build stores `SEAT_Z` and `SEAT_IN` on
  the scene for `bake_j22_hero.py` (`JibTailRest`); the PC reruns `make_coil_data.py` after the rebake (the jib tails'
  coils move inboard with the seat fronts). Blind A/B 3 of 3 for the narrower footwell.
- Round 2: the cockpit's side walls. They followed the sheer 0.25 m in (`SIDE_DECK`), so the cockpit widened forward
  to 1.92 m at the cabin; the deck plan and both overhead photos show straight walls with a slight taper and wide side
  decks. `coaming_y(x)` (`COAMING_HALF` 0.64 aft to 0.73 forward, at least `COAMING_AFT_DECK` 0.12 m from the sheer)
  now places the deck's cockpit hole, the liner, the coaming caps, the jib cams and leads and the traveller's ends;
  the cabin trunk still follows `SIDE_DECK` (wave 3). The crew's well gets `MaxHalfAft`/`MaxHalf` and `WallHalf()`.
  Cockpit 1.33 / 1.37 / 1.41 m at 30 / 50 / 70% (was 1.47 / 1.71 / 1.87). Blind A/B 3 of 3. `measure.py` adds
  `cockpit_width_aft`, `cockpit_width`, `cockpit_width_fwd`; a card's `seams_shorter` lets a join get shorter on
  purpose (with a reason and the fewest bins it may keep): Cabin|Cockpit, whose cabin face now stands on the deck
  outboard of the walls.
- Findings left for later rounds are in the card: the cabin's aft face 7 cm forward of the deck plan's (wave 3), the
  whole cockpit perhaps too wide (side decks 0.25 m; check with a camera solve), the short step at the footwell's
  fore end.

## Wave 3 changes (Nov 11): the cabin trunk

- The trunk followed the sheer 0.25 m in (`SIDE_DECK`): 1.92 m wide at its aft end, about 0.79 of the beam. Its foot
  now follows `CABIN_PLAN` (`cabin_foot(x)` in `build_j22_hero.py`): 0.83 m out aft, 0.755 at x 0.4, 0.645 at x 1.0,
  between the j22.org deck plan's column scans and the Harken J/22 deck layout Bean sent (0.80-0.85 aft, about 0.75 and
  0.70 forward), kept convex: the scan's own points gave the side a waist that 3 of 3 blind reviewers marked down.
  The plan's line goes in as it is (the subdivision takes about 2 cm off the foot); an extra section 1 cm behind the
  aft face keeps its corners on the cockpit coaming's lip (they rounded 3 cm aft and 6 cm in, a 4.9 mm seam gap).
- The halyard winches sit on the roof's aft corners (0.58 m out, as in the Harken drawing; the pods of the first try
  are gone), the cams just forward (`HAL_CAM_Y` 0.54); the portlights and headliner follow `cabin_ring`.
- Card `cards/j22-cabin.json`: widths 12 cm under the top at x -0.45 / 0.40 / 1.00, 1.60 / 1.45 / 1.23 m; built
  1.59 / 1.46 / 1.25. `measure.py` adds `outer_width` and `cabin_width_aft/mid/fwd`. Blind A/B 3 of 3 (round 2).
- Crew: `FCrewCabinTrunk` takes a plan table (`PlanX`/`PlanHalf`, `HalfAt()`); the hero's mirrors `CABIN_PLAN` and
  the built nose, so `CrewFloorZ`/`CrewInsideBoat` with the hero's flag put feet on the side deck beside the trunk
  (`SailingSim.Visual` checks at x -0.30 and 0.83). CrewMotion's own placement still reads the light J/22's trunk.
- The rebake regenerates `J22H_coils.json` and `J22CoilData.inl` (the halyard tails move with the cams).
- Findings for later: the trunk's front reads blunt and pointed next to the Harken drawing; a small notch where each
  coaming end meets the trunk side; the trunk's height and aft face position against IMG_9224 (its top 120-150 px high
  in the overlay).

## Wave 3b changes (Nov 12): the trunk's height and front

- The roof stood a fixed 0.30 m over the sheer (`CABIN_H0`). The trailer broadside photo (Commons
  `j22-broadside-trailer`, scaled 6.22 mm/px from the stem and the keel's leading edge) gives the crown 0.29 m over the
  sheer aft and 0.17-0.19 at the top of the raked front, which the Mac's IMG_9224 overlay agreed with (the top read
  120-150 px high). `cabin_hgt(x)` now falls from `CABIN_H_AFT` 0.23 at the aft face to `CABIN_H_BRK` 0.12 at
  `CABIN_BRK` 1.29 (the side's height; the camber adds 0.055 at the centreline), and the raked front drops from there.
- The front was pointed at 1.65; the photo puts its foot at about 1.55, j22.org's plan blunt at 1.57 (0.41 half
  width), Harken 1.5-1.6. `CABIN_FWD` 1.57 and `CABIN_PLAN` ends square at half width 0.43 (no nose taper).
- The portlights stay inside the trunk's lower sides: `win_top(x)`/`win_bot(x)` in `j22_interior.py` slope with the
  roof, the forward end is raked, and the build stops if a window would cross the shoulder or the foot. The deck
  mould's window mask in `j22_materials.py` follows the same lines.
- Everything on the roof or at the mast foot follows it down: hatches, handrails, winches and cams, the mast step
  (the mast's foot drops 109 mm, its top stays), turning blocks, cunningham, vang, compression post.
- Card: the widths are now the foot out to out 5 cm over the sheer (12 cm under the top crossed the windows once the
  roof came down): targets 1.66 / 1.49 / 1.30 m at x -0.45 / 0.40 / 1.00; built 1.66 / 1.54 / 1.32.
- Crew: `FCrewCabinTrunk` gains `PlanTop` and `HeightAt(X)`; the hero's table mirrors the built top, and
  `CrewFloorZ`/`CrewInsideBoat` use it (other boats keep the fixed `Height`).
- Open: the aft face at -0.55 against the photo's -0.44 to -0.48 (j22.org -0.50): moving it couples the cockpit's
  forward end, the companionway and the crew wells, so it is its own round.

## Wave 3c changes (Nov 12): the trunk's raked front

- The raked front was a smoothstep falloff from `CABIN_BRK` to `CABIN_FWD`, which rounded both of its edges into one
  long soft ramp (three blind reviewers on wave 3b). It is now a straight panel: `front` is linear, the top drops
  `CABIN_FRONT_DROP` 0.95 of its height to the foredeck. A first try left a 25% lip there and lost the blind A/B 0 of 3
  (the lip read as a step; the photos run the face straight onto the deck).
- The plan's front corners are chamfered, as both plans draw them: `CABIN_PLAN` ends (1.45, 0.49), (1.51, 0.46),
  (1.57, 0.38), still convex. `build_cabin` pins sections either side of the crease at `CABIN_BRK` and at 1.45, 1.51,
  1.55 and the front: on the even 2.9 cm spacing alone the subdivision rounded the chamfer and the crease away.
- Crew: the hero's `PlanHalf`/`PlanTop` table ends 0.540 / 0.496 / 0.440 / 0.370 (measure.py's cut) and 0.163 / 0.123 / 0.095 / 0.072 at
  x 1.36 / 1.45 / 1.52 / 1.57 (measured on the build). The raked face's slope now falls entirely in the deck mould's
  `flat` (non-skid) band; the rebake regenerates the mould.

## Cockpit leftovers (Nov 12): the teak coaming cap

- The cabin's aft face was checked against both class deck plans (the class rules' Plan E, page 41, and j22.org's):
  both put it at 41% of LOA from the transom (x -0.58 to -0.60) and the trunk's front at 72-73% (1.55-1.58), so the
  hero's -0.55 / 1.57 stay; the trailer broadside's -0.46 was the coaming hiding the trunk's aft corner. The step where
  the trunk stands 11 cm outboard of the cockpit wall is in both plans too.
- `coaming_cap` was a 44 mm round dowel. It is now a flat board lying on the deck along the cockpit's edge (`CAP_W` 0.065
  wide, `CAP_T` 0.016 proud, its inner edge 4 mm over the coaming's lip, rounded edges), from the cabin's aft face to
  the aft deck in one piece (Commons j22-above-deck-cockpit). Blind A/B 3 of 3; their notes (thinner, wider, one piece
  to the aft deck) are in. The jib sheet's baked lead runs over the board's inner edge with no sag into it.
- The footwell's fore step already reads as in the photos; left as is.

## Wave 4, round 3 (Nov 12-13): keel and rudder fairing

Above the physics only: the keel's planform (`keel_edges`, boatkit-3) and the rudder's span and chord are the physics
foils' and stay as they were (card `cards/j22-keel.json`).

- The keel's sections follow the class's Plan C table of offsets (International J/22 Class Rules, section H; the 1993
  yearbook prints the same page): `KEEL_SECTIONS` holds the half-widths at the leading edge and 15 chord stations at the four sections 216,
  458, 700 and 942 mm under the hull, `keel_half` interpolates them in depth (held past the first and last) and along
  the chord (a monotone cubic, a square-root nose ahead of 2.5%). The fin is 10% thick at the root and 14% at the tip,
  fullest at 30-35%, with a 6 mm blunt trailing edge; it was a NACA 0012 thinned to 8% at the tip.
- The keel meets the hull on a crisp joint. A first round swept a 35 mm concave fillet round the fin (ray-cast to
  the hull) and lost the blind A/B 0 of 3: at that size, and again at 12 mm, it read as a raised bead along the root,
  where the crane photo (Commons j22-broadside-crane-stern) shows the fin going straight into the hull.
- The keel's and the rudder's bottoms close round: the section thins on a quarter ellipse over the last 12 and 9 mm
  (the bottom ring keeps 12% of it, a narrow flat), the planform carried straight down. The rudder's bottom corners are
  on Plan D's 40 mm radius (`j22_steering.BOT_CORNER_R`), sharing the same rings so the outline runs straight into the
  arcs (round 2 dropped the edge's rings below the arcs, and three reviewers saw a thin plate under the blade). The
  keel's trailing edge ends square on Plan C's 6 mm (the ring's middle vertex on the centreline; it sat 3 mm to one
  side), and its nose meets Plan C's cubic in value and slope at 2.5% (a plain square root left a line down the
  leading edge).
- Blind A/B: round 1 0 of 3 (the fillet), round 2 1 of 3, round 3 3 of 3. All three round 3 reviewers noted the keel's
  6 mm trailing edge reads as a rounded strip at the hull (smooth shading over the blunt end): a follow-up.
- Plan D also puts the rudder at 300 mm chord, 13% thick, reaching 860-890 mm under the hull's bottom at the transom
  (about z -0.65; the hero's reaches -0.98 at about 350 mm). That is a real change to the steering and waits for a
  physics calibration pass: see the card's findings.
