"""Visual V6: the traffic's power vessels, built in Blender from code (run headless by scripts/make-world-models.sh).

Lofted hulls (stations of a section shape: V-bottomed for the runabout, round-bilged for the trawlers, box-bilged for the
barges and the ship, with a bulb), deck, superstructure and fittings, at the sizes and fixture positions the game's
navigation lights use (APowerVesselActor). Origin amidships on the waterline, X forward, Z up, metres.
  SM_Vessel_Runabout   21 ft center console with its outboard and the all-round light pole aft
  SM_Vessel_Shrimper   70 ft Gulf shrimp trawler: wheelhouse forward, mast, outrigger booms swung out, try net
  SM_Vessel_Committee  36 ft trawler yacht (the race committee boat; also moored in the coast's marinas)
  SM_Vessel_Express    34 ft express cruiser (Mac polish: moored power boats 8-12 m, hull colour per instance)
  SM_Vessel_Sportfish  46 ft sportfisherman with flybridge, tower and outriggers (moored, 12-16 m)
  SM_Vessel_MotorYacht 60 ft flybridge motor yacht (moored, 16 m and over)
  SM_Vessel_Towboat    85 ft river towboat with push knees and a three-deck house
  SM_Barge_Hopper      a jumbo hopper barge (one hull; the tow is two of them)
  SM_Vessel_Container  a 230 m feeder container ship: bulbous bow, flare, house and funnel aft, hatch coamings
  SM_Container_40      a 40 ft container (stacked on the ship per instance, colour per instance)
  SM_Vessel_Tanker     a 228 m product tanker (the Gulf Pride): catwalk, cargo pipes, manifold and hose cranes, house aft
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
        f.normal_update()   # Graphics G6: a new face's normal is zero until updated (every face was projected along X)
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
             stations=28, rows=10, bow_rise=0.85, bulb=False, stripe=None):
        """A closed hull from stations: deck edge at the sheer, keel at -T, sections by kind ('v', 'round', 'box').
        stripe (z0, z1, slot): a band of the topsides in another slot (a boot stripe above the bottom paint)."""
        self.shape = (L, B, sheer_aft, sheer_bow, transom, kind)
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
                    band = stripe and stripe[0] <= zc < stripe[1]
                    self.face(q, bottom if zc < boot else (stripe[2] if band else top))
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

    def edge(self, x):
        """Half beam and sheer height of the last hull() at x (the deck edge, before the topsides' flare)."""
        L, B, sheer_aft, sheer_bow, transom, kind = self.shape
        u = min(max((x + L / 2) / L, 0.0), 1.0)
        if u < 0.55:
            half = B / 2 * (transom + (1 - transom) * math.sin(min(u / 0.55, 1) * math.pi / 2))
        else:
            half = B / 2 * max(0.0, 1 - ((u - 0.55) / 0.45) ** (2.4 if kind == "box" else 1.7))
        return max(half, 0.02), sheer_aft + (sheer_bow - sheer_aft) * u ** 2.2

    def prism(self, plan0, plan1, z0, z1, slot):
        """Mac polish: a deckhouse layer lofted between two plans (starboard halves aft to fore, mirrored to port, the same
        count each): the sides lean in and the front rakes where the upper plan is smaller, as a cruiser's house does."""
        def ring(plan, z):
            pts = [(x, y) for x, y in plan] + [(x, -y) for x, y in reversed(plan)]
            return [self.bm.verts.new((x, y, z)) for x, y in pts]
        r0, r1 = ring(plan0, z0), ring(plan1, z1)
        n = len(r0)
        for k in range(n):
            k2 = (k + 1) % n
            self.face((r0[k], r0[k2], r1[k2], r1[k]), slot)
        self.face(list(reversed(r0)), slot)
        self.face(r1, slot)

    def deckhouse(self, plans, zs, slots):
        """Stacked prisms: plans[i] -> plans[i + 1] between zs[i] and zs[i + 1] in slots[i] (a house, its window band, a roof)."""
        for k, slot in enumerate(slots):
            self.prism(plans[k], plans[k + 1], zs[k], zs[k + 1], slot)

    def rail(self, x0, x1, h=0.6, inset=0.08, post=1.0, slot="Steel", r=0.016):
        """Stanchions on the deck edge from x0 forward to x1 and a top rail round the bow (both sides meet at the stem)."""
        n = max(2, int((x1 - x0) / post))
        top = {1: [], -1: []}
        for k in range(n + 1):
            x = x0 + (x1 - x0) * k / n
            half, sheer = self.edge(x)
            for sd in (1, -1):
                y = sd * max(half - inset, 0.0)
                self.tube((x, y, sheer), (x, y, sheer + h), r, slot, 6)
                top[sd].append((x, y, sheer + h))
        for sd in (1, -1):
            for a, b in zip(top[sd], top[sd][1:]):
                self.tube(a, b, r, slot, 6)

    def rubrail(self, slot="Trim", r=0.035, n=24):
        """A rubbing strake round the sheer, both sides."""
        L = self.shape[0]
        for sd in (1, -1):
            pts = []
            for k in range(n + 1):
                x = -L / 2 + L * k / n
                half, sheer = self.edge(x)
                pts.append((x, sd * (half * (1 + 0.06 * k / n) + r * 0.5), sheer - 0.04))
            for a, b in zip(pts, pts[1:]):
                self.tube(a, b, r, slot, 6)

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
    # The white house (Mac polish: lofted, its sides leaning in, the wheelhouse windows a raked band all round, the roof
    # overhanging; it was three boxes). Same heights as before: the traffic's lights sit on them (APowerVesselActor).
    hx, lift = L * 0.18, (0.5 if committee else 0.0)
    a, f, w = hx - L * 0.11, hx + L * 0.11, B * 0.3
    p.deckhouse([[(a, w), (f - L * 0.05, w), (f, w * 0.7)],
                 [(a, w * 0.96), (f - L * 0.05, w * 0.96), (f - 0.1, w * 0.66)],
                 [(a, w * 0.92), (f - L * 0.06, w * 0.9), (f - 0.45, w * 0.6)],
                 [(a - 0.5, w * 1.08), (f - L * 0.05, w * 1.05), (f - 0.2, w * 0.75)],
                 [(a - 0.5, w * 1.08), (f - L * 0.05, w * 1.05), (f - 0.2, w * 0.75)]],
                [1.5, 2.95 + lift, 3.7 + lift, 3.72 + lift, 3.88 + lift], ["Gelcoat", "Glass", "Gelcoat", "Gelcoat"])
    p.tube((mast_x, 0.0, 1.6), (mast_x, 0.0, 1.6 + mast_h), 0.12 if not committee else 0.06, "Steel")
    if committee:
        # The saloon aft of the wheelhouse, lower, with its own window band, and the cockpit's coaming; a bow rail.
        sa, sf, sw = -L * 0.3, hx - L * 0.11, B * 0.36
        p.deckhouse([[(sa, sw), (sf, sw)], [(sa, sw * 0.97), (sf, sw * 0.97)], [(sa + 0.1, sw * 0.93), (sf, sw * 0.93)],
                     [(sa - 0.6, sw * 1.02), (sf, sw * 1.02)], [(sa - 0.6, sw * 1.02), (sf, sw * 1.02)]],
                    [1.3, 2.2, 2.75, 2.77, 2.9], ["Gelcoat", "Glass", "Gelcoat", "Gelcoat"])
        for sd in (1, -1):
            p.tube((sa - 0.55, sd * sw, 1.4), (sa - 0.55, sd * sw, 2.77), 0.04, "Steel", 6)
        p.rail(L * 0.12, L * 0.48, 0.65)
        p.rubrail()
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


def express():
    """Mac polish: a 34 ft express cruiser, the commonest bigger power boat in the coast's marinas: a deep-V hull painted
    per instance (Paint: M_VehiclePaint), a boot stripe, a low cabin trunk under the foredeck, a raked wrap-round
    windscreen, a hardtop over the helm on posts, cockpit seats, a swim platform and a bow rail."""
    p = Part("SM_Vessel_Express")
    L, B = 10.4, 3.4
    p.hull(L, B, 1.0, 1.4, 0.75, "v", top="Paint", bottom="Antifouling", boot=0.05, transom=0.95, bow_rise=0.72, stripe=(0.05, 0.16, "Dark"))
    p.rubrail()
    p.box((-L / 2 - 0.42, 0.0, 0.32), (0.45, 1.5, 0.05), "Deck")                 # swim platform
    p.deckhouse([[(-0.9, 1.55), (1.0, 1.55), (2.6, 1.15), (3.7, 0.4)],          # the cabin trunk, raking up to the screen
                 [(-0.8, 1.48), (1.0, 1.46), (2.5, 1.02), (3.4, 0.3)],
                 [(-0.6, 1.42), (-0.2, 1.38), (0.3, 1.05), (0.6, 0.45)],        # windscreen, swept back
                 [(-0.6, 1.42), (-0.2, 1.38), (0.3, 1.05), (0.6, 0.45)]],
                [1.05, 1.55, 2.05, 2.08], ["Gelcoat", "Glass", "Gelcoat"])
    p.deckhouse([[(-2.8, 1.4), (-0.3, 1.45), (0.3, 1.25), (0.55, 0.6)],          # hardtop
                 [(-2.8, 1.4), (-0.3, 1.45), (0.3, 1.25), (0.55, 0.6)]], [2.3, 2.38], ["Gelcoat"])
    for sd in (1, -1):
        p.tube((-2.6, sd * 1.3, 1.05), (-2.6, sd * 1.3, 2.3), 0.04, "Steel", 8)
        p.tube((-0.4, sd * 1.4, 2.05), (-0.5, sd * 1.4, 2.3), 0.04, "Steel", 8)
    p.box((-1.2, 0.0, 2.45), (0.25, 0.25, 0.07), "Gelcoat")                       # radar dome
    p.box((-3.9, 0.0, 1.28), (0.4, 1.35, 0.22), "Cushion")                        # transom seat
    p.box((-1.0, 0.65, 1.32), (0.3, 0.3, 0.27), "Cushion")                        # helm seat
    p.box((2.6, 0.0, 1.43), (0.6, 0.65, 0.05), "Cushion")                         # sun pad
    p.box((4.9, 0.0, 1.42), (0.25, 0.06, 0.05), "Steel")                         # anchor on the pulpit
    p.rail(1.6, 5.0, 0.55)
    p.export()


def sportfish():
    """Mac polish: a 46 ft sportfisherman: high flared bow, the house with its dark window band, a flybridge with helm and
    hardtop, a tuna tower, outriggers stowed upright, the fighting chair in a big cockpit, hull paint per instance."""
    p = Part("SM_Vessel_Sportfish")
    L, B = 14.0, 4.8
    p.hull(L, B, 1.35, 2.3, 1.0, "v", top="Paint", bottom="Antifouling", boot=0.08, transom=0.97, bow_rise=0.7, stripe=(0.08, 0.2, "Dark"))
    p.rubrail()
    p.box((-L / 2 - 0.3, 0.0, 0.45), (0.32, 1.9, 0.05), "Deck")
    p.deckhouse([[(-1.8, 2.25), (1.5, 2.25), (3.4, 1.65), (4.4, 0.6)],
                 [(-1.8, 2.18), (1.5, 2.15), (3.3, 1.5), (4.1, 0.5)],
                 [(-1.8, 2.1), (1.4, 2.06), (2.9, 1.3), (3.5, 0.45)],
                 [(-3.3, 2.2), (1.4, 2.12), (3.0, 1.4), (3.6, 0.5)],
                 [(-3.3, 2.2), (1.4, 2.12), (3.0, 1.4), (3.6, 0.5)]],
                [1.45, 2.55, 3.1, 3.12, 3.27], ["Gelcoat", "Glass", "Gelcoat", "Gelcoat"])
    for sd in (1, -1):
        p.tube((-3.2, sd * 2.05, 1.4), (-3.2, sd * 2.05, 3.12), 0.05, "Steel", 8)
        p.box((-1.0, sd * 2.1, 3.47), (2.3, 0.04, 0.2), "Gelcoat")               # flybridge coaming
    p.box((0.9, 0.0, 3.65), (0.45, 1.0, 0.38), "Gelcoat")                         # flybridge helm
    p.box((0.95, 0.0, 4.05), (0.04, 0.9, 0.12), "Glass")
    for y in (-0.6, 0.0, 0.6):
        p.box((-0.2, y, 3.55), (0.28, 0.25, 0.28), "Cushion")
    p.box((0.0, 0.0, 5.05), (1.7, 1.9, 0.05), "Gelcoat")                          # hardtop
    tower = []
    for sx in (-1.5, 1.5):
        for sd in (1, -1):
            p.tube((sx, sd * 1.75, 3.27), (sx * 0.95, sd * 1.7, 5.0), 0.04, "Steel", 6)
            p.tube((sx * 0.95, sd * 1.7, 5.1), (sx * 0.5, sd * 0.8, 7.2), 0.035, "Steel", 6)
            tower.append((sx * 0.5, sd * 0.8, 7.2))
    p.box((0.0, 0.0, 7.25), (0.8, 0.85, 0.04), "Gelcoat")                         # tower top
    for sd in (1, -1):
        p.tube((0.6, sd * 1.75, 5.1), (-2.5, sd * 2.3, 12.5), 0.03, "Steel", 6)   # outrigger, stowed
    p.tube((-5.0, 0.0, 1.4), (-5.0, 0.0, 1.85), 0.08, "Steel", 8)                 # fighting chair
    p.box((-5.0, 0.0, 1.98), (0.35, 0.33, 0.12), "Cushion")
    p.box((-4.75, 0.0, 2.3), (0.08, 0.33, 0.3), "Cushion")
    p.box((-6.65, 0.0, 1.47), (0.08, 1.9, 0.12), "Gelcoat")                       # transom cap
    p.rail(3.2, 6.9, 0.6)
    p.export()


def motor_yacht():
    """Mac polish: a 60 ft flybridge motor yacht, the big boats at the end of the coast's docks: two decks of house with
    long raked window bands, the aft deck under the saloon roof, the flybridge's hardtop and radar arch, hull windows,
    a swim platform, a bow rail and paint per instance."""
    p = Part("SM_Vessel_MotorYacht")
    L, B = 18.0, 5.2
    p.hull(L, B, 1.6, 2.55, 1.25, "v", top="Paint", bottom="Antifouling", boot=0.1, transom=0.95, bow_rise=0.72, stripe=(0.1, 0.24, "Dark"))
    p.rubrail()
    p.box((-L / 2 - 0.65, 0.0, 0.55), (0.7, 2.3, 0.07), "Deck")
    for x in (-1.5, 0.6, 2.7):                                                     # hull windows
        half, sheer = p.edge(x)
        for sd in (1, -1):
            p.box((x, sd * (half * 1.04 + 0.01), sheer - 0.75), (0.9, 0.04, 0.13), "Glass")
    p.deckhouse([[(-6.2, 2.45), (2.0, 2.45), (4.6, 1.8), (6.1, 0.7)],             # main deck house
                 [(-6.2, 2.4), (2.0, 2.38), (4.5, 1.7), (5.8, 0.6)],
                 [(-6.2, 2.33), (1.8, 2.3), (4.0, 1.5), (5.0, 0.55)],
                 [(-8.4, 2.45), (1.8, 2.38), (4.1, 1.6), (5.1, 0.6)],
                 [(-8.4, 2.45), (1.8, 2.38), (4.1, 1.6), (5.1, 0.6)]],
                [1.75, 2.6, 3.35, 3.37, 3.52], ["Gelcoat", "Glass", "Gelcoat", "Gelcoat"])
    for sd in (1, -1):
        p.tube((-8.2, sd * 2.3, 1.7), (-8.2, sd * 2.3, 3.37), 0.06, "Steel", 8)
        p.box((-7.3, sd * 2.4, 2.05), (1.05, 0.04, 0.4), "Gelcoat")              # aft deck bulwark
    p.deckhouse([[(-2.6, 1.95), (1.5, 1.95), (3.0, 1.45), (3.7, 0.6)],            # flybridge house
                 [(-2.6, 1.9), (1.5, 1.88), (2.9, 1.35), (3.5, 0.55)],
                 [(-2.6, 1.85), (1.3, 1.8), (2.5, 1.2), (3.0, 0.5)],
                 [(-5.8, 2.05), (1.3, 1.9), (2.6, 1.3), (3.1, 0.55)],
                 [(-5.8, 2.05), (1.3, 1.9), (2.6, 1.3), (3.1, 0.55)]],
                [3.5, 4.2, 4.75, 4.77, 4.9], ["Gelcoat", "Glass", "Gelcoat", "Gelcoat"])
    for sd in (1, -1):
        p.tube((-5.6, sd * 1.9, 3.52), (-5.6, sd * 1.9, 4.77), 0.05, "Steel", 8)
        p.box((-4.2, sd * 2.2, 3.75), (1.6, 0.04, 0.25), "Gelcoat")              # flybridge coaming
        p.tube((-1.0, sd * 1.5, 4.9), (-2.0, sd * 1.1, 6.6), 0.09, "Gelcoat", 8)  # radar arch
    p.tube((-2.0, -1.1, 6.6), (-2.0, 1.1, 6.6), 0.09, "Gelcoat", 8)
    p.box((-1.9, 0.0, 6.78), (0.35, 0.35, 0.1), "Gelcoat")                        # radome
    p.box((-2.2, 0.0, 6.75), (0.08, 1.0, 0.04), "Funnel")                         # open-array radar
    for y in (-1.2, -0.4, 0.4, 1.2):
        p.box((-4.2, y, 3.82), (0.4, 0.3, 0.28), "Cushion")
    p.box((-7.2, 0.0, 1.85), (0.6, 0.8, 0.25), "Cushion")                         # aft deck settee
    p.rail(3.0, 8.9, 0.75)
    p.box((8.6, 0.0, 2.6), (0.3, 0.08, 0.06), "Steel")
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
    """Graphics G6: round 7's "low detail" ship. A feeder container ship as one reads from a sailboat a few hundred metres
    off: a five-tier house aft with window bands, bridge wings and rails on every deck, a funnel with its band, a radar
    mast; a bulwark rail along the main deck; three pedestal cranes stowed along the port side, lashing bridges between
    the bays, the forecastle's breakwater, windlasses, bollards and hawse pipes; a freefall lifeboat on its ramp at the
    stern. The hull's paint weeps rust from the deck edge (MI_World_ShipHull, M_WorldSurface pattern 8)."""
    p = Part("SM_Vessel_Container")
    L, B = 230.0, 32.0
    p.hull(L, B, 11.0, 14.0, 10.5, "box", top="ShipHull", bottom="Antifouling", boot=0.4, transom=0.8, stations=40, rows=12, bow_rise=0.9, bulb=True)
    sheer = lambda x: 11.0 + 3.0 * ((x + L / 2) / L) ** 2.2

    def half_beam(x):
        u = (x + L / 2) / L
        if u < 0.55:
            return B / 2 * (0.8 + 0.2 * math.sin(min(u / 0.55, 1) * math.pi / 2))
        return B / 2 * max(0.0, 1 - ((u - 0.55) / 0.45) ** 2.4)

    def rail(pts, h=1.1, post=1.6, slot="Trim"):
        """Stanchions every `post` metres along a polyline, a top rail and a mid rail."""
        for a, b in zip(pts, pts[1:]):
            a, b = Vector(a), Vector(b)
            n = max(1, int((b - a).length / post))
            for k in range(n):
                q = a + (b - a) * (k / n)
                p.tube(q, q + Vector((0, 0, h)), 0.03, slot, 4)
            for z in (h, h * 0.5):
                p.tube(a + Vector((0, 0, z)), b + Vector((0, 0, z)), 0.025, slot, 4)

    # The house: five tiers stepping in, a window band on each (front and sides), rails round every deck.
    hx, hw = -90.0, B * 0.42
    z = sheer(hx)
    for t in range(5):
        dx, dw = 9.0 - 0.6 * t, hw - 0.4 * t
        p.box((hx, 0.0, z + 1.4), (dx, dw, 1.4), "Gelcoat")
        p.box((hx + dx + 0.03, 0.0, z + 1.6), (0.05, dw * 0.9, 0.55), "Glass")
        for s_ in (1, -1):
            for k in range(int(2 * dx / 2.4)):
                p.box((hx - dx + 1.2 + 2.4 * k, s_ * (dw + 0.03), z + 1.6), (0.6, 0.05, 0.5), "Glass")
        deck = z + 2.8
        corners = [(hx - dx, -dw, deck), (hx + dx, -dw, deck), (hx + dx, dw, deck), (hx - dx, dw, deck), (hx - dx, -dw, deck)]
        rail(corners, 1.0, 1.8)
        z = deck
    # The bridge on top, wider than the house (its wings), with its windows all round the front.
    p.box((hx - 1.0, 0.0, z + 1.5), (5.0, B * 0.51, 1.5), "Gelcoat")
    p.box((hx + 4.03, 0.0, z + 1.9), (0.05, B * 0.5, 0.75), "Glass")
    for s_ in (1, -1):
        p.box((hx - 1.0, s_ * (B * 0.51 + 0.03), z + 1.9), (4.0, 0.05, 0.75), "Glass")
        rail([(hx + 4.0, s_ * hw, z), (hx + 4.0, s_ * B * 0.51, z)], 1.0, 1.5)
    top = z + 3.0
    rail([(hx - 6.0, -B * 0.5, top), (hx + 4.0, -B * 0.5, top), (hx + 4.0, B * 0.5, top), (hx - 6.0, B * 0.5, top)], 1.0, 2.0)
    # Radar mast on the wheelhouse top: a tripod, two scanners, the masthead light.
    mx = hx - 1.0
    p.tube((mx, 0.0, top), (mx, 0.0, top + 9.0), 0.25, "Steel", 8)
    p.tube((mx - 2.5, -1.5, top), (mx, 0.0, top + 6.0), 0.12, "Steel", 6)
    p.tube((mx - 2.5, 1.5, top), (mx, 0.0, top + 6.0), 0.12, "Steel", 6)
    p.box((mx, 0.0, top + 6.0), (0.8, 2.2, 0.08), "Steel")
    p.box((mx + 0.3, 0.0, top + 6.5), (0.15, 2.0, 0.12), "Funnel")
    p.box((mx + 0.3, 0.0, top + 8.3), (0.12, 1.4, 0.1), "Funnel")
    # The funnel: dark casing, a coloured band and a black top; exhaust pipes out of it.
    p.box((-102.0, 0.0, 30.0), (4.0, 3.5, 6.0), "Funnel")
    p.box((-102.0, 0.0, 32.0), (4.05, 3.55, 1.0), "AviationRed")
    p.box((-102.0, 0.0, 35.8), (4.05, 3.55, 0.2), "Funnel")
    for dy in (-1.2, 1.2):
        p.tube((-102.5, dy, 35.5), (-102.5, dy, 37.0), 0.35, "Steel", 8)
    # A freefall lifeboat on its ramp over the stern, and a rescue boat's davit to port.
    p.box((-110.0, 0.0, sheer(-110.0) + 2.0), (4.5, 1.6, 0.15), "Steel")
    ramp = Vector((-110.0, 0.0, sheer(-110.0) + 3.4))
    p.box(tuple(ramp), (4.2, 1.5, 1.2), "Lifeboat")
    p.box(tuple(ramp + Vector((0.5, 0.0, 1.35))), (2.0, 1.2, 0.3), "Lifeboat")
    p.tube((-96.0, B * 0.5, sheer(-96.0)), (-96.0, B * 0.5, sheer(-96.0) + 5.0), 0.2, "Trim", 6)
    p.tube((-96.0, B * 0.5, sheer(-96.0) + 5.0), (-96.0, B * 0.5 + 2.0, sheer(-96.0) + 4.0), 0.15, "Trim", 6)
    p.box((-96.0, B * 0.5 - 1.2, sheer(-96.0) + 1.2), (3.0, 1.1, 0.7), "Lifeboat")
    # Hatch coamings under the bays, lashing bridges between them.
    for i in range(14):
        x = -74.0 + i * 12.8
        p.box((x, 0.0, 11.9), (6.1, B * 0.43, 0.9), "ShipHull")
        if i < 13:
            xb = x + 6.4
            for s_ in (1, -1):
                p.box((xb, s_ * B * 0.44, 15.0), (0.15, 0.15, 2.4), "Steel")
            p.box((xb, 0.0, 17.4), (0.25, B * 0.44, 0.08), "Steel")
            p.box((xb, 0.0, 14.8), (0.25, B * 0.44, 0.08), "Steel")
            rail([(xb, -B * 0.44, 17.4), (xb, B * 0.44, 17.4)], 1.0, 2.5, "Steel")
    # The bulwark rail along the main deck, both sides, from the house to the forecastle.
    for s_ in (1, -1):
        pts = [(x, s_ * (half_beam(x) - 0.3), sheer(x)) for x in [-112.0 + 6.0 * k for k in range(37)] if x < 103.0]
        rail(pts, 1.1, 2.0)
    # Three cranes on pedestals along the port walkway, jibs stowed fore and aft on their rests.
    for cx in (-35.5, 3.0, 41.5):
        y = B * 0.465
        p.tube((cx, y, 12.0), (cx, y, 24.0), 1.1, "Steel", 12)
        p.box((cx, y, 25.6), (2.2, 1.4, 1.6), "Steel")
        p.box((cx + 1.6, y - 1.0, 26.2), (0.7, 0.45, 0.8), "Glass")
        p.box((cx - 2.6, y, 25.4), (0.8, 1.0, 1.0), "Steel")                    # counterweight
        jib_a = Vector((cx + 1.8, y, 25.0))
        jib_b = Vector((cx + 26.0, y, 28.5))
        for dz in (0.0, 1.2):
            for dyy in (-0.5, 0.5):
                p.tube(jib_a + Vector((0, dyy, dz)), jib_b + Vector((0, dyy * 0.4, dz * 0.4)), 0.12, "Steel", 6)
        for k in range(1, 12):
            q = jib_a + (jib_b - jib_a) * (k / 12)
            p.tube(q, q + Vector((0, 0, 1.2 * (1 - 0.6 * k / 12))), 0.06, "Steel", 4)
        p.tube((cx + 24.0, y, 12.5), (cx + 24.0, y, 28.3), 0.25, "Steel", 6)       # the jib rest
        p.tube(jib_a + Vector((0, 0, 2.5)), jib_b + Vector((0, 0, 0.6)), 0.03, "Steel", 4)   # luffing wire
    # The forecastle: deck, breakwater ahead of the first bay, windlasses, bollards, the anchors in their hawse pipes.
    p.box((108.0, 0.0, 15.5), (3.0, B * 0.3, 1.5), "ShipHull")
    for s_ in (1, -1):
        p.box((88.0, s_ * 5.0, sheer(88.0) + 1.6), (0.15, 6.0, 1.6), "ShipHull", yaw=s_ * 0.35)
    for s_ in (1, -1):
        wx, wy = 106.0, s_ * 3.0
        p.box((wx, wy, 17.6), (1.2, 0.9, 0.6), "TrimGreen")
        p.tube((wx, wy - 1.2, 18.0), (wx, wy + 1.2, 18.0), 0.55, "Funnel", 10)
        for bx in (100.0, 96.0):
            for dx in (0.0, 0.7):
                p.tube((bx + dx, s_ * 6.0, sheer(bx)), (bx + dx, s_ * 6.0, sheer(bx) + 0.8), 0.22, "Funnel", 8)
        # The hawse pipe and the anchor stowed in it, on the flare of the bow.
        hx_ = 109.0
        hy = s_ * (half_beam(hx_) + 0.15)
        p.box((hx_, hy, 10.5), (1.0, 0.1, 0.9), "Funnel")
        p.box((hx_ - 0.2, hy + s_ * 0.15, 9.6), (0.35, 0.12, 1.2), "Funnel")
    # Aft mooring deck: bollards and a winch each side.
    for s_ in (1, -1):
        for bx in (-108.0, -104.0):
            for dx in (0.0, 0.7):
                p.tube((bx + dx, s_ * 10.0, sheer(bx)), (bx + dx, s_ * 10.0, sheer(bx) + 0.8), 0.22, "Funnel", 8)
        p.box((-106.0, s_ * 6.0, sheer(-106.0) + 0.6), (1.0, 0.8, 0.6), "TrimGreen")
    p.export()
    c = Part("SM_Container_40")
    c.box((0.0, 0.0, 1.295), (6.0, 1.18, 1.25), "ContainerPaint")
    # Graphics G6: what makes a box read as a container up close: corrugated side walls, top and bottom rails, corner
    # posts with their castings, and the door end's four locking bars.
    for s_ in (1, -1):
        for k in range(42):
            x = -5.9 + k * 0.287
            c.box((x, s_ * 1.2, 1.3), (0.07, 0.025, 1.17), "ContainerPaint")
        c.box((0.0, s_ * 1.205, 2.52), (6.06, 0.04, 0.07), "ContainerPaint")
        c.box((0.0, s_ * 1.205, 0.08), (6.06, 0.04, 0.08), "ContainerPaint")
    for sx in (1, -1):
        for sy in (1, -1):
            c.box((sx * 5.98, sy * 1.15, 1.295), (0.08, 0.08, 1.295), "ContainerPaint")
            for z in (0.06, 2.53):
                c.box((sx * 6.0, sy * 1.17, z), (0.09, 0.09, 0.06), "Steel")
    for y in (-0.75, -0.35, 0.35, 0.75):
        c.tube((6.07, y, 0.15), (6.07, y, 2.45), 0.025, "Steel", 6)
    c.export()


def tanker():
    """The Gulf Pride: a 228 m product tanker laden in the channel (6 m of freeboard). Black topsides over the red
    bottom paint, a flush main deck with the cargo pipes and the raised catwalk running from the house to the
    forecastle, ullage domes over the tanks, the midships manifold with its hose cranes, vent risers, a foremast on the
    forecastle, and a five-tier house aft with the bridge wings, radar mast, funnel and freefall lifeboat."""
    p = Part("SM_Vessel_Tanker")
    L, B = 228.0, 32.0
    p.hull(L, B, 7.0, 10.0, 12.0, "box", top="ShipHull", bottom="Antifouling", boot=0.4, transom=0.8, stations=40, rows=12, bow_rise=0.9, bulb=True)

    def deck(x):
        return p.edge(x)[1]

    def rail(pts, h=1.1, post=1.6, slot="Trim"):
        """Stanchions every `post` metres along a polyline, a top rail and a mid rail."""
        for a, b in zip(pts, pts[1:]):
            a, b = Vector(a), Vector(b)
            n = max(1, int((b - a).length / post))
            for k in range(n):
                q = a + (b - a) * (k / n)
                p.tube(q, q + Vector((0, 0, h)), 0.03, slot, 4)
            for z in (h, h * 0.5):
                p.tube(a + Vector((0, 0, z)), b + Vector((0, 0, z)), 0.025, slot, 4)

    x0, x1 = -76.0, 96.0                       # the cargo deck, house front to forecastle
    # Cargo and vapour pipes along the deck on saddles, a little to each side of the catwalk.
    for y, r in ((-3.4, 0.35), (-2.4, 0.3), (-1.5, 0.25), (1.5, 0.25), (2.4, 0.3), (3.4, 0.35), (4.6, 0.45)):
        pts = [(x, y, deck(x) + 0.9) for x in [x0 + (x1 - x0) * k / 12 for k in range(13)]]
        for a, b in zip(pts, pts[1:]):
            p.tube(a, b, r, "Steel", 8)
    for k in range(29):
        x = x0 + (x1 - x0) * k / 28
        p.box((x, 0.5, deck(x) + 0.35), (0.15, 5.0, 0.35), "Steel")
    # The catwalk: a raised gangway on the centreline, on pillars, railed both sides.
    cz = lambda x: deck(x) + 2.6
    for k in range(30):
        x = x0 + (x1 - x0) * k / 29
        p.tube((x, 0.0, deck(x)), (x, 0.0, cz(x)), 0.15, "Steel", 6)
    walk = [x0 + (x1 - x0) * k / 12 for k in range(13)]
    for a, b in zip(walk, walk[1:]):
        p.box(((a + b) / 2, 0.0, (cz(a) + cz(b)) / 2), ((b - a) / 2, 0.6, 0.06), "Steel")
    for s_ in (1, -1):
        rail([(x, s_ * 0.6, cz(x) + 0.06) for x in walk], 1.0, 2.0, "Trim")
    # Ullage domes and tank hatches over twelve pairs of tanks.
    for i in range(12):
        x = x0 + 8.0 + i * 14.0
        for s_ in (1, -1):
            p.tube((x, s_ * 8.0, deck(x)), (x, s_ * 8.0, deck(x) + 0.7), 0.7, "Steel", 10)
            p.box((x + 3.0, s_ * 11.5, deck(x) + 0.25), (0.8, 0.8, 0.25), "Steel")
    # Vent risers with their pressure/vacuum heads.
    for x in (-60.0, -20.0, 20.0, 60.0):
        for s_ in (1, -1):
            p.tube((x, s_ * 5.6, deck(x)), (x, s_ * 5.6, deck(x) + 5.0), 0.25, "Steel", 8)
            p.box((x, s_ * 5.6, deck(x) + 5.2), (0.45, 0.45, 0.25), "Funnel")
    # The manifold midships: crossover pipes to both sides, valves, drip trays, a hose crane each side.
    mx = 4.0
    for k in range(4):
        x = mx - 3.0 + 2.0 * k
        p.tube((x, -B * 0.46, deck(x) + 1.2), (x, B * 0.46, deck(x) + 1.2), 0.3, "Steel", 8)
        for s_ in (1, -1):
            p.box((x, s_ * B * 0.42, deck(x) + 1.2), (0.4, 0.5, 0.5), "TrimGreen")
            p.box((x, s_ * B * 0.455, deck(x) + 1.2), (0.05, 0.4, 0.4), "Steel")
    for s_ in (1, -1):
        p.box((mx, s_ * B * 0.44, deck(mx) + 0.15), (4.5, 1.2, 0.15), "Steel")
        cx, cy = mx + 7.0, s_ * B * 0.36
        p.tube((cx, cy, deck(cx)), (cx, cy, deck(cx) + 8.0), 0.6, "Steel", 10)
        p.box((cx, cy, deck(cx) + 8.6), (1.2, 1.0, 0.8), "Steel")
        tip = Vector((cx - 12.0, cy, deck(cx) + 10.0))
        p.tube((cx, cy, deck(cx) + 9.0), tuple(tip), 0.3, "Steel", 6)
        p.tube(tuple(tip), tuple(tip - Vector((0, 0, 3.0))), 0.03, "Steel", 4)
    # Bulwark rail along the main deck, both sides.
    for s_ in (1, -1):
        pts = [(x, s_ * (p.edge(x)[0] - 0.3), deck(x)) for x in [-112.0 + 6.0 * k for k in range(37)] if x < 103.0]
        rail(pts, 1.1, 2.0)
    # The forecastle: a raised deck, its breakwater, the foremast, windlasses, bollards and the anchors.
    fx = 98.0
    p.box((fx + 6.0, 0.0, deck(fx) + 1.2), (8.0, p.edge(fx)[0] * 0.8, 1.2), "ShipHull")
    for s_ in (1, -1):
        p.box((fx - 3.0, s_ * 4.5, deck(fx) + 1.2), (0.15, 5.0, 1.2), "ShipHull", yaw=s_ * 0.35)
    fz = deck(fx) + 2.4
    p.tube((fx + 2.0, 0.0, fz), (fx + 2.0, 0.0, fz + 14.0), 0.35, "Steel", 8)
    p.box((fx + 2.0, 0.0, fz + 9.0), (0.15, 2.0, 0.12), "Steel")
    for s_ in (1, -1):
        wx, wy = fx + 8.0, s_ * 3.0
        p.box((wx, wy, fz + 0.6), (1.2, 0.9, 0.6), "TrimGreen")
        p.tube((wx, wy - 1.2, fz + 1.0), (wx, wy + 1.2, fz + 1.0), 0.55, "Funnel", 10)
        for dx in (0.0, 0.7):
            p.tube((fx + 3.0 + dx, s_ * 5.5, fz), (fx + 3.0 + dx, s_ * 5.5, fz + 0.8), 0.22, "Funnel", 8)
        hx_ = 108.0
        hy = s_ * (p.edge(hx_)[0] + 0.15)
        p.box((hx_, hy, deck(hx_) - 1.5), (1.0, 0.1, 0.9), "Funnel")
        p.box((hx_ - 0.2, hy + s_ * 0.15, deck(hx_) - 2.4), (0.35, 0.12, 1.2), "Funnel")
    # The house: five tiers stepping in, window bands, rails round every deck; the bridge and its wings on top.
    hx, hw = -88.0, B * 0.42
    z = deck(hx)
    for t in range(5):
        dx, dw = 9.0 - 0.6 * t, hw - 0.4 * t
        p.box((hx, 0.0, z + 1.4), (dx, dw, 1.4), "Gelcoat")
        p.box((hx + dx + 0.03, 0.0, z + 1.6), (0.05, dw * 0.9, 0.55), "Glass")
        for s_ in (1, -1):
            for k in range(int(2 * dx / 2.4)):
                p.box((hx - dx + 1.2 + 2.4 * k, s_ * (dw + 0.03), z + 1.6), (0.6, 0.05, 0.5), "Glass")
        top_ = z + 2.8
        rail([(hx - dx, -dw, top_), (hx + dx, -dw, top_), (hx + dx, dw, top_), (hx - dx, dw, top_), (hx - dx, -dw, top_)], 1.0, 1.8)
        z = top_
    p.box((hx - 1.0, 0.0, z + 1.5), (5.0, B * 0.51, 1.5), "Gelcoat")
    p.box((hx + 4.03, 0.0, z + 1.9), (0.05, B * 0.5, 0.75), "Glass")
    for s_ in (1, -1):
        p.box((hx - 1.0, s_ * (B * 0.51 + 0.03), z + 1.9), (4.0, 0.05, 0.75), "Glass")
    top = z + 3.0
    rail([(hx - 6.0, -B * 0.5, top), (hx + 4.0, -B * 0.5, top), (hx + 4.0, B * 0.5, top), (hx - 6.0, B * 0.5, top)], 1.0, 2.0)
    rx = hx - 1.0
    p.tube((rx, 0.0, top), (rx, 0.0, top + 9.0), 0.25, "Steel", 8)
    p.tube((rx - 2.5, -1.5, top), (rx, 0.0, top + 6.0), 0.12, "Steel", 6)
    p.tube((rx - 2.5, 1.5, top), (rx, 0.0, top + 6.0), 0.12, "Steel", 6)
    p.box((rx, 0.0, top + 6.0), (0.8, 2.2, 0.08), "Steel")
    p.box((rx + 0.3, 0.0, top + 6.5), (0.15, 2.0, 0.12), "Funnel")
    p.box((rx + 0.3, 0.0, top + 8.3), (0.12, 1.4, 0.1), "Funnel")
    # The funnel behind the house, its band and black top; the freefall lifeboat on its ramp over the stern.
    fy = top - 2.0
    p.box((-100.0, 0.0, fy), (4.0, 3.5, 6.0), "Funnel")
    p.box((-100.0, 0.0, fy + 2.0), (4.05, 3.55, 1.0), "AviationRed")
    p.box((-100.0, 0.0, fy + 5.8), (4.05, 3.55, 0.2), "Funnel")
    p.box((-108.0, 0.0, deck(-108.0) + 2.0), (4.5, 1.6, 0.15), "Steel")
    ramp = Vector((-108.0, 0.0, deck(-108.0) + 3.4))
    p.box(tuple(ramp), (4.2, 1.5, 1.2), "Lifeboat")
    p.box(tuple(ramp + Vector((0.5, 0.0, 1.35))), (2.0, 1.2, 0.3), "Lifeboat")
    for s_ in (1, -1):
        for bx in (-106.0, -102.0):
            for dx in (0.0, 0.7):
                p.tube((bx + dx, s_ * 10.0, deck(bx)), (bx + dx, s_ * 10.0, deck(bx) + 0.8), 0.22, "Funnel", 8)
    print(f"Tanker: masthead fwd z {fz + 14.0:.1f} aft z {top + 9.0:.1f}, bridge deck z {z:.1f}, funnel top z {fy + 6.0:.1f}")
    p.export()


bpy.ops.wm.read_factory_settings(use_empty=True)
runabout()
trawler("SM_Vessel_Shrimper", 21.0, 6.5, 0.42, 11.0)
trawler("SM_Vessel_Committee", 11.0, 3.8, 0.0, 6.0, committee=True)
express()
sportfish()
motor_yacht()
towboat()
ship()
tanker()
