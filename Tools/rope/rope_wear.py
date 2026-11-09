"""Rope wear for the texture loop (docs/texture-loop/rope.md): the five wear levels of a braided line, as the game draws them.

This is the numpy twin of M_RigRope's shader (scripts/import_boat_detail.py ROPE_CODE): the same maths line for line, so
the swatches the loop scores are what the game will show, without an Unreal build. Change one, change the other.

    python3 Tools/rope/rope_wear.py [out dir]        # writes rope_L0..L4.png swatches and rope_ladder.png

Wear comes from the boat's Age (years) and Care (0 neglected .. 1 kept), split into two numbers (texture loop plan):
  time  what care can't undo (sun fade on lines that stay rigged)
  dirt  what care removes (grey grime in the weave, fuzz, mildew)
Rope is a consumable: a kept boat replaces her sheets every few seasons, so the rope's own age is capped by care
(ROPE_LIFE_YEARS) and a kept 30-year-old boat carries nearly new line (level L3).
"""
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
ROPE_DIR = os.path.join(REPO, "Inputs", "rope")
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
import wear as W  # noqa: E402  (the shared time_k / dirt_k)

# The five levels (Tools/texloop/levels.json: Age years, Care).
LEVELS = {lv["id"]: (lv["age"], lv["care"]) for lv in W.levels()}


def saturate(x):
    return np.clip(x, 0.0, 1.0)


def rope_wear(age, care):
    """(fade, grime, fuzz, mildew), each 0..1, from the boat's Age and Care. Mirrors ROPE_CODE (M_RigRope) and BOAT_CODE's
    surf == 9: the shared time_k and dirt_k (Tools/texloop/wear.py) taken at the rope's own age."""
    care = float(np.clip(care, 0, 1))
    if age < 0:
        return 0.3 * 0.4, 0.5 * 0.35, 0.4 * 0.4, 0.0         # unset: the old fixed look (Fade 0.4, Dirt 0.5)
    ra = min(age, 3.0 + 12.0 * (1.0 - care))           # replaced every 3 years when kept, 15 when not
    t, d = W.time_k(ra, care), W.dirt_k(ra, care)
    fade = min(0.35 * t + 0.1 * d, 1.0)              # polyester dyes hold: a club boat's red is still red
    grime = min(0.8 * d, 1.0)
    fuzz = min(0.45 * t + 0.75 * d, 1.0)
    mildew = max((d - 0.6) / 0.4, 0.0) * (1 - care)
    return fade, grime, fuzz, mildew


def hash2(ix, iy, seed=0.0):
    """frac(sin(dot)) hash, as the shader's."""
    return frac(np.sin(ix * 12.9898 + iy * 78.233 + seed) * 43758.5453)


def frac(x):
    """HLSL frac: x - floor(x), positive for negative x too."""
    return x - np.floor(x)


def vnoise(x, y, seed=0.0):
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hash2(ix, iy, seed), hash2(ix + 1, iy, seed)
    c, d = hash2(ix, iy + 1, seed), hash2(ix + 1, iy + 1, seed)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def load_maps():
    m = np.asarray(Image.open(os.path.join(ROPE_DIR, "T_Rope_Braid24_M.png"))).astype(np.float64) / 255
    n = np.asarray(Image.open(os.path.join(ROPE_DIR, "T_Rope_Braid24_N.png"))).astype(np.float64) / 127.5 - 1
    lut = np.asarray(Image.open(os.path.join(ROPE_DIR, "T_RopeColourways.png"))).astype(np.float64) / 255
    return m, n, lut


def sample(tex, u, v):
    """Bilinear, wrapping (UV in tiles; V down the image rows as Unreal samples)."""
    h, w = tex.shape[:2]
    x, y = (u % 1.0) * w - 0.5, (v % 1.0) * h - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    x0, y0, x1, y1 = x0 % w, y0 % h, (x0 + 1) % w, (y0 + 1) % h
    t = tex if tex.ndim == 3 else tex[..., None]
    out = (t[y0, x0] * (1 - fx) + t[y0, x1] * fx) * (1 - fy) + (t[y1, x0] * (1 - fx) + t[y1, x1] * fx) * fy
    return out if tex.ndim == 3 else out[..., 0]


def rope_shade(u, v, look, maps, age, care, ndotv, fw, legacy=False):
    """ROPE_CODE in numpy: base colour (linear), roughness and a normal tilt strength, per pixel.
    u, v: UV0 (U along the rope over one lay, V once round); ndotv: |N.V|; fw: the lay pattern's screen derivative.
    legacy: the shader before the texture loop (main 8219696): Fade 0.4 and Dirt 0.5 on every boat, whatever her age."""
    m_tex, _, lut = maps
    m = sample(m_tex, u, v)
    col = int(min(look, 15))
    base = srgb_to_lin(lut[0, col])
    tracer = srgb_to_lin(lut[1, col])
    pattern = lut[2, col]
    mask = (m[..., 1:4] * pattern).sum(-1)
    c = base * (1 - mask[..., None]) + tracer * mask[..., None]
    deep = 1.0 - m[..., 0]
    if legacy:
        c = c + (np.array([0.62, 0.60, 0.55]) - c) * (0.3 * 0.4)
        c = c + (np.array([0.11, 0.095, 0.07]) - c) * saturate((deep * 1.2 + 0.3) * 0.5 * 0.35)[..., None]
        fade, grime, fuzz, mildew = 0.4, 0.0, 0.0, 0.0
        return _rope_tail(c, u, v, deep, ndotv, fw, 0.0, legacy_fade=0.4)
    fade, grime, fuzz, mildew = rope_wear(age, care)
    # ROPE_WEAR: sun fade first (dyes go pale and grey: red toward pink, blue toward slate, white toward ivory-grey)
    lum = (c * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
    c = c + (np.clip(lum * 0.75 + 0.12, 0, 1) * np.array([1.0, 0.985, 0.94]) - c) * (0.55 * fade)
    # grime: grey-brown worked into the whole cover, darker in the weave and in patches along the line (cleats, fairleads)
    patch = vnoise(u * 0.9, np.zeros_like(u) + 3.1 * look, 1.7)
    smudge = saturate(vnoise(u * 4.0, v * 2.0 + 7.0 * look, 2.9) * 2.2 - 1.2)        # dark smudges a hand or cleat left
    g = saturate(grime * (0.45 + 0.6 * patch + 1.2 * smudge))
    c = c + (c * np.array([0.52, 0.50, 0.45]) + np.array([0.012, 0.011, 0.008]) - c) * g[..., None]
    # dirt goes into the weave first: even a few months' use greys the grooves (sqrt: visible early)
    c = c * (1.0 - 0.5 * np.sqrt(grime) * deep)[..., None]
    # mildew: dark grey-green specks in the weave on a neglected line
    sp = hash2(np.floor(u * 90.0), np.floor(v * 60.0), 5.3)
    mil = mildew * (sp > 0.93) * saturate(deep * 2.0)
    c = c + (np.array([0.035, 0.040, 0.028]) - c) * (0.7 * mil)[..., None]
    # and a grey-green film over a line left out for years
    c = c + (np.array([0.19, 0.20, 0.16]) - c) * (0.45 * mildew)
    return _rope_tail(c, u, v, deep, ndotv, fw, fuzz)


def _rope_tail(c, u, v, deep, ndotv, fw, fuzz, legacy_fade=None):
    """The part of ROPE_CODE every level shares: yarn streaks, the weave's shadow, rim fuzz, roughness, the lay."""
    # the existing look: yarn streaks, the weave's shadow
    sS = np.sin(2 * np.pi * (u * 36.0 + v * 48.0))
    sZ = np.sin(2 * np.pi * (u * 36.0 - v * 48.0))
    yarn = 0.5 + 0.5 * np.where(frac(u * 6.0 + v * 12.0) >= 0.5, sZ, sS)
    c = c * (0.9 + 0.16 * yarn * (1.0 - deep))[..., None]
    # fuzz fills the weave a little (loose fibres bridge the gaps), so an old line's shadows are shallower
    c = c + (np.array([0.023, 0.021, 0.018]) - c) * (deep * 0.62 * (1.0 - 0.45 * fuzz))[..., None]
    # polyester fuzz: loose fibres catch the light along the silhouette, much more on a used line
    rim = (1.0 - np.clip(ndotv, 0, 1)) ** 3
    rimK = (0.25 + 0.35 * legacy_fade) if legacy_fade is not None else (0.12 + 0.6 * fuzz)
    c = c + (c * 1.35 + 0.035 - c) * (rim * rimK)[..., None]
    rough = (0.62 if legacy_fade is not None else 0.5 + 0.3 * np.sqrt(fuzz)) + 0.25 * deep - 0.06 * yarn * (1.0 - deep)
    # lay pattern (pc/rig-lines)
    pS = 4.0 * v - u * 4.0 * 5.0 / math.pi
    pZ = 4.0 * v + u * 4.0 * 5.0 / math.pi
    layK = saturate(2.0 - 2.5 * fw)
    onS = frac(0.5 * (np.floor(pS) + np.floor(pZ))) >= 0.5
    ridge = np.where(onS, np.abs(np.cos(np.pi * pS)), np.abs(np.cos(np.pi * pZ)))
    c = c * (1.0 + (0.7 + 0.36 * ridge - 1.0) * layK)[..., None]
    rough = rough + 0.12 * (1.0 - ridge) * layK
    # fuzz veil: broken filaments stand off the cover and soften it, contrast and colour both (sqrt: soft after months)
    if legacy_fade is None:
        lv = (c * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
        k = 0.3 * np.sqrt(fuzz) * saturate(lv * 2.0)          # on the pale carriers: dyed ones keep their colour
        c = c + (0.5 * c + 0.5 * np.array([0.30, 0.295, 0.28]) - c) * k
    nstr = 1.0 - 0.4 * fuzz                             # fuzz softens the weave's relief
    return c, np.clip(rough, 0, 1), nstr


def render_rope(look, age, care, maps, diameter_mm=9.5, length_mm=120.0, px_per_mm=8.0, sun=(-0.35, 0.55, 0.76), legacy=False):
    """A straight line seen side on, lit by an overcast sky plus a soft sun: an image (sRGB uint8) of length x 1.6 d."""
    W, H = int(length_mm * px_per_mm), int(diameter_mm * 1.6 * px_per_mm)
    xs = (np.arange(W) + 0.5) / px_per_mm
    ys = (np.arange(H) + 0.5) / px_per_mm - H / px_per_mm / 2
    X, Y = np.meshgrid(xs, ys)
    r = diameter_mm / 2
    inside = np.abs(Y) < r
    s = np.clip(Y / r, -1, 1)
    theta = np.arcsin(s)                               # angle round the rope, 0 facing the camera
    nz, ny = np.cos(theta), s
    u = X / (5.0 * diameter_mm)
    v = theta / (2 * np.pi) + 0.25
    _, n_tex, _ = maps
    tn = sample(n_tex, u, v)
    fw = np.full_like(u, 4.0 / (math.pi * diameter_mm * px_per_mm) * 4.0)
    c, rough, nstr = rope_shade(u, v, look, maps, age, care, np.abs(nz), fw, legacy)
    # tangent frame: T along the rope (x), B round it, N out
    tx, ty = tn[..., 0] * nstr, tn[..., 1] * nstr
    Nx = tx
    Ny = ny + (-ty) * nz
    Nz = nz - (-ty) * ny
    L = np.linalg.norm(np.stack([Nx, Ny, Nz]), axis=0)
    Nx, Ny, Nz = Nx / L, Ny / L, Nz / L
    sx, sy, sz = sun
    sn = math.sqrt(sx * sx + sy * sy + sz * sz)
    ndl = np.clip((Nx * sx + Ny * sy + Nz * sz) / sn, 0, 1)
    sky = 0.55 + 0.45 * Ny * 0.5 + 0.25
    spec = (1 - rough) ** 2 * np.clip(Nz, 0, 1) ** (2 + 30 * (1 - rough)) * 0.25
    img = c * (0.6 * sky + 0.75 * ndl)[..., None] + spec[..., None]
    img = lin_to_srgb(img * 0.9)
    img = np.where(inside[..., None], img, np.array([0.5, 0.5, 0.5]))
    return (img * 255 + 0.5).astype(np.uint8), inside


def ladder(out_dir, looks=(0, 1, 4, 7)):
    """One row per level, one rope per colourway (0 white/red mainsheet, 1 red jib sheet, 4 white/blue halyard, 7 blue
    dock line), with the level written beside it."""
    maps = load_maps()
    rows = []
    for name, (age, care) in LEVELS.items():
        ims = [render_rope(lk, age, care, maps)[0] for lk in looks]
        pad = np.full((ims[0].shape[0], 16, 3), 128, np.uint8)
        row = np.concatenate(sum(([im, pad] for im in ims), [])[:-1], axis=1)
        Image.fromarray(row).save(os.path.join(out_dir, f"rope_{name}.png"))
        rows.append(row)
    gap = np.full((12, rows[0].shape[1], 3), 128, np.uint8)
    Image.fromarray(np.concatenate(sum(([r, gap] for r in rows), [])[:-1], axis=0)).save(os.path.join(out_dir, "rope_ladder.png"))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "Artifacts", "texloop", "rope")
    os.makedirs(out, exist_ok=True)
    for k, (a, c) in LEVELS.items():
        print(k, "fade %.2f grime %.2f fuzz %.2f mildew %.2f" % rope_wear(a, c))
    ladder(out)
    print("wrote", out)
