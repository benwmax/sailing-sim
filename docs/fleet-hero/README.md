# Fleet hero pass

The fleet's boats, one at a time in career order (Sunfish, Catalina 22, Catalina 30, ILCA, Hobie 16, Corsair 880,
Lagoon 42), each brought up to hero detail in its own generator (`Tools/blender/build_fleet.py`, still exactly the
physics hull below the waterline: `SailingSim.Visual.FleetMesh`), rebuilt with
`scripts\windows\make-boat-models.ps1 -Parts fleet -Fleet <Tag>`.

## Sunfish

Its signatures: the lateen rig, the cockpit well and the dinghy-park sun fade.

- **Rig:** the masthead is the class's black halyard cap with its sheave and the halyard down the forward face (the
  generic wind indicator is gone); the yard ends at the sail's head with black end caps, carries its halyard eye a
  third of the way up, and meets the boom at a through-bolted stainless gooseneck jaw.
- **Well:** a moulded lip round its edge (the deck's gelcoat, rounded corners) and the hiking strap's webbing ends on
  the sole, beside the existing bailer, drain, splash guard and board.
- **Sun fade:** the catalogue's `sail_panel_fade` zones (kind `fade`) now reach the game: `make_liveries.py` writes
  `FLiveryWear::FadeRange` per profile, `SampleBoatLivery` draws `FBoatLivery::SailFade` from its own random stream (the
  sail numbers drawn after it are unchanged), and the pawn hands it to `M_SailCloth`'s new `Fade`. Dyed panels fade
  toward a chalky pastel, reds first and blues least, the head and leech (rolled outermost on the spars in a dinghy
  park) most; white cloth keeps the Dacron ageing it had. The Sunfish's club boats fade 0.4-0.8 (the player's 0.6).

![Before (left), after (middle) and the well from above (right), Ultra on the lake](sunfish-before-after-deck.jpg)

## ILCA

- **Mast:** the two-piece spar, its collar over the joint 2.85 m up, the black gooseneck fitting the boom pins to, the
  rotating mast's step ring and the cunningham hook.
- **Boom:** the outhaul cleat and fairlead, the clew's tie-down strap round the boom end and the vang key.

![Before (left), after (middle) and close (right), Ultra on the lake](ilca-before-after.jpg)
