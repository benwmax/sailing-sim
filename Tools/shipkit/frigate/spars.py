"""The frigate's masts and yards (docs/shipkit-3): the three lower masts with their heads, cheeks, trestletrees,
crosstrees, tops and caps, the topmasts and topgallant masts with royal poles and trucks, every yard, the spanker boom
and gaff, and the bowsprit with its cap, jibboom, flying jibboom, dolphin striker and spritsail yard.

    from spars import Rig;  rig = Rig(L, skin_specs).build();  rig.parts()

Sizes come from spars_1795.json (each number with its source). Units: metres in the ship frame (X forward, Y starboard,
Z up, origin on the centreline at midships on waterline A). Lengths in the json are feet, diameters inches.

Every yard, the spanker boom and gaff and the spritsail yard is its own part with a frame: its origin on the axis it
turns about (the mast's, or the bowsprit's for the spritsail yard), local X forward, Y to starboard, Z up that axis. A
turn about local Z braces it; a move along local Z hoists it (rig.json-style limits in Rig.meta). Masts are built where
they stand; the yards hang hoisted. Rig.stem_bed is the bowsprit's underside over the stem head: build the rig first and
hand it to skin.Skin, which cuts the stem down to it.
"""
import json
import math
import os

import numpy as np
from scipy.interpolate import PchipInterpolator

import loft

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
Y = np.array([0.0, 1.0, 0.0])


# ---- mesh pieces -------------------------------------------------------------------------------------------------
class Mesh:
    """Vertices (metres), faces and a material per face."""

    def __init__(self):
        self.V, self.F, self.M = [], [], []
        self.n = 0

    def add(self, V, F, mat):
        V = np.asarray(V, float).reshape(-1, 3)
        self.V.append(V)
        self.F += [tuple(self.n + i for i in f) for f in F]
        self.M += [mat] * len(F)
        self.n += len(V)

    def arrays(self):
        V = np.concatenate(self.V) if self.V else np.zeros((0, 3))
        return V, list(self.F), list(self.M)

    def tris(self):
        return sum(len(f) - 2 for f in self.F)


def circle(r, n, phase=0.0):
    t = phase + np.arange(n) * 2 * math.pi / n
    return np.stack([r * np.cos(t), r * np.sin(t)], 1)


def square(h, n=4):
    """A square of half side h as n points (n a multiple of 4: corners included)."""
    k = n // 4
    pts = []
    for (ax, ay), (bx, by) in (((h, -h), (h, h)), ((h, h), (-h, h)), ((-h, h), (-h, -h)), ((-h, -h), (h, -h))):
        for i in range(k):
            t = i / k
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    return np.array(pts)


def rect(a0, a1, b0, b1):
    return np.array([[a1, b0], [a1, b1], [a0, b1], [a0, b0]], float)


def loft_solid(mesh, rings, mat, cap0=True, cap1=True):
    """A closed solid through rings: each ring (P (N,3)) has the same count, counter-clockwise seen from its far end."""
    n = len(rings[0])
    V = np.concatenate(rings)
    F = []
    for j in range(len(rings) - 1):
        a, b = j * n, (j + 1) * n
        for i in range(n):
            i1 = (i + 1) % n
            F.append((a + i, a + i1, b + i1, b + i))
    C = []
    if cap0:
        C.append(rings[0].mean(0))
        c0 = len(V) + len(C) - 1
        F += [(c0, (i + 1) % n, i) for i in range(n)]
    if cap1:
        C.append(rings[-1].mean(0))
        c1 = len(V) + len(C) - 1
        b = (len(rings) - 1) * n
        F += [(c1, b + i, b + (i + 1) % n) for i in range(n)]
    if C:
        V = np.concatenate([V, np.array(C)])
    mesh.add(V, F, mat)


def frame_ring(o, a, b, P2):
    """2D points (along a, along b) placed at origin o."""
    return o[None, :] + P2[:, :1] * a[None, :] + P2[:, 1:2] * b[None, :]


def spar(mesh, o, u, a, stations, mat, n=24, shape="round", phase=None):
    """A spar along unit axis u from origin o: stations [(s, radius)], cross-section axes a and b = u x a. shape round,
    oct (eight flat faces) or square (radius is the half side)."""
    b = np.cross(u, a)
    rings = []
    for s, r in stations:
        if shape == "round":
            P2 = circle(r, n, 0.0 if phase is None else phase)
        elif shape == "oct":
            P2 = circle(r / math.cos(math.pi / 8), 8, math.pi / 8)
        else:
            P2 = square(r)
        rings.append(frame_ring(o + s * u, a, b, P2))
    loft_solid(mesh, rings, mat)


def ring_band(mesh, o, u, a, s, r, broad, thick, mat, n=24):
    """An iron hoop: a short ring of rectangular section round an axis, inner radius r."""
    b = np.cross(u, a)
    ri, ro = r - 0.002, r + thick
    loops = [(ri, s - broad / 2), (ro, s - broad / 2), (ro, s + broad / 2), (ri, s + broad / 2)]
    rings = [frame_ring(o + z * u, a, b, circle(rr, n)) for rr, z in loops]
    m = len(rings)
    V = np.concatenate(rings)
    F = []
    for j in range(m):
        p, q = j * n, ((j + 1) % m) * n
        for i in range(n):
            i1 = (i + 1) % n
            F.append((p + i, p + i1, q + i1, q + i))
    mesh.add(V, F, mat)


def prism(mesh, o, u, a, P2, s0, s1, mat):
    """A convex outline P2 (in a, b = u x a) extruded along u from s0 to s1."""
    b = np.cross(u, a)
    P2 = np.asarray(P2, float)
    # counter-clockwise about +u
    area = 0.5 * np.sum(P2[:, 0] * np.roll(P2[:, 1], -1) - np.roll(P2[:, 0], -1) * P2[:, 1])
    if area < 0:
        P2 = P2[::-1]
    loft_solid(mesh, [frame_ring(o + s0 * u, a, b, P2), frame_ring(o + s1 * u, a, b, P2)], mat)


def area2(P):
    return 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))


def unit2(v):
    return v / max(float(np.linalg.norm(v)), 1e-12)


def clip_convex(P, C):
    """Sutherland-Hodgman: polygon P clipped by the convex polygon C (both 2D)."""
    if area2(C) < 0:
        C = C[::-1]
    out = np.asarray(P, float)
    for i in range(len(C)):
        a, b = C[i], C[(i + 1) % len(C)]
        if len(out) == 0:
            break
        inside = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12
        res = []
        for j in range(len(out)):
            p, q = out[j], out[(j + 1) % len(out)]
            ip, iq = inside(p), inside(q)
            if ip:
                res.append(p)
            if ip != iq:
                d = (q - p)
                den = (b[0] - a[0]) * d[1] - (b[1] - a[1]) * d[0]
                tt = ((b[1] - a[1]) * (p[0] - a[0]) - (b[0] - a[0]) * (p[1] - a[1])) / den
                res.append(p + tt * d)
        out = np.array(res)
    return out


def clear_line(R, s0, s1, rb, gap, n=48):
    """Offsets (h0, h1) at s0 and s1 of a straight boom's axis from a spar's axis, for a boom of radius rb lying along
    the spar from s0 to s1: at s0 it just clears R(s0) by gap, and h1 is the least that keeps it clear of R(s) all along."""
    need = lambda s: R(s) + rb + gap
    h0 = need(s0)
    h1 = need(s1)
    for s in np.linspace(s0, s1, n)[1:]:
        t = (s - s0) / (s1 - s0)
        h1 = max(h1, h0 + (need(s) - h0) / t)
    return h0, h1


def box(mesh, c, ax, ay, az, hx, hy, hz, mat):
    """An oriented box: centre c, unit axes, half sizes."""
    P2 = rect(-hx, hx, -hy, hy)
    prism(mesh, c, az, ax, P2, -hz, hz, mat)
    return mesh


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def taper(ratios):
    """A smooth diameter ratio along 0..1 through the quarter points."""
    xs = np.linspace(0, 1, len(ratios))
    return PchipInterpolator(xs, ratios)


# ---- the rig -----------------------------------------------------------------------------------------------------
class Rig:
    def __init__(self, L, skin_specs, path=os.path.join(HERE, "spars_1795.json")):
        import skin
        self.L = L
        self.sp = json.load(open(path))
        self.pr = skin.Profile(L, skin_specs)
        ins = skin_specs["inside"]
        self.deck_drop_ft = ins["spar_deck_below_plankshear_in"] / 12.0
        self.rail_cap_ft = skin_specs["rail"]["thick_in"] / 12.0
        self.parts_ = {}
        self.meta = {}
        self.masts = {}
        f = self.sp["fittings"]
        self.fit = f
        self.mat_wood, self.mat_black, self.mat_iron = (self.sp["paint"][k] for k in ("wood", "black", "iron"))

    # hull heights (feet above A) at ship x feet from midships
    def _xpx(self, x_ft):
        return np.array([self.L.mid_px + x_ft * self.L.ppf])

    def spar_deck_ft(self, x_ft):
        return float(np.ravel(self.pr.P(self._xpx(x_ft)))[0]) / self.L.ppf_y - self.deck_drop_ft

    def gun_deck_ft(self, x_ft):
        return float(np.ravel(self.pr.G(self._xpx(x_ft)))[0]) / self.L.ppf_y

    def rabbet_ft(self, x_ft):
        return float(self.L.rabbet_z(float(self._xpx(x_ft)[0]))) / self.L.ppf_y

    def rail_ft(self, x_ft):
        return float(np.ravel(self.pr.R1(self._xpx(x_ft)))[0]) / self.L.ppf_y

    @staticmethod
    def nseg(d):
        return 48 if d > 0.5 else 32 if d > 0.25 else 24 if d > 0.12 else 16

    def part(self, name):
        if name not in self.parts_:
            self.parts_[name] = {"mesh": Mesh(), "frame": None}
        return self.parts_[name]["mesh"]

    # ---- one mast --------------------------------------------------------------------------------------------------
    def mast(self, name):
        S = self.sp["masts"][name]
        fit = self.fit
        r = math.radians(S["rake_deg"])
        u = np.array([-math.sin(r), 0.0, math.cos(r)])             # up the mast (raking aft)
        f = np.array([math.cos(r), 0.0, math.sin(r)])              # forward, square to it
        x0 = S["x_ft"]
        zd = self.spar_deck_ft(x0)
        O = np.array([x0, 0.0, zd]) * FT                           # on the axis at the spar deck
        lo, tp, tm, tg = S["lower"], S["top"], S["topmast"], S["topgallant"]
        D = lo["diam_in"] * IN
        s_step = ((self.rabbet_ft(x0) + self.sp["step"]["keelson_over_rabbet_ft"]) - zd) * FT / math.cos(r)
        s_gun = (self.gun_deck_ft(x0) - zd) * FT / math.cos(r)
        s_top = s_step + lo["length_ft"] * FT                      # the masthead's top
        head = lo["head_ft"] * FT
        s_h = s_top - head                                         # the hounds: the trestletrees sit here
        mt = taper(self.sp["taper"]["mast"])
        M = self.part(f"Mast_{name.capitalize()}")
        W, B, I = self.mat_wood, self.mat_black, self.mat_iron

        # lower mast: the round body from the step to the hounds (greatest at the spar deck), the square head
        def R_lower(s):
            if s <= 0:
                return D / 2 * (0.9 + 0.1 * (s - s_step) / (0 - s_step))
            return D / 2 * float(mt(min(1.0, s / s_h)))
        n = self.nseg(D)
        ss = list(np.linspace(s_step + 0.25 * D, 0, 5)) + list(np.linspace(0, s_h, 13)[1:])
        spar(M, O, u, f, [(s, R_lower(s)) for s in ss], W, n)
        spar(M, O, u, f, [(s_step, 0.3 * D), (s_step + 0.25 * D, 0.3 * D)], W, shape="square")     # the heel's tenon
        hs = fit["head_square"] * D / 2
        spar(M, O, u, f, [(s_h - 0.02, hs), (s_top, hs * 0.96)], B, shape="square")
        # cheeks (hounds) on both sides under the trestletrees
        ch = fit["cheek"]
        # they stop clear above the lower yard's slings (its drop under the top is the mast's yard_below_top_ft)
        s_plat0 = s_h + (fit["trestletree"]["depth"] + fit["crosstree"]["depth"]) * D + fit["top_plank_in"] * IN
        ly = [y for y in self.sp["yards"].values() if isinstance(y, dict) and y.get("mast") == name and y["on"] == "lower"]
        r_ly = self.sp["yards"]["diam_in_per_yard"] * ly[0]["length_ft"] / 3.0 * IN / 2 if ly else 0.0
        s_ly = s_plat0 - S["yard_below_top_ft"] * FT / math.cos(r)
        lows = [s_ly + r_ly]
        if name == "mizzen":                                       # and above the spanker gaff's jaws
            g = self.sp["spanker"]["gaff"]
            lows.append(s_plat0 - g["jaws_below_top_ft"] * FT / math.cos(r) + 0.85 * g["diam_in"] * IN / 2)
        c_len = min(ch["length_of_head"] * head, s_h - (max(lows) + ch["clear_of_yard_ft"] * FT))
        for sgn in (1, -1):
            rings = []
            for s, t in ((s_h - c_len, 0.0), (s_h - 0.5 * c_len, 0.55), (s_h, 1.0)):
                rr = R_lower(s)
                y0, y1 = rr * 0.7, rr + ch["thick"] * D * max(t, 0.04)
                P2 = rect(-ch["broad"] * D / 2, ch["broad"] * D / 2, sgn * y0, sgn * y1)
                if sgn < 0:
                    P2 = P2[::-1]
                rings.append(frame_ring(O + s * u, f, Y, P2))
            loft_solid(M, rings, B)
        # iron hoops on the made mast: from the step up to the cheeks, every 4 ft
        hp = fit["hoops"]
        for s in np.arange(s_step + 2 * FT, s_h - c_len - 0.5 * FT, hp["pitch_ft"] * FT):
            ring_band(M, O, u, f, s, R_lower(s), hp["broad_in"] * IN, hp["thick_in"] * IN, I, n)
        # the mast coat at the spar deck (canvas over the wedges)
        mc = fit["mast_coat"]
        R0 = R_lower(0.0)
        rings = [frame_ring(O + z * u, f, Y, circle(rr, n)) for rr, z in
                 ((R0 - 0.002, -0.01), (R0 + mc["out_in"] * IN, 0.0), (R0 + 0.3 * IN, mc["height_in"] * IN),
                  (R0 - 0.002, mc["height_in"] * IN))]
        loft_solid(M, rings, B)

        # trestletrees, crosstrees and the top
        tt, ct = fit["trestletree"], fit["crosstree"]
        Lt, Bt = tp["fore_aft_ft"] * FT, tp["breadth_ft"] * FT
        D_tm = tm["diam_in"] * IN
        hg = fit["head_gap_in"]
        gap = hg[name] * IN                                        # room for the stays' eyes (slice 4)
        off_tm = hs + D_tm / 2 + gap                              # the topmast's axis before the masthead's
        fa, ff = -0.45 * Lt, 0.55 * Lt                             # the top's aft edge and fore point
        s_tt1 = s_h + tt["depth"] * D
        s_ct1 = s_tt1 + ct["depth"] * D
        plank = fit["top_plank_in"] * IN
        s_plat = s_ct1 + plank
        tops = self.part(f"Top_{name.capitalize()}")
        for sgn in (1, -1):
            yc = sgn * (hs + tt["breadth"] * D / 2)
            c = O + (s_h + s_tt1) / 2 * u + 0.5 * (fa + 0.03 * Lt + ff - 0.12 * Lt) * f + yc * Y
            box(tops, c, f, Y, u, (ff - 0.12 * Lt - fa - 0.03 * Lt) / 2, tt["breadth"] * D / 2, (s_tt1 - s_h) / 2, B)
        # bolsters on the trestletrees beside the masthead (the shrouds' eyes bed on them), and the topmast's iron fid.
        # They run from just before the after crosstree to 0.8 of the gap before the masthead: the shrouds' legs lie side
        # by side over them (slice 4)
        bo = fit["bolster"]
        bolster_x = (-1.1 * hs, hs + 0.8 * gap)
        for sgn in (1, -1):
            c = O + (s_tt1 + bo * D / 2) * u + sgn * (hs + tt["breadth"] * D / 2) * Y
            spar(tops, c + bolster_x[0] * f, f, u, [(0.0, bo * D / 2), (bolster_x[1] - bolster_x[0], bo * D / 2)], B, 12)
        c = O + (s_tt1 + fit["fid"] * D_tm / 2) * u + off_tm * f
        box(tops, c, f, Y, u, fit["fid"] * D_tm / 2, hs + tt["breadth"] * D * 0.8, fit["fid"] * D_tm / 2, self.mat_iron)
        outline = self.top_outline(fa, ff, Bt)
        # the lubber's hole: x0, x1, half width. Its sides stand off the trestletrees' outer faces by lubber_hole_in, so
        # the lower shrouds' legs pass down through it clear of its coaming (slice 4)
        hole = (-hs - 0.6 * FT, off_tm + D_tm / 2 + 0.6 * FT, hs + tt["breadth"] * D + fit["lubber_hole_in"][name] * IN)
        ct_xs = (fa + 0.03 * Lt + ct["breadth"] * D / 2 + 0.01, -hs - ct["breadth"] * D / 2 - 0.05,
                 off_tm + D_tm / 2 + ct["breadth"] * D / 2 + 0.05, ff - 0.2 * Lt)
        for xc in ct_xs:
            hw = self.top_half_width(outline, xc) - 0.12 * FT
            c = O + (s_tt1 + s_ct1) / 2 * u + xc * f
            box(tops, c, f, Y, u, ct["breadth"] * D / 2, hw, (s_ct1 - s_tt1) / 2, B)
        self.top_planks(tops, O, u, f, outline, hole, s_ct1, s_plat, B)
        self.top_rim(tops, O, u, f, outline, s_plat, B)
        self.top_rail(tops, O, u, f, fa, Bt, s_plat, B)

        # the lower cap
        cap = fit["cap"]
        c_mar = cap["margin_of_topmast"] * D_tm
        c_dep = cap["depth_of_topmast"] * D_tm
        hb = hs + c_mar
        P2 = self.cap_outline(-hs - c_mar, off_tm + D_tm / 2 + c_mar, hb)
        prism(tops, O, u, f, P2, s_top, s_top + c_dep, B)
        self.cap_band(tops, O, u, f, P2, s_top, c_dep)
        s_cap1 = s_top + c_dep

        # the topmast: square heel on the fid, round body (greatest at the cap), square head with cheeks
        Otm = O + off_tm * f
        s0 = s_h - 0.5 * D_tm
        s_tm_top = s0 + tm["length_ft"] * FT
        h_tm = tm["head_ft"] * FT
        s_tmh = s_tm_top - h_tm
        M2 = self.part(f"Topmast_{name.capitalize()}")
        spar(M2, Otm, u, f, [(s0, D_tm / 2), (s0 + 1.6 * D_tm, D_tm / 2)], W, shape="square")

        def R_tm(s):
            if s <= s_cap1:
                return D_tm / 2
            return D_tm / 2 * float(mt(min(1.0, (s - s_cap1) / (s_tmh - s_cap1))))
        ss = [s0 + 1.6 * D_tm - 0.01] + list(np.linspace(s_cap1, s_tmh, 10))
        spar(M2, Otm, u, f, [(s, R_tm(s)) for s in ss], W, self.nseg(D_tm))
        hs_tm = fit["head_square"] * D_tm / 2
        spar(M2, Otm, u, f, [(s_tmh - 0.01, hs_tm), (s_tm_top, hs_tm * 0.96)], B, shape="square")
        c_len2 = ch["topmast_length_of_head"] * h_tm
        for sgn in (1, -1):
            rings = []
            for s, t in ((s_tmh - c_len2, 0.0), (s_tmh - 0.5 * c_len2, 0.55), (s_tmh, 1.0)):
                rr = R_tm(s)
                P2 = rect(-ch["broad"] * D_tm / 2, ch["broad"] * D_tm / 2, sgn * rr * 0.7,
                          sgn * (rr + ch["topmast_thick"] * D_tm * max(t, 0.04)))
                if sgn < 0:
                    P2 = P2[::-1]
                rings.append(frame_ring(Otm + s * u, f, Y, P2))
            loft_solid(M2, rings, B)
        # topmast trestletrees and crosstrees
        D_tg = tg["diam_in"] * IN
        off_tg = hs_tm + D_tg / 2 + hg["topmast"][name] * IN
        L2 = fit["topmast_trestletrees_of_top"] * Lt
        B2 = fit["topmast_crosstrees_of_top"] * Bt
        tt_d, tt_b = tt["depth"] * D_tm, tt["breadth"] * D_tm
        ct_d, ct_b = ct["depth"] * D_tm * 1.2, ct["breadth"] * D_tm
        s_a, s_b = s_tmh, s_tmh + tt_d
        a2, f2 = -0.35 * L2, 0.65 * L2
        for sgn in (1, -1):
            c = Otm + (s_a + s_b) / 2 * u + (a2 + f2) / 2 * f + sgn * (hs_tm + tt_b / 2) * Y
            box(tops, c, f, Y, u, (f2 - a2) / 2, tt_b / 2, tt_d / 2, B)
        c = Otm + (s_b + fit["fid"] * D_tg / 2) * u + off_tg * f
        box(tops, c, f, Y, u, fit["fid"] * D_tg / 2, hs_tm + tt_b * 0.8, fit["fid"] * D_tg / 2, self.mat_iron)
        ct2_xs = (-hs_tm - ct_b / 2 - 0.02, off_tg + D_tg / 2 + ct_b / 2 + 0.03, f2 - ct_b / 2 - 0.05)
        for xc in ct2_xs:
            c = Otm + (s_b + ct_d / 2) * u + xc * f
            box(tops, c, f, Y, u, ct_b / 2, B2 / 2, ct_d / 2, B)
        # the topmast cap
        c_mar2, c_dep2 = cap["margin_of_topmast"] * D_tg, cap["depth_of_topmast"] * D_tg
        P2 = self.cap_outline(-hs_tm - c_mar2, off_tg + D_tg / 2 + c_mar2, hs_tm + c_mar2)
        prism(tops, Otm, u, f, P2, s_tm_top, s_tm_top + c_dep2, B)
        self.cap_band(tops, Otm, u, f, P2, s_tm_top, c_dep2)
        s_tmcap1 = s_tm_top + c_dep2
        s_tmct1 = s_b + ct_d                                       # the topmast crosstrees' top

        # the topgallant mast and royal pole, with the truck
        Otg = Otm + off_tg * f
        t0 = s_tmh - 0.5 * D_tg
        s_stop = t0 + tg["length_ft"] * FT
        s_pole = s_stop + tg["pole_ft"] * FT
        M3 = self.part(f"Topgallant_{name.capitalize()}")
        spar(M3, Otg, u, f, [(t0, D_tg / 2), (t0 + 1.6 * D_tg, D_tg / 2)], W, shape="square")

        def R_tg(s):
            if s <= s_tmcap1:
                return D_tg / 2
            if s <= s_stop:
                return D_tg / 2 * float(mt(min(1.0, (s - s_tmcap1) / (s_stop - s_tmcap1))))
            p0, p1 = self.sp["taper"]["pole"]
            return D_tg / 2 * (p0 + (p1 - p0) * (s - s_stop) / (s_pole - s_stop))
        nt = self.nseg(D_tg)
        ss = [t0 + 1.6 * D_tg - 0.01] + list(np.linspace(s_tmcap1, s_stop, 7))
        spar(M3, Otg, u, f, [(s, R_tg(s)) for s in ss], W, nt)
        spar(M3, Otg, u, f, [(s_stop, R_tg(s_stop + 1e-6)), (s_pole, R_tg(s_pole))], W, nt)
        tr = 0.55 * D_tg
        spar(M3, Otg, u, f, [(s_pole - 0.01, tr * 0.8), (s_pole, tr), (s_pole + 0.3 * D_tg, tr),
                             (s_pole + 0.4 * D_tg, tr * 0.7)], B, 16)                                  # the truck

        self.masts[name] = dict(O=O, u=u, f=f, s_step=s_step, s_gun=s_gun, s_h=s_h, s_top=s_top, s_plat=s_plat,
                                s_cap1=s_cap1, Otm=Otm, s_tm0=s0, s_tmh=s_tmh, s_tm_top=s_tm_top, s_tmcap1=s_tmcap1,
                                Otg=Otg, s_tg0=t0, s_ly=s_ly, c_len2=c_len2, s_tmct1=s_tmct1, s_stop=s_stop, s_pole=s_pole, D=D, D_tm=D_tm, D_tg=D_tg,
                                R_lower=R_lower, R_tm=R_tm, R_tg=R_tg, head=head, deck_ft=zd, Lt=Lt, Bt=Bt, fa=fa, ff=ff,
                                # for the standing rigging (slice 4): the heads, trestletrees, bolsters and crosstrees
                                hs=hs, tt_b=tt["breadth"] * D, s_tt1=s_tt1, s_ct1=s_ct1, bolster_r=bo * D / 2, bolster_x=bolster_x,
                                ct_b=ct["breadth"] * D, ct_xs=ct_xs, outline=outline, off_tm=off_tm, hs_tm=hs_tm,
                                tt2_b=tt_b, s_tt2a=s_a, s_tt2b=s_b, ct2_d=ct_d, ct2_b=ct_b, ct2_xs=ct2_xs, B2=B2,
                                off_tg=off_tg, s_tm_heel=s0, s_tg_heel=t0, fid_tm=fit["fid"] * D_tm, fid_tg=fit["fid"] * D_tg,
                                hole=hole, plank=plank)

    # ---- the top's pieces ------------------------------------------------------------------------------------------
    @staticmethod
    def top_outline(fa, ff, B):
        """The top's outline (fore-aft x, athwart y): straight aft edge and sides, the fore part an elliptic arc."""
        xs = fa + 0.3 * (ff - fa)
        a, b = ff - xs, B / 2
        t = np.linspace(-math.pi / 2, math.pi / 2, 25)
        arc = np.stack([xs + a * np.cos(t), b * np.sin(t)], 1)
        return np.concatenate([[[fa, -b]], arc, [[fa, b]]])

    @staticmethod
    def top_half_width(P, x):
        """Half width of the outline at fore-aft x."""
        best = 0.0
        for i in range(len(P) - 1):
            (x0, y0), (x1, y1) = P[i], P[i + 1]
            if min(x0, x1) - 1e-9 <= x <= max(x0, x1) + 1e-9 and abs(x1 - x0) > 1e-9:
                yy = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                best = max(best, abs(yy))
        return best

    def top_planks(self, mesh, O, u, f, P, hole, s0, s1, mat):
        """Planks laid fore and aft, 9 in wide with a quarter inch between, each cut to the top's outline (its fore
        end follows the curve under the rim) and round the lubber's hole."""
        B = P[:, 1].max()
        w, g = 9 * IN, 0.25 * IN
        nplank = int(round(2 * B / (w + g)))
        edges = np.linspace(-B, B, nplank + 1)
        fa = P[0, 0]
        hx0, hx1, hw = hole
        inner = self.offset_outline(P, 0.6 * IN)
        for y0, y1 in zip(edges[:-1], edges[1:]):
            a, b = y0 + g / 2, y1 - g / 2
            spans = [(fa + 0.5 * IN, P[:, 0].max() + 1.0)]
            if b > -hw and a < hw:
                spans = [(fa + 0.5 * IN, hx0), (hx1, P[:, 0].max() + 1.0)]
            for x0, x1 in spans:
                poly = clip_convex(inner, rect(x0, x1, a, b))
                if len(poly) < 3 or np.ptp(poly[:, 0]) < 0.05:
                    continue
                prism(mesh, O, u, f, poly, s0, s1, mat)
        # the lubber's hole's frame: a coaming round it, flush with the planks
        for x in (hx0, hx1):
            c = O + (s0 + s1) / 2 * u + x * f
            box(mesh, c, f, Y, u, 1.5 * IN, hw + 1.5 * IN, (s1 - s0) / 2 + 0.5 * IN, mat)
        for sgn in (1, -1):
            c = O + (s0 + s1) / 2 * u + 0.5 * (hx0 + hx1) * f + sgn * hw * Y
            box(mesh, c, f, Y, u, (hx1 - hx0) / 2, 1.5 * IN, (s1 - s0) / 2 + 0.5 * IN, mat)

    @staticmethod
    def offset_outline(P, d):
        """The convex outline moved inward by d (each point along its corner's inward bisector)."""
        A = area2(P)
        Q = P if A > 0 else P[::-1]
        n = len(Q)
        out = []
        for i in range(n):
            p0, p1, p2 = Q[i - 1], Q[i], Q[(i + 1) % n]
            e0, e1 = unit2(p1 - p0), unit2(p2 - p1)
            n0, n1 = np.array([-e0[1], e0[0]]), np.array([-e1[1], e1[0]])      # inward normals (counter-clockwise)
            m = n0 + n1
            m = m / max(np.linalg.norm(m), 1e-9)
            out.append(p1 + m * d / max(m @ n0, 0.3))
        return np.array(out)

    def top_rim(self, mesh, O, u, f, P, s_plat, mat):
        """The rim round the fore edge and sides: a timber 4 in broad, standing 1 in proud of the planks."""
        rb, rd = (v * IN for v in self.fit["top_rim_in"])
        pts = P[1:-1]
        # offset each point inward by the rim's breadth along the outline's normal
        n = len(pts)
        rings = []
        inner = []
        for i in range(n):
            p0, p1 = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
            t = unit(np.array([p1[0] - p0[0], p1[1] - p0[1], 0.0]))
            nrm = np.array([t[1], -t[0]])                     # outward for a counter-clockwise outline: flipped below
            inner.append(pts[i] + nrm * rb)
        inner = np.array(inner)
        if np.mean(np.linalg.norm(inner, axis=1)) > np.mean(np.linalg.norm(pts, axis=1)):
            inner = 2 * pts - inner                           # so the rim's inner edge is inside the outline
        zlo, zhi = s_plat - rd + 1 * IN, s_plat + 1 * IN
        for i in range(n):
            q = [(pts[i], zlo), (pts[i], zhi), (inner[i], zhi), (inner[i], zlo)]
            ring = np.array([O + z * u + p[0] * f + p[1] * Y for p, z in q])
            rings.append(ring)
        V = np.concatenate(rings)
        F = []
        for j in range(n - 1):
            a, b = 4 * j, 4 * (j + 1)
            for k in range(4):
                k1 = (k + 1) % 4
                F.append((a + k, b + k, b + k1, a + k1))
        F.append((0, 1, 2, 3))
        e = 4 * (n - 1)
        F.append((e + 3, e + 2, e + 1, e + 0))
        mesh.add(V, F, mat)

    def top_rail(self, mesh, O, u, f, fa, B, s_plat, mat):
        """The top's after rail on five stanchions, and the after crosstree's cover board along the aft edge."""
        h = self.fit["top_rail_ft"] * FT
        st = 3.5 * IN
        for y in np.linspace(-0.47 * B, 0.47 * B, 5):
            c = O + (s_plat + h / 2) * u + (fa + 2.5 * IN) * f + y * Y
            box(mesh, c, f, Y, u, st / 2, st / 2, h / 2, mat)
        c = O + (s_plat + h + 1.5 * IN) * u + (fa + 2.5 * IN) * f
        box(mesh, c, f, Y, u, 2.5 * IN, 0.5 * B, 1.5 * IN, mat)
        c = O + (s_plat - 2 * IN) * u + (fa + 3 * IN) * f
        box(mesh, c, f, Y, u, 3 * IN, 0.5 * B, 4 * IN, mat)

    def cap_band(self, mesh, O, u, f, P2, s0, dep):
        """The iron strap round a cap's sides, 0.3 of its depth up."""
        Q = self.offset_outline(P2, -0.5 * IN)
        prism(mesh, O, u, f, Q, s0 + 0.3 * dep, s0 + 0.3 * dep + 3 * IN, self.mat_iron)

    @staticmethod
    def cap_outline(xa, xf, hb):
        """A cap's plan: square aft, its fore end rounded."""
        r = hb
        xc = xf - r
        t = np.linspace(-math.pi / 2, math.pi / 2, 13)
        arc = np.stack([xc + r * np.cos(t), r * np.sin(t)], 1)
        return np.concatenate([[[xa, -hb]], arc, [[xa, hb]]])

    # ---- yards -----------------------------------------------------------------------------------------------------
    def yard_mesh(self, name, length, d, x_off, oct_mid, booms):
        """A yard along local Y, its centre at local X = x_off: octagonal in the middle third (lower and topsail
        yards), round outside it, tapering by quarters to the yardarms, with sling and stop cleats and its studding sail
        booms."""
        M = Mesh()
        Ys = self.sp["yards"]
        yt = taper(self.sp["taper"]["yard"])
        half = length / 2
        arm = half * {"lower": 1 / 10, "topmast": 2 / 9, "topgallant": 1 / 6, "pole": 1 / 6}[oct_mid[1]]
        n = self.nseg(d)
        o = np.array([x_off, 0.0, 0.0])
        R = lambda yy: d / 2 * float(yt(min(1.0, abs(yy) / half)))
        B = self.mat_black
        third = length / 6 if oct_mid[0] else 0.0
        for sgn in (1, -1):
            ss = np.linspace(third, half, 11)
            if third > 0:
                ss = np.concatenate([[third - 0.01], ss[1:]])
            spar(M, o, Y * sgn, np.array([0.0, 0.0, 1.0]), [(s, R(s)) for s in ss], B, n)
        if third > 0:
            rings = []
            for yy in np.linspace(-third, third, 5):
                rr = R(yy)
                P2 = circle(rr / math.cos(math.pi / 8), 8, math.pi / 8)
                rings.append(frame_ring(o + yy * Y, np.array([0, 0, 1.0]), np.array([1.0, 0, 0]), P2))
            loft_solid(M, rings, B)
        # cleats: two sling cleats on the yard's top, a stop cleat fore and aft at each yardarm
        cl = d * 0.22
        for yy in (-0.06 * length, 0.06 * length):
            c = o + yy * Y + np.array([0, 0, R(yy) + cl / 2 - 0.004])
            box(M, c, np.array([1.0, 0, 0]), Y, np.array([0, 0, 1.0]), cl * 0.6, cl * 1.2, cl / 2, B)
        for sgn in (1, -1):
            yy = sgn * (half - arm)
            for fx in (1, -1):
                c = o + yy * Y + np.array([fx * (R(yy) + cl / 2 - 0.004), 0, 0])
                box(M, c, np.array([1.0, 0, 0]), Y, np.array([0, 0, 1.0]), cl / 2, cl * 0.9, cl * 0.6, B)
        # studding sail booms on the yard's top, fore side: each lies on its own half of the yard, its heel lashed
        # beside the slings, through an iron at the yardarm and another a third of the way in, its end a little past
        # the yardarm. The boom is straight, so it is laid to clear the yard (octagon and taper) all along
        if booms:
            sb = Ys["studding_sail_booms"]
            bl = sb["length_of_yard"] * length
            bd = sb["diam_in_per_ft"] * bl / FT * IN
            nb = self.nseg(bd)
            th = math.radians(55)
            dirn = np.array([math.cos(th), 0.0, math.sin(th)])
            R_hull = lambda yy: R(yy) * (1.0 / math.cos(math.pi / 8) if abs(yy) < third else 1.0)     # octagon's corners
            for sgn in (1, -1):
                y0, y_iron = 0.03 * length, half - 0.02
                h0, h1 = clear_line(R_hull, y0, y_iron, bd / 2, 0.6 * IN)
                c0 = o + sgn * y0 * Y + h0 * dirn
                c1 = o + sgn * y_iron * Y + h1 * dirn
                ub = unit(c1 - c0)
                aa = np.array([0, 0, 1.0]) - (np.array([0, 0, 1.0]) @ ub) * ub
                spar(M, c0, ub, aa, [(0.0, bd * 0.42), (0.06 * bl, bd / 2), (0.85 * bl, bd / 2 * 0.9), (bl, bd / 2 * 0.7)],
                     self.mat_wood, nb)
                for frac in (1.0, 1.0 / 3.0):                    # the yardarm iron, the inner iron
                    yy = y0 + frac * (y_iron - y0)
                    t = (yy - y0) / (y_iron - y0)
                    hb = h0 + t * (h1 - h0)
                    r_y = R_hull(yy)
                    ring_band(M, o, sgn * Y, np.array([0, 0, 1.0]), yy, r_y, 3 * IN, 0.6 * IN, self.mat_iron, n)
                    cb = c0 + (yy - y0) / (ub @ (sgn * Y)) * ub
                    ring_band(M, cb, ub, aa, 0.0, (bd / 2) * (0.9 if frac == 1.0 else 1.0), 3 * IN, 0.5 * IN,
                              self.mat_iron, nb)
                    # the iron's neck from the yard's band to the boom's ring
                    nl0, nl1 = r_y + 0.3 * IN, hb - bd / 2
                    if nl1 > nl0:
                        cn = o + sgn * yy * Y + (nl0 + nl1) / 2 * dirn
                        box(M, cn, dirn, Y, np.cross(dirn, Y), (nl1 - nl0) / 2 + 0.4 * IN, 1.5 * IN, 0.75 * IN,
                            self.mat_iron)
        return M

    def yards(self):
        Ys = self.sp["yards"]
        per = Ys["diam_in_per_yard"]
        booms = set(Ys["studding_sail_booms"]["yards"])
        gap = 3 * IN
        for name, Yd in Ys.items():
            if not isinstance(Yd, dict) or "mast" not in Yd:
                continue
            m = self.masts[Yd["mast"]]
            length = Yd["length_ft"] * FT
            d = per * Yd["length_ft"] / 3.0 * IN
            on = Yd["on"]
            u, f = m["u"], m["f"]
            if on == "lower":
                O, s = m["O"], m["s_ly"]
                Rmax = m["R_lower"](s)
                lowered = 0.0
            elif on == "topmast":
                O = m["Otm"]
                s = m["s_tmh"] - m["c_len2"] - (d / 2 + self.fit["cheek"]["clear_of_yard_ft"] * FT)   # under the cheeks
                Rmax = m["D_tm"] / 2
                lowered = (m["s_cap1"] + d / 2 + 0.4 * FT) - s
            elif on == "topgallant":
                O = m["Otg"]
                s = m["s_stop"] - (d / 2 + 0.6 * FT)
                Rmax = m["D_tg"] / 2
                lowered = (m["s_tmcap1"] + d / 2 + 0.3 * FT) - s
            else:
                O = m["Otg"]
                s = m["s_pole"] - (d / 2 + 1.3 * FT)
                Rmax = m["R_tg"](m["s_stop"] + 1e-6)
                lowered = (m["s_stop"] + d / 2 + 0.25 * FT) - s
            x_off = Rmax + d / 2 + gap
            mesh = self.yard_mesh(name, length, d, x_off, (on in ("lower", "topmast"), on), name in booms)
            pname = "Yard_" + "".join(w.capitalize() for w in name.replace("_yard", "").split("_"))
            o = O + s * u
            Rm = np.stack([f, Y, u], 1)
            self.parts_[pname] = {"mesh": mesh, "frame": (o, Rm)}
            parent = {"lower": "Mast_", "topmast": "Topmast_"}.get(on, "Topgallant_") + Yd["mast"].capitalize()
            self.meta[pname] = {"turns_about": f"{Yd['mast']} {('lower mast' if on == 'lower' else on)} axis",
                                "parent": parent, "port_tack_sign": 1,
                                "origin_m": np.round(o, 4).tolist(), "axis": np.round(u, 5).tolist(),
                                "hoist_m": [round(float(lowered), 3), 0.0] if lowered else [0.0, 0.0],
                                "brace_deg": [-35.0, 35.0], "length_ft": Yd["length_ft"],
                                "diam_in": round(d / IN, 1), "z_ft": round(float(o[2] / FT), 2)}

    # ---- spanker boom and gaff ---------------------------------------------------------------------------------------
    def spanker(self):
        m = self.masts["mizzen"]
        sp = self.sp["spanker"]
        u, f, O = m["u"], m["f"], m["O"]
        rake = math.radians(self.sp["masts"]["mizzen"]["rake_deg"])
        for which in ("boom", "gaff"):
            g = sp[which]
            if which == "boom":
                x_m = float(m["O"][0]) / FT
                rail_top = self.rail_ft(x_m) + self.rail_cap_ft
                s = (rail_top + g["jaws_over_rail_ft"] - m["deck_ft"]) * FT / float(u[2])
                ang = math.radians(g["rise_deg"])
            else:
                s = m["s_plat"] - g["jaws_below_top_ft"] * FT / float(u[2])
                ang = math.radians(g["peak_deg"])
            R = m["R_lower"](s)
            d = g["diam_in"] * IN
            length = g["length_ft"] * FT
            M = Mesh()
            # local frame: X forward (f), Y starboard, Z up the mast; the spar runs aft and up from the jaws. Its rise is
            # over the horizon, so in the raked frame it is the rise plus the mast's rake
            a = ang + rake
            ub = np.array([-math.cos(a), 0.0, math.sin(a)])
            bt = taper(self.sp["taper"]["boom"])
            r_heel = d / 2 * float(bt(0.0))
            o0 = np.array([-(R + 0.12 * FT + r_heel * math.sin(a)), 0.0, 0.0])     # its heel's upper edge clears the mast
            ss = np.linspace(0, length, 11)
            spar(M, o0, ub, np.array([0, 0, 1.0]) - (np.array([0, 0, 1.0]) @ ub) * ub,
                 [(s_, d / 2 * float(bt(s_ / length))) for s_ in ss], self.mat_wood, self.nseg(d))
            # the jaws: a horn each side, bolted to the spar's heel and spreading round the mast
            jt, jh = 0.32 * d, 0.85 * d
            x_a, x_d = o0[0] - 0.7 * d, 0.45 * R
            zc = lambda x: (o0 + (x - o0[0]) / ub[0] * ub)[2] if x < o0[0] else 0.0     # on the spar's axis aft of the throat
            for sgn in (1, -1):
                rings = []
                for x in np.concatenate([np.linspace(x_a, o0[0], 3), np.linspace(o0[0], x_d, 25)[1:]]):
                    y_in = max(r_heel * 0.92, math.sqrt(max(R * R - x * x, 0.0)) + 0.45 * IN)
                    y0, y1 = sgn * y_in, sgn * (y_in + jt)
                    P2 = rect(min(y0, y1), max(y0, y1), -jh / 2, jh / 2)
                    rings.append(frame_ring(np.array([x, 0.0, zc(x)]), Y, np.array([0, 0, 1.0]), P2))
                loft_solid(M, rings, self.mat_black)
            pname = "Spanker" + which.capitalize()
            o = O + s * u
            self.parts_[pname] = {"mesh": M, "frame": (o, np.stack([f, Y, u], 1))}
            self.meta[pname] = {"turns_about": "mizzen lower mast axis", "parent": "Mast_Mizzen", "port_tack_sign": -1,
                                "origin_m": np.round(o, 4).tolist(),
                                "axis": np.round(u, 5).tolist(), "hoist_m": [0.0, 0.0], "brace_deg": [-40.0, 40.0],
                                "length_ft": g["length_ft"], "diam_in": g["diam_in"], "z_ft": round(float(o[2] / FT), 2)}

    # ---- bowsprit ------------------------------------------------------------------------------------------------------
    def bowsprit(self):
        bs = self.sp["bowsprit"]
        th = math.radians(bs["steeve_deg"])
        ub = np.array([math.cos(th), 0.0, math.sin(th)])          # out along the bowsprit
        up = np.array([-math.sin(th), 0.0, math.cos(th)])         # square to it, upward
        D = bs["diam_in"] * IN
        Lb = bs["length_ft"] * FT
        # its heel stands on the forecastle (spar) deck, where the cap at its end lands on the 1817 draught's cap (the
        # 1849 spar deck plan has the heel 10 ft inside the stem, on a later bowsprit); it passes out over the stem head,
        # which is cut down to bed it (stem_bed: the knightheads beside it are slice 9's)
        P = np.array(loft.backbone_outline(self.L))
        top = self.L.fwd_branch[-1][1]
        x_stem = (float(P[np.abs(P[:, 1] - top) < 1e-6][:, 0].max()) - self.L.mid_px) / self.L.ppf     # ft
        z_stem = top / self.L.ppf_y
        reg = self.sp["registration"]
        cx = bs["cap_draught_px"][0]
        x_cap = ((cx - reg["x_offset"]) / reg["x_scale"] - self.L.mid_px) / self.L.ppf               # ft
        xh = x_cap - Lb / FT * math.cos(th)
        r_heel = 0.9 * D / 2
        zh_ft = self.spar_deck_ft(xh + r_heel / FT * math.sin(th)) + (r_heel * math.cos(th) - 0.3 * IN) / FT
        zh = zh_ft * FT
        H = np.array([xh * FT, 0.0, zh])                            # the heel's axis point
        s_bed = (x_stem * FT - H[0]) / ub[0]                        # where it crosses the stem's fore face
        # the bowsprit's underside, as z (ft) at x (ft): the stem head is cut down to it, less a hair
        z0_bed = zh_ft - (D / 2 / math.cos(th) + 0.1 * IN) / FT
        self.stem_bed = {"x_ft": xh, "z_ft": z0_bed, "slope": math.tan(th)}
        bt = taper(self.sp["taper"]["bowsprit"])

        def R_bs(s):
            if s <= s_bed:
                return D / 2 * (0.9 + 0.1 * s / s_bed)
            return D / 2 * float(bt(min(1.0, (s - s_bed) / (Lb - s_bed))))
        M = self.part("Bowsprit")
        n = self.nseg(D)
        ss = [0.0] + list(np.linspace(0.02 * Lb, s_bed, 4)) + list(np.linspace(s_bed, Lb, 10)[1:])
        spar(M, H, ub, up, [(s, R_bs(s)) for s in ss], self.mat_wood, n)
        hp = self.fit["hoops"]
        for s in np.arange(s_bed + 2.5 * FT, Lb - 7 * FT, 4.5 * FT):
            ring_band(M, H, ub, up, s, R_bs(s), hp["broad_in"] * IN, hp["thick_in"] * IN, self.mat_iron, n)
        # bees: a board each side near the end, standing out past the bowsprit
        Re = R_bs(Lb - 0.8)
        for sgn in (1, -1):
            c = H + (Lb - 5.5 * FT) * ub + sgn * (Re * 0.75 + 0.15) * Y
            box(M, c, ub, Y, up, 2.5 * FT, 0.15, 0.06, self.mat_black)
        # the cap: square to the bowsprit, a hole for it below and for the jibboom above
        jb = bs["jibboom"]
        Dj = jb["diam_in"] * IN
        Rend = R_bs(Lb)
        c_lo, c_hi = -Rend - 0.18 * Dj - 2 * IN, Rend + Dj + 0.35 * Dj
        cap_t = 0.9 * Dj
        Mc = self.part("BowspritCap")
        c = H + (Lb + cap_t / 2 - 0.02) * ub + (c_lo + c_hi) / 2 * up
        box(Mc, c, ub, Y, up, cap_t / 2, Rend + 0.3 * Dj, (c_hi - c_lo) / 2, self.mat_black)
        # jibboom: lies along the bowsprit's back, through the cap
        s_out = jb["out_ft"] * FT
        Lj = jb["length_ft"] * FT
        p_end = H + Lb * ub + (Rend + Dj / 2 + 0.5 * IN) * up
        s_heel = Lb - (Lj - s_out)
        p_heel = H + s_heel * ub + (R_bs(s_heel) + Dj / 2 + 0.5 * IN) * up
        uj = unit(p_end - p_heel)
        p0 = p_end - (Lj - s_out) * uj
        upj = unit(np.cross(uj, Y))                                # square to it, upward
        Mj = self.part("Jibboom")
        jt = taper([1.0, 1.0, 0.92, 0.8, 0.62])
        spar(Mj, p0, uj, upj, [(s, Dj / 2 * float(jt(s / Lj))) for s in np.linspace(0, Lj, 9)], self.mat_wood,
             self.nseg(Dj))
        ring_band(Mj, p0, uj, upj, Lj - 0.6 * FT, Dj / 2 * 0.62, 4 * IN, 0.8 * IN, self.mat_iron, self.nseg(Dj))
        # flying jibboom: alongside the jibboom to starboard, through the iron at its end
        fj = bs["flying_jibboom"]
        Df, Lf = fj["diam_in"] * IN, fj["length_ft"] * FT
        side = unit(0.5 * upj + Y)
        # it is laid straight from its heel (lashed to the jibboom) through the iron at the jibboom's end, clear of
        # the jibboom all along
        s_fh = Lj + fj["out_ft"] * FT - Lf                          # its heel, along the jibboom
        Rj = lambda s_: Dj / 2 * float(jt(min(1.0, s_ / Lj)))
        s_ir = Lj - 0.6 * FT                                        # the iron at the jibboom's end
        h0, h1 = clear_line(Rj, s_fh, s_ir, Df / 2, 0.2 * IN)
        q0 = p0 + s_fh * uj + h0 * side
        q_end = p0 + s_ir * uj + h1 * side
        uf = unit(q_end - q0)
        upf = unit(np.cross(uf, Y))
        ft_ = taper([0.9, 1.0, 0.9, 0.75, 0.55])
        spar(Mj, q0, uf, upf, [(s, Df / 2 * float(ft_(s / Lf))) for s in np.linspace(0, Lf, 9)], self.mat_wood,
             self.nseg(Df))
        # the iron at the jibboom's end: its ring round the flying jibboom and the neck between
        s_i = float((q_end - q0) @ uf)
        ring_band(Mj, q0, uf, upf, s_i, Df / 2 * float(ft_(s_i / Lf)), 4 * IN, 0.8 * IN, self.mat_iron, self.nseg(Df))
        nl0, nl1 = Rj(s_ir) + 0.8 * IN, h1 - Df / 2
        if nl1 > nl0:
            box(Mj, p0 + s_ir * uj + (nl0 + nl1) / 2 * side, side, uj, np.cross(side, uj),
                (nl1 - nl0) / 2 + 0.5 * IN, 2 * IN, 1.0 * IN, self.mat_iron)
        # dolphin striker under the cap, hanging nearly upright
        ds = bs["dolphin_striker"]
        Dd, Ld = ds["diam_in"] * IN, ds["length_ft"] * FT
        ud = unit(np.array([0.12, 0.0, -1.0]))
        tilt = math.acos(float(ud @ -up))                           # to the cap's underside: let its top into the cap
        top = H + (Lb + cap_t / 2) * ub + (c_lo + Dd / 2 * math.tan(tilt) + 0.3 * IN) * up
        spar(Mj, top, ud, np.array([1.0, 0, 0.12]) / np.linalg.norm([1.0, 0, 0.12]),
             [(0.0, Dd / 2), (0.75 * Ld, Dd / 2 * 0.9), (Ld, Dd / 2 * 0.7)], self.mat_black, self.nseg(Dd))
        # spritsail yard: slung under the bowsprit, turning about the bowsprit's square-up line
        sy = bs["spritsail_yard"]
        s_sy = sy["at"] * Lb
        d = self.sp["yards"]["diam_in_per_yard"] * sy["length_ft"] / 3.0 * IN
        o = H + s_sy * ub
        x_off = R_bs(s_sy) + d / 2 + 6 * IN
        mesh = self.yard_mesh("spritsail_yard", sy["length_ft"] * FT, d, 0.0, (False, "lower"), False)
        # its local frame: X out along the bowsprit, Y starboard, Z square-up; the yard hangs below (local Z -x_off)
        V, F, Mm = mesh.arrays()
        Mv = Mesh()
        Mv.add(V + np.array([0.0, 0.0, -x_off]), F, "")
        Mv.M = Mm
        self.parts_["Yard_Spritsail"] = {"mesh": Mv, "frame": (o, np.stack([ub, Y, up], 1))}
        self.meta["Yard_Spritsail"] = {"turns_about": "the bowsprit's square-up line", "parent": "Bowsprit",
                                       "port_tack_sign": 1, "origin_m": np.round(o, 4).tolist(),
                                       "axis": np.round(up, 5).tolist(), "hoist_m": [0.0, 0.0], "brace_deg": [-25.0, 25.0],
                                       "length_ft": sy["length_ft"], "diam_in": round(d / IN, 1),
                                       "z_ft": round(float((o - x_off * up)[2] / FT), 2)}
        self.bs = dict(H=H, ub=ub, up=up, Lb=Lb, D=D, R=R_bs, s_bed=s_bed, cap=H + Lb * ub, jib_end=p0 + Lj * uj,
                       fjb_end=q0 + Lf * uf, heel_z_ft=zh / FT, x_stem=x_stem, z_stem=z_stem,
                       # for the standing rigging (slice 4)
                       cap_t=cap_t, c_lo=c_lo, c_hi=c_hi, bee_s=Lb - 5.5 * FT, bee_y=Re * 0.75 + 0.15,
                       jib=(p0, uj, upj, Lj, Rj), fjb=(q0, uf, upf, Lf, lambda s_: Df / 2 * float(ft_(min(1.0, s_ / Lf)))),
                       ds_top=top, ds_dir=ud, ds_len=Ld, ds_d=Dd, sy_s=s_sy)

    # ---- all of it -----------------------------------------------------------------------------------------------------
    def build(self):
        for name in ("fore", "main", "mizzen"):
            self.mast(name)
        self.yards()
        self.spanker()
        self.bowsprit()
        return self

    def parts(self):
        """name -> (V, F, M, frame) with frame None (built in place) or (origin, R): the mesh is in the part's own
        frame (columns of R are its axes in the ship), placed at origin."""
        out = {}
        for name, p in self.parts_.items():
            V, F, M = p["mesh"].arrays()
            out[name] = (V, F, M, p["frame"])
        return out

    def summary(self):
        """Heights (ft above A) of the main points of each mast, for the docs and the check."""
        res = {}
        for name, m in self.masts.items():
            def z(o, s):
                return round(float((o + s * m["u"])[2] / FT), 2)
            res[name] = {"step": z(m["O"], m["s_step"]), "spar_deck": round(m["deck_ft"], 2),
                         "hounds": z(m["O"], m["s_h"]), "top": z(m["O"], m["s_plat"]), "lower_cap": z(m["O"], m["s_cap1"]),
                         "topmast_hounds": z(m["Otm"], m["s_tmh"]), "topmast_crosstrees": z(m["Otm"], m["s_tmct1"]), "topmast_cap": z(m["Otm"], m["s_tmcap1"]),
                         "topgallant_stop": z(m["Otg"], m["s_stop"]), "truck": z(m["Otg"], m["s_pole"])}
        b = self.bs
        res["bowsprit"] = {"heel": np.round(b["H"] / FT, 2).tolist(), "cap": np.round(b["cap"] / FT, 2).tolist(),
                           "jibboom_end": np.round(b["jib_end"] / FT, 2).tolist(),
                           "flying_jibboom_end": np.round(b["fjb_end"] / FT, 2).tolist(),
                           "inboard_of_the_stem_ft": round(float(b["s_bed"] / FT), 2),
                           "stem_bed_at_fore_face": [round(b["x_stem"], 2),
                                                     round(self.stem_bed["z_ft"] + self.stem_bed["slope"] *
                                                           (b["x_stem"] - self.stem_bed["x_ft"]), 2)]}
        res["yards"] = self.meta
        return res
