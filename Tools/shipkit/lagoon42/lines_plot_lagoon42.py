"""The Lagoon 42's hull lines as a drawing (docs/lagoon42-2): profile, half-breadth plan and body plan from hull_lagoon42.

    python3 lines_plot_lagoon42.py <out.jpg> [<lagoon42_report.json>]

Draws one hull's lines at the solved canoe depth: the profile (the sheer, the sugar scoop's treads and its raked skirt,
the knuckle, the canoe body's centreline, the game's waterline and the light boat's), the half-breadth plan from the
hull's own centreline (the sheer, the knuckle and waterlines every 10 cm) and the body plan (sections every 0.8 m, the
forward half on the right, the aft half on the left, as a naval architect draws it; outboard is right on both halves).
With the build's report it marks the light boat's waterline too. A reviewer lays it beside a photo or a published profile. Needs matplotlib (and Pillow for the JPEG).
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hull_lagoon42 as H  # noqa: E402


def waterline(zc, n=500, m=300):
    """Half-breadth of the hull (outboard side) where it crosses height zc, along her length."""
    xs, ys = [], []
    for i in range(n + 1):
        x = H.TRANSOM_X + (H.STEM_X - H.TRANSOM_X) * i / n
        prev = H.section(x, 0.0)
        if prev[1] >= zc:
            continue
        for k in range(1, m + 1):
            cur = H.section(x, k / m)
            if prev[1] < zc <= cur[1]:
                t = (zc - prev[1]) / (cur[1] - prev[1])
                xs.append(x)
                ys.append(prev[0] + (cur[0] - prev[0]) * t)
                break
            prev = cur
    return xs, ys


def main(out, report=None):
    depth = H.solve_depth()
    h = H.hydrostatics()
    sink = json.load(open(report))["load_sink_m"] if report else None
    xs = [H.TRANSOM_X + (H.STEM_X - H.TRANSOM_X) * i / 800 for i in range(801)]
    fig = plt.figure(figsize=(15, 9.5), dpi=110)
    grid = fig.add_gridspec(2, 2, width_ratios=[3.2, 1], height_ratios=[1.25, 0.75])

    ax = fig.add_subplot(grid[0, 0])
    ax.plot(xs, [H.sheer_z(x) for x in xs], "k", lw=1.4, label="sheer")
    ax.plot(xs, [H.top_z(x, 1) for x in xs], "k--", lw=0.9, label="outboard top (the scoop's raked skirt aft)")
    ax.plot(xs, [H.top_z(x, -1) for x in xs], color="tab:brown", lw=1.0, label="inboard top (the scoop's platform and steps)")
    ax.plot(xs, [H.knuckle(x)[1] for x in xs], color="0.45", lw=0.9, label="knuckle (the topsides' chine)")
    ax.plot(xs, [H.keel_z(x) for x in xs], "k", lw=1.4, label="canoe body's centreline")
    ax.plot([H.TRANSOM_X] * 2, [H.keel_z(H.TRANSOM_X), H.top_z(H.TRANSOM_X, 1)], "k", lw=1.4)
    for pane in H.LINES["windows"]["panes"]:
        (xa, xb), (za, zb) = pane["x"], pane["z"]
        ax.fill([xa, xb, xb, xa], [za, za, zb, zb], color="0.2", alpha=0.6, lw=0)
    ax.axhline(0, color="tab:blue", lw=0.9, label="the game's waterline (15.5 t)")
    if sink:
        ax.axhline(-sink, color="tab:cyan", lw=0.8, ls=":", label=f"the light boat's (12.1 t, {sink * 100:.0f} cm lower)")
    ax.set_title(f"Profile: canoe depth {depth:.3f} m, LWL {h['lwl']:.3f} m, CB x {h['cb'][0]:+.3f} m (the physics': -0.196)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=7.5, ncol=2)

    ax = fig.add_subplot(grid[1, 0])
    ax.plot(xs, [H.half_beam(x) for x in xs], "k", lw=1.4, label="sheer")
    ax.plot(xs, [H.knuckle(x)[0] for x in xs], color="0.45", lw=0.9, label="knuckle")
    for zc in [-0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2]:
        wx, wy = waterline(zc)
        ax.plot(wx, wy, color="tab:blue" if zc == 0 else "0.6", lw=1.2 if zc == 0 else 0.6)
    ax.set_title(f"Half-breadth plan of one hull, from its own centreline: waterlines every 10 cm "
                 f"(blue: the game's, {h['beam_wl_one_hull']:.3f} m wide)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)

    ax = fig.add_subplot(grid[:, 1])
    st = [round(-6.0 + 0.8 * i, 2) for i in range(16)]
    for x in st:
        if x > H.STEM_X:
            continue
        pts = [H.section(x, k / 160) for k in range(161)]
        sign = 1 if x >= H.BOT["lowest_x"] else -1
        ax.plot([sign * y for y, _ in pts], [z for _, z in pts], "k", lw=0.8)
    ax.axhline(0, color="tab:blue", lw=0.8)
    ax.axvline(0, color="0.6", lw=0.6)
    ax.set_title("Body plan: stations every 0.8 m\n(right: forward of the lowest point, left: aft)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)

    fig.suptitle("Lagoon 42 rebuild, slice 1: one hull's lines (metres; x from amidships, z from the game's waterline)")
    fig.tight_layout()
    tmp = out + ".png"
    fig.savefig(tmp)
    from PIL import Image
    Image.open(tmp).convert("RGB").save(out, quality=85)
    os.remove(tmp)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
