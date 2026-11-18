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
    """a plate: its top over the outline (n, 2) less the holes at z_top (a height, or a function of x), its underside thick
    under it, the edges of
    the outline and of each hole walled (one welded vertex set: cdt keeps the outline's and holes' points first)"""
    P2, T = cdt(outline, holes, step)
    N = len(P2)
    zt = z_top(P2[:, 0]) if callable(z_top) else np.full(N, z_top)
    V = np.concatenate([np.column_stack([P2, zt]), np.column_stack([P2, zt - thick])])
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
            w = min(1.25 * IN, 0.04 * length)
            h0 = float(np.clip(sh * length, -0.5 * length + w + 0.2 * IN, 0.5 * length - w - 0.2 * IN))
            lathe(part, np.asarray(c, float), axis, ref,
                  [(h0 - w, 0.0), (h0 - w, rr), (h0 + w, rr), (h0 + w, 0.0)], hoop_mat, n)


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
        if berth is None and os.path.exists(os.path.join(HERE, "berthdeck_handover.json")):
            berth = json.load(open(os.path.join(HERE, "berthdeck_handover.json")))
        self.berth = berth
        if berth is not None:
            # slice 13's hand-over: its deck's line and planks, beams, ledges and carlings take the card's estimates' places
            ov = self.c["overhead"]
            ov["berth_plank_in"] = berth["deck"]["plank_in"]
            ov["beam_sided_in"], ov["beam_moulded_in"] = berth["beams"]["sided_in"], berth["beams"]["moulded_in"]
            ov["carling_sided_in"], ov["carling_moulded_in"] = berth["carlings"]["sided_in"], berth["carlings"]["moulded_in"]
            ov["through_berth_deck"] = [o["name"] for o in berth["openings"]]
            self.berth = dict(berth, deck_line=berth["deck"]["line"], beam_x=berth["beams"]["x_m"],
                              ledge_x=berth["ledges"]["x_m"])
        # slice 13's ladders down onto the orlop: their run and a landing at the foot kept clear (x0, x1, y0, y1)
        self.ladder_boxes_orlop = []
        for lad in (berth or {}).get("ladders_down", []):
            w = lad["outside_stringers_in"] * IN / 2 + 3 * IN
            y0 = lad.get("y_m", 0.0)
            a, b = sorted((lad["top_x_m"], lad["foot_x_m"]))
            land = self.c["overhead"]["ladder_landing_m"]
            a, b = (a, b + land) if lad["foot_x_m"] > lad["top_x_m"] else (a - land, b)
            self.ladder_boxes_orlop.append((a, b, y0 - w, y0 + w))
            kc = lad.get("keep_clear_m")
            if kc:
                self.ladder_boxes_orlop.append((kc["x"][0], kc["x"][1], kc["y"][0], kc["y"][1]))
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
        # past the hold's ends, in the run and the bow, it goes on up the side under the berth deck to the deck's ends
        # (the deck transom and the deck hook there), its foot on the floors as they rise
        ea, ef = self.deck_ends()
        # columns mesh_step_m apart amidships, a quarter of that in the ends, where the side turns in fast: the chord
        # between columns stays within half an inch of the surface the parts against it are fitted to
        st, e = cc["mesh_step_m"], cc["end_fine_m"]
        xs = np.unique(np.round(np.concatenate([np.arange(ea, xa + e, st / 4), np.arange(xa + e, xf - e, st),
                                                np.arange(xf - e, ef, st / 4), [ef]]), 6))
        nz = 22
        skipped = []
        rows_in, rows_out, flats_in, flats_out = [], [], [], []
        y_l = (self.c["keelson"]["sided_in"] / 2 + cc["limber_in"]) * IN
        for x in xs:
            z1 = float(self.z_berth(x)) - self.berth_plank()
            z0 = min(float(self.z_floor(x)[0]), z1 - cc["end_least_m"])
            # (near the stem the inside face's solve can miss for the lowest rows, where the side turns in sharply:
            # the foot is raised over them there)
            for _ in range(8):
                zz = z0 + (z1 - z0) * (1.0 - np.cos(np.linspace(0, math.pi / 2, nz))) ** 1.0
                P, N = self.inner_at(np.full(nz, x), zz)
                miss = (np.abs(P[:, 0] - x) > 1e-3) | (np.abs(P[:, 2] - zz) > 1e-3)
                if not miss.any():
                    break
                z0 = float(zz[np.nonzero(miss)[0].max()]) + 0.02
            else:
                # (no column here: its neighbours carry the ceiling past it; never in the hold)
                if xa - 1e-6 <= x <= xf + 1e-6:
                    raise SystemExit("orlop: the ceiling's inside face can't be found at x %.3f" % x)
                skipped.append(x)
                continue
            rows_in.append(P)
            # (its thickness square to the frames: in the bow an offset along the surface's normal leans forward)
            Nt = np.array(N, float)
            Nt[:, 0] = 0.0
            Nt /= np.linalg.norm(Nt, axis=1, keepdims=True)
            rows_out.append(P + Nt * t)
            # the limber strake: flat at the floor heads from the limber passage out to the side
            y0 = P[0, 1]
            ys = np.linspace(y_l, y0, 4)
            flats_in.append(np.column_stack([np.full(4, x), ys, np.full(4, z0)]))
            flats_out.append(np.column_stack([np.full(4, x), ys, np.full(4, z0 - t)]))
        xs = np.array([x for x in xs if x not in skipped])
        hold_cols = [k for k, x in enumerate(xs) if xa - 1e-6 <= x <= xf + 1e-6]
        A = np.stack(rows_in, 1)          # (rows up the side, cols along x, 3)
        B = np.stack(rows_out, 1)
        # the flat's outer edge meets the side's lowest row: share it
        Fi = np.stack(flats_in, 1)[:, hold_cols]
        Fo = np.stack(flats_out, 1)[:, hold_cols]
        Fi[-1] = A[0][hold_cols]
        Fo[-1] = B[0][hold_cols]
        for sgn in (1.0, -1.0):
            s = np.array([1.0, sgn, 1.0])
            slab(part, A * s, B * s, "Ceiling")
            slab(part, Fi * s, Fo * s, "Ceiling")
        self.info["ceiling"] = {"x_m": [round(ea, 3), round(ef, 3)], "hold_x_m": [round(xa, 3), round(xf, 3)],
                                "rows": nz, "cols": len(xs),
                                "columns_skipped_x_m": [round(x, 3) for x in skipped]}
        # the limber boards: loose boards across the passage from the keelson's side to the limber strake
        lb = 1.5 * IN
        ks = self.c["keelson"]["sided_in"] / 2 * IN
        for x0 in np.arange(xa + 0.02, xf - 0.5, 0.5):
            x1 = x0 + 0.48
            zt = float(self.z_floor(0.5 * (x0 + x1))[0])
            for sgn in (1.0, -1.0):
                ya, yb = sorted((sgn * (ks + 0.1 * IN), sgn * (y_l + 1.0 * IN)))
                vbox(part_limber, (x0, ya, zt), (x1, yb, zt + lb), "Oak")

    def deck_ends(self):
        """the berth deck's ends along the ship (slice 13's hand-over; else the hold's)"""
        if self.berth is not None:
            return tuple(self.berth["deck"]["ends_m"])
        return self.x_hold

    def berth_plank(self):
        return self.c["overhead"]["berth_plank_in"] * IN

    # --- the keelson and the mast steps ---------------------------------------------------------------------------------
    def keelson(self, part, steps):
        """the keelson on the floors along the middle line (its top the card's keelson_over_rabbet_ft over the rabbet where
        the floors are lowest, rising with them toward the ends), from end to end of the hold, and a step for each mast"""
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
        self.info["keelson"] = {"top_over_rabbet_ft": self.c["heights"]["keelson_over_rabbet_ft"],
                                "x_m": [round(xa, 3), round(xf, 3)]}
        # the steps: each mast's heel bears on the keelson's top (the rig's heels move onto these points in slice 13:
        # mast_heels()), two chocks fore and aft of the heel's tenon and two cheeks either side of it, the mortise between
        for name, hp in self.mast_heels().items():
            x, z = hp["heel_m"][0], hp["heel_m"][2]
            D = hp["d_m"]
            L_, W = self.step_dims(hp)
            hh = k["step_high_of_d"] * D
            tw = 0.3 * D + 0.25 * IN
            # past the keelson's sides the step is chocked down onto the limber boards
            ks = k["sided_in"] / 2 * IN
            zl = float(self.z_floor(x)[0]) + 1.5 * IN
            for sgn in (1.0, -1.0):
                a, b = sorted((sgn * (ks + 0.1 * IN), sgn * W / 2))
                vbox(steps, (x - L_ / 2, a, zl), (x + L_ / 2, b, z), "Oak")
            vbox(steps, (x - L_ / 2, -W / 2, z), (x - tw / 2, W / 2, z + hh), "Oak")
            vbox(steps, (x + tw / 2, -W / 2, z), (x + L_ / 2, W / 2, z + hh), "Oak")
            vbox(steps, (x - tw / 2, -W / 2, z), (x + tw / 2, -tw / 2, z + hh), "Oak")
            vbox(steps, (x - tw / 2, tw / 2, z), (x + tw / 2, W / 2, z + hh), "Oak")
        self.info["mast_heels"] = self.mast_heels()

    def step_dims(self, hp):
        """a mast step's length and width: the card's, but longer than the heel by step_past_heel_in each way and as wide
        as the limber passages let it be (it stands on the keelson and is chocked onto the limber boards either side)"""
        k = self.c["keelson"]
        D = hp["d_m"]
        L_ = max(k["step_long_in"] * IN, D + 2 * k["step_past_heel_in"] * IN)
        y_l = (k["sided_in"] / 2 + self.c["ceiling"]["limber_in"]) * IN
        W = max(k["step_wide_in"] * IN, min(D + 2 * k["step_past_heel_in"] * IN, 2 * (y_l - 0.5 * IN)))
        return L_, W

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

    def platform_levels(self):
        """[(x0, x1, z)] of the after and fore platforms: each laid level fore and aft (and flat across) at the orlop's
        height under the berth deck at its middle (the berth deck's slice reads them to land its ladders: no build
        needed)"""
        o = self.c["orlop"]
        xh = self.hold_range()
        out = []
        for key in ("after_platform_px", "fore_platform_px"):
            x0, x1 = (self.plan_x(p) for p in o[key])
            x0, x1 = max(x0, xh[0] + 0.15), min(x1, xh[1] - 0.15)
            out.append((x0, x1, float(self.z_orlop(0.5 * (x0 + x1)))))
        return out

    def platforms(self, part, beams):
        """the after and fore platforms: planked, flat across at the orlop's height to the side, holed for the hatches and
        the masts, on beams across the ship at the card's pitch"""
        o = self.c["orlop"]
        th = o["plank_in"] * IN
        ops = self.openings()
        self.platform_x = {}
        for key, (x0, x1, zt) in zip(("after_platform_px", "fore_platform_px"), self.platform_levels()):
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

    def beam(self, part, x, z_top, w, d, holes, follow=None):
        """a beam across the ship at x, its top at z_top, ends let 2 in into the ceiling, cut clear of any hole it would
        cross (its sides an inch clear of the hole's; a beam whose face is within a centimetre of the hole's end is
        not cut: a coaming stands on it). With follow (the top's height at an
        x), its top follows the deck's sheer across its siding, its underside flat d under z_top"""
        y_end = float(self.ceil_y([x], [z_top - d / 2])[0]) + 2.0 * IN
        segs = [(-y_end, y_end)]
        for h in holes:
            h = np.asarray(h)
            if h[:, 0].min() - w / 2 + 0.01 < x < h[:, 0].max() + w / 2 - 0.01:
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
            if b - a > 0.15 and follow is not None:
                from gundeck import prism
                prism(part, [(x - w / 2, z_top - d), (x + w / 2, z_top - d), (x + w / 2, float(follow(x + w / 2))),
                             (x - w / 2, float(follow(x - w / 2)))], a, b, "Oak", axis=1)
            elif b - a > 0.15:
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
        hold_bh = [self.plan_x(v, "hold") for v in self.c["hold"]["bulkheads_px"].values()]
        for b in m["boxes"]:
            x0, x1 = self.box_x[b["name"]]
            z0 = float(self.z_keelson(0.5 * (x0 + x1))[0])
            z1 = float(self.z_berth(0.5 * (x0 + x1))) - self.berth_plank() - self.berth_beam_d()
            # the walls stand on the keelson's top, and beside it come down onto the limber boards (the end walls
            # notched over the keelson)
            # (a hold bulkhead standing at the box's after end closes it: no end wall of its own there, the sides
            # bedded on the bulkhead's fore face)
            xa_ = x0 + 1.25 * IN
            ends = [xa_, x1 - 1.25 * IN - t]
            for hx in hold_bh:
                if abs((hx + 1.5 * IN) - xa_) < 0.1:
                    xa_ = hx + 1.5 * IN - 0.1 * IN
                    ends = ends[1:]
            vbox(part, (x1 - 1.25 * IN - t, -hw, z0), (x1 - 1.25 * IN, hw, z1), "Deal")
            # (where the box's sides start under a platform's end, above its planks' underside they start a quarter
            # inch past its end)
            th_ = self.c["orlop"]["plank_in"] * IN
            over = [(v[1], v[2]) for v in self.platform_x.values() if v[0] < xa_ < v[1]]
            for yy in (-hw, hw - t):
                xs_ = xa_ if len(ends) == 1 else xa_ + t
                if over:
                    pe, pz = over[0]
                    vbox(part, (xs_, yy, z0), (x1 - 1.25 * IN - t, yy + t, pz - th_), "Deal")
                    vbox(part, (max(xs_, pe + 0.25 * IN), yy, pz - th_), (x1 - 1.25 * IN - t, yy + t, z1), "Deal")
                else:
                    vbox(part, (xs_, yy, z0), (x1 - 1.25 * IN - t, yy + t, z1), "Deal")
            if len(ends) == 2:
                vbox(part, (xa_, -hw, z0), (xa_ + t, hw, z1), "Deal")
            ks = self.c["keelson"]["sided_in"] / 2 * IN
            zl = float(self.z_floor(np.linspace(x0, x1, 9)).max()) + 1.5 * IN
            if hw - t > ks + 0.25 * IN:
                for sgn in (1.0, -1.0):
                    a, b2 = sorted((sgn * (hw - t), sgn * hw))
                    vbox(part, (xa_, a, zl), (x1 - 1.25 * IN, b2, z0), "Deal")
                    a, b2 = sorted((sgn * (ks + 0.25 * IN), sgn * (hw - t)))
                    for xe in ends:
                        vbox(part, (xe, a, zl), (xe + t, b2, z0), "Deal")
            if b["kind"] == "shot":
                self.shot_pile(shot, x0 + t + 0.5 * IN, x1 - t - 0.5 * IN, -hw + t, hw - t, z0)

    def berth_beam_d(self):
        return self.c["overhead"]["beam_moulded_in"] * IN

    def shot_pile(self, part, x0, x1, y0, y1, z0):
        """24 pdr round shot (5.55 in) filling a locker to within 2 ft of the orlop, the top layer close packed"""
        r = 5.55 / 2 * IN
        zt = float(self.z_orlop(0.5 * (x0 + x1))) - 2 * FT
        # only the top two layers are drawn (the rest unseen under them): a floor under them hides the box's bottom
        # (the layers 2r sqrt(2/3) apart, the top layer's balls in the hollows of the one under it)
        lz = 2 * r * math.sqrt(2.0 / 3.0)
        vbox(part, (x0, y0, z0), (x1, y1, zt - lz - 2 * r), "Iron")
        for k, dz in enumerate((-lz, 0.0)):
            dy = 2 * r * math.sqrt(0.75)
            off = 0.0 if k == 0 else r
            j = 0
            y = y0 + r + (0.0 if k == 0 else dy / 3)
            while y < y1 - r:
                x = x0 + r + (r if j % 2 else 0.0) + off
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
        self.room_list = []
        self.partition_xs = []
        self.partition_ys = []
        for key, plat in (("after", "after_platform_px"), ("fore", "fore_platform_px")):
            xa, xf, zt = self.platform_x[plat]
            for r in rc[key]:
                x0, x1 = (self.plan_x(p) for p in r["x_px"])
                x0, x1 = max(x0, xa), min(x1, xf)
                if x1 - x0 < 0.3:
                    self.info.setdefault("rooms_off_platform", []).append(r["name"])
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
                    self.room_list.append(dict(name=r["name"] + ("_" + side[0].upper() if r.get("mirror") else ""),
                                               kind=r["kind"], x0=x0, x1=x1, ya=ya, yb=yb, zt=zt))
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
        for x in (x0, x1):
            a, b = self.room_span(x, ya, yb, zt)
            walls.setdefault(("x", round(x, 3)), []).append((a, b, zt))
        for y in (ya, yb):
            if y is None:
                continue
            walls.setdefault(("y", round(y, 3)), []).append((x0, x1, zt))

    def room_span(self, x, ya, yb, zt):
        """a room's span across the ship at x: an open edge (None) runs to the side beyond the other edge (both open: side
        to side)"""
        side = float(self.ceil_y([x], [zt + 1.0])[0])
        if ya is None and yb is None:
            return -side, side
        if ya is None or yb is None:
            g = ya if ya is not None else yb
            return tuple(sorted((g, math.copysign(side, g))))
        return tuple(sorted((ya, yb)))

    def partition(self, part, axis, pos, a, b, zt, t, dw):
        """a partition along a line: axis 'x' stands across the ship at x = pos from y a to b; 'y' fore and aft at y = pos
        from x a to b. Up to the berth deck's beams' underside; a doorway in its middle when longer than 4 ft"""
        door = (b - a) > 4.0 * FT
        mid = 0.5 * (a + b)
        segs = [(a, mid - dw / 2), (mid + dw / 2, b)] if door else [(a, b)]
        if axis == "x":
            self.partition_xs.append((pos, t))
        else:
            self.partition_ys.append((pos, a, b, t))
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
        # up to the orlop's planks under a platform (between its beams, closing the room off), else to its beams' underside
        plat = [v[2] for v in getattr(self, "platform_x", {}).values() if v[0] - 0.05 < x < v[1] + 0.05]
        if z_top is not None:
            z1 = z_top
        elif plat:
            z1 = plat[0] - self.c["orlop"]["plank_in"] * IN
        else:
            z1 = float(self.z_orlop(x)) - (self.c["orlop"]["plank_in"] + self.c["orlop"]["beam_moulded_in"]) * IN
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
            sl, sw = self.step_dims(hp)
            if abs(x - xh) < sl / 2 + t / 2 + 0.1:
                zk = hp["heel_m"][2] + self.c["keelson"]["step_high_of_d"] * hp["d_m"]
                ks = max(ks, sw / 2)
        foot = [(-y_l, z0), (-y_l, z_lb), (-ks, z_lb), (-ks, zk), (ks, zk), (ks, z_lb), (y_l, z_lb), (y_l, z0)]
        P = np.array([(-ys[0], zs[0])] + foot + [(y, z) for y, z in zip(ys, zs)] +
                     [(-y, z) for y, z in zip(ys[::-1][:-1], zs[::-1][:-1])])
        from gundeck import prism
        prism(part, P, x - t / 2, x + t / 2, mat, axis=0)

    def hold_rooms(self, part, lining, powder):
        """the hold's bulkheads (hold plan); the magazines' raised floors and their powder barrels in two tiers (the
        copper lining is the material's look, not modelled sheet)"""
        hb = self.c["hold"]["bulkheads_px"]
        xs = {k: self.plan_x(v, "hold") for k, v in hb.items()}
        self.hold_x = xs
        for k, x in xs.items():
            if self.x_hold[0] + 0.3 < x < self.x_hold[1] - 0.3:
                self.bulkhead(part, x)
        # the magazines: a raised floor on joists (floor timbers across, scribed down to the ceiling and over the keelson),
        # cut to the side, and the powder barrels on it in rows fore and aft, a second tier in the first's cantlines, as
        # many as fit inside the side and under the orlop's beams
        L_, d, dh = self.c["hold"]["casks"]["powder_m"]
        mc = self.c["hold"]["magazine"]
        jt = mc["joist_sided_in"] * IN
        o = self.c["orlop"]
        self.info["powder_barrels"] = 0
        for a, b in (("after_magazine_aft", "after_magazine_fwd"), ("fore_magazine_aft", "fore_magazine_fwd")):
            x0, x1 = xs[a] + 1.5 * IN, xs[b] - 1.5 * IN
            # cut round a mast's step standing in it, or stopped short of one at its end
            steps = []
            for hp in self.mast_heels().values():
                sl, sw = self.step_dims(hp)
                xh = hp["heel_m"][0]
                if xh + sl / 2 + 2 * IN < x0 or xh - sl / 2 - 2 * IN > x1:
                    continue
                if xh < x0 + sl / 2 + 0.3:
                    x0 = xh + sl / 2 + 2 * IN
                elif xh > x1 - sl / 2 - 0.3:
                    x1 = xh - sl / 2 - 2 * IN
                else:
                    steps.append(densify(rect2(xh, 0.0, sl + 4 * IN, sw + 4 * IN), 0.2))
            xm = np.linspace(x0, x1, 9)
            zf = float(self.z_keelson(xm).max()) + mc["floor_over_keelson_in"] * IN + 0.08
            flat_slab(lining, self.side_outline(x0, x1, zf - 0.08, step=0.25, gap=1.0 * IN), steps, zf, 0.08, 0.3,
                      "Oak")
            nj = max(2, int(math.ceil((x1 - x0) / (mc["joist_pitch_ft"] * FT))) + 1)
            for xj in np.linspace(x0 + jt / 2 + 0.5 * IN, x1 - jt / 2 - 0.5 * IN, nj):
                if any(abs(xj - hp["heel_m"][0]) < self.step_dims(hp)[0] / 2 + jt / 2 + 0.1
                       for hp in self.mast_heels().values()):
                    continue
                self.bulkhead(lining, float(xj), "Oak", z_top=zf - 0.08, t=jt)
            s_ = d + 0.03
            placed = set()
            for i, xi in enumerate(np.arange(x0 + L_ / 2 + 0.05, x1 - L_ / 2, L_ + 0.05)):
                z_under = float(self.z_orlop(xi)) - (o["plank_in"] + o["beam_moulded_in"] + 1.0) * IN
                zc0 = zf + d / 2
                for j in range(-12, 13):
                    if zc0 + d / 2 < z_under and self.fits(xi, abs(j * s_), zc0, L_, d):
                        cask(powder, (xi, j * s_, zc0), EX, L_, d, dh, "Powder", "Copper", n=12, rings=7)
                        self.info["powder_barrels"] += 1
                        placed.add((i, j))
                zc1 = zc0 + math.sqrt(max(d * d - (s_ / 2) ** 2, 0.0)) + 0.2 * IN
                for j in range(-12, 12):
                    y = (j + 0.5) * s_
                    if (i, j) in placed and (i, j + 1) in placed and zc1 + d / 2 < z_under and \
                            self.fits(xi, abs(y), zc1, L_, d):
                        cask(powder, (xi, y, zc1), EX, L_, d, dh, "Powder", "Copper", n=12, rings=7)
                        self.info["powder_barrels"] += 1

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
        """the hold's casks, each stowage (card: hold.stowage) in two tiers either side of the middle line, lying fore and
        aft on the shingle bung up, the second tier in the first's cantlines, as many as fit inside the side and under
        the orlop's beams: the water in the main hold either side of the pump well and lockers, the spirits and the
        provisions in their rooms aft either side of the keelson"""
        cs = self.c["hold"]["casks"]
        o = self.c["orlop"]
        gap = cs["gap_in"] * IN
        self.info["casks"] = {}
        for st in self.c["hold"]["stowage"]:
            x0 = self.hold_x[st["from"]] + 0.15
            x1 = self.hold_x[st["to"]] - 0.15
            hw = self.stow_half_width(st) + 2.5 * IN
            L0, D0, Dh0 = cs[st["casks"][0]]
            L1, D1, Dh1 = cs[st["casks"][1]]
            n = 0

            def zc0_at(x):        # bedded half an inch into the shingle
                return float(np.max(self.shingle_z(np.array([x - L0 / 2, x + L0 / 2])))) + D0 / 2 - 0.5 * IN

            def room_at(x, L_, y, D, zc, sgn):
                z_under = float(self.z_orlop(x)) - (o["plank_in"] + o["beam_moulded_in"] + 1.0) * IN
                clear = not any(a < x + L_ / 2 and b > x - L_ / 2 and c_ < sgn * y + D / 2 and d_ > sgn * y - D / 2
                                for a, b, c_, d_ in self.ladder_boxes)
                return clear and zc + D / 2 < z_under and self.fits(x, y, zc, L_, D)
            # the ground tier on the shingle, bilge to bilge in rows out from the middle line; the second tier each in the
            # cantline between two ground casks side by side (at the same station, so its bilge bears on theirs)
            xs_ = list(np.arange(x0 + L0 / 2, x1 - L0 / 2, L0 + gap))
            s_ = D0 + gap
            h1 = math.sqrt(max((D0 / 2 + D1 / 2) ** 2 - (s_ / 2) ** 2, 0.0)) + 0.2 * IN
            def y0_at(x, L_):
                """the rows' inboard edge at x: the middle line's, or beside a ladder coming down there"""
                lad = [max(abs(c_), abs(d_)) for a, b, c_, d_ in self.ladder_boxes if a < x + L_ / 2 and b > x - L_ / 2]
                return max([hw] + [v + gap for v in lad])
            for sgn in (1.0, -1.0):
                placed = set()
                for i, x in enumerate(xs_):
                    for k in range(12):
                        y = y0_at(x, L0) + D0 / 2 + k * s_
                        if room_at(x, L0, y, D0, zc0_at(x), sgn):
                            cask(part, (x, sgn * y, zc0_at(x)), EX, L0, D0, Dh0, "CaskWood", "Iron")
                            placed.add((i, k))
                            n += 1
                for i, x in enumerate(xs_):
                    for k in range(11):
                        y = y0_at(x, L0) + D0 / 2 + (k + 0.5) * s_
                        zc = zc0_at(x) + h1
                        if (i, k) in placed and (i, k + 1) in placed and room_at(x, L1, y, D1, zc, sgn):
                            cask(part, (x, sgn * y, zc), EX, L1, D1, Dh1, "CaskWood", "Iron")
                            n += 1
            self.info["casks"][st["name"]] = n

    def stow_half_width(self, st):
        """the half width kept clear on the middle line of a stowage: the pump well's and lockers' boxes, or the keelson"""
        if st["middle"] == "boxes":
            return self.c["middle"]["half_width_px"] / self.c["registration"]["orlop"]["px_per_ft"] * FT
        return self.c["keelson"]["sided_in"] / 2 * IN

    def shingle(self, part):
        """the shingle ballast over the iron pigs under each stowage, from bulkhead to bulkhead, its top a set depth over
        the ceiling beside the keelson (levelled across, following the floor fore and aft), holed round the pump well
        and lockers in the main hold"""
        b = self.c["hold"]["ballast"]
        dz = b["shingle_over_ceiling_in"] * IN
        self.shingle_z = lambda x: self.z_floor(x) + dz            # noqa: E731
        hw = self.stow_half_width({"middle": "boxes"})
        runs = []
        for a, bb in sorted(self.box_x.values()):
            if runs and a < runs[-1][1] + 0.05:
                runs[-1][1] = max(runs[-1][1], bb)
            else:
                runs.append([a, bb])
        for st in self.c["hold"]["stowage"]:
            x0 = self.hold_x[st["from"]] + 1.6 * IN
            x1 = self.hold_x[st["to"]] - 1.6 * IN
            xs = np.linspace(x0, x1, max(8, int((x1 - x0) / 0.3)))
            ys = self.ceil_y(xs, self.shingle_z(xs)) - 0.1 * IN
            outline = np.concatenate([np.column_stack([xs, -ys]), np.column_stack([xs[::-1], ys[::-1]])])
            # (a box against the stowage's end bulkhead is holed from just inside the shingle's end)
            runs_in = [(max(a, x0 + 0.03), min(bb, x1 - 0.03)) for a, bb in runs if a < x1 - 0.1 and bb > x0 + 0.1]
            holes = [densify(rect2(0.5 * (a + bb), 0.0, bb - a, 2 * hw), 0.4) for a, bb in runs_in] \
                if st["middle"] == "boxes" else []
            # the shingle's top only (its body is down to the ceiling, unseen): a plate 2 in deep
            flat_slab(part, outline, holes, self.shingle_z, 2.0 * IN, 0.4, "Shingle")

    # --- the rooms' contents ---------------------------------------------------------------------------------------------
    def furnish(self, bags, fittings, goods):
        """what each orlop room holds, by its kind (card: furnish): the bread rooms' bags of biscuit stacked along the
        walls, the sail rooms' sails rolled in bolts, the store rooms' shelves with their boxes and kegs, the boatswain's
        counter and racks, the state rooms' cots and sea chests, the filling room's bench and cartridge racks. Each
        stands on the planks a clear inch off the walls and the side, an aisle left down the room's middle to its door
        (sizes from the stores kit, stores.json, where it has the item)"""
        fc = self.c["furnish"]
        c = fc["clear_in"] * IN
        rng = np.random.default_rng(14)
        n = {}
        for r in self.room_list:
            k = r["kind"]
            if k not in fc["kinds"]:
                continue
            spec = fc["kinds"][k]
            for strip in self.strips(r, spec["depth_m"], c, fc["aisle_m"]):
                x0, x1, y0, y1, out = strip
                getattr(self, "fill_" + spec["fill"])(bags if spec["fill"] == "bags" else
                                                     goods if spec["fill"] in ("bolts",) else fittings,
                                                     goods, x0, x1, y0, y1, r["zt"], out, spec, c, rng, n)
            if k == "boatswain":
                self.counter(fittings, r, c)
        self.info["furnish"] = n

    def strips(self, r, depth, c, aisle):
        """the strips along a room's long walls where its contents stand: [(x0, x1, y0, y1, outboard sign)], a gap at
        the middle of its length for the doors, the aisle down its middle clear; a narrow room keeps one strip, on its
        outboard side"""
        xm = 0.5 * (r["x0"] + r["x1"])
        lo, hi = self.room_span(xm, r["ya"], r["yb"], r["zt"])
        x0, x1 = r["x0"] + c + 1.0 * IN, r["x1"] - c - 1.0 * IN
        gap = 0.5 if x1 - x0 > 2.4 else 0.0
        xs = [(x0, xm - gap)] + [(xm + gap, x1)] if gap else [(x0, x1)]
        w = hi - lo
        out = []
        for a, b in xs:
            if w >= 2 * depth + aisle + 2 * c:
                out.append((a, b, lo + c, lo + c + depth, -1.0))
                out.append((a, b, hi - c - depth, hi - c, 1.0))
            elif w >= depth + 2 * c + 0.3:
                s = 1.0 if abs(hi) > abs(lo) else -1.0
                out.append((a, b, hi - c - depth, hi - c, 1.0) if s > 0 else (a, b, lo + c, lo + c + depth, -1.0))
        return out

    def room_ok(self, x0, x1, y0, y1, z0, z1, c):
        """whether a box x0..x1, y0..y1, z0..z1 stands inside the side, clear by c, at its four corners top and bottom"""
        xs = np.array([x0, x1, x0, x1, x0, x1, x0, x1])
        zs = np.array([z0, z0, z1, z1, z0, z0, z1, z1])
        ys = np.array([y0, y0, y0, y0, y1, y1, y1, y1])
        if any(a < x1 and b > x0 and c_ < y1 and d_ > y0 for a, b, c_, d_ in getattr(self, "keep_clear", [])):
            return False
        return bool(np.all(np.abs(ys) + c < self.ceil_y(xs, zs)))

    def fill_bags(self, part, goods, x0, x1, y0, y1, zt, out, spec, c, rng, n):
        L_, W, H = (v * IN for v in self.c["furnish"]["bread_bag_in"])
        layers = spec["layers"]
        x = x0
        while x + L_ <= x1:
            y = y0
            while y + W <= y1:
                for k in range(layers):
                    z = zt + k * H
                    if not self.room_ok(x, x + L_, y, y + W, z, z + H, c):
                        break
                    j = 0.4 * IN * (rng.random() - 0.5)
                    self.bag(part, x + 0.5 * L_ + j, y + 0.5 * W, z, L_ - 0.4 * IN, W - 0.4 * IN, H - 0.05 * IN)
                    n["bread_bags"] = n.get("bread_bags", 0) + 1
                y += W
            x += L_

    def bag(self, part, xc, yc, z, L_, W, H):
        """a bag of biscuit lying flat: a pillow, its sides bulging, flat underneath so the next stacks on it"""
        nx, ny = 6, 4
        u = np.linspace(-1, 1, nx)
        v = np.linspace(-1, 1, ny)
        rings = []
        for k, t in enumerate(np.linspace(0, 1, 5)):
            zz = z + H * t
            bul = 1.0 - 0.18 * (2 * t - 1) ** 2 if 0 < t < 1 else (0.9 if t == 0 else 0.78)
            P = []
            for a in u:
                P.append((xc + 0.5 * L_ * a * bul, yc - 0.5 * W * bul, zz))
            for b in v[1:]:
                P.append((xc + 0.5 * L_ * bul, yc + 0.5 * W * b * bul, zz))
            for a in u[::-1][1:]:
                P.append((xc + 0.5 * L_ * a * bul, yc + 0.5 * W * bul, zz))
            for b in v[::-1][1:-1]:
                P.append((xc - 0.5 * L_ * bul, yc + 0.5 * W * b * bul, zz))
            rings.append(np.array(P))
        solid(part, rings, "Canvas")

    def fill_shelves(self, part, goods, x0, x1, y0, y1, zt, out, spec, c, rng, n):
        """a rack of shelves along the strip: posts every 4 ft, shelves of deal, boxes and kegs on them at random"""
        t, ph = 1.0 * IN, 2.0 * IN
        # the shelves under the berth deck's beams, the top one leaving room for what stands on it
        head = min(self.under_berth_beams(x) for x in (x0, x1)) - zt - 0.03
        levels = [lv for lv in spec["levels_m"] if lv + t + 0.2 < head]
        if not levels:
            return
        top = levels[-1] + t
        posts = np.linspace(x0, x1, max(2, int(math.ceil((x1 - x0) / (4 * FT))) + 1))
        # trim the rack where the side closes in over it
        while y1 - y0 > 0.25 and not self.room_ok(x0, x1, y0, y1, zt, zt + top, c):
            if out > 0:
                y1 -= 0.05
            else:
                y0 += 0.05
        if y1 - y0 <= 0.25:
            return
        post_x = []
        for xp in posts:
            xa = min(max(xp - ph / 2, x0), x1 - ph)
            post_x.append((xa - 0.01, xa + ph + 0.01))
            for yp in (y0, y1 - ph):
                vbox(part, (xa, yp, zt), (xa + ph, yp + ph, zt + top), "Deal")
        for lv in levels:
            vbox(part, (x0, y0, zt + lv), (x1, y1, zt + lv + t), "Deal")
            n["shelves"] = n.get("shelves", 0) + 1
            # goods on it, clear of the posts and of the shelf over it
            room_h = min([l2 for l2 in levels if l2 > lv] + [lv + 0.45, head]) - lv - t - 0.02
            x = x0 + ph + 0.02
            while x < x1 - ph - 0.25:
                kind = rng.integers(0, 3)
                w_ = 0.30 if kind == 0 else 0.45
                hit = [b for a, b in post_x if a < x + w_ and b > x]
                if hit:
                    x = max(hit) + 0.01
                    continue
                if kind == 0:                       # a keg on end
                    d_ = min(0.30, room_h / 1.2, y1 - y0 - 0.06)
                    cask(goods, (x + d_ / 2, 0.5 * (y0 + y1), zt + lv + t + 0.6 * d_ + 0.001), EZ, 1.2 * d_, d_,
                         0.85 * d_, "CaskWood", "Iron", n=10, rings=5)
                    x += d_ + 0.04
                else:                               # a box
                    bl = 0.25 + 0.2 * rng.random()
                    bh = min(room_h, 0.12 + 0.2 * rng.random())
                    bw = min(y1 - y0 - 0.06, 0.25 + 0.15 * rng.random())
                    yb = y0 + 0.03 if out < 0 else y1 - 0.03 - bw
                    if x + bl > x1 - ph - 0.02 or any(a < x + bl and b > x for a, b in post_x):
                        x += 0.05
                        continue
                    vbox(goods, (x, yb, zt + lv + t), (x + bl, yb + bw, zt + lv + t + bh), "Deal")
                    x += bl + 0.03
                n["goods"] = n.get("goods", 0) + 1

    def fill_bolts(self, part, goods, x0, x1, y0, y1, zt, out, spec, c, rng, n):
        """sails rolled in bolts lying fore and aft along the strip, two layers, the upper in the lower's hollows"""
        d_ = spec["bolt_d_m"]
        L_ = x1 - x0
        for k in range(spec["layers"]):
            z = zt + d_ / 2 - 0.1 * IN + k * d_ * math.sqrt(0.75)      # the bottom bolts bedded on the planks
            y = (y0 if out < 0 else y1) - out * (d_ / 2 + k * d_ / 2)
            while (y0 <= y - d_ / 2 and y + d_ / 2 <= y1):
                if self.room_ok(x0, x1, y - d_ / 2, y + d_ / 2, z - d_ / 2, z + d_ / 2, c):
                    lathe(goods, (0.5 * (x0 + x1), y, z), EX, EZ,
                          [(-L_ / 2, 0.0), (-L_ / 2, d_ / 2 - 0.03), (-L_ / 2 + 0.03, d_ / 2), (L_ / 2 - 0.03, d_ / 2),
                           (L_ / 2, d_ / 2 - 0.03), (L_ / 2, 0.0)], "Canvas", 14)
                    n["sail_bolts"] = n.get("sail_bolts", 0) + 1
                y -= out * d_

    def fill_cots(self, part, goods, x0, x1, y0, y1, zt, out, spec, c, rng, n):
        """a state room's cot (a box bed on legs) along its outboard side and a sea chest at its foot"""
        L_, W, H = 6.0 * FT, 2.25 * FT, 1.5 * FT
        ya = y1 - W if out > 0 else y0
        if x1 - x0 < L_ or not self.room_ok(x0, x0 + L_, ya, ya + W, zt, zt + H, c):
            return
        vbox(part, (x0, ya, zt + H - 0.25), (x0 + L_, ya + W, zt + H), "Deal")
        for xl in (x0, x0 + L_ - 2 * IN):
            for yl in (ya, ya + W - 2 * IN):
                vbox(part, (xl, yl, zt), (xl + 2 * IN, yl + 2 * IN, zt + H - 0.25), "Deal")
        vbox(part, (x0 + 0.25, ya + 0.06, zt + H), (x0 + L_ - 0.1, ya + W - 0.06, zt + H + 0.12), "Canvas")
        n["cots"] = n.get("cots", 0) + 1
        sc = self.c["furnish"]["sea_chest_in"]
        if x0 + L_ + 0.05 + sc[0] * IN < x1:
            vbox(goods, (x0 + L_ + 0.05, ya + 0.03, zt), (x0 + L_ + 0.05 + sc[0] * IN, ya + 0.03 + sc[1] * IN,
                                                          zt + sc[2] * IN), "Mahogany")

    def fill_filling(self, part, goods, x0, x1, y0, y1, zt, out, spec, c, rng, n):
        """the filling room: its bench (copper on the top) and a cartridge rack over it"""
        L_, W, H = (v * IN for v in self.c["furnish"]["filling_bench_in"])
        L_ = min(L_, x1 - x0)
        ya = y1 - W if out > 0 else y0
        if not self.room_ok(x0, x0 + L_, ya, ya + W, zt, zt + H, c):
            return
        vbox(part, (x0, ya, zt + H - 2 * IN), (x0 + L_, ya + W, zt + H - 0.1 * IN), "Deal")
        vbox(part, (x0 + IN, ya + IN, zt + H - 0.1 * IN), (x0 + L_ - IN, ya + W - IN, zt + H), "Copper")
        for xl in (x0, x0 + L_ - 2 * IN):
            for yl in (ya, ya + W - 2 * IN):
                vbox(part, (xl, yl, zt), (xl + 2 * IN, yl + 2 * IN, zt + H - 2 * IN), "Deal")
        n["filling_bench"] = 1

    def counter(self, part, r, c):
        """the boatswain's counter down the middle of his store room, stopped short of a mast"""
        x0, x1 = r["x0"] + 0.9, r["x1"] - 0.9
        for name, h in self.mast_holes(x0 - 1.0, x1 + 1.0):
            xa, xb = h[:, 0].min() - 0.3, h[:, 0].max() + 0.3
            if xa < x1 and xb > x0:
                x1 = min(x1, xa) if xa - x0 > x1 - xb else x1
                x0 = max(x0, xb) if xa - x0 <= x1 - xb else x0
        if x1 - x0 < 0.6:
            return
        vbox(part, (x0, -0.3, r["zt"]), (x1, 0.3, r["zt"] + 0.9), "Deal")

    def berth_under(self, x):
        """the underside of the berth deck's planks at x (the top of the beams under them, following her sheer)"""
        return float(self.z_berth(x)) - self.berth_plank()

    def under_berth_beams(self, x):
        """the underside of the berth deck's beams at x"""
        return float(self.z_berth(x)) - self.berth_plank() - self.berth_beam_d()

    # --- ladders down into the hold --------------------------------------------------------------------------------
    def ladders(self, part):
        """a ladder down each orlop hatch the card marks, from its after coaming forward to the keelson's top (the
        gun deck's ladder: gundeck_1797.json's sizes)"""
        lc = self.gd.c["ladders"]
        self.ladder_feet = {}
        self.ladder_boxes = []
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
            # the stringers' feet stand outside the keelson: a chock under each down to the limber boards
            ang = math.radians(lc["angle_deg"])
            sd, st = (v * IN for v in lc["stringer_in"])
            foot = sd / math.sin(ang)
            zl = float(self.z_floor(np.array([xf - foot, xf + foot])).max()) + 1.5 * IN
            if any(self.hold_x[st["from"]] < xf < self.hold_x[st["to"]] for st in self.c["hold"]["stowage"]):
                zl = float(self.shingle_z(np.array([xf - foot, xf + foot])).max())       # on the shingle
            zl -= 0.25 * IN                                                                   # bedded
            for side in (-1.0, 1.0):
                yy = h["y"] + side * (lc["width_in"] * IN / 2 + st / 2)
                vbox(part, (xf - foot / 2 - IN, yy - st / 2, zl), (xf + foot / 2 + IN, yy + st / 2, zk(xf)), "Oak")
            self.ladder_boxes.append((min(xt, xf) - 0.6, max(xt, xf) + 0.6, h["y"] - 0.45, h["y"] + 0.45))
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
        lengths = []
        for k, (fx, side) in enumerate(cc["coils"]):
            x = xa + fx * (xf - xa)
            sgn = 1.0 if side == "stbd" else -1.0
            z0 = float(self.z_orlop(x)) - th + bh            # the battens' top
            y_side = float(np.min(self.ceil_y(np.full(5, x) + np.linspace(-1.6, 1.6, 5), np.full(5, z0 + 0.3))))
            ro = min(cc["outer_m"], 0.5 * (y_side - hw - 2 * IN) - 0.02)
            yc = sgn * (hw + 2 * IN + 0.02 + ro)
            ri = cc["inner_m"]
            turns = max(1, int((ro - ri - r) / pitch))
            # as many layers as the cable's length takes, up to what the tier's headroom holds
            per_layer = sum(2 * math.pi * (ri + r + pitch * (j + 0.5)) for j in range(turns))
            z_top = float(self.z_berth(x)) - self.berth_plank() - self.berth_beam_d() - cc["clear_under_beams_m"]
            fit = max(1, int((z_top - z0) / pitch))
            layers = min(fit, int(math.ceil(cc["length_fathoms"] * 1.8288 / per_layer)))
            lengths.append(round(layers * per_layer / 1.8288, 1))
            for layer in range(layers):
                z = z0 + r + 0.002 + layer * pitch
                t = np.linspace(0, turns * 2 * math.pi, turns * 24 + 1)
                rad = ri + r + pitch * t / (2 * math.pi)
                if layer % 2:
                    rad = rad[::-1]
                ph = 0.7 * k + 0.4 * layer
                P = np.column_stack([x + rad * np.cos(t + ph), yc + rad * np.sin(t + ph), np.full(len(t), z)])
                tube(part, P, r, "Cable", n=8)
                n_ += 1
        self.info["cable_coils"] = {"spirals": n_, "rope_r_m": round(r, 4), "fathoms": lengths}

    # --- the berth deck's beams overhead --------------------------------------------------------------------------------
    def overhead(self, part, knees):
        """the berth deck's overhead over the orlop (below its planks' underside: slice 13's hand-over, else the card's
        estimate): its beams at slice 13's stations with a hanging knee at each end, the ledges between, cut round the
        openings that go down through it and the masts, and carlings along their sides"""
        from gundeck import prism
        bw, bd = self.c["overhead"]["beam_sided_in"] * IN, self.berth_beam_d()
        xa, xf = self.deck_ends()
        if self.berth is not None and "beam_x" in self.berth:
            xs = [x for x in self.berth["beam_x"] if xa < x < xf]
        else:
            xs = list(np.arange(xa + 0.6, xf - 0.4, 4.0 * FT))
        oc = self.c["overhead"]
        holes = []
        if self.berth is not None:
            for o in self.berth["openings"]:
                holes.append(rect2(o["x_m"], o.get("y_m", 0.0), o["inside_m"][0], o["inside_m"][1]))
            masts = [(m["axis_at_beam_underside_m"][0], m["hole_radius_m"]) for m in self.berth["masts"].values()]
        else:
            for k in oc["through_berth_deck"]:
                v = self.gd.items[k]
                holes.append(rect2(v["x"], 0.0, v["Lo"], v["Wo"]))
            masts = [(float(np.mean(h[:, 0])), float(np.ptp(h[:, 1])) / 2) for n, h in self.mast_holes(xa, xf)]
        for mx, mr in masts:
            if xa < mx < xf:
                holes.append(rect2(mx, 0.0, 2 * mr, 2 * mr))
        # the deck's ends, where the deck transom and the deck hook take the planks: no beam or ledge there
        dc = oc["deck_ends"]
        end_spans = [(xa, xa + dc["transom_sided_in"] * IN), (xf - dc["hook_arm_ft"] * FT, xf)]

        def clear_of_ends(x, w):
            return all(x + w / 2 <= a - 0.5 * IN or x - w / 2 >= b + 0.5 * IN for a, b in end_spans)
        n_end = len(xs)
        xs = [x for x in xs if clear_of_ends(x, bw)]
        self.info["berth_beams_at_ends_left_out"] = n_end - len(xs)
        # the pumps' tubes: a beam or ledge in their way is scored round them (no carlings)
        tube_holes = [rect2(x, y, 2 * r + 2 * IN, 2 * r + 2 * IN) for x, y, r, _, _ in self.pump_tube_list()]
        # the carlings: fore and aft timbers along each opening's sides from the whole beam abaft it to the one before
        # it, which take the ends of the beams and ledges cut short by it, their tops at the planks' underside
        cw = oc["carling_sided_in"] * IN
        cd = oc["carling_moulded_in"] * IN
        n_carl = 0
        for h in list(holes):
            h = np.asarray(h)
            # (a beam whose face is the opening's end counts: a coaming sits on it)
            hx0, hx1 = h[:, 0].min() - bw / 2 + 0.01, h[:, 0].max() + bw / 2 - 0.01
            aft = [x for x in xs if x <= hx0]
            fwd = [x for x in xs if x >= hx1]
            if not aft or not fwd:
                continue
            ca, cf = max(aft) + bw / 2, min(fwd) - bw / 2
            zt = float(self.z_berth(0.5 * (ca + cf))) - self.berth_plank()
            for yy in (h[:, 1].min() - IN - cw / 2, h[:, 1].max() + IN + cw / 2):
                # (scored round a pump's tube in its way, as the beams are; its top follows her sheer)
                segs = [(ca, cf)]
                for th_ in tube_holes:
                    if th_[:, 1].min() < yy + cw / 2 and th_[:, 1].max() > yy - cw / 2:
                        ta, tb = th_[:, 0].min(), th_[:, 0].max()
                        segs = [p for a, b in segs for p in ((a, min(b, ta)), (max(a, tb), b)) if p[1] - p[0] > 0]
                for a, b in segs:
                    if b - a < 0.15:
                        continue
                    xs_ = np.linspace(a, b, max(2, int((b - a) / 0.3) + 1))
                    top = [(x_, self.berth_under(x_)) for x_ in xs_[::-1]]
                    prism(part, [(a, zt - cd), (b, zt - cd)] + top, yy - cw / 2, yy + cw / 2, "Oak", axis=1)
                n_carl += 1
        self.info["berth_carlings"] = n_carl
        # (a ledge ends against the carling's outer face, not through it)
        ledge_holes = [rect2(0.5 * (np.asarray(h)[:, 0].min() + np.asarray(h)[:, 0].max()), 0.0,
                             float(np.ptp(np.asarray(h)[:, 0])), float(np.ptp(np.asarray(h)[:, 1])) + 2 * cw)
                       for h in holes] + tube_holes
        holes = holes + tube_holes
        # the ledges between the beams (slice 13's stations), their tops at the planks' underside, cut as the beams
        lw, ld = (self.berth["ledges"]["sided_in"] * IN, self.berth["ledges"]["moulded_in"] * IN) \
            if self.berth is not None else (6.0 * IN, 5.0 * IN)
        ledges = [x for x in (self.berth or {}).get("ledge_x", []) if xa + 0.2 < x < xf - 0.2 and clear_of_ends(x, lw)]
        for xl in ledges:
            self.beam(part, xl, float(self.z_berth(xl)) - self.berth_plank(), lw, ld, ledge_holes, self.berth_under)
        self.info["berth_ledges"] = len(ledges)
        self.deck_transom_and_hook(part)
        self.overhead_holes = holes
        kc = oc["hanging_knee"]
        n_knees = 0
        for xb in xs:
            zt = float(self.z_berth(xb)) - self.berth_plank()
            self.beam(part, xb, zt, bw, bd, holes, self.berth_under)
            # a hanging knee at each end against the beam's fore face, its arm down the side, its other under the beam
            # (on its aft face where a partition across the ship stands at the fore one; none where both are taken)
            kt = kc["sided_in"] * IN
            for xk in (xb + bw / 2 + kt / 2, xb - bw / 2 - kt / 2):
                if all(abs(xk - px) > kt / 2 + pt / 2 + 0.5 * IN for px, pt in self.partition_xs):
                    for sgn in (1.0, -1.0):
                        n_knees += bool(self.hanging_knee(knees, xk, zt - bd + 0.002, sgn, kc))
                    break
        self.info["berth_beams"] = len(xs)
        self.info["hanging_knees"] = n_knees

    def deck_transom_and_hook(self, part):
        """under the berth deck's planks' ends: aft the deck transom, a timber across the run from side to side; forward
        the deck hook, a flat knee across the bow, its arms along the sides (card: overhead.deck_ends)"""
        if self.berth is None:
            return
        dc = self.c["overhead"]["deck_ends"]
        ea, ef = self.deck_ends()
        w, d = dc["transom_sided_in"] * IN, dc["transom_moulded_in"] * IN
        xt = ea + w / 2
        self.beam(part, xt, float(self.z_berth(xt)) - self.berth_plank(), w, d, [], self.berth_under)
        # the hook: inside the ceiling's face (let half an inch into it) from the deck's end aft along each side, its
        # throat a curve across
        hd = dc["hook_moulded_in"] * IN
        arm = dc["hook_arm_ft"] * FT
        thr = dc["hook_throat_ft"] * FT
        zt = float(self.z_berth(ef)) - self.berth_plank()
        xs = np.linspace(ef - arm, ef, 24)
        ys = self.ceil_y(xs, np.full(24, zt - hd / 2)) + 0.5 * IN
        # the inner edge: an arm's width in from the side at the after end, curving in to the middle line a throat's
        # length aft of the deck's end (a quarter ellipse)
        t = np.clip((xs - xs[0]) / max(arm - thr, 0.1), 0.0, 1.0)
        yi = np.clip((ys - dc["hook_arm_in"] * IN) * np.sqrt(1.0 - t ** 2), 0.0, None)
        k = int(np.argmax(yi <= 0.02)) if np.any(yi <= 0.02) else len(xs)
        inner = list(zip(xs[:k], yi[:k]))
        # counter-clockwise: starboard side forward, larboard side aft, then in round the throat and back
        poly = np.array([(x, -y) for x, y in zip(xs, ys)] + [(x, y) for x, y in zip(xs[::-1], ys[::-1])] +
                        inner + [(x, -y) for x, y in inner[::-1]])
        flat_slab(part, poly, [], lambda x: np.asarray(self.z_berth(x), float) - self.berth_plank() + 0.1 * IN, hd, 0.3, "Oak")
        self.info["deck_ends"] = {"transom_x_m": round(xt, 3), "hook_x_m": [round(xs[0], 3), round(ef, 3)]}

    def pillars(self, part):
        """a pillar on the middle line under each of the berth deck's beams over a platform (6 in square, its heel on the
        planks, its head under the beam), where no opening, mast, ladder or partition is in the way"""
        pc = self.c["overhead"]["pillar"]
        w = pc["sided_in"] * IN
        bw, bd = self.c["overhead"]["beam_sided_in"] * IN, self.berth_beam_d()
        xs = [x for x in (self.berth or {}).get("beam_x", [])]
        n = 0
        blocks = [np.asarray(h) for h in self.overhead_holes] + [np.asarray(o) for _, o, _ in self.openings()]
        for xb in xs:
            plat = [v for v in self.platform_x.values() if v[0] + 0.1 < xb < v[1] - 0.1]
            if not plat:
                continue
            x0, x1, zp = plat[0]
            if any(h[:, 0].min() - w < xb < h[:, 0].max() + w and h[:, 1].min() - w < 0 < h[:, 1].max() + w
                   for h in blocks):
                continue
            if any(a - pc["clear_m"] < xb < b + pc["clear_m"] for a, b, c_, d_ in self.ladder_boxes_orlop):
                continue
            # (not in a room across the middle line: its counter and shelves stand there)
            if any(r["x0"] - w < xb < r["x1"] + w and (r["ya"] or -9.0) < 0 < (r["yb"] or 9.0) for r in self.room_list):
                continue
            if any(abs(xb - px) < w / 2 + pt / 2 + IN for px, pt in self.partition_xs) or \
                    any(abs(py) < w / 2 + pt / 2 + IN and a < xb < b for py, a, b, pt in self.partition_ys):
                continue
            zt = float(self.z_berth(xb)) - self.berth_plank() - bd
            vbox(part, (xb - w / 2, -w / 2, zp - 0.25 * IN), (xb + w / 2, w / 2, zt + 0.1 * IN), "Oak")
            self.keep_clear.append((xb - w / 2 - 0.1, xb + w / 2 + 0.1, -w / 2 - 0.1, w / 2 + 0.1))
            n += 1
        self.info["pillars"] = n

    def pump_tube_list(self):
        """[(x, y, r, foot, kind)] of the pumps' tubes below the berth deck (r the half size; none without slice 13's
        hand-over): the hand-over's own tubes where it gives them (the chain pumps' square pipes, the brake pumps' round
        trees), else the gun deck card's"""
        if self.berth is None:
            return []
        given = self.berth["pumps"].get("tubes")
        if given:
            # (footed on the keelson's top where they stand over it at all, else on the limber boards; a tree hanging
            # past the keelson's side gets a step under the overhang: pump_tubes)
            ks = self.c["keelson"]["sided_in"] / 2 * IN
            return [(t["at_m"][0], t["at_m"][1], t["half_size_m"],
                     "keelson" if abs(t["at_m"][1]) - t["half_size_m"] < ks else "limber", t["kind"]) for t in given]
        g = self.gd.c["pumps"]
        r = g["brake"]["tube_in"] / 2 * IN
        ks = self.c["keelson"]["sided_in"] / 2 * IN
        tubes = [(self.berth["pumps"]["brake_x_m"], s * g["brake"]["y_in"] * IN, r, "keelson", "round") for s in (1.0, -1.0)]
        tubes += [(self.berth["pumps"]["chain_x_m"], s * (ks + r + 1.0 * IN), r, "limber", "round") for s in (1.0, -1.0)]
        return tubes

    def pump_tubes(self, part):
        """the pumps' tubes from the berth deck's planks down to the well (slice 13 brings them to its planks'
        underside): the brake pumps' round trees either side of the middle line, footed on the keelson's top; the chain
        pumps' square pipes (each pump's up and down) either side of the keelson, footed on the limber boards"""
        tubes = self.pump_tube_list()
        for x, y, r, foot, kind in tubes:
            zt = float(self.z_berth(x)) - self.berth_plank()
            zb = float(self.z_keelson(x)[0]) if foot == "keelson" else float(self.z_floor(x)[0]) + 1.5 * IN
            ks = self.c["keelson"]["sided_in"] / 2 * IN
            if foot == "keelson" and abs(y) + r > ks:
                # the step under the part hanging past the keelson's side, down to the limber boards
                sg = 1.0 if y > 0 else -1.0
                y0, y1 = sorted((sg * (ks + 0.05 * IN), y + sg * r))   # (a hairline off the keelson's side)
                vbox(part, (x - r, y0, float(self.z_floor(x)[0]) + 1.5 * IN), (x + r, y1, zb), "Oak")
                self.info.setdefault("pump_steps", 0)
                self.info["pump_steps"] += 1
            if kind == "square":
                vbox(part, (x - r, y - r, zb - 0.1 * IN), (x + r, y + r, zt + 0.1 * IN), "Oak")
                continue
            th = np.linspace(0, 2 * math.pi, 16, endpoint=False)
            rings = [np.column_stack([np.full(16, x) + r * np.cos(th), y + r * np.sin(th), np.full(16, z)])
                     for z in (zb - 0.1 * IN, zt + 0.1 * IN)]
            solid(part, rings, "Oak")
        self.info["pump_tubes"] = len(tubes)

    def hanging_knee(self, part, x, z_under, sgn, kc):
        """a hanging knee at x (its middle; sided along x) under a beam whose underside is z_under, on the side sgn: its
        arm down the ceiling, its other arm under the beam, a hollow throat between them"""
        from gundeck import prism
        t = kc["sided_in"] * IN
        m = kc["moulded_in"] * IN
        down, arm = kc["down_ft"] * FT, kc["arm_ft"] * FT
        zs = np.linspace(z_under, z_under - down, 8)
        ys = np.minimum(self.ceil_y(np.full(8, x - t / 2), zs), self.ceil_y(np.full(8, x + t / 2), zs))
        y_top = ys[0]
        # the under arm stops half an inch short of a partition fore and aft on this side; too short a knee is left out
        for py, a, b, pt in self.partition_ys:
            if py * sgn > 0 and a - t / 2 < x < b + t / 2:
                reach = abs(py) + pt / 2 + 0.5 * IN
                arm = min(arm, y_top - reach)
                if ys.min() - m < reach:
                    return False
        if arm < m + 6 * IN:
            return False
        # out along the ceiling from the beam down, back up the inner face, the throat, along under the beam
        outer = [(y, z) for y, z in zip(ys, zs)]
        inner = [(ys[-1] - m, zs[-1]), (ys[3] - m, zs[3])]
        th = np.linspace(0, math.pi / 2, 5)
        r = 0.5 * (y_top - m - (y_top - arm)) * 0.6
        cy, cz = ys[3] - m - r, zs[3] + 0.0
        throat = [(cy + r * math.cos(a), cz + r * math.sin(a) * (z_under - m - cz) / r) for a in th[1:]] if r > 0 else []
        under = [(y_top - arm, z_under - m * 0.8), (y_top - arm, z_under)]
        P = np.array(outer + inner + throat + under)
        if sgn < 0:
            P[:, 0] = -P[:, 0]
        prism(part, P, x - t / 2, x + t / 2, "Oak", axis=0)
        return True

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
                                 "BerthBeams", "HoldLadders", "Cables", "BreadBags", "RoomFittings", "Stores",
                                 "BerthKnees", "Pillars", "PumpTubes")}
        self.x_hold = self.hold_range()
        self.ceiling(P["Ceiling"], P["LimberBoards"])
        self.keelson(P["Keelson"], P["MastSteps"])
        self.platforms(P["OrlopDeck"], P["OrlopBeams"])
        self.middle(P["MiddleLine"], P["ShotPiles"])
        self.tier(P["OrlopBeams"], P["TierBattens"])
        self.rooms(P["Partitions"], None)
        self.coamings(P["OrlopCoamings"])
        self.hold_rooms(P["HoldBulkheads"], P["MagazineFloors"], P["PowderBarrels"])
        self.shingle(P["Shingle"])
        self.ladders(P["HoldLadders"])
        self.casks(P["WaterCasks"])
        self.overhead(P["BerthBeams"], P["BerthKnees"])
        self.keep_clear = list(self.ladder_boxes_orlop) + [
            (o[:, 0].min(), o[:, 0].max(), o[:, 1].min(), o[:, 1].max()) for _, o, _ in self.openings()]
        self.pillars(P["Pillars"])
        self.pump_tubes(P["PumpTubes"])
        self.cable_coils(P["Cables"])
        self.furnish(P["BreadBags"], P["RoomFittings"], P["Stores"])
        self.light_rooms()
        self.parts_ = P
        zm = float(self.z_orlop(0.0))
        self.info["heights_m"] = {"berth_top": round(float(self.z_berth(0.0)), 3), "orlop_top": round(zm, 3),
                                  "keelson_top": round(float(self.z_keelson(0.0)[0]), 3),
                                  "floor_heads": round(float(self.z_floor(0.0)[0]), 3),
                                  "shingle": round(float(self.shingle_z(0.0)[0]), 3)}
        # Humphreys' depth of hold: the ceiling at midships (the floor heads) to the berth deck's beams' tops
        self.info["depth_of_hold_ft"] = round((float(self.z_berth(0.0)) - float(self.z_floor(0.0)[0])) / FT, 2)
        return self

    def parts(self):
        """{name: (V, F, M, frame, uv)} as gundeck.GunDeck.parts()"""
        out = {}
        for name, p in self.parts_.items():
            V, F, M, U = p.arrays()
            if len(F):
                out[name] = (V, F, M, None, None)
        return out
