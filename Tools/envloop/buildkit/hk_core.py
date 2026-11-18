"""Core of the building parts kit (Track E): slots, face marks, and the finish pass that writes every part's UVs and
vertex colours to the contract in slots.json.

Geometry comes from the boat kit's helpers (Tools/boatkit/bk_geom.py: prism, lathe, sweep, bevel, join), imported, not
copied. A piece is marked before it is joined into its part:

    trim(ob, "vinyl", paint=SASH)      a Trim face on a trim-sheet band, painted by a role (slots.json paint_roles)
    cell(ob, "fan_grille")             a Trim face mapped whole onto a cell of the sheet
    wall(ob, finish)  / roof(ob, finish)
    pane(ob, seed, obscure, door)      Glass (each pane gets its own id, so its UV0 runs 0..1 over it)

`finish_part(ob)` then writes UV0 (trim sheet at true scale, pane-local, wall metres or roof metres), UV1 (pane size in
metres on glass) and the colour attribute (R paint role, G finish or window seed, B obscure, A door light).
Conventions: metres, Z up; a part's origin on the wall plane at the bottom centre of its opening (or its mount point),
+Y out of the wall, +X along the wall to the right seen from outside.
"""
import json
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "boatkit"))
import bk_geom as G  # noqa: E402  (the boat kit's primitives)

TRIM = json.load(open(os.path.join(HERE, "trim.json")))
SLOTS_DEF = json.load(open(os.path.join(HERE, "slots.json")))
SIZES = json.load(open(os.path.join(HERE, "sizes.json")))["parts"]
BANDS = sorted(TRIM["bands"], key=lambda b: TRIM["bands"][b]["index"])
CELLS = list(TRIM["cells"])
TW, TH = TRIM["size_px"]
PPM = TRIM["px_per_m"]
BAND_H = TRIM["band_h_px"]

SLOTS = ["Trim", "Glass", "Wall", "Roof"]
TRIM_S, DOOR, SHUTTER, SASH, GARAGE, METAL, FIXED = range(7)    # paint roles
WALL_FINISH = {f["name"]: f["id"] for f in SLOTS_DEF["wall_finishes"]}
ROOF_FINISH = {f["name"]: f["id"] for f in SLOTS_DEF["roof_finishes"]}
_pane_counter = [0]


def mat(slot):
    m = bpy.data.materials.get(slot)
    if m is None:
        m = bpy.data.materials.new(slot)
    return m


def _attr(me, name, kind="INT"):
    a = me.attributes.get(name)
    if a is None:
        a = me.attributes.new(name, kind, "FACE")
    return a


def _mark(ob, slot, **vals):
    me = ob.data
    me.materials.clear()
    me.materials.append(mat(slot))
    for p in me.polygons:
        p.material_index = 0
    for k, v in vals.items():
        a = _attr(me, k, "FLOAT" if isinstance(v, float) else "INT")
        for i in range(len(me.polygons)):
            a.data[i].value = v
    return ob


def trim(ob, band, paint=TRIM_S):
    """Trim on a band by name; bands whose sheet mask is 0 ignore the paint role (they keep the sheet's colour)."""
    if TRIM["bands"][band]["paint"] == 0:
        paint = FIXED
    return _mark(ob, "Trim", band=BANDS.index(band) + 1, paint=paint)


def cell(ob, name, paint=FIXED):
    return _mark(ob, "Trim", band=100 + CELLS.index(name), paint=paint)


def wall(ob, finish="brick_red"):
    return _mark(ob, "Wall", finish=WALL_FINISH[finish] if isinstance(finish, str) else int(finish))


def roof(ob, finish="shingle_charcoal"):
    return _mark(ob, "Roof", finish=ROOF_FINISH[finish] if isinstance(finish, str) else int(finish))


def pane(ob, seed=0.5, obscure=0, door=0):
    _pane_counter[0] += 1
    return _mark(ob, "Glass", pane=_pane_counter[0], seedf=float(seed), obscure=obscure, doorlite=door)


# ------------------------------------------------------------------ shapes used everywhere

def box(name, x0, x1, y0, y1, z0, z1):
    return G.prism(name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1)


def quad_xz(name, x0, x1, z0, z1, y):
    """A single quad in the wall plane at depth y, facing +Y (out)."""
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.y < 0:
        f.normal_flip()
    return G.mesh_obj(name, bm)


def ring_frame(name, x0, x1, z0, z1, width, y0, y1, bottom_w=None):
    """A rectangular frame (four bars) around an opening, outside edge x0..x1, z0..z1, bars `width` wide, depth y0..y1."""
    bw = bottom_w if bottom_w is not None else width
    bars = [box(f"{name}_l", x0, x0 + width, y0, y1, z0, z1), box(f"{name}_r", x1 - width, x1, y0, y1, z0, z1),
            box(f"{name}_t", x0 + width, x1 - width, y0, y1, z1 - width, z1),
            box(f"{name}_b", x0 + width, x1 - width, y0, y1, z0, z0 + bw)]
    return bars


def finish_obj(ob, bevel=0.0):
    return G.finish(ob, bevel, segs=1 if bevel < 0.004 else 2, angle=40.0)


# ------------------------------------------------------------------ the finish pass: UVs and colours

def _axes(n, long_axis):
    k = max(range(3), key=lambda i: abs(n[i]))
    keep = [i for i in range(3) if i != k]
    if long_axis in keep and keep[0] != long_axis:
        keep.reverse()
    return k, keep[0], keep[1]


def finish_part(ob):
    """Write UV0, UV1 and the colour attribute for every face by its slot (see the module docstring)."""
    me = ob.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    uv0 = me.uv_layers.new(name="UVMap")
    uv1 = me.uv_layers.new(name="UVPane")
    col = me.color_attributes.get("Col") or me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    slots = [m.name if m else "Trim" for m in me.materials]
    get = lambda n: me.attributes.get(n)
    A = {n: get(n) for n in ("band", "paint", "finish", "pane", "seedf", "obscure", "doorlite")}
    val = lambda n, i, d=0: (A[n].data[i].value if A[n] is not None else d)
    lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in me.vertices) for i in range(3)])
    long_axis = max(range(3), key=lambda i: hi[i] - lo[i])
    panes, cells = {}, {}
    for p in me.polygons:
        slot = slots[p.material_index] if slots else "Trim"
        i = p.index
        if slot == "Glass":
            panes.setdefault(val("pane", i), []).append(p)
            continue
        if slot == "Trim" and val("band", i) >= 100:
            cells.setdefault(val("band", i), []).append(p)
            continue
        pts = [me.vertices[me.loops[li].vertex_index].co for li in p.loop_indices]
        if slot == "Trim":
            band = BANDS[max(val("band", i), 1) - 1]
            b = TRIM["bands"][band]
            # A face whose own long side is not the part's still runs U along its own longest extent.
            k = max(range(3), key=lambda a: abs(p.normal[a]))
            keep = [a for a in range(3) if a != k]
            ext = [max(q[a] for q in pts) - min(q[a] for q in pts) for a in keep]
            if long_axis in keep:
                ua = long_axis if ext[keep.index(long_axis)] >= 0.5 * max(ext) else keep[ext.index(max(ext))]
            else:
                ua = keep[ext.index(max(ext))]
            va = [a for a in keep if a != ua][0]
            q2 = [(q[ua] * PPM, q[va] * PPM) for q in pts]
            vmin = min(q[1] for q in q2)
            vext = max(q[1] for q in q2) - vmin
            squeeze = min(1.0, (BAND_H - 2) / vext) if vext > 0 else 1.0
            base = vmin - (vmin % BAND_H)
            if squeeze < 1.0 or (vmin - base) + vext > BAND_H - 1:
                base = vmin
            for li, (u, v) in zip(p.loop_indices, q2):
                vp = b["v0_px"] + 1 + (v - base) * squeeze if squeeze < 1.0 else b["v0_px"] + (v - base)
                uv0.data[li].uv = (u / TW, 1.0 - vp / TH)
            c = (val("paint", i) / 255.0, 0.0, 0.0, 1.0)
        elif slot == "Wall":
            n = p.normal
            horiz = Vector((-n.y, n.x, 0.0))
            if horiz.length < 1e-4:
                horiz = Vector((1, 0, 0))
            horiz.normalize()
            for li in p.loop_indices:
                q = me.vertices[me.loops[li].vertex_index].co
                uv0.data[li].uv = (q.dot(horiz), q.z) if abs(n.z) < 0.7 else (q.x, q.y)
            c = (0.0, val("finish", i) / 255.0, 0.0, 1.0)
        else:   # Roof: U along the eave (horizontal in the plane), V up the slope from the face's lowest point
            n = p.normal
            along = Vector((-n.y, n.x, 0.0))
            if along.length < 1e-4:
                along = Vector((1, 0, 0))
            along.normalize()
            up = n.cross(along).normalized()
            if up.z < 0:
                up = -up
            zmin = min(q.z for q in pts)
            for li in p.loop_indices:
                q = me.vertices[me.loops[li].vertex_index].co
                uv0.data[li].uv = (q.dot(along), (q.z - zmin) / max(up.z, 1e-3))
            c = (0.0, val("finish", i) / 255.0, 0.0, 1.0)
        for li in p.loop_indices:
            col.data[li].color = c
            uv1.data[li].uv = (0.0, 0.0)
    for pid, faces in panes.items():
        n = sum((f.normal for f in faces), Vector()).normalized()
        right = Vector((-n.y, n.x, 0.0))
        if right.length < 1e-4:
            right = Vector((1, 0, 0))
        right.normalize()
        up = n.cross(right).normalized() if abs(n.z) < 0.9 else Vector((0, 1, 0))
        pts = {li: me.vertices[me.loops[li].vertex_index].co for f in faces for li in f.loop_indices}
        us = {li: q.dot(right) for li, q in pts.items()}
        vs = {li: q.dot(up) for li, q in pts.items()}
        u0, u1, v0, v1 = min(us.values()), max(us.values()), min(vs.values()), max(vs.values())
        w, h = max(u1 - u0, 1e-6), max(v1 - v0, 1e-6)
        f0 = faces[0].index
        c = (0.0, val("seedf", f0, 0.5), float(val("obscure", f0)), float(val("doorlite", f0)))
        for li in pts:
            uv0.data[li].uv = ((us[li] - u0) / w, (vs[li] - v0) / h)
            uv1.data[li].uv = (w, h)
            col.data[li].color = c
    for tag, faces in cells.items():
        x, y, cw, ch = TRIM["cells"][CELLS[tag - 100]]["rect_px"]
        n = sum((f.normal for f in faces), Vector())
        _, ua, va = _axes(n, long_axis)
        pts = {li: me.vertices[me.loops[li].vertex_index].co for f in faces for li in f.loop_indices}
        u0, u1 = min(q[ua] for q in pts.values()), max(q[ua] for q in pts.values())
        v0, v1 = min(q[va] for q in pts.values()), max(q[va] for q in pts.values())
        for li, q in pts.items():
            fu = (q[ua] - u0) / max(u1 - u0, 1e-9)
            fv = (q[va] - v0) / max(v1 - v0, 1e-9)
            uv0.data[li].uv = ((x + 2 + fu * (cw - 4)) / TW, 1.0 - (y + 2 + (1 - fv) * (ch - 4)) / TH)
            uv1.data[li].uv = (0.0, 0.0)
            col.data[li].color = (FIXED / 255.0, 0.0, 0.0, 1.0)
    # Keep the slot order fixed (Trim, Glass, Wall, Roof) so every part's FBX lists them the same way.
    return ob


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def part(name, pieces, sockets=(), bevel_done=True):
    """Join marked pieces into one part, write UVs and colours, add sockets {name: (x, y, z)}."""
    ob = G.join(name, pieces)
    finish_part(ob)
    for s, loc in dict(sockets).items():
        G.socket(ob, s, loc)
    return ob
