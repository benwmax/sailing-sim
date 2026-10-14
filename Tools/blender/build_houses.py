"""Visual V6: building archetypes for the OSM footprints, built in Blender from code (run headless by
scripts/make-world-models.sh).

Each is a unit footprint (1 x 1, centred, X along the building's length) with the ridge at Z = 1, so an instance scaled by
(length, width, height) fits its OSM outline and height. The walls carry no windows: M_HouseWall draws them in world
space (storeys of 2.9 m, a window every 3.2 m) so they keep their size whatever the scale.
  SM_House_Gable  a ranch house: walls to 0.62, a gable roof along the length with 4% eaves, a chimney
  SM_House_Hip    a two-storey: walls to 0.66, a hip roof
  SM_House_Flat   a commercial block: walls to 0.94 and a parapet, a flat roof with rooftop units
Slots: Walls, Roof, Trim. Prints "Houses: <name> <tris>".
Usage: blender -b --factory-startup -P build_houses.py -- <out dir>
"""
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

    def face(self, pts, slot):
        f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        f.material_index = self.slot(slot)
        for loop in f.loops:
            c = loop.vert.co
            loop[self.uv].uv = (c.x + c.y, c.z)
        return f

    def box(self, x0, x1, y0, y1, z0, z1, slot, top=True, bottom=False):
        P = lambda x, y, z: (x, y, z)
        if top:
            self.face([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], slot)
        if bottom:
            self.face([P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0)], slot)
        self.face([P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)], slot)
        self.face([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], slot)
        self.face([P(x1, y1, z0), P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1)], slot)
        self.face([P(x0, y1, z0), P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1)], slot)

    def export(self):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts[:], dist=1e-5)
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
        print(f"Houses: {self.name} {tris}")


def gable():
    p = Part("SM_House_Gable")
    e, o = 0.62, 0.04
    p.box(-0.5, 0.5, -0.5, 0.5, -0.3, e, "Walls", top=False)
    # Roof planes with eaves, and the gable ends.
    p.face([(-0.5 - o, -0.5 - o, e - 0.02), (0.5 + o, -0.5 - o, e - 0.02), (0.5 + o, 0.0, 1.0), (-0.5 - o, 0.0, 1.0)], "Roof")
    p.face([(0.5 + o, 0.5 + o, e - 0.02), (-0.5 - o, 0.5 + o, e - 0.02), (-0.5 - o, 0.0, 1.0), (0.5 + o, 0.0, 1.0)], "Roof")
    p.face([(-0.5, -0.5, e), (-0.5, 0.0, 1.0 - 0.02), (-0.5, 0.5, e)], "Walls")
    p.face([(0.5, 0.5, e), (0.5, 0.0, 1.0 - 0.02), (0.5, -0.5, e)], "Walls")
    # Fascia boards along the eaves.
    for s in (-1, 1):
        p.box(-0.5 - o, 0.5 + o, s * (0.5 + o) - 0.005, s * (0.5 + o) + 0.005, e - 0.06, e - 0.02, "Trim")
    p.box(0.28, 0.34, 0.12, 0.2, 0.7, 1.0, "Trim")                      # chimney (to 1.0: M_HouseWall assumes -0.3 .. 1.0)
    p.export()


def hip():
    p = Part("SM_House_Hip")
    e, o = 0.66, 0.04
    p.box(-0.5, 0.5, -0.5, 0.5, -0.3, e, "Walls", top=False)
    r = 0.22
    a, b, c, d = (-0.5 - o, -0.5 - o, e - 0.02), (0.5 + o, -0.5 - o, e - 0.02), (0.5 + o, 0.5 + o, e - 0.02), (-0.5 - o, 0.5 + o, e - 0.02)
    r0, r1 = (-r, 0.0, 1.0), (r, 0.0, 1.0)
    p.face([a, b, r1, r0], "Roof")
    p.face([c, d, r0, r1], "Roof")
    p.face([d, a, r0], "Roof")
    p.face([b, c, r1], "Roof")
    for s in (-1, 1):
        p.box(-0.5 - o, 0.5 + o, s * (0.5 + o) - 0.005, s * (0.5 + o) + 0.005, e - 0.06, e - 0.02, "Trim")
    p.export()


def flat():
    p = Part("SM_House_Flat")
    p.box(-0.5, 0.5, -0.5, 0.5, -0.3, 0.94, "Walls", top=False)
    p.face([(-0.49, -0.49, 0.92), (0.49, -0.49, 0.92), (0.49, 0.49, 0.92), (-0.49, 0.49, 0.92)], "Roof")
    for x0, x1, y0, y1 in ((-0.5, 0.5, -0.5, -0.48), (-0.5, 0.5, 0.48, 0.5), (-0.5, -0.48, -0.48, 0.48), (0.48, 0.5, -0.48, 0.48)):
        p.box(x0, x1, y0, y1, 0.9, 1.0, "Trim")                            # parapet
    for x, y in ((-0.2, 0.1), (0.15, -0.15)):
        p.box(x - 0.06, x + 0.06, y - 0.05, y + 0.05, 0.92, 0.99, "Trim")  # rooftop units
    p.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
gable()
hip()
flat()
