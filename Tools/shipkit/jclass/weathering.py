"""Bluebonnet's wear (docs/jclass-11): how much of each kind of wear a level brings, and where on her it falls.

    import weathering
    weathering.amounts("teak", "deck", 6.0, 0.5)     # {"silver": 1.0, "pale": 0.5, ...}, no Blender needed
    weathering.dress(mats)                            # in the build: adds the detail maps and the wear to each material
    weathering.apply_level("L2")                      # in a render: sets every material to a level (or (age, care))

The texture loop's five levels (Tools/texloop/levels.json) are fixed points of E1's Age (years) and Care (0 left to rot
.. 1 kept), and its two numbers (Tools/texloop/wear.py) split them into what the years do whatever the owner does
(time_k: fade, yellowing, patina, grain worn proud) and what care takes away (dirt_k: chalk, grime, rust, mildew, weed).
amounts() turns those into each surface's own terms, 0 to 1, with the reasons in its comments; textures_bluebonnet.json
says what each level should look like and which of her materials each surface covers. dress() builds the patterns in
each material's nodes, scaled by a Value node per term ("wear:<term>"), so one build renders any level: apply_level()
only sets those values. The game's material (slice 14, M_BoatSurface's twin) takes the same amounts from the boat's
Age and Care, so the terms are kept to what a pixel shader can do: noise, streaks run down from a seam, the height above
the waterline, which way a face looks, the camera's distance, and the crevices (ambient occlusion here, a baked cavity
map in the game).

Every pattern is in metres in the part's own frame (or its UVs: the plating's, the deck's, the spars' and ropes', the
sails'), so it keeps its size on a 131 ft yacht; the detail maps tile at their real size (textures.py, the boats'
library) and fade out with the camera's distance as the game's do.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
import wear as loop  # noqa: E402

CARDS = json.load(open(os.path.join(HERE, "textures_bluebonnet.json")))
SHARED_META = json.load(open(os.path.join(REPO, "Inputs", "boat-detail", "detail_textures.json")))
LEVELS = {lv["id"]: lv for lv in loop.levels()}
SALT = 1.0                       # Galveston: the salt-water rate (the lake's is about a third: docs/texture-loop metal)


def sat(x):
    return max(0.0, min(1.0, x))


def ramp(x, lo, hi):
    """0 under lo, 1 over hi, straight between."""
    return sat((x - lo) / (hi - lo))


def refreshed(age, care):
    """How much a kept yacht's routine (the boot top and the spars washed at each haul-out, the sails dried and
    washed, the saloon renewed) has undone the first-season marks: none in her first season, most when well kept."""
    return care ** 2 * ramp(age, 0.5, 2.0)


def amounts(surface, kind, age, care):
    """Each wear term, 0 to 1, for one surface and kind at E1's Age (years) and Care (0..1). The loop's dirt_k takes a
    year to come up and then holds, so the marks of a first season (gloss going, a scum line, smudges, a flattened
    pile) go as its square root, times `fresh` where a kept yacht's routine takes them away again; what neglect alone
    does (rust, flaking, rot, mildew) starts past a threshold of dirt_k that a kept yacht never reaches."""
    t, d = loop.time_k(age, care), loop.dirt_k(age, care)
    young = 1.0 - math.exp(-age / 0.4)           # a few months' exposure: the first change in a bare metal or wood
    fresh = 1.0 - 0.85 * refreshed(age, care)
    first = math.sqrt(d) * fresh                 # first-season marks
    if surface == "paint":
        a = {"gloss": sat(0.8 * first + 0.15 * t),                # the enamel's shine goes; polished, it comes back
             "chalk": max(d * fresh, 0.35 * t),                   # oxidised pigment: polished off, but never all of it
             "rust": SALT * ramp(d, 0.2, 0.9) ** 1.2,             # weeps from rivets and seams once care lapses
             "chips": ramp(d, 0.35, 0.95),                        # knocks at the sheer and stem, left unpainted
             "grime": ramp(d, 0.1, 0.8) * fresh}                  # dark runs under the scuppers and fittings
        if kind == "antifouling":
            a.update(scum=sat(1.8 * first), weed=SALT * ramp(d, 0.3, 0.9), barnacles=SALT * ramp(d, 0.6, 0.95),
                     chalk=max(d, 0.5 * t))
        elif kind == "enamel":
            a.update(scum=sat(1.8 * first), weed=SALT * ramp(d, 0.3, 0.9) * 0.8)  # the boot top's scum, then weed
        elif kind == "interior":                                  # lead-white enamel yellows in the dark
            a = {"yellow": 0.8 * t * (1.0 - 0.6 * refreshed(age, care)),   # a kept yacht repaints below
                 "grime": sat(0.9 * d) * fresh, "rust": ramp(d, 0.55, 0.95), "gloss": 0.5 * t}
        elif kind == "gilt":                                      # the gold leaf is renewed on a kept yacht
            a = {"dull": sat(0.7 * first), "chips": ramp(d, 0.4, 0.9)}
        return a
    if surface == "teak":
        silver = sat(4.0 * t)                                     # bare teak greys within a season
        a = {"silver": silver,
             "pale": silver * care ** 2,                          # scrubbed with salt water: bleached blond
             "dark": d ** 1.3,                                    # grime, algae and mildew in the soft grain
             "raised": t,                                         # the soft grain worn down, the hard grain proud
             "seams": ramp(d, 0.45, 0.95),                        # the marine glue failing
             "checks": t * (1.0 - 0.6 * care)}
        if kind == "sole":                                        # below decks: no sun, scrubbed, foot traffic
            a.update(silver=0.3 * silver, pale=0.3 * a["pale"], seams=0.0, dark=0.6 * a["dark"])
        return a
    if surface == "varnish":
        out = kind == "exterior"
        return {"amber": t,                                       # the wood darkens and the varnish ambers
                "grime": 0.0 if out else sat(1.2 * first),         # below: hands' dirt at the edges and handholds
                "dull": sat(0.8 * first * (1.0 if out else 0.5)),  # revarnished each spring on a kept yacht
                "fail": ramp(d, 0.45, 0.9) if out else 0.0,       # the film breaks at edges and tops, wood greys
                "stain": (d ** 2) * (1.0 if out else 0.5),        # black water stains where it has failed
                "bloom": 0.0 if out else ramp(d, 0.6, 0.95)}      # below: white blush where damp got under it
    if surface == "bronze":
        polish = 0.85 * care * sat(age / 3.0)                     # a kept yacht's bronze is polished
        return {"patina": young * (1.0 - polish),                 # open faces: brown, then dark
                "recess": young,                                  # the recesses keep their patina whatever
                "dark": sat(t + d) * young,                       # and darken with the years
                "verdigris": SALT * ramp(d, 0.5, 0.9),
                "worn": sat(3.0 * t) * (1.0 - 0.5 * d)}           # bright where hands and rope work it
    if surface == "duralumin":
        return {"gloss": sat(0.8 * first + 0.15 * t),             # repainted on a kept yacht
                "slap": sat(1.6 * first),                         # grey marks where the halyards slap
                "chalk": ramp(d, 0.2, 0.7),                       # the paint chalks to a flat pale buff
                "grime": ramp(d, 0.15, 0.8) * fresh,              # grime runs down from the fittings
                "yellow": 0.4 * t * care,                         # repainted, but the buff yellows a little
                "flake": ramp(d, 0.5, 0.9)}                       # the paint lets go: grey metal and white oxide
    if surface == "cotton":
        a = {"dinge": sat(0.75 * first), "grime": sat(1.2 * first), "mildew": ramp(d, 0.25, 0.85),
             "yellow": 0.6 * t, "rust": ramp(d, 0.6, 0.9)}
        if kind == "canvas":
            a["rust"] = 0.0
        return a
    if surface == "manila":
        own = min(age, 0.5 * (3.0 + 12.0 * (1.0 - care)))       # rope is renewed: on average half its life old
        rt, rd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"grey": sat(0.6 * math.sqrt(rd) + 0.3 * rt), "fuzz": sat(0.8 * math.sqrt(rd) + 0.3 * rt),
                "dark": rd, "mildew": ramp(rd, 0.5, 0.9)}
    if surface == "wire":
        dull = sat(3.0 * t)
        if kind == "zinc":                                        # the galley's zinc: no iron in it to rust
            return {"dull": dull, "oxide": sat(1.5 * d) * (1.0 - 0.8 * ramp(d, 0.6, 0.95)),
                    "grime": ramp(d, 0.55, 0.9), "oiled": 0.0, "rust": 0.0}
        bloom = 2.4 if kind == "wire" else 3.5                     # the fittings' thicker zinc blooms more
        return {"dull": dull, "oxide": sat(bloom * d * (1.0 - care)) * (1.0 - ramp(d, 0.8, 0.95)),
                "oiled": care * sat(2.0 * t) * (1.0 - d),         # a kept yacht's wire is oiled: dark, a soft sheen
                "rust": SALT * ramp(d, 0.55, 0.9)}
    if surface == "furnishings":
        return {"fade": 0.7 * t * (1.0 - 0.6 * refreshed(age, care)),  # renewed on a kept yacht
                "worn": sat(1.1 * first + 0.5 * ramp(d, 0.4, 0.9)), "mildew": ramp(d, 0.55, 0.9),
                "stain": d ** 1.5, "grey": sat(0.8 * first)}
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
                    raise SystemExit(f"textures_bluebonnet.json: {n} is in two cards ({out[n]} and {(s, k)})")
                out[n] = (s, k)
    return out


def coverage(material_names):
    """The materials the build makes that no card or 'unweathered' entry covers, and the card entries the build
    does not make (both must be empty)."""
    idx = material_index()
    un = set(CARDS["unweathered"])
    names = set(material_names)
    return sorted(names - set(idx) - un), sorted((set(idx) | un) - names)


# ================================================================================================ Blender
def _lin(c):
    """sRGB 0-255 to linear."""
    return tuple((v / 255.0) / 12.92 if v / 255.0 <= 0.04045 else ((v / 255.0 + 0.055) / 1.055) ** 2.4 for v in c)


# what each wear brings, sRGB 0-255 (the renders'; the game's skins can change the paint, not these)
RUST = (122, 64, 36)
RUST_DARK = (70, 38, 24)
WEED = (52, 70, 34)
SLIME = (84, 70, 40)
BARNACLE = (150, 144, 128)
SILVER = (156, 152, 146)
BLOND = (200, 184, 156)
MILDEW = (36, 38, 32)
GREY_WOOD = (132, 126, 118)
OLD_VARNISH = (92, 52, 26)
STAIN = (40, 34, 28)
BLOOM = (210, 206, 196)
PATINA = (96, 66, 40)
PATINA_DARK = (52, 40, 30)
VERDIGRIS = (96, 150, 128)
DURAL = (196, 198, 200)
OXIDE = (222, 222, 216)
GRIME = (86, 76, 60)
ZINC_WHITE = (226, 226, 220)
CHALK = (150, 156, 170)


class W:
    """Node helpers for one material's tree, with the wear terms as named Value nodes."""

    def __init__(self, mt, surface, kind):
        import bpy  # noqa: F401
        self.mt, self.nt = mt, mt.node_tree
        self.N, self.L = self.nt.nodes, self.nt.links
        self.surface, self.kind = surface, kind
        self._tc = self._geo = self._cam = self._nrm = None
        self.terms = {}

    # -- plumbing
    def link(self, a, b):
        self.L.new(a, b)

    def val(self, v):
        n = self.N.new("ShaderNodeValue")
        n.outputs[0].default_value = float(v)
        return n.outputs[0]

    def rgb(self, c):
        n = self.N.new("ShaderNodeRGB")
        n.outputs[0].default_value = (*c, 1.0)
        return n.outputs[0]

    def sock(self, v):
        return self.val(v) if isinstance(v, (int, float)) else v

    def m(self, op, a, b=None, c=None, clamp=False):
        n = self.N.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for k, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                self.L.new(v, n.inputs[k])
        return n.outputs[0]

    def mul(self, *xs):
        out = xs[0]
        for x in xs[1:]:
            out = self.m("MULTIPLY", out, x)
        return out

    def add(self, *xs):
        out = xs[0]
        for x in xs[1:]:
            out = self.m("ADD", out, x)
        return out

    def sat(self, x):
        return self.m("MULTIPLY", x, 1.0, clamp=True)

    def lerp(self, a, b, f):
        """a + (b - a) f for floats (sockets or numbers)."""
        n = self.N.new("ShaderNodeMix")
        n.data_type = "FLOAT"
        for sock, v in ((n.inputs[0], f), (n.inputs[2], a), (n.inputs[3], b)):
            if isinstance(v, (int, float)):
                sock.default_value = float(v)
            else:
                self.L.new(v, sock)
        n.clamp_factor = True
        return n.outputs[0]

    def mix(self, a, b, f, blend="MIX"):
        """Colours: a where f = 0, b where f = 1 (tuples are sRGB 0-255)."""
        n = self.N.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend
        n.clamp_factor = True
        if isinstance(f, (int, float)):
            n.inputs[0].default_value = float(f)
        else:
            self.L.new(f, n.inputs[0])
        for sock, v in ((n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, tuple):
                sock.default_value = (*_lin(v), 1.0)
            else:
                self.L.new(v, sock)
        return n.outputs[2]

    def scale(self, col, f):
        """A colour times a float (socket or number) per channel; a tuple scales each channel by its own factor."""
        n = self.N.new("ShaderNodeVectorMath")
        if isinstance(f, tuple):
            n.operation = "MULTIPLY"
            n.inputs[1].default_value = f
        else:
            n.operation = "SCALE"
            if isinstance(f, (int, float)):
                n.inputs["Scale"].default_value = float(f)
            else:
                self.L.new(f, n.inputs["Scale"])
        self.L.new(col, n.inputs[0])
        return n.outputs[0]

    def lum(self, col):
        n = self.N.new("ShaderNodeRGBToBW")
        self.L.new(col, n.inputs[0])
        return n.outputs[0]

    def smooth(self, x, lo, hi):
        n = self.N.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        n.clamp = True
        self.L.new(x, n.inputs["Value"])
        for nm, v in (("From Min", lo), ("From Max", hi)):
            if isinstance(v, (int, float)):
                n.inputs[nm].default_value = float(v)
            else:
                self.L.new(v, n.inputs[nm])
        return n.outputs[0]

    def sep(self, v):
        n = self.N.new("ShaderNodeSeparateXYZ")
        self.L.new(v, n.inputs[0])
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x, y, z):
        n = self.N.new("ShaderNodeCombineXYZ")
        for k, v in enumerate((x, y, z)):
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                self.L.new(v, n.inputs[k])
        return n.outputs[0]

    # -- where
    def term(self, name):
        """The level's amount of one wear term (set by apply_level)."""
        if name not in self.terms:
            n = self.N.new("ShaderNodeValue")
            n.name = n.label = "wear:" + name
            self.terms[name] = n.outputs[0]
        return self.terms[name]

    def obj(self):
        if self._tc is None:
            self._tc = self.N.new("ShaderNodeTexCoord")
        return self._tc.outputs["Object"]

    def geo(self, out):
        if self._geo is None:
            self._geo = self.N.new("ShaderNodeNewGeometry")
        return self._geo.outputs[out]

    def up(self):
        """1 on a face looking at the sky, 0 on a wall, below 0 underneath."""
        return self.sep(self.geo("Normal"))[2]

    def wz(self):
        """Height above the load waterline (Blender's z is the hull's)."""
        return self.sep(self.geo("Position"))[2]

    def dist(self):
        if self._cam is None:
            self._cam = self.N.new("ShaderNodeCameraData")
        return self._cam.outputs["View Distance"]

    def fade(self, near, far):
        """1 near the camera, 0 past far (the detail maps and fine patterns, as the game fades them)."""
        return self.m("SUBTRACT", 1.0, self.smooth(self.dist(), near, far))

    def noise(self, vec, size_m, seed=0.0, detail=2.0, rough=0.55, stretch=None, distort=0.0):
        """Blender's noise (mean 0.5, close to normal with the spread NOISE_SD[detail]) with features about size_m
        across; stretch (sx, sy, sz) lengthens them per axis."""
        if stretch:
            mp = self.N.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = tuple(1.0 / s for s in stretch)
            self.L.new(vec, mp.inputs["Vector"])
            vec = mp.outputs[0]
        n = self.N.new("ShaderNodeTexNoise")
        n.noise_dimensions = "4D"
        self.L.new(vec, n.inputs["Vector"])
        n.inputs["W"].default_value = seed
        n.inputs["Scale"].default_value = 1.0 / size_m
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distort
        return n.outputs["Factor"]

    def blot(self, vec, size_m, seed=0.0, detail=2.0, stretch=None):
        """Noise spread over 0..1 (two spreads each side of the mean): blotches that are really there or not, where the
        raw noise would vary by a tenth."""
        sd = noise_sd(detail)
        n = self.noise(vec, size_m, seed, detail=detail, stretch=stretch)
        return self.smooth(n, 0.5 - 2.0 * sd, 0.5 + 2.0 * sd)

    def patches(self, vec, size_m, amount, seed=0.0, soft=0.06, detail=3.0, stretch=None):
        """A share `amount` (socket or number, 0..1) of the surface in blotches about size_m across: the noise above
        the threshold its spread leaves that share over (the normal's quantile, by the logistic approximation
        z = ln((1 - a) / a) / 1.702), with an edge `soft` wide (in noise units, scaled by its spread)."""
        sd = noise_sd(detail)
        nz = self.noise(vec, size_m, seed, detail=detail, stretch=stretch)
        a = self.m("MINIMUM", self.m("MAXIMUM", self.sock(amount), 0.002), 0.998)
        z = self.m("DIVIDE", self.m("LOGARITHM", self.m("DIVIDE", self.m("SUBTRACT", 1.0, a), a), math.e), 1.702)
        edge = soft * sd / 0.09
        thr = self.add(0.5 - 0.5 * edge, self.mul(z, sd))
        # the noise's tail reaches past any threshold: nothing at all when the amount is nothing
        return self.mul(self.smooth(nz, thr, self.add(thr, edge)), self.sat(self.mul(self.sock(amount), 12.0)))

    def hash(self, vec, seed=0.0):
        """White noise per point: (value, colour) sockets, the same for every pixel given the same vec."""
        n = self.N.new("ShaderNodeTexWhiteNoise")
        n.noise_dimensions = "4D"
        self.L.new(vec, n.inputs["Vector"])
        n.inputs["W"].default_value = seed
        return n.outputs["Value"], n.outputs["Color"]

    def ao(self, dist):
        """0 deep in a crevice, 1 in the open."""
        n = self.N.new("ShaderNodeAmbientOcclusion")
        n.samples = 8
        n.only_local = True
        n.inputs["Distance"].default_value = dist
        return n.outputs["AO"]

    def crevice(self, dist, lo=0.35, hi=0.9):
        return self.m("SUBTRACT", 1.0, self.smooth(self.ao(dist), lo, hi))

    def edge(self, radius):
        """1 on a convex or concave edge (within about radius of it), 0 on a flat face."""
        b = self.N.new("ShaderNodeBevel")
        b.samples = 4
        b.inputs["Radius"].default_value = radius
        dot = self.N.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        self.L.new(b.outputs[0], dot.inputs[0])
        self.L.new(self.geo("Normal"), dot.inputs[1])
        return self.smooth(self.m("SUBTRACT", 1.0, dot.outputs["Value"]), 0.004, 0.05)

    def uv(self, name):
        u = self.N.new("ShaderNodeUVMap")
        u.uv_map = name
        return u.outputs[0]

    def image(self, name, vec, tile_m, box=True):
        """One of the detail maps (non-colour), sampled at its real size; returns (r, g, b) sockets. vec is a UV in
        metres (box False) or the part's own coordinates, projected three ways and blended by the face's direction
        (box True): a face looking up or down takes (x, y), one looking to the side (x, z), one looking fore or aft
        (y, z), so a map's U (the grain of the teak and the varnished wood, the brushing of the metal) runs fore and aft
        on the deck and along the horizontal on walls. (Cycles' own box projection takes (y, x) on a top face: the
        deck's grain would run across its planks.)"""
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

    def _vadd(self, a, b):
        n = self.N.new("ShaderNodeVectorMath")
        n.operation = "ADD"
        self.L.new(a, n.inputs[0])
        self.L.new(b, n.inputs[1])
        return n.outputs[0]


def noise_sd(detail):
    """The spread of Blender 5.3's noise Factor (4-D, roughness 0.55) at a detail, measured on 65,536 samples."""
    table = {0: 0.110, 1: 0.081, 2: 0.070, 3: 0.065, 4: 0.062, 5: 0.061}
    return table[min(table, key=lambda d: abs(d - detail))]


def map_path(name):
    own = CARDS["maps"]["own"]
    if name in own:
        return os.path.join(REPO, "Inputs", "jclass-detail", f"T_JClass_{name}_M.png")
    return os.path.join(REPO, "Inputs", "boat-detail", f"T_Detail_{name}_M.png")


def tile_of(name):
    m = CARDS["maps"]["own"].get(name) or CARDS["maps"]["shared"][name]
    return (m["tile_mm"][0] / 1000.0, m["tile_mm"][1] / 1000.0)


class Shader:
    """The material's Principled BSDF (and any translucent lobe) as editable sockets: col, rough, metal, coat and a
    height to add to its bump. finish() wires them back."""

    def __init__(self, w):
        self.w = w
        nt = w.nt
        self.bsdfs = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]
        self.trans = [n for n in nt.nodes if n.type == "BSDF_TRANSLUCENT"]
        b = self.bsdfs[0]
        self.col = self._src(b.inputs["Base Color"], "rgb")
        self.col0 = self.col
        self.rough = self._src(b.inputs["Roughness"])
        self.metal = self._src(b.inputs["Metallic"])
        self.coat = self._src(b.inputs["Coat Weight"])
        self.tcol = [self._src(t.inputs["Color"], "rgb") for t in self.trans]
        self.heights = []            # (socket in metres, fade) to add as a bump

    def _src(self, sock, kind="value"):
        if sock.is_linked:
            return sock.links[0].from_socket
        if kind == "rgb":
            return self.w.rgb(tuple(sock.default_value)[:3])
        return self.w.val(sock.default_value)

    def bump(self, height_m):
        self.heights.append(height_m)

    def finish(self, tint_translucent=True):
        w = self.w
        for b in self.bsdfs:
            for nm, s in (("Base Color", self.col), ("Roughness", self.rough), ("Metallic", self.metal),
                          ("Coat Weight", self.coat)):
                for lk in list(b.inputs[nm].links):
                    w.L.remove(lk)
                w.link(s, b.inputs[nm])
        if tint_translucent and self.trans:
            # the wear's tint on the reflected colour, carried to the light through the cloth
            ratio = w.N.new("ShaderNodeVectorMath")
            ratio.operation = "DIVIDE"
            w.link(self.col, ratio.inputs[0])
            add = w.N.new("ShaderNodeVectorMath")
            add.operation = "ADD"
            w.link(self.col0, add.inputs[0])
            add.inputs[1].default_value = (1e-4, 1e-4, 1e-4)
            w.link(add.outputs[0], ratio.inputs[1])
            for t, c in zip(self.trans, self.tcol):
                mul = w.N.new("ShaderNodeVectorMath")
                mul.operation = "MULTIPLY"
                w.link(c, mul.inputs[0])
                w.link(ratio.outputs[0], mul.inputs[1])
                for lk in list(t.inputs["Color"].links):
                    w.L.remove(lk)
                w.link(mul.outputs[0], t.inputs["Color"])
        if self.heights:
            h = w.add(*self.heights) if len(self.heights) > 1 else self.heights[0]
            bp = w.N.new("ShaderNodeBump")
            bp.name = bp.label = "wear:bump"
            bp.inputs["Distance"].default_value = 1.0
            w.link(h, bp.inputs["Height"])
            first = self.bsdfs[0].inputs["Normal"]
            if first.is_linked:
                w.link(first.links[0].from_socket, bp.inputs["Normal"])
            for n in self.bsdfs + self.trans:
                for nm in ("Normal", "Coat Normal"):
                    if nm in n.inputs and (nm == "Normal" or n.inputs[nm].is_linked):
                        for lk in list(n.inputs[nm].links):
                            w.L.remove(lk)
                        w.link(bp.outputs[0], n.inputs[nm])


# ------------------------------------------------------------------------------------------------ the surfaces
def fade_of(name):
    """A detail map's fade (near, far) in metres: her own card's, or the shared library's (detail_textures.json)."""
    own = CARDS["maps"]["own"].get(name)
    if own:
        return tuple(own.get("fade_m", (1.0, 4.0)))
    return tuple(SHARED_META.get(name, {}).get("fade_m", (1.0, 4.0)))


def detail(w, sh, name, vec, amp_m=None, box=True, pits=False):
    """A detail map's (r, g, b) for the colour and roughness terms, and its B channel as a bump of amp_m metres,
    fading with the camera's distance as the game fades it (fade_of): a height about 0.5, or with pits a depth from 0
    (the Metal map's B). The Gelcoat map has no height (its orange peel is in its normal map, which the game draws and
    these renders, at metres, would not show): amp_m None, no bump."""
    r, g, b = w.image(name, vec, tile_of(name), box=box)
    if amp_m is not None:
        h = w.mul(b, -1.0) if pits else w.m("SUBTRACT", b, 0.5)
        sh.bump(w.mul(h, amp_m, w.fade(*fade_of(name))))
    return r, g, b


def runs(w, u, below, key, pitch, share, width, length, seed, start=None, jitter=0.0, on_lines=False, along=None):
    """Rust or grime runs down from sources `pitch` metres apart along u (at the cells' middles, or on the lines
    u = k pitch with on_lines): a share (number or socket) of them weep, each a streak about `width` wide, spreading as
    it runs and fading over a length drawn from `length` (lo, hi) metres. `below` is metres below the source line;
    `key` (a socket or number) tells one row of sources from another (the plating's strakes), so no two rows weep
    alike; `start` moves each source down by up to that many metres; `jitter` moves it along its cell (a share of the
    pitch); `along` is the coordinate down the run for its broken edge (default `below`: give the girth itself when
    the rows meet, so a run crossing into the next row stays one run)."""
    q = w.add(w.m("DIVIDE", u, pitch), 0.5) if on_lines else w.m("DIVIDE", u, pitch)
    r1, rc = w.hash(w.comb(w.m("FLOOR", q), key, 0.0), seed)
    r2, r3, r4 = w.sep(rc)
    weeping = w.m("LESS_THAN", r1, w.sock(share))
    dv = below if start is None else w.m("SUBTRACT", below, w.mul(r2, start))
    run = w.m("MAXIMUM", dv, 0.0)
    fall = w.mul(w.m("EXPONENT", w.m("DIVIDE", w.mul(run, -1.0), w.add(length[0], w.mul(r3, length[1] - length[0])))),
                 w.m("GREATER_THAN", dv, 0.0))
    off = w.add(0.5, w.mul(w.m("SUBTRACT", r4, 0.5), jitter)) if jitter else 0.5
    x = w.mul(w.m("ABSOLUTE", w.m("SUBTRACT", w.m("FRACT", q), off)), pitch)
    half = w.mul(width * 0.5, w.add(1.0, w.mul(run, 1.5)))
    core = w.m("SUBTRACT", 1.0, w.smooth(x, w.mul(half, 0.3), half))
    n = w.noise(w.comb(u, below if along is None else along, 0.0), 0.04, seed + 0.5, detail=2.0,
                stretch=(1.0, 5.0, 1.0))
    broken = w.smooth(n, 0.32, 0.6)
    return w.mul(weeping, fall, core, broken)


def chalky(w, col, white, lift=0.6):
    """A paint's chalked look: its colour greyed and lifted toward `white` (never darkened: white chalks white)."""
    lm = w.lum(col)
    return w.mix(w.mix(col, w.comb(lm, lm, lm), 0.5), white, lift, blend="LIGHTEN")


def paint(w, sh, kind):
    pos = w.obj()
    plating = kind in ("enamel", "antifouling", "gilt") and w.mt.name in ("Topsides", "Bootstripe", "Antifouling",
                                                                          "Keel", "CoveStripe")
    if kind != "interior":
        _, g, _ = detail(w, sh, "Gelcoat", pos)
        sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", g, 0.5), 0.08))
    if kind == "gilt":
        sh.rough = w.lerp(sh.rough, 0.55, w.term("dull"))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.75, 0.68, 0.55)), w.term("dull"))
        chip = w.patches(pos, 0.02, w.mul(w.term("chips"), 0.35), seed=4.0)
        sh.col = w.mix(sh.col, (30, 48, 118), chip)
        sh.metal = w.lerp(sh.metal, 0.0, chip)
        sh.finish()
        return
    if kind == "interior":
        sh.col = w.mix(sh.col, w.scale(sh.col, (1.0, 0.94, 0.78)), w.term("yellow"))
        sh.rough = w.lerp(sh.rough, 0.7, w.term("gloss"))
        cr = w.crevice(0.12)
        grime = w.mul(w.term("grime"), w.add(w.mul(cr, 0.8), w.mul(w.blot(pos, 0.3, 1.0), 0.6)))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.55, 0.5, 0.42)), w.sat(grime))
        rust = w.mul(w.patches(pos, 0.04, w.mul(w.term("rust"), 0.6), seed=7.0, detail=4.0), w.sat(w.mul(cr, 2.0)))
        sh.col = w.mix(sh.col, RUST, rust)
        sh.rough = w.lerp(sh.rough, 0.9, rust)
        sh.finish()
        return
    # the shine goes: rougher, the clear coat (the enamel's gloss) thinner
    sh.rough = w.lerp(sh.rough, 0.62, w.term("gloss"))
    sh.coat = w.lerp(sh.coat, 0.05, w.term("gloss"))
    # chalk, in big soft blotches, most on what faces the sky: the colour greyed and lifted, a white staying white
    ch = w.mul(w.term("chalk"), w.add(0.35, w.mul(w.blot(pos, 0.45, 2.0), 0.8)), w.add(0.7, w.mul(w.sat(w.up()), 0.3)))
    sh.col = w.mix(sh.col, chalky(w, sh.col, CHALK), w.sat(ch))
    sh.rough = w.lerp(sh.rough, 0.8, w.mul(w.sat(ch), 0.4))
    z = w.wz()
    dry = w.smooth(z, -0.02, 0.08)                                   # nothing runs under the water
    # off the plating (and on the transom, which has no plating UV): streaks and chips anywhere
    loose_rust = w.mul(w.term("rust"), w.smooth(w.noise(pos, 0.06, 9.0, stretch=(1.0, 1.0, 6.0)), 0.62, 0.72))
    loose_chip = w.patches(pos, 0.03, w.mul(w.term("chips"), 0.25), seed=5.0, detail=4.0)
    loose_grime = w.mul(w.term("grime"), w.patches(pos, 0.05, 0.12, seed=15.0, stretch=(1.0, 1.0, 10.0)))
    if plating:
        # on the plating's UV (x, girth below the sheer): weeps run down from the rivet rows, the seams and the sheer
        u, v, _ = w.sep(w.uv("Plating"))
        on = w.m("GREATER_THAN", v, -0.5)                            # plated
        off = w.m("SUBTRACT", 1.0, on)
        row = w.m("FLOOR", w.m("DIVIDE", v, 1.05))                   # the strake
        below_seam = w.m("SUBTRACT", v, w.mul(row, 1.05))            # metres below its upper seam
        more = w.add(0.4, w.mul(w.blot(w.comb(u, 0.0, 0.0), 1.6, 19.0, detail=1.0), 1.6))  # where a frame works
        # a few of the frames' rivet rows weep from a rivet somewhere in the strake (and run on into the next: the
        # strake above's are drawn too); the seams' rivets (7.5 cm apart, on the frames' lines) weep from the seam;
        # the scuppers and fittings at the sheer make the long wide runs
        frame = dict(pitch=0.53, share=w.mul(0.2, more), width=0.02, length=(0.2, 0.9), seed=11.0, start=0.9,
                     on_lines=True, along=v)
        from_frame = w.m("MAXIMUM", runs(w, u, below_seam, row, **frame),
                         runs(w, u, w.add(below_seam, 1.05), w.m("SUBTRACT", row, 1.0), **frame))
        from_seam = runs(w, u, below_seam, row, 0.075, w.mul(0.05, more), 0.012, (0.06, 0.4), 13.0, on_lines=True,
                         along=v)
        from_sheer = runs(w, u, v, 0.0, 0.45, w.mul(0.25, more), 0.035, (0.3, 1.4), 17.0, jitter=0.6)
        weeps = w.mul(on, dry, w.m("MAXIMUM", w.m("MAXIMUM", from_seam, from_frame), from_sheer))
        rust = w.add(w.mul(w.term("rust"), w.sat(w.mul(weeps, 1.5))), w.mul(off, loose_rust))
        # chips along the sheer, where fenders, warps and the dinghy knock her
        chip = w.add(w.mul(w.patches(pos, 0.05, w.mul(w.term("chips"), 0.3), seed=5.0, detail=4.0),
                           w.m("SUBTRACT", 1.0, w.smooth(v, 0.05, 0.4)), on), w.mul(off, loose_chip))
        # dark grime runs from the scuppers and the fittings at the sheer
        dirty = runs(w, u, v, 1.0, 0.6, w.mul(0.35, more), 0.05, (0.4, 1.8), 23.0, jitter=0.8)
        grime = w.add(w.mul(w.term("grime"), on, dry, dirty), w.mul(off, loose_grime))
    else:
        rust, chip, grime = loose_rust, loose_chip, loose_grime
    sh.col = w.mix(sh.col, w.mix(w.scale(sh.col, 0.45), GRIME, 0.4), w.mul(w.sat(grime), 0.7))
    rc = w.sat(w.add(rust, chip))
    sh.col = w.mix(sh.col, w.mix(RUST, RUST_DARK, w.noise(pos, 0.01, 3.0)), rc)
    sh.rough = w.lerp(sh.rough, 0.85, rc)
    sh.coat = w.lerp(sh.coat, 0.0, rc)
    sh.bump(w.mul(chip, -0.0002))
    if kind in ("enamel", "antifouling") and (kind == "antifouling" or w.mt.name == "Bootstripe"):
        # the waterline: a tan scum line within a season, then slime and weed in a band about it, barnacles below
        # (the boot top's lower edge is 0.1 m over the load waterline amidships: she floats a little light, moored)
        line = w.mul(w.smooth(z, -0.05, 0.0), w.m("SUBTRACT", 1.0, w.smooth(z, 0.12, 0.2)))
        scum = w.mul(line, w.term("scum"), w.add(0.5, w.mul(w.blot(pos, 0.3, 20.0), 0.5)), 0.85)
        sh.col = w.mix(sh.col, SLIME, w.sat(scum))
        band = w.mul(w.smooth(z, -0.45, -0.05), w.m("SUBTRACT", 1.0, w.smooth(z, 0.1, 0.22)))
        grow = w.mul(band, w.term("weed"), w.add(0.2, w.mul(w.blot(pos, 0.12, 21.0), 1.0)))
        sh.col = w.mix(sh.col, w.mix(SLIME, WEED, w.smooth(z, -0.2, 0.05)), w.sat(grow))
        wet = w.sat(w.add(scum, grow))
        sh.rough = w.lerp(sh.rough, 0.95, wet)
        sh.coat = w.lerp(sh.coat, 0.0, wet)
        if kind == "antifouling":
            deep = w.m("SUBTRACT", 1.0, w.smooth(z, -0.35, -0.05))
            colony = w.add(0.3, w.mul(w.blot(pos, 0.4, 25.0), 1.4))
            bar = w.mul(w.patches(pos, 0.012, w.mul(w.term("barnacles"), 0.35, colony), seed=23.0, soft=0.02,
                                  detail=1.0), deep)
            sh.col = w.mix(sh.col, BARNACLE, bar)
            sh.bump(w.mul(bar, 0.004))
    sh.finish()


def teak(w, sh, kind):
    pos = w.obj()
    fade = w.fade(*fade_of("TeakWeathered"))
    r, g, b = detail(w, sh, "TeakWeathered", pos, w.mul(0.0004, w.add(0.25, w.term("raised"))))
    # the seams (the Planking group's height dips in a seam) keep their black glue until it fails
    grp = [n for n in w.nt.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.name == "Planking"]
    seam = w.smooth(w.mul(grp[0].outputs["Height"], -1.0), 0.0002, 0.0006) if grp else w.val(0.0)
    wood = w.m("SUBTRACT", 1.0, seam)
    grain = w.m("SUBTRACT", r, 0.55)
    if kind == "deck":
        sh.col = w.scale(sh.col, (1.1, 0.96, 0.82))               # new teak's colour, held to the scan (teak_veneer)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(grain, 0.5, wood)))
    # weathered silver, then scrubbed blond, both keeping the grain's light and dark
    tone = w.add(1.0, w.mul(grain, 0.6))
    sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(SILVER)), tone), w.mul(w.term("silver"), 0.85, wood))
    sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(BLOND)), tone), w.mul(w.term("pale"), 0.75, wood))
    # dark with grime, algae and mildew, most in the soft early wood
    soft = w.m("SUBTRACT", 1.0, w.smooth(r, 0.45, 0.75))
    dark = w.mul(w.term("dark"), w.add(0.35, w.mul(soft, 0.5), w.mul(w.blot(pos, 0.25, 3.0), 0.4)), wood)
    sh.col = w.mix(sh.col, w.mix(MILDEW, (46, 54, 32), w.mul(w.blot(pos, 0.5, 8.0), 0.6)), w.sat(dark))
    sh.rough = w.lerp(sh.rough, 0.85, w.mul(w.term("silver"), 0.6))
    # checks open with the years (the map's checks repeat with its tile: patches pick which open)
    some = w.patches(pos, 0.3, 0.35, seed=29.0, detail=2.0, soft=0.12)
    chk = w.mul(g, w.term("checks"), wood, some, fade)
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.6), w.sat(w.mul(chk, 1.5)))
    if kind == "deck" and grp:
        # the marine glue fails: pale grey and standing proud in patches of seam
        fail = w.mul(seam, w.patches(pos, 0.15, w.mul(w.term("seams"), 0.6), seed=31.0, detail=2.0))
        sh.col = w.mix(sh.col, (120, 116, 108), fail)
        sh.bump(w.mul(fail, 0.0009))
    sh.finish()


def varnish(w, sh, kind):
    pos = w.obj()
    r, g, b = detail(w, sh, "WoodVarnish", pos, 0.00008)
    figure = w.m("SUBTRACT", r, 0.5)
    sh.col = w.scale(sh.col, w.add(1.0, w.mul(figure, 0.7)))
    if kind == "exterior":
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.72, 0.58, 0.42)), w.mul(w.term("amber"), 0.7))
    else:                                                            # below, out of the sun, the wood itself darkens
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.66, 0.52, 0.36)), w.term("amber"))
    # the gloss goes first on the tops and where hands go: rougher, with a faint salt haze
    top = w.sat(w.add(w.m("MAXIMUM", w.up(), 0.0), w.mul(w.edge(0.004 if kind == "exterior" else 0.006), 1.5)))
    dull = w.mul(w.term("dull"), w.add(0.4, w.mul(top, 0.6)))
    sh.rough = w.lerp(sh.rough, 0.55, dull)
    sh.coat = w.lerp(sh.coat, 0.25, dull)
    sh.col = w.mix(sh.col, w.mix(sh.col, (196, 182, 156), 0.3), w.mul(dull, top))
    if kind == "exterior":
        # the old film the sun has cooked: dark and brown, no longer the mahogany's red
        sh.col = w.mix(sh.col, w.scale(w.rgb(_lin(OLD_VARNISH)), w.add(1.0, w.mul(figure, 0.6))),
                       w.mul(w.term("fail"), 0.6))
        # the film goes first on the tops and edges; left long enough it goes everywhere
        # (a few patches at first, most of it gone when long neglected)
        fail = w.patches(pos, 0.06, w.mul(w.term("fail"), w.term("fail"), w.add(0.6, w.mul(top, 0.35))), seed=41.0,
                         detail=3.0, soft=0.04)
        # where it has gone the wood is grey, its grain standing out dark
        bare = w.scale(w.mix(GREY_WOOD, STAIN, w.mul(w.term("stain"), 0.5)), w.add(1.0, w.mul(figure, 1.2)))
        sh.col = w.mix(sh.col, bare, fail)
        sh.rough = w.lerp(sh.rough, 0.85, fail)
        sh.coat = w.lerp(sh.coat, 0.0, fail)
        sh.bump(w.mul(fail, -0.00012))
        stain = w.mul(w.term("stain"), w.smooth(w.noise(pos, 0.04, 43.0, stretch=(1.0, 1.0, 4.0)), 0.6, 0.7))
        sh.col = w.mix(sh.col, STAIN, w.mul(stain, 0.7))
    else:
        hands = w.mul(w.term("grime"), w.add(w.mul(w.edge(0.008), 0.7), w.mul(w.blot(pos, 0.3, 45.0), 0.45)))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.66, 0.62, 0.56)), w.sat(hands))
        bloom = w.mul(w.term("bloom"), w.patches(pos, 0.12, 0.35, seed=47.0, detail=2.0, soft=0.12))
        sh.col = w.mix(sh.col, BLOOM, w.mul(bloom, 0.5))
        sh.coat = w.lerp(sh.coat, 0.2, bloom)
        # water rings: the contour of a smooth noise is a closed ring about each blot
        n = w.noise(pos, 0.02, 49.0, detail=0.0)
        ring = w.mul(w.smooth(n, 0.655, 0.665), w.m("SUBTRACT", 1.0, w.smooth(n, 0.67, 0.68)))
        sh.col = w.mix(sh.col, STAIN, w.mul(ring, w.term("bloom"), w.sat(w.up()), 0.5))
        spots = w.patches(pos, 0.003, w.mul(w.term("stain"), 0.12), seed=53.0, soft=0.02, detail=1.0)
        sh.col = w.mix(sh.col, MILDEW, spots)
    sh.finish()


def bronze(w, sh, kind):
    pos = w.obj()
    cav, rough_v, _ = detail(w, sh, "CastBronze", pos, 0.00005)
    rec = w.sat(w.add(w.crevice(0.03, 0.3, 0.85), w.mul(w.m("SUBTRACT", 1.0, cav), 0.6)))
    worn = w.mul(w.edge(0.003), w.term("worn"))
    # the open faces brown, then darken; polished bright where hands and rope work it
    open_p = w.mul(w.term("patina"), w.m("SUBTRACT", 1.0, worn))
    ptn = w.mix(PATINA, PATINA_DARK, w.sat(w.mul(w.term("patina"), w.add(0.3, w.mul(w.blot(pos, 0.05, 61.0), 0.8)))))
    sh.col = w.mix(sh.col, ptn, w.sat(open_p))
    # the recesses keep theirs whatever the polish, going dark, almost black, with the years
    in_rec = w.mul(w.term("recess"), rec)
    sh.col = w.mix(sh.col, w.mix(PATINA, PATINA_DARK, w.term("dark")), w.sat(in_rec))
    patina = w.sat(w.m("MAXIMUM", open_p, in_rec))
    sh.rough = w.lerp(w.add(sh.rough, w.mul(w.m("SUBTRACT", rough_v, 0.5), 0.1)), 0.62, w.mul(patina, 0.8))
    sh.metal = w.lerp(sh.metal, 0.7, patina)
    crust = w.patches(pos, 0.015, w.mul(0.12, w.add(0.3, w.mul(w.sat(w.up()), 0.7))), seed=67.0, detail=2.0)
    vg = w.sat(w.mul(w.term("verdigris"), w.add(w.mul(rec, 0.6), w.mul(crust, 0.5))))
    sh.col = w.mix(sh.col, VERDIGRIS, vg)
    sh.rough = w.lerp(sh.rough, 0.9, vg)
    sh.metal = w.lerp(sh.metal, 0.0, vg)
    sh.bump(w.mul(vg, 0.0002))
    sh.finish()


def spar_uv(w):
    """The Spar UV (u metres along, v round as a share of the girth) and SparG's girth, and a mask that is 1 where the
    part has them (the bolt ropes on the sails and the headboards have none: the UV reads 0 there)."""
    u, v, _ = w.sep(w.uv("Spar"))
    girth = w.sep(w.uv("SparG"))[0]
    has = w.m("GREATER_THAN", w.add(w.m("ABSOLUTE", u), w.m("ABSOLUTE", v), w.m("ABSOLUTE", girth)), 0.0)
    return u, v, girth, has


def duralumin(w, sh, kind):
    pos = w.obj()
    _, g, _ = detail(w, sh, "Gelcoat", pos)
    sh.rough = w.add(sh.rough, w.mul(w.m("SUBTRACT", g, 0.5), 0.08))
    sh.rough = w.lerp(sh.rough, 0.6, w.term("gloss"))
    sh.coat = w.lerp(sh.coat, 0.05, w.term("gloss"))
    sh.col = w.mix(sh.col, w.scale(sh.col, (1.0, 0.95, 0.8)), w.term("yellow"))
    # the paint chalks to a flat pale buff, in big soft clouds
    ch = w.sat(w.mul(w.term("chalk"), w.add(0.45, w.mul(w.blot(pos, 0.5, 71.0), 0.8))))
    sh.col = w.mix(sh.col, chalky(w, sh.col, (228, 220, 200), 0.5), ch)
    sh.rough = w.lerp(sh.rough, 0.85, w.mul(ch, 0.7))
    sh.coat = w.lerp(sh.coat, 0.0, ch)
    # grey marks where the halyards slap: short dashes along the spar, gathered on one side of it
    u, v, girth, has = spar_uv(w)
    sv = w.comb(u, w.mul(v, girth), 0.0)
    dash = w.patches(sv, 0.02, w.mul(w.term("slap"), 0.12), seed=73.0, detail=2.0, soft=0.04, stretch=(4.0, 1.0, 1.0))
    side = w.blot(w.comb(w.mul(u, 0.2), w.mul(v, girth), 0.0), 0.15, 74.0, detail=1.0)
    slap = w.mul(dash, side, has)
    sh.col = w.mix(sh.col, (118, 116, 110), w.mul(slap, 0.7))
    # grime runs down from the fittings: streaks along the vertical, most under what juts out
    streak = w.patches(pos, 0.03, 0.3, seed=77.0, detail=2.0, stretch=(1.0, 1.0, 12.0))
    gr = w.sat(w.mul(w.term("grime"), streak, w.add(0.4, w.mul(w.crevice(0.08), 1.2))))
    sh.col = w.mix(sh.col, w.mix(w.scale(sh.col, 0.6), GRIME, 0.3), w.mul(gr, 0.6))
    # the paint lets go: grey metal with white oxide powder round each flake
    # (most where water lies: at the fittings and on the upper side)
    where = w.add(0.6, w.mul(w.sat(w.up()), 0.5), w.mul(w.crevice(0.05), 0.8))
    flake = w.patches(pos, 0.05, w.mul(w.term("flake"), 0.12, where), seed=79.0, detail=4.0, soft=0.03)
    halo = w.mul(w.patches(pos, 0.05, w.mul(w.term("flake"), 0.22, where), seed=79.0, detail=4.0, soft=0.14),
                 w.m("SUBTRACT", 1.0, flake))
    mr, mg, _ = w.image("Metal", pos, tile_of("Metal"))
    bare = w.mix(DURAL, OXIDE, w.smooth(mr, 0.3, 0.9))
    bare = w.mix(w.scale(bare, 0.75), bare, w.m("SUBTRACT", 1.0, w.term("grime")))
    sh.col = w.mix(w.mix(sh.col, OXIDE, w.mul(halo, 0.8)), bare, flake)
    sh.rough = w.lerp(w.lerp(sh.rough, 0.95, w.mul(halo, 0.8)), w.add(0.35, w.mul(mg, 0.3)), flake)
    sh.metal = w.lerp(sh.metal, 1.0, flake)
    sh.coat = w.lerp(sh.coat, 0.0, w.sat(w.add(flake, halo)))
    sh.bump(w.mul(flake, -0.00015))
    sh.finish()


def cotton(w, sh, kind):
    pos = w.obj()
    if kind == "sail":
        x, y, _ = w.sep(w.uv("UV0"))                                 # metres: along the row from the luff, up
        vec = w.comb(x, y, 0.0)
        r, g, b = detail(w, sh, "Cotton", vec, 0.00012, box=False)
        height = y
    else:
        tile = 1.4 if kind == "canvas" else 1.0                      # the cots' canvas is a heavier weave
        r, g, b = w.image("Cotton", pos, tuple(t * tile for t in tile_of("Cotton")))
        sh.bump(w.mul(w.m("SUBTRACT", b, 0.5), 0.00015 * tile, w.fade(*fade_of("Cotton"))))
        height = w.wz()
    sh.col = w.scale(sh.col, w.add(0.97, w.mul(g, 0.06)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (1.0, 0.95, 0.8)), w.term("yellow"))
    dinge = w.mul(w.term("dinge"), w.add(0.4, w.mul(w.blot(pos, 0.8, 83.0), 0.9)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.72, 0.71, 0.68)), w.sat(dinge))
    foot = w.m("SUBTRACT", 1.0, w.smooth(height, 0.1, 2.0)) if kind == "sail" else w.val(0.6)
    grime = w.mul(w.term("grime"), foot, w.add(0.3, w.mul(w.blot(pos, 0.3, 89.0), 1.0)))
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.6, 0.52, 0.42)), w.sat(grime))
    # mildew: black specks, in drifts where the damp lay (more of them toward the foot)
    drift = w.patches(pos, 0.5, w.mul(w.term("mildew"), w.add(0.4, w.mul(foot, 0.4))), seed=101.0, detail=2.0,
                      soft=0.25)
    # (specks a few millimetres across: past a few metres they would only alias, so they fade into their own mean,
    # a grey mottle, as the game's fine detail fades)
    share = w.mul(w.term("mildew"), 0.2)
    specks = w.patches(pos, 0.006, share, seed=97.0, soft=0.03, detail=2.0)
    mil = w.mul(w.lerp(w.mul(share, 0.8), specks, w.fade(1.0, 4.0)), drift)
    sh.col = w.mix(sh.col, MILDEW, w.sat(mil))
    if kind == "sail":
        # rust streaks run aft from the hanks and slides along the luff
        streak = w.smooth(w.noise(vec, 0.03, 103.0, stretch=(8.0, 1.0, 1.0)), 0.6, 0.7)
        luff = w.m("SUBTRACT", 1.0, w.smooth(x, 0.05, 0.7))
        sh.col = w.mix(sh.col, RUST, w.mul(w.term("rust"), streak, luff, 0.7))
    elif kind == "stowed":
        rust = w.mul(w.term("rust"), w.smooth(w.noise(pos, 0.03, 103.0, stretch=(1.0, 1.0, 8.0)), 0.66, 0.74))
        sh.col = w.mix(sh.col, RUST, w.mul(rust, 0.6))
    sh.finish()


def manila(w, sh, kind):
    pos = w.obj()
    u, v, girth, has = spar_uv(w)
    s = w.mul(v, girth)                                               # metres round the rope
    ang = math.atan(math.pi / 3.4)                                    # the strands' helix (3.4 diameters a turn)
    ca, sa = math.cos(ang), math.sin(ang)
    along = w.add(w.mul(u, ca), w.mul(s, sa))
    across = w.add(w.mul(u, -sa), w.mul(s, ca))
    tile = tile_of("Manila")
    by_lay = w.image("Manila", w.comb(along, across, 0.0), tile, box=False)
    by_box = w.image("Manila", pos, tile)                             # a bolt rope has no Spar UV: projected
    r, g, b = (w.lerp(bx, ly, has) for bx, ly in zip(by_box, by_lay))
    sh.bump(w.mul(w.m("SUBTRACT", b, 0.5), 0.00025, w.fade(*fade_of("Manila"))))
    sh.col = w.scale(sh.col, (0.94, 1.0, 1.3))                        # new manila's colour, held to the scan (Rope001)
    sh.col = w.scale(sh.col, w.add(0.85, w.mul(r, 0.3)))
    hair = w.mul(g, w.add(0.3, w.mul(w.term("fuzz"), 0.9)), w.fade(0.4, 2.0))
    sh.col = w.mix(sh.col, w.scale(sh.col, 1.25), w.sat(hair))
    sh.col = w.mix(sh.col, (112, 104, 92), w.mul(w.term("grey"), 0.85))
    dark = w.mul(w.term("dark"), w.add(0.2, w.mul(w.blot(pos, 0.2, 107.0), 0.9)))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.6), w.sat(dark))
    mil = w.mul(w.term("mildew"), w.smooth(w.noise(pos, 0.01, 109.0, detail=3.0), 0.5, 0.62))
    sh.col = w.mix(sh.col, w.mix(MILDEW, (40, 54, 32), w.blot(pos, 0.1, 113.0)), w.mul(mil, 0.8))
    sh.rough = w.lerp(sh.rough, 0.95, w.term("fuzz"))
    sh.finish()


def wire(w, sh, kind):
    pos = w.obj()
    grp = [n for n in w.nt.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.name.endswith("Lay")]
    if grp:
        groove = w.smooth(w.mul(grp[0].outputs["Height"], -1.0), 0.0, 0.0015)
    else:
        groove = w.crevice(0.01)
    mr, mg, _ = detail(w, sh, "Metal", pos, 0.00004, pits=True)
    spangle = w.smooth(w.noise(pos, 0.006, 127.0, detail=0.0), 0.4, 0.6)
    sh.col = w.scale(sh.col, w.add(0.92, w.mul(spangle, w.lerp(0.16, 0.04, w.term("dull")))))
    sh.rough = w.lerp(w.add(sh.rough, w.mul(w.m("SUBTRACT", mg, 0.5), 0.1)), 0.7, w.term("dull"))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.82 if kind == "wire" else 0.9), w.term("dull"))
    bloom = w.mul(w.blot(pos, 0.05, 131.0), 0.5 if kind == "wire" else 1.2)
    ox = w.mul(w.term("oxide"), w.add(w.mul(groove, 0.9), bloom))
    sh.col = w.mix(sh.col, ZINC_WHITE, w.sat(ox))
    sh.metal = w.lerp(sh.metal, 0.0, w.sat(ox))
    sh.rough = w.lerp(sh.rough, 0.95, w.sat(ox))
    if kind == "zinc":
        # pure zinc: no iron to rust and nothing to oil; grey grime in the galley
        gr = w.mul(w.term("grime"), w.add(0.3, w.mul(w.crevice(0.04), 0.7), w.mul(w.blot(pos, 0.15, 133.0), 0.6)))
        sh.col = w.mix(sh.col, w.scale(sh.col, 0.45), w.sat(gr))
        sh.finish()
        return
    oil = w.term("oiled")
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.5), oil)
    sh.rough = w.lerp(sh.rough, 0.3, oil)
    sh.col = w.mix(sh.col, w.scale(sh.col, (0.8, 0.66, 0.52)), w.mul(w.term("rust"), 0.5))  # a brown stain all over
    runs_ = w.patches(pos, 0.02, w.mul(w.term("rust"), 0.45), seed=137.0, detail=2.0, stretch=(1.0, 1.0, 5.0))
    rust = w.mul(w.term("rust"), w.add(w.mul(groove, 0.9), runs_))
    sh.col = w.mix(sh.col, w.mix(RUST, RUST_DARK, w.noise(pos, 0.005, 139.0)), w.sat(rust))
    sh.metal = w.lerp(sh.metal, 0.0, w.sat(rust))
    sh.rough = w.lerp(sh.rough, 0.9, w.sat(rust))
    sh.finish()


def furnishings(w, sh, kind):
    pos = w.obj()
    lm = w.lum(sh.col)
    sh.col = w.mix(sh.col, w.mix(w.comb(lm, lm, lm), (190, 186, 176), 0.25), w.mul(w.term("fade"), 0.5))
    if kind == "porcelain":
        vo = w.N.new("ShaderNodeTexVoronoi")
        vo.feature = "DISTANCE_TO_EDGE"
        w.link(pos, vo.inputs["Vector"])
        vo.inputs["Scale"].default_value = 60.0
        craze = w.mul(w.m("SUBTRACT", 1.0, w.smooth(vo.outputs["Distance"], 0.0, 0.06)), w.term("stain"))
        sh.col = w.mix(sh.col, (120, 106, 84), w.mul(craze, 0.8))
        # brown stains in the bowl and under the taps, a dull film of scale over the rest
        stain = w.mul(w.term("stain"), w.sat(w.add(w.crevice(0.06), w.patches(pos, 0.05, 0.35, seed=171.0))))
        sh.col = w.mix(sh.col, (125, 95, 60), w.mul(stain, 0.8))
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.9, 0.88, 0.82)), w.term("stain"))
        sh.finish()
        return
    if kind == "linen":
        sh.col = w.mix(sh.col, w.scale(sh.col, (0.74, 0.73, 0.68)), w.term("grey"))
    if kind == "carpet":
        _, y, _ = w.sep(pos)
        path = w.m("SUBTRACT", 1.0, w.smooth(w.m("ABSOLUTE", y), 0.25, 0.5))
        worn = w.mul(w.term("worn"), path, w.add(0.4, w.mul(w.blot(pos, 0.2, 151.0), 0.8)))
        sh.col = w.mix(sh.col, w.mix(w.scale(sh.col, 0.8), (120, 100, 80), 0.3), w.sat(worn))
    else:
        worn = w.mul(w.term("worn"), w.add(w.mul(w.edge(0.01), 0.8), w.mul(w.patches(pos, 0.15, 0.3, seed=157.0), 0.6)))
        sh.col = w.mix(sh.col, w.scale(sh.col, 1.25), w.mul(w.sat(worn), 0.6))
        if kind in ("velvet", "leather"):
            sh.rough = w.lerp(sh.rough, w.m("SUBTRACT", sh.rough, 0.3), w.sat(worn))
    stain = w.mul(w.term("stain"), w.patches(pos, 0.08, 0.2, seed=163.0, detail=2.0))
    sh.col = w.mix(sh.col, w.scale(sh.col, 0.7), w.mul(stain, 0.6))
    mil = w.patches(pos, 0.004, w.mul(w.term("mildew"), 0.2), seed=167.0, soft=0.03, detail=1.0)
    sh.col = w.mix(sh.col, (110, 120, 96), w.mul(mil, 0.7))
    sh.finish()


DRESS = {"paint": paint, "teak": teak, "varnish": varnish, "bronze": bronze, "duralumin": duralumin,
         "cotton": cotton, "manila": manila, "wire": wire, "furnishings": furnishings}


def dress(level="L0"):
    """Adds the maps and the wear to every material in bpy.data that a card covers (by name), then sets them to
    `level`; returns the names dressed. Stops if the build made a material that no card covers."""
    import bpy
    names = {m.name for m in bpy.data.materials if not m.name.startswith("J_")}
    missing, extra = coverage(names)
    if missing:
        raise SystemExit(f"textures_bluebonnet.json covers no card or 'unweathered' entry for {missing}")
    idx = material_index()
    done = []
    for m in bpy.data.materials:
        if m.name not in idx or m.get("j_surface"):
            continue
        s, k = idx[m.name]
        w = W(m, s, k)
        sh = Shader(w)
        DRESS[s](w, sh, k)
        m["j_surface"], m["j_kind"] = s, k
        done.append(m.name)
    apply_level(level)
    return sorted(done)


def apply_level(level):
    """Sets every dressed material's wear terms to a level ("L0".."L4") or to (age, care)."""
    import bpy
    age, care = (LEVELS[level]["age"], LEVELS[level]["care"]) if isinstance(level, str) else level
    for m in bpy.data.materials:
        s = m.get("j_surface")
        if not s:
            continue
        a = amounts(s, m["j_kind"], age, care)
        for n in m.node_tree.nodes:
            if n.type == "VALUE" and n.name.startswith("wear:"):
                term = n.name[5:]
                if term not in a:
                    raise SystemExit(f"{m.name}: no amount for wear term {term} ({s}, {m['j_kind']})")
                n.outputs[0].default_value = a[term]
    bpy.context.scene["j_wear"] = level if isinstance(level, str) else f"{age},{care}"


def material_id(k):
    """A distinct flat colour (sRGB 0-1) for the k-th dressed material (k from 1), for the id renders."""
    return ((k % 4) / 3.0, (k // 4 % 4) / 3.0, (k // 16 % 4) / 3.0)


def dressed():
    import bpy
    return sorted((m for m in bpy.data.materials if m.get("j_surface")), key=lambda m: m.name)


def albedo_mode(mode):
    """mode "albedo" (or True): each dressed material renders its colour alone (an emission of what feeds its Base
    Color), for measuring the levels' colours (wear_check.py) without the light; "id": each renders its own flat colour
    (material_id, in name order), so the measure knows which pixels are which material; False puts the shaders back.
    In both modes the unweathered glass, lenses and mirrors hold out (black, nothing behind them seen)."""
    import bpy
    if mode is True:
        mode = "albedo"
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
            m["j_shader_node"], m["j_shader_out"] = src.node.name, list(src.node.outputs).index(src)
        idn = nt.nodes["wear:id"]
        idn.inputs["Color"].default_value = (*_lin(tuple(255.0 * c for c in material_id(k))), 1.0)
        if mode == "albedo":
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        elif mode == "id":
            nt.links.new(idn.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(nt.nodes[m["j_shader_node"]].outputs[m["j_shader_out"]], out.inputs["Surface"])
    # glass, lenses and mirrors would pass on (and dim) the id colours behind them: they hold out, measured as nothing
    for m in bpy.data.materials:
        if m.name not in CARDS["unweathered"] or not m.use_nodes:
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
        if out is None or not (out.inputs["Surface"].is_linked or nt.nodes.get("wear:holdout")):
            continue
        ho = nt.nodes.get("wear:holdout")
        if ho is None:
            ho = nt.nodes.new("ShaderNodeHoldout")
            ho.name = ho.label = "wear:holdout"
            src = out.inputs["Surface"].links[0].from_socket
            m["j_shader_node"], m["j_shader_out"] = src.node.name, list(src.node.outputs).index(src)
        if mode in ("albedo", "id"):
            nt.links.new(ho.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(nt.nodes[m["j_shader_node"]].outputs[m["j_shader_out"]], out.inputs["Surface"])


def report(material_names):
    """build.json's 'textures': the cards' coverage, the maps and their budget, every level's amounts."""
    missing, extra = coverage(material_names)
    meta = json.load(open(os.path.join(REPO, "Inputs", "jclass-detail", "jclass_detail.json")))
    own = {}
    total_high = 0.0
    for name in CARDS["maps"]["own"]:
        w, h = meta[name]["px"]
        mb = (w * h * 1.0 + w * h * 0.5) * 4.0 / 3.0 / 2 ** 20      # BC5 normal (1 B/px) + BC1 mask (0.5 B/px), mips
        own[name] = dict(meta[name], mb_high=round(mb, 3), medium=bool(CARDS["maps"]["own"][name].get("medium")))
        total_high += mb
    used = {}
    for s, card in CARDS["surfaces"].items():
        for mp in card["maps"]:
            used.setdefault(mp, []).append(s)
    return {"surfaces": {s: {"kinds": c["kinds"], "maps": c["maps"]} for s, c in CARDS["surfaces"].items()},
            "unweathered": sorted(CARDS["unweathered"]),
            "uncovered": missing, "not_built": extra,
            "maps_own": own, "maps_shared": sorted(m for m in used if m not in CARDS["maps"]["own"]),
            "maps_used_by": used,
            "budget": {"high_mb": round(total_high, 3), "high_cap_mb": CARDS["budget"]["high_mb"],
                       "medium_mb": round(sum(o["mb_high"] for o in own.values() if o["medium"]), 3),
                       "medium_cap_mb": CARDS["budget"]["medium_mb"]},
            "closest_px_per_mm": {n: o["px_per_mm"] for n, o in own.items()},
            "levels": {lv: level_amounts(lv) for lv in LEVELS}}


if __name__ == "__main__":
    for lv in LEVELS:
        print(lv, json.dumps(level_amounts(lv)))
