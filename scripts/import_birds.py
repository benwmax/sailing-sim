"""Wildlife Phase 1 (docs/wildlife-1/README.md): the distant birds' materials and bodies in /Game/Wildlife/Birds. Run by
scripts/make-birds.sh after scripts/make-content.sh; it imports the bodies Tools/blender/build_birds.py exported
(Artifacts/models/birds, or the folder given last). Edit this script, never the assets.

  M_BirdFar  far birds (400 m to 2 km, and every bird until the bodies exist): the engine's 1 m plane turned to the camera
             by AWildlifeActor::FarQuad (x along the bird's span as seen, y up), its silhouette drawn here from the wingbeat.
             Masked, the cover dithered (temporal AA resolves it). Per-instance data (AWildlifeActor::FarFloats = 12):
             0 wing phase (0..1), 1 wing amplitude (0 glide .. 1 full beat), 2 fold (0 open .. 1 folded), 3 cover (fade x
             the share of a sub-MinPixels bird), 4 wingtip darkness, 5-7 colour (linear, the side the camera sees),
             8 below (1 the camera sees the underside), 9 dihedral (rad), 10 crank (rad, the gull's M), 11 span seen (0.25..1).
  M_BirdMid  mid and near birds (under 400 m): SM_Bird_<Style>, wings beating about the shoulder and folding along the
             back in the vertex shader, a wader's legs swinging down to stand. Per-instance data (MidFloats = 11): 0 phase,
             1 amplitude, 2 fold, 3 fade, 4-6 upper colour, 7-9 under colour, 10 wingtip darkness. Mesh attributes as
             build_birds.py writes them (UV0.u wing weight, UV0.v lift, UV1 hip, colour G legs; V flipped by the import).
Prints "Birds: ..." lines; make-birds.sh checks for "Birds: done".
"""
import glob
import os
import sys

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[-1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) else os.path.join(REPO, "Artifacts", "models", "birds")
FOLDER = "/Game/Wildlife/Birds"
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
LIB = unreal.EditorAssetLibrary
F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3


def node(mat, cls, x, y, **props):
    n = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def scalar(mat, name, default, x, y):
    return node(mat, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=default)


def custom(mat, code, inputs, output_type, x, y, extra_outputs=()):
    c = node(mat, unreal.MaterialExpressionCustom, x, y, code=code, output_type=output_type)
    ins = []
    for n in inputs:
        i = unreal.CustomInput()
        i.set_editor_property("input_name", n)
        ins.append(i)
    c.set_editor_property("inputs", ins)
    outs = []
    for n, kind in extra_outputs:
        o = unreal.CustomOutput()
        o.set_editor_property("output_name", n)
        o.set_editor_property("output_type", kind)
        outs.append(o)
    if outs:
        c.set_editor_property("additional_outputs", outs)
    return c


def connect(a, a_out, b, b_in):
    if not MEL.connect_material_expressions(a, a_out, b, b_in):
        raise RuntimeError(f"connect failed: {a.get_name()}.{a_out} -> {b.get_name()}.{b_in}")


def wire(mat, code, inputs, output_type, x, y, extra_outputs=()):
    c = custom(mat, code, list(inputs.keys()), output_type, x, y, extra_outputs)
    for name, n in inputs.items():
        connect(n, "", c, name)
    return c


def instance_data(mat, names, x, y, first=0):
    return {n: node(mat, unreal.MaterialExpressionPerInstanceCustomData, x, y + 70 * k, data_index=first + k)
            for k, n in enumerate(names)}


def new_material(name):
    path = f"{FOLDER}/{name}"
    if LIB.does_asset_exist(path):
        # Rebuilt in place (AWildlifeActor loads them by path; the bodies reference M_BirdMid and are re-set below).
        LIB.delete_asset(path)
    return ASSETS.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())


def dither(mat, alpha, x, y):
    d = node(mat, unreal.MaterialExpressionMaterialFunctionCall, x, y)
    d.set_editor_property("material_function", unreal.load_asset("/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA"))
    connect(alpha, "", d, "Alpha Threshold")
    return d


FAR_CODE = r"""
// docs/wildlife-1: a far bird on the engine's 1 m plane, turned to the camera by AWildlifeActor::FarQuad (x along the
// span as seen, y up). A small body and two wings bent at the wrist, held at the style's dihedral and crank, beating
// about the shoulder, drawn in by Fold; tips darkened by Tips. Returns the coverage (Cover: fades and the share of a bird
// under two pixels); Col the colour.
float2 p = Local.xy / 50.0;
p.x = abs(p.x);
float beat = Amp * 0.8 * sin(6.2831853 * Phase);
float a = Dihedral + beat;
float h = 0.97 * (1.0 - 0.65 * Fold);
float ai = a + 0.6 * Crank, ao = a - Crank;
float2 s = float2(0.07, 0.0);
float2 w = s + 0.44 * h * float2(cos(ai), sin(ai));
float2 t = w + 0.56 * h * float2(cos(ao), sin(ao));
float2 pa = p - s, ba = w - s;
float u1 = saturate(dot(pa, ba) / max(dot(ba, ba), 1e-4));
float d1 = length(pa - ba * u1) - lerp(0.11, 0.085, u1);
float2 pb = p - w, bb = t - w;
float u2 = saturate(dot(pb, bb) / max(dot(bb, bb), 1e-4));
float d2 = length(pb - bb * u2) - lerp(0.085, 0.02, u2);
// (The body is foreshortened with the span: unsquash it so it stays a body, not a needle, seen end-on.)
float2 e = float2(p.x * max(Seen, 0.25), p.y) / float2(0.12, 0.08);
float db = (length(e) - 1.0) * 0.08;
float d = min(min(d1, d2), db);
float aa = max(fwidth(d), 0.02);
float cov = saturate(0.5 - d / aa);
float tip = d2 < min(d1, db) ? smoothstep(0.45, 0.8, u2) : 0.0;
Col = float3(C0, C1, C2) * (1.0 - Tips * tip);
return cov * saturate(Cover);
"""

FAR_NORMAL = r"""
// Lit as the side the camera sees: the underside from below (facing down, toward the eye), the back from above.
return normalize(float3(0.0, 0.0, 1.0 - 2.0 * Below) * 0.8 + V * 0.6);
"""


def build_far():
    mat = new_material("M_BirdFar")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    mat.set_editor_property("tangent_space_normal", False)
    ins = {"Local": node(mat, unreal.MaterialExpressionLocalPosition, -1200, -100)}
    ins.update(instance_data(mat, ("Phase", "Amp", "Fold", "Cover", "Tips", "C0", "C1", "C2"), -1200, 0))
    ins.update(instance_data(mat, ("Dihedral", "Crank", "Seen"), -1200, 600, first=9))
    c = wire(mat, FAR_CODE, ins, F1, -700, 200, extra_outputs=(("Col", F3),))
    n = wire(mat, FAR_NORMAL, {"Below": node(mat, unreal.MaterialExpressionPerInstanceCustomData, -1000, 900, data_index=8),
                               "V": node(mat, unreal.MaterialExpressionCameraVectorWS, -1000, 980)}, F3, -700, 800)
    # A little of the sky's light on the shaded side (an underside against a bright sky otherwise goes near black).
    fill = custom(mat, "return Col * Sky * Fill;", ["Col", "Sky", "Fill"], F3, -400, 600)
    connect(c, "Col", fill, "Col")
    connect(node(mat, unreal.MaterialExpressionSkyAtmosphereDistantLightScatteredLuminance, -700, 650), "", fill, "Sky")
    connect(scalar(mat, "SkyFill", 0.1, -700, 720), "", fill, "Fill")
    MEL.connect_material_property(c, "Col", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(n, "", unreal.MaterialProperty.MP_NORMAL)
    MEL.connect_material_property(fill, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(node(mat, unreal.MaterialExpressionConstant, -400, 400, r=0.8), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(dither(mat, c, -400, 200), "", unreal.MaterialProperty.MP_OPACITY_MASK)
    MEL.recompile_material(mat)
    LIB.save_loaded_asset(mat)
    return mat


MID_WPO = r"""
// docs/wildlife-1: a mid-distance bird (build_birds.py: 100 cm across, X forward, Z up). The wings beat about the shoulder
// line (5 cm out from the body's axis), the hand a little behind the arm; folded they lie swept back along the back; a
// wader's legs (vertex colour G) swing down about the hip (UV1, m) and the bird stands up on them (UV0.v: its lift).
// Unreal's FBX import flips V: 1 - v. Returns the local offset (cm).
float3 P = Local;
float w = UV0.x;
float lift = (1.0 - UV0.y) * 100.0;
float side = P.y >= 0.0 ? 1.0 : -1.0;
float ry = max(abs(P.y) - 5.0, 0.0);
float beat = Amp * 0.85 * sin(6.2831853 * (Phase - 0.06 * w));
float cb = cos(beat), sb = sin(beat);
float3 flap = float3(P.x, side * (5.0 + ry * cb - P.z * sb), ry * sb + P.z * cb);
float3 tuck = float3(P.x - ry * 0.7, side * (5.0 + ry * 0.12), P.z + 3.0 + ry * 0.04);
float3 R = w > 0.001 ? lerp(flap, tuck, Fold) : P;
float hx = UV1.x * 100.0, hz = (1.0 - UV1.y) * 100.0;
float3 stand = float3(hx + (P.z - hz) * 0.3, P.y, hz - (hx - P.x));
R = VC.g > 0.5 ? lerp(P, stand, Fold) : R;
R.z += lift * Fold;
return R - P;
"""

MID_COLOUR = r"""
// The back and upper wing above, the underside below (by the vertex normal), tips darkened by Tips past 72% of the wing.
float up = saturate(N.z * 2.5 + 0.5);
float3 c = lerp(float3(D0, D1, D2), float3(U0, U1, U2), up);
return c * (1.0 - Tips * smoothstep(0.72, 0.9, W));
"""


def build_mid():
    mat = new_material("M_BirdMid")
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    data = instance_data(mat, ("Phase", "Amp", "Fold", "Fade", "U0", "U1", "U2", "D0", "D1", "D2", "Tips"), -1400, 0)
    uv0 = node(mat, unreal.MaterialExpressionTextureCoordinate, -1400, 800, coordinate_index=0)
    uv1 = node(mat, unreal.MaterialExpressionTextureCoordinate, -1400, 880, coordinate_index=1)
    wpo = wire(mat, MID_WPO, {"Local": node(mat, unreal.MaterialExpressionLocalPosition, -1400, -100), "UV0": uv0, "UV1": uv1,
                              "VC": node(mat, unreal.MaterialExpressionVertexColor, -1400, 960),
                              "Phase": data["Phase"], "Amp": data["Amp"], "Fold": data["Fold"]}, F3, -900, -100)
    to_world = node(mat, unreal.MaterialExpressionTransform, -600, -100)
    to_world.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
    to_world.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    connect(wpo, "", to_world, "")
    MEL.connect_material_property(to_world, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mask_w = node(mat, unreal.MaterialExpressionComponentMask, -1150, 800, r=True, g=False, b=False, a=False)
    connect(uv0, "", mask_w, "")
    col_ins = {k: data[k] for k in ("U0", "U1", "U2", "D0", "D1", "D2", "Tips")}
    col_ins["N"] = node(mat, unreal.MaterialExpressionVertexNormalWS, -1150, 900)
    col_ins["W"] = mask_w
    col = wire(mat, MID_COLOUR, col_ins, F3, -700, 300)
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(node(mat, unreal.MaterialExpressionConstant, -400, 450, r=0.75), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(dither(mat, data["Fade"], -400, 600), "", unreal.MaterialProperty.MP_OPACITY_MASK)
    MEL.recompile_material(mat)
    LIB.save_loaded_asset(mat)
    return mat


def import_body(path, mat):
    name = os.path.splitext(os.path.basename(path))[0]
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", FOLDER)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    ASSETS.import_asset_tasks([task])
    mesh = unreal.load_asset(f"{FOLDER}/{name}")
    if not mesh:
        raise RuntimeError(f"import failed: {path}")
    # A few hundred triangles drawn a few dozen times: plain instancing, not Nanite (its wings move in the vertex shader).
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", ns)
    mesh.set_material(0, mat)
    LIB.save_loaded_asset(mesh)
    tris = mesh.get_num_triangles(0) if hasattr(mesh, "get_num_triangles") else -1
    unreal.log(f"Birds: imported {name} ({tris} triangles)")


def main():
    far = build_far()
    mid = build_mid()
    unreal.log(f"Birds: built {far.get_name()} and {mid.get_name()}")
    bodies = sorted(glob.glob(os.path.join(SRC, "SM_Bird_*.fbx")))
    if not bodies:
        unreal.log_warning(f"Birds: no bodies in {SRC} (run Tools/blender/build_birds.py): every bird draws as a quad")
    for path in bodies:
        import_body(path, mid)
    unreal.log(f"Birds: done ({len(bodies)} bodies)")


main()
