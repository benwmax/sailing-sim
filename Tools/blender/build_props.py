"""Visual V6: the world kit's small props, built in Blender from code (run headless by scripts/make-world-models.sh).

Vehicles for the bridge traffic: a sedan, a pickup and a semi with its trailer, as low-poly bodies with slots Paint (colour
per instance), Glass, Tyre, HeadLight, TailLight and Trailer. X forward, origin on the road between the axles.

Riprap rocks: twelve quarried limestone stones from rock_kit.py (shore loop slice 1, docs/shore-loop/rocks.md), about
1 m across so the marina's breakwater and the bridges' riprap scale them per instance. Box-projected UVs in metres and a
vertex colour that M_WorldSurface's rock pattern reads. Prints "Props: <name> <tris>".
Usage: blender -b --factory-startup -P build_props.py -- <out dir>
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rock_kit  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1]


def rock(index):
    """Shore loop slice 1 (docs/shore-loop/rocks.md): a quarried limestone riprap stone from rock_kit.build: a block of
    tilted fracture planes and corner cuts, fresh faces undulating and rough, weathered rind faces lumpy and pitted, edges
    rounded and chipped; about 49k triangles (Nanite). Vertex colour = rock_kit's open / weathered / edge (linear), which
    M_WorldSurface's rock pattern reads. Box-projected UVs in metres, as before. Indices keep their kinds: 0-5 blocks,
    6-11 slab, long, angular twice; sizes match the old kit's, so the placements keep their scale."""
    verts, quads, col, kind = rock_kit.build(index)
    bm = bmesh.new()
    bv = [bm.verts.new(Vector(v)) for v in verts.tolist()]
    bm.verts.index_update()
    for q in quads.tolist():
        bm.faces.new([bv[k] for k in q])
    bm.normal_update()
    uv = bm.loops.layers.uv.new("UVMap")
    cl = bm.loops.layers.color.new("Col")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for loop in f.loops:
            c = loop.vert.co
            loop[uv].uv = (c.y, c.z) if ax == 0 else ((c.x, c.z) if ax == 1 else (c.x, c.y))
            r, g, b = col[loop.vert.index]
            loop[cl] = (float(r), float(g), float(b), 1.0)
    name = f"SM_Rock_{index}"
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new("Rock")
    mesh.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                             mesh_smooth_type="FACE", colors_type="LINEAR")
    bpy.data.objects.remove(obj)
    print(f"Props: {name} {tris} ({kind})")


class Body:
    """Boxes and wheels into one mesh with a material slot per part."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.slots = []

    def slot(self, name):
        if name not in self.slots:
            self.slots.append(name)
        return self.slots.index(name)

    def box(self, slot, x0, x1, y, z0, z1, taper=0.0):
        """A box from x0 to x1, half width y, z0 to z1; taper pulls the top face in along x (windscreens)."""
        m = self.slot(slot)
        v = [self.bm.verts.new(c) for c in (
            (x0, -y, z0), (x1, -y, z0), (x1, y, z0), (x0, y, z0),
            (x0 + taper, -y * 0.92 if taper else -y, z1), (x1 - taper, -y * 0.92 if taper else -y, z1),
            (x1 - taper, y * 0.92 if taper else y, z1), (x0 + taper, y * 0.92 if taper else y, z1))]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            face = self.bm.faces.new([v[i] for i in f])
            face.material_index = m
            for loop in face.loops:
                c = loop.vert.co
                loop[self.uv].uv = (c.x, c.z)

    def wheel(self, x, y, r=0.33, w=0.22, sides=10):
        m = self.slot("Tyre")
        rings = []
        for side in (-0.5, 0.5):
            rings.append([self.bm.verts.new((x + r * math.cos(2 * math.pi * k / sides), y + side * w, r + r * math.sin(2 * math.pi * k / sides))) for k in range(sides)])
        for k in range(sides):
            k2 = (k + 1) % sides
            f = self.bm.faces.new((rings[0][k], rings[0][k2], rings[1][k2], rings[1][k]))
            f.material_index = m
        for ring in rings:
            f = self.bm.faces.new(ring if ring is rings[1] else list(reversed(ring)))
            f.material_index = m

    def export(self):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
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
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, self.name + ".fbx"), use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                                 mesh_smooth_type="FACE")
        bpy.data.objects.remove(obj)
        print(f"Props: {self.name} {tris}")


def lights(b, front, rear, y, z):
    """Two lamps at each end, inset from the sides: white ahead, red astern."""
    for s in (-1, 1):
        yy = s * (y - 0.25)
        b.box_at("HeadLight", front - 0.03, front + 0.02, yy, 0.18, z, z + 0.12)
        b.box_at("TailLight", rear - 0.02, rear + 0.03, yy, 0.18, z + 0.05, z + 0.17)


def box_at(self, slot, x0, x1, yc, hw, z0, z1):
    m = self.slot(slot)
    v = [self.bm.verts.new(c) for c in ((x0, yc - hw, z0), (x1, yc - hw, z0), (x1, yc + hw, z0), (x0, yc + hw, z0),
                                         (x0, yc - hw, z1), (x1, yc - hw, z1), (x1, yc + hw, z1), (x0, yc + hw, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        face = self.bm.faces.new([v[i] for i in f])
        face.material_index = m


Body.box_at = box_at


def sedan():
    b = Body("SM_Car_0")
    b.box("Paint", -2.35, 2.35, 0.9, 0.3, 0.95)
    b.box("Glass", -1.25, 1.0, 0.82, 0.95, 1.42, taper=0.45)
    b.box("Paint", -1.0, 0.75, 0.74, 1.42, 1.45)
    for x in (-1.4, 1.4):
        for y in (-0.78, 0.78):
            b.wheel(x, y)
    lights(b, 2.35, -2.35, 0.9, 0.62)
    b.export()


def pickup():
    b = Body("SM_Pickup_0")
    b.box("Paint", -2.8, 2.8, 1.0, 0.45, 1.15)
    b.box("Glass", -0.4, 1.3, 0.92, 1.15, 1.85, taper=0.35)
    b.box("Paint", -2.8, -0.45, 1.0, 1.15, 1.45)
    b.box("Tyre", -2.7, -0.5, 0.86, 1.1, 1.16)
    for x in (-1.75, 1.75):
        for y in (-0.86, 0.86):
            b.wheel(x, y, r=0.4, w=0.26)
    lights(b, 2.8, -2.8, 1.0, 0.85)
    b.export()


def semi():
    b = Body("SM_Semi_0")
    b.box("Paint", 4.3, 7.4, 1.25, 0.6, 2.2)
    b.box("Glass", 6.2, 7.4, 1.2, 2.2, 2.9, taper=0.2)
    b.box("Paint", 4.3, 6.2, 1.25, 2.2, 3.4)
    b.box("Trailer", -8.7, 4.0, 1.3, 1.25, 4.0)
    b.box("Tyre", -8.6, 3.9, 1.2, 1.05, 1.25)
    for x in (-7.6, -6.4, 5.0, 6.9):
        for y in (-1.0, 1.0):
            b.wheel(x, y, r=0.5, w=0.5)
    lights(b, 7.4, -8.7, 1.25, 0.9)
    b.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
for i in range(12):
    rock(i)
sedan()
pickup()
semi()
