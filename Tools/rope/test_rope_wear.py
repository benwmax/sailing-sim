"""Checks for the rope's wear (docs/texture-loop/rope.md): the numpy twin and the two HLSL copies agree, and the levels
come out in the order a sailor would rank them.

    python3 Tools/rope/test_rope_wear.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import rope_wear as R  # noqa: E402

# the rope lines each copy must carry (rope_wear.py is the reference)
SHARED = ["3.0 + 12.0 * (1.0 - cr)", "0.35 * tK + 0.1 * dK" , "float3(0.19, 0.20, 0.16), 0.45 * "]


def main():
    lv = {k: R.rope_wear(a, c) for k, (a, c) in R.LEVELS.items()}
    assert lv["L0"] == (0.0, 0.0, 0.0, 0.0), "a new line has no wear"
    g = {k: v[1] for k, v in lv.items()}
    assert g["L0"] < g["L1"] < g["L3"] < g["L2"] < g["L4"], f"grime order {g}"
    assert lv["L4"][3] > 0.5 and lv["L2"][3] == 0.0, "mildew only on the neglected boat"
    assert R.rope_wear(-1.0, 0.5)[3] == 0.0, "unset Age keeps the old fixed look"
    rope = open(os.path.join(REPO, "scripts", "import_boat_detail.py")).read()
    kit = open(os.path.join(REPO, "scripts", "make_materials.py")).read()
    for s in SHARED:
        assert s in rope, "ROPE_CODE lacks " + s
    for s in ("3.0 + 12.0 * (1.0 - cr)", "0.35 * rT + 0.1 * rD", "float3(0.19, 0.20, 0.16), 0.45 * milK"):
        assert s in kit, "BOAT_CODE surf == 9 lacks " + s
    src = open(os.path.join(HERE, "rope_wear.py")).read()
    for s in ("3.0 + 12.0 * (1.0 - care)", "0.35 * t + 0.1 * d", "0.8 * d", "np.array([0.19, 0.20, 0.16])"):
        assert s in src, "rope_wear.py lacks " + s
    assert "0.8 * dK" in rope and "0.8 * rD" in kit
    print("rope wear OK:", {k: tuple(round(x, 2) for x in v) for k, v in lv.items()})


if __name__ == "__main__":
    main()
