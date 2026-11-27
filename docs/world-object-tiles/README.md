# World objects in tiles (huge maps, step 5, first part)

Plan: the Claude Doc "Huge maps without memory growth" (step 5 of its order of work). Draft until after the Dec 11 release.

## In plain English

The ground already streams: only the 6.4 km squares near the boat are loaded, and the ones far behind her are let go
(`docs/world-streaming/`). The houses, private docks and lidar tree crowns did not. Every one of them on the whole map was
put into the game's drawing lists when the world loaded and stayed there for the whole sail. On Galveston that is about
half a million pieces. On a Florida-to-Bahamas map it would be many times more, and the cost would grow with the map.

Now they work like the ground:

- **Houses and private docks** are sorted into 6.4 km squares when the world loads. Only the squares near the camera are
  drawn. A square is drawn a kilometre before its houses would be visible anyway, and let go 3 km after they stop being
  visible, so nothing pops in sight and a boat sailing along a square's edge doesn't make it flicker in and out.
  - The far house shapes stop drawing at 8 km, so their squares come in at 9 km and go at 11 km.
  - The detailed waterfront houses stop at 6 km (squares in at 7 km, out at 9 km).
  - The private docks stop at 3 km (squares in at 4 km, out at 6 km).
- **The detailed Galveston-style house tiles** (the baked 500 m tiles of real house footprints) are no longer all loaded
  at the start. Those within 12 km of the start are loaded then, as before. The rest load in the background as the boat
  gets within 12 km, and are let go past 14 km. The memory they used goes back to the engine.
- **Trees** past 9.5 km leave the drawing lists on every world now. Before, that happened only on the Texas coast. The far
  trees already stopped drawing at 9 km, so nothing you can see changes.
- **On a streamed world** (the Texas coast, and the big maps to come) the trees of a ground square are now let go when that
  square is let go (32 km behind the boat), and placed again if the boat comes back. Before, every square's trees stayed in
  memory for the rest of the sail. The lidar crowns and garden trees are placed square by square too, instead of all at once.
- **Reuse, never rebuild.** This is the lesson from the tide memory climb (`docs/tide-memory/`). The pieces that draw a
  square are kept in a pool. When a square behind the boat is let go, its drawing piece is emptied and handed to the next
  square ahead, instead of being thrown away and made again. On a long sail the number of drawing pieces stops growing once
  the ring around the boat is full.

What is not in this part yet:

- The house, crown and dock *data* still loads whole from disk at the start; only the drawing side streams. It is small
  (a few dozen bytes per house). Splitting it per tile needs a bake change in `Tools/`, which needs Bean's label, so it is
  the next part.
- The charted piers, bridges, breakwaters, navaids and landmarks are not tiled yet.
- Unbaked house tiles (a world whose houses were never baked) are still built whole at the start, as before.

To compare with the old way, run with `-SailingWholeWorldObjects`. `-SailingObjectRing=<load km>,<keep km>` changes the ring of the
baked house tiles (default `12,14`).

## How it works

| Piece | What it does |
| --- | --- |
| `ObjectTiles.h` (SailingPhysics, plain C++) | `FObjectCells`: the cells that hold something (a long coast's cells, not its whole box). `PlanObjectCells`: make every cell within the load radius, nearest first, and drop every made cell past the keep radius. `ObjectRingForCull`: the ring from a mesh's cull distance (+1 km in, +3 km out). `FSlotPool`: a free list of drawing slots. |
| `FTiledInstances` (`ObjectStreaming.h`) | For instanced objects. Each kind (house shape, waterfront house, dock, boathouse) has a template component. That component stays empty; it is cloned for a cell when the cell comes into its ring. Objects are stored per cell in the actor's own frame (map centimetres), so a cell made late in a sail stands where one made at the start does, tide and re-centres included. A cell leaving the ring empties its component back into the pool. At most two cells are filled a frame. |
| `FTiledMeshes` (`ObjectStreaming.h`) | For the baked 500 m house tiles. The tiles within the ring at the start are loaded at once; the rest are asked for with `LoadPackageAsync`, the way the far ring loads its tiles. A tile that leaves the ring lets go of its mesh. A late answer for a tile that was let go meanwhile is ignored. A Static mesh can't change its mesh while registered, so a pooled component is unregistered while it changes tile. |
| `ALakeTerrainActor` | `PlaceHouseModels` hands its lists to `HouseCells` and its baked tiles to `HouseTileStream` instead of filling the components; `StartObjects` draws the cells around the launch spot in `BeginPlay`; `UpdateObjects` runs each tick. Trees: `TileComponent` takes a crown tile component that emptied (`FreeTileComps`) before making a new one; `DropTreeTiles` lets go of a dropped height tile's trees and renumbers the rest; `UpdateTreeTiles` places a tile's crowns (`AppendCrownTrees`) and garden trees (`AddYardTrees` with a copy of the terrain) on the worker. |
| Loading screen | "Streaming shoreline and trees" also waits for the house cells and tiles around the start. |
| `bench.json` | The `world` record gains `object_cells`, `object_made`, `object_dropped`, `object_components`, `object_instances`, `model_trees`, `tree_tile_components`, `tree_tile_components_free` and `trees_dropped`. |

### Tests

- `SailingSim.World.ObjectTiles.Rules`: the plan and the pool without a world. A 200 km sail out and back, 10 m a step:
  the ring holds the whole way, it is the same ring back at the start, and the pool never has more slots than the most cells
  drawn at once (checked standalone with clang: 35 cells, at most 7 at once, 67 makes, 60 of them reusing a slot).
- `SailingSim.World.ObjectTiles.Instances`: on a terrain actor 30 cm down with the tide, 2,000 houses along 100 km. Only the
  cells near the start are drawn; a house stands at its map position with its own floats; after the sail and another 2 cm of
  tide the start's house, made again in a reused component, is 32 cm down; the components are reused, not made per cell.
- `SailingSim.World.ObjectTiles.HouseRing`: how many of Ray Hubbard's and Galveston Bay's baked house tiles the start now
  loads, against all of them before.

## To check before it merges (after the Dec 11 release)

1. Mac and PC builds and the full suite (`scripts/test.sh`; the PC's MSVC build).
2. `scripts/gate.sh --scope world` (Medium 60, High 45 fps) and the stream-run view.
3. The Galveston and Texas coast soaks with `-SailingWholeWorldObjects` against without: memory, the number of drawing
   components, no frame over 100 ms when a cell is filled.
4. Eye checks: the far shore at 8-12 km at dusk (houses must not pop), a cell edge sailed along, the Texas coast run out and
   back (trees and houses back where they were).
5. When the tide-memory fix (PR #846) merges first: `MakeHouseTileComponent` makes a `USailingKeptMeshComponent`, as the
   kit tiles there do. The house cells clone their templates' class, so they pick it up by themselves.
