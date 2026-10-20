"""Visual V6: aids to navigation, built in Blender from code (run headless by scripts/make-world-models.sh).

Shapes after the USCG's buoys and beacons (Aids to Navigation Manual): origin at the waterline (buoys) or the bottom of
the visible pile (beacons, which the game stands on the bottom), X forward, Z up, metres.
  SM_Buoy_Can     second-class can: a foam-filled steel float with a cylindrical can on top (odd numbers, green)
  SM_Buoy_Nun     the same float with a conical nun (even numbers, red)
  SM_Buoy_Pillar  a lighted buoy: wide float, four-legged tower, lantern at 3.4 m, radar reflector
  SM_Buoy_Sphere  a spherical special-purpose buoy
  SM_Beacon_Pile  a three-pile dolphin bound with wire, a platform on top (dayboard and light are separate)
  SM_Dayboard_Square / SM_Dayboard_Triangle  the boards with their reflective border
  SM_Light_Tower  a steel skeleton tower for a minor light, ladder and lantern on top
  SM_Light_MoleTower  a European (IALA A) harbour light: whitewashed masonry tower, coloured top, gallery, lantern
Slots: Paint (the aid's colour per instance, with rust and growth from M_NavaidPaint), Dark (counterweight, fenders),
Steel, Wood, Lantern, Reflective; the mole tower adds White, Concrete and Door. Prints "Navaids: <name> <tris>".
Usage: blender -b --factory-startup -P build_navaids.py -- <out dir>
"""
import math
import os
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index("--") + 1]


class Part:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.slots = []

    def slot(self, name):
        if name not in self.slots:
            self.slots.append(name)
        return self.slots.index(name)

    def _face(self, verts, slot):
        f = self.bm.faces.new(verts)
        f.material_index = self.slot(slot)
        for loop in f.loops:
            c = loop.vert.co
            loop[self.uv].uv = (math.atan2(c.y, c.x) * max(math.hypot(c.x, c.y), 0.1), c.z)
        return f

    def lathe(self, profile, slot, sides=20, cap_top=True, cap_bottom=True, x=0.0, y=0.0):
        """Revolves (radius, z) points about a vertical axis at (x, y)."""
        rings = []
        for r, z in profile:
            rings.append([self.bm.verts.new((x + r * math.cos(2 * math.pi * k / sides), y + r * math.sin(2 * math.pi * k / sides), z)) for k in range(sides)])
        for a, b in zip(rings, rings[1:]):
            for k in range(sides):
                k2 = (k + 1) % sides
                self._face((a[k], a[k2], b[k2], b[k]), slot)
        if cap_bottom and profile[0][0] > 0:
            self._face(list(reversed(rings[0])), slot)
        if cap_top and profile[-1][0] > 0:
            self._face(rings[-1], slot)

    def tube(self, a, b, r, slot, sides=8):
        """A cylinder from point a to point b."""
        import mathutils
        a, b = mathutils.Vector(a), mathutils.Vector(b)
        d = (b - a).normalized()
        u = d.orthogonal().normalized()
        v = d.cross(u)
        ring = lambda c: [self.bm.verts.new(c + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides)]
        ra, rb = ring(a), ring(b)
        for k in range(sides):
            k2 = (k + 1) % sides
            self._face((ra[k], ra[k2], rb[k2], rb[k]), slot)
        self._face(list(reversed(ra)), slot)
        self._face(rb, slot)

    def box(self, c, e, slot):
        x, y, z = c
        ex, ey, ez = e
        v = [self.bm.verts.new((x + sx * ex, y + sy * ey, z + sz * ez)) for sx, sy, sz in
             ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self._face([v[i] for i in f], slot)

    def export(self):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        tris = sum(len(f.verts) - 2 for f in self.bm.faces)
        self.bm.free()
        for s in self.slots:
            mesh.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
        for p in mesh.polygons:
            p.use_smooth = True
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, self.name + ".fbx"), use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                                 mesh_smooth_type="FACE")
        bpy.data.objects.remove(obj)
        print(f"Navaids: {self.name} {tris}")


def float_body(p, r=0.75):
    """The buoy's float: a flattened drum riding about a third submerged, a rubbing fender, the counterweight tube below."""
    p.lathe([(0.0, -0.5), (r * 0.9, -0.48), (r, -0.35), (r, 0.12), (r * 0.95, 0.2), (0.0, 0.22)], "Paint")
    p.lathe([(r + 0.04, -0.02), (r + 0.06, 0.02), (r + 0.06, 0.08), (r + 0.04, 0.1)], "Dark", cap_top=False, cap_bottom=False)
    p.lathe([(0.12, -2.2), (0.12, -0.5)], "Dark")
    p.lathe([(0.32, -2.5), (0.32, -2.2)], "Dark")


def can():
    p = Part("SM_Buoy_Can")
    float_body(p)
    p.lathe([(0.45, 0.2), (0.45, 1.45), (0.42, 1.5)], "Paint")
    p.lathe([(0.47, 1.0), (0.47, 1.25)], "Reflective", cap_top=False, cap_bottom=False)
    p.export()


def nun():
    p = Part("SM_Buoy_Nun")
    float_body(p)
    p.lathe([(0.5, 0.2), (0.5, 0.7), (0.06, 1.7), (0.0, 1.72)], "Paint")
    p.lathe([(0.42, 0.75), (0.3, 1.05)], "Reflective", cap_top=False, cap_bottom=False)
    p.export()


def pillar():
    p = Part("SM_Buoy_Pillar")
    float_body(p, r=1.2)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p.tube((0.85 * math.cos(a), 0.85 * math.sin(a), 0.2), (0.35 * math.cos(a), 0.35 * math.sin(a), 3.0), 0.05, "Paint")
    for z, r in ((1.2, 0.68), (2.2, 0.48)):
        p.lathe([(r, z), (r, z + 0.06)], "Paint", cap_top=False, cap_bottom=False)
    p.box((0.0, 0.0, 1.6), (0.36, 0.02, 0.55), "Reflective")      # day panels both ways
    p.box((0.0, 0.0, 1.6), (0.02, 0.36, 0.55), "Reflective")
    p.lathe([(0.4, 3.0), (0.4, 3.08)], "Paint")
    p.lathe([(0.12, 3.08), (0.12, 3.35), (0.14, 3.42), (0.0, 3.45)], "Lantern")
    p.box((0.0, 0.0, 2.6), (0.18, 0.18, 0.18), "Steel")             # radar reflector
    p.export()


def sphere():
    p = Part("SM_Buoy_Sphere")
    prof = [(0.75 * math.sin(math.pi * i / 12), -0.75 * math.cos(math.pi * i / 12) + 0.35) for i in range(13)]
    p.lathe(prof, "Paint")
    p.lathe([(0.12, -2.0), (0.12, -0.3)], "Dark")
    p.export()


def pile():
    p = Part("SM_Beacon_Pile")
    for k in range(3):
        a = k * 2 * math.pi / 3
        x, y = 0.22 * math.cos(a), 0.22 * math.sin(a)
        p.lathe([(0.17, 0.0), (0.16, 6.0)], "Wood", sides=10, x=x, y=y)
    for z in (1.8, 3.6, 5.4):
        p.lathe([(0.42, z), (0.42, z + 0.05)], "Steel", cap_top=False, cap_bottom=False)
    p.box((0.0, 0.0, 6.05), (0.45, 0.45, 0.05), "Wood")
    p.export()


def dayboards():
    sq = Part("SM_Dayboard_Square")
    sq.box((0.0, 0.0, 0.0), (0.03, 0.55, 0.55), "Paint")
    for c, e in (((0.035, 0.0, 0.5), (0.005, 0.55, 0.05)), ((0.035, 0.0, -0.5), (0.005, 0.55, 0.05)),
                 ((0.035, 0.5, 0.0), (0.005, 0.05, 0.55)), ((0.035, -0.5, 0.0), (0.005, 0.05, 0.55))):
        sq.box(c, e, "Reflective")
    sq.export()
    tr = Part("SM_Dayboard_Triangle")
    v = [tr.bm.verts.new(c) for c in ((-0.03, -0.6, -0.5), (-0.03, 0.6, -0.5), (-0.03, 0.0, 0.55), (0.03, -0.6, -0.5), (0.03, 0.6, -0.5), (0.03, 0.0, 0.55))]
    for f in ((0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)):
        tr._face([v[i] for i in f], "Paint")
    tr.box((0.035, 0.0, -0.45), (0.005, 0.55, 0.05), "Reflective")
    tr.export()


def tower():
    p = Part("SM_Light_Tower")
    h = 9.0
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p.tube((1.1 * math.cos(a), 1.1 * math.sin(a), -3.0), (0.45 * math.cos(a), 0.45 * math.sin(a), h), 0.07, "Steel")
    for i in range(1, 7):
        z = h * i / 7
        r = 1.1 + (0.45 - 1.1) * (z + 3.0) / (h + 3.0)
        for k in range(4):
            a0, a1 = math.pi / 4 + k * math.pi / 2, math.pi / 4 + (k + 1) * math.pi / 2
            p.tube((r * math.cos(a0), r * math.sin(a0), z), (r * math.cos(a1), r * math.sin(a1), z), 0.035, "Steel", sides=6)
    p.box((0.0, 0.0, h + 0.05), (0.7, 0.7, 0.05), "Steel")
    p.lathe([(0.2, h + 0.1), (0.2, h + 0.55), (0.24, h + 0.6), (0.0, h + 0.68)], "Lantern")
    p.export()


def mole_tower():
    """A European harbour light (IALA A, Marseille's mole heads): a round masonry tower on a plinth, whitewashed, its top
    third in the light's colour (Paint: red to port, green to starboard), a railed gallery and the lantern with its
    painted dome; the lantern's centre at 9.68 m like SM_Light_Tower so the actor scales both the same."""
    p = Part("SM_Light_MoleTower")
    p.lathe([(1.75, -1.0), (1.75, 0.35), (1.55, 0.45)], "Concrete", sides=28, cap_top=False)
    body = [(1.30, 0.45), (1.22, 3.0), (1.12, 5.6)]
    p.lathe(body, "White", sides=28, cap_bottom=False, cap_top=False)
    p.lathe([(1.12, 5.6), (1.04, 8.2), (1.04, 8.25)], "Paint", sides=28, cap_bottom=False, cap_top=False)
    # The gallery: a corbelled slab, its rail on stanchions.
    p.lathe([(1.04, 8.25), (1.45, 8.35), (1.45, 8.5), (0.0, 8.5)], "White", sides=28, cap_bottom=False)
    for k in range(16):
        a = 2 * math.pi * k / 16
        p.tube((1.38 * math.cos(a), 1.38 * math.sin(a), 8.5), (1.38 * math.cos(a), 1.38 * math.sin(a), 9.45), 0.025, "Steel", sides=6)
    p.lathe([(1.40, 9.42), (1.40, 9.48), (1.36, 9.48), (1.36, 9.42)], "Steel", sides=28, cap_top=False, cap_bottom=False)
    p.lathe([(0.55, 8.5), (0.55, 9.1)], "Paint", sides=20, cap_bottom=False, cap_top=False)
    p.lathe([(0.5, 9.1), (0.5, 10.26)], "Lantern", sides=20, cap_bottom=False, cap_top=False)
    p.lathe([(0.58, 10.26), (0.45, 10.5), (0.2, 10.65), (0.0, 10.7)], "Paint", sides=20, cap_bottom=False)
    p.tube((0.0, 0.0, 10.7), (0.0, 0.0, 11.1), 0.03, "Steel", sides=6)
    # A door and two slit windows up the tower's face.
    p.box((1.27, 0.0, 1.3), (0.06, 0.45, 0.9), "Door")
    for z in (3.6, 6.4):
        p.box((1.18 - 0.035 * (z - 3.6), 0.0, z), (0.05, 0.12, 0.35), "Door")
    p.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
can()
nun()
pillar()
sphere()
pile()
dayboards()
tower()
mole_tower()
