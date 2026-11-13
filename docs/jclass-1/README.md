# J-Class 1: Bluebonnet's size card and hull lines

*Bluebonnet* is our own J-Class racing sloop of 1937, built for the invented Bolivar Roads Yacht Club of Galveston.
She is drawn to the 1930s Universal Rule and sized between *Endeavour* (1934) and *Ranger* (1937), with the 1934-37
look: steel hull, laid teak deck, winches on deck, full accommodation below. Plan and Bean's decisions (Nov 13 2026):
<https://claude.ai/artifact/WdUKp8somgyNJZDyESCgyU>. This page covers slice 0 (references, size card and rule check)
and slice 1 (hull lines). It is post-slice art: nothing here is imported into Unreal or wired into the game yet.

Unlike the frigate, whose hull is read off a 1927 lines plan, *Bluebonnet*'s lines are our own design. Nothing is
traced from a real J's drawing or photo. The real Js only set the targets (their published sizes) and the look we
check her against.

## What slice 1 builds

The moulded hull (the outside of the frames, inside the plating) as one surface: canoe body and keel together, the
wineglass section of the 1930s Js. Plus the transom, and a flat cambered placeholder deck so renders read as a yacht.
The mesh is 182,682 triangles (hull 172,422, transom 216, deck 10,044), under the plan's 200k for this slice. The
plating, the lead keel's casting line and the rudder are slice 2, the deck and deckhouses slice 3.

## The size card and the rule

`Tools/shipkit/jclass/specs_bluebonnet.json` holds the targets, the rule and the published sizes of three real Js.
Every later slice is checked against it by `rule_check.py`: each size within 5% of its target, the rating at 76 ft or
less, the draft at 15 ft or less.

| Measure | Bluebonnet (model) | Target | *Endeavour* 1934 | *Ranger* 1937 |
| --- | --- | --- | --- | --- |
| Length overall | 131.0 ft (39.93 m) | 131 ft | 129.5 ft | 135.2 ft |
| Load waterline | 85.4 ft (26.03 m) | 85 ft | sources differ | 87 ft |
| Beam | 21.5 ft (6.56 m) | 21.5 ft | 22 ft | 21 ft |
| Beam at the waterline | 20.0 ft (6.09 m) | | | |
| Draft | 14.8 ft (4.52 m) | 15 ft | 15 ft | 15 ft |
| Displacement | 155.3 long tons | 155 | 143 | 166 |
| Bow overhang | 18.8 ft | 19 ft | | |
| Stern overhang | 26.8 ft | 27 ft | | |
| Least freeboard | 4.4 ft (1.34 m) | 4.2 ft | | |
| Sail area (rated) | 7,500 sq ft (target until slice 6) | 7,500 | 7,651 | 7,546 |
| Rating | 75.7 ft | 76 or less | | 76 (official) |

The displacement is the moulded hull's 152.9 m³ (154.3 long tons of sea water) plus 35 cu ft (1 long ton) for the
rudder until slice 2 builds it.

**The rule.** R = 0.18 L √S / ∛D, with L and R in feet, S in square feet and D in cubic feet (35 cu ft of sea water
to the long ton). A J must rate 76 ft or less.

* **L is taken as the load waterline length.** The rule's own length measurement changed over the years and added
  something for the overhangs. With L as the waterline, *Ranger*'s published figures (87 ft, 7,546 sq ft, 166 tons)
  rate 75.7 ft against her official 76, so the simplification is close.
* **S is the size card's target** until slice 6 measures the sails.
* **The 15 ft draft** is what the 1934-37 Js drew (*Ranger*'s and *Endeavour*'s published draft). A copy of the
  rule's text with the class's draft limit could not be read from the cloud (Wikipedia and the archive sites are
  blocked), so slice 0 holds her to 15 ft as a design limit.
* **From 1934 the class put the winches on deck and required full accommodation below.** Slices 3, 7, 9 and 10 build
  to that.

## Sources and licence

* **Published sizes** (museum and class pages, read Nov 2026) are facts: free to use. They are in the size card's
  `published` block and only check our sizes.
* **Photos:** `Tools/shipkit/jclass/refs.json` lists eight photos of real Js on Wikimedia Commons, each public domain or
  plain CC BY, with what each is for: *Endeavour*'s launch in 1934 and her departure in 1937 (Agence Rol and Agence
  Meurisse, public domain via the Bibliothèque nationale de France), *Yankee* in 1935 (public domain), and modern
  photos of *Velsheda* and *Ranger* (CC BY: Phil Whiston, Chris Parfitt, Don Ramey Logan, David Blaikie).
  `Tools/shipkit/fetch_refs.py` downloads them into the git-ignored `Data/Reference/raw/ships/Bluebonnet/`, reading
  each file's licence on Commons first and refusing anything that isn't public domain, CC0 or plain CC BY. They are
  for looking only: nothing is traced or measured off them into the model. If one is ever shown in the docs, its
  photographer gets a credit.
* **Left out:** most of the Commons photos of the modern Js are CC BY-SA, which the shipkit doesn't take. The 1930
  *Enterprise* lines scan on archive.org, and the class and museum sites, are blocked from the cloud; *Bluebonnet*'s
  lines are our own design anyway, so nothing waits on them.

## How the hull is made

`Tools/shipkit/jclass/lines_bluebonnet.json` is the design: a handful of curves along the length, in metres, in the
game's frame (X forward, Y starboard, Z up, origin on the centreline at the middle of the load waterline).

* **The canoe body's centreline:** the counter's underside, the run, the bottom, the forefoot and the spoon bow.
* **The keel's outline below it:** a straight raked leading edge, a straight bottom 8 m long with 37 cm of drag (deeper
  aft), and the post the rudder hangs on, raked about 51 degrees from the horizontal, with rounded corners. The leading
  edge is drawn tangent to the forefoot (`loft.leading_edge_tangent` finds the point), so the keel and the stem are one
  convex line crossing the waterline at about 20 degrees, with no knee between them. Under the counter the post meets
  the canoe body with a hollow (the fillet); at the forefoot there is none.
* **The sheer, the deck edge's half-breadth, and the "knuckle":** each section's shoulder, on the waterline amidships
  and rising up the section in the overhangs.
* **A few shape factors along the length:** the floor's width and deadrise, the bilge's place, the topsides' flare.

`loft.py` (plain numpy and scipy, no Blender) turns them into a surface:

* **Each curve is faired like a batten.** It may miss its key points by a set tolerance (1-2 cm for heights and
  breadths, half a degree for the deadrise; listed in the json), with its ends held, and it bends with the least
  change of curvature that allows. A spline forced exactly through hand-placed points bends to meet each one. On a
  hull that shows as a ripple in the reflections every few metres, and the faired curves have none.
* **Each station's section is a control polygon** built from those curves: the keel's bottom, two points up each side
  of the keel and its root, then the floor, bilge, knuckle, topside and sheer. Where there is no keel (the forefoot
  and the counter) the keel's points sit together on the centreline, a stem bar's width out, so every section is the
  same family of curves.
* **The hull is the bicubic B-spline surface on those polygons** (72 rows along the length). A B-spline surface is
  smooth to the second derivative everywhere, so a fair net gives a fair hull. The keel's points run down its sides,
  and the surface turns them into the garboard's hollow on its own.
* **The keel's thickness** is a foil section between its leading edge and the post at each height: 0.54 m thick at
  the bottom (the lead), 0.96 m at the root, 14 cm at the post, and the stem bar's 7 cm forward of the keel and
  under the counter. Along the bottom 0.6 m the lead's casting stays blunt out to the toe and the heel
  (`bottom_blunt`), so the keel ends in a broad rounded bottom, not a knife edge. Where the keel is shallow (the
  leading edge's top, the post's) its thickness eases to the stem bar's, so the bar runs on into it with no swelling.
* **The aft rows lean to the transom's rake,** so the surface's aft edge lies in the transom's plane, and the transom
  closes it there. The forward row is the stem head itself.

`build_jclass.py` makes the Blender objects (`Hull`, `Transom`, `DeckPlaceholder`) and writes `jclass.blend`,
`jclass.obj` and `build.json`. The hull, transom and deck together close into one watertight shell with outward
normals: `build.json`'s `shell` entry counts open, shared-by-three and flipped edges and degenerate faces (all 0) and
the enclosed volume, and the build fails if they don't close.

## Hydrostatics, weights and balance

`loft.py` integrates the hull from 400 station cuts (`baseline/hydrostatics.json`):

| | |
| --- | --- |
| Centre of buoyancy | 0.68 m aft of mid-waterline (52.6% of the waterline from the bow), 1.03 m below it |
| Prismatic and waterplane coefficients | 0.49, 0.74 |
| Block coefficient | 0.21 on the full 4.52 m draft, keel included (the canoe body alone on its own depth is near 0.4) |
| Wetted area | 192.6 m² (2,073 sq ft) |
| Displacement-length ratio | 248 (*Ranger*: 252 by her published figures) |
| Waterplane | 117.9 m², its centre 0.52 m aft of mid-waterline |

**Weights.** The size card's weight split for a riveted steel J (long tons): lead keel 92, hull steel and frames 30,
deck and deckhouses 7, mast, boom and rigging 8.5, sails 3, winches and hardware 3.5, accommodation 6, crew and stores
5: 155 in all. The lead's place comes from the hull, the other parts' centres are estimates (in the size card).

* **The lead fits in the keel:** 93.5 t is 8.24 m³ of lead. It stops at the rudder's stock line (`rudder_chord`, 1.7 m
  forward of the post: the rudder is the keel's after part) and fills the keel forward of it below 2.72 m under the
  waterline, the bottom 1.80 m of the keel. Its centre is 0.90 m aft of mid-waterline and 3.32 m down. Slice 2 casts
  it there.
* **Fore and aft:** the centre of gravity is 0.08 m aft of the centre of buoyancy, which would trim her about 7 cm by
  the stern over the waterline's length. Slice 2 levels her when it sets the casting.
* **Stability:** the centre of gravity is 1.10 m below the waterline and the metacentre 0.79 m above it, so GM is
  1.88 m. That is upright stiffness only; slice 13 works out her stability at heel for the physics.

`baseline/sections.json` has the hull's half sections at 31 stations from the transom's foot to the stem, each 24
points evenly along the girth from the centreline (keel or counter) to the sheer, with the sheer height and the load
waterline's half-breadth, and the hull's volume and centre of buoyancy at the top. It is the format of the maxi's
`Tools/boats/maxi/sections.json`, which slice 13 turns into her physics hull; unlike the maxi's, the sections
include the keel, because a J's keel is part of her hull surface.

## Checks

Run from the repo root, with Blender's Python (pip `bpy`) for the build, the renders and the fairness check:

```
python3 -I Tools/shipkit/fetch_refs.py Tools/shipkit/jclass/refs.json Data/Reference/raw/ships/Bluebonnet
python Tools/shipkit/jclass/loft.py <out>                 # hydrostatics.json, sections.json, lines.png
python Tools/shipkit/jclass/build_jclass.py <out>         # jclass.blend, jclass.obj, build.json
python3 -I Tools/shipkit/jclass/rule_check.py <out>/build.json
python Tools/shapeloop/fairness.py <out>/jclass.blend <out> --object Hull
python Tools/shipkit/jclass/render_jclass.py <out>/jclass.blend <out>/renders --res 1200
python Tools/shipkit/jclass/docs_jclass.py <out> docs/jclass-1/baseline
```

`rule_check.py` prints the rating and every size against its target, and exits 1 if any fails. Slice 1's run:

```
Rating 75.71 ft (L 85.39 ft, S 7500.0 sq ft, D 5435.0 cu ft = 155.3 long tons)
  ok   rating               75.71 ft        (limit 76.0)
  ok   draft limit          14.83 ft        (limit 15.0)
  ok   length overall      131.00 ft        (target 131.0)
  ok   load waterline       85.39 ft        (target 85.0)
  ok   beam                 21.51 ft        (target 21.5)
  ok   draft                14.83 ft        (target 15.0)
  ok   displacement        155.29 long tons (target 155.0)
  ok   bow overhang         18.77 ft        (target 19.0)
  ok   stern overhang       26.84 ft        (target 27.0)
  ok   least freeboard       4.38 ft        (target 4.2)
PASS
```

`render_jclass.py` frames the yacht from her own size (the shape loop's `render_set.py` frames J/22-sized boats):
clay views from the side, above, the quarters, end-on and below; zebra views (stripes in a mirror hull: a fair
surface shows smooth bands); and two views afloat on a flat sea, the first from a dinghy's eye height. They are in
`baseline/` as JPEGs, with the lines drawing (`lines.jpg`) and the contact sheet (`sheet.jpg`): `docs_jclass.py`
copies the build's json files there and writes the images under 300 KB each (docs images are plain git, not LFS).

**Fairness** (`Tools/shapeloop/fairness.py`, 10 waterlines and 10 stations): 18 inflections and 20 kinks, 17 of them
firm (round 1's hull: 18, 19 and 16). Every one is where the design turns on purpose:

* **The stations through the keel** (x -7.1 to +8.5 m): 2 inflections and 2 kinks each. The wineglass section
  reverses twice, into the garboard's hollow and out again at the bilge, and turns hard at both.
* **The station by the post's top** (x -11.0 m): 1 kink, where the counter's V meets the post; no inflection.
* **The stations in the bow overhang** (x +12.4, +16.3 m): 1 inflection each, convex at the forefoot and flaring
  hollow to the sheer; 1 firm kink at +12.4 m, 2 soft ones at +16.3 m.
* **The counter's stations** (x -18.8, -14.9 m): 1 kink each, the bilge turn; no inflection.
* **The waterline 0.55 m above the keel's bottom** (z -4.0 m): 1 kink, where it turns round the lead's blunt heel.
* **The waterlines through the keel** (z -2.7 to -1.4 m): 1 or 2 inflections and at most 1 kink each, where the
  waterline runs off the keel's side onto the canoe body at the leading edge and the post.
* **The waterline at z -0.7 m:** 1 inflection and 1 soft kink where it wraps round the top of the post.
* **The waterline 1.8 m up** cuts only the ends of the two overhangs (4 m of line): 1 inflection there.

## Blind review

A round passes when two of three fresh reviewers prefer the new hull. Each reviewer sees matched views of two hulls,
labelled X and Y at random in each view, with period photos for the look, and is not told which is the newer.

**Round 1: failed, one of three.** It compared round 1's hull with the same design before the batten fairing and
the floor fix, in eight views (three zebra, four clay, the lines drawing) beside the 1934 launch photo. Two reviewers
preferred the older hull, one of them for a pinch at the stem head; all three were unsure. The separate QA review
found the pinch's cause: near the stem head the floor's control point came from a division by a near-zero width, and
one control row dropped 12 cm. The floor now starts at the stem bar's face, and the loft refuses any section polygon
that folds back. All three reviewers agreed on what a J of 1934-37 looks like, and round 2 drew to it: a keel
tapering from about a metre thick at the root, with drag; one convex line from the keel to the stem, with no hollow
in the forefoot; the bow crossing the waterline at about 20 degrees; more spring in the sheer at both ends; the
counter's underside higher and rounder; near-upright topsides with a rounder bilge.

**Round 2: passed, three of three.** Round 2's hull against round 1's lines lofted with the fixed code, in eleven
views (six clay, three zebra, afloat, the lines drawing) beside *Endeavour*'s launch in 1934 and a photo of her in
1937. View by view the reviewers preferred the new hull 7 to 4, 8 to 2 (one view even) and 8 to 3. All three named
round 1's knee in the forefoot, where the bow overhang met the keel's leading edge, as the worst fault in either hull.
To balance the new keel's lead, round 2 also moved the keel forward (its bottom now runs from 1.9 m forward of
mid-waterline to 6.0 m aft) and the canoe body's deepest point aft.

What all three still saw in round 2's hull, and what this PR did about it after the round (checked by the build, the
rule check, the fairness check and the renders; the QA review below looks at the final hull):

* **The keel's bottom closed to a knife edge at the heel.** The lead now stays blunt along the bottom 0.6 m, out to
  the toe and the heel, and the bottom is 0.54 m thick, so the keel ends in a broad rounded bottom like
  *Endeavour*'s on her cradle. The waterline that turns round the heel gains a kink for it (above).
* **A spindle-shaped swelling on the stem near the waterline,** where the thin stem bar met the keel's thicker
  leading edge. The keel's thickness now eases to the bar's where the keel is shallow.
* **A hard bilge shoulder about 40% of the way down** (two of three). The bilge is back halfway toward round 1's
  slacker turn.
* **The post meets the counter in a tight hollow.** The hollow is smaller (`fillet` 1.0 m, from 1.4 m). Slice 2 hangs
  the rudder on a straight post line up to the counter, as on the Js.
* **The bow is one straight line from the keel to the stem head, with no spoon.** Kept, see the known gaps.
* **Small isolated lenses and slivers in the zebra on the topsides** (both hulls). The near-upright topsides reflect
  the stripes edge-on, where the smallest change of slope moves a band; the fairness check finds no ripple there.

## QA review

A separate critical review after round 1 checked the code, the numbers and the renders. Besides the stem head's
pinch it found that the closed-shell claim left out the deck (the build now checks hull, transom and deck together
and fails if they don't close, and `jclass.obj` includes the deck), that the docs called her about 1% deep when she
floats light, and that the block coefficient needed its draft named. All fixed here.

QA OF THE FINAL HULL PENDING

## Known gaps

* **No rudder yet** (slice 2): the rule check counts it as a 35 cu ft allowance. Slice 2 measures it.
* **The bow is straight, with no spoon.** With the waterline's forward end, the 19 ft bow overhang, the stem
  head's 2.4 m and the keel's toe (where the lead balances) all set, the line between them can only bend a little. A
  spoon needs a higher stem head, or the toe further aft, which puts the lead aft or the waterline and the rating up.
  *Ranger*'s bow of 1937 was straight like this; *Endeavour*'s had more spoon. Bean can choose.
* **She floats about 2 tons light for her estimated weight.** The moulded hull displaces 154.3 long tons and the
  weights add to 155.0, but the rudder (1 ton) and the plating (about 8 mm over 193 m², 1.5 tons) add buoyancy, so
  she would float about 2 cm high. Slice 2 sets the plating and rudder, re-weighs her and trims the lead.
* **The rule's own length measurement** (with the overhangs) isn't modelled: L is the waterline. Bean can open the
  rule text on a machine that reaches the archive sites if he wants it checked.
* **The weights' centres are estimates** until each slice builds its part.
* **The deck is a placeholder** (slice 3).

## Files

| File | What it is |
| --- | --- |
| `Tools/shipkit/jclass/specs_bluebonnet.json` | the size card: targets, rule, published sizes, weights |
| `Tools/shipkit/jclass/rule_check.py` | the rule and size check every slice runs (plain Python) |
| `Tools/shipkit/jclass/refs.json` | the reference photos and what each is for (licence-checked by `fetch_refs.py`) |
| `Tools/shipkit/jclass/lines_bluebonnet.json` | the hull's design curves and their fairing tolerances |
| `Tools/shipkit/jclass/loft.py` | the hull surface, hydrostatics, weights, sections and lines drawing |
| `Tools/shipkit/jclass/build_jclass.py` | the Blender build: `jclass.blend`, `jclass.obj`, `build.json` |
| `Tools/shipkit/jclass/render_jclass.py` | clay, zebra and afloat renders framed for a 40 m yacht |
| `Tools/shipkit/jclass/docs_jclass.py` | copies a build's checks and renders into `baseline/` as small JPEGs |
| `Tools/shipkit/jclass/sections_jclass.json` | her parts for the shape-loop tools |
| `docs/jclass-1/baseline/` | this hull's build stats, hydrostatics, fairness, sections, lines drawing and renders |
