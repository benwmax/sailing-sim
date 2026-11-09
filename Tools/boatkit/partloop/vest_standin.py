"""Part detail loop, crew life vest: a stand-in sailor in a polo, for building and rendering the vest away from the crew pack.

The game's vest (Tools/blender/build_vest.py) is tailored over each MetaHuman sailor's polo, and those bodies live only in
the private crew pack. This makes a plain, faceless mannequin of an adult in a polo (chest about 100 cm round, 1.78 m
tall, standing in an A pose, facing -Y like the polos) so the vest can be built and judged in the cloud. Every size here
is the stand-in's, not a MetaHuman's: the PC re-runs build_vest.py on the real polos.

One mesh, two slots: Polo (the shirt, with short sleeves: what build_vest.py keeps) and Skin (head, neck, arms, legs).

    python3 Tools/boatkit/partloop/vest_standin.py <out.fbx>          (bpy module)
    blender -b --factory-startup -P Tools/boatkit/partloop/vest_standin.py -- <out.fbx>
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv[1]
N = 64   # around

# The shirt's cross-sections, hem to collar: (z, half width, half depth, centre y). Superellipse rings (exponent 2.6: a
# torso is boxier than an ellipse). The shoulders flare out past the chest above the armpit, then slope in to the collar.
TORSO = [(0.90, 0.168, 0.118, 0.000), (0.98, 0.158, 0.112, 0.000), (1.08, 0.160, 0.114, -0.004), (1.18, 0.170, 0.122, -0.010),
         (1.28, 0.180, 0.122, -0.010), (1.35, 0.198, 0.110, -0.004), (1.40, 0.192, 0.096, 0.000), (1.43, 0.150, 0.078, 0.004),
         (1.46, 0.092, 0.066, 0.006), (1.48, 0.068, 0.060, 0.008)]
EXP = 2.6


def lerp_sections(z):
    for a, b in zip(TORSO, TORSO[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            t = t * t * (3 - 2 * t)
            return [a[k] + (b[k] - a[k]) * t for k in range(4)]
    return list(TORSO[-1])


def ring_pt(a, b, cy, z, th):
    c, s = math.cos(th), math.sin(th)
    x = a * math.copysign(abs(c) ** (2 / EXP), c)
    y = b * math.copysign(abs(s) ** (2 / EXP), s)
    return Vector((x, cy + y, z))


bm = bmesh.new()


def loft(rings, mat, cap_start=False, cap_end=False):
    vs = [[bm.verts.new(p) for p in r] for r in rings]
    for r0, r1 in zip(vs, vs[1:]):
        n = len(r0)
        for i in range(n):
            bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i])).material_index = mat
    if cap_start:
        bm.faces.new(list(reversed(vs[0]))).material_index = mat
    if cap_end:
        bm.faces.new(vs[-1]).material_index = mat


POLO, SKIN = 0, 1
zs = [0.90 + i * 0.01 for i in range(59)]
rings = []
for z in zs:
    a, b, cy = lerp_sections(z)[1:]
    rings.append([ring_pt(a, b, cy, z, 2 * math.pi * i / N) for i in range(N)])
loft(rings, POLO)
# The polo's collar: a band standing 3.5 cm up the neck (build_vest.py puts the vest's neck at its seam, zmax - 3.5 cm).
a, b, cy = lerp_sections(1.48)[1:]
loft([[ring_pt(a * k, b * k, cy, z, 2 * math.pi * i / N) for i in range(N)] for z, k in ((1.48, 1.0), (1.50, 0.98), (1.515, 0.97))], POLO)


def tube(p0, p1, r0, r1, mat, n=24, steps=10, caps=(True, True)):
    d = (p1 - p0)
    ax = d.normalized()
    up = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    u = ax.cross(up).normalized()
    v = ax.cross(u).normalized()
    rs = []
    for k in range(steps + 1):
        t = k / steps
        c = p0 + d * t
        r = r0 + (r1 - r0) * t
        rs.append([c + (u * math.cos(2 * math.pi * i / n) + v * math.sin(2 * math.pi * i / n)) * r for i in range(n)])
    loft(rs, mat, *caps)


# Short sleeves (Polo), then the arms (Skin) in an A pose, 40 degrees down from level.
for s in (-1, 1):
    sh = Vector((s * 0.185, 0.0, 1.375))
    dirn = Vector((s * math.cos(math.radians(50)), 0.0, -math.sin(math.radians(50))))
    tube(sh - dirn * 0.03, sh + dirn * 0.20, 0.068, 0.058, POLO)
    elbow = sh + dirn * 0.30
    tube(sh + dirn * 0.17, elbow, 0.046, 0.040, SKIN)
    wrist = elbow + Vector((s * 0.06, -0.06, -0.24))
    tube(elbow, wrist, 0.040, 0.030, SKIN)
    # Legs in shorts-length skin: hip to knee to ankle (plain, they only frame the vest).
    hip = Vector((s * 0.09, 0.0, 0.92))
    knee = Vector((s * 0.10, -0.01, 0.50))
    tube(hip, knee, 0.085, 0.055, SKIN)
    tube(knee, Vector((s * 0.10, 0.01, 0.08)), 0.052, 0.036, SKIN)
# Hips under the shirt's hem (closes the body), the neck and a plain head (no face).
tube(Vector((0, 0, 0.84)), Vector((0, 0, 0.93)), 0.15, 0.16, SKIN)
tube(Vector((0, 0.008, 1.44)), Vector((0, 0.012, 1.56)), 0.056, 0.054, SKIN)
hd = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.1)
for v in hd["verts"]:
    v.co = Vector((v.co.x * 0.82, v.co.y * 0.95 + 0.0, v.co.z * 1.05 + 1.65))
for f in {f for v in hd["verts"] for f in v.link_faces}:
    f.material_index = SKIN
bm.normal_update()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

bpy.ops.wm.read_factory_settings(use_empty=True)
me = bpy.data.meshes.new("Standin")
bm.to_mesh(me)
bm.free()
for name in ("Polo", "Skin"):
    me.materials.append(bpy.data.materials.new(name))
for p in me.polygons:
    p.use_smooth = True
ob = bpy.data.objects.new("Standin", me)
bpy.context.scene.collection.objects.link(ob)
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, mesh_smooth_type="FACE")
print(f"Stand-in: {len(me.polygons)} faces -> {OUT}")
