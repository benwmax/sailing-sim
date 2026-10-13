"""Graphics G3: a polo shirt tailored from a MetaHuman's default T-shirt (free, scripted clothing; method in
Inputs/g3/realistic-clothing-method.md). The T-shirt is already fitted to that sailor's body and skinned, so the polo keeps
its panels and adds what makes a polo read as one:

  - a fold-down knit collar on a stand, its points either side of the placket
  - a two-button placket down the front (raised band, buttons)
  - ribbed cuffs on the sleeves (the last 2.5 cm, slot Rib)
  - fabric folds: a slow ripple all over, horizontal creases at the waist (sitting sailors bunch there), drape at the
    sleeve heads

Slots: Polo (the body of the shirt, coloured per sailor), Rib (collar and cuffs), Button. The result is a static mesh in
the outfit's own space; scripts/import_crew_clothes.py copies the T-shirt's skin weights onto it in Unreal.

    blender -b --factory-startup -P Tools/blender/build_polo.py -- <Role>_Outfit.fbx <Role>_Polo.fbx
Prints "Polo: <tris> ..." and the landmarks it found.
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

SRC, OUT = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
obj = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
M = obj.matrix_world.copy()
POLO, RIB, BUTTON = 0, 1, 2

# The T-shirt alone (LOD0's shirt section), in world metres.
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.transform(M)
shirt = [i for i, m in enumerate(obj.data.materials) if m and m.name.endswith("_Shirt")]
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in shirt], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
# The export splits vertices along UV and normal seams: weld them. The shirt is then a closed shell: at the neck, the hem
# and the sleeve ends its fabric turns back inside (a facing), so those openings are fold edges, not open boundaries.
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0002)
bm.normal_update()
# The facings are inside the shell: a face whose normal runs into the shirt within a centimetre is one. Drop them, and the
# openings become open boundaries again (the collar and cuffs replace what they did).
inner_tree = BVHTree.FromBMesh(bm)
inner = []
for f in bm.faces:
    c = f.calc_center_median()
    hit = inner_tree.ray_cast(c + f.normal * 0.0003, f.normal, 0.01)
    if hit[0] is not None:
        inner.append(f)
bmesh.ops.delete(bm, geom=inner, context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.normal_update()
print(f"facings removed: {len(inner)} faces")
for f in bm.faces:
    f.material_index = POLO
bm.verts.ensure_lookup_table()
bm.normal_update()
uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")

zs = [v.co.z for v in bm.verts]
zmin, zmax = min(zs), max(zs)
ys = [v.co.y for v in bm.verts]
# Front: the side the chest and belly push out to (MetaHumans face +Y in Unreal, which the FBX round trip may flip).
mid = [v.co for v in bm.verts if abs(v.co.x) < 0.04 and zmin + 0.25 < v.co.z < zmin + 0.45]
FRONT = -1.0 if sum(c.y for c in mid) / len(mid) < sum(ys) / len(ys) else 1.0
print(f"shirt: {len(bm.verts)} verts, z {zmin:.3f}..{zmax:.3f}, front {'-Y' if FRONT < 0 else '+Y'}")

# Openings: the neck (highest), the hem (lowest), the two sleeve ends (farthest out in X).
boundary = [e for e in bm.edges if e.is_boundary]
rim = set(boundary)
loops, seen = [], set()
for e in boundary:
    if e in seen:
        continue
    loop, stack = set(), [e]
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        loop.add(x)
        for v in x.verts:
            stack.extend(y for y in v.link_edges if y in rim and y not in seen)
    verts = {v for x in loop for v in x.verts}
    c = sum((v.co for v in verts), Vector()) / len(verts)
    loops.append((c, verts, loop))
for c, verts, _ in loops:
    print(f"  opening at ({c.x:.3f}, {c.y:.3f}, {c.z:.3f}), {len(verts)} verts")
# Pinholes where a facing met the outer layer: fill them. What remains are the real openings.
small = [l for l in loops if len(l[1]) < 12]
for _, _, edges in small:
    bmesh.ops.holes_fill(bm, edges=list(edges), sides=0)
loops = [l for l in loops if len(l[1]) >= 12]
neck = max([l for l in loops if l[0].z > max(x[0].z for x in loops) - 0.03], key=lambda l: len(l[1]))  # the outer rim, not the facing's
hem = min(loops, key=lambda l: l[0].z)
sleeves = [l for l in loops if abs(l[0].x) > 0.15]
print(f"loops: {len(loops)}; neck at z {neck[0].z:.3f}, hem {hem[0].z:.3f}, sleeves {len(sleeves)}")


def ordered(loop_edges):
    """The vertices of a closed boundary loop in order around it."""
    adj = {}
    for e in loop_edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    start = next(iter(adj))
    out, prev, cur = [start], None, start
    while True:
        nxt = [v for v in adj[cur] if v is not prev]
        if not nxt or nxt[0] is start:
            break
        prev, cur = cur, nxt[0]
        out.append(cur)
    return out


# ---------------------------------------------------------------- folds
tree = BVHTree.FromBMesh(bm)
sleeve_c = [l[0] for l in sleeves]
for v in bm.verts:
    p = v.co
    n = v.normal
    d = 0.0025 * noise.noise(p * 7.0) + 0.0012 * noise.noise(p * 19.0 + Vector((3, 1, 2)))
    # Waist creases: a sitting sailor's shirt bunches in horizontal folds above the hem, mostly at the front and sides.
    t = (p.z - zmin) / 0.16
    if 0.0 < t < 1.0 and not any((p - c).length < 0.16 for c in sleeve_c):
        w = math.sin(math.pi * t) * (0.55 + 0.45 * max(0.0, FRONT * n.y))
        d += 0.0045 * w * math.sin(p.z * 2 * math.pi / 0.034 + 2.5 * noise.noise(p * 4.0))
    # Sleeve heads: the fabric hangs off the shoulder seam in a few soft vertical folds.
    for c in sleeve_c:
        s = (p - c).length
        if s < 0.14:
            d += 0.003 * (1 - s / 0.14) * math.sin(math.atan2(p.y - c.y, p.z - c.z) * 6.0)
    v.co = p + n * max(d, -0.0015)
bm.normal_update()

# ---------------------------------------------------------------- ribbed cuffs
for c, verts, _ in sleeves:
    for f in bm.faces:
        if all(min((v.co - u.co).length for u in verts) < 0.026 for v in f.verts):
            f.material_index = RIB

# ---------------------------------------------------------------- collar
# The neck rim, resampled as a smooth ring by angle around the neck (the rim's own edges zigzag between the shirt and
# the remains of its facing). The collar is a separate surface: its stand starts just below the rim, hiding the seam.
cen = neck[0].copy()
NA = 96
rim = [None] * NA
for v in neck[1]:
    a = math.atan2(v.co.y - cen.y, v.co.x - cen.x)
    k = int(round((a + math.pi) / (2 * math.pi) * NA)) % NA
    if rim[k] is None or (v.co - cen).xy.length > (rim[k] - cen).xy.length:
        rim[k] = v.co.copy()
known = [k for k in range(NA) if rim[k] is not None]
for k in range(NA):
    if rim[k] is None:   # gaps: between the nearest known samples either side
        a = max([j for j in known if j < k] or [known[-1] - NA])
        b = min([j for j in known if j > k] or [known[0] + NA])
        t = (k - a) / (b - a)
        rim[k] = rim[a % NA].lerp(rim[b % NA], t)
for _ in range(3):   # smooth the ring
    rim = [(rim[k - 1] + 2 * rim[k] + rim[(k + 1) % NA]) / 4 for k in range(NA)]
front_dir = Vector((0.0, FRONT, 0.0))
base, stand, leaf = [], [], []
for k in range(NA):
    p = rim[k]
    r = p - cen
    r.z = 0.0
    r.normalize()
    ang = math.degrees(math.acos(max(-1.0, min(1.0, r.dot(front_dir)))))
    if ang < 6.0:      # the placket opening: the collar's ends sit either side of it
        base.append(None); stand.append(None); leaf.append(None)
        continue
    point = max(0.0, 1.0 - (ang - 6.0) / 30.0)   # the collar's points
    base.append(bm.verts.new(p - r * 0.002 + Vector((0, 0, -0.006))))
    stand.append(bm.verts.new(p + Vector((0, 0, 0.024)) + r * 0.004))
    leaf.append(bm.verts.new(p + r * (0.048 + 0.012 * point) + Vector((0, 0, -0.006 - 0.032 * point))))
n = NA
for k in range(NA):
    a, b = k, (k + 1) % NA
    if base[a] is None or base[b] is None:
        continue
    for quad in ((base[a], base[b], stand[b], stand[a]), (stand[a], stand[b], leaf[b], leaf[a])):
        face = bm.faces.new(quad)
        face.material_index = RIB
ring = [v for v in neck[1]]

# ---------------------------------------------------------------- placket and buttons
z_top = max(rim, key=lambda p: FRONT * p.y).z
def surface(x, z):
    hit = tree.ray_cast(Vector((x, FRONT * 1.0, z)), Vector((0, -FRONT, 0)), 2.0)
    return hit[0], hit[1]
rows = []
for k in range(15):
    z = z_top - 0.01 * k
    row = []
    for x in (-0.014, 0.014):
        p, nn = surface(x, z)
        if p is None:
            break
        row.append(bm.verts.new(p + nn * 0.0028))
    if len(row) == 2:
        rows.append(row)
for a, b in zip(rows, rows[1:]):
    face = bm.faces.new((a[0], a[1], b[1], b[0]))
    face.material_index = POLO
for zb in (z_top - 0.035, z_top - 0.085):
    p, nn = surface(0.0, zb)
    if p is None:
        continue
    o = p + nn * 0.0045
    t1 = nn.cross(Vector((0, 0, 1))).normalized()
    t2 = nn.cross(t1).normalized()
    top = [bm.verts.new(o + 0.0055 * (math.cos(a) * t1 + math.sin(a) * t2)) for a in [2 * math.pi * i / 12 for i in range(12)]]
    bot = [bm.verts.new(v.co - nn * 0.0022) for v in top]
    face = bm.faces.new(top)
    face.material_index = BUTTON
    for i in range(12):
        side = bm.faces.new((top[i], bot[i], bot[(i + 1) % 12], top[(i + 1) % 12]))
        side.material_index = BUTTON

# UVs for the new parts (collar, placket, buttons): a cylinder around the torso, in metres.
for f in bm.faces:
    for loop in f.loops:
        if f.material_index != POLO or loop[uv].uv.length == 0.0:
            c = loop.vert.co
            loop[uv].uv = (math.atan2(c.x, c.y) * 0.25, c.z)

bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.material_index == BUTTON])
tris = sum(len(f.verts) - 2 for f in bm.faces)
bm.transform(M.inverted())
me = bpy.data.meshes.new("Polo")
bm.to_mesh(me)
bm.free()
for name in ("Polo", "Rib", "Button"):
    me.materials.append(bpy.data.materials.new(name))
for p in me.polygons:
    p.use_smooth = True
polo = bpy.data.objects.new("Polo", me)
polo.matrix_world = M
bpy.context.scene.collection.objects.link(polo)
bpy.ops.object.select_all(action="DESELECT")
polo.select_set(True)
bpy.context.view_layer.objects.active = polo
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, mesh_smooth_type="FACE")
print(f"Polo: {tris} tris, collar {n} segments, placket {len(rows)} rows -> {OUT}")
