"""Render a surface's swatch at the five wear levels, the same view every round (docs/texture-loop).

    python Tools/texloop/render_swatch.py gelcoat [--before] [--out DIR] [--size 900]

No Blender: a small image-based-lighting renderer in numpy, the same split-sum shading the engine uses (diffuse from
the sky's irradiance, a prefiltered sky reflection per roughness, a 0.05 clear-coat lobe), under one neutral CC0 sky
(Poly Haven's abandoned_slipway: overcast, with water and a slipway for the gloss to reflect; 1k HDR, fetched to the
git-ignored Data/Reference/raw/textures/_env/). The swatch
is a 1.2 m piece of white topsides and side deck seen from 1.5 m: deck on top (faces the sky), a rounded sheer, then
the topsides curving away. An 18% grey card at the right is the neutral box measure.py balances on.

The surface colours come from Tools/texloop/wear.py and a numpy port of M_BoatSurface's gelcoat lines (the grime
noise, the tone patches, black streaks, dock rash): `--before` renders the material as it was (one ageK), the default
the time/dirt split. Writes <out>/<surface>_<L>.png plus swatch.json (where each box is, for measure.py and score.py).
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image

import wear

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ENV_DIR = os.path.join(REPO, "Data", "Reference", "raw", "textures", "_env")
SKY = "abandoned_slipway"   # Poly Haven, CC0: overcast, water and a slipway to reflect (kloofendal_overcast: open field)
DETAIL = os.path.join(REPO, "Inputs", "boat-detail")

# ------------------------------------------------------------------ the sky

def read_hdr(path):
    """Radiance RGBE (new-style run-length rows), as Poly Haven ships them -> float32 (h, w, 3)."""
    data = open(path, "rb").read()
    head_end = data.index(b"\n\n") + 2
    line_end = data.index(b"\n", head_end)
    dims = data[head_end:line_end].split()
    h, w = int(dims[1]), int(dims[3])
    pos = line_end + 1
    out = np.zeros((h, w, 4), np.uint8)
    buf = np.frombuffer(data, np.uint8)
    for y in range(h):
        pos += 4  # 2, 2, width hi, width lo
        for c in range(4):
            x = 0
            while x < w:
                n = int(buf[pos]); pos += 1
                if n > 128:
                    n -= 128
                    out[y, x:x + n, c] = buf[pos]; pos += 1
                else:
                    out[y, x:x + n, c] = buf[pos:pos + n]; pos += n
                x += n
    e = out[..., 3].astype(np.int32)
    scale = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0)
    return (out[..., :3] * scale[..., None]).astype(np.float32)


def load_env(name=SKY):
    path = os.path.join(ENV_DIR, name + "_1k.hdr")
    if not os.path.exists(path):
        import urllib.request
        os.makedirs(ENV_DIR, exist_ok=True)
        urllib.request.urlretrieve("https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/%s_1k.hdr" % name, path)
    return read_hdr(path)


def dirs_of(h, w):
    """World direction of each equirect pixel (Z up)."""
    phi = (np.arange(w) + 0.5) / w * 2 * np.pi - np.pi
    th = (np.arange(h) + 0.5) / h * np.pi
    p, t = np.meshgrid(phi, th)
    return np.stack([np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)], -1), np.sin(t)


class Sky:
    """Prefiltered copies of the sky: a GGX-ish lobe per roughness (power-cosine), and the cosine irradiance."""

    def __init__(self, env):
        self.levels = {}
        self.src = []
        for w in (256, 128, 64, 32):   # box-filtered copies (Pillow can't resize float RGB)
            fy, fx = env.shape[0] // (w // 2), env.shape[1] // w
            small = env[:fy * (w // 2), :fx * w].reshape(w // 2, fy, w, fx, 3).mean((1, 3))
            d, sw = dirs_of(w // 2, w)
            self.src.append((small, d, sw))
        self.cache = {}

    def _filtered(self, power):
        key = round(power, 1)
        if key in self.cache:
            return self.cache[key]
        if power > 5000:          # near-mirror: the sky itself at 256 x 128 (about 1.4 degrees a texel)
            self.cache[key] = self.src[0][0]
            return self.src[0][0]
        # a coarser source and target for a wider lobe
        small, d, sw = self.src[1 if power > 200 else 2 if power > 20 else 3]
        h, w = small.shape[:2]
        tw, th = (128, 64) if power > 200 else (64, 32)
        dt, _ = dirs_of(th, tw)
        flat_d = d.reshape(-1, 3)
        rad = (small * sw[..., None]).reshape(-1, 3)
        wsum = sw.reshape(-1)
        out = np.zeros((th * tw, 3))
        for i, dd in enumerate(dt.reshape(-1, 3)):
            c = np.clip(flat_d @ dd, 0, 1) ** power
            out[i] = (c[:, None] * rad).sum(0) / max((c * wsum).sum(), 1e-9)
        res = out.reshape(th, tw, 3)
        self.cache[key] = res
        return res

    @staticmethod
    def _lookup(img, v):
        h, w = img.shape[:2]
        th = np.arccos(np.clip(v[..., 2], -1, 1))
        ph = np.arctan2(v[..., 1], v[..., 0])
        y = np.clip(th / np.pi * h - 0.5, 0, h - 1)
        x = (ph + np.pi) / (2 * np.pi) * w - 0.5
        y0 = np.floor(y).astype(int); x0 = np.floor(x).astype(int)
        fy = (y - y0)[..., None]; fx = (x - x0)[..., None]
        y1 = np.minimum(y0 + 1, h - 1); x0w = x0 % w; x1w = (x0 + 1) % w
        a = img[y0, x0w] * (1 - fx) + img[y0, x1w] * fx
        b = img[y1, x0w] * (1 - fx) + img[y1, x1w] * fx
        return a * (1 - fy) + b * fy

    def irradiance(self, n):
        return self._lookup(self._filtered(1.0), n)  # cosine lobe: radiance-weighted mean = E / pi

    def specular(self, r, rough):
        """Prefiltered radiance along r for a per-pixel roughness: blend between a few fixed lobes."""
        rs = (0.05, 0.12, 0.25, 0.45, 0.7, 1.0)
        out = np.zeros(r.shape)
        rr = np.clip(rough, rs[0], rs[-1])
        for i in range(len(rs) - 1):
            lo, hi = rs[i], rs[i + 1]
            m = (rr >= lo) & (rr <= hi)
            if not m.any():
                continue
            t = ((rr - lo) / (hi - lo))[..., None]
            plo = 2.0 / max(lo ** 4, 1e-6) - 2.0
            phi = 2.0 / max(hi ** 4, 1e-6) - 2.0
            a = self._lookup(self._filtered(min(plo, 20000.0)), r)
            b = self._lookup(self._filtered(min(phi, 20000.0)), r)
            out = np.where(m[..., None], a * (1 - t) + b * t, out)
        return out


def env_brdf(rough, nv):
    """Karis' analytic fit of the split-sum's second term (UE's EnvBRDFApprox)."""
    c0 = np.array([-1.0, -0.0275, -0.572, 0.022])
    c1 = np.array([1.0, 0.0425, 1.04, -0.04])
    r = rough[..., None] * c0 + c1
    a004 = np.minimum(r[..., 0] * r[..., 0], np.exp2(-9.28 * nv)) * r[..., 0] + r[..., 1]
    A = a004 * -1.04 + r[..., 2]
    B = a004 * 1.04 + r[..., 3]
    return A, B

# ------------------------------------------------------------------ the swatch

W_M, H_M = 1.2, 0.9          # metres of surface across and down the picture
DECK_FRAC = 0.28             # top of the picture: side deck
SHEER_FRAC = 0.06            # the rounded sheer
CAM = 1.5                    # metres to the topsides


def geometry(px):
    """Per pixel: local position (cm: x along, z up from the waterline), normal (world, camera looks along +Y), up."""
    w, h = px, int(px * H_M / W_M)
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    U, Vv = np.meshgrid(u, v)
    x = (U - 0.5) * W_M
    # topsides: curve away to the sides (radius 3 m) and lean out 8 deg; deck: level with 1 deg camber
    n = np.zeros((h, w, 3))
    deck = Vv < DECK_FRAC
    sheer = (Vv >= DECK_FRAC) & (Vv < DECK_FRAC + SHEER_FRAC)
    side = Vv >= DECK_FRAC + SHEER_FRAC
    yaw = np.arcsin(np.clip(x / 3.0, -1, 1))
    lean = math.radians(8)
    side_n = np.stack([np.sin(yaw) * np.cos(lean), -np.cos(yaw) * np.cos(lean), np.full_like(x, math.sin(lean))], -1)
    deck_n = np.stack([np.zeros_like(x), (Vv - DECK_FRAC / 2) * 0.05, np.ones_like(x)], -1)
    t = np.clip((Vv - DECK_FRAC) / SHEER_FRAC, 0, 1)[..., None]
    sheer_n = deck_n * np.cos(t * np.pi / 2) + side_n * np.sin(t * np.pi / 2)
    n = np.where(deck[..., None], deck_n, np.where(sheer[..., None], sheer_n, side_n))
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    # local z (cm above the waterline): the sheer at 75 cm; the deck runs inboard (we see it from above)
    zcm = np.where(Vv < DECK_FRAC, 75.0, 75.0 - (Vv - DECK_FRAC) / (1 - DECK_FRAC) * 70.0)
    ycm = np.where(Vv < DECK_FRAC, (DECK_FRAC - Vv) / DECK_FRAC * 30.0, 0.0)
    lp = np.stack([x * 100.0, ycm, zcm], -1)
    # camera: 1.5 m off the topsides, 25 cm above the sheer, looking a little down
    cam = np.array([0.0, -CAM, 0.25])
    pos = np.stack([x, np.where(deck, (DECK_FRAC - Vv) / DECK_FRAC * 0.3, 0.0), (zcm - 75.0) / 100.0], -1)
    view = cam - pos
    view /= np.linalg.norm(view, axis=-1, keepdims=True)
    up = np.clip((n[..., 2] - 0.4) * 2.5, 0, 1)
    return dict(lp=lp, n=n, v=view, up=up, deck=deck, w=w, h=h)


def hash2(a, b, k1=12.99, k2=78.23):
    return np.modf(np.abs(np.sin(a * k1 + b * k2) * 43758.5))[0]


def value_noise(lp, turned=True):
    """M_BoatSurface's grime noise: three octaves of value noise anchored to the boat (37, 9, 2.2 cm). #405: each octave's
    lattice is turned (37, 74, 111 deg) and smoothed quintically; turned=False is main before #405 (--before)."""
    vn = np.zeros(lp.shape[:2]); amp = 0.6; sc = 37.0
    for o in range(3):
        px, py = lp[..., 0] + lp[..., 2] * 0.6, lp[..., 1] - lp[..., 2] * 0.4
        ang = 0.6458 * (o + 1) if turned else 0.0
        qx = (px * np.cos(ang) - py * np.sin(ang)) / sc + o * 17.3
        qy = (px * np.sin(ang) + py * np.cos(ang)) / sc + o * 17.3
        ix, iy = np.floor(qx), np.floor(qy)
        fx, fy = qx - ix, qy - iy
        if turned:
            fx = fx * fx * fx * (fx * (fx * 6 - 15) + 10); fy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        else:
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
        a00, a10, a01, a11 = hash2(ix, iy), hash2(ix + 1, iy), hash2(ix, iy + 1), hash2(ix + 1, iy + 1)
        vn += amp * ((a00 * (1 - fx) + a10 * fx) * (1 - fy) + (a01 * (1 - fx) + a11 * fx) * fy)
        amp *= 0.5; sc /= 4.1
    return vn / 1.05


def gelcoat_maps(g, age, care, split=True, base=(0.80, 0.80, 0.77), rough0=0.22, sun=1.0):
    """Albedo (linear), roughness and coat per pixel: wear.gelcoat plus the M_BoatSurface lines that sit on gelcoat."""
    lp, n, up = g["lp"], g["n"], g["up"]
    h, w = up.shape
    zcm = lp[..., 2]
    # the 40 cm chalk blotches (round 2): M_BoatSurface's bq noise
    bx, by = lp[..., 0] / 40.0 + lp[..., 1] / 55.0, lp[..., 2] / 40.0 + lp[..., 1] / 55.0
    ix, iy = np.floor(bx), np.floor(by)
    fx, fy = bx - ix, by - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    blot = (hash2(ix, iy) * (1 - fx) + hash2(ix + 1, iy) * fx) * (1 - fy) + (hash2(ix, iy + 1) * (1 - fx) + hash2(ix + 1, iy + 1) * fx) * fy
    col, rough, coat = wear.gelcoat(base, rough0, 1.0, age, care, up=up, sun=sun, split=split, blot=blot)
    rough = np.broadcast_to(rough, up.shape).copy(); coat = np.broadcast_to(coat, up.shape).copy()
    vn = value_noise(lp, turned=split)
    # grime on the deck (deckish: up-facing, not the hull); #405: the softer edge x1.4 - 0.4 (before: x1.8 - 0.6)
    dirt = wear.grime(age, care, split=split)
    grime = (np.clip(vn * 1.4 - 0.4, 0, 1) if split else np.clip(vn * 1.8 - 0.6, 0, 1)) * up * dirt * 0.45
    col = col + (col * 0.76 + np.array([0.014, 0.011, 0.007]) - col) * grime[..., None]
    rough = rough + (np.minimum(rough + 0.18, 0.9) - rough) * grime
    coat *= 1 - 0.6 * grime
    col *= (1 + 0.05 * (vn - 0.5))[..., None]
    side = np.abs(n[..., 2]) < 0.75
    # dock rash (after: timeK; before: the livery's wear.z, 0 on a seeded boat)
    t = wear.time_k(age, care) if split else 0.0
    if t > 0:
        csx, csz = lp[..., 0] / 45.0, zcm / 16.0
        cx, cz = np.floor(csx), np.floor(csz)
        patch = hash2(cx, cz, 41.3, 17.7)
        fx, fz = csx - cx - 0.5, (csz - cz - 0.5) * 1.8
        smudge = 1 - np.clip((np.hypot(fx, fz) - 0.12) / 0.33, 0, 1)
        band = np.clip((zcm - 25) / 15, 0, 1) * (1 - np.clip((zcm - 70) / 25, 0, 1))
        scuff = 0.7 * min(4.0 * t, 1.0) * side * band * (patch > 0.82) * smudge
        col = col + (col * 0.78 + 0.01 - col) * scuff[..., None]
    # black streaks under the sheer (after: dirtK; before: 0.25 + 0.9 wear.y, wear.y = 0 on a seeded boat)
    k = 1.15 * wear.dirt_k(age, care) if split else 0.25
    sx = lp[..., 0] / 6.0
    sh = hash2(np.floor(sx), 0, 57.31, 0); sh2 = hash2(np.floor(sx) * 13.7 / 57.31 + 3.0 / 57.31, 0, 57.31, 0)
    sw = np.exp(-((sx - np.floor(sx) - 0.5) * ((2.5 + 5 * sh2) if split else (5 + 10 * sh2))) ** 2)
    slen = 25 + 70 * sh; stop = 55 + 70 * sh2
    blk = side * (sh > ((0.85 - 0.5 * wear.dirt_k(age, care)) if split else 0.45)) * sw * np.clip((zcm - (stop - slen)) / slen, 0, 1) * np.clip((stop + 15 - zcm) / 20, 0, 1)
    col = col + (col * np.array([0.62, 0.61, 0.58]) - col) * np.clip(blk * k, 0, 1)[..., None]
    # large faint tone differences (+-3%)
    tone = hash2(np.floor(lp[..., 0] / 160), np.floor(lp[..., 2] / 160))
    col *= (1 + 0.06 * (tone - 0.5))[..., None]
    # orange peel and buffing scratches: the gelcoat detail mask's roughness (tile 25 cm)
    m = np.asarray(Image.open(os.path.join(DETAIL, "T_Detail_Gelcoat_M.png")).convert("RGB"), np.float64) / 255.0
    mh, mw = m.shape[:2]
    ui = ((lp[..., 0] / 25.0) % 1 * mw).astype(int) % mw
    vi = (((lp[..., 2] + lp[..., 1]) / 25.0) % 1 * mh).astype(int) % mh
    mm = m[vi, ui]
    ak = wear.age_k(age, care) if not split else wear.chalk_k(age, care)
    rough = np.clip(rough + (mm[..., 1] - 0.5) * 0.15 + mm[..., 0] * 0.15 * (0.3 + ak), 0, 1)
    return np.clip(col, 0, 1), np.clip(rough, 0.02, 1), np.clip(coat, 0, 1)


def shade(g, sky, col, rough, coat, exposure):
    n, v = g["n"], g["v"]
    nv = np.clip((n * v).sum(-1), 1e-3, 1)
    r = 2 * nv[..., None] * n - v
    diffuse = col * sky.irradiance(n)
    A, B = env_brdf(rough, nv)
    spec = sky.specular(r, rough) * (0.04 * A + B)[..., None]
    Ac, Bc = env_brdf(np.full_like(rough, 0.05), nv)
    fc = (0.04 * Ac + Bc)[..., None]
    spec_c = sky.specular(r, np.full_like(rough, 0.05)) * fc
    k = coat[..., None]
    lit = (diffuse + spec) * (1 - k * fc) + k * spec_c
    return lit * exposure


def aces(x):
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)


def to_srgb(x):
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(np.clip(x, 0, 1), 1 / 2.4) - 0.055)


def render(surface, age, care, split, sky, px=900):
    g = geometry(px)
    col, rough, coat = gelcoat_maps(g, age, care, split=split)
    # grey card: an 18% patch facing the camera, bottom right
    h, w = g["h"], g["w"]
    card = np.zeros((h, w), bool)
    card[int(h * 0.80):int(h * 0.96), int(w * 0.84):int(w * 0.97)] = True
    ncard = np.array([0.0, -1.0, 0.25]); ncard /= np.linalg.norm(ncard)
    g["n"] = np.where(card[..., None], ncard, g["n"])
    col = np.where(card[..., None], 0.18, col)
    rough = np.where(card, 0.9, rough)
    coat = np.where(card, 0.0, coat)
    # exposure: the grey card's irradiance puts it at middle grey (0.18 linear before the tone curve)
    e_card = float((sky.irradiance(ncard[None, None, :])[0, 0] * 0.18).mean())
    lit = shade(g, sky, col, rough, coat, 0.18 / max(e_card, 1e-6) * 0.8)
    img = to_srgb(aces(lit))
    boxes = dict(
        topsides=[0.08, DECK_FRAC + SHEER_FRAC + 0.10, 0.80, 0.78],
        deck=[0.08, 0.04, 0.92, DECK_FRAC - 0.03],
        neutral=[0.85, 0.82, 0.96, 0.94],
    )
    return img, boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("surface", choices=["gelcoat"])
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--out", default=os.path.join(REPO, "Artifacts", "texloop"))
    ap.add_argument("--size", type=int, default=900)
    ap.add_argument("--sky", default=SKY, help="a Poly Haven HDRI name (CC0), fetched at 1k")
    a = ap.parse_args()
    sky = Sky(load_env(a.sky))
    tag = "before" if a.before else "after"
    out = os.path.join(a.out, a.surface, tag)
    os.makedirs(out, exist_ok=True)
    meta = {}
    for lv in wear.levels():
        img, boxes = render(a.surface, lv["age"], lv["care"], not a.before, sky, a.size)
        path = os.path.join(out, "%s_%s.png" % (a.surface, lv["id"]))
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(path)
        meta[lv["id"]] = dict(path=path, boxes=boxes, age=lv["age"], care=lv["care"])
        print(path)
    json.dump(meta, open(os.path.join(out, "swatch.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
