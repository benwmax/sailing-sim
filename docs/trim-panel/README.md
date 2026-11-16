# Sail trim panel: the Telltale window

Bean, Nov 15 2026. The old panel (three streamer lines and a heel bar) showed the right things, but nothing said what they
were or what to do. Two directions were mocked up; Bean chose the **Telltale window** and dropped the heel element.

Mockups (live, every state): https://claude.ai/artifact/5WzmjY6kEr6xtv7oBnvo32

## What it shows

- **Jib window.** The jib's luff seen from the cockpit: luff tape and forestay on the left, three yarn pairs a hand's width
  aft, one for each third of the sail. The near, windward yarn is solid; the far one shows faintly through the cloth.
  Green to starboard, red to port, as on a real boat.
- **Main window.** The main's leech against the sky with three red ribbons at the battens, one for each third of the
  leech, streaming aft, curling behind the leech when the main stalls, flapping when it luffs.
- A cat rig (Sunfish, ILCA) shows her one sail's luff in the left window and its leech in the right, labelled LUFF and
  LEECH.
- At the dock every yarn hangs still.

Each yarn uses the 3D ribbons' own rules (`JibTelltaleState`, `LeechTelltaleState` in `SailCloth.h`) on every physics
strip in its third of the sail and shows the worst of them (`SSailHud::TrimYarnState`; a third with no strip of its own,
on a sail with fewer than three, reads the strip at its middle). So whenever the headline calls a sail, at least one yarn
shows it.

## UI modes

Bean wants three player-selectable UI modes: **UI Off**, **UI Natural** (little or no text, no explainers, natural feel)
and **UI Helpful** (full text and explainers). Until the saved setting exists the panel follows the HUD's existing switch
(`SSailHud::Mode`, the H key and Settings > Display > HUD):

| HUD switch | Bean's mode | Trim panel |
| --- | --- | --- |
| Full (0) | UI Helpful | Panel with a TELLTALES header and point of sail, both windows, a headline and one short line |
| Minimal (1) | UI Natural | The two windows only, no panel, no words (268 x 93 px) |
| Off (2) | UI Off | Hidden |

UI Helpful is 300 px wide at 100% HUD and about 184-200 px tall: its rows follow the fonts' own line heights (`STrimView::HelpfulLayout`), so a bigger type scale or Settings > Text size pushes them down instead of overlapping. It sits at the bottom of the HUD's right-hand column (docs/hud-layout/), with the key hints under it in UI Helpful.

## The Helpful line

`SSailHud::TrimVerdict` says what the coach's tips say (`SailingCollectBoatTips` in `SailingHUD.cpp`), in one headline and
one short line, the most urgent first. It uses the tips' own no-go cue (`NoGoCueFor`: Easy mode's wider zone and its
warning band, held for the tips' first 10 s after a start), their counts over every strip, two strips to make a call, and
their gate (no sail calls under 35 deg off the wind). `SailingSim.UI.TrimVerdict` sweeps every pair of strips on both
sails, a sloop and a dinghy, nine wind angles, Realistic and Easy, and fails if the headline says all is well while a tip
warns (or the other way round), or if a call doesn't show on a yarn.

| When | Headline | Line |
| --- | --- | --- |
| Tied up | Tied up | |
| In irons | In irons | Bear away until the sails fill. |
| Heel past `TrimHeelLimitDeg` (monohulls) | Heeling too much | Ease the main or hike out. |
| Inside the no-go zone | Too close to the wind | Bear away to about 45 degrees. |
| In Easy mode's warning band | Near the no-go zone | Bear away a little before she slows. |
| Two jib strips luffing or backed | Jib luffing | Inside yarns lifting. Sheet in or bear away. (Sheet the jib in, past 60 deg) |
| Two jib strips stalled | Jib too tight | Outside yarns drooping. Ease the jib. |
| Two main strips luffing | Main luffing | Leech ribbons flapping. Sheet the main in. |
| Two main strips stalled | Main too tight | Leech ribbons curling. Ease the main. |
| No jib: two strips luffing / stalled | Sail luffing / Sail too tight | Inside yarns lifting. Sheet in. / Yarns drooping and curling. Ease the sheet. |
| Otherwise | Sailing well | Yarns streaming. Hold course. |

"Sailing well" names a single yarn that is off, since one strip is not a call for the tips but the yarn shows it: "A leech
ribbon is curling. Ease the main a touch." (or the sheet, on a cat rig), then "An outside yarn is drooping. Ease the jib a
touch.", then "Inside yarns just lifting. Right on the edge." when two inside yarns lift short of a luff.

The headline is judged beside the learning tip card, in `SSailHud::Refresh` at the HUD's 10 Hz text rate, from the same
telemetry, and holds by the card's rule (`SSailHud::HoldTrimVerdict`, `TipHoldSeconds`): a warning shows at once and stays
at least 6 s, so a stall flickering between one strip and two doesn't blink it, and the card and the headline change
together. The dock shows at once; the same headline's line changes at most every 1.5 s. On a cat rig the tips say "Sail",
not "Main" or "Jib", as the panel does.

"Good" is light blue (`WindTrue`), never green: red and green only mean port and starboard. A line wider than the panel
is drawn smaller to fit (Settings > Accessibility > Text size).

## Cost

Flat Slate drawing in the volatile `STrimView`: two gradients, about 30 thin boxes for the main, 3 seam lines and up to
15 yarn polylines of 15 points. No textures, no materials.

## Stills

`-SailingHudMode=0|1|2` starts the HUD in a mode, for example
`scripts/run-game.sh 8 -SailingHudMode=1 -SailingHoldTWA=28 -SailingTWA=28 -SailingShot=trim-natural-pinch`.
