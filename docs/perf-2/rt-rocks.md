# Perf 2, step 3: the coast's boulders leave the ray-tracing scene

Coast-day on High was the one view where cutting GPU work moved nothing: its GPU frame was 16 ms against a 20.7 ms frame,
and the render thread spent most of the frame waiting on its tasks (an Insights trace, `-trace=cpu,frame`, and the CSV
profiler: `EventWait/Visibility` 14.9 ms). Lumen in software (`-SailingLumenHW=0`) took the view from 48.3 to 53.3 fps:
it was the hardware ray-tracing scene, which gathers every instance in it each frame. Galveston Bay has 980,000
instances; the trees and reeds were already kept out of it (`bVisibleInRayTracing = false`), but the shore and pier
riprap (`ABridgesActor`, 324,000 boulders in six instanced meshes) were not. They are now. They still render, cast
virtual shadows and are seen by Lumen's screen traces; only Lumen's hardware rays miss them.

Same-session A/B (High, 12 s; main + #71 + #72 against that plus this):

| View | before | after |
|---|---|---|
| coast-day | 48.3, 48.2 | 52.7, 52.1 |
| slip | 51.6 | 51.4 |

Gate (`--scope world --merge` #71 #72 this): pass, 130 tests green (`visual-bench-p2-rtrocks.csv`): coast-day High 53.0,
coast-night High 57.9 (49.1 at the Perf 2 baseline), bridge 61.2. Stills: `rt-rocks/coast-day-before.png` and
`-after.png`: the same image apart from foam and puffs.
