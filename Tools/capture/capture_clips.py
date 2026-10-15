"""Crew C2: carries the filmed crew clips to the crew's skeletons.

Bean films himself on a mock cockpit (docs/crew-2/README.md); MetaHuman Animator's markerless body solve (the Fab plugin
"MetaHuman Animator Markerless Motion Capture", Windows only) turns each clip into an animation on the MetaHuman body
skeleton, exported to /Game/Crew/Capture/Solved/<clip>. This script reads Tools/capture/clips.csv (clip, start, end in
seconds, label; end 0 = to the end) and, for each solved clip, saves
  /Game/Crew/Capture/Sailor/A_<label>     on SK_Sailor's skeleton (the AI crews, Low),
  /Game/Crew/Capture/MetaHuman/A_<label>  on the MetaHuman body skeleton (the player's crew), trimmed,
through UCrewCaptureLibrary (CrewCapture.h: the FCrewRig retarget). Content/Crew/Capture is git-ignored like the
MetaHumans; the clip list and this script are the source. SailingSim.Visual.CrewCapture checks what it saves.

Before any clip is filmed, CAPTURE_SYNTHETIC=1 makes a stand-in for each missing solve from the crew's own stances (the
clip list's last column, "Stance[:hike]=seconds;..."), so the pipeline and the test run end to end.

Run in the editor after a build (Windows):
  set CAPTURE_SYNTHETIC=1   (optional)
  UnrealEditor-Cmd.exe SailingSim.uproject -run=pythonscript -script=Tools/capture/capture_clips.py -unattended -NoCrashReporter
"""
import csv
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLIPS = os.path.join(REPO, "Tools", "capture", "clips.csv")
SOLVED = "/Game/Crew/Capture/Solved"
SYNTHETIC_DIR = "/Game/Crew/Capture/Synthetic"
OUT_SAILOR = "/Game/Crew/Capture/Sailor"
OUT_MH = "/Game/Crew/Capture/MetaHuman"
SYNTHETIC = os.environ.get("CAPTURE_SYNTHETIC") == "1"
FPS = int(os.environ.get("CAPTURE_FPS", "30"))

EAL = unreal.EditorAssetLibrary
LIB = unreal.CrewCaptureLibrary


def load(path):
    return unreal.load_asset(path) if EAL.does_asset_exist(path) else None


def main():
    sailor = load("/Game/Crew/SK_Sailor")
    body = load("/Game/Crew/MetaHumans/Helm/Body/SKM_Helm_BodyMesh")
    if not sailor or not body:
        unreal.log_error("Capture: needs SK_Sailor and the MetaHuman crew (Content/Crew/MetaHumans)")
        return
    done = skipped = 0
    with open(CLIPS, newline="") as f:
        for row in csv.DictReader(f):
            clip, label = row["clip"].strip(), row["label"].strip()
            start, end = float(row["start"] or 0), float(row["end"] or 0)
            src = load(f"{SOLVED}/{clip}")
            if src is None and SYNTHETIC and row.get("synthetic"):
                src = LIB.make_stance_clip(body, row["synthetic"].replace(";", ","), FPS, f"{SYNTHETIC_DIR}/{clip}")
                if src:
                    EAL.save_loaded_asset(src)
            if src is None:
                unreal.log(f"Capture: {clip}: no solve at {SOLVED}/{clip} yet, skipped")
                skipped += 1
                continue
            outs = [(LIB.retarget_clip(src, body, sailor, start, end, FPS, f"{OUT_SAILOR}/A_{label}"), "SK_Sailor"),
                    (LIB.retarget_clip(src, body, body, start, end, FPS, f"{OUT_MH}/A_{label}"), "MetaHuman")]
            for anim, what in outs:
                if anim is None:
                    unreal.log_error(f"Capture: {clip}: the retarget to {what} failed")
                    continue
                EAL.save_loaded_asset(anim)
            unreal.log(f"Capture: {clip} -> A_{label} ({start:.1f}-{end if end > 0 else 'end'} s, {FPS} fps)")
            done += 1
    unreal.log(f"Capture: {done} clips carried to the crew, {skipped} waiting for a solve")


main()
