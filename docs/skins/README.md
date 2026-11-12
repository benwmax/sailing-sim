# Boat skins (v1: the skin file, the loader, the built-in skins and the Customize screen)

Plan: the Claude Doc "Ready About: boat skins plan". A skin is how a boat looks, as one small file a player can load
and unload: paint, wear, sails and rope colours. The Customize screen (from the Boat screen, on the showroom) edits
one; `-SailingSkin=<id>` puts one on for stills.

Nothing here touches the physics, a material, a script or an asset: skins move parameters the materials already have.

## The file

`Saved/Skins/<id>.skin.json` (the file's name is the skin's id). Every section and every field is optional; what is
missing leaves the boat as her class has her, so a skin can change only the sails, and taking it off puts her back.

```json
{
  "format": "ready-about-skin",
  "version": 1,
  "id": "my-navy",
  "name": "My navy",
  "boat": "J22",
  "paint": {
    "hull": "#1C2A44", "deck": "#F2F0EA", "nonSkid": "#D9D7D0", "bottom": "#2E4F8A",
    "boot": "#B3201B", "cove": "#D9B33A", "trim": "#9A6233", "spars": "#17191C"
  },
  "wear": { "level": "club" },
  "sails": { "cloth": "#EDE6D3", "number": "402", "classMark": true },
  "lines": { "mainsheet": "blue_solid", "jibPort": "red_white_fleck", "jibStarboard": "green_white_fleck", "control": "yellow_black_fleck" }
}
```

- Colours are `#RRGGBB` (sRGB). `"boot": "none"` takes the boot stripe off; `"spars": "bare"` leaves the anodised aluminium.
- `wear.level`: `new`, `months`, `club` (the boat every class already is; changes nothing), `classic` (decades, well
  kept), `neglected`. Or the exact pair `"ageYears"` (0 to 60) and `"care"` (0 to 1), which beats the level. These are
  the texture loop's Age and Care.
- `lines`: a colourway from `Inputs/rope/colourways.json` by name, per role. The wires are never recoloured.
- `boat`: the class she was made for (the save's boat ids). A skin made for another class is not listed for this one.

## Safe to take from someone else

A skin names colours and things the game ships, and nothing else: no paths, no scripts, no material names. The reader
(`FBoatSkin::FromJson`) refuses a file over 64 KB or of a newer version whole, with a message; clamps every number;
cleans the id to `[a-z0-9-]` (40 characters) and the name to letters, digits and a few marks (32); and drops every field
it does not know. A file can never claim a built-in's id. `SailingSim.Skin.BadFiles` holds this.

## Built-in skins

Made in code from the boat catalogue's colour schemes (`BoatSkinStore::BuiltIn`), so they cost no files. Ids are
`builtin-<boat>-<name>`. The J/22 has nine: `factory-white`, `late-model`, `race-polished` (new), `navy`, `red`,
`dark-grey`, and three wear looks on the factory white: `showroom`, `well-loved`, `barn-find`. The Sunfish has six (its
red-stripe and blue-stripe schemes differ only in the sail's stripes, which a livery does not hold yet, so they are one skin).

## In the game

- `ASailboatPawn::RebuildBoatVisuals` puts the skin over the class's livery (`FBoatSkin::ApplyTo`): only the player's
  own boat (not traffic, not the ghost) reads `-SailingSkin=<id>` or the save. `SetSkinPreview`/`ClearSkinPreview`/
  `RefreshSkin` are for the Customize screen.
- Wear: the level sets the livery's four wear channels and, on the hero's materials, Age and Care (the same path as
  `-SailingBoatAge`, which still wins).
- Ropes: the rig lines keep their looks; the colour column sent to `M_RigRope` is remapped per role
  (`FBoatSkin::RopeColumns`), on the rope, knot and coil sections only.
- Sails: cloth colour, number, class mark on or off.
- The save: `"boats": { "J22": { "skin": "my-navy" } }` (`FSailSave::BoatSkins`, `SailSaveStore::BoatSkin`/`SetBoatSkin`);
  version unchanged, an older file reads as no skins, unknown fields per boat are kept.

Online-readiness: skins are cosmetic and never reach SailingPhysics (rule 1); any vessel can wear one, nothing asks for
"the player" beyond choosing whose saved skin to read (rule 2); the file is versioned with string ids (rule 7).

## The Customize screen

Boat screen > Customize (C, or Y on the pad; not for a locked boat). `ESailScreen::Customize`, `UI/SailCustomize.cpp`;
the editing itself is `FSkinEditor` (`SkinEditor.h`, plain logic: the draft, undo and redo, what saving does), so the
tests drive it without Slate. The showroom stays up (`SailShowroom::StageFor`): the boat on the right wears the draft as
it changes (`ASailboatPawn::SetSkinPreview`, at most eight times a second while a slider is dragged).

- Tabs (Q/E, LB/RB): **Skins** (the class look, the built-ins, your own; rename, delete), **Paint** (eight parts; sixteen
  real-boat swatches or your own colour by hue, strength and lightness, capped short of neon), **Sails** (cloth, number,
  class mark), **Lines** (a colourway per rope; Left and Right), **Wear** (the five levels).
- Always there: Use this look (saves and goes back), Save as new, Surprise me (R / Menu), Undo and Redo (Z, Y / X, Y),
  Before (T / L3: her saved look, to compare).
- Nothing is saved until Use this look or Save as new. Back with changes says so once; Back again leaves without saving.
- Saving (`FSkinEditor::SavePlan`): an empty draft takes the skin off; an unchanged skin is named in the save; a changed
  skin of the player's is written over; a changed built-in becomes a new file ("My navy").
- One switch: `-SailingNoCustomize` takes the button and the key off the Boat screen (`SSailFrontEnd::CustomizeEnabled`).
- Stills: `-SailingFrontEnd=Customize -SailingCustomTab=<0..4>`.

Not in this version: a camera framing per tab, a name typed from the pad (the pad gets "My navy", "My navy 2"), sail
stripes and designs, lettering and stickers.

## Tests

`scripts/test.sh SailingSim.Skin`: RoundTrip, BadFiles, Apply, BuiltIn, RopeColourways, SaveField, Ids, Editor, Screen.

## Not yet checked on the Mac

This step was written without a compiler. To confirm there:

1. It builds (clang, and MSVC on the PC) and `SailingSim.Skin.*`, `SailingSim.Save.*` and `SailingSim.Visual.*` pass.
2. Stills, High, at the slip: `-SailingSkin=builtin-j22-navy`, `builtin-j22-red`, `builtin-j22-barn-find`,
   `builtin-j22-showroom`, and the Sunfish's `builtin-sunfish-blue-deck`: which livery colours reach the hero models'
   slots (hull, deck, non-skid, bottom, boot, cove, trim, spars).
3. Whether a wear level reads as doubled on the hero (the livery's wear channels and Age/Care both move).
4. A skin with `lines` set: the sheets, their knots and coils take the colourway and the wires do not change.
5. No skin: stills identical to main, and the boats and crew gates hold.
6. The Customize screen: stills of each tab (`-SailingFrontEnd=Customize -SailingCustomTab=0..4`) at 1920x1080 and
   1280x720; a keys run with `-SailingUIScript` (C on the Boat screen, E through the tabs, R, Enter on Use this look);
   that the panel does not cover the boat, and that a preview's rebuild of the boat's look is not a visible hitch.

## Later (the plan's v2 on)

Sunfish sail stripe colours (the palette is in `M_SailCloth`'s code: a material change), lettering and stickers,
finishes, wear that grows with hours sailed (the player can override it), export and import, skins seen by other
players online with a "default looks only" switch.
