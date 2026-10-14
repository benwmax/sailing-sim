"""Graphics G3: deck shoes for a MetaHuman sailor, made from that sailor's own feet (free, scripted clothing). The foot
below the ankle becomes the upper: smoothed (no toes show through leather), pushed out by the leather's thickness, with a
rolled collar at the opening; under it a white rubber sole a centimetre thick that overhangs a few millimetres; round the
collar the rawhide lace of a boat shoe, tied in a bow over the instep.

Slots: Upper (leather, coloured per sailor), Sole (white non-marking rubber), Lace. The mesh is in the body's own space;
scripts/import_crew_clothes.py copies the body's skin weights onto it in Unreal.

    blender -b --factory-startup -P Tools/blender/build_shoes.py -- <Role>_Body.fbx <Role>_Shoes.fbx
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector

SRC, OUT = sys.argv[sys.argv.index("--") + 1:][:2]
UPPER, SOLE, LACE = 0, 1, 2
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
obj = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
M = obj.matrix_world.copy()
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.transform(M)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0002)
zmin = min(v.co.z for v in bm.verts)
CUT = zmin + 0.075          # the shoe's collar: just under the ankle bones
bmesh.ops.delete(bm, geom=[f for f in bm.faces if max(v.co.z for v in f.verts) > CUT], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.verts.ensure_lookup_table()
uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
print(f"feet: {len(bm.verts)} body verts below z {CUT:.3f}")

# Each foot measured along its own heel-to-toe axis: length, and per station the half-width and the instep's height.
feet_pts = [v.co.copy() for v in bm.verts]
bm.free()
bm = bmesh.new()
uv = bm.loops.layers.uv.new("UVMap")
NS, NR = 44, 48          # stations heel to toe, points round each section
SOLE_T = 0.011           # rubber sole thickness (m)


def smooth(vals, n=3):
    for _ in range(n):
        vals = [vals[0]] + [(vals[i - 1] + 2 * vals[i] + vals[i + 1]) / 4 for i in range(1, len(vals) - 1)] + [vals[-1]]
    return vals


for foot in (1, -1):
    pts = [p for p in feet_pts if p.x * foot > 0]
    if len(pts) < 50:
        continue
    cx = sum(p.x for p in pts) / len(pts)
    cy = sum(p.y for p in pts) / len(pts)
    # Principal axis in plan: the foot's length.
    sxx = sum((p.x - cx) ** 2 for p in pts); syy = sum((p.y - cy) ** 2 for p in pts); sxy = sum((p.x - cx) * (p.y - cy) for p in pts)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ax = Vector((math.cos(ang), math.sin(ang), 0.0))
    lat = Vector((-ax.y, ax.x, 0.0))
    s_ = [(p.x - cx) * ax.x + (p.y - cy) * ax.y for p in pts]
    # Toe end: the end where the foot is lower (toes are lower than the ankle).
    lo, hi = min(s_), max(s_)
    def mean_z(a, b):
        z = [p.z for p, s in zip(pts, s_) if a <= s <= b]
        return sum(z) / max(len(z), 1)
    if mean_z(hi - 0.04, hi) > mean_z(lo, lo + 0.04):
        ax, lat = -ax, -lat
        s_ = [-s for s in s_]
        lo, hi = -hi, -lo
    L = hi - lo
    half_w, top = [0.0] * NS, [zmin + 0.03] * NS
    centre = [0.0] * NS
    for p, s in zip(pts, s_):
        i = min(NS - 1, max(0, int((s - lo) / L * (NS - 1) + 0.5)))
        d = (p.x - cx) * lat.x + (p.y - cy) * lat.y
        half_w[i] = max(half_w[i], abs(d))
        top[i] = max(top[i], p.z)
        centre[i] += d
    half_w = smooth([max(w, 0.02) for w in half_w], 4)
    top = smooth(top, 4)
    rows = []
    for i in range(NS):
        t = i / (NS - 1)
        s = lo - 0.012 + t * (L + 0.042)          # room at the heel, and the toe box 3 cm past the toes
        # Plan: full width until the last fifth, then a round toe; a short rounded heel.
        endf = math.sqrt(max(0.0, 1 - max(0.0, (t - 0.80) / 0.20) ** 2)) * math.sqrt(max(0.0, 1 - max(0.0, (0.08 - t) / 0.08) ** 2))
        j = min(NS - 1, max(0, int(round((s - lo) / L * (NS - 1)))))   # the foot's measurements at this station
        w = (half_w[j] + 0.006) * endf + 0.002
        h_top = max(top[j] + 0.013, zmin + 0.04)  # room over the instep: the ankle flexes the foot up into the vamp
        base_z = zmin - 0.002
        ring = []
        for k in range(NR):
            a = 2 * math.pi * k / NR
            c, sn = math.cos(a), math.sin(a)
            # Section: flat-bottomed, full-sided, a crowned top (a superellipse over the upper half).
            y = w * math.copysign(abs(c) ** 0.6, c)
            z = base_z + (h_top - base_z) * (0.5 + 0.5 * math.copysign(abs(sn) ** (0.7 if sn > 0 else 0.25), sn))
            pos = Vector((cx, cy, 0)) + ax * s + lat * y
            pos.z = z
            ring.append(pos)
        rows.append(ring)
    # The opening: the top of the rear 45 % (heel to instep), where the ankle goes in.
    upper = []
    for i, ring in enumerate(rows):
        upper.append([bm.verts.new(p) for p in ring])
    for i in range(NS - 1):
        t = (i + 0.5) / (NS - 1)
        for k in range(NR):
            a = 2 * math.pi * (k + 0.5) / NR
            if t < 0.46 and math.sin(a) > 0.78 - 1.2 * max(0.0, t - 0.32):
                continue
            f = bm.faces.new((upper[i][k], upper[i][(k + 1) % NR], upper[i + 1][(k + 1) % NR], upper[i + 1][k]))
            f.material_index = UPPER
    for ends in (upper[0], upper[-1]):
        f = bm.faces.new(ends)
        f.material_index = UPPER
    # The sole: the plan outline at the bottom, 3 mm proud all round, SOLE_T thick.
    outline = []
    for i in range(NS):
        t = i / (NS - 1)
        s = lo - 0.015 + t * (L + 0.048)
        endf = math.sqrt(max(0.0, 1 - max(0.0, (t - 0.80) / 0.20) ** 2)) * math.sqrt(max(0.0, 1 - max(0.0, (0.08 - t) / 0.08) ** 2))
        j = min(NS - 1, max(0, int(round((s - lo) / L * (NS - 1)))))
        w = (half_w[j] + 0.009) * endf + 0.003
        outline.append((Vector((cx, cy, 0)) + ax * s + lat * w, Vector((cx, cy, 0)) + ax * s - lat * w))
    loop2d = [a for a, _ in outline] + [b for _, b in reversed(outline)]
    top_ring = [bm.verts.new((p.x, p.y, zmin + 0.004)) for p in loop2d]
    bot_ring = [bm.verts.new((p.x, p.y, zmin - SOLE_T)) for p in loop2d]
    n = len(loop2d)
    for k in range(n):
        f = bm.faces.new((top_ring[k], top_ring[(k + 1) % n], bot_ring[(k + 1) % n], bot_ring[k]))
        f.material_index = SOLE
    for ring_ in (top_ring, list(reversed(bot_ring))):
        f = bm.faces.new(ring_)
        f.material_index = SOLE
    # The lace round the opening's rim and a bow over the instep, and the moc-toe seam (a raised line round the vamp).
    rim = [e for e in bm.edges if e.is_boundary and e.link_faces and e.link_faces[0].material_index == UPPER]
    for e in rim:
        a_, b_ = e.verts[0].co, e.verts[1].co
        mid = (a_ + b_) / 2
        out = (mid - Vector((cx, cy, mid.z))).normalized() * 0.002 + Vector((0, 0, -0.004))
        q = [bm.verts.new(a_ + out), bm.verts.new(b_ + out), bm.verts.new(b_ + out + Vector((0, 0, -0.003))), bm.verts.new(a_ + out + Vector((0, 0, -0.003)))]
        f = bm.faces.new(q)
        f.material_index = LACE
    inst = rows[int(0.48 * (NS - 1))][NR // 4]
    for side in (-1, 1):
        lobe = [inst + lat * (side * 0.012 * (1 + math.cos(a)) / 2) + ax * (0.008 * math.sin(a)) + Vector((0, 0, 0.004)) for a in [2 * math.pi * j / 10 for j in range(10)]]
        f = bm.faces.new([bm.verts.new(p) for p in lobe])
        f.material_index = LACE
    for i in range(int(0.55 * (NS - 1)), NS - 1):
        for k in range(NR):
            a = 2 * math.pi * k / NR
            if abs(math.sin(a) - 0.35) < 0.07:
                p = rows[i][k]
                nrm = (p - Vector((cx, cy, zmin))).normalized()
                q = [p + nrm * 0.0015, rows[i + 1][k] + nrm * 0.0015, rows[i + 1][k] + nrm * 0.0015 + Vector((0, 0, 0.0025)), p + nrm * 0.0015 + Vector((0, 0, 0.0025))]
                f = bm.faces.new([bm.verts.new(x) for x in q])
                f.material_index = UPPER
    print(f"foot {foot:+d}: length {L * 100:.1f} cm, width {2 * max(half_w) * 100:.1f} cm")

for f in bm.faces:
    for loop in f.loops:
        c = loop.vert.co
        loop[uv].uv = (math.atan2(c.y, c.x) * 0.1 + c.x, c.z + c.y)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
tris = sum(len(f.verts) - 2 for f in bm.faces)
bm.transform(M.inverted())
me = bpy.data.meshes.new("Shoes")
bm.to_mesh(me)
bm.free()
for name in ("Upper", "Sole", "Lace"):
    me.materials.append(bpy.data.materials.new(name))
for p in me.polygons:
    p.use_smooth = True
shoes = bpy.data.objects.new("Shoes", me)
shoes.matrix_world = M
bpy.context.scene.collection.objects.link(shoes)
bpy.ops.object.select_all(action="DESELECT")
shoes.select_set(True)
bpy.context.view_layer.objects.active = shoes
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, mesh_smooth_type="FACE")
print(f"Shoes: {tris} tris -> {OUT}")
