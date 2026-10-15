"""Ropes and cloth that behave like rope and cloth in the stills: lines hang under their own weight, slack lines drape
over the deck and cabin and round the mast, loaded lines run nearly straight; sails carry the wrinkles real
sailcloth makes (tension lines fanning from the clew and tack, scallops between jib hanks, a leech that flutters,
the soft crinkle of used Dacron).

In the game none of this is baked: the running and standing rigging stay live rope lines (FRigLine in
BoatModelVisuals.cpp, sag from load) and the sails stay the cloth simulation (FSailCloth), so the hero model gives
them sockets and textures rather than frozen shapes. See README.md, "Ropes and sails in the game".
"""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


class Drape:
    """Position-based rope: a chain of points with fixed segment length under gravity, pinned where the line runs
    through a fitting, pushed out of the deck, cabin, cockpit, hull and mast."""

    def __init__(self, colliders):
        self.trees = []
        self.posts = []
        self.add(*colliders)

    def add(self, *colliders):
        dg = bpy.context.evaluated_depsgraph_get()
        for ob in colliders:
            if ob is None:
                continue
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ob.matrix_world
            verts = [mw @ v.co for v in me.vertices]
            polys = [tuple(p.vertices) for p in me.polygons]
            ev.to_mesh_clear()
            if polys:
                self.trees.append(BVHTree.FromPolygons(verts, polys))

    def _collide(self, p, r):
        """Height-field contact: a rope rests on the top-most surface below it (deck, cabin top, cockpit, seats), so
        the test does not depend on which way the shell's normals face. Posts (the mast) push out sideways."""
        top = None
        for t in self.trees:
            hit = t.ray_cast(Vector((p.x, p.y, p.z + 3.0)), Vector((0, 0, -1)), 3.0 + 0.5)
            if hit[0] is not None and (top is None or hit[0].z > top):
                top = hit[0].z
        if top is not None and p.z < top + r and p.z > top - 0.25:
            p = Vector((p.x, p.y, top + r))
        for (cx, cy, z0, z1, rad) in self.posts:
            if z0 < p.z < z1:
                d = Vector((p.x - cx, p.y - cy, 0))
                if d.length < rad + r:
                    d = d.normalized() if d.length > 1e-6 else Vector((1, 0, 0))
                    p = Vector((cx, cy, p.z)) + d * (rad + r) + Vector((0, 0, p.z)) * 0
                    p.z = p.z
        return p

    def post(self, cx, cy, z0, z1, rad):
        self.posts.append((cx, cy, z0, z1, rad))

    def span(self, a, b, slack, r, n=None, iters=500, sideways=Vector((0, 0, 0))):
        """A line from a to b whose length is the straight distance times (1 + slack). Returns the points."""
        a, b = Vector(a), Vector(b)
        L = (b - a).length * (1 + slack)
        n = n or max(8, min(64, int(L / 0.04)))
        seg = L / n
        # start from a parabola below the chord so the solver converges quickly
        sag = math.sqrt(max(3 * slack / 8, 0)) * (b - a).length
        pts = [a.lerp(b, i / n) - Vector((0, 0, sag * 4 * (i / n) * (1 - i / n))) + sideways * 4 * (i / n) * (1 - i / n)
               for i in range(n + 1)]
        prev = [p.copy() for p in pts]
        g = Vector((0, 0, -9.81)) * (1 / 240) ** 2
        for it in range(iters):
            for i in range(1, n):
                v = (pts[i] - prev[i]) * 0.96
                prev[i] = pts[i].copy()
                pts[i] = pts[i] + v + g
            for _ in range(6):
                for i in range(n):
                    d = pts[i + 1] - pts[i]
                    ln = d.length or 1e-9
                    corr = d * ((ln - seg) / ln)
                    wa = 0.0 if i == 0 else (1.0 if i + 1 == n else 0.5)
                    wb = 0.0 if i + 1 == n else (1.0 if i == 0 else 0.5)
                    pts[i] += corr * wa
                    pts[i + 1] -= corr * wb
            if it % 4 == 0 or it > iters - 20:
                for i in range(1, n):
                    pts[i] = self._collide(pts[i], r * 1.15)
        pts[0], pts[-1] = a, b
        return pts

    def line(self, waypoints, slacks, r):
        """A line through fittings: waypoints are where it is held (a block, a cam, a fairlead), slacks per span."""
        out = []
        for k in range(len(waypoints) - 1):
            s = slacks[k] if isinstance(slacks, (list, tuple)) else slacks
            p = self.span(waypoints[k], waypoints[k + 1], s, r)
            out += p if not out else p[1:]
        return [tuple(v) for v in out]


def _hash(i, j, seed):
    h = math.sin(i * 127.1 + j * 311.7 + seed * 74.7) * 43758.5453
    return h - math.floor(h)


def _vnoise(x, y, seed):
    """Smooth value noise, enough for cloth crinkle."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a, b = _hash(xi, yi, seed), _hash(xi + 1, yi, seed)
    c, d = _hash(xi, yi + 1, seed), _hash(xi + 1, yi + 1, seed)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v - 0.5


class Wrinkles:
    """Normal offsets (metres) over a sail's (h, u) surface: h up the luff 0..1, u along the chord 0..1."""

    def __init__(self, luff_len, foot_len, age, seed, hanks=0, battens=(), loose=0.0):
        self.L, self.F, self.age, self.seed = luff_len, foot_len, age, seed
        self.hanks, self.battens, self.loose = hanks, battens, loose

    def __call__(self, h, u, chord_m):
        off = 0.0
        x, y = u * chord_m, h * self.L                # metres along the chord and up the luff
        # clew: tension lines fan out from the clew toward the luff; strongest close in, fading by a metre or two
        cx, cy = self.F, 0.0
        dx, dy = x - cx, y - cy
        rr = math.hypot(dx, dy)
        if rr > 0.02:
            ang = math.atan2(dy, -dx)
            fan = math.sin(ang * 22 + 0.6 * math.sin(rr * 3)) * math.exp(-rr / 0.9) * min(rr / 0.08, 1.0)
            off += (0.004 + 0.003 * self.loose) * fan
        # tack: a smaller fan
        rr = math.hypot(x, y)
        if rr > 0.02:
            ang = math.atan2(y, x)
            off += 0.0025 * math.sin(ang * 16) * math.exp(-rr / 0.45) * min(rr / 0.05, 1.0)
        # head: the headboard or head ring pulls short creases down the luff
        rr = math.hypot(x, self.L - y)
        off += 0.002 * math.sin(math.atan2(self.L - y, x + 0.01) * 14) * math.exp(-rr / 0.35)
        # jib hanks: the luff scallops between hanks, the cloth pulling aft from each one
        if self.hanks:
            t = h * (self.hanks + 1)
            scallop = math.sin(math.pi * (t - math.floor(t)))
            off += 0.010 * scallop * math.exp(-u * chord_m / 0.10)
        # batten pockets stiffen the leech; between them the leech flutters a little
        lee = max(0.0, (u - 0.88) / 0.12)
        if lee > 0:
            near = min([abs(h - b) for b in self.battens] or [1.0])
            off += 0.004 * lee * lee * math.sin(h * 70 + self.seed) * min(near / 0.05, 1.0)
        # used Dacron: soft crinkle that grows with age
        off += 0.0012 * (0.3 + self.age) * (_vnoise(x * 6, y * 6, self.seed) + 0.5 * _vnoise(x * 15, y * 15, self.seed + 1))
        return off
