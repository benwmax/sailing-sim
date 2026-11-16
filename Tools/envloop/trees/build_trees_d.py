"""Track D's trees and shrubs, built in Blender from code: V6/T2's skeleton-and-cards trees (Tools/blender/build_trees.py)
remade for the hero band (0 to 30 m), species by species from a region pack (packs/<pack>/pack.json and its cards).

What changes against build_trees.py:
  - The crown's inside. V6 filled each crown with opaque balls (the far crown's blobs at half size, `hollow`) to save the
    alpha-tested overdraw of the cards deep inside; up close they read as solid dark lumps. Here the fill is a masked
    leaf shell: the same blob shapes, broken up, carrying the species' dense "clump" tile of real leaves (slot Leaves,
    vertex alpha 0 = inside), so the gaps between the outer sprays show leaves in shade, not a ball. CORE_MODE "v6"
    keeps the old balls for comparison, "none" drops the fill (and the card culling) altogether.
  - Leaves at true size: cards are the card's `card_m` across and carry the species' spray from make_leaf_atlas_d.py
    (4 x 4 atlas, T_LeafAtlasD); each card is creased down its middle (four triangles) so it isn't one flat plane.
  - A bark per species: the Bark slot is named Bark_<Species>; UVs are in metres (U round the trunk, V along it), so the
    material lays the scan at its real size (the card's `tile_m`).
  - Three models per species: 0 and 1 as before (two seeds), 2 the open-grown / bank form: limbs low on the trunk
    sweeping out, and on the water's-edge species the roots standing out of an eroded bank on the +X side (the side
    the placement turns to the water).
  - Two new species, pecan and honey mesquite, and every species' sizes from its card.
  - Root flare and surface roots on every tree, half buried.
Vertex colours as V6: R = how far out (sway; the leaf material's shade), G = flutter phase, B = per-card tint, A 1 on
cards and bark, 0 on the shell. Units metres. Prints "TreesD: <name> <tris>" per model.

  blender -b --factory-startup -P Tools/envloop/trees/build_trees_d.py -- <out dir> [Species,...] [--pack north-texas-lake]
  (or import it: build(species, variant) -> (object, triangles, info))
"""
import glob
import json
import math
import os
import random
import sys

import bpy  # noqa: I001 (bpy first: the bpy module provides bmesh)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_MODE = "shell"   # "shell" (Track D: loose inner leaf patches), "v6" (opaque balls), "none"
SHELL_SCALE = 0.5     # the inner patches sit on this fraction of each cluster's extent
SHELL_COVER = 1.1     # patch area over the inner ellipsoid's area
PATCH_SCALE = 1.0     # patch size over the clump tile's real span (card_m / 2)
CARD_FILL = 0.85      # outer cards: V6's leaf area per twig point, scaled for the smaller card
ATLAS_COLS = 4


PACKS = os.path.join(HERE, "packs")
PACK = os.environ.get("TREES_PACK", "north-texas-lake")
CARDS, SHAPE, SHRUBS, BANK_SPECIES, PACK_DATA = {}, {}, {}, set(), {}


def load_pack(name):
    """Region packs are data (the shore plan's rule 1): packs/<name>/pack.json names the species, their growth knobs,
    the shrubs, the bank species and the atlas layout; packs/<name>/cards/*.json the real sizes and photo sets. Sets
    the module's tables; every tool takes --pack (default north-texas-lake, or TREES_PACK)."""
    global PACK
    PACK = name
    root = os.path.join(PACKS, name)
    data = json.load(open(os.path.join(root, "pack.json")))
    CARDS.clear()
    for p in sorted(glob.glob(os.path.join(root, data.get("cards", "cards"), "*.json"))):
        c = json.load(open(p))
        CARDS[c["id"]] = c
    SHAPE.clear()
    SHAPE.update({k: {kk: (tuple(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()} for k, v in data["growth"].items()})
    SHRUBS.clear()
    SHRUBS.update({k: (v["card"], {kk: (tuple(vv) if isinstance(vv, list) else vv) for kk, vv in v["growth"].items()}, tuple(v["height_m"]))
                   for k, v in data.get("shrubs", {}).items()})
    BANK_SPECIES.clear()
    BANK_SPECIES.update(data.get("bank_species", []))
    PACK_DATA.clear()
    PACK_DATA.update(data)
    return data


load_pack(PACK)






def tile_uv(tile):
    """Lower-left corner and size of an atlas tile in UV (V up; the atlas's row 0 is the image's top)."""
    col, row = tile % ATLAS_COLS, tile // ATLAS_COLS
    s = 1.0 / ATLAS_COLS
    return col * s, 1.0 - (row + 1) * s, s


def clump_uv(tile):
    """The species' dense clump: quadrant tile % 4 of atlas tile 12 + tile // 4 (column = q % 2, row = q // 2)."""
    u0, v0, s = tile_uv(12 + tile // 4)
    q = tile % 4
    h = s / 2
    return u0 + (q % 2) * h, v0 + (1 - q // 2) * h, h


class Builder:
    def __init__(self, name, height):
        self.bm = bmesh.new()
        self.color = self.bm.loops.layers.color.new("Col")
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.bark_faces, self.leaf_faces, self.shell_faces = [], [], []
        self.leaf_centers = []
        self.height = height
        # The skeleton is grown first and built after: Tree.fit stretches it to the card's crown height and width.
        self.defer = True
        self.fixed = False      # roots: never stretched
        self.pending = []

    def realise(self, warp):
        """Builds the deferred tubes and cards, their positions through warp(Vector) (cards keep their size)."""
        self.defer = False
        for kind, fixed, args in self.pending:
            if kind == "tube":
                points, radii, sides = args
                self.tube([p if fixed else warp(p) for p in points], radii, sides)
            else:
                center, normal, size, tile, phase, tint, sway = args
                self.card(warp(center), normal, size, tile, phase, tint, sway)
        self.pending = []

    def tube(self, points, radii, sides=6, v0=0.0):
        """A tapered tube; UVs in metres: U round the circumference at the ring's radius, V along."""
        if self.defer:
            self.pending.append(("tube", self.fixed, ([p.copy() for p in points], list(radii), sides)))
            return 0.0
        rings = []
        for i, (p, r) in enumerate(zip(points, radii)):
            d = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
            a = d.orthogonal().normalized()
            b = d.cross(a).normalized()
            rings.append([self.bm.verts.new(p + (a * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides)])
        length = v0
        for i in range(len(rings) - 1):
            seg = (points[i + 1] - points[i]).length
            c0, c1 = 2 * math.pi * radii[i], 2 * math.pi * radii[i + 1]
            for k in range(sides):
                k2 = (k + 1) % sides
                f = self.bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
                for loop, (u, v) in zip(f.loops, ((k / sides * c0, length), ((k + 1) / sides * c0, length), ((k + 1) / sides * c1, length + seg),
                                                  (k / sides * c1, length + seg))):
                    loop[self.uv].uv = (u, v)
                    sway = max(0.0, min(1.0, loop.vert.co.z / self.height)) ** 2
                    loop[self.color] = (sway, 0.0, 0.5, 1.0)
                self.bark_faces.append(f)
            length += seg
        return length

    def card(self, center, normal, size, tile, phase, tint, sway, crease=0.18):
        """One leaf card, creased along its middle (the two halves folded back by `crease` of its half-width)."""
        if self.defer:
            self.pending.append(("card", False, (center.copy(), normal.copy(), size, tile, phase, tint, sway)))
            return
        up = Vector((0, 0, 1))
        a = normal.cross(up)
        if a.length < 1e-3:
            a = Vector((1, 0, 0))
        a.normalize()
        b = normal.cross(a).normalized()
        rot = random.uniform(0, 2 * math.pi)
        a, b = a * math.cos(rot) + b * math.sin(rot), b * math.cos(rot) - a * math.sin(rot)
        h = size * 0.5
        fold = -normal * (crease * h)
        # Six corners: the crease runs b-ward through the middle (u = 0.5).
        pts = [(-a - b) * h + fold, (-b) * h, (a - b) * h + fold, (a + b) * h + fold, b * h, (-a + b) * h + fold]
        uvs = [(0, 0), (0.5, 0), (1, 0), (1, 1), (0.5, 1), (0, 1)]
        vs = [self.bm.verts.new(center + p) for p in pts]
        u0, v0, s = tile_uv(tile)
        for quad in ((0, 1, 4, 5), (1, 2, 3, 4)):
            f = self.bm.faces.new([vs[i] for i in quad])
            for loop, i in zip(f.loops, quad):
                loop[self.uv].uv = (u0 + uvs[i][0] * s, v0 + uvs[i][1] * s)
                loop[self.color] = (sway, phase, tint, 1.0)
            self.leaf_faces.append(f)
        self.leaf_centers.append((center.copy(), size))


def bent(start, direction, length, segments, wobble, droop, floor):
    pts = [start.copy()]
    d = direction.normalized()
    p = start.copy()
    for i in range(segments):
        d = (d + Vector((random.uniform(-wobble, wobble), random.uniform(-wobble, wobble), random.uniform(-wobble, wobble) * 0.5 - droop / segments))).normalized()
        p = p + d * (length / segments)
        if p.z < floor:
            p.z = floor + 0.2 * random.random()
            d.z = max(d.z, 0.05)
        pts.append(p.copy())
    return pts


class Tree:
    def __init__(self, cid, variant, seed):
        if cid in SHRUBS:
            card_id, shape, hr = SHRUBS[cid]
            self.card = dict(CARDS[card_id], height_m=list(hr), budget=CARDS["Yaupon"]["budget"])
            if card_id in ("CedarElm", "RedCedar"):    # saplings: a thin young stem
                self.card["trunk_dbh_m"] = [0.06, 0.1]
                self.card["clear_trunk_m"] = [0.8, 1.4] if card_id == "CedarElm" else [0.1, 0.2]
            self.shape = shape
        else:
            self.card = CARDS[cid]
            self.shape = SHAPE[cid]
        self.cid = cid
        self.variant = variant
        random.seed(seed)
        lo, hi = self.card["height_m"]
        self.h = random.uniform(lo, hi)
        self.b = Builder(cid, self.h)
        leaf = self.card["leaf"]
        self.card_m = leaf["card_m"]
        self.tile = self.card["tile"]
        self.floor = 1.2 if cid not in SHRUBS else 0.15
        # Cards per twig point: V6 had 6 x dens 1.5 m cards; keep the crown's leaf area, so scale by (1.5 / card)^2,
        # tempered (smaller cards fill gaps better), and the creased card's slightly smaller face.
        self.cards_per_point = 6 * self.shape.get("dens", 1.0) * (1.5 / self.card_m) ** 1.6 * CARD_FILL
        self.crown_w = self.card["crown_w_over_h"]
        self.clear = 2.0
        self.stretch = (1.0, 1.0)

    # -- limbs and leaves --------------------------------------------------------------------------------------------
    def grow(self, start, direction, length, radius, level, max_level, floor=None):
        sh = self.shape
        floor = self.floor if floor is None else floor
        pts = bent(start, direction, length, 5, sh.get("wobble", 0.25) if level > 0 else 0.08, sh["droop"] * (level + 1) * 0.5, floor)
        radii = [radius * (1.0 - 0.75 * i / (len(pts) - 1)) for i in range(len(pts))]
        if radius > 0.02:
            # Round enough for the hero band: sides by girth, not by level (V6's 8/6/4 left live oak limbs boxy).
            self.b.tube(pts, radii, sides=12 if radius > 0.25 else (8 if radius > 0.12 else (6 if radius > 0.05 else 4)))
        if level >= max_level:
            self.leaves_along(pts)
            return
        children = random.randint(3, 5) if level > 0 else 0
        for _ in range(children):
            t = random.uniform(0.45, 1.0)
            at = pts[min(len(pts) - 1, int(t * (len(pts) - 1)))]
            d = (pts[-1] - pts[0]).normalized()
            side = d.orthogonal().normalized()
            side.rotate(Matrix.Rotation(random.uniform(0, 2 * math.pi), 3, d))
            nd = (d * 0.6 + side * random.uniform(0.5, 0.9) + Vector((0, 0, random.uniform(-0.1, 0.4)))).normalized()
            self.grow(at, nd, length * random.uniform(0.45, 0.7), radius * 0.55, level + 1, max_level, floor)
        if level < max_level:
            self.grow(pts[-1], (pts[-1] - pts[-2]).normalized(), length * 0.6, radii[-1] * 1.1, level + 1, max_level, floor)

    def leaves_along(self, pts):
        spread = self.card_m * 0.42
        for i in range(2, len(pts)):
            n = int(self.cards_per_point + random.random())
            for _ in range(n):
                c = pts[i] + Vector((random.gauss(0, 1.0), random.gauss(0, 1.0), random.gauss(0, 0.75))) * spread
                out = (c - Vector((0, 0, c.z * 0.6))).normalized() if c.xy.length > 0.1 else Vector((0, 0, 1))
                normal = (out + Vector((random.gauss(0, 0.6), random.gauss(0, 0.6), random.uniform(0.2, 1.0)))).normalized()
                sway = min(1.0, 0.25 + 0.75 * (c.xy.length / (0.5 * self.crown_w * self.h + 1e-3)))
                self.b.card(c, normal, self.card_m * random.uniform(0.85, 1.2), self.tile, random.random(), random.random(), sway)

    # -- trunks ------------------------------------------------------------------------------------------------------
    def trunk_radius(self):
        lo, hi = self.card["trunk_dbh_m"]
        return 0.5 * random.uniform(lo, hi)

    def broad(self):
        h = self.h
        r = self.trunk_radius()
        clear = random.uniform(*self.card["clear_trunk_m"])
        self.clear = clear
        trunk = bent(Vector((0, 0, -0.3)), Vector((0, 0, 1)), clear + 0.3, 4, 0.06, 0.0, -1)
        self.b.tube(trunk, [r * (1.15 - 0.3 * i / (len(trunk) - 1)) for i in range(len(trunk))], sides=12)
        self.roots(Vector((0, 0, 0)), r)
        top = trunk[-1]
        n = random.randint(*self.shape["limbs"])
        reach = 0.5 * self.crown_w * h
        for k in range(n):
            az = 2 * math.pi * (k + random.uniform(-0.3, 0.3)) / n
            rise = math.radians(random.uniform(*self.shape["rise"]))
            d = Vector((math.cos(az) * math.cos(rise), math.sin(az) * math.cos(rise), math.sin(rise)))
            length = math.hypot(reach, h - clear) * random.uniform(0.55, 0.75)
            self.grow(top + Vector((0, 0, random.uniform(-0.4, 0.4))), d, length, r * 0.6, 1, self.shape["levels"])
        if self.variant == 2:
            self.low_limbs(trunk, r, reach)

    def stemmed(self):
        h = self.h
        sh = self.shape
        lean = math.radians(sh["lean"])
        count = random.randint(*sh["stems"])
        r_all = self.trunk_radius()
        r = r_all / math.sqrt(count)
        limbs = random.randint(*sh["limbs"])
        reach = 0.5 * self.crown_w * h
        clear = random.uniform(*self.card["clear_trunk_m"])
        self.clear = clear
        trunks = []
        for s in range(count):
            az = 2 * math.pi * (s + random.uniform(-0.3, 0.3)) / count
            tilt = math.radians(random.uniform(*sh["splay"]))
            d = Vector((math.cos(az) * math.sin(tilt) + math.sin(lean), math.sin(az) * math.sin(tilt), math.cos(tilt) * math.cos(lean))).normalized()
            length = clear * random.uniform(0.8, 1.1) + 0.3
            base = Vector((random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15), -0.3))
            trunk = bent(base, d, length, 4, 0.08 if self.cid != "Mesquite" else 0.22, 0.0, -1)
            self.b.tube(trunk, [r * (1.15 - 0.3 * i / (len(trunk) - 1)) for i in range(len(trunk))], sides=10 if r > 0.12 else 6)
            trunks.append(trunk)
            top = trunk[-1]
            n = limbs if count == 1 else max(2, round(limbs * 1.1 / count) + random.randint(0, 1))
            for k in range(n):
                a = 2 * math.pi * (k + random.uniform(-0.3, 0.3)) / n
                rise = math.radians(random.uniform(*sh["rise"]))
                ld = Vector((math.cos(a) * math.cos(rise), math.sin(a) * math.cos(rise), math.sin(rise)))
                ld = (ld + d * 0.5).normalized()
                ll = math.hypot(reach, max(1.0, h - top.z)) * random.uniform(0.55, 0.75)
                self.grow(top, ld, ll, r * 0.6, 1, sh["levels"])
        if r_all > 0.1:
            self.roots(Vector((0, 0, 0)), r_all * 0.8)
        if self.variant == 2 and trunks:
            self.low_limbs(trunks[0], r, reach)

    def cone(self):
        h = self.h
        leader = bent(Vector((0, 0, -0.3)), Vector((0, 0, 1)), h, 8, 0.03, 0.0, -1)
        r = self.trunk_radius()
        self.b.tube(leader, [r * (1.0 - 0.9 * i / (len(leader) - 1)) for i in range(len(leader))], sides=10)
        self.roots(Vector((0, 0, 0)), r)
        base_r = self.crown_w * h * 0.5
        # A cone of sprays; the open-grown form (variant 2) keeps its skirt to the ground.
        z0 = 0.15 if self.variant == 2 else random.uniform(*self.card["clear_trunk_m"])
        self.clear = z0
        count = int(1100 * self.shape["dens"] * (1.15 / self.card_m) ** 1.6 * 0.55)
        for _ in range(count):
            z = random.uniform(z0, h * 0.98)
            rr = base_r * (1.0 - z / h) ** 0.85 * random.uniform(0.35, 1.08) + 0.15
            az = random.uniform(0, 2 * math.pi)
            c = Vector((math.cos(az) * rr, math.sin(az) * rr, z))
            normal = Vector((math.cos(az), math.sin(az), random.uniform(-0.2, 0.6))).normalized()
            self.b.card(c, normal, self.card_m * random.uniform(0.7, 1.2) * (0.7 + 0.3 * (1 - z / h)), self.tile, random.random(), random.random(), min(1.0, z / h))

    def low_limbs(self, trunk, r, reach):
        """Open-grown form: one to three limbs off the trunk below the crown, rising gently then sweeping out (their floor
        1.5 m, 0.9 m over the water for the bank species), carrying leaves like the rest."""
        for k in range(random.randint(1, 3)):
            t = random.uniform(0.5, 0.9)
            at = trunk[min(len(trunk) - 1, int(t * (len(trunk) - 1)))]
            bank = self.cid in BANK_SPECIES
            az = random.uniform(-0.8, 0.8) if bank else random.uniform(0, 2 * math.pi)   # bank trees: out over the water (+X)
            d = Vector((math.cos(az), math.sin(az), random.uniform(0.15, 0.45))).normalized()
            self.grow(at, d, reach * random.uniform(0.7, 0.95), r * 0.45, 1, self.shape.get("levels", 3), floor=0.9 if bank else 1.5)

    def roots(self, base, r):
        """Root flare and surface roots: five to eight tapering roots running out and down from the trunk's foot, half
        in the ground. The bank form (variant 2 of the water's-edge species) has them standing out of a cut bank on the
        +X side: out over the edge, then down 0.6 to 1.1 m to where the water has washed the clay away."""
        n = random.randint(5, 8)
        bank = self.variant == 2 and self.cid in BANK_SPECIES
        self.b.fixed = True
        for k in range(n):
            az = 2 * math.pi * (k + random.uniform(-0.35, 0.35)) / n
            d = Vector((math.cos(az), math.sin(az), 0.0))
            p0 = base + d * r * 0.7 + Vector((0, 0, 0.35))
            out_len = random.uniform(1.0, 2.2) * (1.0 + r)
            pts = [p0]
            drop = 0.0
            water_side = bank and math.cos(az) > 0.2
            if water_side:
                drop = random.uniform(0.6, 1.1)
            for i in range(1, 7):
                t = i / 6
                p = p0 + d * out_len * t + Vector((random.uniform(-0.08, 0.08), random.uniform(-0.08, 0.08), 0))
                if water_side:
                    # Over the edge at about a metre out, then down the cut face, a little ragged.
                    edge = 0.45
                    p.z = 0.35 - 0.38 * min(t, edge) / edge - (0 if t < edge else drop * ((t - edge) / (1 - edge)) ** 0.8)
                else:
                    p.z = 0.35 - 0.5 * t ** 0.7   # into the ground
                pts.append(p)
            radii = [r * 0.38 * (1.0 - 0.85 * i / 6) for i in range(7)]
            self.b.tube(pts, radii, sides=6 if r > 0.15 else 5)
        self.b.fixed = False

    def fit(self):
        """Stretches the grown skeleton so the crown matches the card: top at the tree's height, width crown_w x h
        (95th percentile of the cards' reach, both sides). Above the clear trunk height z0 the crown scales up from z0;
        sideways the stretch ramps in from the ground to z0. Cards keep their size, roots their place."""
        cards = [a[0] for k, _, a in self.b.pending if k == "card"]
        if not cards:
            self.b.realise(lambda p: p)
            return 1.0, 1.0
        z0 = min(self.clear, self.h * 0.6)
        top = max(c.z for c in cards)
        reach = sorted(c.xy.length for c in cards)[int(0.95 * (len(cards) - 1))]
        want_top = self.h - 0.3 * self.card_m
        sz = max(0.5, min(2.0, (want_top - z0) / max(0.5, top - z0)))
        sxy = max(0.5, min(2.0, 0.5 * self.crown_w * self.h / max(0.5, reach)))

        # The squeeze packs the cards closer: thin them back to the grown crown's density (by volume), then to the card's
        # triangle budget (outer cards get 60 % of it, four triangles each).
        keep = min(1.0, (sxy * sxy * sz) ** 0.6)
        cap = int(self.card.get("budget", {}).get("near_tris_max", 26000) * 0.6 / 4)
        idx = [i for i, (k, _, _) in enumerate(self.b.pending) if k == "card"]
        n_keep = min(cap, int(len(idx) * keep))
        if n_keep < len(idx):
            rng = random.Random(len(idx))
            gone = set(rng.sample(idx, len(idx) - n_keep))
            self.b.pending = [e for i, e in enumerate(self.b.pending) if i not in gone]

        def warp(p):
            t = max(0.0, min(1.0, p.z / max(0.1, z0)))
            k = 1.0 + (sxy - 1.0) * t
            z = p.z if p.z <= z0 else z0 + (p.z - z0) * sz
            return Vector((p.x * k, p.y * k, z))
        self.b.realise(warp)
        return sxy, sz

    # -- crown fill --------------------------------------------------------------------------------------------------
    def blobs(self):
        """The crown's clusters (V6's far_version k-means over the card centres)."""
        pts = [c for c, _ in self.b.leaf_centers]
        if len(pts) < 8:
            return []
        rng = random.Random(len(pts))
        k = min(14, max(4, len(pts) // 120))
        centers = rng.sample(pts, k)
        groups = []
        for _ in range(6):
            groups = [[] for _ in range(k)]
            for p in pts:
                groups[min(range(k), key=lambda i: (p - centers[i]).length_squared)].append(p)
            centers = [sum(g, Vector()) / len(g) if g else centers[i] for i, g in enumerate(groups)]
        out = []
        for c, g in zip(centers, groups):
            if g:
                ext = Vector((max(abs(p.x - c.x) for p in g), max(abs(p.y - c.y) for p in g), max(abs(p.z - c.z) for p in g)))
                out.append((c.copy(), ext))
        return out

    def fill(self, blobs):
        """Drops the cards deep inside the clusters (they are hidden yet cost overdraw), then fills the inside:
        "v6": opaque balls (slot Crown, vertex alpha 0) at 50/50/45 % of each cluster, as on main;
        "shell": loose quads of the species' clump tile scattered over each cluster's inner ellipsoid (slot Leaves,
        vertex alpha 0, shade R 0.1): no closed surface, so nothing inside has an outline of its own."""
        if CORE_MODE == "none" or not blobs:
            return 0
        drop = []
        keep = []
        for i, (c, _) in enumerate(self.b.leaf_centers):
            d = min(((c.x - bc.x) / max(e.x, 0.3)) ** 2 + ((c.y - bc.y) / max(e.y, 0.3)) ** 2 + ((c.z - bc.z) / max(e.z, 0.3)) ** 2 for bc, e in blobs) ** 0.5
            (drop if d < 0.58 and random.random() < 0.8 else keep).append(i)
        dead = set()
        for i in drop:
            dead.update(self.b.leaf_faces[2 * i: 2 * i + 2])
        self.b.leaf_faces = [f for f in self.b.leaf_faces if f not in dead]
        bmesh.ops.delete(self.b.bm, geom=list(dead), context="FACES")
        if CORE_MODE == "v6":
            for k, (c, ext) in enumerate(blobs):
                ret = bmesh.ops.create_icosphere(self.b.bm, subdivisions=2, radius=1.0)
                for v in ret["verts"]:
                    n = v.co.normalized()
                    bump = 1.0 + 0.15 * math.sin(n.x * 7.1 + k) * math.sin(n.y * 6.3 + 1.7 * k)
                    v.co = c + Vector((n.x * ext.x * 0.5, n.y * ext.y * 0.5, n.z * ext.z * 0.45)) * bump
                for f in {f for v in ret["verts"] for f in v.link_faces}:
                    f.smooth = True
                    for loop in f.loops:
                        loop[self.b.color] = (min(1.0, loop.vert.co.z / self.h) ** 2, random.random(), 0.2 * random.random(), 0.0)
                        loop[self.b.uv].uv = (loop.vert.co.x * 0.1, loop.vert.co.z * 0.1)
                    self.b.shell_faces.append(f)
            return len(drop)
        # Track D: no closed surface at all. Loose patches of the clump tile scattered over each cluster's inner
        # ellipsoid (SHELL_SCALE of it), each facing out with a wide random tilt, so nothing inside has an outline of
        # its own: through a gap in the sprays you see more leaves, in shade.
        u0, v0, s = clump_uv(self.tile)
        size = self.card_m * 0.5 * PATCH_SCALE      # the clump tile spans card_m / 2 at the spray's scale
        for c, ext in blobs:
            ax, ay, az = (max(0.3, e) * SHELL_SCALE for e in ext)
            # Ellipsoid area (Knud Thomsen) over the patch's, times the cover wanted.
            p = 1.6075
            area = 4 * math.pi * (((ax * ay) ** p + (ax * az) ** p + (ay * az) ** p) / 3) ** (1 / p)
            n = max(3, int(area / (size * size) * SHELL_COVER))
            for _ in range(n):
                d = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
                pos = c + Vector((d.x * ax, d.y * ay, d.z * az)) * random.uniform(0.75, 1.0)
                normal = (d + Vector((random.gauss(0, 0.7), random.gauss(0, 0.7), random.gauss(0, 0.7)))).normalized()
                a = normal.orthogonal().normalized()
                a.rotate(Matrix.Rotation(random.uniform(0, 2 * math.pi), 3, normal))
                b = normal.cross(a).normalized()
                h = size * random.uniform(0.8, 1.1) * 0.5
                vs = [self.b.bm.verts.new(pos + (x * a + y * b) * h) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                f = self.b.bm.faces.new(vs)
                for loop, (x, y) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                    loop[self.b.uv].uv = (u0 + (0.01 + 0.98 * x) * s, v0 + (0.01 + 0.98 * y) * s)
                    loop[self.b.color] = (0.1, random.random(), random.random(), 0.0)
                self.b.shell_faces.append(f)
        return len(drop)


def far_version(t, blobs, name):
    """The mid band's opaque crown (V6's far_version): the trunk and one lumpy ball per cluster, slots Bark_<Species>
    and Crown, so the far bands keep working unchanged with the new shapes."""
    random.seed(len(blobs) + 7)
    far = Builder(name, t.h)
    far.defer = False
    trunk_top = Vector((0, 0, max(1.5, min(t.clear + 0.5, t.h * 0.4))))
    far.tube([Vector((0, 0, -0.3)), trunk_top], [0.25 + t.h * 0.02, 0.18 + t.h * 0.015], sides=6)
    for k, (c, ext) in enumerate(blobs):
        ret = bmesh.ops.create_icosphere(far.bm, subdivisions=2, radius=1.0)
        for v in ret["verts"]:
            n = v.co.normalized()
            bump = 1.0 + 0.18 * math.sin(n.x * 7.1 + k) * math.sin(n.y * 6.3 + 1.7 * k) + 0.1 * random.uniform(-1, 1)
            v.co = c + Vector((n.x * ext.x * 0.85, n.y * ext.y * 0.85, n.z * ext.z * 0.75)) * bump
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.smooth = True
            for loop in f.loops:
                loop[far.color] = (min(1.0, loop.vert.co.z / t.h) ** 2, random.random(), random.random(), 1.0)
                loop[far.uv].uv = (loop.vert.co.x * 0.1, loop.vert.co.z * 0.1)
            far.leaf_faces.append(f)
    mesh = bpy.data.meshes.new(name)
    mesh.materials.append(bpy.data.materials.new(f"Bark_{t.cid}"))
    mesh.materials.append(bpy.data.materials.new("Crown"))
    for f in far.bark_faces:
        f.material_index = 0
    for f in far.leaf_faces:
        f.material_index = 1
    far.bm.normal_update()
    far.bm.to_mesh(mesh)
    far.bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj, sum(len(p.vertices) - 2 for p in mesh.polygons)


def build_tree(cid, variant):
    seed = sum(ord(ch) for ch in cid) * 31 + variant * 7919 + 17
    t = Tree(cid, variant, seed)
    {"cone": t.cone, "stemmed": t.stemmed}.get(t.shape["kind"], t.broad)()
    t.stretch = t.fit()
    blobs = t.blobs()
    dropped = t.fill(blobs)
    return t, blobs, dropped


def finish(t, name):
    b = t.b
    mesh = bpy.data.meshes.new(name)
    bark = bpy.data.materials.new(f"Bark_{t.cid}")
    leaves = bpy.data.materials.new("Leaves")
    mesh.materials.append(bark)
    mesh.materials.append(leaves)
    for f in b.bark_faces:
        f.material_index = 0
    for f in b.leaf_faces:
        f.material_index = 1
    if b.shell_faces:
        if CORE_MODE == "v6":
            mesh.materials.append(bpy.data.materials.new("Crown"))
            for f in b.shell_faces:
                f.material_index = 2
        else:
            for f in b.shell_faces:
                f.material_index = 1
    b.bm.normal_update()
    b.bm.to_mesh(mesh)
    b.bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    return obj, tris


def bark_set(cid, repo):
    c = card_of(cid) if cid in SHRUBS else CARDS[cid]
    if "bark" not in c:      # the shrub cards: the elm's bark, darker
        c = dict(CARDS["CedarElm"]["bark"] and CARDS["CedarElm"], bark=dict(CARDS["CedarElm"]["bark"], tint=[0.5, 0.47, 0.44]))
    bk = c["bark"]
    source, asset = bk["set"].split("/", 1)
    root = os.path.join(repo, "Inputs", "trees", source, asset)
    if source == "ambientcg":
        base = os.path.join(root, f"{asset}_1K-JPG_")
        maps = dict(color=base + "Color.jpg", normal=base + "NormalGL.jpg", rough=base + "Roughness.jpg")
    else:
        maps = dict(color=os.path.join(root, f"{asset}_diff_1k.jpg"), normal=os.path.join(root, f"{asset}_nor_gl_1k.jpg"),
                    rough=os.path.join(root, f"{asset}_rough_1k.jpg"))
    tu, tv = bk["tile_m"]
    return dict(maps, uv=(1.0 / tu, 1.0 / tv), tint=tuple(bk["tint"]), normal_dx=False)


def card_of(cid):
    return CARDS[SHRUBS[cid][0]] if cid in SHRUBS else CARDS[cid]


def build(cid, variant, far=False):
    t, blobs, dropped = build_tree(cid, variant)
    name = f"SM_{cid}" if cid in SHRUBS else f"SM_{cid}_{variant}"
    obj, tris = finish(t, name)
    if far:
        fobj, ftris = far_version(t, blobs, f"{name}_Far")
        return obj, tris, dict(far=fobj, far_tris=ftris, dropped=dropped, blobs=len(blobs), height=t.h, stretch=t.stretch)
    repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
    return obj, tris, dict(bark=bark_set(cid, repo), dropped=dropped, blobs=len(blobs), height=t.h, stretch=t.stretch)


def export(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="X",
                             axis_up="Z", mesh_smooth_type="FACE", use_mesh_modifiers=True, bake_space_transform=True, add_leaf_bones=False,
                             colors_type="LINEAR")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if "--pack" in args:
        k = args.index("--pack")
        load_pack(args[k + 1])
        del args[k:k + 2]
    out = args[0]
    only = set(args[1].split(",")) if len(args) > 1 else None
    os.makedirs(out, exist_ok=True)
    report = {}
    for cid in list(SHAPE) + list(SHRUBS):
        if only and cid not in only:
            continue
        for variant in (range(3) if cid in SHAPE else range(1)):
            obj, tris, info = build(cid, variant, far=cid in SHAPE)
            export(obj, os.path.join(out, obj.name + ".fbx"))
            if "far" in info:
                export(info["far"], os.path.join(out, info["far"].name + ".fbx"))
                print(f"TreesD: {info['far'].name} {info['far_tris']}")
                bpy.data.objects.remove(info["far"])
            print(f"TreesD: {obj.name} {tris} (dropped {info['dropped']} inner cards, {info['blobs']} clusters, {info['height']:.1f} m, stretch {info['stretch'][0]:.2f} x {info['stretch'][1]:.2f})")
            report[obj.name] = dict(tris=tris, far_tris=info.get("far_tris"), height=round(info["height"], 2), stretch=[round(x, 2) for x in info["stretch"]])
            bpy.data.objects.remove(obj)
    json.dump(report, open(os.path.join(out, "trees_d.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
