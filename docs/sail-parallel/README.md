# The sails' cloth in parallel (Oct 24 2026)

The Marseille lane measured main's sails at about 1.5 ms of game thread and suspected them in a fps drop. The sail update
ran each sail in turn on the game thread:

1. the cloth step (`FSailCloth::Step`);
2. normals and tangents;
3. the render grid's refinement (#267's 73 × 46 Catmull-Rom grid);
4. the procedural mesh's update.

## Change

`ASailboatPawn::UpdateSailCloths`:

- Steps 1–3 touch only each sail's own `FSailCloth` and inputs read before, so the sails run side by side on the task
  graph (`ParallelFor`).
- The meshes' updates stay on the game thread, after.
- The maths is the same, so the look doesn't change. `UpdateSailCloth` (one sail) is the same path with one entry.
- `cloth_cpu_ms` in bench.json is now the parallel section's wall time (step, normals, tangents and the render grid). It
  used to be the steps' summed time.

## Measured

Uncooked, High, the J/22 under spinnaker (three sails) running at TWA 140 in 10 kn, three runs each, from the bench's
game-thread slices:

| | `sails` | game thread | fps |
| --- | --- | --- | --- |
| main | 1.36 ms | 4.86 ms | 62.3 |
| parallel | 0.90 ms | 4.31 ms | 62.2 |

The fps doesn't move in that view, which is GPU-bound at 62. The saving shows where the game thread is the limit. What
remains (about 0.2 ms) is the three procedural mesh updates, which have to be on the game thread.
