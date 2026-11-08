"""Part detail loop: render_views.py for polished metal parts (shackles, snap shackles, padeyes).

The preview studio is lit for black plastic blocks; polished stainless under it renders nearly white, which hides the
shape from the reviewers and from Bean's sheet. This runs render_views.py unchanged with the film exposure lowered
(default -1 stop). Every round of a part, its "before" included, must use the same exposure.

    python3 Tools/boatkit/partloop/render_metal.py <Part> <out dir> [--samples N] [--exposure -1.0]
    blender -b --factory-startup -P Tools/boatkit/partloop/render_metal.py -- <Part> <out dir> [--exposure -1.0]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import render_views as RV  # noqa: E402


def main():
    a = sys.argv
    exposure = -1.0
    if "--exposure" in a:
        i = a.index("--exposure")
        exposure = float(a[i + 1])
        del a[i:i + 2]
    bpy.context.scene.view_settings.exposure = exposure
    RV.main()


if __name__ == "__main__":
    main()
