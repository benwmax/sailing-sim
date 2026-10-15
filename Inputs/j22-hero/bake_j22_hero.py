"""Bakes the J/22 hero model's procedural materials to PBR texture maps and exports the parts for Unreal and the web.

    blender -b -P bake_j22_hero.py -- <j22_hero.blend> <out dir> [--res 4096]

Baked groups (unique UVs from Smart UV Project): Hull (hull, keel, registration), DeckMould (deck, cockpit liner,
cabin trunk), Rudder, Teak (toe rails, coaming caps, handrails, drop board). Each gets T_J22H_<Group>_D (base colour),
_R (roughness) and _N (tangent-space normal, OpenGL green-up; Unreal wants DirectX, so flip green on import).
The other parts keep flat material values (listed in materials.json). Writes fbx/SM_J22H_<Group>.fbx, j22_hero.glb
(2K JPEG textures, for the web viewer) and materials.json.
"""
import json
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:]
BLEND, OUT = ARGS[0], ARGS[1]
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 4096
TEX = os.path.join(OUT, "textures")
FBX = os.path.join(OUT, "fbx")
os.makedirs(TEX, exist_ok=True)
os.makedirs(FBX, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 4
sc.render.bake.margin = 12


# ---------------------------------------------------------------- sockets for the game
# The game hangs live ropes (FRigLine) and cloth sails (FSailCloth) off named sockets on SM_<Tag>_Hull/Mast/Boom/Rudder,
# so the hero model ships the same names, measured off its own fittings. Body frame: y to starboard = -Blender y; cm.
from mathutils import Matrix, Vector  # noqa: E402


def _bb(name):
    o = bpy.data.objects[name]
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _c(name):
    lo, hi = _bb(name)
    return (lo + hi) / 2


def _top(name, dz=0.0):
    lo, hi = _bb(name)
    return Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z + dz))


def _curve_end(name, highest=True):
    o = bpy.data.objects[name]
    pts = [o.matrix_world @ p.co.xyz for sp in o.data.splines for p in (list(sp.points) + list(sp.bezier_points))]
    return max(pts, key=lambda v: v.z) if highest else min(pts, key=lambda v: v.z)


SOCKETS = {}


def sock(name, v):
    SOCKETS[name] = [round(v.x * 100, 2), round(-v.y * 100, 2), round(v.z * 100, 2)]


mast_lo, mast_hi = _bb("Mast")
step = _top("MastStep")
mast_x = (mast_lo.x + mast_hi.x) / 2
sock("MastStep", Vector((mast_x, 0, mast_lo.z)))
for tag, side in (("S", -1), ("P", 1)):
    sock(f"ChainplateUpper_{tag}", _top(f"Chainplate_{side}_strap"))
    sock(f"ChainplateLower_{tag}", _top(f"ChainplateAft_{side}_strap"))
    sock(f"JibWinch_{tag}", _top(f"Winch_{side}_top"))
    sock(f"JibTailer_{tag}", _top(f"Winch_{side}_top", 0.04))
    sock(f"JibLead_{tag}", _c(f"JibCar_{side}_sheave"))
    sock(f"SpreaderTip_{tag}", _c(f"SprTip_{side}_end"))
sock("ForestayTack", _c("StemPin_pin"))
bs = [_c(n) for n in ("BS_eye_1_loop", "BS_eye_-1_loop")]
sock("BackstayPlate", (bs[0] + bs[1]) / 2)
sock("BowCleat", _top("BowCleat_horn"))
tlo, thi = _bb("TravelerBar")
sock("Traveler_C", Vector(((tlo.x + thi.x) / 2, 0, thi.z + 0.02)))
sock("Traveler_S", Vector(((tlo.x + thi.x) / 2, tlo.y + 0.05, thi.z + 0.02)))
sock("Traveler_P", Vector(((tlo.x + thi.x) / 2, thi.y - 0.05, thi.z + 0.02)))
# the lazy sheet's pass over the cabin top: a little above the cabin, a hand's width aft of the mast
clo, chi = _bb("Cabin")
sock("LazySheetVia", Vector((mast_x - 0.35, 0, chi.z + 0.06)))
sock("Hounds", _curve_end("Forestay"))
lt = _curve_end("Lower_1")
sock("LowerTang", Vector((lt.x, 0, lt.z)))
sock("MastheadAft", _c("Masthead_bstang"))
sock("MastBase", _c("Vang_tang"))
sock("Boom_Vang", _c("Vang_bail"))
sock("Boom_Mainsheet", _c("MainsheetHigh_sheave"))
sock("Boom_Clew", _c("BoomEnd_outhaul"))
glo, ghi = _bb("Gooseneck_vpin")
GOOSE = (glo + ghi) / 2
tl_lo, tl_hi = _bb("Tiller")
sock("TillerEnd", Vector((tl_hi.x, 0, tl_hi.z - 0.02)))
rh_lo, rh_hi = _bb("RudderHead")
stock_x = rh_hi.x - 0.02
sock("RudderStock", Vector((stock_x, 0, tl_lo.z + 0.03)))
sock("RudderPivot", Vector((stock_x, 0, 0)))

# crew attach points (crew-motion plan): hands, feet, ducking. The lesson boat has no lifelines or stanchions.
ux_lo, ux_hi = _bb("TillerExt")
sock("TillerExtTip", Vector((ux_lo.x, 0, (ux_lo.z + ux_hi.z) / 2)) if ux_lo.x < tl_lo.x + 0.4 else Vector((ux_hi.x, 0, ux_hi.z)))
sock("TillerExtUJ", _c("ExtUJ"))
sock("MainsheetCam", (_c("MainCam_cam-1") + _c("MainCam_cam1")) / 2)
for tag, side in (("S", -1), ("P", 1)):
    for k in (0, 1):
        sock(f"JibCam{k}_{tag}", (_c(f"Cam_{side}_{k}_cam-1") + _c(f"Cam_{side}_{k}_cam1")) / 2)
    sock(f"HandholdCabin_{tag}", _top(f"Handrail_{side}"))
    sock(f"HandholdCoaming_{tag}", _top(f"CoamingCap_{side}"))


def _down(objname, x, y):
    o = bpy.data.objects[objname]
    inv = o.matrix_world.inverted()
    hit, loc, nrm, _ = o.ray_cast(inv @ Vector((x, y, 4.0)), (inv.to_3x3() @ Vector((0, 0, -1))).normalized())
    return o.matrix_world @ loc if hit else None


ck_lo, ck_hi = _bb("Cockpit")
xm = (ck_lo.x + ck_hi.x) / 2
sole = _down("Cockpit", xm, 0.0)
if sole:
    sock("CockpitSole", sole)
for tag, side in (("S", -1), ("P", 1)):
    # seat top: the highest cockpit surface between the centreline and the coaming at mid-cockpit
    best = None
    for yy in [k * 0.02 for k in range(8, 40)]:
        h = _down("Cockpit", xm, side * yy)
        if h and h.z > 0.3 and (best is None or abs(h.z - 0.40) < abs(best.z - 0.40)):
            best = h
    if best:
        sock(f"Seat_{tag}", best)
        # foot brace: the inboard edge of the seat front on this side
        edge = None
        for yy in [k * 0.01 for k in range(5, 60)]:
            h = _down("Cockpit", xm, side * yy)
            if h and h.z > best.z - 0.03:
                edge = h
                break
        if edge:
            sock(f"FootBrace_{tag}", edge - Vector((0, 0, 0.05)))
    cl = _bb(f"CoamingCap_{side}")
    yd = (cl[1].y if side > 0 else cl[0].y) + side * 0.12
    sd = _down("Deck", xm, yd)
    if sd:
        sock(f"SideDeck_{tag}", sd)
# boom: lowest point over the cockpit (the swing is about the gooseneck's vertical pin, so this is the radius too)
blo, bhi = _bb("Boom")
sock("Boom_LowOverCockpit", Vector((xm, 0, blo.z)))


def owner(n):
    if n in ("Hounds", "LowerTang", "MastheadAft", "MastBase") or n.startswith("SpreaderTip"):
        return "SM_J22H_Mast"
    if n.startswith("Boom_"):
        return "SM_J22H_Boom"
    if n.startswith("TillerExt"):
        return "SM_J22H_Rudder"
    if False:
        return "SM_J22H_Boom"
    if n in ("TillerEnd", "RudderStock", "RudderPivot"):
        return "SM_J22H_Rudder"
    return "SM_J22H_Hull"


PIVOTS = {"SM_J22H_Hull": Vector((0, 0, 0)), "SM_J22H_Mast": Vector((mast_x, 0, mast_lo.z)),
          "SM_J22H_Boom": Vector((GOOSE.x, 0, GOOSE.z)), "SM_J22H_Rudder": Vector((stock_x, 0, 0))}

# which game part each built object belongs to; None = live in the game (ropes, wires, sails, vang) or loose dressing
ROPE_LIKE = ("Halyard", "HalTail", "MainTail", "Mainsheet_", "JibSheet", "JibTail", "Bridle", "Backstay", "Forestay",
             "Upper_", "Lower_", "Vang_", "BS_cascade", "JibBowline")
BOOM_PARTS = ("Boom", "BoomEnd", "MainBail", "MainsheetHigh", "Gooseneck_boomcap", "Gooseneck_fork", "Gooseneck_hpin",
              "Gooseneck_cunnhook", "Gooseneck_reefhook")


def game_part(o):
    n = o.name
    cols = {c.name for c in o.users_collection}
    if "Sails" in cols or n.startswith(ROPE_LIKE) or "Rigging" in cols:
        return None
    if "Rudder" in cols:
        return "SM_J22H_Rudder"
    if "Rig" in cols:
        if n.startswith(("TB_", "BS_eye")):
            return "SM_J22H_Hull"
        return "SM_J22H_Boom" if n.startswith(BOOM_PARTS) else "SM_J22H_Mast"
    return "SM_J22H_Hull"


GAME = {o.name: game_part(o) for o in bpy.data.objects if o.type in ("MESH", "CURVE", "FONT")}
if os.environ.get("J22H_SOCKETS_ONLY"):
    from collections import Counter
    print("SOCKETS", json.dumps(SOCKETS))
    json.dump({"sockets": SOCKETS, "owner": {n: owner(n) for n in SOCKETS},
               "origins": {k: [round(v.x * 100, 2), round(-v.y * 100, 2), round(v.z * 100, 2)] for k, v in PIVOTS.items()},
               "live": {"ropes": "FRigLine (BoatModelVisuals.cpp) from these sockets", "sails": "FSailCloth; hero sail maps on UV1"}},
              open(os.path.join(OUT, "J22H_sockets.json"), "w"), indent=1)
    print("PARTS", dict(Counter(GAME.values())))
    sys.exit(0)


def select(objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def make_mesh(o):
    if o.type != "MESH":
        select([o])
        bpy.ops.object.convert(target="MESH")
        o = bpy.context.view_layer.objects.active
    return o


def join(name, names):
    objs = [make_mesh(bpy.data.objects[n]) for n in names if n in bpy.data.objects]
    objs = [bpy.data.objects[o.name] for o in objs]
    select(objs)
    bpy.ops.object.make_single_user(object=True, obdata=True)
    for o in objs:
        for m in o.modifiers:
            pass
    select(objs)
    for o in objs:
        bpy.context.view_layer.objects.active = o
        for m in list(o.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
    select(objs)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


def unwrap(ob):
    select([ob])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.002, area_weight=1.0, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.002, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_group(name, ob, res):
    """Bake every material on ob into one set of maps, then give ob a single material that uses them."""
    unwrap(ob)
    first = next((sl.material for sl in ob.material_slots if sl.material), None)
    for sl in ob.material_slots:
        if sl.material is None:
            sl.material = first
    maps = {}
    for kind, btype, cs in (("D", "DIFFUSE", "sRGB"), ("R", "ROUGHNESS", "Non-Color"), ("N", "NORMAL", "Non-Color")):
        img = bpy.data.images.new(f"T_J22H_{name}_{kind}", res, res, alpha=False, float_buffer=False)
        img.colorspace_settings.name = cs
        if kind == "N":
            img.generated_color = (0.5, 0.5, 1.0, 1.0)
        nodes = []
        for slot in ob.material_slots:
            nt = slot.material.node_tree
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = img
            nt.nodes.active = n
            nodes.append((nt, n))
        select([ob])
        kw = dict(type=btype, use_clear=True, margin=12)
        if btype == "DIFFUSE":
            kw["pass_filter"] = {"COLOR"}
        bpy.ops.object.bake(**kw)
        path = os.path.join(TEX, img.name + ".png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        for nt, n in nodes:
            nt.nodes.remove(n)
        maps[kind] = img
    m = bpy.data.materials.new(f"J22H_{name}")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    d = nt.nodes.new("ShaderNodeTexImage"); d.image = maps["D"]
    r = nt.nodes.new("ShaderNodeTexImage"); r.image = maps["R"]
    n = nt.nodes.new("ShaderNodeTexImage"); n.image = maps["N"]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(d.outputs[0], b.inputs["Base Color"])
    nt.links.new(r.outputs[0], b.inputs["Roughness"])
    nt.links.new(n.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return {k: os.path.basename(v.filepath_raw) for k, v in maps.items()}


report = {"groups": {}, "flat_materials": {}}
names = lambda prefix: [o.name for o in bpy.data.objects if o.name.startswith(prefix)]  # noqa: E731
GROUPS = {
    "Hull": ["Hull", "Keel"] + names("Reg_") + names("Sticker_"),
    "DeckMould": ["Deck", "Cockpit", "Cabin"],
    "Rudder": ["Rudder"],
    "Teak": names("ToeRail_") + names("CoamingCap_") + names("Handrail_") + ["DropBoard"],
}
for g, members in GROUPS.items():
    ob = join(f"SM_J22H_{g}", members)
    res = RES if g in ("Hull", "DeckMould") else RES // 2
    report["groups"][g] = bake_group(g, ob, res)
    print("baked", g, res)

# flat materials: procedural hardware, rope and spar materials fall back to their viewport colour, which
# j22_materials.build_all sets from the style; sails keep their image textures
for m in bpy.data.materials:
    if m.name.startswith("J22H_") or not m.use_nodes:
        continue
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not b or any(n.type == "TEX_IMAGE" for n in nt.nodes):
        continue
    for inp in ("Base Color", "Roughness", "Normal"):
        for ln in list(b.inputs[inp].links):
            nt.links.remove(ln)
    if tuple(m.diffuse_color[:3]) != (0.8, 0.8, 0.8):
        b.inputs["Base Color"].default_value = m.diffuse_color
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out and out.inputs["Surface"].links and out.inputs["Surface"].links[0].from_node != b:
        nt.links.new(b.outputs[0], out.inputs["Surface"])
for m in bpy.data.materials:
    if m.name.startswith("J22H_") or not m.use_nodes:
        continue
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b and not b.inputs["Base Color"].is_linked:
        report["flat_materials"][m.name] = {"base_color_linear": [round(c, 4) for c in b.inputs["Base Color"].default_value[:3]],
                                            "roughness": round(b.inputs["Roughness"].default_value, 3),
                                            "metallic": round(b.inputs["Metallic"].default_value, 3)}

# export for the game: SM_J22H_Hull/Mast/Boom/Rudder about their pivots plus J22H_sockets.json, the same layout as
# Tools/blender/build_j22.py, so scripts/import_boats.py imports them as tag "J22H". Ropes, wires, sails and the vang
# stay out: the game draws them live. SM_J22H_RiggingStill holds them as built, for cinematics and stills only.
GROUP_OWNER = {"SM_J22H_Hull": "SM_J22H_Hull", "SM_J22H_DeckMould": "SM_J22H_Hull", "SM_J22H_Teak": "SM_J22H_Hull",
               "SM_J22H_Rudder": "SM_J22H_Rudder"}
members = {k: [] for k in PIVOTS}
still, sails = [], []
for o in list(bpy.data.objects):
    if o.type not in ("MESH", "CURVE", "FONT") or o.name == "Water":
        continue
    part = GROUP_OWNER.get(o.name, GAME.get(o.name, "SM_J22H_Hull"))
    if part:
        members[part].append(o.name)
    else:
        (sails if "Sails" in {c.name for c in o.users_collection} else still).append(o.name)
glb_keep = set()
for part, names_ in list(members.items()) + [("SM_J22H_RiggingStill", still), ("SM_J22H_SailsStill", sails)]:
    names_ = [n for n in names_ if n in bpy.data.objects]
    if not names_:
        continue
    ob = join(part + "_tmp", names_) if len(names_) > 1 else make_mesh(bpy.data.objects[names_[0]])
    ob.name = ob.data.name = part
    pv = PIVOTS.get(part, Vector((0, 0, 0)))
    select([ob])
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    ob.data.transform(Matrix.Translation(-pv))
    bpy.ops.export_scene.fbx(filepath=os.path.join(FBX, f"{part}.fbx"), use_selection=True, axis_forward="X",
                             axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False, bake_space_transform=True,
                             path_mode="STRIP")
    ob.location = pv
    glb_keep.add(part)
    print("exported", part, len(names_), "objects,", len(ob.data.polygons), "faces")
meta = {"sockets": SOCKETS, "owner": {n: owner(n) for n in SOCKETS},
        "origins": {k: [round(v.x * 100, 2), round(-v.y * 100, 2), round(v.z * 100, 2)] for k, v in PIVOTS.items()},
        "live": {"ropes": "FRigLine (BoatModelVisuals.cpp) from these sockets", "sails": "FSailCloth; hero sail maps on UV1"}}
json.dump(meta, open(os.path.join(OUT, "J22H_sockets.json"), "w"), indent=1)

# web copy: 2K JPEG textures in one GLB
for img in bpy.data.images:
    if img.name.startswith("T_J22H_") and img.size[0] > 2048:
        img.scale(2048, 2048)
for o in list(bpy.data.objects):
    if o.type in ("CURVE", "FONT"):
        make_mesh(o)
select([o for o in bpy.data.objects if o.type == "MESH" and o.name != "Water"])
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "j22_hero.glb"), use_selection=True, export_format="GLB",
                          export_image_format="JPEG", export_jpeg_quality=85, export_apply=True, export_yup=True)
report["glb_bytes"] = os.path.getsize(os.path.join(OUT, "j22_hero.glb"))
json.dump(report, open(os.path.join(OUT, "materials.json"), "w"), indent=1)
print("J22H bake:", json.dumps({k: v for k, v in report.items() if k != "flat_materials"}))
