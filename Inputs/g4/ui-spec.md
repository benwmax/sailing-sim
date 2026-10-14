# G4 front end and HUD: implementation spec

For: the Mac session building phase G4 of benwmax/sailing-sim (Unreal 5.8.3, Common UI + UMG).
Mockup: https://claude.ai/artifact/DjquUz6DnoQ45rYFFJQ2Ds (source: `sailing-sim-g4/sailing-sim-front-end.html` next to this file).
Written 2026-10-13 in a cloud-only thread with no access to the Unreal project. Every binding below names the game state it needs in plain terms plus a suggested property name. **Where the repo already has a type or field for it, use the repo's; the names here are suggestions, not existing code.** Known from the build history: worlds are data in one map selected by `-SailingWorld`; `FWeatherSystem` drives wind, gusts, storms, sky; launch spots, drills, traffic, race, chart (P), logbook (Y), photo mode (9), cockpit camera (\), bearings (U/O/I), boat keys (N, M, J, X, =, -, [, ]) and the Low/Medium/High tiers exist.

---

## 1. What G4 delivers

1. A front end that replaces the current menus: Title, World, Launch spot, Boat, Conditions, Mode, Loading.
2. A new in-game HUD: compass tape, heading, environment strip, learning tip card, drill or race panel, toast line, sail trim panel, instrument cluster (speed, apparent wind, depth), minimap, key hints.
3. Pause, Settings (five tabs) and Controls (rebinding) screens, reachable from the title and from pause.
4. Level select: choosing a world sets the session config and reloads the map with that world. No new maps.
5. Full controller navigation with glyphs that follow the last input device, and keyboard/mouse everywhere.
6. A Low quality treatment (section 9) and a fifth quality preset, Ultra, for the RTX 4090 PC (section 8.3).

Out of scope: chart view, logbook and photo mode screens themselves (they keep their current UI and are opened from pause), touch controls, localisation beyond keeping all text in a String Table.

---

## 2. Architecture

### 2.1 Plugins and settings
- Enable **CommonUI**, **ModelViewViewModel** (UMG Viewmodel), **EnhancedInput** (already used), **CommonLoadingScreen** (copy from the Lyra sample project into `Plugins/`; it is Epic sample code licensed for UE projects). If copying Lyra code is unwanted, fall back to `MoviePlayer` with a Slate loading widget; the visual spec in 5.7 is the same.
- Project Settings > Engine > General: Game Viewport Client Class = `UCommonGameViewportClient`.
- Project Settings > Common Input: Platform Input > Mac and Windows: Default Input Type Mouse and Keyboard, Supports Gamepad true, Enable Enhanced Input Support true. Input Data = `BP_SailUIInputData` (Default Click = `IA_UI_Confirm`, Default Back = `IA_UI_Back`).
- Controller data: `CD_Keyboard`, `CD_XboxPad`, `CD_DualSense` (`UCommonInputBaseControllerData`), each with a glyph brush set. Glyph art: plain rounded keycaps for keyboard; coloured face buttons (A green, B red, X blue, Y yellow, matching the mockup) for Xbox; shapes for DualSense.

### 2.2 Layers
One root layout widget `W_SailRootLayout` (`UCommonActivatableWidget`) added to the viewport by the PlayerController on BeginPlay, containing four `UCommonActivatableWidgetStack`s, bottom to top:

| Layer | Stack name | Holds | Input mode while top |
|---|---|---|---|
| Game | `Stack_Game` | `W_HUD` | Game |
| GameMenu | `Stack_GameMenu` | Pause, Settings, Controls when opened in game | Menu, game paused |
| Menu | `Stack_Menu` | Title and session setup screens, Settings and Controls from title | Menu |
| Modal | `Stack_Modal` | Confirm dialogs, keep/revert resolution, rebind conflict | Menu |

Push with `PushWidget` by class; Back pops (`bIsBackHandler = true` on every screen except Title and HUD). The setup flow is one stack: World, Launch, Boat, Conditions, Mode each push the next, so Back walks the flow in reverse with state kept.

### 2.3 Session config and level select
One struct carries every front-end choice into the game. Suggested:

```cpp
USTRUCT(BlueprintType) struct FSailSessionConfig {
  FName WorldId;            // "RayHubbard" | "Galveston"  -> -SailingWorld value
  FName LaunchSpotId;       // e.g. "rcyc.dock.b.n18"
  FName BoatId;             // "J22","Sunfish","ILCA7","Catalina22","Catalina30","Hobie16","Corsair880","Lagoon42"
  FSailConditions Conditions;
  ESailMode Mode;           // Free, Drill, Race, Passage
  int32 DrillIndex;         // 0..5, Drill mode only
  FName RaceCourseId;       // Race mode only
  bool bLearningMode;       // Learning explains, Game scores
  ESailDifficulty Difficulty; // Easy, Realistic
  bool bLearningTips;
  ESailTraffic Traffic;     // Off, Light, Busy
};
USTRUCT(BlueprintType) struct FSailConditions {
  float TrueWindFromDeg; float WindKn; float GustKn;
  ESkyType Sky;             // Clear, Fair, Overcast, Storms, Fog
  float LocalHour; int32 Month; int32 Day; float AirTempF;
  ETideState Tide;          // Galveston only
  float LakeLevelFt;        // Ray Hubbard only, offset from normal pool
  FName PresetId;           // NAME_None once the player edits a value
};
```

- Owner: `USailSessionSubsystem` (GameInstance subsystem). It keeps `PendingConfig` while in menus and `ActiveConfig` once loaded, and saves the last `ActiveConfig` to the save game for Continue.
- Start (Cast off): `USailSessionSubsystem::StartSession(PendingConfig)` builds the travel URL `"/Game/Maps/<CurrentMap>?SailingWorld=<WorldId>?Spot=<LaunchSpotId>?Boat=<BoatId>"` and calls `ServerTravel`/`OpenLevel`. The GameMode reads the options in `InitGame` (same path `-SailingWorld` uses today) and pulls the rest of the config from the subsystem. If the current world can be swapped in place without a reload, prefer that and skip the map load; the loading screen still shows while streaming completes.
- Pause > Change conditions edits `ActiveConfig.Conditions` and calls the weather system's apply function without a reload.
- Title is its own lightweight state: the same map with `-SailingWorld` set to the last world, camera on a slow orbit of the marina, no player boat physics. If that costs too much on Low, use a static image (section 9).

### 2.4 Viewmodels (MVVM)
Use `UMVVMViewModelBase` with `FieldNotify` properties; widgets bind in the UMG View Bindings panel, one-way to widget unless noted. Viewmodels are created by the subsystems and handed to widgets with `SetViewModel`, so widgets never reach into actors.

| Viewmodel | Created by | Source of truth |
|---|---|---|
| `VM_Session` | `USailSessionSubsystem` | `PendingConfig` / `ActiveConfig` (two-way from setup screens) |
| `VM_Catalog` | `USailSessionSubsystem` | Worlds, launch spots, boats, presets, drills, race courses from data assets (2.5) |
| `VM_Boat` | Player pawn on possess | Boat physics state, sails, instruments |
| `VM_Environment` | Weather/time system | True wind, gust, sky, temperature, time, tide, current |
| `VM_Coach` | Learning tips system | Current tip, drill objectives, race state, toasts, score |
| `VM_Settings` | `USailGameUserSettings` | Graphics, display, audio, gameplay, accessibility values |
| `VM_Bindings` | `UEnhancedInputUserSettings` | Mappable keys per context |

HUD numbers update through FieldNotify at most at 10 Hz (instrument damping matches a real B&G/Garmin display and keeps text from flickering). Compass tape and dials animate at frame rate via material parameters, not text.

### 2.5 Data assets
- `DA_World_RayHubbard`, `DA_World_Galveston` (`USailWorldDefinition`): display name, tagline, description, four facts (value + label), card image (render target capture or texture), loading images, map texture for the launch screen plus map bounds in world units, launch spot list, `bHasTide`, `bHasLakeLevel`, available modes.
- `USailLaunchSpot` rows: Id, display name, one-line description, start type (Dock, Beach, Under sail, Passage start, Arrival), tag (Home, Busy, none), world location (for the pin), heading.
- `DA_Boat_*` (`USailBoatDefinition`): display name, type line, description, LOA, beam, draft, displacement (display strings in feet/inches and lb, plus metric), close-hauled speed at 12 kn true read from the boat's polar, handling rating 1 to 5, feature flags (Spinnaker, Capsize, Outboard, Inboard, Twin engines, Wheel, Reef, Trapeze, Hiking), card icon, 3D preview mesh.
- `DT_ConditionPresets`: Id, name, summary line, world filter (Both, Galveston), `FSailConditions` values. Ship these six:

| Preset | Wind | Gust | Sky | Time | Date | Temp | Tide | World |
|---|---|---|---|---|---|---|---|---|
| ASA 101 lesson day | 10 kn from 180° | 13 | Fair | 10:00 | Apr 18 | 74°F | Flooding | Both |
| Typical July afternoon | 12 kn from 170° | 20 | Storms (cell after 16:00) | 14:30 | Jul 15 | 98°F | Flooding | Both |
| Glassy morning | 2 kn from 120° | 4 | Clear, haze | 07:30 | Aug 9 | 79°F | Slack low | Both |
| Blue norther | 20 kn from 0° | 28 | Overcast | 11:00 | Nov 22 | 48°F | Ebbing | Both |
| Bay sea breeze | 14 kn from 140° | 18 | Fair | 15:00 | Jun 20 | 88°F | Ebbing | Galveston |
| Live from today | from the weather station history the Phase 8 kit lists | | | now | today | | from NOAA | Both |

"Live from today" uses whatever historical station data is already in the project; if none is bundled, it picks today's date and the climatological average for the hour, and the summary line says so.

---

## 3. Tokens

All sizes are Slate units at the 1920×1080 reference. DPI scaling (Project Settings > User Interface): DPI Scale Rule = Shortest Side, curve points (1080, 1.0), (1440, 1.333), (2160, 2.0), (720, 0.667). A 4K monitor gets the same layout at twice the pixels, which is how the mockup scales. Minimum body text at 1080p is 16; nothing in the HUD smaller than 11.

### 3.1 Colour (`DA_SailUIStyle` or a `UCommonUIStyle` set of named FLinearColors)

| Token | Hex / RGBA | Use |
|---|---|---|
| `Ink` | #0A141C | Screen ground behind menus where no world shows |
| `Panel` | #0D1D28 at 80% | Glass panels over the world |
| `PanelSolid` | #102130 | Panels on Low quality and opaque cards |
| `Raise` | #17303F | Keycaps, chips, unselected segments |
| `Line` | #2B4554 | Borders, tracks, dividers |
| `Fg` | #EAF0F2 | Primary text |
| `Muted` | #93A8B4 | Secondary text |
| `Dim` | #71889A | Tertiary labels, upcoming steps |
| `Accent` | #F4C430 | Focus ring, primary button, progress, current step (Q-flag yellow) |
| `AccentInk` | #1D1600 | Text on Accent |
| `Selected` | #EAF0F2 at 75% | Edge of the chosen card; chosen items also get a yellow ✓ |
| `Chart` | #D14F9B | Map pins, routes, ship channel, chart compass rose |
| `Water` | #2F6F97 | Map water |
| `Land` | #CDBF98 | Map land (chart buff) |
| `Port` | #E2483D | Port side, port-side sectors and lights only |
| `Starboard` | #2DB36A | Starboard side; also "objective done" ticks |
| `Warn` | #FF9A2E | Shallow water, low fps, key conflicts |
| `WindTrue` | #9FD3FF | True wind arrows everywhere |

Rules: yellow means "where you are" (focus) or "do this" (primary). A chosen-but-not-focused item never uses yellow for its border, only the white edge and tick, so focus and selection never look alike. Red and green are reserved for port and starboard; when Accessibility > Port and starboard colours is set to a shapes option, every red element also gets a square and every green a triangle, and the blue/orange option swaps the two colours.

### 3.2 Type
Fonts are SIL Open Font License (Google Fonts); import TTFs as Font Face assets (Runtime) and make three composite Font assets.

| Token | Font | Weight | Size @1080 | Case / tracking | Use |
|---|---|---|---|---|---|
| `Logo` | Saira Condensed | Bold | 120 | Upper | Title logo |
| `ScreenTitle` | Saira Condensed | SemiBold | 60 | Upper, +2% | Screen headings |
| `CardTitle` | Saira Condensed | SemiBold | 38 / 30 / 22 | Upper | World, boat, mode, drill titles |
| `MenuItem` | Saira Condensed | SemiBold | 30 | Upper, +4% | Title and pause menus |
| `Eyebrow` | Saira Semi Condensed | SemiBold | 14 | Upper, +18% | Kickers above titles; Accent colour |
| `Label` | Saira Semi Condensed | SemiBold | 12 | Upper, +14% | Field and instrument labels |
| `Ui` | Saira Semi Condensed | Medium | 17 | Normal | Row names, buttons (buttons Upper +6%, 19) |
| `Value` | Saira Semi Condensed | SemiBold | 19 | Tabular figures | Slider values, specs |
| `InstrumentBig` | Saira Semi Condensed | SemiBold | 48 | Tabular figures | Speed, depth |
| `Body` | Source Sans 3 | Regular | 17 | Normal, line height 1.45 | Descriptions, tips |
| `Small` | Source Sans 3 | Regular | 14 | Normal | Secondary lines |

Make each a `UCommonTextStyle` (`TS_Logo`, `TS_ScreenTitle`, ...). Saira has tabular figures via OpenType `tnum`; if the Slate shaper ignores it, use Saira Semi Condensed's monospaced digits by setting the composite font's digit range to a tabular subset, or right-align numbers in a fixed-width box so they do not jitter.

### 3.3 Spacing, shape and motion
- Spacing scale: 4, 8, 12, 16, 20, 24, 32, 48, 64. Screen safe margin 64 left/right, 50 top; HUD edge margin 30. Honour `Safe Zone` for TVs.
- Radius: 5 for buttons and rows, 7 for cards, 999 for pills. Border 1 px `Line`.
- Focus: 3 px `Accent` outline plus a 26 px `Accent` glow at 35% (`UCommonBorderStyle` `BS_Focus`). Menu list items show focus as a 4 px left bar and a yellow-to-transparent fill instead of an outline.
- Glass: panels use a Background Blur of strength 15 under `Panel`. Low quality drops the blur (section 9).
- Motion: screen push is a 180 ms fade plus 24 px slide from the right; pop is the reverse. Focus moves snap with no tween. Toasts slide 12 px down and fade in 200 ms, hold 3 s, fade 400 ms. Respect Accessibility > Camera motion = Reduced by turning UI slides into fades.

### 3.4 Shared widgets
| Widget | Base | Notes |
|---|---|---|
| `W_ScreenHeader` | UserWidget | Eyebrow, title, `W_StepBar` slot, tab list slot |
| `W_StepBar` | UserWidget | Five steps (World, Start, Boat, Conditions, Mode); states done, current, upcoming |
| `W_PromptBar` | `UCommonBoundActionBar` | Footer; shows actions bound on the active screen plus a right-side hint text |
| `W_MenuItem` | `UCommonButtonBase` | Title and pause menus; label + optional right sub text |
| `W_CardButton` | `UCommonButtonBase` | World, boat, preset, mode, drill, launch spot; Selected state via `SetIsSelected` |
| `W_SliderRow` | `UCommonButtonBase` | Name, track, value; consumes Left/Right (override `NativeOnNavigation`, step on each press, repeat at 8 Hz after 350 ms hold); mouse drag on track |
| `W_ChipRow` | `UCommonRotator` | Name + chips; Left/Right cycles |
| `W_SegmentToggle` | `UCommonRotator` | Two or three segments (Learning/Game, Easy/Realistic, On/Off, Off/Light/Busy) |
| `W_SettingRow` | `UCommonRotator` | ◀ value ▶ with position dots; marks changed rows with a yellow dot |
| `W_Pill` | UserWidget | Small upper-case tag; Accent variant for Home and "Your lesson boat" |
| `W_KeyCap` | `UCommonActionWidget` | Glyph for an input action from the active controller data |

---

## 4. Input

### 4.1 UI input actions (Enhanced Input, context `IMC_UI`, priority above gameplay while a menu is active)

| Action | Keyboard / mouse | Controller | Notes |
|---|---|---|---|
| `IA_UI_Confirm` | Enter, Space, left click | A / Cross | CommonUI default click |
| `IA_UI_Back` | Esc, Backspace, right click | B / Circle | CommonUI default back |
| `IA_UI_TabPrev` / `IA_UI_TabNext` | Q / E | LB / RB | Settings and Controls tabs |
| `IA_UI_Secondary` | I | X | Boat: Inspect in 3D; Loading: Next tip |
| `IA_UI_Tertiary` | R | Y | Conditions: Randomise; Settings: Reset tab; Controls: Reset to default |
| `IA_UI_Zoom` | Z, mouse wheel | Right stick | Launch map zoom |
| `IA_UI_Start` | Enter on Mode | Menu | Cast off from anywhere on the Mode screen |

Arrow keys, WASD in menus, D-pad and left stick drive Slate navigation (CommonUI analog cursor off; focus-based navigation only, the mouse hovers to move focus as in the mockup).

### 4.2 Gameplay toggles the HUD needs (add to the existing gameplay context)
| Action | Default key | Controller | Effect |
|---|---|---|---|
| `IA_Pause` | Tab, Esc | Menu | Opens Pause (replaces the old Tab menu; Traffic, Race and Keys move into the front end and Pause) |
| `IA_ToggleTips` | T | LB + Y | Show/hide learning tip card |
| `IA_CycleHud` | H | LB + View | Full, Minimal, Off |

Existing keys stay as they are. The Controls screen lists them from Enhanced Input player-mappable key settings (4.3), so nothing is hardcoded in UI.

### 4.3 Rebinding
- Mark every gameplay Input Action that players may rebind with `PlayerMappableKeySettings` (Name, Display Name, Display Category = Sailing / Boat systems / Camera and views / Menus).
- Enable `UEnhancedInputUserSettings` (Project Settings > Enhanced Input > User Settings), one key profile per device kind; the Controls screen reads `GetActiveKeyProfile()` rows and writes with `MapPlayerKey` / `UnMapPlayerKey`, then `SaveSettings`.
- Conflict rule: a key already used in the same Display Category opens `W_Modal_KeyConflict` ("R is already Reef in Sailing. Press R again to move it here and leave Reef unbound, or Back to cancel."). Across categories, duplicates are allowed.
- Esc and the controller Menu and B buttons cannot be rebound away from Pause/Back.

---

## 5. Screens

Each screen lists: class, widget tree in order, bindings, focus order (the numbers the mockup shows with "Show focus order") and actions on the prompt bar. "Default focus" is what `GetDesiredFocusTarget` returns on activation; on re-activation focus returns to the last focused widget.

### 5.1 Title (`W_Title`, Menu stack root, not a back handler)
- Background: live title camera (2.3) or Low image; left gradient `Ink` 86% to 15% so text reads on any sky.
- Tree: Logo ("SAILING SIM", `TS_Logo`), subtitle "LAKE RAY HUBBARD · GALVESTON BAY" (`Eyebrow` style in `Muted`, +32% tracking), menu list, Continue card (bottom right), build label (top right).
- Menu items and actions:
  1. Continue: sub text = last boat · last launch spot short name; starts `StartSession(LastConfig)` directly to Loading. Hidden if no save.
  2. Sail: push World with a fresh `PendingConfig` (defaults: last world, J/22, ASA 101 lesson day, Free sail, Learning, Easy, tips on, Light traffic).
  3. ASA 101 Drills: same as Sail with Mode = Drill, DrillIndex = first not-passed drill. Sub text "6 drills · N passed" from the drill progress save.
  4. Race: Sail with Mode = Race. Sub text "vs five AI boats".
  5. Logbook: opens the existing logbook UI. Sub text "N sessions · X nm" from logbook totals.
  6. Replays: opens the existing replay browser. Sub "Ghost boat".
  7. Settings: push Settings on the Menu stack.
  8. Quit: Modal confirm "Quit Sailing Sim?" (Quit / Cancel).
- Continue card binds `LastConfig`: "Last session · <date>", "<Boat> on <World>", detail line "<spot> · <wind> kn <dir> gusting <gust> · <sky> · <Learning|Game> mode, <difficulty>." plus "Drill N, <name>, was in progress." when relevant. Not focusable; Continue in the list is its action.
- Focus: 1 to 8 top to bottom, wraps. Default focus Continue (or Sail if no save).
- Prompts: Confirm "Select", Back "Quit".

### 5.2 World (`W_WorldSelect`)
- Header: eyebrow "New session", title "Choose a world", step bar at 1.
- Two `W_CardButton` world cards side by side, from `VM_Catalog.Worlds`: art (card image) with tag pill top-left ("Fresh water · No tide" / "Tide · Current · Ship traffic"), name, description (max 3 lines), four facts.
  - Ray Hubbard facts: 22,745 acres; 4 launch spots; 6 ASA 101 drills; 435.5 ft normal pool.
  - Galveston facts: 582 aids to nav; 5 launch spots; 45 nm Gulf passage; 1°28′ E variation.
  - Launch spot count and drill count are computed from data, not typed.
- Confirm sets `PendingConfig.WorldId`, resets `LaunchSpotId` to the world's first spot, and pushes Launch. Changing world also swaps the menu background to that world's art.
- Focus: 1 Lake, 2 Galveston. Default = current `WorldId`.
- Prompt hint (right): "Worlds load from the same map; switching takes about 20 s on the Mac" (replace 20 s with the measured figure, or drop the number).

### 5.3 Launch spot (`W_LaunchSelect`)
- Header: eyebrow = world name, title "Where do you start?", step 2.
- Left (60%): `W_LaunchMap`, an image of the world's chart-style map with `Chart` pins placed by projecting each spot's world location through the world's map bounds. Map style for both worlds: `Land` land, `Water` water, `Chart` routes (Ray Hubbard: deep-water route down the old river channel; Galveston: Houston Ship Channel dashed, Gulf passage dotted to Freeport), causeways/jetties in brown, a magenta compass rose, place names in upper-case tracked `Label` style. Bake this map texture offline from the existing chart data (chart view P already renders Galveston ENC data; Ray Hubbard from the terrain water mask); do not draw it live. Legend bottom-left.
- Pins: numbered circles (`Chart` fill, white ring), selected pin fills `Accent` with dark number, focused pin gets the yellow ring. Pins are focusable (`W_MapPin` buttons) so a controller can move on the map.
- Right (40%): one `W_CardButton` per spot: number disc, name, tag pill (Home / Busy / world name), detail line "<description> · <start type>"; then the primary button "Next: boat".
- Example spot data (use the real list in the repo):
  - Ray Hubbard: 1 Rush Creek Yacht Club, Dock B slip N18 (Home, Leave the dock); 2 Chandler's Landing, Rockwall; 3 Paddle Point Park, Rowlett (Beach launch); 4 Mid-lake north (Under sail).
  - Galveston: 1 Kemah · Clear Lake (Busy); 2 Galveston Yacht Basin; 3 Texas City Dike; 4 Galveston entrance (Passage start); 5 Freeport (Arrival).
- Focus: pins 1..N first, then list 1..N, then Next. Up/Down inside the list, Left/Right jumps between a pin and its list row (explicit nav rule: pin k ↔ row k). Selecting a pin or row selects the spot and keeps focus; Next or Confirm on an already-selected item pushes Boat.
- Zoom (Z / right stick) scales the map 1× to 2.5× around the focused pin. Prompt hint: "Schematic map".

### 5.4 Boat (`W_BoatSelect`)
- Header: eyebrow "Fleet of eight", title "Choose a boat", step 3.
- Left: 4×2 grid of `W_CardButton` boat cards: silhouette icon, name (`CardTitle` 22), type line. Order: J/22, Sunfish, ILCA 7, Catalina 22, Catalina 30, Hobie 16, Corsair 880, Lagoon 42.
- Right: detail panel bound to the focused card (focus previews, Confirm selects): type line, name (`CardTitle` 38), flag pills (J/22 also gets the Accent "Your lesson boat" pill), description, spec table (Length, Beam, Draft, Weight, Close-hauled at 12 kn, Handling meter 1 to 5), buttons "Inspect in 3D" and primary "Next: conditions".
- Example figures in the mockup (check each against the boat's definition and physics config; three boats were flagged in V7 for beam/length mismatches):

| Boat | Type | LOA | Beam | Draft | Weight | Flags |
|---|---|---|---|---|---|---|
| J/22 | Keelboat · 3 to 4 crew | 22′6″ | 8′0″ | 3′9″ | 1,790 lb | Spinnaker |
| Sunfish | Dinghy · single-handed | 13′9″ | 4′1″ | 2′11″ board | 130 lb | Capsize, Lateen rig |
| ILCA 7 | Olympic dinghy · single | 13′10″ | 4′6″ | 2′9″ board | 130 lb | Capsize, Hiking |
| Catalina 22 | Trailerable keelboat | 21′6″ | 7′8″ | 1′8″ swing keel up | 2,490 lb | Outboard, Reef |
| Catalina 30 | Cruiser · ASA 103 | 29′11″ | 10′10″ | 5′3″ | 10,200 lb | Inboard, Wheel, Reef |
| Hobie 16 | Beach catamaran | 16′7″ | 7′11″ | 10″ rudders up | 320 lb | Capsize, Trapeze |
| Corsair 880 | Trailerable trimaran | 28′10″ | 20′0″ | 5′7″ board | 3,800 lb | Outboard, Spinnaker |
| Lagoon 42 | Cruising catamaran | 42′0″ | 25′3″ | 4′1″ | 26,000 lb | Twin engines, Wheel |

  "Close-hauled at 12 kn" reads the boat's polar at 12 kn TWS, optimum upwind angle. Handling is a designer rating in the boat definition.
- Inspect in 3D (X / I): pushes `W_BoatInspect`, a turntable of the boat's preview mesh in a small preview scene (left stick orbit, right stick zoom, Back returns). Reuse the boat-parts explorer idea: optional labels for the ASA 101 parts on the J/22.
- Focus: grid 1..8 row-major, then Inspect (9), Next (10). Right from the right column moves to Inspect. Default = selected boat.

### 5.5 Conditions (`W_Conditions`)
- Header: eyebrow "Weather and time", title "Set the conditions", step 4.
- Preset row: six `W_CardButton` preset chips (name + summary). Presets not available in this world are disabled with summary "Galveston only". Applying a preset copies its values; touching any control afterwards clears the preset selection (`PresetId = None`).
- Left column: wind dial (`W_WindDial`, focusable; Left/Right rotate 5° steps, hold to repeat; mouse click/drag sets the direction). Dial shows N/E/S/W, 10° ticks, a `WindTrue` arrow on the rim pointing at the centre from the direction the wind comes from, and centre text "SSE / 157° true". Below it a "What to expect" panel generated from the values (see rules below).
- Middle column: Wind speed (0 to 30 kn, step 1), Gusts to (wind to 40, step 1, never below wind), Sky (chips Clear, Fair, Overcast, Storms, Fog), Air temp (30 to 105°F).
- Right column: Time of day (05:00 to 22:00, 15 min steps), Date (month rotator, day kept), then per world:
  - Ray Hubbard: Tide row disabled with note "No tide on Lake Ray Hubbard. Lake level replaces it."; Lake level (−6.0 to +3.0 ft, 0.5 steps, relative to 435.5 ft).
  - Galveston: Tide (Slack low, Flooding, Ebbing, Slack high); Current row read-only from the NOAA current model: "From NOAA station at Galveston Bay entrance · <x> kn <flood|ebb> at this tide".
  - Then primary button "Next: mode".
- Bindings: every control two-way to `VM_Session.Conditions`. Units follow Settings > Gameplay (knots, mph or km/h; °F shown with °C in brackets when metric).
- "What to expect" text rules (String Table entries with format args):
  - Lead: "<wind> kn <dir>, gusting <gust>."
  - Wind band for the selected boat, using its reef and capsize thresholds from physics config: under 4 kn "Very light: expect to drift between puffs."; up to the boat's comfortable limit "Good learning breeze for the <boat>."; up to reef threshold "Fresh. Consider a reef on the <boat>."; above "Strong. Realistic mode will overpower the <boat> without a reef." (Dinghies say "capsize" instead of "overpower".)
  - Storms: "A storm cell builds after <hour> with a gust front of about <kn> kn." from the weather system's storm schedule.
  - Fog (Galveston): "Visibility under half a mile; sound signals and radar matter."
  - Sunset time for date and world latitude from the existing sun/moon code.
- Randomise (Y / R): picks plausible values for the world and month from the climatology used by the weather system.
- Focus: presets 1..6, dial 7, middle column 8..11, right column 12.. (disabled rows skipped), Next last. Left/Right adjust the focused control; Up/Down move. From a preset, Down goes to the dial or the column below it.

### 5.6 Mode (`W_ModeSelect`)
- Header: eyebrow "Last step", title "How do you want to sail?", step 5.
- Mode cards (4): Free sail, ASA 101 drills, Race, Passage. Passage is disabled on Ray Hubbard ("Galveston world only").
- Contextual row under the cards:
  - Drills: six drill buttons "N. <name>" with right label "Passed" / "Not yet" from drill progress. Names: Leave the dock, Points of sail, Tacking, Gybing, Crew overboard, Return to the dock (use the six that exist).
  - Race: course options from race data (e.g. windward-leeward 2 laps, triangle) plus "Five AI boats · <class>" and a Rules on/off row if the race code supports it.
  - Passage: start and finish (Galveston entrance → Freeport), "Chart fixes required" toggle.
  - Free sail: nothing.
- Toggles (2×2): Mode Learning/Game; Difficulty Easy sailing/Realistic hard; Learning tips On/Off (forced Off and disabled in Game mode, with the note "Tips off in Game mode"); Traffic Off/Light/Busy (Busy only shown where traffic supports it).
- Summary strip: World, Start, Boat, Wind, When, from `VM_Session`; and the primary button "Cast off".
- Focus: cards 1..4, contextual row, toggles row-major, Cast off last. Menu button / Enter on any item with `IA_UI_Start` casts off.
- Cast off: `StartSession(PendingConfig)`.

### 5.7 Loading (`W_Loading`, shown by CommonLoadingScreen during travel and until the game reports ready)
- Full-bleed loading image for the world (pick one of several per world: marina at golden hour, causeway, ship channel), darkened at the bottom-left.
- Bottom-left: eyebrow "<World> · <launch spot>", big title "<Boat>" line break "<drill name | mode name>" (`Logo` style at 80), sub line "<wind> kn <dir> gusting <gust> · <sky> · <date>, <time> · <Learning|Game> mode".
- Right: tip card (`Panel`): "Sailing tip · n of N", heading, small diagram image, body text. Tips come from `DT_LoadingTips`, filtered by world, boat and mode, never the same tip twice in a row. Seed the table from the ASA 101 Study Kit topics (points of sail, no-go zone, right of way, leaving a slip, heaving to, crew overboard, reefing, reading gusts, thunderstorm signs on Texas lakes).
- Bottom: stage label + percent + 4 px progress bar in `Accent`. Stages map to real readiness checks, in order: "Streaming shoreline and trees" (world partition streaming complete around the spawn), "Baking cloud weather map" (G1 weather map built), "Rigging the boat and crew" (boat actor and crew spawned), "Warming water and wake shaders" (PSO precache done for the world), "Placing traffic" (traffic manager spawned), "Ready". Progress is the share of completed checks plus the streaming percentage inside the first stage; never fake time.
- When ready: prompt "Start sailing" appears (Confirm). Hold the loading screen until the player confirms so the first frame they see is smooth; Settings > Gameplay gets "Start automatically when loaded" (default Off).
- X / I: next tip.

### 5.8 HUD (`W_HUD`, Game stack)
Layout at 1080p, edge margin 30. Everything below is bound to `VM_Boat`, `VM_Environment` and `VM_Coach`.

| Element | Position | Contents and binding |
|---|---|---|
| Environment strip | Top-left | Time (`LocalTime` HH:MM), True wind ("<TWS> kn <dir> G<gust>"), Sky ("<sky> · <temp>"); Galveston adds Tide ("Ebbing 1.4 kn") |
| Compass tape | Top-centre, 650 wide, 50 tall, edge fade | Tape scrolls with heading (magnetic by default; true if Settings says so; Galveston applies 1°28′ E); cardinal letters in `Accent`; tick every 5°, numbers every 30°; `WindTrue` mark at the true wind direction; yellow caret at centre. Implement as a material on an image (UV offset = heading/360) so it costs no layout per frame |
| Heading readout | Under the tape | "200°M" `Value` 20 |
| Learning tip card | Top-left under the strip, 400 wide | Eyebrow "Learning tip" (Accent), title, body, footer "Hide tips with T · Tips off in Game mode"; 4 px Accent left edge. From `VM_Coach.CurrentTip` (title, body, priority). New tip fades in; a tip stays at least 6 s unless a higher-priority one arrives. Hidden when tips off or in Game mode |
| Drill / race panel | Top-right, 365 wide | Drill: "ASA 101 drill n of 6", drill name, objective checklist (done = green tick and muted text, current = Accent box and bold, upcoming = outline), footer "<mode> · <difficulty>" and timer. Race: position, leg, distance to mark, start countdown (5:00 sequence with flags), penalties. Free sail: hidden. Passage: next waypoint, DTW, ETA |
| Toast line | Top-centre under heading | One-line events from `VM_Coach.Toasts`: "Good tack · lost 0.9 kn, back up to speed in 6 s", "Starboard! You are stand-on", "Shallow water ahead". Left edge colour: Starboard green for good, Warn for caution, Port red for a fault |
| Sail trim panel | Bottom-right above key hints, 290 wide | Point of sail and tack ("Close-hauled · starboard") from TWA bands; jib telltales (windward and leeward streamer lines; windward lifting = curl), main leech telltale, heel bar with the boat's optimum heel zone in green and the current heel marker |
| Instrument cluster | Bottom-centre | Speed panel (STW kn, `InstrumentBig`; sub "VMG <x> · target <polar target>"); apparent wind dial 200×200 (boat outline, red port and green starboard close-hauled sectors 20° to 60°, grey no-go 0° to 20°, Accent AWA arrow, small `WindTrue` TWA tick, text "<AWA>° S/P" and "APP WIND · <AWS> KN"); depth panel (depth below surface, ft; sub "Keel <draft> · alarm <n>"; turns `Warn` with border when under keel draft + 2 ft, flashes at keel draft + 0.5 ft) |
| Minimap | Bottom-left, 210 circle | North-up chart crop around the boat from the launch map texture, boat arrow (Accent), true wind arrow, nearby marks and buoys (red/green), traffic dots when traffic is on |
| Key hints | Bottom-right | Up to three contextual prompts from the current situation (Tack/Gybe when close-hauled or running, Chart, Pause; Right the boat when capsized; Engine keys at the dock). Uses `W_KeyCap` so glyphs follow the device |

HUD modes (H): Full; Minimal (cluster, compass, drill panel, toasts only); Off (toasts only, for photos and video). Settings > Display > HUD size scales the whole HUD 85% to 130% around each anchor.

Game mode adds a score line in the drill/race panel and turns the tip card off; the toasts then report points ("Clean tack +20").

Cockpit camera (\) and helm view keep the same HUD. Photo mode (9) hides the HUD entirely and restores the previous mode on exit.

### 5.9 Pause (`W_Pause`, GameMenu stack; pauses the game world, keeps recording the replay buffer frozen)
- Background: the game frame blurred (Background Blur 10) with `Ink` at 72%.
- Left: eyebrow "Paused · <time on the water>", title = drill name or mode, menu:
  1. Resume (pop)
  2. Restart drill / Restart race / Restart from launch spot (Modal confirm)
  3. Change conditions: pushes `W_Conditions` in "in-session" variant (no step bar, primary button "Apply"; applying calls the weather system and pops back to Pause)
  4. Chart (P): opens existing chart view
  5. Logbook (Y)
  6. Photo mode (9)
  7. Settings
  8. Controls
  9. Quit to title (Modal confirm "Leave this session? Your logbook entry is saved.")
- Right: stat tiles (Distance nm, Top speed kn, Tacks · gybes), and a coach summary panel from `VM_Coach.Summary` (drill progress sentence, one rule reminder relevant to what happened, e.g. starboard right of way after a crossing).
- Focus: menu 1..9. Back = Resume.

### 5.10 Settings (`W_Settings`, used from Title on the Menu stack and from Pause on the GameMenu stack)
- Header: eyebrow "Settings", title = current tab name, `UCommonTabListWidgetBase` with Q/E or LB/RB glyphs at both ends.
- Body: list of `W_SettingRow` (section headers as non-focusable text), right help panel bound to the focused row (title, explanation, and for Graphics the measured fps bar).
- Save model: `USailGameUserSettings : UGameUserSettings`. Changes apply instantly; resolution, window mode and HDR changes open `W_Modal_KeepDisplay` with a 15 s countdown and revert unless kept. Y / R resets the tab to defaults (Modal confirm).
- Tabs and rows:

**Graphics**
| Row | Options | Applies |
|---|---|---|
| Quality | Low, Medium, High, Ultra, Custom | Sets all rows below; Custom is shown automatically when any row differs from a preset |
| Clouds | Low, Medium, High, Ultra | G1 cloud trace resolution and steps |
| Water and wakes | Low, Medium, High, Ultra | FFT size, wake sim resolution, whitecaps |
| Shoreline and buildings | Low, Medium, High, Ultra | G2 house kit distance (Ultra/High: full detail within 400 m), tree density, Nanite foliage |
| Crew | Stylised, MetaHuman, MetaHuman + hair | Crew pipeline; hair only High/Ultra |
| Lighting | Baked, Lumen software, Lumen ray traced | GI method; ray traced needs hardware RT |
| Upscaling | Off, TAA 82%, TAA 67%, DLSS Quality (PC only, if the plugin is present), TSR | Screen percentage and method |
| Frame rate cap | 30, 45, 60, 120, Uncapped | `t.MaxFPS` |

Preset table (Crew/Lighting/Upscaling/Cap): Low = Stylised / Baked / TAA 82% / 60; Medium = MetaHuman / Lumen software / TAA 82% / 60; High = MetaHuman / Lumen ray traced / governor 82 to 100% / 60; Ultra = MetaHuman + hair / Lumen ray traced full / DLSS Quality or TSR 100% / Uncapped.
The help panel for Quality shows the measured fps from the last bench run for that preset (`docs/` bench output baked into a data table at build time): Medium "75 fps, Mac M5, slowest view", High "46.7 fps", Low and Ultra from their bench runs. Bar colour Starboard green at or above target, `Warn` below. Custom shows a live 2 s average instead.

**Display**: Resolution; Window (Windowed, Borderless, Fullscreen); HDR (Off, On, only when the display supports it); Brightness (−2..+2, exposure compensation); HUD size (85, 100, 115, 130%); HUD (Full, Minimal, Off).

**Audio** (sound classes from V7): Master; Wind and water; Boat and rigging; VHF radio chatter (On/Off); Coach voice (On/Off, only if a voice exists, else hide). Sliders 0 to 100 in steps of 5 with hold-repeat.

**Gameplay**: Speed units (Knots, mph, km/h); Depth units (Feet, Metres, Fathoms); Headings (Magnetic, True); Default camera (Helm, Cockpit, Chase); Steering assist (Off, Light, Strong; Easy difficulty defaults Light); Start automatically when loaded (Off, On); Pause when window loses focus (Off, On).

**Accessibility**: Port and starboard colours (Red and green; Red and green + shapes; Blue and orange + shapes); Text size (100, 115, 130, 150%, scales `Body`, `Small`, `Ui` styles only); Camera motion (Full, Reduced, Horizon locked; Reduced removes heel lean of the cockpit camera and UI slides); Subtitles for radio and coach (Off, On); Hold or Toggle for hold actions (hike, look).

- Focus: rows top to bottom; Left/Right change value; LB/RB change tab and focus the first row.

### 5.11 Controls (`W_Controls`)
- Header: eyebrow "Controls", title "Keys and buttons", tab list of Display Categories (Sailing, Boat systems, Camera and views, Menus).
- Body: grid Action | Keyboard | Controller. Each binding cell is a button; Confirm puts it into listening state ("Press a key…" / "Press a button…", pulsing `Accent` tint) and the next key or button press binds it. Back cancels listening. Conflicts per 4.3 tint the cell `Warn` and show the conflict panel in the right column.
- Right column: help text ("Select a key or button, then press the new one...", "Bindings are saved per device, so the Mac and the PC can differ.").
- Y / R: reset this category to defaults (Modal confirm).
- Rows come entirely from `VM_Bindings` (player-mappable keys), so the list stays right as actions are added. The mockup's steering and sheet keys (A/D, W/S, Q/E) are placeholders: show whatever the project's mapping context defines.
- Focus: Keyboard cell then Controller cell per row, row-major.

---

## 6. Controller focus rules (all screens)
- Every focusable is a `UCommonButtonBase` (or derived rotator); nothing relies on mouse-only hit areas.
- Initial focus on activation via `GetDesiredFocusTarget`; restore last focus on re-activation (`bAutoRestoreFocus`).
- Default Slate spatial navigation is fine in grids; add explicit rules where the mockup lists them (launch pin ↔ row, conditions preset → column below, Mode toggles → Cast off).
- Wrap vertically in single-column menus (Title, Pause); do not wrap in grids.
- Focus visual is always the yellow outline (or the yellow bar on menu items). Selected state is the white edge and tick. Hover with a mouse moves focus, so there is only ever one highlighted item.
- Footer prompt bar shows only actions the active screen handles, with glyphs for the current input type (`UCommonInputSubsystem::OnInputMethodChanged`).

---

## 7. Data the HUD needs that may not exist yet
Check each; add a getter where missing. All are cheap reads.
- Speed through water, VMG to wind, polar target speed for current TWA (polars exist; target = polar at current TWS and optimum angle).
- Apparent wind angle and speed at the masthead; true wind angle and speed.
- Heel angle and the boat's optimum heel band (add to boat definition: J/22 roughly 12° to 18°; dinghies flat; multihulls by hull flying).
- Jib and main telltale states (V3 cloth sails have ribbon telltales; expose windward/leeward stall booleans or a −1..1 flow value).
- Point-of-sail band from TWA: in irons 0 to 40°, close-hauled 40 to 55°, close reach 55 to 80°, beam reach 80 to 100°, broad reach 100 to 160°, running 160 to 180° (tune per boat; keep the label text matching the ASA 101 kit).
- Depth under the boat and keel draft.
- Drill objective list with done/current state; race state; passage waypoint state.
- Coach events for toasts and the tip queue, each with a priority and a minimum display time.

---

## 8. Quality tiers and the UI

### 8.1 Medium and High (default look)
Glass panels with Background Blur 15, title-screen live camera, loading images, toast and screen transitions as in 3.3.

### 8.2 Low
- Panels: `PanelSolid` fill, no Background Blur anywhere (blur is a full-screen pass per widget on Metal).
- Pause/settings dim: `Ink` at 88%, no blur.
- Title: static key art per world instead of the live orbit camera (skip loading the world until Cast off).
- Loading: static image, no Ken Burns pan.
- Animations: no screen slides (instant swap with a 100 ms fade), no pulsing, toasts appear without slide.
- HUD: compass tape and dials still update at frame rate (they are materials); numbers at 5 Hz; minimap updates at 5 Hz.
- Map and boat card art: use 1K textures instead of 2K.
- Invalidation: wrap static panels (`W_ScreenHeader`, card grids, prompt bar) in Invalidation Boxes and the HUD's static frames in a Retainer Box on Low.

### 8.3 Ultra (new, PC with RTX 4090)
- Shows in the Quality list only when the GPU reports hardware RT and at least 12 GB VRAM, or when the user picks Custom.
- No resolution governor, full hardware Lumen, strand hair on MetaHuman crew, full-resolution cloud trace, MegaLights, DLSS Quality if the DLSS plugin is installed (else TSR at 100%), uncapped frame rate.
- UI: same as High, and the Settings help panel says "Ultra: full hardware Lumen, strand hair, full-res clouds, no resolution governor. RTX 4090 PC."
- The Windows build is not set up yet (memory: Windows builds need the PC); Ultra can be added to the settings and scalability files now and verified when the PC build exists.

---

## 9. Performance budget for UI
- Menus: under 1.0 ms game thread and 0.6 ms GPU on Medium at 1440p on the Mac M5.
- HUD: under 0.35 ms game thread (Slate tick + paint) and 0.25 ms GPU. Budget the apparent wind dial and compass tape as materials; no per-frame text rebuilds above 10 Hz; no Canvas Panel deeper than two levels in the HUD.
- Use `stat slate` and `stat ui` in the bench run; add these numbers to the G4 gate report.

---

## 10. Acceptance checks for the G4 gate
1. Every screen in the mockup exists and is reachable with keyboard only, controller only, and mouse only.
2. Lake to Galveston and back from the front end, each with a different boat and preset, lands at the chosen launch spot with the chosen conditions (automation test `SailingSim.UI.SessionFlow`).
3. Continue resumes the last session config.
4. Glyphs switch within one frame of changing input device.
5. Rebinding a key, restarting the game, and checking the HUD hint shows the new key.
6. Changing quality preset in game changes the scene immediately; resolution change reverts after 15 s if not kept.
7. HUD values match the existing instrument and physics readouts (speed, AWA, depth) within display rounding.
8. Low quality: no Background Blur widgets active (`Slate.ShowBatching` or a widget reflector check), title shows static art.
9. UI frame cost within section 9 on Medium.
10. Screenshots of each screen at 1080p and 4K for Bean to compare with the mockup.

---

## 11. Questions for Bean (defaults in brackets; build with the default until answered)
1. Game name on the title screen: keep "Sailing Sim" or something else? [Sailing Sim]
2. Old Tab menu: replace it with Pause (Tab opens Pause) as specced? [yes]
3. Hold on the loading screen until "Start sailing" is pressed? [yes, with a setting to start automatically]
4. Coach voice lines: none planned, so the Coach voice audio row stays hidden. [hidden]
