# Near terrain from altitude

Found in the portfolio rehearsal on main 6630fe1e (PC, Nov 24 2026; `Inputs/portfolio/rehearsal-6630fe1e/` on the inputs
branch): a top-down still of the lake from 10 to 24 km up showed the land missing in square chunks from about 6 km out,
with houses, trees and roads floating on the water. It did not follow the boat.

## Cause

Not the world streamer: the lake is a whole-grid world, every tile is resident, and the terrain actor already makes its
chunks around the camera (`ALakeTerrainActor::UpdateChunkSet`), not the boat. The rehearsal's log agrees (4,247 to 4,420
chunks, none dropped). Two things in `ALakeTerrainActor` went by the camera's distance across the map only:

1. **Detail and build order.** A chunk's step came from its horizontal distance, so from 16 km up the chunks under the
   camera wanted step 1 and the 1 m lidar shore mesh (16 MB each while building). Chunks are built 4 at a time and
   uploaded 3 a frame, and the still is taken after a 10 s warm-up (600 frames), so about 1,800 of the frame's 4,300
   chunks could be in. Everything under 5 km was built first; past it (step 8) the order within the step was the map's
   order, not distance, so the half that got built came in tile blocks and the rest were holes: the checkerboard from
   about 6 km out.
2. **Cull distance.** Every chunk had a 20 km cull distance, which the renderer measures in 3D. From 16 km up that kept
   chunk centres only 12 km out across the map, and from 20 km up nothing (unless a scalability setting stretches view
   distances).

## Fix

`FarRing.h`: `AltitudeFreeM` (300 m), `ChunkViewDistance`, `ChunkCullM`. Below 300 m above the datum nothing changes, so
every view from a boat, the chase and capture cameras and photo mode under 300 m streams and draws exactly as before.
Above it:

- the height past 300 m counts toward a chunk's detail distance (`sqrt(D^2 + H^2)`), so from altitude the chunks are at
  the coarsest step, no lidar mesh, no terrain shadows (they are under a pixel);
- the cull distance grows to keep about 20 km across the map (`sqrt(20^2 + H^2)` km, set on the chunks in 500 m steps);
- builds in flight 32, uploads 32 a frame, chunks made 96 a look (the coarse chunks are a few hundred vertices; fine
  steps still count against the old 4 and 3).

Everywhere, chunks of the same step are now built nearest first (a tie-break; from a boat that changes only the order of
the build queue, not what is built).

The hand-over to the far ring and the chunk set (make and drop radii) stay horizontal, as `M_FarLand`'s burial is.

Test: `SailingSim.World.TerrainAltitude`. Check: the rehearsal's P4 still (`p4-topdown.json`, `-SailingStartAt=6500,-1750,0`,
ClearMistral, 12:00) with the whole lake's land in.
