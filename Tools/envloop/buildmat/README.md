# Building materials (Track E2 of the shore plan)

Walls, roofs and windows for the lake's houses: the materials half of Track E in the shore, grass and buildings plan
(Nov 16 2026). The parts half (windows, doors, trim, the trim sheet) is `Tools/envloop/buildkit/`; the two agree through
its `slots.json` (finish ids, UV rules, paint roles). Results and pictures: `docs/envloop/buildmat/`.

## Region packs

Everything specific to a place is data in `packs/<name>.json`: which wall and roof finishes the region has, their ids
(what the parts kit writes in vertex colour G), real unit sizes, palettes, mortar and paint colours, the scans its colour
check compares with, how many of each class it wants, and its test houses. `north-texas-lake` is the first (three Texas
bricks, Austin limestone, siding, stucco, three shingle colours, metal and flat roofs). The code never names a finish:
each finish picks a class (`pack.CLASSES`: brick, stone, lap, batten, render, shingle, standing_seam, membrane), and the
class decides how the texture is drawn (`make_textures.MAKERS`) and how it wears (the shader's `Kind`). A new region is a
new pack on the same material slots; a new kind of surface (say clay tile or timber shakes) is a new class. Every tool
takes `--pack <name>` (or `BUILDMAT_PACK`); textures go to `Data/BuildMat/raw/out/<pack>/`. When Track 0's shared pack
layout lands, this file moves into it.

Nothing here is loaded by the game yet. The integration pull request after the 21 Nov slice puts `BUILDMAT_CODE` and
`INTERIOR_CODE` in their own material script, imports the textures, and wires the house generator to the kit.

## Steps

```
python3 -I Tools/envloop/buildmat/fetch_sources.py     # CC0 grain scans -> Data/BuildMat/raw/<id>/ (git-ignored)
python3 -I Tools/envloop/buildmat/make_textures.py     # the pack's texture sets + T_BuildNoise -> Data/BuildMat/raw/out/<pack>/
python3 -I Tools/envloop/buildmat/interior.py          # T_RoomAtlas (16 rooms) -> Data/BuildMat/raw/out/
python3 -I Tools/envloop/buildmat/test_buildmat.py     # tests (no downloads needed)
python3 -I Tools/envloop/buildmat/checks.py            # the six checks -> checks_<pack>.json
python3 -I Tools/envloop/buildmat/render.py            # test houses at 3/15/60 m x midday/low sun/overcast (L2)
python3 -I Tools/envloop/buildmat/render.py --before --lights midday,overcast --dists 15,60   # main's materials
python3 -I Tools/envloop/buildmat/render.py --ladder   # every finish at L0..L4
python3 -I Tools/envloop/buildmat/make_sheet.py        # contact sheets -> Artifacts/envloop/buildmat/sheets/
```

Everything is numpy and Pillow; no Blender, no engine. About 25 minutes for the full set on a cloud machine.

## Files

| File | What |
| --- | --- |
| `packs/<name>.json` | A region pack: one card per finish (class, what it is, real unit sizes, tile size in whole units, palette, where it is used; ids match `slots.json`) and the test houses. |
| `pack.py` | Loads the chosen pack; the class table. |
| `sources.json` | The CC0 scans (Poly Haven, ambientCG) used only for fine grain, with their real widths. |
| `make_textures.py` | Draws each finish at its real sizes (whole bricks, boards, rows, panels per tile) and writes colour, normal and mask maps. |
| `buildmat_hlsl.py` | `BUILDMAT_CODE`: the wall and roof material's Custom node (anti-tiling, paint, wear by Age and Care), run on numpy here. |
| `interior.py` | `INTERIOR_CODE` and its numpy twin: fake rooms behind windows; builds the room atlas. |
| `render.py` | Test house renders, the "before" (main's `HOUSE_KIT_*_CODE`), and wear ladder swatches. |
| `checks.py` | The environment loop's six checks. `checks.json` is the last run. |
| `make_sheet.py` | Labelled contact sheets. |
| `reviews_<pack>.json` | Blind review rounds (written after each round). |
| `blind_pack.py` | Shuffled before/after pairs and wear ladders for the blind review (the key stays beside the pack). |

## Texture sets

Per finish, the pack's `px` a tile (north-texas-lake: 1024 on Ultra (about 4 mm a pixel), 512 on High, 256 on Medium). `_C` colour (sRGB; painted finishes
are a neutral 0.8 grey with grain), `_N` normal (green up the wall), `_M` mask (R occlusion, G roughness, B unit id,
A height). Image row 0 is the top of the tile: sample at `(UV.x / tile_w, -UV.y / tile_h)` with UV0 in metres.

The unit id gives every brick, stone, board, tab and panel its own random number, so the material can reshade each one
differently in every tile: that is what stops a 4 m tile from repeating across a 40 m house front.

## Wear

The boats' five levels (`Tools/texloop/levels.json`) and the same two numbers: `dT` (what the years do, `time_k`) and `dD`
(what care removes, `dirt_k`). On houses: mortar darkening, white efflorescence low on brick, red clay splash-back,
green algae on north walls, mildew in siding laps, paint chalk and fade, peeling on a neglected old house, cracks in old
stucco, granule loss and black algae streaks on shingles, lichen, Galvalume dulling, rust at seams on a neglected metal
roof, ponding stains on flat roofs.

## Windows

Interior mapping with a flat atlas: every room is the same 4 x 2.7 x 4 m box; each atlas cell is a pinhole picture of one
room taken from 4 m in front of its front face, so the shader's ray-box hit maps exactly to the picture (see
`interior.py`). Blinds, curtains and obscure glass are drawn at the pane. Lights come on at dusk in 45% of windows.
