"""Drawings for the docs from the build's own pieces (no renderer). Slice 2's finish (docs/jclass-2):

  plating.png         the shell in profile, painted, with the plating's seams, butts and frames drawn from the same
                      'Plating' UV the paint's material reads: each strake should run out where it meets the stem,
                      the keel, the counter or the lead
  rudder_sections.png the rudder hard over against the keel: cut square to the stock through the nose and through the
                      blade, and through the turned rudder's own centreplane: the nose should turn inside the keel's
                      groove, and the head under the deadwood, with the gaps all round

Slice 3's deck (docs/jclass-3):

  deck_plan.png       the deck from above with what stands on it, the mast's clear circle and the rudder stock's head,
                      and close-ups at 4 mm a pixel of the planking at the bow, amidships and the stern, drawn by
                      deck.planking_terms from the deck mesh's own UV maps (the terms the teak's material runs)
  deck_profile.png    everything on deck from starboard, coloured by material, over the centreline section

Slice 4's spars (docs/jclass-4):

  sail_plan.png       the yacht from starboard and from ahead with the built spars, the fore and main triangles and
                      their measures (I, J, P, E and the rated area), the cap shroud's line over the spreaders' tips,
                      and the mast's sections

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
    triangle's index and its barycentric interpolation of `values` (n_triangles, 3: a value per corner; or
    (n_triangles, 3, m): m values per corner)."""
    values = np.asarray(values, float)
    ex = (Ellipsis,) + (None,) * (values.ndim - 2)            # values may carry several numbers per corner
    zbuf = np.full((H, W), -np.inf)
    tri_at = np.full((H, W), -1, int)
    val = np.full((H, W) + values.shape[2:], np.nan)
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
        val[sub] = np.where(win[ex], a[ex] * vv[0] + b[ex] * vv[1] + c[ex] * vv[2], val[sub])
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


PALETTE = {"Teak": (0.70, 0.52, 0.35), "Wood": (0.62, 0.38, 0.20), "Bronze": (0.72, 0.55, 0.25),
           "CabinWindow": (0.12, 0.16, 0.2), "Caulking": (0.08, 0.07, 0.06), "Iron": (0.2, 0.21, 0.22)}


def _hash(a, b):
    """A repeatable number in [0, 1) for each piece (the drawing's stand-in for the material's white noise)."""
    v = np.sin(a * 12.9898 + b * 78.233) * 43758.5453
    return v - np.floor(v)


def _deck_pattern(deck_part, mitre, x0, x1, y0, y1, px, seams=True):
    """The deck's top seen from above, x along and y across (starboard is +y; the axes put it below the centreline),
    coloured by piece and with its seams: an RGB image and its extent."""
    import deck
    V = np.asarray(deck_part.V)
    keep = lambda k: deck_part.slot[k] == "Teak"  # noqa: E731
    tris, _ = _triangles(deck_part, keep)
    uv = np.concatenate([np.asarray(deck_part.uv[m]) for m in ("Planking", "Margin", "Aft")], 1)   # (n, 6)
    W, H = int(round((x1 - x0) / px)), int(round((y1 - y0) / px))
    Vp = V[:, [0, 2, 1]]                                   # project on (x, y), the highest face winning
    tri_at, val = _raster(Vp, tris, uv[tris], x0, y0, px, W, H, depth=True)
    U, Ys, D, YM, DA, SL = (val[..., i] for i in range(6))
    T = deck.planking_terms(deck.np_math, U, Ys, D, YM, DA, SL, mitre, aa=0.6 * px)
    on = tri_at >= 0
    side, aft, king = (np.nan_to_num(T[k]) > 0.5 for k in ("side", "aft", "king"))
    margin = side | aft
    tint = 0.94 + 0.12 * _hash(np.nan_to_num(T["idx"]), np.nan_to_num(T["idy"]))
    base = np.array(PALETTE["Teak"])
    shade = np.where(margin, 0.82, np.where(king, 0.9, 1.0))
    rgb = np.ones((H, W, 3))
    rgb[on] = (base[None, :] * (tint * shade)[on][:, None]).clip(0, 1)
    if seams:
        sm = np.nan_to_num(T["seam"]) > 0.5
        rgb[on & sm] = PALETTE["Caulking"]
    return rgb, (x0, x0 + W * px, y0, y0 + H * px)


def _outline(ax, P, **kw):
    P = np.asarray(P)
    ax.plot(np.r_[P[:, 0], P[0, 0]], np.r_[P[:, 1], P[0, 1]], **kw)


BELOW = ("Cockpit", "SaloonSkylight", "SailHatch")    # labels under the plan; the rest above it
LABELS = {"ForecastleHatch": "forecastle hatch", "SailHatch": "sail hatch", "LazaretteHatch": "lazarette",
          "ForecastleSkylight": "forecastle skylight", "SaloonSkylight": "saloon skylight",
          "Companionway": "companionway", "Doghouse": "doghouse", "Cockpit": "cockpit",
          "WheelBox": "wheel box and binnacle"}


def draw_deck_plan(parts, deck_rep, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Patch

    import deck
    dp = parts["Deck"]
    V = np.asarray(dp.V)
    fp = {k: np.asarray(v) for k, v in deck_rep["footprints"].items()}
    mast = deck.DK["mast"]
    stock = deck_rep["layout"]["stock_meets_deck"]
    mitre = deck_rep["planking_mitre"]
    xa, xb = V[:, 0].min(), V[:, 0].max()
    yb = V[:, 1].max()
    fig = plt.figure(figsize=(18, 13.5), dpi=150)
    ax = fig.add_axes([0.04, 0.6, 0.94, 0.34])
    img, ext = _deck_pattern(dp, mitre, xa - 0.2, xb + 0.2, -yb - 0.2, yb + 0.2, 0.02, seams=False)
    ax.imshow(img, origin="lower", extent=ext, interpolation="antialiased")

    def furniture(ax, labels):
        for k, P in fp.items():
            ax.fill(P[:, 0], P[:, 1], color="#d8d4cc" if k != "Cockpit" else "#9c7a52", alpha=0.85, lw=0)
            _outline(ax, P, color="#333333", lw=0.9)
            if labels:
                c = P.mean(0)
                ax.annotate(LABELS.get(k, k), (c[0], c[1]), (c[0], yb + 0.55 if k in BELOW else -yb - 0.55),
                            ha="center", va="center", fontsize=8.5, arrowprops=dict(arrowstyle="-", lw=0.5, color="#555"))
        ax.add_patch(Circle((mast["x"], 0.0), mast["clear_radius"], fill=False, ls="--", lw=0.9, color="#1f5fbf"))
        ax.plot([mast["x"]], [0.0], "o", ms=3, color="#1f5fbf")
        ax.plot([stock[0]], [stock[1]], "x", ms=6, mew=1.4, color="#c0392b")

    furniture(ax, True)
    ax.annotate("mast (x %.1f), clear %.1f m round its partners" % (mast["x"], mast["clear_radius"]),
                (mast["x"], mast["clear_radius"]), (mast["x"] + 0.5, yb + 0.55), fontsize=8.5, ha="center",
                color="#1f5fbf", arrowprops=dict(arrowstyle="-", lw=0.5, color="#1f5fbf"))
    ax.annotate("rudder stock", (stock[0], stock[1]), (stock[0] + 1.0, yb + 0.55), fontsize=8.5, ha="center",
                color="#c0392b", arrowprops=dict(arrowstyle="-", lw=0.5, color="#c0392b"))
    ax.set_xlim(xa - 0.3, xb + 0.3)
    ax.set_ylim(yb + 0.9, -yb - 0.9)                       # looking down, bow to the right: starboard below
    ax.set_aspect("equal")
    ax.set_xlabel("x, m forward of mid-waterline")
    ax.set_ylabel("y, m to starboard")
    ax.set_title("Bluebonnet's deck in plan, from above, bow to the right: covering boards and after margin (darker), "
                 "king plank, planks; what stands on it in grey, the cockpit's well in brown\n(the pieces' shading is "
                 "this drawing's, to tell them apart: the material gives every piece the same teak, each with its own "
                 "slight tint)", fontsize=11)
    ax.legend(handles=[Patch(color=np.array(PALETTE["Teak"]) * 0.82, label="covering boards, after margin"),
                       Patch(color=np.array(PALETTE["Teak"]) * 0.9, label="king plank"),
                       Patch(color=PALETTE["Teak"], label="planks")], loc="lower right", fontsize=8.5, ncol=1)
    # close-ups at 4 mm a pixel: the planking as the material draws it
    xs = V[:, 0]
    stem = xb
    hd_at = lambda x: float(np.max(np.abs(V[np.abs(xs - x) < 0.3, 1])))  # noqa: E731
    views = [("the bow: planks nibbed into the covering boards, the king plank between", stem - 3.6, stem + 0.1,
              -0.25, hd_at(stem - 3.6) + 0.1),
             ("amidships: butts staggered over four planks, scarfs in the king plank and covering board", -0.6, 3.0,
              -0.25, yb + 0.1),
             ("the stern: the after margin, its mitre with the covering board, nibs along the quarter", xa - 0.1,
              xa + 3.5, -0.25, hd_at(xa + 0.1) + 0.15)]
    for n, (title, x0, x1, y0, y1) in enumerate(views):
        ax = fig.add_axes([0.04 + n * 0.32, 0.05, 0.29, 0.48])
        img, ext = _deck_pattern(dp, mitre, x0, x1, y0, y1, 0.004)
        ax.imshow(img, origin="lower", extent=ext, interpolation="antialiased")
        furniture(ax, False)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=9.5)
        ax.set_xlabel("x, m")
        if n == 0:
            ax.set_ylabel("y, m to starboard")
    pl = deck.PL
    fig.text(0.5, 0.548, "Close-ups, 4 mm a pixel, drawn by deck.planking_terms from the deck mesh's own UV maps (the "
             "same terms as the teak's material; the shading of the pieces is the drawing's)\nplanks %.0f mm with %.0f "
             "mm seams, %.1f m long; king plank %.0f mm; "
             "covering boards %.0f mm, nibs cut square at %.0f%% of a plank's width; after margin %.0f mm"
             % (1000 * (pl["pitch"] - pl["seam"]), 1000 * pl["seam"], pl["plank_length"], 1000 * pl["king_plank"],
                1000 * pl["covering_board"], 100 * pl["nib"], 1000 * pl["after_margin"]), ha="center", fontsize=10)
    fig.savefig(path)
    plt.close(fig)


def draw_deck_profile(parts, deck_rep, sheer, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Patch

    import deck
    names = ["Deck", "ToeRail", "Hatches", "Skylights", "Companionway", "Doghouse", "Cockpit", "Steering", "Wheel"]
    Vs, Ts, Ss = [], [], []
    off = 0
    for k in names:
        p = parts[k]
        V = np.asarray(p.V)
        t, src = _triangles(p, lambda i: True)
        Vs.append(V)
        Ts.append(t + off)
        Ss += [p.slot[i] for i in src]
        off += len(V)
    V, T = np.concatenate(Vs), np.concatenate(Ts)
    sheer = np.asarray(sheer)
    fp = {k: np.asarray(v) for k, v in deck_rep["footprints"].items()}
    rows = [(-16.0, -0.5), (-0.5, 14.0)]
    fig, axes = plt.subplots(2, 1, figsize=(18, 8.6), dpi=110)
    fig.subplots_adjust(left=0.04, right=0.99, bottom=0.07, top=0.9, hspace=0.32)
    px = 0.01
    slots = np.array(Ss + ["none"])
    for ax, (x0, x1) in zip(axes, rows):
        z0, z1 = float(np.interp(x0, sheer[:, 0], sheer[:, 2])) - 0.75, float(np.interp(x0, sheer[:, 0],
                                                                                        sheer[:, 2])) + 1.85
        z0 = min(z0, float(np.interp(x1, sheer[:, 0], sheer[:, 2])) - 0.75)
        z1 = max(z1, float(np.interp(x1, sheer[:, 0], sheer[:, 2])) + 1.85)
        W, H = int((x1 - x0) / px), int((z1 - z0) / px)
        sel = (V[T][:, :, 0].max(1) > x0 - 0.5) & (V[T][:, :, 0].min(1) < x1 + 0.5)
        tri_at, _ = _raster(V, T[sel], np.zeros((int(sel.sum()), 3)), x0, z0, px, W, H, depth=True)
        idx = np.where(tri_at >= 0, np.flatnonzero(sel)[np.maximum(tri_at, 0)], -1)
        lab = slots[idx]
        rgb = np.ones((H, W, 3))
        for k, c in PALETTE.items():
            rgb[lab == k] = np.array(c) * 0.55 + 0.45
        ax.imshow(rgb, origin="lower", extent=(x0, x0 + W * px, z0, z0 + H * px), interpolation="antialiased")
        Vc = V[:, [0, 2, 1]]
        segs = _section(Vc, T[sel], 0.0)
        ax.add_collection(LineCollection(segs, colors="black", linewidths=0.8))
        ax.plot(sheer[:, 0], sheer[:, 2], color="#1f3f7f", lw=1.0, label="sheer (the deck's edge)")
        for k, P in fp.items():
            c = P.mean(0)
            if x0 < c[0] < x1:
                top = float(V[(np.abs(V[:, 0] - c[0]) < 0.5 * np.ptp(P[:, 0]) + 0.05) & (np.abs(V[:, 1]) < 0.5), 2].max())
                ax.text(c[0], top + 0.08, LABELS.get(k, k), ha="center", va="bottom", fontsize=8.5)
        m = deck.DK["mast"]
        if x0 < m["x"] < x1:
            zm = float(deck.shell.deck_z(m["x"], 0.0))
            ax.plot([m["x"], m["x"]], [zm, z1], color="#1f5fbf", lw=1.0, ls="--")
            ax.text(m["x"] + 0.08, z1 - 0.15, "mast", color="#1f5fbf", fontsize=8.5, va="top")
        ax.set_xlim(x0, x1)
        ax.set_ylim(z0, z1)
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_xlabel("x, m forward of mid-waterline")
        ax.set_ylabel("z, m above the waterline")
    axes[0].legend(handles=[Patch(color=np.array(PALETTE[k]) * 0.55 + 0.45, label=n) for k, n in
                            (("Teak", "teak"), ("Wood", "varnished teak"), ("Bronze", "bronze"),
                             ("CabinWindow", "glass"), ("Iron", "soft iron, painted"))]
                   + [plt.Line2D([], [], color="black", lw=0.8, label="section on the centreline")],
                   loc="upper left", fontsize=8.5, ncol=6)
    fig.suptitle("What stands on Bluebonnet's deck, seen from starboard (shaded) and cut on the centreline (black): "
                 "aft half above, forward half below, the same scale up and along", fontsize=11)
    fig.savefig(path)
    plt.close(fig)


SPAR_PALETTE = {"Spar": (0.84, 0.78, 0.66), "Bronze": (0.72, 0.55, 0.25), "Black": (0.09, 0.09, 0.09)}


def _silhouette(ax, part, a, b, palette, order=("Spar", "Bronze", "Black"), alpha=1.0):
    """A part's faces projected on two of its axes (a, b: 0 x, 1 y, 2 z), filled by slot, the later slots on top."""
    from matplotlib.collections import PolyCollection
    V = np.asarray(part.V)
    for slot in order:
        polys = [V[list(f)][:, [a, b]] for k, f in enumerate(part.F) if part.slot[k] == slot]
        if polys:
            c = palette.get(slot, (0.6, 0.6, 0.6))
            ax.add_collection(PolyCollection(polys, facecolors=[c], edgecolors=[c], linewidths=0.15, alpha=alpha,
                                             zorder=3 + order.index(slot)))


def _hull_fill(ax, pieces, a, b, mirror=False, zorder=6):
    """The hull (shell and rudder) filled as seen along the remaining axis: every triangle projected on axes a, b (and
    on -a too with mirror, for a view from ahead), so the outline is exact wherever the mesh's vertices fall."""
    from matplotlib.collections import PolyCollection
    polys = []
    for k in ("Shell", "Rudder"):
        p = pieces[k]
        V = np.asarray(p.V)
        t, _ = _triangles(p, lambda i: True)
        polys.append(V[t][:, :, [a, b]])
        if mirror:
            m = V[t][:, :, [a, b]].copy()
            m[:, :, 0] *= -1.0
            polys.append(m)
    c = (0.79, 0.83, 0.9)
    ax.add_collection(PolyCollection(np.concatenate(polys), facecolors=[c], edgecolors=[c], linewidths=0.3,
                                     zorder=zorder))


def draw_sail_plan(sp_parts, rig, pieces, deck_parts, path):
    """The sail plan from the built spars: the yacht from starboard with the fore and main triangles and their measures
    (I, J, P, E, the rated area S), from ahead with the spreaders and the cap shroud's line over their tips (slice 5
    rigs it), and the mast's and boom's sections."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    import spars
    ms, at, mp = rig["measures"], rig["attachments"], rig["measure_points"]
    FW_IN, FH_IN = 18.0, 12.6
    fig = plt.figure(figsize=(FW_IN, FH_IN), dpi=120)
    # both views at one scale: each box sized from its data's extent at SC inches a metre
    SC, X0, Z0 = 0.19, 0.7, 0.9
    PX, PZ, AY = (-23.0, 21.0), (-5.0, 50.0), (15.5, -6.0)
    wp, hp, wa = SC * (PX[1] - PX[0]), SC * (PZ[1] - PZ[0]), SC * abs(AY[1] - AY[0])
    # ---- profile from starboard
    ax = fig.add_axes([X0 / FW_IN, Z0 / FH_IN, wp / FW_IN, hp / FH_IN])
    from matplotlib.collections import LineCollection
    _hull_fill(ax, pieces, 0, 2)                  # drawn over the spars: the mast's heel is inside her
    for k in ("Shell", "Rudder"):
        p = pieces[k]
        V = np.asarray(p.V)
        t, _ = _triangles(p, lambda i: True)
        ax.add_collection(LineCollection(_section(V[:, [0, 2, 1]], t, 0.0), colors="#1f3f7f", linewidths=0.8,
                                         zorder=7))
    sh = np.asarray(pieces["Shell"].sheer)
    ax.plot(sh[:, 0], sh[:, 2], color="#1f3f7f", lw=0.8, zorder=7)
    ax.axhline(0.0, color="#3b7dbf", lw=0.8, zorder=7)
    for k, p in deck_parts.items():
        if k != "Deck":
            _silhouette(ax, p, 0, 2, {s: (0.62, 0.5, 0.38) for s in set(p.slot)}, order=tuple(sorted(set(p.slot))))
    for k in ("Mast", "Boom", "SpinnakerPole"):
        _silhouette(ax, sp_parts[k], 0, 2, SPAR_PALETTE)
    zp = spars.Z_P
    xf = at["stem_head_forestay_tack"]
    xfront = spars.at(0.0, spars.half_depth(0.0))
    fh = at["forestay_hounds"]
    ax.plot([xf[0], fh[0]], [xf[2], fh[2]], color="#555", lw=0.9, ls=":", zorder=6)
    ax.text(0.5 * (xf[0] + fh[0]) + 0.4, 0.5 * (xf[2] + fh[2]), "forestay (slice 5)", fontsize=8.5, color="#555",
            rotation=math.degrees(math.atan2(fh[2] - xf[2], fh[0] - xf[0])) - 180, ha="left", va="center")
    # the fore triangle (the mast's face at the deck, the forestay's tack, where the forestay meets the face) and the
    # main's (the boom's top at the mast's after face, the mast's black band, the boom's), between the measured points
    fc = mp["forestay_on_mast_face"]
    tri_f = np.array([[xfront[0], xfront[2]], [xf[0], xf[2]], [fc[0], fc[2]]])
    ax.fill(tri_f[:, 0], tri_f[:, 1], color="#e9c46a", alpha=0.22, zorder=2)
    pa, xtop, bb = (mp["boom_top_at_mast_after_face"], mp["black_band_on_mast_lower_edge"],
                    mp["black_band_on_boom_forward_edge"])
    tri_m = np.array([[pa[0], pa[2]], [xtop[0], xtop[2]], [bb[0], bb[2]]])
    ax.fill(tri_m[:, 0], tri_m[:, 1], color="#2a9d8f", alpha=0.16, zorder=2)

    def dim(p, q, label, off, rot=None):
        p, q = np.asarray(p, float), np.asarray(q, float)
        d = q - p
        nrm = np.array([-d[1], d[0]]) / np.linalg.norm(d) * off
        ax.annotate("", p + nrm, q + nrm, arrowprops=dict(arrowstyle="<->", lw=0.8, color="#222"), zorder=7)
        m = 0.5 * (p + q) + nrm * 1.6
        ax.text(m[0], m[1], label, fontsize=10, ha="center", va="center", zorder=7,
                rotation=rot if rot is not None else 0,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    dim((xfront[0], zp), (xfront[0], zp + ms["I_m"]), "I %.1f ft\n(%.2f m)" % (ms["I_ft"], ms["I_m"]), -1.2)
    zj = zp + 6.0                                 # J level, above the pole, from the mast's face to over the stem head
    ax.plot([xf[0], xf[0]], [xf[2], zj + 0.4], color="#222", lw=0.6, zorder=7)
    dim((xfront[0], zj), (xf[0], zj), "J %.1f ft (%.2f m)" % (ms["J_ft"], ms["J_m"]), 0.0)
    dim((pa[0], pa[2]), (xtop[0], xtop[2]), "P %.1f ft\n(%.2f m)" % (ms["P_ft"], ms["P_m"]), 1.4)
    dim((pa[0], pa[2]), (bb[0], bb[2]), "E %.1f ft (%.2f m)" % (ms["E_ft"], ms["E_m"]), -1.4)
    for sp in rig["spreaders"]:
        h = sp["height_above_deck_m"]
        ax.text(spars.at(spars.s_at(h))[0] - 1.0, zp + h, "spreaders %.1f m" % h, fontsize=8, ha="right", va="center")
    ax.text(fh[0] - 1.0, fh[2], "hounds %.1f m" % (fh[2] - zp), fontsize=8, ha="right", va="center")
    ax.text(spars.at(spars.S_TOP)[0] - 1.0, spars.at(spars.S_TOP)[2], "truck %.1f ft above deck" %
            rig["mast"]["height_above_deck_ft"], fontsize=8, ha="right", va="center")
    ax.text(-22.0, 47.0, "rated sail area S = P E / 2 + I J / 2\n= %.0f + %.0f = %.0f sq ft"
            % (ms["main_triangle_ft2"], ms["fore_triangle_ft2"], rig["sail_area_ft2"]), fontsize=11, va="top")
    ax.text(-22.0, 42.5,
            "mast %.1f ft above deck, %.1f ft overall, raked %.1f deg\n"
            "mast with its fittings %.0f lb (the 1937 minimum %.0f)\n"
            "boom %.1f ft, pole %.1f ft (J %.1f ft)\nspars %.2f long tons (the card's %.1f)"
            % (rig["mast"]["height_above_deck_ft"], rig["mast"]["length_overall_ft"], rig["mast"]["rake_deg"],
               rig["weights"]["mast_with_fittings_lb"], rig["weights"]["minimum_1937_lb"],
               rig["boom"]["length_overall_ft"], rig["pole"]["length_ft"], ms["J_ft"],
               rig["weights"]["total_long_tons"], rig["weights"]["card_long_tons"]), fontsize=9.5, va="top")
    ax.set_xlim(*PX)
    ax.set_ylim(*PZ)
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.set_xlabel("x, m forward of mid-waterline")
    ax.set_ylabel("z, m above the waterline")
    ax.set_title("From starboard (the pole set %.0f deg from the bow to starboard)" % rig["pole"]["set_deg_from_bow"],
                 fontsize=11)
    ax.legend(handles=[Patch(color=SPAR_PALETTE["Spar"], label="spars (painted duralumin)"),
                       Patch(color=SPAR_PALETTE["Bronze"], label="bronze fittings"),
                       Patch(color=SPAR_PALETTE["Black"], label="black bands (P and E)"),
                       Patch(color="#e9c46a", alpha=0.4, label="fore triangle"),
                       Patch(color="#2a9d8f", alpha=0.35, label="main's triangle")], loc="upper right", fontsize=9)
    # ---- from ahead
    ax2 = fig.add_axes([(X0 + wp + 0.75) / FW_IN, Z0 / FH_IN, wa / FW_IN, hp / FH_IN])
    _hull_fill(ax2, pieces, 1, 2, mirror=True)
    ax2.axhline(0.0, color="#3b7dbf", lw=0.8, zorder=7)
    for k in ("Mast", "Boom", "SpinnakerPole"):
        _silhouette(ax2, sp_parts[k], 1, 2, SPAR_PALETTE)
    for side in ("starboard", "port"):
        path_pts = [at["chainplates"][side]] + list(at["spreader_tips"][side]) + [at["shroud_tangs"][side]]
        P = np.array(path_pts)
        ax2.plot(P[:, 1], P[:, 2], color="#555", lw=0.9, ls=":", zorder=6)
    ax2.text(14.5, 16.0, "dotted: the cap shrouds'\nline over the spreaders'\ntips (slice 5)", fontsize=8.5,
             color="#555")
    ax2.set_xlim(*AY)                            # seen from ahead: starboard on the left
    ax2.set_ylim(*PZ)
    ax2.set_aspect("equal")
    ax2.grid(alpha=0.2)
    ax2.set_xlabel("y, m to starboard (seen from ahead)")
    ax2.set_title("From ahead", fontsize=11)
    # ---- sections
    heights = [("at the partners", 0.0), ("%.0f%% up, where it starts to taper" % (100 * spars.M["taper_from"]),
                                           spars.M["taper_from"] * spars.H),
               ("at the hounds", spars.RG["hounds"]["height_fraction"] * spars.H), ("under the truck", spars.H - 0.3)]
    for n, (title, h) in enumerate(heights):
        a3 = fig.add_axes([15.3 / FW_IN, (Z0 + hp - 1.95 - n * 2.65) / FH_IN, 2.34 / FW_IN, 1.95 / FH_IN])
        s = spars.s_at(h)
        f, y = spars.egg(spars.scale(s), 128)
        a3.fill(np.r_[y, y[0]], np.r_[f, f[0]], color=SPAR_PALETTE["Spar"], ec="#333", lw=0.8)
        a3.set_xlim(-0.36, 0.36)
        a3.set_ylim(-0.36, 0.36)
        a3.set_aspect("equal")
        a3.grid(alpha=0.25)
        a3.set_title("mast %s\n%.0f x %.0f mm, wall %.1f mm" % (title, 1000 * (f.max() - f.min()),
                                                            1000 * (y.max() - y.min()), 1000 * spars.wall(s)),
                     fontsize=8.5)
        a3.tick_params(labelsize=7)
        if n == 3:
            a3.set_xlabel("m across (forward is up)", fontsize=8)
    fig.suptitle("Bluebonnet's sail plan, measured on the built spars (slice 4): the same scale in both views",
                 fontsize=13)
    fig.savefig(path)
    plt.close(fig)


def draw_all(pieces, fin, out, parts=None, deck_rep=None, rig=None):
    import os
    try:
        draw_plating(pieces["Shell"], pieces["Rudder"], fin, os.path.join(out, "plating.png"))
        draw_rudder_sections(pieces["Shell"], pieces["Rudder"], pieces["Stock"], fin,
                             os.path.join(out, "rudder_sections.png"))
        if parts is not None:
            draw_deck_plan(parts, deck_rep, os.path.join(out, "deck_plan.png"))
            draw_deck_profile(parts, deck_rep, pieces["Shell"].sheer, os.path.join(out, "deck_profile.png"))
        if rig is not None:
            draw_sail_plan(rig[0], rig[1], pieces, parts, os.path.join(out, "sail_plan.png"))
    except ImportError:
        print("the drawings were not drawn: they need matplotlib")
