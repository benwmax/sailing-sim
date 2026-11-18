# #798 Track C shore edges: Ultra stills at the bulkhead lot, clay bank and club beach (PC)

**Build:**

- PR #798 branch tip `0ea7a5fa` ("the kit shore edges on inland lakes only; the coasts keep the tile's bulkhead"), newer than the Mac's asset commit c23b12cd.
- Merged locally with main `f0158285` (merge `3811c732`, never pushed), in a fresh worktree, then `git lfs pull` (exit 0).
- MSVC build: Succeeded, 0 errors.
- The worktree was removed afterwards; the main checkout is clean.

**Stills:**

- The `env-bulkhead-*`, `env-clay-bank-*` and `env-club-beach-*` rows (5, 15 and 60 m) of the branch's `Tools/envloop/stations.csv`.
- Run uncooked through `scripts\windows\run-game.ps1` at 1920x1080 with `-SailingQuality=Ultra -ForceRes -SailingScreenPct=100`, like the Track 0 station stills.
- Exact command lines are in `args.csv`. Taken 08:16-08:22 local, Nov 18. Bean's Saved was held aside and restored.

**Contents:** `stills/` (9 PNGs), `crops/` (1:1 crops and `compare-05m/15m/60m.png`, side by side with the same stations from the #797 run, which is main f0158285 plus the Track A ground), `material-log.txt`.

## Finding: M_ShoreEdge fails to compile on D3D, so every edge piece draws with the default material

The game builds the edge kit ("Shore edges: 23673 pieces (9063 lot wall segments on 674 lots, 14715 natural shore nodes), 21 of 21 meshes"). But its material doesn't compile on Windows. The log, verbatim (`material-log.txt`):

```
LogMaterial: Warning: [AssetLog] D:\dev\ss-fix-wt\pr798\Content\World\Edges\M_ShoreEdge.uasset: Failed to compile Material for platform PCD3D_SM6, Default Material will be used in game.
	(Node Add) Arithmetic between types LWCVector3 and float4 are undefined
	(Node Add) Invalid input types: FWSVector3, FWSVector3
LogMaterial: Warning: Material /Game/World/Edges/M_ShoreEdge.M_ShoreEdge missing usage flag Nanite! Default Material will be used in game.
LogMaterial: Warning: Material /Game/World/Edges/M_ShoreEdge.M_ShoreEdge missing usage flag InstancedStaticMeshes! Default Material will be used in game.
```

There are two separate problems:

1. **An Add node** adds a world position (LWC vector3) to a float4. This looks like `MPC_World.RenderOrigin` added without a component mask; make_materials.py's `node()` does the same addition with a mask.
2. **Usage flags:** the material lacks `bUsedWithNanite` and `bUsedWithInstancedStaticMeshes`, though the edge meshes are Nanite ISMs.

Either one alone gives the default material.

**What it looks like:**

- **Bulkhead lot, 5 m (`crops/crop-bulkhead-05m.png`):** the lot walls along the water are grey open-topped box shells with the engine's checker pattern and black shadowed inner faces. In the #797 run of the same station, the bulkhead is a smooth concrete cap and step.
- **Bulkhead lot, 15 m (`crops/crop-bulkhead-15m.png`):** the same checker shells along the whole waterline.
- **Clay bank and club beach:** the natural-shore nodes read as smooth, untextured tan banks (`compare-05m.png`). This is also because #798 doesn't carry #797's ground, so its ground is the old flat palette.

**Mac:** these lines were logged on the PC (D3D SM6). Whether Metal compiles the Add node isn't known here, but the missing usage flags apply on every platform.

**Other log lines:** the run's other errors are the engine's DoubleFloat OriginMax handled ensure seen in every PC run, and the usual SkyLightEnvMapSample warning.
