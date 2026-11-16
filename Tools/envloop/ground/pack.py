"""Track A: ground region packs. A pack is one JSON file in packs/ that fills the ground material's eight roles (lawn,
rough, clay, gravel, sand, mud, cracked, litter: what the weights decide) with a region's own surfaces, sizes and
colours. The maths never names a region; every tool takes --pack (default north-texas-lake, or $GROUND_PACK).
Track 0's shared pack layout replaces this file's paths once it lands.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DEFAULT = os.environ.get("GROUND_PACK", "north-texas-lake")
ROLES = ["lawn", "rough", "clay", "gravel", "sand", "mud", "cracked", "litter"]


def path(name=None):
    return os.path.join(HERE, "packs", f"{name or DEFAULT}.json")


def load(name=None):
    p = json.load(open(path(name)))
    ids = [s["id"] for s in p["surfaces"]]
    if ids != ROLES:
        raise ValueError(f"pack {name or DEFAULT}: surfaces must fill the roles in order {ROLES}, got {ids}")
    return p


def raw_dir(name=None):
    return os.path.join(REPO, "Data", "Ground", "raw", name or DEFAULT)


def prep_dir(name=None):
    return os.path.join(REPO, "Data", "Ground", "prep", name or DEFAULT)
