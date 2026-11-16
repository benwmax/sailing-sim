"""The Catalina 22's hull lines as a drawing (docs/c22-2): profile, half-breadth plan and body plan from hull_c22.

    python3 lines_plot_c22.py <out.jpg>

Draws the lines the hull is built from, at the solved canoe depth: the profile (sheer, the canoe body's centreline,
the design waterline), the half-breadth plan (the deck's edge and waterlines every 10 cm) and the body plan (sections
every 0.6 m, the forward half on the right, the aft half on the left, as a naval architect draws it). A reviewer lays
it beside a photo or a published profile. Needs matplotlib (and Pillow for the JPEG).
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hull_c22 as H  # noqa: E402


def waterline(zc, n=400, m=300):
    """Half-breadth of the hull where it crosses height zc, along her length."""
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


def main(out):
    depth = H.solve_depth()
    h = H.hydrostatics()
    xs = [H.TRANSOM_X + (H.STEM_X - H.TRANSOM_X) * i / 600 for i in range(601)]
    fig = plt.figure(figsize=(14, 9), dpi=110)
    grid = fig.add_gridspec(2, 2, width_ratios=[3, 1.25], height_ratios=[1, 1])

    ax = fig.add_subplot(grid[0, 0])
    ax.plot(xs, [H.sheer_z(x) for x in xs], "k", lw=1.4, label="sheer")
    ax.plot(xs, [H.keel_z(x) for x in xs], "k", lw=1.4, label="canoe body's centreline")
    ax.plot([H.TRANSOM_X] * 2, [H.keel_z(H.TRANSOM_X), H.sheer_z(H.TRANSOM_X)], "k", lw=1.4)
    ax.axhline(0, color="tab:blue", lw=0.8, label="design waterline")
    ax.set_title(f"Profile: canoe depth {depth:.3f} m, LWL {h['lwl']:.3f} m, CB x {h['cb'][0]:+.3f} m")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)

    ax = fig.add_subplot(grid[1, 0])
    ax.plot(xs, [H.half_beam(x) for x in xs], "k", lw=1.4, label="deck's edge")
    for zc in [-0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
        wx, wy = waterline(zc)
        ax.plot(wx, wy, color="tab:blue" if zc == 0 else "0.5", lw=1.2 if zc == 0 else 0.6)
    ax.set_title(f"Half-breadth plan: waterlines every 10 cm (blue: the design waterline, beam {h['beam_wl']:.3f} m)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)

    ax = fig.add_subplot(grid[:, 1])
    st = [round(-3.0 + 0.6 * i, 2) for i in range(11)]
    for x in st:
        pts = [H.section(x, k / 120) for k in range(121)]
        side = 1 if x >= H.BOT["lowest_x"] else -1
        ax.plot([side * y for y, _ in pts], [z for _, z in pts], "k", lw=0.8)
    ax.axhline(0, color="tab:blue", lw=0.8)
    ax.axvline(0, color="0.6", lw=0.6)
    ax.set_title("Body plan: stations every 0.6 m\n(right: forward of the lowest point, left: aft)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)

    fig.suptitle("Catalina 22 rebuild, slice 1: the hull's lines (metres, origin amidships on the design waterline)")
    fig.tight_layout()
    tmp = out + ".png"
    fig.savefig(tmp)
    from PIL import Image
    Image.open(tmp).convert("RGB").save(out, quality=85)
    os.remove(tmp)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
