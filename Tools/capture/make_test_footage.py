"""Crew C2: renders test footage for the body solve from the game's own crew (no filmed clip needed, nothing licensed).

The helm MetaHuman (BP_Helm) plays a synthetic clip (/Game/Crew/Capture/Synthetic/<clip>, made by capture_clips.py with
CAPTURE_SYNTHETIC=1) on a plain stage, filmed as docs/crew-2/README.md asks of Bean's phone: locked off, whole body in
frame, about 3.5 m away at chest height, 40 deg forward of square, 1080p. Movie Render Queue writes PNG frames to
Saved/CaptureTest/<clip>/, which solve_clips.py takes like a filmed clip.

Two steps (scripts/windows/capture-solve.ps1 -TestClip <clip> runs both):
  stage   (UnrealEditor-Cmd -run=pythonscript): builds /Game/Crew/Capture/Test/L_Stage and LS_<clip>
  render  (UnrealEditor -ExecutePythonScript, a full editor: MRQ renders through PIE): renders LS_<clip>, then quits
The clip comes from CAPTURE_CLIP (default tack_port). Content/Crew/Capture is git-ignored; this script is the source.
"""
import math
import os
import sys

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLIP = os.environ.get("CAPTURE_CLIP", "tack_port")
FPS = int(os.environ.get("CAPTURE_FPS", "30"))
TEST = "/Game/Crew/Capture/Test"
MAP = f"{TEST}/L_Stage"
SEQ = f"{TEST}/LS_{CLIP}"
# CAPTURE_ANIM renders another clip on the same stage (e.g. the solve's /Game/Crew/Capture/MetaHuman/A_<label>, to
# compare with the source), into Saved/CaptureTest/<CAPTURE_OUT>.
ANIM = os.environ.get("CAPTURE_ANIM", f"/Game/Crew/Capture/Synthetic/{CLIP}")
OUT = os.path.join(REPO, "Saved", "CaptureTest", os.environ.get("CAPTURE_OUT", CLIP))

EAL = unreal.EditorAssetLibrary
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Camera: README's placement for a seated sailor (3-4 m, chest height, 30-45 deg forward of square). The MetaHuman faces
# +Y, so forward is +Y and square is +X.
CAM_DIST_CM, CAM_HEIGHT_CM, CAM_FORWARD_DEG, AIM_HEIGHT_CM = 350.0, 100.0, 40.0, 70.0
EXPOSURE_BIAS = float(os.environ.get("CAPTURE_EXPOSURE", "-1"))  # stops; manual exposure, no physical camera
SEATED_PELVIS_CM = 55.0  # pelvis bone over a 45 cm bench
HELM = "/Game/Crew/MetaHumans/Helm"
FACE_ABP = "/Game/Crew/MetaHumans/Common/Face/ABP_Face"
PREVIEW = int(os.environ.get("CAPTURE_PREVIEW", "0"))  # render only the first N frames (0 = all)


def spawn(cls_or_asset, loc, rot=(0, 0, 0), label=None):
    loc, rot = unreal.Vector(*loc), unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=rot[2])  # rot is (pitch, yaw, roll)
    if isinstance(cls_or_asset, str):  # a Blueprint (spawn_actor_from_object returns None in a commandlet)
        cls_or_asset = EAL.load_blueprint_class(cls_or_asset)
    a = ACTORS.spawn_actor_from_class(cls_or_asset, loc, rot)
    if label:
        a.set_actor_label(label)
    return a


def shape(mesh, label, loc, scale):
    a = spawn(unreal.StaticMeshActor, loc, label=label)
    a.static_mesh_component.set_static_mesh(unreal.load_asset(f"/Engine/BasicShapes/{mesh}.{mesh}"))
    a.set_actor_scale3d(unreal.Vector(*scale))
    return a


def box(label, loc, size_cm):
    return shape("Cube", label, loc, tuple(s / 100.0 for s in size_cm))


def stage():
    clip = unreal.load_asset(ANIM)
    if clip is None or not EAL.does_asset_exist(f"{HELM}/Body/SKM_Helm_BodyMesh"):
        unreal.log_error(f"TestFootage: needs {ANIM} (capture_clips.py with CAPTURE_SYNTHETIC=1 makes the synthetic ones) and the MetaHuman crew")
        return
    # A blank map saved over the old one (LevelEditorSubsystem.new_level refuses an existing path, and its
    # save_current_level can't save a level made in a commandlet).
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    # A plain game mode: the project's default would build the lake and the boat around the stage.
    world.get_world_settings().set_editor_property("default_game_mode", unreal.GameModeBase.static_class())

    # Daylight from one side and a sky, a grey floor and a backdrop far behind the sailor: even light, a plain background.
    sun = spawn(unreal.DirectionalLight, (0, 0, 500), (-40, -135, 0), "Sun")
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    spawn(unreal.SkyAtmosphere, (0, 0, 0), label="Sky")
    sky = spawn(unreal.SkyLight, (0, 0, 300), label="SkyLight")
    sky.light_component.set_editor_property("real_time_capture", True)
    # Fixed exposure: the project's pipeline meters the light itself in the game (VisualPipeline), which this stage skips.
    ppv = spawn(unreal.PostProcessVolume, (0, 0, 0), label="Exposure")
    ppv.set_editor_property("unbound", True)
    pp = ppv.get_editor_property("settings")
    for k, v in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                 ("override_auto_exposure_apply_physical_camera_exposure", True),
                 ("auto_exposure_apply_physical_camera_exposure", False),
                 ("override_auto_exposure_bias", True), ("auto_exposure_bias", EXPOSURE_BIAS)):
        pp.set_editor_property(k, v)
    ppv.set_editor_property("settings", pp)
    shape("Plane", "Floor", (0, 0, 0), (40, 40, 1))
    box("Backdrop", (-800, -400, 200), (20, 1600, 400))
    # The mock cockpit's seat (README: a 45 cm bench, running across the camera's view); the sailor sits on its edge.
    box("Bench", (0, -12, 22.5), (140, 40, 45))
    # The stances carry the pelvis at the boat's seat height; drop the sailor so it sits on the bench.
    drop = unreal.AnimationLibrary.get_bone_pose_for_time(clip, "pelvis", 0.0, False).translation.z - SEATED_PELVIS_CM
    drop = float(os.environ.get("CAPTURE_DROP", drop))

    # The helm as the game assembles it (CrewPose.cpp LoadMetaHumanCrew): body, outfit and face. Plain actors, not
    # BP_Helm: its MetaHuman component re-sets the body's animation at BeginPlay, so a track on it never shows.
    # CAPTURE_MESH draws one other mesh instead (e.g. the solve's performer, /MetaHumanBodyTracker/SKM_Body).
    parts = {}
    meshes = (("Body", f"{HELM}/Body/SKM_Helm_BodyMesh"), ("Outfit", f"{HELM}/Clothing/Helm_Outfits"),
              ("Face", f"{HELM}/Face/SKM_Helm_FaceMesh"))
    if os.environ.get("CAPTURE_MESH"):
        meshes = (("Body", os.environ["CAPTURE_MESH"]),)
    for part, mesh in meshes:
        a = spawn(unreal.SkeletalMeshActor, (0, 0, -drop), label=f"Helm{part}")
        c = a.skeletal_mesh_component
        c.set_skeletal_mesh_asset(unreal.load_asset(mesh))
        if part != "Body":
            a.attach_to_actor(parts["Body"][0], "", unreal.AttachmentRule.SNAP_TO_TARGET,
                              unreal.AttachmentRule.SNAP_TO_TARGET, unreal.AttachmentRule.SNAP_TO_TARGET, False)
        if part == "Face":  # ABP_Face copies the attach parent's pose (the head and neck)
            c.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_BLUEPRINT)
            c.set_anim_instance_class(EAL.load_blueprint_class(FACE_ABP))
        parts[part] = (a, c)

    a = math.radians(CAM_FORWARD_DEG)
    cam_loc = (CAM_DIST_CM * math.cos(a), CAM_DIST_CM * math.sin(a), CAM_HEIGHT_CM)
    yaw = math.degrees(math.atan2(-cam_loc[1], -cam_loc[0]))
    pitch = math.degrees(math.atan2(AIM_HEIGHT_CM - CAM_HEIGHT_CM, CAM_DIST_CM))
    cam = spawn(unreal.CineCameraActor, cam_loc, (pitch, yaw, 0), "Phone")
    cc = cam.get_cine_camera_component()
    # A phone's main camera: about 26 mm full-frame equivalent, everything in focus.
    fb = cc.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", 36.0)
    fb.set_editor_property("sensor_height", 20.25)
    cc.set_editor_property("filmback", fb)
    cc.set_editor_property("current_focal_length", 26.0)
    fs = cc.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", fs)
    # Saved before the sequence binds anything: bindings made while the map is still /Temp/Untitled don't resolve in PIE.
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        unreal.log_error(f"TestFootage: couldn't save {MAP}")
        return

    if EAL.does_asset_exist(SEQ):
        EAL.delete_asset(SEQ)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = tools.create_asset(f"LS_{CLIP}", TEST, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    frames = int(round(clip.get_play_length() * FPS))
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(frames)
    # The camera is a spawnable; the body and the outfit (same skeleton) are possessed and play the clip, frame-locked
    # to the render. The face follows the body through ABP_Face.
    binding = seq.add_spawnable_from_instance(cam)
    ACTORS.destroy_actor(cam)
    for part in [p for p in ("Body", "Outfit") if p in parts]:
        anim = seq.add_possessable(parts[part][0]).add_track(unreal.MovieSceneSkeletalAnimationTrack).add_section()
        anim.set_range(0, frames)
        params = anim.get_editor_property("params")
        params.set_editor_property("animation", clip)
        anim.set_editor_property("params", params)
    add_track = getattr(seq, "add_track", None) or seq.add_master_track
    cut = add_track(unreal.MovieSceneCameraCutTrack).add_section()
    cut.set_range(0, frames)
    cut.set_camera_binding_id(seq.get_portable_binding_id(seq, binding) if hasattr(seq, "get_portable_binding_id")
                              else seq.get_binding_id(binding))
    EAL.save_loaded_asset(seq)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        unreal.log_error(f"TestFootage: couldn't save {MAP}")
        return
    unreal.log(f"TestFootage: staged {CLIP} ({frames} frames at {FPS} fps) in {MAP}, {SEQ}")


# Kept alive while MRQ renders (it calls back on the game thread after the script returns).
_KEEP = {}


def render():
    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    queue = subsystem.get_queue()
    queue.delete_all_jobs()
    job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.map = unreal.SoftObjectPath(MAP)
    job.sequence = unreal.SoftObjectPath(SEQ)
    cfg = job.get_configuration()
    out = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out.output_resolution = unreal.IntPoint(1920, 1080)
    out.output_directory = unreal.DirectoryPath(OUT.replace("\\", "/"))
    out.file_name_format = "{frame_number}"
    out.zero_pad_frame_numbers = 5
    if PREVIEW > 0:
        out.use_custom_playback_range = True
        out.custom_start_frame = 0
        out.custom_end_frame = PREVIEW
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.engine_warm_up_count = 32  # lets auto exposure and the sky light settle before frame 0
    os.makedirs(OUT, exist_ok=True)

    def finished(executor, success):
        unreal.log(f"TestFootage: rendered {CLIP} to {OUT} (success {success})")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)  # -ExecutePythonScript then quits

    # Without this, -ExecutePythonScript quits the editor on the next tick, ending PIE before MRQ renders a frame.
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    executor = unreal.MoviePipelinePIEExecutor(subsystem)
    executor.on_executor_finished_delegate.add_callable_unique(finished)
    _KEEP["executor"] = executor
    subsystem.render_queue_with_executor_instance(executor)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stage"
    if mode == "render":
        render()
    else:
        stage()  # returns normally: os._exit crashes the editor on the way out on Windows (docs/windows/README.md)
