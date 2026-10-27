"""Graphics G6: bakes the G2 houses (Content/TerrainData/<World>.houses, Tools/terrain/build_houses.py) into Nanite tiles,
/Game/World/Baked/SM_Houses_<World>_<x>_<y>, and removes stale house tiles. scripts/import_world.py bakes them too.
Run: UnrealEditor-Cmd SailingSim.uproject -run=pythonscript -script=scripts/bake_houses.py (scripts/make-houses.sh)."""
import os

import unreal

BAKED = "/Game/World/Baked"
# HOUSES_WORLDS=RayHubbard bakes (and prunes) only those worlds' tiles.
worlds = [w for w in os.environ.get("HOUSES_WORLDS", "RayHubbard,GalvestonBay").split(",") if w]
old = set(a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets(BAKED, recursive=False)
          if "/SM_Houses_" in a and any(f"/SM_Houses_{w}_" in a for w in worlds))
for world in worlds:
    meshes = unreal.WorldKitLibrary.bake_houses(world)
    for m in meshes:
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        old.discard(m.get_path_name().split(".")[0])
    # Their distance fields and Lumen cards into the DDC before leaving (else every uncooked run rebuilds them).
    unreal.WorldKitLibrary.finish_mesh_builds()
    unreal.log(f"Baked the {world} houses: {len(meshes)} Nanite tiles")
    meshes = None
for path in sorted(old):
    unreal.EditorAssetLibrary.delete_asset(path)
    unreal.log(f"Removed stale {path}")
# As import_world.py: leave without the interpreter's last garbage collection (it crashes after big bakes on the Mac).
# Not on Windows: there os._exit trips an engine ensure at exit and leaves an editor that can't be killed (docs/windows).
import sys
if sys.platform != "win32":
    os._exit(0)
