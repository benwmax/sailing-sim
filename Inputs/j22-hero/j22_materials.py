"""Procedural PBR materials for the J/22 hero model (Cycles/EEVEE node trees), plus the sail textures drawn with PIL.

Every surface is built from noise and pattern nodes in the boat's object space, so the wear sits where it does on the
lesson boats: rain streaks under the sheer, a grey scum line at the lake waterline, grime in the non-skid, silvered
teak, scuffed anodising. bake_j22_hero.py bakes these to texture maps for Unreal.
"""
import math
import os

import bpy

TEX_DIR = os.environ.get("J22H_TEX", "/tmp/j22/hero/out/textures")
# Lettering (sail numbers, insignia, sailmaker, the bow registration): Saira Condensed Bold, SIL OFL 1.1, staged with the
# game's UI fonts. Never a system font: the glyphs ship as images and meshes (docs/licences/README.md item 1).
FONT = os.environ.get("J22H_FONT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Content", "UI",
                                                "Fonts", "SairaCondensed-Bold.ttf"))


def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m, nt, bsdf, out


def _n(nt, kind, **props):
    node = nt.nodes.new(kind)
    for k, v in props.items():
        if k.startswith("in_"):
            key = k[3:]
            idx = int(key) if key.isdigit() else key
            node.inputs[idx].default_value = v
        else:
            setattr(node, k, v)
    return node


def _l(nt, a, b):
    nt.links.new(a, b)


def _rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, 1.0)


def _coords(nt, scale=(1, 1, 1), rot=(0, 0, 0)):
    tc = _n(nt, "ShaderNodeTexCoord")
    mp = _n(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Rotation"].default_value = rot
    _l(nt, tc.outputs["Object"], mp.inputs["Vector"])
    return mp.outputs["Vector"], tc


def _ramp(nt, fac, stops):
    r = _n(nt, "ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) > 2:
        els.remove(els[-1])
    for i, (pos, col) in enumerate(stops):
        e = els[i] if i < 2 else els.new(pos)
        e.position = pos
        e.color = col if len(col) == 4 else (*col, 1)
    _l(nt, fac, r.inputs[0])
    return r


def _math(nt, op, a, b=None, clamp=False):
    m = _n(nt, "ShaderNodeMath", operation=op, use_clamp=clamp)
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            _l(nt, v, m.inputs[i])
    return m.outputs[0]


def _mix(nt, fac, a, b, blend="MIX"):
    m = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type=blend)
    for sock, v in ((m.inputs[0], fac), (m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            _l(nt, v, sock)
    return m.outputs[2]


def _xyz(nt, vec):
    s = _n(nt, "ShaderNodeSeparateXYZ")
    _l(nt, vec, s.inputs[0])
    return s.outputs


def _band(nt, v, lo, hi, soft):
    """1 inside [lo, hi] with soft edges."""
    a = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    a.inputs[1].default_value, a.inputs[2].default_value = lo - soft, lo + soft
    _l(nt, v, a.inputs[0])
    b = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    b.inputs[1].default_value, b.inputs[2].default_value = hi + soft, hi - soft
    _l(nt, v, b.inputs[0])
    return _math(nt, "MULTIPLY", a.outputs[0], b.outputs[0])


def _noise(nt, vec, scale, detail=6, rough=0.6, dist=0.0):
    n = _n(nt, "ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["Distortion"].default_value = dist
    _l(nt, vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def _bump(nt, bsdf, height, strength, dist=0.002):
    b = _n(nt, "ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    _l(nt, height, b.inputs["Height"])
    _l(nt, b.outputs[0], bsdf.inputs["Normal"])
    return b


def _noise4(nt, vec, scale, w, detail=6, rough=0.6):
    """Seeded 4D noise: the same pattern family, a different instance per boat."""
    n = _n(nt, "ShaderNodeTexNoise", noise_dimensions="4D")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["W"].default_value = w
    _l(nt, vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def _ao(nt, dist=0.08):
    a = _n(nt, "ShaderNodeAmbientOcclusion", samples=16)
    a.inputs["Distance"].default_value = dist
    return a.outputs["AO"]


def _edges(nt, dist=0.006):
    """Convex edges, 0.5 on flats rising toward 1 on sharp edges. Inside-AO rather than Pointiness: Pointiness follows
    the mesh's vertex density, so a big flat cap (the transom) came out as blotchy fake chips."""
    a = _n(nt, "ShaderNodeAmbientOcclusion", samples=8, inside=True, only_local=True)
    a.inputs["Distance"].default_value = dist
    return _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", a.outputs["AO"], 0.5))


def _rect(nt, x, z, cx, cz, w, h, soft=0.01):
    return _math(nt, "MULTIPLY", _band(nt, x, cx - w / 2, cx + w / 2, soft), _band(nt, z, cz - h / 2, cz + h / 2, soft))


def simple(name, hexcol, rough, metal=0.0, coat=0.0, spec=0.5):
    m, nt, bsdf, _ = _new(name)
    bsdf.inputs["Base Color"].default_value = _rgb(hexcol)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = _rgb(hexcol)
    return m


def gelcoat_hull(st):
    """Topsides, bottom and transom from the style: rain streaks, chalking, scum line, fender rub marks, colour-matched
    repairs that never quite match, chipped edges, grey bottom with lake slime."""
    h = st["hull"]
    W = st["seed"] * 0.137 % 100
    m, nt, bsdf, _ = _new("GelcoatHull")
    vec, tc = _coords(nt)
    x, y, z = _xyz(nt, vec)
    base = _rgb(h["gelcoat_hex"])
    svec, _ = _coords(nt, scale=(22, 22, 0.9))
    st_ = _noise4(nt, svec, 1.0, W, 3, 0.45)
    st_ = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", st_, 0.58 - 0.08 * h["streaks"], True), 4.0, True)
    fade = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    fade.inputs[1].default_value, fade.inputs[2].default_value = 0.10, 0.62
    _l(nt, z, fade.inputs[0])
    # streaks cluster (lesson photo IMG_9224: broad faint runs, not an even comb) and run hardest under the deck
    # fittings that shed dirty water: chainplates at the mast, jib-lead tracks, the stern cleats and scuppers
    cvec, _ = _coords(nt, scale=(1.0, 0.0, 0.0))
    cluster = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", _noise4(nt, cvec, 1.6, W + 21, 2, 0.5), 0.35, True), 2.4, True)
    st_ = _math(nt, "MULTIPLY", st_, _math(nt, "ADD", 0.25, _math(nt, "MULTIPLY", cluster, 0.75)))
    for i, (sx, sw) in enumerate(((1.0, 0.10), (-0.15, 0.14), (-2.95, 0.10), (-2.2, 0.08))):
        src = _band(nt, x, sx - sw, sx + sw, sw * 0.6)
        run = _math(nt, "GREATER_THAN", _noise4(nt, svec, 1.6, W + 30 + i, 2, 0.5), 0.45)
        st_ = _math(nt, "MAXIMUM", st_, _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", src, run), 0.9))
    streak = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", st_, fade.outputs[0]), 0.25 + 0.5 * h["streaks"], True)
    c = _mix(nt, streak, base, _rgb("#A8A293"))
    # a grey wash just under the hull-deck joint where the toe rail drips
    lip = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    lip.inputs[1].default_value, lip.inputs[2].default_value = 0.42, 0.66
    _l(nt, z, lip.inputs[0])
    c = _mix(nt, _math(nt, "MULTIPLY", lip.outputs[0], 0.10 + 0.25 * h["streaks"]), c, _rgb("#B4AE9F"))
    var = _noise4(nt, vec, 3.0, W + 3, 3, 0.5)
    c = _mix(nt, _math(nt, "MULTIPLY", var, 0.10 + 0.25 * h["chalk"]), c, _rgb("#DCD7CA"))
    for i, r in enumerate(h["repairs"]):
        mask = _math(nt, "MULTIPLY", _rect(nt, x, z, r["x"], r["z"], r["w"], r["h"], 0.015), 0.9)
        c = _mix(nt, mask, c, _rgb(h["gelcoat_hex"]) if False else tuple(min(1, max(0, v * (1 + r["tint"] * 6))) for v in base[:3]) + (1,))
    for i, fx in enumerate(h["fender_marks"]):
        smudge = _math(nt, "MULTIPLY", _rect(nt, x, z, fx, 0.38, 0.30, 0.10, 0.05), _noise4(nt, vec, 30, W + 10 + i, 4, 0.7))
        c = _mix(nt, _math(nt, "MULTIPLY", smudge, 0.6), c, _rgb("#5E5A52"))
    if h.get("boot_stripe_hex"):
        c = _mix(nt, _band(nt, z, 0.07, 0.095, 0.0015), c, _rgb(h["boot_stripe_hex"]))
    rag = _math(nt, "MULTIPLY", _noise4(nt, vec, 18.0, W + 5, 4, 0.6), 0.04)
    zz = _math(nt, "ADD", z, rag)
    scum = _band(nt, zz, 0.005, h["scum_height_m"], 0.012)
    c = _mix(nt, _math(nt, "MULTIPLY", scum, 0.25 + 0.65 * h["scum"]), c, _rgb("#7F7766"))
    # chipped edges at the sheer, transom corners and stem: pointiness picks the convex edges
    chips = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", _edges(nt), 0.53 - 0.02 * h["edge_chips"]),
                  _math(nt, "GREATER_THAN", _noise4(nt, vec, 40, W + 7, 5, 0.7), 0.62 - 0.1 * h["edge_chips"]))
    c = _mix(nt, chips, c, _rgb("#9C927E"))
    under = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    under.inputs[1].default_value, under.inputs[2].default_value = 0.01, -0.03
    _l(nt, z, under.inputs[0])
    bottom = _rgb(h["bottom_hex"])
    film = _mix(nt, _math(nt, "MULTIPLY", _noise4(nt, vec, 6.0, W + 9, 5, 0.6), h["bottom_slime"]), bottom, _rgb("#5F6648"))
    c = _mix(nt, under.outputs[0], c, film)
    _l(nt, c, bsdf.inputs["Base Color"])
    r = _math(nt, "ADD", 0.14, _math(nt, "MULTIPLY", var, 0.1 + 0.3 * h["chalk"]))
    r = _math(nt, "ADD", r, _math(nt, "MULTIPLY", under.outputs[0], 0.45))
    _l(nt, r, bsdf.inputs["Roughness"])
    bsdf.inputs["Coat Weight"].default_value = 0.3 * (1 - h["chalk"])
    bsdf.inputs["Coat Roughness"].default_value = 0.12
    _bump(nt, bsdf, _math(nt, "ADD", _noise(nt, vec, 1.2, 2, 0.4), _math(nt, "MULTIPLY", chips, -0.2)), 0.05, 0.01)
    m.diffuse_color = base
    m["detail"] = "gelcoat"
    return m


def deck_mould(st, name="Gelcoat", windows=False):
    """Deck, cabin and cockpit: smooth gelcoat on edges and walls, crosshatch non-skid on the flats, dirt settled in
    corners (ambient occlusion), polished wear paths where feet go, seeded stains."""
    d = st["deck"]
    W = st["seed"] * 0.211 % 100
    m, nt, bsdf, _ = _new(name)
    vec, tc = _coords(nt)
    x, y, z = _xyz(nt, vec)
    nx, ny, nz = _xyz(nt, tc.outputs["Normal"])
    flat = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    flat.inputs[1].default_value, flat.inputs[2].default_value = 0.84, 0.93
    _l(nt, nz, flat.inputs[0])
    w1v, _ = _coords(nt, rot=(0, 0, math.radians(45)))
    w2v, _ = _coords(nt, rot=(0, 0, math.radians(-45)))
    waves = []
    for wv in (w1v, w2v):
        w = _n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        w.inputs["Scale"].default_value = 170.0
        w.inputs["Distortion"].default_value = 0.6
        w.inputs["Detail"].default_value = 1.0
        _l(nt, wv, w.inputs["Vector"])
        waves.append(w.outputs["Fac"])
    hatch = _math(nt, "MULTIPLY", waves[0], waves[1])
    sand = _noise(nt, vec, 900.0, 2, 0.5)
    pattern = _math(nt, "ADD", _math(nt, "MULTIPLY", hatch, 0.7), _math(nt, "MULTIPLY", sand, 0.3))
    grime = _noise4(nt, vec, 2.2, W, 6, 0.65)
    corner = _math(nt, "SUBTRACT", 1.0, _ao(nt, 0.10))
    dirt = _math(nt, "ADD", _math(nt, "MULTIPLY", grime, 0.5 * d["grime"]), _math(nt, "MULTIPLY", corner, 1.6 * d["grime"]), True)
    # foot traffic: side decks beside the cockpit and the cabin top aft are polished and lighter
    path = _math(nt, "MULTIPLY", _band(nt, x, -2.6, 0.6, 0.4), _band(nt, _math(nt, "ABSOLUTE", y), 0.75, 1.05, 0.1))
    path = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", path, _noise4(nt, vec, 4, W + 2, 4, 0.6)), 1.6 * d["wear_paths"], True)
    gel = _mix(nt, _math(nt, "MULTIPLY", dirt, 0.5), _rgb("#F0EEE7"), _rgb("#B9B3A3"))
    ns = _mix(nt, dirt, _rgb(d["nonskid_hex"]), _rgb("#8C8068"))
    ns = _mix(nt, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, pattern), 0.35), ns, _rgb("#8E846D"))
    ns = _mix(nt, _math(nt, "MULTIPLY", path, 0.5), ns, _rgb("#E2D8C0"))
    # seeded stains: rust drips, a dark spill or two
    if d["stains"]:
        vor = _n(nt, "ShaderNodeTexVoronoi", voronoi_dimensions="4D")
        vor.inputs["Scale"].default_value = 3.0
        vor.inputs["W"].default_value = W + 11
        _l(nt, vec, vor.inputs["Vector"])
        spot = _math(nt, "LESS_THAN", vor.outputs["Distance"], 0.03 + 0.012 * d["stains"])
        spot = _math(nt, "MULTIPLY", spot, _noise4(nt, vec, 25, W + 12, 4, 0.6))
        ns = _mix(nt, _math(nt, "MULTIPLY", spot, 0.7), ns, _rgb("#6E5A44"))
    c = _mix(nt, flat.outputs[0], gel, ns)
    rough = _math(nt, "ADD", _math(nt, "MULTIPLY", flat.outputs[0], _math(nt, "SUBTRACT", 0.55, _math(nt, "MULTIPLY", path, 0.25))), 0.2)
    height = _math(nt, "MULTIPLY", pattern, _math(nt, "MULTIPLY", flat.outputs[0], _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", path, 0.6))))
    if windows:
        side = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        side.inputs[1].default_value, side.inputs[2].default_value = 0.35, 0.55
        _l(nt, _math(nt, "ABSOLUTE", ny), side.inputs[0])
        zb = _band(nt, z, 0.745, 0.835, 0.003)
        fwd = _math(nt, "SUBTRACT", 1.10, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", z, 0.745), 3.0))
        xb = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", x, -0.30), _math(nt, "LESS_THAN", x, fwd))
        win = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", side.outputs[0], zb), xb)
        c = _mix(nt, win, c, _rgb("#141619"))
        rough = _math(nt, "SUBTRACT", rough, _math(nt, "MULTIPLY", win, 0.18), True)
    _l(nt, c, bsdf.inputs["Base Color"])
    _l(nt, rough, bsdf.inputs["Roughness"])
    _bump(nt, bsdf, height, 0.6, 0.0015)
    m.diffuse_color = _rgb("#E8E4D8")
    m["detail"] = "nonskid_normal"
    return m


def teak(st, name, varnish=False):
    m, nt, bsdf, _ = _new(name)
    W = st["seed"] * 0.173 % 100
    vec, _ = _coords(nt, scale=(1, 14, 14))
    w = _n(nt, "ShaderNodeTexWave", wave_type="RINGS", rings_direction="X", wave_profile="SAW")
    w.inputs["Scale"].default_value = 6.0
    w.inputs["Distortion"].default_value = 4.0
    w.inputs["Detail"].default_value = 4.0
    _l(nt, vec, w.inputs["Vector"])
    grain = w.outputs["Fac"]
    vec2, _ = _coords(nt)
    fine = _noise4(nt, vec2, 60.0, W, 8, 0.7)
    if varnish:
        v = st["varnish"]
        wood = _mix(nt, grain, _rgb("#A4602C"), _rgb("#6B3514"))
        peel = _math(nt, "GREATER_THAN", _noise4(nt, vec2, 9, W + 4, 6, 0.7), 0.72 - 0.25 * v["peel"])
        bare = _mix(nt, grain, _rgb("#9C8F7E"), _rgb("#6E6456"))
        c = _mix(nt, peel, wood, bare)
        _l(nt, c, bsdf.inputs["Base Color"])
        coat = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, peel), v["gloss"])
        _l(nt, coat, bsdf.inputs["Coat Weight"])
        bsdf.inputs["Coat Roughness"].default_value = 0.06
        _l(nt, _math(nt, "ADD", 0.35, _math(nt, "MULTIPLY", peel, 0.45)), bsdf.inputs["Roughness"])
        _bump(nt, bsdf, _math(nt, "ADD", grain, _math(nt, "MULTIPLY", peel, 0.6)), 0.08, 0.001)
    else:
        state = st["teak"]["state"]
        hi, lo = {"silvered": ("#9A948A", "#5E584E"), "oiled": ("#9A6233", "#5A3416"), "bare": ("#B08A62", "#7A5C3C")}[state]
        c = _mix(nt, grain, _rgb(hi), _rgb(lo))
        c = _mix(nt, _math(nt, "MULTIPLY", fine, 0.5), c, _rgb("#B4AEA2" if state == "silvered" else "#B88A5E"))
        # dark weathering in grain and around fastener plugs, hand-polished paler patches
        c = _mix(nt, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, _ao(nt, 0.03)), 1.2 * st["teak"]["wear"]), c, _rgb("#3E3A33"))
        _l(nt, c, bsdf.inputs["Base Color"])
        _l(nt, _math(nt, "ADD", 0.62 if state == "silvered" else 0.45, _math(nt, "MULTIPLY", fine, 0.25)), bsdf.inputs["Roughness"])
        _bump(nt, bsdf, _math(nt, "ADD", _math(nt, "MULTIPLY", grain, 0.5), fine), 0.12 + 0.18 * st["teak"]["wear"], 0.0015)
    m.diffuse_color = _rgb("#8C8478" if not varnish else "#9A5A2A")
    m["detail"] = "teak" if not varnish else ""
    return m


def anodised(st, name="Aluminium", base="#C9CCCF"):
    m, nt, bsdf, _ = _new(name)
    W = st["seed"] * 0.311 % 100
    vec, _ = _coords(nt, scale=(2, 2, 40))
    brush = _noise(nt, vec, 30.0, 4, 0.5)
    vec2, _ = _coords(nt)
    wear = st["metal"]["anodise_wear"]
    scuff = _math(nt, "GREATER_THAN", _noise4(nt, vec2, 25.0, W, 6, 0.7), 0.70 - 0.08 * wear)
    edge = _math(nt, "GREATER_THAN", _edges(nt), 0.62 - 0.03 * wear)
    ox = _n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    ox.inputs[1].default_value, ox.inputs[2].default_value = 0.50, 0.75
    _l(nt, _noise4(nt, vec2, 3.0, W + 2, 6, 0.6), ox.inputs[0])
    oxid = _math(nt, "MULTIPLY", ox.outputs[0], wear * 0.6)     # soft chalky oxidation, not flakes
    c = _mix(nt, _math(nt, "MULTIPLY", scuff, 0.35), _rgb(base), _rgb("#9DA0A4"))
    c = _mix(nt, _math(nt, "MULTIPLY", edge, 0.22), c, _rgb("#E2E4E6"))
    c = _mix(nt, _math(nt, "MULTIPLY", oxid, 0.5), c, _rgb("#B5B2AA"))
    _l(nt, c, bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    _l(nt, _math(nt, "ADD", 0.26, _math(nt, "ADD", _math(nt, "MULTIPLY", brush, 0.15), _math(nt, "MULTIPLY", oxid, 0.3))), bsdf.inputs["Roughness"])
    bsdf.inputs["Anisotropic"].default_value = 0.4
    m.diffuse_color = _rgb(base)
    return m


def stainless(st, name="Stainless", base="#C8CACC", rough=0.22):
    """Stainless with tea-staining: brown freckles that gather in crevices."""
    m, nt, bsdf, _ = _new(name)
    W = st["seed"] * 0.19 % 100
    vec, _ = _coords(nt)
    stain = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", _noise4(nt, vec, 120, W, 4, 0.6), 0.66 - 0.12 * st["metal"]["tea_stain"]),
                  st["metal"]["tea_stain"])
    stain = _math(nt, "ADD", stain, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, _ao(nt, 0.01)), st["metal"]["tea_stain"]), True)
    c = _mix(nt, stain, _rgb(base), _rgb("#8A6A44"))
    _l(nt, c, bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    _l(nt, _math(nt, "ADD", rough, _math(nt, "MULTIPLY", stain, 0.4)), bsdf.inputs["Roughness"])
    m.diffuse_color = _rgb(base)
    return m


def rope(st, name, pair, fade):
    base, fleck = pair
    m, nt, bsdf, _ = _new(name)
    W = (st["seed"] + len(name)) * 0.07 % 100
    vec, _ = _coords(nt)
    braid = _n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL")
    braid.inputs["Scale"].default_value = 300.0
    _l(nt, vec, braid.inputs["Vector"])
    f = _math(nt, "GREATER_THAN", _noise4(nt, vec, 420.0, W, 2, 0.5), 0.52)
    c = _mix(nt, f, _rgb(base), _rgb(fleck))
    c = _mix(nt, fade * 0.45, c, _rgb("#C9C6BC"))                     # sun-faded
    c = _mix(nt, _math(nt, "MULTIPLY", _noise4(nt, vec, 8, W + 1, 4, 0.6), 0.35 * fade), c, _rgb("#6D665A"))   # dirt
    c = _mix(nt, _math(nt, "MULTIPLY", braid.outputs["Fac"], 0.25), c, _rgb("#555555"))
    _l(nt, c, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.78
    bsdf.inputs["Sheen Weight"].default_value = 0.5
    _bump(nt, bsdf, braid.outputs["Fac"], 0.6, 0.0008)
    m.diffuse_color = _rgb(base)
    return m


def sail(name, tex_path, bump_path, laminate=False):
    m, nt, bsdf, out = _new(name)
    uv = _n(nt, "ShaderNodeUVMap")
    img = _n(nt, "ShaderNodeTexImage")
    img.image = bpy.data.images.load(tex_path)
    _l(nt, uv.outputs[0], img.inputs[0])
    hb = _n(nt, "ShaderNodeTexImage")
    hb.image = bpy.data.images.load(bump_path)
    hb.image.colorspace_settings.name = "Non-Color"
    _l(nt, uv.outputs[0], hb.inputs[0])
    _l(nt, img.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.42 if laminate else 0.6
    bsdf.inputs["Sheen Weight"].default_value = 0.1 if laminate else 0.3
    _bump(nt, bsdf, hb.outputs["Color"], 0.35, 0.002)
    tr = _n(nt, "ShaderNodeBsdfTranslucent")
    _l(nt, img.outputs["Color"], tr.inputs["Color"])
    mix = _n(nt, "ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.12 if laminate else 0.28
    _l(nt, bsdf.outputs[0], mix.inputs[1])
    _l(nt, tr.outputs[0], mix.inputs[2])
    _l(nt, mix.outputs[0], out.inputs[0])
    m.diffuse_color = _rgb("#F2EFE6")
    return m


def acrylic(name):
    m, nt, bsdf, _ = _new(name)
    bsdf.inputs["Base Color"].default_value = _rgb("#2A2E33")
    bsdf.inputs["Roughness"].default_value = 0.04
    bsdf.inputs["Transmission Weight"].default_value = 0.35
    m.diffuse_color = _rgb("#2A2E33")
    return m


# ------------------------------------------------------------------ sail textures (PIL)

def _font(px):
    from PIL import ImageFont
    return ImageFont.truetype(FONT, px)


def draw_sail_textures(st, kind, out_dir, size=(2048, 4096)):
    """Colour and height maps for one sail from the style. UV u runs luff (0) to leech (1), v foot (0) to head (1).
    White Dacron: crosscut panels with double-stitched seams. Grey laminate: tri-radial panels with a visible scrim
    grid and taffeta. Both: tabling, corner patches, batten pockets, reef points, telltales, window, insignia,
    numbers and a sailmaker's mark; age adds yellowing, crinkles, mildew spots, stains and stitched repair patches."""
    import random as _r
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        # Blender's own Python has no Pillow (the PC's Blender 4.2): reuse the committed maps beside this script, which
        # the game's live cloth reads anyway (the club style's; a new style needs a Blender with Pillow).
        name = "Mainsail" if kind == "main" else "Jib"
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
        print(f"sail maps: no Pillow in this Blender, using the committed T_J22H_{name}_D/H")
        return os.path.join(here, f"T_J22H_{name}_D.png"), os.path.join(here, f"T_J22H_{name}_H.png")
    s = st["sails"]
    lam = s["cloth"] == "grey_laminate"
    rng = _r.Random(st["seed"] * 7 + (1 if kind == "main" else 2))
    Wd, Hd = size
    base = tuple(int(s["base_hex"][i:i + 2], 16) for i in (1, 3, 5))
    age = s["age"]
    if not lam:
        base = (base[0] - int(6 * age), base[1] - int(8 * age), base[2] - int(22 * age))     # Dacron yellows
    img = Image.new("RGB", (Wd, Hd), base)
    hgt = Image.new("L", (Wd, Hd), 128)
    d, h = ImageDraw.Draw(img), ImageDraw.Draw(hgt)
    seam = tuple(max(0, v - 30) for v in base)
    if lam:
        # tri-radial: panels radiating from head, tack and clew
        for cx, cy, n in ((0, 0, 7), (0, Hd, 5), (Wd, Hd, 6)):
            for k in range(1, n):
                ang = (math.pi / 2) * k / n
                ex = cx + (Wd * 1.6 * math.sin(ang) if cx == 0 else -Wd * 1.6 * math.sin(ang))
                ey = cy + (Hd * 0.6 * math.cos(ang) if cy == 0 else -Hd * 0.6 * math.cos(ang))
                d.line([cx, cy, ex, ey], fill=seam, width=4)
                h.line([cx, cy, ex, ey], fill=150, width=8)
        # scrim: a diamond grid of dark yarns under the film
        yarn = tuple(max(0, v - 45) for v in base)
        for k in range(-Hd, Wd + Hd, 64):
            d.line([k, 0, k + Hd // 2, Hd], fill=yarn, width=2)
            d.line([k, 0, k - Hd // 2, Hd], fill=yarn, width=2)
        for k in range(0, Hd, 180):
            d.line([0, k, Wd, k + 40], fill=yarn, width=2)
    else:
        panels = 10 if kind == "main" else 9
        for k in range(panels):
            y0, y1 = int(Hd * k / panels), int(Hd * (k + 1) / panels)
            sh = rng.randint(-4, 4)
            d.rectangle([0, Hd - y1, Wd, Hd - y0], fill=tuple(v + sh for v in base))
            d.rectangle([0, Hd - y1 - 3, Wd, Hd - y1 + 3], fill=seam)
            for off in (-7, 7):
                for xx in range(0, Wd, 10):   # zig-zag stitches
                    d.line([xx, Hd - y1 + off - 2, xx + 5, Hd - y1 + off + 2], fill=tuple(v - 40 for v in base), width=1)
            h.rectangle([0, Hd - y1 - 10, Wd, Hd - y1 + 10], fill=160)
    tab = tuple(max(0, v - 14) for v in base)
    for box_ in ([0, 0, 30, Hd], [Wd - 24, 0, Wd, Hd], [0, Hd - 28, Wd, Hd]):
        d.rectangle(box_, fill=tab)
        h.rectangle(box_, fill=170)
    for cx, cy, r in ((0, Hd, 520), (Wd, Hd, 480), (0, 0, 420 if kind == "main" else 300)):
        for k in range(6):
            bb = [cx - r + k * 40, cy - r + k * 40, cx + r - k * 40, cy + r - k * 40]
            d.pieslice(bb, 0, 360, fill=tuple(max(0, v - 10 - k) for v in base))
            h.pieslice(bb, 0, 360, fill=150 + 4 * k)
    if kind == "main":
        for k in range(1, 5):
            v = Hd * (1 - k / 5)
            L = int(Wd * (0.32 if k in (2, 3) else 0.22))
            d.rectangle([Wd - L, int(v) - 22, Wd, int(v) + 22], fill=tab)
            h.rectangle([Wd - L, int(v) - 22, Wd, int(v) + 22], fill=185)
            h.rectangle([Wd - L + 10, int(v) - 6, Wd - 10, int(v) + 6], fill=215)     # the batten inside
        rv = Hd - int(Hd * 0.13)
        for k in range(6):
            xx = int(Wd * (0.12 + 0.14 * k))
            d.ellipse([xx - 9, rv - 9, xx + 9, rv + 9], fill=(150, 150, 150))
            d.line([xx, rv + 9, xx + rng.randint(-8, 8), rv + 70], fill=(225, 225, 225), width=5)   # reef tie
        num = s["number"].split(" ")[1]
        insig = tuple(int(s["insignia_hex"][i:i + 2], 16) for i in (1, 3, 5))
        numc = tuple(int(s["number_hex"][i:i + 2], 16) for i in (1, 3, 5))
        if lam:
            numc = (20, 20, 22)
        d.text((int(Wd * 0.18), int(Hd * 0.22)), "J/22", fill=insig, font=_font(300))
        d.text((int(Wd * 0.10), int(Hd * 0.36)), num, fill=numc, font=_font(260))
        # vinyl numbers stand slightly proud
        h.text((int(Wd * 0.10), int(Hd * 0.36)), num, fill=140, font=_font(260))
        for k in range(1, 5):
            v = Hd * (1 - k / 5) + 140
            d.rectangle([Wd - 120, int(v) - 6, Wd - 10, int(v) + 6], fill=(200, 40, 30) if k % 2 else (30, 140, 60))
    else:
        d.rounded_rectangle([int(Wd * 0.25), int(Hd * 0.80), int(Wd * 0.65), int(Hd * 0.93)], 30, fill=(150, 156, 162), outline=tab, width=18)
        for k in range(1, 4):
            v = Hd * (1 - k / 4)
            d.rectangle([Wd - 160, int(v) - 18, Wd, int(v) + 18], fill=tab)
            h.rectangle([Wd - 160, int(v) - 18, Wd, int(v) + 18], fill=185)
    maker, mhex = s["maker"]
    mc = tuple(int(mhex[i:i + 2], 16) for i in (1, 3, 5))
    d.text((90, Hd - 430), maker, fill=mc, font=_font(84))
    d.rectangle([90, Hd - 330, 90 + 40 * len(maker), Hd - 322], fill=mc)
    # age: crinkles, mildew, stains, repair patches
    for _ in range(int(80 + 900 * age)):
        x0, y0 = rng.randint(0, Wd), rng.randint(0, Hd)
        x1, y1 = x0 + rng.randint(-260, 260), y0 + rng.randint(-80, 80)
        h.line([x0, y0, x1, y1], fill=rng.choice((110, 146)), width=rng.choice((2, 3, 4)))
        if not lam:
            d.line([x0, y0, x1, y1], fill=tuple(v - 6 for v in base), width=2)
    # mildew grows in clusters where the sail stays folded and damp: low along the foot and in the leech
    mil = Image.new("L", (Wd, Hd), 0)
    md = ImageDraw.Draw(mil)
    for _ in range(int(7 * age * (1 if not lam else 0.4))):
        cx = rng.randint(0, Wd) if rng.random() < 0.5 else rng.randint(int(Wd * 0.75), Wd)
        cy = rng.randint(int(Hd * 0.7), Hd) if rng.random() < 0.6 else rng.randint(0, Hd)
        spread = rng.randint(30, 110)
        for _ in range(rng.randint(30, 140)):
            x0, y0, r = int(rng.gauss(cx, spread)), int(rng.gauss(cy, spread * 0.7)), rng.choice((1, 1, 2, 2, 3))
            md.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=rng.randint(50, 120))
    mil = mil.filter(ImageFilter.GaussianBlur(0.8))
    img.paste((112, 116, 100), (0, 0), mil)
    for _ in range(s["stains"]):
        x0, y0, r = rng.randint(100, Wd - 100), rng.randint(200, Hd - 200), rng.randint(40, 160)
        st_ = Image.new("L", (Wd, Hd), 0)
        ImageDraw.Draw(st_).ellipse([x0 - r, y0 - r // 2, x0 + r, y0 + r // 2], fill=60)
        st_ = st_.filter(ImageFilter.GaussianBlur(30))
        img.paste((150, 135, 100), (0, 0), st_)
    for _ in range(s["patches"]):
        x0, y0 = rng.randint(200, Wd - 400), rng.randint(400, Hd - 600)
        pw, ph = rng.randint(120, 300), rng.randint(80, 220)
        pc = tuple(min(255, v + rng.randint(4, 12)) for v in base)
        d.rectangle([x0, y0, x0 + pw, y0 + ph], fill=pc, outline=tuple(v - 50 for v in base), width=3)
        h.rectangle([x0, y0, x0 + pw, y0 + ph], fill=165)
    hgt = hgt.filter(ImageFilter.GaussianBlur(1.5))
    cpath = os.path.join(out_dir, f"T_J22H_{'Mainsail' if kind == 'main' else 'Jib'}_D.png")
    hpath = os.path.join(out_dir, f"T_J22H_{'Mainsail' if kind == 'main' else 'Jib'}_H.png")
    img.save(cpath)
    hgt.save(hpath)
    return cpath, hpath


def build_all(st):
    from j22_style import rope_pair
    from j22_rope import rope_material, wire_material
    os.makedirs(TEX_DIR, exist_ok=True)
    lam = st["sails"]["cloth"] == "grey_laminate"
    fade = st["ropes"]["fade"]
    dirt = min(1.0, st["wear"] * (1.2 - st["care"]))
    mats = {
        "Gelcoat": deck_mould(st, "Gelcoat"),
        "GelcoatHull": gelcoat_hull(st),
        "CabinGelcoat": deck_mould(st, "CabinGelcoat"),      # real portlights since the interior pass
        "TeakWeathered": teak(st, "TeakWeathered"),
        "TeakVarnish": teak(st, "TeakVarnish", varnish=True),
        "Aluminium": anodised(st),
        "CastAlu": anodised(st, "CastAlu", "#B7BABD"),
        "Chrome": stainless(st, "Chrome", "#E4E6E8", 0.10),
        "Stainless": stainless(st),
        "Wire": wire_material("Wire", st["metal"]["tea_stain"] * 0.5),
        "Bronze": simple("Bronze", "#9C7B4A", 0.35, 1.0),
        "BlackPlastic": simple("BlackPlastic", "#151515", 0.45),
        "CamBase": simple("CamBase", "#2A2B2D", 0.5),
        "SheaveGrey": simple("SheaveGrey", "#3A3C3F", 0.4),
        "RedPlastic": simple("RedPlastic", "#8E1B17", 0.4),
        "WhitePlastic": simple("WhitePlastic", "#E7E5E0", 0.4),
        "OutboardBlack": simple("OutboardBlack", "#111214", 0.28, coat=0.6),
        "ExtensionBlack": simple("ExtensionBlack", "#1A1A1A", 0.6),
        "KeelLead": simple("KeelLead", st["hull"]["bottom_hex"], 0.6),
        "HatchAcrylic": acrylic("HatchAcrylic"),
        "DecalBlack": simple("DecalBlack", "#101010", 0.3),
        "RubRail": simple("RubRail", "#5A5853", 0.5),
        "RigTape": simple("RigTape", st["details"]["rig_tape_hex"], 0.55),
        "Whipping": simple("Whipping", "#1A1A1A", 0.6),
        "TelltaleRed": simple("TelltaleRed", "#C0261C", 0.6),
        "TelltaleGreen": simple("TelltaleGreen", "#1F8A3A", 0.6),
        "Sticker": simple("Sticker", st["hull"]["sticker_hex"], 0.3),
        # braided lines: Tools/rope textures with true arc-length UVs (j22_rope.rope_uv runs at the end of the build)
        "RopeJibPort": rope_material("RopeJibPort", st["ropes"]["jib_sheet_port"], fade, dirt, seed=st["seed"] + 1),
        "RopeJibStbd": rope_material("RopeJibStbd", st["ropes"]["jib_sheet_stbd"], fade, dirt, seed=st["seed"] + 2),
        "RopeMain": rope_material("RopeMain", st["ropes"]["mainsheet"], fade, dirt, seed=st["seed"] + 3),
        "RopeHalyard": rope_material("RopeHalyard", st["ropes"]["halyards"], fade * 0.6, dirt * 0.5, seed=st["seed"] + 4),
        "RopeVang": rope_material("RopeVang", st["ropes"]["vang"], fade, dirt, seed=st["seed"] + 5),
        "RopeBackstay": rope_material("RopeBackstay", st["ropes"]["backstay"], fade, dirt * 0.6, seed=st["seed"] + 6),
        "RopeMooring": rope_material("RopeMooring", "blue_solid", fade * 1.2, dirt * 1.3, kind="Braid16", seed=st["seed"] + 7),
    }
    # aliases used by older call sites
    mats["RopeRedWhite"] = mats["RopeMain"]
    mats["RopeBlue"] = mats["RopeHalyard"]
    mats["RopeGreenWhite"] = mats["RopeJibStbd"]
    # flat stand-in colours (viewport colour) for exports that cannot carry procedural nodes: the web GLB and
    # the hardware entries in materials.json
    def _mixhex(a, b, t):
        ca, cb = _rgb(a), _rgb(b)
        return tuple(ca[i] * (1 - t) + cb[i] * t for i in range(3))
    teak_hex = "#8F8B82" if st["teak"]["state"] == "silvered" else "#7E5230"
    flat = {"Aluminium": _rgb("#C9CCCF"), "CastAlu": _rgb("#B7BABD"), "Chrome": _rgb("#E4E6E8"),
            "Stainless": _rgb("#C8CACC"), "Wire": _rgb("#B9BCBF"), "TeakWeathered": _rgb(teak_hex),
            "TeakVarnish": _rgb("#7A4520"), "Gelcoat": _rgb(st["deck"]["nonskid_hex"]),
            "CabinGelcoat": _rgb(st["deck"]["nonskid_hex"]), "GelcoatHull": _rgb(st["hull"]["gelcoat_hex"])}
    for role, key in (("jib_sheet_port", "RopeJibPort"), ("jib_sheet_stbd", "RopeJibStbd"), ("mainsheet", "RopeMain"),
                      ("halyards", "RopeHalyard"), ("vang", "RopeVang"), ("backstay", "RopeBackstay")):
        a, b = rope_pair(st, role)
        flat[key] = _mixhex(a, b, 0.2)
    flat["RopeMooring"] = _rgb("#22468F")
    for k, c in flat.items():
        mats[k].diffuse_color = (c[0], c[1], c[2], 1.0)
    if os.environ.get("J22H_COILS_ONLY"):
        # Boat fidelity 4: a run that only dumps the coils (J22H_coils.json) needs no sail maps (nor Pillow in Blender).
        mats["SailMain"] = mats["SailJib"] = bpy.data.materials.new("SailStub")
        return mats
    mc, mh = draw_sail_textures(st, "main", TEX_DIR)
    jc, jh = draw_sail_textures(st, "jib", TEX_DIR)
    mats["SailMain"] = sail("SailMain", mc, mh, lam)
    mats["SailJib"] = sail("SailJib", jc, jh, lam)
    return mats
