"""Shore loop slice 1 (docs/shore-loop/rocks.md): render the riprap rocks the way the game draws them, before or after.

    python Tools/shoreloop/rocks/render_rocks.py --out DIR [--rev main] [--scene bank|studio|close] [--tag new]

Run it with Python that has the `bpy` module (pip install bpy==5.1.2; numpy, Pillow). Each run:
  1. builds SM_Rock_<i> with build_props.py's own rock() at the revision (--rev: git show; none: the working tree) and
     reads the FBX back, so the render sees what Unreal imports (vertex colours included);
  2. lays them out: `bank` is a riprap face going into the lake (the breakwater's slope, sizes and tumble, from
     MarinaActor's breakwater), seen from a boat 3.5 m off at 1.5 m; `close` the same bank from 1.2 m; `studio` six
     stones high and dry on a grey floor;
  3. renders data passes in Cycles at one sample (world position, normal, box UVs, vertex colour, the UVs' tangent and
     bitangent, which rock) and the light on a white stone (sun and sky apart, 64 samples);
  4. runs M_WorldSurface's rock pattern (scripts/make_materials.py WORLD_SURFACE_CODE at the revision, through
     Tools/texloop/dock/hlsl_np.py: the shader's own text) on those passes for colour, roughness and the bump, tilts
     the sun's light by the bump, lays the lake (turbid, the sky in it by Fresnel) over everything under the pool, and
     tone maps.
Writes <out>/<tag>_<scene>.png and <tag>_<scene>.json (exposure, rock count, triangles).
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop", "dock"))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
import hlsl_np as H  # noqa: E402

import bpy  # noqa: E402

ENV = os.path.join(REPO, "Data", "Reference", "raw", "textures", "_env")
SKY = "kloofendal_48d_partly_cloudy_puresky"   # Poly Haven CC0: a clear Texas-like sky without its sun (the lamp is it)
ROCK_LOOK = ((0.52, 0.49, 0.43), 0.9, 4.25)      # MI_World_Rock (WORLD_LIBRARY): colour, roughness, pattern
OPEN = "else if (Pattern > 4.15 && Pattern < 4.5)"
WATER = np.array([0.045, 0.055, 0.04])            # Lake Ray Hubbard, turbid olive (the dock renderer's)
SUN_E = 30.0      # W/m2 in Cycles: about 3.5 times the sky's light on a level card, a clear Texas afternoon
SKY_CARD = 1.77   # the sky alone on a level white card (measured in the studio)
SUN_DIR = (math.radians(42), math.radians(60))    # elevation; azimuth from behind the camera round to its right


def source(rev, path):
    if rev:
        return subprocess.run(["git", "-C", REPO, "show", f"{rev}:{path}"], capture_output=True, text=True, check=True).stdout
    return open(os.path.join(REPO, path), encoding="utf-8").read()


def build_rocks(rev, indices, out_dir):
    """Run build_props.py's rock() at the revision into out_dir (FBX), without the vehicles."""
    src = source(rev, "Tools/blender/build_props.py")
    src = src[:src.index("bpy.ops.wm.read_factory_settings(use_empty=True)\nbpy.context.scene.unit_settings")]
    if rev:   # the revision's rock_kit too, if it has one
        try:
            kit = source(rev, "Tools/blender/rock_kit.py")
            kdir = tempfile.mkdtemp()
            open(os.path.join(kdir, "rock_kit.py"), "w").write(kit)
            path = os.path.join(kdir, "build_props.py")
        except subprocess.CalledProcessError:
            path = os.path.join(REPO, "Tools", "blender", "build_props.py")
    else:
        path = os.path.join(REPO, "Tools", "blender", "build_props.py")
    sys.modules.pop("rock_kit", None)
    argv = sys.argv
    sys.argv = ["build_props.py", "--", out_dir]
    ns = {"__file__": path, "__name__": "build_props_at_rev"}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    exec(compile(src, path, "exec"), ns)
    tris = {}
    for i in indices:
        ns["rock"](i)
    sys.argv = argv
    return tris


def import_rock(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward="X", axis_up="Z")
    obj = [o for o in bpy.data.objects if o not in before][0]
    me = obj.data
    # A second UV map with u and v swapped: its tangent is the first map's bitangent (the bump's v axis).
    uv0 = me.uv_layers[0]
    sw = me.uv_layers.new(name="UVsw")
    n = len(uv0.data)
    a = np.zeros(n * 2)
    uv0.data.foreach_get("uv", a)
    a = a.reshape(-1, 2)[:, ::-1].ravel()
    sw.data.foreach_set("uv", a)
    me.uv_layers.active = uv0
    for p in me.polygons:
        p.use_smooth = True
    return obj


def layout(scene, names, rng):
    """[(fbx name, location, rotation (rad), scale, custom data 15)] for the scene."""
    out = []
    if scene == "studio":
        for k, nm in enumerate(names[:6]):
            r, c = divmod(k, 3)
            out.append((nm, ((c - 1) * 2.4, 1.6 + r * 2.4, 3.0), (0.12, 0.08, 0.5 + 1.1 * k), 1.0, rng.random()))
        return out
    # The breakwater's face (MarinaActor): stones of 0.9 to 1.8 m tumbled on a 1:1.6 slope from 1.2 m under the pool to
    # its 1.6 m crest, a toe of bigger ones half drowned; the bank runs along x, rising toward +y.
    for row in range(9):
        y = 0.2 + row * 0.6
        zc = -1.0 + y / 1.6
        for k in range(15):
            x = -5.4 + k * 0.72 + rng.uniform(-0.25, 0.25) + (0.36 if row % 2 else 0.0)
            size = rng.uniform(0.9, 1.8) * (0.85 if row > 4 else 1.0)
            out.append((names[rng.randrange(len(names))], (x, y + rng.uniform(-0.2, 0.2), zc - 0.3 * size),
                        (rng.uniform(-0.44, 0.44), rng.uniform(-0.44, 0.44), rng.uniform(0, 6.28)), size * 0.62, rng.random()))
    for k in range(7):
        size = rng.uniform(1.4, 2.2)
        out.append((names[rng.randrange(len(names))], (-4.6 + k * 1.5 + rng.uniform(-0.3, 0.3), -0.6, -0.35 * size),
                    (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, 6.28)), size * 0.62, rng.random()))
    return out


def camera_for(scene):
    if scene == "studio":
        return (0.0, -4.4, 6.4), (math.radians(65), 0.0, 0.0), 32
    if scene == "close":
        return (0.6, -1.7, 1.25), (math.radians(78), 0.0, math.radians(-8)), 30
    return (0.0, -4.1, 1.5), (math.radians(80), 0.0, 0.0), 32


def materials():
    """One material: a white diffuse stone for the light, and the data it emits (by the `Mode` value on the node tree)."""
    m = bpy.data.materials.new("RockData")
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    col = nt.nodes.new("ShaderNodeVertexColor")
    tan = nt.nodes.new("ShaderNodeTangent")
    tan.direction_type = "UV_MAP"
    tan.uv_map = "UVMap"
    tsw = nt.nodes.new("ShaderNodeTangent")
    tsw.direction_type = "UV_MAP"
    tsw.uv_map = "UVsw"
    info = nt.nodes.new("ShaderNodeObjectInfo")
    emit = nt.nodes.new("ShaderNodeEmission")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diff.inputs["Color"].default_value = (1, 1, 1, 1)
    return m, dict(out=out, geo=geo, uv=uvn, col=col, tan=tan, tsw=tsw, info=info, emit=emit, diff=diff, nt=nt)


def set_mode(N, mode):
    nt = N["nt"]
    for l in list(N["out"].inputs["Surface"].links):
        nt.links.remove(l)
    for l in list(N["emit"].inputs["Color"].links):
        nt.links.remove(l)
    if mode == "light":
        nt.links.new(N["diff"].outputs[0], N["out"].inputs["Surface"])
        return
    src = {"pos": N["geo"].outputs["Position"], "nrm": N["geo"].outputs["Normal"], "uv": N["uv"].outputs["UV"],
           "vc": N["col"].outputs["Color"], "tan": N["tan"].outputs["Tangent"], "tsw": N["tsw"].outputs["Tangent"],
           "idx": N["info"].outputs["Object Index"]}[mode]
    # Cycles clamps negative emission: positions and UVs ride +100, directions * 0.5 + 0.5 (decode() undoes it).
    vm = N.get("vm")
    if vm is None:
        vm = N["vm"] = nt.nodes.new("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY_ADD"
    k = ENCODE[mode]
    vm.inputs[1].default_value = (k[0],) * 3
    vm.inputs[2].default_value = (k[1],) * 3
    for l in list(vm.inputs[0].links):
        nt.links.remove(l)
    nt.links.new(src, vm.inputs[0])
    nt.links.new(vm.outputs[0], N["emit"].inputs["Color"])
    nt.links.new(N["emit"].outputs[0], N["out"].inputs["Surface"])


ENCODE = {"pos": (1.0, 100.0), "uv": (1.0, 100.0), "nrm": (0.5, 0.5), "tan": (0.5, 0.5), "tsw": (0.5, 0.5),
          "vc": (1.0, 0.0), "idx": (1.0, 0.0)}


def decode(mode, a):
    k = ENCODE[mode]
    out = a.copy()
    out[..., :3] = (a[..., :3] - k[1]) / k[0]
    return out


def render_pass(path, samples, w, h):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    a = np.zeros(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1]


def load_sky():
    p = os.path.join(ENV, SKY + "_1k.hdr")
    if not os.path.exists(p):
        import urllib.request
        os.makedirs(ENV, exist_ok=True)
        urllib.request.urlretrieve("https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/%s_1k.hdr" % SKY, p)
    return p


def surface(code, P, Nrm, UV, VC, idx, cds, wetM=0.6):
    """The rock pattern on the passes: colour, roughness, tangent-space bump."""
    col, rough, pat = ROCK_LOOK
    h, w = UV.shape[:2]
    one = np.ones((h, w, 1))
    uv = UV[..., :2]
    wp = P[..., :3] * 100.0
    cd15 = cds[np.clip(np.rint(idx).astype(int), 0, len(cds) - 1)][..., None]
    pp = uv * 0.7
    i0 = np.floor(pp)
    f0 = H.smoothstep(0.0, 1.0, pp - i0)
    hh = lambda o: H.frac(np.sin((i0 + o) @ np.array([12.99, 78.23]))[..., None] * 43758.5)
    blot = H.lerp(H.lerp(hh((0, 0)), hh((1, 0)), f0[..., :1]), H.lerp(hh((0, 1)), hh((1, 1)), f0[..., :1]), f0[..., 1:])
    nn = H.frac(np.sin(np.floor(uv * 7.0) @ np.array([12.9898, 78.233]))[..., None] * 43758.5453)
    env = dict(uv=uv, WP=wp, UV1=uv, Color=np.array(col), Rough=rough, c=np.array(col) * one, r=rough * one,
               Pattern=pat, n=nn, blot=blot, bump=np.zeros((h, w, 3)), age=12.0, care=0.4, sun=0.6, wetM=wetM, site=0.0,
               salt=0.0, aged=0.48, zw=wp[..., 2:3] * 0.01, variant=cd15 * 8.0, Metal=0.0, Met=0.0, Windows=0.0,
               seeded=True, CD10=12.0 * one, CD15=cd15, wh2=0.5 * one, VC=VC[..., :3], dkT=0.5, dkD=0.4)
    ns = H.run(H.branch(code, OPEN), env)
    return ns["c"], ns["r"][..., 0], ns["bump"]


def compose(scene, passes, code, cam_loc, cam_rot, lens, w, h, cds, sun_vec, card):
    P, Nrm, UV, VC, T, B, I, sun, sky = (passes[k] for k in ("pos", "nrm", "uv", "vc", "tan", "tsw", "idx", "sun", "sky"))
    hit = P[..., 3] > 0.5
    c, r, bump = surface(code, P, Nrm, UV, VC, I[..., 0], cds)
    floor = (np.rint(I[..., 0]) == 0)[..., None]          # the studio's floor: an 18% grey card; the bank's core: clay
    c = np.where(floor, np.array([0.18, 0.18, 0.18]) if scene == "studio" else np.array([0.16, 0.13, 0.09]), c)
    r = np.where(floor[..., 0], 0.9, r)
    bump = np.where(floor, 0.0, bump)
    n = Nrm[..., :3]
    n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    t = T[..., :3] - n * np.sum(T[..., :3] * n, -1, keepdims=True)
    t /= np.maximum(np.linalg.norm(t, axis=-1, keepdims=True), 1e-6)
    b = B[..., :3] - n * np.sum(B[..., :3] * n, -1, keepdims=True)
    b /= np.maximum(np.linalg.norm(b, axis=-1, keepdims=True), 1e-6)
    n2 = n - bump[..., :1] * t - bump[..., 1:2] * b
    n2 /= np.maximum(np.linalg.norm(n2, axis=-1, keepdims=True), 1e-6)
    L = np.array(sun_vec)
    k0 = np.maximum(n @ L, 0.0)[..., None]
    k1 = np.maximum(n2 @ L, 0.0)[..., None]
    sunk = np.where(k0 > 0.05, np.clip(k1 / np.maximum(k0, 1e-3), 0.0, 3.0), 1.0)
    light = sun[..., :3] * sunk + sky[..., :3]
    # Roughness: a small sheen where the stone is wet or slick (the engine's spec, roughly: 4% at grazing, wider when rough).
    img = c * light + (0.04 * (1.0 - r) ** 2)[..., None] * sky[..., :3] * 0.6
    img = np.where(hit[..., None], img, 0.0)
    # The lake over everything under the pool, and the open water beyond.
    ray = view_rays(cam_loc, cam_rot, lens, w, h)
    eye = np.array(cam_loc)
    tw = np.where(ray[..., 2] < -1e-4, -eye[2] / np.minimum(ray[..., 2], -1e-4), np.inf)
    dist = np.where(hit, np.linalg.norm(P[..., :3] - eye, axis=-1), np.inf)
    under = (tw < dist) & np.isfinite(tw)
    depth = np.where(under, np.where(np.isfinite(dist), dist - tw, 50.0), 0.0)
    cosv = np.clip(-ray[..., 2], 0.0, 1.0)
    fres = 0.02 + 0.98 * (1.0 - cosv) ** 5
    lit = card / 2.45                                      # the sky and water colours below were set at a 2.45 card
    skyc = np.array([0.55, 0.66, 0.85]) * 1.2 * lit
    wcol = WATER * 1.6 * lit
    a = (1.0 - np.exp(-depth / 0.12))[..., None]          # Secchi depth about half a metre
    img = np.where(under[..., None], img * (1 - a) + wcol * a, img)
    img = np.where(under[..., None], img * (1 - fres[..., None]) + skyc * fres[..., None], img)
    above = ~under & ~hit
    horizon = np.clip(ray[..., 2] * 4.0, 0.0, 1.0)[..., None]
    img = np.where(above[..., None], (np.array([0.75, 0.80, 0.86]) * (1 - horizon) + np.array([0.42, 0.55, 0.80]) * horizon) * lit, img)
    return img


def view_rays(loc, rot, lens, w, h):
    sensor = 36.0
    f = lens / sensor * w
    x = np.arange(w) + 0.5 - w / 2
    y = np.arange(h) + 0.5 - h / 2
    X, Y = np.meshgrid(x, y)
    d = np.stack([X, -Y, -np.full_like(X, f)], -1)   # camera space: -Z forward, +Y up
    rx, ry, rz = rot
    Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    d = d @ (Rz @ Ry @ Rx).T
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def tonemap(img, exposure):
    x = img * exposure
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    y = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)
    return np.where(y <= 0.0031308, 12.92 * y, 1.055 * np.power(y, 1 / 2.4) - 0.055)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--rev", default=None)
    ap.add_argument("--scene", default="bank", choices=["bank", "studio", "close"])
    ap.add_argument("--tag", default="new")
    ap.add_argument("--size", default="1280x800")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--exposure", type=float, default=None)   # default: metered (a level white card at 0.93)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    os.makedirs(a.out, exist_ok=True)
    tmp = tempfile.mkdtemp()
    indices = list(range(12))
    build_rocks(a.rev, indices, tmp)
    code = H.world_code(a.rev)

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
    names = [f"SM_Rock_{i}" for i in indices]
    protos = {nm: import_rock(os.path.join(tmp, nm + ".fbx")) for nm in names}
    tris = {nm: sum(len(p.vertices) - 2 for p in o.data.polygons) for nm, o in protos.items()}
    mat, N = materials()
    rng = __import__("random").Random(7)
    lay = layout(a.scene, names, rng)
    cds = np.array([0.0] + [e[4] for e in lay])
    for k, (nm, loc, rot, s, _) in enumerate(lay):
        o = bpy.data.objects.new(f"inst{k}", protos[nm].data)
        o.location, o.rotation_euler, o.scale = loc, rot, (s, s, s)
        o.pass_index = k + 1
        o.data.materials.clear()
        o.data.materials.append(mat)
        sc.collection.objects.link(o)
    for o in protos.values():
        bpy.data.objects.remove(o)
    if a.scene == "studio":
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 2.62))
    else:   # the bank under the stones: the breakwater's core, 1:1.6
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 2.6, -1.0 + 2.6 / 1.6 - 0.35))
        bpy.context.object.scale = (30, 7.0, 1)
        bpy.context.object.rotation_euler = (math.atan(1 / 1.6), 0, 0)
    fl = bpy.context.object
    fl.data.materials.append(mat)
    fl.pass_index = 0
    cl, cr, lens = camera_for(a.scene)
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    cam.sensor_fit = "HORIZONTAL"
    co = bpy.data.objects.new("cam", cam)
    co.location, co.rotation_euler = cl, cr
    sc.collection.objects.link(co)
    sc.camera = co
    el, az = SUN_DIR
    sun_vec = (math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el))   # toward the sun
    sun_vec = tuple(np.array(sun_vec) / np.linalg.norm(sun_vec))
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    envn = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    envn.image = bpy.data.images.load(load_sky())
    world.node_tree.links.new(envn.outputs["Color"], bg.inputs["Color"])
    lamp = bpy.data.lights.new("sun", "SUN")
    lamp.energy = SUN_E
    lamp.angle = math.radians(0.6)
    lo = bpy.data.objects.new("sun", lamp)
    d = np.array(sun_vec)
    lo.rotation_euler = (math.acos(d[2]), 0.0, math.atan2(d[1], d[0]) + math.pi / 2)
    sc.collection.objects.link(lo)
    passes = {}
    sc.cycles.filter_width = 0.01
    bg.inputs["Strength"].default_value = 0.0
    lo.hide_render = True
    for mode in ("pos", "nrm", "uv", "vc", "tan", "tsw", "idx"):
        set_mode(N, mode)
        passes[mode] = decode(mode, render_pass(os.path.join(tmp, mode + ".exr"), 1, w, h))
    sc.cycles.filter_width = 1.5
    sc.cycles.use_denoising = True    # the light passes only (OpenImageDenoise): the data passes must stay exact
    set_mode(N, "light")
    lo.hide_render = False
    passes["sun"] = render_pass(os.path.join(tmp, "sun.exr"), a.samples, w, h)
    lo.hide_render = True
    bg.inputs["Strength"].default_value = 1.0
    passes["sky"] = render_pass(os.path.join(tmp, "sky.exr"), a.samples, w, h)
    if os.environ.get("ROCKS_DUMP"):
        np.savez_compressed(os.environ["ROCKS_DUMP"], cds=cds, **passes)
    card = SKY_CARD + SUN_E * math.sin(el) / math.pi       # a level white card's light
    img = compose(a.scene, passes, code, cl, cr, lens, w, h, cds, sun_vec, card)
    if a.scene == "studio":   # meter: a level white card's light (median over the floor in the open)
        fl_px = (np.rint(passes["idx"][..., 0]) == 0) & (passes["pos"][..., 3] > 0.5)
        lt = (passes["sun"][..., :3] + passes["sky"][..., :3]).mean(-1)
        print("meter: level white card", float(np.percentile(lt[fl_px], 90)))
    if a.exposure is None:
        a.exposure = 0.93 / card
    out = tonemap(img, a.exposure)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(os.path.join(a.out, f"{a.tag}_{a.scene}.png"))
    json.dump({"rev": a.rev or "working tree", "scene": a.scene, "stones": len(lay), "triangles": tris,
               "exposure": a.exposure, "sun_dir": sun_vec}, open(os.path.join(a.out, f"{a.tag}_{a.scene}.json"), "w"), indent=1)
    print("wrote", os.path.join(a.out, f"{a.tag}_{a.scene}.png"))


if __name__ == "__main__":
    main()
