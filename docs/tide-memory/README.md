# The tide-step memory climb (Galveston)

## In plain English

On a coast the land moves down and up with the tide in 2 cm steps, so the water can stay at the same height for the boat.
Each step moves the shore's houses, docks, tree crowns and far coast. On Galveston Bay that is about half a million
pieces.

The game marks those pieces as "still" (Static), because the graphics engine handles still things much more cheaply.
But the engine has a rule: when a still thing moves, it throws away everything the graphics card knows about it and builds
it again from scratch. So every tide step rebuilt half a million pieces. On Windows the graphics driver's memory pool
kept about 75 to 100 MB more after each rebuild and never gave it back. That is the PC's Galveston climb of about
400 MB an hour (one step every 6 to 11 minutes). The lake has no tide, which is why it stays flat.

The fix keeps the pieces "still" for everything else, but tells the engine that a move of one of them is just a move:
it updates the position in place, the way it does for moving things, instead of rebuilding.

## Where it was

- PC trace (`Inputs/bench/membisect-galveston/trace-95220b32/`): each private-bytes step is the D3D12 allocator's unused pool
  growing at a tide step (461 to 555 MB, kept); the stationary run's steps line up with the tide steps.
- The engine: `UStaticMeshComponent::ShouldRecreateProxyOnUpdateTransform()` is `Mobility != Movable`
  (`StaticMeshSceneProxy.cpp`), and `FScene::UpdatePrimitiveTransformInternal` (`RendererScene.cpp`) then runs
  `RemovePrimitive` + `AddPrimitive`: a new scene proxy, new GPU-scene instance data, new ray-tracing instances and new cached
  draw commands for every moved Static mesh. The PC's trace saw those (`AddPrimitiveCommand`/`RemovePrimitive` at a step).
- The terrain actor's kept components are Static on purpose (`docs/tide-hitch/`: a movable instanced mesh is re-culled as
  dynamic every frame), and `ALakeTerrainActor::FollowActor` moves them with `ApplyWorldOffset(..., false)`, which marks
  the render transform dirty.

## The fix

`KeptComponents.h`: `USailingKeptMeshComponent` (a `UStaticMeshComponent`) and `USailingKeptInstancesComponent` (a
`UInstancedStaticMeshComponent`) return false from `ShouldRecreateProxyOnUpdateTransform`. The renderer then takes the
in-place path a Movable mesh takes (`SetTransform`, the distance-field and Lumen updates, the GPU scene upload). That is safe
for the engine's static mesh proxy: it always draws through the GPU scene (`bStaticElementsAlwaysUseProxyPrimitiveUniformBuffer`
is set in `FStaticMeshSceneProxy`'s constructor, so the cached draw commands don't hold the transform), and cached ray-tracing
instances take their transforms from the GPU scene. The components stay Static for culling, shadows and everything else.

The kept components are made as these classes: the crown proxies and tiles (and the tile clones of `TreeMid`/`TreeFar`), the
houses and docks, the far ring's tiles, and the terrain actor's baked kit tiles (`SpawnKitTiles` with a keeper).
`-SailingTideRecreate` gives the engine's behaviour back, to compare.

Test: `SailingSim.Coast.KeptKeepsProxy` (the kept classes keep their proxy through a step and stand at the new place; a plain
Static mesh still doesn't; the switch).

## To check (PC, before merging)

1. Memory: the tide baseline (`-SailingTideStepEvery=20`, stationary Galveston, private bytes and `D3D12AllocatorUnused` per
   minute, 15-20 min) on this branch, then the same with `-SailingTideRecreate`. Main grew about 75 MB a step.
2. The step's hitch: peak render-thread ms per step (`docs/tide-hitch/`'s table). It should be no worse, likely better.
3. Looks: Ultra stills of the Kemah shore and docks before and after a few forced steps, and a dusk still (ray-traced
   reflections and Lumen on the houses and crowns), against main. Watch for shadows or reflections left behind by 2-3 cm.
4. `SailingSim.Coast.*`, Smoke, and the gate's coast views on both machines.

## Known, not changed here

- The shore edge models (`ALakeTerrainActor`'s bulkheads, limestone, timber and the scatter beside them) are Static and
  `SetupAttachment` to the movable root, which the engine refuses (the "is not static, cannot attach" warnings at load), so
  they don't follow the tide at all. On Galveston they can end up a tide's range off the ground. Keeping them
  (`KeepWithActor`, kept class, with their world-space instances made relative) is the follow-up.
- Longer term the tide should move the water, not the land (a handful of things instead of half a million). See the large-world
  plan.
