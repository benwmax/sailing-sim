# Perf 1: game-thread fixes from the PC CPU profile

The PC's profile (`docs/graphics-8/cpu-profile.md` on `boats-9-models`) found the game thread at 11 to 12 ms at Ultra 1080p
and listed nine fixes. This round makes them on the Mac, plus one the Mac's own measurement found (the crew pose).

## Measuring

`bench.json` now carries stat unit's thread times (`game_ms` is the game thread without its waits, plus `game_p99_ms`,
`render_ms`, `rhi_ms` and `gpu_frame_ms`) and `gt`, the time per frame in each named game-thread scope (`PerfScopes.h`; the
same scopes are Unreal Insights events with `-trace=cpu`). `scripts/bench-visual.sh` writes them to its CSV and the scopes
to `<csv>-gt.csv`. "Before" is main with only that instrumentation (commit a131073); "after" is this branch. Both are the
packaged Development build, `scripts/bench-visual.sh 12 <label> Medium High`, on Bean's M5 Pro.

## Before

On the Mac the render thread is the frame (9 to 21.5 ms) and the game thread was 3.9 to 5.4 ms behind it. Two thirds of
the game thread was the boat's visuals, and almost all of that was the crew pose: 1.9 ms on every view.
`ApplyCrewPose` set each of a MetaHuman's ~200 bones with `SetBoneTransformByName` in component space, and the engine rebuilds
the whole pose for each call, so the cost grows with the square of the bone count. The water's per-frame detail blend and mips were 0.3 ms
and the AI fleet's physics 0.2 to 0.65 ms.

## After

The game thread is halved: on average 4.11 to 1.98 ms on Medium and 4.95 to 2.73 ms on High. The crew pose is now 0.17 ms,
the water uploads 0.02 ms and the player's physics 0.02 ms on the game thread. The frame rate barely moves on the Mac,
because the render thread still sets the frame. High averages 51.2 to 52.4 fps, and the render thread is 0.4 ms lower
there (19.3 to 18.9 ms). Both gates hold: Medium 72.4 fps at worst (gate 60) and High 46.4 fps (gate 45). On the PC, where
the game thread is within 2.5 ms of the render thread, the same changes should count for more.

| View | Tier | game ms before | after | render ms before | after | fps before | after |
|---|---|---|---|---|---|---|---|
| beam8 | Medium | 4.09 | 1.95 | 10.75 | 10.83 | 91.7 | 91.1 |
| beam8 | High | 5.17 | 2.71 | 18.34 | 17.36 | 53.6 | 56.7 |
| beat15 | Medium | 4.12 | 1.94 | 11.35 | 10.76 | 86.9 | 91.6 |
| beat15 | High | 5.04 | 2.6 | 18.88 | 17.66 | 52.0 | 55.6 |
| storm | Medium | 4.42 | 2.15 | 13.63 | 13.61 | 72.4 | 72.4 |
| storm | High | 5.37 | 2.9 | 20.07 | 20.71 | 49.0 | 47.4 |
| marina | Medium | 4.07 | 1.92 | 11.24 | 11.14 | 87.7 | 88.5 |
| marina | High | 4.83 | 2.39 | 19.44 | 18.93 | 50.6 | 52.0 |
| coast-day | Medium | 4.1 | 2.1 | 11.51 | 11.64 | 85.7 | 84.6 |
| coast-day | High | 5.03 | 3.06 | 20.25 | 19.85 | 48.6 | 49.4 |
| coast-night | Medium | 3.91 | 1.93 | 9.34 | 9.3 | 105.9 | 106.1 |
| coast-night | High | 4.65 | 2.79 | 18.88 | 18.44 | 52.2 | 53.3 |
| gulf-sea | Medium | 4.01 | 1.94 | 9.08 | 8.94 | 108.7 | 110.5 |
| gulf-sea | High | 4.89 | 2.81 | 16.31 | 15.84 | 60.4 | 62.2 |
| helm-eye | Medium | 4.04 | 1.98 | 11.6 | 11.75 | 84.8 | 83.7 |
| helm-eye | High | 4.94 | 2.88 | 21.51 | 20.25 | 45.6 | 48.5 |
| slip | Medium | 4.2 | 2.0 | 13.06 | 12.95 | 75.4 | 76.1 |
| slip | High | 4.98 | 2.69 | 20.66 | 20.88 | 47.6 | 47.1 |
| bridge | Medium | 4.07 | 1.92 | 9.99 | 9.88 | 98.7 | 99.9 |
| bridge | High | 4.94 | 2.75 | 18.13 | 17.52 | 54.3 | 56.2 |
| crew | Medium | 4.28 | 2.12 | 13.27 | 13.12 | 74.2 | 75.1 |
| crew | High | 4.95 | 2.9 | 20.67 | 21.17 | 47.5 | 46.4 |
| marina-night | Medium | 4.05 | 1.83 | 11.98 | 11.87 | 82.4 | 83.1 |
| marina-night | High | 4.61 | 2.26 | 18.45 | 18.25 | 53.4 | 54.0 |

High, game-thread scopes averaged over the twelve views (ms per frame, before to after): boat visuals 2.26 to 0.50
(crew 1.93 to 0.17), player physics 0.14 to 0.02, water 0.50 to 0.26 (detail uploads 0.29 to 0.02), traffic 0.42 to 0.29.
The CSVs are in this folder.

## The fixes

1. **Scopes** (`PerfScopes.h`): `SAILING_PERF_SCOPE` around the pawn's physics, visuals, sails, crew, rig lines, telltales,
   sound, capture and drills; the water and its uploads; the terrain and trees; the traffic and its step; the HUD.
2. **Physics on a task** (`BoatPhysicsTask.h`): the pawn's tick (TG_PrePhysics) launches this frame's fixed 120 Hz steps
   as a task. A second tick function (TG_PostPhysics) joins it and runs the rest of the old tick. Everyone who reads or
   writes the player's boat in between (traffic manager, marina, HUD actor, water, environment, navaids and the pawn's own
   components) gets the join as a prerequisite. The game mode, which advances wind and waves, ticks before the launch.
   The AI sailboats step with `ParallelFor` inside `FTrafficSim::Step`. `FWaveField::Bands` is now rebuilt only when the
   sea changes, under a lock, and `FOcean`'s grid cache is read lock-free and filled under a lock. Neither was safe for
   two boats stepping at once. `-SailingSyncPhysics` or `sailing.AsyncPhysics 0` steps inline. Tests:
   `SailingSim.Physics.TaskStep` (task against the old loop, bit for bit, with the trim assist and the simple layout,
   120 steps per second), `SailingSim.Physics.ParallelBoatsShareTheSea`, `SailingSim.Traffic.ParallelStep` and
   `SailingSim.Smoke.AsyncPhysicsMatchesSync` (the pawn in a ticked world, inline against the task: the same boat).
3. **Sails**: they already used `UpdateMeshSection`; the update now skips the UVs, which never change.
4. **Ray tracing**: the sails, telltales, rig lines, crew skinned meshes and grooms are out of the ray-tracing scene
   (`KeepDynamicMeshesOutOfRayTracing`); the procedural hull stays.
5. **Water**: the detail maps' blend, mips and half-float packing run on a worker, for the next frame's time. The game
   thread hands the finished mips to `UpdateTextureRegions`, which enqueues them to the render thread (no
   `UpdateResource`). The FFT itself was already at 30 Hz on a worker. The blend stays per frame, so the short waves
   move smoothly instead of in 30 Hz steps. A true 30 Hz upload would need the material to blend two maps, which costs GPU on
   the Mac's High tier.
6. **Traffic early-out** with no vessels, no race and no horn sounding. The bench views all run traffic level 1 (three
   AI sailboats, two powerboats), so the gain in the table is the parallel step, not the early-out.
7. **Terrain**: the chunks' wanted detail is chosen again only after the camera has moved 20 m or half a second has
   passed (every frame while chunks are queued or building). The trees already rebinned on distance.
8. **Grooms**: brows, beards and moustaches are hidden past 8 m and the hair past 40 m, with their tick off. Eyelashes
   and fuzz were never loaded on this build.
9. **HUD**: `SSailHud` is inside an `SInvalidationPanel`. Its text attributes still poll, and the four instruments that
   draw from the live boat (compass, wind dial, minimap, trim) are volatile.
10. **Crew pose** (new): `ApplyCrewPose` writes every bone's local transform from the component-space pose in one pass,
    then marks the mesh dirty.

## Notes

- Files the PC owns: `SailboatPawn.cpp` has a split tick (`Tick` up to the launch, `TickAfterPhysics` for the rest),
  the scopes, one call at the end of `RebuildBoatVisuals` and the groom distances. `SailboatPawn.h` has two members and
  two declarations. `BoatModelVisuals.cpp` and `CrewPose.h` are untouched; the pose fix is in `CrewPose.cpp`.
- Two ensures in the packaged log at startup come from existing code (groom registration's PSO precache, the distance
  field's origin check), not from this round.
- Tests: 102 of 102 (the four above are new), `scripts/polar.sh --quick` 0 of 39 points out.
