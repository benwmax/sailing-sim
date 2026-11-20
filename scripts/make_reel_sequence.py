"""Builds /Game/Reel/LS_Reel: the empty level sequence the sim reel's Movie Render Queue renders run against.

The reel (docs/sim-reel/) renders whatever the game's own camera sees, so the sequence carries no tracks: Movie Render
Queue only needs one to time the render, and Tools/reel sets each shot's frame range and rate on the job itself. Ten
minutes at 30 fps covers any shot. Run with Tools/reel/capture_reel.py --make-sequence (or scripts/capture-reel.sh).
"""
import unreal

PATH = "/Game/Reel"
NAME = "LS_Reel"
FPS = 30
SECONDS = 600

if unreal.EditorAssetLibrary.does_asset_exist(f"{PATH}/{NAME}"):
    unreal.EditorAssetLibrary.delete_asset(f"{PATH}/{NAME}")
tools = unreal.AssetToolsHelpers.get_asset_tools()
seq = tools.create_asset(NAME, PATH, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
if not seq:
    raise RuntimeError(f"Could not create {PATH}/{NAME}")
seq.set_display_rate(unreal.FrameRate(FPS, 1))
seq.set_tick_resolution(unreal.FrameRate(FPS * 800, 1))
seq.set_playback_start(0)
seq.set_playback_end(FPS * SECONDS)
unreal.EditorAssetLibrary.save_loaded_asset(seq)
unreal.log(f"Sim reel: {PATH}/{NAME} ({SECONDS} s at {FPS} fps)")
