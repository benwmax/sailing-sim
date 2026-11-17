"""Build the house wall and roof texture sets at real sizes (Track E2, docs/envloop/buildmat).

    python3 -I Tools/envloop/buildmat/make_textures.py [names...] [--px 1024] [--out DIR]

Run fetch_sources.py first. Writes, per finish in cards.json, three PNGs to Data/BuildMat/raw/out/ (git-ignored) plus
textures.json:

  <name>_C.png  colour (sRGB). Brick and stone carry their own colour; painted finishes (siding, battens, stucco, metal)
                are a neutral 0.8 grey with grain, tinted by the house's paint in the material.
  <name>_N.png  normal (linear), from the height: x along the wall or eave, y UP the wall or slope (green up, OpenGL
                style), z out. The material flips green if the mesh's tangent frame needs it.
  <name>_M.png  mask (linear): R ambient occlusion, G roughness, B unit id (one random 0..1 per brick, stone, board,
                tab or panel; mortar and gaps 0), A height (0 = 8 mm deep .. 1 = 25 mm proud, 0.32 = the wall plane).

Image row 0 is the TOP of the tile: sample at (u / tile_w, -v / tile_h) with UV0 in metres (u along, v up).

The layout is drawn here from the card's sizes (whole bricks, boards, rows per tile, so courses run on across tiles);
the CC0 scans add only fine grain (fetch_sources.py). Deterministic: the same cards give the same files.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RAW = os.path.join(REPO, "Data", "BuildMat", "raw")
sys.path.insert(0, HERE)
import pack as P    # noqa: E402

OUT = P.tex_dir()
H_LO, H_HI = -8.0, 25.0          # mm range of the A channel
PLANE = -H_LO / (H_HI - H_LO)    # 0.2424: the wall plane


def cards():
    """The region pack (packs/<name>.json, chosen by --pack): its walls, roofs and test houses."""
    return P.load()


def srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def hexlin(h):
    h = h.lstrip("#")
    return srgb_to_lin([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def blur(a, sigma):
    """Gaussian blur of a float image, wrapping at the edges (the tiles are periodic): by FFT."""
    if sigma <= 0:
        return a
    h, w = a.shape
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.rfftfreq(w)[None, :]
    k = np.exp(-2.0 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    return np.fft.irfft2(np.fft.rfft2(a) * k, s=a.shape)


def blur_x(a, sigma):
    """Blur along rows only (wrapping): stretches grain along a board."""
    k = int(3 * sigma) + 1
    x = np.arange(-k, k + 1)
    w = np.exp(-0.5 * (x / sigma) ** 2)
    w /= w.sum()
    out = np.zeros_like(a)
    for o, ww in zip(x, w):
        out += ww * np.roll(a, o, axis=1)
    return out


# ------------------------------------------------------------------ grain from the CC0 scans

_GRAIN = {}


def grain(sid, tile_w, tile_h, pw, ph, channel="height", hp=12.0):
    """The scan's fine detail resampled to this tile at its real size, high-passed (sigma hp px), unit variance.
    The scan repeats a whole number of times across the tile (stretched a few percent to fit)."""
    key = (sid, tile_w, tile_h, pw, ph, channel, hp)
    if key in _GRAIN:
        return _GRAIN[key]
    src = json.load(open(os.path.join(HERE, "sources.json")))["sources"][sid]
    path = os.path.join(RAW, sid, ("height" if channel == "height" else "color") + ".jpg")
    if not os.path.exists(path):
        raise SystemExit("missing %s: run fetch_sources.py first" % path)
    im = Image.open(path).convert("L")
    nx = max(1, round(tile_w / src["width_m"]))
    ny = max(1, round(tile_h / src["width_m"]))
    cw, chh = max(8, pw // nx), max(8, ph // ny)
    small = np.asarray(im.resize((cw, chh), Image.LANCZOS), np.float64) / 255.0
    g = np.tile(small, (ny + 1, nx + 1))[:ph, :pw]
    if g.shape != (ph, pw):
        g = np.asarray(Image.fromarray(g.astype(np.float32), "F").resize((pw, ph), Image.BILINEAR), np.float64)
    g = g - blur(g, hp)
    g /= max(g.std(), 1e-6)
    _GRAIN[key] = g
    return g


# ------------------------------------------------------------------ helpers

def grid(card, px):
    tw, th = card["tile_m"]
    pw = ph = px
    x = (np.arange(pw) + 0.5) / pw * tw                 # metres along
    y = th - (np.arange(ph) + 0.5) / ph * th            # metres up (row 0 = top)
    X, Y = np.meshgrid(x, y)
    return X, Y, tw, th, pw, ph


def unit_hash(*ints, seed=0):
    """A random 0..1 per integer tuple (stable)."""
    h = np.zeros(np.shape(ints[0]), np.uint64) + np.uint64(seed * 2654435761 + 97)
    for k, a in enumerate(ints):
        a = np.asarray(a, np.int64).astype(np.uint64)
        h ^= a + np.uint64(0x9E3779B97F4A7C15) + (h << np.uint64(6)) + (h >> np.uint64(2))
        h *= np.uint64(0xBF58476D1CE4E5B9 + 2 * k)
        h ^= h >> np.uint64(31)
    return (h % np.uint64(1 << 24)).astype(np.float64) / float(1 << 24)


def palette_pick(pal, u):
    cols = np.array([hexlin(p) for p in pal])
    i = np.minimum((u * len(cols)).astype(int), len(cols) - 1)
    return cols[i]


def value_noise(X, Y, cell, seed, tw, th):
    """Smooth periodic value noise on the tile (cell in metres, rounded so it tiles)."""
    nx = max(1, round(tw / cell)); ny = max(1, round(th / cell))
    qx, qy = X / tw * nx, Y / th * ny
    ix, iy = np.floor(qx).astype(int), np.floor(qy).astype(int)
    fx, fy = qx - ix, qy - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    h = lambda a, b: unit_hash(a % nx, b % ny, seed=seed)
    return (h(ix, iy) * (1 - fx) + h(ix + 1, iy) * fx) * (1 - fy) + (h(ix, iy + 1) * (1 - fx) + h(ix + 1, iy + 1) * fx) * fy


def ao_from_height(h_mm, mm_per_px):
    """Cavity occlusion: how far a pixel sits below its neighbourhood at two radii."""
    a = 0.0
    for r_mm, k in ((6.0, 0.06), (20.0, 0.025)):
        s = max(0.7, r_mm / mm_per_px)
        a += k * np.maximum(0.0, blur(h_mm, s) - h_mm)
    return np.clip(1.0 - a, 0.25, 1.0)


def normal_from_height(h_mm, mmx, mmy, max_slope=None):
    dx = (np.roll(h_mm, -1, 1) - np.roll(h_mm, 1, 1)) / (2 * mmx)
    dy_up = (np.roll(h_mm, 1, 0) - np.roll(h_mm, -1, 0)) / (2 * mmy)   # row 0 is the top: up = toward smaller rows
    if max_slope:
        # a ridge narrower than a pixel or two (a standing seam) would otherwise turn its pixels side-on and read black
        dx, dy_up = np.clip(dx, -max_slope, max_slope), np.clip(dy_up, -max_slope, max_slope)
    n = np.stack([-dx, -dy_up, np.ones_like(dx)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ------------------------------------------------------------------ the finishes

def brick(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    u = card["unit_mm"]
    bl, bh = u["brick"][0] / 1000.0, u["brick"][1] / 1000.0
    j = u["joint"] / 1000.0
    ch = u["course"] / 1000.0
    pitch = bl + j
    n_across = card["bricks_across"]
    seed = card["id"] * 101 + 7
    course = np.floor(Y / ch).astype(int)
    off = 0.5 * pitch * (course % 2) + (unit_hash(course % card["courses"], seed=seed) - 0.5) * 0.012
    bx = X - off
    b = np.floor(bx / pitch).astype(int)
    xb = bx - b * pitch              # 0..pitch within the brick + joint
    yc = Y - course * ch             # 0..course; the bed joint at the top of the course
    bid = (b % n_across) + n_across * (course % card["courses"])
    r1 = unit_hash(bid, seed=seed)
    r2 = unit_hash(bid, seed=seed + 1)
    r3 = unit_hash(bid, seed=seed + 2)
    # chipped edges: the edge distance wobbles by a few mm (noise per brick)
    wob = (value_noise(X, Y, 0.03, seed + 3, tw, th) - 0.5) * 0.0025 + (value_noise(X, Y, 0.008, seed + 4, tw, th) - 0.5) * 0.0012
    d = np.minimum(np.minimum(xb, bl - xb), np.minimum(yc, bh - yc)) + wob
    is_brick = d > 0
    gb = grain("brickface", tw, th, pw, ph, hp=10.0)
    gm = grain("mortar", tw, th, pw, ph, hp=6.0)
    # per-brick grain window: shift the grain by a random offset per brick
    oy = (r2 * ph).astype(int); ox = (r3 * pw).astype(int)
    rows = (np.arange(ph)[:, None] + oy) % ph
    cols = (np.arange(pw)[None, :] + ox) % pw
    gbb = gb[rows, cols]
    # heights (mm): the face slightly domed, edges rounded over 2.5 mm, grain; mortar a concave tooled joint 3-5 mm back
    face = 0.6 * gbb + 0.4 * (r1 - 0.5) + np.minimum(1.0, d / 0.0025) * 0.6
    t_joint = np.where(xb > bl, (xb - bl) / j, np.where(yc > bh, (yc - bh) / (ch - bh), 0.5))
    mortar = -3.0 - 1.6 * (1 - (2 * np.clip(t_joint, 0, 1) - 1) ** 2) + 0.35 * gm
    hmm = np.where(is_brick, face, mortar)
    # colour
    col = palette_pick(card["palette"], r1)
    col = col * (1 + 0.14 * (r2 - 0.5))[..., None]
    col = col * (1 + 0.07 * gbb)[..., None]
    if card.get("ironspot"):
        spot = grain("brickface", tw, th, pw, ph, hp=1.2)[rows, cols]
        col = np.where((spot > 2.4)[..., None], col * 0.35, col)
        # flashed (darker) ends on some bricks
        endk = np.exp(-np.minimum(xb, bl - xb) / 0.03) * (r3 > 0.55)
        col = col * (1 - 0.35 * endk)[..., None]
    mc = hexlin(card["mortar"]) * (1 + 0.12 * gm)[..., None]
    col = np.where(is_brick[..., None], col, mc)
    rough = np.where(is_brick, card["roughness"][0] + 0.04 * gbb, card["roughness"][1] + 0.03 * gm)
    uid = np.where(is_brick, 0.02 + 0.98 * r1, 0.0)
    return col, hmm, rough, uid, (tw, th, pw, ph)


def limestone(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    u = card["unit_mm"]
    j = u["joint"] / 1000.0
    seed = card["id"] * 101 + 7
    rng = np.random.default_rng(seed)
    heights = []
    while sum(heights) < th - 0.05:
        heights.append(rng.choice(u["course_heights"]) / 1000.0)
    heights = np.array(heights) * th / sum(heights)
    edges = np.concatenate([[0.0], np.cumsum(heights)])
    course = np.clip(np.searchsorted(edges, Y, side="right") - 1, 0, len(heights) - 1)
    y0 = edges[course]; hc = heights[course]
    yc = Y - y0
    # each course: random stone lengths summing to the tile width, from a random start
    xs_list, starts = [], []
    for c in range(len(heights)):
        ls = []
        while sum(ls) < tw - 0.1:
            ls.append(rng.uniform(*u["length"]) / 1000.0)
        ls = np.array(ls) * tw / sum(ls)
        xs_list.append(np.concatenate([[0.0], np.cumsum(ls)]))
        starts.append(rng.uniform(0, tw))
    sid = np.zeros(X.shape, int); xl = np.zeros(X.shape); ln = np.zeros(X.shape)
    for c in range(len(heights)):
        m = course == c
        xx = (X[m] - starts[c]) % tw
        e = xs_list[c]
        k = np.clip(np.searchsorted(e, xx, side="right") - 1, 0, len(e) - 2)
        sid[m] = c * 100 + k
        xl[m] = xx - e[k]
        ln[m] = e[k + 1] - e[k]
    wob = (value_noise(X, Y, 0.05, seed + 3, tw, th) - 0.5) * 0.008 + (value_noise(X, Y, 0.012, seed + 4, tw, th) - 0.5) * 0.003
    d = np.minimum(np.minimum(xl - j / 2, ln - j / 2 - xl), np.minimum(yc - j / 2, hc - j / 2 - yc)) + wob
    is_stone = d > 0
    r1 = unit_hash(sid, seed=seed); r2 = unit_hash(sid, seed=seed + 1); r3 = unit_hash(sid, seed=seed + 2)
    gs = grain("stone", tw, th, pw, ph, hp=14.0)
    gm = grain("mortar", tw, th, pw, ph, hp=6.0)
    oy = (r2 * ph).astype(int); ox = (r3 * pw).astype(int)
    gss = gs[(np.arange(ph)[:, None] + oy) % ph, (np.arange(pw)[None, :] + ox) % pw]
    lump = value_noise(X, Y, 0.06, seed + 5, tw, th) - 0.5
    face = 4.0 * np.minimum(1.0, np.maximum(d, 0.0) / 0.02) ** 0.6 + 2.5 * lump + 1.2 * gss + 2.0 * (r1 - 0.5)
    mortar = -6.0 + 0.4 * gm
    hmm = np.where(is_stone, face, mortar)
    col = palette_pick(card["palette"], r1) * (1 + 0.10 * (r2 - 0.5))[..., None]
    col = col * (1 + 0.06 * gss + 0.08 * lump)[..., None]
    # a few stones with a rusty or grey cast (iron in the chalk)
    tint = np.where((r3 > 0.85)[..., None], np.array([1.05, 0.97, 0.86]), np.where((r3 < 0.1)[..., None], np.array([0.93, 0.94, 0.95]), 1.0))
    col = col * tint
    mc = hexlin(card["mortar"]) * (1 + 0.1 * gm)[..., None]
    col = np.where(is_stone[..., None], col, mc)
    rough = np.where(is_stone, card["roughness"][0] + 0.03 * gss, card["roughness"][1])
    uid = np.where(is_stone, 0.02 + 0.98 * r1, 0.0)
    return col, hmm, rough, uid, (tw, th, pw, ph)


def lap_siding(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    u = card["unit_mm"]
    e = u["exposure"] / 1000.0
    seed = card["id"] * 101 + 7
    c = np.floor(Y / e).astype(int)
    t = (Y - c * e) / e                       # 0 at the butt (bottom) .. 1 under the next board
    butt_x = unit_hash(c % card["courses"], seed=seed) * tw
    dx = (X - butt_x + tw / 2) % tw - tw / 2  # distance to this course's butt joint
    board = np.where(dx < 0, 0, 1)
    bid = (c % card["courses"]) * 2 + board
    r1 = unit_hash(bid, seed=seed + 1)
    gw = grain("wood", tw, th, pw, ph, hp=8.0)
    gw = blur_x(gw, 6.0); gw /= max(gw.std(), 1e-6)
    # wedge board: 8 mm proud at the butt, 2 mm under the next; a 1.5 mm rounded drip edge
    hmm = 2.0 + 6.0 * (1 - t) - 2.0 * np.exp(-t / 0.015) + 0.25 * gw
    gap = np.abs(dx) < 0.0016
    hmm = np.where(gap, 0.0, hmm)
    col = np.ones(X.shape + (3,)) * 0.8 * (1 + 0.025 * gw + 0.02 * (r1 - 0.5))[..., None]
    col = np.where(gap[..., None], col * 0.55, col)
    rough = card["roughness"][0] + 0.02 * gw
    uid = np.where(gap, 0.0, 0.02 + 0.98 * r1)
    return col, hmm, rough, uid, (tw, th, pw, ph)


def board_batten(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    u = card["unit_mm"]
    cen = u["centres"] / 1000.0; bw = u["batten"] / 1000.0; pr = u["batten_proud"]
    seed = card["id"] * 101 + 7
    k = np.floor(X / cen + 0.5).astype(int)
    dxb = X - k * cen                          # distance to the batten's centre
    batten = np.abs(dxb) < bw / 2
    edge = np.clip((bw / 2 - np.abs(dxb)) / 0.003, 0, 1)
    bidx = np.floor(X / cen).astype(int) % card["boards"]
    r1 = unit_hash(np.where(batten, 100 + k % card["boards"], bidx), seed=seed)
    gw = grain("wood", th, tw, ph, pw, hp=8.0).T     # grain runs up the boards
    gw = blur_x(gw.T, 6.0).T; gw /= max(gw.std(), 1e-6)
    hmm = np.where(batten, pr * np.sqrt(edge), 0.0) + 0.25 * gw
    # the board joint under a batten is hidden; a hairline gap where a board meets the next is under it too
    col = np.ones(X.shape + (3,)) * 0.8 * (1 + 0.025 * gw + 0.02 * (r1 - 0.5))[..., None]
    rough = card["roughness"][0] + 0.02 * gw
    uid = 0.02 + 0.98 * r1
    return col, hmm, rough, uid, (tw, th, pw, ph)


def stucco(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    seed = card["id"] * 101 + 7
    gs = grain("stucco", tw, th, pw, ph, hp=4.0)
    gl = grain("stucco", tw, th, pw, ph, hp=30.0)
    # trowel sweeps: arcs about 40 cm, from two periodic noises bent through a sine
    n1 = value_noise(X, Y, 0.35, seed, tw, th); n2 = value_noise(X, Y, 0.18, seed + 1, tw, th)
    sweep = np.sin((n1 * 6.0 + n2 * 2.0) * np.pi) * 0.5 + 0.5
    # nothing broader than the trowel's 20-40 cm, and that faint: the material's wash does the large scale so the
    # 4 m tile never shows
    hmm = 0.55 * gs + 0.15 * gl + 0.25 * (sweep - 0.5)
    col = np.ones(X.shape + (3,)) * 0.8 * (1 + 0.03 * gs)[..., None]
    rough = card["roughness"][0] - 0.02 * (sweep - 0.5)
    uid = 0.02 + 0.98 * value_noise(X, Y, 1.0, seed + 2, tw, th)
    return col, hmm, rough, uid, (tw, th, pw, ph)


def shingles(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    u = card["unit_mm"]
    e = u["exposure"] / 1000.0; sl = u["strip"] / 1000.0
    seed = card["id"] * 101 + 7
    c = np.floor(Y / e).astype(int)
    t = (Y - c * e) / e                       # 0 at the drip edge of this course .. 1 under the next course
    cc = c % card["courses"]
    off = unit_hash(cc, seed=seed) * sl
    sx = X - off
    s = np.floor(sx / sl).astype(int)
    xs = sx - s * sl                           # 0..strip
    sidx = s % int(round(tw / sl))
    # tabs: each strip has its own random tab widths (100-230 mm) with dragon-tooth gaps (35-70 mm) between them
    rng = np.random.default_rng(seed)
    nstrip = card["courses"] * int(round(tw / sl))
    tab_edges, gap_w, tab_len = [], [], []
    for _ in range(nstrip):
        ws = []
        while sum(ws) < sl - 0.08:
            ws.append(rng.uniform(*u["tab"]) / 1000.0)
        ws = np.array(ws) * sl / sum(ws)
        tab_edges.append(np.concatenate([[0.0], np.cumsum(ws)]))
        gap_w.append(rng.uniform(0.035, 0.07, len(ws)))
        tab_len.append(rng.uniform(0.62, 1.0, len(ws)))
    strip_id = cc * int(round(tw / sl)) + sidx
    tab = np.zeros(X.shape, int); xt = np.zeros(X.shape); tl = np.ones(X.shape); gw_ = np.zeros(X.shape); tw_ = np.ones(X.shape)
    for k in np.unique(strip_id):
        m = strip_id == k
        ed = tab_edges[k]
        i = np.clip(np.searchsorted(ed, xs[m], side="right") - 1, 0, len(ed) - 2)
        tab[m] = i; xt[m] = xs[m] - ed[i]; tw_[m] = ed[i + 1] - ed[i]
        gw_[m] = gap_w[k][i]; tl[m] = tab_len[k][i]
    # dragon-tooth gaps: widest at the drip edge, closing to nothing at 55-100% of the exposure (the tab's length)
    in_gap = (xt > (tw_ - gw_ * np.clip(1.0 - t / (0.55 + 0.45 * tl), 0, 1))) & (t < 0.55 + 0.45 * tl)
    top = ~in_gap
    uidx = strip_id * 16 + tab
    r1 = unit_hash(uidx, seed=seed + 1); r2 = unit_hash(uidx, seed=seed + 2)
    rngs = np.random.default_rng(seed + 9)
    speck = rngs.normal(0, 1, X.shape)
    speck = 0.7 * speck + 0.3 * blur(speck, 0.8) * 2.0
    hmm = 1.5 * (1 - t) + np.where(top, 3.2, 0.0) + 0.35 * speck
    hmm -= 2.0 * np.exp(-t / 0.02)
    # granules: each tab is its own blend of two palette colours, mixed grain by grain (about 2 mm, under a pixel)
    pal = card["palette"]
    ca = palette_pick(pal, r1); cb = palette_pick(pal, r2); cg = palette_pick(pal, rngs.random(X.shape))
    pick = rngs.random(X.shape)
    col = np.where((pick < 0.5)[..., None], ca, np.where((pick < 0.8)[..., None], cb, cg))
    col = 0.55 * col + 0.45 * (0.5 * ca + 0.5 * cb)
    # keep the blend's spread modest: from 15 m a roof reads as one colour with a fine tab-by-tab flicker
    mean = np.array([hexlin(h) for h in pal]).mean(0)
    col = mean + 0.45 * (col - mean)
    col = col * (1 + 0.06 * speck)[..., None]
    # the laminate's under layer shows dark in the gaps; a thin shadow band along every drip edge
    col = np.where(top[..., None], col, col * 0.55)
    col = col * (1 - 0.25 * np.exp(-t / 0.05))[..., None]
    rough = card["roughness"][0] + 0.03 * speck
    uid = np.where(top, 0.02 + 0.98 * r1, 0.0)
    return col, hmm, rough, uid, (tw, th, pw, ph)


def metal_seam(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    u = card["unit_mm"]
    pnl = u["panel"] / 1000.0; sh = u["seam_height"]; sw = u["seam_width"] / 1000.0
    seed = card["id"] * 101 + 7
    k = np.floor(X / pnl + 0.5).astype(int)
    dxs = X - k * pnl                           # to the seam at the panel edge
    seam = np.clip(1 - np.abs(dxs) / (sw / 2), 0, 1)
    seam_h = sh * np.sqrt(seam) * (np.abs(dxs) < sw / 2)
    pidx = np.floor(X / pnl).astype(int) % card["panels"]
    xp = X - np.floor(X / pnl) * pnl
    pencil = sum(np.exp(-((xp - f * pnl) / 0.003) ** 2) for f in (1 / 3, 2 / 3)) * 1.0
    # oil canning: a slow wave in each pan (a few tenths of a mm over 30 cm)
    can = (value_noise(X, Y, 0.3, seed + pidx, tw, th) - 0.5) * 1.2 * np.sin(np.clip(xp / pnl, 0, 1) * np.pi)
    gmet = grain("metal", tw, th, pw, ph, hp=5.0)
    hmm = seam_h + pencil + can + 0.08 * gmet
    r1 = unit_hash(pidx, seed=seed)
    col = np.ones(X.shape + (3,)) * 0.8 * (1 + 0.02 * gmet + 0.015 * (r1 - 0.5))[..., None]
    rough = card["roughness"][0] + 0.05 * gmet + 0.04 * (r1 - 0.5) + 0.08 * (seam > 0)
    uid = 0.02 + 0.98 * r1
    return col, hmm, rough, uid, (tw, th, pw, ph)


def membrane_flat(card, px):
    X, Y, tw, th, pw, ph = grid(card, px)
    seed = card["id"] * 101 + 7
    lap = card["unit_mm"]["lap"] / 1000.0
    xl = X % tw
    seam = np.clip(1 - np.abs((xl + tw / 2) % tw - tw / 2) / (lap / 2), 0, 1)   # the welded lap where one roll meets the next
    gs = grain("stucco", tw, th, pw, ph, hp=3.0)
    # loose wrinkles and the board joints under the membrane (1.2 m insulation boards) show as faint lines
    wr = value_noise(X, Y, 0.25, seed, tw, th) - 0.5
    board = np.exp(-(((Y + 0.61) % 1.22 - 0.61) / 0.004) ** 2)
    hmm = 1.8 * np.sqrt(seam) + 0.35 * wr + 0.08 * gs - 0.25 * board
    col = np.ones(X.shape + (3,)) * 0.8 * (1 + 0.015 * gs)[..., None]
    rough = card["roughness"][0] + 0.02 * gs
    uid = 0.02 + 0.98 * unit_hash(np.floor(X / tw).astype(int), seed=seed) * np.ones(X.shape)
    return col, hmm, rough, uid, (tw, th, pw, ph)


MAX_SLOPE = {"standing_seam": 0.6}

# one maker per class (pack.CLASSES); a region's finishes pick a class and bring their own sizes and colours
MAKERS = {"brick": brick, "stone": limestone, "lap": lap_siding, "batten": board_batten, "render": stucco, "shingle": shingles,
          "standing_seam": metal_seam, "membrane": membrane_flat}


def build(card, px):
    col, hmm, rough, uid, (tw, th, pw, ph) = MAKERS[card["class"]](card, px)
    mmx, mmy = tw * 1000.0 / pw, th * 1000.0 / ph
    ao = ao_from_height(hmm, 0.5 * (mmx + mmy))
    n = normal_from_height(hmm, mmx, mmy, max_slope=MAX_SLOPE.get(card["class"]))
    hA = np.clip((hmm - H_LO) / (H_HI - H_LO), 0, 1)
    return dict(col=np.clip(col, 0, 1), n=n, ao=ao, rough=np.clip(rough, 0.05, 1.0), uid=np.clip(uid, 0, 1), h=hA,
                h_mm=hmm, tile=(tw, th), px=(pw, ph))


def save(name, t, out):
    os.makedirs(out, exist_ok=True)
    c8 = (lin_to_srgb(t["col"]) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(c8, "RGB").save(os.path.join(out, name + "_C.png"))
    n8 = ((t["n"] * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(n8, "RGB").save(os.path.join(out, name + "_N.png"))
    m = np.stack([t["ao"], t["rough"], t["uid"], t["h"]], -1)
    Image.fromarray((m * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(out, name + "_M.png"))


def build_noise(px=512, seed=4242):
    """T_BuildNoise: one periodic RGBA noise the wear reads at 1 m and 0.25 m (buildmat_hlsl.py N1, N2).
    R value noise (three octaves), G spots (finer, for efflorescence, mildew, lichen), B vertical streaks (tall thin
    cells, for algae and rain), A crack network (high on the lines where a noise crosses its middle)."""
    t = 1.0
    x = (np.arange(px) + 0.5) / px
    X, Y = np.meshgrid(x, 1.0 - x)

    def fbm(cells, s, octaves=3):
        out, amp, tot = 0.0, 1.0, 0.0
        for o in range(octaves):
            out = out + amp * value_noise(X, Y, t / (cells * 2 ** o), s + o, t, t)
            tot += amp; amp *= 0.5
        return out / tot

    R = fbm(4, seed)
    G = fbm(16, seed + 10, 2)
    # streaks: cells 1/24 wide and 1/3 tall
    nx, ny = 24, 3
    qx, qy = X * nx, Y * ny
    ix, iy = np.floor(qx).astype(int), np.floor(qy).astype(int)
    fx, fy = qx - ix, qy - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    hh = lambda a, b: unit_hash(a % nx, b % ny, seed=seed + 20)
    B = (hh(ix, iy) * (1 - fx) + hh(ix + 1, iy) * fx) * (1 - fy) + (hh(ix, iy + 1) * (1 - fx) + hh(ix + 1, iy + 1) * fx) * fy
    n = fbm(6, seed + 30)
    A = np.clip(1.0 - np.abs(n - 0.5) * 40.0, 0, 1) * np.clip(fbm(3, seed + 40) * 1.6 - 0.3, 0, 1)
    A = np.maximum(A, 0) ** 0.7
    def stretch(v):
        lo, hi = np.percentile(v, 1), np.percentile(v, 99)
        return np.clip((v - lo) / (hi - lo), 0, 1)
    return np.stack([stretch(R), stretch(G), stretch(B), A], -1)


def all_cards():
    c = cards()
    return [("wall", x) for x in c["walls"]] + [("roof", x) for x in c["roofs"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--px", type=int, default=cards()["px"])
    ap.add_argument("--out", default=OUT)
    P.add_arg(ap)
    a = ap.parse_args()
    meta = {}
    mp = os.path.join(a.out, "textures.json")
    if os.path.exists(mp):
        meta = json.load(open(mp))
    for kind, card in all_cards():
        if a.names and card["name"] not in a.names:
            continue
        t = build(card, a.px)
        save(card["name"], t, a.out)
        meta[card["name"]] = dict(kind=kind, id=card["id"], cls=card["class"], pack=P.NAME, tile_m=list(t["tile"]), px=list(t["px"]),
                                  mm_per_px=[round(t["tile"][0] * 1000 / t["px"][0], 2), round(t["tile"][1] * 1000 / t["px"][1], 2)])
        print(card["name"], meta[card["name"]])
    nz = build_noise()
    Image.fromarray((nz * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(a.out, "BuildNoise.png"))
    meta["BuildNoise"] = dict(kind="noise", px=[nz.shape[1], nz.shape[0]], tile_m=[1.0, 1.0], note="read at 1 m and 0.25 m")
    json.dump(meta, open(mp, "w"), indent=1)


if __name__ == "__main__":
    main()
