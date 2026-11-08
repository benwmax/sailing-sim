"""The boats' wear numbers in Python, the same formulas as the materials' HLSL (docs/texture-loop).

Bean's call (Nov 8 2026): one wear number (ageK) can't tell a few-months boat from a new one, and it gives a kept
30-year-old boat the chalk and stains of a half-neglected one. So the materials work out two numbers from the same E1 Age
(years) and Care (0 neglected .. 1 kept), with no new data slots:

  time_k  what the years do and care can't undo: fade, yellowing, crazing, dock rash. A quarter of it comes in the
          first year or two of use, the rest over decades.
  dirt_k  what care removes: chalk, grime, scum, slime, mildew, tea stains. It comes in the first months and scales
          with how little the boat is kept.

`scripts/make_materials.py` (BOAT_CODE) and `scripts/import_j22_hero.py` (DETAIL_CODE) carry the same lines; the
texture loop's swatch renders (render_swatch.py) call these, so a change here is a change there (tests: test_wear.py).
`age_k` is the old single number, kept so the loop can render "before".
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def levels():
    return json.load(open(os.path.join(HERE, "levels.json")))["levels"]


def saturate(x):
    return max(0.0, min(1.0, x))


def age_k(age, care, wear_x=0.0):
    """Before the split (boat fidelity 1): one number, 0 new .. 1 worn out."""
    return saturate(age / 20.0) * (1.0 - 0.6 * saturate(care)) if age >= 0.0 else wear_x


def time_k(age, care=1.0, wear_x=0.0):
    """care is ignored (the years come whatever the owner does); it is here so every wear function takes (age, care)."""
    if age < 0.0:
        return wear_x
    return saturate(0.25 * (1.0 - math.exp(-age / 0.75)) + 0.75 * (1.0 - math.exp(-age / 18.0)))


def dirt_k(age, care, wear_x=0.0):
    if age < 0.0:
        return wear_x
    return saturate((1.0 - math.exp(-age / 1.0)) * (0.15 + 0.85 * (1.0 - saturate(care))))


def chalk_k(age, care, wear_x=0.0):
    """Gelcoat oxidation: mostly dirt (compound and wax take it off), but a kept old hull never polishes back to new."""
    return max(dirt_k(age, care, wear_x), 0.3 * time_k(age, care, wear_x))


# Gelcoat yellowing with the years (white gelcoat only): the multiplier at time_k 1, per channel, linear.
YELLOW = (1.0, 0.965, 0.86)
# Round 2: chalk comes in blotches. ox scales by BLOT[0] + BLOT[1] * (a 40 cm value noise, 0..1) on a boat with an age.
BLOT = (0.55, 0.9)


def gelcoat(col, rough, coat, age, care, up=0.0, sun=1.0, wear_x=0.0, split=True, blot=None):
    """M_BoatSurface's gelcoat weathering for one linear RGB colour: returns (col, rough, coat).

    up: 0 a topside .. 1 a deck or cabin top facing the sky (the tops chalk first); sun: E1's sunF (0.6..1.4);
    blot: the 40 cm noise (0..1), scalar or array (None: no blotches, the mean look). up and blot may be numpy arrays,
    then the results are arrays (col as (..., 3)). split=False is the material before the texture loop (ageK)."""
    import numpy as np
    r, g, b = col
    if split:
        k = chalk_k(age, care, wear_x)
        t = time_k(age, care, wear_x)
    else:
        k = age_k(age, care, wear_x)
        t = 0.0
    up = np.asarray(up, dtype=float)
    ox = saturate(max(wear_x, k) * sun) * (0.55 + 0.45 * up)
    if split and blot is not None and age >= 0.0:
        ox = np.clip(ox * (BLOT[0] + BLOT[1] * np.asarray(blot, dtype=float)), 0.0, 1.0)
    ox = np.asarray(ox, dtype=float)
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    dark = saturate(1.0 - lum * 2.5)
    pale = np.array([(lum * 0.5 + c * 0.5) * 1.02 for c in (0.82, 0.80, 0.74)])
    deep = np.array([c * 1.25 + lum * 0.35 + 0.01 for c in (r, g, b)])
    chalk = pale + (deep - pale) * dark
    base = np.array([r, g, b], dtype=float)
    out = base + (chalk - base) * (0.4 * ox)[..., None]
    white = np.clip((out.min(-1) - 0.45) * 4.0, 0.0, 1.0)
    yk = t * white * saturate(sun) * (1.0 if age >= 0.0 else 0.0)
    out = out * (1.0 + (np.array(YELLOW) - 1.0) * np.asarray(yk)[..., None])
    rough = rough + (0.72 - rough) * ox
    coat = coat * (1.0 - 0.85 * ox)
    if out.ndim == 1:
        return tuple(float(x) for x in out), float(rough), float(coat)
    return out, rough, coat


def grime(age, care, wear_x=0.0, split=True):
    """How dirty a deck gets (the grime noise's weight)."""
    if not split:
        return saturate(0.15 + age / 18.0) * (1.0 - 0.65 * saturate(care)) if age >= 0.0 else 0.3 + 0.7 * wear_x
    return dirt_k(age, care, wear_x) if age >= 0.0 else 0.3 + 0.7 * wear_x


def table(split=True):
    rows = []
    for lv in levels():
        a, c = lv["age"], lv["care"]
        rows.append(dict(id=lv["id"], age=a, care=c, age_k=round(age_k(a, c), 3), time_k=round(time_k(a, c), 3),
                         dirt_k=round(dirt_k(a, c), 3), chalk_k=round(chalk_k(a, c), 3), grime=round(grime(a, c, split=split), 3)))
    return rows


if __name__ == "__main__":
    for row in table():
        print(row)
