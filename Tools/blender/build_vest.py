"""Graphics G6: the club's Type III life jacket tailored over a sailor's polo (Tools/blender/build_polo.py output), so it is
skinned like the polo and wraps the body however the sailor sits (the rigid SM_CrewPFD sat inside the polo on the bigger
sailors: round 7's crew close-ups, and Bean's lesson photos for the look).

From the polo's own shirt panels (already fitted to that body) it keeps the torso below the neck and inside the armholes,
splits it down the front where the two foam panels meet, and stands it 2.2 cm off the shirt (the foam). Then: three grey
webbing straps across the chest and a strap down each front panel, black side-release buckles off-centre, and lighter
blue piping round every edge (the hem, neck, armholes and the front opening, turned back to the shirt).

Graphics G8 (round 8: "the crew close-up lacks texture and detail"; G6's open item, ragged armholes): every outline is cut
as a straight line on the shirt before faces are chosen (bmesh bisect: the armhole as three segments, the neck, the hem,
the opening, each strap's edges), so the edges no longer step along the shirt's triangles. The straps are raised 3 mm with
side walls (webbing sewn on, not paint). The buckles are two bevelled halves (the female frame and the male tongue) on the
strap's line. The foam's vertical channels and the stitching are in the material (M_CrewFabric's ChanPeriod).

Slots: PFD (royal blue nylon, recoloured per sailor), Straps, Buckle, Piping. A static mesh in the outfit's own space;
scripts/import_crew_clothes.py copies the T-shirt's skin weights onto it (SKM_<Role>_Vest).

    blender -b --factory-startup -P Tools/blender/build_vest.py -- <Role>_Polo.fbx <Role>_Vest.fbx [<Role>_PoloOpen.fbx]
Prints "Vest: <tris> ..." (and with the third path, the polo with its torso under the vest cut away: imported as the polo).
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = ARGS[:2]
OUT_POLO = ARGS[2] if len(ARGS) > 2 else None
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
obj = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
M = obj.matrix_world.copy()
PFD, STRAPS, BUCKLE, PIPING = 0, 1, 2, 3
FOAM = 0.022
WEB = 0.003          # the webbing stands this far off the foam
HALF_STRAP = 0.019   # 38 mm webbing

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
z_hem = zmin + 0.05              # the polo shows a little below the vest (and the cut clears its uneven hem)
OPEN = 0.011                     # half the gap between the front panels
# The armhole's outline (half width against height): straight down the side below the armpit, then curving in to the
# shoulder strap at the neck.
ARM = [(W * 1.12, zmin - 1.0), (W * 1.12, z_arm - 0.02), (W * 0.99, z_arm + 0.35 * (z_neck - z_arm)), (W * 0.80, z_neck)]
print(f"polo: {len(bm.verts)} verts, z {zmin:.3f}..{zmax:.3f}, belly half width {W:.3f}, front {'-Y' if FRONT < 0 else '+Y'}")


def lim(z):
    for (x0, z0), (x1, z1) in zip(ARM, ARM[1:]):
        if z <= z1:
            return x0 + (x1 - x0) * (z - z0) / max(z1 - z0, 1e-6)
    return ARM[-1][0]


def keep(c):
    """Inside the vest: below the neck, above the hem, inside the armholes, not in the front opening."""
    if c.z > z_neck or c.z < z_hem:
        return False
    if abs(c.x) > lim(c.z):
        return False
    if FRONT * c.y > 0 and abs(c.x) < OPEN:
        return False
    return True


def cut(co, no):
    """A straight cut through the shirt along a plane."""
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=Vector(co), plane_no=Vector(no).normalized(), dist=1e-5)


# Graphics G8: the polo with its torso under the vest cut away (a margin inside the vest's edges, so its piping covers the
# cut). Nothing can then show through the vest where the two are skinned a little differently (the trimmer's shoulders,
# seated); the MetaHuman body has no torso under the clothes, and the vest's inside is never in view.
if OUT_POLO:
    MARGIN = 0.02
    pm = bmesh.new()
    pm.from_mesh(obj.data)
    pm.transform(M)

    def covered(c):
        # (6 cm in from the armholes: the vest's sides follow the arm a little more than the shirt does)
        if c.z > z_neck - MARGIN or c.z < z_hem + MARGIN or abs(c.x) > lim(c.z) - 0.06:
            return False
        return not (FRONT * c.y > 0 and abs(c.x) < OPEN + MARGIN)

    gone = [f for f in pm.faces if f.material_index in polo and covered(f.calc_center_median())]
    bmesh.ops.delete(pm, geom=gone, context="FACES")
    bmesh.ops.delete(pm, geom=[v for v in pm.verts if not v.link_faces], context="VERTS")
    pm.transform(M.inverted())
    pme = bpy.data.meshes.new("PoloOpen")
    pm.to_mesh(pme)
    pm.free()
    for m in obj.data.materials:
        pme.materials.append(m)
    po = bpy.data.objects.new("PoloOpen", pme)
    po.matrix_world = M
    bpy.context.scene.collection.objects.link(po)
    bpy.ops.object.select_all(action="DESELECT")
    po.select_set(True)
    bpy.context.view_layer.objects.active = po
    bpy.ops.export_scene.fbx(filepath=OUT_POLO, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, mesh_smooth_type="FACE")
    bpy.data.objects.remove(po)
    print(f"Polo under the vest: {len(gone)} faces cut -> {OUT_POLO}")

# The outline: neck, hem, the opening, the armhole segments either side.
cut((0, 0, z_neck), (0, 0, 1))
cut((0, 0, z_hem), (0, 0, 1))
for s in (-1, 1):
    cut((s * OPEN, 0, 0), (1, 0, 0))
    for (x0, z0), (x1, z1) in zip(ARM, ARM[1:]):
        d = Vector((s * (x1 - x0), 0, z1 - z0))
        cut((s * x0, 0, z0), Vector((d.z, 0, -d.x)))
bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
# Bisect leaves slivers where a cut ran close to an existing vertex: weld them.
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)

# The straps' edges: three bands across the chest, one down each front panel.
bands = [zmin + f * H for f in (0.2, 0.38, 0.55)]
for b in bands:
    cut((0, 0, b - HALF_STRAP), (0, 0, 1))
    cut((0, 0, b + HALF_STRAP), (0, 0, 1))
DOWN = (0.075, 0.11)
for s in (-1, 1):
    for x in DOWN:
        cut((s * x, 0, 0), (1, 0, 0))
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
# (G6 subdivided once so the face-picked straps' edges were straight enough: the cuts make that unnecessary, and the vest
# stays near the polo's own density.)
bm.normal_update()


def is_strap(c):
    across = any(abs(c.z - b) < HALF_STRAP for b in bands)
    down = FRONT * c.y > 0 and DOWN[0] < abs(c.x) < DOWN[1] and c.z < z_neck - 0.01
    return across or down


for f in bm.faces:
    f.material_index = STRAPS if is_strap(f.calc_center_median()) else PFD

# The foam: everything out along its normal (smoothed normals, so the panels stay smooth). The normal is kept on each
# vertex (float layers, copied to the vertices the extrusions below make).
NL = [bm.verts.layers.float.new(k) for k in ("nx", "ny", "nz")]   # (before any vertex is held: a new layer moves them)
normals = {v: v.normal.copy() for v in bm.verts}
for _ in range(6):   # Graphics G8: smoother (foam doesn't follow the shirt's creases, and the cut lines stay straight)
    normals = {v: (normals[v] + sum((normals[e.other_vert(v)] for e in v.link_edges), Vector())).normalized() for v in bm.verts}


def nrm(v):
    return Vector((v[NL[0]], v[NL[1]], v[NL[2]]))


for v in bm.verts:
    v.co += normals[v] * FOAM
    for k in range(3):
        v[NL[k]] = normals[v][k]
bm.normal_update()

# Piping: every open edge rolled over toward the shirt in a lighter blue: out 2 mm and back 4 mm, then down the foam's
# thickness.
edges = [e for e in bm.edges if e.is_boundary]
rim = {v for e in edges for v in e.verts}
outward = {}
for v in rim:
    d = sum((f.calc_center_median() - v.co for f in v.link_faces), Vector())
    d -= nrm(v) * d.dot(nrm(v))
    outward[v] = -d.normalized()
ret = bmesh.ops.extrude_edge_only(bm, edges=edges)
for v in [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]:
    orig = next((u for e in v.link_edges for u in e.verts if u in rim), None)
    if orig is not None:
        v.co = orig.co + outward[orig] * 0.002 - nrm(orig) * 0.004
for g in ret["geom"]:
    if isinstance(g, bmesh.types.BMFace):
        g.material_index = PIPING
edges = [e for e in bm.edges if e.is_boundary]
ret = bmesh.ops.extrude_edge_only(bm, edges=edges)
for v in [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]:
    v.co -= nrm(v) * (FOAM - 0.002)
for g in ret["geom"]:
    if isinstance(g, bmesh.types.BMFace):
        g.material_index = PIPING

# The webbing stands off the foam with its own edges (sewn on).
straps = [f for f in bm.faces if f.material_index == STRAPS]
ret = bmesh.ops.extrude_face_region(bm, geom=straps)
for v in [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]:
    v.co += nrm(v) * WEB
for g in ret["geom"]:
    if isinstance(g, bmesh.types.BMFace):
        g.material_index = STRAPS
bm.normal_update()

# Buckles: a side-release buckle on each chest strap, across the opening: the female frame on one panel, the male tongue
# from the other, on the strap's line and the vest's surface.
tree_bm = bm.copy()
tree = BVHTree.FromBMesh(tree_bm)


def block(centre, half, axes, bevel):
    """A box (half sizes along the strap, out, up) with its edges rounded."""
    ux, uy, uz = axes
    vs = [bm.verts.new(centre + ux * sx * half[0] + uy * sy * half[1] + uz * sz * half[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = []
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        f = bm.faces.new([vs[i] for i in q])
        f.material_index = BUCKLE
        faces.append(f)
    edges = list({e for f in faces for e in f.edges})
    bmesh.ops.bevel(bm, geom=edges + vs, offset=bevel, segments=2, affect="EDGES", profile=0.5)


n_buckles = 0
for b in bands:
    # (along the strap from the opening, half length, half height, half thickness, bevel)
    for x, hl, hh, ht, bev in ((0.026, 0.016, 0.023, 0.0045, 0.003), (-0.010, 0.014, 0.019, 0.0035, 0.0025)):
        hit = tree.ray_cast(Vector((x, FRONT * 1.0, b)), Vector((0, -FRONT, 0)), 2.0)
        if hit[0] is None:
            continue
        n = hit[1].normalized()
        uz = Vector((0, 0, 1))
        ux = uz.cross(n).normalized()
        uz = n.cross(ux).normalized()
        block(hit[0] + n * (ht + 0.001), (hl, ht, hh), (ux, n, uz), bev)
        n_buckles += 1
tree_bm.free()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

# UVs: a cylinder round the torso, in metres (the crew fabric's weave stays square; the foam's channels run up it).
uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
R = W * 1.1
for f in bm.faces:
    for loop in f.loops:
        c = loop.vert.co
        loop[uv].uv = (math.atan2(c.x, c.y) * R, c.z)
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
print(f"Vest: {tris} tris, {n_buckles} buckle halves, straps at z {', '.join(f'{b:.3f}' for b in bands)} -> {OUT}")
