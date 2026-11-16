"""The frigate's anchors and cables (docs/shipkit-10): her six anchors (two bowers, the sheet anchor, the stream anchor
and two kedges), each a wrought-iron anchor of the period with its oak stock, built to its weight (Anchor); on the ship
(Anchors) the catheads the bowers hang from, catted and fished; the billboards their bills rest on; the hawse holes, two
a side, with their bolsters and lead linings; the 22 in hemp cables, bent to the bowers' rings and led in through the
hawse holes; the cat stoppers and the shank painters. The sheet, stream and kedge anchors are sized here (Anchor) and
stowed by the slices that build where they go (anchors_1797.json's stow).
    from anchors import Anchor, Anchors
    a = Anchor(card, weight_lb).solve();  a.iron, a.stock, a.ring (Mesh, local frame);  a.iron_kg;  a.key
    an = Anchors(L, rig, sk, hd, skin_parts).build();  an.cut_hawse(skin_parts);  an.parts();  an.info
Sizes, places and their sources are anchors_1797.json's. An anchor's frame (Anchor): origin on the crown (where the
arms' centre line crosses the shank's axis), +Z up the shank to the ring, the arms in the XZ plane, the stock along Y
(the ring turns about Y in the shank's eye, so it lies in the stock's plane). Units: metres in the ship's frame (X
forward, Y starboard, Z up, origin on the centreline at midships on waterline A) elsewhere.
"""
import json
import math
import os

import numpy as np

import loft
from skin import sweep

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
LB = 0.45359237
CWT_LB = 112.0
EX, EY, EZ = np.eye(3)

IRON = "Blacking"             # the anchors' iron: blacked (tar and lamp black), as the guns' barrels
FITTING = "Iron"              # the stock's hoops, the eyebolts, the cathead's sheave pins
OAK = "Oak"
TARRED = "Tarred"
LEAD = "Lead"


def load_card(path=None):
    """the size card (anchors_1797.json)"""
    with open(path or os.path.join(HERE, "anchors_1797.json")) as f:
        return json.load(f)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rot_axis(axis, ang):
    """the rotation by ang (radians) about axis"""
    a = unit(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def rot_between(u, v):
    """the least rotation taking the direction u to the direction v"""
    u, v = unit(u), unit(v)
    c = float(u @ v)
    w = np.cross(u, v)
    s = float(np.linalg.norm(w))
    if s < 1e-12:
        if c > 0:
            return np.eye(3)
        return rot_axis(unit(np.cross(u, EX if abs(u[0]) < 0.9 else EY)), math.pi)
    return rot_axis(w / s, math.atan2(s, c))


def mass_centre(V, F):
    """the centre and volume of a closed mesh (faces turned out)"""
    V = np.asarray(V, float)
    c, vol = np.zeros(3), 0.0
    for f in F:
        a = V[f[0]]
        for k in range(1, len(f) - 1):
            v = float(np.dot(a, np.cross(V[f[k]], V[f[k + 1]]))) / 6.0
            c += v * (a + V[f[k]] + V[f[k + 1]]) / 4.0
            vol += v
    return c / vol, vol


def signed_volume(V, F):
    """The volume a closed mesh encloses (its faces turned out): the divergence theorem over its faces' fans."""
    V = np.asarray(V, float)
    vol = 0.0
    for f in F:
        a = V[f[0]]
        for k in range(1, len(f) - 1):
            vol += float(np.dot(a, np.cross(V[f[k]], V[f[k + 1]])))
    return vol / 6.0


def rounded_rect(w, h, r, n=3):
    """A rectangle w (along the first axis) by h about its centre, its corners cut round by r (n points a corner),
    counter-clockwise, as (k, 2)."""
    r = min(r, 0.49 * w, 0.49 * h)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 90.0), (-w / 2 + r, -h / 2 + r, 180.0),
                       (w / 2 - r, -h / 2 + r, 270.0)):
        for k in range(n):
            a = math.radians(a0 + 90.0 * k / (n - 1))
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts)


class Mesh:
    """Vertices, faces, a material and a label per face (what each piece is: 'shank', 'arms', 'palm'...)."""

    def __init__(self):
        self.V, self.F, self.M, self.lab = [], [], [], []
        self.n = 0
        self.cur = "part"

    def add(self, V, F, M, uv=None):
        V = np.asarray(V, float).reshape(-1, 3)
        self.V.append(V)
        self.F += [tuple(self.n + int(i) for i in f) for f in F]
        self.M += list(M) if not isinstance(M, str) else [M] * len(F)
        self.lab += [self.cur] * len(F)
        self.n += len(V)

    def add_m(self, V, F, mats):
        """guns.py's call: a material per face"""
        self.add(V, F, list(mats))

    def extend(self, other, T=None):
        """append another Mesh, taken through the 4x4 T if given"""
        for V in other.V:
            self.V.append(V if T is None else V @ T[:3, :3].T + T[:3, 3])
        self.F += [tuple(self.n + i for i in f) for f in other.F]
        self.M += other.M
        self.lab += other.lab
        self.n += other.n

    def arrays(self):
        if not self.V:
            return np.zeros((0, 3)), [], []
        return np.concatenate(self.V), list(self.F), list(self.M)

    def tris(self):
        return sum(len(f) - 2 for f in self.F)


# ---- an anchor ------------------------------------------------------------------------------------------------------
class Anchor:
    """One anchor of the period, built in its own frame (the module's docstring) from its weight and the size card's
    shape: the shank (square, its edges taken off, tapering from the throat to the stock), the eye at its top, the
    arms on their arc through the crown, the palms on the arms' inner faces, the bills, the ring in the eye (puddened
    for a bower), the two nuts under the stock and the oak stock in two pieces with its hoops. The throat's side is
    solved so that the iron weighs the anchor's weight (solve). key: the points the ship's gear needs (the eye, the
    ring, the bills, the palms, the crown, the stock's ends)."""

    def __init__(self, cfg, lb, pudden=None, name="anchor"):
        self.cfg, self.sh, self.lb, self.name = cfg, cfg["shape"], float(lb), name
        sh = self.sh
        self.Ls = sh["shank_ft_per_cwt_cube"] * (self.lb / CWT_LB) ** (1.0 / 3.0) * FT
        self.R = sh["arm_radius"] * self.Ls
        self.th = sh["arm_angle_rad"]
        self.D_ring = sh["ring_outside"] * self.Ls
        self.r_bar = 0.5 * sh["ring_bar"] * self.Ls
        self.pudden = (sh["pudden_in"] * IN) if pudden is None else pudden
        self.L_stock = self.Ls + 0.5 * self.D_ring
        self.kg = self.lb * LB
        self.a_t = None

    # the arms' centre line: phi from 0 (the crown) to th (the bill), sgn +-1 the arm on +-X
    def arc(self, phi, sgn=1.0):
        phi = np.asarray(phi, float)
        return np.stack([sgn * self.R * np.sin(phi), np.zeros_like(phi), self.R * (1 - np.cos(phi))], -1)

    def arc_t(self, phi, sgn=1.0):
        phi = np.asarray(phi, float)
        return np.stack([sgn * np.cos(phi), np.zeros_like(phi), np.sin(phi)], -1)

    def arc_in(self, phi, sgn=1.0):
        """the arm's inner normal (toward the arc's centre on the shank: the palm's face looks this way)"""
        phi = np.asarray(phi, float)
        return np.stack([-sgn * np.sin(phi), np.zeros_like(phi), np.cos(phi)], -1)

    def arm_depth(self, phi):
        """the arm's section (depth in its plane, breadth along Y) at phi, as a share of the throat's side"""
        sh = self.sh
        f = phi / self.th
        palm0 = 1.0 - sh["palm_of_arm"] - sh["bill_beyond_palm"]
        d = np.interp(f, [0.0, palm0, 1.0 - sh["bill_beyond_palm"], 1.0],
                      [sh["arm_crown"], sh["arm_palm"], 0.5 * (sh["arm_palm"] + sh["arm_bill"]), sh["arm_bill"]])
        return d + 0.12 * np.exp(-(phi / 0.22) ** 2)            # the crown swells a little where the arms meet

    def z_levels(self):
        """the shank's heights: where it leaves the crown, the stock's middle, the eye's hole"""
        a_t, sh = self.a_t, self.sh
        a_s = sh["small_end"] * a_t
        r_h = sh["eye_over_bar"] * self.r_bar
        R_e = max(0.5 * a_s, r_h + 0.55 * a_s)                  # the eye swells round its hole
        z_top = self.Ls
        z_hole = z_top - R_e
        s_m = sh["stock_middle"] * self.L_stock
        z_stock = z_hole - R_e - 0.03 - 0.5 * s_m                # the stock's middle, just under the eye
        return a_s, r_h, R_e, z_hole, z_stock, s_m

    def build(self, a_t=None):
        """the anchor at the throat a_t (or solve() first)"""
        if a_t is None:
            return self.solve()
        self.a_t = a_t
        sh = self.sh
        a_s, r_h, R_e, z_hole, z_stock, s_m = self.z_levels()
        self.iron, self.stock, self.ring = Mesh(), Mesh(), Mesh()
        self.vols = {}
        # the shank: from just inside the arms' top at the crown to the eye's foot, curved into the arms' tops at the
        # throat (a fillet in the arms' plane, throat_fillet of the throat's side in radius)
        M = self.iron
        M.cur = "shank"
        h0 = self.arm_depth(0.0) * a_t
        zA = 0.5 * h0                                            # the arms' top at the crown
        z0 = zA - 0.27 * h0                                      # the foot buried below the arms' chamfered edges
        rf = sh["throat_fillet"] * a_t
        e_in = 0.003                                             # the eye 3 mm inside the shank's faces (none coplanar)
        dl = math.asin(min(0.99, (0.5 * a_s - e_in) / R_e))
        z1 = z_hole - R_e * math.cos(dl)                         # the eye's round meets the shank's sides here
        zs = np.concatenate([[z0], zA + rf * (1 - np.cos(np.linspace(0, 0.5 * math.pi, 7))),
                             np.linspace(zA + rf, z_stock - 0.5 * s_m, 10)[1:], np.linspace(z_stock - 0.5 * s_m, z1, 4)[1:]])
        secs = []
        for z in zs:
            a = np.interp(z, [z0, zA + 0.6 * a_t, z_stock - 0.5 * s_m, z1], [a_t, a_t, a_s, a_s])
            fil = rf if z <= zA else (rf - math.sqrt(max(0.0, rf * rf - (zA + rf - z) ** 2)) if z < zA + rf else 0.0)
            ring = rounded_rect(a + 2 * fil, a, sh["chamfer"] * a * 1.4, n=2)
            secs.append(np.stack([ring[:, 0], ring[:, 1], np.full(len(ring), z)], -1))
        V, F, Mt = sweep(secs, IRON)
        M.add(V, F, Mt)
        self.vols["shank"] = signed_volume(V, F)
        # the eye: a plate across the shank's top, round over its hole (the ring's bar through it, along Y)
        M.cur = "eye"
        a = np.linspace(-math.pi / 2 + dl, 3 * math.pi / 2 - dl, 16)
        top = np.stack([R_e * np.cos(a), z_hole + R_e * np.sin(a)], -1)
        foot = np.array([[-0.5 * a_s + e_in, z1 - 0.03], [0.5 * a_s - e_in, z1 - 0.03]])   # let 3 cm into the shank
        outline = np.concatenate([foot[1:], top, foot[:1]])
        t = np.arange(14) * 2 * math.pi / 14
        hole = np.stack([r_h * np.cos(t), z_hole + r_h * np.sin(t)], -1)
        part = Mesh()
        _slab(part, outline, [hole], 0.5 * a_s - e_in, IRON)
        V, F, Mt = part.arrays()
        M.add(V, F, Mt)
        self.vols["eye"] = signed_volume(V, F)
        # the arms through the crown, bill to bill
        M.cur = "arms"
        phis = np.concatenate([-np.linspace(self.th, 0.0, 22)[:-1], np.linspace(0.0, self.th, 22)])
        secs = []
        for ph in phis:
            s = 1.0 if ph >= 0 else -1.0
            p = self.arc(abs(ph), s)
            nin = self.arc_in(abs(ph), s)
            d = self.arm_depth(abs(ph)) * a_t
            ring = rounded_rect(d, d * 0.96, sh["chamfer"] * d * 1.4, n=2)       # (depth along nin, breadth along Y)
            if abs(ph) > self.th - 1e-9:
                ring = ring * 0.35                                            # the bill's blunt point
            secs.append(p + ring[:, :1] * nin + ring[:, 1:2] * EY)
        V, F, Mt = sweep(secs, IRON)
        M.add(V, F, Mt)
        self.vols["arms"] = signed_volume(V, F)
        # the palms: plates bent to the arms' inner faces near the bills
        M.cur = "palm"
        self.vols["palm"] = 0.0
        for sgn in (1.0, -1.0):
            V, F = self.palm(sgn)
            M.add(V, F, IRON)
            self.vols["palm"] += signed_volume(V, F)
        # the nuts under the stock, on the shank's faces toward the arms
        M.cur = "nut"
        nz, npr = sh["nut_of_throat"]
        self.vols["nut"] = 0.0
        e_nut = 0.004
        for sgn in (1.0, -1.0):
            c = np.array([sgn * (0.5 * a_s + 0.5 * npr * a_t - 0.5 * e_nut), 0.0, z_stock - 0.5 * s_m - 0.5 * nz * a_t])
            V, F = _box(c, EX, EY, EZ, (0.5 * npr * a_t + 0.5 * e_nut, 0.45 * a_s, 0.5 * nz * a_t))
            M.add(V, F, IRON)
            self.vols["nut"] += signed_volume(V, F)
        # the stock: two oak pieces either side of the shank (a gap between them), hooped
        self.build_stock(z_stock, s_m, a_s)
        # the ring, hanging along +Z from the eye (pose() swings it)
        self.build_ring(np.array([0.0, 0.0, z_hole]), EZ)
        # the iron's weight: the volume the iron's pieces fill together (they overlap where they are let into each
        # other: union_volume), and the ring's
        V, F, _ = self.iron.arrays()
        self.iron_m3 = union_volume(V, F, self.iron_pieces(), self.Ls / 1000.0) + self.vols["ring"]
        self.iron_kg = self.iron_m3 * self.cfg["iron_kg_m3"]
        self.key = {"eye": np.array([0.0, 0.0, z_hole]), "eye_axis": EY.copy(), "R_e": R_e, "a_s": a_s, "a_t": a_t,
                    "crown": np.zeros(3), "crown_bottom": np.array([0.0, 0.0, -0.5 * h0]),
                    "bill": [self.arc(self.th, 1.0), self.arc(self.th, -1.0)],
                    "palm": [self.palm_mid[1.0], self.palm_mid[-1.0]],
                    "stock_z": z_stock, "stock_middle": s_m, "stock_len": self.L_stock,
                    "ring_R": 0.5 * (self.D_ring - 2 * self.r_bar), "ring_bar": self.r_bar, "pudden": self.pudden,
                    "shank_len": self.Ls}
        return self

    def iron_pieces(self):
        """the iron's faces grouped by the piece each was added as (each piece closed on its own)"""
        starts = np.cumsum([0] + [len(v) for v in self.iron.V])
        k = np.searchsorted(starts, [f[0] for f in self.iron.F], side="right") - 1
        return [[f for f, kk in zip(self.iron.F, k) if kk == i] for i in range(len(self.iron.V))]

    def solve(self, tol=0.002):
        """the throat's side that makes the iron weigh the anchor's weight (secant steps on the built volume)"""
        a0 = 0.047 * self.Ls
        w0 = self.build(a0).iron_kg - self.kg
        a1 = a0 * 1.05
        w1 = self.build(a1).iron_kg - self.kg
        for _ in range(12):
            if abs(w1) < tol * self.kg:
                break
            a2 = a1 - w1 * (a1 - a0) / (w1 - w0)
            a0, w0 = a1, w1
            a1 = a2
            w1 = self.build(a1).iron_kg - self.kg
        return self

    def palm(self, sgn):
        """the palm on the +-X arm: a plate on the arm's inner face from the bill back palm_of_arm of the arm, its
        outline square across its back end (toward the crown) with rounded shoulders, widest palm_shoulder of its
        length out from there and curving in to its point at the bill; thickest on the arm and thinning to its rim and
        its point; bent with the arm so its back lies on the arm's inner face (let in 3 mm)"""
        sh, a_t = self.sh, self.a_t
        arm_len = self.R * self.th
        l_p = sh["palm_of_arm"] * arm_len
        s2 = arm_len * (1.0 - sh["bill_beyond_palm"])
        s1 = s2 - l_p
        b_p = sh["palm_breadth"] * l_p
        t_c = sh["palm_thick"] * a_t
        nu, nw = 14, 9
        u = np.linspace(0.0, 1.0, nu)
        # half-breadth along the palm: the back end square across, rounding out to the shoulders, then in to the point
        us = sh["palm_shoulder"]
        t = np.clip((u - us) / (1.0 - us), 0.0, 1.0)
        half = 0.5 * b_p * np.where(u < us, 0.62 + 0.38 * np.sin(0.5 * math.pi * np.clip(u / us, 0, 1)),
                                    np.clip(1.0 - t ** 1.8, 0.0, 1.0) ** 0.85)
        half = np.maximum(half, 0.004)
        w = np.linspace(-1.0, 1.0, nw)
        tops, backs = [], []
        for k, uk in enumerate(u):
            s = s1 + uk * l_p
            ph = s / self.R
            p, nin = self.arc(ph, sgn), self.arc_in(ph, sgn)
            d = self.arm_depth(ph) * a_t
            base = p + nin * (0.5 * d - 0.003)
            tk = t_c * np.interp(uk, [0.0, 0.25, 0.6, 1.0], [0.75, 1.0, 0.9, 0.35]) * (1.0 - (1 - sh["palm_rim"]) * w ** 2)
            ys = w * half[k]
            backs.append(base[None, :] + ys[:, None] * EY[None, :])
            tops.append(base[None, :] + ys[:, None] * EY[None, :] + tk[:, None] * nin[None, :])
        T, B = np.array(tops), np.array(backs)          # (nu, nw, 3)
        V = np.concatenate([T.reshape(-1, 3), B.reshape(-1, 3)])
        off = nu * nw
        F = []
        for i in range(nu - 1):
            for j in range(nw - 1):
                a, b, c, d = i * nw + j, i * nw + j + 1, (i + 1) * nw + j + 1, (i + 1) * nw + j
                F.append((a, b, c, d))
                F.append((off + d, off + c, off + b, off + a))
        # the rim: round the outline (the two long edges and the two ends), top to back
        rim = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nw)] + \
              [(i, nw - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nw - 2, 0, -1)]
        for k in range(len(rim)):
            i0, j0 = rim[k]
            i1, j1 = rim[(k + 1) % len(rim)]
            a, b = i0 * nw + j0, i1 * nw + j1
            F.append((b, off + b, off + a, a))
        if signed_volume(V, F) < 0:                             # every face out
            F = [f[::-1] for f in F]
        self.palm_mid = getattr(self, "palm_mid", {})
        self.palm_mid[sgn] = T[nu // 2, nw // 2]
        return V, F

    def build_stock(self, z_stock, s_m, a_s):
        sh = self.sh
        L = self.L_stock
        gap = sh["stock_gap_in"] * IN
        e = sh["stock_end"]
        top = z_stock + 0.5 * s_m
        M = self.stock
        M.cur = "stock"
        for side in (1.0, -1.0):                       # the piece on +X, the piece on -X
            secs = []
            for yy in np.linspace(-0.5 * L, 0.5 * L, 17):
                f = min(1.0, max(0.0, (abs(yy) - 0.5 * a_s) / (0.5 * L - 0.5 * a_s)))
                d = s_m * (1 - (1 - e) * f)            # depth: the top straight, the lower face rising to the ends
                b = s_m * (1 - (1 - e) * f)
                x0, x1 = side * 0.5 * gap, side * 0.5 * b
                xa, xb = min(x0, x1), max(x0, x1)
                secs.append(np.array([[xa, yy, top - d], [xb, yy, top - d], [xb, yy, top], [xa, yy, top]]))
            V, F, Mt = sweep(secs, OAK)
            M.add(V, F, Mt)
        # the hoops: iron bands round both pieces, two a side
        M.cur = "hoop"
        hw, ht = sh["hoop_in"][0] * IN, sh["hoop_in"][1] * IN
        for fr in sh["hoops"]:
            for sgn in (1.0, -1.0):
                yy = sgn * fr * L
                f = min(1.0, max(0.0, (abs(yy) - 0.5 * a_s) / (0.5 * L - 0.5 * a_s)))
                d = s_m * (1 - (1 - e) * f)
                b = s_m * (1 - (1 - e) * f)
                secs = []
                for dy in (-0.5 * hw, 0.5 * hw):
                    o = rounded_rect(b + 2 * ht, d + 2 * ht, 0.6 * ht, n=2)
                    secs.append(np.stack([o[:, 0], np.full(len(o), yy + dy), top - 0.5 * d + o[:, 1]], -1))
                V, F, Mt = sweep(secs, FITTING)
                M.add(V, F, Mt)

    def build_ring(self, H, u):
        """the ring through the eye at H (its hole along Y), hanging toward u (perpendicular to Y); a bower's
        puddened (served with old rope) except where it passes through the eye"""
        self.ring = Mesh()
        Rc = 0.5 * (self.D_ring - 2 * self.r_bar)
        u = unit(u - (u @ EY) * EY)
        C = H + u * Rc
        t = np.linspace(0, 2 * math.pi, 41)[:-1]
        P = C[None] + Rc * (-np.cos(t)[:, None] * u[None] + np.sin(t)[:, None] * EY[None])   # t = 0 at the eye
        self.ring.cur = "ring"
        V, F = _tube_loop(P, self.r_bar, 12)
        self.ring.add(V, F, IRON)
        self.vols["ring"] = signed_volume(V, F)
        if self.pudden > 0:
            self.ring.cur = "pudden"
            R_e = self.z_levels()[2]
            a0 = 2 * math.asin(min(0.99, (R_e + self.pudden + 0.01) / (2 * Rc)))   # clear of the eye's round
            ta = np.linspace(a0, 2 * math.pi - a0, 36)
            P = C[None] + Rc * (-np.cos(ta)[:, None] * u[None] + np.sin(ta)[:, None] * EY[None])
            V, F = _tube_open(P, self.r_bar + self.pudden, 12)
            self.ring.add(V, F, TARRED)
        self.ring_frame = (C, u, EY, Rc)

    def centre_of_mass(self, oak_kg_m3=750.0):
        """the anchor's centre of mass in its frame: the iron (its pieces' overlaps counted twice: they are small) and
        the oak stock (its hoops as oak); the ring left out (it hangs from the stopper)"""
        V, F, _ = self.iron.arrays()
        ci, vi = mass_centre(V, F)
        Vs, Fs, _ = self.stock.arrays()
        cs, vs = mass_centre(Vs, Fs)
        mi, ms = vi * self.cfg["iron_kg_m3"], vs * oak_kg_m3
        return (ci * mi + cs * ms) / (mi + ms)


def union_volume(V, F, pieces, h):
    """the volume a set of closed pieces (lists of faces over the vertices V) fill together, overlaps counted once:
    vertical rays on an h grid, each piece's crossings paired into its inside spans, the spans of every piece merged
    in each column"""
    V = np.asarray(V, float)
    lo, hi = V[:, :2].min(0), V[:, :2].max(0)
    x0, y0 = lo + h * 0.5173
    ny = int((hi[1] - y0) / h) + 1
    spans = []
    for Fs in pieces:
        T = np.array([(f[0], f[k], f[k + 1]) for f in Fs for k in range(1, len(f) - 1)])
        cols, zs = [], []
        for a, b, c in V[T]:
            d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
            if abs(d) < 1e-14:
                continue
            i0, i1 = int(math.ceil((min(a[0], b[0], c[0]) - x0) / h)), int(math.floor((max(a[0], b[0], c[0]) - x0) / h))
            j0, j1 = int(math.ceil((min(a[1], b[1], c[1]) - y0) / h)), int(math.floor((max(a[1], b[1], c[1]) - y0) / h))
            if i1 < i0 or j1 < j0:
                continue
            I, J = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
            px, py = x0 + I * h, y0 + J * h
            l1 = ((b[0] - px) * (c[1] - py) - (c[0] - px) * (b[1] - py)) / d
            l2 = ((c[0] - px) * (a[1] - py) - (a[0] - px) * (c[1] - py)) / d
            l3 = 1.0 - l1 - l2
            s = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
            if s.any():
                cols.append((I[s] * ny + J[s]).ravel())
                zs.append((l1 * a[2] + l2 * b[2] + l3 * c[2])[s].ravel())
        if not cols:
            continue
        cols, zs = np.concatenate(cols), np.concatenate(zs)
        o = np.lexsort((zs, cols))
        cols, zs = cols[o], zs[o]
        u, start, cnt = np.unique(cols, return_index=True, return_counts=True)
        for c, s0, n in zip(u, start, cnt):
            if n % 2 == 0:                                    # a grazing ray (odd count) is dropped
                spans += [(c, zs[s0 + k], zs[s0 + k + 1]) for k in range(0, n, 2)]
    spans.sort()
    total, cur_c, cur_lo, cur_hi = 0.0, None, 0.0, 0.0
    for c, a, b in spans:
        if c != cur_c or a > cur_hi:
            total += cur_hi - cur_lo
            cur_c, cur_lo, cur_hi = c, a, b
        else:
            cur_hi = max(cur_hi, b)
    total += cur_hi - cur_lo
    return total * h * h


def _box(c, X, Y, Z, h):
    """a box: centre c, axes X, Y, Z, half sizes h; faces out"""
    c = np.asarray(c, float)
    P = [c + sx * h[0] * X + sy * h[1] * Y + sz * h[2] * Z for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    F = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    V = np.array(P)
    if signed_volume(V, F) < 0:
        F = [f[::-1] for f in F]
    return V, F


def _frames(P, closed):
    """rotation-minimising frames along a polyline (closed: a loop): tangents T, normals A, binormals B"""
    P = np.asarray(P, float)
    m = len(P)
    if closed:
        T = unit(np.roll(P, -1, 0) - np.roll(P, 1, 0))
    else:
        T = np.empty_like(P)
        T[0], T[-1] = unit(P[1] - P[0]), unit(P[-1] - P[-2])
        T[1:-1] = unit(P[2:] - P[:-2])
    A0 = EZ if abs(T[0] @ EZ) < 0.9 else EX
    A = np.empty_like(P)
    A[0] = unit(A0 - (A0 @ T[0]) * T[0])
    for i in range(1, m):
        a = A[i - 1] - (A[i - 1] @ T[i]) * T[i]
        A[i] = unit(a) if np.linalg.norm(a) > 1e-9 else A[i - 1]
    if closed:
        a = unit(A[-1] - (A[-1] @ T[0]) * T[0])
        ang = math.atan2(float(np.cross(A[0], a) @ T[0]), float(A[0] @ a))
        for i in range(m):
            th = -ang * i / m
            A[i] = math.cos(th) * A[i] + math.sin(th) * np.cross(T[i], A[i])
    return T, A, np.cross(T, A)


def _tube_loop(P, r, n):
    """a closed ring of round section r along the loop P"""
    T, A, B = _frames(P, True)
    t = np.arange(n) * 2 * math.pi / n
    R = P[:, None, :] + r * (np.cos(t)[None, :, None] * A[:, None, :] + np.sin(t)[None, :, None] * B[:, None, :])
    m = len(P)
    V = R.reshape(-1, 3)
    F = [(i * n + j, i * n + (j + 1) % n, ((i + 1) % m) * n + (j + 1) % n, ((i + 1) % m) * n + j)
         for i in range(m) for j in range(n)]
    if signed_volume(V, F) < 0:
        F = [f[::-1] for f in F]
    return V, F


def _tube_open(P, r, n, caps=True):
    """a round bar of section r along the open polyline P, its ends capped flat"""
    T, A, B = _frames(P, False)
    t = np.arange(n) * 2 * math.pi / n
    R = P[:, None, :] + r * (np.cos(t)[None, :, None] * A[:, None, :] + np.sin(t)[None, :, None] * B[:, None, :])
    m = len(P)
    V = R.reshape(-1, 3)
    F = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
         for i in range(m - 1) for j in range(n)]
    if caps:
        F.append(tuple(range(n))[::-1])
        F.append(tuple((m - 1) * n + j for j in range(n)))
    if signed_volume(V, F) < 0:
        F = [f[::-1] for f in F]
    return V, F


def _wall_knot(m, base, ax, e1, b, h, mat, lobes=3, n=24):
    """a wall knot in a rope's end (a stopper knot) standing on base along ax: a round lump b across and h high, flat
    where it bears, its strands' lobes twisting a little round it and fading at its foot and crown"""
    ax = unit(ax)
    e1 = unit(e1 - (e1 @ ax) * ax)
    e2 = np.cross(ax, e1)
    prof = [(0.0, 0.62), (0.08, 0.86), (0.22, 0.98), (0.42, 1.0), (0.62, 0.92), (0.78, 0.74), (0.9, 0.52), (0.97, 0.28)]
    th = np.arange(n) * 2 * math.pi / n
    V = [base]
    for z, r in prof:
        amp = 0.1 * math.sin(math.pi * min(1.0, z / 0.9))
        rr = 0.5 * b * r * (1.0 + amp * np.cos(lobes * (th - 0.9 * z)))
        V += list(base + z * h * ax + rr[:, None] * (np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2))
    V.append(base + h * ax)
    V = np.array(V)
    k = len(prof)

    def ring(i, j):
        return 1 + i * n + j % n

    F = [(0, ring(0, j + 1), ring(0, j)) for j in range(n)]
    F += [(ring(i, j), ring(i, j + 1), ring(i + 1, j + 1), ring(i + 1, j)) for i in range(k - 1) for j in range(n)]
    F += [(len(V) - 1, ring(k - 1, j), ring(k - 1, j + 1)) for j in range(n)]
    if signed_volume(V, F) < 0:
        F = [f[::-1] for f in F]
    m.add(V, F, mat)


def _samples(P, step):
    """points over the triangles P (n, 3, 3), no two farther apart than about step"""
    P = np.asarray(P, float)
    if not len(P):
        return np.zeros((0, 3))
    e = np.max(np.stack([np.linalg.norm(P[:, 1] - P[:, 0], axis=1), np.linalg.norm(P[:, 2] - P[:, 1], axis=1),
                         np.linalg.norm(P[:, 0] - P[:, 2], axis=1)], 1), 1)
    K = np.clip(np.ceil(e / step).astype(int), 1, 200)
    out = []
    for k in np.unique(K):
        sel = np.where(K == k)[0]
        ij = np.array([(i, j) for i in range(k + 1) for j in range(k + 1 - i)], float) / k
        a, b, c = P[sel, 0], P[sel, 1], P[sel, 2]
        out.append((a[:, None] + ij[None, :, :1] * (b - a)[:, None] + ij[None, :, 1:] * (c - a)[:, None]).reshape(-1, 3))
    return np.concatenate(out)


def _even(P, step):
    """the polyline P laid again at an even step (its ends kept)"""
    P = np.asarray(P, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    s_e = np.linspace(0.0, s[-1], max(2, int(math.ceil(s[-1] / step))) + 1)
    return np.stack([np.interp(s_e, s, P[:, j]) for j in range(3)], -1)


def _course(P, rad, step):
    """A rope's course through the corners of the polyline P: each inner corner turned on a circular arc of radius
    rad, or as near it as the segments allow (where two corners want more of a segment than it has, they share it in
    proportion), then laid at an even step. Returns (points, the least radius of any turn of more than 5 deg)."""
    P = np.asarray(P, float)
    P = P[np.concatenate([[True], np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-9])]
    n = len(P)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    U = unit(np.diff(P, axis=0))
    th = np.zeros(n)
    for i in range(1, n - 1):
        th[i] = math.acos(float(np.clip(U[i - 1] @ U[i], -1.0, 1.0)))
    want = rad * np.tan(0.5 * np.minimum(th, math.radians(170.0)))
    f = np.ones(n - 1)
    for j in range(n - 1):
        need = want[j] + want[j + 1]
        if need > seg[j]:
            f[j] = 0.999 * seg[j] / need
    out, least = [P[0]], math.inf
    for i in range(1, n - 1):
        if th[i] < 1e-4:
            out.append(P[i])
            continue
        t = want[i] * min(f[i - 1], f[i])
        R = t / math.tan(0.5 * th[i])
        if th[i] > math.radians(5.0):
            least = min(least, R)
        u, v = U[i - 1], U[i]
        w = unit(v - (u @ v) * u)
        A = P[i] - t * u
        O = A + R * w
        ph = np.linspace(0.0, th[i], max(4, int(math.ceil(math.degrees(th[i]) / 3.0))) + 1)
        out += list(O[None] - R * np.cos(ph)[:, None] * w[None] + R * np.sin(ph)[:, None] * u[None])
    out.append(P[-1])
    out = np.array(out)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(out, axis=0), axis=1) > 1e-7])
    return _even(out[keep], step), least


def _bar_turn(rho, r, p1, tail, a0, k=10, gap=0.0):
    """A rope of radius r round a bar and back alongside itself, in the bar's section: p along the rope's way
    through (the bar's centre at the origin), q across. The standing part comes up at (-p1, -r), opens round the bar
    on radius rho (leaving the arc a0 short of the way back on either side), closes again to (-p1, r + gap) and its
    end lies along the standing part to (-p1 - tail, r + gap): the clinch of a cable on its ring, or a splice round an
    eyebolt's eye (gap: between the end and the standing part, so a rope drawn as one tube does not touch itself).
    Returns the (p, q) points in that order"""
    q0 = np.array([-rho * math.cos(a0), -rho * math.sin(a0)])
    m0 = np.array([math.sin(a0), -math.cos(a0)])
    arc = np.linspace(-(math.pi - a0), math.pi - a0, 25)
    chord = float(np.linalg.norm(q0 - np.array([-p1, -r])))
    return np.concatenate([
        _hermite(np.array([-p1, -r]), np.array([1.0, 0.0]) * chord, q0, m0 * chord, k)[:-1],
        np.stack([rho * np.cos(arc), rho * np.sin(arc)], -1)[:-1],
        _hermite(q0 * np.array([1.0, -1.0]), np.array([-m0[0], m0[1]]) * chord,      # leaving the arc as it runs
                 np.array([-p1, r + gap]), np.array([-1.0, 0.0]) * chord, k),
        np.stack([np.linspace(-p1, -p1 - tail, 12)[1:], np.full(11, r + gap)], -1)])


def _hermite(p0, m0, p1, m1, k):
    t = np.linspace(0.0, 1.0, k + 1)[:, None]
    return ((2 * t ** 3 - 3 * t ** 2 + 1) * p0 + (t ** 3 - 2 * t ** 2 + t) * m0 + (-2 * t ** 3 + 3 * t ** 2) * p1 +
            (t ** 3 - t ** 2) * m1)


def _laid(mesh, C, R, lay, strands=3, n=8, mat="Cable", sense=-1.0, phase=0.0):
    """a rope of radius R laid up of `strands` ropes (round, each touching its neighbours) along the centre line C,
    one turn of the lay every `lay` (sense -1: left-handed in a right-handed frame; the ship's frame is the game's, its
    mirror, where -1 shows right-handed)"""
    T, A, B = _frames(C, False)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    r_s = R / (1.0 + 1.0 / math.sin(math.pi / strands))
    r_h = R - r_s
    for k in range(strands):
        th = phase + 2 * math.pi * k / strands + sense * 2 * math.pi * s / lay
        V, F = _tube_open(C + r_h * (np.cos(th)[:, None] * A + np.sin(th)[:, None] * B), r_s, n)
        mesh.add(V, F, mat)
    return r_s


def _rows_solid(rows):
    """A closed solid of revolution through rows going round its meridian: each row a point on the axis (3,) or a ring
    (n, 3) of points at the same angles; consecutive rows joined (fans at axis points); faces turned out."""
    V, idx = [], []
    for r in rows:
        r = np.asarray(r, float)
        if r.ndim == 1:
            idx.append([len(V)])
            V.append(r)
        else:
            idx.append(list(range(len(V), len(V) + len(r))))
            V += list(r)
    V = np.array(V)
    F = []
    for a, b in zip(idx[:-1], idx[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            n = len(b)
            F += [(a[0], b[(i + 1) % n], b[i]) for i in range(n)]
        elif len(b) == 1:
            n = len(a)
            F += [(a[i], a[(i + 1) % n], b[0]) for i in range(n)]
        else:
            n = len(a)
            F += [(a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]) for i in range(n)]
    if signed_volume(V, F) < 0:
        F = [f[::-1] for f in F]
    return V, F


def _slab(part, outline, holes, half, mat):
    """a plate in the XZ plane over outline (k, 2) of (x, z) less holes, y from -half to +half; faces out"""
    import head
    head.slab(part, outline, holes, 0.03, lambda P2, d: np.stack([P2[:, 0], d, P2[:, 1]], -1),
              lambda P2: np.full(len(P2), half), mat)


def cat_relief(x, y):
    """The cat's face carved on a cathead's end, as a height from 0 to 1 over the unit disc (x across the cathead, y up
    it): a ruffed mane round the rim, the face's mound, two ears, brows over sunk eyes with their balls, the nose's
    ridge, the muzzle's two lobes and the mouth's groove under them; 0 at the rim."""
    x, y = np.asarray(x, float), np.asarray(y, float)

    def g(cx, cy, sx, sy):
        return np.exp(-((x - cx) / sx) ** 2 - ((y - cy) / sy) ** 2)

    r = np.hypot(x, y)
    a = np.arctan2(y, x)
    mane = 0.42 * np.sqrt(np.clip(1.0 - r * r, 0.0, 1.0)) * (1.0 + 0.14 * np.cos(14 * a) * smoothstep((r - 0.6) / 0.2))
    face = 0.34 * np.sqrt(np.clip(1.0 - (x / 0.62) ** 2 - ((y + 0.04) / 0.66) ** 2, 0.0, 1.0))
    ears = 0.26 * (g(0.42, 0.56, 0.15, 0.15) + g(-0.42, 0.56, 0.15, 0.15))
    brow = 0.10 * (g(0.22, 0.25, 0.16, 0.05) + g(-0.22, 0.25, 0.16, 0.05))
    eyes = -0.20 * (g(0.22, 0.12, 0.10, 0.055) + g(-0.22, 0.12, 0.10, 0.055)) + \
        0.12 * (g(0.22, 0.12, 0.045, 0.04) + g(-0.22, 0.12, 0.045, 0.04))
    nose = 0.20 * g(0.0, -0.08, 0.07, 0.18) + 0.06 * g(0.0, -0.22, 0.10, 0.05)
    muzzle = 0.18 * (g(0.12, -0.32, 0.12, 0.10) + g(-0.12, -0.32, 0.12, 0.10))
    mouth = -0.14 * g(0.0, -0.45, 0.16, 0.025)
    h = np.clip(mane + face + ears + brow + eyes + nose + muzzle + mouth, 0.0, None)
    return h * smoothstep((1.0 - r) / 0.12) / 1.05


# ---- the ground tackle on the ship ----------------------------------------------------------------------------------
class Anchors:
    """The anchors as the ship carries them (starboard; each part's side says whether it is mirrored for port): the
    catheads, the bowers catted and fished under them, the billboards their bills rest on, the hawse holes with their
    bolsters and linings, the cables bent to the bowers' rings and led in at the hawse, the cat stoppers and shank
    painters (build). info: what the build reports (build.json's anchors) and the game reads (anchors.json)"""

    STEPS = ("cathead", "hawse", "bowers", "billboards", "cables", "stoppers", "painters")

    def __init__(self, L, rig, sk, hd, skin_parts, card=None):
        self.L, self.rig, self.sk, self.hd, self.skin = L, rig, sk, hd, skin_parts
        self.card = card or load_card()
        self.meshes, self.info = {}, {}

    def build(self):
        """every part, in order (each step uses what the ones before it placed), then the six anchors' sizes"""
        for step in self.STEPS:
            getattr(self, step)()
        self.sizes()
        return self

    def sizes(self):
        """each anchor's size as built to its weight (info's anchors): the slices that stow the sheet, stream and kedge
        anchors (anchors_1797.json's stow) build them from these"""
        out = {}
        for key, a in self.card["anchors"].items():
            an = self.bower["an"] if key in ("best_bower", "small_bower") else Anchor(self.card, a["lb"], name=key).solve()
            out[key] = {"lb": a["lb"], "stow": a["stow"], "side": "starboard" if a["side"] > 0 else "port",
                        "iron_kg": round(an.iron_kg, 1),
                        "shank_ft": round(an.Ls / FT, 2), "stock_ft": round(an.L_stock / FT, 2),
                        "pea_to_pea_ft": round(2 * an.R * math.sin(an.th) / FT, 2),
                        "throat_in": round(an.a_t / IN, 2), "ring_ft": round(an.D_ring / FT, 2)}
        self.info["anchors"] = out

    def mesh(self, name, side):
        if name not in self.meshes:
            self.meshes[name] = (Mesh(), side)
        return self.meshes[name][0]

    def cap_edge(self, x):
        """the rail cap's outer edge (y) and its top there (z) at x, starboard: the cap's section by the plane at x"""
        V, F = np.asarray(self.skin["RailCap"][0], float), self.skin["RailCap"][1]
        pts = []
        for f in F:
            for k in range(len(f)):
                a, b = V[f[k]], V[f[(k + 1) % len(f)]]
                if (a[0] - x) * (b[0] - x) < 0:
                    pts.append(a + (x - a[0]) / (b[0] - a[0]) * (b - a))
        P = np.array(pts)
        P = P[P[:, 1] > 0]
        y = float(P[:, 1].max())
        return y, float(P[P[:, 1] > y - 0.05][:, 2].max())

    def cat_frame(self):
        """the starboard cathead's frame: C0 on its axis over the rail cap's outer edge (its underside on the cap's top
        edge there), A along it (out and up), S across it (level, aft and outboard), U up from it (A, S, U right-handed)"""
        c = self.card["cathead"]
        st, pl = math.radians(c["steeve_deg"]), math.radians(c["plan_deg"])
        A = np.array([math.cos(st) * math.cos(pl), math.cos(st) * math.sin(pl), math.sin(st)])
        S = np.array([-math.sin(pl), math.cos(pl), 0.0])
        U = np.cross(A, S)
        y, z = self.cap_edge(c["rail_x"])
        C0 = np.array([c["rail_x"], y, z + 0.5 * c["side_in"][1] * IN / math.cos(st)])
        return C0, A, S, U

    def cat_size(self, s):
        """the cathead's breadth (along S) and depth (along U) at s along it (the rail's size inboard of the rail)"""
        c = self.card["cathead"]
        s1 = c["out_m"]
        return (np.interp(s, [0.0, s1], [c["side_in"][0] * IN, c["end_side_in"][0] * IN]),
                np.interp(s, [0.0, s1], [c["side_in"][1] * IN, c["end_side_in"][1] * IN]))

    def heel_cut(self, C0, A, S, U, w0, d0):
        """Where the cathead's heel is cut off inside the bulwark (starboard): a plane square to the bulwark's inner
        face as fitted over the cathead's own footprint on it, heel_proud_m inboard of the most inboard point of the
        bulwark's inner face, its top or the rail cap that lies within the cathead's section (the cap overhangs the
        bulwark inside: the heel covers it). Returns (n, k): the plane n . (x - C0) = k, n inboard"""
        def inside(name, grow=0.0):
            V, F = np.asarray(self.skin[name][0], float), self.skin[name][1]
            T = np.array([(f[0], f[k], f[k + 1]) for f in F for k in range(1, len(f) - 1)])
            T = T[np.linalg.norm(V[T].mean(1) - C0, axis=1) < 1.5]
            P = _samples(V[T], 0.01)
            Q = P - C0
            ok = (np.abs(Q @ S) <= 0.5 * w0 + grow) & (np.abs(Q @ U) <= 0.5 * d0 + grow) & (Q @ A < 0.5) & \
                (Q @ A > -1.5)
            return P[ok]
        B = inside("BulwarkIn", 0.15)                  # the face about the footprint, for its plane
        Q0 = B.mean(0)
        _, _, vt = np.linalg.svd(B - Q0)
        n = vt[2] if vt[2][1] < 0 else -vt[2]
        within = [P for P in (inside("BulwarkIn"), inside("BulwarkTop"), inside("RailCap")) if len(P)]
        k = max(float(np.max((P - C0) @ n)) for P in within)
        return n, k + self.card["cathead"]["heel_proud_m"]

    def cathead(self):
        """The starboard cathead: a square oak timber (painted with the side) from its heel on the rail out over the
        bow, its breadth and depth easing to the end; three slots through it near the end, each with its sheave on one
        iron pin across (heads on both sides) for the cat fall; a hole either side of them for the cat stopper; the
        cat's face carved on the end. Keys for the gear that hangs from it: self.cat"""
        import guns
        import head
        c = self.card["cathead"]
        C0, A, S, U = self.cat_frame()
        s1 = c["out_m"]
        w0, d0 = self.cat_size(0.0)
        w1, _ = self.cat_size(s1)
        # the heel: cut off just inside the bulwark and the rail cap (heel_cut), where the cathead comes out of the
        # rail: s_cut(t, d) is where the cathead's line at (t, d) across it meets that plane
        n, k0 = self.heel_cut(C0, A, S, U, w0, d0)

        def s_cut(t, d):
            return (k0 - t * (n @ S) - d * (n @ U)) / (n @ A)

        s0 = min(float(s_cut(t, dd)) for t in (-0.5 * w0, 0.5 * w0) for dd in (-0.5 * d0, 0.5 * d0))
        d_sh, t_sh = c["sheave_in"][0] * IN, c["sheave_in"][1] * IN
        slot = c["slot_in"] * IN
        pitch = slot + c["cheek_in"] * IN
        tcs = (np.arange(c["sheaves"]) - 0.5 * (c["sheaves"] - 1)) * pitch
        sb = s1 - c["end_block_m"]
        sa = sb - d_sh - 1.0 * IN
        sm = 0.5 * (sa + sb)
        m = self.mesh("Cathead", "stbd")
        m.cur = "cathead"
        outline = np.array([(s0, -0.5 * w0), (0.0, -0.5 * w0), (s1, -0.5 * w1), (s1, 0.5 * w1), (0.0, 0.5 * w0),
                            (s0, 0.5 * w0)])
        holes = [np.array([(sa, t - 0.5 * slot), (sb, t - 0.5 * slot), (sb, t + 0.5 * slot), (sa, t + 0.5 * slot)])
                 for t in tcs]
        # the cat stopper's two holes, square through the cathead: one in the end block, one inboard of the sheaves
        cs = self.card["stopper"]
        r_h = 0.5 * cs["circ_in"] / math.pi * IN + cs["hole_gap_in"] * IN
        s_holes = (sb + 0.5 * c["end_block_m"], sa - cs["hole_in_m"])
        ph = np.arange(12) * 2 * math.pi / 12
        holes += [np.stack([s_h + r_h * np.cos(ph), r_h * np.sin(ph)], -1) for s_h in s_holes]

        def to3d(P2, d):
            s, t = P2[:, 0].copy(), P2[:, 1]
            d = np.broadcast_to(np.asarray(d, float).reshape(-1), s.shape)
            inb = s < 0                                       # inboard of the rail: [s0, 0] stretched to [s_cut, 0]
            s[inb] *= s_cut(t[inb], d[inb]) / s0
            return C0 + s[:, None] * A + t[:, None] * S + d[:, None] * U

        head.slab(m, outline, holes, 0.25, to3d, lambda P2: 0.5 * self.cat_size(P2[:, 0])[1], "HullBlack")
        # the sheaves (lignum vitae, a groove round each for the fall) and their pin
        m.cur = "sheave"
        R, g = 0.5 * d_sh, c["groove_in"] * IN
        e = 0.12 * IN
        prof = [(-0.5 * t_sh, 0.0), (-0.5 * t_sh, R - e), (-0.5 * t_sh + e, R), (-g, R), (-0.7 * g, R - 0.5 * g),
                (0.0, R - 0.7 * g), (0.7 * g, R - 0.5 * g), (g, R), (0.5 * t_sh - e, R), (0.5 * t_sh, R - e),
                (0.5 * t_sh, 0.0)]
        for t in tcs:
            guns.lathe_closed(m, prof, "Sheave", 24, guns.frame(C0 + sm * A + t * S, S, U))
        m.cur = "pin"
        hw = 0.5 * self.cat_size(sm)[0]
        o = C0 + sm * A
        guns.cylinder(m, o - S * (hw + 0.3 * IN), o + S * (hw + 0.3 * IN), 0.5 * c["pin_in"] * IN, FITTING, n=12)
        for sg in (1.0, -1.0):
            guns.cylinder(m, o + sg * S * (hw - 0.002), o + sg * S * (hw + c["pin_head_in"][1] * IN),
                          0.5 * c["pin_head_in"][0] * IN, FITTING, n=14)
        # the cat's face on the end
        m.cur = "face"
        self.cat_face(m, C0 + s1 * A, A, S, U, c["face_r_m"], c["face_proud_in"] * IN)
        self.cat = {"C0": C0, "A": A, "S": S, "U": U, "s_sheave": sm, "s_slots": (sa, sb), "slots_t": tcs,
                    "end": C0 + s1 * A, "sheave_R": R, "stopper_holes": s_holes}
        heel = [C0 + s_cut(t, dd) * A + t * S + dd * U for t in (-0.5 * w0, 0.5 * w0) for dd in (-0.5 * d0, 0.5 * d0)]
        self.info["cathead"] = {"end_m": np.round(C0 + s1 * A, 3).tolist(), "heel_inboard_of_rail_m":
                                [round(-float(s_cut(t, dd)), 3) for t in (-0.5 * w0, 0.5 * w0)
                                 for dd in (-0.5 * d0, 0.5 * d0)],
                                "heel_z_m": [round(float(min(h[2] for h in heel)), 3),
                                             round(float(max(h[2] for h in heel)), 3)],
                                "length_m": round(float(s1 - s0), 3)}

    def cat_face(self, m, P, A, S, U, rho, H, nr=16, nt=56):
        """the cat's face (cat_relief) on a disc of radius rho on the end face at P (its outward normal A, S across and
        U up), standing up to H proud of it; its rim 1.5 mm proud and its back 2 mm inside the end, so no face of it
        lies in the end's plane"""
        r = np.linspace(0.0, 1.0, nr + 1)[1:]
        th = np.arange(nt) * 2 * math.pi / nt
        R, TH = np.meshgrid(r, th, indexing="ij")
        X, Y = R * np.cos(TH), R * np.sin(TH)
        h = 0.0015 + H * cat_relief(X, Y)
        top = P + rho * (X[..., None] * S + Y[..., None] * U) + h[..., None] * A          # (nr, nt, 3)
        c0 = P + (0.0015 + H * float(cat_relief(0.0, 0.0))) * A
        back = P + rho * (np.cos(th)[:, None] * S + np.sin(th)[:, None] * U) - 0.002 * A
        V = np.concatenate([[c0], top.reshape(-1, 3), back])
        F = [(0, 1 + j, 1 + (j + 1) % nt) for j in range(nt)]
        for i in range(nr - 1):
            for j in range(nt):
                a, b = 1 + i * nt + j, 1 + i * nt + (j + 1) % nt
                F.append((a, a + nt, b + nt, b))
        kb = 1 + nr * nt
        last = 1 + (nr - 1) * nt
        for j in range(nt):
            F.append((last + j, kb + j, kb + (j + 1) % nt, last + (j + 1) % nt))
        F.append(tuple(kb + j for j in range(nt - 1, -1, -1)))
        if signed_volume(V, F) < 0:
            F = [f[::-1] for f in F]
        m.add(V, F, "Gilt")

    # ---- the hawse holes -------------------------------------------------------------------------------------------
    def hawse_axis(self):
        """the bores' inboard direction (starboard): aft, turned axis_deg[0] inboard of fore and aft, rising axis_deg[1]"""
        tn, rs = (math.radians(a) for a in self.card["hawse"]["axis_deg"])
        return np.array([-math.cos(rs) * math.cos(tn), -math.cos(rs) * math.sin(tn), math.sin(rs)])

    def to_hull(self, Q, n):
        """each point Q moved back along -n (one direction, or one per point) onto the planked outside (hull_out's
        surface, whose points stand off the frames' (x, z) along the normal): the line's crossing with the surface's
        tangent plane, the surface point's (x, z) moved on by what still separates them, until they agree"""
        Q = np.asarray(Q, float)
        n = np.broadcast_to(np.asarray(n, float), Q.shape)
        xz = Q[:, [0, 2]].copy()
        R = Q
        for _ in range(40):
            P, N = self.hd.hull_out(xz[:, 0], xz[:, 1])
            t = np.einsum("ij,ij->i", Q - P, N) / np.einsum("ij,ij->i", N, n)
            R = Q - t[:, None] * n
            d = R - P
            xz += d[:, [0, 2]]
            if np.abs(d).max() < 1e-7:
                break
        return R

    def hawse(self):
        """The hawse holes (starboard; mirrored for port): two bores through the bow between the cheeks, under the
        upper cheek, each lined with lead lapped over its mouth and capped cap_m inside the planking (the gun deck,
        slice 12, opens them), in one oak bolster standing off the planking round both. cut_hawse cuts the skin."""
        import head
        h = self.card["hawse"]
        d_in = self.hawse_axis()
        r_b, t_l, lip = 0.5 * h["bore_in"] * IN, h["lead_in"] * IN, h["lip_in"] * IN
        X = np.array(h["holes"], float)
        P, N = self.hd.hull_out(X[:, 0], X[:, 1])
        n_b = unit(N.mean(0))
        e1 = unit((P[1] - P[0]) - ((P[1] - P[0]) @ n_b) * n_b)
        e2 = np.cross(n_b, e1)
        if e2[2] < 0:
            e1, e2 = -e1, -e2
        O = P.mean(0) + n_b * h["bolster_proud_m"]
        e_a = unit(np.cross(d_in, n_b))
        e_b = np.cross(d_in, e_a)
        th = np.arange(24) * 2 * math.pi / 24
        U = np.cos(th)[:, None] * e_a + np.sin(th)[:, None] * e_b         # the bore's radial directions

        def on_plane(Pk, r, c):
            """the bore's cylinder of radius r about the axis through Pk, where it meets the plane through c (normal n_b)"""
            B = Pk + r * U
            tau = ((c - B) @ n_b) / float(d_in @ n_b)
            return B + tau[:, None] * d_in

        # the bolster: a stadium round both mouths, its face flat, its back on the planking (let in embed)
        mouths = [on_plane(Pk, r_b, O) for Pk in P]
        uv = [np.stack([(Q - O) @ e1, (Q - O) @ e2], -1) for Q in mouths]
        cen = [q.mean(0) for q in uv]
        hh = r_b + h["bolster_margin_m"]
        ext = max(float(np.abs(q[:, 0] - c[0]).max()) for q, c in zip(uv, cen)) - r_b
        ua, ub = min(cen[0][0], cen[1][0]) - ext, max(cen[0][0], cen[1][0]) + ext
        vm = 0.5 * (cen[0][1] + cen[1][1])
        a1 = np.linspace(-0.5 * math.pi, 0.5 * math.pi, 13)
        a2 = np.linspace(0.5 * math.pi, 1.5 * math.pi, 13)
        outline = np.concatenate([np.stack([ub + hh * np.cos(a1), vm + hh * np.sin(a1)], -1),
                                  np.stack([ua + hh * np.cos(a2), vm + hh * np.sin(a2)], -1)])
        embed = h["bolster_embed_m"]

        def to3d(P2, d):
            """the face flat; the back on the planking, reached square to the face at the outline but along the bores
            at the holes (bored through the bolster with the planking, so each hole's wall is its bore's), eased from
            one to the other across the margin between them"""
            d = np.asarray(d, float).reshape(-1)
            F = O + P2[:, :1] * e1 + P2[:, 1:2] * e2
            gap = np.min([np.linalg.norm(np.cross(F - Pk, d_in), axis=1) for Pk in P], axis=0) - r_b
            w = np.clip(1.0 - gap / h["bolster_margin_m"], 0.0, 1.0)[:, None]
            n_back = unit(w * -d_in + (1.0 - w) * n_b)
            B = self.to_hull(F, n_back) - n_back * embed
            return F * (0.5 * (1 + d))[:, None] + B * (0.5 * (1 - d))[:, None]

        m = self.mesh("HawseBolster", "stbd")
        m.cur = "bolster"
        head.slab(m, outline, [q[::-1] for q in uv], 0.06, to3d, lambda P2: np.ones(len(P2)), "HullBlack")
        # the linings: lead tubes, a lip lapped over the bolster's face, capped inside
        m = self.mesh("HawseLining", "stbd")
        m.cur = "lining"
        tau_in = h["cap_m"]
        for Pk in P:
            rows = [Pk + tau_in * d_in, Pk + tau_in * d_in + r_b * U, on_plane(Pk, r_b, O - 0.001 * n_b),
                    on_plane(Pk, r_b + lip, O - 0.001 * n_b), on_plane(Pk, r_b + lip, O + t_l * n_b),
                    on_plane(Pk, r_b - t_l, O + t_l * n_b), Pk + (tau_in - t_l) * d_in + (r_b - t_l) * U,
                    Pk + (tau_in - t_l) * d_in]
            V, F = _rows_solid(rows)
            m.add(V, F, LEAD)
        self.hawse_info = {"P": P, "N": N, "d_in": d_in, "n_b": n_b, "O": O, "e1": e1, "e2": e2, "r_b": r_b,
                           "mouth_c": [Pk + float(((O - Pk) @ n_b) / (d_in @ n_b)) * d_in for Pk in P]}
        self.info["hawse"] = {"mouths_m": np.round(P, 3).tolist(), "bolster_face_m": np.round(O, 3).tolist(),
                              "axis": np.round(d_in, 3).tolist(),
                              "bore_off_face_deg": round(math.degrees(math.acos(-float(d_in @ n_b))), 1)}

    def cut_hawse(self, skin):
        """cut each bore through the skin parts that lie across it (a 16-sided prism a little wider than the bore, from
        just outside the bolster to the lining's cap), in place: skin[name] = (V, F, M, side)"""
        import head
        hi = self.hawse_info
        d_in, r = hi["d_in"], hi["r_b"] + 0.006
        e_a = unit(np.cross(d_in, EZ))
        e_b = np.cross(d_in, e_a)
        gone = {}
        for name in self.card["hawse"]["cut_parts"]:
            V, F, M, side = skin[name]
            n0 = 0
            for Pk in hi["P"]:
                cuts = [(Pk - 0.3 * d_in, -d_in), (Pk + (self.card["hawse"]["cap_m"] + 0.02) * d_in, d_in)]
                for a in np.arange(16) * 2 * math.pi / 16:
                    nn = math.cos(a) * e_a + math.sin(a) * e_b
                    cuts.append((Pk + r * nn, nn))
                near = lambda p, Pk=Pk: float(np.linalg.norm(p - Pk)) < 0.7          # noqa: E731
                V, F, M, n, _ = head.cut_away(V, F, M, cuts, near)
                n0 += n
            skin[name] = (V, F, M, side)
            gone[name] = n0
        self.info.setdefault("hawse", {})["cut_faces"] = gone

    # ---- the bowers, catted and fished --------------------------------------------------------------------------
    def ring_top(self, an):
        """where the cat stopper holds a bower's ring (starboard): the top of the ring's bar, its pudden gap_m under
        the cathead's underside at the sheaves"""
        c, f = self.card["cathead"], self.card["fished"]
        C0, A, S, U = self.cat_frame()
        sb = c["out_m"] - c["end_block_m"]
        sm = sb - 0.5 * (c["sheave_in"][0] * IN + 1.0 * IN)
        return C0 + sm * A - U * (0.5 * self.cat_size(sm)[1]) - EZ * (f["stopper_gap_m"] + an.r_bar + an.pudden)

    def bill_on_bow(self, x_b, H, d, off, foot=False):
        """the highest point at x_b, off out from the planking along its normal, that lies d from H (None if none);
        foot: also the point on the planking under it and the normal there"""
        zs = np.linspace(1.0, float(H[2]), 240)
        P, N = self.hd.hull_out(np.full(len(zs), float(x_b)), zs)
        Q = P + N * off
        dd = np.linalg.norm(Q - H, axis=1)
        s = np.where((dd[:-1] - d) * (dd[1:] - d) <= 0)[0]
        if not len(s):
            return None
        k = s[-1]
        t = (d - dd[k]) / (dd[k + 1] - dd[k])
        if foot:
            return Q[k] + t * (Q[k + 1] - Q[k]), P[k] + t * (P[k + 1] - P[k]), unit(N[k] + t * (N[k + 1] - N[k]))
        return Q[k] + t * (Q[k + 1] - Q[k])

    def fished_pose(self, an, x_b, roll=None, off=None):
        """A bower catted and fished (starboard): its ring held by the cat stopper under the cathead (ring_top), the
        bill of its inner fluke (the arm on +X in the anchor's frame) on the billboard at x_b, off out from the
        planking, and the anchor turned about the line from its eye to that bill as its weight takes it (its centre of
        mass under the line) and then roll (degrees) further. The ring turns in the eye to hang from the stopper.
        Returns {R, o: the anchor's frame in the ship's (p_ship = R p + o), eye, ring_top, bill, ring_u (the ring's
        direction in the anchor's frame), roll_natural (its hang's roll from the first try, degrees), below (how far
        its centre of mass hangs under the eye-bill line)}"""
        f = self.card["fished"]
        off = f["bill_off_m"] if off is None else off
        T = self.ring_top(an)
        Rc = an.key["ring_R"]
        h_loc, b_loc = an.key["eye"], an.key["bill"][0]
        d_hb = float(np.linalg.norm(b_loc - h_loc))
        G_loc = an.centre_of_mass()

        def pose(psi):
            H = T - 2 * Rc * EZ
            for _ in range(8):
                B = self.bill_on_bow(x_b, H, d_hb, off)
                if B is None:
                    return None
                R = rot_axis(B - H, psi) @ rot_between(b_loc - h_loc, B - H)
                u = R.T @ EZ
                u = unit(u - (u @ EY) * EY)
                H1 = T - 2 * Rc * (R @ u)
                done = float(np.linalg.norm(H1 - H)) < 1e-6
                H = H1
                if done:
                    break
            B, Pf, Nf = self.bill_on_bow(x_b, H, d_hb, off, foot=True)
            R = rot_axis(B - H, psi) @ rot_between(b_loc - h_loc, B - H)
            o = H - R @ h_loc
            ax = unit(B - H)
            g = R @ G_loc + o - H
            below = -float((g - (g @ ax) * ax)[2])
            return {"R": R, "o": o, "eye": H, "ring_top": T, "bill": B, "bill_foot": Pf, "bill_normal": Nf, "ring_u": u,
                    "below": below}

        tries = [(pose(math.radians(a)), a) for a in range(0, 360, 10)]
        tries = [(p, a) for p, a in tries if p is not None]
        if not tries:
            raise ValueError(f"no fished pose reaches x_b {x_b}")
        _, a0 = max(tries, key=lambda t: t[0]["below"])
        lo, hi = math.radians(a0 - 10), math.radians(a0 + 10)
        g = (math.sqrt(5) - 1) / 2

        def below(psi):                                          # a turn that can't reach the bill hangs no lower
            p = pose(psi)
            return -math.inf if p is None else p["below"]

        for _ in range(40):                                      # golden section on the hang
            m1, m2 = hi - g * (hi - lo), lo + g * (hi - lo)
            if below(m1) > below(m2):
                hi = m2
            else:
                lo = m1
        psi_n = 0.5 * (lo + hi)
        out = pose(psi_n + math.radians(f["roll_from_natural_deg"] if roll is None else roll))
        if out is None:
            raise ValueError(f"the fished pose at x_b {x_b} can't reach its bill rolled that far")
        out["roll_natural"] = math.degrees(psi_n)
        return out

    def bowers(self):
        """The two bowers catted and fished (fished_pose at the card's bill_x): the best bower to starboard, the small
        bower to port. They weigh the same, so the port one is the starboard one mirrored (an anchor is its own mirror
        image). Keys for the gear that holds them: self.bower"""
        a = self.card["anchors"]
        if a["best_bower"]["lb"] != a["small_bower"]["lb"]:
            raise ValueError("the bowers differ in weight: build each on its own side")
        an = Anchor(self.card, a["best_bower"]["lb"], name="best_bower").solve()
        p = self.fished_pose(an, self.card["fished"]["bill_x"])
        an.build_ring(an.key["eye"], p["ring_u"])
        T = np.eye(4)
        T[:3, :3], T[:3, 3] = p["R"], p["o"]
        m = self.mesh("Bower", "stbd")
        for M in (an.iron, an.stock, an.ring):
            m.extend(M, T)
        self.bower = dict(p, an=an, T=T)
        R, o = p["R"], p["o"]
        shank = R @ EZ
        self.info["bower"] = {
            "lb": a["best_bower"]["lb"], "iron_kg": round(an.iron_kg, 1), "shank_m": round(an.Ls, 3),
            "bill_x": self.card["fished"]["bill_x"], "bill_m": np.round(p["bill"], 3).tolist(),
            "ring_top_m": np.round(p["ring_top"], 3).tolist(), "crown_m": np.round(o, 3).tolist(),
            "shank_slope_deg": round(math.degrees(math.asin(float(shank[2]))), 1),
            "stock_off_level_deg": round(math.degrees(math.asin(abs(float((R @ EY)[2])))), 1),
            "roll_natural_deg": round(p["roll_natural"], 2), "cog_below_eye_bill_m": round(p["below"], 3),
            "frame": {"origin_m": np.round(o, 5).tolist(), "x": np.round(R[:, 0], 6).tolist(),
                      "y": np.round(R[:, 1], 6).tolist(), "z": np.round(R[:, 2], 6).tolist()}}

    def billboards(self):
        """The billboard under each bower's bill (starboard; mirrored for port): an oak board bent to the bow, its back
        let into the planking, faced with an iron plate, centred under the bill. The board is as thick as brings the
        plate's face to the bill (the bill rests on it 2 mm deep); info says how thick that is against the card's"""
        import head
        b, bw = self.card["billboard"], self.bower
        P0, N0 = bw["bill_foot"], bw["bill_normal"]
        e2 = unit(EZ - (EZ @ N0) * N0)                          # up the side
        e1 = np.cross(e2, N0)                                   # aft along it ((e1, e2, N0) right-handed)
        tp, embed = b["plate_in"] * IN, b["embed_m"]
        V, _, _ = self.meshes["Bower"][0].arrays()
        near = V[np.linalg.norm(V - bw["bill"], axis=1) < 0.4]

        def planking(Q):
            """the points on the planking under Q (along -N0) and their heights over it"""
            H = self.to_hull(Q, N0)
            return H, (Q - H) @ N0

        w, h = b["size_m"]
        uv = np.stack([(near - P0) @ e1, (near - P0) @ e2], -1)
        inside = (np.abs(uv[:, 0]) < 0.5 * w - b["plate_margin_m"]) & (np.abs(uv[:, 1]) < 0.5 * h - b["plate_margin_m"])
        _, hts = planking(near[inside])
        face = float(hts.min()) + 0.002                         # the plate's face: the bill rests on it
        t = face - tp

        def to3d_fn(t0, t1):
            def to3d(P2, d):
                d = np.asarray(d, float).reshape(-1)
                H, _ = planking(P0 + P2[:, :1] * e1 + P2[:, 1:2] * e2 + N0 * t)
                return H + N0 * (t1 * (0.5 * (1 + d)) + t0 * (0.5 * (1 - d)))[:, None]
            return to3d

        m = self.mesh("Billboard", "stbd")
        m.cur = "board"
        head.slab(m, rounded_rect(w, h, 0.04, n=4), [], 0.05, to3d_fn(-embed, t), lambda P2: np.ones(len(P2)), OAK)
        m.cur = "plate"
        mg = b["plate_margin_m"]
        head.slab(m, rounded_rect(w - 2 * mg, h - 2 * mg, 0.03, n=4), [], 0.05, to3d_fn(t - 0.002, face),
                  lambda P2: np.ones(len(P2)), FITTING)
        self.info["billboard"] = {"centre_m": np.round(P0, 3).tolist(), "board_in": round(t / IN, 2),
                                  "card_board_in": b["thick_in"], "plate_face_off_planking_m": round(face, 4)}

    def cable_line(self):
        """The starboard bower's cable's centre line: from inside its hawse hole (lying on the lining, toward where it
        is pulled at the mouth) out over the lip, through the card's via_m points, to the bower's ring; through the
        ring, round its bar (the clinch) and back alongside itself. Returns (C, clinch): C the points, clinch the
        frame of the clinch (Pbar, n_a: the cable's way through the ring, r_o: out from the ring's centre, t_b: along
        the bar, rho, r_c, the clinch's lead and tail)"""
        c, h = self.card["cable"], self.card["hawse"]
        hi, bw = self.hawse_info, self.bower
        an = bw["an"]
        r_c = 0.5 * c["circ_in"] / math.pi * IN
        r_b, t_l = hi["r_b"], h["lead_in"] * IN
        k = c["hole"]
        Pk, d_in, n_b, O = hi["P"][k], hi["d_in"], hi["n_b"], hi["O"]
        via = np.array(c["via_m"], float)
        # the mouth: where the bore's axis meets the lip's face; the cable lies on the lining toward its pull
        tau = float(((O + t_l * n_b - Pk) @ n_b) / (d_in @ n_b))
        mouth = Pk + tau * d_in
        w = unit(via[0] - mouth)
        e_p = unit(w - (w @ d_in) * d_in)
        off = (r_b - t_l) - r_c - 0.002
        S = [Pk + (h["cap_m"] - 0.03) * d_in + off * e_p, Pk + 0.5 * h["cap_m"] * d_in + off * e_p,
             mouth + off * e_p, mouth + off * e_p - c["bore_out_m"] * d_in]
        # the ring: its centre, its plane (u up it from the eye, e_s along the stock), the bar where the clinch takes it
        R, Rc = bw["R"], an.key["ring_R"]
        u = R @ bw["ring_u"]
        e_s = R @ EY
        Cr = bw["eye"] + u * Rc
        a = math.radians(c["clinch_deg"])
        Pbar = Cr + Rc * (math.cos(a) * u + math.sin(a) * e_s)
        r_o = math.cos(a) * u + math.sin(a) * e_s
        t_b = -math.sin(a) * u + math.cos(a) * e_s
        n_r = unit(np.cross(r_o, t_b))
        if float(n_r @ (Pbar - via[-1])) < 0:                  # through the ring away from the course's last point
            n_r, t_b = -n_r, -t_b
        g = math.radians(c["clinch_tilt_deg"])                 # the cable through the ring askew: turned about the bar
        n_a = math.cos(g) * n_r + math.sin(g) * r_o
        r_o = -math.sin(g) * n_r + math.cos(g) * r_o
        rho = an.r_bar + an.pudden + r_c
        p1, tail = c["eye_lead_m"], c["tail_m"]

        def X(pq):
            pq = np.atleast_2d(pq)
            return Pbar + pq[:, :1] * n_a + pq[:, 1:2] * r_o

        eye = _bar_turn(rho, r_c, p1, tail, math.radians(c["eye_open_deg"]))
        # the free part: straight out of the hole past the lip, each turn up the bow on an arc of at least
        # bend_min_of_diameter of the cable's thickness, into a straight lead alongside the tail for all its length and
        # lead_m past its end (the seizings take both parts); then the whole course at an even step, so the strands'
        # lay turns evenly along it
        poly = np.concatenate([S, via, X(np.array([[-p1 - tail - c["lead_m"], -r_c], [-p1, -r_c]]))])
        free, least = _course(poly, c["bend_min_of_diameter"] * 2 * r_c, 0.02)
        s_free = float(np.sum(np.linalg.norm(np.diff(free, axis=0), axis=1)))
        C = _even(np.concatenate([free, X(eye)[1:]]), 0.02)
        s_e = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
        return C, {"Pbar": Pbar, "n_a": n_a, "r_o": r_o, "t_b": t_b, "rho": rho, "r_c": r_c, "p1": p1, "tail": tail,
                   "n_free": int(np.searchsorted(s_e, s_free - 1e-6)) + 1, "least_bend_m": least}

    def cables(self):
        """The bowers' cables, both sides in one part: hemp, cable-laid (three ropes laid up left-handed),
        cable_line's course; the clinch held by its seizings (small stuff round both parts). A lay has a hand, which a
        mirror turns: the port cable is laid the other way round before it is mirrored, so both show left-handed in
        the game, whose frame the ship's is (Blender, right-handed, draws her as her mirror image)"""
        c = self.card["cable"]
        C, cl = self.cable_line()
        r_c = cl["r_c"]
        r_z = 0.5 * c["seizing_in"] / math.pi * IN
        p1, tail = cl["p1"], cl["tail"]
        m = self.mesh("Cable", "both")
        for sg in (1.0, -1.0):                                   # starboard, then port (laid, then mirrored)
            part = Mesh()
            part.cur = "cable"
            _laid(part, C, r_c, c["lay_of_diameter"] * 2 * r_c, c["strands"], n=8, mat="Cable", sense=sg)
            part.cur = "seizing"
            for k in range(c["clinch_seizings"]):
                p = -p1 - 0.15 - k * (tail - 0.35) / max(1, c["clinch_seizings"] - 1)
                for j in range(c["seizing_turns"]):
                    pj = p + (j - 0.5 * (c["seizing_turns"] - 1)) * 2.1 * r_z
                    ang = np.linspace(0.0, 2 * math.pi, 33)[:-1]
                    rr = r_c + r_z - 0.002
                    ring = []
                    for t in ang:                                # a stadium round both parts
                        q = (r_c if math.cos(t) > 0 else -r_c) + rr * math.cos(t)
                        ring.append(cl["Pbar"] + pj * cl["n_a"] + q * cl["r_o"] + rr * math.sin(t) * cl["t_b"])
                    V, F = _tube_loop(np.array(ring), r_z, 8)
                    part.add(V, F, TARRED)
            V, F, M = part.arrays()
            if sg < 0:
                V, F = V * np.array([1.0, -1.0, 1.0]), [f[::-1] for f in F]
            n0 = len(m.F)
            m.add(V, F, M)
            m.lab[n0:] = part.lab
        self.cable = {"C": C, **cl}
        L = float(np.sum(np.linalg.norm(np.diff(C, axis=0), axis=1)))
        self.info["cable"] = {"circ_in": c["circ_in"], "diameter_m": round(2 * r_c, 4), "length_m": round(L, 2),
                              "hole": c["hole"], "clinch_m": np.round(cl["Pbar"], 3).tolist(),
                              "least_bend_of_diameter": round(cl["least_bend_m"] / (2 * r_c), 3)}

    def _eyebolt(self, m, face, n, along, sp):
        """an iron eyebolt driven into a face (outward normal n), its eye standing off it in the plane of n and along;
        sp: eye_in [the eye's centre-line diameter, its bar's, the shank's] and into_in. Returns the eye's centre"""
        import guns
        n, along = unit(n), unit(along - (along @ n) * n)
        R, r, rs = 0.5 * sp["eye_in"][0] * IN, 0.5 * sp["eye_in"][1] * IN, 0.5 * sp["eye_in"][2] * IN
        c = face + n * (0.25 * IN + r + R)
        guns.torus(m, c, n, along, R, r, FITTING, n=16, m=8)
        guns.cylinder(m, face - n * sp["into_in"] * IN, face + n * (0.25 * IN + 1.2 * r), rs, FITTING, n=8)
        return c

    def _spliced_eye(self, mb, face, n, toward, along0, sp):
        """An iron eyebolt driven into a face (outward normal n) into mb, with a rope spliced round its eye that leads
        off toward the point `toward`. The eye stands in the plane of n and the square to the rope's lead (along0 when
        the rope leads straight off the face), so the rope passes through it square; its end goes round the eye's outer
        bar (_bar_turn, splice_gap_in clear of the iron) and back alongside the standing part for splice_m (the
        splice). sp: the rope's card. Returns (the end's centre line from its tip round the bar to the throat, the
        standing part's lead on from the throat alongside the splice, the eye's centre)"""
        n = unit(n)
        R_e, r_b = 0.5 * sp["eye_in"][0] * IN, 0.5 * sp["eye_in"][1] * IN
        r = 0.5 * sp["circ_in"] / math.pi * IN
        c = face + n * (0.25 * IN + r_b + R_e)
        lead = unit(toward - c)
        along = np.cross(n, lead)
        if np.linalg.norm(along) < 0.25:
            along = along0 - (along0 @ n) * n
        along = unit(along)
        self._eyebolt(mb, face, n, along, sp)
        Pbar = c + R_e * n
        n_a = -unit(lead - (lead @ along) * along)
        r_o = n - (n @ n_a) * n_a
        r_o = unit(r_o) if np.linalg.norm(r_o) > 0.2 else unit(np.cross(along, n_a))
        rho = r_b + r + sp["splice_gap_in"] * IN
        p1, tail = sp["throat_m"], sp["splice_m"]
        pq = _bar_turn(rho, r, p1, tail, math.radians(60.0), gap=sp.get("tail_gap_in", 0.0) * IN)[::-1]

        def X(q):
            return Pbar + q[:, :1] * n_a + q[:, 1:2] * r_o

        return X(pq), X(np.array([[-p1 - tail - 0.02, -r]]))[0], c

    @staticmethod
    def _rope_between(end_a, mid, end_b, rad, step):
        """a rope's centre line from one spliced end (_spliced_eye) through the points mid to another, its corners
        turned on rad, at an even step"""
        (sa, la, _), (sb, lb, _) = end_a, end_b
        P, _ = _course(np.concatenate([[sa[-1], la], mid, [lb, sb[-1]]]), rad, step)
        return _even(np.concatenate([sa[:-1], P, sb[::-1][1:]]), step)

    def stoppers(self):
        """The cat stopper (starboard; mirrored for port): a rope with a wall knot in each end, rove down through a hole
        in the cathead's end block outboard of the sheaves, round under the top of the bower's ring (the ring hangs on
        it) and up through a hole inboard of the sheaves, its knot on the cathead's top. Each leg leaves the ring's bar
        where it runs off it straight to the hole (the bar's tangent), and turns into the hole turn_below_m under the
        cathead"""
        c = self.card["stopper"]
        cat, bw = self.cat, self.bower
        an = bw["an"]
        C0, A, U = cat["C0"], cat["A"], cat["U"]
        r_s = 0.5 * c["circ_in"] / math.pi * IN
        T = bw["ring_top"]
        e_s = bw["R"] @ EY                                          # the ring's bar runs along e_s at its top
        a_h = unit(A - (A @ e_s) * e_s)
        v = np.cross(e_s, a_h)
        v = v if v[2] > 0 else -v
        rho = an.r_bar + an.pudden + r_s
        m = self.mesh("CatStopper", "stbd")
        m.cur = "stopper knot"
        kb, kh = c["knot_of_diameter"][0] * 2 * r_s, c["knot_of_diameter"][1] * 2 * r_s
        ends, legs, tops = [], [], []
        for s_h in cat["stopper_holes"]:
            half = 0.5 * self.cat_size(s_h)[1]
            top = C0 + s_h * A + U * half
            _wall_knot(m, top + U * 0.0005, U, A, kb, kh, "Hemp")
            tops.append(top)
            ends.append(top + U * 0.5 * kh)                         # the rope's end, inside its knot
            legs.append(top - U * (2 * half + c["turn_below_m"]))
        # round under the bar from the outboard leg's tangent point to the inboard leg's (angles in the plane square to
        # the bar, from a_h toward v: the rope runs the bar's way round from the outboard side under it), sliding along
        # the bar (e_s) evenly with its length from the one hole to the other, so each leg leaves the bar on its tangent
        ang, w, lp = [], [], []
        for P_, sg in zip(legs, (-1.0, 1.0)):
            x, y = float((P_ - T) @ a_h), float((P_ - T) @ v)
            D = math.hypot(x, y)
            be = math.acos(min(1.0, rho / D))
            ang.append(math.atan2(y, x) + sg * be)
            w.append(float((P_ - T) @ e_s))
            lp.append(D * math.sin(be))
        b0, b1 = ang
        if b1 > b0:
            b1 -= 2 * math.pi
        arc = rho * (b0 - b1)
        tot = lp[0] + arc + lp[1]
        ph = np.linspace(b0, b1, max(4, int(math.ceil(abs(b1 - b0) / math.radians(4.0)))) + 1)
        ww = w[0] + (w[1] - w[0]) * (lp[0] + np.linspace(0.0, arc, len(ph))) / tot
        wrap = T[None] + rho * (np.cos(ph)[:, None] * a_h[None] + np.sin(ph)[:, None] * v[None]) + ww[:, None] * e_s[None]
        P, least = _course(np.concatenate([[ends[0], legs[0]], wrap, [legs[1], ends[1]]]), c["bend_m"], 0.01)
        m.cur = "stopper"
        V, F = _tube_open(P, r_s, 8)
        m.add(V, F, "Hemp")
        self.info["stopper"] = {"circ_in": c["circ_in"], "holes_m": np.round(tops, 3).tolist(),
                                "wrap_deg": round(math.degrees(b0 - b1), 1),
                                "least_bend_of_diameter": round(least / (2 * r_s), 3)}

    def painters(self):
        """The shank painter (starboard; mirrored for port): a rope spliced to an eyebolt in the bow above the bower,
        down round its shank (a round turn) and back up to a second eyebolt beside the first, spliced there too. The
        eyebolts are AnchorEyebolts'"""
        c = self.card["painter"]
        bw = self.bower
        an, R, o = bw["an"], bw["R"], bw["o"]
        r_p = 0.5 * c["circ_in"] / math.pi * IN
        k = an.key
        z_loc = c["at_shank"] * k["eye"][2]
        sh = an.sh
        h0 = an.arm_depth(0.0) * k["a_t"]
        zA = 0.5 * h0
        a_side = float(np.interp(z_loc, [zA + 0.6 * k["a_t"], k["stock_z"] - 0.5 * k["stock_middle"]], [k["a_t"], k["a_s"]]))
        Sp = R @ np.array([0.0, 0.0, z_loc]) + o
        ax = R @ EZ
        # the eyebolts: on the planking rise_m above the shank's point, beside each other fore and aft
        Pm, Nm = self.hd.hull_out(np.array([Sp[0]]), np.array([Sp[2] + c["rise_m"]]))
        Pm, Nm = Pm[0], unit(Nm[0])
        e_f = unit(np.cross(Nm, EZ))
        e_f = e_f if e_f[0] > 0 else -e_f
        faces = [self.to_hull((Pm + sg * 0.5 * c["eyes_apart_m"] * e_f)[None], Nm)[0] for sg in (1.0, -1.0)]
        R_e, r_b = 0.5 * c["eye_in"][0] * IN, 0.5 * c["eye_in"][1] * IN
        eyes = [Q + Nm * (0.25 * IN + r_b + R_e) for Q in faces]
        mid = 0.5 * (eyes[0] + eyes[1])
        dn = unit((mid - Sp) - ((mid - Sp) @ ax) * ax)
        w = np.cross(ax, dn)
        side = 1.0 if float(w @ (eyes[0] - eyes[1])) > 0 else -1.0
        # the round turn hugs the shank: straight along its flats (bearing a millimetre), round its chamfered corners on
        # a radius rc over the rope's own (a tube bent tighter than its radius folds on itself): the section's octagon
        # in the anchor's frame, shrunk by rc, grown again by rc and the rope's radius
        rc, cut = 0.012, sh["chamfer"] * a_side * 1.4
        octa = rounded_rect(a_side - 2 * rc, a_side - 2 * rc, cut - (2 - math.sqrt(2)) * rc, n=2)
        dn_l = R.T @ dn
        phi = math.atan2(dn_l[1], dn_l[0]) + side * np.radians(np.arange(25.0, 335.01, 1.0))
        u = np.stack([np.cos(phi), np.sin(phi)], -1)
        Pl = octa[np.argmax(u @ octa.T, axis=1)] + (rc + r_p - 0.001) * u
        loop = o + np.stack([Pl[:, 0], Pl[:, 1], np.full(len(Pl), z_loc)], -1) @ R.T
        mb = self.mesh("AnchorEyebolts", "stbd")
        mb.cur = "painter eyebolt"
        ends = [self._spliced_eye(mb, Q, Nm, L0, EZ, c) for Q, L0 in ((faces[0], loop[0]), (faces[1], loop[-1]))]
        # each leg comes off the turn on a curve (a Hermite from jl up the leg to jl round the turn), and the whole
        # course is laid at an even step: the tube's rings never cross where it bends
        s_l = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(loop, axis=0), axis=1))])
        jl = 0.06
        i0, i1 = int(np.searchsorted(s_l, jl)), int(np.searchsorted(s_l, s_l[-1] - jl)) - 1
        legs = []
        for E, L0, B, tB in ((ends[0][1], loop[0], loop[i0], unit(loop[i0 + 1] - loop[i0 - 1])),
                             (ends[1][1], loop[-1], loop[i1], unit(loop[i1 - 1] - loop[i1 + 1]))):
            dl = unit(L0 - E)
            A = L0 - jl * dl
            ch = float(np.linalg.norm(B - A))
            legs.append(_hermite(A, dl * ch, B, tB * ch, 12))
        m = self.mesh("ShankPainter", "stbd")
        m.cur = "painter"
        P = self._rope_between(ends[0], np.concatenate([legs[0], loop[i0 + 1:i1], legs[1][::-1]]), ends[1], 0.036,
                               0.01)
        V, F = _tube_open(P, r_p, 8)
        m.add(V, F, "Hemp")
        self.info["painter"] = {"circ_in": c["circ_in"], "on_shank_m": np.round(Sp, 3).tolist(),
                                "eyes_m": np.round(eyes, 3).tolist()}

    def parts(self):
        """name -> (V, F, M, side): 'stbd' parts are the starboard half (mirror them for port), 'both' parts whole"""
        out = {}
        for name, (mesh, side) in self.meshes.items():
            V, F, M = mesh.arrays()
            out[name] = (V, F, M, side)
        return out
