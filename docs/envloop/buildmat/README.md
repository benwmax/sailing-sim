# Building materials: walls, roofs, windows (Track E2)

The materials half of Track E in the shore, grass and buildings plan (Nov 16 2026). The parts half (windows, doors,
trim) is the parts thread's `Tools/envloop/buildkit/`. Tools: `Tools/envloop/buildmat/` (its README has the steps).
Pictures: the look sheet https://claude.ai/artifact/2Z5nz6xBwEAz822GKf6Fkv (the images can't be stored in this folder
from the cloud, because they are Git LFS files).

**Nothing here is in the game yet.** After the 21 Nov slice an integration pull request puts the wall, roof and glass
shader code in its own material script (not `scripts/make_materials.py`), imports the textures, and wires the house
generator to the parts kit. Only then can the Mac gate measure the cost.

## What there is

| Kind | Finishes |
| --- | --- |
| Brick (king size, 76 mm courses, running bond) | Texas red, brown blend with iron spots, buff and cream |
| Other walls | Austin chopped limestone (random ashlar, three course heights), fibre-cement lap siding (150 mm), board and batten (305 mm centres), sand-finish stucco |
| Roofs | architectural shingles in weathered wood, charcoal and barkwood (143 mm rows), standing-seam metal (406 mm panels, bare Galvalume or painted), flat membrane (white, grey or black) |
| Windows | fake rooms behind the glass: 16 rooms in one atlas, with blinds, curtains, obscure glass, and lights at dusk |

Each finish is drawn at its real sizes, whole bricks or boards per texture so the courses run on across tiles. The
free CC0 scans (Poly Haven, ambientCG) add only the fine grain. The painted finishes are grey in the texture and take
each house's own paint colour (the parts kit's paint roles 7, body, and 8, roof).

## Other places

Everything North Texas about these materials (the three Texas bricks, Austin limestone, the shingle colours, the paint
colours and the test houses) lives in one region file, `Tools/envloop/buildmat/packs/north-texas-lake.json`. The tools
and the shader never name a finish; each finish says what kind of surface it is (brick, stone, lap siding, board and
batten, stucco, shingle, standing-seam metal, flat membrane), and the kind decides how it is drawn and how it ages.
Another lake or coast gets its own region file on the same material slots, with no code change; a new kind of surface
(clay roof tiles, timber shakes) is a small code addition.

## Wear

The boats' five levels: L0 new, L1 months, L2 club (6 years), L3 kept (30 years, cared for), L4 left (20 years,
neglected). The same two numbers drive both: what the years do, and what care removes. On a house that means darker
mortar, white salt bloom low on brick, red clay splashed up from the beds, green algae on north walls, mildew under
siding laps, chalky faded paint, peeling only on a neglected old house, cracks in old stucco, shingles losing granules
with black algae streaks, lichen, dull Galvalume and rust at the seams of a neglected metal roof, and ponding stains on
flat roofs.

## The six checks (`Tools/envloop/buildmat/checks_north-texas-lake.json`)

| Check | Result |
| --- | --- |
| 1. Sizes | All 15 measured repeats within 0.3% of the card (brick course 76.0 for 76.2 mm, lap 150.1, shingle row 143.3, panel 405.9, battens 304.6). |
| 2. Colour | Interim only. Limestone is close to its stand-in scan; Texas red brick is far from Poly Haven's European red brick, as expected. Real answers need Bean's grey-card photos. |
| 3. Repeat | Pass for all 12: across a 40 m wall, the material's pattern one tile apart correlates at -0.67 to -0.05 (the raw texture alone: 0.89 to 1.0; the limit is 0.6). |
| 4. Variety | Met: 3 bricks, 4 other walls, 3 shingles, 1 metal, 1 membrane, 16 rooms, 3 window dressings, 5 wear levels. |
| 5. Budget | Textures: 41.7 MB on Ultra (1024 px a tile, about 4 mm a pixel), 11.7 MB on High, 3.2 MB on Medium. Five texture reads a pixel on walls and roofs, one on glass, where today's house materials read none: the frame cost is unmeasured until the Mac gate after 21 Nov. |
| 6. Blind review | See below. |

## Blind review

Two rounds, three fresh reviewers each, who saw only the pictures (`Tools/envloop/buildmat/reviews_north-texas-lake.json`).
Each round had 14 before/after pairs at 15 m, with sides shuffled, and 12 wear ladders, with levels shuffled.

| Round | New materials chosen | Realism, new vs today (of 5) | Ladder order (1 = perfect) |
| --- | --- | --- | --- |
| 1 | 42 of 42 | 3.4 vs 2.0 | 0.73 |
| 2, after fixes | 42 of 42 | 3.6 vs 2.1 | 0.70 |

Between the rounds the weathering spots were made softer and clustered. Salt bloom now stays low on the wall and
follows the mortar. Metal seams no longer read black, and rain soiling was added to masonry. Roofs, stucco, siding
and board and batten now order almost perfectly (0.8 to 1.0).

Still open:
- Limestone, buff brick and brown brick age too little to see on a 1.6 m swatch. Bean's photos of real aged local
  walls will set how much.
- Lichen on dark shingles reads as white flecks, and membrane stains are still too hard-edged.
- At 15 m the walls lack large stains and shade under the eaves. The eave shadow comes with the parts kit's real
  overhangs.

Today's materials were marked down for diagonal streak bands on the shingles, a white mortar grid, and square tiling
on stucco.

## Known limits

- The "before" pictures run main's house shader through the same offline renderer, which has no temporal
  anti-aliasing: main's fine procedural lines shimmer more here than they do in the game.
- The colour check waits for Bean's grey-card photos of real local brick, stone and roofs.
- Downspouts, gutters, trim and the windows' frames belong to the parts kit and are left out of these renders.
