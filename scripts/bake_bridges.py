"""Near-shore phase 3: bakes the bridges (WorldKit.cpp BuildBridgeGeometry) into Nanite tiles,
/Game/World/Baked/SM_Bridges_<World>_<x>_<y>, and removes that world's stale bridge tiles. scripts/import_world.py bakes
them too. Run: scripts/windows/run-python.ps1 scripts/bake_bridges.py (BRIDGES_WORLDS=RayHubbard,... picks the worlds)."""
import os
import sys

import unreal

BAKED = "/Game/World/Baked"
worlds = [w for w in os.environ.get("BRIDGES_WORLDS", "RayHubbard,GalvestonBay,GulfPassage").split(",") if w]
for world in worlds:
    old = set(a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets(BAKED, recursive=False) if f"/SM_Bridges_{world}_" in a)
    meshes = unreal.WorldKitLibrary.bake_bridges(world)
    for m in meshes:
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        old.discard(m.get_path_name().split(".")[0])
    # Their distance fields and Lumen cards into the DDC before leaving (as bake_houses.py).
    unreal.WorldKitLibrary.finish_mesh_builds()
    unreal.log(f"Baked the {world} bridges: {len(meshes)} Nanite tiles")
    meshes = None
    for path in sorted(old):
        unreal.EditorAssetLibrary.delete_asset(path)
        unreal.log(f"Removed stale {path}")
# As import_world.py: leave without the interpreter's last garbage collection (it crashes after big bakes on the Mac).
# Not on Windows: there os._exit trips an engine ensure at exit and leaves an editor that can't be killed (docs/windows).
if sys.platform != "win32":
    os._exit(0)
