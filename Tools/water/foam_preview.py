"""Storm look (docs/storm-look/whitecaps/): an offline preview of M_WaterV4's near whitecaps (V4_SHADE's foam drawing with
useTable 0 and patFade 0) over a synthetic choppy sea seen from a camera 4 m up, so a change to how caps are drawn can be
judged without the editor. Not the renderer: no lighting, waves or spray; only where the white sits and its texture.

  python -I Tools/water/make_foam_texture.py <dir>        (bakes T_FoamLace.png into <dir>)
  python -I Tools/water/foam_preview.py <dir> [k=v,...]    (writes <dir>/foam_preview.png: classic, first cut, now)

k=v sets the shader's knobs for the last row (HOLES, VARY, CORE, RIM, RAG: make_materials.py's STORM_FOAM_HOLES,
STORM_CAP_VARY, STORM_CAP_CORE, STORM_CAP_RIM, STORM_CAP_RAG). The sea is seeded: the same arguments give the same image."""
import math
import sys
import numpy as np
from PIL import Image

HERE = sys.argv[1]
rng = np.random.default_rng(7)
tex = np.asarray(Image.open(f"{HERE}/T_FoamLace.png").convert("RGB"), dtype=np.float64) / 255.0


def mip(img, f):
    n = img.shape[0] // f
    return img[: n * f, : n * f].reshape(n, f, n, f, 3).mean(axis=(1, 3))


def sample(img, u, v):
    """Bilinear, wrapping; u, v in tiles."""
    n = img.shape[0]
    x = (u % 1.0) * n - 0.5
    y = (v % 1.0) * n - 0.5
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    tx = (x - x0)[..., None]
    ty = (y - y0)[..., None]
    a = img[y0 % n, x0 % n]
    b = img[y0 % n, (x0 + 1) % n]
    c = img[(y0 + 1) % n, x0 % n]
    d = img[(y0 + 1) % n, (x0 + 1) % n]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


# The sea: choppy components around a 20 m peak, spread +-40 deg about the wind (+x).
NC = 60
L = np.exp(rng.uniform(math.log(1.5), math.log(28.0), NC))
k = 2 * math.pi / L
th = rng.normal(0.0, math.radians(28.0), NC)
kx, ky = k * np.cos(th), k * np.sin(th)
om = np.sqrt(9.81 * k)
ph = rng.uniform(0, 2 * math.pi, NC)
# steepness per component (Phillips-like: equal steepness ka per log band, peak boosted)
ka = 0.055 * np.exp(-0.5 * ((np.log(L) - math.log(18.0)) / 0.7) ** 2) + 0.02
amp = ka / k
CH = 1.0


def jacobian(X, Y, t):
    Jxx = np.ones_like(X)
    Jyy = np.ones_like(X)
    Jxy = np.zeros_like(X)
    for i in range(NC):
        s = np.sin(kx[i] * X + ky[i] * Y - om[i] * t + ph[i])
        q = CH * amp[i] * s / k[i]
        Jxx -= q * kx[i] * kx[i]
        Jyy -= q * ky[i] * ky[i]
        Jxy -= q * kx[i] * ky[i]
    return Jxx * Jyy - Jxy * Jxy


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def sat(x):
    return np.clip(x, 0, 1)


def lerp(a, b, t):
    return a + (b - a) * t


def vnoise(u, v, seed):
    """Value noise like WB_NOISE (smoothstep-interpolated hash lattice)."""
    r = np.random.default_rng(seed).random((257, 257))
    x0 = np.floor(u).astype(int)
    y0 = np.floor(v).astype(int)
    fx = ss(0, 1, u - x0)
    fy = ss(0, 1, v - y0)
    h = lambda a, b: r[b % 257, a % 257]
    return lerp(lerp(h(x0, y0), h(x0 + 1, y0), fx), lerp(h(x0, y0 + 1), h(x0 + 1, y0 + 1), fx), fy)


W, H, RES = 70.0, 90.0, 0.04
PERSP = True
Ux = 15.4    # m/s, 30 kn
T_END = 14.0

# Threshold for about 3% folded (crest > 0.5) at the end frame.
xs = np.arange(0, W, 0.1)
ys = np.arange(0, H, 0.1)
X, Y = np.meshgrid(xs, ys)
J = jacobian(X, Y, T_END)
capThr = float(np.quantile(J, 0.03))
# The camera: 4 m up at (35, -3), looking along +y (across the wind, which blows along +x), pitched 9 deg down, 70 deg FOV.
IW, IH = 2400, 1000
fov = math.radians(70.0)
f = (IW / 2) / math.tan(fov / 2)
px, py = np.meshgrid(np.arange(IW) + 0.5 - IW / 2, np.arange(IH) + 0.5 - IH / 2)
pitch = math.radians(-9.0)
dx = px / f
dy = np.cos(pitch) * 1.0 - np.sin(pitch) * (-py / f)
dz = np.sin(pitch) * 1.0 + np.cos(pitch) * (-py / f)
hit = dz < -1e-4
tt = np.where(hit, 4.0 / np.maximum(-dz, 1e-4), 0.0)
X = 35.0 + dx * tt
Y = -3.0 + dy * tt
inside = hit & (Y > 0) & (Y < H - 1) & (X > 0) & (X < W)
X = np.where(inside, X, 0.0)
Y = np.where(inside, Y, 0.0)
foot = np.where(inside, tt / f / np.maximum(-dz, 0.05), 0.0)   # metres a pixel along the view, about
J = jacobian(X, Y, T_END)
capSlope = 0.072
print("capThr", capThr)

# The foam grid (AWaterSurface's): caps' cover laid down, fading exp(-t/4 s), drifting downwind at 3% of the wind.
CR = 0.2
cxs = np.arange(-10, W + 10, CR)
cys = np.arange(0, H, CR)
CX, CY = np.meshgrid(cxs, cys)
persist = np.zeros_like(CX)
dt = 0.1
drift = 0.035 * Ux
for step in range(int(T_END / dt) + 1):
    t = step * dt
    Jc = jacobian(CX, CY, t)
    capc = sat((capThr - Jc) / 0.05 + 0.5)
    persist *= math.exp(-dt / 4.0)
    shift = drift * dt / CR
    # advect downwind (+x) by a fractional shift
    i = int(shift)
    f = shift - i
    persist = np.roll(persist, i, axis=1) * (1 - f) + np.roll(persist, i + 1, axis=1) * f
    persist = np.maximum(persist, capc)
# up-sample to the fine grid
pu = (X + 10) / CR
pv = Y / CR
x0 = np.clip(np.floor(pu).astype(int), 0, persist.shape[1] - 2)
y0 = np.clip(np.floor(pv).astype(int), 0, persist.shape[0] - 2)
fx, fy = pu - x0, pv - y0
P = (persist[y0, x0] * (1 - fx) + persist[y0, x0 + 1] * fx) * (1 - fy) + (persist[y0 + 1, x0] * (1 - fx) + persist[y0 + 1, x0 + 1] * fx) * fy

# Patterns: fine 3.2 m, coarse 12.8 m, in the wind frame, mipped by the pixel's footprint.
def mipped(scale):
    out = np.zeros(X.shape + (3,))
    lev = np.clip(np.log2(np.maximum(foot, 1e-4) / (scale / 1024.0)), 0, 8)
    pyr = [tex] + [mip(tex, 2 ** i) for i in range(1, 9)]
    li = np.floor(lev).astype(int)
    for i in range(9):
        m = li == i
        if m.any():
            out[m] = sample(pyr[i], X[m] / scale, Y[m] / scale)
    return out
fine = mipped(3.2)
coarse = mipped(12.8)
lace, cells, streak = fine[..., 0], fine[..., 2], coarse[..., 1]
wd_x = X
wn_y = Y
T = T_END
capVar = sat(0.6 * vnoise((X - 0.2 * Ux * T) / 90.0 + 41.0, Y / 50.0 + 41.0, 1) + 0.4 * vnoise((X - 0.4 * Ux * T) / 12.0 + 17.0, Y / 12.0 + 17.0, 2))

Jt = J
crest0 = sat((capThr - Jt) / 0.05 + 0.5)
res0 = sat((capThr + 0.08 - Jt) / 0.08 + 0.5)
crest = crest0 * sat(0.8 + 1.3 * lace)
residue = res0 * ss(0.55, 0.95, streak) * 0.25
caps = np.maximum(crest, residue)
fresh = sat(crest / np.maximum(caps, 1e-3))
soft = sat((capThr - Jt) / 0.15 + 0.35)
trail = sat(P - caps)


def compose(capsDrawn, trailDrawn, tone, trail_tone):
    tone = lerp(tone, trail_tone, sat(trailDrawn / np.maximum(capsDrawn + trailDrawn, 1e-3)))
    a = np.maximum(capsDrawn, trailDrawn)
    water = 0.05
    c = water + (0.8 * tone - water) * a
    c = np.where(inside, c, 0.35)
    return c, a


def old():
    capOpen = lerp(0.4, 1.0, ss(0.15, 0.75, cells))
    tone = lerp(0.5, 1.0, fresh) * lerp(0.7, 1.0, sat(cells * 2))
    trailDrawn = trail ** 1.2 * 0.85 * lerp(0.45, 1.0, ss(0.3, 0.85, streak))
    base = np.where(soft * crest > 0, lerp(crest, soft, 0.5), 0.0)
    capsDrawn = sat(np.maximum(base, residue)) ** 1.5 * capOpen
    return compose(capsDrawn, trailDrawn, tone, 0.5)


def first_cut(HOLES=0.3, VARY=0.8):
    capVarS = (2 * capVar - 1) * VARY * capSlope
    laceF = sat(0.8 + 1.3 * lace)
    crestV = crest + (sat((capThr + capVarS - Jt) / 0.05 + 0.5) - sat((capThr - Jt) / 0.05 + 0.5)) * laceF
    softV = sat((capThr + capVarS - Jt) / 0.15 + 0.35)
    capAge = sat(1 - fresh + 0.6 * (1 - softV) ** 2)
    holeT = HOLES * capAge * lerp(1.4, 0.6, capVar)
    capLace = ss(holeT - 0.05, holeT + 0.05, lace + 0.02)
    capOpen = lerp(0.8, 1.0, ss(0.03, 0.4, cells)) * capLace
    tone = lerp(0.5, 1.0, fresh) * lerp(lerp(0.88, 1.0, sat(cells * 2)), lerp(0.7, 1.0, sat(cells * 2)), capAge)
    trailAge = sat((1 - trail) * lerp(1.3, 0.8, capVar))
    trString = ss(0.25, 0.85, trailAge)
    trHole = HOLES * lerp(0.5, 1.6, trailAge)
    trStrT = lerp(0.03, 0.3, trailAge)
    trPat = lerp(ss(trHole - 0.06, trHole + 0.06, lace) * lerp(0.75, 1.0, ss(0.03, 0.4, cells)), ss(trStrT, trStrT + 0.12, streak), trString)
    trailDrawn = trail ** 1.2 * 0.85 * trPat
    base = np.where(softV * crestV > 0, lerp(crestV, softV, 0.5), 0.0)
    capsDrawn = sat(np.maximum(base, residue)) ** 1.5 * capOpen
    return compose(capsDrawn, trailDrawn, tone, lerp(0.75, 0.5, trailAge))


def now(HOLES=0.3, VARY=0.8, CORE=0.3, RIM=1.2, RAG=0.06):
    """As V4_SHADE draws them now: the cap's age grows from its deepest fold out to its rim (only the deepest part is the
    active crest), holes open even in the core (a floor of CORE of the threshold) and the drawn rim is ragged."""
    capVarS = (2 * capVar - 1) * VARY * capSlope
    rag = RAG * (lace - 0.25)   # ragged edge: lace moves the drawn edge (mean 0)
    laceF = sat(0.8 + 1.3 * lace)
    crestV = crest + (sat((capThr + capVarS + rag - Jt) / 0.05 + 0.5) - sat((capThr - Jt) / 0.05 + 0.5)) * laceF
    softV = sat((capThr + capVarS + rag - Jt) / 0.15 + 0.35)
    depth = sat((capThr + capVarS - Jt) / (2.0 * capSlope))   # 0 at the threshold, 1 two e-folds of cover in
    capAge = sat(1 - fresh + RIM * (1 - depth) * (1 - depth))
    holeT = HOLES * lerp(CORE, 1.0, capAge) * lerp(1.4, 0.6, capVar)
    capLace = ss(holeT - 0.05, holeT + 0.05, lace + 0.02)
    capOpen = lerp(0.7, 1.0, ss(0.03, 0.4, cells)) * capLace
    tone = lerp(0.5, 1.0, fresh) * lerp(lerp(0.85, 1.0, sat(cells * 2)), lerp(0.7, 1.0, sat(cells * 2)), capAge)
    trailAge = sat((1 - trail) * lerp(1.3, 0.8, capVar))
    trString = ss(0.25, 0.85, trailAge)
    trHole = HOLES * lerp(0.5, 1.6, trailAge)
    trStrT = lerp(0.03, 0.3, trailAge)
    trPat = lerp(ss(trHole - 0.06, trHole + 0.06, lace) * lerp(0.75, 1.0, ss(0.03, 0.4, cells)), ss(trStrT, trStrT + 0.12, streak), trString)
    trailDrawn = trail ** 1.2 * 0.85 * trPat
    base = np.where(softV * crestV > 0, lerp(crestV, softV, 0.5), 0.0)
    capsDrawn = sat(np.maximum(base, residue)) ** 1.5 * capOpen
    return compose(capsDrawn, trailDrawn, tone, lerp(0.75, 0.5, trailAge))


kv = dict(p.split("=") for p in sys.argv[2].split(",")) if len(sys.argv) > 2 and sys.argv[2] else {}
panels = {"classic (-SailingClassicFoam)": old(), "first cut": first_cut(), "now": now(**{a: float(b) for a, b in kv.items()})}
rows = []
for n, (c, a) in panels.items():
    print(f"{n:30s} mean opacity {a.mean():.4f}  share of pixels over half opaque {(a > 0.5).mean():.4f}")
    img = Image.fromarray((np.clip(c, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)).resize((IW // 2, IH // 2), Image.LANCZOS)
    rows.append(img.crop((0, IH // 4 - 60, IW // 2, IH // 2 - 60)))
out = Image.new("L", (IW // 2, sum(r.height + 6 for r in rows)), 255)
y = 0
for r in rows:
    out.paste(r, (0, y))
    y += r.height + 6
out.save(f"{HERE}/foam_preview.png")
print(f"Wrote {HERE}/foam_preview.png (rows: {', '.join(panels)})")
