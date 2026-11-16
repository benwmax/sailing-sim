# UI overhaul

Bean, Nov 15 2026: the yellow UI was the stand-in that got the game on its feet. The game should feel natural, textured
and real ("not kitschy, but real"), the menus stay over real engine content, and the overhaul lands in the slice.

The direction is **paper for planning, glass for sailing** ("Chart table"): ashore, the menus are ink on chart paper;
afloat, the HUD is ink-blue glass with chart-paper text. Sea aqua is the focus and the main action (Bean, Nov 15 2026: the first pass's chart magenta read as purple on the
menu; magenta stays where a chart uses it, on the chart itself). Yellow means caution and nothing else.

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
| `Accent` | `#F4C430` (yellow) | `#4FD1C9` (sea aqua; first pass `#DB5FA3`) | Focus ring, main action, section labels |
| `AccentInk` | `#1D1600` | `#15222C` | Text on the main button |

New tokens: `Paper` `#F0E8D2`, `PaperInk` `#15222C`, `PaperMuted` `#4A5A64`, `PaperLine` `#CFC4A6`, `AccentDeep`
`#086068` (the accent on paper; first pass `#A62B6E`), `Brass` `#A98A44` (medals), `Caution` `#F4C430` (the old yellow, for caution only). Port red
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
accent diamond at its head, and its text turns to ink. Everything else focusable gets the accent ring. A chosen
launch pin is paper with an accent edge.

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

## Phase 2: menus on paper (first sheets)

The mechanism (`SailUIStyle.h`): while a `SailUI::FScopedPaper` is alive, the shared widgets and text helpers built
inside it are drawn for paper. Screens keep passing the glass tokens; `SailUI::Surface` turns each into its paper twin:

| Glass | On paper |
|---|---|
| `Fg` | `PaperInk` |
| `Muted`, `Dim` | `PaperMuted` |
| `Accent` | `AccentDeep` |
| `Ink`, `PanelSolid` (and `AccentInk`, the same ink) | `Paper` |
| `Raise`, `Line` | `PaperRaise` `#E4DABD`, `PaperLine` |
| `Port`, `Starboard`, `Warn` | `PaperPort` `#B3261F`, `PaperStarboard` `#17703F`, `PaperWarn` `#8A5200` (5.0:1 or better on paper) |

A widget asks `OnPaper()` once, when it is constructed. Map a colour once only: ink and paper are each other's twins, so
inside a scope never pass a paper token (`PaperInk`) to `SailUI::Text`, and give a hand-built `STextBlock`
`OnSurface(<token>)`. A screen wraps only its sheet in the scope (a `TOptional<FScopedPaper>`, reset before the header,
tabs and prompt bar are built): those stay on the glass over the water.

On paper so far: Settings (the rows are one sheet with ruled rows, the help is a second sheet), the first-launch card,
the confirm slip and the credits. The component page has a "Widgets on paper" section. Next: pause, briefing, quiz, the
logbook and the set-up steps.

Test: `SailingSim.UI.Overhaul.Paper` (the scope, nesting, every twin, opacity kept, 4.5:1 on paper). Extra still:
`credits` (`-SailingFrontEnd=Credits`); `settings`, `first-launch` and `components` now show paper.

## Phase 2b: what the first stills showed

The stills of phase 1 and 2 (this folder) showed text that could not be read, and this pass fixes it:

- Body and note text were hairlines: Source Sans 3 is a variable font and Slate draws its lightest instance. Until the
  overhaul's text face is in, `Body` and `Small` are Saira Semi Condensed Regular.
- Text straight on the scene (no panel) gets an ink shadow: `SailUI::TextOverScene`, the screen headers, the menu rows
  off their paper label (their notes are also chart-paper at 85%, not grey).
- The Boat screen's type line, pill, description and flags are a slip of chart paper under her name.
- The step bar lies on its own strip of glass, with thicker bars and readable upcoming steps.
- "Choose a boat" and "Set the conditions" are sentence case, and the boat's name is as written.

## Phase 2c: pause, briefing and quiz on paper

- Pause: the session so far (distance, top speed, the coach's note) is one slip of chart paper; the menu stays on the
  scene with its heading in chart paper.
- Briefing: two sheets, the lesson and its steps ("What good looks like" and "Common mistakes" in the paper's starboard
  green and warning).
- Quiz: one sheet; a right or wrong answer is edged in the paper's starboard or port.

- Career: the tier's lessons and checkride are a page of chart paper (medals in inks that read on it); the tier cards
  stay on glass beside it. The logbook's own redesign comes next.

Stills: `pause`, `briefing` (`-SailingDrill=LeavetheDock -SailingFrontEnd=Briefing`), `quiz`
(`-SailingDrill=LeavetheDock -SailingFrontEnd=Quiz`), `career`.

## Phase 3: the set-up steps

From the stills of main at b2f515a6 (`world.jpg`, `launch.jpg`, `mode.jpg`, `controls.jpg`, `customize.jpg`):

- **Where do you start?** The map pins and the list's numbered circles were the chart's magenta, the last of it in the
  menus, and the chosen pin (paper with a deep-aqua edge) was lost on the paper-coloured land. Pins are now ink with a
  paper ring, and the chosen one is the aqua accent with an ink ring; the list's circles match. Chart magenta stays on
  the chart itself.
- **Choose a world.** A locked card was dimmed to 45% and its reason could not be read. Disabled buttons are now 62%,
  and a locked card keeps its whole glass panel (only its contents dim), so the scene no longer shows through its text.
- **Customize.** The boat's name over the scene has the ink shadow (`TextOverScene`) and the title is sentence case
  ("Customize"), like the other screens.
- **Controls.** The key list and its notes are two paper sheets, like Settings; the header and prompt bar stay on glass.
- **Mode** needed nothing.

### The logbook

The logbook is the heart of the career (Bean, Nov 15). Until now it was one canvas page in the engine's font, reached by
closing the menus. It is now a screen (`ESailScreen::Logbook`, `BuildLogbook`), opened from the title and the pause menu:

- **Left sheet, "In all":** miles and hours in the big numerals, then sails, medals and certificates, and the sails
  already in the book (the session files in `Saved/Logbook`, newest first, in a list that scrolls inside the sheet;
  the file name's water is shown as words). The sails count is the save's or the files', whichever is more.
- **Right sheet, "Ship's log":** this sail's page as a ruled table (time, position, course, knots, log, wind, sea,
  remarks). Watch entries are in ink and events in red, the way a paper log is kept. It scrolls like Credits
  (`IsReadingScreen`).
- The quick look on Y while sailing is still the canvas page, now in the same paper and inks.

Stills to retake: `world` (a locked card in view), `launch`, `controls`, `customize`; new: `logbook`
(`-SailingFrontEnd=Logbook`, best after a few minutes of sailing so the page has entries).

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
