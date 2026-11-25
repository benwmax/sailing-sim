"""The moth's lines on one page (docs/moth-2): profile, plan and body plan from hull_moth.py, with the waterlines at
rest (sailor aboard), empty (her static waterplane) and the flying height.

    python3 -I lines_plot_moth.py <out.jpg>        (needs numpy and matplotlib)
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hull_moth as H  # noqa: E402


def main(out):
    rep = H.report()
    xs = np.linspace(H.TRANSOM_X, H.STEM_X, 200)
    fly = H.CARD["game"]["flying_height_m"]
    fig = plt.figure(figsize=(12, 7.5), dpi=110)
    ax1 = fig.add_axes([0.05, 0.56, 0.62, 0.38])
    ax1.plot(xs, [H.sheer_z(x) for x in xs], "k", lw=1.4, label="deck edge")
    ax1.plot(xs, [H.keel_z(x) for x in xs], "k", lw=1.4, label="keel")
    ax1.plot([H.TRANSOM_X] * 2, [H.keel_z(H.TRANSOM_X), H.sheer_z(H.TRANSOM_X)], "k", lw=1.4)
    ax1.plot([H.STEM_X] * 2, [H.keel_z(H.STEM_X), H.sheer_z(H.STEM_X)], "k", lw=1.4)
    ax1.axhline(0, color="tab:blue", lw=1, label="at rest, sailor aboard")
    ax1.axhline(-rep["empty_rise_m"], color="tab:cyan", lw=1, ls="--", label="empty (static waterplane)")
    zk = min(H.keel_z(x) for x in xs)
    ax1.axhline(zk - fly, color="tab:green", lw=1, ls=":", label=f"water when flying ({fly:.1f} m under her)")
    ax1.set_aspect("equal")
    ax1.set_title("Profile (bow right), metres from the design waterline")
    ax1.legend(fontsize=7, loc="lower left")
    ax1.grid(alpha=0.3)
    ax2 = fig.add_axes([0.05, 0.08, 0.62, 0.38])
    ax2.plot(xs, [H.PLAN(x) for x in xs], "k", lw=1.4)
    ax2.plot(xs, [-H.PLAN(x) for x in xs], "k", lw=1.4)
    wl = [2 * H.breadth_at(H.section(float(x)), 0.0) / 2 for x in xs]
    ax2.plot(xs, wl, "tab:blue", lw=1)
    ax2.plot(xs, [-w for w in wl], "tab:blue", lw=1)
    ax2.set_aspect("equal")
    ax2.set_ylim(-0.35, 0.35)
    ax2.set_title("Plan: deck edge (black) and waterline at rest (blue)")
    ax2.grid(alpha=0.3)
    ax3 = fig.add_axes([0.71, 0.08, 0.27, 0.86])
    for x in np.linspace(H.TRANSOM_X + 0.01, H.STEM_X - 0.02, 11):
        sec = H.section(float(x))
        ys, zs = [p[0] for p in sec], [p[1] for p in sec]
        sgn = 1 if x > 0 else -1                     # body plan: forward sections right, aft left
        ax3.plot([sgn * y for y in ys], zs, "k", lw=0.9)
    ax3.axhline(0, color="tab:blue", lw=1)
    ax3.axhline(-rep["empty_rise_m"], color="tab:cyan", lw=1, ls="--")
    ax3.axvline(0, color="grey", lw=0.6)
    ax3.set_aspect("equal")
    ax3.set_title("Body plan (aft left, forward right)")
    ax3.grid(alpha=0.3)
    fig.text(0.05, 0.015, f"Floats 115 kg at rest: draft {rep['draft_m']:.3f} m, waterline {rep['lwl_m']:.2f} m long and "
             f"{rep['beam_wl_m']:.2f} m wide, freeboard {rep['freeboard_transom_m']:.2f} / {rep['freeboard_mid_m']:.2f} / "
             f"{rep['freeboard_bow_m']:.2f} m (transom / widest / bow), trim {rep['trim_deg']:+.1f} deg bow up; "
             f"empty she rises {rep['empty_rise_m']:.3f} m.", fontsize=8)
    fig.savefig(out, dpi=110, pil_kwargs={"quality": 85})


if __name__ == "__main__":
    main(sys.argv[1])
