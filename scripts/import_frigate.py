"""Frigate Commonwealth (docs/frigate-import/): imports the model export written by Tools/shipkit/frigate/export.py (slice 17,
docs/shipkit-17) into /Game/Boats/Frigate: every mesh of Frigate_sockets.json's `meshes` at its `asset` path (Outside/,
Decks/, Guns/), its light twin beside it as SM_<Part>_Light (the game picks hero or twin by tier and distance; a
commandlet has no static-mesh LOD subsystem), Nanite on all of them, the MI_Frigate_* material instances built from
Frigate_materials.json over M_BoatSurface's kinds and assigned by slot name, and the two json files copied to
Content/TerrainData/Ships/Commonwealth.*.json (staged loose, read by the game for her lanterns and placed copies).
No sockets: every frame the game needs is in the physics tables (CommonwealthRigData.inl, CommonwealthFramesData.inl,
FrigateGunData.inl, generated from the same json by Tools/shipkit/frigate/*_table.py).

Run headless (the PC: scripts\\windows\\run-python.ps1 import_frigate.py -ScriptArgs "<export dir>"; the Mac:
scripts/run-python.sh or the editor's -run=pythonscript) after make_materials.py has built M_BoatSurface. Args:
    <export dir>           the folder holding Outside/, Decks/, Guns/, Frigate_sockets.json, Frigate_materials.json
                           (default Artifacts/frigate-export)
    only=<a,b>             import only the meshes whose part name starts with one of these (e.g. only=Hull,Wheel)
    materials              build the MI_Frigate_* instances only (after a Frigate_materials.json change)
    nolight                skip the light twins
Ends by returning (never os._exit: zombie editors on Windows)."""
import json
import os
import shutil
import sys

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
ROOT = "/Game/Boats/Frigate"
MATERIALS = f"{ROOT}/Materials"
PARENT = "/Game/Boats/Materials/M_BoatSurface"
SHIPS = os.path.join(REPO, "Content", "TerrainData", "Ships")

# M_BoatSurface's Surface kinds (make_materials.py BOAT_SURFACE): 1 paint/gelcoat, 3 bright metal, 5 painted metal, 6 wood,
# 7 teak deck, 8 rubber, 9 rope, 10 sailcloth, 11 canvas cover, 13 black plastic, 14 webbing, 15 cabin window, 16 cast bronze.
# (17 manila and 18 laid teak need their own maps, set only on MI_Boat_Manila and MI_Boat_LaidTeak: not used here.)
# By the material's name, then the export's `kind`, then its `surface`; (surface code, metallic, grain). Grain draws the
# wood's figure along each timber's own long axis, which the export paints into the meshes' Grain colour attribute
# (export.py paint_grain; M_BoatSurface reads it): on a mesh without it the figure runs along the ship, as it did on the
# first import, where a pillar or a beam showed it as wavy bands across the timber (the PC's first gun-deck still), so the
# materials with Grain 1 want the export regenerated with the attribute (docs/frigate-import/).
BY_SURFACE = {"wood": (6, 0.0, 1.0), "deck": (7, 0.0, 1.0), "paint": (1, 0.0, 0.0), "iron": (5, 0.3, 0.0), "bright": (16, 1.0, 0.0),
              "copper": (3, 1.0, 0.0), "rope": (9, 0.0, 0.0), "canvas": (10, 0.0, 0.0), "below_decks": (6, 0.0, 1.0), "unweathered": (1, 0.0, 0.0)}
BY_KIND = {"tarpaulin": (11, 0.0, 0.0), "canvas": (11, 0.0, 0.0), "sail": (10, 0.0, 0.0), "lead": (3, 1.0, 0.0), "gilt": (16, 1.0, 0.0),
           "bronze": (16, 1.0, 0.0), "blacked": (5, 0.3, 0.0), "iron": (5, 0.3, 0.0), "sheathing": (3, 1.0, 0.0)}
BY_NAME = {"ClearGlass": (15, 0.0, 0.0), "Glass": (15, 0.0, 0.0), "Netting": (14, 0.0, 0.0), "FloorCloth": (11, 0.0, 0.0),
           "Interior": (1, 0.0, 0.0), "Shadow": (1, 0.0, 0.0), "CompassCard": (1, 0.0, 0.0), "Brick": (1, 0.0, 0.0),
           "Tin": (3, 1.0, 0.0), "Fleece": (11, 0.0, 0.0), "Horn": (1, 0.0, 0.0), "Powder": (1, 0.0, 0.0), "Pin": (5, 0.3, 0.0),
           "Sheave": (6, 0.0, 0.0), "Deadeye": (6, 0.0, 0.0), "Block": (6, 0.0, 0.0),
           "GunDeckPlanks": (7, 0.0, 1.0), "BerthDeckPlanks": (7, 0.0, 1.0), "OrlopPlanks": (7, 0.0, 1.0), "Deck": (6, 0.0, 1.0)}
# The materials Blender draws from a pattern over a 0.8 grey base (deck.planks_material, the floor cloth's squares, the
# sails' cloth): the export's base colour is that grey, so the undressed colour comes from here until the game draws the
# pattern itself (build_frigate.py DECK_PLANK holystoned pine, FloorCloth's light square; flax for the sails).
COLOUR = {"DeckPlanks": (0.42, 0.36, 0.27), "GunDeckPlanks": (0.42, 0.36, 0.27), "BerthDeckPlanks": (0.42, 0.36, 0.27),
          "FloorCloth": (0.72, 0.70, 0.64), "Sailcloth": (0.72, 0.66, 0.52), "SailclothFA": (0.75, 0.70, 0.57)}
HULL_SLOTS = ("HullBlack", "HullOchre", "HullRed", "Copper")


def surface_for(name, m):
    if name in BY_NAME:
        return BY_NAME[name]
    kind = m.get("kind")
    if kind in BY_KIND:
        return BY_KIND[kind]
    return BY_SURFACE.get(m.get("surface"), (1, 0.0, 0.0))


def build_materials(table):
    """MI_Frigate_<Material> over M_BoatSurface: the undressed colour and roughness, the kind by surface. Updated in place
    (never deleted: the meshes reference them). The wear levels (table['levels'], table['materials'][*]['wear']) are left to
    the game's Age/Care (MPC_Boat): the instance is the clean ship."""
    parent = unreal.load_asset(PARENT)
    if not parent:
        raise RuntimeError(f"{PARENT} missing: run make_materials.py (build_boat_library) first")
    for name, m in table["materials"].items():
        slot = m["slot"]
        path = f"{MATERIALS}/{slot}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            mi = unreal.load_asset(path)
        else:
            mi = ASSETS.create_asset(slot, MATERIALS, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, parent)
        col = COLOUR.get(name) or m["base_colour_linear"]
        surface, metallic, grain = surface_for(name, m)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(col[0], col[1], col[2], 1.0))
        # GrainScale 3: her timbers are seen from 2 to 6 m, where a small boat's centimetre figure has faded. Age and Care
        # (M_BoatSurface's weathering: paint chalking and wear, bare wood's checks, iron's rust in the pits) as a ship two
        # years in commission and well kept; the export's own wear levels stay unused (the PC's Nov 24 textures report).
        values = {"Roughness": float(m.get("roughness", 0.6)), "Metallic": metallic, "ClearCoat": 0.0, "NonSkid": 0.0, "Porosity": 0.0,
                  "IsHull": 1.0 if name in HULL_SLOTS else 0.0, "Grain": grain, "Surface": float(surface), "GrainScale": 3.0,
                  "Age": 2.0, "Care": 0.8}
        for pname, value in values.items():
            MEL.set_material_instance_scalar_parameter_value(mi, pname, value)
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        unreal.log(f"{slot}: surface {surface} metallic {metallic} colour {col}")
    unreal.log(f"Built {len(table['materials'])} MI_Frigate_* instances in {MATERIALS}")


def import_fbx(path, dest, name):
    asset_path = f"{dest}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("remove_degenerates", True)
    data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    ASSETS.import_asset_tasks([task])
    mesh = unreal.load_asset(asset_path)
    if not mesh:
        raise RuntimeError(f"import failed: {path}")
    return mesh


def setup(mesh, slots, triangles):
    """Nanite (the fallback by triangle share on the big parts, as the maxi's hull: Auto ignores the percentage), the
    MI_Frigate_* instance on each slot by its name. Every slot must be in the export's list for that mesh."""
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    if triangles > 100000:
        ns.set_editor_property("fallback_target", unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
        ns.set_editor_property("fallback_percent_triangles", 0.06)
    mesh.set_editor_property("nanite_settings", ns)
    wanted = set(slots)
    for index, m in enumerate(mesh.get_editor_property("static_materials")):
        slot = str(m.get_editor_property("material_slot_name")).split(".")[0]
        if slot not in wanted:
            unreal.log_warning(f"{mesh.get_name()}: slot {slot} is not in the export's list {sorted(wanted)}")
        mi = unreal.load_asset(f"{MATERIALS}/{slot}")
        if not mi:
            raise RuntimeError(f"{mesh.get_name()}: no material for slot {slot} (Frigate_materials.json has no such material)")
        mesh.set_material(index, mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)


def import_meshes(export, sockets, only, light):
    meshes = sockets["meshes"]
    done = 0
    skipped = 0
    for name, m in meshes.items():
        part = m.get("part") or name[len("SM_Frigate_"):]
        if only and not any(part.startswith(o) for o in only):
            skipped += 1
            continue
        asset = m["asset"]
        dest, base = asset.rsplit("/", 1)
        if base != name:
            raise RuntimeError(f"{name}: asset {asset} is not named after the mesh")
        mesh = import_fbx(os.path.join(export, m["file"]), dest, name)
        setup(mesh, m["slots"], int(m.get("triangles", 0)))
        b = mesh.get_bounding_box()
        unreal.log(f"Imported {asset}: {m.get('triangles')} triangles, slots {m['slots']}, bounds {b.min} .. {b.max}")
        done += 1
        twin = m.get("light")
        if light and twin:
            tmesh = import_fbx(os.path.join(export, twin["file"]), dest, f"{name}_Light")
            setup(tmesh, m["slots"], int(twin.get("triangles", 0)))
            unreal.log(f"Imported {asset}_Light: {twin.get('triangles')} triangles")
            done += 1
    unreal.log(f"Imported {done} meshes ({skipped} parts skipped by only=)")


def copy_json(export):
    os.makedirs(SHIPS, exist_ok=True)
    for src, dst in (("Frigate_sockets.json", "Commonwealth.sockets.json"), ("Frigate_materials.json", "Commonwealth.materials.json")):
        shutil.copyfile(os.path.join(export, src), os.path.join(SHIPS, dst))
        unreal.log(f"Copied {src} to Content/TerrainData/Ships/{dst}")


def main():
    args = [a for a in sys.argv[1:] if a]
    export = next((a for a in args if os.path.isdir(a)), os.path.join(REPO, "Artifacts", "frigate-export"))
    only = next((a.split("=", 1)[1].split(",") for a in args if a.startswith("only=")), None)
    sockets = json.load(open(os.path.join(export, "Frigate_sockets.json")))
    table = json.load(open(os.path.join(export, "Frigate_materials.json")))
    if sockets.get("root", ROOT) != ROOT:
        raise RuntimeError(f"the export's root is {sockets.get('root')}, the game's {ROOT}")
    build_materials(table)
    if "materials" in args:
        return
    import_meshes(export, sockets, only, light="nolight" not in args)
    if not only:
        copy_json(export)
    unreal.log("import_frigate.py done")


main()
