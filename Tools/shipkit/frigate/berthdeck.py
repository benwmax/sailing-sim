"""The frigate's berth deck (docs/shipkit-13): the planked deck 7 ft 2 in under the gun deck, the side's ceiling up to
the gun deck, the gun deck's framing over it (its beams, ledges, carlings, clamp and knees), the openings down to the
orlop with their coamings, gratings and ladders, what comes down through the gun deck onto it (the capstan's spindle on
its step, the riding bitts' posts, the pumps' tubes, the masts in their wedges, the cables in their scuttles), the
wardroom aft with its state rooms, the steerage and the officers' rooms forward of it, the crew's deck where the men
slept in hammocks and ate at mess tables, the sick bay forward, and the horn lanterns (and their lights, as game data).

    from berthdeck import BerthDeck;  bd = BerthDeck(gd).build();  bd.parts();  bd.copies_

gd is the gun deck (gundeck.GunDeck, built in berth mode: gundeck.GunDeck(..., berth=<this card's path>)): the berth
deck takes its line from it (its top the gun deck's less top_below_gun_deck_in all along, so it keeps her sheer), its
framing's stations and the openings it frames round. The stores kit's (stores.Kit) hammocks, hooks, mess tables,
benches, kids and chests are hung and laid here as linked copies (copies_, their items copy_items). Sizes and places are
berthdeck_1797.json's, each with its source. Units: metres in the ship frame (X forward, Y starboard, Z up, origin on
the centreline at midships on waterline A).

What it hands the orlop slice (14) is berth_deck.json (the berth deck's line, its beams' stations, its openings, the
masts, pumps and cables through it): the boundary between the two is the underside of this deck's planks. Below it the
orlop slice builds the berth deck's beams and everything under them; above it this module builds the rest.

The berth deck is a GunDeck in most of what it does (the deck's surface and its UVs, the waterways, the members over
it, the coamings, wells and ladders, the bulkheads and lanterns): its own methods put them on this deck's line, under
the gun deck's planks and round its openings.
"""
import json
import math
import os

import numpy as np

import loft
from deck import Part, solid, vbox, lathe, revolve, in_poly, seg_dist, densify, rect2, cdt, newell
from gundeck import GunDeck, prism, prism2, disc
from deck import bar
from rigging import tube
from spars import box
from spars import circle, ring_band

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)
# how far a copy standing on the planks (a bench, a chest, a kid on its table) or screwed up under a beam (a hook's
# plate) is let into what holds it: faces lying exactly on each other may or may not be found crossing, and the room
# check (build_frigate's unmet) holds every copy to meeting what it stands on or hangs from
SEAT = 0.02 * IN
AFT_END_PX = 12.0      # the skin's inner faces end aft this far forward of the stern face (skin.Skin.inner_ends)
KNUCKLE_BAND_M = 0.005  # under the run's top the face's offset jumps up to 3 mm (skin.Hull.frame's one-sided
                        # normals there): within this of it, a height is the counter's foot carried down


def chamfered_rect(cxy, hx, hy, c):
    """a rectangle hx by hy half sizes about cxy, its corners chamfered c (as the gun deck's bitt posts')"""
    x_, y_ = cxy
    return np.array([[x_ + hx, y_ - hy + c], [x_ + hx, y_ + hy - c], [x_ + hx - c, y_ + hy], [x_ - hx + c, y_ + hy],
                     [x_ - hx, y_ + hy - c], [x_ - hx, y_ - hy + c], [x_ - hx + c, y_ - hy], [x_ + hx - c, y_ - hy]])


def mirrored(sp):
    """a deck.Part's mirror across the middle line (its own copy of the vertices, its faces turned to face out)"""
    out = Part()
    out.V = [V * [1.0, -1.0, 1.0] for V in sp.V]
    out.U = [U.copy() for U in sp.U]
    out.F = [tuple(f[::-1]) for f in sp.F]
    out.M = list(sp.M)
    out.n = sp.n
    return out



def strip_solid(mesh, rings, mat):
    """a solid lofted through rings that are each two chains over the same stations, out along one and back along the
    other (a chock's underside on the shelf and its top under the beam), each end filled as a strip of quads between
    its two chains: as one face (deck.solid) the end of a ring whose top runs straight is split into slivers along
    that run, which meet the sides at T-junctions"""
    rings = [np.asarray(r, float) for r in rings]
    d = rings[-1].mean(0) - rings[0].mean(0)
    if newell(rings[0]) @ d < 0:
        rings = [r[::-1] for r in rings]
    n = len(rings[0])
    if n % 2:
        raise SystemExit("berthdeck: strip_solid wants rings of two chains of the same count")
    F = [(j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
         for j in range(len(rings) - 1) for i in range(n)]
    strip = [(i, i + 1, n - 2 - i, n - 1 - i) for i in range(n // 2 - 1)]
    k1 = (len(rings) - 1) * n
    F += [tuple(k1 + v for v in f) for f in strip]               # the last end, facing on along the loft
    F += [f[::-1] for f in strip]                                 # the first, facing back
    mesh.add(np.concatenate(rings), F, mat)

class BerthDeck(GunDeck):
    # the parts that carry UVs (parts()): the deck's 'Planking' and 'Margin'
    UV_PARTS = {"BerthDeck": ("Planking", "Margin")}
    PLANKS = "BerthDeckPlanks"

    """The berth deck under the gun deck gd (gundeck.GunDeck, built in berth mode: its berth the card at path), its
    hammocks, hooks, mess tables, benches, kids and chests the stores kit's items (stores.Kit, kit()) placed as copies."""

    def __init__(self, gd, path=os.path.join(HERE, "berthdeck_1797.json")):
        self.gd = gd
        for k in ("sk", "rig", "dk", "SKM", "skin_parts", "face", "L", "pr", "k", "rows", "e1", "fc", "bp", "decor"):
            setattr(self, k, getattr(gd, k))
        self.hawse_x = None
        self.berth = None                                  # no berth deck under this one (GunDeck's berth): the orlop's
        self.cloth_t = 0.0
        self.c = json.load(open(path))
        self.drop = self.c["deck"]["top_below_gun_deck_in"] * IN
        if self.c["deck"]["top_below_gun_deck_in"] not in self.rig.fit["hoops"]["decks_below_gun_deck_in"]:
            raise SystemExit("berthdeck: the rig's masts would carry iron hoops at this deck's partners (spars_1795.json "
                             "fittings.hoops decks_below_gun_deck_in)")
        self.t_gun = gd.c["deck"]["thick_in"] * IN          # the gun deck's planks, over this deck's overhead
        self.parts_, self.frames, self.info, self.lights = {}, {}, {}, []
        self.ports = []                                    # no ports on this deck: it is under the waterline's swell
        self.copies_ = []                                 # linked copies of the stores kit's items (add_copy)
        self.copy_items = {}                              # their items by name
        self.deck_line = np.column_stack([gd.deck_line[:, 0], gd.deck_line[:, 1] - self.drop])
        self.KN = self.SKM.KNUCKLE                         # the stern's knuckle (the wing transom) in the skin's up-param
        self.zk = self.KN / self.k                         # its moulded height, m
        self.knuckle_lines()
        self.gun = self.edge_row()
        self.x_aft, self.x_fwd = float(self.gun[0, 0]), float(self.gun[-1, 0])

    # --- along the ship -------------------------------------------------------------------------------------------------
    def zg(self, x):
        """the berth deck's top at x (flat across): the gun deck's less top_below_gun_deck_in"""
        return np.interp(x, self.deck_line[:, 0], self.deck_line[:, 1])

    def zs(self, x):
        """the deck over this one (the gun deck): its top"""
        return self.gd.zg(x)

    def zsu(self, x):
        """the gun deck's planks' underside (its beams' tops)"""
        return self.gd.zg(x) - self.t_gun

    # --- the side's inner face (the ceiling) in the skin's own params ---------------------------------------------------
    # The face is the skin's GUN surface, 16 in in from the moulded surface along its normal. The skin gives it by an
    # along-param X (px: the moulded x is xm(X)) and an up-param Zp (px) on its lower piece (the run, closing in to the
    # post, up to the stern's knuckle KN) or its upper (the counter, from the knuckle up, ending aft on the stern face);
    # forward of JOINED the two are one curve. A point's own x and z are not its params': where the side leans (the run,
    # the bow) the face stands up to 0.4 m fore or aft of its moulded point, and up where the side flares.
    def xm(self, X):
        """the moulded x (m) of the along-param X (px)"""
        return (np.asarray(X, float) - self.L.mid_px) * self.sk.m.sx

    def at(self, X, Zp, up):
        """the face's points and the skin's normals at params X, Zp (arrays alike), on the upper piece where up"""
        X = np.atleast_1d(np.asarray(X, float))
        Zp = np.broadcast_to(np.atleast_1d(np.asarray(Zp, float)), X.shape).copy()
        U = np.broadcast_to(np.atleast_1d(np.asarray(up, bool)), X.shape).copy()
        P, N = self.sk.surf(X, Zp, U, 0, self.SKM.GUN)
        return np.asarray(P, float), np.asarray(N, float)

    def at_where(self, X, Zp, up):
        """at(), and which points the skin could frame: within about half a pixel of a piece's end at the knuckle its
        one-sided normals reach past the end's sections (a point there counts as off the face)"""
        X = np.atleast_1d(np.asarray(X, float))
        try:
            P, N = self.at(X, Zp, up)
            return P, N, np.ones(len(X), bool)
        except ValueError:
            Zp = np.broadcast_to(np.atleast_1d(np.asarray(Zp, float)), X.shape)
            U = np.broadcast_to(np.atleast_1d(np.asarray(up, bool)), X.shape)
            P, N, ok = np.zeros((len(X), 3)), np.zeros((len(X), 3)), np.zeros(len(X), bool)
            for i in range(len(X)):
                try:
                    p, n = self.at(X[i:i + 1], Zp[i:i + 1], U[i:i + 1])
                except ValueError:
                    continue
                P[i], N[i], ok[i] = p[0], n[0], True
            return P, N, ok

    def zp_for(self, X, zf, up):
        """the up-param at each along-param X on the piece up (a bool) whose face point stands at zf(its own x): a fixed
        point on the height (the face's z follows its up-param one for one but for the normal's tilt), held to the
        piece aft of JOINED (under the knuckle on the lower, over it on the upper)"""
        X = np.atleast_1d(np.asarray(X, float))
        k, KN = self.k, self.KN
        held = X < self.SKM.JOINED
        Zp = np.asarray(zf(self.xm(X)), float) * k
        for _ in range(100):
            P, _ = self.at(X, Zp, up)
            dz = np.asarray(zf(P[:, 0]), float) - P[:, 2]
            if np.abs(dz).max() < 1e-9:
                break
            Zp = Zp + dz * k
            Zp = np.where(held, np.maximum(Zp, KN) if up else np.minimum(Zp, KN), Zp)
        return np.where(np.abs(dz) < 1e-7, Zp, np.nan)     # nan: no such point (off the piece's end at that height)

    def on_piece(self, X, Zp, up, aft=0.0):
        """whether params X, Zp (arrays alike) lie on the piece up, between its ends at that height (aft px forward of
        its after end)"""
        m = self.sk.m
        U = np.broadcast_to(np.atleast_1d(np.asarray(up, bool)), np.shape(X))
        return (X >= m.x_lo(Zp, U) + aft) & (X <= m.x_hi(Zp))

    def row_end(self, X0, X1, zpf, up, e, aft=0.0):
        """bisect rows from X0 (on the face) toward X1 for where each leaves it: its half-breadth under e, or past the
        piece's end (aft px forward of it aft). zpf(X) gives the rows' up-params at X (arrays alike, one row each).
        The last X on each row"""
        lo, hi = np.array(X0, float), np.array(X1, float)

        def inside(X):
            Zp = zpf(X)
            ok = np.isfinite(Zp)
            ok[ok] = self.on_piece(X[ok], Zp[ok], up, aft)
            if ok.any():                                   # the skin has no sections past a piece's ends
                P, _, framed = self.at_where(X[ok], Zp[ok], up)
                ok[ok] = framed & (P[:, 1] >= e)
            return ok
        if not inside(lo).all():
            raise SystemExit("berthdeck: a row of the side's inner face does not start on it")
        for _ in range(44):
            mid = 0.5 * (lo + hi)
            ins = inside(mid)
            lo, hi = np.where(ins, mid, lo), np.where(ins, hi, mid)
        return lo

    def knuckle_lines(self):
        """the face's two lines at the stern's knuckle (the moulded knuckle carried in): the run's top (the lower
        piece's, from the post forward) and the counter's foot (the upper's, from its after end AFT_END_PX forward of
        the stern face, as the skin ends the gun deck's side, forward), each (n, 3) by x, to a metre forward of JOINED
        where they are one. Between them the wing transom's top: the shelf (ceiling)"""
        m, KN, sx = self.sk.m, self.KN, self.sk.m.sx
        xj = float(self.SKM.JOINED) + 1.0 / sx
        lo0 = float(m.x_lo(np.array([KN]), np.array([False]))[0])
        hi0 = float(m.x_lo(np.array([KN]), np.array([True]))[0]) + AFT_END_PX
        self.k_lo = self.at(np.arange(lo0, xj, 0.05 / sx), KN, False)[0]
        self.k_hi = self.at(np.arange(hi0, xj, 0.05 / sx), KN, True)[0]
        for nm, K in (("run's top", self.k_lo), ("counter's foot", self.k_hi)):
            if np.any(np.diff(K[:, 0]) <= 0):
                raise SystemExit(f"berthdeck: the {nm} at the stern's knuckle doubles back on the side's inner face")

    def knuckle(self, x):
        """at x (array): the run's top (y, z) and the counter's foot (y, z) on the face (forward of the lines the last
        of each, where the two are one; aft of the post the run's y 0)"""
        x = np.atleast_1d(np.asarray(x, float))
        lo, hi = self.k_lo, self.k_hi
        return (np.interp(x, lo[:, 0], lo[:, 1], left=0.0), np.interp(x, lo[:, 0], lo[:, 2]),
                np.interp(x, hi[:, 0], hi[:, 1]), np.interp(x, hi[:, 0], hi[:, 2]))

    def side_step(self, x):
        """how far the counter's face (over the stern's knuckle) stands out from the run's (under it) at x: the wing
        transom's top across between them (0 where the side is fair through the knuckle)"""
        x = np.atleast_1d(np.asarray(x, float))
        ylo, _, yhi, _ = self.knuckle(x)
        return np.where(x < self.k_hi[-1, 0], np.maximum(yhi - ylo, 0.0), 0.0)

    @staticmethod
    def _inboard(N, true):
        """the inboard normals from the skin's (as GunDeck.wall: level, or with true the face's own)"""
        n = np.column_stack([N[:, 0], N[:, 1], np.zeros(len(N))])
        n /= np.maximum(np.linalg.norm(n, axis=1), 1e-9)[:, None]
        inb = (n[:, 1] > 0)[:, None]
        if true:
            n = np.asarray(N, float) / np.linalg.norm(N, axis=1)[:, None]
        return np.where(inb, -n, n)

    def wall(self, x, z, true=False, up=None):
        """the side's inner face at x and z (as GunDeck.wall, but each point on its own x: wall_at)"""
        return self.wall_at(x, z, true, up)

    def wall_at(self, x, z, true=False, up=None, strict=True):
        """the side's inner face exactly at x and z (as GunDeck.wall_at): (points, inboard normals). Over the run's top
        at the stern's knuckle the counter's face, under it the run's; in the knuckle's band (over the run's top less
        KNUCKLE_BAND_M, under the counter's foot) the counter's face carried straight down to the shelf; up forces a
        piece (True the counter's). The skin's two params are solved together by Newton's method on a numerical Jacobian, each step
        halved while it leaves the point worse off and held to its piece: near the stern the face stands off the
        moulded surface along a normal leaning well aft and down, so each param moves both x and z (the gun deck's
        one-at-a-time loops wander there). strict: an x and z off the face is an error; else (points, normals, found)"""
        x = np.atleast_1d(np.asarray(x, float))
        z = np.broadcast_to(np.atleast_1d(np.asarray(z, float)), x.shape).copy()
        if up is None:
            _, zlo, _, zhi = self.knuckle(x)
            U = z > zlo - KNUCKLE_BAND_M
            zt = np.where(U, np.maximum(z, zhi), z)
        else:
            U, zt = np.full(len(x), bool(up)), z.copy()
        sx, k, KN, J = self.sk.m.sx, self.k, self.KN, float(self.SKM.JOINED)
        X, Zp = self.xpx(x).astype(float), zt * k
        hX = 0.002 / sx
        hZ = np.where(U, 1.0, -1.0) * 0.002 * k            # into the piece: up the counter, down the run
        Zp = np.where(X < J, np.where(U, np.maximum(Zp, KN), np.minimum(Zp, KN)), Zp)
        P, N = self.at(X, Zp, U)
        act = np.arange(len(x))
        for _ in range(40):
            rx, rz = x[act] - P[act, 0], zt[act] - P[act, 2]
            go = (np.abs(rx) > 1e-7) | (np.abs(rz) > 1e-7)
            act, rx, rz = act[go], rx[go], rz[go]
            if not len(act):
                break
            Pa, Ua = P[act], U[act]
            PX = self.at(X[act] + hX, Zp[act], Ua)[0]
            PZ = self.at(X[act], Zp[act] + hZ[act], Ua)[0]
            a, b = (PX[:, 0] - Pa[:, 0]) / hX, (PZ[:, 0] - Pa[:, 0]) / hZ[act]
            c, d = (PX[:, 2] - Pa[:, 2]) / hX, (PZ[:, 2] - Pa[:, 2]) / hZ[act]
            det = a * d - b * c
            with np.errstate(divide="ignore", invalid="ignore"):
                dX, dZ = (d * rx - b * rz) / det, (a * rz - c * rx) / det
            fb = ~(np.isfinite(dX) & np.isfinite(dZ))
            dX[fb], dZ[fb] = rx[fb] / sx, rz[fb] * k        # as the gun deck's loops where the Jacobian fails
            dX, dZ = np.clip(dX, -0.25 / sx, 0.25 / sx), np.clip(dZ, -0.25 * k, 0.25 * k)
            r0, lam = np.hypot(rx, rz), np.ones(len(act))
            for _h in range(14):
                Xn, Zn = X[act] + lam * dX, Zp[act] + lam * dZ
                Zn = np.where(Xn < J, np.where(Ua, np.maximum(Zn, KN), np.minimum(Zn, KN)), Zn)
                Pn, Nn = self.at(Xn, Zn, Ua)
                worse = np.hypot(x[act] - Pn[:, 0], zt[act] - Pn[:, 2]) > r0 * (1.0 - 1e-4 * lam)
                if not worse.any():
                    break
                lam[worse] *= 0.5
            better = ~worse
            take = act[better]
            X[take], Zp[take], P[take], N[take] = Xn[better], Zn[better], Pn[better], Nn[better]
            act = take                                      # a point no step betters is as near as the face comes
        err = np.hypot(x - P[:, 0], zt - P[:, 2])
        bad = np.nonzero(err >= 1e-5)[0]
        if len(bad):                                       # near a piece's end the Newton steps can stall
            for u in (False, True):
                b = bad[U[bad] == u]
                if not len(b):
                    continue
                Pf, Nf, ok = self.along_row(x[b], zt[b], u, X[b])
                P[b[ok]], N[b[ok]] = Pf[ok], Nf[ok]
            err = np.hypot(x - P[:, 0], zt - P[:, 2])
        found = err < 1e-5
        if strict and not found.all():
            i = int(np.argmax(err))
            raise SystemExit(f"berthdeck: the side's inner face at x {x[i]:.3f}, z {z[i]:.3f} was not found "
                             f"(nearest {err[i] * 1000:.2f} mm off)")
        P[:, 2] = z                                        # the knuckle's band: straight down the counter's foot
        n = self._inboard(N, true)
        return (P, n) if strict else (P, n, found)

    def along_row(self, xq, zq, up, X0):
        """wall_at's fallback for points its Newton steps could not settle (near a piece's end): on the row at each
        point's own height (zp_for), the along-param whose face point stands at its x, by bisection from a bracket
        about X0 (the face's x grows along the row). (points, normals, found)"""
        sx = self.sk.m.sx
        zq = np.asarray(zq, float)

        def fx(X):
            Zp = self.zp_for(X, lambda _x: zq, up)
            ok = np.isfinite(Zp)
            ok[ok] = self.on_piece(X[ok], Zp[ok], up)
            P = np.full((len(X), 3), np.nan)
            N = np.full((len(X), 3), np.nan)
            if ok.any():
                Pa, Na, fr = self.at_where(X[ok], Zp[ok], up)
                Pa[~fr], Na[~fr] = np.nan, np.nan
                P[ok], N[ok] = Pa, Na
            return P[:, 0] - xq, P, N
        lo, hi = np.array(X0, float), np.array(X0, float)
        have = np.zeros(len(lo), bool)
        for w in (0.002, 0.01, 0.05, 0.2):
            a, b = np.array(X0, float) - w / sx, np.array(X0, float) + w / sx
            fa, fb = fx(a)[0], fx(b)[0]
            new = ~have & (fa < 0) & (fb > 0)
            lo[new], hi[new], have[new] = a[new], b[new], True
            if have.all():
                break
        for _ in range(48):
            mid = 0.5 * (lo + hi)
            fm = fx(mid)[0]
            lo, hi = np.where(fm < 0, mid, lo), np.where(fm < 0, hi, mid)
        f, P, N = fx(0.5 * (lo + hi))
        return P, N, have & np.isfinite(f) & (np.abs(f) < 1e-6) & (np.abs(P[:, 2] - zq) < 1e-6)

    def deck_zp(self, X):
        """the up-param of the face at the deck's top along X"""
        return self.zp_for(X, self.zg, False)

    def ends(self, e):
        """where the side's inner face at the deck's top ends aft (the run closing in to the sternpost) and forward (the
        bow): at e out from the middle line, or at the face's own end if it comes first (the post's rabbet aft). The
        along-params (X aft, X forward)"""
        Xm = np.array([float(self.xpx(0.5 * (float(self.gd.x_aft) + float(self.gd.x_fwd))))])
        Xa = self.row_end(Xm, np.array([float(self.xpx(float(self.gd.x_aft) - 1.5))]), self.deck_zp, False, e)
        Xf = self.row_end(Xm, np.array([float(self.xpx(float(self.gd.x_fwd) + 1.5))]), self.deck_zp, False, e)
        return float(Xa[0]), float(Xf[0])

    def edge_row(self):
        """the deck's edge (starboard): the side's inner face at the deck's top, aft to fore, from where it stands
        end_half_breadth_m out from the middle line (or the face ends) aft to where it does forward, about 0.1 m apart:
        (n, 3). Also the berth deck's beams' ends (beams_end_half_breadth_m, berth_deck.json deck: the orlop slice's
        beams stop there)"""
        dc = self.c["deck"]
        Xa, Xf = self.ends(dc["end_half_breadth_m"])
        Ba, Bf = self.ends(dc["beams_end_half_breadth_m"])
        B = np.array([Ba, Bf])
        Pb = self.at(B, self.deck_zp(B), False)[0]
        self.beam_ends = (float(Pb[0, 0]), float(Pb[1, 0]))
        X = np.linspace(Xa, Xf, int(math.ceil((Xf - Xa) * self.sk.m.sx / 0.1)) + 1)
        R, N = self.at(X, self.deck_zp(X), False)
        self.gun_n = self._inboard(N, False)               # its level inboard normals (as wall gives)
        if np.any(np.diff(R[:, 0]) <= 0):
            raise SystemExit("berthdeck: the deck's edge doubles back on itself")
        if np.abs(R[:, 2] - self.zg(R[:, 0])).max() > 1e-6:
            raise SystemExit("berthdeck: the deck's edge is off the deck's top")
        return R

    def waterway_edge(self):
        """the flush waterway's inner edge (starboard), as GunDeck.waterway_edge, from the deck's edge row's own normals
        (its points are on the face already: re-solving them near the post, where the face ends, is needless)"""
        if getattr(self, "_ww", None) is None:
            fl = self.c["deck"]["waterway"]["flush_in"] * IN
            P, n = self.gun, self.gun_n
            E = (P + n * np.minimum(fl, np.maximum(P[:, 1] - 0.02, 0.0))[:, None])[:, :2]
            E = E[np.argsort(E[:, 0])]
            self._ww = (E, np.gradient(E[:, 1], E[:, 0]))
        return self._ww

    # --- the layout -----------------------------------------------------------------------------------------------------
    def layout(self):
        """the openings through this deck (the gun deck's that go on down, and its own), the fittings that come down
        through the gun deck, and the rooms' lines"""
        c, gd = self.c, self.gd
        op = c["openings"]
        it = self.items = {}
        t, high = op["coaming_thick_in"] * IN, op["coaming_high_in"] * IN
        for o in op["items"]:
            if "over" in o:
                v = gd.items[o["over"]]
                x, y, L, W = v["x"], 0.0, v["L"], v["W"]
                if "inside_x_m" in o:
                    a, b = o["inside_x_m"]
                    x, L = 0.5 * (a + b), b - a
            else:
                x, y = o["x_m"], o["y_m"]
                L, W = o["inside_m"]
            it[o["name"]] = dict(x=x, y=y, L=L, W=W, t=t, high=high, kind=o["kind"], Lo=L + 2 * t, Wo=W + 2 * t,
                                 goes=o.get("goes"))
        self.x_capstan, self.x_chain, self.x_brake = gd.x_capstan, gd.x_chain, gd.x_brake
        self.info["layout"] = {k: {"x_m": round(v["x"], 4), "y_m": round(v["y"], 4),
                                   "inside_m": [round(v["L"], 4), round(v["W"], 4)], "kind": v["kind"]}
                               for k, v in it.items()}
        self.info["layout"]["ends_x_m"] = [round(self.x_aft, 3), round(self.x_fwd, 3)]
        return self

    # --- the deck itself ------------------------------------------------------------------------------------------------
    def mast_hole(self, name):
        """the mast's hole in the planks: its centre at the deck's top, the hole's outline (n, 2) and the mast's radius
        and axis there"""
        g = self.c["deck"]["mast_hole_gap_in"] * IN
        xt = self.mast_x(name)
        for _ in range(4):
            pt, R, u = self.mast_at(name, float(self.zg(xt)))
            xt = pt[0]
        a, b = (R + g) / u[2], R + g
        th = np.linspace(0, 2 * math.pi, 32, endpoint=False)
        return pt, np.stack([a * np.cos(th), b * np.sin(th)], 1) + pt[:2], R, u

    def pump_tubes(self):
        """the pumps' tubes down through this deck: [(name, (x, y), kind, half-size)]: the chain pumps' four square
        pipes (chain_pipes_at_in about the case's middle, both sides) and the brake pumps' two round trees (the gun
        deck's, 12 in either side of the middle line)"""
        th = self.c["through"]
        out = []
        h = th["chain_pipes_in"] / 2 * IN
        for k, (dx, dy) in enumerate(th["chain_pipes_at_in"]):
            for sy in (1.0, -1.0):
                out.append(("ChainPipe_%d%s" % (k, "S" if sy > 0 else "P"), (self.x_chain + dx * IN, sy * dy * IN),
                            "square", h))
        bp = self.gd.c["pumps"]["brake"]
        yb = bp["tube_off_in"] * IN if "tube_off_in" in bp else 12.0 * IN
        for sy in (1.0, -1.0):
            out.append(("BrakeTree_" + ("S" if sy > 0 else "P"), (self.x_brake, sy * yb), "round",
                        th["brake_tree_in"] / 2 * IN))
        return out

    def scuttles(self):
        """the cables' scuttles: (x, y half-breadth) straight under the gun deck's"""
        return tuple(self.gd.c["bow"]["scuttle_at_m"])

    def holes(self):
        """the openings through the deck: [(name, outline (n, 2) counter-clockwise, walls)]: walls True where the deck's
        edge shows (the masts, the pumps' tubes, the cable scuttles), False where a coaming stands in it"""
        out = []
        for name in ("fore", "main", "mizzen"):
            out.append(("Mast_" + name, self.mast_hole(name)[1], True))
        gp = 0.25 * IN
        for name, (x, y), kind, h in self.pump_tubes():
            if kind == "square":
                out.append((name, rect2(x, y, 2 * (h + gp), 2 * (h + gp)), True))
            else:
                out.append((name, circle(h + gp, 20) + [x, y], True))
        xs, ys = self.scuttles()
        r = self.c["through"]["scuttle_in"] / 2 * IN
        for sy in (1.0, -1.0):
            out.append(("CableScuttle_" + ("S" if sy > 0 else "P"), circle(r, 24) + [xs, sy * ys], True))
        for k, v in self.items.items():
            out.append((k, densify(rect2(v["x"], v["y"], v["Lo"], v["Wo"]), 0.2), False))
        return out

    def outline(self):
        """the deck's edge in plan (counter-clockwise): the side along both sides, closing in at the ends"""
        G = self.gun
        stb = G[:, :2]
        port = G[::-1, :2] * [1.0, -1.0]
        fwd = densify(np.array([stb[-1], port[0]]), 0.05, closed=False)[1:-1]
        aft = densify(np.array([port[-1], stb[0]]), 0.05, closed=False)[1:-1]
        return np.concatenate([stb, fwd, port, aft])

    def surface(self, part):
        """the deck's top (planked: UVs 'Planking' and 'Margin'), its underside, and the walls of its holes that show"""
        th = self.c["deck"]["thick_in"] * IN
        holes = self.holes()
        outline = self.outline()
        P2, T = cdt(outline, [h[1] for h in holes], self.c["deck"].get("mesh_step_m", 0.3))
        Z = self.zg(P2[:, 0])
        part.add(np.column_stack([P2, Z]), [tuple(t) for t in T], self.PLANKS,
                 uv=np.column_stack([P2, self.margin_uv(P2)]))
        a2 = (P2[T[:, 1], 0] - P2[T[:, 0], 0]) * (P2[T[:, 2], 1] - P2[T[:, 0], 1]) - \
             (P2[T[:, 1], 1] - P2[T[:, 0], 1]) * (P2[T[:, 2], 0] - P2[T[:, 0], 0])
        self.info["deck"] = {"top_triangles": len(T), "area_m2": round(float(0.5 * np.abs(a2).sum()), 1),
                             "x_m": [round(self.x_aft, 3), round(self.x_fwd, 3)]}
        part.add(np.column_stack([P2, Z - th]), [tuple(t[::-1]) for t in T], "Deck")
        for name, h, walls in holes:
            if not walls:
                continue
            A = np.column_stack([h, self.zg(h[:, 0])])
            B = A - [0.0, 0.0, th]
            A, B = np.concatenate([A, A[:1]]), np.concatenate([B, B[:1]])
            n = len(A)
            V = np.concatenate([A, B])
            F = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
            c2 = h.mean(0)
            want = np.array([c2[0] - A[0, 0], c2[1] - A[0, 1], 0.0])
            nrm = np.cross(V[F[0][1]] - V[F[0][0]], V[F[0][3]] - V[F[0][0]])
            if nrm @ want < 0:
                F = [f[::-1] for f in F]
            part.add(V, F, "Deck")

    def waterways(self, part):
        """the waterway's hollow along each side at the deck's edge, from end to end while the side stands 0.4 m out
        (the gun deck's profile): no spirketting, this deck's ceiling comes down to the cove (ceiling)"""
        prof = np.array(self.c["deck"]["waterway"]["profile_in"], float) * IN
        G = self.gun
        on = np.nonzero(G[:, 1] >= 0.4)[0]
        xa, xf = float(G[on.min(), 0]), float(G[on.max(), 0])
        xs = G[:, 0]
        xs = np.unique(np.concatenate([xs[(xs > xa + 0.02) & (xs < xf - 0.02)][::2], [xa, xf]]))
        P0, n = self.wall_over_deck(xs, 0.0)
        h0 = prof[0, 1]
        P1, _ = self.wall_over_deck(xs, h0)
        let = 0.25 * IN
        rings = []
        for k in range(len(xs)):
            ring = [P0[k] - n[k] * 0.25 * IN - EZ * let, P1[k] - n[k] * 0.25 * IN]
            for w, h in prof:
                ring.append(P0[k] + (P1[k] - P0[k]) * (h / h0) + n[k] * w)
            ring.append(P0[k] + n[k] * prof[-1, 0] - EZ * let)
            ring = np.array(ring)
            ring[:, 2] += self.zg(ring[:, 0]) - self.zg(np.full(len(ring), P0[k, 0]))
            rings.append(ring)
        for sgn in (1.0, -1.0):
            solid(part, [r * [1.0, sgn, 1.0] for r in rings], "Oak")
        self.ww_x = (xa, xf)
        self.ww_rings = np.array(rings)                   # starboard, for scribing the partitions to (waterway_cut)
        self.info["waterways"] = {"x_m": [round(xa, 3), round(xf, 3)]}

    # --- the gun deck's framing overhead --------------------------------------------------------------------------------
    def stations(self):
        """the gun deck's beam stations over this deck, which are the berth deck's own under it (berth_deck.json beams
        and ledges: the spar deck's and gun deck's stations carried down, a beam every other one and a ledge between,
        the waist's stations whole beams here, so the stanchions on each deck stand over one another), between where
        the side at this deck's top stands beams_end_half_breadth_m out: [(x, kind)] aft to fore"""
        bp, e1, fc = self.bp, self.e1, self.fc
        st = set()
        for k in range(-80, 81):
            x = e1 + k * bp
            if x <= fc + 1e-6:
                st.add((round(x, 4), k % 2))
        for k in range(1, 60):
            st.add((round(fc + k * bp, 4), k % 2))
        xs = [x for x, _ in st]
        if len(set(xs)) != len(xs):
            raise SystemExit("berthdeck: a station is both a beam and a ledge")
        oh = self.c["overhead"]
        bs, ls = oh["berth_beam_sided_in"] * IN, oh["ledge_in"][0] * IN
        xa, xf = self.beam_ends
        out = []
        for x, odd in sorted(st):
            w = ls if odd else bs
            if x - w / 2 < xa or x + w / 2 > xf:
                continue
            out.append((x, "ledge" if odd else "beam"))
        return out

    def openings_above(self):
        """what comes through the gun deck over this deck about its middle line, as plan boxes [x0, x1, y half-width,
        name] with the overhead's margin: the gun deck's hatchways, skylight and scuttle (their coamings' outsides), the
        capstan's spindle (the gun deck's hole for it), the masts, and the pumps' tubes (each pump's together)"""
        gd = self.gd
        mg = self.c["overhead"]["opening_margin_in"] * IN
        out = []
        for k, v in gd.items.items():
            out.append([v["x"] - v["Lo"] / 2 - mg, v["x"] + v["Lo"] / 2 + mg, v["Wo"] / 2 + mg, k])
        rb = (gd.c["capstan"]["barrel_diam_in"][1] / 2 + gd.c["deck"]["mast_hole_gap_in"]) * IN
        out.append([self.x_capstan - rb - mg, self.x_capstan + rb + mg, rb + mg, "Capstan"])
        g = gd.c["deck"]["mast_hole_gap_in"] * IN
        bm = self.c["overhead"]["beam_in"][1] * IN
        for name in ("fore", "main", "mizzen"):
            xm = self.mast_x(name)
            xs = []
            for z in (float(self.zsu(xm)) - bm, float(self.zs(xm))):
                p, R, u = self.mast_at(name, z)
                xs += [p[0] - R / u[2] - g, p[0] + R / u[2] + g]
                rr = R + g
            out.append([min(xs) - mg, max(xs) + mg, rr + mg, "Mast_" + name])
        tubes = self.pump_tubes()
        for nm, pre in (("ChainPumps", "ChainPipe"), ("BrakePumps", "BrakeTree")):
            T = [(x, y, h) for n_, (x, y), _, h in tubes if n_.startswith(pre)]
            out.append([min(x - h for x, y, h in T) - mg, max(x + h for x, y, h in T) + mg,
                        max(abs(y) + h for x, y, h in T) + mg, nm])
        return sorted(out)

    def pierce_holes(self):
        """the holes through the gun deck off the middle line that a ledge under them is cut round, its pieces butting
        on them (the riding bitts' posts, the cable scuttles with their collars): [(x, y, half-length, half-width,
        name)]"""
        gd = self.gd
        bt = gd.c["bitts"]
        p = (bt["post_in"] / 2 + 0.25) * IN
        out = [(bt["x_m"], sy * bt["y_in"] * IN, p, p, "BittPost_" + sd) for sy, sd in ((1.0, "S"), (-1.0, "P"))]
        bw = gd.c["bow"]
        xs, ys = bw["scuttle_at_m"]
        r = (bw["scuttle_in"] / 2 + bw["collar_in"][0] + 0.25) * IN
        out += [(xs, sy * ys, r, r, "CableScuttle_" + sd) for sy, sd in ((1.0, "S"), (-1.0, "P"))]
        return out

    def waist_members(self):
        """no waist over this deck: the gun deck runs whole over it"""
        return []

    def lodging_from_x(self):
        """the lodging knees stand at the beams forward of the wardroom's fore bulkhead"""
        w = self.c["wardroom"]
        return w["fore_bulkhead_x_m"] + w["bulkhead_in"] / 2 * IN

    def stanchions_from_x(self):
        """the stanchions stand under the beams forward of the wardroom's after bulkhead"""
        return self.c["wardroom"]["after_bulkhead_x_m"] + 0.3

    def overhead(self, part):
        """the gun deck's beams and ledges over this deck (as GunDeck.overhead does the spar deck's over the gun deck,
        with no waist): each member cut round the openings above (openings_above) onto carlings either side, head ledges
        across at the openings' ends, and a ledge that meets a hole off the middle line (pierce_holes) cut round it"""
        oh = self.c["overhead"]
        bs, bm = (v * IN for v in oh["beam_in"])
        ls, lm = (v * IN for v in oh["ledge_in"])
        cs_, cm = (v * IN for v in oh["carling_in"])
        boxes = self.openings_above()
        members = []
        for x, kind in self.stations():
            s, m = (bs, bm) if kind == "beam" else (ls, lm)
            members.append([x, s, m, kind])

        def crosses(mb, bx):
            return mb[0] + mb[1] / 2 > bx[0] and mb[0] - mb[1] / 2 < bx[1]
        cut, groups = {}, []
        for bx in boxes:
            hit = [i for i, mb in enumerate(members) if crosses(mb, bx)]
            if not hit:
                continue
            aft = [i for i, mb in enumerate(members) if mb[0] + mb[1] / 2 <= bx[0] and i not in hit]
            fwd = [i for i, mb in enumerate(members) if mb[0] - mb[1] / 2 >= bx[1] and i not in hit]
            if not aft or not fwd:
                raise SystemExit(f"berthdeck: no whole member {'aft' if not aft else 'forward'} of the opening {bx[3]}")
            groups.append({"boxes": [bx], "hit": set(hit), "Y": bx[2] + cs_,
                           "aft": max(aft, key=lambda i: members[i][0]), "fwd": min(fwd, key=lambda i: members[i][0])})
        merged = []
        for g in sorted(groups, key=lambda g: members[g["aft"]][0]):
            if merged and members[g["aft"]][0] < members[merged[-1]["fwd"]][0] - 1e-6:
                h = merged[-1]
                h["boxes"] += g["boxes"]
                h["hit"] |= g["hit"]
                h["Y"] = max(h["Y"], g["Y"])
                if members[g["fwd"]][0] > members[h["fwd"]][0]:
                    h["fwd"] = g["fwd"]
            else:
                merged.append(g)
        for g in merged:
            for i in g["hit"]:
                if members[g["aft"]][0] < members[i][0] < members[g["fwd"]][0]:
                    cut[i] = max(cut.get(i, 0.0), g["Y"])
        self.overhead_info = {"members": [], "carlings": [], "head_ledges": [], "pierced": []}
        pierce = self.pierce_holes()
        for i, (x, s, m, kind) in enumerate(members):
            x0, x1 = x - s / 2, x + s / 2
            zt0, zt1 = float(self.zsu(x0)), float(self.zsu(x1))
            ye = self.end_y(x0, x1, min(zt0, zt1) - m, max(zt0, zt1))
            spans = [(cut[i], ye), (-ye, -cut[i])] if i in cut else [(-ye, ye)]
            for hx, hy, hl, hw, nm in pierce:
                if not (x1 > hx - hl and x0 < hx + hl):
                    continue
                if kind != "ledge":
                    raise SystemExit(f"berthdeck: the beam at x {x:.3f} meets {nm} coming down through the gun deck")
                lo, hi = hy - hw, hy + hw
                new = []
                for a, b in spans:
                    if hi <= a or lo >= b:
                        new.append((a, b))
                        continue
                    if lo - a > 0.05:
                        new.append((a, lo))
                    if b - hi > 0.05:
                        new.append((hi, b))
                spans = new
                self.overhead_info["pierced"].append({"x_m": round(x, 4), "round": nm})
            ch = oh["chamfer_in"]["beam" if kind == "beam" else "ledge"] * IN
            for ya, yb in spans:
                self.member(part, x0, x1, zt0, zt1, m, ya, yb, ch, ye)
            self.overhead_info["members"].append({"x_m": round(x, 4), "kind": kind,
                                                  "spans_y_m": [[round(a, 3), round(b, 3)] for a, b in spans]})
        self.members = members
        self.cut = cut
        for g in merged:
            Y = g["Y"]
            xa = members[g["aft"]][0] + members[g["aft"]][1] / 2
            xf = members[g["fwd"]][0] - members[g["fwd"]][1] / 2
            runs, cur = [], xa
            for j, (x, s, m, kind) in sorted(enumerate(members), key=lambda t: t[1][0]):
                if xa < x < xf and j not in g["hit"]:
                    runs.append((cur, x - s / 2))
                    cur = x + s / 2
            runs.append((cur, xf))
            for sy in (1.0, -1.0):
                yc = sy * (Y - cs_ / 2)
                for a, b in runs:
                    if b - a < 0.02:
                        continue
                    self.carling(part, yc, a, b, max(2, int(math.ceil((b - a) / 0.5)) + 1))
                    self.overhead_info["carlings"].append({"y_m": round(yc, 3), "x_m": [round(a, 3), round(b, 3)]})
            for bx in g["boxes"]:
                for xe, sgn in ((bx[0], -1.0), (bx[1], 1.0)):
                    xc = xe + sgn * ls / 2
                    if any(abs(x - xc) < (s + ls) / 2 for x, s, m, kind in members):
                        continue
                    if any(b2 is not bx and b2[0] - ls / 2 < xc < b2[1] + ls / 2 for b2 in g["boxes"]):
                        continue
                    if not (xa + ls / 2 <= xc <= xf - ls / 2):
                        continue
                    z0 = float(self.zsu(xc))
                    vbox(part, [xc - ls / 2, -(Y - cs_), z0 - lm], [xc + ls / 2, Y - cs_, z0], "Oak")
                    self.overhead_info["head_ledges"].append({"x_m": round(float(xc), 4), "for": bx[3],
                                                              "y_m": round(Y - cs_, 4)})
        self.groups = merged
        self.info["overhead"] = {"members": len(members), "cut": {round(members[i][0], 3): round(y, 3)
                                                                  for i, y in sorted(cut.items())},
                                 "groups": [[b[3] for b in g["boxes"]] for g in merged],
                                 "pierced": self.overhead_info["pierced"]}

    def clamps(self, part):
        """the clamp along each side under the beams' ends (overhead clamp_in); aft, where the side steps out over the
        stern's knuckle (more than knee least_side_step_m), it stands on the shelf (the wing transom's top) a tenth of an
        inch over the counter's foot, as deep as the beams leave it there, and it stops where that is under an inch:
        aft of it the beams' ends lie on the wing transom itself"""
        oh = self.c["overhead"]
        dep, th = (v * IN for v in oh["clamp_in"])
        least = oh["knee"]["least_side_step_m"]
        x0 = min(m[0] - m[1] / 2 for m in self.members) - 0.05
        x1 = max(m[0] + m[1] / 2 for m in self.members) + 0.05
        X = np.unique(np.concatenate([np.arange(x0, x1, 0.25), [x1]]))
        zt = np.array([self.beam_bottom(x) for x in X])
        zb = zt - dep
        step = self.side_step(X)
        zhi = self.knuckle(X)[3]
        lift = (step > least) & (zb < zhi + 0.1 * IN)
        zb[lift] = zhi[lift] + 0.1 * IN
        short = zt - zb < 1.0 * IN
        x_stop = None
        if short.any():
            last = int(np.nonzero(short)[0].max())
            if not lift[:last + 1].all() or last + 1 >= len(X):
                raise SystemExit(f"berthdeck: the clamp is less than an inch deep at x {X[last]:.2f}, off the stern's "
                                 "step")
            x_stop = float(X[last + 1])
            X, zt, zb, lift = X[last + 1:], zt[last + 1:], zb[last + 1:], lift[last + 1:]
        Pt, nt = self.wall_at(X, zt)
        Pb, nb = self.wall_at(X, zb)
        rings = [np.array([Pb[i] - nb[i] * 0.3 * IN, Pb[i] + nb[i] * th, Pt[i] + nt[i] * th, Pt[i] - nt[i] * 0.3 * IN])
                 for i in range(len(X))]
        for sgn in (1.0, -1.0):
            solid(part, [r * [1.0, sgn, 1.0] for r in rings], "Oak")
        self.clamp = (X, zb, zt)
        self.info["clamp"] = {"x_m": [round(float(X[0]), 3), round(float(X[-1]), 3)],
                              "least_deep_in": round(float((zt - zb).min() / IN), 2),
                              "on_the_shelf_x_m": [round(float(X[lift].min()), 3), round(float(X[lift].max()), 3)]
                              if lift.any() else None,
                              "beams_on_the_wing_transom_aft_of_x_m": None if x_stop is None else round(x_stop, 3)}

    def knees(self, part):
        """a hanging knee under each beam end (the whole beams and the half beams, both sides): its upright arm down the
        clamp and the ceiling, its other arm along the beam's underside (as the gun deck's). None where the side steps
        out over the stern's knuckle within the knee's arm (its upright arm would have no side to lie on)"""
        oh = self.c["overhead"]
        kn = oh["knee"]
        sd = kn["sided_in"] * IN
        arm = kn["arm_in"] * IN
        thr = kn["throat_in"] * IN
        dep, th = (v * IN for v in oh["clamp_in"])
        Xc, Zb, Zt = self.clamp
        fay = 0.002                                      # the arm's top let 2 mm up into the beam (as the gun deck's)
        placed, stepped = [], []
        self.knee_heads = {}                              # beam x -> (the knee's head's y under the beam, its foot's z)
        self.knee_inner = {}                              # beam x -> [the inner face (y, z) at each side face]
        for x, s, m, kind in self.members:
            if kind != "beam":
                continue
            zbb = self.beam_bottom(x)
            foot = zbb - arm
            if foot < float(self.zg(x)) + 0.5:
                continue
            zhi = float(self.knuckle(np.array([x]))[3][0])
            if x - sd / 2 < Xc[0] or (foot < zhi < zbb and float(self.side_step(np.array([x - sd / 2, x + sd / 2])).max())
                                       > kn["least_side_step_m"]):
                stepped.append(round(x, 3))
                continue

            def profile(xf):
                # fayed to the clamp (its inner face and its bottom, across at xf) and the side under it, its arm along
                # the beam's underside at xf: the beam rises with the sheer along its siding (a level arm left a wedge
                # open under one face, half an inch at the bow), so the whole knee is that much higher there
                zbf = self.beam_bottom(xf)
                ftf = zbf - arm
                zcf = float(np.interp(xf, Xc, Zb))
                zz = np.linspace(ftf, zcf, 6)
                yw = self.wall_at(np.full(len(zz), xf), zz)[0][:, 1]
                Ct, Cb = self.clamp_corner(xf, True), self.clamp_corner(xf, False)
                y_in = min(Ct[1], Cb[1])
                y_end = y_in - (arm - th)
                toe = 3.0 * IN
                outer = [(Ct[1], zbf + fay), (Cb[1], Cb[2])] + [(yw[j] + 0.002, zz[j]) for j in range(len(zz) - 1, -1, -1)]
                foot_in = (yw[0] - toe, ftf)
                head_in = (y_end, zbf - toe)
                corner = np.array([y_in - thr, zbf - thr])
                curve = [tuple((1 - t) ** 2 * np.array(foot_in) + 2 * (1 - t) * t * corner + t ** 2 * np.array(head_in))
                         for t in np.linspace(0.0, 1.0, 9)[1:-1]]
                return np.array(outer + [foot_in] + curve + [head_in, (y_end, zbf + fay)])

            P0, P1 = profile(x - sd / 2), profile(x + sd / 2)
            for sgn in (1.0, -1.0):
                prism2(part, P0 * [sgn, 1.0], P1 * [sgn, 1.0], x - sd / 2, x + sd / 2, "Oak")
            placed.append(round(x, 3))
            self.knee_heads[round(x, 4)] = (float(min(P0[-1][0], P1[-1][0])), foot)
            # its inner face from the foot round the throat to the head (y falling, z rising) at each side face: the
            # profile's points after its outer edge's eight (two on the clamp, six down the side)
            self.knee_inner[round(x, 4)] = [P[8:-1] for P in (P0, P1)]
        self.info["knees_x_m"] = sorted(placed)
        self.info["knees_none_over_the_knuckle_x_m"] = stepped

    def clamp_corner(self, xf, top):
        """the clamp's inner corner (starboard), at its top (under the beams) or its bottom, in the plane across the ship
        at xf: the clamp's section is square to the side, so where the side runs aslant in plan (the bow) the corner
        across at xf is off the side at another x, found by moving along the side till the corner comes to xf"""
        Xc, Zb, Zt = self.clamp
        th = self.c["overhead"]["clamp_in"][1] * IN
        xs, C = xf, None
        for _ in range(8):
            z = float(np.interp(xs, Xc, Zt if top else Zb))
            P, n = self.wall_at(np.array([xs]), np.array([z]))
            C = P[0] + n[0] * th
            if abs(C[0] - xf) < 1e-5:
                break
            xs += xf - C[0]
        return C

    # --- the side between the decks -------------------------------------------------------------------------------------
    def ceiling(self, part):
        """the side's inside between the decks (the ceiling over the frames, painted), both sides, laid in the skin's
        own params: under the stern's knuckle the run's face from just under this deck's top (the waterway covers the
        joint) up to the run's top, closing in to the middle line at the post and the stem; over it the counter's face
        up into the gun deck's planks (side top_into_gun_planks_in), ending aft AFT_END_PX forward of the stern face (as
        the skin ends the gun deck's side) and forward at the stem. Where the counter stands out from the run (aft of
        JOINED) the wing transom's top lies across between them (the shelf), and aft the after wall stands straight
        across between the counter's ends, from the shelf's after edge to the gun deck (as the gun deck's after wall)"""
        sc = self.c["side"]
        KN, sx = self.KN, self.sk.m.sx
        z0f = lambda x: self.zg(x) - 0.5 * IN                                   # noqa: E731
        z1f = lambda x: self.zsu(x) + sc["top_into_gun_planks_in"] * IN        # noqa: E731
        Xm = float(self.xpx(0.5 * (self.x_aft + self.x_fwd)))
        Xa_lim, Xf_lim = float(self.xpx(self.x_aft - 2.0)), float(self.xpx(self.x_fwd + 2.0))

        def span(zf, up):
            """the ends (params) of the row at zf on the piece up"""
            zpf = lambda X: self.zp_for(X, zf, up)                      # noqa: E731
            a = self.row_end(np.array([Xm]), np.array([Xa_lim]), zpf, up, 0.0, AFT_END_PX if up else 0.0)[0]
            return float(a), float(self.row_end(np.array([Xm]), np.array([Xf_lim]), zpf, up, 0.0)[0])
        # the run's rows reach further aft and forward than its foot (the post and stem rake out as they rise) and the
        # counter's no further than its top: past the foot's (top's) ends a row keeps the up-param of its end there
        b_ends, t_ends = span(z0f, False), span(z1f, True)

        def lower(X, T):
            Zb = self.zp_for(np.clip(X, *b_ends), z0f, False)
            return Zb + T * (KN - Zb)

        def upper(X, T):
            Zt = self.zp_for(np.clip(X, *t_ends), z1f, True)
            return KN + T * (Zt - KN)
        # rows rows_step_m apart where each face is tallest (sampled along its middle)
        Xs = np.linspace(float(self.xpx(self.x_aft + 0.6)), float(self.xpx(self.x_fwd - 0.6)), 80)
        tall_lo = self.at(Xs, KN, False)[0][:, 2] - z0f(self.at(Xs, KN, False)[0][:, 0])
        tall_hi = z1f(self.at(Xs, KN, True)[0][:, 0]) - self.at(Xs, KN, True)[0][:, 2]
        faces, snaps = {}, []
        for nm, up, fn, tall in (("run", False, lower, tall_lo), ("counter", True, upper, tall_hi)):
            n = max(2, int(math.ceil(float(tall.max()) / sc["rows_step_m"])) + 1)
            T = np.linspace(0.0, 1.0, n)
            zpf = lambda X, T=T, fn=fn: fn(X, T)                        # noqa: E731
            Xa = self.row_end(np.full(n, Xm), np.full(n, Xa_lim), zpf, up, 0.0, AFT_END_PX if up else 0.0)
            Xf = self.row_end(np.full(n, Xm), np.full(n, Xf_lim), zpf, up, 0.0)
            nu = int(math.ceil(float((Xf - Xa).max()) * sx / sc["along_step_m"])) + 1
            u = np.linspace(0.0, 1.0, nu)
            XX = Xa[:, None] + (Xf - Xa)[:, None] * u[None, :]
            ZZ = fn(XX.ravel(), np.repeat(T, nu))
            if not np.isfinite(ZZ).all():
                raise SystemExit(f"berthdeck: the {nm}'s face has a row off the skin")
            P = self.at(XX.ravel(), ZZ, up)[0].reshape(n, nu, 3)
            # each row's ends on the middle line: the post's and the stem's (the counter's after end stays on its side)
            for j, end in [(j, -1) for j in range(n)] + ([] if up else [(j, 0) for j in range(n)]):
                snaps.append((abs(float(P[j, end, 1])), nm, j, "fore" if end else "aft",
                              [round(float(c), 3) for c in P[j, end]]))
                P[j, end, 1] = 0.0
            faces[nm] = P
        worst = max(snaps, key=lambda t: t[0])
        if worst[0] > 0.08:
            raise SystemExit(f"berthdeck: a ceiling row ends {worst[0]:.3f} m off the middle line ({worst[1:]})")
        run, ctr = faces["run"], faces["counter"]
        # the shelf: between the run's top and the counter's foot, from the after wall forward to where they meet
        top, foot = run[-1], ctr[0]
        gap = np.interp(top[:, 0], foot[:, 0], foot[:, 1]) - top[:, 1]
        least = sc["shelf_least_step_m"] * 0.1
        meet = np.nonzero((gap < least) & (top[:, 0] > foot[0, 0]))[0]
        x_s = float(top[meet[0], 0]) if len(meet) else float(top[-1, 0])
        I, O = top[top[:, 0] <= x_s], foot[foot[:, 0] <= x_s]
        outline = np.concatenate([I, O[::-1]])
        from scipy.interpolate import LinearNDInterpolator
        P2, Tri = cdt(outline[:, :2], [], 0.3)
        self.shelf = (I, O, x_s, LinearNDInterpolator(outline[:, :2], outline[:, 2]))
        zi = self.shelf[3](P2)
        if not np.isfinite(zi).all():
            raise SystemExit("berthdeck: the shelf's heights do not cover it")
        shelf = np.column_stack([P2, zi])
        # the after wall: straight across between the counter's ends (each of its rows), its foot the shelf's after edge
        E = ctr[:, 0]
        nv = max(2, int(math.ceil(float(E[:, 1].max()) / sc["along_step_m"])) + 1)
        v = np.linspace(0.0, 1.0, nv)[:, None]
        wall = np.stack([I[0] + v[:, 0, None] * (O[0] - I[0])] +
                        [np.column_stack([np.full(nv, e[0]), v[:, 0] * e[1], np.full(nv, e[2])]) for e in E[1:]])

        def grid(G):
            """quads over a (rows, columns, 3) grid"""
            r, c = G.shape[:2]
            return G.reshape(-1, 3), [(i * c + j, i * c + j + 1, (i + 1) * c + j + 1, (i + 1) * c + j)
                                      for i in range(r - 1) for j in range(c - 1)]

        def facing(V, F, want):
            """F turned so that, all told, its faces look along want"""
            tot = sum(float(newell(V[list(f)]) @ want) for f in F)
            return F if tot > 0 else [t[::-1] for t in F]
        for sgn in (1.0, -1.0):
            for G, want in ((run, [0.0, -sgn, 0.0]), (ctr, [0.0, -sgn, 0.0]), (wall, [1.0, 0.0, 0.0])):
                V, F = grid(G * [1.0, sgn, 1.0])
                part.add(V, facing(V, F, np.array(want)), "Interior")
            V = shelf * [1.0, sgn, 1.0]
            part.add(V, facing(V, [tuple(t) for t in Tri], EZ), "Interior")
        st = self.side_step(top[:, 0])
        self.ceiling_rows = {"run": run, "counter": ctr}
        self.info["ceiling"] = {"run_x_m": [round(float(run[:, 0, 0].min()), 3), round(float(run[:, -1, 0].max()), 3)],
                                "counter_x_m": [round(float(ctr[:, 0, 0].min()), 3),
                                                round(float(ctr[:, -1, 0].max()), 3)],
                                "rows": [run.shape[0], ctr.shape[0]], "columns": [run.shape[1], ctr.shape[1]],
                                "ends_moved_to_the_middle_line_most_m": round(worst[0], 4),
                                "ends_moved_most_at": list(worst[1:]),
                                "shelf_x_m": [round(float(I[0, 0]), 3), round(x_s, 3)],
                                "shelf_z_m": [round(float(outline[:, 2].min()), 3), round(float(outline[:, 2].max()), 3)],
                                "after_wall_x_m": [round(float(E[:, 0].max()), 3), round(float(E[:, 0].min()), 3)],
                                "after_wall_z_m": [round(float(I[0, 2]), 3), round(float(E[-1, 2]), 3)],
                                "most_step_m": round(float(st.max()), 3)}

    def chocks(self, part):
        """where the counter stands out over the run (the shelf, ceiling) the gun deck's beams cross the wing transom's
        top 1 to 15 cm over it, aft of the clamp: a chock under each, from the shelf up to the beam's underside (SEAT up
        into it), across from the run's top to the counter's face (an inch into it), so the beam bears on the
        transom; one under a beam the clamp's aft end reaches stops against that end (SEAT into it). Both sides"""
        I, O, x_s, zf = self.shelf
        x_clamp = float(self.clamp[0][0])                              # the clamp's aft end
        out, gaps = [], []
        for x, s, m, kind in self.members:
            if kind != "beam":
                continue
            x0, x1 = x - s / 2, x + s / 2
            a, b = max(x0, float(I[0, 0]), float(O[0, 0])), min(x1, x_s, float(O[-1, 0]), float(I[-1, 0]),
                                                                  x_clamp + SEAT)
            if b - a < 0.01:
                continue
            zt0, zt1 = float(self.zsu(x0)) - m, float(self.zsu(x1)) - m
            xs = np.linspace(a, b, max(2, int(math.ceil((b - a) / 0.1)) + 1))
            ylo = np.interp(xs, I[:, 0], I[:, 1])
            yhi = np.interp(xs, O[:, 0], O[:, 1])
            nv = max(2, int(math.ceil(float((yhi - ylo).max()) / 0.25)) + 1)
            v = np.linspace(0.0, 1.0, nv)
            Y = ylo[:, None] + v[None, :] * (yhi - ylo)[:, None]
            Y[:, -1] += 1.0 * IN                                       # into the counter's face
            X = np.repeat(xs[:, None], nv, axis=1)
            Q = np.column_stack([X.ravel(), np.minimum(Y.ravel(), np.repeat(yhi, nv))])
            zs = zf(Q)
            off = ~np.isfinite(zs)                                     # on the outline's chords (the hull's edge)
            if off.any():
                ol = np.concatenate([I, O])
                near = np.argmin(((Q[off, None, :] - ol[None, :, :2]) ** 2).sum(-1), axis=1)
                if np.sqrt(((Q[off] - ol[near, :2]) ** 2).sum(-1)).max() > 0.3:
                    raise SystemExit(f"berthdeck: the chock under the beam at x {x:.3f} is off the shelf")
                zs[off] = ol[near, 2]
            zs = zs.reshape(X.shape)
            zb = zs - 0.005                                            # tucked under the shelf's face
            ztop = zt0 + (X - x0) / (x1 - x0) * (zt1 - zt0) + SEAT
            gap = ztop - zs
            if gap.min() < 0.002:
                raise SystemExit(f"berthdeck: the beam at x {x:.3f} comes down into the shelf ({gap.min() * 1000:.1f} mm)")
            gaps.append(gap)
            rings = [np.concatenate([np.column_stack([X[i], Y[i], zb[i]]),
                                     np.column_stack([X[i], Y[i], ztop[i]])[::-1]]) for i in range(len(xs))]
            for sgn in (1.0, -1.0):
                strip_solid(part, [r * [1.0, sgn, 1.0] for r in rings], "Oak")
            out.append(round(x, 3))
        self.info["chocks"] = {"beams_x_m": out,
                               "deep_mm": [round(float(min(g.min() for g in gaps)) * 1000, 1),
                                           round(float(max(g.max() for g in gaps)) * 1000, 1)] if gaps else None}

    # --- the openings down to the orlop ---------------------------------------------------------------------------------
    def coaming(self, part, v, high=None, mat="Oak"):
        """a coaming round an opening (as the gun deck's), its middle v['y'] off the middle line"""
        high = v["high"] if high is None else high
        th = self.c["deck"]["thick_in"] * IN
        x0, y0, L, W, t = v["x"], v.get("y", 0.0), v["L"], v["W"], v["t"]
        xs = [x0 - L / 2 - t, x0 - L / 2, x0 + L / 2, x0 + L / 2 + t]
        ys = [y0 - W / 2 - t, y0 - W / 2, y0 + W / 2, y0 + W / 2 + t]
        zt = lambda x: float(self.zg(x)) + high          # noqa: E731
        zb = lambda x: float(self.zg(x)) - th - 0.01     # noqa: E731
        for xa, xb_ in ((xs[0], xs[1]), (xs[2], xs[3])):
            rings = [np.array([[x, ys[0], zb(x)], [x, ys[3], zb(x)], [x, ys[3], zt(x)], [x, ys[0], zt(x)]])
                     for x in (xa, xb_)]
            solid(part, rings, mat)
        for ya, yb in ((ys[0], ys[1]), (ys[2], ys[3])):
            rings = [np.array([[x, ya, zb(x)], [x, yb, zb(x)], [x, yb, zt(x)], [x, ya, zt(x)]])
                     for x in np.linspace(xs[1], xs[2], 4)]
            solid(part, rings, mat)
        return zt

    def orlop_top(self, x):
        """the orlop's top under this deck (openings orlop_below_in under this deck's top, so it keeps her sheer: the
        line the orlop slice's deck is built to, berth_deck.json ladders_down)"""
        return np.asarray(self.zg(x), float) - self.c["openings"]["orlop_below_in"] * IN

    def well(self, part, v):
        """the well under an opening down to the orlop's top (orlop_top), its sides lined (1 in, dim) under the coaming
        and its floor across on that line: a stand-in the orlop slice's deck and hatches replace; returns the floor's
        top as a function of x"""
        th = self.c["deck"]["thick_in"] * IN
        x0, y0, L, W = v["x"], v.get("y", 0.0), v["L"], v["W"]
        t = 1.0 * IN
        zf = lambda x: float(self.orlop_top(x))          # noqa: E731
        zb = lambda x: float(self.zg(x)) - th - 0.01     # noqa: E731
        xs = [x0 - L / 2 - t, x0 - L / 2, x0 + L / 2, x0 + L / 2 + t]
        ys = [y0 - W / 2 - t, y0 - W / 2, y0 + W / 2, y0 + W / 2 + t]
        for xa, xb_ in ((xs[0], xs[1]), (xs[2], xs[3])):
            rings = [np.array([[x, ys[0], zf(x)], [x, ys[3], zf(x)], [x, ys[3], zb(x)], [x, ys[0], zb(x)]])
                     for x in (xa, xb_)]
            solid(part, rings, "Dim")
        for ya, yb in ((ys[0], ys[1]), (ys[2], ys[3])):
            rings = [np.array([[x, ya, zf(x)], [x, yb, zf(x)], [x, yb, zb(x)], [x, ya, zb(x)]]) for x in (xs[1], xs[2])]
            solid(part, rings, "Dim")
        rings = [np.array([[x, ys[0], zf(x) - 3.0 * IN], [x, ys[3], zf(x) - 3.0 * IN], [x, ys[3], zf(x)], [x, ys[0], zf(x)]])
                 for x in (xs[0], xs[3])]
        solid(part, rings, "Deck")
        return zf

    def hatchways(self, part, wells, ladders):
        """each opening's coaming, its grating (deck.Deck.grating) or its ladder down to the orlop (hung from the inside
        face of the coaming at the end it leaves from, going the way the opening's 'goes' says), and its well"""
        lc = self.c["ladders"]
        self.ladder_info = []
        for k, v in self.items.items():
            zt = self.coaming(part, v)
            zf = self.well(wells, v)
            if v["kind"] == "grating":
                # its edges in a rabbet half an inch into the coaming all round (the gun deck's grating stands a tenth
                # of an inch inside its opening: 1.2 in more each way)
                self.dk.grating(part, dict(v, L=v["L"] + 1.2 * IN, W=v["W"] + 1.2 * IN), zt)
                continue
            d = 1.0 if v["goes"] == "forward" else -1.0
            xt = v["x"] - d * v["L"] / 2
            xf, drop = self.ladder(ladders, xt, zt(xt), d, v["y"], zf, lc)
            self.ladder_info.append({"in": k, "top_x_m": round(xt, 3), "foot_x_m": round(xf, 3), "y_m": round(v["y"], 3),
                                     "goes": v["goes"], "foot_z_m": round(zf(xf), 3), "drop_m": round(drop, 3)})
        self.info["ladders"] = self.ladder_info

    # --- what comes down through the gun deck ---------------------------------------------------------------------------
    def spindle(self, part):
        """the double capstan's spindle from its step on these planks up into the gun deck capstan's barrel (which hangs
        below the gun deck: GunDeck.capstan), iron hoops at its foot and its head; the step an oak block on the planks,
        let in half an inch, with its bolts' heads"""
        th = self.c["through"]
        gd = self.gd
        x = self.x_capstan
        r = th["spindle_in"] / 2 * IN
        sl, sw, sh = (v * IN for v in th["step_in"])
        zlo = float(min(self.zg(x - sl / 2), self.zg(x + sl / 2))) - 0.5 * IN
        ztop = float(max(self.zg(x - sl / 2), self.zg(x + sl / 2))) + sh
        vbox(part, [x - sl / 2, -sw / 2, zlo], [x + sl / 2, sw / 2, ztop], "Oak")
        for k in range(th["step_bolts"]):
            a = math.pi / 4 + k * math.pi / 2
            p = np.array([x + 0.36 * sl * math.cos(a) / abs(math.cos(a)), 0.36 * sw * math.sin(a) / abs(math.sin(a)), ztop])
            lathe(part, p - EZ * 0.25 * IN, EZ, EX, [(0.0, 0.75 * IN), (0.3 * IN, 0.75 * IN), (0.55 * IN, 0.6 * IN),
                                                    (0.7 * IN, 0.3 * IN)], "Iron", 10)
        z_barrel = float(gd.zg(x)) - gd.c["deck"]["thick_in"] * IN - 0.15     # the gun deck barrel's foot
        top = z_barrel + 1.0 * IN
        lathe(part, [x, 0.0, ztop - 0.25 * IN], EZ, EX, [(0.0, r), (top - ztop + 0.25 * IN, r)], "Oak", 24)
        hw, ht = (v * IN for v in th["spindle_hoop_in"])
        for zc in (ztop + 2.0 * IN, z_barrel - 3.0 * IN):
            ring_band(part, np.array([x, 0.0, zc]), EZ, EX, 0.0, r, hw, ht, "Iron", 24)
        self.info["spindle"] = {"x_m": round(x, 3), "step_top_m": round(ztop, 3), "into_barrel_at_m": round(z_barrel, 3)}

    def bitt_posts(self, part):
        """the riding bitts' posts from the gun deck's (which end 0.15 m under its planks: GunDeck.bitts) on down to
        these planks, let in bitt_let_in_in, of the same chamfered section"""
        gd = self.gd
        bt = gd.c["bitts"]
        x0, p, ch = bt["x_m"], bt["post_in"] * IN, bt["chamfer_in"] * IN
        th_g = gd.c["deck"]["thick_in"] * IN
        let = self.c["through"]["bitt_let_in_in"] * IN
        for sy in (1.0, -1.0):
            y = sy * bt["y_in"] * IN
            S = chamfered_rect((x0, y), p / 2, p / 2, ch)
            lo = np.column_stack([S, self.zg(S[:, 0]) - let])
            hi = np.column_stack([S, gd.zg(S[:, 0]) - th_g - 0.15])
            solid(part, [lo, hi], "Oak")

    def pump_trees(self, part):
        """the pumps' tubes from the holes in these planks up to the gun deck's planks' underside (the pumps stand on
        the gun deck over them): the chain pumps' square pipes, the brake pumps' bored trees, each with an iron band
        under the gun deck"""
        top = lambda x: float(self.zsu(x)) + 0.5 * IN    # noqa: E731
        th = self.c["deck"]["thick_in"] * IN
        for name, (x, y), kind, h in self.pump_tubes():
            z0 = float(self.zg(x)) - th
            if kind == "square":
                vbox(part, [x - h, y - h, z0], [x + h, y + h, top(x)], "Oak")
            else:
                lathe(part, [x, y, z0], EZ, EX, [(0.0, h), (top(x) - z0, h)], "Oak", 16)
                ring_band(part, np.array([x, y, top(x) - 4.0 * IN]), EZ, EX, 0.0, h, 1.5 * IN, 0.3 * IN, "Iron", 16)

    def cable_scuttles(self, part, wells):
        """the cables' scuttles in these planks straight under the gun deck's: a lead collar round each, its lining down
        the hole and a short dark well under it (through scuttle_well_ft: the cable tiers are the orlop slice's)"""
        th = self.c["through"]
        xs, ys = self.scuttles()
        r = th["scuttle_in"] / 2 * IN
        cw, ct = (v * IN for v in th["collar_in"])
        wd = th["scuttle_well_ft"] * FT
        for sy in (1.0, -1.0):
            c = np.array([xs, sy * ys, float(self.zg(xs))])
            k0 = len(part.V)
            ring_band(part, c, EZ, EX, ct / 2 - 0.02 * IN, r, ct, cw, "Lead", 32)
            revolve(part, c - EZ * wd, EZ, EX, [(0.0, r - 0.25 * IN), (wd, r - 0.25 * IN)], "Lead", 32, want_out=False)
            k1 = len(wells.V)
            disc(wells, c - EZ * wd, EZ, r, "Shadow", 24)
            self.drape(part, k0, float(c[2]))
            self.drape(wells, k1, float(c[2]))

    # --- the rooms ------------------------------------------------------------------------------------------------------
    def over_boxes(self):
        """the gun deck's framing between its members over this deck, each carling and head ledge as a plan box with its
        depth under the planks: [(x0, x1, y0, y1, depth)]"""
        oh = self.c["overhead"]
        cs_, cm = (v * IN for v in oh["carling_in"])
        ls, lm = (v * IN for v in oh["ledge_in"])
        out = [(c_["x_m"][0], c_["x_m"][1], c_["y_m"] - cs_ / 2, c_["y_m"] + cs_ / 2, cm)
               for c_ in self.overhead_info["carlings"]]
        out += [(h["x_m"] - ls / 2, h["x_m"] + ls / 2, -h["y_m"], h["y_m"], lm) for h in self.overhead_info["head_ledges"]]
        return out

    def knee_spans(self):
        """the lodging knees' spans along the ship (each from its beam's face out along the side): [(x0, x1)]"""
        s_ = self.c["overhead"]["beam_in"][0] * IN
        out = []
        for k in self.info["lodging_knees"]["by_beam"]:
            d = 1.0 if k["face"] == "fore" else -1.0
            xf = k["beam_x_m"] + d * s_ / 2
            out.append(tuple(sorted((xf, xf + d * k["side_arm_m"]))))
        return out

    def bay_x(self, x, t, side=True, gap=1.0 * IN):
        """x moved the least so a partition t thick across there stands in a bay between the gun deck's members and head
        ledges overhead, gap clear of their faces (its head under the planks, clear of the hanging knees under the
        beams' ends); side (it runs out to the side): clear of the lodging knees too"""
        ls = self.c["overhead"]["ledge_in"][0] * IN
        faces = [(x_ - s_ / 2, x_ + s_ / 2) for x_, s_, m, kind in self.members]
        faces += [(h["x_m"] - ls / 2, h["x_m"] + ls / 2) for h in self.overhead_info["head_ledges"]]
        if side:
            faces += self.knee_spans()
        free, hi = [], -1e9
        for a, b in sorted(faces):
            if a > hi:
                free.append((hi, a))
            hi = max(hi, b)
        free.append((hi, 1e9))
        B = [(a + gap + t / 2, b - gap - t / 2) for a, b in free if b - a >= 2 * gap + t]
        a, b = min(B, key=lambda ab: max(ab[0] - x, x - ab[1], 0.0))
        xb = float(min(max(x, a), b))
        if abs(xb - x) > self.c["overhead"]["bay_max_shift_m"]:
            raise SystemExit(f"berthdeck: a bulkhead or partition at x {x:.3f} would move {xb - x:+.3f} m to stand in a "
                             f"bay overhead, more than overhead bay_max_shift_m: give the card its x in a bay")
        return xb

    def partition(self, part, x, t, y_in, doors=(), mat="Interior"):
        """a partition across the ship at x, t thick (as GunDeck.partition): from y_in out to the starboard side (y_in
        None: from side to side), a quarter inch into the deck, scribed into the waterway's cove, let a quarter inch into
        the side's ceiling and the clamp, doors [(y0, y1, height)] notched up from its foot; its head under the gun
        deck's planks, stepped down under each carling and head ledge over it (over_boxes). Each face is scribed to the
        side, the cove and the clamp as they are across at that face (where the side runs aslant they differ face to
        face). Returns its outlines (y, z) at its two faces"""
        let = 0.25 * IN
        prof = np.array(self.c["deck"]["waterway"]["profile_in"], float) * IN
        Xc, Zb, _ = self.clamp

        def side(xf):
            """the outline's edge against the side at the face xf (starboard), from the cove's toe on the deck up to the
            gun deck's planks, and the face's heights (deck, planks' underside)"""
            zg, zt = float(self.zg(xf)), float(self.zsu(xf))
            S = self.waterway_cut(xf)
            st = [(S[-1, 0], S[-1, 1] - let)] + [(S[j, 0], S[j, 1] - let) for j in range(len(prof) - 2, -1, -1)
                                                 if prof[j, 1] > 0.0]
            zcf = float(np.interp(xf, Xc, Zb))
            zz = np.linspace(S[0, 1], zcf, 8)
            Pw, _ = self.wall_at(np.full(8, xf), zz)
            st += [(float(Pw[k, 1]) + let, float(zz[k])) for k in range(1, 8)]
            Cb, Ct = self.clamp_corner(xf, False), self.clamp_corner(xf, True)
            zct = self.beam_bottom(xf)                     # the clamp's top; over it out to the side again
            ywt = self.wall_at(np.array([xf, xf]), np.array([zct, zt]))[0][:, 1]
            st += [(float(Cb[1]) + let, float(Cb[2])), (float(Ct[1]) + let, zct), (float(ywt[0]) + let, zct),
                   (float(ywt[1]) + let, zt)]
            return st, zg, zt
        faces = [side(xf) for xf in (x - t / 2, x + t / 2)]
        y_out = max(st[-1][0] for st, _, _ in faces)
        y_lo = -y_out if y_in is None else y_in
        boxes = [bx for bx in sorted(self.over_boxes(), key=lambda bx: -bx[3])
                 if bx[0] < x + t / 2 and bx[1] > x - t / 2 and bx[2] < y_out and bx[3] > y_lo]
        polys = []
        for st, zg, zt in faces:
            y_top = st[-1][0]
            lo = -y_top if y_in is None else y_in
            steps = []
            for x0, x1, a, b, dep in boxes:
                a, b = max(a, lo), min(b, y_top)
                steps += [(b, zt), (b, zt - dep), (a, zt - dep), (a, zt)]
            bottom = []
            for d0, d1, h in sorted(doors):
                bottom += [(d0, zg - let), (d0, zg + h), (d1, zg + h), (d1, zg - let)]
            if y_in is None:
                port = [(-y, z) for y, z in st[::-1]]
                poly = port[-1:] + bottom + st + steps + port[:-1]
            else:
                poly = [(y_in, zg - let)] + bottom + st + steps + [(y_in, zt)]
            polys.append(np.array(poly))
        P0, P1 = polys
        keep = [0] + [i for i in range(1, len(P0)) if max(np.linalg.norm(P0[i] - P0[i - 1]),
                                                         np.linalg.norm(P1[i] - P1[i - 1])) > 1e-7]
        P0, P1 = P0[keep], P1[keep]
        prism2(part, P0, P1, x - t / 2, x + t / 2, mat)
        return P0, P1

    def waterway_cut(self, xf):
        """the waterway's cove (starboard) cut across the ship at xf: (y, z) at each point of its profile (profile_in, from
        its top at the side to its toe on the deck). The cove is laid square to the side, so where the side runs aslant
        in plan (the bow) it is wider across than its profile"""
        R = self.ww_rings
        out = []
        for j in range(2, R.shape[1] - 1):
            X = R[:, j, 0]
            if not (X[0] <= xf <= X[-1]) or (np.diff(X) <= 0.0).any():
                raise SystemExit(f"berthdeck: no waterway across at x {xf:.3f} to scribe a partition to")
            out.append((float(np.interp(xf, X, R[:, j, 1])), float(np.interp(xf, X, R[:, j, 2]))))
        return np.array(out)

    def hooked_doors(self, part, x, t, doors, opens):
        """each door's leaf (deal, 1 1/4 in, two raised panels on its open face) hooked back flat against the face of the
        bulkhead at x (t thick) toward opens (+1 forward, -1 aft), outboard of the post it hangs on (the starboard post
        of a door across the middle line), on two hinges, a hook and eye holding it, its foot half an inch over the deck"""
        dt = 1.25 * IN
        zg = float(self.zg(x))
        xf = x + opens * t / 2
        out = []
        for y0, y1, h in doors:
            hinge, sy = (y1, 1.0) if y0 + y1 >= 0.0 else (y0, -1.0)
            w = y1 - y0
            ya, yb = sorted((hinge + sy * 0.2 * IN, hinge + sy * (w - 0.1 * IN)))
            xa, xb = sorted((xf + opens * 0.3 * IN, xf + opens * (0.3 * IN + dt)))
            z0, z1 = zg + 0.5 * IN, zg + h - 0.15 * IN
            vbox(part, [xa, ya, z0], [xb, yb, z1], "Interior")
            xo = xb if opens > 0 else xa
            for zc, hh in ((z0 + 0.28 * (z1 - z0), 0.4 * (z1 - z0)), (z0 + 0.74 * (z1 - z0), 0.36 * (z1 - z0))):
                vbox(part, [min(xo, xo + opens * 0.3 * IN), ya + 0.18 * w, zc - hh / 2],
                     [max(xo, xo + opens * 0.3 * IN), yb - 0.18 * w, zc + hh / 2], "Interior")
            for zk in (z0 + 9.0 * IN, z1 - 9.0 * IN):      # the hinges' knuckles on the post, off the face
                lathe(part, [xf + opens * 0.3 * IN, hinge, zk - 2.0 * IN], EZ, EX, [(0.0, 0.32 * IN), (4.0 * IN, 0.32 * IN)],
                      "Iron", 10)
            # the hook: an eye in the bulkhead's face beyond the leaf's free edge, the hook over the leaf's edge
            ye = (yb if sy > 0 else ya) + sy * 1.5 * IN
            zh = z0 + 0.5 * (z1 - z0)
            tube(part, np.array([[xf - opens * 0.25 * IN, ye, zh], [xf + opens * (0.3 * IN + dt + 0.4 * IN), ye, zh],
                                 [xf + opens * (0.3 * IN + dt + 0.4 * IN), ye - sy * 2.2 * IN, zh],
                                 [xo - opens * 0.1 * IN, ye - sy * 2.2 * IN, zh]]), 0.12 * IN, "Iron", n=6)
            out.append({"y_m": [round(y0, 3), round(y1, 3)], "high_m": round(h, 3), "hinge_y_m": round(hinge, 3),
                        "hooked_back": "forward" if opens > 0 else "aft"})
        return out

    def fa_wall(self, part, y, x0, x1, t, doors=(), hd=0.0, mat="Interior"):
        """a wall fore and aft at y > 0 (built to starboard: the caller mirrors it), t thick, from x0 to x1, its foot a
        quarter inch into the deck along the sheer, its head stepped under the gun deck's members over it
        (top_under_members), a door notched up from its foot for each (d0, d1), hd high, its leaf shut in it with a
        brass knob each face"""
        let = 0.25 * IN
        xs = np.linspace(x0, x1, max(2, int(math.ceil((x1 - x0) / 0.5)) + 1))
        foot = [(float(x), float(self.zg(x)) - let) for x in xs]
        for d0, d1 in sorted(doors):
            notch = [(d0, float(self.zg(d0)) - let), (d0, float(self.zg(d0)) + hd), (d1, float(self.zg(d1)) + hd),
                     (d1, float(self.zg(d1)) - let)]
            foot = [p for p in foot if p[0] < d0 - 0.01] + notch + [p for p in foot if p[0] > d1 + 0.01]
        top = self.top_under_members([x0, x1], y)
        P = np.array(foot + top[::-1])
        keep = [0] + [i for i in range(1, len(P)) if np.linalg.norm(P[i] - P[i - 1]) > 1e-7]
        prism(part, P[keep], y - t / 2, y + t / 2, mat, axis=1)
        for d0, d1 in doors:
            zd = float(self.zg(0.5 * (d0 + d1)))
            k0 = len(part.V)
            vbox(part, [d0 + 0.1 * IN, y - 0.5 * IN, zd + 0.25 * IN], [d1 - 0.1 * IN, y + 0.5 * IN, zd + hd - 0.1 * IN], mat)
            for fy in (1.0, -1.0):
                lathe(part, [d1 - 2.5 * IN, y + fy * 0.4 * IN, zd + 36.0 * IN], fy * EY, EX,
                      [(0.0, 0.35 * IN), (0.8 * IN, 0.3 * IN), (1.0 * IN, 0.8 * IN), (1.8 * IN, 0.8 * IN)], "Bronze", 10)
            self.drape(part, k0, zd)

    def rooms(self, part):
        """the bulkheads across the ship (the wardroom's after and fore, the steerage's, the sick bay's after and fore),
        each in a bay between the gun deck's members (bay_x), its doors' leaves hooked back; the wardroom's state rooms
        either side (their inboard walls fore and aft, the partitions between them, a door into each from the wardroom)
        and the officers' rooms along each side forward of the steerage the same way. Painted deal (Interior). Their x as
        built: self.room_x"""
        c = self.c
        wr, sg, orr, sb = c["wardroom"], c["steerage"], c["officers_rooms"], c["sick_bay"]
        X = self.room_x = {}
        across = {"wardroom_aft": (wr["after_bulkhead_x_m"], wr["bulkhead_in"], wr["after_doors"], -1.0),
                  "wardroom_fore": (wr["fore_bulkhead_x_m"], wr["bulkhead_in"], wr["fore_doors"], 1.0),
                  "steerage": (sg["bulkhead_x_m"], sg["bulkhead_in"], sg["doors"], 1.0),
                  "sick_bay_aft": (sb["after_bulkhead_x_m"], sb["bulkhead_in"], sb["doors"], -1.0),
                  "sick_bay_fore": (sb["fore_bulkhead_x_m"], sb["bulkhead_in"], sb["doors"], 1.0)}
        info = {}
        for k, (x_card, t_in, ds, opens) in across.items():
            t = t_in * IN
            x = X[k] = self.bay_x(x_card, t)
            doors = []
            for d in ds:
                y0, y1 = d["y_m"]
                doors.append((y0, y1, d["high_in"] * IN))
                if y0 > 0.0:                               # one each side of the middle line
                    doors.append((-y1, -y0, d["high_in"] * IN))
            self.partition(part, x, t, None, sorted(doors))
            info[k] = {"x_m": round(x, 4), "card_x_m": x_card, "doors": self.hooked_doors(part, x, t, sorted(doors), opens)}
        # the state rooms (the wardroom's) and the officers' rooms: inboard walls fore and aft, partitions between
        for key, rc, x_a, x_f in (("state_rooms", wr, X["wardroom_aft"] + wr["bulkhead_in"] / 2 * IN,
                                   X["wardroom_fore"] - wr["bulkhead_in"] / 2 * IN),
                                  ("officers_rooms", orr, X["steerage"] + sg["bulkhead_in"] / 2 * IN, None)):
            tw = rc["wall_in"] * IN
            ys = rc["wall_y_m"]
            px = [self.bay_x(x, tw) for x in rc["partitions_x_m"]]
            if x_f is None:                                # the officers' rooms' last partition is their fore wall
                x_f = px[-1] + tw / 2
                walls = px
            else:
                walls = px
            ends = [x_a] + [p + tw / 2 for p in walls if p + tw / 2 < x_f - 0.01]
            fronts = [p - tw / 2 for p in walls if p - tw / 2 < x_f - 0.01] + [x_f]
            d0, d1 = rc["door_in_room_m"]
            doors = [(a + d0, a + d1) for a in ends]
            if any(a + d1 > b - 0.05 for a, b in zip(ends, fronts)):
                raise SystemExit(f"berthdeck: a door of the {key} runs past its room's fore end")
            sp = Part()
            # each end let a quarter inch into what it meets: the wardroom's bulkheads, the steerage's; the officers'
            # rooms' walls end a quarter inch inside their last partition, which is their fore wall
            self.fa_wall(sp, ys, x_a - 0.25 * IN, x_f + (0.25 * IN if key == "state_rooms" else -0.25 * IN), tw, doors,
                         rc["door_high_in"] * IN)
            for p in walls:
                self.partition(sp, p, tw, ys - tw / 2 + 0.25 * IN, ())
            part.extend(sp)
            part.extend(mirrored(sp))
            X[key] = px
            info[key] = {"wall_y_m": ys, "partitions_x_m": [round(p, 4) for p in px],
                         "card_partitions_x_m": rc["partitions_x_m"],
                         "rooms_x_m": [[round(a, 3), round(b, 3)] for a, b in zip(ends, fronts)],
                         "doors_x_m": [[round(a, 3), round(b, 3)] for a, b in doors]}
        self.info["rooms"] = info

    def chair(self, part, cx, cy, deg):
        """a chair as the gun deck's cabin's (gundeck_1797.json cabin chair_in), on a level deck at 0, facing deg (0:
        forward): square legs, a seat, the back's uprights carried up from the back legs, a top rail and a splat"""
        ci = self.gd.c["cabin"]["chair_in"]
        w, d, hs = (v * IN for v in ci["seat"])
        hb = ci["back_high_in"] * IN
        lg = ci["leg_in"] * IN
        a = math.radians(deg)
        f = np.array([math.cos(a), math.sin(a), 0.0])
        s = np.array([-math.sin(a), math.cos(a), 0.0])
        c = np.array([cx, cy, 0.0])

        def P(df, ds, dz):
            return c + f * df + s * ds + EZ * dz
        for df in (d / 2 - lg / 2, -d / 2 + lg / 2):
            for ds in (-w / 2 + lg / 2, w / 2 - lg / 2):
                top = hs - 0.6 * IN if df > 0 else hb - 0.5 * IN
                bar(part, P(df, ds, 0.0), P(df, ds, top), lg, lg, "Mahogany", up=f)
        box(part, P(0.0, 0.0, hs - 0.5 * IN), f, s, EZ, d / 2 + 0.3 * IN, w / 2 + 0.3 * IN, 0.5 * IN, "Mahogany")
        box(part, P(-d / 2 + lg / 2, 0.0, hb - 1.25 * IN), f, s, EZ, lg / 2 + 0.1 * IN, w / 2 + 0.25 * IN, 1.25 * IN,
            "Mahogany")
        hz = 0.5 * (hb - 2.5 * IN - hs)
        box(part, P(-d / 2 + lg / 2, 0.0, hs + hz), f, s, EZ, 0.35 * IN, 2.75 * IN, hz, "Mahogany")
        for ds in (-w / 2 + lg / 2, w / 2 - lg / 2):
            bar(part, P(d / 2 - lg, ds, 5.0 * IN), P(-d / 2 + lg, ds, 5.0 * IN), 0.75 * IN, 1.0 * IN, "Mahogany")
        return d, w

    def wardroom_furniture(self, part):
        """the wardroom's long table (mahogany: its top on an apron and six turned legs) under the skylight, chairs_a_side
        chairs along each side and one at each end (chairs_at_ends) where it stands clear of the mizzen's wedges; built
        on a level deck and laid along the sheer (drape), every foot on the planks"""
        wr = self.c["wardroom"]
        tb = wr["table"]
        L, W = (v * IN for v in tb["size_in"])
        h, tt = tb["high_in"] * IN, tb["top_in"] * IN
        x0 = tb["x_m"]
        k0 = len(part.V)
        vbox(part, [x0 - L / 2, -W / 2, h - tt], [x0 + L / 2, W / 2, h], "Mahogany")
        ins, ap = 3.0 * IN, 0.9 * IN
        for a_, b_ in (((x0 - L / 2 + ins, -W / 2 + ins), (x0 + L / 2 - ins, -W / 2 + ins + ap)),
                       ((x0 - L / 2 + ins, W / 2 - ins - ap), (x0 + L / 2 - ins, W / 2 - ins)),
                       ((x0 - L / 2 + ins, -W / 2 + ins + ap), (x0 - L / 2 + ins + ap, W / 2 - ins - ap)),
                       ((x0 + L / 2 - ins - ap, -W / 2 + ins + ap), (x0 + L / 2 - ins, W / 2 - ins - ap))):
            vbox(part, [a_[0], a_[1], h - tt - 4.5 * IN], [b_[0], b_[1], h - tt + 0.05 * IN], "Mahogany")
        for xl in (x0 - L / 2 + ins + 0.9 * IN, x0, x0 + L / 2 - ins - 0.9 * IN):
            for sy in (-1.0, 1.0):
                lathe(part, [xl, sy * (W / 2 - ins - 0.9 * IN), 0.0], EZ, EX,
                      [(0.0, 0.75 * IN), (1.0 * IN, 0.85 * IN), (2.0 * IN, 0.75 * IN), (h - tt - 6.0 * IN, 1.1 * IN),
                       (h - tt - 5.0 * IN, 1.25 * IN), (h - tt + 0.05 * IN, 1.25 * IN)], "Mahogany", 12)
        ci = self.gd.c["cabin"]["chair_in"]
        d, w = ci["seat"][1] * IN, ci["seat"][0] * IN
        n = wr["chairs_a_side"]
        seats = []
        for k in range(n):
            xc = x0 - L / 2 + L * (k + 0.5) / n
            for sy in (1.0, -1.0):
                seats.append((xc, sy * (W / 2 + d / 2 - 2.0 * IN), -90.0 * sy))
        if wr["chairs_at_ends"]:
            seats += [(x0 - L / 2 - d / 2 + 2.0 * IN, 0.0, 0.0), (x0 + L / 2 + d / 2 - 2.0 * IN, 0.0, 180.0)]
        p_m, R_m, _ = self.mast_at("mizzen", float(self.zg(self.mast_x("mizzen"))))
        r_w = R_m + self.c["deck"]["mast_hole_gap_in"] * IN + 1.25 * IN
        placed, dropped = [], []
        for cx, cy, deg in seats:
            reach = math.hypot(d / 2 + 0.05, w / 2 + 0.05)
            if math.hypot(cx - p_m[0], cy - p_m[1]) < r_w + reach + 0.1:
                dropped.append([round(cx, 3), round(cy, 3)])
                continue
            self.chair(part, cx, cy, deg)
            placed.append([round(cx, 3), round(cy, 3), deg])
        self.drape(part, k0, 0.0)
        self.table_box = (x0 - L / 2 - d - 0.05, x0 + L / 2 + d + 0.05, W / 2 + d)
        self.info["wardroom_furniture"] = {"table_x_m": x0, "chairs": placed, "chairs_left_out_by_the_mizzen": dropped}

    def sick_bay(self, part, hooks):
        """the sick bay's cots (sick_bay cot_in: a canvas bed in a wooden frame, its clews fanned from each end's
        corners to a hook under the beam beyond, cot_drop_in under the beams), cots_a_side rows fore and aft between the
        two beams two apart nearest the room's middle, the outer row's hooks inboard of the hanging knees' heads; and the
        surgeon's dispensary chest against the fore bulkhead's after face to starboard, outboard of its door. The hooks
        are the stores kit's (copies: self.copies_)"""
        sb = self.c["sick_bay"]
        X = self.room_x
        xa, xf = X["sick_bay_aft"], X["sick_bay_fore"]
        Lc, Wc, Dc = (v * IN for v in sb["cot_in"])
        fw, ft = (v * IN for v in sb["cot_frame_in"])
        beams = [m[0] for m in self.members if m[3] == "beam" and xa + 0.3 < m[0] < xf - 0.3]
        mid = 0.5 * (xa + xf)
        pairs = [(a, b) for a, b in zip(beams[:-2], beams[2:])]
        if not pairs:
            raise SystemExit("berthdeck: no two beams two apart over the sick bay to sling its cots from")
        b0, b1 = min(pairs, key=lambda ab: abs(0.5 * (ab[0] + ab[1]) - mid))
        xc = 0.5 * (b0 + b1)
        heads = [v[0] for k, v in self.knee_heads.items() if b0 - 0.01 <= k <= b1 + 0.01]
        y_out = min(heads) - 0.05 - Wc / 2                 # the outer cots' outboard edge inboard of the knees' heads
        gap = 0.15
        rows = [y_out - k * (Wc + gap) for k in range(sb["cots_a_side"])]
        zb0, zb1 = self.beam_bottom(b0), self.beam_bottom(b1)
        hk = self.hook_item()
        bar = np.array(hk.attach["bar"], float)
        hb = hk.info["bar_m"]
        # the clews' ring (the hammock's clew ring, stores_1797.json hammock ring_in), hung on the hook's bar across it:
        # its inside resting on the bar's top, a twentieth of an inch into it as drawn (the ring's six-sided iron and the
        # bar's eight-sided round cut a thirtieth of that off between their flats)
        hc = self.kit().c["hammock"]
        rr, rb = hc["ring_in"][0] / 2 * IN, hc["ring_in"][1] / 2 * IN
        ring_local = bar + EZ * (hb - (rr - rb) - 0.05 * IN)
        cr = 0.16 * IN
        cots = []
        for sy in (1.0, -1.0):
            for y in rows:
                yc = sy * y
                zt = 0.5 * (zb0 + zb1) - sb["cot_drop_in"] * IN          # the cot's frame's top
                xs0, xs1 = xc - Lc / 2, xc + Lc / 2
                # the frame round its top, the canvas bed hanging under it
                for (p0, p1) in (((xs0, yc - Wc / 2), (xs1, yc - Wc / 2 + fw)), ((xs0, yc + Wc / 2 - fw), (xs1, yc + Wc / 2)),
                                 ((xs0, yc - Wc / 2 + fw), (xs0 + fw, yc + Wc / 2 - fw)),
                                 ((xs1 - fw, yc - Wc / 2 + fw), (xs1, yc + Wc / 2 - fw))):
                    vbox(part, [p0[0], p0[1], zt - ft], [p1[0], p1[1], zt], "Oak")
                ins = 0.3 * IN
                vbox(part, [xs0 + ins, yc - Wc / 2 + ins, zt - Dc], [xs1 - ins, yc + Wc / 2 - ins, zt - ft - 0.05 * IN],
                     "Canvas")
                for xe, xh, zh, s_ in ((xs0, b0, zb0, -1.0), (xs1, b1, zb1, 1.0)):
                    # the hook under the beam (its bight toward the cot), an iron ring hung on its bar across it (the
                    # ring in the plane across the bar, y and z), and the clews from the frame's two corners at this end
                    # up to the ring's lower arc, each made fast with an eye round the ring's iron and its end seized
                    # back along it
                    R = np.eye(3) if s_ < 0 else np.diag([-1.0, -1.0, 1.0])
                    o = np.array([xh, yc, zh + SEAT])
                    hooks.append(("CotHook", o, R))
                    rc_ = o + R @ ring_local
                    th = np.linspace(0.0, 2 * math.pi, 17)[:-1]
                    tube(part, rc_[None] + rr * (np.cos(th)[:, None] * EY[None] + np.sin(th)[:, None] * EZ[None]), rb,
                         "Iron", n=6, closed=True)
                    for cy, tc in ((yc - Wc / 2 + fw / 2, math.radians(-120.0)), (yc + Wc / 2 - fw / 2, math.radians(-60.0))):
                        corner = np.array([xe - s_ * 0.5 * IN, cy, zt - ft / 2])
                        Pw = rc_ + rr * (math.cos(tc) * EY + math.sin(tc) * EZ)      # the ring's iron where the clew takes it
                        t_ = -math.sin(tc) * EY + math.cos(tc) * EZ                   # the iron's run there
                        v = corner - Pw
                        e1 = v - t_ * float(v @ t_)
                        e1 = e1 / np.linalg.norm(e1)                                   # toward the corner, across the iron
                        e2 = np.cross(t_, e1)
                        ra = rb + cr * 0.85
                        eye = [Pw + ra * (math.cos(f) * e1 + math.sin(f) * e2) for f in np.linspace(0.5 * math.pi, 1.5 * math.pi, 7)]
                        tail = [eye[-1] + e1 * 0.6 * IN + e2 * 0.2 * ra, eye[-1] + e1 * 1.4 * IN + e2 * 0.6 * ra]
                        tube(part, np.array([corner] + eye + tail), cr, "Hemp", n=6)
                cots.append([round(xc, 3), round(yc, 3)])
        # the dispensary chest: a box and its lid on the planks
        cl, cw, ch = (v * IN for v in sb["chest_in"])
        x1 = xf - sb["bulkhead_in"] / 2 * IN - 0.5 * IN
        x0 = x1 - cw
        y0 = max(d["y_m"][1] for d in sb["doors"]) + 0.15
        k0 = len(part.V)
        z0 = float(self.zg(0.5 * (x0 + x1)))
        vbox(part, [x0, y0, 0.0], [x1, y0 + cl, ch - 1.0 * IN], "Oak")
        vbox(part, [x0 - 0.5 * IN, y0 - 0.5 * IN, ch - 1.0 * IN], [x1 + 0.25 * IN, y0 + cl + 0.5 * IN, ch], "Oak")
        for yy in (y0 + 0.25 * cl, y0 + 0.75 * cl):
            lathe(part, [x0 - 0.5 * IN, yy, ch - 4.0 * IN], -EX, EY, [(0.0, 0.3 * IN), (0.5 * IN, 0.3 * IN), (0.7 * IN, 0.7 * IN),
                                                                  (1.1 * IN, 0.7 * IN)], "Bronze", 10)
        self.drape(part, k0, 0.0)
        self.chest_box = (x0, x1, y0, y0 + cl)
        self.info["sick_bay"] = {"x_m": [round(xa, 3), round(xf, 3)], "cots_between_beams_x_m": [round(b0, 3), round(b1, 3)],
                                 "cots": cots, "chest_x_m": [round(x0, 3), round(x1, 3)], "chest_y_m": [round(y0, 3),
                                                                                                       round(y0 + cl, 3)],
                                 "deck_under_chest_m": round(z0, 3)}

    def kit(self):
        """the stores kit (stores.Kit) whose items this deck places as copies"""
        if getattr(self, "_kit", None) is None:
            import stores
            self._kit = stores.Kit()
        return self._kit

    def hook_item(self):
        """the stores kit's hammock hook (the cots' and the hammocks' hooks under the beams)"""
        if "HammockHook" not in self.copy_items:
            self.copy_items["HammockHook"] = self.kit().hammock_hook()
        return self.copy_items["HammockHook"]

    def add_copy(self, name, item, o, R, collection):
        """a linked copy of a stores item (self.copy_items[item]) placed by its frame's origin o and turn R"""
        M = np.eye(4)
        M[:3, :3], M[:3, 3] = R, o
        self.copies_.append({"name": name, "item": item, "matrix": M, "collection": collection})

    # --- the lanterns ---------------------------------------------------------------------------------------------------
    def lantern_size(self):
        """the hung lanterns' sizes: the gun deck's (gundeck_1797.json lanterns) with this deck's smaller body, roof,
        ring and hook (lanterns size)"""
        return dict(self.gd.c["lanterns"], **self.c["lanterns"]["size"])

    def lantern_r(self):
        """a hung lantern's reach from its axis in plan: its roof's brim"""
        return 0.5 * self.lantern_size()["body_in"][0] * IN + 0.45 * IN

    def lantern(self, part, H, lt=None):
        """a horn lantern as the gun deck's, hung from H, of the gun deck's sizes or lt's (lantern_size)"""
        return GunDeck.lantern(self.gd, part, H, lt)

    def lanterns(self, part, bar_part):
        """the horn lanterns (lanterns hung): each on a hook in the gun deck planks' underside in the bay (between two
        members or head ledges overhead) whose middle lies nearest its x_m, at its y_m, clear of the carlings; and the
        wardroom's over the middle of its table from a bar (in bar_part) across between the skylight's carlings. Each a
        light in the game data (self.lights) in its zone; an unshadowed one reaches no further than the nearest bulkhead
        between zones (the wardroom's and the sick bay's), less 5 cm; a shadowed one stops at them by its shadows"""
        lt, glt = self.c["lanterns"], self.gd.c["lanterns"]
        li, lw = lt["light"], lt["wardroom_light"]
        sz, R_l = self.lantern_size(), self.lantern_r()
        bm = self.c["overhead"]["beam_in"][1] * IN
        ls = self.c["overhead"]["ledge_in"][0] * IN
        faces = sorted([(x - s_ / 2, x + s_ / 2) for x, s_, m, kind in self.members] +
                       [(h["x_m"] - ls / 2, h["x_m"] + ls / 2) for h in self.overhead_info["head_ledges"]])
        bays = [(f0[1], f1[0]) for f0, f1 in zip(faces[:-1], faces[1:]) if f1[0] - f0[1] >= 2 * R_l + 0.1]
        X = self.room_x
        bounds = [X["wardroom_aft"], X["wardroom_fore"], X["sick_bay_aft"], X["sick_bay_fore"]]
        placed = []

        def light(nm, c, zone, radius, shadows):
            self.lights.append({"name": nm, "pos_m": [round(float(v), 4) for v in c], "zone": zone,
                                "colour_rgb": li["colour_rgb"], "kelvin": li["kelvin"], "lumens": li["lumens"],
                                "radius_m": round(float(radius), 3), "cast_shadows": shadows})
        walls = [X[k] for k in ("wardroom_aft", "wardroom_fore", "steerage", "sick_bay_aft", "sick_bay_fore")]
        ob, oa = self.over_boxes(), self.openings_above()

        def clear(x, y):
            """under the gun deck's planks: not under a carling or head ledge, nor under an opening through them"""
            return not (any(x0 < x + R_l + 0.02 and x1 > x - R_l - 0.02 and a < y + R_l + 0.02 and b > y - R_l - 0.02
                            for x0, x1, a, b, dep in ob) or
                        any(x0 < x + R_l + 0.02 and x1 > x - R_l - 0.02 and abs(y) - R_l - 0.02 < hw
                            for x0, x1, hw, nm in oa))
        for h in lt["hung"]:
            y = h["y_m"]
            pick = None
            for lo, hi in sorted(bays, key=lambda b: abs(0.5 * (b[0] + b[1]) - h["x_m"])):
                x = 0.5 * (lo + hi)
                if abs(x - h["x_m"]) > lt["max_shift_m"]:
                    break
                # in its own room: no bulkhead between it and its x_m, nor in its bay
                if any(min(x, h["x_m"]) - R_l < w < max(x, h["x_m"]) + R_l for w in walls):
                    continue
                if clear(x, y):
                    pick = (lo, hi)
                    break
            if pick is None:
                raise SystemExit(f"berthdeck: no bay within {lt['max_shift_m']} m of the lantern {h['name']}'s x_m "
                                 "is clear of the carlings and the openings over it")
            lo, hi = pick
            c, z_low = self.lantern(part, [x, y, float(self.zsu(x))], sz)
            # its dish about level with the beams' underside: a man who clears the beams clears the lantern
            if z_low < float(self.zsu(x)) - bm - lt["dish_under_beams_in"] * IN:
                raise SystemExit(f"berthdeck: the lantern {h['name']}'s dish hangs more than {lt['dish_under_beams_in']} "
                                 "in under the beams' underside")
            shadows = bool(h.get("cast_shadows", h["zone"] in lt["shadowed_zones"]))
            radius = li["radius_m"] if shadows else min(li["radius_m"], min(abs(float(c[0]) - xb) for xb in bounds) - 0.05)
            nm = "Lantern_" + h["name"]
            light(nm, c, h["zone"], radius, shadows)
            placed.append({"name": nm, "x_m": round(x, 3), "y_m": y, "bay_m": [round(lo, 3), round(hi, 3)],
                           "bottom_over_deck_m": round(float(z_low - self.zg(x)), 3),
                           "beams_underside_over_deck_m": round(float(self.zsu(x) - bm - self.zg(x)), 3),
                           "radius_m": round(radius, 3), "cast_shadows": shadows})
        # the wardroom's: a bar across between the skylight's carlings over the table's middle
        cs_ = self.c["overhead"]["carling_in"][0] * IN
        x_t = self.c["wardroom"]["table"]["x_m"]
        ys = [cr["y_m"] for cr in self.overhead_info["carlings"] if cr["x_m"][0] + 0.05 < x_t < cr["x_m"][1] - 0.05]
        yp, yq = [y_ for y_ in ys if y_ > 0], [y_ for y_ in ys if y_ < 0]
        if not yp or not yq:
            raise SystemExit("berthdeck: no carlings either side of the wardroom's table to hang its lantern from")
        yi = min(min(yp), -max(yq)) - cs_ / 2
        bs_, bm_ = (v * IN for v in glt["cabin_bar_in"])
        zt = float(self.zsu(x_t)) - glt["cabin_bar_under_in"] * IN
        vbox(bar_part, [x_t - bs_ / 2, -yi, zt - bm_], [x_t + bs_ / 2, yi, zt], "Oak")
        c, z_low = self.lantern(part, [x_t, 0.0, zt - bm_])
        light("Lantern_Wardroom", c, "wardroom", lw["radius_m"], lw["cast_shadows"])
        top = float(self.zg(x_t)) + self.c["wardroom"]["table"]["high_in"] * IN
        placed.append({"name": "Lantern_Wardroom", "x_m": round(x_t, 3), "y_m": 0.0,
                       "bar_between_y_m": [round(-yi, 3), round(yi, 3)],
                       "bottom_over_table_m": round(float(z_low - top), 3), "radius_m": lw["radius_m"],
                       "cast_shadows": lw["cast_shadows"]})
        if len(self.lights) > lt["light_budget"]["max_lights"]:
            raise SystemExit(f"berthdeck: {len(self.lights)} lights over the berth deck's budget of "
                             f"{lt['light_budget']['max_lights']}")
        self.lantern_at = [(p["x_m"], p["y_m"]) for p in placed]
        self.info["lanterns"] = placed

    # --- the crew's berthing and messes ---------------------------------------------------------------------------------
    def crew_deck(self):
        """the crew's deck along the ship: from the officers' rooms' fore wall (or berthing from_x_m) to the sick bay's
        after bulkhead (or to_x_m), each a few centimetres clear"""
        bc, X = self.c["berthing"], self.room_x
        x_lo = X["officers_rooms"][-1] + self.c["officers_rooms"]["wall_in"] / 2 * IN
        x_hi = X["sick_bay_aft"] - self.c["sick_bay"]["bulkhead_in"] / 2 * IN
        if bc.get("from_x_m") is not None:
            x_lo = max(x_lo, bc["from_x_m"])
        if bc.get("to_x_m") is not None:
            x_hi = min(x_hi, bc["to_x_m"])
        x_lo, x_hi = x_lo + 0.05, x_hi - 0.05
        return x_lo, x_hi

    def obstacles(self, fp):
        """what stands up from the deck to the gun deck's beams over the crew's deck, in plan [(name, outline)]: the
        fittings' footprints but the gratings (hammocks hang over those), the stanchions, the lanterns, and the gun
        deck's ladders that land here (top to foot, their width)"""
        out = [(k, v) for k, v in fp.items() if not (k in self.items and self.items[k]["kind"] == "grating")]
        r = self.c["overhead"]["stanchion_in"] / 2 * IN + 1.5 * IN
        out += [("Stanchion_%.3f" % x, circle(r, 16) + [x, 0.0]) for x in self.info["stanchions_x_m"]]
        out += [("Lantern_%.3f_%.3f" % (x, y), circle(self.lantern_r(), 12) + [x, y]) for x, y in self.lantern_at]
        lg = self.gd.c["ladders"]
        w = (lg["width_in"] + 2 * lg["stringer_in"][1]) * IN
        for li in self.gd.ladder_info:
            if li["from"] == "Companion":
                continue
            a, b = sorted((li["top_x_m"], li["foot_x_m"]))
            out.append(("Ladder_" + li["from"], rect2(0.5 * (a + b), 0.0, b - a, w)))
        return out

    @staticmethod
    def outline_of(item, n=25):
        """an item's plan outline in its own frame: at n stations along X its widest |y| either side and the z there
        (stations (n,), half-widths (n,), z (n,)): the outline [(x, y)] round it"""
        V = np.concatenate([np.concatenate(p.V) for p in item.pieces.values() if p.V])
        xs = np.linspace(V[:, 0].min(), V[:, 0].max(), n)
        h = np.zeros(n)
        zz = np.zeros(n)
        edges = np.concatenate([[xs[0] - 1e-6], 0.5 * (xs[1:] + xs[:-1]), [xs[-1] + 1e-6]])
        for i in range(n):
            sel = (V[:, 0] >= edges[i]) & (V[:, 0] <= edges[i + 1])
            if sel.any():
                j = np.argmax(np.abs(V[sel, 1]))
                h[i], zz[i] = abs(V[sel, 1][j]), V[sel, 2][j]
            elif i:
                h[i], zz[i] = h[i - 1], zz[i - 1]
        return xs, h, zz

    @staticmethod
    def clear_of(P, obs, gap):
        """the first obstacle (name) the plan outline P comes within gap of, or None"""
        for name, O in obs:
            if in_poly(P, O).any() or in_poly(O, P).any():
                return name
            if min(seg_dist(P, O).min(), seg_dist(O, P).min()) < gap:
                return name
        return None

    def knee_under_z(self, xb, y):
        """how high the hanging knee under the beam at xb comes down at |y|: its inner face's z there (the throat's
        curve between its head and its foot; the foot's z outboard of the foot), the lower of its two side faces;
        +inf inboard of its head or where the beam has no knee"""
        kp = self.knee_inner.get(round(xb, 4))
        if kp is None:
            return np.inf
        y = abs(float(y))
        out = np.inf
        for U in kp:
            if y < U[-1, 0]:
                continue
            out = min(out, float(U[0, 1]) if y >= U[0, 0] else float(np.interp(y, U[::-1, 0], U[::-1, 1])))
        return out

    def side_limit(self, x, z):
        """how far out from the middle line anything may come at x, z: the clamp's inner face in the clamp's band
        (from its foot to the beams), the ceiling's under it: (|y| limits, found)"""
        P, N, ok = self.wall_at(x, z, strict=False)
        Xc, Zb, Zt = self.clamp
        th = self.c["overhead"]["clamp_in"][1] * IN
        band = (z > np.interp(x, Xc, Zb) - 0.01) & (z < np.interp(x, Xc, Zt) + 0.01)
        return np.abs(P[:, 1] + np.where(band, N[:, 1] * th, 0.0)), ok

    def berthing(self, fp):
        """the crew's hammocks slung (pose collection BerthDeck_Hammocks, the stores kit's hammock at this deck's span)
        fore and aft between two hooks under the gun deck's beams two apart (hook_span_beams), each hook beside the
        beam's hanging knee (off the beam's middle by half the knee's breadth, half the hook's plate and a centimetre, so
        it can go out under the knee's arm, and the two hammocks that meet under a beam each have their own), in rows
        spacing_in apart across from the middle line (the two inner rows' bodies middle_clear_in apart across it),
        alternate rows a beam along and port's a beam along from starboard's (heads and tails staggered): over the crew's
        deck (crew_deck), and aft of it to the steerage's bulkhead in the rows that pass inboard of the officers' rooms'
        walls. Each where both its beams run over its row (not cut for
        an opening above), its hooks inboard of the clamp, its body under the middle beam's knee (clear_m) and
        side_clear_m in from the clamp and the ceiling, and its outline clear_m clear of everything standing up from the
        deck (obstacles). The hooks are permanent (BerthDeck)"""
        bc = self.c["berthing"]
        x_lo, x_hi = self.crew_deck()
        orr, sg = self.c["officers_rooms"], self.c["steerage"]
        x_aft = self.room_x["steerage"] + sg["bulkhead_in"] / 2 * IN + 0.05
        y_rooms = orr["wall_y_m"] - orr["wall_in"] / 2 * IN
        hk = self.hook_item()
        bx, _, bz = hk.attach["bight"]
        pl, pw, _ = (v * IN for v in self.kit().c["hammock"]["hook"]["plate_in"])
        sd = self.c["overhead"]["knee"]["sided_in"] * IN
        dl = sd / 2 + pl / 2 + 0.01
        beams = [m for m in self.members if m[3] == "beam"]
        bxs = np.array([m[0] for m in beams])
        sp = float(np.median(np.diff(bxs)))
        if np.abs(np.diff(bxs) - sp).max() > 0.01:
            raise SystemExit("berthdeck: the gun deck's beams are not evenly spaced: one hammock will not fit them all")
        nb = bc["hook_span_beams"]
        span = nb * sp - 2 * dl - 2 * bx
        it = self.kit().hammock_slung(span_ft=span / FT)
        self.copy_items["BerthHammock"] = it
        xs_o, hw_o, z_o = self.outline_of(it)
        spans = {round(m["x_m"], 4): m["spans_y_m"] for m in self.overhead_info["members"]}
        obs = self.obstacles(fp)
        gap = bc["clear_m"]
        sc = bc["side_clear_m"]
        y0 = float(hw_o.max()) + bc["middle_clear_in"] / 2 * IN     # the inner rows' bodies middle_clear_in apart
        dy = bc["spacing_in"] * IN
        placed, why = [], {}
        k_hook = 0
        aft_of_rooms = 0
        for k in range(200):
            y = y0 + k * dy
            if y > 7.0:
                break
            xl = x_aft if y + hw_o.max() + gap < y_rooms else x_lo
            for sy in (1.0, -1.0):
                yr = sy * y
                # alternate rows a beam along, and port's a beam along from starboard's: heads and tails staggered
                # across the middle line too
                for g in range((k + (sy < 0)) % 2, len(beams) - nb, 2):
                    ma, mb = beams[g], beams[g + nb]
                    if not (xl + dl + pl < ma[0] and mb[0] < x_hi - dl - pl):
                        continue
                    mids = beams[g + 1:g + nb]
                    xa, xb = ma[0] + dl, mb[0] - dl
                    tag = None
                    for m in (ma, mb):
                        if not any(a + pw < yr < b - pw for a, b in spans[round(m[0], 4)]):
                            tag = "beam cut"
                    za, zb_ = self.beam_bottom(xa), self.beam_bottom(xb)
                    if tag is None:
                        # the hooks' plates inboard of the clamp under the beam
                        lim, ok = self.side_limit(np.array([xa, xb]), np.array([za, zb_]) - 0.02)
                        if not ok.all() or y + pw / 2 > lim.min() - 0.02:
                            tag = "hook at the clamp"
                    pa = np.array([xa + bx, yr, za + bz])
                    pb = np.array([xb - bx, yr, zb_ + bz])
                    o = 0.5 * (pa + pb)
                    ex = (pb - pa) / np.linalg.norm(pb - pa)
                    ez = np.array([-ex[2], 0.0, ex[0]])
                    R = np.column_stack([ex, np.cross(ez, ex), ez])
                    if tag is None:
                        # its body under the knees of the beams between its hooks, over their breadth
                        for m in mids:
                            for dxk in (-sd / 2, 0.0, sd / 2):
                                xr = m[0] + dxk - o[0]
                                ye = y + float(np.interp(xr, xs_o, hw_o))
                                ze = o[2] + float(np.interp(xr, xs_o, z_o))
                                if ze + gap > self.knee_under_z(m[0], ye):
                                    tag = "body by a knee"
                    if tag is None:
                        # the body's outline from the side at its own heights, clear of the clamp and the ceiling
                        Q = (R @ np.column_stack([xs_o, sy * hw_o, z_o]).T).T + o
                        lim, ok = self.side_limit(Q[:, 0], Q[:, 2])
                        if not ok.all() or np.any(np.abs(Q[:, 1]) > lim - sc):
                            tag = "side"
                    if tag is None:
                        P = np.concatenate([np.column_stack([xs_o, hw_o]), np.column_stack([xs_o, -hw_o])[::-1]])
                        P = (R[:2, :2] @ P.T).T + o[:2]
                        hit = self.clear_of(P, obs, gap)
                        if hit:
                            tag = "by " + hit.split("_")[0]
                    if tag:
                        why[tag] = why.get(tag, 0) + 1
                        continue
                    n = len(placed)
                    self.add_copy(f"Hammock_{n:03d}", "BerthHammock", o, R, "BerthDeck_Hammocks")
                    for xh, zh, turn in ((xa, za, False), (xb, zb_, True)):
                        Rh = np.diag([-1.0, -1.0, 1.0]) if turn else np.eye(3)
                        self.add_copy(f"HammockHook_{k_hook:03d}", "HammockHook", np.array([xh, yr, zh + SEAT]), Rh,
                                      "BerthDeck")
                        k_hook += 1
                    placed.append([round(float(o[0]), 3), round(yr, 3)])
                    aft_of_rooms += int(xa < x_lo)
        rows = sorted({p[1] for p in placed})
        lows = [float((np.asarray(c["matrix"])[:3, :3] @ np.array([0.0, 0.0, it.info["lowest_m"]]))[2]
                      + np.asarray(c["matrix"])[2, 3] - self.zg(np.asarray(c["matrix"])[0, 3]))
                for c in self.copies_ if c["item"] == "BerthHammock"]
        self.info["berthing"] = {"hammocks": len(placed), "hooks": k_hook, "span_m": round(span, 4),
                                 "hook_off_beam_m": round(dl, 4), "rows_y_m": rows,
                                 "crew_deck_x_m": [round(x_lo, 3), round(x_hi, 3)],
                                 "between_officers_rooms": aft_of_rooms, "left_out": why,
                                 "lowest_over_deck_m": round(min(lows), 3) if lows else None}

    def messes(self, fp):
        """the crew's messes by day (pose collection BerthDeck_Messes): under every other beam along the crew's deck a
        mess table each side (the stores kit's, its slings run to this deck's beams sling_off_beam_in either side of the
        beam's middle), hinged to its cleat on the side, a bench either side of it bench_off_table_in off, a mess kid on
        it; and a sea chest against the side (chest_off_side_in off it, its foot clear of the waterway's cove) at each
        beam between, each where it stands clear of what stands on the deck"""
        mc = self.c["messes"]
        x_lo, x_hi = self.crew_deck()
        zgap = float(self.zsu(0.0) - self.zg(0.0)) - self.c["overhead"]["beam_in"][1] * IN
        kit = self.kit()
        tab = kit.mess_table(sling_m=zgap, sling_y_m=mc["sling_off_beam_in"] * IN)
        ben, kid, chest = kit.mess_bench(), kit.mess_kid(), kit.sea_chest()
        Vch = np.asarray(chest.merged().arrays()[0], float)   # the chest's points in its own frame (front +Y)
        self.copy_items.update({"BerthMessTable": tab, "MessBench": ben, "MessKid": kid, "SeaChest": chest})
        tc = kit.c["mess"]["table"]
        L, W = (v * IN for v in tc["size_in"])
        bW = kit.c["mess"]["bench"]["size_in"][1] * IN
        off = W / 2 + mc["bench_off_table_in"] * IN + bW / 2
        side = np.array(tab.attach["side"])
        cmin, cmax = tab.box()
        nmin, nmax = ben.box()
        beams = [m[0] for m in self.members if m[3] == "beam" and x_lo + off + bW < m[0] < x_hi - off - bW]
        obs = self.obstacles(fp)
        tables, chests, skipped = [], [], []
        for j, xb in enumerate(beams):
            for sy in (1.0, -1.0):
                Rz = np.array([[0.0, -sy, 0.0], [sy, 0.0, 0.0], [0.0, 0.0, 1.0]])       # item +X to the side
                zg0 = float(self.zg(xb))
                if j % mc["every_beams"] == 0:
                    # the cleat's face against the side's inner face, the nearest it comes over the cleat's height
                    zc = zg0 + np.array([cmin[2], side[2], side[2] + 0.06])
                    xc = xb + np.array([-W / 2 - 2.0 * IN, 0.0, W / 2 + 2.0 * IN])
                    XX, ZZ = np.meshgrid(xc, zc)
                    ys = self.wall_at(XX.ravel(), ZZ.ravel())[0][:, 1]
                    yo = sy * (float(ys.min()) - 0.002 - side[0])
                    o = np.array([xb, yo, zg0])
                    P = (Rz[:2, :2] @ np.array([[cmin[0], cmin[1]], [cmax[0], cmin[1]], [cmax[0], cmax[1]],
                                                [cmin[0], cmax[1]]]).T).T + o[:2]
                    hit = self.clear_of(P, obs, 0.1)
                    for sx in (-1.0, 1.0):                  # and its benches
                        if not hit:
                            Pb = (Rz[:2, :2] @ np.array([[nmin[0], nmin[1]], [nmax[0], nmin[1]], [nmax[0], nmax[1]],
                                                         [nmin[0], nmax[1]]]).T).T + [xb + sx * off, yo]
                            hit = self.clear_of(Pb, obs, 0.1)
                    if hit:
                        skipped.append([round(xb, 3), sy, hit])
                        continue
                    self.add_copy(f"MessTable_{len(tables):02d}", "BerthMessTable", o, Rz, "BerthDeck_Messes")
                    kz = tab.info["top_m"]
                    self.add_copy(f"MessKid_{len(tables):02d}", "MessKid", o + Rz @ np.array([0.0, 0.0, kz - SEAT]), Rz,
                                  "BerthDeck_Messes")
                    for sx in (-1.0, 1.0):
                        xbn = xb + sx * off
                        s_ = float((self.zg(xbn + 0.05) - self.zg(xbn - 0.05)) / 0.1)
                        th = math.atan(s_)
                        Ry = np.array([[math.cos(th), 0.0, -math.sin(th)], [0.0, 1.0, 0.0], [math.sin(th), 0.0, math.cos(th)]])
                        self.add_copy(f"MessBench_{len(tables):02d}_{'AF'[sx > 0]}", "MessBench",
                                      np.array([xbn, yo, float(self.zg(xbn)) - SEAT]), Ry @ Rz, "BerthDeck_Messes")
                    tables.append([round(xb, 3), round(float(yo + sy * L / 2), 3)])
                else:
                    # the chest: its length fore and aft, its front inboard, its back chest_off_side_in off the side
                    Rc = np.diag([-1.0, -1.0, 1.0]) if sy > 0 else np.eye(3)
                    bmin, bmax = chest.box()
                    zc = zg0 + np.array([0.0, 0.5 * bmax[2], bmax[2]])
                    xc = xb + np.array([bmin[0], 0.0, bmax[0]])
                    XX, ZZ = np.meshgrid(xc, zc)
                    ys = self.wall_at(XX.ravel(), ZZ.ravel())[0][:, 1]
                    back = -bmin[1]                         # its back's reach behind its frame's origin
                    y_back = float(ys.min()) - mc["chest_off_side_in"] * IN
                    # and its foot clear of the waterway's cove, which stands out from the side along the deck: at
                    # each point of the cove across at the chest's ends and middle, the chest's back as far as it
                    # reaches at that height or under it a tenth of an inch inboard of it
                    for xq in xc:
                        for yq, zq in self.waterway_cut(xq):
                            low = Vch[:, 2] <= zq - zg0 + 1e-6
                            if low.any():
                                y_back = min(y_back, yq - 0.1 * IN - (float(-Vch[low, 1].min()) - back))
                    yo = sy * (y_back - back)
                    o = np.array([xb, yo, zg0])
                    P = rect2(xb, yo, bmax[0] - bmin[0], bmax[1] - bmin[1])
                    hit = self.clear_of(P, obs, 0.1)
                    if hit:
                        skipped.append([round(xb, 3), sy, hit])
                        continue
                    s_ = float((self.zg(xb + 0.05) - self.zg(xb - 0.05)) / 0.1)
                    th = math.atan(s_)
                    Ry = np.array([[math.cos(th), 0.0, -math.sin(th)], [0.0, 1.0, 0.0], [math.sin(th), 0.0, math.cos(th)]])
                    self.add_copy(f"SeaChest_{len(chests):02d}", "SeaChest", o - EZ * SEAT, Ry @ Rc, "BerthDeck_Messes")
                    chests.append([round(xb, 3), round(float(yo), 3)])
        self.info["messes"] = {"tables": len(tables), "men": len(tables) * tab.info["seats"], "chests": len(chests),
                               "tables_at": tables, "left_out": skipped, "sling_m": round(zgap, 4)}

    # --- the room between the fittings ----------------------------------------------------------------------------------
    def footprints(self):
        """every fitting's plan outline on this deck (name -> (n, 2)): the openings' coamings, the capstan's step, the
        bitts' posts, the pumps' tubes, the cable scuttles' collars, the masts' wedges, and the room kept clear (ladders
        clear_m) beyond the feet of the gun deck's ladders that land here and before the tops of this deck's own"""
        fp = {}
        for k, v in self.items.items():
            fp[k] = rect2(v["x"], v["y"], v["Lo"], v["Wo"])
        th = self.c["through"]
        sl, sw, _ = (v * IN for v in th["step_in"])
        fp["CapstanStep"] = rect2(self.x_capstan, 0.0, sl, sw)
        bt = self.gd.c["bitts"]
        p = bt["post_in"] * IN
        for sy, sd in ((1.0, "S"), (-1.0, "P")):
            fp["BittPost_" + sd] = rect2(bt["x_m"], sy * bt["y_in"] * IN, p, p)
        for name, (x, y), kind, h in self.pump_tubes():
            fp[name] = rect2(x, y, 2 * h, 2 * h) if kind == "square" else circle(h, 16) + [x, y]
        xs, ys = self.scuttles()
        r = (th["scuttle_in"] / 2 + th["collar_in"][0]) * IN
        for sy, sd in ((1.0, "S"), (-1.0, "P")):
            fp["CableScuttle_" + sd] = circle(r, 16) + [xs, sy * ys]
        g = self.c["deck"]["mast_hole_gap_in"] * IN
        for name in ("fore", "main", "mizzen"):
            pt, R, _ = self.mast_at(name, float(self.zg(self.mast_x(name))))
            fp["Mast_" + name] = circle(R + g + 1.25 * IN, 24) + pt[:2]
        cl = self.c["ladders"]["clear_m"]
        lg = self.gd.c["ladders"]
        w = (lg["width_in"] + 2 * lg["stringer_in"][1]) * IN
        for li in self.gd.ladder_info:
            if li["from"] == "Companion":                  # the companion's ladder lands on the gun deck
                continue
            d = 1.0 if li["foot_x_m"] > li["top_x_m"] else -1.0
            fp["LadderFoot_" + li["from"]] = rect2(li["foot_x_m"] + d * cl / 2, 0.0, cl, w)
        lc = self.c["ladders"]
        w = (lc["width_in"] + 2 * lc["stringer_in"][1]) * IN
        for k, v in self.items.items():
            if v["kind"] != "ladder":
                continue
            d = 1.0 if v["goes"] == "forward" else -1.0
            xe = v["x"] - d * v["Lo"] / 2
            fp["LadderTop_" + k] = rect2(xe - d * cl / 2, v["y"], cl, w)
        if getattr(self, "table_box", None) is not None:
            a, b, ye = self.table_box
            fp["WardroomTable"] = rect2(0.5 * (a + b), 0.0, b - a, 2 * ye)
        if getattr(self, "chest_box", None) is not None:
            x0, x1, y0, y1 = self.chest_box
            fp["SickBayChest"] = rect2(0.5 * (x0 + x1), 0.5 * (y0 + y1), x1 - x0, y1 - y0)
        return fp

    def layout_check(self, fp, gap=0.15):
        """GunDeck.layout_check less the pairs that meet by design: two rooms kept clear (where one ladder's foot is the
        next one's top) and an opening with the room before its own ladder's top"""
        room = lambda n: n.startswith(("LadderFoot_", "LadderTop_"))     # noqa: E731
        return [c for c in GunDeck.layout_check(self, fp, gap)
                if not (room(c[0]) and room(c[1])) and "LadderTop_" + c[0] != c[1] and "LadderTop_" + c[1] != c[0]]

    # --- the hand-over to the orlop slice --------------------------------------------------------------------------------
    def handover(self):
        """berth_deck.json, the orlop slice's (14) hand-over, from this deck as built: its line every 0.25 m between its
        beams' ends and the side's inside at its top, its own beams' and ledges' stations and sizes (the orlop slice
        builds them), the openings through it and the ladders down to the orlop's top, the gun deck's openings that end
        on it and its ladders that land there, the masts, pumps and cable scuttles where they pass it, and the gun deck's
        beams over it; the notes are the card's (handover)"""
        c, gd = self.c, self.gd
        h, oh, op, lc = c["handover"], c["overhead"], c["openings"], c["ladders"]
        r = lambda v, n=4: round(float(v), n)          # noqa: E731
        plank = c["deck"]["thick_in"] * IN
        xa, xf = self.beam_ends
        XS = np.round(np.arange(math.floor(xa * 4) / 4, math.ceil(xf * 4) / 4 + 1e-9, 0.25), 3)
        G = self.gun
        if XS[0] < G[0, 0] or XS[-1] > G[-1, 0]:
            raise SystemExit("berthdeck: the hand-over's deck line runs past the side's inside at the deck's top")
        half = np.interp(XS, G[:, 0], G[:, 1])
        st = self.stations()
        overs = {o["name"]: o for o in op["items"]}
        opens = []
        for k, v in sorted(self.items.items(), key=lambda kv: kv[1]["x"]):
            o = overs[k]
            e = {"name": k, "x_m": r(v["x"]), "y_m": r(v["y"]), "inside_m": [r(v["L"]), r(v["W"])],
                 "with_coaming_m": [r(v["Lo"]), r(v["Wo"])], "inside_x_m": [r(v["x"] - v["L"] / 2), r(v["x"] + v["L"] / 2)],
                 "inside_y_m": [r(v["y"] - v["W"] / 2), r(v["y"] + v["W"] / 2)],
                 "gun_deck_kind": gd.items[o["over"]]["kind"] if "over" in o else None,
                 "ladder_down_to_orlop": v["kind"] == "ladder"}
            if "note" in o:
                e["note"] = o["note"]
            opens.append(e)
        stop = sorted(k for k in gd.items if k not in {o.get("over") for o in op["items"]})
        sd, ts = (v * IN for v in lc["stringer_in"])
        fh = sd / 2 / math.sin(math.radians(lc["angle_deg"]))     # half the stringers' foot along the deck
        ho = lc["width_in"] / 2 * IN + ts                           # half the ladder's width outside its stringers
        cl = lc["clear_m"]
        lads = []
        for li in self.ladder_info:
            x, y = li["foot_x_m"], li["y_m"]
            lo, hi = (x - fh, x + cl + fh) if li["goes"] == "forward" else (x - cl - fh, x + fh)
            lads.append(dict(li, between_stringers_in=lc["width_in"],
                             outside_stringers_in=lc["width_in"] + 2 * lc["stringer_in"][1], angle_deg=lc["angle_deg"],
                             foot_stringers_x_m=[r(x - fh, 3), r(x + fh, 3)],
                             keep_clear_m={"x": [r(lo, 3), r(hi, 3)], "y": [r(y - ho, 3), r(y + ho, 3)]}))
        land = [{"from": li["from"], "top_x_m": li["top_x_m"], "foot_x_m": li["foot_x_m"], "y_m": 0.0,
                 "goes": "forward" if li["foot_x_m"] > li["top_x_m"] else "aft", "note": h["gun_deck_ladders_note"]}
                for li in gd.ladder_info if li["from"] in stop]
        if sorted(li["from"] for li in land) != sorted(k for k in stop if gd.items[k]["kind"] == "ladder"):
            raise SystemExit("berthdeck: a gun deck ladderway that stops at this deck has no ladder landing on it")
        g = c["deck"]["mast_hole_gap_in"] * IN
        masts = {}
        for name in ("fore", "main", "mizzen"):
            pt, _, R, u = self.mast_hole(name)
            pu, Ru, _ = self.mast_at(name, float(self.zg(pt[0])) - plank - oh["berth_beam_moulded_in"] * IN)
            masts[name] = {"axis_at_top_m": np.round(np.asarray(pt, float), 4).tolist(), "radius_at_top_m": r(R),
                           "axis_at_beam_underside_m": np.round(np.asarray(pu, float), 4).tolist(),
                           "radius_at_beam_underside_m": r(Ru), "axis": np.round(np.asarray(u, float), 5).tolist(),
                           "hole_radius_m": r(R + g)}
        xs, ys = self.scuttles()
        bg = oh["beam_in"][1] * IN
        return {
            "about": h["about"], "sources": h["sources"],
            "deck": {"top_below_gun_deck_in": c["deck"]["top_below_gun_deck_in"], "flat_across": True,
                     "plank_in": c["deck"]["thick_in"], "line_note": h["line_note"],
                     "line": [[float(x), r(self.zg(x))] for x in XS], "ends_m": [r(xa, 3), r(xf, 3)],
                     "ends_note": h["ends_note"],
                     "half_breadth_inside_at_top_m": [[float(x), r(y, 3)] for x, y in zip(XS, half)]},
            "beams": {"sided_in": oh["berth_beam_sided_in"], "moulded_in": oh["berth_beam_moulded_in"],
                      "x_m": [r(x) for x, k in st if k == "beam"], "note": h["beams_note"]},
            "ledges": {"sided_in": oh["berth_ledge_in"][0], "moulded_in": oh["berth_ledge_in"][1],
                       "x_m": [r(x) for x, k in st if k == "ledge"], "note": h["ledges_note"]},
            "carlings": {"sided_in": oh["berth_carling_in"][0], "moulded_in": oh["berth_carling_in"][1],
                         "note": oh["berth_framing_note"]},
            "station_pitch_m": r(self.bp, 5),
            "openings": opens, "openings_note": h["openings_note"],
            "stop_at_berth_deck": stop, "stop_note": h["stop_note"],
            "ladders_down": lads, "ladders_note": h["ladders_note"],
            "gun_deck_ladders_land": land,
            "masts": masts, "masts_note": h["masts_note"],
            "pumps": {"chain_x_m": r(self.x_chain, 3), "brake_x_m": r(self.x_brake, 3),
                      "tubes": [{"name": n, "at_m": [r(x), r(y)], "kind": kind, "half_size_m": r(hs)}
                                for n, (x, y), kind, hs in self.pump_tubes()], "note": h["pumps_note"]},
            "cable_scuttles": {"at_m": [r(xs), r(ys)], "both_sides": True, "diam_in": c["through"]["scuttle_in"],
                               "half_breadth_inside_at_deck_m": r(np.interp(xs, G[:, 0], G[:, 1]), 3)},
            "cable_scuttles_note": h["cable_scuttles_note"],
            "ending_on_the_berth_deck": h["ending_on_the_berth_deck"],
            "who_builds_what": h["who_builds_what"],
            "gun_deck_beams": {"sided_in": oh["beam_in"][0], "moulded_in": oh["beam_in"][1],
                               "plank_in": gd.c["deck"]["thick_in"],
                               "underside": [[float(x), r(self.zsu(x) - bg)] for x in XS], "note": h["gun_deck_beams_note"]},
            "headroom_m": {"under_gun_deck_beams_amidships": r(self.zsu(0.0) - bg - self.zg(0.0), 3),
                           "between_beams_amidships": r(self.zsu(0.0) - self.zg(0.0), 3)},
            "midships_m": {"gun_deck_top": r(gd.zg(0.0)), "berth_deck_top": r(self.zg(0.0))}}

    # --- assembly -------------------------------------------------------------------------------------------------------
    def build(self):
        """every part (parts()): the deck, the side, the gun deck's framing over it, the openings and what comes down
        through the gun deck; then the stanchions where they stand clear, and the room between the fittings"""
        self.layout()
        names = ("BerthDeck", "BerthWaterways", "BerthCeiling", "BerthOverhead", "BerthClamps", "BerthChocks",
                 "BerthHangingKnees", "BerthLodgingKnees", "BerthStanchions", "BerthHatchways", "BerthWells", "BerthLadders",
                 "BerthMastWedges", "BerthSpindle", "BerthBittPosts", "BerthPumpTubes", "BerthCableScuttles",
                 "BerthRooms", "BerthWardroom", "BerthSickBay", "BerthLanterns")
        P = {n: Part() for n in names}
        self.surface(P["BerthDeck"])
        self.waterways(P["BerthWaterways"])
        self.overhead(P["BerthOverhead"])
        self.clamps(P["BerthClamps"])
        self.knees(P["BerthHangingKnees"])
        self.ceiling(P["BerthCeiling"])
        self.chocks(P["BerthChocks"])
        self.lodging_knees(P["BerthLodgingKnees"])
        self.hatchways(P["BerthHatchways"], P["BerthWells"], P["BerthLadders"])
        self.mast_wedges(P["BerthMastWedges"])
        self.spindle(P["BerthSpindle"])
        self.bitt_posts(P["BerthBittPosts"])
        self.pump_trees(P["BerthPumpTubes"])
        self.cable_scuttles(P["BerthCableScuttles"], P["BerthWells"])
        self.parts_ = P
        self.rooms(P["BerthRooms"])
        self.wardroom_furniture(P["BerthWardroom"])
        hooks = []
        self.sick_bay(P["BerthSickBay"], hooks)
        for k, (item, o, R) in enumerate(hooks):
            self.add_copy(f"BerthCotHook_{k:02d}", "HammockHook", o, R, "BerthDeck")
        self.lanterns(P["BerthLanterns"], P["BerthOverhead"])
        fp = self.footprints()
        self.stanchions(P["BerthStanchions"], fp)
        self.info["layout_close"] = self.layout_check(fp)
        self.berthing(fp)
        self.messes(fp)
        return self
