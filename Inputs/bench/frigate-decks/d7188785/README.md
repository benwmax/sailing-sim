# Frigate decks (#823) at d7188785 on the PC, Nov 24 2026

**Head:** `claude/project-thread-xkunbh` at **d7188785** ("Frigate lanterns: created lit, never toggled"). The range
gate and toggling are gone; the lanterns are created lit at load as in 44733c87, plus `SetCastShadows(false)` and
volumetric scattering 0. Fresh worktree, removed afterwards. Nothing was pushed.

- **MSVC build:** Succeeded, 0 errors.
- **Tests:** ShipOutside 4/4, ShipWalk 8/8, Smoke 36/36.
- **Package:** Development `Packaged\Windows-pr823-d7188785` (kept); cook 0 errors, 1 warning.

## Ship decks lines

```
Ship decks Gun: 0 copies, 15 lanterns (unshadowed)
Ship decks Berth: 406 copies, 12 lanterns (unshadowed)
Ship decks Orlop: 0 copies, 2 lanterns (unshadowed)
```

## Perf (Ultra, 100%, 20 s)

| Run | fps | GPU ms | base | Lumen | post | game | render | f2b9c3c5 | 44733c87 | 3946b08c (last night) |
|---|---|---|---|---|---|---|---|---|---|---|
| berth 1080p | **73.1** | 10.03 | 4.61 | 1.14 | 0.75 | 9.51 | 13.64 | 65.1 | 73.7 | |
| gun 1080p | **74.4** | 10.01 | 4.43 | 1.05 | 0.75 | 9.41 | 13.38 | 72.6 | 72.6 | 76.4 (base 3.14) |
| berth 4K | **42.7** | 22.88 | 9.51 | 2.39 | 2.47 | 12.44 | 23.40 | hang | 41.0 | |
| gun 4K | **44.5** | 21.99 | **8.95** | 2.45 | 2.36 | 11.77 | 22.47 | hang | 45.4 | 54.0 (base 5.14) |

- **No hang at 4K.** Both decks run their 20 s; the largest frame is 27.4 ms. Creating the lanterns lit and never
  toggling them clears the VSM hang that 1186594d to f2b9c3c5 had.
- **Gun deck base pass at 4K: 8.95 ms, over 5.1.** It's about what 44733c87 had (8.73), and 3.8 ms over last night's
  lantern-free 5.14.
- **Still under the 45 limit at 4K:** the berth deck is 42.7 and the gun deck 44.5. Unshadowed, the lanterns still go
  through MegaLights shading per pixel (`ab/`: about 5.4 ms at 4K on the berth deck at 44733c87). Dropping shadows
  helps only a little at 4K (berth 41.0 to 42.7).
- **1080p is fine:** 73-74 fps on both decks.

Bean's Saved was held aside and restored (7B5CA7BE).
