"""W5b: the baked days' timelines (docs/w5b/timeline.png) and the storm's radar replay (docs/w5b/radar.png).
Usage: Tools/venv/bin/python Tools/weather/plot_days.py [out_dir]"""
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "docs", "w5b")
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def load(path):
    raw = open(path, "rb").read()
    text, _, radar = raw.partition(b"RADARBIN\n")
    meta, hours = {}, []
    for line in text.decode().splitlines():
        if line.startswith("hour "):
            hours.append([float(v) for v in line.split()[1:]])
        elif line and not line.startswith("#"):
            k, _, v = line.partition(" ")
            meta[k] = v
    d = dict(meta=meta, h=np.array(hours))
    if radar:
        nx, ny, cell, n = (int(float(v)) for v in meta["radar"].split())
        d["radar"] = np.frombuffer(radar, np.uint8).reshape(n, nx, ny) / 2.0
        d["radar_hours"] = np.array([float(v) for v in meta["radar_hours"].split()])
        d["cell"] = cell
        d["storm"] = dict(zip(meta["storm"].split()[0::2], map(float, meta["storm"].split()[1::2])))
    return d


def style(ax):
    ax.grid(True, color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 3))


days = [load(p) for p in sorted(glob.glob(os.path.join(REPO, "Content", "TerrainData", "Weather", "*.wxday")))]
rows = ["Wind (kn)", "From (deg)", "Air and dew point (C)", "Mixed layer (m)", "Cloud (fraction)", "Rain at the lake (mm/h)"]
fig, axes = plt.subplots(len(rows), len(days), figsize=(5.2 * len(days), 13), sharex=True, constrained_layout=True)
for c, d in enumerate(days):
    h = d["h"]
    t = h[:, 0]
    axes[0, c].set_title(d["meta"]["title"], fontsize=10, color=INK)
    a = axes[0, c]; a.plot(t, h[:, 1], color=BLUE, lw=2, label="mean"); a.plot(t, h[:, 3], color=ORANGE, lw=2, label="HRRR gust")
    a = axes[1, c]; a.plot(t, h[:, 2], "o", color=BLUE, ms=4)
    a.set_ylim(0, 360); a.set_yticks([0, 90, 180, 270, 360])
    a = axes[2, c]; a.plot(t, h[:, 4], color=ORANGE, lw=2, label="air"); a.plot(t, h[:, 5], color=AQUA, lw=2, label="dew point")
    a = axes[3, c]; a.plot(t, h[:, 7], color=VIOLET, lw=2)
    a = axes[4, c]
    for k, (col, name) in enumerate(((BLUE, "low"), (AQUA, "middle"), (VIOLET, "high"))):
        a.plot(t, h[:, 9 + k], color=col, lw=2, label=name)
    a.set_ylim(-0.02, 1.02)
    a = axes[5, c]; a.plot(t, h[:, 13], color=BLUE, lw=2, label="HRRR")
    if "radar" in d:
        c0 = d["radar"].shape[1] // 2
        r = d["radar"][:, c0 - 3:c0 + 3, c0 - 3:c0 + 3].max(axis=(1, 2))
        a.plot(d["radar_hours"], r, color=ORANGE, lw=2, label="MRMS radar (within 6 km)")
        s = d["storm"]
        for ax in axes[:, c]:
            ax.axvline(s["arrival"], color=MUTED, lw=1, ls="--")
        axes[0, c].annotate("gust front", (s["arrival"], axes[0, c].get_ylim()[1] * 0.92), color=MUTED, fontsize=8, ha="right")
    for r_, ax in enumerate(axes[:, c]):
        style(ax)
        if c == 0:
            ax.set_ylabel(rows[r_], color=MUTED, fontsize=9)
    axes[-1, c].set_xlabel("local hour", color=MUTED, fontsize=9)
for r_ in (0, 2, 4, 5):
    axes[r_, 0].legend(fontsize=8, frameon=False, labelcolor=MUTED)
os.makedirs(OUT, exist_ok=True)
fig.savefig(os.path.join(OUT, "timeline.png"), dpi=110, facecolor="white")
print("wrote", os.path.join(OUT, "timeline.png"))

storm = next((d for d in days if "radar" in d), None)
if storm:
    s = storm["storm"]
    hours = storm["radar_hours"]
    picks = [np.argmin(np.abs(hours - (s["arrival"] + dh))) for dh in (-0.75, -0.25, 0.0, 0.25, 0.5, 0.75)]
    fig, axes = plt.subplots(1, len(picks), figsize=(3.2 * len(picks), 3.6), constrained_layout=True)
    half = storm["radar"].shape[1] * storm["cell"] / 2000.0
    for ax, k in zip(axes, picks):
        im = ax.imshow(storm["radar"][k], origin="lower", extent=[-half, half, -half, half], cmap="Blues", vmin=0, vmax=60)
        ax.plot(0, 0, "o", color=ORANGE, ms=5)
        hh = hours[k]
        ax.set_title(f"{int(hh):02d}:{int(round((hh % 1) * 60)) % 60:02d}", fontsize=10, color=INK)
        ax.tick_params(colors=MUTED, labelsize=7)
        ax.set_xlabel("east (km)", color=MUTED, fontsize=8)
    axes[0].set_ylabel("north (km)", color=MUTED, fontsize=8)
    fig.colorbar(im, ax=axes, shrink=0.8, label="rain rate (mm/h)")
    fig.suptitle(f"MRMS rain rate, 11 June 2023 (the lake: orange dot; storm moving toward {s['move']:.0f} deg at {s['speed']:.1f} m/s)",
                 fontsize=10, color=INK)
    fig.savefig(os.path.join(OUT, "radar.png"), dpi=110, facecolor="white")
    print("wrote", os.path.join(OUT, "radar.png"))
