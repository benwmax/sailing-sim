"""The long guns' own gear about the gun deck (docs/shipkit-12; gundeck_1797.json gun_gear): what slice 8 left for the
deck slice.

* Housed for sea, a wooden tompion in each muzzle and a lead apron over each vent and lock: meshes in the barrel's own
  frame (guns.Long24's, inches scaled to metres like the guns' meshes), copied to every housed gun (Guns_Housed).
* Over each gun, athwartships in the bay between the spar deck's beams over its port, its two staffs (sponge and
  rammer, worm and ladle) and two handspikes, each on two iron hangers, hung under the beams' underside so they pass
  under the carlings (GunImplements).
* Its shot in a garland on the deck along the waterway's cove, in the space forward of its port (ShotGarlands).
* Each lid's two lanyards: an eyebolt and ring at each hinge strap's end, built into the lid (lid_rings: they turn with
  it); the lanyard from the ring up to a lead-lined hole over the port, in through it and down to a cleat beside the
  port (LanyardFittings: the lead bushes and the cleats; LidLanyards: the rope inside, laid taut down the side's true
  inner face, and outside the bridle ports' lids, which never open); the part outside in two poses, down the shut lid
  with the guns housed (LidLanyards_Shut) and taut to the open lid with them run in or out (LidLanyards_Open, from the
  lids' openings the guns' room check finds).

    from gungear import GunGear;  gg = GunGear(gd);  rings = gg.lid_rings()   # {lid name: (V, F, M)}: the skin's lids
    gg.build(overhead, gn);  gg.parts(), gg.meshes, gg.instances()
    gg.lanyards_open(openings)              # {lid object name: degrees}, after guns.Guns.room

Metres in the ship's frame (X forward, Y starboard, Z up) but the tompion and apron. Runs in Blender's Python (mathutils'
BVH: the apron's drape over the lock, the hangers' reach to the deck above).
"""
import json
import math
import os

import numpy as np

import guns as G
from deck import solid
from rigging import fillet, tube
from spars import unit

HERE = os.path.dirname(os.path.abspath(__file__))
IN = G.IN
EX, EY, EZ = np.eye(3)
FLIP = np.array([1.0, -1.0, 1.0])
# the rays laid_off casts for a ball's clearance: (across, across, the ball's depth there), in units of its radius
LAY_DISC = [(0.0, 0.0, 1.0)] + [(rho * math.cos(a), rho * math.sin(a), math.sqrt(1.0 - rho * rho))
                                for rho, k in ((0.55, 6), (0.97, 12)) for a in np.linspace(0, 2 * math.pi, k, endpoint=False)]


def bvh(V, F):
    try:
        from mathutils.bvhtree import BVHTree
    except ImportError:                             # the bpy module registers mathutils when it is imported
        import bpy  # noqa: F401
        from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons(np.asarray(V, float).tolist(), [[int(i) for i in f] for f in F])


def grid_slab(M, Bot, Top, mat):
    """a thin solid between two grids of points (n, m, 3): Bot its underside, Top its upper face, and the walls round its
    edge; faces turned out (Top's along Top - Bot)"""
    n, m = Bot.shape[:2]
    V = np.concatenate([Bot.reshape(-1, 3), Top.reshape(-1, 3)])
    o = n * m
    idx = lambda i, j, top: (o if top else 0) + i * m + j        # noqa: E731
    F = []
    for i in range(n - 1):
        for j in range(m - 1):
            F.append((idx(i, j, 1), idx(i + 1, j, 1), idx(i + 1, j + 1, 1), idx(i, j + 1, 1)))
            F.append((idx(i, j, 0), idx(i, j + 1, 0), idx(i + 1, j + 1, 0), idx(i + 1, j, 0)))
    up = (Top - Bot).reshape(-1, 3).mean(0)
    f = F[0]
    if np.cross(V[f[1]] - V[f[0]], V[f[3]] - V[f[0]]) @ up < 0:
        F = [t[::-1] for t in F]
    # the walls: round the border, each quad turned away from the slab's middle
    ring = [(i, 0) for i in range(n)] + [(n - 1, j) for j in range(1, m)] + \
           [(i, m - 1) for i in range(n - 2, -1, -1)] + [(0, j) for j in range(m - 2, 0, -1)]
    mid = V.mean(0)
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        q = (idx(*a, 0), idx(*b, 0), idx(*b, 1), idx(*a, 1))
        nrm = np.cross(V[q[1]] - V[q[0]], V[q[3]] - V[q[0]])
        F.append(q if nrm @ (V[list(q)].mean(0) - mid) > 0 else q[::-1])
    M.add(V, F, mat)


def sphere(M, c, r, mat, n=12, m=8):
    th = np.linspace(0.0, math.pi, m + 1)
    prof = [(-r * math.cos(t), r * math.sin(t)) for t in th]
    G.lathe_closed(M, prof, mat, n, G.tr(np.asarray(c, float)))


class GunGear:
    """gd: the gun deck (gundeck.GunDeck, built); gn: the guns (guns.Guns, built), or None until build (lid_rings needs
    only the deck and the skin)."""

    def __init__(self, gd, gn=None, path=os.path.join(HERE, "gundeck_1797.json")):
        self.gd, self.gn, self.sk, self.SKM = gd, gn, gd.sk, gd.SKM
        self.c = json.load(open(path))["gun_gear"]
        self.info = {}
        self.parts_ = {}
        self.meshes = {}

    # --- the housed gun's tompion and apron (the barrel's frame, inches) ---------------------------------------------
    def tompion(self):
        """a turned oak plug in the bore, its head over the muzzle's mouth and a boss to pull it by"""
        g = self.gn.L24
        t = self.c["tompion"]
        L, rb, rm = g.g["length_in"], g.g["bore_in"] / 2, g.g["mouth_in"]
        p, (hd, ht), (bd, bt) = t["plug_in"], t["head_in"], t["boss_in"]
        hr, br, c = hd / 2, bd / 2, 0.04                      # c: its play in the bore
        prof = [(L - p, 0.0), (L - p, rb - c - 0.2), (L - p + 0.2, rb - c), (L - 0.35, rb - c), (L + 0.03, rm - c),
                (L + 0.03, hr - 0.15), (L + 0.18, hr), (L + ht - 0.15, hr), (L + ht, hr - 0.15), (L + ht, br),
                (L + ht + bt - 0.2, br), (L + ht + bt, br - 0.2), (L + ht + bt, 0.0)]
        M = G.GPart()
        M.cur = "tompion"
        G.lathe_closed(M, prof, "Oak", 24, G.tr([-g.s_t, 0.0, g.up]))
        if rb - c > rb * math.cos(math.pi / g.g["sides"]) - 0.005:
            raise SystemExit("gungear: the tompion's plug does not clear the bore's facets")
        return M

    def apron(self):
        """a lead sheet laid over the vent and the lock and beaten down over them: its underside lift_in over whatever
        it covers (the barrel's mesh, lock and all, read with rays in from outside), draped over the lock's parts as a
        sheet beaten over them would be (nowhere lower than a cap of radius drape_in over any point it covers), then
        eased; checked that no point of the barrel's mesh under it comes through"""
        g = self.gn.L24
        a = self.c["apron"]
        Ls, W = a["size_in"]
        th, lift, Rd = a["thick_in"], a["lift_in"], a["drape_in"]
        vent, lk = g.g["vent"], g.g["lock"]
        BV, BF, _, _ = self.gn.parts["Gun24_Barrel"].arrays()
        tree = bvh(BV, BF)
        s0 = vent["x_in"] - vent["patch_in"][0] / 2 - 0.5
        s1 = lk["x_in"] + lk["plate_in"][0] / 2 + 0.5
        sc = 0.5 * (s0 + s1)
        Rr = g.R(vent["x_in"])
        phc = math.radians(lk["around_deg"]) / 2               # its middle half way round toward the lock
        S = np.linspace(sc - Ls / 2, sc + Ls / 2, 49)
        U = np.linspace(-W / 2, W / 2, 45)
        PH = phc + U / Rr
        D = np.stack([np.zeros_like(PH), np.sin(PH), np.cos(PH)], -1)        # out from the axis (+Z toward +Y)
        rho = np.zeros((len(S), len(U)))
        for i, s in enumerate(S):
            ax = np.array([s - g.s_t, 0.0, g.up])
            R0 = g.R(s) + 6.0
            for j in range(len(U)):
                o = ax + D[j] * R0
                hit = tree.ray_cast(o.tolist(), (-D[j]).tolist(), 8.0)
                rho[i, j] = R0 - hit[3] if hit[0] is not None else g.R(s)
        A0 = rho + lift
        ss, uu = np.meshgrid(S, U, indexing="ij")
        P2 = np.stack([ss.ravel(), uu.ravel()], 1)
        # the mesh's own corners under it too (the rays can pass beside a thin part, the lock's cock): a facet is
        # never farther from the axis than its corners
        yv, zv = BV[:, 1], BV[:, 2] - g.up
        sv, rv, pv = BV[:, 0] + g.s_t, np.hypot(yv, zv), np.arctan2(yv, zv)
        uv = (pv - phc) * Rr
        near = (sv > S[0] - 2.0) & (sv < S[-1] + 2.0) & (uv > U[0] - 2.0) & (uv < U[-1] + 2.0) & \
            (rv > 0.5 * g.R(vent["x_in"]))
        Q2 = np.concatenate([P2, np.stack([sv[near], uv[near]], 1)])
        H = np.concatenate([A0.ravel(), rv[near] + lift])
        d2 = ((P2[:, None, :] - Q2[None, :, :]) ** 2).sum(2)
        Ah = (H[None, :] - d2 / (2.0 * Rd)).max(1).reshape(A0.shape)
        A = Ah
        for _ in range(3):                                     # eased (each pass a 3x3 mean), never below the drape
            Ap = np.pad(A, 1, mode="edge")
            A = np.maximum(sum(Ap[1 + di:Ap.shape[0] - 1 + di, 1 + dj:Ap.shape[1] - 1 + dj]
                               for di in (-1, 0, 1) for dj in (-1, 0, 1)) / 9.0, Ah)
        # nothing of the barrel's mesh under it comes through its underside
        inside = (sv > S[0]) & (sv < S[-1]) & (uv > U[0]) & (uv < U[-1]) & (rv > 0.5 * g.R(vent["x_in"]))
        fi = np.interp(sv[inside], S, np.arange(len(S)))
        fj = np.interp(uv[inside], U, np.arange(len(U)))
        i0, j0 = np.minimum(fi.astype(int), len(S) - 2), np.minimum(fj.astype(int), len(U) - 2)
        ti, tj = fi - i0, fj - j0
        Ai = (A[i0, j0] * (1 - ti) * (1 - tj) + A[i0 + 1, j0] * ti * (1 - tj) + A[i0, j0 + 1] * (1 - ti) * tj +
              A[i0 + 1, j0 + 1] * ti * tj)
        worst = float((rv[inside] - Ai).max()) if inside.any() else -1.0
        if worst > -0.25 * lift:
            raise SystemExit(f"gungear: the barrel comes {worst + lift:.2f} in through the apron's underside")
        Bot = np.zeros((len(S), len(U), 3))
        Top = np.zeros_like(Bot)
        for i, s in enumerate(S):
            ax = np.array([s - g.s_t, 0.0, g.up])
            Bot[i] = ax + D * A[i][:, None]
            Top[i] = ax + D * (A[i][:, None] + th)
        M = G.GPart()
        M.cur = "apron"
        grid_slab(M, Bot, Top, "Lead")
        self.info["apron"] = {"over_lock_in": round(float((A - (g.R(sc) + lift)).max()), 2),
                              "least_over_barrel_in": round(-worst, 3),
                              "s_in": [round(float(S[0]), 2), round(float(S[-1]), 2)]}
        return M

    def housed_copies(self):
        """each housed long gun's tompion and apron: (object name, mesh, 4x4 in the ship (m), collection)"""
        g, gn = self.gn.L24, self.gn
        out = []
        for kind, deck, i, sd, T in gn.gun_frames():
            if kind != "Gun24":
                continue
            gid = f"Gun24_{sd}{i:02d}"
            Tb = T @ G.in_m(G.tr([gn.x24[i]["housed"], 0.0, 0.0])) @ G.in_m(g.barrel_T(gn.elev24["housed"]))
            out.append((gid + "_Tompion", "Gun24_Tompion", Tb, "Guns_Housed"))
            out.append((gid + "_Apron", "Gun24_Apron", Tb, "Guns_Housed"))
        return out

    # --- the implements over each gun -------------------------------------------------------------------------------
    def members(self):
        """everything athwartships under the spar deck over this deck: [(x0, x1)] (the gun deck's beams, ledges and
        breast beams, and the waist's beams, deck.py's)"""
        gd, dk = self.gd, self.gd.dk
        out = [(x - s / 2, x + s / 2) for x, s, m, kind in gd.members]
        sided = dk.c["waist"]["beam_sided_in"] * IN
        out += [(x - sided / 2, x + sided / 2) for x in dk.beams_x]
        return sorted(out)

    def item_set(self):
        """the four things hung over a gun, outboard end first: [(name, length, [(along, half-width)])], and their
        spacing across the bay"""
        im = self.c["implements"]
        Lt = im["staff_ft"] * 12.0
        rs = im["staff_in"] / 2
        heads = {k: (im[k + "_in"][0] / 2, im[k + "_in"][1]) for k in ("sponge", "rammer", "worm", "ladle")}
        items = []
        for a, b in im["staffs"]:
            (ra, la), (rb_, lb) = heads[a], heads[b]
            items.append((f"{a}_{b}", Lt, [(0.0, ra), (la, ra), (la, rs), (Lt - lb, rs), (Lt - lb, rb_), (Lt, rb_)],
                          (a, b)))
        hl = im["handspike_ft"] * 12.0
        hw = im["handspike_in"][0] / 2
        for k in range(2):
            items.append((f"handspike{k + 1}", hl, [(0.0, hw), (hl, hw)], None))
        gap = im["gap_in"]

        def hw_at(it, s):
            prof = it[2]
            if s > it[1]:
                return 0.0
            return max(w for (s0, w), (s1, _) in zip(prof[:-1], prof[1:]) if s0 - 1e-9 <= s <= s1 + 1e-9)
        offs = [0.0]
        probe = np.linspace(0.0, Lt, 241)
        for a, b in zip(items[:-1], items[1:]):
            offs.append(offs[-1] + max(hw_at(a, s) + hw_at(b, s) for s in probe) + gap)
        lo = -max(w for _, w in items[0][2])
        hi = offs[-1] + max(w for _, w in items[-1][2])
        return items, offs, (lo, hi)

    def bay(self, a, f, need):
        """the bay (between two members' faces) over the port spanning a..f where the set fits: the one whose middle
        lies nearest the port's, and where in it the set's middle goes (as near the port's middle as it fits)"""
        M = self.members()
        pm = 0.5 * (a + f)
        best = None
        for (p0, p1), (q0, q1) in zip(M[:-1], M[1:]):
            lo, hi = p1, q0
            if hi - lo < need:
                continue
            x = float(np.clip(pm, lo + need / 2, hi - need / 2))
            d = abs(x - pm)
            if best is None or d < best[0]:
                best = (d, x, lo, hi)
        if best is None or best[0] > 0.5 * (f - a) + 0.3:
            raise SystemExit(f"gungear: no bay over the port at x {a:.2f}..{f:.2f} holds its implements")
        return best[1], best[2], best[3]

    def overhead_tree(self, objs):
        self.over = bvh(*objs)

    def ceiling(self, p, reach):
        """where a hanger from p (a point under the deck) meets what is over it, straight up, within reach, or None"""
        hit = self.over.ray_cast(np.asarray(p, float).tolist(), [0.0, 0.0, 1.0], reach)
        return None if hit[0] is None else np.array(hit[0])

    def staff(self, M, it, P0, d, z):
        """one staff and its heads, from its outboard end P0 inboard along d (level, athwartships), its axis at z"""
        im = self.c["implements"]
        rs = im["staff_in"] / 2 * IN
        name, Lt, prof, heads = it
        Lt *= IN
        side = np.cross(EZ, d)
        at = lambda s: np.array([P0[0], P0[1], z]) + d * s          # noqa: E731
        fr, fl = (v * IN for v in im["ferrule_in"])
        fr /= 2
        la, lb = prof[1][0] * IN, (prof[-1][0] - prof[-2][0]) * IN
        M.cur = "staff"
        G.lathe_closed(M, [(la - 0.1 * IN, 0.0), (la - 0.1 * IN, rs), (Lt - lb + 0.1 * IN, rs), (Lt - lb + 0.1 * IN, 0.0)],
                       "Ash", 10, self.frame_along(at(0.0), d, side))
        for which, s_end, toward in ((heads[0], 0.0, 1.0), (heads[1], Lt, -1.0)):
            r, ln = (v * IN for v in (im[which + "_in"][0] / 2, im[which + "_in"][1]))
            T = self.frame_along(at(s_end), d * toward, side * toward)    # X from the end inboard
            M.cur = which
            if which == "sponge":
                G.lathe_closed(M, [(0.0, 0.0), (0.0, r - 0.6 * IN), (0.6 * IN, r), (ln - 0.3 * IN, r), (ln, r - 0.3 * IN),
                                   (ln, 0.0)], "Fleece", 16, T)
            elif which == "rammer":
                G.lathe_closed(M, [(0.0, 0.0), (0.0, r - 0.25 * IN), (0.25 * IN, r), (ln - 0.25 * IN, r), (ln, r - 0.25 * IN),
                                   (ln, 0.0)], "Oak", 16, T)
            elif which == "ladle":
                self.ladle(M, T, r, ln)
            else:
                self.worm(M, T, r, ln)
            # the ferrule over the staff where it enters the head
            M.cur = "ferrule"
            G.lathe_closed(M, [(ln - 0.05 * IN, 0.0), (ln - 0.05 * IN, fr), (ln + fl, fr), (ln + fl, 0.0)], "Iron", 12, T)

    @staticmethod
    def frame_along(o, X, Y):
        T = np.eye(4)
        X = unit(X)
        Y = unit(Y - (Y @ X) * X)
        T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = X, Y, np.cross(X, Y), o
        return T

    def ladle(self, M, T, r, ln):
        """a wooden head on the staff's end and the copper scoop out from it, open a third of its round (upward)"""
        hb = 2.5 * IN
        G.lathe_closed(M, [(ln - hb, 0.0), (ln - hb, r), (ln, r), (ln, 0.0)], "Oak", 16, T)
        t = 0.08 * IN
        ph = np.linspace(math.radians(60), math.radians(300), 17)       # from the top's +60 deg round under to +300
        s = np.array([0.0, ln - hb + 0.3 * IN])
        rings = []
        for rr in (r + t, r):
            rings.append([[G.pts(T, np.array([[sv, rr * math.sin(p), rr * math.cos(p)]]))[0] for p in ph] for sv in s])
        Out, Inn = np.array(rings[0]), np.array(rings[1])      # (2 along, k round, 3)
        grid_slab(M, Inn.transpose(1, 0, 2), Out.transpose(1, 0, 2), "Copper")
        # its end closed by a round plate (the scoop's tip) only below the opening: a flat half disc at s = 0
        P = [G.pts(T, np.array([[0.0, (r + t) * math.sin(p), (r + t) * math.cos(p)]]))[0] for p in ph]
        c = G.pts(T, np.array([[0.0, 0.0, 0.0]]))[0]
        V = np.array([c] + P)
        F = [(0, k + 1, k + 2) for k in range(len(P) - 1)]
        nrm = np.cross(V[F[0][1]] - V[0], V[F[0][2]] - V[0])
        if nrm @ (-T[:3, 0]) < 0:
            F = [f[::-1] for f in F]
        M.add(V, F, "Copper")

    def worm(self, M, T, r, ln):
        """two iron prongs in a double spiral, from a collar on the staff's end out to points"""
        im = self.c["implements"]
        rb = im["worm_bar_in"] / 2 * IN
        turns = im["worm_turns"]
        rh = r - rb
        G.lathe_closed(M, [(ln - 1.0 * IN, 0.0), (ln - 1.0 * IN, 1.1 * IN), (ln, 1.1 * IN), (ln, 0.0)], "Iron", 12, T)
        for k in range(2):
            s = np.linspace(ln - 0.9 * IN, 0.15 * IN, 40)
            ang = k * math.pi + 2 * math.pi * turns * (ln - s) / ln
            rr = np.minimum(rh, 0.9 * IN + (rh - 0.9 * IN) * (ln - 0.9 * IN - s) / (1.2 * IN))
            P = np.stack([s, rr * np.sin(ang), rr * np.cos(ang)], 1)
            tube(M, G.pts(T, P), rb, "Iron", n=6)

    def handspike(self, M, P0, d, z):
        """6 ft of ash from its toe (outboard, a bevel under the carriage's steps) to the round of its grip"""
        im = self.c["implements"]
        L = im["handspike_ft"] * 12.0
        (w, h), (tw, tt) = im["handspike_in"], im["handspike_toe_in"]
        side = unit(np.cross(EZ, d))
        rings = []
        for s, ww, hh, dz in ((0.0, w, tt, -(h - tt) / 2), (tw, w, h, 0.0), (L * 0.3, w * 0.95, h * 0.95, 0.0),
                              (L - 4.0, 1.5, 1.4, 0.0), (L, 1.3, 1.2, 0.0)):
            c = np.array([P0[0], P0[1], z]) + d * s * IN + EZ * dz * IN
            rings.append(np.array([c - side * ww / 2 * IN - EZ * hh / 2 * IN, c + side * ww / 2 * IN - EZ * hh / 2 * IN,
                                   c + side * ww / 2 * IN + EZ * hh / 2 * IN, c - side * ww / 2 * IN + EZ * hh / 2 * IN]))
        M.cur = "handspike"
        solid(M, rings, "Ash")

    def hanger_top(self, p_axis, half, d, reach):
        """where a hanger beside the item at p_axis (going along d; half: its half width and half height there) meets
        what is over it, or None if nothing is within reach"""
        rb = self.c["implements"]["hanger_in"][0] / 2 * IN
        side = unit(np.cross(EZ, d))
        return self.ceiling(p_axis + side * (half[0] + rb + 0.05 * IN) + EZ * 0.01, reach)

    def hanger(self, M, p_axis, half, d, top):
        """an iron hanger under the deck: a rod from a screw eye in what is over it (top) down beside the item, its hook
        round under the item (the item's weight on it)"""
        im = self.c["implements"]
        rb = im["hanger_in"][0] / 2 * IN
        side = unit(np.cross(EZ, d))
        Rw, Rh = half[0] + rb + 0.05 * IN, half[1] + rb + 0.05 * IN
        M.cur = "hanger"
        ang = np.linspace(0.0, math.radians(215), 12)          # from beside the item round under it and up the far side
        hook = [p_axis + side * Rw * math.cos(t) - EZ * Rh * math.sin(t) for t in ang]
        P = [top - EZ * 0.4 * IN] + hook
        tube(M, fillet(np.array(P), 0.5 * IN), rb, "Iron", n=6)
        # the screw eye: a small ring under the deck
        G.torus(M, top - EZ * 0.4 * IN, side, EZ, 0.45 * IN, 0.12 * IN, "Iron", n=10, m=5)

    def under(self, x0, x1):
        """the lowest underside of what runs athwartships over x0..x1 (the gun deck's beams and ledges, the gangways'
        and the waist's beams)"""
        gd, dk = self.gd, self.gd.dk
        zs = [gd.beam_bottom(x0), gd.beam_bottom(x1)]
        zs += [float(gd.zsu(x)) - m for x, s, m, kind in gd.members if x0 - s / 2 <= x <= x1 + s / 2]
        zs += [dk.waist_beam_z(x)[1] for x in dk.beams_x if x0 <= x <= x1]
        return min(zs)

    def item_dims(self, it):
        """an item's half width and half height at its hangers, and its axis's depth under its top"""
        im = self.c["implements"]
        if it[3]:
            r = im["staff_in"] / 2 * IN
            return (r, r), r
        r_ax = im["handspike_in"][1] / 2 * IN
        return (im["handspike_in"][0] / 2 * IN, r_ax), r_ax

    def athwart(self, xc, items, offs, lo, hi):
        """the set athwartships in the bay at xc over a starboard port, outboard ends 14 in from the side: [(item, its
        outboard end, d, z, half, [(s, the hanger's top)])], or None where the deck over it is too short to hang it
        from (the waist, where only the gangways are over the guns)"""
        gd = self.gd
        im = self.c["implements"]
        below = im["below_beam_in"] * IN
        x0 = xc - 0.5 * (hi + lo) * IN                       # the first item's axis
        zb = gd.beam_bottom(xc)
        d = np.array([0.0, -1.0, 0.0])                       # inboard
        plan = []
        for it, off in zip(items, offs):
            x = x0 + off * IN
            half, r_ax = self.item_dims(it)
            z = zb - below - r_ax
            P, n = gd.wall_at(np.array([x]), np.array([z]))
            yo = float(P[0, 1]) - im["in_from_side_in"] * IN
            P0 = np.array([x, yo, z])
            Lm = it[1] * IN
            reach = below + r_ax + gd.c["overhead"]["beam_in"][1] * IN + 4.0 * IN
            # its hangers either side of its middle, each where the deck (or a carling) is over it: looked for from
            # 0.22 and 0.72 of its length toward the side, the inboard one never nearer the side than its middle
            got = []
            for frac, least in ((0.22, 0.05 * Lm), (0.72, 0.5 * Lm + 0.1)):
                s = frac * Lm
                top = None
                while s >= least:
                    top = self.hanger_top(P0 + d * s, half, d, reach)
                    if top is not None:
                        break
                    s -= 0.05
                if top is None:
                    return None
                got.append((s, top))
            if yo - Lm < 0.05:
                raise SystemExit(f"gungear: the {it[0]} over the gun at x {xc:.2f} reaches past the middle line")
            # and the deck over it all its length: in the waist the gangway's edge may hold a hanger short of the
            # middle, but the rest would hang out under open sky
            if any(self.ceiling(P0 + d * s + EZ * 0.01, reach) is None for s in np.linspace(0.0, Lm, 13)):
                return None
            plan.append((it, P0, d, z, half, got))
        return plan

    def fore_and_aft(self, a, f, items, offs, lo, hi):
        """the set fore and aft under the gangway beside a waist port (a..f), its middle over the port's, its innermost
        item edge_in in from the gangway's inner edge: the same shape as athwart(), or None"""
        gd = self.gd
        im = self.c["implements"]
        below = im["below_beam_in"] * IN
        pm = 0.5 * (a + f)
        d = np.array([1.0, 0.0, 0.0])
        Y0 = gd.dk.y_open + im["waist"]["edge_in"] * IN + hi * IN      # the first item's axis (outboard)
        plan = []
        for it, off in zip(items, offs):
            Lm = it[1] * IN
            half, r_ax = self.item_dims(it)
            x0 = pm - Lm / 2
            z = self.under(x0, x0 + Lm) - below - r_ax
            P0 = np.array([x0, Y0 - off * IN, z])
            reach = below + r_ax + gd.c["overhead"]["beam_in"][1] * IN + 4.0 * IN
            got = []
            for frac in im["waist"]["hangers_at"]:
                top = self.hanger_top(P0 + d * frac * Lm, half, d, reach)
                if top is None:
                    return None
                got.append((frac * Lm, top))
            plan.append((it, P0, d, z, half, got))
        return plan

    def implements(self, M):
        gd = self.gd
        im = self.c["implements"]
        items, offs, (lo, hi) = self.item_set()
        need = (hi - lo) * IN + 2 * im["gap_in"] * IN
        placed = []
        Ms = G.GPart()
        for i, (a, f) in enumerate(gd.ports[:-1]):              # the bridle port has no gun
            xc, b0, b1 = self.bay(a, f, need)
            how, plan = "athwartships", self.athwart(xc, items, offs, lo, hi)
            if plan is None:
                how, plan = "fore_and_aft", self.fore_and_aft(a, f, items, offs, lo, hi)
            if plan is None:
                raise SystemExit(f"gungear: no deck over gun {i + 1}'s implements to hang them from")
            for it, P0, d, z, half, got in plan:
                if it[3]:
                    self.staff(Ms, it, P0, d, z)
                else:
                    self.handspike(Ms, P0, d, z)
                for s, top in got:
                    self.hanger(Ms, P0 + d * s, half, d, top)
                Lm = it[1] * IN
                end = P0 + d * Lm
                placed.append({"port": i + 1, "item": it[0], "stowed": how,
                               "from_m": [round(float(v), 3) for v in P0], "to_m": [round(float(v), 3) for v in end],
                               "hangers_at": [round(s / Lm, 2) for s, _ in got],
                               "hanger_drop_m": [round(float(top[2] - z), 3) for _, top in got]})
        M.extend(Ms)
        M.extend(Ms.mirrored_y())
        self.info["implements"] = {"sets": len(placed) // len(items), "set_width_in": round(hi - lo, 2),
                                   "spacing_in": [round(b - a, 2) for a, b in zip(offs[:-1], offs[1:])],
                                   "fore_and_aft_ports": sorted({p["port"] for p in placed if p["stowed"] != "athwartships"}),
                                   "least_inboard_y_m": round(min(min(p["from_m"][1], p["to_m"][1]) for p in placed), 3),
                                   "by_item": placed}

    # --- the shot garlands ------------------------------------------------------------------------------------------
    def garlands(self, M):
        gd = self.gd
        ga = self.c["garland"]
        prof = np.array(gd.c["deck"]["waterway"]["profile_in"], float)
        cove = prof[-1, 0] * IN
        w, h = (v * IN for v in ga["rail_in"])
        n, pitch, r = ga["shot_count"], ga["pitch_in"] * IN, ga["shot_in"] / 2 * IN
        L = n * pitch
        clear = ga["port_clear_in"] * IN
        out = []
        for i in range(len(gd.ports) - 1):
            f, a2 = gd.ports[i][1], gd.ports[i + 1][0]
            if a2 - f - 2 * clear < L:
                raise SystemExit(f"gungear: no room for gun {i + 1}'s garland between its port and the next")
            xc = 0.5 * (f + a2)
            xs = np.linspace(xc - L / 2, xc + L / 2, 15)
            P0, nn = gd.wall_over_deck(xs, 0.0)
            # each point's inboard offset from the side's foot, then back to its own x along the side's line
            C = P0 + nn * (cove + ga["off_cove_in"] * IN + w / 2)
            C[:, 2] = gd.zg(C[:, 0])
            T = np.gradient(C, axis=0)
            T = T / np.linalg.norm(T, axis=1)[:, None]
            Nn = np.cross(EZ, T)
            Nn *= np.sign((Nn * nn).sum(1))[:, None]
            rings = []
            for k in range(len(C)):
                c = C[k]
                rings.append(np.array([c - Nn[k] * w / 2 - EZ * 0.1 * IN, c + Nn[k] * w / 2 - EZ * 0.1 * IN,
                                       c + Nn[k] * w / 2 + EZ * h, c - Nn[k] * w / 2 + EZ * h]))
            for sgn in (1.0, -1.0):
                M.cur = "garland"
                solid(M, [rr * [1.0, sgn, 1.0] for rr in rings], "Oak")
                s_all = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
                for k in range(n):
                    s = (k + 0.5) * pitch
                    p = np.array([np.interp(s, s_all, C[:, j]) for j in range(3)])
                    p[2] = float(gd.zg(p[0])) + h - ga["cup_in"] * IN + r
                    M.cur = "shot"
                    sphere(M, p * [1.0, sgn, 1.0], r, "Blacking")
            out.append({"gun": i + 1, "x_m": [round(float(xs[0]), 3), round(float(xs[-1]), 3)],
                        "port_clear_m": [round(float(xs[0] - f), 3), round(float(a2 - xs[-1]), 3)]})
        self.info["garlands"] = out

    # --- the lids' lanyards -----------------------------------------------------------------------------------------
    def lid_points(self):
        """each starboard lid's two lanyards: the hinge strap's x (px and m), the ring's eye on the strap's end, the
        lid's up (toward the hinge) and out there, the knuckle's centre, the outside and inside bushes and the cleat"""
        sk, gd, S = self.sk, self.gd, self.SKM
        ly = self.c["lanyard"]
        n = int(sk.sp["port_lids"]["hinges"])
        # the port's head on the side's inner face (the skin's row there): toward the bow the face leans in, and the
        # head there stands as much as 3.5 in over the outside's
        head_in = gd.rows["g_Shd"]
        cleats = gd.lanyard_cleats()
        out = {}
        for k, (name, xa, xf, _) in enumerate(sk.lid_groups):
            w = xf - xa
            recs = []
            for j, x in enumerate(xa + w * np.linspace(0.2, 0.8, n)):
                z_top = float(sk.pr.Shd(np.array([x]))[0]) - sk.inset
                z_bot = float(sk.pr.S(np.array([x]))[0]) + sk.inset
                zr = z_top - ly["ring_from_hinge_of_lid"] * (z_top - z_bot)
                Z = np.array([z_top, zr, zr + 0.5])
                P, N = sk.surf(np.full(3, x), Z, True, 0, S.LIDOUT)
                up = unit(P[2] - P[1])
                nrm = unit(N[1])
                up = unit(up - (up @ nrm) * nrm)
                knuckle = P[0] + unit(N[0]) * 0.9 * IN
                xm = float(P[1][0])
                # the bush over the port: hole_over_clamp_edge_in over the clamp's lower edge there (eased over the
                # port's head, clear of the housing bolts: gundeck.clamps), lower where the clamp is eased so shallow
                # that the bush's rim would come within a quarter inch of its top (in the middle of it if it can't clear
                # both edges), or past the clamp's ends hole_above_head_in over the port's head, on the outside or the
                # inside, whichever is the higher; the hole's inner end at the same height (bored square through)
                Xc, zbc, ztc = gd.clamp
                if Xc[0] <= xm <= Xc[-1]:
                    zb_, zt_ = float(np.interp(xm, Xc, zbc)), float(np.interp(xm, Xc, ztc))
                    rim = (ly["bush_in"][0] / 2 + 0.25) * IN
                    zh = zb_ + ly["hole_over_clamp_edge_in"] * IN
                    zh = min(max(zh, zb_ + rim), zt_ - rim) if zt_ - zb_ >= 2 * rim else 0.5 * (zb_ + zt_)
                    if zh < zb_ + ly["hole_over_clamp_edge_in"] * IN - 1e-6:
                        self.info.setdefault("lanyard_holes_lowered_in", []).append(
                            round((zb_ + ly["hole_over_clamp_edge_in"] * IN - zh) / IN, 2))
                else:
                    zh = max(float(gd.Shd(xm)), float(np.interp(xm, head_in[:, 0], head_in[:, 2]))) + \
                        ly["hole_above_head_in"] * IN
                zp = zh * gd.k
                xp = gd.xpx(xm)
                for _ in range(8):
                    Q, NQ = sk.surf(np.array([xp]), np.array([zp]), True, 0, S.OUT)
                    zp += (zh - Q[0][2]) * gd.k
                    xp += (xm - Q[0][0]) / sk.m.sx
                Q, NQ = sk.surf(np.array([xp]), np.array([zp]), True, 0, S.OUT)
                bo, no = Q[0], unit(NQ[0])
                # its rim on the planking's faces as built, over any seam it lands on (seat)
                disc = [(0.0, 0.0)] + [(f * ly["bush_in"][0] / 2 * IN * math.cos(a), f * ly["bush_in"][0] / 2 * IN *
                                        math.sin(a)) for f, k_ in ((0.5, 8), (0.85, 12))
                                       for a in np.linspace(0.0, 2 * math.pi, k_, endpoint=False)]
                bo = bo + no * self.seat(bo, no, disc, self.skin_tree())
                # its inner end on the side's inner face, or on the clamp's where the clamp covers that height: the
                # hole is bored through both. The bush lies on the face square to it (the face's own normal: the side
                # tumbles home amidships, as much as 1 in 4 at the ports, and flares at the bow), as the clamp's inner
                # face does (the clamp stands off the side by its thickness, level, so its face leans as the side's)
                Pi, ni = gd.wall_at(np.array([bo[0]]), np.array([bo[2]]), true=True)
                bi = Pi[0]
                rb_ = ly["bush_in"][0] / 2 * IN
                if np.interp(bo[0], Xc, zbc) - rb_ <= bo[2] <= np.interp(bo[0], Xc, ztc) + rb_:
                    bi, _ = gd.clamp_inner(float(bo[0]), float(bo[2]))
                bi = bi + unit(ni[0]) * self.seat(bi, unit(ni[0]), disc)
                # the cleat beside the port, out from the inner jamb on this strap's side, cleat_over_deck_in up
                # (gundeck.lanyard_cleats; the hanging knees keep clear of it), lying on the side's face (its own
                # normal, so the cleat's length runs up the face's slope) and seated on the planking as built (seat:
                # the cleat and the rope's turns round it, out to the run coming down to it and the tail)
                xc = cleats[k][0][j]
                zc = float(gd.zg(xc)) + ly["cleat_over_deck_in"] * IN
                Pc, nc = gd.wall_at(np.array([xc]), np.array([zc]), true=True)
                rr_ = ly["circ_in"] / (2 * math.pi) * IN
                hu, hv_ = ly["cleat_in"][1] / 2 * IN + rr_ + 0.4 * IN, ly["cleat_in"][0] / 2 * IN + 2.5 * IN
                Pc = Pc + nc * self.seat(Pc[0], unit(nc[0]), [(b * hu, a * hv_) for a in np.linspace(-1.0, 1.0, 9)
                                                              for b in np.linspace(-1.0, 1.0, 5)])
                recs.append({"x_px": x, "eye_at": P[1], "up": up, "out": nrm, "knuckle": knuckle, "z_top": P[0],
                             "bush_out": bo, "n_out": no, "bush_in": bi, "n_in": ni[0], "cleat": Pc[0], "n_cleat": nc[0],
                             "aft": j == 0})
            out[name] = recs
        return out

    def seat(self, c, n, offs, tree=None):
        """how far the side's planking as built (side_tree) stands in from its true face (the point c on it, n its own
        normal) under what is fastened there, at offs [(along the side, up its slope)] from c: between the drawn
        stations the planking's flat faces lie as much as 0.3 in in from the curved face, so a cleat or a bush's rim
        stands out by the most the planking under it does (outside, tree the skin_tree, a seam's groove under a bush
        sinks the rim no further than the planks' faces). Raises if any of it is not on the side (in a port's
        opening, past the clamp's edge), or if the planking anywhere under it lies more than half an inch behind the
        true face (what is let into the side would not reach it)"""
        u = unit(np.cross(EZ, n))
        v = np.cross(n, u)
        tree = tree or self.side_tree()
        got = []
        for du, dv in offs:
            q = c + v * dv + u * du
            loc = tree.ray_cast((q + n * 0.5).tolist(), (-n).tolist(), 0.5 + 1.0 * IN)[0]
            if loc is None:
                raise SystemExit(f"gungear: a lid lanyard's fitting at {np.round(c, 3).tolist()} is not all on the "
                                 f"side (nothing under {np.round(q, 3).tolist()})")
            got.append(float((np.array(loc) - q) @ n))
        if min(got) < -0.5 * IN:
            raise SystemExit(f"gungear: the side lies {-min(got) / IN:.2f} in behind its true face under a lid "
                             f"lanyard's fitting at {np.round(c, 3).tolist()}")
        rise = max(0.0, max(got))
        self.info.setdefault("lanyard_seat_in", []).append(round(rise / IN, 3))
        return rise

    def holes_out(self):
        """each starboard lid lanyard's hole on the side's outside: [(x, z, its lead bush's rim radius)] in metres, for
        the standing rigging's chains to stop above (rigging.Standing's holes)"""
        if not hasattr(self, "lp"):
            self.lid_rings()
        R = self.c["lanyard"]["bush_in"][0] / 2 * IN
        return [(float(r["bush_out"][0]), float(r["bush_out"][2]), R) for recs in self.lp.values() for r in recs]

    def ring_geometry(self, r):
        """the eyebolt on the strap's end and the ring in it, lying up the lid toward the hinge: (part, the ring's
        top, where the lanyard is spliced)"""
        ly = self.c["lanyard"]
        M = G.GPart()
        (eo, eb), (ro, rb_) = ly["eye_in"], ly["ring_in"]
        Re, re = (eo - eb) / 2 * IN, eb / 2 * IN
        Rr, rr = (ro - rb_) / 2 * IN, rb_ / 2 * IN
        nrm, up = r["out"], r["up"]
        along = np.cross(up, nrm)
        strap_out = 0.35 * IN
        base = r["eye_at"] + nrm * strap_out
        ce = base + nrm * Re                                   # the eye stands out of the strap
        M.cur = "eye"
        G.torus(M, ce, nrm, up, Re, re, "Iron", n=12, m=6)
        G.cylinder(M, base + nrm * 0.15 * IN, base - nrm * 1.5 * IN, re * 1.1, "Iron", n=8)
        cr = ce + up * Rr
        M.cur = "ring"
        G.torus(M, cr, up, along, Rr, rr, "Iron", n=16, m=6)
        return M, cr + up * Rr, cr

    def lid_rings(self):
        """{lid name: (V, F, M)}: each starboard lid's two eyebolts and rings (ship frame, the lid shut), for
        build_frigate.py to add to the lid before it is made an object (so they turn with it)"""
        self.lp = self.lid_points()
        out = {}
        for name, recs in self.lp.items():
            M = G.GPart()
            for r in recs:
                part, top, cr = self.ring_geometry(r)
                r["ring_top"], r["ring_c"] = top, cr
                M.extend(part)
            V, F, Mt, _ = M.arrays()
            out[name] = (V, F, Mt)
        return out

    def bush(self, M, c, n):
        """a lead bush lining the hole at c (on a face whose outward normal is n): its rim bush_in across standing proud,
        its bore down into the side to a dark bottom"""
        ly = self.c["lanyard"]
        D, proud = ly["bush_in"]
        R, rh = D / 2 * IN, ly["holes_in"] / 2 * IN
        n = unit(n)
        ref = unit(np.cross(n, EZ if abs(n[2]) < 0.9 else EX))
        T = self.frame_along(c, -n, ref)                         # X into the side
        M.cur = "bush"
        G.lathe_closed(M, [(-proud * IN, rh), (-proud * IN, R), (1.0 * IN, R), (1.0 * IN, rh)], "Lead", 16, T,
                       closed=True)
        G.lathe_closed(M, [(0.9 * IN, 0.0), (0.9 * IN, rh + 0.02 * IN), (1.0 * IN, rh + 0.02 * IN), (1.0 * IN, 0.0)],
                       "Shadow", 12, T)

    def cleat(self, M, c, n):
        """a horn cleat on the side, its length up and down: the body against the side, a horn each end standing off it"""
        ly = self.c["lanyard"]
        Lc, wc, hc = (v * IN for v in ly["cleat_in"])
        n = unit(n)
        u = unit(np.cross(EZ, n))
        v = np.cross(n, u)
        M.cur = "cleat"
        G.obox(M, c + n * (hc / 2 - 0.25 * IN), u, v, n, [wc / 2, 1.5 * IN, hc / 2 + 0.25 * IN], "Oak")
        for sg in (1.0, -1.0):
            G.obox(M, c + v * sg * (1.5 * IN + (Lc / 2 - 1.5 * IN) / 2) + n * (0.85 * IN + (hc - 0.85 * IN) / 2), u, v, n,
                   [wc / 2 * 0.8, (Lc / 2 - 1.5 * IN) / 2 + 0.05 * IN, (hc - 0.85 * IN) / 2], "Oak")
        return u, v

    def skin_tree(self):
        """a BVH of the side's outside where the lanyards' holes come through it: the planking and its mouldings"""
        if getattr(self, "_skin", None) is None:
            sp = self.gd.skin_parts
            Vs, Fs, n0 = [], [], 0
            for n in ("Skin", "Moulding"):
                V = np.asarray(sp[n][0], float)
                Vs.append(V)
                Fs += [[int(i) + n0 for i in f] for f in sp[n][1]]
                n0 += len(V)
            self._skin = bvh(np.concatenate(Vs), Fs)
        return self._skin

    def side_tree(self):
        """a BVH of what the inside of the side is made of where the lanyards run down it: the skin's inner face
        (GunWall) and port linings, the clamps, waterways and hanging knees"""
        if getattr(self, "_side", None) is None:
            sp, gp = self.gd.skin_parts, self.gd.parts_
            meshes = [(sp[n][0], sp[n][1]) for n in ("GunWall", "PortLinings") if n in sp]
            for n in ("Clamps", "GunWaterways", "HangingKnees"):
                if n in gp:
                    V, F, _, _ = gp[n].arrays()
                    meshes.append((V, F))
            Vs, Fs, n0 = [], [], 0
            for V, F in meshes:
                V = np.asarray(V, float)
                Vs.append(V)
                Fs += [[int(i) + n0 for i in f] for f in F]
                n0 += len(V)
            self._side = bvh(np.concatenate(Vs), Fs)
        return self._side

    def lay_need(self, q, n, t, b, off):
        """how far q must move in from the side along n (the side's inward normal; t, b across it) for a ball of radius
        off round it to clear the side's fabric: rays cast out at the side from the room through a disc of that radius,
        each ray's first hit (the fabric nearest the room along it) setting how far in the ball's face must stand there"""
        tree = self.side_tree()
        L = 0.5
        need = -1.0
        for dt, db, h in LAY_DISC:
            o = q + n * L + (t * dt + b * db) * off
            loc = tree.ray_cast(o.tolist(), (-n).tolist(), L + off)[0]
            if loc is not None:
                need = max(need, (np.array(loc) - q) @ n + off * h)
        return need

    def laid_off(self, A, B, off, step=0.25 * IN, depth=0, free=False):
        """a rope's centre line from A to B down the inside of the side, taut: where the straight run would come
        nearer the side's fabric than off (or into it), it is laid over it as a string over the bumps, the worst place
        first: that point moved in from the side, square to it (along the face's own normal there, never along the
        side or up and down), until off clear (lay_need). With free, B is a loose end (a tail): moved in the same way
        first if it would lie in the side. Points from A to B"""
        _, nab = self.gd.wall_at(np.array([A[0], B[0]]), np.array([A[2], B[2]]), true=True)
        n = unit(nab[0] + nab[1])
        t = (B - A) - ((B - A) @ n) * n
        t = unit(t) if np.linalg.norm(t) > 1e-9 else unit(np.cross(n, EZ))
        b = np.cross(n, t)
        if free:
            need = self.lay_need(B, n, t, b, off)
            if need > 0.0:
                B = B + n * (need + 0.02 * IN)
        m = max(2, int(np.linalg.norm(B - A) / step))
        worst, wq = 0.005 * IN, None
        for s in np.linspace(0.0, 1.0, m + 1)[1:-1]:
            q = A + s * (B - A)
            need = self.lay_need(q, n, t, b, off)
            if need > worst:
                worst, wq = need, q + n * (need + 0.02 * IN)
        if wq is None:
            return [A, B]
        if depth >= 10:
            raise SystemExit(f"gungear: a lanyard could not be laid off the side near {np.round(wq, 3).tolist()}")
        return self.laid_off(A, wq, off, step, depth + 1)[:-1] + self.laid_off(wq, B, off, step, depth + 1)

    def lanyard_inside(self, M, r):
        """from the inner bush down the side to the cleat: under its upper horn, across its face, under the lower horn
        and its tail hanging plumb. The cleat and its turns lie on the side's face, square to it; the run from the bush
        to the cleat and the tail are laid off the side's true inner face (and the clamp, waterway and knees) by
        lay_off_in (laid_off: where the side flares under the cleat, the tail lies down the face)"""
        ly = self.c["lanyard"]
        rr = ly["circ_in"] / (2 * math.pi) * IN
        off = rr + ly["lay_off_in"] * IN
        n_in = unit(r["n_in"])
        c, nc = r["cleat"], unit(r["n_cleat"])
        u = unit(np.cross(EZ, nc))
        v = np.cross(nc, u)
        Lc, wc, hc = (x * IN for x in ly["cleat_in"])
        s = -1.0 if r["aft"] else 1.0                          # the side the rope comes in from (toward the port)
        u = u * (1.0 if (u @ (r["bush_in"] - c)) * s >= 0 else -1.0) * s
        hv = Lc / 2 - 0.6 * IN
        under = 0.42 * IN
        front = hc + rr + 0.08 * IN
        P = [r["bush_in"] + n_in * 0.3 * IN, r["bush_in"] + n_in * (rr + 0.6 * IN) - EZ * 1.0 * IN,
             c + v * (hv + 2.5 * IN) + u * (wc / 2 + rr + 0.4 * IN) + nc * (under + 0.3 * IN),
             c + v * hv + u * (wc / 2 + rr) + nc * under,
             c + v * hv - u * (wc / 2 + rr) + nc * under,
             c + v * (hv - 0.6 * IN) - u * (wc / 2 + rr + 0.1 * IN) + nc * (front - 0.3 * IN),
             c + v * 0.0 + nc * front,
             c - v * (hv - 0.6 * IN) + u * (wc / 2 + rr + 0.1 * IN) + nc * (front - 0.3 * IN),
             c - v * hv + u * (wc / 2 + rr) + nc * under,
             c - v * hv - u * (wc / 2 + rr) + nc * under,
             c - v * (hv + 1.0 * IN) - u * (wc / 2 + rr + 0.2 * IN) + nc * (under + 0.2 * IN)]
        run = self.laid_off(P[1], P[2], off)
        tail = self.laid_off(P[10], P[10] - EZ * (ly["tail_in"] - 1.0) * IN, off, free=True)
        P = [P[0]] + run[:-1] + P[2:10] + tail
        M.cur = "lanyard_in"
        tube(M, fillet(np.array(P), 0.5 * IN), rr, "Hemp", n=6)

    def lanyard_shut(self, M, r):
        """outside, the lid shut: from the ring up the strap, over the hinge's knuckle and up the side to the bush"""
        ly = self.c["lanyard"]
        rr = ly["circ_in"] / (2 * math.pi) * IN
        nrm, up = r["out"], r["up"]
        k = r["knuckle"]
        Rk = 1.0 * IN + rr + 0.04 * IN
        off = (0.35 * IN + rr + 0.04 * IN)
        zt = r["z_top"]
        a = r["eye_at"] + nrm * off + up * ((r["ring_top"] - r["eye_at"]) @ up + 1.5 * IN)
        b = zt + nrm * off - up * 2.2 * IN
        P = [r["ring_top"], a, b, k + nrm * Rk, k + unit(nrm + up) * Rk, k + up * Rk + nrm * 0.3 * IN,
             r["bush_out"] + r["n_out"] * (rr + 0.05 * IN) - up * 1.6 * IN, r["bush_out"] + r["n_out"] * 0.4 * IN,
             r["bush_out"] - r["n_out"] * 0.8 * IN]
        M.cur = "lanyard_out"
        tube(M, fillet(np.array(P), 0.6 * IN), rr, "Hemp", n=6)

    def lanyard_open(self, M, r, o, axis, deg):
        """outside, the lid open deg about its hinge: from the ring taut to the bush, over the knuckle if it reaches it"""
        ly = self.c["lanyard"]
        rr = ly["circ_in"] / (2 * math.pi) * IN
        Rt = G.rot(axis, deg)[:3, :3]
        ring_top = o + Rt @ (r["ring_top"] - o)
        k = r["knuckle"]
        A, B = r["bush_out"] + r["n_out"] * 0.4 * IN, ring_top
        Rk = 1.0 * IN + rr + 0.04 * IN
        t = np.clip((k - A) @ (B - A) / ((B - A) @ (B - A)), 0.0, 1.0)
        q = A + t * (B - A)
        dvec = q - k
        dvec -= (dvec @ axis) * axis
        P = [r["bush_out"] - r["n_out"] * 0.8 * IN, A]
        if np.linalg.norm(dvec) < Rk:
            P.append(k + unit(dvec) * Rk)
        P.append(B)
        M.cur = "lanyard_out"
        tube(M, fillet(np.array(P), 0.6 * IN), rr, "Hemp", n=6)
        return float(np.linalg.norm(dvec) - Rk)

    def lanyards(self, Mfit, Mrope, Mshut):
        """the lead bushes and cleats (Mfit), the lanyards inside (Mrope) and outside down the shut lids (Mshut; the
        bridle ports', whose lids never open, in Mrope)"""
        if not hasattr(self, "lp"):
            self.lid_rings()
        gunless = []
        for k, (name, recs) in enumerate(self.lp.items()):
            # the bridle port has no gun, so its lid stays shut: its lanyards are fixed with it
            shut = Mshut if k < len(self.gd.ports) - 1 else Mrope
            if shut is Mrope:
                gunless.append(name)
            for r in recs:
                self.bush(Mfit, r["bush_out"], r["n_out"])
                self.bush(Mfit, r["bush_in"], r["n_in"])
                self.cleat(Mfit, r["cleat"], r["n_cleat"])
                self.lanyard_inside(Mrope, r)
                self.lanyard_shut(shut, r)
        self.info["lanyards"] = {"lids": len(self.lp), "each": 2, "always_shut": gunless}

    def lanyards_open(self, openings):
        """the lanyards outside with each lid open (openings: {lid object name: degrees}, the starboard lids' names
        ending _S, the port's _P): the part LidLanyards_Open (both sides)"""
        M = G.GPart()
        least = {}
        for name, recs in self.lp.items():
            o, xa, za = self.sk.lid_frame(name)
            for sd, sgn in (("S", 1.0), ("P", -1.0)):
                deg = openings.get(f"{name}_{sd}")
                if deg is None:
                    continue
                Mx = G.GPart()
                for r in recs:
                    least[f"{name}_{sd}"] = min(least.get(f"{name}_{sd}", 9.9), self.lanyard_open(Mx, r, o, xa, deg))
                M.extend(Mx if sgn > 0 else Mx.mirrored_y())
        self.parts_["LidLanyards_Open"] = M
        self.info["lanyards_open"] = {"lids": sorted(least), "least_clear_of_knuckle_in": round(min(least.values()) / IN, 2)
                                      if least else None}
        return M

    # --- building ---------------------------------------------------------------------------------------------------
    def build(self, overhead, gn=None):
        """overhead: (V, F) of everything under the spar deck that a hanger may be screwed into (the deck's underside,
        its beams, carlings and the waist's beams), ship frame; gn: the guns, if not given to the constructor (the lids'
        rings are built before the guns: lid_rings)"""
        if gn is not None:
            self.gn = gn
        self.overhead_tree(overhead)
        self.meshes = {"Gun24_Tompion": G.scaled(self.tompion(), IN), "Gun24_Apron": G.scaled(self.apron(), IN)}
        P = {n: G.GPart() for n in ("GunImplements", "ShotGarlands", "LanyardFittings", "LidLanyards",
                                    "LidLanyards_Shut")}
        self.implements(P["GunImplements"])
        self.garlands(P["ShotGarlands"])
        self.lid_rings()
        self.lanyards(P["LanyardFittings"], P["LidLanyards"], P["LidLanyards_Shut"])
        both = {}
        for n in ("LanyardFittings", "LidLanyards", "LidLanyards_Shut"):
            M = G.GPart()
            M.extend(P[n])
            M.extend(P[n].mirrored_y())
            both[n] = M
        P.update(both)
        self.parts_ = P
        return self

    def parts(self):
        """name -> (V, faces, materials, None, None), like gundeck.GunDeck.parts()"""
        out = {}
        for name, p in self.parts_.items():
            V, F, M, _ = p.arrays()
            out[name] = (V, F, M, None, None)
        return out

    def instances(self):
        return self.housed_copies()
