"""The building parts kit (Track E): every standard house feature as a reusable part at real size, mapped onto the
shared trim sheet, so one good window improves every house on the lake.

Each builder returns one joined part (hk_core.part) and is registered in PARTS with its size-card row (sizes.json) and
triangle budget. Openings (windows, doors, garage doors) have their origin at the bottom centre of the opening on the
wall plane; the frame's outer face sits on y = 0 and the part runs back into -Y, so the house builder can set it back
by its reveal. Wall-mounted parts (lights, meters, vents) mount at their back face centre, +Y out. Roof parts mount on
the roof at their base centre, +Z up (the house builder tilts nothing: these parts are plumb, like the real ones).

Glass is one pane per opening light (hk_core.pane), with muntins as Trim bars 6 mm in front of it.
"""
import math

from mathutils import Vector

import hk_core as K
from hk_core import G, DOOR, FIXED, GARAGE, METAL, SASH, SHUTTER, TRIM_S, box, quad_xz

PARTS = {}


def register(name, budget, row=None, kind="opening"):
    def deco(fn):
        PARTS[name] = {"build": fn, "budget": budget, "row": row or name, "kind": kind}
        return fn
    return deco


# ------------------------------------------------------------------ shared window pieces

def grille(name, x0, x1, z0, z1, y, cols, rows, bar=0.016, depth=0.008, band="vinyl", paint=SASH):
    """Muntin bars over a pane: cols x rows lights."""
    out = []
    for i in range(1, cols):
        x = x0 + (x1 - x0) * i / cols
        out.append(K.trim(box(f"{name}_v{i}", x - bar / 2, x + bar / 2, y, y + depth, z0, z1), band, paint))
    for j in range(1, rows):
        z = z0 + (z1 - z0) * j / rows
        out.append(K.trim(box(f"{name}_h{j}", x0, x1, y, y + depth, z - bar / 2, z + bar / 2), band, paint))
    return out


def sash(name, x0, x1, z0, z1, y0, y1, rail=0.045, bottom=None, band="vinyl", paint=SASH, seed=0.5, grid=(1, 1),
         obscure=0, door=0, bar=0.016):
    """A sash: four rails around one pane, the glass 15 mm behind the rails' front, optional grille in front."""
    out = [K.trim(b, band, paint) for b in K.ring_frame(name, x0, x1, z0, z1, rail, y0, y1, bottom)]
    gy = (y0 + y1) * 0.5
    bw = bottom if bottom is not None else rail
    out.append(K.pane(quad_xz(f"{name}_glass", x0 + rail, x1 - rail, z0 + bw, z1 - rail, gy), seed, obscure, door))
    if grid != (1, 1):
        out += grille(f"{name}_gr", x0 + rail, x1 - rail, z0 + bw, z1 - rail, y1 - 0.004, grid[0], grid[1], bar, 0.006, band, paint)
    return out


def window_frame(name, w, h, d, band="vinyl", paint=SASH, fw=0.05, sill_out=0.025):
    """The outer frame (nailing-fin-less, as seen): jambs, head, and a sloped sill that sheds water."""
    out = [K.trim(b, band, paint) for b in K.ring_frame(name, -w / 2, w / 2, 0.0, h, fw, -d, 0.0)]
    # sloped sill nose in front of the bottom rail
    import bmesh
    bm = bmesh.new()
    pts = [(-w / 2 - 0.01, 0.0, 0.0), (w / 2 + 0.01, 0.0, 0.0), (w / 2 + 0.01, sill_out, -0.012), (-w / 2 - 0.01, sill_out, -0.012),
           (-w / 2 - 0.01, 0.0, fw * 0.55), (w / 2 + 0.01, 0.0, fw * 0.55), (w / 2 + 0.01, sill_out, 0.006), (-w / 2 - 0.01, sill_out, 0.006)]
    v = [bm.verts.new(p) for p in pts]
    for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([v[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out.append(K.trim(G.mesh_obj(f"{name}_sill", bm), band, paint))
    return out


def screen(name, x0, x1, z0, z1, y):
    """A half screen: a thin aluminium frame and the mesh (screen band, alpha 0.45)."""
    out = [K.trim(b, "aluminium", SASH) for b in K.ring_frame(name, x0, x1, z0, z1, 0.012, y, y + 0.008)]
    out.append(K.trim(quad_xz(f"{name}_mesh", x0 + 0.012, x1 - 0.012, z0 + 0.012, z1 - 0.012, y + 0.004), "screen"))
    return out


def single_hung(name, w, h, d=0.08, grid=(3, 2), band="vinyl", paint=SASH, seed=0.5, with_screen=True, x=0.0):
    fw = 0.05
    out = window_frame(name, w, h, d, band, paint, fw)
    ix0, ix1, iz0, iz1 = -w / 2 + fw + x, w / 2 - fw + x, fw, h - fw
    if x:
        for o in out:
            o.location.x += x
            G.bake_xform(o)
    mid = (iz0 + iz1) / 2
    # lower sash in front (y nearer the face), upper sash behind; they overlap at the meeting rail
    out += sash(f"{name}_lo", ix0, ix1, iz0, mid + 0.02, -0.050, -0.018, 0.045, 0.06, band, paint, seed, grid)
    out += sash(f"{name}_up", ix0, ix1, mid - 0.02, iz1, -0.075, -0.045, 0.045, None, band, paint, seed, grid)
    if with_screen:
        out += screen(f"{name}_scr", ix0 + 0.004, ix1 - 0.004, iz0 + 0.004, mid + 0.016, -0.016)
    return out


# ------------------------------------------------------------------ windows (8)

@register("WinSingleHung3050", 1400)
def win_3050(name="WinSingleHung3050", grid=(3, 2), seed=0.31):
    s = K.SIZES["WinSingleHung3050"]
    return K.part(name, single_hung(name, s["w"], s["h"], grid=grid, seed=seed),
                  {"ShutterL": (-s["w"] / 2 - 0.02, 0.0, 0.0), "ShutterR": (s["w"] / 2 + 0.02, 0.0, 0.0)})


@register("WinSingleHung3060", 1400)
def win_3060(name="WinSingleHung3060", grid=(2, 2), seed=0.47):
    s = K.SIZES["WinSingleHung3060"]
    return K.part(name, single_hung(name, s["w"], s["h"], grid=grid, seed=seed),
                  {"ShutterL": (-s["w"] / 2 - 0.02, 0.0, 0.0), "ShutterR": (s["w"] / 2 + 0.02, 0.0, 0.0)})


@register("WinTwin3050", 2600)
def win_twin(name="WinTwin3050", seed=0.12):
    s = K.SIZES["WinSingleHung3050"]
    w1, mull = s["w"], 0.052
    out = single_hung(name + "_a", w1, s["h"], grid=(3, 2), seed=seed, x=-(w1 + mull) / 2)
    out += single_hung(name + "_b", w1, s["h"], grid=(3, 2), seed=seed, x=(w1 + mull) / 2)
    out.append(K.trim(box(name + "_mull", -mull / 2 - 0.002, mull / 2 + 0.002, -0.08, 0.004, 0.0, s["h"]), "vinyl", SASH))
    W = 2 * w1 + mull
    return K.part(name, out, {"ShutterL": (-W / 2 - 0.02, 0, 0), "ShutterR": (W / 2 + 0.02, 0, 0)})


@register("WinPicture6050", 900)
def win_picture(name="WinPicture6050", seed=0.66):
    s = K.SIZES["WinPicture6050"]
    w, h = s["w"], s["h"]
    out = window_frame(name, w, h, 0.08)
    out += sash(name + "_fix", -w / 2 + 0.05, w / 2 - 0.05, 0.05, h - 0.05, -0.06, -0.025, 0.035, None, seed=seed)
    return K.part(name, out, {"ShutterL": (-w / 2 - 0.02, 0, 0), "ShutterR": (w / 2 + 0.02, 0, 0)})


@register("WinSlider6040", 900)
def win_slider(name="WinSlider6040", seed=0.22):
    """1970s horizontal slider in dark bronze aluminium: thin frame, two panes side by side, the left one sliding."""
    s = K.SIZES["WinSlider6040"]
    w, h = s["w"], s["h"]
    out = window_frame(name, w, h, 0.07, "bronze", FIXED, fw=0.032, sill_out=0.012)
    ix0, ix1, iz0, iz1 = -w / 2 + 0.032, w / 2 - 0.032, 0.032, h - 0.032
    out += sash(name + "_l", ix0, 0.02, iz0, iz1, -0.035, -0.012, 0.028, None, "bronze", FIXED, seed)
    out += sash(name + "_r", -0.02, ix1, iz0, iz1, -0.058, -0.035, 0.028, None, "bronze", FIXED, seed)
    out += screen(name + "_scr", 0.0, ix1 - 0.004, iz0 + 0.004, iz1 - 0.004, -0.010)
    return K.part(name, out, {"ShutterL": (-w / 2 - 0.02, 0, 0), "ShutterR": (w / 2 + 0.02, 0, 0)})


@register("WinSmall2030", 700)
def win_small(name="WinSmall2030", seed=0.91):
    s = K.SIZES["WinSmall2030"]
    w, h = s["w"], s["h"]
    out = window_frame(name, w, h, 0.07)
    out += sash(name + "_fix", -w / 2 + 0.05, w / 2 - 0.05, 0.05, h - 0.05, -0.055, -0.022, 0.04, None, seed=seed, obscure=1)
    return K.part(name, out)


@register("WinCasement2470", 900)
def win_casement(name="WinCasement2470", seed=0.58):
    """Modern tall casement, black frame, a fixed transom-height bar at two thirds."""
    s = K.SIZES["WinCasement2470"]
    w, h = s["w"], s["h"]
    out = window_frame(name, w, h, 0.09, "black_iron", FIXED, fw=0.045, sill_out=0.015)
    zb = h * 0.68
    out += sash(name + "_lo", -w / 2 + 0.045, w / 2 - 0.045, 0.045, zb, -0.06, -0.02, 0.05, None, "black_iron", FIXED, seed)
    out += sash(name + "_up", -w / 2 + 0.045, w / 2 - 0.045, zb, h - 0.045, -0.06, -0.02, 0.04, None, "black_iron", FIXED, seed)
    return K.part(name, out)


@register("WinArchTop3060", 2600)
def win_arch(name="WinArchTop3060", seed=0.74):
    """3060 single-hung under a half-round transom with a sunburst grille (1990s two-storey brick)."""
    s = K.SIZES["WinSingleHung3060"]
    w, h = s["w"], s["h"]
    out = single_hung(name, w, h, grid=(1, 1), seed=seed)
    r_out = w / 2
    z0 = h
    segs = 24
    # arched frame: a swept band of the frame's section along the half circle
    path = [(r_out * math.cos(math.pi * i / segs), 0.0, z0 + r_out * math.sin(math.pi * i / segs)) for i in range(segs + 1)]
    inner = [(0.0, -0.08), (0.05, -0.08), (0.05, 0.0), (0.0, 0.0)]
    ring = []
    for i in range(segs):
        a0, a1 = math.pi * i / segs, math.pi * (i + 1) / segs
        for (ra, rb) in ((r_out - 0.05, r_out),):
            import bmesh
            bm = bmesh.new()
            q = []
            for a in (a0, a1):
                for r in (ra, rb):
                    for y in (-0.08, 0.0):
                        q.append(bm.verts.new((r * math.cos(a), y, z0 + r * math.sin(a))))
            # q index: a(0/1)*4 + r(0/1)*2 + y(0/1)
            idx = lambda a, r, y: q[a * 4 + r * 2 + y]
            for f in ((idx(0, 0, 1), idx(0, 1, 1), idx(1, 1, 1), idx(1, 0, 1)),      # front
                      (idx(0, 1, 0), idx(0, 1, 1), idx(1, 1, 1), idx(1, 1, 0)),      # outer
                      (idx(0, 0, 0), idx(1, 0, 0), idx(1, 0, 1), idx(0, 0, 1))):     # inner
                bm.faces.new(f)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            ring.append(K.trim(G.mesh_obj(f"{name}_arc{i}", bm), "vinyl", SASH))
    out += ring
    # half-round glass as one fan pane, and the sunburst bars
    import bmesh
    bm = bmesh.new()
    c = bm.verts.new((0.0, -0.05, z0))
    rim = [bm.verts.new(((r_out - 0.05) * math.cos(math.pi * i / segs), -0.05, z0 + (r_out - 0.05) * math.sin(math.pi * i / segs))) for i in range(segs + 1)]
    for i in range(segs):
        f = bm.faces.new((c, rim[i + 1], rim[i]))
    for f in bm.faces:
        f.normal_update()
        if f.normal.y < 0:
            f.normal_flip()
    out.append(K.pane(G.mesh_obj(name + "_arcglass", bm), seed))
    for k in range(1, 4):
        a = math.pi * k / 4
        L = r_out - 0.05
        bar = G.box(f"{name}_ray{k}", (0.0, 0.0, L / 2), (0.016, 0.006, L))
        bar.matrix_world = G.along((0.0, -0.04, z0), (math.cos(a), 0.0, math.sin(a)), up=(0, 1, 0))
        G.bake_xform(bar)
        out.append(K.trim(bar, "vinyl", SASH))
    out.append(K.trim(box(name + "_spring", -w / 2 + 0.05, w / 2 - 0.05, -0.08, 0.0, z0 - 0.01, z0 + 0.03), "vinyl", SASH))
    return K.part(name, out)


# ------------------------------------------------------------------ doors (5)

def door_frame(name, w, h, d=0.14, casing=True):
    """Jambs and head (trim colour), aluminium threshold."""
    out = [K.trim(box(name + "_jl", -w / 2 - 0.02, -w / 2, -d, 0.0, 0.0, h), "paint_smooth", TRIM_S),
           K.trim(box(name + "_jr", w / 2, w / 2 + 0.02, -d, 0.0, 0.0, h), "paint_smooth", TRIM_S),
           K.trim(box(name + "_hd", -w / 2 - 0.02, w / 2 + 0.02, -d, 0.0, h, h + 0.02), "paint_smooth", TRIM_S),
           K.trim(box(name + "_th", -w / 2, w / 2, -d, 0.03, 0.0, 0.018), "bronze")]
    return out


def raised_panel(name, x0, x1, z0, z1, y, rise=0.012, bevel=0.035, paint=DOOR, band="paint_grain"):
    """A raised field: a flat panel with bevelled edges standing proud of the stiles by `rise`."""
    outline = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    ob = G.prism(name, [(p[0], p[1]) for p in outline], 0.0, rise, taper=1.0)
    # taper the top face inward by the bevel width to make the raised field's slope
    me = ob.data
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    for v in me.vertices:
        if v.co.z > rise * 0.5:
            v.co.x = cx + (v.co.x - cx) * max(0.0, 1 - 2 * bevel / max(x1 - x0, 1e-6))
            v.co.y = cz + (v.co.y - cz) * max(0.0, 1 - 2 * bevel / max(z1 - z0, 1e-6))
    # prism is in XY with Z up: turn it so it stands on the wall plane facing +Y
    for v in me.vertices:
        x, zz, yy = v.co.x, v.co.y, v.co.z
        v.co = Vector((x, y + yy, zz))
    me.update()
    from mathutils import Vector as V  # noqa
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return K.trim(ob, band, paint)


def handleset(name, x, z, y, brass=True):
    out = [K.trim(box(name + "_rose", x - 0.03, x + 0.03, y, y + 0.012, z - 0.13, z + 0.06), "black_iron")]
    knob = G.lathe(name + "_knob", [(0, 0), (0.012, 0), (0.012, 0.03), (0.03, 0.045), (0.028, 0.065), (0, 0.068)], segs=16)
    knob.matrix_world = G.along((x, y + 0.012, z), (0, 1, 0))
    G.bake_xform(knob)
    out.append(K.cell(knob, "kick_plate") if brass else K.trim(knob, "black_iron"))
    dead = G.cyl(name + "_dead", (x, y + 0.012, z + 0.10), (x, y + 0.03, z + 0.10), 0.03, segs=16)
    out.append(K.cell(dead, "kick_plate") if brass else K.trim(dead, "black_iron"))
    return out


@register("DoorSixPanel", 2400)
def door_six(name="DoorSixPanel"):
    s = K.SIZES["DoorSixPanel"]
    w, h, t = s["w"], s["h"], s["d"]
    y = -0.06
    out = door_frame(name, w, h)
    out.append(K.trim(box(name + "_slab", -w / 2, w / 2, y - t, y, 0.018, h), "paint_grain", DOOR))
    st, rl = 0.12, 0.12
    cols = [(-w / 2 + st, -0.03), (0.03, w / 2 - st)]
    rows = [(0.018 + 0.23, 0.018 + 0.23 + 0.68), (0.018 + 0.23 + 0.68 + 0.20, h - 0.12 - 0.33), (h - 0.12 - 0.27, h - rl)]
    for i, (x0, x1) in enumerate(cols):
        for j, (z0, z1) in enumerate(rows):
            out.append(raised_panel(f"{name}_p{i}{j}", x0, x1, z0, z1, y, 0.016, 0.035))
    out += handleset(name + "_hs", w / 2 - 0.07, 0.96, y)
    return K.part(name, out, {"LightL": (-w / 2 - 0.25, 0, 1.75), "LightR": (w / 2 + 0.25, 0, 1.75)})


@register("DoorCraftsman", 2400)
def door_craftsman(name="DoorCraftsman", seed=0.4):
    s = K.SIZES["DoorCraftsman"]
    w, h, t = s["w"], s["h"], s["d"]
    y = -0.06
    out = door_frame(name, w, h)
    out.append(K.trim(box(name + "_slab", -w / 2, w / 2, y - t, y, 0.018, h), "cedar"))
    # three lites at the top
    lz0, lz1 = h - 0.12 - 0.50, h - 0.12
    lw = (w - 2 * 0.12 - 2 * 0.03) / 3
    for k in range(3):
        x0 = -w / 2 + 0.12 + k * (lw + 0.03)
        out.append(K.pane(quad_xz(f"{name}_lite{k}", x0, x0 + lw, lz0, lz1, y + 0.002), seed, 0, 1))
    for k in range(4):   # stops round the lites
        x = -w / 2 + 0.12 + k * (lw + 0.03) - (0.03 if k else 0.0)
        out.append(K.trim(box(f"{name}_mv{k}", x, x + 0.03, y, y + 0.012, lz0, lz1), "cedar"))
    # the dentil shelf under the lites
    out.append(K.trim(box(name + "_shelf", -w / 2 + 0.08, w / 2 - 0.08, y, y + 0.05, lz0 - 0.05, lz0 - 0.01), "cedar"))
    for k in range(6):
        x = -w / 2 + 0.12 + k * (w - 0.24) / 5.0
        out.append(K.trim(box(f"{name}_den{k}", x - 0.015, x + 0.015, y, y + 0.03, lz0 - 0.10, lz0 - 0.05), "cedar"))
    # two tall flat panels below, recessed
    for k, (x0, x1) in enumerate(((-w / 2 + 0.12, -0.03), (0.03, w / 2 - 0.12))):
        out.append(K.trim(box(f"{name}_pan{k}", x0, x1, y - 0.012, y - 0.004, 0.25, lz0 - 0.18), "cedar"))
        out += [K.trim(b, "cedar") for b in K.ring_frame(f"{name}_pf{k}", x0, x1, 0.25, lz0 - 0.18, 0.012, y - 0.004, y + 0.004)]
    out += handleset(name + "_hs", w / 2 - 0.07, 0.96, y, brass=False)
    return K.part(name, out, {"LightL": (-w / 2 - 0.25, 0, 1.75), "LightR": (w / 2 + 0.25, 0, 1.75)})


@register("DoorPlankGlass", 2400)
def door_plank(name="DoorPlankGlass", seed=0.83):
    s = K.SIZES["DoorPlankGlass"]
    w, h, t = s["w"], s["h"], s["d"]
    y = -0.06
    out = door_frame(name, w, h)
    n = 6
    pw = w / n
    gz0, gz1 = 1.15, h - 0.15
    gx0, gx1 = -w / 2 + 0.15, w / 2 - 0.15
    for k in range(n):   # planks with a V-groove between them
        x0 = -w / 2 + k * pw
        out.append(K.trim(box(f"{name}_pl{k}", x0 + 0.003, x0 + pw - 0.003, y - t, y, 0.018, gz0), "paint_grain", DOOR))
        out.append(K.trim(box(f"{name}_pg{k}", x0 + 0.002, x0 + pw - 0.002, y - t, y - 0.004, 0.018, h), "paint_grain", DOOR))
    for (x0, x1, z0, z1) in ((-w / 2, gx0, gz0, h), (gx1, w / 2, gz0, h), (gx0, gx1, gz1, h)):
        out.append(K.trim(box(name + f"_fr{x0:.2f}{z1:.2f}", x0, x1, y - t, y, z0, z1), "paint_grain", DOOR))
    out.append(K.pane(quad_xz(name + "_glass", gx0, gx1, gz0, gz1, y - 0.02), seed, 0, 1))
    out += grille(name + "_gr", gx0, gx1, gz0, gz1, y - 0.012, 3, 3, 0.02, 0.012, "paint_grain", DOOR)
    out += handleset(name + "_hs", w / 2 - 0.07, 0.96, y, brass=False)
    return K.part(name, out, {"LightL": (-w / 2 - 0.25, 0, 1.75), "LightR": (w / 2 + 0.25, 0, 1.75)})


@register("DoorPivotModern", 1200)
def door_pivot(name="DoorPivotModern"):
    s = K.SIZES["DoorPivotModern"]
    w, h, t = s["w"], s["h"], s["d"]
    y = -0.08
    out = door_frame(name, w, h, d=0.16)
    out.append(K.trim(box(name + "_slab", -w / 2, w / 2, y - t, y, 0.018, h), "cedar"))
    for k in range(7):   # shallow horizontal reveals across the slab
        z = 0.018 + (h - 0.018) * (k + 1) / 8
        out.append(K.trim(box(f"{name}_rv{k}", -w / 2 + 0.002, w / 2 - 0.002, y - 0.006, y + 0.0005, z - 0.003, z + 0.003), "black_iron"))
    for zz in (0.55, 1.75):   # long bar pull on stand-offs
        out.append(K.trim(G.cyl(f"{name}_so{zz}", (w / 2 - 0.12, y, zz), (w / 2 - 0.12, y + 0.06, zz), 0.012, segs=12), "black_iron"))
    out.append(K.trim(box(name + "_bar", w / 2 - 0.135, w / 2 - 0.105, y + 0.06, y + 0.09, 0.45, 1.85), "black_iron"))
    return K.part(name, out, {"LightL": (-w / 2 - 0.3, 0, 2.0), "LightR": (w / 2 + 0.3, 0, 2.0)})


@register("DoorPatioSlider", 1400)
def door_patio(name="DoorPatioSlider", seed=0.18):
    s = K.SIZES["DoorPatioSlider"]
    w, h = s["w"], s["h"]
    out = window_frame(name, w, h, 0.10, "vinyl", SASH, fw=0.06, sill_out=0.03)
    ix0, ix1 = -w / 2 + 0.06, w / 2 - 0.06
    out += sash(name + "_l", ix0, 0.025, 0.06, h - 0.06, -0.05, -0.02, 0.07, 0.10, "vinyl", SASH, seed, door=1)
    out += sash(name + "_r", -0.025, ix1, 0.06, h - 0.06, -0.085, -0.055, 0.07, 0.10, "vinyl", SASH, seed, door=1)
    out.append(K.trim(box(name + "_pull", -0.005, 0.015, -0.02, 0.0, 0.85, 1.10), "black_iron"))
    return K.part(name, out)


# ------------------------------------------------------------------ garage doors (2 designs x 2 widths)

def garage(name, w, h, carriage, seed=0.5, flush=False):
    y = -0.10
    out = [K.trim(box(name + "_jl", -w / 2 - 0.09, -w / 2, -0.12, 0.0, 0.0, h), "paint_smooth", TRIM_S),
           K.trim(box(name + "_jr", w / 2, w / 2 + 0.09, -0.12, 0.0, 0.0, h), "paint_smooth", TRIM_S),
           K.trim(box(name + "_hd", -w / 2 - 0.09, w / 2 + 0.09, -0.12, 0.0, h, h + 0.09), "paint_smooth", TRIM_S),
           K.trim(box(name + "_seal", -w / 2, w / 2, y, y + 0.012, 0.0, 0.02), "rubber")]
    nsec = 4
    sh = h / nsec
    for k in range(nsec):
        z0, z1 = k * sh + 0.004, (k + 1) * sh - 0.004
        out.append(K.trim(box(f"{name}_sec{k}", -w / 2, w / 2, y - 0.045, y, z0, z1), "paint_grain", GARAGE))
        if flush:
            if k == 3:   # a full-width row of lites in the top section, in dark bronze frames
                nl = 4 if w > 4 else 2
                lw = (w - 0.10) / nl
                for b in range(nl):
                    x0 = -w / 2 + 0.05 + b * lw
                    out.append(K.pane(quad_xz(f"{name}_fl{b}", x0 + 0.03, x0 + lw - 0.03, z0 + 0.06, z1 - 0.06, y + 0.001), seed + b * 0.01))
                    out += [K.trim(q, "bronze") for q in K.ring_frame(f"{name}_ff{b}", x0, x0 + lw, z0 + 0.03, z1 - 0.03, 0.035, y, y + 0.012)]
        elif carriage:
            nb = max(4, int(round(w / 0.15)))
            for b in range(1, nb):   # V-grooves of the vertical boards
                x = -w / 2 + w * b / nb
                out.append(K.trim(box(f"{name}_g{k}_{b}", x - 0.003, x + 0.003, y - 0.004, y + 0.0005, z0, z1), "paint_grain", GARAGE))
        elif not flush:
            npan = 8 if w > 4 else 4
            pw = w / npan
            for b in range(npan):
                x0 = -w / 2 + b * pw + 0.05
                out.append(raised_panel(f"{name}_rp{k}_{b}", x0, x0 + pw - 0.10, z0 + 0.09, z1 - 0.09, y, 0.016, 0.028, GARAGE))
    if carriage:
        nl = 4 if w > 4 else 2
        lw = (w - 0.3) / nl
        z0, z1 = 3 * sh + 0.12, 4 * sh - 0.10
        for b in range(nl):
            x0 = -w / 2 + 0.15 + b * lw + 0.06
            out.append(K.pane(quad_xz(f"{name}_lite{b}", x0, x0 + lw - 0.12, z0, z1, y + 0.002), seed + b * 0.01))
            out += [K.trim(q, "paint_grain", GARAGE) for q in K.ring_frame(f"{name}_lf{b}", x0 - 0.02, x0 + lw - 0.10, z0 - 0.02, z1 + 0.02, 0.025, y, y + 0.015)]
        # strap hinges and handles in black iron
        for side in (-1, 1):
            for k in (0, 2, 3):
                zc = k * sh + sh * 0.5
                x0 = side * (w / 2 - 0.06)
                x1 = side * (w / 2 - 0.50)
                out.append(K.trim(box(f"{name}_strap{side}{k}", min(x0, x1), max(x0, x1), y, y + 0.006, zc - 0.022, zc + 0.022), "black_iron"))
            hx = side * 0.25
            out.append(K.trim(box(f"{name}_hdl{side}", hx - 0.012, hx + 0.012, y, y + 0.05, sh * 1.2, sh * 1.2 + 0.30), "black_iron"))
    return out


@register("GarageRaised16", 4000, kind="opening")
def garage_raised16(name="GarageRaised16"):
    s = K.SIZES["GarageRaised16"]
    return K.part(name, garage(name, s["w"], s["h"], False), {"LightL": (-s["w"] / 2 - 0.35, 0, 2.3), "LightR": (s["w"] / 2 + 0.35, 0, 2.3)})


@register("GarageRaised9", 2400)
def garage_raised9(name="GarageRaised9"):
    s = K.SIZES["GarageRaised9"]
    return K.part(name, garage(name, s["w"], s["h"], False), {"LightL": (-s["w"] / 2 - 0.35, 0, 2.3), "LightR": (s["w"] / 2 + 0.35, 0, 2.3)})


@register("GarageCarriage16", 4000)
def garage_carriage16(name="GarageCarriage16"):
    s = K.SIZES["GarageCarriage16"]
    return K.part(name, garage(name, s["w"], s["h"], True, 0.27), {"LightL": (-s["w"] / 2 - 0.35, 0, 2.3), "LightR": (s["w"] / 2 + 0.35, 0, 2.3)})


@register("GarageCarriage9", 2400)
def garage_carriage9(name="GarageCarriage9"):
    s = K.SIZES["GarageCarriage9"]
    return K.part(name, garage(name, s["w"], s["h"], True, 0.61), {"LightL": (-s["w"] / 2 - 0.35, 0, 2.3), "LightR": (s["w"] / 2 + 0.35, 0, 2.3)})


@register("GarageFlush16", 1200, row="GarageRaised16")
def garage_flush16(name="GarageFlush16"):
    s = K.SIZES["GarageRaised16"]
    return K.part(name, garage(name, s["w"], s["h"], False, 0.44, flush=True), {"LightL": (-s["w"] / 2 - 0.35, 0, 2.3), "LightR": (s["w"] / 2 + 0.35, 0, 2.3)})


# ------------------------------------------------------------------ shutters (3): origin bottom inner edge, extends +X? no: centred

def shutter(name, w, h, kind):
    t = 0.028
    out = []
    st, rl = 0.055, 0.07
    out += [K.trim(b, "paint_smooth", SHUTTER) for b in K.ring_frame(name + "_f", -w / 2, w / 2, 0.0, h, st, 0.0, t, rl)]
    if kind == "louvre":
        mid = h * 0.5
        out.append(K.trim(box(name + "_mid", -w / 2 + st, w / 2 - st, 0.0, t, mid - 0.03, mid + 0.03), "paint_smooth", SHUTTER))
        out.append(K.trim(box(name + "_lv", -w / 2 + st, w / 2 - st, 0.004, t - 0.008, rl, h - st), "louvre", SHUTTER))
    elif kind == "panel":
        mid = h * 0.42
        out.append(K.trim(box(name + "_mid", -w / 2 + st, w / 2 - st, 0.0, t, mid - 0.035, mid + 0.035), "paint_smooth", SHUTTER))
        out.append(K.trim(box(name + "_back", -w / 2 + st, w / 2 - st, 0.0, t * 0.5, rl, h - st), "paint_smooth", SHUTTER))
        out.append(raised_panel(name + "_p0", -w / 2 + st, w / 2 - st, rl, mid - 0.035, t * 0.5, 0.008, 0.025, SHUTTER, "paint_smooth"))
        out.append(raised_panel(name + "_p1", -w / 2 + st, w / 2 - st, mid + 0.035, h - st, t * 0.5, 0.008, 0.025, SHUTTER, "paint_smooth"))
    else:   # board and batten with a Z brace
        out = []
        nb = 3
        for k in range(nb):
            x0 = -w / 2 + w * k / nb
            out.append(K.trim(box(f"{name}_b{k}", x0 + 0.002, x0 + w / nb - 0.002, 0.0, t, 0.0, h), "paint_grain", SHUTTER))
        for zc in (0.18, h - 0.18):
            out.append(K.trim(box(f"{name}_bat{zc:.2f}", -w / 2 + 0.02, w / 2 - 0.02, t, t + 0.022, zc - 0.045, zc + 0.045), "paint_grain", SHUTTER))
        L = math.hypot(w - 0.06, h - 0.45)
        br = G.box(name + "_z", (0, 0, L / 2), (0.08, 0.022, L))
        br.matrix_world = G.along((-w / 2 + 0.03, t + 0.011, 0.225), (w - 0.06, 0.0, h - 0.45))
        G.bake_xform(br)
        out.append(K.trim(br, "paint_grain", SHUTTER))
    # two hinge straps (black iron) on the inner stile; the shutter dog goes on the wall (socket Dog)
    for zc in (0.15, h - 0.15):
        out.append(K.trim(box(f"{name}_hg{zc:.2f}", -w / 2, -w / 2 + 0.12, t, t + 0.004, zc - 0.012, zc + 0.012), "black_iron"))
    return out


@register("ShutterLouvre", 600, kind="wallmount")
def shutter_louvre(name="ShutterLouvre"):
    s = K.SIZES["ShutterLouvre"]
    return K.part(name, shutter(name, s["w"], s["h"], "louvre"), {"Dog": (0.0, 0.0, -0.08)})


@register("ShutterPanel", 700, kind="wallmount")
def shutter_panel(name="ShutterPanel"):
    s = K.SIZES["ShutterPanel"]
    return K.part(name, shutter(name, s["w"], s["h"], "panel"), {"Dog": (0.0, 0.0, -0.08)})


@register("ShutterBoard", 600, kind="wallmount")
def shutter_board(name="ShutterBoard"):
    s = K.SIZES["ShutterBoard"]
    return K.part(name, shutter(name, s["w"], s["h"], "board"), {"Dog": (0.0, 0.0, -0.08)})


# ------------------------------------------------------------------ gutters, downspouts, roof vents

def k_gutter_section(depth=0.127, width=0.127):
    """K-style gutter cross-section (u out from the fascia, v up), as an open profile shelled to 1 mm (drawn as a
    closed thin outline so it reads from both sides)."""
    o = [(0.0, depth), (0.0, 0.0), (width * 0.78, 0.0), (width * 0.84, depth * 0.10), (width * 0.86, depth * 0.45),
         (width, depth * 0.62), (width * 0.97, depth * 0.84), (width, depth)]
    inner = [(u + (0.002 if u < width * 0.5 else -0.002), v + (0.002 if v < depth * 0.5 else 0.0)) for (u, v) in reversed(o)]
    return o + inner


@register("Gutter", 200, kind="linear")
def gutter(name="Gutter", length=1.0, paint=METAL):
    sec = k_gutter_section()
    path = [(-length / 2, 0.0, 0.0), (length / 2, 0.0, 0.0)]
    # sweep: section u along +Y (out), v along +Z
    ob = G.sweep(name + "_run", path, [(u, v) for (u, v) in sec], twist_up=(0, 0, 1))
    # make sure the section's u axis is +Y: sweep's u is up x tangent = Z x X = +Y; v = t x u = X x Y = +Z
    pieces = [K.trim(ob, "aluminium", paint)]
    return K.part(name, pieces)


@register("Downspout", 500, kind="linear")
def downspout(name="Downspout", height=2.9, off=0.20, paint=METAL):
    """2 x 3 in downspout from the gutter outlet (top, `off` out from the wall) down the wall, kick-out and splash block."""
    sec = [(-0.038, -0.0255), (0.038, -0.0255), (0.038, 0.0255), (-0.038, 0.0255)]
    top = height
    path = [(0.0, off, top), (0.0, off, top - 0.08), (0.0, 0.06, top - 0.30), (0.0, 0.035, top - 0.40),
            (0.0, 0.035, 0.32), (0.0, 0.06, 0.20), (0.0, 0.25, 0.08)]
    run = G.sweep(name + "_run", path, [(a, b) for (a, b) in sec], twist_up=(0, 1, 0))
    out = [K.trim(run, "aluminium", paint)]
    for z in (0.9, 1.9):   # straps
        out.append(K.trim(box(f"{name}_st{z}", -0.045, 0.045, 0.0, 0.064, z - 0.015, z + 0.015), "aluminium", paint))
    sb = G.prism(name + "_splash", [(-0.15, 0.20), (0.15, 0.20), (0.18, 0.80), (-0.18, 0.80)], -0.01, 0.05, taper=1.0)
    out.append(K.trim(sb, "concrete"))
    return K.part(name, out)


@register("TurbineVent", 2400, kind="roof")
def turbine(name="TurbineVent"):
    out = []
    base = G.lathe(name + "_base", [(0.0, 0.0), (0.23, 0.0), (0.23, 0.012), (0.10, 0.02), (0.10, 0.17), (0.0, 0.17)], segs=24)
    out.append(K.trim(base, "galvanised"))
    # the head: twisted vanes between two rings
    n = 30
    for i in range(n):
        a0 = 2 * math.pi * i / n
        pts = []
        for k in range(7):
            t = k / 6.0
            z = 0.17 + 0.03 + t * 0.20
            r = 0.17 + 0.03 * math.sin(math.pi * t)
            a = a0 + 0.55 * t
            pts.append((r * math.cos(a), r * math.sin(a), z))
        vane = G.sweep(f"{name}_v{i}", pts, [(-0.012, -0.0008), (0.012, -0.0008), (0.012, 0.0008), (-0.012, 0.0008)])
        out.append(K.trim(vane, "galvanised"))
    for z, r in ((0.20, 0.17), (0.40, 0.17)):
        out.append(K.trim(G.lathe(f"{name}_ring{z}", [(r - 0.012, z - 0.006), (r + 0.006, z - 0.006), (r + 0.006, z + 0.006), (r - 0.012, z + 0.006)], segs=30), "galvanised"))
    cap = G.lathe(name + "_cap", [(0.0, 0.40), (0.17, 0.40), (0.12, 0.43), (0.0, 0.435)], segs=24)
    out.append(K.trim(cap, "galvanised"))
    return K.part(name, out)


@register("BoxVent", 200, kind="roof")
def box_vent(name="BoxVent"):
    out = [K.trim(box(name + "_flash", -0.23, 0.23, -0.23, 0.23, 0.0, 0.004), "black_iron"),
           K.trim(G.prism(name + "_hood", [(-0.16, -0.18), (0.16, -0.18), (0.16, 0.16), (-0.16, 0.16)], 0.004, 0.15, taper=0.85), "black_iron"),
           K.trim(box(name + "_mouth", -0.15, 0.15, -0.20, -0.17, 0.01, 0.06), "screen")]
    return K.part(name, out)


@register("GableVent", 400, kind="wallmount")
def gable_vent(name="GableVent", tri=False):
    s = K.SIZES["GableVent"]
    w, h = s["w"], s["h"]
    out = [K.trim(b, "paint_smooth", TRIM_S) for b in K.ring_frame(name + "_f", -w / 2, w / 2, 0.0, h, 0.07, 0.0, 0.03)]
    out.append(K.trim(box(name + "_lv", -w / 2 + 0.07, w / 2 - 0.07, -0.01, 0.022, 0.07, h - 0.07), "louvre", TRIM_S))
    return K.part(name, out)


@register("StackPipe", 120, kind="roof")
def stack_pipe(name="StackPipe"):
    out = [K.trim(G.cyl(name + "_p", (0, 0, 0), (0, 0, 0.30), 0.045, segs=12), "black_iron"),
           K.trim(G.lathe(name + "_boot", [(0.0, 0.0), (0.16, 0.0), (0.05, 0.06), (0.05, 0.08), (0.0, 0.08)], segs=12), "black_iron")]
    return K.part(name, out)


@register("RidgeCap", 200, kind="linear")
def ridge_cap(name="RidgeCap", length=1.0, pitch_deg=26.0, finish="shingle_charcoal"):
    """Ridge cap shingles over a vent strip: a shallow tent 0.30 wide, in the roof finish (Roof slot)."""
    a = math.radians(pitch_deg)
    hw = 0.15
    sec = [(-hw, -hw * math.tan(a) + 0.02), (0.0, 0.03), (hw, -hw * math.tan(a) + 0.02), (hw, -hw * math.tan(a)),
           (0.0, 0.0), (-hw, -hw * math.tan(a))]
    ob = G.sweep(name + "_cap", [(-length / 2, 0, 0), (length / 2, 0, 0)], sec)
    return K.part(name, [K.roof(ob, finish)])


# ------------------------------------------------------------------ chimneys (3): origin at the roof line's base centre

@register("ChimneyBrick", 900, kind="roof")
def chimney_brick(name="ChimneyBrick", height=1.5, finish="brick_red"):
    s = K.SIZES["ChimneyBrick"]
    w, d = s["w"], s["d"]
    out = [K.wall(box(name + "_body", -w / 2, w / 2, -d / 2, d / 2, -0.6, height), finish),
           K.trim(box(name + "_crown", -w / 2 - 0.05, w / 2 + 0.05, -d / 2 - 0.05, d / 2 + 0.05, height, height + 0.10), "concrete"),
           K.trim(box(name + "_corbel", -w / 2 - 0.02, w / 2 + 0.02, -d / 2 - 0.02, d / 2 + 0.02, height - 0.25, height - 0.17), "concrete"),
           K.trim(box(name + "_flash", -w / 2 - 0.006, w / 2 + 0.006, -d / 2 - 0.006, d / 2 + 0.006, -0.6, 0.12), "aluminium", METAL)]
    for k, x in enumerate((-w / 4, w / 4)):   # two clay flue tiles and a mesh cap over each
        out.append(K.trim(box(f"{name}_flue{k}", x - 0.11, x + 0.11, -0.11, 0.11, height + 0.10, height + 0.30), "cast_stone"))
        out.append(K.trim(box(f"{name}_cap{k}", x - 0.15, x + 0.15, -0.15, 0.15, height + 0.42, height + 0.45), "galvanised"))
        out.append(K.trim(box(f"{name}_mesh{k}", x - 0.13, x + 0.13, -0.13, 0.13, height + 0.30, height + 0.42), "screen"))
    return K.part(name, out)


@register("ChimneyChase", 700, kind="roof")
def chimney_chase(name="ChimneyChase", height=1.5, finish="lap_siding"):
    s = K.SIZES["ChimneyChase"]
    w, d = s["w"], s["d"]
    out = [K.wall(box(name + "_body", -w / 2, w / 2, -d / 2, d / 2, -0.6, height), finish),
           K.trim(box(name + "_pan", -w / 2 - 0.03, w / 2 + 0.03, -d / 2 - 0.03, d / 2 + 0.03, height, height + 0.04), "black_iron"),
           K.trim(G.cyl(name + "_pipe", (0.0, 0.0, height + 0.04), (0.0, 0.0, height + 0.35), 0.13, segs=16), "galvanised")]
    # decorative shroud: four sloping sides on four legs
    shroud = G.prism(name + "_shroud", [(-0.38, -0.30), (0.38, -0.30), (0.38, 0.30), (-0.38, 0.30)], height + 0.55, height + 0.80, taper=0.3)
    out.append(K.trim(shroud, "black_iron"))
    out.append(K.trim(box(name + "_skirt", -0.38, 0.38, -0.30, 0.30, height + 0.47, height + 0.55), "black_iron"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(K.trim(box(f"{name}_leg{sx}{sy}", sx * 0.33 - 0.015, sx * 0.33 + 0.015, sy * 0.25 - 0.015, sy * 0.25 + 0.015, height + 0.04, height + 0.47), "black_iron"))
    out += [K.trim(b, "paint_smooth", TRIM_S) for b in (
        box(name + "_cb0", -w / 2 - 0.02, -w / 2 + 0.07, -d / 2 - 0.02, -d / 2 + 0.07, -0.6, height),
        box(name + "_cb1", w / 2 - 0.07, w / 2 + 0.02, -d / 2 - 0.02, -d / 2 + 0.07, -0.6, height),
        box(name + "_cb2", -w / 2 - 0.02, -w / 2 + 0.07, d / 2 - 0.07, d / 2 + 0.02, -0.6, height),
        box(name + "_cb3", w / 2 - 0.07, w / 2 + 0.02, d / 2 - 0.07, d / 2 + 0.02, -0.6, height))]
    return K.part(name, out)


@register("ChimneyFlue", 400, kind="roof")
def chimney_flue(name="ChimneyFlue", height=1.2):
    out = [K.trim(G.cyl(name + "_pipe", (0, 0, -0.3), (0, 0, height), 0.125, segs=16), "galvanised"),
           K.trim(G.lathe(name + "_boot", [(0.0, -0.02), (0.40, -0.02), (0.40, 0.0), (0.14, 0.18), (0.13, 0.18), (0.0, 0.18)], segs=16), "galvanised"),
           K.trim(G.lathe(name + "_collar", [(0.0, 0.20), (0.24, 0.20), (0.13, 0.30), (0.0, 0.30)], segs=16), "galvanised"),
           K.trim(G.lathe(name + "_cap", [(0.0, height + 0.08), (0.24, height + 0.08), (0.20, height + 0.14), (0.0, height + 0.20)], segs=16), "galvanised")]
    for k in range(4):
        a = math.pi / 2 * k + math.pi / 4
        out.append(K.trim(box(f"{name}_br{k}", 0.11 * math.cos(a) - 0.008, 0.11 * math.cos(a) + 0.008, 0.11 * math.sin(a) - 0.008, 0.11 * math.sin(a) + 0.008, height, height + 0.09), "galvanised"))
    return K.part(name, out)


# ------------------------------------------------------------------ dormers (2): origin at the front face's bottom centre on the roof

@register("DormerGable", 3200, kind="roof")
def dormer_gable(name="DormerGable", pitch_deg=40.0, wall_fin="lap_siding", roof_fin="shingle_charcoal", seed=0.55):
    s = K.SIZES["DormerGable"]
    w, h, d = s["w"], s["h"], s["d"]
    out = []
    a = math.radians(pitch_deg)
    ridge = h + (w / 2 + 0.25) * math.tan(math.radians(40))
    # front wall: rectangle and gable triangle; cheeks back to where the main roof meets them
    import bmesh
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in ((-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (0, 0, ridge - 0.10), (-w / 2, 0, h))]
    bm.faces.new(v)
    for f in bm.faces:
        f.normal_update()
        if f.normal.y > 0:
            f.normal_flip()
    front = G.mesh_obj(name + "_front", bm)
    # the front faces -Y (downhill, out of the main roof); turn the part so its face is +Y like every opening
    out.append(K.wall(front, wall_fin))
    for sx in (-1, 1):
        x = sx * w / 2
        bm = bmesh.new()
        # cheek: from the front's side edge back to the roof plane (which rises toward -Y... here +Y is into the roof)
        back = h / math.tan(a)
        vv = [bm.verts.new(p) for p in ((x, 0, 0), (x, 0, h), (x, back, h))]
        bm.faces.new(vv)
        for f in bm.faces:
            f.normal_update()
            if f.normal.x * sx < 0:
                f.normal_flip()
        out.append(K.wall(G.mesh_obj(f"{name}_cheek{sx}", bm), wall_fin))
    # roof planes with 0.25 m overhangs
    ov = 0.25
    back = ridge / math.tan(a)
    for sx in (-1, 1):
        bm = bmesh.new()
        e0 = (sx * (w / 2 + ov), -ov, h - ov * math.tan(math.radians(40)))
        r0 = (0.0, -ov, ridge)
        r1 = (0.0, back, ridge)
        e1 = (sx * (w / 2 + ov), back, h - ov * math.tan(math.radians(40)))
        vv = [bm.verts.new(p) for p in (e0, r0, r1, e1)]
        bm.faces.new(vv)
        for f in bm.faces:
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
        out.append(K.roof(G.mesh_obj(f"{name}_roof{sx}", bm), roof_fin))
        # rake board under the roof edge
        rake = G.sweep(f"{name}_rake{sx}", [(e0[0] * 0.98, -ov, e0[2] - 0.02), (0.0, -ov, ridge - 0.02)], [(-0.012, -0.14), (0.012, -0.14), (0.012, 0.0), (-0.012, 0.0)], twist_up=(0, -1, 0))
        out.append(K.trim(rake, "paint_smooth", TRIM_S))
    win = single_hung(name + "_w", 0.762, 1.219, grid=(2, 2), seed=seed)
    for o in win:
        o.location = (0.0, 0.0, 0.18)
        o.rotation_euler = (0.0, 0.0, math.pi)   # the dormer's face is -Y: turn the window to face it
        G.bake_xform(o)
    out += win
    # casing round the window
    for (x0, x1, z0, z1) in ((-0.381 - 0.09, -0.381, 0.18, 0.18 + 1.219), (0.381, 0.381 + 0.09, 0.18, 0.18 + 1.219), (-0.381 - 0.09, 0.381 + 0.09, 0.18 + 1.219, 0.18 + 1.219 + 0.09)):
        out.append(K.trim(box(name + f"_cs{x0:.2f}{z0:.2f}", x0, x1, -0.022, 0.0, z0, z1), "paint_smooth", TRIM_S))
    ob = K.part(name, out)
    # turn the whole dormer so its face looks +Y like every other part (origin unchanged)
    ob.rotation_euler = (0, 0, math.pi)
    G.bake_xform(ob)
    return ob


@register("DormerShed", 3200, kind="roof")
def dormer_shed(name="DormerShed", pitch_deg=40.0, wall_fin="lap_siding", roof_fin="shingle_charcoal", seed=0.36):
    s = K.SIZES["DormerShed"]
    w, h, d = s["w"], s["h"], s["d"]
    out = []
    a = math.radians(pitch_deg)
    import bmesh

    def face(nm, pts, want, kind):
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(p) for p in pts])
        for f in bm.faces:
            f.normal_update()
            if f.normal.dot(Vector(want)) < 0:
                f.normal_flip()
        ob = G.mesh_obj(nm, bm)
        return K.wall(ob, wall_fin) if kind == "wall" else K.roof(ob, roof_fin)
    back = d
    zb = h + back * math.tan(math.radians(12))     # the shed roof climbs at 12 deg to meet the main roof higher up
    out.append(face(name + "_front", [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)], (0, -1, 0), "wall"))
    for sx in (-1, 1):
        x = sx * w / 2
        out.append(face(f"{name}_ch{sx}", [(x, 0, 0), (x, 0, h), (x, back, zb), (x, back, back * math.tan(a))], (sx, 0, 0), "wall"))
    ov = 0.25
    out.append(face(name + "_roof", [(-w / 2 - ov, -ov, h - ov * math.tan(math.radians(12))), (w / 2 + ov, -ov, h - ov * math.tan(math.radians(12))), (w / 2 + ov, back + 0.2, zb + 0.2 * math.tan(math.radians(12))), (-w / 2 - ov, back + 0.2, zb + 0.2 * math.tan(math.radians(12)))], (0, 0, 1), "roof"))
    out.append(K.trim(box(name + "_fascia", -w / 2 - ov, w / 2 + ov, -ov - 0.025, -ov, h - ov * math.tan(math.radians(12)) - 0.14, h - ov * math.tan(math.radians(12))), "paint_smooth", TRIM_S))
    for k, x in enumerate((-0.45, 0.45)):
        win = single_hung(f"{name}_w{k}", 0.762, 1.067, grid=(2, 2), seed=seed)
        for o in win:
            o.location = (x, 0.0, 0.2)
            o.rotation_euler = (0.0, 0.0, math.pi)
            G.bake_xform(o)
        out += win
    ob = K.part(name, out)
    ob.rotation_euler = (0, 0, math.pi)
    G.bake_xform(ob)
    return ob


# ------------------------------------------------------------------ porch: columns, rails, steps

@register("ColumnSquare", 300, kind="floor")
def column_square(name="ColumnSquare", height=2.74):
    out = [K.trim(box(name + "_base", -0.13, 0.13, -0.13, 0.13, 0.0, 0.22), "paint_smooth", TRIM_S),
           K.trim(box(name + "_shaft", -0.10, 0.10, -0.10, 0.10, 0.22, height - 0.18), "paint_grain", TRIM_S),
           K.trim(box(name + "_neck", -0.115, 0.115, -0.115, 0.115, height - 0.18, height - 0.14), "paint_smooth", TRIM_S),
           K.trim(box(name + "_cap", -0.14, 0.14, -0.14, 0.14, height - 0.10, height), "paint_smooth", TRIM_S)]
    return K.part(name, out)


@register("ColumnTapered", 400, kind="floor")
def column_tapered(name="ColumnTapered", height=2.74, pier_finish="limestone"):
    pier = 0.95
    out = [K.wall(box(name + "_pier", -0.23, 0.23, -0.23, 0.23, 0.0, pier), pier_finish),
           K.trim(box(name + "_pcap", -0.26, 0.26, -0.26, 0.26, pier, pier + 0.06), "cast_stone"),
           K.trim(G.prism(name + "_shaft", [(-0.15, -0.15), (0.15, -0.15), (0.15, 0.15), (-0.15, 0.15)], pier + 0.06, height - 0.12, taper=0.66), "paint_grain", TRIM_S),
           K.trim(box(name + "_cap", -0.13, 0.13, -0.13, 0.13, height - 0.12, height), "paint_smooth", TRIM_S)]
    return K.part(name, out)


@register("ColumnRound", 600, kind="floor")
def column_round(name="ColumnRound", height=2.74):
    r = 0.125
    prof = [(0.0, 0.0), (0.17, 0.0), (0.17, 0.05), (0.15, 0.06), (0.15, 0.09), (r + 0.01, 0.11), (r, 0.14),
            (r * 0.84, height - 0.20), (r * 0.9, height - 0.17), (r * 0.9, height - 0.15), (0.15, height - 0.11),
            (0.16, height - 0.06), (0.16, height), (0.0, height)]
    ob = G.lathe(name + "_c", prof, segs=24)
    return K.part(name, [K.trim(ob, "paint_smooth", TRIM_S)])


@register("PostCedar", 300, kind="floor")
def post_cedar(name="PostCedar", height=2.74):
    out = [K.trim(box(name + "_p", -0.07, 0.07, -0.07, 0.07, 0.0, height), "cedar")]
    for sx in (-1, 1):   # knee braces toward the beam either side
        L = 0.62
        br = G.box(f"{name}_kb{sx}", (0, 0, 0), (0.07, 0.07, L))
        br.matrix_world = G.along((sx * 0.07, 0.0, height - 0.55), (sx * 0.42, 0.0, 0.45))
        G.bake_xform(br)
        out.append(K.trim(br, "cedar"))
    out.append(K.trim(box(name + "_base", -0.09, 0.09, -0.09, 0.09, 0.0, 0.015), "black_iron"))
    return K.part(name, out)


@register("RailBaluster", 1200, kind="linear")
def rail_baluster(name="RailBaluster", length=2.4, height=0.914, band="paint_smooth", paint=TRIM_S):
    out = [K.trim(box(name + "_top", -length / 2, length / 2, -0.045, 0.045, height - 0.04, height), band, paint),
           K.trim(box(name + "_sub", -length / 2, length / 2, -0.03, 0.03, height - 0.08, height - 0.04), band, paint),
           K.trim(box(name + "_bot", -length / 2, length / 2, -0.03, 0.03, 0.06, 0.10), band, paint)]
    n = int(length / 0.135)
    for k in range(n):
        x = -length / 2 + (k + 0.5) * length / n
        out.append(K.trim(box(f"{name}_b{k}", x - 0.019, x + 0.019, -0.019, 0.019, 0.10, height - 0.08), band, paint))
    return K.part(name, out)


@register("StepsConcrete", 300, kind="floor")
def steps_concrete(name="StepsConcrete", width=1.52, risers=3, rail=True):
    rise, tread = 0.178, 0.28
    out = []
    for k in range(risers):
        z1 = (risers - k) * rise
        out.append(K.trim(box(f"{name}_s{k}", -width / 2, width / 2, 0.0, (k + 1) * tread, 0.0, z1), "concrete"))
    if rail:   # an iron handrail down the left side
        x = -width / 2 + 0.06
        top = risers * rise + 0.86
        out.append(K.trim(G.cyl(name + "_hr", (x, 0.05, top), (x, risers * tread, 0.86), 0.02, segs=10), "black_iron"))
        for y, z in ((0.05, risers * rise), (risers * tread - 0.05, rise * 0.3)):
            out.append(K.trim(box(f"{name}_po{y:.2f}", x - 0.02, x + 0.02, y - 0.02, y + 0.02, z, z + 0.88), "black_iron"))
    return K.part(name, out)


# ------------------------------------------------------------------ foundations

@register("FoundationSlab", 40, kind="linear")
def foundation_slab(name="FoundationSlab", length=1.0, height=0.30):
    return K.part(name, [K.trim(box(name + "_e", -length / 2, length / 2, 0.0, 0.02, -0.05, height), "concrete")])


@register("SkirtLattice", 80, kind="linear")
def skirt_lattice(name="SkirtLattice", length=1.0, height=0.60):
    out = [K.trim(box(name + "_l", -length / 2, length / 2, 0.0, 0.012, 0.0, height), "lattice", TRIM_S),
           K.trim(box(name + "_t", -length / 2, length / 2, 0.012, 0.03, height - 0.07, height), "paint_smooth", TRIM_S),
           K.trim(box(name + "_b", -length / 2, length / 2, 0.012, 0.03, 0.0, 0.07), "paint_smooth", TRIM_S)]
    return K.part(name, out)


# ------------------------------------------------------------------ lights, AC, meters

@register("LightCoach", 900, kind="wallmount")
def light_coach(name="LightCoach"):
    out = [K.trim(box(name + "_plate", -0.06, 0.06, 0.0, 0.015, 0.10, 0.30), "black_iron"),
           K.trim(box(name + "_arm", -0.015, 0.015, 0.015, 0.13, 0.17, 0.20), "black_iron"),
           K.trim(G.prism(name + "_roof", [(-0.10, 0.03), (0.10, 0.03), (0.10, 0.23), (-0.10, 0.23)], 0.33, 0.40, taper=0.35), "black_iron"),
           K.trim(box(name + "_bot", -0.08, 0.08, 0.05, 0.21, 0.10, 0.13), "black_iron"),
           K.trim(G.cyl(name + "_fin", (0, 0.13, 0.40), (0, 0.13, 0.44), 0.012, segs=8), "black_iron")]
    for k, (x0, x1, y0, y1) in enumerate(((-0.08, 0.08, 0.205, 0.215), (-0.08, 0.08, 0.045, 0.055), (-0.085, -0.075, 0.05, 0.21), (0.075, 0.085, 0.05, 0.21))):
        out.append(K.cell(box(f"{name}_g{k}", x0, x1, y0, y1, 0.13, 0.33), "lamp_glass"))
    for sx in (-1, 1):
        for sy in (0.05, 0.21):
            out.append(K.trim(box(f"{name}_c{sx}{sy}", sx * 0.08 - 0.008, sx * 0.08 + 0.008, sy - 0.008, sy + 0.008, 0.13, 0.33), "black_iron"))
    return K.part(name, out, {"Bulb": (0.0, 0.13, 0.22)})


@register("LightCylinder", 300, kind="wallmount")
def light_cylinder(name="LightCylinder"):
    out = [K.trim(box(name + "_plate", -0.04, 0.04, 0.0, 0.012, 0.05, 0.25), "black_iron"),
           K.trim(G.cyl(name + "_body", (0, 0.08, 0.0), (0, 0.08, 0.30), 0.05, segs=16), "black_iron"),
           K.trim(box(name + "_arm", -0.02, 0.02, 0.012, 0.04, 0.12, 0.18), "black_iron"),
           K.cell(G.cyl(name + "_lensb", (0, 0.08, -0.002), (0, 0.08, 0.002), 0.04, segs=16), "lamp_glass"),
           K.cell(G.cyl(name + "_lenst", (0, 0.08, 0.298), (0, 0.08, 0.302), 0.04, segs=16), "lamp_glass")]
    return K.part(name, out, {"BulbDown": (0, 0.08, 0.0), "BulbUp": (0, 0.08, 0.30)})


@register("LightGooseneck", 500, kind="wallmount")
def light_gooseneck(name="LightGooseneck"):
    path = [(0.0, 0.0, 0.10), (0.0, 0.10, 0.10), (0.0, 0.22, 0.16), (0.0, 0.30, 0.30), (0.0, 0.36, 0.40)]
    out = [K.trim(G.cyl(name + "_plate", (0, 0, 0.10), (0, 0.02, 0.10), 0.06, segs=16), "black_iron"),
           K.trim(G.tube(name + "_arm", path, 0.012, segs=10), "black_iron"),
           K.trim(G.lathe(name + "_shade", [(0.0, 0.42), (0.03, 0.42), (0.05, 0.40), (0.18, 0.30), (0.18, 0.29), (0.0, 0.29)], segs=24), "black_iron")]
    out[-1].location = (0, 0.36, -0.02)
    G.bake_xform(out[-1])
    out.append(K.cell(G.cyl(name + "_lens", (0, 0.36, 0.27), (0, 0.36, 0.272), 0.16, segs=24), "lamp_glass"))
    return K.part(name, out, {"Bulb": (0, 0.36, 0.30)})


@register("ACCondenser", 1200, kind="floor")
def ac_condenser(name="ACCondenser"):
    s = K.SIZES["ACCondenser"]
    w, h = s["w"], s["h"]
    y0 = 0.30
    cy = y0 + w / 2
    out = [K.trim(box(name + "_pad", -0.45, 0.45, cy - 0.45, cy + 0.45, 0.0, 0.08), "concrete"),
           K.trim(box(name + "_base", -w / 2, w / 2, cy - w / 2, cy + w / 2, 0.08, 0.16), "galvanised"),
           K.trim(box(name + "_top", -w / 2, w / 2, cy - w / 2, cy + w / 2, 0.08 + h - 0.06, 0.08 + h), "galvanised"),
           K.cell(box(name + "_fan", -w / 2 + 0.05, w / 2 - 0.05, cy - w / 2 + 0.05, cy + w / 2 - 0.05, 0.08 + h, 0.08 + h + 0.004), "fan_grille")]
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0 = w / 2 - 0.03 if sx > 0 else -w / 2
            yy0 = cy + w / 2 - 0.03 if sy > 0 else cy - w / 2
            out.append(K.trim(box(f"{name}_post{sx}{sy}", x0, x0 + 0.03, yy0, yy0 + 0.03, 0.16, 0.08 + h - 0.06), "galvanised"))
    inset = 0.012
    for (x0, x1, yy0, yy1) in ((-w / 2 + 0.03, w / 2 - 0.03, cy - w / 2 + inset - 0.002, cy - w / 2 + inset),
                              (-w / 2 + 0.03, w / 2 - 0.03, cy + w / 2 - inset, cy + w / 2 - inset + 0.002),
                              (-w / 2 + inset - 0.002, -w / 2 + inset, cy - w / 2 + 0.03, cy + w / 2 - 0.03),
                              (w / 2 - inset, w / 2 - inset + 0.002, cy - w / 2 + 0.03, cy + w / 2 - 0.03)):
        out.append(K.trim(box(name + f"_coil{x0:.2f}{yy0:.2f}", x0, x1, yy0, yy1, 0.16, 0.08 + h - 0.06), "coil_guard"))
    # service panel corner and the insulated line set running to the wall
    out.append(K.trim(box(name + "_svc", w / 2 - 0.25, w / 2 + 0.004, cy - w / 2 - 0.004, cy - w / 2 + 0.25, 0.20, 0.08 + h - 0.10), "galvanised"))
    path = [(w / 2 - 0.10, cy - w / 2 - 0.02, 0.30), (w / 2 - 0.10, 0.20, 0.30), (w / 2 - 0.10, 0.05, 0.40), (w / 2 - 0.10, 0.0, 0.40)]
    out.append(K.trim(G.tube(name + "_line", path, 0.022, segs=10), "rubber"))
    out.append(K.trim(box(name + "_disc", w / 2 - 0.25, w / 2 - 0.05, 0.0, 0.10, 1.05, 1.35), "galvanised"))
    out.append(K.trim(G.tube(name + "_whip", [(w / 2 - 0.15, 0.05, 1.05), (w / 2 - 0.15, 0.10, 0.8), (w / 2 - 0.15, cy - w / 2 - 0.02, 0.6)], 0.012, segs=8), "black_iron"))
    return K.part(name, out)


@register("ACWindowUnit", 300, kind="wallmount")
def ac_window(name="ACWindowUnit"):
    s = K.SIZES["ACWindowUnit"]
    w, h, d = s["w"], s["h"], s["d"]
    out = [K.trim(box(name + "_case", -w / 2, w / 2, -0.15, d - 0.15, 0.0, h), "galvanised"),
           K.trim(box(name + "_grille", -w / 2 + 0.02, w / 2 - 0.02, d - 0.15, d - 0.14, 0.02, h - 0.02), "coil_guard"),
           K.trim(box(name + "_brk", -w / 2 + 0.03, w / 2 - 0.03, 0.0, 0.25, -0.03, 0.0), "black_iron")]
    return K.part(name, out)


@register("MeterElectric", 500, kind="wallmount")
def meter_electric(name="MeterElectric"):
    out = [K.trim(G.prism(name + "_base", G.rrect(0.28, 0.38, 0.03), 0.0, 0.10), "galvanised"),
           K.trim(G.cyl(name + "_ring", (0, 0.10, 0.0), (0, 0.11, 0.0), 0.095, segs=20), "galvanised")]
    # prism is in XY: turn the base to stand on the wall (its 0.38 height along Z)
    b = out[0]
    for v in b.data.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z
        v.co = Vector((x, z, y + 0.19))
    b.data.update()
    out[1].location = (0, 0, 0.19)
    G.bake_xform(out[1])
    dome = G.lathe(name + "_dome", [(0.0, 0.0), (0.085, 0.0), (0.085, 0.07), (0.07, 0.10), (0.0, 0.11)], segs=20)
    dome.matrix_world = G.along((0, 0.11, 0.19), (0, 1, 0))
    G.bake_xform(dome)
    out.append(K.cell(dome, "meter_face"))
    out.append(K.trim(G.cyl(name + "_conduit", (0.0, 0.035, -0.6), (0.0, 0.035, 0.0), 0.022, segs=10), "galvanised"))
    return K.part(name, out)


@register("MeterGas", 600, kind="wallmount")
def meter_gas(name="MeterGas"):
    out = [K.trim(G.cyl(name + "_riser", (0.10, 0.18, 0.0), (0.10, 0.18, 0.62), 0.02, segs=10), "galvanised"),
           K.trim(G.cyl(name + "_out", (-0.10, 0.18, 0.62), (-0.10, 0.18, 0.95), 0.02, segs=10), "galvanised"),
           K.trim(G.tube(name + "_tw", [(-0.10, 0.18, 0.95), (-0.10, 0.10, 0.95), (-0.10, 0.0, 0.95)], 0.02, segs=10), "galvanised"),
           K.trim(box(name + "_body", -0.18, 0.18, 0.07, 0.29, 0.62, 0.92), "galvanised"),
           K.cell(box(name + "_dial", -0.06, 0.06, 0.29, 0.292, 0.70, 0.80), "dial_gauge"),
           K.trim(box(name + "_reg", 0.03, 0.17, 0.12, 0.24, 0.45, 0.58), "galvanised")]
    return K.part(name, out)


# ------------------------------------------------------------------ trim runs (used by the house builder; a sample each)

@register("CasingBrickMould", 60, kind="linear")
def casing_brick(name="CasingBrickMould", length=1.0):
    sec = [(0.0, 0.0), (0.051, 0.0), (0.051, 0.014), (0.040, 0.026), (0.022, 0.032), (0.0, 0.032)]
    ob = G.sweep(name + "_r", [(0, 0, 0), (0, 0, length)], [(u, v) for (u, v) in sec], twist_up=(0, 1, 0))
    return K.part(name, [K.trim(ob, "paint_smooth", TRIM_S)])


@register("CasingFlat", 24, kind="linear")
def casing_flat(name="CasingFlat", length=1.0):
    return K.part(name, [K.trim(box(name + "_r", -0.0445, 0.0445, 0.0, 0.019, 0.0, length), "paint_grain", TRIM_S)])


@register("SillCastStone", 40, kind="opening")
def sill_cast(name="SillCastStone", width=1.10):
    import bmesh
    bm = bmesh.new()
    pts = [(-width / 2, -0.03, 0.0), (width / 2, -0.03, 0.0), (width / 2, 0.07, 0.0), (-width / 2, 0.07, 0.0),
           (-width / 2, -0.03, 0.10), (width / 2, -0.03, 0.10), (width / 2, 0.07, 0.075), (-width / 2, 0.07, 0.075)]
    v = [bm.verts.new(p) for p in pts]
    for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([v[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return K.part(name, [K.trim(G.mesh_obj(name + "_s", bm), "cast_stone")])


@register("CornerBoard", 24, kind="linear")
def corner_board(name="CornerBoard", length=1.0):
    out = [K.trim(box(name + "_a", 0.0, 0.089, 0.0, 0.025, 0.0, length), "paint_grain", TRIM_S),
           K.trim(box(name + "_b", -0.025, 0.0, -0.089 + 0.025, 0.025, 0.0, length), "paint_grain", TRIM_S)]
    return K.part(name, out)


@register("Fascia", 24, kind="linear")
def fascia(name="Fascia", length=1.0):
    return K.part(name, [K.trim(box(name + "_r", -length / 2, length / 2, 0.0, 0.025, -0.14, 0.0), "paint_smooth", TRIM_S)])
