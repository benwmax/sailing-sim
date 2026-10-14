"""Visual V6: the chart's landmarks, built in Blender from code (run headless by scripts/make-world-models.sh).

S-57 LNDMRK categories and the bay's platforms, at typical sizes (origin at the foot, metres; the game scales a
landmark to its charted height when the chart gives one):
  SM_Landmark_Platform   a bay gas-well platform: four-pile jacket, deck at 6 m, wellhead, boat landing (OFSPLF)
  SM_Landmark_WaterTower a Texas spheroid on a fluted pedestal, 40 m (tower, CATLMK 17)
  SM_Landmark_Mast       a guyed lattice radio mast, 100 m, in aviation red and white bands (mast, 7)
  SM_Landmark_Windmill   a farm windpump: lattice tower and a multi-blade wheel with its vane, 12 m (windmill, 18)
  SM_Landmark_Stack      a refinery stack, 60 m, tapering, with a platform near the top (chimney, 3)
  SM_Landmark_Spire      a church: nave and a spire, 30 m (spire, 20)
  SM_Landmark_Flagstaff  a 15 m flagstaff (5)
Slots: Concrete, Steel, Paint, Red, White, Brick, Roof. Prints "Landmarks: <name> <tris>".
Usage: blender -b --factory-startup -P build_landmarks.py -- <out dir>
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

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

    def face(self, verts, slot):
        f = self.bm.faces.new(verts)
        f.material_index = self.slot(slot)
        for loop in f.loops:
            c = loop.vert.co
            loop[self.uv].uv = (math.atan2(c.y, c.x) * max(math.hypot(c.x, c.y), 0.2), c.z)
        return f

    def lathe(self, profile, slot, sides=16, x=0.0, y=0.0, caps=True):
        rings = [[self.bm.verts.new((x + r * math.cos(2 * math.pi * k / sides), y + r * math.sin(2 * math.pi * k / sides), z)) for k in range(sides)] for r, z in profile]
        for a, b in zip(rings, rings[1:]):
            for k in range(sides):
                self.face((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]), slot)
        if caps and profile[0][0] > 0:
            self.face(list(reversed(rings[0])), slot)
        if caps and profile[-1][0] > 0:
            self.face(rings[-1], slot)

    def tube(self, a, b, r, slot, sides=6):
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized()
        u = d.orthogonal().normalized()
        v = d.cross(u)
        ring = lambda c: [self.bm.verts.new(c + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides)]
        ra, rb = ring(a), ring(b)
        for k in range(sides):
            self.face((ra[k], ra[(k + 1) % sides], rb[(k + 1) % sides], rb[k]), slot)

    def box(self, c, e, slot):
        x, y, z = c
        ex, ey, ez = e
        v = [self.bm.verts.new((x + sx * ex, y + sy * ey, z + sz * ez)) for sx, sy, sz in
             ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.face([v[i] for i in f], slot)

    def lattice(self, h, w0, w1, slot, legs=3, panels=10, r=0.06, z0=0.0):
        """A tapering lattice tower: legs and zig-zag bracing."""
        pts = lambda z: [(((w0 + (w1 - w0) * (z - z0) / h) * math.cos(2 * math.pi * k / legs + 0.3)), ((w0 + (w1 - w0) * (z - z0) / h) * math.sin(2 * math.pi * k / legs + 0.3)), z) for k in range(legs)]
        for k in range(legs):
            self.tube(pts(z0)[k], pts(z0 + h)[k], r, slot)
        for i in range(panels):
            za, zb = z0 + h * i / panels, z0 + h * (i + 1) / panels
            A, B = pts(za), pts(zb)
            for k in range(legs):
                self.tube(A[k], B[(k + 1) % legs], r * 0.5, slot, sides=4)
                self.tube(B[k], B[(k + 1) % legs], r * 0.5, slot, sides=4)

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
        print(f"Landmarks: {self.name} {tris}")


def platform():
    p = Part("SM_Landmark_Platform")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.tube((sx * 3.2, sy * 3.2, -6.0), (sx * 2.6, sy * 2.6, 6.0), 0.35, "Paint", sides=8)
    for z in (1.5, 4.0):
        for a, b in (((-3.0, -3.0), (3.0, -3.0)), ((3.0, -3.0), (3.0, 3.0)), ((3.0, 3.0), (-3.0, 3.0)), ((-3.0, 3.0), (-3.0, -3.0))):
            p.tube((a[0], a[1], z), (b[0], b[1], z), 0.15, "Paint")
    p.box((0.0, 0.0, 6.2), (3.6, 3.6, 0.2), "Steel")
    p.lathe([(0.25, 6.4), (0.25, 8.0), (0.4, 8.1), (0.4, 8.5), (0.0, 8.6)], "Red", sides=10)      # wellhead "christmas tree"
    p.box((1.8, -1.5, 7.0), (0.9, 0.6, 0.6), "Steel")                                               # separator
    p.box((-4.2, 0.0, 0.8), (0.6, 1.5, 0.08), "Steel")                                              # boat landing
    for z in (6.4, 7.4):
        for a, b in (((-3.6, -3.6), (3.6, -3.6)), ((3.6, -3.6), (3.6, 3.6)), ((3.6, 3.6), (-3.6, 3.6)), ((-3.6, 3.6), (-3.6, -3.6))):
            p.tube((a[0], a[1], z), (b[0], b[1], z), 0.04, "Paint", sides=4)
    p.export()


def water_tower():
    p = Part("SM_Landmark_WaterTower")
    p.lathe([(5.0, 0.0), (3.0, 3.0), (1.8, 8.0), (1.6, 26.0), (3.0, 28.0)], "White", sides=20, caps=False)
    sph = [(9.0 * math.sin(math.pi * i / 14), 34.0 - 7.0 * math.cos(math.pi * i / 14)) for i in range(15)]
    p.lathe([(1.6, 27.0)] + sph[1:], "White", sides=24, caps=False)
    p.lathe([(0.0, 41.0), (0.6, 41.0), (0.6, 41.6), (0.0, 41.6)], "Steel", sides=8)
    p.export()


def mast():
    p = Part("SM_Landmark_Mast")
    h = 100.0
    for i in range(7):
        p.lattice(h / 7, 0.9, 0.9, "Red" if i % 2 == 0 else "White", panels=6, r=0.07, z0=i * h / 7)
    for k in range(3):
        a = 2 * math.pi * k / 3
        for f in (0.35, 0.7, 0.98):
            p.tube((0.0, 0.0, h * f), (60.0 * f * math.cos(a), 60.0 * f * math.sin(a), 0.0), 0.02, "Steel", sides=3)
    p.export()


def windmill():
    p = Part("SM_Landmark_Windmill")
    p.lattice(11.0, 2.0, 0.4, "Steel", legs=4, panels=6, r=0.05)
    hub = Vector((0.6, 0.0, 11.5))
    for k in range(18):
        a = 2 * math.pi * k / 18
        tip = hub + Vector((0.0, 1.8 * math.cos(a), 1.8 * math.sin(a)))
        p.tube(hub, tip, 0.04, "Paint", sides=3)
        p.box((tip.x, (hub.y + tip.y) / 2, (hub.z + tip.z) / 2), (0.02, 0.12, 0.12), "Paint")
    p.box((-1.6, 0.0, 11.5), (1.4, 0.03, 0.6), "Paint")                                            # tail vane
    p.export()


def stack():
    p = Part("SM_Landmark_Stack")
    p.lathe([(2.4, 0.0), (2.0, 20.0), (1.5, 55.0), (1.5, 60.0)], "Concrete", sides=16, caps=False)
    p.lathe([(1.5, 56.0), (1.5, 60.0)], "Red", sides=16, caps=False)
    p.lathe([(2.4, 52.0), (2.4, 52.3)], "Steel", sides=16)
    p.export()


def spire():
    p = Part("SM_Landmark_Spire")
    p.box((-6.0, 0.0, 4.0), (10.0, 6.0, 4.0), "Brick")
    p.face([p.bm.verts.new(c) for c in ((-16.0, -6.5, 8.0), (4.0, -6.5, 8.0), (4.0, 0.0, 13.0), (-16.0, 0.0, 13.0))], "Roof")
    p.face([p.bm.verts.new(c) for c in ((4.0, 6.5, 8.0), (-16.0, 6.5, 8.0), (-16.0, 0.0, 13.0), (4.0, 0.0, 13.0))], "Roof")
    p.box((6.5, 0.0, 9.0), (2.5, 2.5, 9.0), "Brick")
    p.lathe([(2.4, 18.0), (0.05, 30.0)], "Roof", sides=8)
    p.export()


def flagstaff():
    p = Part("SM_Landmark_Flagstaff")
    p.lathe([(0.12, 0.0), (0.05, 15.0)], "White", sides=8)
    p.lathe([(0.15, 15.0), (0.15, 15.3), (0.0, 15.35)], "Steel", sides=8)
    p.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
platform()
water_tower()
mast()
windmill()
stack()
spire()
flagstaff()
