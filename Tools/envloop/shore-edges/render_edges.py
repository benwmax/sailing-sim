"""Shore edge kit renders (shore plan Track C, docs/envloop/shore-edges/): the environment loop's standard renders.

    python Tools/envloop/shore-edges/render_edges.py --out DIR [--pack north-texas-lake] [--types bulkhead,ramp] [--size 640x320] [--samples 16]

Python with the `bpy` module (pip install bpy==5.1.2), numpy and Pillow. For each type it builds the kit
(edge_kit.py) long enough for the view, and from a boat 1.5 m over the water at 3 m, 15 m and 60 m off the water's
edge renders, in Cycles, the data passes (position, normal, metre UVs, vertex colour: one sample, twice the size) and
the light on white (the sun high, the sun low, the clear sky, an overcast sky). The look is then edge_layer.py's
HLSL run on those passes through Tools/texloop/dock/hlsl_np.py, lit, the lake laid over everything under the water
(turbid, the sky in it by Fresnel), tone mapped and halved. Four lights a distance: midday at the pool, low sun at the
pool, overcast at the pool, and midday with the lake a metre down (the October 2026 gauge), which bares the stain band.

Writes <out>/<type>/<dist>m_<light>.png, a sheet per type (<out>/<type>_sheet.png: rows 3, 15, 60 m; columns the
four lights), a contact sheet of every type at 15 m midday (<out>/all_15m.png) and <out>/<type>/measures.json
(triangles, sizes as built, the repeat score per view) for check_edges.py.

The lighting and the water are render_rocks.py's (Tools/shoreloop/rocks/), imported, so both loops light alike.
"""
import argparse
import json
import math
import os
import sys
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path[:0] = [HERE, os.path.join(REPO, "Tools", "shoreloop", "rocks"), os.path.join(REPO, "Tools", "texloop", "dock")]
import bpy  # noqa: E402
import hlsl_np as H  # noqa: E402
import render_rocks as RR  # noqa: E402
import edge_kit as K  # noqa: E402
import edge_layer as L  # noqa: E402
from rock_kit import perlin  # noqa: E402

DISTS = (3, 15, 60)
LOOK_DOWN = {"sheetpile": -0.55, "bulkhead": -0.2}   # metres off the 3 m view's aim, per type
LENGTH = {3: 16.0, 15: 40.0, 60: 100.0}
LENS = {3: 24.0, 15: 50.0, 60: 54.0}           # mm on a 36 mm sensor: 74, 40 and 37 degrees; at 60 m the frame is the plan's 40 m repeat check
LIGHTS = [("midday", "pool"), ("lowsun", "pool"), ("overcast", "pool"), ("midday-low-lake", "gauge")]
SUN_MID = (math.radians(68), math.radians(35))
SUN_LOW = (math.radians(11), math.radians(70))    # raking along the shore from the right and a little in front, late afternoon
LOW_TINT = np.array([1.0, 0.80, 0.58]) * 0.75
OVERCAST = 1.6                                   # uniform sky radiance; a level white card reads the same
WATER = RR.WATER


def edge_y(kind, level):
    """Where the water meets the shore at x = 0 (y), for the camera; walls stand at 0 whatever the level."""
    if kind in ("bulkhead", "sheetpile", "limestone", "timber"):
        return 0.0
    if kind == "claycut":
        return float(np.interp(level, [-0.9, -0.35, -0.08, 0.04], [-4.0, -2.2, -1.0, -0.3]))
    if kind == "mudflat":
        return (level + 0.45) / K.SIZE["mud_slope"] - 15.0
    if kind == "gravel":
        return level / K.SIZE["beach_slope"] if level > -0.3 else -3.0 + (level + 0.3) / 0.2
    if kind == "reedcove":
        return 6.0 + level * 15.0
    if kind == "ramp":
        return 6.0 - (0.9 - level) / K.SIZE["ramp_slope"]
    raise KeyError(kind)


def to_blender(m, name="edge"):
    V, F, C, S = m.arrays()
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.polygons.foreach_set("use_smooth", S)
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.concatenate([C, np.ones((len(C), 1))], 1).astype(np.float32).ravel())
    # Metre UVs by the triangle's main axis: walls (x, z), ground (x, y), side faces (y, z).
    P = V[F]                                                   # (T, 3, 3)
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    ax = np.argmax(np.abs(n), 1)
    uv = np.where((ax == 2)[:, None, None], P[..., [0, 1]], np.where((ax == 1)[:, None, None], P[..., [0, 2]], P[..., [1, 2]]))
    for nm in ("UVMap", "UVsw"):
        lay = me.uv_layers.new(name=nm)
        lay.data.foreach_set("uv", (uv if nm == "UVMap" else uv[..., ::-1]).astype(np.float32).ravel())
    me.uv_layers.active = me.uv_layers["UVMap"]
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def grad_noise(P, scale, seed, foot):
    """Gradient (Perlin) noise in 0..1 at points P (H, W, 3) metres, cells `scale` metres, two octaves so no cell shows
    as a square (round 1's value noise did); histogram-equalised, then flattened toward 0.5 where a pixel covers more
    than a cell (what the game's mipped noise texture does)."""
    q = P.reshape(-1, 3) / np.asarray(scale, float)
    out = perlin(q, seed) + 0.45 * perlin(q * 2.03 + 11.7, seed + 31)
    # Equalise to a uniform 0..1 (the game's noise texture is authored equalised): thresholds then mean what they say.
    rank = np.empty(len(out))
    rank[np.argsort(out, kind="stable")] = (np.arange(len(out)) + 0.5) / len(out)
    out = rank.reshape(P.shape[:-1] + (1,))
    s = float(np.min(scale))
    amp = np.clip(s / (2.0 * np.maximum(foot, 1e-6)) - 0.5, 0.0, 1.0)
    return 0.5 + (out - 0.5) * amp


value_noise = grad_noise   # round 1's name, kept for callers


def shade(passes, level, eye, px_angle, pack):
    P, Nrm, UV, VC = (passes[k] for k in ("pos", "nrm", "uv", "vc"))
    h, w = P.shape[:2]
    hit = P[..., 3:4] > 0.5
    wp = np.where(hit, P[..., :3], 0.0)
    dist = np.linalg.norm(wp - eye, axis=-1, keepdims=True)
    foot = dist * px_angle
    env = dict(uv=UV[..., :2], WP=wp, Nw=Nrm[..., :3], VC=VC[..., :3], UVm=UV[..., :2],
               n003=value_noise(wp, 0.03, 3, foot), n01=value_noise(wp, 0.10, 5, foot), n05=value_noise(wp, 0.5, 7, foot),
               n2=value_noise(wp, 2.0, 9, foot), ns=value_noise(wp, np.array([0.04, 0.04, 0.7]), 13, foot), **L.values(pack, level))
    ns = H.run(L.EDGE_LAYER_CODE, env)
    return ns["c"], ns["r"], ns["wet"]


def compose(c, r, passes, light, wz, cam, rays):
    P = passes["pos"]
    hit = P[..., 3] > 0.5
    Nrm = passes["nrm"][..., :3]
    if light == "overcast":
        lit = passes["ovc"][..., :3]
        skyc = np.array([0.80, 0.82, 0.86]) * OVERCAST
        card = OVERCAST
    elif light == "lowsun":
        lit = passes["sunlow"][..., :3] * LOW_TINT + passes["sky"][..., :3] * 0.6
        skyc = np.array([0.62, 0.68, 0.82]) * 1.2 * 0.6 * RR.SKY_CARD / 2.45 * 2.45
        card = 0.6 * RR.SKY_CARD + 0.75 * RR.SUN_E * 0.5 / math.pi
    else:
        lit = passes["sun"][..., :3] + passes["sky"][..., :3]
        card = RR.SKY_CARD + RR.SUN_E * math.sin(SUN_MID[0]) / math.pi
        skyc = np.array([0.55, 0.66, 0.85]) * 1.2 * card / 2.45
    img = c * lit
    # A sky sheen on smooth and wet surfaces, by Fresnel at the view angle.
    cosv = np.clip(-np.sum(rays * Nrm, -1, keepdims=True), 0.0, 1.0)
    fres = 0.02 + 0.98 * (1.0 - cosv) ** 5
    img = img + fres * (1.0 - r) ** 2 * skyc * 0.8
    img = np.where(hit[..., None], img, 0.0)
    # The lake: everything under the water level, and the open water beyond the built shore.
    eye = np.array(cam)
    tw = np.where(rays[..., 2] < -1e-4, (wz - eye[2]) / np.minimum(rays[..., 2], -1e-4), np.inf)
    dist = np.where(hit, np.linalg.norm(P[..., :3] - eye, axis=-1), np.inf)
    under = (tw < dist) & np.isfinite(tw)
    cosw = np.clip(-rays[..., 2], 0.0, 1.0)
    depth = np.where(under, np.where(np.isfinite(dist), dist - np.where(np.isfinite(tw), tw, 0.0), 50.0), 0.0)   # the ray's path in the water
    fresw = (0.02 + 0.98 * (1.0 - cosw) ** 5)[..., None]
    wcol = WATER * 1.6 * card / 2.45
    a = (1.0 - np.exp(-depth / 0.12))[..., None]
    img = np.where(under[..., None], img * (1 - a) + wcol * a, img)
    img = np.where(under[..., None], img * (1 - fresw) + skyc * fresw, img)
    above = ~under & ~hit
    horizon = np.clip(rays[..., 2] * 4.0, 0.0, 1.0)[..., None]
    sky = (np.array([0.75, 0.80, 0.86]) * (1 - horizon) + np.array([0.42, 0.55, 0.80]) * horizon) * card / 2.45
    if light == "overcast":
        sky = np.array([0.82, 0.83, 0.85]) * card / 1.6 * 0.9 + 0 * horizon
    img = np.where(above[..., None], sky, img)
    return RR.tonemap(img, 0.93 / card)


def camera(kind, dist, wz):
    ye = edge_y(kind, wz)
    eye = (0.0, ye - dist, wz + 1.5)
    tz = {3: 0.35, 15: 0.55, 60: 0.9}[dist] + wz
    if dist == 3:
        # The hold station looks a little down at a wall whose cap and waler hide the face from eye height.
        tz += LOOK_DOWN.get(kind, 0.0)
    tgt = np.array([0.0, ye + (0.8 if dist == 3 else 1.5), tz])
    d = tgt - np.array(eye)
    d /= np.linalg.norm(d)
    rx = math.atan2(math.hypot(d[0], d[1]), -d[2])
    rz = math.atan2(d[1], d[0]) - math.pi / 2
    return eye, (rx, 0.0, rz)


def repeat_score(img):
    """How strongly the frame repeats sideways: the highest normalised autocorrelation of the columns' mean brightness
    (in the band where the shore is) at a shift between 5 and 50 percent of the width. Near 1 is a visible tile."""
    g = np.asarray(img, float).mean(-1)
    h = g.shape[0]
    band = g[int(h * 0.3):int(h * 0.75)]
    prof = band - band.mean(1, keepdims=True)
    prof = prof.mean(0)
    prof = prof - np.linspace(prof[0], prof[-1], len(prof))      # remove the light's slow trend across the frame
    prof = prof - prof.mean()
    n = len(prof)
    den = np.dot(prof, prof) + 1e-9
    best = 0.0
    for s in range(int(0.05 * n), int(0.5 * n)):
        best = max(best, float(np.dot(prof[:-s], prof[s:]) / den * n / (n - s)))
    return best


def setup_scene(w, h):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.image_settings.color_depth = "32"
    sc.view_settings.view_transform = "Standard"
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 3
    return sc


def sun_lamp(sc, el_az):
    el, az = el_az
    v = np.array((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
    v /= np.linalg.norm(v)
    lamp = bpy.data.lights.new("sun", "SUN")
    lamp.energy = RR.SUN_E
    lamp.angle = math.radians(0.6)
    lo = bpy.data.objects.new("sun", lamp)
    lo.rotation_euler = (math.acos(v[2]), 0.0, math.atan2(v[1], v[0]) + math.pi / 2)
    sc.collection.objects.link(lo)
    return lo


def render_type(kind, out, w, h, samples, seed, pack):
    os.makedirs(os.path.join(out, kind), exist_ok=True)
    tmp = tempfile.mkdtemp()
    report = dict(kind=kind, views={})
    for dist in DISTS:
        m, meas = K.build(kind, LENGTH[dist], seed, pack)
        report.setdefault("measures", meas)
        if dist == 3:
            report["triangles_16m"] = m.piece_triangles
            report["triangles_16m_with_ground"] = m.triangles
            report["triangles_by_part"] = dict(m.part_tris)
        sc = setup_scene(2 * w, 2 * h)
        obj = to_blender(m)
        mat, N = RR.materials()
        N["col"].layer_name = "Col"
        obj.data.materials.append(mat)
        world = bpy.data.worlds.new("W")
        sc.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        envn = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
        envn.image = bpy.data.images.load(RR.load_sky())
        mid, low = sun_lamp(sc, SUN_MID), sun_lamp(sc, SUN_LOW)
        cam = bpy.data.cameras.new("cam")
        cam.lens = LENS[dist]
        cam.sensor_fit = "HORIZONTAL"
        cam.clip_end = 2000.0
        co = bpy.data.objects.new("cam", cam)
        sc.collection.objects.link(co)
        sc.camera = co
        tiles = {}
        for level in ("pool", "gauge"):
            eye, rot = camera(kind, dist, pack["levels"][level])
            co.location, co.rotation_euler = eye, rot
            passes = {}
            sc.cycles.filter_width = 0.01
            sc.cycles.use_denoising = False
            bg.inputs["Strength"].default_value = 0.0
            mid.hide_render = low.hide_render = True
            for mode in ("pos", "nrm", "uv", "vc"):
                RR.set_mode(N, mode)
                passes[mode] = RR.decode(mode, RR.render_pass(os.path.join(tmp, mode + ".exr"), 1, 2 * w, 2 * h))
            sc.cycles.filter_width = 1.5
            sc.cycles.use_denoising = True
            RR.set_mode(N, "light")
            want = [("sun", mid, None)] if level == "gauge" else [("sun", mid, None), ("sunlow", low, None), ("sky", None, "hdri"), ("ovc", None, "flat")]
            if level == "gauge":
                want.append(("sky", None, "hdri"))
            for key, lamp, sky in want:
                mid.hide_render = low.hide_render = True
                bg.inputs["Strength"].default_value = 0.0
                if lamp is not None:
                    lamp.hide_render = False
                for lk in list(bg.inputs["Color"].links):
                    world.node_tree.links.remove(lk)
                if sky == "hdri":
                    world.node_tree.links.new(envn.outputs["Color"], bg.inputs["Color"])
                    bg.inputs["Strength"].default_value = 1.0
                elif sky == "flat":
                    bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
                    bg.inputs["Strength"].default_value = OVERCAST
                passes[key] = RR.render_pass(os.path.join(tmp, key + ".exr"), samples, 2 * w, 2 * h)
            rays = RR.view_rays(eye, rot, LENS[dist], 2 * w, 2 * h)
            px = 36.0 / (LENS[dist] * 2 * w)
            c, r, wet = shade(passes, level, np.array(eye), px, pack)
            for light, lev in LIGHTS:
                if lev != level:
                    continue
                img = compose(c, r, passes, light.split("-")[0], pack["levels"][level], eye, rays)
                img = img.reshape(h, 2, w, 2, 3).mean((1, 3))
                im = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
                im.save(os.path.join(out, kind, f"{dist}m_{light}.png"))
                tiles[light] = im
                report["views"][f"{dist}m_{light}"] = dict(repeat=round(repeat_score(im), 3))
        report.setdefault("tiles", {})[dist] = tiles
        print(f"  {kind} {dist} m done", flush=True)
    tiles = report.pop("tiles")
    sheet(tiles, os.path.join(out, f"{kind}_sheet.png"), kind, w, h)
    json.dump(report, open(os.path.join(out, kind, "measures.json"), "w"), indent=1, default=float)
    return tiles


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 8 + 7 * len(text), 18], fill=(0, 0, 0))
    d.text((4, 3), text, fill=(255, 255, 255))
    return im


def sheet(tiles, path, kind, w, h):
    cols = [l for l, _ in LIGHTS]
    S = Image.new("RGB", (w * len(cols), h * len(DISTS) + 24), (20, 20, 20))
    ImageDraw.Draw(S).text((6, 6), f"{kind}: rows 3 m, 15 m, 60 m off the water's edge; columns " + ", ".join(cols), fill=(255, 255, 255))
    for i, dist in enumerate(DISTS):
        for j, light in enumerate(cols):
            if light in tiles[dist]:
                S.paste(label(tiles[dist][light].copy(), f"{kind} {dist} m {light}"), (j * w, 24 + i * h))
    S.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--types", default=None, help="default: every type the pack has that the kit builds")
    ap.add_argument("--size", default="640x320")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--pack", default=K.DEFAULT_PACK, help="region pack: packs/<name>/pack.json")
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    os.makedirs(a.out, exist_ok=True)
    pack = K.load_pack(a.pack)
    allt = {}
    kinds = a.types.split(",") if a.types else [k for k in pack["types"] if k in K.BUILDERS]
    for kind in kinds:
        t0 = time.time()
        allt[kind] = render_type(kind, a.out, w, h, a.samples, a.seed, pack)
        print(f"{kind}: {time.time() - t0:.0f} s", flush=True)
    kinds = list(allt)
    ncol = 3
    rows = (len(kinds) + ncol - 1) // ncol
    S = Image.new("RGB", (w * ncol, h * rows), (20, 20, 20))
    for k, kind in enumerate(kinds):
        S.paste(label(allt[kind][15]["midday"].copy(), f"{kind} 15 m midday"), ((k % ncol) * w, (k // ncol) * h))
    S.save(os.path.join(a.out, "all_15m.png"))


if __name__ == "__main__":
    main()
