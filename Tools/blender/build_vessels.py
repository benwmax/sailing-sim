"""Visual V6: the traffic's power vessels, built in Blender from code (run headless by scripts/make-world-models.sh).

Lofted hulls (stations of a section shape: V-bottomed for the runabout, round-bilged for the trawlers, box-bilged for the
barges and the ship, with a bulb), deck, superstructure and fittings, at the sizes and fixture positions the game's
navigation lights use (APowerVesselActor). Origin amidships on the waterline, X forward, Z up, metres.
  SM_Vessel_Runabout   21 ft center console with its outboard and the all-round light pole aft
  SM_Vessel_Shrimper   70 ft Gulf shrimp trawler: wheelhouse forward, mast, outrigger booms swung out, try net
  SM_Vessel_Committee  36 ft trawler yacht (the race committee boat)
  SM_Vessel_Towboat    85 ft river towboat with push knees and a three-deck house
  SM_Barge_Hopper      a jumbo hopper barge (one hull; the tow is two of them)
  SM_Vessel_Container  a 230 m feeder container ship: bulbous bow, flare, house and funnel aft, hatch coamings
  SM_Container_40      a 40 ft container (stacked on the ship per instance, colour per instance)
Slots map to MI_World_<slot> (scripts/make_materials.py WORLD_LIBRARY). Prints "Vessels: <name> <tris>".
Usage: blender -b --factory-startup -P build_vessels.py -- <out dir>
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
        try:
            f = self.bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = self.slot(slot)
        n = f.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for loop in f.loops:
            c = loop.vert.co
            loop[self.uv].uv = (c.y, c.z) if ax == 0 else ((c.x, c.z) if ax == 1 else (c.x, c.y))
        return f

    def box(self, c, e, slot, yaw=0.0):
        x, y, z = c
        ex, ey, ez = e
        cy, sy = math.cos(yaw), math.sin(yaw)
        pts = []
        for sx_, sy_, sz_ in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
            lx, ly = sx_ * ex, sy_ * ey
            pts.append(self.bm.verts.new((x + lx * cy - ly * sy, y + lx * sy + ly * cy, z + sz_ * ez)))
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.face([pts[i] for i in f], slot)

    def tube(self, a, b, r, slot, sides=8):
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized()
        u = d.orthogonal().normalized()
        v = d.cross(u)
        ring = lambda c: [self.bm.verts.new(c + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides)]
        ra, rb = ring(a), ring(b)
        for k in range(sides):
            k2 = (k + 1) % sides
            self.face((ra[k], ra[k2], rb[k2], rb[k]), slot)
        self.face(list(reversed(ra)), slot)
        self.face(rb, slot)

    def cone(self, base, tip, r, slot, sides=10):
        base, tip = Vector(base), Vector(tip)
        d = (tip - base).normalized()
        u = d.orthogonal().normalized()
        v = d.cross(u)
        ring = [self.bm.verts.new(base + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides)]
        t = self.bm.verts.new(tip)
        for k in range(sides):
            self.face((ring[k], ring[(k + 1) % sides], t), slot)
        self.face(list(reversed(ring)), slot)

    def hull(self, L, B, sheer_aft, sheer_bow, T, kind, top="Gelcoat", bottom="Antifouling", boot=0.05, transom=0.85,
             stations=28, rows=10, bow_rise=0.85, bulb=False):
        """A closed hull from stations: deck edge at the sheer, keel at -T, sections by kind ('v', 'round', 'box')."""
        grid = []
        for i in range(stations + 1):
            u = i / stations                          # 0 transom .. 1 stem
            x = -L / 2 + u * L
            if u < 0.55:
                half = B / 2 * (transom + (1 - transom) * math.sin(min(u / 0.55, 1) * math.pi / 2))
            else:
                w = (u - 0.55) / 0.45
                half = B / 2 * max(0.0, 1 - w ** (2.4 if kind == "box" else 1.7))
            half = max(half, 0.02)
            sheer = sheer_aft + (sheer_bow - sheer_aft) * u ** 2.2
            keel = -T if u < bow_rise else -T * max(0.05, 1 - (u - bow_rise) / (1 - bow_rise))
            if kind == "v":
                keel = -T * (0.55 + 0.45 * min(1.0, u / 0.7)) if u < bow_rise else keel
            col = []
            for j in range(rows + 1):
                t = j / rows                          # 0 keel .. 1 deck edge
                z = keel + t * (sheer - keel)
                if kind == "v":
                    y = half * min(1.0, t * 1.6) ** 0.9
                elif kind == "box":
                    y = half * min(1.0, (t * 6.0) ** 0.5) if t < 0.17 else half
                else:
                    y = half * math.sin(min(t * 1.25, 1.0) * math.pi / 2) ** 0.7
                # Flare: topsides lean out a little above the waterline toward the bow.
                if z > 0:
                    y *= 1 + 0.06 * u * min(z / max(sheer, 0.1), 1.0)
                col.append((x, y, z))
            grid.append(col)
        sides = []
        for s in (1, -1):
            vs = [[self.bm.verts.new((x, s * y, z)) for (x, y, z) in col] for col in grid]
            sides.append(vs)
            for i in range(stations):
                for j in range(rows):
                    q = (vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1])
                    if s < 0:
                        q = tuple(reversed(q))
                    zc = (grid[i][j][2] + grid[i][j + 1][2]) / 2
                    self.face(q, bottom if zc < boot else top)
        # Deck and transom.
        P, S = sides
        for i in range(stations):
            self.face((P[i][rows], P[i + 1][rows], S[i + 1][rows], S[i][rows]), "Deck")
        tr = [P[0][j] for j in range(rows + 1)] + [S[0][j] for j in reversed(range(rows + 1))]
        self.face(list(reversed(tr)), top)
        if bulb:
            # A bulbous bow: an ellipsoid at the forefoot.
            c = Vector((L / 2 - 2.0, 0.0, -T * 0.55))
            r = Vector((9.0, 3.2, T * 0.3))
            lat, lon = 8, 12
            ring = []
            for a in range(1, lat):
                th = math.pi * a / lat
                ring.append([self.bm.verts.new(c + Vector((r.x * math.cos(th), r.y * math.sin(th) * math.cos(2 * math.pi * k / lon), r.z * math.sin(th) * math.sin(2 * math.pi * k / lon)))) for k in range(lon)])
            front, back = self.bm.verts.new(c + Vector((r.x, 0, 0))), self.bm.verts.new(c - Vector((r.x, 0, 0)))
            for k in range(lon):
                k2 = (k + 1) % lon
                self.face((front, ring[0][k2], ring[0][k]), bottom)
                self.face((back, ring[-1][k], ring[-1][k2]), bottom)
                for a in range(len(ring) - 1):
                    self.face((ring[a][k], ring[a][k2], ring[a + 1][k2], ring[a + 1][k]), bottom)

    def export(self):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts[:], dist=0.0005)
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
        mod = obj.modifiers.new("split", "EDGE_SPLIT")
        mod.split_angle = math.radians(40)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier="split")
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, self.name + ".fbx"), use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                                 mesh_smooth_type="FACE")
        bpy.data.objects.remove(obj)
        print(f"Vessels: {self.name} {tris}")


def runabout():
    p = Part("SM_Vessel_Runabout")
    p.hull(6.4, 2.4, 0.7, 0.95, 0.38, "v", top="Gelcoat", bottom="Gelcoat", boot=-0.5, transom=0.92, bow_rise=0.78)
    p.box((-0.0, 0.0, 0.05), (2.9, 1.08, 0.04), "Deck")                       # cockpit sole
    p.box((0.4, 0.0, 0.55), (0.45, 0.4, 0.5), "Gelcoat")                       # console
    p.box((0.75, 0.0, 1.18), (0.05, 0.42, 0.2), "Glass", )                      # windscreen
    p.box((-0.7, 0.0, 0.42), (0.35, 0.45, 0.3), "Cushion")                      # leaning post
    p.box((-1.9, 0.0, 0.45), (0.35, 1.0, 0.25), "Cushion")                      # stern bench
    p.box((-3.45, 0.0, 0.45), (0.25, 0.22, 0.4), "Dark")                        # outboard cowling
    p.box((-3.5, 0.0, -0.15), (0.08, 0.06, 0.35), "Dark")                       # leg
    p.tube((-2.6, 0.0, 0.7), (-2.6, 0.0, 2.35), 0.025, "Steel")                 # all-round light pole
    for s in (1, -1):
        p.tube((2.4, s * 0.62, 0.95), (0.3, s * 1.1, 0.95), 0.015, "Steel")     # bow rail
    p.export()


def trawler(name, L, B, mast_x, mast_h, committee=False):
    p = Part(name)
    p.hull(L, B, 1.5 if not committee else 1.3, 2.6 if not committee else 2.0, 1.9 if not committee else 1.1, "round",
           top="Gelcoat" if committee else "TrimGreen", bottom="Antifouling", boot=0.15, transom=0.8)
    # Bulwark rail and the white house.
    hx = L * 0.18
    p.box((hx, 0.0, 2.6 + (0.5 if committee else 0.0)), (L * 0.11, B * 0.3, 1.1), "Gelcoat")
    p.box((hx + L * 0.09, 0.0, 3.25 + (0.5 if committee else 0.0)), (0.05, B * 0.28, 0.35), "Glass")
    for s in (1, -1):
        p.box((hx, s * B * 0.3, 3.25 + (0.5 if committee else 0.0)), (L * 0.08, 0.04, 0.3), "Glass")
    p.box((hx - 0.2, 0.0, 3.8 + (0.5 if committee else 0.0)), (L * 0.13, B * 0.33, 0.08), "Gelcoat")
    p.tube((mast_x, 0.0, 1.6), (mast_x, 0.0, 1.6 + mast_h), 0.12 if not committee else 0.06, "Steel")
    if committee:
        p.box((-L * 0.15, 0.0, 2.2), (L * 0.12, B * 0.28, 0.6), "Gelcoat")      # flybridge
        p.tube((L * 0.4, 0.0, 2.0), (L * 0.4, 0.0, 4.0), 0.03, "Steel")
        p.export()
        return
    # Outrigger booms swung out at 60 degrees, stays, and the nets' cables astern to their doors and bags.
    for s in (1, -1):
        tip = (mast_x, s * 9.2, 3.0 + 10.0 * math.cos(math.radians(60)) * 0.0 + 1.6)
        p.tube((mast_x, s * 0.2, 3.0), (mast_x - 0.5, s * 9.0, 5.8), 0.1, "Steel")
        p.tube((mast_x, 0.0, 1.6 + mast_h), (mast_x - 0.5, s * 9.0, 5.8), 0.015, "Steel")
        p.tube((mast_x - 0.5, s * 9.0, 5.8), (-12.0, s * 9.5, 0.2), 0.02, "Dark")
        p.box((-12.5, s * 9.6, -0.2), (0.9, 0.08, 0.5), "Dark")                  # trawl door at the surface
        p.cone((-13.0, s * 9.0, -0.6), (-24.0, s * 6.0, -1.5), 1.2, "Net")      # the net's bag
    p.box((-L * 0.3, 0.0, 2.1), (1.2, 1.0, 0.5), "Dark")                         # winch
    p.export()


def towboat():
    p = Part("SM_Vessel_Towboat")
    p.hull(26.0, 10.0, 2.0, 2.4, 2.7, "box", top="Gelcoat", bottom="Barge", boot=0.0, transom=0.95, bow_rise=0.97)
    # Push knees at the bow.
    for s in (1, -1):
        p.box((13.2, s * 3.2, 2.6), (0.3, 0.25, 1.6), "Dark")
    p.box((-0.5, 0.0, 3.6), (8.0, 4.4, 1.6), "Gelcoat")                          # main deck house
    p.box((-0.5, 0.0, 6.4), (5.5, 4.0, 1.2), "Gelcoat")
    p.box((-0.5, 0.0, 9.2), (3.0, 3.5, 1.6), "Pilothouse")
    p.box((2.45, 0.0, 9.5), (0.06, 3.3, 0.6), "Glass")
    p.tube((-1.0, 0.0, 10.8), (-1.0, 0.0, 16.0), 0.15, "Steel")
    for s in (1, -1):
        p.tube((-6.0, s * 1.5, 4.0), (-6.0, s * 1.5, 11.5), 0.45, "Funnel")       # stacks
    p.export()
    b = Part("SM_Barge_Hopper")
    b.hull(59.5, 10.7, 3.6, 3.8, 2.7, "box", top="Barge", bottom="Barge", boot=-10, transom=0.97, bow_rise=0.92)
    b.box((0.0, 0.0, 4.2), (26.0, 4.6, 0.6), "Barge")                            # hopper coaming
    b.box((0.0, 0.0, 4.75), (26.0, 4.2, 0.05), "Cargo")                          # the load (gravel)
    b.export()


def ship():
    p = Part("SM_Vessel_Container")
    L, B = 230.0, 32.0
    p.hull(L, B, 11.0, 14.0, 10.5, "box", top="ShipHull", bottom="Antifouling", boot=0.4, transom=0.8, stations=40, rows=12, bow_rise=0.9, bulb=True)
    # House and funnel aft, bridge wings, mast; hatch coamings forward.
    p.box((-90.0, 0.0, 19.0), (9.0, B * 0.42, 8.0), "Gelcoat")
    p.box((-92.0, 0.0, 27.5), (5.0, B * 0.51, 1.5), "Gelcoat")
    p.box((-87.1, 0.0, 27.5), (0.05, B * 0.5, 0.7), "Glass")
    p.box((-102.0, 0.0, 30.0), (4.0, 3.5, 6.0), "Funnel")
    p.tube((-90.0, 0.0, 29.0), (-90.0, 0.0, 42.5), 0.4, "Steel")
    p.tube((100.0, 0.0, 14.0), (100.0, 0.0, 31.5), 0.5, "Steel")
    for i in range(14):
        x = -74.0 + i * 12.8
        p.box((x, 0.0, 11.9), (6.1, B * 0.43, 0.9), "ShipHull")
    p.box((108.0, 0.0, 15.5), (3.0, B * 0.3, 1.5), "ShipHull")                   # forecastle
    p.export()
    c = Part("SM_Container_40")
    c.box((0.0, 0.0, 1.295), (6.06, 1.22, 1.295), "ContainerPaint")
    c.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
runabout()
trawler("SM_Vessel_Shrimper", 21.0, 6.5, 0.42, 11.0)
trawler("SM_Vessel_Committee", 11.0, 3.8, 0.0, 6.0, committee=True)
towboat()
ship()
