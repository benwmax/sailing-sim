"""Track B (shore plan, docs/envloop/grass/README.md): the grass and ground-plant shapes, as plain Python (no bpy), so
the builder, the size check and the tests share one source.

Every plant is a `Plant`: vertices (metres, Z up, origin at the plant's foot), triangles, a per-vertex normal, colour
and UV, and a slot per triangle. The vertex colour carries what the grass material and its wind need:
  R  height fraction: 0 at the ground, 1 at the plant's top (wind sway grows with it, the root darkens below it)
  G  a random number per blade (hue, length and sway phase variation)
  B  part: 0 leaf, 0.5 stem or stalk, 1 seed head or flower
  A  1 on a cut (mown) blade tip, else 0
UV0: U across the blade 0..1 (midrib at 0.5), V along it 0..1 (the material's root-to-tip blend).
Normals lean halfway from the blade's face toward up (the usual grass trick: a thin blade lit from its back side
reads black otherwise); the material is two-sided, so every blade is one surface, not two.
"""
import math
import random

UP = (0.0, 0.0, 1.0)


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


SLOTS = ("Grass", "GrassSeed")   # leaf and stem in Grass, seed heads and flowers in GrassSeed (separate translucency)


class Plant:
    def __init__(self, name):
        self.name = name
        self.v, self.n, self.c, self.uv, self.tris, self.slot = [], [], [], [], [], []
        self.blades = []   # (kind, length, width) per blade, for the size check

    def vert(self, p, n, rnd, part, u, v, cut=0.0):
        self.v.append(p)
        self.n.append(n)
        self.c.append([0.0, rnd, part, cut])
        self.uv.append((u, v))
        return len(self.v) - 1

    def tri(self, a, b, c, slot=0):
        self.tris.append((a, b, c))
        self.slot.append(slot)

    def finish(self):
        """Height fraction into R, once the plant is whole."""
        top = max((p[2] for p in self.v), default=1.0) or 1.0
        for p, col in zip(self.v, self.c):
            col[0] = max(0.0, min(1.0, p[2] / top))
        return self

    def merge(self, other, offset=(0.0, 0.0, 0.0)):
        base = len(self.v)
        for p, n, c, uv in zip(other.v, other.n, other.c, other.uv):
            self.v.append(_add(p, offset))
            self.n.append(n)
            self.c.append(list(c))
            self.uv.append(uv)
        for t, s in zip(other.tris, other.slot):
            self.tris.append((t[0] + base, t[1] + base, t[2] + base))
            self.slot.append(s)
        self.blades += other.blades

    @property
    def tri_count(self):
        return len(self.tris)

    def bounds(self):
        xs, ys, zs = zip(*self.v)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def blade(pl, base, yaw, length, width, tilt, droop, rnd, segs=3, part=0.0, slot=0, taper=0.8, fold=0.0,
          cut=False, profile=None, normal_up=0.5):
    """One leaf blade or a flat stalk: a ribbon of `length` metres along a curve that leaves the ground `tilt` radians
    from vertical, toward `yaw`, and bends further over by `droop` radians by its tip (gravity: most of the bend in the
    outer half). `width` is the full width at the base, tapering to a point (`taper` 1) or a square cut (`cut`).
    `fold` raises a midrib row by that share of the half-width (a V-section blade: its two halves catch the light
    differently, the "solid" look up close; costs twice the triangles). `profile(t)` overrides the width shape.
    Returns the tip point."""
    d = (math.cos(yaw), math.sin(yaw), 0.0)
    side = (-d[1], d[0], 0.0)
    step = length / segs
    p = base
    centres, tangents = [base], []
    for i in range(segs):
        t = (i + 0.5) / segs
        a = tilt + droop * t * t
        tan = (d[0] * math.sin(a), d[1] * math.sin(a), math.cos(a))
        tangents.append(tan)
        p = _add(p, _mul(tan, step))
        centres.append(p)
    tangents.append(tangents[-1])
    rows = []
    for i, c in enumerate(centres):
        t = i / segs
        if profile:
            w = width * 0.5 * profile(t)
        elif cut:
            w = width * 0.5 * (1.0 - 0.15 * t)
        else:
            w = width * 0.5 * max(0.0, 1.0 - t) ** taper if i < segs else 0.0
        face = _norm(_cross(side, tangents[i]))          # the blade's face normal (toward the outside of its bend)
        n = _norm(_add(_mul(face, 1.0 - normal_up), _mul(UP, normal_up)))
        mid = _add(c, _mul(face, fold * w)) if fold else None
        left = pl.vert(_sub(c, _mul(side, w)), n, rnd, part, 0.0, t, 1.0 if (cut and i == segs) else 0.0)
        right = pl.vert(_add(c, _mul(side, w)), n, rnd, part, 1.0, t, 1.0 if (cut and i == segs) else 0.0)
        m = pl.vert(mid, n, rnd, part, 0.5, t, 1.0 if (cut and i == segs) else 0.0) if fold else None
        rows.append((left, m, right, w))
    for (l0, m0, r0, w0), (l1, m1, r1, w1) in zip(rows, rows[1:]):
        if fold:
            for a0, b0, a1, b1 in ((l0, m0, l1, m1), (m0, r0, m1, r1)):
                pl.tri(a0, b0, b1, slot)
                if w1 > 1e-6:
                    pl.tri(a0, b1, a1, slot)
        else:
            pl.tri(l0, r0, r1, slot)
            if w1 > 1e-6:
                pl.tri(l0, r1, l1, slot)
    pl.blades.append((part, length, width))
    return centres[-1]


def stalk(pl, base, yaw, height, width, lean, rnd, segs=3, slot=0):
    """A round stem as two crossed ribbons (reads as a cylinder from any side for a quarter of a tube's triangles)."""
    tip = blade(pl, base, yaw, height, width, lean, lean * 0.6, rnd, segs, part=0.5, slot=slot, taper=0.3, normal_up=0.2)
    blade(pl, base, yaw + math.pi / 2, height, width, lean * 0.3, 0.0, rnd, segs, part=0.5, slot=slot, taper=0.3,
          profile=lambda t: 1.0 - 0.7 * t, normal_up=0.2)
    pl.blades.pop()
    return tip


def _disc_point(rng, radius):
    r, a = radius * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
    return (r * math.cos(a), r * math.sin(a), 0.0), a


# ---------------------------------------------------------------------------------------------------------- plants

def lawn_tile(seed, blades, size=0.5, light=False):
    """Mown bermuda on a `size` square tile: short flat blades, half with square mown tips, some lying over, and a few
    runners (stolons) along the ground. Tiles are placed on a jittered grid with random yaw; the blades reach a few
    cm past the tile so the seams never line up."""
    rng = random.Random(seed)
    pl = Plant("lawn")
    for _ in range(blades):
        base = (rng.uniform(-size / 2, size / 2), rng.uniform(-size / 2, size / 2), -0.004)
        rnd = rng.random()
        cut = rng.random() < 0.5
        length = rng.uniform(0.04, 0.065) if cut else rng.uniform(0.025, 0.06)
        width = rng.uniform(0.0015, 0.003) * (2.2 if light else 1.0)
        tilt = rng.uniform(0.1, 0.9) if rng.random() < 0.8 else rng.uniform(1.0, 1.35)
        blade(pl, base, rng.uniform(0, 2 * math.pi), length, width, tilt, rng.uniform(0.0, 0.6), rnd,
              segs=1 if light else 2, cut=cut, taper=0.6)
    if not light:
        for _ in range(4):
            base = (rng.uniform(-size / 2, size / 2), rng.uniform(-size / 2, size / 2), 0.004)
            blade(pl, base, rng.uniform(0, 2 * math.pi), rng.uniform(0.08, 0.16), 0.0018, 1.5, 0.0, rng.random(),
                  segs=2, part=0.5, taper=0.2, normal_up=0.8)
    return pl.finish()


def rough_tile(seed, blades, stalks, size=0.5, light=False):
    """The unmown edge: longer leaning blades and seed stalks, bermuda's finger heads and bahia's V pairs."""
    rng = random.Random(seed)
    pl = Plant("rough")
    for _ in range(blades):
        base = (rng.uniform(-size / 2, size / 2), rng.uniform(-size / 2, size / 2), -0.004)
        blade(pl, base, rng.uniform(0, 2 * math.pi), rng.uniform(0.06, 0.26), rng.uniform(0.002, 0.005) * (2.6 if light else 1.0),
              rng.uniform(0.15, 1.0), rng.uniform(0.2, 1.2), rng.random(), segs=2 if light else 3)
    for k in range(stalks):
        base = (rng.uniform(-size / 2, size / 2), rng.uniform(-size / 2, size / 2), -0.004)
        rnd = rng.random()
        bahia = k % 3 == 0
        h = rng.uniform(0.25, 0.45) if bahia else rng.uniform(0.15, 0.32)
        yaw = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.05, 0.5) if rng.random() < 0.6 else rng.uniform(0.6, 1.1)
        tip = blade(pl, base, yaw, h, 0.0016, lean, lean * 0.5, rnd, segs=2 if light else 3, part=0.5, taper=0.2)
        if light:
            continue
        fingers = 2 if bahia else rng.randint(3, 6)
        for f in range(fingers):
            fy = yaw + (f - (fingers - 1) / 2) * (0.9 if bahia else 2 * math.pi / fingers)
            blade(pl, tip, fy, rng.uniform(0.04, 0.08) if bahia else rng.uniform(0.03, 0.06), 0.0025,
                  rng.uniform(0.35, 0.8), 0.4, rnd, segs=2, part=1.0, slot=1, taper=0.4)
    return pl.finish()


def bluestem(seed, blades, stems, light=False):
    """Little bluestem: a tight upright bunch of folded blades, flowering stems with fluffy seed tufts spaced along
    their top third."""
    rng = random.Random(seed)
    pl = Plant("bluestem")
    r0 = rng.uniform(0.07, 0.13)
    for _ in range(blades):
        base, a = _disc_point(rng, r0)
        blade(pl, base, a + rng.uniform(-0.5, 0.5), rng.uniform(0.25, 0.6), rng.uniform(0.003, 0.006) * (2.6 if light else 1.0),
              rng.uniform(0.12, 0.7), rng.uniform(0.2, 1.1), rng.random(), segs=2 if light else 4,
              fold=0.0 if light else 0.35)
    for _ in range(stems):
        base, a = _disc_point(rng, r0 * 0.7)
        rnd = rng.random()
        h = rng.uniform(0.7, 1.05)
        lean = rng.uniform(0.03, 0.3)
        tip = blade(pl, base, a, h, 0.0022, lean, lean * 0.4, rnd, segs=2 if light else 4, part=0.5, taper=0.2)
        if light:
            continue
        for k in range(rng.randint(4, 7)):     # seed tufts on short side branches, down the top third
            t = 1.0 - k * rng.uniform(0.05, 0.09)
            p = _add(_mul(base, 1.0 - t), _mul(tip, t))
            blade(pl, p, a + rng.uniform(-1.5, 1.5), rng.uniform(0.02, 0.04), rng.uniform(0.008, 0.014),
                  rng.uniform(0.3, 0.8), 0.3, rnd, segs=1, part=1.0, slot=1, taper=1.0)
    return pl.finish()


def switchgrass(seed, stems, panicles, light=False):
    """Switchgrass: tall upright stems with leaves arching out from them, and an open airy panicle on top."""
    rng = random.Random(seed)
    pl = Plant("switchgrass")
    r0 = rng.uniform(0.12, 0.25)
    for i in range(stems):
        base, a = _disc_point(rng, r0)
        rnd = rng.random()
        h = rng.uniform(0.9, 1.5)
        lean = rng.uniform(0.02, 0.25)
        tip = blade(pl, base, a, h, 0.004, lean, lean * 0.4, rnd, segs=2 if light else 4, part=0.5, taper=0.3)
        for k in range(2 if light else 6):             # leaves leave the stem up its lower three quarters and arch out
            t = rng.uniform(0.05, 0.75)
            p = _add(_mul(base, 1.0 - t), _mul(tip, t))
            blade(pl, p, a + rng.uniform(-1.2, 1.2), rng.uniform(0.3, 0.55), rng.uniform(0.006, 0.012) * (2.2 if light else 1.0),
                  rng.uniform(0.3, 0.6), rng.uniform(0.5, 1.4), rnd, segs=2 if light else 4, fold=0.0 if light else 0.3)
        if i < panicles and not light:
            for k in range(rng.randint(7, 11)):        # the panicle: fine branches with tiny seeds at their ends
                t = 1.0 - k * 0.035
                p = _add(_mul(base, 1.0 - t), _mul(tip, t))
                br = blade(pl, p, a + rng.uniform(0, 2 * math.pi), rng.uniform(0.08, 0.2), 0.0012, rng.uniform(0.5, 1.0), 0.3,
                           rnd, segs=2, part=1.0, slot=1, taper=0.0)
                for s in range(3):
                    blade(pl, br, rng.uniform(0, 2 * math.pi), 0.01, 0.006, rng.uniform(0.3, 1.2), 0.0, rnd, segs=1,
                          part=1.0, slot=1, taper=1.0)
    return pl.finish()


def johnsongrass(seed, stems, light=False):
    """Johnsongrass: coarse cane stems with broad arching leaves (a pale midrib, so folded: the midrib row is where the
    material puts it) and a loose branched panicle."""
    rng = random.Random(seed)
    pl = Plant("johnsongrass")
    r0 = rng.uniform(0.15, 0.3)
    for _ in range(stems):
        base, a = _disc_point(rng, r0)
        rnd = rng.random()
        h = rng.uniform(1.0, 1.9)
        lean = rng.uniform(0.02, 0.25)
        tip = blade(pl, base, a, h, 0.008, lean, lean * 0.5, rnd, segs=2 if light else 5, part=0.5, taper=0.25)
        for k in range(3 if light else 6):
            t = 0.08 + k * (0.75 / 6) + rng.uniform(-0.03, 0.03)
            p = _add(_mul(base, 1.0 - t), _mul(tip, t))
            blade(pl, p, a + (math.pi if k % 2 else 0.0) + rng.uniform(-0.5, 0.5), rng.uniform(0.25, 0.5),
                  rng.uniform(0.010, 0.02), rng.uniform(0.6, 0.9), rng.uniform(0.6, 1.3), rnd,
                  segs=2 if light else 5, fold=0.0 if light else 0.25, taper=0.9)
        if light:
            continue
        for k in range(rng.randint(8, 12)):
            t = 1.0 - k * 0.022
            p = _add(_mul(base, 1.0 - t), _mul(tip, t))
            br = blade(pl, p, a + rng.uniform(0, 2 * math.pi), rng.uniform(0.06, 0.15), 0.0015, rng.uniform(0.4, 0.9), 0.4,
                       rnd, segs=2, part=1.0, slot=1, taper=0.0)
            for s in range(2):
                blade(pl, br, rng.uniform(0, 2 * math.pi), 0.012, 0.004, rng.uniform(0.3, 1.0), 0.0, rnd, segs=1,
                      part=1.0, slot=1, taper=1.0)
    return pl.finish()


def sedge(seed, blades, light=False):
    """A sedge tussock: keeled leaves fountaining out and over, a few three-sided stems with small brown spikes."""
    rng = random.Random(seed)
    pl = Plant("sedge")
    r0 = rng.uniform(0.06, 0.12)
    for _ in range(blades):
        base, a = _disc_point(rng, r0)
        blade(pl, base, a + rng.uniform(-0.4, 0.4), rng.uniform(0.3, 0.75), rng.uniform(0.003, 0.008) * (2.4 if light else 1.0),
              rng.uniform(0.15, 0.6), rng.uniform(0.8, 2.0), rng.random(), segs=3 if light else 5,
              fold=0.0 if light else 0.4)
    if not light:
        for _ in range(rng.randint(5, 9)):
            base, a = _disc_point(rng, r0 * 0.6)
            rnd = rng.random()
            tip = blade(pl, base, a, rng.uniform(0.3, 0.55), 0.003, rng.uniform(0.05, 0.4), 0.3, rnd, segs=3, part=0.5, taper=0.2)
            for s in range(3):
                blade(pl, tip, a + s * 2.1, rng.uniform(0.015, 0.03), 0.005, rng.uniform(0.2, 0.6), 0.0, rnd, segs=1,
                      part=1.0, slot=1, taper=0.6)
    return pl.finish()


def horseweed(seed, leaves, light=False):
    """Horseweed: one stem crowded with narrow leaves, branching at the top into small flower heads."""
    rng = random.Random(seed)
    pl = Plant("horseweed")
    rnd = rng.random()
    h = rng.uniform(0.6, 1.4)
    yaw = rng.uniform(0, 2 * math.pi)
    base = (0.0, 0.0, -0.01)
    tip = stalk(pl, base, yaw, h, 0.008, rng.uniform(0.0, 0.12), rnd, segs=2 if light else 4)
    for k in range(leaves // (3 if light else 1)):
        t = rng.uniform(0.05, 0.85)
        p = _add(_mul(base, 1.0 - t), _mul(tip, t))
        size = 1.0 - 0.6 * t
        blade(pl, p, rng.uniform(0, 2 * math.pi), rng.uniform(0.03, 0.1) * size + 0.01, rng.uniform(0.004, 0.01),
              rng.uniform(0.6, 1.2), rng.uniform(0.0, 0.6), rng.random(), segs=1 if light else 2, taper=0.7)
    if not light:
        for k in range(rng.randint(10, 16)):
            t = 1.0 - k * 0.012
            p = _add(_mul(base, 1.0 - t), _mul(tip, t))
            br = blade(pl, p, rng.uniform(0, 2 * math.pi), rng.uniform(0.05, 0.14), 0.002, rng.uniform(0.4, 0.9), -0.3, rnd,
                       segs=2, part=0.5, taper=0.2)
            for s in range(2):
                blade(pl, br, rng.uniform(0, 2 * math.pi), 0.006, 0.006, rng.uniform(0.0, 0.8), 0.0, rnd, segs=1,
                      part=1.0, slot=1, taper=1.0)
    return pl.finish()


def _rosette_leaf(pl, rng, base, yaw, length, width, lobes, rnd, segs):
    def prof(t):
        env = math.sin(math.pi * min(1.0, t * 1.05)) ** 0.6
        if lobes:
            env *= 0.55 + 0.45 * abs(math.sin(t * lobes * math.pi))
        return env
    blade(pl, base, yaw, length, width, rng.uniform(1.15, 1.4), 0.25, rnd, segs=segs, profile=prof, normal_up=0.6)


def dandelion(seed, light=False):
    rng = random.Random(seed)
    pl = Plant("dandelion")
    for k in range(rng.randint(9, 14)):
        _rosette_leaf(pl, rng, (0.0, 0.0, 0.0), k * 2.4 + rng.uniform(-0.3, 0.3), rng.uniform(0.1, 0.24), rng.uniform(0.025, 0.045),
                      5 if not light else 0, rng.random(), 3 if light else 8)
    if not light:
        for _ in range(rng.randint(1, 3)):
            rnd = rng.random()
            tip = blade(pl, (0.0, 0.0, 0.0), rng.uniform(0, 6.28), rng.uniform(0.08, 0.2), 0.004, rng.uniform(0.1, 0.5), 0.2, rnd,
                        segs=3, part=0.5, taper=0.0)
            for r in range(8):                          # the flower: a flat ring of strap petals
                blade(pl, tip, r * math.pi / 4, 0.016, 0.006, 1.45, 0.0, rnd, segs=1, part=1.0, slot=1, taper=0.2, normal_up=0.8)
    return pl.finish()


def clover(seed, light=False):
    rng = random.Random(seed)
    pl = Plant("clover")
    for _ in range(14 if light else 40):
        base, _a = _disc_point(rng, 0.22)
        rnd = rng.random()
        tip = blade(pl, base, rng.uniform(0, 6.28), rng.uniform(0.04, 0.1), 0.0015, rng.uniform(0.1, 0.6), 0.2, rnd, segs=2,
                    part=0.5, taper=0.0)
        y0 = rng.uniform(0, 6.28)
        for l in range(3):                              # three round leaflets, near flat
            blade(pl, tip, y0 + l * 2.094, rng.uniform(0.01, 0.018), 0.014, 1.4, 0.0, rnd, segs=1 if light else 2,
                  profile=lambda t: math.sin(math.pi * min(1.0, t * 1.0 + 0.05)) ** 0.5 + 0.05, normal_up=0.7)
    if not light:
        for _ in range(rng.randint(3, 7)):
            base, _a = _disc_point(rng, 0.18)
            rnd = rng.random()
            tip = blade(pl, base, rng.uniform(0, 6.28), rng.uniform(0.08, 0.14), 0.0015, rng.uniform(0.05, 0.3), 0.1, rnd, segs=2,
                        part=0.5, taper=0.0)
            for r in range(6):
                blade(pl, tip, r * 1.047, 0.01, 0.008, rng.uniform(0.6, 1.6), 0.0, rnd, segs=1, part=1.0, slot=1, taper=0.5,
                      normal_up=0.6)
    return pl.finish()


def plantain(seed, light=False):
    rng = random.Random(seed)
    pl = Plant("plantain")
    for k in range(rng.randint(6, 9)):
        _rosette_leaf(pl, rng, (0.0, 0.0, 0.0), k * 2.4 + rng.uniform(-0.3, 0.3), rng.uniform(0.08, 0.15), rng.uniform(0.04, 0.08),
                      0, rng.random(), 3 if light else 6)
    if not light:
        for _ in range(rng.randint(1, 4)):
            rnd = rng.random()
            tip = blade(pl, (0.0, 0.0, 0.0), rng.uniform(0, 6.28), rng.uniform(0.1, 0.2), 0.003, rng.uniform(0.05, 0.35), 0.1, rnd,
                        segs=3, part=0.5, taper=0.0)
            blade(pl, tip, rng.uniform(0, 6.28), rng.uniform(0.05, 0.1), 0.007, 0.05, 0.0, rnd, segs=2, part=1.0, slot=1, taper=0.3)
    return pl.finish()


# ------------------------------------------------------------------------------------------------------ region packs

import json  # noqa: E402
import os  # noqa: E402

PACKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packs")
# The shapes above are archetypes; a region pack (packs/<name>/pack.json) picks which, with which numbers.
ARCHETYPES = {"mown_tile": lawn_tile, "rough_tile": rough_tile, "fine_bunch": bluestem, "panicle_clump": switchgrass,
              "broadleaf_cane": johnsongrass, "tussock": sedge, "stalk_weed": horseweed, "lobed_rosette": dandelion,
              "trefoil_patch": clover, "broad_rosette": plantain}
PACK = {}


def use_pack(name=None):
    """Load a region pack (default: $GRASS_PACK or north-texas-lake): pack.json, look.json and cards/*.json."""
    name = name or os.environ.get("GRASS_PACK", "north-texas-lake")
    root = os.path.join(PACKS, name)
    PACK.clear()
    PACK.update(json.load(open(os.path.join(root, "pack.json"))))
    PACK["look"] = json.load(open(os.path.join(root, "look.json")))
    PACK["cards"] = {f[:-5]: json.load(open(os.path.join(root, "cards", f)))
                     for f in sorted(os.listdir(os.path.join(root, "cards"))) if f.endswith(".json")}
    PACK["root"] = root
    return PACK


def pack():
    return PACK if PACK else use_pack(pack_from_argv())


def pack_from_argv():
    """Every tool here takes --pack <name> (read before argparse, so module-level tables see the right pack)."""
    import sys
    return sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else None


# ------------------------------------------------------------------------------------------------------- far cards

def far_frame(card_id):
    """The square frame (side in metres) the baker renders the source plant into: the card is that square."""
    lo, hi = catalogue(False)[pack()["far"]["source"][card_id]][1]().bounds()
    return max(hi[2], hi[0] - lo[0], hi[1] - lo[1]) * 1.02


def far_card(card_id, side):
    """Two upright quads crossed at 90 deg (4 triangles), each showing the plant's baked side view from its atlas slot
    (T_GrassFar_<season>: 3 x 2 slots in the pack's far.atlas order). For 60 to 150 m on High, 100 to 200 m on Ultra,
    where a bunch is 2 to 10 pixels tall and only its outline and colour count."""
    i = pack()["far"]["atlas"].index(card_id)
    u0, v0 = (i % 3) / 3.0, 1.0 - (i // 3 + 1) / 2.0
    pl = Plant("far")
    for yaw in (0.0, math.pi / 2):
        d = (math.cos(yaw), math.sin(yaw), 0.0)
        ids = []
        for cx, cz in ((-0.5, 0.0), (0.5, 0.0), (0.5, 1.0), (-0.5, 1.0)):
            idx = pl.vert((d[0] * cx * side, d[1] * cx * side, cz * side), (0.0, 0.0, 1.0), 0.5, 0.0,
                          u0 + (cx + 0.5) / 3.0, v0 + cz / 2.0)
            pl.c[idx][0] = cz
            ids.append(idx)
        pl.tri(ids[0], ids[1], ids[2])
        pl.tri(ids[0], ids[2], ids[3])
    pl.blades.append((0.0, side, side))
    return pl


# ---------------------------------------------------------------------------------------------------------- the set

def catalogue(with_far=True):
    """mesh name -> (card id, builder, kind) for every mesh the pack ships. kind: hero (LOD0), light, far (a crossed
    card whose texture the renderer bakes from the hero)."""
    out = {}
    for m in pack()["meshes"]:
        fn, args = ARCHETYPES[m["archetype"]], m.get("args", {})
        for i in range(m.get("variants", 1)):
            name = m["name"].replace("{i}", str(i))
            out[name] = (m["card"], lambda fn=fn, seed=m["seed"] + i, args=args: fn(seed, **args), m["kind"])
    if with_far:
        for cid, src in pack()["far"]["source"].items():
            out[src.rsplit("_", 1)[0] + "_Far"] = (cid, lambda cid=cid: far_card(cid, far_frame(cid)), "far")
    return out
