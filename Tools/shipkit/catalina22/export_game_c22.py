"""The Catalina 22 rebuild's game parts (docs/c22-12): the build cut into the parts the game hangs a boat on.

    blender -b --factory-startup -noaudio -P Tools/shipkit/catalina22/export_game_c22.py -- <build dir> <out dir>
    python Tools/shipkit/catalina22/export_game_c22.py <build dir> <out dir>          (the bpy module)

Reads <build dir>/c22.blend and c22_sockets.json (build_c22.py) and writes <out>/SM_C22Hero_{Hull,Mast,Boom,Rudder}.fbx
(and SM_C22Hero_Interior.fbx once the build has slice 7's cabin) with <out>/C22Hero_sockets.json in
scripts/import_boats.py's form (sockets in cm in the body frame, each one's part, the parts' origins), as game_c22.json
says: which of the build's objects go in each part, the game slot of each material, what stays out and why, and the
sockets the game reads beyond the build's own. Each part is joined, moved to its pivot, given box-projected UVs (the boat
library's tangent frame) and its slots folded into the packs (Tools/blender/boat_packs.py). <out> is normally
Artifacts/models; `import_boats.py c22hero` imports it to /Game/Boats/C22Hero.

Checks, each stopping the export: every material has a game slot; every socket the game reads is there; the mast's part
(not Nanite, bent by M_BoatMast) is under its triangle cap. The canoe as exported (the hull part's paint slots, cut at the
design waterline) and her length, beam and draft are printed beside the build's report: SailingSim.Visual.C22HeroMesh holds
them to the physics once imported. Prints one line starting "C22Hero:" for the scripts' logs.
Frames: the body frame (X forward, Y starboard, Z up, metres, origin on the design waterline) is the physics'; Blender's has
Y to port (build_c22.py's frame).
"""
import json
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "blender"))
from boat_packs import pack_slots  # noqa: E402 (pc/boat-slots)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
if len(ARGS) < 2:
    raise SystemExit(__doc__)
BUILD, OUT = ARGS[0], ARGS[1]
os.makedirs(OUT, exist_ok=True)
G = json.load(open(os.path.join(HERE, "game_c22.json")))
KC = json.load(open(os.path.join(HERE, "keel_c22.json")))
RUDDER, KEEL = KC["rudder"], KC["keel"]
TAG = "C22Hero"


def B(p):
    """Body frame to Blender (and back: the same flip)."""
    return Vector((p[0], -p[1], p[2]))


def cm(p):
    return [round(float(v) * 100.0, 2) for v in p]


# ------------------------------------------------------------------------------------------------------------- geometry

def body_tris(ob):
    """An object's triangles in the body frame (n x 3 x 3) and each one's slot name."""
    me = ob.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    idx = np.empty(n * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", idx)
    mat = np.empty(n, dtype=np.int64)
    me.loop_triangles.foreach_get("material_index", mat)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    M = np.array(ob.matrix_world)
    p = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    p[:, 1] *= -1.0
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    return p[idx.reshape(-1, 3)], [names[k] for k in mat]


def volume_below(tris):
    """The volume a closed-below-the-waterline surface holds under z = 0, and its centre (triangles clipped at the plane)."""
    vol, mom = 0.0, np.zeros(3)
    for t in tris[(tris[:, :, 2] <= 0.0).any(axis=1)]:
        poly = []
        for k in range(3):
            p, q = t[k], t[(k + 1) % 3]
            if p[2] <= 0.0:
                poly.append(p)
            if (p[2] <= 0.0) != (q[2] <= 0.0):
                poly.append(p + (q - p) * (-p[2] / (q[2] - p[2])))
        for k in range(1, len(poly) - 1):
            vv = float(np.dot(poly[0], np.cross(poly[k], poly[k + 1]))) / 6.0
            vol += vv
            mom += vv * (poly[0] + poly[k] + poly[k + 1]) / 4.0
    return vol, mom


# ---------------------------------------------------------------------------------------------------------------- parts

def show(ob):
    if ob.name not in bpy.context.view_layer.objects:
        bpy.context.scene.collection.objects.link(ob)
    ob.hide_set(False)
    ob.hide_viewport = False
    ob.hide_select = False
    ob.hide_render = False


def slot_material(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def game_slots(ob):
    """Each of the object's slots to its game slot (game_c22.json "materials"); stops on one without."""
    me = ob.data
    missing = []
    for i, m in enumerate(me.materials):
        src = m.name.split(".")[0] if m else ""
        tgt = G["materials"].get(src)
        if tgt is None:
            missing.append(src)
            continue
        me.materials[i] = slot_material(tgt)
    if missing:
        raise SystemExit(f"{ob.name}: no game slot for {sorted(set(missing))} (game_c22.json materials)")


def paint_lines():
    """The hull's one gelcoat cut at the paint lines: bottom, boot stripe, topsides (game_c22.json paint_lines)."""
    P = G["paint_lines"]
    ob = bpy.data.objects[P["object"]]
    me = ob.data
    af, bt = P["antifouling_top"], P["bootstripe_top"]
    Mi = ob.matrix_world.inverted()
    bm = bmesh.new()
    bm.from_mesh(me)
    for z in (af, bt):
        co = Mi @ Vector((0.0, 0.0, z))
        no = (Mi.to_3x3().transposed() @ Vector((0.0, 0.0, 1.0))).normalized()   # (the plane's normal into the local frame)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    slots = {}
    for s in ("Antifouling", "Bootstripe", "Topsides"):
        if s not in names:
            me.materials.append(slot_material(s))
            names.append(s)
        slots[s] = names.index(s)
    W = ob.matrix_world
    for f in bm.faces:
        z = (W @ f.calc_center_median()).z
        f.material_index = slots["Antifouling" if z < af else "Bootstripe" if z < bt else "Topsides"]
    bm.to_mesh(me)
    bm.free()


def loose_parts(ob):
    """The object's loose parts as lists of vertex indices."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    seen, parts = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            a = stack.pop()
            comp.append(a.index)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        parts.append(comp)
    bm.free()
    return parts


def split_object(name, rule, mast_x):
    """Splits `name` into <name>:mast (its loose parts on the mast, by `rule`) and <name>:hull (the rest)."""
    ob = bpy.data.objects[name]
    show(ob)
    W = np.array(ob.matrix_world)
    co = np.array([v.co for v in ob.data.vertices])
    co = co @ W[:3, :3].T + W[:3, 3]
    on_mast = np.zeros(len(co), dtype=bool)
    for comp in loose_parts(ob):
        c = co[comp].mean(axis=0)
        if c[2] > rule["above_z"] and np.hypot(c[0] - mast_x, c[1]) < rule["within_m_of_mast"]:
            on_mast[comp] = True
    out = {}
    for side, keep in (("mast", on_mast), ("hull", ~on_mast)):
        cp = ob.copy()
        cp.data = ob.data.copy()
        cp.name = f"{name}:{side}"
        bpy.context.scene.collection.objects.link(cp)
        bm = bmesh.new()
        bm.from_mesh(cp.data)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(~keep)[0]], context="VERTS")
        bm.to_mesh(cp.data)
        bm.free()
        out[side] = cp
    bpy.data.objects.remove(ob, do_unlink=True)
    return out


def split_by_material(name, rule):
    """Splits `name` into <name>:<piece> (the faces of each piece's materials, game_c22.json split_material) and
    <name>:head (the rest)."""
    ob = bpy.data.objects[name]
    show(ob)
    names = [m.name.split(".")[0] if m else "" for m in ob.data.materials]
    pieces = {k: v for k, v in rule.items() if k != "note"}
    out = {}
    for piece in list(pieces) + ["head"]:
        mats = pieces.get(piece)
        cp = ob.copy()
        cp.data = ob.data.copy()
        cp.name = f"{name}:{piece}"
        bpy.context.scene.collection.objects.link(cp)
        bm = bmesh.new()
        bm.from_mesh(cp.data)
        if mats is None:
            drop = [f for f in bm.faces if names[f.material_index] in sum(pieces.values(), [])]
        else:
            drop = [f for f in bm.faces if names[f.material_index] not in mats]
        bmesh.ops.delete(bm, geom=drop, context="FACES")
        bm.to_mesh(cp.data)
        bm.free()
        if not cp.data.polygons:
            raise SystemExit(f"{cp.name}: no faces (split_material {mats})")
        out[piece] = cp
    bpy.data.objects.remove(ob, do_unlink=True)
    return out


def box_uvs(me):
    """UV0 projected on the axis nearest each face's normal, in metres (build_fleet.py's: the boat library's tangent
    frame); the build's own UV sets go."""
    for name in [u.name for u in me.uv_layers]:
        me.uv_layers.remove(me.uv_layers[name])
    uv = me.uv_layers.new(name="UVMap")
    n = len(me.polygons)
    nrm = np.empty(n * 3)
    me.polygons.foreach_get("normal", nrm)
    ax = np.abs(nrm.reshape(-1, 3)).argmax(axis=1)
    total = np.empty(n, dtype=np.int64)
    me.polygons.foreach_get("loop_total", total)
    lax = np.repeat(ax, total)
    vi = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", vi)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    lc = co.reshape(-1, 3)[vi]
    u = np.where(lax == 0, lc[:, 1], lc[:, 0])
    v = np.where(lax == 2, lc[:, 1], lc[:, 2])
    uv.data.foreach_set("uv", np.c_[u, v].ravel())


def join_part(name, obs, pivot):
    """One game part: the objects joined, the transforms applied, the origin moved to the pivot (body frame)."""
    for ob in obs:
        show(ob)
        ob.parent = None
    bpy.ops.object.select_all(action="DESELECT")
    for ob in obs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pv = B(pivot)
    ob.data.transform(Matrix.Translation(-pv))
    ob.location = pv
    return ob


def export_part(ob, keep):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    box_uvs(ob.data)
    slots = pack_slots(ob.data, keep=tuple(keep))
    tri = ob.modifiers.new("Triangulate", "TRIANGULATE")   # (n-gons triangulated here, not by the importer's guess)
    tri.min_vertices = 5
    loc = ob.location.copy()
    ob.location = (0, 0, 0)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, ob.name + ".fbx"), use_selection=True, axis_forward="X",
                             axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False, bake_space_transform=True)
    ob.location = loc
    return slots


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ---------------------------------------------------------------------------------------------------------------- sockets

def sockets(build):
    """The build's sockets (c22_sockets.json, cm, body frame) with their parts renamed, plus game_c22.json's. Body metres."""
    S = {n: (build["owner"][n].replace("SM_Catalina22_", f"SM_{TAG}_"), Vector(p) / 100.0) for n, p in build["sockets"].items()}
    px = RUDDER["pivot_x"]
    end = RUDDER["tiller"]["end"]
    S["RudderPivot"] = (f"SM_{TAG}_Hull", Vector((px, 0.0, 0.0)))
    S["RudderStock"] = (f"SM_{TAG}_Rudder", Vector((px, 0.0, RUDDER["head"]["z"][1])))
    S["TillerEnd"] = (f"SM_{TAG}_Rudder", Vector((end[0], 0.0, end[1])))
    S["Gooseneck"] = (f"SM_{TAG}_Hull", Vector(build["origins"]["SM_Catalina22_Boom"]) / 100.0)
    S["KeelPin"] = (f"SM_{TAG}_Hull", Vector((KEEL["pivot"][0], 0.0, KEEL["pivot"][1])))
    bolt = RUDDER["head"]["bolt"]
    S["RudderBolt"] = (f"SM_{TAG}_Rudder", Vector((px + bolt[0], 0.0, bolt[1])))
    missing = [f"{part}: {n}" for part, names in G["required_sockets"].items() if part != "note"
               for n in names if n not in S or S[n][0] != part]
    if missing:
        raise SystemExit("sockets the game reads are missing (or on another part):\n  " + "\n  ".join(missing))
    return S


# ----------------------------------------------------------------------------------------------------------------- main

def main():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BUILD, "c22.blend"))
    if not hasattr(bpy.ops.export_scene, "fbx"):
        bpy.ops.preferences.addon_enable(module="io_scene_fbx")
    build = json.load(open(os.path.join(BUILD, "c22_sockets.json")))
    report = json.load(open(os.path.join(BUILD, "c22_report.json")))
    S = sockets(build)
    O = bpy.data.objects
    pivots = {n: S[n][1] for n in ("MastStep", "Gooseneck", "RudderPivot", "KeelPin", "RudderBolt")}
    paint_lines()
    for name, rule in G["split"].items():
        split_object(name, rule["mast"], float(pivots["MastStep"].x))
    for name, rule in G.get("split_material", {}).items():
        if name != "note":
            split_by_material(name, rule)
    origins, tris, slots, done = {}, {}, {}, []
    lowest = 0.0
    for name, part in G["parts"].items():
        if "objects_prefix" in part:
            names = sorted(o.name for o in O if o.type == "MESH" and o.name.startswith(part["objects_prefix"])
                           and o.name not in part.get("objects_skip", []) and "light_of" not in o)   # (slice 9's light twins)
        else:
            names = [n for n in part["objects"] if n in O or not part.get("optional")]
        absent = [n for n in names if n not in O]
        if absent:
            # (an object a later slice adds, like C22_LidRails, is left out with a note, not a stop)
            print(f"C22Hero: {name}: not in this build: {absent}")
            names = [n for n in names if n in O]
        if not names:
            if part.get("optional"):
                print(f"C22Hero: {name}: none of its objects in this build (optional), skipped")
                continue
            raise SystemExit(f"{name}: none of its objects are in the build")
        for n in names:
            game_slots(O[n])
        pv = part["pivot"]
        pv = Vector(pv) if isinstance(pv, list) else pivots[pv]
        ob = join_part(name, [O[n] for n in names], pv)
        tris[name] = tri_count(ob)
        if "max_tris" in part and tris[name] > part["max_tris"]:
            raise SystemExit(f"{name}: {tris[name]} triangles, over its {part['max_tris']} (not Nanite)")
        if name in (f"SM_{TAG}_Hull", f"SM_{TAG}_Keel"):
            bpy.context.view_layer.update()      # (join_part moved its origin: the draft from the keel down in place)
            lowest = min(lowest, float(body_tris(ob)[0].reshape(-1, 3)[:, 2].min()))
        if name == f"SM_{TAG}_Hull":
            t, sl = body_tris(ob)
            canoe = t[np.array([s in ("Topsides", "Bootstripe", "CoveStripe", "Antifouling") for s in sl])]
            vol, mom = volume_below(canoe)
            cb = mom / vol          # (the body frame's Y flip turns the winding over: the sign goes with both sums)
            vol = abs(vol)
            meas = {"loa": float(np.ptp(canoe[:, :, 0])), "beam": float(np.ptp(canoe[:, :, 1])), "draft": 0.0,
                    "canoe_volume_m3": round(vol, 4), "cb": [round(float(v), 3) for v in cb]}
        origins[name] = pv
        slots[name] = export_part(ob, part.get("keep", ()))
        done.append(name)
    meas["draft"] = -lowest
    socks = {n: (o, p) for n, (o, p) in S.items() if o in done}
    meta = {"sockets": {n: cm(p) for n, (o, p) in socks.items()},
            "owner": {n: o for n, (o, p) in socks.items()},
            "origins": {n: cm(p) for n, p in origins.items()},
            "measures": dict(meas, tris=tris, slots=slots, build_report=report),
            "live": {"standing rigging": "FRigLine from the sockets (forestay, backstay, uppers, lowers)",
                     "ropes": "the jib sheets and mainsheet from the sockets", "sails": "FSailCloth from the physics strips"},
            "left_out": G["left_out"]}
    with open(os.path.join(OUT, f"{TAG}_sockets.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"C22Hero: LOA {meas['loa']:.3f} beam {meas['beam']:.3f} draft {meas['draft']:.3f}; canoe {meas['canoe_volume_m3']:.4f} m^3 "
          f"at ({meas['cb'][0]:.3f}, {meas['cb'][2]:.3f}) (build's hull {report.get('hull_volume_m3')} at ({report.get('cb_x')}, "
          f"{report.get('cb_z')})); tris {tris}; {len(socks)} sockets")


main()
