"""Water W6 LES pilot: what the near-surface wind of the North Texas afternoon CBL (ntxcbl) says about the game's wind
field (FWindField: GustIntensity, GustLengthMeters, ShiftDegrees, ShiftPeriodSeconds). Reads MicroHH's xy
cross-sections (12.5, 62.5 and 212.5 m, every 60 s) over the saved last hour and the statistics file.
Writes docs/water-6/les-pilot.json (the numbers) and the figures docs/water-6/speed-12m.png, w-225m.png,
spectrum.png. Usage (WSL): python3 Tools/les/analyse_pilot.py [work dir, default /root/les-runs/ntxcbl] [tag, e.g. -lake]"""
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs", "water-6")
N, L = 400, 10000.0
DX = L / N
KN = 0.514444


STAGGER = {"u": "100", "v": "010", "w": "001", "th": "000"}   # MicroHH names cross-sections <var>.xy.<stagger>.<k>.<time>


def read(work, var, k, t):
    """A level of an xy cross-section: k is the cell index for u, v and th (0 = 12.5 m), the face index for w (9 = 225 m)."""
    f = os.path.join(work, f"{var}.xy.{STAGGER[var]}.{k:05d}.{t:07d}")
    return np.fromfile(f, dtype="<f8").reshape(N, N) if os.path.exists(f) else None


def times(work):
    return sorted({int(p.rsplit(".", 1)[1]) for p in glob.glob(os.path.join(work, "u.xy.100.00000.*"))})


def corr_length(a):
    """The e-folding length of the field's 2-D autocorrelation (radially averaged), m."""
    a = a - a.mean()
    f = np.fft.fft2(a)
    ac = np.fft.ifft2(f * np.conj(f)).real
    ac /= ac[0, 0]
    ac = np.fft.fftshift(ac)
    y, x = np.indices(ac.shape)
    r = np.hypot(x - N // 2, y - N // 2).astype(int)
    prof = np.bincount(r.ravel(), ac.ravel()) / np.bincount(r.ravel())
    below = np.where(prof < 1 / np.e)[0]
    return float(below[0] * DX) if len(below) else float("nan")


def main(work, tag=""):
    os.makedirs(DOCS, exist_ok=True)
    ts = [t for t in times(work) if t >= 7200]
    if not ts:
        sys.exit("no cross-sections after the 2 h spin-up yet")
    out = {"times_s": [ts[0], ts[-1]], "frames": len(ts)}
    spd, dirn, gust_local, lens, lens_w = [], [], [], [], []
    for t in ts:
        u, v = read(work, "u", 0, t), read(work, "v", 0, t)
        s = np.hypot(u, v)
        spd.append(s)
        dirn.append((np.degrees(np.arctan2(-u, -v)) + 360) % 360)   # from which the wind blows
        lens.append(corr_length(s))
        w = read(work, "w", 9, t)
        if w is not None:
            lens_w.append(corr_length(w))
    spd = np.array(spd)
    dirn = np.array(dirn)
    mean = float(spd.mean())
    out["speed_12m_mean_kn"] = mean / KN
    out["gust_intensity_spatial"] = float(np.mean([s.std() / s.mean() for s in spd]))          # across the tile, per frame
    out["gust_intensity_point"] = float(np.mean(spd.std(axis=0) / spd.mean(axis=0)))           # at a point, over the hour
    out["gust_factor_p99_point"] = float(np.mean(np.percentile(spd, 99, axis=0) / spd.mean(axis=0)))
    dd = (dirn - dirn.mean(axis=0) + 180) % 360 - 180
    out["direction_std_deg_point"] = float(np.mean(dd.std(axis=0)))
    out["speed_corr_length_m"] = float(np.nanmedian(lens))
    out["w225_corr_length_m"] = float(np.nanmedian(lens_w)) if lens_w else None
    # The period of the shifts at a point: the first zero crossing of the direction's autocorrelation in time.
    if len(ts) > 8:
        x = dd.reshape(len(ts), -1)
        x = x - x.mean(axis=0)
        ac = np.array([np.mean(x[:len(ts) - lag] * x[lag:]) for lag in range(len(ts) // 2)])
        ac /= ac[0]
        zero = np.where(ac < 0)[0]
        dt = ts[1] - ts[0]
        out["shift_period_s"] = float(4 * zero[0] * dt) if len(zero) else None
    # Mixed-layer height: where the mean potential temperature gradient peaks (statistics over the last hour).
    try:
        import netCDF4 as nc
        st = sorted(glob.glob(os.path.join(work, "*.default.*.nc")))
        ds = nc.Dataset(st[-1])
        z = ds["z"][:]
        th = ds.groups["thermo"]["th"][:] if "thermo" in ds.groups else ds.groups["default"]["th"][:]
        tt = ds["time"][:]
        last = th[tt >= ts[0]].mean(axis=0)
        out["mixed_layer_m"] = float(z[np.argmax(np.gradient(last, z))])
    except Exception as e:   # noqa: BLE001 - the numbers above stand without it
        out["mixed_layer_m"] = None
        out["mixed_layer_note"] = str(e)
    mask_file = os.path.join(work, "lake_mask.npy")
    lake = np.load(mask_file) if os.path.exists(mask_file) else None
    if lake is not None:
        out.update(lake_stats(spd, lake))
    json.dump(out, open(os.path.join(DOCS, f"les-pilot{tag}.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    figures(work, ts[-1], spd[-1], tag, lake)


def lake_stats(spd, lake):
    """Over the water against over the land (12.5 m), and how the wind over the lake changes with distance from the
    upwind (south) shore, which the wind crosses first (13 kn geostrophic from the south)."""
    mean = spd.mean(axis=0)
    gi = spd.std(axis=0) / mean
    out = {"lake_fraction": float(lake.mean()),
           "speed_water_kn": float(mean[lake].mean() / KN), "speed_land_kn": float(mean[~lake].mean() / KN),
           "gust_intensity_water": float(gi[lake].mean()), "gust_intensity_land": float(gi[~lake].mean())}
    # Distance over water from the shore to the south (rows run north), per lake cell.
    dist = np.zeros(lake.shape)
    for j in range(1, N):
        dist[j] = np.where(lake[j], np.where(lake[j - 1], dist[j - 1] + DX, DX), 0.0)
    bins = [0, 250, 500, 1000, 2000, 4000, 10000]
    prof = []
    for a, b in zip(bins, bins[1:]):
        m = lake & (dist > a) & (dist <= b)
        if m.sum() > 50:
            prof.append({"from_m": a, "to_m": b, "cells": int(m.sum()), "speed_ratio_to_land": float(mean[m].mean() / mean[~lake].mean()),
                         "gust_intensity": float(gi[m].mean())})
    out["downwind_of_shore"] = prof
    return out


def figures(work, t, s, tag="", lake=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ext = [0, L / 1000, 0, L / 1000]
    fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=110)
    im = ax.imshow(s / KN, origin="lower", extent=ext, cmap="viridis")
    if lake is not None:
        ax.contour(lake.astype(float), levels=[0.5], colors="w", linewidths=0.6, extent=ext, origin="lower")
    ax.set_title(f"Wind speed at 12.5 m, t = {t / 3600:.2f} h (kn)\n13 kn geostrophic from the south, 250 W/m2")
    ax.set_xlabel("east (km)")
    ax.set_ylabel("north (km)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, f"speed-12m{tag}.png"))
    plt.close(fig)
    w = read(work, "w", 9, t)
    if w is not None:
        fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=110)
        im = ax.imshow(w, origin="lower", extent=ext, cmap="RdBu_r", vmin=-3, vmax=3)
        ax.set_title(f"Vertical wind at 225 m, t = {t / 3600:.2f} h (m/s): thermals and their sinking lanes")
        ax.set_xlabel("east (km)")
        ax.set_ylabel("north (km)")
        fig.colorbar(im, ax=ax, shrink=0.8)
        fig.tight_layout()
        fig.savefig(os.path.join(DOCS, f"w-225m{tag}.png"))
        plt.close(fig)
    # The 1-D spectrum of the speed along the mean wind (north), averaged over columns.
    a = s - s.mean(axis=0)
    p = (np.abs(np.fft.rfft(a, axis=0)) ** 2).mean(axis=1)
    k = np.fft.rfftfreq(N, DX)
    fig, ax = plt.subplots(figsize=(6, 4), dpi=110)
    ax.loglog(1 / k[1:], p[1:])
    ax.set_xlabel("wavelength along the wind (m)")
    ax.set_ylabel("speed variance (arb.)")
    ax.set_title("Where the gust energy sits at 12.5 m")
    ax.axvline(250, color="r", lw=0.8, ls="--")
    ax.text(260, p[1:].max() * 0.5, "game: 250 m", color="r", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, f"spectrum{tag}.png"))
    plt.close(fig)


if __name__ == "__main__":
    # analyse_pilot.py [work dir] [tag]: the lake run writes les-pilot-lake.json and <figure>-lake.png.
    main(sys.argv[1] if len(sys.argv) > 1 else "/root/les-runs/ntxcbl", sys.argv[2] if len(sys.argv) > 2 else "")
