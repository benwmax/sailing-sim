"""Checks that the materials' HLSL and Tools/texloop/wear.py carry the same wear formulas (docs/texture-loop).

    python Tools/texloop/test_wear.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wear  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TIME = "saturate(0.25 * (1.0 - exp(-{a} / 0.75)) + 0.75 * (1.0 - exp(-{a} / 18.0)))"
DIRT = "saturate((1.0 - exp(-{a})) * (0.15 + 0.85 * (1.0 - saturate({c}))))"
YELLOW = "float3(%.1f, %.3f, %.2f)" % wear.YELLOW
BLOT = "(%.2f + %.1f * lerp(" % wear.BLOT


def check_source(path, a, c):
    s = open(os.path.join(REPO, path)).read()
    assert TIME.format(a=a) in s, path + ": timeK differs from wear.time_k"
    assert DIRT.format(a=a, c=c) in s, path + ": dirtK differs from wear.dirt_k"
    assert "max(dirtK, 0.3 * timeK)" in s, path + ": chalk differs from wear.chalk_k"
    assert YELLOW in s, path + ": yellowing differs from wear.YELLOW"


def check_levels():
    rows = {r["id"]: r for r in wear.table()}
    assert [r for r in rows] == ["L0", "L1", "L2", "L3", "L4"]
    assert rows["L0"]["time_k"] == 0 and rows["L0"]["dirt_k"] == 0, "a new boat carries no wear"
    assert rows["L1"]["time_k"] > 0.05 and rows["L1"]["dirt_k"] > 0.03, "a few months' use shows"
    assert rows["L3"]["dirt_k"] < rows["L2"]["dirt_k"], "a kept 30-year-old boat is cleaner than a club boat"
    assert rows["L3"]["time_k"] > rows["L2"]["time_k"], "but older"
    assert rows["L4"]["dirt_k"] > 0.85, "neglect is near the top"
    # unset age: both numbers are the livery's channel, as the old ageK was
    assert wear.time_k(-1, 0.5, 0.4) == 0.4 and wear.dirt_k(-1, 0.5, 0.4) == 0.4


def check_unset_unchanged():
    """A boat with no age (the player's and AI boats) looks as it did before the split."""
    for wx in (0.0, 0.3, 0.8):
        for up in (0.0, 1.0):
            before = wear.gelcoat((0.8, 0.8, 0.77), 0.22, 1.0, -1.0, 0.5, up=up, wear_x=wx, split=False)
            after = wear.gelcoat((0.8, 0.8, 0.77), 0.22, 1.0, -1.0, 0.5, up=up, wear_x=wx, split=True)
            assert all(abs(x - y) < 1e-9 for x, y in zip(before[0], after[0])) and abs(before[1] - after[1]) < 1e-9


if __name__ == "__main__":
    check_source("scripts/make_materials.py", "age", "care")
    check_source("scripts/import_j22_hero.py", "Age", "Care")
    assert BLOT in open(os.path.join(REPO, "scripts/make_materials.py")).read(), "chalk blotches differ from wear.BLOT"
    check_levels()
    check_unset_unchanged()
    print("wear formulas match: make_materials.py, import_j22_hero.py, wear.py")
