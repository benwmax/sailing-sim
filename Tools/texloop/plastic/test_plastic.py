"""Checks that BOAT_CODE's PLASTIC_WEAR lines, M_BoatKit's copy of them and port.py agree (docs/texloop-plastic).

    python Tools/texloop/plastic/test_plastic.py
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
    assert code.count("// PLASTIC_WEAR >>>") == 1 and code.count("// PLASTIC_WEAR <<<") == 1, "one PLASTIC_WEAR block"
    return code[code.index("// PLASTIC_WEAR >>>"):code.index("// PLASTIC_WEAR <<<")]


def check_constants(b):
    f3 = lambda c, fmt: "float3(" + ", ".join(fmt % x for x in c) + ")"  # noqa: E731
    assert f3(port.CHALK, "%.3f") in b, "chalk colour differs from port.CHALK"
    for c in (port.DUST, port.SCUFF, port.MILDEW):
        assert f3(c, "%g") in b, "colour %s differs from port.py" % (c,)
    for frag in ("timeK * (0.25 + 1.3 * dirtK)", "(0.85 - 0.45 * saturate(care))", "(0.4 + 1.2 * dirtK)", "saturate(0.5 + 0.5 * bpNz)", "(0.5 + 0.5 * bpCav)",
                 "saturate((bpCurv - 0.7) * 2.0)", "smoothstep(150.0, 400.0, Depth)", "1.0 - 0.08 * saturate(4.0 * timeK) - 0.35 * timeK - 0.15 * dirtK",
                 "0.25 + 0.35 * frac(bpH * 7.3)", "lerp(0.82, 0.55, saturate(care))", "step(0.93, bpM)", "saturate((dirtK - 0.6) / 0.4)", "smoothstep(0.25, 0.4, length(frac(bpMc) - 0.5))"):
        assert frag in b, "BOAT_CODE PLASTIC_WEAR no longer has: " + frag
    # the C++ test's rule (SailingSim.Visual.BoatShaderLiterals): no conditional between bare literals
    assert not re.search(r"\?\s*-?[0-9]+(\.[0-9]+)?\s*:\s*-?[0-9]+(\.[0-9]+)?(?![0-9.f])", b), "type the literals (0.5f)"


def check_wiring():
    kinds = constant("scripts/make_materials.py", "BOAT_SURFACE")
    assert kinds["BlackPlastic"] == 13
    hero = open(os.path.join(REPO, "scripts/import_j22_hero.py")).read()
    assert '"BlackPlastic": 13' in hero and '"CamBase": 13' in hero, "the hero J/22's black plastic is kind 13"
    kit = open(os.path.join(REPO, "scripts/import_hardware_kit.py")).read()
    assert "@PLASTIC_WEAR@" in kit and "plastic_wear()" in kit, "M_BoatKit copies BOAT_CODE's block"
    assert test_wear.TIME.format(a="age") in kit and test_wear.DIRT.format(a="age", c="care") in kit, "M_BoatKit's timeK/dirtK differ"


def check_ladder():
    """Unset age: no change. New: no change. Then the chalk orders L2 < L4 and the kept L3 is no dustier than L2."""
    n = np.zeros((4, 4, 3)); n[..., 2] = 1.0
    p = np.stack(np.meshgrid(np.arange(4.0), np.arange(4.0)), -1)
    curv = np.zeros((4, 4)); depth = np.full((4, 4), 50.0)
    base = (0.018, 0.018, 0.02)
    for age, care in ((-1.0, 0.5), (0.0, 1.0)):
        col, rough = port.plastic(base, 0.45, age, care, n, p, curv, depth)
        assert np.allclose(col, base) and np.allclose(rough, 0.45), "no weathering at Age %s" % age
    out = {lv["id"]: port.plastic(base, 0.45, lv["age"], lv["care"], n, p, curv, depth, parts=True)[2] for lv in wear.levels()}
    assert out["L2"]["chalk"].mean() < out["L4"]["chalk"].mean()
    assert out["L3"]["dust"].mean() < out["L2"]["dust"].mean() and out["L3"]["mildew"].max() == 0


if __name__ == "__main__":
    b = block()
    check_constants(b)
    check_wiring()
    check_ladder()
    print("plastic wear matches: make_materials.py PLASTIC_WEAR, import_hardware_kit.py, port.py")
