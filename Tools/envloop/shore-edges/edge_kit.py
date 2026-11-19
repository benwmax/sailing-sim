"""Shore edge kit (shore plan Track C, docs/envloop/shore-edges/): the lake's shoreline types, built from code.

The plan takes the shore from four edge types (natural bank, concrete bulkhead, stepped riprap, sand strip) to ten:

    riprap        done in the rock loop (Tools/blender/rock_kit.py, docs/shore-loop/rocks.md): not rebuilt here
    bulkhead      poured concrete wall, 300 mm cap, 75 mm weep holes, panel joints
    sheetpile     steel Z-pile wall with a channel cap and tie-rod nuts on a waler
    limestone     stacked limestone blocks (0.6 m courses), each course stepped back
    timber        treated posts and horizontal boards, a cap board on top
    claycut       an eroded blackland-clay cut bank: wave-cut notch, slumped blocks, hanging roots, a narrow bench
    mudflat       the wide flat a low lake leaves: ripples, drying and cracking toward the bank
    gravel        a gravel and shell beach: berm at the wrack line, pebbles and Asian clam shells
    reedcove      a shallow cove with a cattail and rush stand (stand-in plants: Track B makes the real ones)
    ramp          a one-lane concrete launch ramp, 14 percent, V-grooves, gravel shoulders

Every type builds a stretch of shore `length` metres long on x, the land toward +y, the lake toward -y, z up, z = 0 the
435.5 ft conservation pool. The look is not baked: each vertex carries which surface it is and two small hints, and the
shared layer (edge_layer.py: wet line, stain band, scum line, algae, run-off, wrack) is worked out per pixel from the
height against the lake, so one mesh is right at every lake level.

Vertex colour (linear), read by edge_layer.py and later by the in-game material:
    R = (surface id + 0.5) / 16 (SURF below)
    G = a per-part random (board, block, stone, plant: its own shade)
    B = run-off source: 1 on the wall face straight under a weep hole or a bolt, fading down to the water

Pure numpy; render_edges.py turns a build into a Blender mesh. Everything specific to a region (which types it has,
their sizes, the lake's levels, colours, placement rules) is a pack, packs/<name>/pack.json with the types' cards beside
it (packs/north-texas-lake/ first); the builders are the same everywhere. Sizes there are the plan's interim size card
(Track 0 publishes the shared one) and published construction sizes; `measures` reports what was built for the checks.
"""
import json
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "blender"))
from rock_kit import perlin, fbm  # noqa: E402  (vectorised noise; the rock kit's)

# Parts that stand in for the terrain (Track A and the terrain mesh own the ground in game): not counted in a type's
# triangle budget.
GROUND_PARTS = ("lot", "bed", "flat", "beach", "cove", "shoulders")
SURF = dict(soil=0, lawn=1, concrete=2, steel=3, limestone=4, timber=5, claycut=6, mud=7, gravel=8, shell=9, sand=10,
            ramp=11, wood=12, leaf=13, reed=14, drygrass=15)
TYPES = ["bulkhead", "sheetpile", "limestone", "timber", "claycut", "mudflat", "gravel", "reedcove", "ramp"]

# The plan's interim size card (Track 0 replaces it with the shared one) and the measures the types are built to.
# Region data (sizes, levels, colours, placement) is a pack: packs/<name>/pack.json. The kit's builders read SIZE, which
# build() sets from the pack it is given.
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PACK = "north-texas-lake"


def load_pack(name=DEFAULT_PACK):
    path = name if name.endswith(".json") else os.path.join(HERE, "packs", name, "pack.json")
    pack = json.load(open(path))
    pack["dir"] = os.path.dirname(os.path.abspath(path))
    return pack


SIZE = load_pack()["sizes"]


class Mesh:
    """Triangles with per-vertex colour and a smooth flag per triangle; parts are named for the size checks."""

    def __init__(self):
        self.V, self.F, self.C, self.S = [], [], [], []
        self.n = 0
        self.parts = {}
        self.part_tris = {}
        self.part_of = []   # the part of each add() call (export_edges.py drops the ground parts)

    def add(self, V, F, C, smooth=True, part=None):
        V = np.asarray(V, float).reshape(-1, 3)
        F = np.asarray(F, np.int64).reshape(-1, 3)
        C = np.broadcast_to(np.asarray(C, float), (len(V), 3)) if np.ndim(C) == 1 else np.asarray(C, float)
        self.V.append(V)
        self.F.append(F + self.n)
        self.C.append(C)
        self.S.append(np.full(len(F), bool(smooth)))
        self.part_of.append(part)
        if part:
            self.part_tris[part] = self.part_tris.get(part, 0) + len(F)
            lo, hi = V.min(0), V.max(0)
            if part in self.parts:
                plo, phi = self.parts[part]
                lo, hi = np.minimum(lo, plo), np.maximum(hi, phi)
            self.parts[part] = (lo, hi)
        self.n += len(V)

    def arrays(self):
        return np.concatenate(self.V), np.concatenate(self.F), np.concatenate(self.C), np.concatenate(self.S)

    @property
    def triangles(self):
        return int(sum(len(f) for f in self.F))

    @property
    def piece_triangles(self):
        """Triangles of the edge itself (walls, bank, scatter, plants), without the stand-in ground."""
        return int(sum(n for p, n in self.part_tris.items() if p not in GROUND_PARTS))


def col(surface, shade=0.5, run=0.0):
    return np.array([(SURF[surface] + 0.5) / 16.0, shade, run])


def cols(surface_ids, shade, run=None):
    """Per-vertex colours from arrays of surface ids, shades and run-off."""
    sid = np.asarray(surface_ids, float)
    shade = np.broadcast_to(np.asarray(shade, float), sid.shape)
    run = np.zeros_like(sid) if run is None else np.broadcast_to(np.asarray(run, float), sid.shape)
    return np.stack([(sid + 0.5) / 16.0, shade, run], -1).reshape(-1, 3)


def grid_faces(nu, nv):
    """Two triangles per cell of an nv x nu vertex grid (row-major)."""
    i, j = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1))
    a = (j * nu + i).ravel()
    b, c, d = a + 1, a + nu + 1, a + nu
    return np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])


def box(m, c, half, surface, shade=0.5, yaw=0.0, smooth=False, part=None, run=0.0):
    """An axis box (centre, half sizes), turned by yaw about z."""
    sx, sy, sz = half
    P = np.array([[x, y, z] for z in (-sz, sz) for y in (-sy, sy) for x in (-sx, sx)], float)
    cy, sy_ = math.cos(yaw), math.sin(yaw)
    P = P @ np.array([[cy, sy_, 0], [-sy_, cy, 0], [0, 0, 1]]) + np.asarray(c, float)
    q = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    F = [t for a, b, cc, d in q for t in ((a, b, cc), (a, cc, d))]
    m.add(P, F, col(surface, shade, run), smooth, part)


def tube(m, pts, radii, surface, shade=0.5, sides=6, part=None):
    """A tube along a polyline (N, 3) with a radius per point."""
    pts = np.asarray(pts, float)
    radii = np.broadcast_to(np.asarray(radii, float), (len(pts),))
    tang = np.gradient(pts, axis=0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
    ref = np.where(np.abs(tang[:, 2:3]) < 0.9, np.array([[0, 0, 1.0]]), np.array([[1.0, 0, 0]]))
    u = np.cross(tang, ref)
    u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-9)
    v = np.cross(tang, u)
    a = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    V = pts[:, None, :] + radii[:, None, None] * (np.cos(a)[None, :, None] * u[:, None, :] + np.sin(a)[None, :, None] * v[:, None, :])
    V = V.reshape(-1, 3)
    F = []
    for k in range(len(pts) - 1):
        for s in range(sides):
            p, q = k * sides + s, k * sides + (s + 1) % sides
            F += [(p, q, q + sides), (p, q + sides, p + sides)]
    m.add(V, F, col(surface, shade), True, part)


def heightfield(m, x0, x1, y0, y1, step, zfn, sidfn, shadefn=None, part=None, smooth=True):
    """Ground as a grid; zfn(X, Y) heights, sidfn(X, Y, Z) surface ids."""
    nu = max(2, int(round((x1 - x0) / step)) + 1)
    nv = max(2, int(round((y1 - y0) / step)) + 1)
    X, Y = np.meshgrid(np.linspace(x0, x1, nu), np.linspace(y0, y1, nv))
    Z = zfn(X, Y)
    sid = sidfn(X, Y, Z)
    sh = shadefn(X, Y) if shadefn else 0.5 + 0.0 * X
    m.add(np.stack([X, Y, Z], -1).reshape(-1, 3), grid_faces(nu, nv), cols(sid, sh), smooth, part)


def pn(P, seed, octaves=1):
    """rock_kit's noise on points of any shape (..., 3)."""
    P = np.asarray(P, float)
    q = P.reshape(-1, 3)
    return (fbm(q, octaves, seed) if octaves > 1 else perlin(q, seed)).reshape(P.shape[:-1])


def noise2(X, Y, scale, seed, octaves=1):
    P = np.stack([np.asarray(X).ravel() / scale, np.asarray(Y).ravel() / scale, np.zeros(np.size(X))], 1)
    return (fbm(P, octaves, seed) if octaves > 1 else perlin(P, seed)).reshape(np.shape(X))


# ------------------------------------------------------------------ the shared pieces
def lake_bed(m, length, y_toe, z_toe, seed, y_far=-40.0):
    """The bed in front of a wall: soft clay and silt falling away gently from the toe."""
    def z(X, Y):
        return z_toe - 0.035 * (y_toe - Y) + 0.06 * noise2(X, Y, 3.0, seed)
    heightfield(m, -length / 2, length / 2, y_far, y_toe, 0.5 if length > 30 else 0.25, z,
                lambda X, Y, Z: np.where(noise2(X, Y, 2.0, seed + 1) > 0.25, SURF["gravel"], SURF["mud"]),
                lambda X, Y: 0.5 + 0.5 * noise2(X, Y, 1.0, seed + 2), part="bed")


def back_lot(m, length, y0, z0, seed, surface="lawn", y_far=60.0):
    """The land behind a wall or bank: a lawn (or dry grass) rising gently."""
    def z(X, Y):
        return z0 + 0.012 * (Y - y0) + 0.04 * noise2(X, Y, 4.0, seed) * np.clip((Y - y0) / 2.0, 0, 1)
    heightfield(m, -length / 2, length / 2, y0, y_far, 1.0 if length > 30 else 0.5, z,
                lambda X, Y, Z: np.full_like(X, SURF[surface]), lambda X, Y: 0.5 + 0.5 * noise2(X, Y, 2.5, seed + 3),
                part="lot")


def debris_line(m, rng, length, zfn, y_lo, y_hi, wrack_z, per_m=8.0, near=None):
    """The wrack: sticks lying mostly along the shore and leaf flecks, a thin band where the ground meets wrack_z.

    zfn(X, Y) is the ground; the band is found by marching y between y_lo and y_hi at each x. `near` (half width in x)
    limits the leaves to the middle, where the 3 m camera can see them, to keep the far builds light.
    """
    xs = np.arange(-length / 2, length / 2, 0.25)
    ys = np.linspace(y_lo, y_hi, 200)
    X, Y = np.meshgrid(xs, ys)
    Z = zfn(X, Y)
    k = np.argmin(np.abs(Z - wrack_z), axis=0)
    yline = ys[k]
    n_sticks = int(per_m * length)
    for _ in range(n_sticks):
        x = rng.uniform(-length / 2, length / 2)
        y = np.interp(x, xs, yline) + rng.gauss(0, 0.12)
        ln = rng.choice([0.08, 0.12, 0.2, 0.3, 0.45, 0.7]) * rng.uniform(0.7, 1.3)
        r = min(0.03, 0.004 + 0.02 * ln * rng.random())
        yaw = rng.gauss(0, 0.5) + (math.pi if rng.random() < 0.5 else 0.0)
        d = np.array([math.cos(yaw), math.sin(yaw), 0.0]) * ln / 2
        a, b = np.array([x, y, 0.0]) - d, np.array([x, y, 0.0]) + d
        pts = np.linspace(a, b, 4)
        pts[:, 1] += np.array([0, rng.gauss(0, 0.01), rng.gauss(0, 0.01), 0])
        pts[:, 2] = zfn(pts[:, 0], pts[:, 1]) + r * 0.7
        tube(m, pts, np.linspace(r, r * 0.6, 4), "wood", rng.random(), sides=5, part="debris")
    lim = min(near, length / 2) if near else length / 2   # never past the piece's ends (the game's 4 m pieces)
    for _ in range(int(per_m * 3.0 * 2 * lim)):
        x = rng.uniform(-lim, lim)
        y = np.interp(x, xs, yline) + rng.gauss(0, 0.18)
        s = rng.uniform(0.025, 0.06)
        a = rng.uniform(0, 2 * math.pi)
        c = np.array([x, y, float(zfn(np.array(x), np.array(y))) + 0.004])
        P = c + s * np.array([[math.cos(a + t), math.sin(a + t), 0.3 * rng.random()] for t in (0, 2.1, 3.14, 4.2)])
        m.add(P, [(0, 1, 2), (0, 2, 3)], col("leaf", rng.random()), False, "debris")


def pebbles(m, rng, count, area, zfn, surface="gravel", size=(0.02, 0.07), flat=0.55, part="pebbles"):
    """Small stones (or shells: surface 'shell', half domes) on the ground."""
    x0, x1, y0, y1 = area
    # An octahedron subdivided once and rounded: 32 triangles a stone.
    base = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    tris = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    V, F, mid = list(base), [], {}

    def midpoint(a, b):
        key = (min(a, b), max(a, b))
        if key not in mid:
            p = (V[a] + V[b]) / 2
            V.append(p / np.linalg.norm(p))
            mid[key] = len(V) - 1
        return mid[key]
    for a, b, c in tris:
        ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
        F += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
    V = np.array(V)
    for _ in range(count):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        s = rng.uniform(*size)
        sc = np.array([s * rng.uniform(0.8, 1.3), s * rng.uniform(0.6, 1.0), s * flat * rng.uniform(0.7, 1.2)])
        P = V * sc
        if surface == "shell":
            P[:, 2] = np.maximum(P[:, 2], 0.0) * 0.8   # a valve: a shallow dome, the hollow side down or up
            if rng.random() < 0.35:
                P[:, 2] *= -0.6
        yaw = rng.uniform(0, 2 * math.pi)
        R = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
        z = float(zfn(np.array(x), np.array(y)))
        m.add(P @ R.T + np.array([x, y, z + sc[2] * 0.25]), F, col(surface, rng.random()), True, part)


# ------------------------------------------------------------------ the types
def build_bulkhead(m, length, rng, seed):
    S = SIZE
    top = S["bulkhead_face_above_pool"]
    toe = -1.5
    # The face: a grid fine enough for the run-off under the weep holes (10 cm across, 5 cm up).
    xs = np.arange(-length / 2, length / 2 + 1e-6, 0.1)
    zs = np.linspace(toe, top, int((top - toe) / 0.05) + 1)
    X, Z = np.meshgrid(xs, zs)
    Y = -0.004 * noise2(X, Z, 0.8, seed)        # a poured face is not perfectly flat
    holes = np.arange(-length / 2 + S["weep_spacing"] / 2, length / 2, S["weep_spacing"])
    dx = np.min(np.abs(X[..., None] - holes), -1)
    run = np.clip(1.0 - dx / 0.09, 0, 1) * (Z < S["weep_z"]) * np.clip((Z - toe) / 0.8, 0, 1)
    m.add(np.stack([X, Y, Z], -1).reshape(-1, 3), grid_faces(len(xs), len(zs)), cols(np.full(X.shape, SURF["concrete"]),
          0.5 + 0.0 * X, run), False, "face")
    # The cap: 300 mm wide, 300 mm tall, a 25 mm lip proud of the face, in pours one panel long.
    cw, ch = S["bulkhead_cap_w"], S["bulkhead_cap_h"]
    for x in np.arange(-length / 2, length / 2, S["panel"]):
        x1 = min(x + S["panel"], length / 2)   # the last pour ends with the piece
        box(m, ((x + x1) / 2, cw / 2 - 0.025, top + ch / 2), ((x1 - x) / 2 - 0.006, cw / 2, ch / 2), "concrete",
            rng.uniform(0.3, 0.7), part="cap")
    # Weep holes: a dark recess (the pipe's end) 75 mm across, a few mm proud.
    for x in holes:
        a = np.linspace(0, 2 * math.pi, 10, endpoint=False)
        r = S["weep_dia"] / 2
        ring = np.stack([x + r * np.cos(a), np.full(10, -0.006), S["weep_z"] + r * np.sin(a)], 1)
        back = ring + np.array([0, 0.08, 0])
        V = np.concatenate([ring, back, [[x, 0.08, S["weep_z"]]]])
        F = [(k, (k + 1) % 10, 10 + (k + 1) % 10) for k in range(10)] + [(k, 10 + (k + 1) % 10, 10 + k) for k in range(10)]
        F += [(10 + k, 10 + (k + 1) % 10, 20) for k in range(10)]
        m.add(V, F, col("wood", 0.0), False, "weep")
    # The fill behind it up to the lawn, the bed in front.
    back_lot(m, length, cw - 0.025, top + ch - 0.02, seed)
    lake_bed(m, length, -0.01, toe + 0.05, seed)
    return dict(cap_w=m.parts["cap"][1][1] - m.parts["cap"][0][1] + 0.0,
                cap_h=m.parts["cap"][1][2] - m.parts["cap"][0][2], weep_dia=S["weep_dia"],
                weep_spacing=float(np.diff(holes).mean()), wall_above_pool=float(m.parts["cap"][1][2]))


def build_sheetpile(m, length, rng, seed):
    S = SIZE
    W, D, top, toe = S["pile_pair_w"], S["pile_depth"], S["pile_top"], -1.6
    # Z profile in plan: flanges (in and out) joined by sloped webs, a pair every W.
    def prof(x):
        t = np.mod(x, W) / W
        f = 0.28   # flange share of half a pair
        y = np.where(t < f, 0.0, np.where(t < 0.5, (t - f) / (0.5 - f), np.where(t < 0.5 + f, 1.0, 1.0 - (t - 0.5 - f) / (0.5 - f))))
        return y * D
    xs = np.sort(np.concatenate([np.arange(-length / 2, length / 2 + 1e-6, 0.04)]))
    zs = np.linspace(toe, top, int((top - toe) / 0.05) + 1)
    X, Z = np.meshgrid(xs, zs)
    Y = prof(X)
    ties = np.arange(-length / 2 + S["tie_spacing"] / 2, length / 2, S["tie_spacing"])
    dx = np.min(np.abs(X[..., None] - ties), -1)
    run = np.clip(1.0 - dx / 0.06, 0, 1) * (Z < S["tie_z"]) * np.clip((Z - toe) / 0.6, 0, 1)
    pair = np.floor((X + length / 2) / W)
    shade = 0.5 + 0.5 * np.sin(pair * 12.9898) % 1.0
    m.add(np.stack([X, Y, Z], -1).reshape(-1, 3), grid_faces(len(xs), len(zs)), cols(np.full(X.shape, SURF["steel"]), shade, run),
          False, "piles")
    # The cap: a steel channel over the pile tops (250 mm), and a waler (a 200 mm channel) with tie-rod nuts.
    box(m, (0.0, D / 2, top + S["channel_h"] / 2), (length / 2, D / 2 + 0.06, S["channel_h"] / 2), "steel", 0.3, part="cap")
    box(m, (0.0, -0.07, S["tie_z"]), (length / 2, 0.07, 0.10), "steel", 0.4, part="waler")
    for x in ties:
        box(m, (x, -0.16, S["tie_z"]), (0.05, 0.02, 0.05), "steel", 0.1, part="nut")
        box(m, (x, -0.19, S["tie_z"]), (0.018, 0.03, 0.018), "steel", 0.0, part="rod")
    back_lot(m, length, D + 0.06, top + S["channel_h"] - 0.03, seed)
    lake_bed(m, length, -0.02, toe + 0.05, seed)
    return dict(pair_w=W, depth=float(Y.max() - Y.min()), tie_spacing=float(np.diff(ties).mean()),
                wall_above_pool=float(m.parts["cap"][1][2]))


def rough_block(m, c, size, rng, seed, surface="limestone", res=0.06):
    """A dressed-ish block: six faces as grids, edges rounded, faces chipped by noise a few cm (a box ray-cast as in the
    rock kit, simpler: the cube grid pushed onto a rounded box and displaced)."""
    sx, sy, sz = (s / 2 for s in size)
    n = [max(3, int(2 * s / res)) for s in (sx, sy, sz)]
    faces = []
    allV, allF = [], []
    off = 0
    for ax in range(3):
        for sign in (-1, 1):
            a1, a2 = [k for k in range(3) if k != ax]
            u = np.linspace(-1, 1, n[a1])
            v = np.linspace(-1, 1, n[a2])
            U, Vv = np.meshgrid(u, v)
            P = np.zeros(U.shape + (3,))
            P[..., ax] = sign
            P[..., a1] = U
            P[..., a2] = Vv
            allV.append(P.reshape(-1, 3))
            F = grid_faces(n[a1], n[a2])
            if (sign > 0) == (ax == 1):   # outward (every face pointed in: Nanite culled the stones' lake faces, round 6)
                F = F[:, ::-1]
            allF.append(F + off)
            off += P.shape[0] * P.shape[1]
    P = np.concatenate(allV)
    F = np.concatenate(allF)
    # Round the box: a superellipsoid-ish squeeze of the corners, then scale and chip.
    q = np.abs(P) ** 18       # round 2: a sharper arris (8 read pillowy)
    rr = (q.sum(1, keepdims=True)) ** (1 / 18)
    P = P / rr
    half = np.array([sx, sy, sz])
    W = P * half
    nrm = P / np.maximum(np.linalg.norm(P, axis=1, keepdims=True), 1e-9)
    d = 0.012 * fbm(W * 4.0 + seed * 7.1, 3, seed) + 0.008 * np.abs(perlin(W * 11.0, seed + 5))
    W = W + nrm * d[:, None] - nrm * 0.006
    m.add(W + np.asarray(c, float), F, col(surface, rng.random()), True, "blocks")


def build_limestone(m, length, rng, seed):
    S = SIZE
    h, d, setback = S["block_h"], S["block_d"], S["block_setback"]
    courses = [(-1.2, 0), (-0.6, 1), (0.0, 2)]
    for z0, k in courses:
        x = -length / 2 - rng.uniform(0, S["block_l"])
        y0 = k * setback
        while x < length / 2:
            L = S["block_l"] * rng.uniform(0.75, 1.25)
            gap = rng.uniform(0.01, 0.03)
            x0, x1 = max(x, -length / 2), min(x + L, length / 2)   # the end blocks are cut to the piece
            if x1 - x0 > 0.12:
                c = ((x0 + x1) / 2, y0 + d / 2 + rng.gauss(0, 0.012), z0 + h / 2 + rng.gauss(0, 0.008))
                rough_block(m, c, (x1 - x0 - gap, d * rng.uniform(0.95, 1.05), h * rng.uniform(0.96, 1.02)), rng, seed + int(x * 10))
            x += L
    top = courses[-1][0] + h
    back_lot(m, length, 2 * setback + d * 0.9, top - 0.02, seed)
    lake_bed(m, length, -0.05, -1.2 + 0.02, seed)
    return dict(course_h=h, setback=setback, wall_above_pool=top, blocks_bbox_z=float(m.parts["blocks"][1][2] - m.parts["blocks"][0][2]))


def build_timber(m, length, rng, seed):
    S = SIZE
    toe, top = -1.3, S["timber_top"]
    bh, bt = S["board_h"], S["board_t"]
    # Boards: horizontal, lake face at y = 0, 6 m long, gaps of 5-12 mm, each a little bowed and its own shade.
    z = toe
    while z < top - bh * 0.5:
        x = -length / 2 - rng.uniform(0, 6.0)
        while x < length / 2:
            L = 6.0 if rng.random() < 0.8 else rng.uniform(2.0, 4.8)
            bow = rng.gauss(0, 0.006)
            nseg = 8
            x0, x1 = max(x, -length / 2), min(x + L, length / 2)   # boards end with the piece
            if x1 - x0 < 0.1:
                x += L
                continue
            xs = np.linspace(x0 + 0.004, x1 - 0.004, nseg + 1)
            yb = bow * np.sin(np.linspace(0, math.pi, nseg + 1))
            V, F = [], []
            for i, (xx, yy) in enumerate(zip(xs, yb)):
                for (dy, dz) in ((0, 0), (0, bh), (bt, bh), (bt, 0)):
                    V.append((xx, yy + dy, z + dz))
            for i in range(nseg):
                a, b = 4 * i, 4 * (i + 1)
                for s in range(4):
                    p, q = a + s, a + (s + 1) % 4
                    r, t = b + (s + 1) % 4, b + s
                    F += [(p, t, r), (p, r, q)]
            m.add(V, F, col("timber", rng.random()), False, "boards")
            x += L
        z += bh + rng.uniform(0.005, 0.012)
    # Posts in front, 2.4 m apart, a little proud of the cap and out of plumb; a cap board over the boards.
    for x in np.arange(-length / 2 + 1.2, length / 2, S["post_spacing"]):
        r = S["post_dia"] / 2
        lean = rng.gauss(0, 0.012)
        pts = np.array([[x, -r - 0.005, toe - 0.3], [x + lean * 0.5, -r - 0.005 - lean, (toe + top) / 2], [x + lean, -r - 0.005 - 2 * lean, top + 0.12]])
        tube(m, pts, np.array([r, r, r * 0.97]), "timber", 0.15 * rng.random(), sides=10, part="posts")
    box(m, (0.0, 0.10, top + 0.025), (length / 2, 0.15, 0.025), "timber", 0.6, part="capboard")
    back_lot(m, length, 0.26, top + 0.03, seed)
    lake_bed(m, length, -0.25, toe + 0.05, seed)
    return dict(board_h=bh, post_dia=S["post_dia"],
                post_spacing=S["post_spacing"], wall_above_pool=float(m.parts["capboard"][1][2]))


def build_claycut(m, length, rng, seed):
    S = SIZE
    # A section whose shape changes along the shore: the scarp's height, how far it has retreated (scallops between
    # firmer spurs) and the notch the waves cut at the pool.
    step = 0.06 if length <= 20 else 0.12
    xs = np.arange(-length / 2, length / 2 + 1e-6, step)
    off = 0.9 * noise2(xs, 0 * xs, 9.0, seed) + 0.25 * noise2(xs, 0 * xs, 2.5, seed + 1)
    H = S["scarp_h"][0] + (S["scarp_h"][1] - S["scarp_h"][0]) * (0.5 + 0.5 * noise2(xs, 0 * xs, 14.0, seed + 2))
    nd = S["notch_depth"] * (0.6 + 0.6 * (0.5 + 0.5 * noise2(xs, 0 * xs, 3.0, seed + 3)))
    # Profile stations (y, z, surface): the bench, the toe, the notch, the face, the topsoil, the lip and the top.
    t_list = []
    for k in range(len(xs)):
        h = H[k]
        prof = [(-4.0, -0.9, "gravel"), (-2.2, -0.35, "gravel"), (-1.0, -0.08, "gravel"), (-0.3, 0.04, "mud"),
                (0.0, 0.08, "claycut"), (nd[k], 0.16, "claycut"), (nd[k] * 0.8, S["notch_h"], "claycut"),
                (0.02, S["notch_h"] + 0.12, "claycut"), (0.0, 0.5 * h, "claycut"), (-0.03, h - 0.45, "claycut"),
                (-0.05, h - 0.30, "soil"), (-0.10, h - 0.02, "soil"), (0.05, h + 0.02, "drygrass"), (0.6, h + 0.05, "drygrass")]
        t_list.append(prof)
    # Resample each profile to the same count along its length (so the grid lines up), denser on the face.
    nv = 44
    P = np.zeros((nv, len(xs), 3))
    SID = np.zeros((nv, len(xs)))
    for k, prof in enumerate(t_list):
        pts = np.array([[p[0], p[1]] for p in prof])
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        tt = np.linspace(0, s[-1], nv)
        yy = np.interp(tt, s, pts[:, 0])
        zz = np.interp(tt, s, pts[:, 1])
        idx = np.clip(np.searchsorted(s, tt, side="right") - 1, 0, len(prof) - 1)
        SID[:, k] = [SURF[prof[i][2]] for i in idx]
        P[:, k, 0] = xs[k]
        P[:, k, 1] = yy + off[k]
        P[:, k, 2] = zz
    # Blocky faceting on the face: slump scars a few cm to 15 cm deep, more where it is tall.
    face = (SID == SURF["claycut"]) | (SID == SURF["soil"])
    jag = 0.07 * pn(P * np.array([1.6, 1.6, 2.2]), seed + 4, 3) + 0.03 * pn(P * 6.0, seed + 5)
    P[..., 1] += np.where(face, jag, 0.0)
    P[..., 2] += np.where(~face, 0.03 * pn(P * 1.5, seed + 6), 0.0)
    shade = 0.5 + 0.5 * pn(P * 0.7, seed + 7)
    m.add(P.reshape(-1, 3), grid_faces(len(xs), nv), cols(SID.ravel(), shade.ravel()), True, "bank")
    # The land behind and slumped blocks of clay at the toe.
    heightfield(m, -length / 2, length / 2, 0.6 + off.max(), 60.0, 1.0,
                lambda X, Y: np.interp(X, xs, H) + 0.05 + 0.01 * (Y - 0.6),
                lambda X, Y, Z: np.full_like(X, SURF["drygrass"]), part="lot")
    for _ in range(int(length * 0.5)):
        x = rng.uniform(-length / 2, length / 2)
        k = int((x + length / 2) / step)
        s = rng.uniform(0.15, 0.45)
        rough_block(m, (x, off[min(k, len(off) - 1)] - rng.uniform(0.15, 0.6), 0.04 + s * 0.3),
                    (s * rng.uniform(1.0, 1.6), s, s * 0.7), rng, seed + k, surface="claycut", res=0.08)
    # Roots: from the topsoil, out of the face, hanging down; a few long ones reach the notch.
    for _ in range(int(length * 1.1)):
        x = rng.uniform(-length / 2, length / 2)
        k = min(int((x + length / 2) / step), len(xs) - 1)
        h = H[k]
        z0 = h - rng.uniform(0.08, 0.5)
        y0 = off[k] - 0.06
        ln = rng.choice([0.2, 0.35, 0.5, 0.8, 1.2]) * rng.uniform(0.7, 1.3)
        n = 7
        t = np.linspace(0, 1, n)
        out = rng.uniform(0.05, 0.25)
        pts = np.stack([x + np.cumsum(np.r_[0, rng.gauss(0, 0.03) * np.ones(n - 1)]),
                        y0 - out * np.sin(t * 1.4) + 0.02 * np.sin(t * 9 + rng.random() * 6),
                        np.maximum(z0 - ln * t ** 1.3, 0.18)], 1)
        r0 = rng.choice([0.004, 0.006, 0.01, 0.015, 0.025])
        tube(m, pts, r0 * (1 - 0.6 * t), "wood", 0.3 + 0.4 * rng.random(), sides=5, part="roots")
    zb = lambda X, Y: np.interp(Y, [-4.0, -2.2, -1.0, -0.3, 0.0], [-0.9, -0.35, -0.08, 0.04, 0.08]) + 0 * X
    debris_line(m, rng, length, lambda X, Y: zb(X, Y - np.interp(X, xs, off)), -2.0, -0.2, 0.0, per_m=5.0, near=10.0)
    pebbles(m, rng, int(220 * min(length, 16) / 16), (-min(6.0, length / 2), min(6.0, length / 2), -1.6, -0.4), lambda X, Y: zb(X, Y - np.interp(X, xs, off)) + 0.0,
            surface="shell", size=(0.012, 0.025), part="shells")
    return dict(scarp_h_min=float(H.min()), scarp_h_max=float(H.max()), notch_depth=float(nd.mean()))


def build_mudflat(m, length, rng, seed):
    S = SIZE
    # The flat: 1:60 from the old bank (an eroded edge at y ~ 12) out under the water; ripples and shallow pans.
    def z(X, Y):
        base = -0.45 + (Y + 15.0) * S["mud_slope"]
        # Ripples: wavelength drifting 0.35-0.55 m, crests wandering and splitting, amplitude patchy (round 2: the
        # even sine of round 1 read as corrugated iron).
        lam = 0.45 * (1.0 + 0.25 * noise2(X, Y, 2.5, seed + 8))
        amp = 0.012 * np.clip(0.55 + 0.6 * noise2(X, Y, 1.5, seed + 7), 0.1, 1.0)
        rip = amp * np.sin(Y * 2 * math.pi / lam + 3.0 * noise2(X, Y, 1.2, seed) + 0.8 * noise2(X, Y, 0.3, seed + 9)) * np.clip(0.3 - base, 0, 0.3) / 0.3
        pans = -0.035 * np.clip(noise2(X, Y, 2.2, seed + 1) - 0.25, 0, 1)
        bank = np.clip((Y - 12.0) / 1.2, 0, 1) * 0.6
        return base + rip + pans + 0.02 * noise2(X, Y, 0.7, seed + 2) + bank
    step = 0.08 if length <= 20 else 0.25
    heightfield(m, -length / 2, length / 2, -64.0, 14.0, step, z,
                lambda X, Y, Zz: np.where(Y > 12.6, SURF["drygrass"], np.where(noise2(X, Y, 4.0, seed + 3) > 0.45, SURF["sand"], SURF["mud"])),
                lambda X, Y: 0.5 + 0.5 * noise2(X, Y, 1.0, seed + 4), part="flat")
    back_lot(m, length, 14.0, float(z(np.array(0.0), np.array(14.0))), seed, surface="drygrass")
    # The wrack at the high-water line, and clam shells scattered over the flat.
    debris_line(m, rng, length, z, -15.0, 13.0, 0.15, per_m=6.0, near=10.0)
    pebbles(m, rng, int(500 * min(length, 16) / 16), (-min(6.0, length / 2), min(6.0, length / 2), -6.0, 6.0), z, surface="shell", size=(0.012, 0.028), part="shells")
    return dict(slope=S["mud_slope"], flat_width_above_gauge=float((0.0 - (-1.0)) / S["mud_slope"]))


def build_gravel(m, length, rng, seed):
    S = SIZE
    # A beach face of 1:10 with a berm at the wrack line and a steeper step under the water.
    def z(X, Y):
        z0 = Y * S["beach_slope"]
        berm = S["berm_z"] - z0
        z1 = np.where(Y > 2.5, np.maximum(z0, S["berm_z"] + (Y - 2.5) * 0.02), z0)
        z1 = np.where(Y < -3.0, -0.3 + (Y + 3.0) * 0.2, z1)
        return np.maximum(z1, -1.6) + 0.025 * noise2(X, Y, 1.5, seed) + 0.012 * noise2(X, Y, 0.4, seed + 1) + 0 * berm
    step = 0.06 if length <= 20 else 0.2
    heightfield(m, -length / 2, length / 2, -12.0, 9.0, step, z,
                lambda X, Y, Zz: np.where(Y > 7.0, SURF["drygrass"], np.where(noise2(X, Y, 1.4, seed + 2) > 0.35, SURF["shell"], SURF["gravel"])),
                lambda X, Y: 0.5 + 0.5 * noise2(X, Y, 0.8, seed + 3), part="beach")
    back_lot(m, length, 9.0, float(z(np.array(0.0), np.array(9.0))), seed, surface="drygrass")
    debris_line(m, rng, length, z, -2.0, 6.0, S["berm_z"], per_m=7.0, near=10.0)
    pebbles(m, rng, int(900 * min(length, 16) / 16), (-min(6.0, length / 2), min(6.0, length / 2), -2.5, 4.0), z, size=(0.02, 0.08))
    pebbles(m, rng, int(500 * min(length, 16) / 16), (-min(6.0, length / 2), min(6.0, length / 2), -2.0, 4.0), z, surface="shell", size=(0.012, 0.028), part="shells")
    return dict(slope=S["beach_slope"], berm_z=S["berm_z"])


def build_reedcove(m, length, rng, seed):
    # A shallow cove: the shore bows back up to 6 m, mud at 1:15, a cattail and rush stand in 0.5 m of water to the bank.
    def shore_y(X):
        return 6.0 * np.cos(np.clip(X / (length * 0.45), -1, 1) * math.pi / 2) ** 2 + 0.4 * noise2(X, 0 * X, 3.0, seed)
    def z(X, Y):
        d = Y - shore_y(X)
        return np.where(d < 0, np.maximum(d / 15.0, -1.2), d / 9.0) + 0.02 * noise2(X, Y, 0.8, seed + 1)
    step = 0.1 if length <= 20 else 0.25
    heightfield(m, -length / 2, length / 2, -20.0, 14.0, step, z,
                lambda X, Y, Zz: np.where(Zz > 0.25, SURF["drygrass"], SURF["mud"]),
                lambda X, Y: 0.5 + 0.5 * noise2(X, Y, 1.0, seed + 2), part="cove")
    back_lot(m, length, 14.0, float(np.max(z(np.linspace(-length / 2, length / 2, 50), np.full(50, 14.0)))), seed, surface="drygrass")
    # Stand-in plants (Track B builds the real ones): cattail blades 1.2-2.4 m with a few heads, rush tufts nearer the
    # bank; the stand is patchy (open water channels), 25 shoots per square metre where it grows.
    xs = np.linspace(-length / 2, length / 2, int(length * 10))
    count = 0
    for x in xs:
        for _ in range(16):
            xx = x + rng.uniform(-0.1, 0.1)
            d = rng.uniform(-4.0, 0.5)
            yy = float(shore_y(np.array(xx))) + d
            zz = float(z(np.array(xx), np.array(yy)))
            if zz < -0.45 or noise2(np.array(xx), np.array(yy), 3.0, seed + 9) < 0.05:
                continue
            h = rng.uniform(1.2, 2.4) * (0.7 if d > -1.0 else 1.0)
            yaw = rng.uniform(0, 2 * math.pi)
            lean = rng.gauss(0, 0.15)
            w = rng.uniform(0.012, 0.022)
            n = 4
            t = np.linspace(0, 1, n)
            cx, cy = math.cos(yaw), math.sin(yaw)
            spine = np.stack([xx + lean * t ** 2 * cx * h * 0.3, yy + lean * t ** 2 * cy * h * 0.3, zz + h * t], 1)
            side = np.array([-cy, cx, 0.0]) * w
            V = np.concatenate([spine - side * (1 - t)[:, None], spine + side * (1 - t)[:, None]])
            F = []
            for i in range(n - 1):
                F += [(i, i + 1, n + i + 1), (i, n + i + 1, n + i)]
            m.add(V, F, col("reed", rng.random()), True, "reeds")
            count += 1
            if rng.random() < 0.12 and d < -0.8:
                hz = zz + h * 0.75
                tube(m, [[xx, yy, hz], [xx, yy, hz + 0.2]], 0.014, "wood", 0.05, sides=6, part="heads")
    debris_line(m, rng, length, z, -6.0, 8.0, 0.15, per_m=4.0, near=10.0)
    return dict(stems=count)


def build_ramp(m, length, rng, seed):
    S = SIZE
    W, slope, t = S["lane_w"], S["ramp_slope"], S["ramp_t"]
    top_y, top_z, bot_z = 6.0, 0.9, -1.6
    bot_y = top_y - (top_z - bot_z) / slope
    # The slab: top surface, edges and the toe, as a grid down the lane (for the run-off on the sides it needs none).
    ny = int((top_y - bot_y) / 0.25) + 1
    ys = np.linspace(bot_y, top_y, ny)
    xs = np.linspace(-W / 2, W / 2, 9)
    X, Y = np.meshgrid(xs, ys)
    Z = top_z - (top_y - Y) * slope
    m.add(np.stack([X, Y, Z], -1).reshape(-1, 3), grid_faces(len(xs), ny), col("ramp", 0.5), False, "slab")
    for sx in (-1, 1):
        V = np.concatenate([np.stack([np.full(ny, sx * W / 2), ys, top_z - (top_y - ys) * slope], 1),
                            np.stack([np.full(ny, sx * W / 2), ys, top_z - (top_y - ys) * slope - t], 1)])
        F = []
        for i in range(ny - 1):
            a = (i, i + 1, ny + i + 1, ny + i)
            F += [(a[0], a[2], a[1]), (a[0], a[3], a[2])] if sx > 0 else [(a[0], a[1], a[2]), (a[0], a[2], a[3])]
        m.add(V, F, col("ramp", 0.4), False, "slab")
    box(m, (0.0, bot_y + 0.02, bot_z - t / 2), (W / 2, 0.02, t / 2), "ramp", 0.4, part="slab")
    # Gravel shoulders a little under the slab's edge, then the natural shore (a low clay bank with dry grass).
    def ground(X, Y):
        along = top_z - (top_y - Y) * slope
        nat = np.where(Y > 1.0, 0.15 + (Y - 1.0) * 0.08, Y * 0.15)
        nat = np.maximum(nat, -1.8 + 0.0 * Y)
        a = np.clip((np.abs(X) - W / 2) / 3.0, 0, 1)
        return (along - 0.12) * (1 - a) + nat * a + 0.02 * noise2(X, Y, 1.0, seed)
    step = 0.15 if length <= 20 else 0.4
    for x0, x1 in ((-length / 2, -W / 2 - 0.02), (W / 2 + 0.02, length / 2)):
        heightfield(m, x0, x1, -16.0, 10.0, step, ground,
                    lambda X, Y, Zz: np.where(np.abs(X) < W / 2 + 2.2, SURF["gravel"], np.where(Zz > 0.3, SURF["drygrass"], SURF["mud"])),
                    lambda X, Y: 0.5 + 0.5 * noise2(X, Y, 1.0, seed + 1), part="shoulders")
    # The top: a flat concrete apron to the parking lot, the lot's gravel and the grass beyond.
    box(m, (0.0, top_y + 3.0, top_z - t / 2), (W / 2 + 1.0, 3.0, t / 2), "ramp", 0.6, part="apron")
    back_lot(m, length, 10.0, float(ground(np.array(-length / 2), np.array(10.0))), seed, surface="drygrass")
    # The lake bed beyond the toe.
    lake_bed(m, W + 0.2, bot_y, bot_z - 0.1, seed, y_far=bot_y - 20.0)
    return dict(lane_w=W, slope_pct=100 * slope, slab_t=t, bottom_below_pool=bot_z)


BUILDERS = dict(bulkhead=build_bulkhead, sheetpile=build_sheetpile, limestone=build_limestone, timber=build_timber,
                claycut=build_claycut, mudflat=build_mudflat, gravel=build_gravel, reedcove=build_reedcove, ramp=build_ramp)


def build(kind, length=16.0, seed=11, pack=None):
    """Build one type with a region pack's sizes (default north-texas-lake): returns (Mesh, measures)."""
    global SIZE
    pack = pack or load_pack()
    if kind not in pack["types"]:
        raise ValueError(f"{kind} is not an edge type of pack {pack['pack']}")
    SIZE = pack["sizes"]
    m = Mesh()
    rng = random.Random(seed * 1009 + TYPES.index(kind))
    measures = BUILDERS[kind](m, length, rng, seed)
    return m, measures


if __name__ == "__main__":
    for k in TYPES:
        mm, meas = build(k)
        print(f"{k:10s} {mm.piece_triangles:8d} piece tris / 16 m ({mm.triangles} with ground)  {mm.part_tris}")
