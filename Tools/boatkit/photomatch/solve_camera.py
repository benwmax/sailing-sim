"""Solve a photo's camera from a handful of picked points, so the boat can be rendered from exactly where the photo
was taken (the "photo match loop").

Input (matches/<photo>.json, numbers only, so it can live in the public repo even when the photo cannot):
  {"photo": "IMG_9224.jpg", "size": [4032, 3024],
   "points": [{"name": "BowCleat", "px": [1810, 1322]}, {"name": "TransomTopS", "xyz": [-3.40, -0.92, 0.78], "px": [..]}]}
A point is a socket name from the boat's sockets file (or a named landmark in landmarks.json) or an explicit "xyz" in
Blender metres (X forward, Y port, Z up). Six or more points spread over the boat give a stable solve.

Model: pinhole, square pixels, principal point at the image centre, unknown focal length (phone lenses crop and
digital zoom changes it). Linear DLT start, then Levenberg-Marquardt on rotation, position and focal.
Output: <photo>.camera.json with the Blender camera (location, rotation quaternion, lens for a 36 mm sensor width) and
the per-point reprojection error in pixels.

  python3 Tools/boatkit/photomatch/solve_camera.py <matches.json> <sockets.json> [landmarks.json]
  python3 Tools/boatkit/photomatch/solve_camera.py --selftest
"""
import json
import math
import os
import sys

import numpy as np


def rodrigues(r):
    th = np.linalg.norm(r)
    if th < 1e-12:
        return np.eye(3)
    k = r / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


def to_rvec(R):
    c = max(-1.0, min(1.0, (np.trace(R) - 1) / 2))
    th = math.acos(c)
    if th < 1e-9:
        return np.zeros(3)
    v = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(th))
    return v * th


def project(params, X, cx, cy):
    """Camera looks along +z_cam, image y down (OpenCV convention). params = rvec(3), t(3), f."""
    R = rodrigues(params[:3])
    t = params[3:6]
    f = params[6]
    Xc = X @ R.T + t
    return np.stack([f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy], axis=1), Xc


def dlt(X, x):
    A = []
    for (Xw, Yw, Zw), (u, v) in zip(X, x):
        A.append([Xw, Yw, Zw, 1, 0, 0, 0, 0, -u * Xw, -u * Yw, -u * Zw, -u])
        A.append([0, 0, 0, 0, Xw, Yw, Zw, 1, -v * Xw, -v * Yw, -v * Zw, -v])
    _, _, Vt = np.linalg.svd(np.array(A))
    return Vt[-1].reshape(3, 4)


def start_from_dlt(X, x, cx, cy):
    P = dlt(X, x - np.array([cx, cy]))
    M = P[:, :3]
    # RQ of M = K R with K = diag(f, f, 1) (approximately); take f from the row norms
    if np.linalg.det(M) < 0:
        P = -P
        M = -M
    f = (np.linalg.norm(M[0]) + np.linalg.norm(M[1])) / (2 * np.linalg.norm(M[2]))
    s = 1 / np.linalg.norm(M[2])
    R = np.vstack([M[0] / f, M[1] / f, M[2]]) * s
    U, _, Vt = np.linalg.svd(R)
    R = U @ Vt
    t = np.array([P[0, 3] / f, P[1, 3] / f, P[2, 3]]) * s
    return np.concatenate([to_rvec(R), t, [f]])


def refine(p, X, x, cx, cy, iters=200, fixed_f=None):
    lam = 1e-3
    def res(q):
        if fixed_f is not None:
            q = np.concatenate([q[:6], [fixed_f]])
        u, Xc = project(q, X, cx, cy)
        return (u - x).ravel()
    if fixed_f is not None:
        p = p[:6]
    r = res(p)
    for _ in range(iters):
        J = np.zeros((len(r), len(p)))
        for j in range(len(p)):
            d = np.zeros(len(p))
            d[j] = 1e-6 * max(1.0, abs(p[j]))
            J[:, j] = (res(p + d) - r) / d[j]
        H = J.T @ J
        g = J.T @ r
        step = np.linalg.solve(H + lam * np.diag(np.diag(H) + 1e-12), -g)
        r2 = res(p + step)
        if r2 @ r2 < r @ r:
            p, r = p + step, r2
            lam *= 0.3
            if np.linalg.norm(step) < 1e-10:
                break
        else:
            lam *= 10
    if fixed_f is not None:
        p = np.concatenate([p, [fixed_f]])
    return p, r.reshape(-1, 2)


def look_at_params(C, target, f):
    """Pose parameters for a camera at C looking at target with the image up roughly world +Z."""
    z = target - C
    z /= np.linalg.norm(z)
    x = np.cross(z, [0, 0, 1.0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.vstack([x, y, z])
    return np.concatenate([to_rvec(R), -R @ C, [f]])


def solve_fixed_focal(X, x, size, f):
    """Few or nearly coplanar points (a deck seen from a dock): fix the focal length from the lens and search starting
    poses around the boat, keeping the best Levenberg-Marquardt result."""
    cx, cy = size[0] / 2, size[1] / 2
    centre = X.mean(0)
    best = None
    for az in range(0, 360, 20):
        for dist in (5.0, 8.0, 12.0, 18.0):
            for h in (0.5, 2.0, 4.0):
                a = math.radians(az)
                C = centre + np.array([dist * math.cos(a), dist * math.sin(a), h])
                p0 = look_at_params(C, centre, f)
                u, Xc = project(p0, X, cx, cy)
                if (Xc[:, 2] <= 0).any():
                    continue
                p, r = refine(p0, X, x, cx, cy, iters=60, fixed_f=f)
                _, Xc = project(p, X, cx, cy)
                if (Xc[:, 2] <= 0).any():
                    continue
                e = (r ** 2).sum()
                if best is None or e < best[0]:
                    best = (e, p, r)
    p, r = refine(best[1], X, x, cx, cy, iters=200, fixed_f=f)
    return p, r


def solve(X, x, size):
    cx, cy = size[0] / 2, size[1] / 2
    p = start_from_dlt(X, x, cx, cy)
    p, r = refine(p, X, x, cx, cy)
    return p, r


def blender_camera(p, size):
    """Camera pose in Blender terms: location, rotation (quaternion w, x, y, z) of a camera looking down its -Z with
    +Y up, and the lens in mm for a 36 mm sensor fitted to the image width."""
    R = rodrigues(p[:3])
    t = p[3:6]
    C = -R.T @ t
    # OpenCV camera axes (x right, y down, z forward) -> Blender camera axes (x right, y up, z back)
    Rb = R.T @ np.diag([1, -1, -1])
    w = math.sqrt(max(0.0, 1 + Rb[0, 0] + Rb[1, 1] + Rb[2, 2])) / 2
    if w > 1e-6:
        q = [w, (Rb[2, 1] - Rb[1, 2]) / (4 * w), (Rb[0, 2] - Rb[2, 0]) / (4 * w), (Rb[1, 0] - Rb[0, 1]) / (4 * w)]
    else:
        i = int(np.argmax(np.diag(Rb)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(1 + Rb[i, i] - Rb[j, j] - Rb[k, k]) * 2
        q = [0, 0, 0, 0]
        q[0] = (Rb[k, j] - Rb[j, k]) / s
        q[1 + i] = s / 4
        q[1 + j] = (Rb[j, i] + Rb[i, j]) / s
        q[1 + k] = (Rb[k, i] + Rb[i, k]) / s
    lens = p[6] * 36.0 / size[0]
    return {"location": [float(v) for v in C], "rotation_quaternion": [float(v) for v in q], "lens_mm": float(lens),
            "sensor_width_mm": 36.0, "resolution": list(size)}


def load_points(matches, sockets, landmarks):
    X, x, names = [], [], []
    for pt in matches["points"]:
        if "xyz" in pt:
            xyz = pt["xyz"]
        elif pt["name"] in sockets:
            v = sockets[pt["name"]]
            xyz = [v[0] / 100, -v[1] / 100, v[2] / 100]       # Unreal cm, Y starboard -> Blender m, Y port
        elif pt["name"] in landmarks:
            xyz = landmarks[pt["name"]]
        else:
            raise KeyError(f"Unknown point {pt['name']}: not a socket or landmark and no xyz")
        X.append(xyz)
        x.append(pt["px"])
        names.append(pt["name"])
    return np.array(X, float), np.array(x, float), names


def selftest():
    rng = np.random.default_rng(3)
    X = rng.uniform([-3.4, -1.2, 0], [3.4, 1.2, 1.4], (10, 3))
    size = (4032, 3024)
    truth = np.concatenate([to_rvec(rodrigues(np.array([1.9, 0.3, -0.4]))), [0.2, -0.3, 7.5], [3100]])
    x, _ = project(truth, X, size[0] / 2, size[1] / 2)
    x += rng.normal(0, 1.0, x.shape)                       # one pixel of picking noise
    p, r = solve(X, x, size)
    err_f = abs(p[6] - truth[6]) / truth[6]
    C_true = -rodrigues(truth[:3]).T @ truth[3:6]
    C = -rodrigues(p[:3]).T @ p[3:6]
    print(f"selftest: rms {np.sqrt((r ** 2).sum(1).mean()):.2f} px, focal error {100 * err_f:.2f}%, "
          f"camera position error {100 * np.linalg.norm(C - C_true):.1f} cm")
    assert err_f < 0.02 and np.linalg.norm(C - C_true) < 0.10
    q, r2 = solve_fixed_focal(X[:5], x[:5], size, truth[6])
    C2 = -rodrigues(q[:3]).T @ q[3:6]
    print(f"selftest (fixed focal, 5 points): camera position error {100 * np.linalg.norm(C2 - C_true):.1f} cm")
    assert np.linalg.norm(C2 - C_true) < 0.25
    print("selftest: ok")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    mpath, spath = sys.argv[1], sys.argv[2]
    landmarks = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else {}
    matches = json.load(open(mpath))
    lens35 = matches.get("lens_35mm_equiv")
    sockets = json.load(open(spath))["sockets"]
    X, x, names = load_points(matches, sockets, landmarks)
    # points marked "solve": false are checks: left out of the solve, reported against the solved camera
    use = np.array([pt.get("solve", True) for pt in matches["points"]])
    Xall, xall, names_all = X, x, names
    X, x = X[use], x[use]
    names = [n for n, u in zip(names, use) if u]
    if lens35:
        if len(X) < 4:
            raise SystemExit(f"{len(X)} points: pick at least 4 with a known lens")
        f = lens35 / 36.0 * matches["size"][0]
        p, r = solve_fixed_focal(X, x, matches["size"], f)
    else:
        if len(X) < 6:
            raise SystemExit(f"{len(X)} points: pick at least 6 off one plane, or give lens_35mm_equiv")
        p, r = solve(X, x, matches["size"])
    cam = blender_camera(p, matches["size"])
    err = np.sqrt((r ** 2).sum(1))
    cam["photo"] = matches["photo"]
    cam["residual_px"] = {n: round(float(e), 1) for n, e in zip(names, err)}
    cam["rms_px"] = round(float(np.sqrt((err ** 2).mean())), 2)
    u_all, _ = project(p, Xall, matches["size"][0] / 2, matches["size"][1] / 2)
    cam["checks_px"] = {n: {"error_px": round(float(np.linalg.norm(u - q)), 1), "model_px": [round(float(c)) for c in u]}
                        for n, u, q, k in zip(names_all, u_all, xall, use) if not k}
    out = os.path.splitext(mpath)[0] + ".camera.json"
    json.dump(cam, open(out, "w"), indent=1)
    print(f"Photomatch: {matches['photo']}: rms {cam['rms_px']} px over {len(X)} points, lens {cam['lens_mm']:.1f} mm -> {out}")
    worst = sorted(cam["residual_px"].items(), key=lambda kv: -kv[1])[:3]
    print("Photomatch: worst points " + ", ".join(f"{n} {e} px" for n, e in worst))
    for n, c in cam["checks_px"].items():
        print(f"Photomatch: check {n}: the model puts it {c['error_px']} px from the photo (at {c['model_px']})")


if __name__ == "__main__":
    main()
