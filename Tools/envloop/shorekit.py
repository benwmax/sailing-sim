"""Environment loop, Tracks F and H (docks, boathouses, yard clutter): the shared modelling helpers.

Builds on the club dock kit's `Part` (Tools/blender/build_docks.py: boxes, tubes, sweeps, lofts, lathes, bolts, export
with box-projected UVs in metres) and adds what shore structures need: whole-board decking, steel pipe pilings,
ribbed metal roofing, lattice and rails, and a way to drop a club kit part (the cleat, the ladder) into a bigger mesh.

Conventions (docs/envloop/docks/README.md): metres, +X out from the bank toward the water, +Y to the left looking out,
Z up, Z = 0 at the lake's 435.5 ft pool. Slots name MI_World_* looks (scripts/import_world.py WORLD_SLOTS); slots not
there yet are listed in NEW_SLOTS and made at integration (Track I).

Run under Blender or the bpy module; nothing here touches Unreal.
"""
import importlib.util
import json
import math
import os
import random

import bpy  # noqa: F401  (first: brings bmesh and mathutils)
import bmesh
from mathutils import Matrix, Vector

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("build_docks", os.path.join(REPO, "Tools", "blender", "build_docks.py"))
club = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(club)
ClubPart = club.Part

# Slots the world import knows today, and the few this track adds (Track I makes their MI_World_* instances).
KNOWN_SLOTS = {"Bark", "Leaves", "Crown", "Rock", "Paint", "Glass", "Tyre", "HeadLight", "TailLight", "Trailer", "Dark", "Steel",
               "Wood", "Lantern", "Reflective", "ContainerPaint", "Trim", "FarWeed", "Reed", "ReedHead", "Door", "Decking", "White",
               "Concrete", "Roof", "Gelcoat", "Antifouling", "TrimGreen", "Deck", "Cushion", "Net", "Barge", "Cargo", "Pilothouse",
               "Funnel", "ShipHull", "Lifeboat", "AviationRed", "Limestone", "StoneGreen", "RoofTile", "Gold", "LampGlow",
               "SafetyRed", "Floats"}
NEW_SLOTS = {
    "MetalRoof": "painted ribbed steel roofing (Galvalume, barn red, forest green, charcoal, tan): per-instance colour",
    "Galv": "hot-dip galvanized steel: dull spangled grey, rougher than Steel (pilings, lift beams, roof framing)",
    "Canvas": "boat covers, umbrellas, cushions' outdoor fabric (Sunbrella-type): per-instance colour",
    "Plastic": "rotomoulded and injection plastic (kayaks, paddleboards, bins, play sets, PWC ports): per-instance colour",
    "Vinyl": "white PVC vinyl (dock bumpers, pool fence, railings)",
    "Carpet": "bunk carpet on lift cradles and trailers (marine carpet, dark grey or blue)",
}


class Part(ClubPart):
    """The club kit's Part plus the shore helpers. `export(out)` writes <out>/<name>.fbx and returns its stats."""

    def __init__(self, name, seed=0):
        super().__init__(name)
        self.rng = random.Random(seed)
        self.sockets = {}

    # -- bits ------------------------------------------------------------------------------------------------------
    def board(self, slot, a, b, w, t, z_top, jitter=0.0):
        """One board from a to b (2D, along its length), w wide, t thick, its top at z_top. jitter: random sag/twist in m."""
        a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
        d = b - a
        L = d.length
        yaw = math.degrees(math.atan2(d.y, d.x))
        c = (a + b) / 2
        dz = self.rng.uniform(-jitter, jitter) if jitter else 0.0
        roll = math.degrees(self.rng.uniform(-jitter, jitter) * 4) if jitter else 0.0
        self.box(slot, (c.x, c.y, z_top - t / 2 + dz), (L / 2, w / 2, t / 2), bevel=min(0.004, t / 4), yaw=yaw, roll=roll, segments=1)

    def decking(self, x0, x1, y0, y1, z_top, across=True, board=0.140, gap=0.006, t=0.025, slot="Decking"):
        """Deck boards over the rectangle [x0,x1] x [y0,y1]: across=True lays them along Y (a walk running along X),
        else along X. Real 5/4x6 boards: 140 mm wide, 25 mm thick, 6 mm gaps."""
        pitch = board + gap
        if across:
            n = max(1, int((x1 - x0 + gap) / pitch))
            for i in range(n):
                x = x0 + board / 2 + i * pitch
                ov = self.rng.uniform(-0.012, 0.012)
                self.board(slot, (x, y0 + ov), (x, y1 + ov), board, t, z_top, jitter=0.003)
        else:
            n = max(1, int((y1 - y0 + gap) / pitch))
            for i in range(n):
                y = y0 + board / 2 + i * pitch
                ov = self.rng.uniform(-0.012, 0.012)
                self.board(slot, (x0 + ov, y), (x1 + ov, y), board, t, z_top, jitter=0.003)

    def frame(self, x0, x1, y0, y1, z_top, along_x=True, joist=0.6, slot="Wood"):
        """The framing under a deck: rim boards (2x8, 38 x 184 mm) round the edge and joists every `joist` m
        under the boards, running at right angles to them."""
        zt = z_top - 0.025
        h, t = 0.184, 0.038
        zc = zt - h / 2
        for y in (y0 + t / 2, y1 - t / 2):
            self.box(slot, ((x0 + x1) / 2, y, zc), ((x1 - x0) / 2, t / 2, h / 2), segments=1)
        for x in (x0 + t / 2, x1 - t / 2):
            self.box(slot, (x, (y0 + y1) / 2, zc), (t / 2, (y1 - y0) / 2 - t, h / 2), segments=1)
        if along_x:
            n = max(1, int(round((y1 - y0) / joist)))
            for i in range(1, n):
                y = y0 + (y1 - y0) * i / n
                self.box(slot, ((x0 + x1) / 2, y, zc), ((x1 - x0) / 2 - t, t / 2, h / 2), segments=1)
        else:
            n = max(1, int(round((x1 - x0) / joist)))
            for i in range(1, n):
                x = x0 + (x1 - x0) * i / n
                self.box(slot, (x, (y0 + y1) / 2, zc), (t / 2, (y1 - y0) / 2 - t, h / 2), segments=1)

    def piling(self, x, y, z_top, r=0.1095, z_bed=-2.6, slot="Galv", cap=True):
        """A steel pipe piling (8 5/8 in OD) from below the bed to z_top, with a domed cap."""
        self.tube(slot, (x, y, z_bed), (x, y, z_top), r, sides=14, caps=not cap)
        if cap:
            self.lathe(slot, (x, y, z_top), [(r * 1.08, 0.0), (r * 1.08, 0.02), (r * 0.7, 0.045), (0.0, 0.055)], sides=14)

    def bent(self, x, ys, z_top, slot="Galv"):
        """A bent: a cross beam under the deck between pilings at (x, ys) - a steel channel (C8) bolted to their sides."""
        y0, y1 = min(ys) - 0.15, max(ys) + 0.15
        z = z_top - 0.025 - 0.184 - 0.1
        self.box(slot, (x + 0.13, (y0 + y1) / 2, z), (0.028, (y1 - y0) / 2, 0.1), segments=1)
        for y in ys:
            self.bolt(slot, (x + 0.16, y, z), d=0.022, h=0.01, axis="X", washer=True)

    def rail(self, pts, z_deck, h=0.95, post_every=1.8, slot="Wood", pickets=True):
        """A wooden guard rail along a polyline: 4x4 posts (89 mm), a 2x6 cap, a bottom rail and 2x2 pickets every
        0.14 m (the 4 in sphere rule)."""
        pts = [Vector((p[0], p[1], 0)) for p in pts]
        for a, b in zip(pts, pts[1:]):
            d = b - a
            L = d.length
            u = d.normalized()
            yaw = math.degrees(math.atan2(u.y, u.x))
            n = max(1, int(math.ceil(L / post_every)))
            for i in range(n + 1):
                p = a + u * (L * i / n)
                self.box(slot, (p.x, p.y, z_deck + h / 2), (0.0445, 0.0445, h / 2), bevel=0.004, yaw=yaw, segments=1)
            c = (a + b) / 2
            self.box(slot, (c.x, c.y, z_deck + h + 0.019), (L / 2 + 0.05, 0.07, 0.019), bevel=0.004, yaw=yaw, segments=1)
            self.box(slot, (c.x, c.y, z_deck + 0.12), (L / 2, 0.019, 0.044), yaw=yaw, segments=1)
            self.box(slot, (c.x, c.y, z_deck + h - 0.06), (L / 2, 0.019, 0.044), yaw=yaw, segments=1)
            if pickets:
                m = int(L / 0.14)
                for i in range(1, m):
                    p = a + u * (L * i / m)
                    self.box(slot, (p.x, p.y, z_deck + 0.12 + (h - 0.18) / 2), (0.019, 0.019, (h - 0.18) / 2), yaw=yaw, segments=1)

    def ribbed_plane(self, slot, p0, p1, p2, p3, rib_dir, pitch=0.305, rib_h=0.032, rib_w=0.03, t=0.012):
        """A metal roof panel field on the quad p0..p3 (p0->p1 along the eave, p0->p3 up the slope): a thin sheet plus a
        raised rib every `pitch` m running up the slope (R-panel major ribs: 12 in, 1 1/4 in high). rib_dir is unused
        but kept for clarity: ribs always run p0->p3."""
        p0, p1, p2, p3 = (Vector(p) for p in (p0, p1, p2, p3))
        along = p1 - p0
        up = p3 - p0
        n = along.cross(up).normalized()
        if n.z < 0:
            n = -n
        bm = self.bm
        vs = [bm.verts.new(p) for p in (p0, p1, p2, p3)]
        vb = [bm.verts.new(p - n * t) for p in (p0, p1, p2, p3)]
        faces = [bm.faces.new(vs), bm.faces.new(list(reversed(vb)))]
        for i in range(4):
            j = (i + 1) % 4
            faces.append(bm.faces.new((vs[i], vb[i], vb[j], vs[j])))
        self._faces(faces, slot)
        L = along.length
        k = int(L / pitch)
        ua = along.normalized()
        for i in range(k + 1):
            a = p0 + ua * min(i * pitch + 0.02, L - 0.02)
            b = a + up
            mid = (a + b) / 2
            # a trapezoid rib as a thin box set on the sheet
            self._rib(slot, a + n * (rib_h / 2), b + n * (rib_h / 2), ua, n, rib_w, rib_h)

    def _rib(self, slot, a, b, side, n, w, h):
        bm = self.bm
        base = [a - side * w, a + side * w, b + side * w, b - side * w]
        top = [p + n * (h / 2) - side * 0 for p in base]
        top = [a - side * w * 0.4 + n * h / 2, a + side * w * 0.4 + n * h / 2, b + side * w * 0.4 + n * h / 2, b - side * w * 0.4 + n * h / 2]
        base = [p - n * h / 2 for p in base]
        vb = [bm.verts.new(p) for p in base]
        vt = [bm.verts.new(p) for p in top]
        faces = [bm.faces.new(vt)]
        for i in range(4):
            j = (i + 1) % 4
            faces.append(bm.faces.new((vb[i], vb[j], vt[j], vt[i])))
        self._faces(faces, slot)

    def gable_roof(self, x0, x1, y0, y1, z_eave, rise, overhang=0.3, slot="MetalRoof", frame_slot="Galv", ridge_along_x=True,
                   purlin=0.6):
        """A gable roof of ribbed metal over [x0,x1] x [y0,y1] (the post line), ridge along X (or Y), eaves `overhang`
        past the posts, with steel purlins, rafters at each end and mid, ridge cap, rake trim and gutter-less drip edge."""
        if not ridge_along_x:
            raise NotImplementedError
        xa, xb = x0 - overhang, x1 + overhang
        ya, yb = y0 - overhang, y1 + overhang
        ym = (y0 + y1) / 2
        half = (yb - ya) / 2
        zr = z_eave + rise
        za = z_eave - overhang * rise / ((y1 - y0) / 2)
        for s in (-1, 1):
            ye = ym + s * half
            p0, p1 = (xa, ye, za), (xb, ye, za)
            p3, p2 = (xa, ym, zr), (xb, ym, zr)
            if s < 0:
                self.ribbed_plane(slot, p0, p1, p2, p3, None)
            else:
                self.ribbed_plane(slot, p1, p0, p3, p2, None)
            # rake trim along both gable ends and the eave drip
            for x in (xa, xb):
                self.sweep(slot, [(x, ye, za - 0.02), (x, ym, zr - 0.02)], [(0.03, 0.06)] * 2, sides=4, up=(1, 0, 0))
            self.box(slot, ((xa + xb) / 2, ye, za - 0.04), ((xb - xa) / 2, 0.02, 0.05), segments=1)
            # purlins under the sheets (Z-purlins as thin boxes), one each `purlin` metres up the slope
            slope = math.hypot(half, zr - za)
            m = max(1, int(slope / purlin))
            for i in range(m + 1):
                f = (i + 0.3) / (m + 0.6)
                y = ye + (ym - ye) * f
                z = za + (zr - za) * f - 0.012 - 0.1
                self.box(frame_slot, ((xa + xb) / 2, y, z), ((xb - xa) / 2 - 0.05, 0.03, 0.1), segments=1)
        # ridge cap
        self.sweep(slot, [(xa, ym, zr + 0.02), (xb, ym, zr + 0.02)], [(0.16, 0.05)] * 2, sides=6, up=(0, 0, 1))
        # rafters (steel tube) at each post line and middle
        for x in (x0, (x0 + x1) / 2, x1):
            for s in (-1, 1):
                y = ym + s * (y1 - y0) / 2
                self.sweep(frame_slot, [(x, y, z_eave - 0.12), (x, ym, zr - 0.25)], [(0.05, 0.1)] * 2, sides=4, up=(0, 0, 1))
            self.box(frame_slot, (x, ym, z_eave - 0.1), (0.05, (y1 - y0) / 2, 0.075), segments=1)   # tie beam
        return zr

    def drop(self, builder, at=(0, 0, 0), yaw=0.0, scale=1.0):
        """Place a club kit part (a build_docks.py function such as club.cleat) into this mesh at `at`, turned `yaw` deg."""
        cap = _capture(builder)
        m = Matrix.Translation(Vector(at)) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Scale(scale, 4)
        me = bpy.data.meshes.new("drop")
        cap.bm.to_mesh(me)
        cap.bm.free()
        me.transform(m)
        n0 = len(self.bm.faces)
        self.bm.from_mesh(me)
        self.bm.faces.ensure_lookup_table()
        for f in self.bm.faces[n0:]:
            f.material_index = self.slot(cap.slots[f.material_index])
        bpy.data.meshes.remove(me)

    def shift(self, dx, dy=0.0, dz=0.0):
        """Move everything built so far (to put a boat's origin at its cradle contact, midships)."""
        bmesh.ops.translate(self.bm, vec=Vector((dx, dy, dz)), verts=self.bm.verts[:])

    def socket(self, name, at, yaw=0.0):
        self.sockets[name] = {"at": [round(v, 3) for v in at], "yaw": round(yaw, 1)}

    def stats(self):
        lo = Vector((1e9, 1e9, 1e9))
        hi = -lo
        for v in self.bm.verts:
            lo = Vector([min(lo[i], v.co[i]) for i in range(3)])
            hi = Vector([max(hi[i], v.co[i]) for i in range(3)])
        tris = sum(len(f.verts) - 2 for f in self.bm.faces)
        return {"tris": tris, "lo": [round(x, 3) for x in lo], "hi": [round(x, 3) for x in hi],
                "size": [round(hi[i] - lo[i], 3) for i in range(3)], "slots": list(self.slots), "sockets": self.sockets}

    def export(self, out):
        st = self.stats()
        super().export(out)
        return st


class _Capture(ClubPart):
    """Stands in for build_docks.Part while a club builder runs: keeps the mesh instead of exporting it."""
    last = None

    def export(self, out):
        _Capture.last = self


def _capture(builder):
    orig = club.Part
    club.Part = _Capture
    club.OUT = None
    try:
        builder()
    finally:
        club.Part = orig
    return _Capture.last


def write_manifest(out, kind, stats):
    path = os.path.join(out, f"{kind}_manifest.json")
    with open(path, "w") as f:
        json.dump(stats, f, indent=1, sort_keys=True)
    return path
