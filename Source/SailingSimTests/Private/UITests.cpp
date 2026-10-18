#include "Misc/AutomationTest.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "SailingBindings.h"
#include "BoatModel.h"
#include "Misc/ConfigCacheIni.h"
#include "UI/SailCatalog.h"
#include "UI/SailFrontEnd.h"
#include "UI/SailHud.h"
#include "UI/SailLoading.h"
#include "LakeData.h"
#include "Dom/JsonObject.h"
#include "Framework/Application/SlateApplication.h"
#include "Misc/FileHelper.h"
#include "Widgets/Text/STextBlock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	constexpr EAutomationTestFlags UIFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	int32 JsonSpots(const FString& File)
	{
		FString Text;
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Text, *(FLakeData::DefaultDirectory() / (File + TEXT(".json"))))
			|| !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid()) return -1;
		return Root->GetArrayField(TEXT("launch_spots")).Num();
	}
}

// Graphics G4 (ui-spec.md 10, check 2): the front end's choices reach the game. Lake to Galveston and back, each with a
// different boat and preset, lands in the settings the game mode and pawn start from (world, launch spot, boat, weather
// preset, start hour, traffic, difficulty); the catalog matches the world data; every screen builds.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUISessionFlowTest, "SailingSim.UI.SessionFlow", UIFlags)
bool FSailingUISessionFlowTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	// Restored at the end: the test must not change the player's settings.
	const int32 W0 = S->World, L0 = S->LaunchSpot, B0 = S->BoatType, T0 = S->TrafficLevel;
	const ESailingWeather P0 = S->WeatherPreset;
	const float H0 = S->StartHour;
	const ESailingDifficulty D0 = S->Difficulty;
	const bool bLearn0 = S->bLearningMode;
	// The catalog, from the data.
	const TArray<SailCatalog::FWorld>& Worlds = SailCatalog::Worlds();
	TestEqual(TEXT("Two worlds"), Worlds.Num(), 2);
	TestEqual(TEXT("Lake launch spots match RayHubbard.json"), Worlds[0].Spots.Num(), JsonSpots(TEXT("RayHubbard")));
	TestEqual(TEXT("Galveston launch spots match GalvestonBay.json"), Worlds[1].Spots.Num(), JsonSpots(TEXT("GalvestonBay")));
	TestTrue(TEXT("The lake's first spot is home"), Worlds[0].Spots.Num() > 0 && Worlds[0].Spots[0].Tag == TEXT("Home"));
	TestEqual(TEXT("Eight boats"), SailCatalog::Boats().Num(), 8);
	TestEqual(TEXT("J/22 length 22'6\""), SailCatalog::Boat(0).Length, FString(TEXT("22′6″")));
	for (const SailCatalog::FBoat& B : SailCatalog::Boats()) TestFalse(FString::Printf(TEXT("%s has a close-hauled speed"), *B.Name), B.CloseHauled == TEXT("–"));
	TestEqual(TEXT("Six condition presets"), USailSessionSubsystem::Presets().Num(), 6);

	// Galveston, Hobie 16, bay sea breeze, a race in busy traffic, realistic.
	FSailSessionConfig A = USailSessionSubsystem::MakeDefault();
	A.World = 1; A.LaunchSpot = 2; A.Boat = 5; A.Mode = ESailMode::Race; A.Traffic = 2; A.bEasy = false;
	const FSailPreset* Bay = USailSessionSubsystem::Presets().FindByPredicate([](const FSailPreset& P) { return P.Id == TEXT("SeaBreeze"); });
	TestNotNull(TEXT("Bay sea breeze preset"), Bay);
	if (Bay) USailSessionSubsystem::ApplyPreset(A.Conditions, *Bay);
	USailSessionSubsystem::ApplyToSettings(A);
	TestEqual(TEXT("Galveston: world"), S->World, 1);
	TestEqual(TEXT("Galveston: launch spot"), S->LaunchSpot, 2);
	TestEqual(TEXT("Galveston: boat"), S->BoatType, 5);
	TestEqual(TEXT("Galveston: fair sky runs the afternoon breeze"), int32(S->WeatherPreset), int32(ESailingWeather::AfternoonBreeze));
	TestEqual(TEXT("Galveston: start hour"), S->StartHour, 15.f);
	TestEqual(TEXT("Galveston: busy traffic"), S->TrafficLevel, 2);
	TestTrue(TEXT("Galveston: realistic"), S->Difficulty == ESailingDifficulty::Realistic);

	// Back to the lake: the J/22, the blue norther, a drill, the lake 2 ft low (the level is the player's, kept by presets).
	FSailSessionConfig B = USailSessionSubsystem::MakeDefault();
	B.World = 0; B.LaunchSpot = 0; B.Boat = 0; B.Mode = ESailMode::Drill; B.DrillIndex = 2;
	B.Conditions.LakeLevelFt = -2.f;
	const FSailPreset* Norther = USailSessionSubsystem::Presets().FindByPredicate([](const FSailPreset& P) { return P.Id == TEXT("Norther"); });
	if (Norther) USailSessionSubsystem::ApplyPreset(B.Conditions, *Norther);
	TestEqual(TEXT("Presets keep the lake level"), B.Conditions.LakeLevelFt, -2.f);
	TestEqual(TEXT("Norther: 20 kn from the north"), B.Conditions.WindKn, 20.f);
	USailSessionSubsystem::ApplyToSettings(B);
	TestEqual(TEXT("Lake: world"), S->World, 0);
	TestEqual(TEXT("Lake: boat"), S->BoatType, 0);
	TestEqual(TEXT("Lake: overcast"), int32(S->WeatherPreset), int32(ESailingWeather::Overcast));
	TestTrue(TEXT("Lake: easy"), S->Difficulty == ESailingDifficulty::Easy);

	// Passage mode on Galveston sails the Gulf world.
	FSailSessionConfig C = A;
	C.Mode = ESailMode::Passage;
	USailSessionSubsystem::ApplyToSettings(C);
	TestEqual(TEXT("Passage: the Gulf world"), S->World, 2);

	// What to expect: the bands follow the boat.
	TestTrue(TEXT("Light air says so"), SailCatalog::Expect(3.f, 5.f, 1, 10.f, 4, 18, 0, 0).Contains(TEXT("Very light")));
	TestTrue(TEXT("A Sunfish in 25 kn capsizes"), SailCatalog::Expect(22.f, 28.f, 1, 10.f, 4, 18, 1, 0).Contains(TEXT("capsize")));
	const float Sunset = SailCatalog::SunsetHour(6, 21, 0);
	TestTrue(FString::Printf(TEXT("Midsummer sunset on the lake near 20:38 CDT (%.2f)"), Sunset), FMath::Abs(Sunset - 20.63f) < 0.25f);

	// Every screen builds (no player: the screens that need one show empty lists).
	if (FSlateApplication::IsInitialized())
	{
		for (int32 I = 0; I <= int32(ESailScreen::Controls); ++I)
		{
			TSharedRef<SSailFrontEnd> F = SNew(SSailFrontEnd).Start(ESailScreen(I));
			TestTrue(FString::Printf(TEXT("Screen %d builds"), I), F->Current() == ESailScreen(I));
		}
		TSharedRef<SSailFrontEnd> Credits = SNew(SSailFrontEnd).Start(ESailScreen::Credits);
		TestTrue(TEXT("Credits builds"), Credits->Current() == ESailScreen::Credits);
		TSharedRef<SSailHud> Hud = SNew(SSailHud);
		TestTrue(TEXT("HUD builds"), Hud->Pawn() == nullptr);
	}
	S->World = W0; S->LaunchSpot = L0; S->BoatType = B0; S->TrafficLevel = T0; S->WeatherPreset = P0; S->StartHour = H0; S->Difficulty = D0; S->bLearningMode = bLearn0;
	S->Save();
	return true;
}
namespace
{
	/** Every text block's text under a widget (upper-cased, as some styles draw it). */
	void CollectTexts(const TSharedRef<SWidget>& W, TArray<FString>& Out)
	{
		if (W->GetType() == TEXT("STextBlock")) Out.Add(StaticCastSharedRef<STextBlock>(W)->GetText().ToString().ToUpper());
		FChildren* Children = W->GetChildren();
		for (int32 I = 0; Children && I < Children->Num(); ++I) CollectTexts(Children->GetChildAt(I), Out);
	}
}

// Release readiness (docs/licences): the credits screen opens, leads with the Unreal Engine notice and shows every
// heading of CREDITS.md (read at runtime, the single source), and the Markdown reads as plain text.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUICreditsTest, "SailingSim.UI.Credits", UIFlags)
bool FSailingUICreditsTest::RunTest(const FString&)
{
	FString Markdown;
	if (!TestTrue(TEXT("CREDITS.md loads"), FFileHelper::LoadFileToString(Markdown, *SailCatalog::CreditsPath()))) return false;
	TArray<FString> Lines, Headings;
	Markdown.ParseIntoArrayLines(Lines);
	for (const FString& L : Lines) if (L.StartsWith(TEXT("#"))) Headings.Add(L.Replace(TEXT("#"), TEXT("")).TrimStartAndEnd());
	TestTrue(TEXT("CREDITS.md has its sections"), Headings.Num() >= 4);

	const TArray<SailCatalog::FCreditLine> Credits = SailCatalog::Credits();
	TestTrue(TEXT("The Unreal notice comes first"), Credits.Num() > 1 && Credits[0].Kind == SailCatalog::ECreditKind::Notice
		&& Credits[0].Text.Contains(TEXT("Made with Unreal Engine")) && Credits[0].Text.Contains(TEXT("trademark of Epic Games")));
	bool bLarus = false, bMarkdown = false;
	for (const SailCatalog::FCreditLine& L : Credits)
	{
		bLarus |= L.Text.Contains(TEXT("Larus atricilla")) && L.Text.Contains(TEXT("CC BY 3.0"));
		bMarkdown |= L.Text.Contains(TEXT("](")) || L.Text.Contains(TEXT("`")) || L.Text.Contains(TEXT("**"));
	}
	TestTrue(TEXT("Credits Larus atricilla (CC BY 3.0)"), bLarus);
	TestFalse(TEXT("No Markdown marks left"), bMarkdown);
	const TArray<SailCatalog::FCreditLine> Sample = SailCatalog::ParseCredits(TEXT("## A\n- [OSM](https://osm.org/c) and\n  `x` **y**\n\nPara [P](https://commons.wikimedia.org/wiki/File:P.jpg)."));
	TestEqual(TEXT("Parsed lines"), Sample.Num(), 4);
	if (Sample.Num() == 4)
	{
		TestEqual(TEXT("Bullet joined, link kept with its address"), Sample[2].Text, FString(TEXT("OSM (https://osm.org/c) and x y")));
		TestEqual(TEXT("Commons file link keeps its title"), Sample[3].Text, FString(TEXT("Para P.")));
	}

	if (FSlateApplication::IsInitialized())
	{
		TSharedRef<SSailFrontEnd> F = SNew(SSailFrontEnd).Start(ESailScreen::Title);
		F->Push(ESailScreen::Credits);
		TestTrue(TEXT("Credits opens from the title"), F->Current() == ESailScreen::Credits);
		TArray<FString> Texts;
		CollectTexts(F, Texts);
		auto Shows = [&Texts](const FString& S) { const FString U = S.ToUpper(); return Texts.ContainsByPredicate([&U](const FString& T) { return T.Contains(U); }); };
		TestTrue(TEXT("The screen shows the Unreal notice"), Shows(SailCatalog::UnrealNotice));
		for (const FString& H : Headings) TestTrue(FString::Printf(TEXT("The screen shows \"%s\""), *H), Shows(H));
		F->Pop();
		TestTrue(TEXT("Back returns to the title"), F->Current() == ESailScreen::Title);
	}
	return true;
}

// Bench-fix: a measuring run (bench, capture, shot, demo, drill, automation) ignores the player's saved session. With
// Galveston, the Lagoon 42 and a far launch spot in the settings (as GameUserSettings.ini would load them), the run's
// defaults are the J/22 at Rush Creek on Lake Ray Hubbard, and saving writes nothing to the player's ini.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIMeasuringIgnoresSaveTest, "SailingSim.UI.MeasuringIgnoresSave", UIFlags)
bool FSailingUIMeasuringIgnoresSaveTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	const int32 W0 = S->World, L0 = S->LaunchSpot, B0 = S->BoatType, T0 = S->TrafficLevel;
	const ESailingWeather P0 = S->WeatherPreset;
	const float H0 = S->StartHour;
	const ESailingQuality Q0 = S->Quality;
	const ESailingDifficulty D0 = S->Difficulty;
	const bool bLearn0 = S->bLearningMode;
	TestTrue(TEXT("An automation run ignores the saved choices"), USailingSettings::IgnoresSavedChoices());

	// The player's last session: Galveston, the Lagoon 42 from the third spot, busy traffic, realistic.
	FSailSessionConfig Saved = USailSessionSubsystem::MakeDefault();
	Saved.World = 1; Saved.LaunchSpot = 2; Saved.Boat = int32(Sailing::EBoatType::Lagoon42); Saved.Traffic = 2; Saved.bEasy = false;
	const FString Section = USailingSettings::StaticClass()->GetPathName();
	int32 IniWorld = -100;
	const bool bHadIniWorld = GConfig->GetInt(*Section, TEXT("World"), IniWorld, GGameUserSettingsIni);
	USailSessionSubsystem::ApplyToSettings(Saved);   // saves, which a measuring run must not
	int32 IniAfter = -100;
	const bool bHasIniAfter = GConfig->GetInt(*Section, TEXT("World"), IniAfter, GGameUserSettingsIni);
	TestTrue(TEXT("Applying a session in a measuring run leaves the ini alone"), bHadIniWorld == bHasIniAfter && IniWorld == IniAfter);
	TestEqual(TEXT("The saved world is in memory"), S->World, 1);

	USailingSettings::RestoreClassDefaults();
	TestEqual(TEXT("Run defaults: Lake Ray Hubbard"), S->World, 0);
	TestEqual(TEXT("Run defaults: Rush Creek (spot 0)"), S->LaunchSpot, 0);
	TestEqual(TEXT("Run defaults: the J/22"), S->BoatType, int32(Sailing::EBoatType::J22));
	TestEqual(TEXT("Run defaults: light traffic"), S->TrafficLevel, 1);
	TestTrue(TEXT("Run defaults: the afternoon breeze"), S->WeatherPreset == ESailingWeather::AfternoonBreeze);
	TestEqual(TEXT("Run defaults: the boat name match still picks from there"), USailingSettings::MatchBoatName(TEXT("J22")), S->BoatType);

	S->World = W0; S->LaunchSpot = L0; S->BoatType = B0; S->TrafficLevel = T0; S->WeatherPreset = P0; S->StartHour = H0; S->Quality = Q0;
	S->Difficulty = D0; S->bLearningMode = bLearn0;
	return true;
}


// Gamepad rebinding: the rules both columns of the Controls screen share (SailingBindings, pure logic on a list). A
// pad button swaps like a keyboard key, takes a free button off a command that had no old one to give, leaves menu
// navigation's shared D-pad alone, refuses sticks and triggers, and never takes Menu (the pad's only pause) for nothing.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIGamepadBindingsTest, "SailingSim.UI.GamepadBindings", UIFlags)
bool FSailingUIGamepadBindingsTest::RunTest(const FString&)
{
	using namespace SailingBindings;
	const TArray<FSailingKeyBinding>& Defaults = GetDefault<USailingInputSettings>()->GetDefaults();
	TArray<FSailingKeyBinding> L = Defaults;
	auto PadOf = [&](FName Action, bool bNeg) { return Find(L, Action, bNeg, EColumn::Gamepad); };
	auto KeyOf = [&](FName Action, bool bNeg) { return Find(L, Action, bNeg, EColumn::Keyboard); };

	// The columns.
	TestEqual(TEXT("Wing-on-wing's button is X"), PadOf(TEXT("WingOnWing"), false), EKeys::Gamepad_FaceButton_Left);
	TestEqual(TEXT("Wing-on-wing's key is G"), KeyOf(TEXT("WingOnWing"), false), EKeys::G);
	TestFalse(TEXT("Steering has no button"), PadOf(TEXT("Tiller"), true).IsValid());
	TestEqual(TEXT("Steering to port is on the left stick"), FindPadAxis(L, TEXT("Tiller"), true), EKeys::Gamepad_LeftX);
	TestEqual(TEXT("Trimming the main is the right trigger"), FindPadAxis(L, TEXT("MainSheet"), true), EKeys::Gamepad_RightTriggerAxis);
	TestEqual(TEXT("Easing the main is the left trigger"), FindPadAxis(L, TEXT("MainSheet"), false), EKeys::Gamepad_LeftTriggerAxis);
	TestEqual(TEXT("Labels: Y"), PadLabel(EKeys::Gamepad_FaceButton_Top), FString(TEXT("Y")));
	TestEqual(TEXT("Labels: RB"), PadLabel(EKeys::Gamepad_RightShoulder), FString(TEXT("RB")));
	TestTrue(TEXT("The D-pad is a button"), IsPadButton(EKeys::Gamepad_DPad_Left));
	TestFalse(TEXT("A trigger is not"), IsPadButton(EKeys::Gamepad_LeftTrigger));
	TestFalse(TEXT("A stick direction is not"), IsPadButton(EKeys::Gamepad_LeftStick_Up));

	// A swap: wing-on-wing to A, so the backstay's ease (A) takes X.
	FAssignResult R = Assign(L, TEXT("WingOnWing"), false, EKeys::Gamepad_FaceButton_Bottom);
	TestTrue(TEXT("Wing-on-wing to A: changed and swapped"), R.bChanged && R.bSwapped && R.OtherAction == TEXT("Backstay") && R.bOtherNegative);
	TestEqual(TEXT("Wing-on-wing is on A"), PadOf(TEXT("WingOnWing"), false), EKeys::Gamepad_FaceButton_Bottom);
	TestEqual(TEXT("Backstay ease took X"), PadOf(TEXT("Backstay"), true), EKeys::Gamepad_FaceButton_Left);
	TestEqual(TEXT("Wing-on-wing keeps G"), KeyOf(TEXT("WingOnWing"), false), EKeys::G);

	// A command with no button takes one: the board to Y, learning mode had Y and has none now.
	R = Assign(L, TEXT("Board"), false, EKeys::Gamepad_FaceButton_Top);
	TestTrue(TEXT("Board to Y"), R.bChanged && R.bSwapped && !R.Old.IsValid());
	TestEqual(TEXT("Board is on Y"), PadOf(TEXT("Board"), false), EKeys::Gamepad_FaceButton_Top);
	TestFalse(TEXT("Learning mode has no button now"), PadOf(TEXT("ToggleLearning"), false).IsValid());
	TestEqual(TEXT("Board keeps J"), KeyOf(TEXT("Board"), false), EKeys::J);

	// The D-pad: menu navigation shares it and is left alone.
	R = Assign(L, TEXT("Vang"), false, EKeys::Gamepad_DPad_Up);
	TestTrue(TEXT("Vang on to D-pad up"), R.bChanged && R.OtherAction == TEXT("Hike"));
	TestEqual(TEXT("Menu up keeps D-pad up"), Find(L, TEXT("MenuUp"), false, EColumn::Gamepad), EKeys::Gamepad_DPad_Up);

	// Refusals: sticks and triggers, a keyboard key's column, Menu with nothing to give back, menu navigation itself.
	const int32 N = L.Num();
	TestFalse(TEXT("A trigger can't be bound"), Assign(L, TEXT("Reef"), false, EKeys::Gamepad_LeftTriggerAxis).bChanged);
	TestFalse(TEXT("A stick can't be bound"), Assign(L, TEXT("Reef"), false, EKeys::Gamepad_LeftStick_Up).bChanged);
	R = Assign(L, TEXT("Reef"), false, EKeys::Gamepad_Special_Right);
	TestTrue(TEXT("Menu keeps its button when the reef has none to give"), R.bRefused && !R.bChanged);
	TestFalse(TEXT("Menu navigation is not a row"), Assign(L, TEXT("MenuUp"), false, EKeys::Gamepad_FaceButton_Left).bChanged);
	TestEqual(TEXT("Refusals change nothing"), L.Num(), N);
	TestEqual(TEXT("Menu still on the Menu button"), PadOf(TEXT("Menu"), false), EKeys::Gamepad_Special_Right);

	// The keyboard follows the same rule: the board to K, difficulty takes J.
	R = Assign(L, TEXT("Board"), false, EKeys::K);
	TestTrue(TEXT("Board to K swaps"), R.bChanged && R.bSwapped && R.OtherAction == TEXT("ToggleDifficulty"));
	TestEqual(TEXT("Difficulty took J"), KeyOf(TEXT("ToggleDifficulty"), false), EKeys::J);
	TestEqual(TEXT("The board's button is untouched"), PadOf(TEXT("Board"), false), EKeys::Gamepad_FaceButton_Top);

	// Round trip through Input.ini: both columns saved, reloaded, then the defaults restored.
	USailingInputSettings* Settings = GetMutableDefault<USailingInputSettings>();
	const TArray<FSailingKeyBinding> Saved = Settings->Bindings;
	Settings->Bindings = L;
	Settings->SaveConfig();
	GConfig->Flush(false, GInputIni);
	TArray<FString> IniLines;
	GConfig->GetArray(*USailingInputSettings::StaticClass()->GetPathName(), TEXT("Bindings"), IniLines, GInputIni);
	TestTrue(TEXT("Input.ini has the board on Y"), IniLines.ContainsByPredicate([](const FString& Line) { return Line.Contains(TEXT("Action=\"Board\",Key=Gamepad_FaceButton_Top")); }));
	Settings->Bindings.Reset();
	Settings->ReloadConfig();
	TestEqual(TEXT("Reloaded: as many bindings"), Settings->Bindings.Num(), L.Num());
	const TArray<FSailingKeyBinding>& Live = Settings->GetBindings();
	TestEqual(TEXT("Reloaded: board on Y"), Find(Live, TEXT("Board"), false, EColumn::Gamepad), EKeys::Gamepad_FaceButton_Top);
	TestEqual(TEXT("Reloaded: board on K"), Find(Live, TEXT("Board"), false, EColumn::Keyboard), EKeys::K);
	TestEqual(TEXT("Reloaded: wing-on-wing on A"), Find(Live, TEXT("WingOnWing"), false, EColumn::Gamepad), EKeys::Gamepad_FaceButton_Bottom);
	TestEqual(TEXT("Labels read the live pad binding"), Label(TEXT("Board"), false, true), FString(TEXT("Y")));
	TestEqual(TEXT("Labels read the live key"), Label(TEXT("Board"), false, false), FString(TEXT("K")));
	TestEqual(TEXT("A command without a button names its stick"), Label(TEXT("Tiller"), false, true), FString(TEXT("Left stick")));
	TestEqual(TEXT("And without either, its key"), Label(TEXT("Chart"), false, true), FString(TEXT("P")));
	Settings->Bindings = Settings->GetDefaults();
	TestEqual(TEXT("Defaults: board has no button"), Find(Settings->GetBindings(), TEXT("Board"), false, EColumn::Gamepad), FKey());
	TestEqual(TEXT("Defaults: learning mode on Y"), Find(Settings->GetBindings(), TEXT("ToggleLearning"), false, EColumn::Gamepad), EKeys::Gamepad_FaceButton_Top);
	// Leave the player's bindings as they were.
	Settings->Bindings = Saved;
	Settings->SaveConfig();
	return true;
}
