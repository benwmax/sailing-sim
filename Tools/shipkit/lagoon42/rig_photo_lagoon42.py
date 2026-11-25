"""The Lagoon 42's rig read from the CC BY drone photo (slice 6, docs/lagoon42-7): numbers only, the photo is not in the
repo (match_two_canoes.json says which photo and where its picks come from).

    python3 -I rig_photo_lagoon42.py [--camera out.json]

Slice 3's camera (match_two_canoes.json, hull points only) leaves the camera's roll and height loosely held: its
points lie near one plane. The sea's horizon is level, so three picks along it hold the roll. This solves the camera
again with the hull points and the horizon together (each horizon pick's ray must be level), then reads the rig
through it: each pick is a pixel on a part of the rig whose plan position is known (the mast's axis, the centreline),
so its height comes from where its ray passes that line or plane. The mast's own picks, up its length, check the
solve (an upright mast at x -0.42 should pass through all of them).

What it reads (rig_lagoon42.json takes these numbers, rounded):
  hounds          the forestay's and caps' tang on the mast
  spreaders       their roots on the mast, and both tips solved together as a symmetric pair (aft, out, up); each
                  tip's height alone shows how far the two disagree
  boom            the lazy bag's top and bottom where they meet the mast (the gooseneck's pin is under the bottom)
  mast foot       where the mast meets the roof: a check on the roof's height (3.26)
What it doesn't: the self-tacking track and the chainplates were placed by eye on the photo, and the radar dome and the
mast's colour were looked at; their points are printed as pixels to compare by eye.

Pure numpy. Frame: Blender's (X forward, Y to port, Z up), metres over the game's waterline, as match_two_canoes.json.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "boatkit", "photomatch"))
import solve_camera as SC  # noqa: E402

HORIZON = [(80, 347.0), (650, 357.5), (950, 365.5)]   # the sea's horizon, picked on 4x crops (px)
MAST_X = -0.42
MAST_AXIS = [(401.0, 14), (404.5, 134), (407.0, 234), (408.3, 334), (408.0, 424)]   # the mast's middle, top to bottom
PICKS = {   # name: (u, v) px, picked by eye on 4x and 6x crops in the desktop app's browser
    "hounds_tang": (402, 62),
    "spreader_root_left": (404.6, 270.1),
    "spreader_root_right": (412.3, 268.7),
    "spreader_tip_left": (349.3, 266.3),       # the starboard tip (the photo looks from off her starboard bow)
    "spreader_tip_right": (433.3, 268.4),      # the port tip
    "bag_top_at_mast": (404, 445),
    "bag_bottom_at_mast": (404, 468),
    "roof_at_mast_foot": (407, 514),
}
CHECKS = {  # model points (game frame: X forward, Y starboard, Z up) printed as pixels, to compare by eye
    "cap chainplate, starboard": (-2.25, 3.72, 1.63),
    "lower chainplate, starboard": (-1.05, 3.6, 1.63),
    "self-tacking track, middle": (0.49, 0.0, 3.3),
    "self-tacking track, starboard end": (0.83, 1.9, 3.3),
    "radar dome": (-0.05, 0.0, 11.4),
    "masthead": (-0.47, 0.0, 20.48),
}


def lm(fun, q, iters=100):
    """Levenberg-Marquardt with a forward-difference Jacobian (no scipy)."""
    lam = 1e-3
    r = fun(q)
    for _ in range(iters):
        J = np.empty((len(r), len(q)))
        for i in range(len(q)):
            h = 1e-6 * max(1.0, abs(q[i]))
            dq = q.copy()
            dq[i] += h
            J[:, i] = (fun(dq) - r) / h
        A, g = J.T @ J, J.T @ r
        while True:
            step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-12), -g)
            r2 = fun(q + step)
            if r2 @ r2 < r @ r:
                q, r, lam = q + step, r2, lam * 0.3
                break
            lam *= 10.0
            if lam > 1e12:
                return q
        if np.linalg.norm(step) < 1e-10 * (1.0 + np.linalg.norm(q)):
            break
    return q


def from_blender(c, W):
    """solve_camera's parameters (Rodrigues vector, translation, focal in px) from a Blender camera json."""
    w, x, y, z = c["rotation_quaternion"]
    Rb = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                   [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                   [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    Rcv = (Rb @ np.diag([1, -1, -1])).T
    return np.concatenate([SC.to_rvec(Rcv), -Rcv @ np.array(c["location"]), [c["lens_mm"] * W / c["sensor_width_mm"]]])


class Camera:
    def __init__(self, q, size):
        self.R, self.t, self.f = SC.rodrigues(q[:3]), q[3:6], q[6]
        self.L = -self.R.T @ self.t
        self.cx, self.cy = size[0] / 2, size[1] / 2

    def ray(self, u, v):
        d = self.R.T @ np.array([(u - self.cx) / self.f, (v - self.cy) / self.f, 1.0])
        return d / np.linalg.norm(d)

    def project(self, p):
        c = self.R @ np.array(p, float) + self.t
        return self.cx + self.f * c[0] / c[2], self.cy + self.f * c[1] / c[2]

    def near_line(self, u, v, a, e):
        """The point on the line a + t e nearest the pick's ray, and how far the ray passes from it (m)."""
        d, a, e = self.ray(u, v), np.array(a, float), np.array(e, float) / np.linalg.norm(e)
        w0 = self.L - a
        b, dd, ee = d @ e, d @ w0, e @ w0
        s, t = (b * ee - dd) / (1 - b * b), (ee - b * dd) / (1 - b * b)
        return a + t * e, float(np.linalg.norm(self.L + s * d - (a + t * e)))


def solve():
    M = json.load(open(os.path.join(HERE, "match_two_canoes.json")))
    C0 = json.load(open(os.path.join(HERE, "match_two_canoes.camera.json")))
    pts = [p for p in M["points"] if p.get("solve", True)]
    X = np.array([p["xyz"] for p in pts])
    x = np.array([p["px"] for p in pts])
    W, H = M["size"]

    def residuals(q):
        pr, _ = SC.project(q[:7], X, W / 2, H / 2)
        r = list((pr - x).ravel())
        R, f = SC.rodrigues(q[:3]), q[6]
        for u, v in HORIZON:        # a level ray's height over the horizontal, in px at the focal length
            d = R.T @ np.array([(u - W / 2) / f, (v - H / 2) / f, 1.0])
            r.append(f * d[2] / math.hypot(d[0], d[1]))
        return np.array(r)

    q0 = from_blender(C0, W)
    q = lm(residuals, q0)
    res = residuals(q)
    n = 2 * len(X)
    return q, (W, H), {"hull_rms_px": float(np.sqrt(np.mean(res[:n] ** 2))), "horizon_px": [round(float(v), 2) for v in res[n:]],
                       "start_hull_rms_px": float(np.sqrt(np.mean(residuals(q0)[:n] ** 2)))}


def main():
    q, size, fit = solve()
    cam = Camera(q, size)
    bc = SC.blender_camera(q, size)
    print(f"camera: hull points {fit['hull_rms_px']:.2f} px rms (slice 3's {fit['start_hull_rms_px']:.2f}), horizon "
          f"{fit['horizon_px']} px, lens {bc['lens_mm']:.2f} mm at {np.round(bc['location'], 2).tolist()}")
    up = (0.0, 0.0, 1.0)
    axis = (MAST_X, 0.0, 0.0)
    off = [cam.near_line(u, v, axis, up)[1] for u, v in MAST_AXIS]
    print("mast picks off an upright mast at x -0.42:", [round(m, 3) for m in off], "m")
    z = {k: cam.near_line(*PICKS[k], axis, up)[0][2] for k in
         ("hounds_tang", "spreader_root_left", "spreader_root_right", "bag_top_at_mast", "bag_bottom_at_mast", "roof_at_mast_foot")}
    for k, v in z.items():
        print(f"{k:22s} z {v:6.2f}")

    def tips(p):
        a = cam.project((p[0], p[1], p[2]))     # Blender frame: +Y is port, so the photo's left tip is at -Y
        b = cam.project((p[0], -p[1], p[2]))
        L, R = PICKS["spreader_tip_left"], PICKS["spreader_tip_right"]
        return np.array([b[0] - L[0], b[1] - L[1], a[0] - R[0], a[1] - R[1]])
    t = lm(tips, np.array([-1.1, 1.9, 11.4]))
    sweep = math.degrees(math.atan2(MAST_X - t[0], t[1]))
    print(f"spreader tips (symmetric): x {t[0]:.2f} (aft of the mast {MAST_X - t[0]:.2f}), out {t[1]:.2f}, z {t[2]:.2f}; "
          f"swept {sweep:.1f} deg; misfit {np.round(tips(t), 1).tolist()} px")
    for name, sgn in (("spreader_tip_left", -1), ("spreader_tip_right", 1)):
        p, _ = cam.near_line(*PICKS[name], (t[0], sgn * t[1], 0.0), up)
        print(f"{name:22s} alone: z {p[2]:.2f}")
    for k, (gx, gy, gz) in CHECKS.items():
        print(f"check {k:34s} at px {np.round(cam.project((gx, -gy, gz)), 1).tolist()}")
    if "--camera" in sys.argv:
        json.dump(bc, open(sys.argv[sys.argv.index("--camera") + 1], "w"), indent=1)


if __name__ == "__main__":
    main()
