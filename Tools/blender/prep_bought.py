"""Bought-model test (docs/bought-yacht): fits a purchased sailboat model to one of our classes, for
scripts/import_boats.py `bought <Tag>` (into the git-ignored /Game/Boats/Bought/<Tag>).

The purchased file stays where it was saved (Data/Reference/raw/boats/<name>, git-ignored); this writes only
Artifacts/models/bought/SM_<Tag>B_{Hull,Mast,Boom,Rudder}.fbx and <Tag>B_sockets.json. The class's physics is
unchanged, so the model is fitted to it:
- its hull is turned bow +X, scaled so its length is the class's (Artifacts/models/<tag>.json `loa`, from
  Tools/BoatExport), its bow put at the physics bow and its keel's lowest point at the class's draft below the water;
- its objects are grouped into the four parts by a mapping file (object name substrings), and the sails (and anything
  else listed under "drop") left out: the game draws its own sails (FSailCloth) and rig lines;
- each part is written relative to the class's part origin (<Tag>_sockets.json `origins`, from build_fleet.py): it keeps
  its place on the model's hull, but the boom's forward end goes to the class's gooseneck (see ANCHORS); and every socket
  of the class is copied, renamed to the bought parts, so the rig lines and sails meet the model where the physics has
  them.
Run make-boat-models.ps1 -Parts fleet -Fleet <Tag> -NoImport first (it writes the class's json and sockets).

Mapping file (JSON): {"Hull": ["hull", "deck", "cockpit"], "Mast": ["mast"], "Boom": ["boom"], "Rudder": ["rudder"],
                      "drop": ["sail", "rope"], "bow": "auto" | "+X" | "-X" | "+Y" | "-Y",
                      "anchors": {"Mast": "keep" | "snap", "Boom": ..., "Rudder": ...}}
Objects matching nothing go with the hull. Prints what it put where.
Usage: blender -b --disable-autoexec --factory-startup -P prep_bought.py -- <source .blend/.fbx/.obj> <Tag> <mapping.json>
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

SRC, TAG, MAPPING = sys.argv[sys.argv.index("--") + 1:][:3]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = os.path.join(REPO, "Artifacts", "models")
OUT = os.path.join(MODELS, "bought")
PARTS = ("Hull", "Mast", "Boom", "Rudder")


def load_source(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=path)
        else:
            raise SystemExit(f"Unknown source format: {path}")
    # What renders in the file: hidden helpers (lights, cameras, oceans, high-poly twins) stay out.
    return [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]


def world_box(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            w = o.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        ev.to_mesh_clear()
    return lo, hi


def classify(objs, mapping):
    groups = {p: [] for p in PARTS}
    dropped = []
    for o in objs:
        name = o.name.lower()
        if any(k.lower() in name for k in mapping.get("drop", [])):
            dropped.append(o)
            continue
        part = next((p for p in ("Mast", "Boom", "Rudder") if any(k.lower() in name for k in mapping.get(p, []))), "Hull")
        groups[part].append(o)
    return groups, dropped


def apply_root(objs, m):
    """Moves objects by m, through their top-level ancestors only (a child moved with its parent and again by itself
    would move twice)."""
    roots = []
    for o in objs:
        r = o
        while r.parent is not None:
            r = r.parent
        if r not in roots:
            roots.append(r)
    for r in roots:
        r.matrix_world = m @ r.matrix_world
    bpy.context.view_layer.update()


def export_part(objs, name, origin_m):
    """Joins the part's objects into one mesh (modifiers applied), moves it so origin_m is its origin, writes the FBX."""
    bpy.ops.object.select_all(action="DESELECT")
    dg = bpy.context.evaluated_depsgraph_get()
    joined = []
    for o in objs:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        copy = bpy.data.objects.new(o.name + "_baked", me)
        bpy.context.scene.collection.objects.link(copy)
        joined.append(copy)
    for c in joined:
        c.select_set(True)
    bpy.context.view_layer.objects.active = joined[0]
    if len(joined) > 1:
        bpy.ops.object.join()
    part = bpy.context.view_layer.objects.active
    part.name = name
    part.data.transform(Matrix.Translation(-Vector(origin_m)))
    tris = sum(len(p.vertices) - 2 for p in part.data.polygons)
    bpy.ops.object.select_all(action="DESELECT")
    part.select_set(True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                             mesh_smooth_type="FACE", path_mode="COPY", embed_textures=True)
    print(f"Bought: {name} {tris} tris from {len(objs)} objects")


mapping = json.load(open(MAPPING))
spec = json.load(open(os.path.join(MODELS, f"{TAG.lower()}.json")))
fleet = json.load(open(os.path.join(MODELS, f"{TAG}_sockets.json")))
objs = load_source(SRC)
groups, dropped = classify(objs, mapping)
if not groups["Hull"]:
    raise SystemExit("No hull objects")

# Bow +X: as the mapping says, or the long axis with the mast forward of the middle.
lo, hi = world_box(groups["Hull"])
size = hi - lo
bow = mapping.get("bow", "auto")
if bow == "auto":
    along_y = size.y > size.x
    mlo, mhi = world_box(groups["Mast"]) if groups["Mast"] else (lo, hi)
    mid, mast = (lo + hi) / 2, (mlo + mhi) / 2
    fwd = (mast.y > mid.y) if along_y else (mast.x > mid.x)
    bow = ("+Y" if fwd else "-Y") if along_y else ("+X" if fwd else "-X")
yaw = {"+X": 0.0, "-X": 180.0, "+Y": -90.0, "-Y": 90.0}[bow]
# The whole scene moves for the fit (empties, mirror targets and hidden helpers too, so modifiers that refer to them
# stay right); only the spars' snaps move a part alone.
everything = list(bpy.context.scene.objects)
apply_root(everything, Matrix.Rotation(math.radians(yaw), 4, "Z"))

# Scale to the class's length, the bow at the physics bow, the keel at the draft.
lo, hi = world_box(groups["Hull"])
scale = spec["loa"] / (hi.x - lo.x)
apply_root(everything, Matrix.Scale(scale, 4))
lo, hi = world_box(groups["Hull"] + groups["Rudder"])
hlo, hhi = world_box(groups["Hull"])
apply_root(everything, Matrix.Translation(Vector((spec["hull"]["bow_x"] - hhi.x, -(hlo.y + hhi.y) / 2, -spec["draft"] - lo.z))))
print(f"Bought: {TAG} bow {bow}, scaled {scale:.3f}, {len(dropped)} objects dropped (sails, ropes)")

# Each spar on the class's own part origin (cm in the sockets json): the mast's foot, the boom's forward end, the
# rudder's leading edge.
origins = {k.replace(f"SM_{TAG}_", ""): Vector(v) / 100.0 for k, v in fleet["origins"].items()}
# By default a part stays where the model has it on its hull ("keep"), except the boom, whose forward end goes to the
# class's gooseneck ("snap": the game swings it about that point). "snap" on the mast puts its foot on the class's step,
# on the rudder its leading edge on the pivot (only fore and aft and across: its height came with the hull's fit). The
# mapping's "anchors" overrides each: {"Mast": "snap", "Boom": "keep", ...}. A rudder group holding a long tiller, or a
# boom group holding a lateen's yard, wants "keep": their boxes aren't the blade's or the boom's.
ANCHORS = {"Mast": "keep", "Boom": "snap", "Rudder": "keep"}
ANCHORS.update(mapping.get("anchors", {}))
for part, anchor in (("Mast", lambda l, h: Vector(((l.x + h.x) / 2, (l.y + h.y) / 2, l.z))),
                     ("Boom", lambda l, h: Vector((h.x, (l.y + h.y) / 2, (l.z + h.z) / 2))),
                     ("Rudder", lambda l, h: Vector((h.x, (l.y + h.y) / 2, origins["Rudder"].z)))):
    if not groups[part]:
        raise SystemExit(f"No {part} objects: name them in the mapping")
    if ANCHORS[part] == "snap":
        plo, phi = world_box(groups[part])
        apply_root(groups[part], Matrix.Translation(origins[part] - anchor(plo, phi)))
    print(f"Bought: {part} {ANCHORS[part]}")

os.makedirs(OUT, exist_ok=True)
for part in PARTS:
    export_part(groups[part], f"SM_{TAG}B_{part}", origins[part])
rename = {f"SM_{TAG}_{p}": f"SM_{TAG}B_{p}" for p in PARTS}
json.dump({"sockets": fleet["sockets"], "owner": {s: rename[o] for s, o in fleet["owner"].items()},
           "origins": {rename[k]: v for k, v in fleet["origins"].items()}},
          open(os.path.join(OUT, f"{TAG}B_sockets.json"), "w"), indent=1)
print(f"Bought: wrote {OUT}")
