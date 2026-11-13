"""Builds the frigate Commonwealth in Blender (docs/shipkit-1, docs/shipkit-2, docs/shipkit-3).

Slice 1 lofted the moulded hull (the frames' outside, as the 1927 lines give it). Slice 2 planks it (skin.py): copper
to the main wale, the wales, black strakes, the ochre port band, the bulwarks to the rail, the gun deck and spar deck
ports with their linings and lids, the rail cap, the plankshear moulding, the channels, the entry steps, the rudder
and its irons, and placeholder decks and bulkheads for the later slices. Slice 3 (spars.py, spars_1795.json) masts
her: lower masts, tops, caps, topmasts, topgallant masts, every yard, the spanker boom and gaff, the bowsprit and
jibbooms. Each yard, the boom, the gaff and the spritsail yard is its own object with its origin on the axis it turns
about (local Z up that axis): <out>/rig.json lists how far each one braces and hoists.

    python build_frigate.py <out dir>        (Blender's Python: pip bpy, or blender -b -P build_frigate.py -- <out>)

Writes <out>/frigate.blend, <out>/frigate.obj (the moulded hull, transom and backbone, for lines_check.py),
<out>/build.json (triangles per object, main dimensions, displacement, the rig's heights) and <out>/rig.json. Units are metres in Unreal's body frame
(X forward, Y starboard, Z up), origin on the centreline at midships on the load waterline. The moulded hull stays in
the .blend as "Hull", hidden from renders: the shape tools measure it. Edit loft.py, skin.py, offsets.json and
specs_1795.json, spars.py and spars_1795.json, never the .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import skin  # noqa: E402
import spars  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.unit_settings.system = "METRIC"


def material(name, rgb, rough=0.6):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def make(name, V, F, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def weld(ob, dist=0.0005):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=dist)
    bm.to_mesh(ob.data)
    bm.free()


def smooth(ob, angle=30):
    me = ob.data
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(angle))


L = loft.Lines()
H = loft.Hull(L).build()
parts = loft.mesh(L, H)

# paint as built (1797): a black side with an ochre band along the gun ports and black lids (the chequer of the
# period), copper to the main wale, red inside the bulwarks and ports. Plain colours: textures are the texture loop's
PAINT = {
    "Copper": ((0.62, 0.36, 0.22), 0.35, 1.0),
    "HullBlack": ((0.03, 0.028, 0.026), 0.55, 0.0),
    "HullOchre": ((0.60, 0.44, 0.17), 0.6, 0.0),
    "HullRed": ((0.40, 0.07, 0.045), 0.6, 0.0),
    "Interior": ((0.66, 0.60, 0.50), 0.7, 0.0),
    "Deck": ((0.58, 0.52, 0.42), 0.75, 0.0),
    "Iron": ((0.05, 0.05, 0.05), 0.5, 0.6),
    "Bronze": ((0.55, 0.40, 0.22), 0.35, 1.0),
    "Spar": ((0.50, 0.36, 0.20), 0.5, 0.0),
}
MATS = {}
for name, (rgb, rough, metal) in PAINT.items():
    m = material(name, rgb, rough)
    m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = metal
    MATS[name] = m
CLAY = material("Clay_Hull", (0.55, 0.53, 0.5))


def make_painted(name, V, F, M):
    """One object, a material slot per paint used, each face on its paint's slot."""
    names = sorted(set(M))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    for n in names:
        me.materials.append(MATS[n])
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [idx[m] for m in M])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    return ob


def mirrored(V, F, M):
    """A starboard part and its port twin as one mesh (y flipped, faces turned so they still face out)."""
    V = np.asarray(V, float)
    Vp = V * np.array([1.0, -1.0, 1.0])
    n = len(V)
    return np.concatenate([V, Vp]), list(F) + [tuple(n + i for i in f[::-1]) for f in F], list(M) + list(M)


# the moulded hull: both sides and the wing transom's underside as one welded surface. It is the drawing's line and
# what lines_check and the shape tools measure; the planking covers it, so it is hidden from renders
objs = [make(n, *parts[n], CLAY) for n in ("Hull_Stbd", "Hull_Port")]
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
hull = bpy.context.view_layer.objects.active
hull.name = hull.data.name = "Hull"
weld(hull)
smooth(hull)
hull.hide_render = True
hull.hide_set(True)

# the transom (moulded, black; the stern windows and carvings go on it in slice 9)
transom = make("Transom", *parts["Transom"], MATS["HullBlack"])
weld(transom)
smooth(transom)

# the planked ship
# the rig first: the stem head is cut down to the bowsprit's bed
RIG = spars.Rig(L, json.load(open(os.path.join(HERE, "specs_1795.json")))).build()
SK = skin.Skin(L, stem_bed=RIG.stem_bed).build()
SKIN = SK.parts()
LIDS = []
for name, (V, F, M, side) in SKIN.items():
    if name.startswith("Lid_"):
        LIDS.append(name)
        continue
    if side == "stbd":
        V, F, M = mirrored(V, F, M)
    ob = make_painted(name, V, F, M)
    smooth(ob, 40 if name in ("Backbone", "Rudder") else 30)

# the gun port lids: an object each side, its origin on the hinge axis (through the knuckles) with X along it and Z out
# of the side, so on either side a positive turn about the lid's own X opens it outward. Port lids are the starboard
# ones mirrored; their X points aft so the frame stays right-handed and opens the same way (Y points down on both)
for name in LIDS:
    V, F, M, _ = SKIN[name]
    o, xa, za = SK.lid_frame(name)
    for suffix, sgn in (("S", 1.0), ("P", -1.0)):
        flip = np.array([1.0, sgn, 1.0])
        oo, xx, zz = o * flip, xa * flip * sgn, za * flip
        yy = np.cross(zz, xx)
        R = np.stack([xx, yy, zz], 1)                 # columns: the lid's axes in the ship
        Vw = np.asarray(V, float) * flip
        Vl = (Vw - oo) @ R
        Fs = list(F) if sgn > 0 else [f[::-1] for f in F]
        ob = make_painted(f"{name}_{suffix}", Vl, Fs, M)
        ob.matrix_world = Matrix(((*R[0], oo[0]), (*R[1], oo[1]), (*R[2], oo[2]), (0, 0, 0, 1)))
        smooth(ob, 30)

# the masts and yards (slice 3): masts, tops and the bowsprit where they stand; each yard, the spanker boom and gaff on
# its own frame, origin on the axis it turns about
for name, (V, F, M, frame) in RIG.parts().items():
    ob = make_painted(name, V, F, M)
    if frame is not None:
        o, R = frame
        ob.matrix_world = Matrix(((*R[0], o[0]), (*R[1], o[1]), (*R[2], o[2]), (0, 0, 0, 1)))
    smooth(ob, 35)

# a sun and sky so a quick look in Blender isn't black (render_set.py brings its own)
SC.world = bpy.data.worlds.new("World")
SC.world.color = (0.6, 0.65, 0.7)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "frigate.blend"))
# the lines check reads the moulded surfaces only: the drawing's lines are the frames' outside, not the planking
loft.write_obj(os.path.join(OUT, "frigate.obj"), {n: parts[n] for n in ("Hull_Stbd", "Hull_Port", "Transom", "Backbone")})


def tris(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def bounds(ob):
    P = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    return P.min(0).round(3).tolist(), P.max(0).round(3).tolist()


def displacement(L):
    """Moulded volume below the load waterline: each section's area (both sides, from the rabbet up to A) plus the
    keel and deadwood below the rabbet (the keel's siding), summed along x at 1 px."""
    k = L.k
    xa, xf = L.wl_ends["A"]
    vol_px = 0.0
    for x in np.arange(xa + 0.5, xf, 1.0):
        zb = L.rabbet_z(x)
        if zb >= 0:
            continue
        sec = L.section(x, "lower")
        zs = np.linspace(zb, 0, 200)
        vol_px += 2 * np.trapezoid(np.maximum(sec(zs), k), zs)
    keel = L.P["keel_bottom_z_px"]
    kx, kz = [p[0] for p in keel], [p[1] for p in keel]
    for x in np.arange(max(kx[0], xa), kx[-1], 1.0):
        zr = min(L.rabbet_z(x), 0.0)
        vol_px += 2 * k * max(0.0, zr - float(np.interp(x, kx, kz)))
    return vol_px / (L.ppf * L.ppf_y ** 2) * loft.FT ** 3     # x across the sheet, half-breadths and heights down it


REFERENCE = {"Hull"}           # measured, never drawn
stats = {"objects": {o.name: {"triangles": tris(o), "bounds_m": bounds(o)} for o in SC.objects if o.type == "MESH"}}
stats["triangles_model"] = sum(v["triangles"] for k, v in stats["objects"].items() if k not in REFERENCE)
stats["triangles_reference"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in REFERENCE)
stats["dimensions"] = loft.summary(L, H)
sk_ob = SC.objects["Skin"]
P = np.array([v.co for v in sk_ob.data.vertices])
stats["dimensions"]["extreme_breadth_planked_ft"] = round(float(2 * P[:, 1].max()) / loft.FT, 2)
stats["dimensions"]["extreme_breadth_note"] = "outside the main wales: the moulded 43 ft 5 in plus two 7 in wales (specs_1795.json)"
vol = displacement(L)
stats["displacement"] = {"moulded_volume_m3": round(vol, 1), "seawater_tonnes": round(vol * 1.025, 0),
                         "long_tons": round(vol * 1.025 / 1.016, 0),
                         "note": "moulded (inside the planking); the planking and copper add about 3-4%. Constitution: about 2,200 long tons at 21 ft (designed)"}
stats["rig"] = RIG.summary()
stats["triangles_rig"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in RIG.parts_)
json.dump(stats, open(os.path.join(OUT, "build.json"), "w"), indent=1)
json.dump({"note": "each moving spar (docs/shipkit-3): origin_m on the axis it turns about (metres, ship frame) and that "
                   "axis (the object's local +Z); parent, the object it rides on; hoist_m, its offset along the axis "
                   "[lowered, hoisted] (negative is down; the model hangs it hoisted); brace_deg, the limits of a turn "
                   "about local +Z (right-handed: positive swings a square yard's starboard arm aft and the spanker "
                   "boom and gaff to port); port_tack_sign, the sign of the turn that trims it for the wind on the "
                   "port side (each yard's lee arm aft, the boom and gaff to leeward)",
           "parts": RIG.meta}, open(os.path.join(OUT, "rig.json"), "w"), indent=1)
print(json.dumps(stats, indent=1))
