"""Visual V2: the J/22 model, built from code in Blender (headless) like the rest of the game's content.

    blender -b --factory-startup -P Tools/blender/build_j22.py -- <j22.json> <out dir>

The physics is the source of truth: j22.json comes from Tools/BoatExport (the same FBoatConfig the simulation floats
and sails). Below the waterline the canoe body is exactly the physics hull surface (FHullShape::BottomZ at the
computed canoe depth), so the model's centre of buoyancy matches the physics; above it the stem and sheer sharpen
toward the real boat. Dimensions of the parts a sailor touches (cabin trunk, cockpit, coamings, hatches, winches,
cleats, traveler, tracks, tiller and extension, keel and transom-hung rudder, outboard on its bracket,
chainplates, spars) come from the class drawings and photos of the J/22 (LOA 22 ft 6 in, beam 8 ft, draft 3 ft 9 in,
fractional rig with swept spreaders, deck-stepped mast on the cabin top, traveler across the cockpit). Like the
lesson boats at Rush Creek (TX 7295 EC, 7297 EC) she has an open deck: no pulpits, stanchions or lifelines.

Writes <out>/SM_J22_Hull.fbx, SM_J22_Mast.fbx, SM_J22_Boom.fbx, SM_J22_Rudder.fbx and J22_sockets.json (attachment
points for the rig and lines, in Unreal's frame and centimetres), and prints the model's measures for the log.

Frames: everything is computed in the boat's body frame as Unreal uses it (X forward, Y starboard, Z up, metres, origin
at the design waterline amidships). Blender's right-handed frame is the same physical space with Y to port, so points
go into Blender as (x, -y, z) and the FBX import turns them back.
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

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CFG = json.load(open(ARGS[0]))
OUT = ARGS[1]
os.makedirs(OUT, exist_ok=True)

H = CFG["hull"]
DEPTH = CFG["canoe_depth"]
RIG = CFG["rig"]

SLOTS = ["Topsides", "Bootstripe", "CoveStripe", "Antifouling", "Keel", "Deck", "NonSkid", "CabinWindow",
         "Stainless", "Aluminium", "BlackPlastic", "Wood", "Graphics", "Rubrail", "Rope", "Teak"]


# ---------------------------------------------------------------- the physics hull (FHullShape, BoatModel.cpp)

def deck_half_beam(x):
    if x > H["max_beam_x"]:
        u = (x - H["max_beam_x"]) / (H["bow_x"] - H["max_beam_x"] + 0.02)
        return H["max_half_beam"] * math.sqrt(max(0.0, 1.0 - u * u))
    u = (H["max_beam_x"] - x) / H["aft_length"]
    return max(H["max_half_beam"] - H["transom_beam_loss"] * u * u, 0.02)


def sheer(x):
    return H["sheer_z"] + H["sheer_rise"] * max(0.0, (x - H["sheer_rise_from_x"]) / max(H["bow_x"] - H["sheer_rise_from_x"], 1e-3))


def keel_line_depth(x):
    u = (x - H["waterline_mid_x"]) / H["waterline_half_length"]
    if abs(u) <= 1.0:
        return DEPTH * (1.0 - u * u)
    return -(abs(u) - 1.0) * H["waterline_half_length"] * (H["bow_overhang_slope"] if u > 0 else H["stern_overhang_slope"])


def sharp_half_beam(x):
    """Above the water the real J/22 has a fine, straight-sided entry rather than the physics' elliptic deck line."""
    if x <= H["max_beam_x"]:
        return deck_half_beam(x)
    u = (x - H["max_beam_x"]) / (H["bow_x"] - H["max_beam_x"] + 0.02)
    return H["max_half_beam"] * (1.0 - u ** 2.2) ** 0.92


def half_beam(x, z):
    """Half-beam of the section's waterlines: the physics below the water, sharpening toward the deck above it."""
    k = min(max(z / 0.35, 0.0), 1.0)
    k = k * k * (3 - 2 * k)
    return (1 - k) * deck_half_beam(x) + k * sharp_half_beam(x)


def section_point(x, r):
    """A point on the hull at station x and fraction r (0 on the keel line, 1 at the sheer), starboard side."""
    d, s = keel_line_depth(x), sheer(x)
    z = -d + (d + s) * r ** H["bilge_power"]
    return (x, half_beam(x, z) * r, z)


def r_at_z(x, z):
    d, s = keel_line_depth(x), sheer(x)
    t = min(max((z + d) / max(d + s, 1e-6), 0.0), 1.0)
    return t ** (1.0 / H["bilge_power"])


# ---------------------------------------------------------------- mesh building

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
        """rows[i][j]: quads between consecutive rows; slot_fn(i, j) may override the slot per quad."""
        for i in range(len(rows) - 1):
            for j in range(len(rows[i]) - 1):
                q = [rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]]
                if flip:
                    q.reverse()
                self.face(q, slot_fn(i, j) if slot_fn else slot)

    def finish(self, smooth_angle=35.0, origin=(0, 0, 0), pack=True):
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        # Box-projected UVs (1 m tiles): the materials are procedural, but a UV set gives the meshes a tangent frame.
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
        for name in SLOTS:
            mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
            me.materials.append(mat)
        # pc/boat-slots: one slot per pack (the mast keeps its own: M_BoatMast bends it).
        if pack:
            pack_slots(me)
        # Origin: geometry is in the boat frame; move it so the object's origin sits at `origin` (boat frame).
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
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        m.face([p[i] for i in f], slot)


def tube(m, path, radius, slot, sides=10, cap=True, radii=None):
    """A round tube along a polyline (rails, stanchions, wires, sheets); radii, if given, one per point (a taper)."""
    pts = [Vector(p) for p in path]
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(a).normalized()
        w = t.cross(u).normalized()
        r = radii[i] if radii else radius
        rings.append([tuple(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides + 1)])
    m.grid(rings, slot)
    if cap:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            r = ring[:-1]
            m.face(list(reversed(r)) if rev else r, slot)


def cylinder(m, base, axis, radius, length, slot, sides=16):
    b = Vector(base)
    tube(m, [tuple(b), tuple(b + Vector(axis).normalized() * length)], radius, slot, sides)


def naca_loop(chord, thickness, n=24):
    """Upper then lower surface of a NACA 00xx section: (x along chord from the leading edge, y)."""
    pts = []
    for i in range(n + 1):
        t = 0.5 * (1 - math.cos(math.pi * i / n))
        y = 5 * thickness * (0.2969 * math.sqrt(t) - 0.1260 * t - 0.3516 * t * t + 0.2843 * t ** 3 - 0.1036 * t ** 4)
        pts.append((t * chord, y * chord))
    upper = pts
    lower = [(x, -y) for (x, y) in reversed(pts[1:-1])]
    return upper + lower


def foil(m, sections, slot, thickness=0.12):
    """A vertical foil lofted through (z, leading edge x, chord) sections; flat caps at both ends."""
    rings = []
    for z, le_x, chord in sections:
        loop = naca_loop(chord, thickness)
        rings.append([(le_x - x, y, z) for (x, y) in loop] + [(le_x - loop[0][0], loop[0][1], z)])
    m.grid(rings, slot)
    m.face(rings[0][:-1], slot)
    m.face(list(reversed(rings[-1][:-1])), slot)


# ---------------------------------------------------------------- layout of the deck (body frame, metres)

STERN, BOW = H["stern_x"], H["bow_x"]
COCKPIT_AFT = STERN + 0.14          # narrow aft deck behind the cockpit
CABIN_AFT = -0.72                   # companionway bulkhead
CABIN_FWD = 1.60                    # front of the cabin trunk
SIDE_DECK = 0.36                    # side deck width alongside the cabin and cockpit
CAMBER = 0.05                       # deck crown
SOLE_Z = 0.30                       # cockpit sole (self-draining, above the waterline)
SEAT_Z = 0.47
SEAT_W = 0.36
COAMING_H = 0.09


def deck_z(x, y):
    b = max(sharp_half_beam(x), 1e-3)
    return sheer(x) + CAMBER * max(0.0, 1.0 - (y / b) ** 2)


def inner_edge(x):
    return max(sharp_half_beam(x) - SIDE_DECK, 0.05)


def cabin_height(x):
    t = (x - CABIN_AFT) / (CABIN_FWD - CABIN_AFT)
    return 0.31 - 0.07 * t


def stations(x0, x1, n, bias=1.0):
    return [x0 + (x1 - x0) * ((i / n) ** bias) for i in range(n + 1)]


SOCKETS = {}


def socket(name, p):
    SOCKETS[name] = [round(p[0] * 100, 2), round(p[1] * 100, 2), round(p[2] * 100, 2)]


# Graphics G6: deck hardware a close camera reads (the round 7 action cam: "few details").
def ring(c, r, z, n, wobble=None):
    return [(c[0] + (r + (wobble(k) if wobble else 0.0)) * math.cos(2 * math.pi * k / n),
             c[1] + (r + (wobble(k) if wobble else 0.0)) * math.sin(2 * math.pi * k / n), z) for k in range(n + 1)]


def disc(m, c, r, z, slot, n=24, up=True):
    pts = ring(c, r, z, n)[:-1]
    m.face(pts if up else list(reversed(pts)), slot)


def winch(m, x, y, z):
    """A two-speed self-tailing winch (a Harken 16 size): base flange, fluted drum, the tailer's jaws and stripper arm, a top
    cap with the handle socket."""
    c = (x, y)
    flute = lambda k: 0.0035 * (k % 2)
    m.grid([ring(c, 0.078, z, 32), ring(c, 0.078, z + 0.012, 32), ring(c, 0.062, z + 0.018, 32)], "Stainless", flip=True)
    rows = [ring(c, 0.050, z + 0.018 + h, 32, flute) for h in (0.0, 0.07)] + [ring(c, 0.056, z + 0.095, 32)]
    m.grid(rows, "Stainless", flip=True)
    # Self-tailer: two black jaws with the line's gap between them, and the cap above.
    m.grid([ring(c, 0.056, z + 0.095, 32), ring(c, 0.064, z + 0.1, 32), ring(c, 0.064, z + 0.11, 32), ring(c, 0.052, z + 0.113, 32),
            ring(c, 0.064, z + 0.118, 32), ring(c, 0.064, z + 0.128, 32), ring(c, 0.05, z + 0.14, 32), ring(c, 0.02, z + 0.145, 32)],
           "BlackPlastic", flip=True)
    disc(m, c, 0.02, z + 0.145, "BlackPlastic", 16)
    m.grid([ring(c, 0.012, z + 0.146, 12), ring(c, 0.012, z + 0.12, 12)], "Stainless", flip=True)   # handle socket
    box(m, (x + 0.05, y, z + 0.112), (0.05, 0.02, 0.014), "BlackPlastic")                          # stripper arm


def cam_cleat(m, x, y, z, yaw):
    """A cam cleat on its base, with the fairlead ahead of the cams."""
    rbox(m, (x, y, z + 0.006), (0.09, 0.05, 0.012), "BlackPlastic", yaw, r=0.012)
    bolts(m, [(x - 0.035 * math.cos(yaw), y - 0.035 * math.sin(yaw)), (x + 0.03 * math.cos(yaw), y + 0.03 * math.sin(yaw))], z + 0.012, 0.003)
    cs, sn = math.cos(yaw), math.sin(yaw)
    for s in (1, -1):
        px, py = x - 0.01 * cs - s * 0.014 * sn, y - 0.01 * sn + s * 0.014 * cs
        m.grid([ring((px, py), 0.012, z + 0.012, 10, lambda k: 0.002 * (k % 2)), ring((px, py), 0.012, z + 0.032, 10, lambda k: 0.002 * (k % 2))],
               "Aluminium", flip=True)
        disc(m, (px, py), 0.012, z + 0.032, "Aluminium", 10)
    fx, fy = x + 0.04 * cs, y + 0.04 * sn
    tube(m, [(fx - 0.012 * sn + 0.0, fy + 0.012 * cs, z + 0.01), (fx, fy, z + 0.03), (fx + 0.012 * sn, fy - 0.012 * cs, z + 0.01)], 0.003, "Stainless", 6)


def rrect(sx, sy, r, n=4):
    """A rounded rectangle sx by sy (corner radius r) about the origin, counter-clockwise, closed."""
    r = min(r, 0.5 * sx - 1e-4, 0.5 * sy - 1e-4)
    pts = []
    for q, (cx, cy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        for k in range(n + 1):
            a = 0.5 * math.pi * (q + k / n)
            pts.append((cx * (0.5 * sx - r) + r * math.cos(a), cy * (0.5 * sy - r) + r * math.sin(a)))
    return pts + [pts[0]]


def loft(m, rows, slot, cap_bottom=False):
    """Closed sections stacked upward: rows of (profile, (cx, cy, z), yaw); the top is capped (and the bottom if asked)."""
    rings = []
    for prof, (cx, cy, z), yaw in rows:
        cs, sn = math.cos(yaw), math.sin(yaw)
        rings.append([(cx + u * cs - v * sn, cy + u * sn + v * cs, z) for u, v in prof])
    m.grid(rings, slot, flip=True)
    m.face(rings[-1][:-1], slot)
    if cap_bottom:
        m.face(list(reversed(rings[0][:-1])), slot)


def rbox(m, c, size, slot, yaw=0.0, r=None, chamfer=None):
    """A cast or moulded fitting's block: rounded corners in plan and a rounded-over top edge (round 12: the plain
    boxes read as placeholders)."""
    sx, sy, sz = size
    r = 0.3 * min(sx, sy) if r is None else r
    ch = min(r, 0.35 * sz) if chamfer is None else chamfer
    x, y, z = c
    z0, z1 = z - 0.5 * sz, z + 0.5 * sz
    rows = [(rrect(sx, sy, r), (x, y, z0), yaw), (rrect(sx, sy, r), (x, y, z1 - ch), yaw)]
    for k in (1, 2):
        t = k / 2
        d = ch * (1 - math.cos(0.5 * math.pi * t))
        rows.append((rrect(sx - 2 * d, sy - 2 * d, max(r - d, 1e-3)), (x, y, z1 - ch + ch * math.sin(0.5 * math.pi * t)), yaw))
    loft(m, rows, slot, cap_bottom=True)


def bolts(m, pts, z, r=0.0045, slot="Stainless"):
    """Domed fastener heads."""
    for x, y in pts:
        m.grid([ring((x, y), r, z, 8), ring((x, y), 0.7 * r, z + 0.4 * r, 8)], slot, flip=True)
        disc(m, (x, y), 0.7 * r, z + 0.4 * r, slot, 8)


def horn_cleat(m, x, y, z, length, yaw):
    """A cast horn cleat: two feet on a rounded base and a horn swept up at each end."""
    cs, sn = math.cos(yaw), math.sin(yaw)
    rbox(m, (x, y, z + 0.006), (0.45 * length, 0.03, 0.012), "Stainless", yaw)
    for s in (1, -1):
        fx, fy = x + s * 0.13 * length * cs, y + s * 0.13 * length * sn
        rbox(m, (fx, fy, z + 0.022), (0.022, 0.018, 0.026), "Stainless", yaw, r=0.008)
    horn = []
    for k in range(11):
        u = -0.5 + k / 10
        horn.append((x + u * length * cs, y + u * length * sn, z + 0.034 + 0.012 * (2 * u) ** 2))
    tube(m, horn, 0.008, "Stainless", 10)


def outboard(m, x, y, z):
    """A 3.5 hp four-stroke on a two-position transom bracket (photo IMG_9273: the lesson boat's on the port quarter):
    the bracket's side plates and teak pad on the transom, the clamp over the pad, cowl, midsection, leg, gearcase,
    skeg, a three-blade prop and the tiller arm reaching forward over the transom. x is the transom, z the prop's axis."""
    xb = x - 0.17                                   # the pad's aft face
    for s in (1, -1):
        rbox(m, (x - 0.085, y + s * 0.10, z + 0.62), (0.17, 0.012, 0.05), "Stainless", r=0.005)
        rbox(m, (x - 0.085, y + s * 0.10, z + 0.48), (0.17, 0.012, 0.04), "Stainless", r=0.005)
        rbox(m, (x - 0.006, y + s * 0.10, z + 0.55), (0.012, 0.05, 0.26), "Stainless", r=0.005)
    rbox(m, (xb + 0.015, y, z + 0.55), (0.03, 0.26, 0.20), "Teak", r=0.01)
    tube(m, [(x - 0.09, y - 0.11, z + 0.55), (x - 0.09, y + 0.11, z + 0.55)], 0.006, "Stainless", 8)   # lock pin
    xm = xb - 0.16                                  # the leg's axis
    ell = lambda rx, ry, nose=1.0: [((rx * nose if math.cos(a) > 0 else rx) * math.cos(a), ry * math.sin(a))
                                     for a in (2 * math.pi * k / 24 for k in range(25))]
    # clamp bracket and swivel over the pad
    rbox(m, (xb - 0.02, y, z + 0.58), (0.07, 0.15, 0.16), "BlackPlastic", r=0.02)
    rbox(m, (xm + 0.07, y, z + 0.60), (0.08, 0.10, 0.16), "BlackPlastic", r=0.025)
    # leg (a foil, blunt nose forward), cavitation plate, gearcase, skeg
    loft(m, [(ell(0.05, 0.022, 0.6), (xm, y, z + 0.02), 0.0), (ell(0.055, 0.025, 0.6), (xm, y, z + 0.40), 0.0)], "Aluminium")
    rbox(m, (xm - 0.04, y, z + 0.10), (0.22, 0.14, 0.008), "Aluminium", r=0.05, chamfer=0.003)
    tor = [(0.0, 0.0), (0.03, 0.015), (0.06, 0.036), (0.15, 0.042), (0.22, 0.034), (0.24, 0.022)]
    rings = [[(xm + 0.08 - u, y + rr * math.cos(2 * math.pi * k / 16), z + rr * math.sin(2 * math.pi * k / 16)) for k in range(17)] for u, rr in tor]
    m.grid(rings, "Aluminium")
    m.face(list(reversed(rings[-1][:-1])), "Aluminium")
    loft(m, [(ell(0.06, 0.004), (xm - 0.02, y, z - 0.13), 0.0), (ell(0.07, 0.005), (xm - 0.01, y, z - 0.02), 0.0)], "Aluminium", cap_bottom=True)
    # propeller: hub and three blades raked a little aft
    hx = xm + 0.08 - 0.24
    hub = [(0.0, 0.024), (0.03, 0.024), (0.06, 0.012), (0.07, 0.0)]
    rings = [[(hx - u, y + rr * math.cos(2 * math.pi * k / 12), z + rr * math.sin(2 * math.pi * k / 12)) for k in range(13)] for u, rr in hub]
    m.grid(rings, "BlackPlastic")
    for b in range(3):
        a0 = 2 * math.pi * b / 3 + 0.3
        pts = []
        for rr, da, dx in ((0.022, -0.35, -0.012), (0.07, -0.30, -0.020), (0.10, 0.0, -0.028), (0.07, 0.42, -0.034), (0.022, 0.38, -0.036)):
            a = a0 + da
            pts.append((hx + dx, y + rr * math.cos(a), z + rr * math.sin(a)))
        m.face(pts, "BlackPlastic")
        m.face(list(reversed(pts)), "BlackPlastic")
    # midsection (the exhaust housing) and the cowl's lower band and lid
    loft(m, [(ell(0.09, 0.06), (xm - 0.01, y, z + 0.40), 0.0), (ell(0.10, 0.07), (xm - 0.01, y, z + 0.56), 0.0)], "BlackPlastic")
    cowl = [(0.0, 0.90), (0.02, 1.0), (0.17, 1.0), (0.24, 0.86), (0.28, 0.55), (0.295, 0.2)]
    loft(m, [(ell(0.20, 0.145), (xm - 0.03, y, z + 0.56), 0.0)] +
         [(ell(0.20 * f, 0.145 * f), (xm - 0.03, y, z + 0.585 + h), 0.0) for h, f in cowl], "BlackPlastic", cap_bottom=True)
    # tiller arm with its twist grip, folded up (sailing, with the motor stopped, it clears the transom)
    tube(m, [(xm + 0.12, y, z + 0.66), (xm + 0.19, y, z + 0.78), (xm + 0.23, y, z + 0.96)], 0.017, "BlackPlastic", 12)
    tube(m, [(xm + 0.23, y, z + 0.96), (xm + 0.25, y, z + 1.08)], 0.021, "Rubrail", 12)


def block(m, p, axis_y=True, r=0.025, slot="BlackPlastic"):
    """A single block: cheeks round a sheave (axis across Y or X)."""
    x, y, z = p
    for s in (1, -1):
        off = (0, s * 0.012, 0) if axis_y else (s * 0.012, 0, 0)
        cylinder(m, (x + off[0], y + off[1], z), (0, 1, 0) if axis_y else (1, 0, 0), r, 0.004, slot, 16)
    cylinder(m, (x, y - 0.008, z) if axis_y else (x - 0.008, y, z), (0, 1, 0) if axis_y else (1, 0, 0), r * 0.75, 0.016, "Aluminium", 16)


def coil(m, c, r, turns, z, slot="Rope", rope=0.0045, seed=0):
    """A coiled tail lying on deck: a flattened spiral of rope, each turn a little off the last."""
    pts = []
    n = int(turns * 24)
    for k in range(n + 1):
        a = 2 * math.pi * k / 24 + seed
        rr = r * (1.0 + 0.08 * math.sin(3 * a + seed) - 0.06 * k / n)
        pts.append((c[0] + rr * math.cos(a), c[1] + 0.85 * rr * math.sin(a), z + rope * (1.0 + 0.6 * k / n)))
    tube(m, pts, rope, slot, 6, cap=True)


# ---------------------------------------------------------------- the hull

hull = Mesh("SM_J22_Hull")

# Shell: stations from the transom to the stem (closer near the bow where it curves), rows from the keel line to
# the sheer. Rows are split exactly at the paint lines so the antifouling, boot stripe and cove stripe are crisp.
XS = [STERN + (BOW - STERN) * (0.5 - 0.5 * math.cos(math.pi * (i / 150) ** 0.85)) for i in range(151)]
ANTIFOULING_TOP, BOOT_TOP, COVE_LOW, COVE_HIGH = 0.05, 0.11, 0.075, 0.055  # z; cove stripe is measured below the sheer


def shell_rows(x):
    """r values for one station: the bottom in r (it is nearly flat), the topsides in z."""
    s = sheer(x)
    levels = []
    r_af = r_at_z(x, ANTIFOULING_TOP)
    levels += [r_af * (i / 14) for i in range(14)]
    for z0, z1, n in ((ANTIFOULING_TOP, BOOT_TOP, 2), (BOOT_TOP, s - COVE_LOW, 10), (s - COVE_LOW, s - COVE_HIGH, 1), (s - COVE_HIGH, s, 2)):
        for k in range(n):
            levels.append(r_at_z(x, z0 + (z1 - z0) * k / n))
    levels.append(1.0)
    return levels


def shell_slot(z):
    if z < ANTIFOULING_TOP - 1e-4:
        return "Antifouling"
    return "Topsides"


rows = []
for x in XS:
    rs = shell_rows(x)
    rows.append([section_point(x, r) for r in rs])
nr = len(rows[0])
for i in range(len(rows) - 1):
    for j in range(nr - 1):
        x0 = rows[i][j][0]
        zc = 0.25 * (rows[i][j][2] + rows[i][j + 1][2] + rows[i + 1][j][2] + rows[i + 1][j + 1][2])
        s = sheer(0.5 * (XS[i] + XS[i + 1]))
        if zc < ANTIFOULING_TOP:
            slot = "Antifouling"
        elif zc < BOOT_TOP:
            slot = "Bootstripe"
        elif s - COVE_LOW < zc < s - COVE_HIGH:
            slot = "CoveStripe"
        else:
            slot = "Topsides"
        for side in (1, -1):
            q = [rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]]
            q = [(p[0], side * p[1], p[2]) for p in q]
            if side < 0:
                q.reverse()
            hull.face(q, slot)
# Transom: the section at the stern, closed flat.
tr = rows[0]
loop = [(p[0], p[1], p[2]) for p in tr] + [(p[0], -p[1], p[2]) for p in reversed(tr[:-1])]
hull.face(list(reversed(loop)), "Topsides")

# Rubrail along the hull-deck joint.
for side in (1, -1):
    tube(hull, [(x, side * (sharp_half_beam(x) + 0.008), sheer(x) - 0.01) for x in XS[2:-3:3]], 0.014, "Rubrail", 8)

# Graphics G6: the teak toe rails along the deck edge, weathered grey (Bean's lesson photos), from the bow to the cockpit's end.
for side in (1, -1):
    pts = []
    for x in XS[8:-12:3]:
        if x < COCKPIT_AFT + 0.15 or x > BOW - 0.4:
            continue
        y = side * (sharp_half_beam(x) - 0.028)
        pts.append((x, y, deck_z(x, y) + 0.016))
    tube(hull, pts, 0.017, "Teak", 4)

# ---------------------------------------------------------------- deck, cabin trunk, cockpit

# Foredeck: full width forward of the cabin, crowned; non-skid inside a smooth margin.
fx = stations(CABIN_FWD, BOW - 0.002, 40)
fv = [-1 + 2 * k / 24 for k in range(25)]
frows = [[(x, v * sharp_half_beam(x), deck_z(x, v * sharp_half_beam(x)) + 0.002) for v in fv] for x in fx]
hull.grid(frows, "Deck", flip=True, slot_fn=lambda i, j: "NonSkid" if (2 <= j < 22 and 1 <= i < 30) else "Deck")

# Side decks from the transom to the cabin front, and the aft deck behind the cockpit.
sx = stations(STERN, CABIN_FWD, 70)
for side in (1, -1):
    srows = []
    for x in sx:
        b, e = sharp_half_beam(x), inner_edge(x)
        srows.append([(x, side * (b - w * (b - e) / 6), deck_z(x, side * (b - w * (b - e) / 6)) + 0.002) for w in range(7)])
    hull.grid(srows, "Deck", flip=(side > 0), slot_fn=lambda i, j: "NonSkid" if 1 <= j < 5 and sx[i] > COCKPIT_AFT + 0.1 else "Deck")
ax = stations(STERN, COCKPIT_AFT, 3)
arows = [[(x, v * inner_edge(x), deck_z(x, v * inner_edge(x)) + 0.002) for v in fv] for x in ax]
hull.grid(arows, "Deck", flip=True)

# Cabin trunk: sides lean in 0.06 m, a crowned top, the front raked back 0.22 m; windows in the sides.
cx = stations(CABIN_AFT, CABIN_FWD, 40)
WIN_X0, WIN_X1 = CABIN_AFT + 0.25, CABIN_FWD - 0.45


def cabin_top_edge(x):
    e = inner_edge(x) - 0.06
    rake = max(0.0, (x - (CABIN_FWD - 0.22)) / 0.22)
    return e, deck_z(x, inner_edge(x)) + cabin_height(x) * (1 - 0.55 * rake)


for side in (1, -1):
    crows = []
    for x in cx:
        e0 = inner_edge(x)
        e1, ztop = cabin_top_edge(x)
        z0 = deck_z(x, e0)
        col = []
        for k, f in enumerate((0.0, 0.3, 0.75, 1.0)):
            col.append((x, side * (e0 + (e1 - e0) * f), z0 + (ztop - z0) * f))
        crows.append(col)
    hull.grid(crows, "Deck", flip=(side < 0),
              slot_fn=lambda i, j: "CabinWindow" if (j == 1 and WIN_X0 < cx[i] < WIN_X1) else "Deck")
ttop = []
for x in cx:
    e1, ztop = cabin_top_edge(x)
    ttop.append([(x, v * e1, ztop + 0.035 * (1 - v * v)) for v in fv])
hull.grid(ttop, "Deck", flip=True, slot_fn=lambda i, j: "NonSkid" if 3 <= j < 21 and 2 <= i < 36 else "Deck")
# Front of the cabin closes down to the foredeck; aft face is the companionway bulkhead with the washboards.
fe0, fe1 = inner_edge(CABIN_FWD), cabin_top_edge(CABIN_FWD)[0]
front = [(CABIN_FWD, v * fe0, deck_z(CABIN_FWD, v * fe0)) for v in fv]
front_top = [(CABIN_FWD, v * fe1, cabin_top_edge(CABIN_FWD)[1] + 0.035 * (1 - v * v)) for v in fv]
hull.grid([front, front_top], "Deck")
ae0, (ae1, aztop) = inner_edge(CABIN_AFT), cabin_top_edge(CABIN_AFT)
aft_low = [(CABIN_AFT, v * ae0, SOLE_Z) for v in fv]
aft_high = [(CABIN_AFT, v * ae1, aztop + 0.035 * (1 - v * v)) for v in fv]
hull.grid([aft_high, aft_low], "Deck", slot_fn=lambda i, j: "CabinWindow" if 9 <= j < 15 else "Deck")
# Companionway slide and its garage, the forehatch, the mast step.
box(hull, (CABIN_AFT + 0.36, 0, aztop + 0.06), (0.62, 0.62, 0.03), "Deck")
box(hull, (CABIN_AFT + 0.36, 0, aztop + 0.08), (0.56, 0.56, 0.008), "CabinWindow")
for side in (1, -1):
    box(hull, (CABIN_AFT + 0.36, side * 0.33, aztop + 0.05), (0.64, 0.03, 0.04), "Deck")
fh_x = CABIN_FWD + 0.42
box(hull, (fh_x, 0, deck_z(fh_x, 0) + 0.035), (0.5, 0.5, 0.07), "Deck")
box(hull, (fh_x, 0, deck_z(fh_x, 0) + 0.072), (0.44, 0.44, 0.006), "CabinWindow")
mast_step_z = cabin_top_edge(RIG["mast_x"])[1] + 0.035
box(hull, (RIG["mast_x"], 0, mast_step_z + 0.015), (0.2, 0.14, 0.03), "Aluminium")
# Graphics G6: the halyards' turning blocks round the mast step, and the vang's base block.
for k in range(3):
    for side in (1, -1):
        block(hull, (RIG["mast_x"] - 0.12, side * (0.06 + 0.02 * k), mast_step_z + 0.03), axis_y=True, r=0.02)
socket("MastStep", (RIG["mast_x"], 0, mast_step_z))
lazy_x = RIG["mast_x"] + 0.32
socket("LazySheetVia", (lazy_x, 0, cabin_top_edge(lazy_x)[1] + 0.035 + 0.03))

# Cockpit: coaming lip, seat backs, seats, seat fronts, sole, the bridge deck and the aft wall.
kx = stations(COCKPIT_AFT, CABIN_AFT, 30)
for side in (1, -1):
    wall = []
    for x in kx:
        e = inner_edge(x)
        z = deck_z(x, e)
        wall.append([(x, side * (e + 0.02), z + COAMING_H), (x, side * e, z + COAMING_H), (x, side * e, SEAT_Z),
                     (x, side * (e - SEAT_W), SEAT_Z), (x, side * (e - SEAT_W), SOLE_Z)])
    hull.grid(wall, "Deck", flip=(side < 0), slot_fn=lambda i, j: "NonSkid" if j == 2 else "Deck")
    # Outside of the coaming (deck to lip).
    hull.grid([[(x, side * (inner_edge(x) + 0.02), deck_z(x, inner_edge(x)) + 0.002), (x, side * (inner_edge(x) + 0.02), deck_z(x, inner_edge(x)) + COAMING_H)] for x in kx], "Deck", flip=(side > 0))
    # J/22 light match: the teak cap along the coaming's lip (the hero's; Bean's cockpit photos), a wood line that reads
    # from the next boat over.
    tube(hull, [(x, side * (inner_edge(x) + 0.01), deck_z(x, inner_edge(x)) + COAMING_H + 0.006) for x in kx[1:-1:2]], 0.016, "Teak", 4)
sole = [[(x, v * (inner_edge(x) - SEAT_W), SOLE_Z) for v in fv] for x in kx]
hull.grid(sole, "NonSkid", flip=True)
for x, ztop in ((COCKPIT_AFT, None), ):
    e = inner_edge(x)
    hull.grid([[(x, v * e, deck_z(x, v * e)) for v in fv], [(x, v * (e - SEAT_W), SOLE_Z) for v in fv]], "Deck")

# Keel: lead fin, NACA 0012, swept leading edge, from inside the canoe body to the class draft. Plan form from the class
# template (boat kit phase 3, docs/boatkit-3): chord 0.965 m at MPA (216 mm under the hull) and 0.603 m 483 mm lower,
# trailing edge 2.90 m forward of the transom, drawn as in Inputs/j22-hero/build_j22_hero.py (keel_edges). The physics
# keel's Center stays where the polar put it (a balance knob, not the drawn fin).
root_z, tip_z = -keel_line_depth(0.0) + 0.06, -CFG["draft"]
mpa_z = -keel_line_depth(0.0) - 0.216
keel = []
for k in range(9):
    t = k / 8
    z = root_z + (tip_z - root_z) * t
    d = mpa_z - z
    le, te = 0.465 - 0.708 * d, -0.500 + 0.041 * d
    keel.append((z, le, le - te))
foil(hull, keel, "Keel", 0.12)

# Chainplates, stem fitting, backstay plate.
for side, tag in ((1, "S"), (-1, "P")):
    # abeam of the mast and 26 cm aft of it, so they follow the physics' MastX (moved to the class's J, boat kit phase 2)
    for name, x in (("Upper", RIG["mast_x"] - 0.02), ("Lower", RIG["mast_x"] - 0.28)):
        y = side * (sharp_half_beam(x) - 0.05)
        rbox(hull, (x, y, deck_z(x, y) + 0.035), (0.06, 0.012, 0.07), "Stainless", r=0.005, chamfer=0.02)
        rbox(hull, (x, y, deck_z(x, y) + 0.003), (0.09, 0.04, 0.006), "Stainless", r=0.012)
        socket(f"Chainplate{name}_{tag}", (x, y, deck_z(x, y) + 0.07))
stem_x = BOW - 0.09
rbox(hull, (stem_x, 0, deck_z(stem_x, 0) + 0.012), (0.18, 0.06, 0.012), "Stainless", r=0.02)
rbox(hull, (stem_x + 0.02, 0, deck_z(stem_x, 0) + 0.04), (0.10, 0.012, 0.05), "Stainless", r=0.005, chamfer=0.018)
bolts(hull, [(stem_x - 0.06, 0.0), (stem_x - 0.03, 0.0)], deck_z(stem_x, 0) + 0.018)
socket("ForestayTack", (stem_x + 0.04, 0, deck_z(stem_x, 0) + 0.06))
socket("BackstayPlate", (STERN + 0.03, 0, sheer(STERN) + 0.04))
rbox(hull, (STERN + 0.03, 0, sheer(STERN) + 0.004), (0.07, 0.10, 0.008), "Stainless", r=0.015)
rbox(hull, (STERN + 0.03, 0, sheer(STERN) + 0.025), (0.04, 0.012, 0.04), "Stainless", r=0.005, chamfer=0.015)

# No pulpits, stanchions or lifelines: the lesson J/22s (TX 7295 EC, 7297 EC; photos IMG_9224, 9272, 9273) sail
# with an open deck, and the hero model has none either (round 12 caught them, docs/boatkit-4).

# Winches, cam cleats, jib tracks and cars, cleats, the traveler.
for side, tag in ((1, "S"), (-1, "P")):
    wx = CABIN_AFT - 0.28
    wy = side * (inner_edge(wx) + 0.16)
    wz = deck_z(wx, wy)
    rbox(hull, (wx, wy, wz + 0.004), (0.20, 0.20, 0.008), "BlackPlastic", r=0.05, chamfer=0.004)
    bolts(hull, [(wx + 0.088 * math.cos(a), wy + 0.088 * math.sin(a)) for a in (2 * math.pi * k / 5 + 0.3 for k in range(5))], wz + 0.008, 0.004)
    winch(hull, wx, wy, wz + 0.008)
    socket(f"JibWinch_{tag}", (wx, wy, wz + 0.07))
    socket(f"JibTailer_{tag}", (wx, wy, wz + 0.11))
    cx2 = wx - 0.25
    cam_cleat(hull, cx2, side * (inner_edge(cx2) + 0.1), deck_z(cx2, inner_edge(cx2)), 0.0)
    # The jib sheet's tail: from the self-tailer down onto the cockpit seat, the rest coiled there.
    sz = SEAT_Z + 0.002
    ty0 = side * (inner_edge(wx - 0.35) - 0.12)
    tube(hull, [(wx - 0.02, wy - side * 0.06, wz + 0.11), (wx - 0.12, wy - side * 0.1, wz + 0.05), (wx - 0.25, ty0, sz + 0.02), (wx - 0.38, ty0, sz + 0.005)],
         0.0045, "Rope", 6)
    coil(hull, (wx - 0.55, ty0), 0.11, 3.0, sz, seed=0.7 * side)
    # Rope clutches beside the companionway (halyards, cunningham), their tails coiled on the cabin top's aft edge.
    for k in range(3):
        kx = CABIN_AFT + 0.12
        ky = side * (0.42 + 0.05 * k)
        kz = cabin_top_edge(kx)[1] + 0.035 * (1 - (ky / cabin_top_edge(kx)[0]) ** 2)
        # a rope clutch: cast body with the line through it and the lever folded down over the top
        rbox(hull, (kx, ky, kz + 0.004), (0.13, 0.042, 0.008), "BlackPlastic", r=0.012)
        rbox(hull, (kx, ky, kz + 0.022), (0.11, 0.036, 0.03), "Aluminium", r=0.012, chamfer=0.012)
        tube(hull, [(kx - 0.05, ky, kz + 0.04), (kx - 0.01, ky, kz + 0.047), (kx + 0.05, ky, kz + 0.044)], 0.007, "BlackPlastic", 10)
        bolts(hull, [(kx - 0.058, ky), (kx + 0.058, ky)], kz + 0.008, 0.0035)
        # Its halyard runs forward along the cabin top to the turning block at the mast step.
        hx = RIG["mast_x"] - 0.12
        tube(hull, [(kx + 0.06, ky, kz + 0.02), (0.5 * (kx + hx), side * (0.3 + 0.04 * k), cabin_top_edge(0.5 * (kx + hx))[1] + 0.04), (hx, side * (0.06 + 0.02 * k), cabin_top_edge(hx)[1] + 0.05)],
             0.004, "Rope", 6)
    coil(hull, (CABIN_AFT + 0.05, side * 0.55), 0.09, 2.5, cabin_top_edge(CABIN_AFT + 0.05)[1] + 0.01, seed=1.3 * side)
    # J/22 light match: the teak grab rail on the cabin top (the hero's), a bar on three legs.
    hx0, hx1 = CABIN_AFT + 0.32, CABIN_AFT + 1.30

    def top_at(x, y):
        e, zt = cabin_top_edge(x)
        return zt + 0.035 * (1 - (y / e) ** 2)
    hy = side * (cabin_top_edge(0.5 * (hx0 + hx1))[0] - 0.14)
    tube(hull, [(x, hy, top_at(x, hy) + 0.06) for x in (hx0, 0.5 * (hx0 + hx1), hx1)], 0.014, "Teak", 4)
    for k in range(3):
        x = hx0 + 0.04 + (hx1 - hx0 - 0.08) * k / 2
        box(hull, (x, hy, top_at(x, hy) + 0.03), (0.05, 0.026, 0.06), "Teak")
    # Jib track on the side deck and its car with a block.
    tx0, tx1 = 0.45, -0.25
    ty = side * (sharp_half_beam(0.1) - 0.24)
    tube(hull, [(tx0, ty, deck_z(tx0, ty) + 0.006), (tx1, ty, deck_z(tx1, ty) + 0.006)], 0.008, "Aluminium", 6)
    carx = 0.12
    rbox(hull, (carx, ty, deck_z(carx, ty) + 0.02), (0.08, 0.035, 0.03), "Aluminium", r=0.01, chamfer=0.01)
    cylinder(hull, (carx, ty - side * 0.0, deck_z(carx, ty) + 0.035), (0, 1, 0), 0.025, 0.02, "BlackPlastic", 16)
    socket(f"JibLead_{tag}", (carx, ty, deck_z(carx, ty) + 0.05))
    # Stern cleats.
    sx2 = STERN + 0.22
    sy2 = side * (sharp_half_beam(sx2) - 0.12)
    horn_cleat(hull, sx2, sy2, deck_z(sx2, sy2), 0.16, 0.0)
bx = BOW - 0.45
# J/22 light match (the hero's boat fidelity 3, Bean's bow photos): two small horn cleats abreast instead of one on the
# centreline. The BowCleat socket stays on the centreline between them (nothing reads it; build_berthed.py reads these
# sockets, so it doesn't move).
for side in (1, -1):
    by = side * 0.13
    horn_cleat(hull, BOW - 0.42, by, deck_z(BOW - 0.42, by), 0.13, 0.0)
socket("BowCleat", (bx, 0, deck_z(bx, 0) + 0.04))
TRAV_X = -1.75
te = inner_edge(TRAV_X) - SEAT_W
tube(hull, [(TRAV_X, -te, SEAT_Z + 0.02), (TRAV_X, te, SEAT_Z + 0.02)], 0.012, "Aluminium", 8)
for side in (1, -1):
    rbox(hull, (TRAV_X, side * te, SEAT_Z + 0.02), (0.06, 0.035, 0.04), "Aluminium", r=0.012, chamfer=0.012)
socket("Traveler_S", (TRAV_X, te - 0.05, SEAT_Z + 0.05))
socket("Traveler_P", (TRAV_X, -te + 0.05, SEAT_Z + 0.05))
socket("Traveler_C", (TRAV_X, 0, SEAT_Z + 0.05))
# The traveler sits on a bridge across the cockpit at seat height.
box(hull, (TRAV_X, 0, SEAT_Z - 0.005), (0.16, 2 * te, 0.03), "Deck")

# Gudgeons on the transom for the rudder: each a plate with two lugs, above and below the pintle strap (the hero's, from
# Bean's transom photos).
for z in (0.32, 0.56):
    rbox(hull, (STERN + 0.001, 0, z), (0.006, 0.10, 0.08), "Stainless", r=0.01)
    for dz in (0.022, -0.022):
        rbox(hull, (STERN - 0.02, 0, z + dz), (0.05, 0.06, 0.016), "Stainless", r=0.008, chamfer=0.006)
# The cockpit drains' outlets low on the transom: white flanges round dark bores (Bean's transom photos).
zb = -keel_line_depth(STERN)
for side in (1, -1):
    zd = zb + 0.07
    yd = side * 0.42 * half_beam(STERN, zd) * r_at_z(STERN, zd)
    cylinder(hull, (STERN + 0.004, yd, zd), (-1, 0, 0), 0.030, 0.008, "Rubrail", 16)    # (not a canoe slot: J22Mesh measures those)
    cylinder(hull, (STERN - 0.003, yd, zd), (-1, 0, 0), 0.016, 0.003, "BlackPlastic", 12)

# The outboard on its bracket, where the physics puts the engine (round 12: the game drew a grey box there; the pawn
# skips that box when the model has an "Outboard" socket).
# Drawn with the bracket in its raised, sailing position (photo IMG_9273: the cowl stands above the transom and the
# leg's foot is at the water), 0.30 m above the physics prop, which is where the motor sits lowered to drive.
BRACKET_UP = 0.30
for E in CFG.get("engines", []):
    ex, ey, ez = E["position"]
    outboard(hull, STERN, ey, ez + BRACKET_UP)
    socket("Outboard", (STERN - 0.33, ey, ez + BRACKET_UP))

# Hull graphics: the class mark on each bow.
def text_mesh(body, size, x, z, side, slot, shear=0.22):
    curve = bpy.data.curves.new("txt", type="FONT")
    curve.body = body
    curve.size = size
    curve.shear = shear
    curve.extrude = 0.0012
    curve.align_x = "CENTER"
    tobj = bpy.data.objects.new("txt", curve)
    bpy.context.scene.collection.objects.link(tobj)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tobj.evaluated_get(deps))
    bpy.data.objects.remove(tobj)
    bm2 = bmesh.new()
    bm2.from_mesh(me)
    # Standing in the X-Z plane; reads bow-ward on starboard, aft-ward... both read left to right from outside.
    for v in bm2.verts:
        lx, ly, lz = v.co
        if side > 0:   # starboard: viewer outside looks toward -Y (body); text runs toward the bow
            px, pz, py_out = x + lx, z + ly, lz
        else:          # port: text runs toward the stern
            px, pz, py_out = x - lx, z + ly, lz
        yb = half_beam(px, pz) * r_at_z(px, pz) if pz > -keel_line_depth(px) else 0.0
        v.co = Vector((px, -(side * (yb + 0.003 + py_out)), pz))
    for f in bm2.faces:
        hull.face([(vv.co.x, -vv.co.y, vv.co.z) for vv in f.verts], slot)
    bm2.free()
    bpy.data.meshes.remove(me)


for side in (1, -1):
    text_mesh("J/22", 0.15, 2.15, sheer(2.15) - 0.24, side, "Graphics")

hull_obj = hull.finish(smooth_angle=40.0)

# ---------------------------------------------------------------- mast, boom, rudder (separate: they move or bend)

mast = Mesh("SM_J22_Mast")
MAST_X, MAST_TOP = RIG["mast_x"], RIG["masthead_z"]
HOUNDS_Z = CFG["jib"][-1]["z_top"] + 0.05
SPREADER_Z = 0.55 * (HOUNDS_Z - mast_step_z) + mast_step_z
mz = [mast_step_z + (MAST_TOP - mast_step_z) * k / 30 for k in range(31)]
rings = []
for z in mz:
    taper = 1.0 if z < HOUNDS_Z else 1.0 - 0.35 * (z - HOUNDS_Z) / (MAST_TOP - HOUNDS_Z)
    a, b = 0.5 * RIG["mast_diameter"] * taper, 0.034 * taper
    rings.append([(MAST_X + a * math.cos(2 * math.pi * k / 20), b * math.sin(2 * math.pi * k / 20), z) for k in range(21)])
mast.grid(rings, "Aluminium")
mast.face(rings[-1][:-1], "Aluminium")
for side, tag in ((1, "S"), (-1, "P")):
    tip = (MAST_X - 0.16, side * 0.62, SPREADER_Z + 0.04)
    tube(mast, [(MAST_X - 0.02, side * 0.03, SPREADER_Z), tip], 0.016, "Aluminium", 8)
    socket(f"SpreaderTip_{tag}", tip)
box(mast, (MAST_X + 0.06, 0, HOUNDS_Z), (0.05, 0.05, 0.06), "Stainless")
socket("Hounds", (MAST_X + 0.08, 0, HOUNDS_Z))
socket("LowerTang", (MAST_X, 0, SPREADER_Z - 0.05))
box(mast, (MAST_X - 0.06, 0, MAST_TOP + 0.02), (0.22, 0.05, 0.04), "Aluminium")
socket("MastheadAft", (MAST_X - 0.16, 0, MAST_TOP + 0.02))
box(mast, (MAST_X - 0.06, 0, RIG["boom_z"]), (0.06, 0.06, 0.08), "Stainless")
socket("MastBase", (MAST_X - 0.06, 0, mast_step_z + 0.2))
mast_obj = mast.finish(smooth_angle=60.0, origin=(MAST_X, 0, mast_step_z), pack=False)

boom = Mesh("SM_J22_Boom")
GX, GZ = RIG["main_luff_x"], RIG["boom_z"]
BOOM_LEN = RIG["main_foot_chord"] + 0.08
bx_ = [GX - BOOM_LEN * k / 16 for k in range(17)]
rings = [[(x, 0.03 * math.sin(2 * math.pi * k / 16), GZ - 0.02 + 0.05 * math.cos(2 * math.pi * k / 16)) for k in range(17)] for x in bx_]
boom.grid(rings, "Aluminium", flip=True)
boom.face(rings[0][:-1], "Aluminium")
boom.face(list(reversed(rings[-1][:-1])), "Aluminium")
box(boom, (GX - BOOM_LEN + 0.04, 0, GZ - 0.02), (0.1, 0.07, 0.11), "BlackPlastic")
box(boom, (GX - 0.62, 0, GZ - 0.08), (0.06, 0.03, 0.03), "Stainless")
box(boom, (TRAV_X, 0, GZ - 0.08), (0.06, 0.03, 0.03), "Stainless")
socket("Boom_Vang", (GX - 0.62, 0, GZ - 0.09))
socket("Boom_Mainsheet", (TRAV_X, 0, GZ - 0.09))
socket("Boom_Clew", (GX - BOOM_LEN + 0.06, 0, GZ + 0.04))
boom_obj = boom.finish(smooth_angle=60.0, origin=(GX, 0, GZ))

rudder = Mesh("SM_J22_Rudder")
STOCK_X = STERN - 0.05
blade = []
for k in range(9):
    t = k / 8
    z = 0.28 + (-0.92 - 0.28) * t
    chord = 0.42 + (0.28 - 0.42) * t ** 1.5
    blade.append((z, STOCK_X + 0.03, chord))
foil(rudder, blade, "Topsides", 0.11)  # round 11: white gelcoat (J/22s are dry-sailed; a dark blade read as a grey slab)
box(rudder, (STOCK_X - 0.06, 0, 0.5), (0.2, 0.05, 0.46), "Topsides")       # rudder head cheeks
TILLER_Z0 = sheer(STERN) + 0.1
tiller = [(STOCK_X - 0.02, 0, TILLER_Z0)]
for k in range(1, 9):
    t = k / 8
    # J/22 light match: the hero's laminated tiller sweeps up out of the head and runs nearly level to the grip (Bean's
    # tiller photos); both ends stay where they were, so TillerEnd and RudderStock don't move.
    tiller.append((STOCK_X + RIG["tiller_length"] * t, 0, TILLER_Z0 + 0.1 * t * t * (3 - 2 * t) + 0.04 * math.sin(math.pi * t) * (1 - t)))
# one smooth taper (round 12: drawn as eight stepped segments, each capped, it shaded in bands like a repeating texture)
tube(rudder, tiller, 0.022, "Wood", 16, radii=[0.022 - 0.008 * max(0.0, (p[0] - STOCK_X) / RIG["tiller_length"]) for p in tiller])
end = tiller[-1]
cylinder(rudder, (end[0] - 0.01, 0, end[2] + 0.02), (0, 0, 1), 0.012, 0.03, "BlackPlastic", 12)
# Graphics G6: the tiller extension is drawn by the pawn (BoatModelVisuals.cpp), from here to the helm's hand.
socket("TillerEnd", end)
socket("RudderStock", (STOCK_X, 0, TILLER_Z0))
socket("RudderPivot", (STOCK_X, 0, 0))
rudder_obj = rudder.finish(smooth_angle=45.0, origin=(STOCK_X, 0, 0))

# ---------------------------------------------------------------- measures (printed and written for the tests)

def measure(obj, slots, z_cut=0.0):
    """Volume and centroid below z_cut of the faces in the given slots (Unreal body frame, metres)."""
    me = obj.data
    me.calc_loop_triangles()
    mw = obj.matrix_world
    vol, mom = 0.0, Vector((0, 0, 0))
    idx = {i for i, m in enumerate(me.materials) if m and m.name.split(".")[0] in slots}
    for tri in me.loop_triangles:
        if tri.material_index not in idx:
            continue
        p = [mw @ me.vertices[i].co for i in tri.vertices]
        poly = clip_below(p, z_cut)
        for k in range(1, len(poly) - 1):
            a, b, c = poly[0], poly[k], poly[k + 1]
            v = a.dot(b.cross(c)) / 6.0
            vol += v
            mom += v * (a + b + c) / 4.0
    cen = mom / vol if abs(vol) > 1e-9 else Vector((0, 0, 0))
    return abs(vol), Vector((cen.x, -cen.y, cen.z))


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


# The canoe slots, or the pack that holds exactly them (pc/boat-slots: the finished mesh is packed)
CANOE = ("Topsides", "Bootstripe", "CoveStripe", "Antifouling", "PackCanoe")
vol, cb = measure(hull_obj, CANOE)
xs = [(hull_obj.matrix_world @ v.co) for v in hull_obj.data.vertices]
# length of the hull shell alone, as SailingSim.Visual.J22Mesh measures it (the outboard hangs aft of the transom)
canoe_slots = {i for i, m in enumerate(hull_obj.data.materials) if m and m.name.split(".")[0] in CANOE}
cx = [(hull_obj.matrix_world @ hull_obj.data.vertices[i].co).x for f in hull_obj.data.polygons if f.material_index in canoe_slots for i in f.vertices]
loa = max(cx) - min(cx)
beam = 2 * max(abs(v.y) for v in xs if v.z < sheer(v.x) + 0.02 and v.z > 0.0)
draft = -min(v.z for v in xs)
print(f"J22: LOA {loa:.3f} m, beam {beam:.3f} m, draft {draft:.3f} m, canoe volume {vol:.3f} m^3 (physics {CFG['design_volume']:.3f}), "
      f"CB ({cb.x:.3f}, {cb.y:.3f}, {cb.z:.3f}) (physics {CFG['design_cb']})")
print(f"J22: triangles hull {sum(len(p.vertices) - 2 for p in hull_obj.data.polygons)}, mast {len(mast_obj.data.polygons)}, "
      f"boom {len(boom_obj.data.polygons)}, rudder {len(rudder_obj.data.polygons)}")
OWNER = {}
for name in SOCKETS:
    if name in ("Hounds", "LowerTang", "MastheadAft", "MastBase") or name.startswith("SpreaderTip"):
        OWNER[name] = "SM_J22_Mast"
    elif name.startswith("Boom_"):
        OWNER[name] = "SM_J22_Boom"
    elif name in ("TillerEnd", "RudderStock"):
        OWNER[name] = "SM_J22_Rudder"
    else:
        OWNER[name] = "SM_J22_Hull"
ORIGINS = {o.name: [round(o.location.x * 100, 2), round(-o.location.y * 100, 2), round(o.location.z * 100, 2)]
           for o in (hull_obj, mast_obj, boom_obj, rudder_obj)}
json.dump({"sockets": SOCKETS, "owner": OWNER, "origins": ORIGINS, "measures": {"loa": loa, "beam": beam, "draft": draft, "canoe_volume": vol,
           "cb": [cb.x, cb.y, cb.z]}}, open(os.path.join(OUT, "J22_sockets.json"), "w"), indent=1)

# ---------------------------------------------------------------- export

for obj in (hull_obj, mast_obj, boom_obj, rudder_obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    loc = obj.location.copy()
    obj.location = (0, 0, 0)     # export about the object's own origin (pivot)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, obj.name + ".fbx"), use_selection=True, axis_forward="X",
                             axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False, bake_space_transform=True)
    obj.location = loc
print("J22: exported", ", ".join(o.name for o in (hull_obj, mast_obj, boom_obj, rudder_obj)))
