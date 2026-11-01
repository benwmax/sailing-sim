"""Club docks (slice #405 part 2, pass 2): the floating docks' hardware at real size, built in Blender from code (run
headless by scripts/make-world-models.sh). AMarinaActor places them as static instances at the points its generator
computes (AMarinaActor::DockKitPlacements); without them it draws the kit's boxes.

Each mesh: X along its finger or out from the dock's edge, Z up, the origin on the deck (or on the piling's axis at deck
height for the hoop, on its top for the cap). Slots name MI_World_* looks (import_world.py's WORLD_SLOTS): White
(weathered moulded plastic), Steel, Dark (black rubber and plastic), LampGlow, SafetyRed. UVs are box-projected in
metres. Prints "Docks: <name> <tris>".
Usage: blender -b --factory-startup -P build_docks.py -- <out dir>
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = sys.argv[sys.argv.index("--") + 1]


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

    def box(self, slot, c, half, bevel=0.0, yaw=0.0):
        """A box centred at c with half extents, its edges rounded by `bevel` metres, turned by yaw (deg) about Z."""
        geom = bmesh.ops.create_cube(self.bm, size=1.0)
        verts = geom["verts"]
        bmesh.ops.scale(self.bm, vec=Vector(half) * 2.0, verts=verts)
        if bevel > 0.0:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bevel, segments=2, affect="EDGES", profile=0.5)
            verts = list({v for f in res["faces"] for v in f.verts} | set(v for v in verts if v.is_valid))
        verts = [v for v in verts if v.is_valid]
        bmesh.ops.transform(self.bm, matrix=Matrix.Rotation(math.radians(yaw), 4, "Z"), verts=verts)
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=verts)
        self._faces({f for v in verts for f in v.link_faces}, slot)

    def tube(self, slot, a, b, r0, r1=None, sides=12, caps=True):
        """A round bar from a to b, radius r0 at a and r1 at b."""
        r1 = r0 if r1 is None else r1
        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        u = axis.cross(Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))).normalized()
        w = axis.cross(u)
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
        rings = []
        for i, p in enumerate(pts):
            p = Vector(p)
            d = (Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
            u = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized()
            w = d.cross(u)
            rings.append([self.bm.verts.new(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * r)
                          for k in range(sides)])
        faces = []
        for ra, rb in zip(rings, rings[1:]):
            faces += [self.bm.faces.new((ra[k], ra[(k + 1) % sides], rb[(k + 1) % sides], rb[k])) for k in range(sides)]
        faces.append(self.bm.faces.new(list(reversed(rings[0]))))
        faces.append(self.bm.faces.new(rings[-1]))
        self._faces(faces, slot)

    def lathe(self, slot, c, profile, sides=16):
        """A turned part about a vertical axis through c: profile [(radius, z)] from the bottom up."""
        c = Vector(c)
        rings = []
        for r, z in profile:
            if r <= 1e-6:
                rings.append([self.bm.verts.new(c + Vector((0, 0, z)))])
            else:
                rings.append([self.bm.verts.new(c + Vector((r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides), z)))
                              for k in range(sides)])
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

    def export(self):
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
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, self.name + ".fbx"), use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                                 mesh_smooth_type="FACE")
        bpy.data.objects.remove(obj)
        print(f"Docks: {self.name} {tris}")


def cleat():
    """A 10 in cast aluminium dock cleat: two splayed feet on a base plate, the horn tapering to rounded ends."""
    p = Part("SM_Dock_Cleat")
    p.box("Steel", (0, 0, 0.004), (0.065, 0.032, 0.004), bevel=0.003)
    for s in (-1, 1):
        p.tube("Steel", (s * 0.04, 0, 0.006), (s * 0.03, 0, 0.05), 0.018, 0.013, sides=10)
        p.path("Steel", [(s * 0.03, 0, 0.055), (s * 0.075, 0, 0.062), (s * 0.115, 0, 0.066), (s * 0.127, 0, 0.064)], 0.011, sides=10)
    p.tube("Steel", (-0.03, 0, 0.055), (0.03, 0, 0.055), 0.014, sides=10)
    p.export()


def pedestal():
    """A shore power pedestal (about 1.1 m): a moulded post with a meter window and two outlet covers toward the slip
    (+X), the lamp lens under a domed cap, and a dark base plate."""
    p = Part("SM_Dock_Pedestal")
    p.box("Dark", (0, 0, 0.015), (0.17, 0.17, 0.015), bevel=0.006)
    p.box("White", (0, 0, 0.5), (0.12, 0.12, 0.48), bevel=0.025)
    p.box("Dark", (0.122, 0, 0.74), (0.004, 0.07, 0.085), bevel=0.004)       # meter window
    for z in (0.44, 0.58):
        p.box("Steel", (0.124, 0, z), (0.006, 0.055, 0.045), bevel=0.004)   # outlet covers
    p.lathe("LampGlow", (0, 0, 0.98), [(0.11, 0.0), (0.115, 0.03), (0.11, 0.06)], sides=16)
    p.lathe("White", (0, 0, 1.04), [(0.135, 0.0), (0.14, 0.015), (0.12, 0.045), (0.07, 0.07), (0.0, 0.078)], sides=16)
    p.export()


def dock_box():
    """A moulded dock box (1.2 x 0.56 x 0.6 m) along the finger: rounded body, the lid proud of it with a lip, the
    hinge along its back, a hasp at the front and a dark toe kick."""
    p = Part("SM_Dock_Box")
    p.box("Dark", (0, 0, 0.02), (0.58, 0.26, 0.02), bevel=0.01)
    p.box("White", (0, 0, 0.29), (0.6, 0.28, 0.26), bevel=0.035)
    p.box("White", (0, 0, 0.585), (0.62, 0.3, 0.03), bevel=0.02)
    p.tube("Steel", (-0.5, -0.29, 0.555), (0.5, -0.29, 0.555), 0.012, sides=8)
    p.box("Steel", (0, 0.302, 0.52), (0.035, 0.006, 0.05), bevel=0.004)
    p.export()


def piling_cap():
    """A white conical piling cap for a 0.34 m piling, its skirt over the top (origin at the piling's top)."""
    p = Part("SM_Dock_PilingCap")
    p.lathe("White", (0, 0, 0), [(0.19, -0.06), (0.195, -0.055), (0.195, 0.0), (0.16, 0.05), (0.06, 0.11), (0.0, 0.12)], sides=20)
    p.export()


def hoop():
    """A piling hoop for a 0.34 m piling: a steel ring round the piling (origin on its axis at deck height), two arms
    back to the dock's edge (-X, 0.37 m out) bolted to a plate, and two black rollers bearing on the piling."""
    p = Part("SM_Dock_Hoop")
    ring = [(0.25 * math.cos(2 * math.pi * k / 24), 0.25 * math.sin(2 * math.pi * k / 24), 0.0) for k in range(25)]
    p.path("Steel", ring, 0.022, sides=8)
    for s in (-1, 1):
        p.path("Steel", [(-0.18, s * 0.17, 0.0), (-0.3, s * 0.15, 0.0), (-0.37, s * 0.15, 0.0)], 0.022, sides=8)
        p.tube("Dark", (-0.2, s * 0.08, -0.12), (-0.2, s * 0.08, 0.12), 0.045, sides=12)
        p.tube("Steel", (-0.2, s * 0.08, -0.14), (-0.2, s * 0.08, 0.14), 0.008, sides=6)
    p.box("Steel", (-0.38, 0, 0.0), (0.008, 0.2, 0.06), bevel=0.003)
    p.export()


def ladder():
    """A stainless swim ladder off the dock's end (+X out over the water): the rails rise 0.9 m above the deck and bend
    back onto it, four treads below the deck down to 1 m under the water."""
    p = Part("SM_Dock_Ladder")
    for s in (-1, 1):
        y = s * 0.22
        p.path("Steel", [(-0.25, y, 0.0), (-0.25, y, 0.6), (-0.15, y, 0.85), (0.02, y, 0.88), (0.12, y, 0.75), (0.14, y, 0.2), (0.14, y, -1.05)], 0.019, sides=10)
    for k in range(4):
        z = -0.2 - 0.27 * k
        p.box("Steel", (0.16, 0, z), (0.05, 0.22, 0.012), bevel=0.004)
    p.export()


def float_drum():
    """A polyethylene dock float, unit size (1 m long, 1 m wide, 1 m deep; the marina scales it per module): rounded
    body with moulded ribs round it."""
    p = Part("SM_Dock_Float")
    p.box("Dark", (0, 0, -0.5), (0.5, 0.5, 0.5), bevel=0.06)
    for x in (-0.3, -0.1, 0.1, 0.3):
        p.box("Dark", (x, 0, -0.42), (0.025, 0.51, 0.4), bevel=0.012)
    p.export()


def extinguisher():
    """A fire extinguisher cabinet on a post: the red cabinet, its window and a white label, at a walkway's edge."""
    p = Part("SM_Dock_Extinguisher")
    p.tube("Steel", (0, 0, 0.0), (0, 0, 0.75), 0.03, sides=10)
    p.box("Dark", (0, 0, 0.01), (0.09, 0.09, 0.01), bevel=0.004)
    p.box("SafetyRed", (0, 0, 1.02), (0.13, 0.11, 0.3), bevel=0.02)
    p.box("Dark", (0.112, 0, 1.05), (0.004, 0.08, 0.2), bevel=0.004)
    p.box("White", (0.114, 0, 0.8), (0.004, 0.07, 0.025), bevel=0.002)
    p.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
os.makedirs(OUT, exist_ok=True)
for build in (cleat, pedestal, dock_box, piling_cap, hoop, ladder, float_drum, extinguisher):
    build()
