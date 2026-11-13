"""Shape loop wave 5: numbers from a measured reference model (never its geometry). Run in Blender:

    blender -b <model.blend> -P measure_reference.py -- <out.json> [--objects name1,name2] [--up z|y] [--bow +x|-x|+y|-y]

With no --objects it prints every mesh object's name, triangles and bounds and stops: pick the hull and deck ones.
Writes, in metres with x from the transom (0) to the bow (LOA), y to port, z up from the lowest hull point:
LOA, beam, 41 stations (half-breadth max and at the deck edge, sheer height, deck height on the centreline, bottom
height), deck crown sections at 9 stations (deck height at 0..100% of the half-breadth), the centreline profile
every 2 cm (top and bottom), and the plan's half-breadth every 2 cm. Numbers only: no image or mesh leaves the PC.
"""
import json
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

A = sys.argv[sys.argv.index("--") + 1:]
OUT = A[0]
opt = {A[i]: A[i + 1] for i in range(1, len(A) - 1, 2)}
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if "--objects" not in opt:
    for o in meshes:
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = [round(min(v[i] for v in bb), 3) for i in range(3)]
        hi = [round(max(v[i] for v in bb), 3) for i in range(3)]
        print("OBJ", o.name, len(o.data.polygons), lo, hi)
    sys.exit(0)
names = opt["--objects"].split(",")
up = opt.get("--up", "z")
bow = opt.get("--bow", "+x")
dg = bpy.context.evaluated_depsgraph_get()
bm = bmesh.new()
for n in names:
    o = bpy.data.objects[n]
    t = bmesh.new()
    t.from_object(o, dg)
    t.transform(o.matrix_world)
    me = bpy.data.meshes.new("tmp")
    t.to_mesh(me)
    bm.from_mesh(me)
    t.free()
# to the frame: x forward, z up
R = Matrix.Identity(3)
if up == "y":
    R = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0))) @ R
ax = {"+x": 0, "-x": 180, "+y": -90, "-y": 90}[bow]
import math  # noqa: E402
R = Matrix.Rotation(math.radians(ax), 3, "Z") @ R
for v in bm.verts:
    v.co = R @ v.co
xs = [v.co.x for v in bm.verts]
zs = [v.co.z for v in bm.verts]
x0, x1, z0 = min(xs), max(xs), min(zs)
yc = (min(v.co.y for v in bm.verts) + max(v.co.y for v in bm.verts)) / 2
for v in bm.verts:
    v.co = Vector((v.co.x - x0, v.co.y - yc, v.co.z - z0))
L = x1 - x0
bm.verts.ensure_lookup_table()


def cut(co, no):
    c = bm.copy()
    g = c.verts[:] + c.edges[:] + c.faces[:]
    r = bmesh.ops.bisect_plane(c, geom=g, plane_co=co, plane_no=no)
    pts = [tuple(v.co) for v in r["geom_cut"] if isinstance(v, bmesh.types.BMVert)]
    c.free()
    return pts


def r4(v):
    return round(v, 4)


st = []
crown = []
for k in range(41):
    x = L * (0.005 + 0.99 * k / 40)
    p = cut((x, 0, 0), (1, 0, 0))
    if not p:
        continue
    hb = max(abs(q[1]) for q in p)
    top = max(q[2] for q in p)
    bot = min(q[2] for q in p)
    edge = [q for q in p if abs(q[1]) > hb - 0.01]
    sheer = max(q[2] for q in edge)
    cl = [q[2] for q in p if abs(q[1]) < 0.02]
    st.append({"x": r4(x), "half_breadth": r4(hb), "sheer_z": r4(sheer), "deck_cl_z": r4(max(cl)) if cl else None,
               "top_z": r4(top), "bottom_z": r4(bot)})
    if k % 5 == 0:
        row = []
        for f in [i / 10 for i in range(11)]:
            band = [q[2] for q in p if abs(abs(q[1]) - f * hb) < max(0.01, 0.02 * hb)]
            row.append(r4(max(band)) if band else None)
        crown.append({"x": r4(x), "half_breadth": r4(hb), "deck_z_at_fraction": row})
prof = []
plan = []
n = int(L / 0.02)
for k in range(n + 1):
    x = min(max(k * 0.02, 0.002), L - 0.002)
    p = [q for q in cut((x, 0, 0), (1, 0, 0))]
    if not p:
        continue
    cl = [q[2] for q in p if abs(q[1]) < 0.015]
    prof.append([r4(x), r4(max(cl)) if cl else None, r4(min(cl)) if cl else None])
    plan.append([r4(x), r4(max(abs(q[1]) for q in p))])
json.dump({"objects": names, "up": up, "bow": bow, "loa": r4(L),
           "beam": r4(2 * max(abs(v.co.y) for v in bm.verts)), "height": r4(max(v.co.z for v in bm.verts)),
           "stations": st, "crown": crown, "centreline_profile_top_bottom": prof, "plan_half_breadth": plan},
          open(OUT, "w"), indent=1)
print("wrote", OUT, "LOA", round(L, 3))
