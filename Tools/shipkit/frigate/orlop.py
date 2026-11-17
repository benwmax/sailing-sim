"""The frigate's orlop and hold (docs/shipkit-14): the berth deck's beams overhead, the orlop's after and fore platforms
with their rooms, the cable tiers amidships between them, and the hold under them: the ceiling, the keelson and its mast
steps, the limber boards, the shingle ballast, the casks in their tiers, the pump well and the lockers on the middle
line, the magazines with their light rooms and filling room, the spirit room, the bread rooms and the store rooms.

    from orlop import Orlop;  ob = Orlop(sk, rig, dk, gd).build();  ob.parts()

Sizes and places are orlop_1797.json's, each with its source: the 1849 orlop and hold plans (registered to our masts
at each level), or the period's practice. Units: metres in the ship frame (X forward, Y starboard, Z up, origin on the
centreline at midships on waterline A).

The hold's side is the ceiling's inside face: the moulded surface moved in along its normal by the frames and the
ceiling together (16 in, the gun deck's wall), never lower than the floor heads' flat beside the keelson, where the
limber strake runs flat to the limber passage. The orlop lies parallel to the berth deck above it; until the berth deck
slice (13) hands over its line, the berth deck is the gun deck's well floor (6 ft 10 in under the gun deck).
"""
import json
import math
import os

import numpy as np

import loft
from deck import Part, solid, vbox, bar, lathe, in_poly, densify, rect2, cdt
from spars import circle, unit
from rigging import tube, rope_r

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)


# ---- mesh pieces -------------------------------------------------------------------------------------------------------
def slab(part, A, B, mat, mat_back=None):
    """a closed sheet between two grids of points A and B (rows, cols, 3) laid one over the other (B behind A): A's face,
    B's face turned the other way, and the four edges, every face pointing out of the sheet (one welded vertex set)"""
    A, B = np.asarray(A, float), np.asarray(B, float)
    r, c = A.shape[:2]
    idx = np.arange(r * c).reshape(r, c)
    V = np.concatenate([A.reshape(-1, 3), B.reshape(-1, 3)])
    n = r * c
    F = [(idx[i, j], idx[i, j + 1], idx[i + 1, j + 1], idx[i + 1, j]) for i in range(r - 1) for j in range(c - 1)]
    Fb = [tuple(n + k for k in f[::-1]) for f in F]
    E = []
    for loop in (idx[0, :], idx[:, -1], idx[-1, ::-1], idx[::-1, 0]):
        for a, b in zip(loop[:-1], loop[1:]):
            E.append((b, a, n + a, n + b))
    # turn so A's faces point away from B (the edges follow: a quad's winding agrees with its neighbours')
    f0 = F[len(F) // 2]
    nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
    if nrm @ (V[f0[0]] - V[n + f0[0]]) < 0:
        F, Fb, E = ([f[::-1] for f in G] for G in (F, Fb, E))
    k = len(part.M)
    part.add(V, F + Fb + E, mat)
    if mat_back:
        part.M[k + len(F):] = [mat_back] * (len(Fb) + len(E))


def flat_slab(part, outline, holes, z_top, thick, step, mat, mat_under=None):
    """a flat plate: its top over the outline (n, 2) less the holes at z_top, its underside thick under it, the edges of
    the outline and of each hole walled (one welded vertex set: cdt keeps the outline's and holes' points first)"""
    P2, T = cdt(outline, holes, step)
    N = len(P2)
    V = np.concatenate([np.column_stack([P2, np.full(N, z_top)]), np.column_stack([P2, np.full(N, z_top - thick)])])
    F = [tuple(int(i) for i in t) for t in T]
    Fu = [tuple(N + int(i) for i in t[::-1]) for t in T]
    W, k0 = [], 0
    for poly, is_hole in [(outline, False)] + [(h, True) for h in holes]:
        poly = np.asarray(poly, float)
        m = len(poly)
        a2 = 0.5 * np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1])
        # a counter-clockwise ring's quad (i, i+1 under, i+1 top...) faces out of its own inside; a hole's must face
        # into the hole (out of the plate)
        out = (a2 > 0) != is_hole
        for i in range(m):
            a, b = k0 + i, k0 + (i + 1) % m
            q = (a, N + a, N + b, b) if out else (b, N + b, N + a, a)
            W.append(q)
        k0 += m
    k = len(part.M)
    part.add(V, F + Fu + W, mat)
    if mat_under:
        part.M[k + len(F):] = [mat_under] * (len(Fu) + len(W))


def box_ring(part, x0, x1, y0, y1, z0, z1, t, mat, open_top=True):
    """a box's four walls of boards t thick standing on z0 to z1 round the rectangle x0..x1, y0..y1 (outside faces)"""
    vbox(part, (x0, y0, z0), (x0 + t, y1, z1), mat)
    vbox(part, (x1 - t, y0, z0), (x1, y1, z1), mat)
    vbox(part, (x0 + t, y0, z0), (x1 - t, y0 + t, z1), mat)
    vbox(part, (x0 + t, y1 - t, z0), (x1 - t, y1, z1), mat)


def cask(part, c, axis, length, bung_d, head_d, mat, hoop_mat=None, n=16, rings=9):
    """a cask lying along axis (unit) centred at c: a bulging stave body (head_d at the heads, bung_d at the bung), its
    heads set in a chime, iron hoops near each end and either side of the bung"""
    axis = unit(np.asarray(axis, float))
    ref = unit(np.cross(axis, EZ)) if abs(axis[2]) < 0.9 else EX
    s = np.linspace(-0.5, 0.5, rings)
    r = 0.5 * head_d + 0.5 * (bung_d - head_d) * (1.0 - (2 * s) ** 2)
    prof = [(float(si * length), float(ri)) for si, ri in zip(s, r)]
    chime = 0.6 * IN
    prof = [(-0.5 * length + chime, 0.0), (-0.5 * length + chime, 0.5 * head_d - 0.5 * IN)] + prof + \
           [(0.5 * length - chime, 0.5 * head_d - 0.5 * IN), (0.5 * length - chime, 0.0)]
    lathe(part, np.asarray(c, float), axis, ref, prof, mat, n)
    if hoop_mat:
        for sh in (-0.42, -0.30, -0.12, 0.12, 0.30, 0.42):
            rr = 0.5 * head_d + 0.5 * (bung_d - head_d) * (1.0 - (2 * sh) ** 2) + 0.15 * IN
            w = 1.25 * IN
            lathe(part, np.asarray(c, float), axis, ref,
                  [(sh * length - w, 0.0), (sh * length - w, rr), (sh * length + w, rr), (sh * length + w, 0.0)],
                  hoop_mat, n)


def sphere(part, c, r, mat, n=8):
    """a round shot: a uv sphere of n sides and n/2 rings"""
    th = np.linspace(0, math.pi, n // 2 + 1)
    prof = [(float(-r * math.cos(t)), float(r * math.sin(t))) for t in th]
    prof[0] = (prof[0][0], 0.0)
    prof[-1] = (prof[-1][0], 0.0)
    lathe(part, np.asarray(c, float), EZ, EX, prof, mat, n)


class Orlop:
    """The orlop, its overhead and the hold for the skin sk (skin.Skin, built), the rig (spars.Rig), the spar deck dk
    (deck.Deck) and the gun deck gd (gundeck.GunDeck, built: its hatchways, pumps and masts stack down through these
    decks). berth: the berth deck's hand-over (slice 13: its line, beam stations and openings), or None."""

    def __init__(self, sk, rig, dk, gd, path=os.path.join(HERE, "orlop_1797.json"), berth=None):
        import skin as SKM
        self.sk, self.rig, self.dk, self.gd, self.SKM = sk, rig, dk, gd, SKM
        self.c = json.load(open(path))
        self.berth = berth
        self.L = sk.L
        self.m = sk.m
        self.parts_ = {}
        self.info = {}
        self.lights = []
        h = self.c["heights"]
        self.t_in = h["ceiling_in_from_moulded_in"] * IN

    # --- heights along the ship ------------------------------------------------------------------------------------------
    def xpx(self, x):
        return np.asarray(x, float) / self.m.sx + self.L.mid_px

    def z_berth(self, x):
        """the berth deck's top at x (flat across)"""
        if self.berth is not None and "deck_line" in self.berth:
            D = np.asarray(self.berth["deck_line"], float)
            return np.interp(x, D[:, 0], D[:, 1])
        return self.gd.zg(x) - self.c["heights"]["berth_below_gun_ft"] * FT

    def z_orlop(self, x):
        """the orlop's top at x (flat across, parallel to the berth deck)"""
        return self.z_berth(x) - self.c["heights"]["orlop_below_berth_ft"] * FT

    def z_rabbet(self, x):
        x = np.atleast_1d(np.asarray(x, float))
        return np.array([self.L.rabbet_z(float(p)) for p in self.xpx(x)]) * self.m.sy

    def z_floor(self, x):
        """the floor heads' flat beside the keelson (the limber strake's top): the floors' 22 in over the rabbet amidships;
        in the ends, where the deadwood and the rising wood fill the narrow run and entrance, as high as the ceiling's
        inside must stand for the limber passage and the strake beside the keelson"""
        if not hasattr(self, "_floor"):
            self._floor = self.floor_line()
        X, Z = self._floor
        return np.atleast_1d(np.interp(np.asarray(x, float), X, Z))

    def floor_line(self):
        cc, k = self.c["ceiling"], self.c["keelson"]
        need = (k["sided_in"] / 2 + cc["limber_in"] + 6.0) * IN
        X = np.arange(-34.0, 36.0 + 1e-9, 0.5)
        base = self.z_rabbet(X) + self.c["heights"]["floor_over_rabbet_in"] * IN
        lo, hi = base.copy(), base + 4.0

        def wide(z):
            P, _ = self.inner_at(X, z)
            return (P[:, 1] >= need) & (np.abs(P[:, 0] - X) < 1e-3)
        ok = wide(lo)
        for _ in range(15):
            mid = 0.5 * (lo + hi)
            w = wide(mid)
            hi = np.where(w, mid, hi)
            lo = np.where(w, lo, mid)
        Z = np.where(ok, base, hi)
        return X, Z

    def z_keelson(self, x):
        """the keelson's top: its height over the floor heads amidships kept the length of the hold, so it rides up the
        rising wood in the ends with the floors"""
        h = self.c["heights"]
        return self.z_floor(x) + h["keelson_over_rabbet_ft"] * FT - h["floor_over_rabbet_in"] * IN

    # --- the ceiling's inside face ---------------------------------------------------------------------------------------
    def inner(self, X, Z):
        """the ceiling's inside face at moulded params (x px, z px arrays): (points (n, 3) starboard, moulded outward
        normals)"""
        X = np.atleast_1d(np.asarray(X, float))
        Z = np.atleast_1d(np.asarray(Z, float))
        U = Z >= self.SKM.KNUCKLE
        P, N, _ = self.m.frame(X, Z, U)
        return P - N * self.t_in, N

    def inner_at(self, x, z):
        """the inside face's half-breadth at x, z (arrays alike): (points, outward normals), the params moved until the
        point lands on x and z"""
        x = np.atleast_1d(np.asarray(x, float))
        z = np.broadcast_to(np.atleast_1d(np.asarray(z, float)), x.shape).astype(float)
        X, Zp = self.xpx(x), z / self.m.sy
        for _ in range(16):
            P, N = self.inner(X, Zp)
            dx, dz = x - P[:, 0], z - P[:, 2]
            if max(np.abs(dx).max(), np.abs(dz).max()) < 2e-5:
                break
            X = X + dx / self.m.sx
            Zp = Zp + dz / self.m.sy
            Zp = np.maximum(Zp, np.array([self.m.z_lo(float(a), False) for a in X]) + 1e-3)
        return P, N

    def ceil_y(self, x, z):
        """the hold's side (the ceiling's inside) half-breadth at x, z; below the floor heads' flat, the flat's edge"""
        P, _ = self.inner_at(x, np.maximum(z, self.z_floor(x)))
        return P[:, 1]

    # --- the plans ------------------------------------------------------------------------------------------------------
    def mast_x(self, name, z):
        pt, _, _ = self.gd.mast_at(name, float(z))
        return float(pt[0])

    def plan_x(self, px, which="orlop"):
        """a place along a plan (x px) in the ship, through the main and fore masts at that level"""
        reg = self.c["registration"][which]
        z = float(self.z_orlop(0.0)) if which == "orlop" else float(self.z_keelson(0.0)[0])
        mp = reg["masts_px"]
        p0, p1 = mp["main"], mp["fore"]
        x0, x1 = self.mast_x("main", z), self.mast_x("fore", z)
        if px <= p0:
            return x0 + (px - p0) / reg["px_per_ft"] * FT
        if px >= p1:
            return x1 + (px - p1) / reg["px_per_ft"] * FT
        return x0 + (px - p0) / (p1 - p0) * (x1 - x0)

    def plan_y(self, py, which="orlop"):
        reg = self.c["registration"][which]
        return (py - reg["centreline_px"]) / reg["px_per_ft"] * FT

    # --- the hold's range -----------------------------------------------------------------------------------------------
    def hold_range(self):
        """the hold's ends along the ship: where the floor (risen over the deadwood in the ends) comes within 3 ft of the
        orlop's top"""
        X = np.arange(-34.0, 36.0, 0.05)
        room = self.z_orlop(X) - self.z_floor(X)
        ok = np.nonzero(room > 3.0 * FT)[0]
        return float(X[ok[0]]), float(X[ok[-1]])

    # --- the ceiling ----------------------------------------------------------------------------------------------------
    def ceiling(self, part, part_limber):
        """the ceiling either side from the limber strake up to the berth deck's planks: its inside face a grid over x
        and height, its back the ceiling's thickness out; the limber strake flat across the floor heads to the limber
        passage; the limber boards over the passage to the keelson"""
        cc = self.c["ceiling"]
        t = cc["thick_in"] * IN
        xa, xf = self.x_hold
        # columns mesh_step_m apart amidships, a quarter of that in the ends, where the side turns in fast: the chord
        # between columns stays within half an inch of the surface the parts against it are fitted to
        st, e = cc["mesh_step_m"], cc["end_fine_m"]
        xs = np.unique(np.round(np.concatenate([np.arange(xa, xa + e, st / 4), np.arange(xa + e, xf - e, st),
                                                np.arange(xf - e, xf, st / 4), [xf]]), 6))
        nz = 22
        rows_in, rows_out, flats_in, flats_out = [], [], [], []
        y_l = (self.c["keelson"]["sided_in"] / 2 + cc["limber_in"]) * IN
        for x in xs:
            z0 = float(self.z_floor(x)[0])
            z1 = float(self.z_berth(x)) - self.berth_plank()
            zz = z0 + (z1 - z0) * (1.0 - np.cos(np.linspace(0, math.pi / 2, nz))) ** 1.0
            P, N = self.inner_at(np.full(nz, x), zz)
            rows_in.append(P)
            rows_out.append(P + N * t)
            # the limber strake: flat at the floor heads from the limber passage out to the side
            y0 = P[0, 1]
            ys = np.linspace(y_l, y0, 4)
            flats_in.append(np.column_stack([np.full(4, x), ys, np.full(4, z0)]))
            flats_out.append(np.column_stack([np.full(4, x), ys, np.full(4, z0 - t)]))
        A = np.stack(rows_in, 1)          # (rows up the side, cols along x, 3)
        B = np.stack(rows_out, 1)
        # the flat's outer edge meets the side's lowest row: share it
        Fi = np.stack(flats_in, 1)
        Fo = np.stack(flats_out, 1)
        Fi[-1] = A[0]
        Fo[-1] = B[0]
        for sgn in (1.0, -1.0):
            s = np.array([1.0, sgn, 1.0])
            slab(part, A * s, B * s, "Ceiling")
            slab(part, Fi * s, Fo * s, "Ceiling")
        self.info["ceiling"] = {"x_m": [round(xa, 3), round(xf, 3)], "rows": nz, "cols": len(xs)}
        # the limber boards: loose boards across the passage from the keelson's side to the limber strake
        lb = 1.5 * IN
        ks = self.c["keelson"]["sided_in"] / 2 * IN
        for x0 in np.arange(xa + 0.02, xf - 0.5, 0.5):
            x1 = x0 + 0.48
            zt = float(self.z_floor(0.5 * (x0 + x1))[0])
            for sgn in (1.0, -1.0):
                ya, yb = sorted((sgn * (ks + 0.1 * IN), sgn * (y_l + 1.0 * IN)))
                vbox(part_limber, (x0, ya, zt), (x1, yb, zt + lb), "Oak")

    def berth_plank(self):
        return 3.0 * IN

    # --- the keelson and the mast steps ---------------------------------------------------------------------------------
    def keelson(self, part, steps):
        """the keelson on the floors along the middle line, its top 3 ft over the rabbet, from end to end of the hold, and
        a step for each mast on it"""
        k = self.c["keelson"]
        w, d = k["sided_in"] * IN, k["moulded_in"] * IN
        xa, xf = self.x_hold
        xs = np.linspace(xa, xf, 120)
        zt = self.z_keelson(xs)
        rings = []
        for x, z in zip(xs, zt):
            rings.append(np.array([[x, -w / 2, z - d - 0.5 * IN], [x, w / 2, z - d - 0.5 * IN], [x, w / 2, z],
                                   [x, -w / 2, z]]))
        solid(part, rings, "Oak")
        self.info["keelson"] = {"top_over_rabbet_ft": k.get("top_over_rabbet_ft", 3.0),
                                "x_m": [round(xa, 3), round(xf, 3)]}
        # the steps: each mast's heel bears on the keelson's top (the rig's heels move onto these points in slice 13:
        # mast_heels()), two chocks fore and aft of the heel's tenon and two cheeks either side of it, the mortise between
        for name, hp in self.mast_heels().items():
            x, z = hp["heel_m"][0], hp["heel_m"][2]
            D = hp["d_m"]
            L_ = k["step_long_in"] * IN
            hh = k["step_high_of_d"] * D
            tw = 0.3 * D + 0.25 * IN
            W = k["step_wide_in"] * IN
            vbox(steps, (x - L_ / 2, -W / 2, z), (x - tw / 2, W / 2, z + hh), "Oak")
            vbox(steps, (x + tw / 2, -W / 2, z), (x + L_ / 2, W / 2, z + hh), "Oak")
            vbox(steps, (x - tw / 2, -W / 2, z), (x + tw / 2, -tw / 2, z + hh), "Oak")
            vbox(steps, (x - tw / 2, tw / 2, z), (x + tw / 2, W / 2, z + hh), "Oak")
        self.info["mast_heels"] = self.mast_heels()

    def mast_heels(self):
        """where each lower mast's axis meets the keelson's top: {name: heel_m, s_step (along the rig's axis), the rig's
        old heel, how much shorter the mast is below, its diameter at the heel}"""
        if getattr(self, "_heels", None):
            return self._heels
        out = {}
        for name in ("fore", "main", "mizzen"):
            m = self.rig.masts[name]
            O, u = np.asarray(m["O"], float), np.asarray(m["u"], float)
            s = float(m["s_step"])
            for _ in range(8):
                P = O + s * u
                s += (float(self.z_keelson(float(P[0]))[0]) - float(P[2])) / u[2]
            P, old = O + s * u, O + m["s_step"] * u
            D = 2 * float(self.gd.mast_at(name, float(old[2]) + 0.3)[1])
            out[name] = {"heel_m": [round(float(P[0]), 4), 0.0, round(float(P[2]), 4)], "s_step": round(s, 4),
                         "old_heel_m": [round(float(old[0]), 4), 0.0, round(float(old[2]), 4)],
                         "shorter_below_m": round(s - float(m["s_step"]), 4), "d_m": round(D, 4)}
        self._heels = out
        return out

    # --- the orlop's platforms and beams --------------------------------------------------------------------------------
    def side_outline(self, x0, x1, z, step=0.3, gap=0.0):
        """a platform's outline at height z from x0 to x1, across to the side less gap (counter-clockwise)"""
        xs = np.linspace(x0, x1, max(3, int(math.ceil((x1 - x0) / step)) + 1))
        ys = self.ceil_y(xs, np.full(len(xs), z)) - gap
        stb = np.column_stack([xs, ys])
        return np.concatenate([np.column_stack([xs, -ys]), stb[::-1]])

    def openings(self):
        """the holes through the orlop's platforms: [(name, outline (n, 2))]: the hatches (outside their coamings), the
        masts (with the partners' gap)"""
        out = []
        hc = self.c["hatches"]
        t = hc["coaming_thick_in"] * IN
        for h in hc["items"]:
            L_, W = (v * FT for v in h["inside_ft"])
            x, y = self.plan_x(h["x_px"]), self.plan_y(h["y_px"])
            out.append((h["name"], densify(rect2(x, y, L_ + 2 * t, W + 2 * t), 0.2), dict(h, x=x, y=y, L=L_, W=W)))
        return out

    def mast_holes(self, x0, x1):
        out = []
        for name in ("mizzen", "main", "fore"):
            z = float(self.z_orlop(0.0))
            pt, R, u = self.gd.mast_at(name, z)
            if x0 < pt[0] < x1:
                g = 0.5 * IN
                th = np.linspace(0, 2 * math.pi, 32, endpoint=False)
                out.append(("Mast_" + name, np.stack([(R + g) / u[2] * np.cos(th) + pt[0], (R + g) * np.sin(th)], 1)))
        return out

    def platforms(self, part, beams):
        """the after and fore platforms: planked, flat across at the orlop's height to the side, holed for the hatches and
        the masts, on beams across the ship at the card's pitch"""
        o = self.c["orlop"]
        th = o["plank_in"] * IN
        ops = self.openings()
        self.platform_x = {}
        for key in ("after_platform_px", "fore_platform_px"):
            x0, x1 = (self.plan_x(p) for p in o[key])
            x0, x1 = max(x0, self.x_hold[0] + 0.15), min(x1, self.x_hold[1] - 0.15)
            zt = float(self.z_orlop(0.5 * (x0 + x1)))
            outline = self.side_outline(x0, x1, zt)
            holes = [h for n, h, _ in ops if x0 < h[:, 0].mean() < x1]
            holes += [h for n, h in self.mast_holes(x0, x1)]
            flat_slab(part, outline, holes, zt, th, 0.3, "OrlopPlanks", "Deck")
            self.platform_x[key] = (x0, x1, zt)
            # its beams
            bw, bd = o["beam_sided_in"] * IN, o["beam_moulded_in"] * IN
            xs = np.arange(x0 + bw, x1 - bw / 2, o["beam_pitch_ft"] * FT)
            for xb in xs:
                self.beam(beams, xb, zt - th, bw, bd, [h for h in holes])
        return self

    def beam(self, part, x, z_top, w, d, holes):
        """a beam across the ship at x, its top at z_top, ends let 2 in into the ceiling, cut clear of any hole it would
        cross (the hole's outline widened by an inch)"""
        y_end = float(self.ceil_y([x], [z_top - d / 2])[0]) + 2.0 * IN
        segs = [(-y_end, y_end)]
        for h in holes:
            h = np.asarray(h)
            if h[:, 0].min() - w / 2 - IN < x < h[:, 0].max() + w / 2 + IN:
                ya, yb = h[:, 1].min() - IN, h[:, 1].max() + IN
                new = []
                for a, b in segs:
                    if yb <= a or ya >= b:
                        new.append((a, b))
                        continue
                    if ya > a:
                        new.append((a, ya))
                    if yb < b:
                        new.append((yb, b))
                segs = new
        for a, b in segs:
            if b - a > 0.15:
                vbox(part, (x - w / 2, a, z_top - d), (x + w / 2, b, z_top), "Oak")

    def tier(self, beams, battens):
        """the cable tiers amidships between the platforms: beams across at the platforms' pitch through the plan's four,
        their tops at the orlop's height, cut round the middle line's boxes; battens on them either side where the cables
        lie"""
        o = self.c["orlop"]
        th = o["plank_in"] * IN
        xa = self.platform_x["after_platform_px"][1]
        xf = self.platform_x["fore_platform_px"][0]
        bw, bd = o["beam_sided_in"] * IN, o["beam_moulded_in"] * IN
        hw = self.c["middle"]["half_width_px"] / self.c["registration"]["orlop"]["px_per_ft"] * FT
        xs = [self.plan_x(0.5 * (a + b)) for a, b in o["tier_beams_px"]]
        pitch = o["beam_pitch_ft"] * FT
        x = xs[-1] + pitch
        while x < xf - bw:
            xs.append(x)
            x += pitch
        mid = [rect2(0.5 * (self.box_x[k][0] + self.box_x[k][1]), 0.0, self.box_x[k][1] - self.box_x[k][0] + 2 * IN,
                     2 * hw + 2 * IN) for k in self.box_x]
        self.tier_x = sorted(xs)
        for xb in self.tier_x:
            zt = float(self.z_orlop(xb)) - th
            self.beam(beams, xb, zt, bw, bd, mid if xb < self.box_x_end else [])
        # battens fore and aft over the beams, each side from the middle line's boxes to the side
        bt, bh = (v * IN for v in o["batten_in"])
        gap = o["batten_gap_in"] * IN
        for sgn in (1.0, -1.0):
            y = hw + 2 * IN
            while True:
                x0, x1 = xa + 0.05, xf - 0.05
                z = float(self.z_orlop(0.5 * (x0 + x1))) - th
                ym = float(self.ceil_y([0.5 * (x0 + x1)], [z + bh])[0])
                if y + bt > ym - 2 * IN:
                    break
                # each batten runs only where the side leaves it room
                xs_ = np.linspace(x0, x1, 40)
                yy = np.minimum(self.ceil_y(xs_, np.full(40, z + bh)), self.ceil_y(xs_, np.full(40, z)))
                ok = xs_[yy > y + bt + IN]
                if len(ok) > 1:
                    a, b = sorted((sgn * y, sgn * (y + bt)))
                    vbox(battens, (ok[0], a, z), (ok[-1], b, z + bh), "Oak")
                y += bt + gap

    # --- the middle line's boxes ----------------------------------------------------------------------------------------
    def middle(self, part, shot):
        """the pump well round the pumps and the main mast, the shot lockers and the cable lockers on the middle line, each
        a box of 2 in deal from the floor heads up to the berth deck's beams"""
        m = self.c["middle"]
        hw = m["half_width_px"] / self.c["registration"]["orlop"]["px_per_ft"] * FT
        t = 2.0 * IN
        self.box_x = {}
        for b in m["boxes"]:
            x0, x1 = (self.plan_x(p) for p in b["x_px"])
            self.box_x[b["name"]] = (x0, x1)
        self.box_x_end = max(v[1] for v in self.box_x.values()) + 0.1
        for b in m["boxes"]:
            x0, x1 = self.box_x[b["name"]]
            z0 = float(self.z_keelson(0.5 * (x0 + x1))[0])
            z1 = float(self.z_berth(0.5 * (x0 + x1))) - self.berth_plank() - self.berth_beam_d()
            # the walls stand on the keelson's top and the limber strake beside it
            box_ring(part, x0 + 1.25 * IN, x1 - 1.25 * IN, -hw, hw, z0, z1, t, "Deal")
            if b["kind"] == "shot":
                self.shot_pile(shot, x0 + t + 0.5 * IN, x1 - t - 0.5 * IN, -hw + t, hw - t, z0)

    def berth_beam_d(self):
        return 13.0 * IN

    def shot_pile(self, part, x0, x1, y0, y1, z0):
        """24 pdr round shot (5.55 in) filling a locker to within 2 ft of the orlop, the top layer close packed"""
        r = 5.55 / 2 * IN
        zt = float(self.z_orlop(0.5 * (x0 + x1))) - 2 * FT
        # only the top two layers are drawn (the rest unseen under them): a floor under them hides the box's bottom
        vbox(part, (x0, y0, z0), (x1, y1, zt - 3 * r), "Iron")
        for k, dz in enumerate((-1.6 * r, 0.0)):
            dy = 2 * r * math.sqrt(0.75)
            off = 0.0 if k == 0 else r
            j = 0
            y = y0 + r + (0.0 if k == 0 else dy / 3)
            while y < y1 - r:
                x = x0 + r + (r if j % 2 else 0.0) + off * 0.0
                while x < x1 - r:
                    sphere(part, (x, y, zt + dz - r), r, "Iron", 8)
                    x += 2 * r
                y += dy
                j += 1

    # --- rooms on the platforms -----------------------------------------------------------------------------------------
    def rooms(self, part, doors_part):
        """each room's partitions (deal, 1.5 in, from the platform up to the berth deck's beams), a doorway in the side
        facing the middle of the ship"""
        rc = self.c["rooms"]
        t = rc["partition_in"] * IN
        dw = rc["door_wide_in"] * IN
        walls = {}
        for key, plat in (("after", "after_platform_px"), ("fore", "fore_platform_px")):
            xa, xf, zt = self.platform_x[plat]
            for r in rc[key]:
                x0, x1 = (self.plan_x(p) for p in r["x_px"])
                x0, x1 = max(x0, xa), min(x1, xf)
                if x1 - x0 < 0.3:
                    continue
                y0p, y1p = r["y_px"]
                sides = [None]
                if r.get("mirror"):
                    sides = ["port", "stbd"]
                elif r.get("side"):
                    sides = [r["side"]]
                for side in sides:
                    ya = self.plan_y(y0p) if y0p is not None else None
                    yb = self.plan_y(y1p) if y1p is not None else None
                    if side == "stbd" and r.get("mirror"):
                        ya, yb = (-yb if yb is not None else None), (-ya if ya is not None else None)
                    # an open edge (null) runs to the side; the partitions there are the ceiling's own
                    self.room_walls(walls, x0, x1, ya, yb, zt, t)
        # merge overlapping walls on one line and build them, each with a doorway near its middle if it faces inboard
        for (axis, pos), spans in sorted(walls.items()):
            spans.sort()
            merged = []
            for a, b, zt in spans:
                if merged and a <= merged[-1][1] + 1e-3:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b, zt])
            for a, b, zt in merged:
                if b - a < 0.05:
                    continue
                self.partition(part, axis, pos, a, b, zt, t, dw)
        return self

    def room_walls(self, walls, x0, x1, ya, yb, zt, t):
        """collect a room's walls: athwartships at x0 and x1 (from ya to yb, or to the side), fore and aft along ya and yb
        (from x0 to x1)"""
        def side_y(x, s):
            return s * float(self.ceil_y([x], [zt + 1.0])[0])
        lo = ya if ya is not None else None
        hi = yb if yb is not None else None
        for x in (x0, x1):
            a = lo if lo is not None else side_y(x, -1.0)
            b = hi if hi is not None else side_y(x, 1.0)
            walls.setdefault(("x", round(x, 3)), []).append((a, b, zt))
        for y in (ya, yb):
            if y is None:
                continue
            walls.setdefault(("y", round(y, 3)), []).append((x0, x1, zt))

    def partition(self, part, axis, pos, a, b, zt, t, dw):
        """a partition along a line: axis 'x' stands across the ship at x = pos from y a to b; 'y' fore and aft at y = pos
        from x a to b. Up to the berth deck's beams' underside; a doorway in its middle when longer than 4 ft"""
        door = (b - a) > 4.0 * FT
        mid = 0.5 * (a + b)
        segs = [(a, mid - dw / 2), (mid + dw / 2, b)] if door else [(a, b)]
        for s0, s1 in segs:
            xm = pos if axis == "x" else 0.5 * (s0 + s1)
            z1 = float(self.z_berth(xm)) - self.berth_plank() - self.berth_beam_d()
            if axis == "x":
                # the ends that reach the side are cut to it: a few slices up the side
                self.side_cut_wall(part, pos, s0, s1, zt, z1, t)
            else:
                self.y_wall(part, pos, s0, s1, zt, z1, t)
        if door:
            xm = pos if axis == "x" else mid
            z1 = float(self.z_berth(xm)) - self.berth_plank() - self.berth_beam_d()
            zd = min(zt + 5.0 * FT, z1 - 3 * IN)
            if axis == "x":
                vbox(part, (pos - t / 2, mid - dw / 2, zd), (pos + t / 2, mid + dw / 2, z1), "Deal")
            else:
                self.y_wall(part, pos, mid - dw / 2, mid + dw / 2, zd, z1, t)

    def y_wall(self, part, y, x0, x1, z0, z1, t, n=16):
        """a partition fore and aft at y from x0 to x1 between z0 and z1, an end that runs into the side (in the ends of
        the ship) cut back to it, half an inch clear"""
        from gundeck import prism
        zs = np.linspace(z0, z1, n)
        xs = np.linspace(x0, x1, max(2, int(math.ceil((x1 - x0) / 0.04)) + 1))
        need = abs(y) + t / 2
        lo, hi = [], []
        for z in zs:
            ok = np.nonzero(self.ceil_y(xs, np.full(len(xs), z)) > need)[0]
            if not len(ok):
                return
            lo.append((xs[ok[0]], z))
            hi.append((xs[ok[-1]], z))
        P = np.array(lo[::-1] + hi)          # (x, z): down the after edge, then up the fore edge
        if P[:, 0].max() - P[:, 0].min() < 0.05:
            return
        prism(part, P, y - t / 2, y + t / 2, "Deal", axis=1)

    def side_cut_wall(self, part, x, y0, y1, z0, z1, t):
        """a partition across the ship at x from y0 to y1 between z0 and z1, its ends that reach the side following it"""
        zs = np.linspace(z0, z1, 16)
        yside = np.minimum(self.ceil_y(np.full(16, x - t / 2), zs), self.ceil_y(np.full(16, x + t / 2), zs))
        ring_lo, ring_hi = [], []
        for z, ys in zip(zs, yside):
            a = max(y0, -ys)
            b = min(y1, ys)
            if b - a < 0.05:              # the side has closed in past the wall's run here: none of it stands at this z
                if not ring_lo:
                    return
                break
            ring_lo.append((a, z))
            ring_hi.append((b, z))
        if len(ring_lo) < 2:
            return
        P = np.array(ring_lo + ring_hi[::-1])
        from gundeck import prism
        prism(part, P, x - t / 2, x + t / 2, "Deal", axis=0)

    # --- hatches -------------------------------------------------------------------------------------------------------
    def coamings(self, part):
        hc = self.c["hatches"]
        t = hc["coaming_thick_in"] * IN
        hh = hc["coaming_high_in"] * IN
        for name, outline, h in self.openings():
            zt = float(self.z_orlop(h["x"]))
            L_, W = h["L"], h["W"]
            box_ring(part, h["x"] - L_ / 2 - t, h["x"] + L_ / 2 + t, h["y"] - W / 2 - t, h["y"] + W / 2 + t,
                     zt - self.c["orlop"]["plank_in"] * IN, zt + hh, t, "Oak")

    # --- the hold: bulkheads, magazines, casks, ballast --------------------------------------------------------------
    def bulkhead(self, part, x, mat="Deal", z_top=None, t=3.0 * IN):
        """a bulkhead across the hold at x from the floor heads to the orlop's beams (or z_top), its edges on the side"""
        z0 = float(self.z_floor(x)[0])
        z1 = z_top if z_top is not None else float(self.z_orlop(x)) - self.c["orlop"]["plank_in"] * IN - \
            self.c["orlop"]["beam_moulded_in"] * IN
        zs = np.linspace(z0, z1, 16)
        ys = np.minimum(self.ceil_y(np.full(16, x - t / 2), zs), self.ceil_y(np.full(16, x + t / 2), zs)) - 0.5 * IN
        # its foot: on the limber strake outboard, on the limber boards over the passage, over the keelson (and a mast's
        # step where one stands under it)
        ks = self.c["keelson"]["sided_in"] / 2 * IN
        y_l = ks + self.c["ceiling"]["limber_in"] * IN
        z_lb = z0 + 1.5 * IN
        zk = float(self.z_keelson(x)[0])
        for hp in self.mast_heels().values():
            xh = hp["heel_m"][0]
            if abs(x - xh) < self.c["keelson"]["step_long_in"] * IN / 2 + t / 2 + 0.1:
                zk = hp["heel_m"][2] + self.c["keelson"]["step_high_of_d"] * hp["d_m"]
                ks = max(ks, self.c["keelson"]["step_wide_in"] * IN / 2)
        foot = [(-y_l, z0), (-y_l, z_lb), (-ks, z_lb), (-ks, zk), (ks, zk), (ks, z_lb), (y_l, z_lb), (y_l, z0)]
        P = np.array([(-ys[0], zs[0])] + foot + [(y, z) for y, z in zip(ys, zs)] +
                     [(-y, z) for y, z in zip(ys[::-1][:-1], zs[::-1][:-1])])
        from gundeck import prism
        prism(part, P, x - t / 2, x + t / 2, mat, axis=0)

    def hold_rooms(self, part, lining, powder):
        """the hold's bulkheads (hold plan), the magazines lined with copper, their powder in barrels on racks"""
        hb = self.c["hold"]["bulkheads_px"]
        xs = {k: self.plan_x(v, "hold") for k, v in hb.items()}
        self.hold_x = xs
        for k, x in xs.items():
            if self.x_hold[0] + 0.3 < x < self.x_hold[1] - 0.3:
                self.bulkhead(part, x)
        # the magazines: a raised floor on joists over the keelson, cut to the side, and the powder barrels on it in rows
        # fore and aft, as many as fit inside the side
        L_, d, dh = self.c["hold"]["casks"]["powder_m"]
        self.info["powder_barrels"] = 0
        for a, b in (("after_magazine_aft", "after_magazine_fwd"), ("fore_magazine_aft", "fore_magazine_fwd")):
            x0, x1 = xs[a] + 1.6 * IN, xs[b] - 1.6 * IN
            xm = np.linspace(x0, x1, 9)
            zf = float(self.z_keelson(xm).max()) + 2.0 * IN + 0.08
            flat_slab(lining, self.side_outline(x0, x1, zf - 0.08, step=0.25, gap=1.0 * IN), [], zf, 0.08, 0.3, "Oak")
            for xi in np.arange(x0 + L_ / 2 + 0.05, x1 - L_ / 2, L_ + 0.05):
                k = 0
                while True:
                    ys = [sg * (k * (d + 0.03)) for sg in ((1.0,) if k == 0 else (1.0, -1.0))]
                    if not self.fits(xi, abs(ys[0]), zf + d / 2 + 0.01, L_, d):
                        break
                    for yi in ys:
                        cask(powder, (xi, yi, zf + d / 2 + 0.01), EX, L_, d, dh, "Powder", "Copper", n=12, rings=7)
                        self.info["powder_barrels"] += 1
                    k += 1

    def fits(self, x, y, zc, L_, D, clear=IN):
        """whether a cask lying fore and aft at (x, y, zc) (y the side's) stands clear of the ceiling: its round at both
        heads and the bung, all the way round, clear inside the side by clear"""
        th = np.linspace(0, 2 * math.pi, 12, endpoint=False)
        for xx in (x - L_ / 2, x, x + L_ / 2):
            yy = y + D / 2 * np.cos(th)
            zz = zc + D / 2 * np.sin(th)
            if np.any(yy + clear > self.ceil_y(np.full(len(th), xx), zz)):
                return False
        return True

    def casks(self, part):
        """water casks in two tiers either side of the middle line through the main hold, end on fore and aft on the
        shingle, as many as fit inside the side"""
        cs = self.c["hold"]["casks"]
        gap = cs["gap_in"] * IN
        x0 = self.hold_x["main_hold_aft"] + 0.15
        x1 = self.hold_x["fore_magazine_aft"] - 0.15
        hw = self.c["middle"]["half_width_px"] / self.c["registration"]["orlop"]["px_per_ft"] * FT + 2.5 * IN
        n = 0
        zsh = self.shingle_z
        for tier, (L_, D, Dh) in enumerate((cs["leaguer_m"], cs["butt_m"])):
            zc = zsh + D / 2 if tier == 0 else zsh + cs["leaguer_m"][1] + D / 2 - 0.12 * D
            yoff = 0.0 if tier == 0 else 0.5 * (cs["leaguer_m"][1] + gap)
            for sgn in (1.0, -1.0):
                y = hw + D / 2 + yoff
                while True:
                    placed = False
                    x = x0 + L_ / 2 + (0.5 * (L_ + gap) if tier == 1 else 0.0)
                    while x < x1 - L_ / 2:
                        if self.in_middle(x, L_):
                            x += L_ + gap
                            continue
                        if self.fits(x, y, zc, L_, D):
                            cask(part, (x, sgn * y, zc), EX, L_, D, Dh, "CaskWood", "Iron")
                            n += 1
                            placed = True
                        x += L_ + gap
                    if not placed:
                        break
                    y += D + gap
        self.info["casks"] = n

    def in_middle(self, x, L_):
        """whether a cask at x would stand under the middle line's boxes' ends (it never does, they're inboard of the
        casks: kept for the hatches' wells later)"""
        return False

    def shingle(self, part):
        """the shingle ballast levelled over the iron pigs through the main hold, from bulkhead to bulkhead"""
        b = self.c["hold"]["ballast"]
        x0 = self.hold_x["main_hold_aft"] + 1.6 * IN
        x1 = self.hold_x["fore_magazine_aft"] - 1.6 * IN
        z = float(max(self.z_floor(x0)[0], self.z_floor(x1)[0], self.z_floor(0.5 * (x0 + x1))[0])) + \
            b["shingle_over_ceiling_in"] * IN
        self.shingle_z = z
        xs = np.linspace(x0, x1, 60)
        ys = self.ceil_y(xs, np.full(60, z)) - 0.1 * IN
        outline = np.concatenate([np.column_stack([xs, -ys]), np.column_stack([xs[::-1], ys[::-1]])])
        hw = self.c["middle"]["half_width_px"] / self.c["registration"]["orlop"]["px_per_ft"] * FT
        runs = []
        for a, b in sorted(self.box_x.values()):
            if runs and a < runs[-1][1] + 0.05:
                runs[-1][1] = max(runs[-1][1], b)
            else:
                runs.append([a, b])
        holes = [densify(rect2(0.5 * (a + b), 0.0, b - a, 2 * hw), 0.4) for a, b in runs if x0 + 0.1 < a and b < x1 - 0.1]
        # the shingle's top only (its body is down to the ceiling, unseen): a plate 2 in deep
        flat_slab(part, outline, holes, z, 2.0 * IN, 0.4, "Shingle")

    # --- ladders down into the hold --------------------------------------------------------------------------------
    def ladders(self, part):
        """a ladder down each orlop hatch the card marks, from its after coaming forward to the keelson's top (the
        gun deck's ladder: gundeck_1797.json's sizes)"""
        lc = self.gd.c["ladders"]
        self.ladder_feet = {}
        for name, outline, h in self.openings():
            if not h.get("ladder"):
                continue
            # down from the after coaming going forward, or from the fore coaming going aft where a bulkhead of the
            # hold stands in the way forward
            zk = lambda x: float(self.z_keelson(x)[0])                             # noqa: E731
            run = (float(self.z_orlop(h["x"])) - zk(h["x"])) / math.tan(math.radians(lc["angle_deg"]))
            bx = list(self.hold_x.values())
            d = 1.0
            xt = h["x"] - h["L"] / 2
            if any(xt - 0.1 < b < xt + run + 0.3 for b in bx):
                d, xt = -1.0, h["x"] + h["L"] / 2
            zt = float(self.z_orlop(xt))
            xf, drop = self.gd.ladder(part, xt, zt, d, h["y"], zk, lc)
            self.ladder_feet[name] = {"x_m": round(xf, 3), "drop_m": round(drop, 3)}
        self.info["ladders"] = self.ladder_feet

    # --- the cables in their tiers ------------------------------------------------------------------------------------
    def cable_coils(self, part):
        """the hemp cables flaked down in the tiers either side of the middle line, each a flat spiral per layer (in
        and out by turns), the layers stacked on the battens (card: cables)"""
        cc = self.c["cables"]
        r = rope_r(cc["circ_in"])
        gap = 0.004
        pitch = 2 * r + gap
        hw = self.c["middle"]["half_width_px"] / self.c["registration"]["orlop"]["px_per_ft"] * FT
        th = self.c["orlop"]["plank_in"] * IN
        bh = self.c["orlop"]["batten_in"][1] * IN
        xa = self.platform_x["after_platform_px"][1]
        xf = self.platform_x["fore_platform_px"][0]
        n_ = 0
        for k, (fx, side) in enumerate(cc["coils"]):
            x = xa + fx * (xf - xa)
            sgn = 1.0 if side == "stbd" else -1.0
            z0 = float(self.z_orlop(x)) - th + bh            # the battens' top
            y_side = float(np.min(self.ceil_y(np.full(5, x) + np.linspace(-1.6, 1.6, 5), np.full(5, z0 + 0.3))))
            ro = min(cc["outer_m"], 0.5 * (y_side - hw - 2 * IN) - 0.02)
            yc = sgn * (hw + 2 * IN + 0.02 + ro)
            ri = cc["inner_m"]
            turns = max(1, int((ro - ri - r) / pitch))
            for layer in range(cc["layers"]):
                z = z0 + r + 0.002 + layer * pitch
                t = np.linspace(0, turns * 2 * math.pi, turns * 24 + 1)
                rad = ri + r + pitch * t / (2 * math.pi)
                if layer % 2:
                    rad = rad[::-1]
                ph = 0.7 * k + 0.4 * layer
                P = np.column_stack([x + rad * np.cos(t + ph), yc + rad * np.sin(t + ph), np.full(len(t), z)])
                tube(part, P, r, "Hemp", n=8)
                n_ += 1
        self.info["cable_coils"] = {"spirals": n_, "rope_r_m": round(r, 4)}

    # --- the berth deck's beams overhead --------------------------------------------------------------------------------
    def overhead(self, part):
        """the berth deck's beams over the orlop, 15 in sided and 13 in moulded under its 3 in planks (estimate until the
        berth deck slice hands over its stations), at the platforms' pitch, cut round the gun deck's hatchways stacked
        over this deck and the masts"""
        bw, bd = 15.0 * IN, self.berth_beam_d()
        xa, xf = self.x_hold
        if self.berth is not None and "beam_x" in self.berth:
            xs = [x for x in self.berth["beam_x"] if xa < x < xf]
        else:
            xs = list(np.arange(xa + 0.6, xf - 0.4, 4.0 * FT))
        holes = []
        for k, v in self.gd.items.items():
            holes.append(rect2(v["x"], 0.0, v["Lo"], v["Wo"]))
        for n, h in self.mast_holes(xa, xf):
            holes.append(h)
        for xb in xs:
            zt = float(self.z_berth(xb)) - self.berth_plank()
            self.beam(part, xb, zt, bw, bd, holes)
        self.info["berth_beams"] = len(xs)

    # --- the lanterns ---------------------------------------------------------------------------------------------------
    def light_rooms(self):
        """the light rooms' lanterns and the cockpit's (game data: each a warm point light)"""
        for name, px, py in (("LightRoomAft", 499.0, 509.0), ("Cockpit", 1250.0, 509.0)):
            x, y = self.plan_x(px), self.plan_y(py)
            z = float(self.z_orlop(x)) + 1.4
            self.lights.append({"name": "Lantern_" + name, "at_m": [round(x, 3), round(y, 3), round(z, 3)],
                                "colour_rgb": [1.0, 0.62, 0.3], "cast_shadows": True})

    # --- build ---------------------------------------------------------------------------------------------------------
    def build(self):
        P = {n: Part() for n in ("Ceiling", "LimberBoards", "Keelson", "MastSteps", "OrlopDeck", "OrlopBeams",
                                 "TierBattens", "MiddleLine", "ShotPiles", "Partitions", "OrlopCoamings",
                                 "HoldBulkheads", "MagazineFloors", "PowderBarrels", "WaterCasks", "Shingle",
                                 "BerthBeams", "HoldLadders", "Cables")}
        self.x_hold = self.hold_range()
        self.ceiling(P["Ceiling"], P["LimberBoards"])
        self.keelson(P["Keelson"], P["MastSteps"])
        self.middle(P["MiddleLine"], P["ShotPiles"])
        self.platforms(P["OrlopDeck"], P["OrlopBeams"])
        self.tier(P["OrlopBeams"], P["TierBattens"])
        self.rooms(P["Partitions"], None)
        self.coamings(P["OrlopCoamings"])
        self.hold_rooms(P["HoldBulkheads"], P["MagazineFloors"], P["PowderBarrels"])
        self.shingle(P["Shingle"])
        self.casks(P["WaterCasks"])
        self.overhead(P["BerthBeams"])
        self.ladders(P["HoldLadders"])
        self.cable_coils(P["Cables"])
        self.light_rooms()
        self.parts_ = P
        zm = float(self.z_orlop(0.0))
        self.info["heights_m"] = {"berth_top": round(float(self.z_berth(0.0)), 3), "orlop_top": round(zm, 3),
                                  "keelson_top": round(float(self.z_keelson(0.0)[0]), 3),
                                  "floor_heads": round(float(self.z_floor(0.0)[0]), 3),
                                  "shingle": round(self.shingle_z, 3)}
        # Humphreys' depth of hold: the ceiling at midships (the floor heads) to the berth deck's beams' tops
        self.info["depth_of_hold_ft"] = round((float(self.z_berth(0.0)) - self.berth_plank() -
                                               float(self.z_floor(0.0)[0])) / FT, 2)
        return self

    def parts(self):
        """{name: (V, F, M, frame, uv)} as gundeck.GunDeck.parts()"""
        out = {}
        for name, p in self.parts_.items():
            V, F, M, U = p.arrays()
            if len(F):
                out[name] = (V, F, M, None, None)
        return out
