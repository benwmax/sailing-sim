"""Visual V7: imports recorded sound samples (Audio/Samples/<Cue>.wav) into /Game/Audio/Samples/S_<Cue>, looping. A
sample replaces the synthesized voice of the same name (ESailingCue in SailingAudio.h: Wind, GustRumble, SailFlog,
Telltales, BowWave, HullSlap, Winch, SheetBlock, HalyardSlap, RainDeck, RainWater, SquallHiss, Thunder); the game
drives its level from the same physics. Credit each file in Audio/Samples/CREDITS.md (Freesound CC0 or Bean's own).
Run: scripts/import-audio.sh"""
import glob
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "Audio", "Samples")
DEST = "/Game/Audio/Samples"
CUES = {"Wind", "GustRumble", "SailFlog", "Telltales", "BowWave", "HullSlap", "Winch", "SheetBlock", "HalyardSlap", "RainDeck", "RainWater",
        "SquallHiss", "Thunder"}
tools = unreal.AssetToolsHelpers.get_asset_tools()
for path in sorted(glob.glob(os.path.join(SRC, "*.wav"))):
    cue = os.path.splitext(os.path.basename(path))[0]
    if cue not in CUES:
        unreal.log_warning(f"{cue}.wav: not a cue name, skipped")
        continue
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", f"S_{cue}")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    tools.import_asset_tasks([task])
    wave = unreal.load_asset(f"{DEST}/S_{cue}")
    if wave:
        wave.set_editor_property("looping", True)
        unreal.EditorAssetLibrary.save_loaded_asset(wave)
        unreal.log(f"Imported S_{cue}")
unreal.log("Import done")
os._exit(0)
