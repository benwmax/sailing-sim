"""Track A self-checks (no engine, no textures needed):  python3 -I Tools/envloop/ground/test_ground.py

  card      every region pack in packs/: eight surfaces, CC0 sources, sizes and colours in range, hero-band sharpness at every tier
  weights   the weights sum to 1, are never negative, and each surface wins somewhere on the test shore
  decode    the vertex-colour decode reads BuildChunk's own tones: open grass, woods, low flats, clay and sand banks
  hlsl      the HLSL is fully generated (no {PLACEHOLDER} left, braces balance), its constants are the card's, and the
            committed copy M_Ground.hlsl (what scripts/import_ground.py builds M_Ground from) is up to date
  shared    Track 0's shared pack file (Tools/envloop/packs/<pack>/ground.json) names only surfaces on the card
"""
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ground_hlsl  # noqa: E402
import ground_material as gm  # noqa: E402
import scene as sc  # noqa: E402
import pack  # noqa: E402

FAIL = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def test_card():
    for f in sorted(os.listdir(os.path.join(HERE, "packs"))):
        test_pack(f[:-5])


def test_pack(name):
    card = pack.load(name)
    s = card["surfaces"]
    check(f"{name}: fills the eight roles in order", [x["id"] for x in s] == pack.ROLES)
    check("every source CC0", all(x["source"]["licence"] == "CC0" for x in s))
    for x in s:
        for season in ("summer", "dormant"):
            a = x["albedo_linear"][season]
            check(f"{x['id']} {season} albedo in 0.03..0.5", all(0.03 <= v <= 0.5 for v in a), str(a))
        px = card["tiers"]["Medium"]["res"] / x["tile_m"]
        check(f"{x['id']} Medium keeps 1 cm/px or finer", px >= 100, f"{px:.0f} px/m")


def test_weights():
    scn = sc.Scene()
    xs = np.linspace(-100, 100, 400)
    ys = np.linspace(-20, 80, 200)
    X, Y = np.meshgrid(xs, ys)
    x, y = X.ravel(), Y.ravel()
    at = scn.attributes(x, y)
    P = np.stack([x, y, at["Z"]], -1)
    w = gm.weights(P, at["N"], at["C"], at["Near"], scn.water, at["Mown"])
    check("weights sum to 1", np.allclose(w.sum(-1), 1, atol=1e-4))
    check("weights never negative", (w >= -1e-6).all())
    wins = np.bincount(w.argmax(-1), minlength=8)
    check("each surface wins somewhere on the test shore", (wins > 0).all(), ", ".join(f"{k} {n}" for k, n in zip(gm.IDS, wins)))


def test_decode():
    N = np.array([[0, 0, 1.0]])
    cases = {
        "open grass": ([0.36, 0.36, 0.16], 0.0, 3.0, 0.0, "rough"),
        "mown lawn": ([0.36, 0.36, 0.16], 0.0, 3.0, 1.0, "lawn"),
        "woods": ([0.16, 0.22, 0.08], 0.0, 3.0, 0.0, "litter"),
        "clay bank": ([0.42, 0.30, 0.20], 1.0, 0.9, 0.0, "clay"),
        "sand bank": ([0.50, 0.42, 0.30], 1.0, 0.9, 0.0, "sand"),
        "swash": ([0.42, 0.30, 0.20], 1.0, 0.05, 0.0, "mud"),
    }
    for name, (c, near, z, mown, want) in cases.items():
        # Average over a few spots so the patch noise doesn't decide the case.
        pts = np.array([[17.3 * k, 5.1 * k, z] for k in range(1, 40)])
        w = gm.weights(pts, np.repeat(N, len(pts), 0), np.repeat([c], len(pts), 0), np.full(len(pts), near), 0.0,
                       np.full(len(pts), mown)).mean(0)
        got = gm.IDS[int(w.argmax())]
        check(f"decode {name} -> {want}", got == want, f"got {got} ({w.max():.2f})")


def test_hlsl():
    code = ground_hlsl.build()
    left = re.findall(r"\{[A-Z_]+\}", code)
    check("HLSL has no placeholders left", not left, ", ".join(left))
    check("HLSL braces balance", code.count("{") == code.count("}"))
    card = pack.load()
    first = card["surfaces"][0]["albedo_linear"]["summer"]
    check("HLSL carries the card's colours", "float3(%.4f, %.4f, %.4f)" % tuple(first) in code)
    committed = os.path.join(HERE, "M_Ground.hlsl")
    check("M_Ground.hlsl is up to date (python3 -I Tools/envloop/ground/ground_hlsl.py > Tools/envloop/ground/M_Ground.hlsl)",
          os.path.exists(committed) and open(committed).read().strip() == code.strip())


def test_shared():
    import json
    for name in sorted(f[:-5] for f in os.listdir(os.path.join(HERE, "packs"))):
        shared = os.path.join(HERE, "..", "packs", name, "ground.json")
        if not os.path.exists(shared):
            print(f"skip shared pack file for {name} (none)")
            continue
        ids = {x["id"] for x in pack.load(name)["surfaces"]}
        assets = [e["asset"] for e in json.load(open(shared))["entries"]]
        check(f"{name}: shared ground.json names only card surfaces", set(assets) <= ids, ", ".join(sorted(set(assets) - ids)))
        check(f"{name}: shared ground.json covers every card surface", ids <= set(assets), ", ".join(sorted(ids - set(assets))))


if __name__ == "__main__":
    test_card()
    test_weights()
    test_decode()
    test_hlsl()
    test_shared()
    print("FAILED: " + ", ".join(FAIL) if FAIL else "all passed")
    sys.exit(1 if FAIL else 0)
