"""Graphics G3: imports each sailor's polo (and Graphics G6: life jacket, build_vest.py: SKM_<Role>_Vest) (Tools/blender/build_polo.py, Artifacts/crew/<Role>_Polo.fbx) and deck shoes
(build_shoes.py, skinned from the feet: SKM_<Role>_Shoes) as skeletal meshes
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


SHOE_SLOTS = {"Upper": "/Game/Crew/Fabric/MI_Crew_ShoeLeather", "Sole": "/Game/Boats/Materials/MI_Boat_CrewSole", "Lace": "/Game/Boats/Materials/MI_Boat_CrewLace"}


ARM_BONES = ("upperarm", "lowerarm", "hand", "thumb", "index", "middle", "ring", "pinky")


def keep_arms_off(mesh):
    """Round 11 ("person looks like a doll"): the vest's armhole tore in seated poses. Closest-point weights from the
    T-shirt give the armhole's edge the sleeve's upper-arm weights, so the edge swung with the arm while the polo under it
    didn't. A life jacket doesn't follow the arm: every arm bone's weight goes to the clavicle on the same side."""
    bw = unreal.GeometryScript_BoneWeights
    names = {b.index: str(b.name) for b in bw.get_all_bones_info(mesh)[1]}
    clav = {n[-1]: i for i, n in names.items() if n in ("clavicle_l", "clavicle_r")}
    to = {i: clav[n[-1]] for i, n in names.items() if n.startswith(ARM_BONES) and n[-2:] in ("_l", "_r") and n[-1] in clav}
    moved = 0
    queries = unreal.GeometryScript_MeshQueries
    count = queries.get_num_vertex_i_ds(mesh) if hasattr(queries, "get_num_vertex_i_ds") else queries.get_vertex_count(mesh)
    for v in range(count):   # (ids past a gap report no weights)
        _, weights, ok = bw.get_vertex_bone_weights(mesh, v)
        if not ok or not any(w.bone_index in to for w in weights):
            continue
        merged = {}
        for w in weights:
            i = to.get(w.bone_index, w.bone_index)
            merged[i] = merged.get(i, 0.0) + w.weight
        bw.set_vertex_bone_weights(mesh, v, [unreal.GeometryScriptBoneWeight(bone_index=i, weight=x) for i, x in merged.items()])
        moved += 1
    return moved


def make(role, piece, fbx, source_mesh, slots):
    """The garment's FBX as a static mesh, the source's skin weights on it, a skeletal mesh on its skeleton."""
    folder = f"/Game/Crew/MetaHumans/{role}/Clothing"
    task = unreal.AssetImportTask()
    task.filename = fbx
    task.destination_path = folder
    task.destination_name = f"SM_{role}_{piece}Source"
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
    source = unreal.load_asset(f"{folder}/SM_{role}_{piece}Source")
    if not source:
        log(f"{role} {piece}: import FAILED")
        return
    read = unreal.GeometryScriptCopyMeshFromAssetOptions()
    lod = unreal.GeometryScriptMeshReadLOD()
    garment, o1 = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(source, unreal.DynamicMesh(), read, lod)
    donor, o2 = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(source_mesh, unreal.DynamicMesh(), read, lod)
    gb = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(garment)
    log(f"{role} {piece}: bounds z {gb.min.z:.1f}..{gb.max.z:.1f} cm")
    t = unreal.GeometryScriptTransferBoneWeightsOptions()
    t.transfer_method = unreal.TransferBoneWeightsMethod.CLOSEST_POINT_ON_SURFACE
    t.output_target_mesh_bones = unreal.OutputTargetMeshBones.SOURCE_BONES
    unreal.GeometryScript_BoneWeights.transfer_bone_weights_from_mesh(donor, garment, t)
    if piece == "Vest":
        log(f"{role} Vest: arm weights moved to the clavicles on {keep_arms_off(garment)} vertices")
    c = unreal.GeometryScriptCreateNewSkeletalMeshAssetOptions()
    c.use_mesh_bone_proportions = True
    c.enable_recompute_tangents = True
    c.materials = {slot: unreal.load_asset(path) for slot, path in slots.items()}
    path = f"{folder}/SKM_{role}_{piece}"
    if LIB.does_asset_exist(path):
        LIB.delete_asset(path)
    mesh, o3 = unreal.GeometryScript_NewAssetUtils.create_new_skeletal_mesh_asset_from_mesh(garment, source_mesh.skeleton, path, c)
    if mesh:
        LIB.save_loaded_asset(mesh)
    LIB.delete_asset(f"{folder}/SM_{role}_{piece}Source")
    log(f"{role}: {path} {'ok' if mesh else 'FAILED'} ({o1}, {o2}, {o3})")


# Graphics G6: the life jacket tailored over the polo (Tools/blender/build_vest.py), skinned from the T-shirt like the polo.
VEST_SLOTS = {"PFD": "/Game/Crew/Fabric/MI_Crew_PFDShell", "Straps": "/Game/Crew/Fabric/MI_Crew_Webbing",   # Graphics G8: woven webbing
              "Buckle": "/Game/Boats/Materials/MI_Boat_CrewBuckle", "Piping": "/Game/Boats/Materials/MI_Boat_CrewPiping"}
# PIECES=Vest (comma list) imports only those.
PIECES = [p for p in os.environ.get("PIECES", "Polo,Shoes,Vest").split(",") if p]

for role in ("Helm", "Trimmer", "Bow"):
    outfit = unreal.load_asset(f"/Game/Crew/MetaHumans/{role}/Clothing/{role}_Outfits")
    body = unreal.load_asset(f"/Game/Crew/MetaHumans/{role}/Body/SKM_{role}_BodyMesh")
    polo = os.path.join(CREW, f"{role}_Polo.fbx")
    # Graphics G8: the polo with its torso under the vest cut away (build_vest.py), where it has been made.
    if os.path.exists(os.path.join(CREW, f"{role}_PoloOpen.fbx")):
        polo = os.path.join(CREW, f"{role}_PoloOpen.fbx")
    shoes = os.path.join(CREW, f"{role}_Shoes.fbx")
    vest = os.path.join(CREW, f"{role}_Vest.fbx")
    if outfit and os.path.exists(polo) and "Polo" in PIECES:
        make(role, "Polo", polo, outfit, SLOTS)    # skinned from the T-shirt it was tailored from
    if body and os.path.exists(shoes) and "Shoes" in PIECES:
        make(role, "Shoes", shoes, body, SHOE_SLOTS)  # skinned from the feet
    if outfit and os.path.exists(vest) and "Vest" in PIECES:
        # Skinned from the T-shirt by closest point like the polo (Graphics G8 tried inpainting the weights where the nearest
        # shirt was a sleeve: the solver failed on the buckles and webbing walls and the vest went to spikes).
        make(role, "Vest", vest, outfit, VEST_SLOTS)
