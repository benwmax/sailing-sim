"""Wide World Rendering PR 1 (docs/world-far): builds the far coast ring's Nanite tiles from <World>.far
(UWorldKitLibrary::BakeFarRing -> /Game/World/Far/SM_Far_<World>_<row>_<col>) and removes that world's stale tiles.
`--ultra` builds the 30 m ring from <World>.far30 into /Game/World/Far30 (SM_Far30_<World>_...), drawn on Ultra.
Run: scripts/make-far-ring.sh [World ...]."""
import sys

import unreal

ULTRA = "--ultra" in sys.argv
VARIANT = "30" if ULTRA else ""
FAR = f"/Game/World/Far{VARIANT}"
worlds = [a for a in sys.argv[1:] if not a.startswith("-")] or ["GalvestonBay", "GulfPassage"]
for world in worlds:
    old = set()
    if unreal.EditorAssetLibrary.does_directory_exist(FAR):
        old = set(a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets(FAR, recursive=False) if f"/SM_Far{VARIANT}_{world}_" in a)
    meshes = unreal.WorldKitLibrary.bake_far_ring(world, VARIANT)
    for m in meshes:
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        old.discard(m.get_path_name().split(".")[0])
    unreal.log(f"Far ring {world}{' (30 m)' if ULTRA else ''}: {len(meshes)} Nanite tiles saved")
    meshes = None
    for path in sorted(old):
        unreal.EditorAssetLibrary.delete_asset(path)
        unreal.log(f"Removed stale {path}")
