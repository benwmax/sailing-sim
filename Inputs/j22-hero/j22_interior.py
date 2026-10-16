"""The J/22's cabin below decks: what you see through the companionway, the portlights and the fore hatch.

The J/22 is a day racer with a shelter cabin, not a cruiser (magazine reviews: a V-berth over the forward buoyancy
compartment, a bench either side of the keel, optional quarter berths, a cream gelcoat liner, two low fixed
portlights, no galley, head or wiring, storage only aft under the cockpit seats). Built here:

  - the trunk and deck opened up inside (the trunk becomes a shell, the deck is cut away under it), real portlight
    openings with smoked acrylic in place of the painted windows, a clear fore hatch;
  - a moulded cream liner: cabin sole, the two benches with their fronts, the V-berth platform and its face with an
    inspection port onto the buoyancy compartment, the aft cabin wall (companionway and the two openings into the
    under-seat lockers), the hull's inside skin;
  - structure you can see on a real boat: keel bolts with nuts and backing plates in a shallow sump under a lift-out
    sole hatch, a mast compression post, glassed-in chainplate knees with their bolts;
  - what a club boat carries (the style decides): V-berth cushions, a sail bag, spare foam PFDs, a paddle, a bucket,
    a fire extinguisher on its bracket, a Danforth anchor with its rode, the drop board stowed on a bench.

Dimensions the published numbers don't give are marked GUESS (sole height, bench height, the post, the knees).
Everything is in the Interior collection, exported as SM_J22H_Interior (same pivot as the hull) so the game can draw
it only when the camera is close or in the cockpit.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import j22_materials as M
from j22_geom import apply_mods, box, cyl, mesh_obj, tube

SOLE_Z = -0.10            # GUESS: cabin sole above the design waterline (about 1.05 m under the trunk's headliner)
BENCH_Z = 0.26            # GUESS: bench tops
BENCH_IN = 0.28           # bench fronts, half-width
VBERTH_Z = 0.30           # GUESS: V-berth top
VBERTH_AFT = 1.12         # V-berth face
LINER_T = 0.012
WIN_FWD = 1.10           # portlights' forward end at their foot, clear of the trunk's rounded nose (j22_materials.py too)
SKIN = 0.016              # the liner stands this far inside the hull's outer surface (12 mm shell + a gap)


# ------------------------------------------------------------------ materials

def liner(st, name="InteriorLiner", nonskid=False):
    """Cream gelcoat liner: orange peel, dull mould-release patches, dirt that settles low and in corners, scuffs on
    the bench edges, brown water tracks under the chainplates and the hatch (the J/22's known leaks), mildew dots on
    a neglected boat."""
    wear, care = st["wear"], st["care"]
    W = st["seed"] * 0.293 % 100
    m, nt, bsdf, _ = M._new(name)
    vec, tc = M._coords(nt)
    x, y, z = M._xyz(nt, vec)
    base = M._rgb("#E6DCC0")
    var = M._noise4(nt, vec, 2.5, W, 4, 0.5)
    c = M._mix(nt, M._math(nt, "MULTIPLY", var, 0.18), base, M._rgb("#D2C6A4"))
    low = M._n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    low.inputs[1].default_value, low.inputs[2].default_value = 0.10, -0.12
    M._l(nt, z, low.inputs[0])
    corner = M._math(nt, "SUBTRACT", 1.0, M._ao(nt, 0.08))
    dirt = M._math(nt, "ADD", M._math(nt, "MULTIPLY", low.outputs[0], 0.5), M._math(nt, "MULTIPLY", corner, 1.4), True)
    dirt = M._math(nt, "MULTIPLY", dirt, M._math(nt, "ADD", 0.4, M._noise4(nt, vec, 5.0, W + 1, 5, 0.6)))
    k = wear * (1.15 - care)
    c = M._mix(nt, M._math(nt, "MULTIPLY", dirt, 0.9 * k, True), c, M._rgb("#8A7C5E"))
    # water tracks: vertical streaks hanging under the chainplates (x ~0.8-1.0, CHAINPLATE_X) and the fore hatch (x ~1.2-1.6)
    svec, _ = M._coords(nt, scale=(40, 40, 1.5))
    streak = M._math(nt, "MULTIPLY", M._math(nt, "SUBTRACT", M._noise4(nt, svec, 1.0, W + 2, 3, 0.4), 0.55, True), 3.0, True)
    near = M._math(nt, "ADD", M._band(nt, x, 0.70, 1.05, 0.08), M._band(nt, x, 1.20, 1.62, 0.06))
    track = M._math(nt, "MULTIPLY", M._math(nt, "MULTIPLY", streak, near), M._band(nt, z, 0.05, 0.75, 0.1))
    c = M._mix(nt, M._math(nt, "MULTIPLY", track, 0.55 * wear, True), c, M._rgb("#9A7A4E"))
    if wear > 0.5:
        vor = M._n(nt, "ShaderNodeTexVoronoi", voronoi_dimensions="4D")
        vor.inputs["Scale"].default_value = 140.0
        vor.inputs["W"].default_value = W + 3
        M._l(nt, vec, vor.inputs["Vector"])
        dots = M._math(nt, "MULTIPLY", M._math(nt, "LESS_THAN", vor.outputs["Distance"], 0.12), corner)
        c = M._mix(nt, M._math(nt, "MULTIPLY", dots, (wear - 0.5) * 1.6, True), c, M._rgb("#3E4032"))
    scuff = M._math(nt, "MULTIPLY", M._math(nt, "GREATER_THAN", M._edges(nt), 0.55),
                    M._math(nt, "GREATER_THAN", M._noise4(nt, vec, 30, W + 4, 5, 0.7), 0.6 - 0.1 * wear))
    c = M._mix(nt, M._math(nt, "MULTIPLY", scuff, 0.6), c, M._rgb("#A39678"))
    height = M._math(nt, "ADD", M._math(nt, "MULTIPLY", M._noise(nt, vec, 260.0, 2, 0.5), 0.5), M._math(nt, "MULTIPLY", scuff, -0.3))
    rough = M._math(nt, "ADD", 0.32, M._math(nt, "MULTIPLY", M._noise4(nt, vec, 1.8, W + 5, 3, 0.5), 0.22))
    if nonskid:
        nx, ny, nz = M._xyz(nt, tc.outputs["Normal"])
        flat = M._n(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        flat.inputs[1].default_value, flat.inputs[2].default_value = 0.84, 0.93
        M._l(nt, nz, flat.inputs[0])
        dots = M._n(nt, "ShaderNodeTexVoronoi")
        dots.inputs["Scale"].default_value = 260.0
        M._l(nt, vec, dots.inputs["Vector"])
        pattern = M._math(nt, "MULTIPLY", M._math(nt, "LESS_THAN", dots.outputs["Distance"], 0.32), flat.outputs[0])
        c = M._mix(nt, M._math(nt, "MULTIPLY", pattern, 0.15), c, M._rgb("#8C8068"))
        height = M._math(nt, "ADD", height, pattern)
        rough = M._math(nt, "ADD", rough, M._math(nt, "MULTIPLY", flat.outputs[0], 0.25))
    M._l(nt, c, bsdf.inputs["Base Color"])
    M._l(nt, rough, bsdf.inputs["Roughness"])
    M._bump(nt, bsdf, height, 0.25, 0.0015)
    m.diffuse_color = base
    m["detail"] = "nonskid_normal" if nonskid else "gelcoat"
    return m


def bilge(st):
    m, nt, bsdf, _ = M._new("Bilge")
    W = st["seed"] * 0.41 % 100
    vec, _ = M._coords(nt)
    n = M._noise4(nt, vec, 9.0, W, 6, 0.65)
    c = M._mix(nt, n, M._rgb("#7C7A68"), M._rgb("#3F3D30"))
    M._l(nt, c, bsdf.inputs["Base Color"])
    M._l(nt, M._math(nt, "ADD", 0.15, M._math(nt, "MULTIPLY", n, 0.5)), bsdf.inputs["Roughness"])
    m.diffuse_color = M._rgb("#5E5C4C")
    return m


def fabric(st, name, hexcol, weave=380.0, fade=0.3):
    """Canvas or acrylic upholstery: a plain weave, sun-faded tops, darker piping and seams, stains."""
    m, nt, bsdf, _ = M._new(name)
    W = (st["seed"] + len(name)) * 0.17 % 100
    vec, _ = M._coords(nt)
    w1 = M._n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
    w1.inputs["Scale"].default_value = weave
    w2 = M._n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Y", wave_profile="SIN")
    w2.inputs["Scale"].default_value = weave
    for w in (w1, w2):
        M._l(nt, vec, w.inputs["Vector"])
    cloth = M._math(nt, "MULTIPLY", w1.outputs["Fac"], w2.outputs["Fac"])
    c = M._mix(nt, M._math(nt, "MULTIPLY", cloth, 0.25), M._rgb(hexcol), M._rgb("#0E0E12"))
    c = M._mix(nt, M._math(nt, "MULTIPLY", M._noise4(nt, vec, 3, W, 4, 0.5), fade), c, M._rgb("#9BA2AA"))
    stains = M._math(nt, "GREATER_THAN", M._noise4(nt, vec, 6, W + 1, 6, 0.7), 0.70 - 0.08 * st["wear"])
    c = M._mix(nt, M._math(nt, "MULTIPLY", stains, 0.35), c, M._rgb("#4A4232"))
    M._l(nt, c, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Sheen Weight"].default_value = 0.5
    M._bump(nt, bsdf, cloth, 0.3, 0.0006)
    m.diffuse_color = M._rgb(hexcol)
    return m


def smoked_acrylic(name):
    m, nt, bsdf, _ = M._new(name)
    bsdf.inputs["Base Color"].default_value = M._rgb("#55493E")   # dark bronze tint: near black from outside by day (IMG_9224)
    bsdf.inputs["Roughness"].default_value = 0.03
    bsdf.inputs["Transmission Weight"].default_value = 0.9
    bsdf.inputs["IOR"].default_value = 1.49
    m.diffuse_color = (*M._rgb("#2F2B26")[:3], 0.4)
    m["translucent"] = 0.35
    return m


def galvanised(name):
    m, nt, bsdf, _ = M._new(name)
    vec, _ = M._coords(nt)
    vor = M._n(nt, "ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 90.0
    M._l(nt, vec, vor.inputs["Vector"])
    c = M._mix(nt, vor.outputs["Distance"], M._rgb("#9EA2A3"), M._rgb("#6C7072"))
    rust = M._math(nt, "GREATER_THAN", M._noise(nt, vec, 25, 5, 0.7), 0.66)
    c = M._mix(nt, rust, c, M._rgb("#6B3F22"))
    M._l(nt, c, bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.85
    M._l(nt, M._math(nt, "ADD", 0.35, M._math(nt, "MULTIPLY", rust, 0.5)), bsdf.inputs["Roughness"])
    m.diffuse_color = M._rgb("#8E9294")
    return m


def materials(st):
    cw = st.get("interior", {})
    return {
        "InteriorLiner": liner(st),
        "InteriorSole": liner(st, "InteriorSole", nonskid=True),
        "Bilge": bilge(st),
        "Cushion": fabric(st, "Cushion", cw.get("cushion_hex", "#1F2D4A"), fade=0.25 + 0.4 * st["wear"]),
        "SailBag": fabric(st, "SailBag", cw.get("sailbag_hex", "#2457A6"), weave=700.0, fade=0.3),
        "PFDNylon": fabric(st, "PFDNylon", "#1E4FB0", weave=900.0, fade=0.35),
        "Webbing": fabric(st, "Webbing", "#77797C", weave=600.0, fade=0.1),
        "PortlightAcrylic": smoked_acrylic("PortlightAcrylic"),
        "Galvanised": galvanised("Galvanised"),
        "ExtinguisherRed": M.simple("ExtinguisherRed", "#B3201B", 0.3, coat=0.8),
        "BucketWhite": M.simple("BucketWhite", "#E8E6DF", 0.45),
        "PaddleBlack": M.simple("PaddleBlack", "#1C1C1C", 0.5),
        "KeelBoltSteel": M.simple("KeelBoltSteel", "#7E7A72", 0.55, metal=0.9),
        "WaterBilge": smoked_water("WaterBilge"),
    }


def smoked_water(name):
    m, nt, bsdf, _ = M._new(name)
    bsdf.inputs["Base Color"].default_value = M._rgb("#4B4A36")
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["Transmission Weight"].default_value = 0.7
    bsdf.inputs["IOR"].default_value = 1.33
    m.diffuse_color = M._rgb("#4B4A36")
    return m


# ------------------------------------------------------------------ geometry helpers

def hull_y(H, x, z):
    """Half-breadth of the hull's inside at station x and height z (bisection on the girth fraction)."""
    if z <= H.keel_z(x):
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(32):
        mid = (lo + hi) / 2
        if H.section(x, mid)[1] < z:
            lo = mid
        else:
            hi = mid
    y, _ = H.section(x, (lo + hi) / 2)
    return max(y - SKIN, 0.0)


def bool_op(ob, cutter, op="DIFFERENCE", keep=False, tolerant=True):
    m = ob.modifiers.new("bool", "BOOLEAN")
    m.operation, m.object, m.solver = op, cutter, "EXACT"
    m.material_mode = "TRANSFER"
    # the deck and cockpit shells are open at the cockpit: without hole tolerance they gain the cutter's faces. The
    # cabin trunk is a closed solid and takes the plain exact solver
    m.use_hole_tolerant = tolerant
    m.use_self = not tolerant         # the trunk's nose sections fold over themselves where it narrows to the stem
    apply_mods(ob)
    if not keep:
        bpy.data.objects.remove(cutter, do_unlink=True)


def loft(name, rings, mat, cap=True, smooth=True, closed=False):
    """Quads between equal-length rings of points. closed: each ring is a closed loop (last point joins the first), so
    with cap the result is a closed solid; boolean cutters must be (an open bottom makes the exact solver leave slivers)."""
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    for a, b in zip(vr[:-1], vr[1:]):
        for j in range(len(a) - (0 if closed else 1)):
            k = (j + 1) % len(a)
            bm.faces.new((a[j], a[k], b[k], b[j]))
    if cap:
        bm.faces.new(vr[0])
        bm.faces.new(list(reversed(vr[-1])))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat, smooth_shade=smooth)


def slab(name, outline, axis, at, thick, mat):
    """An extruded flat panel: outline in the plane normal to axis ('x' -> (y, z) pairs, 'z' -> (x, y) pairs)."""
    def p3(u, v, w):
        return (w, u, v) if axis == "x" else (u, v, w)
    bm = bmesh.new()
    a = [bm.verts.new(p3(u, v, at)) for u, v in outline]
    b = [bm.verts.new(p3(u, v, at + thick)) for u, v in outline]
    k = len(outline)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat, smooth_shade=False)


def rounded_rect(cx, cy, w, h, r, n=6):
    pts = []
    for (qx, qy, a0) in ((cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90),
                         (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((qx + r * math.cos(a), qy + r * math.sin(a)))
    return pts


def soft_box(name, c, s, mat, r=0.03, subdiv=2, squash=None):
    """A pillowy box (cushion, sail bag, PFD): bevelled cube, subdivided, optionally sagging under its own weight."""
    ob = box(name, c[0] - s[0] / 2, c[0] + s[0] / 2, c[1] - s[1] / 2, c[1] + s[1] / 2, c[2] - s[2] / 2, c[2] + s[2] / 2, mat,
             bev=min(r, min(s) * 0.45), segs=3)
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = subdiv
    apply_mods(ob)
    if squash:
        for v in ob.data.vertices:
            dz = v.co.z - c[2]
            v.co.z -= squash * max(0.0, 1 - ((v.co.x - c[0]) / (s[0] / 2)) ** 2) * (0.5 + dz / s[2])
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


# ------------------------------------------------------------------ the cabin

def open_up(H, cabin, deck, cockpit, mats):
    """Hollow the trunk, cut the deck under it, cut the portlights, the fore hatch and the companionway through the
    cockpit's forward bulkhead. Returns the new acrylic panes."""
    n = 64
    t0 = 0.03 / (H.CABIN_FWD - H.CABIN_AFT)
    # the top stays thicker than the sides: the deck hardware's fastenings sit in it (a cored top, about 6 cm here)
    rings = [H.cabin_ring(t0 + (0.965 - t0) * i / n, inset=0.028, z_floor=0.36, top_extra=0.03) for i in range(n + 1)]
    cut = loft("cabin_cut", rings, mats["InteriorLiner"], closed=True)
    bool_op(cabin, cut, keep=True, tolerant=False)
    bool_op(deck, cut)
    # companionway through the bridge-deck bulkhead, the deck's aft edge and what is left of the trunk's aft wall
    for ob in (cockpit, deck, cabin):
        bool_op(ob, box("comp_cut", H.CABIN_AFT - 0.05, H.CABIN_AFT + 0.10, -0.235, 0.235, H.SEAT_Z, 1.3), tolerant=ob is not cabin)
    # portlights: the long low windows of the dock photo (IMG_9224), slanted at the forward end
    out = []
    zb, zt = 0.745, 0.835
    win = []
    for (x, z) in ((-0.30, zb), (WIN_FWD, zb), (WIN_FWD - (zt - zb) * 3.0, zt), (-0.30, zt)):
        win.append((x, z))
    win = _fillet_closed(win, 0.025)
    cutter = _prism_y("win_cut", win, -1.6, 1.6)
    bool_op(cabin, cutter, tolerant=False)
    for side in (1, -1):
        pts = []
        for (x, z) in win:
            t = (x - H.CABIN_AFT) / (H.CABIN_FWD - H.CABIN_AFT)
            ring = H.cabin_ring(t)
            (_, y_lo, z_lo), (_, y_hi, z_hi) = ring[-2], ring[-3]       # outside of the wall: deck edge and shoulder
            f = (z - z_lo) / max(z_hi - z_lo, 1e-6)
            yw = abs(y_lo + (y_hi - y_lo) * f) - 0.012
            pts.append((x, side * yw, z))
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in pts]
        bm.faces.new(vs if side > 0 else list(reversed(vs)))
        pane = mesh_obj(f"Portlight_{side}", bm, mats["PortlightAcrylic"], smooth_shade=False)
        sol = pane.modifiers.new("solid", "SOLIDIFY")
        sol.thickness = 0.006
        apply_mods(pane)
        out.append(pane)
    # fore hatch: open the trunk top under the acrylic so daylight falls on the V-berth
    hx0, hx1 = H.FWD_HATCH
    hxc = 0.5 * (hx0 + hx1)
    zt_h = H.deck_z(hxc, 0) + H.CABIN_H0 - 0.06 * (hxc - H.CABIN_AFT) / (H.CABIN_FWD - H.CABIN_AFT)
    bool_op(cabin, box("hatch_cut", hx0 + 0.03, hx1 - 0.03, -0.23, 0.23, zt_h - 0.2, zt_h + 0.1), tolerant=False)
    if not cabin.data.polygons:
        raise RuntimeError("J22H interior: the trunk booleans left no faces")
    return out


def _prism_y(name, outline_xz, y0, y1):
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for x, z in outline_xz]
    b = [bm.verts.new((x, y1, z)) for x, z in outline_xz]
    k = len(outline_xz)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, None, smooth_shade=False)


def _fillet_closed(poly, r, n=4):
    out = []
    k = len(poly)
    for i in range(k):
        a, b, c = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % k])
        u, w = (a - b).normalized(), (c - b).normalized()
        rr = min(r, (a - b).length * 0.45, (c - b).length * 0.45)
        p0, p1 = b + u * rr, b + w * rr
        for j in range(n + 1):
            t = j / n
            q = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p1
            out.append((q.x, q.y))
    return out


def split_hull_skin(hull, mat):
    """The hull shell's inside faces (the solidify's inner skin) become their own object in the liner material."""
    bm = bmesh.new()
    bm.from_mesh(hull.data)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    inner = []
    for f in bm.faces:
        c = f.calc_center_median()
        # inside faces point toward the centreline (or up, at the bottom)
        if c.z > -0.25 and f.normal.y * c.y < -1e-4 and abs(c.y) > 0.05 or (abs(c.y) <= 0.05 and f.normal.z > 0.5 and c.z < 0.3):
            inner.append(f)
    bm2 = bmesh.new()
    vmap = {}
    for f in inner:
        vs = []
        for v in f.verts:
            if v.index not in vmap:
                vmap[v.index] = bm2.verts.new(v.co)
            vs.append(vmap[v.index])
        try:
            bm2.faces.new(vs)
        except ValueError:
            pass
    bmesh.ops.delete(bm, geom=inner, context="FACES_ONLY")
    bm.to_mesh(hull.data)
    bm.free()
    return mesh_obj("HullInner", bm2, mat)


def build(H, cabin, deck, cockpit, hull):
    st = H.STYLE
    mats = materials(st)
    H.MAT.update(mats)
    objs = open_up(H, cabin, deck, cockpit, mats)
    objs.append(split_hull_skin(hull, mats["InteriorLiner"]))
    xa = H.CABIN_AFT + 0.04
    rng = random.Random(st["seed"] + 77)

    # cabin sole between the benches, aft wall to the V-berth face; a lift-out hatch over the keel bolts
    sole_rings = []
    for i in range(25):
        x = xa + (VBERTH_AFT - xa) * i / 24
        w = min(BENCH_IN, hull_y(H, x, SOLE_Z))
        sole_rings.append([(x, -w, SOLE_Z - 0.03), (x, -w, SOLE_Z), (x, w, SOLE_Z), (x, w, SOLE_Z - 0.03)])
    sole = loft("CabinSole", sole_rings, mats["InteriorSole"], closed=True)
    bool_op(sole, box("sump_cut", 0.38, 0.98, -0.16, 0.16, SOLE_Z - 0.2, SOLE_Z + 0.1))
    objs.append(sole)
    hatch = box("SoleHatch", 0.385, 0.975, -0.155, 0.155, SOLE_Z + 0.004, SOLE_Z + 0.018, mats["InteriorSole"], bev=0.004)
    hatch.location = (0.0, 0.10, 0.0)        # lifted aside on its edge would hide the bolts; slid to port, part open
    hatch.rotation_euler = (math.radians(-4), 0, 0)
    objs.append(hatch)
    objs.append(cyl("SoleHatchRing", (0.50, 0.10, SOLE_Z + 0.018), (0.50, 0.10, SOLE_Z + 0.024), 0.018, H.MAT["Stainless"], 20))
    # the sump: a shallow liner tub over the keel root with the bolts, washers and backing plates, a little bilge water
    sump = []
    for i in range(13):
        x = 0.38 + 0.60 * i / 12
        zk = H.keel_z(x) + 0.03
        sump.append([(x, -0.16, SOLE_Z), (x, -0.13, zk + 0.02), (x, 0.13, zk + 0.02), (x, 0.16, SOLE_Z)])
    tub = loft("Sump", sump, mats["Bilge"], cap=False)
    s = tub.modifiers.new("solid", "SOLIDIFY")
    s.thickness = 0.01
    apply_mods(tub)
    objs.append(tub)
    zsump = max(H.keel_z(x) for x in (0.4, 0.7, 0.95)) + 0.05
    objs.append(box("BilgeWater", 0.42, 0.94, -0.12, 0.12, zsump - 0.005, zsump + 0.012, mats["WaterBilge"]))
    for k, x in enumerate((0.48, 0.66, 0.84)):
        for sy in (-0.06, 0.06):
            zb = H.keel_z(x) + 0.05
            objs.append(box(f"KeelPlate_{k}_{sy}", x - 0.045, x + 0.045, sy - 0.035, sy + 0.035, zb, zb + 0.008, mats["KeelBoltSteel"], bev=0.002))
            objs.append(cyl(f"KeelNut_{k}_{sy}", (x, sy, zb + 0.008), (x, sy, zb + 0.032), 0.016, mats["KeelBoltSteel"], 6))
            objs.append(cyl(f"KeelStud_{k}_{sy}", (x, sy, zb + 0.03), (x, sy, zb + 0.05), 0.0095, mats["KeelBoltSteel"], 12))

    # benches: top, front and an end cheek at each end
    for side in (1, -1):
        rings = []
        for i in range(25):
            x = xa + (VBERTH_AFT - 0.005 - xa) * i / 24
            yo = hull_y(H, x, BENCH_Z)
            ys = hull_y(H, x, SOLE_Z + 0.02)
            ring = [(x, BENCH_IN, SOLE_Z), (x, BENCH_IN, BENCH_Z - 0.02), (x, BENCH_IN + 0.02, BENCH_Z),
                    (x, yo, BENCH_Z), (x, yo, BENCH_Z - LINER_T), (x, BENCH_IN + LINER_T, BENCH_Z - LINER_T),
                    (x, BENCH_IN + LINER_T, SOLE_Z), (x, max(ys, BENCH_IN + 0.02), SOLE_Z)]
            rings.append([(px, side * py, pz) for px, py, pz in ring])
        bench = loft(f"Bench_{side}", rings, mats["InteriorLiner"], cap=True)
        objs.append(bench)
        # locker openings in the bench fronts (dark: the hull's inside)
        objs.append(box(f"BenchVoid_{side}", 0.05, 0.62, side * (BENCH_IN - 0.002) - 0.001, side * (BENCH_IN - 0.002) + 0.001,
                        SOLE_Z + 0.07, BENCH_Z - 0.07, mats["Bilge"]))
        # chainplate knee: a glassed-in plywood knee on the hull side under the chainplates, with the bolts through it
        xk = H.CHAINPLATE_X
        yk = hull_y(H, xk, 0.45)
        knee = box(f"ChainKnee_{side}", xk - 0.012, xk + 0.012, side * (yk - 0.10), side * yk, BENCH_Z, H.sheer_z(xk) - 0.03,
                   mats["InteriorLiner"], bev=0.008)
        objs.append(knee)
        for k in range(3):
            zz = H.sheer_z(xk) - 0.10 - 0.08 * k
            objs.append(cyl(f"KneeBolt_{side}_{k}", (xk + 0.012, side * (yk - 0.04), zz), (xk + 0.022, side * (yk - 0.04), zz),
                            0.009, H.MAT["Stainless"], 6))
    # V-berth: platform following the hull, its face with an inspection port onto the buoyancy compartment
    x_end = VBERTH_AFT
    while x_end < H.BOW - 0.2 and hull_y(H, x_end, VBERTH_Z) > 0.12:
        x_end += 0.02
    rings = []
    for i in range(31):
        x = VBERTH_AFT + (x_end - VBERTH_AFT) * i / 30
        w = hull_y(H, x, VBERTH_Z)
        rings.append([(x, -w, VBERTH_Z - LINER_T), (x, -w, VBERTH_Z), (x, w, VBERTH_Z), (x, w, VBERTH_Z - LINER_T)])
    objs.append(loft("VBerth", rings, mats["InteriorLiner"]))
    face = []
    for k in range(13):
        z = SOLE_Z + (VBERTH_Z - SOLE_Z) * k / 12
        face.append((hull_y(H, VBERTH_AFT, z), z))
    outline = [(-y, z) for y, z in reversed(face)] + [(y, z) for y, z in face]
    vf = slab("VBerthFace", outline, "x", VBERTH_AFT - LINER_T, LINER_T, mats["InteriorLiner"])
    objs.append(vf)
    objs.append(cyl("VBerthPort", (VBERTH_AFT - LINER_T - 0.004, 0, 0.10), (VBERTH_AFT - LINER_T + 0.001, 0, 0.10), 0.075, H.MAT["WhitePlastic"], 32))
    objs.append(cyl("VBerthPortLid", (VBERTH_AFT - LINER_T - 0.010, 0, 0.10), (VBERTH_AFT - LINER_T - 0.004, 0, 0.10), 0.062, H.MAT["WhitePlastic"], 32))
    # aft cabin wall (the bridge deck's forward face) from the hull up to the deck, companionway and locker openings
    xw = H.CABIN_AFT + 0.03
    side_pts = []
    for k in range(17):
        f = k / 16
        y, z = H.section(xw, f)
        if z > SOLE_Z - 0.03:
            side_pts.append((max(y - SKIN, 0.0), z))
    top = H.deck_z(xw, 0) - 0.04
    side_pts = [(y, min(z, top)) for y, z in side_pts]
    outline = [(-y, z) for y, z in reversed(side_pts)] + [(y, z) for y, z in side_pts]
    wall = slab("AftCabinWall", outline, "x", xw, LINER_T, mats["InteriorLiner"])
    bool_op(wall, box("wall_comp", xw - 0.05, xw + 0.05, -0.235, 0.235, H.SEAT_Z, 1.3))
    for side in (1, -1):
        bool_op(wall, box(f"wall_lock_{side}", xw - 0.05, xw + 0.05, side * 0.42 - 0.17, side * 0.42 + 0.17, BENCH_Z + 0.03, H.SEAT_Z - 0.04))
    objs.append(wall)
    # companionway step: a teak box on the sole
    objs.append(box("CompStep", xa + 0.02, xa + 0.26, -0.20, 0.20, SOLE_Z, SOLE_Z + 0.24, H.MAT["TeakWeathered"], bev=0.01))
    # mast compression post: aluminium tube from the sole to the headliner under the step (GUESS)
    zt = H.deck_z(H.MAST_X, 0) + H.CABIN_H0 - 0.06 * (H.MAST_X - H.CABIN_AFT) / (H.CABIN_FWD - H.CABIN_AFT) - 0.028
    objs.append(cyl("CompressionPost", (H.MAST_X, 0, SOLE_Z), (H.MAST_X, 0, zt), 0.032, H.MAT["Aluminium"], 24))
    objs.append(box("PostFoot", H.MAST_X - 0.06, H.MAST_X + 0.06, -0.06, 0.06, SOLE_Z, SOLE_Z + 0.01, H.MAT["CastAlu"], bev=0.003))
    objs.append(box("PostHead", H.MAST_X - 0.07, H.MAST_X + 0.07, -0.07, 0.07, zt - 0.01, zt, H.MAT["CastAlu"], bev=0.003))

    # ---------------------------------------------------------- what's aboard (style.interior)
    ins = st.get("interior", {})
    if ins.get("cushions", True):
        # two V-berth cushions split down the middle, piped edges, sagging a little
        for side in (1, -1):
            xs = [VBERTH_AFT + 0.02 + (x_end - 0.08 - VBERTH_AFT) * i / 12 for i in range(13)]
            pts = [(x, side * 0.01) for x in xs] + [(x, side * (hull_y(H, x, VBERTH_Z + 0.04) - 0.02)) for x in reversed(xs)]
            cu = slab(f"VCushion_{side}", pts, "z", VBERTH_Z, 0.075, mats["Cushion"])
            if side < 0:
                for p in cu.data.polygons:
                    p.flip()
            bev = cu.modifiers.new("bev", "BEVEL")
            bev.width, bev.segments = 0.02, 3
            sub = cu.modifiers.new("sub", "SUBSURF")
            sub.levels = 1
            apply_mods(cu)
            for p in cu.data.polygons:
                p.use_smooth = True
            objs.append(cu)
        if ins.get("bench_cushions", False):
            for side in (1, -1):
                objs.append(soft_box(f"BCushion_{side}", (0.30, side * (BENCH_IN + 0.24), BENCH_Z + 0.04), (1.40, 0.44, 0.07), mats["Cushion"]))
    if ins.get("sail_bag", True):
        objs.append(soft_box("SailBag", (1.75, -0.18, VBERTH_Z + 0.075 + 0.11), (0.95, 0.42, 0.24), mats["SailBag"], r=0.1, squash=0.03))
        objs.append(tube("SailBagTie", [(2.20, -0.18, VBERTH_Z + 0.30), (2.24, -0.10, VBERTH_Z + 0.27), (2.27, -0.05, VBERTH_Z + 0.20)],
                         0.004, H.MAT["RopeHalyard"], smooth_path=True))
    for k in range(ins.get("spare_pfds", 2)):
        x = 0.05 + 0.42 * k
        p = soft_box(f"SparePFD_{k}", (x, -(BENCH_IN + 0.22), BENCH_Z + 0.045), (0.38, 0.32, 0.07), mats["PFDNylon"], r=0.03)
        p.rotation_euler = (0, 0, math.radians(rng.uniform(-12, 12)))
        objs.append(p)
        for j in range(3):
            objs.append(box(f"PFDStrap_{k}_{j}", x - 0.19, x + 0.19, -(BENCH_IN + 0.22) - 0.10 + 0.1 * j - 0.012,
                            -(BENCH_IN + 0.22) - 0.10 + 0.1 * j + 0.012, BENCH_Z + 0.08, BENCH_Z + 0.085, mats["Webbing"]))
    if ins.get("paddle", True):
        objs.append(cyl("PaddleShaft", (-0.35, BENCH_IN + 0.06, BENCH_Z + 0.02), (0.75, BENCH_IN + 0.08, BENCH_Z + 0.02), 0.014, H.MAT["Aluminium"], 12))
        bl = box("PaddleBlade", 0.75, 1.05, BENCH_IN + 0.0, BENCH_IN + 0.17, BENCH_Z + 0.012, BENCH_Z + 0.026, mats["PaddleBlack"], bev=0.01)
        objs.append(bl)
        objs.append(box("PaddleGrip", -0.43, -0.33, BENCH_IN + 0.03, BENCH_IN + 0.09, BENCH_Z + 0.01, BENCH_Z + 0.035, mats["PaddleBlack"], bev=0.008))
    if ins.get("bucket", True):
        bk = cyl("Bucket", (-0.12, 0.12, SOLE_Z), (-0.12, 0.12, SOLE_Z + 0.26), 0.12, mats["BucketWhite"], 32, r1=0.145, cap=True)
        sol = bk.modifiers.new("solid", "SOLIDIFY")
        sol.thickness = 0.004
        apply_mods(bk)
        objs.append(bk)
        objs.append(tube("BucketLine", [(-0.12, 0.26, SOLE_Z + 0.26), (-0.10, 0.30, SOLE_Z + 0.28), (-0.02, 0.25, SOLE_Z + 0.01),
                                         (0.10, 0.20, SOLE_Z + 0.005)], 0.004, H.MAT["RopeMain"], smooth_path=True))
    if ins.get("extinguisher", True):
        xe, ye = xw + LINER_T + 0.06, 0.40
        objs.append(cyl("Extinguisher", (xe, ye, 0.36), (xe, ye, 0.62), 0.04, mats["ExtinguisherRed"], 24))
        objs.append(cyl("ExtValve", (xe, ye, 0.62), (xe, ye, 0.66), 0.015, H.MAT["BlackPlastic"], 12))
        objs.append(box("ExtBracket", xe - 0.045, xe - 0.035, ye - 0.04, ye + 0.04, 0.42, 0.56, H.MAT["Stainless"]))
    if ins.get("anchor", True):
        # Danforth on the V-berth's forward end with its rode flaked beside it
        ax, ay, az = x_end - 0.30, 0.10, VBERTH_Z + 0.01
        objs.append(cyl("AnchorShank", (ax - 0.25, ay, az + 0.03), (ax + 0.12, ay, az + 0.01), 0.008, mats["Galvanised"], 8))
        for sy in (-1, 1):
            fl = box(f"AnchorFluke_{sy}", ax + 0.0, ax + 0.18, ay + sy * 0.02, ay + sy * 0.15, az, az + 0.004, mats["Galvanised"])
            fl.rotation_euler = (math.radians(6 * sy), 0, 0)
            objs.append(fl)
        objs.append(cyl("AnchorStock", (ax + 0.02, ay - 0.20, az + 0.008), (ax + 0.02, ay + 0.20, az + 0.008), 0.007, mats["Galvanised"], 8))
        from j22_details import coil
        objs += coil("AnchorRode", (ax - 0.05, -0.12, az), 0.12, 3.5, H.MAT["RopeMooring"], r=0.0055, seed=st["seed"] + 9, flat_z=az)
    return objs
