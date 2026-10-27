"""Loads the house tiles of HOUSES_WORLDS (default RayHubbard) and waits for their derived data (distance fields, Lumen
cards) to finish building into the local DDC, so uncooked runs don't rebuild them (bake_houses.py does this after a bake).
Run: scripts/windows/run-python.ps1 scripts/warm_house_tiles.py"""
import os

import unreal

worlds = [w for w in os.environ.get("HOUSES_WORLDS", "RayHubbard").split(",") if w]
paths = [a.split(".")[0] for a in unreal.EditorAssetLibrary.list_assets("/Game/World/Baked", recursive=False)
         if any(f"/SM_Houses_{w}_" in a for w in worlds)]
meshes = [unreal.EditorAssetLibrary.load_asset(p) for p in paths]
unreal.WorldKitLibrary.finish_mesh_builds()
unreal.log(f"Warmed {len(meshes)} house tiles")
