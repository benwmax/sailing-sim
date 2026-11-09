"""Checks that BOAT_CODE's ACRYLIC_WEAR lines, the copies in M_BoatKit and M_J22HeroGlass, and port.py agree
(docs/texloop-acrylic).

    python Tools/texloop/acrylic/test_acrylic.py
"""
import ast
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import port  # noqa: E402
import test_wear  # noqa: E402
import wear  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def constant(path, name):
    for node in ast.parse(open(os.path.join(REPO, path)).read()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not in {path}")


def block():
    code = constant("scripts/make_materials.py", "BOAT_CODE")
    assert code.count("// ACRYLIC_WEAR >>>") == 1 and code.count("// ACRYLIC_WEAR <<<") == 1, "one ACRYLIC_WEAR block"
    assert "gel *= (age >= 0.0 && abs(Surface - 14.0) < 0.5) ? 0.0f : 1.0f;" in code, "aged acrylic must not chalk as gelcoat"
    assert "surf != 13 && surf != 14" in code, "the detail-map block skips acrylic (no gelcoat orange peel)"
    return code[code.index("// ACRYLIC_WEAR >>>"):code.index("// ACRYLIC_WEAR <<<")]


def check_constants(b):
    lits = {tuple(float(x) for x in m.split(",")) for m in re.findall(r"float3\(([-0-9., ]+)\)", b)}
    for c in (port.BLEACH, port.HAZE, port.DUST, port.CRACK, port.SCRATCH, port.MINERAL, port.MILDEW):
        assert tuple(float(x) for x in c) in lits, "colour %s differs from port.py" % (c,)
    for frag in ("acP / 2.5", "* 3.1 + 4.1", "float2(23.3, 71.9)", "0.6 * timeK * acSky * sunF",
                 "timeK * (0.12 + 0.55 * dirtK) * (1.0 - 0.5 * saturate(care)) * (0.6 + 0.4 * acSky) * sunF * (0.75 + 0.5 * acN)",
                 "0.55 * acHaze", "rough = lerp(rough, 0.32, acHaze)", "1.0 - 0.8 * acHaze",
                 "dirtK * saturate(acNz * 1.5) * (0.35 + 0.65 * acN)", "0.45 * acDust", "lerp(rough, 0.7, 0.6 * acDust)",
                 "acP / 6.0", "float2(53.1, 17.3)", "saturate((timeK - 0.3) / 0.5) * (0.45 + 0.55 * (1.0 - saturate(care)))",
                 "smoothstep(1.0 - acCr, 1.45 - acCr, acZn)", "acP / 0.25", "float2(12.7, 31.1)", "float2(26.9, 18.3)",
                 "0.006 / 0.25", "min(1.0, acW / acPw * 2.5) * smoothstep(0.3, 0.7, acN)", "0.35 * acCrA", "0.5 * acCrack",
                 "lerp(rough, 0.45, 0.4 * acCrA + 0.5 * acCrack)", "1.0 - 0.5 * acCrA",
                 "(0.08 * saturate(4.0 * timeK) + 0.45 * timeK + 0.15 * dirtK)", "/ 1.2", "17.9 + 3.0 * acL", "0.3 + 0.4 * frac(acH * 7.3)",
                 "0.8 * acAl * acAl", "0.006 * sqrt(acT)", "min(1.0, acSw / acPx * 2.5) * (0.4 + 0.6 * frac(acH * 11.3))", "0.45 * acScr",
                 "acP / 0.5", "float2(41.3, 29.9)", "0.05 + 0.07 * frac(acWh * 7.7)", "- 0.5) * 0.2) * 0.5", "max(0.012, acPx)",
                 "1.0 - 0.18 * dirtK * (0.2 + 0.8 * saturate(acNz * 2.0))", "0.12 * smoothstep(acWr, acWr - acWw, acWd)", "0.5 * acSpot",
                 "acP / 0.15", "step(0.95, acM)", "saturate((dirtK - 0.6) / 0.4)", "smoothstep(150.0, 400.0, Depth)",
                 "saturate(acHaze + 0.5 * acCrA + 0.6 * acDust + 0.3 * acSpot)"):
        assert frag in b, "BOAT_CODE ACRYLIC_WEAR no longer has: " + frag
    # the C++ test's rule (SailingSim.Visual.BoatShaderLiterals): no conditional between bare literals
    assert not re.search(r"\?\s*-?[0-9]+(\.[0-9]+)?\s*:\s*-?[0-9]+(\.[0-9]+)?(?![0-9.f])", b), "type the literals (0.5f)"


def check_wiring():
    kinds = constant("scripts/make_materials.py", "BOAT_SURFACE")
    assert kinds["CabinWindow"] == 14 and list(kinds.values()).count(14) == 1, "CabinWindow is kind 14, and only it"
    kit = open(os.path.join(REPO, "scripts/import_hardware_kit.py")).read()
    assert "@ACRYLIC_WEAR@" in kit and "acrylic_wear()" in kit and "if (surf == 14)" in kit, "M_BoatKit copies BOAT_CODE's block"
    assert test_wear.TIME.format(a="age") in kit and test_wear.DIRT.format(a="age", c="care") in kit, "M_BoatKit's timeK/dirtK differ"
    hero = open(os.path.join(REPO, "scripts/import_j22_hero.py")).read()
    glass = constant("scripts/import_j22_hero.py", "GLASS_CODE")
    assert "@ACRYLIC_WEAR@" in glass and "acrylic_wear()" in hero, "M_J22HeroGlass copies BOAT_CODE's block"
    assert test_wear.TIME.format(a="age") in glass and test_wear.DIRT.format(a="age", c="care") in glass, "M_J22HeroGlass's timeK/dirtK differ"
    assert '"Acrylic", 0.0' in hero, "the bilge water takes no acrylic wear"


def check_ladder():
    """Unset age and new: no change. Then haze orders L2 < L4, the kept L3 crazes but is no dustier than L2."""
    n = np.zeros((64, 64, 3)); n[..., 2] = 1.0
    p = np.stack(np.meshgrid(np.arange(64.0) * 0.5, np.arange(64.0) * 0.5), -1)
    px = np.full((64, 64), 0.03); depth = np.full((64, 64), 50.0)
    base = (0.006, 0.008, 0.010)
    for age, care in ((-1.0, 0.5), (0.0, 1.0)):
        col, rough, coat, haze = port.acrylic(base, 0.04, 1.0, age, care, n, p, px, depth)
        assert np.allclose(col, base) and np.allclose(rough, 0.04) and np.allclose(coat, 1.0) and haze.max() == 0, "no weathering at Age %s" % age
    out = {lv["id"]: port.acrylic(base, 0.04, 1.0, lv["age"], lv["care"], n, p, px, depth, parts=True)[4] for lv in wear.levels()}
    assert out["L2"]["haze"].mean() < out["L4"]["haze"].mean()
    assert out["L1"]["craze"].max() == 0 and out["L2"]["craze"].mean() < out["L3"]["craze"].mean() < out["L4"]["craze"].mean()
    assert out["L3"]["dust"].mean() < out["L2"]["dust"].mean() and out["L3"]["mildew"].max() == 0


if __name__ == "__main__":
    b = block()
    check_constants(b)
    check_wiring()
    check_ladder()
    print("acrylic wear matches: make_materials.py ACRYLIC_WEAR, import_hardware_kit.py, import_j22_hero.py, port.py")
