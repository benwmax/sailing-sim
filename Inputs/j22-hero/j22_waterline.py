"""The lake waterline on the hero J/22's hull (texture loop, waterline surface): the scum line, the slime and the film on
the bottom paint, as Blender nodes. The numbers come from Tools/texloop/waterline/waterline.py, the same table the fleet
shader (scripts/make_materials.py BOAT_CODE) and the swatch renders use, so the hero and the fleet age alike.

Object space is metres with z = 0 at the design waterline and x forward. The style's `dirt` and `time` (0..1, the
texture loop's split) drive it; a style without them falls back to its preset's wear and care.
"""
import os
import sys

_TL = os.environ.get("J22H_TEXLOOP", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Tools", "texloop", "waterline"))
if _TL not in sys.path:
    sys.path.insert(0, _TL)
import waterline as wl  # noqa: E402


def wear_of(st):
    """(dirt, time) for a style: its own if it carries them, else Age and Care through the shared split, else (an old
    style with only the preset's wear and care) wear stands in for both as BOAT_CODE's unset-Age fallback does."""
    if "dirt" in st and "time" in st:
        return float(st["dirt"]), float(st["time"])
    sys.path.insert(0, os.path.join(_TL, ".."))
    import wear
    if "age" in st:
        return float(wear.dirt_k(st["age"], st.get("care", 1.0))), float(wear.time_k(st["age"], st.get("care", 1.0)))
    w, c = float(st.get("wear", 0.5)), float(st.get("care", 0.5))
    return max(0.0, min(1.0, w * (1.15 - c))), w


def _hex(c):
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in c)


def _ss(m, nt, v, lo, hi):
    """smoothstep(lo, hi, v); lo and hi may be numbers or sockets (hi < lo gives the falling edge)."""
    r = m._n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
    for i, e in ((1, lo), (2, hi)):
        if isinstance(e, (int, float)):
            r.inputs[i].default_value = e
        else:
            m._l(nt, e, r.inputs[i])
    m._l(nt, v, r.inputs[0])
    return r.outputs[0]


def _nz(m, nt, scale_xyz, w, detail=2, rough=0.5):
    """Noise in object space stretched per axis (scale = 1 / feature size in metres), 0..1 with the usual ~0.5 mean."""
    vec, _ = m._coords(nt, scale=scale_xyz)
    return m._noise4(nt, vec, 1.0, w, detail, rough)


def bottom(st, nt, z, paint, W):
    """Bottom paint (RGBA) with its time fade and the dirt's grey-olive film; mix it under the waterline as before."""
    import j22_materials as m
    dirt, time = wear_of(st)
    p = wl.params(dirt, time)
    faded = m._mix(nt, p["paint_fade"], paint, m._rgb("#C7C7C2"))
    blot = _nz(m, nt, (1 / 0.30, 1 / 0.30, 1 / 0.12), W + 41)
    film = m._math(nt, "MULTIPLY", m._math(nt, "ADD", 0.6, m._math(nt, "MULTIPLY", blot, 0.4)), p["film_k"])
    film = m._math(nt, "MULTIPLY", film, _ss(m, nt, z, 0.0, -0.01))
    return m._mix(nt, film, faded, m._rgb(_hex(wl.BOTTOM_FILM)))


def lake(st, nt, c, x, z, W):
    """Lay the scum line and the slime over the hull colour `c`. Returns (colour, cover); cover (0..1) is how much of
    the surface is stain or slime, for the roughness (both are matte, 0.8)."""
    import j22_materials as m
    dirt, time = wear_of(st)
    p = wl.params(dirt, time)
    if p["line_k"] <= 0.0:
        return c, 0.0
    h = p["line_h"] / 100.0
    # the top edge wanders with the wash: a slow swell along the hull plus a fine ragged edge
    wob = m._math(nt, "ADD", m._math(nt, "MULTIPLY", _nz(m, nt, (1 / 0.23, 0, 0), W + 31, 1), 0.6),
                  m._math(nt, "MULTIPLY", _nz(m, nt, (1 / 0.015, 0, 0), W + 32, 4, 0.6), 0.4))
    # Blender's noise sits near 0.5 (value noise spans 0..1): stretch it so the edge wanders as far as the swatches'
    wob = m._math(nt, "ADD", m._math(nt, "MULTIPLY", m._math(nt, "SUBTRACT", wob, 0.5), 2.4), 0.5, True)
    top = m._math(nt, "ADD", h, m._math(nt, "MULTIPLY", m._math(nt, "SUBTRACT", wob, 0.5), 0.02 * p["rag"]))
    fall_lo = m._math(nt, "SUBTRACT", top, 0.002 + 0.06 * h)
    line = m._math(nt, "MULTIPLY", _ss(m, nt, z, -0.006, -0.001), _ss(m, nt, z, top, fall_lo))
    # a tide mark along the top edge; streaky up and down and mottled, the noise entering about its middle (waterline.py)
    u = m._math(nt, "DIVIDE", z, m._math(nt, "MAXIMUM", top, 0.001), True)
    dens = m._math(nt, "ADD", 0.75 + 0.45 * p["line_clay"], m._math(nt, "MULTIPLY", _ss(m, nt, u, 0.6, 0.95), 0.35))
    streak = _nz(m, nt, (1 / 0.035, 1 / 0.035, 1 / 0.14), W + 33, 2)
    mott = _nz(m, nt, (1 / 0.05, 1 / 0.05, 1 / 0.025), W + 34, 2)
    tex = m._math(nt, "ADD", 1.0, m._math(nt, "ADD", m._math(nt, "MULTIPLY", m._math(nt, "SUBTRACT", streak, 0.5), 1.44 * (1.0 - 0.85 * p["line_clay"])),
                                         m._math(nt, "MULTIPLY", m._math(nt, "SUBTRACT", mott, 0.5), 0.96 * (1.0 - 0.85 * p["line_clay"]))))
    dt = m._math(nt, "MINIMUM", m._math(nt, "MAXIMUM", m._math(nt, "MULTIPLY", dens, tex), 0.0), 1.3)
    line = m._math(nt, "MULTIPLY", line, dt)
    stain = m._mix(nt, p["line_clay"], m._rgb(_hex(wl.LINE_GREY)), m._rgb(_hex(wl.LINE_CLAY)))
    k = m._math(nt, "MULTIPLY", line, p["line_k"], True)
    c = m._mix(nt, k, c, stain)
    cover = k
    if p["slime_k"] > 0.0:
        # smeared along the hull by the wash (14 x 3 cm), thickest at the line and thinning with depth
        blot = _nz(m, nt, (1 / 0.14, 1 / 0.14, 1 / 0.03), W + 35, 2)
        blot = m._math(nt, "ADD", m._math(nt, "MULTIPLY", m._math(nt, "SUBTRACT", blot, 0.5), 2.4), 0.5, True)
        fine = _nz(m, nt, (1 / 0.025, 1 / 0.025, 1 / 0.008), W + 36, 2)
        dp = m._math(nt, "DIVIDE", z, -p["slime_depth"] / 100.0, True)
        thin = m._math(nt, "POWER", m._math(nt, "SUBTRACT", 1.0, dp), 1.5)
        s = m._math(nt, "MULTIPLY", thin, _ss(m, nt, z, 0.002, -0.005))
        s = m._math(nt, "MULTIPLY", s, _ss(m, nt, blot, m._math(nt, "ADD", 0.3, m._math(nt, "MULTIPLY", dp, 0.25)), 0.65))
        s = m._math(nt, "MULTIPLY", s, m._math(nt, "ADD", 0.75, m._math(nt, "MULTIPLY", fine, 0.25)))
        s = m._math(nt, "MULTIPLY", s, p["slime_k"], True)
        c = m._mix(nt, s, c, m._rgb(_hex(wl.SLIME)))
        cover = m._math(nt, "ADD", cover, s, True)
    return c, cover
