"""The frigate Commonwealth's wear (slice 15, docs/shipkit-15): how much of each kind of wear a level brings, and where
on her it falls.

    import weathering
    weathering.amounts("copper", "sheathing", 6.0, 0.5)   # {"brown": 1.0, ...}, no Blender needed
    weathering.dress()                                     # on a built frigate.blend: adds the maps and the wear
    weathering.apply_level("L2")                           # in a render: sets every material to a level (or (age, care))

The texture loop's five levels (Tools/texloop/levels.json) are fixed points of E1's Age (years) and Care (0 left to rot
.. 1 kept), and its two numbers (Tools/texloop/wear.py) split them into what the years do whatever the crew does
(time_k: fading, silvering, the grain worn proud) and what care takes away (dirt_k: chalk, grime, rust, mildew, weed).
amounts() turns those into each surface's own terms, 0 to 1, with the reasons in its comments; textures_1797.json says
what each level should look like and which of her materials each surface covers. dress() builds the patterns in each
material's nodes, scaled by a Value node per term ("wear:<term>"), so one build renders any level: apply_level() only
sets those values. The game's material (the import's, by E1's Age and Care) takes the same amounts, so the terms are kept
to what a pixel shader can do: noise, streaks run down from a row of sources, the height above the waterline, which way
a face looks, the camera's distance, a hash per sheet or plank, and the crevices (ambient occlusion here, a baked cavity
map in the game).

Most of her parts carry no UVs (slices 1 to 11 draw from flat colours), so every pattern is in metres in world space or
the part's own frame, box-projected; her linked copies (the guns, the carronades, the blocks) take world space for what
runs down and a per-object random for their tone, so no two guns rust alike. The deck draws from its Planking UV and the
sails from their cloths' UV0 and planform UV1 (sails.py).

The node helpers are the J-Class's (Tools/shipkit/jclass/weathering.py's W and Shader, loaded by path, not copied), with
the frigate's own maps (textures_1797.json 'maps').
"""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
import wear as loop  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


JW = _load("jclass_weathering", os.path.join(REPO, "Tools", "shipkit", "jclass", "weathering.py"))
CARDS = json.load(open(os.path.join(HERE, "textures_1797.json")))
SHARED_META = json.load(open(os.path.join(REPO, "Inputs", "boat-detail", "detail_textures.json")))
DECK = json.load(open(os.path.join(HERE, "deck_1797.json")))
LEVELS = {lv["id"]: lv for lv in loop.levels()}
LEVEL_IDS = ("L0", "L1", "L2", "L3", "L4")
SALT = CARDS["salt"]
FT = 0.3048
TAG = "f_surface"                 # the custom property a dressed material carries (and f_kind)

sat, ramp, _lin, chalky, runs = JW.sat, JW.ramp, JW._lin, JW.chalky, JW.runs


def refreshed(age, care):
    """How much a kept ship's routine (paint touched up in port, the decks holystoned each morning, the rigging
    re-tarred each refit) has undone the first-season marks: none in her first months, most when well kept."""
    return care ** 2 * ramp(age, 0.5, 2.0)


def renewed(age, care, every):
    """The age of a part a crew renews: on a kept ship every `every` years or so (on average half that old), on a
    neglected one hardly ever."""
    return min(age, 0.5 * every / max(care, 0.05))


def amounts(surface, kind, age, care):
    """Each wear term, 0 to 1, for one surface and kind at E1's Age (years) and Care (0..1). The loop's dirt_k takes a
    year to come up and then holds, so a first season's marks (gloss going, salt, smudges, tar drips) go as its square
    root, times `fresh` where a kept ship's routine takes them away again; what neglect alone does (rust through the
    paint, flaking, rot, mildew, weed) starts past a threshold of dirt_k that a kept ship never reaches."""
    t, d = loop.time_k(age, care), loop.dirt_k(age, care)
    young = 1.0 - math.exp(-age / 0.1)          # weeks in the weather: bare copper browns, fresh tar dulls
    fresh = 1.0 - 0.85 * refreshed(age, care)
    first = math.sqrt(d) * fresh
    if surface == "paint":
        # oil paint over oak, renewed on a kept ship every refit or two (but thirty years of coats build up)
        a = {"gloss": sat(0.9 * first + 0.3 * t * (1.0 - 0.5 * care)),   # linseed oil dulls fast in the sun
             "chalk": max(d * fresh, 0.15 * t),                           # the oil perishes, the pigment powders
             "salt": sat(1.6 * first) * SALT * (1.0 - 0.8 * care * ramp(age, 5.0, 25.0)),   # dries white
             "touchup": care * ramp(age, 5.0, 25.0),                       # an old kept side: touched up in patches
             "rust": SALT * ramp(d, 0.2, 0.85) ** 1.2,                    # the fastenings weep once care lapses
             "tar": sat(1.2 * first + 0.3 * ramp(d, 0.5, 0.95)),          # tar drips off the rigging above
             "scrape": ramp(d, 0.4, 0.95),                                # boats, fenders and cables at the wales
             "crack": ramp(d, 0.5, 0.95),                                 # old oil paint alligators and flakes
             "coats": 0.6 * t * care}                                     # thirty years of coats soften the grain
        if kind == "white":                                               # white lead yellows and greys in the hollows
            a.update(yellow=0.85 * t * (1.0 - 0.5 * refreshed(age, care)), salt=0.0)
        return a
    if surface == "copper":
        own = renewed(age, care, 8.0)                                     # a kept ship is recoppered every few years
        ot, od = loop.time_k(own, care), loop.dirt_k(own, care)
        oy = 1.0 - math.exp(-own / 0.1) if own > 0 else 0.0
        return {"brown": oy,                                                  # cuprite browns new copper within weeks
                "dark": sat(1.2 * ot + 0.8 * od) * oy,                    # then darker year by year
                "verdigris": SALT * sat(1.2 * od ** 2) * sat(0.3 + ot),   # green where it dries and wets, late
                "slime": sat(1.5 * math.sqrt(od)) * (1.0 - 0.7 * refreshed(age, care)),
                "weed": SALT * ramp(od, 0.45, 0.9),                       # copper's poison wasted: growth takes
                "barnacles": SALT * ramp(od, 0.6, 0.95),
                "lift": ramp(od, 0.6, 0.95),                              # worn thin, sheets lift at the laps
                "patchwork": care * ramp(age, 5.0, 25.0)}                 # renewed sheet by sheet: a quilt of shades
    if surface == "wood":
        silver = sat(3.0 * t)                                             # bare oak greys within a season
        a = {"silver": silver,
             "scrub": silver * care ** 3 * ramp(age, 0.2, 2.0),          # scrubbed: pale, the grain proud
             "dark": d ** 1.2,                                            # grime, algae and mildew in the grain
             "green": ramp(d, 0.45, 0.9),
             "stain": ramp(d, 0.3, 0.9),                                  # black iron stains round the bolts
             "checks": t * (1.0 - 0.5 * care),
             "raised": t,
             "tar": 0.0}
        if kind == "blocks":                                              # handled with tarry hands, oiled
            a.update(tar=sat(1.4 * first + 0.5 * t), silver=0.5 * silver, scrub=0.0)
        elif kind == "spar":                                              # scraped and oiled: an oil finish
            a = {"amber": t, "dull": sat(0.9 * first),
                 "fail": ramp(d, 0.45, 0.9),                              # the oil gone: grey checked wood
                 "tar": sat(1.2 * first + 0.4 * ramp(d, 0.4, 0.9)),       # tar runs down from the rigging
                 "dark": d ** 1.3, "checks": t * (1.0 - 0.6 * care)}
        return a
    if surface == "deck":
        silver = sat(3.0 * t)
        return {"silver": silver,
                "white": sat(2.5 * care ** 3 * ramp(age, 0.0, 3.0)) * (1.0 - d * d),   # holystoned each morning, paler each year
                "traffic": sat(first),                                    # grey where the crew walk and haul
                "dark": d ** 1.3,
                "tar": sat(1.3 * first) * (1.0 - 0.6 * care ** 2),        # drips and spots under the rigging
                "seams": ramp(d, 0.45, 0.95),                             # the pitch cracks and lifts
                "green": ramp(d, 0.5, 0.9),
                "raised": t}
    if surface == "rope":
        if kind == "tarred":
            own = renewed(age, care, 3.0)                                 # re-tarred each refit, renewed when worn
            ot, od = loop.time_k(own, care), loop.dirt_k(own, care)
            oy = 1.0 - math.exp(-own / 0.1) if own > 0 else 0.0
            return {"dull": sat(0.8 * oy + 0.3 * ot),                     # the tar's gloss goes within weeks
                    "brown": sat(0.6 * math.sqrt(od) + 0.6 * ot),         # and browns
                    "bleach": sat(1.2 * od) * SALT,                       # grey on top in the sun
                    "fibre": sat(1.3 * math.sqrt(od) + 0.2 * ot),         # worn through to the fibre
                    "rot": ramp(od, 0.55, 0.95),
                    "retar": care * ramp(age, 5.0, 25.0)}                 # tarred over and over: near black, glossy
        own = renewed(age, care, 2.0)
        rt, rd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"grey": sat(0.6 * math.sqrt(rd) + 0.45 * rt), "fuzz": sat(0.8 * math.sqrt(rd) + 0.3 * rt),
                "dark": rd, "mildew": ramp(rd, 0.5, 0.9)}
    if surface == "canvas":
        if kind == "tarpaulin":
            return {"dull": sat(young + 0.3 * t), "crack": ramp(d, 0.3, 0.9), "grey": sat(1.2 * d)}
        own = renewed(age, care, 4.0) if kind == "sail" else age          # a kept ship bends a newer suit
        st, sd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"dinge": sat(0.8 * math.sqrt(sd)), "grime": sat(1.2 * math.sqrt(sd)),
                "mildew": ramp(sd, 0.3, 0.85), "yellow": 0.5 * st + 0.75 * care * ramp(age, 5.0, 25.0),
                "patches": sat(1.4 * sd + 0.5 * ramp(st, 0.3, 0.8) + 0.9 * care * ramp(age, 5.0, 25.0))
                if kind == "sail" else 0.0,                               # (a kept ship's old suit, patched)
                "stain": ramp(sd, 0.4, 0.9)}
    if surface == "iron":
        blacked = 0.85 * care * sat(age / 0.5)                            # re-blacked each refit on a kept ship
        if kind == "lead":
            return {"dull": sat(2.0 * t + young), "oxide": sat(1.5 * d), "pits": ramp(d, 0.5, 0.95)}
        kept = 1.0 - 0.8 * blacked * ramp(age, 1.0, 5.0)               # a kept ship's refits black it over again
        return {"brown": sat(1.6 * first + 0.3 * t * (1.0 - blacked)) * kept,   # the blacking browns at the edges
                "bloom": SALT * sat(1.4 * d) * (1.0 - 0.7 * care ** 2) * kept,   # rust blooms through
                "rust": SALT * ramp(d, 0.4, 0.9),                         # the black gone, flaking orange-brown
                "skin": t * blacked}                                      # coats over the casting's skin
    if surface == "bright":
        if kind == "gilt":                                                # re-gilt on a kept ship
            return {"dull": sat(1.6 * first + 0.3 * t * (1.0 - care)), "dirt": sat(2.0 * first),
                    "regilt": t * care * ramp(age, 5.0, 20.0),
                    "chips": ramp(d, 0.3, 0.8), "gone": ramp(d, 0.6, 0.95)}
        polish = 0.85 * care * sat(age / 3.0)
        return {"patina": (1.0 - math.exp(-age / 0.4)) * (1.0 - polish), "dark": sat(t + d),
                "verdigris": SALT * ramp(d, 0.5, 0.9)}
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
                    raise SystemExit(f"textures_1797.json: {n} is in two cards ({out[n]} and {(s, k)})")
                out[n] = (s, k)
    return out


def coverage(material_names):
    """The materials the build makes that no card, 'unweathered' or 'below_decks' entry covers, and the cards'
    outside materials the build does not make (both must be empty)."""
    idx = material_index()
    un = set(CARDS["unweathered"])
    below = set(CARDS["below_decks"]["names"])
    names = set(material_names)
    return sorted(names - set(idx) - un - below), sorted((set(idx) | un) - names)


# ================================================================================================ Blender
RUST = (122, 62, 34)
RUST_DARK = (66, 36, 22)
RUST_ORANGE = (150, 80, 38)
TAR = (26, 20, 15)
SALT_WHITE = (206, 204, 196)
GRIME = (70, 62, 50)
SILVER = (148, 147, 144)
DECK_SILVER = (154, 145, 128)      # pine greys warmer than oak
SCRUBBED = (218, 200, 164)
HOLYSTONED = (228, 214, 184)
MILDEW = (34, 36, 30)
ALGAE = (58, 70, 40)
GREY_OAK = (118, 116, 112)
OAK_BARE = (150, 118, 82)
COPPER_NEW = (226, 134, 104)
COPPER_BROWN = (146, 82, 30)
COPPER_DARK = (62, 42, 32)
VERDIGRIS = (92, 150, 122)
VERDIGRIS_PALE = (150, 180, 150)
FELT = (24, 20, 16)
SLIME = (82, 72, 42)
WEED = (50, 68, 32)
BARNACLE = (150, 144, 128)
BOLE = (140, 52, 32)
OXIDE_WHITE = (200, 200, 194)
HEMP_GREY = (128, 122, 110)
CANVAS_PATCH = (226, 214, 184)


class W(JW.W):
    """The J-Class's node helpers with this ship's maps, world positions and a per-object random."""

    def __init__(self, mt, surface, kind):
        super().__init__(mt, surface, kind)
        self._info = None

    def world(self):
        return self.geo("Position")

    def rnd(self):
        """0..1 per object: the linked guns, carronades and blocks each get their own."""
        if self._info is None:
            self._info = self.N.new("ShaderNodeObjectInfo")
        return self._info.outputs["Random"]

    def image(self, name, vec, tile_m, box=True):
        import bpy
        path = map_path(name)
        img = bpy.data.images.get(os.path.basename(path)) or bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "Non-Color"

        def sample(u, v):
            tx = self.N.new("ShaderNodeTexImage")
            tx.image = img
            tx.interpolation = "Linear"
            self.L.new(self.comb(self.m("DIVIDE", u, tile_m[0]), self.m("DIVIDE", v, tile_m[1]), 0.0),
                       tx.inputs["Vector"])
            return tx.outputs["Color"]

        x, y, z = self.sep(vec)
        if not box:
            col = sample(x, y)
        else:
            if self._nrm is None:
                self._nrm = self.N.new("ShaderNodeTexCoord")
            nx, ny, nz = self.sep(self._nrm.outputs["Normal"])
            wx, wy, wz = (self.m("POWER", self.m("ABSOLUTE", c), 4.0) for c in (nx, ny, nz))
            tot = self.add(wx, wy, wz, 1e-6)
            col = None
            for wgt, (u, v) in ((wz, (x, y)), (wy, (x, z)), (wx, (y, z))):
                term = self.scale(sample(u, v), self.m("DIVIDE", wgt, tot))
                col = term if col is None else self._vadd(col, term)
        s = self.N.new("ShaderNodeSeparateColor")
        self.L.new(col, s.inputs[0])
        return s.outputs[0], s.outputs[1], s.outputs[2]

    def side_uv(self):
        """World (along, up) on a side, (along, across) under her: the sheathing's and the paint's 'girth' frame,
        chosen by which way the face looks (|normal z| over 0.7: the bottom's flat)."""
        x, y, z = self.sep(self.world())
        nz = self.m("ABSOLUTE", self.sep(self.geo("Normal"))[2])
        flat = self.m("GREATER_THAN", nz, 0.7)
        return x, self.lerp(z, y, flat)


def map_path(name):
    m = CARDS["maps"]
    if name in m["own"]:
        return os.path.join(REPO, "Inputs", "frigate-detail", f"T_Frigate_{name}_M.png")
    if name in m["jclass"]:
        return os.path.join(REPO, "Inputs", "jclass-detail", f"T_JClass_{name}_M.png")
    return os.path.join(REPO, "Inputs", "boat-detail", f"T_Detail_{name}_M.png")


def tile_of(name):
    m = CARDS["maps"]
    c = m["own"].get(name) or m["jclass"].get(name) or m["shared"][name]
    return (c["tile_mm"][0] / 1000.0, c["tile_mm"][1] / 1000.0)


def fade_of(name):
    m = CARDS["maps"]
    c = m["own"].get(name) or m["jclass"].get(name)
    if c:
        return tuple(c.get("fade_m", (1.0, 4.0)))
    return tuple(SHARED_META.get(name, {}).get("fade_m", (1.0, 4.0)))


def detail(w, sh, name, vec, amp_m=None, box=True, pits=False):
    """A detail map's (r, g, b), its B channel added as a bump of amp_m metres that fades with the camera's distance as
    the game fades it (a height about 0.5, or with pits a depth from 0)."""
    r, g, b = w.image(name, vec, tile_of(name), box=box)
    if amp_m is not None:
        h = w.mul(b, -1.0) if pits else w.m("SUBTRACT", b, 0.5)
        sh.bump(w.mul(h, amp_m, w.fade(*fade_of(name))))
    return r, g, b


def cracks(w, vec, cell_m, width):
    """1 in the cracks of an alligatored film (Voronoi cells about cell_m across, cracks `width` of a cell wide)."""
    vo = w.N.new("ShaderNodeTexVoronoi")
    vo.feature = "DISTANCE_TO_EDGE"
    vo.voronoi_dimensions = "3D"
    w.L.new(vec, vo.inputs["Vector"])
    vo.inputs["Scale"].default_value = 1.0 / cell_m
    vo.inputs["Randomness"].default_value = 0.9
    return w.m("SUBTRACT", 1.0, w.smooth(vo.outputs["Distance"], 0.0, width))


def flakes(w, vec, cell_m, amount, cluster_m, seed, stretch=None):
    """(flaked, crack): old paint (or oil, or gold leaf) let go cell by cell. The film's cracks are Voronoi cells about
    cell_m across; a cell flakes off whole when its own random falls under the local share, which is `amount` (socket or
    number) gathered into clusters about cluster_m across (a blot), so bare patches are ragged groups of whole flakes,
    never smooth blotches. crack is 1 in the cracks between cells. stretch (sx, sy, sz) lengthens the cells per axis
    (along a spar's grain)."""
    if stretch:
        mp = w.N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = tuple(1.0 / s_ for s_ in stretch)
        w.L.new(vec, mp.inputs["Vector"])
        vec = mp.outputs[0]
    vo = w.N.new("ShaderNodeTexVoronoi")
    vo.feature = "F1"
    vo.voronoi_dimensions = "4D"
    vo.inputs["W"].default_value = seed
    w.L.new(vec, vo.inputs["Vector"])
    vo.inputs["Scale"].default_value = 1.0 / cell_m
    vo.inputs["Randomness"].default_value = 0.9
    ed = w.N.new("ShaderNodeTexVoronoi")
    ed.feature = "DISTANCE_TO_EDGE"
    ed.voronoi_dimensions = "4D"
    ed.inputs["W"].default_value = seed
    w.L.new(vec, ed.inputs["Vector"])
    ed.inputs["Scale"].default_value = 1.0 / cell_m
    ed.inputs["Randomness"].default_value = 0.9
    cell = w.lum(vo.outputs["Color"])
    local = w.sat(w.mul(w.sock(amount), w.add(0.2, w.mul(w.blot(vec, cluster_m, seed + 0.3, detail=2.0), 1.6))))
    flaked = w.m("LESS_THAN", cell, local)
    crack = w.m("SUBTRACT", 1.0, w.smooth(ed.outputs["Distance"], 0.0, 0.07))
    return flaked, crack


# ------------------------------------------------------------------------------------------------ the surfaces
def paint(w, sh, kind):
    pos, wpos = w.obj(), w.world()
    x, v = w.side_uv()
    z = w.wz()
    r, g, _ = detail(w, sh, "WoodVarnish", pos, w.mul(0.00012, w.add(0.4, w.term("coats"))))
    # the oak's grain shows through the paint (more through thirty years of coats, which also soften it)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(w.m("SUBTRACT", r, 0.5), 0.12)))
    # the oil's gloss goes in the sun; chalk greys and lifts each colour (the black to a brownish grey, the ochre and
    # red paler), most on what faces the sky and high up, washed down the side in long soft streaks
    sh.rough = w.lerp(sh.rough, 0.85, w.term("gloss"))
    washed = w.blot(wpos, 0.3, 2.0, detail=1.0, stretch=(1.0, 1.0, 7.0))
    high = w.smooth(z, 0.0, 6.0)
    ch = w.mul(w.term("chalk"), w.add(0.55, w.mul(washed, 0.2), w.mul(high, 0.2)),
               w.add(0.75, w.mul(w.sat(w.up()), 0.25)))
    tint = {"black": (88, 88, 90), "ochre": (226, 196, 140), "red": (176, 104, 84), "white": (220, 216, 204)}[kind]
    sh.col = w.mix(sh.col, chalky(w, sh.col, tint, lift=0.32 if kind == "black" else 0.5), w.sat(ch))
    # an old kept side is touched up where it chafes rather than painted whole: fresh glossy patches, deeper in tone,
    # over the year-old coat (the first-cruise ship has one coat, all the same age)
    touch = w.mul(w.term("touchup"), w.patches(wpos, 0.6, 0.35, seed=52.0, detail=1.0, stretch=(4.0, 1.0, 1.0)))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.85), w.mul(touch, 0.6))
    sh.rough = w.lerp(sh.rough, 0.22, touch)
    if kind == "white":
        sh.col = w.mix(sh.col, w.scale(sh.col, (1.0, 0.94, 0.78)), w.term("yellow"))
    cr = w.crevice(0.15)
    dry = w.smooth(z, 0.05, 0.3)                                       # nothing dries or runs under the water
    # dirt settles in the carving's hollows and the strakes' steps
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.45), w.mul(w.sat(w.add(w.term("chalk"), w.term("tar"))), cr, 0.6))
    # salt dries white: in runs under the ports and along the top of each wale (a face looking up), on the side only
    srow = w.m("FLOOR", w.m("DIVIDE", v, 1.3))
    salt_run = runs(w, x, w.m("SUBTRACT", w.mul(w.add(srow, 1.0), 1.3), v), srow, 1.1, 0.5, 0.08, (0.3, 1.2), 41.0,
                    jitter=0.7)
    salt = w.mul(w.term("salt"), dry, w.sat(w.add(w.mul(salt_run, 0.7), w.mul(w.sat(w.mul(w.up(), 2.0)), 0.5),
                                                 w.mul(w.blot(wpos, 0.5, 42.0), 0.25))))
    sh.col = w.mix(sh.col, SALT_WHITE, w.mul(w.sat(salt), 0.75))
    # rust weeps down from the fastenings: a row at every frame (2 ft apart), one source in each strake
    strake = 0.28
    row = w.m("FLOOR", w.m("DIVIDE", v, strake))
    below = w.m("SUBTRACT", w.mul(w.add(row, 1.0), strake), v)          # metres under the strake's upper edge
    frame = dict(pitch=0.61, share=0.35, width=0.025, length=(0.2, 1.1), seed=11.0, start=0.2, on_lines=True,
                 along=v)
    rust_run = w.m("MAXIMUM", runs(w, x, below, row, **frame),
                   runs(w, x, w.add(below, strake), w.add(row, 1.0), **frame))
    rust_spot = w.mul(w.patches(wpos, 0.012, 0.25, seed=12.0, detail=1.0), w.sat(w.mul(cr, 1.5)))
    rust = w.mul(w.term("rust"), dry, w.sat(w.add(w.mul(rust_run, 1.4), rust_spot)))
    # tar drips off the rigging: long thin black runs from high up, and spots on what faces the sky
    tar_run = runs(w, x, w.m("SUBTRACT", 8.0, v), 0.0, 0.35, 0.18, 0.012, (0.6, 3.0), 23.0, start=6.0, jitter=0.9)
    tar_spot = w.mul(w.patches(wpos, 0.01, 0.12, seed=24.0, detail=1.0), w.sat(w.up()))
    tar = w.mul(w.term("tar"), w.sat(w.add(tar_run, tar_spot)))
    # scrapes where boats, fenders and the cables work: along the wales low on the side, on edges and corners
    low = w.m("SUBTRACT", 1.0, w.smooth(z, 2.0, 4.0))
    edges = w.edge(0.01)
    scrape = w.mul(w.term("scrape"), w.sat(w.add(
        w.mul(w.patches(wpos, 0.08, 0.22, seed=31.0, detail=3.0, stretch=(5.0, 1.0, 1.0)), low),
        w.mul(edges, w.patches(pos, 0.03, 0.5, seed=32.0, detail=3.0)))))
    # alligatored old paint: cracks to the wood, then whole cells lifting off in ragged groups, more high up in the sun
    flake, crk_c = flakes(w, pos, 0.012, w.mul(w.term("crack"), w.add(0.35, w.mul(high, 0.25))), 0.25, 33.0)
    crk = w.mul(crk_c, w.term("crack"), w.fade(2.0, 12.0))
    bare = w.sat(w.add(scrape, flake))
    oak = w.mix(OAK_BARE, GREY_OAK, w.sat(w.add(w.term("chalk"), 0.3)))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.4), crk)
    sh.col = w.mix(sh.col, oak, bare)
    sh.col = w.mix(sh.col, w.mix(RUST, RUST_DARK, w.noise(wpos, 0.01, 3.0)), w.sat(rust))
    sh.col = w.mix(sh.col, TAR, w.mul(w.sat(tar), 0.85))
    sh.rough = w.lerp(sh.rough, 0.9, w.sat(w.add(bare, rust, crk)))
    sh.rough = w.lerp(sh.rough, 0.35, w.mul(w.sat(tar), 0.6))
    sh.bump(w.add(w.mul(bare, -0.0003), w.mul(crk, -0.0002), w.mul(w.sat(tar), 0.0004)))
    sh.finish()


def copper(w, sh, kind):
    wpos = w.world()
    x, v = w.side_uv()
    z = w.wz()
    sw, sh_ = CARDS["surfaces"]["copper"]["pattern_mm"]["sheet"]
    sw, sh_ = sw / 1000.0, sh_ / 1000.0
    # the sheets: rows sh_ high (up the side, across under her), each row's seams half a sheet on from the last
    row = w.m("FLOOR", w.m("DIVIDE", v, sh_))
    xs = w.add(w.m("DIVIDE", x, sw), w.mul(w.m("FRACT", w.mul(row, 0.5)), 1.0))
    col_i = w.m("FLOOR", xs)
    tone, tc = w.hash(w.comb(row, col_i, 0.0), 5.0)
    t2, t3, _ = w.sep(tc)
    fu, fv = w.m("FRACT", xs), w.m("FRACT", w.m("DIVIDE", v, sh_))
    lap_m = 0.038
    lap = w.sat(w.add(w.m("LESS_THAN", w.mul(fu, sw), lap_m * 0.25), w.m("GREATER_THAN", w.mul(fv, sh_), sh_ - lap_m * 0.25)))
    # the nails: a row round each sheet's edge, 1.5 in apart
    near = w.fade(1.0, 4.0)
    nail_u = w.m("LESS_THAN", w.m("ABSOLUTE", w.m("SUBTRACT", w.m("FRACT", w.m("DIVIDE", x, 0.038)), 0.5)), 0.12)
    nail_v = w.m("LESS_THAN", w.m("ABSOLUTE", w.m("SUBTRACT", w.m("FRACT", w.m("DIVIDE", v, 0.038)), 0.5)), 0.12)
    on_edge_u = w.m("LESS_THAN", w.m("ABSOLUTE", w.m("SUBTRACT", w.mul(fv, sh_), sh_ - 0.019)), 0.006)
    on_edge_v = w.m("LESS_THAN", w.m("ABSOLUTE", w.m("SUBTRACT", w.mul(fu, sw), 0.019)), 0.006)
    nails = w.mul(w.sat(w.add(w.mul(nail_u, on_edge_u), w.mul(nail_v, on_edge_v))), near)
    r, g, _ = detail(w, sh, "Metal", wpos, 0.00003)
    # new copper: salmon, each sheet a little different; browned within weeks, darker with the years
    new = w.mix(COPPER_NEW, (238, 156, 124), tone)
    sh.col = w.mix(w.rgb(_lin(COPPER_NEW)), new, 0.8)
    brown = w.mix(COPPER_BROWN, (156, 92, 40), t2)
    sh.col = w.mix(sh.col, brown, w.mul(w.term("brown"), w.add(0.94, w.mul(t3, 0.06))))
    sh.col = w.mix(sh.col, w.mix(COPPER_DARK, (84, 54, 40), tone), w.mul(w.term("dark"), w.add(0.6, w.mul(t2, 0.4))))
    # a kept ship's sheets renewed one by one over the years: some new and bright, some dark, in a quilt
    quilt = w.m("GREATER_THAN", t3, 0.8)                                # a sheet in five renewed: bright among the old
    sh.col = w.mix(sh.col, w.mix(w.mix(COPPER_DARK, (70, 46, 34), tone), w.mix(COPPER_NEW, COPPER_BROWN, w.mul(t2, 0.5)),
                                 quilt), w.mul(w.term("patchwork"), w.add(0.7, w.mul(tone, 0.25))))
    sh.metal = w.lerp(sh.metal, 0.55, w.term("brown"))
    sh.rough = w.lerp(w.m("MAXIMUM", sh.rough, 0.38), 0.6, w.term("brown"))   # new sheets: a soft bright sheen
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(w.m("SUBTRACT", r, 0.5), 0.15)))
    # the laps and nail heads catch dirt (or shine where new)
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.6), w.mul(w.add(lap, w.mul(nails, 0.7)), w.add(0.3, w.term("dark"))))
    sh.bump(w.add(w.mul(lap, 0.0008), w.mul(nails, 0.0006)))
    # green verdigris where she dries and wets: a band about the waterline, streaks up, the laps first
    splash = w.mul(w.smooth(z, -0.6, -0.05), w.m("SUBTRACT", 1.0, w.smooth(z, 0.6, 1.4)))
    streak = w.blot(wpos, 0.15, 7.0, detail=2.0, stretch=(1.0, 1.0, 6.0))
    vg = w.mul(w.term("verdigris"), w.sat(w.add(w.mul(splash, w.add(0.6, w.mul(streak, 0.8))), w.mul(lap, 0.4),
                                                w.mul(w.blot(wpos, 0.4, 8.0), 0.7))))
    sh.col = w.mix(sh.col, w.mix(VERDIGRIS, VERDIGRIS_PALE, streak), w.sat(vg))
    sh.metal = w.lerp(sh.metal, 0.0, w.sat(vg))
    sh.rough = w.lerp(sh.rough, 0.9, w.sat(vg))
    # sheets lifting at the laps (worn thin): the tarred felt under them shows black
    lifted = w.mul(w.term("lift"), w.m("LESS_THAN", t3, 0.12), w.sat(w.add(w.m("SUBTRACT", 1.0, w.smooth(fv, 0.0, 0.5)),
                                                                              w.mul(w.blot(wpos, 0.3, 9.0), 0.4))))
    sh.col = w.mix(sh.col, FELT, w.mul(w.sat(lifted), 0.85))
    sh.bump(w.mul(w.sat(lifted), 0.003))
    # slime, weed and barnacles in a band about the waterline (she floats moored, a little light)
    line = w.mul(w.smooth(z, -0.5, -0.05), w.m("SUBTRACT", 1.0, w.smooth(z, 0.05, 0.25)))
    slime = w.mul(line, w.term("slime"), w.add(0.4, w.mul(w.blot(wpos, 0.3, 20.0), 0.6)))
    band = w.mul(w.smooth(z, -1.4, -0.3), w.m("SUBTRACT", 1.0, w.smooth(z, 0.0, 0.2)))
    grow = w.mul(band, w.term("weed"), w.add(0.3, w.mul(w.blot(wpos, 0.25, 21.0), 1.0)))
    sh.col = w.mix(sh.col, SLIME, w.mul(w.sat(slime), 0.8))
    sh.col = w.mix(sh.col, w.mix(SLIME, WEED, w.smooth(z, -0.8, -0.1)), w.sat(grow))
    deep = w.m("SUBTRACT", 1.0, w.smooth(z, -0.6, -0.1))
    colony = w.add(0.3, w.mul(w.blot(wpos, 0.5, 25.0), 1.4))
    bar = w.mul(w.patches(wpos, 0.015, w.mul(w.term("barnacles"), 0.4, colony), seed=26.0, soft=0.02, detail=1.0),
                deep, band)
    sh.col = w.mix(sh.col, BARNACLE, bar)
    wet = w.sat(w.add(slime, grow, bar))
    sh.metal = w.lerp(sh.metal, 0.0, wet)
    sh.rough = w.lerp(sh.rough, 0.95, wet)
    sh.bump(w.mul(bar, 0.005))
    sh.finish()


def wood(w, sh, kind):
    pos, wpos = w.obj(), w.world()
    rnd = w.rnd()
    if kind == "spar":
        r, g, b = detail(w, sh, "Oak", pos, 0.00015)
        grain = w.m("SUBTRACT", r, 0.5)
        sh.col = w.scale(sh.col, w.add(1.0, w.mul(grain, 0.35)))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.85, 0.7, 0.5)), w.mul(w.term("amber"), 0.6))
        sh.rough = w.lerp(sh.rough, 0.8, w.term("dull"))
        fail, _ = flakes(w, pos, 0.02, w.mul(w.term("fail"), 0.7), 0.4, 51.0, stretch=(1.0, 1.0, 5.0))
        sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(GREY_OAK)), w.add(1.0, w.mul(grain, 0.5))), fail)
        sh.rough = w.lerp(sh.rough, 0.9, fail)
        # tar off the rigging: smudges and drips where the ropes work (the spars' frames differ, a yard's local z is its
        # mast's, so in world space: drips run down a mast's vertical faces, spots on everything)
        side = w.m("SUBTRACT", 1.0, w.m("ABSOLUTE", w.sep(w.geo("Normal"))[2]))
        drip = w.mul(side, w.patches(wpos, 0.012, 0.12, seed=52.0, detail=1.0, stretch=(1.0, 1.0, 12.0)))
        spot = w.patches(wpos, 0.01, 0.06, seed=58.0, detail=1.0)
        tar = w.mul(w.term("tar"), w.sat(w.add(drip, spot)))
        sh.col = w.mix(sh.col, TAR, w.mul(tar, 0.8))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.5), w.mul(w.term("dark"), w.crevice(0.1), 0.7))
        chk = w.mul(g, w.term("checks"), w.fade(1.0, 5.0))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.5), w.sat(w.mul(chk, 1.5)))
        sh.finish()
        return
    r, g, b = detail(w, sh, "Oak", pos, w.mul(0.0003, w.add(0.3, w.term("raised"))))
    grain = w.m("SUBTRACT", r, 0.5)
    tone = w.add(1.0, w.mul(grain, 0.6))
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(grain, 0.5), w.mul(w.m("SUBTRACT", rnd, 0.5), 0.12)))
    exposed = w.add(0.6, w.mul(w.sat(w.up()), 0.4))
    sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(SILVER)), tone), w.mul(w.term("silver"), 0.85, exposed))
    sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(SCRUBBED)), tone), w.mul(w.term("scrub"), 0.9, exposed))
    cr = w.crevice(0.12, 0.4, 0.95)
    soft = w.m("SUBTRACT", 1.0, w.smooth(r, 0.45, 0.75))
    dark = w.mul(w.term("dark"), w.sat(w.add(0.25, w.mul(soft, 0.35), w.mul(cr, 0.5),
                                             w.mul(w.blot(wpos, 0.3, 53.0), 0.3))))
    sh.col = w.mix(sh.col, MILDEW, w.sat(dark))
    green = w.mul(w.term("green"), w.sat(w.add(w.mul(cr, 0.7), w.mul(w.sat(w.up()), 0.4),
                                               w.mul(w.blot(wpos, 0.5, 54.0), 0.4))))
    sh.col = w.mix(sh.col, ALGAE, w.mul(w.sat(green), 0.7))
    # black iron stains round the bolts (tannin and iron): small dark spots with a soft halo
    stain = w.mul(w.term("stain"), w.patches(pos, 0.02, 0.12, seed=55.0, detail=1.0, soft=0.2))
    sh.col = w.mix(sh.col, (30, 28, 30), w.mul(stain, 0.8))
    if kind == "blocks":
        tar = w.mul(w.term("tar"), w.sat(w.add(0.5, w.mul(w.blot(pos, 0.03, 56.0), 0.6), w.mul(cr, 0.4))))
        sh.col = w.mix(sh.col, w.mix(w.scale(sh.col, 0.35), TAR, 0.5), w.mul(w.sat(tar), 0.85))
        sh.rough = w.lerp(sh.rough, 0.45, w.mul(w.sat(tar), 0.6))
    chk = w.mul(g, w.term("checks"), w.fade(1.0, 5.0), w.patches(pos, 0.3, 0.4, seed=57.0, detail=2.0, soft=0.12))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.45), w.sat(w.mul(chk, 1.5)))
    sh.rough = w.lerp(sh.rough, 0.9, w.mul(w.term("silver"), 0.6))
    sh.finish()


def deck_surface(w, sh, kind):
    pos, wpos = w.obj(), w.world()
    pu, pv, _ = w.sep(w.uv("Planking"))
    pl = DECK["deck"]["planking"]
    pitch = pl["width_in"] * FT / 12.0
    plen = pl["length_beams"] * 0.8312        # the waist's beams are 0.8312 m apart (build.json deck.waist)
    # the seams: deck.planks_material lets its roughness up by 0.2 in a seen seam (0.72 on the wood)
    seam = w.sat(w.m("DIVIDE", w.m("SUBTRACT", sh.rough, 0.72), 0.2))
    r, g, b = detail(w, sh, "Oak", w.comb(pu, pv, 0.0), w.mul(0.0003, w.add(0.3, w.term("raised"))), box=False)
    grain = w.m("SUBTRACT", r, 0.5)
    tone = w.add(1.0, w.mul(grain, 0.5))
    row = w.m("FLOOR", w.m("DIVIDE", pv, pitch))
    piece = w.m("FLOOR", w.add(w.m("DIVIDE", pu, plen), w.mul(row, 0.37)))
    ptone, _ = w.hash(w.comb(row, piece, 0.0), 61.0)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(grain, 0.3), w.mul(w.m("SUBTRACT", ptone, 0.5), 0.1)))
    sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(DECK_SILVER)), tone), w.mul(w.term("silver"), 0.8))
    sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(HOLYSTONED)), tone), w.mul(w.term("white"), 0.85))
    # the crew's traffic: the gangways and round the capstan, the main hatch and the guns (greyer, darker)
    path = w.blot(wpos, 1.2, 62.0, detail=1.0, stretch=(3.0, 1.0, 1.0))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.78, 0.76, 0.74)), w.mul(w.term("traffic"), w.add(0.2, w.mul(path, 0.6))))
    cr = w.crevice(0.2, 0.4, 0.95)
    along = w.blot(w.comb(pu, pv, 0.0), 0.06, 63.0, detail=2.0, stretch=(14.0, 1.0, 1.0))
    soft = w.m("SUBTRACT", 1.0, w.smooth(r, 0.45, 0.75))
    dark = w.mul(w.term("dark"), w.sat(w.add(0.3, w.mul(soft, 0.3), w.mul(ptone, 0.3), w.mul(along, 0.3),
                                             w.mul(cr, 0.4))))
    green = w.sat(w.add(w.mul(cr, 0.8), w.mul(w.blot(wpos, 0.8, 64.0, stretch=(4.0, 1.0, 1.0)), 0.4)))
    sh.col = w.mix(sh.col, w.mix(MILDEW, ALGAE, w.mul(green, w.term("green"))), w.sat(dark))
    # tar: drips and spots under the rigging (by the rails, the masts and the pin rails)
    spots = w.patches(wpos, 0.015, w.mul(w.term("tar"), 0.18), seed=65.0, detail=1.0, soft=0.03)
    sh.col = w.mix(sh.col, TAR, w.mul(spots, 0.85))
    # the pitch seams crack and lift: pale grey patches of seam standing proud
    fail = w.mul(seam, w.patches(pos, 0.2, w.mul(w.term("seams"), 0.6), seed=66.0, detail=2.0))
    sh.col = w.mix(sh.col, (96, 92, 86), fail)
    sh.bump(w.mul(fail, 0.0012))
    sh.rough = w.lerp(sh.rough, 0.9, w.term("silver"))
    sh.finish()


def rope(w, sh, kind):
    pos, wpos = w.obj(), w.world()
    r, g, b = detail(w, sh, "Manila", pos, 0.0002)
    fib = w.m("SUBTRACT", r, 0.5)
    up = w.sat(w.up())
    if kind == "tarred":
        sh.rough = w.lerp(0.25, w.m("MAXIMUM", sh.rough, 0.75), w.term("dull"))
        sh.col = w.mix(sh.col, (60, 44, 30), w.mul(w.term("brown"), 0.8))
        sh.col = w.mix(sh.col, (30, 24, 19), w.mul(w.term("retar"), 0.65))
        sh.rough = w.lerp(sh.rough, 0.3, w.mul(w.term("retar"), 0.5))
        fibre = w.patches(pos, 0.05, w.mul(w.term("fibre"), 0.45), seed=71.0, detail=2.0, stretch=(1.0, 1.0, 3.0))
        sh.col = w.mix(sh.col, w.scale(w.rgb(_lin((96, 78, 56))), w.add(1.0, w.mul(fib, 0.6))), fibre)
        sh.col = w.mix(sh.col, (112, 108, 100), w.mul(w.term("bleach"), w.add(0.45, w.mul(up, 0.55)), 0.8))
        # rotten: the tar long gone, the yarns grey and furred, mildewed in the lay
        rot = w.mul(w.term("rot"), w.add(0.4, w.mul(w.blot(wpos, 0.2, 72.0), 0.6)))
        sh.col = w.mix(sh.col, w.mix((118, 114, 102), MILDEW, w.mul(w.crevice(0.03), 0.5)), w.mul(rot, 0.7))
        sh.rough = w.lerp(sh.rough, 0.95, w.sat(w.add(fibre, w.term("bleach"))))
    else:
        sh.col = w.scale(sh.col, w.add(1.0, w.mul(fib, 0.5)))
        sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(HEMP_GREY)), w.add(1.0, w.mul(fib, 0.4))), w.mul(w.term("grey"), 0.85))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.55), w.mul(w.term("dark"), w.add(0.3, w.mul(w.crevice(0.05), 0.7))))
        mil = w.patches(pos, 0.006, w.mul(w.term("mildew"), 0.3), seed=73.0, soft=0.03, detail=1.0)
        sh.col = w.mix(sh.col, MILDEW, w.mul(mil, 0.8))
        sh.rough = w.lerp(sh.rough, 0.98, w.term("fuzz"))
        sh.bump(w.mul(g, w.term("fuzz"), 0.0002))
    sh.finish()


def canvas(w, sh, kind):
    pos, wpos = w.obj(), w.world()
    if kind == "tarpaulin":
        r, g, b = detail(w, sh, "Cotton", pos, 0.00015)
        sh.rough = w.lerp(0.4, 0.85, w.term("dull"))
        crk = w.mul(cracks(w, pos, 0.03, 0.06), w.term("crack"))
        sh.col = w.mix(sh.col, (112, 104, 88), w.mul(crk, 0.8))
        # the tar perishes in the sun to a dull brown-grey, most on top
        sh.col = w.mix(sh.col, (110, 104, 94), w.mul(w.term("grey"), w.add(0.6, w.mul(w.sat(w.up()), 0.4)), 0.85))
        sh.finish()
        return
    if kind == "sail":
        u0, v0, _ = w.sep(w.uv("UV0"))
        _, v1, _ = w.sep(w.uv("UV1"))
        uvm = w.comb(u0, v0, 0.0)
        r, g, b = detail(w, sh, "Cotton", uvm, 0.0001, box=False)
    else:
        u0, v0 = None, None
        uvm = pos
        r, g, b = detail(w, sh, "Cotton", pos, 0.0001)
    weave = w.m("SUBTRACT", g, 0.5)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(weave, 0.15)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (1.0, 0.95, 0.82)), w.term("yellow"))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.76, 0.76, 0.74)), w.mul(w.term("dinge"), w.add(0.6, w.mul(w.blot(uvm, 1.5, 81.0), 0.4))))
    if kind == "sail":
        # grime along the foot (handled, washed by the bow wave's spray) and under the yard (chafe, tar off the
        # jackstay and the robands); stains running down from the head
        foot = w.m("SUBTRACT", 1.0, w.smooth(v1, 0.0, 0.18))
        head = w.smooth(v1, 0.88, 1.0)
        streak = w.blot(uvm, 0.4, 82.0, detail=2.0, stretch=(1.0, 6.0, 1.0))
        gr = w.mul(w.term("grime"), w.sat(w.add(w.mul(foot, w.add(0.4, w.mul(streak, 0.6))), w.mul(head, 0.7))))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.5), w.sat(w.mul(gr, 1.4)))
        # rust-brown stains run down from the head's earrings and the reef cringles: thin, few
        stain = w.mul(w.term("stain"), w.patches(uvm, 0.06, 0.06, seed=83.0, detail=1.0, soft=0.12,
                                                 stretch=(1.0, 6.0, 1.0)), head)
        sh.col = w.mix(sh.col, (110, 82, 52), w.mul(stain, 0.6))
        # patches: new cloth sewn over a tear, a cloth wide or less, square to the cloths (paler, crisper)
        cw = CARDS["surfaces"]["canvas"]["pattern_mm"]["cloth"] / 1000.0
        ci = w.m("FLOOR", w.m("DIVIDE", u0, cw))
        pr = w.m("FLOOR", w.m("DIVIDE", v0, 1.4))
        h1, hc = w.hash(w.comb(ci, pr, 0.0), 84.0)
        h2, h3, _ = w.sep(hc)
        cu, cv = w.m("FRACT", w.m("DIVIDE", u0, cw)), w.m("FRACT", w.m("DIVIDE", v0, 1.4))
        # a patch is the cloth's width less its seams, 0.4 to 1.2 m long
        inside = w.mul(w.m("GREATER_THAN", cu, 0.06), w.m("LESS_THAN", cu, 0.94),
                       w.m("GREATER_THAN", cv, w.mul(h3, 0.15)), w.m("LESS_THAN", cv, w.add(0.3, w.mul(h2, 0.55))))
        patch = w.mul(inside, w.m("LESS_THAN", h1, w.mul(w.term("patches"), 0.12)))
        sh.col = w.mix(sh.col, CANVAS_PATCH, w.mul(patch, 0.8))
    mil = w.patches(uvm, 0.005, w.mul(w.term("mildew"), 0.35), seed=85.0, soft=0.03, detail=1.0)
    mil_area = w.blot(uvm, 0.8, 86.0)
    sh.col = w.mix(sh.col, MILDEW, w.mul(mil, w.add(0.3, w.mul(mil_area, 0.7)), 0.85))
    sh.finish()


def iron(w, sh, kind):
    pos, wpos = w.obj(), w.world()
    rnd = w.rnd()
    if kind == "lead":
        r, g, b = detail(w, sh, "Metal", pos, 0.00003)
        sh.metal = w.lerp(sh.metal, 0.1, w.term("dull"))
        sh.rough = w.lerp(sh.rough, 0.8, w.term("dull"))
        ox = w.mul(w.term("oxide"), w.add(0.4, w.mul(w.blot(pos, 0.05, 91.0), 0.6)))
        sh.col = w.mix(sh.col, OXIDE_WHITE, w.mul(w.sat(ox), 0.7))
        pit = w.patches(pos, 0.004, w.mul(w.term("pits"), 0.3), seed=92.0, detail=1.0, soft=0.03)
        sh.col = w.mix(sh.col, (60, 60, 62), pit)
        sh.bump(w.mul(pit, -0.0005))
        sh.finish()
        return
    r, g, b = detail(w, sh, "CastBronze" if kind == "blacked" else "Metal", pos, 0.0002 if kind == "blacked" else 0.00005,
                     pits=kind == "blacked")
    if kind == "blacked":
        pit = w.m("SUBTRACT", 1.0, r)
        sh.col = w.scale(sh.col, w.add(1.0, w.mul(w.m("SUBTRACT", g, 0.5), w.add(0.1, w.term("skin")))))
    else:
        pit = w.val(0.0)
    edges = w.edge(0.008)
    cr = w.crevice(0.06)
    br = w.mul(w.term("brown"), w.sat(w.add(w.mul(edges, 0.8), w.mul(w.blot(pos, 0.08, 93.0 + 0.0), 0.3))))
    sh.col = w.mix(sh.col, (60, 40, 28), w.mul(w.sat(br), 0.7))
    # rust blooms through in spots (each gun its own, by the object's random), then flakes the black off
    seed_rnd = w.mul(rnd, 100.0)
    bloom_n = w.N.new("ShaderNodeTexNoise")
    bloom_n.noise_dimensions = "4D"
    w.L.new(wpos, bloom_n.inputs["Vector"])
    w.L.new(seed_rnd, bloom_n.inputs["W"])
    bloom_n.inputs["Scale"].default_value = 1.0 / 0.03
    bloom_n.inputs["Detail"].default_value = 3.0
    bloom = w.mul(w.term("bloom"), w.smooth(bloom_n.outputs["Factor"], 0.56, 0.64), w.add(0.5, w.mul(cr, 0.5), edges))
    rust = w.sat(w.add(bloom, w.mul(w.term("rust"), w.add(0.55, w.mul(w.blot(wpos, 0.05, 94.0), 0.6)))))
    rc = w.mix(RUST_DARK, RUST_ORANGE, w.blot(wpos, 0.01, 95.0))
    sh.col = w.mix(sh.col, rc, rust)
    sh.metal = w.lerp(sh.metal, 0.0, rust)
    sh.rough = w.lerp(sh.rough, 0.92, rust)
    flake = w.mul(w.term("rust"), w.patches(pos, 0.01, 0.4, seed=96.0, detail=3.0))
    sh.bump(w.add(w.mul(flake, 0.0006), w.mul(pit, w.term("rust"), -0.0003)))
    sh.finish()


def bright(w, sh, kind):
    pos = w.obj()
    cr = w.crevice(0.08)
    if kind == "gilt":
        sh.rough = w.lerp(sh.rough, 0.6, w.term("dull"))
        # re-gilt over thirty years of size and leaf: a deeper, warmer oil gilding than the first water gilt
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.82, 0.54, 0.22)), w.term("regilt"))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.75, 0.68, 0.55)), w.term("dull"))
        sh.col = w.mix(sh.col, (30, 24, 16), w.mul(w.term("dirt"), w.add(0.3, w.mul(cr, 0.7)), 0.95))
        chip = w.patches(pos, 0.01, w.mul(w.term("chips"), 0.35), seed=101.0, detail=3.0)
        gone = w.patches(pos, 0.08, w.mul(w.term("gone"), 0.8), seed=102.0, detail=2.0)
        lost = w.sat(w.add(chip, gone))
        under = w.mix(BOLE, GREY_OAK, w.mul(gone, 0.8))
        sh.col = w.mix(sh.col, under, lost)
        sh.metal = w.lerp(sh.metal, 0.0, lost)
        sh.rough = w.lerp(sh.rough, 0.85, lost)
        sh.finish()
        return
    r, g, b = detail(w, sh, "CastBronze", pos, 0.0001, pits=True)
    sh.col = w.mix(sh.col, (110, 76, 46), w.term("patina"))
    sh.col = w.mix(sh.col, (54, 40, 30), w.mul(w.term("dark"), w.add(0.3, w.mul(cr, 0.7)), w.term("patina")))
    vg = w.mul(w.term("verdigris"), w.add(w.mul(cr, 0.8), w.mul(w.blot(pos, 0.05, 103.0), 0.4)))
    sh.col = w.mix(sh.col, VERDIGRIS, w.sat(vg))
    sh.metal = w.lerp(sh.metal, 0.0, w.sat(vg))
    sh.rough = w.lerp(sh.rough, 0.7, w.mul(w.term("patina"), 0.6))
    sh.finish()


DRESS = {"paint": paint, "copper": copper, "wood": wood, "deck": deck_surface, "rope": rope, "canvas": canvas,
         "iron": iron, "bright": bright}


def dress(level="L0"):
    """Adds the maps and the wear to every material in bpy.data that a card covers (by name), then sets them to
    `level`; returns the names dressed. Stops if the build made a material that no card covers."""
    import bpy
    names = {m.name for m in bpy.data.materials if not m.name.startswith("J_") and m.users}
    missing, _ = coverage(names)
    if missing:
        raise SystemExit(f"textures_1797.json covers no card, 'unweathered' or 'below_decks' entry for {missing}")
    idx = material_index()
    done = []
    for m in bpy.data.materials:
        if m.name not in idx or m.get(TAG):
            continue
        s, k = idx[m.name]
        w = W(m, s, k)
        sh = JW.Shader(w)
        DRESS[s](w, sh, k)
        m[TAG], m["f_kind"] = s, k
        done.append(m.name)
    apply_level(level)
    return sorted(done)


def apply_level(level):
    """Sets every dressed material's wear terms to a level ("L0".."L4") or to (age, care)."""
    import bpy
    age, care = (LEVELS[level]["age"], LEVELS[level]["care"]) if isinstance(level, str) else level
    for m in bpy.data.materials:
        s = m.get(TAG)
        if not s:
            continue
        a = amounts(s, m["f_kind"], age, care)
        for n in m.node_tree.nodes:
            if n.type == "VALUE" and n.name.startswith("wear:"):
                term = n.name[5:]
                if term not in a:
                    raise SystemExit(f"{m.name}: no amount for wear term {term} ({s}, {m['f_kind']})")
                n.outputs[0].default_value = a[term]
    bpy.context.scene["f_wear"] = level if isinstance(level, str) else f"{age},{care}"


def dressed():
    import bpy
    return sorted((m for m in bpy.data.materials if m.get(TAG)), key=lambda m: m.name)


def material_id(k):
    """A distinct flat colour (sRGB 0-1) for the k-th dressed material (k from 1), for the id renders."""
    return ((k % 4) / 3.0, (k // 4 % 4) / 3.0, (k // 16 % 4) / 3.0)


def albedo_mode(mode):
    """"albedo": each dressed material renders its colour alone (an emission of what feeds its Base Color), for
    measuring the levels' colours without the light; "id": each its own flat colour (material_id, in name order);
    False puts the shaders back. In both modes everything else holds out (black)."""
    import bpy
    for k, m in enumerate(dressed(), 1):
        nt = m.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        em = nt.nodes.get("wear:albedo")
        if em is None:
            em = nt.nodes.new("ShaderNodeEmission")
            em.name = em.label = "wear:albedo"
            idn = nt.nodes.new("ShaderNodeEmission")
            idn.name = idn.label = "wear:id"
            bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
            nt.links.new(bsdf.inputs["Base Color"].links[0].from_socket, em.inputs["Color"])
            src = out.inputs["Surface"].links[0].from_socket
            m["f_shader_node"], m["f_shader_out"] = src.node.name, list(src.node.outputs).index(src)
        idn = nt.nodes["wear:id"]
        idn.inputs["Color"].default_value = (*_lin(tuple(255.0 * c for c in material_id(k))), 1.0)
        if mode in ("albedo", True):
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        elif mode == "id":
            nt.links.new(idn.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(nt.nodes[m["f_shader_node"]].outputs[m["f_shader_out"]], out.inputs["Surface"])
    for m in bpy.data.materials:
        if m.get(TAG) or not m.use_nodes or not m.node_tree:
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
        if out is None:
            continue
        ho = nt.nodes.get("wear:holdout")
        if ho is None:
            if not out.inputs["Surface"].is_linked:
                continue
            ho = nt.nodes.new("ShaderNodeHoldout")
            ho.name = ho.label = "wear:holdout"
            src = out.inputs["Surface"].links[0].from_socket
            m["f_shader_node"], m["f_shader_out"] = src.node.name, list(src.node.outputs).index(src)
        if mode in ("albedo", "id", True):
            nt.links.new(ho.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(nt.nodes[m["f_shader_node"]].outputs[m["f_shader_out"]], out.inputs["Surface"])


if __name__ == "__main__":
    for lv in LEVEL_IDS:
        print(lv, json.dumps(level_amounts(lv)))
