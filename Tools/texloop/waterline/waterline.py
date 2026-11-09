"""The lake waterline (Lake Ray Hubbard, fresh water): one set of numbers for the fleet shader, the hero J/22 bake
and the swatch renders, so all three age the same way.

Inputs are the texture loop's two wear numbers (Tools/texloop, docs/texture-loop):
  dirt 0..1  what care removes: the scum line, the slime, the film on the bottom paint
  time 0..1  what care can't undo: the bottom paint's fade
The waterline reads dirt only, except the bottom paint, which also fades with time.

What it draws (heights in cm above the design waterline, z):
  line   a thin ragged film where the water sits, grey on a kept boat, tan-brown clay on a neglected one; measured on
         TX 7295 EC at Rush Creek (Tools/texloop/refs/waterline.json): about 1.75 cm high, 89% as bright as the
         gelcoat beside it, almost no colour.
  slime  olive algae film at and below the line, only on a dirty boat (dirt above about 0.4).
  film   a grey-olive film over the bottom paint, blotchy.
No barnacles or mussel crust: the lake is fresh water and only 'suspect' for zebra mussels.

`params(dirt, time)` is the table all three read; `shade(...)` is the numpy reference that the HLSL block in
scripts/make_materials.py (BOAT_CODE, "Texture loop, waterline") and Inputs/j22-hero/j22_waterline.py follow step for
step. Their noises differ (value noise here and in BOAT_CODE, Blender's noise in the bake), so every noise enters about
its middle and the mean cover agrees; colours here are sRGB and are mixed in linear, as the engine and Blender do.
"""
import numpy as np

# sRGB colours (0-1). The film colours are what the stain itself looks like, mixed over the gelcoat by `line_k`.
LINE_GREY = (0.46, 0.45, 0.42)      # kept boat: a neutral, faintly warm grey film (TX 7295 EC: dLab a 0.1, b 0.2)
LINE_CLAY = (0.45, 0.38, 0.22)      # neglected: muddy tan-brown Texas clay and tannin (round 3's 0.50, 0.33, 0.12 read orange-pink)
SLIME = (0.30, 0.33, 0.17)          # olive algae
BOTTOM_FILM = (0.45, 0.47, 0.40)    # grey-olive film on grey bottom paint


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def params(dirt, time=0.0):
    d = float(np.clip(dirt, 0.0, 1.0))
    t = float(np.clip(time, 0.0, 1.0))
    return {
        "line_k": 0.4 * d ** 0.3 + 0.3 * float(smoothstep(0.6, 1.0, d)),   # how much of the stain covers the gelcoat
        "line_clay": float(smoothstep(0.45, 0.9, d)),                 # grey film -> tan-brown clay
        "line_h": 1.0 + 1.6 * d + 5.0 * float(smoothstep(0.55, 1.0, d)),  # cm
        "rag": 0.25 + 0.08 * (1.0 + 1.6 * d + 5.0 * float(smoothstep(0.55, 1.0, d))),  # cm the top edge wanders
        "slime_k": 0.85 * float(smoothstep(0.4, 0.95, d)),
        "slime_depth": 4.0 + 16.0 * float(smoothstep(0.4, 1.0, d)),  # cm below the waterline
        "film_k": 0.45 * d,
        "paint_fade": 0.25 * t,                                       # bottom paint pales with age
    }


def _vnoise(x, y, seed=0.0):
    """Value noise like BOAT_CODE's (hash of the cell corners, smoothstep blend)."""
    xi, yi = np.floor(x), np.floor(y)
    xf, yf = x - xi, y - yi
    xf, yf = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)

    def h(a, b):
        return np.modf(np.sin(a * 12.99 + b * 78.23 + seed) * 43758.5)[0] % 1.0

    return (h(xi, yi) * (1 - xf) + h(xi + 1, yi) * xf) * (1 - yf) + (h(xi, yi + 1) * (1 - xf) + h(xi + 1, yi + 1) * xf) * yf


def _fbm(x, y, seed=0.0, octaves=3):
    """Three octaves of the value noise, 0..1 (BOAT_CODE's vn loop)."""
    v, amp, tot = 0.0, 0.6, 0.0
    for o in range(octaves):
        v = v + amp * _vnoise(x * 2.0 ** o * 1.3 ** o, y * 2.0 ** o * 1.3 ** o, seed + 17.3 * o)
        tot += amp
        amp *= 0.5
    return v / tot


def masks(x_cm, z_cm, p, seed=0.0):
    """Line, slime and film coverage at points along the hull (x cm, forward) and up it (z cm above the waterline)."""
    h = p["line_h"]
    # the line's top edge wanders with the wash: slow swell plus a fine ragged edge
    wob = 0.6 * _vnoise(x_cm / 23.0, 0.0, seed) + 0.4 * _fbm(x_cm / 1.5, 3.1, seed)
    top = h + p["rag"] * (2.0 * wob - 1.0)
    line = smoothstep(-0.6, -0.1, z_cm) * (1.0 - smoothstep(top - 0.2 - 0.06 * h, top, z_cm))
    # density: a tide mark along the top edge, heavier through the band on a dirty boat; streaky up and down (water running
    # off as the boat rocks) and mottled. The noise enters about its middle (0.5), so the mean cover doesn't depend on how
    # a noise is distributed: numpy here, value noise in BOAT_CODE and Blender's noise in the hero bake agree on average.
    u = np.clip(z_cm / np.maximum(top, 0.1), 0.0, 1.0)
    dens = 0.75 + 0.45 * p["line_clay"] + 0.35 * smoothstep(0.6, 0.95, u)
    streak = _fbm(x_cm / 3.5 + 0.3 * z_cm, z_cm / 14.0, seed + 5.0)
    mott = _fbm(x_cm / 5.0, z_cm / 2.5, seed + 7.0)
    line = line * np.clip(dens * (1.0 + (1.0 - 0.85 * p["line_clay"]) * (0.6 * (streak - 0.5) + 0.4 * (mott - 0.5))), 0.0, 1.3)
    # smeared along the hull by the wash (14 cm x 3 cm blotches), thickest at the line and thinning with depth
    blot = _fbm(x_cm / 14.0, z_cm / 3.0, seed + 9.0)
    depth = np.clip(-z_cm / p["slime_depth"], 0.0, 1.0)
    slime = (1.0 - smoothstep(-0.5, 0.2, z_cm)) * (1.0 - depth) ** 1.5
    slime = slime * smoothstep(0.3 + 0.25 * depth, 0.65, blot) * (0.75 + 0.25 * _fbm(x_cm / 2.5, z_cm / 0.8, seed + 15.0))
    film = (1.0 - smoothstep(-1.0, 0.0, z_cm)) * (0.6 + 0.4 * _fbm(x_cm / 30.0, z_cm / 12.0, seed + 13.0))
    return line, slime, film


def _lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def shade(gel, bottom, x_cm, z_cm, dirt, time=0.0, seed=0.0):
    """Albedo (sRGB 0-1, HxWx3) of a hull patch: gelcoat above the waterline, bottom paint below. The mixing is done in
    linear colour, as the engine and Blender do; the colour constants above are sRGB."""
    p = params(dirt, time)
    line, slime, film = masks(x_cm, z_cm, p, seed)
    above = smoothstep(-0.6, 0.0, z_cm)[..., None]
    paint = _lin(bottom) * (1 - p["paint_fade"]) + p["paint_fade"] * _lin([0.78, 0.78, 0.76])
    col = _lin(gel) * above + paint * (1 - above)
    col = col * (1 - (p["film_k"] * film)[..., None]) + _lin(BOTTOM_FILM) * (p["film_k"] * film)[..., None]
    stain = _lin(LINE_GREY) * (1 - p["line_clay"]) + _lin(LINE_CLAY) * p["line_clay"]
    k = (p["line_k"] * line)[..., None]
    col = col * (1 - k) + stain * k
    s = (p["slime_k"] * slime)[..., None]
    col = col * (1 - s) + _lin(SLIME) * s
    return _srgb(col)


def roughness(base, x_cm, z_cm, dirt, time=0.0, seed=0.0):
    """Stain and slime are matte (0.8); slime is wet-looking only when the hull is wet, which the water shader owns."""
    p = params(dirt, time)
    line, slime, film = masks(x_cm, z_cm, p, seed)
    cover = np.clip(p["line_k"] * line + p["slime_k"] * slime + 0.5 * p["film_k"] * film, 0.0, 1.0)
    return base + (0.8 - base) * cover
