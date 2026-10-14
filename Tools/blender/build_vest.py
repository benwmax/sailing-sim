"""Graphics G6: the club's Type III life jacket tailored over a sailor's polo (Tools/blender/build_polo.py output), so it is
skinned like the polo and wraps the body however the sailor sits (the rigid SM_CrewPFD sat inside the polo on the bigger
sailors: round 7's crew close-ups, and Bean's lesson photos for the look).

From the polo's own shirt panels (already fitted to that body) it keeps the torso below the neck and inside the armholes,
splits it down the front where the two foam panels meet, and stands it 2.2 cm off the shirt (the foam). Then: three grey
webbing straps across the chest and a strap down each front panel (raised bands), black side-release buckles off-centre,
and lighter blue piping round every edge (the hem, neck, armholes and the front opening, turned back to the shirt).

Slots: PFD (royal blue nylon, recoloured per sailor), Straps, Buckle, Piping. A static mesh in the outfit's own space;
scripts/import_crew_clothes.py copies the T-shirt's skin weights onto it (SKM_<Role>_Vest).

    blender -b --factory-startup -P Tools/blender/build_vest.py -- <Role>_Polo.fbx <Role>_Vest.fbx
Prints "Vest: <tris> ...".
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector

SRC, OUT = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
obj = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
M = obj.matrix_world.copy()
PFD, STRAPS, BUCKLE, PIPING = 0, 1, 2, 3
FOAM = 0.022

bm = bmesh.new()
bm.from_mesh(obj.data)
bm.transform(M)
polo = [i for i, m in enumerate(obj.data.materials) if m and m.name.split(".")[0] == "Polo"]
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in polo], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0002)
bm.normal_update()

zs = [v.co.z for v in bm.verts]
zmin, zmax = min(zs), max(zs)
ys = [v.co.y for v in bm.verts]
mid = [v.co for v in bm.verts if abs(v.co.x) < 0.04 and zmin + 0.25 < v.co.z < zmin + 0.45]
FRONT = -1.0 if sum(c.y for c in mid) / len(mid) < sum(ys) / len(ys) else 1.0
# The torso's half width at the belly (below the armpits): the armholes are a little outside it.
belly = sorted(abs(v.co.x) for v in bm.verts if zmin + 0.12 < v.co.z < zmin + 0.22)
W = belly[int(0.95 * (len(belly) - 1))]
H = zmax - zmin
z_neck = zmax - 0.035            # the vest's neck sits a little below the polo's collar seam
z_arm = zmin + 0.62 * H          # the armholes open above this
print(f"polo: {len(bm.verts)} verts, z {zmin:.3f}..{zmax:.3f}, belly half width {W:.3f}, front {'-Y' if FRONT < 0 else '+Y'}")


def keep(c):
    """Inside the vest: below the neck, inside the armholes (narrowing over the shoulders), not in the front opening."""
    if c.z > z_neck or c.z < zmin + 0.005:
        return False
    if c.z > z_arm:
        t = (c.z - z_arm) / max(z_neck - z_arm, 1e-3)
        lim = W * (1.06 - 0.28 * t)        # the shoulder straps get narrower toward the neck
    else:
        lim = W * 1.12
    if abs(c.x) > lim:
        return False
    if FRONT * c.y > 0 and abs(c.x) < 0.011:    # the opening where the two front panels meet
        return False
    return True


bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
# Finer faces, so the straps' edges are straight enough.
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
bm.normal_update()
# The foam: everything out along its normal (smoothed normals, so the panels stay smooth).
normals = {v: v.normal.copy() for v in bm.verts}
for _ in range(2):
    normals = {v: (normals[v] + sum((normals[e.other_vert(v)] for e in v.link_edges), Vector())).normalized() for v in bm.verts}
for v in bm.verts:
    v.co += normals[v] * FOAM
bm.normal_update()

# Straps: three bands across the chest, one down each front panel; raised 4 mm.
bands = [zmin + f * H for f in (0.2, 0.38, 0.55)]
for f in bm.faces:
    c = f.calc_center_median()
    across = any(abs(c.z - b) < 0.019 for b in bands)
    down = FRONT * c.y > 0 and 0.075 < abs(c.x) < 0.11 and c.z < z_neck - 0.01
    if across or down:
        f.material_index = STRAPS
    else:
        f.material_index = PFD
lift = set()
for f in bm.faces:
    if f.material_index == STRAPS:
        lift.update(f.verts)
for v in lift:
    v.co += normals[v] * 0.004
bm.normal_update()

# Piping: every open edge turned back toward the shirt (the foam's thickness), in a lighter blue.
edges = [e for e in bm.edges if e.is_boundary]
ret = bmesh.ops.extrude_edge_only(bm, edges=edges)
new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
for v in new_verts:
    n = next((normals[u] for e in v.link_edges for u in e.verts if u in normals), Vector((0, 0, 1)))
    v.co -= n * (FOAM + 0.003)
for g in ret["geom"]:
    if isinstance(g, bmesh.types.BMFace):
        g.material_index = PIPING


# Buckles: a female and a male half on each chest strap, a little to one side of the opening, on the vest's surface.
tree_bm = bm.copy()
from mathutils.bvhtree import BVHTree
tree = BVHTree.FromBMesh(tree_bm)


def box(centre, half, axes):
    ux, uy, uz = axes
    vs = [bm.verts.new(centre + ux * sx * half[0] + uy * sy * half[1] + uz * sz * half[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        f = bm.faces.new([vs[i] for i in q])
        f.material_index = BUCKLE


for b in bands:
    for x, half in ((0.035, (0.026, 0.006, 0.026)), (-0.03, (0.02, 0.005, 0.021))):   # either side of the opening
        hit = tree.ray_cast(Vector((x, FRONT * 1.0, b)), Vector((0, -FRONT, 0)), 2.0)
        if hit[0] is None:
            continue
        n = hit[1]
        ux = Vector((1, 0, 0))
        uz = Vector((0, 0, 1))
        box(hit[0] + n * (half[1] + 0.002), half, (ux, n, uz))
tree_bm.free()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

# UVs: a cylinder round the torso, in metres (the crew fabric's weave stays square).
uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
for f in bm.faces:
    for loop in f.loops:
        c = loop.vert.co
        loop[uv].uv = (math.atan2(c.x, c.y) * 0.2, c.z)
tris = sum(len(f.verts) - 2 for f in bm.faces)
bm.transform(M.inverted())
me = bpy.data.meshes.new("Vest")
bm.to_mesh(me)
bm.free()
for s_ in ("PFD", "Straps", "Buckle", "Piping"):
    me.materials.append(bpy.data.materials.new(s_))
for p in me.polygons:
    p.use_smooth = True
for o in list(bpy.context.scene.objects):
    bpy.data.objects.remove(o)
out = bpy.data.objects.new("Vest", me)
out.matrix_world = M
bpy.context.scene.collection.objects.link(out)
bpy.ops.object.select_all(action="DESELECT")
out.select_set(True)
bpy.context.view_layer.objects.active = out
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, mesh_smooth_type="FACE")
print(f"Vest: {tris} tris, straps at z {', '.join(f'{b:.3f}' for b in bands)} -> {OUT}")
