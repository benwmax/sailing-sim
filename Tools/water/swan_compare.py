"""Water W3: the SWAN bake (swan_bake.py collect -> <work>/<world>/summary.npz) against the game's chop: the fetch-law Hs
and Tp (FWaveField::TargetSignificantHeight / TargetPeakPeriod) on the fetch the game marches (FLakeTerrain::FetchToward,
on the game's own 5 m / 10 m grid, capped at 15 km), at every wet 50 m cell and at the ten spectrum points.
Writes docs/water-3/swan-compare.csv (per world, direction, speed: medians and spreads), docs/water-3/points.csv and the
figures docs/water-3/<world>-ratio.png (SWAN Hs / game Hs, wind from the south-west at 14 kn) and
docs/water-3/<world>-growth.png (Hs against fetch for every point and speed, both models).
Usage (WSL): python3 Tools/water/swan_compare.py [--work /root/swan-runs]"""
import argparse
import csv
import json
import os

import numpy as np

import swan_bake as sb

DOCS = os.path.join(sb.ROOT, "docs", "water-3")


def main(work):
    os.makedirs(DOCS, exist_ok=True)
    rows, prow = [], []
    for world in sb.WORLDS:
        base = os.path.join(work, world)
        if not os.path.exists(os.path.join(base, "summary.npz")):
            continue
        s = np.load(os.path.join(base, "summary.npz"))
        g = json.load(open(os.path.join(base, "grid.json")))
        h, cell, ox, oy = sb.read_height(world)
        level = g["level"]
        hh = h - level
        R, C = np.mgrid[0:g["rows"], 0:g["cols"]]
        xs = g["origin_north"] + R * g["cell"]
        ys = g["origin_east"] + C * g["cell"]
        wet = np.isfinite(s["hs"]).any(axis=(0, 1))
        for i, d in enumerate(sb.DIRS):
            fetch = np.full(xs.shape, np.nan)
            fetch[wet] = sb.game_fetch(hh, cell, ox, oy, xs[wet], ys[wet], d)
            for j, kn in enumerate(sb.SPEEDS_KN):
                hs = s["hs"][i, j]
                if not np.isfinite(hs).any():
                    continue
                u = kn * sb.KN
                game = sb.fetch_law_hs(u, fetch)
                gtp = sb.fetch_law_tp(u, fetch)
                m = np.isfinite(hs) & (hs > 0.005) & np.isfinite(game) & (game > 0.005)
                ratio = hs[m] / game[m]
                tpr = s["tp"][i, j][m] / gtp[m]
                rows.append(dict(world=world, wind_from=d, knots=kn, cells=int(m.sum()), swan_hs_median=float(np.median(hs[m])),
                                 game_hs_median=float(np.median(game[m])), ratio_median=float(np.median(ratio)),
                                 ratio_p10=float(np.percentile(ratio, 10)), ratio_p90=float(np.percentile(ratio, 90)),
                                 tp_ratio_median=float(np.median(tpr))))
                for p in g["points"]:
                    r, c = p["row"], p["col"]
                    if np.isfinite(hs[r, c]):
                        prow.append(dict(world=world, point=p["name"], wind_from=d, knots=kn, fetch_m=round(float(fetch[r, c])),
                                         swan_hs=round(float(hs[r, c]), 3), game_hs=round(float(game[r, c]), 3),
                                         swan_tp=round(float(s["tp"][i, j][r, c]), 2), game_tp=round(float(gtp[r, c]), 2),
                                         swan_dir=round(float(s["dir"][i, j][r, c]), 1), swan_dspr=round(float(s["dspr"][i, j][r, c]), 1)))
                if d == 225.0 and kn == 14:
                    figure_ratio(world, hs, game)
        print(f"{world}: compared")
    for name, data in (("swan-compare.csv", rows), ("points.csv", prow)):
        if data:
            with open(os.path.join(DOCS, name), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(data[0]))
                w.writeheader()
                w.writerows(data)
    figure_growth(prow)


def figure_ratio(world, hs, game):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    r = np.where((hs > 0.005) & (game > 0.005), hs / game, np.nan)
    fig, ax = plt.subplots(figsize=(6, 8) if world == "RayHubbard" else (8, 7), dpi=110)
    im = ax.imshow(r, origin="lower", cmap="RdBu_r", vmin=0.0, vmax=2.0)
    ax.set_title(f"{world}: SWAN Hs / game fetch-law Hs\nwind from 225 deg at 14 kn (1 = agree)")
    ax.set_xlabel("east (50 m cells)")
    ax.set_ylabel("north (50 m cells)")
    fig.colorbar(im, ax=ax, shrink=0.7)
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, f"{world}-ratio.png"))
    plt.close(fig)


def figure_growth(prow):
    if not prow:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=110)
    for ax, world in zip(axes, sb.WORLDS):
        pr = [p for p in prow if p["world"] == world]
        for kn in sb.SPEEDS_KN:
            q = [p for p in pr if p["knots"] == kn]
            if not q:
                continue
            f = np.array([p["fetch_m"] for p in q]) / 1000.0
            ax.scatter(f, [p["swan_hs"] for p in q], s=8, label=f"{kn} kn SWAN")
            ff = np.linspace(0.05, 15, 200)
            ax.plot(ff, sb.fetch_law_hs(kn * sb.KN, ff * 1000.0), lw=0.8)
        ax.set_title(f"{world}: Hs against the game's fetch (dots SWAN, lines fetch law)")
        ax.set_xlabel("fetch the game marches (km)")
        ax.set_ylabel("Hs (m)")
    axes[0].legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "growth.png"))
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="/root/swan-runs")
    main(ap.parse_args().work)
