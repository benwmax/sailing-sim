"""Ropework for the boats' dock gear (fenders and dock lines pass, Nov 2026: docs/part-detail-loop/docklines.md).

Plain point maths (mathutils only, no bpy) so both the kit parts (bk_part_docking.py) and the berthed dress
(Tools/blender/build_berthed.py) can share it:

  smooth(points)            a Catmull-Rom curve through control points, resampled to an even step
  strands(path, d)          the three strand centrelines of a right-hand (Z-laid) three-strand rope along a path
  eye_splice(...)           a soft eye spliced into a three-strand line: the eye, the throat and the tucked strands
  eye_on_cleat(...)         the eye of a dock line dropped round a horn cleat's base, under both horns
  cleat_hitch(...)          a line made fast on a horn cleat: a turn round the base, figure eights and a locking hitch
  fender_profile(...)       the side profile of a twin-eye vinyl fender (radius along its axis)

Cleat frame (the kit's and the docks' convention): X along the horns, Y across, Z up, origin on the deck under the
cleat's middle. Line sizes are diameters in metres. Dock lines on a 22 ft keelboat are 3/8 in (9.5 mm) three-strand
nylon with a 12 in (305 mm) eye (BoatUS, West Marine, Sea-Dog sizing: 3/8 in for boats to about 27 ft).
"""
import math

from mathutils import Vector

TAU = 2.0 * math.pi


# ------------------------------------------------------------------ curves

def _cr(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def length(path):
    return sum((b - a).length for a, b in zip(path, path[1:]))


def resample(path, step):
    """Even spacing along a polyline (keeps both ends)."""
    path = [Vector(p) for p in path]
    total = length(path)
    n = max(2, int(math.ceil(total / step)) + 1)
    out, seg, acc = [path[0].copy()], 0, 0.0
    for i in range(1, n - 1):
        s = total * i / (n - 1)
        while seg < len(path) - 2 and acc + (path[seg + 1] - path[seg]).length < s:
            acc += (path[seg + 1] - path[seg]).length
            seg += 1
        a, b = path[seg], path[seg + 1]
        L = (b - a).length
        out.append(a.lerp(b, 0.0 if L < 1e-9 else (s - acc) / L))
    out.append(path[-1].copy())
    return out


def smooth(ctrl, step=0.004):
    """A Catmull-Rom curve through the control points (ends held), resampled every `step`."""
    c = [Vector(p) for p in ctrl]
    if len(c) < 3:
        return resample(c, step)
    c = [2 * c[0] - c[1]] + c + [2 * c[-1] - c[-2]]
    dense = []
    for i in range(1, len(c) - 2):
        n = max(4, int((c[i + 1] - c[i]).length / (step * 0.5)) + 1)
        for k in range(n):
            dense.append(_cr(c[i - 1], c[i], c[i + 1], c[i + 2], k / n))
    dense.append(c[-2])
    return resample(dense, step)


def relax(ctrl, step=0.003, iters=6, keep_ends=True):
    """Waypoints joined by straight runs, resampled every `step`, then corners rounded by a few passes of neighbour
    averaging (stays close to the waypoints, unlike a spline through sparse points, which overshoots)."""
    pts = resample([Vector(p) for p in ctrl], step)
    for _ in range(iters):
        pts = [pts[0]] + [(pts[i - 1] + 2 * pts[i] + pts[i + 1]) / 4 for i in range(1, len(pts) - 1)] + [pts[-1]]
    return pts


def sag(a, b, drop, n=24):
    """A line hanging from a to b, `drop` below the straight chord at the middle (a parabola is close enough)."""
    a, b = Vector(a), Vector(b)
    return [a.lerp(b, i / n) - Vector((0, 0, drop * 4 * (i / n) * (1 - i / n))) for i in range(n + 1)]


def frames(path, up=(0, 0, 1)):
    """Rotation-minimising frames (tangent, u, v) along a path."""
    P = [Vector(p) for p in path]
    tans = [(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized() for i in range(len(P))]
    u = Vector(up).cross(tans[0])
    if u.length < 1e-6:
        u = Vector((1, 0, 0)).cross(tans[0])
    u.normalize()
    out = []
    for i, t in enumerate(tans):
        if i:
            u = tans[i - 1].rotation_difference(t) @ u
            u = (u - t * u.dot(t)).normalized()
        out.append((t, u, t.cross(u)))
    return out


def arclen(path):
    s, out = 0.0, [0.0]
    for a, b in zip(path, path[1:]):
        s += (Vector(b) - Vector(a)).length
        out.append(s)
    return out


# ------------------------------------------------------------------ three-strand rope

def strands(path, d, lay=None, phase=0.0, hand=1.0, offset=0.27, step=None, swell=None):
    """Three strand centrelines for a Z-laid (right-hand) three-strand rope of diameter d along `path`.

    Each strand is a helix round the path at offset*d, one full turn every `lay` (3.3 diameters for hard-laid nylon).
    Returns ([pts0, pts1, pts2], strand radius). The strand radius 0.25 d makes the three overlap a little, so the core
    never shows through, and the outside diameter is d."""
    lay = lay or 3.3 * d
    P = resample(path, step or lay / 14.0)
    F = frames(P)
    S = arclen(P)
    out = []
    for k in range(3):
        pts = []
        for p, (t, u, v), s in zip(P, F, S):
            a = hand * TAU * s / lay + phase + k * TAU / 3
            off = splice_swell(s, swell[0], swell[1], d) if swell else offset * d
            pts.append(p + (u * math.cos(a) + v * math.sin(a)) * off)
        out.append(pts)
    return out, 0.25 * d


def tucks(path, d, start, end, lay=None, phase=0.0):
    """The three tucked strands of an eye splice laid into the standing part between arc lengths start and end (start
    at the throat): they sit in the grooves between the standing part's strands, so the splice reads as a fatter rope
    of six strands, and each is cut off a little further along than the last (the taper). Returns [(pts, radii)]."""
    lay = lay or 3.3 * d
    P = resample(path, lay / 16.0)
    F = frames(P)
    S = arclen(P)
    out = []
    for k in range(3):
        stop = start + (end - start) * (0.72 + 0.14 * k)
        pts, radii = [], []
        for p, (t, u, v), s in zip(P, F, S):
            if s < start or s > stop:
                continue
            f = (s - start) / max(1e-6, stop - start)
            a = TAU * s / lay + phase + k * TAU / 3 + TAU / 6
            pts.append(p + (u * math.cos(a) + v * math.sin(a)) * ((0.40 - 0.10 * f) * d))
            radii.append(0.25 * d * (1 - 0.55 * f ** 2))
        out.append((pts, radii))
    return out


def splice_swell(s, start, end, d):
    """How far the standing part's strands sit out from its axis over the splice (they ride over the tucks)."""
    if s < start or s > end:
        return 0.27 * d
    f = (s - start) / max(1e-6, end - start)
    return (0.27 + 0.12 * (1 - f)) * d


# ------------------------------------------------------------------ eye splice

def eye_splice(d=0.0095, eye=0.305, width=0.13, standing=0.6, splice=None):
    """A soft eye spliced into three-strand line, laid flat (XY plane, z = d/2: resting on a deck).

    The crown of the eye is at +X (x = eye), the throat at the origin, the standing part runs off along -X for
    `standing` metres. Returns dict: 'eye' the eye's centreline from the throat round the crown and back beside it,
    'standing' the standing part's from the throat outwards (its first `splice` metres carry the tucks: strands(...,
    swell=(0, splice)) and tucks(standing, d, 0, splice) share its arc length), 'splice' the splice's length."""
    splice = splice or 5 * 3.3 * d            # five tucks, about one lay each
    z = d / 2
    g = 0.5 * d
    hw = width / 2
    eye_pts = [(0.0, g, z), (0.05, 0.4 * hw, z), (0.42 * eye, 0.95 * hw, z), (0.8 * eye, 0.92 * hw, z), (eye, 0.0, z),
               (0.8 * eye, -0.92 * hw, z), (0.42 * eye, -0.95 * hw, z), (0.05, -0.4 * hw, z), (0.0, -g, z)]
    stand = [(0.0, 0.0, z), (-splice, 0.0, z), (-standing, 0.0, z)]
    return {"eye": smooth(eye_pts, d * 0.4), "standing": resample(stand, d * 0.4), "splice": splice}


def eye_on_cleat(L, d, lead, eye=0.305, deck=0.0, under=None):
    """The eye of a dock line round a horn cleat's base, under both horns (passed through and dropped over the horns),
    with the throat out towards the lead. `lead` is the line's direction away from the cleat (XY, cleat frame).
    Returns (eye centreline from the throat round the cleat and back, throat point)."""
    lead = Vector((lead[0], lead[1], 0)).normalized()
    side = Vector((-lead.y, lead.x, 0))
    r = d / 2
    z = deck + r + 0.001
    zu = under if under is not None else z
    hx = 0.40 * L + r                         # the line passes round the cast feet under the horns
    hy = 0.14 * L + r
    # throat distance: the eye's 2 * eye of line goes round the base (an oval) and back out to the throat
    round_len = math.pi * (hx + hy) * 0.5 * 2
    reach = max(0.08, (2 * eye - round_len) / 2)
    throat = lead * (reach + hy) + Vector((0, 0, z))
    g = 0.55 * d
    a_l = math.atan2(lead.y / hy, lead.x / hx)        # the oval's point facing the lead
    n, gap = 28, 0.55
    ring = [Vector((hx * math.cos(a), hy * math.sin(a), zu)) for a in
            (a_l + gap + (TAU - 2 * gap) * i / n for i in range(n + 1))]
    pts = [throat + side * g] + ring + [throat - side * g]
    for p in pts:
        p.z = max(p.z, z)
    return smooth(pts, d * 0.35), throat


# ------------------------------------------------------------------ cleat hitch

def cleat_hitch(L, d, lead, h_under, h_top, half_w, foot_x, tail=0.22, crosses=1):
    """A line made fast on a horn cleat of length L the way ASA teaches it: a full turn round the base (under the far
    horn first, then the near one), figure eights over the top, and a locking hitch on the near horn whose tail lies
    alongside the first cross. Cleat frame (X along the horns, Z up, deck at 0). `lead` is the direction the line
    leaves the cleat towards the load (XY); h_under the free height under the horns, h_top the top of the horns,
    half_w the horns' half width, foot_x the outer edge of the cast feet (|x|). Returns the centreline from 0.5 m out
    along the lead to the tail's end."""
    lead = Vector((lead[0], lead[1], 0)).normalized()
    r = d / 2
    Ls = -1.0 if lead.y <= 0 else 1.0       # the load's side (y sign)
    Fh = -1.0 if lead.x >= 0 else 1.0       # the far horn's x sign: taken first
    Nh = -Fh
    cx = foot_x * 0.62                       # where the turn goes round, under each horn
    R = foot_x + r + 0.003 - cx
    sy = half_w + r + 0.003                  # beside the horns
    zt = h_top + r                           # over the top
    z0 = r + 0.0025
    zmax = h_under - r
    lay = 0.85 * d
    P = []

    def wrap(sgn, y_from, z):
        for i in range(9):
            t = math.pi * i / 8
            P.append(Vector((sgn * (cx + R * math.sin(t)), y_from * R * math.cos(t), z)))

    def over(x0, y0, x1, y1, z):
        P.append(Vector((x0, y0, z)))
        P.append(Vector((x1, y1, z)))

    P.append(Vector((Fh * cx, Ls * R, z0 + 0.03)) + lead * 0.5)
    P.append(Vector((Fh * cx, Ls * R, z0 + 0.006)) + lead * 0.06)
    wrap(Fh, Ls, z0)                                              # the turn: under the far horn,
    wrap(Nh, -Ls, z0 + 0.3 * lay)                                 # along the far side, under the near horn
    z, top = min(zmax, z0 + 1.0 * lay), zt
    for k in range(crosses):                                      # figure eights
        over(Nh * (cx + 0.45 * R), Ls * (sy + 0.004), Fh * (cx + 0.45 * R), -Ls * (sy + 0.004), top)       # up and across the top
        wrap(Fh, -Ls, z)                                          # under the far horn
        top += lay
        over(Fh * (cx + 0.45 * R), Ls * (sy + 0.004), Nh * (cx + 0.45 * R), -Ls * (sy + 0.004), top)       # back across: the X
        z = min(zmax, z + 0.8 * lay)
    # the locking hitch: down the far side of the near horn, under it, up over the horn and back under itself, so
    # the tail runs out alongside the first cross towards the far horn
    wrap(Nh, -Ls, z)
    top += 0.4 * lay
    P.append(Vector((Nh * (cx + 0.6 * R), Ls * 0.4 * sy, top + 0.2 * lay)))
    P.append(Vector((Nh * 0.55 * cx, -Ls * 0.15 * sy, top - 0.6 * lay)))       # under the last cross
    P.append(Vector((Fh * 0.75 * cx + Nh * d, -Ls * sy, zt + 0.1 * lay)))
    # off the far horn's end and down onto the deck
    e = Vector((Fh * (0.5 * L + 0.01), -Ls * (sy + 0.01), 0.5 * zt))
    P.append(e)
    P.append(Vector((e.x + Fh * 0.04, e.y - Ls * 0.01, r + 0.002)))
    P.append(Vector((e.x + Fh * tail, e.y - Ls * 0.05, r + 0.001)))
    return relax(P, d * 0.3, 5)


def clove_hitch(center, axis, post_r, d, lead, tail=0.12):
    """A clove hitch round a post, wire or rail (a fender's line on a shroud or a track end): the line comes in from
    `lead` (a point), takes a turn round the post, crosses over its own standing part and takes a second turn, tucked
    under the cross, and the tail hangs off. Returns the centreline from the lead to the tail's end."""
    c, ax = Vector(center), Vector(axis).normalized()
    ld = Vector(lead) - c
    ld = (ld - ax * ld.dot(ax)).normalized()
    side = ax.cross(ld)
    rr = post_r + d / 2
    pitch = 1.15 * d
    pts = [Vector(lead)]
    n = 18
    a0 = 0.0
    for turn in (0, 1):
        for i in range(n + 1):
            a = a0 + TAU * i / n
            h = (turn - 0.5) * pitch + pitch * 0.5 * (i / n - 0.5)
            lift = (d * 0.35) if (turn == 1 and 0.35 < i / n < 0.65) else 0.0     # the cross rides over
            pts.append(c + ax * h + (ld * math.cos(a) + side * math.sin(a)) * (rr + lift))
    # out under the cross and down: the tail
    end = pts[-1]
    pts.append(end + ld * (0.6 * d) - ax * (0.4 * d))
    pts.append(end + ld * (1.2 * d) - ax * tail * 0.5)
    pts.append(end + ld * (1.6 * d) - ax * tail)
    return smooth(pts, d * 0.35)


# ------------------------------------------------------------------ fender

def fender_profile(dia=0.165, length=0.559, eye_len=0.045, n=48):
    """Side profile of a twin-eye vinyl fender (Polyform G/Taylor Made class): a straight-sided body, shoulders rounding
    into blunt cone ends, a moulded eye lug at each end. Returns [(z, radius)] of the body from end to end (the lugs
    are built separately: they are flat tabs, not round), z from 0 at the bottom lug's tip to `length` at the top's."""
    R = dia / 2
    body0, body1 = eye_len, length - eye_len
    bl = body1 - body0
    out = []
    for i in range(n + 1):
        f = i / n
        z = body0 + bl * f
        u = abs(2 * f - 1)                     # 0 mid, 1 at the ends
        if u < 0.62:
            r = R
        else:
            w = (u - 0.62) / 0.38              # the shoulder: an ellipse into a blunt cone
            r = R * (math.sqrt(max(0.0, 1 - w ** 2.2)) * 0.82 + 0.18 * (1 - w))
        out.append((z, max(r, 0.13 * R)))
    return out
