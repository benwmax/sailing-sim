"""Club docks (slice #405 part 2, pass 2; dock hardware detail pass Nov 9 2026): the floating docks' hardware at real
size, built in Blender from code (run headless by scripts/make-world-models.sh). AMarinaActor places them as static
instances at the points its generator computes (AMarinaActor::DockKitPlacements); without them it draws the kit's boxes.

Each mesh: X along its finger or out from the dock's edge, Z up, the origin on the deck (or on the piling's axis at deck
height for the hoop, on its top for the cap, on the finger's tip at deck level for the bumper). Slots name MI_World_*
looks (import_world.py's WORLD_SLOTS): White (weathered moulded plastic), Steel, Dark (black rubber and plastic), Trim
(grey moulded plastic), Glass, Floats (the float drums' polyethylene), LampGlow, SafetyRed. UVs are box-projected in
metres. Prints "Docks: <name> <tris>".

The detail pass (docs/dock-hardware) follows the part detail loop: sizes from catalogues, features from free photos,
scored before/after by Tools/blender/dockloop. Origins, facing and footprints are the same as pass 2's, so the
placements and the bake are unchanged.
Usage: blender -b --factory-startup -P build_docks.py -- <out dir>
"""
import math
import os
import sys

import bpy  # noqa: I001 (first: the bpy module brings bmesh and mathutils)
import bmesh
from mathutils import Matrix, Vector


def _frame(d, up=None):
    """Two unit vectors across the direction d: u sideways, w 'up' (toward `up`, default world Z)."""
    up = Vector(up) if up is not None else (Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0)))
    u = d.cross(up)
    if u.length < 1e-6:
        u = d.cross(Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0)))
    u.normalize()
    w = u.cross(d).normalized()
    return u, w


class Part:
    """Primitives into one mesh with a material slot per look."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.slots = []

    def slot(self, name):
        if name not in self.slots:
            self.slots.append(name)
        return self.slots.index(name)

    def _faces(self, faces, slot):
        m = self.slot(slot)
        for f in faces:
            f.material_index = m

    def box(self, slot, c, half, bevel=0.0, yaw=0.0, segments=2, pitch=0.0, roll=0.0):
        """A box centred at c with half extents, its edges rounded by `bevel` metres, turned by roll (X), pitch (Y)
        then yaw (Z), in degrees."""
        geom = bmesh.ops.create_cube(self.bm, size=1.0)
        verts = geom["verts"]
        bmesh.ops.scale(self.bm, vec=Vector(half) * 2.0, verts=verts)
        if bevel > 0.0:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bevel, segments=segments, affect="EDGES", profile=0.5)
            verts = list({v for f in res["faces"] for v in f.verts} | set(v for v in verts if v.is_valid))
        verts = [v for v in verts if v.is_valid]
        rot = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(pitch), 4, "Y") @ Matrix.Rotation(math.radians(roll), 4, "X")
        bmesh.ops.transform(self.bm, matrix=rot, verts=verts)
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=verts)
        self._faces({f for v in verts for f in v.link_faces}, slot)

    def tube(self, slot, a, b, r0, r1=None, sides=12, caps=True):
        """A round bar from a to b, radius r0 at a and r1 at b."""
        r1 = r0 if r1 is None else r1
        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        u, w = _frame(axis)
        rings = []
        for p, r in ((a, r0), (b, r1)):
            rings.append([self.bm.verts.new(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * r)
                          for k in range(sides)])
        faces = [self.bm.faces.new((rings[0][k], rings[0][(k + 1) % sides], rings[1][(k + 1) % sides], rings[1][k])) for k in range(sides)]
        if caps:
            faces.append(self.bm.faces.new(list(reversed(rings[0]))))
            faces.append(self.bm.faces.new(rings[1]))
        self._faces(faces, slot)

    def path(self, slot, pts, r, sides=10):
        """A bar along a polyline (bent rails, hoops), each joint a shared ring."""
        self.sweep(slot, pts, [(r, r)] * len(pts), sides=sides)

    def sweep(self, slot, pts, sec, sides=12, caps=("flat", "flat"), up=None, closed=False):
        """A bar along a polyline with an elliptical section per point: sec[i] = (half width, half height), the height
        toward `up` (default world Z). caps: "flat", "round" (a dome as deep as the smaller radius) or None."""
        pts = [Vector(p) for p in pts]
        n = len(pts)
        rings, frames = [], []
        for i, p in enumerate(pts):
            if closed:
                d = (pts[(i + 1) % n] - pts[(i - 1) % n]).normalized()
            else:
                d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            u, w = _frame(d, up)
            rw, rh = sec[i]
            frames.append((d, u, w))
            rings.append([self.bm.verts.new(p + u * (rw * math.cos(2 * math.pi * k / sides)) + w * (rh * math.sin(2 * math.pi * k / sides)))
                          for k in range(sides)])
        faces = []
        pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
        for ra, rb in pairs:
            faces += [self.bm.faces.new((ra[k], ra[(k + 1) % sides], rb[(k + 1) % sides], rb[k])) for k in range(sides)]
        if not closed:
            for end, (ring, p, (d, u, w), (rw, rh)) in enumerate(((rings[0], pts[0], frames[0], sec[0]), (rings[-1], pts[-1], frames[-1], sec[-1]))):
                kind = caps[end]
                if kind is None:
                    continue
                out = -d if end == 0 else d
                if kind == "round":
                    depth = min(rw, rh)
                    prev = ring
                    for j in (1, 2, 3):
                        a = j / 4 * math.pi / 2 if j < 3 else math.radians(72)
                        s = math.cos(a)
                        nr = [self.bm.verts.new(p + out * (depth * math.sin(a)) + u * (rw * s * math.cos(2 * math.pi * k / sides)) + w * (rh * s * math.sin(2 * math.pi * k / sides)))
                              for k in range(sides)]
                        faces += [self._quad(prev[k], prev[(k + 1) % sides], nr[(k + 1) % sides], nr[k], end) for k in range(sides)]
                        prev = nr
                    tip = self.bm.verts.new(p + out * depth)
                    faces += [self._tri(prev[k], prev[(k + 1) % sides], tip, end) for k in range(sides)]
                else:
                    faces.append(self.bm.faces.new(list(reversed(ring)) if end == 0 else ring))
        self._faces(faces, slot)

    def _quad(self, a, b, c, d, end):
        return self.bm.faces.new((a, b, c, d) if end == 1 else (d, c, b, a))

    def _tri(self, a, b, c, end):
        return self.bm.faces.new((a, b, c) if end == 1 else (c, b, a))

    def loft(self, slot, stations, n=3.0, sides=24, hole=None):
        """A cast body lofted along X: stations [(x, z bottom, z top, half width)] give a rounded-rectangle section
        (superellipse exponent n: 2 an ellipse, higher squarer); flat end caps. hole ((x, z), r) cuts a round hole
        through along Y (an exact boolean)."""
        bm = bmesh.new()
        rings = []
        for x, zb, zt, hw in stations:
            zc, hh = 0.5 * (zb + zt), 0.5 * (zt - zb)
            ring = []
            for k in range(sides):
                t = 2 * math.pi * k / sides
                c, sn = math.cos(t), math.sin(t)
                y = hw * math.copysign(abs(c) ** (2.0 / n), c)
                z = zc + hh * math.copysign(abs(sn) ** (2.0 / n), sn)
                ring.append(bm.verts.new((x, y, z)))
            rings.append(ring)
        for ra, rb in zip(rings, rings[1:]):
            for k in range(sides):
                bm.faces.new((ra[k], ra[(k + 1) % sides], rb[(k + 1) % sides], rb[k]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if not hole:
            n0 = len(self.bm.faces)
            me = bpy.data.meshes.new("loft")
            bm.to_mesh(me)
            bm.free()
            self._append(me, slot)
            return
        me = bpy.data.meshes.new("loft")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("loft", me)
        bpy.context.scene.collection.objects.link(ob)
        (hx, hz), hr = hole
        cb = bmesh.new()
        bmesh.ops.create_cone(cb, cap_ends=True, segments=20, radius1=hr, radius2=hr, depth=1.0)
        bmesh.ops.rotate(cb, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"), verts=cb.verts[:])
        bmesh.ops.translate(cb, vec=Vector((hx, 0, hz)), verts=cb.verts[:])
        cme = bpy.data.meshes.new("cut")
        cb.to_mesh(cme)
        cb.free()
        cut = bpy.data.objects.new("cut", cme)
        bpy.context.scene.collection.objects.link(cut)
        m = ob.modifiers.new("Hole", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "EXACT"
        m.object = cut
        dg = bpy.context.evaluated_depsgraph_get()
        res = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(cut, do_unlink=True)
        bpy.data.objects.remove(ob, do_unlink=True)
        self._append(res, slot)

    def _append(self, mesh, slot):
        n0 = len(self.bm.faces)
        self.bm.from_mesh(mesh)
        self.bm.faces.ensure_lookup_table()
        self._faces(self.bm.faces[n0:], slot)
        bpy.data.meshes.remove(mesh)

    def lathe(self, slot, c, profile, sides=16, axis="Z"):
        """A turned part about an axis through c (Z, or X/Y for parts on a side face): profile [(radius, h)] from the
        base up."""
        c = Vector(c)

        def at(r, h, k):
            a = 2 * math.pi * k / sides
            x, y = r * math.cos(a), r * math.sin(a)
            if axis == "Z":
                return c + Vector((x, y, h))
            if axis == "X":
                return c + Vector((h, x, y))
            if axis == "-X":
                return c + Vector((-h, y, x))
            if axis == "Y":
                return c + Vector((y, h, x))
            return c + Vector((x, -h, y))   # -Y
        rings = []
        for r, h in profile:
            if r <= 1e-6:
                rings.append([self.bm.verts.new(at(0.0, h, 0))])
            else:
                rings.append([self.bm.verts.new(at(r, h, k)) for k in range(sides)])
        faces = []
        for ra, rb in zip(rings, rings[1:]):
            for k in range(sides):
                q = [ra[k % len(ra)], ra[(k + 1) % len(ra)], rb[(k + 1) % len(rb)], rb[k % len(rb)]]
                uniq = []
                for v in q:
                    if v not in uniq:
                        uniq.append(v)
                if len(uniq) >= 3:
                    faces.append(self.bm.faces.new(uniq))
        self._faces(faces, slot)

    def bolt(self, slot, c, d=0.016, h=0.007, axis="Z", washer=True):
        """A hex bolt head (across flats d) on a round washer, standing off a face along axis (Z, X, -X, Y, -Y)."""
        prof = [(0.65 * d, 0.0), (0.65 * d, 0.0015), (0.0, 0.0015)] if washer else []
        if prof:
            self.lathe(slot, c, prof, sides=12, axis=axis)
        r = d / math.sqrt(3)
        base = 0.0015 if washer else 0.0
        self.lathe(slot, c, [(r, base), (r, base + h * 0.8), (r * 0.85, base + h), (0.0, base + h)], sides=6, axis=axis)

    def export(self, out):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        for f in self.bm.faces:                                   # box-projected UVs in metres
            n = f.normal
            for loop in f.loops:
                co = loop.vert.co
                loop[self.uv].uv = (co.y, co.z) if abs(n.x) >= max(abs(n.y), abs(n.z)) else ((co.x, co.z) if abs(n.y) >= abs(n.z) else (co.x, co.y))
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        tris = sum(len(f.verts) - 2 for f in self.bm.faces)
        self.bm.free()
        for s in self.slots:
            mesh.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        except Exception:
            pass
        bpy.ops.export_scene.fbx(filepath=os.path.join(out, self.name + ".fbx"), use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                                 mesh_smooth_type="FACE")
        bpy.data.objects.remove(obj)
        print(f"Docks: {self.name} {tris}")


def cleat():
    """A 10 in (254 mm) cast dock cleat, 75 mm high, the kind on lake club docks: a closed base flaring onto the deck
    (117 mm long), its web pierced by a round hole for the line, the horns rounded in section and tapering out to
    blunt tips that lift a little; two bolt heads countersunk in the top. Its side outline was measured on the
    square-on reference photo (docs/dock-hardware): a lofted body (the web and horns) and the base's flare."""
    p = Part("SM_Dock_Cleat")
    top = [(0.0, 0.067), (0.035, 0.0675), (0.065, 0.069), (0.095, 0.0725), (0.112, 0.0748), (0.12, 0.0748), (0.127, 0.073)]
    under = [(0.0365, 0.0), (0.0385, 0.012), (0.0402, 0.024), (0.0408, 0.034), (0.043, 0.04), (0.05, 0.045), (0.064, 0.049), (0.088, 0.0525), (0.108, 0.0555), (0.12, 0.0582), (0.127, 0.0615)]

    def lerp(tab, x):
        x = abs(x)
        for (x0, z0), (x1, z1) in zip(tab, tab[1:]):
            if x <= x1:
                return z0 + (z1 - z0) * (x - x0) / max(x1 - x0, 1e-9)
        return tab[-1][1]

    def hw(x):
        return 0.015 - 0.0045 * max(0.0, (abs(x) - 0.04) / 0.087)

    xs = [0.0, 0.01, 0.02, 0.03, 0.0365, 0.0385, 0.0402, 0.0408, 0.0415, 0.043, 0.046, 0.05, 0.056, 0.064, 0.074, 0.084, 0.094, 0.104, 0.112, 0.118, 0.122, 0.1245, 0.1262]
    xs = [-x for x in reversed(xs[1:])] + xs
    st = []
    for x in xs:
        zb = 0.0 if abs(x) <= 0.0365 else lerp(under, x)
        zt = lerp(top, x)
        w = hw(x)
        if abs(x) > 0.118:            # the blunt tip rounds over
            k = (abs(x) - 0.118) / (0.1262 - 0.118)
            sh = math.sqrt(max(0.0, 1.0 - 0.75 * k * k))
            zc, hh = 0.5 * (zb + zt), 0.5 * (zt - zb) * sh
            zb, zt, w = zc - hh, zc + hh, w * sh
        st.append((x, zb, zt, w))
    p.loft("Steel", st, n=2.6, sides=24, hole=((0.0, 0.032), 0.0125))
    # the base's flare onto the deck, wider than the web, in a separate loft under it
    lower = [(0.0, 0.012), (0.04, 0.012), (0.0405, 0.03), (0.041, 0.025), (0.045, 0.016), (0.052, 0.008), (0.0585, 0.003)]
    bx = [0.0, 0.02, 0.0395, 0.0415, 0.045, 0.049, 0.052, 0.055, 0.0575, 0.0585]
    bx = [-x for x in reversed(bx[1:])] + bx
    base = []
    for x in bx:
        zt = lerp(lower[:2], x) if abs(x) <= 0.04 else lerp(lower[2:], x)
        base.append((x, -0.004, zt, 0.0155 + 0.004 * min(1.0, max(0.0, (abs(x) - 0.03) / 0.025)) - 0.002 * max(0.0, (abs(x) - 0.054) / 0.0045)))
    p.loft("Steel", base, n=2.3, sides=24)        # rounded on top, so the flare reads as the casting's fillet
    for x in (-0.029, 0.029):                                                     # bolts sunk in pockets in the top
        z = lerp(top, x)
        p.lathe("Dark", (x, 0, z - 0.0035), [(0.0, 0.0), (0.0078, 0.0), (0.0084, 0.0034), (0.0, 0.0034)], sides=12)
        p.lathe("Steel", (x, 0, z - 0.0026), [(0.0062, 0.0), (0.0058, 0.0012), (0.0, 0.0016)], sides=10)
        p.box("Dark", (x, 0, z - 0.0009), (0.0048, 0.0008, 0.0004))
    p.export(OUT)


def pedestal():
    """A shore power pedestal (1.12 m): a moulded white post with chamfered corners on a dark base plate, toward the slip
    (+X) a kWh meter behind its window in a bezel, a breaker door with screws, and two grey receptacle housings with
    hinged weather lids; a hose bib with its round handle on the side (-Y); the lamp head: a louvred lens under a
    domed cap."""
    p = Part("SM_Dock_Pedestal")
    p.box("Dark", (0, 0, 0.012), (0.165, 0.165, 0.012), bevel=0.006)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.bolt("Steel", (sx * 0.14, sy * 0.14, 0.024), d=0.014, h=0.006)
    p.box("White", (0, 0, 0.05), (0.13, 0.13, 0.03), bevel=0.012)                 # plinth
    p.box("White", (0, 0, 0.5), (0.12, 0.12, 0.44), bevel=0.028, segments=3)     # the post
    for z in (0.93, 0.07):                                                       # seams top and bottom
        p.box("Trim", (0, 0, z), (0.123, 0.123, 0.006), bevel=0.026, segments=3)
    # the meter: bezel, the dial behind glass
    p.lathe("Trim", (0.12, 0, 0.78), [(0.07, 0.0), (0.072, 0.008), (0.066, 0.016), (0.06, 0.016)], sides=20, axis="X")
    p.lathe("White", (0.12, 0, 0.78), [(0.06, 0.008), (0.0, 0.008)], sides=20, axis="X")
    p.lathe("Glass", (0.12, 0, 0.78), [(0.06, 0.016), (0.045, 0.024), (0.0, 0.026)], sides=20, axis="X")
    # the breaker door with four screws and a pull
    p.box("Trim", (0.124, 0, 0.64), (0.006, 0.075, 0.05), bevel=0.004)
    for sy in (-1, 1):
        for sz in (-1, 1):
            p.lathe("Steel", (0.13, sy * 0.064, 0.64 + sz * 0.04), [(0.004, 0.0), (0.0035, 0.002), (0.0, 0.0025)], sides=8, axis="X")
    p.box("Dark", (0.132, 0, 0.605), (0.004, 0.02, 0.006), bevel=0.002)
    # two receptacle housings, each with a hinged lid sloping out over the outlet
    for z in (0.47, 0.32):
        p.box("Trim", (0.135, 0, z), (0.018, 0.06, 0.055), bevel=0.006)
        p.box("Trim", (0.16, 0, z + 0.01), (0.014, 0.062, 0.052), bevel=0.012, segments=3, pitch=-12.0)   # the domed lid
        p.tube("Steel", (0.15, -0.055, z + 0.06), (0.15, 0.055, z + 0.06), 0.005, sides=8)      # its hinge
        p.box("Dark", (0.155, 0, z - 0.05), (0.01, 0.03, 0.008), bevel=0.003)                  # the cord slot
    # the hose bib on the side: a flange, the valve body, the spout down, a round handle
    p.lathe("Steel", (0, -0.12, 0.6), [(0.022, 0.0), (0.022, 0.006), (0.012, 0.008), (0.011, 0.05), (0.0, 0.05)], sides=14, axis="-Y")
    p.tube("Steel", (0, -0.165, 0.6), (0, -0.168, 0.565), 0.011, 0.012, sides=12)
    p.lathe("Steel", (0, -0.168, 0.565), [(0.012, 0.0), (0.0135, -0.004), (0.0135, -0.016), (0.0, -0.016)], sides=12)
    p.tube("Steel", (0, -0.155, 0.61), (0, -0.155, 0.645), 0.004, sides=6)
    p.sweep("Dark", [(0.022 * math.cos(2 * math.pi * k / 16), -0.155 + 0.022 * math.sin(2 * math.pi * k / 16), 0.65) for k in range(16)],
            [(0.004, 0.004)] * 16, sides=6, closed=True)
    for yaw in (0, 90):
        p.box("Dark", (0, -0.155, 0.65), (0.022, 0.003, 0.003), yaw=yaw)
    # the rating label and the cable chase at the back
    p.box("Steel", (0.122, 0, 0.88), (0.002, 0.05, 0.018))
    p.box("Steel", (-0.122, 0, 0.88), (0.002, 0.05, 0.018))                          # slip number plate at the back
    # the lamp head: collar, louvred lens, domed cap
    p.lathe("White", (0, 0, 0.94), [(0.13, 0.0), (0.135, 0.012), (0.115, 0.022)], sides=24)
    p.lathe("LampGlow", (0, 0, 0.955), [(0.105, 0.0), (0.11, 0.035), (0.105, 0.07)], sides=24)
    for z in (0.968, 0.99, 1.012):
        p.lathe("White", (0, 0, z), [(0.106, 0.0), (0.116, 0.002), (0.116, 0.006), (0.106, 0.008)], sides=24)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p.box("White", (0.108 * math.cos(a), 0.108 * math.sin(a), 0.99), (0.008, 0.008, 0.036), yaw=math.degrees(a))
    p.lathe("White", (0, 0, 1.025), [(0.14, 0.0), (0.145, 0.012), (0.138, 0.024), (0.11, 0.05), (0.06, 0.068), (0.0, 0.074)], sides=24)
    p.export(OUT)


def dock_box():
    """A moulded dock box (1.2 x 0.56 x 0.6 m) along the finger: the body with draft and rounded corners on a dark
    skid, vertical ribs and a raised panel on the front (+Y), recessed grab handles in each end, the lid proud of the
    body with a raised, ribbed top, two hinges at the back, a hasp and staple with a padlock at the front."""
    p = Part("SM_Dock_Box")
    for sx in (-1, 1):
        p.box("White", (sx * 0.47, 0, 0.022), (0.07, 0.25, 0.022), bevel=0.01)    # moulded feet
    p.box("White", (0, 0, 0.3), (0.6, 0.28, 0.255), bevel=0.04, segments=3)
    for x in (-0.42, -0.14, 0.14, 0.42):                                            # front ribs
        p.box("White", (x, 0.282, 0.29), (0.018, 0.008, 0.2), bevel=0.006)
    p.box("White", (0, 0.283, 0.29), (0.1, 0.004, 0.16), bevel=0.004)              # the panel under the hasp
    for sx in (-1, 1):                                                              # recessed handles in the ends
        p.box("Trim", (sx * 0.597, 0, 0.42), (0.006, 0.11, 0.03), bevel=0.012)
        for y in (-0.17, 0.17):                                                     # end ribs
            p.box("White", (sx * 0.602, y, 0.29), (0.008, 0.018, 0.2), bevel=0.006)
        p.box("White", (sx * 0.6, 0, 0.45), (0.008, 0.12, 0.008), bevel=0.004)
    # the lid: a lip all round, the raised top with ribs
    p.box("White", (0, 0, 0.575), (0.62, 0.3, 0.022), bevel=0.016, segments=3)
    p.box("White", (0, -0.01, 0.603), (0.57, 0.25, 0.012), bevel=0.012, segments=3)
    for x in (-0.36, -0.12, 0.12, 0.36):
        p.box("White", (x, -0.01, 0.616), (0.07, 0.22, 0.004), bevel=0.003)
    p.box("Steel", (0, -0.302, 0.55), (0.5, 0.003, 0.028), bevel=0.0015)             # piano hinge along the back
    p.tube("Steel", (-0.5, -0.307, 0.568), (0.5, -0.307, 0.568), 0.006, sides=8)
    # the hasp on the lid, the staple on the body, the padlock
    p.box("Steel", (0, 0.302, 0.555), (0.018, 0.004, 0.045), bevel=0.003)
    p.sweep("Steel", [(-0.012, 0.29, 0.49), (-0.012, 0.31, 0.49), (0.012, 0.31, 0.49), (0.012, 0.29, 0.49)], [(0.003, 0.003)] * 4, sides=6)
    p.box("Gold", (0, 0.318, 0.455), (0.02, 0.008, 0.022), bevel=0.004)
    p.sweep("Steel", [(-0.011, 0.318, 0.47), (-0.011, 0.318, 0.495), (0.0, 0.318, 0.503), (0.011, 0.318, 0.495), (0.011, 0.318, 0.47)],
            [(0.0028, 0.0028)] * 5, sides=6, up=(0, 1, 0))
    p.export(OUT)


def piling_cap():
    """A white moulded piling cap for a 0.3-0.34 m piling (origin at the piling's top): one moulding, a snug skirt held
    by four flush screws running into the cone to a rounded point."""
    p = Part("SM_Dock_PilingCap")
    p.lathe("White", (0, 0, 0), [(0.176, -0.075), (0.184, -0.073), (0.186, -0.066), (0.186, -0.004), (0.184, 0.006),
                                 (0.165, 0.022), (0.1, 0.07), (0.04, 0.108), (0.015, 0.117), (0.0, 0.119)], sides=40)
    for k in range(4):
        a = 2 * math.pi * k / 4 + math.pi / 4
        c = Vector((0.186 * math.cos(a), 0.186 * math.sin(a), -0.035))
        n = Vector((math.cos(a), math.sin(a), 0.0))
        p.tube("Trim", c - n * 0.001, c + n * 0.0015, 0.005, 0.0042, sides=8)
    p.export(OUT)


def hoop():
    """A galvanized piling guide for a 0.34 m piling (origin on its axis at deck height -0.06): a flat-bar ring round
    the piling, two box-section arms back to a mounting plate on the dock's edge (-X) with four bolts, gussets at the
    corners, and three black rollers on vertical axles in yokes, two on the dock side and one opposite. (Round 3's pipe
    ring with welded U yokes lost its blind review 1 of 3 and was reverted: docs/dock-hardware.)"""
    p = Part("SM_Dock_Hoop")
    S = "Steel"
    R = 0.255
    ring = [(R * math.cos(2 * math.pi * k / 36), R * math.sin(2 * math.pi * k / 36), 0.0) for k in range(36)]
    p.sweep(S, ring, [(0.006, 0.04)] * 36, sides=8, closed=True)                   # 80 x 12 mm flat bar
    for s in (-1, 1):
        a0 = Vector((-R * 0.72, s * R * 0.69, 0.0))
        p.sweep(S, [a0 + Vector((0.01, 0, 0)), (-0.3, s * 0.17, 0.0), (-0.355, s * 0.17, 0.0)], [(0.022, 0.025)] * 3, sides=4)
        p.box(S, (-0.32, s * 0.12, -0.018), (0.035, 0.05, 0.004), yaw=s * 25)        # gusset under the arm
    p.box(S, (-0.365, 0, 0.0), (0.01, 0.22, 0.06), bevel=0.003)                    # mounting plate
    for sy in (-0.17, -0.07, 0.07, 0.17):
        p.bolt(S, (-0.355, sy, 0.0), d=0.019, h=0.01, axis="X")
    # rollers: two on the dock side at +-42 deg off -X, one opposite on +X; each a black roller in a yoke
    for ang in (180 - 42, 180 + 42, 0):
        a = math.radians(ang)
        c = Vector((0.212 * math.cos(a), 0.212 * math.sin(a), 0.0))
        out = Vector((math.cos(a), math.sin(a), 0.0))
        p.lathe("Dark", c, [(0.0, -0.075), (0.036, -0.075), (0.04, -0.068), (0.04, 0.068), (0.036, 0.075), (0.0, 0.075)], sides=16)
        p.tube(S, c - Vector((0, 0, 0.1)), c + Vector((0, 0, 0.1)), 0.008, sides=8)
        for z in (-0.088, 0.088):                                                     # the yoke's plates to the ring
            p.box(S, c + out * 0.025 + Vector((0, 0, z)), (0.032, 0.03, 0.005), yaw=math.degrees(a))
            p.lathe(S, c + Vector((0, 0, z + (0.005 if z > 0 else -0.005))), [(0.013, 0.0), (0.013, 0.006 * (1 if z > 0 else -1)), (0.0, 0.006 * (1 if z > 0 else -1))], sides=6)
    p.export(OUT)


def ladder():
    """A stainless swim ladder off the dock's end (+X out over the water): 38 mm (1.5 in) rails 0.44 m apart rise 0.9 m above
    the deck as grab handles and bend back onto it on bolted flange bases; four ribbed treads with end sleeves below the
    deck down to 1 m under the water; a cross brace at the dock's edge, rubber standoffs against the float, end plugs."""
    p = Part("SM_Dock_Ladder")
    S = "Steel"
    r = 0.019
    for s in (-1, 1):
        y = s * 0.22
        pts = [(-0.26, y, 0.012), (-0.26, y, 0.55)]
        # the top bend: a half circle of radius 0.2 from x -0.26 up and over to x +0.14
        cx, cz, rr = -0.06, 0.66, 0.2
        for k in range(1, 12):
            a = math.pi - k * math.pi / 12
            pts.append((cx + rr * math.cos(a), y, cz + rr * math.sin(a) * 0.95))
        pts += [(0.14, y, 0.66), (0.14, y, 0.2), (0.14, y, -1.05)]
        p.sweep(S, pts, [(r, r)] * len(pts), sides=12, caps=("flat", "flat"))
        p.lathe("Dark", (0.14, y, -1.05), [(r * 1.05, 0.0), (r * 1.05, -0.02), (r * 0.8, -0.03), (0.0, -0.03)], sides=12)   # end plug
        # flange base on the deck, three bolts
        p.lathe(S, (-0.26, y, 0.0), [(0.0, 0.0), (0.04, 0.0), (0.04, 0.005), (0.03, 0.008), (0.021, 0.02), (0.018, 0.04)], sides=16)
        for k in range(3):
            a = 2 * math.pi * k / 3 + math.pi / 2
            p.lathe(S, (-0.26 + 0.031 * math.cos(a), y + 0.031 * math.sin(a), 0.005), [(0.005, 0.0), (0.0045, 0.002), (0.0, 0.003)], sides=6)
        # a rubber standoff from the rail to the float's face
        p.tube(S, (0.14, y, -0.25), (0.06, y, -0.25), 0.008, sides=8)
        p.lathe("Dark", (0.06, y, -0.25), [(0.0, 0.0), (0.025, 0.0), (0.028, 0.02), (0.022, 0.035), (0.0, 0.035)], sides=12, axis="-X")
    p.tube(S, (0.14, -0.22, 0.05), (0.14, 0.22, 0.05), 0.011, sides=10)             # cross brace at the deck's edge
    for s in (-1, 1):                                                                  # brackets bolted to the dock's face
        p.tube(S, (0.14, s * 0.22, -0.04), (0.01, s * 0.22, -0.04), 0.012, sides=10)
        p.box(S, (0.006, s * 0.22, -0.04), (0.005, 0.045, 0.05), bevel=0.002)
        for z in (-0.07, -0.01):
            p.bolt(S, (0.011, s * 0.22, z), d=0.013, h=0.005, axis="X")
        p.tube(S, (0.14, s * 0.22, -0.85), (0.06, s * 0.22, -0.85), 0.008, sides=8)  # a lower standoff pad
        p.lathe("Dark", (0.06, s * 0.22, -0.85), [(0.0, 0.0), (0.035, 0.0), (0.038, 0.02), (0.03, 0.035), (0.0, 0.035)], sides=12, axis="-X")
    for k in range(4):
        z = -0.2 - 0.27 * k
        p.box(S, (0.17, 0, z), (0.055, 0.205, 0.01), bevel=0.004)                     # tread
        for j in range(5):                                                             # its ribs
            p.box(S, (0.135 + j * 0.0175, 0, z + 0.012), (0.004, 0.19, 0.003), bevel=0.0015)
        for s in (-1, 1):                                                              # sleeves round the rails
            p.lathe(S, (0.14, s * 0.22, z - 0.03), [(0.024, 0.0), (0.024, 0.05), (0.0, 0.05)], sides=12)
            p.box(S, (0.168, s * 0.205, z - 0.008), (0.05, 0.006, 0.025), bevel=0.002)   # side plates
    p.export(OUT)


def float_drum():
    """A polyethylene dock float, unit size (1 m long, 1 m wide, 1 m deep; the marina scales it per module): rounded
    body with moulded ribs round it."""
    p = Part("SM_Dock_Float")
    p.box("Floats", (0, 0, -0.5), (0.5, 0.5, 0.5), bevel=0.06)   # texture loop: black polyethylene with its waterline (pattern 11)
    for x in (-0.3, -0.1, 0.1, 0.3):
        p.box("Floats", (x, 0, -0.42), (0.025, 0.51, 0.4), bevel=0.012)
    p.export(OUT)


def extinguisher():
    """A fire extinguisher cabinet on a post: a square post on a bolted base plate, a bracket to the red cabinet, its
    door (+X) with a frame round the window, the extinguisher and its hose behind the glass, a pull handle, a hinge on
    one side, a drip cap over the top, and the white FIRE EXTINGUISHER label under the door."""
    p = Part("SM_Dock_Extinguisher")
    p.box("Steel", (0, 0, 0.006), (0.09, 0.09, 0.006), bevel=0.003)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.bolt("Steel", (sx * 0.068, sy * 0.068, 0.012), d=0.013, h=0.006)
    p.box("Steel", (0, 0, 0.42), (0.038, 0.038, 0.41), bevel=0.004)
    p.box("Steel", (0.0, 0, 0.78), (0.045, 0.06, 0.04), bevel=0.003)                # bracket
    p.box("SafetyRed", (0, 0, 1.02), (0.12, 0.13, 0.3), bevel=0.012, segments=2)     # cabinet body
    p.box("SafetyRed", (0.012, 0, 1.332), (0.138, 0.142, 0.012), bevel=0.006)          # rain top over the door
    p.box("SafetyRed", (0.146, 0, 1.318), (0.004, 0.142, 0.012), bevel=0.002)          # its drip edge
    # inside: the extinguisher (red) with its black hose and grey valve, seen through the window
    p.lathe("SafetyRed", (0.0, 0, 0.78), [(0.0, 0.0), (0.075, 0.0), (0.078, 0.01), (0.078, 0.36), (0.06, 0.4), (0.025, 0.41), (0.0, 0.41)], sides=16)
    p.lathe("Trim", (0.0, 0, 1.19), [(0.02, 0.0), (0.02, 0.04), (0.0, 0.05)], sides=10)
    p.sweep("Dark", [(0.0, 0.02, 1.22), (0.05, 0.05, 1.21), (0.08, 0.06, 1.1), (0.08, 0.05, 0.95)], [(0.008, 0.008)] * 4, sides=8)
    # the door: a frame round the glass
    for y in (-0.105, 0.105):
        p.box("SafetyRed", (0.122, y, 1.04), (0.006, 0.02, 0.22))
    for z in (0.83, 1.25):
        p.box("SafetyRed", (0.122, 0, z), (0.006, 0.125, 0.03))
    p.box("Glass", (0.12, 0, 1.04), (0.003, 0.085, 0.19))
    p.tube("Steel", (0.124, 0.127, 0.86), (0.124, 0.127, 1.22), 0.004, sides=8)      # hinge
    p.sweep("Steel", [(0.124, -0.11, 1.0), (0.145, -0.11, 1.0), (0.145, -0.11, 1.08), (0.124, -0.11, 1.08)], [(0.005, 0.005)] * 4, sides=8)
    p.box("White", (0.124, 0, 0.765), (0.003, 0.1, 0.022), bevel=0.002)             # label
    p.export(OUT)


def bumper():
    """A finger-end bumper (new in the detail pass): a black rubber D-profile, its flat back on the finger's fascia just
    under the deck (origin on the tip at deck level, X out from the finger), across the end and round the open corner
    (+Y) 0.3 m back along the side over the rub strip's end, with two ribs along its face; the other corner is the tip
    piling's (AMarinaActor puts it 0.45 m to that side), so the bumper stops square short of it. Screws sunk in it."""
    p = Part("SM_Dock_Bumper")
    W, Back, Z, Rc = 0.30, 0.3, -0.085, 0.08
    pts = [(0.0, -0.24, Z), (0.0, -0.12, Z), (0.0, 0.0, Z), (0.0, 0.12, Z)]
    for k in range(9):                                    # the open corner at +Y
        a = k * (math.pi / 2) / 8
        pts.append((-Rc + Rc * math.cos(a), W - Rc + Rc * math.sin(a), Z))
    pts += [(-0.15, W, Z), (-Back, W, Z)]
    p.sweep("Dark", pts, [(0.045, 0.062)] * len(pts), sides=20, caps=("flat", "flat"))   # half of it inside the fascia: a D
    n = len(pts)
    for dz in (-0.028, 0.028):                                                          # ribs along the face
        rib = []
        for i, q in enumerate(pts):
            t = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
            nrm = Vector((t.y, -t.x, 0.0))
            rib.append(Vector(q) + nrm * 0.0385 + Vector((0, 0, dz)))
        p.sweep("Dark", rib, [(0.006, 0.006)] * n, sides=8)
    for y in (-0.18, 0.0, 0.18):
        p.lathe("Dark", (0.044, y, Z), [(0.0065, 0.0), (0.006, 0.0015), (0.0, 0.002)], sides=8, axis="X")
    p.lathe("Dark", (-0.2, W + 0.044, Z), [(0.0065, 0.0), (0.006, 0.0015), (0.0, 0.002)], sides=8, axis="Y")
    p.export(OUT)


BUILDS = (cleat, pedestal, dock_box, piling_cap, hoop, ladder, float_drum, extinguisher, bumper)

if __name__ == "__main__":
    OUT = sys.argv[sys.argv.index("--") + 1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(OUT, exist_ok=True)
    for build in BUILDS:
        build()
