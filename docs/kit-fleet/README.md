# The shared kit on the fleet

The other seven boats (`Tools/blender/build_fleet.py`) now carry the shared kit's fittings (`Tools/boatkit/bk_parts.py`):
the same generic, hero-quality hardware the J/22 and the maxi carry, with library materials. Before this, they had
hand-built boxes and cylinders.

## How

- **`kit_part(name, x, y, z, yaw, flip, size)`** builds one kit part and merges it into the hull's mesh before
  `finish()`. So it shares the hull's box UVs, smoothing and packs (`boat_packs.json`). The kit's library slots that
  the fleet didn't use yet are appended to `SLOTS`. A part's own UV set is dropped, because `finish()` writes the box
  UVs.
- **`place_kit`** reads `Tools/boatkit/layouts/<tag>.json` for the boats whose fittings aren't placed in code: the
  Sunfish and the ILCA. A layout entry gives:
  - `on`: `deck`, `sole` or `z`;
  - `dz`, `mirror`, `yaw`;
  - `flip`: the kit's blocks are built hanging from their head, so a block standing on deck is flipped;
  - `size` and `kw`, passed to `bk_parts.build`.
- **In code:**
  - `winch()` is the kit's `Winch16` at the catalogue size whose base is nearest: 16 on the Catalina 22 and the Corsair,
    30 on the Catalina 30, 40 on the Lagoon's cabin-top winches.
  - `cleat()` is the kit's horn cleat at the nearest length.
  - On the keelboats, the mast-step turning blocks are the kit's `Block29` and the halyard clutches its `Clutch`. They
    are 5.5 cm apart, since the kit parts are wider than the old boxes.
  - On the Hobie, the gudgeons are the kit's `Gudgeon` and the jib cars its `JibTrack`.

| Boat | Kit parts |
| --- | --- |
| Sunfish | halyard horn cleat, mainsheet block on the aft deck (`layouts/sunfish.json`) |
| ILCA 7 | ratchet block on its post in the well, six control-line cam cleats (`layouts/ilca7.json`) |
| Catalina 22, Catalina 30, Corsair 880 | sheet winches, jib-sheet and mooring horn cleats, mast-step turning blocks, halyard clutches |
| Lagoon 42 | cabin-top winches, mooring cleats |
| Hobie 16 | gudgeons on both transoms, jib tracks with cars |

Sockets are unchanged. Every hull's measures (length, beam, canoe volume, centre of buoyancy) are as before, and slot
counts are unchanged (3 or 4: the kit's materials are pack entries).

## Stills

- `<boat>-before-after.jpg`: High, uncooked, a close view of the cockpit from above, before at left.
- `blender-<boat>.jpg`: Blender views of the keelboats' decks with the kit.
