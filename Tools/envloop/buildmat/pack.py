"""The region pack every buildmat tool works on (Track E2). A pack is data only: packs/<name>.json lists a region's wall
and roof finishes (ids, class, real sizes, palettes) and its test houses. The code and the shader are shared by every
region; another region is a new pack file, not new code.

Every tool takes --pack <name> (or BUILDMAT_PACK in the environment); the default is north-texas-lake. It is read here,
at import, so module-level tables in the tools see the chosen pack.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DEFAULT = "north-texas-lake"

# How each class is drawn (make_textures.MAKERS) and worn (buildmat_hlsl: the shader's Kind). The numbers keep the
# shader's ranges: masonry < 3.5 (stone 3), painted 4..6, shingle 10, metal 13, membrane 14.
CLASSES = {"brick": 0, "stone": 3, "lap": 4, "batten": 5, "render": 6, "shingle": 10, "standing_seam": 13, "membrane": 14}


def _name():
    argv = sys.argv
    for i, a in enumerate(argv):
        if a == "--pack" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--pack="):
            return a.split("=", 1)[1]
    return os.environ.get("BUILDMAT_PACK", DEFAULT)


NAME = _name()


def path(name=None):
    return os.path.join(HERE, "packs", (name or NAME) + ".json")


def load(name=None):
    p = json.load(open(path(name)))
    for kind in ("walls", "roofs"):
        for c in p[kind]:
            if c["class"] not in CLASSES:
                raise ValueError("%s: unknown class %r (one of %s)" % (c["name"], c["class"], ", ".join(CLASSES)))
    return p


def finishes(name=None):
    """{finish name: card} for walls then roofs."""
    p = load(name)
    return {c["name"]: c for c in p["walls"] + p["roofs"]}


def kind(card):
    """The shader's Kind for a finish card."""
    return float(CLASSES[card["class"]])


def tex_dir(name=None):
    """Where make_textures.py writes this pack's maps (git-ignored)."""
    return os.path.join(REPO, "Data", "BuildMat", "raw", "out", name or NAME)


def add_arg(ap):
    ap.add_argument("--pack", default=NAME, help="region pack in packs/ (default %s)" % DEFAULT)
