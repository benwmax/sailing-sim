"""Environment loop checks for Tracks F and H (shore plan step 6, the parts that need no game): every built mesh against
its card. Until Track 0's shared checks land.

  1 size     the bounding box within the card's tolerance (5%) of `expect` (x, y and z when given)
  2 budget   triangles under `tris_max`
  3 slots    every material slot is a WORLD_SLOTS look or one of shorekit.NEW_SLOTS (listed for Track I)
  4 variety  at least 6 dock layouts, 3 boathouses and 30 yard props (the plan's counts)
  5 sockets  the card's sockets exist on the mesh
  6 cards    every mesh has a card and every card a mesh
Colour against grey-card photos, repeat in a 40 m frame and the blind review are judged on renders (README).

Usage: python3 Tools/envloop/docks/checks.py <manifest.json> <cards.json> [<manifest> <cards> ...]   (exit 1 on a failure)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN = {"Bark", "Leaves", "Crown", "Rock", "Paint", "Glass", "Tyre", "HeadLight", "TailLight", "Trailer", "Dark", "Steel",
         "Wood", "Lantern", "Reflective", "ContainerPaint", "Trim", "FarWeed", "Reed", "ReedHead", "Door", "Decking", "White",
         "Concrete", "Roof", "Gelcoat", "Antifouling", "TrimGreen", "Deck", "Cushion", "Net", "Barge", "Cargo", "Pilothouse",
         "Funnel", "ShipHull", "Lifeboat", "AviationRed", "Limestone", "StoneGreen", "RoofTile", "Gold", "LampGlow",
         "SafetyRed", "Floats"}
NEW = {"MetalRoof", "Galv", "Canvas", "Plastic", "Vinyl", "Carpet"}   # mirror of shorekit.NEW_SLOTS (no bpy here)
VARIETY = {"SM_ShoreDock_": 6, "SM_Boathouse_": 3, "SM_Yard_": 30}


def check(man, cards, out):
    fails = 0
    tol = cards.get("_tol", 0.05)
    for name, st in sorted(man.items()):
        card = cards.get(name)
        if not card:
            out.append(f"FAIL cards   {name}: no card")
            fails += 1
            continue
        exp = card["expect"]
        bad = []
        for i, e in enumerate(exp):
            got = st["size"][i]
            if abs(got - e) > tol * e + 0.005:
                bad.append(f"{'xyz'[i]} {got:.2f} vs {e:.2f}")
        line = f"{'FAIL' if bad else 'ok  '} size     {name}: " + (", ".join(bad) if bad else " x ".join(f"{s:.2f}" for s in st["size"][:len(exp)]))
        out.append(line)
        fails += bool(bad)
        if st["tris"] > card["tris_max"]:
            out.append(f"FAIL budget   {name}: {st['tris']} tris > {card['tris_max']}")
            fails += 1
        else:
            out.append(f"ok   budget   {name}: {st['tris']} / {card['tris_max']}")
        odd = [s for s in st["slots"] if s not in KNOWN and s not in NEW]
        if odd:
            out.append(f"FAIL slots    {name}: unknown {odd}")
            fails += 1
        for s in card.get("sockets", []):
            if s not in st.get("sockets", {}):
                out.append(f"FAIL sockets  {name}: missing {s}")
                fails += 1
    for name in cards:
        if not name.startswith("_") and name not in man:
            out.append(f"FAIL cards   {name}: card but no mesh")
            fails += 1
    return fails


def main():
    a = sys.argv[1:]
    fails = 0
    out = []
    names = []
    for mp, cp in zip(a[0::2], a[1::2]):
        with open(mp) as f:
            man = json.load(f)
        with open(cp) as f:
            cards = json.load(f)
        names += list(man)
        fails += check(man, cards, out)
    for prefix, n in VARIETY.items():
        have = sum(1 for k in names if k.startswith(prefix))
        if any(k.startswith(prefix) for k in names):
            ok = have >= n
            out.append(f"{'ok  ' if ok else 'FAIL'} variety  {prefix}*: {have} (need {n})")
            fails += not ok
    new_used = sorted({s for mp in a[0::2] for st in json.load(open(mp)).values() for s in st["slots"] if s in NEW})
    out.append(f"note slots    new looks for Track I: {', '.join(new_used)}")
    print("\n".join(out))
    print(f"{fails} failure(s)")
    sys.exit(1 if fails else 0)


main()
