"""Visual V7: what the MetaHuman crew wear over the default shirt and shorts, in unit size; the game scales each piece to
the character's own skeleton (shoulder span, torso height, head size) and hangs it on the chest and head bones.

  SM_CrewPFD  a foam life jacket: a vest open at the neck and arms, X forward, Y right, Z up, from the waist (z 0) to the
              shoulders (z 1); width 1 at the chest (y -0.5..0.5), depth 0.62; quilted shell, zip, straps, buckles and
              reflective patches (Graphics G3; slots PFD, Straps, Buckle, Reflective)
  SM_CrewCap  a six-panel cap on a head of radius 1, the crown's centre at the origin, the peak forward (Graphics G3:
              seams, button, eyelets, a brim with thickness and stitching, the back strap; slots Cap, CapUnder, Buckle)

    blender -b --factory-startup -P Tools/blender/build_crew_gear.py -- <out dir>
Prints "Gear: <name> <tris>".
"""
import math
import os
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index("--") + 1]


def export(name, bm, slots):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            c = loop.vert.co
            loop[uv].uv = (math.atan2(c.y, c.x) * math.hypot(c.x, c.y), c.z)  # arc length: the cloth's weave stays square
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.to_mesh(me)
    bm.free()
    for s in slots:
        me.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                             mesh_smooth_type="FACE")
    bpy.data.objects.remove(obj)
    print(f"Gear: {name} {tris}")


def ring(bm, z, half_w, half_d, n=28, power=2.6, gap=None):
    """A superellipse ring at height z (Blender's Y is Unreal's -Y; the vest is symmetric, so it doesn't matter)."""
    vs = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        x = half_d * math.copysign(abs(c) ** (2 / power), c)
        y = half_w * math.copysign(abs(s) ** (2 / power), s)
        vs.append(bm.verts.new((x, y, z)))
    return vs


def loft(bm, rings, slot_index, closed=True):
    for a, b in zip(rings, rings[1:]):
        n = len(a)
        for k in range(n if closed else n - 1):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            f.material_index = slot_index


PROF = [(0.0, 0.47, 0.30), (0.25, 0.49, 0.31), (0.55, 0.5, 0.31), (0.8, 0.46, 0.27), (0.92, 0.36, 0.2), (1.0, 0.22, 0.13)]


def shell_size(z):
    """Half width and half depth of the jacket's outer shell at height z (smoothstep between the profile rows)."""
    for (z0, w0, d0), (z1, w1, d1) in zip(PROF, PROF[1:]):
        if z <= z1:
            t = (z - z0) / (z1 - z0)
            t = t * t * (3 - 2 * t)
            return w0 + (w1 - w0) * t, d0 + (d1 - d0) * t
    return PROF[-1][1], PROF[-1][2]


def quilt(a, z):
    """Graphics G3: how far the stitched seams pull the outer fabric in (foam panels between them): vertical channels on
    the front (x > 0), horizontal ones on the back, a groove each side of the zip."""
    c, s = math.cos(a), math.sin(a)
    _, d = shell_size(z)
    y = s * 0.5
    g = lambda u, w: math.exp(-(u / w) ** 2)
    front = max(0.0, c) ** 0.5
    seams = sum(g(abs(y) - y0, 0.010) for y0 in (0.035, 0.17, 0.30)) * front
    back = max(0.0, -c) ** 0.5
    seams += sum(g(z - z0, 0.012) for z0 in (0.28, 0.52, 0.74)) * back
    seams += g(z - 0.04, 0.02) + g(z - 0.97, 0.02)          # the hem and the neck binding
    return 0.011 * min(seams, 1.0)


def surf(a, z, off=0.0):
    """A point on the outer shell (superellipse section), pushed out by `off` along the section's normal."""
    w, d = shell_size(z)
    c, s = math.cos(a), math.sin(a)
    power = 2.6
    x = d * math.copysign(abs(c) ** (2 / power), c)
    y = w * math.copysign(abs(s) ** (2 / power), s)
    r = math.hypot(x, y) or 1.0
    k = (off - quilt(a, z)) / r
    return (x * (1 + k), y * (1 + k), z)


def grid(bm, a0, a1, z0, z1, na, nz, off, slot, closed=False):
    rows = []
    for j in range(nz + 1):
        z = z0 + (z1 - z0) * j / nz
        n = na if closed else na + 1
        rows.append([bm.verts.new(surf(a0 + (a1 - a0) * k / na, z, off)) for k in range(n)])
    for a, b in zip(rows, rows[1:]):
        n = len(a)
        for k in range(n if closed else n - 1):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            f.material_index = slot
    return rows


def box(bm, centre, half, slot):
    cx, cy, cz = centre
    hx, hy, hz = half
    v = [bm.verts.new((cx + sx * hx, cy + sy * hy, cz + sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        f = bm.faces.new([v[i] for i in q])
        f.material_index = slot


def pfd():
    """Graphics G3: a foam vest as worn dinghy and keelboat sailors wear them (after Stohlquist / Onyx style vests): quilted
    nylon shell over foam panels (stitched channels), webbing hem and neck binding, a front zip with its pull, two
    waist straps with side-release buckles, reflective patches on the shoulders. Slots: PFD (shell, recoloured per sailor),
    Straps (webbing), Buckle (black plastic, zip), Reflective."""
    bm = bmesh.new()
    PFD, STRAPS, BUCKLE, REFL = 0, 1, 2, 3
    na, nz = 112, 48
    outer = grid(bm, 0.0, 2 * math.pi, 0.0, 1.0, na, nz, 0.0, PFD, closed=True)
    # The inside (foam 2.5 cm and lining), a plain smaller shell, and the hem and neck faces between them.
    inner = []
    for j in range(nz + 1):
        z = j / nz
        w, d = shell_size(z)
        inner.append(ring(bm, z, w - 0.065, d - 0.065, n=na))
    loft(bm, list(reversed(inner)), PFD)
    for a, b in ((outer[0], inner[0]), (inner[-1], outer[-1])):
        n = len(a)
        for k in range(n):
            f = bm.faces.new((a[k], b[k], b[(k + 1) % n], a[(k + 1) % n]))
            f.material_index = STRAPS
    # Webbing binding at the hem and the neck, proud of the shell.
    grid(bm, 0.0, 2 * math.pi, 0.0, 0.035, na, 2, 0.004, STRAPS, closed=True)
    grid(bm, 0.0, 2 * math.pi, 0.965, 1.0, na, 2, 0.004, STRAPS, closed=True)
    # Two waist straps (38 mm webbing in a 0.38 m jacket: 0.1 of the unit width) with a side-release buckle at the front.
    for z in (0.18, 0.40):
        grid(bm, 0.0, 2 * math.pi, z - 0.045, z + 0.045, na, 2, 0.007, STRAPS, closed=True)
        x, _, _ = surf(0.0, z, 0.016)
        box(bm, (x, 0.055, z), (0.010, 0.05, 0.055), BUCKLE)       # female
        box(bm, (x + 0.004, -0.03, z), (0.007, 0.04, 0.045), BUCKLE)  # male, tongue in
    # The zip: a tape either side of the front centre, the teeth between, the pull near the top.
    za = 0.05
    grid(bm, -za, za, 0.035, 0.965, 4, 40, 0.004, BUCKLE)
    x, _, _ = surf(0.0, 0.9, 0.012)
    box(bm, (x, 0.0, 0.88), (0.006, 0.012, 0.04), BUCKLE)
    # Reflective patches high on the front of each shoulder.
    for sgn in (1, -1):
        a0, a1 = sorted((sgn * 0.55, sgn * 0.95))
        grid(bm, a0, a1, 0.80, 0.90, 8, 4, 0.003, REFL)
    export("SM_CrewPFD", bm, ["PFD", "Straps", "Buckle", "Reflective"])


def cap():
    """Graphics G3: a six-panel cotton cap: stitched panel seams, a button on top, an eyelet on each panel, a curved brim
    with thickness and rows of stitching, the back opening and its strap. Slots: Cap (recoloured per sailor), CapUnder
    (the brim's grey-green underside and the sweatband), Buckle (the strap's clasp)."""
    bm = bmesh.new()
    CAP, UNDER, BUCKLE = 0, 1, 2
    n, m = 96, 24

    def crown(a, el, off=0.0):
        # Six panels: the seams sit between them, pulled in a little; the back opening (a > 150 deg) is cut below.
        seam = min(abs(((a / (math.pi / 3)) % 1.0) - 0.5) for _ in (0,))
        pull = 0.012 * math.exp(-((0.5 - seam) / 0.03) ** 2) * math.cos(el)
        r = (1.06 + off - pull) * math.cos(el)
        z = (1.06 + off - pull) * math.sin(el) * 0.92 - 0.05
        return (r * math.cos(a), r * math.sin(a), z)

    rings = []
    for j in range(m):
        t = j / (m - 1)
        el = math.radians(-8 + 88 * t)
        rings.append([bm.verts.new(crown(2 * math.pi * k / n, el)) for k in range(n)])
    for j, (a, b) in enumerate(zip(rings, rings[1:])):
        for k in range(n):
            ang = 2 * math.pi * (k + 0.5) / n
            # The back opening: the lowest rows behind the head, above the strap.
            if j < 4 and abs(math.atan2(math.sin(ang), math.cos(ang))) > math.radians(160):
                continue
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            f.material_index = CAP
    top = bm.faces.new(rings[-1])
    top.material_index = CAP
    # The inside of the crown (seen under the brim) and the sweatband.
    inside = [[bm.verts.new(crown(2 * math.pi * k / n, math.radians(-8 + 30 * j / 3), -0.02)) for k in range(n)] for j in range(4)]
    for a, b in zip(inside, inside[1:]):
        for k in range(n):
            f = bm.faces.new((a[(k + 1) % n], a[k], b[k], b[(k + 1) % n]))
            f.material_index = UNDER
    # The button on top and an eyelet on each panel.
    box(bm, (0.0, 0.0, 1.06 * 0.92 - 0.04), (0.06, 0.06, 0.025), CAP)
    for p in range(6):
        a = (p + 0.5) * math.pi / 3
        x, y, z = crown(a, math.radians(58), 0.004)
        box(bm, (x, y, z), (0.02, 0.02, 0.02), UNDER)
    # The brim: curved across and down, rounded at the front, with thickness; top in the cap's colour, underside grey-green.
    nb, rb = 33, 7
    top_rows, bot_rows = [], []
    for j in range(rb):
        t = j / (rb - 1)
        row_t, row_b = [], []
        for k in range(nb):
            u = -1 + 2 * k / (nb - 1)
            a = math.radians(70) * u
            reach = 0.42 * math.sqrt(max(0.0, 1 - u * u * 0.85))
            r = 1.04 + reach * t
            z = -0.17 - 0.10 * t * t - 0.10 * u * u * t
            row_t.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z + 0.012)))
            row_b.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z - 0.012)))
        top_rows.append(row_t)
        bot_rows.append(row_b)
    for rows, slot, flip in ((top_rows, CAP, False), (bot_rows, UNDER, True)):
        for a, b in zip(rows, rows[1:]):
            for k in range(nb - 1):
                q = (a[k], a[k + 1], b[k + 1], b[k])
                f = bm.faces.new(tuple(reversed(q)) if flip else q)
                f.material_index = slot
    for k in range(nb - 1):   # the brim's edge
        f = bm.faces.new((top_rows[-1][k], bot_rows[-1][k], bot_rows[-1][k + 1], top_rows[-1][k + 1]))
        f.material_index = CAP
    # Stitch rows on the brim: thin raised arcs.
    for t in (0.25, 0.45, 0.65, 0.85):
        j = t * (rb - 1)
        for k in range(nb - 1):
            u = -1 + 2 * (k + 0.5) / (nb - 1)
            a = math.radians(70) * u
            reach = 0.42 * math.sqrt(max(0.0, 1 - u * u * 0.85))
            r = 1.04 + reach * t
            z = -0.17 - 0.10 * t * t - 0.10 * u * u * t + 0.0135
            box(bm, (r * math.cos(a), r * math.sin(a), z), (0.006, 0.02, 0.0015), UNDER)
    # The back strap and its clasp across the opening.
    for k in range(-6, 7):
        a = math.pi + math.radians(4) * k
        x, y, z = crown(a, math.radians(-4), 0.006)
        box(bm, (x, y, z), (0.01, 0.04, 0.045), CAP)
    x, y, z = crown(math.pi, math.radians(-4), 0.02)
    box(bm, (x, y, z), (0.012, 0.07, 0.05), BUCKLE)
    export("SM_CrewCap", bm, ["Cap", "CapUnder", "Buckle"])


bpy.ops.wm.read_factory_settings(use_empty=True)
pfd()
cap()
