"""Clutch: a single lever rope clutch (part detail loop, Nov 2026: docs/part-detail-loop/clutch.md).

The "Rope Jammer" from Bean's hardware reference sheet: a lever clutch for 6 to 12 mm line, the kind that holds a
halyard or a control line on a cabin top so the winch can be freed. Built to catalogue sizes (a 6-12 mm single
clutch: 125 mm long, about 62 to 72 mm high, 32 to 40 mm wide) and the shape read off Bean's sheet: two side plates,
tall at the tail end and sloping down to the load end, each edged with a bright strip and held by four screw heads; a
lever along the top, hinged at the low end, with a ribbed grip that overhangs the tall end; an open mouth under the
grip that shows the toothed cam and a red line guide; a red release button and a moulded groove on each plate.
Generic TERNWAY design (no maker's shapes copied beyond what every lever clutch shares, no logos).

It lives in its own file so threads working on other parts don't touch the same lines: bk_parts imports every
bk_part_*.py at its end, and the @part below replaces bk_parts' older box clutch of the same name.
Conventions follow bk_parts: origin at the middle of the underside, +Z up, the line along X. The tall (tail) end with
the grip and the mouth is at -X, where the line leaves for the winch; the load comes in at the low end, +X.
"""
import math

from mathutils import Matrix

import bk_geom as G
import bk_parts as P

MM = 0.001

# side outline (x, z) in mm, counter-clockwise from the aft foot; the radius rounds that corner (0 = sharp)
_SIDE = [((-62.5, 0.0), 0), ((60.0, 0.0), 0), ((62.5, 3.0), 1.5), ((62.5, 34.0), 3), ((57.0, 39.0), 5),
         ((-42.0, 60.0), 8), ((-53.0, 59.5), 5), ((-62.5, 10.0), 3)]
# round 2: the low end raised from 26 to 50 mm and the tall end raked back, after round 1's outline matched Bean's photo
# only 81% (photo_outline.py; the old box clutch scored 89%): the photo's plates are nearly parallel-sided, the slope is
# mostly the lever. Round 5: the low end back down to 39 mm, all three blind reviewers of round 4 asked for a clear
# wedge (tallest at the grip end); the outline still passes
_W = 36.0          # across the plates (catalogues: 32 to 40 mm for a single; round 7: 38 measured 40.3 with the screw heads)
_T_PLATE = 3.5     # side plate
_T_RIM = 1.0       # the bright strip between each plate and the body
_RIM = 0.8         # how far the strip stands out past the plate's edge
_LINE_Z = 11.5     # the line's centre above the deck (round 5: lower, reviewers saw it run mid-height)
_LINE_R = 6.2      # the bore (10 mm line, 12 mm max)
_HANDLE_T = 7.5    # lever thickness
_FIT = 0.974       # whole-part scale to the catalogue's 125 mm overall


def _rounded(corners, n=5):
    """A polygon with each corner rounded by its radius (corners: [((x, z), r)])."""
    out = []
    k = len(corners)
    for i, (p, r) in enumerate(corners):
        if r <= 0:
            out.append(p)
            continue
        a, b = corners[i - 1][0], corners[(i + 1) % k][0]
        u = (a[0] - p[0], a[1] - p[1])
        v = (b[0] - p[0], b[1] - p[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        u, v = (u[0] / lu, u[1] / lu), (v[0] / lv, v[1] / lv)
        ang = math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))
        d = min(r / math.tan(ang / 2), lu * 0.45, lv * 0.45)
        r = d * math.tan(ang / 2)
        t0 = (p[0] + u[0] * d, p[1] + u[1] * d)
        t1 = (p[0] + v[0] * d, p[1] + v[1] * d)
        bis = (u[0] + v[0], u[1] + v[1])
        lb = math.hypot(*bis)
        c = (p[0] + bis[0] / lb * r / math.sin(ang / 2), p[1] + bis[1] / lb * r / math.sin(ang / 2))
        a0 = math.atan2(t0[1] - c[1], t0[0] - c[0])
        a1 = math.atan2(t1[1] - c[1], t1[0] - c[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        out += [(c[0] + r * math.cos(a0 + da * j / n), c[1] + r * math.sin(a0 + da * j / n)) for j in range(n + 1)]
    return out


def _offset(poly, d):
    """A convex counter-clockwise outline moved out by d (in by -d), corner points pushed along their bisectors. Moving
    a rounded outline in by more than its corner radii folds the arcs over: inset the sharp corners, then round them."""
    out = []
    k = len(poly)
    for i, p in enumerate(poly):
        a, b = poly[i - 1], poly[(i + 1) % k]
        n1 = (p[1] - a[1], -(p[0] - a[0]))
        n2 = (b[1] - p[1], -(b[0] - p[0]))
        l1, l2 = math.hypot(*n1) or 1, math.hypot(*n2) or 1
        n = (n1[0] / l1 + n2[0] / l2, n1[1] / l1 + n2[1] / l2)
        ln = math.hypot(*n) or 1
        cosh = max(0.5, (n[0] / ln) * (n1[0] / l1) + (n[1] / ln) * (n1[1] / l1))
        out.append((p[0] + n[0] / ln * d / cosh, p[1] + n[1] / ln * d / cosh))
    return out


def _mm(poly):
    return [(x * MM, z * MM) for x, z in poly]


def _top_z(x):
    """Height of the plates' sloping top at x (mm), between the low end's shoulder and the tall end's corner."""
    (x0, z0), (x1, z1) = _SIDE[4][0], _SIDE[5][0]
    return z0 + (z1 - z0) * (x - x0) / (x1 - x0)


def _clutch_parts():
    alu, plastic, steel, red = P.M("Aluminium"), P.M("BlackPlastic"), P.M("Stainless"), P.M("Graphics")
    # round 3: the side plates satin charcoal (hard-anodised look) so the bright strip, screws and red button read
    # against them; round 2's aluminium plates went white in the preview and lost every detail
    satin = P.M("CarbonMatte")
    objs = []
    side = _rounded(_SIDE)
    yi = _W / 2 - _T_PLATE - _T_RIM          # body half width (inner face of the strips)
    ys = yi + _T_RIM                          # strip outer face = plate inner face
    slope = math.atan2(_SIDE[5][0][1] - _SIDE[4][0][1], _SIDE[5][0][0] - _SIDE[4][0][0])   # top, rising to -X

    # body: the moulded core between the plates, its top a little under the plates' so the lever sits down in it
    inner = _rounded(list(zip(_offset([c for c, _ in _SIDE], -2.2), [max(r - 2.2, 0.8) if r else 0 for _, r in _SIDE])))
    core = P._xz_prism("body", _mm(inner), -yi * MM, yi * MM, plastic)
    # the line's bore along X, and the mouth under the grip: an open pocket in the tall end showing cam and guide
    G.boolean(core, G.cyl("bore", (-0.08, 0, _LINE_Z * MM), (0.08, 0, _LINE_Z * MM), _LINE_R * MM, plastic, 28))
    mouth = [(-70.0, 5.0), (-49.0, 5.0), (-49.0, 30.0), (-53.0, 44.0), (-70.0, 44.0)]
    G.boolean(core, P._xz_prism("mouthcut", _mm(mouth), -(yi + 1) * MM, (yi + 1) * MM, plastic))
    objs.append(G.finish(core, 0.0012, segs=2))

    # toothed cam in the mouth, pressing down on the line: ten deep teeth on its lower arc, set forward into the mouth so
    # they show. Round 6: a black cam with bright teeth (all six reviewers of rounds 4 and 5 saw a smooth roller: round 4's
    # was all black, round 5's all stainless)
    cam_c, cam_r = (-53.0, _LINE_Z + _LINE_R + 7.5), 8.0
    cy = yi - 1.5
    cam = G.cyl("cam", (cam_c[0] * MM, -cy * MM, cam_c[1] * MM), (cam_c[0] * MM, cy * MM, cam_c[1] * MM), cam_r * MM, plastic, 32)
    objs.append(G.finish(cam, 0.0005, segs=2))
    teeth = []
    for j in range(10):
        a0 = math.radians(-170 + j * 16)
        da = math.radians(6.5)
        teeth.append((cam_c[0] + (cam_r - 0.2) * math.cos(a0 - da), cam_c[1] + (cam_r - 0.2) * math.sin(a0 - da)))
        teeth.append((cam_c[0] + (cam_r + 3.0) * math.cos(a0), cam_c[1] + (cam_r + 3.0) * math.sin(a0)))
        teeth.append((cam_c[0] + (cam_r - 0.2) * math.cos(a0 + da), cam_c[1] + (cam_r - 0.2) * math.sin(a0 + da)))
    for j in range(10):
        tri = teeth[3 * j:3 * j + 3]
        objs.append(G.finish(P._xz_prism(f"camtooth{j}", _mm(tri), -(cy - 0.8) * MM, (cy - 0.8) * MM, steel), 0, weighted=False))
    # cam axle bosses on the plates' inner faces are hidden; its pin shows as a cap on each plate
    # line guides: a red flared bush at the mouth, a black one at the load end
    for nm, x0, x1, mat in (("guide_tail", -58.0, -50.0, red), ("guide_load", 60.2, 55.0, plastic)):
        s = 1 if x1 > x0 else -1
        g = G.lathe(nm, [(_LINE_R * MM, 0), (_LINE_R * 1.55 * MM, 0), (_LINE_R * 1.35 * MM, 1.2 * MM), (_LINE_R * 1.1 * MM, abs(x1 - x0) * MM),
                         (_LINE_R * 0.98 * MM, abs(x1 - x0) * MM), (_LINE_R * 0.98 * MM, 0.1 * MM)], mat, 32)
        g.matrix_world = G.along((x0 * MM, 0, _LINE_Z * MM), (s, 0, 0))
        G.bake_xform(g)
        objs.append(G.finish(g, 0, weighted=False, sharp=50))

    # the bright strip and the side plate, both sides; the plate carries the groove, the release button's recess,
    # the lock window and four screw heads
    btn_c = (-36.0, 24.0)
    for sy in (-1, 1):
        rim = P._xz_prism(f"strip{sy}", _mm([(x, max(z, 0.0)) for x, z in _offset(side, _RIM)]), (sy * yi if sy > 0 else -ys) * MM, (ys if sy > 0 else -yi) * MM, steel)
        objs.append(G.finish(rim, 0.0003, segs=1))
        y0, y1 = (ys, ys + _T_PLATE) if sy > 0 else (-ys - _T_PLATE, -ys)
        plate = P._xz_prism(f"sideplate{sy}", _mm(side), y0 * MM, y1 * MM, satin)
        yo = (y1 if sy > 0 else y0)                          # outer face
        dep = 1.6
        cy0, cy1 = (yo - dep, yo + 1) if sy > 0 else (yo - 1, yo + dep)
        groove = P._capsule((-4.0, 15.0), (44.0, 29.0), 3.2, 6)
        G.boolean(plate, P._xz_prism(f"groove{sy}", _mm(groove), cy0 * MM, cy1 * MM, alu))
        # the button's recess and the lock window, set square to the sloping top
        for nm, c, w, h in (("btnwell", btn_c, 17.0, 8.5), ("lockwin", (-17.0, 29.0), 8.0, 5.0)):
            rr = [(c[0] + x * math.cos(slope) - z * math.sin(slope), c[1] + x * math.sin(slope) + z * math.cos(slope))
                  for x, z in G.rrect(w, h, h * 0.45, 4)]
            G.boolean(plate, P._xz_prism(f"{nm}{sy}", _mm(rr), cy0 * MM, cy1 * MM, alu))
        objs.append(G.finish(plate, 0.0007, segs=2))
        # red release button standing 0.8 mm proud of the face in its recess
        btn = [(btn_c[0] + x * math.cos(slope) - z * math.sin(slope), btn_c[1] + x * math.sin(slope) + z * math.cos(slope))
               for x, z in G.rrect(14.5, 6.2, 3.0, 5)]
        by0, by1 = (yo - dep, yo + 0.8) if sy > 0 else (yo - 0.8, yo + dep)
        objs.append(G.finish(P._xz_prism(f"release{sy}", _mm(btn), by0 * MM, by1 * MM, red), 0.0004, segs=2))
        # two tick marks in the lock window (open / locked)
        for k, dx in enumerate((-2.0, 2.0)):
            c = (-17.0 + dx * math.cos(slope), 29.0 + dx * math.sin(slope))
            tk = [(c[0] + x * math.cos(slope) - z * math.sin(slope), c[1] + x * math.sin(slope) + z * math.cos(slope))
                  for x, z in G.rrect(0.9, 3.0, 0.3, 2)]
            ty0, ty1 = (yo - dep, yo - dep + 0.3) if sy > 0 else (yo + dep - 0.3, yo + dep)
            objs.append(G.finish(P._xz_prism(f"tick{sy}{k}", _mm(tk), ty0 * MM, ty1 * MM, steel), 0, weighted=False))
        # screw heads (socket-head, domed), heads out along the plate's normal
        for k, (sx, sz) in enumerate(((-53.0, 8.0), (52.0, 7.5), (50.0, 30.0), (-46.0, 49.0))):
            h = G.lathe(f"screw{sy}{k}", [(0, 0), (3.7 * MM, 0), (3.5 * MM, 0.8 * MM), (2.4 * MM, 1.45 * MM), (0, 1.55 * MM)], steel, 20)
            h.matrix_world = G.along((sx * MM, yo * MM, sz * MM), (0, sy, 0))
            G.bake_xform(h)
            objs.append(G.finish(h, 0, weighted=False))
            hx = G.cyl(f"hex{sy}{k}", (sx * MM, (yo + sy * 1.0) * MM, sz * MM), (sx * MM, (yo + sy * 1.65) * MM, sz * MM), 1.4 * MM, plastic, 6)
            objs.append(G.finish(hx, 0, weighted=False))

    # lever: a hood along the sloping top from the hinge at the low end to the grip at the tall end. Round 4: the grip
    # end turns down into a visor over the mouth (Bean's photo: a deep ribbed grip block, not a thin slab), and the
    # hood thickens toward it
    xh, xg = 50.0, -64.5
    zb = lambda x: _top_z(x) - 2.6                       # lever underside: seated 2.6 mm into the body
    top_at = lambda x: zb(x) + 4.5 + (_HANDLE_T + 3.0 - 4.5) * (xh + 4.0 - x) / (xh + 4.0 - xg)
    xv, drop = -54.0, 14.0                               # the visor's inner face and how far it hangs below the hood
    lever = [((xh + 4.0, zb(xh + 4.0)), 2.0), ((xv, zb(xv)), 1.0), ((xv, zb(xv) - drop), 1.5), ((xg + 1.0, zb(xv) - drop), 1.5),
             ((xg, zb(xv) - drop + 3.0), 1.0), ((xg, top_at(xg)), 3.0), ((xh + 4.0, top_at(xh + 4.0)), 3.0)]
    lever = _rounded(lever, 4)
    hw = _W / 2 - 0.4
    lv = P._xz_prism("lever", _mm(lever), -hw * MM, hw * MM, alu)
    objs.append(G.finish(lv, 0.0012, segs=2))
    # grip block: round 5 caps the grip end in satin charcoal so it reads as a separate chunky grip (reviewers: too thin,
    # too white), with ribs across its face and top
    gb = [((xv + 3.0, zb(xv)), 1.0), ((xv + 3.0, zb(xv) - drop - 0.5), 0), ((xg - 0.6, zb(xv) - drop - 0.5), 1.5),
          ((xg - 0.6, top_at(xg) + 0.6), 2.5), ((xg + 16.0, top_at(xg + 16.0) + 0.6), 1.5), ((xg + 16.0, zb(xg + 16.0) + 1.0), 0)]
    gblk = P._xz_prism("gripblock", _mm(_rounded(gb, 3)), -(hw + 0.3) * MM, (hw + 0.3) * MM, satin)
    objs.append(G.finish(gblk, 0.0010, segs=2))
    for k in range(5):
        z = zb(xv) - drop + 4.0 + k * 3.3
        rib = G.cyl(f"rib{k}", ((xg - 0.8) * MM, -(hw - 1.5) * MM, z * MM), ((xg - 0.8) * MM, (hw - 1.5) * MM, z * MM), 1.05 * MM, satin, 10)
        objs.append(G.finish(rib, 0, weighted=False))
    for k in range(3):
        x = xg + 4.0 + k * 3.6
        rib = G.cyl(f"ribtop{k}", (x * MM, -(hw - 1.5) * MM, (top_at(x) + 1.2) * MM), (x * MM, (hw - 1.5) * MM, (top_at(x) + 1.2) * MM),
                    1.05 * MM, satin, 10)
        objs.append(G.finish(rib, 0, weighted=False))
    # hinge pin through the plates at the low end, with its caps on the plates
    pz = zb(xh) + 2.5
    objs.append(G.finish(G.cyl("hinge", (xh * MM, -(ys + _T_PLATE + 0.8) * MM, pz * MM), (xh * MM, (ys + _T_PLATE + 0.8) * MM, pz * MM), 2.6 * MM, steel, 20), 0.0003))
    # maker's plate on the lever's top, laid along its slope
    xm = -2.0
    tilt = -math.atan((top_at(xm + 1) - top_at(xm - 1)) / 2.0)
    objs.append(P.badge("plate", "Plate", 0.030, 0.011, Matrix.Translation((xm * MM, 0, top_at(xm) * MM)) @ Matrix.Rotation(tilt, 4, "Y"), plastic))
    socks = [("LineIn", (0.0625, 0, _LINE_Z * MM)), ("LineOut", (-0.0625, 0, _LINE_Z * MM)),
             ("Grip", (xg * MM, 0, top_at(xg) * MM)), ("Hinge", (xh * MM, 0, pz * MM)),
             ("BoltFwd", (0.0395, 0, 0)), ("BoltAft", (-0.0395, 0, 0))]
    return objs, socks


@P.part("Clutch", "rope", "Single lever rope clutch for 6 to 12 mm line: side plates with a bright edge, lever with a ribbed grip, "
        "toothed cam and red line guide in the mouth, red release button")
def clutch():
    objs, socks = _clutch_parts()
    # drawn about 3% long (the lever's overhang and the strips push it past the plates): fit to 125 mm overall
    k = Matrix.Scale(_FIT, 4)
    for o in objs:
        o.data.transform(k)
    return P.done("Clutch", objs, [(n, tuple(c * _FIT for c in p)) for n, p in socks])

