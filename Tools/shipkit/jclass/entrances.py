"""Bluebonnet's way below at sea (docs/ship-walk/, J-Class walking): the crew's companionway and the doghouse with their
doors hooked open and their sliding hatches run forward, on a loaded build (jclass.blend from build_jclass.py).

The build draws both shut (deck.py companionway() and doghouse(): each a pair of door leaves in the house's after face
and a slide over its after end). The game's walk map (walk_bluebonnet.py) and her hull part (export_game.py) both want
them open, the way she would be sailed with her crew going up and down: this moves the build's own pieces, it builds
nothing. Each piece is found in its object by its loose part (a closed solid of its own), by where deck_bluebonnet.json
puts it, so a change to the deck that moves a door or a slide stops here instead of opening the wrong piece.

    open_entrances(bpy, spec)    spec: game_bluebonnet.json "entrances"

Body frame (X forward, Y starboard, Z up, metres) in the spec and the report; Blender's Y is to port.
"""
import math

import numpy as np


def _loose_parts(me):
    """Each loose part's vertex indices (union-find over the edges)."""
    n = len(me.vertices)
    parent = np.arange(n)

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    for a, b in ev.reshape(-1, 2):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots = np.array([find(i) for i in range(n)])
    return [np.nonzero(roots == r)[0] for r in np.unique(roots)]


def _body(co):
    out = co.copy()
    out[:, 1] *= -1.0
    return out


def _matching(parts, co, want):
    """The loose parts whose box in the body frame lies inside want's box ([[x0, y0, z0], [x1, y1, z1]]) with at least
    want's vertex count."""
    lo, hi = np.array(want["box"][0]), np.array(want["box"][1])
    out = []
    for idx in parts:
        p = co[idx]
        if (p.min(0) >= lo).all() and (p.max(0) <= hi).all() and len(idx) >= want.get("min_vertices", 8):
            out.append(idx)
    return out


def _rotate(co, idx, origin, axis, angle):
    """Rodrigues' rotation of the vertices idx about the line through origin along axis."""
    k = axis / np.linalg.norm(axis)
    p = co[idx] - origin
    c, s = math.cos(angle), math.sin(angle)
    co[idx] = origin + p * c + np.cross(k, p) * s + np.outer(p @ k, k) * (1.0 - c)


def open_entrances(bpy, spec):
    """Opens each house in spec (game_bluebonnet.json "entrances"): its two door leaves turned about their outboard
    edges by 'door_open_deg' (aft and outboard, hooked back against the after face), its slide moved forward by
    'slide_forward'. Returns a report per house; stops if a house hasn't exactly two leaves and one slide where the spec
    says."""
    report = {}
    for name, h in spec.items():
        if name == "note":
            continue
        ob = bpy.data.objects[h["object"]]
        me = ob.data
        m = np.array(ob.matrix_world)
        if not np.allclose(m, np.eye(4), atol=1e-9):
            raise SystemExit(f"{ob.name}: expected in the body frame (identity transform), not {m.tolist()}")
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = _body(co.reshape(-1, 3))
        parts = _loose_parts(me)
        leaves = _matching(parts, co, h["doors"])
        slides = _matching(parts, co, h["slide"])
        if len(leaves) != 2 or len(slides) != 1:
            raise SystemExit(f"{name}: found {len(leaves)} door leaves and {len(slides)} slides where "
                             f"game_bluebonnet.json entrances says (want 2 and 1): has the deck moved?")
        moved = []
        for idx in leaves:
            p = co[idx]
            side = 1.0 if p[:, 1].mean() > 0 else -1.0
            # the hinge: the leaf's outboard edge on its after (outside) face, along the leaf's lean
            # (the doghouse's after face leans in with her tumblehome, so the hinge runs up the edge's lean: its lowest
            # and highest quarters' means)
            edge = p[np.abs(p[:, 1]) > np.abs(p[:, 1]).max() - 0.004]
            zs = np.sort(edge[:, 2])
            lo = edge[edge[:, 2] <= zs[len(zs) // 4]]
            hi = edge[edge[:, 2] >= zs[(3 * len(zs)) // 4]]
            axis = hi.mean(0) - lo.mean(0)
            bot = lo[lo[:, 0].argmin()]
            # turned so its inboard edge swings aft (the door opens outward): in the body frame's numbers a turn of -angle
            # about +Z on the starboard leaf, +angle to port
            angle = math.radians(h["door_open_deg"]) * (-1.0 if side > 0 else 1.0)
            before = p[:, 0].min()
            _rotate(co, idx, bot, axis, angle)
            if co[idx][:, 0].min() > before + 1e-3:
                raise SystemExit(f"{name}: the {'starboard' if side > 0 else 'port'} door swung inboard")
            moved.append({"side": "starboard" if side > 0 else "port",
                          "hinge": [round(float(v), 4) for v in bot], "open_deg": h["door_open_deg"],
                          "box": [co[idx].min(0).round(3).tolist(), co[idx].max(0).round(3).tolist()]})
        s = slides[0]
        co[s, 0] += h["slide_forward"]
        me.vertices.foreach_set("co", _body(co).ravel())
        me.update()
        report[name] = {"doors": moved, "slide_forward": h["slide_forward"],
                        "slide": [co[s].min(0).round(3).tolist(), co[s].max(0).round(3).tolist()]}
    bpy.context.view_layer.update()
    return report
