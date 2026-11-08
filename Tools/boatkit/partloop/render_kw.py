"""Part detail loop: render_views.py with builder options, for a reference photo that shows the part set differently
from the kit's default (a turnbuckle screwed further in, say), so the outline is compared like for like.

    python3 Tools/boatkit/partloop/render_kw.py <Part> <out dir> [--samples N] key=value ...

Values are read as numbers where they can be. The kit itself always builds the default (build_kit.py is unchanged).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import render_views as RV  # noqa: E402  (first: it imports bpy, which bmesh needs)
import bk_parts as P  # noqa: E402


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    kw = {}
    for x in [x for x in a if "=" in x]:
        k, v = x.split("=", 1)
        try:
            kw[k] = float(v)
        except ValueError:
            kw[k] = v
    sys.argv = [sys.argv[0]] + [x for x in a if "=" not in x]
    build = P.build
    P.build = lambda name, size=None, **k: build(name, size, **{**kw, **k})
    RV.main()


if __name__ == "__main__":
    main()
