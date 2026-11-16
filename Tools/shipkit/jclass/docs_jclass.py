"""Copies a build's checks and renders into a docs page's baseline folder (docs/jclass-1 to docs/jclass-12).

    python docs_jclass.py <out dir> <docs baseline dir> [--slice 2|3|4|5|6|7|8|9|10|11|12]

<out dir> is where loft.py, build_jclass.py, fairness.py and render_jclass.py wrote (renders in <out>/renders). Slice 1
(the default) copies build.json, hydrostatics.json, sections.json and fairness.json and writes the clay, zebra and
afloat renders and the lines drawing. Slice 2 copies build.json, fairness.json (the moulded hull, as slice 1) and
<out>/shell/fairness.json as fairness_shell.json (the finished shell), and writes the paint renders and the build's two
drawings (plating.png, rudder_sections.png). Slice 3 copies the same three jsons and writes the deck renders, the afloat
and profile views with the deck on, and the deck's two drawings (deck_plan.png, deck_profile.png). Slice 4 copies the
same three jsons and writes the rig renders and the sail plan (sail_plan.png). Slice 5 copies the same three jsons and
writes the rigging renders and the rigging plan (rigging_plan.png). Slice 6 copies the same three jsons and writes the
sails' renders (the 200 m silhouettes first, Milestone A's) and the sails' two drawings (sail_cut.png, sail_suits.png).
Slice 7 copies the same three jsons and writes the running rigging's renders and its plan (running_plan.png). Slice 8
copies the same three jsons and writes the deck hardware's renders and its plan (hardware_plan.png). Slice 9 copies
the same three jsons and writes the renders below decks forward and the arrangement drawing (interior_plan.png).
Slice 10 copies the same three jsons and writes the renders below decks aft, lit by the cabins' lamps, and the
arrangement drawing aft (interior_aft_plan.png). Slice 11 copies build.json and wear_check.json (from the renders) and
writes only a contact sheet of the wear views, each at L0, L2 and L4 (new, six years half kept, twenty neglected) in
a row; its ladders are wear_check.py's sheets. Slice 12 copies build.json, light.json (the light copy's report),
gate_views.json (gate_views.py's six frame-rate views) and the light renders' compare.json, and writes a contact sheet
of the light shots, the detailed boat beside her light copy in each row; the pairs over their difference and the crops
at the screen's own pixels are light_compare.py's (run it with this docs folder). Each image is a JPEG under 300 KB
(docs images are plain git, not LFS), with a contact sheet of the renders. Needs Pillow.
"""
import os
import shutil
import sys

from PIL import Image

ARGS, SLICE = [], 1
_it = iter(sys.argv[1:])
for _a in _it:
    if _a == "--slice":
        SLICE = int(next(_it))
    elif _a.startswith("--slice="):
        SLICE = int(_a.split("=", 1)[1])
    elif _a.startswith("--"):
        raise SystemExit(f"docs_jclass.py: unknown option {_a}")
    else:
        ARGS.append(_a)
if len(ARGS) != 2 or SLICE not in range(1, 13):
    raise SystemExit("usage: docs_jclass.py <out dir> <docs baseline dir> [--slice 1|2|...|12]")
OUT, DOCS = ARGS
RENDERS = {
    1: ["clay_profile", "clay_plan", "clay_bow34", "clay_stern34", "clay_bow", "clay_stern", "clay_under",
        "zebra_bow34", "zebra_under", "zebra_profile", "afloat_34", "afloat_profile"],
    2: ["paint_profile", "paint_bow34", "paint_stern34", "paint_under", "paint_afloat34", "paint_bowline",
        "paint_rudder", "paint_slot", "paint_transom", "paint_plating"],
    3: ["deck_aloft", "deck_34", "deck_eye", "deck_bow", "deck_skylight", "deck_doghouse", "deck_helm", "deck_stern",
        "paint_afloat34", "paint_profile"],
    4: ["rig_profile", "rig_afloat34", "rig_ahead", "rig_run", "rig_reach", "rig_spreaders", "rig_masthead",
        "rig_hounds", "rig_gooseneck", "rig_polecar"],
    5: ["rigging_profile", "rigging_ahead", "rigging_afloat34", "rigging_hounds", "rigging_tip", "rigging_chainplates",
        "rigging_lashing", "rigging_tackle", "rigging_masthead", "rigging_jumpers", "rigging_counter",
        "rigging_stemhead", "rigging_boom_lee", "rigging_run", "rigging_run_port"],
    6: ["sails_200m_genoa", "sails_200m_genoa_abeam", "sails_200m_genoa_windward", "sails_200m_spin",
        "sails_200m_spin_abeam", "sails_200m_quad", "sails_profile", "sails_lee34", "sails_backlit", "sails_quad34",
        "sails_spin34", "sails_head", "sails_clew", "sails_luff", "sails_hanks", "sails_genoa_clew", "sails_spin_head",
        "sails_moored", "sails_lowered", "sails_stack"],
    7: ["running_afterdeck", "running_primary", "running_mainsheet", "running_runner", "running_mast_foot",
        "running_reel", "running_masthead", "running_genoa_lead", "running_quad", "running_spin34", "running_pole_end",
        "running_spin_quarter", "running_moored", "running_profile", "running_capstan", "running_reel_close"],
    8: ["hardware_foredeck", "hardware_profile", "hardware_stem_head", "hardware_bow_cleat", "hardware_anchor",
        "hardware_cowl", "hardware_cowl_capped", "hardware_deck_prism", "hardware_sidelight", "hardware_sidelight_port",
        "hardware_track", "hardware_stern", "hardware_ensign", "hardware_burgee"],
    9: ["below_plan", "below_half_port", "below_half_starboard", "below_fcsl_forward", "below_fcsl_aft", "below_cot",
        "below_galley", "below_range", "below_galley_bins", "below_sail_locker", "below_washroom", "below_forepeak",
        "below_forepeak_section", "below_windlass", "below_cable_lead", "below_bow_chock"],
    10: ["below_aft_plan", "below_aft_half_port", "below_aft_half_starboard", "below_aft_saloon_forward",
         "below_aft_saloon_aft", "below_aft_pantry", "below_aft_bookcase", "below_aft_lobby", "below_aft_stairs",
         "below_aft_doghouse_up", "below_aft_desk", "below_aft_stateroom", "below_aft_bathroom", "below_aft_guest",
         "below_aft_heads"],
    11: [f"wear_{v}_{lv}" for v in ("hull", "deck", "winch", "chainplates", "doghouse", "gooseneck", "sail", "cot",
                                    "saloon") for lv in ("L0", "L2", "L4")],
    12: [f"light_{d}_{b}_{w}" for d in (50, 100, 300) for b in ("abeam", "bow") for w in ("hero", "light")]
    + [f"light_wire_{v}_{w}" for v in ("bow", "mast_foot", "counter") for w in ("hero", "light")],
}[SLICE]
JSONS = {1: [("build.json", "build.json"), ("hydrostatics.json", "hydrostatics.json"),
             ("sections.json", "sections.json"), ("fairness.json", "fairness.json")],
         2: [("build.json", "build.json"), ("fairness.json", "fairness.json"),
             (os.path.join("shell", "fairness.json"), "fairness_shell.json")]}
if SLICE < 11:
    JSONS = JSONS[min(SLICE, 2)]
elif SLICE == 11:
    JSONS = [("build.json", "build.json"), (os.path.join("renders", "wear_check.json"), "wear_check.json")]
else:
    JSONS = [("build.json", "build.json"), ("light.json", "light.json"), ("gate_views.json", "gate_views.json"),
             (os.path.join("renders", "compare.json"), "compare.json")]
DRAWINGS = {1: [("lines.png", "lines.jpg", 1800)],
            2: [("plating.png", "plating.jpg", 1800), ("rudder_sections.png", "rudder_sections.jpg", 1600)],
            3: [("deck_plan.png", "deck_plan.jpg", 2000), ("deck_profile.png", "deck_profile.jpg", 1800)],
            4: [("sail_plan.png", "sail_plan.jpg", 1800)],
            5: [("rigging_plan.png", "rigging_plan.jpg", 2000)],
            6: [("sail_cut.png", "sail_cut.jpg", 2000), ("sail_suits.png", "sail_suits.jpg", 1800)],
            7: [("running_plan.png", "running_plan.jpg", 2000)],
            8: [("hardware_plan.png", "hardware_plan.jpg", 2000)],
            9: [("interior_plan.png", "interior_plan.jpg", 2000)],
            10: [("interior_aft_plan.png", "interior_aft_plan.jpg", 2000)], 11: [], 12: []}[SLICE]
COLS, CELL = (2, (900, 506)) if SLICE == 12 else (3, (600, 337))    # slice 12: each row a pair
LIMIT = 290_000


def save(im, path, width):
    im = im.convert("RGB")
    im = im.resize((width, round(width * im.size[1] / im.size[0])), Image.LANCZOS)
    for q in (88, 82, 76, 70, 64, 58):
        im.save(path, quality=q, optimize=True)
        if os.path.getsize(path) < LIMIT:
            return
    raise SystemExit(f"{path} is still over {LIMIT} bytes")


def fit(im, cell):
    """im scaled to fit the cell, centred on white (slice 12's shots are cropped to the boat, each its own shape)."""
    im = im.convert("RGB")
    k = min(cell[0] / im.size[0], cell[1] / im.size[1])
    im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
    out = Image.new("RGB", cell, "white")
    out.paste(im, ((cell[0] - im.size[0]) // 2, (cell[1] - im.size[1]) // 2))
    return out


def main():
    os.makedirs(DOCS, exist_ok=True)
    for src, dst in JSONS:
        shutil.copy(os.path.join(OUT, src), os.path.join(DOCS, dst))
    for n in RENDERS if SLICE < 11 else []:     # slice 11's are wear_check.py's, slice 12's light_compare.py's
        save(Image.open(os.path.join(OUT, "renders", n + ".png")), os.path.join(DOCS, n + ".jpg"), 1200)
    for src, dst, width in DRAWINGS:
        save(Image.open(os.path.join(OUT, src)), os.path.join(DOCS, dst), width)
    rows = (len(RENDERS) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * CELL[0], CELL[1] * rows), "white")
    for k, n in enumerate(RENDERS):
        im = Image.open(os.path.join(OUT, "renders", n + ".png"))
        im = fit(im, CELL) if SLICE == 12 else im.convert("RGB").resize(CELL, Image.LANCZOS)
        sheet.paste(im, ((k % COLS) * CELL[0], (k // COLS) * CELL[1]))
    save(sheet, os.path.join(DOCS, "sheet.jpg"), 1800 if rows <= 6 else 1350)    # slice 11's 9 rows: smaller
    print("docs_jclass: wrote", DOCS)


main()
