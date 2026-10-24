# The sail number's thin strokes (Oct 24 2026)

At a chase camera's distance the "1" of the sail number broke into a dashed stroke.

## Cause

M_SailCloth read the marks atlas (`T_SailMarks`, insignia and digit strip) with `SampleLevel(..., 0)`: always its
finest mip, whatever the footprint. A stroke a texel or two wide on screen then aliases.

## Fix

The atlas is read with `SampleGrad`, the gradients taken from the continuous coordinates, before the branches (a digit's
cell is picked by a `floor`, which has no useful derivative). A ray-tracing hit shader has no screen derivatives, so it
keeps mip 0.

`number.png`: the tacking demo (12 kn, overcast, High) at four moments. Top: main, where the "1" is dashed in three of
them. Bottom: with the fix, unbroken. The digits are a little softer, as their footprint is.

## Left

The speckled fringe along the sail's edge against the sky (the left of each crop) is unchanged. It isn't the leech
flutter (the same with it off) and it isn't the opacity's dither (the mask is 1 off the jib's window). Its cause needs a
deeper look.
