# In-game HUD layout (Bean, Nov 15 2026)

Bean's ask: the minimap to the top right corner, speed, depth and wind to the bottom left where the minimap was, the
bottom centre clear so the boat can be seen, and the game messages and points easier to read over the scene and
centre right. Code: `Source/SailingSim/Private/UI/SailHud.cpp` (`SSailHud::Construct`).

## Where things are now

| Corner | Before | After |
|---|---|---|
| Top left | Time, wind, sky, tide strip; learning tip; rules callout | unchanged |
| Top centre | Compass tape, heading, toasts | Compass tape and heading only |
| Right column | Drill or race panel, navigation panel (top); sail trim, key hints (bottom) | **Minimap** in the corner; the drill or race panel and the navigation panel in the room between it and the sail trim panel; sail trim and key hints at the bottom |
| Centre right | (nothing) | **Message stack**: captain's call, toasts, rules points, signals heard, sound captions |
| Bottom left | Minimap | **Apparent wind dial, then speed over depth** (one compact 410 x 254 block) |
| Bottom centre | Captain's call, captions, signals, speed, wind dial, depth | **Clear** (the boat) |

HUD modes are unchanged: Full shows everything; Minimal hides the minimap, tip and trim but keeps the cluster, compass,
drill panel and messages; Off keeps toasts, the captain's call and sound captions.

## The right column

The minimap, the drill/race/navigation panels and the sail trim panel are one column from the top-right corner to the
bottom-right corner, so the panels can never run under the trim panel. The panels get the room between the minimap and
the trim panel. When they need more (a long drill at HUD size 130%, or a drill and a race at once), the drill panel
condenses to its current step and "Step k of n" (`bCompactDrill`). It goes back to the full list once the room holds it.
Anything still too tall is clipped at the trim panel's top edge. The first stills (82fa86c) showed both overlaps that
led to this: the race card's last line under the trim panel, and the 130% drill card's last steps under it.

## The messages

- Each message is a card of ink at 92% (the panels' 80% let bright sky and whitecaps show through the letters), a 1 px
  light rim and a 6 px edge in the message's colour: green good, amber caution, red fault, blue for signals heard.
- Text carries a dark drop shadow (1.5 px), so it still reads at the card's edge.
- Rules points are their own card: the number large in its colour (`+20`, `-10`), then what it was for. They used to be
  one line inside the signals panel.
- Toasts and captions are the Ui size (17 px, scaled by Accessibility > Text size), up from Small for signals and captions.
- The stack is centred on the screen's height and right-aligned. When the right-hand column shows a panel under the minimap
  (drill, race, or the coast's navigation), the stack moves left of it (`RightColumnWidth` 365 + `MessageGap` 20).
- Its width is `SSailHud::MessageWidthFor`: up to 460 px, kept right of the screen's centre plus 40 px where the screen
  is wide enough, never under 300.

## Sizes checked

Slate lays the HUD out at 1080 logical pixels tall at any resolution (the engine's DPI curve), so what changes is the
logical width (aspect ratio) and Settings > Display > HUD size (85% to 130%, which shrinks the logical canvas).

| Screen | Logical canvas at 100% | at 130% | Notes |
|---|---|---|---|
| 1920x1080, 2560x1440, 3840x2160 (16:9) | 1920 x 1080 | 1477 x 831 | messages 460 wide either side of the drill panel |
| 1920x1200, 2560x1600 (16:10) | 1728 x 1080 | 1329 x 831 | as 16:9 |
| 3440x1440 (21:9) | 2580 x 1080 | 1985 x 831 | more room between messages and centre |
| 5120x1440 (32:9) | 3640 x 1080 | 2800 x 831 | messages stay at the right, as asked |
| 1440x1080 (4:3) | 1440 x 1080 | 1108 x 831 | with a drill panel the stack narrows to 300 and reaches the centre |

Worst-case stacks (captain's call, toast, points and signals at once, about 330 px) end above the sail trim panel at 100%
(the trim redesign's 300 x 196 box plus hints reaches up to y 824); at 130% the stack's bottom and the redesigned panel's top
meet within a few pixels only when all four messages show at once. The top right has no pause button to clash with: pause is a key (Esc or the pad's Menu), shown in the bottom-right
hints. There is no touch layout yet; the pad uses the same HUD.

`-SailingHudSample` holds up a toast, a points card and a signal so the layout can be photographed at any size
(`-SailingHudScale=<percent>`, 85 to 130, stands in for Settings > HUD size), e.g.
`RESX=2560 RESY=1080 scripts/run-game.sh 8 -ForceRes -SailingHudSample -SailingDrill=LeavetheDock`.

## Screenshots

Before (main) and after, at the sizes above, are in this folder once the Mac has run them (`before-*.jpg`, `after-*.jpg`).
