"""Graphics G7: bakes the shore kit (WorldKit.cpp BuildShoreGeometry: riprap, jetties, the Texas City Dike, the Seawall and the G2
lidar decks on piles) into Nanite tiles, /Game/World/Baked/SM_Shore_<World>_<x>_<y>, and removes that world's stale shore
tiles. scripts/import_world.py bakes them too. Run: scripts/bake-shore.sh [World ...] (default GalvestonBay)."""
import os
import sys

import unreal

BAKED = "/Game/World/Baked"
worlds = [a for a in sys.argv[1:] if not a.startswith("-")] or ["GalvestonBay"]
for world in worlds:
    old = set(a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets(BAKED, recursive=False) if f"/SM_Shore_{world}_" in a)
    meshes = unreal.WorldKitLibrary.bake_shore(world)
    for m in meshes:
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        old.discard(m.get_path_name().split(".")[0])
    unreal.log(f"Baked the {world} shore: {len(meshes)} Nanite tiles")
    meshes = None
    for path in sorted(old):
        unreal.EditorAssetLibrary.delete_asset(path)
        unreal.log(f"Removed stale {path}")
# As import_world.py: leave without the interpreter's last garbage collection (it crashes after big bakes).
os._exit(0)
