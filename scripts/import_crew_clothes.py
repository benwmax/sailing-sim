"""Graphics G3: imports each sailor's polo (Tools/blender/build_polo.py, Artifacts/crew/<Role>_Polo.fbx) as a skeletal mesh
on the MetaHuman's skeleton: the FBX comes in as a static mesh in the outfit's space, the default T-shirt's skin weights are
transferred onto it (Geometry Script, closest point on the surface) and a skeletal mesh is made with the outfit's bones
and proportions: /Game/Crew/MetaHumans/<Role>/Clothing/SKM_<Role>_Polo. Slots go to MI_Crew_Polo, MI_Crew_PoloRib and
MI_Boat_CrewButton. Run by scripts/make-crew-clothes.sh."""
import os
import unreal

CREW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Artifacts", "crew")
LIB = unreal.EditorAssetLibrary
# The polo in the crew cloth (make_materials.py, build_crew_fabric), its buttons in the boat library.
SLOTS = {"Polo": "/Game/Crew/Fabric/MI_Crew_Polo", "Rib": "/Game/Crew/Fabric/MI_Crew_PoloRib", "Button": "/Game/Boats/Materials/MI_Boat_CrewButton"}


def log(m):
    unreal.log("Crew clothes: " + m)


for role in ("Helm", "Trimmer", "Bow"):
    fbx = os.path.join(CREW, f"{role}_Polo.fbx")
    outfit = unreal.load_asset(f"/Game/Crew/MetaHumans/{role}/Clothing/{role}_Outfits")
    if not os.path.exists(fbx) or not outfit:
        log(f"{role}: skipped (no polo or outfit)")
        continue
    folder = f"/Game/Crew/MetaHumans/{role}/Clothing"
    task = unreal.AssetImportTask()
    task.filename = fbx
    task.destination_path = folder
    task.destination_name = f"SM_{role}_PoloSource"
    task.automated = True
    task.replace_existing = True
    task.save = False
    opts = unreal.FbxImportUI()
    opts.import_mesh = True
    opts.import_as_skeletal = False
    opts.import_materials = False
    opts.import_textures = False
    opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    opts.static_mesh_import_data.combine_meshes = True
    opts.static_mesh_import_data.auto_generate_collision = False
    opts.static_mesh_import_data.convert_scene = True
    task.options = opts
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    source = unreal.load_asset(f"{folder}/SM_{role}_PoloSource")
    if not source:
        log(f"{role}: import FAILED")
        continue

    read = unreal.GeometryScriptCopyMeshFromAssetOptions()
    lod = unreal.GeometryScriptMeshReadLOD()
    polo = unreal.DynamicMesh()
    shirt = unreal.DynamicMesh()
    polo, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(source, polo, read, lod)
    shirt, outcome2 = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(outfit, shirt, read, lod)
    pb = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(polo)
    sb = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(shirt)
    log(f"{role}: polo bounds {pb.min} .. {pb.max}; outfit {sb.min} .. {sb.max}")
    t = unreal.GeometryScriptTransferBoneWeightsOptions()
    t.transfer_method = unreal.TransferBoneWeightsMethod.CLOSEST_POINT_ON_SURFACE
    t.output_target_mesh_bones = unreal.OutputTargetMeshBones.SOURCE_BONES
    unreal.GeometryScript_BoneWeights.transfer_bone_weights_from_mesh(shirt, polo, t)
    c = unreal.GeometryScriptCreateNewSkeletalMeshAssetOptions()
    c.use_mesh_bone_proportions = True
    c.enable_recompute_normals = False
    c.enable_recompute_tangents = True
    mats = {}
    for slot, lib in SLOTS.items():
        mats[slot] = unreal.load_asset(lib)
    c.materials = mats
    path = f"{folder}/SKM_{role}_Polo"
    if LIB.does_asset_exist(path):
        LIB.delete_asset(path)
    mesh, outcome3 = unreal.GeometryScript_NewAssetUtils.create_new_skeletal_mesh_asset_from_mesh(polo, outfit.skeleton, path, c)
    if mesh:
        LIB.save_loaded_asset(mesh)
    LIB.delete_asset(f"{folder}/SM_{role}_PoloSource")
    log(f"{role}: {path} {'ok' if mesh else 'FAILED'} ({outcome}, {outcome2}, {outcome3})")
