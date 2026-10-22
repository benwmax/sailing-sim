"""Boat fidelity (pc/j22-detail, assembly 4): the mast's own gear as Bean's photos show it (mast-bottom-closeup,
mast-sheetsandhardware, mast-cunningham, mast-and-spreader, shroud-mounts, mast-boom-gooseneck-connector).
Replaces j22_details' mast step box, collar, exit plates, turning blocks, spreader roots and tips, chainplates and
turnbuckles:

- the mast step: a stainless base plate on the cabin top, the dark grey heel casting over it rising round the mast's
  foot with two halyard sheaves in its aft face, a hex bolt across, ring pins through its fore and aft ears;
- turning blocks round the step with perforated cheeks on their padeyes;
- the halyards' exit boxes on the mast's sides: a stainless plate, the sheave in its slot, four screws;
- the spreaders' roots (a saddle on the mast's side and a socket the spreader slides into, bolted) and their tips in
  white boots taped round the upper shroud;
- the chainplates: a rounded cover plate with four countersunk screws, the strap; closed-body turnbuckles on toggles,
  lock nuts, ribbed grey boots over the upper studs and swages, white tape at the toggles;
- the cunningham: a cam and fairlead block on a plate low on the mast's side, a block hung under the gooseneck, the line;
- the black tape band round the mast at the gooseneck.

The parts the bake reads keep their names and centres (Chainplate_<side>_strap's top: the shroud sockets;
SprTip_<side>_end: SpreaderTip), so no socket moves. Blender frame, as build_j22_hero.py. Sizes GUESS from the photos
and the class's hardware sizes (1/4 in turnbuckles, 29-40 mm blocks)."""
import math

import bmesh
from mathutils import Vector

import j22_details as D
from j22_boomgear import countersunk, plate_xy, rounded
from j22_geom import cyl, mesh_obj, tube
from j22_steering import hex_head, lathe, nylock, plate


def _pan(name, p, axis, mat, d=0.0085):
    """A pan-head screw standing out of p along axis."""
    return lathe(name, [(0.0, 0.0), (d / 2, 0.0), (d * 0.47, d * 0.18), (d * 0.3, d * 0.3), (0.0, d * 0.32)], p, axis, mat, 14)


def _loft(name, sections, mat, n=40):
    """A closed loft through rounded rectangles: sections (x, y, z, half_x, half_y), superellipse corners."""
    bm = bmesh.new()
    rings = []
    for x, y, z, hx, hy in sections:
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            c, s = math.cos(a), math.sin(a)
            # superellipse, exponent 4: a rectangle with generous corners
            r = (abs(c) ** 4 + abs(s) ** 4) ** -0.25
            ring.append(bm.verts.new((x + hx * r * c, y + hy * r * s, z)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)


def _fluted(name, p0, axis, length, r, mat, flutes=10, n=60, taper=0.85):
    """A ribbed PVC turnbuckle boot: flutes along its length, a domed top end."""
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    w = axis.cross(u)
    p0 = Vector(p0)
    bm = bmesh.new()
    rings = []
    hs = [0.0, 0.08, 0.5, 0.88, 0.96, 1.0]
    scale = [taper, 1.0, 1.0, 1.0, 0.8, 0.35]
    for h, sc in zip(hs, scale):
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            rr = r * sc * (1.0 + 0.07 * max(math.cos(flutes * a), 0.0) ** 0.5)
            ring.append(bm.verts.new(p0 + axis * (h * length) + (u * math.cos(a) + w * math.sin(a)) * rr))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)


# ------------------------------------------------------------------ mast step and turning blocks

def mast_step(mast_x, zm, M):
    """The step on the cabin top (photo mast-bottom-closeup). MastStep keeps its name (the base plate)."""
    out = []
    # the stainless base plate, rounded in plan, four countersunk screws at its corners
    out.append(plate_xy("MastStep", rounded(mast_x - 0.10, mast_x + 0.10, -0.06, 0.06, 0.02), zm - 0.005, zm + 0.008, M["Stainless"], bev=0.0015))
    for dx in (-0.082, 0.082):
        for dy in (-0.043, 0.043):
            out += countersunk(f"MastStep_scr{dx:+.2f}{dy:+.2f}", Vector((mast_x + dx, dy, zm + 0.008)), (0, 0, 1), 0.009, M["Stainless"])
    # the heel casting: a broad foot narrowing up round the mast's heel (the mast's section is 98 x 68 mm)
    out.append(_loft("MastStep_casting", [(mast_x, 0, zm + 0.008, 0.074, 0.048), (mast_x, 0, zm + 0.020, 0.072, 0.047),
                                          (mast_x, 0, zm + 0.060, 0.062, 0.044), (mast_x, 0, zm + 0.115, 0.056, 0.041),
                                          (mast_x, 0, zm + 0.122, 0.0535, 0.039)], M["CamBase"]))
    # its ears fore and aft on the plate, ring pins through them
    for sgn in (1, -1):
        ex = mast_x + sgn * 0.083
        out.append(plate(f"MastStep_ear{sgn}", rounded(ex - 0.012, ex + 0.012, zm + 0.008, zm + 0.030, 0.008), -0.012, 0.012, M["CamBase"], bev=0.002))
        out += D.clevis(f"MastStep_pin{sgn}", (ex, 0, zm + 0.020), (0, 1, 0), M, 0.036, 0.003)
    # the halyards' sheaves in the aft face, side by side in a dark pocket, on one axle
    sx, sz = mast_x - 0.064, zm + 0.042
    out.append(D.lbox("MastStep_pocket", (sx + 0.006, 0, sz), (0.022, 0.034, 0.05), M["BlackPlastic"], bev=0.004))
    for k, dy in enumerate((-0.0085, 0.0085)):
        out.append(cyl(f"MastStep_sheave{k}", (sx, dy - 0.0065, sz), (sx, dy + 0.0065, sz), 0.019, M["WhitePlastic"], 28))
        out.append(D.torus(f"MastStep_groove{k}", 0.0185, 0.0035, M["WhitePlastic"], 28, 8))
        out[-1].matrix_world = D.frame((sx, dy, sz), (1, 0, 0), (0, 1, 0))
    for sgn in (1, -1):
        out.append(plate(f"MastStep_cheek{sgn}", [(sx + 0.03, sz - 0.03), (sx - 0.008, sz - 0.03), (sx - 0.024, sz - 0.012), (sx - 0.022, sz + 0.012),
                                                 (sx - 0.004, sz + 0.03), (sx + 0.03, sz + 0.04)],
                         min(sgn * 0.0175, sgn * 0.026), max(sgn * 0.0175, sgn * 0.026), M["CamBase"], bev=0.002))
    out.append(cyl("MastStep_axle", (sx, -0.028, sz), (sx, 0.028, sz), 0.0035, M["Stainless"], 12))
    for sgn in (1, -1):
        out.append(lathe(f"MastStep_axlehead{sgn}", [(0.0, 0.0), (0.006, 0.0), (0.0055, 0.002), (0.0, 0.0025)], Vector((sx, sgn * 0.026, sz)), (0, sgn, 0), M["Stainless"], 14))
    # the bolt across the casting through the mast's heel
    out.append(cyl("MastStep_bolt", (mast_x + 0.010, -0.047, zm + 0.085), (mast_x + 0.010, 0.047, zm + 0.085), 0.004, M["Stainless"], 12))
    out += hex_head("MastStep_bolthead", Vector((mast_x + 0.010, 0.043, zm + 0.085)), (0, 1, 0), 0.013, 0.006, M["Stainless"])
    out += nylock("MastStep_boltnut", Vector((mast_x + 0.010, -0.043, zm + 0.085)), (0, -1, 0), 0.013, M["Stainless"])
    return out


def cheek_block(name, at, axle, toward, M, sheave_d=0.035, padeye=None):
    """A ball-bearing block with perforated cheeks (photos mast-sheetsandhardware, mast-bottom-closeup): round black
    cheeks with a ring of lightening holes showing the grey sheave, a stainless centre rivet each side, a swivel head and
    shackle toward `toward`, and its padeye on the deck under it (padeye = (point on the deck, its normal))."""
    R = sheave_d * 0.68
    W = sheave_d * 0.5
    ax = Vector(axle).normalized()
    up = Vector(toward).normalized()
    up = (up - ax * up.dot(ax)).normalized()
    M4 = D.frame(at, up, ax)           # local X toward the head, local Z along the axle
    objs = []
    for sgn in (-1, 1):
        objs.append(cyl(f"{name}_cheek{sgn}", (0, 0, sgn * W * 0.32), (0, 0, sgn * W * 0.5), R, M["BlackPlastic"], 32))
        objs.append(cyl(f"{name}_rivet{sgn}", (0, 0, sgn * W * 0.5), (0, 0, sgn * (W * 0.5 + 0.0016)), 0.0045, M["Stainless"], 14))
        for k in range(6):
            a = 2 * math.pi * (k + 0.5) / 6
            c = (math.cos(a) * R * 0.6, math.sin(a) * R * 0.6)
            objs.append(cyl(f"{name}_hole{sgn}{k}", (c[0], c[1], sgn * W * 0.5), (c[0], c[1], sgn * (W * 0.5 + 0.0003)), R * 0.17, M["SheaveGrey"], 12))
        objs.append(D.lbox(f"{name}_head{sgn}", (R * 0.98, 0, sgn * W * 0.41), (R * 0.55, R * 0.8, W * 0.18), M["BlackPlastic"], bev=0.002))
    objs.append(cyl(f"{name}_sheave", (0, 0, -W * 0.30), (0, 0, W * 0.30), sheave_d / 2, M["SheaveGrey"], 28))
    D._place(objs, M4)
    head = Vector(at) + up * R * 1.3
    objs.append(lathe(f"{name}_swivel", [(0.0, 0.0), (0.0045, 0.0), (0.0045, 0.008), (0.0035, 0.010), (0.0, 0.011)], Vector(at) + up * R * 1.05, up, M["Stainless"], 14))
    objs += D.shackle(f"{name}_sh", head + up * 0.004, up, M, size=0.8)
    if padeye is not None:
        objs += D.padeye(f"{name}_pad", padeye[0], padeye[1], M)
    return objs


def turning_blocks(mast_x, zm, M):
    """Two blocks beside the step's aft side, on padeyes (Bean's feedback 2, the Harken J/22 layout: the halyards turn on
    the step's own sheaves; these take the control lines). It had been six."""
    out = []
    for k, dy in enumerate((-0.11, 0.11)):
        out += cheek_block(f"Turn_{k}", (mast_x - 0.12, dy, zm + 0.058), (1, 0, 0), (0, 0, -1), M, padeye=((mast_x - 0.12, dy, zm), (0, 0, 1)))
    return out


# ------------------------------------------------------------------ on the mast

def exit_box(name, at, side, M):
    """A halyard's exit box on the mast's side: a stainless plate (name keeps the plate), the sheave in a dark slot,
    four pan-head screws. at = the plate's centre on the mast's side face."""
    p = Vector(at)
    y0 = side * 0.0335
    y1 = side * 0.0365
    out = [plate(name, rounded(p.x - 0.018, p.x + 0.018, p.z - 0.058, p.z + 0.058, 0.012), min(y0, y1), max(y0, y1), M["Stainless"], bev=0.0012)]
    yo = side * 0.0367
    out.append(plate(f"{name}_slot", rounded(p.x - 0.0055, p.x + 0.0055, p.z - 0.034, p.z + 0.030, 0.0055), min(yo, yo + side * 0.0004), max(yo, yo + side * 0.0004), M["BlackPlastic"], bev=0.0))
    out.append(cyl(f"{name}_sheave", (p.x, yo, p.z + 0.006), (p.x, yo + side * 0.0012, p.z + 0.006), 0.0045, M["SheaveGrey"], 16))
    for dz in (-0.046, 0.046):
        for dx in (-0.009, 0.009):
            out.append(_pan(f"{name}_scr{dz:+.3f}{dx:+.3f}", Vector((p.x + dx, side * 0.0365, p.z + dz)), (0, side, 0), M["Stainless"], 0.0065))
    return out


def tape_band(name, x, z, half_fa, half_at, height, M, proud=0.0022):
    """Black rigging tape round the mast (photos mast-boom-gooseneck-connector, mast-cunningham). The game bends the mast
    in its material (M_BoatMast) and not its fittings, so the band stands a little proud and the caller centres it on the
    mast's resting bend."""
    bm = bmesh.new()
    n = 48
    rings = []
    for h in (z - height / 2, z + height / 2):
        rings.append([bm.verts.new((x + (half_fa + proud) * math.cos(2 * math.pi * k / n), (half_at + proud) * math.sin(2 * math.pi * k / n), h)) for k in range(n)])
    for k in range(n):
        bm.faces.new((rings[0][k], rings[0][(k + 1) % n], rings[1][(k + 1) % n], rings[1][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, M["BlackPlastic"])          # black electrical tape (the rig tape at the turnbuckles is white)
    s = ob.modifiers.new("solid", "SOLIDIFY")
    s.thickness = 0.0006
    return [ob]


def spreader_root(name, mast_pt, tip, side, M):
    """The spreader's root: a cast saddle on the mast's side with four rivets, a socket the spreader slides into toward
    its tip, a through-bolt down the socket."""
    p = Vector(mast_pt)
    d = (Vector(tip) - Vector((p.x, side * 0.035, p.z))).normalized()
    y0, y1 = side * 0.0335, side * 0.040
    out = [plate(f"{name}_root", rounded(p.x - 0.040, p.x + 0.022, p.z - 0.045, p.z + 0.045, 0.012), min(y0, y1), max(y0, y1), M["CastAlu"], bev=0.002)]
    for dx in (-0.030, 0.012):
        for dz in (-0.034, 0.034):
            out.append(lathe(f"{name}_riv{dx:+.3f}{dz:+.3f}", [(0.0, 0.0), (0.0035, 0.0), (0.003, 0.0012), (0.0, 0.0016)], Vector((p.x + dx, y1, p.z + dz)), (0, side, 0), M["Stainless"], 12))
    s0 = Vector((p.x - 0.010, y1, p.z))
    out.append(lathe(f"{name}_socket", [(0.0, 0.0), (0.019, 0.0), (0.021, 0.006), (0.019, 0.055), (0.017, 0.060), (0.0, 0.060)], s0, d, M["CastAlu"], 24))
    b = s0 + d * 0.038
    out.append(cyl(f"{name}_bolt", b - Vector((0, 0, 0.028)), b + Vector((0, 0, 0.028)), 0.003, M["Stainless"], 10))
    out += hex_head(f"{name}_bolthead", b + Vector((0, 0, 0.021)), (0, 0, 1), 0.010, 0.005, M["Stainless"])
    out += nylock(f"{name}_boltnut", b - Vector((0, 0, 0.021)), (0, 0, -1), 0.010, M["Stainless"])
    return out


def spreader_tip(name, tip, along, M):
    """The tip: the end fitting clamping the upper shroud (`{name}_end`: the SpreaderTip socket), inside a white boot,
    white tape wound round the shroud above and below so nothing chafes the sail (photo mast-and-spreader)."""
    a = Vector(along).normalized()
    t = Vector(tip)
    out = [cyl(f"{name}_end", t - a * 0.03, t, 0.011, M["CastAlu"], 14)]
    out.append(lathe(f"{name}_boot", [(0.0, 0.0), (0.0125, 0.0), (0.0175, 0.012), (0.018, 0.075), (0.0165, 0.088), (0.011, 0.096), (0.0, 0.099)],
                     t - a * 0.080, a, M["WhitePlastic"], 28))
    out.append(cyl(f"{name}_tape", t + Vector((0, 0, -0.045)), t + Vector((0, 0, 0.045)), 0.0065, M["WhitePlastic"], 16))
    return out


# ------------------------------------------------------------------ chainplates and turnbuckles

def chainplate(name, at, M, normal=(0, 0, 1), along=(1, 0, 0), span=0.032):
    """Cover plate and strap through the deck (photo shroud-mounts). The strap keeps its name and extent (its top's
    centre is the shroud sockets'); the cover is rounded with four countersunk screws."""
    n = Vector(normal).normalized()
    M4 = D.frame(at, along, n)
    c = max(0.07, span + 0.04)
    objs = [plate_xy(f"{name}_cover", rounded(-c / 2, c / 2, -0.016, 0.016, 0.008), 0.0, 0.0035, M["Stainless"], bev=0.0012),
            plate(f"{name}_strap", rounded(-span / 2, span / 2, 0.0025, 0.0575, 0.010), -0.0024, 0.0024, M["Stainless"], bev=0.0008)]
    D._place(objs, M4)
    for dx in (-c / 2 + 0.008, c / 2 - 0.008):
        for dy in (-0.0085, 0.0085):
            objs += countersunk(f"{name}_scr{dx:+.3f}{dy:+.3f}", M4 @ Vector((dx, dy, 0.0035)), n, 0.007, M["Stainless"])
    return objs


def turnbuckle(name, base, wire_dir, M, length=0.22):
    """A toggle on the chainplate, a closed-body turnbuckle (chrome tube, tapered ends, lock nuts), the upper stud and
    swage inside a ribbed grey boot, white tape over the toggle. Returns (objects, the wire's start)."""
    d = Vector(wire_dir).normalized()
    p = Vector(base)
    side = d.orthogonal().normalized()
    M4 = D.frame(p, side, d)
    objs = []
    # toggle: two rounded cheeks round the strap, a clevis pin through, a knuckle above
    for sgn in (-1, 1):
        objs.append(D._place([plate(f"{name}_tog{sgn}", rounded(-0.007, 0.007, -0.006, 0.026, 0.006), sgn * 0.0045 - 0.0013, sgn * 0.0045 + 0.0013, M["Stainless"])],
                             D.frame(p, side, d))[0])
    objs += D.clevis(f"{name}_tpin", p, M4.to_3x3() @ Vector((0, 1, 0)), M, 0.018, 0.0025)
    objs.append(lathe(f"{name}_knuckle", [(0.0, 0.0), (0.0062, 0.0), (0.0062, 0.010), (0.0045, 0.014), (0.0, 0.014)], p + d * 0.022, d, M["Stainless"], 16))
    # the lower stud, then the body
    s0 = p + d * 0.036
    objs.append(cyl(f"{name}_stud_lo", s0, s0 + d * 0.016, 0.0032, M["Chrome"], 12))
    objs += hex_head(f"{name}_nut_lo", s0 + d * 0.004, d, 0.011, 0.005, M["Chrome"], washer=False)
    b0 = s0 + d * 0.016
    objs.append(lathe(f"{name}_body", [(0.0, 0.0), (0.0046, 0.0), (0.0062, 0.010), (0.0062, 0.070), (0.0046, 0.080), (0.0, 0.080)], b0, d, M["Chrome"], 20))
    # the scale's rings engraved on the body (photo: numbered)
    for k in range(6):
        objs.append(lathe(f"{name}_mark{k}", [(0.00625, 0.0), (0.0064, 0.0), (0.0064, 0.0008), (0.00625, 0.0008)], b0 + d * (0.016 + 0.009 * k), d, M["SheaveGrey"], 20))
    b1 = b0 + d * 0.080
    objs.append(cyl(f"{name}_stud_hi", b1, b1 + d * 0.030, 0.0032, M["Chrome"], 12))
    objs += hex_head(f"{name}_nut_hi", b1, d, 0.011, 0.005, M["Chrome"], washer=False)
    sw0 = b1 + d * 0.030
    objs.append(cyl(f"{name}_swage", sw0, sw0 + d * 0.050, 0.0042, M["Chrome"], 14, r1=0.0024))
    # the ribbed boot over the upper stud and swage, its screw; white tape at the toggle
    objs.append(_fluted(f"{name}_boot", b1 + d * 0.004, d, 0.088, 0.0125, M["SheaveGrey"]))
    objs.append(_pan(f"{name}_bootscr", b1 + d * 0.072 + side * 0.0128, side, M["Stainless"], 0.006))
    objs.append(cyl(f"{name}_tape_lo", p - d * 0.006, p + d * 0.016, 0.0105, M["WhitePlastic"], 18))
    return objs, sw0 + d * 0.050


# ------------------------------------------------------------------ cunningham

def cunningham(mast_x, zm, boom_z, aft_face, M):
    """The cunningham (photo mast-cunningham): on the mast's port side low down, a plate carrying a fairlead block and a
    cam cleat under it; the line runs up to a block hung under the gooseneck from a strop and back down to the plate."""
    out, lines = [], []
    side = 1                             # port (Blender +y)
    zc = zm + 0.24
    xp = mast_x + 0.004
    y0 = side * 0.0335
    out.append(plate("Cunn_plate", rounded(xp - 0.022, xp + 0.022, zc - 0.075, zc + 0.065, 0.01), min(y0, y0 + side * 0.003), max(y0, y0 + side * 0.003), M["Stainless"], bev=0.001))
    for dz in (-0.062, 0.052):
        for dx in (-0.012, 0.012):
            out.append(_pan(f"Cunn_scr{dz:+.3f}{dx:+.3f}", Vector((xp + dx, side * 0.0365, zc + dz)), (0, side, 0), M["Stainless"], 0.0065))
    # the fairlead block over the cam, its axle along the mast's side face's normal (the line runs up and down)
    out += D.block("Cunn_lead", (xp, side * 0.047, zc + 0.030), (0, side, 0), (0, 0, 1), M, 0.029, with_shackle=False)
    out += D.cam_cleat("Cunn_cam", (xp, side * 0.0365, zc - 0.030), (0, side, 0), (0, 0, 1), M, 0.055)
    # the block hung under the gooseneck from a strop round the tang
    hb = Vector((aft_face(boom_z) - 0.040, 0.010, boom_z - 0.16))
    out += D.block("Cunn_block", hb, (0, 1, 0), (0, 0, 1), M, 0.029)
    strop_top = Vector((aft_face(boom_z) - 0.030, 0.0, boom_z - 0.030))
    lines.append(tube("Cunn_strop", [tuple(hb + Vector((0, 0, 0.035))), tuple(strop_top + Vector((-0.004, 0.006, -0.03))), tuple(strop_top)], 0.003, M["SheaveGrey"], smooth_path=True))
    # the line: from the cam's tail up through the lead to the hanging block, round it, back down to the plate's dead end
    lead_top = Vector((xp, side * 0.047, zc + 0.030 + 0.016))
    for k, dy in enumerate((-0.006, 0.006)):
        top = hb + Vector((0, dy, -0.018))
        lo = lead_top if k == 0 else Vector((xp + 0.008, side * 0.040, zc + 0.062))
        lines.append(tube(f"Cunn_line{k}", [tuple(lo), tuple(lo + (top - lo) * 0.5 + Vector((0.004, 0.0, 0.0))), tuple(top)], 0.0035, M["CunnLine"], smooth_path=True))
    tail0 = Vector((xp, side * 0.040, zc - 0.060))
    lines.append(tube("Cunn_tail", [tuple(tail0), tuple(tail0 + Vector((0.02, side * 0.03, -0.10))), tuple(tail0 + Vector((0.05, side * 0.08, -0.17)))],
                      0.0035, M["CunnLine"], smooth_path=True))
    return out + lines
