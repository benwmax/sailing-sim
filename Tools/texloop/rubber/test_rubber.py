"""Checks that BOAT_CODE's RUBBER_WEAR and WEBBING_WEAR lines, M_BoatKit's copy and port.py agree (docs/texloop-rubber).

    python Tools/texloop/rubber/test_rubber.py
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
import wear  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def constant(path, name):
    for node in ast.parse(open(os.path.join(REPO, path)).read()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not in {path}")


def block(code, name):
    a, b = "// %s_WEAR >>>" % name, "// %s_WEAR <<<" % name
    assert code.count(a) == 1 and code.count(b) == 1, "one %s_WEAR block" % name
    return code[code.index(a):code.index(b)]


def f3(c):
    return "float3(" + ", ".join("%g" % x for x in c) + ")"


def check_constants(code):
    rb, wb = block(code, "RUBBER"), block(code, "WEBBING")
    for c in (port.BLOOM, port.PVC_YELLOW, port.CRACK, port.ABRADE, port.MARK, port.DUST, port.MILDEW):
        assert f3(c) in rb, "RUBBER_WEAR colour %s differs from port.py" % (c,)
    for frag in ("timeK * (0.3 + 1.2 * dirtK) * rbSky * sunF * (1.0 + (rbN - 0.5) * (0.5 + 1.0 * dirtK))", "(0.85 - 0.6 * saturate(care)) * rbBloom",
                 "lerp(0.92, 0.45, saturate(care))", "smoothstep(0.45, 0.85, timeK) * (1.0 - 0.85 * saturate(care)) * (1.0 - 0.7 * rbPale) * rbNear * (0.4 + 0.6 * rbSky)",
                 "rbP / float2(0.35, 0.9)", "step(1.0 - 0.5 * rbCk, frac(rbCh * 11.7))", "smoothstep(0.04, 0.05 + 0.08 * rbCk, abs(rbCx))", "0.9 * rbCf.y * (frac(rbCh * 5.3) - 0.5) + 0.1 * sin(rbCf.y * 9.0 + rbCh * 20.0)",
                 "rbP / float2(6.0, 0.35)", "1.0 - 0.25 * saturate(3.0 * timeK) - 0.5 * dirtK", "(0.06 + 0.16 * frac(rbH * 9.1)) * sqrt(rbT)",
                 "(1.0 - saturate(abs(rbNz) * 1.5))", "smoothstep(400.0, 1200.0, Depth)", "saturate((dirtK - 0.6) / 0.4)", "step(0.92, rbM)",
                 "rbQ = rbP / 2.0", "float2(23.3, 71.9)", "* 3.1 + 4.9"):
        assert frag in rb, "BOAT_CODE RUBBER_WEAR no longer has: " + frag
    for c in (port.WB_FADE, port.WB_FUZZ, port.WB_GRIT, port.WB_FRAY, port.WB_MILDEW):
        assert f3(c) in wb, "WEBBING_WEAR colour %s differs from port.py" % (c,)
    for frag in ("timeK * (1.0 - 0.5 * smoothstep(0.6, 0.95, saturate(care)) * saturate(age / 8.0))", "wbTime * (0.55 + 0.45 * wbSky) * sunF * (0.8 + 0.4 * wbN)",
                 "lerp(float3(wbLum, wbLum, wbLum), col, 0.4) * 0.9", "saturate(wbTime * (0.6 + 0.9 * dirtK)) * saturate(wbN * 2.2 - 0.4)",
                 "dirtK * (0.5 + 0.5 * wbN)", "saturate((wbTime - 0.3) * 2.5) * saturate((wbCurv - 0.7) * 2.0)", "saturate((dirtK - 0.45) / 0.35)",
                 "step(0.88, wbM)", "wbQ = wbP / 3.0", "float2(29.3, 53.9)", "* 3.0 + 6.1"):
        assert frag in wb, "BOAT_CODE WEBBING_WEAR no longer has: " + frag
    for b in (rb, wb):   # the C++ test's rule (SailingSim.Visual.BoatShaderLiterals): no conditional between bare literals
        assert not re.search(r"\?\s*-?[0-9]+(\.[0-9]+)?\s*:\s*-?[0-9]+(\.[0-9]+)?(?![0-9.f])", b), "type the literals (0.5f)"
    for frag in ("abs(sin(3.14159 * hwP.y / 0.12))", "(0.7 + 0.45 * sqrt(wbRib)) * (0.85 + 0.2 * wbWeft), 1.0 - smoothstep(100.0, 300.0, Depth)", "step(0.5, frac(hwP.y / 0.24))) / 0.12"):
        assert frag in code, "BOAT_CODE's webbing ribs no longer have: " + frag
    # gated: with an age only (the old lines run on unset boats)
    assert "if (surf == 8 && age >= 0.0)" in code and "else if (surf == 8 && age < 0.0)" in code
    assert "if (surf == 14 && age >= 0.0)" in code and "(surf == 14 && age < 0.0)" in code


def check_wiring():
    kinds = constant("scripts/make_materials.py", "BOAT_SURFACE")
    assert kinds["Rubrail"] == 8 and kinds["Rubber"] == 8 and kinds["Webbing"] == 14
    assert "Webbing" in constant("scripts/make_materials.py", "BOAT_LIBRARY")
    hero = open(os.path.join(REPO, "scripts/import_j22_hero.py")).read()
    assert '"RubRail": 8' in hero and '"ExtensionBlack": 8' in hero and '"Webbing": 14' in hero
    kit = open(os.path.join(REPO, "scripts/import_hardware_kit.py")).read()
    assert "@RUBBER_WEAR@" in kit and "rubber_wear()" in kit, "M_BoatKit copies BOAT_CODE's rubber block"
    fleet = open(os.path.join(REPO, "Tools/blender/build_fleet.py")).read()
    assert 'bar(hull, path, secs, "Webbing")' in fleet and '"Webbing"]' in fleet, "the dinghies' hiking strap is the Webbing slot"
    cpp = open(os.path.join(REPO, "Source/SailingSimTests/Private/VisualTests.cpp")).read()
    assert '{ TEXT("Webbing"), 14 }' in cpp


def check_ladder():
    """Unset age: the old lines. New: no change. Then L4 blooms more than L2, the kept L3 is clean, cracks come late."""
    n = np.zeros((40, 40, 3)); n[..., 1] = -1.0
    v = -n
    x, z = np.meshgrid(np.linspace(0, 30, 40), np.linspace(0, 6, 40))
    p = np.stack([x, z], -1)
    depth = np.full((40, 40), 50.0)
    curv = np.zeros((40, 40))
    for base, rough in (((0.03, 0.03, 0.03), 0.5), ((0.1022, 0.0976, 0.0865), 0.5)):
        col, r = port.rubber(base, rough, 0.0, 1.0, n, v, p, depth)
        assert np.allclose(col, base) and np.allclose(r, rough), "new rubber unchanged"
        col, r = port.rubber(base, rough, -1.0, 0.5, n, v, p, depth)
        assert np.allclose(col, base) and np.allclose(r, rough), "unset rubber: the old ageK line (0 with no livery wear)"
    col, r = port.webbing((0.022, 0.022, 0.024), 0.85, 0.0, 1.0, n, v, p, curv, depth)
    rib, _ = port.webbing((0.022, 0.022, 0.024), 0.85, -1.0, 0.5, n, v, p, curv, depth)
    assert np.allclose(col, rib), "new webbing: only the weave's ribs"
    out = {lv["id"]: port.rubber((0.03, 0.03, 0.03), 0.5, lv["age"], lv["care"], n, v, p, depth, parts=True) for lv in wear.levels()}
    lum = {k: float((c * port.LUMA).sum(-1).mean()) for k, (c, r, d) in out.items()}
    assert lum["L0"] <= lum["L1"] < lum["L2"] < lum["L4"] and lum["L3"] < lum["L2"], lum
    assert out["L3"][2]["dust"].max() == 0 and out["L3"][2]["mildew"].max() == 0
    assert out["L2"][2]["crack"].max() < 0.05 and out["L4"][2]["crack"].max() > 0.3 and out["L3"][2]["crack"].mean() < out["L4"][2]["crack"].mean()
    wo = {lv["id"]: port.webbing((0.022, 0.022, 0.024), 0.85, lv["age"], lv["care"], n, v, p, curv, depth) for lv in wear.levels()}
    wl = {k: float((c * port.LUMA).sum(-1).mean()) for k, (c, r) in wo.items()}
    assert wl["L0"] < wl["L1"] < wl["L2"] < wl["L4"] and wl["L3"] < wl["L4"], wl


if __name__ == "__main__":
    code = constant("scripts/make_materials.py", "BOAT_CODE")
    check_constants(code)
    check_wiring()
    check_ladder()
    print("rubber and webbing wear match: make_materials.py RUBBER_WEAR / WEBBING_WEAR, import_hardware_kit.py, port.py")
