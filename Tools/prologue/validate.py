"""Checks the prologue's scripted scene (Content/Prologue/prologue.json, docs/prologue/README.md): the same rules
FScriptedScene::LoadText applies in the game (Source/SailingPhysics/Private/ScriptedScene.cpp), plus a few the loader
leaves to the author (captions in every call, call ids under "captain." or "instructor.", every camera used, every step at
a station). The first job (#402, Content/FirstSail/first-sail.json) is the same format.

Usage: python3 Tools/prologue/validate.py [scene.json ...]   (defaults to Content/Prologue/prologue.json)
       python3 Tools/prologue/validate.py --self-test         (the validator rejects broken scenes)
Exits non-zero on any problem. SailingSim.Prologue.Scene loads the same file in the game.
"""
import copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
DEFAULT = os.path.join(ROOT, "Content", "Prologue", "prologue.json")
FIRST_JOB = os.path.join(ROOT, "Content", "FirstSail", "first-sail.json")

SCENE_KEYS = {"schema_version", "id", "title", "setting", "assist_caption", "cameras", "stations", "actions", "steps"}
SETTING_KEYS = {"boat", "world", "weather", "rain", "wind_kn", "gust_kn", "sea_hs_m", "reefs", "hour", "world_stand_in", "stand_in", "then"}
STEP_KEYS = {"id", "trigger", "call", "expect", "retry_after_s", "crew_takes_over_after", "next", "checkpoint", "restart", "camera", "station", "weather"}
CALL_KEYS = {"id", "caption", "retry", "ok"}
# Trigger type -> (required, optional) fields, as ScriptedScene.cpp reads them.
TRIGGERS = {
    "previous": (set(), {"after_s", "or_after_s"}),
    "time": ({"at_s"}, {"after_s"}),
    "gust": ({"over_mean_kn"}, {"after_s", "or_after_s"}),
    "twa": ({"twa_min_deg", "twa_max_deg"}, {"after_s", "or_after_s"}),
    "heel": ({"heel_above_deg"}, {"after_s", "or_after_s"}),
    "speed": ({"speed_above_kn"}, {"after_s", "or_after_s"}),
    "past-mark": ({"bearing_deg", "meters"}, {"after_s", "or_after_s"}),
}
EXPECTS = {
    "none": ({"seconds"}, set()),
    "sheet": ({"sheet"}, {"by", "at_least", "at_most", "controls", "within_s"}),
    "tack": (set(), {"within_s"}),
    "gybe": (set(), {"within_s"}),
    "hold": ({"hold_s"}, {"twa_min_deg", "twa_max_deg", "max_heel_deg", "min_speed_kn", "max_speed_kn", "station", "controls", "within_s"}),
    "station": ({"station"}, {"within_s"}),
    "action": ({"action"}, {"within_s"}),
}

# Step 4: the weather a step brings as it begins (FWeatherSystem::CueSquall / CueClearing).
WEATHER_CUES = {"squall", "clearing"}

# Step 2: the crew stations and the controls each one works (CrewStation.cpp's StationOwns).
STATIONS = {
    "helm": {"wheel"},
    "jib-trimmer": {"jib-sheet", "grinder"},
    "main-trimmer": {"main-sheet", "traveller", "traveller-dump"},
}
CONTROLS = set().union(*STATIONS.values())


def problems(scene):
    errors = []
    def check(cond, msg):
        if not cond: errors.append(msg)
    def only(obj, allowed, where):
        for k in obj:
            check(k in allowed, f"{where}: unknown field \"{k}\"")
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    check(isinstance(scene, dict), "the scene is not a JSON object")
    if not isinstance(scene, dict): return errors
    only(scene, SCENE_KEYS, "scene")
    check(scene.get("schema_version") == 1, "scene: schema_version must be 1")
    for f in ("id", "title"):
        check(isinstance(scene.get(f), str) and scene[f], f"scene: missing {f}")
    s = scene.get("setting")
    check(isinstance(s, dict), "scene: missing setting")
    if isinstance(s, dict):
        only(s, SETTING_KEYS, "setting")
        check(isinstance(s.get("boat"), str) and s["boat"], "setting: missing boat")
        check(num(s.get("wind_kn")), "setting: missing wind_kn")
        if "gust_kn" in s: check(num(s["gust_kn"]) and s["gust_kn"] >= s.get("wind_kn", 0), "setting: gust_kn below wind_kn")
        reefs_ok = lambda r: isinstance(r, int) and not isinstance(r, bool) and 0 <= r <= 3
        if "reefs" in s: check(reefs_ok(s["reefs"]), "setting: reefs is 0 to 3")
        si = s.get("stand_in")
        if si is not None:
            check(isinstance(si, dict) and set(si) <= {"boat", "wind_kn", "gust_kn", "reefs"} and si.get("boat"), "setting.stand_in: boat, wind_kn, gust_kn, reefs")
            if isinstance(si, dict) and "reefs" in si: check(reefs_ok(si["reefs"]), "setting.stand_in: reefs is 0 to 3")
        if "hour" in s: check(num(s["hour"]) and 0 <= s["hour"] < 24, "setting: hour is 0 to 24")
        ws = s.get("world_stand_in")
        if ws is not None:
            check(isinstance(ws, dict) and set(ws) <= {"world", "launch", "wind_from_deg"} and isinstance(ws.get("world"), str) and ws["world"],
                  "setting.world_stand_in: world, launch, wind_from_deg")
            if isinstance(ws, dict) and "wind_from_deg" in ws: check(num(ws["wind_from_deg"]) and 0 <= ws["wind_from_deg"] < 360, "setting.world_stand_in: wind_from_deg is 0 to 360")
        th = s.get("then")
        if th is not None:
            check(isinstance(th, dict) and set(th) <= {"cut", "tier"}, "setting.then: cut and tier only")
    cameras, stations, actions = (scene.get(k, []) for k in ("cameras", "stations", "actions"))
    for name, lst in (("cameras", cameras), ("stations", stations), ("actions", actions)):
        check(isinstance(lst, list) and all(isinstance(x, str) and x for x in lst), f"scene: {name} holds names only")
        check(len(set(lst)) == len(lst), f"scene: {name} repeat")
    for st in stations if isinstance(stations, list) else []:
        check(st in STATIONS, f"scene: unknown station \"{st}\"")

    steps = scene.get("steps")
    check(isinstance(steps, list) and steps, "scene: steps must be a non-empty list")
    if not isinstance(steps, list): return errors
    ids, used_cameras, used_stations, used_actions, call_ids = [], set(), set(), set(), set()
    cues = []
    for n, st in enumerate(steps, 1):
        if not isinstance(st, dict):
            errors.append(f"step {n}: not an object"); continue
        sid = st.get("id") or f"step {n}"
        only(st, STEP_KEYS, sid)
        check(isinstance(st.get("id"), str) and st["id"], f"step {n}: missing id")
        check(st.get("id") not in ids, f"{sid}: repeated step id")
        check(st.get("id") != "end", f"{sid}: \"end\" is reserved for next")
        ids.append(st.get("id"))
        for k in ("retry_after_s", "crew_takes_over_after"):
            if k in st: check(num(st[k]) and st[k] >= 0, f"{sid}: {k} must not be negative")
        if "checkpoint" in st: check(isinstance(st["checkpoint"], bool), f"{sid}: checkpoint must be true or false")
        if "restart" in st:
            r = st["restart"]
            check(isinstance(r, dict) and set(r) <= {"twa_deg", "speed_kn"} and num(r.get("twa_deg")), f"{sid}.restart: twa_deg (and speed_kn)")
            check(st.get("checkpoint") is True, f"{sid}: a restart pose belongs on a checkpoint")
        if st.get("checkpoint"): check("restart" in st, f"{sid}: a checkpoint needs a restart pose (where the game puts the boat)")
        if "camera" in st:
            check(st["camera"] in cameras, f"{sid}: camera \"{st['camera']}\" is not in the scene's cameras")
            used_cameras.add(st["camera"])
        if "station" in st:
            check(st["station"] in stations, f"{sid}: station \"{st['station']}\" is not in the scene's stations")
            used_stations.add(st["station"])
        elif stations:
            errors.append(f"{sid}: every step names its station (where the scene puts the crew member)")

        if "weather" in st:
            w = st["weather"]
            check(isinstance(w, dict) and set(w) <= {"cue", "in_s"}, f"{sid}.weather: cue and in_s only")
            if isinstance(w, dict):
                check(w.get("cue") in WEATHER_CUES, f"{sid}.weather: unknown weather cue \"{w.get('cue')}\"")
                if "in_s" in w: check(num(w["in_s"]) and w["in_s"] >= 0, f"{sid}.weather: in_s must not be negative")
                cues.append((sid, w.get("cue")))

        t = st.get("trigger")
        check(isinstance(t, dict), f"{sid}: missing trigger")
        if isinstance(t, dict):
            tt = t.get("type")
            check(tt in TRIGGERS, f"{sid}.trigger: unknown trigger \"{tt}\"")
            if tt in TRIGGERS:
                req, opt = TRIGGERS[tt]
                only(t, req | opt | {"type"}, f"{sid}.trigger")
                for k in req: check(num(t.get(k)), f"{sid}.trigger: missing {k}")
                if tt == "twa" and num(t.get("twa_min_deg")) and num(t.get("twa_max_deg")):
                    check(t["twa_min_deg"] <= t["twa_max_deg"], f"{sid}.trigger: twa_min_deg above twa_max_deg")
        c = st.get("call")
        check(isinstance(c, dict), f"{sid}: missing call")
        if isinstance(c, dict):
            only(c, CALL_KEYS, f"{sid}.call")
            check(isinstance(c.get("id"), str) and c["id"].startswith(("captain.", "instructor.")), f"{sid}.call: id must start with captain. or instructor.")
            check(c.get("id") not in call_ids, f"{sid}.call: repeated call id")
            call_ids.add(c.get("id"))
            check(isinstance(c.get("caption"), str) and c["caption"].strip(), f"{sid}.call: missing caption")
            check(len(c.get("caption", "")) <= 120, f"{sid}.call: caption over 120 characters (one callout line or two)")
        e = st.get("expect")
        check(isinstance(e, dict), f"{sid}: missing expect")
        if isinstance(e, dict):
            et = e.get("type")
            check(et in EXPECTS, f"{sid}.expect: unknown expectation \"{et}\"")
            if et in EXPECTS:
                req, opt = EXPECTS[et]
                only(e, req | opt | {"type"}, f"{sid}.expect")
                for k in req: check(k in e, f"{sid}.expect: missing {k}")
                if "within_s" in e: check(num(e["within_s"]) and e["within_s"] > 0, f"{sid}.expect: within_s must be positive")
                if et == "sheet":
                    check(e.get("sheet") in ("main", "jib"), f"{sid}.expect: sheet must be main or jib")
                    check(any(k in e for k in ("by", "at_least", "at_most")), f"{sid}.expect: a sheet expectation needs by, at_least or at_most")
                if et == "hold":
                    check(("twa_min_deg" in e) == ("twa_max_deg" in e), f"{sid}.expect: a TWA band needs both twa_min_deg and twa_max_deg")
                if "controls" in e:
                    ok = isinstance(e["controls"], list) and all(isinstance(c, str) and c for c in e["controls"])
                    check(ok, f"{sid}.expect: controls holds names only")
                    for c in e["controls"] if ok else []:
                        if c not in CONTROLS: errors.append(f"{sid}.expect: unknown control \"{c}\"")
                        elif c not in STATIONS.get(st.get("station"), set()):
                            errors.append(f"{sid}.expect: control \"{c}\" is not worked at the step's station \"{st.get('station', '')}\"")
                if "station" in e:
                    check(e["station"] in stations, f"{sid}.expect: station \"{e['station']}\" is not in the scene's stations")
                    used_stations.add(e["station"])
                if "action" in e:
                    check(e["action"] in actions, f"{sid}.expect: action \"{e['action']}\" is not in the scene's actions")
                    used_actions.add(e["action"])
    for st in steps:
        if isinstance(st, dict) and "next" in st:
            check(st["next"] == "end" or st["next"] in ids, f"{st.get('id')}: next names no step: \"{st['next']}\"")
    check(steps and isinstance(steps[0], dict) and steps[0].get("checkpoint") is True, "the first step must be a checkpoint (the scene restarts there)")
    # Every step reachable from the first, and the scene reaches its end.
    if not errors:
        idx = {st["id"]: i for i, st in enumerate(steps)}
        seen, i = set(), 0
        while 0 <= i < len(steps) and i not in seen:
            seen.add(i)
            nxt = steps[i].get("next", "")
            i = len(steps) if nxt == "end" else (idx[nxt] if nxt else i + 1)
        check(i >= len(steps), "the steps loop: the scene never ends")
        for j, st in enumerate(steps):
            check(j in seen, f"{st['id']}: never reached")
    # The weather runs forward: a clearing clears a squall, each cue once.
    names = [c for _, c in cues]
    check(len(set(names)) == len(names), "a weather cue is used twice")
    if "clearing" in names: check("squall" in names and names.index("squall") < names.index("clearing"), "the clearing cue comes after the squall's")
    for c in set(cameras) - used_cameras: errors.append(f"camera \"{c}\" is listed but no step uses it")
    return errors


def self_test():
    good = json.load(open(DEFAULT, encoding="utf-8"))
    assert not problems(good), problems(good)
    cases = []
    bad = copy.deepcopy(good); bad["steps"][1]["trigger"]["type"] = "moonrise"; cases.append(("unknown trigger", bad, "unknown trigger"))
    bad = copy.deepcopy(good); bad["steps"][2]["next"] = "no-such-step"; cases.append(("dangling next", bad, "next names no step"))
    bad = copy.deepcopy(good); bad["steps"][1]["expect"]["type"] = "dance"; cases.append(("unknown expectation", bad, "unknown expectation"))
    bad = copy.deepcopy(good); bad["steps"][3]["id"] = bad["steps"][2]["id"]; cases.append(("repeated id", bad, "repeated step id"))
    bad = copy.deepcopy(good); bad["steps"][0]["camera"] = "drone"; cases.append(("unknown camera", bad, "not in the scene's cameras"))
    bad = copy.deepcopy(good); bad["steps"][1]["trigger"]["over_mean"] = 6; cases.append(("typo'd field", bad, "unknown field"))
    bad = copy.deepcopy(good); bad["steps"][-1]["next"] = good["steps"][0]["id"]; cases.append(("loop", bad, "never ends"))
    grind = next(i for i, st in enumerate(good["steps"]) if st["id"] == "grind")
    bad = copy.deepcopy(good); bad["steps"][grind]["expect"]["controls"] = ["wheel"]; cases.append(("control at the wrong station", bad, "is not worked at the step's station"))
    bad = copy.deepcopy(good); bad["steps"][grind]["expect"]["controls"] = ["capstan"]; cases.append(("unknown control", bad, "unknown control"))
    bad = copy.deepcopy(good); del bad["steps"][grind]["station"]; cases.append(("step without a station", bad, "every step names its station"))
    bad = copy.deepcopy(good); bad["stations"].append("pit"); cases.append(("unknown station", bad, "unknown station"))
    dump = next(i for i, st in enumerate(good["steps"]) if st.get("weather", {}).get("cue") == "squall")
    bad = copy.deepcopy(good); bad["steps"][dump]["weather"]["cue"] = "hail"; cases.append(("unknown weather cue", bad, "unknown weather cue"))
    bad = copy.deepcopy(good); del bad["steps"][dump]["weather"]; cases.append(("a clearing without a squall", bad, "comes after the squall"))
    for name, scene, expect in cases:
        errs = problems(scene)
        assert any(expect in e for e in errs), f"{name}: expected '{expect}', got {errs}"
        print(f"rejects {name}: {next(e for e in errs if expect in e)}")
    first = json.load(open(FIRST_JOB, encoding="utf-8"))
    assert not problems(first), problems(first)
    stop = next(i for i, st in enumerate(first["steps"]) if st["id"] == "stop")
    bad = copy.deepcopy(first); bad["steps"][stop]["expect"]["max_speed"] = 1; errs = problems(bad)
    assert any("unknown field" in e for e in errs), errs
    print(f"rejects a typo'd max_speed_kn: {next(e for e in errs if 'unknown field' in e)}")
    bad = copy.deepcopy(first); bad["steps"][0]["call"]["id"] = "coach.steer"; errs = problems(bad)
    assert any("must start with" in e for e in errs), errs
    print(f"rejects a call id outside captain./instructor.: {next(e for e in errs if 'must start with' in e)}")
    print("self-test ok")


def main(args):
    if args == ["--self-test"]:
        self_test(); return 0
    status = 0
    for path in args or [DEFAULT, FIRST_JOB]:
        try:
            scene = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"{path}: {e}"); status = 1; continue
        errs = problems(scene)
        for e in errs: print(f"{os.path.relpath(path, ROOT)}: {e}")
        if errs: status = 1
        else: print(f"{os.path.relpath(path, ROOT)}: ok, {len(scene['steps'])} steps")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
