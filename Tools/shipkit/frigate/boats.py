"""The frigate's boats (docs/shipkit-11): a launch, two cutters and a gig, stowed on spare spars over the open waist,
the stream anchor and the two kedges in the launch.

    from boats import Lines, Boat, Boats
    ln = Lines(card["lines"]["longboat_1801"], scale)     # a draught's traced lines, scaled: the moulded surface
    bt = Boats(sk, rig, dk, card=None).build();  bt.parts();  bt.info

Each hull is lofted from a period draught's traced lines (boats_1797.json lines: feet in the draught's frame) the way
the shape loop builds the Sunfish: the stations, the sheer, the gunwale in plan, the stem's rabbet, the keel and the
transom are traced off the draught, the moulded surface (the frames' outside, the drawing's line) is lofted through
them, and the hull is held to the drawing (Lines.check: every station, the sheer, the plan and the written sizes).

How a hull is lofted (Lines)
----------------------------
The moulded surface is laid strake by strake, as a boatbuilder lines off his planks: a row for each fraction s of the
girth, from s = 0 (the garboard's lower edge, on the keel's rabbet) to s = 1 (the sheer). Each row runs from where it
lands aft (on the rabbet up the deadwood and the post below the transom's heel, then on the transom's edge) to where
it lands forward (on the stem's rabbet), so the hood ends are spread up the stem and the transom as the planks' are.
A station whose foot is on the keel holds every row (its girth shared out evenly); a station near either end, whose
foot is up the stem's or the deadwood's rabbet, holds only the rows that pass it (from the one that lands at its foot
up to the sheer). Each row is a smooth curve (monotone cubic in x) through its points on the stations and its two
ends. The sheer row is the draught's sheer in profile and gunwale in plan; the rabbet is the stations' feet, the
stem's traced rabbet and the post.

The boat's frame: metres, x forward from the transom's aft face at its top on the middle line, y to starboard, z up
from the base (the keel's rabbet amidships); Boats places each boat in the ship's frame.
"""
import json
import math
import os

import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator, UnivariateSpline
from scipy.spatial import ConvexHull

import loft
from anchors import Mesh
from skin import sweep

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)


def load_card(path=None):
    return json.load(open(path or os.path.join(HERE, "boats_1797.json")))


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 1e-12, n, 1.0)


def arclen(P):
    P = np.asarray(P, float)
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def resample(P, n):
    """the polyline P at n points evenly by arc length"""
    P = np.asarray(P, float)
    s = arclen(P)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, j]) for j in range(P.shape[1])], -1)


def at_fraction(P, f, wt=None):
    """the point at fraction f (0..1) of the polyline P's length (measured with the axes scaled by wt, if given)"""
    P = np.asarray(P, float)
    s = arclen(P if wt is None else P * wt)
    t = np.clip(f, 0.0, 1.0) * s[-1]
    return np.stack([np.interp(t, s, P[:, j]) for j in range(P.shape[1])], -1)


def fraction_of(P, q, wt=None):
    """the fraction of the polyline P's length (measured as at_fraction's) at its point nearest q, and the distance"""
    P = np.asarray(P, float)
    s = arclen(P if wt is None else P * wt)
    best, f = math.inf, 0.0
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        d = b - a
        L2 = float(d @ d)
        t = 0.0 if L2 < 1e-18 else float(np.clip((q - a) @ d / L2, 0.0, 1.0))
        e = float(np.linalg.norm(a + t * d - q))
        if e < best:
            best, f = e, (s[i] + t * (s[i + 1] - s[i])) / s[-1]
    return f, best


class Curve:
    """a smooth curve through a polyline's points against their length (measured with the axes scaled by wt, if
    given): a cubic spline (C2), or a monotone cubic where the points are few and uneven (no overshoot); kept densely
    sampled at even fractions of that length"""

    def __init__(self, P, wt=None, monotone=False, n=800):
        P = np.asarray(P, float)
        t = arclen(P if wt is None else P * wt)
        keep = np.concatenate([[True], np.diff(t) > 1e-9])
        P, t = P[keep], t[keep] / t[keep][-1]
        f = PchipInterpolator(t, P, axis=0) if (monotone or len(P) < 4) else CubicSpline(t, P, axis=0)
        self.u = np.linspace(0.0, 1.0, n)
        self.D = f(self.u)

    def at(self, f):
        return np.array([np.interp(np.clip(f, 0.0, 1.0), self.u, self.D[:, j]) for j in range(self.D.shape[1])])

    def fraction_of(self, q):
        """the fraction at the curve's point nearest q, and the distance"""
        D = self.D
        d = D[1:] - D[:-1]
        L2 = np.maximum((d * d).sum(1), 1e-18)
        t = np.clip(((q - D[:-1]) * d).sum(1) / L2, 0.0, 1.0)
        e = np.linalg.norm(D[:-1] + t[:, None] * d - q, axis=1)
        i = int(np.argmin(e))
        return float(self.u[i] + t[i] * (self.u[i + 1] - self.u[i])), float(e[i])


def smooth_poly(P, passes=2):
    """light smoothing of a traced polyline (ends kept): the ink's jitter off"""
    P = np.asarray(P, float).copy()
    for _ in range(passes):
        P[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
    return P


class Lines:
    """A traced draught's moulded surface, scaled (scale: drawing feet to the boat's feet in x, y and z), in metres in
    the boat's frame (the module's docstring). rows (n_rows, n_cols, 3): the surface strake row by row from the
    rabbet (row 0) to the sheer; the draught's own lines (scaled) are kept for the checks."""

    def __init__(self, ln, scale, n_rows=25, n_cols=801, land_x=0.35, fair=0.0):
        self.ln, self.scale = ln, np.asarray(scale, float)
        self.n_rows, self.n_cols = n_rows, n_cols
        # the rows land along the rabbet up the deadwood and the stem spaced by its length with its run fore and aft
        # counted at land_x: the long flat stretches by the keel take fewer hood ends, as a builder lines them off
        self.land_w = np.array([land_x, 1.0, 1.0])
        self.fair = fair            # > 0: each row a smoothing spline to about this (m), else a monotone cubic through them
        k = self.scale * FT
        self.k = k
        # the stations, each a polyline in 3D: a square one at its x, a cant frame (cant: the tan of its cant in the
        # half-breadth plan, forward going outboard if > 0) in its plane x = x + cant y, its yz then its true shape
        # (the distance out along the cant line, the height)
        self.stations = []
        for s in sorted(ln["stations"], key=lambda s: s["x"]):
            t = float(s.get("cant", 0.0))
            yz = np.asarray(s["yz"], float)
            c, sn = 1.0 / math.hypot(1.0, t), t / math.hypot(1.0, t)
            P = np.stack([s["x"] + yz[:, 0] * sn, yz[:, 0] * c, yz[:, 1]], -1) * k
            self.stations.append({"name": s["name"], "x": s["x"] * k[0], "cant": t * k[0] / k[1], "P": P})
        self.hs = ln["rabbet_half_siding_ft"] * k[1]                  # the rabbet's half-siding
        sh = smooth_poly(np.asarray(ln["sheer"], float) * k[[0, 2]])
        gw = smooth_poly(np.asarray(ln["gunwale_plan"], float) * k[[0, 1]])
        self.sheer_xz, self.gunwale_xy = sh, gw
        self.keel_bottom = ln["keel_bottom_z"] * k[2]
        self.stem_fore = np.asarray(ln["stem_fore_edge"], float) * k[[0, 2]]
        self.transom_tr = np.asarray(ln["transom_edge"], float) * k
        self.waterlines = [(w["z"] * k[2], np.asarray(w["plan"], float) * k[[0, 1]]) for w in ln.get("waterlines", [])]
        self._backbone()
        self._boundaries()
        self._wl_sections()
        self._rows()

    @staticmethod
    def plane_x(st, y):
        """x of a station's plane at half-breadth y"""
        return st["x"] + st["cant"] * y

    # --- the draught's lines ---------------------------------------------------------------------------------------
    def sheer_z(self, x):
        return np.interp(x, self.sheer_xz[:, 0], self.sheer_xz[:, 1])

    def gunwale_y(self, x):
        return np.interp(x, self.gunwale_xy[:, 0], self.gunwale_xy[:, 1], left=self.gunwale_xy[0, 1], right=self.hs)

    def _backbone(self):
        """the rabbet in profile (x, z) from the transom's heel along the deadwood and keel to the stem head, and the
        transom's plane"""
        ln, k = self.ln, self.k
        tr = self.transom_tr
        heel = tr[0]
        # the transom's outer face: the plane through the post's aft edge, square to the middle line
        if "post_aft_edge" in ln:
            pa = np.asarray(ln["post_aft_edge"], float) * k[[0, 2]]
            top, foot = pa[0], pa[1]
        else:
            top = np.array([tr[-1][0], tr[-1][2]])
            foot = np.array([heel[0], heel[2]])
        d = unit(foot - top)
        self.post_top, self.post_dir = top, d                  # (x, z), down and forward along the post's aft edge
        self.transom_n = np.array([d[1], 0.0, -d[0]])            # the transom face's normal (aft and up)
        if self.transom_n[0] > 0:
            self.transom_n = -self.transom_n
        # the stations' feet (y, z at j = 0), and the stem's rabbet run up to the sheer
        feet = np.array([[self.plane_x(s, self.hs), s["P"][0][2]] for s in self.stations])
        sr = (np.asarray(ln["stem_rabbet"], float) * k[[0, 2]])[::-1]          # traced from the head down: up the stem
        sr = sr[np.concatenate([[True], np.diff(sr[:, 1]) > -0.02 * k[2]])]
        # the rabbet ends at the sheer: cut where it passes it (a washstrake's above), or run up to it, turning
        # upright toward the head (the stem's moulding kept)
        over = sr[:, 1] - self.sheer_z(sr[:, 0])
        if (over > 0).any():
            i = int(np.argmax(over > 0))
            a, b = sr[i - 1], sr[i]
            t = over[i - 1] / (over[i - 1] - over[i])
            sr = np.concatenate([sr[:i], [a + t * (b - a)]])
        else:
            top_r = sr[-1]
            slope = (sr[-1][0] - sr[-4][0]) / max(1e-6, sr[-1][1] - sr[-4][1])   # dx/dz at the traced top
            z_head = float(self.sheer_z(top_r[0]))
            for _ in range(4):
                dz = z_head - top_r[1]
                z_head = float(self.sheer_z(top_r[0] + 0.5 * slope * dz))
            dz = z_head - top_r[1]
            t = np.linspace(0.0, 1.0, 8)[1:]
            xx = top_r[0] + slope * dz * (t - 0.5 * t * t)        # its lean dying away to upright at the head
            sr = np.concatenate([sr, np.stack([xx, top_r[1] + dz * t], -1)])
        self.stem_rabbet = sr
        self.head = np.array([sr[-1][0], self.hs, sr[-1][1]])
        # the keel's rabbet: z 0 between the feet of the deadwood and the stem (the base), the stations' feet aft
        # of where the deadwood rises, the transom's heel
        z_lift = 0.05 * k[2]                                       # a foot higher than this is up the deadwood/stem
        aft = [(heel[0], heel[2])] + [(x, z) for x, z in feet if z > z_lift and x < 0.5 * self.head[0]]
        aft += [(float(p[0][0]), z) for z, p in self.waterlines if z < heel[2]]     # a waterline's end on the deadwood
        aft = np.array(sorted(aft))
        # the deadwood's foot: where the rabbet comes down to the base
        x_af = float(aft[-1][0])
        nxt = [x for x, z in feet if x > x_af]
        if nxt:
            x_af = 0.5 * (x_af + min(nxt))
        aft = np.concatenate([aft, [[x_af, 0.0]]])
        i0 = int(np.argmax(sr[:, 1] > z_lift))
        x_ff = float(sr[max(0, i0 - 1)][0])
        fore_ = np.concatenate([[[x_ff, 0.0]], sr[i0:]])
        self.after_foot, self.fore_foot = np.array([x_af, self.hs, 0.0]), np.array([x_ff, self.hs, 0.0])
        self.deadwood = aft[::-1]                                 # from the foot up to the heel: (x, z)
        self.stem_up = fore_                                      # from the forefoot up to the head: (x, z)
        self.rabbet = np.concatenate([aft, fore_])                # aft to fore along the bottom: (x, z)
        # the gunwale in plan ends on the stem's side at the head: its traced end (short of the head by an inch or
        # four, the plan's ink fading into the stem's) is drawn out over its last two feet to meet it
        gw = self.gunwale_xy.copy()
        xe, xh = float(gw[-1, 0]), float(self.head[0])
        xs = xe - 2.0 * k[0]
        m = gw[:, 0] > xs
        gw[m, 0] = xs + (gw[m, 0] - xs) * (xh - xs) / (xe - xs)
        w = np.clip((gw[:, 0] - xs) / (xh - xs), 0.0, 1.0) ** 3
        gw[:, 1] = np.maximum(gw[:, 1] + w * (self.hs - gw[-1, 1]), self.hs)
        self.gunwale_xy = gw

    def rabbet_z(self, x):
        R = self.rabbet
        return np.interp(x, R[:, 0], R[:, 1])

    def _boundaries(self):
        """where each row lands aft (the deadwood's rabbet, then the transom's edge) and forward (the stem's rabbet):
        3D polylines with the share of the rows each part takes"""
        hs = self.hs
        dw = np.stack([self.deadwood[:, 0], np.full(len(self.deadwood), hs), self.deadwood[:, 1]], -1)
        tr = self.transom_tr.copy()
        # the transom's top corner on the sheer (the draught's body plan and profile differ by an inch or so there)
        corner_z = float(self.sheer_z(tr[-1][0]))
        corner_y = float(self.gunwale_y(tr[-1][0]))
        n = len(tr)
        w = np.clip(np.linspace(-0.5, 1.0, n), 0.0, 1.0) ** 2
        tr[:, 2] += w * (corner_z - tr[-1][2])
        tr[:, 1] += w * (corner_y - tr[-1][1])
        tr[0, 1] = hs
        self.transom_edge = tr
        # the rows that land on the transom: as many as its edge takes at the planks' width amidships
        mid = max(self.stations, key=lambda s: float(np.max(s["P"][:, 1])))
        self.s_heel = float(np.clip(1.0 - arclen(tr)[-1] / arclen(mid["P"])[-1], 0.3, 0.75))
        self.aft_parts = (dw, tr)
        st = np.stack([self.stem_up[:, 0], np.full(len(self.stem_up), hs), self.stem_up[:, 1]], -1)
        self.fore_edge = st
        self.dw_curve = Curve(dw, self.land_w, monotone=True)
        self.tr_curve = Curve(tr)
        self.fore_curve = Curve(st, self.land_w, monotone=True)

    @staticmethod
    def _hb_at(P, z):
        """a section polyline's half-breadth at height z (its highest crossing), or None"""
        for i in range(len(P) - 1, 0, -1):
            a, b = P[i - 1], P[i]
            if (a[2] - z) * (b[2] - z) <= 0 and a[2] != b[2]:
                return float(a[1] + (b[1] - a[1]) * (z - a[2]) / (b[2] - a[2]))
        return None

    def _wl_sections(self):
        """sections where the draught's stations are far apart (and in the run and the entrance beyond them), from its
        waterlines: each is the neighbouring sections' shape blended by distance, then bent to its foot on the rabbet,
        its head on the sheer and the gunwale, and the waterlines' half-breadths at their heights. The stations are
        held where they are: a waterline's disagreement with them (an inch or two of ink) is shared out between them"""
        if not self.waterlines:
            return
        step = 0.75 * self.k[0]
        real = list(self.stations)
        n_pts = 28
        corr = []
        for z, p in self.waterlines:
            xc, dc = [], []
            for st in real:
                hb = self._hb_at(st["P"], z) if st["cant"] == 0 and st["P"][0][2] < z else None
                if hb is not None:
                    xc.append(st["x"])
                    dc.append(hb - float(np.interp(st["x"], p[:, 0], p[:, 1])))
            corr.append((np.array(xc), np.array(dc)))

        def target_y(i, x):
            z, p = self.waterlines[i]
            xc, dc = corr[i]
            y = float(np.interp(x, p[:, 0], p[:, 1]))
            if not len(xc):
                return y
            if x < xc[0]:
                return y + dc[0] * (x - p[0, 0]) / max(1e-9, xc[0] - p[0, 0])
            if x > xc[-1]:
                return y + dc[-1] * (p[-1, 0] - x) / max(1e-9, p[-1, 0] - xc[-1])
            return y + float(np.interp(x, xc, dc))

        def shape(P):
            return resample(P[:, 1:], n_pts)

        tr = self.transom_edge
        anchors = [(float(np.mean(tr[:, 0])), shape(tr))] + [(st["x"], shape(st["P"])) for st in real]
        anchors.append((float(self.head[0]), None))
        x_wl0 = min(p[0, 0] for _, p in self.waterlines)
        x_wl1 = max(p[-1, 0] for _, p in self.waterlines)
        new = []
        for (xa, Pa), (xb, Pb) in zip(anchors[:-1], anchors[1:]):
            n = int(round((xb - xa) / step)) - 1
            for x in np.linspace(xa, xb, n + 2)[1:-1]:
                if not (x_wl0 < x < x_wl1):
                    continue
                t = (x - xa) / (xb - xa)
                P = Pa if Pb is None else (Pb if Pa is None else (1.0 - t) * Pa + t * Pb)
                foot = np.array([self.hs, float(self.rabbet_z(x))])
                top = np.array([float(self.gunwale_y(x)), float(self.sheer_z(x))])
                # the blended shape turned and scaled onto the chord from its foot to its head (so its fullness goes
                # with its size: a fine bow section stays fine)
                c0, c1 = P[-1] - P[0], top - foot
                sc = float(np.linalg.norm(c1) / max(1e-9, np.linalg.norm(c0)))
                an = math.atan2(c1[1], c1[0]) - math.atan2(c0[1], c0[0])
                rot = np.array([[math.cos(an), -math.sin(an)], [math.sin(an), math.cos(an)]])
                P = foot + sc * (P - P[0]) @ rot.T
                # bend it to the waterlines (half-breadths only), each correction fading to the next along the girth
                knots, dy = [0.0, 1.0], [0.0, 0.0]
                g = arclen(P) / arclen(P)[-1]
                for i, (z, p) in enumerate(self.waterlines):
                    if not (p[0, 0] < x < p[-1, 0]) or z <= foot[1] or z >= top[1]:
                        continue
                    Q = np.stack([np.zeros(n_pts), P[:, 0], P[:, 1]], -1)
                    hb = self._hb_at(Q, z)
                    if hb is None:
                        continue
                    j = int(np.argmin(np.abs(P[:, 1] - z)))
                    knots.append(float(g[j]))
                    dy.append(target_y(i, x) - hb)
                o = np.argsort(knots)
                P[:, 0] += np.interp(g, np.asarray(knots)[o], np.asarray(dy)[o])
                P[:, 0] = np.maximum(P[:, 0], self.hs)
                yz = resample(P, n_pts)
                new.append({"name": "wl %.2f" % (x / self.k[0]), "x": float(x), "cant": 0.0, "synthetic": True,
                            "P": np.stack([np.full(n_pts, x), yz[:, 0], yz[:, 1]], -1)})
        self.stations = sorted(real + new, key=lambda st: st["x"])

    def aft_end(self, s):
        dw, tr = self.aft_parts
        if s <= self.s_heel:
            return self.dw_curve.at(s / self.s_heel)
        return self.tr_curve.at((s - self.s_heel) / (1.0 - self.s_heel))

    def fore_end(self, s):
        return self.fore_curve.at(s)

    def s_of_foot(self, x, z):
        """the row that lands at a station's foot (x, z): 0 on the keel, else where it is up the deadwood or stem"""
        q = np.array([x, self.hs, z])
        if x < self.after_foot[0] and z > 1e-4:
            dw, tr = self.aft_parts
            f, e = self.dw_curve.fraction_of(q)
            return f * self.s_heel
        if x > self.fore_foot[0] and z > 1e-4:
            f, e = self.fore_curve.fraction_of(q)
            return f
        return 0.0

    def station_top(self, st):
        """where a station's plane meets the gunwale in plan: (x, y, z on the sheer)"""
        y = float(st["P"][-1][1])
        for _ in range(40):
            y = 0.5 * y + 0.5 * float(self.gunwale_y(self.plane_x(st, y)))
        x = self.plane_x(st, y)
        return np.array([x, y, float(self.sheer_z(x))])

    def _rows(self):
        """the surface, row by row (the class docstring)"""
        nr, nc = self.n_rows, self.n_cols
        S = np.linspace(0.0, 1.0, nr)
        secs = []
        for st in self.stations:
            P = st["P"].copy()
            # its foot on the rabbet, its head on the sheer and the gunwale (the draught's views agree to an inch), each
            # shift in the station's own plane, spread over the lower quarter and the upper two fifths of its girth
            xf = self.plane_x(st, self.hs)
            d_foot = np.array([xf, self.hs, float(self.rabbet_z(xf))]) - P[0]
            d_top = self.station_top(st) - P[-1]
            gl = arclen(P) / arclen(P)[-1]
            wt = np.clip((gl - 0.6) / 0.4, 0.0, 1.0) ** 2
            wb = np.clip(1.0 - gl / 0.25, 0.0, 1.0) ** 2
            P += wt[:, None] * d_top[None] + wb[:, None] * d_foot[None]
            s0 = self.s_of_foot(P[0][0], P[0][2])
            secs.append((Curve(P), s0))
        self.sec_s0 = {st["name"]: sec[1] for st, sec in zip(self.stations, secs)}
        rows = np.zeros((nr, nc, 3))
        self.row_ends = []
        for k, s in enumerate(S):
            pts = [self.aft_end(s)]
            for P, s0 in secs:
                if s0 <= s + 1e-9 and s0 < 1.0:
                    pts.append(P.at((s - s0) / (1.0 - s0)))
            pts.append(self.fore_end(s))
            P = np.array(sorted(pts, key=lambda p: p[0]))
            keep = np.concatenate([[True], np.diff(P[:, 0]) > 1e-5])
            P = P[keep]
            if self.fair > 0 and len(P) >= 6:
                # faired as a loftsman's batten: a smoothing spline through the stations, held at its two ends
                w = np.ones(len(P))
                w[0] = w[-1] = 30.0
                fy = UnivariateSpline(P[:, 0], P[:, 1], w=w, k=3, s=len(P) * self.fair ** 2)
                fz = UnivariateSpline(P[:, 0], P[:, 2], w=w, k=3, s=len(P) * self.fair ** 2)
            else:
                fy = PchipInterpolator(P[:, 0], P[:, 1])
                fz = PchipInterpolator(P[:, 0], P[:, 2])
            xs = np.linspace(P[0, 0], P[-1, 0], nc)
            rows[k] = np.stack([xs, fy(xs), fz(xs)], -1)
            self.row_ends.append((P[0], P[-1]))
        # the sheer row is the draught's sheer and gunwale between the transom's corner and the stem head
        xs = np.linspace(rows[-1, 0, 0], rows[-1, -1, 0], nc)
        rows[-1] = np.stack([xs, self.gunwale_y(xs), self.sheer_z(xs)], -1)
        rows[-1, -1] = self.fore_end(1.0)
        rows[-1, 0] = self.aft_end(1.0)
        self.rows = rows
        self.S = S

    # --- sections of the lofted surface ---------------------------------------------------------------------------
    def section(self, x, cant=0.0):
        """the lofted surface cut by the plane x' = x + cant y': (m, 3) points from the lowest row that reaches it up
        to the sheer"""
        def cross(R):
            g = R[:, 0] - cant * R[:, 1] - x
            i = np.nonzero(np.sign(g[:-1]) * np.sign(g[1:]) <= 0)[0]
            if not len(i):
                return None
            i = int(i[0])
            t = g[i] / (g[i] - g[i + 1]) if g[i] != g[i + 1] else 0.0
            return R[i] + t * (R[i + 1] - R[i])
        out = [p for p in (cross(self.rows[k]) for k in range(self.n_rows)) if p is not None]
        if out and cross(self.rows[0]) is None:
            # a cut near either end starts where it crosses the rabbet up the deadwood or the stem
            ends = [p for p in (cross(np.concatenate(self.aft_parts)), cross(self.fore_edge)) if p is not None]
            if ends:
                out.insert(0, min(ends, key=lambda p: p[2]))
        return np.array(out)

    def half_breadth(self, x, z):
        """the surface's half-breadth at (x, z), or None outside it"""
        sec = self.section(x)
        if len(sec) < 2 or z < sec[:, 2].min() or z > sec[:, 2].max():
            return None
        o = np.argsort(sec[:, 2])
        return float(np.interp(z, sec[o, 2], sec[o, 1]))

    def check(self):
        """the loft against the draught (inches at the boat's own scale): each station's deviation (the lofted section
        at its x against its traced points, nearest distance), the sheer's and the plan's"""
        out = {}
        worst = 0.0
        for st in self.stations:
            if st.get("synthetic"):
                continue
            sec = self.section(st["x"], st["cant"])
            d = []
            for p in st["P"][1:-1]:
                dd = np.min(np.linalg.norm(sec - p[None], axis=1)) if len(sec) else math.inf
                # distance to the polyline, not only its vertices
                for a, b in zip(sec[:-1], sec[1:]):
                    v = b - a
                    t = float(np.clip((p - a) @ v / max(1e-12, v @ v), 0.0, 1.0))
                    dd = min(dd, float(np.linalg.norm(a + t * v - p)))
                d.append(dd)
            m = max(d) / IN
            worst = max(worst, m)
            out[st["name"]] = round(m, 2)
        wl = []
        for z, p in self.waterlines:
            d = [abs(hb - y) for x, y in p[2:-2] for hb in [self.half_breadth(x, z)] if hb is not None]
            wl.append(round(max(d) / IN, 2) if d else None)
        return {"stations_max_in": out, "worst_in": round(worst, 2), "waterlines_max_in": wl}


# ---- a boat ---------------------------------------------------------------------------------------------------------
def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class Surface:
    """A lofted hull's moulded surface as a fine grid over (s, u): s the girth fraction (0 on the rabbet, 1 on the sheer)
    and u the fraction along each row from its after end to its fore end (Lines.rows, a monotone cubic in s between
    them); the end columns exactly on the boundaries the rows land on. at() and normal() read it bilinearly; the
    normal points out of the hull (starboard side)."""

    def __init__(self, ln, ns=201):
        R = ln.rows
        s = np.linspace(0.0, 1.0, ns)
        G = PchipInterpolator(ln.S, R, axis=0)(s)
        for i, si in enumerate(s):
            G[i, 0] = ln.aft_end(si)
            G[i, -1] = ln.fore_end(si)
        self.ln, self.s, self.G = ln, s, G
        self.ns, self.nc = G.shape[:2]
        self.u = np.linspace(0.0, 1.0, self.nc)
        N = np.cross(np.gradient(G, self.u, axis=1), np.gradient(G, s, axis=0))
        self.sign = 1.0 if N[ns // 2, self.nc // 2, 1] > 0 else -1.0
        self.N = unit(N * self.sign)
        # the end columns are the boundaries themselves (the rabbet, the transom's edge), not the rows' cubics: there
        # the low rows meet the rabbet at a shallow angle and the grid's derivatives give no normal (they turned it
        # into the boat), so the three end columns take the normal of the next column in (3 cm along a row)
        self.N[:, :3] = self.N[:, 3:4]
        self.N[:, -3:] = self.N[:, -4:-3]
        d = np.linalg.norm(np.diff(G, axis=0), axis=2)
        self.girth_cols = d.sum(0)                                    # each column's girth (m)
        self.len_rows = G[:, -1, 0] - G[:, 0, 0]                      # each row's length (m)

    def _bilinear(self, A, s, u):
        s = np.clip(np.asarray(s, float), 0.0, 1.0) * (self.ns - 1)
        u = np.clip(np.asarray(u, float), 0.0, 1.0) * (self.nc - 1)
        i = np.minimum(np.floor(s).astype(int), self.ns - 2)
        j = np.minimum(np.floor(u).astype(int), self.nc - 2)
        fs, fu = (s - i)[..., None], (u - j)[..., None]
        return ((A[i, j] * (1 - fu) + A[i, j + 1] * fu) * (1 - fs) + (A[i + 1, j] * (1 - fu) + A[i + 1, j + 1] * fu) * fs)

    def at(self, s, u):
        return self._bilinear(self.G, s, u)

    def normal(self, s, u):
        return unit(self._bilinear(self.N, s, u))

    def tangent_u(self, s, u, h=1e-3):
        return unit(self.at(s, np.minimum(np.asarray(u) + h, 1.0)) - self.at(s, np.maximum(np.asarray(u) - h, 0.0)))

    def girth(self, u):
        return np.interp(u, self.u, self.girth_cols)

    def row_len(self, s):
        return np.interp(s, self.s, self.len_rows)

    def u_at_x(self, s, x):
        """u where the row s reaches x (rows are monotone in x)"""
        i = int(round(float(np.clip(s, 0, 1)) * (self.ns - 1)))
        return float(np.interp(x, self.G[i, :, 0], self.u))


def grid_quads(nr, nc, base=0, flip=False, closed_c=False):
    """the quads of an nr x nc grid of vertices (row-major from base): corner order (r, c), (r, c+1), (r+1, c+1),
    (r+1, c), or reversed"""
    F = []
    cc = nc if closed_c else nc - 1
    for r in range(nr - 1):
        for c in range(cc):
            c1 = (c + 1) % nc
            q = (base + r * nc + c, base + r * nc + c1, base + (r + 1) * nc + c1, base + (r + 1) * nc + c)
            F.append(q[::-1] if flip else q)
    return F


def mirror_mesh(m, start=0):
    """a Mesh's pieces from index start mirrored to port and added (faces turned so they still face out)"""
    Vs = m.V[start:]
    k0 = sum(len(v) for v in m.V[:start])
    nf = len(m.F)
    Fs = [f for f in m.F if min(f) >= k0]
    Ms = [mm for f, mm in zip(m.F, m.M) if min(f) >= k0]
    Ls = [ll for f, ll in zip(m.F, m.lab) if min(f) >= k0]
    V = np.concatenate(Vs) * np.array([1.0, -1.0, 1.0])
    off = m.n - k0
    m.V.append(V)
    m.F += [tuple(off + i for i in f[::-1]) for f in Fs]
    m.M += Ms
    m.lab += Ls
    m.n += len(V)
    return nf


def strip_solid(A, B, wa, wb, mat_side, mat_b=None, mat_a=None, cap0=True, cap1=True, mat_caps=None):
    """a profile strip (in the boat's middle plane: A and B polylines (n, 2) of (x, z), matched point by point)
    given breadth: half-widths wa at A and wb at B (scalars or (n,)); both sides, B's edge face, A's edge face if
    mat_a, and caps at the ends. Returns (V, F, M), its faces turned out"""
    A, B = np.asarray(A, float), np.asarray(B, float)
    n = len(A)
    wa = np.broadcast_to(np.asarray(wa, float), (n,))
    wb = np.broadcast_to(np.asarray(wb, float), (n,))
    # vertex rings: [A+, B+, B-, A-] per point
    V = np.stack([np.stack([A[:, 0], wa, A[:, 1]], -1), np.stack([B[:, 0], wb, B[:, 1]], -1),
                  np.stack([B[:, 0], -wb, B[:, 1]], -1), np.stack([A[:, 0], -wa, A[:, 1]], -1)], 1).reshape(-1, 3)
    F, M = [], []

    def q(i, a, b):
        return (4 * i + a, 4 * i + b, 4 * (i + 1) + b, 4 * (i + 1) + a)
    for i in range(n - 1):
        F += [q(i, 0, 1), q(i, 2, 3)]
        M += [mat_side, mat_side]
        if mat_b:
            F.append(q(i, 1, 2))
            M.append(mat_b)
        if mat_a:
            F.append(q(i, 3, 0))
            M.append(mat_a)
    if cap0:
        F.append((0, 3, 2, 1))
        M.append(mat_caps or mat_side)
    if cap1:
        k = 4 * (n - 1)
        F.append((k, k + 1, k + 2, k + 3))
        M.append(mat_caps or mat_side)
    # turn them out: the first side face's normal points to +y
    V3 = V
    f = F[0]
    nrm = np.cross(V3[f[1]] - V3[f[0]], V3[f[3]] - V3[f[0]])
    if nrm[1] < 0:
        F = [ff[::-1] for ff in F]
    return V, F, M


def profile_solid(O, R, wo, wr, mat):
    """the keel, deadwood, post and stem outside the rabbet: the region in the middle plane between the outer edge O
    and the rabbet R (both (n, 2) of (x, z), from the heel (O[0] = R[0]) to the stem head's top), half-widths wo and
    wr (scalars or per point): its two sides (the region triangulated), its outer edge's faces and the head's top;
    open along the rabbet (the hog and the planking close it). Faces turned out"""
    O, R = np.asarray(O, float), np.asarray(R, float)
    wo = np.broadcast_to(np.asarray(wo, float), (len(O),))
    wr = np.broadcast_to(np.asarray(wr, float), (len(R),))
    start = 1 if np.linalg.norm(O[0] - R[0]) < 1e-6 else 0
    P = np.concatenate([O, R[::-1][:len(R) - start]])
    W = np.concatenate([wo, wr[::-1][:len(R) - start]])
    n, no = len(P), len(O)
    sgn_area = area2d(P)
    tris = loft.ear_clip(P if sgn_area > 0 else P[::-1])
    if sgn_area <= 0:
        tris = [tuple(n - 1 - i for i in t) for t in tris]
    V = np.concatenate([np.stack([P[:, 0], W, P[:, 1]], -1), np.stack([P[:, 0], -W, P[:, 1]], -1)])
    F = [tuple(t) for t in tris] + [tuple(n + i for i in t[::-1]) for t in tris]
    M = [mat] * len(F)
    for i in range(no):                    # the outer edge, then the head's top (O's last to R's last)
        j = i + 1
        if j >= n:
            break
        q = (i, j, n + j, n + i)            # out of the region where P runs counter-clockwise: in, like the sides
        F.append(q[::-1] if sgn_area > 0 else q)
        M.append(mat)
    # turn them out: a +y side face's normal along +y
    f = F[0]
    nrm = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
    if nrm[1] < 0:
        F = [ff[::-1] for ff in F]
    return V, F, M


def bar(P, Nn, Bn, n0, n1, b0, b1, mat, caps=True):
    """a bar along the polyline P (k, 3) with the cross-section's axes Nn and Bn at each point (k, 3): its corners at
    P + n Nn + b Bn for n in (n0, n1) and b in (b0, b1) (each scalar or (k,)); faces turned out"""
    P = np.asarray(P, float)
    k = len(P)
    n0, n1, b0, b1 = (np.broadcast_to(np.asarray(v, float), (k,))[:, None] for v in (n0, n1, b0, b1))
    C = np.stack([P + n0 * Nn + b0 * Bn, P + n1 * Nn + b0 * Bn, P + n1 * Nn + b1 * Bn, P + n0 * Nn + b1 * Bn], 1)
    return sweep_ends(list(C), mat) if caps else sweep(list(C), mat, closed=True, caps=False)


def poly_slab(outline, z0, z1, mat, mat_edge=None):
    """a slab between heights z0 and z1 over a plan outline (n, 2), counter-clockwise, convex or star-shaped about
    its mean: top, bottom and edges (fanned round the outline's mean)"""
    P = np.asarray(outline, float)
    n = len(P)
    c = P.mean(0)
    V = np.concatenate([np.c_[P, np.full(n, z1)], np.c_[P, np.full(n, z0)], [[c[0], c[1], z1], [c[0], c[1], z0]]])
    F, M = [], []
    for i in range(n):
        j = (i + 1) % n
        F += [(2 * n, i, j), (2 * n + 1, n + j, n + i), (i, n + i, n + j, j)]
        M += [mat, mat, mat_edge or mat]
    if area2d(P) < 0:
        F = [f[::-1] for f in F]
    return V, F, M


def area2d(P):
    P = np.asarray(P, float)
    return 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))


def offset2(Q, d):
    """the polyline Q (n, 2) of (y, z), running from her middle or her bottom up her side, carried into her by d
    (scalar or (n,)) square to each segment, mitred at its corners (the mitre held to twice d)"""
    Q = np.asarray(Q, float)
    d = np.broadcast_to(np.asarray(d, float), (len(Q),))
    seg = unit(np.diff(Q, axis=0))
    nseg = np.stack([-seg[:, 1], seg[:, 0]], -1)
    N = np.zeros_like(Q)
    N[0], N[-1] = nseg[0], nseg[-1]
    m = unit(nseg[:-1] + nseg[1:])
    c = np.maximum((m * nseg[1:]).sum(1), 0.5)
    N[1:-1] = m / c[:, None]
    return Q + N * d[:, None]


def level_top(Q, z):
    """the polyline Q (y, z) with its last point slid along its last segment to height z (a cut level there)"""
    Q = np.array(Q, float)
    a, b = Q[-2], Q[-1]
    if abs(b[1] - a[1]) > 1e-9:
        Q[-1] = a + (z - a[1]) / (b[1] - a[1]) * (b - a)
    return Q


def y_at_z(Q, z):
    """the half-breadth where the polyline Q (y, z), running up her side, is at height z (its highest crossing), or
    None"""
    for i in range(len(Q) - 1, 0, -1):
        a, b = Q[i - 1], Q[i]
        if (a[1] - z) * (b[1] - z) <= 0 and a[1] != b[1]:
            return float(a[0] + (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]))
    return None


def extrude(P2, to3d, w0, w1, mat, mat_caps=None):
    """a prism: the simple polygon P2 (n, 2) in (u, v) carried from w0 to w1, to3d(uv (n, 2), w) giving its points
    (n, 3) in the boat; both ends and the sides, faces turned out"""
    P2 = np.asarray(P2, float)
    if area2d(P2) < 0:
        P2 = P2[::-1]
    n = len(P2)
    tris = loft.ear_clip(P2)
    V = np.concatenate([to3d(P2, w1), to3d(P2, w0)])
    F = [tuple(t) for t in tris] + [tuple(n + i for i in t[::-1]) for t in tris]
    F += [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)]
    c = P2.mean(0)
    e = 1e-3 * max(1e-9, float(np.ptp(P2, axis=0).max()))
    o = to3d(c[None], w0)[0]
    du = to3d((c + [e, 0.0])[None], w0)[0] - o
    dv = to3d((c + [0.0, e])[None], w0)[0] - o
    dw = to3d(c[None], w1)[0] - o
    if np.dot(np.cross(du, dv), dw) < 0:
        F = [f[::-1] for f in F]
    return V, F, [mat_caps or mat] * (2 * len(tris)) + [mat] * n


def plan_prism(outline, z_top, z_bot, mat, mat_side=None):
    """a slab over a plan outline (n, 2) of (x, y), its top at z_top and bottom at z_bot (scalars or per point)"""
    P = np.asarray(outline, float)
    n = len(P)
    zt = np.broadcast_to(np.asarray(z_top, float), (n,))
    zb = np.broadcast_to(np.asarray(z_bot, float), (n,))
    flip = area2d(P) < 0
    if flip:
        P, zt, zb = P[::-1], zt[::-1], zb[::-1]
    tris = loft.ear_clip(P)
    V = np.concatenate([np.c_[P, zt], np.c_[P, zb]])
    F = [tuple(t) for t in tris] + [tuple(n + i for i in t[::-1]) for t in tris]
    F += [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)]
    return V, F, [mat] * (2 * len(tris)) + [mat_side or mat] * n


def cylinder(P0, P1, r, mat, n=8, caps=True, r1=None):
    """a straight round bar from P0 to P1 (radius r, or r to r1), n sides"""
    P0, P1 = np.asarray(P0, float), np.asarray(P1, float)
    a = unit(P1 - P0)
    u = unit(np.cross(a, EZ if abs(a[2]) < 0.9 else EX))
    v = np.cross(a, u)
    t = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    ring = np.cos(t)[:, None] * u + np.sin(t)[:, None] * v
    r1 = r if r1 is None else r1
    return sweep([P0 + r * ring, P1 + r1 * ring], mat, closed=True, caps=caps)


def torus(c, ax, R, r, mat, n=12, m=6, e1=None):
    """a ring about the axis ax through c: radius R to its bar's centre, the bar's radius r"""
    c, ax = np.asarray(c, float), unit(ax)
    e1 = unit(np.cross(ax, EZ if abs(ax[2]) < 0.9 else EX)) if e1 is None else unit(e1)
    e2 = np.cross(ax, e1)
    S = []
    for t in np.linspace(0.0, 2.0 * math.pi, n, endpoint=False):
        d = math.cos(t) * e1 + math.sin(t) * e2
        p = np.linspace(0.0, 2.0 * math.pi, m, endpoint=False)
        S.append(c + R * d + r * (np.cos(p)[:, None] * d + np.sin(p)[:, None] * ax))
    S = np.array(S)
    V = S.reshape(-1, 3)
    F = []
    for i in range(n):
        for j in range(m):
            a, b = i * m + j, i * m + (j + 1) % m
            a2, b2 = ((i + 1) % n) * m + j, ((i + 1) % n) * m + (j + 1) % m
            F.append((a, a2, b2, b))
    f = F[0]
    nrm = np.cross(V[f[1]] - V[f[0]], V[f[3]] - V[f[0]])
    ctr = c + R * unit(V[list(f)].mean(0) - c - ax * ((V[list(f)].mean(0) - c) @ ax))
    if np.dot(nrm, V[list(f)].mean(0) - ctr) < 0:
        F = [ff[::-1] for ff in F]
    return V, F, [mat] * len(F)


def box(c, half, mat, R=None):
    """a box centred at c with half-sizes half (3,), turned by the rotation R (3x3, its columns the box's axes)"""
    c, h = np.asarray(c, float), np.asarray(half, float)
    R = np.eye(3) if R is None else np.asarray(R, float)
    s = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]])
    V = c + (s * h) @ R.T
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    if np.linalg.det(R) < 0:
        F = [f[::-1] for f in F]
    return V, F, [mat] * 6


def sweep_ends(secs, mat):
    """skin.sweep with its end caps turned out along the tube's own ends (sweep turns them along its chord, which lies
    square to them on a half round)"""
    V, F, M = sweep(secs, mat, closed=True, caps=False)
    S = np.asarray(secs, float)
    m = S.shape[1]
    for end, t in ((0, S[0].mean(0) - S[1].mean(0)), (len(S) - 1, S[-1].mean(0) - S[-2].mean(0))):
        cap = list(range(end * m, end * m + m))
        P = V[cap]
        nrm = sum(np.cross(P[k] - P[0], P[k + 1] - P[0]) for k in range(1, m - 1))
        F.append(tuple(cap) if nrm @ t > 0 else tuple(cap[::-1]))
        M.append(mat)
    return V, F, M


class Boat:
    """One boat as card['boats'][key] gives her, built in her own frame (the module's docstring): the planking
    (carvel or clinker), the keel, stem, deadwood and post, the transom, the frames, keelson, risings, inwales,
    cappings and rubbing strakes (and a cutter's washstrake with its rowlock notches), the thwarts and their knees,
    the stern sheets, bottom boards, breasthook and quarter knees, the rowlocks, a launch's windlass, roller and sling
    plates, and her gear stowed in her (masts and furled sails, oars, rudder and tiller). mesh: every piece, labelled;
    info: her sizes as built."""

    def __init__(self, card, key, name=None):
        self.card, self.key = card, key
        self.name = name or key
        self.b = b = card["boats"][key]
        lc = card["lines"][b["lines"]]
        self.lc = lc
        self.ln = ln = Lines(lc, b["scale"])
        self.fit = lc.get("fittings", {})
        self.k = ln.k
        self.clinker = b["build"] == "clinker"
        self.t = b["plank_in"] * IN
        self.mesh = Mesh()
        self.info = {}
        self.sf = Surface(ln)
        n_cols = {"launch": 96, "cutter": 76, "gig": 66}.get(key, 80)
        tt = np.linspace(0.0, 1.0, n_cols)
        self.U = 0.55 * tt + 0.45 * (0.5 - 0.5 * np.cos(math.pi * tt))  # denser toward the ends
        # the transom's outer face: the plane through the post's aft edge
        self.tr_p = np.array([ln.post_top[0], 0.0, ln.post_top[1]])
        self.tr_n = np.asarray(ln.transom_n, float)                    # aft and up, out of the boat
        self.s_heel = ln.s_heel

    # --- helpers ------------------------------------------------------------------------------------------------------
    def put(self, label, V, F, M):
        self.mesh.cur = label
        self.mesh.add(V, F, M)

    def to_transom(self, P, T):
        """P moved along T to the transom's outer plane"""
        P, T = np.atleast_2d(P), np.atleast_2d(T)
        d = -((P - self.tr_p) @ self.tr_n) / np.where(np.abs(T @ self.tr_n) > 1e-9, T @ self.tr_n, 1e-9)
        return P + d[:, None] * T

    def offset_pts(self, s, u, o):
        """points off the moulded surface by o along its normal, at (s, u) arrays; those on the transom's edge
        (u = 0, s above the heel) kept in the transom's plane"""
        s, u, o = np.broadcast_arrays(np.asarray(s, float), np.asarray(u, float), np.asarray(o, float))
        P = self.sf.at(s, u) + self.sf.normal(s, u) * o[..., None]
        m = (u <= 1e-9) & (s > self.s_heel + 1e-9)
        if m.any():
            T = self.sf.tangent_u(s[m], np.full(m.sum(), 0.002))
            P[m] = self.to_transom(P[m], T)
        return P

    # --- the planking -------------------------------------------------------------------------------------------------
    def strake_edges(self):
        n = self.b["strakes"]
        return np.linspace(0.0, 1.0, n + 1)

    def gerald(self, s_edge, U):
        """the share of a clinker land's step kept along its row (1 amidships): the laps are worked away to nothing
        over gerald_ft at the stem, and on the deadwood aft (a row landing on the transom keeps its step there)"""
        Lg = self.b.get("gerald_ft", 2.0) * FT
        L = float(self.sf.row_len(s_edge))
        g = smoothstep((1.0 - U) * L / Lg)
        if s_edge <= self.s_heel:
            g = g * smoothstep(U * L / Lg)
        return g

    def planking(self):
        """the shell: outside and inside surfaces (clinker: each strake's land stepped over the one below it, its lower
        edge showing outside and its upper edge inside), the ends on the transom; the top strake painted the band"""
        t, U = self.t, self.U
        e = self.strake_edges()
        n = len(e) - 1
        nu = len(U)
        paint = self.card["paint"]
        out_m, band_m, in_m = paint["outside"], paint["band"], paint["inside"]
        lam = (self.b.get("land_in", 0.0) * IN) / self.sf.girth(U) if self.clinker else np.zeros(nu)
        rows_o, rows_i = [], []                   # (s (nu,), offset (nu,), strake) per row
        for k in range(n):
            a, b_ = e[k], e[k + 1]
            G = self.gerald(a, U) if (self.clinker and k > 0) else np.zeros(nu)
            top = k == n - 1
            if not self.clinker:
                for s in (a, 0.5 * (a + b_)):
                    rows_o.append((np.full(nu, s), np.full(nu, t), k))
                    rows_i.append((np.full(nu, s), np.zeros(nu), k))
                if top:
                    rows_o.append((np.full(nu, 1.0), np.full(nu, t), k))
                    rows_i.append((np.full(nu, 1.0), np.zeros(nu), k))
                continue
            # outside: the step up from the strake below, its land, its ramp down to the next strake's land
            if k == 0:
                rows_o += [(np.full(nu, 0.0), np.full(nu, t), 0), (np.full(nu, 0.5 * b_), np.full(nu, t), 0)]
            else:
                rows_o += [(np.full(nu, a), t + t * G, k), (a + lam, t + t * G, k)]
            rows_o.append((np.full(nu, b_), np.full(nu, t), k))
            # inside: (above the strake below's upper edge) its ramp, then flat under the next strake's land
            if k == 0:
                rows_i += [(np.full(nu, 0.0), np.zeros(nu), 0), (np.full(nu, 0.5 * b_), np.zeros(nu), 0)]
            else:
                rows_i.append((a + lam, t * G, k))
            if top:
                rows_i.append((np.full(nu, 1.0), np.zeros(nu), k))
            else:
                rows_i += [(np.full(nu, b_), np.zeros(nu), k), (b_ + lam, np.zeros(nu), k)]
        for rows, side, lab in ((rows_o, 1, "planking_out"), (rows_i, -1, "planking_in")):
            S = np.stack([r[0] for r in rows])
            O = np.stack([r[1] for r in rows])
            P = self.offset_pts(S, np.broadcast_to(U, S.shape), O)
            V = P.reshape(-1, 3)
            F = grid_quads(len(rows), nu, flip=(side > 0))         # the outside facing out, the inside in
            M = []
            for r in range(len(rows) - 1):
                k = rows[r + 1][2]
                mat = in_m if side < 0 else (band_m if k == n - 1 else out_m)
                M += [mat] * (nu - 1)
            self.put(lab, V, F, M)
        self.plank_rows = (rows_o, rows_i)
        # the plank ends on the transom: each strake's end grain, from its inside to its outside
        sh = self.s_heel
        Vq, Fq = [], []
        for k in range(n):
            a, b_ = e[k], e[k + 1]
            l0 = float(np.interp(0.0, self.sf.u, self.sf.girth_cols))
            lm = (self.b.get("land_in", 0.0) * IN) / l0 if self.clinker else 0.0
            top = k == n - 1
            g = float(self.gerald(a, np.zeros(1))[0]) * t if (self.clinker and k > 0) else 0.0
            if not self.clinker:
                smp = [(a, 0.0, t), (b_, 0.0, t)]
            elif k == 0:
                smp = [(0.0, 0.0, t), (b_, 0.0, t), (b_ + lm, 0.0, t)]
            else:
                smp = [(a, g, t + g), (a + lm, g, t + g), (b_, 0.0, t)] + ([] if top else [(b_ + lm, 0.0, t)])
            for (s0, i0, o0), (s1, i1, o1) in zip(smp[:-1], smp[1:]):
                if s1 <= sh + 1e-9:
                    continue
                if s0 < sh:
                    f = (sh - s0) / (s1 - s0)
                    s0, i0, o0 = sh, i0 + f * (i1 - i0), o0 + f * (o1 - o0)
                Q = self.offset_pts([s0, s0, s1, s1], [0, 0, 0, 0], [i0, o0, o1, i1])
                base = sum(len(v) for v in Vq)
                Vq.append(Q)
                Fq.append((base, base + 1, base + 2, base + 3))
        if Vq:
            V = np.concatenate(Vq)
            # turned to face aft (out of the transom's plane)
            F = [f if np.cross(V[f[1]] - V[f[0]], V[f[3]] - V[f[0]]) @ self.tr_n > 0 else f[::-1] for f in Fq]
            self.put("plank_ends", V, F, [paint["outside"]] * len(F))

    def mirror(self):
        """everything built so far (the starboard half of her hull and fittings) mirrored to port"""
        mirror_mesh(self.mesh, 0)
        self.n_sym = len(self.mesh.V)

    # --- the backbone -------------------------------------------------------------------------------------------------
    def profile_lines(self):
        """the backbone in profile (x, z): the rabbet R from the transom's heel along the deadwood, keel and stem to the
        stem head's top; the outer edge O from the heel down the post's aft edge, along the keel's bottom and up the
        stem's fore edge, matched point by point to R in three runs (the deadwood and post, the keel, the forefoot and
        stem); half-widths for each"""
        ln, b = self.ln, self.b
        kb = ln.keel_bottom
        R = ln.rabbet.copy()
        i_af = len(ln.deadwood) - 1
        H = R[0]
        fe = ln.stem_fore[::-1].copy()                            # the stem's fore edge, from its foot up
        # the trace's foot runs along the keel's bottom (its points there out of order): the edge from where it leaves
        # the bottom, its first rise carried down to it
        k = int(np.nonzero(fe[:, 1] > kb + 0.25 * IN)[0][0])
        fe = fe[max(k, 1) - 1:]
        d = fe[1] - fe[0]
        fe[0] = [fe[1, 0] - d[0] * (fe[1, 1] - kb) / d[1] if d[1] > 1e-9 else fe[0, 0], kb]
        z_top = float(fe[-1, 1])
        # the rabbet carried on up from the head as the stem's after face to the stem head's top
        d = unit(R[-1] - R[-4])
        R = np.concatenate([R, [R[-1] + d * (z_top - R[-1][1]) / max(1e-6, d[1])]])
        # the post's aft edge from the heel down to the keel's bottom
        pt, pd = ln.post_top, ln.post_dir
        foot = pt + pd * (kb - pt[1]) / pd[1]
        n_a, n_b, n_c = 14, 12, 26
        Ra = resample(R[:i_af + 1], n_a)
        Oa = resample(np.array([H, foot, [R[i_af][0], kb]]), n_a)
        Rb = resample(R[i_af:i_af + 2], n_b)
        Ob = resample(np.array([[R[i_af][0], kb], [fe[0, 0], kb]]), n_b)
        Rc = resample(R[i_af + 1:], n_c)
        Oc = resample(fe, n_c)
        Rp = np.concatenate([Ra, Rb[1:], Rc[1:]])
        Op = np.concatenate([Oa, Ob[1:], Oc[1:]])
        self.keel_run = (float(R[i_af][0]), float(fe[0, 0]), float(kb))   # the straight keel: the deadwood's foot to the forefoot
        w_r = self.ln.hs + self.t
        kbs = b["keel_bottom_sided_in"] / 2 * IN
        sf = b["stem_face_in"] / 2 * IN
        # on the stem's fore edge the stem's face, blended in from the keel's bottom over its first foot of rise
        rise = np.clip((Op[:, 1] - kb) / (1.0 * FT), 0.0, 1.0)
        on_stem = (np.arange(len(Op)) >= n_a + n_b - 2)
        w_o = np.where(on_stem, kbs + (sf - kbs) * smoothstep(rise), kbs)
        return Rp, Op, w_r, w_o, z_top

    def inner_post_line(self):
        """the inner post's after face on the transom's inside, from the heel up to 1.5 in under the transom's top on
        the middle line: points (k, 3), its moulding forward (m) and half-siding"""
        b, ln = self.b, self.ln
        tt = b["transom_in"] * IN
        H = self.prof[0][0]
        z1 = float(self.transom_top_mid()[2]) - 1.5 * IN
        pt, pd = ln.post_top, ln.post_dir
        zs = np.linspace(H[1], z1, 6)
        P = np.array([[pt[0] + pd[0] * (z - pt[1]) / pd[1], 0.0, z] for z in zs])
        P = P - self.tr_n * tt                                    # its after face on the transom's inside
        dz = zs - P[:, 2]                                         # slid along the plane back to its height
        P[:, 0] += pd[0] * dz / pd[1]
        P[:, 2] = zs
        return P, b["keel_sided_in"] * IN, self.prof[2]

    def backbone(self):
        """the keel, deadwood, post and stem outside the rabbet (sided to the planks' outside there, tapering to the
        keel's bottom and the stem's face), the hog, deadwood and apron inside it (sided to the rabbet), and the post
        on up inside the transom to its top (whole: built across her middle line, after mirror())"""
        ln = self.ln
        paint = self.card["paint"]
        Rp, Op, w_r, w_o, z_top = self.prof
        self.put("keel_stem", *profile_solid(Op, Rp, w_o, w_r, paint["outside"]))
        V, F, M = strip_solid(Rp, self.hog_line, ln.hs, ln.hs, paint["inside"], mat_b=paint["inside"],
                              mat_caps=paint["inside"])
        self.put("hog", V, F, M)
        P, mo, w = self.inner_post_line()
        fwd = -self.tr_n
        V, F, M = bar(P, np.tile(fwd, (len(P), 1)), np.tile(EY, (len(P), 1)), 0.0, mo, -w, w, paint["inside"])
        self.put("inner_post", V, F, M)

    # --- the transom --------------------------------------------------------------------------------------------------
    def transom_top_mid(self):
        """the transom's top on the middle line: its corners' height and a crown"""
        C = self.ln.transom_edge[-1]
        crown = self.b.get("transom_crown_in", 1.5) * IN
        z = C[2] + crown
        return np.array([self.ln.post_top[0] + self.ln.post_dir[0] * (z - self.ln.post_top[1]) / self.ln.post_dir[1],
                         0.0, z])

    def transom(self):
        """the transom: its outer face in the plane through the post's aft edge, bounded by the planks' inside where
        they meet that plane (a clinker boat's lands stepped round it) and a crowned top; its inner face transom_in
        forward of it, bounded where the planks' inside meets that plane; the top edge between them"""
        b, sf = self.b, self.sf
        paint = self.card["paint"]
        tt = b["transom_in"] * IN
        # the planks' inside at the transom: the inside rows' (s, offset) at their after ends, from the heel up (the
        # planking's own edge there, so the two meet without a sliver; a plank is flat across its width)
        rows_i = self.plank_rows[1]
        pts = np.array([(float(r[0][0]), float(r[1][0])) for r in rows_i])
        sh = self.s_heel
        keep = pts[:, 0] > sh + 1e-9
        i = int(np.argmax(keep))
        if i > 0:
            (s0, o0), (s1, o1) = pts[i - 1], pts[i]
            f = (sh - s0) / max(1e-12, s1 - s0)
            pts = np.concatenate([[[sh, o0 + f * (o1 - o0)]], pts[keep]])
        S, O = pts[:, 0], pts[:, 1]
        E_out = self.offset_pts(S, np.zeros_like(S), O)
        # the inner plane's edge: where each of those lines along the planks' inside crosses it
        p_in = self.tr_p - self.tr_n * tt
        E_in = []
        for s_, o_ in zip(S, O):
            lo, hi = 0.0, 0.4
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                q = sf.at(s_, mid) + sf.normal(s_, mid) * o_
                if (q - p_in) @ self.tr_n > 0:
                    lo = mid
                else:
                    hi = mid
            E_in.append(sf.at(s_, 0.5 * (lo + hi)) + sf.normal(s_, 0.5 * (lo + hi)) * o_)
        E_in = np.array(E_in)
        top = self.transom_top_mid()
        up = np.array([self.tr_n[2], 0.0, -self.tr_n[0]])            # up the transom's plane
        for E, off, mat, lab in ((E_out, 0.0, paint["outside"], "transom_out"), (E_in, tt, paint["inside"],
                                                                                 "transom_in")):
            # the starboard half: up its edge from the heel, across the top to the middle line, down it
            tm = top - self.tr_n * off
            bm = E[0].copy()
            bm[1] = 0.0
            V = np.concatenate([E, [tm, bm]])
            uv = np.stack([V[:, 1], V @ up], -1)
            tris = loft.ear_clip(uv)
            nrm = np.zeros(3)
            for f in tris:
                nrm += np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
            want = self.tr_n if off == 0.0 else -self.tr_n
            if nrm @ want < 0:
                tris = [f[::-1] for f in tris]
            self.put(lab, V, tris, [mat] * len(tris))
        # the top edge: from the corner to the middle, outer to inner
        Q = np.array([E_out[-1], top, top - self.tr_n * tt, E_in[-1]])
        F = [(0, 1, 2, 3)]
        if np.cross(Q[1] - Q[0], Q[3] - Q[0]) @ EZ < 0:
            F = [(3, 2, 1, 0)]
        self.put("transom_top", Q, F, [paint["outside"]])

    # --- the layout the parts are built to ----------------------------------------------------------------------------
    def prep(self):
        """the backbone in profile and the hog's top, the frames' sizes, the floors' and bottom boards' heights, the
        thwarts (and which carry a mast), the rowlocks and the stern sheets"""
        b, fit, k = self.b, self.fit, self.k
        self.prof = self.profile_lines()
        Rp = self.prof[0]
        d_in = b.get("hog_in", b["keel_sided_in"] * 0.5) * IN
        T = unit(np.gradient(Rp, axis=0))
        Ri = Rp + d_in * np.stack([-T[:, 1], T[:, 0]], -1)
        Ri[-1, 1] = self.prof[4]
        self.hog_line, self.stem_top_z = Ri, self.prof[4]
        fr = b["frames"]
        self.m0, self.m1 = fr["moulded_in"][0] * IN, fr["moulded_in"][1] * IN
        self.sided, self.room = fr["sided_in"] * IN, fr["room_in"] * IN
        self.z_bb = fit["bottom_boards_z"] * k[2] if "bottom_boards_z" in fit else b["bottom_boards_z_ft"] * FT
        self.bb_w, self.bb_t = b["bottom_boards_in"][0] * IN, b["bottom_boards_in"][1] * IN
        self.z_floor = self.z_bb - self.bb_t
        self.tw, self.tt = b["thwart_in"][0] * IN, b["thwart_in"][1] * IN
        self.tbs = fit["thwart_below_sheer"] * k[2]
        if "thwarts_x" in fit:
            xs = [x * k[0] for x in fit["thwarts_x"]]
            mast_at = {nm: int(np.argmin([abs(x - xm * k[0]) for x in xs])) for nm, xm in fit["mast_thwarts"].items()}
            mast_d = {nm: d * k[1] for nm, d in fit["masts_diam"].items()}
        else:
            room = b["thwart_room_ft"] * FT
            xs = [b["stern_sheets_ft"] * FT + (i + b.get("first_thwart_room", 0.75)) * room
                  for i in range(b["rowing_thwarts"])]
            mast_at = dict(b.get("mast_thwarts", {}))
            mast_d = {m["name"]: m["diam_in"] * IN for m in b["masts"]}
        self.thwarts = []
        for i, x in enumerate(xs):
            mast = next((nm for nm, j in mast_at.items() if j == i), None)
            self.thwarts.append({"i": i, "x": float(x), "mast": mast, "mast_d": mast_d.get(mast) if mast else None})
        aft = b.get("rowlock_aft_in", 11.0) * IN
        self.rowlocks = []
        for th in self.thwarts:
            x = th["x"] - 0.5 * self.tw - aft
            if b.get("rowlock_sides", "both") == "alternate":
                self.rowlocks.append((x, -1 if th["i"] % 2 == 0 else 1))
            else:
                self.rowlocks += [(x, 1), (x, -1)]
        if "stern_sheets_to_x" in fit:
            self.x_ss, self.ss_below = fit["stern_sheets_to_x"] * k[0], fit["stern_sheets_below_sheer"] * k[2]
        else:
            self.x_ss, self.ss_below = b["stern_sheets_ft"] * FT, b["stern_sheets_below_sheer_ft"] * FT
        self.ss_t, self.ss_w = b["stern_sheets_in"] * IN, b["stern_bench_in"] * IN
        self.tr_t = b["transom_in"] * IN
        self.iw_d, self.iw_t = b["inwale_in"][0] * IN, b["inwale_in"][1] * IN
        self.cap_w, self.cap_t = b["capping_in"][0] * IN, b["capping_in"][1] * IN
        self.ri_d, self.ri_t = b["rising_in"][0] * IN, b["rising_in"][1] * IN
        self._side, self._frame = {}, {}

    def sheer(self, x):
        """the sheer's height at x (the lofted surface's top row)"""
        return float(self.sf.at(1.0, self.u_at(1.0, x))[2])

    def x_on_plane(self, z, off=0.0):
        """x on the transom's plane (off forward of its outer face) at height z"""
        n, p = self.tr_n, self.tr_p - self.tr_n * off
        return float(p[0] - (z - p[2]) * n[2] / n[0])

    def onto_plane(self, sec, off):
        """a section's points (k, 3) slid along x onto the transom's plane off forward of its outer face"""
        sec = np.array(sec, float)
        sec[:, 0] = [self.x_on_plane(z, off) for z in sec[:, 2]]
        return sec

    # --- sections across her ------------------------------------------------------------------------------------------
    def s_min_at(self, x):
        """the lowest row (girth fraction) that reaches the plane x: 0 between the deadwood's and the forefoot's feet,
        else where the plane meets the rabbet up the deadwood (or the transom's edge) or the stem; None past her ends"""
        G = self.sf.G
        if not (G[-1, 0, 0] < x < G[-1, -1, 0]):
            return None
        if self.ln.after_foot[0] <= x <= self.ln.fore_foot[0]:
            return 0.0
        aft = x < self.ln.after_foot[0]
        lo, hi = 0.0, 1.0
        for _ in range(44):
            mid = 0.5 * (lo + hi)
            xe = float(self.sf.at(mid, 0.0 if aft else 1.0)[0])
            if (xe <= x) if aft else (xe >= x):
                hi = mid
            else:
                lo = mid
        return hi

    def u_at(self, s, x):
        """u where the (bilinear) row s reaches x"""
        sf = self.sf
        t = float(np.clip(s, 0.0, 1.0)) * (sf.ns - 1)
        i = min(int(t), sf.ns - 2)
        f = t - i
        xr = (1.0 - f) * sf.G[i, :, 0] + f * sf.G[i + 1, :, 0]
        return float(np.interp(x, xr, sf.u))

    def section(self, x, n=24, s_lo=None):
        """the moulded section in the plane x from its lowest row (or s_lo) up to the sheer: s (n,), points (n, 3)"""
        s0 = self.s_min_at(x) if s_lo is None else s_lo
        if s0 is None:
            return None, None
        S = np.linspace(s0, 1.0, n)
        P = self.sf.at(S, np.array([self.u_at(s, x) for s in S]))
        P[:, 0] = x
        return S, P

    def moulded(self, s):
        """the frames' moulding at girth fraction s (heel to head)"""
        return self.m0 + (self.m1 - self.m0) * np.clip(s, 0.0, 1.0)

    def side_lines(self, x, n=24):
        """the moulded line and the frames' inside in the plane x, (y, z) from her lowest row there up to the sheer:
        (s, outer, inner), the inside cut level at the sheer; or None past her ends"""
        key = round(float(x), 7)
        if key not in self._side:
            S, P = self.section(x, n=n)
            if S is None or S[0] > 0.97:
                self._side[key] = None
            else:
                Q = P[:, 1:]
                I = offset2(Q, self.moulded(S))
                a, b_ = I[-2], I[-1]
                if abs(b_[1] - a[1]) > 1e-9:
                    I[-1] = a + (Q[-1, 1] - a[1]) / (b_[1] - a[1]) * (b_ - a)
                self._side[key] = (S, Q, I)
        return self._side[key]

    def hog_top(self, x):
        """the top of the hog (the deadwood's, the apron's) on the middle line at x, or None"""
        R = self.hog_line
        z = None
        for a, b in zip(R[:-1], R[1:]):
            if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
                zz = float(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
                z = zz if z is None else max(z, zz)
        return z

    def frame_lines(self, x, n=14):
        """a frame's outside and inside in the plane x (starboard half, from the middle line up to the sheer), (y, z):
        the outside on the moulded line, bridged straight across the top of the hog; the inside its moulding in from
        that, the head cut level at the sheer and the floor's top held up to the bottom boards' underside; or None"""
        key = round(float(x), 7)
        if key in self._frame:
            return self._frame[key]
        out = None
        zh = self.hog_top(x)
        S, P = self.section(x, n=64)
        if zh is not None and S is not None and zh < P[-1, 2] - 0.05:
            s_h = float(S[0]) if zh <= P[0, 2] else float(np.interp(zh, P[:, 2], S))
            S2, P2 = self.section(x, n=n, s_lo=s_h)
            Q = np.concatenate([[[0.0, zh]], P2[:, 1:]])
            if zh > P2[0, 2]:
                Q[1, 1] = zh
            m = np.concatenate([[self.m0], self.moulded(S2)])
            I = offset2(Q, m)
            a, b_ = I[-2], I[-1]
            if abs(b_[1] - a[1]) > 1e-9:
                I[-1] = a + (Q[-1, 1] - a[1]) / (b_[1] - a[1]) * (b_ - a)
            I[:, 1] = np.maximum(I[:, 1], self.z_floor)
            out = (Q, I, zh)
        self._frame[key] = out
        return out

    def inside_y(self, x, z):
        """the frames' inside's half-breadth at height z in the plane x (on her side), or None"""
        sl = self.side_lines(x)
        return None if sl is None else y_at_z(sl[2], z)

    def stringer(self, xs, z_top, depth, thick):
        """a stringer along the frames' inside (a rising, an inwale): at each x its outer face on the frames' inside
        from z_top(x) down depth, thick in from that face, its top and bottom level: sections [outer bottom, outer top,
        inner top, inner bottom] (4, 3), only where it fits (a run of them)"""
        out = []
        for x in xs:
            zt = float(z_top(x))
            zb = zt - depth
            yt, yb = self.inside_y(x, zt), self.inside_y(x, zb)
            if yt is None or yb is None:
                if out:
                    break
                continue
            e = unit(np.array([yt - yb, zt - zb]))
            p0 = np.array([yb, zb]) + thick * np.array([-e[1], e[0]])
            it = p0 + (zt - p0[1]) / e[1] * e
            ib = p0 + (zb - p0[1]) / e[1] * e
            out.append(np.array([[x, yb, zb], [x, yt, zt], [x, it[0], zt], [x, ib[0], zb]]))
        return out

    # --- the frames, keelson and floors ---------------------------------------------------------------------------------
    def frame_xs(self):
        """the frames' stations: room_in apart about her middle, from clear of the inner post aft to where her floor
        rises past 0.6 of her sheer forward"""
        G = self.sf.G
        h = 0.5 * self.sided
        P, mo, w = self.inner_post_line()
        Pf = P - self.tr_n * mo
        x_mid = 0.5 * (G[-1, 0, 0] + G[-1, -1, 0])
        out = []
        for j in range(-80, 81):
            x = x_mid + j * self.room
            A, B = self.frame_lines(x - h), self.frame_lines(x + h)
            if A is None or B is None:
                continue
            zh = max(A[2], B[2])
            if zh > 0.6 * self.sheer(x):
                continue
            # clear of the inner post's fore face (and so of the transom) by half an inch at every height
            if x - h < float(np.interp(min(A[2], B[2]), Pf[:, 2], Pf[:, 0])) + 0.5 * IN:
                continue
            out.append(x)
        return out

    def frames(self):
        """the frames (timbers), each one piece across her from head to head: room_in apart, sided_in fore and aft and
        moulded_in deep (heel to head), each face cut to the moulded section in its own plane (bevelled near her
        ends), bridged across the hog and floored up flat under the bottom boards"""
        paint = self.card["paint"]
        h = 0.5 * self.sided
        self.frame_x = self.frame_xs()

        def full(L):
            return np.concatenate([L[:0:-1] * [-1.0, 1.0], L])
        for x in self.frame_x:
            A, B = self.frame_lines(x - h), self.frame_lines(x + h)
            oa, ia, ob, ib = full(A[0]), full(A[1]), full(B[0]), full(B[1])
            secs = [np.array([[x - h, *oa[j]], [x + h, *ob[j]], [x + h, *ib[j]], [x - h, *ia[j]]]) for j in range(len(oa))]
            self.put("frames", *sweep_ends(secs, paint["inside"]))

    def floor_top(self, x):
        """the floors' (frames') top on the middle line at x, or None"""
        fl = self.frame_lines(x)
        return None if fl is None else float(fl[1][0, 1])

    def keelson(self):
        """the keelson over the floors on the middle line, from the aftmost frame to the foremost, and the mast steps
        on it"""
        b, paint = self.b, self.card["paint"]
        ks, kd = b["keelson_in"][0] * IN, b["keelson_in"][1] * IN
        h = 0.5 * self.sided
        x0, x1 = self.frame_x[0] - h, self.frame_x[-1] + h
        xs = np.unique(np.concatenate([np.arange(x0, x1, 0.12), [x1], [x - h for x in self.frame_x],
                                       [x + h for x in self.frame_x]]))
        # it lies on the floors: straight from one floor's top to the next
        zf = np.array([self.floor_top(x) for x in self.frame_x])
        zb = np.interp(xs, self.frame_x, zf)
        secs = [np.array([[x, -ks / 2, z], [x, ks / 2, z], [x, ks / 2, z + kd], [x, -ks / 2, z + kd]])
                for x, z in zip(xs, zb)]
        self.put("keelson", *sweep_ends(secs, paint["inside"]))
        self.keelson_top = (xs, zb + kd)
        self.ks = ks
        # the mast steps: a block on the keelson under each mast thwart's notch, a mortise in its top
        for th in self.thwarts:
            if not th["mast"]:
                continue
            d = th["mast_d"]
            x = th["x"] - 0.5 * self.tw
            z0 = float(np.interp(x, xs, zb + kd))
            L, hgt, m = 1.6 * d, 0.45 * d, 0.32 * d
            mw = min(m, ks / 2 - 0.75 * IN)                       # the mortise's half width: a cheek either side
            for c, half in (((x - 0.5 * (L / 2 + m), 0.0, z0 + hgt / 2), (0.5 * (L / 2 - m), ks / 2, hgt / 2)),
                            ((x + 0.5 * (L / 2 + m), 0.0, z0 + hgt / 2), (0.5 * (L / 2 - m), ks / 2, hgt / 2)),
                            ((x, 0.5 * (ks / 2 + mw), z0 + hgt / 2), (m, 0.5 * (ks / 2 - mw), hgt / 2)),
                            ((x, -0.5 * (ks / 2 + mw), z0 + hgt / 2), (m, 0.5 * (ks / 2 - mw), hgt / 2))):
                self.put("mast_steps", *box(c, half, paint["inside"]))

    # --- the stringers: risings, inwales ------------------------------------------------------------------------------
    def thwart_z(self, th):
        """a thwart's underside and top (its underside on the risings at the higher of its edges)"""
        xa, xb = th["x"] - 0.5 * self.tw, th["x"] + 0.5 * self.tw
        zb = max(self.sheer(xa), self.sheer(xb)) - self.tbs - self.tt
        return zb, zb + self.tt

    def risings(self):
        """the risings the thwarts rest on (from the stern sheets to the foremost thwart and a little past), and the
        stern sheets' risings under the stern benches (from the transom to the stern sheets' fore edge)"""
        paint = self.card["paint"]
        x1 = self.thwarts[-1]["x"] + 0.5 * self.tw + 0.3
        xs = np.linspace(self.x_ss, x1, max(8, int((x1 - self.x_ss) / 0.12)))
        secs = self.stringer(xs, lambda x: self.sheer(x) - self.tbs - self.tt, self.ri_d, self.ri_t)
        self.put("risings", *sweep_ends(secs, paint["inside"]))
        # the stern sheets' rising, its after end on the transom's inside
        z_of = lambda x: self.sheer(x) - self.ss_below - self.ss_t          # noqa: E731
        x0 = self.x_on_plane(z_of(0.0) - self.ri_d, self.tr_t) + 0.002
        xs = np.linspace(x0, self.x_ss, max(6, int((self.x_ss - x0) / 0.12)))
        secs = self.stringer(xs, z_of, self.ri_d, self.ri_t)
        secs[0] = self.onto_plane(secs[0], self.tr_t)
        self.put("stern_risings", *sweep_ends(secs, paint["inside"]))

    def inwales(self):
        """the inwales along the frames' heads under the cappings, from the transom's inside forward until they come
        within the breasthook's reach of her middle line"""
        paint = self.card["paint"]
        G = self.sf.G
        zt = self.sheer
        x0 = self.x_on_plane(self.sheer(0.0) - self.iw_d, self.tr_t) + 0.002
        x1 = float(G[-1, -1, 0]) - 0.01
        xs = np.concatenate([np.linspace(x0, x1 - 1.2, 50), np.linspace(x1 - 1.2, x1, 40)[1:]])
        secs = self.stringer(xs, zt, self.iw_d, self.iw_t)
        # forward: stop where the inner face comes within the stem's half-breadth of her middle
        w = self.prof[2]
        keep = [s for s in secs if s[2, 1] > w + 0.25 * IN and s[3, 1] > w + 0.25 * IN]
        secs = keep
        secs[0] = self.onto_plane(secs[0], self.tr_t)
        self.iw_secs = secs
        self.put("inwales", *sweep_ends(secs, paint["inside"]))

    def iw_inner(self, x):
        """the inwale's inner face's top edge's half-breadth at x"""
        S = np.array([s[2] for s in self.iw_secs])
        return float(np.interp(x, S[:, 0], S[:, 1]))

    # --- the gunwale: cappings and rubbing strakes ---------------------------------------------------------------------
    def cap_lines(self, x):
        """the capping's inner and outer edges' half-breadths at x: over the inwale's inner face and a lip outside the
        planking"""
        sl = self.side_lines(x)
        u = self.u_at(1.0, x)
        P = self.sf.at(1.0, u) + self.sf.normal(1.0, u) * self.t
        y_out_plank = float(P[1])
        y_in = self.iw_inner(x) if self.iw_secs[0][2, 0] <= x <= self.iw_secs[-1][2, 0] else None
        if y_in is None and sl is not None:
            y_in = float(sl[2][-1, 0]) - self.iw_t
        if y_in is None:
            y_in = self.prof[2]                     # at the stem head: from the stem's side out
        lip = max(0.125 * IN, self.cap_w - (self.t + self.m1 + self.iw_t))
        return y_in, y_out_plank + lip

    def cappings(self):
        """the cappings over the sheer strake, the frames' heads and the inwale, from the transom's face to the stem
        head's side (whose half-breadth they end on)"""
        paint = self.card["paint"]
        G = self.sf.G
        w = self.prof[2]
        xa = float(G[-1, 0, 0]) + 0.004
        xb = float(G[-1, -1, 0])
        xs = np.concatenate([np.linspace(xa, xb - 1.2, 56), np.linspace(xb - 1.2, xb, 30)[1:]])
        secs = []
        for x in xs:
            yi, yo = self.cap_lines(x)
            if yi is None:
                continue
            yi, yo = max(yi, w), max(yo, w + 0.125 * IN)
            z = self.sheer(x)
            secs.append(np.array([[x, yi, z], [x, yo, z], [x, yo, z + self.cap_t], [x, yi, z + self.cap_t]]))
        secs[0] = self.onto_plane(secs[0], 0.0)
        self.cap_secs = secs
        self.put("cappings", *sweep_ends(secs, paint["bright"]))

    def rubbing(self):
        """the rubbing strakes: proud of the planking just under the capping (a launch) or on the draught's line (a
        cutter, gig), from the transom's face to the stem, thinned toward the stem"""
        b, paint = self.b, self.card["paint"]
        rd, rt = b["rubbing_in"][0] * IN, b["rubbing_in"][1] * IN
        G = self.sf.G
        w = self.prof[2]
        rub = self.lc.get("rubbing_strake")
        if rub is not None:
            R = np.asarray(rub, float) * self.k[[0, 2]]
            z_top = lambda x: float(np.interp(x, R[:, 0], R[:, 1]))     # noqa: E731
        else:
            z_top = lambda x: self.sheer(x)                               # noqa: E731
        o = 2.0 * self.t if self.clinker else self.t                      # bearing on the lands
        xa, xb = float(G[-1, 0, 0]) + 0.004, float(G[-1, -1, 0])
        xs = np.concatenate([np.linspace(xa, xb - 1.0, 56), np.linspace(xb - 1.0, xb, 26)[1:]])
        secs = []
        for x in xs:
            S, P = self.section(x, n=48)
            Q = None if S is None else level_top(offset2(P[:, 1:], -o), P[-1, 2])
            zt = z_top(x)
            zb = zt - rd
            yt, yb = (None, None) if Q is None else (y_at_z(Q, zt), y_at_z(Q, zb))
            if yt is None or yb is None:
                if secs:
                    break
                continue
            # thinned over its last half metre to the stem
            th = rt * (1.0 - 0.6 * smoothstep((x - (xb - 0.5)) / 0.5))
            yt, yb = max(yt, w), max(yb, w)
            yo = max(yt, yb) + th
            secs.append(np.array([[x, yb, zb], [x, yt, zt], [x, yo, zt], [x, yo, zb]]))
        secs[0] = self.onto_plane(secs[0], 0.0)
        self.put("rubbing", *sweep_ends(secs, paint["outside"]))

    # --- thwarts and knees --------------------------------------------------------------------------------------------
    def thwart_outline(self, th):
        """a thwart in plan (x, y), across her from the frames' inside to the frames' inside at its underside; a mast
        thwart's after edge notched for the mast"""
        zb, zt = self.thwart_z(th)
        xa, xb = th["x"] - 0.5 * self.tw, th["x"] + 0.5 * self.tw
        ya, yb = self.inside_y(xa, zb), self.inside_y(xb, zb)
        P = [(xa, -ya), (xb, -yb), (xb, yb), (xa, ya)]
        if th["mast"]:
            r = 0.5 * th["mast_d"] + 0.25 * IN
            P += [(xa + r * math.cos(a), r * math.sin(a)) for a in np.linspace(0.5 * math.pi, -0.5 * math.pi, 13)]
        return np.array(P), zb, zt

    def thwart_parts(self):
        """the thwarts on the risings (whole: across her middle line), each mast thwart with its iron clamp round the
        notch"""
        paint = self.card["paint"]
        for th in self.thwarts:
            P, zb, zt = self.thwart_outline(th)
            th["z"] = (zb, zt)
            self.put("thwarts", *plan_prism(P, zt, zb, paint["bright"]))
            if not th["mast"]:
                continue
            # the clamp: an iron half band round the notch's open (after) side, its ends turned forward as tabs
            # bolted on the thwart's top
            r = 0.5 * th["mast_d"] + 0.25 * IN
            xa = th["x"] - 0.5 * self.tw
            it, ih = 0.375 * IN, 1.75 * IN
            z0, z1 = zt - ih + 0.375 * IN, zt + 0.375 * IN
            secs = []
            for a in np.linspace(0.5 * math.pi, 1.5 * math.pi, 11):
                d = np.array([math.cos(a), math.sin(a), 0.0])
                c = np.array([xa, 0.0, 0.0])
                secs.append(np.array([c + r * d + [0, 0, z0], c + (r + it) * d + [0, 0, z0],
                                      c + (r + it) * d + [0, 0, z1], c + r * d + [0, 0, z1]]))
            self.put("mast_clamps", *sweep_ends(secs, paint["iron"]))
            for sgn in (1.0, -1.0):
                c = (xa + 1.5 * IN, sgn * (r + 0.5 * it), zt + 0.1875 * IN)
                self.put("mast_clamps", *box(c, (1.5 * IN, 0.75 * IN, 0.1875 * IN), paint["iron"]))

    def knees(self):
        """a hanging knee on each thwart's end (the starboard ones; mirrored): its arm along the thwart's top, its
        body up the frames' inside to the inwale, its throat cut in a curve"""
        b, paint = self.b, self.card["paint"]
        kt, arm = b["knee_in"][0] * IN, b["knee_in"][1] * IN
        toe = max(0.75 * IN, 0.45 * kt)
        for th in self.thwarts:
            x = th["x"]
            zb, zt = self.thwart_z(th)
            z_iw = self.sheer(x) - self.iw_d
            sl = self.side_lines(x)
            if sl is None:
                continue
            I = sl[2]
            ys, yi = y_at_z(I, zt), y_at_z(I, z_iw)
            if ys is None or yi is None or z_iw - zt < 2 * toe:
                continue
            arm_x = min(arm, 0.45 * ys)
            p2 = np.array([ys - arm_x, zt + toe])
            p3 = np.array([yi - toe, z_iw])
            c = np.array([yi - toe - 0.15 * arm_x, zt + toe + 0.15 * (z_iw - zt)])
            t = np.linspace(0.0, 1.0, 9)[:, None]
            throat = (1 - t) ** 2 * p2 + 2 * t * (1 - t) * c + t ** 2 * p3
            side = [p for p in I[::-1] if zt < p[1] < z_iw]
            poly = np.concatenate([[[ys, zt], [ys - arm_x, zt]], throat, [[yi, z_iw]], side]) if side else \
                np.concatenate([[[ys, zt], [ys - arm_x, zt]], throat, [[yi, z_iw]]])
            V, F, M = extrude(poly, lambda uv, w: np.stack([np.full(len(uv), x + w), uv[:, 0], uv[:, 1]], -1),
                              -0.5 * kt, 0.5 * kt, paint["bright"])
            self.put("knees", V, F, M)

    def quarter_knees(self):
        """a quarter knee in each corner of the transom under the capping (the starboard one; mirrored): one arm along
        the transom's inside, the other along the inwale, its throat curved"""
        b, paint = self.b, self.card["paint"]
        L, dep = b["quarter_knee_in"][0] * IN, b["quarter_knee_in"][1] * IN
        toe = 1.25 * IN
        z_mid = self.sheer(0.0) - 0.5 * dep
        x0 = self.x_on_plane(z_mid - 0.5 * dep, self.tr_t) + 0.001
        y0 = self.iw_inner(x0)
        x1 = x0 + L
        y1 = self.iw_inner(x1)
        a2, b2 = np.array([x0 + toe, y0 - L]), np.array([x1, y1 - toe])
        c = np.array([x0 + toe + 0.2 * L, y1 - toe - 0.2 * L])
        t = np.linspace(0.0, 1.0, 9)[:, None]
        throat = (1 - t) ** 2 * a2 + 2 * t * (1 - t) * c + t ** 2 * b2
        side = [(x, self.iw_inner(x)) for x in np.linspace(x1, x0, 6)[1:-1]]
        P = np.concatenate([[[x0, y0], [x0, y0 - L]], throat, [[x1, y1]], side])
        zt = np.array([self.sheer(x) for x in P[:, 0]])
        self.put("quarter_knees", *plan_prism(P, zt, zt - dep, paint["bright"]))

    def breasthook(self):
        """the breasthook in her bow under the cappings (whole): between the inwales and forward of them between the
        frames' heads to the apron, its after edge curved"""
        b, paint = self.b, self.card["paint"]
        L, dep = b["breasthook_in"][0] * IN, b["breasthook_in"][1] * IN
        S = np.array([s[2] for s in self.iw_secs])
        x_ie = float(S[-1, 0])
        # forward of the inwales' ends: the frames' heads' inside, until it meets the apron
        w = self.ln.hs
        fwd = []
        for x in np.linspace(x_ie, x_ie + 0.5, 26):
            sl = self.side_lines(x)
            if sl is None:
                break
            y = float(sl[2][-1, 0])
            if y <= w + 0.1 * IN:
                break
            fwd.append((x, y))
        x_bh = x_ie - L
        side = [(x, self.iw_inner(x)) for x in np.linspace(x_bh, x_ie, 7)] + fwd
        side = np.array(side)
        y_bh = float(side[0, 1])
        # the after edge: a curve bowed forward, from port to starboard
        t = np.linspace(-1.0, 1.0, 11)[1:-1]
        aft = np.stack([x_bh + 0.35 * L * (1.0 - t ** 2), y_bh * t], -1)
        P = np.concatenate([side, side[::-1] * [1.0, -1.0], aft])
        zt = np.array([self.sheer(x) for x in P[:, 0]])
        self.put("breasthook", *plan_prism(P, zt, zt - dep, paint["bright"]))
        self.bh = (x_bh, float(side[-1, 0]))

    # --- the stern sheets and bottom boards ---------------------------------------------------------------------------
    def bench_y(self, x):
        """the stern benches' outer and inner edges' half-breadths at x (the outer on the frames' inside at their
        underside)"""
        zt = self.sheer(x) - self.ss_below
        yo = self.inside_y(x, zt - self.ss_t)
        return (None, None) if yo is None else (yo, yo - self.ss_w)

    def stern_benches(self):
        """the stern benches round the stern sheets: one up each side (the starboard one; mirrored) from the transom
        to the stern sheets' fore edge, on the stern risings"""
        paint = self.card["paint"]
        z_of = lambda x: self.sheer(x) - self.ss_below                       # noqa: E731
        x0 = self.x_on_plane(z_of(0.0) - self.ss_t, self.tr_t) + 0.002
        secs = []
        for x in np.linspace(x0, self.x_ss, max(6, int((self.x_ss - x0) / 0.1))):
            yo, yi = self.bench_y(x)
            if yo is None:
                continue
            zt = z_of(x)
            secs.append(np.array([[x, yi, zt - self.ss_t], [x, yo, zt - self.ss_t], [x, yo, zt], [x, yi, zt]]))
        secs[0] = self.onto_plane(secs[0], self.tr_t)
        self.put("stern_benches", *sweep_ends(secs, paint["bright"]))
        self.x_bench0 = x0

    def transom_bench(self):
        """the bench across the transom between the side benches (whole), notched round the inner post"""
        paint = self.card["paint"]
        x0 = self.x_bench0
        x1 = x0 + self.ss_w
        P, mo, w = self.inner_post_line()
        Pf = P - self.tr_n * mo
        z_b = self.sheer(x0) - self.ss_below - self.ss_t
        x_pf = float(np.interp(z_b, Pf[:, 2], Pf[:, 0])) + 0.25 * IN
        wn = w + 0.25 * IN
        e0, e1 = self.bench_y(x0)[1], self.bench_y(x1)[1]
        Q = [(x0, -e0), (x1, -e1), (x1, e1), (x0, e0)]
        if x_pf < x1 - 0.5 * IN:
            Q += [(x0, wn), (x_pf, wn), (x_pf, -wn), (x0, -wn)]
        Q = np.array(Q)
        zt = np.array([self.sheer(x) - self.ss_below for x in Q[:, 0]])
        self.put("transom_bench", *plan_prism(Q, zt, zt - self.ss_t, paint["bright"]))

    def bottom_boards(self):
        """the bottom boards on the floors either side of the keelson (the starboard ones; mirrored): boards
        bottom_boards_in wide with a quarter inch between them, the outermost cut to the frames' inside, over the run
        of her where the floors come up flat to their underside"""
        paint = self.card["paint"]
        G = self.sf.G
        xs = np.arange(float(G[-1, 0, 0]) + 0.05, float(G[-1, -1, 0]) - 0.05, 0.05)
        ok = []
        for x in xs:
            fl = self.frame_lines(x)
            ok.append(fl is not None and fl[2] + self.m0 <= self.z_floor - 0.25 * IN)
        ok = np.array(ok)
        idx = np.nonzero(ok)[0]
        if not len(idx):
            return
        x0, x1 = float(xs[idx[0]]), float(xs[idx[-1]])
        gap = 0.25 * IN
        y_k = 0.5 * self.b["keelson_in"][0] * IN + gap
        X = np.linspace(x0, x1, max(8, int((x1 - x0) / 0.1)))
        ylim = np.array([(self.inside_y(x, self.z_floor) or 0.0) - gap for x in X])
        zf, zt = self.z_floor, self.z_bb
        i = 0
        while True:
            y0 = y_k + i * (self.bb_w + gap)
            y1 = y0 + self.bb_w
            if y0 + 1.5 * IN > ylim.max():
                break
            yc = np.minimum(y1, ylim)
            good = np.nonzero(yc - y0 >= 1.5 * IN)[0]
            if len(good) >= 2:
                a, b_ = good[0], good[-1]
                secs = [np.array([[X[j], y0, zf], [X[j], yc[j], zf], [X[j], yc[j], zt], [X[j], y0, zt]])
                        for j in range(a, b_ + 1)]
                self.put("bottom_boards", *sweep_ends(secs, paint["inside"]))
            i += 1
        self.bb_x = (x0, x1)

    # --- rowlocks, washstrake, a launch's fittings --------------------------------------------------------------------
    def cap_at(self, x):
        """the capping at x: its inner and outer edges' half-breadths and its top"""
        C = np.array([[s[0, 0], s[0, 1], s[1, 1], s[2, 2]] for s in self.cap_secs])
        return tuple(float(np.interp(x, C[:, 0], C[:, j])) for j in (1, 2, 3))

    def washstrake(self):
        """a cutter's washstrake (the starboard one; mirrored): a plank standing on the capping from abaft the
        aftmost rowlock to the stem, its top on the draught's line, a rowlock notch cut in it over each rowlock"""
        b, paint = self.b, self.card["paint"]
        if "washstrake_ft" not in b:
            return
        wt = b["washstrake_thick_in"] * IN
        nw, nd = b["notch_in"][0] * IN, b["notch_in"][1] * IN
        R = np.asarray(self.lc["washstrake_top"], float) * self.k[[0, 2]]
        dz0 = float(R[0, 1]) - self.sheer(float(R[0, 0]))
        w = self.prof[2]

        def z_top(x):
            return float(np.interp(x, R[:, 0], R[:, 1])) if x >= R[0, 0] else self.sheer(x) + dz0

        def y_o(x):
            return self.cap_at(x)[1] - 0.25 * IN
        xn = sorted(x for x, sd in self.rowlocks if sd > 0)
        x0 = xn[0] - 0.5 * nw - 1.0 * FT
        G = self.sf.G
        xs = np.linspace(x0, float(G[-1, -1, 0]), 400)
        dy = np.gradient(np.array([y_o(x) for x in xs]), xs)
        x1 = next(x for x, d in zip(xs, dy) if y_o(x) - wt * math.hypot(1.0, d) <= w + 0.25 * IN)

        def th_y(x):
            d = float(np.interp(x, xs, dy))
            return wt * math.hypot(1.0, d)
        # the outline in (x, z): along its foot on the capping, up its fore end, back along its top with the notches,
        # its after end sweeping down in a quarter round
        L_end = 0.35
        X = np.linspace(x0, x1, int((x1 - x0) / 0.05) + 2)
        foot = [(x, self.cap_at(x)[2]) for x in X]
        top = []
        for x in X[::-1]:
            if any(abs(x - c) <= 0.5 * nw + 0.01 for c in xn):
                continue
            h = z_top(x) - self.cap_at(x)[2]
            f = 1.0 if x > x0 + L_end else 0.12 + 0.88 * math.sin(0.5 * math.pi * (x - x0) / L_end)
            top.append((x, self.cap_at(x)[2] + h * f))
        for c in xn:
            zt = z_top(c)
            pts = [(c + 0.5 * nw, zt), (c + 0.5 * nw, zt - nd), (c - 0.5 * nw, zt - nd), (c - 0.5 * nw, zt)]
            i = next(j for j, p in enumerate(top) if p[0] < c)
            top[i:i] = pts
        P = np.array(foot + top)

        def to3d(uv, wv):
            return np.stack([uv[:, 0], np.array([y_o(x) - wv * th_y(x) for x in uv[:, 0]]), uv[:, 1]], -1)
        V, F, M = extrude(P, to3d, 0.0, 1.0, paint["bright"])
        nt = (len(F) - len(P)) // 2
        M = [paint["inside"]] * nt + [paint["band"]] * nt + [paint["bright"]] * len(P)
        self.put("washstrake", V, F, M)
        self.wash = (x0, x1, z_top)

    def thole_pins(self):
        """the thole pins (whole: each rowlock's side): a pair on the capping over each rowlock, the oar's loom between
        them"""
        b, paint = self.b, self.card["paint"]
        if b.get("rowlocks") != "thole_pins":
            return
        d, hgt = b["thole_in"][0] * IN, b["thole_in"][1] * IN
        gap = b.get("thole_gap_in", 4.0) * IN
        for x, sd in self.rowlocks:
            for dx in (-0.5 * (gap + d), 0.5 * (gap + d)):
                yi, yo, zc = self.cap_at(x + dx)
                y = sd * 0.5 * (yi + yo)
                P0, P1 = np.array([x + dx, y, zc - 0.5 * IN]), np.array([x + dx, y, zc + hgt])
                self.put("thole_pins", *cylinder(P0, P1, 0.5 * d, paint["bright"], n=8, r1=0.42 * d))

    def sling_plates(self):
        """a launch's sling plates (the starboard ones; mirrored): an iron strap down her side under the rubbing strake
        at each, an eyebolt's ring on the capping over it for the slings"""
        b, paint = self.b, self.card["paint"]
        if not b.get("sling_plates"):
            return
        rd = b["rubbing_in"][0] * IN
        sw, st, L = 1.25 * IN, 0.375 * IN, 1.5 * FT
        for xp in self.fit.get("sling_plates_x", []):
            x = xp * self.k[0]
            S, P = self.section(x, n=48)
            Q = level_top(offset2(P[:, 1:], -self.t), P[-1, 2])
            zt = self.sheer(x) - rd
            zs = np.linspace(zt - L, zt, 7)
            ys = np.array([y_at_z(Q, z) for z in zs])
            secs = []
            for y, z in zip(ys, zs):
                secs.append(np.array([[x - sw, y, z], [x + sw, y, z], [x + sw, y + st, z], [x - sw, y + st, z]]))
            self.put("sling_plates", *sweep_ends(secs, paint["iron"]))
            yi, yo, zc = self.cap_at(x)
            Rr, rr = 1.25 * IN, 0.3 * IN
            self.put("sling_plates", *torus((x, 0.5 * (yi + yo), zc + Rr + rr), EY, Rr, rr, paint["iron"], n=12, m=6,
                                            e1=EX))

    def windlass(self):
        """a launch's windlass (whole): two bitts standing on the bottom boards against her sides, the barrel between
        them (eight-sided, its heads square for the handspikes), the pawl post on the keelson"""
        b, paint = self.b, self.card["paint"]
        if not b.get("windlass"):
            return
        fit, k = self.fit, self.k
        x, z = fit["windlass_x"] * k[0], fit["windlass_z"] * k[2]
        rb = 4.5 * IN
        bw, bs = 5.0 * IN, 6.0 * IN
        z_top = z + rb + 6.0 * IN
        yb = min(self.inside_y(x - 0.5 * bs, z_top), self.inside_y(x + 0.5 * bs, z_top),
                 self.inside_y(x, self.z_bb)) - 0.75 * IN - 0.5 * bw
        for sg in (1.0, -1.0):
            self.put("windlass", *box((x, sg * yb, 0.5 * (self.z_bb + z_top)), (0.5 * bs, 0.5 * bw,
                                                                                  0.5 * (z_top - self.z_bb)),
                                      paint["inside"]))
        y_in = yb - 0.5 * bw
        head = 9.0 * IN
        t = np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False) + math.pi / 8
        ring = np.stack([np.cos(t), np.zeros(8), np.sin(t)], -1)
        secs = [np.array([x, yy, z]) + ring * (rb * (0.9 + 0.1 * math.cos(math.pi * yy / (y_in - head))))
                for yy in np.linspace(-(y_in - head), y_in - head, 5)]
        self.put("windlass", *sweep_ends(secs, paint["bright"]))
        for sg in (1.0, -1.0):
            self.put("windlass", *box((x, sg * (y_in - 0.5 * head), z), (0.95 * rb, 0.5 * head, 0.95 * rb),
                                      paint["bright"]))
        # the pawl post on the keelson forward of the barrel, its pawl down on the barrel
        xs, zk = self.keelson_top
        zk = float(np.interp(x, xs, zk))
        xp = x + rb + 2.5 * IN
        self.put("windlass", *box((xp, 0.0, 0.5 * (zk + z + rb + 4 * IN)), (2.0 * IN, 2.0 * IN,
                                                                             0.5 * (z + rb + 4 * IN - zk)),
                                  paint["inside"]))
        ang = math.radians(35)
        R = np.array([[math.cos(ang), 0, -math.sin(ang)], [0, 1, 0], [math.sin(ang), 0, math.cos(ang)]])
        self.put("windlass", *box((xp - 2.0 * IN - 0.5 * 4.5 * IN * math.cos(ang), 0.0,
                                   z + rb + 0.5 * 4.5 * IN * math.sin(ang)), (2.25 * IN, 1.0 * IN, 0.75 * IN),
                                  paint["iron"], R))

    def roller(self):
        """a launch's stem-head roller (whole): a roller across the head in a slot near its fore edge, between iron
        cheeks on its sides, on an iron pin"""
        b, paint = self.b, self.card["paint"]
        if not b.get("roller"):
            return
        Rp, Op, w_r, w_o, z_top = self.prof
        xf, xa = float(Op[-1, 0]), float(Rp[-1, 0])
        rr = 1.75 * IN
        xr = xf - rr + 0.25 * IN                  # its fore side a little proud of the stem's face, so a rope clears it
        wo = float(np.atleast_1d(w_o)[-1])
        hw = float(np.interp(xr, [xa, xf], [w_r, wo] if xa < xf else [wo, w_r]))
        zr = z_top + 0.25 * IN
        self.put("roller", *cylinder((xr, -hw, zr), (xr, hw, zr), rr, paint["bright"], n=10))
        ct = 0.375 * IN
        for sg in (1.0, -1.0):
            self.put("roller", *box((xr - 0.5 * IN, sg * (hw + 0.5 * ct), z_top - 1.0 * IN),
                                    (3.0 * IN, 0.5 * ct, 3.5 * IN), paint["iron"]))
        self.put("roller", *cylinder((xr, -(hw + ct + 0.3 * IN), zr), (xr, hw + ct + 0.3 * IN, zr), 0.4 * IN,
                                     paint["iron"], n=8))

    # --- her gear, stowed in her --------------------------------------------------------------------------------------
    @staticmethod
    def rest_line(xs, z_req, x_c=None):
        """the lowest straight line over the required heights z_req at xs (where something stowed must rest above
        them): (slope, intercept), pivoting about x_c (its middle)"""
        xs, z_req = np.asarray(xs, float), np.asarray(z_req, float)
        x_c = float(np.mean(xs)) if x_c is None else x_c
        best = None
        for a in np.linspace(-0.25, 0.25, 501):
            c = float(np.max(z_req - a * (xs - x_c)))
            if best is None or c < best[1] - 1e-9:
                best = (a, c)
        a, c = best
        return a, c - a * x_c

    def oar(self, P0, P1, o, blade_up=False):
        """an oar from its handle's end P0 to its blade's tip P1 (o: its card), its blade flat"""
        paint = self.card["paint"]
        P0, P1 = np.asarray(P0, float), np.asarray(P1, float)
        L = float(np.linalg.norm(P1 - P0))
        a = (P1 - P0) / L
        r = 0.5 * o["loom_in"] * IN
        bl, bw = o["blade_ft"][0] * FT, o["blade_ft"][1] * FT
        u = unit(np.cross(a, EZ))
        v = np.cross(u, a)
        t8 = np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False) + math.pi / 8
        ring = np.cos(t8)[:, None] * u + np.sin(t8)[:, None] * v
        # handle, its shoulder, the loom (thickest at the rowlock, a third along) and the neck into the blade
        prof = [(0.0, 0.5), (0.11, 0.5), (0.13, 0.85), (0.33, 1.0), (1.0 - bl / L, 0.72)]
        secs = [P0 + a * f * L + ring * (r * k) for f, k in prof]
        self.put("oars", *sweep_ends(secs, paint["oars"]))
        # the blade: flat, widening from the neck over its first third, its tip squared off with the corners eased
        th = max(0.5 * IN, 0.28 * r)
        f0 = 1.0 - bl / L
        secs = []
        for f, wf in ((f0 - 0.02, 0.6 * r / (0.5 * bw)), (f0 + 0.33 * bl / L, 1.0), (0.97, 1.0), (1.0, 0.8)):
            c = P0 + a * f * L
            hw = 0.5 * bw * min(1.0, wf)
            secs.append(np.array([c - u * hw - v * th, c + u * hw - v * th, c + u * hw + v * th, c - u * hw + v * th]))
        self.put("oars", *sweep_ends(secs, paint["oars"]))

    def oar_shape(self, L):
        """an oar's half-width in plan and half-depth (its blade flat) at fractions f along it from its handle's end,
        as oar() makes it"""
        o = self.b["oars"]
        r = 0.5 * o["loom_in"] * IN
        bl, bw = o["blade_ft"][0] * FT, o["blade_ft"][1] * FT
        f0 = 1.0 - bl / L
        th = max(0.5 * IN, 0.28 * r)
        lf, lk = zip(*[(0.0, 0.5), (0.11, 0.5), (0.13, 0.85), (0.33, 1.0), (f0, 0.72)])
        bf, bk = zip(*[(f0 - 0.02, 0.6 * r), (f0 + 0.33 * bl / L, 0.5 * bw), (0.97, 0.5 * bw), (1.0, 0.4 * bw)])

        def shape(f):
            f = np.asarray(f, float)
            loom = np.where(f <= f0, r * np.interp(f, lf, lk), 0.0)
            blade = f >= f0 - 0.02
            return (np.maximum(loom, np.where(blade, np.interp(f, bf, bk), 0.0)),
                    np.maximum(loom, np.where(blade, th, 0.0)))
        return shape

    def stow_oars(self):
        """the oars on the thwarts along her sides (half each side), handles and blades alternating, inboard of the
        knees: each loom rests on the thwarts under it and each blade (wider than the looms' pitch) on its neighbours'
        handles, the oar lying as low as it can about its balance (0.45 of it from the handle)"""
        b = self.b
        o = b["oars"]
        L = o["length_ft"] * FT
        r = 0.5 * o["loom_in"] * IN
        bw = o["blade_ft"][1] * FT
        arm = b["knee_in"][1] * IN
        kt = b["knee_in"][0] * IN
        shape = self.oar_shape(L)
        x_c = 0.5 * (self.thwarts[0]["x"] + self.thwarts[-1]["x"])
        x0, x1 = x_c - 0.5 * L, x_c + 0.5 * L
        xs = np.linspace(x0, x1, 161)
        pitch = max(2.0 * r + 0.5 * IN, 0.5 * bw + 0.3 * IN)
        top = np.full(len(xs), -np.inf)
        for th in self.thwarts:
            top[np.abs(xs - th["x"]) <= 0.5 * self.tw] = self.thwart_z(th)[1]
        # d: the oar's blade forward (its handle at x0); its neighbours lie the other way
        hw, hz = {}, {}
        for d in (True, False):
            hw[d], hz[d] = shape((xs - x0) / L if d else (x1 - xs) / L)
        z = {True: None, False: None}

        def solve(d):
            req = top + hz[d]
            if z[not d] is not None:
                on = (hw[d] + hw[not d] > pitch - 0.1 * IN) & (hw[d] > hw[not d])
                req = np.where(on, np.maximum(req, z[not d] + hz[not d] + hz[d] + 0.1 * IN), req)
            ok = np.isfinite(req)
            a, c = self.rest_line(xs[ok], req[ok], x0 + 0.45 * L if d else x1 - 0.45 * L)
            return a * xs + c
        for _ in range(4):
            z[True] = solve(True)
            z[False] = solve(False)
        # the outermost oar each side: clear of her side and of the knees' arms on the thwarts
        self.oars = {"xs": xs, "z": z, "hw": hw, "hz": hz, "y": {}}
        for sg in (1.0, -1.0):
            d = sg > 0
            lim = []
            for i, x in enumerate(xs):
                ys = [self.inside_y(x, zz) for zz in (z[d][i] - hz[d][i], z[d][i] + hz[d][i])]
                lim.append(min(yy if yy is not None else 0.0 for yy in ys) - 1.0 * IN - hw[d][i])
            for th in self.thwarts:
                ys = self.inside_y(th["x"], self.thwart_z(th)[1])
                near = np.abs(xs - th["x"]) <= 0.5 * kt + 0.5 * IN
                if ys is not None and near.any():
                    lim.append(ys - min(arm, 0.45 * ys) - 0.5 * IN - float(hw[d][near].max()))
            y_out = min(lim)
            self.oars["y"][sg] = []
            for j in range(o["count"] // 2):
                y = sg * (y_out - j * pitch)
                d = (j % 2 == 0) == (sg > 0)
                P0 = np.array([x0, y, z[d][0]]) if d else np.array([x1, y, z[d][-1]])
                P1 = np.array([x1, y, z[d][-1]]) if d else np.array([x0, y, z[d][0]])
                self.oar(P0, P1, o)
                self.oars["y"][sg].append((y, d))

    def oars_inner(self, x, sg):
        """the inner edge (half-breadth) of the oars on side sg at x, and their top there (None where they don't
        reach)"""
        A = self.oars
        xs = A["xs"]
        if not xs[0] <= x <= xs[-1]:
            return None
        y, d = A["y"][sg][-1]
        top = max(float(np.interp(x, xs, A["z"][dd] + A["hz"][dd])) for dd in (True, False))
        return abs(y) - float(np.interp(x, xs, A["hw"][d])), top

    def stow_masts(self):
        """each mast on the bottom boards beside the keelson (the first to starboard, the next to port), its sail
        furled on its yard in a roll beside it, lashed together; each bundle resting on whatever is under it"""
        paint = self.card["paint"]
        b = self.b
        rs = 0.5 * b["sail_roll_in"] * IN
        x_lo, x_hi = self.frame_x[0], self.frame_x[-1]
        self.mast_bundles = []
        for j, m in enumerate(b["masts"]):
            sg = 1.0 if j % 2 == 0 else -1.0
            L = m["length_ft"] * FT
            rm = 0.5 * m["diam_in"] * IN
            y_m = 0.5 * self.ks + 0.5 * IN + rm
            y_s = y_m + rm + rs + 0.25 * IN
            y_out = y_s + rs
            best = None
            for x_c in np.linspace(x_lo + 0.5 * L, x_hi - 0.5 * L, 21) if x_hi - x_lo > L else [0.5 * (x_lo + x_hi)]:
                xs = np.linspace(x_c - 0.5 * L, x_c + 0.5 * L, 31)
                zr = []
                for x in xs:
                    z = max(self.z_bb if self.bb_x[0] <= x <= self.bb_x[1] else self.z_floor, self.floor_top(x)
                            or self.z_floor)
                    # up until her side clears the bundle
                    for _ in range(80):
                        yy = self.inside_y(x, z + rs)
                        if yy is not None and yy > y_out + 0.5 * IN:
                            break
                        z += 0.01
                    zr.append(z)
                a, c = self.rest_line(xs, np.array(zr), x_c)
                h = a * x_c + c
                if best is None or h < best[0]:
                    best = (h, x_c, a, c)
            h, x_c, a, c = best
            x0, x1 = x_c - 0.5 * L, x_c + 0.5 * L
            # the mast, tapering to its head forward
            P0 = np.array([x0, sg * y_m, a * x0 + c + rm])
            P1 = np.array([x1, sg * y_m, a * x1 + c + 0.75 * rm])
            self.put("masts", *cylinder(P0, P1, rm, paint["oars"], n=10, r1=0.75 * rm))
            # the yard (its ends out of the roll) and the sail rolled on it
            Ly = 0.62 * L
            ya = np.array([x_c - 0.5 * Ly, sg * y_s, 0.0])
            yb = np.array([x_c + 0.5 * Ly, sg * y_s, 0.0])
            ya[2] = a * ya[0] + c + rs
            yb[2] = a * yb[0] + c + rs
            self.put("masts", *cylinder(ya, yb, 0.3 * rs, paint["oars"], n=8))
            ax = unit(yb - ya)
            k = 14
            t12 = np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)
            u = unit(np.cross(ax, EZ))
            v = np.cross(u, ax)
            secs = []
            for i, f in enumerate(np.linspace(0.06, 0.94, k)):
                c0 = ya + ax * f * Ly
                taper = 0.55 + 0.45 * math.sin(math.pi * (f - 0.06) / 0.88)
                bump = 1.0 + 0.06 * math.sin(7.3 * f + 1.1 * j) + 0.04 * math.cos(13.1 * f)
                rad = rs * taper * bump
                ring = c0 + rad * (np.cos(t12)[:, None] * u + np.sin(t12)[:, None] * v * 0.9)
                ring[:, 2] -= rs * (1.0 - taper) * 0.9          # the roll's ends sag onto the yard
                secs.append(ring)
            self.put("sails", *sweep_ends(secs, paint["canvas"]))
            # lashings round mast and roll: the rope round the pair's hull, under them on the bed
            rope_r = 0.35 * IN
            for f in (0.2, 0.5, 0.8):
                xl = x_c + (f - 0.5) * Ly
                zc = a * xl + c
                tm = (xl - x0) / L
                rmx = rm * (1.0 - 0.25 * tm)
                fr = (xl - ya[0]) / Ly
                taper = 0.55 + 0.45 * math.sin(math.pi * (fr - 0.06) / 0.88)
                bump = 1.0 + 0.06 * math.sin(7.3 * fr + 1.1 * j) + 0.04 * math.cos(13.1 * fr)
                rad = rs * taper * bump
                cz_s = zc + rs - rs * (1.0 - taper) * 0.9
                t36 = np.linspace(0.0, 2.0 * math.pi, 36, endpoint=False)
                pts = np.concatenate([np.stack([sg * y_m + rmx * np.cos(t36), zc + rmx + rmx * np.sin(t36)], -1),
                                      np.stack([sg * y_s + rad * np.cos(t36), cz_s + 0.9 * rad * np.sin(t36)], -1)])
                H = pts[ConvexHull(pts).vertices]
                H = np.concatenate([H, H[:1]])
                d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(H, axis=0), axis=1))]
                tt = np.linspace(0.0, d[-1], 24, endpoint=False)
                Q = np.stack([np.interp(tt, d, H[:, 0]), np.interp(tt, d, H[:, 1])], -1)
                ctr = Q.mean(0)
                nq = len(Q)
                N2 = np.array([unit2(np.array([Q[(i + 1) % nq][1] - Q[i - 1][1], Q[i - 1][0] - Q[(i + 1) % nq][0]]))
                               for i in range(nq)])
                N2 = np.where(((Q - ctr) * N2).sum(1)[:, None] < 0, -N2, N2)
                Q = Q + rope_r * N2
                Q[:, 1] = np.maximum(Q[:, 1], zc + rope_r)
                loop = np.stack([np.full(nq, xl), Q[:, 0], Q[:, 1]], -1)
                self.put("lashings", *ring_tube(loop, rope_r, paint["rope"]))
            self.mast_bundles.append((x0, x1, sg))

    def stow_rudder(self):
        """the rudder unshipped and laid flat along the starboard stern bench (its fore edge, with the pintles, to her
        side), the tiller along the port bench"""
        paint = self.card["paint"]
        b = self.b
        c = b["rudder"]["chord_ft"] * FT
        th = max(1.0 * IN, 0.075 * c)
        z_heel = float(self.prof[1][:, 1].min())
        # aft of the stern sheets' fore edge, and forward of the quarter knee where it would not clear the knee
        qk_len, qk_dep = (v * IN for v in b["quarter_knee_in"])
        x_qk = self.x_on_plane(self.sheer(0.0) - qk_dep, self.tr_t) + qk_len

        def start(height):
            """the after end of something height thick lying on the bench: at the bench's after end if it clears the
            quarter knee there (it lies at the bench's highest point under it), else forward of the knee"""
            x0 = self.x_bench0 + 0.05
            top = max(self.sheer(x) - self.ss_below for x in np.linspace(x0, x_qk, 9)) + height + 0.5 * IN
            clear = all(top < self.sheer(x) - qk_dep for x in np.linspace(x0, x_qk, 9))
            return x0 if clear else x_qk + 0.5 * IN
        xa = start(th + 0.25 * IN)
        Lr = min(self.transom_top_mid()[2] - z_heel + 0.8 * FT, self.x_ss - xa - 0.05)
        xb = xa + Lr
        # its outline in plan: the head (aft, narrow, the tiller's mortise in it) to the heel (forward, the full chord)
        yo = min(self.bench_y(x)[0] for x in np.linspace(xa, xb, 8)) - 0.5 * IN
        prof = [(0.0, 0.45), (0.22, 0.5), (0.34, 1.0), (0.97, 1.0), (1.0, 0.92)]
        P = [(xa + f * Lr, yo) for f, _ in prof] + [(xa + f * Lr, yo - w * c) for f, w in prof[::-1]]
        # lying along the bench (which rises aft with the sheer) on its pintles' straps: the lowest straight line over
        # the bench's top under it
        xs_r = np.linspace(xa, xb, 25)
        a_r, c_r = self.rest_line(xs_r, [self.sheer(x) - self.ss_below + 0.25 * IN for x in xs_r])
        z_rest = np.array([a_r * p[0] + c_r for p in P])
        self.put("rudder", *plan_prism(np.array(P), z_rest + th, z_rest, paint["outside"]))
        # the pintles: iron straps round its fore edge, their pins pointing aft
        for f in (0.45, 0.8):
            x = xa + f * Lr
            zr = a_r * x + c_r
            self.put("rudder", *box((x, yo - 1.5 * IN, zr + 0.5 * th), (0.75 * IN, 1.75 * IN, 0.5 * th + 0.2 * IN),
                                    paint["iron"]))
            self.put("rudder", *cylinder((x, yo + 0.25 * IN, zr + 0.5 * th), (x, yo + 0.25 * IN, zr + 0.5 * th + 0.01),
                                         0.4 * IN, paint["iron"], n=8))
        # the tiller, along the port bench (forward of the quarter knee where it would not clear it)
        xt = start(2.2 * IN * (b["tiller_ft"] / 4.5) ** 0.5)
        Lt = min(b["tiller_ft"] * FT, self.x_ss - xt - 0.05)
        r0, r1 = 1.1 * IN * (Lt / (4.5 * FT)) ** 0.5, 0.7 * IN * (Lt / (4.5 * FT)) ** 0.5
        yo_p = min(self.bench_y(x)[0] for x in np.linspace(xt, xt + Lt, 6)) - 0.5 * self.ss_w
        xs_t = np.linspace(xt, xt + Lt, 25)
        a_t, c_t = self.rest_line(xs_t, [self.sheer(x) - self.ss_below + 0.05 * IN + r0 + (r1 - r0) * (x - xt) / Lt
                                         for x in xs_t])
        self.put("tiller", *cylinder((xt, -yo_p, a_t * xt + c_t), (xt + Lt, -yo_p, a_t * (xt + Lt) + c_t), r0,
                                     paint["bright"], n=8, r1=r1))
        self.rudder_box = (xa, xb)

    def painter(self):
        """the painter: from a ring bolt in the stem's fore face under the head, up over the head (over the roller in
        a launch), down onto the breasthook, slack from its after edge to the foremost thwart and coiled down there
        (a stack of turns, laid with the sun) clear of the oars and the mast clamp"""
        paint = self.card["paint"]
        p = self.b["painter"]
        rr = p["circ_in"] * IN / (2.0 * math.pi)
        Rp, Op, w_r, w_o, z_top = self.prof
        z_s = self.sheer(float(Op[-1, 0]) - 0.3)
        # the ring bolt: its eye on the stem's fore edge a little under the sheer, the ring hanging from it
        zr = z_s - 4.0 * IN
        fe = Op[np.argsort(Op[:, 1])]

        def x_fore(zz):
            return float(np.interp(zz, fe[:, 1], fe[:, 0]))
        xf = x_fore(zr)
        Rg = 1.6 * rr + 0.6 * IN
        eye = np.array([xf + 0.6 * IN, 0.0, zr])
        self.put("ring_bolt", *cylinder(eye - [0.9 * IN, 0, 0], eye + [0.3 * IN, 0, 0], 0.35 * IN, paint["iron"],
                                        n=8))
        ring_c = eye + [0.25 * IN, 0.0, -Rg]
        self.put("ring_bolt", *torus(ring_c, EY, Rg, 0.3 * IN, paint["iron"], n=12, m=6, e1=EX))
        # the coil on the foremost thwart: between the mast clamp (or her middle) and the oars, to port
        th = self.thwarts[-1]
        ztw = self.thwart_z(th)[1]
        y_in = (0.5 * th["mast_d"] + 0.25 * IN + 0.375 * IN + 0.75 * IN) if th["mast"] else 0.0
        y_lim = []
        for x in np.linspace(th["x"] - 0.15, th["x"] + 0.15, 7):
            oi = self.oars_inner(x, -1.0)
            y_lim.append(oi[0] - 0.5 * IN if oi is not None else
                         self.inside_y(x, ztw) - self.b["knee_in"][1] * IN - 0.75 * IN)
        y_out = min(y_lim)
        Rc = min(5.0 * IN, 0.5 * (y_out - y_in))
        cy = -0.5 * (y_in + y_out) if th["mast"] else -max(0.0, min(0.5 * (y_in + y_out), y_out - Rc))
        cx = th["x"]
        Rm = Rc - rr
        # down onto the breasthook, to its after edge's middle
        x_bh, x_bf = self.bh
        L_bh = self.b["breasthook_in"][0] * IN
        xe = x_bh + 0.35 * L_bh
        E = np.array([xe - 0.25 * IN, 0.0, self.sheer(xe) + rr])
        # the head: over its top (over the roller in a launch) to the after corner
        xa_h, xf_h = min(float(Rp[-1, 0]), float(self.hog_line[-1, 0])), float(Op[-1, 0])
        # round the head's square corners a quarter of the rope's radius clear (a tighter turn folds the rope's skin),
        # its arcs at 3 deg a step (coarser, the smoothing below leaves a kink where an arc meets a long straight)
        Rb = 1.25 * rr
        rake = math.atan2(x_fore(z_top) - x_fore(z_top - 2.0 * IN), 2.0 * IN)      # the fore face leaning forward
        head = []
        th = 0.5 * math.pi
        if self.b.get("roller"):
            rrol = 1.75 * IN
            xr = xf_h - rrol + 0.25 * IN
            zrl = z_top + 0.25 * IN
            Ra = 1.03 * (rrol + rr)
            # off the roller along the line touching it and the turn over the head's after corner
            dx, dz = xa_h - xr, z_top - zrl
            th = (math.atan2(dz, dx) - math.acos((Ra - Rb) / math.hypot(dx, dz))) % (2.0 * math.pi)
            for ang in np.linspace(0.0, th, max(4, int(math.degrees(th) / 3.0) + 1)):
                head.append([xr + Ra * math.cos(ang), 0.0, zrl + Ra * math.sin(ang)])
        else:
            head = [[xf_h + Rb * math.cos(ang), 0.0, z_top + Rb * math.sin(ang)]
                    for ang in np.linspace(-rake, 0.5 * math.pi, int(math.degrees(0.5 * math.pi + rake) / 3.0) + 2)]
        # off the after corner along the line touching it and running down to the breasthook's after edge
        dx, dz = E[0] - xa_h, E[2] - z_top
        th_e = (math.atan2(dz, dx) - math.acos(min(1.0, Rb / math.hypot(dx, dz)))) % (2.0 * math.pi)
        th_e = min(max(th_e, th + 1e-3), math.pi)
        head += [[xa_h + Rb * math.cos(ang), 0.0, z_top + Rb * math.sin(ang)]
                 for ang in np.linspace(th, th_e, max(3, int(math.degrees(th_e - th) / 3.0) + 1))]
        # down the fore face from the head to the ring, clear of the eye
        down = []
        for zz in np.linspace(z_top - 0.5 * IN, zr + 1.0 * IN, 5):
            down.append([x_fore(zz) + Rb / math.cos(rake) + (1.6 * IN if zz < zr + 2.5 * IN else 0.0), 0.0, zz])
        fore = [list(ring_c + [0.0, 0.0, -Rg + 0.5 * rr])] + [list(ring_c + [0.6 * IN, 0.0, 0.3 * Rg])] + down[::-1]
        # slack from there to the coil's first turn (on the thwart, the rope leaving it toward the stem)
        turns = p.get("turns", 4)
        n = 20 * turns
        tt = np.linspace(0.0, 2.0 * math.pi * turns, n)
        jit = 1.0 + 0.05 * np.sin(1.7 * tt + 0.4)

        def coil_at(a0):
            return np.stack([cx + Rm * jit * np.cos(a0 - tt) + 0.15 * IN * np.sin(tt / turns),
                             cy + Rm * jit * np.sin(a0 - tt), ztw + rr + 2.1 * rr * tt / (2.0 * math.pi)], -1)
        dir2 = unit((np.array([cx, cy]) - E[:2]))
        for _ in range(4):
            ang0 = math.atan2(dir2[0], -dir2[1])
            coil = coil_at(ang0)
            S = coil[0]
            dir2 = unit(S[:2] - E[:2])
        D = float(np.linalg.norm(E[:2] - S[:2]))
        Hh = float(E[2] - S[2])
        lo, hi = 1e-3, 1e3
        for _ in range(100):
            am = math.sqrt(lo * hi)
            if am * (math.cosh(min(D / am, 50.0)) - 1.0) > Hh:
                lo = am
            else:
                hi = am
        cat = []
        for dd in np.linspace(D, 0.0, 16)[1:-1]:
            q = S[:2] - dir2 * dd
            cat.append([q[0], q[1], S[2] + am * (math.cosh(dd / am) - 1.0)])
        # the coil (above): from its bottom turn (S) up, clockwise seen from above
        lead = np.array(fore + head + [list(E)] + cat)
        lead = chaikin(lead, 2)
        # at an even step: where an arc's close points meet a long straight the rope's sections would otherwise
        # turn the arc's last step over a hair's length and fold
        lead = resample(lead, max(2, int(math.ceil(float(arclen(lead)[-1]) / (0.5 * rr))) + 1))
        path = np.concatenate([lead, coil[1:]])
        self.put("painter", *tube(path, rr, paint["rope"], n=6))
        self.coil = (cx, cy, Rc, ztw)

    # --- the whole boat -----------------------------------------------------------------------------------------------
    def build(self):
        """every part: her starboard half (mirrored to port), then what crosses her middle line, then her rowlocks,
        fittings and gear; info her sizes as built"""
        self.prep()
        for step in (self.planking, self.transom, self.risings, self.inwales, self.cappings, self.rubbing,
                     self.washstrake, self.knees, self.quarter_knees, self.stern_benches, self.bottom_boards,
                     self.sling_plates):
            step()
        self.mirror()
        for step in (self.backbone, self.frames, self.keelson, self.thwart_parts, self.breasthook, self.transom_bench,
                     self.thole_pins, self.windlass, self.roller, self.stow_oars, self.stow_masts, self.stow_rudder,
                     self.painter):
            step()
        self.measure()
        return self

    def measure(self):
        """her sizes as built (feet and inches where the card gives them so): length over the stem and transom,
        breadth over the rubbing strakes, depth amidships, and the layout"""
        V, F, M = self.mesh.arrays()
        hull = np.concatenate([v for v, lab in zip(self.mesh.V, self._labels_per_piece()) if lab in
                               ("planking_out", "keel_stem", "transom_out", "rubbing", "cappings")])
        x_mid = 0.5 * (self.sf.G[-1, 0, 0] + self.sf.G[-1, -1, 0])
        self.info = {
            "length_ft": round(float(hull[:, 0].max() - hull[:, 0].min()) / FT, 2),
            "breadth_ft": round(float(hull[:, 1].max() - hull[:, 1].min()) / FT, 2),
            "breadth_moulded_ft": round(2.0 * float(self.sf.G[-1, :, 1].max()) / FT, 2),
            "depth_ft": round((self.sheer(x_mid) - 0.0) / FT, 2),
            "keel_bottom_z_m": round(float(self.prof[1][:, 1].min()), 4),
            "thwarts_x_m": [round(t["x"], 3) for t in self.thwarts],
            "masts_at": {t["mast"]: t["i"] for t in self.thwarts if t["mast"]},
            "frames": len(self.frame_x), "room_in": self.b["frames"]["room_in"],
            "tris": self.mesh.tris(),
            "parts": sorted(set(self.mesh.lab)),
        }
        return self.info

    def label_tris(self):
        """{label: (V, T)}: her parts by label, each in triangles over its own vertices"""
        V, F, _ = self.mesh.arrays()
        by = {}
        for f, lab in zip(F, self.mesh.lab):
            by.setdefault(lab, []).append(f)
        out = {}
        for lab, fs in by.items():
            T = np.array([(f[0], f[k], f[k + 1]) for f in fs for k in range(1, len(f) - 1)], np.int64)
            idx, inv = np.unique(T, return_inverse=True)
            out[lab] = (V[idx], inv.reshape(T.shape))
        return out

    def room_check(self, near=0.03):
        """her parts clear of each other but where they meet by design (the card's meets: the parts on one side, those
        on the other, why, and how deep in inches the two may go into each other there), by deck.room over her labels:
        {"meet": the pairs that cross and shouldn't, or go deeper than allowed, "by_design": every designed pair met,
        with its deepest}"""
        import deck
        objs = self.label_tris()
        mine = set(objs)
        # deck.room weighs its parts against the rest of the ship as well: here there is none, so a speck far off
        objs[" far"] = (np.array([[1e3, 1e3, 1e3], [1e3 + 1, 1e3, 1e3], [1e3, 1e3 + 1, 1e3]]), np.array([[0, 1, 2]]))
        meets = {}
        for A, B, why, depth_in in self.card["meets"]["pairs"]:
            for a in A:
                for b in B:
                    if (a, b) in meets or (b, a) in meets:
                        raise ValueError(f"the boats' meets name {a} with {b} twice")
                    meets[(a, b)] = (why, depth_in)
        r = deck.room(objs, mine, None, near=near, meets=meets)
        return {"meet": r["meet"], "by_design": r["by_design"]}

    def _labels_per_piece(self):
        """each vertex block's label (the label of its first face)"""
        out, k = [], 0
        starts = np.cumsum([0] + [len(v) for v in self.mesh.V])
        fi = 0
        F = self.mesh.F
        for i in range(len(self.mesh.V)):
            while fi < len(F) and min(F[fi]) < starts[i]:
                fi += 1
            out.append(self.mesh.lab[fi] if fi < len(F) and starts[i] <= min(F[fi]) < starts[i + 1] else None)
        _ = k
        return out


def catmull(P, k):
    """a Catmull-Rom curve through the points P, k steps between each pair"""
    P = np.asarray(P, float)
    Q = np.concatenate([[2 * P[0] - P[1]], P, [2 * P[-1] - P[-2]]])
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        for t in np.linspace(0.0, 1.0, k, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1])
    return np.array(out)


def tube(P, r, mat, n=6):
    """a rope along the polyline P (parallel-transported frames), its ends capped"""
    P = np.asarray(P, float)
    T = unit(np.gradient(P, axis=0))
    e1 = unit(np.cross(T[0], EZ if abs(T[0][2]) < 0.9 else EX))
    secs = []
    t = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    for i in range(len(P)):
        if i:
            e1 = unit(e1 - T[i] * (e1 @ T[i]))
        e2 = np.cross(T[i], e1)
        secs.append(P[i] + r * (np.cos(t)[:, None] * e1 + np.sin(t)[:, None] * e2))
    return sweep_ends(secs, mat)


def unit2(v):
    n = float(np.hypot(v[0], v[1]))
    return v / n if n > 1e-12 else v


def ring_tube(P, r, mat, n=6):
    """a closed loop of rope through the points P (a ring, no caps)"""
    P = np.asarray(P, float)
    m = len(P)
    t = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    secs = []
    for i in range(m):
        tng = unit(P[(i + 1) % m] - P[i - 1])
        e1 = unit(np.cross(tng, EX)) if abs(tng @ EX) < 0.9 else unit(np.cross(tng, EY))
        e2 = np.cross(tng, e1)
        secs.append(P[i] + r * (np.cos(t)[:, None] * e1 + np.sin(t)[:, None] * e2))
    V = np.concatenate(secs)
    F = []
    for i in range(m):
        for q in range(n):
            a0, b0 = i * n + q, i * n + (q + 1) % n
            a1, b1 = ((i + 1) % m) * n + q, ((i + 1) % m) * n + (q + 1) % n
            F.append((a0, a1, b1, b0))
    f0 = F[0]
    nrm = np.cross(V[f0[1]] - V[f0[0]], V[f0[3]] - V[f0[0]])
    if np.dot(nrm, V[list(f0)].mean(0) - P[0]) < 0:
        F = [f[::-1] for f in F]
    return V, F, [mat] * len(F)


def chaikin(P, k=2):
    """corner cutting (its ends kept), k passes"""
    P = np.asarray(P, float)
    for _ in range(k):
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q += [0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b]
        Q.append(P[-1])
        P = np.array(Q)
    return P


# --- the boats stowed over the waist ----------------------------------------------------------------------------------
def _bvh(V, T):
    """a BVH tree over the triangles T (m, 3) of V (n, 3)"""
    try:
        from mathutils.bvhtree import BVHTree
    except ImportError:                             # the bpy module registers mathutils when it is imported
        import bpy  # noqa: F401
        from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons(np.asarray(V, float).tolist(), np.asarray(T, np.int64).reshape(-1, 3).tolist(),
                                all_triangles=True)


def fan_tris(F):
    """the faces F (each a fan from its first corner) as triangles (m, 3)"""
    return np.array([(f[0], f[k], f[k + 1]) for f in F for k in range(1, len(f) - 1)], np.int64).reshape(-1, 3)


def plane_cut(V, T, x0):
    """where the triangles T of V cross the plane x = x0: segments (n, 2, 2) of (y, z)"""
    P = np.asarray(V, float)[np.asarray(T, np.int64)]
    s = P[:, :, 0] - x0
    s = np.where(np.abs(s) < 1e-9, 1e-9, s)
    hit, pts = [], []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        sa, sb = s[:, a], s[:, b]
        t = (sa / np.where(sa != sb, sa - sb, 1.0))[:, None]
        hit.append(sa * sb < 0)
        pts.append((P[:, a] + t * (P[:, b] - P[:, a]))[:, 1:])
    hit, pts = np.stack(hit, 1), np.stack(pts, 1)
    two = hit.sum(1) == 2
    return pts[two][hit[two]].reshape(-1, 2, 2)


def lower_envelope(seg, ys):
    """the lowest z of the segments seg (n, 2, 2 of y, z) at each y of ys (nan where none spans it)"""
    ys = np.asarray(ys, float)
    y1, z1 = seg[:, 0, 0], seg[:, 0, 1]
    dy, dz = seg[:, 1, 0] - y1, seg[:, 1, 1] - z1
    ok = np.abs(dy) > 1e-12
    y1, z1, dy, dz = y1[ok], z1[ok], dy[ok], dz[ok]
    lo, hi = np.minimum(y1, y1 + dy), np.maximum(y1, y1 + dy)
    out = np.full(len(ys), np.nan)
    for i0 in range(0, len(ys), 256):
        Y = ys[i0:i0 + 256, None]
        Z = np.where((Y >= lo) & (Y <= hi), z1 + (Y - y1) / dy * dz, np.inf)
        z = Z.min(1)
        out[i0:i0 + 256] = np.where(np.isfinite(z), z, np.nan)
    return out


def rdp_keep(ys, Z, tol):
    """which of the samples ys to keep (Ramer-Douglas-Peucker on each row of Z, by its height off the chord)"""
    keep = np.zeros(len(ys), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(ys) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        t = (ys[i + 1:j] - ys[i]) / max(float(ys[j] - ys[i]), 1e-12)
        dev = np.abs(Z[:, i + 1:j] - (Z[:, i:i + 1] + t * (Z[:, j:j + 1] - Z[:, i:i + 1]))).max(0)
        k = int(np.argmax(dev))
        if dev[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return keep


def envelope_samples(segs, y_a, y_b, tol=0.0003, eps=1e-6):
    """the lower envelopes of the sections segs (each (n, 2, 2)) over y_a..y_b at shared samples: every segment's end
    (either side of it, so a step stays a step), thinned where every envelope runs straight (within tol). Returns
    the ys and each envelope's z there (nan where a section doesn't reach)"""
    br = [y_a, y_b]
    for seg in segs:
        e = seg[:, :, 0].ravel()
        br += list(e[(e > y_a + 2 * eps) & (e < y_b - 2 * eps)])
    br = np.unique(np.round(br, 7))
    ys = np.unique(np.concatenate([[y_a, y_b], np.clip(br - eps, y_a, y_b), np.clip(br + eps, y_a, y_b)]))
    Z = np.stack([lower_envelope(seg, ys) for seg in segs])
    if np.isnan(Z).any():
        return ys, Z
    keep = rdp_keep(ys, Z, tol)
    return ys[keep], Z[:, keep]


def turned_course(P, rad, max_step=0.1):
    """a rope's centre line through the corners of the polyline P, each inner corner turned on a circular arc of radius
    rad or as near it as the segments allow (anchors._course's turn), its arcs kept at 3 deg a step and its straight
    runs divided no longer than max_step (not laid at an even step, which would cut a tight turn's arc into chords)"""
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
    pts = [P[0]]
    for i in range(1, n - 1):
        if th[i] < 1e-4:
            pts.append(P[i])
            continue
        t = want[i] * min(f[i - 1], f[i])
        R = t / math.tan(0.5 * th[i])
        u, v = U[i - 1], U[i]
        w = unit(v - (u @ v) * u)
        O = P[i] - t * u + R * w
        ph = np.linspace(0.0, th[i], max(2, int(math.ceil(math.degrees(th[i]) / 3.0))) + 1)
        pts += list(O[None] - R * np.cos(ph)[:, None] * w[None] + R * np.sin(ph)[:, None] * u[None])
    pts.append(P[-1])
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        d = float(np.linalg.norm(b - a))
        if d < 1e-7:
            continue
        k = int(math.ceil(d / max_step))
        out += [a + (b - a) * j / k for j in range(1, k + 1)]
    return np.array(out)


def two_face_prism(PA, PB, xa, xb, mat):
    """a solid between the polygon PA (n, 2: y, z) in the plane x = xa and PB (as many points, nearly the same shape)
    in x = xb: both faces and the sides, turned out"""
    PA, PB = np.asarray(PA, float), np.asarray(PB, float)
    if area2d(PA) < 0:
        PA, PB = PA[::-1], PB[::-1]
    if area2d(PB) <= 0:
        raise ValueError("two_face_prism: its faces wind opposite ways")
    n = len(PA)
    # each face triangulated on its own (a triangle of one can fold over in the other where a step is a hair wide)
    V = np.concatenate([np.c_[np.full(n, xa), PA], np.c_[np.full(n, xb), PB]])
    F = [tuple(n + i for i in t) for t in loft.ear_clip(PB)] + [tuple(t[::-1]) for t in loft.ear_clip(PA)]
    F += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    T = fan_tris(F)
    vol = float(np.einsum("ij,ij->i", V[T[:, 0]], np.cross(V[T[:, 1]], V[T[:, 2]])).sum())
    if vol < 0:
        F = [f[::-1] for f in F]
    return V, F, [mat] * len(F)


def saddle_top(segs, y_a, y_b, z_e):
    """a saddle's top across y_a..y_b, one shape its whole length: the lowest of the spar's undersides over it (its
    sections segs, as envelope_samples takes them: round or square alike) where that is under z_e, flat at z_e either
    side. Returns the ys and the top's z there"""
    br = [y_a, y_b]
    for seg in segs:
        e = seg[:, :, 0].ravel()
        br += list(e[(e > y_a) & (e < y_b)])
    br = np.round(br, 7)
    ys = np.unique(np.concatenate([br, np.clip(br - 1e-6, y_a, y_b), np.clip(br + 1e-6, y_a, y_b)]))
    Z = np.stack([lower_envelope(seg, ys) for seg in segs if len(seg)])
    z = np.where(np.isnan(Z), np.inf, Z).min(0)
    # where it crosses z_e between two samples (it runs straight between them): a sample there
    d = z - z_e
    i = np.nonzero(np.isfinite(d[:-1]) & np.isfinite(d[1:]) & (d[:-1] * d[1:] < 0))[0]
    if len(i):
        yc = ys[i] + (ys[i + 1] - ys[i]) * d[i] / (d[i] - d[i + 1])
        ys, z = np.concatenate([ys, yc]), np.concatenate([z, np.full(len(yc), z_e)])
        o = np.argsort(ys, kind="stable")
        ys, z = ys[o], z[o]
    z = np.minimum(z, z_e)
    keep = rdp_keep(ys, z[None], 0.0002)
    return ys[keep], z[keep]


def notched_bottom(ya, yb, z_cb, spars_):
    """an underside from ya to yb, flat at z_cb but hollowed over each spar (y, z of its axis, R) up round its top"""
    pts = [(ya, z_cb)]
    for ys, zs, R in sorted(spars_):
        h = z_cb - zs
        a0 = math.asin(min(1.0, math.sqrt(max(0.0, R * R - h * h)) / R))
        pts += [(ys + R * math.sin(a), zs + R * math.cos(a)) for a in np.linspace(-a0, a0, 15)]
    pts.append((yb, z_cb))
    return np.array(pts)


class _Splicer:
    """anchors.py's eyebolt and spliced eye, for the gripes"""
    from anchors import Anchors as _A
    _eyebolt = _A._eyebolt
    _spliced_eye = _A._spliced_eye
    _rope_between = staticmethod(_A._rope_between)
    del _A


class Boats:
    """The boats stowed over the open waist (card['stowage']; the module's docstring): the spare spars on saddles on
    the waist's beams, each boat level on two cradles across her own two spars (the launch in the middle, a cutter
    either side as close as gap_between_boats_in allows), the gig nested in the starboard cutter on two chocks across
    its thwarts, the stream anchor and the large kedge in the launch and the small kedge in the port cutter (each
    turned down about its stock on her gunwales until it rests on something in her), and a gripe over each boat (and
    what rides in her) at each cradle, spliced to eyebolts in its ends. sk, rig, dk: the built skin, rig (spars.Rig)
    and spar deck (deck.Deck). parts(): name -> (V, F, M, frame): a boat's vertices in her own frame (frame (origin,
    axes) in the ship), the rest in the ship's frame (frame None); info: where everything is and the checks"""

    BOATS = ("Launch", "Cutter_S", "Cutter_P", "Gig")
    ANCHORS = {"stream": "StreamAnchor", "kedge_large": "KedgeLarge", "kedge_small": "KedgeSmall"}

    def __init__(self, sk, rig, dk, card=None):
        import anchors as AN
        self.card = card or load_card()
        self.st = self.card["stowage"]
        self.sk, self.rig, self.dk, self.AN = sk, rig, dk, AN
        self.acard = AN.load_card()
        self.info = {}
        self.x_mid = 0.5 * (dk.e1 + dk.fc)
        self.thick = dk.c["deck"]["planking"]["thick_in"] * IN
        self.beam_sided = dk.c["waist"]["beam_sided_in"] * IN
        self.beams = [(float(x), float(dk.z(x)) - self.thick) for x in dk.beams_x]   # each waist beam: x, its top
        self.units = {}

    def build(self):
        self.hulls()
        self.spare_spars()
        for name in ("Launch", "Cutter_S", "Cutter_P"):
            self.cradle_boat(name)
        self.nest_gig()
        self.stow_anchors()
        for name in ("Launch", "Cutter_S", "Cutter_P"):
            self.gripes(name)
        self.place()
        self.checks()
        return self

    # --- the boats ------------------------------------------------------------------------------------------------------
    def hulls(self):
        """each kind of boat built once (the two cutters are alike), her own clash check and the drawing's check"""
        self.built = {}
        for key in sorted({v["boat"] for v in self.st["boats"].values()}):
            bt = Boat(self.card, key).build()
            bt.room_ = bt.room_check()
            bt.lines_ = bt.ln.check()
            V, F, _ = bt.mesh.arrays()
            bt.T_ = fan_tris(F)
            bt.V_ = V
            bt.tree_ = _bvh(V, bt.T_)
            self.built[key] = bt

    def unit(self, name):
        """the boat name's stowage: her boat, its origin (x, z in the ship's frame; y off her own middle line, placed
        later), her spars and what rides in her"""
        if name not in self.units:
            b = self.st["boats"][name]
            bt = self.built[b["boat"]]
            V = bt.V_
            x0 = self.x_mid - 0.5 * float(V[:, 0].min() + V[:, 0].max())
            self.units[name] = {"name": name, "bt": bt, "o": np.array([x0, 0.0, 0.0]), "pieces": {}, "spars": []}
        return self.units[name]

    @staticmethod
    def add(u, obj, V, F, M):
        """a piece of the object obj (in the unit's frame) to the unit u"""
        u["pieces"].setdefault(obj, Mesh())
        u["pieces"][obj].add(V, F, M)

    # --- the spare spars and their saddles ---------------------------------------------------------------------------
    def spar_shape(self, sp):
        """a spare spar in its own frame (along X, its middle at the origin, its top up) as the rig builds it: its mesh
        (V, F, M) and its radius along it (a function of x)"""
        import spars
        rig = self.rig
        L, d = sp["length_ft"] * FT, sp["diam_in"] * IN
        kind, path = sp["kind"], sp["spar"].split(".")
        if kind == "yard":
            on = rig.sp["yards"][path[1]]["on"]
            V, F, M = rig.yard_mesh(path[1], L, d, 0.0, (on in ("lower", "topmast"), on), False).arrays()
            V = np.stack([V[:, 1], -V[:, 0], V[:, 2]], -1)                 # its length (the yard's Y) fore and aft
            yt = spars.taper(rig.sp["taper"]["yard"])
            return (V, F, M), (lambda x: 0.5 * d * float(yt(min(1.0, abs(x) / (0.5 * L)))))
        mesh = spars.Mesh()
        o = np.array([-0.5 * L, 0.0, 0.0])
        if kind == "mast":                                                  # its heel aft
            m = rig.masts[path[1]]
            t0, D = m["s_tg0"], m["D_tg"]
            L = m["s_pole"] - t0
            o = np.array([-0.5 * L, 0.0, 0.0])
            spars.spar(mesh, o, EX, EY, [(0.0, D / 2), (1.6 * D, D / 2)], rig.mat_wood, shape="square")
            nt = rig.nseg(D)
            ss = [1.6 * D - 0.01] + list(np.linspace(m["s_tmcap1"] - t0, m["s_stop"] - t0, 7))
            spars.spar(mesh, o, EX, EY, [(s, m["R_tg"](s + t0)) for s in ss], rig.mat_wood, nt)
            spars.spar(mesh, o, EX, EY, [(m["s_stop"] - t0, m["R_tg"](m["s_stop"] + 1e-6)), (L, m["R_tg"](m["s_pole"]))],
                       rig.mat_wood, nt)
            ss = np.linspace(0.0, L, 200)
            Rs = np.array([D / 2 if s < 1.6 * D else m["R_tg"](s + t0) for s in ss])
            sp["length_ft"] = round(L / FT, 2)
        else:                                                               # a studding sail boom, its heel aft
            st_ = [(0.0, 0.42 * d), (0.06 * L, 0.5 * d), (0.85 * L, 0.45 * d), (L, 0.35 * d)]
            spars.spar(mesh, o, EX, EY, st_, rig.mat_wood, rig.nseg(d))
            ss, Rs = np.array([s for s, _ in st_]), np.array([r for _, r in st_])
        V, F, M = mesh.arrays()
        return (V, F, M), (lambda x: float(np.interp(x + 0.5 * L, ss, Rs)))

    def spare_spars(self):
        """each boat's two spars level, their middles at the waist's middle, their tops at its middle at one height: the
        least that leaves every saddle under them saddle_min_in thick on every beam each crosses (a beam crossed where
        the spar runs on past its saddle 2 in). The saddles: a beam's siding long, the spar's diameter and saddle_in[1]
        wide, hollowed to the spar"""
        st = self.st
        by = {sp["name"]: sp for sp in st["spars"]}
        s_min = st["saddle_min_in"] * IN
        self.spar_info = {}
        for name in ("Launch", "Cutter_S", "Cutter_P"):
            u = self.unit(name)
            sps = []
            for sname, y_off in st["boats"][name]["spars"]:
                sp = dict(by[sname])
                (V, F, M), R = self.spar_shape(sp)
                L = float(V[:, 0].max() - V[:, 0].min())
                beams = [(xb, zb) for xb, zb in self.beams
                         if abs(xb - self.x_mid) + 0.5 * self.beam_sided + 2 * IN <= 0.5 * L]
                sps.append({"name": sname, "y": float(y_off), "R": R, "L": L, "mesh": (V, F, M), "beams": beams,
                            "d_in": sp["diam_in"], "length_ft": sp["length_ft"], "kind": sp["kind"]})
            z_top = max(zb + s_min + sp["R"](xb - self.x_mid) + sp["R"](0.0) for sp in sps for xb, zb in sp["beams"])
            for sp in sps:
                sp["z"] = z_top - sp["R"](0.0)                               # its axis
                V, F, M = sp["mesh"]
                Vw = V + [self.x_mid, sp["y"], sp["z"]]
                self.add(u, "SpareSpars", Vw, F, M)
                Tw = fan_tris(F)
                th = []
                for xb, zb in sp["beams"]:
                    r = sp["R"](xb - self.x_mid)
                    w = 2 * r + st["saddle_in"][1] * IN
                    x0, x1 = xb - 0.5 * self.beam_sided, xb + 0.5 * self.beam_sided
                    # its sections over the saddle's length: its faces and either side of each ring between (a mast's
                    # square heel running into its round, a yard's taper)
                    xr = np.unique(np.round(Vw[(Vw[:, 0] > x0) & (Vw[:, 0] < x1), 0], 5))
                    xc = np.clip(np.concatenate([[x0, x1], xr - 1e-4, xr + 1e-4]), x0, x1)
                    ys, Z = saddle_top([plane_cut(Vw, Tw, xx) for xx in np.unique(xc)], sp["y"] - 0.5 * w,
                                       sp["y"] + 0.5 * w, sp["z"] - r * math.cos(math.radians(50.0)))
                    P2 = np.concatenate([[(sp["y"] - 0.5 * w, zb), (sp["y"] + 0.5 * w, zb)], np.c_[ys[::-1], Z[::-1]]])
                    V2, F2, M2 = two_face_prism(P2, P2, x0, x1, "Oak")
                    self.add(u, "SparSaddles", V2, F2, M2)
                    th.append(round(float(Z.min() - zb) / IN, 2))
                self.spar_info[sp["name"]] = {"boat": name, "kind": sp["kind"], "length_ft": sp["length_ft"],
                                              "diam_in": sp["d_in"], "y_off_boat_m": sp["y"],
                                              "axis_z_m": round(sp["z"], 4), "beams": len(sp["beams"]),
                                              "saddles_in": [min(th), max(th)]}
            u["spars"] = sps

    # --- each boat on her cradles ----------------------------------------------------------------------------------------
    def section(self, bt, extra, x_l):
        """her section (y, z segments, her frame) at x_l: her own triangles' and those of extra ((V, T) in her frame)"""
        segs = [plane_cut(bt.V_, bt.T_, x_l)] + [plane_cut(V, T, x_l) for V, T in extra]
        return np.concatenate([s for s in segs if len(s)]) if any(len(s) for s in segs) else np.zeros((0, 2, 2))

    def cradle_boat(self, name):
        """her two cradles at cradle.at of her straight keel, each across her spars (its ends beyond_spar_in past
        them), notched over them an inch, its top cut to her outside (her keel in its slot, a clinker boat's lands
        stepped); she sits level, her keel under_keel_in over the higher cradle's underside"""
        u = self.unit(name)
        bt, cr = u["bt"], self.st["cradle"]
        xa_k, xf_k, kb = bt.keel_run
        half_t = 0.5 * cr["thick_in"] * IN
        beyond = cr["beyond_spar_in"] * IN
        sps = u["spars"]
        ya = min(sp["y"] - sp["R"](0.0) for sp in sps) - beyond
        yb = max(sp["y"] + sp["R"](0.0) for sp in sps) + beyond
        xs_l = [xa_k + f * (xf_k - xa_k) for f in cr["at"]]
        # her height: each cradle's underside an inch under its lower spar's top there
        z_cb = []
        for x_l in xs_l:
            x = u["o"][0] + x_l
            z_cb.append(min(sp["z"] + sp["R"](x - self.x_mid) for sp in sps) - 1.0 * IN)
        z_keel = max(z_cb) + cr["under_keel_in"] * IN
        u["o"][2] = z_keel - kb
        u["cradles"] = []
        for x_l, zc in zip(xs_l, z_cb):
            x = u["o"][0] + x_l
            segA = self.section(bt, [], x_l - half_t)
            segB = self.section(bt, [], x_l + half_t)
            ys, Z = envelope_samples([segA, segB], ya, yb)
            if np.isnan(Z).any():
                raise ValueError(f"{name}'s cradle at {x_l:.3f} m reaches past her outside")
            Z = Z + u["o"][2]
            bot = notched_bottom(ya, yb, zc, [(sp["y"], sp["z"], sp["R"](x - self.x_mid)) for sp in sps])
            PA = np.concatenate([bot, np.c_[ys[::-1], Z[0][::-1]]])
            PB = np.concatenate([bot, np.c_[ys[::-1], Z[1][::-1]]])
            if (Z.min(0) - zc).min() < 0.5 * IN:
                raise ValueError(f"{name}'s cradle at {x_l:.3f} m is too thin")
            V, F, M = two_face_prism(PA, PB, x - half_t, x + half_t, "Oak")
            self.add(u, "BoatCradles", V, F, M)
            u["cradles"].append({"x": x, "x_l": x_l, "ya": ya, "yb": yb, "z_cb": zc, "top_ends": [float(Z[:, 0].min()),
                                                                                                    float(Z[:, -1].min())]})
        self.info.setdefault("boats", {})[name] = {
            "boat": self.st["boats"][name]["boat"], "keel_bottom_z_m": round(z_keel, 4),
            "cradles_x_m": [round(c["x"], 3) for c in u["cradles"]],
            "under_keel_in": [round((z_keel - c["z_cb"]) / IN, 2) for c in u["cradles"]]}

    # --- the gig nested in the starboard cutter ------------------------------------------------------------------------
    @staticmethod
    def heights(V, T, cell, top):
        """the triangles' surface rasterised on a plan grid (x, y cells cell square): each cell's highest point (top)
        or lowest: {(i, j): z}"""
        import deck
        P = deck.surface_points(V, T, 0.7 * cell)
        ij = np.floor(P[:, :2] / cell).astype(np.int64)
        key = ij[:, 0] * 100000 + ij[:, 1]
        order = np.argsort(key, kind="stable")
        key, z = key[order], P[order, 2]
        uk, start = np.unique(key, return_index=True)
        zz = (np.maximum if top else np.minimum).reduceat(z, start)
        return dict(zip(uk.tolist(), zz.tolist()))

    def nest_gig(self):
        """the gig on two chocks across the starboard cutter's thwarts (on_thwarts), level, her keel nest_chock_in[1]
        over the higher thwart's top: placed along her straight keel where she clears everything in the cutter by an
        inch (raised on deeper chocks only if she clears nowhere). Each chock nest_chock_in[0] fore and aft on its
        thwart, its top cut to her outside, its ends where her bottom has risen chock_rise_in over her keel or an inch
        short of the cutter's oars"""
        g = self.st["boats"]["Gig"]
        host = self.unit(g["in"])
        cb, gb = host["bt"], self.built[g["boat"]]
        w_c, under = (v * IN for v in self.st["nest_chock_in"])
        rise = self.st.get("chock_rise_in", 6.0) * IN
        ths = [cb.thwarts[i] for i in g["on_thwarts"]]
        tops = [cb.thwart_z(th)[1] for th in ths]
        xa_k, xf_k, kb = gb.keel_run
        margin = 0.5 * w_c + 2 * IN
        z0 = max(tops) + under - kb                    # her origin's height in the cutter's frame on the chocks
        cell = 0.01
        cut = self.heights(cb.V_, cb.T_, cell, True)
        gig = self.heights(gb.V_, gb.T_, cell, False)
        gk = np.array(list(gig.keys()))
        gi = (gk + 50000) // 100000
        gj, gz = gk - gi * 100000, np.array(list(gig.values()))
        lo = max(th["x"] for th in ths) - (xf_k - margin)
        hi = min(th["x"] for th in ths) - (xa_k + margin)
        best = None
        for di in range(int(math.ceil(lo / cell)), int(math.floor(hi / cell)) + 1, 2):
            k = (gi + di) * 100000 + gj
            need = -np.inf
            for kk, z in zip(k.tolist(), gz.tolist()):
                c = cut.get(kk)
                if c is not None:
                    need = max(need, c + 1.0 * IN - z)
            lift = max(0.0, need - z0)
            if best is None or lift < best[0] - 1e-9 or (abs(lift - best[0]) < 1e-9 and
                                                         abs(di * cell - 0.5 * (lo + hi)) < abs(best[1] - 0.5 * (lo + hi))):
                best = (lift, di * cell)
        lift, dx = best
        zg = z0 + lift
        host["gig"] = {"bt": gb, "o": host["o"] + [dx, 0.0, zg]}
        # the chocks
        for th, zt in zip(ths, tops):
            x_l = th["x"]
            xg = x_l - dx
            segs = [self.section(gb, [], xg - 0.5 * w_c), self.section(gb, [], xg + 0.5 * w_c)]
            # her bottom's rise either side of her keel: the chock ends where it has risen `rise`
            ys = np.linspace(0.0, 1.5, 301)
            env = np.nanmax(np.stack([lower_envelope(s, ys) for s in segs]), 0)
            y_end = float(ys[np.nonzero(~(env <= kb + rise))[0][0] - 1]) if (~(env <= kb + rise)).any() else 0.5
            for sg in (1, -1):
                oi = cb.oars_inner(x_l, sg)
                if oi is not None:
                    y_end = min(y_end, oi[0] - 1.0 * IN)
            ys, Z = envelope_samples(segs, -y_end, y_end)
            Z = Z + zg
            bot = np.array([(-y_end, zt), (y_end, zt)])
            PA = np.concatenate([bot, np.c_[ys[::-1], Z[0][::-1]]])
            PB = np.concatenate([bot, np.c_[ys[::-1], Z[1][::-1]]])
            x = host["o"][0] + x_l
            V, F, M = two_face_prism(PA + [0.0, host["o"][2]], PB + [0.0, host["o"][2]], x - 0.5 * w_c,
                                     x + 0.5 * w_c, "Oak")
            self.add(host, "GigChocks", V, F, M)
        self.info["gig"] = {"in": g["in"], "on_thwarts": g["on_thwarts"], "x_off_m": round(dx, 3),
                            "keel_over_thwart_in": round((zg + kb - max(tops)) / IN, 2), "lifted_in": round(lift / IN, 2)}

    # --- the anchors in the boats ----------------------------------------------------------------------------------------
    def stow_anchors(self):
        """the stream anchor and the large kedge in the launch, the small kedge in the port cutter (stowage anchors),
        each with what is already in her as something to rest on"""
        self.info["anchors"] = {}
        for key, a in self.st["anchors"].items():
            if not isinstance(a, dict):
                continue
            u = self.unit(a["boat"])
            u.setdefault("loads", [])
            mesh, pose = self.stow_anchor(u["bt"], key, a["stock"], u["loads"])
            V, F, M = mesh.arrays()
            u["loads"].append((V, fan_tris(F)))
            self.add(u, self.ANCHORS[key], V + u["o"], F, M)
            self.info["anchors"][key] = dict(pose, boat=a["boat"])

    def stow_anchor(self, bt, key, end, loads):
        """the anchor key in the boat bt (her frame): its stock across her gunwales near her end ('aft' or 'fore'),
        resting on their tops (her cappings, or a cutter's washstrakes where she has them), where her breadth over the
        cappings is the stock's length less stock_overhang_in each side, or as near there as lets it lie clear of her
        thole pins and the like (toward her middle only while it still overhangs 3 in); its shank along her middle line
        toward her middle, its arms upright; turned down about the stock (rolling on her gunwales) from crown up until
        its crown, an arm or its shank first touches something in her (loads: what lies in her already, (V, T) in her
        frame), never its stock; its ring hanging from the eye, swung about the eye's axis until clear. Returns its mesh
        (her frame) and where it lies"""
        import deck
        an = self.AN.Anchor(self.acard, self.acard["anchors"][key]["lb"], pudden=0.0, name=key).solve()
        k = an.key
        half_b = 0.5 * k["stock_len"] - self.st["anchors"]["stock_overhang_in"] * IN
        half_min = 0.5 * k["stock_len"] - 3.0 * IN
        lt = bt.label_tris()
        gun = [n for n in ("cappings", "washstrake") if n in lt]

        def joined(names):
            Vs_, Ts_, off = [], [], 0
            for n in names:
                Vs_.append(lt[n][0])
                Ts_.append(lt[n][1] + off)
                off += len(lt[n][0])
            return np.concatenate(Vs_), np.concatenate(Ts_)
        # her gunwales' tops on a plan grid: the stock rests on the highest of the cells under it
        cell = 0.01
        sup = self.heights(*joined(gun), cell, True)
        K = np.array(sorted(sup), np.int64)
        Zc = np.array([sup[c] for c in K.tolist()])
        others = [n for n in lt if n not in gun]
        obst = [_bvh(*joined(others))] + [_bvh(V, T) for V, T in loads]
        C = np.array([s[0, 0] for s in bt.cap_secs])
        x_lo, x_hi = float(C.min()), float(C.max())
        x_mid = 0.5 * (x_lo + x_hi)
        sgn = 1.0 if end == "aft" else -1.0                       # the shank's way from the stock toward her middle
        xs = np.linspace(x_lo, x_mid, 600) if end == "aft" else np.linspace(x_hi, x_mid, 600)
        x_b = next(float(x) for x in xs if bt.cap_at(x)[1] >= half_b)
        Vs, Fs, _ = an.stock.arrays()
        Ts = fan_tris(Fs)
        S = deck.surface_points(Vs, Ts, 0.01)
        Vi, Fi, _ = an.iron.arrays()
        Vk = np.concatenate([Vi, Vs])
        Tk = np.concatenate([fan_tris(Fi), Ts + len(Vi)])

        def rot(phi):
            c_, s_ = math.cos(phi), math.sin(phi)
            Z = np.array([-sgn * c_, 0.0, s_])                     # up the shank, crown to ring: toward her end
            X = np.cross(EY, Z)
            return np.stack([X, EY, Z], 1)

        def pose(phi, xs_):
            """the anchor turned phi about its stock (down from the shank level), its stock's middle over xs_ and its
            stock on her gunwales' tops on both sides (None where it doesn't reach them)"""
            R = rot(phi)
            P0 = R @ np.array([0.0, 0.0, k["stock_z"]])
            Q = S @ R.T
            tx = xs_ - P0[0]
            kk = np.floor((Q[:, 0] + tx) / cell).astype(np.int64) * 100000 + np.floor(Q[:, 1] / cell).astype(np.int64)
            i = np.minimum(np.searchsorted(K, kk), len(K) - 1)
            on = K[i] == kk
            if not ((Q[on, 1] > 0).any() and (Q[on, 1] < 0).any()):
                return None
            return R, np.array([tx, 0.0, float((Zc[i[on]] - Q[on, 2]).max())])

        def hits(phi, xs_, V, T):
            R, t = pose(phi, xs_)
            tr = _bvh(V @ R.T + t, T)
            return any(len(tr.overlap(o)) for o in obst)

        def settle(xs_):
            """its rest turning down from crown up with its stock over xs_: (the last clear turn, the first touching),
            or None where its stock would stand in something or it rests on nothing"""
            top = math.radians(-84.0)
            if pose(top, xs_) is None or hits(top, xs_, Vk, Tk):
                return None
            prev = top
            for deg in np.arange(-82.0, 89.0, 2.0):
                ph = math.radians(deg)
                if pose(ph, xs_) is None:
                    return None
                if hits(ph, xs_, Vk, Tk):
                    a_, b_ = prev, ph
                    for _ in range(13):
                        m_ = 0.5 * (a_ + b_)
                        a_, b_ = (m_, b_) if not hits(m_, xs_, Vk, Tk) else (a_, m_)
                    return None if hits(b_, xs_, Vs, Ts) else (a_, b_)
                prev = ph
            return None

        def ring_clear(R, t):
            """the ring hanging from the eye, swung about the eye's axis (the stock's way) until clear of her, what lies
            in her and its own stock, then back toward hanging until it rests: its swing, or None"""
            down = R.T @ np.array([0.0, 0.0, -1.0])
            down = unit(down - (down @ EY) * EY)
            side = np.cross(EY, down)
            trees = [bt.tree_, _bvh(Vs @ R.T + t, Ts)] + obst[1:]

            def ring_hits(psi):
                an.build_ring(k["eye"], math.cos(psi) * down + math.sin(psi) * side)
                Vr, Fr, _ = an.ring.arrays()
                tr = _bvh(Vr @ R.T + t, fan_tris(Fr))
                return any(len(tr.overlap(o)) for o in trees)
            psi = None
            for deg in np.arange(0.0, 150.0, 2.0):
                for s_ in ((1.0, -1.0) if deg else (1.0,)):
                    if not ring_hits(math.radians(s_ * deg)):
                        psi = math.radians(s_ * deg)
                        break
                if psi is not None:
                    break
            if psi is None:
                return None
            if abs(psi) > 0:
                a_, b_ = psi, psi - math.copysign(math.radians(2.0), psi)
                for _ in range(10):
                    m_ = 0.5 * (a_ + b_)
                    a_, b_ = (m_, b_) if not ring_hits(m_) else (a_, m_)
                psi = a_
            ring_hits(psi)
            return psi

        found = None
        for n in range(0, 121):                                   # 1 cm steps, the nearer side first
            for d in ((0.0,) if n == 0 else (-sgn * 0.01 * n, sgn * 0.01 * n)):
                xs_ = x_b + d
                if not (x_lo <= xs_ <= x_hi) or bt.cap_at(xs_)[1] > half_min:
                    continue
                st_ = settle(xs_)
                if st_ is None:
                    continue
                R, t = pose(st_[0], xs_)
                psi = ring_clear(R, t)
                if psi is not None:
                    found = (xs_, st_, R, t, psi)
                    break
            if found:
                break
        if found is None:
            raise ValueError(f"{key} finds no place across {bt.key}'s gunwales")
        x_s, (phi, phi_in), R, t, psi = found
        # what it rests on (its pose just past touching)
        R1, t1 = pose(phi_in, x_s)
        tr = _bvh(Vk @ R1.T + t1, Tk)
        on = sorted(n for n in others if len(tr.overlap(_bvh(*lt[n]))))
        on += ["a load"] * any(len(tr.overlap(o)) for o in obst[1:])
        out = Mesh()
        for part in (an.iron, an.stock, an.ring):
            V, F, M = part.arrays()
            out.add(V @ R.T + t, F, M)
        y_o = bt.cap_at(x_s)[1]
        return out, {"stock_x_m": round(x_s, 3), "stock_off_m": round(x_s - x_b, 3),
                     "shank_down_deg": round(math.degrees(phi), 2), "rests_on": on,
                     "ring_swing_deg": round(math.degrees(psi), 1), "stock_len_ft": round(k["stock_len"] / FT, 2),
                     "breadth_over_cappings_ft": round(2 * y_o / FT, 2),
                     "overhang_in": round((0.5 * k["stock_len"] - y_o) / IN, 1),
                     "stock_on": "+".join(gun)}

    # --- the gripes --------------------------------------------------------------------------------------------------------
    def unit_meshes(self, u, skip=()):
        """every mesh of the unit u in its frame: (V, T), her boat, the gig in her, and each of her pieces"""
        out = [(u["bt"].V_ + u["o"], u["bt"].T_)]
        if "gig" in u:
            out.append((u["gig"]["bt"].V_ + u["gig"]["o"], u["gig"]["bt"].T_))
        for obj, m in u["pieces"].items():
            if obj in skip:
                continue
            V, F, _ = m.arrays()
            out.append((V, fan_tris(F)))
        return out

    def gripes(self, name):
        """a gripe at each of her cradles: from an eyebolt in one end of the cradle up her side, over her gunwales and
        whatever rides in her, down to an eyebolt in its other end, set up taut: over their section's convex hull at the
        cradle (the rope's own thickness clear of it), each end spliced round its eyebolt's eye"""
        u = self.unit(name)
        gc = self.st["gripes"]
        r = 0.5 * gc["circ_in"] / math.pi * IN
        R_e, r_b = 0.5 * gc["eye_in"][0] * IN, 0.5 * gc["eye_in"][1] * IN
        stand = 0.25 * IN + r_b + R_e
        meshes = self.unit_meshes(u, skip=("SpareSpars", "SparSaddles", "BoatGripes", "BoatCradles"))
        SP = _Splicer()
        u["gripes"] = []
        for c in u["cradles"]:
            x = c["x"]
            faces, eyes = [], []
            for yy, sg, ztop in ((c["ya"], -1.0, c["top_ends"][0]), (c["yb"], 1.0, c["top_ends"][1])):
                Q = np.array([x, yy, c["z_cb"] + 0.4 * (ztop - c["z_cb"])])
                faces.append((Q, np.array([0.0, sg, 0.0])))
                eyes.append(Q + [0.0, sg * stand, 0.0])
            pts = []
            for dxx in (-r - 0.5 * IN, 0.0, r + 0.5 * IN):
                for V, T in meshes:
                    s = plane_cut(V, T, x + dxx)
                    if len(s):
                        pts.append(s.reshape(-1, 2))
            pts = np.concatenate(pts + [np.array([[e[1], e[2]] for e in eyes])])
            H = ConvexHull(pts).vertices                     # counter-clockwise (y right, z up)
            ia, ib = len(pts) - 2, len(pts) - 1
            H = list(H)
            if ia not in H or ib not in H:
                raise ValueError(f"{name}'s gripe at {x:.2f}: an eyebolt inside the outline")
            ka, kb_ = H.index(ia), H.index(ib)
            chain = []
            k = kb_
            while True:                                      # counter-clockwise from the starboard eye over the top
                k = (k + 1) % len(H)
                if k == ka:
                    break
                chain.append(pts[H[k]])
            chain = np.array(chain[::-1])                    # from the port eye's side over to the starboard's
            poly = np.concatenate([[eyes[0][1:]], chain, [eyes[1][1:]]])
            seg = np.diff(poly, axis=0)
            nrm = np.stack([seg[:, 1], -seg[:, 0]], -1)
            nrm = nrm / np.linalg.norm(nrm, axis=1)[:, None]
            ctr = pts[H].mean(0)                             # each segment's normal turned away from the hull's middle
            nrm = np.where((((poly[:-1] + poly[1:]) / 2 - ctr) * nrm).sum(1)[:, None] < 0, -nrm, nrm)
            vn = unit(nrm[:-1] + nrm[1:])
            rho = r + 0.05 * IN                              # its centre line off the outline: lying on it
            ch = chain + rho * vn / np.maximum(0.5, (vn * nrm[1:]).sum(1))[:, None]
            # the offset outline's corners (a point every 2 mm at most)
            keep = [0]
            for i in range(1, len(ch)):
                if np.linalg.norm(ch[i] - ch[keep[-1]]) >= 0.002:
                    keep.append(i)
            ch = ch[keep]
            mid = np.c_[np.full(len(ch), x), ch]
            mb = Mesh()
            mb.cur = "gripe eyebolt"
            ends = []
            for (Q, n_), tw in zip(faces, (mid[0], mid[-1])):
                ends.append(SP._spliced_eye(mb, Q, n_, tw, EX, gc))
            # the course starts beyond each splice's lead
            la, lb = ends[0][1], ends[1][1]
            mid = mid[(np.linalg.norm(mid - la, axis=1) > 0.05) & (np.linalg.norm(mid - lb, axis=1) > 0.05)]
            # turned round each corner on rho (about the outline's corner itself: a rope bent round an edge), so it
            # lies on its corners without cutting them; its arcs kept whole
            (sa, la, _), (sb, lb, _) = ends
            P = turned_course(np.concatenate([[sa[-1], la], mid, [lb, sb[-1]]]), rho, 0.1)
            P = np.concatenate([sa[:-1], P, sb[::-1][1:]])
            Vt, Ft = self.AN._tube_open(P, r, 8)
            mb.cur = "gripe"
            mb.add(Vt, Ft, "Hemp")
            V, F, M = mb.arrays()
            self.add(u, "BoatGripes", V, F, M)
            u["gripes"].append({"x_m": round(x, 3), "length_m": round(float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum()), 2)})

    # --- placed in the ship ----------------------------------------------------------------------------------------------
    def place(self):
        """the launch on the middle line (her y_m), each cutter to her side as close as gap_between_boats_in allows
        between the launch's every piece (her boat, what rides in her, her cradles and gripes) and the cutter's, at
        every height all along them (3 cm bins, each the worst of its neighbours too); then everything into the ship's
        frame"""
        import deck
        gap = self.st["gap_between_boats_in"] * IN
        b = 0.03

        def extremes(u):
            P = np.concatenate([deck.surface_points(V, T, 0.015) for V, T in
                                self.unit_meshes(u, ("SpareSpars", "SparSaddles"))])
            key = np.floor(P[:, 0] / b).astype(np.int64) * 100000 + np.floor(P[:, 2] / b).astype(np.int64)
            order = np.argsort(key, kind="stable")
            key, y = key[order], P[order, 1]
            uk, start = np.unique(key, return_index=True)
            return dict(zip(uk.tolist(), np.maximum.reduceat(y, start).tolist())), \
                dict(zip(uk.tolist(), np.minimum.reduceat(y, start).tolist()))

        def grown(d, f):
            out = {}
            for k, v in d.items():
                for di in (-100000, 0, 100000):
                    for dj in (-1, 0, 1):
                        kk = k + di + dj
                        out[kk] = f(out[kk], v) if kk in out else v
            return out
        L = self.unit("Launch")
        L["y"] = float(self.st["boats"]["Launch"].get("y_m", 0.0))
        lmax, lmin = extremes(L)
        lmax, lmin = grown(lmax, max), grown(lmin, min)
        self.info["gaps"] = {}
        for name in ("Cutter_S", "Cutter_P"):
            u = self.unit(name)
            cmax, cmin = extremes(u)
            if self.st["boats"][name]["side"] > 0:
                y = max(lmax[k] - v for k, v in cmin.items() if k in lmax) + gap
            else:
                y = min(lmin[k] - v for k, v in cmax.items() if k in lmin) - gap
            u["y"] = L["y"] + y
            self.info["gaps"][name] = round(u["y"], 4)
        self.objs, self.frames = {}, {}
        for name in ("Launch", "Cutter_S", "Cutter_P"):
            u = self.units[name]
            dy = np.array([0.0, u["y"], 0.0])
            self.frames[name] = (u["bt"], u["o"] + dy)
            if "gig" in u:
                self.frames["Gig"] = (u["gig"]["bt"], u["gig"]["o"] + dy)
            for obj, m in u["pieces"].items():
                V, F, M = m.arrays()
                self.objs.setdefault(obj, Mesh()).add(V + dy, F, M)
            self.info["boats"][name].update({"y_m": round(u["y"], 4), "origin_m": np.round(u["o"] + dy, 4).tolist(),
                                             "gripes": u.get("gripes", [])})
        self.info["boats"]["Gig"] = {"boat": "gig", "origin_m": np.round(self.frames["Gig"][1], 4).tolist(),
                                     **self.info["gig"]}
        self.info["spars"] = self.spar_info
        for name, (bt, o) in self.frames.items():
            self.info["boats"][name]["built"] = bt.info

    def parts(self):
        """name -> (V, F, M, frame): each boat in her own frame (frame: her origin in the ship and her axes, the ship's),
        the rest in the ship's frame (frame None)"""
        out = {}
        for name, (bt, o) in self.frames.items():
            V, F, M = bt.mesh.arrays()
            out[name] = (V, F, M, (np.asarray(o, float), np.eye(3)))
        for obj, m in self.objs.items():
            V, F, M = m.arrays()
            out[obj] = (V, F, M, None)
        return out

    def world(self):
        """every object's triangles in the ship's frame: name -> (V, T)"""
        out = {}
        for name, (V, F, M, fr) in self.parts().items():
            out[name] = (V + fr[0] if fr is not None else V, fan_tris(F))
        return out

    # --- the checks ----------------------------------------------------------------------------------------------------
    def checks(self):
        """each boat's own clash check and the drawing's; her size as built against the card's (within 5%); the gangways'
        clear width under the boats up to headroom over their deck (at least gangway_clear_min_ft); the ladders'
        headroom over every tread and their head (at least ladder_headroom_ft); every spar and saddle an inch inside
        the waist's coamings; the triangles against budget_tris. The boats against the ship and each other is
        build_frigate.py's boats_room"""
        import deck
        st, dk = self.st, self.dk
        out = {"inside": {k: bt.room_["meet"] for k, bt in self.built.items()},
               "inside_by_design": {k: len(bt.room_["by_design"]) for k, bt in self.built.items()},
               "lines_worst_in": {k: bt.lines_["worst_in"] for k, bt in self.built.items()}}
        sizes = {}
        for k, bt in self.built.items():
            b = bt.b
            row = {"length_ft": [bt.info["length_ft"], b["length_ft"]]}
            if b.get("breadth_moulded_ft"):
                row["breadth_moulded_ft"] = [bt.info["breadth_moulded_ft"], b["breadth_moulded_ft"]]
            sizes[k] = {q: v + [round(abs(v[0] / v[1] - 1.0) * 100, 1)] for q, v in row.items()}
        out["sizes"] = sizes
        out["sizes_off"] = [[k, q] for k, r in sizes.items() for q, v in r.items() if v[2] > 5.0]
        W = self.world()
        P = np.concatenate([deck.surface_points(V, T, 0.03) for V, T in W.values()])
        head = st["ladder_headroom_ft"] * FT
        # the gangways
        y_in = dk.y_open + dk.t_coam
        least = {}
        for sg, side in ((1.0, "starboard"), (-1.0, "port")):
            Q = P[(sg * P[:, 1] > y_in)]
            worst = (math.inf, None)
            for x in np.arange(dk.e1, dk.fc, 0.05):
                zd = float(dk.z(x))
                m = (np.abs(Q[:, 0] - x) < 0.025) & (Q[:, 2] < zd + head)
                y_out = float(dk.y_side(x))
                w = y_out - (float(np.max(sg * Q[m, 1])) if m.any() else y_in)
                if w < worst[0]:
                    worst = (w, round(float(x), 2))
            least[side] = {"clear_ft": round(worst[0] / FT, 2), "at_x_m": worst[1]}
        out["gangways"] = least
        out["gangways_narrow"] = [s for s, v in least.items() if v["clear_ft"] < st["gangway_clear_min_ft"]]
        # the ladders
        lc = dk.c["ladders"]
        wi, td = lc["width_in"] * IN, lc["tread_in"][0] * IN
        ang, rise = math.radians(lc["angle_deg"]), lc["rise_in"] * IN
        ladders = []
        for li in dk.ladder_info:
            xe, y0 = li["top_x_m"], li["y_m"]
            d = 1.0 if li["break"] == "quarterdeck" else -1.0
            zt = float(dk.z(xe))
            n = int(round(li["drop_m"] / rise))
            rr = li["drop_m"] / n
            steps = [(xe - d * 0.3, zt, 0.6)] + [(xe + d * (k * rr) / math.tan(ang), zt - k * rr, td)
                                                 for k in range(1, n)]
            low = math.inf
            for x, z, depth in steps:
                m = (np.abs(P[:, 0] - x) <= 0.5 * depth) & (np.abs(P[:, 1] - y0) <= 0.5 * wi) & (P[:, 2] > z)
                if m.any():
                    low = min(low, float(P[m, 2].min() - z))
            ladders.append({"break": li["break"], "y_m": y0, "headroom_ft": round(low / FT, 2) if low < math.inf else None})
        out["ladders"] = ladders
        out["ladders_low"] = [lad for lad in ladders if lad["headroom_ft"] is not None and
                              lad["headroom_ft"] < st["ladder_headroom_ft"]]
        # the coamings
        Vs = np.concatenate([W[n][0] for n in ("SpareSpars", "SparSaddles")])
        out["coaming_clear_in"] = round((dk.y_open - float(np.abs(Vs[:, 1]).max())) / IN, 2)
        # triangles
        tris_ = {n: int(len(T)) for n, (V, T) in W.items()}
        out["triangles"] = tris_
        out["triangles_total"] = sum(tris_.values())
        out["over_budget"] = out["triangles_total"] > st["budget_tris"]
        self.info["checks"] = out
        return out

    def failures(self):
        """what the checks found wrong (empty when all pass)"""
        c = self.info["checks"]
        bad = {}
        for k in ("sizes_off", "gangways_narrow", "ladders_low"):
            if c[k]:
                bad[k] = c[k]
        if any(c["inside"].values()):
            bad["inside"] = {k: v for k, v in c["inside"].items() if v}
        if c["coaming_clear_in"] < 1.0:
            bad["coaming_clear_in"] = c["coaming_clear_in"]
        if c["over_budget"]:
            bad["triangles_total"] = c["triangles_total"]
        return bad
