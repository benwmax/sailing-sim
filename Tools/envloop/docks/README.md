# Environment loop tools for Tracks F and H (interim)

Scripts for the shore plan's environment loop until Track 0's shared tools land: build by script, check against cards,
render at 3, 15 and 60 m in three lights, contact sheets, blind pairs. Pages: `docs/envloop/docks/`, `docs/envloop/yard/`.

Everything lives in this track's folder (Track 0 owns `Tools/envloop/` itself); Track H's builder imports from here.

- `shorekit.py`: modelling helpers on top of `Tools/blender/build_docks.py`'s `Part` (boards, framing, pipe pilings,
  ribbed roofs, rails, dropping a club kit part into a bigger mesh, sockets).
- `build_shore_docks.py`, `build_before.py`, `cards.json`: Track F.
- `../yard/build_yard_props.py`, `../yard/cards.json`: Track H.
- `checks.py`, `render_envloop.py`, `make_sheet.py`: the loop's checks, standard renders and sheets.

No game files are touched: nothing here writes under `Content/`. Run with Python 3.13 and `pip install bpy==5.1.2 numpy
pillow`, or Blender (`blender -b --factory-startup -P <script> -- <args>`).
