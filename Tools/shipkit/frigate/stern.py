"""The frigate's stern (docs/shipkit-9): the taffrail with its carved board, the spar deck's stern ports (closed), the
arch over the cabin's windows with their sashes and the paired pilasters beside them, the stars, the name band and the
name, the quarter pieces down the corners, a quarter gallery on each quarter (its roof carved with scales, three lights
between pilasters and one in its after face, a cornice, a panelled band, a base and a drop), the cabin's side light
forward of each gallery and a lantern hung off each quarter.
    from stern import Stern;  sn = Stern(L, rig, sk).build();  sn.parts()
Sizes and places are decor_1797.json's "stern", each with its source: the 1927 lines plan (its body plan's stern view
and its sheer plan), the 1817 draught, or the period's practice. Heights are tied to the side's own lines where the
plan's agree with them: the taffrail is the quarterdeck's rail, the ports stand between the spar port sill line and the
sheer, the arch's top is at the plankshear. Units: metres in the ship frame (X forward, Y starboard, Z up). On the stern
face things are placed by (u, v), u across (+ starboard) and v up, on the transom as loft draws it (its round-up), and
stand off it along its normal; a gallery's are placed by (s, z, d): s aft to forward from the stern's edge along the
side, z up and d out from the planking. The parts are whole ('centre') except the galleries, the cabin windows and
the lanterns, which are starboard parts mirrored for port by the caller.
The ship's frame is Unreal's (Y to starboard): Blender draws her as her mirror image, so the name reads backwards in
Blender's renders and the right way round in the game (docs/shipkit-8).
"""
import json
import math
import os

import numpy as np

import carve
import loft
from head import slab, smoothstep, unit
from skin import Part, compact, sweep

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
KNUCKLE = loft.KNUCKLE
EX, EY, EZ = np.eye(3)


def rect(u0, u1, v0, v1):
    return np.array([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], float)


def ring(P, step):
    """A closed polygon with points about step apart along each side, its corners kept."""
    P = np.asarray(P, float)
    out = []
    for a, b in zip(P, np.roll(P, -1, axis=0)):
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        out.append(a + (np.arange(n)[:, None] / n) * (b - a))
    return np.concatenate(out)


def star(c, R, r, n=5, rot=90.0):
    a = np.radians(rot) + np.arange(2 * n) * math.pi / n
    rr = np.where(np.arange(2 * n) % 2 == 0, R, r)
    return np.stack([c[0] + rr * np.cos(a), c[1] + rr * np.sin(a)], -1)


def plate(mesh, mapping, outline, holes, d0, d1, mat, step, edge_mat=None):
    """A plate over outline less its holes (2D, in the mapping's coordinates) standing from d0 to d1 off the surface:
    mapping(P2 (n, 2), d (n,)) -> points (n, 3)."""
    c, h = 0.5 * (d0 + d1), 0.5 * (d1 - d0)
    to3d = lambda P2, d: mapping(P2, c + np.asarray(d, float) * np.ones(len(P2)))          # noqa: E731
    slab(mesh, ring(outline, step), [ring(q, step) for q in holes], step, to3d,
         lambda P2: np.full(len(P2), h), mat, edge_mat)


def faceted_star(mesh, mapping, normal_at, c, R, r, h0, h1, mat):
    """A five-pointed star in low relief: its centre raised h1, its points and notches h0, walls down to the surface."""
    B = star(c, R, r)
    n = len(B)
    top = mapping(B, np.full(n, h0))
    bot = mapping(B, np.full(n, -0.004))
    C = mapping(np.array([c]), np.array([h1]))[0]
    V = np.concatenate([top, bot, [C]])
    ic = 2 * n
    F = []
    for i in range(n):
        j = (i + 1) % n
        F.append((ic, i, j))
        F.append((i, n + i, n + j, j))
    # every face out: the top faces along the surface's normal, the walls away from the star's middle
    nrm = normal_at(np.array([c]))[0]
    out = []
    for f in F:
        P = V[list(f)]
        fn = np.cross(P[1] - P[0], P[2] - P[0])
        want = nrm if len(f) == 3 else P.mean(0) - C
        out.append(f if fn @ want > 0 else f[::-1])
    mesh.add(V, out, [mat] * len(out))


class Face:
    """The stern face as loft draws the transom (its round-up eased in over the wing transom's first 30 px), charted
    by u across (m, + starboard) and v up (m)."""

    def __init__(self, L):
        self.L = L
        self.k = L.ppf_y / FT                       # px per m (heights and half-breadths)

    def xyz(self, u, v):
        L = self.L
        u, v = np.broadcast_arrays(np.asarray(u, float), np.asarray(v, float))
        shape = u.shape
        u, v = u.ravel(), v.ravel()
        zp = v * self.k
        W = L._W(zp)
        ru = L.round_up * np.clip((zp - KNUCKLE) / 30.0, 0.0, 1.0)
        yp = u * self.k
        t = yp / W
        x, y, z = L.to_m(L._x_sf(zp) - ru * (1 - t * t), yp, zp)
        return np.stack([x, y, z], -1).reshape(shape + (3,))

    def normal(self, u, v):
        h = 0.004
        u, v = np.broadcast_arrays(np.asarray(u, float), np.asarray(v, float))
        Pu = self.xyz(u + h, v) - self.xyz(u - h, v)
        Pv = self.xyz(u, v + h) - self.xyz(u, v - h)
        n = unit(np.cross(Pv, Pu))
        return np.where(n[..., :1] > 0, -n, n)       # out of the stern: aft

    def at(self, P2, d=0.0):
        P2 = np.atleast_2d(np.asarray(P2, float))
        d = np.broadcast_to(np.asarray(d, float), (len(P2),))
        return self.xyz(P2[:, 0], P2[:, 1]) + d[:, None] * self.normal(P2[:, 0], P2[:, 1])

    def n_at(self, P2):
        P2 = np.atleast_2d(np.asarray(P2, float))
        return self.normal(P2[:, 0], P2[:, 1])

    def half(self, v):
        """the face's half breadth at height v (m): the moulded edge"""
        return np.asarray(self.L._W(np.asarray(v, float) * self.k), float) / self.k

    def edge_x(self, v):
        """the face's x at its edge (where the side's planking ends) at height v"""
        return (np.asarray(self.L._x_sf(np.asarray(v, float) * self.k), float) - self.L.mid_px) / self.L.ppf * FT


class Stern:
    def __init__(self, L, rig, sk, cfg=None):
        self.L, self.rig, self.sk = L, rig, sk
        self.cfg = cfg or json.load(open(os.path.join(HERE, "decor_1797.json")))
        self.c = self.cfg["stern"]
        self.paint = self.c["paint"]
        self.face = Face(L)
        self.meshes = {}                # name -> (Part, side)
        self.info = {}
        k = self.face.k
        pr = sk.pr
        # the side's lines where they meet the stern face (each at the face's x at its own height)
        xpx = lambda z: float(L._x_sf(z * k))                       # noqa: E731
        self.line_z = {}
        for name, fn in (("sheer", pr.H), ("spar_sill", pr.Ssp), ("plankshear", pr.P), ("gun_sill", pr.S),
                         ("gun_head", pr.Shd), ("gun_deck", pr.G)):
            z = 5.0
            for _ in range(4):
                z = float(fn(np.array([xpx(z)]))[0]) / k
            self.line_z[name] = z
        # the rail at the stern face (the skin's bulwark top there) and the stern bulwark's inner face
        top = sk.byname[f"b{sk.nb}"]
        idx, _ = sk.seg_of(top, True, top.segs[0])
        self.z_rail = float(sk.V.Z[idx[0]]) / k
        pos = sk.positions()
        r = sk.byname["w_R1"]
        i, _ = sk.seg_of(r, True, r.segs[0])
        self.x_inner = float(pos[i[0]][0])
        rs = sk.sp["rail"]
        self.cap = (self.z_rail - 0.5 * IN, self.z_rail - 0.5 * IN + rs["thick_in"] * IN)    # the side caps' under, top
        # the side caps' after ends (built here as the skin builds them): the taffrail stands over them
        tmp = Part()
        sk.rail_caps(tmp)
        Vc = tmp.arrays()[0]
        Vc = Vc[Vc[:, 0] < self.x_inner + 0.3]
        self.side_cap = {"top_z": float(Vc[:, 2].max()), "out_y": float(np.abs(Vc[:, 1]).max()),
                         "end_x": float(Vc[:, 0].min())}
        # the planking's outside at the stern's edge (from the skin) as a function of height
        zs = np.linspace(1.8, self.z_rail, 24)
        P, _ = self.side(self.face.edge_x(zs) + 0.004, zs)
        self._y_out = (zs, P[:, 1])
        self.info["lines_m"] = {k_: round(v, 3) for k_, v in self.line_z.items()}
        self.info["lines_m"].update({"rail": round(self.z_rail, 3), "inner_face_x": round(self.x_inner, 3)})

    def mesh(self, name, side="centre"):
        if name not in self.meshes:
            self.meshes[name] = (Part(), side)
        return self.meshes[name][0]

    # ---- the side's planking near the stern ---------------------------------------------------------------------------
    def side(self, x, z, smooth=False):
        """the planked side's outside at (x, z) (starboard) and its outward normal; smooth: the moulded side plus the
        planking's ordinary thickness (no wales, no seams), the surface the galleries and the cabin's light are laid on
        (the wales run on under them)"""
        L = self.L
        x, z = np.broadcast_arrays(np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float)))
        X = L.mid_px + x / FT * L.ppf
        Z = z * self.face.k
        if not smooth:
            return self.sk.surf(X, Z)
        g = self._smooth_grid()
        Q = np.stack([x, z], -1)
        inside = (x >= g["x"][0]) & (x <= g["x"][-1]) & (z >= g["z"][0]) & (z <= g["z"][-1])
        S = np.empty((len(x), 3))
        N = np.empty((len(x), 3))
        if inside.any():
            S[inside] = g["S"](Q[inside])
            N[inside] = unit(g["N"](Q[inside]))
        if (~inside).any():
            S[~inside], N[~inside] = self._smooth_exact(X[~inside], Z[~inside])
        return S, N

    def _smooth_exact(self, X, Z):
        P, N, _ = self.sk.m.frame(X, Z, np.ones(len(X), bool))
        return P + N * (self.sk.pl.t0 * IN), N

    def _smooth_grid(self):
        """the smooth side tabled over the quarter (4 cm), the surface's cost being a section per distinct x: aft of
        the stern's edge (where the lines stop) carried on straight from its last 5 cm"""
        if getattr(self, "_sg", None) is None:
            from scipy.interpolate import RegularGridInterpolator
            L, k = self.L, self.face.k
            xs = np.arange(-30.4, -22.6, 0.04)
            zs = np.arange(1.4, 5.4, 0.04)
            X, Z = np.meshgrid(L.mid_px + xs / FT * L.ppf, zs * k, indexing="ij")
            S, N = self._smooth_exact(X.ravel(), Z.ravel())
            S, N = S.reshape(len(xs), len(zs), 3), N.reshape(len(xs), len(zs), 3)
            xe = np.asarray(self.face.edge_x(zs), float) + 0.004
            Sa, Na = self._smooth_exact(L.mid_px + xe / FT * L.ppf, zs * k)
            Sb, Nb = self._smooth_exact(L.mid_px + (xe + 0.05) / FT * L.ppf, zs * k)
            for j in range(len(zs)):
                aft = xs < xe[j]
                t = (xs[aft] - xe[j]) / 0.05
                S[aft, j] = Sa[j] + t[:, None] * (Sb[j] - Sa[j])
                N[aft, j] = Na[j] + t[:, None] * (Nb[j] - Na[j])
            self._sg = {"x": xs, "z": zs, "S": RegularGridInterpolator((xs, zs), S),
                        "N": RegularGridInterpolator((xs, zs), N)}
        return self._sg

    def excess(self, x, z):
        """how far the planking (a wale, a thicker strake) stands out of the smooth surface at (x, z), m"""
        L = self.L
        x, z = np.broadcast_arrays(np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float)))
        X = L.mid_px + x / FT * L.ppf
        Z = z * self.face.k
        n = len(X)
        d = self.sk.pl.thick_in(X, Z, np.ones(n, bool), np.zeros(n, int), grooves=False)
        return np.maximum(d - self.sk.pl.t0, 0.0) * IN

    def y_out(self, v):
        return np.interp(v, *self._y_out)

    def fmap(self, P2, d):
        return self.face.at(P2, d)

    # ---- the taffrail -------------------------------------------------------------------------------------------------
    def taffrail(self):
        """The rail cap across the stern's top (the side caps' section), from the side's outside at one corner to the
        other's, lapping the side caps' after ends; a gilt bead under its after edge, a moulding across at the sheer,
        and the board between them carved (frieze())."""
        c = self.c["taffrail"]
        ov = c["overhang_m"]
        m = self.mesh("Taffrail")
        sc = self.side_cap
        z0 = self.cap[0]
        z1 = max(self.cap[1], sc["top_z"] + c["over_side_caps_m"])     # a little over the side caps that run into it
        U = max(float(self.y_out(self.z_rail)), sc["out_y"]) + ov
        us = np.linspace(-U, U, 61)
        aft = self.face.xyz(us, np.full(len(us), self.z_rail))
        aft[:, 0] -= ov
        xf = self.x_inner + ov + c["fwd_lap_m"]
        outline = ring(np.concatenate([aft[:, :2], [(xf, U), (xf, -U)]]), 0.12)
        to3d = lambda P2, d: np.stack([P2[:, 0], P2[:, 1], 0.5 * (z0 + z1) + np.asarray(d, float) * np.ones(len(P2))], -1)  # noqa
        slab(m, outline, [], 0.12, to3d, lambda P2: np.full(len(P2), 0.5 * (z1 - z0)), self.paint["ground"])
        # the bead under the cap's after edge, and the moulding at the sheer, each from quarter piece to quarter piece
        qp = self.c["quarter_pieces"]
        g = self.mesh("SternCarving")
        rb = c["bead_r_m"]
        for v, r_, mat in ((z0 - 0.7 * rb, rb, self.paint["carving"]),
                           (self.line_z["sheer"], c["sheer_moulding_r_m"], self.paint["ground"])):
            Ue = float(self.face.half(v)) - qp["on_face_m"] + 0.01
            uu = np.linspace(-Ue, Ue, 120)
            P2 = np.stack([uu, np.full(len(uu), v)], -1)
            V, F, M = carve.stroke_mesh(self.face.at(P2), self.face.n_at(P2), np.full(len(uu), r_), mat)
            (g if mat == self.paint["carving"] else m).add(V, F, M)
        self.taffrail_half = U
        self.info["taffrail"] = {"cap_z_m": [round(z0, 3), round(z1, 3)], "half_breadth_m": round(U, 3),
                                 "fwd_edge_x_m": round(xf, 3),
                                 "side_caps": {k_: round(v_, 3) for k_, v_ in sc.items()}}
        self.taffrail_top = z1

    def frieze(self):
        """The taffrail board's carving: from a star on the middle line a running scroll out to each quarter piece,
        in the band between the sheer's moulding and the cap's bead."""
        f = self.c["frieze"]
        tf = self.c["taffrail"]
        qp = self.c["quarter_pieces"]
        v0 = self.line_z["sheer"] + tf["sheer_moulding_r_m"] + f["margin_m"]
        v1 = self.cap[0] - 1.5 * tf["bead_r_m"] - f["margin_m"]
        vm, half = 0.5 * (v0 + v1), 0.5 * (v1 - v0)
        u0 = f["centre_gap_m"]
        u1 = float(self.face.half(vm)) - qp["on_face_m"] - f["end_gap_m"]
        design = carve.running_scroll(u1 - u0, half, f)
        g = self.mesh("SternCarving")
        tris = 0
        for sgn in (1.0, -1.0):
            to_uv = lambda P, s_=sgn: np.stack([s_ * (u0 + np.asarray(P)[:, 0]), vm + np.asarray(P)[:, 1]], -1)  # noqa
            tris += carve.relief(g, design, to_uv, lambda UV: (self.face.at(UV), self.face.n_at(UV)), f["mat"])
        R, r = f["star_r_m"]
        faceted_star(g, self.fmap, self.face.n_at, np.array([0.0, vm]), R, r, 0.004, 0.025, f["mat"])
        self.info["frieze"] = {"band_m": [round(v0, 3), round(v1, 3)], "u_m": [round(u0, 3), round(u1, 3)],
                               "triangles": tris}

    # ---- the ports over the quarterdeck -------------------------------------------------------------------------------
    def ports(self):
        """The stern's ports between the spar port sill line and the sheer, closed: each lid a little proud of the
        face, a joint round it, two hinge straps from its top."""
        c = self.c["ports"]
        m = self.mesh("SternPorts")
        v0, v1 = self.line_z["spar_sill"], self.line_z["sheer"] - self.c["taffrail"]["sheer_moulding_r_m"]
        spans = []
        for a, b in c["u_m"]:
            spans.append((a, b))
            if a > 0:
                spans.append((-b, -a))
        e = c["inset_m"]
        hw, ht, hl = c["hinge_m"]
        for a, b in spans:
            plate(m, self.fmap, rect(a + e, b - e, v0 + e, v1 - e), [], -0.01, c["lid_proud_m"], self.paint["ground"],
                  0.06)
            for f_ in (0.22, 0.78):
                uc = a + f_ * (b - a)
                plate(m, self.fmap, rect(uc - hw / 2, uc + hw / 2, v1 - e - hl * (v1 - v0), v1 - 0.004),
                      [], c["lid_proud_m"] - 0.004, c["lid_proud_m"] + ht, self.paint["iron"], 0.05)
        self.info["ports"] = {"z_m": [round(v0, 3), round(v1, 3)], "u_m": [[round(a, 3), round(b, 3)] for a, b in spans]}

    # ---- the arch, stars, windows, pilasters --------------------------------------------------------------------------
    def arch_line(self):
        """the arch's middle line (u, v), port foot to starboard foot: its legs a little in from the stern's edge, its
        corners rounded, level across the top"""
        a = self.c["arch"]
        vt, vf, Rc = a["top_m"], self.c["name"]["band_z_m"][1], a["corner_r_m"]           # its feet on the name band
        leg = lambda v: float(self.face.half(v)) - a["leg_in_m"]                     # noqa: E731
        vc = vt - Rc
        uc = leg(vc) - Rc
        legs = np.array([(leg(v), v) for v in np.linspace(vf, vc, 24)])
        th = np.linspace(0.0, math.pi / 2, 18)[1:]
        corner = np.stack([uc + Rc * np.cos(th), vc + Rc * np.sin(th)], -1)
        top = np.array([(u, vt) for u in np.linspace(uc, 0.0, 26)[1:]])
        half = np.concatenate([legs, corner, top])
        P = np.concatenate([half * [-1.0, 1.0], half[::-1][1:]])
        return P

    def arch(self):
        a = self.c["arch"]
        m = self.mesh("SternFrame")
        g = self.mesh("SternCarving")
        C = self.arch_line()
        T = np.gradient(C, axis=0)
        T = unit(T)
        N = np.stack([-T[:, 1], T[:, 0]], -1)
        bw = 0.5 * a["band_m"]
        outline = np.concatenate([C + bw * N, (C - bw * N)[::-1]])
        plate(m, self.fmap, outline, [], -0.005, a["proud_m"], self.paint["ground"], 0.05)
        for sgn in (1.0, -1.0):
            P2 = C + sgn * (bw - 0.4 * a["bead_r_m"]) * N
            V, F, M = carve.stroke_mesh(self.face.at(P2, a["proud_m"]), self.face.n_at(P2),
                                        np.full(len(P2), a["bead_r_m"]), self.paint["carving"])
            g.add(V, F, M)
        self.info["arch"] = {"top_m": a["top_m"], "feet_u_m": [round(float(C[0, 0]), 3), round(float(C[-1, 0]), 3)]}

    def stars(self):
        s = self.c["stars"]
        g = self.mesh("SternCarving")
        R, r = s["r_m"]
        h0, h1 = s["raised_m"]
        for u, v in s["at_m"]:
            for sgn in ((1.0,) if u == 0 else (1.0, -1.0)):
                faceted_star(g, self.fmap, self.face.n_at, np.array([sgn * u, v]), R, r, h0, h1, self.paint["carving"])

    def window_spans(self):
        w = self.c["windows"]
        out = []
        for a, b in w["u_m"]:
            out.append((a, b))
            if a > 0:
                out.append((-b, -a))
        return sorted(out)

    def sash(self, m, mapping, u0, u1, v0, v1, panes, bar, d0, d1, mat):
        """a sash over (u0..u1, v0..v1): its frame bar[0] wide, its glazing bars bar[1], panes (across, up)"""
        fb, gb = bar
        nu, nv = panes
        holes = []
        wu = (u1 - u0 - 2 * fb - (nu - 1) * gb) / nu
        wv = (v1 - v0 - 2 * fb - (nv - 1) * gb) / nv
        for i in range(nu):
            for j in range(nv):
                a = u0 + fb + i * (wu + gb)
                b = v0 + fb + j * (wv + gb)
                holes.append(rect(a, a + wu, b, b + wv))
        plate(m, mapping, rect(u0, u1, v0, v1), holes, d0, d1, mat, 0.05)

    def windows(self):
        """The cabin's windows: a casing standing off the face, the sash inside it, the glass behind its bars; a
        sill ledge under the whole row (windows and pilasters) and a head over each window."""
        w = self.c["windows"]
        frame = self.mesh("SternFrame")
        sash = self.mesh("SternSash")
        glass = self.mesh("SternGlass")
        v0, v1 = w["z_m"]
        cw = w["casing_m"]
        for a, b in self.window_spans():
            plate(frame, self.fmap, rect(a - cw, b + cw, v0 - cw, v1 + cw), [rect(a, b, v0, v1)], -0.005,
                  w["casing_proud_m"], self.paint["frames"], 0.05)
            self.sash(sash, self.fmap, a, b, v0, v1, w["panes"], w["sash_m"], -0.005, w["sash_proud_m"],
                      self.paint["sash"])
            plate(glass, self.fmap, rect(a, b, v0, v1), [], -0.005, w["glass_proud_m"], self.paint["clear_glass"], 0.08)
            hh, hp, ho = w["head_m"]
            plate(frame, self.fmap, rect(a - cw - ho, b + cw + ho, v1 + cw, v1 + cw + hh), [], -0.005, hp,
                  self.paint["frames"], 0.05)
        p = self.c["pilasters"]
        ue = max(p["u_m"]) + 0.5 * p["base_m"][0] + 0.03
        sh, sp = w["sill_m"]
        plate(frame, self.fmap, rect(-ue, ue, v0 - cw - sh, v0 - cw), [], -0.005, sp, self.paint["frames"], 0.05)
        self.info["windows"] = {"u_m": [[round(a, 3), round(b, 3)] for a, b in self.window_spans()],
                                "z_m": [v0, v1], "sill_z_m": [round(v0 - cw - sh, 3), round(v0 - cw, 3)]}

    def pilasters(self):
        p = self.c["pilasters"]
        w = self.c["windows"]
        frame = self.mesh("SternFrame")
        g = self.mesh("SternCarving")
        v0, v1 = w["z_m"]
        cw = w["casing_m"]
        vb = v0 - cw                                    # on the sill
        bw, bh, bp = p["base_m"]
        cwid, ch, cp = p["cap_m"]
        for u in p["u_m"]:
            for uc in (u, -u):
                plate(frame, self.fmap, rect(uc - p["w_m"] / 2, uc + p["w_m"] / 2, vb + bh - 0.01, v1 + 0.01), [],
                      -0.005, p["proud_m"], self.paint["frames"], 0.05)
                plate(frame, self.fmap, rect(uc - bw / 2, uc + bw / 2, vb, vb + bh), [], -0.005, bp,
                      self.paint["frames"], 0.05)
                plate(frame, self.fmap, rect(uc - cwid / 2, uc + cwid / 2, v1, v1 + ch), [], -0.005, cp,
                      self.paint["frames"], 0.05)
                c3 = np.array([[uc, v1 + ch + p["boss_over_m"] - p["boss_r_m"]]])
                V, F, M = carve.berry_mesh(self.face.at(c3)[0], self.face.n_at(c3)[0], p["boss_r_m"],
                                           self.paint["carving"], n=12)
                g.add(V, F, M)

    # ---- the name -----------------------------------------------------------------------------------------------------
    def name(self):
        """The name band across the stern under the windows, a gilt bead along each edge, and the name on it in gilt
        Roman capitals, centred, reading from astern (in the game's frame: left to right is port to starboard)."""
        nc = self.c["name"]
        qp = self.c["quarter_pieces"]
        m = self.mesh("SternFrame")
        g = self.mesh("SternCarving")
        v0, v1 = nc["band_z_m"]
        w = self.c["windows"]
        sill = w["z_m"][0] - w["casing_m"] - w["sill_m"][0]
        if v1 > sill - 0.005:
            raise ValueError(f"the name band's top ({v1} m) must stand at least 5 mm under the windows' sill ({sill:.3f} m)")
        bp = nc["band_proud_m"]
        Ue = min(float(self.face.half(v)) for v in (v0, v1)) - qp["on_face_m"] + 0.01
        plate(m, self.fmap, rect(-Ue, Ue, v0, v1), [], -0.005, bp, self.paint["ground"], 0.05)
        rb = nc["bead_r_m"]
        for v in (v0 + 0.6 * rb, v1 - 0.6 * rb):
            uu = np.linspace(-Ue + 0.01, Ue - 0.01, 120)
            P2 = np.stack([uu, np.full(len(uu), v)], -1)
            V, F, M = carve.stroke_mesh(self.face.at(P2, bp), self.face.n_at(P2), np.full(len(uu), rb),
                                        self.paint["carving"])
            g.add(V, F, M)
        V, T, rep = self.glyphs(nc)
        # the letters on the band's face: (gx along the line, gy up, gz through it) -> (u, v, d)
        u = V[:, 0]
        v = 0.5 * (v0 + v1) - 0.5 * nc["cap_height_m"] + V[:, 1]
        if v.min() < v0 + 1.6 * rb + 0.005 or v.max() > v1 - 1.6 * rb - 0.005:
            raise ValueError(f"the name's letters ({v.min():.3f} to {v.max():.3f} m) must stand 5 mm clear of the band's "
                             f"beads ({v0 + 1.6 * rb:.3f}, {v1 - 1.6 * rb:.3f} m)")
        P = self.face.at(np.stack([u, v], -1), bp + V[:, 2])
        # the glyphs' winding was set in their own (right-handed) frame; the map to (u, v, d) keeps or turns it: make
        # every face point out of the letter (positive volume)
        vol = np.einsum("ij,ij->i", P[T[:, 0]], np.cross(P[T[:, 1]], P[T[:, 2]])).sum()
        if vol < 0:
            T = T[:, ::-1]
        g.add(P, [tuple(t) for t in T], [self.paint["carving"]] * len(T))
        rep.update({"band_z_m": [v0, v1], "band_half_m": round(Ue, 3)})
        self.info["name"] = rep

    def glyphs(self, nc):
        """the name's letters as a closed mesh, cap height nc['cap_height_m'], centred on u = 0, baseline at 0, through
        the band from -seat to +relief: (V (n, 3) as (u, v, d), T (t, 3), report)"""
        import bpy
        font = bpy.data.fonts.load(os.path.normpath(os.path.join(HERE, nc["font"])), check_existing=True)

        def text_mesh(body, spacing):
            cu = bpy.data.curves.new("_text", "FONT")
            cu.body, cu.font, cu.align_x = body, font, "CENTER"
            cu.space_character = spacing
            cu.extrude = 1.0
            cu.resolution_u = 6
            ob = bpy.data.objects.new("_text", cu)
            bpy.context.scene.collection.objects.link(ob)
            bpy.context.view_layer.update()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            bpy.data.objects.remove(ob)
            bpy.data.curves.remove(cu)
            me.calc_loop_triangles()
            V = np.array([tuple(v.co) for v in me.vertices], float)
            T = np.array([tuple(t.vertices) for t in me.loop_triangles], int)
            bpy.data.meshes.remove(me)
            return V, T
        Vh, _ = text_mesh("H", 1.0)
        cap = float(Vh[:, 1].max())
        V, T = text_mesh(nc["text"], 1.0 + nc["tracking"])
        s = nc["cap_height_m"] / cap
        z0, z1 = V[:, 2].min(), V[:, 2].max()
        d = (V[:, 2] - z0) / (z1 - z0) * (nc["relief_m"] + nc["seat_m"]) - nc["seat_m"]
        out = np.stack([V[:, 0] * s, V[:, 1] * s, d], -1)
        out[:, 0] -= 0.5 * (out[:, 0].max() + out[:, 0].min())
        width = float(out[:, 0].max() - out[:, 0].min())
        return out, T, {"text": nc["text"], "cap_height_m": nc["cap_height_m"], "width_m": round(width, 3),
                        "triangles": int(len(T))}

    # ---- the quarter pieces -------------------------------------------------------------------------------------------
    def quarter_pieces(self):
        """A moulded piece down each corner of the stern, over the side planking's ends: on the face on_face_m in from
        its edge and proud of it, round the corner and out over the planking, forward along the side; a gilt bead on
        its outer corner and a gilt volute at its head under the taffrail's end. The starboard piece is built and the
        port one is its mirror image (the stern's face is symmetric)."""
        q = self.c["quarter_pieces"]
        m = Part()
        g = Part()
        za, zb = q["z_m"]
        zb = min(zb, self.cap[0] + 0.01)
        zs = np.linspace(za, zb, 40)
        a, h, wr, o, rc = q["on_face_m"], q["proud_m"], q["wrap_m"], q["out_m"], q["round_m"]
        beads = {1.0: []}

        def frame(z, sgn):
            """at height z: the face's half breadth, its edge, the level normal there and the way outboard along it"""
            W = float(self.face.half(z))
            C = self.face.xyz(sgn * W, z)
            nf = self.face.normal(sgn * W, z)
            nf = unit(nf - nf[2] * EZ)                                      # level: the piece is a vertical sweep
            es = unit(np.cross(EZ, nf) * sgn * np.sign(np.cross(EZ, nf)[1] + 1e-12))  # outboard along the face
            if es[1] * sgn < 0:
                es = -es
            return W, C, nf, es

        def front(UV, sgn):
            """the piece's face part, h proud of the stern's face (u across as the face's, v up): its points and
            normals, as the sweep lays it"""
            def at(u, v):
                W, C, nf, es = frame(v, sgn)
                return C + (sgn * u - W) * es + h * nf
            P, N = [], []
            for u, v in np.atleast_2d(np.asarray(UV, float)):
                e = 0.002
                du, dv = at(u + e, v) - at(u - e, v), at(u, v + e) - at(u, v - e)
                n_ = unit(np.cross(du, dv))
                P.append(at(u, v))
                N.append(n_ if n_ @ frame(v, sgn)[2] > 0 else -n_)
            return np.array(P), np.array(N)
        for sgn in (1.0,):
            secs = []
            for z in zs:
                W, C, nf, es = frame(z, sgn)
                tp = float(self.y_out(z)) - W                               # the planking's thickness at the edge
                corner = C + (tp + o) * es + h * nf
                pts = [C - a * es - 0.01 * nf, C - a * es + h * nf]
                # round the outer corner
                for th in np.linspace(0.0, math.pi / 2, 5):
                    pts.append(corner - rc * es - rc * nf + rc * (math.sin(th) * es + math.cos(th) * nf))
                pts += [C + (tp + o) * es - wr * nf, C + (tp - 0.01) * es - wr * nf, C + (tp - 0.01) * es - 0.01 * nf]
                # counter-clockwise seen from above; the sweep closes and caps it
                secs.append(np.array(pts))
                beads[sgn].append(corner - 0.3 * rc * (es + nf))
            V, F, M = sweep(secs, self.paint["ground"], closed=True, caps=True)
            m.add(*self.outward(V, F, M))
            B = np.array(beads[sgn])
            nb = unit(np.array([unit(self.face.normal(sgn * float(self.face.half(z)), z)) for z in zs]) +
                      sgn * EY)
            V, F, M = carve.stroke_mesh(B, nb, np.full(len(B), q["bead_r_m"]), self.paint["carving"])
            g.add(V, F, M)
            # the volute at its head: on the face part (as swept, not the stern's face h out), under the taffrail
            vo = q["volute"]
            zc = zb - vo["below_m"]
            W = float(self.face.half(zc))
            cen = np.array([sgn * (W - 0.5 * a), zc])
            sp = carve.spiral(np.array([0.0, 0.0]), vo["r_m"], vo["end"] * vo["r_m"], vo["turns"], math.pi / 2,
                              -sgn)
            sp = cen + sp * [0.55 * a / vo["r_m"], 1.0]
            r0, r1 = vo["rope_m"]
            design = {"strokes": [(sp, np.linspace(r0, r1, len(sp)))], "leaves": [], "berries": [(sp[-1], 1.4 * r1)]}
            Vm, Fm, _ = m.arrays()
            carve.relief(g, design, lambda P: np.asarray(P, float), lambda UV, s_=sgn: front(UV, s_),
                         self.paint["carving"], seat=carve.Seat(Vm, Fm))
        for part, name in ((m, "QuarterPieces"), (g, "SternCarving")):
            V, F, M = part.arrays()
            V = np.asarray(V, float)
            self.mesh(name).add(V, F, M)
            self.mesh(name).add(V * np.array([1.0, -1.0, 1.0]), [tuple(f[::-1]) for f in F], M)
        self.info["quarter_pieces"] = {"z_m": [za, round(zb, 3)]}

    @staticmethod
    def outward(V, F, M):
        """turn a closed sweep's faces out (positive volume)"""
        V = np.asarray(V, float)
        vol = 0.0
        for f in F:
            for i in range(1, len(f) - 1):
                vol += V[f[0]] @ np.cross(V[f[i]], V[f[i + 1]])
        if vol < 0:
            F = [tuple(f[::-1]) for f in F]
        return V, F, M

    # ---- the quarter galleries ------------------------------------------------------------------------------------------
    def gal_xa(self, z):
        """the gallery's after edge: the stern's edge (the face's x where the planking ends) at height z"""
        return self.face.edge_x(z)

    def gmap(self, P2, d):
        """(s, z) on the gallery, d out from the planking (horizontally, square to the side) -> points"""
        P2 = np.atleast_2d(np.asarray(P2, float))
        d = np.broadcast_to(np.asarray(d, float), (len(P2),))
        z = P2[:, 1]
        x = self.gal_xa(z) + np.maximum(P2[:, 0], 0.004)
        S, N = self.side(x, z, smooth=True)
        h = N.copy()
        h[:, 2] = 0.0
        h = unit(h)
        return S + d[:, None] * h

    def g_floor(self, P2):
        """the least depth of a gallery's thin edge at (s, z): over the planking where a wale stands out of the smooth
        surface"""
        P2 = np.atleast_2d(np.asarray(P2, float))
        x = self.gal_xa(P2[:, 1]) + np.maximum(P2[:, 0], 0.004)
        return self.excess(x, P2[:, 1]) + 0.012

    def g_n(self, P2, d):
        """the outward normal of the surface d(s, z) off the planking (d a function of (s, z) points)"""
        P2 = np.atleast_2d(np.asarray(P2, float))
        e = 0.004
        ds, dz = np.array([e, 0.0]), np.array([0.0, e])
        Ps = self.gmap(P2 + ds, d(P2 + ds)) - self.gmap(P2 - ds, d(P2 - ds))
        Pz = self.gmap(P2 + dz, d(P2 + dz)) - self.gmap(P2 - dz, d(P2 - dz))
        n = unit(np.cross(Ps, Pz))
        return np.where(n[:, 1:2] < 0, -n, n)

    def galleries(self):
        """A gallery on the quarter, raked with the stern: bands one over another, each a block from the planking out
        (the base, the panelled band, the lights, the cornice), the roof rising from the cornice in to the side (lower
        forward, clear of the aftmost spar deck port), the drop under the base; the lights' windows let into the lights
        band, pilasters between them, a light in the after face; scales carved on the roof, a garland down its fore edge,
        leaves on the drop."""
        gc = self.c["galleries"]
        Lg = gc["length_m"]
        body = self.mesh("Gallery", "stbd")
        frame = self.mesh("GalleryFrame", "stbd")
        sash = self.mesh("GallerySash", "stbd")
        glass = self.mesh("GalleryGlass", "stbd")
        g = self.mesh("GalleryCarving", "stbd")
        B = gc["bands"]
        gm = self.gmap
        ground, frames = self.paint["ground"], self.paint["frames"]
        for key in ("base", "panels", "cornice"):
            z0, z1, D = B[key]
            plate(body, gm, rect(0.0, Lg, z0, z1), [], -0.01, D, ground, 0.06)
        # the panels band's panels, raised a little, ochre
        pc = gc["panels"]
        z0, z1, D = B["panels"]
        n = pc["count"]
        ei, ev = pc["inset_m"]
        wpan = (Lg - (n + 1) * ei) / n
        for i in range(n):
            a = ei + i * (wpan + ei)
            plate(frame, gm, rect(a, a + wpan, z0 + ev, z1 - ev), [], D - 0.005, D + pc["proud_m"], frames, 0.05)
        # the lights band, its windows let in
        lc = gc["lights"]
        z0, z1, D = B["lights"]
        post, pil = lc["posts_m"]
        wz0, wz1 = lc["z_m"]
        nw = 3
        ww = (Lg - 2 * post - (nw - 1) * pil) / nw
        spans = [(post + i * (ww + pil), post + i * (ww + pil) + ww) for i in range(nw)]
        plate(body, gm, rect(0.0, Lg, z0, z1), [rect(a, b, wz0, wz1) for a, b in spans], -0.01, D, ground, 0.06)
        rs, rg = lc["recess_m"]                         # the sash's face in from the band's, the glass in from the sash's
        for a, b in spans:
            self.sash(sash, gm, a, b, wz0, wz1, lc["panes"], lc["sash_m"], D - rs - 0.035, D - rs, self.paint["sash"])
            plate(glass, gm, rect(a, b, wz0, wz1), [], D - rs - 0.05, D - rs - rg, self.paint["glass"], 0.08)
        # pilasters: on the posts and between the windows, from the panels band to the cornice
        pp = lc["pilaster_proud_m"]
        for a, b in [(0.02, post - 0.02)] + [(spans[i][1] + 0.02, spans[i + 1][0] - 0.02) for i in range(nw - 1)] + \
                [(Lg - post + 0.02, Lg - 0.02)]:
            plate(frame, gm, rect(a, b, z0 + 0.03, z1 - 0.03), [], D - 0.005, D + pp, frames, 0.05)
        # a gilt bead under the cornice and along the base's top
        for zb_, Db in ((B["cornice"][0] + 0.012, B["cornice"][2]), (B["base"][1] - 0.012, B["base"][2])):
            ss = np.linspace(0.02, Lg - 0.02, 80)
            P2 = np.stack([ss, np.full(len(ss), zb_)], -1)
            P3 = gm(P2, np.full(len(ss), Db))
            V, F, M = carve.stroke_mesh(P3, self.g_n(P2, lambda Q, D_=Db: np.full(len(Q), D_)),
                                        np.full(len(ss), 0.016), self.paint["carving"])
            g.add(V, F, M)
        self.roof(gc, body, g)
        self.drop(gc, body, g)
        self.aft_light(gc, frame, sash, glass)
        self.info["galleries"] = {"length_m": Lg, "x_m_at": {str(z): [round(float(self.gal_xa(z)), 3),
                                                                     round(float(self.gal_xa(z)) + Lg, 3)]
                                                            for z in (B["base"][0], B["lights"][1], gc["roof"]["top_m"])},
                                  "windows_s_m": [[round(a, 3), round(b, 3)] for a, b in spans]}

    def roof_top(self, s, gc):
        r = gc["roof"]
        z_c = gc["bands"]["cornice"][1]
        Lg = gc["length_m"]
        t = smoothstep((np.asarray(s, float) - r["level_to_m"]) / (Lg - r["level_to_m"]))
        return r["top_m"] - (r["top_m"] - z_c - 0.03) * t

    def roof(self, gc, body, g):
        """the roof: from the cornice's top in to the side, its height falling forward to the cornice; its depth off
        the planking eased from the cornice's to nothing at its top (a sweeping hood); scales carved over it"""
        r = gc["roof"]
        Lg = gc["length_m"]
        zc = gc["bands"]["cornice"][1]
        Dr = r["depth_m"]

        def depth(P2):
            P2 = np.atleast_2d(np.asarray(P2, float))
            zt = self.roof_top(P2[:, 0], gc)
            t = np.clip((P2[:, 1] - zc) / np.maximum(zt - zc, 0.03), 0.0, 1.0)
            return np.maximum(Dr * (1.0 - smoothstep(t)) ** 0.8, self.g_floor(P2))
        ss = np.linspace(0.0, Lg, 60)
        outline = np.concatenate([[(0.0, zc - 0.01), (Lg, zc - 0.01)],
                                  np.stack([ss[::-1], self.roof_top(ss[::-1], gc)], -1)])
        outline = outline[np.concatenate([[True], np.linalg.norm(np.diff(outline, axis=0), axis=1) > 0.005])]
        to3d = lambda P2, d: self.gmap(P2, 0.5 * depth(P2) + np.asarray(d, float) * np.ones(len(P2)))  # noqa: E731
        slab(body, outline, [], 0.05, to3d, lambda P2: 0.5 * depth(P2), self.paint["ground"])
        seat = carve.Seat(*body.arrays()[:2])                  # the berries and the garland set down on its faces
        # the scales: rows of scallops, each a half ring hanging from its row with a berry in it, staggered
        sc = gc["scales"]
        R = sc["r_m"]
        th = np.linspace(math.pi, 2 * math.pi, 14)
        design = {"strokes": [], "leaves": [], "berries": []}
        for j in range(sc["rows"]):
            zr = sc["first_m"] + j * sc["pitch_m"]
            s0 = 0.06 + (R if j % 2 else 0.0)
            for s in np.arange(s0 + R, Lg, 2 * R):
                if zr + 0.3 * R > float(self.roof_top(s + R, gc)) - 0.04:
                    continue
                arc = np.stack([s + R * np.cos(th), zr + R * np.sin(th)], -1)
                design["strokes"].append((arc, np.full(len(arc), sc["rope_m"])))
                design["berries"].append((np.array([s, zr - 0.45 * R]), sc["berry_r_m"]))
        n = carve.relief(g, design, lambda P: np.asarray(P, float),
                         lambda P2: (self.gmap(P2, depth(P2)), self.g_n(P2, depth)), self.paint["carving"], seat=seat)
        # the garland down the roof's fore edge: leaves following its curve
        ga = gc["garland"]
        Lf, Wf, Hf = ga["leaf_m"]
        s_e = np.linspace(r["level_to_m"] + 0.3, Lg - 0.05, ga["leaves"])
        leaves = []
        for k, s in enumerate(s_e):
            zt = float(self.roof_top(s, gc))
            p = np.array([s - 0.04, zt - 0.08])
            q = np.array([s + 0.05, float(self.roof_top(s + 0.05, gc)) - 0.08])
            dirn = unit(q - p) * (1 if k % 2 else -1)
            leaves.append((p, unit(dirn + np.array([0.0, -0.5])), Lf, Wf, Hf))
        n += carve.relief(g, {"strokes": [], "leaves": leaves, "berries": []}, lambda P: np.asarray(P, float),
                          lambda P2: (self.gmap(P2, depth(P2)), self.g_n(P2, depth)), self.paint["carving"],
                          drape=True, seat=seat)
        self.info["roof"] = {"scales_triangles_a_side": n}

    def drop(self, gc, body, g):
        """the drop under the base: its outline curving down from the base's ends to a point; its depth off the
        planking eased from the base's to nothing at the outline's foot; a fan of gilt leaves on it"""
        dr = gc["drop"]
        Lg = gc["length_m"]
        zt, _, Db = gc["bands"]["base"]
        zb = dr["bottom_m"]
        sp = dr["point_at"] * Lg
        ss = np.linspace(0.0, Lg, 61)

        def foot(s):
            t = np.clip(np.asarray(s, float) / Lg, 0.0, 1.0)
            a = np.where(t < dr["point_at"], t / dr["point_at"], (1 - t) / (1 - dr["point_at"]))
            return zt - (zt - zb) * np.sin(0.5 * math.pi * a) ** 1.6

        def depth(P2):
            P2 = np.atleast_2d(np.asarray(P2, float))
            f = foot(P2[:, 0])
            t = np.clip((P2[:, 1] - f) / np.maximum(zt - f, 0.03), 0.0, 1.0)
            return np.maximum(Db * t ** dr["power"], self.g_floor(P2))
        outline = np.concatenate([np.stack([ss, foot(ss)], -1), [(Lg, zt + 0.01), (0.0, zt + 0.01)]])
        outline = outline[np.concatenate([[True], np.linalg.norm(np.diff(outline, axis=0), axis=1) > 0.005])]
        to3d = lambda P2, d: self.gmap(P2, 0.5 * depth(P2) + np.asarray(d, float) * np.ones(len(P2)))  # noqa: E731
        slab(body, outline, [], 0.05, to3d, lambda P2: 0.5 * depth(P2), self.paint["ground"])
        # leaves: a fan from the point up the drop; a gilt bead along its foot from end to end
        leaves = []
        pt = np.array([sp, zb + 0.08])
        Lf, Wf, Hf = dr["leaf_m"]
        for k, a in enumerate(np.linspace(-62.0, 62.0, 7)):
            dirn = np.array([math.sin(math.radians(a)) * 2.2, math.cos(math.radians(a))])
            leaves.append((pt, unit(dirn), Lf * (1.0 - 0.28 * abs(a) / 62.0), Wf, Hf))
        sb = np.linspace(0.04, Lg - 0.04, 90)
        Pb = np.stack([sb, foot(sb) + 0.6 * dr["bead_r_m"] + 0.012], -1)
        design = {"strokes": [(Pb, np.full(len(Pb), dr["bead_r_m"]))], "leaves": leaves,
                  "berries": [(pt + [0.0, -0.02], 0.035)]}
        carve.relief(g, design, lambda P: np.asarray(P, float),
                     lambda P2: (self.gmap(P2, depth(P2)), self.g_n(P2, depth)), self.paint["carving"], drape=True,
                     seat=carve.Seat(*body.arrays()[:2]))

    def aft_light(self, gc, frame, sash, glass):
        """a light in the gallery's after face: a sash of one pane by three, in a casing, between the planking and the
        gallery's outside"""
        al = gc["aft_light"]
        lc = gc["lights"]
        D = gc["bands"]["lights"][2]
        wz0, wz1 = lc["z_m"]
        d0, d1 = al["in_m"][0], D - al["in_m"][1]

        def amap(P2, h):
            """(d, z) on the after face, h aft off it"""
            P2 = np.atleast_2d(np.asarray(P2, float))
            h = np.broadcast_to(np.asarray(h, float), (len(P2),))
            S = self.gmap(np.stack([np.zeros(len(P2)), P2[:, 1]], -1), P2[:, 0])
            e = 0.004
            Pz = self.gmap(np.stack([np.zeros(len(P2)), P2[:, 1] + e], -1), P2[:, 0]) - \
                self.gmap(np.stack([np.zeros(len(P2)), P2[:, 1] - e], -1), P2[:, 0])
            Pd = self.gmap(np.stack([np.zeros(len(P2)), P2[:, 1]], -1), P2[:, 0] + e) - S
            n = unit(np.cross(Pz, Pd))
            n = np.where(n[:, :1] > 0, -n, n)
            return S + h[:, None] * n
        cw = 0.06
        plate(frame, amap, rect(d0 - cw, d1 + cw, wz0 - cw, wz1 + cw), [rect(d0, d1, wz0, wz1)], -0.005, 0.05,
              self.paint["frames"], 0.04)
        self.sash(sash, amap, d0, d1, wz0, wz1, al["panes"], lc["sash_m"], -0.005, 0.035, self.paint["sash"])
        plate(glass, amap, rect(d0, d1, wz0, wz1), [], -0.005, 0.015, self.paint["glass"], 0.08)

    # ---- the cabin's side light ---------------------------------------------------------------------------------------
    def cabin_window(self):
        """the great cabin's side light: the sash and its glass fill the port the skin cuts for it in the port band
        (slice 12: specs_1795.json cabin_lights_m, a port with no lid), its sill and head following the port's along the
        sheer (the window is drawn in a chart sheared to them), the casing round it on the side"""
        cw_ = self.c["cabin_window"]
        x0, x1 = cw_["x_m"]
        lights = self.sk.sp["inside"].get("cabin_lights_m", [])
        if not any(abs(a - x0) < 1e-3 and abs(f - x1) < 1e-3 for a, f in lights):
            raise SystemExit(f"stern: the cabin window's x {cw_['x_m']} is not a port the skin cuts {lights}")
        L, k, pr = self.L, self.face.k, self.sk.pr
        sill = lambda x: float(pr.S(np.array([L.mid_px + x / FT * L.ppf]))[0]) / k     # noqa: E731
        head = lambda x: float(pr.Shd(np.array([L.mid_px + x / FT * L.ppf]))[0]) / k     # noqa: E731
        xc = 0.5 * (x0 + x1)
        slope = (sill(x1) - sill(x0)) / (x1 - x0)
        z0, z1 = sill(xc), head(xc)
        frame = self.mesh("CabinWindowFrame", "stbd")
        sash = self.mesh("CabinWindowSash", "stbd")
        glass = self.mesh("CabinWindowGlass", "stbd")

        c = cw_["casing_m"]
        # laid on the smooth side lifted to the thickest strake under it, the casing's back sunk into the thinnest
        gx, gz = np.meshgrid(np.linspace(x0 - c, x1 + c, 12), np.linspace(z0 - c, z1 + c, 16))
        gz = gz + slope * (gx - xc)
        e = float(self.excess(gx.ravel(), gz.ravel()).max())

        def smap(P2, d):
            P2 = np.atleast_2d(np.asarray(P2, float))
            d = np.broadcast_to(np.asarray(d, float), (len(P2),))
            S, N = self.side(P2[:, 0], P2[:, 1] + slope * (P2[:, 0] - xc), smooth=True)
            return S + (e + d)[:, None] * N
        plate(frame, smap, rect(x0 - c, x1 + c, z0 - c, z1 + c), [rect(x0, x1, z0, z1)], -0.01 - e,
              cw_["casing_proud_m"], self.paint["ground"], 0.05)
        self.sash(sash, smap, x0, x1, z0, z1, cw_["panes"], self.c["windows"]["sash_m"], -0.01, 0.035, self.paint["sash"])
        plate(glass, smap, rect(x0, x1, z0, z1), [], -0.01, 0.012, self.paint["clear_glass"], 0.08)
        worst = max(abs(sill(x) - (z0 + slope * (x - xc))) + abs(head(x) - (z1 + slope * (x - xc)))
                    for x in np.linspace(x0, x1, 9))
        self.info["cabin_window"] = {"x_m": [x0, x1], "sill_m": [round(sill(x0), 3), round(sill(x1), 3)],
                                     "head_m": [round(head(x0), 3), round(head(x1), 3)],
                                     "off_port_mm": round(worst * 1000, 2)}
        if worst > 0.003:
            raise SystemExit(f"stern: the cabin window strays {worst * 1000:.1f} mm off its port's sill and head")

    # ---- the lanterns -------------------------------------------------------------------------------------------------
    def lanterns(self):
        """A six-sided lantern off each quarter on an iron bracket from the quarter piece: a base, the glazed body
        between iron bars, a roof and a finial."""
        lc = self.c["lanterns"]
        m = self.mesh("Lanterns", "stbd")
        gl = self.mesh("LanternGlass", "stbd")
        zb = lc["foot_z_m"]
        R = 0.5 * lc["across_m"]
        # aft of the stern's edge at its foot's height, and outboard of the taffrail's end (its widest ring clear of it)
        xe = float(self.face.edge_x(zb))
        ax = np.array([xe - lc["aft_m"], self.taffrail_half + 1.08 * R + lc["clear_m"], zb])     # its axis at its foot
        hb, hbody, hr, hf = lc["base_m"], lc["body_m"], lc["roof_m"], lc["finial_m"]
        k = np.arange(6) * math.pi / 3

        def hexring(z, r):
            return np.stack([ax[0] + r * np.cos(k), ax[1] + r * np.sin(k), np.full(6, ax[2] + z)], -1)
        iron = self.paint["iron"]
        # the base: a bowl from a small foot up to the body's rim
        rings = [hexring(0.0, 0.35 * R), hexring(0.4 * hb, 0.8 * R), hexring(hb, 1.05 * R)]
        V, F, M = sweep(rings, iron, closed=True, caps=True)
        m.add(*self.outward(V, F, M))
        # the body: glass panes, iron bars at the corners and rims
        z0, z1 = hb, hb + hbody
        Vg = np.concatenate([hexring(z0, 0.97 * R), hexring(z1, 0.97 * R)])
        Fg = [(i, (i + 1) % 6, 6 + (i + 1) % 6, 6 + i) for i in range(6)]
        Fg += [tuple(range(6))[::-1], tuple(range(6, 12))]
        gl.add(*self.outward(Vg, Fg, [self.paint["glass"]] * len(Fg)))
        b = 0.5 * lc["bar_m"]
        for i in range(6):
            p = np.array([ax[0] + R * math.cos(k[i]), ax[1] + R * math.sin(k[i])])
            ring0 = np.stack([p[0] + b * np.cos(k), p[1] + b * np.sin(k), np.full(6, ax[2] + z0)], -1)
            ring1 = ring0 + np.array([0.0, 0.0, hbody])
            V, F, M = sweep([ring0, ring1], iron, closed=True, caps=True)
            m.add(*self.outward(V, F, M))
        for z in (z0, z1):
            V, F, M = sweep([hexring(z - 0.02, 1.04 * R), hexring(z + 0.02, 1.04 * R)], iron, closed=True, caps=True)
            m.add(*self.outward(V, F, M))
        # the roof and the finial
        rings = [hexring(z1, 1.08 * R), hexring(z1 + 0.35 * hr, 0.85 * R), hexring(z1 + hr, 0.18 * R),
                 hexring(z1 + hr + 0.5 * hf, 0.22 * R), hexring(z1 + hr + hf, 0.05 * R)]
        V, F, M = sweep(rings, iron, closed=True, caps=True)
        m.add(*self.outward(V, F, M))
        # the bracket: an iron bar from the quarter piece's side (where it wraps the planking's ends) aft and out to
        # under the lantern, and a stay below it
        rb = lc["bracket_r_m"]
        q = self.c["quarter_pieces"]

        def root(z):
            S, N = self.side(float(self.face.edge_x(z)) + 0.5 * q["wrap_m"], z)
            return S[0] + N[0] * (q["out_m"] - 0.01)
        A, A2 = root(zb - 0.02), root(zb - 0.34)
        foot = ax + np.array([0.0, 0.0, -0.02])
        arm = np.array([A + t * (foot - A) + np.array([0, 0, 0.06 * math.sin(math.pi * t)]) for t in np.linspace(0, 1, 12)])
        stay = np.array([A2 + t * (0.5 * (A + foot) - A2) for t in np.linspace(0, 1, 8)])
        for path in (arm, stay):
            V, F, M = carve.stroke_mesh(path, np.tile(EZ, (len(path), 1)), np.full(len(path), rb), iron, sides=8,
                                        sink=-1.0)
            m.add(V, F, M)
        self.lantern_top = float(ax[2] + hb + hbody + hr + hf)
        self.lantern_pts = np.concatenate([np.asarray(v, float) for v in m.V + gl.V])
        self.info["lanterns"] = {"foot_m": np.round(ax, 3).tolist(), "top_z_m": round(self.lantern_top, 3)}

    def boom_check(self):
        """The spanker boom swung through its brace limits must pass over the lanterns (both, the port's mirrored): run
        once the limits are the build's (brace_limits'), with the lanterns in the scene"""
        lc = self.c["lanterns"]
        swing = max(abs(float(b)) for b in self.rig.meta["SpankerBoom"]["brace_deg"])
        P = self.lantern_pts
        clear = boom_clearance(self.rig, np.concatenate([P, P * np.array([1.0, -1.0, 1.0])]), swing)
        if clear < lc["boom_clear_min_m"]:
            raise ValueError(f"the spanker boom swung {swing} deg comes within {clear:.3f} m of a quarter lantern")
        self.info["lanterns"].update({"boom_clear_m": round(clear, 3), "boom_swing_deg": swing})

    # ---- all of it ------------------------------------------------------------------------------------------------
    def build(self):
        self.taffrail()
        self.frieze()
        self.ports()
        self.arch()
        self.stars()
        self.windows()
        self.pilasters()
        self.name()
        self.quarter_pieces()
        self.galleries()
        self.cabin_window()
        self.lanterns()
        return self

    def parts(self):
        """name -> (V, F, M, side): 'stbd' parts are the starboard half (mirror them for port), 'centre' parts whole."""
        out = {}
        for name, (mesh, side) in self.meshes.items():
            V, F, M = mesh.arrays()
            out[name] = compact(V, F, M) + (side,)
        return out


def boom_clearance(rig, pts, swing_deg=40.0, steps=81):
    """the least distance from points (n, 3) to the spanker boom's surface as it swings either way (its axis turned
    about the mizzen's): for the lanterns"""
    g = rig.spanker_geom["SpankerBoom"]
    o, R = rig.parts_["SpankerBoom"]["frame"]
    o, R = np.asarray(o, float), np.asarray(R, float)
    ax = R[:, 2]
    heel = o + R @ g["heel"]
    end = o + R @ (g["heel"] + g["length"] * g["axis"])
    best = 1e9
    for a in np.radians(np.linspace(-swing_deg, swing_deg, steps)):
        c, s_ = math.cos(a), math.sin(a)
        K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        Rot = np.eye(3) + s_ * K + (1 - c) * K @ K
        h, e = o + Rot @ (heel - o), o + Rot @ (end - o)
        d = e - h
        t = np.clip(((pts - h) @ d) / (d @ d), 0.0, 1.0)
        dist = np.linalg.norm(pts - (h + t[:, None] * d), axis=1) - 0.5 * g["d"]
        best = min(best, float(dist.min()))
    return best
