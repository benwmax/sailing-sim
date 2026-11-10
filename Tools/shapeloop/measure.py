"""Shape loop, step 5a: measure a built boat (docs/shape-loop).

    python measure.py <j22_hero.blend | fbx dir> <sections.json> <out dir>

Writes <out>/stats.json: every object's section, triangles, bounds and centre (the object centres stand in for the
sockets the bake derives from them: a centre that moves is a socket that may move); triangles per section; the hull's
principal dimensions and its sheer, half-beam and keel line at 21 stations (cut through the hull mesh); and, when the
build's j22_hero_report.json sits beside the .blend, the canoe body's volume and centre of buoyancy with the physics'.
Needs Blender's Python (pip bpy). Frame: Blender, X forward, Y to port, Z up, metres.
"""
import json
import os
import sys

import bpy  # noqa: F401  (pip bpy: bpy must load before bmesh)
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, SECTIONS, OUT = ARGS[0], ARGS[1], ARGS[2]
os.makedirs(OUT, exist_ok=True)
SC = C.load_scene(SRC)
SEC = C.load_sections(SECTIONS)
DG = bpy.context.evaluated_depsgraph_get()
HULL = SEC.get("hull_object", "Hull")


def r(v, n=4):
    return round(v, n)


objects, per_section = {}, {}
for o in C.mesh_objects(SC):
    verts, tris = C.evaluated_mesh(o, DG)
    if not verts:
        continue
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    sec = C.section_of(o.name, SEC)
    objects[o.name] = {"section": sec, "tris": len(tris), "min": [r(a) for a in lo], "max": [r(a) for a in hi],
                       "centre": [r(a) for a in o.matrix_world.translation] if o.type != "MESH" or len(verts) < 3 else
                       [r((a + b) / 2) for a, b in zip(lo, hi)]}
    s = per_section.setdefault(sec, {"tris": 0, "objects": 0})
    s["tris"] += len(tris)
    s["objects"] += 1


def hull_cut(ob, x):
    """Outer section of the hull at station x: (max half-breadth, sheer height, keel height) from a plane cut."""
    bm = bmesh.new()
    bm.from_object(ob, DG)
    bm.transform(ob.matrix_world)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(x, 0, 0), plane_no=(1, 0, 0), clear_inner=False, clear_outer=False)
    pts = [v.co.copy() for v in res["geom_cut"] if isinstance(v, bmesh.types.BMVert)]
    bm.free()
    if not pts:
        return None
    return max(abs(p.y) for p in pts), max(p.z for p in pts), min(p.z for p in pts)


hull = {}
ob = bpy.data.objects.get(HULL)
if ob is None:
    sys.exit(f"shapeloop measure: no object named {HULL!r}: the hull was renamed or the build failed")
h = objects[ob.name]
x0, x1 = h["min"][0], h["max"][0]
hull = {"loa": r(x1 - x0), "beam": r(h["max"][1] - h["min"][1]), "x_stern": x0, "x_bow": x1, "stations": []}
for i in range(21):
    x = x0 + (x1 - x0) * (0.005 + 0.99 * i / 20)
    c = hull_cut(ob, x)
    if c:
        hull["stations"].append({"x": r(x), "half_beam": r(c[0]), "sheer_z": r(c[1]), "keel_z": r(c[2])})
st = hull["stations"]
if st:
    hull["freeboard_bow"] = st[-2]["sheer_z"]
    hull["freeboard_stern"] = st[0]["sheer_z"]
    hull["transom_width"] = r(2 * st[0]["half_beam"])     # across the hull 0.5% of LOA (3.4 cm) forward of the transom

physics = {}
rep = os.path.join(os.path.dirname(os.path.abspath(SRC)), "j22_hero_report.json")
if os.path.exists(rep):
    physics = json.load(open(rep))

stats = {"source": os.path.basename(SRC), "objects": objects, "sections": per_section,
         "triangles": sum(s["tris"] for s in per_section.values()), "hull": hull, "physics": physics}
json.dump(stats, open(os.path.join(OUT, "stats.json"), "w"), indent=1)
print(f"shapeloop measure: {len(objects)} objects, {stats['triangles']:,} tris;",
      {k: v["tris"] for k, v in sorted(per_section.items())}, "hull", {k: v for k, v in hull.items() if k != "stations"})
