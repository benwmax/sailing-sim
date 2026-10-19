"""Wide World Rendering PR 1 (docs/world-far): builds the far coast ring's Nanite tiles from <World>.far
(UWorldKitLibrary::BakeFarRing -> /Game/World/Far/SM_Far_<World>_<row>_<col>) and removes that world's stale tiles.
Run: scripts/make-far-ring.sh [World ...]."""
import sys

import unreal

FAR = "/Game/World/Far"
worlds = [a for a in sys.argv[1:] if not a.startswith("-")] or ["GalvestonBay", "GulfPassage"]
for world in worlds:
    old = set()
    if unreal.EditorAssetLibrary.does_directory_exist(FAR):
        old = set(a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets(FAR, recursive=False) if f"/SM_Far_{world}_" in a)
    meshes = unreal.WorldKitLibrary.bake_far_ring(world)
    for m in meshes:
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        old.discard(m.get_path_name().split(".")[0])
    unreal.log(f"Far ring {world}: {len(meshes)} Nanite tiles saved")
    meshes = None
    for path in sorted(old):
        unreal.EditorAssetLibrary.delete_asset(path)
        unreal.log(f"Removed stale {path}")
