"""Checks the drill learning content: structure, ids, references between the files, key tokens, and that each
briefing's steps still match FDrillRunner's steps in Source/SailingSim/Private/Drills.cpp.

Usage: python3 validate.py [repo root]   (defaults to two folders up, so it works from Inputs/drills)
Exits non-zero on any problem.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..")

DRILLS = ["LeaveTheDock", "SailATriangle", "HeaveTo", "CrewOverboardFigureEight", "CrewOverboardQuickStop", "ReturnAndDock"]
TOPICS = {"parts", "sail", "trim", "rules", "lights", "aton", "nav", "knots", "safety", "weather", "dock"}
LEVELS = {"info", "good", "warn", "danger"}
KEYS = {"DockLines", "BackJib", "JibSheet.trim", "JibSheet.ease", "MainSheet.trim", "MainSheet.ease", "Hike.out", "ToggleLearning"}

errors = []
def check(cond, msg):
    if not cond: errors.append(msg)

def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        d = json.load(f)
    check(d.get("schema_version") == 1, f"{name}: schema_version must be 1")
    return d

def tokens(text, where):
    for t in re.findall(r"\{key:([^}]*)\}", text):
        check(t in KEYS, f"{where}: unknown key token {{key:{t}}}")

b = load("drill-briefings.json")
t = load("learning-tips.json")
q = load("quiz-bank.json")

# Briefings
ids = [d["id"] for d in b["drills"]]
check(ids == DRILLS, f"drill-briefings: drills must be {DRILLS} in that order, got {ids}")
for d in b["drills"]:
    for f in ("name", "asa_skill", "goal", "why_it_matters", "setup", "commands", "steps", "good", "mistakes", "lake_notes", "debrief", "quiz_after"):
        check(f in d, f"{d['id']}: missing {f}")
    for i, s in enumerate(d["steps"]):
        check(s.get("sim_text") and s.get("coach"), f"{d['id']} step {i}: needs sim_text and coach")
        tokens(s.get("text", ""), f"{d['id']} step {i}")
    n = sum(1 for x in q["questions"] if d["id"] in x["drills"] or "Any" in x["drills"])
    check(d["quiz_after"] <= n, f"{d['id']}: quiz_after {d['quiz_after']} but only {n} questions")

# Steps against Drills.cpp
cpp = os.path.join(ROOT, "Source", "SailingSim", "Private", "Drills.cpp")
if os.path.exists(cpp):
    src = open(cpp, encoding="utf-8").read()
    start = src[src.index("void FDrillRunner::Start"):src.index("bool FDrillRunner::Update")]
    def steps_in(block):
        m = re.search(r"Steps = \{(.*?)\};", block, re.S)
        return [bytes(s, "utf-8").decode("unicode_escape") for s in re.findall(r'TEXT\("((?:[^"\\]|\\.)*)"\)', m.group(1))] if m else []
    for d in b["drills"]:
        m = re.search(r"case ESailingDrill::" + d["id"] + r":(.*?)(?=case ESailingDrill::|default:)", start, re.S)
        block = m.group(1) if m else ""
        if d["id"].startswith("CrewOverboard"):
            parts = re.split(r"\belse\b", start[start.index("case ESailingDrill::CrewOverboardFigureEight"):start.index("case ESailingDrill::ReturnAndDock")])
            block = parts[0] if d["id"].endswith("FigureEight") else parts[1]
        code = steps_in(block)
        mine = [s["sim_text"] for s in d["steps"]]
        check(code == mine, f"{d['id']}: steps differ from Drills.cpp\n  code: {code}\n  json: {mine}")
else:
    print(f"note: {cpp} not found, step check skipped")

# Tips
events = t["events"]
seen = set()
for x in t["tips"]:
    check(x["id"] not in seen, f"tip {x['id']}: duplicate id"); seen.add(x["id"])
    check(x["event"] in events, f"tip {x['id']}: unknown event {x['event']}")
    check(x["level"] in LEVELS, f"tip {x['id']}: bad level {x['level']}")
    check(x["asa_topic"] in TOPICS, f"tip {x['id']}: bad topic {x['asa_topic']}")
    check(all(dr in DRILLS or dr == "Any" for dr in x["drills"]), f"tip {x['id']}: bad drill in {x['drills']}")
    check(isinstance(x["cooldown_s"], (int, float)) and x["cooldown_s"] >= 0, f"tip {x['id']}: bad cooldown")
    check(len(x["text"]) <= 240, f"tip {x['id']}: text over 240 characters ({len(x['text'])})")
    tokens(x["text"], f"tip {x['id']}")
unused = set(events) - {x["event"] for x in t["tips"]}
check(not unused, f"learning-tips: events with no tip: {sorted(unused)}")

# Quiz
seen, texts = set(), set()
for x in q["questions"]:
    check(x["id"] not in seen, f"quiz {x['id']}: duplicate id"); seen.add(x["id"])
    check(x["q"] not in texts, f"quiz {x['id']}: duplicate question text"); texts.add(x["q"])
    check(x["topic"] in TOPICS, f"quiz {x['id']}: bad topic")
    check(all(dr in DRILLS or dr == "Any" for dr in x["drills"]), f"quiz {x['id']}: bad drill")
    check(len(x["options"]) == 4 and len(set(x["options"])) == 4, f"quiz {x['id']}: needs 4 distinct options")
    check(isinstance(x["answer"], int) and 0 <= x["answer"] < 4, f"quiz {x['id']}: bad answer index")
    check(x["why"] and len(x["why"]) <= 200, f"quiz {x['id']}: why missing or over 200 characters")
for dr in DRILLS:
    n = sum(1 for x in q["questions"] if dr in x["drills"])
    check(n >= 5, f"quiz: only {n} questions for {dr}")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"ok: {len(b['drills'])} briefings, {len(t['tips'])} tips on {len(events)} events, {len(q['questions'])} questions")
