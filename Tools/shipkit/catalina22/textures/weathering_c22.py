"""The Catalina 22's wear (docs/c22-9): how much of each kind of wear a level brings, and where on her it falls.

    import weathering_c22 as wc
    wc.amounts("gelcoat", "topsides", 6.0, 0.5)     # {"gloss": 0.6, "chalk": 0.5, ...}, no Blender needed
    wc.dress("L2")                                   # in Blender, on a built c22.blend: finish + wear on every slot
    wc.apply_level("L4")                             # then any level (or (age, care)) without dressing again

    blender -b -P weathering_c22.py -- <c22.blend> <out.blend> [--level L2]     # dress a build and save it

The texture loop's five levels (Tools/texloop/levels.json) are fixed points of E1's Age (years) and Care (0 left to rot
.. 1 kept). The loop's two numbers (Tools/texloop/wear.py) split them into what the years do whatever the owner does
(time_k: fade, yellowing, crazing, the grain worn proud) and what care takes away (dirt_k: chalk, grime, slime, rust,
mildew). amounts() turns those into each surface's own terms, 0 to 1, with the reasons in its comments, the same way
Bluebonnet's slice 11 does (Tools/shipkit/jclass/weathering.py, whose node helpers this reuses). She lives on Lake Ray
Hubbard: fresh water, so rust, tea staining and growth come at the card's 'water' rate (a third of salt water's) and
there are no barnacles; the lake's clay line comes instead.

dress() gives each material the build made (flat slot colours, build_c22.SLOT_RGB) its new finish from the cards
(textures_c22.json 'finish': the game library's values where it has the slot) and builds the wear in its nodes, each
term a Value node named "wear:<surface>.<term>" that apply_level() sets, so one dressed .blend renders every level.
The hull is one material (GelcoatHull) from keel to sheer: below her paint line it takes the bottom's paint and wear.

Everything is in metres in the boat's frame (every C22 part is built in place: object = world, X forward, Y to port,
Z up from the design waterline), and the detail maps tile at their real size and fade with the camera's distance as the
game's do. The terms are kept to what a pixel shader can do (noise, streaks, height, which way a face looks, the
camera's distance, crevices: ambient occlusion here, a baked cavity in the game), so the game's twin can follow.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
sys.path.insert(0, os.path.join(REPO, "Tools", "shipkit", "jclass"))
import wear as loop  # noqa: E402
import weathering as JW  # noqa: E402  (Bluebonnet's: the node helpers W, Shader, runs, noise_sd)

CARDS = json.load(open(os.path.join(HERE, "textures_c22.json")))
SHARED_META = json.load(open(os.path.join(REPO, "Inputs", "boat-detail", "detail_textures.json")))
OWN_DIR = os.path.join(REPO, "Inputs", "c22-detail")
LEVELS = {lv["id"]: lv for lv in loop.levels()}
RATE = CARDS["water"]["rate"]          # fresh water: rust, tea and growth at a third of salt water's
PAINT_LINE = 0.04                      # the bottom paint's top, metres over the design waterline (she floats a touch light)

sat, ramp, refreshed = JW.sat, JW.ramp, JW.refreshed


def renewed_age(age, care, every):
    """How old something a kept boat renews is: on average half its life `every` years at full care, longer as
    care lapses; never older than the boat."""
    return min(age, every / max(care, 0.05))


def PATINA(age):
    """What no care takes off an old boat: the moulding's corners dirty for good, the paths worn, the edges handled.
    It follows age alone, so a kept thirty-year-old boat never reads as new."""
    return ramp(age, 8.0, 25.0)


def amounts(surface, kind, age, care):
    """Each wear term, 0 to 1, for one surface and kind at E1's Age (years) and Care (0..1). As Bluebonnet's:
    a first season's marks go as the square root of dirt_k (which is near its first-year value by then), times
    `fresh` where a kept boat's routine takes them away again; what neglect alone does (rust, flaking, rot, mildew)
    starts past a threshold of dirt_k a kept boat never reaches; what the years do follows time_k."""
    t, d = loop.time_k(age, care), loop.dirt_k(age, care)
    young = 1.0 - math.exp(-age / 0.4)
    fresh = 1.0 - 0.85 * refreshed(age, care)
    first = math.sqrt(d) * fresh
    if surface == "gelcoat":
        if kind == "liner":                                       # inside: no sun, no rain, hands and damp
            return {"gloss": sat(0.4 * first + 0.15 * t), "chalk": 0.25 * max(d * fresh, 0.3 * t), "yellow": 0.9 * t,
                    "craze": 0.4 * ramp(t, 0.3, 0.9), "grime": sat(1.2 * first), "mildew": ramp(d, 0.6, 0.95),
                    "patina": PATINA(age)}
        a = {"gloss": sat(0.8 * first + 0.2 * t),                 # the shine goes; compounded and waxed it comes back
             "chalk": loop.chalk_k(age, care) * (1.0 if kind == "topsides" else 0.9) * (0.5 + 0.5 * fresh),
             "yellow": t,                                         # the sun's yellowing: kept or not
             "craze": ramp(t, 0.3, 0.9) * (1.0 - 0.3 * care),     # spider cracks where the moulding flexes
             "streak": ramp(d, 0.1, 0.8) * fresh,                 # black runs under fittings and ports: washed off
             "scuff": sat(1.4 * first + 0.35 * t),                # dock rash: buffed, but the deep ones stay
             "dirt": ramp(d, 0.2, 0.9) * fresh,                   # a grey-brown film of dust and pollen, washed off
             "mildew": ramp(d, 0.55, 0.95),                       # grey-green on the decks' flats, left alone
             "patina": PATINA(age)}
        if kind == "topsides":
            a.update(clay=sat(1.8 * first),                       # the lake's tan line within a season
                     slime=RATE * 3.0 * ramp(d, 0.3, 0.9))        # then green-brown slime (fresh water: slower)
        return a
    if surface == "nonskid":
        return {"dirt": sat(1.3 * first), "chalk": max(d * fresh, 0.3 * t) * 0.8,
                "worn": t,                                        # the peaks worn smooth where feet go, the colour
                "faded": t,                                       # faded pale by the sun
                "mildew": ramp(d, 0.4, 0.9), "stain": ramp(d, 0.3, 0.9), "patina": PATINA(age)}
    if surface == "bottom":
        paint = renewed_age(age, care, 1.5)                       # a kept boat is repainted every two years or so
        pd = loop.dirt_k(paint, care)
        a = {"chalk": sat(1.0 - math.exp(-paint / 1.5)),          # ablative paint chalks and pales as it works
             "film": sat(1.6 * math.sqrt(pd)) * fresh,            # the lake's clay film, scrubbed at each haul-out
             "slime": 3.0 * RATE * ramp(d, 0.25, 0.85),
             "bare": ramp(d, 0.5, 0.95)}                          # worn through to primer and gelcoat
        if kind == "iron":
            a.update(rust=ramp(d, 0.3, 0.9),                      # the cast iron rusts where the paint fails, even fresh
                     blister=ramp(d, 0.55, 0.95))
        return a
    if surface == "teak":
        if kind == "varnish":                                     # the laminated tiller
            return {"amber": t, "dull": sat(0.8 * first), "fail": ramp(d, 0.45, 0.9), "stain": d ** 2}
        oil = care ** 3 * ramp(age, 0.5, 2.0)                     # a kept boat re-oils her teak each spring; half
        return {"silver": sat(7.0 * t) * (1.0 - 0.9 * oil),      # bare teak greys within a season
                "oiled": oil * sat(3.0 * t),                      # kept, hardly; oil darkens it a little more each year
                "dark": d ** 2,                                   # grime and mildew in the soft grain: neglect's
                "checks": t * (1.0 - 0.7 * care)}
    if surface == "canvas":
        own = renewed_age(age, care, 4.0)                         # renewed about every eight years on a kept boat
        ct, cd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"fade": sat(1.2 * ct), "dirt": sat(1.2 * math.sqrt(cd)) * (1.0 - 0.6 * refreshed(age, care)) * (0.6 + 0.6 * cd),
                "mildew": ramp(cd, 0.25, 0.85), "rot": ramp(cd, 0.6, 0.95) * ramp(own, 4.0, 12.0)}
    if surface == "vinyl":
        if kind == "rubrail":
            return {"chalk": max(d * fresh, 0.3 * t), "scuff": sat(1.4 * first + 0.4 * t), "grime": ramp(d, 0.2, 0.8)}
        return {"yellow": 0.85 * t,                               # headliners are seldom renewed
                "stain": sat(ramp(d, 0.2, 0.8) + 0.25 * t * (1.0 - care)),   # leaks: fixed on a kept boat, the old
                "grime": sat(1.2 * first),                        # stain stays faintly
                "mildew": ramp(d, 0.6, 0.95)}
    if surface == "sole":
        return {"amber": t, "worn": sat(1.2 * first + 0.3 * ramp(d, 0.3, 0.9)),
                "stain": d ** 1.4, "grime": sat(1.1 * first), "rot": ramp(d, 0.6, 0.95), "patina": PATINA(age)}
    if surface == "veneer":
        oil = care ** 2 * ramp(age, 0.5, 2.0)
        return {"dry": sat(2.0 * t) * (1.0 - 0.9 * oil) * (0.4 + 0.6 * (1.0 - care)),
                "oiled": oil * sat(2.0 * t), "hands": sat(1.2 * first), "water": ramp(d, 0.25, 0.9),
                "mildew": ramp(d, 0.65, 0.95), "patina": PATINA(age)}
    if surface == "fabric":
        own = renewed_age(age, care, 3.0) if kind == "cushion" else renewed_age(age, care, 5.0)
        ft = loop.time_k(own, care)
        a = {"fade": sat(1.3 * ft) if kind == "curtain" else sat(1.1 * ft) * (0.45 + 0.55 * (1.0 - care)), "stain": d ** 1.5,
             "mildew": ramp(d, 0.6, 0.95)}
        a["worn"] = sat(1.1 * first + 0.6 * ft) if kind == "cushion" else 0.0
        return a
    if surface == "plastic":
        if kind == "white":
            return {"yellow": t, "scuff": sat(1.2 * first + 0.3 * t), "grime": ramp(d, 0.15, 0.85)}
        return {"bloom": sat(1.6 * t) * (1.0 - 0.5 * care) + 0.4 * d, "grime": ramp(d, 0.2, 0.85)}
    if surface == "metal":
        if kind == "stainless":
            return {"dull": sat(0.6 * first + 0.2 * t), "tea": RATE * 2.0 * ramp(d, 0.1, 0.7),
                    "rust": RATE * 2.0 * ramp(d, 0.6, 0.95)}
        if kind == "aluminium":
            return {"dull": sat(2.5 * t), "oxide": ramp(d, 0.25, 0.85), "grime": ramp(d, 0.1, 0.8) * fresh}
        return {"chalk": max(d * fresh, 0.3 * t), "flake": ramp(d, 0.5, 0.9), "grime": ramp(d, 0.15, 0.8) * fresh}
    if surface == "acrylic":
        return {"haze": sat(1.3 * t) * (1.0 - 0.5 * care) + 0.4 * d, "craze": ramp(t, 0.35, 0.9) * (1.0 - 0.4 * care),
                "grime": sat(1.2 * first) * (0.5 + 0.5 * (1.0 - care))}
    raise KeyError(surface)


def level_amounts(level):
    lv = LEVELS[level]
    out = {}
    for s, card in CARDS["surfaces"].items():
        for k in card["kinds"]:
            out[f"{s}.{k}"] = {term: round(v, 3) for term, v in amounts(s, k, lv["age"], lv["care"]).items()}
    return out


def material_index():
    """{material name: (surface, kind)} from the cards."""
    out = {}
    for s, card in CARDS["surfaces"].items():
        for k, names in card["kinds"].items():
            for n in names:
                if n in out:
                    raise SystemExit(f"textures_c22.json: {n} is in two cards ({out[n]} and {(s, k)})")
                out[n] = (s, k)
    return out


def coverage(material_names):
    """The materials the build uses that no card or 'unweathered' entry covers (must be empty), and the card entries
    the build does not use (reported: a slot the build may use later, like PaintedAluminium)."""
    idx = material_index()
    un = set(CARDS["unweathered"])
    names = set(material_names)
    return sorted(names - set(idx) - un), sorted((set(idx) | un) - names)


# ================================================================================================ Blender
_lin = JW._lin
# what each wear brings, sRGB 0-255 (the renders'; the game's twin uses the same where its library has them)
RUST, RUST_DARK, MILDEW, STAIN, GRIME = JW.RUST, JW.RUST_DARK, JW.MILDEW, JW.STAIN, JW.GRIME
GREY_WOOD, OLD_VARNISH = JW.GREY_WOOD, JW.OLD_VARNISH
SILVER = (120, 118, 112)              # weathered teak, held to the CC0 board scans (wood_planks_grey)
# the game's lake waterline (BOAT_CODE, texture loop: waterline): linear
CLAY_LIN = (0.171, 0.119, 0.04)
CLAY_GREY_LIN = (0.179, 0.171, 0.147)
SLIME_LIN = (0.073, 0.089, 0.025)
FILM_LIN = (0.171, 0.187, 0.133)
CHALK_LIN = (0.80, 0.785, 0.735)      # the game's oxidised white gelcoat (Tools/texloop/wear.py gelcoat's pale)
LEAK = (156, 118, 70)                 # a headliner's leak stain: tannin and rust from the deck's core and fastenings
HOLLY = (226, 214, 180)
HONEY = (206, 168, 104)
PRIMER = (150, 150, 146)
OXIDE = JW.OXIDE
TEA = (150, 98, 58)


def map_path(name):
    if name in CARDS["maps"]["own"]:
        return os.path.join(OWN_DIR, f"T_C22_{name}_M.png")
    return os.path.join(REPO, "Inputs", "boat-detail", f"T_Detail_{name}_M.png")


def tile_of(name):
    own = CARDS["maps"]["own"].get(name)
    if own:
        return (own["tile_mm"][0] / 1000.0, own["tile_mm"][1] / 1000.0)
    return tuple(SHARED_META[name]["tile_m"])


def fade_of(name):
    own = CARDS["maps"]["own"].get(name)
    return tuple(own["fade_m"]) if own else tuple(SHARED_META.get(name, {}).get("fade_m", (1.0, 4.0)))


class CW(JW.W):
    """Bluebonnet's node helpers, with her maps and her terms named by surface ("wear:<surface>.<term>"), so a
    material can carry two surfaces' wear (the hull: gelcoat above the paint line, the bottom's below)."""

    def __init__(self, mt, surface, kind):
        super().__init__(mt, surface, kind)
        self.prefix = surface

    def term(self, name):
        key = f"{self.prefix}.{name}"
        if key not in self.terms:
            n = self.N.new("ShaderNodeValue")
            n.name = n.label = "wear:" + key
            self.terms[key] = n.outputs[0]
            self.mt["c22_terms"] = sorted(set(self.mt.get("c22_terms", [])) | {key})
        return self.terms[key]

    def image(self, name, vec, tile_m, box=True):
        old = JW.map_path
        JW.map_path = map_path              # W.image looks the file up through the module's map_path
        try:
            return super().image(name, vec, tile_m, box=box)
        finally:
            JW.map_path = old

    def ao(self, dist):
        """Bluebonnet's crevice term with twice the samples: on the C22's broad mouldings 8 left a grain."""
        n = self.N.new("ShaderNodeAmbientOcclusion")
        n.samples = 16
        n.only_local = True
        n.inputs["Distance"].default_value = dist
        return n.outputs["AO"]

    def voronoi_edge(self, vec, cell_m):
        """1 on the edges of a Voronoi cell network about cell_m across (crazing), falling off within a tenth."""
        vo = self.N.new("ShaderNodeTexVoronoi")
        vo.feature = "DISTANCE_TO_EDGE"
        self.L.new(vec, vo.inputs["Vector"])
        vo.inputs["Scale"].default_value = 1.0 / cell_m
        return self.m("SUBTRACT", 1.0, self.smooth(vo.outputs["Distance"], 0.0, 0.06))

    def lin(self, c):
        return self.rgb(c)


def mildew(w, pos, amount, seed, extra=None):
    """Mildew: sparse dark dots a few millimetres across, thickest where the damp lies (`extra`: the corners, low down,
    by a leak) and thinning out over a soft drift; past a metre or so they fade into their own mean, a faint grey
    (dots any further off only alias into grain, and dense dot fields read as leopard print)."""
    drift = w.mul(w.blot(pos, 0.5, seed + 0.5, detail=1.0), amount, 0.45)
    if extra is not None:
        drift = w.add(drift, w.mul(extra, amount))
    drift = w.sat(drift)
    share = w.mul(drift, 0.18)
    specks = w.patches(pos, 0.005, share, seed=seed, soft=0.3, detail=1.0)          # fuzzy, not pepper
    return w.add(w.mul(w.lerp(w.mul(share, 0.6), specks, w.fade(0.4, 1.2)), 0.6), w.mul(drift, 0.15))


def detail(w, sh, name, vec, amp_m=None, box=True):
    r, g, b = w.image(name, vec, tile_of(name), box=box)
    if amp_m is not None:
        sh.bump(w.mul(w.m("SUBTRACT", b, 0.5), amp_m, w.fade(*fade_of(name))))
    return r, g, b


def finish(m):
    """The slot's new finish (the card's 'finish'): a Principled BSDF in place of the build's flat colour."""
    f = CARDS["finish"][m.name]
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(pb.outputs[0], out.inputs[0])
    pb.inputs["Base Color"].default_value = (*f["rgb"], 1.0)
    pb.inputs["Roughness"].default_value = f.get("rough", 0.5)
    pb.inputs["Metallic"].default_value = f.get("metal", 0.0)
    pb.inputs["Coat Weight"].default_value = f.get("coat", 0.0)
    pb.inputs["Coat Roughness"].default_value = 0.05
    m.diffuse_color = (*f["rgb"], 1.0)


def under(w, sh, mask, fn, kind, base=None):
    """Runs a dresser only where `mask` is 1: what it does to the colour, roughness, metal, coat and bump is blended
    in by the mask (base: (linear rgb, rough, coat) to start from there first, the hull's bottom paint)."""
    c0, r0, m0, k0, nh = sh.col, sh.rough, sh.metal, sh.coat, len(sh.heights)
    if base:
        sh.col, sh.rough, sh.coat = w.lin(base[0]), w.val(base[1]), w.val(base[2])
    fn(w, sh, kind)
    sh.col = w.mix(c0, sh.col, mask)
    sh.rough, sh.metal, sh.coat = (w.lerp(a, b, mask) for a, b in ((r0, sh.rough), (m0, sh.metal), (k0, sh.coat)))
    sh.heights[nh:] = [w.mul(h, mask) for h in sh.heights[nh:]]


# ------------------------------------------------------------------------------------------------ the surfaces
def gelcoat(w, sh, kind):
    pos, z, up = w.obj(), w.wz(), w.sat(w.up())
    out = kind != "liner"
    _, g, _ = detail(w, sh, "Gelcoat", pos)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", g, 0.5), 0.06))
    sh.rough = w.lerp(sh.rough, 0.55, w.term("gloss"))
    sh.coat = w.lerp(sh.coat, 0.05, w.term("gloss"))
    # chalk: the pigment's surface oxidised to a flat, faintly yellow-grey powder, most on what faces the sky and
    # washed down the topsides in long soft streaks (the game's gelcoat chalk, wear.gelcoat)
    washed = w.blot(pos, 0.3, 2.0, detail=1.0, stretch=(1.0, 1.0, 5.0))
    blot = w.blot(pos, 0.4, 3.0, detail=1.0)
    ch = w.mul(w.term("chalk"), w.add(0.7, w.mul(washed, 0.15), w.mul(blot, 0.15)), w.add(0.7, w.mul(up, 0.3)))
    sh.col = w.mix(sh.col, w.lin(CHALK_LIN), w.mul(w.sat(ch), 0.6))
    sh.rough = w.lerp(sh.rough, 0.72, w.sat(ch))
    sh.coat = w.lerp(sh.coat, 0.0, w.sat(ch))
    old = (1.0, 0.93, 0.76) if out else (1.0, 0.9, 0.7)   # thirty years: a cream (inside, the resin's own amber)
    sh.col = w.mix(sh.col, w.scale(sh.col, old), w.mul(w.term("yellow"), w.add(0.6, w.mul(up, 0.4)) if out else 1.0))
    # spider cracks: star-shaped networks of fine cracks where the moulding flexes, round the fittings' bases (their
    # crevices) and on the trunk's and cockpit's corners, dirt dark in the cracks
    near = w.sat(w.add(w.crevice(0.08, 0.45, 0.95), w.mul(w.edge(0.008), 0.7)))
    craze = w.mul(w.voronoi_edge(pos, 0.012), w.patches(pos, 0.12, 0.3, seed=5.0, detail=2.0, soft=0.2),
                  w.add(0.15, near), w.term("craze"), w.fade(1.0, 5.0))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.62), w.sat(w.mul(craze, 1.4)))
    # old dirt in the moulding's corners and joints that no polish reaches
    pat = w.mul(w.term("patina"), w.sat(w.add(w.mul(w.crevice(0.12, 0.4, 0.95), 1.2), w.mul(w.edge(0.01), 0.4))))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.78, 0.75, 0.68)), w.mul(pat, 0.55))
    if not out:
        # hand grime round the companionway and the handholds, mildew specks in the corners
        # (by place, not by crevice: the ambient occlusion's own noise would read as grime on these broad faces)
        x = w.sep(pos)[0]
        aft = w.m("SUBTRACT", 1.0, w.smooth(x, -0.9, -0.2))           # the companionway's end, where hands go
        hands = w.mul(w.term("grime"), w.add(w.mul(aft, 0.6), 0.15), w.add(0.3, w.mul(w.blot(pos, 0.3, 7.0), 0.7)))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.72, 0.68, 0.6)), w.sat(hands))
        low = w.m("SUBTRACT", 1.0, w.smooth(z, -0.1, 0.4))           # damp gathers low, over the bilge
        sh.col = w.mix(sh.col, MILDEW, mildew(w, pos, w.term("mildew"), 9.0, extra=low))
        return
    # black streaks: rain carries the grime off the deck and the fittings down every wall in soft runs, under the
    # stanchions, cleats and ports most, the topsides from the toe rail
    wall = w.m("SUBTRACT", 1.0, w.smooth(w.m("ABSOLUTE", w.up()), 0.5, 0.85))
    src = w.add(0.08, w.mul(w.crevice(0.3, 0.45, 0.97), 1.2))
    runs = w.patches(pos, 0.07, w.mul(w.term("streak"), 0.3), seed=11.0, detail=1.0, soft=0.5,
                     stretch=(1.0, 1.0, 6.0))
    blk = w.sat(w.mul(runs, src, wall))
    # the dirt film: dust and pollen settle on the flats, rain spreads it thinner down the walls; left alone the
    # flats go grey-green with mildew where water lies
    film = w.mul(w.term("dirt"), w.add(0.45, w.mul(up, 0.55)), w.add(0.75, w.mul(w.blot(pos, 0.8, 12.0, detail=1.0), 0.25)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.78, 0.75, 0.68)), w.sat(film))
    mg = w.mul(w.term("mildew"), up, w.add(0.45, w.mul(w.crevice(0.15, 0.4, 0.95), 0.8), w.mul(w.blot(pos, 1.0, 14.0, detail=1.0), 0.15)))
    sh.col = w.mix(sh.col, (104, 108, 92), w.mul(w.sat(mg), 0.55))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.5, 0.49, 0.46)), w.mul(blk, 0.75))
    if kind == "topsides":
        # dock rash: grey smudges along the topsides' fender band
        band = w.mul(w.smooth(z, 0.25, 0.4), w.m("SUBTRACT", 1.0, w.smooth(z, 0.7, 0.85)), wall)
        sc = w.mul(w.patches(pos, 0.07, w.mul(w.term("scuff"), 0.2), seed=13.0, detail=2.0, soft=0.25,
                             stretch=(6.0, 6.0, 1.0)), band)
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.72), w.mul(sc, 0.8))
        # the lake's line: a tan clay band just over the paint line, ragged along its top and darkest at its top
        # (the tide mark of the lake's level), then green-brown slime hanging from it into the water
        xs = w.comb(w.sep(pos)[0], 0.0, 0.0)
        wob = w.add(w.mul(w.m("SUBTRACT", w.noise(xs, 0.5, 15.0, detail=1.0), 0.5), 0.05),
                    w.mul(w.m("SUBTRACT", w.noise(xs, 0.12, 16.0, detail=1.0), 0.5), 0.04))   # wavelets' ragged edge
        bow = w.smooth(w.sep(pos)[0], 0.8, 2.6)                          # the bow wave lifts it forward
        top = w.add(PAINT_LINE + 0.03, w.mul(w.term("clay"), w.add(0.05, w.mul(bow, 0.05))), wob)
        feather = w.mul(w.noise(pos, 0.1, 18.0, detail=1.0), 0.02)        # splash marks feathering up
        line = w.mul(w.smooth(z, PAINT_LINE - 0.01, PAINT_LINE + 0.005), w.m("SUBTRACT", 1.0, w.smooth(z, w.m(
            "SUBTRACT", top, 0.03), w.add(top, feather))))
        clay = w.mul(line, w.term("clay"), w.add(0.85, w.mul(w.blot(pos, 0.8, 17.0, detail=1.0, stretch=(4.0, 4.0, 1.0)), 0.15)))
        sh.col = w.mix(sh.col, w.mix(w.lin(CLAY_GREY_LIN), w.lin(CLAY_LIN), 0.9), w.mul(w.sat(clay), 0.95))
        sl = w.mul(w.smooth(z, PAINT_LINE - 0.02, PAINT_LINE + 0.01), w.m("SUBTRACT", 1.0, w.smooth(
            z, PAINT_LINE + 0.02, PAINT_LINE + 0.06)), w.term("slime"),
            w.add(0.75, w.mul(w.blot(pos, 0.5, 19.0, detail=1.0, stretch=(6.0, 6.0, 1.0)), 0.25)))    # a band, not patches
        sh.col = w.mix(sh.col, w.lin(SLIME_LIN), w.mul(w.sat(sl), 0.85))
        wet = w.sat(w.add(clay, sl))
        sh.rough = w.lerp(sh.rough, 0.85, wet)
        sh.coat = w.lerp(sh.coat, 0.0, wet)


def nonskid(w, sh, kind):
    pos = w.obj()
    cav, polish, h = detail(w, sh, "NonSkid", pos, 0.0005)
    path = w.add(0.35, w.mul(w.blot(pos, 0.5, 21.0, detail=1.0), 0.65))     # where feet go more
    dirt = w.mul(w.term("dirt"), w.add(w.mul(cav, 0.9), 0.15), w.add(0.75, w.mul(path, 0.25)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.62, 0.58, 0.52)), w.sat(dirt))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.72, 0.69, 0.62)), w.mul(w.term("patina"), w.add(w.mul(cav, 0.8), 0.15), 0.6))
    worn = w.mul(w.term("worn"), w.m("SUBTRACT", 1.0, cav), path)
    sh.rough = w.lerp(sh.rough, 0.42, w.sat(worn))
    sh.col = w.mix(sh.col, w.scale(sh.col, 1.06), w.mul(w.sat(worn), 0.5))
    ch = w.mul(w.term("chalk"), w.add(0.6, w.mul(w.blot(pos, 0.4, 23.0), 0.4)))
    sh.col = w.mix(sh.col, w.lin((0.76, 0.72, 0.64)), w.mul(w.sat(ch), 0.5))
    lm = w.lum(sh.col)
    sh.col = w.mix(sh.col, w.mix(w.comb(lm, lm, lm), (190, 186, 176), 0.5), w.mul(w.term("faded"), 0.55))   # chalky grey
    mil = w.mul(w.term("mildew"), w.add(w.mul(cav, 0.6), 0.25, w.mul(w.blot(pos, 0.7, 25.0, detail=1.0), 0.35)))
    sh.col = w.mix(sh.col, (88, 92, 76), w.mul(w.sat(mil), 0.7))
    st = w.patches(pos, 0.08, w.mul(w.term("stain"), 0.06), seed=27.0, detail=1.0, soft=0.5)
    sh.col = w.mix(sh.col, (118, 86, 56), w.mul(st, 0.6))


def bottom(w, sh, kind):
    pos, z = w.obj(), w.wz()
    _, g, _ = detail(w, sh, "Gelcoat", pos)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", g, 0.5), 0.05))
    # the ablative paint wears as it works: paler, powdery, patchy
    ch = w.mul(w.term("chalk"), w.add(0.55, w.mul(w.blot(pos, 0.3, 31.0), 0.45)))
    sh.col = w.mix(sh.col, (92, 116, 148), w.mul(w.sat(ch), 0.55))
    # the lake's clay film over all of it, then slime blotches near the top
    film = w.mul(w.term("film"), w.add(0.55, w.mul(w.blot(pos, 0.2, 33.0), 0.45)))
    sh.col = w.mix(sh.col, w.mix(w.lin(FILM_LIN), w.lin(CLAY_LIN), 0.5), w.mul(w.sat(film), 0.6))
    # slime: a soft olive film smeared along the hull by the wash, thickest just under the line
    shallow = w.smooth(z, -0.6, -0.05)
    smear = w.blot(pos, 0.15, 35.0, detail=2.0, stretch=(6.0, 6.0, 1.0))
    sl = w.mul(w.term("slime"), shallow, w.add(0.25, w.mul(smear, 0.75)), 0.7)
    sh.col = w.mix(sh.col, w.lin(SLIME_LIN), w.sat(sl))
    # worn through where the water and the trailer's bunks scour it: the edges, the stub's corners, the forefoot,
    # in long soft patches; grey primer, the white gelcoat under that
    edge = w.edge(0.03)
    where = w.add(0.015, w.mul(edge, 0.7))
    flake = dict(seed=37.0, detail=3.0, soft=0.25, stretch=(3.0, 3.0, 1.0))
    bare = w.patches(pos, 0.12, w.mul(w.term("bare"), where), **flake)
    deep = w.patches(pos, 0.12, w.mul(w.term("bare"), where, 0.45), **flake)
    sh.col = w.mix(w.mix(sh.col, PRIMER, w.mul(bare, 0.7)), (176, 176, 170) if kind == "antifouling" else PRIMER,
                   w.mul(deep, 0.6))
    sh.bump(w.mul(bare, -0.0002))
    if kind == "iron":
        # the iron rusts through: orange bleeding from the edges and the pivot, running down the flats in streaks,
        # broad soft patches where the paint has gone; blisters on the flats
        bleed = w.mul(edge, w.add(0.3, w.mul(w.blot(pos, 0.1, 39.0), 0.7)))
        run = w.smooth(w.noise(pos, 0.04, 41.0, detail=2.0, stretch=(1.0, 1.0, 10.0)), 0.52, 0.62)
        patch = w.mul(w.blot(pos, 0.4, 42.0, detail=1.0, stretch=(1.0, 1.0, 3.0)), 0.2)   # a thin wash where the paint thinned
        rr = w.term("rust")                       # the edges first; runs and patches only once it is well on
        r = w.sat(w.add(w.mul(rr, bleed, 1.4), w.mul(rr, rr, w.add(w.mul(run, 0.8), patch))))
        sh.col = w.mix(sh.col, w.mix(RUST, RUST_DARK, w.add(0.3, w.mul(w.blot(pos, 0.2, 43.0, detail=1.0), 0.5))), r)
        sh.rough = w.lerp(sh.rough, 0.9, r)
        bl = w.patches(pos, 0.015, w.mul(w.term("blister"), 0.15), seed=45.0, detail=1.0, soft=0.05)
        sh.bump(w.mul(bl, 0.0015))
        sh.col = w.mix(sh.col, RUST, w.mul(bl, w.term("rust"), 0.4))


def teak(w, sh, kind):
    pos = w.obj()
    if kind == "varnish":
        varnish(w, sh, pos)
        return
    r, chk, _ = detail(w, sh, "TeakWeathered", pos, 0.0003)
    grain = w.m("SUBTRACT", r, 0.55)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(grain, 0.5)))
    tone = w.add(1.0, w.mul(grain, 0.6))
    sh.col = w.mix(sh.col, w.scale(w.lin(_lin(SILVER)), tone), w.mul(w.term("silver"), 0.95))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.68, 0.52, 0.36)), w.mul(w.term("oiled"), 0.85))   # deep oiled brown
    sh.rough = w.lerp(sh.rough, 0.45, w.term("oiled"))
    sh.rough = w.lerp(sh.rough, 0.85, w.mul(w.term("silver"), 0.6))
    soft = w.m("SUBTRACT", 1.0, w.smooth(r, 0.45, 0.75))
    wet = w.crevice(0.15, 0.4, 0.95)
    dark = w.mul(w.term("dark"), w.sat(w.add(0.45, w.mul(soft, 0.45), w.mul(w.blot(pos, 0.3, 51.0, detail=1.0), 0.1),
                                              w.mul(wet, 0.4))))
    sh.col = w.mix(sh.col, w.mix(MILDEW, (46, 54, 32), w.mul(wet, 0.8)), w.sat(w.mul(dark, 1.3)))
    some = w.patches(pos, 0.2, 0.35, seed=53.0, detail=2.0, soft=0.12)
    c = w.mul(chk, w.term("checks"), some, w.fade(*fade_of("TeakWeathered")))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.6), w.sat(w.mul(c, 1.5)))


def varnish(w, sh, pos):
    """The laminated tiller: Bluebonnet's exterior varnish, without her film flakes' rim."""
    r, _, _ = detail(w, sh, "WoodVarnish", pos, 0.00008)
    figure = w.m("SUBTRACT", r, 0.5)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(figure, 0.7)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.72, 0.58, 0.42)), w.mul(w.term("amber"), 0.7))
    top = w.sat(w.add(w.m("MAXIMUM", w.up(), 0.0), w.mul(w.edge(0.004), 1.5)))
    dull = w.mul(w.term("dull"), w.add(0.4, w.mul(top, 0.6)))
    sh.rough = w.lerp(sh.rough, 0.55, dull)
    sh.coat = w.lerp(sh.coat, 0.2, dull)
    sh.col = w.mix(sh.col, w.lin(_lin(OLD_VARNISH)), w.mul(w.term("fail"), 0.7))
    share = w.mul(w.term("fail"), w.term("fail"), w.add(0.55, w.mul(top, 0.4)))
    fail = w.patches(pos, 0.03, share, seed=55.0, detail=4.0, soft=0.03, stretch=(3.0, 1.0, 1.0))
    bare = w.scale(w.mix(GREY_WOOD, STAIN, w.mul(w.term("stain"), 0.5)), w.add(1.0, w.mul(figure, 1.2)))
    sh.col = w.mix(sh.col, bare, fail)
    sh.rough = w.lerp(sh.rough, 0.85, fail)
    sh.coat = w.lerp(sh.coat, 0.0, fail)


def canvas(w, sh, kind):
    pos, up = w.obj(), w.sat(w.up())
    x, y, zz = w.sep(pos)
    weave = w.mul(w.m("SINE", w.mul(w.add(x, y), 2 * math.pi / 0.0011)), w.m("SINE", w.mul(zz, 2 * math.pi / 0.0011)))
    sh.bump(w.mul(weave, 0.00008, w.fade(0.6, 2.0)))
    lm = w.lum(sh.col)
    faded = w.mix(w.mix(sh.col, w.comb(lm, lm, lm), 0.35), (214, 204, 182), 0.3)
    sh.col = w.mix(sh.col, faded, w.mul(w.term("fade"), w.add(0.55, w.mul(up, 0.45))))
    low = w.crevice(0.06, 0.4, 0.95)
    streak = w.blot(pos, 0.3, 61.0, detail=1.0, stretch=(1.0, 1.0, 3.0))
    dirt = w.mul(w.term("dirt"), w.add(0.25, w.mul(low, 0.6), w.mul(streak, 0.5)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.62, 0.6, 0.5)), w.sat(dirt))
    # left out for years it greys and greens all over, not just in the folds
    sh.col = w.mix(sh.col, w.scale(w.mix(sh.col, (84, 90, 70), 0.6), 0.75), w.mul(w.term("mildew"), 0.8))
    green = w.mul(w.term("mildew"), w.add(w.mul(low, 0.6), w.mul(w.smooth(w.noise(pos, 0.15, 63.0, detail=1.0, stretch=(1.0, 1.0, 3.0)), 0.5, 0.75), 0.5)))
    sh.col = w.mix(sh.col, (58, 66, 44), w.mul(green, 0.6))
    sh.col = w.mix(sh.col, MILDEW, mildew(w, pos, w.term("mildew"), 65.0, extra=low))
    rot = w.mul(w.term("rot"), w.add(0.4, w.mul(up, 0.6)), w.add(0.5, w.mul(w.blot(pos, 0.2, 67.0), 0.5)))
    sh.col = w.mix(sh.col, (150, 146, 128), w.mul(w.sat(rot), 0.3))         # rotten cloth: grey, furred
    sh.rough = w.lerp(sh.rough, 0.98, w.sat(rot))


def vinyl(w, sh, kind):
    pos = w.obj()
    cav, rg, h = detail(w, sh, "Vinyl", pos, 0.00012)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", rg, 0.5), 0.15))
    sh.col = w.scale(sh.col, w.add(0.96, w.mul(cav, 0.04)))
    if kind == "rubrail":
        sh.col = w.mix(sh.col, (176, 176, 172), w.mul(w.term("chalk"), 0.6))
        sh.rough = w.lerp(sh.rough, 0.8, w.term("chalk"))
        sc = w.patches(pos, 0.05, w.mul(w.term("scuff"), 0.3), seed=71.0, detail=2.0, soft=0.15, stretch=(8.0, 8.0, 1.0))
        sh.col = w.mix(sh.col, (58, 56, 54), w.mul(sc, 0.75))
        gr = w.mul(w.term("grime"), w.add(w.mul(cav, 0.6), w.mul(w.crevice(0.03), 0.6)))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.55), w.sat(gr))
        return
    sh.col = w.mix(sh.col, w.scale(sh.col, (1.0, 0.93, 0.74)), w.term("yellow"))
    # leak stains: brown rings spreading out from where the deck leaks (ports, the mast step, the pop-top's
    # edge, fittings), darkest at their drying edge, the tide mark
    big = w.patches(pos, 0.22, w.mul(w.term("stain"), 0.3), seed=73.0, detail=2.0, soft=0.4)
    ring = w.sat(w.m("SUBTRACT", w.patches(pos, 0.22, w.mul(w.term("stain"), 0.36), seed=73.0, detail=2.0,
                                           soft=0.1), w.patches(pos, 0.22, w.mul(w.term("stain"), 0.26), seed=73.0,
                                                                detail=2.0, soft=0.1)))
    sh.col = w.mix(sh.col, LEAK, w.mul(big, 0.45))
    sh.col = w.mix(sh.col, w.scale(w.lin(_lin(LEAK)), 0.7), w.mul(ring, 0.7))
    gr = w.mul(w.term("grime"), w.add(w.mul(w.edge(0.012), 0.6), w.mul(w.blot(pos, 0.35, 75.0), 0.35),
                                      w.mul(cav, 0.3, w.fade(0.3, 0.8))))       # the grain's dirt only up close
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.7, 0.66, 0.6)), w.sat(gr))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.86, 0.78, 0.6)), w.mul(w.term("mildew"), 0.55))   # gone yellow-brown
    sh.col = w.mix(sh.col, MILDEW, mildew(w, pos, w.term("mildew"), 79.0, extra=w.crevice(0.15, 0.4, 0.95)))


def sole(w, sh, kind):
    pos = w.obj()
    x, y, _ = w.sep(pos)
    r, pores, film = detail(w, sh, "WoodVarnish", pos, 0.00006)
    # teak strips 50 mm wide fore and aft, a 6 mm holly strip between each pair, each teak strip its own tone
    q = w.m("DIVIDE", w.add(y, 0.025), 0.05)
    holly = w.m("SUBTRACT", 1.0, w.smooth(w.mul(w.m("ABSOLUTE", w.m("SUBTRACT", w.m("FRACT", q), 0.5)), 0.05),
                                          0.0025, 0.0035))
    tone, _ = w.hash(w.comb(w.m("FLOOR", q), 0.0, 0.0), 81.0)
    figure = w.m("SUBTRACT", r, 0.5)
    sh.col = w.scale(sh.col, w.add(0.88, w.mul(tone, 0.24), w.mul(figure, 0.6)))
    hc = w.mix(w.mix(HOLLY, HONEY, w.term("amber")), (66, 58, 44), w.mul(w.term("stain"), 0.8))   # neglected: dark holly
    sh.col = w.mix(sh.col, hc, holly)
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.7, 0.54, 0.36)), w.mul(w.term("amber"), w.m("SUBTRACT", 1.0, holly), 0.85))
    # the varnish worn grey down the middle where feet go
    path = w.m("SUBTRACT", 1.0, w.smooth(w.m("ABSOLUTE", y), 0.12, 0.3))
    worn = w.mul(w.add(w.term("worn"), w.mul(w.term("patina"), 0.5)), path, w.add(0.5, w.mul(w.blot(pos, 0.12, 83.0, stretch=(3.0, 1.0, 1.0)), 0.6)))
    sh.rough = w.lerp(sh.rough, 0.7, w.sat(worn))
    sh.coat = w.lerp(sh.coat, 0.0, w.sat(worn))
    sh.col = w.mix(sh.col, w.scale(w.mix(GREY_WOOD, sh.col, 0.4), w.add(1.0, w.mul(figure, 0.6))), w.mul(w.sat(worn),
                                                                                                         0.55))
    # water stains: black at the edges, the keel trunk and the companionway's foot; grime in the corners
    edge = w.sat(w.add(w.crevice(0.12, 0.4, 0.95), w.mul(w.m("SUBTRACT", 1.0, w.smooth(x, -0.78, -0.55)), 0.6)))
    st = w.mul(w.term("stain"), edge, w.add(0.6, w.mul(w.blot(pos, 0.3, 85.0, detail=1.0), 0.4)))
    sh.col = w.mix(sh.col, STAIN, w.mul(w.sat(st), 0.75))
    gr = w.mul(w.term("grime"), w.crevice(0.06, 0.4, 0.95))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.6), w.sat(gr))
    rot = w.patches(pos, 0.15, w.mul(w.term("rot"), 0.2, w.add(0.2, edge)), seed=87.0, detail=1.0, soft=0.6,
                    stretch=(3.0, 1.0, 1.0))                     # soft, along the strips
    sh.col = w.mix(sh.col, (52, 46, 36), w.mul(rot, 0.7))
    sh.rough = w.lerp(sh.rough, 0.9, rot)
    sh.bump(w.mul(rot, -0.0004))


def veneer(w, sh, kind):
    pos, z = w.obj(), w.wz()
    r, _, _ = detail(w, sh, "WoodVarnish", pos, 0.00005)
    figure = w.m("SUBTRACT", r, 0.5)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(figure, 0.8)))
    lm = w.lum(sh.col)
    sh.col = w.mix(sh.col, w.mix(w.comb(lm, lm, lm), (178, 160, 136), 0.6), w.mul(w.term("dry"), 0.55))
    sh.rough = w.lerp(sh.rough, 0.8, w.term("dry"))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.66, 0.52, 0.38)), w.mul(w.term("oiled"), 0.85))
    hands = w.mul(w.add(w.term("hands"), w.mul(w.term("patina"), 0.7)),
                  w.add(w.mul(w.edge(0.015), 0.9), w.mul(w.blot(pos, 0.25, 91.0), 0.3)))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.62), w.sat(hands))
    # water rises black from the sole and the bilge: a ragged tide line a few centimetres up
    rise = w.add(-0.08, w.mul(w.term("water"), 0.3), w.mul(w.m("SUBTRACT", w.noise(pos, 0.06, 93.0), 0.5), 0.08))
    wet = w.mul(w.term("water"), w.m("SUBTRACT", 1.0, w.smooth(z, w.m("SUBTRACT", rise, 0.03), rise)))
    sh.col = w.mix(sh.col, STAIN, w.mul(w.sat(wet), 0.8))
    sh.col = w.mix(sh.col, (70, 80, 62), mildew(w, pos, w.term("mildew"), 95.0, extra=wet))


def fabric(w, sh, kind):
    pos, up = w.obj(), w.sat(w.up())
    tone, gaps, h = detail(w, sh, "Tweed", pos, 0.0002)
    if kind == "cushion":
        sh.col = w.scale(sh.col, w.add(0.6, w.mul(tone, 0.8)))      # the plaid
    sh.col = w.scale(sh.col, w.m("SUBTRACT", 1.0, w.mul(gaps, 0.25)))
    lm = w.lum(sh.col)
    faded = w.mix(w.mix(sh.col, w.comb(lm, lm, lm), 0.5), (186, 178, 158), 0.35)
    sh.col = w.mix(sh.col, faded, w.mul(w.term("fade"), w.add(0.5, w.mul(up, 0.5)) if kind == "cushion" else 1.0))
    if kind == "cushion":
        worn = w.mul(w.term("worn"), w.add(w.mul(w.edge(0.015), 0.8), w.mul(up, 0.25)))
        sh.col = w.mix(sh.col, w.mix(sh.col, (160, 150, 130), 0.35), w.mul(w.sat(worn), 0.6))
        sh.rough = w.lerp(sh.rough, 0.7, w.sat(worn))
    st = w.patches(pos, 0.07, w.mul(w.term("stain"), 0.18), seed=101.0, detail=2.0, soft=0.35)
    ring = w.sat(w.m("SUBTRACT", w.patches(pos, 0.07, w.mul(w.term("stain"), 0.22), seed=101.0, detail=2.0, soft=0.1),
                     w.patches(pos, 0.07, w.mul(w.term("stain"), 0.15), seed=101.0, detail=2.0, soft=0.1)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.62, 0.55, 0.42)), w.sat(w.add(w.mul(st, 0.7), w.mul(ring, 0.7))))
    # neglected, the cloth goes dingy all over: damp, dust and body oils
    if kind == "curtain":
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.7, 0.68, 0.6)), w.mul(w.term("stain"), 0.7))
    else:                                                       # a cushion washes out grey-beige and dingy
        # neglected, a dark cushion goes dusty and grey all over (bloom of dust and mildew, the dye gone), the dark
        # stains above standing out on it
        sh.col = w.mix(sh.col, (148, 140, 118), w.mul(w.term("stain"), w.term("stain"), 0.55))
    sh.col = w.mix(sh.col, (52, 60, 44), mildew(w, pos, w.term("mildew"), 105.0))


def plastic(w, sh, kind):
    pos, up = w.obj(), w.sat(w.up())
    if kind == "white":
        sh.col = w.mix(sh.col, w.scale(sh.col, (1.0, 0.92, 0.72)), w.term("yellow"))
        sc = w.patches(pos, 0.02, w.mul(w.term("scuff"), 0.15), seed=111.0, detail=2.0, soft=0.2, stretch=(3.0, 1.0, 1.0))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.75), w.mul(sc, 0.6))
        sh.rough = w.lerp(sh.rough, 0.6, sc)
        gr = w.mul(w.term("grime"), w.add(0.35, w.mul(w.crevice(0.04), 0.8), w.mul(w.blot(pos, 0.1, 113.0), 0.4)))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.6, 0.55, 0.45)), w.sat(gr))
        return
    bl = w.mul(w.term("bloom"), w.add(0.45, w.mul(up, 0.55)), w.add(0.7, w.mul(w.blot(pos, 0.1, 115.0), 0.3)))
    sh.col = w.mix(sh.col, (92, 92, 90), w.mul(w.sat(bl), 0.55))
    sh.rough = w.lerp(sh.rough, 0.85, w.sat(bl))
    gr = w.mul(w.term("grime"), w.add(0.3, w.crevice(0.03)))
    sh.col = w.mix(sh.col, (112, 106, 92), w.mul(w.sat(gr), 0.5))           # dust caked in the bloom


def metal(w, sh, kind):
    pos = w.obj()
    streak, rg, pits = detail(w, sh, "Metal", pos)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", rg, 0.5), 0.08))
    cr = w.crevice(0.03, 0.35, 0.9)
    if kind == "stainless":
        sh.rough = w.lerp(sh.rough, 0.45, w.term("dull"))
        tea = w.mul(w.term("tea"), w.add(w.mul(cr, 0.9), w.mul(w.blot(pos, 0.05, 121.0), 0.35)))
        sh.col = w.mix(sh.col, TEA, w.mul(w.sat(tea), 0.6))
        sh.metal = w.lerp(sh.metal, 0.4, w.mul(w.sat(tea), 0.6))
        sp = w.patches(pos, 0.004, w.mul(w.term("rust"), 0.12, w.add(0.3, cr)), seed=123.0, soft=0.03, detail=1.0)
        sh.col = w.mix(sh.col, RUST, sp)
        sh.metal = w.lerp(sh.metal, 0.0, sp)
        return
    if kind == "aluminium":
        sh.rough = w.lerp(sh.rough, 0.6, w.term("dull"))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.92), w.term("dull"))
        ox = w.mul(w.term("oxide"), w.add(0.4, w.mul(cr, 0.8), w.mul(pits, 0.6),
                                          w.mul(w.blot(pos, 0.1, 125.0, detail=1.0), 0.3)))
        sh.col = w.mix(sh.col, OXIDE, w.mul(w.sat(ox), 0.85))
        sh.metal = w.lerp(sh.metal, 0.0, w.sat(ox))
        sh.rough = w.lerp(sh.rough, 0.95, w.sat(ox))
        runs = w.patches(pos, 0.02, w.mul(w.term("grime"), 0.3), seed=127.0, detail=2.0, stretch=(1.0, 1.0, 10.0))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.5), w.mul(runs, 0.7))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.8, 0.78, 0.72)), w.mul(w.term("oxide"), 0.5))   # grime over all
        return
    ch = w.mul(w.term("chalk"), w.add(0.6, w.mul(w.blot(pos, 0.3, 129.0), 0.4)))
    sh.col = w.mix(sh.col, (216, 214, 206), w.mul(w.sat(ch), 0.4))
    sh.rough = w.lerp(sh.rough, 0.8, w.sat(ch))
    sh.coat = w.lerp(sh.coat, 0.0, w.sat(ch))
    fl = w.patches(pos, 0.02, w.mul(w.term("flake"), 0.25, w.add(0.2, w.mul(cr, 1.5))), seed=131.0, detail=4.0, soft=0.04)
    sh.col = w.mix(sh.col, w.mix(JW.DURAL, OXIDE, w.smooth(streak, 0.3, 0.9)), fl)
    sh.metal = w.lerp(sh.metal, 1.0, fl)
    runs = w.patches(pos, 0.02, w.mul(w.term("grime"), 0.3), seed=133.0, detail=2.0, stretch=(1.0, 1.0, 10.0))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.55), w.mul(runs, 0.6))


def acrylic(w, sh, kind):
    pos = w.obj()
    haze = w.term("haze")
    sh.col = w.mix(sh.col, (88, 92, 96), w.mul(haze, 0.45))
    sh.rough = w.lerp(sh.rough, 0.35, haze)
    sh.coat = w.lerp(sh.coat, 0.3, haze)
    cz = w.mul(w.voronoi_edge(pos, 0.004), w.term("craze"), w.fade(0.3, 0.9))     # only at arm's length
    sh.col = w.mix(sh.col, (150, 152, 156), w.mul(cz, 0.3))
    sh.col = w.mix(sh.col, (112, 114, 118), w.mul(w.term("craze"), 0.12))       # its haze past that
    gr = w.mul(w.term("grime"), w.add(0.2, w.mul(w.edge(0.01), 0.8), w.mul(w.blot(pos, 0.1, 141.0), 0.35)))
    sh.col = w.mix(sh.col, (110, 100, 84), w.mul(w.sat(gr), 0.5))
    sh.rough = w.lerp(sh.rough, 0.6, w.mul(w.sat(gr), 0.6))


DRESS = {"gelcoat": gelcoat, "nonskid": nonskid, "bottom": bottom, "teak": teak, "canvas": canvas, "vinyl": vinyl,
         "sole": sole, "veneer": veneer, "fabric": fabric, "plastic": plastic, "metal": metal, "acrylic": acrylic}


def used_materials():
    import bpy
    return {s.material.name for o in bpy.data.objects if o.type == "MESH" for s in o.material_slots if s.material}


def dress(level="L0"):
    """Gives every material the build uses its finish and its wear, then sets them to `level`; returns the names
    dressed. Stops if the build uses a material no card covers."""
    import bpy
    used = used_materials()
    missing, _ = coverage(used)
    if missing:
        raise SystemExit(f"textures_c22.json covers no card or 'unweathered' entry for {missing}")
    idx = material_index()
    done = []
    for m in bpy.data.materials:
        if m.name not in used or m.name not in idx or m.get("c22_surface"):
            continue
        s, k = idx[m.name]
        finish(m)
        w = CW(m, s, k)
        sh = JW.Shader(w)
        DRESS[s](w, sh, k)
        if m.name == "GelcoatHull":
            # below the paint line her hull is the bottom: its paint and its wear (and the lake's line above it)
            bw = CW(m, "bottom", "antifouling")
            bw.nt, bw.N, bw.L = w.nt, w.N, w.L
            below = w.m("SUBTRACT", 1.0, w.smooth(w.wz(), PAINT_LINE - 0.003, PAINT_LINE + 0.003))
            af = CARDS["finish"]["Antifouling"]
            under(bw, sh, below, bottom, "antifouling", base=(af["rgb"], af["rough"], 0.0))
        sh.finish()
        m["c22_surface"], m["c22_kind"] = s, k
        done.append(m.name)
    apply_level(level)
    return sorted(done)


def apply_level(level):
    """Sets every dressed material's wear terms to a level ("L0".."L4") or to (age, care)."""
    import bpy
    age, care = (LEVELS[level]["age"], LEVELS[level]["care"]) if isinstance(level, str) else level
    cache = {}
    for m in bpy.data.materials:
        if not m.get("c22_surface"):
            continue
        idx_kind = {m["c22_surface"]: m["c22_kind"], "bottom": "antifouling"} if m.name == "GelcoatHull" \
            else {m["c22_surface"]: m["c22_kind"]}
        for n in m.node_tree.nodes:
            if n.type == "VALUE" and n.name.startswith("wear:"):
                s, term = n.name[5:].split(".", 1)
                key = (s, idx_kind[s])
                if key not in cache:
                    cache[key] = amounts(s, idx_kind[s], age, care)
                if term not in cache[key]:
                    raise SystemExit(f"{m.name}: no amount for wear term {term} ({key})")
                n.outputs[0].default_value = cache[key][term]
    bpy.context.scene["c22_wear"] = level if isinstance(level, str) else f"{age},{care}"


def dressed():
    import bpy
    return sorted((m for m in bpy.data.materials if m.get("c22_surface")), key=lambda m: m.name)


def albedo_mode(mode):
    """"albedo": each dressed material renders its colour alone (an emission of its Base Color), for measuring;
    "id": each its own flat colour (JW.material_id, in name order); False: the shaders back. The glass holds out."""
    for m in dressed():
        m["j_surface"] = m["c22_surface"]           # Bluebonnet's albedo_mode keys on j_surface
    JW_unweathered = JW.CARDS["unweathered"]
    try:
        JW.CARDS["unweathered"] = []
        JW.dressed = dressed
        JW.albedo_mode(mode)
    finally:
        JW.CARDS["unweathered"] = JW_unweathered


def report(material_names):
    """The cards' coverage, the maps and their budget, every level's amounts."""
    missing, extra = coverage(material_names)
    meta_path = os.path.join(OWN_DIR, "c22_detail.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    own, total = {}, 0.0
    for name in CARDS["maps"]["own"]:
        w, h = meta.get(name, {}).get("px", CARDS["maps"]["own"][name]["px"])
        mb = (w * h * 1.0 + w * h * 0.5) * 4.0 / 3.0 / 2 ** 20
        own[name] = {"px": [w, h], "mb_high": round(mb, 3)}
        total += mb
    return {"uncovered": missing, "not_built": extra, "maps_own": own,
            "budget": {"high_mb": round(total, 3), "high_cap_mb": CARDS["budget"]["high_mb"]},
            "levels": {lv: level_amounts(lv) for lv in LEVELS}}


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if len(args) >= 2 and args[0].endswith(".blend"):
        import bpy
        bpy.ops.wm.open_mainfile(filepath=args[0])
        lv = args[args.index("--level") + 1] if "--level" in args else "L0"
        names = dress(lv)
        print(f"dressed {len(names)} materials at {lv}: {', '.join(names)}")
        bpy.ops.wm.save_as_mainfile(filepath=args[1])
    else:
        for lv in LEVELS:
            print(lv, json.dumps(level_amounts(lv)))
