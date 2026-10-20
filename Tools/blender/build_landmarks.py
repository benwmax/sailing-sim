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
Marseille's (named in French, drawn at their own sizes): SM_Landmark_Church (a Provencal church with its campanile,
28 m), SM_Landmark_Fort (a crenellated fort with round towers, 16 m), SM_Landmark_Lighthouse (a major phare, 70 m),
SM_Landmark_NotreDameGarde (the basilica and its gilded Virgin, 62 m).
Slots: Concrete, Steel, Paint, Red, White, Brick, Roof; Marseille's add Limestone, StoneGreen, RoofTile, Door, Glass, Gold. Prints "Landmarks: <name> <tris>".
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
        self.hard = None   # split the edges sharper than this (degrees): masonry's corners read square, not blobby

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
        if self.hard:
            self.bm.normal_update()
            sharp = [e for e in self.bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(self.hard)]
            bmesh.ops.split_edges(self.bm, edges=sharp)
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


# ------------------------------------------------------------------------------------------------- Marseille's harbour kit
# The Mediterranean landmarks the chart names in French (Tools/coast/worlds/Marseille.json; docs/world-marseille: the
# harbour kit list): built at their real sizes, drawn at them (ALandmarksActor: bOwnHeight).


def gable(p, x0, x1, w, z0, rise, wall, roof, overhang=0.4):
    """A walled block x0..x1 by +-w, eaves at z0, a pitched roof along X rising `rise`, closed gables."""
    p.box(((x0 + x1) / 2, 0.0, z0 / 2), ((x1 - x0) / 2, w, z0 / 2), wall)
    a, b = x0 - overhang, x1 + overhang
    e = w + overhang
    v = [p.bm.verts.new(c) for c in ((a, -e, z0 - 0.2), (b, -e, z0 - 0.2), (b, 0.0, z0 + rise), (a, 0.0, z0 + rise),
                                      (a, e, z0 - 0.2), (b, e, z0 - 0.2))]
    p.face((v[0], v[1], v[2], v[3]), roof)
    p.face((v[3], v[2], v[5], v[4]), roof)
    for x in (x0, x1):
        g = [p.bm.verts.new(c) for c in ((x, -w, z0), (x, w, z0), (x, 0.0, z0 + rise - 0.1))]
        p.face(g if x == x1 else list(reversed(g)), wall)


def merlons(p, pts, z, slot, size=0.7, gap=1.5):
    """Crenellations along a closed polyline of (x, y) at height z."""
    for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
        n = max(1, int(math.hypot(xb - xa, yb - ya) / gap))
        for k in range(n):
            t = (k + 0.5) / n
            p.box((xa + (xb - xa) * t, ya + (yb - ya) * t, z + size / 2), (size / 2, size / 2, size / 2), slot)


def church():
    """A Provencal parish church (eglise, chapelle): a limestone nave under a terracotta roof, a round apse, the west front
    with its door, and a square bell tower topped by a wrought-iron campanile (the bell's cage, against the
    mistral), 28 m."""
    p = Part("SM_Landmark_Church")
    p.hard = 35.0
    gable(p, -14.0, 12.0, 5.5, 11.0, 4.0, "Limestone", "RoofTile")
    p.lathe([(5.5, 0.0), (5.5, 9.0), (0.0, 12.5)], "Limestone", sides=16, x=-14.0)
    p.box((12.1, 0.0, 2.2), (0.15, 1.1, 2.2), "Door")
    # The bell tower beside the choir: shaft, belfry with an opening each face, cornice, low tiled pyramid.
    tx, ty = -6.0, 7.5
    p.box((tx, ty, 9.0), (2.5, 2.5, 9.0), "Limestone")
    p.box((tx, ty, 20.0), (2.6, 2.6, 2.0), "Limestone")
    for dx, dy in ((2.62, 0), (-2.62, 0), (0, 2.62), (0, -2.62)):
        p.box((tx + dx, ty + dy, 20.0), (0.05 if dx else 0.9, 0.9 if dx else 0.05, 1.3), "Door")
    p.box((tx, ty, 22.2), (2.9, 2.9, 0.2), "Limestone")
    v = [p.bm.verts.new(c) for c in ((tx - 2.9, ty - 2.9, 22.4), (tx + 2.9, ty - 2.9, 22.4), (tx + 2.9, ty + 2.9, 22.4),
                                      (tx - 2.9, ty + 2.9, 22.4), (tx, ty, 24.0))]
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
        p.face((v[a], v[b], v[4]), "RoofTile")
    # The campanile: four curved irons to a cross, a bell inside.
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p.tube((tx + 1.4 * math.cos(a), ty + 1.4 * math.sin(a), 23.4), (tx + 0.25 * math.cos(a), ty + 0.25 * math.sin(a), 27.0), 0.06, "Steel")
    p.lathe([(0.0, 25.6), (0.55, 24.4), (0.6, 24.2)], "Steel", sides=10, x=tx, y=ty, caps=False)
    p.tube((tx, ty, 27.0), (tx, ty, 28.0), 0.06, "Steel")
    p.tube((tx - 0.35, ty, 27.7), (tx + 0.35, ty, 27.7), 0.05, "Steel")
    p.export()


def fort():
    """A Provencal fort (fort, chateau, batterie: Chateau d'If, Fort Saint-Jean's towers, the Frioul batteries): a square
    keep in a crenellated limestone curtain with three round towers, 16 m."""
    p = Part("SM_Landmark_Fort")
    p.hard = 35.0
    h = 9.0
    for (cx, cy, ex, ey) in ((0.0, 19.0, 20.0, 1.0), (0.0, -19.0, 20.0, 1.0), (19.0, 0.0, 1.0, 18.0), (-19.0, 0.0, 1.0, 18.0)):
        p.box((cx, cy, h / 2), (ex, ey, h / 2), "Limestone")
    merlons(p, [(-19.5, -19.5), (19.5, -19.5), (19.5, 19.5), (-19.5, 19.5)], h, "Limestone")
    for (x, y) in ((19.0, 19.0), (-19.0, 19.0), (19.0, -19.0)):
        p.lathe([(5.6, 0.0), (5.0, 3.0), (5.0, 13.0), (5.4, 13.2), (5.4, 14.0)], "Limestone", sides=20, x=x, y=y)
        merlons(p, [(x + 5.0 * math.cos(2 * math.pi * k / 10), y + 5.0 * math.sin(2 * math.pi * k / 10)) for k in range(10)], 14.0, "Limestone", gap=3.2)
    p.box((-3.0, -3.0, 7.5), (8.0, 8.0, 7.5), "Limestone")
    merlons(p, [(-11.0, -11.0), (5.0, -11.0), (5.0, 5.0), (-11.0, 5.0)], 15.0, "Limestone")
    for (x, y, z) in ((5.05, -3.0, 9.0), (5.05, -6.0, 9.0), (5.05, 0.0, 9.0)):
        p.box((x, y, z), (0.05, 0.4, 0.8), "Door")
    p.box((19.05, 0.0, 2.0), (0.1, 1.6, 2.0), "Door")
    p.export()


def lighthouse():
    """A major French lighthouse (phare: Planier, 68 m): a keeper's block at the foot, a tall limestone tower tapering to
    its corbelled gallery, the lantern and its dome; 70 m to the vane."""
    p = Part("SM_Landmark_Lighthouse")
    p.hard = 35.0
    gable(p, -9.0, 9.0, 6.0, 7.0, 1.2, "Limestone", "RoofTile")
    p.lathe([(5.2, 0.0), (5.2, 8.0), (4.6, 9.0), (3.4, 60.0), (3.4, 61.0)], "Limestone", sides=24)
    p.lathe([(3.4, 61.0), (4.6, 61.6), (4.6, 62.2), (0.0, 62.2)], "Limestone", sides=24, caps=False)
    for k in range(20):
        a = 2 * math.pi * k / 20
        p.tube((4.4 * math.cos(a), 4.4 * math.sin(a), 62.2), (4.4 * math.cos(a), 4.4 * math.sin(a), 63.3), 0.05, "Steel", sides=4)
    p.lathe([(4.45, 63.2), (4.45, 63.35)], "Steel", sides=24, caps=False)
    p.lathe([(2.2, 62.2), (2.2, 63.0)], "Steel", sides=16, caps=False)
    p.lathe([(2.1, 63.0), (2.1, 67.0)], "Glass", sides=16, caps=False)
    p.lathe([(2.4, 67.0), (1.8, 68.2), (0.6, 69.2), (0.0, 69.4)], "Steel", sides=16, caps=False)
    p.tube((0.0, 0.0, 69.4), (0.0, 0.0, 70.0), 0.06, "Steel")
    for z in range(12, 58, 7):
        r = 4.6 - (z - 9.0) * (1.2 / 51.0)
        p.box((r + 0.02, 0.0, float(z)), (0.06, 0.35, 0.9), "Door")
    p.box((5.22, 0.0, 1.4), (0.08, 0.9, 1.4), "Door")
    p.export()


def notre_dame_garde():
    """Notre-Dame de la Garde, Marseille's landmark on its 149 m hill: the fortress-like crypt platform, the Romano-Byzantine
    basilica in bands of white limestone and green stone, its dome, and the square bell tower with its belfry carrying the
    gilded Virgin and Child, 11 m, about 62 m to her crown."""
    p = Part("SM_Landmark_NotreDameGarde")
    p.hard = 35.0
    p.box((0.0, 0.0, 5.0), (28.0, 13.0, 5.0), "Limestone")
    merlons(p, [(-28.0, -13.0), (28.0, -13.0), (28.0, 13.0), (-28.0, 13.0)], 10.0, "Limestone", size=0.8, gap=2.2)
    # The nave in courses: white and green bands, 1.2 m each.
    for k in range(10):
        z0 = 10.0 + 1.2 * k
        p.box((-6.0, 0.0, z0 + 0.6), (17.0, 7.0, 0.6), "Limestone" if k % 2 == 0 else "StoneGreen")
    v = [p.bm.verts.new(c) for c in ((-23.4, -7.4, 21.8), (11.4, -7.4, 21.8), (11.4, 0.0, 25.0), (-23.4, 0.0, 25.0), (-23.4, 7.4, 21.8), (11.4, 7.4, 21.8))]
    p.face((v[0], v[1], v[2], v[3]), "Steel")
    p.face((v[3], v[2], v[5], v[4]), "Steel")
    # The dome on its drum over the crossing, striped too.
    p.lathe([(5.0, 22.0), (5.0, 25.5)], "StoneGreen", sides=24, x=-14.0, caps=False)
    p.lathe([(5.4, 25.5), (5.0, 27.5), (3.6, 30.0), (1.2, 31.4), (0.0, 31.6)], "Gold", sides=24, x=-14.0)
    # The bell tower at the west front: shaft in bands, the belfry, a cornice, the drum and the statue.
    tx = 18.0
    for k in range(18):
        z0 = 10.0 + 1.5 * k
        p.box((tx, 0.0, z0 + 0.75), (4.6, 4.6, 0.75), "Limestone" if k % 2 == 0 else "StoneGreen")
    p.box((tx, 0.0, 41.0), (4.9, 4.9, 4.0), "Limestone")
    for dx, dy in ((4.92, 0), (-4.92, 0), (0, 4.92), (0, -4.92)):
        p.box((tx + dx, dy, 41.0), (0.05 if dx else 1.5, 1.5 if dx else 0.05, 2.8), "Door")
    p.box((tx, 0.0, 45.3), (5.3, 5.3, 0.3), "Limestone")
    p.lathe([(3.4, 45.6), (3.4, 48.6), (2.6, 49.2), (1.6, 50.6)], "Limestone", sides=20, x=tx)
    # The Virgin, gilded copper: robe to the crown, the Child on her left arm.
    p.lathe([(1.5, 50.6), (1.7, 51.5), (1.4, 55.0), (1.1, 57.5), (0.9, 58.6), (0.55, 59.2), (0.6, 60.2), (0.45, 61.0), (0.0, 61.6)], "Gold", sides=16, x=tx)
    p.lathe([(0.45, 57.4), (0.5, 58.4), (0.3, 59.0), (0.0, 59.3)], "Gold", sides=10, x=tx + 0.8, y=0.7)
    p.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
platform()
water_tower()
mast()
windmill()
stack()
spire()
flagstaff()
church()
fort()
lighthouse()
notre_dame_garde()
