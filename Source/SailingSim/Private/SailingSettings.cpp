#include "SailingSettings.h"

USailingInputSettings::USailingInputSettings()
{
	auto Add = [this](const TCHAR* Action, const FKey& Key, float Scale = 1.f)
	{
		FSailingKeyBinding B;
		B.Action = Action;
		B.Key = Key;
		B.Scale = Scale;
		Defaults.Add(B);
	};

	// Tiller: positive turns the bow to starboard.
	Add(TEXT("Tiller"), EKeys::D);
	Add(TEXT("Tiller"), EKeys::A, -1.f);
	Add(TEXT("Tiller"), EKeys::Right);
	Add(TEXT("Tiller"), EKeys::Left, -1.f);
	Add(TEXT("Tiller"), EKeys::Gamepad_LeftX);

	// Sheets: positive eases, negative trims in.
	Add(TEXT("MainSheet"), EKeys::S);
	Add(TEXT("MainSheet"), EKeys::W, -1.f);
	Add(TEXT("MainSheet"), EKeys::Gamepad_LeftTriggerAxis);
	Add(TEXT("MainSheet"), EKeys::Gamepad_RightTriggerAxis, -1.f);
	Add(TEXT("JibSheet"), EKeys::Q);
	Add(TEXT("JibSheet"), EKeys::E, -1.f);
	Add(TEXT("JibSheet"), EKeys::Gamepad_LeftShoulder);
	Add(TEXT("JibSheet"), EKeys::Gamepad_RightShoulder, -1.f);

	// Traveler: positive to leeward, negative to windward.
	Add(TEXT("Traveler"), EKeys::C);
	Add(TEXT("Traveler"), EKeys::Z, -1.f);
	Add(TEXT("Traveler"), EKeys::Gamepad_DPad_Right);
	Add(TEXT("Traveler"), EKeys::Gamepad_DPad_Left, -1.f);

	// Crew: positive hikes out, negative moves in (and to leeward).
	Add(TEXT("Hike"), EKeys::F);
	Add(TEXT("Hike"), EKeys::V, -1.f);
	Add(TEXT("Hike"), EKeys::Gamepad_DPad_Up);
	Add(TEXT("Hike"), EKeys::Gamepad_DPad_Down, -1.f);

	// Sail shape: positive pulls on.
	Add(TEXT("Vang"), EKeys::Two);
	Add(TEXT("Vang"), EKeys::One, -1.f);
	Add(TEXT("Cunningham"), EKeys::Four);
	Add(TEXT("Cunningham"), EKeys::Three, -1.f);
	Add(TEXT("Outhaul"), EKeys::Six);
	Add(TEXT("Outhaul"), EKeys::Five, -1.f);
	Add(TEXT("Backstay"), EKeys::Eight);
	Add(TEXT("Backstay"), EKeys::Seven, -1.f);
	Add(TEXT("Backstay"), EKeys::Gamepad_FaceButton_Right);
	Add(TEXT("Backstay"), EKeys::Gamepad_FaceButton_Bottom, -1.f);

	// Camera.
	Add(TEXT("Look"), EKeys::Mouse2D);
	Add(TEXT("Look"), EKeys::Gamepad_Right2D, 3.f);
	Add(TEXT("Zoom"), EKeys::MouseWheelAxis);

	// Buttons.
	Add(TEXT("WingOnWing"), EKeys::G);
	Add(TEXT("WingOnWing"), EKeys::Gamepad_FaceButton_Left);
	Add(TEXT("ToggleLearning"), EKeys::L);
	Add(TEXT("ToggleLearning"), EKeys::Gamepad_FaceButton_Top);
	Add(TEXT("ToggleDifficulty"), EKeys::K);
	Add(TEXT("ToggleHud"), EKeys::H);
	Add(TEXT("ResetBoat"), EKeys::R);
	Add(TEXT("DockLines"), EKeys::T);
	Add(TEXT("BackJib"), EKeys::B);
	Add(TEXT("BackJib"), EKeys::Gamepad_LeftThumbstick);
	Add(TEXT("DockLines"), EKeys::Gamepad_RightThumbstick);
	Add(TEXT("ControlsCard"), EKeys::Slash);
	Add(TEXT("ControlsCard"), EKeys::Gamepad_Special_Left);
	Add(TEXT("Menu"), EKeys::Tab);
	Add(TEXT("Menu"), EKeys::Gamepad_Special_Right);
	Add(TEXT("MenuUp"), EKeys::Up);
	Add(TEXT("MenuUp"), EKeys::Gamepad_DPad_Up);
	Add(TEXT("MenuDown"), EKeys::Down);
	Add(TEXT("MenuDown"), EKeys::Gamepad_DPad_Down);
	Add(TEXT("MenuLeft"), EKeys::Left);
	Add(TEXT("MenuLeft"), EKeys::Gamepad_DPad_Left);
	Add(TEXT("MenuRight"), EKeys::Right);
	Add(TEXT("MenuRight"), EKeys::Gamepad_DPad_Right);
}
