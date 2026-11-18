"""The frigate's below-decks stores kit (docs/shipkit-stores): the movable things her lower decks fill with, each built
as its own mesh in its own frame for the deck slices to place as linked copies.

    import stores;  kit = stores.Kit();  items = kit.build()        # {name: Item}
    stores.Kit().mess_table(sling_m=1.6)                             # a mess table hung from a beam 1.6 m up

Sizes are stores_1797.json's, each with its source (Falconer's hammock, the navy's cask measures, slice 12's shot, or
the period's practice). Units: metres. Each item's frame: X along its length, Y across, Z up, the origin at the middle
of the face it rests on (z 0 on the deck), or for a hung item (the slung hammock) at the middle between the points it
hangs from. An item is a set of named pieces (each a deck.Part of closed solids facing out, in build_frigate.py's
PAINT materials); the pieces that meet by design are listed under the item in stores_1797.json's meets, and
build_stores.py checks every other pair is clear (deck.room), every solid closed and facing out and no piece crossing
itself. Besides its pieces an item carries its rests (how it lies on the deck: a cask on end or on its bilge), its
attach points (where it hangs or meets the ship) and its slots (where other items go in it: the barrels in the
magazine's rack, the cartridges on their shelves), for the deck slices.

This module needs Blender's mathutils (pip bpy) for the flat faces it fills (tessellate_polygon)."""
import json
import math
import os

import numpy as np

import loft
from deck import Part, vbox
from rigging import tube
from spars import box, unit

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)
GAL = 231.0 * IN ** 3                       # a wine gallon, in cubic metres


# ---- solids ---------------------------------------------------------------------------------------------------------------
def signed_volume(V, F):
    V = np.asarray(V, float)
    s = 0.0
    for f in F:
        for k in range(1, len(f) - 1):
            s += float(np.dot(V[f[0]], np.cross(V[f[k]], V[f[k + 1]])))
    return s / 6.0


def add_solid(part, V, F, mats, uv=None):
    """add a closed solid, its faces turned to face out (by its signed volume); mats one name or one per face"""
    V = np.asarray(V, float)
    F = [tuple(int(i) for i in f) for f in F]
    if signed_volume(V, F) < 0:
        F = [f[::-1] for f in F]
    if isinstance(mats, str):
        part.add(V, F, mats, uv)
        return
    # one add per material, sharing the vertices: Part.add takes a single material, so split the faces by it
    k0 = part.n
    part.V.append(V)
    U = np.zeros((len(V), 4))
    if uv is not None:
        uv = np.asarray(uv, float).reshape(len(V), -1)
        U[:, :uv.shape[1]] = uv
    part.U.append(U)
    part.F += [tuple(k0 + i for i in f) for f in F]
    part.M += list(mats)
    part.n += len(V)


def lathe(part, o, axis, ref, prof, mats, n=24):
    """a closed solid of revolution about axis through o: prof [(h, r)] from one pole (r 0) round to the other, mats one
    per segment (len(prof) - 1) or one name. A ring of radius 0 is a single point. UV: u round the ring (metres at its
    radius), v along the profile (metres)."""
    o, axis, ref = (np.asarray(v, float) for v in (o, axis, ref))
    axis = unit(axis)
    ref = unit(ref - (ref @ axis) * axis)
    b = np.cross(axis, ref)
    if isinstance(mats, str):
        mats = [mats] * (len(prof) - 1)
    th = np.arange(n + 1) * 2 * math.pi / n           # n + 1: the seam doubled for the UVs
    V, U, rings = [], [], []
    s = 0.0
    for k, (h, r) in enumerate(prof):
        if k:
            s += math.hypot(h - prof[k - 1][0], r - prof[k - 1][1])
        if r < 1e-9:
            rings.append([len(V)])
            V.append(o + h * axis)
            U.append((0.0, s))
            continue
        idx = []
        for t in th:
            idx.append(len(V))
            V.append(o + h * axis + r * (math.cos(t) * ref + math.sin(t) * b))
            U.append((t * r, s))
        rings.append(idx)
    F, M = [], []
    for k in range(len(prof) - 1):
        A, B = rings[k], rings[k + 1]
        for i in range(n):
            if len(A) == 1 and len(B) == 1:
                continue
            if len(A) == 1:
                F.append((A[0], B[i + 1], B[i]))
            elif len(B) == 1:
                F.append((A[i], A[i + 1], B[0]))
            else:
                F.append((A[i], A[i + 1], B[i + 1], B[i]))
            M.append(mats[k])
    k0 = part.n
    add_solid(part, np.array(V), F, M, np.array(U))
    if hasattr(part, "seams"):                         # the doubled seam's vertices, to be welded in the exported mesh
        part.seams += [(k0 + R[n], k0 + R[0]) for R in rings if len(R) > 1]


def tessellate(loops):
    """triangles (indices into the loops' points, in order) filling flat 2D loops: the first the outline, the rest holes"""
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    return tessellate_polygon([[Vector((float(p[0]), float(p[1]), 0.0)) for p in L] for L in loops])


def area2(L):
    L = np.asarray(L, float)
    return 0.5 * float(np.sum(L[:, 0] * np.roll(L[:, 1], -1) - np.roll(L[:, 0], -1) * L[:, 1]))


def prism(part, loops, o, a, b, t0, t1, mat):
    """a flat outline (2D loops in the plane of a, b through o: the first the outline, the rest holes) extruded along
    a x b from t0 to t1, its ends filled; a closed solid facing out"""
    o, a, b = (np.asarray(v, float) for v in (o, a, b))
    d = np.cross(a, b)
    loops = [np.asarray(L, float) for L in loops]
    # the outline counter-clockwise, the holes clockwise: each side quad (edge, then along d) then faces out
    loops = [L if (area2(L) > 0) == (k == 0) else L[::-1] for k, L in enumerate(loops)]
    pts = np.concatenate(loops)
    m = len(pts)
    P = o[None] + pts[:, :1] * a[None] + pts[:, 1:2] * b[None]
    V = np.concatenate([P + t0 * d, P + t1 * d])
    F = []
    for tri in tessellate(loops):
        tri = tuple(int(i) for i in tri)
        nz = np.cross(P[tri[1]] - P[tri[0]], P[tri[2]] - P[tri[0]]) @ d
        up = tri if nz > 0 else tri[::-1]
        F.append(tuple(m + i for i in up))                # the t1 end, facing along d
        F.append(up[::-1])                                # the t0 end, facing back
    k = 0
    for L in loops:
        n = len(L)
        for i in range(n):
            i0, i1 = k + i, k + (i + 1) % n
            F.append((i0, i1, m + i1, m + i0))
        k += n
    if t1 < t0:
        F = [f[::-1] for f in F]
    part.add(V, F, mat)


def holed_plate(part, w, h, r, hole_at, t, o, a, b, mat, n=16):
    """a flat plate w (along a) by h (along b) centred at o, t thick (along a x b, centred), with a round hole of radius r
    at hole_at (2D, from the plate's centre)"""
    k = n // 4
    pts = []
    for (ax, ay), (bx, by) in (((w / 2, -h / 2), (w / 2, h / 2)), ((w / 2, h / 2), (-w / 2, h / 2)),
                               ((-w / 2, h / 2), (-w / 2, -h / 2)), ((-w / 2, -h / 2), (w / 2, -h / 2))):
        for i in range(k):
            s = i / k
            pts.append((ax + (bx - ax) * s, ay + (by - ay) * s))
    pts = np.array(pts)
    c = np.asarray(hole_at, float)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    hole = c[None] + r * np.stack([np.cos(ang), np.sin(ang)], 1)
    o, a, b = (np.asarray(v, float) for v in (o, a, b))
    d = unit(np.cross(a, b))
    P = lambda Q, z: o[None] + Q[:, :1] * a[None] + Q[:, 1:2] * b[None] + z * d[None]   # noqa
    V = np.concatenate([P(pts, -t / 2), P(hole, -t / 2), P(pts, t / 2), P(hole, t / 2)])
    F = []
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j, n + i))                              # the back, outline to hole
        F.append((2 * n + i, 3 * n + i, 3 * n + j, 2 * n + j))      # the front
        F.append((i, 2 * n + i, 2 * n + j, j))                      # the edge
        F.append((n + i, n + j, 3 * n + j, 3 * n + i))              # the bore
    # the four kinds wind consistently with each other; turn them all by the solid's volume
    add_solid(part, V, F, mat)


def shell(part, Top, Bot, mat, uv=None):
    """a closed solid between two grids of points (nu, nv, 3): the top, the bottom, and walls round their edges"""
    Top, Bot = np.asarray(Top, float), np.asarray(Bot, float)
    nu, nv = Top.shape[:2]
    V = np.concatenate([Top.reshape(-1, 3), Bot.reshape(-1, 3)])
    off = nu * nv
    ix = lambda i, j: i * nv + j    # noqa
    F = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            # as triangles, the top's and the bottom's split along the same diagonal: a warped cell split two ways
            # would cross itself where the cloth is thinner than its warp
            a, b, c, d = ix(i, j), ix(i + 1, j), ix(i + 1, j + 1), ix(i, j + 1)
            F += [(a, b, c), (a, c, d), (off + c, off + b, off + a), (off + d, off + c, off + a)]
    ring = [(0, j) for j in range(nv)] + [(i, nv - 1) for i in range(1, nu)] + \
           [(nu - 1, j) for j in range(nv - 2, -1, -1)] + [(i, 0) for i in range(nu - 2, 0, -1)]
    for k in range(len(ring)):
        p, q = ring[k], ring[(k + 1) % len(ring)]
        F.append((ix(*p), ix(*q), off + ix(*q), off + ix(*p)))
    # the ring runs against the top's quads' boundary, so each wall meets the top and the bottom the right way; the
    # volume then decides which way is out
    UV = None
    if uv is not None:
        UV = np.concatenate([uv.reshape(-1, 2), uv.reshape(-1, 2)])
    add_solid(part, V, F, mat, UV)


def sphere(part, c, r, mat, n=8, rings=5):
    """a UV sphere: n round, rings from pole to pole (poles included)"""
    prof = [(-r * math.cos(math.pi * k / (rings + 1)), r * math.sin(math.pi * k / (rings + 1))) for k in range(rings + 2)]
    prof[0] = (-r, 0.0)
    prof[-1] = (r, 0.0)
    lathe(part, c, EZ, EX, prof, mat, n)


# ---- the kit ----------------------------------------------------------------------------------------------------------------
class SPart(Part):
    """a deck.Part that also keeps its seams: pairs of vertices (the one doubled for a turned piece's UVs, the one it
    doubles) that are one vertex in the exported mesh, so a turned piece is closed and shades smooth across its seam"""

    def __init__(self):
        super().__init__()
        self.seams = []

    def extend(self, other):
        k0 = self.n
        super().extend(other)
        self.seams += [(k0 + a, k0 + b) for a, b in getattr(other, "seams", [])]


class Item:
    """one stores item: its pieces {name: SPart}; its rests {name: {'turn_deg', 'at_m'}} and slots [{'item', 'name',
    'turn_deg', 'at_m'}], each placed the same way: turned about X, then Y, then Z (degrees, R = Rz Ry Rx), then moved
    to at_m; its attach points {name: [x, y, z]}; whether it stands on the deck; its anchors (where the ship holds a hung
    item, for the held check: ('z', z) a level plane, ('x', x) a plane square to X, ('p', point, r) a point); the card's
    triangle figure it is reported against (budget_key) and its notes"""

    def __init__(self, name, note, stands=True, budget_key="each"):
        self.name, self.note, self.stands, self.budget_key = name, note, stands, budget_key
        self.pieces = {}
        self.rests = {"as_built": {"turn_deg": [0.0, 0.0, 0.0], "at_m": [0.0, 0.0, 0.0]}}
        self.attach, self.slots, self.info, self.anchors = {}, [], {}, []

    def piece(self, name):
        return self.pieces.setdefault(name, SPart())

    def merged(self):
        P = SPart()
        for name in sorted(self.pieces):
            P.extend(self.pieces[name])
        return P

    def box(self):
        V = np.concatenate([np.concatenate(p.V) for p in self.pieces.values() if p.V])
        return V.min(0), V.max(0)


class Kit:
    def __init__(self, path=os.path.join(HERE, "stores_1797.json")):
        self.c = json.load(open(path))

    def build(self):
        items = [self.mess_table(), self.mess_bench(), self.mess_kid(), self.sea_chest(), self.hammock_slung(),
                 self.hammock_lashed(), self.hammock_hook(), self.quoin()]
        items += [self.cask(k) for k in self.c["casks"]["kinds"]]
        items += [self.shot_locker(k) for k in self.c["shot_lockers"]["kinds"]]
        items += [self.magazine_rack(), self.cartridge(), self.cartridge_rack(), self.passing_box(), self.filling_bench(),
                  self.bread_bag()]
        return {it.name: it for it in items}

    # --- the mess ---------------------------------------------------------------------------------------------------------
    def mess_table(self, sling_m=None, sling_y_m=None):
        """a mess table: its top (scrubbed deal), two battens under it, the hinge's cleat at its outboard end (+X: its
        outer face is the ship's side), two strap hinges, and at its inboard end two eyebolts with slings up to two
        eyebolts in the beam over it (sling_m over the deck: the beam's underside; sling_y_m: the eyebolts' and slings'
        distance either side of the table's middle, kept inside the beam's sided breadth; by default 2.5 in in from
        the table's sides)"""
        tb = self.c["mess"]["table"]
        L, W = (v * IN for v in tb["size_in"])
        tt, h = tb["top_in"] * IN, tb["high_in"] * IN
        z_beam = sling_m if sling_m is not None else tb["sling_to_ft"] * FT
        it = Item("MessTable", "a mess of eight's table, hinged to a cleat on the side (+X end, attach 'side') and hung "
                  "by two slings from the beam over it (attach 'beam')", stands=False)
        z0 = h - tt
        vbox(it.piece("Top"), [-L / 2, -W / 2, z0], [L / 2, W / 2, h], "Ash")
        bw, bt = (v * IN for v in tb["batten_in"])
        for x in (-L / 2 + 6.0 * IN, L / 2 - 11.0 * IN):
            vbox(it.piece("Battens"), [x - bw / 2, -W / 2 + 1.0 * IN, z0 - bt], [x + bw / 2, W / 2 - 1.0 * IN, z0], "Ash")
        ch, cd = (v * IN for v in tb["cleat_in"])
        gap = 0.25 * IN                                     # the knuckle's room between the top's end and the cleat
        xc0 = L / 2 + gap
        vbox(it.piece("Cleat"), [xc0, -W / 2 - 2.0 * IN, z0 - ch + 0.5 * IN], [xc0 + cd, W / 2 + 2.0 * IN, z0 + 0.5 * IN],
             "Oak")
        hl, hw, ht = (v * IN for v in tb["hinge_in"])
        rk = 0.3 * IN                                       # the knuckle's pin
        for y in (-W / 2 + 5.0 * IN, W / 2 - 5.0 * IN):
            # one leaf along the top's underside, one down the cleat's face, the knuckle in the corner between
            vbox(it.piece("Hinges"), [L / 2 - hl + 2.0 * IN, y - hw / 2, z0 - ht], [L / 2 - 0.05 * IN, y + hw / 2, z0],
                 "Iron")
            vbox(it.piece("Hinges"), [xc0 - ht, y - hw / 2, z0 - 0.55 * hl], [xc0, y + hw / 2, z0 - 2.0 * rk], "Iron")
            lathe(it.piece("Knuckles"), [L / 2 + gap / 2, y - hw / 2 - 0.2 * IN, z0 - rk], EY, EX,
                  [(0.0, 0.0), (0.0, rk), (hw + 0.4 * IN, rk), (hw + 0.4 * IN, 0.0)], "Iron", 8)
        er, eb = (v * IN for v in tb["eyebolt_in"])
        sr = tb["sling_in"] / 2 * IN
        xi = -L / 2 + 2.5 * IN
        ye = W / 2 - 2.5 * IN if sling_y_m is None else sling_y_m
        for y in (-ye, ye):
            for z_face, up in ((h, 1.0), (z_beam, -1.0)):
                # an eyebolt: a shank into the wood, a collar on its face and the eye standing off it
                lathe(it.piece("Eyebolts"), [xi, y, z_face - up * 1.5 * IN], EZ * up, EX,
                      [(0.0, 0.0), (0.0, eb), (1.5 * IN, eb), (1.5 * IN, 1.5 * eb), (1.5 * IN + 0.15 * IN, 1.5 * eb),
                       (1.5 * IN + 0.15 * IN, eb), (1.5 * IN + 0.4 * IN, eb), (1.5 * IN + 0.4 * IN, 0.0)], "Iron", 8)
                c_eye = np.array([xi, y, z_face + up * (0.4 * IN + er * 0.6 + eb * 0.6)])
                th = np.linspace(0.0, 2 * math.pi, 13)[:-1]
                tube(it.piece("Eyes"), c_eye + np.stack([np.zeros_like(th), np.cos(th) * er * 0.6, np.sin(th) * er * 0.6], 1),
                     eb * 0.9, "Iron", n=6, closed=True)
            # the sling: an eye round the far bar of the table's eye (down one side of the bar, under it through the
            # eye, up the other side and seized to itself), straight up, and an eye round the near bar of the beam's
            ra = eb * 0.9 + sr * 0.85                          # the sling's centreline round a bar, bearing on it
            ca = np.array([xi, y, h + 0.4 * IN + 2 * er * 0.6 + eb * 0.6])          # the table eye's top bar
            cb = np.array([xi, y, z_beam - 0.4 * IN - 2 * er * 0.6 - eb * 0.6])     # the beam eye's bottom bar
            lo_eye = [ca + ra * np.array([math.cos(a), 0.0, -math.sin(a)]) for a in np.linspace(0.0, math.pi, 7)]
            hi_eye = [cb + ra * np.array([-math.cos(a), 0.0, math.sin(a)]) for a in np.linspace(0.0, math.pi, 7)]
            path = [lo_eye[-1] + EZ * 1.2 * IN] + lo_eye[::-1] + [ca + EX * ra + EZ * 1.5 * IN,
                                                                   cb - EX * ra - EZ * 1.5 * IN] + hi_eye
            path += [hi_eye[-1] - EZ * 1.2 * IN]
            # the two legs of each eye lie side by side: the returning end a sling's breadth off the standing part
            tube(it.piece("Slings"), np.array(path), sr, "Hemp", n=6)
        it.attach = {"side": [xc0 + cd, 0.0, z0 - ch / 2], "beam": [xi, 0.0, z_beam]}
        it.anchors = [("x", xc0 + cd), ("z", z_beam)]
        it.info = {"sling_m": round(z_beam, 4), "top_m": round(h, 4), "seats": 8}
        return it

    def mess_bench(self):
        """a mess form: its top, two legs (a notch cut up from each foot) and a rail between them under the top"""
        bc = self.c["mess"]["bench"]
        L, W = (v * IN for v in bc["size_in"])
        tt, h = bc["top_in"] * IN, bc["high_in"] * IN
        it = Item("MessBench", "a mess form for four men, standing on the deck")
        vbox(it.piece("Top"), [-L / 2, -W / 2, h - tt], [L / 2, W / 2, h], "Ash")
        lw, lt = (v * IN for v in bc["leg_in"])
        nw, nh = (v * IN for v in bc["notch_in"])
        xl = L / 2 - bc["leg_from_end_in"] * IN
        outline = np.array([[-lw / 2, 0.0], [-nw / 2, 0.0], [0.0, nh], [nw / 2, 0.0], [lw / 2, 0.0], [lw / 2, h - tt],
                            [-lw / 2, h - tt]])
        for x in (-xl, xl):
            prism(it.piece("Legs"), [outline], [x, 0.0, 0.0], EY, EZ, -lt / 2, lt / 2, "Ash")
        rh, rt = (v * IN for v in bc["rail_in"])
        vbox(it.piece("Rail"), [-xl - lt / 2 - 0.5 * IN, -rt / 2, h - tt - rh], [xl + lt / 2 + 0.5 * IN, rt / 2, h - tt],
             "Ash")
        it.info = {"seats": 4}
        return it

    def mess_kid(self):
        """a mess kid: a staved tub, wider at the foot, two iron hoops, a bottom let in, and two ears (staves standing up
        over the rim) each with a hole to lift it by"""
        kc = self.c["mess"]["kid"]
        rt, rb, H = kc["top_in"] / 2 * IN, kc["bottom_in"] / 2 * IN, kc["high_in"] * IN
        st, bb = kc["stave_in"] * IN, kc["bottom_board_in"] * IN
        th = kc["hoop_in"] * IN
        it = Item("MessKid", "a mess kid (a tub for the mess's food), standing on the deck")
        r = lambda z: rb + (rt - rb) * z / H    # noqa
        chime = 0.5 * IN
        prof = [(chime, 0.0), (chime, r(chime) - st), (0.0, r(0.0) - st)]
        mats = ["Oak", "Oak"]
        hoops = sorted(kc["hoops"])
        prof.append((0.0, r(0.0)))
        mats.append("Oak")
        for zc, w in hoops:
            z0, z1 = (zc - w / 2) * IN, (zc + w / 2) * IN
            prof += [(z0, r(z0)), (z0, r(z0) + th), (z1, r(z1) + th), (z1, r(z1))]
            mats += ["Oak", "Oak", "Iron", "Iron"]
        prof += [(H, r(H)), (H, r(H) - st), (chime + bb, r(chime + bb) - st), (chime + bb, 0.0)]
        mats += ["Oak", "Oak", "Oak", "Oak"]
        mats = mats[:len(prof) - 1]
        lathe(it.piece("Tub"), [0.0, 0.0, 0.0], EZ, EX, prof, mats, 24)
        ew, eh, et = (v * IN for v in kc["ear_in"])
        hr = kc["ear_hole_in"] / 2 * IN
        down = 1.5 * IN                                    # how far each ear runs down inside the wall
        for s in (-1.0, 1.0):
            # the ear stands in the wall's middle at the rim, its face square to Y
            zc = H + (eh - down) / 2
            yc = s * (r(H) - st / 2)
            holed_plate(it.piece("Ears"), ew, eh + down, hr, (0.0, (eh + down) / 2 - eh / 2), et * 0.9,
                        [0.0, yc, zc], EX, EZ, "Oak", 16)
        it.info = {"holds_gal": round(math.pi * H / 3 * (r(0) ** 2 + r(0) * r(H) + r(H) ** 2) / GAL, 1)}
        return it

    # --- the sea chest ----------------------------------------------------------------------------------------------------
    def sea_chest(self):
        """a seaman's chest: its body (front and back leaning in to the lid), the plinth round its foot, the lid and its
        skirt, a cleat on each end with a rope becket through it, the hasp"""
        cc = self.c["chest"]
        Lf, Df = (v * IN for v in cc["foot_in"])
        Lt, Dt = (v * IN for v in cc["top_in"])
        H = cc["high_in"] * IN
        lt, lo, ls = (v * IN for v in cc["lid_in"])
        it = Item("SeaChest", "a seaman's chest, standing on the deck, its length along X, its front to +Y")
        zb = H - lt                                        # the body's top, under the lid
        depth = lambda z: Df + (Dt - Df) * z / zb          # noqa  the body's depth at height z (it leans in front and back)

        def ring(z, grow=0.0):
            d = depth(z) / 2 + grow
            l_ = Lf / 2 + grow
            return np.array([[-l_, -d, z], [l_, -d, z], [l_, d, z], [-l_, d, z]])
        from deck import solid
        solid(it.piece("Body"), [ring(0.0), ring(zb)], "Interior")
        ph, pp = (v * IN for v in cc["plinth_in"])
        outer = lambda z, g: ring(z, g)[:, :2]                 # noqa
        prism(it.piece("Plinth"), [outer(0.0, pp), outer(ph, -0.02 * IN)[::-1]], [0.0, 0.0, 0.0], EX, EY, 0.0, ph,
              "Interior")
        # the lid: a board overhanging the body by lo all round, its skirt hanging down round the body's top
        prism(it.piece("Lid"), [outer(zb, lo)], [0.0, 0.0, 0.0], EX, EY, zb, H, "Interior")
        prism(it.piece("LidSkirt"), [outer(zb, lo), outer(zb - ls, -0.02 * IN)[::-1]], [0.0, 0.0, 0.0], EX, EY, zb - ls, zb,
              "Interior")
        # the cleats and beckets on the ends
        cl, ct, chh = (v * IN for v in cc["cleat_in"])
        br, bl, bd = (v * IN for v in cc["becket_in"])
        zc = 0.62 * zb
        for s in (-1.0, 1.0):
            x0 = s * Lf / 2
            vbox(it.piece("Cleats"), [min(x0, x0 + s * ct), -cl / 2, zc - chh / 2], [max(x0, x0 + s * ct), cl / 2, zc + chh / 2],
                 "Oak")
            # the becket: out of the cleat's face at two holes, down and round in a loop
            xo = x0 + s * (ct + 0.5 * IN)
            pts = [[x0 + s * (ct - 0.6 * IN), -bl / 2, zc]]
            for t in np.linspace(0.0, math.pi, 9):
                pts.append([xo + s * 0.4 * IN * math.sin(t), -bl / 2 * math.cos(t), zc - bd * math.sin(t)])
            pts.append([x0 + s * (ct - 0.6 * IN), bl / 2, zc])
            tube(it.piece("Beckets"), np.array(pts), br, "Hemp", n=6)
        # the hasp down the front from the lid's skirt, and the staple through it
        hw, hl, ht = (v * IN for v in cc["hasp_in"])
        zt, zl = zb - ls + 0.5 * IN, zb - ls - hl + 1.0 * IN
        yf = lambda z: depth(z) / 2                         # noqa
        nrm = unit(np.array([0.0, 1.0, (Df - Dt) / 2 / zb]))
        # a plate lying on the front face from below the skirt up under it
        c = np.array([0.0, yf(0.5 * (zl + zt)), 0.5 * (zl + zt)]) + nrm * (ht / 2 - 0.02 * IN)
        up = unit(np.array([0.0, yf(zt) - yf(zl), zt - zl]))
        box(it.piece("Hasp"), c, EX, nrm, up, hw / 2, ht / 2, (zt - zl) / 2, "Iron")
        zs = zl + 1.0 * IN
        c = np.array([0.0, yf(zs), zs]) + nrm * (ht + 0.25 * IN)
        th = np.linspace(0.0, math.pi, 7)
        staple = [c - nrm * 0.45 * IN + EX * 0.4 * IN] + [c + nrm * 0.25 * IN * math.sin(t) + EX * 0.4 * IN * math.cos(t)
                                                          for t in th] + [c - nrm * 0.45 * IN - EX * 0.4 * IN]
        tube(it.piece("Staple"), np.array(staple), 0.09 * IN, "Iron", n=6)
        it.info = {"holds_cuft": round((Lf * zb * 0.5 * (Df + Dt)) / FT ** 3, 1)}
        return it

    # --- the hammocks ---------------------------------------------------------------------------------------------------
    def hammock_slung(self, span_ft=None):
        """Falconer's hammock slung lengthways (X) between two hooks span_ft apart (attach 'hook_aft', 'hook_fore', z 0
        there: the hooks' bights): the cloth hanging in a trough (its sides drawn up by the clews), the bed lying in it,
        at each end the nettles from grommets along the cloth's end to an iron ring, and the lanyard from the ring to
        the hook (the clews made shorter where the hooks are too close for the card's: info clew_m)"""
        hc = self.c["hammock"]
        L, W = (v * FT for v in hc["cloth_ft"])
        span = (span_ft or hc["span_ft"]) * FT
        t = hc["cloth_in"] * IN
        sag, drop = hc["sag_in"] * IN, hc["drop_in"] * IN
        c_end, c_mid = (v * IN for v in hc["chord_in"])
        it = Item("HammockSlung", "a hammock slung between two hooks (hung: its origin midway between the hooks' bights)",
                  stands=False, budget_key="hammock")
        Lx = L * 0.985                                    # its length along X, a little under the cloth's for the sag
        nu, nv = 17, 11
        xs = np.linspace(-Lx / 2, Lx / 2, nu)

        def alpha(c, We=W):                               # the half angle of a circular arc We long on a chord c
            lo, hi = 1e-4, math.pi - 1e-4
            for _ in range(60):
                m = 0.5 * (lo + hi)
                if math.sin(m) / m > c / We:
                    lo = m
                else:
                    hi = m
            return 0.5 * (lo + hi)

        def section(x, frac):
            """the cloth's point at x and frac (-1..1 across), and the normal into the trough"""
            q = (2 * x / Lx) ** 2
            c = c_end + (c_mid - c_end) * (1.0 - q)
            We = W * (1.0 - hc["gather"] * q ** 2)         # the cloth gathered toward its ends by the nettles
            a = alpha(c, We)
            R = We / (2 * a)
            zc = -drop - sag * (1.0 - q)
            ph = frac * a
            P = np.array([x, R * math.sin(ph), zc + R * (1.0 - math.cos(ph))])
            N = np.array([0.0, -math.sin(ph), math.cos(ph)])
            return P, N
        fr = np.linspace(-1.0, 1.0, nv)
        Top = np.zeros((nu, nv, 3))
        Nm = np.zeros((nu, nv, 3))
        for i, x in enumerate(xs):
            for j, f in enumerate(fr):
                Top[i, j], Nm[i, j] = section(x, f)
        # the cloth's true normal (its rows' and columns' tangents crossed), turned into the trough: at the ends the
        # cloth turns along X too, and an offset square to the section alone would fold its thin edge
        Tu = np.gradient(Top, axis=0)
        Tv = np.gradient(Top, axis=1)
        Ng = np.cross(Tu, Tv)
        Ng /= np.linalg.norm(Ng, axis=2, keepdims=True)
        Ng *= np.sign(np.sum(Ng * Nm, axis=2, keepdims=True))
        Nm = Ng
        uv = np.stack(np.meshgrid(np.linspace(0, L, nu), np.linspace(0, W, nv), indexing="ij"), -1)
        shell(it.piece("Cloth"), Top, Top - Nm * t, "Canvas", uv)
        # the bed: from bed.in_from_ends_in inside each end, across the middle 'across' of the cloth, its underside on the
        # cloth (a hair into it), thickest along the middle
        bd = hc["bed"]
        e = bd["in_from_ends_in"] * IN
        bu, bv = 15, 9
        bxs = np.linspace(-Lx / 2 + e, Lx / 2 - e, bu)
        Bb = np.zeros((bu, bv, 3))
        Bt = np.zeros((bu, bv, 3))
        for i, x in enumerate(bxs):
            qx = (2 * x / (Lx - 2 * e)) ** 2
            across = bd["across"] * (0.7 + 0.3 * math.sqrt(max(0.0, 1.0 - qx ** 2)))    # its ends rounded in plan
            for j, f in enumerate(np.linspace(-1.0, 1.0, bv)):
                P, N = section(x, f * across)
                k = (1.0 - f ** 2) ** 0.5 * (1.0 - qx) ** 0.6                           # and in section and length
                Bb[i, j] = P - N * 0.03 * IN
                Bt[i, j] = P + N * (0.1 * IN + (bd["thick_in"] * IN - 0.1 * IN) * k)
        shell(it.piece("Bed"), Bt, Bb, bd["material"])
        # the clews: nettles from grommets 1 in inside the cloth's end to the ring, on the line from the end's middle to
        # the hook; then the lanyard on that line to the hook's bight
        n = hc["nettles"]
        nr = hc["nettle_in"] / 2 * IN
        rr, rb = hc["ring_in"][0] / 2 * IN, hc["ring_in"][1] / 2 * IN
        ly = hc["lanyard_in"] / 2 * IN
        hooks = {}
        clews = []
        for s, tag in ((-1.0, "aft"), (1.0, "fore")):
            xe = s * Lx / 2
            P_end, _ = section(xe, 0.0)
            P_end = P_end + EZ * (W * (1 - hc["gather"]) / (2 * alpha(c_end, W * (1 - hc["gather"])))) * 0.35        # the end's middle, part way up its arc
            hook = np.array([s * span / 2, 0.0, 0.0])
            d = unit(hook - P_end)
            # the clews as the card has them, or shorter where the hooks are closer than the cloth, the clews and the
            # lanyard's least length allow (its ring would hang at or past the hook)
            clew = min(hc["clew_ft"] * FT, float(np.linalg.norm(hook - P_end)) - rr - hc["lanyard_least_in"] * IN)
            if clew < 0.5 * hc["clew_ft"] * FT:
                raise SystemExit(f"stores: hooks {span:.3f} m apart leave the hammock's clews {clew / IN:.1f} in long, "
                                 "under half the card's")
            clews.append(clew)
            ring_c = P_end + d * clew
            # the ring in the plane of the hang (x, z), its near side toward the cloth
            a1 = d
            a2 = EY
            th = np.linspace(0.0, 2 * math.pi, 17)[:-1]
            tube(it.piece("Rings"), ring_c[None] + rr * (np.cos(th)[:, None] * a1[None] + np.sin(th)[:, None] *
                                                         np.cross(a2, a1)[None]), rb, "Iron", n=6, closed=True)
            # the nettles gathered into the clew at the ring's near side: each ends on a small circle round the hang's
            # line there, at its grommet's own angle round that line, so they fan out to the cloth without crossing; a
            # seizing of spun yarn binds them round the ring's bar. At the cloth each runs through its grommet and is
            # knotted under the cloth
            e1 = EY
            e2 = unit(np.cross(d, EY))
            Qc = ring_c - d * rr * 0.75
            fan = hc["clew_fan_in"] / 2 * IN
            for k_ in range(n):
                f = -1.0 + 2.0 * k_ / (n - 1)
                # the grommet on the cloth as built (its grid and true normals, which tilt along X at the gathered end):
                # the nettle starts in the middle of the cloth's thickness and runs out through it
                gu = (xe - s * 1.0 * IN + Lx / 2) / Lx * (nu - 1)
                gv = (f * 0.96 + 1.0) / 2 * (nv - 1)
                i0, j0 = min(int(gu), nu - 2), min(int(gv), nv - 2)
                du, dv = gu - i0, gv - j0
                w = [(i0, j0, (1 - du) * (1 - dv)), (i0 + 1, j0, du * (1 - dv)), (i0, j0 + 1, (1 - du) * dv),
                     (i0 + 1, j0 + 1, du * dv)]
                Pt = sum(Top[a_, b_] * w_ for a_, b_, w_ in w)
                Nt = unit(sum(Nm[a_, b_] * w_ for a_, b_, w_ in w))
                P = Pt - Nt * t / 2
                v = P - P_end
                ang = math.atan2(float(v @ e2), float(v @ e1))
                Q = Qc + fan * (math.cos(ang) * e1 + math.sin(ang) * e2)
                tube(it.piece("Nettles_" + tag), np.array([P, P + 0.5 * (Q - P), Q]), nr, "Hemp", n=4)
            sl = hc["seizing_in"] * IN
            sz = fan + nr + 0.04 * IN
            lathe(it.piece("Seizing"), Qc - d * sl, d, e1, [(0.0, 0.0), (0.0, sz), (sl, sz), (sl, 0.0)], "Tarred", 10)
            # the lanyard: from the ring to the hook, an eye round the hook's bar there (the bar runs along X at the
            # hook's bight, which is the lanyard's centreline under the bar: the bar's axis is bar_r + the lanyard's
            # radius over it), its end seized back along the lanyard
            q0 = ring_c + d * rr
            hb = self.c["hammock"]["hook"]["bar_in"] / 2 * IN
            cbar = hook + EZ * (hb + ly)
            ra = hb + ly * 0.85
            eye = [cbar + ra * np.array([0.0, math.cos(a), math.sin(a)])
                   for a in np.linspace(-math.pi / 2, 1.5 * math.pi - 0.75, 12)]
            tail = eye[-1] - d * 1.2 * IN - EY * 0.12 * IN
            tube(it.piece("Lanyards"), np.array([q0 - d * rb * 0.5, hook - d * 0.6 * IN] + eye + [tail]), ly, "Hemp", n=6)
            hooks["hook_" + tag] = hook.tolist()
            it.anchors.append(("p", cbar.tolist(), hb + 2.5 * ly))
        it.attach = hooks
        it.info = {"span_m": round(span, 4), "lowest_m": round(float(Top[nu // 2, nv // 2, 2]), 4),
                   "clew_m": round(min(clews), 4),
                   "note": "the slung hammock with its bed: about 14 to 20 in of the beam's length a man (Falconer)"}
        return it

    def hammock_lashed(self):
        """a hammock lashed up for stowing: the cloth rolled round the bed (a long round body, its ends rounded and drawn
        in), seven turns of the lashing round it and the lashing's run along its top from turn to turn; lying on the deck
        along X"""
        hl = self.c["hammock"]["lashed"]
        L, D = hl["length_in"] * IN, hl["across_in"] * IN
        R = D / 2
        tr = hl["turn_in"] / 2 * IN
        nt = hl["turns"]
        it = Item("HammockLashed", "a hammock lashed up for stowing (in the nettings by day), lying along X",
                  budget_key="hammock")
        xs_t = np.linspace(-L / 2 + 0.09 * L, L / 2 - 0.09 * L, nt)
        nip = 0.35 * IN                                    # how far each turn draws the roll in under it
        def r_at(x):                                       # noqa  the roll's radius: drawn in under each turn
            d = np.min(np.abs(xs_t - x))
            w = 1.8 * IN
            return R - nip * math.exp(-(d / w) ** 2)
        prof = [(-L / 2, 0.0), (-L / 2, 0.45 * R), (-L / 2 + 0.6 * IN, 0.78 * R), (-L / 2 + 2.0 * IN, 0.96 * R)]
        # the roll between its ends: a ring at each turn (drawn in) and one midway between turns (full)
        xs = sorted(set(np.round(np.concatenate([xs_t, 0.5 * (xs_t[1:] + xs_t[:-1]),
                                                 [-L / 2 + 3.5 * IN, L / 2 - 3.5 * IN]]), 6)))
        prof += [(x, r_at(x)) for x in xs]
        prof += [(L / 2 - 2.0 * IN, 0.96 * R), (L / 2 - 0.6 * IN, 0.78 * R), (L / 2, 0.45 * R), (L / 2, 0.0)]
        lift = R
        lathe(it.piece("Roll"), [0.0, 0.0, lift], EX, EZ, prof, "Canvas", 16)
        th = np.linspace(0.0, 2 * math.pi, 17)[:-1]
        tops = []
        for x in xs_t:
            rc = r_at(x) + tr * 0.55
            tube(it.piece("Turns"), np.stack([np.full_like(th, x), rc * np.sin(th), lift + rc * np.cos(th)], 1), tr, "Hemp",
                 n=5, closed=True)
            tops.append(np.array([x, 0.0, lift + rc]))
        for a, b in zip(tops[:-1], tops[1:]):
            # the run from one turn's top to the next, over the roll, starting and ending in the turns (its hitches)
            m = 0.5 * (a + b)
            m[2] = lift + r_at(m[0]) + tr * 0.6
            tube(it.piece("Run"), np.array([a + EX * tr * 0.3, m, b - EX * tr * 0.3]), tr * 0.95, "Hemp", n=5)
        # it lies on its turns: lift it so the lowest point of everything is on the deck
        zmin = min(float(np.concatenate(p.V)[:, 2].min()) for p in it.pieces.values())
        for p in it.pieces.values():
            for V in p.V:
                V[:, 2] -= zmin
        return it

    def hammock_hook(self):
        """a hammock hook: an iron plate screwed to the beam's underside (z 0 its top, the beam's underside) and a hook
        hanging from it; attach 'bight': where a lanyard's eye round the hook's bar has its centreline just under the
        bar (the bar's axis is bar_m + the lanyard's radius over it: hammock_slung's cbar)"""
        hk = self.c["hammock"]["hook"]
        pl, pw, pt = (v * IN for v in hk["plate_in"])
        br = hk["bar_in"] / 2 * IN
        dr = hk["drop_in"] * IN
        th_ = hk["throat_in"] * IN
        it = Item("HammockHook", "a hammock hook, screwed under a beam (z 0: the beam's underside)", stands=False)
        vbox(it.piece("Plate"), [-pl / 2, -pw / 2, -pt], [pl / 2, pw / 2, 0.0], "Iron")
        for x in (-pl / 2 + 0.5 * IN, pl / 2 - 0.5 * IN):          # the screws' heads
            lathe(it.piece("Screws"), [x, 0.0, -pt - 0.12 * IN], EZ, EX, [(0.0, 0.0), (0.0, 0.25 * IN), (0.12 * IN, 0.25 * IN),
                                                                     (0.2 * IN, 0.0)], "Iron", 8)
        rc = th_ / 2 + br                                  # the bend's centreline radius
        pts = [[0.0, 0.0, -pt + 0.15 * IN], [0.0, 0.0, -dr + rc]]
        for a in np.linspace(0.0, math.radians(200.0), 11)[1:]:
            pts.append([rc - rc * math.cos(a), 0.0, -dr + rc - rc * math.sin(a)])
        tube(it.piece("Hook"), np.array(pts), br, "Iron", n=8)
        lr = self.c["hammock"]["lanyard_in"] / 2 * IN
        it.attach = {"bight": [rc, 0.0, -dr - br - lr], "bar": [rc, 0.0, -dr]}
        it.anchors = [("z", 0.0)]
        it.info = {"bar_m": round(br, 5), "note": "the bar runs along X at the bight, its axis at 'bar'; a lanyard's eye "
                                                 "round it passes under the bar with its centreline at 'bight'"}
        return it

    # --- casks --------------------------------------------------------------------------------------------------------------
    def cask_size(self, kind):
        """a cask's bilge and head diameters and its length (m), so that its inside holds the kind's gallons"""
        ck = self.c["casks"]
        k = ck["kinds"][kind]
        st, ch = ck["stave_in"] * IN, ck["chime_in"] * IN
        head = st                                           # the heads as thick as the staves

        def inside(D):
            L = k["L_over_D"] * D
            d = k["head_over_D"] * D
            Li, Di, di = L - 2 * (ch + head), D - 2 * st, d - 2 * st
            return math.pi * Li / 12.0 * (2 * Di ** 2 + di ** 2)
        gal_m3 = ck["measures_in3"][k["measure"]] * IN ** 3
        lo, hi = 0.05, 3.0
        for _ in range(80):
            m = 0.5 * (lo + hi)
            if inside(m) < k["gal"] * gal_m3:
                lo = m
            else:
                hi = m
        D = 0.5 * (lo + hi)
        return D, k["head_over_D"] * D, k["L_over_D"] * D, inside(D) / gal_m3

    def hoops(self, L):
        """the hoops [(middle, width)] (m) on a cask L long: each at its card's place, the chime hoops held in by half their
        width, and each kept at least half an inch clear of the one before it (on a short cask the quarter hoops move
        toward the bilge)"""
        out, prev = [], -1.0
        hs = self.c["casks"]["hoops_at"]
        for k, (f, w) in enumerate(hs):
            w = w * IN
            zc = min(max(f * L, w / 2), L - w / 2)
            if k < len(hs) / 2:
                zc = max(zc, prev + 0.5 * IN + w / 2) if prev > 0 else zc
            out.append([zc, w])
            prev = zc + w / 2
        # the after half mirrors the fore half
        n = len(out)
        for k in range(n // 2, n):
            out[k][0] = L - out[n - 1 - k][0]
        return [tuple(h) for h in out]

    def cask(self, kind):
        """a cask standing on end (rest 'on_end'; 'on_bilge' lays it along X on its bilge hoops): its staves bellied to
        the bilge with the hoops raised on them, the heads let in at the chimes, its bung in the bung stave"""
        ck = self.c["casks"]
        k = ck["kinds"][kind]
        D, d, L, gal = self.cask_size(kind)
        st, ch, th = ck["stave_in"] * IN, ck["chime_in"] * IN, ck["hoop_in"] * IN
        it = Item("Cask_" + kind if kind != "PowderBarrel" else "PowderBarrel",
                  f"a {kind.lower()}: {k['use']}" if kind != "PowderBarrel" else "a powder barrel: " + k["use"],
                  budget_key="cask")
        rb, rh = D / 2, d / 2
        r = lambda z: rh + (rb - rh) * (1.0 - (2 * z / L - 1.0) ** 2)     # noqa
        hoops = self.hoops(L)
        prof = [(ch, 0.0), (ch, rh - st), (0.0, rh - st)]
        mats = ["Oak", "Oak"]
        z = 0.0
        # out along the foot to the hoop's face, then up the side: hoops raised th, bare staves between them (each run
        # of bare stave in short steps to follow its belly)
        first = True
        for zc, w in hoops:
            z0, z1 = zc - w / 2, zc + w / 2
            if first and z0 <= 1e-9:
                prof.append((0.0, r(0.0) + th))
                mats.append("Oak")
            else:
                steps = max(1, int(math.ceil((z0 - z) / (3.0 * IN))))
                for s_ in range(1, steps + 1):
                    zz = z + (z0 - z) * s_ / steps
                    prof.append((zz, r(zz)))
                    mats.append("Oak")
                prof.append((z0, r(z0) + th))
                mats.append(k["hoop"])
            first = False
            zm = 0.5 * (z0 + z1)
            prof += [(zm, r(zm) + th), (z1, r(z1) + th)]
            mats += [k["hoop"], k["hoop"]]
            if z1 < L - 1e-9:
                prof.append((z1, r(z1)))
                mats.append(k["hoop"])
            z = z1
        prof += [(L, rh - st), (L - ch, rh - st), (L - ch, 0.0)]
        mats += ["Oak", "Oak", "Oak"]
        lathe(it.piece("Cask"), [0.0, 0.0, 0.0], EZ, EX, prof, mats, 24)
        if not k.get("no_bung"):
            br, bp = ck["bung_in"][0] / 2 * IN, ck["bung_in"][1] * IN
            zc = 0.5 * L
            lathe(it.piece("Bung"), [rb - 0.6 * IN, 0.0, zc], EX, EY, [(0.0, 0.0), (0.0, br * 0.9), (0.6 * IN + bp - 0.1 * IN, br),
                                                                     (0.6 * IN + bp, br - 0.1 * IN), (0.6 * IN + bp, 0.0)],
                  "Oak", 10)
        # lying on its side it bears on whatever stands out most: the bare bilge between the bilge hoops, or a hoop
        r_out = max(r_ for _h, r_ in prof)
        it.rests["on_end"] = it.rests.pop("as_built")
        it.rests["on_bilge"] = {"turn_deg": [0.0, -90.0, 0.0], "at_m": [round(L / 2, 5), 0.0, round(r_out, 5)],
                                "note": "turned about Y so its length runs along X (centred on 0) with the bung up, and "
                                        "lifted so it bears on the deck at its widest (bilge or bilge hoop); the deck "
                                        "slice turns it about Z to lie fore and aft or athwart, and chocks it with quoins "
                                        "(Quoin)"}
        it.info = {"bilge_m": round(D, 4), "head_m": round(d, 4), "length_m": round(L, 4), "gal": round(gal, 1),
                   "hoops_m": [[round(zc, 4), round(w, 4), round(r(zc) + th, 4)] for zc, w in hoops],
                   "card_gal": k["gal"], "measure": k["measure"], "over_hoops_m": round(2 * r_out, 4)}
        return it

    def quoin(self):
        """an oak quoin: a wedge to chock a cask lying on its bilge, its toe under the cask"""
        q = self.c["casks"]["quoin"]
        L, W, H = (v * IN for v in q["size_in"])
        it = Item("Quoin", "a quoin, its toe to +X (under the cask)")
        outline = np.array([[-L / 2, 0.0], [L / 2, 0.0], [L / 2, 0.6 * IN], [-L / 2, H]])
        prism(it.piece("Wedge"), [outline], [0.0, 0.0, 0.0], EX, EZ, -W / 2, W / 2, "Oak")
        return it

    # --- shot lockers -----------------------------------------------------------------------------------------------------
    def shot_locker(self, kind):
        """a bay of shot locker: corner posts, planked back (-Y) and ends, loose boards dropped into the posts' grooves
        across the front (+Y), the shot heaped inside (the top layer's shot sunk into the heap's top)"""
        sc = self.c["shot_lockers"]
        sk = sc["kinds"][kind]
        Wx, Wy, H = (v * IN for v in sc["inside_in"])
        ps, pt = sc["post_in"] * IN, sc["plank_in"] * IN
        it = Item(kind, f"a bay of the hold's shot lockers ({sk['note']}), its front to +Y")
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                cx, cy = sx * (Wx / 2 + ps / 2), sy * (Wy / 2 + ps / 2)
                vbox(it.piece("Posts"), [cx - ps / 2, cy - ps / 2, 0.0], [cx + ps / 2, cy + ps / 2, H], "Oak")
        gap = 1.0 / 16 * IN
        nb = int(math.ceil(H / (11.0 * IN)))
        bh = (H - (nb - 1) * gap) / nb
        for k in range(nb):
            z0 = k * (bh + gap)
            vbox(it.piece("Back"), [-Wx / 2, -Wy / 2 - pt, z0], [Wx / 2, -Wy / 2, z0 + bh], "Oak")
            for sx in (-1.0, 1.0):
                x0 = sx * Wx / 2
                vbox(it.piece("Ends"), [min(x0, x0 + sx * pt), -Wy / 2, z0], [max(x0, x0 + sx * pt), Wy / 2, z0 + bh],
                     "Oak")
        bdh, bdt = (v * IN for v in sc["board_in"])
        gv = sc["groove_in"] * IN
        fill = sc["fill_in"] * IN
        # the heap: up to the top layer's shot, sunk into it 0.35 of a shot
        sd = sk["shot_in"] * IN
        sr = sd / 2
        nx, ny = int(Wx // sd), int(Wy // sd)
        top = fill - sc["fill_under_top_in"] * IN
        heap_top = top - 0.65 * sd
        # the boards dropped in one above another up to the top shot, the last one cut down to it
        z, nbd = 0.0, 0
        while z < top - 1e-6:
            h = min(bdh, top - z)
            vbox(it.piece("Boards"), [-Wx / 2 - gv, Wy / 2, z], [Wx / 2 + gv, Wy / 2 + bdt, z + h], "Oak")
            z += h + sc["board_gap_in"] * IN
            nbd += 1
        boards_top = z - sc["board_gap_in"] * IN
        assert boards_top >= top - 1e-6, (kind, boards_top, top)
        vbox(it.piece("Heap"), [-Wx / 2 + 0.1 * IN, -Wy / 2 + 0.1 * IN, 0.0], [Wx / 2 - 0.1 * IN, Wy / 2 - 0.1 * IN, heap_top],
             "Iron")
        px, py = Wx / nx, Wy / ny
        rng = np.random.default_rng(1797)
        for i in range(nx):
            for j in range(ny):
                c = [-Wx / 2 + px * (i + 0.5) + rng.uniform(-0.15, 0.15) * (px - sd),
                     -Wy / 2 + py * (j + 0.5) + rng.uniform(-0.15, 0.15) * (py - sd),
                     top - sr - rng.uniform(0.0, 0.08) * sd]
                # only the shot's top shows: a cap cut 0.1 in down into the heap
                zc = heap_top - 0.1 * IN - c[2]
                prof = [(zc, 0.0), (zc, math.sqrt(sr * sr - zc * zc))]
                a0 = math.asin(zc / sr)
                prof += [(sr * math.sin(a), sr * math.cos(a)) for a in np.linspace(a0, math.pi / 2, 5)[1:-1]]
                prof.append((sr, 0.0))
                lathe(it.piece("Shot"), c, EZ, EX, prof, "Blacking", 10)
        it.info = {"shot_in": sk["shot_in"], "shot_shown": nx * ny,
                   "holds_shot": int(nx * ny * (fill / sd) * 1.15), "boards": nbd,
                   "boards_top_m": round(boards_top, 4), "shot_top_m": round(top, 4)}
        return it

    # --- the magazine ------------------------------------------------------------------------------------------------------
    def magazine_rack(self):
        """the magazine's barrel rack: two tiers of powder barrels lying on their bilges along X (their heads to +-Y),
        each on two oak chocks hollowed to its bilge hoops, the chocks on bearers along the rack, the upper tier's
        bearers on uprights; the barrels are slots (PowderBarrel, rest on_bilge turned to lie athwart)"""
        mc = self.c["magazine"]["rack"]
        D, d, L, _ = self.cask_size("PowderBarrel")
        ck = self.c["casks"]
        th = ck["hoop_in"] * IN
        it = Item("MagazineRack", "the magazine's rack for eight barrels of powder (slots: PowderBarrel)")
        rb, rh = D / 2, d / 2
        r = lambda z: rh + (rb - rh) * (1.0 - (2 * z / L - 1.0) ** 2)    # noqa
        hoops = self.hoops(L)
        bilge = [h for h in hoops if 0.2 * L < h[0] < 0.8 * L]
        nb, nt = mc["barrels"], mc["tiers"]
        gap = mc["gap_in"] * IN
        bw, bh = (v * IN for v in mc["bearer_in"])
        cw, cmin = (v * IN for v in mc["chock_in"])
        up = mc["upright_in"] * IN
        pitch = D + 2 * th + gap
        mid = up + gap                                     # the room left between the middle barrels for the centre upright
        xs = (np.arange(nb) - (nb - 1) / 2) * pitch
        xs = xs + np.where(xs > 0, mid / 2, -mid / 2)
        span = nb * pitch + mid
        ys = [hz - L / 2 for hz, _ in bilge]               # the bilge hoops across the rack (the barrel's middle at y 0)
        rr = [r(hz) + th for hz, _ in bilge]               # the hoops' outer radius there
        z_bear = 0.0
        tiers = []
        for t_ in range(nt):
            zc = z_bear + bh + cmin + max(rr)              # the barrels' axis
            for y, ro in zip(ys, rr):
                vbox(it.piece("Bearers"), [-span / 2, y - bw / 2, z_bear], [span / 2, y + bw / 2, z_bear + bh], "Oak")
                for x in xs:
                    # a chock: a block across the bearer, its top hollowed to the hoop's round
                    half = 0.42 * (D + 2 * th)
                    arc = [(x + ro * math.sin(a), zc - ro * math.cos(a)) for a in np.linspace(-math.asin(half / ro),
                                                                                             math.asin(half / ro), 9)]
                    outline = [(x - half, z_bear + bh), (x + half, z_bear + bh)] + arc[::-1]
                    prism(it.piece("Chocks"), [np.array(outline)], [0.0, 0.0, 0.0], EX, EZ, y - cw / 2, y + cw / 2, "Oak")
            tiers.append(zc)
            z_bear = zc + max(rr) + mc["tier_clear_in"] * IN
        # the uprights at the rack's ends and in its middle, under each upper bearer
        top = tiers[-1] - max(rr) - cmin
        for y in ys:
            for sx in (-1.0, 1.0):
                x0 = sx * span / 2
                vbox(it.piece("Uprights"), [min(x0, x0 + sx * up), y - bw / 2, 0.0], [max(x0, x0 + sx * up), y + bw / 2, top],
                     "Oak")
            vbox(it.piece("Uprights"), [-up / 2, y - bw / 2, bh], [up / 2, y + bw / 2, top - bh], "Oak")
        for t_, zc in enumerate(tiers):
            for k_, x in enumerate(xs):
                it.slots.append({"item": "PowderBarrel", "name": f"tier{t_ + 1}_{k_ + 1}",
                                 "at_m": [round(float(x), 4), round(-L / 2, 4), round(float(zc), 4)],
                                 "turn_deg": [-90.0, 0.0, 0.0],
                                 "note": "the barrel built standing (z its length) turned about X so its length runs "
                                         "along +Y from at_m"})
        it.info = {"barrels": nb * nt, "powder_lb": nb * nt * 100}
        return it

    def cartridge(self):
        """a filled flannel cartridge for a 24-pounder, lying along X: the bag rounded at its foot, choked round its neck
        at the head with a turn of twine, the choked tail beyond"""
        cc = self.c["magazine"]["cartridge"]
        R = cc["across_in"] / 2 * IN
        L = cc["long_in"] * IN
        tl, nr = (v * IN for v in cc["choke_in"])
        it = Item("Cartridge24", "a filled 24-pounder cartridge lying along X, its tail to +X")
        x0 = -(L + tl) / 2                                  # the origin under its middle
        prof = [(0.0, 0.0), (0.0, 0.55 * R), (0.25 * IN, 0.85 * R), (0.9 * IN, R)]
        prof += [(x, R) for x in np.linspace(2.0 * IN, L - 2.0 * IN, 5)]
        # the choked tail: the flannel gathered to the neck, then flaring out into a ragged tuft
        prof += [(L - 0.9 * IN, 0.9 * R), (L - 0.2 * IN, 0.55 * R), (L + 0.3 * IN, nr), (L + 0.6 * IN, nr * 0.9),
                 (L + 1.0 * IN, nr * 1.12), (L + 0.6 * tl, nr * 1.38), (L + tl - 0.25 * IN, nr * 1.55),
                 (L + tl, nr * 1.25), (L + tl - 0.15 * IN, nr * 0.6), (L + tl - 0.15 * IN, 0.0)]
        tmp = SPart()
        lathe(tmp, [x0, 0.0, R], EX, EZ, prof, "Fleece", 24)
        # the tuft gathered into folds: past the twine each ring is pushed in and out round its nine folds, more toward
        # the ragged end (seam vertices move alike, so the seam stays shut)
        for k, V_ in enumerate(tmp.V):
            V_ = np.asarray(V_, float)
            x = V_[:, 0] - x0
            q = np.clip((x - (L + 1.0 * IN)) / (tl - 1.0 * IN), 0.0, 1.0)
            ang = np.arctan2(V_[:, 1], V_[:, 2] - R)
            f = 1.0 + 0.16 * q * np.cos(9 * ang)
            V_[:, 1] *= f
            V_[:, 2] = R + (V_[:, 2] - R) * f
            tmp.V[k] = V_
        it.piece("Bag").extend(tmp)
        th = np.linspace(0.0, 2 * math.pi, 13)[:-1]
        tr = 0.08 * IN
        x_t = x0 + L + 0.6 * IN
        rc = nr * 0.9 + tr * 0.5
        tube(it.piece("Tie"), np.stack([np.full_like(th, x_t), rc * np.cos(th), R + rc * np.sin(th)], 1), tr, "Hemp", n=5,
             closed=True)
        return it

    def cartridge_rack(self):
        """the filling room's cartridge rack: upright dividers, the shelves between them and a top, filled cartridges
        lying on each shelf (slots: Cartridge24, each across the rack, its tail to the back)"""
        rc = self.c["magazine"]["cartridge_rack"]
        cc = self.c["magazine"]["cartridge"]
        cd, cl = cc["across_in"] * IN, cc["long_in"] * IN + cc["choke_in"][0] * IN
        nb, ns, pb = rc["bays"], rc["shelves"], rc["per_bay"]
        sh, dv, deep = rc["shelf_in"] * IN, rc["divider_in"] * IN, rc["deep_in"] * IN
        gap, pitch = rc["gap_in"] * IN, rc["pitch_in"] * IN
        bay = pb * cd + (pb + 1) * gap
        width = nb * bay + (nb + 1) * dv
        H = ns * pitch + rc["top_in"] * IN
        it = Item("CartridgeRack", "the filling room's cartridge rack (slots: Cartridge24), its front to +Y")
        x = -width / 2
        for k in range(nb + 1):
            vbox(it.piece("Dividers"), [x, -deep / 2, 0.0], [x + dv, deep / 2, H], "Oak")
            if k < nb:
                x0 = x + dv
                for s in range(ns):
                    z0 = s * pitch
                    vbox(it.piece("Shelves"), [x0, -deep / 2, z0], [x0 + bay, deep / 2, z0 + sh], "Oak")
                    for c in range(pb):
                        xc = x0 + gap + cd / 2 + c * (cd + gap)
                        it.slots.append({"item": "Cartridge24", "name": f"bay{k + 1}_shelf{s + 1}_{c + 1}",
                                         "at_m": [round(xc, 6), round(-(cl - deep) / 2, 6), round(z0 + sh, 6)],
                                         "turn_deg": [0.0, 0.0, -90.0],
                                         "note": "the cartridge turned about Z so its tail points back (-Y), its "
                                                 "foot at the shelf's front edge"})
                vbox(it.piece("Top"), [x0, -deep / 2, H - rc["top_in"] * IN], [x0 + bay, deep / 2, H], "Oak")
            x += dv + bay
        if cl > deep:
            it.info["cartridge_over_shelf_m"] = round(cl - deep, 4)
        it.info.update({"cartridges": nb * ns * pb})
        return it

    def passing_box(self):
        """a passing box: a wooden cylinder a boy carried one cartridge up from the magazine in, two copper bands round
        it, its lid fitting over the top with a rope becket to lift it by"""
        pc = self.c["magazine"]["passing_box"]
        R, H = pc["across_in"] / 2 * IN, pc["high_in"] * IN
        lh = pc["lid_in"] * IN
        it = Item("PassingBox", "a passing box, standing on the deck, its lid on")
        cc = self.c["magazine"]["cartridge"]
        inside = H - lh - pc["wall_in"] * IN
        need = (cc["long_in"] + cc["choke_in"][0]) * IN
        assert inside >= need + 0.25 * IN, ("passing box too short for a cartridge", inside / IN, need / IN)
        it.info = {"inside_m": round(inside, 4), "cartridge_m": round(need, 4)}
        th = 0.05 * IN
        prof = [(0.0, 0.0), (0.0, R)]
        mats = ["Oak"]
        for zc in (2.0 * IN, H - lh - 2.5 * IN):
            prof += [(zc - 0.4 * IN, R), (zc - 0.4 * IN, R + th), (zc + 0.4 * IN, R + th), (zc + 0.4 * IN, R)]
            mats += ["Oak", "Copper", "Copper", "Copper"]
        prof += [(H - lh + 0.2 * IN, R), (H - lh + 0.2 * IN, 0.0)]
        mats += ["Oak", "Oak"]
        lathe(it.piece("Box"), [0.0, 0.0, 0.0], EZ, EX, prof, mats, 20)
        lw = 0.3 * IN
        lathe(it.piece("Lid"), [0.0, 0.0, H - lh], EZ, EX, [(0.0, 0.0), (0.0, R + lw), (lh, R + lw), (lh, 0.0)], "Oak", 20)
        br = pc["becket_in"] / 2 * IN
        pts = [[-1.2 * IN, 0.0, H - 0.4 * IN]]
        for t in np.linspace(0.0, math.pi, 9):
            pts.append([-1.2 * IN * math.cos(t), 0.0, H + 1.4 * IN * math.sin(t)])
        pts.append([1.2 * IN, 0.0, H - 0.4 * IN])
        tube(it.piece("Becket"), np.array(pts), br, "Hemp", n=6)
        return it

    def filling_bench(self):
        """the filling room's bench: an oak top on four legs with stretchers, a low rim round it, the top inside the rim
        sheathed in copper"""
        fb = self.c["magazine"]["filling_bench"]
        L, W = (v * IN for v in fb["size_in"])
        H, tt = fb["high_in"] * IN, fb["top_in"] * IN
        rh, rw = (v * IN for v in fb["rim_in"])
        sh = fb["sheet_in"] * IN
        lg = fb["leg_in"] * IN
        sw, st = (v * IN for v in fb["stretcher_in"])
        zs = fb["stretcher_high_in"] * IN
        it = Item("FillingBench", "the filling room's bench, standing on the deck")
        vbox(it.piece("Top"), [-L / 2, -W / 2, H - tt], [L / 2, W / 2, H], "Oak")
        outer = np.array([[-L / 2, -W / 2], [L / 2, -W / 2], [L / 2, W / 2], [-L / 2, W / 2]])
        inner = np.array([[-L / 2 + rw, -W / 2 + rw], [L / 2 - rw, -W / 2 + rw], [L / 2 - rw, W / 2 - rw],
                          [-L / 2 + rw, W / 2 - rw]])
        prism(it.piece("Rim"), [outer, inner[::-1]], [0.0, 0.0, 0.0], EX, EY, H, H + rh, "Oak")
        vbox(it.piece("Sheet"), [-L / 2 + rw, -W / 2 + rw, H], [L / 2 - rw, W / 2 - rw, H + sh], "Copper")
        xi, yi = L / 2 - 2.0 * IN - lg / 2, W / 2 - 2.0 * IN - lg / 2
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                vbox(it.piece("Legs"), [sx * xi - lg / 2, sy * yi - lg / 2, 0.0], [sx * xi + lg / 2, sy * yi + lg / 2, H - tt],
                     "Oak")
        for sy in (-1.0, 1.0):                              # the side stretchers, between the legs' faces
            vbox(it.piece("Stretchers"), [-xi + lg / 2, sy * yi - st / 2, zs], [xi - lg / 2, sy * yi + st / 2, zs + sw], "Oak")
        for sx in (-1.0, 1.0):                              # the end stretchers, a little lower so they miss the sides'
            vbox(it.piece("Stretchers"), [sx * xi - st / 2, -yi + lg / 2, zs - sw - 0.5 * IN],
                 [sx * xi + st / 2, yi - lg / 2, zs - 0.5 * IN], "Oak")
        return it

    def bread_bag(self):
        """a bag of biscuit lying flat along X: a canvas pillow (its sections superellipses, flat underneath so the bags
        stack), drawn in to its neck at +X, choked by a lashing, the tail beyond"""
        bc = self.c["bread"]
        L, W, H = (v * IN for v in bc["size_in"])
        nr, tl = (v * IN for v in bc["neck_in"])
        p = bc["squareness"]
        it = Item("BreadBag", "a bag of ship's biscuit lying flat along X, its neck to +X")
        n = 24
        th = np.arange(n + 1) * 2 * math.pi / n
        cs, sn = np.cos(th), np.sin(th)
        x0 = -(L + tl) / 2                                  # the origin under its middle
        xn = x0 + L                                         # the neck
        draw = 8.0 * IN                                     # the length over which the bag is drawn in to its neck

        def ring(x, a, b, folds=0.0, flat=True):
            """a section at x: a superellipse of half sizes a, b about the bag's middle height, gathered into folds"""
            r = 1.0 + folds * np.cos(8 * th)
            y = a * r * np.sign(cs) * np.abs(cs) ** (2 / p)
            z = H / 2 + b * r * np.sign(sn) * np.abs(sn) ** (2 / p)
            P = np.stack([np.full(n + 1, x), y, z], 1)
            if flat:
                P[:, 2] = np.maximum(P[:, 2], 0.0)          # pressed flat underneath
            return P
        rings = []
        for f in np.linspace(0.0, 1.0, 7)[1:]:              # the sewn foot, rounding out over 3 in
            g = 0.35 + 0.65 * math.sin(f * math.pi / 2)
            rings.append(ring(x0 + 3.0 * IN * (1 - math.cos(f * math.pi / 2)), W / 2 * g, H / 2 * g))
        for x in np.linspace(x0 + 3.0 * IN, xn - draw, 6)[1:]:
            rings.append(ring(x, W / 2, H / 2))
        for f in np.linspace(0.0, 1.0, 8)[1:]:              # drawn in to the neck, the cloth gathering into folds
            g = (1 + math.cos(f * math.pi)) / 2
            rings.append(ring(xn - draw + f * draw, nr + (W / 2 - nr) * g, nr + (H / 2 - nr) * g,
                              folds=0.25 * 4 * g * (1 - g) + 0.08 * (1 - g)))
        # the tail beyond the lashing, flaring into its gathered folds
        for x, r, fo in ((xn + 0.4 * IN, nr * 0.95, 0.05), (xn + 0.9 * IN, nr * 1.15, 0.12), (xn + tl * 0.6, nr * 1.6, 0.2),
                         (xn + tl - 0.3 * IN, nr * 1.9, 0.22), (xn + tl, nr * 1.2, 0.15)):
            rings.append(ring(x, r, r, folds=fo, flat=False))
        foot = np.array([x0, 0.0, H / 2 * 0.35])
        tip = np.array([xn + tl, 0.0, H / 2])
        F = []
        Vs = [foot] + [r_ for ring_ in rings for r_ in ring_] + [tip]
        m = n + 1
        for i in range(n):
            F.append((0, 1 + i + 1, 1 + i))
        for k in range(len(rings) - 1):
            a0, b0 = 1 + k * m, 1 + (k + 1) * m
            for i in range(n):
                F.append((a0 + i, a0 + i + 1, b0 + i + 1, b0 + i))
        last = 1 + (len(rings) - 1) * m
        for i in range(n):
            F.append((last + i, last + i + 1, len(Vs) - 1))
        Vs = np.array(Vs)
        # weld the seam (ring point n is point 0) so the solid is closed: point n of each ring onto point 0
        remap = list(range(len(Vs)))
        for k in range(len(rings)):
            remap[1 + k * m + n] = 1 + k * m
        F = [tuple(remap[i] for i in f) for f in F]
        F = [f for f in F if len(set(f)) == len(f)]
        add_solid(it.piece("Bag"), Vs, F, "Canvas")
        tr = bc["tie_in"] / 2 * IN
        thr = np.linspace(0.0, 2 * math.pi, 13)[:-1]
        rc = nr * 0.95 + tr * 0.6
        tube(it.piece("Tie"), np.stack([np.full_like(thr, xn + 0.4 * IN), rc * np.cos(thr), H / 2 + rc * np.sin(thr)], 1), tr,
             "Hemp", n=5, closed=True)
        return it
