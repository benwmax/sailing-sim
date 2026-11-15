# In-game HUD layout (Bean, Nov 15 2026)

Bean's ask: the minimap to the top right corner, speed, depth and wind to the bottom left where the minimap was, the
bottom centre clear so the boat can be seen, and the game messages and points easier to read over the scene and
centre right. Code: `Source/SailingSim/Private/UI/SailHud.cpp` (`SSailHud::Construct`).

## Where things are now

| Corner | Before | After |
|---|---|---|
| Top left | Time, wind, sky, tide strip; learning tip; rules callout | unchanged |
| Top centre | Compass tape, heading, toasts | Compass tape and heading only |
| Top right | Drill or race panel, navigation panel | **Minimap** in the corner, then the drill or race panel and the navigation panel under it |
| Centre right | (nothing) | **Message stack**: captain's call, toasts, rules points, signals heard, sound captions |
| Bottom left | Minimap | **Apparent wind dial, then speed over depth** (one compact 410 x 254 block) |
| Bottom centre | Captain's call, captions, signals, speed, wind dial, depth | **Clear** (the boat) |
| Bottom right | Sail trim, key hints (Esc Pause) | unchanged |

HUD modes are unchanged: Full shows everything; Minimal hides the minimap, tip and trim but keeps the cluster, compass,
drill panel and messages; Off keeps toasts, the captain's call and sound captions.

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

Worst-case stacks (captain's call, toast, points and signals at once, about 330 px) still end above the sail trim panel at
130%. The top right has no pause button to clash with: pause is a key (Esc or the pad's Menu), shown in the bottom-right
hints. There is no touch layout yet; the pad uses the same HUD.

`-SailingHudSample` holds up a toast, a points card and a signal so the layout can be photographed at any size, e.g.
`RESX=2560 RESY=1080 scripts/run-game.sh 8 -ForceRes -SailingHudSample -SailingDrill=LeavetheDock`.

## Screenshots

Before (main) and after, at the sizes above, are in this folder once the Mac has run them (`before-*.jpg`, `after-*.jpg`).
