"""Bluebonnet's game parts (J-Class 14, step 2): her shipkit build cut into the parts the game hangs a boat on (the four
every boat has, and her wheel, which turns with the rudder).

    blender -b --factory-startup -noaudio -P Tools/shipkit/jclass/export_game.py -- <build dir> <out dir>
    python Tools/shipkit/jclass/export_game.py <build dir> <out dir>          (the bpy module)

Reads <build dir>/jclass.blend (build_jclass.py) and writes <out>/SM_Bluebonnet_{Hull,Mast,Boom,Rudder,Wheel}.fbx and
<out>/Bluebonnet_sockets.json in scripts/import_boats.py's form (sockets in cm in the body frame, each one's part, the
parts' origins), as game_bluebonnet.json says: which of the build's objects go in each part, how the moving ones are posed,
the game slot of each material, what stays out and why, and the sockets. Each part is joined, moved to its pivot, given
box-projected UVs (the boat library's tangent frame) and its slots folded into the packs (Tools/blender/boat_packs.py).

Checks, each stopping the export: every material has a game slot; every socket lies within its 'within' of its 'near'
object; the canoe as exported (the shell's paint, keel included, and the rudder below the load waterline) holds her
physics' displacement within 2% (the sections' canoe and the keel's and rudder's appendage volume,
Source/SailingPhysics/Private/BluebonnetHullData.inl), its centre within 5 cm, and her length, beam and draft are the
config's (BluebonnetConfig.inl) within 2 cm. Prints one line starting "Bluebonnet:" for the scripts' logs.
Frames: the body frame (X forward, Y starboard, Z up, metres, origin on the load waterline at the middle of the
waterline) is the build's and the physics'; Blender's has Y to port.
"""
import json
import math
import os
import re
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "blender"))
from boat_packs import pack_slots  # noqa: E402 (pc/boat-slots)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
if len(ARGS) < 2:
    raise SystemExit(__doc__)
BUILD, OUT = ARGS[0], ARGS[1]
os.makedirs(OUT, exist_ok=True)
G = json.load(open(os.path.join(HERE, "game_bluebonnet.json")))
PHYS = os.path.join(REPO, "Source", "SailingPhysics", "Private")


def B(p):
    """Body frame to Blender (and back: the same flip)."""
    return Vector((p[0], -p[1], p[2]))


# ---------------------------------------------------------------------------------------------------------- the physics

def physics():
    """Her physics' numbers the export is held to, read from the generated .inl files (slice 13)."""
    hull = open(os.path.join(PHYS, "BluebonnetHullData.inl")).read()
    cfg = open(os.path.join(PHYS, "BluebonnetConfig.inl")).read()

    def num(text, name):
        m = re.search(r"\b" + re.escape(name) + r"\s*=\s*(-?[\d.]+)", text)
        if not m:
            raise SystemExit(f"{name} not found in the physics' .inl")
        return float(m.group(1))
    main = [float(a) for a in re.search(r"SetMain\(C,([^)]*)\)", cfg).group(1).split(",")]
    canoe, keel = num(hull, "kBluebonnetCanoeVolume"), num(hull, "kBluebonnetKeelVolume")
    cb = Vector((num(hull, "kBluebonnetBuoyancyX"), 0.0, num(hull, "kBluebonnetBuoyancyZ")))
    kc = Vector((num(hull, "kBluebonnetKeelX"), 0.0, num(hull, "kBluebonnetKeelZ")))
    return {"volume": canoe + keel, "cb": (cb * canoe + kc * keel) / (canoe + keel),
            "loa": num(cfg, "C.LengthOverall"), "beam": num(cfg, "C.Beam"), "draft": num(cfg, "C.Draft"),
            "mast_x": num(cfg, "C.MastX"), "boom_z": num(cfg, "C.BoomZ"), "main_luff_x": main[5],
            "jib_head_z": num(cfg, "C.JibHeadZ")}


# ------------------------------------------------------------------------------------------------------------- geometry

def body_verts(ob):
    """An object's vertices in the body frame (world matrix applied, Y turned to starboard)."""
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    p = co @ M[:3, :3].T + M[:3, 3]
    p[:, 1] *= -1.0
    return p


def body_tris(ob):
    """An object's triangles in the body frame (n x 3 x 3) and each one's slot name."""
    me = ob.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    idx = np.empty(n * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", idx)
    mat = np.empty(n, dtype=np.int64)
    me.loop_triangles.foreach_get("material_index", mat)
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    return body_verts(ob)[idx.reshape(-1, 3)], [names[k] for k in mat]


def volume_below(tris):
    """The volume a closed-below-the-waterline surface holds under z = 0, and its centre (the triangles clipped at the
    waterplane; the waterplane's own cap adds nothing to either sum, its points having z = 0)."""
    vol, mom = 0.0, np.zeros(3)
    z = tris[:, :, 2]
    under = (z <= 0.0).all(axis=1)
    a, b, c = tris[under, 0], tris[under, 1], tris[under, 2]
    v = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    vol += v.sum()
    mom += (v[:, None] * (a + b + c) / 4.0).sum(axis=0)
    for t in tris[~under & (z <= 0.0).any(axis=1)]:
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


def rudder_axis():
    """The rudder stock's axis in the body frame: a point on it and its unit direction, pointing up (the build turns the
    rudder about its 'frame''s Z: build_jclass.py, shell.rudder_frame)."""
    M = bpy.data.objects["Rudder"].matrix_world
    o = B(M.translation)
    d = B(Vector((M[0][2], M[1][2], M[2][2]))).normalized()
    return o, (d if d.z > 0 else -d)


def on_axis(z):
    o, d = rudder_axis()
    return o + d * ((z - o.z) / d.z)


def wheel_frame():
    """The wheel's hub and axes in the body frame: X forward along its shaft, Z up its king spoke (deck.py steering():
    the 'Wheel' object's own frame, read before it is joined into its part)."""
    M = bpy.data.objects["Wheel"].matrix_world
    o = B(M.translation)
    x = B(Vector((M[0][0], M[1][0], M[2][0]))).normalized()
    z = B(Vector((M[0][2], M[1][2], M[2][2]))).normalized()
    if abs(x.x) < 0.99 or z.z < 0.99:
        raise SystemExit(f"the wheel's frame is not along the shaft and upright: X {tuple(x)}, Z {tuple(z)}")
    return o, x, z


# ---------------------------------------------------------------------------------------------------------------- sockets

def top_or_bottom(names, x, y, r, top):
    """The highest (or lowest) vertex of the named objects within r of (x, y) in plan."""
    zs = []
    for n in names:
        p = body_verts(bpy.data.objects[n])
        near = p[np.hypot(p[:, 0] - x, p[:, 1] - y) <= r]
        if len(near):
            zs.append(near[:, 2].max() if top else near[:, 2].min())
    if not zs:
        raise SystemExit(f"nothing of {names} within {r} m of ({x}, {y})")
    return max(zs) if top else min(zs)


def socket_point(name, s):
    if "wheel_at" in s:
        o, x, z = wheel_frame()
        along, up = s["wheel_at"]
        return o + x * along + z * up
    if "rudder_axis_z" in s:
        z = s["rudder_axis_z"]
        if isinstance(z, str):
            z = float(body_verts(bpy.data.objects[z])[:, 2].max())
        return on_axis(z + s.get("dz", 0.0))
    at = s["at"]
    if "z_top" in s:
        return Vector((at[0], at[1], top_or_bottom(s["z_top"], at[0], at[1], s.get("r", 0.15), True) + s.get("dz", 0.0)))
    if "z_bottom" in s:
        return Vector((at[0], at[1], top_or_bottom(s["z_bottom"], at[0], at[1], s.get("r", 0.15), False) + s.get("dz", 0.0)))
    return Vector(at)


def nearest(name, p):
    """The distance from p to the named object's surface (body frame)."""
    ob = bpy.data.objects[name]
    pts = [Vector(q) for q in body_verts(ob)]
    tree = BVHTree.FromPolygons(pts, [tuple(f.vertices) for f in ob.data.polygons])
    return tree.find_nearest(p)[3]


def sockets():
    S, bad = {}, []
    for name, s in G["sockets"].items():
        if name == "note":
            continue
        p = socket_point(name, s)
        if "near" in s:
            d = nearest(s["near"], p)
            if d > s["within"]:
                bad.append(f"{name} at ({p.x:.3f}, {p.y:.3f}, {p.z:.3f}) is {d:.3f} m from {s['near']} (within {s['within']})")
        S[name] = (s["part"], p)
    if bad:
        raise SystemExit("sockets off their fittings:\n  " + "\n  ".join(bad))
    return S


# ---------------------------------------------------------------------------------------------------------------- parts

def show(ob):
    if ob.name not in bpy.context.view_layer.objects:
        bpy.context.scene.collection.objects.link(ob)
    ob.hide_set(False)
    ob.hide_viewport = False
    ob.hide_select = False
    ob.hide_render = False


def pose():
    """The moving pieces at rest: the boom on the centreline (its 'frame'), the spinnaker pole stowed."""
    for part in G["parts"].values():
        for n, what in part.get("pose", {}).items():
            G["poses"][n] = what
    for n, what in G["poses"].items():
        ob = bpy.data.objects[n]
        ob.matrix_world = Matrix([ob[what][k:k + 4] for k in range(0, 16, 4)])
    bpy.context.view_layer.update()


def slot_material(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def game_slots(ob):
    """Each of the object's slots to its game slot (game_bluebonnet.json "materials"); stops on one without."""
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
        raise SystemExit(f"{ob.name}: no game slot for {sorted(set(missing))} (game_bluebonnet.json materials)")


def box_uvs(me):
    """UV0 projected on the axis nearest each face's normal, in metres (build_fleet.py's: the boat library's tangent
    frame); the build's own UV sets (plating, planking, spar grain) go."""
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
    # (a flat plate like the transom is one n-gon: triangulated here, not by the importer's guess)
    tri = ob.modifiers.new("Triangulate", "TRIANGULATE")
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


# ----------------------------------------------------------------------------------------------------------------- main

def main():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BUILD, "jclass.blend"))
    if not hasattr(bpy.ops.export_scene, "fbx"):
        bpy.ops.preferences.addon_enable(module="io_scene_fbx")
    P = physics()
    pose()
    O = bpy.data.objects
    # The canoe as exported: the shell's paint (the lead keel painted with the bottom) and the rudder, below the waterline.
    canoe = [s for s, t in G["materials"].items() if t in ("Topsides", "Bootstripe", "CoveStripe", "Antifouling")]
    vol, mom = 0.0, np.zeros(3)
    ext = []
    for n in ("Shell", "Rudder"):
        t, slots = body_tris(O[n])
        keep = np.array([s in canoe for s in slots])
        v, m = volume_below(t[keep])
        vol, mom = vol + abs(v), mom + (m if v > 0 else -m)
        ext.append(t[keep].reshape(-1, 3))
    shell = ext[0]
    cb = Vector(mom / vol)
    size = shell.max(axis=0) - shell.min(axis=0)
    draft = -min(e[:, 2].min() for e in ext)
    meas = {"loa": float(size[0]), "beam": float(size[1]), "draft": float(draft), "volume": vol, "cb": list(cb)}
    bad = []
    if abs(vol - P["volume"]) > 0.02 * P["volume"]:
        bad.append(f"canoe volume {vol:.3f} m^3, physics {P['volume']:.3f}")
    if (cb - P["cb"]).length > 0.05:
        bad.append(f"centre of buoyancy ({cb.x:.3f}, {cb.y:.3f}, {cb.z:.3f}), physics ({P['cb'].x:.3f}, 0, {P['cb'].z:.3f})")
    for k in ("loa", "beam", "draft"):
        if abs(meas[k] - P[k]) > 0.02:
            bad.append(f"{k} {meas[k]:.3f} m, physics {P[k]:.3f}")
    socks = sockets()
    axis = rudder_axis()[1]   # (before the rudder is joined into its part)
    hounds = socks["Hounds"][1]
    if hounds.z - 0.05 < P["jib_head_z"]:
        bad.append(f"the hounds ({hounds.z:.3f}) under the genoa's head ({P['jib_head_z']:.3f}): the game would lower it")
    if bad:
        raise SystemExit("Bluebonnet's export does not match her physics:\n  " + "\n  ".join(bad))
    # The gooseneck: the boom's own pin, its rest frame's origin (the physics' MainLuffX, 2.3508 since J-Class upwind,
    # Fleet.cpp Bluebonnet(); the .inl's SetMain luff, 2.578, is the sail plan's, not the pin). Its height is held to BoomZ.
    goose = B(bpy.data.objects["Boom"].matrix_world.translation)
    if abs(goose.y) > 0.01 or abs(goose.z - P["boom_z"]) > 0.02:
        raise SystemExit(f"the boom's pin ({goose.x:.4f}, {goose.y:.4f}, {goose.z:.4f}) is off the centreline or BoomZ {P['boom_z']}")
    pivots = {"mast_step": socks["MastStep"][1], "gooseneck": goose,
              "rudder_pivot": socks["RudderPivot"][1], "wheel_hub": socks["WheelHub"][1]}
    if abs(pivots["mast_step"].x - P["mast_x"]) > 0.01:
        raise SystemExit(f"MastStep x {pivots['mast_step'].x} is not the physics' MastX {P['mast_x']}")
    origins, tris, slots = {}, {}, {}
    for name, part in G["parts"].items():
        pv = part["pivot"]
        pv = Vector(pv) if isinstance(pv, list) else pivots[pv]
        for o in part["objects"]:
            game_slots(O[o])
        ob = join_part(name, [O[o] for o in part["objects"]], pv)
        origins[name] = pv
        tris[name] = tri_count(ob)
        slots[name] = export_part(ob, part.get("keep", ()))
    cm = lambda p: [round(v * 100.0, 2) for v in p]   # noqa: E731
    meta = {"sockets": {n: cm(p) for n, (o, p) in socks.items()},
            "owner": {n: o for n, (o, p) in socks.items()},
            "origins": {n: cm(p) for n, p in origins.items()},
            "measures": dict(meas, tris=tris, slots=slots, physics={k: (list(v) if isinstance(v, Vector) else v) for k, v in P.items()},
                             rudder_axis=list(axis)),
            "live": {"ropes": "FRigLine (BoatModelVisuals.cpp) from these sockets: her genoa sheets and mainsheet",
                     "sails": "FSailCloth from the physics strips", "standing rigging": "in SM_Bluebonnet_Mast as built"},
            "left_out": G["left_out"]}
    with open(os.path.join(OUT, "Bluebonnet_sockets.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"Bluebonnet: LOA {meas['loa']:.3f} beam {meas['beam']:.3f} draft {meas['draft']:.3f} (physics {P['loa']:.3f}, "
          f"{P['beam']:.3f}, {P['draft']:.3f}); canoe {vol:.3f} m^3 at ({cb.x:.3f}, {cb.z:.3f}) (physics {P['volume']:.3f} "
          f"at ({P['cb'].x:.3f}, {P['cb'].z:.3f})); tris {tris}; {len(socks)} sockets")


main()
