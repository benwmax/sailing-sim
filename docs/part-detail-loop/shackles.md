# Shackles: bow shackle and long D shackle (Nov 8 2026)

Bean's hardware sheet (Nov 8) asked for each part on it to be rebuilt with the [part detail loop](README.md). This page
is the bow shackle (top row) and the dee shackles (bottom row). They share one design, so they are built together in
`Tools/boatkit/bk_part_shackles.py`.

| Part | What | Size | Where it goes |
|---|---|---|---|
| `ShackleBow` (new) | forged stainless bow (lyre) shackle, 5 mm, flat key-head pin | 36 mm overall, 10 mm opening, 25 mm across the bow | loads that pull at an angle: the jib tack at the stemhead, halyards on the sail heads, a block on a padeye |
| `ShackleD` (rebuilt) | forged stainless long D shackle, 5 mm, flat key-head pin, flat section | 41 mm overall, 10 mm opening | a straight pull: the jib sheets at the clew, blocks on bails (vang, mainsheet), the Sunfish's mainsheet block |

The October kit had one shackle, `ShackleD`: a bent tube with a plain pin and a round head, 29 mm, pin along Y. No
layout placed it, so changing it moves nothing on a boat. It was the only shackle the kit had, so it is the "before"
for both.

## How they are built

- One 5 mm body swept along a centreline, two flat round ears (lugs taller than wide, as forged), fused by a voxel
  remesh so the ears grow out of the legs with no seams, drilled for the pin and reduced to about 11,000 triangles.
- The bow's centreline was measured row by row on the square-on photo and scaled to the catalogue's 36 mm: the legs
  pinch in just above the ears, swell out to the widest point two thirds up, and close over a crown a little taller
  than a half circle.
- The D is straight legs and a half-round crown, in the long size of Bean's sheet (inside length about three times the
  opening), with a forged flat section (flat faces, rounded edges).
- The pin: a 5 mm shank through both ears, a domed end on one side, and on the other a collar and a flat key head (a
  tab with a hole for seizing wire).
- Frame (as the blocks' own shackles): origin at the pin's centre, pin along X with the key head on +X, the shackle
  standing up along +Z. Sockets: `Pin`, `Bow` (inside of the crown, where a line or ring sits), `Head` (the key's hole).
- Sizes 4, 5, 6, 8 and 10 mm scale the 5 mm build (`SIZES`), like the old `ShackleD`.

## Results

| Part | Round | Overall | Other sizes | Outline | Features | Triangles | Blind review |
|---|---|---|---|---|---|---|---|
| Bow | before (old ShackleD) | 29 mm (-19%) | height/width 1.15 (-11%) | 81% | 3/9 | 776 | |
| Bow | r5 | 36 mm | 1.27, 28.5 mm with the head | 93% | 9/9 | 12,774 | won 3 of 3 against before (confidence 5, 5, 5); all three called the before the wrong part ("U-bolt", "staple", "padlock loop") |
| Bow | r6 | 36 mm | 1.23 (-4%), 29.4 mm (+5%) | 93% | 9/9 | 12,834, 1 slot | won 3 of 3 against r5 (confidence 2, 3, 3) |
| D | before | 29 mm (-29%) | | not checked | 3/9 | 776 | |
| D | r5 | 41 mm | | not checked | 9/9 | 12,774 | won 3 of 3 against before (confidence 5, 5, 5); all three called the before the wrong part |
| D | r6 | 41 mm | | not checked | 9/9 | 12,822, 1 slot | won 3 of 3 against r5 (confidence 4, 4, 3) |

r6 made the key head a bigger, squarer tab with a larger hole, made the ears taller and a little wider (forged lugs,
not washers) and gave the bow a deeper waist above the ears. The D has no outline check: the only square-on D photo
with a free licence is a heavy galvanised lifting D, a different shape, so it was used for the key head and ears only.

Still different from the photos (the reviewers' shared notes on r6, for a later round):

- The key head sits square to the pin; on the photos it is angled a little off the ear.
- The ears still read a little round; real ones are flatter slabs that taper longer into the legs.
- The bow could swell a touch more at the shoulders.
- The far pin end is a small dome; on the photos it is nearly flush. No collar or shoulder by the key head on the shank.
- The preview studio washes polished steel out (see below).

## Rendering metal

The preview studio is lit for black plastic blocks, so polished stainless renders nearly white. `partloop/render_metal.py`
runs `render_views.py` unchanged with the exposure lowered one stop; every round here (and the before) used it. The
camera's 0.1 m near clip cut a black hole into the near side of a 30 mm part; the 1 mm clip now on main in
`bk_render._camera` (found here and shared with the other part threads) fixes it.

    python3 Tools/boatkit/partloop/render_metal.py ShackleBow Artifacts/partloop/ShackleBow/r6
    python3 Tools/boatkit/partloop/score.py Tools/boatkit/partloop/parts/shacklebow.json Data/Reference/raw/parts/ShackleBow Artifacts/partloop/ShackleBow/r6

The old part was rendered from main before this change, turned 90 degrees about Z so its face meets the side camera.

## Kit and game

The shackles register themselves through the loader at the end of `bk_parts.py` (every `bk_part_<name>.py`), so
`bk_parts.py` itself is unchanged; `bk_part_shackles.py` replaces the old `ShackleD` entry when it loads. The whole kit builds in the cloud
with the `bpy` module: against `Inputs/boat-kit/kit.json`, only `ShackleD` and the new `ShackleBow` differ beyond the
parts already rebuilt on main (Block40, HornCleat, CamCleat, the fiddles). `kit.json` is left for the PC's import, as
before.

`partloop/render_inuse_snapshackle.py --part ShackleD` (the snap shackle's "before" stand-in) dresses the old D with
its pin along Y; with the new D (pin along X) a rerun of that option would need its line turned to match.

In the game nothing changes until Bean's PC does `scripts\windows\make-boatkit.ps1 -Import`. Putting the shackles on the
boats is the next step and needs a layout entry each (not in this change): a `ShackleBow` on the J/22's stemhead tack
hole for the jib tack, and the kit blocks' own built-in shackles kept as they are. Halyard and sheet shackles move with
the live sails and ropes, so they belong to the rig code rather than the deck layout.

## References

None of these are in the repo; the git-ignored copies are in `Data/Reference/raw/parts/ShackleBow/` and `.../ShackleD/`.

| Reference | Used for | Licence |
|---|---|---|
| Bean's hardware reference sheet (project upload, Nov 8): "Bow Shackle" | bow outline mask and proportions (square-on) | measuring and look only, never committed |
| Bean's hardware reference sheet: "Dee Shakles" | the long D's look, key heads (three-quarter view) | measuring and look only, never committed |
| [Bow Shackle](https://commons.wikimedia.org/wiki/File:Bow_Shackle.jpg) (Eunosfire986) | a lifting-style bow shackle in the hand | CC0 |
| [D-sluiting](https://commons.wikimedia.org/wiki/File:D-sluiting.JPG) (S.J. de Waard) | key head, ears and pin of a square-on D | CC BY 3.0 |
| Catalogue sizes: [S3i self-locking bow](https://www.s3i.co.uk/wichard-self-locking-bow-shackle.php), [Mealey Marine](https://mealeymarine.com/products/wichard-self-locking-bow-shackle-diameter-5mm-3-16-01242), [S3i long D](https://www.s3i.co.uk/wichard-self-locking-long-d-shackle.php) | bow L 36, A 23, B 10, M 25 mm; long D L 41, A 29, B 10 mm | numbers only |

Note for the next run: Wikimedia rate-limited the shared cloud address hard this time (most downloads took several
minutes of retries on `upload.wikimedia.org/.../1280px-`).
