# Asset gallery G2: the screen (PC, Oct 28 2026)

This is the PC part of `Inputs/gallery/brief.md` (inputs branch, df60bd2). It sits on the Mac's core (G1, `docs/gallery-core/`): the index, `AGalleryStage`, the views, detail, stats and compare. The screen is `ESailScreen::Gallery`, in its own file, `UI/SailGallery.cpp`.

## Getting in

- **Title > Gallery** ("Developer · every asset") appears only when `USailingSettings::bDeveloperTools` is set.
  - Development builds have it on.
  - In Shipping, add this to the user's `GameUserSettings.ini` (`%LOCALAPPDATA%\SailingSim\Saved\Config\Windows\` on the PC):

        [/Script/SailingSim.SailingSettings]
        bDeveloperTools=True

  - Without that line, players never see the entry.
- With the tenth Title item, the menu items are a little tighter, so Quit stays clear of the prompt bar at 1080 lines.
- `-SailingFrontEnd=Gallery` opens it for stills (dev builds).
- Whole boats are left out of the list until G3 (the Mac's), because the stage shows meshes only.

## The screen

**The left panel** (360 px) holds, from top to bottom:
- "DEVELOPER", "GALLERY";
- the search box: `/` focuses it; every word must match; Enter, Esc or Down goes back to the list;
- category chips with counts (they follow the search);
- the chosen category's tag chips, most common first; they AND together;
- the list, under a header per category. Each row has a thumbnail, the name, two tags and a HERO badge where it applies;
- "N of M assets".

The list:
- Focus is the selection. The stage loads only where a flick stops (its 200 ms `Select`).
- The scroll box keeps the focused row in view.
- Q/E or LB/RB change category.
- Enter or A on a row gives the input to the viewer: the left stick and the arrows pan. Esc or B comes back to the row.

**Over the viewer:**
- **Top left:** category, name at 44 px, description, tags (plus "Loading…" while the mesh loads).
- **Top right:** Light (cycles Studio, Noon on the lake, Golden hour, Overcast; L or the D-pad's sides), Compare (C or X), Full screen (F or View).
- **Model stats card:** triangles (Nanite or LOD), the detail shown, materials, size in metres, render scale, the path.
- **Bottom left:** mouse orbit controls (← 45°, 45° →, Zoom out, Zoom in, Auto spin on or off, Reset) and the angle and zoom readout.
- **Bottom right:** the Graphics & view card:
  - **Tier:** Low, Medium, High, Ultra. G or Y cycles it.
  - **More settings** opens the main Settings rows: Shadows, Lighting, Reflections, Anti-aliasing, Render scale, Motion blur. The code is shared with Settings > Graphics (`UI/SailGraphicsRows`), so the two pages can't drift. It also has Compare left / right and Restore my settings.
  - **View:** Lit, Wireframe, Lit + wire. V cycles it.
  - **Detail:** Auto, a LOD per level (non-Nanite), Fallback mesh (Nanite), Light (AI boats) and Far where those twins exist.
- **Folding:** each card's header folds it. T (L3 on a pad) folds or opens both. The fold is remembered in `GameUserSettings.ini` (`[SailingGallery] bCardsFolded`).

**Compare:**
- C captures the same shot at the two chosen tiers (Low and Ultra by default) through the stage.
- It then shows them over the whole screen with a split the mouse drags, labelled with the tiers.
- Any orbit, Esc or B leaves it.

**Full screen and clean view:**
- F or View hides the list and the stats card. The asset moves to the middle: `AGalleryStage::SetPanelShare(0)`.
- View again, or H, hides everything but the asset (the backdrop, the cards and the prompt bar too).
- Esc or B steps back out, one layer at a time: compare, clean, full screen, viewer, then the screen.

**Leaving:**
- If the graphics changed in here, "Keep these graphics settings?" asks once. Restore has the focus, so a look at Ultra on a laptop doesn't stick; Keep keeps them.
- Esc stays in the gallery.
- `Confirm` gained a second answer for it.

**Orbit input:**
- Left drag orbits. Right drag, or Shift and drag, pans.
- The wheel zooms.
- The right stick orbits and the triggers zoom (the showroom's rates).
- R or R3 resets the view.

## Thumbnails

- Each mesh is rendered once, at runtime, one a frame in the list's order. A scene capture on a rig of its own, 2.5 km over the boat, captures the mesh alone (show-only list) at the stage's three-quarter view.
- They are cached in memory and in `Saved/GalleryThumbs/`, keyed by the mesh path and the build. A new build renders them again.
  - With an empty cache, all 132 rendered within the first UIScript run (I didn't time it). After that they come from disk.
  - The log says `Gallery thumbnails: N rendered, M from Saved/GalleryThumbs`.
- They are the mesh's **base colour, unlit**. A lit capture drew the sky and the clouds behind the mesh (they aren't primitives a show-only list leaves out) and needed an exposure of its own. On a 72×48 row, the shape and colours are what tell assets apart. A lit thumbnail would need a small closed studio around the rig; that's a follow-up if wanted.

## Stage changes (the Mac's file, small)

`AGalleryStage` gained:
- `SetAutoSpin` / `GetAutoSpin`: the screen's Auto spin button. Spin stays 6 deg/s after 4 s idle.
- `SetPanelShare`: 0.25 with the list, 0 full screen.
- `GetZoom`: for the readout.

## Found on the way

- **Uncooked, the asset registry hadn't scanned the content** when the gallery opened at startup with the menus. The index held only the boats, logging "0 meshes in the registry". The screen now scans the gallery's folders first (`ScanPathsSynchronous`, editor builds only). The cooked registry is read whole at startup.
- **`Ensure condition failed: OriginX <= OriginMax ... precision loss while converting matrix to GPU format`** appears once about 2 s after launch. It also happens on the Title screen with no gallery, so it isn't this PR; worth a look on main.

## Checked

- MSVC build clean on main 050b6817 (#372). Full tests pass.
- UIScript runs, uncooked, 1920×1080 and 1440×1080, `-SailingNoGpuSlices`:
  - Down walks the rows, each loading on the stage (0-86 ms once warm; the first load about 3 s uncooked).
  - E twice goes to Houses & docks.
  - L L gives golden hour on a tree.
  - V gives wireframe on a kit part.
  - C gives the compare: "tiers 0 and 3 captured at 1920 x 1080".
  - F goes full screen.
  - G then Esc gives the leaving prompt.
  - 132 thumbnails rendered.
- **Not checked yet:** the packaged Shipping run, with the index count against the editor's and the entry hidden by default and shown with the ini line. That goes with the next Shipping build.

## Stills (`docs/gallery/pc/`, Ultra unless named)

| Still | What it shows |
| --- | --- |
| `studio-ultra-1920.jpg`, `studio-ultra-1440.jpg` | The cottage in the studio, Houses & docks chosen |
| `studio-low-1920.jpg` | The same at Low |
| `compare-1920.jpg` | Compare tiers: Low left, Ultra right |
| `golden-1920.jpg` | Cedar elm at golden hour on the lake |
| `wire-kit-1920.jpg` | The bow pulpit (kit, HERO) in wireframe |
| `full-1920.jpg` | Full screen |
| `leave-1920.jpg` | "Keep these graphics settings?" after a tier change |
| `title-1920.jpg` | Title with the Gallery entry; Quit clear of the prompt bar |
