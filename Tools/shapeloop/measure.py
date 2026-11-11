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


def footwell(ob, x, dz=0.10):
    """The cockpit's footwell at station x: the gap between the seat fronts' inner faces dz over the sole's top (the
    sole's top is the cut's highest point within 10 cm of the centreline; the liner's underside lies 2 cm under it), and
    the sole top's height. With dz over the seats (0.35: seats 0.27 m over the sole on the hero), the gap between the
    cockpit's side walls."""
    bm = bmesh.new()
    bm.from_object(ob, DG)
    bm.transform(ob.matrix_world)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(x, 0, 0), plane_no=(1, 0, 0), clear_inner=False, clear_outer=False)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    mid = [v.co.z for e in cut for v in e.verts if abs(v.co.y) < 0.10]
    if not mid:
        bm.free()
        return None
    sole = max(mid)
    h = sole + dz
    ys = []
    for e in cut:
        a, b = e.verts[0].co, e.verts[1].co
        if (a.z - h) * (b.z - h) <= 0 and a.z != b.z:
            ys.append(a.y + (b.y - a.y) * (h - a.z) / (b.z - a.z))
    bm.free()
    port, stbd = [y for y in ys if y > 0], [-y for y in ys if y < 0]
    if not port or not stbd:
        return None
    return min(port) + min(stbd), sole


features = {}
ck = bpy.data.objects.get("Cockpit")
if ck is not None and ck.name in objects:
    c = objects[ck.name]
    xs = [c["min"][0] + (c["max"][0] - c["min"][0]) * f for f in (0.3, 0.5, 0.7)]
    cuts = [footwell(ck, x) for x in xs]
    if cuts[1]:                                       # the cockpit's middle
        features["footwell_width"] = r(cuts[1][0])
    walls = [footwell(ck, x, 0.35) for x in xs]
    for key, w in zip(("cockpit_width_aft", "cockpit_width", "cockpit_width_fwd"), walls):   # at 30, 50, 70%
        if w:
            features[key] = r(w[0])
    features["cockpit_walls"] = [{"x": r(x), "width": r(w[0])} for x, w in zip(xs, walls) if w]
    cuts = [(x, w) for x, w in zip(xs, cuts) if w]
    if cuts:
        features["footwell_cuts"] = [{"x": r(x), "width": r(w[0]), "sole_z": r(w[1])} for x, w in cuts]
    features["cockpit_aft"] = c["min"][0]
    if "x_stern" in hull:
        features["aft_deck"] = r(c["min"][0] - hull["x_stern"])

physics = {}
rep = os.path.join(os.path.dirname(os.path.abspath(SRC)), "j22_hero_report.json")
if os.path.exists(rep):
    physics = json.load(open(rep))

stats = {"source": os.path.basename(SRC), "objects": objects, "sections": per_section,
         "triangles": sum(s["tris"] for s in per_section.values()), "hull": hull, "features": features,
         "physics": physics}
json.dump(stats, open(os.path.join(OUT, "stats.json"), "w"), indent=1)
print(f"shapeloop measure: {len(objects)} objects, {stats['triangles']:,} tris;",
      {k: v["tris"] for k, v in sorted(per_section.items())}, "hull", {k: v for k, v in hull.items() if k != "stations"},
      "features", {k: v for k, v in features.items() if k != "footwell_cuts"})
