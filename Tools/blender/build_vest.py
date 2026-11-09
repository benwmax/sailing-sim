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

Crew life vest detail pass (Nov 2026, docs/part-detail-loop/crewvest.md): the strap layout, buckles, tails, binding, foam
and rolled edges rebuilt against Bean's lesson photo of the club's vest.

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
# Crew life vest detail pass (Nov 2026, Tools/boatkit/partloop/parts/crewvest.json, against Bean's lesson photo of the
# club's royal blue foam Type III): the front panels are thicker foam than the back (about 3 cm against 2), every edge is a
# rolled foam edge instead of a 2 mm piping lip, and only the armholes and the shoulders carry the lighter blue binding (the
# vest's lining turned over the edge, about 2 cm wide on the face); the hem and the front opening are the shell's own blue.
FOAM_FRONT, FOAM_BACK = 0.032, 0.022
ROLL = 0.007         # the rolled edge's radius
BIND = 0.02          # the lighter binding's width on the face, along the armholes and over the shoulders
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
OPEN = 0.005                     # half the gap between the front panels (detail pass: closed up, as zipped; was 11 mm)
# Detail pass: the front panels' top edges drop in a shallow V to the opening (the photo's neckline), V_DROP below the neck
# at the centre, meeting the neck V_HALF out.
V_DROP, V_HALF = 0.065, 0.085
LEFT = -FRONT                    # +1: the wearer's left is +X (facing -Y, Z up). The buckles sit on the left panel.
# The armhole's outline (half width against height): straight down the side below the armpit, then curving in to the
# shoulder strap at the neck.
# Round 11 ("person looks like a doll"): seated, the arm swings forward and the armhole's edge tore into a zigzag; the
# armhole is 2 cm more open above the armpit (ARMHOLE_OPEN), and the import keeps the arm bones off the vest.
# Clipping audit 2 (the side panel showing under the trimmer's arm, between the sleeve and the torso): the armhole is
# wider at its bottom. The side runs straight up to ARMHOLE_FOOT under the armpit, then tapers in to the torso's own width
# (W) at the armpit, so the vest's edge sits on the torso where the arm comes down rather than inside the arm.
ARMHOLE_OPEN = 0.02
ARMHOLE_FOOT = 0.09
ARM = [(W * 1.12, zmin - 1.0), (W * 1.12, z_arm - ARMHOLE_FOOT), (W * 1.0 - ARMHOLE_OPEN, z_arm - 0.02),
       (W * 0.97 - ARMHOLE_OPEN, z_arm + 0.35 * (z_neck - z_arm)), (W * 0.92 - ARMHOLE_OPEN, z_neck)]
# (Detail pass: the armhole meets the neck at 0.92 W, was 0.80 W: the shoulder straps were about 4 cm wide over the top of
# the shoulder, the photo's are about 7; the armhole below the shoulder, where the arm swings, is unchanged.)
print(f"polo: {len(bm.verts)} verts, z {zmin:.3f}..{zmax:.3f}, belly half width {W:.3f}, front {'-Y' if FRONT < 0 else '+Y'}")


def lim(z):
    for (x0, z0), (x1, z1) in zip(ARM, ARM[1:]):
        if z <= z1:
            return x0 + (x1 - x0) * (z - z0) / max(z1 - z0, 1e-6)
    return ARM[-1][0]


def z_top(c):
    """The vest's top edge over this point: the neck, or on the front the V down to the opening."""
    if FRONT * c.y > 0 and abs(c.x) < V_HALF:
        return z_neck - V_DROP * (1.0 - abs(c.x) / V_HALF)
    return z_neck


def keep(c):
    """Inside the vest: below the neck (and the front's V), above the hem, inside the armholes, not in the front opening."""
    if c.z > z_top(c) or c.z < z_hem:
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
        # (7 cm in from the armholes, 9 cm in from round 10's: the vest's sides follow the arm a little more than the shirt)
        if c.z > z_top(c) - MARGIN or c.z < z_hem + MARGIN or abs(c.x) > lim(c.z) - 0.07:
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
    # (the front's V: a plane through the opening's top and the neck V_HALF out, square to the front)
    cut((0, 0, z_neck - V_DROP), Vector((-s * V_DROP, 0, V_HALF)))
    cut((s * V_HALF, 0, 0), (1, 0, 0))
    for (x0, z0), (x1, z1) in zip(ARM, ARM[1:]):
        d = Vector((s * (x1 - x0), 0, z1 - z0))
        cut((s * x0, 0, z0), Vector((d.z, 0, -d.x)))
        # the binding's inner edge, BIND in from the armhole (detail pass)
        cut(Vector((s * x0, 0, z0)) + Vector((-s * BIND, 0, 0)), Vector((d.z, 0, -d.x)))
cut((0, 0, z_neck - BIND), (0, 0, 1))
bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
# Bisect leaves slivers where a cut ran close to an existing vertex: weld them.
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)

# The straps' edges: three bands across the chest, one down each front panel.
# Detail pass (the photo): the bands sit at 18%, 40% and 66% of the vest's height up from the hem (the top one at the
# armpits; they were at 20/38/55% of the polo's and bunched low), and a single strap runs down the wearer's right panel
# only, from a little above the middle band to a little below the bottom one (there were two on each panel, a ladder).
bands = [z_hem + f * (z_neck - z_hem) for f in (0.18, 0.40, 0.66)]
for b in bands:
    cut((0, 0, b - HALF_STRAP), (0, 0, 1))
    cut((0, 0, b + HALF_STRAP), (0, 0, 1))
DOWN = (0.072, 0.110)
DOWN_Z = (bands[0] - HALF_STRAP - 0.035, bands[1] + HALF_STRAP + 0.05)
for x in DOWN:
    cut((-LEFT * x, 0, 0), (1, 0, 0))
for z in DOWN_Z:
    cut((0, 0, z), (0, 0, 1))
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
# (G6 subdivided once so the face-picked straps' edges were straight enough: the cuts make that unnecessary, and the vest
# stays near the polo's own density.)
bm.normal_update()


def is_strap(c):
    across = any(abs(c.z - b) < HALF_STRAP for b in bands)
    down = FRONT * c.y > 0 and DOWN[0] < -LEFT * c.x < DOWN[1] and DOWN_Z[0] < c.z < DOWN_Z[1]
    return across or down


def is_binding(c):
    """Detail pass: the lighter lining turned over the armholes and the shoulders, BIND wide on the face."""
    return abs(c.x) > lim(c.z) - BIND or c.z > z_neck - BIND


for f in bm.faces:
    c = f.calc_center_median()
    f.material_index = STRAPS if is_strap(c) else PIPING if is_binding(c) else PFD

# The foam: everything out along its normal (smoothed normals, so the panels stay smooth). The normal is kept on each
# vertex (float layers, copied to the vertices the extrusions below make).
NL = [bm.verts.layers.float.new(k) for k in ("nx", "ny", "nz")]   # (before any vertex is held: a new layer moves them)
FM = bm.verts.layers.float.new("foam")
normals = {v: v.normal.copy() for v in bm.verts}
for _ in range(6):   # Graphics G8: smoother (foam doesn't follow the shirt's creases, and the cut lines stay straight)
    normals = {v: (normals[v] + sum((normals[e.other_vert(v)] for e in v.link_edges), Vector())).normalized() for v in bm.verts}


def nrm(v):
    return Vector((v[NL[0]], v[NL[1]], v[NL[2]]))


def foam(n):
    """The foam's thickness: FOAM_FRONT where the vest faces forward, FOAM_BACK on the back, blended round the sides."""
    t = min(1.0, max(0.0, (FRONT * n.y + 0.2) / 0.8))
    return FOAM_BACK + (FOAM_FRONT - FOAM_BACK) * t * t * (3 - 2 * t)


for v in bm.verts:
    v[FM] = foam(normals[v])
    v.co += normals[v] * v[FM]
    for k in range(3):
        v[NL[k]] = normals[v][k]
bm.normal_update()

# The edges (detail pass): every open edge is the foam rolled over toward the shirt, a quarter round of radius ROLL in
# three steps and then straight down the rest of the foam's thickness (G8 had a 2 mm lip and a flat wall, every edge in the
# lighter piping blue). Its colour follows the face beside it: binding on the armholes and the shoulders, the shell's blue
# at the hem and the front opening.
edges = [e for e in bm.edges if e.is_boundary]
rim = {v for e in edges for v in e.verts}
outward = {}
for v in rim:
    d = sum((f.calc_center_median() - v.co for f in v.link_faces), Vector())
    d -= nrm(v) * d.dot(nrm(v))
    outward[v] = -d.normalized()
edge_mat = {}
for e in edges:
    edge_mat[frozenset(e.verts)] = e.link_faces[0].material_index if e.link_faces[0].material_index != STRAPS else PFD
origin = {v: v for v in rim}
for step, ang in enumerate((30, 60, 90, None)):
    ret = bmesh.ops.extrude_edge_only(bm, edges=edges)
    new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    nxt = {}
    for v in new_verts:
        prev = next((u for e in v.link_edges for u in e.verts if u is not v and u in origin), None)
        if prev is None:
            continue
        o = origin[prev]
        if ang is None:
            v.co = o.co + outward[o] * ROLL - nrm(o) * (o[FM] - 0.002)
        else:
            t = math.radians(ang)
            v.co = o.co + outward[o] * ROLL * math.sin(t) - nrm(o) * ROLL * (1 - math.cos(t))
        nxt[v] = o
    for g in ret["geom"]:
        if isinstance(g, bmesh.types.BMFace):
            src = {nxt.get(v, origin.get(v)) for v in g.verts}
            g.material_index = edge_mat.get(frozenset(src), PFD) if len(src) == 2 else PFD
    origin = nxt
    edges = [e for e in bm.edges if e.is_boundary]

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


def block(centre, half, axes, bevel, recess=0.0):
    """A box (half sizes along the strap, out, up) with its edges rounded. Detail pass: with a recess, its face is a
    frame round a sunken centre (the buckle's moulded window), and every face the bevel makes stays black."""
    ux, uy, uz = axes
    vs = [bm.verts.new(centre + ux * sx * half[0] + uy * sy * half[1] + uz * sz * half[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = []
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        f = bm.faces.new([vs[i] for i in q])
        f.material_index = BUCKLE
        faces.append(f)
    edges = list({e for f in faces for e in f.edges})
    ret = bmesh.ops.bevel(bm, geom=edges + vs, offset=bevel, segments=2, affect="EDGES", profile=0.5)
    made = set(ret["faces"]) | {f for f in faces if f.is_valid}
    for f in made:
        f.material_index = BUCKLE
    if recess > 0:
        front = max((f for f in made if f.is_valid), key=lambda f: f.normal.dot(uy) * f.calc_area())
        r = bmesh.ops.inset_region(bm, faces=[front], thickness=min(half[0], half[2]) * 0.28, depth=-recess)
        for f in r["faces"]:
            f.material_index = BUCKLE


n_buckles = 0
for b in bands:
    # (along the strap from the opening, half length, half height, half thickness, bevel)
    # Detail pass: full-size 38 mm side-release buckles (the female 46 mm tall and 50 mm long on the wearer's left panel
    # from the opening, the male half with its ladder lock 32 mm across the opening; they were 46 x 32 and read as small dark squares).
    for x, hl, hh, ht, bev in ((LEFT * 0.031, 0.025, 0.023, 0.0055, 0.0035), (-LEFT * 0.008, 0.016, 0.019, 0.004, 0.0028)):
        hit = tree.ray_cast(Vector((x, FRONT * 1.0, b)), Vector((0, -FRONT, 0)), 2.0)
        if hit[0] is None:
            continue
        n = hit[1].normalized()
        uz = Vector((0, 0, 1))
        ux = uz.cross(n).normalized()
        uz = n.cross(ux).normalized()
        block(hit[0] + n * (ht + 0.001), (hl, ht, hh), (ux, n, uz), bev, recess=ht * 0.45)
        n_buckles += 1


def surface(x, z, last):
    """The vest's face (with its straps) at (x, z), and its normal. Off the face (the rolled hem, a strap's wall, past
    the hem) it carries straight on from the last point on the face, never following the roll in toward the shirt."""
    hit = tree.ray_cast(Vector((x, FRONT * 1.0, z)), Vector((0, -FRONT, 0)), 2.0)
    if hit[0] is not None and abs(hit[1].normalized().z) < 0.5:
        return hit[0], hit[1].normalized()
    if last is None:
        return (hit[0], hit[1].normalized()) if hit[0] is not None else None
    if last[0].z - z > TAIL_PAST + 0.03:
        return None
    return Vector((x, last[0].y, z)), last[1]


def tail(b, x_in, x_fold, length, lean, lift=0.0):
    """The strap's loose end (round 11; Bean Nov 9: "the tails should run through the buckles"). A side-release buckle
    is adjusted at the male half's ladder lock: the strap from the right panel runs into it, round its bar, and the free
    end comes back out of it lying doubled on the incoming strap. So the ribbon starts inside the male half (x_in, on the
    band's line), runs out over the strap to x_fold, folds down across itself in a 45 degree crease (the ribbon's
    mitred corner) and hangs down over the foam, past the hem by up to TAIL_PAST (a 38 mm ribbon, 2 mm thick, standing a
    little further off the vest as it falls: webbing is stiff)."""
    out = 1.0 if x_fold > x_in else -1.0
    # The centre line: along the band, then the fold's corner, then down. The corner sits HALF_STRAP in from x_fold, so
    # the doubled end's outer edge stops at x_fold.
    # The doubled run stops at the crease's inner end (2 half widths in from x_fold), so its lower edge never folds back
    # past the corner; it needs x_fold at least 2 half widths out from x_in.
    xc = x_fold - out * HALF_STRAP
    x_stop = xc - out * HALF_STRAP
    path = [(x_in + (x_stop - x_in) * k / 3, b, 0.0) for k in range(4)] + [(xc, b, 0.0)]
    steps = 10
    path += [(xc + lean * (k / steps), b - (HALF_STRAP + (length - HALF_STRAP) * k / steps) if k else b - HALF_STRAP, k / steps)
             for k in range(1, steps + 1)]
    pts = []
    last = None
    for x, z, t in path:
        hit = surface(x, z, last)
        if hit is None:
            break
        if abs(hit[1].z) < 0.5:
            last = hit
        # (the doubled layer lies on the strap: 2.5 mm over it; the hanging part stands off more as it falls)
        pts.append((hit[0] + hit[1] * (0.0025 + lift * min(1.0, 3.0 * t) + 0.012 * t * t), hit[1]))   # (lift: off the strap once hanging)
    if len(pts) < 7:
        return False
    rows = []
    for i, (c, n) in enumerate(pts):
        prev = pts[max(i - 1, 0)][0]
        nxt = pts[min(i + 1, len(pts) - 1)][0]
        if i == 4:
            # The crease: the corner's cross-section runs along the 45 degree fold, sqrt 2 times the half width.
            d_in = (c - prev).normalized()
            d_out = (nxt - c).normalized()
            across = (n.cross(d_in) + n.cross(d_out)).normalized() * (HALF_STRAP * math.sqrt(2.0))
        else:
            across = n.cross((nxt - prev).normalized()).normalized() * HALF_STRAP
        rows.append([c - across - n * 0.001, c + across - n * 0.001, c + across + n * 0.001, c - across + n * 0.001])
    vs = [[bm.verts.new(p) for p in r] for r in rows]
    for ra, rb in zip(vs, vs[1:]):
        for k in range(4):
            f = bm.faces.new((ra[k], ra[(k + 1) % 4], rb[(k + 1) % 4], rb[k]))
            f.material_index = STRAPS
    bm.faces.new(vs[0]).material_index = STRAPS          # (inside the buckle)
    # Round 12: the end cut as webbing is, a hot-knife point (14 mm), not a square slab: its corners fold in to a tip
    # on the strap's line, both faces of the ribbon meeting the two cut edges.
    ca, cb = [sum((v.co for v in r), Vector()) / 4 for r in (vs[-2], vs[-1])]
    d = (cb - ca).normalized()
    lb, rb_, rf, lf = vs[-1]
    nn = (lf.co - lb.co).normalized() * 0.001
    tb, tf = bm.verts.new(cb + d * 0.014 - nn), bm.verts.new(cb + d * 0.014 + nn)
    for f in ((lb, rb_, tb), (lf, tf, rf), (rb_, rf, tf, tb), (lb, tb, tf, lf)):
        bm.faces.new(f).material_index = STRAPS
    return True


n_tails = 0
TAIL_PAST = 0.04
for i, b in enumerate(bands):
    # Detail pass (the photo; Bean Nov 9: the tails run through the buckles): each loose end comes back out of the male
    # half's ladder lock and folds down: the top one a short tab, the lower two long tails past the hem. (They hung from the female buckle's far end, pasted on.)
    # (The top and bottom creases lie under the male half, so those tails come out from under the buckle's lower edge.
    # The middle one folds at the male half's outer end and hangs straight down beside the bottom buckle, flat on the
    # bottom band as it crosses it, as in the photo: a diagonal tail floating over the bottom buckle read as pasted on.)
    male_out = -LEFT * 0.024
    x_in = (LEFT * 0.006, male_out + LEFT * 0.004, LEFT * 0.006)[i]
    n_tails += tail(b, x_in, x_in - LEFT * 2.0 * HALF_STRAP, (0.20, 0.24, 0.08)[i], LEFT * (0.01, -0.006, 0.0)[i],
                    (0.0, 0.002, 0.0)[i])
tree_bm.free()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

# UVs: a cylinder round the torso, in metres (the crew fabric's weave stays square; the foam's channels run up it).
uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
R = W * 1.1
for f in bm.faces:
    for loop in f.loops:
        c = loop.vert.co
        # Round 11: U = 0 at the front's centre whichever way the outfit faces (M_CrewFabric keeps the foam's channels off
        # the two flat front panels by |U|); the seam is at the back.
        loop[uv].uv = (math.atan2(c.x, FRONT * c.y) * R, c.z)
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
print(f"Vest: {tris} tris, {n_buckles} buckle halves, {n_tails} strap tails, straps at z {', '.join(f'{b:.3f}' for b in bands)} -> {OUT}")
