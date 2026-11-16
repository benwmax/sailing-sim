# Building parts kit: results (Track E, parts half)

Plan: "Shore, Grass and Buildings" (Nov 16 2026), Track E. Tools and how to run them: `Tools/envloop/buildkit/README.md`.
Review page with every render: https://claude.ai/artifact/EuV8wLy5cTwEkoimabCtRM. Nothing here is loaded by the game yet; the integration step (after the
Nov 21 slice) swaps `HouseKit.cpp`'s flat window and door rectangles for these parts and re-bakes the mid-band tiles.

## What is in it

- **53 parts** at real size from the interim size card (`sizes.json`, US catalogue sizes and IRC stair and guard
  rules): 8 windows, 5 doors, 5 garage doors, 3 shutters, gutters and downspouts, 4 roof vents, ridge cap, 3 chimneys,
  2 dormers, 4 columns and posts, rails, steps, 2 foundations, 3 lights, 2 AC units, 2 meters, casings, sills, corner
  boards, fascia. 15,443 triangles for the whole kit.
- **One shared trim sheet**, 2048 x 2048 at 4 px/cm: 15 surface bands (painted wood, vinyl, aluminium, galvanised,
  black iron, bronze, cedar, concrete, cast stone, rubber, screen, coil guard, louvre, lattice) and 6 cells (fan grille,
  meter face, lamp glass, round vent, kick plate, dial). Colour, normal and mask maps, all made by script.
- **Six house styles** in the `north-texas-lake` region pack: 1970s brick ranch, 1990s two-storey brick, stone and
  metal-roof farmhouse, lake cottage, modern infill, plain commercial. Each style is a recipe (roof shape and pitch,
  wall and roof finish, which windows and doors, porch, trim, palettes); a seed picks within it, the same every run.
- **A test house builder** that puts the parts on a whole house and renders the loop's standard views.

## The six checks

| Check | Result |
| --- | --- |
| Sizes within 5 percent of the card | Pass, all 53 parts (`build_kit.py`; openings checked on the opening, frames allowed for) |
| Triangle budget per part | Pass, all 53 |
| Colour against a grey card | Waits for Bean's lake-house photos |
| No repeat in a 40 m frame | Three seeds side by side per style; the commercial box repeats its shape (only its finish and openings move) |
| Variety counts | 8 windows, 5 doors, 5 garage doors, 6 styles: met |
| Blind review | Fair only on in-game stills, after Nov 21 |
| Budget per house | 3.1k to 11.3k triangles at seed 1 (table below), and three seeds per style stay between 3.1k and 11.8k |

| Style | Triangles | Parts placed | Roof | Front wall |
| --- | ---: | ---: | --- | --- |
| 1970s brick ranch | 8,544 | 39 | gable, barkwood shingle | red brick |
| 1990s two-storey | 11,306 | 57 | gable, charcoal shingle | buff brick |
| Farmhouse | 9,530 | 45 | gable, standing seam | board and batten |
| Lake cottage | 5,850 | 37 | gable, barkwood shingle | lap siding |
| Modern | 5,362 | 31 | shed, standing seam | board and batten |
| Commercial | 3,130 | 15 | flat, membrane | stucco |

## What the renders show

- Walls and roofs in these renders are stand-in patterns at the true course sizes. The real ones are the materials
  thread's (PR #750, `Tools/envloop/buildmat/`); the preview swaps to them once both merge.
- The white mortar in the brick stand-ins is too bright. That is the stand-in, not the kit.
- Glass is plain dark glass here; the fake interiors are the materials thread's.

## Other regions

Region packs are data, not code: everything North Texas is in `Tools/envloop/buildkit/packs/north-texas-lake/`, and the
tools take `--pack`. Wall and roof finish names are the materials pack's list on the ids in `slots.json`. Another region
copies the pack and adds parts only where its houses need a shape the kit lacks. The layout moves to Track 0's shared
pack format when it lands.

## Next

1. After Nov 21: integration in `HouseKit.cpp` (same openings, kit parts), the mid-band re-bake, in-game stills at Track
   0's stations, then the blind review.
2. Bean's lake-house photos: colour check against a grey card, and the size card checked against real houses.
3. Swap the preview's wall, roof and glass for the materials thread's once PR #750 merges.
4. Adopt Track 0's size card and pack layout when they land.
