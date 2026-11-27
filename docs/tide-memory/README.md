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
instances take their transforms from the GPU scene. The baked kit tiles and the tree models are Nanite, which has its own
proxy and draws entirely through the GPU scene, so the same holds for them. The components stay Static for culling and
everything else.

Two things are not proven and are what the look check is for:

- Ray tracing (High and Ultra): that a cached primitive's ray-tracing instances follow an in-place move. If they didn't,
  reflections and hardware Lumen hits from the houses and crowns would stay where they were, and with nothing rebuilding
  them any more the gap would grow to the whole tide range.
- Shadows: the kept casters use `ShadowCacheInvalidationBehavior::Static`, so an in-place move may not invalidate their
  cached virtual shadow map pages the way the old rebuild did. The sun turns in 0.05 degree steps, which re-renders its
  pages about every 12 s, so a stale shadow should be short-lived; no shadowing local lights sit on the shore.

If either shows, the fallback is to rebuild only on a big move (or the plan's longer-term fix, moving the water instead).

The kept components are made as these classes: the crown proxies and tiles (and the tile clones of `TreeMid`/`TreeFar`), the
houses and docks, the far ring's tiles, and the terrain actor's baked kit tiles (`SpawnKitTiles` with a keeper).
`-SailingTideRecreate` gives the engine's behaviour back, to compare. It is read when each component is kept, so give it at
launch (and `SailingSim.Coast.KeptKeepsProxy` fails under it, as it should). A Static component kept as a plain class still
rebuilds on every step, so any new `KeepWithActor` caller must make one of the kept classes.

Test: `SailingSim.Coast.KeptKeepsProxy` (the kept classes keep their proxy through a step and stand at the new place; a plain
Static mesh still doesn't; the switch). `scripts/test.sh` runs `-nullrhi`, where the proxy checks are skipped with a warning;
they need one run with a renderer (an error there if the proxies are missing).

## To check (PC, before merging)

1. Memory: the tide baseline (`-SailingTideStepEvery=20`, stationary Galveston, private bytes and `D3D12AllocatorUnused` per
   minute, 15-20 min) on this branch, then the same with `-SailingTideRecreate`. Main grew about 75 MB a step.
2. The step's hitch: peak render-thread ms per step (`docs/tide-hitch/`'s table). It should be no worse, likely better.
3. Looks, with a large forced step so a lag can be seen: `-SailingTideStepEvery=30 -SailingTideStepSize=1` (the land drops
   and rises 1 m every 30 s). Ultra stills of the Kemah shore and docks in both halves, each pair taken within a few seconds of
   each other so the sun hasn't turned a step (the stale-shadow case), plus the ray-tracing debug view and a dusk still (reflections and Lumen on the houses and crowns),
   against main and `-SailingTideRecreate`. Look for shadows, reflections or lighting left 1 m off.
4. `SailingSim.Coast.*`, Smoke, and the gate's coast views on both machines, and `SailingSim.Coast.KeptKeepsProxy` once with a
   renderer (the editor without `-nullrhi`) so its proxy checks run.

## Known, not changed here

- The shore edge models (`ALakeTerrainActor::PlaceShoreEdges`: bulkheads, limestone, timber and the natural-shore scatter)
  are Static and `SetupAttachment` to the movable root, which the engine refuses (the "is not static, cannot attach" warnings
  at load). Today that is harmless: they are only placed on inland lakes (`ShoreEdgesOn`: the coasts wait for a region pack
  of their own), where the terrain actor never steps, and a re-centre shifts them with everything else. A coast pack (the
  Florida map) would need them kept like the rest (`KeepWithActor`, kept class): a separate draft PR.
- Longer term the tide should move the water, not the land (a handful of things instead of half a million). See the large-world
  plan.
