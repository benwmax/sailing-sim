"""The Hobie 16's wear (docs/hobie16-8): how much of each kind of wear a level brings, and where on her it falls.

    import weathering_hobie16 as wh
    wh.amounts("gelcoat", "topsides", 6.0, 0.5)     # {"gloss": 0.6, "chalk": 0.5, ...}, no Blender needed
    wh.dress("L2")                                   # in Blender, on a built hobie16.blend: finish + wear on every slot
    wh.apply_level("L4")                             # then any level (or (age, care)) without dressing again

    blender -b -P weathering_hobie16.py -- <hobie16.blend> <out.blend> [--level L2]     # dress a build and save it

The texture loop's five levels (Tools/texloop/levels.json) are fixed points of E1's Age (years) and Care (0 left to rot
.. 1 kept); the loop's time_k and dirt_k (Tools/texloop/wear.py) split them into what the years do whatever the owner
does and what care takes away, as for the Catalina 22 (docs/c22-9, weathering_c22.py), whose node helpers, gelcoat,
metal, plastic and canvas dressers this reuses. Hers are the beach cat's own: dry-sailed from the club's beach, so no
bottom paint, slime or lake mustache, but sun on the hulls, trampoline and anodising, sand and the dolly on her keels,
and a faint tan line where she floats.

dress() gives each material the build made (flat slot colours, build_hobie16.SLOT_RGB) its new finish from the cards
(textures_hobie16.json 'finish') and builds the wear in its nodes, each term a Value node named
"wear:<surface>.<term>" that apply_level() sets, so one dressed .blend renders every level. Everything is in metres in
the boat's frame (X forward, Y to port, Z up from the design waterline with her crew aboard); the terms are kept to what
a pixel shader can do, so the game's twin can follow.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
sys.path.insert(0, os.path.join(REPO, "Tools", "shipkit", "jclass"))
sys.path.insert(0, os.path.join(REPO, "Tools", "shipkit", "catalina22", "textures"))
import wear as loop  # noqa: E402
import weathering as JW  # noqa: E402  (Bluebonnet's node helpers)
import weathering_c22 as WC  # noqa: E402  (the Catalina 22's dressers and helpers)

CARDS = json.load(open(os.path.join(HERE, "textures_hobie16.json")))
OWN_DIR = os.path.join(REPO, "Inputs", "hobie16-detail")
LEVELS = {lv["id"]: lv for lv in loop.levels()}
RATE = CARDS["water"]["rate"]
sat, ramp, refreshed = JW.sat, JW.ramp, JW.refreshed
renewed_age, PATINA = WC.renewed_age, WC.PATINA


def amounts(surface, kind, age, care):
    """Each wear term, 0 to 1, for one surface and kind at E1's Age (years) and Care (0..1), with the Catalina's rules
    (weathering_c22.amounts): a first season's marks go as the square root of dirt_k times `fresh` where a kept boat's
    routine takes them away again; neglect's own terms start past a threshold of dirt_k a kept boat never reaches;
    what the years do follows time_k."""
    t, d = loop.time_k(age, care), loop.dirt_k(age, care)
    fresh = 1.0 - 0.85 * refreshed(age, care)
    first = math.sqrt(d) * fresh
    if surface == "gelcoat":
        a = {"gloss": sat(0.8 * first + 0.2 * t),
             "chalk": loop.chalk_k(age, care) * (0.9 if kind == "topsides" else 1.0) * (0.5 + 0.5 * fresh),
             "yellow": t,
             "craze": ramp(t, 0.3, 0.9) * (1.0 - 0.3 * care),     # round the pylons and tangs, where the hull flexes
             "streak": ramp(d, 0.1, 0.8) * fresh,
             "dirt": ramp(d, 0.2, 0.9) * fresh,
             "mildew": ramp(d, 0.55, 0.95),
             "patina": PATINA(age)}
        if kind in ("topsides", "blade"):
            # beached and dollied every sail: sand scratches along the keels within a season, scraped grey over the
            # years whatever the care (keel strips cover the worst on a kept boat), worn through when neglected
            a["scrape"] = sat(1.6 * first + 0.5 * t) * (1.0 - 0.3 * care * ramp(age, 6.0, 20.0))
            a["worn"] = ramp(d, 0.45, 0.95)
        if kind == "topsides":
            a["line"] = sat(1.5 * first) * (0.5 + 0.5 * (1.0 - care))   # the lake's tan where she floats: washed off
        return a
    if surface == "tramp":
        own = renewed_age(age, care, 4.0)                        # a kept boat's is renewed every 8 years: 4 on average
        ct, cd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"fade": sat(1.5 * ct) * (1.0 - 0.35 * care),      # the dye goes in the sun; a kept one is covered
                "chalk": max(cd * fresh, 0.3 * ct),
                "dirt": sat(1.3 * math.sqrt(cd)) * (1.0 - 0.6 * refreshed(age, care)),
                "mildew": ramp(cd, 0.35, 0.9),
                "fray": ramp(cd, 0.5, 0.95) * ramp(own, 3.0, 10.0)}
    if surface == "anodised":
        return {"fade": sat(1.5 * t),                             # the dye fades toward grey-bronze: kept or not
                # a kept boat's polished, covered spars fade to a warm bronze; a half-kept or neglected boat's to a
                # dull grey (blind round 3: bronze at six years half kept read as the thirty-year boat)
                "bronze": care * care,
                "dull": sat(0.8 * first + 0.3 * t),
                "scratch": sat(1.2 * first + 0.6 * t),           # lines and hands rub through to bright metal
                "oxide": ramp(d, 0.2, 0.85),                      # white powder where the metal is bare
                "grime": ramp(d, 0.1, 0.8) * fresh}
    if surface == "metal":
        return WC.amounts("metal", kind, age, care)
    if surface == "plastic":
        return WC.amounts("plastic", "black", age, care)        # black and grey moulded bodies bloom alike
    if surface == "canvas":
        own = renewed_age(age, care, 5.0)                        # hiking straps: renewed about every ten years kept
        ct, cd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"fade": sat(1.2 * ct), "dirt": sat(1.2 * math.sqrt(cd)) * (1.0 - 0.6 * refreshed(age, care)) * (0.6 + 0.6 * cd),
                "mildew": ramp(cd, 0.25, 0.85), "rot": ramp(cd, 0.6, 0.95) * ramp(own, 4.0, 12.0)}
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
                    raise SystemExit(f"textures_hobie16.json: {n} is in two cards ({out[n]} and {(s, k)})")
                out[n] = (s, k)
    return out


def coverage(material_names):
    """The materials the build uses that no card or 'unweathered' entry covers (must be empty), and the card entries
    the build does not use (reported)."""
    idx = material_index()
    un = set(CARDS["unweathered"])
    names = set(material_names)
    return sorted(names - set(idx) - un), sorted((set(idx) | un) - names)


# ================================================================================================ Blender
_lin = JW._lin
MILDEW, GRIME, RUST = JW.MILDEW, JW.GRIME, JW.RUST
OXIDE = JW.OXIDE
LAMINATE = (128, 132, 124)              # worn-through gelcoat: the grey-green glass laminate under it
SCRAPED = (146, 144, 136)               # scratched gelcoat with sand ground in: a dull grey
LINE_TAN = (172, 146, 104)              # the lake's clay where she floats
FADED_BLACK = (78, 74, 70)              # sun-faded black PVC and dye: a dusty grey-brown
HULL_CY = json.load(open(os.path.join(HERE, "..", "specs_hobie16.json")))["game"]["hull_center_y_m"]   # each hull's centreline
BRONZE = (92, 78, 64)                   # anodising's black dye faded: a dull bronze-grey
GREY_FADE = (98, 96, 92)                # the same dye faded on a spar left dull and unpolished: a flat grey
BRIGHT = (186, 188, 192)                # bare aluminium where it is scratched through


def map_path(name):
    if name in CARDS["maps"]["own"]:
        return os.path.join(OWN_DIR, f"T_H16_{name}_M.png")
    return WC.map_path(name)


def tile_of(name):
    own = CARDS["maps"]["own"].get(name)
    return (own["tile_mm"][0] / 1000.0, own["tile_mm"][1] / 1000.0) if own else WC.tile_of(name)


def fade_of(name):
    own = CARDS["maps"]["own"].get(name)
    return tuple(own["fade_m"]) if own else WC.fade_of(name)


class HW(WC.CW):
    """The Catalina's node helpers with the Hobie's own map."""

    def term(self, name):
        key = f"{self.prefix}.{name}"
        if key not in self.terms:
            n = self.N.new("ShaderNodeValue")
            n.name = n.label = "wear:" + key
            self.terms[key] = n.outputs[0]
        return self.terms[key]

    def image(self, name, vec, tile_m, box=True):
        old = JW.map_path
        JW.map_path = map_path
        try:
            return JW.W.image(self, name, vec, tile_m, box=box)
        finally:
            JW.map_path = old


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


# ------------------------------------------------------------------------------------------------ the surfaces
def gelcoat(w, sh, kind):
    """The Catalina's gelcoat (chalk, yellowing, crazing at the fittings, black streaks, the dirt film, mildew, the
    corners' patina: weathering_c22.gelcoat as on her decks), then the beach's marks: sand scratches along the keels
    and forefoot that scrape grey and wear through to the laminate, and a faint tan line where she floats."""
    WC.gelcoat(w, sh, "deck")
    # neglected, the chalk lifts in powdery patches over the cream (an even beige read as paint)
    up = w.sat(w.up())
    # (broad and soft: tight blots at a strong mix read as beige camouflage up close)
    bloom = w.mul(w.term("chalk"), w.term("dirt"), w.add(0.3, w.mul(up, 0.7)),
                  w.smooth(w.blot(w.obj(), 0.7, 213.0, detail=1.0), 0.3, 0.85))
    sh.col = w.mix(sh.col, (214, 211, 202), w.mul(w.sat(bloom), 0.28))
    sh.rough = w.lerp(sh.rough, 0.85, w.sat(bloom))
    if kind == "deck":
        return
    pos, z = w.obj(), w.wz()
    x = w.sep(pos)[0]
    down = w.sat(w.m("MULTIPLY", w.up(), -1.0))
    if kind == "topsides":
        # the keel line: the deep V's bottom along her whole length up to the stem (her forefoot, where she is run up
        # the beach), which takes the sand and the dolly's rollers; its very edge is where the gelcoat wears through
        off = w.m("ABSOLUTE", w.m("SUBTRACT", w.m("ABSOLUTE", w.sep(pos)[1]), HULL_CY))
        wet = w.m("SUBTRACT", 1.0, w.smooth(z, -0.05, 0.08))
        where = w.mul(w.m("SUBTRACT", 1.0, w.smooth(off, 0.02, 0.06)), wet)
        core = w.mul(w.m("SUBTRACT", 1.0, w.smooth(off, 0.006, 0.018)), wet)
    else:
        # the rudder blades' tips, which touch the bottom first coming in
        # (the lower third: round 3's lowest 12 cm hardly showed, and the blind reviewers missed the scrapes)
        where = w.m("SUBTRACT", 1.0, w.smooth(z, -0.66, -0.38))
        core = w.m("SUBTRACT", 1.0, w.smooth(z, -0.76, -0.62))
    # a neglected hull's grubby film from the beach and the trailer: sand, sunscreen and dust over the chalk, heaviest
    # low down and on what faces the ground (a kept hull is washed: the dirt term starts only with neglect)
    low = w.add(0.45, w.mul(w.m("SUBTRACT", 1.0, w.smooth(z, -0.1, 0.25)), 0.35), w.mul(down, 0.2))
    film = w.mul(w.term("dirt"), low, w.add(0.6, w.mul(w.blot(pos, 0.4, 211.0, detail=1.0, stretch=(3.0, 1.0, 1.0)), 0.4)))
    sh.col = w.mix(sh.col, (170, 162, 146), w.mul(w.sat(film), 0.4))
    sh.rough = w.lerp(sh.rough, 0.7, w.mul(w.sat(film), 0.6))
    # sand scratches: fine straight lines fore and aft, seen within a couple of metres (past that their mean);
    # then, as the years add up, the gloss rubbed off to a dull grey band along the keel, ragged along its length
    lines = w.patches(pos, 0.0025, w.mul(w.term("scrape"), 0.3), seed=201.0, detail=1.0, soft=0.1,
                      stretch=(80.0, 1.0, 1.0))
    fine = w.lerp(w.mul(w.term("scrape"), 0.25), lines, w.fade(0.6, 2.5))
    along = w.noise(pos, 0.3, 203.0, detail=2.0, stretch=(5.0, 1.0, 1.0))      # runs fore and aft, soft-ended
    band = w.mul(where, w.smooth(w.term("scrape"), 0.55, 1.0), w.add(0.5, w.mul(along, 0.5)))
    sc = w.sat(w.add(w.mul(fine, where), w.mul(band, 0.7)))
    sh.col = w.mix(sh.col, SCRAPED, sc)
    sh.rough = w.lerp(sh.rough, 0.7, sc)
    sh.coat = w.lerp(sh.coat, 0.0, sc)
    # neglected, the keel wears through to the grey laminate in long runs where the beach takes her weight
    worn = w.mul(core, w.term("worn"), w.smooth(along, 0.25, 0.7))
    sh.col = w.mix(sh.col, LAMINATE, w.mul(w.sat(worn), 0.95))
    sh.rough = w.lerp(sh.rough, 0.85, w.sat(worn))
    sh.bump(w.mul(w.sat(worn), -0.0004))
    if kind == "topsides":
        # the lake's line: a faint ragged tan band where she floats with her crew aboard (z 0), higher at the bow
        xs = w.comb(x, 0.0, 0.0)
        wob = w.add(w.mul(w.m("SUBTRACT", w.noise(xs, 0.4, 207.0, detail=1.0), 0.5), 0.03),
                    w.mul(w.m("SUBTRACT", w.noise(xs, 0.1, 208.0, detail=1.0), 0.5), 0.02))
        top = w.add(0.025, w.mul(w.smooth(x, 0.8, 2.4), 0.04), wob)
        # soft-edged: fading down into what was under water and up over the splash, never a drawn stripe
        band = w.mul(w.smooth(z, -0.07, 0.0), w.m("SUBTRACT", 1.0, w.smooth(z, w.m("SUBTRACT", top, 0.035), w.add(top, 0.01))))
        ln = w.mul(band, w.term("line"), w.add(0.6, w.mul(w.blot(pos, 0.5, 209.0, detail=1.0, stretch=(4.0, 1.0, 1.0)), 0.4)))
        sh.col = w.mix(sh.col, LINE_TAN, w.mul(w.sat(ln), 0.4))


def tramp(w, sh, kind):
    """The trampoline: the weave close up, the black fading to a dusty grey-brown in the sun and chalking, the walks
    darkened by feet and sand (along each hull and the centre lacing, where crews cross), mildew where water lies in
    the sag, the edges frayed at the lacing."""
    pos, up = w.obj(), w.sat(w.up())
    x, y, _ = w.sep(pos)
    cav, rg, h = detail(w, sh, "Tramp", pos, 0.00012)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", rg, 0.5), 0.2), w.mul(cav, 0.1))
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(w.m("SUBTRACT", 0.5, cav), 0.25, w.fade(0.6, 2.5))))
    patch = w.add(0.75, w.mul(w.blot(pos, 0.5, 211.0, detail=1.0), 0.25))
    sh.col = w.mix(sh.col, FADED_BLACK, w.mul(w.term("fade"), 0.9, w.add(0.5, w.mul(up, 0.5)), patch))
    ch = w.mul(w.term("chalk"), w.add(0.6, w.mul(w.blot(pos, 0.3, 213.0), 0.4)))
    sh.col = w.mix(sh.col, (124, 118, 108), w.mul(w.sat(ch), 0.6))       # neglect bleaches it past the fade
    sh.rough = w.lerp(sh.rough, 0.85, w.sat(ch))
    ay = w.m("ABSOLUTE", y)
    walk = w.sat(w.add(w.m("SUBTRACT", 1.0, w.smooth(ay, 0.08, 0.25)),                # crossing at the centre
                       w.smooth(ay, 0.75, 0.95)))                                       # along each hull
    dirt = w.mul(w.term("dirt"), w.add(0.3, w.mul(walk, 0.7)), w.add(0.6, w.mul(w.blot(pos, 0.25, 215.0, detail=1.0), 0.4)))
    sh.col = w.mix(sh.col, (66, 58, 46), w.mul(w.sat(dirt), 0.55))
    # mildew where water and dirt sit: along the laced edges and the hulls, and in the sag of each half; small
    # patches, not a film
    edges = w.sat(w.add(w.m("SUBTRACT", 1.0, w.smooth(ay, 0.05, 0.16)), w.smooth(ay, 0.72, 0.85),
                        w.m("SUBTRACT", 1.0, w.smooth(x, -1.68, -1.5)), w.smooth(x, 0.3, 0.45)))
    sag = w.mul(w.m("SUBTRACT", 1.0, w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", ay, 0.45)), 0.1, 0.3)),
                w.m("SUBTRACT", 1.0, w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", x, -0.6)), 0.3, 0.8)))
    # (distinct soft-edged patches: round 2's hard edges read as stamped, round 3's 0.6 mix as an even wash)
    blots = w.smooth(w.blot(pos, 0.13, 217.0, detail=1.5), 0.5, 0.72)
    mg = w.mul(w.term("mildew"), w.add(w.mul(edges, 0.9), w.mul(sag, 0.35)), blots)
    sh.col = w.mix(sh.col, (62, 76, 54), w.mul(w.sat(mg), 0.8))
    sh.col = w.mix(sh.col, MILDEW, WC.mildew(w, pos, w.term("mildew"), 219.0, extra=edges))
    # frayed edges by the lacing: pale broken threads along the centre gap, the rear edge and the sides; the
    # threads up close, their mean further off
    edge = w.sat(w.add(w.m("SUBTRACT", 1.0, w.smooth(ay, 0.03, 0.08)), w.smooth(ay, 0.8, 0.86),
                       w.m("SUBTRACT", 1.0, w.smooth(x, -1.66, -1.58))))
    thr = w.patches(pos, 0.005, w.mul(w.term("fray"), 0.22), seed=221.0, detail=2.0, soft=0.25, stretch=(1.0, 6.0, 1.0))
    fr = w.mul(w.lerp(w.mul(w.term("fray"), 0.2), thr, w.fade(0.5, 2.0)), edge)
    sh.col = w.mix(sh.col, (122, 117, 106), w.mul(w.sat(fr), 0.45))
    sh.rough = w.lerp(sh.rough, 0.9, w.sat(fr))


def anodised(w, sh, kind):
    """Black anodised aluminium: the dye fades toward grey-bronze, the surface dulls and chalks, the edges and the
    places lines rub scratch through to bright metal, and the bare metal blooms white oxide."""
    pos, up = w.obj(), w.sat(w.up())
    streak, rg, pits = WC.detail(w, sh, "Metal", pos)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", rg, 0.5), 0.08))
    sh.col = w.mix(sh.col, w.mix(GREY_FADE, BRONZE, w.term("bronze")), w.mul(w.term("fade"), 0.8, w.add(0.6, w.mul(up, 0.4)),
                                         w.add(0.8, w.mul(w.blot(pos, 0.4, 231.0, detail=1.0), 0.2))))
    sh.rough = w.lerp(sh.rough, 0.62, w.term("dull"))
    sh.metal = w.lerp(sh.metal, 0.3, w.term("dull"))
    sh.col = w.mix(sh.col, (112, 110, 106), w.mul(w.term("dull"), w.term("fade"), 0.25))     # a chalky bloom
    # scratched through to bright metal where lines and hands rub: the edges and the tops, as fine marks up close
    # and only their faint mean past a couple of metres (specks any further off alias into a mottle)
    edge = w.edge(0.006)
    near = w.fade(0.4, 1.6)
    rub = w.sat(w.add(w.mul(edge, 0.6), w.mul(up, 0.4)))
    # (fine, sparse and drawn out along the bars: round specks read as granite on the crossbar)
    marks = w.patches(pos, 0.0012, w.mul(w.term("scratch"), 0.05), seed=233.0, detail=2.0, soft=0.06,
                      stretch=(2.0, 14.0, 2.0))
    # gathered where hands, lines and the beach rub (soft patches), not an even grain over the whole tube
    rubbed = w.smooth(w.blot(pos, 0.12, 239.0, detail=1.5, stretch=(1.0, 3.0, 1.0)), 0.45, 0.7)
    marks = w.mul(marks, rubbed)
    sc = w.mul(w.lerp(w.mul(w.term("scratch"), 0.08), marks, near), rub)
    sc = w.sat(w.add(sc, w.mul(w.term("scratch"), edge, w.smooth(streak, 0.65, 0.85), 0.35, near)))
    sh.col = w.mix(sh.col, BRIGHT, w.mul(sc, 0.4))
    sh.metal = w.lerp(sh.metal, 1.0, sc)
    sh.rough = w.lerp(sh.rough, 0.4, sc)
    cr = w.crevice(0.03, 0.35, 0.9)
    ox = w.mul(w.term("oxide"), w.add(w.mul(sc, 0.8), w.mul(cr, 0.6)))
    sh.col = w.mix(sh.col, OXIDE, w.mul(w.sat(ox), 0.65))
    sh.metal = w.lerp(sh.metal, 0.0, w.sat(ox))
    sh.rough = w.lerp(sh.rough, 0.95, w.sat(ox))
    # neglected, the faded dye chalks to a white powder on what faces the sky, in broad soft drifts
    pw = w.mul(w.term("oxide"), w.add(0.35, w.mul(up, 0.65)), w.add(0.4, w.mul(w.smooth(w.blot(pos, 0.5, 235.0, detail=1.0), 0.35, 0.75), 0.6)))
    sh.col = w.mix(sh.col, (150, 147, 140), w.mul(w.sat(pw), 0.45))
    pits = w.mul(w.patches(pos, 0.0015, w.mul(w.term("oxide"), 0.06), seed=237.0, detail=2.0, soft=0.15), w.fade(0.5, 2.5))
    pits = w.mul(pits, rubbed)
    sh.col = w.mix(sh.col, OXIDE, w.mul(w.sat(w.add(pits, w.mul(w.term("oxide"), rubbed, 0.8, rub))), 0.55))                 # white pitting in the powder, up close
    sh.rough = w.lerp(sh.rough, 0.9, w.sat(pw))
    gr = w.mul(w.term("grime"), w.add(0.3, w.mul(up, 0.4), w.mul(cr, 0.6)))
    sh.col = w.mix(sh.col, (96, 90, 78), w.mul(w.sat(gr), 0.35))


def metal(w, sh, kind):
    """Stainless as the Catalina's; the castings' bare cast aluminium dulls to a matt grey and blooms white oxide in
    its crevices and pits, not over its whole face (the Catalina's base of 0.4 turned the small castings to granite)."""
    if kind == "stainless":
        WC.metal(w, sh, kind)
        # a neglected beach boat's wires and tangs go dull grey under salt-free grime and sunscreen (its rust term
        # starts only with neglect, so a kept boat's stay bright)
        sh.col = w.mix(sh.col, (120, 116, 108), w.mul(w.term("rust"), 0.35))
        sh.rough = w.lerp(sh.rough, 0.6, w.mul(w.term("rust"), 0.5))
        return
    if kind != "aluminium":
        return WC.metal(w, sh, kind)
    pos = w.obj()
    streak, rg, pits = WC.detail(w, sh, "Metal", pos)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", rg, 0.5), 0.08))
    cr = w.crevice(0.03, 0.35, 0.9)
    sh.rough = w.lerp(sh.rough, 0.6, w.term("dull"))
    sh.col = w.mix(sh.col, (150, 150, 146), w.mul(w.term("dull"), 0.3))          # matt grey, the casting's skin
    # neglected, grime darkens the casting to a grubby grey (its own tone, under the oxide), and white powder blooms
    # in the crevices and pits; a kept casting stays a clean matt grey
    # (soft and broad: round 3's even grey over a whole rudder head read as plastic, round 4's centimetre mottle and
    # specks as granite)
    gr = w.mul(w.term("grime"), w.add(0.45, w.mul(cr, 0.55), w.mul(w.blot(pos, 0.15, 127.0, detail=1.0), 0.25)))
    sh.col = w.mix(sh.col, (80, 76, 66), w.mul(w.sat(gr), 0.85))
    sh.rough = w.lerp(sh.rough, 0.8, w.sat(gr))
    ox = w.mul(w.term("oxide"), w.add(0.05, w.mul(cr, 1.0), w.mul(pits, 0.5, w.fade(0.4, 1.6)),
                                      w.mul(w.smooth(w.blot(pos, 0.1, 125.0, detail=1.0), 0.62, 0.85), 0.3)))
    sh.col = w.mix(sh.col, OXIDE, w.mul(w.sat(ox), 0.55))
    sh.metal = w.lerp(sh.metal, 0.0, w.sat(w.add(ox, w.mul(gr, 0.9))))
    sh.rough = w.lerp(sh.rough, 0.95, w.sat(ox))


DRESS = {"gelcoat": gelcoat, "tramp": tramp, "anodised": anodised, "metal": metal, "plastic": WC.plastic,
         "canvas": WC.canvas}


def used_materials():
    return WC.used_materials()


def dress(level="L0"):
    """Gives every material the build uses its finish and its wear, then sets them to `level`; returns the names
    dressed. Stops if the build uses a material no card covers."""
    import bpy
    used = used_materials()
    missing, _ = coverage(used)
    if missing:
        raise SystemExit(f"textures_hobie16.json covers no card or 'unweathered' entry for {missing}")
    idx = material_index()
    done = []
    for m in bpy.data.materials:
        if m.name not in used or m.name not in idx or m.get("h16_surface"):
            continue
        s, k = idx[m.name]
        finish(m)
        w = HW(m, s, k)
        sh = JW.Shader(w)
        DRESS[s](w, sh, k if s != "plastic" else "black")
        sh.finish()
        m["h16_surface"], m["h16_kind"] = s, k
        done.append(m.name)
    apply_level(level)
    return sorted(done)


def apply_level(level):
    """Sets every dressed material's wear terms to a level ("L0".."L4") or to (age, care)."""
    import bpy
    age, care = (LEVELS[level]["age"], LEVELS[level]["care"]) if isinstance(level, str) else level
    cache = {}
    for m in bpy.data.materials:
        if not m.get("h16_surface"):
            continue
        s0, k0 = m["h16_surface"], m["h16_kind"]
        for n in m.node_tree.nodes:
            if n.type == "VALUE" and n.name.startswith("wear:"):
                s, term = n.name[5:].split(".", 1)
                key = (s0, k0)
                if key not in cache:
                    cache[key] = amounts(s0, k0, age, care)
                if term not in cache[key]:
                    raise SystemExit(f"{m.name}: no amount for wear term {s}.{term} ({key})")
                n.outputs[0].default_value = cache[key][term]
    bpy.context.scene["h16_wear"] = level if isinstance(level, str) else f"{age},{care}"


def dressed():
    import bpy
    return sorted((m for m in bpy.data.materials if m.get("h16_surface")), key=lambda m: m.name)


def albedo_mode(mode):
    """"albedo": each dressed material renders its colour alone, for measuring; "id": each its own flat colour
    (JW.material_id, in name order); False: the shaders back."""
    for m in dressed():
        m["j_surface"] = m["h16_surface"]
    keep = JW.CARDS["unweathered"]
    try:
        JW.CARDS["unweathered"] = []
        JW.dressed = dressed
        JW.albedo_mode(mode)
    finally:
        JW.CARDS["unweathered"] = keep


def report(material_names):
    """The cards' coverage, the map and its budget, every level's amounts."""
    missing, extra = coverage(material_names)
    meta_path = os.path.join(OWN_DIR, "hobie16_detail.json")
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
