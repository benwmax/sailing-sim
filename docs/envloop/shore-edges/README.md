# Shore edge types (shore plan Track C)

Bean's ask (Nov 16 2026): the shoreline, grass and buildings look low quality up close. The plan ("Better shoreline,
grass and buildings", https://claude.ai/artifact/FMpfBPUrLhUvUmFr3eEf9B, all eleven recommended answers approved Nov 16)
splits the work into tracks. Track C takes the shore from four edge types to ten, each with its own wet line, stain
band and thin debris line, plus a soft foam and ripple edge where water meets land (that last part is the water
material's, on the Mac, after Nov 21).

This page is the cloud half, done before the Nov 21 slice: the pieces, the shared water-edge layer and the standard
renders, all in `Tools/envloop/shore-edges/`. Nothing the game loads changes. Wiring into the game, the stations'
in-game stills and the frame-rate gates come after Nov 21 through Track I and the main sim thread.

## The ten types

| Type | What it is | Today | Here |
| --- | --- | --- | --- |
| riprap | quarried limestone armour stone | done (rock loop, `docs/shore-loop/rocks.md`) | not rebuilt |
| bulkhead | poured concrete wall, 300 mm cap, 75 mm weep holes every 2.44 m panel | plain wall and a kerb (HouseKit) | new |
| sheetpile | steel Z-piles (PZ22: 1.118 m a pair, 229 mm deep), channel cap, tie-rod nuts on a waler | none | new |
| limestone | stacked 0.6 m blocks, each course 5 cm back | none | new |
| timber | 8 in posts every 8 ft, 2x10 boards, a cap board | none | new |
| claycut | eroded blackland-clay scarp 1.2-1.9 m, wave-cut notch, slumped blocks, hanging roots, a bench | "natural bank" (terrain paint) | new |
| mudflat | 1:60 silt flat, ripples and pans, cracks as it dries, shells | none | new (scatter; ground is Track A) |
| gravel | gravel and clam-shell beach, 1:10, berm at the wrack line | "sand strip" (terrain paint) | new |
| reedcove | shallow cove, patchy cattails and rushes | lone reeds | new (stand-in plants: Track B) |
| ramp | 4.6 m concrete lane at 14 percent, chevron V-grooves, apron, gravel shoulders | none | new |

## Region packs

Everything specific to North Texas is data in one named pack, `Tools/envloop/shore-edges/packs/north-texas-lake/`
(the plan's "Built to work for other locations" rules): `pack.json` holds which edge types the region has, their sizes,
the lake's levels and marks (pool, the band's top and bottom, the wrack line, the swash), every surface colour the
shader uses, and the placement rules Track I will apply from map data (lots by seed, marinas, natural shore by slope,
fetch and shelter, ramps from OSM slipways; no hand placement outside the home club). The cards sit beside it. The
builders, the shader and the tools are the same for every region and take `--pack <name>`; another lake or coast is a
new folder. When Track 0 publishes the shared pack layout this pack moves into it.

Each type has a card (`packs/north-texas-lake/cards/<type>.json`): what it is and where it goes in the game, what the
real thing looks like on a North Texas reservoir, its measures with their sources, its triangle budget, the reference
photos wanted. Sizes come from the plan's interim size card (bulkhead cap 300 mm, sharpness about 1 cm per pixel in the
hero band) and published construction sizes; Track 0's shared size card replaces the interim one when it lands.

## How it is built

- `edge_kit.py`: pure numpy geometry, one builder per type, a stretch of shore of any length (x along the shore, the
  land toward +y, z = 0 the 435.5 ft pool). Vertex colour R says which surface a vertex is (concrete, steel, limestone,
  timber, cut clay, mud, gravel, shell, sand, ramp, sticks, leaves, reeds, grasses), G a per-part shade, B a run-off
  source (under weep holes and bolts). Shared pieces: the wrack line of sticks and leaves, pebbles and clam shells,
  slumped clay blocks, roots. `python3 Tools/envloop/shore-edges/edge_kit.py` prints each type's triangles.
- `edge_layer.py`: `EDGE_LAYER_CODE`, HLSL for the in-game material (its own script after Nov 21, never
  `scripts/make_materials.py`) that the renders run on numpy through `Tools/texloop/dock/hlsl_np.py`, so the cloud
  pictures are the shader's own text. It draws each surface's look and the water's marks, all from height against the
  lake, so one mesh is right at any lake level (`packs/north-texas-lake/cards/layers.json`). Its colours are named
  parameters whose values come from the pack:
  - the wet line up the swash (porous ground wicks higher);
  - the stain band between the lowest (-1.25 m) and highest (+0.30 m) recent water, ringed, darker lower down;
  - the pale scum line at its top;
  - algae on whatever is under the pool most of the year: slimy olive in the water, a grey-green crust when a low lake
    leaves it dry (the ramp's slick toe);
  - run-off streaks under weep holes and rust under bolts;
  - the wrack stain where sticks and leaves come to rest.
  Its noise inputs are one tiling, histogram-equalised noise texture at four scales (3 cm, 10 cm, 0.5 m, 2 m) plus a
  narrow streak noise; the renders fade each scale toward its mean where a pixel covers more than a cell, as mips do.
- `render_edges.py`: the loop's standard renders. Each type from a boat 1.5 m over the water at 3 m, 15 m and 60 m off
  the water's edge (24, 50 and 54 mm lenses: at 60 m the frame is the plan's 40 m repeat check), in midday sun, low sun
  raking along the shore, overcast, and midday with the lake a metre down (the Oct 11 2026 gauge, which bares the
  band). Cycles renders the data and the light on white; the look is the HLSL; the lake is laid over what is under the
  water. Lighting and water are the rock loop's (`render_rocks.py`), imported, so both loops light alike.
- `check_edges.py`: the six checks on the renders' output (below).

Run (Python with `bpy`: `pip install bpy==5.1.2`; numpy, Pillow):

```
python3 Tools/envloop/shore-edges/render_edges.py --out <dir> [--pack north-texas-lake] [--types bulkhead,ramp] [--size 640x320] [--samples 16]
python3 Tools/envloop/shore-edges/check_edges.py --out <dir> [--pack north-texas-lake]
```

The renders are pictures, so they stay out of git (images are Git LFS and the cloud cannot push LFS): the sheets are in
the project files (`shore-env/track-c/`) and on the Track C review page.

## The six checks

| Check | How | State |
| --- | --- | --- |
| Sizes within 5% | the card's measures against what the kit built | see the round below |
| Colour against a grey card | Lab dE against Bean's photos | waits on the photos |
| No repeat in a 40 m frame | the 60 m views' sideways self-match under 0.6 | see the round below |
| Variety | ten edge types | ten (riprap from the rock loop) |
| Blind review | three fresh reviewers, new beats old, "photo or game" at 15 m | after Nov 21, on in-game stills |
| Budget | the edge's own triangles per 16 m against the card | see the round below |

## In the game (the wiring PR, before the Nov 27 freeze)

Bean moved the slice to Fri Dec 11 (Nov 17), so the edges go into the game before the Nov 27 freeze instead of after the
slice. The wiring is one PR of code, scripts and this page; the Mac imports the pieces and commits the assets.

- **Pieces.** `Tools/envloop/shore-edges/export_edges.py` builds each type as 4 m of shore (three seeds a type) without
  the stand-in ground and writes `SM_Edge_<Type>_<n>.fbx` plus a `_Light` copy at an eighth of the triangles;
  `scripts/import_shore_edges.py` imports them to `/Game/World/Edges` with Nanite (`scripts/make-shore-edges.sh` runs
  both). Seven types are pieces: bulkhead, limestone, timber (walls) and clay cut, gravel, mud flat, reed cove (the
  scarp with its notch and slumped blocks; the shells, pebbles, wrack and reed clumps). Riprap stays the rock loop's
  stones; sheet pile and the ramp wait for the marina and slipway placement.
- **Material.** The same script builds `M_ShoreEdge` from `edge_layer.py`'s `EDGE_LAYER_CODE` (one Custom node; the
  colours are vector parameters with the pack's values, the four noise scales and the streak noise are gradient noise
  computed in their own Custom nodes from the map-frame position, `EDGE_NOISE_CODE`), and gives `MPC_World` the pack's
  marks `PoolZ`, `HighZ`, `LowZ`, `WrackZ`, `Swash` (metres) beside the game's `WaterZ`, so the wet line follows the lake
  level and the stain band stays where the water has been. Nothing in `scripts/make_materials.py` changes; the ground
  textures PR (Track A) adds its own `Season` scalar the same way, so the two don't collide.
- **Placement, by rule from map data.** `LotBankType` (`HouseKit.cpp`) gives every full-detail lakefront lot its bank by
  its seed, the pack's `developed_lot` rule: bulkhead on half, riprap on a fifth, then limestone, timber, or a natural
  bank. The house tile keeps the stepped riprap and drops its old plain wall and kerb; `ShoreEdgeRuns` returns the other
  lots' waterlines (the same line the kit found for the riprap, every 2 m) and `ALakeTerrainActor::PlaceShoreEdges`
  lays a piece on each segment, x along the shore and stretched to it, +y toward the land, at the pool datum. The
  natural shore is picked per grid node outside the lots, the marina and the club by the bank's slope and the fetch
  across the water in front of it (`pack.json placement.natural`): mud flat under 1:30, reed cove where the fetch is
  under 300 m, clay cut on a bank over 30 degrees with a kilometre of fetch, gravel on a gentle exposed shore, clay cut
  as the fallback for a steep bank; two nodes in three take a piece, laid across the slope at the waterline. Instanced
  static meshes, static, no collision; the walls to 1.5 km and in ray tracing, the scatter to 300 m. Nothing is placed
  by hand outside the home club. `-SailingNoShoreEdges` compares; Low keeps the old shore.
- **Known gaps for the Mac stills.** The natural pieces' scatter follows the kit's own slope, not the terrain's, so on
  a bank steeper or flatter than the card's a shell or stick can hover or sink a few centimetres; the clay scarp is a
  fixed 1.2-1.9 m face standing in the lidar bank. Reeds are stand-ins until Track B's grass lands; the lawn behind the
  walls is Track A's ground.

### What the Mac does (about 3 hours, Nov 23-25)

1. `scripts/build.sh`, then `scripts/make-content.sh` is not needed (no material script changes) but `MPC_World` must
   exist; `scripts/make-shore-edges.sh` (Blender export, import, `M_ShoreEdge`, the marks); `scripts/make-houses.sh`
   (the tiles lose the plain walls). Commit `/Game/World/Edges` and the rebuilt house tiles to the branch.
2. Station stills before and after: Track 0's bulkhead lot, natural clay bank and club beach stations
   (`Tools/envloop/stations.csv`), `SCENES=... scripts/capture-scenes.sh 8` on main and the branch.
3. `scripts/gate.sh --scope world`; a view under its floor is benched beside main.
4. The PC: a Windows build and an Ultra look at the bulkhead and clay bank stations (about an hour).

Then the blind review on the stills (three fresh reviewers, new beats old) and the colour check when Bean's grey-card
photos come. The foam and ripple edge in the water material is still the Mac's, after the freeze.

## Rounds

Round 1 (Nov 16): first build of all nine, 640x320 at 16 samples, about 27 minutes on four cloud cores. Sheets in the
project files, `shore-env/track-c/round1/` (`all_15m.png`, `all_3m_midday.png`, `all_3m_low_lake.png`, one sheet a type).

| Type | Sizes | Repeat at 60 m | Triangles per 16 m (budget) |
| --- | --- | --- | --- |
| bulkhead | ok | 0.76, by design (a panel and weep hole every 2.44 m) | 13,734 (20,000) |
| sheetpile | ok | 0.90, by design (piles every 1.118 m) | 35,392 (40,000) |
| limestone | ok | 0.23 | 64,016 (70,000) |
| timber | ok | 0.91, by design (posts every 2.4 m) | 2,276 (8,000) |
| claycut | ok | 0.44 | 34,808 (40,000) |
| mudflat | ok | 0.27 | 19,600 (25,000) |
| gravel | ok | 0.56 | 49,000 (50,000) |
| reedcove | ok | 0.36 | 10,884 (15,000) |
| ramp | ok | 0.62, by design (one ramp, alike on both sides) | 1,444 (4,000) |

The budgets are first proposals set with this round's counts in view; Track 0's frame measurements set the real ones.

Seen in the sheets, for round 2:
- the value noise shows its 10 cm and 0.5 m cells as soft squares in the algae crust and the wet band (gradient noise,
  like the game's texture will be, fixes it);
- limestone blocks read pillowy (corners too round) and the lichen too blotchy;
- at 3 m the sheet pile's waler and cap hide most of the corrugation at the pool (true to life, but the 5 m hold
  station should look down a little);
- the mud flat's ripples are too regular; the reeds are thin stand-ins (Track B);
- the lawn behind the walls is a flat stand-in (Track A).

Round 2 (Nov 18): the fixes above and the game pieces. Sheets in `shore-env/track-c/round2/`. All checks that can run
pass again; the 60 m repeat scores fell where the noise changed (bulkhead 0.76 to 0.35, limestone 0.23 to 0.34, mudflat
0.27 to 0.36, gravel 0.56 to 0.47, claycut 0.44 to 0.48; the piled walls keep their pitch by design). Triangle counts are
unchanged.

- Gradient noise (two octaves, equalised) replaces the value noise in the renders (`grad_noise`): the soft squares in the
  algae crust and the wet band are gone; the game computes the same noise in `M_ShoreEdge` (`EDGE_NOISE_CODE`).
- Limestone: a sharper arris (superellipsoid power 18, half the chipping) and lichen as soft blotches at 0.5 m instead of
  10 cm specks. The blocks still read a little soft at 3 m: the next step is a flat-shaded face with a chamfer.
- Mud flat: ripple wavelength drifts 0.35-0.55 m, the crests wander and split, the amplitude is patchy.
- The 3 m view looks down a little at the sheet pile (0.55 m) and the bulkhead (0.2 m), so the hold station shows the
  piles' feet at the pool, not the waler alone (`LOOK_DOWN`).
- The scatter (pebbles, shells) is clipped to the piece's length, so a 4 m game piece carries only its own.

