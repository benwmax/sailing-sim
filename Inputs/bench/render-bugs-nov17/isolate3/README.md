# #29 waterline glow: specular, reflection and Lumen-reflection switches on the ecd4ed1c package (PC)

**Setup:**

- **Package:** main `ecd4ed1c`'s Development package (`Packaged\Windows-ecd4ed1c`), the one the #29 stills came from.
- **Runs:** the same recipe and args as `../isolate/` (render-bugs-nov17 `args.csv`): Ultra 1920x1080, `-SailingScreenPct=100`, ecd4ed1c's own `bench-win.ps1 -Seconds 8`, after one warm-up. Each still was shot once:
  - baseline
  - `-ExecCmds="r.ReflectionEnvironment 0"`
  - `-ExecCmds="ShowFlag.Specular 0"`
  - `-ExecCmds="r.Lumen.Reflections.Allow 0"`
- **Applied:** the game log shows the switches took effect, e.g. `r.Lumen.Reflections.Allow = "0"` after the ini's `1`.
- **Saved:** Bean's Saved was held aside and restored.

**Contents:**

- `stills/`, `args.csv` (the exact command lines).
- `crops/glow-<station>-<flag>.png`: 1:1 at the render-bugs-nov17 boxes (bridge-05m x 480-960 y 640-900, wooded-15m x 480-900 y 580-700).
- `crops/sheet-<station>.png`: the four side by side.

## Result: specular off removes the glow; reflections off do not

Mean colour inside the glow itself (bridge-05m x 560-820 y 700-830; wooded-15m x 560-760 y 615-650):

| Station | baseline | ReflectionEnvironment 0 | ShowFlag.Specular 0 | Lumen.Reflections.Allow 0 |
|---|---|---|---|---|
| bridge-05m, luma | 150.5 | 152.0 | **79.8** | 154.8 |
| wooded-15m, luma | 128.1 | 127.6 | **44.1** | 127.0 |

- **The ecd4ed1c baseline still shows the cream glow** at both stations, as on Nov 17.
- **`ShowFlag.Specular 0` removes it completely:** the bank under it reads as plain shaded soil (`sheet-bridge-05m.png`, `sheet-wooded-15m.png`).
- **The reflection switches don't touch it:** turning off the reflection environment or Lumen reflections leaves it unchanged. Lumen-off only changes the bank's ambient tone.

**Verdict:** the glow is direct specular from the terrain's own surface at the waterline, the sun's specular on the wet band, not reflected light. That points at M_Terrain's wet-band roughness and specular, which is what #804 changes.

#804's own before/after (`isolate3/fix/`) follows separately.
