"""Visual V7: the MetaHuman crew (Medium and High; Low keeps SK_Sailor). Run in the full editor (scripts/make-metahumans.sh):
the MetaHuman build bakes textures with the Texture Graph, which needs a ticking editor with a renderer, so the steps
run from a Slate tick callback.

For each role a MetaHuman Creator preset is duplicated to /Game/Crew/MetaHumanSources/<Role>, rigged by Epic's cloud
auto-rigging (joints only; needs the editor signed in to an Epic account: the first run opens the device-code page),
given its texture sources, and assembled with the optimized pipeline (high quality since Graphics G3) to
/Game/Crew/MetaHumans/<Role>/... with the shared parts in /Game/Crew/MetaHumans/Common. The default garment (shirt and
shorts) stays on; the game adds the life jacket and cap (/Game/Crew/Gear) and the grooms (cards on the Mac, whose SM5 shader
platform has no strand geometry; strands on Windows High and Ultra).
The output is git-ignored (about 0.5 GB per character, and the MetaHuman licence covers use in the game, not
redistribution); SailingSim.Visual.MetaHumanCrew checks it.
"""
import os, time, traceback
import unreal

ROLES = [("Helm", "Bruce"), ("Trimmer", "Ada"), ("Bow", "Omari")]
ROOT = "/Game/Crew/MetaHumans"            # what the game loads (cooked: Body, Face, Clothing per role)
SOURCES = "/Game/Crew/MetaHumanSources"   # the MetaHuman Character assets (editor only, never cooked)
PRESETS = "/MetaHumanCharacter/Optional/Presets"
# Graphics G3: High (more face and body LODs, larger textures, the grooms' card atlases for the hair). MH_QUALITY=MEDIUM
# for the V7 build.
QUALITY = os.environ.get("MH_QUALITY", "HIGH").upper()


def log(m):
    unreal.log("MetaHumans: " + str(m))


def make(role, preset):
    if unreal.EditorAssetLibrary.does_asset_exist(f"{ROOT}/{role}/Face/SKM_{role}_FaceMesh"):
        log(f"{role}: already built (delete {ROOT}/{role} to rebuild)")
        return
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    src = f"{SOURCES}/{role}"
    path = f"{ROOT}/{role}"
    ch = unreal.load_asset(f"{src}/{role}.{role}")
    fresh = ch is None
    if fresh:
        ch = tools.duplicate_asset(role, src, unreal.load_asset(f"{PRESETS}/{preset}.{preset}"))
    sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    if not sub.try_add_object_to_edit(ch):
        raise RuntimeError(f"{role}: can't edit")
    try:
        # The cloud rig and texture sources are saved with the source character: only a new one needs them (a rebuild at
        # another quality reuses them; MH_RERIG=1 asks again).
        if fresh or os.environ.get("MH_RERIG") == "1":
            rq = unreal.MetaHumanCharacterAutoRiggingRequestParams()
            rq.blocking = True
            rq.report_progress = False
            rq.rig_type = unreal.MetaHumanRigType.JOINTS_ONLY
            sub.request_auto_rigging(ch, rq)
            tq = unreal.MetaHumanCharacterTextureRequestParams()
            tq.blocking = True
            tq.report_progress = False
            sub.request_texture_sources(character=ch, params=tq)
            unreal.EditorAssetLibrary.save_loaded_asset(ch)
        p = unreal.MetaHumanCharacterEditorBuildParameters()
        p.pipeline_type = unreal.MetaHumanDefaultPipelineType.OPTIMIZED
        p.pipeline_quality = getattr(unreal.MetaHumanQualityLevel, QUALITY)
        p.absolute_build_path = ROOT          # the build adds /<Role>
        p.common_folder_path = f"{ROOT}/Common"
        p.enable_wardrobe_item_validation = False
        try:
            sub.build_meta_human(character=ch, params=p)
        except Exception as e:
            # The face control rigs log link errors that Python raises; the meshes still build (checked below).
            log(f"{role}: build reported: " + str(e).splitlines()[0][:160])
    finally:
        if sub.is_object_added_for_editing(ch):
            sub.remove_object_to_edit(ch)
    # Save now: the editor has been seen to die on a Metal pipeline later in the session.
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    for part in (f"{path}/Body/SKM_{role}_BodyMesh", f"{path}/Face/SKM_{role}_FaceMesh", f"{path}/Clothing/{role}_Outfits"):
        log(f"{role}: {part} {'ok' if unreal.EditorAssetLibrary.does_asset_exist(part) else 'MISSING'}")


T0 = time.time()
state = {"i": 0, "busy": False, "wait": None}


def tick(dt):
    if state["busy"]:
        return
    try:
        t = time.time() - T0
        if t < 60:                       # let the startup shader compiles settle
            return
        if state["i"] < len(ROLES):
            state["busy"] = True
            try:
                make(*ROLES[state["i"]])
            finally:
                state["i"] += 1
                state["busy"] = False
                state["wait"] = time.time()
        elif time.time() - state["wait"] > 20:   # the last textures finish baking over a few frames
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
            log("done")
            os._exit(0)
    except Exception:
        log("FAILED " + traceback.format_exc())
        os._exit(1)


unreal.register_slate_post_tick_callback(tick)
log("waiting for the editor to settle")
