#!/usr/bin/env python3
"""Counts whitecaps on a -SailingDebugFoam still (white caps on black water) using its camera.json.

Each water pixel's ray is put on the plane z = 0 (pinhole, hfov and pitch from camera.json), which gives its distance
and its patch of surface. Cover per distance band = white pixels / water pixels (pixels that are neither black nor
white, the boat and the sky, are left out). Caps are 8-connected white blobs (after a 1-pixel close, since the debug
view draws a cap's soft edge as a hashed share of white pixels); each is measured on the plane: its length along the
wind is its extent along the camera's look direction or across it, whichever is longer (the major axis of the
projected points), its width the minor axis.

Usage: count_caps.py <still.png> [...]   prints one block per still.
"""
import json, math, sys
import numpy as np
from PIL import Image
from scipy import ndimage

BANDS = [(5, 10), (10, 20), (20, 40), (40, 80), (80, 160), (160, 320)]


def ground(cam, w, h, roll_sign=1.0):
    hf = math.radians(cam["hfov_deg"])
    f = (w / 2) / math.tan(hf / 2)
    pitch = math.radians(cam["camera_pitch_yaw_roll_deg"][0])
    z = cam["camera_m"][2]
    u = (np.arange(w) + 0.5 - w / 2)[None, :].repeat(h, 0)
    v = (np.arange(h) + 0.5 - h / 2)[:, None].repeat(w, 1)
    # Camera frame: forward x, right y, up z; pitch about y (negative looks down).
    dx, dy, dz = np.full_like(u, f), u, -v
    roll = roll_sign * math.radians(cam["camera_pitch_yaw_roll_deg"][2])
    cr, sr = math.cos(roll), math.sin(roll)
    dy, dz = dy * cr - dz * sr, dy * sr + dz * cr
    c, s = math.cos(pitch), math.sin(pitch)
    fx, fz = dx * c - dz * s, dx * s + dz * c
    t = np.where(fz < -1e-6, z / -np.minimum(fz, -1e-6), np.nan)
    return fx * t, dy * t  # forward and right on the water, metres from below the camera


def count(path):
    cam = json.load(open(path.replace(".png", ".camera.json")))
    img = np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255
    h, w, _ = img.shape
    lum = img.mean(2)
    chroma = img.max(2) - img.min(2)
    black = (lum < 0.12) & (chroma < 0.08)
    # The roll's sign: the one that puts the fewest black (water) pixels above the horizon.
    best = None
    for sgn in (1.0, -1.0):
        X, Y = ground(cam, w, h, sgn)
        bad = int((black & ~np.isfinite(X)).sum())
        if best is None or bad < best[0]:
            best = (bad, X, Y)
    _, X, Y = best
    d = np.hypot(X, Y)
    # A cap is white enclosed by the black water (the deck, sails and sky are not): holes in the water under 3000 px.
    holes = ndimage.binary_fill_holes(black) & ~black
    lab, _ = ndimage.label(holes, structure=np.ones((3, 3)))
    big = np.bincount(lab.ravel())
    holes &= big[lab] < 3000
    white = holes & (lum > 0.5)
    water = (black | white) & np.isfinite(d)
    # The debug view's uniform floor: isolated white pixels (a cover of a few tenths of a percent everywhere, far below
    # anything the eye sees: the beauty pass draws it as foam opacity 0.003). Caps are the clusters.
    lab0, _ = ndimage.label(white, structure=np.ones((3, 3)))
    sz0 = np.bincount(lab0.ravel()); sz0[0] = 0
    salt = white & (sz0[lab0] <= 2)
    out_salt = round(100 * float((salt & water & (d < 80)).sum()) / max(int((water & (d < 80)).sum()), 1), 3)
    white = white & ~salt
    # Each pixel's patch of water (m^2), for area-weighted cap sizes and pooled cover.
    gxu, gxv = np.gradient(X); gyu, gyv = np.gradient(Y)
    A = np.abs(gxu * gyv - gxv * gyu)
    out = {"still": path.split("/")[-1], "wind_kn": cam.get("true_wind_kn"), "bands": {}}
    tot_w = tot_n = 0
    for a, b in BANDS:
        m = water & (d >= a) & (d < b)
        n = int(m.sum())
        if n < 2000:
            continue
        cw = int((white & m).sum())
        out["bands"][f"{a}-{b} m"] = round(100 * cw / n, 3)
        if b <= 80:
            tot_w += cw; tot_n += n
    out["cover_5_80m_pct"] = round(100 * tot_w / max(tot_n, 1), 3)
    out["isolated_pixel_floor_pct"] = out_salt
    # Caps within 60 m, where a 1 m cap still spans several pixels.
    blob = ndimage.binary_closing(white & water, structure=np.ones((3, 3)))
    lab, nlab = ndimage.label(blob, structure=np.ones((3, 3)))
    sizes = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        mm = lab[sl] == i
        if mm.sum() < 10:
            continue
        xs, ys, ds = X[sl][mm], Y[sl][mm], d[sl][mm]
        if not np.isfinite(ds).all() or ds.mean() > 60 or ds.mean() < 5:
            continue
        P = np.stack([xs - xs.mean(), ys - ys.mean()])
        ev, evec = np.linalg.eigh(np.cov(P))
        proj = evec.T @ P
        L = proj[1].max() - proj[1].min()
        W = proj[0].max() - proj[0].min()
        sizes.append((L, W, ds.mean(), float(A[sl][mm].sum())))
    if sizes:
        S = np.array(sizes)
        out["caps_5_60m"] = len(S)
        out["cap_length_median_m"] = round(float(np.median(S[:, 0])), 2)
        out["cap_length_p90_m"] = round(float(np.percentile(S[:, 0], 90)), 2)
        out["cap_width_median_m"] = round(float(np.median(S[:, 1])), 2)
        out["cap_aspect_median"] = round(float(np.median(S[:, 0] / np.maximum(S[:, 1], 0.05))), 2)
        out["cap_length_areaweighted_m"] = round(float((S[:, 0] * S[:, 3]).sum() / S[:, 3].sum()), 2)
    m = water & (d >= 10) & (d < 80)
    out["_pool"] = (float((A * (white & m)).sum()), float((A * m).sum()), sizes)
    return out


if __name__ == "__main__":
    pools = {}
    for p in sys.argv[1:]:
        o = count(p)
        cw, cn, sz = o.pop("_pool")
        print(json.dumps(o))
        k = round(o["wind_kn"] or 0)
        q = pools.setdefault(k, [0.0, 0.0, [], 0])
        q[0] += cw; q[1] += cn; q[2] += sz; q[3] += 1
    # Pooled over the stills at each wind: cover by water area 10-80 m, caps 5-60 m.
    for k, (cw, cn, sz, n) in sorted(pools.items()):
        S = np.array(sz) if sz else np.zeros((0, 4))
        aw = (S[:, 0] * S[:, 3]).sum() / max(S[:, 3].sum(), 1e-9) if len(S) else 0
        print(json.dumps({"pooled_wind_kn": k, "stills": n, "water_m2_10_80m": round(cn), "cover_pct": round(100 * cw / max(cn, 1e-9), 3),
                          "caps": len(S), "cap_length_median_m": round(float(np.median(S[:, 0])), 2) if len(S) else None,
                          "cap_length_areaweighted_m": round(float(aw), 2),
                          "cap_length_p90_m": round(float(np.percentile(S[:, 0], 90)), 2) if len(S) else None}))
