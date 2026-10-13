# G3 crew clothing shortlist (Fab, MetaHuman)

Researched 2026-10-13 for the sailing sim's MetaHuman crew (three sailors on the player J/22). Cloud-only research; nothing bought or downloaded.

## Headline findings

1. **No life jacket (PFD) exists on Fab as a MetaHuman garment.** Searches for life jacket, life vest, PFD, buoyancy aid, kayak, rafting and fishing vest on Fab turned up nothing fitted to MetaHumans (only generic static life-jacket models on TurboSquid/CGTrader/Sketchfab). The PFD will have to come from the project's own Blender pipeline whichever pack Bean buys. That is the right call anyway: a Type III foam vest and an inflatable yoke PFD are simple, mostly rigid shapes, and crew in PFDs is what an ASA 101 sim should show.
2. **No dedicated sailing or foul-weather pack exists either.** The closest real fit is a mix-and-match of single parametric items (polo, shorts, cap, sunglasses, technical anorak) from one seller, NDart.
3. **Use parametric (MHPKG) wardrobe items, not older skeleton-fitted outfits.** Since MetaHuman 5.6, "Parametric Wardrobe" .mhpkg items resize to any MetaHuman body in MetaHuman Creator. Older listings are fitted to one body type (for example "Male Tall Normalweight") and need manual refitting for the other two sailors.
4. **Prices could not be read from here.** Fab blocks automated price lookups (the price field comes back blank on every listing). Prices below are left for Bean to see on the listing; the recommendation assumes NDart single items are in the usual Fab range for single MetaHuman garments, which is inferred, not checked.

## Licence (applies to every paid pick)

Fab Standard License, from fab.com/eula summary: commercial or private use, modify, and ship in a commercial game with the asset built in. You may not resell or redistribute the asset on its own. Personal and Professional tiers grant the same rights; Personal is the tier for individuals and small businesses (Fab's threshold is US$100k annual revenue), and there is no need to upgrade later if revenue crosses it. **Bean qualifies for Personal.**

Project consequence: like the MetaHuman assets today (~440 MB, git-ignored), purchased clothing source files must stay out of the GitHub repo (redistribution clause). Git-ignore them and document the re-download step next to the MetaHuman rebuild script.

Known 5.6+ gotcha: in Aug 2025, MetaHuman clothing showed "Not available for use within Unreal Engine versions prior to 5.6" in the in-editor Fab panel. Epic fixed it in a Fab plugin update; if it appears in 5.8.3, update the Fab plugin from the launcher ([forum thread](https://forums.unrealengine.com/t/cant-use-metahuman-clothing-from-fab-in-unreal-5-6/2643008)).

## Ranked shortlist

### 1. Recommended: NDart parametric sailing kit (buy 4 to 5 single items)

Seller: NDart. All MHPKG Parametric Wardrobe, MetaHuman 5.6+ / UE 5.6+, game-ready topology, PBR.

| Item | Link | Detail |
|---|---|---|
| Polo Shirt | https://www.fab.com/listings/3cc63844-d122-4e5d-b82b-6166a4f1cf28 | 6 colours (white, beige, blue, gray, green, black); 4K base colour, ORM, normal; body mask |
| Athletic Running Shorts | https://www.fab.com/listings/25af9f0a-6704-4889-bbcd-db8de1efaf1d | elastic waist, relaxed fit; parametric |
| Cap | https://www.fab.com/listings/217f5cf6-65cf-44ec-b89c-7324a43397a2 | six-panel ball cap, buckle strap, 12 colours |
| Round Sunglasses | https://www.fab.com/listings/54c19534-0ee1-467e-b7eb-9163e4191227 | adjustable lens tint and transparency; adapts to head shape |
| Technical Anorak Jacket (optional, foul weather) | https://www.fab.com/listings/1ef84e7c-2f9f-42a9-a649-b31a3b528fdc | hood, half zip, front pocket, elastic cuffs, 6 colours; stands in for a sailing spray top in storm scenes |
| Alt bundle: Smart Casual Outfit | https://www.fab.com/listings/0e186c50-92f7-4446-b95b-a140b018704c | polo + jeans + leather sneakers; only worth it for the sneakers as deck-shoe stand-ins |

- **Covers:** polo, shorts, cap, sunglasses, foul-weather top. **Missing:** PFD (Blender), deck shoes (Blender, or the Creator's built-in shoes).
- **MetaHuman evidence:** listings and Epic forum posts state "MetaHuman 5.6+ Parametric Characters", MHPKG, "adapts automatically to MetaHuman body proportions". Explicit 5.8 support is not stated; MHPKG items generally carry forward, but test-import one item first.
- **Poly/texture:** 4K PBR stated on polo; polycounts not published.
- **Risks:** no ratings or reviews yet on any NDart item. Mixing items lets each sailor look different (three colours of polo and cap), which also helps Bean's "everything looks the same" note from blind round 6.
- **Why first:** only option that hits polo + shorts + cap + sunglasses + rain top, resizes to all three crew bodies, and should land in the $20 to $50 range if bought as 4 items (check the cart total; drop the anorak if it pushes over).

### 2. Stretch pick: Nice Pictures "Clothes Collection for MetaHuman"

- Link: https://www.fab.com/listings/fad76433-5497-43c6-a657-b144863d1c2a
- Publisher: Nice Pictures. Listing says 100 clothing assets at "$8 per asset"; total price not readable.
- Garments: men's and women's summer, sport, hiking/backpacker, hunting and winter outfits (hoodie with shorts, casual shirt, puffer, parka, more). No PFD, no polo specifically.
- MetaHuman evidence: UE 5.3+, rigged to MetaHuman female and male normal bodies plus UE5 Manny/Quinn; ships as MHPKG, FBX and **Blender** source; tutorials target MetaHumans 5.6+.
- Detail: 4K PBR textures. Polycounts not published.
- Reviews: **5.0 from 9 ratings**, the best-reviewed relevant pack found.
- Known issues: seller fixes bugs free but charges for skinning changes; some items are fitted to normal-weight bodies rather than fully parametric.
- Why stretch: much larger wardrobe with real reviews, and the Blender source files make it the easiest base for the team to cut a properly fitted PFD and spray top from. Costs more and needs more fitting work than pick 1.

### 3. Mesh Atelier "MetaHuman Male Outfit Pack" (+ Women's Outfit Pack)

- Links: male https://www.fab.com/listings/63b79129-8f92-4e91-a5cf-f2b498cb1325, women's https://www.fab.com/listings/2f376410-f954-4e48-bcd3-d0fe8290e8ee, sportswear https://www.fab.com/listings/c708eb85-b42d-4c88-b56e-f62d4eea7cbc
- Male garments: windproof jacket, puffer, hoodie, long-sleeve tee, sleeveless shirts, 2 shirts, 3 pants, **4 shorts styles**. Sportswear pack (21 items) adds a nylon jacket, shorts and tops.
- Chaos Cloth assets (fabric moves in wind, nice on a boat).
- MetaHuman evidence: "designed for the MetaHuman Male Tall Normalweight skeleton" only; not parametric.
- Reviews: male pack **1.0 from 1 rating**; sportswear unrated.
- Why third: good garment range and real cloth sim, but single body type and the one review is bad.

### Also seen, not recommended

- **Vu. Explorer Outfit** (https://www.fab.com/listings/1dd24a54-3b31-4cc5-b182-24e484004f06): shirt, vest, pants, boots as separate meshes, ~21k triangles, MetaHuman + Manny rig, UE 5.3+. Safari look, not sailing.
- **Jels Studio OoMH-02 shirt and shorts** (https://www.fab.com/listings/4204e0f9-8ff8-4ecb-a85f-11cf7a20cca2): shirt + belted shorts with Chaos cloth preset; Tall/Medium bodies; unrated.
- **Space Monkey MetaHuman Sports Outfit** (https://www.fab.com/listings/65f81bd6-c35c-4a33-a006-ea727820c8f6): pants + bonus item, but notable for shipping separate MHPKGs for UE 5.6, 5.7 and **5.8**, 4K textures, LOD0 to 3.
- **CGTailor Parametric Workwear** (https://www.fab.com/listings/709a5877-3cfe-4af8-819f-94983d26c53d): flannel/overalls/denim with clean and weathered versions. Wrong look.

## Free options

- **Epic "MetaHuman Techwear Outfit"** (free, Epic Games): https://www.fab.com/listings/9e04c752-1979-4723-b78f-6d24afc532bc. Jacket, pants and shoes as one parametric outfit, 4 body LODs, colour editable in MetaHuman Creator, **4.8 from 12 ratings**. Usable today as a foul-weather stand-in; one-piece, so it cannot be mixed with shorts.
- **MetaHuman Creator's built-in wardrobe** (5.6+): basic parametric tops, bottoms and shoes ship with the plugin. Fine for deck shoes and plain tees; generic look.
- **Epic "MetaHuman Clothing Construction Presets, Set of 4"**: four body presets plus FBX for building your own parametric garments in Blender at four sizes ([forum](https://forums.unrealengine.com/t/epic-games-metahuman-clothing-construction-presets-set-of-4/2538920)). Known bug: the FBX scrambles in a resizable Outfit Asset under Interchange import; workaround is `Interchange.FeatureFlags.Import.FBX 0` or rebuilding a skeletal mesh and transferring skin weights.
- **Toby Virtual Filmer free casual resizable outfit** (Gumroad, $0, UE 5.6): https://tobyvirtualfilmer.gumroad.com/l/vfhorizoncasual. Licence not stated on the page, so do not ship it without checking.
- Quixel/Megascans: no MetaHuman garments; only useful for fabric surface textures.

## Could the existing Blender pipeline do this for free?

Partly.
- **PFDs: yes, and it must.** Foam Type III vest (rigid panels, skinned mostly to spine_03/spine_05 and clavicles) and an inflatable yoke PFD (collar tube plus waist belt) are low-deformation shapes the generated pipeline already handles. Use Epic's four construction presets so they become parametric Outfit Assets that fit all three crew. Reference: J/22 lesson PFDs are usually inflatable yoke or foam Type III in red, yellow or navy.
- **Deck shoes, caps, sunglasses: yes,** small rigid items; quality would be close to bought ones.
- **Polos, shorts, spray tops: possible but weaker.** The hard part is believable fabric folds, seams and 4K woven textures, which is exactly what the paid items supply. Matching NDart/Nice Pictures quality would take many hours of sculpting and texture work per garment; for $20 to $50 buying is the better trade.

## Suggested order for G3

1. Bean buys pick 1 (Personal licence), or pick 2 as the stretch.
2. Sim thread test-imports one NDart item into the 5.8.3 project before relying on the rest (version check; update the Fab plugin if the "prior to 5.6" error appears).
3. Blender pipeline builds the PFD (foam and inflatable variants) and deck shoes as parametric Outfit Assets.
4. Git-ignore purchased source; document the re-download step.

## Budget revision (2026-10-13 19:40 UTC)

Bean checked the NDart listings: each item is $20 to $40, so buying 4 to 5 singles is too much. Revised options:

1. **Recommended: buy one polo, build the rest.** One NDart Polo Shirt (6 colours covers all three sailors) is the garment hardest to fake (soft knit folds, collar, 4K weave). Shorts, cap, sunglasses, deck shoes and both PFDs come from the Blender pipeline as parametric Outfit Assets via Epic's free Clothing Construction Presets. Free Epic Techwear Outfit stays as the storm outfit. Cost: one item, $20 to $40.
2. **Nice Pictures single items:** the collection listing says "$8 per asset"; pick a summer outfit with shorts plus a sport top (~$16 to $24). Fitted to normal-weight bodies, not parametric, so fitting work for the other two sailors. Price per item is the listing's claim, not checked in a cart.
3. **Free only:** MetaHuman Creator built-in wardrobe + Epic Techwear + everything else from Blender. $0; garment detail a notch below bought items.

### Correction (19:40 UTC)

Bean reports the Nice Pictures Clothes Collection costs $400 in full. The "$8 per asset" line I read on the listing does not mean single items can be bought separately, so revised option 2 above is unconfirmed. Drop it as a budget pick. It stays the stretch pick only if the budget ever allows $400.
