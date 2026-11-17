# Walking a ship (frigate wiring, part 1)

The frigate *Commonwealth* is the first boat you can walk about: from the wheel, round the spar deck, down the ladders
to the gun deck and, as the model's slices 13 and 14 land, to the berth deck, the orlop and the hold. This page covers
the walker and its map (part 1); the game's side (first-person view, keys and pad, the decks loading as you go below)
is part 2, the cameras for a 62 m ship are below, and the orders panel and the crew on deck follow.

## The walker (`Source/SailingPhysics/Public/ShipWalk.h`)

Plain C++ in the ship's own frame (metres, X forward, Y starboard, Z up, the model's origin midships on the load
waterline), so the walker rides her however she rolls and pitches, and the game only puts her transform on top. There
is no physics-engine collision: Unreal's character movement on a base that heels and pitches tens of degrees jitters,
costs a capsule sweep against millions of triangles, and can't be tested without the engine.

* **The map** (`FWalkMap`): each deck's floor height and what is overhead on a 10 cm grid, and the ladders between the
  decks, each with its foot on the lower deck and its top on the upper. `Finish()` marks where a body fits: a floor,
  1.25 m of headroom, and every floor within 0.22 m (half a sailor's shoulders) within a 0.32 m step of it.
* **Walking** (`FShipWalker::Step`): 1.4 m/s, 3 m/s running, 0.8 m/s crouched, 1.0 m/s under a beam; he slides along
  whatever stops him and moves in half-cell steps so nothing thin is stepped through.
* **Heel**: the felt gravity in the ship's frame (the game passes the physics' own) tilts the deck under him. Uphill he
  walks slower (0.84 m/s across a deck heeled 15 deg), downhill quicker (1.96 m/s). Past 24 deg his feet go and he
  slides to leeward until the side stops him; his walking can't cancel the slide, and his feet catch once she comes
  back.
* **Headroom**: the gun deck has 5 ft 9 in to 5 ft 11 in under its beams (the model thread's measurement). His eye is
  1.62 m over the floor standing, 1.15 crouched, and never closer than 0.14 m under anything over him; it eases down
  (0.12 s) a pace before a beam, so a walk along the gun deck bobs under each one.
* **Ladders**: walk onto one facing it (toward the hatch at its top, toward its foot from below) or press Use beside it;
  forward climbs, back descends (0.8 m/s along it); off at either end. Backing off a ladder's foot, or walking past its
  top, never takes it.
* **Decks to load** (`DecksWanted`): his deck, both ends of his ladder, the deck any ladder within 6 m leads to, and what
  his deck's `AlsoLoad` names (the spar deck keeps the gun deck: it shows through the open waist and the hatches).

## The map (`Tools/shipkit/frigate/walk.py`, part 2's pull request)

`walk.py` bakes `Content/TerrainData/Ships/Commonwealth.walk` from the model's `.blend` and its game data (`deck.json`,
`gundeck.json`, and the lower decks' as they land) in about 20 seconds: every 10 cm column shot from above through the
whole ship in her sea pose (guns housed; sails and running rigging left out), each deck's floor taken against its own
planking, anything with less than 1.25 m over it (a gun, the capstan, a mast) taken out, thin upright things the
columns slip past (a bulkhead, a door's frame) found by short level rays at shin, waist and chest height, and grating
holes closed. The great cabin's doors are baked open. Ladders come from the decks' json.

Build b4 (spar and gun decks): spar deck 316 m2 to walk on, gun deck 314 m2, seven ladders: the four at the breaks of
the quarterdeck and forecastle into the waist, the companion, and (when the berth deck lands) the after and fore
hatches' ladders down to it.

## Cameras for a ship (`ChaseCamera::ScaleForShip`)

A boat 45 m or longer is a ship: the chase and overview rigs drop the small boats' clamps (the chase arm stopped at
75 m, the overview's at 40), which would park the lens inside her rigging. The same framing rules: the chase arm's
origin at the spanker boom's height (up to 9 m), back 1.8 lengths or 1.55 masthead heights (about 112 m), zoom from
0.6 lengths to 6 (450 m at most). Classic, the measured runs' rig, is unchanged. Every boat before the frigate is under
45 m, so their rigs don't move (`SailingSim.Visual.ChaseCamera.Rig`).

## Tests

`SailingSim.ShipWalk.*`: `File` (the format round trip and refusals), `Ladders`, `Beams`, `Heel`, `Wander` (ten minutes
of a random walker rolling 20 deg each way, never off a floor or inside a beam), `Commonwealth` (the frigate's own map
once it is in the tree: each ladder's ends somewhere to stand, every deck reached from the spar deck).
