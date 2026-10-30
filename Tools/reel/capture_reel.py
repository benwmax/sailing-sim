"""Renders one sim reel loop through Movie Render Queue (docs/sim-reel/README.md). Mac and Windows.

  python3 Tools/reel/capture_reel.py <shot> [--quality preview|master] [--passes a,b] [--compose-only] [--dry-run]
  python3 Tools/reel/capture_reel.py --make-sequence      (builds /Game/Reel/LS_Reel; done for you when missing)
  python3 Tools/reel/capture_reel.py --list

Shots and qualities are in Tools/reel/shots.json. For each pass it runs the game from the editor binary (-game, the
uncooked content, no packaging) at a fixed step from launch, with the shot's args plus -SailingReel and the reel
executor (Content/Python/sailing_reel_executor.py), which renders the frames to
Artifacts/reel/<shot>/<quality>/passes/<pass>/. Then Tools/reel/compose.py makes the loop and ffmpeg encodes:
  master.mov            ProRes 422 HQ, the full-resolution master (the longer reel cuts from these)
  <shot>.mp4, .webm     1280 wide, 30 fps, no audio, for the portfolio's sim-reel widget
  <shot>.jpg            the poster (first frame)
  meta.json             the shot, args, commit, render times, and render = "offline"
Uses the Mac lock (scripts/mac-lock.sh) on the Mac. Needs ffmpeg on the PATH (brew install ffmpeg / winget install ffmpeg).
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.environ.get("SAILING_ROOT", os.path.join(HERE, "..", "..")))
PROJECT = os.path.join(REPO, "SailingSim.uproject")
IS_MAC = platform.system() == "Darwin"
UE_ROOT = os.environ.get("UE_ROOT", "/Users/Shared/Epic Games/UE_5.8" if IS_MAC else r"C:\Program Files\Epic Games\UE_5.8")
EXECUTOR = ["-MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor",
            "-ExecutorPythonClass=/Engine/PythonTypes.SailingReelExecutor"]
SEQUENCE_ASSET = os.path.join(REPO, "Content", "Reel", "LS_Reel.uasset")

sys.path.insert(0, HERE)
import compose  # noqa: E402


def log(msg):
    print(msg, flush=True)


def editor_cmd():
    return os.path.join(UE_ROOT, "Engine", "Binaries", "Mac" if IS_MAC else "Win64", "UnrealEditor-Cmd" if IS_MAC else "UnrealEditor-Cmd.exe")


def make_sequence():
    script = os.path.join(REPO, "scripts", "make_reel_sequence.py")
    log("Building /Game/Reel/LS_Reel")
    subprocess.run([editor_cmd(), PROJECT, "-run=pythonscript", f"-script={script}", "-unattended", "-nosplash",
                    "-nullrhi"], check=True)
    if not os.path.isfile(SEQUENCE_ASSET):
        raise SystemExit(f"{SEQUENCE_ASSET} was not written")


class MacLock:
    """scripts/mac-lock.sh around the renders (the GPU is shared with the other lanes' benches)."""

    def __init__(self, what):
        self.env = dict(os.environ)
        self.env.setdefault("MAC_LOCK_OWNER", f"capture-reel {what} pid {os.getpid()}")
        self.held = False

    def __enter__(self):
        if IS_MAC:
            already = subprocess.run([os.path.join(REPO, "scripts", "mac-lock.sh"), "held"], env=self.env).returncode == 0
            if not already:
                subprocess.run([os.path.join(REPO, "scripts", "mac-lock.sh"), "take"], env=self.env, check=True)
                self.held = True
        return self

    def __exit__(self, *exc):
        if self.held:
            subprocess.run([os.path.join(REPO, "scripts", "mac-lock.sh"), "drop"], env=self.env)


def game_args(cfg, shot, pass_, quality, job_path):
    fps = shot["fps"]
    args = ["-game", "-windowed", "-ResX=1280", "-ResY=720", "-nosplash", "-UseFixedTimeStep", f"-FPS={fps}",
            "-NoTextureStreaming", "-unattended", *EXECUTOR, f"-SailingReelJob={job_path}",
            f"-SailingShot={shot['_name']}-{pass_['name']}"]
    if shot.get("dilation", 1) != 1:
        args.append(f"-SailingSlowMo={shot['dilation']}")
    return args + [f"-SailingQuality={cfg['qualities'][quality]['tier']}"] + cfg["common_args"] + shot["args"] + pass_["args"]


def run_game(args, timeout_s):
    """The game from the editor binary. On the Mac through `open` (started straight from a shell it can hang at window
    creation, as the packaged game does); on Windows the binary itself."""
    start = time.time()
    if IS_MAC:
        app = os.path.join(UE_ROOT, "Engine", "Binaries", "Mac", "UnrealEditor.app")
        p = subprocess.Popen(["open", "-n", "-W", "-a", app, "--args", PROJECT, *args])
    else:
        p = subprocess.Popen([os.path.join(UE_ROOT, "Engine", "Binaries", "Win64", "UnrealEditor.exe"), PROJECT, *args])
    try:
        p.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        log(f"  timed out after {timeout_s} s; stopping the game")
        if IS_MAC:
            subprocess.run(["pkill", "-9", "-f", f"{PROJECT} -game"])
        p.kill()
    return time.time() - start


def render_pass(cfg, shot, pass_, quality, out_root, dry_run):
    q = cfg["qualities"][quality]
    out = os.path.join(out_root, "passes", pass_["name"])
    decimate = shot.get("decimate", 1)
    frames = round((shot["seconds"] + shot.get("tail", 0)) * shot["fps"]) * decimate
    job = {"output_dir": out, "fps": shot["fps"], "frames": frames, "start_s": shot.get("start_s", 2),
           "width": q["width"], "height": q["height"], "spatial": q["spatial"], "temporal": q["temporal"],
           "engine_warmup": q.get("engine_warmup", 8), "render_warmup": q["render_warmup"], "format": q["format"],
           "dilation": shot.get("dilation", 1)}
    args = game_args(cfg, shot, pass_, quality, os.path.join(out, "job.json"))
    log(f"Pass {pass_['name']}: {frames} frames at {q['width']}x{q['height']}, {q['spatial']}x{q['temporal']} samples")
    log("  " + " ".join(args))
    if dry_run:
        return {"pass": pass_["name"], "frames": frames}
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    with open(os.path.join(out, "job.json"), "w") as f:
        json.dump(job, f, indent=1)
    # Generous: a 4K frame with 16 samples is seconds on the 4090 and longer on the Mac; plus start-up and shaders.
    timeout = 900 + frames * q["spatial"] * q["temporal"] * (3 if IS_MAC else 1)
    seconds = run_game(args, timeout)
    # The editor binary's -game log: ~/Library/Logs/SailingSim on the Mac, Saved/Logs on Windows.
    game_log = os.path.expanduser("~/Library/Logs/SailingSim/SailingSim.log") if IS_MAC else os.path.join(REPO, "Saved", "Logs", "SailingSim.log")
    if os.path.isfile(game_log):
        shutil.copy(game_log, os.path.join(out, "game.log"))
    done = {}
    if os.path.isfile(os.path.join(out, "done.json")):
        with open(os.path.join(out, "done.json")) as f:
            done = json.load(f)
    got = len(compose.frames_of(out))
    log(f"  {got} frames in {seconds:.0f} s ({seconds / max(got, 1):.2f} s a frame); success {done.get('success')}")
    if not done.get("success") or got < frames:
        raise SystemExit(f"Pass {pass_['name']} failed: {got}/{frames} frames; see {out}/game.log")
    telemetry = os.path.join(REPO, "Saved", "Bench", f"{shot['_name']}-{pass_['name']}.telemetry.csv")
    if os.path.isfile(telemetry):
        shutil.copy(telemetry, os.path.join(out, "telemetry.csv"))
    return {"pass": pass_["name"], "frames": got, "seconds": round(seconds, 1), "game_time_at_start": done.get("game_time_at_start")}


def encode(loop_dir, out_root, name, fps):
    ff = shutil.which("ffmpeg")
    if not ff:
        log("ffmpeg not found: the loop's frames are in " + loop_dir)
        return
    seq = os.path.join(loop_dir, "%05d.png")
    run = lambda *a: subprocess.run([ff, "-y", "-loglevel", "error", *a], check=True)
    run("-framerate", str(fps), "-i", seq, "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
        os.path.join(out_root, "master.mov"))
    # The portfolio's encode settings (bmax-portfolio docs/side-projects/sim-reel.md).
    web = ["-vf", "scale=1280:-2,fps=30", "-an"]
    run("-framerate", str(fps), "-i", seq, *web, "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", os.path.join(out_root, f"{name}.mp4"))
    run("-framerate", str(fps), "-i", seq, *web, "-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0",
        os.path.join(out_root, f"{name}.webm"))
    run("-i", os.path.join(out_root, f"{name}.mp4"), "-frames:v", "1", "-q:v", "3", os.path.join(out_root, f"{name}.jpg"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shot", nargs="?")
    ap.add_argument("--quality", default="preview")
    ap.add_argument("--passes", help="render only these passes (comma-separated); the others are reused")
    ap.add_argument("--compose-only", action="store_true", help="compose and encode the passes already rendered")
    ap.add_argument("--dry-run", action="store_true", help="print the game commands only")
    ap.add_argument("--make-sequence", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    with open(os.path.join(HERE, "shots.json")) as f:
        cfg = json.load(f)
    if a.list:
        for name, s in cfg["shots"].items():
            log(f"{name:10s} {s['seconds']:>4} s, {len(s['passes'])} pass(es): {s['what']}")
        return
    if a.make_sequence:
        make_sequence()
        return
    if a.shot not in cfg["shots"]:
        raise SystemExit(f"No shot {a.shot!r}; one of {', '.join(cfg['shots'])}")
    shot = dict(cfg["shots"][a.shot], _name=a.shot)
    out_root = os.path.join(REPO, "Artifacts", "reel", a.shot, a.quality)
    want = set(a.passes.split(",")) if a.passes else None
    results = []
    started = time.time()
    if not a.compose_only:
        if not os.path.isfile(SEQUENCE_ASSET) and not a.dry_run:
            make_sequence()
        with MacLock(a.shot):
            for p in shot["passes"]:
                if want is None or p["name"] in want:
                    results.append(render_pass(cfg, shot, p, a.quality, out_root, a.dry_run))
    if a.dry_run:
        return
    render_s = time.time() - started
    pass_dirs = [os.path.join(out_root, "passes", p["name"]) for p in shot["passes"]]
    missing = [d for d in pass_dirs if not os.path.isfile(os.path.join(d, "done.json"))]
    if missing:
        log("Not composing: no frames yet for " + ", ".join(os.path.basename(d) for d in missing))
        return
    log("Composing")
    tele = None
    t0 = dt = 0.0
    if shot["compose"].get("overlay") == "telemetry":
        tele = os.path.join(pass_dirs[0], "telemetry.csv")
        with open(os.path.join(pass_dirs[0], "done.json")) as f:
            done = json.load(f)
        q = cfg["qualities"][a.quality]
        # The first rendered frame comes after the engine's and the renderer's warm-up frames (one frame time each).
        d = shot.get("dilation", 1)
        t0 = done.get("game_time_at_start", 0.0) + (q.get("engine_warmup", 8) + q["render_warmup"]) * d / shot["fps"]
        dt = shot.get("decimate", 1) * d / shot["fps"]
    loop_dir = os.path.join(out_root, "loop")
    shutil.rmtree(loop_dir, ignore_errors=True)
    n = compose.compose(shot, pass_dirs, loop_dir, shot["fps"], shot.get("decimate", 1), tele, t0, dt, log)
    log("Encoding")
    encode(loop_dir, out_root, a.shot, shot["fps"])
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"shot": a.shot, "what": shot["what"], "render": shot.get("render", "offline"), "quality": a.quality,
            "frames": n, "fps": shot["fps"], "commit": commit, "machine": platform.node(), "args": cfg["common_args"] + shot["args"],
            "passes": results, "total_seconds": round(time.time() - started, 1), "render_seconds": round(render_s, 1)}
    with open(os.path.join(out_root, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    log(f"Done in {meta['total_seconds']:.0f} s: {out_root}")


if __name__ == "__main__":
    main()
