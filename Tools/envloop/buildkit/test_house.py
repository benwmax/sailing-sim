"""Test house builder (Track E): assembles a whole house from a style recipe (styles/<id>.json) and the parts kit, to
judge the kit outside the game. It is the reference for the integration step after Nov 21, when HouseKit.cpp swaps its
flat window and door rectangles for kit parts on the same openings: the rules here (where openings go, reveals,
casings, sills, shutters, gutters, porches) are the ones the game will follow.

    python3 Tools/envloop/buildkit/test_house.py <style> <seed> <out dir> [--render] [--row] [--blend]
        (bpy module; or blender -b --factory-startup -P test_house.py -- <style> <seed> <out> ...)

The house is one rectangle (length along X, the front facing -Y), one or two storeys, with a gable, hip, shed or flat
roof. Writes <out>/<style>_<seed>.json (parts used, triangle counts, openings) and with --render the standard views:
3 m (front door), 15 m (front three-quarter: midday, low sun, overcast), 15 m back (the lake side, midday), 60 m
(midday). --row renders three seeds side by side in a 40 m wide frame (the "no repeat" check).
"""
import json
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hk_core as K  # noqa: E402
import hk_parts as P  # noqa: E402
from hk_core import G, METAL, TRIM_S  # noqa: E402


def pick(rng, spec):
    """spec: a plain value, or a flat list [value, weight, value, weight, ...]."""
    if not isinstance(spec, list) or len(spec) < 2 or not isinstance(spec[1], (int, float)) or isinstance(spec[0], (int, float)):
        return spec
    vals, ws = spec[0::2], spec[1::2]
    return rng.choices(vals, ws)[0]


class House:
    def __init__(self, style, seed, origin=(0.0, 0.0)):
        self.s = style
        self.seed = seed
        self.rng = random.Random(hash((style["id"], seed)) & 0xFFFFFFFF)
        self.o = Vector((origin[0], origin[1], 0.0))
        self.pieces = []          # loose marked pieces (walls, roof, trim runs), joined at the end
        self.placed = []          # placed part objects
        self.used = {}
        self.cache = {}
        self.openings = []
        r = self.rng
        st = style
        self.storeys = st["storeys"]
        self.plate = st["plate_m"]
        self.raised = st.get("raised_m", 0.0)
        self.floor = self.raised if self.raised else 0.20
        self.L = {"ranch1970": 19.0, "twostory1990": 15.0, "farmhouse": 18.0, "cottage": 11.0, "modern": 14.0, "commercial": 16.0}.get(st["id"], 15.0)
        self.D = {"ranch1970": 10.5, "twostory1990": 10.0, "farmhouse": 10.0, "cottage": 8.0, "modern": 10.0, "commercial": 12.0}.get(st["id"], 10.0)
        self.L *= 0.92 + 0.16 * r.random()
        self.D *= 0.94 + 0.12 * r.random()
        self.roof_type = pick(r, st["roof"]["type"])
        self.pitch = math.radians(st["roof"]["pitch_deg"])
        self.ov = st["roof"]["overhang_m"]
        self.roof_fin = pick(r, st["roof"]["finish"])
        if self.roof_type == "flat":
            self.roof_fin = "membrane_flat"
        elif self.roof_fin == "membrane_flat":
            self.roof_fin = "metal_seam"
        self.palette = dict(r.choice(st["palettes"]))
        self.galvalume = r.random() < st["roof"].get("galvalume_chance", 0.0)
        if st["windows"].get("sash_override"):
            self.palette["sash"] = st["windows"]["sash_override"]
        w = st["wall"]
        self.fin_front = pick(r, w["front"])
        self.fin_sides = self.fin_front if w["sides"] in ("same", "front") else pick(r, w["sides"])
        up = w.get("upper", "same")
        self.fin_upper = self.fin_sides if up == "same" else pick(r, up)
        self.fin_upper_front = self.fin_front if w.get("upper_front") == "front" else self.fin_upper
        g = w.get("gables", "same")
        self.fin_gable = self.fin_sides if g in ("same", "front") else pick(r, g)
        self.wainscot = pick(r, w["wainscot"]) if w.get("wainscot") and r.random() < 0.7 else None
        self.reveal = w["reveal_m"]
        self.eave = self.floor + self.storeys * self.plate
        self.grid = tuple(pick(r, st["windows"]["grid"]))
        self.parapet = st["trim"].get("parapet", False) and self.roof_type == "flat"

    # -------------------------------------------------------------- helpers
    def is_brick(self, fin):
        return fin.startswith("brick") or fin == "limestone"

    def part(self, key, builder, *args, **kw):
        """Build a part once per variant and place linked copies."""
        if key not in self.cache:
            ob = builder(*args, **kw)
            ob.name = f"KIT_{key}"
            ob.hide_render = True
            ob.hide_viewport = True
            for ch in ob.children:
                ch.hide_render = True
            self.cache[key] = ob
        return self.cache[key]

    def place(self, key, src, M):
        ob = src.copy()
        ob.hide_render = False
        ob.hide_viewport = False
        ob.matrix_world = Matrix.Translation(self.o) @ M
        bpy.context.scene.collection.objects.link(ob)
        self.placed.append(ob)
        self.used[key] = self.used.get(key, 0) + 1
        return ob

    def wall_frame(self, side):
        """(origin at the run's left end seen from outside, along, out, length) for front/right/back/left."""
        L, D = self.L, self.D
        if side == "front":
            return Vector((-L / 2, -D / 2, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)), L
        if side == "right":
            return Vector((L / 2, -D / 2, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)), D
        if side == "back":
            return Vector((L / 2, D / 2, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), L
        return Vector((-L / 2, D / 2, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0)), D

    def M_on(self, side, u, z, depth=0.0):
        """Matrix putting a part (X along the wall, +Y out, Z up) at u along a wall run, height z, set back by depth."""
        o, a, n, _ = self.wall_frame(side)
        p = o + a * u + n * (-depth) + Vector((0, 0, z))
        m = Matrix((a, n, Vector((0, 0, 1)))).transposed().to_4x4()
        m.translation = p
        return m

    def quad(self, pts, kind, fin):
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(p) for p in pts])
        ob = G.mesh_obj("q", bm)
        ob.data.transform(Matrix.Translation(self.o))
        (K.wall if kind == "wall" else K.roof)(ob, fin)
        self.pieces.append(ob)
        return ob

    def tbox(self, x0, x1, y0, y1, z0, z1, band, paint=TRIM_S, M=None):
        ob = K.box("b", x0, x1, y0, y1, z0, z1)
        if M is not None:
            ob.data.transform(M)
        ob.data.transform(Matrix.Translation(self.o))
        K.trim(ob, band, paint)
        self.pieces.append(ob)
        return ob

    # -------------------------------------------------------------- openings
    def plan_openings(self):
        r = self.rng
        st = self.s
        win = st["windows"]
        main = pick(r, win["main"])
        feat = pick(r, win["front_feature"])
        sill = win["sill_m"]
        L, D = self.L, self.D
        ops = {s: [] for s in ("front", "right", "back", "left")}

        def size(part):
            row = K.SIZES.get(part) or K.SIZES.get(P.PARTS[part]["row"])
            w, h = row["w"], row["h"]
            if part == "WinArchTop3060":
                h += row["w"] / 2
            if part == "WinTwin3050":
                w = 2 * K.SIZES["WinSingleHung3050"]["w"] + 0.052
            return w, h

        # ground floor front: garage at the right end, door, a feature window by the door
        u_free = [0.9, L - 0.9]
        gar = st.get("garage")
        if gar:
            gp = pick(r, gar["part"])
            gw, gh = size(gp)
            gx = L - 0.9 - gw / 2 - 0.2
            ops["front"].append(dict(part=gp, u=gx, z=0.0, w=gw, h=gh, kind="garage"))
            u_free[1] = gx - gw / 2 - 0.6
            self.garage_u = gx
            self.garage_w = gw
        dp = pick(r, st["door"])
        dw, dh = size(dp)
        if dp == "DoorPatioSlider":
            dx = (u_free[0] + u_free[1]) * 0.5
        else:
            dx = u_free[0] + (u_free[1] - u_free[0]) * (0.42 + 0.12 * r.random())
        ops["front"].append(dict(part=dp, u=dx, z=self.floor, w=dw, h=dh, kind="door"))
        self.door_u = dx
        fw, fh = size(feat)
        top = self.floor + 2.134       # window heads line up with the door head, 2.13 m above the floor
        fz = top - fh if feat != "WinArchTop3060" else self.floor + 0.6
        if self.s["id"] == "modern":
            fz = self.floor + 0.45
        left_space = (u_free[0], dx - dw / 2 - 0.5)
        if left_space[1] - left_space[0] > fw + 0.4:
            fx = left_space[0] + (left_space[1] - left_space[0]) * 0.5
            ops["front"].append(dict(part=feat, u=fx, z=fz, w=fw, h=fh, kind="window", feature=True))
            # more windows to the left of the feature if there is room
            spare = (left_space[0], fx - fw / 2 - 0.6)
            mw, mh = size(main)
            if spare[1] - spare[0] > mw + 0.4:
                ops["front"].append(dict(part=main, u=(spare[0] + spare[1]) / 2, z=top - mh if main != "WinCasement2470" else self.floor + 0.10, w=mw, h=mh, kind="window"))
        right_space = (dx + dw / 2 + 0.6, u_free[1])
        mw, mh = size(main)
        mz = top - mh if main != "WinCasement2470" else self.floor + 0.10
        if right_space[1] - right_space[0] > mw + 0.4:
            n = max(1, int((right_space[1] - right_space[0]) // win["every_m"]))
            for k in range(n):
                ops["front"].append(dict(part=main, u=right_space[0] + (k + 0.5) * (right_space[1] - right_space[0]) / n, z=mz, w=mw, h=mh, kind="window"))
        # sides: a window or two per storey, a bathroom window on the left
        for side in ("right", "left"):
            for s_ in range(self.storeys):
                zb = self.floor + s_ * self.plate
                n = max(1, int((D - 2.0) // (win["every_m"] + 0.8)))
                for k in range(n):
                    part = main if not (side == "left" and k == 0 and s_ == 0) else win["bath"]
                    pw, ph = size(part)
                    z = zb + (1.55 if part == win["bath"] else (2.134 - ph if part != "WinCasement2470" else 0.10))
                    ops[side].append(dict(part=part, u=1.2 + (k + 0.5) * (D - 2.4) / n, z=z, w=pw, h=ph, kind="window"))
        # back (the lake side): a patio slider and windows, more glass
        bp = "DoorPatioSlider"
        bw, bh = size(bp)
        bx = L * (0.35 + 0.1 * r.random())
        ops["back"].append(dict(part=bp, u=bx, z=self.floor, w=bw, h=bh, kind="door"))
        nb = max(2, int(L // win["every_m"]))
        for k in range(nb):
            u = 0.9 + (k + 0.5) * (L - 1.8) / nb
            if abs(u - bx) < bw / 2 + mw / 2 + 0.4:
                continue
            ops["back"].append(dict(part=feat if k == nb - 1 and feat != "WinArchTop3060" else main, u=u, z=mz if feat == "WinArchTop3060" or k != nb - 1 else top - fh, w=fw if k == nb - 1 and feat != "WinArchTop3060" else mw, h=fh if k == nb - 1 and feat != "WinArchTop3060" else mh, kind="window"))
        # upper storey: windows over the ground-floor openings on front and back
        for s_ in range(1, self.storeys):
            zb = self.floor + s_ * self.plate
            for side in ("front", "back"):
                for op in list(ops[side]):
                    if op.get("storey", 0) or op["kind"] == "garage" and side == "back":
                        continue
                    if op["kind"] == "door" and side == "front" and feat == "WinArchTop3060":
                        continue
                    part = main
                    pw, ph = size(part)
                    if op.get("feature") and feat == "WinArchTop3060" and side == "front":
                        continue
                    ops[side].append(dict(part=part, u=op["u"], z=zb + (2.134 - ph if part != "WinCasement2470" else 0.10), w=pw, h=ph, kind="window", storey=s_))
            if st["windows"].get("front_feature") and feat == "WinArchTop3060":
                fwid, fht = size(feat)
                ops["front"].append(dict(part=feat, u=self.door_u, z=zb + 0.25, w=fwid, h=fht, kind="window", storey=s_, feature=True))
        self.ops = ops
        return ops

    # -------------------------------------------------------------- walls
    def wall_rects(self, length, z0, z1, holes):
        """Rectangles covering u 0..length, z z0..z1 minus the holes (u0, u1, h0, h1)."""
        us = sorted({0.0, length} | {max(0.0, min(length, x)) for h in holes for x in (h[0], h[1])})
        out = []
        for a, b in zip(us, us[1:]):
            if b - a < 1e-4:
                continue
            m = (a + b) / 2
            cut = sorted([(max(h[2], z0), min(h[3], z1)) for h in holes if h[0] < m < h[1] and h[3] > z0 and h[2] < z1])
            z = z0
            for c0, c1 in cut:
                if c0 > z + 1e-4:
                    out.append((a, b, z, c0))
                z = max(z, c1)
            if z1 > z + 1e-4:
                out.append((a, b, z, z1))
        return out

    def finish_for(self, side, z):
        storey = int((z - self.floor) // self.plate) if z > self.floor else 0
        if storey >= 1:
            return self.fin_upper_front if side == "front" else self.fin_upper
        if self.wainscot and side == "front" and z < self.floor + 0.9:
            return self.wainscot
        return self.fin_front if side == "front" else self.fin_sides

    def build_walls(self):
        top = self.eave
        for side in ("front", "right", "back", "left"):
            o, a, n, length = self.wall_frame(side)
            holes = [(op["u"] - op["w"] / 2, op["u"] + op["w"] / 2, op["z"], op["z"] + op["h"]) for op in self.ops[side]]
            bands = [self.floor - (0.0 if self.raised else 0.0)]
            for s_ in range(1, self.storeys):
                bands.append(self.floor + s_ * self.plate)
            if self.wainscot and side == "front":
                bands.append(self.floor + 0.9)
            bands = sorted(set(bands)) + [top + (0.7 if self.parapet else 0.0)]
            for z0, z1 in zip(bands, bands[1:]):
                fin = self.finish_for(side, (z0 + z1) / 2 if z1 - z0 < 1.0 else z0 + 0.01)
                for (u0, u1, h0, h1) in self.wall_rects(length, z0, z1, holes):
                    pts = [o + a * u0 + Vector((0, 0, h0)), o + a * u1 + Vector((0, 0, h0)), o + a * u1 + Vector((0, 0, h1)), o + a * u0 + Vector((0, 0, h1))]
                    self.quad(pts, "wall", fin)
            if self.wainscot and side == "front":   # a cast-stone ledge on the wainscot
                self.tbox(0, length, 0.0, 0.06, self.floor + 0.9, self.floor + 0.95, "cast_stone", M=self.M_on(side, 0, 0))
            # reveals (returns) round every opening: the wall finish, into the wall by the reveal depth
            for op in self.ops[side]:
                rv = max(self.reveal, 0.03)
                fin = self.finish_for(side, op["z"] + 0.5)
                u0, u1, z0, z1 = op["u"] - op["w"] / 2, op["u"] + op["w"] / 2, op["z"], op["z"] + op["h"]
                P0 = lambda u, z, d: o + a * u - n * d + Vector((0, 0, z))
                for (pa, pb, pc, pd) in (((u0, z0), (u0, z1), (u0, z1), (u0, z0)), ((u1, z1), (u1, z0), (u1, z0), (u1, z1)), ((u0, z1), (u1, z1), (u1, z1), (u0, z1))):
                    q = [P0(pa[0], pa[1], 0.0), P0(pb[0], pb[1], 0.0), P0(pc[0], pc[1], rv), P0(pd[0], pd[1], rv)]
                    self.quad(q, "wall", fin)
                if op["kind"] == "window":
                    q = [P0(u1, z0, 0.0), P0(u0, z0, 0.0), P0(u0, z0, rv), P0(u1, z0, rv)]
                    self.quad(q, "wall", fin)
                self.openings.append(dict(side=side, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in op.items()}))

    # -------------------------------------------------------------- parts in the openings
    def build_openings(self):
        st = self.s
        sh = st.get("shutters")
        use_sh = bool(sh) and self.rng.random() < sh["chance"]
        sh_part = pick(self.rng, sh["part"]) if use_sh else None
        casing = st["trim"]["casing"]
        sill = st["trim"]["sill"]
        for side, ops in self.ops.items():
            for op in ops:
                part = op["part"]
                key = part
                kw = {}
                if part in ("WinSingleHung3050", "WinSingleHung3060"):
                    kw = {"grid": self.grid, "seed": (self.seed * 0.137 + op["u"] * 0.01) % 1.0}
                    key = f"{part}_{self.grid[0]}x{self.grid[1]}"
                src = self.part(key, P.PARTS[part]["build"], **({"name": key} | kw))
                depth = max(self.reveal, 0.03) - 0.0 if op["kind"] != "garage" else 0.02
                depth = max(self.reveal, 0.03) if op["kind"] != "garage" else max(self.reveal, 0.03)
                self.place(key, src, self.M_on(side, op["u"], op["z"], depth))
                fin = self.finish_for(side, op["z"] + 0.5)
                brick = self.is_brick(fin) or fin == "stucco"
                u0, u1, z0, z1 = op["u"] - op["w"] / 2, op["u"] + op["w"] / 2, op["z"], op["z"] + op["h"]
                M = self.M_on(side, 0, 0)
                if op["kind"] == "window" and not brick and casing != "none":
                    cw, cd, band = (0.089, 0.019, "paint_grain") if casing == "CasingFlat" else (0.051, 0.032, "paint_smooth")
                    self.tbox(u0 - cw, u0, 0.0, cd, z0, z1 + cw, band, M=M)
                    self.tbox(u1, u1 + cw, 0.0, cd, z0, z1 + cw, band, M=M)
                    self.tbox(u0 - cw - 0.01, u1 + cw + 0.01, 0.0, cd + 0.006, z1, z1 + cw + 0.02, band, M=M)
                    self.tbox(u0 - cw, u1 + cw, 0.0, cd + 0.01, z0 - 0.05, z0 - 0.005, band, M=M)
                if op["kind"] == "door" and casing != "none" and not brick:
                    cw = 0.089
                    for (a0, a1, b0, b1) in ((u0 - cw - 0.02, u0 - 0.02, z0, z1 + 0.02), (u1 + 0.02, u1 + cw + 0.02, z0, z1 + 0.02), (u0 - cw - 0.03, u1 + cw + 0.03, z1 + 0.02, z1 + 0.13)):
                        self.tbox(a0, a1, 0.0, 0.022, b0, b1, "paint_grain", M=M)
                if op["kind"] == "window" and brick and sill == "SillCastStone" and self.is_brick(fin):
                    ss = self.part(f"Sill_{op['w']:.2f}", P.sill_cast, name=f"Sill_{op['w']:.2f}", width=op["w"] + 0.18)
                    self.place("SillCastStone", ss, self.M_on(side, op["u"], z0 - 0.10, 0.03))
                    # a soldier course over the head reads as a flat lintel: an angle-iron edge
                    self.tbox(u0 - 0.05, u1 + 0.05, 0.0, 0.006, z1, z1 + 0.012, "black_iron", FIXED_PAINT, M=M)
                if op["kind"] == "garage" and casing == "none" and not brick:
                    pass
                if use_sh and side == "front" and op["kind"] == "window" and op["part"] not in ("WinPicture6050", "WinSmall2030") and op["w"] < 1.0:
                    sk = f"{sh_part}_{op['h']:.2f}"
                    kind = {"ShutterLouvre": "louvre", "ShutterPanel": "panel", "ShutterBoard": "board"}[sh_part]
                    if sk not in self.cache:
                        o_ = K.part(sk, P.shutter(sk, op["w"] * 0.42, op["h"], kind))
                        o_.hide_render = True
                        self.cache[sk] = o_
                    for sgn in (-1, 1):
                        uu = op["u"] + sgn * (op["w"] / 2 + 0.02 + op["w"] * 0.21 + (0.05 if casing != "none" and not brick else 0.0))
                        self.place(sh_part, self.cache[sk], self.M_on(side, uu, z0, -0.005))
                if op["kind"] in ("door", "garage") and side in ("front", "back"):
                    lp = pick(self.rng, st["lights"]) if not hasattr(self, "light_part") else self.light_part
                    self.light_part = lp
                    ls = self.part(lp, P.PARTS[lp]["build"])
                    for sgn in ((-1, 1) if op["kind"] == "door" and side == "front" else (-1,) if op["kind"] == "garage" else (1,)):
                        uu = op["u"] + sgn * (op["w"] / 2 + 0.30)
                        self.place(lp, ls, self.M_on(side, uu, op["z"] + (1.70 if op["kind"] == "door" else 2.25), 0.0))

    # -------------------------------------------------------------- roof
    def roof_z(self, x, y):
        """Roof surface height over plan point (x, y) (house frame)."""
        L, D, e, p = self.L, self.D, self.eave, self.pitch
        if self.roof_type == "gable":
            return e + (D / 2 - abs(y)) * math.tan(p)
        if self.roof_type == "hip":
            return e + min(D / 2 - abs(y), L / 2 - abs(x)) * math.tan(p)
        if self.roof_type == "shed":
            return e + (y + D / 2) * math.tan(p)
        return e + 0.25

    def build_roof(self):
        L, D, e, p, ov = self.L, self.D, self.eave, self.pitch, self.ov
        fin = self.roof_fin
        t = math.tan(p)
        drop = ov * t
        V = Vector
        ridge_runs = []
        eaves = []      # (start, end) at the fascia's top, outward direction
        if self.roof_type == "gable":
            zr = e + D / 2 * t
            xo = L / 2 + 0.3
            for sy in (-1, 1):
                self.quad([V((-xo, sy * (D / 2 + ov), e - drop)), V((xo, sy * (D / 2 + ov), e - drop)), V((xo, 0, zr)), V((-xo, 0, zr))], "roof", fin)
                eaves.append((V((-xo, sy * (D / 2 + ov), e - drop)), V((xo, sy * (D / 2 + ov), e - drop)), V((0, sy, 0))))
            ridge_runs.append((V((-xo, 0, zr)), V((xo, 0, zr))))
            for sx in (-1, 1):   # gable triangles and the rake boards
                x = sx * L / 2
                self.quad([V((x, -D / 2, e)), V((x, D / 2, e)), V((x, 0, zr))], "wall", self.fin_gable)
                for sy in (-1, 1):
                    a, b = V((sx * xo, sy * (D / 2 + ov), e - drop)), V((sx * xo, 0, zr))
                    rk = G.sweep("rake", [a + V((0, 0, -0.02)), b + V((0, 0, -0.02))], [(-0.015, -0.16), (0.015, -0.16), (0.015, 0.0), (-0.015, 0.0)], twist_up=(sx, 0, 0))
                    rk.data.transform(Matrix.Translation(self.o))
                    K.trim(rk, "paint_smooth", TRIM_S)
                    self.pieces.append(rk)
                    # soffit under the rake overhang
                    self.quad_trim([V((x, sy * D / 2, e)), V((sx * xo, sy * (D / 2 + ov), e - drop)), V((sx * xo, 0, zr - 0.02)), V((x, 0, zr - 0.02))])
                gv = self.part("GableVent", P.PARTS["GableVent"]["build"])
                side = "right" if sx > 0 else "left"
                self.place("GableVent", gv, self.M_on(side, D / 2, e + (zr - e) * 0.35, -0.0))
        elif self.roof_type == "hip":
            zr = e + min(D, L) / 2 * t
            hx = max(L / 2 - D / 2, 0.0)
            c = [V((-L / 2 - ov, -D / 2 - ov, e - drop)), V((L / 2 + ov, -D / 2 - ov, e - drop)), V((L / 2 + ov, D / 2 + ov, e - drop)), V((-L / 2 - ov, D / 2 + ov, e - drop))]
            r0, r1 = V((-hx, 0, zr)), V((hx, 0, zr))
            self.quad([c[0], c[1], r1, r0], "roof", fin)
            self.quad([c[2], c[3], r0, r1], "roof", fin)
            self.quad([c[1], c[2], r1], "roof", fin)
            self.quad([c[3], c[0], r0], "roof", fin)
            for a, b, n in ((c[0], c[1], V((0, -1, 0))), (c[1], c[2], V((1, 0, 0))), (c[2], c[3], V((0, 1, 0))), (c[3], c[0], V((-1, 0, 0)))):
                eaves.append((a, b, n))
            ridge_runs += [(r0, r1), (c[0], r0), (c[1], r1), (c[2], r1), (c[3], r0)]
        elif self.roof_type == "shed":
            zb = e + D * t
            xo = L / 2 + ov
            self.quad([V((-xo, -D / 2 - ov, e - drop)), V((xo, -D / 2 - ov, e - drop)), V((xo, D / 2 + ov, zb + drop)), V((-xo, D / 2 + ov, zb + drop))], "roof", fin)
            eaves.append((V((-xo, -D / 2 - ov, e - drop)), V((xo, -D / 2 - ov, e - drop)), V((0, -1, 0))))
            for sx in (-1, 1):
                x = sx * L / 2
                self.quad([V((x, -D / 2, e)), V((x, D / 2, e)), V((x, D / 2, zb))], "wall", self.fin_sides)
                # a deep fascia along each rake, front eave to back
                a, b = V((sx * xo, -D / 2 - ov, e - drop)), V((sx * xo, D / 2 + ov, zb + drop))
                rk = G.sweep("rake", [a, b], [(-0.02, -0.25), (0.02, -0.25), (0.02, 0.02), (-0.02, 0.02)], twist_up=(sx, 0, 0))
                rk.data.transform(Matrix.Translation(self.o))
                K.trim(rk, "black_iron")
                self.pieces.append(rk)
            # back wall's clerestory above the eave
            self.quad([V((L / 2, D / 2, e)), V((-L / 2, D / 2, e)), V((-L / 2, D / 2, zb)), V((L / 2, D / 2, zb))], "wall", self.fin_upper)
        else:   # flat behind a parapet
            z = e + 0.25
            self.quad([V((-L / 2, -D / 2, z)), V((L / 2, -D / 2, z)), V((L / 2, D / 2, z)), V((-L / 2, D / 2, z))], "roof", "membrane_flat")
            topz = e + 0.7
            for (x0, x1, y0, y1) in ((-L / 2 - 0.03, L / 2 + 0.03, -D / 2 - 0.03, -D / 2 + 0.2), (-L / 2 - 0.03, L / 2 + 0.03, D / 2 - 0.2, D / 2 + 0.03),
                                     (-L / 2 - 0.03, -L / 2 + 0.2, -D / 2, D / 2), (L / 2 - 0.2, L / 2 + 0.03, -D / 2, D / 2)):
                self.tbox(x0, x1, y0, y1, topz, topz + 0.06, "cast_stone" if self.s["id"] == "commercial" else "black_iron")
            for sgn in (-1, 1):   # inner parapet faces
                self.quad([V((sgn * L / 2 * 0.99, -D / 2, z)), V((sgn * L / 2 * 0.99, D / 2, z)), V((sgn * L / 2 * 0.99, D / 2, topz)), V((sgn * L / 2 * 0.99, -D / 2, topz))], "wall", self.fin_sides)
        # fascia, soffit, frieze and gutters along every eave
        gut = self.rng.random() < self.s["gutters"]["chance"]
        for a, b, n in eaves:
            L_ = (b - a).length
            along = (b - a).normalized()
            m = Matrix((along, n, V((0, 0, 1)))).transposed().to_4x4()
            m.translation = a
            self.tbox(0, L_, 0.0, 0.025, -0.16, 0.01, "paint_smooth", M=m)
            wall_off = ov
            self.quad_trim([a, b, b - n * wall_off + V((0, 0, 0)), a - n * wall_off])
            if self.s["trim"].get("frieze"):
                self.tbox(ov, L_ - ov, -ov - 0.0, -ov + 0.02, -0.16, 0.0, "paint_smooth", M=m)
            if gut:
                gs = P.gutter("gut", length=L_ + 0.02)
                gs.data.transform(Matrix.Translation((L_ / 2, 0.025, -0.15)))
                gs.data.transform(m)
                gs.data.transform(Matrix.Translation(self.o))
                self.pieces.append(gs)
                if n.length > 0:
                    # downspouts at both ends of the long eaves, on the wall corner below
                    for f in ((0.0 + ov + 0.15), (L_ - ov - 0.15)):
                        h = (a.z - 0.15)
                        dsk = f"Downspout_{h:.2f}"
                        ds = self.part(dsk, P.downspout, name=dsk, height=h, off=ov + 0.04)
                        mm = m.copy()
                        pos = a + along * f - n * ov
                        mm.translation = V((pos.x, pos.y, 0.0))
                        self.place("Downspout", ds, mm)
        for a, b in ridge_runs:
            if self.roof_type in ("flat", "shed"):
                continue
            Lr = (b - a).length
            rk = f"Ridge_{Lr:.2f}"
            rc = self.part(rk, P.ridge_cap, name=rk, length=Lr, pitch_deg=math.degrees(self.pitch) if (a.z == b.z) else 15.0, finish=self.roof_fin)
            mm = G.frame((a + b) / 2, b - a)
            self.place("RidgeCap", rc, mm)
        self.roof_extras()

    def shear_y(self, t, z0, y0):
        return Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, t, 1, z0 - t * y0), (0, 0, 0, 1)))

    def quad_trim(self, pts):
        bm = bmesh.new()
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        f.normal_update()
        if f.normal.z > 0:
            f.normal_flip()
        ob = G.mesh_obj("soffit", bm)
        ob.data.transform(Matrix.Translation(self.o))
        K.trim(ob, "paint_smooth", TRIM_S)
        self.pieces.append(ob)

    def roof_extras(self):
        r = self.rng
        st = self.s
        L, D = self.L, self.D
        rv = st["roof_vents"]
        on_back = lambda x, frac: (x, D / 2 * frac, self.roof_z(x, D / 2 * frac))
        if self.roof_type in ("gable", "hip", "shed"):
            for k in range(r.randint(*rv["turbine"])):
                x = (k - 0.5) * 2.4
                p = on_back(x, 0.18)
                self.place("TurbineVent", self.part("TurbineVent", P.turbine), Matrix.Translation(p))
            for k in range(r.randint(*rv["box"])):
                p = on_back(-L / 4 + k * 1.6, 0.25)
                self.place("BoxVent", self.part("BoxVent", P.box_vent), Matrix.Translation(p) @ Matrix.Rotation(-self.pitch, 4, "X"))
        for k in range(r.randint(*rv["stacks"])):
            p = on_back(L / 5 - k * 2.1, 0.55) if self.roof_type != "flat" else (L / 5 - k * 2.1, 1.0, self.eave + 0.25)
            self.place("StackPipe", self.part("StackPipe", P.stack_pipe), Matrix.Translation(p))
        ch = st.get("chimney")
        if ch and r.random() < ch["chance"]:
            cp = pick(r, ch["part"])
            x = -L / 2 + 2.2 + r.random() * 1.5
            if cp == "ChimneyFlue":
                y = D / 4
                base = self.roof_z(x, y)
                key = "ChimneyFlue"
                src = self.part(key, P.chimney_flue)
                self.place(key, src, Matrix.Translation((x, y, base)))
            else:
                y = 0.0 if self.roof_type in ("gable", "hip") else D / 4
                d = K.SIZES[cp]["d"]
                base = self.roof_z(x, y + d / 2) - 0.05 if self.roof_type != "flat" else self.eave + 0.25
                top = self.roof_z(x, y) + 0.6 if self.roof_type != "flat" else self.eave + 1.6
                fin = ch.get("finish") or (self.fin_front if self.is_brick(self.fin_front) and cp == "ChimneyBrick" else ("brick_red" if cp == "ChimneyBrick" else self.fin_upper if not self.is_brick(self.fin_upper) else "lap_siding"))
                key = f"{cp}_{top - base:.2f}_{fin}"
                b = P.chimney_brick if cp == "ChimneyBrick" else P.chimney_chase
                src = self.part(key, b, name=key, height=top - base, finish=fin)
                self.place(cp, src, Matrix.Translation((x, y, base)))
        if st.get("dormers") and r.random() < st["dormers"]["chance"] and self.roof_type == "gable":
            n = r.randint(*st["dormers"]["count"])
            for k in range(n):
                x = -L / 2 + L * (k + 1) / (n + 1)
                if abs(x - (self.door_u - L / 2)) < 1.2:
                    x += 1.6
                y = -D / 2 + 0.9
                z = self.roof_z(x, y)
                key = f"Dormer_{self.roof_fin}_{self.fin_gable}"
                src = self.part(key, P.dormer_gable, name=key, pitch_deg=math.degrees(self.pitch), wall_fin=self.fin_gable, roof_fin=self.roof_fin)
                self.place("DormerGable", src, Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.pi, 4, "Z"))

    # -------------------------------------------------------------- porch, foundation, services
    def build_porch(self):
        st = self.s
        po = st.get("porch")
        if not po:
            return
        L, D = self.L, self.D
        y0 = -D / 2
        kind = po["kind"]
        dpt = po["depth_m"]
        if kind == "canopy":
            u = self.door_u - L / 2
            w = 3.2
            z = self.floor + 2.75
            self.tbox(u - w / 2, u + w / 2, y0 - dpt, y0, z, z + 0.20, "black_iron")
            self.tbox(u - w / 2 + 0.03, u + w / 2 - 0.03, y0 - dpt + 0.03, y0, z - 0.004, z, "cedar")
            self.tbox(u - 1.2, u + 1.2, y0 - 1.6, y0, 0.0, self.floor, "concrete")
            return
        if kind == "stoop":
            u = self.door_u - L / 2
            x0, x1 = u - 1.6, u + 1.6
        else:
            x0 = -L / 2 + 0.3
            x1 = (self.garage_u - L / 2 - getattr(self, "garage_w", 0) / 2 - 0.4) if hasattr(self, "garage_u") else L / 2 - 0.3
        fz = self.floor
        # floor: a slab, or a deck on the raised cottage
        if self.raised:
            self.tbox(x0, x1, y0 - dpt, y0, fz - 0.05, fz, "paint_grain", TRIM_S)
            for xx in (x0 + 0.1, (x0 + x1) / 2, x1 - 0.1):
                self.tbox(xx - 0.07, xx + 0.07, y0 - dpt + 0.05, y0 - dpt + 0.19, 0.0, fz - 0.05, "cedar")
        else:
            self.tbox(x0, x1, y0 - dpt, y0, 0.0, fz, "concrete")
        h = self.plate - 0.15
        col = po.get("columns", "ColumnSquare")
        n = max(2, int(round((x1 - x0) / 2.6)) + 1)
        b = P.PARTS[col]["build"]
        key = f"{col}_{h:.2f}"
        src = self.part(key, b, name=key, height=h)
        xs = [x0 + 0.2 + (x1 - x0 - 0.4) * k / (n - 1) for k in range(n)]
        for xx in xs:
            self.place(col, src, Matrix.Translation((xx, y0 - dpt + 0.2, fz)))
        # beam and the porch roof: a shed from under the eave down to the beam
        zb = fz + h
        self.tbox(x0, x1, y0 - dpt + 0.05, y0 - dpt + 0.35, zb, zb + 0.28, "cedar" if col == "PostCedar" else "paint_smooth")
        ztop = min(self.floor + self.plate - 0.05, self.eave - 0.05) if self.storeys > 1 or kind == "full" else zb + 0.6
        if self.storeys == 1 and kind == "full":
            ztop = self.eave - 0.1
        fin = self.roof_fin if po.get("roof", "same") == "same" else po["roof"]
        fin = "metal_seam" if fin == "membrane_flat" else fin
        ov = 0.25
        V = Vector
        self.quad([V((x0 - ov, y0 - dpt - ov, zb + 0.28)), V((x1 + ov, y0 - dpt - ov, zb + 0.28)), V((x1 + ov, y0 - 0.0, ztop)), V((x0 - ov, y0, ztop))], "roof", fin)
        self.tbox(x0 - ov, x1 + ov, y0 - dpt - ov - 0.025, y0 - dpt - ov, zb + 0.10, zb + 0.30, "paint_smooth")
        self.quad_trim([V((x0, y0 - dpt + 0.05, zb + 0.28)), V((x1, y0 - dpt + 0.05, zb + 0.28)), V((x1, y0, zb + 0.28)), V((x0, y0, zb + 0.28))])
        if po.get("rails"):
            gaps = [(xs[k], xs[k + 1]) for k in range(len(xs) - 1)]
            mid = len(gaps) // 2
            for k, (a, b_) in enumerate(gaps):
                if k == mid:
                    continue
                Lr = b_ - a - 0.2
                rk = f"Rail_{Lr:.2f}"
                rs = self.part(rk, P.rail_baluster, name=rk, length=Lr)
                self.place("RailBaluster", rs, Matrix.Translation(((a + b_) / 2, y0 - dpt + 0.2, fz)))
        steps = po.get("steps", 1)
        if steps:
            u = self.door_u - L / 2 if kind == "stoop" or not po.get("rails") else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2 if len(xs) > 1 else self.door_u - L / 2
            risers = max(1, int(round(fz / 0.178))) if self.raised else 1
            sk = f"Steps_{risers}"
            ss = self.part(sk, P.steps_concrete, name=sk, width=1.5, risers=risers, rail=risers > 2)
            self.place("StepsConcrete", ss, Matrix.Translation((u, y0 - dpt, 0.0)) @ Matrix.Rotation(math.pi, 4, "Z"))

    def build_base(self):
        st = self.s
        for side in ("front", "right", "back", "left"):
            o, a, n, length = self.wall_frame(side)
            if st["foundation"] == "SkirtLattice":
                sk = f"Skirt_{length:.2f}"
                src = self.part(sk, P.skirt_lattice, name=sk, length=length, height=self.raised)
                self.place("SkirtLattice", src, self.M_on(side, length / 2, 0.0, -0.005))
            else:
                self.tbox(0, length, 0.0, 0.02, -0.10, self.floor, "concrete", FIXED_PAINT, M=self.M_on(side, 0, 0))
            if st["trim"]["corner_boards"] and not self.is_brick(self.fin_sides):
                cb = f"Corner_{self.eave - self.floor:.2f}"
                src = self.part(cb, P.corner_board, name=cb, length=self.eave - self.floor)
                self.place("CornerBoard", src, self.M_on(side, 0.0, self.floor, 0.0))
        # services on the right side: AC, meters
        ac, n_ac = st["ac"]
        if ac == "ACCondenser":
            src = self.part(ac, P.ac_condenser)
            for k in range(n_ac):
                self.place(ac, src, self.M_on("right", self.D * 0.55 + k * 1.1, 0.0, 0.0))
        else:
            src = self.part(ac, P.ac_window)
            ops = [o_ for o_ in self.ops["right"] if o_["kind"] == "window"]
            if ops:
                o_ = ops[0]
                self.place(ac, src, self.M_on("right", o_["u"], o_["z"] + 0.12, max(self.reveal, 0.03) - 0.02))
        if st.get("meters"):
            self.place("MeterElectric", self.part("MeterElectric", P.meter_electric), self.M_on("right", 1.2, 1.55, 0.0))
            self.place("MeterGas", self.part("MeterGas", P.meter_gas), self.M_on("right", 2.0, 0.0, -0.0))

    def build(self):
        self.plan_openings()
        self.build_walls()
        self.build_openings()
        self.build_roof()
        self.build_porch()
        self.build_base()
        body = G.join(f"House_{self.s['id']}_{self.seed}", [p for p in self.pieces])
        K.finish_part(body)
        self.body = body
        tri = K.tris(body) + sum(K.tris(o) for o in self.placed)
        return dict(style=self.s["id"], seed=self.seed, length=round(self.L, 2), depth=round(self.D, 2), roof=self.roof_type,
                    roof_finish=self.roof_fin, galvalume=self.galvalume, wall_front=self.fin_front, wall_sides=self.fin_sides, palette=self.palette,
                    tris=tri, parts=self.used, openings=self.openings)


FIXED_PAINT = K.FIXED


def ground(extent=400.0, drive=None):
    bpy.ops.mesh.primitive_plane_add(size=extent, location=(0, 0, 0))
    g = bpy.context.active_object
    m = bpy.data.materials.new("Lawn")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.4
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.10, 0.12, 0.045, 1)
    ramp.color_ramp.elements[1].color = (0.17, 0.17, 0.07, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    g.data.materials.append(m)
    return g


def camera(loc, target, lens=35.0):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 2000
    c = bpy.data.objects.new("Cam", cd)
    bpy.context.scene.collection.objects.link(c)
    c.location = loc
    d = Vector(target) - Vector(loc)
    c.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = c
    return c


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sid, seed, out = argv[0], int(argv[1]), argv[2]
    flags = set(argv[3:])
    os.makedirs(out, exist_ok=True)
    import hk_preview as PV
    G.clear_scene()
    style = json.load(open(os.path.join(HERE, "styles", f"{sid}.json")))
    trim_dir = os.path.join(K.REPO, "Artifacts", "buildkit", "trim")
    if not os.path.exists(os.path.join(trim_dir, "T_HouseTrim_C.png")):
        import subprocess
        subprocess.run([sys.executable, os.path.join(HERE, "make_trim_sheet.py"), trim_dir], check=True)
    seeds = [seed, seed + 1, seed + 2] if "--row" in flags else [seed]
    infos = []
    houses = []
    for k, sd in enumerate(seeds):
        h = House(style, sd, origin=((k - (len(seeds) - 1) / 2) * 24.0, 0.0))
        infos.append(h.build())
        houses.append(h)
    h0 = houses[0]
    if "body" in h0.palette:
        r, g, b, _ = PV._hex(h0.palette["body"])
        for fid in (4, 5, 6):
            PV.WALL_PREVIEW[fid] = ((r, g, b), (0, 0, 0), PV.WALL_PREVIEW[fid][2])
    if h0.galvalume:
        PV.ROOF_PREVIEW[3] = (0.50, 0.52, 0.53)
    elif "roof" in h0.palette:
        PV.ROOF_PREVIEW[3] = PV._hex(h0.palette["roof"])[:3]
    PV.setup_materials(h0.palette, trim_dir)
    ground()
    tag = f"{sid}_{seed}" + ("_row" if "--row" in flags else "")
    json.dump(infos if len(infos) > 1 else infos[0], open(os.path.join(out, f"{tag}.json"), "w"), indent=1)
    print(f"House: {tag} tris {[i['tris'] for i in infos]} parts {sum(sum(i['parts'].values()) for i in infos)}")
    if "--blend" in flags:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"{tag}.blend"))
    if "--render" not in flags:
        return
    PV.render_setup(res=(1280, 720), samples=int(os.environ.get("HK_SAMPLES", "48")))
    L, D = h0.L, h0.D
    door = Vector((h0.door_u - L / 2, -D / 2, 1.2))
    views = []
    if "--row" in flags:
        views.append(("row40", (0.0, -D / 2 - 34.0, 1.6), (0.0, 0.0, 3.0), 35.0, "midday"))
    else:
        views += [("03m", (door.x + 1.2, -D / 2 - 3.0, 1.6), (door.x + 0.2, -D / 2, 1.5), 28.0, "midday"),
                  ("15m_midday", (L * 0.35, -D / 2 - 15.0, 1.6), (0.0, 0.0, 2.6), 35.0, "midday"),
                  ("15m_low", (L * 0.35, -D / 2 - 15.0, 1.6), (0.0, 0.0, 2.6), 35.0, "low"),
                  ("15m_overcast", (L * 0.35, -D / 2 - 15.0, 1.6), (0.0, 0.0, 2.6), 35.0, "overcast"),
                  ("15m_back", (-L * 0.30, D / 2 + 15.0, 1.6), (0.0, 0.0, 2.6), 35.0, "midday"),
                  ("60m", (L * 0.6, -D / 2 - 60.0, 1.6), (0.0, 0.0, 3.0), 50.0, "midday"),
                  ("40m_back", (-L * 0.5, D / 2 + 40.0, 2.0), (0.0, 0.0, 3.0), 35.0, "midday")]
    only = [v for v in os.environ.get("HK_ONLY", "").split(",") if v]
    for name, loc, tgt, lens, lt in views:
        if only and name not in only:
            continue
        for o in [o for o in bpy.context.scene.objects if o.type == "CAMERA"]:
            bpy.data.objects.remove(o, do_unlink=True)
        camera(loc, tgt, lens)
        PV.light(lt, yaw_deg=200.0 if "back" not in name else 20.0)
        bpy.context.scene.render.filepath = os.path.join(out, f"{tag}_{name}.jpg")
        bpy.ops.render.render(write_still=True)
        print(f"Render: {tag}_{name}.jpg")


if __name__ == "__main__":
    main()
