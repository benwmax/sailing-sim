"""Frigate hull loft (docs/shipkit-1): the moulded hull of the frigate Commonwealth from offsets.json.

    python loft.py [offsets.json] [out.obj]

Plain Python (numpy, scipy): no Blender. build_frigate.py imports it and makes the Blender objects; lines_check.py
measures the built mesh against the drawing, independently of this code.

The drawing's units are kept to the end: x and z in scan pixels of the 1927 lines plan (x forward along the
half-breadth plan, z up from the load waterline A), half-breadths in the same pixels. The scan is 5.3% taller than
wide: lengths are 11.1 px to the foot (across the sheet), half-breadths and heights 11.69 (down it), and the body
plan's half-breadths, read across the sheet, are scaled into down-the-sheet pixels by the registration. The
readings are taken in each view's own frame and mapped into the half-breadth plan's through drawing_1927.json
(Tools/shipkit/scanreg.py): the sheer plan is drawn 8-15 px aft of the half-breadth plan and the body plan is turned
0.85 deg on the scan. The output is metres in Unreal's body frame: X forward, Y starboard, Z up, origin on the
centreline at midships (station 5) on the load waterline.

How the surface is made
-----------------------
The hull is a half-breadth field hb(x, z) over the profile plane, built from the offsets in two directions:

* Below A, each waterline A-F is a faired spline along x through the read rows (0.9 px RMS, 2.7 px at most), ending
  at the keel's half siding on the stem rabbet (the waterline's own end in the half-breadth plan) and on the
  sternpost rabbet (the sheer plan's).
* Above A, each row's faired half-breadth at A is carried up by the body plan's section shape (a ratio to the
  section's own width at A, itself faired across the stations at each height), eased from the half-breadth plan's
  width at A to the body plan's own width at the top of its sections (the two views differ by up to 1.8% at A),
  and each height level is a C2 batten along x between the sternpost (above the wing transom, the stern face) and
  the stem rabbet.

A section at x is then one C2 batten in z through the rabbet, the waterlines and the levels above A, so it is smooth
through A. Aft of the row at x = 611 px the side has a knuckle at the wing transom (z = 66 px): below it the waterlines
close on the sternpost (a round tuck), above it the side runs aft to the stern face at the stern's half-width, and the
wing transom's underside is the flat between the two. At 611 the tuck's top and the counter's foot meet; from there to
x = 702.5 the two pieces blend into one curve through the wing transom's height (smootherstep in x).

The mesh is four patches per side, sharing their edges vertex for vertex:
  bottom   below F: columns at constant x from the rabbet up to F;
  lower    F to the wing transom: rows at constant z, columns vertical in the midbody and fanned at the ends;
  ledge    the wing transom's underside at z = 66 px (the strip between lower's top row and upper's bottom row);
  upper    the wing transom to the sheer: rows follow the sheer, aft end on the stern face;
plus the transom (across the stern face above the wing transom) and the backbone (keel, deadwood, sternpost and stem
as a plate of the keel's siding, its inner edge traced along the side's own boundary so the two meet with no gap,
triangulated because the outline is concave).
"""
import json
import math
import os
import sys

import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator, UnivariateSpline
from scipy.optimize import brentq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from scanreg import ScanRegistration  # noqa: E402
FT = 0.3048
KNUCKLE = 66.0                       # the wing transom, px above A
JOINED = 702.5                       # forward of this row the levels no longer depend on the stern's end points


def _sorted(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    o = np.argsort(xs)
    xs, ys = xs[o], ys[o]
    keep = np.concatenate([[True], np.diff(xs) > 1e-6])
    return xs[keep], ys[keep]


def pchip(xs, ys):
    """Shape-preserving (no overshoot, but only C1: its curvature jumps at the nodes). Used for the profile lines."""
    return PchipInterpolator(*_sorted(xs, ys), extrapolate=True)


def batten(xs, ys, floor=None, start_slope=False):
    """A fair curve through the points, like a draughtsman's batten: a C2 cubic spline (its curvature is continuous,
    so the fairness check sees no corners at the read points). With start_slope the first point's slope is held to the
    shape-preserving one (a section leaving the rabbet), which keeps the spline from dipping under the keel's half
    siding there; it falls back to PCHIP only if it still would."""
    xs, ys = _sorted(xs, ys)
    if len(xs) < 4:
        return PchipInterpolator(xs, ys, extrapolate=True)
    bc = "not-a-knot"
    if start_slope:
        bc = ((1, float(PchipInterpolator(xs, ys)(xs[0], 1))), "not-a-knot")
    cs = CubicSpline(xs, ys, bc_type=bc, extrapolate=True)
    if floor is not None:
        t = np.linspace(xs[0], xs[-1], 400)
        if cs(t).min() < floor - 0.25:
            return PchipInterpolator(xs, ys, extrapolate=True)
    return cs


def faired(xs, ys, tol=0.8, floor=None):
    """A waterline faired through read offsets: a smoothing spline that keeps its two ends exactly (where it meets the
    rabbet) and passes the rows between at about tol px RMS, the way a loftsman lets a batten find its own line
    through slightly uneven readings. Falls back to the interpolating batten if it would dip under the floor."""
    xs, ys = _sorted(xs, ys)
    w = np.ones(len(xs))
    w[0] = w[-1] = 30.0
    sp = UnivariateSpline(xs, ys, w=w, k=3, s=len(xs) * tol * tol)
    if floor is not None and sp(np.linspace(xs[0], xs[-1], 600)).min() < floor - 0.25:
        return batten(xs, ys, floor)
    return sp


def smooth_curve(xs, ys, tol=0.6):
    """A smoothing spline for traced data (reading noise about a pixel): passes within about tol px of the samples."""
    xs, ys = _sorted(xs, ys)
    return UnivariateSpline(xs, ys, k=3, s=len(xs) * tol * tol)


class Lines:
    """The offsets as functions of the drawing's pixels."""

    def __init__(self, path=os.path.join(HERE, "offsets.json")):
        d = json.load(open(path))
        self.d = d
        self.ppf = d["scale"]["px_per_ft"]                                  # lengths (across the scanned sheet)
        self.ppf_y = d["scale"].get("px_per_ft_down", self.ppf)             # half-breadths and heights (down it)
        self.mid_px = d["frame"]["stations_px"]["5"]
        self.k = float(d["keel_half_siding_px"])
        self.wl_z = {k: float(v) for k, v in d["waterlines_z_px"].items()}
        # the sheer and body plan readings are in their own views' frames: map them into the half-breadth plan's
        self.reg = ScanRegistration(os.path.join(os.path.dirname(os.path.abspath(path)), d["registration"]))
        P = {}
        for name, v in d["profile"].items():
            if isinstance(v, dict) and "pts" in v:
                p = np.asarray(v["pts"], float)
                P[name] = np.stack([self.reg.sheer_to_ship_x(p[:, 0], p[:, 1]), p[:, 1]], 1).tolist()
        self.P = P
        r = d["profile"]["rudder_aft_edge_px"]
        self.rudder_aft_edge = [[float(self.reg.sheer_to_ship_x(r["x"], z)), z] for z in (r["z_top"], r["z_bottom"])]
        hb = d["half_breadths_px"]
        # every row is in this plan's pixels; the midship rows' B-D come from the body plan (offsets.json midship_rows)
        self.rows = [dict(r) for r in hb["rows"]]
        self.row_x = np.array([r["x"] for r in self.rows])
        self.row_A_read = np.array([r["A"] for r in self.rows], float)
        # the rabbet's two branches as x(z): aft (sternpost and deadwood) and forward (keel, forefoot, stem). Below A
        # the forward branch is the waterlines' own ends on the stem (the half-breadth plan); the aft one is the sheer
        # plan's sternpost rabbet, which gives the waterlines their aft ends
        aft = sorted(P["stern_rabbet_px"], key=lambda p: p[1])
        keel = P["keel_rabbet_z_px"]
        # the bearding line meets the keel rabbet at a sheer plan x: map it like every other profile reading
        kr = sorted(d["profile"]["keel_rabbet_z_px"]["pts"])
        zj = float(np.interp(hb["keel_join_x_px"], [p[0] for p in kr], [p[1] for p in kr]))
        x0 = float(self.reg.sheer_to_ship_x(hb["keel_join_x_px"], zj))
        self.keel_join = (x0, float(np.interp(x0, [p[0] for p in keel], [p[1] for p in keel])))
        aft[0] = list(self.keel_join)
        self.aft_branch = aft
        ends_fwd = [[float(hb["ends_fwd"][n]), self.wl_z[n]] for n in "ABCDEF"]
        stem = [p for p in P["stem_rabbet_px"] if p[1] > 0.0 or p[1] < self.wl_z["F"]]
        fwd = [list(self.keel_join)] + [p for p in keel if p[0] > x0 + 10] + ends_fwd + stem
        fwd = sorted(fwd, key=lambda p: p[1])
        self.fwd_branch = fwd
        self._x_aft = pchip([p[1] for p in aft], [p[0] for p in aft])
        self._x_fwd = pchip([p[1] for p in fwd], [p[0] for p in fwd])
        # waterlines below A along x, closing on the rabbet at the keel's half siding
        self.wl = {}
        self.wl_ends = {}
        for name in "ABCDEF":
            a, f = float(self._x_aft(self.wl_z[name])), float(hb["ends_fwd"][name])
            pts = [(a, self.k)] + [(r["x"], r[name]) for r in self.rows if a + 1 < r["x"] < f - 1] + [(f, self.k)]
            self.wl[name] = faired(*zip(*pts), floor=self.k)
            self.wl_ends[name] = (a, f)
        self.row_A = self.wl["A"](self.row_x)             # the faired A, carried up by the sections above it
        # the bottom boundary as z(x) between F's two ends (aft deadwood, keel, forefoot)
        bot = [p for p in aft if p[1] <= self.wl_z["F"] + 1e-6] + [p for p in fwd if p[1] <= self.wl_z["F"] + 1e-6]
        bot = sorted({(round(p[0], 3), p[1]) for p in bot})
        self._z_bot = pchip([p[0] for p in bot], [p[1] for p in bot])
        self.sheer = pchip(*zip(*P["sheer_z_px"]))
        sf = sorted(P["stern_face_px"], key=lambda p: p[1])
        self._x_sf = faired([p[1] for p in sf], [p[0] for p in sf], tol=2.0)     # read point by point: fair it
        T = d["topsides"]
        st = T["stern"]
        bp = T["body_plan"]
        sw = np.asarray(st["stern_half_width_px"], float)                         # body plan, left half
        hw, zw = self.reg.body_nominal_to_ship(sw[:, 1], sw[:, 0], left=True)
        self._W = faired(zw, hw, tol=1.0)
        self.round_up = float(st["transom_round_up_px"])
        # body plan sections above A as ratios to their own width at A (extrapolated from their two lowest readings)
        self.st_x, self.st_r, st_q = [], [], []
        for name in sorted(bp["stations"], key=lambda s: bp["stations"][s]["x_px"]):
            s = bp["stations"][name]
            hbz = bp["stations"][s["hb"]]["hb"] if isinstance(s["hb"], str) else s["hb"]
            a = np.asarray(hbz, float)
            h, z = self.reg.body_nominal_to_ship(a[:, 1], a[:, 0], left=int(name) >= 5)
            o = np.argsort(z)
            h, z = h[o], z[o]
            h0 = h[0] - z[0] * (h[1] - h[0]) / (z[1] - z[0])
            self.st_x.append(float(s["x_px"]))
            self.st_r.append(smooth_curve(np.concatenate([[0.0], z]), np.concatenate([[1.0], h / h0]), tol=0.6 / h0))
            st_q.append(h0 / float(self.wl["A"](float(s["x_px"]))))
        # at A the body plan's sections and the half-breadth plan's A (the master there) differ by up to 1.8%. The
        # ratio is eased from the half-breadth plan's width at A to the body plan's own width at the top, so the
        # topsides end on the body plan's lines rather than carrying that gap up (q is the body plan's width at A over
        # the half-breadth plan's). Forward of station 1 the bow's ratios come from the rail line: no easing there
        qw = np.ones(len(st_q) + 1)
        qw[0] = qw[-1] = 10.0
        self._q = UnivariateSpline(self.st_x + [2295.5], st_q + [1.0], w=qw, k=3, s=len(qw) * (0.8 / 220.0) ** 2)
        self.st_q = st_q
        self._rcache = {}
        bow = T["bow"]
        self.r_2295 = pchip(*zip(*bow["row_2295_ratio"]))
        self.hb_2340 = pchip(*zip(*bow["row_2340_hb"]))
        self.build_levels()

    # --- profile ---------------------------------------------------------------------------------------------------
    def x_aft(self, z):
        """Where the side ends aft at height z: the sternpost rabbet up to the wing transom, then the stern face."""
        return float(self._x_aft(min(z, KNUCKLE))) if z <= KNUCKLE else float(self._x_sf(z))

    def x_fwd(self, z):
        return float(self._x_fwd(z))

    def z_bot(self, x):
        return float(self._z_bot(x))

    def rabbet_z(self, x):
        """The lowest point of the side at x: on the bottom line between F's ends, on the post or the stem beyond."""
        Fa, Ff = self.wl_ends["F"]
        if Fa <= x <= Ff:
            return self.z_bot(x)
        if x < Fa:
            return self._root(lambda z: self.x_aft(z) - x, self.keel_join[1], KNUCKLE)
        return self._root(lambda z: self.x_fwd(z) - x, self.wl_z["F"], self.fwd_branch[-1][1])

    def W(self, z):
        return float(self._W(z))

    def sheer_z(self, x):
        return float(self.sheer(x))

    # --- above A ---------------------------------------------------------------------------------------------------
    def ratio(self, x, z):
        """A section's width at height z as a ratio to the half-breadth plan's A: the body plan's shape (its width at z
        over its width at A), eased toward the body plan's own widths going up (see q above)."""
        # 230 px is about the traced sections' tops: after the registration they end at 228.4-228.8 (stations 1-4, carried
        # on 1.6 px) and 234 (stations 5-9, whose top 4 px go unused); either way under 1 px of width
        if z > 230.0:                         # past the tops: carry on with their slope
            return self.ratio(x, 230.0) + (self.ratio(x, 230.0) - self.ratio(x, 225.0)) / 5.0 * (z - 230.0)
        q = float(self._q(min(max(x, self.st_x[0]), 2295.5)))
        t = min(max(z / 230.0, 0.0), 1.0)
        return self._shape(x, z) * (1.0 - (1.0 - q) * t * t * t * (10 - 15 * t + 6 * t * t))

    def _shape(self, x, z):
        """A section's width at height z as a ratio to its own width at A, interpolated in x between the stations."""
        xs = self.st_x
        if x <= xs[0]:
            return float(self.st_r[0](z))
        if x >= 2295.5:
            return float(self.r_2295(z))
        # across the stations at this height the ratio is itself faired in x (about 0.8 px RMS from each station's
        # reading), so the level curves made from it are fair too: a straight-line blend between stations puts a corner
        # in every level at every station, and the body plan's readings carry a pixel of noise
        key = round(z, 6)
        if key not in self._rcache:
            rx = [float(r(z)) for r in self.st_r] + [float(self.r_2295(z))]
            w = np.ones(len(rx))
            w[0] = w[-1] = 10.0
            self._rcache[key] = UnivariateSpline(xs + [2295.5], rx, w=w, k=3, s=len(rx) * (0.8 / 220.0) ** 2)
        return float(self._rcache[key](x))

    def level(self, z, upper):
        """The side's half-breadth along x at height z (z > 0), as a PCHIP; and its x range."""
        if upper:
            xa, ha = float(self._x_sf(z)), self.W(z)
            rows = [(x, a) for x, a in zip(self.row_x, self.row_A) if x >= 600]     # the tuck's rows stay below
        else:
            xa, ha = float(self._x_aft(z)), self.k
            rows = list(zip(self.row_x, self.row_A))
        xf = self.x_fwd(z)
        pts = [(xa, ha)]
        for x, a in rows:
            if xa + 4 < x < xf - 4:
                pts.append((x, a * self.ratio(x, z)))
        if xa + 4 < 2340 < xf - 4:
            pts.append((2340.0, float(self.hb_2340(z))))
        pts.append((xf, self.k))
        return batten(*zip(*pts), floor=self.k), (xa, xf)

    def build_levels(self):
        # level spacing like the waterlines' (34 px): closer levels would follow the body plan's reading noise
        self.lo_z = [25.0, 47.0, KNUCKLE]
        self.hi_z = [KNUCKLE, 100.0, 135.0, 170.0, 205.0, 235.0, 260.0]
        self.lo = [self.level(z, False) for z in self.lo_z]
        self.hi = [self.level(z, True) for z in self.hi_z]
        # the side is one curve through the wing transom's height from where the tuck's top (lower level) and the
        # counter's foot (upper level) meet: aft of that the wing transom's underside is the ledge between them. The two
        # cross about 1 px apart within a few rows of station 9; joining only at JOINED left a 1 px reverse step
        f_lo, f_hi = self.lo[-1][0], self.hi[0][0]
        gap = lambda x: float(f_hi(x) - f_lo(x))
        xs = np.arange(560.0, JOINED, 1.0)
        g = np.array([gap(x) for x in xs])
        cross = np.nonzero((g[:-1] > 0) & (g[1:] <= 0))[0]
        self.joined = self._root(gap, xs[cross[0]], xs[cross[0] + 1]) if len(cross) else JOINED

    # --- the field -------------------------------------------------------------------------------------------------
    def section(self, x, part):
        """hb(z) of the section at x. part: 'lower' (up to the wing transom, closing on the post) or 'upper' (from the
        wing transom up, aft end on the stern face). Forward of `joined` the side is one curve through the wing
        transom's height; the two pieces blend into it over the next rows (to JOINED), weighted by smootherstep in x so
        the waterlines and level cuts stay curvature-continuous there."""
        if x < self.joined:
            return self._section(x, part, False)
        if x >= JOINED:
            return self._section(x, part, True)
        t = (x - self.joined) / (JOINED - self.joined)
        w = t * t * t * (10 - 15 * t + 6 * t * t)
        a, b = self._section(x, part, False), self._section(x, part, True)
        return lambda z: (1 - w) * a(z) + w * b(z)

    def _section(self, x, part, joined):
        nodes = []
        if part == "lower" or joined:
            zb = self.rabbet_z(x)
            nodes.append((zb, self.k))
            for name in "FEDCBA":
                a, f = self.wl_ends[name]
                zk = self.wl_z[name]
                if a < x < f and zk > zb + 1.0:
                    nodes.append((zk, float(self.wl[name](x))))
            for z, (f, (xa, xf)) in zip(self.lo_z, self.lo):
                if z > zb + 1.0 and xa < x < xf and z < KNUCKLE:
                    nodes.append((z, float(f(x))))
        if part == "upper" and not joined and self.hi[-1][1][0] < x < self.hi[0][1][0]:
            # the counter aft of the wing transom's corner: the section starts on the stern face, where it passes x. The
            # node slides into each level's own end as x reaches it, so no node appears or drops out between two x
            zs = self._root(lambda z: float(self._x_sf(z)) - x, KNUCKLE, self.hi_z[-1])
            nodes.append((zs, self.W(zs)))
        if part == "upper" or joined:
            for z, (f, (xa, xf)) in zip(self.hi_z, self.hi):
                if xa < x < xf:
                    nodes.append((z, float(f(x))))
        elif part == "lower":
            # the tuck's top: its own level aft of the join, the counter's foot from there on (they meet at `joined`)
            f, (xa, xf) = self.lo[-1] if x < self.joined else self.hi[0]
            nodes.append((KNUCKLE, float(f(x)) if xa < x < xf else self.k))
        nodes = sorted(nodes)
        if len(nodes) < 2:                    # a sliver at the stem or post: the rabbet only
            nodes.append((nodes[0][0] + 1.0, self.k))
        zs = [nodes[0]]
        for n in nodes[1:]:
            if n[0] > zs[-1][0] + 0.5:
                zs.append(n)
        return batten(*zip(*zs), floor=self.k, start_slope=True)

    @staticmethod
    def _root(f, a, b):
        try:
            return brentq(f, a, b)
        except ValueError:
            print(f"loft: no crossing between {a:.1f} and {b:.1f}; using the nearer end", file=sys.stderr)
            return a if abs(f(a)) < abs(f(b)) else b

    # --- units -----------------------------------------------------------------------------------------------------
    def to_m(self, x, y, z):
        return ((np.asarray(x) - self.mid_px) / self.ppf * FT, np.asarray(y) / self.ppf_y * FT, np.asarray(z) / self.ppf_y * FT)


def cluster(n, a=0.0, b=1.0, ends=0.6):
    """n+1 samples from a to b, closer at both ends (ends = 0: even; 1: cosine)."""
    t = np.linspace(0, 1, n + 1)
    c = 0.5 - 0.5 * np.cos(np.pi * t)
    return a + (b - a) * ((1 - ends) * t + ends * c)


class Hull:
    """Builds the patches as (vertices in px, quads) for the starboard side; mirror for port."""

    def __init__(self, L, nu=720, nv_bottom=28, nv_lower=96, nv_upper=72, ny_transom=48):
        self.L = L
        self.nu, self.nvb, self.nvl, self.nvu, self.nyt = nu, nv_bottom, nv_lower, nv_upper, ny_transom
        Fa, Ff = L.wl_ends["F"]
        self.base = cluster(nu, Fa, Ff, ends=0.5)              # x of the columns along F
        self.mid = (720.0, 2060.0)                              # columns stay vertical between these

    def stretch(self, xa, xf):
        """Maps the base columns onto a row that runs from xa to xf, keeping the midbody columns where they are. The
        shift fades in as the cube of the distance into each end zone, so the columns' spacing and slant change
        smoothly (a straight-line stretch puts a crease in every cut where the end zone starts)."""
        b, (m0, m1) = self.base, self.mid
        b0, b1 = b[0], b[-1]
        out = b.copy()
        lo, hi = b < m0, b > m1
        t = (m0 - b[lo]) / (m0 - b0)
        out[lo] = b[lo] + (xa - b0) * t ** 3
        t = (b[hi] - m1) / (b1 - m1)
        out[hi] = b[hi] + (xf - b1) * t ** 3
        return out

    def bottom(self):
        L = self.L
        zF = L.wl_z["F"]
        V = np.zeros((self.nu + 1, self.nvb + 1, 3))
        for i, x in enumerate(self.base):
            zb = L.z_bot(x) if 0 < i < self.nu else zF
            sec = L.section(x, "lower")
            zs = zb + (zF - zb) * cluster(self.nvb, ends=0.5)
            V[i, :, 0], V[i, :, 2] = x, zs
            V[i, :, 1] = np.maximum(sec(zs), L.k)
            V[i, 0, 1] = L.k
        return V

    def lower(self):
        L = self.L
        zF = L.wl_z["F"]
        zs = zF + (KNUCKLE - zF) * cluster(self.nvl, ends=0.25)
        V = np.zeros((self.nu + 1, self.nvl + 1, 3))
        cache = {}
        for j, z in enumerate(zs):
            xa = float(L._x_aft(z))
            xf = L.x_fwd(z)
            xs = self.stretch(xa, xf)
            for i, x in enumerate(xs):
                if i in (0, self.nu):
                    V[i, j] = (x, L.k, z)
                    continue
                key = round(x, 6)
                if key not in cache:
                    cache[key] = L.section(x, "lower")
                V[i, j] = (x, max(float(cache[key](z)), L.k), z)
        return V

    def upper_rows(self):
        """Each row j runs from the stern face to the stem at fraction v of the way from the wing transom to the sheer."""
        L = self.L
        v = cluster(self.nvu, ends=0.3)
        rows = []
        for vj in v:
            zof = lambda x, vj=vj: KNUCKLE + vj * (L.sheer_z(x) - KNUCKLE)     # bind this row's v now
            xa = L._root(lambda x: float(L._x_sf(zof(x))) - x, 250, 430)
            xf = L._root(lambda x: L.x_fwd(zof(x)) - x, 2300, 2400)
            rows.append((vj, zof, xa, xf))
        return rows

    def upper(self):
        L = self.L
        rows = self.upper_rows()
        V = np.zeros((self.nu + 1, self.nvu + 1, 3))
        cache = {}
        for j, (vj, zof, xa, xf) in enumerate(rows):
            xs = self.stretch(xa, xf)
            for i, x in enumerate(xs):
                z = zof(x)
                if i == 0:
                    y = L.W(z)
                elif i == self.nu:
                    y = L.k
                else:
                    key = round(x, 6)
                    if key not in cache:
                        cache[key] = L.section(x, "upper")
                    y = max(float(cache[key](z)), L.k)
                V[i, j] = (x, y, z)
        return V

    def transom(self, upper, lower=None):
        """Across the stern face, from the wing transom to the sheer: the aft column of `upper`, port to starboard. The
        bottom row follows the ledge's aft edge (from the post's rabbet at the keel's half siding out to the stern face
        at the side), so the transom, the ledge and the backbone close with no gap."""
        L = self.L
        aft = upper[0]                                   # (nvu+1, 3)
        t = cluster(self.nyt, -1.0, 1.0, ends=0.3)
        V = np.zeros((self.nvu + 1, self.nyt + 1, 3))
        for j, (x, w, z) in enumerate(aft):
            ru = L.round_up * min(1.0, (z - KNUCKLE) / 30.0)
            V[j, :, 0] = x - ru * (1 - t ** 2)
            V[j, :, 1] = w * t
            V[j, :, 2] = z
        if lower is not None:
            x_lo, k = lower[0, -1, 0], lower[0, -1, 1]      # the ledge's inboard end: on the rabbet, at the half siding
            x_up, w = aft[0, 0], aft[0, 1]                  # its outboard end: the stern face at the side
            y = np.abs(V[0, :, 1])
            V[0, :, 0] = np.where(y <= k, x_lo, x_lo + (x_up - x_lo) * (y - k) / max(w - k, 1e-9))
        return V

    def build(self):
        self.B, self.Lo, self.Up = self.bottom(), self.lower(), self.upper()
        self.T = self.transom(self.Up, self.Lo)
        return self


def grid_quads(nI, nJ, flip=False, offset=0):
    """Quads of an (nI+1) x (nJ+1) grid in row-major order (index i*(nJ+1)+j)."""
    q = []
    for i in range(nI):
        for j in range(nJ):
            a = offset + i * (nJ + 1) + j
            b = offset + (i + 1) * (nJ + 1) + j
            quad = (a, b, b + 1, a + 1)
            q.append(quad[::-1] if flip else quad)
    return q


def backbone_outline(L):
    """Keel, deadwood, sternpost and stem in profile (x, z px), counter-clockwise: the outer face, then back along the
    rabbet where the planking lands."""
    P = L.P
    post = sorted(P["sternpost_aft_face_px"], key=lambda p: -p[1])        # top down
    keel = P["keel_bottom_z_px"]
    stem = P["stem_outer_px"]
    stem_lo = [p for p in stem if p[1] <= 32]
    top = L.fwd_branch[-1][1]
    # above 32 px the drawing's fore line is the knee of the head (slice 9): the stem itself keeps its width at A
    # (the band between the rabbet and the fore face, 40 px) up to its head
    band = float(np.interp(0.0, [p[1] for p in stem], [p[0] for p in stem])) - float(L.x_fwd(0.0))
    stem_hi = [[float(L.x_fwd(z)) + band, z] for z in (66.0, 100.0, 160.0, top)]
    outer = post + [p for p in keel if p[0] > post[-1][0]] + stem_lo[1:] + stem_hi
    # the inner edge is where the hull's side ends, traced the way the hull traces it (so the two meet with no gap): the
    # stem rabbet as x(z) down to waterline F, the bottom line as z(x) between F's two ends, the sternpost rabbet as
    # x(z) up to the wing transom
    zF = L.wl_z["F"]
    Fa, Ff = L.wl_ends["F"]
    rab = [[float(L.x_fwd(z)), float(z)] for z in np.linspace(top, zF, 60)]
    bot = [[float(x), float(L.z_bot(x))] for x in np.linspace(Ff, Fa, 240)[1:-1]]
    aftr = [[float(L._x_aft(z)), float(z)] for z in np.linspace(zF, KNUCKLE, 40)]
    inner = rab + bot + aftr
    return outer + inner


def ear_clip(poly):
    """Triangles (index triples, counter-clockwise) of a simple polygon given counter-clockwise, by ear clipping."""
    P = np.asarray(poly, float)
    idx = list(range(len(P)))
    out = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    while len(idx) > 3:
        m = len(idx)
        best = None
        for j in range(m):
            i0, i1, i2 = idx[j - 1], idx[j], idx[(j + 1) % m]
            a, b, c = P[i0], P[i1], P[i2]
            area = cross(a, b, c)
            if area <= 1e-9:
                continue                                   # reflex or flat: not an ear
            Q = P[[q for q in idx if q not in (i0, i1, i2)]]
            inside = ((cross(a, b, Q.T) >= 0) & (cross(b, c, Q.T) >= 0) & (cross(c, a, Q.T) >= 0)).any()
            if not inside:
                # of the ears, clip the one with the widest smallest angle: keeps the slivers out of a long thin band
                e = [np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)]
                score = area / max(e) ** 2
                if best is None or score > best[0]:
                    best = (score, j)
        if best is None:
            raise ValueError("ear_clip: no ear (the polygon is not simple)")
        j = best[1]
        out.append((idx[j - 1], idx[j], idx[(j + 1) % m]))
        del idx[j]
    out.append(tuple(idx))
    return out


def mesh(L, H):
    """Starboard and port hull, transom, ledge and backbone as metres: dict name -> (V (n,3), quads or polygons)."""
    def m(P):
        x, y, z = L.to_m(P[..., 0], P[..., 1], P[..., 2])
        return np.stack([x, y, z], -1)

    out = {}
    # the starboard shell: bottom, lower, ledge strip, upper (each an (nu+1) x (n+1) grid of columns)
    parts = []
    for G in (H.B, H.Lo):
        parts.append(G)
    ledge = np.stack([H.Lo[:, -1], H.Up[:, 0]], axis=1)          # (nu+1, 2, 3): lower's top row to upper's bottom row
    parts += [ledge, H.Up]
    V, Q, off = [], [], 0
    for G in parts:
        nI, nJ = G.shape[0] - 1, G.shape[1] - 1
        V.append(G.reshape(-1, 3))
        Q += grid_quads(nI, nJ, flip=True, offset=off)
        off += (nI + 1) * (nJ + 1)
    Vs = m(np.concatenate(V))
    out["Hull_Stbd"] = (Vs, Q)
    Vp = Vs * np.array([1, -1, 1])
    out["Hull_Port"] = (Vp, [q[::-1] for q in Q])
    # transom: rows up the face, columns port to starboard; normal aft
    nJ, nY = H.T.shape[0] - 1, H.T.shape[1] - 1
    out["Transom"] = (m(H.T.reshape(-1, 3)), grid_quads(nJ, nY, flip=False))
    # backbone: the outline triangulated on each side (it is concave: an OBJ reader fans an n-gon from its first vertex,
    # which fills outside the outline), joined round the edge
    ol = np.array(backbone_outline(L))
    k = L.k
    n = len(ol)
    P = np.concatenate([np.stack([ol[:, 0], np.full(n, k), ol[:, 1]], -1), np.stack([ol[:, 0], np.full(n, -k), ol[:, 1]], -1)])
    tri = ear_clip(ol)
    faces = [t[::-1] for t in tri] + [tuple(n + i for i in t) for t in tri]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    out["Backbone"] = (m(P), faces)
    return out


def write_obj(path, parts):
    with open(path, "w") as f:
        f.write("# frigate Commonwealth hull loft (Tools/shipkit/frigate/loft.py); metres, X forward, Y starboard, Z up\n")
        base = 1
        for name, (V, F) in parts.items():
            f.write(f"o {name}\n")
            for v in V:
                f.write(f"v {v[0]:.5f} {v[2]:.5f} {-v[1]:.5f}\n")   # OBJ is Y up: (x, z, -y)
            for q in F:
                f.write("f " + " ".join(str(base + i) for i in q) + "\n")
            base += len(V)


def summary(L, H):
    """Main dimensions of the loft (metres and feet)."""
    allp = np.concatenate([H.B.reshape(-1, 3), H.Lo.reshape(-1, 3), H.Up.reshape(-1, 3)])
    xa, xf = L.wl_ends["A"]
    xs = np.linspace(xa, xf, 2000)
    s = {
        "lwl_ft": round((xf - xa) / L.ppf, 2),
        "moulded_beam_ft": round(2 * allp[:, 1].max() / L.ppf_y, 2),
        "beam_at_A_ft": round(2 * float(L.wl["A"](xs).max()) / L.ppf_y, 2),
        "depth_rabbet_to_A_ft": round(-L.z_bot(L.mid_px) / L.ppf_y, 2),
        "draft_keel_bottom_aft_ft": round(-min(p[1] for p in L.P["keel_bottom_z_px"]) / L.ppf_y, 2),
        "length_on_sheer_ft": round((H.Up[-1, -1, 0] - H.Up[0, -1, 0]) / L.ppf, 2),
    }
    return s


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "offsets.json")
    dst = sys.argv[2] if len(sys.argv) > 2 else "frigate_hull.obj"
    L = Lines(src)
    H = Hull(L).build()
    write_obj(dst, mesh(L, H))
    print(json.dumps(summary(L, H), indent=1))
