# Shipkit 1: the frigate's hull lines

The frigate *Commonwealth* is our own 44-gun heavy frigate with her 1797 look, based on the Humphreys design of USS
*Constitution*. Plan and Bean's decisions (Nov 12 2026): <https://claude.ai/artifact/8y6hW8vHjjUPJRovJEuxY7>. This
page covers slice 0 (references and tools) and slice 1 (hull lines). It is post-slice art: nothing here is imported
into Unreal or wired into the game yet.

## What slice 1 builds

The moulded hull (the frame's outside, inside the planking) and the backbone (keel, deadwood, sternpost and stem), with
a flat placeholder deck so renders read as a ship. The mesh is 596k triangles: the plan's 150k for this slice was a
starting point, and Bean lifted the budget for quality. The hull is dense so that the fairness checks see the
surface, not the facets. Planking, wales, gunports and the rudder come in slice 2, the head and stern decoration in
slice 9, and the decks in slice 7.

| Measure | Model | Published (US Navy) |
| --- | --- | --- |
| Length on the load waterline | 174.4 ft | 175 ft |
| Beam at the load waterline | 43.4 ft | 43 ft 6 in |
| Widest moulded beam | 43.4 ft | |
| Rabbet to load waterline, midships | 18.1 ft | |
| Keel bottom to load waterline, aft | 21.5 ft | 21-23 ft |
| Length on the sheer | 188.0 ft | |
| Moulded displacement | 2,076 m³, 2,095 long tons | about 2,200 long tons at 21 ft (designed) |

The moulded volume leaves out the planking and copper. They add about 3-4%, which brings the model to about
2,170 long tons. The model floats at the 1927 drawing's load waterline.

Before the scan's two scales were found (see "Registration"), the same drawing gave 44.1 ft of beam, 22.6 ft of draft
and 2,299 long tons. The corrected scale brings all three onto the published figures without any fitting to them.

## Sources and licence

* **Lines:** the 1927 lines plan of USS *Constitution* ("Plan VIII", F. Alexander Magoun, MIT), US National Archives
  record 75841374, in Wikimedia Commons' 3840 px rendering. Commons lists it as a National Archives record in the
  public domain, so it is fine for a game we sell. Every reading is in pixels on that rendering.
* **Other drawings:** `Tools/shipkit/frigate/refs.json` lists 22 National Archives drawings on Commons with what each
  slice takes from them: the 1817 draught, the deck plans, the midship sections and the inboard profile. Each is
  recorded there as public domain. `Tools/shipkit/fetch_refs.py` downloads them into the git-ignored
  `Data/Reference/raw/ships/Commonwealth/`. Before each download it reads the file's licence on Commons and refuses
  anything that isn't public domain, CC0 or plain CC BY (no NC, ND or SA). 17 have been fetched so far
  (`cloud_copy_3840px`); slice 1 uses only the lines plan.
* **Elsewhere** (`refs.json`, listed with how each may be used):
  * the USS Constitution Museum's modeller resources: copyrighted, so we only read and measure them, and the site is
    blocked from the cloud;
  * Marquardt's *Anatomy of the Ship* (Osprey 2017): a paid book, about $39, for Bean to decide;
  * Steel's *Elements and Practice of Rigging and Seamanship* (1794): public domain, for slices 4-6;
  * HMS *Trincomalee*'s Matterport tour: for looking only;
  * the Smithsonian's gunboat *Philadelphia* scan: CC0.
* The drawings stay out of the repo. Only the numbers read from them and the check overlays are kept here.

## How the hull is made

`Tools/shipkit/frigate/offsets.json` holds the readings, each traced from the scan:

* waterline half-breadths at 14 rows, and the waterline ends;
* the profile: keel, rabbet, stem, sternpost, stern face and sheer;
* the body plan's sections above the waterline.

`loft.py` (plain numpy and scipy, no Blender) turns them into a surface. `build_frigate.py` makes the Blender objects
(`Hull`, `Transom`, `Backbone`, `DeckPlaceholder`).

* **Below the load waterline A,** each waterline A-F is a faired spline along the ship through the read rows (0.9 px
  RMS from them, 2.7 px at most). It ends at the keel's half siding on the stem and sternpost rabbets.
* **Midships,** at stations 3-5, the half-breadth plan runs waterline B into A or C. There B comes from the body plan's
  section, as a ratio to the section's own width at A (the way the topsides are made). Every other line is read at the
  centre of its ink, at the station itself.
* **Above A,** each row's width at A is carried up by the body plan's section shape. The shape is used as a ratio to
  the section's own width at A, so the two views meet exactly at A, and it is faired across the stations at each
  height. Going up, the width eases to the body plan's own width at the top of its sections (up to 1.8%: see "Where
  the drawing disagrees with itself").
* **Each section** is one C2 batten in height, through the rabbet, the waterlines and the levels above A. (C2 means
  the curvature changes smoothly, with no corners or flat spots.)
* **The stern:** aft of station 9 the side has a knuckle at the wing transom, 5.6 ft above A.
  * Below the knuckle, the waterlines close on the sternpost (a round tuck).
  * Above it, the counter runs aft to the stern face.
  * The two pieces meet at x = 611 px and blend into one curve by x = 702.5 px.
  * Aft of the wing transom's corner, each counter section starts on the stern face itself. That way the waterline cuts
    there have no crease where a level ends.
* **The backbone** is a plate of the keel's siding. Its inner edge follows the side's own boundary, so there is no gap
  between the two: the stem rabbet, the bottom line between waterline F's ends, and the sternpost rabbet.

### Registration: where each view sits on the scan

The 1927 sheet is three drawings on one folded, scanned page. They are not quite square to the scan or to each other.
`Tools/shipkit/scanreg.py` reads the registration in `drawing_1927.json`. `loft.py` uses it to map each reading into
the half-breadth plan's frame, and `lines_check.py` uses it to map the built hull back onto the scan.

* **Scale: the scan is 5.3% taller than it is wide.** Across the sheet a foot is 11.1 px: the scale bar, the body
  plan's beam and the load waterline's length all agree. Down the sheet it is 11.69 px, 1.053 times as many. The
  evidence is the ratio between the two directions:
  * The half-breadth plan draws the two buttocks 92.6 and 185.0 px from its centreline, measured down the sheet. The
    body plan draws them 87.8 and 175.5 px from its own, measured across. Both give 1.054.
  * 27 crossings of waterlines and stations, read in both plans, give a median of 1.05.
  * The ship's frame keeps the half-breadth plan's own pixels: lengths across the sheet, half-breadths and heights
    down it. The body plan's half-breadths, read across the sheet, are scaled by 11.69 / 11.1.
  * The QA review after round 3 found this. Until then one scale was used. That made the ship 5% too deep, 5% too
    wide toward the ends and 1.4% too wide midships, and made the views seem to disagree by up to 6% (see below).
* **Half-breadth plan:** its centreline is read every 50 px. The first version of the table read the keel's siding
  line instead of the centreline near the stern. That put the quarter's waterlines 5 px outboard in the check, which
  reviewers in the first blind round saw as a "quarter bulge".
* **Sheer plan:** its station lines sit 8.6 px aft of the half-breadth plan's at station 9 and 14.6 px aft at station
  1, and they lean slightly.
  * Each profile reading is mapped through the station lines where they cross A, and through their tilt.
  * With this mapping, the sheer plan's stem and sternpost rabbets meet the half-breadth plan's waterline ends within
    2-3 px. Before it they were 6-16 px apart.
* **Body plan:** turned 0.85 deg on the scan (its waterline A drops about 7 px across the view), with the centre at
  (3130.65, 1136.95). Readings taken against a square frame are mapped through the turn. Its waterlines B-F land
  within 1 px of their heights in the other two views.

## Checks

Run from the repo root, with Blender's Python (pip `bpy`) for the build and the shape-loop tools:

```
python3 -I Tools/shipkit/fetch_refs.py Tools/shipkit/frigate/refs.json Data/Reference/raw/ships/Commonwealth
python Tools/shipkit/frigate/build_frigate.py <out>
python Tools/shipkit/lines_check.py <out>/frigate.obj Tools/shipkit/frigate/drawing_1927.json \
    Data/Reference/raw/ships/Commonwealth/USS_Constitution-_Sheer_Plan_-_Body_Plan_-_Lines_-_NARA_-_75841374.jpg <out>/check
python Tools/shapeloop/fairness.py <out>/frigate.blend <out> --object Hull
python Tools/shapeloop/render_set.py <out>/frigate.blend Tools/shipkit/frigate/sections_frigate.json <out>/renders
```

`lines_check.py` cuts the built mesh with the drawing's own planes and measures how far each cut lands from the
nearest ink. It works on the mesh, not on the loft's tables. The results and overlays are in `baseline/` (`lines.md`,
`overlay_*.jpg`), along with `fairness.json`, `build.json` and the clay renders.

How the measure counts:

* The outline is thinned to one point per 2 px, so it counts like the other lines.
* The buttocks are scored only below A, and only where the drawing has them. The drawing leaves both out between
  stations 6 and 3, where they run flat along the floor.
* The overall figure is over every sample.

**Lines:** median 0 px from the ink, 94% of 11,963 samples within 2 px (2 px is about 2 in). Round 3's
winner, measured the same way on the corrected scale, scores 33%: most of its misses were the scale.

| Lines | Within 2 px | Notes |
| --- | --- | --- |
| Profile outline | 96% | keel, stem, sternpost, counter and sheer |
| Waterlines A, B, D, E, F | 95-99% | |
| Waterline C | 86% | up to 4 px off between stations 7 and 5, and between 3 and 1 |
| Body plan stations 1-9 | 84-100% | |
| Buttocks, 8 ft and 16 ft | 84%, 81% | below A, where drawn (see below) |

The scores count distance to the nearest ink, so where two drawn lines are close together a score can flatter or
punish a line. Read them with the overlays.

**Fairness** (`Tools/shapeloop/fairness.py`, 10 waterlines and 10 stations): 13 inflections and 15 kinks, 10 of them
firm.

* **The firm kinks:**
  * where the waterlines below A end on the stem rabbet (x 2210-2340 px: the forefoot and the cutwater);
  * on the aftmost station cut, where it crosses the tuck and the wing transom's knuckle (by design);
  * at A just forward of where the tuck and the counter meet (x 623 px).
* **The 5 soft ones:** four more where the waterlines near A meet the stem, and one on the station cut at x 827 px near
  waterline B.
* The second QA pass's fixes (below) took the count from 22 to 15: six of the seven were on stations 3-9.

## Where the drawing disagrees with itself

A hand-drawn lines plan is not perfectly consistent between views. The half-breadth plan is the master at A and
below. The body plan gives the shape above A, and waterline B midships, where the half-breadth plan runs it into A or C.

Most of what earlier rounds took for disagreement was the scan's stretch, and the rest was mostly how the lines were
read. Read with one scale, the body plan came out up to 12 px narrower than waterline A, and the buttocks missed
their ink by 5-15 px. With the two scales, and every line read at the centre of its ink, what is left is small:

* **Waterline A against the body plan.** At A the body plan's sections are 0-3.9 px (0-1.8%) wider than the
  half-breadth plan's waterline A at the same stations:

  | Station | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | Body plan wider at A (px) | 0.3 | 1.5 | 3.6 | 1.1 | 3.9 | 1.3 | 1.0 | 2.5 | 3.0 |

  Above A the side eases from the half-breadth plan's width to the body plan's, so the topsides end on the body plan's
  lines. The body plan draws stations 3 and 4 as one curve on its right half, so station 3's figure compares the
  half-breadth plan's station 3 with that curve.
* **The midship rows were first read off the outer edge of the body plan's lines.** That needed a 1.036 scale to land
  on the half-breadth plan, which looked like a 1-2% disagreement. They were also placed 9 px forward of their
  stations, and one of them had read the 16 ft buttock (a straight line at 185 px) as waterline E, 5 px inside E.
  The second QA pass found all three; the rows are now read at the line centres, at the stations.
* **The rabbet in the body plan.** The body plan takes every section down to one point on the keel, about 207 px
  below A, and draws the keel at one depth: the midship keel. The sheer plan's rabbet has drag. It runs from 227 px
  below A at station 9 to 203 px at station 3, about 2 ft. The hull follows the sheer plan. So in the body plan its
  sections at stations 5-8 run on below the drawn meeting point (4 px at station 5, 18 px at station 8), and those
  forward of station 4 end 4-8 px above it. Station 9 ends higher, on the deadwood.
* **The 16 ft buttock forward:** between stations 3 and 2 it runs 1-3 px above its ink, at waterline E's height.
  Waterline E is on its own line there, so the sheer plan and the half-breadth plan differ by about that much at this
  spot.

## Blind review

Each round packs both candidates' overlays on five views (body plan, half-breadth aft and forward, sheer stern and
bow) for three fresh reviewers who see only the images. The candidates are labelled X and Y at random for each view.
The tally is per view. A round passes when two of three reviewers prefer the new hull overall and the views agree.

* **Round 1** (the first loft against the corrected stern and counter): 2 of 3 preferred the new hull for its stern
  and counter. All three flagged the quarter's waterlines bulging outboard, which turned out to be the registration
  error above.
* **Round 2** (re-registered readings against round 1's winner): void.
  * Reviewers preferred the new hull's half-breadth plan and stern, but flagged its sternpost and stem outlines as
    missing. The hull was whole: the check drew every second outline pixel in scan order, which drops either the stem
    or the sternpost at each height. Fixed.
  * The same round found the topsides at station 1 too full.
* **Round 3** (the re-registered hull against round 1's winner, both drawn by the fixed check): passed.
  * All three preferred the new hull on four views: the body plan (the topsides at the rail), the half-breadth plan aft
    (waterline A into the sternpost), and the sheer plan's stern and bow. They called the forward half-breadth plan a
    tie. That is 12 of the 12 decided views.
  * They noted a small wobble in waterline A near the stern (within 2 px of the ink), pinholes in the check's fill
    under station 9 (now closed), and the missing head (slice 9).
* **Round 4** (the first hull on the two scales, against round 3's winner): passed. All three reviewers preferred
  the new hull in all five views, 15 of 15.
  * They saw round 3's winner as a waterline-spacing too full in plan (50-60 px wide at E and F) and its keel 25 px
    deep at the stern. Both are the 5% stretch, now that its metres are drawn back on the true scale.
  * On the new hull they noted the body plan's aft station tops stopping up to 30 px below the drawing's top line, the
    forward tops matching it, and the head ending in a straight cut. The aft tops end at the sheer: the drawing's top
    line there is the quarterdeck's rail, on the bulwarks (slice 2). The head is slice 9.
* **Round 5** (this hull, after the second QA pass's fixes, against the hull that went into that pass): split, so
  it did not pass by the rule above.
  * Per view, this hull won the half-breadth plan aft (2 to 1), the half-breadth plan forward (2 to 0, one tie) and
    the sheer plan's bow (2 to 0, one tie). The older hull won the body plan (3 to 0) and the sheer plan's stern (1
    to 0, two ties). That is 6 views to 5, with 4 ties.
  * All three reviewers named the older hull overall, for the body plan. There its midship sections sit a pixel or
    two further out, in the middle of the drawn sections' ink, where this hull's run along the ink's inner edge.
    That is the gap between the two views at A (above). The older hull got there by reading the midship rows off
    the outer edge of the body plan's lines and scaling them by 1.036.
  * This hull is kept. It follows the half-breadth plan, the master at A and below, and it scores better on the
    drawing's own lines: 94% of samples within 2 px against 93%, with waterline C at 86% against 81% and station 3
    at 97% against 88%. Splitting the difference between the two views at A would move the midship sections out
    about 1 px. That is left for slice 2, whose planking moves the outer surface out by its own thickness anyway.
  * All three flagged the body plan's aft sections running on below the point where the drawn sections meet the
    keel. That is the drawing again (above): its body plan takes every section down to one rabbet, while the sheer
    plan's rabbet drops toward the stern.

## Known gaps

* **The wing transom's underside is a flat shelf.** It runs forward from the transom: 2 ft at 4 ft off the
  centreline, 4.7 ft at 8 ft and 8.6 ft at 12 ft. The tuck's top waterline runs from the sternpost out to the side,
  while the counter's foot runs straight across. On the real ship the tuck fills out under the wing transom, so only
  the transom's own thickness shows. Slice 9 (the stern) fixes it,
  with the 1817 draught's stern view.
* **The bow's top forward of station 1 is up to 1.5 ft too narrow.** The body plan has no sections there, so the side
  flares toward the half-breadth plan's rail line. The two bow rows were set for a 14 px rail overhang, which is what
  stations 1 and 2 measured under the single scale. With the two scales those stations meet the rail line within
  2 px, but from x 2240 to 2360 px the side at the sheer runs 3-17 px inside it. Raising the bow rows in place bends
  the station fairing between stations 2 and 1 (5 px in), so the refit waits for slice 2, which builds the bulwarks
  and rails.
* **The head is missing:** above the waterline, the drawing's fore line is the knee of the head (slice 9). The model's
  stem keeps its width at A (40 px, 3.6 ft from the rabbet to the fore face) up to the stem head.
* **The deck is a placeholder** (slice 7). The bulwarks and rails are slice 2 (`bulwark_top_z_px` and `rail_hb_px` are
  read already).

## Files

| File | What it is |
| --- | --- |
| `Tools/shipkit/fetch_refs.py` | downloads a ship's reference drawings from Commons (licence-checked) |
| `Tools/shipkit/scanreg.py` | the scan registration: views to the ship's frame and back |
| `Tools/shipkit/lines_check.py` | the lines check: the built hull's cuts against the drawing's ink |
| `Tools/shipkit/frigate/refs.json` | the frigate's reference drawings and what each slice uses |
| `Tools/shipkit/frigate/offsets.json` | every reading from the lines plan |
| `Tools/shipkit/frigate/drawing_1927.json` | the lines plan's registration and scales |
| `Tools/shipkit/frigate/loft.py` | the hull surface and mesh, from the offsets |
| `Tools/shipkit/frigate/build_frigate.py` | the Blender build: `frigate.blend`, `frigate.obj`, `build.json` |
| `Tools/shipkit/frigate/sections_frigate.json` | the frigate's sections for the shape-loop tools |
| `docs/shipkit-1/baseline/` | this hull's lines check, overlays, fairness, build stats and clay renders |
