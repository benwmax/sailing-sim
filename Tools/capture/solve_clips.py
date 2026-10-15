"""Crew C2: the body solve. Turns each clip's frames into an animation on the MetaHuman body for capture_clips.py.

Runs MetaHuman Animator's markerless body solve (the Fab plugin "MetaHuman Animator Markerless Motion Capture",
MetaHumanBodyTracker, enabled for the Windows editor in SailingSim.uproject) through its scripted entry point: for each
row of Tools/capture/clips.csv whose frames are in <CAPTURE_FOOTAGE>/<clip>/ (PNG or JPG, one per frame), it makes
  /Game/Crew/Capture/Footage/<clip>_Frames   an Img Media Source over the frames,
  /Game/Crew/Capture/Footage/<clip>          Footage Capture Data holding it (mono footage, no calibration),
  /Game/Crew/Capture/Performance/<clip>      a MetaHuman Performance: mono footage, body tracking on, face off,
processes it (blocking, about 1 frame a second on the RTX 4090) and exports the body to /Game/Crew/Capture/Solved/<clip>
(on the plugin's MetaHuman body skeleton), which is where capture_clips.py looks. A clip that already has a solve is
skipped unless CAPTURE_RESOLVE=1.

  CAPTURE_FOOTAGE      folder of frame folders (default D:\\dev\\capture\\frames; test footage: Saved/CaptureTest)
  CAPTURE_FPS          the footage's frame rate (default 30; the README asks for 60 from the phone)
  CAPTURE_ONLY         comma-separated clip names to solve (default all)
  CAPTURE_EXPORT_ONLY  1: re-export clips whose performance is already processed, without solving again

Run in a full editor after a build, not a -run=pythonscript commandlet: the solve needs the GPU, and the performance
refuses to process without a supported RHI (scripts/windows/capture-solve.ps1 runs this, capture_clips.py and the test).
"""
import csv
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLIPS = os.path.join(REPO, "Tools", "capture", "clips.csv")
FOOTAGE = os.environ.get("CAPTURE_FOOTAGE", r"D:\dev\capture\frames")
FPS = int(os.environ.get("CAPTURE_FPS", "30"))
ONLY = [c for c in os.environ.get("CAPTURE_ONLY", "").split(",") if c]
RESOLVE = os.environ.get("CAPTURE_RESOLVE") == "1"
EXPORT_ONLY = os.environ.get("CAPTURE_EXPORT_ONLY") == "1"
FOOTAGE_DIR = "/Game/Crew/Capture/Footage"
PERF_DIR = "/Game/Crew/Capture/Performance"
SOLVED = "/Game/Crew/Capture/Solved"
BODY = "/Game/Crew/MetaHumans/Helm/Body/SKM_Helm_BodyMesh"

EAL = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
FRAME_EXT = (".png", ".jpg", ".jpeg", ".exr")


def fresh(name, folder, cls, factory_name):
    """The asset at folder/name, made if missing; reused (and overwritten by the caller) if not, since these
    reference each other and a referenced asset can't be deleted."""
    path = f"{folder}/{name}"
    if EAL.does_asset_exist(path):
        return unreal.load_asset(path)
    factory = getattr(unreal, factory_name)() if hasattr(unreal, factory_name) else None
    return TOOLS.create_asset(name, folder, cls, factory)


def solve(clip, frames_dir):
    frames = sorted(f for f in os.listdir(frames_dir) if f.lower().endswith(FRAME_EXT))
    if not frames:
        unreal.log_warning(f"Solve: {clip}: no frames in {frames_dir}")
        return None
    src = fresh(f"{clip}_Frames", FOOTAGE_DIR, unreal.ImgMediaSource, "ImgMediaSourceFactoryNew")
    src.set_sequence_path(frames_dir.replace("\\", "/"))
    src.set_editor_property("frame_rate_override", unreal.FrameRate(FPS, 1))
    EAL.save_loaded_asset(src)
    capture = fresh(clip, FOOTAGE_DIR, unreal.FootageCaptureData, "FootageCaptureDataFactoryNew")
    capture.set_editor_property("image_sequences", [src])
    meta = capture.get_editor_property("metadata")
    meta.set_editor_property("frame_rate", float(FPS))  # the performance rejects footage without one
    capture.set_editor_property("metadata", meta)
    EAL.save_loaded_asset(capture)

    perf = fresh(clip, PERF_DIR, unreal.MetaHumanPerformance, "MetaHumanPerformanceFactoryNew")
    perf.set_editor_property("input_type", unreal.DataInputType.MONO_FOOTAGE)
    perf.set_editor_property("footage_capture_data", capture)
    perf.set_editor_property("face_tracking", False)
    perf.set_editor_property("body_tracking", True)
    if not perf.can_process():
        fcd = perf.get_editor_property("footage_capture_data")
        unreal.log_error(f"Solve: {clip}: the performance can't process this footage: input {perf.get_editor_property('input_type')}, "
                         f"footage {fcd.get_path_name() if fcd else None}, frames {src.get_sequence_path()} "
                         f"at {src.get_editor_property('frame_rate_override')}, "
                         f"{len(fcd.get_editor_property('image_sequences')) if fcd else 0} sequences, "
                         f"body {perf.get_editor_property('body_tracking')}, face {perf.get_editor_property('face_tracking')} "
                         f"(body tracking needs the MetaHumanBodyTracker plugin loaded)")
        return None
    perf.set_blocking_processing(True)
    t0 = unreal.MathLibrary.now()
    result = perf.start_pipeline(True)
    secs = unreal.MathLibrary.get_total_seconds(unreal.MathLibrary.subtract_date_time_date_time(unreal.MathLibrary.now(), t0))
    unreal.log(f"Solve: {clip}: {len(frames)} frames, pipeline {result} in {secs:.0f} s")
    EAL.save_loaded_asset(perf)
    # (get_number_of_processed_frames counts the face's frames: 0 for a body solve.)
    if result != unreal.StartPipelineErrorType.NONE or not perf.contains_animation_data_type(unreal.FrameAnimationDataType.BODY):
        unreal.log_error(f"Solve: {clip}: no body animation came out of the solve")
        return None
    return export(clip, perf)


def export(clip, perf):
    """The body on the performer skeleton: the plugin's MetaHuman body skeleton (/MetaHumanBodyTracker/
    metahuman_base_skel), the same bones as the crew's, which is all capture_clips.py needs (it reads tracks by bone
    name). Exporting onto the helm's own skeleton asset instead wants an IK retargeter and, without one, writes only
    the root."""
    utils = unreal.MetaHumanPerformanceExportUtils
    settings = utils.get_export_animation_sequence_settings(perf)
    settings.set_editor_property("show_export_dialog", False)
    settings.set_editor_property("export_face", False)
    settings.set_editor_property("export_body", True)
    settings.set_editor_property("export_skeleton", unreal.PerformanceExportSkeleton.PERFORMER_SKELETON)
    settings.set_editor_property("package_path", SOLVED)
    settings.set_editor_property("asset_name", clip)
    settings.set_editor_property("auto_save_anim_sequence", True)
    if EAL.does_asset_exist(f"{SOLVED}/{clip}"):
        EAL.delete_asset(f"{SOLVED}/{clip}")
    anim = utils.export_animation_sequence(perf, settings)
    if anim is None:
        unreal.log_error(f"Solve: {clip}: the export failed")
        return None
    EAL.save_loaded_asset(anim)
    unreal.log(f"Solve: {clip} -> {anim.get_path_name()} ({anim.get_play_length():.2f} s)")
    return anim


def main():
    body = unreal.load_asset(BODY)
    if body is None:
        unreal.log_error(f"Solve: needs the MetaHuman crew ({BODY})")
        return
    if not hasattr(unreal, "MetaHumanPerformance"):
        unreal.log_error("Solve: MetaHuman Animator isn't loaded (enable MetaHumanBodyTracker; Windows only)")
        return
    done = waiting = 0
    with open(CLIPS, newline="") as f:
        for row in csv.DictReader(f):
            clip = row["clip"].strip()
            if ONLY and clip not in ONLY:
                continue
            frames_dir = os.path.join(FOOTAGE, clip)
            if not os.path.isdir(frames_dir):
                waiting += 1
                continue
            if EAL.does_asset_exist(f"{SOLVED}/{clip}") and not RESOLVE:
                unreal.log(f"Solve: {clip}: already solved (CAPTURE_RESOLVE=1 solves it again)")
                continue
            perf = unreal.load_asset(f"{PERF_DIR}/{clip}") if EAL.does_asset_exist(f"{PERF_DIR}/{clip}") else None
            if EXPORT_ONLY and perf and perf.contains_animation_data_type(unreal.FrameAnimationDataType.BODY):
                anim = export(clip, perf)  # the performance is already processed: just export it again
            else:
                anim = solve(clip, frames_dir)
            if anim:
                done += 1
    unreal.log(f"Solve: {done} clips solved, {waiting} without footage in {FOOTAGE}")


main()
