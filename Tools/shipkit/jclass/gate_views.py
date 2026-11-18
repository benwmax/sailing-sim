"""What each of Bluebonnet's frame-rate gate views should draw (slice 12, docs/jclass-12).

    python gate_views.py <build dir>

Reads gate_views_bluebonnet.json and the build's light.json and build.json; writes <build dir>/gate_views.json. For
each view, every outside part shown in its suit is drawn detailed or as its light twin by Unreal's rule: the part's
screen size there (its bounding sphere's diameter over the screen's height, ComputeBoundsScreenSize with the view's
field of view) against the twin's switch (light.json's ue_screen_size, where the twin's error is within a pixel of
the 4K screen at the part's nearest point in the game's widest view). Below decks (slices 9 and 10) is drawn only in
a view below, all of it detailed. A view's camera is either aboard ("frame": "boat", heeled with her: the wheel, the
masthead, the saloon) or off the boat ("level": a chase camera's, level, turning with her heading), where each part's
centre is first heeled by heel_deg about her centreline (positive: starboard side up, heeled to port). Gives the
triangles drawn, the parts each way, the triangles if every part were detailed, and the camera as the bench's
arguments take it, in the view's own frame: the look direction relative to her bow (0 forward, 90 to starboard), the
pitch (negative down) and the distance to the target. Pure Python, no Blender.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def screen_size(radius, dist, fov_deg, aspect):
    """Unreal's ComputeBoundsScreenSize with the horizontal field of view held (ScreenMultiple = aspect / 2 / tan)."""
    return aspect * radius / (max(dist, 1e-6) * math.tan(math.radians(fov_deg) / 2))


def heeled(c, heel_deg):
    """A point of her frame (X forward, Y starboard, Z up) heeled by heel_deg about her centreline: positive lifts
    the starboard side (heeled to port), so the masthead goes to port."""
    h = math.radians(heel_deg)
    return [c[0], c[1] * math.cos(h) - c[2] * math.sin(h), c[1] * math.sin(h) + c[2] * math.cos(h)]


def view(v, parts, build, fov, aspect):
    eye, tgt = v["eye_m"], v["target_m"]
    d = [t - e for t, e in zip(tgt, eye)]
    dist = math.sqrt(sum(a * a for a in d))
    level = v["frame"] == "level"
    out = {"what": v["what"], "suit": v["suit"], "heel_deg": v["heel_deg"], "frame": v["frame"],
           "camera": {"look_deg": round(math.degrees(math.atan2(d[1], d[0])), 1),
                      "pitch_deg": round(math.degrees(math.asin(d[2] / dist)), 1),
                      "distance_m": round(dist, 1), "fov_deg": fov}}
    drawn = all_hero = 0
    hero, light = [], []
    nearest = math.inf
    for name, p in sorted(parts.items()):
        if v["suit"] not in p["suits"]:
            continue
        c = list(p["centre_m"])
        c[1] = -c[1]                                    # Blender's y is the hull's turned over
        if level:
            c = heeled(c, v["heel_deg"])
        r = math.dist(eye, c)
        nearest = min(nearest, r)
        s = screen_size(p["bounding_radius_m"], r, fov, aspect)
        all_hero += p["hero_triangles"]
        if s < p["ue_screen_size"]:
            drawn += p["light_triangles"]
            light.append(name)
        else:
            drawn += p["hero_triangles"]
            hero.append(name)
    below = 0
    if v.get("below"):
        below = build["triangles_slice_9_below"] + build["triangles_slice_10_below"]
    out.update({"triangles_drawn": drawn + below, "triangles_if_all_detailed": all_hero + below,
                "below_decks_triangles": below, "parts_detailed": hero, "parts_light": light,
                "share_light_parts": round(len(light) / max(1, len(light) + len(hero)), 3)})
    if "with" in v:
        out["with"] = v["with"]
    return out


def main(d):
    spec = json.load(open(os.path.join(HERE, "gate_views_bluebonnet.json")))
    lj = json.load(open(os.path.join(d, "light.json")))
    build = json.load(open(os.path.join(d, "build.json")))
    fov, aspect = spec["fov_deg"], spec["screen"]["aspect"]
    rep = {"fov_deg": fov, "views": {v["name"]: view(v, lj["parts"], build, fov, aspect) for v in spec["views"]}}
    with open(os.path.join(d, "gate_views.json"), "w") as f:
        json.dump(rep, f, indent=1)
    return rep


if __name__ == "__main__":
    r = main(os.path.abspath(sys.argv[1]))
    for k, v in r["views"].items():
        print(f"{k:22s} drawn {v['triangles_drawn']:9,d} of {v['triangles_if_all_detailed']:9,d}  "
              f"light parts {len(v['parts_light'])}/{len(v['parts_light']) + len(v['parts_detailed'])}  "
              f"camera {v['camera']}")
