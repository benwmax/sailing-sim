# Environment loop tools (Tracks F and H, interim)

Scripts for the shore plan's environment loop until Track 0's shared tools land: build by script, check against cards,
render at 3, 15 and 60 m in three lights, contact sheets, blind pairs. Pages: `docs/envloop/docks/`, `docs/envloop/yard/`.

- `shorekit.py`: modelling helpers on top of `Tools/blender/build_docks.py`'s `Part` (boards, framing, pipe pilings,
  ribbed roofs, rails, dropping a club kit part into a bigger mesh, sockets).
- `docks/build_shore_docks.py`, `docks/build_before.py`, `docks/cards.json`: Track F.
- `yard/build_yard_props.py`, `yard/cards.json`: Track H.
- `checks.py`, `render_envloop.py`, `make_sheet.py`: the loop's checks, standard renders and sheets.

No game files are touched: nothing here writes under `Content/`. Run with Python 3.13 and `pip install bpy==5.1.2 numpy
pillow`, or Blender (`blender -b --factory-startup -P <script> -- <args>`).
