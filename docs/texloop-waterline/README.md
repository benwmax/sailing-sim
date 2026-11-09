# Texture loop: lake waterline and bottom (round 4)

Plan: the boat texture and wear loop (https://claude.ai/artifact/Bq6JXirCL49khtgLL76h3q), surface 2 of the first five.
Lake Ray Hubbard is fresh water and only "suspect" for zebra mussels, so the slice boats get a scum line and slime, not
barnacles or mussel crust. The salt-water band and crust (E1, Site bay/Gulf) are unchanged.

## What changed

- **One table for three places.** `Tools/texloop/waterline/waterline.py` holds the numbers (stain cover, height, how
  ragged, clay colour, slime, bottom film) as a function of the texture loop's Dirt (and Time for the bottom paint's
  fade). The fleet shader (`scripts/make_materials.py`, BOAT_CODE, "Texture loop, waterline"), the hero J/22 bake
  (`Inputs/j22-hero/j22_waterline.py`, called from `gelcoat_hull()`) and the swatches all read it. Change them together.
- **Fleet and berthed boats (BOAT_CODE).** The old brown "mustache" (livery wear.y, 2-10 cm, brown on every boat) and E1's
  lake stain band (green-brown up to 25 cm on every berthed boat, from age and care) are replaced by the measured line:
  Dirt sets its strength, height and colour (grey film on a kept boat, tan-brown clay on a neglected one); E1's Wet
  (how much this berth's water moves) scales the height 0.7-1.3x. Below the water: a grey-olive film and olive slime
  blotches on a dirty boat. No new textures on any tier; about 40 ALU, no extra texture reads. Unset Age (player and AI
  boats) uses the livery's wear.y, as before.
- **Hero J/22 (j22_materials.py).** The 3-8 cm grey scum band and the bottom slime are replaced by the same line, slime and
  film as Blender nodes; the bottom paint's edge is now a crisp taped line (was a 4 cm blend that smeared the scum
  line into the paint). The style's `dirt`/`time` drive it, else its `age`/`care` through `Tools/texloop/wear.py`, else
  (the shipped style JSONs) the preset's wear and care.
- **Card and targets.** `Tools/texloop/cards/waterline.json`, `Tools/texloop/refs/waterline.json`.

## Reference and targets

Bean's dock photo of TX 7295 EC at Rush Creek (Oct 4 2026, overcast, on her lift; measure only, never committed) is the
only lake photo so far. `measure_waterline.py` traces the line along the hull and compares it with the clean gelcoat just
above it, so the numbers hold under any light; the 3 in (7.6 cm) Texas registration letters give the scale. The line's
colour is the mean over its full width at half depth.

The targets are judged on the hero render (`score_render.py`), which is lit and tone-mapped like the photo. The
swatches (`swatch.py`, flat albedo) are a quick proxy for heights, colour and L4's band; they read darker than a render.
L1, L3 and L4 targets are estimates anchored on L2 until club close-ups exist: a slip-kept boat's waterline and the
dirtiest boat in the yard, with a coin in frame.

| Level | Dirt | Target (line brightness vs gelcoat) | Round 4 render | Height (swatch) |
|---|---|---|---|---|
| L0 new | 0.00 | 98.5-100% | 99.7% | none |
| L1 a few months | 0.06 | 93-97% | 94.6% | 0.8 cm |
| L2 club boat | 0.57 | 86-93% (photo 89.4%) | 86.5% | 1.7 cm (photo 1.75) |
| L3 old, kept | 0.24 | 89-95% | 91.0% | 1.1 cm |
| L4 neglected | 0.92 | swatch 30-50%, tan-brown | swatch 32%, Lab a 0.8, b 8.6 | 6.5 cm |

The photo's line is almost colourless (Lab a 0.1, b 0.3); round 4's L2 is too (0.0, 0.0).

## Renders and reviews

`render_hero.py` renders the hero hull in Blender (Cycles, Poly Haven's CC0 kloofendal overcast sky) at each level,
main's material and this round's, close at the dock and from below. `make_sheet.py` makes the sheet.

Three blind reviewers per round (shuffled images, key kept outside their folder) ranked the five levels and picked
main's material or this branch's at each level (A/B, before and after shuffled):

| Round | Ladder order | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|
| 2 | failed (faint levels blank) | - | after 3/3 | - | after 3/3 |
| 3 | right 3/3 (L0 = L1 tie) | after 3/3 | after 3/3 | after 3/3 | before 3/3 ("orange-pink camo, white blotches") |
| 4 | right 3/3 (L0 = L1 tie) | after 2/3 (low confidence) | after 3/3 | after 3/3 | after 3/3 |

Round 4 fixed L4: a muddier clay (sRGB 0.45, 0.38, 0.22, was 0.50, 0.33, 0.12), a denser band with less mottle on a
dirty boat (no more white holes), and a little more cover above Dirt 0.6. L1 is meant to be barely there, so the
L0 = L1 tie is expected. What the reviewers still see: L4's slime blotches look a bit like a camo noise with no drips,
the stain has no vertical runs from rain, and the hull around it has none of the photo's streaks and scuffs (that is
the gelcoat lane's job).

## Still to do

- The Mac boats gate (`scripts/gate.sh --scope boats`): BOAT_CODE is not compiled from the cloud.
- PC: rebake the hero (`bake_j22_hero.py`) and import, then stills with `-SailingBoatAge`.
- Club photos for L1, L3 and L4.
