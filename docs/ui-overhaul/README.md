# UI overhaul

Bean, Nov 15 2026: the yellow UI was the stand-in that got the game on its feet. The game should feel natural, textured
and real ("not kitschy, but real"), the menus stay over real engine content, and the overhaul lands in the slice.

The direction is **paper for planning, glass for sailing** ("Chart table"): ashore, the menus are ink on chart paper;
afloat, the HUD is ink-blue glass with chart-paper text. Chart magenta, the colour a chart uses for the course and for
anything you should look at, is the focus and the main action. Yellow means caution and nothing else.

- Findings (15, ranked, with sources): https://claude.ai/artifact/H9AP6SSkH3NvfujdPUsQYS
- Proposal with mockups, the phases and the questions: https://claude.ai/artifact/Tu4gEHprSbyBKygQ7MJCkB

## The three interface modes

The player picks one (Bean, Nov 15 2026). Every screen and HUD element is designed for all three.

| Mode | What it shows | Number |
|---|---|---|
| Helpful | Full text and explainer elements | 0 |
| Natural | A glimpse of what is hard to see from the normal view, few words, no explainers | 1 |
| Off | Nothing but warnings (aground, capsized) | 2 |

`SailUI::UiMode()` reads it and `SailUI::SetUiMode()` sets it, keeps the HUD in step and saves. It is
`USailingSettings::UiMode` and `settings.uiMode` in the save (`helpful`, `natural`, `off`; `docs/save/README.md`).
`SSailHud::Mode` is the same number while sailing, so HUD code that branches on it (the trim panel) needs no change. The
H key cycles it; Settings > Display > Interface and the first-launch card set it. Before this pass the HUD's mode was
Full, Minimal, Off and was forgotten when the game closed. A measuring run (bench, capture) keeps the full HUD.

## Phase 1: foundations (this pull request)

Game code only (`Source/`), no assets.

**Colour** (`SailUIStyle.cpp`). The glass tokens keep their names, so every screen changes at once:

| Token | Was | Now | Use |
|---|---|---|---|
| `Ink` | `#0A141C` | `#15222C` | Backdrop washes, text on light chips |
| `Panel` | `#0D1D28` 80% | `#15222C` 82% | Glass panels |
| `Raise`, `Line` | `#17303F`, `#2B4554` | `#26394A`, `#3B5161` | Raised buttons, hairlines |
| `Fg` | `#EAF0F2` | `#F0E8D2` (chart paper) | Main text on glass |
| `Muted`, `Dim` | `#93A8B4`, `#71889A` | `#AEB6B0`, `#8C968F` | Quieter text (7.7:1 and 5.2:1 on the panel; `Dim` was 4.3:1) |
| `Accent` | `#F4C430` (yellow) | `#DB5FA3` (chart magenta) | Focus ring, main action, section labels |
| `AccentInk` | `#1D1600` | `#15222C` | Text on the main button |

New tokens: `Paper` `#F0E8D2`, `PaperInk` `#15222C`, `PaperMuted` `#4A5A64`, `PaperLine` `#CFC4A6`, `AccentDeep`
`#A62B6E` (magenta on paper), `Brass` `#A98A44` (medals), `Caution` `#F4C430` (the old yellow, for caution only). Port red
and starboard green are unchanged and are still always paired with P and S or a word.

**Type.** Sizes are pixels at 1080p. Nothing is under 15 px now; the player's text size (100 to 150%) reaches every style
under 30 px (it reached three); capitals stay only on the short tracked labels.

| Style | Was | Now | Capitals |
|---|---|---|---|
| ScreenTitle | 60 | 56 | no (was yes) |
| MenuItem | 30 | 30 | no (was yes) |
| CardTitleS | 22 | 24 | no (was yes) |
| Button, Value | 19 | 21 | no (Button was yes) |
| Ui, Body | 17 | 20 | no |
| Small | 14 | 17 | no |
| Eyebrow | 14 | 16 | yes |
| Label | 12 | 15 | yes |
| InstrumentBig | 48 | 52 | no |

The proposal's targets for the couch are body 24 and labels 20. This step goes most of the way without the new layouts;
the rest comes with each screen's own pass, where its boxes are redrawn for the bigger text.

**Focus.** A focused menu row (the title's and the pause menu's, `SailUI::MenuRow`) lies on a paper label with the
chart's magenta diamond at its head, and its text turns to ink. Everything else focusable gets the magenta ring. A chosen
launch pin is paper with a magenta edge.

**Margins.** `SafeX` 64 to 80, `SafeTop` 50 to 54, `HudMargin` 30 to 40 (the title-safe area of a television is the
inner 90%: 96 by 54 px at 1080p). A margin slider comes with the display rows.

**Component page.** Settings > Component page (developer), or `-SailingFrontEnd=Components`: every token, type style
and shared widget on one screen (`SailComponents.cpp`), so one still shows what a style change did.

Tests: `SailingSim.UI.Overhaul.Tokens` (contrast on glass and paper, the accent is not yellow), `.Type` (nothing under
15 px, the text size reaches labels and notes, capitals only on labels), `.Mode` (the three modes through the save);
`SailingSim.Save.RoundTrip` carries `uiMode`.

### Stills to take

At 1920x1080 (`RESX=1920 RESY=1080 scripts/run-game.sh 6 -ForceRes -SailingNoGpuSlices ...`), each with `-SailingShot=<name>`:

| Shot | Arguments |
|---|---|
| components | `-SailingFrontEnd=Components` |
| title | `-SailingFrontEnd=Title` |
| boat | `-SailingFrontEnd=Boat` |
| conditions | `-SailingFrontEnd=Conditions` |
| settings | `-SailingFrontEnd=Settings` |
| first-launch | `-SailingFrontEnd=FirstLaunch` |
| pause | `-SailingFrontEnd=Pause` |
| career | `-SailingFrontEnd=Career` |
| hud | `-SailingWind=10 -SailingTWA=60` (the HUD while sailing) |

What to look for: text that no longer fits its box (the bigger type), the title's ten rows clear of the prompt bar, the
paper label under the focused row with ink text, and nothing yellow except a caution.

## What comes next

1. Fonts (Besley for titles, Atkinson Hyperlegible Next for text, B612 for instrument numerals; all SIL OFL, to be
   confirmed from the licence file in each download), paper textures and controller glyph sets (Kenney input prompts,
   CC0). These are `Content/` files: they go in through the Mac or the PC with their rows in
   `docs/licences/assets.csv`, and need Bean's label.
2. Menus on paper: title, the set-up steps, the logbook as the heart of the career, briefing, settings, pause.
3. On the water: a box-free HUD, the chart minimap, messages, the red night palette, instruments on the boat (bulkhead
   compass and masthead fly on keelboats, a wrist compass on dinghies) so Off is sailable.
4. Moments: the medal card and the certificate.
5. The brand kit on the study and feedback sites.

The HUD's own files (`SailHud.cpp`) are not touched in this phase: the HUD layout (#710) and the trim panel (#712) are in
flight there, and the HUD pass lands after them.
