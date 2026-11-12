"""Where each view of a lines plan scan lies in the ship's frame (docs/shipkit-1).

A scanned lines plan is three drawings on one sheet that has been folded, stored and photographed: the views are not
exactly square to the scan or to each other, and the scan is not to the same scale across and down. The ship's frame is the half-breadth plan's: x along it in scan pixels
(the stations where its dashed station lines cross the centreline), half-breadths from its centreline. The registration
in a drawing json (Tools/shipkit/frigate/drawing_1927.json) says where the other two views sit against that:

  half_breadth.centreline_y   the centreline's scan y along x (read every 50 px; the paper is not flat)
  sheer.waterline_A_y         the load waterline's scan y along x: heights are measured up from it
  sheer.x_registration        the sheer plan's station lines: their scan x where they cross A, their tilt (scan x per
                              px down) and the station's x in the ship's frame. Between and beyond them x is
                              interpolated linearly: the sheer plan is drawn 8-15 px aft of the half-breadth plan
  body.origin_px              where the body plan's centreline crosses its load waterline
  body.waterline_slope        the load waterline's scan dy/dx in the body plan (the view is turned about 0.85 deg)
  body.centreline_slope       the centreline's scan dx/dy
  px_per_ft, px_per_ft_down   the scan's scale across and down the sheet: it is 5.3% taller than wide. The ship's frame
                              keeps the half-breadth plan's own pixels (lengths across, half-breadths and heights
                              down), so the body plan's half-breadths, read across the sheet, are scaled by their ratio

Readings kept in an offsets json are in each view's nominal frame (scan x and height above the waterline table for the
sheer plan, a fixed centre and waterline for the body plan); loft.py maps them into the ship's frame through here, and
lines_check.py maps the built hull back onto the scan the same way.
"""
import json

import numpy as np


class ScanRegistration:
    def __init__(self, path):
        self.d = json.load(open(path))
        v = self.d["views"]
        c = np.array(v["half_breadth"]["centreline_y"], float)
        self._cl = (c[:, 0], c[:, 1])
        a = np.array(v["sheer"]["waterline_A_y"], float)
        self._wa = (a[:, 0], a[:, 1])
        xr = v["sheer"]["x_registration"]
        st = sorted(xr["stations"], key=lambda s: s[0])
        self._sx = np.array([s[0] for s in st], float)     # sheer plan scan x at A
        self._tilt = np.array([s[1] for s in st], float)   # scan x per px down the station line
        self._shipx = np.array([s[2] for s in st], float)  # the station in the ship's frame
        b = v["body"]
        self._bo = np.array(b["origin_px"], float)
        e_hb = np.array([1.0, b["waterline_slope"]])
        e_up = np.array([-b["centreline_slope"], -1.0])
        self._bm = np.stack([e_hb / np.linalg.norm(e_hb), e_up / np.linalg.norm(e_up)], 1)   # columns: hb, up
        self._bmi = np.linalg.inv(self._bm)
        self.body_nominal = b.get("nominal", None)
        self.ppf_x = float(self.d["px_per_ft"])
        self.ppf_y = float(self.d.get("px_per_ft_down", self.ppf_x))
        self.down = self.ppf_y / self.ppf_x          # a half-breadth read across the sheet, in down-the-sheet pixels

    # --- half-breadth plan ---------------------------------------------------------------------------------------------
    def centreline_y(self, x):
        return np.interp(x, *self._cl)

    # --- sheer plan ------------------------------------------------------------------------------------------------------
    def waterline_A_y(self, x):
        return np.interp(x, *self._wa)

    @staticmethod
    def _lin(x, xp, fp):
        """Piecewise linear through (xp, fp), carried on straight past either end."""
        x = np.asarray(x, float)
        y = np.interp(x, xp, fp)
        lo, hi = x < xp[0], x > xp[-1]
        y = np.where(lo, fp[0] + (x - xp[0]) * (fp[1] - fp[0]) / (xp[1] - xp[0]), y)
        return np.where(hi, fp[-1] + (x - xp[-1]) * (fp[-1] - fp[-2]) / (xp[-1] - xp[-2]), y)

    def sheer_to_ship_x(self, x_scan, z):
        """A sheer plan reading (scan x, height above A in px) to x in the ship's frame."""
        tilt = np.interp(x_scan, self._sx, self._tilt)
        return self._lin(np.asarray(x_scan, float) + tilt * np.asarray(z, float), self._sx, self._shipx)

    def ship_to_sheer(self, x_ship, z):
        """A point (ship x, height above A, px) to scan pixels in the sheer plan."""
        xa = self._lin(x_ship, self._shipx, self._sx)
        xs = xa - np.interp(xa, self._sx, self._tilt) * np.asarray(z, float)
        return xs, self.waterline_A_y(xs) - z

    # --- body plan -------------------------------------------------------------------------------------------------------
    def body_scan_to_ship(self, x, y):
        """Scan pixels in the body plan to (signed half-breadth, height above A) in the ship's frame: negative
        half-breadths are left."""
        d = np.stack([np.asarray(x, float) - self._bo[0], np.asarray(y, float) - self._bo[1]])
        hb, z = self._bmi @ d.reshape(2, -1)
        return hb.reshape(np.shape(x)) * self.down, z.reshape(np.shape(x))

    def body_nominal_to_ship(self, hb, z, left):
        """A body plan reading taken against the nominal centre and waterline (body.nominal) to the ship's frame."""
        xc, ya = self.body_nominal
        x = xc - np.asarray(hb, float) if left else xc + np.asarray(hb, float)
        h, zz = self.body_scan_to_ship(x, ya - np.asarray(z, float))
        return np.abs(h), zz

    def ship_to_body(self, hb, z, left):
        """(half-breadth, height above A) in the ship's frame to scan pixels in the body plan's left or right half."""
        s = -1.0 if left else 1.0
        hb, z = np.broadcast_arrays(np.asarray(hb, float), np.asarray(z, float))
        P = self._bo[:, None] + self._bm @ np.stack([s * hb.ravel() / self.down, z.ravel()])
        return P[0].reshape(hb.shape), P[1].reshape(hb.shape)
