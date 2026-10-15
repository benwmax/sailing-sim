"""Style profiles: one seeded dictionary that decides how a boat looks, so every hull in a fleet is its own boat.

    python3 j22_style.py --seed 7295 --preset club > style.json

A profile is plain JSON, made from a preset (how well the boat is kept) and a seed (which particular scuffs, stains,
patches, numbers and line colours it has). The build script reads it for geometry choices (windex, telltales, tape
colour, coiled tails) and j22_materials.py reads it for every surface. Nothing in it is J/22-specific except the
defaults, so build_fleet.py can call make_style() for the other classes with its own `boat` overrides.

Sailmakers and logos are invented names: no real trademarks go on the sails.
"""
import json
import random
import sys

PRESETS = {
    # wear: how worn the surfaces are; care: how much the owner fixes and cleans
    "new": dict(wear=0.05, care=1.0),
    "race": dict(wear=0.25, care=0.9),
    "club": dict(wear=0.65, care=0.35),      # school and club boats such as TX 7295 EC
    "neglected": dict(wear=0.92, care=0.08),
}

SAILMAKERS = [
    ("LONE STAR LOFT", "#B22A22"), ("BLUE NORTHER SAILS", "#1F4E9A"), ("GULFLINE", "#0E6E6E"),
    ("REDFISH SAILS", "#C0471C"), ("PRAIRIE WIND", "#4A5A1E"), ("HARBOUR & CO", "#222222"),
    ("TRINITY LOFT", "#5B2A86"), ("CEDAR CREEK SAILS", "#2F5D3A"),
]

ROPE_COLOURS = {
    # (base, fleck) pairs seen on club boats; jib sheets come in matched pairs or port/starboard colours
    "white_red": ("#EDEBE4", "#B3201B"), "white_green": ("#EDEBE4", "#1F6A34"), "white_blue": ("#EDEBE4", "#1D3F8F"),
    "blue_white": ("#1D3F8F", "#E8E8E8"), "red_white": ("#B3201B", "#EDEBE4"), "black_white": ("#1A1A1A", "#D8D8D8"),
    "grey_red": ("#9A9A96", "#B3201B"), "yellow_black": ("#D7B21E", "#1A1A1A"),
}


def _hex_shift(h, dl, rng, warm=0.0):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    k = 1 + dl
    r, g, b = r * k + warm * 6, g * k + warm * 3, b * k - warm * 6
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in (r, g, b))


def make_style(seed=0, preset="club", boat=None, overrides=None):
    rng = random.Random(seed)
    p = dict(PRESETS[preset])
    wear, care = p["wear"], p["care"]
    j = lambda a=0.12: rng.uniform(-a, a)  # noqa: E731
    clamp = lambda v: max(0.0, min(1.0, v))  # noqa: E731
    age_yellow = clamp(wear * 0.8 + j(0.15))
    s = {
        "seed": seed, "preset": preset, "wear": round(wear, 3), "care": round(care, 3),
        "hull": {
            "gelcoat_hex": _hex_shift("#F2F0EA", -0.02 * age_yellow, rng, warm=age_yellow),
            "streaks": round(clamp(wear * (1.1 - care) + j()), 3),
            "chalk": round(clamp(wear * 0.9 - care * 0.4 + j()), 3),
            "scum": round(clamp(wear * (1.2 - care) + j()), 3),
            "scum_height_m": round(0.03 + 0.05 * wear + j(0.01), 3),
            "edge_chips": round(clamp(wear * 0.8 + j()), 3),
            "fender_marks": [round(rng.uniform(-2.2, 1.8), 2) for _ in range(rng.randint(0, int(1 + 5 * wear)))],
            "repairs": [dict(x=round(rng.uniform(-3.0, 2.8), 2), z=round(rng.uniform(0.15, 0.55), 2),
                             w=round(rng.uniform(0.05, 0.25), 2), h=round(rng.uniform(0.03, 0.10), 2),
                             tint=round(rng.uniform(-0.04, 0.03), 3))
                        for _ in range(rng.randint(0, int(4 * wear * (1.2 - care))))],
            "bottom_hex": rng.choice(["#8E918F", "#7F8482", "#9A9C97"]),    # grey, per Bean
            "bottom_slime": round(clamp(wear * (1 - care) + j()), 3),
            "boot_stripe_hex": None if rng.random() > 0.25 else rng.choice(["#1C2A44", "#2E4F8A"]),
            "registration": "TX %04d %s" % (rng.randint(1000, 9999), rng.choice(["EC", "ED", "EF", "AB", "BC", "LK"])),
            "sticker_hex": rng.choice(["#2F7D3A", "#C9A227", "#3060A8"]),
        },
        "deck": {
            "nonskid_hex": _hex_shift("#D5C7A6", j(0.05), rng),
            "grime": round(clamp(wear * (1.1 - care) + j()), 3),
            "wear_paths": round(clamp(wear + j()), 3),
            "stains": rng.randint(0, int(6 * wear)),
        },
        "teak": {"state": "silvered" if care < 0.5 else rng.choice(["oiled", "silvered"]),
                 "wear": round(clamp(wear + j()), 3)},
        "varnish": {"gloss": round(clamp(care + j(0.1)), 3), "peel": round(clamp(wear * (1 - care) + j(0.1)), 3)},
        "metal": {"anodise_wear": round(clamp(wear + j()), 3), "tea_stain": round(clamp(wear * (1 - care) + j()), 3)},
        "ropes": {
            "jib_sheet_port": rng.choice(["white_red", "red_white", "white_blue"]),
            "jib_sheet_stbd": None,
            "mainsheet": rng.choice(["white_red", "grey_red", "black_white"]),
            "halyards": rng.choice(["white_blue", "blue_white", "white_red"]),
            "vang": rng.choice(["blue_white", "black_white", "red_white"]),
            "backstay": rng.choice(["white_red", "red_white"]),
            "fade": round(clamp(wear * (1.1 - care) + j()), 3),
        },
        "sails": {
            "cloth": rng.choices(["white_dacron", "grey_laminate"], weights=[0.6, 0.4])[0],
            "age": round(clamp(wear + j(0.15)), 3),
            "stains": rng.randint(0, int(8 * wear)),
            "patches": rng.randint(0, int(3 * wear * (1.2 - care))),
            "number": "USA %d" % rng.randint(1, 1700),
            "maker": rng.choice(SAILMAKERS),
            "insignia_hex": "#1F4E9A",
            "number_hex": rng.choice(["#111111", "#111111", "#1C2A44"]),
        },
        "details": {
            "windex": rng.random() < 0.85,
            "rig_tape_hex": rng.choice(["#F2F2F0", "#F2F2F0", "#1A1A1A"]),
            "telltales": rng.random() < 0.9,
            "coiled_tails": True,
            "outboard": True,
        },
    }
    # matched or port/starboard coloured jib sheets
    s["ropes"]["jib_sheet_stbd"] = s["ropes"]["jib_sheet_port"] if rng.random() < 0.6 else "white_green"
    s["sails"]["base_hex"] = "#F2EFE6" if s["sails"]["cloth"] == "white_dacron" else "#8B8D8C"
    if boat:
        s.update(boat)
    for k, v in (overrides or {}).items():
        cur = s
        keys = k.split(".")
        for kk in keys[:-1]:
            cur = cur[kk]
        cur[keys[-1]] = v
    return s


def rope_pair(style, role):
    return ROPE_COLOURS[style["ropes"][role]]


# TX 7295 EC as photographed at Rush Creek in October 2026: a club boat with red/white and green/white jib sheets,
# a red/white backstay bridle, silvered teak, a varnished tiller, white sails (Bean: grey or white), grey bottom.
TX7295 = {
    "hull.registration": "TX 7295 EC", "hull.boot_stripe_hex": None, "hull.sticker_hex": "#2F7D3A",
    "ropes.jib_sheet_port": "white_red", "ropes.jib_sheet_stbd": "white_green", "ropes.backstay": "white_red",
    "ropes.mainsheet": "white_red", "teak.state": "silvered", "sails.cloth": "white_dacron", "sails.base_hex": "#F2EFE6",
}


if __name__ == "__main__":
    a = sys.argv[1:]
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    preset = a[a.index("--preset") + 1] if "--preset" in a else "club"
    ov = TX7295 if "--tx7295" in a else None
    print(json.dumps(make_style(seed, preset, overrides=ov), indent=1))
