"""The frigate Commonwealth's estimated polar (docs/frigate-physics): what a heavy frigate of 1797 made through the water
by the period's logs and accounts, as a table the trial (trial/trial_sail.cpp) and later the reference polar are held to.

No VPP or tank data exists for these ships, so each number is read from the accounts below, with their spread as the
tolerance. Usage: python polar_commonwealth.py [out json] (prints the table; writes polar_commonwealth.json beside it by
default); python polar_commonwealth.py --compare <trial.json> holds a trial (trial/trial.sh) to it.

Sources (speeds in knots through the water; log-line speeds read about a tenth high, so the table takes 0.9 of them):
- Constitution: "13 knots and more" large (NHHC); 13.5 in her logs; 11 kn close to the wind in the chase of July 1812
  in a moderate breeze, with every sail set and wetted.
- Endymion (40, 1797): 14.4 kn large, about 11 close-hauled, the fastest frigate of her day.
- Leda class (38): 13 large, 10 close-hauled; Aigle class: 10 close-hauled under topgallants, 12 quartering.
- Robert Gardiner, Frigates of the Napoleonic Wars: by 1800 a good frigate made 13 kn quartering and 10 or more
  close-hauled in a fresh breeze (log speeds).
- Hermione (the 2014 replica of a 1779 French frigate): 65-75% of the wind's speed on a beam reach, 13.3 kn at most.
- A square-rigger sails no closer than about 6 points (67.5 deg) of the true wind, with the leeway on top.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

WINDS = [8.0, 12.0, 16.0, 20.0, 24.0]
# Each angle's speeds by wind. The light winds from Hermione's share of the wind; the strong winds held by her hull
# (a 52 m waterline: Froude 0.30 is 13.2 kn, where her wave resistance climbs steeply) and by the sail she carried
# (topgallants in by about 20 kn close-hauled, single reefs by 24).
SPEEDS = {
    67.5: [3.8, 5.8, 7.4, 8.6, 8.8],     # close-hauled, 6 points: 0.9 x the logs' 10-11 in a fresh breeze
    80.0: [4.6, 7.0, 8.9, 10.2, 10.6],
    90.0: [5.3, 7.9, 10.0, 11.4, 11.9],  # Hermione's 0.65-0.7 of the wind
    110.0: [5.6, 8.3, 10.6, 12.0, 12.6],
    135.0: [5.4, 8.1, 10.6, 12.2, 13.0], # quartering, her best: 0.9 x the logs' 13-14.4 large
    160.0: [4.8, 7.3, 9.6, 11.2, 12.2],  # the after sails blanket the fore
    180.0: [4.2, 6.5, 8.7, 10.3, 11.4],  # dead before it: only the fore and main square sails draw
}
# The tolerance: the spread of the accounts (a fifth), wider in light air where the logs say least.
TOLERANCE = {8.0: 0.25, 12.0: 0.20, 16.0: 0.20, 20.0: 0.20, 24.0: 0.20}


def table():
    rows = []
    for twa, speeds in SPEEDS.items():
        for tws, v in zip(WINDS, speeds):
            rows.append({"tws": tws, "twa": twa, "speed": v, "tolerance": TOLERANCE[tws]})
    return rows


def expected(tws, twa):
    """The table at a wind and angle, linear between its rows (its angles), clamped to its ends."""
    angles = sorted(SPEEDS)
    i = WINDS.index(tws)
    if twa <= angles[0]:
        return SPEEDS[angles[0]][i]
    for a, b in zip(angles, angles[1:]):
        if twa <= b:
            t = (twa - a) / (b - a)
            return SPEEDS[a][i] + t * (SPEEDS[b][i] - SPEEDS[a][i])
    return SPEEDS[angles[-1]][i]


def compare(trial_path):
    """Each trial point against the table at the angle she sailed; a point outside its tolerance is marked."""
    trial = json.load(open(trial_path))
    worst, out = 0.0, 0
    for p in trial["points"]:
        twa = abs(p["twa_sailed"]) if abs(p["twa"]) < 179 else 180.0
        e = expected(p["tws"], twa)
        d = p["speed"] / e - 1.0
        bad = abs(d) > TOLERANCE[p["tws"]]
        worst = max(worst, abs(d))
        out += bad
        print(f"TWS {p['tws']:4.0f} TWA {twa:5.1f}: {p['speed']:5.2f} kn, estimate {e:5.2f} ({100 * d:+5.1f}%), heel {p['heel']:4.1f}, "
              f"{p['plan']}{'  OUTSIDE' if bad else ''}")
    print(f"{out} of {len(trial['points'])} points outside tolerance, worst {100 * worst:.1f}%")
    return out


def main(out):
    rows = table()
    print("TWA    " + "".join(f"{w:7.0f}" for w in WINDS))
    for twa, speeds in SPEEDS.items():
        print(f"{twa:5.1f}  " + "".join(f"{v:7.1f}" for v in speeds))
    doc = {"about": __doc__.strip().splitlines()[0], "winds_kn": WINDS, "points": rows}
    with open(out, "w") as f:
        json.dump(doc, f, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--compare":
        sys.exit(1 if compare(sys.argv[2]) else 0)
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "polar_commonwealth.json"))
