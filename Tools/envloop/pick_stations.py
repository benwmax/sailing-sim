"""Fix the ten shore stations for the shore, grass and buildings plan (docs/env-loop/README.md, Track 0).

    python3 Tools/envloop/pick_stations.py            # writes Tools/envloop/stations.json and stations.csv

A station is one piece of shore (its subject point on the waterline and the direction straight out to the lake) seen
from a boat at three distances: 5 m (the hold distance), 15 m (the design distance) and 60 m (the near band). Eight of
the ten start from the PC's "before" stills of 16 Nov (inputs branch, Inputs/bench/env-before-nov16/args.csv): their
camera and bearing find the bank, then the bank's own normal sets the cameras. Two are found by rule from the bakes
(a second residential street, a natural clay cut bank). Run once; after that the stations are fixed so every before and
after picture is taken from the same place. Re-running on the same bakes gives the same answer.

Each camera is checked: over water, with open water all the way to the bank, not inside a map dock or one of the
generated boathouses (lake.py mirrors HouseKit's rule), and the boat (put 35 m further out, behind the camera) is
afloat. The CSV is capture-scenes.sh's format: SCENES=Tools/envloop/stations.csv OUT=<dir> scripts/capture-scenes.sh 8
"""
import csv
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lake import Lake, hash01  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = (5, 15, 60)
EYE = 2.0                                  # the Drone preset's eye above the water (the PC's before set used 2 m)
PITCH = {5: -6.0, 15: -2.0, 60: 0.0}
BOAT_BEHIND = 35.0                         # the boat sits this far behind the camera, out of frame
COMMON = ("-SailingWorld=Lake -SailingLakeLevel=pool -SailingDate=2026-06-15 -SailingHour=15 -SailingWeather=AfternoonBreeze "
          "-SailingWind=8 -SailingKeepStart -SailingCaptureAbsolute -SailingNoHud -SailingNoGpuSlices")

# Seeds from the PC's before set: camera map position (start + CamWorld) and its bearing.
SEEDS = [
    ("club-lawn", "Club lawn", "01-clubhouse", (85 - 3, -40 + 40), 95,
     "Rush Creek clubhouse, its lawn and the bank in front of it, looking east"),
    ("club-beach", "Club beach (low bank north of the club)", "07-natural-bank", (118 + 7, -48 + 40), 80,
     "The low bank north of the club: lawn running down to a sand strip, the club's 1 km first"),
    ("breakwater", "Club breakwater", "02-riprap", (-48 + 4, 5 + 40), 85,
     "The breakwater's lake face (the rock kit, merged 13 Nov)"),
    ("residential-a", "Residential street A (Rowlett)", "03-residential", (8752 - 40, 2115), 180,
     "A row of lakefront lots: houses, lawns, fences, bulkheads, the October audit's spot"),
    ("bulkhead", "Bulkhead lot", "04-house-bulkhead", (8705 - 34, 2065), 180,
     "One lot's concrete bulkhead with its boathouse and lift"),
    ("private-dock", "Private dock", "05-dock", (8175 + 5, 1625 + 35), 145,
     "A mapped private pier (OSM) off the Rowlett shore, seen from its side, 25 degrees off square, with the bank and houses behind"),
    ("wooded", "Wooded bank", "06-wooded", (2466 + 14, -3656 - 38), 290,
     "The audit's wooded spit: trees and understory to the water"),
    ("bridge", "Bridge shore (I-30 west landfall)", "08-bridge", (7175 + 30, 815 - 25), 320,
     "The bank under the I-30 deck: piers, riprap and the shade under the bridge"),
]


def bearing(v):
    return (math.degrees(math.atan2(v[1], v[0])) + 360.0) % 360.0


class Picker:
    def __init__(self):
        self.lake = Lake()
        self.lots = [lt for lt in (self.lake.lot(k) for k, h in enumerate(self.lake.houses) if h["full"]) if lt and lt["bank"]]
        self.slips = [(lt["slip"], lt["water"]) for lt in self.lots if lt["boathouse"]]

    def normal_at(self, s, r=20.0):
        """Unit vector from the land toward the water round point s (centroids of each within r)."""
        g = np.arange(-r, r + 0.5, 1.0)
        X, Y = np.meshgrid(s[0] + g, s[1] + g, indexing="ij")
        inside = (X - s[0]) ** 2 + (Y - s[1]) ** 2 <= r * r
        h = self.lake.height_at(X, Y)
        wet = (h < -0.05) & inside
        dry = (h >= -0.05) & inside
        if wet.sum() < 10 or dry.sum() < 10:
            return None
        v = np.array([X[wet].mean() - X[dry].mean(), Y[wet].mean() - Y[dry].mean()])
        return v / np.linalg.norm(v)

    def waterline(self, p, n, back=30.0):
        """Walk from the land side along n; return the last dry point before the water (the bank's foot)."""
        last = None
        for t in np.arange(-back, back, 0.25):
            q = (p[0] + n[0] * t, p[1] + n[1] * t)
            if self.lake.height_at(*q) < -0.05:
                if last is not None:
                    return q
            else:
                last = q
        return None

    def subject_from_camera(self, cam, brg):
        d = (math.cos(math.radians(brg)), math.sin(math.radians(brg)))
        for t in np.arange(0.0, 150.0, 0.5):
            q = (cam[0] + d[0] * t, cam[1] + d[1] * t)
            if self.lake.height_at(*q) >= -0.05:
                return q
        return None

    def check_camera(self, cam, s, n):
        lk = self.lake
        problems = []
        if lk.height_at(*cam) > -0.3:
            problems.append("camera not over water (%.2f m)" % lk.height_at(*cam))
        dist = math.hypot(s[0] - cam[0], s[1] - cam[1])
        for t in np.arange(0.0, max(dist - 1.0, 0.0), 0.5):
            q = (cam[0] - n[0] * t, cam[1] - n[1] * t)
            if lk.height_at(*q) > -0.05:
                problems.append("land between the camera and the bank at %.1f m" % t)
                break
        for dk in lk.docks:
            for a, b in zip(dk["points"], dk["points"][1:]):
                if _seg_dist(cam, a, b) < 4.0:
                    problems.append("within 4 m of map dock %s" % dk["id"])
                    break
        for sp, w in self.slips:
            # the boathouse runs 0.6..15.4 m out from its slip point, about 4 m each side
            rel = (cam[0] - sp[0], cam[1] - sp[1])
            along = rel[0] * w[0] + rel[1] * w[1]
            acr = abs(-rel[0] * w[1] + rel[1] * w[0])
            if -1.0 < along < 17.0 and acr < 5.5:
                problems.append("inside a generated boathouse (slip %.0f, %.0f)" % sp)
        for row in lk.marina.get("rows", []) + lk.marina.get("piers", []):
            for a, b in zip(row["points"], row["points"][1:]):
                if _seg_dist(cam, a, b) < 0.5 * row.get("width", 2.0) + row.get("finger_length", 0.0) + 2.0:
                    problems.append("inside the club's docks (%s)" % row["id"])
                    break
        return problems

    def station(self, sid, name, s, n, why, source=None, extra=None):
        lk = self.lake
        cams = []
        for d in DIST:
            cam = (s[0] + n[0] * d, s[1] + n[1] * d)
            boat = (s[0] + n[0] * (d + BOAT_BEHIND), s[1] + n[1] * (d + BOAT_BEHIND))
            look = bearing((-n[0], -n[1]))
            probs = self.check_camera(cam, s, n)
            if lk.height_at(*boat) > -1.0:
                probs.append("boat start in water under 1 m (%.2f m)" % lk.height_at(*boat))
            rel = (cam[0] - boat[0], cam[1] - boat[1])
            cams.append(dict(
                scene="env-%s-%02dm" % (sid, d), distance_m=d, camera_map=[round(cam[0], 1), round(cam[1], 1)],
                eye_m=EYE, bearing_deg=round(look, 1), pitch_deg=PITCH[d], boat_map=[round(boat[0], 1), round(boat[1], 1)],
                water_depth_m=round(float(-lk.height_at(*cam)), 2),
                args="%s -SailingStartAt=%.1f,%.1f,%.1f -SailingCamWorld=%.1f,%.1f,%.1f,%.1f,%.1f" % (
                    COMMON, boat[0], boat[1], look, rel[0], rel[1], EYE, look, PITCH[d]),
                problems=probs))
        houses = lk.houses_near(s[0], s[1], 150.0)
        banks = {}
        for k in houses:
            lt = lk.lot(k)
            if lt and lt["bank"]:
                banks[lt["bank"]] = banks.get(lt["bank"], 0) + 1
        rise = float(lk.height_at(s[0] - n[0] * 8.0, s[1] - n[1] * 8.0))
        return dict(id=sid, name=name, why=why, subject_map=[round(s[0], 1), round(s[1], 1)], out_to_lake=[round(n[0], 3), round(n[1], 3)],
                    bank_rise_8m=round(rise, 2), houses_150m=len(houses), lot_banks_150m=banks,
                    crowns_60m=lk.crowns_near(s[0], s[1], 60.0), before_still=source, cameras=cams, **(extra or {}))

    def from_seed(self, sid, name, src, cam, brg, why):
        s0 = self.subject_from_camera(cam, brg)
        n = self.normal_at(s0)
        s = self.waterline(s0, n) or s0
        n = self.normal_at(s) if self.normal_at(s) is not None else n
        if sid == "breakwater":
            # the rocks are not terrain: the toe stones reach about 5.5 m off the breakwater's centreline
            # (RayHubbard.marina.json, docs/shore-loop/README.md), so distances count from there
            bw = self.lake.marina["breakwaters"][0]
            a, b = bw["points"][0], bw["points"][1]
            t = (b[0] - a[0], b[1] - a[1])
            L = math.hypot(*t)
            out = (-t[1] / L, t[0] / L)
            if out[0] * n[0] + out[1] * n[1] < 0:
                out = (-out[0], -out[1])
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            s, n = (m[0] + out[0] * 5.5, m[1] + out[1] * 5.5), out
        if sid == "private-dock":
            # the subject is the mapped pier itself (its longest run's middle), seen from whichever side has open water,
            # 25 degrees off square toward the pier's head: straight out from the bank the pier would run at the camera
            dk = min(self.lake.docks, key=lambda d: min(_seg_dist(cam, a, b) for a, b in zip(d["points"], d["points"][1:])))
            a, b = max(zip(dk["points"], dk["points"][1:]), key=lambda ab: math.hypot(ab[1][0] - ab[0][0], ab[1][1] - ab[0][1]))
            s = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            t = (b[0] - a[0], b[1] - a[1])
            L = math.hypot(*t)
            t = (t[0] / L, t[1] / L)
            head = a if self.lake.height_at(*a) < self.lake.height_at(*b) else b    # the pier's lake end
            if t[0] * (head[0] - s[0]) + t[1] * (head[1] - s[1]) < 0:
                t = (-t[0], -t[1])
            a25 = math.radians(25.0)
            src_path = "Inputs/bench/env-before-nov16/%s.jpg (inputs branch)" % src
            st = None
            for side in (1.0, -1.0):   # whichever side has open water out to the 60 m camera
                perp = (-t[1] * side, t[0] * side)
                n = (perp[0] * math.cos(a25) + t[0] * math.sin(a25), perp[1] * math.cos(a25) + t[1] * math.sin(a25))
                st = self.station(sid, name, s, n, why, source=src_path, extra=dict(dock_id=dk["id"], distances_from="the pier's centreline"))
                if not any(c["problems"] for c in st["cameras"]):
                    break
            return st
        st = self.station(sid, name, s, n, why, source="Inputs/bench/env-before-nov16/%s.jpg (inputs branch)" % src)
        # a bank that bends: if a camera fails, try turning the line out by up to 30 degrees either way
        if any(c["problems"] for c in st["cameras"]):
            for turn in (10, -10, 20, -20, 30, -30):
                a = math.radians(turn)
                n2 = (n[0] * math.cos(a) - n[1] * math.sin(a), n[0] * math.sin(a) + n[1] * math.cos(a))
                st2 = self.station(sid, name, s, n2, why, source=st["before_still"], extra=dict(turned_deg=turn))
                if not any(c["problems"] for c in st2["cameras"]):
                    return st2
        return st

    def residential_b(self, avoid):
        """A second residential street: the stretch with the most banked lots within 120 m, at least 2 km from
        street A, preferring a mix of bank types and wall finishes (so it shows what A doesn't)."""
        lots = [lt for lt in self.lots if lt["line"]]
        mid = np.array([lt["line"][len(lt["line"]) // 2] for lt in lots])
        ranked = []
        for i, lt in enumerate(lots):
            c = mid[i]
            if math.hypot(c[0] - avoid[0], c[1] - avoid[1]) < 2000.0 or lt["boathouse"]:
                continue
            near = [lots[j] for j in np.nonzero(np.hypot(mid[:, 0] - c[0], mid[:, 1] - c[1]) < 60.0)[0]]
            score = len(near) + 2 * len({o["bank"] for o in near}) + 2 * len({o["wall"] for o in near})
            ranked.append((score, -i, lt, len(near)))
        ranked.sort(reverse=True)
        for score, _, lt, nn in ranked[:60]:
            s = tuple(lt["line"][len(lt["line"]) // 2])
            n = self.normal_at(s)
            if n is None:
                continue
            st = self.station("residential-b", "Residential street B", self.waterline(s, n) or s, n,
                              "A second street of lakefront lots with mixed banks and wall finishes, %d lots within 60 m" % nn,
                              extra=dict(found_by="rule: most banked lots within 60 m (mixed banks and walls scored up), 2 km or more "
                                                  "from street A, the subject lot without a boathouse, all three cameras clear"))
            if not any(c["problems"] for c in st["cameras"]):
                return st
        return None

    def clay_bank(self):
        """A natural clay cut bank: no houses within 150 m, the ground 1.5 m or more above the pool within 6 m of the
        water (a cut face, not a beach), few trees on the face; nearest the club first (the club's 1 km comes first)."""
        lk = self.lake
        found = []
        for r in np.arange(200.0, 12000.0, 50.0):
            for a in np.arange(0.0, 360.0, 360.0 / max(12, int(2 * math.pi * r / 40.0))):
                p = (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
                h = lk.height_at(*p)
                if not (-0.05 <= h < 0.4):
                    continue
                n = self.normal_at(p, 12.0)
                if n is None:
                    continue
                s = self.waterline(p, n, 12.0)
                if s is None:
                    continue
                if lk.height_at(s[0] - n[0] * 6.0, s[1] - n[1] * 6.0) < 1.5:
                    continue
                # mainland, not a spit or an island: still dry 30 and 80 m inland, and not the dam's embankment
                # (the dam's crest stands about 10 m over the pool)
                inland = [float(lk.height_at(s[0] - n[0] * t, s[1] - n[1] * t)) for t in (15.0, 30.0, 60.0)]
                if min(inland) < 0.5 or max(inland) > 15.0:
                    continue
                if lk.houses_near(s[0], s[1], 100.0) or lk.crowns_near(s[0], s[1], 12.0) > 3:
                    continue
                if lk.height_at(s[0] + n[0] * 60.0, s[1] + n[1] * 60.0) > -0.5:
                    continue
                st = self.station("clay-bank", "Natural clay cut bank", s, n,
                                  "A bare cut bank with no lots near: the shore types (Track C) and the ground (Track A) at their rawest",
                                  extra=dict(found_by="rule: nearest the club with 1.5 m of rise within 6 m of the water, dry 15 to 60 m inland (mainland, not the dam), no houses within 100 m, three crowns or fewer within 12 m"))
                if not any(c["problems"] for c in st["cameras"]):
                    found.append(st)
                    return st
        return None


def _seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def main():
    pk = Picker()
    stations = [pk.from_seed(*s) for s in SEEDS]
    a = next(s for s in stations if s["id"] == "residential-a")
    stations.insert(4, pk.residential_b(a["subject_map"]))
    cb = pk.clay_bank()
    if cb:
        stations.insert(8, cb)
    out = dict(note="Fixed shore stations (docs/env-loop/README.md). Map metres from Rush Creek YC, +north +east; "
                    "bearings are compass; eye above the water. Generated by pick_stations.py; do not edit by hand.",
               distances_m=list(DIST), common_args=COMMON, stations=stations)
    json.dump(out, open(os.path.join(HERE, "stations.json"), "w"), indent=1)
    with open(os.path.join(HERE, "stations.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scene", "reference_id", "url", "seconds", "preset", "args", "description"])
        for st in stations:
            for c in st["cameras"]:
                w.writerow([c["scene"], "ENV-%s" % st["id"].upper(), "", 8, "Drone", c["args"],
                            "%s from %d m: %s" % (st["name"], c["distance_m"], st["why"])])
    bad = 0
    for st in stations:
        probs = [p for c in st["cameras"] for p in c["problems"]]
        bad += bool(probs)
        print("%-14s subject %9.1f %8.1f  out %5.0f deg  rise %5.2f  houses %3d  crowns %3d  %s" % (
            st["id"], st["subject_map"][0], st["subject_map"][1], bearing(st["out_to_lake"]), st["bank_rise_8m"],
            st["houses_150m"], st["crowns_60m"], "; ".join(sorted(set(probs))) or "ok"))
    print("%d stations, %d cameras -> stations.json, stations.csv%s" % (len(stations), 3 * len(stations),
                                                                    "" if not bad else " (%d with problems)" % bad))


if __name__ == "__main__":
    main()
