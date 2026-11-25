"""The Lagoon 42's rebuild in Blender (docs/lagoon42-2 on): the hulls (slice 1), the bridge deck (slice 2), the decks,
saloon and roof (slice 3), the cockpit (slice 4), the appendages (slice 5) and the rig (slice 6).

    blender -b --factory-startup -P build_lagoon42.py -- <out dir>

Builds both hull shells from hull_lagoon42.py (lines_lagoon42.json, the canoe depth solved for the game's 15.5 t),
each one shell from its inboard top round the keel to its outboard top: the sugar scoop's treads and risers close it
aft (L42_Hull, with the swim platforms and steps), the outboard windows are flush dark panes (L42_HullWindows). The
shell is cut along the boot top's line BOTTOM_Z: Topsides above, Antifouling below.

Slice 2 (docs/lagoon42-3) adds the bridge deck, its placeholder lid, the crossbeam with the centre beam, the bowsprit
and the trampolines from bridgedeck_lagoon42.py.

Slice 3 (docs/lagoon42-4) replaces the deck's lid with each hull's deck, toe rail and hatches (L42_Deck, L42_Hatches)
and adds the saloon's walls with their windows (L42_Saloon) and the roof over the saloon and cockpit (L42_Roof) from
saloon_lagoon42.py.

Slice 4 (docs/lagoon42-5) builds the cockpit from cockpit_lagoon42.py (L42_Cockpit: the sole, the aft bench, the roof's
posts, the settee and table, the lounge, the raised helm with its steps, seat, console and wheel, the landings' riser
windows), brings the bridge deck's aft face and the saloon's aft bulkhead down to the sole (the lid stays only inside
the saloon), glazes the sliding door from the sole up and cuts the helm's opening through the roof.

Slice 5 (docs/lagoon42-6) hangs the keels (L42_Keels, with their sacrificial shoes), the saildrives (L42_Saildrives:
legs, pods, anodes, intakes) and the propellers (L42_Prop_S, L42_Prop_P, origins on their axes) under the hulls from
appendages_lagoon42.py, and the rudders (L42_Rudder_S, L42_Rudder_P: one mesh, origins at the stocks' pivots).

Slice 6 (docs/lagoon42-7) stands the rig on the roof from rig_lagoon42.py: the mast (L42_Mast, origin at its heel, with
its track, spreaders, masthead and the fittings on it), the boom (L42_Boom, origin at the gooseneck's pin), the standing
rigging's wire (L42_Wires), its fittings and the running rigging's hardware (L42_RigFittings) and the lines
(L42_Running). Blocks, winches, clutches, the traveller, chainplates and turnbuckles are the boat kit's parts
(Tools/boatkit/bk_parts.py) on the axes and scale rig_lagoon42 gives them; their sockets are checked against where it
expects them.

Writes <out>/lagoon42.blend, <out>/lagoon42_report.json (the shape loop's report: the canoe bodies' volume and centre
of buoyancy beside the game's), <out>/hydrostatics.json and, from slice 6, <out>/Lagoon42_sockets.json (the rig's
sockets in the game's frame and centimetres, for the size check's air draft and slice 13).
Frame: Blender's, X forward, Y to PORT, Z up (the game's starboard-positive Y is mirrored, as build_fleet.py does), so
the shape loop's tools read it like the fleet's .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_lagoon42 as H  # noqa: E402
import bridgedeck_lagoon42 as B  # noqa: E402
import saloon_lagoon42 as S  # noqa: E402
import cockpit_lagoon42 as C  # noqa: E402
import appendages_lagoon42 as A  # noqa: E402
import rig_lagoon42 as R  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0]
os.makedirs(OUT, exist_ok=True)

N_STATIONS, N_GIRTH = 220, 60          # stations along her length; girth steps per side (bunched: hull_lagoon42.girth)
UV_M = 1.0
BOTTOM_Z = 0.05                        # the antifouling's top over the game's waterline
SLOT_RGB = {"Topsides": (0.92, 0.92, 0.9), "Antifouling": (0.16, 0.17, 0.2), "CabinWindow": (0.06, 0.07, 0.08),
            "Teak": (0.55, 0.38, 0.22), "Trampoline": (0.1, 0.1, 0.11), "Spar": (0.55, 0.56, 0.58),
            "Cushion": (0.78, 0.76, 0.72), "Keel": (0.24, 0.25, 0.28), "Stainless": (0.72, 0.73, 0.75),
            "Aluminium": (0.62, 0.63, 0.64), "Rubber": (0.04, 0.04, 0.045), "CastBronze": (0.66, 0.48, 0.26),
            "PaintedAluminium": (0.86, 0.86, 0.84), "WhitePlastic": (0.85, 0.84, 0.8), "BlackPlastic": (0.03, 0.03, 0.035),
            "CarbonMatte": (0.05, 0.05, 0.055), "Graphics": (0.45, 0.015, 0.02), "RedPlastic": (0.7, 0.05, 0.04),
            "Rope": (0.78, 0.79, 0.8)}


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*SLOT_RGB[name], 1.0)
    return m


def box_uvs(bm):
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        f.normal_update()
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[a] / UV_M, lp.vert.co[b] / UV_M)


def to_object(name, bm, mats):
    box_uvs(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in mats:
        me.materials.append(material(m))
    return ob


def bl(x, y, z):
    """Game frame (Y starboard) to Blender's (Y port)."""
    return (x, -y, z)


def hull_rows(cy, out_sign):
    """One hull's grid: for each station, the section from the inboard top round the keel to the outboard top, as
    game-frame points; out_sign is the outboard direction (+1 starboard hull, -1 port hull)."""
    rows = []
    xs = H.stations(N_STATIONS)
    for x in xs:
        row = []
        for j in range(-N_GIRTH, N_GIRTH + 1):
            side = 1 if j > 0 else -1
            y, z = H.section(x, H.girth(abs(j), N_GIRTH), side)
            if x == xs[-1]:
                y = 0.0
            row.append((x, cy + out_sign * side * y if j else cy, z))
        rows.append(row)
    return xs, rows


def section_between(x, z0, z1, side, n=8):
    """Half-breadths of the shell at station x between heights z0 and z1 on one side (side 1 outboard)."""
    out = []
    for k in range(n + 1):
        z = z0 + (z1 - z0) * k / n
        out.append((H.topsides_y(x, z), z))
    return out


def build_hull(bm, cy, out_sign):
    xs, rows = hull_rows(cy, out_sign)
    vrows = [[bm.verts.new(bl(*p)) for p in row] for row in rows]
    for a, b in zip(vrows[:-1], vrows[1:]):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    # the transom: from the platform's edge round the keel, its own vertices so its edge stays crisp
    bm.faces.new([bm.verts.new(bl(*p)) for p in rows[0]])
    treads = []
    steps = H.scoop_steps()
    # the treads: flat from the inboard top to the outboard wall at each step's height
    for (x0, x1, z) in steps:
        txs = [x for x in xs if x0 - 1e-6 <= x <= x1 + 1e-6]
        trow = []
        for x in txs:
            yi = H.topsides_y(x, z)
            trow.append([bm.verts.new(bl(x, cy - out_sign * yi, z)), bm.verts.new(bl(x, cy + out_sign * yi, z))])
        for a, b in zip(trow[:-1], trow[1:]):
            treads.append(bm.faces.new((a[0], a[1], b[1], b[0])))
    # the risers: up from each tread to the next (the last to the sheer), across the hull at the step's forward edge
    tops = [z for _, _, z in steps[1:]] + [H.sheer_z(steps[-1][1])]
    for (x0, x1, z), zt in zip(steps, tops):
        inb = section_between(x1, z, zt, -1)
        outb = section_between(x1, z, zt, 1)
        poly = [bl(x1, cy - out_sign * y, zz) for y, zz in inb] + [bl(x1, cy + out_sign * y, zz) for y, zz in reversed(outb)]
        bm.faces.new([bm.verts.new(p) for p in poly])
    return treads


def build_windows(bm, cy, out_sign):
    """Flush dark panes on the outboard topsides, 4 mm proud, with rounded corners."""
    for pane in H.LINES["windows"]["panes"]:
        (xa, xb), (za, zb), r = pane["x"], pane["z"], pane["corner"]
        nx, nz = 24, 8
        grid = []
        for i in range(nx + 1):
            x = xa + (xb - xa) * i / nx
            dx = min(x - xa, xb - x)
            inset = r - math.sqrt(max(r * r - (r - dx) ** 2, 0.0)) if dx < r else 0.0
            col = []
            for k in range(nz + 1):
                z = za + inset + (zb - za - 2 * inset) * k / nz
                y = H.topsides_y(x, z) + 0.004
                col.append(bm.verts.new(bl(x, cy + out_sign * y, z)))
            grid.append(col)
        for a, b in zip(grid[:-1], grid[1:]):
            for k in range(nz):
                bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))


def grid_faces(bm, rows, flip=False):
    """Quads between consecutive rows of game-frame points (every row the same length); returns the faces."""
    vrows = [[bm.verts.new(bl(*p)) for p in row] for row in rows]
    faces = []
    for a, b in zip(vrows[:-1], vrows[1:]):
        for j in range(len(a) - 1):
            q = (a[j], a[j + 1], b[j + 1], b[j])
            faces.append(bm.faces.new(q[::-1] if flip else q))
    return faces


def face_out(bm, faces, probe, want):
    """Turn the faces' winding so the one nearest the game-frame point probe faces along want (a game-frame vector)."""
    p = bl(*probe)
    near = min(faces, key=lambda f: (f.calc_center_median() - Vector(p)).length)
    near.normal_update()
    w = bl(*want)
    if near.normal.dot(Vector(w)) < 0:
        bmesh.ops.reverse_faces(bm, faces=faces)


def sweep(bm, section, path, closed_ends=True):
    """A tube: section [(a, b)] placed at each path point by frame(t) -> (origin, a axis, b axis), game frame."""
    vrows = []
    for o, ea, eb in path:
        vrows.append([bm.verts.new(bl(*(o[i] + ea[i] * a + eb[i] * b for i in range(3)))) for a, b in section])
    faces = []
    n = len(section)
    for r0, r1 in zip(vrows[:-1], vrows[1:]):
        for j in range(n):
            faces.append(bm.faces.new((r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j])))
    if closed_ends:
        faces.append(bm.faces.new(vrows[0][::-1]))
        faces.append(bm.faces.new(vrows[-1]))
    return faces


def build_bridgedeck():
    """The bridge deck (underside, nose, foredeck and its aft face), the placeholder lid aft of the foredeck, the
    crossbeam with the centre beam, the bowsprit and the trampolines: each its own object."""
    bm = bmesh.new()
    faces = grid_faces(bm, B.bridgedeck_rows())
    faces.append(bm.faces.new([bm.verts.new(bl(*p)) for p in B.aft_face(S.SOLE_Z)]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    face_out(bm, bm.faces[:], (0.0, 0.0, B.US["z"]), (0, 0, -1))
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    to_object("L42_Bridgedeck", bm, ["Topsides"])

    bm = bmesh.new()
    grid_faces(bm, B.lid_rows(S.SAL["aft"][0]))
    face_out(bm, bm.faces[:], (0.0, 0.0, 1.6), (0, 0, 1))
    to_object("L42_BridgeLidPlaceholder", bm, ["Topsides"])

    bm = bmesh.new()
    sec = B.rounded_rect(B.CB["chord"], B.CB["depth"], B.CB["radius"])
    e = B.crossbeam_ends()
    path = [((B.CB["x"], -e + 2 * e * k / 40, B.CB["z"]), (1, 0, 0), (0, 0, 1)) for k in range(41)]
    sweep(bm, sec, path)
    sec = B.rounded_rect(B.CBM["width"], B.CBM["depth"], B.CBM["radius"])
    x0, x1 = B.centre_beam_ends()
    path = [((x0 + (x1 - x0) * k / 20, 0.0, B.CBM["z"]), (0, 1, 0), (0, 0, 1)) for k in range(21)]
    sweep(bm, sec, path)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    to_object("L42_Crossbeam", bm, ["Topsides"])

    bm = bmesh.new()
    n = 16
    path = []
    for k in range(13):
        x, z, r = B.bowsprit_axis(k / 12)
        path.append(((x, 0.0, z), (0, r, 0), (0, 0, r)))
    circle = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]
    sweep(bm, circle, path)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    to_object("L42_Bowsprit", bm, ["Spar"])

    bm = bmesh.new()
    for side in (1, -1):
        fs = grid_faces(bm, B.trampoline_grid(side))
        face_out(bm, fs, (5.0, side * 1.2, B.TR["z"]), (0, 0, 1))
    to_object("L42_Trampolines", bm, ["Trampoline"])


def loop_faces(bm, rings, mats=None):
    """Quads between consecutive closed rings of game-frame points (every ring the same length); mats(k, i) gives a
    face's material index (k the ring, i the column). Returns the vertex rings and the faces."""
    vr = [[bm.verts.new(bl(*p)) for p in ring] for ring in rings]
    faces = []
    for k, (a, b) in enumerate(zip(vr[:-1], vr[1:])):
        n = len(a)
        for i in range(n):
            f = bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
            if mats:
                f.material_index = mats(k, i)
            faces.append(f)
    return vr, faces


def build_deck():
    """Each hull's deck (crowned between its sheers) with the toe rail on its outboard edge (L42_Deck), and the hatches
    (L42_Hatches: a low white frame, dark acrylic on top)."""
    bm = bmesh.new()
    for cy, out_sign in ((H.HULL_Y, 1), (-H.HULL_Y, -1)):
        fs = grid_faces(bm, S.deck_rows(cy))
        face_out(bm, fs, (0.0, cy, 1.6), (0, 0, 1))
        fs = grid_faces(bm, S.toe_rail_rows(cy, out_sign))
        face_out(bm, fs, (0.0, cy + out_sign * (H.half_beam(0.0) - 0.015), 1.6), (0, 0, 1))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    to_object("L42_Deck", bm, ["Topsides"])

    bm = bmesh.new()
    for cy in (H.HULL_Y, -H.HULL_Y):
        for x0, x1, y0, y1, z0, z1 in S.hatches(cy):
            v = [bm.verts.new(bl(x, y, z)) for z in (z0, z1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            top = bm.faces.new(v[4:])
            top.material_index = 1
            for i in range(4):
                bm.faces.new((v[i], v[(i + 1) % 4], v[4 + (i + 1) % 4], v[4 + i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    to_object("L42_Hatches", bm, ["Topsides", "CabinWindow"])


def build_saloon():
    """The saloon's walls round its plan, from under the decks (or the cockpit's sole) up into the roof: white below
    the plinth and above the windows, dark glass between along the front, the side windows and the aft bulkhead, and
    from the sole up across the sliding door (L42_Saloon)."""
    rows, glazed = S.wall_rows()
    bm = bmesh.new()
    _, faces = loop_faces(bm, rows, lambda k, i: 1 if (k == 1 and glazed[i]) or (k == 0 and glazed[i] == S.DOOR)
                          else 0)
    face_out(bm, faces, (S.SAL["front_x"], 0.0, 2.1), (1, 0, 0))
    for f in bm.faces:
        f.smooth = True
    to_object("L42_Saloon", bm, ["Topsides", "CabinWindow"])


def build_roof():
    """The roof over the saloon and the cockpit: rings from the top's centre over its rounded edge to the underside's
    centre, each closed at the middle (L42_Roof)."""
    rings = S.roof_rings()
    bm = bmesh.new()
    vr, faces = loop_faces(bm, rings)
    faces.append(bm.faces.new(vr[0][::-1]))
    faces.append(bm.faces.new(vr[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    face_out(bm, faces, (0.0, 0.0, S.ROOF["top_z"]), (0, 0, 1))
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    roof = to_object("L42_Roof", bm, ["Topsides"])
    ho = S.ROOF["helm_opening"]
    (x0, x1), (y0, y1) = ho["x"], ho["y"]
    bm = bmesh.new()
    add_slab(bm, C.rounded_rect(x0, x1, y0, y1, ho["radius"], 6), (S.ROOF["under_z"] - 0.2, S.ROOF["top_z"] + 0.2))
    cutter = to_object("L42_HelmOpeningCutter", bm, ["Topsides"])
    mod = roof.modifiers.new("HelmOpening", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(roof.evaluated_get(dg))
    roof.modifiers.clear()
    old = roof.data
    roof.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    if not me.materials:
        me.materials.append(material("Topsides"))
    for p in me.polygons:
        p.material_index = 0
    return roof


def add_slab(bm, outline, z):
    """A prism over a plan outline [(x, y)] from z[0] to z[1], its normals out. Returns its faces."""
    lo = [bm.verts.new(bl(x, y, z[0])) for x, y in outline]
    hi = [bm.verts.new(bl(x, y, z[1])) for x, y in outline]
    n = len(outline)
    faces = [bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i])) for i in range(n)]
    faces += [bm.faces.new(lo[::-1]), bm.faces.new(hi)]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def add_box(bm, lo, hi, rnd):
    """A box between game-frame corners lo and hi with its edges rounded rnd. Returns (faces, rounded faces)."""
    before = set(bm.faces)
    a, b = bl(*lo), bl(*hi)
    c = [(a[i] + b[i]) / 2 for i in range(3)]
    sz = [abs(b[i] - a[i]) for i in range(3)]
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    for v in vs:
        v.co = Vector([c[i] + v.co[i] * sz[i] for i in range(3)])
    rounded = []
    if rnd > 0:
        es = list({e for v in vs for e in v.link_edges})
        rounded = bmesh.ops.bevel(bm, geom=vs + es, offset=min(rnd, 0.45 * min(sz)), offset_type="OFFSET",
                                  segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)["faces"]
    faces = [f for f in bm.faces if f not in before]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces, rounded


def add_cylinder(bm, a, b, r, segments=16):
    """A capped cylinder from game-frame point a to b. Returns its faces."""
    before = set(bm.faces)
    pa, pb = Vector(bl(*a)), Vector(bl(*b))
    d = pb - pa
    m = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    m.translation = (pa + pb) / 2
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=r, radius2=r, depth=d.length,
                          matrix=m)
    faces = [f for f in bm.faces if f not in before]
    for f in faces:
        f.smooth = len(f.verts) == 4
    return faces


def add_torus(bm, centre, axis, R, r, n=48, m=10):
    """A ring of tube radius r round centre, R to the tube's centre, in the plane normal to axis (game frame)."""
    ax = Vector(bl(*axis)).normalized()
    u = ax.orthogonal().normalized()
    w = ax.cross(u)
    c = Vector(bl(*centre))
    rings = []
    for i in range(n):
        t = 2 * math.pi * i / n
        radial = u * math.cos(t) + w * math.sin(t)
        o = c + radial * R
        ring = []
        for j in range(m):
            p = 2 * math.pi * j / m
            ring.append(bm.verts.new(o + radial * (r * math.cos(p)) + ax * (r * math.sin(p))))
        rings.append(ring)
    faces = []
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(m):
            faces.append(bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in faces:
        f.smooth = True
    return faces


def solid(bm, rings, mat=0, mats=None, smooth=True, origin=(0.0, 0.0, 0.0)):
    """A closed solid from rings of game-frame points (every ring the same length), capped at both ends, its normals
    out; points are taken relative to origin (game frame). Returns its faces."""
    o = bl(*origin)
    vr = [[bm.verts.new(tuple(c - oc for c, oc in zip(bl(*p), o))) for p in rg] for rg in rings]
    faces = []
    for k, (a, b) in enumerate(zip(vr[:-1], vr[1:])):
        n = len(a)
        for i in range(n):
            f = bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
            f.material_index = mats(k) if mats else mat
            f.smooth = smooth
            faces.append(f)
    for cap in (vr[0][::-1], vr[-1]):
        f = bm.faces.new(cap)
        f.material_index = mat if not mats else mats(0 if cap is vr[0] else len(vr) - 2)
        faces.append(f)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def build_appendages():
    """The keels, saildrives and propellers under the hulls, and the rudders (each its own object at its pivot)."""
    kr, shoe = A.keel_rings()
    bm = bmesh.new()
    for rings in (kr, A.mirror(kr)):
        solid(bm, rings, mats=lambda k: 1 if k >= shoe else 0)
    to_object("L42_Keels", bm, ["Antifouling", "Keel"])

    bm = bmesh.new()
    for mir in (False, True):
        f = A.mirror if mir else (lambda r: r)
        solid(bm, f(A.leg_rings()))
        solid(bm, f(A.pod_rings()))
        solid(bm, f(A.anode_rings()), mat=1, smooth=False)
        for q in A.intake_slots():
            qq = f([q])[0]
            face = bm.faces.new([bm.verts.new(bl(*p)) for p in qq])
            face.material_index = 2
            x, y, z = qq[0]
            face_out(bm, [face], (x, y, z), (0, 1 if y > (H.HULL_Y if not mir else -H.HULL_Y) else -1, 0))
    to_object("L42_Saildrives", bm, ["Antifouling", "Aluminium", "Rubber"])

    ax = A.prop_axis()
    for tag, mir in (("S", False), ("P", True)):
        f = A.mirror if mir else (lambda r: r)
        origin = f([[ax]])[0][0]
        bm = bmesh.new()
        solid(bm, f(A.hub_rings()), origin=origin)
        for k in range(A.SD["prop"]["blades"]):
            solid(bm, f(A.blade_rings(k)), origin=origin)
        ob = to_object("L42_Prop_" + tag, bm, ["CastBronze"])
        ob.location = bl(*origin)

    piv = A.rudder_pivot()
    bm = bmesh.new()
    solid(bm, A.rudder_rings(), origin=piv)
    a, b, r = A.rudder_stock()
    for fc in add_cylinder(bm, a, b, r):
        fc.material_index = 1
    stock_faces = [fc for fc in bm.faces if fc.material_index == 1]
    sv = {v for fc in stock_faces for v in fc.verts}      # add_cylinder placed them in the game frame
    o = Vector(bl(*piv))
    for v in sv:
        v.co -= o
    me_ob = to_object("L42_Rudder_S", bm, ["Antifouling", "Stainless"])
    me_ob.location = bl(*piv)
    port = bpy.data.objects.new("L42_Rudder_P", me_ob.data)
    bpy.context.scene.collection.objects.link(port)
    port.location = bl(*A.rudder_pivot(-H.HULL_Y))
    return me_ob, port


RIG_OBJECTS = {"mast": "L42_Mast", "boom": "L42_Boom", "wires": "L42_Wires", "fittings": "L42_RigFittings",
               "running": "L42_Running"}


class Part:
    """One rig object's bmesh and its material slots, by name."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def slot(self, name):
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)


def kit_merge(acc, p):
    """One of the boat kit's parts (rig_lagoon42.kit) merged into acc: built by bk_parts, collapsed if light, put on
    its axes (game frame, mirrored into Blender's) and scale. Returns its sockets in the game frame."""
    if R.KIT_DIR not in sys.path:
        sys.path.insert(0, R.KIT_DIR)
    import bk_parts as KP  # noqa: E402
    import bk_geom as KG  # noqa: E402
    ob = KP.build(p["name"], **p["kw"])
    if p["light"]:
        d = ob.modifiers.new("light", "DECIMATE")
        d.decimate_type = "COLLAPSE"
        d.ratio = p["light"]
        d.use_collapse_triangulate = True
        KG.apply(ob)
    S_ = lambda v: Vector((v[0], -v[1], v[2]))
    k = p["scale"]
    cols = [S_(p["ax"]) * k, S_(p["ay"]) * k, S_(p["az"]) * k]
    rot = Matrix([[cols[c][r] for c in range(3)] for r in range(3)]).to_4x4()
    xf = Matrix.Translation(S_(p["origin"])) @ rot
    socks = {}
    for ch in list(ob.children):
        if ch.name.startswith("SOCKET_"):
            q = xf @ (ob.matrix_world @ ch.location)
            socks[ch.name[7:].split(".")[0]] = (q.x, -q.y, q.z)
        bpy.data.objects.remove(ch)
    me = ob.data
    me.transform(ob.matrix_world)
    me.transform(xf)
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    tmp = bmesh.new()
    tmp.from_mesh(me)
    bmesh.ops.dissolve_degenerate(tmp, dist=1e-6, edges=tmp.edges[:])
    tmp.to_mesh(me)
    tmp.free()
    # Appended by hand: bmesh.from_mesh into a bmesh that already holds faces renumbered some of the new faces'
    # materials. Faces keep their slot (by material name), smoothing and the kit's sharp edges.
    names = [mt.name.split(".")[0] for mt in me.materials] or ["Stainless"]
    slots = [acc.slot(n) for n in names]
    sharp_attr = me.attributes.get("sharp_edge")
    sharp = {tuple(sorted(e.vertices)) for e, a in zip(me.edges, sharp_attr.data) if a.value} if sharp_attr else set()
    vs = [acc.bm.verts.new(v.co) for v in me.vertices]
    index = {v: i for i, v in enumerate(vs)}
    for poly in me.polygons:
        try:
            f = acc.bm.faces.new([vs[i] for i in poly.vertices])
        except ValueError:
            continue
        f.material_index = slots[min(poly.material_index, len(slots) - 1)]
        f.smooth = poly.use_smooth
        if sharp:
            for e in f.edges:
                if tuple(sorted(index[v] for v in e.verts)) in sharp:
                    e.smooth = False
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return socks


def build_rig():
    """The mast, boom, wires, the rig's fittings and its lines (rig_lagoon42.parts()), each object at its origin (the
    mast at its step, the boom at the gooseneck's pin). Checks every kit part's sockets where rig_lagoon42 expects
    them; returns the worst miss (m)."""
    accs = {k: Part() for k in RIG_OBJECTS}
    worst = 0.0
    for p in R.parts():
        acc = accs[p["obj"]]
        k = p["kind"]
        if k == "rings":
            solid(acc.bm, p["rings"], mat=acc.slot(p["mat"]), smooth=p["smooth"])
        elif k == "cyl":
            for f in add_cylinder(acc.bm, p["a"], p["b"], p["radius"], p.get("segments", 16)):
                f.material_index = acc.slot(p["mat"])
        elif k == "torus":
            for f in add_torus(acc.bm, p["centre"], p["axis"], p["R"], p["r"], p.get("n", 48), p.get("m", 10)):
                f.material_index = acc.slot(p["mat"])
        elif k == "box":
            faces, rounded = add_box(acc.bm, p["lo"], p["hi"], p["round"])
            for f in faces:
                f.material_index = acc.slot(p["mat"])
                f.smooth = False
            for f in rounded:
                f.smooth = True
        elif k == "kit":
            got = kit_merge(acc, p)
            for name, want in p["expect"].items():
                miss = math.dist(got[name], want) if name in got else float("inf")
                worst = max(worst, miss)
                if miss > 0.002:
                    print(f"rig: kit {p['name']} socket {name} at {got.get(name)}, expected {want}")
    _, origins = R.sockets()
    obj_origin = {"mast": origins["SM_Lagoon42_Mast"], "boom": origins["SM_Lagoon42_Boom"]}
    for key, acc in accs.items():
        o = Vector(bl(*obj_origin.get(key, (0.0, 0.0, 0.0))))
        for v in acc.bm.verts:
            v.co -= o
        ob = to_object(RIG_OBJECTS[key], acc.bm, acc.mats)
        ob.location = o
    return worst


def write_sockets(path):
    """The rig's sockets in the game's sockets file shape (Unreal frame: X forward, Y starboard, Z up, centimetres)."""
    so, origins = R.sockets()
    cm = lambda p: [round(c * 100.0, 2) for c in p]
    json.dump({"sockets": {k: cm(p) for k, (p, _) in sorted(so.items())},
               "owner": {k: o for k, (_, o) in sorted(so.items())},
               "origins": {k: cm(p) for k, p in origins.items()},
               "note": "Written by build_lagoon42.py from rig_lagoon42.sockets() (docs/lagoon42-7): the rebuild's sockets "
                       "for the size check's air draft and for slice 13, which imports her into the game."},
              open(path, "w"), indent=1)


def build_cockpit():
    """The cockpit (L42_Cockpit): the teak sole, every part of cockpit_lagoon42.parts() and the dark windows in the
    landings' risers."""
    mats = ["Topsides", "Teak", "Cushion", "Stainless", "CabinWindow", "Rubber"]
    mi = {m: i for i, m in enumerate(mats)}
    bm = bmesh.new()
    sole = grid_faces(bm, C.sole_rows())
    face_out(bm, sole, (-3.5, 0.0, C.SOLE_Z), (0, 0, 1))
    for f in sole:
        f.material_index = mi["Teak"]
    for p in C.parts():
        k = p["kind"]
        if k == "box":
            lo, hi = list(p["lo"]), list(p["hi"])
            top_z = hi[2]
            if p.get("cushion"):
                hi[2] = top_z - C.CUSHION
            faces, rounded = add_box(bm, lo, hi, p["round"])
            for f in faces:
                f.material_index = mi[p["mat"]]
                f.smooth = False
            for f in rounded:
                f.smooth = True
            if p.get("top"):
                for f in faces:
                    f.normal_update()
                    if f.normal.z > 0.99 and f.calc_center_median().z > hi[2] - 1e-3:
                        f.material_index = mi[p["top"]]
            if p.get("cushion"):
                c_lo = (lo[0] + 0.01, lo[1] + 0.01, top_z - C.CUSHION - 0.005)
                c_hi = (hi[0] - 0.01, hi[1] - 0.01, top_z)
                faces, rounded = add_box(bm, c_lo, c_hi, 0.03)
                for f in faces:
                    f.material_index = mi["Cushion"]
                    f.smooth = False
                for f in rounded:
                    f.smooth = True
        elif k == "slab":
            for f in add_slab(bm, p["outline"], p["z"]):
                f.material_index = mi[p["mat"]]
                f.smooth = False
        elif k == "cyl":
            for f in add_cylinder(bm, p["a"], p["b"], p["radius"]):
                f.material_index = mi[p["mat"]]
        elif k == "torus":
            for f in add_torus(bm, p["centre"], p["axis"], p["R"], p["r"]):
                f.material_index = mi[p["mat"]]
        elif k == "rings":
            solid(bm, p["rings"], mat=mi[p["mat"]], smooth=p["smooth"])
        elif k == "pane":
            f = bm.faces.new([bm.verts.new(bl(*q)) for q in p["corners"]])
            face_out(bm, [f], p["corners"][0], p["facing"])
            f.material_index = mi[p["mat"]]
    for poly in C.riser_windows():
        f = bm.faces.new([bm.verts.new(bl(*q)) for q in poly])
        face_out(bm, [f], poly[0], (-1, 0, 0))
        f.material_index = mi["CabinWindow"]
    return to_object("L42_Cockpit", bm, mats)


def mesh_volume_below(ob, z=0.0):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, z), plane_no=(0, 0, 1),
                           clear_outer=True)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def light_sink(ob, light_m3):
    """How far the light boat rises off the game's waterline: the height z whose mesh volume under it, plus the
    appendages', is light_m3 (bisection on the built mesh, so it is the new hulls' own waterplane, not today's)."""
    app = H.BOT["appendage_volume_m3"]
    lo, hi = -0.4, 0.0
    for _ in range(30):
        z = (lo + hi) / 2
        if mesh_volume_below(ob, z) + app > light_m3:
            hi = z
        else:
            lo = z
    return -(lo + hi) / 2


def main():
    clear_scene()
    depth = H.solve_depth()
    bm = bmesh.new()
    treads = []
    for cy, out_sign in ((H.HULL_Y, 1), (-H.HULL_Y, -1)):
        treads += build_hull(bm, cy, out_sign)
    for f in treads:
        f.material_index = 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0.0, 0.0, BOTTOM_Z),
                           plane_no=(0.0, 0.0, 1.0))
    for f in bm.faces:
        if f.material_index != 2:
            f.material_index = 1 if f.calc_center_median().z < BOTTOM_Z else 0
        f.smooth = len(f.verts) < 6
    hull = to_object("L42_Hull", bm, ["Topsides", "Antifouling", "Teak"])
    wm = bmesh.new()
    for cy, out_sign in ((H.HULL_Y, 1), (-H.HULL_Y, -1)):
        build_windows(wm, cy, out_sign)
    to_object("L42_HullWindows", wm, ["CabinWindow"])
    build_deck()
    build_bridgedeck()
    build_saloon()
    build_roof()
    build_cockpit()
    build_appendages()
    kit_miss = build_rig()
    write_sockets(os.path.join(OUT, "Lagoon42_sockets.json"))

    h = H.hydrostatics()
    mesh_v = mesh_volume_below(hull)
    app = H.BOT["appendage_volume_m3"]
    g = H.CARD["game"]
    sink = light_sink(hull, g["design_volume_m3"] - (g["load_kg"] + g["crew_kg"]) / 1000.0)
    appn = A.numbers()
    ax = A.prop_axis()
    report = {"canoe_volume_m3": round(mesh_v + app, 4), "hull_volume_m3": round(mesh_v, 4),
              "design_hull_volume_m3": round(h["volume_m3"], 4), "appendage_volume_m3": app,
              "physics_volume_m3": g["design_volume_m3"], "cb_x": round(h["cb"][0], 3), "cb_z": round(h["cb"][2], 3),
              "physics_cb": [-0.196, -0.424], "canoe_depth_m": round(depth, 4), "lwl_m": round(h["lwl"], 3),
              "beam_wl_one_hull_m": round(h["beam_wl_one_hull"], 3),
              "waterplane_m2": round(H.waterplane(), 2), "waterplane_15cm_down_m2": round(H.waterplane(-0.15), 2),
              "load_sink_m": round(sink, 4), "canoe_depth_light_m": round(depth - sink, 4),
              "bridgedeck_clearance_m": B.US["z"], "bridgedeck_clearance_light_m": round(B.US["z"] + sink, 4),
              "roof_top_z_m": S.ROOF["top_z"], "roof_top_light_m": round(S.ROOF["top_z"] + sink, 4),
              "mast_foot_measured": S.SD["measured"]["mast_foot"],
              "cockpit_sole_z_m": C.SOLE_Z, "cockpit_headroom_m": round(S.ceiling_z(0.0) - C.SOLE_Z, 3),
              "helm_side": "port", "helm_eye_m": [round(v, 3) for v in C.helm_eye()],
              "keel_bottom_z_m": round(A.TIP_Z, 3), "keel_area_m2": round(appn["keel"]["area"], 3),
              "keel_centroid_x_m": round(appn["keel"]["centroid_x"], 3), "rudder_area_m2": round(appn["rudder"]["area"], 3),
              "rudder_pivots_m": [[round(c, 3) for c in A.rudder_pivot(cy)] for cy in (-H.HULL_Y, H.HULL_Y)],
              "prop_axes_m": [[round(c, 3) for c in (ax[0], cy, ax[2])] for cy in (-H.HULL_Y, H.HULL_Y)],
              "appendage_volume_built_m3": round(appn["total_volume"], 4),
              "rig": {k: (round(v, 3) if isinstance(v, float) else v if isinstance(v, str) else [round(c, 3) for c in v])
                      for k, v in R.numbers().items()},
              "rig_kit_socket_miss_m": round(kit_miss, 4),
              "note": "canoe_volume_m3 is what lagoon42_check.py weighs: both hull meshes' volume under the game's "
                      "waterline (hull_volume_m3) plus the appendages' (appendage_volume_m3: the keels, rudders and "
                      "saildrives under the hulls' bottoms as slice 5 builds them, appendage_volume_built_m3, solved "
                      "with the canoe depth). design_hull_volume_m3 is the drawing's own integral "
                      "(hull_lagoon42.hydrostatics), which solve_depth sets to the target. load_sink_m: how far the "
                      "game's stores and crew (3.4 t) sink these hulls below the light boat's waterline, from the mesh "
                      "(today's hulls: 0.148, the card's game.load_sink_m); lagoon42_check.py measures the draft and "
                      "air draft from it when it is here. helm_eye_m: the seated helmsman's eye at "
                      "the raised helm, to port as on the real boat (today's model, and the crew's helm position in "
                      "CrewMotion, have it to starboard until slice 12). rudder_pivots_m (port, starboard) are the "
                      "rudders' origins, the game's RudderPivot sockets; prop_axes_m the propellers' (slice 13)."}
    json.dump(report, open(os.path.join(OUT, "lagoon42_report.json"), "w"), indent=1)
    json.dump(h, open(os.path.join(OUT, "hydrostatics.json"), "w"), indent=1)
    tris = sum(len(p.vertices) - 2 for p in hull.data.polygons)
    print(f"Lagoon 42: canoe depth {depth:.4f} m, hulls {h['volume_m3']:.4f} m^3 (mesh {mesh_v:.4f}), CB x {h['cb'][0]:+.3f}, "
          f"LWL {h['lwl']:.3f} m, one hull's BWL {h['beam_wl_one_hull']:.3f} m, load sink {sink:.3f} m, hull triangles {tris}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "lagoon42.blend"))


main()
