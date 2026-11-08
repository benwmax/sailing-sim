"""Course marks and the crew-overboard buoy (part detail loop, Nov 2026: docs/part-detail-loop/marks.md).

The drills' and races' placeholders were engine shapes: an orange cylinder for each lesson and race mark, a sphere for
the race's pin end and a yellow sphere for the crew-overboard "dummy". These are the real things, sized from the
catalogues:

  RaceMark       inflatable cylindrical racing mark, 0.90 m across and 1.50 m tall (the common club size: Lalizas and
                 Osculati 90 x 150 cm; Crewsaver's 5 ft is 0.76 x 1.52 m)
  LessonMark     the smaller cylinder schools lay for drills, 0.61 m across and 1.22 m tall (Crewsaver's 4 ft)
  PinBuoy        the start line's pin end: a 0.80 m inflatable ball with a fibreglass flag staff and an orange flag
  HorseshoeBuoy  a US Type IV horseshoe buoy, 610 x 585 x 100 mm (Jim-Buoy 920 class: 24 x 23 x 4 in), yellow vinyl
                 over foam, reflective patches, a web strap with a snap across the open end

Inflatable PVC marks: a rolled tube with one welded vertical seam, end caps welded on with a proud flange at the top
and bottom edge (the shoulders round over where the pressure pushes the cap out), a webbing lifting handle on a
welded patch on top, an inflation valve, and a webbing loop with a stainless ring underneath for the anchor line. They
ride with a little of the bottom under: a scummed band at the waterline (slot MarkScum) and faded orange vinyl with a
soft sheen above it (slot MarkVinyl).

Unlike deck fittings these float, so the origin is on the WATERLINE (z = 0 is the lake's surface; the game places them
at the water's height), +Z up, the seam and the anchor ring toward -Y (away from a camera on +Y is arbitrary: the
game turns them at random). Sockets: Top, Anchor (the anchor line's ring), Waterline.

Lives in its own file (bk_parts imports every bk_part_*.py at its end).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

TAU = math.tau


# ------------------------------------------------------------------ helpers

def _slot_by_z(ob, z_split, low_slot):
    """Faces whose centre is below z_split take `low_slot` (the waterline scum) instead of the first slot."""
    me = ob.data
    if low_slot.name not in [m.name for m in me.materials]:
        me.materials.append(low_slot)
    k = [m.name for m in me.materials].index(low_slot.name)
    for p in me.polygons:
        if p.center.z < z_split:
            p.material_index = k
    return ob


def _inflated_cylinder_profile(R, H, z0, shoulder, bulge, n_side=24, n_sh=10, cap_dome=0.0):
    """(radius, z) profile of an inflated PVC tube with welded end caps, bottom to top. The side bows out by `bulge`
    (fraction of R) at mid height, the shoulders round over with radius `shoulder`, and the caps dome by `cap_dome`."""
    prof = [(0.0, z0 - cap_dome * 0.5)]
    # bottom cap: gentle dome out to the shoulder
    for i in range(1, 5):
        t = i / 5
        prof.append(((R - shoulder) * t, z0 - cap_dome * 0.5 * (1 - t * t)))
    for i in range(n_sh + 1):                                   # bottom shoulder, quarter round
        a = -math.pi / 2 + (math.pi / 2) * i / n_sh
        prof.append((R - shoulder + shoulder * math.cos(a), z0 + shoulder + shoulder * math.sin(a)))
    zs, ze = z0 + shoulder, z0 + H - shoulder
    for i in range(1, n_side):                                   # the side, bowed out a little in the middle
        t = i / n_side
        prof.append((R * (1 + bulge * math.sin(math.pi * t)), zs + (ze - zs) * t))
    for i in range(n_sh + 1):                                   # top shoulder
        a = (math.pi / 2) * i / n_sh
        prof.append((R - shoulder + shoulder * math.cos(a), ze + shoulder * math.sin(a)))
    zt = z0 + H
    for i in range(1, 6):
        t = i / 6
        prof.append(((R - shoulder) * (1 - t), zt + cap_dome * (1 - (1 - t) ** 2)))
    prof.append((0.0, zt + cap_dome))
    return prof


def _flange_ring(name, R, z, w, t, mat, segs=96):
    """A welded seam flange: a thin rounded lip standing proud `w` round the tube at height z."""
    prof = [(R - 0.004, z - t / 2), (R + w * 0.85, z - t / 2), (R + w, z - t * 0.2), (R + w, z + t * 0.2),
            (R + w * 0.85, z + t / 2), (R - 0.004, z + t / 2)]
    o = G.lathe(name, prof, mat, segs)
    return o


def _vertical_seam(name, R_of_z, z0, z1, ang, w, t, mat, n=24):
    """A welded vertical seam strip lying on the tube at angle `ang` (radius follows R_of_z)."""
    pts = [(R_of_z(z0 + (z1 - z0) * i / n), z0 + (z1 - z0) * i / n) for i in range(n + 1)]
    ca, sa = math.cos(ang), math.sin(ang)
    path = [(r * ca, r * sa, z) for r, z in pts]
    sec = [(-w / 2, -0.001), (w / 2, -0.001), (w / 2 * 0.8, t), (-w / 2 * 0.8, t)]
    # section u across the seam, v out of the surface: twist_up is the outward normal
    o = G.sweep(name, path, sec, mat, twist_up=(ca, sa, 0.0))
    return o


def _web_loop(name, p0, p1, height, width, thick, mat, n=16):
    """A flat webbing loop sewn down at p0 and p1, arching `height` off the surface (surface normal +Z)."""
    p0, p1 = Vector(p0), Vector(p1)
    mid = (p0 + p1) / 2
    path = []
    for i in range(n + 1):
        t = i / n
        p = p0.lerp(p1, t)
        p = p + Vector((0, 0, height * math.sin(math.pi * t) ** 0.8))
        path.append(p)
    sec = [(-width / 2, -thick / 2), (width / 2, -thick / 2), (width / 2, thick / 2), (-width / 2, thick / 2)]
    return G.sweep(name, path, sec, mat, twist_up=(0, 0, 1))


def _patch(name, c, w, d, t, mat, normal=(0, 0, 1), r=0.02):
    """A welded reinforcing patch: a thin rounded rectangle, its bottom face on the surface at c."""
    o = G.prism(name, G.rrect(w, d, r, 4), 0.0, t, mat, taper=0.97)
    o.matrix_world = G.along(Vector(c), Vector(normal))
    G.bake_xform(o)
    return o


def _valve(name, c, mat_body, mat_cap):
    """A low PVC inflation valve: a flanged base and a screw cap (Boston-valve size, about 45 mm across)."""
    x, y, z = c
    base = G.lathe(f"{name}_base", [(0, 0), (0.026, 0), (0.026, 0.003), (0.019, 0.006), (0.0, 0.006)], mat_body, 40)
    cap = G.lathe(f"{name}_cap", [(0, 0.005), (0.016, 0.005), (0.016, 0.017), (0.014, 0.019), (0.0, 0.019)], mat_cap, 32)
    # knurl on the cap: shallow ribs
    ribs = [G.box(f"{name}_rib{k}", (0.0162 * math.cos(TAU * k / 18), 0.0162 * math.sin(TAU * k / 18), 0.011),
                  (0.0025, 0.0025, 0.010), mat_cap) for k in range(18)]
    for k, rb in enumerate(ribs):
        rb.matrix_world = Matrix.Translation(rb.matrix_world.translation) @ Matrix.Rotation(TAU * k / 18, 4, "Z") @ \
            Matrix.Translation(-rb.matrix_world.translation) @ rb.matrix_world
        G.bake_xform(rb)
    o = G.join(name, [base, cap] + ribs)
    o.location = (x, y, z)
    G.bake_xform(o)
    return o


def _ring(name, c, r, wire, mat, plane="xz", segs=24):
    return G.tube(name, G.arc_pts(c, r, 0, TAU, segs, plane)[:-1], wire, mat, 12, closed=True)


# ------------------------------------------------------------------ cylindrical inflatable marks

def _cylinder_mark_parts(D, H, draft, segs=96):
    """An inflatable cylindrical mark D across and H tall, floating `draft` deep (origin on the waterline)."""
    vinyl, scum, web, steel, valve_mat = P.M("MarkVinyl"), P.M("MarkScum"), P.M("CrewStraps"), P.M("Stainless"), P.M("BlackPlastic")
    R = D / 2
    z0 = -draft
    shoulder = 0.11 * D                     # the weld lets the cap pull the edge into a soft round
    bulge = 0.018                           # the tube bows out ~1.8% at mid height under pressure
    dome = 0.025 * D                        # the end caps bow out a little under pressure (r3's 6% dome read as a cone)
    # the catalogue height is overall, domes included: the cylinder between the caps' seams is H less 1.5 domes (the
    # bottom cap's dome is half the top's: the anchor's pull and the water flatten it)
    z0, H = z0 + 0.5 * dome, H - 1.5 * dome
    body = G.lathe("tube", _inflated_cylinder_profile(R, H, z0, shoulder, bulge, cap_dome=dome), vinyl, segs)
    G.finish(body, 0)
    # scum band: everything up to 25 mm above the waterline (a film the wind chop leaves) is the waterline slot
    _slot_by_z(body, 0.025, scum)

    def r_at(z):                            # the side's radius at height z (for seams laid on it)
        zs, ze = z0 + shoulder, z0 + H - shoulder
        t = min(1.0, max(0.0, (z - zs) / (ze - zs)))
        return R * (1 + bulge * math.sin(math.pi * t))

    # welded end-cap flanges, just inside the shoulders' tangent points (where the cap sheet meets the tube)
    fl_w, fl_t = 0.016, 0.012
    fz_top = z0 + H - shoulder * 0.30
    fz_bot = z0 + shoulder * 0.30
    rr_top = R - shoulder + shoulder * math.cos(math.asin(0.70))
    flange_top = _flange_ring("flange_top", rr_top, fz_top, fl_w, fl_t, vinyl)
    flange_bot = _flange_ring("flange_bot", rr_top, fz_bot, fl_w, fl_t, scum)
    # the rolled tube's vertical seam (toward -Y)
    # the rolled tube's vertical seam (toward -Y), starting just above the waterline (r3's seam ran into the scum band
    # and its foot read as a dark defect)
    seams = [_vertical_seam("seam", lambda z: r_at(z), max(z0 + shoulder * 0.9, 0.04), z0 + H - shoulder * 0.9, -math.pi / 2, 0.030, 0.003, vinyl)]
    # top: a welded patch with a webbing lifting handle across it, and the inflation valve beside it
    zt = z0 + H + dome
    hl = 0.13 * D / 0.9                     # half the handle's span: a 26 cm webbing handle on the 0.9 m mark
    hp = _patch("handle_patch", (0, 0, zt - 0.004), 2.4 * hl, 0.13, 0.003, vinyl)
    handle = _web_loop("handle", (-hl, 0, zt), (hl, 0, zt), 0.075, 0.050, 0.003, web)
    tacks = [G.box(f"tack{s}", (s * hl, 0, zt + 0.001), (0.035, 0.054, 0.004), web) for s in (-1, 1)]
    valve = _valve("valve", (0.22 * R, 0.30 * R, zt - 0.004), vinyl, valve_mat)
    # underneath: a patch, a webbing loop and a stainless ring for the anchor line
    zb = z0 - dome * 0.5
    bp = _patch("anchor_patch", (0, 0, zb + 0.004), 0.22, 0.12, 0.003, scum, normal=(0, 0, -1))
    loop = _web_loop("anchor_loop", (-0.05, 0, zb), (0.05, 0, zb), -0.05, 0.030, 0.003, web)
    ring_r = 0.025
    ring = _ring("anchor_ring", (0, 0, zb - 0.05 - ring_r + 0.004), ring_r, 0.004, steel, plane="yz")
    objs = [body, flange_top, flange_bot] + seams + [hp, handle] + tacks + [valve, bp, loop, ring]
    socks = [("Top", (0, 0, zt + 0.075)), ("Anchor", (0, 0, zb - 0.05 - 2 * ring_r)), ("Waterline", (0, 0, 0))]
    return objs, socks


@P.part("RaceMark", "course", "Inflatable cylindrical racing mark, 0.90 m x 1.50 m, faded orange PVC, welded seams, lifting handle, anchor ring underneath; origin on the waterline")
def race_mark(diameter=0.90, height=1.50, draft=0.20):
    return P.done("RaceMark", *_cylinder_mark_parts(diameter, height, draft))


@P.part("LessonMark", "course", "Inflatable cylindrical drill mark, 0.61 m x 1.22 m (4 ft), faded orange PVC, welded seams, lifting handle, anchor ring underneath; origin on the waterline")
def lesson_mark(diameter=0.61, height=1.22, draft=0.15):
    return P.done("LessonMark", *_cylinder_mark_parts(diameter, height, draft))


# ------------------------------------------------------------------ the pin end: an inflatable ball with a flag

def _flag(name, x0, z0, w, h, mat, waves=1.2, amp=0.025, nx=16, nz=6, thick=0.0012):
    """A cloth flag in the XZ plane, luff on the staff at x0, a gentle wave across it (thin solid so both sides draw)."""
    bm = bmesh.new()
    grid = []
    for side in (-1, 1):
        rows = []
        for j in range(nz + 1):
            row = []
            for i in range(nx + 1):
                u, v = i / nx, j / nz
                y = amp * u * math.sin(TAU * waves * u + 0.6 * v) + side * thick / 2
                row.append(bm.verts.new((x0 + w * u, y, z0 - h * v - 0.015 * u * u)))
            rows.append(row)
        grid.append(rows)
    for s, rows in enumerate(grid):
        for j in range(nz):
            for i in range(nx):
                q = (rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i])
                bm.faces.new(q if s else tuple(reversed(q)))
    a, b = grid
    for i in range(nx):                      # close the edges top and bottom, and the leech
        bm.faces.new((a[0][i], a[0][i + 1], b[0][i + 1], b[0][i]))
        bm.faces.new((b[nz][i], b[nz][i + 1], a[nz][i + 1], a[nz][i]))
    for j in range(nz):
        bm.faces.new((a[j][nx], a[j + 1][nx], b[j + 1][nx], b[j][nx]))
        bm.faces.new((b[j][0], b[j + 1][0], a[j + 1][0], a[j][0]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _pin_parts(D=0.80, draft=0.16, staff_above=1.30, segs=96):
    vinyl, scum, web, steel = P.M("MarkVinyl"), P.M("MarkScum"), P.M("CrewStraps"), P.M("Stainless")
    glass = P.M("WhitePlastic")
    R = D / 2
    zc = R - draft                                       # ball centre above the waterline
    # an inflated ball from two welded hemispheres: slightly oblate (the equator seam pulls in), with a flange there
    prof = []
    for i in range(49):
        a = -math.pi / 2 + math.pi * i / 48
        r = R * math.cos(a) * (1.0 - 0.012 * math.cos(a) ** 8)
        prof.append((max(0.0, r), zc + R * 0.97 * math.sin(a)))
    prof[0] = (0.0, prof[0][1])
    prof[-1] = (0.0, prof[-1][1])
    ball = G.lathe("ball", prof, vinyl, segs)
    G.finish(ball, 0)
    _slot_by_z(ball, 0.025, scum)
    flange = _flange_ring("equator", R * 0.985, zc, 0.012, 0.010, vinyl)
    # the staff runs through a sleeve on top and a collar underneath, with a lead weight hanging below
    zt = zc + R * 0.97
    zb = zc - R * 0.97
    sleeve = G.lathe("sleeve", [(0, 0), (0.060, 0), (0.060, 0.004), (0.024, 0.010), (0.022, 0.12), (0.0, 0.12)], vinyl, 40)
    sleeve.location = (0, 0, zt - 0.006)
    G.bake_xform(sleeve)
    staff = G.cyl("staff", (0, 0, zb - 0.45), (0, 0, staff_above), 0.0125, glass, 20)
    tip = G.lathe("staff_tip", [(0, 0), (0.0145, 0), (0.0145, 0.030), (0.010, 0.040), (0.0, 0.042)], P.M("BlackPlastic"), 20)
    tip.location = (0, 0, staff_above - 0.004)
    G.bake_xform(tip)
    weight = G.lathe("weight", [(0, 0), (0.035, 0), (0.040, 0.03), (0.040, 0.11), (0.030, 0.14), (0.0, 0.14)], P.M("Rubber"), 24)
    weight.location = (0, 0, zb - 0.62)
    G.bake_xform(weight)
    collar = G.lathe("collar", [(0, 0), (0.045, 0), (0.045, 0.012), (0.0, 0.012)], scum, 32)
    collar.location = (0, 0, zb - 0.010)
    G.bake_xform(collar)
    flag_w, flag_h = 0.45, 0.30                          # r3's larger flag tied with this one
    flag = _flag("flag", 0.0125, staff_above - 0.03, flag_w, flag_h, vinyl)
    clips = [_ring(f"flag_clip{k}", (0, 0, staff_above - 0.04 - k * (flag_h - 0.02)), 0.017, 0.0025, steel, plane="xy") for k in range(2)]
    # a lifting / anchor loop on the ball's flank (the anchor line takes the staff's foot on a real one)
    objs = [ball, flange, sleeve, staff, tip, weight, collar, flag] + clips
    socks = [("Top", (0, 0, staff_above + 0.04)), ("Anchor", (0, 0, zb - 0.62)), ("Waterline", (0, 0, 0)),
             ("Flag", (flag_w / 2, 0, staff_above - 0.03 - flag_h / 2))]
    return objs, socks


@P.part("PinBuoy", "course", "Start line pin end: 0.80 m inflatable orange ball with a fibreglass flag staff (1.3 m above the water) and an orange flag; origin on the waterline")
def pin_buoy(diameter=0.80):
    return P.done("PinBuoy", *_pin_parts(diameter))


# ------------------------------------------------------------------ the crew-overboard buoy: a Type IV horseshoe

def _horseshoe_path(W, L, band, n_arc=40, n_leg=10):
    """Centre line of the U, lying in XY: the closed bend toward +X, the open ends toward -X. W outer width (across Y),
    L outer length (along X), `band` the width of the foam band."""
    rc = (W - band) / 2                                  # centre-line radius of the bend
    xc = L / 2 - band / 2 - rc                           # bend centre
    x_end = -L / 2 + band / 2                            # the open ends' centres (their rounded ends reach -L/2)
    pts = []
    for i in range(n_leg + 1):                           # left leg, open end to the bend
        t = i / n_leg
        pts.append((x_end + (xc - x_end) * t, -rc, 0.0))
    for i in range(1, n_arc):                            # the bend
        a = -math.pi / 2 + math.pi * i / n_arc
        pts.append((xc + rc * math.cos(a), rc * math.sin(a), 0.0))
    for i in range(n_leg + 1):                           # right leg back to its open end
        t = i / n_leg
        pts.append((xc + (x_end - xc) * t, rc, 0.0))
    return pts, rc, xc, x_end


def _soft_section(w, t, n=28, p=2.6):
    """A foam-filled cover's section: a superellipse w wide (u) and t thick (v)."""
    out = []
    for i in range(n):
        a = TAU * i / n
        c, s = math.cos(a), math.sin(a)
        out.append((w / 2 * math.copysign(abs(c) ** (2 / p), c), t / 2 * math.copysign(abs(s) ** (2 / p), s)))
    return out


def _horseshoe_parts(W=0.610, L=0.585, T=0.100, band=0.150, float_depth=0.035):
    vinyl, web, refl, buckle = P.M("MOBVinyl"), P.M("CrewStraps"), P.M("CrewReflective"), P.M("CrewBuckle")
    path, rc, xc, x_end = _horseshoe_path(W, L, band)
    zc = T / 2 - float_depth                              # it floats flat, about a third under
    path = [(x, y, zc) for x, y, _ in path]
    body = G.sweep("cover", path, _soft_section(band, T), vinyl, cap=False, twist_up=(0, 0, 1))
    # round the open ends: half-domes (a lathe of the section's half, squashed to the section)
    ends = []
    for s in (-1, 1):
        dome = G.lathe(f"end{s}", [(0.0, 0.0)] + [(math.cos(math.pi / 2 * i / 10) ** 0.5, math.sin(math.pi / 2 * i / 10)) for i in range(11)], vinyl, 28)
        # unit dome along +Z; scale to the band (Y), the thickness (Z after the turn) and a 0.45-band reach (-X)
        m = (Matrix.Translation((x_end, s * rc, zc)) @ Matrix.Rotation(-math.pi / 2, 4, "Y")
             @ Matrix.Diagonal((T / 2 * 0.98, band / 2 * 0.98, band * 0.45, 1.0)))
        dome.matrix_world = m
        G.bake_xform(dome)
        ends.append(dome)
    # the cover's welded seam: a thin flange right round the outer and inner edge at mid thickness
    def offset_path(off):
        out = []
        for i, (x, y, z) in enumerate(path):
            a = path[max(i - 1, 0)]
            b = path[min(i + 1, len(path) - 1)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(tx, ty) or 1.0
            nx, ny = ty / ln, -tx / ln                   # right-hand normal in XY
            out.append((x + nx * off, y + ny * off, z))
        return out
    seams = []
    for k, off in enumerate((band / 2 - 0.003, -(band / 2 - 0.003))):
        sp = offset_path(off)
        sec = [(-0.005, -0.0025), (0.009 if off > 0 else 0.005, -0.0015), (0.009 if off > 0 else 0.005, 0.0015), (-0.005, 0.0025)]
        if off < 0:
            sec = [(-u, v) for u, v in sec]
        seams.append(G.sweep(f"seam{k}", sp, sec, vinyl, twist_up=(0, 0, 1)))
    # reflective tape: four patches wrapped over the top face (USCG / SOLAS practice), two on the bend, one per leg
    tapes = []
    spots = [(xc + rc * math.cos(a), rc * math.sin(a), a) for a in (math.radians(-35), math.radians(35))]
    spots += [(x_end + 0.12, -rc, -math.pi / 2), (x_end + 0.12, rc, math.pi / 2)]
    for k, (x, y, a) in enumerate(spots):
        tp = _soft_section(band * 1.012, T * 1.03, 28)
        top = [(u, v) for u, v in tp if v > T * 0.12]   # the upper part of the section, an arch over the top
        top = sorted(top, key=lambda q: q[0])
        sec = [(u, v) for u, v in top] + [(u, v - 0.0015) for u, v in reversed(top)]
        tang = (-math.sin(a), math.cos(a)) if k < 2 else (1.0, 0.0)
        p0 = (x - tang[0] * 0.025, y - tang[1] * 0.025, zc)
        p1 = (x + tang[0] * 0.025, y + tang[1] * 0.025, zc)
        tapes.append(G.sweep(f"tape{k}", [p0, p1], sec, refl, twist_up=(0, 0, 1)))
    # the web strap across the open end, with its snap: it hangs in a slight sag between the two legs' ends
    sx = x_end + 0.035
    y0 = rc - band * 0.40
    # a snug retaining strap (r3's slack belly read as a broken tail)
    strap_pts = [(sx - 0.015 * math.sin(math.pi * i / 16), -y0 + 2 * y0 * i / 16, zc + 0.012) for i in range(17)]
    strap = G.sweep("strap", strap_pts, [(-0.0125, -0.0012), (0.0125, -0.0012), (0.0125, 0.0012), (-0.0125, 0.0012)], web,
                    twist_up=(0, 0, 1))
    snap = G.lathe("snap", [(0, 0), (0.011, 0), (0.011, 0.004), (0.008, 0.007), (0.0, 0.007)], buckle, 24)
    snap.location = (sx - 0.015, 0.04, zc + 0.012 + 0.0012)
    G.bake_xform(snap)
    # stitched strap ends where they wrap the legs
    wraps = []
    for s in (-1, 1):
        wsec = _soft_section(band * 1.03, T * 1.06, 24)
        wraps.append(G.sweep(f"wrap{s}", [(sx - 0.0125, s * rc, zc), (sx + 0.0125, s * rc, zc)], wsec, web, twist_up=(0, 0, 1)))
    objs = [body] + ends + seams + tapes + [strap, snap] + wraps
    socks = [("Waterline", (0, 0, 0)), ("Strap", (sx, 0, zc + 0.012)), ("Bend", (L / 2, 0, zc))]
    return objs, socks


@P.part("HorseshoeBuoy", "safety", "US Type IV horseshoe buoy, 610 x 585 x 100 mm, faded yellow vinyl over foam, reflective patches, web strap and snap across the open end; floats flat, origin on the waterline")
def horseshoe_buoy():
    return P.done("HorseshoeBuoy", *_horseshoe_parts())
