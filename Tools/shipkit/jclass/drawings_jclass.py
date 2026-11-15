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

Slice 6's sails (docs/jclass-6):

  sail_cut.png        each sail's flat pattern (its cloth's UV0, metres) with its cut drawn by the rules its material
                      runs: the seams (parallel to the leech on the mainsail, mitre cut on the jibs, square to the
                      centre seam on the spinnaker), the corner patches, the mainsail's reef bands and the club's star,
                      with each sail's measures and weight
  sail_suits.png      the three sailing suits from starboard, the cloth as built (pressed and trimmed) with the boom and
                      the pole posed as each suit has them, over the rated fore and main triangles

build_jclass.py calls draw_all() after the build; it needs matplotlib (it says so and goes on without it).
"""
import math
import types

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


RIG_COLOURS = {"cap": "#1d3557", "d3": "#457b9d", "d2": "#2a9d8f", "d1": "#6a994e", "forestay": "#9d0208",
               "staysail": "#dc2f02", "backstay": "#7b2cbf", "jumper": "#c77dff", "runner": "#e85d04",
               "checkstay": "#f48c06", "fall": "#b08968"}
RIG_PALETTE = {"Wire": (0.45, 0.46, 0.47), "WireRope": (0.38, 0.38, 0.38), "Rope": (0.69, 0.54, 0.34),
               "Bronze": (0.72, 0.55, 0.25), "Galvanised": (0.55, 0.56, 0.57)}


def draw_rigging_plan(rg_parts, rr, sp_parts, rig, pieces, deck_parts, path, shown):
    """The standing rigging and the runners as built (slice 5), at the sail plan's scale: from starboard with each
    wire's line (the starboard runner and checkstay set, the port pair let off and lashed to the aftermost shroud,
    dashed), from ahead with the shrouds over the spreaders' tips and the jumper stays, and a table of the wires'
    sizes, lengths and strength, the weights and the checks."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    FW_IN, FH_IN = 18.0, 12.6
    fig = plt.figure(figsize=(FW_IN, FH_IN), dpi=120)
    SC, X0, Z0 = 0.19, 0.7, 0.9
    PX, PZ, AY = (-23.0, 21.0), (-5.0, 50.0), (6.0, -6.0)
    wp, hp, wa = SC * (PX[1] - PX[0]), SC * (PZ[1] - PZ[0]), SC * abs(AY[1] - AY[0])
    sizes = rr["sizes"]
    wires = [w for w in rr["wires"] if w["object"] in shown]

    def lw(w):
        return max(0.5, 1000 * 2 * w["r"] / 11.0)

    def draw(ax, a, b, side=None):
        _hull_fill(ax, pieces, a, b, mirror=(a == 1))
        ax.axhline(0.0, color="#3b7dbf", lw=0.8, zorder=7)
        for k in ("Mast", "Boom", "SpinnakerPole"):
            _silhouette(ax, sp_parts[k], a, b, SPAR_PALETTE, alpha=0.75)
        for name in shown:
            _silhouette(ax, rg_parts[name], a, b, RIG_PALETTE, order=("Wire", "WireRope", "Rope", "Galvanised",
                                                                         "Bronze"))
        for w in wires:
            if side is not None and ", port" in w["name"]:          # from starboard: the port side's lie behind
                continue
            P = np.array(w["path"], float)
            let_off = w["state"] is not None and w["state"][1] == "LetOff"
            ax.plot(P[:, a], P[:, b], color=RIG_COLOURS[w["key"]], lw=lw(w), ls="--" if let_off else "-", zorder=8,
                    alpha=0.9)
    # ---- profile from starboard: the starboard side's wires (the port shrouds lie behind them)
    ax = fig.add_axes([X0 / FW_IN, Z0 / FH_IN, wp / FW_IN, hp / FH_IN])
    for k, p in deck_parts.items():
        if k != "Deck":
            _silhouette(ax, p, 0, 2, {s: (0.62, 0.5, 0.38) for s in set(p.slot)}, order=tuple(sorted(set(p.slot))))
    draw(ax, 0, 2, side="starboard")
    for w in [w for w in rr["wires"] if w["object"] in shown and w["state"] is not None and w["state"][0] == "port"
              and w["key"] != "fall"]:
        P = np.array(w["path"], float)
        ax.plot(P[:, 0], P[:, 2], color=RIG_COLOURS[w["key"]], lw=lw(w), ls="--", zorder=8, alpha=0.6)

    def tag(P, Q, text, f=0.5, dx=0.4, **kw):
        m = np.asarray(P, float) + f * (np.asarray(Q, float) - np.asarray(P, float))
        ax.text(m[0] + dx, m[2], text, fontsize=8.5, va="center", zorder=9,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8), **kw)
    tag(rr["forestay"]["stem_pin"], rr["forestay"]["tang_pin"], "forestay %.0f mm" % sizes["forestay"]["d_mm"], 0.45)
    tag(rr["staysail_stay"]["deck_pin"], rr["staysail_stay"]["tang_pin"],
        "staysail stay %.0f mm" % sizes["staysail"]["d_mm"], 0.35)
    tag(rr["backstay"]["deck_pin"], rr["backstay"]["crane_pin"], "backstay %.0f mm" % sizes["backstay"]["d_mm"], 0.5)
    ru, ck = rr["runners"]["runner"]["starboard"], rr["runners"]["checkstay"]["starboard"]
    tag(ru["padeye_hole"], ru["tang_pin"], "runner (set) %.0f mm" % sizes["runner"]["d_mm"], 0.3)
    tag(ck["padeye_hole"], ck["tang_pin"], "checkstay (set) %.0f mm" % sizes["checkstay"]["d_mm"], 0.42)
    lp = rr["runners"]["runner"]["port"]["lashed_to_d3_at"]
    ax.text(lp[0] + 1.0, lp[2] + 3.0, "dashed: the port (lee) runner and\ncheckstay let off, lashed to D3",
            fontsize=8.5, zorder=9, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))
    ax.set_xlim(*PX)
    ax.set_ylim(*PZ)
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.set_xlabel("x, m forward of mid-waterline")
    ax.set_ylabel("z, m above the waterline")
    ax.set_title("From starboard, sailing on starboard tack", fontsize=11)
    keys = ["cap", "d3", "d2", "d1", "forestay", "staysail", "backstay", "jumper", "runner", "checkstay"]
    ax.legend(handles=[Line2D([], [], color=RIG_COLOURS[k], lw=2, label=sizes[k]["label"]) for k in keys]
              + [Line2D([], [], color=RIG_COLOURS["fall"], lw=2, label="tackle falls (manila)")],
              loc="upper right", fontsize=8.5)
    # ---- from ahead: both sides' shrouds over the spreaders, the jumper stays
    ax2 = fig.add_axes([(X0 + wp + 0.6) / FW_IN, Z0 / FH_IN, wa / FW_IN, hp / FH_IN])
    draw(ax2, 1, 2)
    sh = rr["shrouds"]["starboard"]
    for k, row in sh.items():                     # each label on the wire's top run, where the four part company
        top = np.asarray(row["top_pin"], float)
        q = np.asarray(row["passes"][0] if row["passes"] else row["chainplate_pin"], float)
        m = top + 0.5 * (q - top)
        ax2.text(m[1] + 0.3, m[2], {"cap": "V1", "d3": "D3", "d2": "D2", "d1": "D1"}[k], fontsize=9,
                 color=RIG_COLOURS[k], ha="right", va="center", zorder=9,
                 bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
    ax2.set_xlim(*AY)
    ax2.set_ylim(*PZ)
    ax2.set_aspect("equal")
    ax2.grid(alpha=0.2)
    ax2.set_xlabel("y, m to starboard (seen from ahead)")
    ax2.set_title("From ahead", fontsize=11)
    # ---- the table
    a3 = fig.add_axes([(X0 + wp + wa + 1.0) / FW_IN, Z0 / FH_IN, (FW_IN - X0 - wp - wa - 1.2) / FW_IN, hp / FH_IN])
    a3.axis("off")
    length = {}
    for w in rr["wires"]:
        if w["key"] == "fall" or (w["state"] is not None and w["state"] != ("starboard", "Set")):
            continue
        if w["state"] is None and ", port" in w["name"]:
            continue
        P = np.array(w["path"], float)
        length[w["key"]] = length.get(w["key"], 0.0) + float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
    lines = ["%-20s %5s %5s %5s %6s %6s" % ("wire (one side)", "d mm", "", "kg/m", "break", "length"),
             "%-20s %5s %5s %5s %6s %6s" % ("", "", "", "", "kN", "m")]
    for k in keys:
        z = sizes[k]
        lines.append("%-20s %5.0f %5s %5.2f %6.0f %6.1f" % (z["label"].split(" (")[0][:20], z["d_mm"],
                                                           z["construction"], z["kg_per_m"], z["breaking_kn"],
                                                           length.get(k, 0.0)))
    wt = rr["weights"]
    lines += ["", "weights as sailed (kg)"]
    for row in sorted(wt["rows"], key=lambda r: -r["kg"]):
        lines.append("  %-34s %7.1f" % (row["part"][:34], row["kg"]))
    lines.append("  %-34s %7.1f" % ("total: %.2f long tons (card %.1f)" % (wt["total_long_tons"], wt["card_long_tons"]),
                                    wt["total_kg"]))
    st = rr["strength"]
    fl, bl = st["fittings"]["least"], st["balance"]
    lines += ["", "strength",
              "  weakest fitting: %.3f x its wire" % fl["over_wire"],
              "    (%s, %s)" % (fl["fitting"], fl["how"]),
              "  runner / forestay fore and aft: %.2f" % bl["runner"]["ratio"],
              "  checkstay / staysail stay: %.2f" % bl["checkstay"]["ratio"],
              "  windward shrouds' breaking moment",
              "  %.0f kNm = %.1f x her righting moment" % (st["breaking_moment_knm"], st["breaking_over_righting"]),
              "  heeled 30 deg (%.0f kNm, GM sin 30)" % st["righting_moment_30_deg_knm"]]
    bs = rig["boom_sweep"]
    ps = rig["pole_sweep"]
    room = rr["room"]["starboard"]
    rd = room["least_to_hull_deck"]
    # the least room between two wires (a wire's own tube, not a fitting or a block)
    rw = min((dict(r["rigging"], wire=r["wire"]) for r in room["rows"]
              if "rigging" in r and " | " not in r["rigging"]["piece"]), key=lambda q: q["gap_mm"])
    lines += ["", "checks",
              "  boom swung to %.0f deg: %.0f mm at least" % (abs(bs["least_clearance_lee_runners_at_deg"]),
                                                            bs["least_clearance_lee_runners_mm"]),
              "    from the let-off runner and checkstay",
              "  pole 10-90 deg each side: %.0f mm at least" % ps["least_clearance_rigging_mm"],
              "    from the rigging",
              "  least room between two wires: %.1f mm" % rw["gap_mm"],
              "    (%s by %s)" % (rw["wire"].split(",")[0], rw["against"].split(",")[0]),
              "  least room anywhere: %.1f mm" % room["least"]["least_gap_mm"],
              "    (%s)" % room["least"]["wire"],
              "  the let-off tackles' ropes lie %.0f mm" % rd["gap_mm"],
              "    off the deck",
              "  the mainsail's slides' lane up the track:",
              "    %s" % ("clear" if all(v["ok"] for v in rr["slide_lane"].values()) else "NOT clear")]
    a3.text(0.0, 1.0, "\n".join(lines), family="monospace", fontsize=8.6, va="top", transform=a3.transAxes)
    fig.suptitle("Bluebonnet's standing rigging and runners as built (slice 5): the sail plan's scale in both views",
                 fontsize=13)
    fig.savefig(path)
    plt.close(fig)


SAIL_FILL = (0.93, 0.9, 0.82)
SAIL_EDGE = "#6b5d3f"
SEAM = "#9c8a62"


def _cloth(part):
    """A set sail's cloth: its triangles (n, 3) over the part's vertices, and the vertices' three UV maps."""
    t, _ = _triangles(part, lambda k: part.labels[k].endswith(" cloth"))
    used = np.unique(t)
    remap = -np.ones(len(part.V), int)
    remap[used] = np.arange(len(used))
    uv = {k: np.asarray(v, float)[used] for k, v in part.uv.items()}
    return remap[t], np.asarray(part.V, float)[used], uv


def _boundary(tris):
    """The edges used by one triangle only (the cloth's outline), as index pairs."""
    from collections import Counter
    e = Counter()
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            e[(min(u, v), max(u, v))] += 1
    return [k for k, n in e.items() if n == 1]


def draw_sail_cut(sl_parts, srep, cloth, path):
    """Each sail's flat pattern with its cut, at one scale."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    from matplotlib.collections import LineCollection
    IN = 0.0254
    order = ["Mainsail", "Genoa", "Quadrilateral", "Staysail", "Spinnaker"]
    info = srep["sails"]
    pats = {}
    for name in order:
        tris, V, uv = _cloth(sl_parts[f"{name}.Set"])
        x0, y0 = uv["UV0"][:, 0], uv["UV0"][:, 1]
        if name == "Spinnaker":                     # centred on its centre seam
            x0 = x0 - 0.5 * np.interp(y0, *_row_width(x0, y0))
        pats[name] = (tris, x0, y0, uv)
    widths = [float(p[1].max() - p[1].min()) for p in pats.values()]
    H = max(float(p[2].max()) for p in pats.values())
    SC, GAP, X0, Z0 = 0.165, 1.5, 0.5, 2.0
    FW = X0 * 2 + SC * sum(widths) + GAP * (len(order) - 1)
    FH = Z0 + SC * H + 1.4
    fig = plt.figure(figsize=(FW, FH), dpi=130)
    xl = X0
    for name, w in zip(order, widths):
        tris, x0, y0, uv = pats[name]
        it = info[name]
        ax = fig.add_axes([xl / FW, Z0 / FH, SC * w / FW, SC * H / FH])
        xl += SC * w + GAP
        T = mtri.Triangulation(x0, y0, tris)
        ax.tripcolor(T, np.zeros(len(x0)), cmap=matplotlib.colors.ListedColormap([SAIL_FILL]), shading="flat",
                     edgecolors="none")
        c = cloth[it["cloth"]]
        pitch = (c["cloth_in"] - c["seam_in"]) * IN
        a, b = uv["UV2"][:, 0], uv["UV2"][:, 1]
        f = uv["UV1"][:, 0]
        if it["kind"] == "main":
            # in the roach the cloths run on past the leech's straight line (b at and under 0)
            q, how = b, "cloths parallel to the leech"
            lv = np.arange(math.ceil(float(q.min()) / pitch) * pitch, float(q.max()), pitch)
        elif it["kind"] == "mitre":
            q, how = np.minimum(b, y0), "mitre cut: cloths parallel\nto the leech and to the foot"
            lv = np.arange(pitch, float(q.max()), pitch)
        else:
            q, how = y0, "two halves, cloths square\nto the centre seam"
            lv = np.arange(pitch, float(q.max()), pitch)
        ax.tricontour(T, q, levels=lv, colors=SEAM, linewidths=0.35)
        if it["kind"] == "mitre":
            ax.tricontour(T, b - y0, levels=[0.0], colors=SEAM, linewidths=0.9)
        if it["kind"] == "spin":
            ax.tricontour(T, f - 0.5, levels=[0.0], colors=SEAM, linewidths=0.9)
        # corner patches (the material's: straight across the corner) and the mainsail's reef bands
        after = a
        hy = it["head_y_m"]
        corners = [x0 + y0, after + y0, x0 + (hy - y0)] if it["kind"] != "spin" else \
            [uv["UV0"][:, 0] + y0, a + y0, hy - y0]
        if "upper_clew_y_m" in it:
            corners.append(after + np.abs(y0 - it["upper_clew_y_m"]))
        r1, r2 = (1.6, 0.95) if it["kind"] != "spin" else (1.2, 0.6)
        for cv in corners:
            ax.tricontour(T, cv, levels=[r2, r1], colors="#7a6a48", linewidths=0.7)
        for h in it.get("reefs_m", []):
            ax.plot([float(x0.min()), float(np.interp(h, *_row_width(x0, y0)))], [h, h], color="#7a6a48", lw=0.8,
                    ls="--")
        if it.get("emblem"):
            e = it["emblem"]
            ang = np.radians(90 + np.arange(11) * 36.0)
            rr = np.where(np.arange(11) % 2 == 0, e["radius_m"], e["radius_m"] * math.sin(math.radians(18)) /
                          math.sin(math.radians(126)))
            ax.fill(e["at"][0] + rr * np.cos(ang), e["at"][1] + rr * np.sin(ang), color="#1e3076", zorder=5)
        P = np.stack([x0, y0], 1)
        ax.add_collection(LineCollection([P[list(e)] for e in _boundary(tris)], colors=SAIL_EDGE, linewidths=1.0))
        ax.set_xlim(float(x0.min()) - 0.3, float(x0.min()) + w + 0.3)
        ax.set_ylim(-0.5, H + 0.3)
        ax.set_aspect("equal")
        ax.axis("off")
        meas = [f"{it['area_m2']:.0f} m\u00b2 ({it['area_ft2']:.0f} sq ft)", f"luff {it['luff_m']:.1f} m, "
                f"foot {it['foot_m']:.1f} m"]
        if it["kind"] == "main":
            meas += [f"roach {it['roach_m2']:.0f} m\u00b2", f"reefs at {', '.join(str(h) for h in it['reefs_m'])} m"]
        elif it["kind"] == "mitre":
            meas += [f"leech {it['leech_m']:.1f} m, LP {it['lp_m']:.1f} m", f"{it['hanks']} hanks"]
        else:
            meas += [f"widest girth {it['widest_girth_m']:.1f} m", f"pole {it['pole_m']:.2f} m"]
        meas += [f"{c['oz']:g} oz cotton", f"{it['total_kg']:.0f} kg made up"]
        ax.text(0.0, -0.06, f"{name}\n" + "\n".join(meas) + f"\n{how}", transform=ax.transAxes, fontsize=8.5,
                va="top", ha="left")
    wd = srep["wardrobe"]
    fig.suptitle("Bluebonnet's sails cut flat (slice 6): seams every %.1f in (the %g in cloths less their overlap), "
                 "corner patches in two layers, the mainsail's reef bands dashed. The five weigh %.0f kg (%.2f long "
                 "tons); the size card allows %.1f for her whole wardrobe"
                 % (cloth["main"]["cloth_in"] - cloth["main"]["seam_in"], cloth["main"]["cloth_in"], wd["total_kg"],
                    wd["total_long_tons"], wd["card_long_tons"]), fontsize=11)
    fig.savefig(path)
    plt.close(fig)


def _row_width(x0, y0):
    """Each height's row width in a flat pattern (for centring the spinnaker on its seam)."""
    ys = np.unique(np.round(y0, 6))
    w = np.array([x0[np.abs(y0 - y) < 1e-6].max() for y in ys])
    return ys, w


def _posed(part, deg, about):
    """A spar's vertices turned deg about its own frame's Z through its origin (sails.rot's sense: positive takes +X
    to +Y; the boom's X runs aft, so positive swings its end to port, and the pole's runs forward, so positive swings
    its end to starboard)."""
    import sails
    o, X, Z = (np.asarray(a, float) for a in part.frame)
    R = sails.rot(Z, math.radians(deg))
    return o[None] + (np.asarray(part.V, float) - o[None]) @ R.T


def draw_sail_suits(sl_parts, srep, sp_parts, rig, pieces, deck_parts, path):
    """The three sailing suits from starboard over the rated triangles."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    import spars
    suits = [(n, srep["suits"][n]) for n in ("Genoa", "Quadrilateral", "Spinnaker")]
    mp = rig["measure_points"]
    PX, PZ = (-23.0, 21.0), (-5.0, 50.0)
    SC = 0.115
    FW = 0.6 + 3 * SC * (PX[1] - PX[0]) + 2 * 0.4 + 0.3
    FH = 1.3 + SC * (PZ[1] - PZ[0]) + 0.9
    fig = plt.figure(figsize=(FW, FH), dpi=130)
    pl = spars.RG["pole"]
    for n, (name, suit) in enumerate(suits):
        ax = fig.add_axes([(0.6 + n * (SC * (PX[1] - PX[0]) + 0.4)) / FW, 1.3 / FH, SC * (PX[1] - PX[0]) / FW,
                           SC * (PZ[1] - PZ[0]) / FH])
        _hull_fill(ax, pieces, 0, 2)
        ax.axhline(0.0, color="#3b7dbf", lw=0.8, zorder=7)
        sh = np.asarray(pieces["Shell"].sheer)
        ax.plot(sh[:, 0], sh[:, 2], color="#1f3f7f", lw=0.8, zorder=7)
        # the rated triangles
        xf = rig["attachments"]["stem_head_forestay_tack"]
        xfront = spars.at(0.0, spars.half_depth(0.0))
        fc = mp["forestay_on_mast_face"]
        ax.fill([xfront[0], xf[0], fc[0]], [xfront[2], xf[2], fc[2]], color="#e9c46a", alpha=0.25, zorder=1)
        pa, xtop, bb = (mp["boom_top_at_mast_after_face"], mp["black_band_on_mast_lower_edge"],
                        mp["black_band_on_boom_forward_edge"])
        ax.fill([pa[0], xtop[0], bb[0]], [pa[2], xtop[2], bb[2]], color="#2a9d8f", alpha=0.2, zorder=1)
        # the sails, the farthest from the viewer (to port) first
        order = sorted(suit["sails"], key=lambda k: float(np.mean(np.asarray(sl_parts[k].V, float)[:, 1])))
        for k in order:
            p = sl_parts[k]
            tris, V, _ = _cloth(p)
            ax.add_collection(PolyCollection(V[tris][:, :, [0, 2]], facecolors=[SAIL_FILL], edgecolors=[SAIL_FILL],
                                             linewidths=0.2, alpha=0.93, zorder=4))
            P = V[:, [0, 2]]
            from matplotlib.collections import LineCollection
            ax.add_collection(LineCollection([P[list(e)] for e in _boundary(tris)], colors=SAIL_EDGE, linewidths=0.8,
                                             zorder=5))
        for k in ("Mast", "Boom", "SpinnakerPole"):
            part = sp_parts[k]
            if k == "Boom":
                Vp = _posed(part, suit["boom_deg"], None)
            elif k == "SpinnakerPole" and suit.get("pole") == "stowed":
                ps = srep["pole_stowed"]
                Vp = np.asarray(part.V, float) @ np.asarray(ps["R"]).T + np.asarray(ps["t"])[None]
            elif k == "SpinnakerPole":
                Vp = _posed(part, suit["pole_deg"] - pl["set_deg"], None)
            else:
                Vp = np.asarray(part.V, float)
            polys = [Vp[list(f)][:, [0, 2]] for f in part.F]
            ax.add_collection(PolyCollection(polys, facecolors=[SPAR_PALETTE["Spar"]], edgecolors=[SPAR_PALETTE["Spar"]],
                                             linewidths=0.15, zorder=6))
        area = sum(srep["sails"][k.split(".")[0]]["area_ft2"] for k in suit["sails"])
        ax.set_title("%s suit: %s\n%.0f sq ft of sail set (rated S %.0f)" % (
            name, " + ".join(k.split(".")[0].lower() for k in suit["sails"]), area, rig["sail_area_ft2"]), fontsize=10)
        ax.set_xlim(*PX)
        ax.set_ylim(*PZ)
        ax.set_aspect("equal")
        ax.grid(alpha=0.2)
        ax.set_xlabel("x, m forward of mid-waterline")
        if n == 0:
            ax.set_ylabel("z, m above the waterline")
    fig.suptitle("Bluebonnet's suits from starboard (slice 6), sailed on starboard tack: the cloth as built, over the "
                 "rated fore triangle (yellow) and main triangle (green)", fontsize=11.5)
    fig.savefig(path)
    plt.close(fig)


def draw_running_plan(rn_parts, rnrep, pieces, deck_rep, path):
    """Slice 7's running rigging in plan, one panel for each sailing suit (starboard tack, the sheets to port): the
    deck's edge and furniture, the winches and cleats, the padeyes, the blocks and fittings, and every rope's
    centreline (the coils as laid), each loaded rope's rise onto its drum by its winch."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    sh = np.asarray(pieces["Shell"].sheer)
    o = np.argsort(sh[:, 0])
    fp = {k: np.asarray(v) for k, v in deck_rep["footprints"].items()}
    names = ("Genoa", "Quadrilateral", "Spinnaker")
    fig = plt.figure(figsize=(20, 16), dpi=130)
    colours = plt.get_cmap("tab20")
    for n, name in enumerate(names):
        ax = fig.add_axes([0.03, 0.04 + (2 - n) * 0.32, 0.95, 0.27])
        ax.plot(sh[o, 0], sh[o, 1], color="#1f3f7f", lw=1.0)
        ax.plot(sh[o, 0], -sh[o, 1], color="#1f3f7f", lw=1.0)
        for k, P in fp.items():
            ax.fill(P[:, 0], P[:, 1], color="#d8d4cc", lw=0.6, ec="#555555")
        for k, col in (("Winches", "#b08a3e"), ("RunningFittings", "#8a6a2e"), (f"Running.{name}", "#6b4f1d")):
            p = rn_parts[k]
            V = np.asarray(p.V, float)
            keep = [i for i, lb in enumerate(p.labels) if " | " in lb]
            polys = [V[list(p.F[i])][:, :2] for i in keep if V[list(p.F[i]), 2].min() < 6.0]
            ax.add_collection(PolyCollection(polys, facecolors=[col], edgecolors=[col], linewidths=0.1, zorder=3))
        for i, rp in enumerate(rnrep["ropes"][name]):
            for pc in rp["pieces"]:
                P = np.asarray(pc["path"], float)
                low = P[:, 2] < 6.0
                if low.any():
                    ax.plot(P[low, 0], P[low, 1], color=colours(i % 20), lw=max(0.6, rp["r"] * 60), zorder=4,
                            solid_capstyle="round")
        rep = rnrep["suits"][name]
        for g, w in rnrep["winches"].items():
            ax.annotate(g.replace(" winch", ""), w["at"], fontsize=6, ha="center", va="bottom", color="#222222",
                        xytext=(0, 7), textcoords="offset points", zorder=6)
        for g, (deg, L) in rep["rise_deg"].items():
            w = rnrep["winches"][rep["ropes"][g]["winch"]]
            ax.annotate(f"{deg:+.1f}\u00b0", w["at"], fontsize=6, ha="center", va="top", color="#7f1f1f",
                        xytext=(0, -7), textcoords="offset points", zorder=6)
        ax.set_xlim(-19.5, 19.0)
        ax.set_ylim(-3.6, 3.6)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
        ax.set_title(f"{name} suit, starboard tack: the running rigging on deck (winches labelled, each loaded rope's "
                     f"rise onto its drum in red; ropes above 6 m not drawn)", fontsize=10)
    fig.savefig(path)
    plt.close(fig)


HW_COLOURS = {"Bronze": "#b08a3e", "Wood": "#9c6433", "Galvanised": "#8d9297", "Gilt": "#d4af37", "Black": "#222222",
              "CowlRed": "#aa201c", "LensGreen": "#28aa5a", "LensRed": "#c81e1e", "LensClear": "#dfe8ec",
              "DeckGlass": "#bfe0d4", "Ensign": "#b22234", "Burgee": "#1c2852", "Rope": "#c2a878"}


def _hw_faces(ax, part, alpha=1.0, zorder=4):
    """A hardware part's faces from above, the higher drawn over the lower, coloured by slot."""
    from matplotlib.collections import PolyCollection
    V = np.asarray(part.V, float)
    order = sorted(range(len(part.F)), key=lambda i: V[list(part.F[i]), 2].mean())
    polys = [V[list(part.F[i])][:, :2] for i in order]
    cols = [HW_COLOURS.get(part.slot[i], "#777777") for i in order]
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors=cols, linewidths=0.05, alpha=alpha,
                                     zorder=zorder))


def draw_hardware_plan(hw_parts, hwrep, pieces, deck_rep, path, fittings=None):
    """Slice 8's deck hardware in plan, from above, bow to the right (starboard below): the deck's edge and furniture,
    every piece (the cowls standing and the ensign flown, as in harbour), the sheet tracks and their cars (from
    `fittings`, slice 7's RunningFittings), the running lights' arcs and the mooring lines' leads; close-ups of the
    bow, a side light and the counter; and the burgee's heading in each suit."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Wedge

    sh = np.asarray(pieces["Shell"].sheer)
    o = np.argsort(sh[:, 0])
    fp = {k: np.asarray(v) for k, v in deck_rep["footprints"].items()}
    lights = hwrep["lights"]
    arc_col = {"starboard": "#28aa5a", "port": "#c81e1e", "stern": "#9aa4a8"}
    tracks = None
    if fittings is not None:
        # the sheet tracks and their cars, with the eyes on them (their faces' groups name the car)
        tracks = types.SimpleNamespace(V=fittings.V, F=[], slot=[])
        for f, sl, lb in zip(fittings.F, fittings.slot, fittings.labels):
            if " car" in lb.split(" | ")[0]:
                tracks.F.append(f)
                tracks.slot.append(sl)

    def base(ax, r_arc):
        ax.plot(sh[o, 0], sh[o, 1], color="#1f3f7f", lw=1.0)
        ax.plot(sh[o, 0], -sh[o, 1], color="#1f3f7f", lw=1.0)
        for k, P in fp.items():
            ax.fill(P[:, 0], P[:, 1], color="#d8d4cc", lw=0.6, ec="#555555", zorder=1)
        for k, L in lights.items():
            a0, a1 = sorted(L["arc_deg"])
            ax.add_patch(Wedge(tuple(L["lamp"][:2]), r_arc, a0, a1, color=arc_col[k], alpha=0.22, lw=0, zorder=2))
        for ld in hwrep["mooring_leads"]:
            for pc in ld["pieces"]:
                P = np.asarray(pc["path"], float)
                ax.plot(P[:, 0], P[:, 1], color="#6b4f1d", lw=0.8, ls="--", zorder=5)
        _hw_faces(ax, hw_parts["DeckHardware"])
        _hw_faces(ax, hw_parts["Cowls.Moored"], zorder=4.5)
        if tracks is not None:
            _hw_faces(ax, tracks)
        _hw_faces(ax, hw_parts["Ensign.Moored"], alpha=0.85, zorder=5)

    fig = plt.figure(figsize=(20, 14), dpi=130)
    ax = fig.add_axes([0.03, 0.56, 0.95, 0.38])
    base(ax, 1.6)
    tags = {"Stem head": hwrep["stem_head"]["tip_x"] - 0.3, "Anchor": hwrep["anchor"]["crown"][0] + 0.7}
    for k, L in lights.items():
        ax.annotate(f"{k} light", L["lamp"][:2], (L["lamp"][0] + 0.8, L["lamp"][1] * 0.45 if k != "stern" else -2.2),
                    fontsize=8, ha="center", arrowprops=dict(arrowstyle="-", lw=0.5, color="#555"), zorder=7)
    for name, x in tags.items():
        ax.annotate(name.lower(), (x, -1.0 if name == "Anchor" else 0.0), (x, -2.6), fontsize=8, ha="center",
                    arrowprops=dict(arrowstyle="-", lw=0.5, color="#555"), zorder=7)
    ax.set_xlim(-24.0, 19.5)
    ax.set_ylim(3.6, -3.6)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=7)
    ax.set_xlabel("x, m forward of mid-waterline", fontsize=8)
    ax.set_ylabel("y, m to starboard", fontsize=8)
    ax.set_title("Bluebonnet's deck hardware in plan, from above, bow to the right (starboard below): bronze, teak, "
                 "galvanised iron, the lenses and deck glass in their colours; the running lights' arcs shaded, the "
                 "mooring lines' leads dashed, the cowls and the ensign as in harbour, the sheet tracks", fontsize=10)
    views = [("the bow: stem head, bow cleats and fairleads, chain pipe, the anchor on its chocks", 13.2, 19.0,
              -1.9, 1.3),
             ("the starboard side light on its board, and the spring cleat", 3.6, 9.0, 1.6, 3.4),
             ("the counter: stern light, ensign socket and staff, quarter cleats and fairleads", -23.6, -18.6, -1.4,
              1.4)]
    for n, (title, x0, x1, y0, y1) in enumerate(views):
        ax = fig.add_axes([0.03 + n * 0.245, 0.06, 0.225, 0.42])
        base(ax, 0.9)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
        ax.set_title(title, fontsize=8.5)
    # the burgee's heading in each suit, seen from above at the masthead
    ax = fig.add_axes([0.78, 0.08, 0.2, 0.38])
    for k, (s, b) in enumerate(hwrep["burgee"].items()):
        q = np.radians(b["flies_deg"]) if "flies_deg" in b else None
        if q is None:
            continue
        c = np.array([0.0, k * 1.2])
        ax.annotate("", c + 0.9 * np.array([np.cos(q), np.sin(q)]), c, arrowprops=dict(arrowstyle="-|>", lw=1.2,
                                                                                       color="#1c2852"))
        ax.plot([c[0]], [c[1]], "o", ms=4, color="#b08a3e")
        ax.text(c[0] + 1.1, c[1], f"{s}: {b['flies_deg']:+.0f}\u00b0", fontsize=8, va="center")
    ax.set_xlim(-1.2, 3.2)
    ax.set_ylim(len(hwrep["burgee"]) * 1.2 - 0.4, -0.8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("the burgee's heading from forward in each suit\n(from above, bow to the right: streaming down the "
                 "apparent wind)", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)


def draw_all(pieces, fin, out, parts=None, deck_rep=None, rig=None, rigging=None, sails=None, running=None,
             hardware=None):
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
        if rigging is not None:
            draw_rigging_plan(rigging[0], rigging[1], rig[0], rig[1], pieces, parts,
                              os.path.join(out, "rigging_plan.png"), rigging[2])
        if sails is not None:
            draw_sail_cut(sails[0], sails[1], sails[2], os.path.join(out, "sail_cut.png"))
            draw_sail_suits(sails[0], sails[1], rig[0], rig[1], pieces, parts, os.path.join(out, "sail_suits.png"))
        if running is not None:
            draw_running_plan(running[0], running[1], pieces, deck_rep, os.path.join(out, "running_plan.png"))
        if hardware is not None:
            draw_hardware_plan(hardware[0], hardware[1], pieces, deck_rep, os.path.join(out, "hardware_plan.png"),
                               fittings=running[0]["RunningFittings"] if running is not None else None)
    except ImportError:
        print("the drawings were not drawn: they need matplotlib")
