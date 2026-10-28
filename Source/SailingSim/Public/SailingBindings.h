#pragma once

#include "CoreMinimal.h"
#include "InputCoreTypes.h"

struct FSailingKeyBinding;

/**
 * Gamepad rebinding: the rules both columns of the Controls screen share, on a plain list of bindings (USailingInputSettings'
 * flat Bindings, where one action may carry keyboard keys, gamepad buttons and gamepad axes side by side). A row is an
 * action and a direction (scale < 0 is the negative one). The keyboard column is its first keyboard key, the gamepad
 * column its first gamepad button; sticks and triggers stay on their axes and are shown, never rebound.
 */
namespace SailingBindings
{
	enum class EColumn : uint8 { Keyboard, Gamepad };

	/** A keyboard key the keyboard column takes (not a mouse button, an axis, a gamepad key or touch). */
	SAILINGSIM_API bool IsKeyboardKey(const FKey& Key);
	/** A gamepad button the gamepad column takes: face buttons, bumpers, the D-pad, stick presses, View and Menu. */
	SAILINGSIM_API bool IsPadButton(const FKey& Key);
	/** A stick or trigger (its axis, or the button form Slate also sends for it): shown, never rebound. */
	SAILINGSIM_API bool IsPadAxis(const FKey& Key);
	SAILINGSIM_API bool InColumn(const FKey& Key, EColumn Column);

	/** Short name for a gamepad key, as the prompt bars write them: "A", "LB", "D-pad up", "Left stick". */
	SAILINGSIM_API FString PadLabel(const FKey& Key);
	/** PadLabel for gamepad keys, the key's display name otherwise. */
	SAILINGSIM_API FString KeyLabel(const FKey& Key);

	/** Menu navigation (MenuUp/Down/Left/Right) shares the arrows and the D-pad with game commands: no row, never swapped. */
	SAILINGSIM_API bool IsRowAction(FName Action);

	/**
	 * Key layers: the prologue's crew-station commands (CrewAction, Grind, TravellerDump, Station) are only live at a crew
	 * station, where the crew hold the boat's other commands, so the two layers may share a key or a button. Menu and the
	 * controls card are in both. Two rows clash (and swap on Assign) only when they share a layer.
	 */
	SAILINGSIM_API bool IsStationAction(FName Action);
	/**
	 * Photo mode's layer (docs/photo-freefly/): the free camera's commands are live only in photo mode, where the boat
	 * takes no input, so they share keys with the boat's (WASD flies, F goes back to the boat). The shutter is in this
	 * layer too (Enter, and A on the pad only while photo mode is open). Photo mode's own toggle is a boat command.
	 */
	SAILINGSIM_API bool IsPhotoAction(FName Action);
	/** The photo panel's rows, values and pages (docs/photo-mode/pc/), part of that layer. */
	SAILINGSIM_API bool IsPhotoPanelAction(FName Action);
	SAILINGSIM_API bool SameLayer(FName A, FName B);
	/** Photo mode's input context (IMC_Photo, above the boat's): every photo command, and the toggle's pad button (the
	 *  context takes that button for the orbit toggle, so it carries the hold that leaves too). */
	SAILINGSIM_API bool InPhotoContext(const FSailingKeyBinding& Binding);
	/** The boat's context: everything else, and the shutter's keyboard key (the Controls screen's Enter chooses). */
	SAILINGSIM_API bool InBoatContext(const FSailingKeyBinding& Binding);

	/** The row's key in a column (the first binding), or an invalid key. */
	SAILINGSIM_API FKey Find(const TArray<FSailingKeyBinding>& Bindings, FName Action, bool bNegative, EColumn Column);
	/** The stick or trigger that drives this row on the pad, or an invalid key. Sticks drive both directions, triggers one. */
	SAILINGSIM_API FKey FindPadAxis(const TArray<FSailingKeyBinding>& Bindings, FName Action, bool bNegative);

	struct FAssignResult
	{
		bool bChanged = false;
		/** Refused (the key belongs to a command that must keep it): Bindings are unchanged. */
		bool bRefused = false;
		/** Another row had the key: it took this row's old key (Old), or lost it when this row had none. */
		bool bSwapped = false;
		FName OtherAction;
		bool bOtherNegative = false;
		FKey Old;
	};
	/**
	 * Puts Key on the row in Key's column (the column follows the key). Another row with Key swaps to this row's old key,
	 * so nothing is left without one; if this row had none, the other row loses it (refused for Menu: the pad must keep
	 * a pause button). The same rule for both columns.
	 */
	SAILINGSIM_API FAssignResult Assign(TArray<FSailingKeyBinding>& Bindings, FName Action, bool bNegative, const FKey& Key);

	/** The live name of a command's key for prompts and tips: the gamepad's when bGamepad (its button, else its stick or
	 *  trigger), falling back to the keyboard's; "?" when unbound. Reads USailingInputSettings. */
	SAILINGSIM_API FString Label(FName Action, bool bNegative, bool bGamepad);
}
