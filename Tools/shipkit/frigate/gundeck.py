"""The frigate's gun deck (docs/shipkit-12): the planked deck under the long guns and the spar deck's framing over it,
the hatchways with their coamings, gratings, wells and ladders, the gun deck's capstan, the pumps, the riding bitts,
the galley, the bow's manger and cable scuttles, the captain's great cabin aft (its bulkhead, state rooms, the after
wall with the stern windows opened through it, the window seat over the rudder's head, the floor cloth and furniture),
the lanterns (and their lights, as game data) and the guns' own gear that hangs and lies about the deck.

    from gundeck import GunDeck;  gd = GunDeck(sk, rig, dk, skin_parts).build();  gd.parts()

Sizes and places are gundeck_1797.json's, each with its source: the 1849 gun deck plan (registered to our masts at this
deck), the spar deck's own fittings over it (deck_1797.json), or the period's practice. Units: metres in the ship
frame (X forward, Y starboard, Z up, origin on the centreline at midships on waterline A).

The deck is flat across, its top on the skin's g_G row (the line 24 in under the port sills, faired between
specs_1795.json's gun_deck_fair_m), one surface cut round the hatchways (their coamings' outsides), the masts, the
capstan's barrel and the cable scuttles (Blender's constrained Delaunay triangulation, so this module runs in Blender's
Python), carrying the 'Planking' and 'Margin' UVs the material draws its planks from (build_frigate.py's
GunDeckPlanks), with its underside a plank's thickness below. Over it the spar deck's beams and ledges (the waist's beams
are deck.py's, made again here with their ends cut to the side), cut round the spar deck's openings onto carlings and
head ledges, their ends on a clamp along each side held by hanging knees between the ports, and stanchions on the
middle line.

The capstan's head turns on a frame of its own (origin on its axis at the deck, Z up), with the spar deck's capstan;
everything else is built in place. The great cabin's after wall replaces the skin's placeholder there, and the
transom is cut for the stern windows (holed_transom), so daylight comes in through them and through the cabin's side
lights (a port with no lid, cut by skin.py) as it does through the open gun ports.
"""
import json
import math
import os

import numpy as np

import loft
from deck import Part, solid, vbox, bar, lathe, revolve, in_poly, seg_dist, densify, rect2, cdt, newell
from rigging import tube
from spars import box, circle, ring_band, clip_convex, unit

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)
GLASS_BACK_M = -0.005          # stern.Stern.windows lays the stern windows' glass, sash and casings from 5 mm inside the face


# ---- mesh pieces -------------------------------------------------------------------------------------------------------
def prism(part, poly, x0, x1, mat, axis=0):
    """a straight prism: the simple polygon poly (n, 2) in the plane square to axis (axis 0: poly is (y, z) and the
    prism runs along x from x0 to x1; axis 1: (x, z) along y; axis 2: (x, y) along z), its ends ear-clipped, every face
    pointing out"""
    P = np.asarray(poly, float)
    a2 = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    if a2 < 0:
        P = P[::-1]
    n = len(P)
    other = [k for k in range(3) if k != axis]

    def lift(Q, v):
        out = np.zeros((len(Q), 3))
        out[:, other[0]], out[:, other[1]], out[:, axis] = Q[:, 0], Q[:, 1], v
        return out
    V = np.concatenate([lift(P, x0), lift(P, x1)])
    tri = loft.ear_clip(P)
    F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    F += [tuple(t[::-1]) for t in tri] + [tuple(n + i for i in t) for t in tri]
    # turn the whole set so its first side face points away from the polygon's middle
    c = lift(P.mean(0)[None], 0.5 * (x0 + x1))[0]
    f0 = F[0]
    nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
    if nrm @ (0.5 * (V[f0[0]] + V[f0[2]]) - c) < 0:
        F = [f[::-1] for f in F]
    part.add(V, F, mat)


def prism2(part, P0, P1, x0, x1, mat):
    """a prism along x from the simple (y, z) polygon P0 at x0 to P1 at x1 (the same count, point for point): its sides
    quads between the two, each end ear-clipped on its own outline, every face pointing out"""
    P0, P1 = np.asarray(P0, float), np.asarray(P1, float)

    def area(P):
        return 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    if area(P0) < 0:
        P0, P1 = P0[::-1], P1[::-1]
    if area(P1) <= 0:
        raise SystemExit("gundeck: prism2's two outlines turn opposite ways")
    n = len(P0)
    V = np.concatenate([np.column_stack([np.full(n, x0), P0]), np.column_stack([np.full(n, x1), P1])])
    F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    F += [tuple(t[::-1]) for t in loft.ear_clip(P0)] + [tuple(n + i for i in t) for t in loft.ear_clip(P1)]
    c = np.concatenate([[0.5 * (x0 + x1)], 0.5 * (P0.mean(0) + P1.mean(0))])
    f0 = F[0]
    nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
    if nrm @ (0.5 * (V[f0[0]] + V[f0[2]]) - c) < 0:
        F = [f[::-1] for f in F]
    part.add(V, F, mat)


def disc(part, c, nrm, r, mat, n=16):
    """a flat disc facing along nrm"""
    nrm = unit(np.asarray(nrm, float))
    a = unit(np.cross(nrm, EZ if abs(nrm[2]) < 0.9 else EX))
    b = np.cross(nrm, a)
    th = np.arange(n) * 2 * math.pi / n
    V = np.asarray(c, float) + r * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b)
    F = [tuple(range(n))]
    if newell(V) @ nrm < 0:
        F = [tuple(reversed(range(n)))]
    part.add(V, F, mat)


def quad(part, P, want, mat):
    """one quad P (4, 3), turned to face along want"""
    P = np.asarray(P, float)
    F = [(0, 1, 2, 3)]
    if np.cross(P[1] - P[0], P[3] - P[0]) @ np.asarray(want, float) < 0:
        F = [(3, 2, 1, 0)]
    part.add(P, F, mat)


def bolt_head(part, P, n, d, mat="Iron", seg=8):
    """a round bolt head (or rivet) d across on a face at P, facing along n, its shank let a quarter inch into the face"""
    n = unit(np.asarray(n, float))
    lathe(part, np.asarray(P, float) - n * 0.25 * IN, n, np.cross(n, EZ) if abs(n[2]) < 0.9 else EX,
          [(0.0, d / 2), (0.25 * IN, d / 2), (0.25 * IN + 0.2 * d, 0.4 * d), (0.25 * IN + 0.35 * d, 0.15 * d)], mat, seg)


class GunDeck:
    # the parts that carry UVs (parts()): the deck's 'Planking' and 'Margin', the floor cloth's 'Cloth' (squares)
    UV_PARTS = {"GunDeck": ("Planking", "Margin"), "FloorCloth": ("Cloth",)}

    """The gun deck and its fittings for the skin sk (skin.Skin, built), the rig (spars.Rig, built), the spar deck dk
    (deck.Deck, built) and the skin's parts (skin.Skin.parts(): the rudder's head stands up through the deck aft)."""

    def __init__(self, sk, rig, dk, skin_parts, path=os.path.join(HERE, "gundeck_1797.json"), hawse_x=None):
        import skin as SKM
        self.sk, self.rig, self.dk, self.SKM = sk, rig, dk, SKM
        self.skin_parts = skin_parts
        self.hawse_x = hawse_x                             # the hawse holes' linings' aftmost point (anchors.py), or None
        self.c = json.load(open(path))
        self.decor = json.load(open(os.path.join(HERE, "decor_1797.json")))
        import stern
        self.face = stern.Face(sk.L)
        self.cloth_t = 0.0
        if not hasattr(sk, "pos"):
            sk.positions()
        self.L = sk.L
        self.pr = sk.pr
        self.k = self.L.ppf_y / FT                         # px per m, heights and half-breadths

        def row(name):
            P, _, _ = sk.row_points(name)
            return P[np.argsort(P[:, 0])]
        self.rows = {n: row(n) for n in ("g_G", "g_GS", "g_S", "g_Shd", "g_mid", "g_Pu")}
        self.gun = self.rows["g_G"]
        # the deck's top: the skin's row at the deck on the gun deck's side (its inner face, where the skin cuts the
        # ports' inner edges and slice 7 stood the guns: deck.Deck.zg), not the draught's deck line (pr.G) itself. The
        # inner face is the moulded surface moved in along its normal, which leans with the tumblehome and the flare, so
        # its row lies up to 3 in under the line amidships and 3 in over it forward; the ports' sills and heads on the
        # face move with it. Three of its stations where the face turns into the stern (x -27.2) dip half an inch: left
        # out, so the deck is fair
        G = self.gun
        s = np.diff(G[:, 2]) / np.maximum(np.diff(G[:, 0]), 1e-9)
        keep = np.ones(len(G), bool)
        keep[1:-1] = np.degrees(np.abs(np.diff(np.arctan(s)))) < 10.0
        self.deck_line = G[keep][:, [0, 2]]
        self.x_aft, self.x_fwd = float(self.gun[0, 0]), float(self.gun[-1, 0])
        self.e1, self.fc, self.bp = dk.e1, dk.fc, dk.beam_pitch
        self.parts_ = {}
        self.frames = {}
        self.info = {}
        self.lights = []
        self.ports = [((a - self.L.mid_px) * sk.m.sx, (f - self.L.mid_px) * sk.m.sx) for a, f, _, _ in self.pr.gun]

    # --- along the ship -------------------------------------------------------------------------------------------------
    def xpx(self, x):
        return np.asarray(x, float) / self.sk.m.sx + self.L.mid_px

    def zg(self, x):
        """the gun deck's top at x (flat across)"""
        return np.interp(x, self.deck_line[:, 0], self.deck_line[:, 1])

    def zs(self, x):
        """the spar deck's top"""
        return self.dk.z(x)

    def zsu(self, x):
        """the spar deck's planks' underside (the beams' tops)"""
        return self.dk.zu(x)

    def S(self, x):
        """the gun port sill line (the draught's, on the side's outside)"""
        return np.asarray(self.pr.S(self.xpx(x)), float) / self.k

    def Shd(self, x):
        """the gun port head line (the draught's, on the side's outside)"""
        return np.asarray(self.pr.Shd(self.xpx(x)), float) / self.k

    def wall(self, x, z, true=False):
        """points on the gun deck's side (its inner face, starboard) at x and height z (arrays alike): (points (n, 3),
        unit normals pointing inboard: horizontal, or with true the face's own, square to it, which tilt down where the
        side tumbles home and up where it flares)"""
        x = np.atleast_1d(np.asarray(x, float))
        z = np.broadcast_to(np.atleast_1d(np.asarray(z, float)), x.shape).copy()
        X = self.xpx(x)
        zp = z * self.k
        for _ in range(5):
            P, N = self.sk.surf(X, zp, True, 0, self.SKM.GUN)
            zp = zp + (z - P[:, 2]) * self.k
        P, N = self.sk.surf(X, zp, True, 0, self.SKM.GUN)
        n = np.column_stack([N[:, 0], N[:, 1], np.zeros(len(N))])
        n /= np.linalg.norm(n, axis=1)[:, None]
        inb = (n[:, 1] > 0)[:, None]
        if true:
            n = np.asarray(N, float) / np.linalg.norm(N, axis=1)[:, None]
        n = np.where(inb, -n, n)
        return P, n

    def wall_at(self, x, z, true=False):
        """the side's inner face exactly at x and z (arrays alike): wall's point for an x lies fore or aft of it where the
        side leans fore and aft (its inner face stands off the moulded surface along that surface's normal: at the bow
        by as much as 0.3 m), so the x asked of wall is moved until its point lands on x. (points, normals: as wall's)"""
        x = np.atleast_1d(np.asarray(x, float))
        z = np.broadcast_to(np.atleast_1d(np.asarray(z, float)), x.shape).copy()
        xq = x.copy()
        for _ in range(12):
            P, n = self.wall(xq, z, true)
            d = x - P[:, 0]
            if np.abs(d).max() < 1e-6:
                break
            xq = xq + d
        else:
            raise SystemExit(f"gundeck: the side's inner face at x {x[np.argmax(np.abs(d))]:.3f} was not found")
        return P, n

    def wall_y(self, x, z):
        """the side's half-breadth at x, z (arrays alike), from the gun rows (quick: for clearances)"""
        x = np.atleast_1d(np.asarray(x, float))
        z = np.broadcast_to(np.atleast_1d(np.asarray(z, float)), x.shape)
        Y = np.stack([np.interp(x, r[:, 0], r[:, 1]) for r in self.rows.values()], 1)
        Z = np.stack([np.interp(x, r[:, 0], r[:, 2]) for r in self.rows.values()], 1)
        out = np.empty(len(x))
        for i in range(len(x)):
            o = np.argsort(Z[i])
            zz, yy = Z[i][o], Y[i][o]
            if z[i] <= zz[0]:
                out[i] = yy[0] + (yy[1] - yy[0]) * (z[i] - zz[0]) / max(zz[1] - zz[0], 1e-9)
            elif z[i] >= zz[-1]:
                out[i] = yy[-1] + (yy[-1] - yy[-2]) * (z[i] - zz[-1]) / max(zz[-1] - zz[-2], 1e-9)
            else:
                out[i] = np.interp(z[i], zz, yy)
        return out

    def plan_x(self, px):
        """a place on the 1849 gun deck plan (x px) in the ship, through the masts at this deck"""
        reg = self.c["registration"]
        mp = reg["masts_px"]
        names = sorted(mp, key=lambda k: mp[k])
        P = [mp[k] for k in names]
        X = [self.mast_x(k) for k in names]
        if px <= P[0]:
            return X[0] + (px - P[0]) / reg["px_per_ft"] * FT
        if px >= P[-1]:
            return X[-1] + (px - P[-1]) / reg["px_per_ft"] * FT
        return float(np.interp(px, P, X))

    def mast_x(self, name):
        """where the mast's axis passes this deck"""
        m = self.rig.masts[name]
        return float((np.asarray(m["O"], float) + m["s_gun"] * np.asarray(m["u"], float))[0])

    def mast_at(self, name, z):
        """the mast's axis point at height z, its radius there and its axis"""
        return self.dk.mast_at(name, z)

    def port_near(self, x, margin):
        """the gun port (index from 0) whose x span, widened by margin, holds x, or None"""
        for i, (a, f) in enumerate(self.ports):
            if a - margin <= x <= f + margin:
                return i
        return None

    # --- the layout -----------------------------------------------------------------------------------------------------
    def layout(self):
        c = self.c
        dk = self.dk
        it = self.items = {}
        hw = c["hatchways"]
        for h in hw["items"]:
            L, W = (v * FT for v in h["inside_ft"])
            x = dk.items[h["under"]]["x"] if "under" in h else self.plan_x(h["plan_px"])
            t = h.get("coaming_thick_in", hw["coaming_thick_in"]) * IN
            it[h["name"]] = dict(x=x, L=L, W=W, t=t, high=hw["coaming_high_in"] * IN, kind=h["kind"],
                                 Lo=L + 2 * t, Wo=W + 2 * t)
        self.x_capstan = dk.x_capstan
        pm = c["pumps"]
        self.x_chain = 0.5 * sum(self.plan_x(p) for p in pm["chain"]["plan_px"])
        self.x_brake = 0.5 * sum(self.plan_x(p) for p in pm["brake"]["plan_px"])
        self.info["layout"] = {k: {"x_m": round(v["x"], 3), "inside_m": [round(v["L"], 3), round(v["W"], 3)],
                                   "kind": v["kind"]} for k, v in it.items()}
        self.info["layout"].update({"GunCapstan": {"x_m": round(self.x_capstan, 3)},
                                    "ChainPumps": {"x_m": round(self.x_chain, 3)},
                                    "BrakePumps": {"x_m": round(self.x_brake, 3)},
                                    "masts_x_m": {n: round(self.mast_x(n), 3) for n in ("mizzen", "main", "fore")}})
        return self

    # --- the deck itself ------------------------------------------------------------------------------------------------
    def rudder_notch(self):
        """the rudder's head comes up through the deck's after edge: (x of its fore face plus a gap, half-width plus a
        gap) at the deck's height there, or None"""
        V = np.asarray(self.skin_parts["Rudder"][0], float)
        za = float(self.gun[0, 2])
        m = (V[:, 2] > za - 0.05) & (V[:, 2] < za + 0.1)
        if not m.any():
            return None
        g = 1.0 * IN
        xr = float(V[m, 0].max()) + g
        if xr <= self.x_aft + 0.005:
            return None
        return xr, float(np.abs(V[m, 1]).max()) + g

    def holes(self):
        """the openings through the deck: [(name, outline (n, 2) counter-clockwise, walls)]: walls True where the
        deck's edge shows (the masts, the capstan's barrel, the cable scuttles), False where a coaming stands in it"""
        out = []
        g = self.c["deck"]["mast_hole_gap_in"] * IN
        for name in ("fore", "main", "mizzen"):
            xt = self.mast_x(name)
            for _ in range(3):
                pt, R, u = self.mast_at(name, float(self.zg(xt)))
                xt = pt[0]
            a, b = (R + g) / u[2], R + g
            th = np.linspace(0, 2 * math.pi, 32, endpoint=False)
            E = np.stack([a * np.cos(th), b * np.sin(th)], 1)
            out.append(("Mast_" + name, E + pt[:2], True))
        cs = self.c["capstan"]
        rb = (cs["barrel_diam_in"][1] / 2 + self.c["deck"]["mast_hole_gap_in"]) * IN
        out.append(("GunCapstan", circle(rb, 24) + [self.x_capstan, 0.0], True))
        bw = self.c["bow"]
        xs, ys = bw["scuttle_at_m"]
        for sy in (1.0, -1.0):
            out.append(("CableScuttle_" + ("S" if sy > 0 else "P"), circle(bw["scuttle_in"] / 2 * IN, 20) + [xs, sy * ys],
                        True))
        for k, v in self.items.items():
            out.append((k, densify(rect2(v["x"], 0.0, v["Lo"], v["Wo"]), 0.2), False))
        bt = self.c["bitts"]
        p = (bt["post_in"] + 0.2) * IN
        for sy in (1.0, -1.0):
            out.append(("BittPost_" + ("S" if sy > 0 else "P"), rect2(bt["x_m"], sy * bt["y_in"] * IN, p, p), False))
        # the tiller rope's legs from the wheel go on down through this deck to the tiller below (slice 13), each in a
        # lead bush
        for k, (x, y, rr) in enumerate(self.dk.tiller_legs):
            out.append(("TillerLeg_%d" % k, circle(rr + 0.8 * IN, 12) + [x, y], True))
        return out

    def outline(self):
        """the deck's edge in plan (counter-clockwise): the side along both sides, across at the ends, notched round the
        rudder's head aft"""
        G = self.gun
        stb = G[:, :2]
        port = G[::-1, :2] * [1.0, -1.0]
        fwd = densify(np.array([stb[-1], port[0]]), 0.3, closed=False)[1:-1]
        xa = float(G[0, 0])
        nt = self.rudder_notch()
        if nt is None:
            aft = densify(np.array([port[-1], stb[0]]), 0.3, closed=False)[1:-1]
        else:
            xr, yr = nt
            pts = np.array([port[-1], [xa, -yr], [xr, -yr], [xr, yr], [xa, yr], stb[0]])
            aft = densify(pts, 0.3, closed=False)[1:-1]
            self.info["rudder_notch_m"] = {"x": [round(xa, 3), round(xr, 3)], "half_width": round(yr, 3)}
        return np.concatenate([stb, fwd, port, aft])

    def surface(self, part):
        """the deck's top (planked: UVs 'Planking' and 'Margin'), its underside, and the walls of its round holes"""
        th = self.c["deck"]["thick_in"] * IN
        holes = self.holes()
        outline = self.outline()
        P2, T = cdt(outline, [h[1] for h in holes], self.c["deck"].get("mesh_step_m", 0.3))
        Z = self.zg(P2[:, 0])
        part.add(np.column_stack([P2, Z]), [tuple(t) for t in T], "GunDeckPlanks",
                 uv=np.column_stack([P2, self.margin_uv(P2)]))
        a2 = (P2[T[:, 1], 0] - P2[T[:, 0], 0]) * (P2[T[:, 2], 1] - P2[T[:, 0], 1]) - \
             (P2[T[:, 1], 1] - P2[T[:, 0], 1]) * (P2[T[:, 2], 0] - P2[T[:, 0], 0])
        self.info["deck"] = {"top_triangles": len(T), "area_m2": round(float(0.5 * np.abs(a2).sum()), 1),
                             "x_m": [round(self.x_aft, 3), round(self.x_fwd, 3)]}
        # the underside, a plank's thickness down, and the deck's edge round the openings that show it
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
        # the deck's edge across the stern's foot under the after wall (it shows where the rudder's notch is)
        nt = self.rudder_notch()
        if nt is not None:
            xr, yr = nt
            xa = self.x_aft
            for y0, y1, x0, x1, want in ((-yr, yr, xr, xr, -EX), (-yr, -yr, xa, xr, EY), (yr, yr, xa, xr, -EY)):
                za, zb = float(self.zg(x0)), float(self.zg(x1))
                quad(part, [[x0, y0, za], [x1, y1, zb], [x1, y1, zb - th], [x0, y0, za - th]], want, "Deck")

    def waterway_edge(self):
        """the flush waterway's inner edge (starboard): (x, y) along the ship, and its half-breadth's slope"""
        if getattr(self, "_ww", None) is None:
            fl = self.c["deck"]["waterway"]["flush_in"] * IN
            G = self.gun
            xs = G[:, 0]
            P, n = self.wall(xs, G[:, 2])
            E = (P + n * np.minimum(fl, np.maximum(P[:, 1] - 0.02, 0.0))[:, None])[:, :2]
            E = E[np.argsort(E[:, 0])]
            self._ww = (E, np.gradient(E[:, 1], E[:, 0]))
        return self._ww

    def margin_uv(self, P2):
        E, dE = self.waterway_edge()
        x = np.clip(P2[:, 0], E[0, 0], E[-1, 0])
        return np.column_stack([np.interp(x, E[:, 0], E[:, 1]) - np.abs(P2[:, 1]), np.abs(np.interp(x, E[:, 0], dE))])

    def planking(self):
        """the material's planking terms' parameters (deck.planking_terms' P)"""
        pk = self.c["deck"]["planking"]
        return {"w": pk["width_in"] * IN, "seam": pk["seam_in"] * IN, "x0": self.e1, "bp": self.bp,
                "Lb": pk["length_beams"], "stagger": pk["butt_stagger_beams"], "plug_r": pk["plug_in"] / 2 * IN,
                "plug_off": pk["plug_off_butt_in"] * IN, "nib": pk["nib_of_width"]}

    def waterways(self, part):
        """the waterway's hollow along each side at the deck's edge, from the after wall to where the bow narrows to
        0.4 m, or to 2 in short of the hawse holes' linings: their bores come in at the deck, with no room for the cove
        under them (forward of its end the side's inner face comes down to the deck)"""
        prof = np.array(self.c["deck"]["waterway"]["profile_in"], float) * IN
        G = self.gun
        i = int(np.nonzero(G[:, 1] >= 0.4)[0].max())
        x_end = float(G[i, 0])
        x_cut = None
        if self.hawse_x is not None:
            # the face's points lie aft of the x asked for at the bow: find the x whose point (the cove's top, the
            # foremost of the ring) lands 2 in aft of the lining
            xq = np.linspace(x_end - 1.5, x_end, 151)
            xa = self.wall_over_deck(xq, float(prof[0, 1]))[0][:, 0]
            want = self.hawse_x - 2.0 * IN
            if xa.max() > want:
                x_end = float(np.interp(want, np.maximum.accumulate(xa), xq))
                x_cut = round(want, 3)
        xs = G[:, 0]
        xs = np.unique(np.concatenate([xs[(xs > xs[0] + 0.02) & (xs < x_end)][::2], [xs[0] + 0.005, x_end]]))
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
            # (at the bow the side's normal leans fore and aft: the cove's foot follows the deck at its own x)
            ring[:, 2] += self.zg(ring[:, 0]) - self.zg(np.full(len(ring), P0[k, 0]))
            rings.append(ring)
        for sgn in (1.0, -1.0):
            solid(part, [r * [1.0, sgn, 1.0] for r in rings], "Oak")
        self.info["waterways"] = {"fore_end_x_m": round(float(max(r[:, 0].max() for r in rings)), 3),
                                  "short_of_hawse_x_m": x_cut}
        self.spirketting(part, xs, h0)

    def wall_over_deck(self, xs, h):
        """points on the side's inner face h over the deck at their own x (wall's points lie aft of the x asked for
        where the bow's side leans fore and aft), and the inboard normals there"""
        xs = np.atleast_1d(np.asarray(xs, float))
        z = self.zg(xs) + h
        for _ in range(4):
            P, n = self.wall(xs, z)
            z = self.zg(P[:, 0]) + h
        return self.wall(xs, z)

    def spirketting(self, part, xs, h0):
        """toward the bow the skin's inner face (GunWall) stops short of the deck, over the waterway's cove: a strip of
        the ceiling from the cove's top up behind the face's lower edge closes the slit (laid a little behind the face,
        so where both are the face shows)"""
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        V, F = np.asarray(self.skin_parts["GunWall"][0], float), self.skin_parts["GunWall"][1]
        T = [(f[0], f[i], f[i + 1]) for f in F for i in range(1, len(f) - 1)]
        bvh = BVHTree.FromPolygons([tuple(map(float, v)) for v in V], T)
        let = 0.25 * IN
        hs = np.arange(0.0, 0.3, 0.002)
        lows = []                                      # the face's lowest point over the deck at each x
        for x in xs:
            h_lo = 0.3
            for h in hs:
                P, n = self.wall_over_deck(np.array([x]), h)
                hit = bvh.ray_cast(Vector(P[0] + 0.3 * n[0]), Vector(-n[0]), 0.4)
                if hit[0] is not None:
                    h_lo = h
                    break
            lows.append(h_lo)
        lows = np.array(lows)
        gap = lows - h0
        on = gap > -0.004
        if not on.any():
            self.info["spirketting"] = None
            return
        k0, k1 = int(np.nonzero(on)[0].min()), int(np.nonzero(on)[0].max())
        k0 = max(k0 - 1, 0)
        sel = np.arange(k0, k1 + 1)
        rows = []
        for t in np.linspace(0.0, 1.0, 4):
            hb = h0 - let
            ht = lows[sel] + 0.75 * IN
            h = hb + (ht - hb) * t
            P = np.empty((len(sel), 3))
            n = np.empty((len(sel), 3))
            for j, kk in enumerate(sel):
                Pj, nj = self.wall_over_deck(np.array([xs[kk]]), float(h[j]))
                P[j], n[j] = Pj[0], nj[0]
            rows.append(P - n * 0.001)
        G = np.stack(rows)                       # (4, n, 3): up the wall, along it
        for sgn in (1.0, -1.0):
            Vg = (G * [1.0, sgn, 1.0]).reshape(-1, 3)
            m = G.shape[1]
            Fq = [(j * m + i, j * m + i + 1, (j + 1) * m + i + 1, (j + 1) * m + i) for j in range(3) for i in range(m - 1)]
            nrm = newell(Vg[list(Fq[0])])
            want = np.array([0.0, -sgn, 0.0])
            if float(nrm @ want) < 0:
                Fq = [f[::-1] for f in Fq]
            part.add(Vg, Fq, "Interior")
        self.info["spirketting"] = {"x_m": [round(float(xs[k0]), 3), round(float(xs[k1]), 3)],
                                    "slit_m": round(float(gap[on].max()), 4)}

    # --- overhead: the spar deck's framing ------------------------------------------------------------------------------
    def openings_above(self):
        """the spar deck's openings over this deck, as plan boxes [x0, x1, y half-width, name], each its own size with
        the overhead's margin: the hatchways, companion, skylights and chimney (their coamings' outsides), the
        capstan's barrel and the masts"""
        dk = self.dk
        mg = self.c["overhead"]["opening_margin_in"] * IN
        out = []
        for k, v in dk.items.items():
            out.append([v["x"] - v["Lo"] / 2 - mg, v["x"] + v["Lo"] / 2 + mg, v["Wo"] / 2 + mg, k])
        cs = dk.c["capstan"]
        rb = (cs["barrel_diam_in"][1] / 2 + dk.c["deck"]["mast_hole_gap_in"]) * IN
        out.append([dk.x_capstan - rb - mg, dk.x_capstan + rb + mg, rb + mg, "Capstan"])
        g = dk.c["deck"]["mast_hole_gap_in"] * IN
        for name in ("fore", "main", "mizzen"):
            xs = []
            for z in (float(self.zsu(self.mast_x(name))) - self.c["overhead"]["beam_in"][1] * IN,
                      float(self.zs(self.mast_x(name)))):
                p, R, u = self.mast_at(name, z)
                xs += [p[0] - R / u[2] - g, p[0] + R / u[2] + g]
                rr = R + g
            out.append([min(xs) - mg, max(xs) + mg, rr + mg, "Mast_" + name])
        return sorted(out)

    def stations(self):
        """the spar deck's beam stations over this deck: [(x, kind)], kind 'beam' (every other station, the waist's
        own beams are deck.py's), 'ledge' between them, 'breast' at the breaks, 'gangway' (the odd stations in the
        waist: ledges under the gangways only), aft to fore while the deck is wide enough"""
        bp, e1, fc = self.bp, self.e1, self.fc
        sided = self.c["overhead"]["beam_in"][0] * IN
        out = [(e1 - sided / 2, "breast"), (fc + sided / 2, "breast")]
        k = 1
        while True:
            x = e1 - k * bp
            if x - sided / 2 < float(self.rows["g_Pu"][0, 0]) + 0.05:
                break
            out.append((x, "beam" if k % 2 == 0 else "ledge"))
            k += 1
        k = 1
        while True:
            x = fc + k * bp
            if float(np.interp(x + sided / 2, self.rows["g_Pu"][:, 0], self.rows["g_Pu"][:, 1])) < 0.6:
                break
            out.append((x, "beam" if k % 2 == 0 else "ledge"))
            k += 1
        for k in range(1, 16, 2):
            out.append((e1 + k * bp, "gangway"))
        return sorted(out)

    def end_y(self, x0, x1, z0, z1):
        """how far a member spanning x0..x1 and z0..z1 reaches out to the side: the least half-breadth over it, less
        2 mm"""
        P, _ = self.wall_at(np.array([x0, x1, x0, x1]), np.array([z0, z0, z1, z1]))
        return float(P[:, 1].min()) - 0.002

    def overhead(self, part):
        """the spar deck's beams, ledges, carlings and head ledges over this deck (the waist's beams are deck.py's)"""
        oh = self.c["overhead"]
        bs, bm = (v * IN for v in oh["beam_in"])
        ls, lm = (v * IN for v in oh["ledge_in"])
        cs_, cm = (v * IN for v in oh["carling_in"])
        yo = self.dk.y_open + self.dk.t_coam / 2           # the waist's carlings under the gangways' coamings
        boxes = self.openings_above()
        st = self.stations()
        members = []                                       # [x, sided, moulded, kind]
        for x, kind in st:
            s, m = (bs, bm) if kind in ("beam", "breast") else (ls, lm)
            members.append([x, s, m, kind])
        # which members cross an opening; the openings grouped where their framing overlaps
        def crosses(mb, bx):
            return mb[0] + mb[1] / 2 > bx[0] and mb[0] - mb[1] / 2 < bx[1]
        cut = {}                                            # member index -> half-width cut out of it
        groups = []
        for bx in boxes:
            hit = [i for i, mb in enumerate(members) if mb[3] != "gangway" and crosses(mb, bx)]
            if not hit:
                continue
            Y = bx[2] + cs_
            aft = [i for i, mb in enumerate(members) if mb[0] + mb[1] / 2 <= bx[0] and mb[3] != "gangway"
                   and i not in hit]
            fwd = [i for i, mb in enumerate(members) if mb[0] - mb[1] / 2 >= bx[1] and mb[3] != "gangway"
                   and i not in hit]
            if not aft or not fwd:
                raise SystemExit(f"gundeck: no whole beam {'aft' if not aft else 'forward'} of the opening {bx[3]}")
            whole_aft = max(aft, key=lambda i: members[i][0])
            whole_fwd = min(fwd, key=lambda i: members[i][0])
            groups.append({"boxes": [bx], "hit": set(hit), "Y": Y, "aft": whole_aft, "fwd": whole_fwd})
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
            for i in range(len(members)):
                if members[g["aft"]][0] < members[i][0] < members[g["fwd"]][0] and members[i][3] != "gangway":
                    if i in g["hit"]:
                        cut[i] = max(cut.get(i, 0.0), g["Y"])
        self.overhead_info = {"members": [], "carlings": [], "head_ledges": []}
        # the members: whole, or two halves from the side to the carlings
        for i, (x, s, m, kind) in enumerate(members):
            x0, x1 = x - s / 2, x + s / 2
            zt0, zt1 = float(self.zsu(x0)), float(self.zsu(x1))
            ye = self.end_y(x0, x1, min(zt0, zt1) - m, max(zt0, zt1))
            if kind == "gangway":
                spans = [(yo + cs_ / 2, ye), (-ye, -(yo + cs_ / 2))]
            elif i in cut:
                Y = cut[i]
                spans = [(Y, ye), (-ye, -Y)]
            else:
                spans = [(-ye, ye)]
            ch = oh["chamfer_in"]["beam" if kind in ("beam", "breast") else "ledge"] * IN
            for ya, yb in spans:
                self.member(part, x0, x1, zt0, zt1, m, ya, yb, ch, ye)
            self.overhead_info["members"].append({"x_m": round(x, 4), "kind": kind,
                                                  "spans_y_m": [[round(a, 3), round(b, 3)] for a, b in spans]})
        self.members = members
        self.cut = cut
        # the carlings: fore and aft either side of each group of openings, from whole member to whole member, broken
        # where a whole member crosses them; the head ledges across between them at each opening's ends
        mid = lambda i: members[i]                         # noqa: E731
        for g in merged:
            Y = g["Y"]
            xa = mid(g["aft"])[0] + mid(g["aft"])[1] / 2
            xf = mid(g["fwd"])[0] - mid(g["fwd"])[1] / 2
            # each whole member inside the span breaks the carling: a run between consecutive faces
            runs, cur = [], xa
            for j, (x, s, m, kind) in sorted(enumerate(members), key=lambda t: t[1][0]):
                if xa < x < xf and j not in g["hit"] and kind != "gangway":
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
            # head ledges: at each opening's ends, between the carlings, where no member already stands there
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
                    self.overhead_info["head_ledges"].append({"x_m": round(xc, 3), "for": bx[3]})
        # the waist's carlings under the gangways' coamings, between the waist's beams (deck.py) and the breast beams
        wb = sorted(self.dk.beams_x)
        faces = [self.e1] + [v for x in wb for v in (x - bs / 2, x + bs / 2)] + [self.fc]
        for sy in (1.0, -1.0):
            for a, b in zip(faces[0::2], faces[1::2]):
                self.carling(part, sy * yo, a, b, 3)
        self.groups = merged
        self.info["overhead"] = {"members": len(members), "cut": {round(members[i][0], 3): round(y, 3)
                                                                  for i, y in sorted(cut.items())},
                                 "groups": [[b[3] for b in g["boxes"]] for g in merged]}

    def member(self, part, x0, x1, zt0, zt1, m, ya, yb, ch, ye):
        """one beam or ledge (or one half of it) between its faces x0 and x1, its top at the planks' underside (zt0, zt1
        there), m deep, from ya to yb across: its two lower edges chamfered ch, each chamfer stopped short of the member's
        ends (overhead chamfer_stop_m: at the side, where the hanging and lodging knees and the clamp take the end, and
        at a carling) and dying out over twice its own size. The stopped length keeps a sliver of a chamfer (a
        millimetre) so that no face there has no area"""
        st = self.c["overhead"]["chamfer_stop_m"]
        tiny = 0.001

        def ring(y, c):
            def zb(x):
                return zt0 - m + (zt1 - zt0) * (x - x0) / (x1 - x0)
            return np.array([[x0, y, zb(x0) + c], [x0 + c, y, zb(x0 + c)], [x1 - c, y, zb(x1 - c)], [x1, y, zb(x1) + c],
                             [x1, y, zt1], [x0, y, zt0]])
        sa = st["side"] if abs(abs(ya) - ye) < 0.01 else st["inner"]
        sb = st["side"] if abs(abs(yb) - ye) < 0.01 else st["inner"]
        run = 2.0 * ch
        if ch <= tiny or yb - ya < sa + sb + 2 * run + 0.1:
            rings = [np.array([[x0, y, zt0 - m], [x1, y, zt1 - m], [x1, y, zt1], [x0, y, zt0]]) for y in (ya, yb)]
        else:
            rings = [ring(y, c) for y, c in ((ya, tiny), (ya + sa, tiny), (ya + sa + run, ch), (yb - sb - run, ch),
                                             (yb - sb, tiny), (yb, tiny))]
        solid(part, rings, "Oak")

    def carling(self, part, yc, a, b, n):
        """a carling centred at yc from x a to b (its top at the planks' underside, sampled n times along), its two lower
        edges chamfered (overhead chamfer_in carling) the whole way: its ends butt on the members' faces"""
        oh = self.c["overhead"]
        cs_, cm = (v * IN for v in oh["carling_in"])
        c = oh["chamfer_in"]["carling"] * IN
        rings = []
        for xx in np.linspace(a, b, n):
            zt = float(self.zsu(xx))
            rings.append(np.array([[xx, yc - cs_ / 2, zt - cm + c], [xx, yc - cs_ / 2 + c, zt - cm],
                                   [xx, yc + cs_ / 2 - c, zt - cm], [xx, yc + cs_ / 2, zt - cm + c],
                                   [xx, yc + cs_ / 2, zt], [xx, yc - cs_ / 2, zt]]))
        solid(part, rings, "Oak")

    def beam_bottom(self, x):
        """the beams' underside at x"""
        return float(self.zsu(x)) - self.c["overhead"]["beam_in"][1] * IN

    def waist_members(self):
        """the waist's beams (deck.py's, across the open waist: their tops at the spar deck's underside, their ends on
        this deck's clamp) as members (x, sided, moulded, 'waist'), for the knees and stanchions under them"""
        wa = self.dk.c["waist"]
        return [(x, wa["beam_sided_in"] * IN, wa["beam_moulded_in"] * IN, "waist") for x in self.dk.beams_x]

    def clamps(self, part):
        """the clamp along each side under the beams' ends, its depth eased over the ports' heads"""
        oh = self.c["overhead"]
        dep, th = (v * IN for v in oh["clamp_in"])
        over = oh["clamp_over_port_in"] * IN
        x0 = min(m[0] - m[1] / 2 for m in self.members) - 0.05
        x1 = max(m[0] + m[1] / 2 for m in self.members) + 0.05
        X = list(np.arange(x0, x1, 0.25)) + [x1]
        for a, f in self.ports:
            X += [a - 2 * IN, a, 0.5 * (a + f), f, f + 2 * IN]
        X = np.unique(np.clip(np.array(X), x0, x1))
        zt = np.array([self.beam_bottom(x) for x in X])
        zb = zt - dep
        for i, x in enumerate(X):
            k = self.port_near(x, 2 * IN)
            if k is not None:
                zb[i] = max(zb[i], float(self.Shd(x)) + over)
        if np.any(zt - zb < 2.0 * IN):
            raise SystemExit(f"gundeck: the clamp is less than 2 in deep over a port at x {X[np.argmin(zt - zb)]:.2f}")
        Pt, nt = self.wall_at(X, zt)
        Pb, nb = self.wall_at(X, zb)
        rings = [np.array([Pb[i] - nb[i] * 0.3 * IN, Pb[i] + nb[i] * th, Pt[i] + nt[i] * th, Pt[i] - nt[i] * 0.3 * IN])
                 for i in range(len(X))]
        for sgn in (1.0, -1.0):
            solid(part, [r * [1.0, sgn, 1.0] for r in rings], "Oak")
        self.clamp = (X, zb, zt)
        self.info["clamp"] = {"x_m": [round(float(X[0]), 3), round(float(X[-1]), 3)],
                              "least_deep_in": round(float((zt - zb).min() / IN), 2)}

    def lanyard_cleats(self):
        """each port's two lid lanyard cleats on the side's inner face: [((x of the aft cleat, x of the fore one), ((the
        aft lanyard's room, lo, hi), (the fore's)))]. The port's jambs on the inner face lie where the side's thickness
        carries them (the opening is cut through at the drawing's stations, and toward the bow the inner face stands
        several inches aft of the outside's), so each cleat stands cleat_out_of_jamb_in along the face from the inner
        jamb, cleat_over_deck_in up; its room (the cleat, the rope's turns round it and an inch more) is what the hanging
        knees keep out of (knees)"""
        lan = self.c["gun_gear"]["lanyard"]
        rr = lan["circ_in"] / (2 * math.pi) * IN
        d_c = (lan["cleat_out_of_jamb_in"] + lan["cleat_in"][1] / 2) * IN
        d_r = (lan["cleat_out_of_jamb_in"] + lan["cleat_in"][1] + 0.4 + 1.0) * IN + rr
        out = []
        for a, f in self.ports:
            xs, rooms = [], []
            for xj, sg in ((a, -1.0), (f, 1.0)):
                zc = float(self.zg(xj)) + lan["cleat_over_deck_in"] * IN
                P, n = self.wall(np.array([xj]), np.array([zc]))
                xi, k = float(P[0, 0]), 1.0 / max(abs(float(n[0, 1])), 0.2)     # along the face, not along x
                xs.append(xi + sg * d_c * k)
                rooms.append(tuple(sorted((xi, xi + sg * d_r * k))))
            out.append((tuple(xs), tuple(rooms)))
        return out

    def clamp_inner(self, x, z):
        """the clamp's inner face (starboard) at x, z"""
        P, n = self.wall_at(np.array([x]), np.array([z]))
        return P[0] + n[0] * self.c["overhead"]["clamp_in"][1] * IN, n[0]

    def knees(self, part):
        """a hanging knee under each beam end (whole beams, half beams and the waist's beams, both sides) that comes
        between two ports: its upright arm down the clamp and the side, its other arm along the beam's underside. Beside
        each port the lid's lanyard comes down the side to its cleat (gun_gear's lanyard: cleat_out_of_jamb_in out from
        the jamb, the rope round it) at the height of the knees' feet: a knee that would come within an inch of that
        slides along under its beam, away from the port, to the beam's face (or is left out if that is not far enough)"""
        oh = self.c["overhead"]
        kn = oh["knee"]
        sd = kn["sided_in"] * IN
        arm = kn["arm_in"] * IN
        thr = kn["throat_in"] * IN
        clear = kn["port_clear_in"] * IN
        rooms = [r for _, r in self.lanyard_cleats()]
        dep, th = (v * IN for v in oh["clamp_in"])
        Xc, Zb, Zt = self.clamp
        placed, slid, left_out = [], [], []

        def in_room(xk):
            """the side toward the port whose lanyard's room (lanyard_cleats) the knee at xk comes into (-1 aft of a
            port, +1 forward of one), or 0"""
            for (ra, rf) in rooms:
                if xk + sd / 2 > ra[0] and xk - sd / 2 < ra[1]:
                    return -1
                if xk - sd / 2 < rf[1] and xk + sd / 2 > rf[0]:
                    return 1
            return 0

        for i, (x, s, m, kind) in enumerate(self.members + self.waist_members()):
            if kind not in ("beam", "breast", "waist"):
                continue
            if self.port_near(x, clear + sd / 2) is not None or self.port_near(x, 0.0) is not None:
                continue
            for x_k in ((x,) if kind in ("beam", "waist") else ((x - s / 2 + sd / 2,) if x < 0 else (x + s / 2 - sd / 2,))):
                side = in_room(x_k)
                if side:
                    x_k = x + side * (s / 2 - sd / 2)
                    if in_room(x_k):
                        left_out.append(round(x, 3))
                        continue
                    slid.append(round(x_k, 3))
                zbb = self.beam_bottom(x_k)
                zcb = float(np.interp(x_k, Xc, Zb))
                foot = zbb - arm
                if foot < float(self.zg(x_k)) + 0.5:
                    continue
                def profile(xf):
                    """the knee's outline in (y, z) on its face at xf, starboard: down the clamp's face, out onto the
                    side, down it to the foot, back in along the foot, up the throat to the beam's underside at the
                    arm's end. Each face fits the side at its own x: forward the side narrows by as much as 2 in across
                    the knee's 7 in"""
                    zz = np.linspace(foot, zcb, 6)
                    yw = self.wall_at(np.full(len(zz), xf), zz)[0][:, 1]
                    yc, _ = self.clamp_inner(xf, zbb)
                    ycb, _ = self.clamp_inner(xf, zcb)
                    y_in = min(yc[1], ycb[1])
                    y_end = y_in - (arm - th)
                    toe = 3.0 * IN
                    outer = [(y_in, zbb), (y_in, zcb)] + [(yw[j] + 0.002, zz[j]) for j in range(len(zz) - 1, -1, -1)]
                    foot_in = (yw[0] - toe, foot)
                    head_in = (y_end, zbb - toe)
                    corner = np.array([y_in - thr, zbb - thr])
                    curve = []
                    for t in np.linspace(0.0, 1.0, 9)[1:-1]:
                        p = (1 - t) ** 2 * np.array(foot_in) + 2 * (1 - t) * t * corner + t ** 2 * np.array(head_in)
                        curve.append(tuple(p))
                    return np.array(outer + [foot_in] + curve + [head_in, (y_end, zbb)])

                P0, P1 = profile(x_k - sd / 2), profile(x_k + sd / 2)
                for sgn in (1.0, -1.0):
                    prism2(part, P0 * [sgn, 1.0], P1 * [sgn, 1.0], x_k - sd / 2, x_k + sd / 2, "Oak")
                placed.append(round(x_k, 3))
        self.info["knees_x_m"] = sorted(placed)
        self.info["knees_clear_of_lanyards"] = {"slid_to_beam_face_x_m": slid, "left_out_at_beam_x_m": left_out}

    def bay_faces(self):
        """every overhead member's faces along the ship [(aft face, fore face)], the waist's beams among them, sorted"""
        return sorted((x - s_ / 2, x + s_ / 2) for x, s_, m, kind in list(self.members) + list(self.waist_members()))

    def lodging_knees(self, part):
        """a lodging knee at each end of each beam forward of the cabin's bulkhead (the whole and half beams and the
        waist's), lying flat in the angle between the beam's face and the side, its top flush with the beam's under the
        planks (overhead lodging_knee): one arm fayed along the beam's face, the other along the side, stopping short of
        the next member, the throat between them rounded. It goes on the face toward the ship's middle where that bay is
        clear of the ports (the bays over the ports hold the guns' implements and the lids' lanyards), else on the other
        face; none where both bays are over ports, where the arm along the side would be too short, or where the side
        turns too far from fore and aft to lie along (the bow)"""
        lk = self.c["overhead"]["lodging_knee"]
        sd = lk["sided_in"] * IN
        ab, asd = lk["arm_beam_in"] * IN, lk["arm_side_in"] * IN
        bt_, be, rf = lk["breadth_in"] * IN, lk["end_in"] * IN, lk["throat_in"] * IN
        cp = lk["clear_of_ports_m"]
        cb = self.c["cabin"]
        x_bk = cb["bulkhead_x_m"] + cb["bulkhead_in"] / 2 * IN
        faces = self.bay_faces()
        fay = 0.002
        placed, skipped = [], []
        for x, s_, m, kind in list(self.members) + list(self.waist_members()):
            if kind not in ("beam", "waist"):
                continue
            if x - s_ / 2 < x_bk + 0.3:
                continue
            got = None
            for d in ((-1.0, 1.0) if x > 0 else (1.0, -1.0)):
                xf = x + d * s_ / 2
                nxt = (min((a for a, f in faces if a > xf + 1e-6), default=xf + 2 * asd) if d > 0
                       else max((f for a, f in faces if f < xf - 1e-6), default=xf - 2 * asd))
                L = min(asd, abs(nxt - xf) - lk["short_of_next_in"] * IN)
                lo, hi = sorted((xf, xf + d * L))
                if L < lk["least_side_arm_in"] * IN or any(lo < f + cp and hi > a - cp for a, f in self.ports):
                    continue
                got = (d, xf, L)
                break
            if got is None:
                skipped.append(round(x, 3))
                continue
            d, xf, L = got
            zt0 = float(self.zsu(xf))
            n_mid = self.wall_at(np.array([xf + d * L / 2]), np.array([zt0 - sd / 2]))[1][0]
            if abs(float(n_mid[1])) < math.cos(math.radians(lk["side_within_deg"])):
                skipped.append(round(x, 3))
                continue
            # the outline in (u along d from the beam's face, v in from the side's inner face), round the knee
            arc = [(bt_ + rf + rf * math.cos(a), bt_ + rf + rf * math.sin(a))
                   for a in np.linspace(math.pi, 1.5 * math.pi, 7)]
            side_u = list(np.linspace(L, -fay, 5))
            uv = [(-fay, ab), (be, ab)] + arc + [(L, be)] + [(u, -fay) for u in side_u]

            def ring(z_of):
                out = []
                for u, v in uv:
                    xx = xf + d * u
                    zz = z_of(xx)
                    yw = float(self.wall_at(np.array([xx]), np.array([zz]))[0][0, 1])
                    out.append([xx, yw - v, zz])
                return np.array(out)
            top = ring(lambda xx: float(self.zsu(xx)))
            bot = ring(lambda xx: float(self.zsu(xx)) - sd)
            for sg in (1.0, -1.0):
                solid(part, [bot * [1.0, sg, 1.0], top * [1.0, sg, 1.0]], "Oak")
            placed.append({"beam_x_m": round(x, 3), "face": "fore" if d > 0 else "aft", "side_arm_m": round(L, 3)})
        self.info["lodging_knees"] = {"each_side": len(placed), "by_beam": placed, "none_at_beam_x_m": skipped}

    def stanchions(self, part, footprints):
        """a turned stanchion on the middle line under each whole beam where it stands clear of the fittings'
        footprints (name -> plan outline), forward of the cabin's bulkhead"""
        oh = self.c["overhead"]
        r = oh["stanchion_in"] / 2 * IN
        clear = oh["stanchion_clear_m"]
        xb = self.c["cabin"]["bulkhead_x_m"]
        placed = []
        whole = [m for i, m in enumerate(self.members) if m[3] == "beam" and i not in self.cut] + self.waist_members()
        for x, s, m, kind in whole:
            if x < xb + 0.3:
                continue
            p = np.array([[x, 0.0]])
            if any(in_poly(p, F)[0] or seg_dist(p, F)[0] < r + clear for F in footprints.values()):
                continue
            z0, z1 = float(self.zg(x)), self.beam_bottom(x)
            h = z1 - z0
            prof = [(0.0, r + 1.5 * IN), (2.0 * IN, r + 1.5 * IN), (2.5 * IN, r + 0.5 * IN), (4.0 * IN, r),
                    (h - 4.0 * IN, r), (h - 2.5 * IN, r + 0.5 * IN), (h - 2.0 * IN, r + 1.5 * IN), (h, r + 1.5 * IN)]
            k0 = len(part.V)
            lathe(part, [x, 0.0, z0], EZ, EX, prof, "Oak", 16)
            for V in part.V[k0:]:                          # the foot on the deck's sheer, eased out half way up
                w = np.clip(1.0 - (V[:, 2] - z0) / (0.5 * h), 0.0, 1.0)
                V[:, 2] += w * (self.zg(V[:, 0]) - z0)
            placed.append(round(x, 3))
        self.info["stanchions_x_m"] = sorted(placed)

    # --- hatchways: coamings, gratings, wells and ladders ---------------------------------------------------------------
    def drape(self, part, k0, z_flat):
        """lay what was added to part since k0, built level on z_flat, along this deck's sheer"""
        for V in part.V[k0:]:
            V[:, 2] += self.zg(V[:, 0]) - z_flat

    def coaming(self, part, v, high=None, mat="Oak"):
        """a coaming round an opening (as the spar deck's): its inside the opening, its outside the deck's hole, from
        just under the deck's underside up"""
        high = v["high"] if high is None else high
        th = self.c["deck"]["thick_in"] * IN
        x0, L, W, t = v["x"], v["L"], v["W"], v["t"]
        xs = [x0 - L / 2 - t, x0 - L / 2, x0 + L / 2, x0 + L / 2 + t]
        ys = [-W / 2 - t, -W / 2, W / 2, W / 2 + t]
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

    def well(self, part, v):
        """the well under an opening down to the berth deck's height (slice 13 builds that deck): its sides lined (1 in,
        dim) under the coaming, its floor (3 in) across the bottom; returns the floor's top"""
        th = self.c["deck"]["thick_in"] * IN
        x0, L, W = v["x"], v["L"], v["W"]
        t = 1.0 * IN
        zf = float(self.zg(x0)) - self.c["wells"]["depth_ft"] * FT
        zb = lambda x: float(self.zg(x)) - th - 0.01     # noqa: E731
        xs = [x0 - L / 2 - t, x0 - L / 2, x0 + L / 2, x0 + L / 2 + t]
        ys = [-W / 2 - t, -W / 2, W / 2, W / 2 + t]
        for xa, xb_ in ((xs[0], xs[1]), (xs[2], xs[3])):
            rings = [np.array([[x, ys[0], zf], [x, ys[3], zf], [x, ys[3], zb(x)], [x, ys[0], zb(x)]]) for x in (xa, xb_)]
            solid(part, rings, "Dim")
        for ya, yb in ((ys[0], ys[1]), (ys[2], ys[3])):
            rings = [np.array([[x, ya, zf], [x, yb, zf], [x, yb, zb(x)], [x, ya, zb(x)]]) for x in (xs[1], xs[2])]
            solid(part, rings, "Dim")
        vbox(part, [xs[0], ys[0], zf - 3.0 * IN], [xs[3], ys[3], zf], "Deck")
        return zf

    def ladder(self, part, x_top, z_top, d, y0, z_floor, lc, mat="Oak"):
        """a ladder from its top (x_top, z_top: its stringers cut square against what they hang from there) going d
        (+1 forward, -1 aft) down at lc's angle to the floor z_floor(x); lc: width, stringer, tread, rise, angle.
        Returns its foot's x and the drop"""
        wi = lc["width_in"] * IN
        sd, st = (v * IN for v in lc["stringer_in"])
        td, tt = (v * IN for v in lc["tread_in"])
        ang = math.radians(lc["angle_deg"])
        zf = float(z_floor(x_top + d * 1.0))
        for _ in range(4):
            xf = x_top + d * (z_top - zf) / math.tan(ang)
            zf = float(z_floor(xf))
        xf = x_top + d * (z_top - zf) / math.tan(ang)
        drop = z_top - zf
        for side in (-1.0, 1.0):
            yy = y0 + side * (wi / 2 + st / 2)
            T = np.array([x_top, z_top - 0.5 * IN])
            F_ = np.array([xf, zf])
            a = unit(F_ - T)
            nrm = np.array([-a[1], a[0]])
            if nrm[1] < 0:
                nrm = -nrm
            ext = 0.5
            P = np.array([T - a * ext + nrm * sd / 2, F_ + a * ext + nrm * sd / 2, F_ + a * ext - nrm * sd / 2,
                          T - a * ext - nrm * sd / 2])
            C = np.array([[x_top + d * 0.1 * IN, zf], [x_top + d * 5.0, zf], [x_top + d * 5.0, z_top],
                          [x_top + d * 0.1 * IN, z_top]])
            if d < 0:
                C = C[::-1]
            Q = clip_convex(P, C)
            ring0 = np.column_stack([Q[:, 0], np.full(len(Q), yy - st / 2), Q[:, 1]])
            solid(part, [ring0, ring0 + [0.0, st, 0.0]], mat)
        n = int(round(drop / (lc["rise_in"] * IN)))
        rr = drop / n
        for k in range(1, n):
            z = z_top - k * rr
            x = x_top + d * (z_top - z) / math.tan(ang)
            vbox(part, [x - td / 2, y0 - wi / 2 - 0.4 * IN, z - tt], [x + td / 2, y0 + wi / 2 + 0.4 * IN, z], mat)
        return xf, drop

    def hatchways(self, part, wells, ladders):
        """each opening's coaming, its grating (deck.Deck.grating) or its ladder down, and its well; the companion's
        ladder from the quarterdeck down to this deck"""
        lc = self.c["ladders"]
        self.ladder_info = []
        for k, v in self.items.items():
            zt = self.coaming(part, v)
            zf = self.well(wells, v)
            if v["kind"] == "grating":
                self.dk.grating(part, dict(v, L=v["L"], W=v["W"]), zt)
            else:
                xt = v["x"] - v["L"] / 2
                xf, drop = self.ladder(ladders, xt, zt(xt), 1.0, 0.0, lambda x: zf, lc)
                self.ladder_info.append({"from": k, "top_x_m": round(xt, 3), "foot_x_m": round(xf, 3),
                                         "drop_m": round(drop, 3)})
        # the companion's ladder: its top at the companion's fore coaming (inside), down aft to this deck
        cv = self.dk.items["Companion"]
        xt = cv["x"] + cv["L"] / 2
        zt = float(self.zs(xt)) + cv["high"]
        lcc = dict(lc, **lc["companion"])
        xf, drop = self.ladder(ladders, xt, zt, -1.0, 0.0, self.zg, lcc)
        self.companion_foot = (xf, lcc["width_in"] * IN + 2 * lc["stringer_in"][1] * IN)
        self.ladder_info.append({"from": "Companion", "top_x_m": round(xt, 3), "foot_x_m": round(xf, 3),
                                 "drop_m": round(drop, 3)})
        self.info["ladders"] = self.ladder_info

    # --- the masts' partners --------------------------------------------------------------------------------------------
    def mast_wedges(self, part):
        """the wedges round each mast where it passes the deck: a ring filling the hole's gap, standing 3 in proud"""
        th = self.c["deck"]["thick_in"] * IN
        g = self.c["deck"]["mast_hole_gap_in"] * IN
        for name in ("fore", "main", "mizzen"):
            xt = self.mast_x(name)
            for _ in range(3):
                pt, R, u = self.mast_at(name, float(self.zg(xt)))
                xt = pt[0]
            a = unit(EX - (EX @ u) * u)
            lo, hi = -(th + 0.5 * IN) / u[2], 3.0 * IN / u[2]
            ring_band(part, pt, u, a, 0.5 * (lo + hi), R, hi - lo, g + 1.25 * IN, "Oak", 32)

    # --- the capstan ----------------------------------------------------------------------------------------------------
    def capstan(self, part, pawls):
        """the double capstan's lower head in its own frame (origin on its axis at this deck's top, Z up): the barrel
        through the deck, eight whelps, the drumhead with its bar holes and hoops, and the spindle up into the spar deck
        capstan's barrel; the pawl ring and four pawls on the deck (built in place)"""
        cs = self.c["capstan"]
        x0 = self.x_capstan
        z0 = float(self.zg(x0))
        R = cs["drumhead_diam_in"] / 2 * IN
        Td = cs["drumhead_thick_in"] * IN
        Ht = cs["top_high_in"] * IN
        rt, rb = (v / 2 * IN for v in cs["barrel_diam_in"])
        z_dh = Ht - Td
        z_low = -(self.c["deck"]["thick_in"] * IN + 0.15)
        lathe(part, [0.0, 0.0, z_low], EZ, EX, [(0.0, rb), (-z_low + 2 * IN, rb), (z_dh - z_low, rt)], "Oak", 32)
        wo = cs["whelp_out_in"] * IN
        nw = cs["whelps"]
        z_w0 = 3.0 * IN
        prof = [(z_w0, 1.0), (z_w0 + 0.25 * (z_dh - z_w0), 0.8), (z_w0 + 0.55 * (z_dh - z_w0), 0.62), (z_dh, 0.85)]
        ww = 3.0 * IN
        for k in range(nw):
            a = 2 * math.pi * k / nw
            rad = np.array([math.cos(a), math.sin(a), 0.0])
            tan = np.array([-math.sin(a), math.cos(a), 0.0])
            rings = []
            for z, f in prof:
                rr = rb + (rt - rb) * (z / z_dh)
                ri, ro = rr - 0.6 * IN, rr + wo * f + (1.0 * IN if z == z_w0 else 0.0)
                c = np.array([0.0, 0.0, z])
                rings.append(np.array([c + rad * ri - tan * ww / 2, c + rad * ro - tan * ww / 2,
                                       c + rad * ro + tan * ww / 2, c + rad * ri + tan * ww / 2]))
            solid(part, rings, "Oak")
        nd = 3 * cs["bar_holes"]
        lathe(part, [0.0, 0.0, z_dh], EZ, EX, [(0.0, R - 0.3 * IN), (0.3 * IN, R), (Td - 0.3 * IN, R),
                                               (Td, R - 0.5 * IN), (Td + 0.6 * IN, 0.6 * R)], "Oak", nd)
        for zz in (z_dh + 1.0 * IN, z_dh + Td - 1.0 * IN):
            ring_band(part, np.zeros(3), EZ, EX, zz, R, 1.75 * IN, 0.4 * IN, "Iron", nd)
        bh = cs["bar_hole_in"]
        nb = cs["bar_holes"]
        for k in range(nb):
            a = 2 * math.pi * (k + 0.5) / nb
            rad = np.array([math.cos(a), math.sin(a), 0.0])
            tan = np.array([-math.sin(a), math.cos(a), 0.0])
            c = np.array([0.0, 0.0, z_dh + Td / 2]) + rad * (R * math.cos(math.pi / nd) + 0.0005)
            Q = np.array([c - tan * bh[0] / 2 * IN - EZ * bh[1] / 2 * IN, c + tan * bh[0] / 2 * IN - EZ * bh[1] / 2 * IN,
                          c + tan * bh[0] / 2 * IN + EZ * bh[1] / 2 * IN, c - tan * bh[0] / 2 * IN + EZ * bh[1] / 2 * IN])
            quad(part, Q, rad, "Shadow")
        # the spindle: from the drumhead's crown up 1 in into the spar deck capstan's barrel (its foot 0.15 m under that
        # deck's planks: deck.py)
        z_top = float(self.zsu(x0)) - 0.15 - z0
        rs = cs["spindle_in"] / 2 * IN
        lathe(part, [0.0, 0.0, Ht], EZ, EX, [(0.0, rs + 1.0 * IN), (1.5 * IN, rs), (z_top - Ht + 1.0 * IN, rs)], "Oak",
              24)
        ring_band(part, np.zeros(3), EZ, EX, Ht + 3.0 * IN, rs, 1.5 * IN, 0.35 * IN, "Iron", 24)
        self.frames["GunCapstan"] = (np.array([x0, 0.0, z0]), np.eye(3))
        self.capstan_spindle = (z0 + Ht, z0 + z_top + 1.0 * IN, rs)
        # the pawl ring and pawls, as the spar deck's
        r_ring = rb + wo + 2.0 * IN
        k0 = len(pawls.V)
        ring_band(pawls, np.array([x0, 0.0, z0]), EZ, EX, 0.5 * IN, r_ring, 1.4 * IN, 3.0 * IN, "Iron", 40)
        for k in range(4):
            a = 2 * math.pi * (k + 0.3) / 4
            p0 = np.array([x0 + (r_ring + 1.5 * IN) * math.cos(a), (r_ring + 1.5 * IN) * math.sin(a), z0 + 1.6 * IN])
            tgt = np.array([x0 + (rb + wo + 1.4 * IN) * math.cos(a + 0.22), (rb + wo + 1.4 * IN) * math.sin(a + 0.22),
                            z0 + 1.6 * IN])
            bar(pawls, p0, tgt, 1.5 * IN, 1.0 * IN, "Iron")
            lathe(pawls, p0 - EZ * 0.6 * IN, EZ, EX, [(0.0, 0.5 * IN), (1.4 * IN, 0.5 * IN)], "Iron", 8)
        self.drape(pawls, k0, z0)

    # --- the pumps ------------------------------------------------------------------------------------------------------
    def chain_pumps(self, part):
        """the chain pumps abaft the main mast: their case on the deck over the well, a crank axle across it in two
        standards, a winch handle at each end"""
        pc = self.c["pumps"]["chain"]
        x0 = self.x_chain
        z0 = float(self.zg(x0))
        Lc, Wc, Hc = (v * IN for v in pc["case_in"])
        k0 = len(part.V)
        # the case, its lid lapping it an inch all round
        vbox(part, [x0 - Lc / 2, -Wc / 2, z0 - 0.5 * IN], [x0 + Lc / 2, Wc / 2, z0 + Hc - 2.0 * IN], "Oak")
        vbox(part, [x0 - Lc / 2 - 1.0 * IN, -Wc / 2 - 1.0 * IN, z0 + Hc - 2.0 * IN],
             [x0 + Lc / 2 + 1.0 * IN, Wc / 2 + 1.0 * IN, z0 + Hc], "Oak")
        za = z0 + pc["axle_high_in"] * IN
        ss, sth = (v * IN for v in pc["standard_in"])
        ra = pc["axle_in"] / 2 * IN
        y_std = Wc / 2 + 1.0 * IN + sth / 2 + 0.25 * IN
        for sy in (1.0, -1.0):
            # each standard stands on the deck against the case's side, its head over the axle
            vbox(part, [x0 - ss / 2, sy * y_std - sth / 2, z0 - 0.5 * IN], [x0 + ss / 2, sy * y_std + sth / 2,
                                                                         za + ra + 3.0 * IN], "Oak")
        hy = pc["handle_y_in"] * IN
        throw = pc["crank_throw_in"] * IN
        rh = pc["handle_in"] / 2 * IN
        y_end = y_std + sth / 2 + 2.0 * IN
        lathe(part, [x0, -y_end, za], EY, EX, [(0.0, ra), (2 * y_end, ra)], "Iron", 12)
        for sy, ang in ((1.0, 30.0), (-1.0, 210.0)):
            # the crank's web out and down from the axle's end, the handle outboard on its pin
            a = math.radians(ang)
            r_dir = np.array([math.sin(a), 0.0, -math.cos(a)])
            p0 = np.array([x0, sy * (y_end - 0.75 * IN), za])
            p1 = p0 + r_dir * throw
            bar(part, p0 - r_dir * 1.5 * IN, p1 + r_dir * 1.5 * IN, 2.5 * IN, 1.5 * IN, "Iron", up=EY)
            y1, y2 = y_end + 0.25 * IN, hy + 9.0 * IN          # the handle, outboard of the web on its pin
            lathe(part, [p1[0], sy * y1, p1[2]], sy * EY, EX, [(0.0, rh), (y2 - y1, rh)], "Oak", 12)
        self.drape(part, k0, z0)
        self.chain_case = (x0, Lc + 2.0 * IN, 2 * (hy + 9.0 * IN))

    def brake_pumps(self, part):
        """the pair of common pumps forward of the main mast: each a barrel on the deck with a spout to the side, a
        standard forward of it carrying the brake (the handle) that works the spear in the barrel"""
        pb = self.c["pumps"]["brake"]
        x0 = self.x_brake
        rb = pb["barrel_in"][0] / 2 * IN
        hb = pb["barrel_in"][1] * IN
        rbore = pb["tube_in"] / 2 * IN
        rs, ls = pb["spout_in"][0] / 2 * IN, pb["spout_in"][1] * IN
        ss, sth = (v * IN for v in pb["standard_in"])
        hs = pb["standard_high_in"] * IN
        Lb = pb["brake_ft"] * FT
        bw, bt = (v * IN for v in pb["brake_in"])
        xs = x0 + rb + 6.0 * IN + ss / 2                      # the standard, just forward of the barrel
        for sy in (1.0, -1.0):
            y = sy * pb["y_in"] * IN
            z0 = float(self.zg(x0))
            lathe(part, [x0, y, z0 - 0.5 * IN], EZ, EX, [(0.0, rb + 1.0 * IN), (2.0 * IN, rb + 1.0 * IN),
                                                         (2.5 * IN, rb), (hb - 1.5 * IN, rb), (hb, rb - 0.5 * IN)],
                  "Oak", 20)
            for zz in (z0 + 6.0 * IN, z0 + hb - 4.0 * IN):
                ring_band(part, np.array([x0, y, zz]), EZ, EX, 0.0, rb, 1.5 * IN, 0.3 * IN, "Iron", 20)
            disc(part, [x0, y, z0 + hb + 0.05 * IN], EZ, rbore, "Shadow", 16)
            zsp = z0 + hb - 9.0 * IN
            lathe(part, [x0, y + sy * (rb - 1.0 * IN), zsp], sy * EY, EX, [(0.0, rs + 0.5 * IN), (1.5 * IN, rs),
                                                                           (ls, rs)], "Lead", 12)
            disc(part, [x0, y + sy * (rb - 1.0 * IN + ls + 0.05 * IN), zsp], sy * EY, rs - 0.5 * IN, "Shadow", 12)
            zs0 = float(self.zg(xs))
            vbox(part, [xs - ss / 2, y - sth / 2, zs0 - 0.5 * IN], [xs + ss / 2, y + sth / 2, zs0 + hs], "Oak")
            # the brake across the standard's head on a bolt: its short arm aft over the spear, the long arm forward
            zbk = zs0 + hs + bt / 2 + 0.25 * IN
            xa_ = x0 - 3.0 * IN
            vbox(part, [xa_, y - bw / 2, zbk - bt / 2], [xa_ + Lb, y + bw / 2, zbk + bt / 2], "Oak")
            lathe(part, [xs, y - bw / 2 - 1.0 * IN, zbk], EY, EX, [(0.0, 0.6 * IN), (bw + 2.0 * IN, 0.6 * IN)], "Iron",
                  8)
            lathe(part, [x0, y, z0 + hb - 6.0 * IN], EZ, EX, [(0.0, 0.7 * IN), (zbk - bt / 2 - (z0 + hb - 6.0 * IN), 0.7 * IN)],
                  "Iron", 8)
        self.brake_span = (x0 - rb - 1.0 * IN, x0 - 3.0 * IN + Lb, (pb["y_in"] * IN + rb + ls) * 2)

    # --- the riding bitts -----------------------------------------------------------------------------------------------
    def bitts(self, part):
        """the riding bitts abaft the fore mast: two posts down through the deck (their edges chamfered, their heads
        rounded over), the cross piece on their fore faces (its fore edges chamfered, its ends rounded down), a standard
        behind each, and the iron bolts through them (round heads: two through the cross piece into each post, two down
        through each standard's arm into the deck)"""
        bt = self.c["bitts"]
        x0 = bt["x_m"]
        p = bt["post_in"] * IN
        th = self.c["deck"]["thick_in"] * IN
        z0 = float(self.zg(x0))
        hh = bt["head_in"] * IN
        k0 = len(part.V)
        cz, cx = (v * IN for v in bt["cross_in"])
        so, sm = (v * IN for v in bt["standard_in"])
        out = bt["cross_out_in"] * IN
        yb = bt["y_in"] * IN
        ch = bt["chamfer_in"] * IN
        bh = bt["bolt_head_in"] * IN

        def section(cxy, hx, hy, c):
            """a rectangle hx by hy half sizes about cxy, its corners chamfered c"""
            x_, y_ = cxy
            return np.array([[x_ + hx, y_ - hy + c], [x_ + hx, y_ + hy - c], [x_ + hx - c, y_ + hy], [x_ - hx + c, y_ + hy],
                             [x_ - hx, y_ + hy - c], [x_ - hx, y_ - hy + c], [x_ - hx + c, y_ - hy], [x_ + hx - c, y_ - hy]])

        def bolt(P, n):
            lathe(part, P - n * 0.25 * IN, n, np.cross(n, EZ) if abs(n[2]) < 0.9 else EX,
                  [(0.0, bh / 2), (0.3 * IN, bh / 2), (0.55 * IN, 0.4 * bh), (0.7 * IN, 0.2 * bh)], "Iron", 10)

        zc1 = z0 + hh - bt["cross_below_head_in"] * IN
        for sy in (1.0, -1.0):
            y = sy * yb
            # the post: chamfered up to its head, which rounds over in four steps to a flat crown
            rings = []
            for z, k in ((z0 - th - 0.15, 1.0), (z0 + hh - 2.5 * IN, 1.0), (z0 + hh - 1.2 * IN, 0.94), (z0 + hh - 0.4 * IN, 0.8),
                         (z0 + hh, 0.55)):
                S2 = section((x0, y), k * p / 2, k * p / 2, ch * k)
                rings.append(np.column_stack([S2, np.full(len(S2), z)]))
            solid(part, rings, "Oak")
            # the standard: up the post's after face, along the deck aft; a knee's throat between
            arm_up = hh - 8.0 * IN
            arm_aft = self.bitt_standard_m
            prof = [(0.0, 0.0), (0.0, arm_up), (-sm, arm_up)]
            for t in np.linspace(0.0, 1.0, 9)[1:-1]:
                q = (1 - t) ** 2 * np.array([-sm, arm_up - 4.0 * IN]) + 2 * (1 - t) * t * np.array([-sm - 4.0 * IN, sm + 4.0 * IN]) \
                    + t ** 2 * np.array([-arm_aft + 4.0 * IN, sm])
                prof.append((float(q[0]), float(q[1])))
            prof += [(-arm_aft, sm * 0.6), (-arm_aft, 0.0)]
            P = np.array([[x0 - p / 2 + a_, z0 + b_] for a_, b_ in prof])
            P[:, 1] -= 0.25 * IN
            prism(part, P, y - so / 2, y + so / 2, "Oak", axis=1)
            # its bolts: down through the arm along the deck, square to its top
            tx, tz = P[2:-1, 0][::-1], P[2:-1, 1][::-1]
            for d in (arm_aft - 7.0 * IN, arm_aft - 15.0 * IN):
                xb_ = x0 - p / 2 - d
                zt_ = float(np.interp(xb_, tx, tz))
                sl = (float(np.interp(xb_ + 0.5 * IN, tx, tz)) - float(np.interp(xb_ - 0.5 * IN, tx, tz))) / IN
                bolt(np.array([xb_, y, zt_]), unit(np.array([-sl, 0.0, 1.0])))
            # two bolts through the cross piece into the post, their heads on its fore face
            for dz in (0.3, 0.7):
                bolt(np.array([x0 + p / 2 + cx, y, zc1 - dz * cz]), EX)
        # the cross piece on the posts' fore faces, its top cross_below_head under the heads, its fore edges chamfered,
        # its ends rounded down (a quarter round of half its depth over the end)
        ye = yb + p / 2 + out
        r = 0.5 * cz
        q = np.linspace(0.0, 0.5 * math.pi, 6)
        top = [(ye - r + r * math.sin(a_), zc1 - r + r * math.cos(a_)) for a_ in q]
        prof = np.array([(-y_, z_) for y_, z_ in top[::-1]] + top + [(ye, zc1 - cz), (-ye, zc1 - cz)])
        inner = np.column_stack([prof[:, 0] * (ye - ch) / ye, zc1 - cz + ch + (prof[:, 1] - (zc1 - cz)) * (cz - 2 * ch) / cz])
        solid(part, [np.column_stack([np.full(len(Q), xx), Q]) for xx, Q in
                     ((x0 + p / 2, prof), (x0 + p / 2 + cx - ch, prof), (x0 + p / 2 + cx, inner))], "Oak")
        self.drape(part, k0, z0)
        self.bitts_box = (x0 - p / 2 - self.bitt_standard_m, x0 + p / 2 + cx, ye)

    # --- the galley -----------------------------------------------------------------------------------------------------
    def galley(self, part):
        """the galley's iron stove (Brodie's patent kind) on its brick hearth under the forecastle: cast plates bolted at
        angle irons up the corners, a band round its sides and after end at half height and a rib up the middle of each
        side, every joint on round bolt heads; the top plate with a fiddle bar round its edge and the boilers' lids in it;
        on its fore face the fire's open mouth with the grate's bars across it, the ash pit's door under it and the
        oven's door beside it, each in its frame, the oven door on two strap hinges with a latch; an iron kerb round the
        hearth's top edge, an iron rail round the sides and after end, and its flue up into the forecastle's chimney,
        meeting its plate, with a band and the damper's handle"""
        gl = self.c["galley"]
        dt = gl["detail"]
        xa, xf = gl["x_m"]
        W = gl["width_in"] * IN
        Hs = gl["high_in"] * IN
        ht, hm = (v * IN for v in gl["hearth_in"])
        bd = dt["bolt_in"] * IN
        k0 = len(part.V)
        z0 = float(self.zg(0.5 * (xa + xf)))
        # the hearth, a course of brick set in mortar, and the stove on it (built level, then laid along the sheer)
        vbox(part, [xa - hm, -W / 2 - hm, z0 - 0.5 * IN], [xf + hm, W / 2 + hm, z0 + ht], "Brick")
        zb = z0 + ht
        # the hearth's kerb: an iron angle round its top edge (its upright leg standing up off the bricks)
        kl, kt = (v * IN for v in dt["kerb_in"])
        ko = 0.05 * IN                                     # its faces a hair proud of the bricks' sides
        xk0, xk1, yk = xa - hm - ko, xf + hm + ko, W / 2 + hm + ko
        for (a_, b_), (c_, d_) in (((xk0, xk1), (-yk, -yk + kt)), ((xk0, xk1), (yk - kt, yk)),
                                   ((xk0, xk0 + kt), (-yk + kt, yk - kt)), ((xk1 - kt, xk1), (-yk + kt, yk - kt))):
            vbox(part, [a_, c_, zb - 0.6 * IN], [b_, d_, zb + kl], "Iron")
        vbox(part, [xa, -W / 2, zb - 0.25 * IN], [xf, W / 2, zb + Hs - 1.0 * IN], "Iron")
        vbox(part, [xa - 0.75 * IN, -W / 2 - 0.75 * IN, zb + Hs - 1.0 * IN], [xf + 0.75 * IN, W / 2 + 0.75 * IN, zb + Hs],
             "Iron")
        # a moulding round the foot
        vbox(part, [xa - 0.75 * IN, -W / 2 - 0.75 * IN, zb - 0.25 * IN], [xf + 0.75 * IN, W / 2 + 0.75 * IN, zb + 2.0 * IN],
             "Iron")
        # the corners' angle irons, from the foot's moulding to the top plate, bolted along each leg
        al, at_ = (v * IN for v in dt["angle_in"])
        z_lo, z_hi = zb + 2.0 * IN, zb + Hs - 1.0 * IN
        nb = max(2, int(round((z_hi - z_lo) / (dt["bolt_pitch_in"] * IN))))
        zbs = z_lo + (np.arange(nb) + 0.5) * (z_hi - z_lo) / nb
        for cx_, sx in ((xa, -1.0), (xf, 1.0)):
            for sy in (-1.0, 1.0):
                cy_ = sy * W / 2
                # the leg on the end face (square to x) and the leg on the side (square to y)
                vbox(part, [min(cx_, cx_ + sx * at_), min(cy_, cy_ - sy * al), z_lo],
                     [max(cx_, cx_ + sx * at_), max(cy_, cy_ - sy * al), z_hi], "Iron")
                vbox(part, [min(cx_, cx_ - sx * al), min(cy_, cy_ + sy * at_), z_lo],
                     [max(cx_, cx_ - sx * al), max(cy_, cy_ + sy * at_), z_hi], "Iron")
                for zz in zbs:
                    if not (sx > 0 and abs(zz - (zb + 0.45 * Hs)) < 9.0 * IN):
                        bolt_head(part, [cx_ + sx * at_, cy_ - sy * al / 2, zz], sx * EX, bd)
                    bolt_head(part, [cx_ - sx * al / 2, cy_ + sy * at_, zz], sy * EY, bd)
        # the band round the sides and after end at half height, and a rib up the middle of each side
        bw_, bt_ = (v * IN for v in dt["band_in"])
        zm = zb + 0.5 * (Hs + 1.0 * IN)
        xm = 0.5 * (xa + xf)
        for sy in (-1.0, 1.0):
            vbox(part, [xa + al, min(sy * W / 2, sy * (W / 2 + bt_)), zm - bw_ / 2],
                 [xf - al, max(sy * W / 2, sy * (W / 2 + bt_)), zm + bw_ / 2], "Iron")
            br_ = bt_ - 0.1 * IN                           # the rib a little less proud than the band it passes under
            vbox(part, [xm - bw_ / 2, min(sy * W / 2, sy * (W / 2 + br_)), z_lo],
                 [xm + bw_ / 2, max(sy * W / 2, sy * (W / 2 + br_)), z_hi], "Iron")
            for x_b in np.linspace(xa + al + 3.0 * IN, xf - al - 3.0 * IN, 5):
                if abs(x_b - xm) > bw_:
                    bolt_head(part, [x_b, sy * (W / 2 + bt_), zm], sy * EY, bd)
            for zz in zbs:
                if abs(zz - zm) > bw_:
                    bolt_head(part, [xm, sy * (W / 2 + br_), zz], sy * EY, bd)
            bolt_head(part, [xm, sy * (W / 2 + bt_), zm], sy * EY, 1.3 * bd)
        vbox(part, [xa - bt_, -W / 2 + al, zm - bw_ / 2], [xa, W / 2 - al, zm + bw_ / 2], "Iron")
        for y_b in np.linspace(-W / 2 + al + 3.0 * IN, W / 2 - al - 3.0 * IN, 4):
            bolt_head(part, [xa - bt_, y_b, zm], -EX, bd)
        # the top plate's fiddle bar round its edge, on short posts
        fh, ft = (v * IN for v in dt["fiddle_in"])
        zt = zb + Hs
        xa_t, xf_t, yt = xa - 0.75 * IN, xf + 0.75 * IN, W / 2 + 0.75 * IN
        ring = np.array([[xa_t + ft / 2, -yt + ft / 2], [xf_t - ft / 2, -yt + ft / 2], [xf_t - ft / 2, yt - ft / 2],
                         [xa_t + ft / 2, yt - ft / 2]])
        for j in range(4):
            a_, b_ = ring[j], ring[(j + 1) % 4]
            d = unit(np.append(b_ - a_, 0.0))
            bar(part, np.append(a_, zt + fh - ft / 2) - d * ft / 2, np.append(b_, zt + fh - ft / 2) + d * ft / 2, ft, ft,
                "Iron")
        for a_ in ring:
            vbox(part, [a_[0] - ft / 2, a_[1] - ft / 2, zt - 0.1 * IN], [a_[0] + ft / 2, a_[1] + ft / 2, zt + fh - ft],
                 "Iron")
        # the boilers' lids, each with a ring handle
        rl = gl["lid_in"] / 2 * IN
        nl = gl["lids"]
        cv = self.dk.items["Chimney"]
        xflue = cv["x"]
        rflue = gl["flue_in"] / 2 * IN
        lid_x = np.linspace(xa + rl + 4.0 * IN, xflue - rflue - rl - 3.0 * IN, nl)
        for x in lid_x:
            lathe(part, [x, 0.0, zb + Hs - 0.1 * IN], EZ, EX, [(0.0, rl), (0.6 * IN, rl), (0.9 * IN, rl - 1.0 * IN),
                                                                (1.2 * IN, 2.0 * IN), (1.6 * IN, 1.0 * IN)], "Iron", 24)
            ring_band(part, np.array([x, 0.0, zb + Hs + 2.2 * IN]), EY, EX, 0.0, 1.6 * IN, 0.4 * IN, 0.4 * IN, "Iron", 12)
        # the fore face: the fire's mouth (open, its grate's bars across it) and the oven's door beside it, each in a
        # frame; the ash pit's door under the fire
        xface = xf + 0.75 * IN
        fz = zb + 0.45 * Hs
        hg = dt["hinge"]
        for yc, (dw, dh), zc, shut in ((-W / 4, (12.0 * IN, 10.0 * IN), fz, False),
                                       (W / 4, (14.0 * IN, 12.0 * IN), fz, True)):
            vbox(part, [xf - 0.5 * IN, yc - dw / 2 - 1.5 * IN, zc - dh / 2 - 1.5 * IN],
                 [xface, yc + dw / 2 + 1.5 * IN, zc + dh / 2 + 1.5 * IN], "Iron")
            for sy_, sz_ in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                bolt_head(part, [xface, yc + sy_ * (dw / 2 + 0.75 * IN), zc + sz_ * (dh / 2 + 0.75 * IN)], EX, bd)
            if shut:
                vbox(part, [xface, yc - dw / 2, zc - dh / 2], [xface + 0.5 * IN, yc + dw / 2, zc + dh / 2], "Iron")
                self.door_furniture(part, xface + 0.5 * IN, yc - dw / 2, yc + dw / 2, zc, dh, hg)
            else:
                quad(part, [[xface + 0.02 * IN, yc - dw / 2, zc - dh / 2], [xface + 0.02 * IN, yc + dw / 2, zc - dh / 2],
                            [xface + 0.02 * IN, yc + dw / 2, zc + dh / 2], [xface + 0.02 * IN, yc - dw / 2, zc + dh / 2]],
                     EX, "Shadow")
                gr = dt["grate_bar_in"] / 2 * IN
                for zg_ in np.linspace(zc - dh / 2 + 1.0 * IN, zc + 1.0 * IN, dt["grate_bars"]):
                    lathe(part, [xface + 0.35 * IN, yc - dw / 2 - 0.5 * IN, zg_], EY, EZ,
                          [(0.0, gr), (dw + 1.0 * IN, gr)], "Iron", 6)
                # the ash pit's door under it
                aw, ah = (v * IN for v in dt["ash_door_in"])
                za = zb + 2.0 * IN + 1.25 * IN + ah / 2
                vbox(part, [xf - 0.5 * IN, yc - aw / 2 - 1.0 * IN, za - ah / 2 - 1.0 * IN],
                     [xface, yc + aw / 2 + 1.0 * IN, za + ah / 2 + 1.0 * IN], "Iron")
                vbox(part, [xface, yc - aw / 2, za - ah / 2], [xface + 0.4 * IN, yc + aw / 2, za + ah / 2], "Iron")
                lathe(part, [xface + 0.4 * IN, yc + aw / 2 - 1.5 * IN, za], EX, EY,
                      [(0.0, 0.45 * IN), (0.6 * IN, 0.3 * IN), (0.9 * IN, 0.55 * IN), (1.2 * IN, 0.4 * IN)], "Iron", 8)
        # the rail: round the sides and the after end on iron stanchions, open across the front
        rw, rt_ = (v * IN for v in gl["rail_in"])
        ro = gl["rail_out_in"] * IN
        zr = z0 + gl["rail_high_in"] * IN
        xr0, xr1 = xa - hm - ro, xf + 2.0 * IN
        yr = W / 2 + hm + ro
        path = np.array([[xr1, -yr, zr], [xr0, -yr, zr], [xr0, yr, zr], [xr1, yr, zr]])
        for a_, b_ in zip(path[:-1], path[1:]):
            d = unit(b_ - a_)
            bar(part, a_ - d * rw / 2, b_ + d * rw / 2, rw, rt_, "Iron")
        for x, y in ((xr1 - 1.0 * IN, -yr), (0.5 * (xr0 + xr1), -yr), (xr0, -yr), (xr0, 0.0), (xr0, yr),
                     (0.5 * (xr0 + xr1), yr), (xr1 - 1.0 * IN, yr)):
            lathe(part, [x, y, z0 - 0.5 * IN], EZ, EX, [(0.0, 1.5 * IN), (0.5 * IN, 1.5 * IN), (0.6 * IN, 0.6 * IN),
                                                        (zr - z0 - rt_ / 2 + 0.5 * IN, 0.6 * IN)], "Iron", 8)
        self.drape(part, k0, z0)
        # the flue: from the stove's top (laid on the sheer) straight up into the chimney's plate, a collar at its foot,
        # a band at its middle and the damper's handle out of its fore side
        zst = zb + Hs + float(self.zg(xflue)) - z0
        zch = self.dk.chimney_plate_z(xflue) if hasattr(self.dk, "chimney_plate_z") else None
        if zch is None:
            ch = self.dk.items["Chimney"]
            zch = float(self.dk.z(xflue)) + ch["high"] - 0.05 * IN
        lathe(part, [xflue, 0.0, zst - 0.2 * IN], EZ, EX, [(0.0, rflue + 2.0 * IN), (0.8 * IN, rflue + 2.0 * IN),
                                                            (1.2 * IN, rflue), (zch - zst + 0.2 * IN + 0.25 * IN, rflue)],
              "Iron", 24)
        zmid = zst + 0.45 * (zch - zst)
        ring_band(part, np.array([xflue, 0.0, zmid]), EZ, EX, 0.0, rflue, 1.5 * IN, 0.35 * IN, "Iron", 24)
        for zz in (zmid - 0.5 * IN, zmid + 0.5 * IN):
            for a_ in np.arange(6) * math.pi / 3:
                bolt_head(part, [xflue + (rflue + 0.35 * IN) * math.cos(a_), (rflue + 0.35 * IN) * math.sin(a_), zz],
                          [math.cos(a_), math.sin(a_), 0.0], 0.55 * bd, seg=6)
        zd = zst + 0.25 * (zch - zst)
        dl = dt["damper_handle_in"] * IN
        lathe(part, [xflue + rflue - 0.5 * IN, 0.0, zd], EX, EY, [(0.0, 0.3 * IN), (dl, 0.3 * IN)], "Iron", 8)
        lathe(part, [xflue + rflue - 0.5 * IN + dl, 0.0, zd], EX, EY,
              [(0.0, 0.6 * IN), (0.6 * IN, 0.75 * IN), (1.6 * IN, 0.75 * IN), (2.0 * IN, 0.45 * IN)], "Iron", 10)
        self.galley_box = (xa - hm - ro - 1.0 * IN, xf + 1.0 * IN + 0.5 * IN, yr + 1.0 * IN)
        self.info["galley"] = {"x_m": [xa, xf], "flue_x_m": round(xflue, 3), "flue_m": [round(zst, 3), round(zch, 3)],
                               "front_out_m": round(xface + 1.5 * IN - xf, 3)}

    def door_furniture(self, part, x_face, y_hinge, y_latch, zc, dh, hg):
        """an iron door's two strap hinges (knuckle on its hinge edge y_hinge, the strap reaching hg['strap_of_width']
        across) and its latch (a turned knob near y_latch), on its face at x_face"""
        sw, st_ = (v * IN for v in hg["strap_in"])
        rk = hg["knuckle_in"] / 2 * IN
        L = (y_latch - y_hinge) * hg["strap_of_width"]
        for zz in (zc - dh / 2 + 1.5 * IN + sw / 2, zc + dh / 2 - 1.5 * IN - sw / 2):
            prism(part, [(y_hinge, zz - sw / 2), (y_hinge + L - sw, zz - sw / 2), (y_hinge + L, zz),
                         (y_hinge + L - sw, zz + sw / 2), (y_hinge, zz + sw / 2)], x_face - 0.05 * IN, x_face + st_, "Iron",
                  axis=0)
            lathe(part, [x_face + rk - 0.1 * IN, y_hinge - rk, zz - sw], EZ, EX, [(0.0, rk), (2 * sw, rk)], "Iron", 10)
            for f in (0.3, 0.6):
                bolt_head(part, [x_face + st_, y_hinge + f * L, zz], EX, 0.5 * sw, seg=6)
        lathe(part, [x_face, y_latch - 2.0 * IN, zc], EX, EY, [(0.0, 0.5 * IN), (0.8 * IN, 0.35 * IN), (1.2 * IN, 0.7 * IN),
                                                                (1.5 * IN, 0.5 * IN)], "Iron", 10)
        vbox(part, [x_face - 0.05 * IN, y_latch - 3.2 * IN, zc - 0.35 * IN], [x_face + 0.3 * IN, y_latch - 0.8 * IN,
                                                                                zc + 0.35 * IN], "Iron")

    # --- the bow --------------------------------------------------------------------------------------------------------
    def bow(self, part, wells):
        """the manger across the bow abaft the hawse holes, the cable scuttles' lead collars and their short wells"""
        bw = self.c["bow"]
        xm = bw["manger_x_m"]
        hm, tm = (v * IN for v in bw["manger_in"])
        # each face's outline on its own: its foot half an inch into the deck at that face's x (the sheer is steep
        # this far forward), its ends a quarter inch into the side's inner face, which flares out from the deck to its
        # top and is wider at the after face than the fore one
        rings, ye = [], 9.0
        for x in (xm - tm / 2, xm + tm / 2):
            zz = float(self.zg(x)) + np.linspace(-0.5 * IN, hm, 6)
            ys = self.wall_at(np.full(6, x), zz)[0][:, 1] + 0.25 * IN
            poly = [(-ys[0], zz[0])] + [(ys[k], zz[k]) for k in range(6)] + [(-ys[k], zz[k]) for k in range(5, 0, -1)]
            rings.append(np.array([[x, y, z] for y, z in poly]))
            ye = min(ye, float(ys.min()))
        solid(part, rings, "Oak")
        self.manger = (xm, tm, ye)
        xs, ys = bw["scuttle_at_m"]
        r = bw["scuttle_in"] / 2 * IN
        cw, ct = (v * IN for v in bw["collar_in"])
        for sy in (1.0, -1.0):
            c = np.array([xs, sy * ys, float(self.zg(xs))])
            # the collar, the lining and the well's dark foot built level, then laid along the sheer (steep this far
            # forward: the collar's 2 ft across rises 2.5 in)
            k0 = len(part.V)
            ring_band(part, c, EZ, EX, ct / 2 - 0.02 * IN, r, ct, cw, "Lead", 32)
            # the lead lining down the hole and a short well below (the cable tier is slice 14's)
            revolve(part, c - EZ * (bw["well_ft"] * FT), EZ, EX, [(0.0, r - 0.25 * IN), (bw["well_ft"] * FT + 0.0, r - 0.25 * IN)],
                    "Lead", 32, want_out=False)
            k1 = len(wells.V)
            disc(wells, c - EZ * (bw["well_ft"] * FT), EZ, r, "Shadow", 24)
            self.drape(part, k0, float(c[2]))
            self.drape(wells, k1, float(c[2]))
        self.info["bow"] = {"manger_x_m": xm, "manger_half_m": round(ye, 3)}

    # --- the bowers' cables -----------------------------------------------------------------------------------------------
    def cable_course(self, an):
        """the bowers' cables led in on this deck (starboard; anchors.py lays both): from where each lies in its bore's
        inner mouth (an.bore_lie) out over the lip, over the manger's top and down its cable scuttle into the well, each
        turn bent no tighter than the cable's least bend (anchors_1797.json); the lift over the manger, the corner over
        the scuttle and the place the cable goes down it are the first (shortest) that clear the board, the deck, the
        scuttle's lead collar and its lining. Returns the course from its inboard end (in the well) to the bore, for
        an.lead_inboard"""
        import anchors as anm
        bw = self.c["bow"]
        xm, tm, ye = self.manger
        hm = bw["manger_in"][0] * IN
        zm = float(self.zg(xm))
        xs, ys = bw["scuttle_at_m"]
        r = bw["scuttle_in"] / 2 * IN
        cw, ct = (v * IN for v in bw["collar_in"])
        well = bw["well_ft"] * FT
        zsd = float(self.zg(xs))
        top = zm + hm
        B, d_in, r_c = an.bore_lie(np.array([xm, ys, top]))
        cc = an.card["cable"]
        R = cc["bend_min_of_diameter"] * 2 * r_c
        r_l = r - 0.25 * IN                                  # the scuttle's lining's inside
        gap = 0.003

        def clear(C):
            """the least room (m, past the cable's surface) to the manger, the deck, the collar and the lining"""
            worst = {}
            # the manger: a board across, its top at `top`
            dx = np.maximum(np.abs(C[:, 0] - xm) - tm / 2, 0.0)
            dz = np.maximum(C[:, 2] - top, 0.0) + np.maximum(zm - 0.5 * IN - C[:, 2], 0.0)
            dy = np.maximum(np.abs(C[:, 1]) - ye, 0.0)
            worst["manger"] = float((np.sqrt(dx ** 2 + dy ** 2 + dz ** 2) - r_c).min())
            rho = np.hypot(C[:, 0] - xs, C[:, 1] - ys)
            zdeck = self.zg(C[:, 0])
            out_hole = rho > r_l
            # the deck (outside the scuttle's collar) and the collar's top (on it)
            ztop = np.where(rho < r - 0.002 + cw, zsd + ct - 0.02 * IN, zdeck)
            worst["deck"] = float((C[out_hole, 2] - ztop[out_hole] - r_c).min()) if out_hole.any() else 1.0
            # the collar's inner top edge (the lip the cable turns down over)
            lip = np.stack([rho - (r - 0.002), C[:, 2] - (zsd + ct - 0.02 * IN)], -1)
            worst["lip"] = float((np.linalg.norm(lip, axis=1) - r_c).min())
            # the lining, below the deck
            below = C[:, 2] < zsd
            worst["lining"] = float((r_l - rho[below] - r_c).min()) if below.any() else 1.0
            return worst

        best = None
        for lift in np.arange(0.0, 0.08, 0.004):
            for h3 in np.arange(0.0, 0.4, 0.02):
                for fv in (0.3, 0.45, 0.6, 0.75):
                    dv = -fv * (r_l - r_c)
                    K4 = np.array([xs + dv, ys, zsd - well + 0.12])
                    K3 = np.array([xs + dv, ys, zsd + h3])
                    y2 = ys + (B[1] - ys) * (xm - xs) / (B[0] - xs)
                    K2 = np.array([xm, y2, top + r_c + gap + lift])
                    K1 = B + 0.08 * d_in
                    poly = [K4, K3, K2, K1, B]
                    C, least = anm._course(poly, R, 0.02)
                    w = clear(C)
                    if min(w.values()) >= gap and least >= R - 1e-6:
                        L = float(np.sum(np.linalg.norm(np.diff(C, axis=0), axis=1)))
                        if best is None or L < best[0] - 1e-4:
                            best = (L, poly, w, least, (lift, h3, fv))
                if best is not None:
                    break
            if best is not None:
                break
        if best is None:
            raise SystemExit("gundeck: no course for the cable over the manger and down the scuttle clears them")
        L, poly, w, least, knobs = best
        self.info["cables"] = {"course_m": [np.round(p, 3).tolist() for p in poly], "length_on_deck_m": round(L, 2),
                               "room_m": {k: round(v, 4) for k, v in w.items()},
                               "least_bend_of_diameter": round(least / (2 * r_c), 3),
                               "lift_over_manger_m": round(knobs[0], 3), "corner_over_scuttle_m": round(knobs[1], 3)}
        return poly

    def lead_bushes(self, part):
        """a lead bush round each of the tiller rope's legs where they pass down through this deck: lining the hole,
        its flange on the deck"""
        th = self.c["deck"]["thick_in"] * IN
        for x, y, rr in self.dk.tiller_legs:
            c = np.array([x, y, float(self.zg(x))])
            ring_band(part, c, EZ, EX, -th / 2 + 0.1 * IN, rr + 0.25 * IN, th + 0.2 * IN, 0.5 * IN, "Lead", 16)
            ring_band(part, c, EZ, EX, 0.125 * IN - 0.02 * IN, rr + 0.25 * IN, 0.25 * IN, 1.75 * IN, "Lead", 16)

    def port_stops(self, part):
        """a stop round the inside of each gun port with a lid (card port_stops), for the shut lid to close against: the
        sill's and the head's from jamb to jamb, the jambs' between them (each a solid of its own, lapping the others).
        Laid on the side as the skin lays its lids (skin.Skin.lids: param x and z in px, the lid inset a quarter inch
        all round): each point on the moulded surface moved along its normal to the lid's inner face (the planking's
        thickness read at the nearest point of the lid, since the strakes under the sill and over the head are thicker
        than the port's band), then the stop's own depth in from there; mirrored to port. info port_stops: its sizes"""
        ps = self.c["port_stops"]
        sk, pr, SKM = self.sk, self.pr, self.SKM
        pin, e = pr.pxin, sk.inset
        p, s, off, let = ps["proud_in"], ps["deep_in"], ps["off_lid_in"], ps["let_in"]
        d_out, d_in = -off, -off - s                     # inches along the normal from the lid's inner face
        lo, hi = pr.S, pr.Shd                            # the sill and head lines (px; pr.gun's own ends are numbers)
        C = sk.C

        def pts(X, Z, dd, a, b):
            X, Z = np.asarray(X, float), np.asarray(Z, float)
            P, N = sk.surf(X, Z, True, 0, SKM.MOULD)
            Xc = np.clip(X, a + e, b - e)
            Zc = np.clip(Z, lo(Xc) + e, hi(Xc) - e)
            d = sk.pl.thick_in(Xc, Zc, np.ones(len(X), bool), np.zeros(len(X), int), grooves=False) - sk.lid_t
            return P + N * ((d + np.asarray(dd, float)) * IN)[:, None]

        dd = np.array([d_in, d_in, d_out, d_out])
        n = 0
        for a, b, _, _ in pr.gun:
            X = np.concatenate([[a - let * pin], C[(C > a + 0.15) & (C < b - 0.15)], [b + let * pin]])
            S, H = lo(X), hi(X)
            rings = [[pts([x] * 4, [z0, z1, z1, z0], dd, a, b) for x, z0, z1 in zip(X, S - let * pin, S + p * pin)],
                     [pts([x] * 4, [z0, z1, z1, z0], dd, a, b) for x, z0, z1 in zip(X, H - p * pin, H + let * pin)]]
            for x, x0, x1 in ((a, a - let * pin, a + p * pin), (b, b - p * pin, b + let * pin)):
                zs, zh = float(lo(np.array([x]))[0]), float(hi(np.array([x]))[0])
                rings.append([pts([x0, x1, x1, x0], [z] * 4, dd, a, b)
                              for z in np.linspace(zs + (p - 0.1) * pin, zh - (p - 0.1) * pin, 9)])
            for R in rings:
                for sgn in (1.0, -1.0):
                    solid(part, [r * [1.0, sgn, 1.0] for r in R], "HullRed")
            n += 1
        self.info["port_stops"] = {"ports_each_side": n, "lap_over_lid_in": round(p - 0.25, 2),
                                   "off_lid_in": off, "deep_in": s, "let_into_lining_in": let}

    # --- the great cabin ------------------------------------------------------------------------------------------------
    def aft_rows(self):
        """the gun rows' aft ends (x, y, z), low to high: the after wall's starboard edge (skin.Skin.bulkheads carries
        each straight across the ship)"""
        P = np.array([r[0] for r in self.rows.values()])
        return P[np.argsort(P[:, 2])]

    def wall_x(self, z):
        """the after wall's x at height z"""
        A = self.aft_rows()
        return np.interp(z, A[:, 2], A[:, 0])

    def window_rects(self):
        """the stern windows' glass on the stern face: (u0, u1, v0, v1) each, u across and v up (m: the face's chart,
        stern.Face; decor_1797.json stern.windows)"""
        w = self.decor["stern"]["windows"]
        out = []
        for a, b in w["u_m"]:
            out.append((a, b))
            if a > 0:
                out.append((-b, -a))
        v0, v1 = w["z_m"]
        return [(a, b, v0, v1) for a, b in sorted(out)]

    @staticmethod
    def edges(a, b, v0, v1, step):
        """a rectangle's four edges in (u, v), each sampled step apart: bottom (left to right), right (up), top (right
        to left), left (down); each from its corner to the next"""
        def seg(p, q):
            n = max(int(math.ceil(np.linalg.norm(np.subtract(q, p)) / step)), 1)
            return np.array([np.add(p, np.subtract(q, p) * (k / n)) for k in range(n + 1)])
        return [seg((a, v0), (b, v0)), seg((b, v0), (b, v1)), seg((b, v1), (a, v1)), seg((a, v1), (a, v0))]

    def window_loop(self, r, grow=0.0, step=0.06):
        a, b, v0, v1 = r
        E = self.edges(a - grow, b + grow, v0 - grow, v1 + grow, step)
        return np.concatenate([e[:-1] for e in E])

    def rudder_head(self):
        """the rudder's head above the deck: (its fore face's x, its half-width, its top)"""
        V = np.asarray(self.skin_parts["Rudder"][0], float)
        za = float(self.gun[0, 2])
        m = V[:, 2] > za - 0.05
        return float(V[m, 0].max()), float(np.abs(V[m, 1]).max()), float(V[:, 2].max())

    def after_wall(self, part):
        """the after wall (the skin leaves the gun deck's aft end open for it): straight across between the gun rows'
        aft ends and raked as they are, from the deck up to the spar deck's planks, the stern windows' openings through
        it (each reveal_in larger all round than its glass) and a notch at its foot where the rudder's head comes up
        (the window seat boxes it in)"""
        A = self.aft_rows()
        rv = self.c["cabin"]["after_wall"]["reveal_in"] * IN
        xr, yr, ztr = self.rudder_head()
        g = 1.0 * IN
        z0 = float(A[0, 2]) - 0.25 * IN                     # a quarter inch into the deck (straight down: wall_x)
        right = [(float(A[0, 1]), z0)] + [(float(p[1]), float(p[2])) for p in A]
        notch = [(-yr - g, z0), (-yr - g, ztr + g), (yr + g, ztr + g), (yr + g, z0)]
        outline = [(-right[0][0], z0)] + notch + right + [(-y, z) for y, z in right[::-1]][:-1]
        holes = [self.window_loop(r, rv, 0.1) for r in self.window_rects()]
        P2, T = cdt(densify(np.array(outline), 0.3), holes, 0.25)
        V = np.column_stack([self.wall_x(P2[:, 1]), P2[:, 0], P2[:, 1]])
        n = np.cross(V[T[0, 1]] - V[T[0, 0]], V[T[0, 2]] - V[T[0, 0]])
        F = [tuple(t) for t in T] if n[0] > 0 else [tuple(t[::-1]) for t in T]
        part.add(V, F, "Interior")
        self.info["after_wall"] = {"z_m": [round(z0, 3), round(float(A[-1, 2]), 3)],
                                   "x_m": [round(float(A[-1, 0]), 3), round(float(A[0, 0]), 3)],
                                   "rudder_notch_m": [round(yr + g, 3), round(ztr + g, 3)]}

    def reveals(self, part):
        """each stern window's reveal, lined with board lining_in thick: a closed frame of four boards mitred at the
        corners, from the glass's back (the glass, sash and casing are laid from GLASS_BACK_M inside the stern face,
        stern.Stern.windows; the transom is cut for the glass) to the after wall's opening (reveal_in larger all round
        than the glass), the boards' backs on the openings' edges and their faces lining_in inside them, so where the
        lining butts on the glass it is behind the sash's frame (decor_1797.json stern.windows sash_m)"""
        ca = self.c["cabin"]["after_wall"]
        rv, t = ca["reveal_in"] * IN, ca["lining_in"] * IN
        sash = self.decor["stern"]["windows"]["sash_m"][0]
        if t >= sash:
            raise SystemExit(f"gundeck: the reveals' lining ({ca['lining_in']} in) would show past the sash's frame "
                             f"({sash} m)")
        for r in self.window_rects():
            a, b, v0, v1 = r
            uc, vc = 0.5 * (a + b), 0.5 * (v0 + v1)
            counts = [len(e) - 1 for e in self.edges(a, b, v0, v1, 0.06)]

            def loop(g, at_face):
                E = self.edges(a - g, b + g, v0 - g, v1 + g, 1.0)
                P = []
                for e, n in zip(E, counts):
                    P += [e[0] + (e[-1] - e[0]) * (k / n) for k in range(n)]
                P = np.array(P)
                if at_face:
                    return self.face.at(P, GLASS_BACK_M)
                return np.column_stack([self.wall_x(P[:, 1]), P[:, 0], P[:, 1]])
            Of, Ow, If, Iw = loop(0.0, True), loop(rv, False), loop(-t, True), loop(rv - t, False)
            n = len(Of)
            V = np.concatenate([Of, Ow, If, Iw])
            o_f, o_w, i_f, i_w = 0, n, 2 * n, 3 * n
            axis0, axis1 = Of.mean(0), Ow.mean(0)
            d = unit(axis1 - axis0)
            nf = self.face.n_at(np.array([[uc, vc]]))[0]
            F = []
            for i in range(n):
                j = (i + 1) % n
                for q, out in (((o_f + i, o_f + j, o_w + j, o_w + i), 1.0),        # the back: away from the opening
                               ((i_f + i, i_f + j, i_w + j, i_w + i), -1.0),       # the face: into the opening
                               ((o_f + i, o_f + j, i_f + j, i_f + i), None),       # on the glass: aft
                               ((o_w + i, o_w + j, i_w + j, i_w + i), None)):      # at the wall: into the cabin
                    P = V[list(q)]
                    nq = np.cross(P[2] - P[0], P[3] - P[1])
                    c = P.mean(0)
                    if out is not None:
                        r_ = c - axis0 - ((c - axis0) @ d) * d
                        want = out * r_
                    else:
                        want = nf if q[0] < n else -nf
                    F.append(q if nq @ want > 0 else q[::-1])
            part.add(V, F, "Interior")
        self.info["reveals"] = {"lining_in": ca["lining_in"], "glass_back_m": GLASS_BACK_M, "windows": len(self.window_rects())}

    def holed_transom(self, V, F):
        """the transom (loft's: a grid of quads, row by row up the stern face, each row level) with the stern windows cut
        through it: the rows over the windows' band triangulated again round the openings (stern.Face maps the new
        points), the others kept; returns (V, F)"""
        V = np.asarray(V, float)
        nY = F[0][1] - F[0][0]
        nJ = len(V) // nY
        G = V.reshape(nJ, nY, 3)
        zr = G[:, 0, 2]
        rects = self.window_rects()
        lo = min(r[2] for r in rects) - 0.12
        hi = max(r[3] for r in rects) + 0.12
        j0 = int(np.nonzero(zr <= lo)[0].max())
        j1 = int(np.nonzero(zr >= hi)[0].min())
        keep = [f for k, f in enumerate(F) if not (j0 <= k // (nY - 1) < j1)]
        idx = [j0 * nY + c for c in range(nY)] + [j * nY + nY - 1 for j in range(j0 + 1, j1)] + \
              [j1 * nY + c for c in range(nY - 1, -1, -1)] + [j * nY for j in range(j1 - 1, j0, -1)]
        O = V[idx][:, 1:3]
        if np.sum(O[:, 0] * np.roll(O[:, 1], -1) - np.roll(O[:, 0], -1) * O[:, 1]) < 0:
            raise SystemExit("gundeck: the transom's band outline runs clockwise")
        holes = [self.window_loop(r, 0.0, 0.06) for r in rects]
        P2, T = cdt(O, holes, 0.12)
        no = len(O)
        new = self.face.xyz(P2[no:, 0], P2[no:, 1])
        to = np.array(idx + list(range(len(V), len(V) + len(new))))
        Vn = np.concatenate([V, new])
        Tn = to[T]
        # the triangles face out of the stern (aft) as the kept quads do
        nrm = np.cross(Vn[Tn[:, 1]] - Vn[Tn[:, 0]], Vn[Tn[:, 2]] - Vn[Tn[:, 0]]).sum(0)
        f0 = keep[0]
        n0 = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
        if (nrm @ n0) < 0:
            Tn = Tn[:, ::-1]
        self.info["transom"] = {"rows_retriangulated": [j0, j1], "triangles": len(Tn)}
        return Vn, keep + [tuple(int(i) for i in t) for t in Tn]

    def partition(self, part, x, t, y_in, doors=(), mat="Interior"):
        """a partition across the ship at x, t thick: from y_in out to the starboard side (y_in None: from side to
        side), sitting a quarter inch into the deck and up to the spar deck's planks; at the side scribed a quarter inch
        into the waterway's cove, let a quarter inch into the side and the clamp; doors [(y0, y1, height)] notched up
        from its foot. Returns its outline (y, z)"""
        let = 0.25 * IN
        zg, zt = float(self.zg(x)), float(self.zsu(x))
        prof = np.array(self.c["deck"]["waterway"]["profile_in"], float) * IN
        th = self.c["overhead"]["clamp_in"][1] * IN
        Xc, Zb, _ = self.clamp
        zcb = float(np.interp(x, Xc, Zb))
        yw0 = float(self.wall_at(np.array([x]), np.array([zg]))[0][0, 1])
        zz = np.linspace(zg + prof[0, 1], zcb, 8)
        Pw, _ = self.wall_at(np.full(8, x), zz)
        ycl = float(self.wall_at(np.array([x]), np.array([zcb]))[0][0, 1]) - th + let

        def side():                                      # the starboard end, from the foot up to the top
            pts = [(yw0 - prof[-1, 0], zg - let)] + [(yw0 - w, zg + h - let) for w, h in prof[::-1] if h > 0.0]
            pts += [(float(Pw[k, 1]) + let, float(zz[k])) for k in range(1, 8)]
            pts += [(ycl, zcb), (ycl, zt)]
            return pts
        st = side()
        # above the clamp (its top at the beams' underside) out to the side again, so no gap is left there
        zct = self.beam_bottom(x)
        if zct < zt - 0.01:
            ywt = self.wall_at(np.array([x, x]), np.array([zct, zt]))[0][:, 1]
            st = st[:-1] + [(ycl, zct), (float(ywt[0]) + let, zct), (float(ywt[1]) + let, zt)]
        bottom = []
        y0 = -st[0][0] if y_in is None else y_in
        for d0, d1, h in sorted(doors):
            bottom += [(d0, zg - let), (d0, zg + h), (d1, zg + h), (d1, zg - let)]
        if y_in is None:
            port = [(-y, z) for y, z in st[::-1]]
            poly = [(y0, zg - let)] + bottom + st + port[:-1]
        else:
            poly = [(y0, zg - let)] + bottom + st + [(y0, zt)]
        P = np.array(poly)
        prism(part, P, x - t / 2, x + t / 2, mat, axis=0)
        return P

    def bulkhead(self, part, doors_part):
        """the great cabin's bulkhead across the ship: panelled on both faces, a door either side of the tiller rope's
        legs (each door its own part, hung on its outboard post: a turn about its own Z opens it aft into the cabin).
        Each door's hinge pins stand on the bulkhead's after face at the opening's outboard edge, the leaf set in from
        that face (door_hang), so it swings aft clear of its jamb and casing; a low sill across the doorway, and the
        leaf's foot clear of the sill and of the floor cloth where the deck rises aft under its swing"""
        cb = self.c["cabin"]
        xb = cb["bulkhead_x_m"]
        t = cb["bulkhead_in"] * IN
        zg, zt = float(self.zg(xb)), float(self.zsu(xb))
        ds = []
        for d in cb["doors"]:
            y0, y1 = d["y_m"]
            ds += [(y0, y1, d["high_in"] * IN), (-y1, -y0, d["high_in"] * IN)]
        self.partition(part, xb, t, None, ds)
        # the panelling: stiles and rails proud of each face, broken at the doors
        pn = cb["panel"]
        sw, pr = pn["stile_in"] * IN, pn["proud_in"] * IN
        H = zt - zg
        Xc, Zb, _ = self.clamp
        zcb = float(np.interp(xb, Xc, Zb))
        th = self.c["overhead"]["clamp_in"][1] * IN

        def ye(z):                                         # how far out the panelling runs at height z
            yw = float(self.wall_at(np.array([xb]), np.array([min(z, zcb)]))[0][0, 1])
            return (yw - th if z > zcb else yw) - 3.5 * IN
        z_rails = [zg + 2.0 * IN] + [zg + f * H for f in pn["rows"]] + [zt - sw / 2 - 0.5 * IN]
        door_spans = [(a, b, h) for a, b, h in ds]
        for face in (1.0, -1.0):
            xf = xb + face * t / 2
            x0, x1 = (xf, xf + pr) if face > 0 else (xf - pr, xf)
            # the rails and the doors' heads stand a little less proud than the stiles and end inside them, so no two
            # faces lie in one plane where they cross (they flickered there)
            r0, r1 = (xf, xf + 0.7 * pr) if face > 0 else (xf - 0.7 * pr, xf)
            lap = 0.25 * IN
            for zr in z_rails:
                y_e = ye(zr)
                cuts = sorted([(a, b) for a, b, h in door_spans if zr - sw / 2 < zg + h])
                spans, cur = [], -y_e
                for a, b in cuts:
                    spans.append((cur, a - sw + lap))
                    cur = b + sw - lap
                spans.append((cur, y_e))
                for a, b in spans:
                    if b - a > 0.05:
                        vbox(part, [r0, a, zr - sw / 2], [r1, b, zr + sw / 2], "Interior")
            # stiles: either side of each door (its casing) and every 0.8 m between, up to just under the top rail's top
            stiles = []
            for a, b, h in door_spans:
                stiles += [a - sw / 2, b + sw / 2]
                vbox(part, [r0, a - sw + lap, zg + h], [r1, b + sw - lap, zg + h + sw], "Interior")   # the door's head
            for y in np.arange(1.75, ye(zg + H / 2) - 3.0 * IN, 0.8):
                stiles += [y, -y]
            for y in stiles:
                vbox(part, [x0, y - sw / 2, zg], [x1, y + sw / 2, z_rails[-1] + sw / 2 - lap], "Interior")
        # the doors: each a leaf in its opening, shut, on its own frame (origin on its hinge pins' axis at the deck, X
        # across the leaf toward the latch, Z up, Y = Z x X: forward for the starboard door, aft for the port one)
        dt = cb["door_in"] * IN
        dh = cb["door_hang"]
        sill, under, recess = (dh[k] * IN for k in ("sill_in", "under_in", "recess_in"))
        g_hinge, g_latch = dh["hinge_gap_in"] * IN, dh["latch_gap_in"] * IN
        k_d, k_l = (v * IN for v in dh["knuckle_in"])
        cloth = cb["floor_cloth"]["thick_in"] * IN
        let = 0.25 * IN
        x_a = xb - t / 2                                           # the bulkhead's after face: the pins' axis
        self.door_frames = {}
        for (a, b, h), side in zip(ds, ("S", "P")):
            hinge_y = b if side == "S" else a                      # the outboard post
            latch = -1.0 if side == "S" else 1.0
            wd = b - a
            z0 = float(self.zg(x_a))
            o = np.array([x_a, hinge_y, z0])
            X = latch * EY
            Z = EZ
            Y = np.cross(Z, X)
            R = np.column_stack([X, Y, Z])
            fwd = float(Y @ EX)                                    # +1 when the frame's Y points forward
            # the sill across the doorway, let into the deck; the floor under the leaf's swing aft (the deck rising
            # aft, the cloth on it); the leaf's foot under_in over the higher of the two
            vbox(part, [x_a, a, zg - let], [x_a + t, b, zg + sill], "Oak")
            xs = np.linspace(x_a - wd - 0.05, x_a, 40)
            floor = float(np.max(self.zg(xs))) + cloth
            foot = max(zg + sill, floor) + under - z0
            top = zg + h - 0.15 * IN - z0
            # the leaf, set in recess_in from the after face (toward the bulkhead's middle)
            y0_, y1_ = sorted((fwd * recess, fwd * (recess + dt)))
            yc = 0.5 * (y0_ + y1_)
            dp = Part()
            vbox(dp, [g_hinge, y0_, foot], [wd - g_latch, y1_, top], "Interior")
            hl = top - foot
            for zc, hh in ((foot + 0.28 * hl, 0.4 * hl), (foot + 0.74 * hl, 0.36 * hl)):   # two raised panels each face
                for fy in (1.0, -1.0):
                    yy = yc + fy * dt / 2
                    vbox(dp, [0.2 * wd, min(yy, yy + fy * 0.3 * IN), zc - hh / 2], [0.8 * wd, max(yy, yy + fy * 0.3 * IN),
                                                                                   zc + hh / 2], "Interior")
            for fy in (1.0, -1.0):                                   # a brass knob each side near the latch
                lathe(dp, [wd - 3.0 * IN, yc + fy * dt / 2 - fy * 0.1 * IN, 36.0 * IN], fy * EY, EX,
                      [(0.0, 0.4 * IN), (0.9 * IN, 0.35 * IN), (1.2 * IN, 0.9 * IN), (2.0 * IN, 0.9 * IN),
                       (2.2 * IN, 0.5 * IN)], "Bronze", 12)
            # the hinges' knuckles on the pins' axis, against the casing (the bulkhead's: they stay as the leaf turns)
            for zk in (foot + 9.0 * IN, top - 9.0 * IN):
                lathe(part, [x_a, hinge_y, z0 + zk - k_l / 2], EZ, EX,
                      [(0.0, k_d / 2), (k_l, k_d / 2)], "Iron", 10)
            name = "CabinDoor_" + side
            self.parts_[name] = dp
            self.frames[name] = (o, R)
            sign = -1.0 if side == "S" else 1.0
            self.door_frames[name] = {"hinge_m": [round(float(v), 4) for v in o], "width_m": round(wd, 3),
                                      "high_m": round(h, 3), "foot_over_hinge_m": round(foot, 4),
                                      "sill_top_m": round(zg + sill, 4), "floor_under_swing_m": round(floor, 4),
                                      "open_sign": sign, "open_deg": dh["open_deg"],
                                      "opens": "a turn about its own Z by open_sign x up to open_deg swings it aft "
                                               "into the cabin"}
        self.info["cabin_doors"] = self.door_frames

    def top_under_members(self, xs, y):
        """the partitions' top along x at |y|: the spar deck's planks, stepping down under each beam or ledge that
        crosses there (points (x, z) in x order)"""
        cuts = []
        for i, (x, s, m, kind) in enumerate(self.members):
            if kind == "gangway":
                continue
            if i in self.cut and abs(y) < self.cut[i]:
                continue
            cuts.append((x - s / 2, x + s / 2, m))
        x0, x1 = min(xs), max(xs)
        pts = [x0, x1] + [v for a, b, m in cuts for v in (a, b) if x0 < v < x1]
        out = []
        for x in sorted(set(round(v, 6) for v in pts)):
            for side in (-1e-4, 1e-4):
                xx = min(max(x + side, x0), x1)
                d = max([m for a, b, m in cuts if a < xx < b] or [0.0])
                out.append((xx, float(self.zsu(xx)) - d))
        # keep the steps: drop repeats
        res = [out[0]]
        for p in out[1:]:
            if abs(p[0] - res[-1][0]) > 1e-7 or abs(p[1] - res[-1][1]) > 1e-7:
                res.append(p)
        return res

    def state_rooms(self, part):
        """a state room in each quarter: its fore wall across from the inboard wall to the side, and its inboard wall
        fore and aft from there to the after wall (its top stepped round the beams over it), a door in it near the
        fore end, shut"""
        sr = self.c["cabin"]["state_rooms"]
        ys, xf = sr["y_m"], sr["fore_x_m"]
        t = sr["wall_in"] * IN
        let = 0.25 * IN
        hd = sr["door_high_in"] * IN
        d0, d1 = (xf - v for v in sr["door_aft_of_fore_m"][::-1])
        A = self.aft_rows()
        xe = xf + t / 2 + 0.25 * IN                    # the inboard wall's fore end, a little proud of the fore wall
        for sgn in (1.0, -1.0):
            sp = Part()
            self.partition(sp, xf, t, ys, ())            # from the middle of the inboard wall (no faces in one plane)
            # the inboard wall in (x, z): foot from the after wall forward (the door notched in it), the fore end up,
            # the top aft under the beams, then down the after wall's rake
            xa = float(self.wall_x(float(self.zg(self.x_aft)))) - let
            foot = [(x, float(self.zg(x)) - let) for x in np.linspace(xa, xe, 12)]
            foot = [p for p in foot if not (d0 - 0.01 < p[0] < d1 + 0.01)]
            door = [(d0, float(self.zg(d0)) - let), (d0, float(self.zg(d0)) + hd), (d1, float(self.zg(d1)) + hd),
                    (d1, float(self.zg(d1)) - let)]
            foot = [p for p in foot if p[0] < d0] + door + [p for p in foot if p[0] > d1]
            top = self.top_under_members([float(A[-1, 0]) - 0.5, xe], ys)
            top = [p for p in top if p[0] >= float(self.wall_x(p[1])) - let]
            rake = [(float(self.wall_x(z)) - let, float(z)) for z in A[::-1, 2] if z < top[0][1] - 1e-4]
            z_top_aft = top[0][1]
            poly = foot + top[::-1] + [(float(self.wall_x(z_top_aft)) - let, z_top_aft)] + rake
            P = np.array(poly)
            # drop points that repeat
            keep = [0] + [i for i in range(1, len(P)) if np.linalg.norm(P[i] - P[i - 1]) > 1e-6]
            P = P[keep]
            if np.linalg.norm(P[0] - P[-1]) < 1e-6:
                P = P[:-1]
            prism(sp, P, ys - t / 2, ys + t / 2, "Interior", axis=1)
            # the door: a leaf in its opening (shut), a knob each face, built level and laid along the sheer (its foot
            # a quarter inch over the deck all along)
            zd = float(self.zg(0.5 * (d0 + d1)))
            k0 = len(sp.V)
            vbox(sp, [d0 + 0.1 * IN, ys - 0.5 * IN, zd + 0.25 * IN], [d1 - 0.1 * IN, ys + 0.5 * IN, zd + hd - 0.1 * IN],
                 "Interior")
            for fy in (1.0, -1.0):
                lathe(sp, [d1 - 2.5 * IN, ys + fy * 0.4 * IN, zd + 36.0 * IN], fy * EY, EX,
                      [(0.0, 0.35 * IN), (0.8 * IN, 0.3 * IN), (1.0 * IN, 0.8 * IN), (1.8 * IN, 0.8 * IN)], "Bronze", 10)
            self.drape(sp, k0, zd)
            if sgn < 0:                                    # the port one: the starboard one mirrored
                for V in sp.V:
                    V[:, 1] *= -1.0
                sp.F = [tuple(f[::-1]) for f in sp.F]
            part.extend(sp)
        self.info["state_rooms"] = {"y_m": ys, "fore_x_m": xf, "door_x_m": [round(d0, 3), round(d1, 3)]}

    def window_seat(self, part):
        """the seat across the stern under the windows between the state rooms: a hinge rail along the after wall (let
        into it), the lids before it on brass hinges (lids_a_side each side; the piece over the rudder's head is fixed),
        each with a rounded nosing over the front, and the front board under them framed and panelled (raised and
        fielded panels no wider than panel_max_in between stiles and rails) down to the deck; the rudder's head boxed
        inside it"""
        st = self.c["cabin"]["seat"]
        sr = self.c["cabin"]["state_rooms"]
        ys = sr["y_m"] - sr["wall_in"] / 2 * IN
        xr, yr, ztr = self.rudder_head()
        let = 0.25 * IN
        b = 1.0 * IN
        zt = float(self.zg(self.x_aft)) + st["high_in"] * IN
        x_f = max(float(self.wall_x(zt)) + st["deep_in"] * IN, xr + st["rudder_box_in"] * IN + b)
        tt = st["top_in"] * IN
        if ztr > zt - tt - st["rudder_box_in"] * IN:
            raise SystemExit(f"gundeck: the window seat ({zt:.3f}) is too low over the rudder's head ({ztr:.3f})")
        gap = st["gap_in"] * IN
        x_n = x_f + st["nosing_in"] * IN
        r = tt / 2
        x_hr = float(self.wall_x(zt)) + st["hinge_rail_in"] * IN
        # the hinge rail, let into the wall
        prism(part, [(float(self.wall_x(zt - tt)) - let, zt - tt), (x_hr, zt - tt), (x_hr, zt), (float(self.wall_x(zt)) - let, zt)],
              -ys, ys, "Interior", axis=1)
        # the lids and the fixed middle, each with its nosing rounded over
        arc = [(x_n - r + r * math.cos(a), zt - r + r * math.sin(a)) for a in np.linspace(-math.pi / 2, math.pi / 2, 9)]
        poly = [(x_hr + gap, zt - tt)] + arc + [(x_hr + gap, zt)]
        y_mid = yr + st["rudder_box_in"] * IN + b + st["middle_beyond_box_in"] * IN
        n_l = st["lids_a_side"]
        side = [y_mid + k * (ys - y_mid) / n_l for k in range(n_l + 1)]
        edges = [-y for y in side[::-1]] + side
        pieces = list(zip(edges[:-1], edges[1:]))
        hinges = []
        for a, c in pieces:
            a_ = a if a <= -ys + 1e-9 else a + gap / 2
            c_ = c if c >= ys - 1e-9 else c - gap / 2
            prism(part, poly, a_, c_, "Interior", axis=1)
            if abs(a + y_mid) < 1e-9 and abs(c - y_mid) < 1e-9:
                continue                                            # the fixed middle over the rudder's head
            for f in (0.2, 0.8):
                hinges.append(a_ + f * (c_ - a_))
        hl, hr = (v * IN for v in st["hinge_in"])
        for y in hinges:
            lathe(part, [x_hr + gap / 2, y - hl / 2, zt - hr], EY, EX, [(0.0, hr), (hl, hr)], "Bronze", 10)
        # the front board, framed and panelled
        zf = float(self.zg(x_f))
        vbox(part, [x_f - b, -ys, zf - let], [x_f, ys, zt - tt], "Interior")
        fp_, ff = (v * IN for v in st["frame_proud_in"])           # the frame's and the fields' faces off the board
        sw = st["stile_in"] * IN
        zr0, zr1 = zf + 0.25 * IN, zf + st["bottom_rail_in"] * IN
        zr2, zr3 = zt - tt - st["top_rail_in"] * IN, zt - tt - 0.02 * IN
        for z0_, z1_ in ((zr0, zr1), (zr2, zr3)):
            vbox(part, [x_f - 0.05 * IN, -ys + 0.05 * IN, z0_], [x_f + fp_, ys - 0.05 * IN, z1_], "Interior")
        cs = [-ys + 0.05 * IN + sw / 2]
        for a, c in pieces:
            n_p = max(1, int(math.ceil((c - a) / (st["panel_max_in"] * IN))))
            cs += [a + k * (c - a) / n_p for k in range(1, n_p)] + [c]
        cs[-1] = ys - 0.05 * IN - sw / 2
        for yc in cs:
            vbox(part, [x_f - 0.05 * IN, yc - sw / 2, zr1 - 0.02 * IN], [x_f + fp_, yc + sw / 2, zr2 + 0.02 * IN], "Interior")
        ins = st["field_inset_in"] * IN
        for y0_, y1_ in zip(cs[:-1], cs[1:]):
            a, c = y0_ + sw / 2, y1_ - sw / 2
            back = np.array([[x_f - 0.05 * IN, a, zr1], [x_f - 0.05 * IN, c, zr1], [x_f - 0.05 * IN, c, zr2],
                             [x_f - 0.05 * IN, a, zr2]])
            front = np.array([[x_f + ff, a + ins, zr1 + ins], [x_f + ff, c - ins, zr1 + ins], [x_f + ff, c - ins, zr2 - ins],
                              [x_f + ff, a + ins, zr2 - ins]])
            solid(part, [back, front], "Interior")
        self.seat = (x_f, zt, ys)
        self.info["window_seat"] = {"front_x_m": round(x_f, 3), "top_z_m": round(zt, 3), "half_m": round(ys, 3),
                                    "lids": len(pieces) - 1, "panels": len(cs) - 1}

    def after_panelling(self, part):
        """the after wall's joinery between the state rooms (cabin after_wall panelling), laid on the wall's rake: a
        sill rail across under the windows on the seat's top, a pilaster (its base and capital) between each two
        windows and a stile at each end, a head moulding over each window and a raised and fielded panel over that, and
        a cornice along the top under the spar deck's planks. Each piece stands clear of the windows' openings (their
        linings) by clear_in"""
        aw = self.c["cabin"]["after_wall"]
        ap = aw["panelling"]
        rv = aw["reveal_in"] * IN
        _, zt_seat, ys = self.seat
        z_top = float(self.aft_rows()[-1, 2])
        e = 0.05 * IN
        cl = ap["clear_in"] * IN
        y_end = ys - 0.1 * IN
        opens = sorted((a - rv, b_ + rv, v0 - rv, v1 + rv) for a, b_, v0, v1 in self.window_rects())
        z_sill = min(o[2] for o in opens) - 0.5 * IN
        wx = self.wall_x

        def on_wall(y, z, out):
            return [float(wx(z)) + out, y, z]

        def strip_v(y0, y1, z0, z1, t):
            zz = np.linspace(z0, z1, max(2, int(math.ceil((z1 - z0) / 0.25)) + 1))
            solid(part, [np.array([on_wall(y0, z, -e), on_wall(y1, z, -e), on_wall(y1, z, t), on_wall(y0, z, t)])
                         for z in zz], "Interior")

        def strip_h(y0, y1, prof):
            """along y from y0 to y1, its section prof [(out, z)]"""
            solid(part, [np.array([on_wall(y, z, o) for o, z in prof]) for y in (y0, y1)], "Interior")

        def field(y0, y1, z0, z1, t, ins):
            back = np.array([on_wall(y0, z0, -e), on_wall(y1, z0, -e), on_wall(y1, z1, -e), on_wall(y0, z1, -e)])
            front = np.array([on_wall(y0 + ins, z0 + ins, t), on_wall(y1 - ins, z0 + ins, t), on_wall(y1 - ins, z1 - ins, t),
                              on_wall(y0 + ins, z1 - ins, t)])
            solid(part, [back, front], "Interior")
        # the cornice, its section from the wall: a fascia, then an ovolo out to its full projection under the planks
        ch_ = ap["cornice_in"] * IN
        cp = ap["cornice_out_in"] * IN
        fo = ap["fascia_out_in"] * IN
        zc0 = z_top - ch_
        ovolo = [(fo + (cp - fo) * math.sin(a), z_top - 0.45 * ch_ + 0.35 * ch_ * (1 - math.cos(a)))
                 for a in np.linspace(0.0, math.pi / 2, 5)]
        prof = [(-e, zc0), (fo, zc0)] + ovolo + [(cp, z_top), (-e, z_top)]
        strip_h(-y_end, y_end, prof)
        # the sill rail on the seat's top
        sp = ap["sill_out_in"] * IN
        strip_h(-y_end, y_end, [(-e, zt_seat), (sp, zt_seat), (sp, z_sill - 0.4 * IN), (sp - 0.4 * IN, z_sill), (-e, z_sill)])
        # the pilasters between the windows, with base and capital, and a stile at each end
        pw, pt = (v * IN for v in ap["pilaster_in"])
        bh_, bo = (v * IN for v in ap["base_in"])
        kh, ko = (v * IN for v in ap["capital_in"])
        pil = []
        for o0, o1 in zip(opens[:-1], opens[1:]):
            g0, g1 = o0[1] + cl, o1[0] - cl
            if g1 - g0 < 3.0 * IN:
                continue
            w = min(pw, g1 - g0 - 2 * max(bo, ko))
            yc = 0.5 * (g0 + g1)
            strip_v(yc - w / 2, yc + w / 2, z_sill + bh_ - 0.1 * IN, zc0 - kh + 0.1 * IN, pt)
            strip_v(yc - w / 2 - bo, yc + w / 2 + bo, z_sill, z_sill + bh_, pt + bo)
            strip_v(yc - w / 2 - ko, yc + w / 2 + ko, zc0 - kh, zc0, pt + ko)
            pil.append(round(yc, 3))
        sw = ap["stile_in"] * IN
        for sg in (-1.0, 1.0):
            y_in = sg * (y_end - sw)
            if any(o[0] - cl < max(y_in, sg * y_end) and o[1] + cl > min(y_in, sg * y_end) for o in opens):
                raise SystemExit("gundeck: the after wall's end stile comes into a window's opening")
            strip_v(min(y_in, sg * y_end), max(y_in, sg * y_end), z_sill, zc0, pt * 0.6)
        # over each window a head moulding and a raised panel
        hh, ho = (v * IN for v in ap["head_in"])
        for u0, u1, v0, v1 in opens:
            z0_ = v1 + cl
            strip_h(u0 - 1.0 * IN, u1 + 1.0 * IN, [(-e, z0_), (ho, z0_), (ho, z0_ + hh - 0.4 * IN), (ho - 0.4 * IN, z0_ + hh),
                                                  (-e, z0_ + hh)])
            zp0, zp1 = z0_ + hh + 2.0 * IN, zc0 - 2.0 * IN
            if zp1 - zp0 > 4.0 * IN:
                field(u0, u1, zp0, zp1, ap["field_out_in"] * IN, ap["field_inset_in"] * IN)
        self.info["after_wall"]["panelling"] = {"pilasters_y_m": pil, "cornice_m": [round(zc0, 3), round(z_top, 3)],
                                                "sill_rail_top_m": round(z_sill, 3)}

    def floor_cloth(self, part):
        """the painted floor cloth over the cabin's deck (black and white squares: its 'Cloth' UV counts squares), from
        the window seat to the bulkhead, between the state rooms aft and out to the waterways forward of them: a closed
        sheet thick_in thick on the deck"""
        cb = self.c["cabin"]
        fc = cb["floor_cloth"]
        t = fc["thick_in"] * IN
        mg = fc["margin_in"] * IN
        sq = fc["square_in"] * IN
        sr = cb["state_rooms"]
        x_seat = self.seat[0] + mg
        x_sr = sr["fore_x_m"] + sr["wall_in"] / 2 * IN + mg
        x_bk = cb["bulkhead_x_m"] - cb["bulkhead_in"] / 2 * IN - mg
        ysr = sr["y_m"] - sr["wall_in"] / 2 * IN - mg
        flush = 3.0 * IN + mg                                  # inside the waterway's cove
        xs = np.linspace(x_sr, x_bk, 10)
        yside = self.wall_at(xs, self.zg(xs))[0][:, 1] - flush
        right = [(x_seat, ysr), (x_sr, ysr)] + [(float(x), float(y)) for x, y in zip(xs, yside)]
        outline = np.array([(x, -y) for x, y in right[::-1]] + right)
        a2 = np.sum(outline[:, 0] * np.roll(outline[:, 1], -1) - np.roll(outline[:, 0], -1) * outline[:, 1])
        if a2 < 0:
            outline = outline[::-1]
        P2, T = cdt(densify(outline, 0.25), [], 0.3)
        Z = self.zg(P2[:, 0]) + t
        uv = np.column_stack([P2[:, 0] / sq, P2[:, 1] / sq + 0.5])
        part.add(np.column_stack([P2, Z]), [tuple(tr) for tr in T], "FloorCloth", uv=uv)
        # its underside, a hair into the deck (closed, so the room check can tell what lies under it from what is in it)
        part.add(np.column_stack([P2, self.zg(P2[:, 0]) - 0.02 * IN]), [tuple(tr[::-1]) for tr in T], "FloorCloth",
                 uv=uv)
        # its edge down onto the deck
        O = densify(outline, 0.25)
        A = np.column_stack([O, self.zg(O[:, 0]) + t])
        B = np.column_stack([O, self.zg(O[:, 0]) - 0.02 * IN])
        n = len(O)
        V = np.concatenate([A, B])
        F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        c = O.mean(0)
        f0 = F[0]
        nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
        if nrm[:2] @ (O[0] - c) < 0:
            F = [f[::-1] for f in F]
        part.add(V, F, "FloorCloth", uv=np.zeros((2 * n, 2)))
        self.cloth_t = t
        self.info["floor_cloth"] = {"x_m": [round(x_seat, 3), round(x_bk, 3)], "triangles": len(T)}

    def furniture(self, part):
        """the cabin's table, six chairs and the sideboard (mahogany), standing on the floor cloth: each built on a
        level deck at 0 and laid along the sheer (drape), so every foot is on the cloth"""
        cb = self.c["cabin"]
        tb = cb["table"]
        L, W = (v * IN for v in tb["size_in"])
        h, tt = tb["high_in"] * IN, tb["top_in"] * IN
        x0 = tb["x_m"]
        k0 = len(part.V)
        z0 = self.cloth_t
        vbox(part, [x0 - L / 2, -W / 2, z0 + h - tt], [x0 + L / 2, W / 2, z0 + h], "Mahogany")
        # the apron under the top, inset, and four turned legs at its corners
        ins = 3.0 * IN
        ap = 0.9 * IN                                      # the side aprons run the length, the end ones between them
        for a_, b_ in (((x0 - L / 2 + ins, -W / 2 + ins), (x0 + L / 2 - ins, -W / 2 + ins + ap)),
                       ((x0 - L / 2 + ins, W / 2 - ins - ap), (x0 + L / 2 - ins, W / 2 - ins)),
                       ((x0 - L / 2 + ins, -W / 2 + ins + ap), (x0 - L / 2 + ins + ap, W / 2 - ins - ap)),
                       ((x0 + L / 2 - ins - ap, -W / 2 + ins + ap), (x0 + L / 2 - ins, W / 2 - ins - ap))):
            vbox(part, [a_[0], a_[1], z0 + h - tt - 4.5 * IN], [b_[0], b_[1], z0 + h - tt + 0.05 * IN], "Mahogany")
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                c = [x0 + sx * (L / 2 - ins - 0.9 * IN), sy * (W / 2 - ins - 0.9 * IN), z0]
                lathe(part, c, EZ, EX, [(0.0, 0.75 * IN), (1.0 * IN, 0.85 * IN), (2.0 * IN, 0.75 * IN),
                                        (h - tt - 6.0 * IN, 1.1 * IN), (h - tt - 5.0 * IN, 1.25 * IN),
                                        (h - tt + 0.05 * IN, 1.25 * IN)], "Mahogany", 12)
        # the chairs: square legs, a seat, the back's uprights carried up from the back legs, a top rail and a splat
        ci = cb["chair_in"]
        w, d, hs = (v * IN for v in ci["seat"])
        hb = ci["back_high_in"] * IN
        lg = ci["leg_in"] * IN
        for cx, cy, deg in cb["chairs"]:
            a = math.radians(deg)
            f = np.array([math.cos(a), math.sin(a), 0.0])
            s = np.array([-math.sin(a), math.cos(a), 0.0])
            zc = self.cloth_t
            c = np.array([cx, cy, zc])

            def P(df, ds, dz):
                return c + f * df + s * ds + EZ * dz
            for df in (d / 2 - lg / 2, -d / 2 + lg / 2):
                for ds in (-w / 2 + lg / 2, w / 2 - lg / 2):
                    top = hs - 0.6 * IN if df > 0 else hb - 0.5 * IN
                    bar(part, P(df, ds, 0.0), P(df, ds, top), lg, lg, "Mahogany", up=f)
            box(part, P(0.0, 0.0, hs - 0.5 * IN), f, s, EZ, d / 2 + 0.3 * IN, w / 2 + 0.3 * IN, 0.5 * IN, "Mahogany")
            # the top rail across the uprights' heads, a little wider and thicker than them (it hides their tops)
            box(part, P(-d / 2 + lg / 2, 0.0, hb - 1.25 * IN), f, s, EZ, lg / 2 + 0.1 * IN, w / 2 + 0.25 * IN, 1.25 * IN,
                "Mahogany")
            hz = 0.5 * (hb - 2.5 * IN - hs)
            box(part, P(-d / 2 + lg / 2, 0.0, hs + hz), f, s, EZ, 0.35 * IN, 2.75 * IN, hz, "Mahogany")
            for ds in (-w / 2 + lg / 2, w / 2 - lg / 2):          # the side stretchers
                bar(part, P(d / 2 - lg, ds, 5.0 * IN), P(-d / 2 + lg, ds, 5.0 * IN), 0.75 * IN, 1.0 * IN, "Mahogany")
        # the sideboard against the bulkhead's after face: on legs, two drawers over two cupboard doors, brass knobs
        sb = cb["sideboard"]
        D, Ln, H = (v * IN for v in sb["size_in"])
        x1 = cb["bulkhead_x_m"] - cb["bulkhead_in"] / 2 * IN - cb["panel"]["proud_in"] * IN - 0.25 * IN
        x_0 = x1 - D
        yc = sb["y_m"]
        zs = self.cloth_t
        legh = 7.0 * IN
        for xx in (x_0 + 1.0 * IN, x1 - 1.0 * IN):
            for yy in (yc - Ln / 2 + 1.0 * IN, yc + Ln / 2 - 1.0 * IN):
                bar(part, [xx, yy, zs], [xx, yy, zs + legh + 0.5 * IN], 1.5 * IN, 1.5 * IN, "Mahogany", up=EX)
        vbox(part, [x_0 + 0.5 * IN, yc - Ln / 2 + 0.25 * IN, zs + legh], [x1, yc + Ln / 2 - 0.25 * IN, zs + H - 1.0 * IN],
             "Mahogany")
        vbox(part, [x_0, yc - Ln / 2, zs + H - 1.0 * IN], [x1, yc + Ln / 2, zs + H], "Mahogany")
        zmid = zs + H - 1.0 * IN - 7.0 * IN
        for (ya, yb), (za, zb) in (((yc - Ln / 2 + 1.0 * IN, yc - 0.25 * IN), (zmid + 0.25 * IN, zs + H - 1.5 * IN)),
                                   ((yc + 0.25 * IN, yc + Ln / 2 - 1.0 * IN), (zmid + 0.25 * IN, zs + H - 1.5 * IN)),
                                   ((yc - Ln / 2 + 1.0 * IN, yc - 0.25 * IN), (zs + legh + 0.75 * IN, zmid - 0.25 * IN)),
                                   ((yc + 0.25 * IN, yc + Ln / 2 - 1.0 * IN), (zs + legh + 0.75 * IN, zmid - 0.25 * IN))):
            vbox(part, [x_0 + 0.25 * IN, ya, za], [x_0 + 0.55 * IN, yb, zb], "Mahogany")
            lathe(part, [x_0 + 0.3 * IN, 0.5 * (ya + yb) if zb > zmid else (yb - 2.5 * IN if ya < yc else ya + 2.5 * IN),
                         0.5 * (za + zb)], -EX, EY, [(0.0, 0.3 * IN), (0.6 * IN, 0.25 * IN), (0.8 * IN, 0.6 * IN),
                                                     (1.3 * IN, 0.6 * IN)], "Bronze", 10)
        self.drape(part, k0, 0.0)
        self.info["furniture"] = {"table_x_m": x0, "chairs": len(cb["chairs"]), "sideboard_x_m": [round(x_0, 3), round(x1, 3)]}

    # --- the lanterns ---------------------------------------------------------------------------------------------------
    def lantern(self, part, H):
        """a horn lantern hung from H (the planks' or a bar's underside): a screw eye and hook, the ring on its roof,
        the cone roof, the six-sided body (tin posts and bands, horn panes) and its dish; returns the light's place
        (the body's middle) and the dish's underside"""
        lt = self.c["lanterns"]
        across, high = (v * IN for v in lt["body_in"])
        roof, ring, hook = (lt[k] * IN for k in ("roof_in", "ring_in", "hook_in"))
        R = across / 2
        H = np.asarray(H, float)
        ring_band(part, H - EZ * 0.3 * IN, EZ, EX, -0.3 * IN, 0.35 * IN, 0.3 * IN, 0.2 * IN, "Iron", 8)
        z_ring = H[2] - hook
        tube(part, np.array([H - EZ * 0.3 * IN, H - EZ * (hook - ring * 0.4), H - EZ * (hook - ring * 0.45) + EX * 0.25 * IN]),
             0.12 * IN, "Iron", n=6)
        c_ring = np.array([H[0], H[1], z_ring - ring * 0.1])
        th = np.linspace(0.0, 2 * math.pi, 13)[:-1]
        tube(part, c_ring + np.stack([np.cos(th) * ring * 0.4, np.zeros_like(th), np.sin(th) * ring * 0.4], 1), 0.1 * IN,
             "Tin", n=6, closed=True)
        z_roof = z_ring - ring * 0.5                       # the roof's top
        z_top = z_roof - roof                              # the body's top
        z_bot = z_top - high
        lathe(part, [H[0], H[1], z_top - 0.3 * IN], EZ, EX, [(0.0, R + 0.45 * IN), (0.3 * IN, R + 0.45 * IN),
                                                            (roof * 0.8, 1.2 * IN), (roof * 0.8 + 0.6 * IN, 1.2 * IN),
                                                            (roof + 0.3 * IN, 0.6 * IN)], "Tin", 12)
        # the body: six posts at the corners, bands round its top and bottom, horn between
        ang = np.arange(6) * math.pi / 3
        C = np.array([H[0], H[1], 0.0])
        for a in ang:
            p = C + R * np.array([math.cos(a), math.sin(a), 0.0])
            box(part, np.array([p[0], p[1], 0.5 * (z_bot + z_top)]), EX, EY, EZ, 0.2 * IN, 0.2 * IN, high / 2, "Tin")
        for zb_, zt_ in ((z_bot, z_bot + 1.2 * IN), (z_top - 1.2 * IN, z_top)):
            rings = [C + EZ * z + (R + 0.12 * IN) * np.stack([np.cos(ang), np.sin(ang), np.zeros(6)], 1)
                     for z in (zb_, zt_)]
            solid(part, rings, "Tin")
        panes = [C + EZ * z + (R - 0.1 * IN) * np.stack([np.cos(ang), np.sin(ang), np.zeros(6)], 1)
                 for z in (z_bot + 1.0 * IN, z_top - 1.0 * IN)]
        solid(part, panes, "Horn")
        lathe(part, [H[0], H[1], z_bot - 1.0 * IN], EZ, EX, [(0.0, R - 1.0 * IN), (0.4 * IN, R + 0.3 * IN),
                                                           (1.05 * IN, R + 0.3 * IN)], "Tin", 12)
        return np.array([H[0], H[1], 0.5 * (z_bot + z_top)]), z_bot - 1.0 * IN

    def lanterns(self, part):
        """one hung between each second pair of guns a side (lanterns.between_guns), between the spar deck's beams on a
        hook in the planks' underside: in the bay (between two members overhead, the waist's beams and the gangways'
        ledges among them) whose middle lies nearest the middle between the two ports and which stands clear of both
        (clear_of_ports_m: the bays over the ports hold the guns' implements), in_from_side_m in from the side's inner
        face, over the room between the two guns and out of the walk inboard of them; and one over the middle of the
        cabin's table, from a bar (in DeckBeams) across between the carlings either side of the skylight over it. Each a
        light in the game data (self.lights) in its zone: the deck's lanterns, unshadowed, reach no further than the
        cabin's bulkhead (radius_m, less where one stands nearer), the cabin's casts shadows, so neither shines through
        the bulkhead"""
        lt = self.c["lanterns"]
        li, lc = lt["light"], lt["cabin_light"]
        cb = self.c["cabin"]
        mids = [0.5 * (a + f) for a, f in self.ports]
        faces = sorted((x - s / 2, x + s / 2) for x, s, m, kind in list(self.members) + list(self.waist_members()))
        bays = [(f0[1], f1[0]) for f0, f1 in zip(faces[:-1], faces[1:])]
        R_l = 0.5 * lt["body_in"][0] * IN + 0.45 * IN                 # the roof's brim
        drop = (lt["hook_in"] + 0.5 * lt["ring_in"] + lt["roof_in"] + 0.5 * lt["body_in"][1]) * IN
        cp = lt["clear_of_ports_m"]
        x_bk = cb["bulkhead_x_m"] + cb["bulkhead_in"] / 2 * IN           # the bulkhead's fore face
        cs_ = self.c["overhead"]["carling_in"][0] * IN
        y_gang = self.dk.y_open + self.dk.t_coam / 2 + cs_ / 2         # the waist's carlings' outer faces
        placed = []

        def light(nm, c, zone, radius, shadows):
            self.lights.append({"name": nm, "pos_m": [round(float(v), 4) for v in c], "zone": zone,
                                "colour_rgb": li["colour_rgb"], "kelvin": li["kelvin"], "lumens": li["lumens"],
                                "radius_m": round(float(radius), 3), "cast_shadows": shadows})

        for a, b in lt["between_guns"]:
            xw = 0.5 * (mids[a - 1] + mids[b - 1])
            ok = [(lo, hi) for lo, hi in bays if hi - lo >= 2 * R_l + 0.1
                  and not any(lo < f + cp and hi > p0 - cp for p0, f in self.ports)]
            if not ok:
                raise SystemExit(f"gundeck: no bay between the ports {a} and {b} to hang a lantern in")
            lo, hi = min(ok, key=lambda bb: abs(0.5 * (bb[0] + bb[1]) - xw))
            x = 0.5 * (lo + hi)
            z0 = float(self.zsu(x))
            P, _ = self.wall_at(np.array([x]), np.array([z0 - drop]))
            y = float(P[0, 1]) - lt["in_from_side_m"]
            if self.e1 < x < self.fc and y - R_l < y_gang + 0.05:
                raise SystemExit(f"gundeck: the lantern between the ports {a} and {b} would hang under the waist's "
                                 f"opening (y {y:.3f})")
            if abs(x - xw) > 0.6:
                raise SystemExit(f"gundeck: the lantern between the ports {a} and {b} hangs {x - xw:.2f} m off their "
                                 f"middle")
            for sd, sgn in (("S", 1.0), ("P", -1.0)):
                c, z_low = self.lantern(part, [x, sgn * y, z0])
                nm = f"Lantern_{a:02d}_{b:02d}_{sd}"
                radius = min(li["radius_m"], float(c[0]) - x_bk - 0.05)
                light(nm, c, "gun_deck", radius, li["cast_shadows"])
                placed.append({"name": nm, "x_m": round(x, 3), "y_m": round(sgn * y, 3), "off_middle_m": round(x - xw, 3),
                               "bay_m": [round(lo, 3), round(hi, 3)], "in_from_side_m": lt["in_from_side_m"],
                               "bottom_over_deck_m": round(float(z_low - self.zg(x)), 3), "radius_m": round(radius, 3)})
        # the cabin's: a bar across between the carlings either side of the skylight, over the table's middle
        x_t = cb["table"]["x_m"]
        ys = [cr["y_m"] for cr in self.overhead_info["carlings"] if cr["x_m"][0] + 0.05 < x_t < cr["x_m"][1] - 0.05]
        yp, yq = [y_ for y_ in ys if y_ > 0], [y_ for y_ in ys if y_ < 0]
        if not yp or not yq:
            raise SystemExit("gundeck: no carlings either side of the cabin's table to hang its lantern from")
        yi = min(min(yp), -max(yq)) - cs_ / 2                          # the carlings' inner faces
        bs_, bm_ = (v * IN for v in lt["cabin_bar_in"])
        zt = float(self.zsu(x_t)) - lt["cabin_bar_under_in"] * IN
        vbox(self.parts_["DeckBeams"], [x_t - bs_ / 2, -yi, zt - bm_], [x_t + bs_ / 2, yi, zt], "Oak")
        c, z_low = self.lantern(part, [x_t, 0.0, zt - bm_])
        light("Lantern_Cabin", c, "great_cabin", lc["radius_m"], lc["cast_shadows"])
        top = float(self.zg(x_t)) + (cb["table"]["high_in"]) * IN
        placed.append({"name": "Lantern_Cabin", "x_m": round(x_t, 3), "y_m": 0.0, "off_middle_m": 0.0,
                       "bar": {"between_y_m": [round(-yi, 3), round(yi, 3)], "top_under_planks_in": lt["cabin_bar_under_in"]},
                       "bottom_over_deck_m": round(float(z_low - self.zg(x_t)), 3),
                       "bottom_over_table_m": round(float(z_low - top), 3), "radius_m": lc["radius_m"]})
        if len(self.lights) > lt["light_budget"]["max_lights"]:
            raise SystemExit(f"gundeck: {len(self.lights)} lights over the gun deck's budget of "
                             f"{lt['light_budget']['max_lights']}")
        self.info["lanterns"] = placed

    # --- the capstan bars -------------------------------------------------------------------------------------------------
    def capstan_bars(self, part):
        """the capstan's bars (capstan bars: one for each hole) stowed overhead athwartships, bars_a_bay to a bay in
        the bays nearest the capstan, half each side: each bay clear of the ports (the implements' and the lids'
        lanyards' bays), with no lantern, forward of the cabin and outside the waist, and long enough across to the
        nearest carling; each set in two iron stirrups from the planks, the bars' tops under the lodging knees, from
        out_of_side_m in from the side inboard"""
        cs = self.c["capstan"]
        cbar = cs["bars"]
        nb = cs["bar_holes"]
        Lb = cbar["long_ft"] * FT
        sq = cbar["square_in"] * IN
        sq_l = cbar["square_long_in"] * IN
        d1, d2 = (v * IN for v in cbar["round_in"])
        gap = cbar["gap_in"] * IN
        per = cbar["bars_a_bay"]
        v0 = cbar["out_of_side_m"]
        sw_, st_ = (v * IN for v in cbar["stirrup_in"])
        sd = self.c["overhead"]["lodging_knee"]["sided_in"] * IN
        cp = self.c["lanterns"]["clear_of_ports_m"]
        cb = self.c["cabin"]
        x_bk = cb["bulkhead_x_m"] + cb["bulkhead_in"] / 2 * IN
        lantern_bays = [tuple(li["bay_m"]) for li in self.info["lanterns"] if "bay_m" in li]
        faces = self.bay_faces()
        set_w = per * sq + (per - 1) * gap
        bays = []
        for (p0, p1), (q0, q1) in zip(faces[:-1], faces[1:]):
            lo, hi = p1, q0
            mid = 0.5 * (lo + hi)
            if hi - lo < set_w + 2 * (sw_ + 1.5 * IN) or lo < x_bk + 0.3 or self.e1 - 0.05 < mid < self.fc + 0.05:
                continue
            if any(lo < f + cp and hi > a - cp for a, f in self.ports):
                continue
            if any(abs(mid - 0.5 * (a + b)) < 0.05 for a, b in lantern_bays):
                continue
            zt = float(min(self.zsu(lo), self.zsu(hi)))
            z_top = zt - sd - 0.25 * IN
            yw = float(self.wall_at(np.array([mid]), np.array([z_top - sq / 2]))[0][0, 1])
            y_in = yw - v0 - Lb
            # the half members either side: the carling their cut stops at must lie inboard of the bars' inner ends
            cuts = [self.cut[i] for i, mb in enumerate(self.members)
                    if i in self.cut and (abs(mb[0] + mb[1] / 2 - lo) < 1e-6 or abs(mb[0] - mb[1] / 2 - hi) < 1e-6)]
            if cuts and max(cuts) + 0.05 > y_in:
                continue
            bays.append((abs(mid - self.x_capstan), lo, hi, z_top, yw))
        bays.sort()
        need = int(math.ceil(nb / 2 / per))
        if len(bays) < need:
            raise SystemExit(f"gundeck: only {len(bays)} bays to stow the capstan's bars in ({need} wanted a side)")
        stowed = []
        left = nb // 2
        for _, lo, hi, z_top, yw in bays[:need]:
            k = min(per, left)
            left -= k
            mid = 0.5 * (lo + hi)
            us = mid + (np.arange(k) - (k - 1) / 2) * (sq + gap)
            zc = z_top - sq / 2
            for sg in (1.0, -1.0):
                for xb in us:
                    y_out = yw - v0
                    # the square inner end (it goes into the drumhead's hole), then round, tapering to the hand
                    y_sq = y_out - Lb + sq_l
                    vbox(part, [xb - sq / 2, min(sg * (y_out - Lb), sg * y_sq), zc - sq / 2],
                         [xb + sq / 2, max(sg * (y_out - Lb), sg * y_sq), zc + sq / 2], "Oak")
                    lathe(part, [xb, sg * y_sq, zc], sg * EY, EZ,
                          [(-0.5 * IN, d1 / 2), (0.0, d1 / 2), (Lb - sq_l - 2.0 * IN, d2 / 2), (Lb - sq_l - 0.5 * IN, d2 / 2 - 0.2 * IN),
                           (Lb - sq_l, d2 / 2 - 0.6 * IN)], "Oak", 10)
                # two stirrups: straps down from the planks round the set
                for vs in cbar["stirrups_from_side_m"]:
                    y_s = sg * (yw - vs)
                    xa_, xf_ = us[0] - sq / 2 - st_, us[-1] + sq / 2 + st_
                    zb_ = zc - sq / 2 - st_
                    zt_ = float(self.zsu(mid)) + 0.25 * IN
                    for x_l in (xa_, xf_ - st_):
                        vbox(part, [x_l, y_s - sw_ / 2, zb_], [x_l + st_, y_s + sw_ / 2, zt_], "Iron")
                    vbox(part, [xa_, y_s - sw_ / 2, zb_], [xf_, y_s + sw_ / 2, zb_ + st_], "Iron")
            stowed.append({"bay_m": [round(lo, 3), round(hi, 3)], "bars_a_side": k, "under_planks_m": round(
                float(self.zsu(mid)) - (zc - sq / 2), 3)})
        self.info["capstan_bars"] = {"bars": nb, "long_m": round(Lb, 3), "bays": stowed}

    # --- the layout check -----------------------------------------------------------------------------------------------
    def footprints(self):
        """every fitting's plan outline on this deck (name -> (n, 2)), and the room kept clear at the spar deck's
        ladders' feet and the companion ladder's"""
        fp = {}
        for k, v in self.items.items():
            fp[k] = rect2(v["x"], 0.0, v["Lo"], v["Wo"])
        fp["GunCapstan"] = circle(self.c["capstan"]["drumhead_diam_in"] / 2 * IN, 32) + [self.x_capstan, 0.0]
        x0, L, W = self.chain_case
        fp["ChainPumps"] = rect2(x0, 0.0, L, W)
        a, b, W = self.brake_span
        fp["BrakePumps"] = rect2(0.5 * (a + b), 0.0, b - a, W)
        a, b, ye = self.bitts_box
        fp["RidingBitts"] = rect2(0.5 * (a + b), 0.0, b - a, 2 * ye)
        a, b, ye = self.galley_box
        fp["Galley"] = rect2(0.5 * (a + b), 0.0, b - a, 2 * ye)
        g = self.c["deck"]["mast_hole_gap_in"] * IN
        for name in ("fore", "main", "mizzen"):
            p, R, _ = self.mast_at(name, float(self.zg(self.mast_x(name))))
            fp["Mast_" + name] = circle(R + g + 1.25 * IN, 24) + p[:2]
        bw = self.c["bow"]
        xs, ys = bw["scuttle_at_m"]
        for sy in (1.0, -1.0):
            fp["CableScuttle_" + ("S" if sy > 0 else "P")] = circle((bw["scuttle_in"] / 2 + bw["collar_in"][0]) * IN,
                                                                    16) + [xs, sy * ys]
        xm, tm, ye = self.manger
        fp["Manger"] = rect2(xm, 0.0, tm, 2 * ye)
        # the ladders' feet: the room a man needs stepping off (clear_m) beyond each foot, the ladder's width
        cl = self.c["ladders"]["clear_m"]
        for li in self.dk.ladder_info:
            d = 1.0 if li["break"] == "quarterdeck" else -1.0
            w = self.dk.c["ladders"]["width_in"] * IN + 2 * self.dk.c["ladders"]["stringer_in"][1] * IN
            xf = li["foot_x_m"]
            fp["LadderFoot_%s_%s" % (li["break"], "S" if li["y_m"] > 0 else "P")] = rect2(xf + d * cl / 2, li["y_m"], cl, w)
        xf, w = self.companion_foot
        fp["LadderFoot_companion"] = rect2(xf - cl / 2, 0.0, cl, w)
        for k, (x, y, rr) in enumerate(self.dk.tiller_legs):
            fp["TillerLeg_%d" % k] = circle(rr + 2.0 * IN, 12) + [x, y]
        return fp

    def layout_check(self, fp, gap=0.15):
        """the least room in plan between every two fittings: pairs closer than gap"""
        names = list(fp)
        close = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                A, B = fp[a], fp[b]
                if in_poly(A, B).any() or in_poly(B, A).any():
                    d = 0.0
                else:
                    d = float(min(seg_dist(A, B).min(), seg_dist(B, A).min()))
                if d < gap:
                    close.append([a, b, round(d, 3)])
        return close

    # --- assembly -------------------------------------------------------------------------------------------------------
    def build(self):
        self.layout()
        names = ("GunDeck", "GunWaterways", "DeckBeams", "Clamps", "HangingKnees", "Stanchions", "Hatchways", "Wells",
                 "HatchLadders", "MastWedges", "GunCapstan", "GunCapstanPawls", "Pumps", "RidingBitts", "Galley",
                 "Manger", "LeadBushes", "AfterWall", "WindowReveals", "CabinBulkhead", "StateRooms", "WindowSeat",
                 "FloorCloth", "CabinFurniture", "HornLanterns", "PortStops", "LodgingKnees", "CapstanBars")
        P = {n: Part() for n in names}
        # the waist's beams (deck.py's) made again with their ends cut to this deck's side, over its clamp
        self.dk.rebuild_waist(lambda x0, x1, z: float(self.wall_at(np.array([x0, x1]), np.array([z, z]))[0][:, 1].min())
                              - 0.002)
        self.surface(P["GunDeck"])
        self.waterways(P["GunWaterways"])
        self.overhead(P["DeckBeams"])
        self.clamps(P["Clamps"])
        self.knees(P["HangingKnees"])
        self.lodging_knees(P["LodgingKnees"])
        self.hatchways(P["Hatchways"], P["Wells"], P["HatchLadders"])
        self.mast_wedges(P["MastWedges"])
        self.capstan(P["GunCapstan"], P["GunCapstanPawls"])
        self.chain_pumps(P["Pumps"])
        self.brake_pumps(P["Pumps"])
        self.galley(P["Galley"])
        # the bitts' standards reach aft along the deck as far as the galley's hearth leaves room (a hand's breadth)
        bt = self.c["bitts"]
        room = bt["x_m"] - bt["post_in"] / 2 * IN - (self.c["galley"]["x_m"][1] + self.c["galley"]["hearth_in"][1] * IN)
        self.bitt_standard_m = min(36.0 * IN, room - 4.0 * IN)
        self.bitts(P["RidingBitts"])
        self.bow(P["Manger"], P["Wells"])
        self.lead_bushes(P["LeadBushes"])
        self.port_stops(P["PortStops"])
        # the great cabin
        self.parts_ = P
        self.after_wall(P["AfterWall"])
        self.reveals(P["WindowReveals"])
        self.bulkhead(P["CabinBulkhead"], None)
        self.state_rooms(P["StateRooms"])
        self.window_seat(P["WindowSeat"])
        self.after_panelling(P["AfterWall"])
        self.floor_cloth(P["FloorCloth"])
        self.furniture(P["CabinFurniture"])
        self.lanterns(P["HornLanterns"])
        self.capstan_bars(P["CapstanBars"])
        fp = self.footprints()
        self.stanchions(P["Stanchions"], fp)
        self.info["layout_close"] = self.layout_check(fp)
        return self

    def parts(self):
        """name -> (V, faces, materials, frame, uv): frame (origin, R) for a part built in its own frame (R's columns
        its axes in the ship), else None; uv the 'Planking' and 'Margin' UVs per vertex (the deck's top) or None"""
        out = {}
        for name, p in self.parts_.items():
            V, F, M, U = p.arrays()
            out[name] = (V, F, M, self.frames.get(name), U if name in self.UV_PARTS else None)
        return out

    def world(self, name):
        V, F, M, U = self.parts_[name].arrays()
        fr = self.frames.get(name)
        if fr is not None:
            o, R = fr
            V = o + V @ np.asarray(R).T
        return V, F
