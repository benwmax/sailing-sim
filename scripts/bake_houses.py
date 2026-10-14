"""Graphics G6: bakes the G2 houses (Content/TerrainData/<World>.houses, Tools/terrain/build_houses.py) into Nanite tiles,
/Game/World/Baked/SM_Houses_<World>_<x>_<y>, and removes stale house tiles. scripts/import_world.py bakes them too.
Run: UnrealEditor-Cmd SailingSim.uproject -run=pythonscript -script=scripts/bake_houses.py (scripts/make-houses.sh)."""
import os

import unreal

BAKED = "/Game/World/Baked"
old = set(a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets(BAKED, recursive=False) if "/SM_Houses_" in a)
for world in ("RayHubbard", "GalvestonBay"):
    meshes = unreal.WorldKitLibrary.bake_houses(world)
    for m in meshes:
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        old.discard(m.get_path_name().split(".")[0])
    unreal.log(f"Baked the {world} houses: {len(meshes)} Nanite tiles")
    meshes = None
for path in sorted(old):
    unreal.EditorAssetLibrary.delete_asset(path)
    unreal.log(f"Removed stale {path}")
# As import_world.py: leave without the interpreter's last garbage collection (it crashes after big bakes).
os._exit(0)
