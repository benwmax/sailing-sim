"""Bakes Bluebonnet's walk map (docs/ship-walk/, J-Class walking): where you can stand on her deck, in her cockpit and in
her cabins below, and the ways between them.

The game walks the player about a boat in her own frame (Sailing::FShipWalker, Source/SailingPhysics/Public/ShipWalk.h)
with no physics collision, on a baked map: each deck's floor and what is overhead on a 10 cm grid, and the ladders and
steps between the decks. The frigate's map comes from Tools/shipkit/frigate/walk.py; this is the same bake (the same
rays, wall test, stand mask and file) for the J-Class yacht, whose 'decks' are her deck, her cockpit's sole half a metre
under it, and her cabins' soles (slices 9 and 10: from -0.6 m aft to +0.36 in the crew's washroom).

Every 10 cm column is shot from above through the whole yacht as she sails (her build, jclass.blend, with the crew's
companionway and the doghouse opened as the game draws them: entrances.py; sails, running rigging, flags, the runners and
the hidden light copies left out). For each deck:

* its baseline: the deck where the column meets her `Deck` planking, the cockpit where it meets the same object's
  slatted sole half a metre lower inside the well's plan (COCKPIT), and below where an upward face lies within 8 cm of the room's sole (interior_bluebonnet.json "rooms": the sole is
  joinery like the berths and tables over it, so the room's own height picks it out), filled across gaps up to half a
  metre from the baseline round it;
* its floor: the highest upward face within [baseline - 0.15, baseline + MaxStep] (planks, a sill, a step, a carpet);
* what is overhead: the lowest hit above the floor; less than MinHeadroom (1.25 m) over it and the column has no floor
  (the mast, a table, a berth, the wheel box);
* thin upright things the columns slip past (a bulkhead, a partition, a door's leaf) are found by short level rays at
  shin, waist and chest height, and gaps between a grating's slats are closed.

The ways (WAYS): the crew's ladder down the companionway into the pantry, the companion stairs down from the doghouse's
doors into the owner's lobby, and the cockpit's step over its after coaming. Each end is moved off the way, away from
it, to the nearest place a body fits. The Helm spot is in the cockpit aft of the wheel, facing forward (where you set off
from her helm view).

    python -I Tools/shipkit/jclass/walk_bluebonnet.py <build dir with jclass.blend> <out .walk> [--summary <json>]

Writes Content/TerrainData/Ships/Bluebonnet.walk for the game (FWalkMap::Parse's format, version 2). Needs Blender's
Python (the bpy module). About two minutes.
"""

import json
import math
import os
import struct
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from entrances import open_entrances  # noqa: E402

# The walker's numbers; keep them in step with FWalkMap in ShipWalk.h.
BODY_RADIUS = 0.22
MAX_STEP = 0.32
MIN_HEADROOM = 1.25
WALL_HEIGHTS = (0.3, 0.8, 1.2)   # m over the floor: shin, waist, chest

CELL = 0.05   # m: half the frigate's: her doors (0.53 to 0.56 m) and the crew ladder's foot leave a body only a few cm
MAGIC = 0x4B4C5753
VERSION = 2
RAY_NUDGES = ((0.0013, 0.0013), (0.021, 0.037))   # m off each cell's centre for its two rays down
SOLE_WINDOW = 0.08   # m: an upward face this near a room's sole is the sole (its planks, a carpet, a runner, a sill)

# Top to bottom: name, how the baseline is found ("objects": the column's first upward face of these; "rooms": within
# SOLE_WINDOW of the room's sole), decks kept loaded while on it (none: her cabins show only through the skylights).
# The cockpit's well is let into her `Deck` object half a metre down (deck_bluebonnet.json cockpit): its sole is a deck of
# its own ('inside' its plan), cut out of the deck's ('outside'), with a step over its after coaming (WAYS).
COCKPIT = [[-11.95, -0.9], [-9.95, 0.9]]
DECKS = [
    {"name": "Deck", "objects": ["Deck"], "outside": COCKPIT, "also": []},
    {"name": "Cockpit", "objects": ["Deck"], "inside": COCKPIT, "also": []},
    {"name": "Below", "rooms": True, "also": []},
]

# The ways between them: (name, kind 0 ladder / 1 steps, upper, lower, top x, y, foot x, y), body frame. The ends are where
# you step on and off, moved to the nearest place a body fits away from the way.
#   Companionway: the crew's ladder, leaning 15 deg against the opening's after edge (x 0.425) from the pantry's sole
#     (-0.6) up to the sill (deck + 0.04): its foot about 0.56 m forward of the top.
#   Doghouse: the companion stairs, leaning 35 deg, down forward from the doors' sill (x -7.36, 1.53 m) to the lobby's
#     sole (-0.6): 1.49 m forward.
#   Cockpit: over the after coaming, from the cockpit's sole half a metre up to the deck behind it. (One step: in a well
#     1.8 m wide a step each side would have you taking one whenever you crossed it.)
WAYS = [
    ("Companionway", 0, "Deck", "Below", 0.20, 0.0, 1.10, 0.0),
    ("Doghouse", 1, "Deck", "Below", -7.65, 0.0, -5.75, 0.0),
    ("Cockpit", 1, "Deck", "Cockpit", -12.35, 0.0, -11.60, 0.0),
]
HELM = {"deck": "Cockpit", "x": -10.85, "y": 0.0, "yaw": 0.0}   # aft of the wheel (x -10.15), facing forward

# Left out of the rays: what a sailor ducks under or goes round, and what isn't there at sea.
SKIP_PREFIXES = ("Mainsail", "Genoa", "Quadrilateral", "Staysail", "Spinnaker.", "Running", "Burgee", "Ensign", "Runner",
                 "Checkstay", "Flag")


def load(build):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=os.path.join(build, "jclass.blend"))
    game = json.load(open(os.path.join(HERE, "game_bluebonnet.json")))
    opened = open_entrances(bpy, game["entrances"])
    return bpy, opened


def gather(bpy):
    """Every mesh she sails with as one triangle soup in the body frame (X forward, Y starboard), with each face's
    object. Hidden objects (the light copies, the moulded hull, the other suits' sails) are left out."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts, polys, owner, names = [], [], [], []
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or obj.hide_render or obj.name.startswith(SKIP_PREFIXES) or obj.name.endswith("_Light"):
            continue
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", co)
        m = np.array(obj.matrix_world)
        co = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        co[:, 1] *= -1.0   # Blender's Y is to port
        tri = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
        mesh.loop_triangles.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3)
        if np.linalg.det(m[:3, :3]) > 0:   # (the mirror in Y turns every face inside out)
            tri = tri[:, ::-1]
        base = sum(len(v) for v in verts)
        verts.append(co)
        polys.append(tri + base)
        owner.append(np.full(len(tri), len(names), dtype=np.int32))
        names.append(obj.name)
        ev.to_mesh_clear()
    return np.concatenate(verts), np.concatenate(polys), np.concatenate(owner), names


def room_sole(rooms, x):
    """The sole's top under x (interior_bluebonnet.json rooms; the washroom's raised forward part), None outside them."""
    for name, r in rooms.items():
        if not isinstance(r, dict) or "x" not in r:
            continue
        if r["x"][0] <= x <= r["x"][1]:
            if r.get("sole_forward") and x >= r["sole_forward"][0]:
                return r["sole_forward"][1]
            return r["sole"]
    return None


def shoot(V, P, xs, ys, z_top, z_bottom):
    """All hits down each column: a list per column of (z, normal z, face index)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromPolygons([tuple(v) for v in V], [tuple(p) for p in P], all_triangles=True)
    down = Vector((0.0, 0.0, -1.0))
    hits = []
    for y in ys:
        row = []
        for x in xs:
            # Two rays a little apart, their hits merged: her soles are planks 0.11 m wide with open seams, one on the
            # centreline, which a single ray down the grid can fall through all the way along.
            col = []
            for dx, dy in RAY_NUDGES:
                z = z_top
                while z > z_bottom:
                    loc, nrm, idx, dist = tree.ray_cast(Vector((x + dx, y + dy, z)), down, z - z_bottom)
                    if loc is None:
                        break
                    col.append((loc.z, nrm.z, idx))
                    z = loc.z - 1e-4
            col.sort(key=lambda h: -h[0])
            row.append(col)
        hits.append(row)
    return hits, tree


def walls(tree, floor, xs, ys):
    """Thin upright things the columns slip past (a bulkhead, a door frame, a stanchion between rays): a short level ray
    from each cell to the next, at shin, waist and chest height over its floor; the cell nearer whatever it meets loses
    its floor. Returns how many cells it took."""
    from mathutils import Vector
    ny, nx = floor.shape
    cut = np.zeros_like(floor, dtype=bool)
    for j in range(ny):
        for i in range(nx):
            f = floor[j, i]
            if np.isnan(f):
                continue
            for dj, di in ((0, 1), (1, 0)):
                jj, ii = j + dj, i + di
                if jj >= ny or ii >= nx or np.isnan(floor[jj, ii]):
                    continue
                d = Vector((di * 1.0, dj * 1.0, 0.0))
                for h in WALL_HEIGHTS:
                    z = max(f, floor[jj, ii]) + h
                    loc, nrm, idx, dist = tree.ray_cast(Vector((xs[i], ys[j], z)), d, CELL)
                    if loc is not None:
                        if dist < CELL / 2:
                            cut[j, i] = True
                        else:
                            cut[jj, ii] = True
                        break
    floor[cut] = np.nan
    return int(cut.sum())


def bake_deck(deck, hits, face_owner, names, xs, ys, rooms):
    """One deck's floor and overhead grids (NaN no floor, inf open)."""
    ids = {i for i, n in enumerate(names) if n in deck.get("objects", ())}
    ny, nx = len(ys), len(xs)
    base = np.full((ny, nx), np.nan)
    for i in range(nx):
        sole = room_sole(rooms, xs[i]) if deck.get("rooms") else None
        for j in range(ny):
            for z, nz, idx in hits[j][i]:
                if nz <= 0.5:
                    continue
                if (sole is not None and abs(z - sole) <= SOLE_WINDOW) or (not deck.get("rooms") and face_owner[idx] in ids):
                    base[j, i] = z
                    break
    # Fill the baseline across gaps up to half a metre (a coaming, a sill, a ladder's foot) from the nearest baseline.
    filled = base.copy()
    reach = int(round(0.5 / CELL))
    have = ~np.isnan(base)
    for j in range(ny):
        for i in range(nx):
            if have[j, i]:
                continue
            j0, j1, i0, i1 = max(0, j - reach), min(ny, j + reach + 1), max(0, i - reach), min(nx, i + reach + 1)
            sub = base[j0:j1, i0:i1]
            ok = ~np.isnan(sub)
            if ok.any():
                jj, ii = np.nonzero(ok)
                d2 = (jj + j0 - j) ** 2 + (ii + i0 - i) ** 2
                filled[j, i] = sub[jj[np.argmin(d2)], ii[np.argmin(d2)]]
    floor = np.full((ny, nx), np.nan)
    over = np.full((ny, nx), np.inf)
    blocked = np.zeros((ny, nx), dtype=bool)
    for j in range(ny):
        for i in range(nx):
            b = filled[j, i]
            if np.isnan(b):
                continue
            col = hits[j][i]
            f = None
            for z, nz, idx in col:   # top down: the first upward face in the window is the highest
                if b - 0.15 <= z <= b + MAX_STEP and nz > 0.5:
                    f = z
                    break
            if f is None:
                continue
            above = [z for z, nz, idx in col if z > f + 0.01]
            o = min(above) if above else math.inf
            if o - f < MIN_HEADROOM:
                blocked[j, i] = True
                over[j, i] = o
                continue
            floor[j, i] = f
            over[j, i] = o if o - f < 25.0 else math.inf
    # Close slat gaps (the cockpit's slatted sole, a grating): a cell without a floor amid floor cells at one height.
    r = int(round(0.2 / CELL))
    add = []
    for j in range(ny):
        for i in range(nx):
            if not np.isnan(floor[j, i]) or blocked[j, i] or np.isnan(filled[j, i]):
                continue
            j0, j1, i0, i1 = max(0, j - r), min(ny, j + r + 1), max(0, i - r), min(nx, i + r + 1)
            sub = floor[j0:j1, i0:i1]
            ok = ~np.isnan(sub)
            row, colm = floor[j, i0:i1], floor[j0:j1, i]
            spans = (not np.isnan(row[:r]).all() and not np.isnan(row[r + 1:]).all()) if len(row) == 2 * r + 1 else False
            spans = spans or ((not np.isnan(colm[:r]).all() and not np.isnan(colm[r + 1:]).all()) if len(colm) == 2 * r + 1 else False)
            if spans and ok.sum() >= 4 and np.nanmax(sub) - np.nanmin(sub) <= 0.05:
                add.append((j, i, float(np.nanmean(sub)), float(np.min(over[j0:j1, i0:i1]))))
    for j, i, f, o in add:
        floor[j, i] = f
        over[j, i] = o
    # (the cockpit's plan: its own deck inside, none of the deck's)
    X, Y = np.meshgrid(xs, ys)
    for key, keep in (("inside", True), ("outside", False)):
        if key in deck:
            (ax, ay), (bx, by) = deck[key]
            within = (X >= ax) & (X <= bx) & (Y >= ay) & (Y <= by)
            cut = ~within if keep else within
            floor[cut] = np.nan
            over[cut] = np.inf
    return floor, over


def stand_mask(floor, over):
    """FWalkMap::Finish in numpy: a floor, headroom, and every floor within the body's radius within a step."""
    ny, nx = floor.shape
    ok = ~np.isnan(floor) & ((over - floor) >= MIN_HEADROOM)
    R = int(math.ceil(BODY_RADIUS / CELL))
    R2 = (BODY_RADIUS / CELL) ** 2
    pad = np.pad(floor, R, constant_values=np.nan)
    stand = ok.copy()
    for dj in range(-R, R + 1):
        for di in range(-R, R + 1):
            if di * di + dj * dj > R2:
                continue
            nb = pad[R + dj:R + dj + ny, R + di:R + di + nx]
            with np.errstate(invalid='ignore'):
                stand &= ~np.isnan(nb) & (np.abs(nb - floor) <= MAX_STEP)
    return stand


def nearest_stand(stand, floor, xs, ys, x, y, away, limit=1.2):
    """The first place a body fits from (x, y) stepping along `away` (a unit plan vector), then anywhere nearest."""
    def cell(px, py):
        return int(round((py - ys[0]) / CELL)), int(round((px - xs[0]) / CELL))
    s = 0.0
    while s <= limit:
        j, i = cell(x + away[0] * s, y + away[1] * s)
        if 0 <= j < len(ys) and 0 <= i < len(xs) and stand[j, i]:
            return xs[i], ys[j], float(floor[j, i])
        s += CELL / 2
    jj, ii = np.nonzero(stand)
    if len(jj) == 0:
        return None
    d2 = (xs[ii] - x) ** 2 + (ys[jj] - y) ** 2
    k = int(np.argmin(d2))
    if d2[k] > limit * limit:
        return None
    return xs[ii[k]], ys[jj[k]], float(floor[jj[k], ii[k]])


def base_of(floor):
    """The millimetre grid's zero: the lowest floor (0 for a deck with none)."""
    return float(np.nanmin(floor)) if np.isfinite(floor).any() else 0.0


def quantize(floor, over):
    """The floor and overhead as the game reads them back (FWalkMap::Parse: millimetres over the base, as float32), so
    the stand mask and the ladder ends here are worked on the numbers FWalkMap::Finish sees."""
    base = base_of(floor)
    f = np.where(np.isnan(floor), np.nan, base + np.clip(np.round((floor - base) * 1000.0), -32767, 32766) * 0.001)
    o = np.where(np.isfinite(over), base + np.clip(np.round((over - base) * 1000.0), -32767, 32766) * 0.001, np.inf)
    return f.astype(np.float32).astype(np.float64), o.astype(np.float32).astype(np.float64)


def write(path, decks, links, xs, ys, spots):
    out = bytearray()
    out += struct.pack("<IIII", MAGIC, VERSION, len(decks), len(links))
    for d in decks:
        floor, over = d["floor"], d["over"]
        base = base_of(floor)
        name = d["name"].encode()
        out += struct.pack("<B", len(name)) + name
        out += struct.pack("<dddd", float(xs[0]), float(ys[0]), CELL, base)
        out += struct.pack("<iiI", len(xs), len(ys), d["also_mask"])
        f = np.where(np.isnan(floor), -32768, np.clip(np.round((floor - base) * 1000.0), -32767, 32766)).astype("<i2")
        o = np.where(np.isfinite(over), np.clip(np.round((over - base) * 1000.0), -32767, 32766), 32767).astype("<i2")
        out += f.tobytes() + o.tobytes()   # row-major, x fastest: FWalkDeck::Index(I, J) = J NX + I
    for L in links:
        name = L["name"].encode()
        out += struct.pack("<BBBB", L["kind"], L["lower"], L["upper"], len(name)) + name
        out += struct.pack("<7d", *L["foot"], *L["top"], L.get("half_width", 0.4))
    out += struct.pack("<I", len(spots))
    for S in spots:
        name = S["name"].encode()
        out += struct.pack("<BB", S["deck"], len(name)) + name
        out += struct.pack("<3d", S["x"], S["y"], S.get("yaw", 0.0))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return len(out)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    build, out = argv[0], argv[1]
    summary_path = argv[argv.index("--summary") + 1] if "--summary" in argv else None
    t0 = time.time()
    bpy, opened = load(build)
    rooms = json.load(open(os.path.join(HERE, "interior_bluebonnet.json")))["rooms"]
    V, P, owner, names = gather(bpy)
    print(f"{len(names)} objects, {len(P)} triangles; opened {sorted(opened)}")
    # One grid for every deck: the deck's plan with a body's room round it.
    sel = np.isin(owner, [names.index("Deck")])
    pts = V[np.unique(P[sel])]
    x0, x1 = math.floor(pts[:, 0].min() / CELL) * CELL - 0.5, math.ceil(pts[:, 0].max() / CELL) * CELL + 0.5
    y1 = math.ceil(np.abs(pts[:, 1]).max() / CELL) * CELL + 0.5
    xs = np.round(np.arange(x0, x1 + CELL / 2, CELL), 4)
    ys = np.round(np.arange(-y1, y1 + CELL / 2, CELL), 4)
    z_top = float(V[:, 2].max()) + 1.0
    z_bottom = -2.0   # (under every sole: the bilge, the keel's top)
    print(f"grid {len(xs)} x {len(ys)} at {CELL} m, x {xs[0]}..{xs[-1]}, y +-{y1}; shooting...")
    hits, tree = shoot(V, P, xs, ys, z_top, z_bottom)
    print(f"  {sum(len(c) for r in hits for c in r)} hits, {time.time() - t0:.0f} s")
    baked = []
    for d in DECKS:
        floor, over = bake_deck(d, hits, owner, names, xs, ys, rooms)
        thin = walls(tree, floor, xs, ys)
        floor, over = quantize(floor, over)
        stand = stand_mask(floor, over)
        baked.append({"name": d["name"], "floor": floor, "over": over, "stand": stand, "also": d["also"]})
        print(f"  {d['name']}: floor {np.isfinite(floor).sum() * CELL * CELL:.1f} m2, stand {stand.sum() * CELL * CELL:.1f} m2"
              f" ({thin} cells under thin walls)")
    order = [b["name"] for b in baked]
    for b in baked:
        b["also_mask"] = sum(1 << order.index(a) for a in b.pop("also"))
    links = []
    for name, kind, up, low, tx, ty, fx, fy in WAYS:
        U, L = baked[order.index(up)], baked[order.index(low)]
        d = np.array([tx - fx, ty - fy])
        d /= np.linalg.norm(d)
        top = nearest_stand(U["stand"], U["floor"], xs, ys, tx, ty, d)
        foot = nearest_stand(L["stand"], L["floor"], xs, ys, fx, fy, -d)
        if top is None or foot is None:
            raise SystemExit(f"way {name}: no room at its {'top' if top is None else 'foot'}")
        links.append({"name": name, "kind": kind, "upper": order.index(up), "lower": order.index(low),
                      "top": [float(v) for v in top], "foot": [float(v) for v in foot]})
        print(f"  {name}: {up} ({top[0]:.2f}, {top[1]:.2f}, {top[2]:.2f}) to {low} ({foot[0]:.2f}, {foot[1]:.2f}, {foot[2]:.2f})")
    H = baked[order.index(HELM["deck"])]
    at = nearest_stand(H["stand"], H["floor"], xs, ys, HELM["x"], HELM["y"], np.array([-1.0, 0.0]))
    if at is None:
        raise SystemExit("no room for the Helm spot in the cockpit")
    spots = [{"name": "Helm", "deck": order.index(HELM["deck"]), "x": float(at[0]), "y": float(at[1]), "yaw": HELM["yaw"]}]
    print(f"  spot Helm: {HELM['deck']} ({at[0]:.2f}, {at[1]:.2f}, {at[2]:.2f})")
    size = write(out, baked, links, xs, ys, spots)
    print(f"wrote {out}: {size} bytes, {time.time() - t0:.0f} s")
    if summary_path:
        summary = {
            "cell_m": CELL, "x_m": [float(xs[0]), float(xs[-1])], "y_m": [float(ys[0]), float(ys[-1])],
            "decks": [{"name": b["name"], "floor_m2": round(float(np.isfinite(b["floor"]).sum()) * CELL * CELL, 1),
                       "stand_m2": round(float(b["stand"].sum()) * CELL * CELL, 1),
                       "least_headroom_m": round(float(np.nanmin(np.where(b["stand"], b["over"] - b["floor"], np.nan))), 3)}
                      for b in baked],
            "ways": links, "spots": spots, "entrances": opened,
        }
        with open(summary_path, "w") as fh:
            json.dump(summary, fh, indent=1)
        # a plan of each deck for the docs: stand (light), floor without room (mid), ways and the Helm spot
        np.savez_compressed(os.path.splitext(summary_path)[0] + ".npz", xs=xs, ys=ys,
                            **{f"{b['name']}_{k}": b[k] for b in baked for k in ("floor", "over", "stand")})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
