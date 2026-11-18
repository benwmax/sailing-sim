# A ship's orders

On a ship (a boat with a walk map: `docs/ship-walk/`) you are her captain. G (the pad's X) opens the orders panel from the
wheel or on deck. Its own keys work while it is open: up and down choose an order, left and right switch tabs, Enter (A)
gives the order, and Backspace (B) or G closes it. The order's call goes on the status line ("Captain: Luff a point!").

* **Sails**: make all sail, fighting sail, shorten sail, furl all, tack, wear ship, heave to, fill away. The four sail plans
  are carried out now (`Sailing::ApplySailPlan` on the square rig's controls): make all sail sets every sail and shakes out
  the reefs; fighting sail keeps the topsails, jibs and spanker, clews up the courses, furls the topgallants and royals and
  hauls the staysails down; shorten sail furls the topgallants and royals and takes a reef in the topsails; furl all takes
  everything in. The crew work at the physics' pace (a sail takes about a minute to set) and the model follows
  (`docs/ship-rig/`). Tack, wear and heave to are her officers' manoeuvres (`Sailing::FShipHandling`,
  `docs/frigate-physics/`): the order hands the wheel to her helmsman, the handling works the braces, sails and helm after
  the trimmer each physics step (`FBoatStepJob::Handling`), and each step is called on the status line ("Officer of the
  watch: Mainsail haul"). Round, the helmsman takes her close-hauled on the new tack (`CourseAfterDeg`). Hove to she
  lies until "fill away", which ends the manoeuvre and has the helmsman take her a point free of close-hauled on the tack
  she lies on. While one is under way the other sail orders wait.
* **Helm**: "Helmsman: hold her" hands her helmsman the wheel at her present wind angle. "Luff a point" and "Bear away a
  point" move that angle by 11.25 degrees, between six points off the wind and dead downwind. "I have the helm" takes the
  wheel back (and walks you back to it from on deck). Walking about hands her to the helmsman too.
* **Guns**: cast loose, load, run out, fire, cease fire, secure, to port, starboard or both sides (the first row picks the
  side). The player's ship spawns her battery (`ACannonBattery`, `docs/cannon-fire/`) on her root when she is built, and
  the orders go to it (`CannonOrderFor`, `CannonSideFor`). The panel reads each side from the battery's counts
  (`GunsReadyFor`: the side's least ready gun) and remembers which sides were told to fire, for cease fire. Each shot kicks
  the camera's buffet (Settings > Camera shake), hardest for a gun beside the camera and fading past about 15 m. The
  recoil's push on the ship (`GetForceOnShip`) isn't in her physics yet.

What can be ordered follows her state (`Sailing::ShipOrderBlocked`): no sail orders during a manoeuvre, fill away only when
hove to, no luffing past close-hauled, and the guns' drill one step at a time on each side (an order to both sides goes to
whichever side can carry it out).

UI Helpful adds each order's plain line and the keys under the rows. Natural and Off show only why an order can't be given.

Code: `Source/SailingPhysics/Public/ShipOrders.h` (the orders, their calls, the rules, the panel's state), the pawn's
`GetShipOrderContext`, `OnOrdersButton`, `GiveShipOrder` and `GetOrdersPanelText` (`ShipWalkVisuals.cpp`), and the HUD's
card (`SSailHud`, top of the centre-right messages). Keys: `IMC_Ship` (the panel's key, on any ship), `IMC_Walk` above it
while walking, and `IMC_Orders` above both while the panel is open. Tests: `SailingSim.ShipOrders.Rules`, `.SailPlan`, `.Guns`, `.Panel`.
