"""Graphics G3: exports each MetaHuman crew body (/Game/Crew/MetaHumans/<Role>/Body/SKM_<Role>_BodyMesh) and its default
outfit (<Role>_Outfits: the T-shirt and shorts) with the skeleton to Artifacts/crew/<Role>_Body.fbx and <Role>_Outfit.fbx.
The optimized build cuts the body away under the clothes, so Tools/blender/build_polo.py tailors the polo from the
T-shirt (already fitted to that body). Run by
scripts/make-crew-clothes.sh (the full editor: the FBX exporter needs the mesh render data)."""
import os
import sys
import unreal

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Artifacts", "crew")
os.makedirs(OUT, exist_ok=True)
for role in ("Helm", "Trimmer", "Bow"):
    for path, name in ((f"/Game/Crew/MetaHumans/{role}/Body/SKM_{role}_BodyMesh", "Body"), (f"/Game/Crew/MetaHumans/{role}/Clothing/{role}_Outfits", "Outfit")):
        mesh = unreal.load_asset(path)
        if not mesh:
            unreal.log_warning(f"Crew bodies: {path} missing")
            continue
        task = unreal.AssetExportTask()
        task.object = mesh
        task.filename = os.path.join(OUT, f"{role}_{name}.fbx")
        task.automated = True
        task.replace_identical = True
        task.prompt = False
        opts = unreal.FbxExportOption()
        opts.export_morph_targets = False
        opts.level_of_detail = False
        opts.collision = False
        task.options = opts
        ok = unreal.Exporter.run_asset_export_task(task)
        unreal.log(f"Crew bodies: {role} {name} {'exported' if ok else 'FAILED'} ({type(mesh).__name__})")
# The Mac runs this in the full editor (-ExecCmds), which only quits this way; on Windows it leaves a zombie editor
# holding the asset locks (docs/windows/README.md), and run-python.ps1's commandlet returns by itself.
if sys.platform != "win32":
    os._exit(0)
