"""Checks that FABRIC_CODE's FABRIC_WEAR lines (scripts/make_materials.py) and port.py agree, and the ladder's order
(docs/texloop-crewfabric).

    python Tools/texloop/crewfabric/test_crewfabric.py
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


def constant(name):
    for node in ast.parse(open(os.path.join(REPO, "scripts/make_materials.py")).read()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    raise AssertionError(name + " not in make_materials.py")


def block():
    code = constant("FABRIC_CODE")
    assert code.count("// FABRIC_WEAR >>>") == 1 and code.count("// FABRIC_WEAR <<<") == 1, "one FABRIC_WEAR block"
    return code[code.index("// FABRIC_WEAR >>>"):code.index("// FABRIC_WEAR <<<")]


def check_constants(b):
    f = lambda c: "float%d(" % len(c) + ", ".join("%.2f" % x for x in c) + ")"  # noqa: E731
    for k in (1, 2, 3):
        assert f(port.W[k]) in b, "fwW for kind %d differs from port.W" % k
        assert f(port.W2[k]) in b, "fwW2 for kind %d differs from port.W2" % k
    assert ": " + f(port.W[4]) + ";" in b and ": " + f(port.W2[4]) + ";" in b, "kind 4 (the default branch) differs"
    for c in (port.GRIME, port.MILDEW):
        assert "float3(" + ", ".join("%.3f" % x for x in c) + ")" in b, "colour %s differs" % (c,)
    assert "float3(%.2f, %.2f, %.2f)" % port.SALT in b and "float3(%.1f, %.2f, %.2f)" % port.FADE_TINT in b
    assert test_wear.TIME.format(a="fwAge") in b, "timeK differs from wear.time_k"
    assert test_wear.DIRT.format(a="fwAge", c="Care") in b, "dirtK differs from wear.dirt_k"
    for frag in ("UV0 * UVm * 100.0", "fwP / 9.0", "/ 3.1 + 5.3", "fwP / 14.0 + 11.7", "/ 4.3 + 2.9", "saturate(0.5 + 0.5 * Nw.z)",
                 "smoothstep(60.0, 150.0, Depth)", "0.55) + 0.07 * (1.0 - fwLum)", "pow(fwTime, 0.7) * fwW.x * (0.35 + 0.65 * fwSky) * (0.8 + 0.4 * fwBlot) * lerp(1.0, saturate(detail), 0.3)",
                 "lerp(RoughOut, 0.88, 0.6 * fwTime * fwW2.y)", "saturate(0.2 + 0.8 * smoothstep(0.4, 0.7, fwGrimeN) * (0.5 + 0.5 * (1.0 - fwSky)))",
                 "AlbedoOut * 0.6 + float3", "fwP / 0.12", "step(1.0 - 0.30 * fwTime - 0.15 * fwDirt, fwPh)", "smoothstep(0.22, 0.38,",
                 "0.35 * fwTime * fwW.w", "frac((fwP.y + 1.5 * fwBlot) / 1.6) - 0.5", "(1.0 - smoothstep(0.1, 0.35, UV0.y)) * (0.5 + 0.5 * fwB)", "saturate((fwDirt - 0.2) / 0.5)", "smoothstep(0.44, 0.48, fwRing)",
                 "smoothstep(0.34, 0.42, fwRing) * (1.0 - smoothstep(0.42, 0.45, fwRing))", "0.3 * fwTide", "fwP / 5.0 + 3.3", "fwP / 0.18",
                 "step(0.75, fwMh)", "smoothstep(0.12, 0.25,", "saturate((fwDirt - 0.5) / 0.4) * (1.0 - saturate(Care)) * smoothstep(0.6, 0.8, fwM)",
                 "lerp(0.25, 0.9 * fwSpeck, fwNear)"):
        assert frag in b, "FABRIC_WEAR no longer has: " + frag
    # the C++ test's rule for BOAT_CODE holds here too: no conditional between bare literals (Metal refuses FP64)
    assert not re.search(r"\?\s*-?[0-9]+(\.[0-9]+)?\s*:\s*-?[0-9]+(\.[0-9]+)?(?![0-9.f])", b), "type the literals (0.5f)"


def check_wiring():
    kinds = constant("FABRIC_WEAR_KIND")
    assert kinds["MI_Crew_PFDShell"][0] == 1 and kinds["MI_Crew_Polo"][0] == 2 and kinds["MI_Crew_CapCloth"][0] == 3
    assert "MI_Crew_Webbing" not in kinds and "MI_Crew_ShoeLeather" not in kinds, "webbing and leather are not this pass's"
    src = open(os.path.join(REPO, "scripts/make_materials.py")).read()
    for name in ("Age", "Care", "Kind", "UVm", "Nw"):
        assert '"%s"' % name in src[src.index("def build_crew_fabric"):], name + " not wired into M_CrewFabric"
    pawn = open(os.path.join(REPO, "Source/SailingSim/Private/SailboatPawn.cpp")).read()
    assert "SailingCrewAge=" in pawn and pawn.count("WearGear(Mid)") >= 5, "the pawn sets the crew gear's Age"
    lv = {l["id"]: l for l in wear.levels()}
    assert "kClubGearAge = %g.f" % lv["L2"]["age"] in pawn and "kClubGearCare = %gf" % lv["L2"]["care"] in pawn, "club gear defaults to L2"


def check_ladder():
    """Age unset: no change at all; new: no change; then the ladder's order on the vest."""
    h = w = 6
    uv = np.stack(np.meshgrid(np.linspace(0, 0.3, w), np.linspace(0, 0.3, h)), -1)
    nz = np.linspace(-1, 1, h * w).reshape(h, w)
    depth = np.full((h, w), 50.0)
    base = np.broadcast_to(np.array([0.02, 0.07, 0.42]), (h, w, 3))
    rough = np.full((h, w), 0.7); fuzz = np.full((h, w), 0.25); det = np.ones((h, w))
    for age, care in ((-1.0, 0.5), (0.0, 1.0)):
        for kind in (1, 2, 3, 4):
            c, r, f = port.fabric(base, rough, fuzz, det, uv, nz, depth, age, care, kind)
            assert np.allclose(c, base) and np.allclose(r, rough) and np.allclose(f, fuzz), "no wear at Age %s kind %d" % (age, kind)
    c, r, f = port.fabric(base, rough, fuzz, det, uv, nz, depth, 6.0, 0.5, 0)
    assert np.allclose(c, base), "kind 0 (webbing, leather): never"
    out = {lv["id"]: port.fabric(base, rough, fuzz, det, uv, nz, depth, lv["age"], lv["care"], 1, parts=True)[3] for lv in wear.levels()}
    assert out["L1"]["fade"].mean() < out["L2"]["fade"].mean() < out["L3"]["fade"].mean()
    assert out["L3"]["grime"].mean() < out["L2"]["grime"].mean() < out["L4"]["grime"].mean()
    assert out["L3"]["mildew"].max() == 0 and out["L2"]["mildew"].mean() < 0.25 * out["L4"]["mildew"].mean(), "a club vest has a trace, a kept one none"


if __name__ == "__main__":
    b = block()
    check_constants(b)
    check_wiring()
    check_ladder()
    print("crew fabric wear matches: make_materials.py FABRIC_WEAR, SailboatPawn.cpp, port.py")
