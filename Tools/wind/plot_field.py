"""W1: plots Tools/wind/DumpField.cpp's patch: the puffs (speed factor, shaded) with the wind's direction as arrows, and
the whole field (puffs, fine turbulence, shifts) beside it. Usage: plot_field.py <dump.txt> <out.png>"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

src, out = sys.argv[1], sys.argv[2]
head = open(src).readline().strip("# \n")
d = np.loadtxt(src)
xs, ys = np.unique(d[:, 0]), np.unique(d[:, 1])
n, m = len(xs), len(ys)
grid = lambda k: d[:, k].reshape(n, m)
pf, ps, tf, ts = grid(2), grid(3), grid(4), grid(5)
fig, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)
for ax, f, s, title in ((axes[0], pf, ps, "Puffs: speed factor, wind direction (veer and fan)"), (axes[1], tf, ts, "Everything: puffs, fine turbulence, shifts")):
    # Plot with east to the right and north up (Y east, X north).
    im = ax.imshow(f, origin="lower", extent=[ys[0], ys[-1], xs[0], xs[-1]], cmap="Blues", vmin=0.6, vmax=1.6)
    k = 6
    # Direction the air goes: north (+X) shifted by the angle (positive = veer, toward east).
    ang = np.radians(s[::k, ::k])
    U, V = np.sin(ang), np.cos(ang)
    Y, X = np.meshgrid(ys[::k], xs[::k])
    ax.quiver(Y, X, U * f[::k, ::k], V * f[::k, ::k], color="#a33", scale=40, width=0.0025)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="speed / mean")
fig.suptitle("W1 wind field, 4 km square, wind from the south (" + head + ")", fontsize=10)
fig.savefig(out, dpi=110)
print("wrote", out)
