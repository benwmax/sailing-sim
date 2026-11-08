# Rope clutch (Nov 8 2026)

Bean's hardware reference sheet asked for each part on it to go through the part detail loop ([README](README.md)).
This is the "Rope Jammer" tile: a single lever rope clutch, the kind that holds a halyard or reef line on a cabin top so
its winch can be used for something else. It rebuilds the kit's `Clutch`, which was a tapered black box with a flat
handle.

The builder is in its own file, `Tools/boatkit/bk_part_clutch.py`, which `bk_parts` loads at its end (the shared loader
block): its `@part("Clutch")` replaces the old box. Card: `Tools/boatkit/partloop/parts/clutch.json`.

Bean's sheets (not in the repo: they show Bean's product photo): `part-detail-loop/clutch_before_after.jpg` and
`part-detail-loop/clutch_photo_vs_render.jpg` in the project files.

## What it is now

Round 7, 126 x 38 x 72 mm, 8,430 triangles, 5 material slots (budget 20,000 and 8):

- Two satin charcoal side plates, tallest at the grip end and sloping down to the hinge end, each edged with a bright
  strip and held by four socket screw heads.
- A lever along the top, hinged at the low end, with a chunky ribbed grip block turned down over the mouth.
- An open mouth at the tail end showing a black cam with bright teeth above a red flared line guide.
- A red release button in a recess, a lock window with two ticks and a moulded diagonal groove on each plate.
- The line's bore runs straight through, 11.5 mm off the deck; a flush black guide at the load end.
- The made-up TERNWAY maker's plate on the lever.

Sockets: `LineIn` (load end, +X), `LineOut` (tail end, under the grip), `Grip`, `Hinge`, `BoltFwd`, `BoltAft` (79 mm
apart, the catalogue's fixing centres).

## The checks

| Round | Size (L x W x H) | Photo outline | Features | Blind review |
|---|---|---|---|---|
| Before | 139 x 50 x 67 mm (length +11%, width +38%) | 89% | 1/11 | lost 0 of 3 to r4; all three called it the wrong part ("junction box", "stapler", "deck organiser cover") |
| r1 | 125 x 40 x 63 | 81% | | not reviewed (a steep wedge, low end 26 mm) |
| r2, r3 | 125 x 40 x 64 | 86.5% | | r3 lost 0 of 3 to r4 (r2 to r3: plates from white aluminium to satin charcoal) |
| r4 | 126 x 40 x 66 | 86% | | won 3 of 3 against before (confidence 5, 5, 5) and 3 of 3 against r3 (3, 4, 3) |
| r5 | 126 x 40 x 71 | 82% | | won 3 of 3 against r4 (4, 4, 4) |
| r6 | 126 x 40 x 72 | 82% | 11/11 | won 3 of 3 against r5 (2, 3, 2); every reviewer ticked all five hand-judged features |
| **r7** | **126 x 38 x 72** | **82%** | **11/11** | r6 narrowed 2 mm (r6 measured 40.3 mm wide with its screw heads); not re-reviewed |

Catalogue sizes: 125 mm long (Spinlock XAS 6-12 single 125 mm, Lewmar D1 single 126 mm), 62 to 72 mm high, 32 to
40 mm wide. All three pass on r7 (+1%, +9%, +6%).

**The outline check does not pass (82% against 85%), and that is a known conflict, not an oversight.** There is no free
square-on side photo of a lever clutch, so the outline is matched by angle on Bean's three-quarter photo
(`photo_outline.py`, as for the pad eye). That match rewards a box: the old box scores 89%, and the closest round to a
pass (r2 to r4, 86%) has nearly parallel plates. All six reviewers of r4 and r5 asked for a clear wedge, tall at the
grip end, and they are right by eye against the photo; the photo's own camera angle also sits outside the tool's grid
(round 7's best match, azimuth 210 and elevation 40, looks down on the part far more steeply than the photo does). The
wedge rounds won every blind review, so round 7 keeps the wedge.

What changed, round by round:

- r1: the clutch's real parts instead of a box: side plates, strip, lever and hinge, mouth with cam, guides, release
  button, lock window, screws, groove, maker's plate.
- r2: low end raised and the tail end raked back (outline 81% to 86.5%).
- r3: side plates satin charcoal (the cloud preview turns aluminium white, which hid every detail).
- r4: the grip turned down over the mouth, a bigger release button near the mouth, bigger screw heads.
- r5: the wedge back (low end 39 mm), line lower (15 to 11.5 mm), a satin grip block with ribs, a stainless toothed cam,
  the load end's guide flush (reviewers saw a "knob"), a bolder longer groove.
- r6: a black cam with bright teeth and a bigger red guide at the mouth's face (all-black and all-stainless cams both read
  as a smooth roller).
- r7: 36 mm across the plates.

Still different from the photo (r6 reviewers' shared notes, for a later round):

- The lever top is a flat bright slab; the real one is a crowned grey moulding whose grip rolls over the end as one
  piece, not a separate block.
- The plates are flat sheets with sharp corners; real ones are thicker castings with rounded corners and a raised rim.
- The red guide in the mouth is still small; the photo's red flared entry is the first thing you see.
- The groove is a thin slot; the real one is a broad moulded channel, with a raised indicator window.
- No dark base strip along the bottom.
- The preview materials make light metal too white (the same for every round and for the old part).

## Not done here

- **In the game**: the cloud built and exported the kit's clutch parts with the `bpy` module (`build_kit.py --only
  Clutch,ClutchBank`: Clutch 8,430 triangles, light copy 2,042). `Inputs/boat-kit/kit.json` is left alone, as for the
  other parts: on BEN-PC, after Bean's "resume", `scripts\windows\make-boatkit.ps1 -Import` builds the whole kit and
  copies it. No layout places a `Clutch` yet, so the close-up is the gallery (`-SailingGallery=SM_Kit_Clutch`).
- **On the boats**: a J/22's halyards usually lead aft from the mast to cabin-top clutches or cam cleats; the J/22 hero
  layout has neither yet. Placing a bank of these on the cabin top (with live halyards) is its own step.
- **ClutchBank** still uses the old box shape per line; it should be rebuilt from `_clutch_parts` side by side.
- The `Clutch` sizes in `bk_parts.SIZES` (8, 10, 14 mm line) still scale the whole part, as before.

## Running it

    python3 Tools/boatkit/partloop/render_views.py Clutch Artifacts/partloop/Clutch/r7          # bpy module
    python3 Tools/boatkit/partloop/photo_outline.py mask <Bean's crop> Data/Reference/raw/parts/Clutch/bean.mask.png
    python3 Tools/boatkit/partloop/photo_outline.py render Clutch Artifacts/partloop/Clutch/r7
    python3 Tools/boatkit/partloop/photo_outline.py score Data/Reference/raw/parts/Clutch/bean.mask.png Artifacts/partloop/Clutch/r7
    python3 Tools/boatkit/partloop/render_inline.py Clutch Artifacts/partloop/Clutch/r7       # in-use stills + matched view
    python3 Tools/boatkit/partloop/score.py Tools/boatkit/partloop/parts/clutch.json Data/Reference/raw/parts/Clutch Artifacts/partloop/Clutch/r7

`render_inline.py` is new: `render_views.py` dresses blocks and cleats with a line, and this does the same for any part a
line runs straight through (`LineIn` and `LineOut` sockets, no sheave), plus `matched.png`, the part in full materials at
the angle `photo_outline.py` matched, for a photo-against-render tile.

## References

None are in the repo; the git-ignored copies are in `Data/Reference/raw/parts/Clutch/`.

| Reference | Used for | Licence |
|---|---|---|
| Bean's hardware reference sheet, "Rope Jammer" tile | the look, the angle-matched outline | product photo: comparing only |
| [Umgelenkte Fallen](https://commons.wikimedia.org/wiki/File:Umgelenkte_Fallen.JPG) (PaterMcFly) | a bank of five clutches in use on a cabin top | CC BY 3.0 |
| [Fallenstopper zerlegt](https://commons.wikimedia.org/wiki/File:Fallenstopper_zerlegt.JPG) (PaterMcFly) | a disassembled clutch's cam and lever (not downloaded: the image host refused the cloud) | CC BY 3.0 |
| Spinlock XAS 6-12 and Lewmar D1 catalogue sizes, read from search results (maker and shop sites are blocked from the cloud) | length, height, width, fixing centres | numbers only |

No free 3D model of a rope clutch turned up.
