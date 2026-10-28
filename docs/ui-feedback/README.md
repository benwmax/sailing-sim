# Settings tabs and the world cards (Bean's UI feedback, Oct 27 2026)

Two changes in `SailFrontEnd.cpp`/`.h`:

- **Settings tabs are clickable.** Each tab pill is a button, and so are the Q and E keycaps either side. The pills, the
  keycaps, Q/E and LB/RB all go through `SetSettingsTab`. It rebuilds the screen, and the new tab's first row takes the
  focus once it is laid out (`Show`'s active timer).
- **The world cards' descriptions scroll.** Each card's text sits in a scroll box in its 80 px, with a thin bar that only
  shows when there is more, and a "Read more ↓" line while text runs on below. It scrolls with:
  - the mouse wheel over the card;
  - Up and Down, the D-pad, and Page Up and Page Down on the focused card;
  - the right stick, smoothly. The left stick and Left and Right still move between cards.

  Credits and the cards share one stick-scroll path (`ActiveScroll`, `ScrollActive`). The World screen's footer gains a
  "↑ ↓ Read more" prompt.

Stills (1920x1080, `-SailingFrontEnd=Settings|World`, keys sent through Slate by `-SailingUIScript`):

- `settings-graphics.jpg`: the Settings screen with the pill row and the Q and E buttons.
- `settings-display-after-keys.jpg`: after E, E, Q, on Display.
- `world-cards.jpg`: the four cards, each with "Read more" where its text runs on.
- `world-cards-scrolled.jpg`: after Down, Down on the focused card, which shows the end of its text.

Mouse clicks on the tabs and the wheel over a card were not driven here (no synthetic mouse input); they are Bean's to try.
