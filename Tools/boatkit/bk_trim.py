"""Trim-sheet UVs for the hardware kit (boat fidelity 2): every face lands on its surface kind's band of the shared
10 px/cm sheet (make_trim_sheet.py, Inputs/boat-kit/trim.json) at true scale, and a badge lands whole on its brand plate.

- Faces carry a FACE int attribute `trim` (0 = by material slot, 1..8 = a band by index + 1, 100 + n + 1000 k = plate
  cell n, badge k),
  set by `mark` on a piece before bk_geom.join (bmesh keeps it; unmarked pieces read 0).
- `assign` box-projects each face on its dominant axis in metres, U along the longer of the part's two other axes (a
  tube's length runs along the band), shifts each face inside its band (bands tile within their height, so the shift
  is invisible) and squeezes the rare face taller than a band. Plate faces are fitted, as a group, into their cell.
- UVs follow Blender's convention (v up); Unreal's FBX import flips V onto the texture's rows.
"""
import json
import os

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TRIM = json.load(open(os.path.join(HERE, "..", "..", "Inputs", "boat-kit", "trim.json")))
BANDS = list(TRIM["bands"])               # in the sheet's order
CELLS = list(TRIM["cells"])
W, H = TRIM["size_px"]
PPM = TRIM["px_per_m"]
BAND_H = TRIM["band_h_px"]

# The band each material slot (phase 1's surface kinds) maps onto when a face isn't marked.
SLOT_BAND = {
    "Stainless": "brushed", "Aluminium": "anodised", "MastAluminium": "anodised", "BlackPlastic": "textured",
    "Rubrail": "grip", "Carbon": "carbon", "CarbonMatte": "carbon", "CarbonMast": "carbon",
    "CabinWindow": "smooth", "Deck": "smooth", "Topsides": "smooth", "Teak": "smooth", "Wood": "smooth",
}


def _attr(me):
    a = me.attributes.get("trim")
    if a is None:
        a = me.attributes.new("trim", "INT", "FACE")
    return a


def mark(ob, band=None, cell=None, inst=0):
    """Mark every face of a piece: a band by name, or a plate cell by name (`inst` tells apart badges sharing a cell,
    each fitted into the cell on its own)."""
    v = BANDS.index(band) + 1 if band else 100 + CELLS.index(cell) + 1000 * inst
    a = _attr(ob.data)
    for i in range(len(ob.data.polygons)):
        a.data[i].value = v
    return ob


def _axes(n, long_axis):
    """The two projection axes for a face with normal n: drop the dominant one, U along the part's long axis if kept."""
    k = max(range(3), key=lambda i: abs(n[i]))
    keep = [i for i in range(3) if i != k]
    if long_axis in keep and keep[0] != long_axis:
        keep.reverse()
    return k, keep[0], keep[1]


def assign(ob):
    me = ob.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    uv = me.uv_layers.new(name="UVMap")
    lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in me.vertices) for i in range(3)])
    long_axis = max(range(3), key=lambda i: hi[i] - lo[i])
    marks = _attr(me)
    slots = [m.name if m else "" for m in me.materials]
    groups = {}
    for p in me.polygons:
        tag = marks.data[p.index].value
        if tag >= 100:
            groups.setdefault(tag, []).append(p)
            continue
        band = BANDS[tag - 1] if tag else SLOT_BAND.get(slots[p.material_index] if slots else "", "smooth")
        b = TRIM["bands"][band]
        _, ua, va = _axes(p.normal, long_axis)
        pts = [(me.vertices[me.loops[li].vertex_index].co[ua] * PPM, me.vertices[me.loops[li].vertex_index].co[va] * PPM) for li in p.loop_indices]
        vmin = min(q[1] for q in pts)
        vext = max(q[1] for q in pts) - vmin
        squeeze = min(1.0, (BAND_H - 2) / vext) if vext > 0 else 1.0
        # Keep the face's place in the band's period (neighbours line up) unless that would run it off the band.
        base = vmin - (vmin % BAND_H)
        if squeeze < 1.0 or (vmin - base) + vext > BAND_H - 1:
            base = vmin
        for li, (u, v) in zip(p.loop_indices, pts):
            vp = b["v0_px"] + 1 + (v - base) * squeeze if squeeze < 1.0 else b["v0_px"] + (v - base)
            uv.data[li].uv = (u / W, 1.0 - vp / H)
    for tag, faces in groups.items():
        cell = TRIM["cells"][CELLS[(tag - 100) % 1000]]
        x, y, cw, ch = cell["rect_px"]
        n = sum((p.normal for p in faces), Vector())
        _, ua, va = _axes(n, long_axis)
        pts = {li: (me.vertices[me.loops[li].vertex_index].co[ua], me.vertices[me.loops[li].vertex_index].co[va]) for p in faces for li in p.loop_indices}
        u0, u1 = min(q[0] for q in pts.values()), max(q[0] for q in pts.values())
        v0, v1 = min(q[1] for q in pts.values()), max(q[1] for q in pts.values())
        for li, (u, v) in pts.items():
            fu = (u - u0) / max(u1 - u0, 1e-9)
            fv = (v - v0) / max(v1 - v0, 1e-9)
            uv.data[li].uv = ((x + 2 + fu * (cw - 4)) / W, 1.0 - (y + 2 + (1 - fv) * (ch - 4)) / H)
    return ob
