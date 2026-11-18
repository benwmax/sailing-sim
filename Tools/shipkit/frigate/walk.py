"""Bakes the frigate's walk map (docs/ship-walk/): where a sailor can stand on each deck and the ladders between them.

The game walks the player about the ship in her own frame (Sailing::FShipWalker, Source/SailingPhysics/Public/ShipWalk.h),
with no physics collision: this script gives it each deck's floor and what is overhead on a 10 cm grid, and the ladders.

Every column of the grid is shot from above with a ray through the whole ship (every mesh in her sea pose: the guns
housed, the sails set; sails and running rigging left out, a sailor goes round a rope), and each hit kept. For each deck:

* its baseline is where the column meets the deck's own planking object (DECKS: the spar deck's `SparDeck`, the gun
  deck's `GunDeck`, ...), filled across small gaps (a grating, a coaming) from the planking round it;
* its floor is the highest upward face within [baseline - 0.15, baseline + MaxStep]: the planks, a grating, a sill;
* what is overhead is the lowest hit above that floor; a column with less than MinHeadroom (1.25 m) over its floor (a
  gun, the capstan, a mast, a bulkhead) has no floor at all;
* thin upright things the columns slip past (a bulkhead, a door's frame) are found by short level rays between the
  cells at shin, waist and chest height, and the cell they stand in loses its floor;
* grating holes (a ray between the bars) are closed: a cell with no floor whose neighbours within 0.2 m have one at
  the same height takes their floor, if nothing stands in it.

Ladders come from the model's data: deck.json's ladders (the breaks of the quarterdeck and forecastle, into the waist)
and each deck's json's ladders (`from` names the hatch, which says which deck the ladder's top is on; its foot is on
the next deck down). Each end is moved off the ladder, away from it, to the nearest place a body fits. The Helm spot
(where the game stands you at the wheel) is just aft of deck.json's Wheel, facing forward.

The file format is FWalkMap::Parse's (ShipWalk.h). The game reads Content/TerrainData/Ships/<Ship>.walk; decks whose
planking isn't in the .blend yet (the berth deck, the orlop, the hold before slices 13 and 14) are left out, with the
ladders down to them.

    python walk.py <frigate.blend> <build dir with deck.json, gundeck.json, ...> <out .walk> [--summary <json>]

Needs Blender's Python (`bpy`, the pip wheel works: see docs/ship-walk/). About two minutes for the spar and gun decks.
"""

import json
import math
import os
import struct
import sys
import time

import numpy as np

# The walker's numbers; keep them in step with FWalkMap in ShipWalk.h.
BODY_RADIUS = 0.22
MAX_STEP = 0.32
MIN_HEADROOM = 1.25
WALL_HEIGHTS = (0.3, 0.8, 1.2)   # m over the floor: shin, waist, chest

CELL = 0.1
MAGIC = 0x4B4C5753
VERSION = 2   # 2 added the spots
HELM_BEHIND_WHEEL = 0.7   # m: the Helm spot is this far aft of the wheel, facing forward

# Top to bottom. floor: the deck's planking objects; json: its game data (ladders, layout); also: decks to keep loaded
# while on it (the gun deck shows through the spar deck's open waist and hatches).
DECKS = [
    {"name": "Spar", "floor": ["SparDeck"], "json": "deck.json", "also": ["Gun"]},
    {"name": "Gun", "floor": ["GunDeck"], "json": "gundeck.json", "also": []},
    {"name": "Berth", "floor": ["BerthDeck"], "json": "berthdeck.json", "also": []},
    {"name": "Orlop", "floor": ["Orlop", "OrlopDeck"], "json": "orlop.json", "also": []},
    {"name": "Hold", "floor": ["Hold", "HoldFloor"], "json": "hold.json", "also": []},
]
ALL_DECKS = [d["name"] for d in DECKS]   # top down

# Left out of the rays: what a sailor ducks under or goes round, and what isn't there at sea.
# The great cabin's doors are baked open (the game swings them; docs/ship-walk/).
SKIP_PREFIXES = ("Sail", "Running", "Clew", "Bunt", "Reef", "Flag", "Pennant", "Ensign", "CabinDoor")
SKIP_COLLECTIONS_HIDDEN = True


def load_ship(blend):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=blend)
    hidden = set()
    for coll in bpy.data.collections:
        if SKIP_COLLECTIONS_HIDDEN and (coll.hide_render or coll.hide_viewport):
            hidden.update(o.name for o in coll.objects)
        if coll.name.startswith(("Sails_", "Running_")):
            hidden.update(o.name for o in coll.objects)
    return bpy, hidden


def gather(bpy, hidden):
    """Every mesh in her sea pose as one triangle soup in the ship's frame, with each face's object."""
    from mathutils import Vector  # noqa: F401  (bpy's own)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts, polys, owner, names = [], [], [], []
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or obj.name in hidden or obj.name.startswith(SKIP_PREFIXES):
            continue
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        mw = obj.matrix_world
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(mw)
        co = co @ m[:3, :3].T + m[:3, 3]
        tri = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
        mesh.loop_triangles.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3)
        if np.linalg.det(m[:3, :3]) < 0:
            tri = tri[:, ::-1]
        base = sum(len(v) for v in verts)
        verts.append(co)
        polys.append(tri + base)
        owner.append(np.full(len(tri), len(names), dtype=np.int32))
        names.append(obj.name)
        ev.to_mesh_clear()
    V = np.concatenate(verts)
    P = np.concatenate(polys)
    return V, P, np.concatenate(owner), names


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
            col = []
            z = z_top
            while z > z_bottom:
                loc, nrm, idx, dist = tree.ray_cast(Vector((x, y, z)), down, z - z_bottom)
                if loc is None:
                    break
                col.append((loc.z, nrm.z, idx))
                z = loc.z - 1e-4
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


def bake_deck(deck, hits, face_owner, names, xs, ys):
    """One deck's floor and overhead grids (NaN no floor, inf open)."""
    floor_ids = {i for i, n in enumerate(names) if n in deck["floor"]}
    ny, nx = len(ys), len(xs)
    base = np.full((ny, nx), np.nan)
    for j in range(ny):
        for i in range(nx):
            for z, nz, idx in hits[j][i]:
                if nz > 0.5 and face_owner[idx] in floor_ids:
                    base[j, i] = z
                    break
    # Fill the baseline across gaps up to half a metre (gratings, coamings, a ladderway's lip) from the nearest planking.
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
    # Close grating holes: a cell without a floor (not one blocked by something in it) amid floor cells at one height.
    r = int(round(0.2 / CELL))
    add = []
    for j in range(ny):
        for i in range(nx):
            if not np.isnan(floor[j, i]) or blocked[j, i] or np.isnan(filled[j, i]):
                continue
            j0, j1, i0, i1 = max(0, j - r), min(ny, j + r + 1), max(0, i - r), min(nx, i + r + 1)
            sub = floor[j0:j1, i0:i1]
            ok = ~np.isnan(sub)
            # floor on both sides along a row or a column (a hole, not an edge)
            row, colm = floor[j, i0:i1], floor[j0:j1, i]
            spans = (not np.isnan(row[:r]).all() and not np.isnan(row[r + 1:]).all()) if len(row) == 2 * r + 1 else False
            spans = spans or ((not np.isnan(colm[:r]).all() and not np.isnan(colm[r + 1:]).all()) if len(colm) == 2 * r + 1 else False)
            if spans and ok.sum() >= 4 and np.nanmax(sub) - np.nanmin(sub) <= 0.05:
                add.append((j, i, float(np.nanmean(sub)), float(np.min(over[j0:j1, i0:i1]))))
    for j, i, f, o in add:
        floor[j, i] = f
        over[j, i] = o
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


def ladders(build, decks):
    """(name, upper deck, lower deck, top x, y, foot x, y) from each deck's json."""
    names = [d["name"] for d in decks]
    out = []
    for k, d in enumerate(decks):
        path = os.path.join(build, d["json"])
        if not os.path.exists(path):
            continue
        data = json.load(open(path))
        for lad in data.get("ladders", []):
            if "break" in lad:   # deck.json: the breaks, from this deck down into the waist
                up = k
                name = f"{lad['break'].capitalize()}{'S' if lad['y_m'] > 0 else 'P'}"
                y = lad["y_m"]
            else:   # a hatch's ladder: its top is on this deck if its layout has the hatch (gundeck.json's AfterHatch
                # leads down to the berth deck), else on the deck above whose layout does (the spar deck's Companion)
                hatch = lad["from"]
                up = k
                if hatch not in data.get("layout", {}):
                    up = next((m for m in range(k - 1, -1, -1)
                               if os.path.exists(os.path.join(build, decks[m]["json"]))
                               and hatch in json.load(open(os.path.join(build, decks[m]["json"]))).get("layout", {})), k)
                name = hatch
                y = lad.get("y_m", 0.0)
            # (down to the next deck in the ship, built or not: main() leaves out a ladder to a deck not built yet)
            below = ALL_DECKS.index(names[up]) + 1
            if below >= len(ALL_DECKS):
                continue
            out.append((name, names[up], ALL_DECKS[below], lad["top_x_m"], y, lad["foot_x_m"], y))
    # the same ladder listed from both decks' files once
    seen, uniq = set(), []
    for L in out:
        key = (L[1], L[2], round(L[3], 2), round(L[4], 2))
        if key not in seen:
            seen.add(key)
            uniq.append(L)
    return uniq


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


def write(path, decks, links, xs, ys, spots=()):
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
        out += struct.pack("<BBBB", 0, L["lower"], L["upper"], len(name)) + name
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
    if len(argv) < 3:
        print(__doc__)
        return 2
    blend, build, out = argv[0], argv[1], argv[2]
    summary_path = argv[argv.index("--summary") + 1] if "--summary" in argv else None
    t0 = time.time()
    bpy, hidden = load_ship(blend)
    V, P, owner, names = gather(bpy, hidden)
    present = [d for d in DECKS if any(n in names for n in d["floor"])]
    missing = [d["name"] for d in DECKS if d not in present]
    if not present:
        print("no deck planking found in", blend)
        return 1
    print(f"{len(names)} objects, {len(P)} triangles; decks {[d['name'] for d in present]}"
          + (f", not built yet {missing}" if missing else ""))
    # One grid for every deck: the planking objects' plan with a body's room round it.
    fl = [i for i, n in enumerate(names) if any(n in d["floor"] for d in present)]
    sel = np.isin(owner, fl)
    pts = V[np.unique(P[sel])]
    x0, x1 = math.floor(pts[:, 0].min() / CELL) * CELL - 0.5, math.ceil(pts[:, 0].max() / CELL) * CELL + 0.5
    y1 = math.ceil(np.abs(pts[:, 1]).max() / CELL) * CELL + 0.5
    xs = np.round(np.arange(x0, x1 + CELL / 2, CELL), 4)
    ys = np.round(np.arange(-y1, y1 + CELL / 2, CELL), 4)
    z_top = float(V[:, 2].max()) + 1.0
    z_bottom = float(pts[:, 2].min()) - 3.0
    print(f"grid {len(xs)} x {len(ys)} at {CELL} m, x {xs[0]}..{xs[-1]}, y +-{y1}; shooting...")
    hits, tree = shoot(V, P, xs, ys, z_top, z_bottom)
    print(f"  {sum(len(c) for r in hits for c in r)} hits, {time.time() - t0:.0f} s")
    baked = []
    for d in present:
        floor, over = bake_deck(d, hits, owner, names, xs, ys)
        thin = walls(tree, floor, xs, ys)
        if not np.isfinite(floor).any():
            print(f"  {d['name']}: no floor found: left out")
            continue
        floor, over = quantize(floor, over)
        stand = stand_mask(floor, over)
        baked.append({"name": d["name"], "floor": floor, "over": over, "stand": stand, "also": d["also"]})
        print(f"  {d['name']}: floor {int(np.isfinite(floor).sum() * CELL * CELL)} m2, stand {int(stand.sum() * CELL * CELL)} m2"
              f" ({thin} cells under thin walls)")
    order = [b["name"] for b in baked]
    for b in baked:
        b["also_mask"] = sum(1 << order.index(a) for a in b.pop("also") if a in order)
    present = [d for d in present if d["name"] in order]
    links = []
    for name, up, low, tx, ty, fx, fy in ladders(build, present):
        if up not in order or low not in order:
            continue
        U, L = baked[order.index(up)], baked[order.index(low)]
        away_top = np.array([math.copysign(1.0, tx - fx), 0.0])
        away_foot = -away_top
        top = nearest_stand(U["stand"], U["floor"], xs, ys, tx, ty, away_top)
        foot = nearest_stand(L["stand"], L["floor"], xs, ys, fx, fy, away_foot)
        if top is None or foot is None:
            print(f"  ladder {name}: no room at its {'top' if top is None else 'foot'}: left out")
            continue
        links.append({"name": name, "upper": order.index(up), "lower": order.index(low),
                      "top": [float(v) for v in top], "foot": [float(v) for v in foot]})
        print(f"  ladder {name}: {up} ({top[0]:.2f}, {top[1]:.2f}, {top[2]:.2f}) to {low} ({foot[0]:.2f}, {foot[1]:.2f}, {foot[2]:.2f})")
    spots = []
    wheel = json.load(open(os.path.join(build, "deck.json"))).get("layout", {}).get("Wheel")
    if wheel and "Spar" in order:
        S = baked[order.index("Spar")]
        at = nearest_stand(S["stand"], S["floor"], xs, ys, wheel["x_m"] - HELM_BEHIND_WHEEL, 0.0, np.array([-1.0, 0.0]))
        if at is not None:
            spots.append({"name": "Helm", "deck": order.index("Spar"), "x": float(at[0]), "y": float(at[1]), "yaw": 0.0})
            print(f"  spot Helm: Spar ({at[0]:.2f}, {at[1]:.2f}, {at[2]:.2f}), the wheel at {wheel['x_m']:.2f}")
    size = write(out, baked, links, xs, ys, spots)
    print(f"wrote {out}: {size} bytes, {time.time() - t0:.0f} s")
    if summary_path:
        summary = {
            "cell_m": CELL, "x_m": [float(xs[0]), float(xs[-1])], "y_m": [float(ys[0]), float(ys[-1])],
            "decks": [{"name": b["name"], "floor_m2": round(float(np.isfinite(b["floor"]).sum()) * CELL * CELL, 1),
                       "stand_m2": round(float(b["stand"].sum()) * CELL * CELL, 1),
                       "least_headroom_m": round(float(np.nanmin(np.where(b["stand"], b["over"] - b["floor"], np.nan))), 3)}
                      for b in baked],
            "ladders": links, "spots": spots, "not_built": missing,
        }
        with open(summary_path, "w") as fh:
            json.dump(summary, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
