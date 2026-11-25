"""The Hobie 16's hull lines as a drawing (docs/hobie16-2): profile, half-breadth plan and body plan from hull_hobie16.

    python3 lines_plot_hobie16.py <out.jpg>

Draws one hull's lines at the solved keel depth: the profile (the keel, the deck's top and the greatest breadth's line,
the design waterline with her crew aboard and the empty boat's), the plan (both faces' greatest breadth and the
waterlines, the outboard face up) and the body plan (sections every 0.5 m, whole since the two faces differ: the aft half's
and the forward half's side by side, the outboard face to the right). A reviewer lays it
beside a photo. Needs numpy, matplotlib and Pillow.
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hull_hobie16 as H  # noqa: E402


def main(out):
    H.solve_depth()
    ze = H.empty_waterline()
    xs = np.linspace(H.TRANSOM_X, H.STEM_X, 600)
    fig = plt.figure(figsize=(14, 12))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.1, 1.6])
    ax = [fig.add_subplot(gs[0, :]), fig.add_subplot(gs[1, :]), fig.add_subplot(gs[2, 0]), fig.add_subplot(gs[2, 1])]
    # profile
    a = ax[0]
    a.plot(xs, [H.keel_z(x) for x in xs], "k", lw=1.4, label="keel")
    a.plot(xs, [H.top_z(x) for x in xs], "k", lw=1.4, label="deck's top")
    a.plot(xs, [H.max_beam_z(x) for x in xs], color="0.5", lw=0.8, label="greatest breadth")
    a.axhline(0.0, color="tab:blue", lw=0.8, label="waterline, crew aboard")
    a.axhline(ze, color="tab:blue", lw=0.8, ls="--", label="waterline, empty")
    a.plot([H.TRANSOM_X] * 2, [H.keel_z(H.TRANSOM_X), H.top_z(H.TRANSOM_X)], "k", lw=1.4)
    a.set_title("Profile")
    a.legend(loc="lower center", ncol=5, fontsize=8)
    # plan: the outboard face up (+), the inboard face down (-)
    a = ax[1]
    out_b = [H.half_beam(x) for x in xs]
    in_b = [H.inboard_plan(x) for x in xs]
    a.plot(xs, out_b, "k", lw=1.4, label="greatest breadth, outboard")
    a.plot(xs, [-b for b in in_b], "k", lw=1.4, label="greatest breadth, inboard")
    for zc, style in ((0.0, "-"), (ze, "--"), (-0.12, ":")):
        po, pi = [], []
        for x in xs[::4]:
            p = H.section(float(x))
            ys = []
            for i in range(len(p)):
                q, r = p[i], p[(i + 1) % len(p)]
                if (q[1] - zc) * (r[1] - zc) <= 0 and q[1] != r[1]:
                    ys.append(q[0] + (r[0] - q[0]) * (zc - q[1]) / (r[1] - q[1]))
            if len(ys) >= 2:
                po.append((x, max(ys)))
                pi.append((x, min(ys)))
        if po:
            a.plot(*zip(*po), color="tab:blue", lw=0.8, ls=style)
            a.plot(*zip(*pi), color="tab:blue", lw=0.8, ls=style)
    a.axhline(0.0, color="0.7", lw=0.5)
    a.set_title("Plan: outboard face up, inboard face down; waterlines crew aboard (solid), empty (dashed), 12 cm "
                "under (dotted)")
    # body plans: the aft half's sections and the forward half's, whole, the outboard face to the right
    for a, sel, name in ((ax[2], lambda x: x <= 0, "aft half"), (ax[3], lambda x: x >= 0, "forward half")):
        for x in np.arange(-2.5, 2.51, 0.5):
            if not sel(x):
                continue
            p = H.section(float(x))
            a.plot(np.append(p[:, 0], p[0, 0]), np.append(p[:, 1], p[0, 1]), "tab:red" if abs(x) < 1e-6 else "k", lw=1.0)
        a.axhline(0.0, color="tab:blue", lw=0.8)
        a.axhline(ze, color="tab:blue", lw=0.8, ls="--")
        a.axvline(0.0, color="0.7", lw=0.5)
        a.set_title(f"Sections every 0.5 m, {name} (amidships red); outboard face to the right")
    for a in ax:
        a.set_aspect("equal")
        a.grid(True, lw=0.3, color="0.85")
    fig.tight_layout()
    tmp = out + ".png"
    fig.savefig(tmp, dpi=110)
    from PIL import Image
    Image.open(tmp).convert("RGB").save(out, quality=88)
    os.remove(tmp)
    print(f"lines: {out}")


if __name__ == "__main__":
    main(sys.argv[1])
