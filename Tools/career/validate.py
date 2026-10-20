"""Checks the career data (Content/Career/career.json, docs/career/README.md): structure, unique ids, worlds and boats
the save knows, lessons that name a drill and a quiz in Content/Learning, medal rules that only get stricter from
bronze to gold, checkrides over the tier's own lessons, unlocks that name real tiers, and every tier reachable.

Usage: python3 Tools/career/validate.py [repo root]   (defaults to two folders up)
Exits non-zero on any problem. SailingSim.Career.Content checks the same file in the game.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..")

WORLDS = {"ray-hubbard", "galveston-bay", "gulf", "marseille", "texas-coast"}   # FSailSave::WorldId
MEDALS = ["bronze", "silver", "gold"]
CRITERIA = {"outcomes", "max_seconds", "max_contact_kn", "max_collisions", "max_infractions"}
STATUS = {"ready", "stub"}

errors = []
def check(cond, msg):
    if not cond: errors.append(msg)

def boat_ids():
    src = open(os.path.join(ROOT, "Source", "SailingSim", "Private", "SailSave.cpp"), encoding="utf-8").read()
    m = re.search(r"BoatIds\[\] = \{(.*?)\};", src, re.S)
    return set(re.findall(r'TEXT\("([^"]+)"\)', m.group(1))) if m else set()

BOATS = boat_ids()
check(BOATS, "could not read the boat ids from SailSave.cpp")

learning = os.path.join(ROOT, "Content", "Learning")
briefings = {d["id"]: d for d in json.load(open(os.path.join(learning, "drill-briefings.json"), encoding="utf-8"))["drills"]}
questions = json.load(open(os.path.join(learning, "quiz-bank.json"), encoding="utf-8"))["questions"]

c = json.load(open(os.path.join(ROOT, "Content", "Career", "career.json"), encoding="utf-8"))
check(c.get("schema_version") == 1, "schema_version must be 1")
check(c.get("medals") == MEDALS, f"medals must be {MEDALS}")
check(c.get("easy_max_medal", "gold") in MEDALS, f"easy_max_medal must be one of {MEDALS}")
tiers = c.get("tiers", [])
tier_ids = [t.get("id") for t in tiers]
check(len(set(tier_ids)) == len(tier_ids), f"tier ids repeat: {tier_ids}")

def criteria(where, crit, outcomes):
    for k in crit:
        check(k in CRITERIA, f"{where}: unknown rule {k}")
    for o in crit.get("outcomes", []):
        check(o in outcomes, f"{where}: outcome {o} is not one of the drill's {sorted(outcomes)}")

def stricter(where, hi, lo):
    """hi (the better medal) must ask at least what lo asks."""
    if lo.get("outcomes"):
        check(set(hi.get("outcomes", [])) and set(hi.get("outcomes", [])) <= set(lo["outcomes"]), f"{where}: outcomes looser than the medal below")
    for k in ("max_seconds", "max_contact_kn", "max_collisions", "max_infractions"):
        if k in lo:
            check(k in hi and hi[k] <= lo[k], f"{where}: {k} looser than the medal below")

ao = c.get("always_open", {})
for t in ao.get("tiers", []): check(t in tier_ids, f"always_open: unknown tier {t}")
for w in ao.get("worlds", []): check(w in WORLDS, f"always_open: unknown world {w}")
for b in ao.get("boats", []): check(b in BOATS, f"always_open: unknown boat {b}")

lesson_ids, cert_ids = set(), set()
for t in tiers:
    tid = t.get("id", "?")
    for f in ("name", "status", "summary", "world", "boats", "lessons", "checkride", "certificate", "unlocks"):
        check(f in t, f"{tid}: missing {f}")
    check(t.get("status") in STATUS, f"{tid}: status must be one of {sorted(STATUS)}")
    check(t.get("world") in WORLDS, f"{tid}: unknown world {t.get('world')}")
    for b in t.get("boats", []): check(b in BOATS, f"{tid}: unknown boat {b}")
    check("ASA" not in t.get("name", "") + t.get("summary", "") + t.get("certificate", {}).get("name", ""),
          f"{tid}: ASA belongs in the learning text only")
    if t.get("status") == "ready": check(len(t.get("lessons", [])) > 0, f"{tid}: a ready tier needs lessons")
    mine = set()
    for l in t.get("lessons", []):
        lid = l.get("id", "?")
        check(lid.startswith(tid + "."), f"{lid}: lesson ids start with the tier id")
        check(lid not in lesson_ids, f"{lid}: repeated lesson id")
        lesson_ids.add(lid); mine.add(lid)
        for f in ("title", "drill", "quiz", "quiz_pass", "medals"):
            check(f in l, f"{lid}: missing {f}")
        b = briefings.get(l.get("drill"))
        check(b is not None, f"{lid}: drill {l.get('drill')} is not in Content/Learning")
        q = briefings.get(l.get("quiz"))
        check(q is not None and q.get("quiz_after", 0) > 0, f"{lid}: quiz {l.get('quiz')} has no quiz in Content/Learning")
        check(0.0 < l.get("quiz_pass", 0) <= 1.0, f"{lid}: quiz_pass must be in (0, 1]")
        outcomes = set(b["debrief"].keys()) if b else set()
        m = l.get("medals", {})
        check(list(m.keys()) == MEDALS, f"{lid}: medals must be {MEDALS} in that order")
        for name in MEDALS: criteria(f"{lid} {name}", m.get(name, {}), outcomes)
        if all(n in m for n in MEDALS):
            stricter(f"{lid} silver", m["silver"], m["bronze"])
            stricter(f"{lid} gold", m["gold"], m["silver"])
    cr = t.get("checkride", {})
    check(cr.get("id") == tid + ".checkride", f"{tid}: checkride id must be {tid}.checkride")
    for lid in cr.get("lessons", []): check(lid in mine, f"{tid} checkride: {lid} is not one of the tier's lessons")
    check(cr.get("min_medal") in MEDALS, f"{tid} checkride: min_medal must be a medal")
    if t.get("status") == "ready":
        check(set(cr.get("lessons", [])) == mine, f"{tid} checkride: should cover every lesson of the tier")
        qz = cr.get("quiz")
        check(isinstance(qz, dict), f"{tid} checkride: a ready tier needs a quiz")
        if isinstance(qz, dict):
            for d in qz.get("drills", []): check(d in briefings, f"{tid} checkride quiz: unknown drill {d}")
            avail = sum(1 for x in questions if any(d in x["drills"] for d in qz.get("drills", [])) or "Any" in x["drills"])
            check(0 < qz.get("questions", 0) <= avail, f"{tid} checkride quiz: {qz.get('questions')} questions but {avail} available")
            check(0.0 < qz.get("pass", 0) <= 1.0, f"{tid} checkride quiz: pass must be in (0, 1]")
    cert = t.get("certificate", {})
    check(cert.get("id") and cert.get("name"), f"{tid}: certificate needs id and name")
    check(cert.get("id") not in cert_ids, f"{tid}: repeated certificate id")
    cert_ids.add(cert.get("id"))
    u = t.get("unlocks", {})
    for x in u.get("tiers", []): check(x in tier_ids and x != tid, f"{tid} unlocks: unknown tier {x}")
    for w in u.get("worlds", []): check(w in WORLDS, f"{tid} unlocks: unknown world {w}")
    for b in u.get("boats", []): check(b in BOATS, f"{tid} unlocks: unknown boat {b}")

# Every tier reachable from the always-open ones through certificates.
reach, todo = set(ao.get("tiers", [])), list(ao.get("tiers", []))
by_id = {t["id"]: t for t in tiers if "id" in t}
while todo:
    for x in by_id.get(todo.pop(), {}).get("unlocks", {}).get("tiers", []):
        if x not in reach: reach.add(x); todo.append(x)
for t in tier_ids: check(t in reach, f"{t}: no certificate unlocks it")

if errors:
    print("\n".join(errors))
    sys.exit(1)
ready = [t["id"] for t in tiers if t.get("status") == "ready"]
print(f"career.json ok: {len(tiers)} tiers ({', '.join(ready)} ready), {len(lesson_ids)} lessons, {len(BOATS)} boat ids")
