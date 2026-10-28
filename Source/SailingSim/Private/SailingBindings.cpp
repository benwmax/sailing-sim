#include "SailingBindings.h"
#include "SailingSettings.h"

namespace SailingBindings
{
	namespace
	{
		struct FPadName { FKey Key; const TCHAR* Label; };

		const TArray<FPadName>& PadButtons()
		{
			static const TArray<FPadName> Buttons = {
				{ EKeys::Gamepad_FaceButton_Bottom, TEXT("A") }, { EKeys::Gamepad_FaceButton_Right, TEXT("B") },
				{ EKeys::Gamepad_FaceButton_Left, TEXT("X") }, { EKeys::Gamepad_FaceButton_Top, TEXT("Y") },
				{ EKeys::Gamepad_LeftShoulder, TEXT("LB") }, { EKeys::Gamepad_RightShoulder, TEXT("RB") },
				{ EKeys::Gamepad_DPad_Up, TEXT("D-pad up") }, { EKeys::Gamepad_DPad_Down, TEXT("D-pad down") },
				{ EKeys::Gamepad_DPad_Left, TEXT("D-pad left") }, { EKeys::Gamepad_DPad_Right, TEXT("D-pad right") },
				{ EKeys::Gamepad_LeftThumbstick, TEXT("Left stick press") }, { EKeys::Gamepad_RightThumbstick, TEXT("Right stick press") },
				{ EKeys::Gamepad_Special_Left, TEXT("View") }, { EKeys::Gamepad_Special_Right, TEXT("Menu") } };
			return Buttons;
		}

		const TArray<FPadName>& PadAxes()
		{
			static const TArray<FPadName> Axes = {
				{ EKeys::Gamepad_LeftX, TEXT("Left stick") }, { EKeys::Gamepad_LeftY, TEXT("Left stick") }, { EKeys::Gamepad_Left2D, TEXT("Left stick") },
				{ EKeys::Gamepad_RightX, TEXT("Right stick") }, { EKeys::Gamepad_RightY, TEXT("Right stick") }, { EKeys::Gamepad_Right2D, TEXT("Right stick") },
				{ EKeys::Gamepad_LeftTriggerAxis, TEXT("LT") }, { EKeys::Gamepad_RightTriggerAxis, TEXT("RT") },
				{ EKeys::Gamepad_LeftTrigger, TEXT("LT") }, { EKeys::Gamepad_RightTrigger, TEXT("RT") },
				{ EKeys::Gamepad_LeftStick_Up, TEXT("Left stick") }, { EKeys::Gamepad_LeftStick_Down, TEXT("Left stick") },
				{ EKeys::Gamepad_LeftStick_Left, TEXT("Left stick") }, { EKeys::Gamepad_LeftStick_Right, TEXT("Left stick") },
				{ EKeys::Gamepad_RightStick_Up, TEXT("Right stick") }, { EKeys::Gamepad_RightStick_Down, TEXT("Right stick") },
				{ EKeys::Gamepad_RightStick_Left, TEXT("Right stick") }, { EKeys::Gamepad_RightStick_Right, TEXT("Right stick") } };
			return Axes;
		}

		bool IsTrigger(const FKey& Key)
		{
			return Key == EKeys::Gamepad_LeftTriggerAxis || Key == EKeys::Gamepad_RightTriggerAxis || Key == EKeys::Gamepad_LeftTrigger || Key == EKeys::Gamepad_RightTrigger;
		}

		bool SameRow(const FSailingKeyBinding& B, FName Action, bool bNegative) { return B.Action == Action && (B.Scale < 0.f) == bNegative; }
	}

	bool IsKeyboardKey(const FKey& Key)
	{
		return Key.IsValid() && !Key.IsGamepadKey() && !Key.IsMouseButton() && !Key.IsAxis1D() && !Key.IsAxis2D() && !Key.IsAxis3D() && !Key.IsTouch()
			&& Key != EKeys::MouseWheelAxis && Key != EKeys::Mouse2D;
	}

	bool IsPadButton(const FKey& Key) { return PadButtons().ContainsByPredicate([&](const FPadName& P) { return P.Key == Key; }); }
	bool IsPadAxis(const FKey& Key) { return PadAxes().ContainsByPredicate([&](const FPadName& P) { return P.Key == Key; }); }
	bool InColumn(const FKey& Key, EColumn Column) { return Column == EColumn::Gamepad ? IsPadButton(Key) : IsKeyboardKey(Key); }

	FString PadLabel(const FKey& Key)
	{
		for (const FPadName& P : PadButtons()) if (P.Key == Key) return P.Label;
		for (const FPadName& P : PadAxes()) if (P.Key == Key) return P.Label;
		return Key.GetDisplayName().ToString();
	}

	FString KeyLabel(const FKey& Key)
	{
		if (!Key.IsValid()) return TEXT("–");
		return Key.IsGamepadKey() ? PadLabel(Key) : Key.GetDisplayName().ToString();
	}

	bool IsRowAction(FName Action)
	{
		return Action != TEXT("MenuUp") && Action != TEXT("MenuDown") && Action != TEXT("MenuLeft") && Action != TEXT("MenuRight");
	}

	bool IsStationAction(FName Action)
	{
		return Action == TEXT("CrewAction") || Action == TEXT("Grind") || Action == TEXT("TravellerDump") || Action == TEXT("Station");
	}

	bool IsPhotoAction(FName Action)
	{
		return Action == TEXT("PhotoShot") || Action == TEXT("PhotoForward") || Action == TEXT("PhotoRight") || Action == TEXT("PhotoUpDown")
			|| Action == TEXT("PhotoRoll") || Action == TEXT("PhotoRollReset") || Action == TEXT("PhotoBoost") || Action == TEXT("PhotoSlow")
			|| Action == TEXT("PhotoSpeed") || Action == TEXT("PhotoToBoat") || Action == TEXT("PhotoOrbit") || Action == TEXT("PhotoHideUI")
			|| IsPhotoPanelAction(Action);
	}

	bool IsPhotoPanelAction(FName Action)
	{
		return Action == TEXT("PhotoRowDown") || Action == TEXT("PhotoRowUp") || Action == TEXT("PhotoValueUp") || Action == TEXT("PhotoValueDown")
			|| Action == TEXT("PhotoPageNext") || Action == TEXT("PhotoPagePrev");
	}

	bool SameLayer(FName A, FName B)
	{
		// The photo layer has its own keys for the menu (Tab orbits; Esc, fixed, still leaves).
		if (IsPhotoAction(A) || IsPhotoAction(B)) return IsPhotoAction(A) == IsPhotoAction(B);
		auto Global = [](FName N) { return N == TEXT("Menu") || N == TEXT("ControlsCard"); };
		return Global(A) || Global(B) || IsStationAction(A) == IsStationAction(B);
	}

	bool InPhotoContext(const FSailingKeyBinding& Binding)
	{
		return IsPhotoAction(Binding.Action) || (Binding.Action == TEXT("Photo") && Binding.Key.IsGamepadKey());
	}

	bool InBoatContext(const FSailingKeyBinding& Binding)
	{
		return !IsPhotoAction(Binding.Action) || (Binding.Action == TEXT("PhotoShot") && !Binding.Key.IsGamepadKey());
	}

	FKey Find(const TArray<FSailingKeyBinding>& Bindings, FName Action, bool bNegative, EColumn Column)
	{
		for (const FSailingKeyBinding& B : Bindings) if (SameRow(B, Action, bNegative) && InColumn(B.Key, Column)) return B.Key;
		return FKey();
	}

	FKey FindPadAxis(const TArray<FSailingKeyBinding>& Bindings, FName Action, bool bNegative)
	{
		for (const FSailingKeyBinding& B : Bindings)
		{
			if (B.Action != Action || !IsPadAxis(B.Key)) continue;
			// A trigger pulls one way; a stick axis covers both directions of its command.
			if (!IsTrigger(B.Key) || (B.Scale < 0.f) == bNegative) return B.Key;
		}
		return FKey();
	}

	FAssignResult Assign(TArray<FSailingKeyBinding>& Bindings, FName Action, bool bNegative, const FKey& Key)
	{
		FAssignResult R;
		const EColumn Column = IsPadButton(Key) ? EColumn::Gamepad : EColumn::Keyboard;
		if (!InColumn(Key, Column) || !IsRowAction(Action)) return R;
		R.Old = Find(Bindings, Action, bNegative, Column);
		if (R.Old == Key) return R;
		// Who else has it (menu navigation shares keys on purpose and is left alone).
		int32 Other = INDEX_NONE;
		for (int32 I = 0; I < Bindings.Num(); ++I)
		{
			const FSailingKeyBinding& B = Bindings[I];
			if (B.Key == Key && IsRowAction(B.Action) && !SameRow(B, Action, bNegative) && SameLayer(B.Action, Action)) { Other = I; break; }
		}
		if (Other != INDEX_NONE)
		{
			if (!R.Old.IsValid() && Bindings[Other].Action == TEXT("Menu")) { R.bRefused = true; R.OtherAction = Bindings[Other].Action; return R; }
			R.bSwapped = true;
			R.OtherAction = Bindings[Other].Action;
			R.bOtherNegative = Bindings[Other].Scale < 0.f;
			// Every binding of that key on another row moves (an action can list the same key twice in a hand-edited ini).
			for (int32 I = Bindings.Num() - 1; I >= 0; --I)
			{
				FSailingKeyBinding& B = Bindings[I];
				if (B.Key != Key || !IsRowAction(B.Action) || SameRow(B, Action, bNegative) || !SameLayer(B.Action, Action)) continue;
				if (R.Old.IsValid()) B.Key = R.Old;
				else Bindings.RemoveAt(I);
			}
		}
		bool bPlaced = false;
		if (R.Old.IsValid())
		{
			for (FSailingKeyBinding& B : Bindings)
				if (SameRow(B, Action, bNegative) && B.Key == R.Old) { B.Key = Key; bPlaced = true; break; }
		}
		if (!bPlaced)
		{
			FSailingKeyBinding B;
			B.Action = Action;
			B.Key = Key;
			B.Scale = bNegative ? -1.f : 1.f;
			Bindings.Add(B);
		}
		R.bChanged = true;
		return R;
	}

	FString Label(FName Action, bool bNegative, bool bGamepad)
	{
		const TArray<FSailingKeyBinding>& Bindings = GetDefault<USailingInputSettings>()->GetBindings();
		if (bGamepad)
		{
			FKey Pad = Find(Bindings, Action, bNegative, EColumn::Gamepad);
			if (!Pad.IsValid()) Pad = FindPadAxis(Bindings, Action, bNegative);
			if (Pad.IsValid()) return PadLabel(Pad);
		}
		const FKey Key = Find(Bindings, Action, bNegative, EColumn::Keyboard);
		return Key.IsValid() ? Key.GetDisplayName().ToString() : FString(TEXT("?"));
	}
}
