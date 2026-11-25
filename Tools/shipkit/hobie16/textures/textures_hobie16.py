"""The Hobie 16's own close-up detail map (docs/hobie16-8): the woven, PVC-coated polyester of her trampoline. Made
with numpy (no photos), tileable, sized from the card's real pattern (textures_hobie16.json 'maps.own'), written as
plain PNGs to Inputs/hobie16-detail (the folder's .gitattributes keeps them out of Git LFS, which the cloud cannot
push): a normal map (OpenGL) and a mask map.

    python3 -I Tools/shipkit/hobie16/textures/textures_hobie16.py [<out dir>]

  Tramp  30 x 30 mm, 512 px    mask R cavity (the gaps between the yarns), G roughness, B height

The shared library's maps (Inputs/boat-detail: Gelcoat, Metal, Canvas) are already resident for the J/22 and cost her
nothing. Bluebonnet's generator (Tools/shipkit/jclass/textures.py) supplies the noise, normal-map and measuring
helpers, as it does for the Catalina 22's maps (Tools/shipkit/catalina22/textures/textures_c22.py).
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

OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(REPO, "Inputs", "hobie16-detail")
CARDS = json.load(open(os.path.join(HERE, "textures_hobie16.json")))
OWN = CARDS["maps"]["own"]


def tramp(card):
    """A tight 2/2 basket weave of flat coated yarns about 1.2 mm apart: pairs of warp yarns over pairs of weft, each
    yarn a flattened crown (the PVC coating rounds it and half fills the gaps), with the coating's own fine orange peel
    and a slight wander in each yarn's width so the weave is not a lattice."""
    tile = card["tile_mm"]
    shape = (card["px"][1], card["px"][0])
    x, y = JT.grid(shape)
    n = int(round(tile[0] / 1.2))                     # yarns across the tile (a whole number, so it tiles)
    wx, wy = x * n, y * n
    ix, iy = np.floor(wx).astype(int), np.floor(wy).astype(int)
    fx, fy = wx - ix, wy - iy
    rng = np.random.default_rng(61)
    pw, pf = rng.random(n) * 2 * math.pi, rng.random(n) * 2 * math.pi
    sl_w = 1.0 + 0.06 * np.cos(2 * math.pi * 2 * y + pw[ix % n])
    sl_f = 1.0 + 0.06 * np.cos(2 * math.pi * 3 * x + pf[iy % n])
    warp = np.clip(1.0 - ((fx - 0.5) / (0.46 * sl_w)) ** 4, 0, 1) ** 0.5     # flat-topped: coated, not round
    weft = np.clip(1.0 - ((fy - 0.5) / (0.46 * sl_f)) ** 4, 0, 1) ** 0.5
    over = ((ix // 2) + (iy // 2)) % 2 == 0          # basket: pairs over pairs
    h = np.where(over, warp * (0.75 + 0.25 * np.sin(math.pi * ((iy % 2) + fy) / 2)),
                 weft * (0.75 + 0.25 * np.sin(math.pi * ((ix % 2) + fx) / 2)))
    coat = 0.35                                       # the coating half fills the gaps
    h = np.maximum(h, coat * np.maximum(warp, weft))
    peel = JT.spectral_noise(shape, 0.15, 0.5, tile, 62)
    hmm = 0.12 * h + 0.004 * peel
    cav = 1.0 - JT.unit(np.clip(h, coat, 1.0))
    rough = JT.unit(0.5 * cav + 0.5 * JT.unit(JT.spectral_noise(shape, 0.3, 1.2, tile, 63)))
    sizes = {"weave": (JT.peak_mm(warp, tile, 1), card["pattern_mm"]["weave"])}
    return hmm, np.stack([cav, rough, JT.unit(hmm)], -1), tile, sizes


MAKERS = {"Tramp": tramp}


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {"_about": "The Hobie 16's own detail map (docs/hobie16-8, Tools/shipkit/hobie16/textures/textures_hobie16.py);"
                      " it tiles at tile_m (x, y) metres; normals OpenGL. Medium draws none of them."}
    for name, card in OWN.items():
        hmm, m, tile, sizes = MAKERS[name](card)
        nrm = JT.normal_map(hmm, tile)
        JT.save(nrm, os.path.join(OUT, f"T_H16_{name}_N.png"))
        JT.save(m, os.path.join(OUT, f"T_H16_{name}_M.png"))
        h, w = hmm.shape
        meta[name] = {"tile_m": [tile[0] / 1000.0, tile[1] / 1000.0], "px": [w, h],
                      "px_per_mm": round(min(w / tile[0], h / tile[1]), 2), "fade_m": card["fade_m"],
                      "tiling_N": JT.tiling(nrm), "tiling_M": JT.tiling(m), "repeat_N": JT.repeat_share(nrm),
                      "repeat_M": JT.repeat_share(m), "size": JT.size_report(sizes)}
        print(name, json.dumps(meta[name]))
    json.dump(meta, open(os.path.join(OUT, "hobie16_detail.json"), "w"), indent=1)
    gat = os.path.join(OUT, ".gitattributes")
    if not os.path.exists(gat):
        open(gat, "w").write("# Plain git blobs: cloud sessions cannot upload to Git LFS\n*.png -filter -diff -merge binary\n")


if __name__ == "__main__":
    main()
