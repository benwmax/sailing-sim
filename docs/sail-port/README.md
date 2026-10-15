# Sail numbers on both sides

Before this, `M_SailCloth` drew one set of marks from the cloth's UVs, the same on both faces of the (two-sided) cloth. It
read right from port and mirrored from starboard.

Now each face draws its own set (`TwoSidedSign` into the sail code as `Face`, +1 on the starboard face):

- **Starboard:** the insignia and the number, looked up mirrored along the chord, so they read right from that side.
- **Port:** the number one row lower (0.48 instead of 0.62 of the height), as the class rules ask, so the two sets don't
  show through each other. The insignia are back to back, as on a real sail.
- **Against the light:** both sets block the light through the cloth, so the other side's number shows faintly, mirrored.
  A real sail does the same.

This covers every class: the J/22's insignia and number, and the numbers of the other classes (`Marks` 1 and 2). The hero
J/22's sails are the same `FSailCloth` meshes, and its numbers aren't baked anywhere else.

![Port (left) and starboard (right), close-hauled, morning; the insignia close up in the evening (bottom)](both-sides.jpg)

The top row is lit from the morning sun, so the port side is front-lit and starboard is against the light (the port number
shows through). The bottom row is the evening, the other way round.
