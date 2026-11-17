"""The frigate Commonwealth's own close-up detail map (slice 15, docs/shipkit-15), tileable, built from numpy (no
photos, nothing to licence).

    python3 -I Tools/shipkit/frigate/textures.py [out dir] [--res 2048] [--check]

Her other surfaces reuse the boats' shared library (Inputs/boat-detail: Metal for the copper's rolled skin and the
wrought iron, Canvas for the flax, WoodVarnish for the grain under the paint) and the J-Class's (Inputs/jclass-detail:
Manila for the hemp, CastBronze for the guns' sand-cast iron and the bronze), so only what neither has is made here
(textures_1797.json 'maps'):

  T_Frigate_Oak_N/_M   400 x 200 mm, along the grain by across it: white oak (and the deck's pine draws from it too):
                       growth rings 3-6 mm apart wandering along the board, a band of open pores at each ring's start
                       (ring-porous earlywood), the medullary rays' light flecks 2-12 mm long, and a few checks 30-200
                       mm long along the grain.
                       M: R the grain's tone, G checks (1 in a check), B height

The maker's helpers (periodic spectral noise, normal maps, the tiling and repeat checks) are the J-Class's
(Tools/shipkit/jclass/textures.py, loaded by path). Every map is periodic, so it tiles with no seam; --check prints the
loop's tiling, repeat and size checks as JSON. Normals are OpenGL (+Y up), as the boat library's.
"""
import importlib.util
import json
import math
import os
import sys

import numpy as np

ARGS = sys.argv[1:]
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(REPO, "Inputs", "frigate-detail")
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 2048
CARDS = json.load(open(os.path.join(HERE, "textures_1797.json")))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = [path]                 # the J-Class maker reads its own arguments at import
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


JT = _load("jclass_textures", os.path.join(REPO, "Tools", "shipkit", "jclass", "textures.py"))
SURF = CARDS["surfaces"]["wood"]["pattern_mm"]


def oak(card):
    tile = card["tile_mm"]                       # x along the grain, y across it
    shape = (RES // 2, RES)
    H, W = shape
    rng = np.random.default_rng(1797)
    x, y = JT.grid(shape)
    # growth rings: 48 across the tile (about 4 mm apart, wider and narrower), wandering along the board as a flat-
    # sawn face's do; each ring's phase 0..1 from its start (the earlywood) to its end (the latewood)
    wander = JT.spectral_noise(shape, 10.0, 40.0, tile, 11, aniso=(10.0, 1.0))
    rings = 48
    ph = (y * rings + 0.45 * wander) % 1.0
    ring_no = np.floor(y * rings + 0.45 * wander) % rings      # periodic across the tile
    # earlywood: the ring's first fifth, full of open pores (dark dots 0.1-0.3 mm); latewood denser and darker
    early = np.clip(1.0 - ph / 0.22, 0, 1) ** 0.7
    pores = JT.spectral_noise(shape, 0.1, 0.3, tile, 13)
    pore = np.clip((pores - 0.8) * 2.0, 0, 1) * early
    late = np.clip((ph - 0.4) / 0.6, 0, 1)
    # rays: light flecks along the grain, 2-12 mm long and a fraction of a millimetre wide
    rays_n = JT.spectral_noise(shape, 0.2, 0.6, tile, 14, aniso=(18.0, 1.0))
    rays = np.clip((rays_n - 2.1) * 1.5, 0, 1)
    # a streaky tone along the grain (kept fine: a tile-sized blotch would repeat), and the rings' own shade
    tone_slow = JT.spectral_noise(shape, 3.0, 12.0, tile, 15, aniso=(8.0, 1.0))
    ring_tone = np.sin(ring_no * 12.9898) * 0.5
    tone = 0.5 + 0.06 * tone_slow - 0.16 * late + 0.06 * ring_tone + 0.18 * rays - 0.35 * pore
    # checks: a few cracks along the grain, 30-200 mm long, tapering at their ends
    chk = np.zeros(shape)
    n = 9
    for _ in range(n):
        cx, cy = rng.random() * W, rng.random() * H
        ln = rng.uniform(SURF["check_length"][0], SURF["check_length"][1]) / tile[0] * W
        wid = rng.uniform(0.15, 0.45) / tile[1] * H
        drift = rng.uniform(-0.02, 0.02)
        for s in np.linspace(0.0, 1.0, int(ln) + 2):
            px = int(cx + s * ln) % W
            py = cy + drift * s * ln
            taper = math.sin(math.pi * s) ** 0.5
            hw = max(wid * taper, 0.5)
            for dy in range(-int(hw) - 1, int(hw) + 2):
                q = 1.0 - abs(dy) / (hw + 0.5)
                if q > 0:
                    chk[int(py + dy) % H, px] = max(chk[int(py + dy) % H, px], q * taper)
    # heights (mm): the latewood stands a little proud (weathering wears the soft earlywood), pores and checks sunk
    h = 0.03 * late - 0.04 * pore - 0.35 * chk + 0.01 * JT.spectral_noise(shape, 1.0, 5.0, tile, 16)
    sizes = {"ring_spacing": (round(tile[1] / rings, 2), [3, 6]),
             "rays": (JT.feature_mm(rays_n, tile, 1), SURF["grain_rays"])}
    return h, np.stack([JT.unit(tone), np.clip(chk, 0, 1), JT.unit(h)], -1), tile, sizes


MAKERS = {"Oak": oak}


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {"_about": "Commonwealth's own detail maps (docs/shipkit-15, Tools/shipkit/frigate/textures.py); each tiles "
                      "at tile_m (x, y) metres; normals OpenGL."}
    for name, card in CARDS["maps"]["own"].items():
        hmm, m, tile, sizes = MAKERS[name](card)
        n = JT.normal_map(hmm, tile)
        JT.save(n, os.path.join(OUT, f"T_Frigate_{name}_N.png"))
        JT.save(m, os.path.join(OUT, f"T_Frigate_{name}_M.png"))
        h, w = hmm.shape
        meta[name] = {"tile_m": [tile[0] / 1000.0, tile[1] / 1000.0], "px": [w, h],
                      "px_per_mm": round(min(w / tile[0], h / tile[1]), 2),
                      "normal_strength": card["normal_strength"], "fade_m": card["fade_m"],
                      "tiling_N": JT.tiling(n), "tiling_M": JT.tiling(m), "repeat_N": JT.repeat_share(n),
                      "repeat_M": JT.repeat_share(m), "size": JT.size_report(sizes)}
        print(name, meta[name])
    json.dump(meta, open(os.path.join(OUT, "frigate_detail.json"), "w"), indent=1)
    if "--check" in ARGS:
        print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
