"""Builds the frigate Commonwealth in Blender (docs/shipkit-1). Slice 1: the moulded hull, the transom and the
backbone (keel, deadwood, sternpost, stem), plus a flat placeholder deck at the sheer so renders read as a ship.

    python build_frigate.py <out dir>        (Blender's Python: pip bpy, or blender -b -P build_frigate.py -- <out>)

Writes <out>/frigate.blend, <out>/frigate.obj (every object, for lines_check.py) and <out>/build.json (triangles per
object, main dimensions, displacement). Units are metres in Unreal's body frame (X forward, Y starboard, Z up), origin
on the centreline at midships on the load waterline. Edit loft.py and offsets.json, never the .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402

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
CLAY = material("Clay_Hull", (0.55, 0.53, 0.5))
WOOD = material("Clay_Backbone", (0.42, 0.36, 0.3))
DECK = material("Clay_DeckPlaceholder", (0.62, 0.6, 0.55))

# the hull: both sides and the wing transom's underside as one welded surface; the transom meets it at a hard corner
# and stays its own object (the stern windows and carvings go on it in slice 9)
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

transom = make("Transom", *parts["Transom"], CLAY)
weld(transom)
smooth(transom)

bb = make("Backbone", *parts["Backbone"], WOOD)
weld(bb)
smooth(bb, 40)

# placeholder deck: straight across between the two sheers (the decks are slice 7)
top = H.Up[:, -1]
x, y, z = L.to_m(top[:, 0], top[:, 1], top[:, 2])
n = 16
V, F = [], []
for i in range(len(x)):
    for j in range(n + 1):
        t = -1 + 2 * j / n
        V.append((x[i], y[i] * t, z[i] - 0.02))
for i in range(len(x) - 1):
    for j in range(n):
        a, b = i * (n + 1) + j, (i + 1) * (n + 1) + j
        F.append((a, b, b + 1, a + 1))          # normal up
deck = make("DeckPlaceholder", np.array(V), F, DECK)
weld(deck)

# a sun and sky so a quick look in Blender isn't black (render_set.py brings its own)
SC.world = bpy.data.worlds.new("World")
SC.world.color = (0.6, 0.65, 0.7)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "frigate.blend"))
bpy.ops.wm.obj_export(filepath=os.path.join(OUT, "frigate.obj"), export_selected_objects=False, forward_axis="NEGATIVE_Z",
                      up_axis="Y", apply_modifiers=True, export_materials=False, export_normals=False, export_uv=False)


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


stats = {"objects": {o.name: {"triangles": tris(o), "bounds_m": bounds(o)} for o in SC.objects if o.type == "MESH"}}
stats["triangles_total"] = sum(v["triangles"] for v in stats["objects"].values())
stats["dimensions"] = loft.summary(L, H)
vol = displacement(L)
stats["displacement"] = {"moulded_volume_m3": round(vol, 1), "seawater_tonnes": round(vol * 1.025, 0),
                         "long_tons": round(vol * 1.025 / 1.016, 0),
                         "note": "moulded (inside the planking); the planking and copper add about 3-4%. Constitution: about 2,200 long tons at 21 ft (designed)"}
json.dump(stats, open(os.path.join(OUT, "build.json"), "w"), indent=1)
print(json.dumps(stats, indent=1))
