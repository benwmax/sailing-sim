"""Frigate skin (docs/shipkit-2): the planked outside of the frigate Commonwealth over the moulded hull of loft.py.

    python skin.py [out.obj]          (plain Python: numpy, scipy; build_frigate.py imports it for the Blender build)

The moulded hull (loft.py) is the frames' outside, the line the drawing gives. This module lays the planking on it:
copper below the main wale, then the wales, the black strakes, the port band, string plank, channel wale, the
plankshear and the bulwark to the rail, each strake its own thickness (specs_1795.json) with a small V at every seam,
and cuts the gun deck and spar deck ports through it. Behind it go the inner faces (the gun deck's side and the
bulwark's inside, as placeholders for the deck slices), the port linings between them, the rail cap, the plankshear
moulding, the channels, the entry steps, the port lids with their hinges, and the rudder with its irons.

How the skin is laid out
------------------------
Everything is in the drawing's pixels until the end, like loft.py: x forward along the half-breadth plan, z up from
waterline A. The side is described by rows, each a curve z(x) along the ship:

  bottom   from the keel's rabbet up to waterline F, between F's two ends (the rows close on those ends);
  copper   from F up to the main wale's bottom, ending on the sternpost and the stem;
  topside  the strakes' edges and seams, which follow the gun port sill line (the sheer plus a fitted offset) the way
           the planks do, from the wales to the rail.

A row is cut by the ship's ends where it meets them (the rabbets, the stern face) and by the bulwark's breaks (the
entry port, the quarterdeck and forecastle ends). Neighbouring rows are joined by a zipper along x: where both have a
vertex at the same x they make a quad, elsewhere triangles, so each row can end where it really ends. Every row has
a vertex at every one of a common set of x columns (finer at the ends of the ship, and through every port edge and
break), so the ports' sides are straight and the seams line up.

Aft of the stern's join the moulded side has a knuckle at the wing transom (z = 66 px): the tuck below, the counter
above and the transom's flat underside between them. The rows are laid twice, once held at or below the knuckle (on
the lower piece) and once held at or above it (on the upper piece); where a row is held on the knuckle its strip has
no area and is dropped. The knuckle's row on each piece is then joined across by the ledge. Forward of the join the
two pieces are one surface and the two copies weld into one.

A vertex is the moulded point moved out along the moulded surface's normal by the planking's thickness there, which is
a field over (x, z): the strake that holds the point, less the seam's V near its edges. Where two strakes of different
thickness meet, the boundary has two rows (one on each side) and a riser between them. Toward the stem, the sternpost
and the stern face the extra thickness of the wales and thick strakes eases to the bottom planking's 4 in over the
last 2 ft; there the planking lands in the stem and post (the backbone is widened by the bottom's thickness, so the
edge is buried in it).
"""
import json
import math
import os
import sys

import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.optimize import brentq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
from loft import FT, JOINED, KNUCKLE  # noqa: E402

IN = 0.0254                     # metres per inch
TAPER_PX = 24.0                 # the wales ease to the bottom's thickness over this length at the ends (about 2 ft)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------------------------------------------------------------
# the lines along the side
# ---------------------------------------------------------------------------------------------------------------------
class Profile:
    """The side's lines as functions of the ship's x (px): the sheer, the gun port sill line, the wales, the plankshear,
    the rail, and the ports, breaks and channels, all mapped from the sheer plan into the ship's frame."""

    def __init__(self, L, specs):
        self.L = L
        self.sp = specs
        sk = L.d["skin"]
        reg = L.reg
        self.pxin = L.ppf_y / 12.0                      # px per inch, heights and half-breadths
        ship = lambda xs, z: float(reg.sheer_to_ship_x(xs, z))
        # gun ports: [x aft, x fore, z sill, z head]
        raw = [list(p) for p in sk["gun_ports"]["ports"]] + [list(sk["gun_ports"]["bridle"])]
        self.gun = [(ship(a, 0.5 * (s + h)), ship(f, 0.5 * (s + h)), s, h) for a, f, s, h in raw]
        xc = np.array([0.5 * (a + f) for a, f, _, _ in self.gun])
        sill = np.array([s - L.sheer_z(x) for x, (_, _, s, _) in zip(xc, self.gun)])
        high = np.array([h - s for _, _, s, h in self.gun])
        # the sill line under the sheer: fair through the ports' sills (about a pixel of reading noise); the ports'
        # height barely changes along the ship, so it is a straight line through theirs
        self._sill = UnivariateSpline(xc, sill, k=3, s=len(xc) * 0.8 ** 2)
        self._high = np.polyfit(xc, high, 1)
        self.xc0, self.xc1 = float(xc[0]), float(xc[-1])
        self.sill_resid = sill - self._sill(xc)
        self.high_resid = high - np.polyval(self._high, xc)
        # spar deck ports: [x aft, x fore]
        sp = sk["spar_ports"]
        self.spar_over_sill = float(sp["sill_above_gun_sill_px"])
        self.spar = [(ship(a, 200.0), ship(f, 200.0)) for a, f in sp["quarterdeck"] + sp["forecastle"]]
        self.plankshear_over_sill = float(sk["plankshear_px"]["above_gun_sill_px"])
        br = sk["breaks"]
        self.x_e0 = ship(br["entry"][0], 200.0)          # the quarterdeck bulwark ends at the entry's aft post
        self.x_e1 = ship(br["entry"][1], 200.0)
        self.x_fc = ship(br["forecastle_start"], 220.0)
        # the rail line (the bulwark's top) on the quarterdeck and forecastle: a gentle curve through the traced points
        self._r1 = {}
        for part in ("quarterdeck", "forecastle"):
            p = np.array(sk["rail"][part], float)
            xs = np.array([ship(x, z) for x, z in p])
            self._r1[part] = np.polyfit(xs, p[:, 1], 2)
            setattr(self, "rail_resid_" + part[:2], p[:, 1] - np.polyval(self._r1[part], xs))
        # the channels as traced, less any part over the open waist (the 1927 plan runs the fore channel about 6 ft aft
        # of the forecastle into what was then a solid waist; on the 1817 draught it starts at the forecastle's break)
        self.channels = {}
        for name, v in sk["channels"].items():
            if name != "note":
                a, f, za, zf = v
                xa, xf = ship(a, za), ship(f, zf)
                lerp = lambda x: za + (zf - za) * (x - xa) / (xf - xa)
                if self.x_e0 < xa < self.x_fc:
                    xa, za = self.x_fc, lerp(self.x_fc)
                if self.x_e0 < xf < self.x_fc:
                    xf, zf = self.x_e0, lerp(self.x_e0)
                self.channels[name] = (xa, xf, za, zf)
        ri = sk["rudder_irons"]
        self.rudder_straps = [(z, ship(xe, ze), ze) for z, xe, ze in ri["straps"]]
        self.rudder_band = (ri["pendant_band"][0], ship(ri["pendant_band"][1], ri["pendant_band"][0]))
        self.rudder_bottom = float(ri["rudder_bottom_z"])
        r = L.d["profile"]["rudder_aft_edge_px"]
        self.rudder_aft = lambda z: float(reg.sheer_to_ship_x(r["x"], z))
        es = sk["entry_steps"]
        self.steps = (ship(es["x"][0], 80.0), ship(es["x"][1], 80.0), es["z_top"], es["z_bottom"], es["count"])

    def channel_top(self, name, x):
        """A channel's top along x: the spar port sill line moved to the traced heights at the channel's ends, but
        never above the sills (a channel passes under the ports)."""
        a, b, za, zf = self.channels[name]
        x = np.asarray(x, float)
        oa = min(0.0, za - float(self.Ssp(np.array([a]))[0]))
        ob = min(0.0, zf - float(self.Ssp(np.array([b]))[0]))
        return self.Ssp(x) + oa + (ob - oa) * (x - a) / (b - a)

    def _clip(self, x):
        return np.clip(x, self.xc0, self.xc1)

    # heights (px above A) along x; every one takes an array
    def H(self, x):
        """The sheer: the waist's top and the spar ports' heads."""
        return self.L.sheer(x)

    def S(self, x):
        """The gun port sill line."""
        return self.L.sheer(x) + self._sill(self._clip(x))

    def Shd(self, x):
        """The gun port head line."""
        return self.S(x) + np.polyval(self._high, self._clip(x))

    def P(self, x):
        """The spar deck's plankshear."""
        return self.S(x) + self.plankshear_over_sill

    def Ssp(self, x):
        """The spar port sill line."""
        return self.S(x) + self.spar_over_sill

    def Wt(self, x):
        return self.S(x) - self.sp["heights"]["lower_sill_to_top_of_main_wale_in"] * self.pxin

    def Wb(self, x):
        """The main wale's bottom: the copper's top."""
        return self.Wt(x) - self.sp["heights"]["main_wale_depth_in"] * self.pxin

    def M(self, x):
        """String plank to channel wale."""
        return 0.5 * (self.Shd(x) + self.P(x))

    def G(self, x):
        """The gun deck (its planking's top)."""
        return self.S(x) - self.sp["inside"]["gun_deck_below_port_sill_in"] * self.pxin

    def R1(self, x):
        """The rail line on the quarterdeck and forecastle; in the waist the sheer (no bulwark above it there)."""
        x = np.asarray(x, float)
        qd = np.polyval(self._r1["quarterdeck"], x)
        fc = np.polyval(self._r1["forecastle"], x)
        return np.where(x <= self.x_e0 + 1e-9, qd, np.where(x >= self.x_fc - 1e-9, fc, self.H(x)))


# ---------------------------------------------------------------------------------------------------------------------
# the moulded surface
# ---------------------------------------------------------------------------------------------------------------------
class Mould:
    """The moulded hull as hb(x, z) on its two pieces (lower: up to the wing transom, closing on the post; upper: from the
    wing transom up, ending aft on the stern face), with points and outward normals in metres. Forward of JOINED the two
    pieces are the same curve. Sections come from loft.Lines.section, one per x (cached)."""

    def __init__(self, L):
        self.L = L
        self.k = L.k
        self._sec = {}
        self._zlo = {}
        self.x_sf66 = float(L._x_sf(KNUCKLE))           # the stern face at the wing transom
        self.x_post66 = float(L._x_aft(KNUCKLE))        # the post's rabbet there
        self.sx = FT / L.ppf
        self.sy = FT / L.ppf_y

    def sec(self, x, up):
        key = (x, bool(up))
        s = self._sec.get(key)
        if s is None:
            s = self._sec[key] = self.L.section(float(x), "upper" if up else "lower")
        return s

    def x_lo(self, z, up):
        """Where the piece ends aft at height z."""
        z = np.asarray(z, float)
        return np.where(up, self.L._x_sf(np.maximum(z, KNUCKLE)), self.L._x_aft(np.minimum(z, KNUCKLE)))

    def x_hi(self, z):
        return self.L._x_fwd(np.asarray(z, float))

    def W(self, z):
        return self.L._W(np.asarray(z, float))

    def z_lo(self, x, up):
        """The piece's lowest height at x."""
        key = (x, bool(up))
        v = self._zlo.get(key)
        if v is None:
            L = self.L
            if not up or x >= JOINED:
                v = L.rabbet_z(x)
            elif x >= self.x_sf66:
                v = KNUCKLE
            else:
                v = L._root(lambda z: float(L._x_sf(z)) - x, KNUCKLE, 300.0)
            self._zlo[key] = v
        return v

    def hb(self, X, Z, U):
        """Half-breadths at param points (arrays; U true on the upper piece)."""
        X, Z, U = np.asarray(X, float), np.asarray(Z, float), np.asarray(U, bool)
        out = np.full(len(X), self.k)
        xl, xh = self.x_lo(Z, U), self.x_hi(Z)
        at_aft = X <= xl + 1e-9
        at_fwd = X >= xh - 1e-9
        out[at_aft & U] = self.W(Z[at_aft & U])
        inner = ~(at_aft | at_fwd)
        idx = np.nonzero(inner)[0]
        if len(idx):
            o = np.lexsort((X[idx], U[idx]))
            idx = idx[o]
            xs, us = X[idx], U[idx]
            cut = np.nonzero((np.diff(xs) != 0) | (np.diff(us) != 0))[0] + 1
            for g in np.split(np.arange(len(idx)), cut):
                ii = idx[g]
                out[ii] = self.sec(float(xs[g[0]]), bool(us[g[0]]))(Z[ii])
        return np.maximum(out, self.k)

    def frame(self, X, Z, U):
        """Moulded points (metres) and unit outward normals at param points."""
        X, Z, U = np.asarray(X, float), np.asarray(Z, float), np.asarray(U, bool)
        n = len(X)
        h = 0.5
        hb0 = self.hb(X, Z, U)
        # along x, inside the piece's ends
        xl, xh = self.x_lo(Z, U), self.x_hi(Z)
        okp, okm = X + h <= xh, X - h >= xl
        hp, hm = np.full(n, np.nan), np.full(n, np.nan)
        hp[okp] = self.hb(X[okp] + h, Z[okp], U[okp])
        hm[okm] = self.hb(X[okm] - h, Z[okm], U[okm])
        hx = np.where(okp & okm, (hp - hm) / (2 * h), np.where(okp, (hp - hb0) / h, np.where(okm, (hb0 - hm) / h, 0.0)))
        # up and down the section, inside the piece (across the wing transom's height where the pieces are one)
        joined = X >= JOINED
        zlo = np.array([self.z_lo(float(x), bool(u)) for x, u in zip(X, U)])
        zhi = np.where(joined | U, 300.0, KNUCKLE)
        zlo = np.where(joined, np.array([self.z_lo(float(x), False) if j else 0.0 for x, j in zip(X, joined)]), zlo)
        okp, okm = Z + h <= zhi, Z - h >= zlo
        hp, hm = np.full(n, np.nan), np.full(n, np.nan)
        up_p = np.where(joined, Z + h > KNUCKLE, U)
        up_m = np.where(joined, Z - h > KNUCKLE, U)
        hp[okp] = self.hb(X[okp], Z[okp] + h, up_p[okp])
        hm[okm] = self.hb(X[okm], Z[okm] - h, up_m[okm])
        hz = np.where(okp & okm, (hp - hm) / (2 * h), np.where(okp, (hp - hb0) / h, np.where(okm, (hb0 - hm) / h, 0.0)))
        # on the knuckle between the loft's join and JOINED (where the pieces blend into one curve) both copies of the
        # knuckle's row take one normal, across both pieces and along the upper one, so they land on the same point and
        # weld (one-sided normals pushed them up to 9 mm apart and folded the ledge between them)
        kn = np.nonzero((X >= self.L.joined) & ~joined & (np.abs(Z - KNUCKLE) < 1e-9))[0]
        if len(kn):
            Xk, Zk = X[kn], Z[kn]
            up, lo = np.ones(len(kn), bool), np.zeros(len(kn), bool)
            hz[kn] = (self.hb(Xk, Zk + h, up) - self.hb(Xk, Zk - h, lo)) / (2 * h)
            hx[kn] = (self.hb(Xk + h, Zk, up) - self.hb(Xk - h, Zk, up)) / (2 * h)
            hb0[kn] = self.hb(Xk, Zk, up)
        P = np.stack([(X - self.L.mid_px) * self.sx, hb0 * self.sy, Z * self.sy], -1)
        N = np.stack([-self.sy * hx, np.full(n, self.sx), -self.sx * hz], -1)
        N /= np.linalg.norm(N, axis=1)[:, None]
        return P, N, hb0


# ---------------------------------------------------------------------------------------------------------------------
# planking: the strakes and the thickness field
# ---------------------------------------------------------------------------------------------------------------------
class Planking:
    """The topside strakes (from the main wale's bottom up) as plank boundaries along x, and the planking's thickness at
    any point of the side."""

    def __init__(self, prof, mould, specs):
        self.pr = prof
        self.m = mould
        st = specs["strakes"]
        g = specs["grooves"]
        pxin = prof.pxin
        self.t0 = float(st["bottom_in"])
        self.cu_top = float(st["thick_stuff_under_wales_in"][0])
        self.cu_band = 4 * 10.0 * pxin                  # the four strakes under the wales, 10 in each
        self.g_in = float(g["depth_in"])
        self.d_px = float(g["half_width_in"]) * pxin
        pr = prof
        # (lower line, upper line, thicknesses (one per plank, bottom up), paint)
        bands = [
            ("wales", pr.Wb, pr.Wt, [st["main_wales"]["thick_in"]] * st["main_wales"]["count"], "HullBlack"),
            ("black", pr.Wt, pr.S, list(st["black_strakes_in"]), "HullBlack"),
            ("portband", pr.S, pr.Shd, [st["port_band"]["thick_in"]] * st["port_band"]["count"], "HullOchre"),
            ("string", pr.Shd, pr.M, [st["string_plank"]["thick_in"]] * st["string_plank"]["count"], "HullBlack"),
            ("chwale", pr.M, pr.P, [st["channel_wale"]["thick_in"]] * st["channel_wale"]["count"], "HullBlack"),
            ("lowbul", pr.P, pr.Ssp, [st["bulwark"]["thick_in"]], "HullBlack"),
            ("sparband", pr.Ssp, pr.H, [st["bulwark"]["thick_in"]] * 4, "HullBlack"),
            ("upbul", pr.H, pr.R1, [st["bulwark"]["thick_in"]] * 2, "HullBlack"),
        ]
        self.bands = bands
        # the planks: boundary functions b_0..b_n (b_i = band lower + (upper - lower) * j / count)
        self.bfun, self.t, self.paint, self.bname = [], [], [], []
        for name, lo, hi, ts, paint in bands:
            n = len(ts)
            for j in range(n):
                self.bfun.append((lo, hi, j / n))
                self.t.append(float(ts[j]))
                self.paint.append(paint)
                self.bname.append(f"{name}{j}")
        self.bfun.append((bands[-1][1], bands[-1][2], 1.0))
        self.t = np.array(self.t)
        self.band_of = []
        for name, lo, hi, ts, paint in bands:
            self.band_of += [name] * len(ts)

    def bounds(self, X):
        """(n points, n planks + 1) plank boundaries at X."""
        X = np.asarray(X, float)
        cache = {}
        cols = []
        for lo, hi, f in self.bfun:
            a = cache.setdefault(id(lo), lo(X))
            b = cache.setdefault(id(hi), hi(X))
            cols.append(a + (b - a) * f)
        return np.stack(cols, -1)

    def boundary(self, i):
        lo, hi, f = self.bfun[i]
        return lambda x: lo(x) + (hi(x) - lo(x)) * f

    def taper(self, X, Z, U):
        m = self.m
        dist = np.minimum(m.x_hi(Z) - X, X - m.x_lo(Z, U))
        return smoothstep(dist / TAPER_PX)

    def plank_at(self, X, Z, side):
        """Plank index at each point (-1: below the wales, in the copper), and the point's distance to that plank's
        nearer edge (px). side breaks ties on a boundary: -1 the plank below, +1 or 0 the one above."""
        B = self.bounds(X)
        eps = 1e-7
        Z = np.asarray(Z, float)[:, None]
        lt = (B < Z - eps).sum(1)
        le = (B <= Z + eps).sum(1)
        on = le > lt
        side = np.asarray(side)
        nb = B.shape[1] - 1
        # on a boundary below the top: the plank above (the first of any zero-width ones, the waist's upper bulwark)
        i = np.where(on, np.where(side < 0, lt - 1, np.minimum(lt, nb - 1)), lt - 1)
        i = np.clip(i, -1, nb - 1)
        ii = np.clip(i, 0, nb - 1)
        r = np.arange(len(ii))
        lo, hi = B[r, ii], B[r, ii + 1]
        dist = np.minimum(Z[:, 0] - lo, hi - Z[:, 0])
        return i, np.maximum(dist, 0.0)

    def thick_in(self, X, Z, U, side, grooves=True):
        """The planking's thickness (in), seams included unless grooves is false."""
        X, Z = np.asarray(X, float), np.asarray(Z, float)
        side = np.asarray(side)
        tap = self.taper(X, Z, U)
        wb = self.pr.Wb(X)
        cop = (Z < wb - 1e-7) | ((np.abs(Z - wb) <= 1e-7) & (side < 0))
        d = np.empty(len(X))
        s = smoothstep((Z - (wb - self.cu_band)) / self.cu_band)
        d[cop] = self.t0 + (self.cu_top - self.t0) * s[cop] * tap[cop]
        if (~cop).any():
            i, dist = self.plank_at(X[~cop], Z[~cop], side[~cop])
            i = np.maximum(i, 0)
            t = self.t[i]
            groove = self.g_in * np.maximum(0.0, 1.0 - dist / self.d_px) if grooves else 0.0
            d[~cop] = self.t0 + (t - self.t0) * tap[~cop] - groove
        return d

    def paint_at(self, X, Z, side):
        X, Z = np.asarray(X, float), np.asarray(Z, float)
        wb = self.pr.Wb(X)
        out = np.array(["Copper"] * len(X), dtype=object)
        top = Z > wb + 1e-7
        if top.any():
            i, _ = self.plank_at(X[top], Z[top], np.asarray(side)[top] if np.ndim(side) else np.zeros(top.sum()))
            out[top] = np.array(self.paint, dtype=object)[np.maximum(i, 0)]
        return out


# ---------------------------------------------------------------------------------------------------------------------
# rows and the zipper
# ---------------------------------------------------------------------------------------------------------------------
OUT, GUN, BUL, MOULD, LIDOUT, LIDIN = range(6)     # what a vertex is: the skin, the two inner faces, the moulded line,
#                                                     the lids' outside and inside


class Row:
    """A curve z(x) along the side. segs: [(aft end, fore end)], each end None (where the row ends by its rule: on the
    ship's ends for the skin) or a cut x. side: which plank a point on a boundary belongs to (-1 below, +1 above, 0 the
    same either way). kind: which surface its vertices are on."""

    def __init__(self, name, z, side=0, segs=((None, None),), zone="T", riser_below=False, kind=OUT, ends=None):
        self.name, self.z, self.side, self.segs, self.zone = name, z, side, list(segs), zone
        self.riser_below = riser_below            # the strip under this row is a riser (a step between thicknesses)
        self.kind = kind
        self.ends = ends                          # ends(zc, up, fwd) -> x; None: the ship's ends

    def zmin(self, xs):
        return float(np.min(self.z(xs)))

    def zmax(self, xs):
        return float(np.max(self.z(xs)))


def zipper(A, B, ax, bx):
    """Faces joining two polylines that run the same way (A's and B's vertex indices, their params). Quads where both
    have a vertex at the same param, triangles elsewhere. Orientation: normal = (B - A) x (direction of travel)."""
    faces = []
    i = j = 0
    na, nb = len(A), len(B)
    while i < na - 1 or j < nb - 1:
        if i < na - 1 and j < nb - 1 and abs(ax[i + 1] - bx[j + 1]) < 1e-9:
            faces.append((A[i], B[j], B[j + 1], A[i + 1]))
            i += 1
            j += 1
        elif j >= nb - 1 or (i < na - 1 and ax[i + 1] < bx[j + 1]):
            faces.append((A[i], B[j], A[i + 1]))
            i += 1
        else:
            faces.append((A[i], B[j], B[j + 1]))
            j += 1
    return faces


class Verts:
    """A table of param points (x, z, piece, side, kind) -> index; positions are filled in bulk."""

    def __init__(self):
        self.key = {}
        self.X, self.Z, self.U, self.S, self.K = [], [], [], [], []

    def add(self, x, z, up, side, kind=OUT):
        k = (float(x), float(z), bool(up), int(side), int(kind))
        i = self.key.get(k)
        if i is None:
            i = self.key[k] = len(self.X)
            self.X.append(k[0])
            self.Z.append(k[1])
            self.U.append(k[2])
            self.S.append(k[3])
            self.K.append(k[4])
        return i

    def arrays(self):
        return (np.array(self.X), np.array(self.Z), np.array(self.U, bool), np.array(self.S, int), np.array(self.K, int))


class Part:
    """A mesh being built: vertices (metres), faces (index tuples) and a material per face."""

    def __init__(self):
        self.V, self.F, self.M = [], [], []

    def add(self, V, F, M):
        base = sum(len(v) for v in self.V)
        V = np.asarray(V, float).reshape(-1, 3)
        self.V.append(V)
        self.F += [tuple(base + i for i in f) for f in F]
        self.M += list(M) if not isinstance(M, str) else [M] * len(F)

    def arrays(self):
        V = np.concatenate(self.V) if self.V else np.zeros((0, 3))
        return V, list(self.F), list(self.M)


def compact(V, F, M, tol=1e-6):
    """Merges coincident vertices, drops faces that lose a corner or have no area, and unused vertices."""
    V = np.asarray(V, float)
    key = np.round(V / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    F2, M2 = [], []
    for f, m in zip(F, M):
        g = [int(inv[i]) for i in f]
        h = []
        for i in g:
            if not h or h[-1] != i:
                h.append(i)
        if len(h) > 1 and h[0] == h[-1]:
            h.pop()
        if len(h) < 3 or len(set(h)) < len(h):
            continue
        P = V[first[h]]
        a = np.zeros(3)
        for k in range(1, len(h) - 1):
            a += np.cross(P[k] - P[0], P[k + 1] - P[0])
        if np.linalg.norm(a) < 1e-12:
            continue
        F2.append(tuple(h))
        M2.append(m)
    # a face laid twice (both copies of a strip on the knuckle) keeps one; two faces back to back on the same corners
    # (where two closed pieces meet, like the backbone's copper and black) are an inner wall and both go
    seen, drop = {}, set()
    for i, f in enumerate(F2):
        k = tuple(sorted(f))
        if k not in seen:
            seen[k] = i
            continue
        j = seen[k]
        g = F2[j]
        r = g.index(f[0])
        same = tuple(g[r:] + g[:r]) == f
        drop.add(i)
        if not same:
            drop.add(j)
    if drop:
        F2 = [f for i, f in enumerate(F2) if i not in drop]
        M2 = [m for i, m in enumerate(M2) if i not in drop]
    used = np.unique([i for f in F2 for i in f]) if F2 else np.zeros(0, int)
    remap = -np.ones(len(first), int)
    remap[used] = np.arange(len(used))
    V2 = V[first[used]]
    F2 = [tuple(int(remap[i]) for i in f) for f in F2]
    return V2, F2, M2


def sweep(sections, mat, closed=True, caps=True):
    """A tube through cross-sections (each an (m, 3) array, the same m, corresponding points in order). Faces are
    turned to face away from each section's centre; the end caps face along the tube's ends."""
    S = np.asarray(sections, float)
    n, m = S.shape[0], S.shape[1]
    V = S.reshape(-1, 3)
    F = []
    mm = m if closed else m - 1
    for i in range(n - 1):
        for j in range(mm):
            a, b = i * m + j, i * m + (j + 1) % m
            F.append((a, b, b + m, a + m))
    # orientation: the first face's normal against the section centre
    c0 = S[0].mean(0)
    f0 = F[0]
    nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
    if np.dot(nrm, V[list(f0)].mean(0) - 0.5 * (c0 + S[1].mean(0))) < 0:
        F = [f[::-1] for f in F]
    if caps and closed:
        axis = S[-1].mean(0) - S[0].mean(0)
        for end, sgn in ((0, -1.0), (n - 1, 1.0)):
            cap = list(range(end * m, end * m + m))
            P = V[cap]
            nrm = np.zeros(3)
            for k in range(1, m - 1):
                nrm += np.cross(P[k] - P[0], P[k + 1] - P[0])
            if np.dot(nrm, axis) * sgn < 0:
                cap = cap[::-1]
            F.append(tuple(cap))
    return V, F, [mat] * len(F)


def box_along(points, up, out, half_h, t_in, t_out, mat, caps=True):
    """A rectangular bar along a polyline: at each point the section spans +-half_h along `up` and from t_in to t_out
    along `out` (unit vectors per point)."""
    P, U, O = (np.asarray(a, float) for a in (points, up, out))
    secs = []
    for p, u, o in zip(P, U, O):
        secs.append([p + o * t_in - u * half_h, p + o * t_out - u * half_h, p + o * t_out + u * half_h,
                     p + o * t_in + u * half_h])
    return sweep(secs, mat, closed=True, caps=caps)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


class Skin:
    """Builds the planking and everything on it. build() then parts() returns name -> (V (n, 3) metres, faces, face
    materials): starboard parts (mirrored for port by the caller) and centreline parts."""

    def __init__(self, L, specs=None):
        self.L = L
        self.sp = specs or json.load(open(os.path.join(HERE, "specs_1795.json")))
        self.pr = Profile(L, self.sp)
        self.m = Mould(L)
        self.pl = Planking(self.pr, self.m, self.sp)
        self.Fa, self.Ff = L.wl_ends["F"]
        self.zF = L.wl_z["F"]
        ins = self.sp["inside"]
        pxin = self.pr.pxin
        self.d_gun = float(ins["gun_deck_wall_in"])
        self.d_bul = float(ins["bulwark_inner_face_in"])
        self.deck_drop = float(ins["spar_deck_below_plankshear_in"]) * pxin
        self.slab = float(ins["deck_slab_in"]) * pxin
        self.lid_t = float(self.sp["port_lids"]["thick_in"])
        self.inset = 0.25 * pxin                 # the lids' gap all round
        # the ship's ends along x (the backbone's outline and the stern face), so root searches along a row bracket the
        # whole ship rather than fixed ranges that a change to offsets.json could step outside
        ol = np.array(loft.backbone_outline(L))
        zsf = np.linspace(KNUCKLE, 300.0, 60)                 # the stern face up past the taffrail
        self.x_stern = min(float(ol[:, 0].min()), float(np.min(L._x_sf(zsf)))) - 2.0
        self.x_bow = float(ol[:, 0].max()) + 2.0          # the stem's fore face: the planking ends in its rabbet

    # --- columns ---------------------------------------------------------------------------------------------------
    def columns(self, anchors):
        """The common x columns: 1.5 px at the ends of the ship, 5 px through the midbody, plus the anchors."""
        def step(x):
            if x < 480 or x > 2300:
                return 1.5
            if x < 760:
                return 1.5 + 3.5 * (x - 480) / 280
            if x > 2060:
                return 1.5 + 3.5 * (2300 - x) / 240
            return 5.0
        xs, x = [], min(255.0, self.x_stern)
        while x < max(2386.0, self.x_bow):
            xs.append(x)
            x += step(x)
        xs = np.array(xs)
        anchors = np.unique(np.asarray(anchors, float))
        keep = np.ones(len(xs), bool)
        for a in anchors:
            keep &= np.abs(xs - a) > 0.35
        return np.unique(np.concatenate([xs[keep], anchors]))

    # --- rows ------------------------------------------------------------------------------------------------------
    def rows(self):
        pr, pl = self.pr, self.pl
        zF, Fa, Ff = self.zF, self.Fa, self.Ff
        L = self.L
        bottom = []
        nv = 8

        def zbot(x):
            x = np.asarray(x, float)
            zb = L._z_bot(np.clip(x, Fa, Ff))
            return np.where((x <= Fa + 1e-9) | (x >= Ff - 1e-9), zF, zb)

        for j in range(nv):
            v = 0.5 - 0.5 * math.cos(math.pi * j / nv)
            bottom.append(Row(f"bot{j}", (lambda x, v=v: zbot(x) + (zF - zbot(x)) * v), 0, [(Fa, Ff)], "bottom"))
        copper = []
        nB = 34
        for j in range(nB + 1):
            u = j / nB
            side = -1 if j == nB else 0
            copper.append(Row(f"cu{j}", (lambda x, u=u: zF + (pr.Wb(x) - zF) * u), side, [(None, None)], "copper"))
        # the topside: each plank boundary, with a flat row a seam's half-width inside each plank
        top = []
        nb = len(pl.t)
        d = pl.d_px
        e0, efc = pr.x_e0, pr.x_fc
        self.segs_full = segs_full = [(None, None)]
        self.segs_qdfc = segs_qdfc = [(None, e0), (efc, None)]
        names = pl.bname
        iP = names.index("lowbul0")          # plank iP sits on the plankshear (boundary iP)
        iH = names.index("upbul0")           # plank iH sits on the sheer

        def segs_plank(j):
            # above the plankshear only the quarterdeck and forecastle are planked: the waist is open there, its rail on
            # stanchions over the gangways (the 1817 draught; the 1927 lines draw the later solid bulwark)
            return segs_full if j < iP else segs_qdfc

        for i in range(nb + 1):
            b = pl.boundary(i)
            if i > 0:
                top.append(Row(f"b{i}-", (lambda x, b=b: b(x) - d), 0, segs_plank(i - 1)))
            if i == 0:
                top.append(Row("b0+", b, +1, segs_full, riser_below=True))
            elif i == nb:
                top.append(Row(f"b{i}", b, -1, segs_plank(i - 1)))
            elif pl.t[i - 1] == pl.t[i]:        # one row: the top of the plank below (the one above may stop sooner)
                top.append(Row(f"b{i}", b, 0, segs_plank(i - 1)))
            else:                               # two rows and a riser between them
                top.append(Row(f"b{i}a", b, -1, segs_plank(i - 1)))
                top.append(Row(f"b{i}b", b, +1, segs_plank(i), riser_below=True))
            if i < nb:
                top.append(Row(f"b{i}+", (lambda x, b=b: b(x) + d), 0, segs_plank(i)))
        self.iP, self.iH, self.nb = iP, iH, nb
        self.iS = names.index("portband0")
        self.iShd = names.index("string0")
        self.iSsp = names.index("sparband0")
        # the inner faces: the gun deck's side (from the deck up to the spar deck's underside) and the bulwark's inside
        # (from the spar deck up), each a fixed distance in from the moulded surface
        Pd = lambda x: pr.P(x) - self.deck_drop
        Pu = lambda x: pr.P(x) - self.deck_drop - self.slab
        ge = self.inner_ends(self.d_gun, 12.0)
        be = self.inner_ends(self.d_bul, 10.0)
        gun = [Row("g_G", pr.G, kind=GUN, ends=ge), Row("g_GS", lambda x: 0.5 * (pr.G(x) + pr.S(x)), kind=GUN, ends=ge),
               Row("g_S", pr.S, kind=GUN, ends=ge), Row("g_Shd", pr.Shd, kind=GUN, ends=ge),
               Row("g_mid", lambda x: 0.5 * (pr.Shd(x) + Pu(x)), kind=GUN, ends=ge), Row("g_Pu", Pu, kind=GUN, ends=ge)]
        bul = [Row("w_Pd", Pd, kind=BUL, ends=be), Row("w_P", pr.P, kind=BUL, ends=be),
               Row("w_Ssp", pr.Ssp, segs=segs_qdfc, kind=BUL, ends=be),
               Row("w_mid", lambda x: 0.5 * (pr.Ssp(x) + pr.H(x)), segs=segs_qdfc, kind=BUL, ends=be),
               Row("w_H", pr.H, segs=segs_qdfc, kind=BUL, ends=be),
               Row("w_HR", lambda x: 0.5 * (pr.H(x) + pr.R1(x)), segs=segs_qdfc, kind=BUL, ends=be),
               Row("w_R1", pr.R1, segs=segs_qdfc, kind=BUL, ends=be)]
        self.Pd, self.Pu = Pd, Pu
        return bottom, copper, top, gun, bul

    def inner_ends(self, d_in, margin):
        """An inner face's ends: aft, a little forward of the stern face (the transom's thickness); forward, where the
        hull has narrowed to the face's depth plus a margin (a bulkhead closes it there)."""
        m = self.m
        target = d_in * self.pr.pxin + margin
        mid = self.L.mid_px

        def ends(zc, up, fwd):
            if not fwd:
                return brentq(lambda x: x - float(m.L._x_sf(zc(np.array([x]))[0])) - 12.0, self.x_stern, mid,
                              xtol=1e-9)
            g = lambda x: float(m.hb(np.array([x]), zc(np.array([x])), np.array([True]))[0]) - target
            return brentq(g, mid, self.x_bow, xtol=1e-7)
        return ends

    # --- ends ------------------------------------------------------------------------------------------------------
    def end_x(self, zc, up, fwd):
        """Where a row (zc: its clamped z(x)) meets the ship's end."""
        m = self.m
        if fwd:
            f = lambda x: float(m.x_hi(zc(np.array([x]))[0])) - x
            a, b = self.L.mid_px, self.x_bow
        else:
            f = lambda x: x - float(m.x_lo(zc(np.array([x]))[0], up))
            a, b = self.x_stern, self.L.mid_px
        x = brentq(f, a, b, xtol=1e-10)
        z = float(zc(np.array([x]))[0])
        if z == KNUCKLE:                        # held on the knuckle: the knuckle's own end (same float for every row)
            x = float(m.x_hi(KNUCKLE)) if fwd else (m.x_sf66 if up else m.x_post66)
        return x

    def crossings(self, rows, lo=380.0):
        """x where each row crosses the wing transom's height (forward of lo: aft of it the rows end on the stern)."""
        xs = np.arange(lo, self.x_bow, 0.25)
        out = []
        for r in rows:
            g = r.z(xs) - KNUCKLE
            for i in np.nonzero(np.sign(g[:-1]) != np.sign(g[1:]))[0]:
                out.append(brentq(lambda x: float(r.z(np.array([x]))[0]) - KNUCKLE, xs[i], xs[i + 1], xtol=1e-11))
        return out

    # --- the param mesh --------------------------------------------------------------------------------------------
    def build(self):
        pr, m = self.pr, self.m
        bottom, copper, top, gun, bul = self.rows()
        anchors = [self.Fa, self.Ff, self.L.joined, JOINED, pr.x_e0, pr.x_e1, pr.x_fc, m.x_sf66, m.x_post66]
        for a, f, _, _ in pr.gun:
            anchors += [a, f]
        for a, f in pr.spar:
            anchors += [a, f]
        xs_probe = np.linspace(300, 2380, 400)                  # where the rows cross the wing transom's height
        self.cross = self.crossings([r for r in top if r.zmin(xs_probe) < KNUCKLE + 1])
        anchors += self.cross
        C = self.columns(anchors)
        self.C = C
        K = Row("knuckle", lambda x: np.full(np.shape(x), KNUCKLE), 0, [(None, None)])
        lower_rows = bottom + copper + [r for r in top if r.zmin(xs_probe) < KNUCKLE] + [K]
        upper_rows = [K] + [r for r in top if r.zmax(xs_probe) > KNUCKLE]
        self.byname = {r.name: r for r in bottom + copper + top + gun + bul + [K]}
        self.V = V = Verts()
        self.groups = {}                # name -> list of (face, material key)
        self.polys = {}

        def poly(row, up, seg):
            """Vertex indices and x of one segment of a row on one piece."""
            clamp = (lambda z: np.minimum(z, KNUCKLE)) if not up else (lambda z: np.maximum(z, KNUCKLE))
            zc = lambda x: clamp(row.z(x))
            a, f = seg
            rule = row.ends or self.end_x
            if row.zone == "bottom":
                xa, xf = a, f
            else:
                xa = a if a is not None else rule(zc, up, False)
                xf = f if f is not None else rule(zc, up, True)
            inner = C[(C > xa + 0.15) & (C < xf - 0.15)]
            xs = np.concatenate([[xa], inner, [xf]])
            raw = row.z(xs)
            zs = np.where(np.abs(raw - KNUCKLE) < 1e-7, KNUCKLE, zc(xs))     # a crossing lands exactly on the knuckle
            held = zs != raw
            idx = [V.add(x, z, up, 0 if h else row.side, row.kind) for x, z, h in zip(xs, zs, held)]
            return idx, xs

        def seg_of(row, up, seg):
            key = (row.name, up, seg)
            if key not in self.polys:
                self.polys[key] = poly(row, up, seg)
            return self.polys[key]

        self.seg_of = seg_of

        def strip(lo, hi, up, inward=False):
            """Zip row lo to row hi on one piece, segment by segment of the upper row."""
            out = []
            for seg in hi.segs:
                bi, bx = seg_of(hi, up, seg)
                for lseg in lo.segs:
                    li, lx = seg_of(lo, up, lseg)
                    if lx[0] > bx[-1] + 1e-6 or lx[-1] < bx[0] - 1e-6:
                        continue
                    sel = np.ones(len(lx), bool)
                    if seg[0] is not None:
                        sel &= lx >= seg[0] - 1e-9
                    if seg[1] is not None:
                        sel &= lx <= seg[1] + 1e-9
                    ai = [i for i, s in zip(li, sel) if s]
                    ax = lx[sel]
                    if len(ai) >= 1 and len(bi) >= 1:
                        out += zipper(bi, ai, bx, ax) if inward else zipper(ai, bi, ax, bx)
            return out

        def add(group, faces, mat):
            self.groups.setdefault(group, []).extend((f, mat) for f in faces)

        for up, rows in ((False, lower_rows), (True, upper_rows)):
            for lo, hi in zip(rows[:-1], rows[1:]):
                riser = hi.riser_below and lo.side == -1
                add("Skin", strip(lo, hi, up), "riser" if riser else "paint")
        ki, kx = seg_of(K, False, (None, None))
        ui, ux = seg_of(K, True, (None, None))
        add("Skin", zipper(ki, ui, kx, ux), "HullBlack")                      # the wing transom's underside
        for rows, group, mat in ((gun, "GunWall", "Interior"), (bul, "BulwarkIn", "HullRed")):
            for lo, hi in zip(rows[:-1], rows[1:]):
                add(group, strip(lo, hi, True, inward=True), mat)
        self.rows_ = (bottom, copper, top, gun, bul, K, upper_rows)
        self.cut_ports()
        self.linings()
        self.closures()
        self.lids()
        return self

    # --- helpers on rows -------------------------------------------------------------------------------------------
    def row_range(self, name, xa, xf, up=True):
        """A row's vertices (indices, x) between xa and xf."""
        row = self.byname[name]
        I, X = [], []
        for seg in row.segs:
            idx, xs = self.seg_of(row, up, seg)
            for i, x in zip(idx, xs):
                if xa - 1e-9 <= x <= xf + 1e-9 and (not X or x > X[-1] + 1e-12):
                    I.append(i)
                    X.append(x)
        return I, np.array(X)

    def vert_at(self, name, x, up=True):
        I, X = self.row_range(name, x, x, up)
        if not I:
            raise KeyError(f"{name} has no vertex at x={x}")
        return I[0]

    def column(self, names, x, up=True):
        """A column of vertices at x through the named rows (bottom up), with their heights."""
        idx = [self.vert_at(n, x, up) for n in names]
        return idx, np.array([self.V.Z[i] for i in idx])

    def outer_names(self, z_lo_name, z_hi_name):
        """The skin's rows from one to another (inclusive), bottom up."""
        names = [r.name for r in self.rows_[2]]
        return names[names.index(z_lo_name):names.index(z_hi_name) + 1]

    # --- ports -----------------------------------------------------------------------------------------------------
    def port_rects(self):
        pr = self.pr
        gun = [(a, f, pr.S, pr.Shd) for a, f, _, _ in pr.gun]
        spar = [(a, f, pr.Ssp, pr.H) for a, f in pr.spar]
        return gun, spar

    def cut_ports(self):
        gun, spar = self.port_rects()
        X, Z = np.array(self.V.X), np.array(self.V.Z)
        for group, rects in (("Skin", gun + spar), ("GunWall", gun), ("BulwarkIn", spar)):
            keep = []
            for f, mat in self.groups.get(group, []):
                xc, zc = X[list(f)].mean(), Z[list(f)].mean()
                inside = False
                for a, b, lo, hi in rects:
                    if a + 1e-6 < xc < b - 1e-6 and lo(xc) - 0.01 < zc < hi(xc) + 0.01:
                        inside = True
                        break
                if not inside:
                    keep.append((f, mat))
            self.groups[group] = keep

    def linings(self):
        """The ports' sides, sill and head: from the skin's edge in to the inner face."""
        out = []
        sS, sH = f"b{self.iS}a", f"b{self.iShd}"
        pS, pH = f"b{self.iSsp}", f"b{self.iH}"
        gun, spar = self.port_rects()
        # the jambs run through every inner row between sill and head (the spar ports' bulwark has a row at mid
        # height: a jamb drawn only from sill to head would leave a slit beside it)
        for rects, o_lo, o_hi, inner in ((gun, sS, sH, ["g_S", "g_Shd"]), (spar, pS, pH, ["w_Ssp", "w_mid", "w_H"])):
            i_lo, i_hi = inner[0], inner[-1]
            names = self.outer_names(o_lo, o_hi)
            for a, b, _, _ in rects:
                A, ax = self.row_range(o_lo, a, b)
                B, bx = self.row_range(i_lo, a, b)
                out += zipper(A, B, ax, bx)                        # sill, facing up
                A, ax = self.row_range(i_hi, a, b)
                B, bx = self.row_range(o_hi, a, b)
                out += zipper(A, B, ax, bx)                        # head, facing down
                for x, aft in ((a, True), (b, False)):
                    oc, oz = self.column(names, x)
                    ic, iz = self.column(inner, x)
                    out += zipper(ic, oc, iz, oz) if aft else zipper(oc, ic, oz, iz)
        self.groups["Linings"] = [(f, "HullRed") for f in out]

    def closures(self):
        """The bulwark's top (skin to inner face), the ends of the bulwark at its breaks, and the planking's ends at the
        stern face."""
        pr = self.pr
        e0, fc = pr.x_e0, pr.x_fc
        top, P = f"b{self.nb}", f"b{self.iP}a"
        faces = []
        for o, i, a, b in ((top, "w_R1", -1e9, e0), (P, "w_P", e0, fc), (top, "w_R1", fc, 1e9)):
            A, ax = self.row_range(o, a, b)
            B, bx = self.row_range(i, a, b)
            faces += zipper(A, B, ax, bx)
        self.groups["BulwarkTop"] = [(f, "HullBlack") for f in faces]
        ends = []
        inner_all = ["w_P", "w_Ssp", "w_mid", "w_H", "w_HR", "w_R1"]
        for x, lo_o, hi_o, inn, facing_fwd in ((e0, P, top, inner_all, True), (fc, P, top, inner_all, False)):
            names = self.outer_names(lo_o, hi_o)
            oc, oz = self.column(names, x)
            ic, iz = self.column(inn, x)
            ends += zipper(ic, oc, iz, oz) if facing_fwd else zipper(oc, ic, oz, iz)
        self.groups["BulwarkEnds"] = [(f, "HullRed") for f in ends]
        # the planking's ends on the stern face, from the skin to the moulded edge (the quarter pieces of slice 9 go
        # over this)
        V = self.V
        oe, me, zs = [], [], []
        for row in self.rows_[6]:
            if row.segs[0][0] is not None:
                continue
            idx, xs = self.seg_of(row, True, row.segs[0])
            i0 = idx[0]
            oe.append(i0)
            zs.append(V.Z[i0])
            me.append(V.add(V.X[i0], V.Z[i0], True, 0, MOULD))
        o = np.argsort(zs)
        zs = np.array(zs)[o]
        oe = [oe[k] for k in o]
        me = [me[k] for k in o]
        self.groups["SternEnds"] = [(f, "HullBlack") for f in zipper(oe, me, zs, zs)]
        # the wing transom's planked underside ends aft on a line from the post to the stern's corner, the planking's
        # thickness under the moulded edge (the Transom's foot): close it up to that edge, facing aft
        K = self.rows_[5]
        a = self.seg_of(K, False, (None, None))[0][0]
        b = self.seg_of(K, True, (None, None))[0][0]
        ma = V.add(V.X[a], V.Z[a], False, 0, MOULD)
        mb = V.add(V.X[b], V.Z[b], True, 0, MOULD)
        q = [a, b, mb, ma]
        P, _ = self.eval_points([V.X[i] for i in q], [V.Z[i] for i in q], [V.U[i] for i in q], [V.S[i] for i in q],
                                [V.K[i] for i in q])
        if np.cross(P[1] - P[0], P[3] - P[0])[0] > 0:
            q = q[::-1]
        self.groups["SternEnds"].append((tuple(q), "HullBlack"))

    def lids(self):
        """Each gun port's lid, closed: the port band's planking over the opening (its seams too) less a quarter inch
        all round, 4 in thick."""
        pr, V, C = self.pr, self.V, self.C
        e = self.inset
        band = self.outer_names(f"b{self.iS}+", f"b{self.iShd}-")
        zfun = [lambda x: pr.S(x) + e] + [self.byname[n].z for n in band] + [lambda x: pr.Shd(x) - e]
        self.lid_groups = []
        for k, (a, b, _, _) in enumerate(pr.gun):
            xs = np.concatenate([[a + e], C[(C > a + e + 0.15) & (C < b - e - 0.15)], [b - e]])
            grid = {}
            for kind in (LIDOUT, LIDIN):
                grid[kind] = [[V.add(x, float(zf(np.array([x]))[0]), True, 0, kind) for x in xs] for zf in zfun]
            faces = []
            go, gi = grid[LIDOUT], grid[LIDIN]
            for r in range(len(zfun) - 1):
                faces += [(f, "HullBlack") for f in zipper(go[r], go[r + 1], xs, xs)]
                faces += [(f, "HullRed") for f in zipper(gi[r + 1], gi[r], xs, xs)]
            red = []
            red += zipper(gi[0], go[0], xs, xs)                    # bottom edge, facing down
            red += zipper(go[-1], gi[-1], xs, xs)                  # top edge, facing up
            zcol = np.arange(len(zfun), dtype=float)
            red += zipper([g[0] for g in go], [g[0] for g in gi], zcol, zcol)        # aft edge
            red += zipper([g[-1] for g in gi], [g[-1] for g in go], zcol, zcol)      # fore edge
            faces += [(f, "HullRed") for f in red]
            name = f"Lid_{k + 1:02d}"
            self.groups[name] = faces
            self.lid_groups.append((name, a + e, b - e, go))

    # --- evaluation ------------------------------------------------------------------------------------------------
    def eval_points(self, X, Z, U, S, kind):
        """Positions and normals of param points (arrays) on a surface kind."""
        X, Z = np.asarray(X, float), np.asarray(Z, float)
        U = np.broadcast_to(np.asarray(U, bool), X.shape)
        S = np.broadcast_to(np.asarray(S, int), X.shape)
        kind = np.broadcast_to(np.asarray(kind, int), X.shape)
        P, N, hb = self.m.frame(X, Z, U)
        d = np.zeros(len(X))
        field = (kind == OUT) | (kind == LIDOUT)
        if field.any():
            d[field] = self.pl.thick_in(X[field], Z[field], U[field], S[field])
        li = kind == LIDIN                      # the lid's inside is smooth: the seams' Vs are on its outside only
        if li.any():
            d[li] = self.pl.thick_in(X[li], Z[li], U[li], S[li], grooves=False) - self.lid_t
        d[kind == GUN] = -self.d_gun
        d[kind == BUL] = -self.d_bul
        return P + N * (d * IN)[:, None], N

    def positions(self):
        X, Z, U, S, K = self.V.arrays()
        self.pos, self.nrm = self.eval_points(X, Z, U, S, K)
        return self.pos

    # --- what sits on the planking (built from the evaluated surfaces) ----------------------------------------------
    def surf(self, X, Z, up=True, side=0, kind=OUT):
        """Points and normals on a surface at param points."""
        X = np.atleast_1d(np.asarray(X, float))
        Z = np.broadcast_to(np.atleast_1d(np.asarray(Z, float)), X.shape).copy()
        return self.eval_points(X, Z, up, side, kind)

    def row_points(self, name, xa=-1e9, xf=1e9):
        I, X = self.row_range(name, xa, xf)
        return self.pos[I], self.nrm[I], X

    def rail_caps(self, part):
        """The rail cap (14 x 4 1/2 in) on the bulwark's top on the quarterdeck and forecastle, from the skin's outside to
        the inner face (the cap overhangs both by an inch); and the waist's rail on its stanchions."""
        pr = self.pr
        top = f"b{self.nb}"
        for a, b in ((-1e9, pr.x_e0), (pr.x_fc, 1e9)):
            I_pos, _, X = self.row_points("w_R1", a, b)
            orow = self.byname[top]
            O_pos, _ = self.surf(X, orow.z(X), True, orow.side, OUT)
            part.add(*sweep(self.cap_sections(O_pos, I_pos), "HullBlack"))
        self.waist_rail(part)

    def cap_sections(self, O_pos, I_pos):
        """The rail cap's sections over pairs of outside and inside points: centred between them, its underside half an
        inch under the higher of the two."""
        rs = self.sp["rail"]
        w, t = 0.5 * rs["broad_in"] * IN, rs["thick_in"] * IN
        secs = []
        for o, i in zip(O_pos, I_pos):
            u = o - i
            u[2] = 0.0
            u /= np.linalg.norm(u)
            mid = 0.5 * (o + i)
            c = np.array([mid[0], mid[1], max(o[2], i[2]) - 0.5 * IN])
            secs.append([c - u * w, c + u * w, c + u * w + [0, 0, t], c - u * w + [0, 0, t]])
        return secs

    def waist_rail(self, part):
        """The waist above the gangways (1797, as the 1817 draught draws it): no bulwark over the plankshear, only the
        rail at the sheer's height on square stanchions about 6 ft apart, from the entry to the forecastle (the hammock
        netting along it is slice 8's)."""
        pr, ws = self.pr, self.sp["waist_rail"]
        xa, xf = pr.x_e1, pr.x_fc
        X = np.concatenate([[xa], self.C[(self.C > xa + 0.15) & (self.C < xf - 0.15)], [xf]])
        O_pos, _ = self.surf(X, pr.H(X), True, 0, OUT)
        I_pos, _ = self.surf(X, pr.H(X), True, 0, BUL)
        part.add(*sweep(self.cap_sections(O_pos, I_pos), "HullBlack"))
        # the stanchions: from the plankshear's top to the rail, leaning in with the side
        half = 0.5 * ws["stanchion_in"] * IN
        n = max(2, int(round((xf - xa) / (ws["stanchion_spacing_ft"] * self.L.ppf))) + 1)
        end = half / self.m.sx + 1.0                       # px: the end posts stand just inside the rail's ends
        for x in np.linspace(xa + end, xf - end, n):
            xs = np.array([x])
            ob, _ = self.surf(xs, pr.P(xs), True, -1, OUT)
            ib, _ = self.surf(xs, pr.P(xs), True, 0, BUL)
            ot, _ = self.surf(xs, pr.H(xs), True, 0, OUT)
            it, _ = self.surf(xs, pr.H(xs), True, 0, BUL)
            b = 0.5 * (ob[0] + ib[0])
            t = 0.5 * (ot[0] + it[0])
            b[2] = max(ob[0][2], ib[0][2]) - 0.5 * IN
            t[2] = max(ot[0][2], it[0][2])
            u = ob[0] - ib[0]
            u[2] = 0.0
            u = unit(u)
            fwd = np.array([1.0, 0.0, 0.0])
            part.add(*box_along([b, t], [fwd, fwd], [u, u], half, -half, half, "HullBlack"))

    def moulding(self, part):
        """The half-round along the plankshear's outer edge."""
        r = self.sp["plankshear_moulding"]["radius_in"] * IN
        P, N, X = self.row_points(f"b{self.iP}a")
        T = np.gradient(P, axis=0)
        secs = []
        for p, n, t in zip(P, N, T):
            up = unit(np.cross(n, t))
            if up[2] < 0:
                up = -up
            c = p - n * 0.5 * IN
            secs.append([c + r * (math.cos(a) * n + math.sin(a) * up) for a in np.linspace(-math.pi / 2, math.pi / 2, 13)])
        part.add(*sweep(secs, "HullBlack"))

    def channels(self, part):
        """The chains' channels: planks standing out from the side at the spar port sills, on the channel wale."""
        pr, ch = self.pr, self.sp["channels"]
        th = ch["thick_in"] * IN
        for name, (a, b, _, _) in pr.channels.items():
            out = ch[f"{name}_out_ft"] * FT
            X = np.concatenate([[a], self.C[(self.C > a + 0.15) & (self.C < b - 0.15)], [b]])
            zt = pr.channel_top(name, X)
            zb = zt - th / IN * pr.pxin
            Ot, Nt = self.surf(X, zt)
            Ob, Nb = self.surf(X, zb)
            secs = []
            for ot, ob, nt, nb in zip(Ot, Ob, Nt, Nb):
                h = 0.5 * (nt + nb)
                h[2] = 0.0
                h = unit(h)
                secs.append([ob - h * IN, ob + h * out, ot + h * out, ot - h * IN])
            part.add(*sweep(secs, "HullBlack"))

    def entry_steps(self, part):
        pr, es = self.pr, self.sp["entry_steps"]
        xa, xf, z0, z1, n = pr.steps
        hh, proud = 0.5 * es["broad_in"] * pr.pxin, es["proud_in"] * IN
        X = np.linspace(xa, xf, 7)
        for z in np.linspace(z0, z1, n):
            Ob, Nb = self.surf(X, z - hh)
            Ot, Nt = self.surf(X, z + hh)
            secs = [[ob - nb * 0.5 * IN, ob + nb * proud, ot + nt * proud, ot - nt * 0.5 * IN]
                    for ob, ot, nb, nt in zip(Ob, Ot, Nb, Nt)]
            part.add(*sweep(secs, "HullBlack"))

    def hinges(self, lid_parts):
        """Iron straps down each lid's outside from its head (specs: port_lids.hinges), with the hinge's knuckle at the
        top. The knuckles' centres are kept for lid_frame: the line through them is the axis the lid turns on."""
        pr = self.pr
        n = int(self.sp["port_lids"]["hinges"])
        self.knuckles = {}
        for name, xa, xf, _ in self.lid_groups:
            part = lid_parts[name]
            w = xf - xa
            self.knuckles[name] = []
            for x in xa + w * np.linspace(0.2, 0.8, n):
                z_top = float(pr.Shd(np.array([x]))[0]) - self.inset
                z_bot = float(pr.S(np.array([x]))[0]) + self.inset
                Z = np.linspace(z_top, z_top - 0.7 * (z_top - z_bot), 8)
                P, N = self.surf(np.full(8, x), Z, True, 0, LIDOUT)
                along = np.array([1.0, 0.0, 0.0])
                U = unit(np.array([along - n * np.dot(along, n) for n in N]))
                part.add(*box_along(P, U, N, 1.25 * IN, -0.1 * IN, 0.45 * IN, "Iron"))
                c = P[0] + N[0] * 0.9 * IN
                self.knuckles[name].append(c)
                ring = [c + 1.0 * IN * (math.cos(a) * N[0] + math.sin(a) * np.array([0, 0, 1.0])) for a in
                        np.linspace(0, 2 * math.pi, 9)[:-1]]
                ring = np.array(ring)
                part.add(*sweep([ring - U[0] * 2 * IN, ring + U[0] * 2 * IN], "Iron"))

    def lid_frame(self, name):
        """A starboard lid's hinge axis (after parts()): origin midway between its hinges' knuckles, X along the axis
        through them (forward), Z out of the side (square to X). Turning the lid about +X opens it outward."""
        for nm, xa, xf, go in self.lid_groups:
            if nm == name:
                ks = self.knuckles[name]
                o = np.mean(ks, axis=0)
                xax = unit(ks[-1] - ks[0])
                nrm = self.nrm[go[-1]].mean(0)
                zax = unit(nrm - xax * np.dot(nrm, xax))
                return o, xax, zax
        raise KeyError(name)

    # --- centreline parts ------------------------------------------------------------------------------------------
    def across(self, P, n=16):
        """A row of points on the starboard side carried straight across to port: (len(P), n + 1, 3)."""
        t = np.linspace(1.0, -1.0, n + 1)
        G = np.repeat(P[:, None, :], n + 1, 1).copy()
        G[:, :, 1] = P[:, None, 1] * t[None, :]
        return G

    @staticmethod
    def grid_faces(G, flip=False):
        nI, nJ = G.shape[0], G.shape[1]
        F = []
        for i in range(nI - 1):
            for j in range(nJ - 1):
                a, b = i * nJ + j, (i + 1) * nJ + j
                f = (a, b, b + 1, a + 1)
                F.append(f[::-1] if flip else f)
        return G.reshape(-1, 3), F

    def facing(self, V, F, want):
        """Turns a patch's faces so their mean normal points along `want`."""
        nrm = np.zeros(3)
        for f in F:
            nrm += np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
        return F if np.dot(nrm, want) >= 0 else [f[::-1] for f in F]

    def bulkheads(self, part):
        """Placeholders closing the inner faces at their ends (the transom's and the bow's inside): flat across."""
        bottom, copper, top, gun, bul, K, upper = self.rows_
        for rows, mat in ((gun, "Interior"), (bul, "HullRed")):
            for end, want in ((0, 1.0), (-1, -1.0)):
                pts = []
                for r in rows:
                    seg = r.segs[end]
                    idx, xs = self.seg_of(r, True, seg)
                    pts.append(self.pos[idx[end]])
                G = np.stack([self.across(np.array([p]))[0] for p in pts])
                V, F = self.grid_faces(G)
                part.add(V, self.facing(V, F, np.array([want, 0, 0])), mat)

    def decks(self, gun_part, spar_part):
        """Placeholder decks (slice 7 builds the real ones): the gun deck, and the spar deck (planking's top and the
        beams' underside) with the waist open between gangways along each side."""
        pr = self.pr
        wg = 6.5 * FT                                      # gangway width
        P, _, X = self.row_points("g_G")
        V, F = self.grid_faces(self.across(P))
        gun_part.add(V, self.facing(V, F, np.array([0, 0, 1.0])), "Deck")
        e0, fc = pr.x_e0, pr.x_fc
        Pt, _, Xt = self.row_points("w_Pd")
        Pb, _, Xb = self.row_points("g_Pu")
        edge = dict(zip(np.round(Xt, 9), Pt[:, 1] - wg))
        for P, X, mat, want in ((Pt, Xt, "Deck", 1.0), (Pb, Xb, "Interior", -1.0)):
            ys = P[:, 1]
            for sel in (X <= e0 + 1e-9, X >= fc - 1e-9):
                Q = P[sel]
                if len(Q) < 2:
                    continue
                G = []
                for p, y in zip(Q, ys[sel]):
                    w = min(wg, 0.4 * y)
                    yy = np.concatenate([[y, y - w / 2], np.linspace(y - w, -(y - w), 9), [-(y - w / 2), -y]])
                    G.append([[p[0], v, p[2]] for v in yy])
                V, F = self.grid_faces(np.array(G))
                spar_part.add(V, self.facing(V, F, np.array([0, 0, want])), mat)
            sel = (X >= e0 - 1e-9) & (X <= fc + 1e-9)
            Q = P[sel]
            for sgn in (1.0, -1.0):
                G = []
                for p, x in zip(Q, X[sel]):
                    yi = edge.get(round(float(x), 9), p[1] - wg)
                    G.append([[p[0], sgn * v, p[2]] for v in np.linspace(p[1], yi, 4)])
                V, F = self.grid_faces(np.array(G))
                spar_part.add(V, self.facing(V, F, np.array([0, 0, want])), mat)
        # the opening's edges: the gangways' inner sides and the breast beams at each end
        ztop = dict(zip(np.round(Xt, 9), Pt[:, 2]))
        zbot = dict(zip(np.round(Xb, 9), Pb[:, 2]))
        xs = [x for x in Xt if e0 - 1e-9 <= x <= fc + 1e-9 and round(float(x), 9) in zbot]
        for sgn in (1.0, -1.0):
            G = [[[ (x - self.L.mid_px) * self.m.sx, sgn * edge[round(float(x), 9)], ztop[round(float(x), 9)]],
                  [(x - self.L.mid_px) * self.m.sx, sgn * edge[round(float(x), 9)], zbot[round(float(x), 9)]]] for x in xs]
            V, F = self.grid_faces(np.array(G))
            spar_part.add(V, self.facing(V, F, np.array([0, -sgn, 0])), "Deck")
        for x, want in ((xs[0], 1.0), (xs[-1], -1.0)):
            k = round(float(x), 9)
            y = edge[k]
            xm = (x - self.L.mid_px) * self.m.sx
            G = np.array([[[xm, v, ztop[k]], [xm, v, zbot[k]]] for v in np.linspace(y, -y, 9)])
            V, F = self.grid_faces(G)
            spar_part.add(V, self.facing(V, F, np.array([want, 0, 0])), "Deck")

    def stern_top(self, part):
        """The transom carried up from the sheer to the rail (the taffrail's face; slice 9 makes the stern), and its top
        across to the stern bulwark's inside."""
        L = self.L
        top = self.byname[f"b{self.nb}"]
        idx, xs = self.seg_of(top, True, top.segs[0])
        z1 = self.V.Z[idx[0]]                                  # the rail's height at the stern face
        z0 = float(brentq(lambda x: x - float(L._x_sf(L.sheer_z(x))), self.x_stern, L.mid_px))
        z0 = L.sheer_z(z0)
        t = loft.cluster(48, -1.0, 1.0, ends=0.3)
        rows = []
        for z in np.linspace(z0, z1, 7):
            x = float(L._x_sf(z))
            w = float(L._W(z))
            rows.append(np.stack(L.to_m(x - L.round_up * (1 - t ** 2), w * t, np.full(len(t), z)), -1))
        G = np.array(rows)
        V, F = self.grid_faces(G)
        part.add(V, self.facing(V, F, np.array([-1.0, 0, 0])), "HullBlack")
        # its top: across to the stern bulwark's inside (the w_R1 row's aft end)
        r = self.byname["w_R1"]
        i, _ = self.seg_of(r, True, r.segs[0])
        p = self.pos[i[0]]
        inner = np.stack([np.full(len(t), p[0]), p[1] * t, np.full(len(t), p[2])], -1)
        G = np.array([G[-1], inner])
        V, F = self.grid_faces(G)
        part.add(V, self.facing(V, F, np.array([0, 0, 1.0])), "HullBlack")

    def backbone(self, part):
        """Keel, deadwood, sternpost and stem as loft.py draws them, sided wider by the bottom planking's thickness each
        side (the planking lands in their rabbets) and the stem carried up to the forecastle's rail; coppered up to the
        main wale's bottom."""
        L, pr = self.L, self.pr
        hw = L.k + self.pl.t0 * pr.pxin
        top = float(pr.R1(np.array([L.x_fwd(250.0)]))[0]) + self.sp["rail"]["thick_in"] * pr.pxin
        ol = np.array(loft.backbone_outline(L, top=top))
        c = lambda p: float(pr.Wb(np.array([p[0]]))[0])
        pieces = [(clip_poly(ol, lambda p: c(p) - p[1]), "Copper"),
                  (clip_poly(ol, lambda p: min(p[1] - c(p), p[0] - 1500.0)), "HullBlack"),
                  (clip_poly(ol, lambda p: min(p[1] - c(p), 1000.0 - p[0])), "HullBlack")]
        for poly, mat in pieces:
            poly = np.array(poly)
            n = len(poly)
            if n < 3:
                continue
            tri = loft.ear_clip(poly)
            Pm = np.concatenate([np.stack([poly[:, 0], np.full(n, hw), poly[:, 1]], -1),
                                 np.stack([poly[:, 0], np.full(n, -hw), poly[:, 1]], -1)])
            V = np.stack(L.to_m(Pm[:, 0], Pm[:, 1], Pm[:, 2]), -1)
            F = [t[::-1] for t in tri] + [tuple(n + i for i in t) for t in tri]
            for i in range(n):
                j = (i + 1) % n
                F.append((i, j, n + j, n + i))
            part.add(V, F, mat)

    def rudder(self, part, irons):
        """The rudder (as thick as the post at its fore edge, thinner aft; coppered to the wale's bottom) hung on the
        sternpost, up into the counter; its bronze straps, the hull's gudgeon arms, the pintles' knuckles and the band
        for the pendants."""
        L, pr, m = self.L, self.pr, self.m
        rs = self.sp["rudder"]
        post = sorted(L.P["sternpost_aft_face_px"], key=lambda p: p[1])
        pz, px = np.array([p[1] for p in post]), np.array([p[0] for p in post])
        slope = (px[-1] - px[-2]) / (pz[-1] - pz[-2])
        x_post = lambda z: float(np.interp(z, pz, px)) if z <= pz[-1] else float(px[-1] + slope * (z - pz[-1]))
        gap = 0.5 * L.ppf / 12.0
        hf = 0.5 * rs["fore_edge_siding_in"] * IN
        ha = 0.5 * rs["aft_edge_siding_in"] * IN
        zb, zt = pr.rudder_bottom, 104.0
        zc = float(pr.Wb(np.array([380.0]))[0])
        zs = np.unique(np.concatenate([np.linspace(zb, zt, 60), [zc]]))
        sx = m.sx

        def section(z, grow=0.0):
            xf = (x_post(z) - gap - L.mid_px) * sx
            xa = (pr.rudder_aft(z) - L.mid_px) * sx
            u = np.linspace(0, 1, 6)
            xs = xf + (xa - xf) * u
            hs = hf + (ha - hf) * u + grow
            zm = z * m.sy
            stb = [[x, h, zm] for x, h in zip(xs, hs)]
            prt = [[x, -h, zm] for x, h in zip(xs[::-1], hs[::-1])]
            if grow:
                stb[-1][0] -= grow
                prt[0][0] -= grow
            return np.array(stb + prt)
        V, F, M = sweep([section(z) for z in zs], "Copper")
        zc_m = zc * m.sy
        M = ["Copper" if V[list(f)][:, 2].mean() < zc_m else "HullBlack" for f in F]
        part.add(V, F, M)
        # straps: a band round the blade at each pintle
        bz = 0.5 * rs["strap_broad_in"] * IN
        st = rs["strap_thick_in"] * IN
        for z, x_end, z_end in pr.rudder_straps + [(pr.rudder_band[0], None, None)]:
            ring = section(z, grow=st)
            secs = [ring + [0, 0, -bz], ring + [0, 0, bz]]
            irons.add(*sweep(secs, "Bronze"))
            # the knuckle on the post's aft face
            if x_end is not None:
                c = np.array([(x_post(z) - 1.0 - L.mid_px) * sx, 0.0, z * m.sy])
                circ = np.array([c + 2.0 * IN * np.array([math.cos(a), math.sin(a), 0]) for a in
                                 np.linspace(0, 2 * math.pi, 13)[:-1]])
                irons.add(*sweep([circ + [0, 0, -2.5 * IN], circ + [0, 0, 2.5 * IN]], "Bronze"))
                # the gudgeon's arms forward along the post's side and onto the planking, both sides
                xs = np.linspace(x_post(z), x_end, 24)
                zz = np.linspace(z, z_end, 24)
                Pp, Nn = self.surf(xs, zz, False, 0, OUT)
                post_y = L.k * m.sy + self.pl.t0 * IN
                for sgn in (1.0, -1.0):
                    pts, outs = [], []
                    for x, z2, p, nv in zip(xs, zz, Pp, Nn):
                        on_post = x <= float(L._x_aft(min(z2, KNUCKLE))) + 0.5 or p[1] < post_y
                        q = np.array([(x - L.mid_px) * sx, post_y, z2 * m.sy]) if on_post else p.copy()
                        nn = np.array([0, 1.0, 0]) if on_post else nv
                        q[1] *= sgn
                        nn = nn * [1, sgn, 1]
                        pts.append(q)
                        outs.append(nn)
                    ups = [np.array([0, 0, 1.0])] * len(pts)
                    irons.add(*box_along(pts, ups, outs, bz, -0.2 * IN, st, "Bronze"))
        # the pendant band's eye, standing aft from the blade
        z, x_end = pr.rudder_band
        xa = (pr.rudder_aft(z) - L.mid_px) * sx
        xe = (x_end - L.mid_px) * sx
        pts = [[xa + 0.5 * IN, 0, z * m.sy], [xe, 0, z * m.sy]]
        irons.add(*box_along(pts, [[0, 0, 1.0]] * 2, [[0, 1.0, 0]] * 2, 1.5 * IN, -0.75 * IN, 0.75 * IN, "Bronze"))

    def parts(self):
        """Every mesh: dict name -> (V, faces, materials, side) with side 'stbd' (mirror it for port) or 'centre'."""
        pos = self.positions()
        out = {}
        groups = {"Skin": ["Skin", "SternEnds"], "GunWall": ["GunWall"], "BulwarkIn": ["BulwarkIn", "BulwarkEnds"],
                  "BulwarkTop": ["BulwarkTop"], "PortLinings": ["Linings"]}
        X, Z = np.array(self.V.X), np.array(self.V.Z)
        for name, gs in groups.items():
            part = Part()
            for g in gs:
                fl = self.groups[g]
                F = [f for f, _ in fl]
                M = []
                for f, mat in fl:
                    if mat in ("paint", "riser"):
                        xc, zc = X[list(f)].mean(), Z[list(f)].mean()
                        if mat == "riser":
                            mat = "HullBlack"
                        else:
                            mat = str(self.pl.paint_at(np.array([xc]), np.array([zc]), np.array([0]))[0])
                    M.append(mat)
                part.add(pos, F, M)
            out[name] = part
        lid_parts = {}
        for name, _, _, _ in self.lid_groups:
            part = Part()
            fl = self.groups[name]
            part.add(pos, [f for f, _ in fl], [mm for _, mm in fl])
            lid_parts[name] = part
        self.hinges(lid_parts)
        for name in ("RailCap", "Moulding", "Channels", "EntrySteps"):
            out[name] = Part()
        self.rail_caps(out["RailCap"])
        self.moulding(out["Moulding"])
        self.channels(out["Channels"])
        self.entry_steps(out["EntrySteps"])
        centre = {n: Part() for n in ("Bulkheads", "GunDeck", "SparDeck", "TransomTop", "Backbone", "Rudder",
                                      "RudderIrons")}
        self.bulkheads(centre["Bulkheads"])
        self.decks(centre["GunDeck"], centre["SparDeck"])
        self.stern_top(centre["TransomTop"])
        self.backbone(centre["Backbone"])
        self.rudder(centre["Rudder"], centre["RudderIrons"])
        res = {}
        for name, part in list(out.items()) + list(lid_parts.items()):
            res[name] = compact(*part.arrays()) + ("stbd",)
        for name, part in centre.items():
            res[name] = compact(*part.arrays()) + ("centre",)
        return res


def clip_poly(poly, inside):
    """The part of a polygon where inside(p) >= 0 (Sutherland-Hodgman; crossings found on the edge by bisection)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = np.asarray(poly[i], float), np.asarray(poly[(i + 1) % n], float)
        fa, fb = inside(a), inside(b)
        if fa >= 0:
            out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = brentq(lambda t: inside(a + t * (b - a)), 0.0, 1.0, xtol=1e-10)
            out.append(a + t * (b - a))
    # drop repeats
    clean = []
    for p in out:
        if not clean or np.linalg.norm(p - clean[-1]) > 1e-9:
            clean.append(p)
    if len(clean) > 1 and np.linalg.norm(clean[0] - clean[-1]) < 1e-9:
        clean.pop()
    return clean


if __name__ == "__main__":
    import time
    t = time.time()
    L = loft.Lines()
    sk = Skin(L).build()
    res = sk.parts()
    print("built", round(time.time() - t, 1), "s")
    loft.write_obj(sys.argv[1] if len(sys.argv) > 1 else "skin.obj", {k: (v[0], v[1]) for k, v in res.items()})
    print({k: len(v[1]) for k, v in res.items() if not k.startswith("Lid_")})
