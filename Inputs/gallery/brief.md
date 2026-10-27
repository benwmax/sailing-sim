# Asset gallery: implementation brief

For the build lanes (PC UI and graphics, Mac wiring and gate). Written Oct 27 2026 from main at 0f5aa252 (#356) and the
inputs branch at 2a782cd (showroom brief). Class names below are suggestions; the repo's real types win.

- Bean's ask (Oct 27 20:15 UTC, cmsg_01LZf6WW82DddXS8e3xrubuG2j6RDG4kd4wivaf38cW528): a Gallery, but not a free-fly
  past the assets. Same idea as the new boat showroom: a panel on the left to search and filter the assets, the selected
  asset on the right with zoom, pan and rotate, a full-screen view, and graphics settings in reach so he can see each
  asset at different fidelities.
- APPROVED by Bean (Oct 27 20:38 UTC, cmsg_01LZf6WW82DddXS8e3xrubuGPjWumUAcoxSc44mfT8ZKRu: "looks good").
- Clickable mockup: https://claude.ai/artifact/MLtw3UqhR9DWyMNvoZ2k7v (the shapes are browser stand-ins; the list uses
  the real folder names and paths from main; the tier look is imitated).
- Sequenced after the showroom PRs (`Inputs/ui-showroom/brief.md`): it reuses photo mode's `AFreeCamera` orbit mode
  (photo PR 1), the showroom's Slate-to-camera input forwarding (showroom PR 2), and for whole boats the showroom hold
  and async `SetBoat` (showroom PR 1). Keep it a small-to-moderate build: three PRs, the third optional.

## 0. Bean's answers (Oct 27 20:27 UTC, cmsg_01LZf6WW82DddXS8e3xrubuGWCsRuRFoPwvM84o5f38Ez2)

| # | Question | Decided |
|---|---|---|
| 1 | Shipped to players, or developer-only? | **Developer-only: Bean and internal devs.** Not in the players' menus (section 6). Every technical view is always on inside it. |
| 2 | What is behind the asset? | A studio backdrop by default, plus light presets: Studio, Noon on the lake, Golden hour, Overcast. |
| 3 | Which categories first? | Everything already in the cooked content: boats, deck hardware, houses and docks, trees, rocks and plants, buoys and marks, other vessels, landmarks, cars and trucks, crew gear. Crew bodies and faces later (private crew pack). |
| 4 | Graphics | Tier switch plus the main Settings > Graphics rows, and Compare tiers (same shot at two tiers side by side). **The graphics section must be collapsible / hidable.** |
| 5 | Technical views | Wireframe, detail level (LOD 0, LOD 1, Light twin, Far twin), stats. Collision later. **Also collapsible / hidable** (same rule as 4). |

## 1. What the code has today (main 0f5aa252)

- One map, `/Game/Maps/Lake`; the game mode spawns everything in code. The front end is `SSailFrontEnd`
  (`Private/UI/SailFrontEnd.cpp`, ~1950 lines), screens in `ESailScreen`, built by `Build<Screen>()`.
- Settings > Graphics (`BuildSettings`, case 0, from Bean's Oct 20 playtest, #192): Quality tier (choosing one resets
  every row to Auto), Anti-aliasing (DLSS modes where available), the Detail rows Shadows, Lighting, Reflections, Clouds,
  Water, Foliage, View distance (each Auto or a tier, `USailingSettings::*Quality`, -1 = Auto), Motion blur, Render scale,
  Frame cap. Every change calls `S->Save()` and `ASailingGameMode::ApplyQualitySettings()`, which sets engine
  scalability and the tier's console variables live, no reload.
- Cooked content (`DefaultGame.ini` `DirectoriesToAlwaysCook`): `/Game/World`, `/Game/Boats`, `/Game/Crew/Gear`,
  `/Game/Crew/Fabric`, `/Game/UI`, the MetaHuman crew folders. So every candidate asset is in a Shipping build already.
- Asset folders and counts on main (static meshes): `Boats/Kit` (SM_Kit_*, each with a `_Light` twin for AI boats),
  `Boats/<Type>` (SM_<Tag>_* parts per boat; hero J/22 in `Boats/J22Hero`), `World/Houses` (SM_HouseNear_* near-shore,
  SM_House_* far), `World/Trees` (SM_<Species>_0/_1 plus `_Far`), `World/Props` (rocks, reeds, deadfall), `World/Navaids`,
  `World/Vessels`, `World/Landmarks`, `World/Vehicles`, `Crew/Gear`. `World/Baked` (2,764) and `World/Far` (857) are
  baked terrain and marina tiles: not gallery material.
- Boats are not one mesh: `ASailboatPawn::SetBoat` → `RebuildBoatVisuals` assembles parts from `ModelMeshesFor`, and the
  sails and ropes are live cloth and `FRigLine`s.
- Launch args: `SailingArgs::Dev()` is filtered to the release smoke's switches in Shipping, so a `-Sailing...` dev
  switch does not reach a Shipping build. Bean plays the Shipping package on BEN-PC, so the developer views need a
  switch that works there (section 6).

## 2. Layout (mockup)

1440x1080 reference, the existing safe-zone and text-scale rules apply.

- Left panel, about 360 px, translucent like the showroom's columns (the fade stops at the panel's edge, per Bean's
  showroom note):
  - Eyebrow "DEVELOPER", title "GALLERY".
  - Search box: matches name, folder path, tags, category and world, every word must match ("live oak", "kit cleat").
  - Category chips with counts: All, Boats, Deck hardware, Houses & docks, Trees, Rocks & plants, Buoys & marks, Other
    vessels, Landmarks, Cars & trucks, Crew gear (plus Other, section 3).
  - Tag chips for the chosen category (Near shore, Far shore, Texas, Marseille, Gulf, Has light version, Has far version,
    Hero detail, ASA 101 ...). Tags AND together.
  - The list, grouped under sticky category headers: thumbnail, name, two tags, a HERO badge where it applies.
  - Footer: "N of M assets".
- Right, the viewer (the rest of the screen):
  - Top left: category, name at 44 px, one-line description, tags pill.
  - Top right: Light preset button (cycles), Compare tiers, Full screen.
  - Right column: Model stats card (triangles, detail level shown, levels, materials, size, used in, render scale, the
    asset path). Collapsible: its header folds it to one line.
  - Bottom left: orbit controls for mouse users (rotate left and right by 45 degrees, zoom out and in, Auto spin,
    Reset), and the angle and zoom readout.
  - Bottom right: "Graphics & view" card, collapsible (Bean, answer 4 and 5): its header folds it to one line. Inside:
    Tier Low / Medium / High / Ultra, and "More" which opens the main Settings rows (Shadows, Lighting, Reflections,
    Anti-aliasing, Render scale, Motion blur) plus "Restore my settings"; then View (Lit, Wireframe, Lit + wire) and
    Detail (Auto, LOD 0, LOD 1, Far / Light twin).
  - T / D-pad down folds or opens both the Graphics & view card and the stats card together; each header folds its own.
    The folded state is remembered (in the gallery's saved settings) between visits.
  - Prompt bar along the bottom, as on the other screens.
- Full screen (F, gamepad View): the left panel and the stats card go, the viewer takes the whole screen with the name,
  the toolbars and the prompt bar. A second press of View (or H) hides everything but the asset for a clean look; any of
  F, View, Esc or B steps back out. Same rule as the showroom's View mode.

Input (wired the same way as the showroom: `SSailFrontEnd` has focus and forwards to the camera):
- List: Up/Down or D-pad moves the selection and shows it (focus is the selection, debounced 200 ms like the showroom
  strip); Q/E or LB/RB change category; typing goes to the search box (or `/` focuses it); Enter or A on a row puts focus
  on the viewer.
- Orbit: left drag / right stick. Pan: right drag or Shift+drag / left stick (when the viewer has focus). Zoom: wheel /
  LT RT. Reset: R / R3. Graphics tier: G / Y cycles. Compare: C / X. Light preset: L / D-pad left-right on the viewer.
- Auto spin: on by default, 6 degrees a second after 4 s idle, off on any orbit input (showroom values).

## 3. Assets found automatically (never stale)

The gallery lists what is cooked, read from the asset registry at open time; no hand-kept list.

- `UGalleryIndex` (a small `UGameInstanceSubsystem`, or a namespace like `SailCatalog`): `IAssetRegistry::GetAssets`
  with an `FARFilter` for `UStaticMesh` under `/Game/Boats` and `/Game/World` and `/Game/Crew/Gear`,
  `bRecursivePaths = true`. Uses `FAssetData` only (no loads) to build the list: package path, asset name, tags.
  The cooked asset registry is in Shipping by default; confirm in the packaged check.
- One table maps folders to categories and to default tags, the only hand-written part:
  `Boats/Kit → Deck hardware`, `World/Houses → Houses & docks` (`HouseNear_` adds "Near shore", `House_` adds "Far
  shore"), `World/Trees → Trees`, `World/Props → Rocks & plants`, `World/Navaids → Buoys & marks`, `World/Vessels →
  Other vessels`, `World/Landmarks → Landmarks`, `World/Vehicles → Cars & trucks`, `Crew/Gear → Crew gear`. Excluded:
  `World/Baked`, `World/Far`, the boat part folders (boats come whole, below), material and texture assets.
  **A mesh in a folder the table doesn't name goes under "Other"**, so a new folder shows up the day it is cooked and the
  table gets a line later. The index logs "Gallery index: N assets, M categories, K in Other".
- Variants are grouped, not listed twice: `<Name>_Light` (kit twins for AI boats) and `<Name>_Far` (tree stand-ins)
  attach to their base entry and appear in the Detail picker. Numbered shapes (`SM_LiveOak_0`, `_1`) are separate
  entries ("Live oak 1", "Live oak 2").
- Display names: from a small optional names table (e.g. `HornCleat → Horn cleat`, `NotreDameGarde → Notre-Dame de la
  Garde`); without an entry, split the CamelCase. Descriptions are optional, also from that table.
- "Used in" (world tags Texas, Marseille, Gulf): from what each world's bake and kit placements reference, if it is
  cheap to read (the world JSON lists kit and landmark ids); otherwise leave it out of the first PR.
- Boats: from `SailCatalog` (the eight in the strip, the same names and descriptions as the showroom), not from folders.
- Crew: later. The MetaHuman folders exist only where the private crew pack is installed; when that step comes, list
  them only if the pack is mounted, and never put face stills in public PRs or docs (the repo is public).

## 4. The stage (where the asset is shown)

Stay in the Lake world: no new map and no travel, so opening the gallery is instant and the lake presets use the real
sky and water.

- `AGalleryStage` (spawned by the gallery on open, destroyed on close; client-side only):
  - A display `UStaticMeshComponent` that takes the selected mesh (async load, below), placed on a turntable root.
    The asset never moves; the camera orbits it.
  - Studio set: a cyclorama (curved floor-to-wall sweep, mid grey, rough) big enough to fill the frame at any orbit
    angle for assets up to about 30 m, and scaled up for vessels and landmarks (a 220 m tanker gets a ground plane and
    the sky; acceptable). Two or three local rect lights (key, fill, rim) with a lighting channel the world doesn't use,
    so the lake isn't lit by them. No new directional light. The stage sits somewhere the player never sees it: e.g.
    1 km above open water near the showroom spot (it hides the sky behind the cyclorama). Pick by eye.
  - Lake presets (Noon on the lake, Golden hour, Overcast): hide the cyclorama, put the asset at the showroom spot on the
    water (floating things: navaids and vessels sit at their waterline; shore things on a small patch of ground at the
    shore if one is near, otherwise on the dock), and set the time and sky through the showroom's
    `PreviewConditions` (12:00 Fair, 19:00 Clear, 15:00 Overcast); `EndPreview(false)` on close.
- Exposure: leave the tuned auto exposure alone (#345 "Truest" band). In the studio the metering may need a fixed
  compensation on the gallery camera's post-process; tune by eye on PC Ultra and Mac Medium.
- Loading: on selection (debounced 200 ms) `FStreamableManager::RequestAsyncLoad` the mesh (and its twins if a twin
  is picked), show it when loaded, release the previous handle. A spinner on the row while loading. No frame over 33 ms
  on Mac Medium while flicking down the list.
- Framing: from the mesh bounds: target the bounds centre, distance so the bounding sphere fills about 70% of the
  viewer's height (not the whole screen: the left panel is open), zoom 0.35x to 6x, pitch -10 to 80 degrees, default yaw
  135 degrees (three-quarter view), pan limited to the bounds' radius. Small parts (a 6 cm deck plate) need the near
  clip plane brought in (e.g. 1 cm) while the gallery is open.
- Camera: photo mode's `AFreeCamera` in orbit mode, with the showroom's added orbit parameters (target, yaw, pitch,
  distance, zoom range, lateral offset, auto spin). Add pan as a target offset in the camera's screen plane. The
  gallery forwards Slate input exactly like the showroom (the camera class never assumes its own input context).

## 5. Graphics in the gallery

- The tier switch and the "More" rows are the real settings: they write the same `USailingSettings` fields and call
  `ApplyQualitySettings()`, using the same choice lists as Settings > Graphics (share the code: lift the Detail lambda
  and the AA list out of `BuildSettings` into a helper both screens use, so the two pages can't drift).
- Snapshot the graphics fields on entering the gallery. "Restore my settings" puts them back. On leaving, if anything
  changed, ask once: "Keep these graphics settings?" Keep / Restore (default Restore, so a look at Ultra on a laptop
  doesn't stick).
- Compare tiers: freeze the camera, set tier A, wait for the frame to settle (about 1 s: Lumen and virtual shadow maps
  converge), capture the viewport into a texture, set tier B, settle, capture, restore the current tier, then show the
  two captures in Slate with a draggable split (labels "LOW" and "ULTRA", either side switchable). Any orbit input
  leaves compare mode. A ray-tracing toggle recreates render state and hitches; fine here, and it's why it's captures
  and not live. The captures are kept only in memory.
- The stats card's "Render scale" shows the effective screen percentage.

## 6. Developer-only access and the technical views

- Bean (answer 1): the gallery is for him and internal devs only. Its menu entry (Title > Gallery) shows only when a
  config flag `USailingSettings::bDeveloperTools` is set (saved in the user's ini, on no settings page), default off.
  Non-Shipping builds have it on. It has to work in Shipping (Bean plays the Shipping package on BEN-PC), so it is an
  ini line, not a `-Sailing...` argument (those are filtered in Shipping). Write the exact line in the PR and in
  docs/. Players never see the entry; the code and the stage ship but stay unreachable without the flag.
- Inside the gallery everything is on: no player/developer split.
- View modes: Lit; Wireframe and Lit + wire by an override material on the display component (a wireframe material),
  not the engine's wireframe view mode, which is stripped from Shipping.
- Detail: Auto; LOD n via `UStaticMeshComponent::SetForcedLodModel(n + 1)` for non-Nanite meshes; for Nanite meshes say
  "Nanite" and offer "Fallback mesh" instead of LOD numbers (the fallback is what ray tracing and Low tiers see). Twins:
  "Light (AI boats)" and "Far" swap the displayed mesh to the twin.
- Stats: triangles of the shown LOD (`GetRenderData()->LODResources[n].GetNumTriangles()`, or the Nanite resource's
  triangle count), number of LODs, material slots, bounds size in metres, the package path. "Used in" from section 3.
- Later, not in these PRs: collision view (simple and complex), UV checker, texel density.

## 7. Whole boats

- The eight boats come from `SailCatalog`. Studio: an `ABoatDisplay` that builds the same visual assembly as the
  pawn (factor the visual half of `RebuildBoatVisuals` into a component both use), with no physics, sails and sheets in
  a still pose (the hero already has still sail shapes for the model viewer; for the others, the rest pose of the cloth
  or a captured frame), standing on a cradle on the cyclorama floor so the keel and rudder show. Lake presets: the
  showroom path as it is (the pawn in the showroom hold with the live sails).
- If the refactor proves big, ship the boats as "lake presets only" first and say so in the PR.

## 8. Suggested PRs (one per phase, against main, not stacked, after the showroom PRs)

1. **Mac: gallery core** (after showroom PR 1 and photo PR 1). `UGalleryIndex` with the folder table, variant grouping,
   names table and logging; `AGalleryStage` with the display component, async load, framing from bounds, studio set
   and lights, lake presets through `PreviewConditions`; graphics snapshot and restore; tier compare captures;
   the developer-tools flag, wireframe override, forced LOD and twins, stats. Testable from launch args:
   `-SailingGallery=/Game/World/Houses/SM_HouseNear_Cottage -SailingGalleryLight=Studio -SailingShot=...` for stills, and
   a tests file: the index finds every static mesh under the named folders, an unknown folder lands in Other, `_Light`
   and `_Far` group under their base.
2. **PC: gallery screen** (after 1 and showroom PR 2). `ESailScreen::Gallery` in its own file (e.g.
   `UI/SailGallery.cpp`, so `SailFrontEnd.cpp` doesn't grow), entered from the Title menu (Gallery, only with the
   developer flag); collapsible Graphics & view and stats cards; the left
   panel, search, chips, tags, grouped list, thumbnails, viewer overlay, graphics strip with the shared Settings rows,
   compare split, full screen and clean view, prompt bar, controller navigation. Thumbnails: rendered at runtime with a
   scene capture on the stage, one per frame for the rows on screen, cached in memory and in `Saved/GalleryThumbs/`
   keyed by package path and the build's changelist so they refresh when an asset changes. Studio look tuned at Ultra.
3. **Mac: whole boats** (optional, after 2). `ABoatDisplay` and the visuals refactor, still sails, cradle.

Gates: Mac gate Medium 60 with the gallery open on the heaviest assets (Lagoon 42 at Ultra on PC; the container ship
and the church in the studio and on the lake) and while flicking through 30 rows; no hitch over 33 ms on Mac Medium
when selecting. Packaged check (Shipping): the index count in the log matches the editor's, thumbnails and async loads
work, the Gallery entry hidden by default and shown with the ini line.

Each PR: stills at 1440x1080 and 1920x1080 for the docs folder (Studio at Low and Ultra, a compare split, Golden hour on
the lake, wireframe on a kit part, full screen), no crew faces in anything that goes to the public repo.

Online readiness: the gallery is client-side presentation only; it spawns nothing the sim reads, holds no boat state
(the showroom hold is the showroom's), and uses `GetFirstPlayerController` only on the client, per the rules.

## 9. Still open

- Whether the gallery also opens from the Pause menu in game (it would leave the boat held while the gallery is open).
  The brief assumes Title only.
- Where exactly the studio stage sits, and its backdrop shade: pick by eye in stills.
