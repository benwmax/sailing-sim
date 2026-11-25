"""The moth's looks and wear (docs/moth-10): how much of each kind of wear a level brings, and where on her it falls.

    import weathering_moth as WE
    WE.amounts("carbon", "tube", 6.0, 0.5)    # {"haze": 0.6, ...}, no Blender needed
    WE.dress()                                 # in the build: every material's look, detail maps and wear terms
    WE.apply_level("L2")                       # in a render: sets every material to a level (or (age, care))
    WE.albedo_mode("albedo" | "id" | None)     # the colour alone (for measuring), material ids, or lit

As the J-Class's slice 11 (Tools/shipkit/jclass/weathering.py, whose node helpers this borrows): the texture loop's five
levels (Tools/texloop/levels.json) are fixed points of E1's Age (years) and Care (0 left in the yard .. 1 kept), and its
two numbers (Tools/texloop/wear.py) split them into what the years do whatever the owner does (time_k: the clear coat
ambering, the white paint going cream, the mesh fading) and what care takes away (dirt_k: haze, chalk, grime, mildew,
dings left unfilled). amounts() turns those into each surface's own terms, 0 to 1; textures_moth.json says what each
level should look like and which of her materials each surface covers. dress() builds each material from scratch (her
.blend had viewport colours only), its patterns scaled by a Value node per term ("wear:<term>"), so one build renders
any level: apply_level() only sets those values. The terms are kept to what a pixel shader can do (noise, the height,
which way a face looks, the camera's distance, crevices and edges: a baked cavity map in the game), so the game's
material can take the same amounts from the boat's Age and Care when she is imported (slice 9).

Every pattern is in metres in the part's own frame or its UVs: the carbon's twill and the lines' braid round each tube
by its Tube UV (build_moth.add_tube), the rest projected three ways; the detail maps tile at their real size
(textures.py, the boats' library) and fade out with the camera's distance as the game's do.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
import wear as loop  # noqa: E402

CARDS = json.load(open(os.path.join(HERE, "textures_moth.json")))
SHARED_META = json.load(open(os.path.join(REPO, "Inputs", "boat-detail", "detail_textures.json")))
LEVELS = {lv["id"]: lv for lv in loop.levels()}
FRESH = 1.0 / 3.0            # Ray Hubbard is fresh water: the lake's third of the salt-water corrosion (docs/texture-loop)


def sat(x):
    return max(0.0, min(1.0, x))


def ramp(x, lo, hi):
    """0 under lo, 1 over hi, straight between."""
    return sat((x - lo) / (hi - lo))


def refreshed(age, care):
    """How much a kept boat's routine (washed after every sail, the foils' dings filled and faired each winter, the clear
    coat polished) has undone the first-season marks: none in her first season, most when well kept."""
    return care ** 2 * ramp(age, 0.5, 2.0)


def renewed(age, care, life):
    """The age of a part a kept boat renews every `life` years or so (on average half that old; a neglected one hardly
    ever): the sail, the lines, the mesh, the grip."""
    return min(age, 0.5 * life / max(care ** 2, 0.02))


def amounts(surface, kind, age, care):
    """Each wear term, 0 to 1, for one surface and kind at E1's Age (years) and Care (0..1). dirt_k takes a year to come
    up and then holds, so a first season's marks (scratches, scuffs, dust) go as its square root, times `fresh` where a
    kept boat's routine takes them away again; what neglect alone does (the coat flaking, mildew, oxide, chips left)
    starts past a threshold of dirt_k that a kept boat never reaches (L3's 0.24)."""
    t, d = loop.time_k(age, care), loop.dirt_k(age, care)
    fresh = 1.0 - 0.85 * refreshed(age, care)
    first = math.sqrt(d) * fresh
    if surface == "carbon":
        return {"scratch": sat(1.3 * first),                       # hairlines where hands, the boom and the wand touch
                "haze": sat(1.1 * d * fresh + 0.1 * t),           # the coat dulls; polished, it comes back
                "amber": t,                                        # epoxy yellows in the sun, refinished or not
                "chalk": ramp(d, 0.45, 0.95),                     # the coat breaks down: the fibre blooms grey
                "grime": ramp(d, 0.2, 0.9) * fresh}               # dirt in the scratches and the joints
    if surface == "paint":
        a = {"gloss": sat(0.8 * first + 0.2 * t),                 # the paint's shine; polished, most comes back
             "chalk": max(d * fresh, 0.3 * t) * (1.0 if kind != "deck" else 0.6),
             "yellow": 0.8 * t,                                   # white paint goes cream with the years
             "scuff": sat(1.4 * first),                           # the trolley and the ramp along the bottom
             "streaks": ramp(d, 0.3, 0.9),                        # black runs from every fitting
             "scum": sat(sat(1.5 * first) * (1.0 - 0.5 * care) + ramp(d, 0.6, 0.95))}
        if kind == "hull":
            a["tape"] = ramp(d, 0.2, 0.6) * fresh                 # tape residue round the case and the gantry's feet
        elif kind == "deck":
            a = {"dust": sat(1.5 * first), "worn": sat(t + 0.5 * d), "chalk": a["chalk"], "yellow": a["yellow"],
                 "grime": ramp(d, 0.2, 0.9) * fresh}
        elif kind == "foil":
            a = {"gloss": a["gloss"], "chalk": a["chalk"],
                 "scratch": sat(1.4 * first),                     # spanwise scratches from weed, sand and the trolley
                 "dings": sat(1.6 * first + 0.4 * t) * (1.0 - 0.6 * refreshed(age, care)),   # knocks; kept: faired
                 # filled and faired each winter (none yet in her first season): the white filler shows through
                 "filler": sat(2.0 * first * care * ramp(age, 0.5, 2.0) + 0.35 * t * care),
                 "filler_show": 0.9 - 0.55 * refreshed(age, care),
                 "chips": ramp(d, 0.45, 0.95),                    # left: the paint chips to grey primer
                 "scum": ramp(d, 0.5, 0.95)}                      # left in the water
        return a
    if surface == "mesh":
        own = renewed(age, care, 6.0)
        mt, md = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"fade": sat(1.2 * mt), "dust": sat(1.2 * math.sqrt(md)), "shine": sat(1.5 * mt) * care,
                "mildew": ramp(md, 0.55, 0.95), "brown": ramp(md, 0.5, 0.95)}
    if surface == "sail":
        own = renewed(age, care, 3.0)
        st, sd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"crease": sat(0.9 * math.sqrt(sd) + 0.3 * st), "haze": sat(0.9 * sd + 0.4 * st),
                "yellow": sat(1.3 * st ** 1.5), "mildew": ramp(sd, 0.55, 0.95), "grime": ramp(sd, 0.3, 0.9)}
    if surface == "rope":
        own = renewed(age, care, 3.0)
        rt, rd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"fade": sat(0.7 * math.sqrt(rd) + 0.6 * rt), "fuzz": sat(0.8 * math.sqrt(rd) + 0.3 * rt),
                "grime": rd, "mildew": ramp(rd, 0.5, 0.9)}
    if surface == "alloy":
        polish = 0.7 * care * sat(age / 3.0)
        return {"dull": sat(0.6 * first + 0.6 * t) * (1.0 - 0.5 * polish),
                "scratch": sat(1.3 * first + 0.2 * t),            # edges knocked through to bright metal
                "hairlines": sat(1.1 * t),                        # years of use: fine scratches over the faces
                "fade": sat(1.2 * t),                             # the anodising fades in the sun
                "oxide": ramp(d, 0.45, 0.95) * (0.5 + 0.5 * FRESH),  # white powder, slower in fresh water
                "grime": ramp(d, 0.3, 0.9)}                       # never washed: brown grime over the dulled metal
    if surface == "grip":
        own = renewed(age, care, 4.0)
        gt, gd = loop.time_k(own, care), loop.dirt_k(own, care)
        return {"shine": sat(1.5 * math.sqrt(gd)) * (1.0 - ramp(gd, 0.6, 0.95)),   # worn smooth; left, it chalks
                "grime": sat(1.2 * gd), "chalk": sat(0.8 * gt + ramp(gd, 0.5, 0.95)), "cracks": ramp(gd, 0.6, 0.95)}
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
                    raise SystemExit(f"textures_moth.json: {n} is in two cards ({out[n]} and {(s, k)})")
                out[n] = (s, k)
    return out


def coverage(material_names):
    """The materials the build makes that no card covers, and the card entries the build does not make (both must be
    empty)."""
    idx = material_index()
    un = set(CARDS["unweathered"])
    names = set(material_names)
    return sorted(names - set(idx) - un), sorted((set(idx) | un) - names)


def material_id(k):
    """Material k's id colour as the image shows it: each channel a third (0..3), code = r + 4 g + 16 b, from 1 (0 is
    the background)."""
    c = k + 1
    return (c % 4 / 3.0, c // 4 % 4 / 3.0, c // 16 % 4 / 3.0)


def material_id_linear(k):
    """material_id in linear light, so the sRGB image holds the thirds exactly."""
    return tuple(_lin((v * 255.0,))[0] for v in material_id(k))


def map_path(name, ch="M"):
    if name in CARDS["maps"]["own"]:
        return os.path.join(REPO, "Inputs", "moth-detail", f"T_Moth_{name}_{ch}.png")
    return os.path.join(REPO, "Inputs", "boat-detail", f"T_Detail_{name}_{ch}.png")


def tile_of(name):
    m = CARDS["maps"]["own"].get(name) or CARDS["maps"]["shared"][name]
    return (m["tile_mm"][0] / 1000.0, m["tile_mm"][1] / 1000.0)


def fade_of(name):
    own = CARDS["maps"]["own"].get(name)
    if own:
        return tuple(own.get("fade_m", (1.0, 4.0)))
    return tuple(SHARED_META.get(name, {}).get("fade_m", (1.0, 4.0)))


def report(material_names):
    """The build's texture summary (moth_report.json's 'textures')."""
    chk = os.path.join(REPO, "Inputs", "moth-detail", "check.json")
    return {"materials": {n: "/".join(material_index()[n]) for n in sorted(material_names)},
            "maps": json.load(open(chk)) if os.path.exists(chk) else "run textures.py",
            "levels": {lv: level_amounts(lv) for lv in LEVELS}}


# ================================================================================================ Blender
def _lin(c):
    """sRGB 0-255 to linear."""
    return tuple((v / 255.0) / 12.92 if v / 255.0 <= 0.04045 else ((v / 255.0 + 0.055) / 1.055) ** 2.4 for v in c)


# her colours, sRGB 0-255 (the renders'; the game's livery can change the hull's paint, not these)
CARBON = (20, 20, 22)
FIBRE_BLOOM = (128, 128, 124)        # the bare weave where the coat has gone: grey, fuzzy
AMBER = (255, 196, 110)              # the clear coat's tint after decades of sun
HULL_WHITE = (238, 238, 233)
CREAM = (232, 222, 188)
SCUFF = (112, 110, 102)
TAPE = (190, 186, 168)
STREAK = (60, 58, 54)
SCUM = (96, 104, 58)
FOIL_GREY = (44, 45, 48)
FILLER = (214, 210, 198)
PRIMER = (150, 150, 146)
MESH_BLACK = (14, 14, 15)
MESH_FADED = (82, 80, 76)
MESH_BROWN = (98, 86, 68)
DUST = (150, 140, 120)
MILDEW = (30, 34, 28)
FILM = (250, 250, 248)
FILM_YELLOW = (228, 210, 150)
SCRIM_THREAD = (52, 52, 56)
LINE_ORANGE = (222, 96, 28)
SHROUD_GREY = (160, 160, 158)
LINE_FADED = (204, 150, 112)
GRIME = (78, 72, 60)
ANODISE = (196, 198, 204)
OXIDE = (224, 224, 216)
RUBBER = (22, 22, 23)
RUBBER_CHALK = (70, 70, 68)


def _jw():
    sys.path.insert(0, os.path.join(REPO, "Tools", "shipkit", "jclass"))
    import weathering as JW
    return JW


def make_w(mt, surface, kind):
    """The J-Class's node helpers (W), sampling her maps instead of the J-Class's."""
    JW = _jw()

    class W(JW.W):
        def image(self, name, vec, tile_m, box=True, ch="M"):
            import bpy
            path = map_path(name, ch)
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

    return W(mt, surface, kind)


class Look:
    """One material built from scratch: sockets for its colour, roughness, metal, clear coat, anisotropy and opacity,
    heights (metres) for its bump; finish() wires a Principled BSDF (or, for the film, a clear sheet) and the albedo and
    id modes behind it."""

    def __init__(self, mt, surface, kind):
        mt.use_nodes = True
        for n in list(mt.node_tree.nodes):
            mt.node_tree.nodes.remove(n)
        self.mt = mt
        self.w = make_w(mt, surface, kind)
        w = self.w
        self.col = w.rgb(_lin((128, 128, 128)))
        self.rough = w.val(0.5)
        self.metal = w.val(0.0)
        self.coat = w.val(0.0)
        self.coat_rough = w.val(0.03)
        self.coat_tint = None
        self.aniso = None
        self.aniso_rot = None
        self.tangent = None
        self.opacity = None           # None: opaque
        self.heights = []
        self.film = None              # the sail: (transmitted tint, haze colour)
        self.albedo = None            # the colour the albedo mode shows, when it is not col (the film)

    def bump(self, h):
        self.heights.append(h)

    def finish(self):
        import bpy  # noqa: F401
        w = self.w
        N, L = w.N, w.L
        out = N.new("ShaderNodeOutputMaterial")
        b = N.new("ShaderNodeBsdfPrincipled")
        for nm, s in (("Base Color", self.col), ("Roughness", self.rough), ("Metallic", self.metal),
                      ("Coat Weight", self.coat), ("Coat Roughness", self.coat_rough)):
            L.new(s, b.inputs[nm])
        if self.coat_tint is not None:
            L.new(self.coat_tint, b.inputs["Coat Tint"])
        if self.aniso is not None:
            L.new(self.aniso, b.inputs["Anisotropic"])
            L.new(self.aniso_rot, b.inputs["Anisotropic Rotation"])
            if self.tangent is not None:
                L.new(self.tangent, b.inputs["Tangent"])
        if self.heights:
            h = w.add(*self.heights) if len(self.heights) > 1 else self.heights[0]
            bp = N.new("ShaderNodeBump")
            bp.name = bp.label = "wear:bump"
            bp.inputs["Distance"].default_value = 1.0
            L.new(h, bp.inputs["Height"])
            L.new(bp.outputs[0], b.inputs["Normal"])
            L.new(bp.outputs[0], b.inputs["Coat Normal"])
        shader = b.outputs[0]
        if self.film is not None:
            # a clear sheet: light through it tinted by the film, the scrim and haze scattering, a thin reflection
            tint, haze_col = self.film
            tr = N.new("ShaderNodeBsdfTransparent")
            L.new(tint, tr.inputs[0])
            b.inputs["Coat Weight"].default_value = 0.0
            mx = N.new("ShaderNodeMixShader")
            L.new(self.opacity, mx.inputs[0])
            L.new(tr.outputs[0], mx.inputs[1])
            L.new(b.outputs[0], mx.inputs[2])
            gl = N.new("ShaderNodeBsdfGlossy")
            gl.inputs["Roughness"].default_value = 0.06
            fr = N.new("ShaderNodeFresnel")
            fr.inputs["IOR"].default_value = 1.6
            if self.heights:
                L.new(bp.outputs[0], gl.inputs["Normal"])
                L.new(bp.outputs[0], fr.inputs["Normal"])
            mx2 = N.new("ShaderNodeMixShader")
            L.new(fr.outputs[0], mx2.inputs[0])
            L.new(mx.outputs[0], mx2.inputs[1])
            L.new(gl.outputs[0], mx2.inputs[2])
            shader = mx2.outputs[0]
        elif self.opacity is not None:
            L.new(self.opacity, b.inputs["Alpha"])
        # the measuring modes: the colour alone (albedo), or the material's id colour, as an unlit opaque emission
        mode = N.new("ShaderNodeValue")
        mode.name = mode.label = "mode:emit"
        ident = N.new("ShaderNodeValue")
        ident.name = ident.label = "mode:id"
        idc = N.new("ShaderNodeRGB")
        idc.name = idc.label = "mode:idcolour"
        em_col = w.mix(self.col if self.albedo is None else self.albedo, idc.outputs[0], ident.outputs[0])
        em = N.new("ShaderNodeEmission")
        L.new(em_col, em.inputs[0])
        final = N.new("ShaderNodeMixShader")
        L.new(mode.outputs[0], final.inputs[0])
        L.new(shader, final.inputs[1])
        L.new(em.outputs[0], final.inputs[2])
        L.new(final.outputs[0], out.inputs["Surface"])


# ------------------------------------------------------------------------------------------------ the surfaces
def detail(lk, name, vec, box=True, ch="M"):
    """A detail map's (r, g, b) and its fade with the camera's distance."""
    w = lk.w
    r, g, b = w.image(name, vec, tile_of(name), box=box, ch=ch)
    return r, g, b, w.fade(*fade_of(name))


def tube_uv(w):
    return w.uv("Tube")


def carbon(lk, kind):
    w = lk.w
    r, g, b, fd = detail(lk, "CarbonTwill", tube_uv(w), box=False)
    T = w.term
    obj = w.obj()
    # the twill: each tow a little lighter or darker by which way it runs, its filaments' sheen turned with it
    col = w.mix(CARBON, (30, 30, 33), w.mul(r, fd, 0.6))
    rough = w.add(0.22, w.mul(g, 0.16))
    lk.aniso = w.mul(0.75, fd)
    lk.aniso_rot = w.mul(r, 0.25)
    tg = w.N.new("ShaderNodeTangent")
    tg.direction_type = "UV_MAP"
    tg.uv_map = "Tube"
    lk.tangent = tg.outputs[0]
    lk.bump(w.mul(w.m("SUBTRACT", b, 0.5), 0.00006, fd))
    # scratches: fine hairlines in every direction, densest where hands and the boom work, lighter in the coat
    sc1 = w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", w.noise(obj, 0.02, 3.0, detail=1, stretch=(4.0, 0.15, 0.15)), 0.5)),
                   0.012, 0.0)
    sc2 = w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", w.noise(obj, 0.02, 7.0, detail=1, stretch=(0.15, 4.0, 1.0)), 0.5)),
                   0.012, 0.0)
    scr = w.mul(w.sat(w.add(sc1, sc2)), w.patches(obj, 0.12, w.mul(T("scratch"), 0.7), seed=4.0), T("scratch"))
    haze = T("haze")
    coat_rough = w.add(0.03, w.mul(haze, 0.28), w.mul(scr, 0.35))
    col = w.mix(col, (70, 70, 72), w.add(w.mul(scr, 0.35), w.mul(haze, 0.12)))
    # amber: the coat yellows, most on the faces the sun sees
    sun = w.add(0.55, w.mul(w.sat(w.up()), 0.45))
    # chalk: the clear coat breaks down. It goes milky first (a whitish haze over a weave still seen through it, most
    # where the sun reaches), then lifts in small flakes: the bare fibre under them dark, matte and fuzzy, the weave
    # plain in it, a pale rim of lifted coat round each (round 2's reviewers read big pale patches as paint)
    milk = w.mul(T("chalk"), w.sat(w.add(0.1, w.mul(w.sat(w.up()), 0.45), w.mul(w.blot(obj, 0.12, 1.0), 0.35))))
    lk.coat_tint = w.mix((255, 255, 255), AMBER, w.mul(T("amber"), sun, 0.55, w.m("SUBTRACT", 1.0, w.mul(milk, 0.8))))
    col = w.mix(col, (52, 44, 30), w.mul(T("amber"), sun, 0.15))
    col = w.mix(col, w.mix((146, 146, 142), (178, 178, 174), r), w.mul(milk, 0.7))   # the weave shows through, faintly
    flaking = w.patches(obj, 0.08, w.mul(T("chalk"), 0.35), seed=19.0, soft=0.3)   # it lifts in a few places
    amt = w.mul(T("chalk"), 0.3, flaking, w.add(0.3, w.sat(w.up())))
    gone = w.patches(obj, 0.01, amt, seed=9.0, soft=0.03, detail=2.0)
    rim = w.m("SUBTRACT", w.patches(obj, 0.01, w.mul(amt, 1.5), seed=9.0, soft=0.03, detail=2.0), gone)
    bare = w.mix((96, 96, 94), (118, 118, 114), r)          # bare fibre: grey and fuzzy
    col = w.mix(col, bare, gone)
    col = w.mix(col, (200, 198, 192), w.mul(w.sat(rim), 0.35))
    lk.coat = w.m("SUBTRACT", 1.0, w.sat(w.add(gone, w.mul(milk, 0.5))))
    rough = w.lerp(rough, 0.9, w.sat(w.add(gone, w.mul(milk, 0.5))))
    lk.aniso = w.mul(lk.aniso, w.m("SUBTRACT", 1.0, gone))
    lk.bump(w.add(w.mul(w.sat(rim), 0.00012), w.mul(gone, -0.00006)))
    # grime in the scratches and joints
    cr = w.crevice(0.01)
    col = w.mix(col, GRIME, w.mul(T("grime"), w.add(w.mul(scr, 0.8), w.mul(cr, 0.6), w.mul(gone, 0.3))))
    lk.col, lk.rough, lk.coat_rough = col, rough, coat_rough


def paint(lk, kind):
    w = lk.w
    T = w.term
    obj = w.obj()
    pos = w.geo("Position")
    if kind == "deck":
        r, g, b, fd = detail(lk, "NonSkid", obj)
        col = w.mix(HULL_WHITE, (215, 215, 208), w.mul(r, 0.5, fd))
        lk.bump(w.mul(w.m("SUBTRACT", b, 0.5), 0.0004, fd))
        col = w.mix(col, DUST, w.mul(T("dust"), w.add(w.mul(r, fd, 0.6), 0.15), 0.6))
        col = w.mix(col, CREAM, w.mul(T("yellow"), 0.55))
        col = w.mix(col, (200, 200, 196), w.mul(T("chalk"), 0.5))
        # the sailor's knees and feet: grime and worn grip in patches along the middle of the deck
        walk = w.patches(obj, 0.25, w.mul(T("grime"), 0.4), seed=12.0, stretch=(3.0, 1.0, 1.0), soft=0.4)
        col = w.mix(col, GRIME, w.mul(walk, 0.3))
        lk.col = col
        lk.rough = w.lerp(w.add(0.55, w.mul(g, 0.15)), 0.35, w.mul(T("worn"), g, 0.5))
        return
    if kind == "foil":
        r, g, b, fd = detail(lk, "Gelcoat", obj)
        col = w.rgb(_lin(FOIL_GREY))
        rough = w.add(0.32, w.mul(g, 0.1, fd), w.mul(T("gloss"), 0.25))
        # spanwise scratches (the foils' span runs across y)
        sc = w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", w.noise(obj, 0.03, 2.0, detail=1, stretch=(0.08, 5.0, 0.3)),
                                            0.5)), 0.01, 0.0)
        scr = w.mul(sc, w.patches(obj, 0.15, w.mul(T("scratch"), 0.8), seed=3.0), T("scratch"))
        col = w.mix(col, (120, 120, 118), w.mul(scr, 0.7))
        nx, _, _ = w.sep(w.geo("Normal"))
        edge = w.mul(w.edge(0.006), w.smooth(nx, 0.1, 0.5))          # the leading edges (forward is +x) take the knocks
        # dings on the edges; filled and faired (white filler), or left and chipped to grey primer
        ding = w.mul(edge, w.patches(obj, 0.012, w.mul(T("dings"), 0.5), seed=5.0, soft=0.03))
        where = w.patches(obj, 0.2, 0.15, seed=16.0, soft=0.3)          # knocks come in a few stretches of edge
        fill = w.mul(w.sat(w.add(w.patches(obj, 0.012, w.mul(T("filler"), 0.35), seed=6.0, soft=0.1, detail=2.0),
                                 w.patches(obj, 0.04, w.mul(T("filler"), 0.25), seed=17.0, soft=0.15,
                                           stretch=(1.0, 2.0, 1.0)))),
                     where, w.sat(w.mul(edge, 2.0)))
        chip = w.mul(w.patches(obj, 0.01, w.mul(T("chips"), 0.4), seed=7.0, soft=0.04), w.sat(w.mul(edge, 2.5)))
        col = w.mix(col, (90, 90, 90), w.mul(ding, 0.8))
        col = w.mix(col, FILLER, w.mul(fill, T("filler_show")))     # painted over on a kept boat: it shows faintly
        col = w.mix(col, PRIMER, chip)
        lk.bump(w.mul(w.add(fill, w.mul(chip, -1.0), w.mul(ding, -1.0)), 0.00015))
        rough = w.lerp(rough, 0.75, w.add(fill, chip))
        col = w.mix(col, (120, 120, 118), w.mul(T("chalk"), 0.35))
        rough = w.lerp(rough, 0.8, T("chalk"))
        scum = w.mul(T("scum"), w.patches(obj, 0.1, 0.6, seed=8.0, soft=0.4))
        col = w.mix(col, (96, 98, 84), w.mul(scum, 0.3))
        lk.col, lk.rough = col, rough
        return
    # the hull's white paint
    r, g, b, fd = detail(lk, "Gelcoat", obj)
    col = w.rgb(_lin(HULL_WHITE))
    rough = w.add(0.1, w.mul(g, 0.06, fd), w.mul(T("gloss"), 0.32))
    col = w.mix(col, CREAM, w.mul(T("yellow"), 0.75))
    chalk = w.mul(T("chalk"), w.add(0.85, w.mul(w.blot(obj, 0.6, 2.0, detail=1), 0.15)))
    col = w.mix(col, (206, 205, 199), w.mul(chalk, 0.8))      # chalked: a flat grey-white powder over the cream
    rough = w.lerp(rough, 0.75, chalk)
    x, y, z = w.sep(pos)
    # scuffs: the trolley's pads and the ramp along the bottom and chines, the bow's knocks
    low = w.m("SUBTRACT", 1.0, w.smooth(z, -0.06, 0.0))           # the bottom, where the trolley's pads and the ramp go
    bow = w.mul(w.smooth(x, 1.55, 1.7), w.m("SUBTRACT", 1.0, w.smooth(z, 0.1, 0.25)))   # knocks low on the stem
    sc = w.patches(obj, 0.015, w.mul(T("scuff"), 0.12), seed=11.0, stretch=(5.0, 1.0, 0.5), soft=0.25, detail=2.0)
    near_pads = w.patches(obj, 0.15, 0.3, seed=18.0, soft=0.3)                 # where the trolley's pads sat
    scuff = w.mul(sc, near_pads, w.sat(w.add(low, w.mul(bow, 0.6))))
    col = w.mix(col, SCUFF, w.mul(scuff, 0.5))
    rough = w.lerp(rough, 0.6, scuff)
    # tape residue: rectangles round the foil case (x about 0.15) and the gantry's feet at the transom
    tape = w.add(w.mul(w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", x, 0.14)), 0.08, 0.075),
                       w.smooth(w.m("ABSOLUTE", y), 0.07, 0.065)),
                 w.mul(w.m("SUBTRACT", 1.0, w.smooth(x, -1.62, -1.6)), w.smooth(z, 0.05, 0.07)))   # aft of x -1.6 only
    col = w.mix(col, TAPE, w.mul(T("tape"), w.sat(tape), w.add(0.6, w.mul(w.blot(obj, 0.02, 4.0), 0.4))))
    # black streaks running down the topsides from the deck edge and fittings
    down0 = w.smooth(z, 0.12, 0.24)
    # (thin near-vertical lines a few mm wide, only some of them; round 2's blotches read as a lace pattern)
    run = w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", w.noise(obj, 0.05, 13.0, detail=1, stretch=(1.0, 1.0, 12.0),
                                                           distort=0.4), 0.5)),
                   w.add(0.006, w.mul(down0, 0.014)), 0.0)                # wider and softer near the sheer
    some = w.patches(obj, 0.12, w.mul(T("streaks"), 0.8), seed=16.0, soft=0.2, stretch=(1.0, 1.0, 40.0))
    length = w.add(0.025, w.mul(w.noise(obj, 0.03, 14.0, detail=0, stretch=(1.0, 1.0, 40.0)), 0.16))
    top = 0.24
    down = w.m("POWER", w.smooth(z, w.m("SUBTRACT", top, length), top), 2.0)   # 1 at the sheer, tapering away below
    col = w.mix(col, STREAK, w.mul(run, some, down, 0.4))
    # a scum line where she sat in the water: a crisp top edge, a little wavy, fading below it
    wav = w.mul(w.m("SUBTRACT", w.noise(obj, 0.08, 15.0, detail=1), 0.5), 0.01)
    band = w.mul(w.m("SUBTRACT", 1.0, w.smooth(z, w.add(0.002, wav), w.add(0.004, wav))),
                 w.smooth(z, w.add(-0.045, wav), w.add(0.0, wav)))
    col = w.mix(col, SCUM, w.mul(T("scum"), band, w.add(0.7, w.mul(w.blot(obj, 0.05, 1.0), 0.3)), 0.8))
    lk.col, lk.rough = col, rough


def mesh(lk, kind):
    w = lk.w
    T = w.term
    obj = w.obj()
    r, g, b, fd = detail(lk, "WingMesh", obj)
    col = w.mix(MESH_BLACK, (26, 26, 27), w.mul(b, 0.5))
    col = w.mix(col, MESH_FADED, w.mul(T("fade"), w.add(0.95, w.mul(w.blot(obj, 0.5, 1.0, detail=1), 0.05))))
    col = w.mix(col, MESH_BROWN, w.mul(T("brown"), 0.35))
    x, y, z = w.sep(w.geo("Position"))
    near = w.m("SUBTRACT", 1.0, w.smooth(w.m("ABSOLUTE", y), 0.3, 0.9))       # dust gathers by the hull
    dust = w.blot(obj, 0.05, 21.0, detail=1)
    col = w.mix(col, DUST, w.mul(T("dust"), w.add(w.mul(dust, 0.04), 0.2), w.add(0.4, w.mul(near, 0.6))))
    mil = w.mul(w.patches(obj, 0.0025, w.mul(T("mildew"), 0.25), seed=22.0, soft=0.1, detail=1.0),
                w.patches(obj, 0.015, w.mul(T("mildew"), 0.15), seed=24.0, soft=0.2))
    col = w.mix(col, MILDEW, w.mul(mil, 0.55))
    knees = w.mul(w.patches(obj, 0.2, 0.4, seed=23.0), near, T("shine"))
    lk.col = col
    lk.rough = w.lerp(w.add(0.42, w.mul(g, 0.1)), 0.22, knees)
    lk.rough = w.lerp(lk.rough, 0.8, w.add(T("brown"), w.mul(T("fade"), 0.3)))
    lk.opacity = r
    lk.bump(w.mul(b, 0.0004, fd))


def sail(lk, kind):
    w = lk.w
    T = w.term
    obj = w.obj()
    r, g, b, fd = detail(lk, "Scrim", obj)
    # creases: straight fold lines (two families, along and up the sail, and a few across at 45 degrees), densest by
    # the luff and the foot where it is rolled and flogs
    def folds(stretch, seed, width):
        n = w.noise(obj, 0.05, seed, detail=0, stretch=stretch)
        return w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", n, 0.5)), width, 0.0)
    cr = w.mul(w.sat(w.add(folds((30.0, 1.0, 0.6), 31.0, 0.004), folds((0.6, 1.0, 30.0), 32.0, 0.004))),
               w.patches(obj, 0.25, w.mul(T("crease"), 0.6), seed=33.0, soft=0.4))   # more folded places with wear
    xs, ys, zs = w.sep(w.geo("Position"))
    edges = w.sat(w.add(w.m("SUBTRACT", 1.0, w.smooth(xs, -0.6, -0.2)), w.m("SUBTRACT", 1.0, w.smooth(zs, 0.9, 1.6)),
                        0.25))
    crease = w.mul(cr, T("crease"), edges, 0.8)
    haze = w.mul(T("haze"), w.add(0.6, w.mul(g, 0.4)))
    x, y, z = w.sep(w.geo("Position"))
    foot = w.m("SUBTRACT", 1.0, w.smooth(z, 0.6, 1.2))
    mil = w.patches(obj, 0.0035, w.mul(T("mildew"), 0.18), seed=34.0, soft=0.15, detail=1.0)
    milc = w.patches(obj, 0.08, w.mul(T("mildew"), 0.3, w.add(0.3, foot)), seed=35.0, soft=0.4)
    mild = w.mul(mil, milc, 0.75)
    grime = w.mul(T("grime"), foot, w.add(0.5, w.mul(w.blot(obj, 0.3, 3.0), 0.2)))
    # what scatters (the scrim, the haze, a crease's white, the specks); the rest goes through tinted
    thread = w.mul(r, w.add(0.55, w.mul(fd, 0.35)))
    lk.opacity = w.sat(w.add(0.03, thread, w.mul(haze, 0.28), w.mul(crease, 0.5), w.mul(mild, 0.7),
                             w.mul(grime, 0.3)))
    yellow = T("yellow")
    white = w.add(w.mul(haze, 0.28), w.mul(crease, 0.5))             # of what scatters, the share that is film, not thread
    col = w.mix(SCRIM_THREAD, (236, 236, 230), w.m("DIVIDE", white, w.add(white, thread, 0.02)))
    col = w.mix(col, FILM_YELLOW, w.mul(yellow, 0.6))
    col = w.mix(col, (64, 70, 56), mild)
    col = w.mix(col, GRIME, w.mul(grime, 0.35))
    tint = w.mix(FILM, FILM_YELLOW, w.mul(yellow, 0.6))
    tint = w.mix(tint, (200, 172, 120), w.mul(yellow, T("grime"), 0.2))
    lk.col = col
    lk.rough = w.val(0.45)
    lk.film = (tint, col)
    lk.albedo = w.mix(tint, col, lk.opacity)       # what the film looks like over white: its tint, and what it scatters
    lk.bump(w.add(w.mul(b, 0.00005, fd), w.mul(crease, 0.0004)))


def rope(lk, kind):
    w = lk.w
    T = w.term
    obj = w.obj()
    r, g, b, fd = detail(lk, "Braid", tube_uv(w), box=False, ch="N")
    braid = w.mul(w.m("SUBTRACT", r, 0.5), 2.0)             # the normal map's x tilt: the braid's strands
    base = LINE_ORANGE if kind == "line" else SHROUD_GREY
    col = w.scale(w.rgb(_lin(base)), w.add(1.0, w.mul(braid, 0.25, fd)))
    col = w.mix(col, LINE_FADED if kind == "line" else (178, 176, 170), w.mul(T("fade"), 0.8))
    fz = w.mul(T("fuzz"), w.add(0.6, w.mul(w.noise(tube_uv(w), 0.002, 42.0, detail=1), 0.8)))   # loose fibres
    col = w.mix(col, (232, 216, 198), w.mul(fz, 0.35))
    # a running line's grime is light (it cleans itself through the blocks); a standing shroud's goes dark grey-green
    dirt, dw = ((120, 124, 100), 0.4) if kind == "line" else ((92, 92, 80), 0.45)
    col = w.mix(col, dirt, w.mul(T("grime"), w.add(dw, w.mul(w.blot(obj, 0.1, 2.0), 0.25))))
    mil = w.patches(obj, 0.002, w.mul(T("mildew"), 0.15), seed=41.0, soft=0.1, detail=1.0)
    col = w.mix(col, (70, 82, 60), w.mul(mil, 0.6))
    lk.col = col
    lk.rough = w.add(0.45, w.mul(T("fuzz"), 0.4))
    lk.bump(w.mul(braid, 0.0003, fd))


def alloy(lk, kind):
    w = lk.w
    T = w.term
    obj = w.obj()
    r, g, b, fd = detail(lk, "Metal", obj)
    col = w.scale(w.rgb(_lin(ANODISE)), w.add(0.92, w.mul(r, 0.12, fd)))
    col = w.mix(col, (184, 184, 182), w.mul(T("fade"), 0.45))   # faded anodising: greyer and flat (round 4: paler read as new)
    col = w.mix(col, (96, 96, 96), w.mul(T("dull"), 0.65))        # neglected: a dull dark grey
    col = w.mix(col, GRIME, w.mul(T("grime"), w.add(0.25, w.mul(w.crevice(0.03, 0.2, 0.6), 0.5))))   # most in the joints
    rough = w.add(0.32, w.mul(g, 0.1, fd), w.mul(T("dull"), 0.3), w.mul(T("fade"), 0.25))
    hl = w.smooth(w.m("ABSOLUTE", w.m("SUBTRACT", w.noise(obj, 0.02, 57.0, detail=1, stretch=(4.0, 0.15, 0.4)), 0.5)),
                  0.01, 0.0)                                          # hairline scratches on the faces
    hl = w.mul(hl, w.patches(obj, 0.05, w.mul(T("hairlines"), 0.9), seed=58.0, soft=0.2), T("hairlines"))
    col = w.mix(col, (240, 240, 242), w.mul(hl, 0.75))
    edge = w.edge(0.005)
    scr = w.mul(edge, w.patches(obj, 0.01, w.mul(T("scratch"), 0.7), seed=51.0, soft=0.05))
    col = w.mix(col, (246, 246, 248), w.mul(scr, 0.95))
    rough = w.lerp(rough, 0.12, scr)
    cr = w.crevice(0.012, 0.2, 0.6)
    ox = w.mul(T("oxide"), w.sat(w.mul(cr, 2.5)))                   # white powder in the joints and round fasteners
    pit = w.val(0.0)            # (pitting specks read as glitter or granite to every reviewer: none)
    film = w.mul(T("oxide"), 0.12, w.add(0.7, w.mul(w.blot(obj, 0.15, 53.0, detail=1), 0.3)))   # a thin soft bloom
    ox = w.sat(w.add(ox, pit, film))
    col = w.mix(col, OXIDE, ox)
    lk.metal = w.m("SUBTRACT", 1.0, ox)
    lk.rough = w.lerp(rough, 0.9, ox)
    lk.col = col
    lk.bump(w.mul(w.add(w.mul(b, -0.5), w.mul(ox, 1.0)), 0.00005))


def grip(lk, kind):
    w = lk.w
    T = w.term
    obj = w.obj()
    r, g, b, fd = detail(lk, "Rubber", obj, ch="N")
    tex = w.mul(w.m("SUBTRACT", r, 0.5), 2.0)
    col = w.scale(w.rgb(_lin(RUBBER)), w.add(1.0, w.mul(tex, 0.15)))
    cr = w.crevice(0.004)
    col = w.mix(col, RUBBER_CHALK, w.mul(T("chalk"), w.add(0.35, w.mul(cr, 0.35), w.mul(w.blot(obj, 0.03, 1.0), 0.2))))
    col = w.mix(col, GRIME, w.mul(T("grime"), w.add(w.mul(cr, 0.9), 0.1)))
    vo = w.N.new("ShaderNodeTexVoronoi")                            # ozone crazing: a network of small cells
    vo.feature = "DISTANCE_TO_EDGE"
    vo.inputs["Scale"].default_value = 1.0 / 0.01
    w.L.new(obj, vo.inputs["Vector"])
    craze = w.smooth(vo.outputs["Distance"], 0.035, 0.0)
    crk = w.mul(craze, w.patches(obj, 0.015, w.mul(T("cracks"), 0.5), seed=61.0, soft=0.3))
    col = w.mix(col, (12, 12, 12), w.mul(crk, 0.6))
    shine = w.mul(T("shine"), w.m("SUBTRACT", 1.0, cr))
    lk.col = col
    lk.rough = w.lerp(w.add(0.72, w.mul(T("chalk"), 0.15)), 0.45, shine)
    lk.bump(w.add(w.mul(tex, 0.0002), w.mul(crk, T("cracks"), -0.0003)))


DRESS = {"carbon": carbon, "paint": paint, "mesh": mesh, "sail": sail, "rope": rope, "alloy": alloy, "grip": grip}


def dress(level="L0"):
    """Builds every carded material (her .blend's are viewport colours only) and sets them to a level."""
    import bpy
    idx = material_index()
    for k, (name, (surface, kind)) in enumerate(sorted(idx.items())):
        mt = bpy.data.materials[name]
        lk = Look(mt, surface, kind)
        DRESS[surface](lk, kind)
        lk.finish()
        mt.node_tree.nodes["mode:idcolour"].outputs[0].default_value = (*material_id_linear(k), 1.0)
        want = set(amounts(surface, kind, 6.0, 0.5))
        have = {n.name[5:] for n in mt.node_tree.nodes if n.name.startswith("wear:") and n.name != "wear:bump"}
        if want != have:
            raise SystemExit(f"{name}: wear terms {sorted(want)} but the nodes use {sorted(have)}")
    apply_level(level)


def apply_level(level, only=None):
    """Every material to a level ('L0'..'L4') or an (age, care); with `only` ('paint' or 'paint.foil'), just that
    surface or kind, the rest new (a ladder's sheet then ages only its own material: round 2's reviewers ordered
    sheets by the lines and the sail in the crops)."""
    import bpy
    age, care = (LEVELS[level]["age"], LEVELS[level]["care"]) if isinstance(level, str) else level
    new = (LEVELS["L0"]["age"], LEVELS["L0"]["care"])
    for name, (surface, kind) in material_index().items():
        mt = bpy.data.materials[name]
        mine = only is None or only in (surface, f"{surface}.{kind}")
        for term, v in amounts(surface, kind, *((age, care) if mine else new)).items():
            mt.node_tree.nodes["wear:" + term].outputs[0].default_value = v


def material_ids():
    """{material name: id code} as material_id draws them."""
    return {name: k + 1 for k, name in enumerate(sorted(material_index()))}


def albedo_mode(mode):
    """'albedo': every carded material its colour alone, unlit and opaque; 'id': its id colour; None: lit."""
    import bpy
    for name in material_index():
        nt = bpy.data.materials[name].node_tree
        nt.nodes["mode:emit"].outputs[0].default_value = 0.0 if mode is None else 1.0
        nt.nodes["mode:id"].outputs[0].default_value = 1.0 if mode == "id" else 0.0
