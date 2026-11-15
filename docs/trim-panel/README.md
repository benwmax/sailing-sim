# Sail trim panel: the Telltale window

Bean, Nov 15 2026. The old panel (three streamer lines and a heel bar) showed the right things, but nothing said what they
were or what to do. Two directions were mocked up; Bean chose the **Telltale window** and dropped the heel element.

Mockups (live, every state): https://claude.ai/artifact/5WzmjY6kEr6xtv7oBnvo32

## What it shows

- **Jib window.** The jib's luff seen from the cockpit: luff tape and forestay on the left, three yarn pairs a hand's width
  aft (a quarter, half and three-quarters up, the same strips as the 3D ribbons). The near, windward yarn is solid; the far
  one shows faintly through the cloth. Green to starboard, red to port, as on a real boat.
- **Main window.** The main's leech against the sky with three red ribbons at the battens (0.4, 0.6, 0.8 up), streaming aft
  or curling behind the leech when the main stalls.
- A boat with no jib (Sunfish, ILCA) shows the luff of her main in the left window, labelled SAIL.
- At the dock every yarn hangs still.

The yarns use the 3D ribbons' own rules (`JibTelltaleState`, `LeechTelltaleState` in `SailCloth.h`) and strip mapping
(`SSailHud::TrimStripAt`), so the panel and the sail always agree.

## UI modes

Bean wants three player-selectable UI modes: **UI Off**, **UI Natural** (little or no text, no explainers, natural feel)
and **UI Helpful** (full text and explainers). Until the saved setting exists the panel follows the HUD's existing switch
(`SSailHud::Mode`, the H key and Settings > Display > HUD):

| HUD switch | Bean's mode | Trim panel |
| --- | --- | --- |
| Full (0) | UI Helpful | Panel with a TELLTALES header and point of sail, both windows, a headline and one short line |
| Minimal (1) | UI Natural | The two windows only, no panel, no words (268 x 93 px) |
| Off (2) | UI Off | Hidden |

UI Helpful is 300 px wide at 100% HUD and about 184-200 px tall: its rows follow the fonts' own line heights (`STrimView::HelpfulLayout`), so a bigger type scale or Settings > Text size pushes them down instead of overlapping. It is anchored bottom right with the key hints under it.

## The Helpful line

`SSailHud::TrimVerdict` picks the most urgent; two of the three yarns make a call (`SailingSim.UI.TrimVerdict`).

| When | Headline | Line |
| --- | --- | --- |
| Tied up | Tied up | |
| In irons | In irons | Bear away until the sails fill. |
| Heel past `TrimHeelLimitDeg` (monohulls) | Heeling too much | Ease the main or hike out. |
| Inside yarns lifting, TWA under 50 deg | Pinching | Inside yarns lifting. Bear away. |
| Inside yarns lifting, further off the wind | Sails luffing | Inside yarns lifting. Sheet in. |
| Outside yarns stalled | Sails too tight | Outside yarns drooping. Ease out. |
| Leech ribbons curling | Main too tight | Leech ribbons curling. Ease the main. |
| Otherwise | Sailing well | All yarns streaming. Hold course. |

"Good" is light blue (`WindTrue`), never green: red and green only mean port and starboard. A line wider than the panel
is drawn smaller to fit (Settings > Accessibility > Text size).

## Cost

Flat Slate drawing in the volatile `STrimView`: two gradients, about 30 thin boxes for the main, 3 seam lines and up to
15 yarn polylines of 15 points. No textures, no materials.

## Stills

`-SailingHudMode=0|1|2` starts the HUD in a mode, for example
`scripts/run-game.sh 8 -SailingHudMode=1 -SailingHoldTWA=28 -SailingTWA=28 -SailingShot=trim-natural-pinch`.
