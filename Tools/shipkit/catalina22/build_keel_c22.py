"""The Catalina 22's swing keel, keel stub and trunk, kick-up rudder and outboard as meshes (docs/c22-4), from keel_c22.

Imported by build_c22.py (needs Blender's Python). Built in the game's frame (X forward, Y starboard, Z up) and
written with Y mirrored to Blender's port-positive Y, as the hull and deck are (build_deck_c22.Mesh).

Objects:
  C22_Keel       the swing keel, down: a cast-iron plate with rounded edges, its pin through the stub
  C22_KeelUp     the same turned up about its pin to the raised draft (hidden; with --keel-up it is built in place of
                 the down one, under the name C22_Keel, and the down one is hidden as C22_KeelDown)
  C22_KeelStub   the stub moulded under the hull with the slot along its bottom, the slot's walls up into the hull,
                 and the trunk inside the hull where the keel's top swings
  C22_Rudder     the kick-up rudder: the head's two aluminium cheeks, its spine, bolts and pintles (the kit's), the
                 blade, and the tiller to today's TillerEnd socket. The game turns it about RudderPivot.
  C22_RudderUp   the same with the blade kicked up about its bolt (hidden; built in place with --keel-up)
  C22_Gudgeons   the four strap gudgeons on the transom (the kit's), two round each pintle
  C22_Outboard   the kit's two-position bracket and 3.5 hp outboard on the starboard quarter, as today's model has them
"""
import math
import os
import sys

import bpy
from mathutils import Matrix

import build_deck_c22 as BD
import keel_c22 as KC

KIT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "boatkit")
RD = KC.RD
TRANSOM_X = -3.25
PIN_R, PIN_N = 0.0127, 12                       # the keel's 1 in pin
PIN_HALF = KC.SL["half_width"] + 0.004          # its ends just inside the stub's walls, which hide them
PINTLE_CHORD = 0.23   # the kit's pintle straps follow a NACA section of this chord and thickness: chosen so they lie
PINTLE_BLADE = 0.06   # on the head's cheeks (0.027 a side) from 0 to 3 mm proud, never inside them


class Mesh(BD.Mesh):
    """build_deck_c22's Mesh, which can be sealed: its own faces welded and cleaned before the kit's parts are merged
    in, so the kit's separate shells (a pin through a barrel, a bolt on a strap) keep their own vertices."""

    def __init__(self, name):
        super().__init__(name)
        self.sealed = False

    def seal(self):
        import bmesh
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-6)
        bmesh.ops.dissolve_degenerate(self.bm, dist=1e-6, edges=self.bm.edges[:])
        bmesh.ops.delete(self.bm, geom=[v for v in self.bm.verts if not v.link_faces], context="VERTS")
        self.sealed = True

    def finish(self, materials, weld=1e-6):
        if not self.sealed:
            self.seal()
        return super().finish(materials, weld=0.0)


def plate(m, rows, half, slot, xz=lambda x, z: (x, z), nu=16):
    """A plate from rows (z, x_aft, x_fwd): its two faces at +-half(xa, xf, x), meeting on the outline (half 0 there),
    each point taken through xz (a turn). Columns bunch toward both edges, where they round."""
    for side in (1, -1):
        grid = []
        for z, xa, xf in rows:
            r = []
            for j in range(nu + 1):
                u = 0.5 - 0.5 * math.cos(math.pi * j / nu)
                x = xa + (xf - xa) * u
                h = half(xa, xf, x) if 0 < j < nu else 0.0
                px, pz = xz(x, z)
                r.append((px, side * h, pz))
            grid.append(r)
        m.grid(grid, slot, lambda mid, s=side: (0, s, 0))


def cylinder_y(m, x, z, r, y0, y1, slot, n=12):
    """A short cylinder across the boat (along Y) at (x, z), from y0 to y1, capped."""
    ring = lambda y: [(x + r * math.cos(2 * math.pi * k / n), y, z + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    a, b = ring(y0), ring(y1)
    m.grid([a + a[:1], b + b[:1]], slot, lambda mid: (mid[0] - x, 0, mid[2] - z))
    m.polygon(a, slot, (0, -1 if y0 < y1 else 1, 0))
    m.polygon(b, slot, (0, 1 if y0 < y1 else -1, 0))


# ------------------------------------------------------------------ the keel

def build_keel(mats, phi=0.0, name="C22_Keel"):
    m = Mesh(name)
    t = KC.thickness()
    rows = KC.keel_rows(60)
    turn = lambda x, z: KC.turn([(x, z)], phi)[0]
    plate(m, rows, lambda xa, xf, x: KC.half_t(t, xa, xf, x), "Keel", turn)
    # the pin: 1 in through both bronze castings, its ends just inside the stub's walls (the stub hides them)
    px, pz = KC.KL["pivot"]
    cylinder_y(m, px, pz, PIN_R, -PIN_HALF, PIN_HALF, "Stainless", n=PIN_N)
    return m.finish(mats)


def pin_volume():
    """The keel pin's volume as meshed (the report takes it off the keel's: it is stainless, not iron)."""
    return 0.5 * PIN_N * PIN_R ** 2 * math.sin(2 * math.pi / PIN_N) * 2 * PIN_HALF


# ------------------------------------------------------------------ the stub and the trunk

def stub_stations():
    x0, x1 = KC.ST["x"]
    base = [x0 + (x1 - x0) * k / 90 for k in range(91)]
    keep = list(KC.SL["x"]) + list(KC.ST["full_x"]) + [x for x, _ in KC.trunk_knots()]
    base = [x for x in base if all(abs(x - c) > 0.006 for c in keep)]
    return sorted(base + keep)


def build_stub(mats):
    m = Mesh("C22_KeelStub")
    xs = stub_stations()
    s0, s1 = KC.SL["x"]
    s = KC.SL["half_width"]
    rows, secs = [], {}
    for x in xs:
        port = KC.stub_section(x)
        secs[x] = port
        row = [(x, y, z) for y, z in port] + [(x, -y, z) for y, z in reversed(port)]
        rows.append(row)
    n = len(rows[0]) // 2
    in_slot = lambda xm: s0 - 1e-9 <= xm <= s1 + 1e-9

    def skip(i, j):
        return j == n - 1 and in_slot(0.5 * (xs[i] + xs[i + 1]))

    m.grid(rows, "Antifouling", lambda mid: (0, mid[1], -0.02), skip=skip)
    # the slot's walls, from the stub's slot edges up to the slot's top (KC.trunk_top: the trunk inside the hull)
    sx = [x for x in xs if s0 - 1e-9 <= x <= s1 + 1e-9]
    top = KC.trunk_top
    nz = 8
    for sign in (-1, 1):
        wall = [[(x, sign * s, secs[x][-1][1] + (top(x) - secs[x][-1][1]) * k / nz) for x in sx] for k in range(nz + 1)]
        m.grid(wall, "Antifouling", lambda mid, sg=sign: (0, -sg, 0))
    # the slot's two ends and its top, all facing into the slot
    for x, facing in ((s0, 1), (s1, -1)):
        z0 = secs[x][-1][1]
        m.polygon([(x, -s, z0), (x, s, z0), (x, s, top(x)), (x, -s, top(x))], "Antifouling", (facing, 0, 0))
    m.grid([[(x, -s, top(x)) for x in sx], [(x, s, top(x)) for x in sx]], "Antifouling", lambda mid: (0, 0, -1))
    # the trunk's outside in the cabin: its walls from just under the hull's bottom, its ends and its top
    w = s + KC.SL["wall"]
    H = KC._hull()
    base = lambda x: H.keel_z(x) - 0.01
    zt = lambda x: top(x) + KC.SL["wall"]
    for sign in (-1, 1):
        m.grid([[(x, sign * w, base(x)) for x in sx], [(x, sign * w, zt(x)) for x in sx]], "Deck",
               lambda mid, sg=sign: (0, sg, 0))
    for x, facing in ((s0, -1), (s1, 1)):
        m.polygon([(x, -w, base(x)), (x, w, base(x)), (x, w, zt(x)), (x, -w, zt(x))], "Deck", (facing, 0, 0))
    m.grid([[(x, -w, zt(x)) for x in sx], [(x, w, zt(x)) for x in sx]], "Deck", lambda mid: (0, 0, 1))
    return m.finish(mats)


# ------------------------------------------------------------------ the kit's parts

def kit_into(m, name, x, y, z, yaw=0.0, **kw):
    """One of the shared kit's parts (Tools/boatkit/bk_parts.py) merged into m at (x, y, z), game frame, yaw about
    Z (pi turns its +X aft). Returns its sockets in the game frame."""
    if KIT_DIR not in sys.path:
        sys.path.insert(0, KIT_DIR)
    import bk_parts as KP   # noqa: E402 (needs bpy)
    ob = KP.build(name, **kw)
    xf = Matrix.Translation((x, -y, z)) @ Matrix.Rotation(-yaw, 4, "Z")
    socks = {}
    for c in list(ob.children):
        if c.name.startswith("SOCKET_"):
            p = xf @ (ob.matrix_world @ c.location)
            socks[c.name[7:].split(".")[0]] = (p.x, -p.y, p.z)
        bpy.data.objects.remove(c)
    me = ob.data
    me.transform(ob.matrix_world)
    me.transform(xf)
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    first = len(m.bm.faces)
    m.bm.from_mesh(me)
    m.bm.faces.ensure_lookup_table()
    names = [mt.name.split(".")[0] for mt in me.materials]
    for f in m.bm.faces[first:]:
        f.material_index = m.slot(names[f.material_index] if names else "Stainless")
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return socks


# ------------------------------------------------------------------ the rudder

def head_outline():
    """The head's cheek outline (x, z): its front just aft of the pintles, narrowing to its top; corners rounded."""
    px, HD = RD["pivot_x"], RD["head"]
    (z0, z1) = HD["z"]
    xf = px - 0.03
    pts = [(xf, z0), (xf, z1), (xf - HD["chord_top"], z1), (xf - HD["chord_bottom"], z0)]
    return BD.DK.round_polygon(pts, 0.025, 5)


def build_rudder(mats, kick=0.0, name="C22_Rudder"):
    m = Mesh(name)
    px, HD, B = RD["pivot_x"], RD["head"], RD["blade"]
    bx, bz = px + HD["bolt"][0], HD["bolt"][1]
    gap, pl = HD["blade_slot"] / 2, HD["plate"]
    # the cheeks: two aluminium plates either side of the blade
    out = head_outline()
    for sg in (-1, 1):
        y0, y1 = sg * gap, sg * (gap + pl)
        m.polygon([(x, y0, z) for x, z in out], "Aluminium", (0, -sg, 0))
        m.polygon([(x, y1, z) for x, z in out], "Aluminium", (0, sg, 0))
        ring = out + out[:1]
        m.grid([[(x, y0, z) for x, z in ring], [(x, y1, z) for x, z in ring]], "Aluminium",
               lambda mid, c=(sum(p[0] for p in out) / len(out), sum(p[1] for p in out) / len(out)): (mid[0] - c[0], 0, mid[2] - c[1]))
    # the spine closing the head's front between the cheeks, from its foot to the tiller
    xf = px - 0.03
    (z0, z1) = HD["z"]
    T = RD["tiller"]
    spine_top = T["root_z"] - T["depth"][0] / 2 + 0.002          # up to the tiller's underside, 2 mm into it
    BD.box(m, (xf - 0.03, -gap - 0.0005, z0 + 0.01), (xf - 0.002, gap + 0.0005, spine_top), "Aluminium")
    # the bolts: the blade's pivot and the tiller's, through both cheeks, heads proud of them
    for (x, z) in ((bx, bz), (px + T["bolt_dx"], T["root_z"])):
        cylinder_y(m, x, z, 0.006, -(gap + pl + 0.004), gap + pl + 0.004, "Stainless")
        for sg in (-1, 1):
            cylinder_y(m, x, z, 0.011, sg * (gap + pl), sg * (gap + pl + 0.005), "Stainless", n=6)
    # the blade: a NACA 00xx section on each row, kicked up about its bolt by `kick`
    turn = lambda x, z: KC.turn([(x, z)], kick, about=(bx, bz))[0]
    plate(m, KC.blade_rows(56), lambda xa, xf_, x: KC.naca_half(x, xa, xf_, B["thickness"]), "Topsides", turn, nu=20)
    build_tiller(m)
    m.seal()
    # the pintles on the head's front, one at each pair of gudgeons
    for zg in RD["gudgeons_z"]:
        # (the kit lays its straps on a NACA section: this one is within 3 mm of the cheeks' flat faces over the straps)
        kit_into(m, "Pintle", px, 0.0, zg, math.pi, blade=PINTLE_BLADE, chord=PINTLE_CHORD, length=0.10)
    return m.finish(mats)


def build_tiller(m, n=12):
    """The tiller: a rounded section tapering from the head to its end, which rounds off at TillerEnd."""
    T = RD["tiller"]
    path = KC.tiller_path()
    (d0, d1), (w0, w1) = T["depth"], T["width"]
    rings = []
    for k, (x, z) in enumerate(path):
        u = k / (len(path) - 1)
        d, w = d0 + (d1 - d0) * u, w0 + (w1 - w0) * u
        rings.append([(x, w / 2 * _se(math.cos(a)), z + d / 2 * _se(math.sin(a)))
                      for a in [2 * math.pi * j / n for j in range(n)]])
    x1, z1 = path[-1]
    for k in range(1, 5):                                       # the end, rounded off
        a = math.pi / 2 * k / 5
        f, dx = math.cos(a), d1 / 2 * math.sin(a)
        rings.append([(x1 + dx, p[1] * f, z1 + (p[2] - z1) * f) for p in rings[len(path) - 1]])
    grid = [r + r[:1] for r in rings]
    m.grid(grid, "Wood", lambda mid: (0, mid[1], 0.0) if abs(mid[1]) > 1e-4 else (0, 0, 1))
    m.polygon(rings[0], "Wood", (-1, 0, 0))
    m.polygon(rings[-1], "Wood", (1, 0, 0))


def _se(c, p=0.6):
    """A superellipse's coordinate: |c|^p with c's sign (a rounded rectangle's section)."""
    return math.copysign(abs(c) ** p, c)


def build_gudgeons(mats):
    m = Mesh("C22_Gudgeons")
    m.seal()
    face = TRANSOM_X + 0.001                                   # 1 mm into the transom: a join overlaps
    lug = 0.028                                                # (the kit's LUG_Z)
    for zg in RD["gudgeons_z"]:
        for dz in (-lug, lug):
            kit_into(m, "Gudgeon", face, 0.0, zg + dz, math.pi, offset=face - RD["pivot_x"])
    return m.finish(mats)


def build_outboard(mats):
    m = Mesh("C22_Outboard")
    m.seal()
    O = KC.K["outboard"]
    st, zb = TRANSOM_X + 0.001, O["bracket_z"]                 # the bracket's plates 1 mm into the transom
    kit_into(m, "OutboardBracket", st, O["y"], zb)
    kit_into(m, "Outboard35", st - 0.17 - 0.12, O["y"], zb + 0.21 - 0.69)
    return m.finish(mats)


def build_all(mats, keel_up=False):
    """Every part. keel_up: the keel raised and the rudder kicked up in place (named C22_Keel and C22_Rudder, so the
    shape loop draws them), the down ones hidden; otherwise the raised ones are built hidden."""
    phi = KC.raise_angle()
    kick = math.radians(RD["blade"]["kick_up_deg"])
    obs = [build_stub(mats), build_gudgeons(mats), build_outboard(mats)]
    if keel_up:
        keel, rud = build_keel(mats, phi), build_rudder(mats, kick)
        hide = [build_keel(mats, 0.0, "C22_KeelDown"), build_rudder(mats, 0.0, "C22_RudderDown")]
    else:
        keel, rud = build_keel(mats), build_rudder(mats)
        hide = [build_keel(mats, phi, "C22_KeelUp"), build_rudder(mats, kick, "C22_RudderUp")]
    for ob in hide:
        ob.hide_render = ob.hide_viewport = True
    return obs + [keel, rud] + hide
