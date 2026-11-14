"""Two drawings of slice 2's finish for the docs (docs/jclass-2), from the build's own pieces (no renderer):

  plating.png         the shell in profile, painted, with the plating's seams, butts and frames drawn from the same
                      'Plating' UV the paint's material reads: each strake should run out where it meets the stem,
                      the keel, the counter or the lead
  rudder_sections.png the rudder hard over against the keel: cut square to the stock through the nose and through the
                      blade, and through the turned rudder's own centreplane: the nose should turn inside the keel's
                      groove, and the head under the deadwood, with the gaps all round

build_jclass.py calls draw_all() after the build; it needs matplotlib (it says so and goes on without it).
"""
import math

import numpy as np


def _srgb(c):
    return np.array(c, float) / 255.0


def _triangles(piece, keep, corners=False):
    """Fan-triangulated faces of a piece that pass keep(face index): (n, 3) vertex indices and each one's face (and,
    with corners, each triangle's corners as positions in its face)."""
    tris, src, pos = [], [], []
    for k, f in enumerate(piece.F):
        if not keep(k):
            continue
        for i in range(1, len(f) - 1):
            tris.append((f[0], f[i], f[i + 1]))
            src.append(k)
            pos.append((0, i, i + 1))
    out = (np.array(tris, int).reshape(-1, 3), np.array(src, int))
    return out + (np.array(pos, int).reshape(-1, 3),) if corners else out


def _raster(V, tris, values, x0, z0, px, W, H, depth):
    """Rasterise triangles projected on (x, z), nearest the starboard viewer (largest y) winning: per pixel the
    triangle's index and its barycentric interpolation of `values` (n_triangles, 3: a value per corner)."""
    zbuf = np.full((H, W), -np.inf)
    tri_at = np.full((H, W), -1, int)
    val = np.full((H, W), np.nan)
    P = V[tris]                                                # (n, 3, 3)
    for k in range(len(tris)):
        xs, zs = (P[k, :, 0] - x0) / px, (P[k, :, 2] - z0) / px
        i0, i1 = max(int(math.floor(xs.min())), 0), min(int(math.ceil(xs.max())), W - 1)
        j0, j1 = max(int(math.floor(zs.min())), 0), min(int(math.ceil(zs.max())), H - 1)
        if i1 < i0 or j1 < j0:
            continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1) + 0.5, np.arange(j0, j1 + 1) + 0.5)
        d = (zs[1] - zs[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (zs[0] - zs[2])
        if abs(d) < 1e-12:
            continue
        a = ((zs[1] - zs[2]) * (ii - xs[2]) + (xs[2] - xs[1]) * (jj - zs[2])) / d
        b = ((zs[2] - zs[0]) * (ii - xs[2]) + (xs[0] - xs[2]) * (jj - zs[2])) / d
        c = 1.0 - a - b
        inside = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6)
        if not inside.any():
            continue
        y = a * P[k, 0, 1] + b * P[k, 1, 1] + c * P[k, 2, 1]
        sub = (slice(j0, j1 + 1), slice(i0, i1 + 1))
        win = inside & (y > zbuf[sub]) if depth else inside
        zbuf[sub] = np.where(win, y, zbuf[sub])
        tri_at[sub] = np.where(win, k, tri_at[sub])
        vv = values[k]
        val[sub] = np.where(win, a * vv[0] + b * vv[1] + c * vv[2], val[sub])
    return tri_at, val


def draw_plating(shell_piece, rudder_piece, fin, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    pl, col = fin["plating"], fin["paint"]["colours"]
    w, lp, fs = pl["width"], pl["plate_length"], pl["frame_spacing"]
    # one piece of vertices: the shell's, then the rudder's; starboard surface faces only
    Vs, Vr = np.asarray(shell_piece.V), np.asarray(rudder_piece.V)
    V = np.concatenate([Vs, Vr])
    stb = lambda piece, Vp: lambda k: (piece.kind[k] == "surface" and  # noqa: E731
                                       all(Vp[v][1] > -1e-9 for v in piece.F[k]))
    ts, fs_, cs = _triangles(shell_piece, stb(shell_piece, Vs), corners=True)
    tr, fr = _triangles(rudder_piece, stb(rudder_piece, Vr))
    tris = np.concatenate([ts, tr + len(Vs)])
    # the girth below the sheer at each triangle's corners, as the paint reads it (-1: not plated)
    girth = np.full((len(tris), 3), -1.0)
    for n, (k, pos) in enumerate(zip(fs_, cs)):
        girth[n] = [shell_piece.uv[k][q][1] for q in pos]
    slots = [shell_piece.slot[k] for k in fs_] + ["Rudder"] * len(fr)
    px = 0.02
    x0, x1 = V[:, 0].min() - 0.3, V[:, 0].max() + 0.3
    z0, z1 = V[:, 2].min() - 0.3, V[:, 2].max() + 0.3
    W, H = int((x1 - x0) / px), int((z1 - z0) / px)
    tri_at, g = _raster(V, tris, girth, x0, z0, px, W, H, depth=True)
    names = np.array(slots + ["none"])
    lab = names[tri_at]                                          # -1 indexes the "none" at the end
    rgb = np.ones((H, W, 3))
    colours = {"Topsides": _srgb(col["Topsides"]), "CoveStripe": _srgb(col["CoveStripe"]),
               "Bootstripe": _srgb(col["Bootstripe"]), "Antifouling": _srgb(col["Antifouling"]),
               "Keel": _srgb(col["Keel"]) * 0.62, "Rudder": _srgb(col["Antifouling"]) * 0.85 + 0.15}
    for k, c in colours.items():
        rgb[lab == k] = c
    # the plating's lines from the girth: seams (every w below the sheer), butts (staggered a third a strake), frames
    xs = x0 + (np.arange(W) + 0.5) * px
    X = np.broadcast_to(xs, (H, W))
    plated = np.isfinite(g) & (g > -0.5)
    gg = np.where(plated, g, np.nan)
    dgz, dgx = np.gradient(gg, px)
    grad = np.sqrt(dgx ** 2 + dgz ** 2)
    with np.errstate(invalid="ignore"):
        k = np.round(gg / w)
        seam = plated & (k >= 1) & (np.abs(gg - k * w) / np.maximum(grad, 1e-6) < 1.1 * px)
        j = np.floor(gg / w)
        off = np.mod(j, 3) * lp / 3
        butt = plated & (np.abs(X - off - lp * np.round((X - off) / lp)) < 1.1 * px)
        frame = plated & (np.abs(X - fs * np.round(X / fs)) < 0.55 * px)
    # the edges between paint regions and against the background, so the outline reads
    edge = np.zeros((H, W), bool)
    edge[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edge[1:, :] |= lab[1:, :] != lab[:-1, :]
    rgb[frame] = rgb[frame] * 0.75 + 0.25
    rgb[seam | butt] = np.array([0.93, 0.93, 0.9])
    rgb[edge] = 0.08
    fig = plt.figure(figsize=(18, 4.6), dpi=110)
    ax = fig.add_axes([0.04, 0.12, 0.94, 0.78])
    ax.imshow(rgb, origin="lower", extent=(x0, x0 + W * px, z0, z0 + H * px), interpolation="antialiased")
    ax.set_aspect("equal")
    ax.set_xlabel("x, m forward of mid-waterline")
    ax.set_ylabel("z, m above the load waterline")
    ax.axhline(0.0, color="#3b7dd8", lw=0.7, ls="--")
    ax.set_title("Bluebonnet's plating in profile: seams every %.2f m of girth below the sheer, butts every %.1f m "
                 "staggered a third, frames every %.2f m (light lines); the lead and the rudder are not plated"
                 % (w, lp, fs), fontsize=11)
    ax.legend(handles=[Patch(color=colours[k], label=n) for k, n in
                       (("Topsides", "topsides"), ("CoveStripe", "cove line"), ("Bootstripe", "boot top"),
                        ("Antifouling", "bottom"), ("Keel", "lead casting"), ("Rudder", "rudder"))],
              loc="lower right", fontsize=9, ncol=3, framealpha=0.9)
    fig.savefig(path)
    plt.close(fig)


def _section(V, tris, c):
    """Segments where the plane z = c cuts the triangles (V already in the plane's frame): (n, 2, 2) in (x, y)."""
    P = V[tris]
    d = P[:, :, 2] - c
    segs = []
    for e0, e1, e2 in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
        # the vertex e0 alone on its side: the two edges from it cross the plane
        alone = (np.sign(d[:, e0]) != np.sign(d[:, e1])) & (np.sign(d[:, e0]) != np.sign(d[:, e2]))
        if not alone.any():
            continue
        A, B, C = P[alone, e0], P[alone, e1], P[alone, e2]
        da, db, dc = d[alone, e0], d[alone, e1], d[alone, e2]
        t1 = (da / (da - db))[:, None]
        t2 = (da / (da - dc))[:, None]
        segs.append(np.stack([A + t1 * (B - A), A + t2 * (C - A)], 1)[:, :, :2])
    return np.concatenate(segs) if segs else np.zeros((0, 2, 2))


def draw_rudder_sections(shell_piece, rudder_piece, stock_piece, fin, path, turn=35.0, heights=(-0.8, 0.8)):
    """The rudder hard over against the keel: two cuts square to the stock (through the nose in its groove, and through
    the blade under the deadwood) and one through the turned rudder's own centreplane (its head's shoulder and cone
    under the deadwood's)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    import shell

    def local(piece):
        xl, y, h, _ = shell.stock_frame(np.asarray(piece.V))
        return np.stack([xl, y, h], 1)

    Ls, Lr, Lk = local(shell_piece), local(rudder_piece), local(stock_piece)
    near = (np.abs(Ls[:, 0]) < 4.0) & (np.abs(Ls[:, 2]) < 5.0)
    ts, _ = _triangles(shell_piece, lambda k: all(near[v] for v in shell_piece.F[k]))
    tr, _ = _triangles(rudder_piece, lambda k: True)
    tk, _ = _triangles(stock_piece, lambda k: True)
    a = math.radians(turn)
    # a positive turn swings the trailing edge (+x_l) to starboard (+y)
    rot = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.2), dpi=110, gridspec_kw={"width_ratios": [1, 1, 0.8]})
    fig.subplots_adjust(left=0.04, right=0.99, bottom=0.1, top=0.86, wspace=0.16)
    styles = (("black", 1.4, "-", "keel and deadwood (shell)"), ("#1f5fbf", 1.4, "-", "rudder, straight"),
              ("#c0392b", 1.2, "--", f"rudder, hard over ({turn:.0f} degrees)"), ("#9a6a2a", 1.0, "-", "stock"))
    g = fin["rudder"]
    for ax, c in zip(axes[:2], heights):
        for (V, tris), (colr, lw, ls, label) in zip(((Ls, ts), (Lr, tr), (Lr @ rot.T, tr), (Lk, tk)), styles):
            s = _section(V, tris, c)
            ax.add_collection(LineCollection(s, colors=colr, linewidths=lw, linestyles=ls, label=label))
        ax.set_xlim(-0.9, 1.9)
        ax.set_ylim(-1.15, 1.15)
        ax.set_aspect("equal")
        ax.grid(alpha=0.3)
        where = "below" if c < 0 else "above"
        ax.set_title(f"square to the stock, {abs(c):.1f} m {where} the head's foot", fontsize=10)
        ax.set_xlabel("m aft of the stock's axis")
        ax.set_ylabel("m to starboard")
    # the turned rudder's centreplane: the hull cut by the same plane (turned with the rudder), the rudder by its own
    ax = axes[2]
    turned = Ls @ np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    for (V, tris), (colr, lw, ls, label) in zip(((turned[:, [0, 2, 1]], ts), (Lr[:, [0, 2, 1]], tr),
                                                  (Lk[:, [0, 2, 1]], tk)), (styles[0], styles[2], styles[3])):
        s = _section(V, tris, 0.0)
        ax.add_collection(LineCollection(s, colors=colr, linewidths=lw, linestyles=ls))
    ax.set_xlim(-0.9, 1.9)
    ax.set_ylim(-1.6, 2.9)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.set_title(f"through the rudder's own centreplane, {turn:.0f} degrees over", fontsize=10)
    ax.set_xlabel("m aft of the stock's axis")
    ax.set_ylabel("m up the stock from the head's foot")
    axes[0].legend(loc="lower left", fontsize=9)
    fig.suptitle(f"Rudder and keel in section, the rudder hard over: its nose turns in the keel's groove "
                 f"({g['gap'] * 1000:.0f} mm clear) and its head (a flat shoulder, then a cone about the stock) under "
                 f"the deadwood's ({g['head_gap'] * 1000:.0f} mm clear)", fontsize=11)
    fig.savefig(path)
    plt.close(fig)


def draw_all(pieces, fin, out):
    import os
    try:
        draw_plating(pieces["Shell"], pieces["Rudder"], fin, os.path.join(out, "plating.png"))
        draw_rudder_sections(pieces["Shell"], pieces["Rudder"], pieces["Stock"], fin,
                             os.path.join(out, "rudder_sections.png"))
    except ImportError:
        print("plating.png and rudder_sections.png not drawn: they need matplotlib")
