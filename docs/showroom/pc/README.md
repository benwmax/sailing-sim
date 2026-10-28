# Showroom, PC PR 2: the Boat screen

The Boat screen from `Inputs/ui-showroom/brief.md` (inputs branch, 2a782cdf), sections 2, 3 and 5, on the Mac's wiring
(`docs/showroom-wiring/`: `FSailShowroom`, the showroom stage, `ShowBoat`). The layout follows Bean's mockup. The boat owns
the middle of the screen, as on a racing game's car select.

## The screen (`SailFrontEnd.cpp` `BuildBoat`)

- **Top left:** "Fleet of eight" over "CHOOSE A BOAT" at 44 px, smaller than before. The step tracker sits top right.
- **Left column (380 px):** her type line, her name at 80 px, the "Your lesson boat" pill (or the certificate that opens
  her), her description and her flags.
- **Right column (330 px panel):** Length, Beam, Weight and Close-hauled at 12 kn, each a value plus a bar scaled to the
  fleet's biggest (the prologue's maxi left out), then the handling pips, the polar note and Next.
- **Under the boat:**
  - where the camera stands ("View from starboard quarter", from `GetShowroomViewBearing`);
  - ← and → buttons that turn it 30 degrees for the mouse;
  - an Auto spin switch (on by default; off leaves the camera where it is);
  - Reset view.
- **Bottom strip:** the eight boats as compact cards (silhouette and name), with Q/LB and E/RB at the ends.
  - Focus is the selection: moving along the strip shows that boat (the Mac's debounce, async load and build in place).
  - Enter, or a click on the shown boat, moves on to Conditions.
  - A boat loading shows "Loading · · ·" on her card.
  - A locked boat can still be looked at. Her card says Locked, the pill says which certificate opens her, and Next does
    nothing on her.
  - The prologue's maxi is not in the strip (brief section 8: "Fleet of eight").
- **View mode:** V or the controller's View button hides every panel but her name and the prompts. V, View, Esc or B
  bring the panels back.
- **The backdrop** (Bean, Oct 27): on this screen there is no left-heavy wash. There are soft vignettes top and bottom, and
  a light fade behind the left column that ends at its right edge (460 px of 1440, scaled with the width). It never reaches
  the boat's side.
- **The swap's dip:** the moment the new boat is built the screen is dark (60%), and it clears over 150 ms.

## Input (the menus have focus, so the screen forwards it to the camera)

`ASailboatPawn::ShowroomLook`, `ShowroomZoom`, `ShowroomResetView` and `SetShowroomAutoSpin` go to the free camera's orbit:

| Action | Keyboard / mouse | Controller |
| --- | --- | --- |
| Turn | drag on empty space (left button), or ← / → | right stick (90 deg/s) |
| Zoom | the wheel | LT out, RT in |
| Reset view | Home | R3 |

Any look stops the auto spin until the idle delay (the camera's own rule: 4 s).

`-SailingUIScript` gained `Cmd:<console command>` ('+' for spaces), outside Shipping builds only. It is how the cycle
below takes its memreport.

## Numbers (PC, packaged Development build of this branch, Ultra, every boat cycled in the strip)

| Swap | Load | Build | Shown after focus (with the 200 ms debounce) |
| --- | --- | --- | --- |
| J/22 → Sunfish | 24 ms | 56 ms | 280 ms |
| → ILCA 7 | 5 ms | 55 ms | 260 ms |
| → Catalina 22 | 0 ms | 149 ms | 349 ms |
| → Catalina 30 | 0 ms | 272 ms | 472 ms |
| → Hobie 16 | 9 ms | 106 ms | 315 ms |
| → Corsair 880 | 24 ms | 136 ms | 360 ms |
| → Lagoon 42 | 27 ms | 174 ms | 401 ms |
| → J/22 | 0 ms | 133 ms | 333 ms |

- **Swap times:** every boat is under the brief's 800 ms. Against the PC's own 400 ms, the Catalina 30 (472 ms) and the
  Lagoon 42 (401 ms) are over. Their time is in the build (`SetBoat`'s visuals), not the load; the Mac's lane owns
  `SetBoat`.
- **Memory** (`memreport -full`): 3,659 MB used and 3,832 MB peak after cycling all eight, against 3,704 MB used and
  4,326 MB peak sailing the Lagoon 42 in game. That is inside the brief's budget (the in-game peak plus 150 MB).

## Stills (Ultra, `-SailingFreeSail=1 -SailingFrontEnd=Boat`, the strip moved by `-SailingUIScript`)

- `boat-j22-1440.jpg`, `boat-j22-1920.jpg`: the J/22, the default.
- `boat-sunfish-1440.jpg`: the dinghy (E once).
- `boat-lagoon-1440.jpg`, `boat-lagoon-1920.jpg`: the Lagoon 42 (Q once, round to the end of the strip).
- `boat-viewmode-1920.jpg`: View mode (V).

I couldn't try mouse drag, wheel and clicks here: this PC sends no synthetic input. They are Bean's to try.

## Not in this PR

- Depth of field in the showroom (optional on High and Ultra per the brief): left for later.
- The Conditions screen: PR 3, pc/showroom-conditions.
