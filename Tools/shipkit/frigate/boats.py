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

import loft

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
