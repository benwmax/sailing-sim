"""Bluebonnet's sail materials in Blender (docs/jclass-6): each set sail's cream cotton with its cut drawn from its UVs,
and the materials of what goes with the sails (folded cloth, bags, cotton line).

    mats = sail_materials.make(rep["sails"], sails.SL["cloth"], hull_rgb)

The cloth's UVs are sails.py's (FSailCloth's convention): UV0 metres (x along the row from the luff, y up from the
foot), UV1 the share along the row and up the sail, UV2 (a, b): a metres along the row from the after edge (the
leech; on the spinnaker the clew's luff), b the cut's own measure: on the mainsail and the mitre-cut headsails metres
in from the leech's straight line, on the spinnaker metres from the centre seam. From them each material draws, with
no image textures:

  seams      one every cloth width less the overlap ('cloth_in' - 'seam_in' inches), the overlap's double layer a band
             'seam_in' wide with two rows of stitching: on the mainsail lines of constant b (the cloths parallel to the
             leech), on a headsail lines of constant min(b, y) (parallel to the leech above the mitre, to the foot
             below it) and the mitre itself where b = y, on the spinnaker lines of constant height and the centre seam
  tablings   the edges turned over: luff, foot and the after edge (a)
  patches    corner patches in two layers at the tack, the clew and the head (and the quadrilateral jib's upper clew),
             each cut straight across its corner, and the mainsail's reef bands
  emblem     the club's star on the mainsail (both faces, the hull's blue)

Each layer of cloth darkens the face a little in reflected light and a lot against the light: the shader mixes a
diffuse cotton (sheen, rough) with a translucent one whose colour falls with the layers, so a backlit sail shows its
seams and patches dark, as cotton does. The stitching fades out with the camera's distance.
"""
import math

import bpy

IN = 0.0254


def srgb(c):
    """sRGB 0-255 to linear."""
    out = []
    for v in c:
        v /= 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out)


class Nodes:
    """Small helpers for building a node tree."""

    def __init__(self, nt):
        self.N, self.L = nt.nodes, nt.links

    def link(self, a, b):
        self.L.new(a, b)

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

    def uv(self, name):
        u = self.N.new("ShaderNodeUVMap")
        u.uv_map = name
        s = self.N.new("ShaderNodeSeparateXYZ")
        self.L.new(u.outputs[0], s.inputs[0])
        return s.outputs[0], s.outputs[1]

    def length(self, a, b):
        return self.m("SQRT", self.m("ADD", self.m("MULTIPLY", a, a), self.m("MULTIPLY", b, b)))

    def bell(self, d, width):
        q = self.m("DIVIDE", d, width)
        return self.m("EXPONENT", self.m("MULTIPLY", self.m("MULTIPLY", q, q), -1.0))

    def lt(self, a, b):
        return self.m("LESS_THAN", a, b)

    def add(self, *xs):
        out = xs[0]
        for x in xs[1:]:
            out = self.m("ADD", out, x)
        return out

    def rgb_mix(self, fac, a, b):
        """a where fac = 0, b where fac = 1 (colours as sockets or tuples)."""
        n = self.N.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = "MIX"
        self.L.new(fac, n.inputs["Factor"])
        for sock, v in ((n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, tuple):
                sock.default_value = (*v, 1.0)
            else:
                self.L.new(v, sock)
        return n.outputs[2]

    def scale_rgb(self, col, fac):
        """A colour (tuple or socket) times a float socket."""
        n = self.N.new("ShaderNodeVectorMath")
        n.operation = "SCALE"
        if isinstance(col, tuple):
            n.inputs[0].default_value = col
        else:
            self.L.new(col, n.inputs[0])
        self.L.new(fac, n.inputs["Scale"])
        return n.outputs[0]


def star(G, x, y, cx, cy, radius):
    """1 inside a five-pointed star (a point straight up) centred at (cx, cy) in (x, y), its points `radius` out."""
    px = G.m("DIVIDE", G.m("SUBTRACT", x, cx), radius)
    py = G.m("DIVIDE", G.m("SUBTRACT", y, cy), radius)
    r = G.length(px, py)
    th = G.m("ARCTAN2", px, py)                                  # from straight up
    sector = 2.0 * math.pi / 5.0
    tm = G.m("ABSOLUTE", G.m("SUBTRACT", G.m("FLOORED_MODULO", G.m("ADD", th, sector / 2.0), sector), sector / 2.0))
    lx = G.m("MULTIPLY", r, G.m("COSINE", tm))
    ly = G.m("MULTIPLY", r, G.m("SINE", tm))
    ri = math.sin(math.radians(18.0)) / math.sin(math.radians(126.0))     # the inner vertices' radius
    bx, by = ri * math.cos(sector / 2.0) - 1.0, ri * math.sin(sector / 2.0)
    # (B - A) x (P - A) > 0: on the inner side of the edge from the point A = (1, 0) to the inner vertex B
    cross = G.m("SUBTRACT", G.m("MULTIPLY", ly, bx), G.m("MULTIPLY", G.m("SUBTRACT", lx, 1.0), by))
    return G.m("GREATER_THAN", cross, 0.0)


def cloth_material(name, info, cloth, rgb, emblem_rgb):
    """One set sail's cloth: info is sails.build's report for the sail, cloth its cloth's entry in sails_bluebonnet.json."""
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    G = Nodes(nt)
    kind = info["kind"]
    x0, y0 = G.uv("UV0")
    a, b = G.uv("UV2")
    pitch, w = (cloth["cloth_in"] - cloth["seam_in"]) * IN, cloth["seam_in"] * IN
    if kind == "main":
        q = b
    elif kind == "mitre":
        q = G.m("MINIMUM", b, y0)
    else:
        q = y0
    s = G.m("FLOORED_MODULO", q, pitch)
    band = G.lt(s, w)
    stitch = G.m("MAXIMUM", G.bell(G.m("SUBTRACT", s, 0.22 * w), 0.0012), G.bell(G.m("SUBTRACT", s, 0.78 * w), 0.0012))
    extra = None
    if kind == "mitre":                                          # the mitre: a seam where the two cuts meet
        d = G.m("ABSOLUTE", G.m("SUBTRACT", b, y0))
        extra = G.lt(d, 0.5 * w)
        stitch = G.m("MAXIMUM", stitch, G.m("MAXIMUM", G.bell(G.m("SUBTRACT", d, 0.28 * w), 0.0012),
                                              G.bell(G.m("SUBTRACT", d, 0.0), 0.0008)))
    elif kind == "spin":                                         # the centre seam
        extra = G.lt(b, 0.5 * w)
        stitch = G.m("MAXIMUM", stitch, G.bell(G.m("SUBTRACT", b, 0.28 * w), 0.0012))
    # tablings: the luff, the foot and the after edge (a: the distance along the row from it)
    tw = info.get("tabling_m", 0.06)
    after = a
    tab = G.m("MAXIMUM", G.m("MAXIMUM", G.lt(x0, tw), G.lt(y0, tw)), G.lt(after, tw + 0.02))
    # corner patches, two layers each, cut straight across the corner (their edge square to its bisector): the sum
    # of the distances in from the two edges that meet there under r1 and r2
    hy = info["head_y_m"]
    corners = [G.add(x0, y0), G.add(after, y0), G.add(x0, G.m("SUBTRACT", hy, y0))]
    if kind == "spin":
        corners = [G.add(x0, y0), G.add(a, y0), G.m("SUBTRACT", hy, y0)]
    if "upper_clew_y_m" in info:
        corners.append(G.add(after, G.m("ABSOLUTE", G.m("SUBTRACT", y0, info["upper_clew_y_m"]))))
    r1, r2 = (1.6, 0.95) if kind != "spin" else (1.2, 0.6)
    patch = None
    for r in corners:
        p = G.add(G.lt(r, r1), G.lt(r, r2))
        patch = p if patch is None else G.m("MAXIMUM", patch, p)
    layers = G.add(band, tab, patch)
    if extra is not None:
        layers = G.add(layers, extra)
    for h in info.get("reefs_m", []):
        layers = G.add(layers, G.lt(G.m("ABSOLUTE", G.m("SUBTRACT", y0, h)), 0.075))
    # the stitching fades out between 15 and 40 m from the camera
    dist = G.N.new("ShaderNodeCameraData").outputs["View Distance"]
    fade = G.m("DIVIDE", G.m("SUBTRACT", 40.0, dist), 25.0, clamp=True)
    st = G.m("MULTIPLY", stitch, fade)
    # a faint mottle in the cotton
    tex = G.N.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 1.6
    tex.inputs["Detail"].default_value = 3.0
    comb = G.N.new("ShaderNodeCombineXYZ")
    G.link(x0, comb.inputs[0])
    G.link(y0, comb.inputs[1])
    G.link(comb.outputs[0], tex.inputs["Vector"])
    mottle = G.m("ADD", 0.97, G.m("MULTIPLY", tex.outputs["Fac"], 0.06))
    lit = G.m("MULTIPLY", G.m("MULTIPLY", G.m("SUBTRACT", 1.0, G.m("MULTIPLY", layers, 0.045)),
                              G.m("SUBTRACT", 1.0, G.m("MULTIPLY", st, 0.35))), mottle)
    cream = srgb(rgb)
    base = G.scale_rgb(cream, lit)
    trans_fac = G.m("POWER", G.m("ADD", layers, 1.0), -1.4)
    t0 = {"main": 0.55, "mitre": 0.6, "spin": 0.85}[kind]
    tcol = G.scale_rgb(cream, G.m("MULTIPLY", trans_fac, t0))
    if info.get("emblem"):
        e = info["emblem"]
        inside = star(G, x0, y0, e["at"][0], e["at"][1], e["radius_m"])
        base = G.rgb_mix(inside, base, srgb(emblem_rgb))
        tcol = G.rgb_mix(inside, tcol, tuple(0.12 * c for c in srgb(emblem_rgb)))
    bsdf = G.N.new("ShaderNodeBsdfPrincipled")
    G.link(base, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    bsdf.inputs["Sheen Weight"].default_value = 0.35
    bsdf.inputs["Sheen Roughness"].default_value = 0.6
    trans = G.N.new("ShaderNodeBsdfTranslucent")
    G.link(tcol, trans.inputs["Color"])
    bump = G.N.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 1.0
    bump.inputs["Strength"].default_value = 1.0
    G.link(G.add(G.m("MULTIPLY", layers, 0.0004), G.m("MULTIPLY", st, -0.0002)), bump.inputs["Height"])
    G.link(bump.outputs[0], bsdf.inputs["Normal"])
    G.link(bump.outputs[0], trans.inputs["Normal"])
    mix = G.N.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = {"main": 0.25, "mitre": 0.28, "spin": 0.42}[kind]
    G.link(bsdf.outputs[0], mix.inputs[1])
    G.link(trans.outputs[0], mix.inputs[2])
    out = G.N.new("ShaderNodeOutputMaterial")
    G.link(mix.outputs[0], out.inputs["Surface"])
    return mt


def plain_material(name, rgb, rough, translucency=0.0, folds=0.0, weave=0.0):
    """Folded cloth (lumpy shading from object-space noise), canvas (a fine weave) or line."""
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    G = Nodes(nt)
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*srgb(rgb), 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = 0.3
    out = nt.nodes.get("Material Output")
    if folds or weave:
        tc = G.N.new("ShaderNodeTexCoord")
        tex = G.N.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 9.0 if folds else 600.0
        tex.inputs["Detail"].default_value = 4.0
        G.link(tc.outputs["Object"], tex.inputs["Vector"])
        bump = G.N.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = folds or weave
        bump.inputs["Distance"].default_value = 0.02 if folds else 0.0005
        G.link(tex.outputs["Fac"], bump.inputs["Height"])
        G.link(bump.outputs[0], b.inputs["Normal"])
    if translucency:
        tr = G.N.new("ShaderNodeBsdfTranslucent")
        tr.inputs["Color"].default_value = (*(0.5 * c for c in srgb(rgb)), 1.0)
        mix = G.N.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = translucency
        G.link(b.outputs[0], mix.inputs[1])
        G.link(tr.outputs[0], mix.inputs[2])
        G.link(mix.outputs[0], out.inputs["Surface"])
    return mt


def make(sails_rep, cloth, hull_rgb):
    """{slot name: material} for every slot sails.py uses that the hull's materials do not have."""
    mats = {}
    for name, info in sails_rep.items():
        rgb = cloth["spinnaker_colour"] if info["kind"] == "spin" else cloth["colour"]
        mats[f"Cloth{name}"] = cloth_material(f"Cloth{name}", info, cloth[info["cloth"]], rgb, hull_rgb)
    mats["SailHeap"] = plain_material("SailHeap", cloth["colour"], 0.82, translucency=0.12, folds=0.35)
    mats["SailBag"] = plain_material("SailBag", cloth["bag_colour"], 0.88, weave=0.4)
    mats["SailLine"] = plain_material("SailLine", [226, 218, 196], 0.8)
    return mats
