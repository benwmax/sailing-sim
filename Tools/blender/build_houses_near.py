"""Graphics G2: houses near the water (within 400 m), modelled at real size so their details keep their proportions:
framed windows with glass and sills, doors, a garage door, eaves with fascia and soffit, gutters, a chimney, a
foundation, porches and decks. ALakeTerrainActor picks the closest size for each OSM footprint and scales it by no more
than about 20% each way; the far houses keep build_houses.py's unit archetypes.

  SM_HouseNear_RanchS   13 x 9 m, one storey, gable roof, attached garage
  SM_HouseNear_RanchM   18 x 11 m, one storey, hip roof, garage, front porch
  SM_HouseNear_TwoS     12 x 9 m, two storeys, gable roof
  SM_HouseNear_TwoL     17 x 12 m, two storeys, hip roof, porch with columns, garage
  SM_HouseNear_Cottage  10 x 8 m, lake cottage, steep gable, a deck along the lake side
  SM_HouseNear_Modern   15 x 10 m, flat roof with a parapet, tall windows, a canopy
Origin at the footprint's centre on the ground, X along the length, the front (door) on -Y. Metres.
  SM_HouseNear_Dock, SM_HouseNear_Boathouse  a private dock (and one with a boathouse) from the bank out over the water
Slots: Walls (M_HouseWall, which skips its painted windows on these), Roof (M_HouseRoof), Trim, Glass, Door, Concrete,
Decking, Wood, Steel. Prints "HousesNear: <name> <tris> <length> <width> <height>".
    blender -b --factory-startup -P Tools/blender/build_houses_near.py -- <out dir>
"""
import math
import os
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index("--") + 1]
STOREY = 2.9


class Part:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.slots = []
        self.wants = []                           # (face, the way it must face): loose panes the normal pass can't orient

    def slot(self, name):
        if name not in self.slots:
            self.slots.append(name)
        return self.slots.index(name)

    def face(self, pts, slot, want=None):
        f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        if want is not None:
            self.wants.append((f, want))
        f.material_index = self.slot(slot)
        for loop in f.loops:
            c = loop.vert.co
            loop[self.uv].uv = (c.x + c.y, c.z)
        return f

    def box(self, x0, x1, y0, y1, z0, z1, slot, top=True, bottom=False):
        if top:
            self.face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], slot)
        if bottom:
            self.face([(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], slot)
        self.face([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], slot)
        self.face([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], slot)
        self.face([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], slot)
        self.face([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], slot)

    def export(self, L, W, H):
        # Weld coincident corners first: boxes become closed shells and roofs one sheet, so the normals turn outward.
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts[:], dist=1e-4)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        for f, want in self.wants:
            if f.is_valid:
                f.normal_update()
                if f.normal.dot(want) < 0:
                    f.normal_flip()
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
        print(f"HousesNear: {self.name} {tris} {L} {W} {H:.1f}")


def window(p, axis, at, side, z0, w=1.0, h=1.35, depth=0.0):
    """A framed window on a wall: axis 'x' = on a long wall (y = side), 'y' = on an end wall (x = side). The glass sits
    6 cm in front of the wall plane (the wall is a closed shell), white frame and sill around it."""
    s = 1 if side > 0 else -1
    t, f = 0.07, 0.05                           # frame width, frame depth
    if axis == "x":
        for y in (side + s * 0.06, side + s * 0.05):                       # both faces: a loose pane has no "outward"
            q = [(at - w / 2, y, z0), (at + w / 2, y, z0), (at + w / 2, y, z0 + h), (at - w / 2, y, z0 + h)]
            outer = y == side + s * 0.06
            p.face(q, "Glass", want=(0.0, -1.0 if (s < 0) == outer else 1.0, 0.0))
        y0, y1 = sorted((side, side + s * (0.06 + f)))
        p.box(at - w / 2 - t, at - w / 2, y0, y1, z0, z0 + h, "Trim")
        p.box(at + w / 2, at + w / 2 + t, y0, y1, z0, z0 + h, "Trim")
        p.box(at - w / 2 - t, at + w / 2 + t, y0, y1, z0 + h, z0 + h + t, "Trim")
        p.box(at - w / 2, at + w / 2, y0, y1, z0 + h * 0.5 - 0.02, z0 + h * 0.5 + 0.02, "Trim")      # meeting rail
        sy0, sy1 = sorted((side, side + s * 0.16))
        p.box(at - w / 2 - 0.1, at + w / 2 + 0.1, sy0, sy1, z0 - 0.06, z0, "Trim")               # sill
    else:
        for x in (side + s * 0.06, side + s * 0.05):
            q = [(x, at - w / 2, z0), (x, at + w / 2, z0), (x, at + w / 2, z0 + h), (x, at - w / 2, z0 + h)]
            outer = x == side + s * 0.06
            p.face(q, "Glass", want=(s * 1.0 if outer else -s * 1.0, 0.0, 0.0))
        x0, x1 = sorted((side, side + s * (0.06 + f)))
        p.box(x0, x1, at - w / 2 - t, at - w / 2, z0, z0 + h, "Trim")
        p.box(x0, x1, at + w / 2, at + w / 2 + t, z0, z0 + h, "Trim")
        p.box(x0, x1, at - w / 2 - t, at + w / 2 + t, z0 + h, z0 + h + t, "Trim")
        sx0, sx1 = sorted((side, side + s * 0.16))
        p.box(sx0, sx1, at - w / 2 - 0.1, at + w / 2 + 0.1, z0 - 0.06, z0, "Trim")


def door(p, at, y, w=1.0, h=2.1):
    p.face([(at - w / 2, y - 0.04, 0.3), (at + w / 2, y - 0.04, 0.3), (at + w / 2, y - 0.04, 0.3 + h), (at - w / 2, y - 0.04, 0.3 + h)][::-1], "Door")
    p.box(at - w / 2 - 0.09, at - w / 2, y - 0.1, y, 0.3, 0.3 + h + 0.09, "Trim")
    p.box(at + w / 2, at + w / 2 + 0.09, y - 0.1, y, 0.3, 0.3 + h + 0.09, "Trim")
    p.box(at - w / 2 - 0.09, at + w / 2 + 0.09, y - 0.1, y, 0.3 + h, 0.3 + h + 0.09, "Trim")
    p.box(at - 0.8, at + 0.8, y - 1.0, y, 0.0, 0.25, "Concrete")                                  # step


def garage(p, at, y, w=4.9, h=2.2):
    p.face([(at - w / 2, y - 0.05, 0.05), (at + w / 2, y - 0.05, 0.05), (at + w / 2, y - 0.05, 0.05 + h), (at - w / 2, y - 0.05, 0.05 + h)][::-1], "Trim")
    for k in range(1, 4):                                                                          # panel grooves
        z = 0.05 + h * k / 4
        p.box(at - w / 2, at + w / 2, y - 0.07, y - 0.05, z - 0.015, z + 0.015, "Door")
    p.box(at - w / 2 - 0.12, at + w / 2 + 0.12, y - 0.12, y, 0.05 + h, 0.05 + h + 0.12, "Trim")
    p.box(at - w / 2, at + w / 2, y - 6.0, y, -0.05, 0.02, "Concrete")                            # driveway apron


def walls_and_windows(p, L, W, storeys, front_skip=(), win_w=1.0):
    eave = 0.3 + storeys * STOREY
    p.box(-L / 2 - 0.08, L / 2 + 0.08, -W / 2 - 0.08, W / 2 + 0.08, -0.3, 0.3, "Concrete")         # foundation
    p.box(-L / 2, L / 2, -W / 2, W / 2, 0.3, eave, "Walls", top=False)
    for k in range(storeys):
        z0 = 0.3 + k * STOREY + 0.95
        n = max(1, int((L - 2.0) / 3.2))
        for i in range(n):
            x = -L / 2 + (i + 0.5) * L / n
            if k == 0 and any(abs(x - a) < b for a, b in front_skip):
                pass
            else:
                window(p, "x", x, -W / 2, z0, w=win_w)
            window(p, "x", x, W / 2, z0, w=win_w)
        m = max(1, int((W - 2.0) / 3.4))
        for j in range(m):
            yy = -W / 2 + (j + 0.5) * W / m
            window(p, "y", yy, -L / 2, z0, w=0.9)
            window(p, "y", yy, L / 2, z0, w=0.9)
    return eave


def eaves_trim(p, L, W, eave, o):
    for s in (-1, 1):
        y = s * (W / 2 + o)
        y0, y1 = sorted((y, y + s * 0.04))
        p.box(-L / 2 - o, L / 2 + o, y0, y1, eave - 0.22, eave + 0.02, "Trim")                     # fascia
        g0, g1 = sorted((y + s * 0.04, y + s * 0.16))
        p.box(-L / 2 - o, L / 2 + o, g0, g1, eave - 0.16, eave - 0.02, "Trim")                     # gutter
        p.face([(-L / 2 - o, y, eave - 0.22), (L / 2 + o, y, eave - 0.22), (L / 2, s * W / 2, eave - 0.22), (-L / 2, s * W / 2, eave - 0.22)][::(1 if s < 0 else -1)], "Trim")  # soffit
    for x in (-L / 2 + 0.2, L / 2 - 0.2):                                                          # downspouts
        for s in (-1, 1):
            y0, y1 = sorted((s * (W / 2 + 0.02), s * (W / 2 + 0.12)))
            p.box(x - 0.05, x + 0.05, y0, y1, 0.0, eave - 0.1, "Trim")


def gable_roof(p, L, W, eave, pitch=0.42, o=0.5, gable_slot="Walls"):
    ridge = eave + (W / 2 + o) * pitch
    for s in (-1, 1):
        p.face([(-L / 2 - o, s * (W / 2 + o), eave - 0.02), (L / 2 + o, s * (W / 2 + o), eave - 0.02), (L / 2 + o, 0.0, ridge), (-L / 2 - o, 0.0, ridge)][::(1 if s < 0 else -1)], "Roof")
        p.face([(s * L / 2, -W / 2, eave), (s * L / 2, 0.0, eave + W / 2 * pitch), (s * L / 2, W / 2, eave)][::(1 if s < 0 else -1)], gable_slot)
        p.box(s * (L / 2 + o) - 0.03, s * (L / 2 + o) + 0.03, -W / 2 - o, W / 2 + o, eave - 0.2, eave, "Trim")   # rake
    p.box(-L / 2 - o, L / 2 + o, -0.06, 0.06, ridge - 0.02, ridge + 0.06, "Roof")                 # ridge cap
    eaves_trim(p, L, W, eave, o)
    return ridge


def hip_roof(p, L, W, eave, pitch=0.4, o=0.5):
    h = (W / 2 + o) * pitch
    r = max(0.0, L / 2 - W / 2)
    a, b, c, d = (-L / 2 - o, -W / 2 - o, eave - 0.02), (L / 2 + o, -W / 2 - o, eave - 0.02), (L / 2 + o, W / 2 + o, eave - 0.02), (-L / 2 - o, W / 2 + o, eave - 0.02)
    r0, r1 = (-r, 0.0, eave + h), (r, 0.0, eave + h)
    p.face([a, b, r1, r0], "Roof")
    p.face([c, d, r0, r1], "Roof")
    p.face([d, a, r0], "Roof")
    p.face([b, c, r1], "Roof")
    eaves_trim(p, L, W, eave, o)
    return eave + h


def chimney(p, x, y, top):
    p.box(x - 0.55, x + 0.55, y - 0.35, y + 0.35, 2.0, top + 0.9, "Walls")
    p.box(x - 0.62, x + 0.62, y - 0.42, y + 0.42, top + 0.9, top + 1.0, "Concrete")


def porch(p, x0, x1, y_front, depth, eave, roof_pitch=0.25):
    p.box(x0, x1, y_front - depth, y_front, 0.0, 0.3, "Concrete")
    n = max(2, int((x1 - x0) / 2.6) + 1)
    for i in range(n):
        x = x0 + 0.2 + (x1 - x0 - 0.4) * i / (n - 1)
        p.box(x - 0.1, x + 0.1, y_front - depth + 0.1, y_front - depth + 0.3, 0.3, eave - 0.1, "Trim")
    zr = eave + depth * roof_pitch
    p.face([(x0 - 0.2, y_front - depth - 0.3, eave - 0.1), (x1 + 0.2, y_front - depth - 0.3, eave - 0.1), (x1 + 0.2, y_front, zr), (x0 - 0.2, y_front, zr)], "Roof")
    p.box(x0 - 0.2, x1 + 0.2, y_front - depth - 0.34, y_front - depth - 0.3, eave - 0.3, eave - 0.1, "Trim")


def deck(p, x0, x1, y0, y1, z):
    p.box(x0, x1, y0, y1, z - 0.08, z, "Decking")
    for x in (x0 + 0.1, (x0 + x1) / 2, x1 - 0.1):
        for y in (y0 + 0.1, y1 - 0.1):
            p.box(x - 0.08, x + 0.08, y - 0.08, y + 0.08, -0.2, z - 0.08, "Decking")
    for (a0, a1, b0, b1) in ((x0, x1, y1 - 0.05, y1), (x0, x0 + 0.05, y0, y1), (x1 - 0.05, x1, y0, y1)):
        p.box(a0, a1, b0, b1, z + 0.9, z + 0.96, "Decking")                                      # rail
        n = max(2, int(max(a1 - a0, b1 - b0) / 1.6) + 1)
        for i in range(n):
            t = i / (n - 1)
            x = a0 + (a1 - a0) * t if a1 - a0 > 0.1 else (a0 + a1) / 2
            y = b0 + (b1 - b0) * t if b1 - b0 > 0.1 else (b0 + b1) / 2
            p.box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, z, z + 0.9, "Decking")


def ranch_s():
    L, W = 13.0, 9.0
    p = Part("SM_HouseNear_RanchS")
    eave = walls_and_windows(p, L, W, 1, front_skip=((-0.5, 0.9), (3.6, 2.8)))
    door(p, -0.5, -W / 2)
    garage(p, 3.6, -W / 2)
    top = gable_roof(p, L, W, eave)
    chimney(p, -3.5, 1.5, top)
    p.export(L, W, top)


def ranch_m():
    L, W = 18.0, 11.0
    p = Part("SM_HouseNear_RanchM")
    eave = walls_and_windows(p, L, W, 1, front_skip=((-2.0, 0.9), (5.8, 2.8)))
    door(p, -2.0, -W / 2)
    garage(p, 5.8, -W / 2)
    porch(p, -5.0, 1.0, -W / 2, 2.0, eave)
    top = hip_roof(p, L, W, eave)
    p.export(L, W, top)


def two_s():
    L, W = 12.0, 9.0
    p = Part("SM_HouseNear_TwoS")
    eave = walls_and_windows(p, L, W, 2, front_skip=((0.0, 0.9),))
    door(p, 0.0, -W / 2)
    top = gable_roof(p, L, W, eave, pitch=0.5)
    chimney(p, L / 2 - 1.2, 0.0, top)
    p.export(L, W, top)


def two_l():
    L, W = 17.0, 12.0
    p = Part("SM_HouseNear_TwoL")
    eave = walls_and_windows(p, L, W, 2, front_skip=((-1.5, 0.9), (5.3, 2.8)))
    door(p, -1.5, -W / 2)
    garage(p, 5.3, -W / 2)
    porch(p, -6.5, 2.5, -W / 2, 2.4, 0.3 + STOREY)
    top = hip_roof(p, L, W, eave)
    p.export(L, W, top)


def cottage():
    L, W = 10.0, 8.0
    p = Part("SM_HouseNear_Cottage")
    eave = walls_and_windows(p, L, W, 1, front_skip=((1.5, 0.9),))
    door(p, 1.5, -W / 2)
    top = gable_roof(p, L, W, eave, pitch=0.75, o=0.4)
    deck(p, -L / 2 - 0.5, L / 2 + 0.5, W / 2, W / 2 + 3.5, 0.6)          # the lake side
    chimney(p, -L / 2 + 0.8, -1.0, top)
    p.export(L, W, top)


def modern():
    L, W = 15.0, 10.0
    p = Part("SM_HouseNear_Modern")
    eave = walls_and_windows(p, L, W, 2, front_skip=((-3.0, 1.2),), win_w=2.2)
    door(p, -3.0, -W / 2, w=1.2, h=2.4)
    p.face([(-L / 2, -W / 2, eave), (L / 2, -W / 2, eave), (L / 2, W / 2, eave), (-L / 2, W / 2, eave)], "Roof")
    for (x0, x1, y0, y1) in ((-L / 2, L / 2, -W / 2, -W / 2 + 0.2), (-L / 2, L / 2, W / 2 - 0.2, W / 2), (-L / 2, -L / 2 + 0.2, -W / 2, W / 2), (L / 2 - 0.2, L / 2, -W / 2, W / 2)):
        p.box(x0, x1, y0, y1, eave, eave + 0.5, "Trim")                                          # parapet
    p.box(-5.0, -1.0, -W / 2 - 1.8, -W / 2, 0.3 + STOREY - 0.15, 0.3 + STOREY, "Trim")          # canopy
    p.box(2.0, 4.0, -1.5, 0.5, eave, eave + 1.0, "Trim")                                          # rooftop unit
    p.export(L, W, eave + 0.5)


def dock(name, boathouse):
    """A lakefront house's private dock: a walkway from the bank out over the water (+X), a platform at its end, piles to
    the bed; the boathouse variant roofs the platform over a slip. Origin at the bank, deck 0.6 m above the water."""
    p = Part(name)
    z = 0.6
    p.box(0.0, 14.0, -0.6, 0.6, z - 0.08, z, "Decking")
    for x in (0.5, 4.5, 8.5, 12.5):
        for y in (-0.55, 0.55):
            p.box(x - 0.1, x + 0.1, y - 0.1, y + 0.1, -2.5, z - 0.08, "Wood")
    if boathouse:
        for y0, y1 in ((-4.0, -2.8), (2.8, 4.0)):                       # two finger walkways either side of the slip
            p.box(14.0, 22.0, y0, y1, z - 0.08, z, "Decking")
        p.box(14.0, 15.2, -4.0, 4.0, z - 0.08, z, "Decking")
        for x in (14.2, 18.0, 21.8):
            for y in (-3.9, 3.9):
                p.box(x - 0.12, x + 0.12, y - 0.12, y + 0.12, -2.5, z + 3.0, "Wood")
        for s in (-1, 1):                                               # a low-pitched metal roof over the slip
            p.face([(13.6, s * 4.6, z + 3.0), (22.4, s * 4.6, z + 3.0), (22.4, 0.0, z + 3.9), (13.6, 0.0, z + 3.9)][::(1 if s < 0 else -1)], "Steel")
            p.box(13.6, 22.4, s * 4.6 - 0.03, s * 4.6 + 0.03, z + 2.85, z + 3.0, "Trim")
    else:
        p.box(14.0, 18.0, -3.0, 3.0, z - 0.08, z, "Decking")
        for x in (14.2, 17.8):
            for y in (-2.9, 2.9):
                p.box(x - 0.1, x + 0.1, y - 0.1, y + 0.1, -2.5, z + 0.9, "Wood")
        p.box(14.0, 18.0, -3.0, -2.95, z + 0.85, z + 0.92, "Decking")
        p.box(14.0, 18.0, 2.95, 3.0, z + 0.85, z + 0.92, "Decking")
    p.export(22.0 if boathouse else 18.0, 8.0 if boathouse else 6.0, 4.5 if boathouse else 1.5)


bpy.ops.wm.read_factory_settings(use_empty=True)
for build in (ranch_s, ranch_m, two_s, two_l, cottage, modern):
    build()
dock("SM_HouseNear_Dock", False)
dock("SM_HouseNear_Boathouse", True)
