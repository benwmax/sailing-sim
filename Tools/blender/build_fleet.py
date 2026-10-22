"""Visual V7: the other seven boats of the fleet, built from code in Blender (headless), like the J/22 (build_j22.py).

    blender -b --factory-startup -P Tools/blender/build_fleet.py -- <boat.json> <Tag> <out dir>

<boat.json> comes from Tools/BoatExport (the FBoatConfig the physics floats and sails). As with the J/22, every hull
below the waterline is exactly the physics hull surface (FHullShape::BottomZ at the computed canoe depth, each hull at
its CenterY with its DepthScale and DepthOffset), so the model's displaced volume and centre of buoyancy are the
physics'. Above the water the bow sharpens toward the real boat, and the class's own deck goes on top: cockpits and
cabin trunks, lifelines and pulpits on the keelboats, a trampoline and beams on the Hobie, akas and nets on the Corsair,
a bridgedeck, saloon and bimini on the Lagoon, from the class drawings and photos. Keels and boards reach the physics'
draft. Each class's rig is built from the same numbers (mast, spreaders, boom, the Sunfish's lateen yard) with sockets
only for the fittings that class has (an unstayed ILCA has no shroud plates); the game draws its wires from them.

Writes <out>/SM_<Tag>_Hull.fbx, _Mast, _Boom, _Rudder and <Tag>_sockets.json (Unreal frame, cm), like the J/22.
Frames as in build_j22.py: Unreal's body frame (X forward, Y starboard, Z up, metres, origin on the design waterline
amidships); points go into Blender as (x, -y, z).
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from boat_packs import pack_slots  # noqa: E402  (pc/boat-slots)

ARGS = sys.argv[sys.argv.index("--") + 1:]
CFG = json.load(open(ARGS[0]))
TAG = ARGS[1]
OUT = ARGS[2]
os.makedirs(OUT, exist_ok=True)

MAIN_DEPTH = CFG["canoe_depth"]
RIG = CFG["rig"]
HULLS = CFG["hulls"]
DRAFT = CFG["draft"]

SLOTS = ["Topsides", "Bootstripe", "CoveStripe", "Antifouling", "Keel", "Deck", "NonSkid", "CabinWindow",
         "Stainless", "Aluminium", "BlackPlastic", "Wood", "Graphics", "Rubrail", "SailCover", "Rope"]   # Rope last: the earlier slots keep their indices
CANOE = ("Topsides", "Bootstripe", "CoveStripe", "Antifouling", "PackCanoe")   # (packed: boat_packs.json's PackCanoe is exactly these)

# Per class: the deck and fittings the physics doesn't describe (metres, body frame), from the class drawings.
SPECS = {
    "Sunfish": dict(paint=False, crown=0.035, cockpit=(-1.18, -0.52, 0.29, 0.20), trunk=True, rig="lateen", tiller=True),
    "ILCA7": dict(paint=False, crown=0.05, cockpit=(-1.62, -0.22, 0.31, 0.22), trunk=True, rig="una", tiller=True, vang=True),
    "Catalina22": dict(paint=True, crown=0.05, cockpit=(-3.05, -0.78, 0.63, 0.42), cabin=(-0.78, 1.70, 0.62, 0.42), rig="masthead",
                       tiller=True, lifelines=True, outboard=True, spreader=0.62, winch_x=-1.05),
    "Catalina30": dict(paint=True, crown=0.06, cockpit=(-4.05, -1.32, 0.82, 0.5), cabin=(-1.32, 2.85, 0.92, 0.6), rig="masthead",
                       wheel=-3.45, dodger=True, lifelines=True, spreader=0.95, winch_x=-1.65),
    "Hobie16": dict(paint=False, crown=0.12, rig="beachcat", beams=(0.55, -1.75), tiller=True),
    "Corsair880": dict(paint=True, crown=0.05, cockpit=(-3.75, -0.95, 0.62, 0.45), cabin=(-0.95, 2.2, 0.62, 0.48), rig="tri",
                       akas=(1.55, -1.75), tiller=True, outboard=True, spreader=1.1, winch_x=-1.2, bowsprit=1.25),
    "Lagoon42": dict(paint=True, crown=0.04, rig="cruisingcat", bridgedeck=(-4.6, 4.3), spreader=1.6),
}
SPEC = SPECS[TAG]


# ---------------------------------------------------------------- the physics hulls (FHullShape, BoatModel.cpp)

class Hull:
    def __init__(self, h):
        self.h = h
        self.cy = h["center_y"]

    def deck_half_beam(self, x):
        h = self.h
        if x > h["max_beam_x"]:
            u = (x - h["max_beam_x"]) / (h["bow_x"] - h["max_beam_x"] + 0.02)
            return h["max_half_beam"] * math.sqrt(max(0.0, 1.0 - u * u))
        u = (h["max_beam_x"] - x) / h["aft_length"]
        return max(h["max_half_beam"] - h["transom_beam_loss"] * u * u, 0.02)

    def sheer(self, x):
        h = self.h
        return h["sheer_z"] + h["sheer_rise"] * max(0.0, (x - h["sheer_rise_from_x"]) / max(h["bow_x"] - h["sheer_rise_from_x"], 1e-3))

    def keel_line_depth(self, x):
        h = self.h
        d = MAIN_DEPTH * h["depth_scale"]
        u = (x - h["waterline_mid_x"]) / h["waterline_half_length"]
        if abs(u) <= 1.0:
            return d * (1.0 - u * u) - h["depth_offset"]
        return -(abs(u) - 1.0) * h["waterline_half_length"] * (h["bow_overhang_slope"] if u > 0 else h["stern_overhang_slope"]) - h["depth_offset"]

    def sharp_half_beam(self, x):
        h = self.h
        if x <= h["max_beam_x"]:
            return self.deck_half_beam(x)
        u = (x - h["max_beam_x"]) / (h["bow_x"] - h["max_beam_x"] + 0.02)
        return h["max_half_beam"] * (1.0 - min(u, 1.0) ** 2.2) ** 0.92

    def half_beam(self, x, z):
        # Below the water: the physics. Above it the entry sharpens over the first 0.35 m (scaled to the hull's height).
        k = min(max(z / (0.35 * max(self.h["sheer_z"] / 0.62, 0.4)), 0.0), 1.0)
        k = k * k * (3 - 2 * k)
        return (1 - k) * self.deck_half_beam(x) + k * self.sharp_half_beam(x)

    def section_point(self, x, r):
        d, s = self.keel_line_depth(x), self.sheer(x)
        z = -d + (d + s) * r ** self.h["bilge_power"]
        return (x, self.cy + self.half_beam(x, z) * r, z), z

    def r_at_z(self, x, z):
        d, s = self.keel_line_depth(x), self.sheer(x)
        t = min(max((z + d) / max(d + s, 1e-6), 0.0), 1.0)
        return t ** (1.0 / self.h["bilge_power"])

    def bottom_z(self, x, y):
        d = self.keel_line_depth(x)
        b = max(self.deck_half_beam(x), 1e-3)
        r = min(abs(y - self.cy) / b, 1.0)
        return -d + (d + self.sheer(x)) * r ** self.h["bilge_power"]

    def deck_z(self, x, y):
        b = max(self.sharp_half_beam(x), 1e-3)
        return self.sheer(x) + SPEC["crown"] * max(0.0, 1.0 - ((y - self.cy) / b) ** 2)


HS = [Hull(h) for h in HULLS]
MAIN = HS[0]


# ---------------------------------------------------------------- mesh building (as build_j22.py)

class Mesh:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.verts = {}

    def v(self, p):
        x, y, z = p
        key = (round(x, 5), round(-y, 5), round(z, 5))
        vert = self.verts.get(key)
        if vert is None:
            vert = self.bm.verts.new((x, -y, z))
            self.verts[key] = vert
        return vert

    def face(self, pts, slot):
        vs = [self.v(p) for p in pts]
        uniq = []
        for v in vs:
            if not uniq or uniq[-1] is not v:
                uniq.append(v)
        if len(uniq) > 2 and uniq[0] is uniq[-1]:
            uniq.pop()
        if len(uniq) < 3 or len(set(uniq)) < len(uniq):
            return None
        try:
            f = self.bm.faces.new(uniq)
        except ValueError:
            return None
        f.material_index = SLOTS.index(slot)
        f.smooth = True
        return f

    def grid(self, rows, slot, flip=False, slot_fn=None):
        for i in range(len(rows) - 1):
            for j in range(len(rows[i]) - 1):
                q = [rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]]
                if flip:
                    q.reverse()
                self.face(q, slot_fn(i, j) if slot_fn else slot)

    def finish(self, smooth_angle=35.0, origin=(0, 0, 0), keep=()):
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        uv = self.bm.loops.layers.uv.new("UVMap")
        for f in self.bm.faces:
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            for loop in f.loops:
                co = loop.vert.co
                loop[uv].uv = (co.y, co.z) if ax == 0 else ((co.x, co.z) if ax == 1 else (co.x, co.y))
        self.bm.to_mesh(me)
        self.bm.free()
        obj = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(obj)
        used = sorted({p.material_index for p in me.polygons})
        remap = {old: new for new, old in enumerate(used)}
        for name in [SLOTS[i] for i in used]:
            me.materials.append(bpy.data.materials.get(name) or bpy.data.materials.new(name))
        for p in me.polygons:
            p.material_index = remap[p.material_index]
        # pc/boat-slots: one slot per pack (a mast keeps its aluminium: M_BoatMast bends it).
        pack_slots(me, keep=keep)
        ox, oy, oz = origin
        me.transform(Matrix.Translation((-ox, oy, -oz)))
        obj.location = (ox, -oy, oz)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(smooth_angle))
        except Exception:
            pass
        obj.select_set(False)
        return obj


def box(m, c, size, slot, yaw=0.0):
    cx, cy, cz = c
    sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
    cs, sn = math.cos(yaw), math.sin(yaw)

    def P(dx, dy, dz):
        return (cx + dx * cs - dy * sn, cy + dx * sn + dy * cs, cz + dz)
    p = [P(-sx, -sy, -sz), P(sx, -sy, -sz), P(sx, sy, -sz), P(-sx, sy, -sz),
         P(-sx, -sy, sz), P(sx, -sy, sz), P(sx, sy, sz), P(-sx, sy, sz)]
    # Wound for Unreal's axes: Mesh.v mirrors Y into Blender, which turns each face over, so list them clockwise here
    # (counter-clockwise lists made every box inside out: cockpit seats you could see the water through).
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        m.face([p[i] for i in reversed(f)], slot)


def tube(m, path, radius, slot, sides=10, cap=True):
    pts = [Vector(p) for p in path]
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(a).normalized()
        w = t.cross(u).normalized()
        rings.append([tuple(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * radius) for k in range(sides + 1)])
    m.grid(rings, slot)
    if cap:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            r = ring[:-1]
            m.face(list(reversed(r)) if rev else r, slot)


def naca_loop(chord, thickness, n=20):
    pts = []
    for i in range(n + 1):
        t = 0.5 * (1 - math.cos(math.pi * i / n))
        y = 5 * thickness * (0.2969 * math.sqrt(t) - 0.1260 * t - 0.3516 * t * t + 0.2843 * t ** 3 - 0.1036 * t ** 4)
        pts.append((t * chord, y * chord))
    return pts + [(x, -y) for (x, y) in reversed(pts[1:-1])]


def foil(m, sections, slot, thickness=0.12, y0=0.0):
    """A vertical foil through (z, leading edge x, chord) sections."""
    rings = []
    for z, le_x, chord in sections:
        loop = naca_loop(chord, thickness)
        rings.append([(le_x - x, y0 + y, z) for (x, y) in loop] + [(le_x - loop[0][0], y0 + loop[0][1], z)])
    m.grid(rings, slot)
    m.face(rings[0][:-1], slot)
    m.face(list(reversed(rings[-1][:-1])), slot)


SOCKETS, OWNER = {}, {}


def socket(name, p, owner="Hull"):
    SOCKETS[name] = [round(p[0] * 100, 2), round(p[1] * 100, 2), round(p[2] * 100, 2)]
    OWNER[name] = f"SM_{TAG}_{owner}"


def stations(x0, x1, n, bias=1.0):
    return [x0 + (x1 - x0) * ((i / n) ** bias) for i in range(n + 1)]


hull = Mesh(f"SM_{TAG}_Hull")


# ---------------------------------------------------------------- shells

def shell(H):
    """One hull's shell from transom to stem, paint lines split exactly (keelboats: antifouling, boot and cove stripes)."""
    stern, bow = H.h["stern_x"], H.h["bow_x"]
    n = 110
    xs = [stern + (bow - stern) * (0.5 - 0.5 * math.cos(math.pi * (i / n) ** 0.85)) for i in range(n + 1)]
    paint = SPEC["paint"]
    af, bt = (0.05, 0.11) if paint else (0.03, 0.03)
    rows = []
    for x in xs:
        s = H.sheer(x)
        d = H.keel_line_depth(x)
        # A fixed number of rows per station (the grid needs it): uniform in r across the flat of the bottom, uniform
        # in z through the turn of the bilge, then the paint bands and the topsides.
        r_af = H.r_at_z(x, af)
        levels = [r_af * k / 12 for k in range(12)] + [H.r_at_z(x, -d + (af + d) * k / 16) for k in range(1, 16)]
        for z0, z1, cnt in ((af, bt, 2), (bt, s - 0.07, 9), (s - 0.07, s - 0.05, 1), (s - 0.05, s, 2)):
            for k in range(cnt):
                levels.append(H.r_at_z(x, z0 + (z1 - z0) * k / cnt))
        levels.append(1.0)
        rows.append(sorted(levels))
    nr = len(rows[0])
    pts = [[H.section_point(x, r)[0] for r in rs] for x, rs in zip(xs, rows)]
    for i in range(len(pts) - 1):
        for j in range(nr - 1):
            zc = 0.25 * (pts[i][j][2] + pts[i][j + 1][2] + pts[i + 1][j][2] + pts[i + 1][j + 1][2])
            s = H.sheer(0.5 * (xs[i] + xs[i + 1]))
            if paint and zc < af:
                slot = "Antifouling"
            elif paint and zc < bt:
                slot = "Bootstripe"
            elif paint and s - 0.07 < zc < s - 0.05:
                slot = "CoveStripe"
            else:
                slot = "Topsides"
            q = [pts[i][j], pts[i + 1][j], pts[i + 1][j + 1], pts[i][j + 1]]
            for side in (1, -1):
                qq = [(p[0], H.cy + side * (p[1] - H.cy), p[2]) for p in q]
                if side < 0:
                    qq.reverse()
                hull.face(qq, slot)
    tr = pts[0]
    loop = tr + [(p[0], H.cy - (p[1] - H.cy), p[2]) for p in reversed(tr[:-1])]
    hull.face(list(reversed(loop)), "Topsides")
    return xs


def deck(H, cuts=(), slot="NonSkid"):
    """The crowned deck over a hull, leaving out the rectangles in `cuts` (x0, x1, y0, y1), with a smooth margin."""
    stern, bow = H.h["stern_x"], H.h["bow_x"] - 0.003
    xs = set(stations(stern, bow, 48))
    mhb = H.h["max_half_beam"]
    ys = set(H.cy + mhb * (-1 + 2 * k / 20) for k in range(21))
    for (x0, x1, y0, y1) in cuts:
        xs.update((x0, x1))
        ys.update((y0, y1))
    xs, ys = sorted(xs), sorted(ys)

    def P(x, y):
        b = H.sharp_half_beam(x)
        yy = min(max(y, H.cy - b), H.cy + b)
        return (x, yy, H.deck_z(x, yy))
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cyy = 0.5 * (xs[i] + xs[i + 1]), 0.5 * (ys[j] + ys[j + 1])
            if any(x0 < cx < x1 and y0 < cyy < y1 for (x0, x1, y0, y1) in cuts):
                continue
            edge = abs(cyy - H.cy) > H.sharp_half_beam(cx) - 0.08
            hull.face([P(xs[i], ys[j]), P(xs[i], ys[j + 1]), P(xs[i + 1], ys[j + 1]), P(xs[i + 1], ys[j])], "Deck" if edge else slot)
    # Rubrail along the hull-deck joint.
    for side in (1, -1):
        rail = [(x, H.cy + side * (H.sharp_half_beam(x) + 0.006), H.sheer(x) - 0.008) for x in stations(stern + 0.02, bow - 0.06, 40)]
        tube(hull, rail, 0.011 if H.h["sheer_z"] < 0.8 else 0.02, "Rubrail", 8)


def cockpit(H, spec):
    """A self-draining well: walls down from the deck to the sole, seats along both sides."""
    x0, x1, w, depth = spec
    xs = stations(x0, x1, 12)
    for side in (1, -1):
        y = H.cy + side * w
        wall = [[(x, y, H.deck_z(x, y)), (x, y, H.deck_z(x, y) - depth)] for x in xs]
        hull.grid(wall, "Deck", flip=side > 0)
    for x, sgn in ((x0, 1), (x1, -1)):
        pts = [(x, H.cy - w, H.deck_z(x, H.cy - w)), (x, H.cy + w, H.deck_z(x, H.cy + w)), (x, H.cy + w, H.deck_z(x, H.cy + w) - depth), (x, H.cy - w, H.deck_z(x, H.cy - w) - depth)]
        hull.face(pts if sgn < 0 else list(reversed(pts)), "Deck")
    sole = lambda x: H.deck_z(x, H.cy + w) - depth
    hull.face([(x0, H.cy + w, sole(x0)), (x1, H.cy + w, sole(x1)), (x1, H.cy - w, sole(x1)), (x0, H.cy - w, sole(x0))], "NonSkid")  # faces up
    if depth > 0.3:
        for side in (1, -1):
            seat_w = 0.34 * min(1.0, w / 0.6)
            yc = H.cy + side * (w - seat_w / 2)
            zc = sole(0.5 * (x0 + x1)) + 0.5 * (depth - 0.14)
            box(hull, (0.5 * (x0 + x1) - 0.05, yc, zc), (x1 - x0 - 0.3, seat_w, depth - 0.14), "Deck")


def cabin(H, spec):
    """A cabin trunk: sides from the deck up, a crowned top, a raked front, the companionway hatch aft, windows."""
    x0, x1, hw, h = spec
    xs = stations(x0, x1, 16)
    top = lambda x: H.deck_z(x, H.cy) + h * (1.0 - 0.25 * max(0.0, (x - (x0 + 0.7 * (x1 - x0))) / (0.3 * (x1 - x0))))
    half = lambda x: min(hw, H.sharp_half_beam(x) - 0.3)
    for side in (1, -1):
        wall = [[(x, H.cy + side * half(x), H.deck_z(x, H.cy + side * half(x)) - 0.02), (x, H.cy + side * half(x) * 0.93, top(x) - 0.04)] for x in xs]
        hull.grid(wall, "Topsides", flip=side > 0)
        if TAG in ("Catalina22", "Catalina30"):
            # Fleet hero: the Catalinas' smoked windows, rounded ends in aluminium frames (the 22's two long ones a side,
            # the 30's three).
            for (fa, fb) in (((0.16, 0.44), (0.5, 0.78)) if TAG == "Catalina22" else ((0.12, 0.28), (0.34, 0.52), (0.58, 0.76))):
                wa, wb = x0 + fa * (x1 - x0), x0 + fb * (x1 - x0)
                zc = lambda x: H.deck_z(x, H.cy) + 0.62 * h   # noqa: E731
                r = 0.16 * h
                loop = []
                for (cx, a0) in ((wb - r, -90.0), (wa + r, 90.0)):
                    for k in range(9):
                        a = math.radians(a0 + 180.0 * k / 8)
                        x = cx + r * math.cos(a)
                        loop.append((x, H.cy + side * (half(x) * 0.968 + 0.006), zc(x) + r * math.sin(a)))
                hull.face(loop if side < 0 else list(reversed(loop)), "CabinWindow")
                tube(hull, loop + loop[:1], 0.008, "Aluminium", 5, cap=False)
            continue
        # Ports: a long dark window band in the trunk side.
        wx0, wx1 = x0 + 0.2 * (x1 - x0), x0 + 0.78 * (x1 - x0)
        for k in range(10):
            xa, xb = wx0 + (wx1 - wx0) * k / 10, wx0 + (wx1 - wx0) * (k + 1) / 10
            za, zb = H.deck_z(xa, H.cy) + 0.45 * h, H.deck_z(xa, H.cy) + 0.8 * h
            ya, yb = H.cy + side * (half(xa) * 0.965 + 0.004), H.cy + side * (half(xb) * 0.965 + 0.004)
            q = [(xa, ya, za), (xb, yb, za), (xb, yb, zb), (xa, ya, zb)]
            hull.face(q if side < 0 else list(reversed(q)), "CabinWindow")
    rows = []
    for x in xs:
        hb = half(x) * 0.93
        rows.append([(x, H.cy + hb * v, top(x) - 0.04 + 0.035 * (1 - v * v)) for v in [-1 + 2 * k / 10 for k in range(11)]])
    hull.grid(rows, "NonSkid", flip=True)
    for x, rev in ((x0, False), (x1, True)):
        hb = half(x)
        pts = [(x, H.cy - hb, H.deck_z(x, H.cy - hb) - 0.02)] + [(x, H.cy + hb * 0.93 * v, top(x) - 0.04 + 0.035 * (1 - v * v)) for v in [-1 + 2 * k / 10 for k in range(11)]] + [(x, H.cy + hb, H.deck_z(x, H.cy + hb) - 0.02)]
        hull.face(list(reversed(pts)) if rev else pts, "Topsides")
    # Companionway hatch and washboard; forward hatch.
    if TAG in ("Catalina22", "Catalina30"):
        # Fleet hero: teak drop boards in the companionway (three, their edges proud), and a teak eyebrow along both
        # edges of the trunk top.
        for k in range(3):
            zk = H.deck_z(x0, H.cy) + 0.1 * h + k * 0.27 * h
            box(hull, (x0 + 0.012, H.cy, zk + 0.13 * h), (0.025, 0.48 - 0.03 * k, 0.24 * h), "Wood")
            box(hull, (x0 + 0.03, H.cy, zk + 0.255 * h), (0.012, 0.47 - 0.03 * k, 0.012), "Wood")
        for side in (1, -1):
            tube(hull, [(x, H.cy + side * half(x) * 0.935, top(x) - 0.035) for x in stations(x0 + 0.02, x1 - 0.02, 14)], 0.01, "Wood", 5, cap=False)
    else:
        box(hull, (x0 + 0.01, H.cy, H.deck_z(x0, H.cy) + 0.5 * h), (0.03, 0.5, h * 0.8), "BlackPlastic")
    box(hull, (x0 + 0.45, H.cy, top(x0 + 0.45) + 0.01), (0.8, 0.62, 0.04), "Deck")
    box(hull, (x1 + 0.45, H.cy, H.deck_z(x1 + 0.45, H.cy) + 0.04), (0.5, 0.5, 0.06), "CabinWindow")
    # Grab rails on the top.
    for side in (1, -1):
        tube(hull, [(x0 + 0.3, H.cy + side * half(x0) * 0.75, top(x0 + 0.3)), (x1 - 0.4, H.cy + side * half(x1) * 0.6, top(x1 - 0.4))], 0.015, "Wood", 6)
    return top, half


def lifelines(H, x_from, x_to):
    """Stanchions every 0.9 m with two lifelines, a bow pulpit and a stern pushpit."""
    hgt = 0.6 if H.h["sheer_z"] < 0.9 else 0.68
    xs = stations(x_from, x_to, max(2, int((x_to - x_from) / 0.9)))
    for side in (1, -1):
        posts = [(x, H.cy + side * (H.sharp_half_beam(x) - 0.05), H.deck_z(x, H.cy + side * (H.sharp_half_beam(x) - 0.05))) for x in xs]
        for (x, y, z) in posts:
            tube(hull, [(x, y, z), (x, y, z + hgt)], 0.012, "Stainless", 6)
            box(hull, (x, y, z + 0.02), (0.07, 0.05, 0.04), "Stainless")              # boats 11: stanchion base
        for f in (0.5, 1.0):
            tube(hull, [(x, y, z + hgt * f) for (x, y, z) in posts], 0.0035, "Stainless", 4)
    bow = H.h["bow_x"]
    ring = [(x_to + (bow - 0.1 - x_to) * math.sin(math.pi / 2 * k / 8), H.cy + (H.sharp_half_beam(x_to) - 0.05) * math.cos(math.pi / 2 * k / 8), H.deck_z(x_to, H.cy) + hgt) for k in range(9)]
    tube(hull, ring + [(p[0], H.cy - (p[1] - H.cy), p[2]) for p in reversed(ring[:-1])], 0.014, "Stainless", 8)
    st = H.h["stern_x"]
    hb = H.sharp_half_beam(st) - 0.06
    tube(hull, [(x_from, H.cy + hb, H.deck_z(x_from, H.cy) + hgt), (st + 0.05, H.cy + hb, H.deck_z(st, H.cy) + hgt), (st + 0.05, H.cy - hb, H.deck_z(st, H.cy) + hgt),
                (x_from, H.cy - hb, H.deck_z(x_from, H.cy) + hgt)], 0.014, "Stainless", 8)
    for y in (hb, -hb):
        tube(hull, [(st + 0.05, H.cy + y, H.deck_z(st, H.cy)), (st + 0.05, H.cy + y, H.deck_z(st, H.cy) + hgt)], 0.014, "Stainless", 6)


def cleat(x, y, z, yaw=0.0, length=0.2):
    """A horn cleat: a low base and the horns across it (aluminium)."""
    box(hull, (x, y, z + 0.012), (length * 0.45, 0.035, 0.024), "Aluminium", yaw)
    box(hull, (x, y, z + 0.04), (length, 0.03, 0.022), "Aluminium", yaw)


def keelboat_deck_detail(H, top, half, cb, mast_x, st, bw):
    """Boats & models 9 (the boats "read flat"): what a keelboat's deck carries that the clean model didn't. An aluminium
    toe rail along the sheer, mooring cleats on the foredeck and both quarters with fairleads at the bow, the halyards
    led from the mast step aft along the cabin top to clutches beside the companionway, and their coiled tails."""
    xs = stations(st + 0.12, bw - 0.3, 48)
    for side in (1, -1):
        rail = []
        for x in xs:
            y = H.cy + side * (H.sharp_half_beam(x) - 0.025)
            rail.append((x, y, H.deck_z(x, y) + 0.018))
        tube(hull, rail, 0.014, "Aluminium", 6)
    for (cx, side) in ((bw - 0.55, 1), (bw - 0.55, -1), (st + 0.35, 1), (st + 0.35, -1)):
        y = H.cy + side * (H.sharp_half_beam(cx) - 0.18)
        cleat(cx, y, H.deck_z(cx, y), 0.0)
    for side in (1, -1):                       # bow fairleads (chocks) on the toe rail
        x = bw - 0.42
        y = H.cy + side * (H.sharp_half_beam(x) - 0.03)
        box(hull, (x, y, H.deck_z(x, y) + 0.035), (0.12, 0.04, 0.035), "Aluminium")
    # Halyards and control lines: three a side, from turning blocks at the mast step aft to clutches by the hatch.
    x0 = cb[0]
    for side in (1, -1):
        for k in range(3):
            dy = side * (0.07 + 0.035 * k)
            yc = H.cy + side * (0.24 + 0.035 * k) * min(1.0, half(x0 + 0.35) / 0.55)
            xm = mast_x - 0.12
            box(hull, (xm, H.cy + dy, top(xm) + 0.02), (0.05, 0.025, 0.035), "BlackPlastic")       # turning block
            xs_l = stations(xm - 0.04, x0 + 0.38, 10)
            line = [(x, H.cy + dy + (yc - H.cy - dy) * ((x - xm) / (x0 + 0.38 - xm)) ** 1.5, top(x) + 0.012) for x in xs_l]
            tube(hull, line, 0.005, "Rope", 4)
            box(hull, (x0 + 0.3, yc, top(x0 + 0.3) + 0.022), (0.11, 0.03, 0.04), "BlackPlastic")    # clutch
        # The tails, flaked in a heap on the cabin top beside the hatch.
        for k in range(3):
            c = (x0 + 0.12 - 0.04 * k, H.cy + side * (0.3 + 0.02 * k), top(x0 + 0.12) + 0.008 + 0.009 * k)
            ring = [(c[0] + 0.09 * math.cos(2 * math.pi * j / 14), c[1] + 0.07 * math.sin(2 * math.pi * j / 14), c[2]) for j in range(15)]
            tube(hull, ring, 0.005, "Rope", 4, cap=False)


def keelboat_cockpit_detail(H, ck, cb, top, half, st, bw):
    """Boats 11: the cockpit, foredeck and stern fittings of a cruising keelboat, from Catalina 22 and 30 photos: seat
    locker lids with hasps, cockpit drains, jib-sheet horn cleats behind the winches, slide-hatch rails, an anchor
    locker hatch and a bow roller, running lights on the pulpit and pushpit, and on the Catalina 30 a binnacle compass
    and a stern ladder."""
    x0, x1, w, depth = ck
    sole_z = lambda x: H.deck_z(x, H.cy + w) - depth
    seat_w = 0.34 * min(1.0, w / 0.6)
    seat_top = lambda x: sole_z(x) + depth - 0.14
    for side in ((1, -1) if TAG == "Catalina30" else (-1,)):
        lx0, lx1 = x0 + 0.35, x0 + 0.35 + min(0.9, (x1 - x0) * 0.4)
        yc = H.cy + side * (w - seat_w / 2)
        zc = seat_top(0.5 * (lx0 + lx1)) + 0.003
        box(hull, (0.5 * (lx0 + lx1), yc, zc), (lx1 - lx0, seat_w - 0.06, 0.008), "Deck")              # lid
        box(hull, (lx0 + 0.02, yc, zc + 0.008), (0.03, seat_w - 0.1, 0.012), "Stainless")              # hinge line
        box(hull, (lx1 - 0.03, H.cy + side * (w - seat_w + 0.04), zc + 0.01), (0.05, 0.03, 0.015), "BlackPlastic")  # hasp
    for side in (1, -1):
        tube(hull, [(x0 + 0.08, side * (w - 0.08), sole_z(x0) + 0.001), (x0 + 0.08, side * (w - 0.08), sole_z(x0) + 0.006)], 0.03, "BlackPlastic", 10)
        wx = SPEC["winch_x"]
        y = side * (w + 0.13)
        cleat(wx - 0.28, y, H.deck_z(wx - 0.28, y), 0.0, 0.15)
    # slide-hatch rails either side of the companionway hatch
    for side in (1, -1):
        tube(hull, [(cb[0] + 0.02, side * 0.34, top(cb[0] + 0.05) + 0.012), (cb[0] + 0.9, side * 0.34, top(cb[0] + 0.9) + 0.012)], 0.012, "Wood", 6)
    # foredeck: anchor locker lid and a bow roller at the stem
    ax = bw - 0.75
    box(hull, (ax, 0, H.deck_z(ax, 0) + 0.006), (0.42, 0.5, 0.014), "Deck")
    box(hull, (ax - 0.2, 0, H.deck_z(ax - 0.2, 0) + 0.016), (0.03, 0.4, 0.015), "Stainless")
    if TAG != "Corsair880":                    # the Corsair's bowsprit takes the stem
        box(hull, (bw - 0.22, 0, H.deck_z(bw - 0.22, 0) + 0.03), (0.3, 0.07, 0.05), "Stainless")
        tube(hull, [(bw - 0.12, -0.03, H.deck_z(bw - 0.12, 0) + 0.05), (bw - 0.12, 0.03, H.deck_z(bw - 0.12, 0) + 0.05)], 0.025, "BlackPlastic", 10)
    # running lights: a bicolour on the pulpit, a white stern light on the pushpit
    hgt = 0.6 if H.h["sheer_z"] < 0.9 else 0.68
    box(hull, (bw - 0.35, 0, H.deck_z(bw - 0.35, 0) + hgt + 0.03), (0.07, 0.09, 0.05), "BlackPlastic")
    box(hull, (st + 0.06, 0, H.deck_z(st, 0) + hgt + 0.03), (0.05, 0.06, 0.05), "BlackPlastic")
    if TAG == "Catalina30":
        wxp = SPEC["wheel"]
        sz = H.deck_z(wxp, w) - depth + 1.06
        tube(hull, [(wxp, 0, sz), (wxp, 0, sz + 0.07)], 0.08, "BlackPlastic", 16)                      # compass
        for k in range(4):                                                                           # stern ladder
            z = H.sheer(st) - 0.15 - 0.22 * k
            tube(hull, [(st - 0.03, -0.17, z), (st - 0.03, 0.17, z)], 0.012, "Stainless", 6)
        for y in (-0.17, 0.17):
            tube(hull, [(st - 0.03, y, H.sheer(st)), (st - 0.03, y, H.sheer(st) - 0.8)], 0.012, "Stainless", 6)


def winch(x, y, z, r=0.055):
    tube(hull, [(x, y, z), (x, y, z + 0.11)], r, "Stainless", 14)
    tube(hull, [(x, y, z + 0.11), (x, y, z + 0.13)], r * 0.6, "BlackPlastic", 10)


def board(Hh, f, deepest):
    """A keel or daggerboard: NACA section from inside the hull down to the deepest point."""
    cx, cy, cz = f["center"]
    chord = f["chord"]
    le = cx + 0.25 * chord
    z_top = Hh.bottom_z(cx, cy) + 0.05
    secs = []
    for k in range(9):
        t = k / 8
        z = z_top + (deepest - z_top) * t
        c = chord * (1.0 - 0.25 * t if f["role"] == "keel" else 1.0)
        secs.append((z, le - 0.1 * t * chord if f["role"] == "keel" else le, c))
    foil(hull, secs, "Keel", 0.12 if f["role"] == "keel" else 0.08, cy)
    if f["role"] == "keel" and SPEC["paint"] and deepest < -1.2:
        # A bulb on the deeper fins (the Catalina 30's lead), faired into the tip.
        tube(hull, [(le - 0.05, cy, deepest + 0.08), (le - chord * 1.05, cy, deepest + 0.1)], 0.09, "Keel", 12)


def dinghy_detail(H, ck, f, mast_x, mast_step_z, traveler):
    """Boats 11: what a Sunfish or ILCA carries on deck that the clean model left out, from class photos. The board
    standing in its trunk with a grip, the self-bailer and drain in the well, the mainsheet's ratchet block and its
    blocks on the traveler, deck control lines to cam cleats, a bow handle and the transom drain plug; the Sunfish's
    V splash guard and halyard cleat, the ILCA's control lines and the shock cord on its hiking strap."""
    x0, x1, w, depth = ck
    sole = lambda x: H.deck_z(x, 0) - depth
    bx, chord = f["center"][0], f["chord"]
    dz = H.deck_z(bx, 0)
    # the daggerboard (Sunfish: varnished wood; ILCA: white plastic centreboard) a hand's width proud, with a grip
    board_slot = "Wood" if TAG == "Sunfish" else "Deck"
    box(hull, (bx, 0, dz + 0.06), (chord * 0.92, 0.018, 0.12), board_slot)
    box(hull, (bx - chord * 0.25, 0, dz + 0.135), (0.10, 0.03, 0.03), "BlackPlastic")
    # well: auto-bailer and drain plug in the sole, a non-skid pad is the sole's own slot already
    xb = x0 + 0.18
    box(hull, (xb, 0.0, sole(xb) + 0.006), (0.12, 0.07, 0.012), "BlackPlastic")
    tube(hull, [(xb + 0.2, 0.12, sole(xb + 0.2)), (xb + 0.2, 0.12, sole(xb + 0.2) + 0.008)], 0.02, "BlackPlastic", 10)
    # mainsheet: blocks on the traveler bridle, a swivel ratchet block in the well (ILCA) or on the aft deck (Sunfish)
    tx, tz, tw = traveler
    box(hull, (tx, 0.0, tz + 0.03), (0.05, 0.03, 0.05), "BlackPlastic")
    if TAG == "ILCA7":
        rx, rz = 0.5 * (x0 + x1), sole(0.5 * (x0 + x1))
        tube(hull, [(rx, 0, rz), (rx, 0, rz + 0.12)], 0.012, "Stainless", 8)
        box(hull, (rx, 0, rz + 0.16), (0.08, 0.03, 0.08), "BlackPlastic")
    else:
        rx = x0 - 0.06
        box(hull, (rx, 0, H.deck_z(rx, 0) + 0.035), (0.06, 0.03, 0.07), "BlackPlastic")
    # deck control lines to cam cleats either side of the well's forward end (ILCA: cunningham, outhaul, vang;
    # Sunfish: the halyard to a horn cleat and the sail's bow line)
    if TAG == "ILCA7":
        for side in (1, -1):
            for k in range(3):
                cx, cy = x1 + 0.06, side * (0.09 + 0.05 * k)
                box(hull, (cx, cy, H.deck_z(cx, cy) + 0.012), (0.06, 0.035, 0.024), "BlackPlastic")
                line = [(mast_x - 0.08, side * 0.03, mast_step_z + 0.02), (bx + 0.25, side * (0.05 + 0.02 * k), H.deck_z(bx + 0.25, 0) + 0.012),
                        (cx + 0.03, cy, H.deck_z(cx, cy) + 0.02)]
                tube(hull, line, 0.003, "Rope", 4, cap=False)
        # shock cord from the transom holding the hiking strap up off the sole
        tube(hull, [(x0 + 0.1, 0, sole(x0) + 0.07), (x0 - 0.25, 0, H.deck_z(x0 - 0.25, 0) + 0.005)], 0.003, "BlackPlastic", 4, cap=False)
    else:
        # V splash guard ahead of the well, white moulding
        sx = x1 + 0.10
        for side in (1, -1):
            a = (sx + 0.22, 0.0)
            b = (sx, side * (w + 0.06))
            n = 8
            for k in range(n):
                t0, t1 = k / n, (k + 1) / n
                pa = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                pb = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                za, zb = H.deck_z(pa[0], pa[1]), H.deck_z(pb[0], pb[1])
                q = [(pa[0], pa[1], za), (pb[0], pb[1], zb), (pb[0], pb[1], zb + 0.075 - 0.025 * t1), (pa[0], pa[1], za + 0.075 - 0.025 * t0)]
                hull.face(q if side > 0 else list(reversed(q)), "Deck")
                hull.face(list(reversed(q)) if side > 0 else q, "Deck")
        # Fleet hero: the well's moulded lip, a rounded rim along its edge (the deck's own gelcoat), and the hiking strap's
        # worn webbing ends screwed to the sole.
        rim, rr = [], 0.05
        for (cx, cy, a0) in ((x1 - rr, w - rr, 0.0), (x0 + rr, w - rr, 90.0), (x0 + rr, -w + rr, 180.0), (x1 - rr, -w + rr, 270.0)):
            for k in range(5):
                a = math.radians(a0 + 90.0 * k / 4)
                px, py = cx + rr * math.cos(a), cy + rr * math.sin(a)
                rim.append((px, py, H.deck_z(px, py) + 0.004))
        tube(hull, rim + rim[:1], 0.011, "Deck", 6, cap=False)
        for xs_ in (x0 + 0.06, x1 - 0.06):
            box(hull, (xs_, 0, sole(xs_) + 0.004), (0.05, 0.05, 0.008), "Graphics")
        cleat(x1 + 0.05, -0.18, H.deck_z(x1 + 0.05, -0.18), 0.0, 0.12)
        line = [(mast_x - 0.05, -0.03, mast_step_z + 0.04), (x1 + 0.4, -0.12, H.deck_z(x1 + 0.4, -0.12) + 0.01), (x1 + 0.08, -0.18, H.deck_z(x1 + 0.08, -0.18) + 0.045)]
        tube(hull, line, 0.003, "Rope", 4, cap=False)
    # bow handle (inside the stem so LOA is untouched) and the transom drain plug
    bwx = H.h["bow_x"] - 0.22
    tube(hull, [(bwx - 0.06, 0, H.deck_z(bwx - 0.06, 0)), (bwx - 0.03, 0, H.deck_z(bwx, 0) + 0.04),
                (bwx + 0.05, 0, H.deck_z(bwx, 0) + 0.04), (bwx + 0.08, 0, H.deck_z(bwx + 0.08, 0))], 0.007, "Stainless", 6, cap=False)
    st = H.h["stern_x"]
    tube(hull, [(st + 0.004, 0.0, H.sheer(st) - 0.06), (st - 0.006, 0.0, H.sheer(st) - 0.06)], 0.014, "BlackPlastic", 8)


def hobie_detail(fb, rb, bz, inner, traveler):
    """Boats 11: a Hobie 16's fittings from class photos. The trampoline laced to the beams with shock cord, the dolphin
    striker under the front beam with its wire to the beam ends, the mast ball on its step, the mainsheet car on the
    rear beam, jib cars on short tracks on the tramp, gudgeons and rudder castings on each transom, shroud adjusters at
    the chainplates, inspection ports and drain plugs on each hull."""
    # lacing: a zigzag of shock cord between each beam and the trampoline's hemmed edge
    for bx, ex in ((fb, fb - 0.05), (rb, rb + 0.05)):
        w = inner(bx) - 0.06
        n = int(2 * w / 0.09)
        zig = [(bx if k % 2 == 0 else ex, -w + 2 * w * k / n, bz + 0.035) for k in range(n + 1)]
        tube(hull, zig, 0.003, "Rope", 4, cap=False)
    # dolphin striker: a strut under the front beam's middle and its wire to the beam ends at the hulls
    sz = bz - 0.32
    tube(hull, [(fb, 0, bz - 0.045), (fb, 0, sz)], 0.014, "Aluminium", 8)
    for side in (1, -1):
        tube(hull, [(fb, 0, sz), (fb, side * (inner(fb) - 0.02), bz - 0.03)], 0.003, "Stainless", 4, cap=False)
    # the mast ball on its step
    tube(hull, [(fb, 0, bz + 0.06), (fb, 0, bz + 0.1)], 0.035, "BlackPlastic", 12)
    # mainsheet traveler car and its block on the rear beam
    box(hull, (rb + 0.02, 0, bz + 0.075), (0.09, 0.07, 0.04), "BlackPlastic")
    box(hull, (rb + 0.02, 0, bz + 0.13), (0.05, 0.03, 0.07), "BlackPlastic")
    for side in (1, -1):
        box(hull, (rb + 0.02, side * traveler[2], bz + 0.065), (0.04, 0.04, 0.03), "BlackPlastic")    # end stops
    for Hh, side in ((HS[1], 1), (HS[0], -1)):
        # jib car on a short track at the lead, laid on the tramp
        lx, ly = rb + 0.9, Hh.cy - side * 0.25
        box(hull, (lx, ly, bz + 0.04), (0.45, 0.03, 0.012), "Aluminium")
        box(hull, (lx, ly, bz + 0.065), (0.07, 0.04, 0.04), "BlackPlastic")
        # shroud adjuster: a stainless plate rising from the chainplate at the hull's outer sheer
        cx = mast_x - 0.05
        cy = Hh.cy + side * (Hh.sharp_half_beam(cx) - 0.03)
        box(hull, (cx, cy, Hh.sheer(cx) + 0.07), (0.03, 0.006, 0.14), "Stainless")
        # inspection ports fore and aft of the beams, drain plug on the transom
        for px in (fb + 0.7, rb - 0.45):
            pz = Hh.deck_z(px, Hh.cy)
            tube(hull, [(px, Hh.cy, pz - 0.002), (px, Hh.cy, pz + 0.008)], 0.065, "BlackPlastic", 14)
        st = Hh.h["stern_x"]
        tube(hull, [(st + 0.004, Hh.cy, Hh.sheer(st) - 0.08), (st - 0.006, Hh.cy, Hh.sheer(st) - 0.08)], 0.012, "BlackPlastic", 8)
        # the rudder casting's gudgeons on the transom
        for gz in (Hh.sheer(st) - 0.04, Hh.sheer(st) - 0.24):
            box(hull, (st + 0.015, Hh.cy, gz), (0.03, 0.06, 0.03), "Stainless")
        # Fleet hero: the cast aluminium beam ends (the corner castings bolted to each hull), the hull's coloured stripe
        # along the sheer, and the trapeze shock cords' deck eyes beside the tramp.
        for bx in (fb, rb):
            by = Hh.cy - side * 0.02
            box(hull, (bx, by, bz + 0.005), (0.2, 0.16, 0.11), "Aluminium")
        xs_ = stations(Hh.h["stern_x"] + 0.15, Hh.h["bow_x"] - 0.5, 36)
        stripe = [(x, Hh.cy + side * (Hh.sharp_half_beam(x) + 0.004), Hh.sheer(x) - 0.06) for x in xs_]
        tube(hull, stripe, 0.012, "Graphics", 4, cap=False)
        ex = mast_x - 0.35
        box(hull, (ex, Hh.cy - side * 0.12, bz + 0.03), (0.04, 0.02, 0.02), "Stainless")
    # Fleet hero: the righting line's bag on the front beam's middle.
    box(hull, (fb - 0.08, 0, bz + 0.03), (0.12, 0.3, 0.06), "BlackPlastic")


def corsair_detail(ck, cb, top, half, st, bw):
    """Boats 11: the Corsair 880's own fittings from class photos, besides the keelboat set it shares: the folding akas'
    hinge castings at the main hull and the floats, net lacing along the hull and float edges, and float deck hatches
    with a bow eye on each float."""
    for ax in SPEC["akas"]:
        for Hh in HS[1:]:
            side = 1 if Hh.cy > 0 else -1
            y0 = side * (MAIN.sharp_half_beam(ax) - 0.1)
            box(hull, (ax, y0, MAIN.deck_z(ax, y0) - 0.02), (0.26, 0.16, 0.1), "Aluminium")             # fold hinge
            y1 = Hh.cy - side * (Hh.sharp_half_beam(ax) - 0.15)
            box(hull, (ax, y1, Hh.deck_z(ax, Hh.cy) + 0.02), (0.24, 0.14, 0.08), "Aluminium")             # float socket
    a0, a1 = SPEC["akas"]
    for Hh in HS[1:]:
        side = 1 if Hh.cy > 0 else -1
        for edge in ("main", "float"):
            pts = []
            xs = stations(a1 + 0.1, a0 - 0.1, 24)
            for k, x in enumerate(xs):
                if edge == "main":
                    y = side * (MAIN.sharp_half_beam(x) - 0.05)
                    z = MAIN.deck_z(x, y) - 0.02
                    d = side * (0.06 if k % 2 else 0.0)
                else:
                    y = Hh.cy - side * (Hh.sharp_half_beam(x) - 0.1)
                    z = Hh.deck_z(x, Hh.cy) - 0.03
                    d = -side * (0.06 if k % 2 else 0.0)
                pts.append((x, y + d, z + (0.01 if k % 2 else 0.0)))
            tube(hull, pts, 0.003, "Rope", 4, cap=False)
        for hx in (a0 + 0.6, a1 - 0.5):
            box(hull, (hx, Hh.cy, Hh.deck_z(hx, Hh.cy) + 0.008), (0.42, 0.32, 0.016), "CabinWindow")    # float hatch
        fbx = Hh.h["bow_x"] - 0.12
        tube(hull, [(fbx, Hh.cy, Hh.deck_z(fbx, Hh.cy)), (fbx, Hh.cy, Hh.deck_z(fbx, Hh.cy) + 0.04)], 0.012, "Stainless", 6)


def lagoon_detail(b0, b1, dz, inner, s0, s1, sw, roof):
    """Boats 11: the Lagoon 42's fittings from builder and charter photos. Long hull windows on each hull's outer side,
    mullions on the saloon glazing, the raised helm station at the aft bulkhead's starboard end (wheel, pod, seat), a
    cockpit table, solar panels on the bimini, flush deck hatches and mooring cleats on each hull, and the anchor
    windlass and bow roller on the forward crossbeam."""
    for Hh, side in ((HS[1], 1), (HS[0], -1)):
        # hull windows: three long dark panes along the outer topsides, under the sheer
        for (wx0, wx1) in ((1.6, 3.3), (-0.9, 1.2), (-3.4, -1.3)):
            rows = []
            for x in stations(wx0, wx1, 8):
                zt, zb = Hh.sheer(x) - 0.28, Hh.sheer(x) - 0.48
                rows.append([(x, Hh.cy + side * (Hh.half_beam(x, z) + 0.004), z) for z in (zb, zt)])
            hull.grid(rows, "CabinWindow", flip=side < 0)
        # flush hatches on the foredeck and a cleat at the bow and quarter
        for hx in (b1 + 0.6, b1 + 1.8):
            box(hull, (hx, Hh.cy, Hh.deck_z(hx, Hh.cy) + 0.008), (0.55, 0.55, 0.016), "CabinWindow")
        for cx in (Hh.h["bow_x"] - 0.7, Hh.h["stern_x"] + 0.45):
            cy = Hh.cy + side * (Hh.sharp_half_beam(cx) - 0.15)
            cleat(cx, cy, Hh.deck_z(cx, cy), 0.0, 0.3)
    # saloon mullions: dark frames between the side panes
    for side in (1, -1):
        for x in stations(s0 + 0.4, s1 - 0.5, 4):
            tube(hull, [(x, side * (sw + 0.008), dz + 0.55), (x, side * (sw + 0.008), roof - 0.15)], 0.02, "BlackPlastic", 4)
    # helm station (pc/lagoon-helm): raised on the starboard side at the coachroof's aft end, as on the real boat, so the
    # helmsman looks forward over the roof (at the old height, 0.49 m up, the view was the wheel and the bulkhead). A helm
    # deck 0.40 m over the bridgedeck with a step up from the cockpit; the seat on it, its cushion 0.86 m up (a seated eye
    # about 1.66 m, the roof 1.44 there); the pod and wheel out of the bulkhead, the hub 1.19 m up so the rim stays under
    # the eye. Fore and aft the seat and wheel are where they were (seat x s0 - 0.85, wheel s0 - 0.35).
    hx, hy, hz = s0 - 0.35, sw - 0.35, dz + 1.19
    hd = dz + 0.40                                                                              # the helm deck's top
    x0, x1 = hx - 0.85, s0 - 0.02
    box(hull, (0.5 * (x0 + x1), hy, 0.5 * (dz + hd)), (x1 - x0, 0.8, hd - dz), "Topsides")       # helm deck
    box(hull, (0.5 * (x0 + x1), hy, hd + 0.004), (x1 - x0 - 0.04, 0.76, 0.008), "NonSkid")
    box(hull, (x0 - 0.15, hy, dz + 0.10), (0.30, 0.8, 0.20), "Topsides")                        # the step up to it
    box(hull, (x0 - 0.15, hy, dz + 0.204), (0.26, 0.76, 0.008), "NonSkid")
    box(hull, (s0 - 0.12, hy, hz - 0.15), (0.25, 0.5, 0.45), "Topsides")                        # the pod
    box(hull, (s0 - 0.25, hy, hz + 0.12), (0.05, 0.35, 0.15), "BlackPlastic")                  # instruments
    r = 0.36
    rim = [(hx, hy + r * math.cos(2 * math.pi * k / 24), hz + r * math.sin(2 * math.pi * k / 24)) for k in range(25)]
    tube(hull, rim, 0.014, "Stainless", 8, cap=False)
    for k in range(5):
        a = 2 * math.pi * k / 5
        tube(hull, [(hx, hy, hz), (hx, hy + r * math.cos(a), hz + r * math.sin(a))], 0.008, "Stainless", 6)
    tube(hull, [(hx, hy, hz), (s0 - 0.25, hy, hz)], 0.025, "Stainless", 8)
    box(hull, (hx - 0.5, hy, hd + 0.42), (0.45, 0.6, 0.08), "SailCover")                      # helm seat cushion
    box(hull, (hx - 0.5, hy, hd + 0.19), (0.4, 0.55, 0.38), "Topsides")
    # cockpit table between the bimini legs
    tx = 0.5 * (s0 + b0 + 0.4)
    tube(hull, [(tx, 0, dz), (tx, 0, dz + 0.68)], 0.04, "Stainless", 10)
    box(hull, (tx, 0, dz + 0.71), (0.75, 1.1, 0.04), "Wood")
    # solar panels on the bimini
    for y in (-0.62, 0.62):
        box(hull, (0.5 * (b0 + 0.3 + s0), y, roof + 0.08), (1.1, 1.0, 0.03), "CabinWindow")
    # Fleet hero: the charter cat's davits off the stern with the tender hung between them (a grey RIB: two tubes and a
    # floor, its outboard tilted up), and a swim ladder folded on each sugar-scoop step.
    dx0 = min(Hh.h["stern_x"] for Hh in HS[:2]) - 0.45   # hung clear of the sugar scoops
    for y in (-0.95, 0.95):
        tube(hull, [(b0 - 0.1, y, dz + 0.9), (dx0 + 0.45, y, dz + 1.25), (dx0, y, dz + 1.2)], 0.03, "Stainless", 8)
        tube(hull, [(dx0, y, dz + 1.2), (dx0, y * 0.7, dz + 0.85)], 0.004, "Rope", 4, cap=False)
    tz = dz + 0.8    # the tender's tubes, hung across the stern from the davits
    ty0, ty1 = -1.3, 1.3
    for xo in (-0.32, 0.32):
        tube(hull, [(dx0 + xo, ty0 + 0.25, tz), (dx0 + xo, ty1 - 0.2, tz)], 0.2, "BlackPlastic", 14)
    tube(hull, [(dx0 - 0.32, ty0 + 0.25, tz), (dx0, ty0 + 0.05, tz), (dx0 + 0.32, ty0 + 0.25, tz)], 0.2, "BlackPlastic", 14)
    box(hull, (dx0, 0.05, tz - 0.12), (0.5, 2.3, 0.06), "Deck")
    box(hull, (dx0, ty1 - 0.05, tz + 0.15), (0.22, 0.18, 0.35), "BlackPlastic")
    for Hh in HS[:2]:
        st = Hh.h["stern_x"]
        for k in range(3):
            tube(hull, [(st + 0.12, Hh.cy - 0.18, Hh.sheer(st) - 0.3 - 0.18 * k), (st + 0.12, Hh.cy + 0.18, Hh.sheer(st) - 0.3 - 0.18 * k)], 0.012, "Stainless", 6)
        for y in (-0.18, 0.18):
            tube(hull, [(st + 0.12, Hh.cy + y, Hh.sheer(st) - 0.2), (st + 0.12, Hh.cy + y, Hh.sheer(st) - 0.7)], 0.012, "Stainless", 6)
    # windlass and bow roller on the forward crossbeam
    box(hull, (b1 + 0.9, 0, dz + 0.1), (0.22, 0.25, 0.14), "Stainless")
    tube(hull, [(b1 + 0.9, -0.16, dz + 0.12), (b1 + 0.9, 0.16, dz + 0.12)], 0.05, "BlackPlastic", 12)


# ---------------------------------------------------------------- the boat

for Hh in HS:
    shell(Hh)

boards = [f for f in CFG["foils"] if f["role"] in ("keel", "board")]
for f in boards:
    board(HS[f["hull"]], f, -DRAFT)

mast_x = RIG["mast_x"]
jib = CFG["jib"]
main = CFG["main"]
has_jib = len(jib) > 0
hounds_z = (jib[-1]["z_top"] + 0.05) if has_jib else RIG["masthead_z"] * 0.85
if SPEC["rig"] == "masthead":
    hounds_z = RIG["masthead_z"] - 0.05
mast_step_z = MAIN.deck_z(mast_x, MAIN.cy)
traveler = None

if TAG in ("Sunfish", "ILCA7"):
    ck = SPEC["cockpit"]
    deck(MAIN, cuts=[(ck[0], ck[1], -ck[2], ck[2])])
    cockpit(MAIN, ck)
    # Daggerboard trunk cap and the mast thwart; hiking strap.
    f = boards[0]
    box(hull, (f["center"][0], 0, MAIN.deck_z(f["center"][0], 0) + 0.01), (f["chord"] + 0.06, 0.05, 0.03), "BlackPlastic")
    tube(hull, [(ck[0] + 0.1, 0, MAIN.deck_z(ck[0], 0) - ck[3] + 0.06), (ck[1] - 0.1, 0, MAIN.deck_z(ck[1], 0) - ck[3] + 0.06)], 0.018, "Graphics", 6)
    tube(hull, [(mast_x, 0, mast_step_z - 0.02), (mast_x, 0, mast_step_z + 0.03)], RIG["mast_diameter"] * 0.7, "BlackPlastic", 12)
    traveler = (MAIN.h["stern_x"] + 0.18, MAIN.deck_z(MAIN.h["stern_x"] + 0.18, 0) + 0.02, 0.32 if TAG == "ILCA7" else 0.2)
    tube(hull, [(traveler[0], -traveler[2], traveler[1]), (traveler[0], traveler[2], traveler[1])], 0.006, "Rubrail", 6)  # the traveler rope
    for side in (1, -1):
        box(hull, (traveler[0], side * traveler[2], traveler[1] - 0.005), (0.05, 0.03, 0.02), "Stainless")
    dinghy_detail(MAIN, ck, boards[0], mast_x, mast_step_z, traveler)

elif TAG in ("Catalina22", "Catalina30"):
    ck, cb = SPEC["cockpit"], SPEC["cabin"]
    deck(MAIN, cuts=[(ck[0], ck[1], -ck[2], ck[2])])
    cockpit(MAIN, ck)
    top, half = cabin(MAIN, cb)
    mast_step_z = top(mast_x) - 0.04 + 0.035
    st, bw = MAIN.h["stern_x"], MAIN.h["bow_x"]
    lifelines(MAIN, st + 0.25, bw - 0.95)
    keelboat_deck_detail(MAIN, top, half, cb, mast_x, st, bw)
    keelboat_cockpit_detail(MAIN, ck, cb, top, half, st, bw)
    if TAG == "Catalina22":
        traveler = (ck[0] + 0.35, MAIN.deck_z(ck[0], 0) + 0.04, ck[2] - 0.12)
    else:
        # The 30's traveler on the cabin top just forward of the companionway hatch, sheeted mid-boom, as on most hulls
        # (it had been across the cockpit at the wheel, and an eased sheet swept the helm's back).
        tx = cb[0] + 1.0  # (forward of the slide-hatch rails)
        traveler = (tx, top(tx) + 0.03, half(tx) - 0.15)
    tube(hull, [(traveler[0], -traveler[2], traveler[1]), (traveler[0], traveler[2], traveler[1])], 0.012, "Aluminium", 8)
    wx = SPEC["winch_x"]
    for side, tag in ((1, "S"), (-1, "P")):
        y = side * (ck[2] + 0.13)
        winch(wx, y, MAIN.deck_z(wx, y))
        socket(f"JibWinch_{tag}", (wx, y, MAIN.deck_z(wx, y) + 0.08))
        clew_x = jib[0]["luff_x"] - jib[0]["chord"]
        lx = clew_x - 0.15
        ly = side * (MAIN.sharp_half_beam(lx) - 0.12)
        box(hull, (lx, ly, MAIN.deck_z(lx, ly) + 0.015), (0.9, 0.03, 0.02), "Aluminium")
        socket(f"JibLead_{tag}", (lx, ly, MAIN.deck_z(lx, ly) + 0.05))
    socket("LazySheetVia", (mast_x + 0.4, 0, top(mast_x + 0.4) + 0.05))
    socket("BackstayPlate", (st + 0.04, 0, MAIN.deck_z(st, 0) + 0.02))
    if SPEC.get("wheel"):
        wxp = SPEC["wheel"]
        sole = MAIN.deck_z(wxp, ck[2]) - ck[3]
        tube(hull, [(wxp, 0, sole), (wxp, 0, sole + 0.85)], 0.06, "Stainless", 12)
        box(hull, (wxp, 0, sole + 0.95), (0.18, 0.2, 0.22), "BlackPlastic")
        r = 0.42
        rim = [(wxp - 0.12, r * math.cos(2 * math.pi * k / 24), sole + 0.95 + r * math.sin(2 * math.pi * k / 24)) for k in range(25)]
        tube(hull, rim, 0.014, "Stainless", 8, cap=False)
        for k in range(6):
            a = 2 * math.pi * k / 6
            tube(hull, [(wxp - 0.12, 0, sole + 0.95), (wxp - 0.12, r * math.cos(a), sole + 0.95 + r * math.sin(a))], 0.008, "Stainless", 6)
    if SPEC.get("dodger"):
        x0 = cb[0]
        # Fixed to the cabin top forward of the companionway, rising aft to its bow frame, open aft; windows in the front.
        frame = [(x0 - 0.1 + 0.7 * math.cos(math.pi / 2 * k / 8), 0.0, top(x0) + 0.75 * math.sin(math.pi / 2 * k / 8)) for k in range(9)]
        rows = [[(p[0], v * (half(x0) + 0.05), MAIN.deck_z(x0, 0) + (p[2] - MAIN.deck_z(x0, 0)) * (1 - 0.15 * v * v)) for v in [-1 + 2 * j / 8 for j in range(9)]] for p in frame]
        pane = lambda i, j: "CabinWindow" if 1 <= i <= 4 and j in (1, 2, 5, 6) else "SailCover"
        hull.grid(rows, "SailCover", slot_fn=pane)
        hull.grid(rows, "SailCover", flip=True, slot_fn=pane)
    if SPEC.get("outboard"):
        e = CFG["engines"][0]["position"]
        tz = MAIN.deck_z(st, 0)
        box(hull, (st - 0.12, e[1], tz - 0.15), (0.12, 0.3, 0.25), "Stainless")                      # bracket
        box(hull, (st - 0.3, e[1], tz + 0.05), (0.42, 0.3, 0.38), "BlackPlastic")                     # cowling
        box(hull, (st - 0.28, e[1], tz - 0.4), (0.14, 0.08, 0.75), "BlackPlastic")                    # leg
        tube(hull, [(st - 0.28, e[1], e[2] + 0.05), (st - 0.42, e[1], e[2] + 0.05)], 0.06, "BlackPlastic", 10)

elif TAG == "Hobie16":
    fb, rb = SPEC["beams"]
    for Hh in HS:
        deck(Hh, slot="Topsides")
    inner = lambda x: HS[1].cy - HS[1].sharp_half_beam(x) + 0.05
    bz = HS[0].sheer(fb) + 0.07
    for bx in (fb, rb):
        tube(hull, [(bx, HS[0].cy - 0.05, bz), (bx, HS[1].cy + 0.05, bz)], 0.045, "Aluminium", 14)
    # Trampoline laced between the beams and the hulls' inner sides.
    rows = [[(x, -inner(x) + 0.02 + (2 * inner(x) - 0.04) * k / 12, bz + 0.03) for k in range(13)] for x in stations(rb + 0.05, fb - 0.05, 10)]
    hull.grid(rows, "BlackPlastic", flip=True)
    hull.grid(rows, "BlackPlastic")
    for side in (1, -1):
        tube(hull, [(rb, side * inner(rb), bz + 0.02), (fb, side * inner(fb), bz + 0.02)], 0.02, "Aluminium", 8)
    mast_step_z = bz + 0.05
    box(hull, (fb, 0, bz + 0.03), (0.12, 0.12, 0.06), "BlackPlastic")
    # Bridles from the bows to the forestay junction, which the game ties the forestay to.
    jx, jz = fb + 1.1, bz + 0.75
    for Hh in HS:
        bx = Hh.h["bow_x"] - 0.1
        tube(hull, [(bx, Hh.cy, Hh.sheer(bx) + 0.02), (jx, 0, jz)], 0.004, "Stainless", 4)
    socket("ForestayTack", (jx, 0, jz))
    for Hh, tag in ((HS[1], "S"), (HS[0], "P")):
        y = Hh.cy + (1 if tag == "S" else -1) * (Hh.sharp_half_beam(mast_x) - 0.02)
        socket(f"ChainplateUpper_{tag}", (mast_x - 0.05, y, Hh.sheer(mast_x)))
        socket(f"ChainplateLower_{tag}", (mast_x - 0.05, y, Hh.sheer(mast_x)))
        lx = rb + 0.9
        socket(f"JibLead_{tag}", (lx, Hh.cy - (0.25 if tag == "S" else -0.25), bz + 0.05))
        socket(f"JibWinch_{tag}", (lx - 0.25, Hh.cy - (0.3 if tag == "S" else -0.3), bz + 0.05))
    socket("LazySheetVia", (fb - 0.6, 0, bz + 0.1))
    traveler = (rb, bz + 0.05, inner(rb) - 0.05)
    tube(hull, [(rb + 0.02, -traveler[2], bz + 0.05), (rb + 0.02, traveler[2], bz + 0.05)], 0.012, "Aluminium", 8)
    hobie_detail(fb, rb, bz, inner, traveler)

elif TAG == "Corsair880":
    ck, cb = SPEC["cockpit"], SPEC["cabin"]
    deck(MAIN, cuts=[(ck[0], ck[1], -ck[2], ck[2])])
    cockpit(MAIN, ck)
    top, half = cabin(MAIN, cb)
    mast_step_z = top(mast_x) - 0.04 + 0.035
    for Hh in HS[1:]:
        deck(Hh)
    # Akas: curved beams from the main hull up and out to the floats (Farrier's folding beams).
    for ax in SPEC["akas"]:
        for Hh in HS[1:]:
            side = 1 if Hh.cy > 0 else -1
            y0, y1 = side * (MAIN.sharp_half_beam(ax) - 0.1), Hh.cy - side * (Hh.sharp_half_beam(ax) - 0.15)
            z0, z1 = MAIN.deck_z(ax, y0) - 0.05, Hh.deck_z(ax, Hh.cy) - 0.02
            path = [(ax, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t + 0.25 * math.sin(math.pi * t)) for t in [k / 10 for k in range(11)]]
            tube(hull, path, 0.09, "Topsides", 12)
    # Nets between the akas.
    for Hh in HS[1:]:
        side = 1 if Hh.cy > 0 else -1
        a0, a1 = SPEC["akas"]
        rows = []
        for x in stations(a1 + 0.1, a0 - 0.1, 8):
            y0, y1 = side * (MAIN.sharp_half_beam(x) - 0.05), Hh.cy - side * (Hh.sharp_half_beam(x) - 0.1)
            rows.append([(x, y0 + (y1 - y0) * t, MAIN.deck_z(x, y0) - 0.02 + 0.12 * math.sin(math.pi * t) + (Hh.deck_z(x, Hh.cy) - MAIN.deck_z(x, y0)) * t) for t in [k / 10 for k in range(11)]])
        hull.grid(rows, "BlackPlastic")
        hull.grid(rows, "BlackPlastic", flip=True)
    bw = MAIN.h["bow_x"]
    sp = SPEC["bowsprit"]
    tube(hull, [(bw - 0.3, 0, MAIN.deck_z(bw - 0.3, 0) + 0.05), (bw + sp, 0, MAIN.deck_z(bw, 0) + 0.02)], 0.035, "BlackPlastic", 10)
    # Fleet hero: the sprit's end fitting with the gennaker's tack block, its bobstay down to the stem just above the
    # water, and the self-tacking jib's track across the cabin top where its lead is.
    ez = MAIN.deck_z(bw, 0) + 0.02
    tube(hull, [(bw + sp - 0.06, 0, ez), (bw + sp + 0.03, 0, ez)], 0.042, "Aluminium", 10)
    box(hull, (bw + sp + 0.02, 0, ez - 0.07), (0.05, 0.03, 0.06), "BlackPlastic")
    tube(hull, [(bw + sp - 0.02, 0, ez - 0.03), (bw - 0.02, 0, 0.12)], 0.004, "Stainless", 4, cap=False)
    jx = mast_x + 0.6
    tube(hull, [(jx, y, top(jx) + 0.02) for y in (-0.5, -0.25, 0.0, 0.25, 0.5)], 0.012, "Aluminium", 6)
    box(hull, (jx, 0.3, top(jx) + 0.045), (0.07, 0.05, 0.03), "BlackPlastic")
    lifelines(MAIN, ck[0] - 0.1, bw - 0.9)
    st = MAIN.h["stern_x"]
    traveler = (ck[0] + 0.3, MAIN.deck_z(ck[0], 0) + 0.04, ck[2] - 0.1)
    tube(hull, [(traveler[0], -traveler[2], traveler[1]), (traveler[0], traveler[2], traveler[1])], 0.012, "Aluminium", 8)
    wx = SPEC["winch_x"]
    for side, tag in ((1, "S"), (-1, "P")):
        y = side * (ck[2] + 0.12)
        winch(wx, y, MAIN.deck_z(wx, y))
        socket(f"JibWinch_{tag}", (wx, y, MAIN.deck_z(wx, y) + 0.08))
        socket(f"JibLead_{tag}", (mast_x + 0.6, side * 0.45, top(mast_x + 0.6) + 0.04))  # self-tacking track on the cabin top
        Hh = max(HS[1:], key=lambda h: side * h.cy)  # rig clearance: the float on this side (HS[1] is the port one)
        socket(f"ChainplateUpper_{tag}", (mast_x - 0.3, Hh.cy, Hh.deck_z(mast_x - 0.3, Hh.cy)))
        socket(f"ChainplateLower_{tag}", (mast_x - 0.2, side * (MAIN.sharp_half_beam(mast_x) - 0.08), MAIN.deck_z(mast_x, side * 0.5)))
    socket("LazySheetVia", (mast_x + 0.6, 0, top(mast_x + 0.6) + 0.05))
    keelboat_deck_detail(MAIN, top, half, cb, mast_x, st, bw)
    keelboat_cockpit_detail(MAIN, ck, cb, top, half, st, bw)
    corsair_detail(ck, cb, top, half, st, bw)
    if SPEC.get("outboard"):
        e = CFG["engines"][0]["position"]
        tz = MAIN.deck_z(st, 0)
        box(hull, (st - 0.25, e[1], tz - 0.05), (0.42, 0.3, 0.38), "BlackPlastic")
        box(hull, (st - 0.25, e[1], tz - 0.55), (0.14, 0.08, 0.8), "BlackPlastic")

elif TAG == "Lagoon42":
    b0, b1 = SPEC["bridgedeck"]
    for Hh in HS:
        deck(Hh)
    inner = lambda x: HS[1].cy - HS[1].sharp_half_beam(x)
    dz = HS[0].sheer(0.0)
    under = 0.85                                    # bridgedeck clearance above the water
    # Bridgedeck: a box between the hulls' inner sides, its underside clear of the water.
    xs = stations(b0, b1, 16)
    top_rows = [[(x, -inner(x) + 2 * inner(x) * k / 10, dz + 0.02) for k in range(11)] for x in xs]
    hull.grid(top_rows, "NonSkid", flip=True)
    bot_rows = [[(x, -inner(x) + 2 * inner(x) * k / 10, under) for k in range(11)] for x in xs]
    hull.grid(bot_rows, "Topsides")
    for x, rev in ((b0, False), (b1, True)):
        q = [(x, -inner(x), under), (x, inner(x), under), (x, inner(x), dz + 0.02), (x, -inner(x), dz + 0.02)]
        hull.face(list(reversed(q)) if rev else q, "Topsides")
    # Saloon: walls of glass and gelcoat on the bridgedeck, a cambered roof the mast stands on.
    s0, s1, sw, sh = -2.4, 2.8, inner(0.0) + 0.55, 1.42
    roof = dz + sh
    for side in (1, -1):
        hull.grid([[(x, side * sw, dz), (x, side * sw, roof)] for x in stations(s0, s1, 10)], "Topsides", flip=side > 0)
        hull.grid([[(x, side * (sw + 0.004), dz + 0.55), (x, side * (sw + 0.004), roof - 0.15)] for x in stations(s0 + 0.4, s1 - 0.5, 10)], "CabinWindow", flip=side > 0)
    front = [(s1, -sw, dz), (s1, sw, dz), (s1 - 0.6, sw, roof), (s1 - 0.6, -sw, roof)]
    hull.face(front, "CabinWindow")
    hull.face([(s0, sw, dz), (s0, -sw, dz), (s0, -sw, roof), (s0, sw, roof)], "CabinWindow")
    hull.grid([[(x, sw * v, roof + 0.08 * (1 - v * v)) for v in [-1 + 2 * k / 8 for k in range(9)]] for x in stations(s0 - 0.2, s1 - 0.6, 8)], "Topsides", flip=True)
    mast_step_z = roof + 0.08
    # Bimini over the cockpit aft of the saloon, on stainless legs; the forward trampoline and crossbeam.
    for side in (1, -1):
        for x in (s0 - 0.1, b0 + 0.4):
            tube(hull, [(x, side * (inner(x) - 0.1), dz), (x, side * (inner(x) - 0.1), roof)], 0.02, "Stainless", 8)
    hull.grid([[(x, (inner(x) - 0.05) * v, roof + 0.05) for v in [-1 + 2 * k / 6 for k in range(7)]] for x in stations(b0 + 0.3, s0, 4)], "SailCover")
    tube(hull, [(b1 + 0.9, HS[0].cy, dz - 0.05), (b1 + 0.9, HS[1].cy, dz - 0.05)], 0.11, "Topsides", 12)
    rows = [[(x, -inner(x) + 0.05 + (2 * inner(x) - 0.1) * k / 10, dz - 0.05) for k in range(11)] for x in stations(b1, b1 + 0.9, 3)]
    hull.grid(rows, "BlackPlastic")
    hull.grid(rows, "BlackPlastic", flip=True)
    lifelines(HS[0], b0, HS[0].h["bow_x"] - 1.0)
    lifelines(HS[1], b0, HS[1].h["bow_x"] - 1.0)
    socket("ForestayTack", (b1 + 0.9, 0, dz))
    for Hh, tag in ((HS[1], "S"), (HS[0], "P")):
        side = 1 if tag == "S" else -1
        socket(f"ChainplateUpper_{tag}", (mast_x - 1.0, Hh.cy + side * (Hh.sharp_half_beam(mast_x) - 0.1), Hh.deck_z(mast_x, Hh.cy)))
        socket(f"ChainplateLower_{tag}", (mast_x - 0.6, Hh.cy + side * (Hh.sharp_half_beam(mast_x) - 0.15), Hh.deck_z(mast_x, Hh.cy)))
        # The self-tacking track across the saloon roof's forward end, under the jib's clew (Fleet.cpp: x 0.45).
        socket(f"JibLead_{tag}", (0.45, side * 0.5, roof + 0.08 * (1 - (0.5 / sw) ** 2) + 0.05))
        socket(f"JibWinch_{tag}", (s0 + 0.3, side * (sw - 0.2), roof + 0.06))
        winch(s0 + 0.3, side * (sw - 0.2), roof)
    socket("LazySheetVia", (0.45, 0, roof + 0.13))
    # The self-tacking track itself: an aluminium rail across the roof's crown, end stops, and its car's blocks.
    track = [(0.45, y, roof + 0.08 * (1 - (y / sw) ** 2) + 0.02) for y in [-0.9 + 1.8 * k / 12 for k in range(13)]]
    tube(hull, track, 0.018, "Aluminium", 8)
    for y in (-0.9, 0.9):
        box(hull, (0.45, y, roof + 0.08 * (1 - (y / sw) ** 2) + 0.035), (0.06, 0.04, 0.04), "BlackPlastic")
    traveler = (s0 + 0.2, roof + 0.1, sw - 0.3)
    tube(hull, [(traveler[0], -traveler[2], traveler[1]), (traveler[0], traveler[2], traveler[1])], 0.02, "Aluminium", 8)
    lagoon_detail(b0, b1, dz, inner, s0, s1, sw, roof)

# Common sockets on the hull.
socket("MastStep", (mast_x, 0, mast_step_z))
if traveler:
    socket("Traveler_C", (traveler[0], 0, traveler[1]))
    socket("Traveler_S", (traveler[0], traveler[2], traveler[1]))
if SPEC["rig"] in ("masthead", "tri"):
    bw = MAIN.h["bow_x"]
    socket("ForestayTack", (bw - 0.04, 0, MAIN.deck_z(bw - 0.04, 0) + 0.02))
if SPEC["rig"] == "masthead":
    for side, tag in ((1, "S"), (-1, "P")):
        y = side * (MAIN.sharp_half_beam(mast_x) - 0.08)
        socket(f"ChainplateUpper_{tag}", (mast_x - 0.05, y, MAIN.deck_z(mast_x, y)))
        socket(f"ChainplateLower_{tag}", (mast_x - 0.35, y * 0.96, MAIN.deck_z(mast_x - 0.35, y)))


# ---------------------------------------------------------------- mast, boom, rudder

def build_mast():
    m = Mesh(f"SM_{TAG}_Mast")
    top = RIG["masthead_z"]
    d = RIG["mast_diameter"]
    wing = SPEC["rig"] in ("beachcat", "tri")      # rotating wing-section masts
    zs = [mast_step_z + (top - mast_step_z) * k / 30 for k in range(31)]
    rings = []
    for z in zs:
        taper = 1.0 if z < hounds_z else 1.0 - 0.35 * (z - hounds_z) / max(top - hounds_z, 0.1)
        a = 0.5 * d * taper
        b = (0.55 if wing else 0.72) * a
        rings.append([(mast_x + a * math.cos(2 * math.pi * k / 20), b * math.sin(2 * math.pi * k / 20), z) for k in range(21)])
    m.grid(rings, "Aluminium")
    m.face(rings[-1][:-1], "Aluminium")
    stayed = SPEC["rig"] not in ("una", "lateen")
    if stayed:
        socket("Hounds", (mast_x + 0.5 * d, 0, hounds_z), "Mast")
        socket("MastheadAft", (mast_x - 0.6 * d - 0.08, 0, top + 0.02), "Mast")
        box(m, (mast_x - 0.05, 0, top + 0.02), (0.25 * max(1.0, d / 0.1), 0.05, 0.04), "Aluminium")
        if SPEC.get("spreader"):
            sz = mast_step_z + 0.5 * (hounds_z - mast_step_z)
            for side, tag in ((1, "S"), (-1, "P")):
                tip = (mast_x - 0.12, side * SPEC["spreader"], sz + 0.04)
                tube(m, [(mast_x - 0.02, side * 0.03, sz), tip], 0.016 * max(1.0, d / 0.09), "Aluminium", 8)
                socket(f"SpreaderTip_{tag}", tip, "Mast")
            socket("LowerTang", (mast_x, 0, sz - 0.05), "Mast")
        else:
            socket("LowerTang", (mast_x, 0, hounds_z - 0.1), "Mast")
    socket("MastBase", (mast_x - 0.06, 0, mast_step_z + 0.2), "Mast")
    if TAG == "Hobie16":
        # Fleet hero: the trapeze wires from the hounds, each to its ring and handle at a crew member's reach over the
        # tramp, and the shock cord down to the deck eye beside it (baked on the mast: they hang from it).
        bzh = MAIN.sheer(mast_x)
        for Hh, side in ((HS[1], 1), (HS[0], -1)):
            ring = (mast_x - 0.35, Hh.cy - side * 0.12, bzh + 1.15)
            tube(m, [(mast_x, side * 0.03, hounds_z - 0.05), ring], 0.002, "Stainless", 4, cap=False)
            tube(m, [ring, (ring[0], ring[1], ring[2] - 0.12)], 0.012, "BlackPlastic", 8)
            tube(m, [(ring[0] - 0.06, ring[1], ring[2] - 0.12), (ring[0] + 0.06, ring[1], ring[2] - 0.12)], 0.012, "BlackPlastic", 8)
            tube(m, [(ring[0], ring[1], ring[2] - 0.12), (ring[0], ring[1], bzh + 0.06)], 0.004, "Rope", 4, cap=False)
    if TAG == "Sunfish":
        # Fleet hero: the Sunfish's masthead is a black halyard cap with its sheave (no wind indicator); the halyard comes
        # down the forward face to the deck.
        tube(m, [(mast_x, 0, top - 0.02), (mast_x, 0, top + 0.06)], 0.5 * d + 0.006, "BlackPlastic", 14)
        box(m, (mast_x + 0.5 * d + 0.012, 0, top + 0.02), (0.03, 0.012, 0.06), "BlackPlastic")
        tube(m, [(mast_x + 0.5 * d + 0.02, 0, top + 0.02), (mast_x + 0.5 * d + 0.012, 0, mast_step_z + 0.3)], 0.003, "Rope", 4, cap=False)
        # Chalky anodising bands where the sail ties and the mast meets the step.
        tube(m, [(mast_x, 0, mast_step_z), (mast_x, 0, mast_step_z + 0.06)], 0.5 * d + 0.004, "BlackPlastic", 14)
    else:
        # Wind indicator at the masthead.
        tube(m, [(mast_x, 0, top), (mast_x - 0.25, 0, top + 0.25)], 0.004, "Stainless", 4)
    if TAG == "ILCA7":
        # Fleet hero: the ILCA's two-piece mast. The top section sleeves into the bottom one 2.85 m up, a collar over the
        # joint; the black plastic gooseneck fitting where the boom pins on; the rotating mast's step ring and the
        # cunningham's hook just above the boom.
        jz = min(mast_step_z + 2.85, top - 0.5)
        tube(m, [(mast_x, 0, jz - 0.07), (mast_x, 0, jz + 0.07)], 0.5 * d + 0.004, "Aluminium", 16)
        tube(m, [(mast_x, 0, jz + 0.07), (mast_x, 0, jz + 0.075)], 0.5 * d + 0.006, "Stainless", 16)
        bz = RIG["boom_z"]
        box(m, (mast_x - 0.5 * d - 0.02, 0, bz), (0.05, 0.035, 0.07), "BlackPlastic")
        tube(m, [(mast_x, 0, mast_step_z - 0.01), (mast_x, 0, mast_step_z + 0.025)], 0.5 * d + 0.008, "BlackPlastic", 16)
        box(m, (mast_x + 0.5 * d + 0.012, 0, bz + 0.22), (0.02, 0.012, 0.04), "Stainless")
    return m.finish(smooth_angle=60.0, origin=(mast_x, 0, mast_step_z), keep=("Aluminium",))


def build_boom():
    m = Mesh(f"SM_{TAG}_Boom")
    gx, gz = RIG["main_luff_x"], RIG["boom_z"]
    length = RIG["main_foot_chord"] + 0.08
    r = 0.025 + 0.012 * min(length, 6.0) / 3.0
    xs = [gx - length * k / 16 for k in range(17)]
    rings = [[(x, 0.75 * r * math.sin(2 * math.pi * k / 16), gz - 0.02 + r * math.cos(2 * math.pi * k / 16)) for k in range(17)] for x in xs]
    m.grid(rings, "Aluminium", flip=True)
    m.face(rings[0][:-1], "Aluminium")
    m.face(list(reversed(rings[-1][:-1])), "Aluminium")
    sheet_x = traveler[0] if traveler else gx - 0.85 * length
    sheet_x = min(max(sheet_x, gx - length + 0.05), gx - 0.3)
    box(m, (sheet_x, 0, gz - 0.02 - r), (0.06, 0.03, 0.03), "Stainless")
    socket("Boom_Mainsheet", (sheet_x, 0, gz - 0.03 - r), "Boom")
    socket("Boom_Clew", (gx - length + 0.06, 0, gz + 0.04), "Boom")
    if SPEC.get("vang", SPEC["rig"] in ("masthead", "tri", "cruisingcat")):
        socket("Boom_Vang", (gx - 0.55, 0, gz - 0.03 - r), "Boom")
    if TAG == "ILCA7":
        # Fleet hero: the ILCA boom's outhaul cleat and fairlead, the clew's tie-down strap round the boom's end and the
        # vang key near the gooseneck.
        box(m, (gx - 0.75, 0, gz - 0.02 + r + 0.012), (0.08, 0.03, 0.02), "BlackPlastic")
        box(m, (gx - length + 0.25, 0, gz - 0.02 + r + 0.008), (0.03, 0.02, 0.016), "Stainless")
        cx = gx - length + 0.09
        tube(m, [(cx, r * 1.05 * math.cos(2 * math.pi * k / 12), gz - 0.02 + r * 1.05 * math.sin(2 * math.pi * k / 12)) for k in range(13)], 0.006, "Graphics", 4, cap=False)
        box(m, (gx - 0.55, 0, gz - 0.02 - r - 0.012), (0.04, 0.02, 0.025), "Stainless")
    if SPEC["rig"] == "lateen":
        # The Sunfish's upper spar (the yard) lies along the sail's luff from the tack to the head.
        lx0, z0 = main[0]["luff_x"], main[0]["z_bottom"]
        lx1, z1 = main[-1]["luff_x"], main[-1]["z_top"]
        a, b = Vector((lx0 + 0.05, 0, z0 - 0.01)), Vector((lx1, 0, z1))
        tube(m, [tuple(a), tuple(b)], 0.024, "Aluminium", 10)
        # Fleet hero: black end caps, the yard's halyard eye a third of the way up, and the gooseneck jaw where yard and
        # boom meet at the tack (stainless, through-bolted).
        u = (b - a).normalized()
        tube(m, [tuple(b), tuple(b + u * 0.03)], 0.026, "BlackPlastic", 10)
        tube(m, [tuple(a - u * 0.03), tuple(a)], 0.026, "BlackPlastic", 10)
        eye = a + (b - a) * 0.36
        box(m, (eye.x + 0.03, 0, eye.z), (0.05, 0.014, 0.02), "Stainless")
        box(m, (gx - 0.02, 0, gz + 0.02), (0.09, 0.05, 0.06), "Stainless")
        tube(m, [(gx - 0.02, -0.03, gz + 0.02), (gx - 0.02, 0.03, gz + 0.02)], 0.006, "Stainless", 6)
    return m.finish(smooth_angle=60.0, origin=(gx, 0, gz))


def build_rudder():
    rudders = [f for f in CFG["foils"] if f["role"] == "rudder"]
    f = rudders[0]
    m = Mesh(f"SM_{TAG}_Rudder")
    cx, cy, cz = f["center"]
    chord = f["chord"]
    stock_x = cx + 0.25 * chord
    Hh = HS[f["hull"]]
    tillered = SPEC.get("tiller", False)
    st = Hh.h["stern_x"]
    transom = stock_x < st + 0.15
    # Blade: from above the water (transom-hung) or from the hull (spade) down; the boats without a keel or board
    # draw to the physics' draft with the rudder (the beach cat).
    z_top = (Hh.sheer(st) - 0.05) if transom else Hh.bottom_z(stock_x, cy) + 0.03
    z_bot = cz - 0.5 * f["span"]
    if not boards:
        z_bot = min(z_bot, -DRAFT)
    else:
        z_bot = max(z_bot, -DRAFT + 0.06)    # a spade rudder stays shallower than the keels it sails with
    secs = []
    for k in range(9):
        t = k / 8
        z = z_top + (z_bot - z_top) * t
        c = chord * (1.2 - 0.45 * t ** 1.4) if transom else chord * (1.0 - 0.3 * t)
        secs.append((z, stock_x + 0.25 * c - 0.25 * chord + 0.03, c))
    foil(m, [(z, le, c) for (z, le, c) in secs], "Antifouling" if SPEC["paint"] else "Topsides", 0.11, cy)
    if transom and tillered:
        tz = Hh.sheer(st) + 0.08
        box(m, (stock_x - 0.04, cy, tz - 0.12), (0.18, 0.05, 0.3), "Topsides")
        tl = RIG["tiller_length"]
        tube(m, [(stock_x - 0.02, cy, tz), (stock_x + tl, cy, tz + 0.08)], 0.02, "Wood", 10)
        # Boats & models 9: no extension baked along the tiller. The game draws the live one from this socket (in the helm's
        # hand, or lying back along the tiller; ASailboatPawn::TillerEndCm), so the baked one showed as a second. The Hobie's
        # extension hangs from the middle of its crossbar, which the game doesn't draw: it keeps the baked one.
        if TAG == "Hobie16":
            tube(m, [(stock_x + tl, cy, tz + 0.1), (stock_x + tl - 0.8, cy + 0.03, tz + 0.02)], 0.01, "Aluminium", 8)
        else:
            socket("TillerEnd", (stock_x + tl, cy, tz + 0.08), owner="Rudder")
    socket("RudderPivot", (stock_x, cy, 0))
    for k, g in enumerate(rudders[1:], start=1):
        socket(f"RudderPivot_{k}", (g["center"][0] + 0.25 * g["chord"], g["center"][1], 0))
    if TAG == "Hobie16":
        # The tiller crossbar joining the two tillers (the game turns each rudder; the bar is drawn on the hull).
        tz = Hh.sheer(st) + 0.15
        tube(hull, [(stock_x + 0.55, HS[0].cy, tz), (stock_x + 0.55, HS[1].cy, tz)], 0.016, "Aluminium", 8)
    return m.finish(smooth_angle=45.0, origin=(stock_x, cy, 0))


mast_obj = build_mast()
boom_obj = build_boom()
rudder_obj = build_rudder()
hull_obj = hull.finish(smooth_angle=35.0, origin=(0, 0, 0))


# ---------------------------------------------------------------- measures

def clip_below(p, z):
    out = []
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        ain, bin_ = a.z <= z, b.z <= z
        if ain:
            out.append(a)
        if ain != bin_:
            t = (z - a.z) / (b.z - a.z)
            out.append(a + (b - a) * t)
    return out


def measure(obj):
    me = obj.data
    me.calc_loop_triangles()
    mw = obj.matrix_world
    names = [m.name.split(".")[0] for m in me.materials]
    idx = {i for i, n in enumerate(names) if n in CANOE}
    vol, mom = 0.0, Vector((0, 0, 0))
    box_min, box_max = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for tri in me.loop_triangles:
        if tri.material_index not in idx:
            continue
        p = [mw @ me.vertices[i].co for i in tri.vertices]
        for q in p:
            box_min = Vector(map(min, box_min, q))
            box_max = Vector(map(max, box_max, q))
        poly = clip_below(p, 0.0)
        for k in range(1, len(poly) - 1):
            a, b, c = poly[0], poly[k], poly[k + 1]
            v = a.dot(b.cross(c)) / 6.0
            vol += v
            mom += v * (a + b + c) / 4.0
    cen = mom / vol if abs(vol) > 1e-9 else Vector((0, 0, 0))
    return abs(vol), Vector((cen.x, -cen.y, cen.z)), box_max - box_min


vol, cb, size = measure(hull_obj)
print(f"{TAG}: LOA {size.x:.3f} m (physics {CFG['loa']:.3f}), beam {size.y:.3f} m (physics {CFG['beam']:.3f}), canoe volume {vol:.3f} m^3 "
      f"(physics {CFG['design_volume']:.3f}), CB ({cb.x:.3f}, {cb.y:.3f}, {cb.z:.3f}) (physics {CFG['design_cb']})")
print(f"{TAG}: triangles hull {sum(len(p.vertices) - 2 for p in hull_obj.data.polygons)}, mast {len(mast_obj.data.polygons)}, "
      f"boom {len(boom_obj.data.polygons)}, rudder {len(rudder_obj.data.polygons)}")
ORIGINS = {o.name: [round(o.location.x * 100, 2), round(-o.location.y * 100, 2), round(o.location.z * 100, 2)]
           for o in (hull_obj, mast_obj, boom_obj, rudder_obj)}
json.dump({"sockets": SOCKETS, "owner": OWNER, "origins": ORIGINS, "measures": {"loa": size.x, "beam": size.y, "canoe_volume": vol, "cb": [cb.x, cb.y, cb.z]}},
          open(os.path.join(OUT, f"{TAG}_sockets.json"), "w"), indent=1)

for obj in (hull_obj, mast_obj, boom_obj, rudder_obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    loc = obj.location.copy()
    obj.location = (0, 0, 0)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, obj.name + ".fbx"), use_selection=True, axis_forward="X",
                             axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False, bake_space_transform=True)
    obj.location = loc
print(f"{TAG}: exported", ", ".join(o.name for o in (hull_obj, mast_obj, boom_obj, rudder_obj)))
