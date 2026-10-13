# Boat catalogue for G3 (boats and crew)

Reference for baked texture sets, seeded colour and wear, decals, woven sails and dimension fixes for the sim's eight boats. Compiled 13 Oct 2026. The generator-readable twin is [boat-catalogue.json](boat-catalogue.json).

**How solid is this?** Dimensions, class marking rules and sail cloth specs come straight from builders, class rules and RRS Appendix G. Hull colour frequencies are estimates: sale listings almost never state colours and the research tools could not view photos, so weights come from builder catalogues, colour history and the few listings that do say. Every hex value is an art-direction suggestion, not a manufacturer colour. Each scheme in the JSON carries a `confidence` field. A quick check against regatta photos (or Bean's own Rush Creek photos, when they exist) is the cheapest way to tighten the J/22 weights.

## JSON schema

```
{
  schema_version: 1,
  generated: "YYYY-MM-DD",
  conventions: {                     // units, hex notation, sampling rules, RRS table
    rrs_appendix_g_heights_mm: { band: [min_height_mm, min_spacing_mm] }
  },
  classes: [ {
    id: "j22" | "sunfish" | "ilca7" | "catalina22" | "catalina30" | "hobie16" | "corsair880" | "lagoon42",
    name, kind,
    dimensions: {
      loa_m, beam_m,                 // always present; published values
      hull_length_m?, lwl_m?, beam_folded_m?, loa_incl_rudder_m?,
      draft_m: { <config>: m }, displacement_kg? | hull_weight_kg? | unladen_weight_kg?,
      I_m?, J_m?, P_m?, E_m?, mast_length_m? | mast_above_dwl_m? | air_draft_m?,
      sail_area_m2: { <sail>: m2 },
      sources: [url], notes
    },
    colour_schemes: [ {
      id, weight,                    // relative; normalise per class
      hull_hex, deck_hex, nonskid_hex?, bottom_hex?, coaming_hex?, cabintop_hex?,
      tramp_hex?, frame_hex?, spar_hex?, glazing_hex?,
      *_hex_options?: [hex],         // pick one uniformly when present
      stripes: [ { zone, hex, height_mm?, probability? } ],
      trim?: { handrails, toerail, teak_hex? },
      notes, confidence
    } ],
    sail_number: {
      required: bool, probability?,  // probability a boat carries numbers when not required
      format,                        // "USA {n}", "{n}", "{n6}" (six digits)
      number_range: [lo, hi], height_mm, spacing_mm, char_width_mm?, stroke_mm?,
      font, colour_hex, alt_colours?: [{hex, weight, when?}], lead_digits_hex?,
      placement: { <sail>: text }, insignia: { <sail>: text, hex?, probability? },
      sources: [url]
    },
    sails: [ {
      sail: "main" | "jib" | "genoa" | "spinnaker" | "lateen" | "screecher" | "asymmetric_spinnaker" | "self_tacking_jib" | "code0",
      cloth, weight_gsm_min?, weight_oz_typical?,
      colours: [ { hex, weight, name? } ],   // hex may be "stripes:#a,#b,..." (bands foot to head) or "multi"
      variants?: [ { id, weight, cloth, colours, panel_layout, scrim_hex? } ],
      panel_layout, panel_width_mm?, battens: { count, type?, lengths_in? },
      windows?: [ { pos, max_side_mm?, probability? } ],
      branding?: [ { maker, weight } ], uv_strip?: { probability, colours },
      stowage?: { type, colours }, sources: [url]
    } ],
    covers?: [ { item, hex, name, weight } ], spars?: {...}, decals?: [ { item, probability } ],
    wear: {
      profile_weights: { club, race, charter? },   // sample one profile per boat
      zones: [ {
        id, zone, kind,              // kind: oxidation | stain | rust | scuff | abrasion | crack | fade | weathering | crease
        intensity: { club: [min,max], race: [min,max], charter?: [min,max] },  // 0..1
        colour_hex | null,           // null = desaturate/lighten the base material
        notes, source: url | null
      } ]
    },
    research_notes
  } ]
}
```

Sampling: seed per boat, pick a colour scheme by weight, pick a wear profile by `profile_weights`, then sample each zone's intensity uniformly in that profile's range.

## Published dimensions (and the three the sim gets wrong)

| Class | LOA | Beam | Other key figures | Sources |
|---|---|---|---|---|
| J/22 | 6.86 m (22'6") | 2.44 m (8'0") | LWL 5.79 m, draft 1.16 m, disp. 812 kg, main 10.91 / jib 10.14 / kite 33.5 m² | [Wikipedia](https://en.wikipedia.org/wiki/J/22), [class rules 2021](https://arbitrage.ffvoile.fr/media/w25lbhof/j22-2021-e.pdf) |
| Sunfish | 4.19 m (13'9") | 1.24 m (4'1") | hull 54 kg, sail 7.0 m², mast 3.05 m, spars 4.17 m | [Wikipedia](https://en.wikipedia.org/wiki/Sunfish_(sailboat)), [SERO](https://seroinnovation.com/product/sero-innovation-sunfish-sailboat-century-edition-all-blue-deck-w-white-stripes/), [Rig-Rite](https://www.rigrite.com/Spars/A_spec_classes/Sunfish_spars.php) |
| ILCA 7 | 4.23 m | 1.37 m | hull ~59 kg, sail 7.06 m² | [Wikipedia](https://en.wikipedia.org/wiki/Laser_(dinghy)), [Binks](https://binksmarine.com.au/products/ilca-ex-charter-boat) |
| Catalina 22 | 6.55 m hull (21'6"); 7.26 m with rudder | 2.34 m (7'8") | LWL 5.89 m, disp. 1,021 kg, mast 8.69 m above DWL | [sailboatdata](https://sailboatdata.com/sailboat/catalina-22), [Catalina](https://www.catalinayachts.com/sport-series/22-sport/) |
| Catalina 30 | 9.12 m (29'11") | 3.30 m (10'10") | LWL 7.62 m, disp. 4,627 kg, draft 1.60 / 1.31 / 1.17 m | [sailboatdata](https://sailboatdata.com/sailboat/catalina-30) |
| **Hobie 16** | **5.04 m (16'7")** | **2.41 m (7'11")** | hull 145 kg, mast 8.07 m, main 13.77 / jib 5.12 m², spinnaker 17.5 m² | [Hobie US](https://hobie.com/sail/hobie-16/), [Wikipedia](https://en.wikipedia.org/wiki/Hobie_16) |
| **Corsair 880** | **8.8 m (28'8")** | **6.8 m (22'3") deployed, 2.5 m (8'2") folded** | draft 0.45 / 1.6 m, unladen 1,660 kg, mast 12 m (Sport 13.5 m), upwind 51.5 m² (Sport 62.9) | [Corsair spec](https://corsairmarine.com/corsair-880/specifications/), [Corsair Sport](https://corsairmarine.com/corsair-880/sport-specifications/) |
| **Lagoon 42** | **12.79 m hull; 13.22 m LOA with sprit** | **7.68 m** | draft 1.26 m, air draft 20.6 m, light disp. 12.1 t, main 55 m² (sq-top 59), jib 35 m², Code 0 78 m² | [Lagoon](https://www.catamarans-lagoon.com/boats/lagoon-42), [Lagoon 42 Millenium](https://catamarans-lagoon.com/boats/lagoon-42-millenium) |

What to watch on the three flagged boats:

- **Hobie 16.** Hobie's own pages disagree: the US page says 5.04 m and mast 8.07 m, the international page 5.11 m and 7.92 m ([Hobie intl](https://www.hobie.com/xe/en/sail/hobie-16/)). Use the US figures, which match Wikipedia (5.05 m, 8.08 m). Beam 2.41 m is outside to outside over both hulls.
- **Corsair 880.** Beam is 6.8 m with the floats out and 2.5 m folded; if the sim's config holds one beam it should be 6.8 m in the water. The Sport page quotes the mast as both 13.8 m and 13.5 m, and listings say about 45 ft ([listing](https://multihullcompany.com/boat/corsair-880-sport-4195167)). sailboatdata's 28.87 ft LOA and mixed sail areas are less reliable than the builder.
- **Lagoon 42.** Model the hulls at 12.79 m and let the bowsprit carry LOA to 13.22 m. Older listings round to 12.80 × 7.70 m ([yachtall](https://www.yachtall.com/en/boat/lagoon-42-s233753?print=1)). Do not use Wikipedia's "Lagoon 42" page: it describes a different 1990–94 boat (12.95 × 6.91 m). One boats.com listing gives a 6.71 m beam, which is wrong.
- **Catalina 22.** The 23.83 ft figure on sailboatdata includes the rudder; the hull is 21'6".

## Sail numbers (RRS Appendix G, all classes)

Capitals and Arabic numerals in one colour that contrasts with the sail, sans-serif, on both sides with the starboard side uppermost, and national letters above numbers. Main: above an arc from the head at 60% of the leech. Spinnaker: front side, between arcs at 40% and 60% of the foot median. Headsail: only if the foot is over 1.3 × J. Minimum height and spacing by LOA: under 3.5 m 230/45 mm; 3.5–8.5 m 300/60 mm; 8.5–11 m 375/75 mm; over 11 m 450/90 mm. Source: [RRS Appendix G](https://www.racingrulesofsailing.org/rules?part_id=81).

## J/22 (deepest: Bean's lesson boat at Rush Creek)

- **Hull.** Factory white gelcoat. White was the only colour stated in about 32 listings read ([Rightboat](https://www.rightboat.com/boats-for-sale/j-boats/j22/rb499483), [sailingtexas hull #118](https://www.sailingtexas.com/sj22.html)), so plan roughly 85–90% white. Painted race hulls (navy, red, dark grey) about 1 in 8. Class rules set no hull colour. A thin navy boot stripe is inferred, not sourced.
- **Trim by builder.** TPI boats (1983 on) have teak handrails and toe rails ([Wikipedia](https://en.wikipedia.org/wiki/J/22)); late Waterline Systems boats have stainless handrails and white composite toe rails, "no teak trim" ([Brewer](https://breweryacht.com/listings/2003-j-boats-22-sloop-serendipity/2803723), [J/Boats](https://jboats.com/j22-one-design-sailboat)). Club fleets are mostly older teak boats.
- **Bottom.** VC17m (copper-bronze weathering to grey-brown in fresh water) or VC Offshore blue/red/black on club boats; race boats sand to 220 grit or barrier-coat ([listing](https://www.sailboatlistings.com/view/108081), [Fisheries Supply](https://www.fisheriessupply.com/interlux-vc-17m-racing-antifouling)).
- **Sails.** Class rule: single-ply woven polyester, no film; main at least 198 g/m² with up to 4 fibreglass battens; jib at least 186 g/m² with up to 3 leech battens; spinnaker woven nylon at least 40 g/m²; windows at most 1,500 mm per side and at least 80 mm from edges; royalty label near the tack ([class rules](https://arbitrage.ffvoile.fr/media/w25lbhof/j22-2021-e.pdf)). Main and jib are white crosscut with a radial head and radial clew patch ([North M7](https://www.northsails.com/products/j-22-m7-mainsail), [Quantum](https://www.quantumsails.com/en/sails/one-design/inshore/j-22)). Jib has bronze hanks and draft stripes. Sailmakers named in 13 listings: North 8, Quantum 3, Doyle 2. Spinnaker is full or tri-radial in white, dark blue, red or combinations ([North kite](https://www.northsails.com/products/j-22-fr-1-airx-spinnaker), [UK Sailmakers](https://www.uksailmakers.com/one-design/j-22/)).
- **Markings.** Sail number is the hull number and must match the transom ID (rules A.9, C.10). About 1,650–1,700 built ([US Sailing](https://www.ussailing.org/one-design-profile/international-j-22-class-association)); range 1–1700 with "USA". Blue J/22 insignia within 305 × 610 mm on the main. Class membership sticker on the transom's upper starboard corner (rule B.2). 300 mm numbers.
- **Wear.** Club and community fleets are "ridden hard and put away wet", with grey, loose teak rails ([Sailing Anarchy](https://forums.sailinganarchy.com/threads/looking-for-advice-teak-hand-and-toe-rail-repair-replacement-j-22-repost-from-fix-it.242187/)); leaks at chainplates and deck fittings ([listing](https://www.sailboatlistings.com/view/107011)); crazing ([listing](https://boatsign.com/for-sale/j22-sailboat)); waterline yellowing that buffs out. Texas club boat: heavy chalking, grey teak, worn cockpit non-skid, gunwale and bow dock rash, rust under the outboard bracket. Dry-sailed race boat: glossy, faired, little wear. Blue Sunbrella covers.

## Sunfish

White hulls dominate. Current options are white with a red or blue three-stripe deck and coaming, plus an all-blue "Century Edition" deck ([SERO builder](https://seroinnovation.com/sunfish-builder/), [Zim ISCA](https://zimsailing.com/isca/)). Class racing sails are white with 5 panels; recreational sails are coloured with 6 panels, all by North ([ISCA FAQ](https://www.sunfishclass.org/isca_faq)); 3.8 oz Dacron with a window ([SERO sail](https://seroinnovation.com/?p=4148)); rainbow sails such as "Afterglow" ([West Coast Sailing](https://westcoastsailing.net/sunfish-sail-afterglow-SF-7C2)). Numbers are 300 mm with 60 mm spacing, black or dark blue on white (white on dark), centred under the emblem, starboard above the seam and port below; digital cut numbers allowed ([class](https://sunfishclass.org/sailnumbers)). Spars are clear-anodised aluminium. Wear (unsourced art direction): keel-line beach scuffs, chalky deck, faded red panels, dull spars.

## ILCA 7

Hulls are "slightly different shades of white or grey" ([KGSC guide](https://www.kgsc.org.uk/sailing/buying-a-used-laser)), with a few faded vintage coloured hulls ([forum](https://www.yachtsandyachting.com/Forum/printer_friendly_posts.asp?TID=3633)). The sail is MKII radial cut 4.5 oz Dacron from Hyde or North ([West Coast Sailing](https://westcoastsailing.net/ilca-7-sail-mk2-hyde/)); older MKI is crosscut ([Rooster](https://www.roostersailing.com/collections/shop-by-boat-laserilca/products/133327)); 3 battens; the logo is on one side only. Numbers ([class rule 4](https://www.laserjapan.org/info/rules/classrules/2021/4-sailnumbers2021.php)): six digits, 300 mm high, 200 mm wide, 45 mm stroke, at least 50 mm apart; last four black, leading digits contrasting (red recommended); starboard numbers 100 mm from the leech; red rhombus for women. Wear: trolley-support cracks, side-deck cracks at the footwell, foil edge wear, spar corrosion, and sails that go from crinkly to soft ([KGSC](https://www.kgsc.org.uk/sailing/buying-a-used-laser)).

## Catalina 22

The current Sport has a white hull with a moulded Midwatch Blue waterline stripe and blue plus silver sheer stripes, with Captain's Navy canvas ([Catalina](https://www.catalinayachts.com/sport-series/22-sport/)). 1970s boats have brown stripes and sometimes avocado or baby-blue decks ([forum](https://forums.sailboatowners.com/threads/71-brown.13361/latest)). Class insignia is a red diamond outline with "C" above "22"; the class rules require no sail numbers, and main battens are 4, jibs none ([class rules](https://catalina22.org/index.php/rules/68-class-rules)). Furling genoas with UV strips are a factory option. Wear: the 1969–94 cast-iron swing keel "rusted, pitted and bleeding", chainplate leaks, mast-step cracks and leaking aluminium window frames ([buyer's guide](https://keelindex.com/articles/catalina-22-buyers-guide)).

## Catalina 30

White hull with a blue double cove stripe (sold as "Sapphire Blue, Double") ([forum](https://forums.sailboatowners.com/threads/hull-stripes.1249923785/)); canvas in Pacific Blue or Captain's Navy, the most common ([forum](https://forums.sailboatowners.com/threads/which-sunbrella-blue.158102/), [C30 cover](https://forums.sailboatowners.com/threads/c30-main-sail-cover.17551/latest)). Crosscut Dacron main and a 135–150% furling genoa with a UV strip. Sail numbers are rare, 375 mm if present. Wear: chainplate rust where they pass the deck, keel-joint weeping and rust staining ([buyer's guide](https://keelindex.com/articles/catalina-30-buyers-guide)), greyed teak and the brown waterline "mustache" ([Practical Sailor](https://www.practical-sailor.com/waypoints-tips/how-to-safely-remove-the-dreaded-icw-mustache/)).

## Hobie 16

Coloured hulls faded and drew warranty claims, so Hobie moved to white ([Hobie forum](https://www.hobie.com/au/en/forums/viewtopic.php?p=5861)). In the 1980s colours were cut to white, blue and yellow ([Scuttlebutt](https://www.sailingscuttlebutt.com/2015/10/19/the-power-of-color/)). Sails are 6 oz Dacron with 8 full battens on the main and 4 on the jib ([Murrays](https://murrays.com/collections/hobie-16-sail-parts)). Current schemes include Mistral, Zephyr, White, Cayman (chartreuse, white, grey) and Tortola (orange, aqua, white) ([Hobie blog](https://www.hobie.com/blog/post/260/A-Trip-to-the-Caribbean-Introducing-Hobiee28099s-New-Sail-Colors)); vintage Tequila Sunrise and Prism stripes. Trampolines come in black, grey or turquoise ([West Coast Sailing](https://westcoastsailing.net/parts/hobie-16/trampolines)). Numbers: Hobie-issued, up to 6 digits, at least 254 mm, on each side of the main ([IHCA rules](https://hobieclass.com/ihca-class-rules-updated/)). Wear: keel lines worn through the gelcoat, then flat and concave, and repaired keels showing translucent strips ([Hobie forum](https://www.hobie.com/au/en/forums/viewtopic.php?p=35039)); sand abrasion from beaching ([Beachcats](https://thebeachcats.com/forums/general-sailing-forum/hobie-hull-wear-prevention/)).

## Corsair 880

White gelcoat with a light grey cabintop finish; standard mast painted white; the Sport has a carbon rotating wing mast and clear-coat carbon boom and sprit ([Corsair](https://corsairmarine.com/corsair-880/specifications/), [listing](https://multihullcompany.com/boat/corsair-880-sport-4195167)). Standard sails are a fully battened Dacron main and hank-on Dacron jib; the Sport has a black aramid laminate main and an aramid 110% jib ([Sport spec](https://corsairmarine.com/corsair-880/sport-specifications/)). Listings show black Doyle laminates, a furling screecher and an asymmetric spinnaker ([listing](https://www.multihullcompany.com/boat/corsair-880-sport-4257043)). Spinnaker colours and hull colours other than white are unsourced. Wear is light, since it is a design first built in 2019.

## Lagoon 42

White hulls ([listing](https://www.yachtall.com/en/boat/lagoon-42-s233753?print=1)) with dark hull-window bands and wrap-around saloon glazing (visual, unsourced). The mast is set aft with a self-tacking jib on a track and a square-top main by Incidence; the review boat flew an aquamarine Code 0 on a sprit ([SAIL review](https://www.sailmagazine.com/boats/boat-review-lagoon-42)). Charter is the main wear profile: a 2018 ex-charter boat "needs some minor cosmetic work" ([boats.com](https://ca.boats.com/sailing-boats/2018-lagoon-42-10092793)). Use salt-air wear (stainless tea staining, sugar-scoop scuffs) because it sails Galveston in the sim.

## General wear references

- UV strips: Sunbrella stitching fails at 4–6 years without high-UV thread; darker colours protect better ([Practical Sailor](https://www.practical-sailor.com/sails-rigging-deckgear/the-case-of-the-painted-jib)). Red fades most, then orange and yellow; blue and purple least ([YBW](https://forums.ybw.com/threads/why-blue.571766)). Pacific Blue is the most popular marine Sunbrella ([Sailrite](https://sailrite.com/Sunbrella-6001-0000-Pacific-Blue-60)).
- Waterline "mustache": brown tannin and algae band, most visible on white hulls ([Practical Sailor](https://www.practical-sailor.com/waypoints-tips/how-to-safely-remove-the-dreaded-icw-mustache/)).
- Unsourced but standard art direction, flagged `source: null` in the JSON: stanchion-base rust streaks, rub-rail dock rash, mildew on covers.
