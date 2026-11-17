"""The Catalina 22's own close-up detail maps (docs/c22-9): the grained vinyl of her headliner and rubrail, and the
woven tweed of her cushions. Made with numpy (no photos), tileable, sized from the card's real pattern
(textures_c22.json 'maps.own'), written as plain PNGs to Inputs/c22-detail (the folder's .gitattributes keeps them out
of Git LFS, which the cloud cannot push): a normal map (OpenGL) and a mask map each.

    python3 -I Tools/shipkit/catalina22/textures/textures_c22.py [<out dir>] [--check]

  Vinyl  60 x 60 mm, 512 px    mask R cavity (the grain's valleys), G roughness, B height
  Tweed  60 x 60 mm, 1024 px   mask R plaid tone, G weave gaps, B height

The shared library's maps (Inputs/boat-detail: Gelcoat, NonSkid, TeakWeathered, WoodVarnish, Metal, Canvas) are already
resident for the J/22 and cost her nothing. Bluebonnet's generator (Tools/shipkit/jclass/textures.py) supplies the
noise, normal-map and measuring helpers, so both boats' maps are made and checked the same way.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ARGS = sys.argv[1:]
sys.path.insert(0, os.path.join(REPO, "Tools", "shipkit", "jclass"))
_argv, sys.argv = sys.argv, sys.argv[:1]          # Bluebonnet's generator reads its own arguments at import
import textures as JT  # noqa: E402
sys.argv = _argv

OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(REPO, "Inputs", "c22-detail")
CARDS = json.load(open(os.path.join(HERE, "textures_c22.json")))
OWN = CARDS["maps"]["own"]


def vinyl(card):
    """A pebbled leather grain: rounded cells 0.6 to 1.6 mm across, separated by narrow valleys, with a faint
    long-wavelength wander so the grain is not a lattice."""
    tile = card["tile_mm"]
    shape = (card["px"][1], card["px"][0])
    a = JT.spectral_noise(shape, 0.8, 2.2, tile, 31)
    b = JT.spectral_noise(shape, 0.8, 2.2, tile, 32)
    cell = np.abs(a) + 0.6 * np.abs(b)                # ridged: valleys where either noise crosses zero
    pebble = 1.0 - np.exp(-1.6 * cell)                # flat-topped pebbles, sharp valleys
    wander = JT.spectral_noise(shape, 4.0, 12.0, tile, 33)
    hmm = 0.05 * pebble + 0.004 * wander
    cav = 1.0 - JT.unit(pebble)
    rough = JT.unit(0.6 * cav + 0.4 * JT.unit(JT.spectral_noise(shape, 0.2, 0.6, tile, 34)))
    sizes = {"grain": (JT.feature_mm(pebble, tile), card["pattern_mm"]["grain"])}
    return hmm, np.stack([cav, rough, JT.unit(hmm)], -1), tile, sizes


def tweed(card):
    """A 2/2 twill of thick woollen yarns about 1.2 mm apart, in a 6 cm plaid of three tones (the period's olive and
    brown): the tone is the plaid, the gaps the shadows between the yarns, the height the yarns' rounded crowns, with
    each yarn's own slubs and a fibrous fuzz."""
    tile = card["tile_mm"]
    shape = (card["px"][1], card["px"][0])
    x, y = JT.grid(shape)
    n = int(round(tile[0] / 1.2))                     # yarns across the tile (a whole number, so it tiles)
    wx, wy = x * n, y * n
    ix, iy = np.floor(wx).astype(int), np.floor(wy).astype(int)
    fx, fy = wx - ix, wy - iy
    rng = np.random.default_rng(41)
    pw, pf = rng.random(n) * 2 * math.pi, rng.random(n) * 2 * math.pi
    sl_w = 1.0 + 0.12 * np.cos(2 * math.pi * 3 * y + pw[ix % n])
    sl_f = 1.0 + 0.12 * np.cos(2 * math.pi * 4 * x + pf[iy % n])
    warp = np.clip(1.0 - ((fx - 0.5) / (0.48 * sl_w)) ** 2, 0, 1) ** 0.5
    weft = np.clip(1.0 - ((fy - 0.5) / (0.48 * sl_f)) ** 2, 0, 1) ** 0.5
    over = ((ix + iy) // 2 % 2) == 0                  # 2/2 twill: the float steps one yarn each row
    h = np.where(over, warp * (0.7 + 0.3 * np.sin(math.pi * fy)), weft * (0.7 + 0.3 * np.sin(math.pi * fx)))
    h = np.maximum(h, 0.6 * np.minimum(warp, weft))
    fuzz = JT.spectral_noise(shape, 0.05, 0.2, tile, 42)
    hmm = 0.25 * h + 0.012 * fuzz
    gaps = 1.0 - np.clip(h * 1.5, 0, 1)
    # the plaid: a light and a dark half (the 6 cm check), a narrow light stripe and a dark one, the same in both directions; a yarn
    # takes its band's tone (warp tones from x, weft tones from y), so the checks cross where they meet
    def band(u):
        u = u % 1.0
        return 0.7 * np.cos(2 * math.pi * u) + np.where(u < 0.06, 1.0, np.where((u > 0.48) & (u < 0.6), -1.0, np.where((u > 0.62) & (u < 0.66), 0.6, 0.0)))
    yarn_band = np.where(over, band((ix + 0.5) / n), band((iy + 0.5) / n))
    fleck = JT.spectral_noise(shape, 0.3, 1.0, tile, 43)
    tone = JT.unit(0.5 * yarn_band + 0.2 * (np.where(over, sl_w, sl_f) - 1.0) / 0.12 * 0.3 + 0.12 * fleck)
    sizes = {"weave": (JT.peak_mm(h, tile, 1), card["pattern_mm"]["weave"]),
             "plaid": (JT.peak_mm(yarn_band, tile, 1), card["pattern_mm"]["plaid"])}
    return hmm, np.stack([tone, gaps, JT.unit(hmm)], -1), tile, sizes


MAKERS = {"Vinyl": vinyl, "Tweed": tweed}


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {"_about": "The Catalina 22's own detail maps (docs/c22-9, Tools/shipkit/catalina22/textures/textures_c22.py);"
                      " each tiles at tile_m (x, y) metres; normals OpenGL. Medium draws none of them."}
    for name, card in OWN.items():
        hmm, m, tile, sizes = MAKERS[name](card)
        nrm = JT.normal_map(hmm, tile)
        JT.save(nrm, os.path.join(OUT, f"T_C22_{name}_N.png"))
        JT.save(m, os.path.join(OUT, f"T_C22_{name}_M.png"))
        h, w = hmm.shape
        meta[name] = {"tile_m": [tile[0] / 1000.0, tile[1] / 1000.0], "px": [w, h],
                      "px_per_mm": round(min(w / tile[0], h / tile[1]), 2), "fade_m": card["fade_m"],
                      "tiling_N": JT.tiling(nrm), "tiling_M": JT.tiling(m), "repeat_N": JT.repeat_share(nrm),
                      "repeat_M": JT.repeat_share(m), "size": JT.size_report(sizes)}
        print(name, json.dumps(meta[name]))
    json.dump(meta, open(os.path.join(OUT, "c22_detail.json"), "w"), indent=1)
    gat = os.path.join(OUT, ".gitattributes")
    if not os.path.exists(gat):
        open(gat, "w").write("# Plain git blobs: cloud sessions cannot upload to Git LFS\n*.png -filter -diff -merge binary\n")


if __name__ == "__main__":
    main()
