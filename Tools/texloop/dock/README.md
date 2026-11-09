# Club dock texture loop tools

- `measure_refs.py`: fetch and measure the CC0 Poly Haven scans in `../refs/dock.json` -> `../targets/dock.json`.
- `hlsl_np.py`: runs M_WorldSurface's HLSL text (any git revision) on numpy, so renders can't drift from the shader.
- `render_levels.py`: deck, float + rub strip, piling and ramp at L0-L4 (`--rev main --tag old` for "before").
- `albedo.py`: albedo Lab per surface and level beside the targets (the colour check).
- `make_sheet.py`: the before/after sheet in `docs/texloop-dock/`.
- `test_dock.py`: dkT/dkD match `wear.py`; every dock pattern runs finite and in range at every level; MI_World_Floats
  matches KitLook in WorldKit.cpp.

Needs numpy, Pillow, scipy. See `docs/texloop-dock/README.md`.
