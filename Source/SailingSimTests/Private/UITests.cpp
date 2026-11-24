#include "Misc/AutomationTest.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "SailSave.h"
#include "SailingBindings.h"
#include "BoatModel.h"
#include "Misc/ConfigCacheIni.h"
#include "UI/SailCatalog.h"
#include "BenchRunner.h"
#include "Misc/ScopeExit.h"
#include "UI/SailFrontEnd.h"
#include "UI/SailHud.h"
#include "UI/SailUIStyle.h"
#include "UI/SailWidgets.h"
#include "SailingHUD.h"
#include "SailCloth.h"
#include "EasyAssists.h"
#include "UI/SailLoading.h"
#include "UI/SailSplash.h"
#include "LakeData.h"
#include "SailboatPawn.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "Dom/JsonObject.h"
#include "Framework/Application/SlateApplication.h"
#include "Misc/FileHelper.h"
#include "Internationalization/Regex.h"
#include "HAL/FileManager.h"
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
	TestEqual(TEXT("Four worlds (the lake, Galveston, Marseille, the streamed Texas coast)"), Worlds.Num(), 4);
	TestTrue(TEXT("The Texas coast's launch spots match TexasCoast.json"), Worlds.Num() > 3 && Worlds[3].Index == 4 && Worlds[3].Spots.Num() == JsonSpots(TEXT("TexasCoast")));
	TestEqual(TEXT("Lake launch spots match RayHubbard.json"), Worlds[0].Spots.Num(), JsonSpots(TEXT("RayHubbard")));
	TestEqual(TEXT("Galveston launch spots match GalvestonBay.json"), Worlds[1].Spots.Num(), JsonSpots(TEXT("GalvestonBay")));
	TestTrue(TEXT("Marseille launch spots match Marseille.json"), Worlds.Num() > 2 && Worlds[2].Index == 3 && Worlds[2].Spots.Num() == JsonSpots(TEXT("Marseille")));
	TestTrue(TEXT("The lake's first spot is home"), Worlds[0].Spots.Num() > 0 && Worlds[0].Spots[0].Tag == TEXT("Home"));
	TestEqual(TEXT("Eleven boats (the fleet, the prologue's maxi, Bluebonnet and the frigate)"), SailCatalog::Boats().Num(), 11);
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
	// The Sky row's Rain: steady rain from the start (the Rain preset), named for the loading screen.
	B.Conditions.Sky = ESailSky::Rain;
	USailSessionSubsystem::ApplyToSettings(B);
	TestEqual(TEXT("Lake: rain runs the Rain preset"), int32(S->WeatherPreset), int32(ESailingWeather::Rain));
	TestEqual(TEXT("Rain's name"), USailSessionSubsystem::SkyName(ESailSky::Rain), FString(TEXT("Rain")));

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
		TSharedRef<SSailFrontEnd> LogScreen = SNew(SSailFrontEnd).Start(ESailScreen::Logbook);
		TestTrue(TEXT("Logbook builds"), LogScreen->Current() == ESailScreen::Logbook);
		TSharedRef<SSailHud> Hud = SNew(SSailHud);
		TestTrue(TEXT("HUD builds"), Hud->Pawn() == nullptr);
	}
	{
		// The night palette (docs/ui-overhaul/, Phase 6): day colours untouched, the dark all red, the accent still bright.
		const FLinearColor Day = SSailHud::NightColor(SailUI::Accent, 0.f);
		TestTrue(TEXT("By day a colour is itself"), Day.Equals(SailUI::Accent));
		const FLinearColor Aqua = SSailHud::NightColor(SailUI::Accent, 1.f);
		const FLinearColor Cream = SSailHud::NightColor(SailUI::Fg, 1.f);
		TestTrue(TEXT("At night the accent is red"), Aqua.R > 3.f * Aqua.G && Aqua.R > 3.f * Aqua.B);
		TestTrue(TEXT("... and keeps its brightness in the red"), Aqua.R > 0.3f);
		TestTrue(TEXT("At night the text is red"), Cream.R > 3.f * Cream.G && Cream.R > 3.f * Cream.B);
		TestTrue(TEXT("Opacity is kept"), FMath::IsNearlyEqual(SSailHud::NightColor(SailUI::Panel, 1.f).A, SailUI::Panel.A));
		TestEqual(TEXT("No red at sunset"), SSailHud::NightHudAmount(0.f, true), 0.f);
		TestEqual(TEXT("No red in early twilight"), SSailHud::NightHudAmount(0.25f, true), 0.f);
		TestEqual(TEXT("All red in the dark"), SSailHud::NightHudAmount(1.f, true), 1.f);
		TestEqual(TEXT("Turned off, never red"), SSailHud::NightHudAmount(1.f, false), 0.f);
		// The chart minimap's scale bar (Phase 7): a round length that fits in 40% of the width.
		float BarPx = 0.f;
		TestEqual(TEXT("The lake's 3 km map: half a mile"), SSailHud::MiniMapScaleBar(3000.0, 198.f, BarPx), FString(TEXT("0.5 nm")));
		TestTrue(FString::Printf(TEXT("... 926 m of it (%.1f px)"), BarPx), FMath::IsNearlyEqual(BarPx, 926.f * 198.f / 3000.f, 0.01f));
		TestEqual(TEXT("Offshore's 8 km map: a mile"), SSailHud::MiniMapScaleBar(8000.0, 198.f, BarPx), FString(TEXT("1 nm")));
		TestTrue(TEXT("... inside 40% of the width"), BarPx <= 198.f * 0.4f);
		TestEqual(TEXT("No span: the shortest, no length"), SSailHud::MiniMapScaleBar(0.0, 198.f, BarPx), FString(TEXT("0.1 nm")));
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
	const TArray<SailCatalog::FCreditLine> Credits = SailCatalog::Credits();
	TArray<FString> Headings;
	for (const SailCatalog::FCreditLine& L : Credits)
		if (L.Kind == SailCatalog::ECreditKind::Heading1 || L.Kind == SailCatalog::ECreditKind::Heading2 || L.Kind == SailCatalog::ECreditKind::Heading3)
			Headings.Add(L.Text);
	TestTrue(TEXT("CREDITS.md has its sections"), Headings.Num() >= 4);
	TestTrue(TEXT("The Unreal notice comes first"), Credits.Num() > 1 && Credits[0].Kind == SailCatalog::ECreditKind::Notice
		&& Credits[0].Text.Contains(TEXT("Ready About: Sailing uses Unreal")) && Credits[0].Text.Contains(TEXT("trademark or registered trademark of Epic Games, Inc. in the United States of America and elsewhere."))
		&& Credits[0].Text.Contains(FString::Printf(TEXT("Copyright 1998 – %d, Epic Games, Inc. All rights reserved."), FDateTime::UtcNow().GetYear())));
	bool bLarus = false, bMarkdown = false;
	for (const SailCatalog::FCreditLine& L : Credits)
	{
		bLarus |= L.Text.Contains(TEXT("Larus atricilla")) && L.Text.Contains(TEXT("CC BY 3.0"));
		bMarkdown |= L.Text.Contains(TEXT("](")) || L.Text.Contains(TEXT("`")) || L.Text.Contains(TEXT("**"));
	}
	TestTrue(TEXT("Credits Larus atricilla (CC BY 3.0)"), bLarus);
	TestFalse(TEXT("No Markdown marks left"), bMarkdown);
	// feedback #487: the screen is for players, so no repo paths, phase or round notes, names of the team or the
	// repo-only photo list (CREDITS.md keeps those between <!-- game:skip --> and <!-- game:end -->).
	// "Phase" only as a phase number (a moon phase is fine); the team's names are matched with their case.
	const FRegexPattern PhaseNote(TEXT("[Pp]hase[ -]?[0-9]"));
	for (const SailCatalog::FCreditLine& L : Credits)
	{
		for (const TCHAR* Dev : { TEXT("docs/"), TEXT("/Users"), TEXT("Graphics G"), TEXT("/Game/"), TEXT("Source/"), TEXT("scripts/"),
			TEXT("Inputs/"), TEXT("Tools/"), TEXT("placeholder"), TEXT("the repo"), TEXT("<!--") })
			if (L.Text.Contains(Dev)) AddError(FString::Printf(TEXT("Credits show developer text \"%s\": %s"), Dev, *L.Text.Left(120)));
		FRegexMatcher Phase(PhaseNote, L.Text);
		if (Phase.FindNext() || L.Text.Contains(TEXT("Bean"), ESearchCase::CaseSensitive))
			AddError(FString::Printf(TEXT("Credits show a phase note or a name: %s"), *L.Text.Left(120)));
	}
	// Every skip is closed (an open one hides the rest of the file), and the player's last section still shows.
	int32 Open = 0;
	{
		TArray<FString> Lines;
		Markdown.ParseIntoArrayLines(Lines);
		for (const FString& Raw : Lines)
		{
			const FString T = Raw.TrimStart();
			if (!T.StartsWith(TEXT("<!--"))) continue;
			const FString M = T.Mid(4).TrimStart();
			if (M.StartsWith(TEXT("game:skip"))) { TestEqual(TEXT("game:skip not nested"), Open, 0); ++Open; }
			else if (M.StartsWith(TEXT("game:end"))) { TestEqual(TEXT("game:end closes a skip"), Open, 1); Open = 0; }
		}
	}
	TestEqual(TEXT("Every game:skip in CREDITS.md has its game:end"), Open, 0);
	TestTrue(TEXT("The credits reach their last section"), Headings.Contains(TEXT("Sound and map credits")));
	const TArray<SailCatalog::FCreditLine> Skipped = SailCatalog::ParseCredits(TEXT("## A\nShown.\n<!--game:skip-->\n## B\nHidden.\n<!--  game:end -->\nAfter."));
	TestEqual(TEXT("game:skip drops its block (any spacing)"), Skipped.Num(), 4);
	if (Skipped.Num() == 4) TestEqual(TEXT("game:end resumes"), Skipped[3].Text, FString(TEXT("After.")));
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
		TestTrue(TEXT("The screen shows the Unreal notice"), Shows(SailCatalog::UnrealNotice()));
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
	// Prologue step 2: the station layer shares buttons with commands the crew hold at a station, and is left alone.
	TestEqual(TEXT("Grinding stays on A beside wing-on-wing"), PadOf(TEXT("Grind"), false), EKeys::Gamepad_FaceButton_Bottom);
	TestTrue(TEXT("The two layers may share a button"), !SameLayer(TEXT("Grind"), TEXT("WingOnWing")) && SameLayer(TEXT("Grind"), TEXT("Station")) && SameLayer(TEXT("Grind"), TEXT("Menu")));
	R = Assign(L, TEXT("Station"), false, EKeys::Gamepad_FaceButton_Bottom);
	TestTrue(TEXT("Within the station layer keys still swap: station to A, grinding takes Y"), R.bChanged && R.bSwapped && R.OtherAction == TEXT("Grind"));
	TestEqual(TEXT("Grinding took Y"), PadOf(TEXT("Grind"), false), EKeys::Gamepad_FaceButton_Top);
	TestEqual(TEXT("Wing-on-wing still on A"), PadOf(TEXT("WingOnWing"), false), EKeys::Gamepad_FaceButton_Bottom);
	TestEqual(TEXT("Learning mode keeps Y"), PadOf(TEXT("ToggleLearning"), false), EKeys::Gamepad_FaceButton_Top);

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
	TestEqual(TEXT("Defaults: the wrist compass is on the period key"), Find(Settings->GetBindings(), TEXT("Wrist"), false, EColumn::Keyboard), EKeys::Period);
	TestEqual(TEXT("Defaults: learning mode on Y"), Find(Settings->GetBindings(), TEXT("ToggleLearning"), false, EColumn::Gamepad), EKeys::Gamepad_FaceButton_Top);
	// Leave the player's bindings as they were.
	Settings->Bindings = Saved;
	Settings->SaveConfig();
	return true;
}

/**
 * Bean's playtest (Oct 20): the Display and Graphics rows. They go through the save and back; a Quality tier puts them all
 * back on Auto (it is their preset); Auto is -1 so the Mac's tiers keep their own; the field of view and brightness clamp
 * and default to the game's 90 and 100%.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIGraphicsRowsTest, "SailingSim.UI.GraphicsRows", UIFlags)
bool FSailingUIGraphicsRowsTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	int32 USailingSettings::* const Rows[] = { &USailingSettings::AntiAliasing, &USailingSettings::ShadowQuality, &USailingSettings::LightingQuality, &USailingSettings::ReflectionQuality,
		&USailingSettings::CloudQuality, &USailingSettings::WaterQuality, &USailingSettings::FoliageQuality, &USailingSettings::ViewDistanceQuality, &USailingSettings::MotionBlur,
		&USailingSettings::FieldOfView, &USailingSettings::Brightness };
	TArray<int32> Kept;
	for (int32 USailingSettings::* R : Rows) Kept.Add(S->*R);
	const bool bVSync0 = S->bVSync;
	TestTrue(TEXT("The class defaults are all Auto"), GetDefault<USailingSettings>()->AntiAliasing == -1 && GetDefault<USailingSettings>()->ShadowQuality == -1
		&& GetDefault<USailingSettings>()->CloudQuality == -1 && GetDefault<USailingSettings>()->MotionBlur == -1 && !GetDefault<USailingSettings>()->bVSync
		&& GetDefault<USailingSettings>()->FieldOfView == 0 && GetDefault<USailingSettings>()->Brightness == 100);
	S->AntiAliasing = 5; S->ShadowQuality = 3; S->LightingQuality = 0; S->ReflectionQuality = 1; S->CloudQuality = 2; S->WaterQuality = 0;
	S->FoliageQuality = 1; S->ViewDistanceQuality = 3; S->MotionBlur = 0; S->bVSync = true; S->FieldOfView = 105; S->Brightness = 120;
	FSailSave Save;
	Save.Capture(*S, *GetMutableDefault<USailSessionSave>());
	FSailSave Back;
	FSailSave::FromJson(Save.ToJson(), Back);
	USailingSettings* Out = NewObject<USailingSettings>();
	Back.Apply(*Out, *NewObject<USailSessionSave>());
	TestTrue(TEXT("The rows round-trip through the save"), Out->AntiAliasing == 5 && Out->ShadowQuality == 3 && Out->LightingQuality == 0 && Out->ReflectionQuality == 1
		&& Out->CloudQuality == 2 && Out->WaterQuality == 0 && Out->FoliageQuality == 1 && Out->ViewDistanceQuality == 3 && Out->MotionBlur == 0 && Out->bVSync
		&& Out->FieldOfView == 105 && Out->Brightness == 120);
	TestEqual(TEXT("The field of view as set"), Out->ChaseFov(), 105.f);
	TestTrue(TEXT("Brightness 120% is a quarter stop up"), FMath::IsNearlyEqual(Out->BrightnessBias(), FMath::Log2(1.2f), 1e-4f));
	Out->FieldOfView = 200; Out->Brightness = 10;
	TestEqual(TEXT("The field of view clamps to 120"), Out->ChaseFov(), 120.f);
	TestTrue(TEXT("Brightness clamps to half"), FMath::IsNearlyEqual(Out->BrightnessBias(), -1.f, 1e-4f));
	Out->FieldOfView = 0;
	TestEqual(TEXT("Field of view 0 is the game's 90"), Out->ChaseFov(), 90.f);
	S->ResetGraphicsRows();
	TestTrue(TEXT("A tier puts every row back on Auto"), S->AntiAliasing == -1 && S->ShadowQuality == -1 && S->LightingQuality == -1 && S->ReflectionQuality == -1
		&& S->CloudQuality == -1 && S->WaterQuality == -1 && S->FoliageQuality == -1 && S->ViewDistanceQuality == -1 && S->MotionBlur == -1);
	for (int32 K = 0; K < UE_ARRAY_COUNT(Rows); ++K) S->*Rows[K] = Kept[K];
	S->bVSync = bVSync0;
	return true;
}

/**
 * Bean's playtest (Oct 20): Esc opens the pause menu. It is mapped to the Menu action as a fixed key, next to whatever
 * the rebindable rows hold, so a saved Input.ini can't lose it; and Tab, the Menu row's default, is still there.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIEscMenuTest, "SailingSim.UI.EscOpensMenu", UIFlags)
bool FSailingUIEscMenuTest::RunTest(const FString& Parameters)
{
	UInputMappingContext* Context = NewObject<UInputMappingContext>();
	UInputAction* Menu = NewObject<UInputAction>();
	TMap<FName, TObjectPtr<UInputAction>> Actions;
	Actions.Add(TEXT("Menu"), Menu);
	ASailboatPawn::MapFixedKeys(Context, Actions);
	const bool bEsc = Context->GetMappings().ContainsByPredicate([&](const FEnhancedActionKeyMapping& M) { return M.Action == Menu && M.Key == EKeys::Escape; });
	TestTrue(TEXT("Esc is the Menu action's"), bEsc);
	const bool bTab = GetDefault<USailingInputSettings>()->GetDefaults().ContainsByPredicate([](const FSailingKeyBinding& B) { return B.Action == TEXT("Menu") && B.Key == EKeys::Tab; });
	TestTrue(TEXT("Tab stays the Menu row's default"), bTab);
	return true;
}
/**
 * The slice build (#399): with the switch on, the menus offer only the vertical slice (Ray Hubbard and Galveston Bay;
 * the J/22, Sunfish and Catalina 22; Day Sailor, Club Racer and Coastal Cruiser), and everything is back with it off.
 * -SailingSlice=0|1 wins over the build's ini; the Shipping smoke may pass it.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUISliceBuildTest, "SailingSim.UI.SliceBuild", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FSailingUISliceBuildTest::RunTest(const FString&)
{
	const FString Saved = FCommandLine::Get();
	ON_SCOPE_EXIT { SailingArgs::SetCommandLine(Saved); };
	using Sailing::EBoatType;
	SailingArgs::SetCommandLine(Saved + TEXT(" -SailingSlice=1"));
	TestTrue(TEXT("On with -SailingSlice=1"), USailingSettings::SliceOnly());
	TestTrue(TEXT("Ray Hubbard"), SailCatalog::InSliceWorld(0));
	TestTrue(TEXT("Galveston Bay (the stretch)"), SailCatalog::InSliceWorld(1));
	TestFalse(TEXT("No Marseille"), SailCatalog::InSliceWorld(3));
	TestFalse(TEXT("No Texas coast"), SailCatalog::InSliceWorld(4));
	TestTrue(TEXT("The J/22"), SailCatalog::InSliceBoat(int32(EBoatType::J22)));
	TestTrue(TEXT("The Sunfish"), SailCatalog::InSliceBoat(int32(EBoatType::Sunfish)));
	TestTrue(TEXT("The Catalina 22 (the stretch)"), SailCatalog::InSliceBoat(int32(EBoatType::Catalina22)));
	TestTrue(TEXT("Bluebonnet, the J-Class (Bean, Nov 17 2026: docs/jclass-14)"), SailCatalog::InSliceBoat(int32(EBoatType::Bluebonnet)));
	TestTrue(TEXT("Commonwealth, the frigate (Bean, Nov 17 2026: docs/frigate-physics)"), SailCatalog::InSliceBoat(int32(EBoatType::Commonwealth)));
	for (const EBoatType T : { EBoatType::ILCA7, EBoatType::Catalina30, EBoatType::Hobie16, EBoatType::Corsair880, EBoatType::Lagoon42 })
		TestFalse(*FString::Printf(TEXT("No %hs"), Sailing::BoatTypeName(T)), SailCatalog::InSliceBoat(int32(T)));
	TestTrue(TEXT("Day Sailor"), SailCatalog::InSliceTier(TEXT("day-sailor")));
	TestTrue(TEXT("Club Racer"), SailCatalog::InSliceTier(TEXT("club-racer")));
	TestTrue(TEXT("Coastal Cruiser (the stretch)"), SailCatalog::InSliceTier(TEXT("coastal-cruiser")));
	TestFalse(TEXT("No Passage Maker"), SailCatalog::InSliceTier(TEXT("passage-maker")));
	USailingSettings* Dev = USailingSettings::Get();
	const bool bDevWas = Dev->bShowDeveloperTools;
	Dev->bShowDeveloperTools = true;
	TestFalse(TEXT("No developer tools in a slice build, whatever the ini says (#436)"), USailingSettings::DeveloperTools());
	SailingArgs::SetCommandLine(Saved + TEXT(" -SailingSlice=0"));
	TestFalse(TEXT("Off with -SailingSlice=0"), USailingSettings::SliceOnly());
	TestTrue(TEXT("... the developer tools back"), USailingSettings::DeveloperTools());
	Dev->bShowDeveloperTools = bDevWas;
	TestTrue(TEXT("... Marseille back"), SailCatalog::InSliceWorld(3));
	TestTrue(TEXT("... the Lagoon back"), SailCatalog::InSliceBoat(int32(EBoatType::Lagoon42)));
	TestTrue(TEXT("... Passage Maker back"), SailCatalog::InSliceTier(TEXT("passage-maker")));
	TestTrue(TEXT("The Shipping smoke may pass the switch"), SailingArgs::ShippingSmokeArgs(TEXT("-SailingShippingSmoke -SailingSlice=0 -SailingQuality=Low")).Contains(TEXT("-SailingSlice=0")));
	return true;
}

namespace
{
	/** The SSailChoice under W whose label reads Label (its texts include it, upper-cased). */
	TSharedPtr<SWidget> FindChoice(const TSharedRef<SWidget>& W, const FString& Label)
	{
		if (W->GetType() == TEXT("SSailChoice"))
		{
			TArray<FString> Texts;
			CollectTexts(W, Texts);
			if (Texts.Contains(Label.ToUpper())) return W;
		}
		FChildren* Children = W->GetChildren();
		for (int32 I = 0; Children && I < Children->Num(); ++I)
			if (TSharedPtr<SWidget> Found = FindChoice(Children->GetChildAt(I), Label)) return Found;
		return nullptr;
	}
}

// The PC's UI script: Right on the Mode screen's Mode choice rebuilt the screen and the focus left the choice (to the
// mode card), so a pad-only player's next key went elsewhere. A choice that rebuilds its screen keeps the focus
// (SSailFrontEnd::RebuildKeeping): the rebuilt screen's focus target is the same choice, rebuilt. Slate's navigation
// itself needs a window, so the Down that follows is checked with -SailingUIScript on the build Mac (docs in the PR).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIChoiceKeepsFocusTest, "SailingSim.UI.ChoiceKeepsFocus", UIFlags)
bool FSailingUIChoiceKeepsFocusTest::RunTest(const FString&)
{
	if (!FSlateApplication::IsInitialized()) { AddWarning(TEXT("No Slate application")); return true; }
	struct FCase { ESailScreen Screen; const TCHAR* Label; };
	for (const FCase& C : { FCase{ ESailScreen::Mode, TEXT("Mode") }, FCase{ ESailScreen::Feedback, TEXT("This is") } })
	{
		TSharedRef<SSailFrontEnd> F = SNew(SSailFrontEnd).Start(C.Screen);
		const TSharedPtr<SWidget> Before = FindChoice(F, C.Label);
		if (!TestTrue(FString::Printf(TEXT("%s: the choice is on screen"), C.Label), Before.IsValid())) continue;
		const FReply Reply = Before->OnKeyDown(FGeometry(), FKeyEvent(EKeys::Right, FModifierKeysState(), 0, false, 0, 0));
		TestTrue(FString::Printf(TEXT("%s: Right is handled"), C.Label), Reply.IsEventHandled());
		const TSharedPtr<SWidget> Target = F->FocusTarget();
		const TSharedPtr<SWidget> After = FindChoice(F, C.Label);
		TestTrue(FString::Printf(TEXT("%s: the screen was rebuilt"), C.Label), After.IsValid() && After != Before);
		TestTrue(FString::Printf(TEXT("%s: the focus stays on the choice (%s)"), C.Label, Target.IsValid() ? *Target->ToString() : TEXT("none")),
			Target.IsValid() && Target == After);
	}
	return true;
}

// Bean's call (Nov 6 2026, #497): the boat commands with no controller button stay keyboard-only for the slice, and
// the Controls screen says so on their rows (it showed a dash). The rest show their button or their fixed stick.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIKeyboardOnlyRowsTest, "SailingSim.UI.KeyboardOnlyRows", UIFlags)
bool FSailingUIKeyboardOnlyRowsTest::RunTest(const FString&)
{
	using namespace SailingBindings;
	const TArray<FSailingKeyBinding>& Defaults = GetDefault<USailingInputSettings>()->GetDefaults();
	struct FRow { const TCHAR* Action; bool bNegative; };
	for (const FRow& R : { FRow{ TEXT("Board"), false }, FRow{ TEXT("Spinnaker"), false }, FRow{ TEXT("Reef"), false }, FRow{ TEXT("Righting"), false },
		FRow{ TEXT("EngineNeutral"), false }, FRow{ TEXT("ThrottleSplit"), false }, FRow{ TEXT("ThrottleSplit"), true } })
	{
		const FKey Button = Find(Defaults, R.Action, R.bNegative, EColumn::Gamepad), Axis = FindPadAxis(Defaults, R.Action, R.bNegative);
		TestEqual(FString::Printf(TEXT("%s%s reads Keyboard only"), R.Action, R.bNegative ? TEXT(" (-)") : TEXT("")), PadColumnText(Button, Axis), FString(TEXT("Keyboard only")));
		TestTrue(FString::Printf(TEXT("%s has a key"), R.Action), Find(Defaults, R.Action, R.bNegative, EColumn::Keyboard).IsValid());
	}
	TestEqual(TEXT("A button reads its label"), PadColumnText(Find(Defaults, TEXT("DockLines"), false, EColumn::Gamepad), FKey()), PadLabel(EKeys::Gamepad_RightThumbstick));
	TestEqual(TEXT("A stick reads fixed"), PadColumnText(FKey(), FindPadAxis(Defaults, TEXT("Throttle"), false)), FString(TEXT("Left stick (fixed)")));
	return true;
}

// Slice audit finding 25: a returning Career player (progress in the save) starts on Career, not Sail (Bean, Nov 6 2026),
// even with a last session to continue (Bean, Nov 7: Career wins); a last session without Career progress starts on
// Continue; a new save and Free Sail start on Sail.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUITitleFocusTest, "SailingSim.UI.TitleFocus", UIFlags)
bool FSailingUITitleFocusTest::RunTest(const FString&)
{
	if (!FSlateApplication::IsInitialized()) { AddWarning(TEXT("No Slate application")); return true; }
	USailingSettings* S = USailingSettings::Get();
	USailSessionSave* Save = USailSessionSave::Get();
	FSailSave::FProgress& Progress = SailSaveStore::Progress();
	const FSailSave::FProgress WasProgress = Progress;
	const bool bWasFree = S->bFreeSail, bHadLast = Save->bHasLast;
	ON_SCOPE_EXIT { S->bFreeSail = bWasFree; Save->bHasLast = bHadLast; Progress = WasProgress; };
	auto Focused = [this]()
	{
		TSharedRef<SSailFrontEnd> F = SNew(SSailFrontEnd).Start(ESailScreen::Title);
		TArray<FString> Texts;
		if (const TSharedPtr<SWidget> Target = F->FocusTarget()) CollectTexts(Target.ToSharedRef(), Texts);
		return FString::Join(Texts, TEXT(" ")).ToUpper();
	};
	Save->bHasLast = false;
	S->bFreeSail = false;
	Progress = FSailSave::FProgress();
	FString Got = Focused();
	TestTrue(FString::Printf(TEXT("A new save starts on Sail (%s)"), *Got), Got.StartsWith(TEXT("SAIL")));
	FSailSave::FLessonRecord Lesson;
	Lesson.Id = TEXT("leave-the-dock");
	Progress.Lessons.Add(Lesson);
	Got = Focused();
	TestTrue(FString::Printf(TEXT("A returning Career player starts on Career (%s)"), *Got), Got.StartsWith(TEXT("CAREER")));
	S->bFreeSail = true;
	Got = Focused();
	TestTrue(FString::Printf(TEXT("Free Sail starts on Sail (%s)"), *Got), Got.StartsWith(TEXT("SAIL")));
	Save->bHasLast = true;
	S->bFreeSail = false;
	Got = Focused();
	TestTrue(FString::Printf(TEXT("A last session with Career progress starts on Career (%s)"), *Got), Got.StartsWith(TEXT("CAREER")));
	Progress = FSailSave::FProgress();
	Got = Focused();
	TestTrue(FString::Printf(TEXT("A last session without Career progress starts on Continue (%s)"), *Got), Got.StartsWith(TEXT("CONTINUE")));
	return true;
}

// Bean, Nov 7 2026: Continue overwrites the difficulty. Continue casts off with the last session as it was saved, and
// applying a session (USailSessionSubsystem::ApplyToSettings, StartSession's path) writes its Easy or Realistic over the
// Settings difficulty. Behaviour locked here, not changed.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIContinueKeepsItsDifficultyTest, "SailingSim.UI.ContinueKeepsItsDifficulty", UIFlags)
bool FSailingUIContinueKeepsItsDifficultyTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	const int32 World = S->World, Spot = S->LaunchSpot, Traffic = S->TrafficLevel, Boat = S->BoatType;
	const ESailingWeather Weather = S->WeatherPreset;
	const float Hour = S->StartHour;
	const ESailingDifficulty Difficulty = S->Difficulty;
	const bool bLearning = S->bLearningMode, bFree = S->bFreeSail;
	ON_SCOPE_EXIT
	{
		S->World = World; S->LaunchSpot = Spot; S->TrafficLevel = Traffic; S->BoatType = Boat; S->WeatherPreset = Weather;
		S->StartHour = Hour; S->Difficulty = Difficulty; S->bLearningMode = bLearning; S->bFreeSail = bFree;
		S->Save();
	};
	FSailSessionConfig Last = USailSessionSubsystem::MakeDefault();
	Last.bEasy = false;
	S->Difficulty = ESailingDifficulty::Easy;
	USailSessionSubsystem::ApplyToSettings(Last);
	TestTrue(TEXT("A Realistic last session over an Easy setting sails Realistic"), S->Difficulty == ESailingDifficulty::Realistic);
	Last.bEasy = true;
	S->Difficulty = ESailingDifficulty::Realistic;
	USailSessionSubsystem::ApplyToSettings(Last);
	TestTrue(TEXT("An Easy last session over a Realistic setting sails Easy"), S->Difficulty == ESailingDifficulty::Easy);
	return true;
}

// Bean, Nov 7 2026: a Career lesson over a Free Sail choice sails as Career (medals count) without turning Free Sail off;
// back on the title the player's choice is the mode again.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUILessonKeepsFreeSailTest, "SailingSim.UI.LessonKeepsFreeSail", UIFlags)
bool FSailingUILessonKeepsFreeSailTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	const int32 World = S->World, Spot = S->LaunchSpot, Traffic = S->TrafficLevel, Boat = S->BoatType, Run = S->RunFreeSail;
	const ESailingWeather Weather = S->WeatherPreset;
	const float Hour = S->StartHour;
	const ESailingDifficulty Difficulty = S->Difficulty;
	const bool bLearning = S->bLearningMode, bFree = S->bFreeSail;
	ON_SCOPE_EXIT
	{
		S->World = World; S->LaunchSpot = Spot; S->TrafficLevel = Traffic; S->BoatType = Boat; S->WeatherPreset = Weather;
		S->StartHour = Hour; S->Difficulty = Difficulty; S->bLearningMode = bLearning; S->bFreeSail = bFree; S->RunFreeSail = Run;
		S->Save();
	};
	if (USailingSettings::FreeSailArg() >= 0) { AddWarning(TEXT("-SailingFreeSail on the command line decides the mode")); return true; }
	S->bFreeSail = true;
	S->RunFreeSail = -1;
	const FSailSessionConfig Lesson = USailSessionSubsystem::MakeLesson(TEXT("ray-hubbard"), TEXT("J22"), 1);
	TestFalse(TEXT("The lesson's own config is Career"), Lesson.bFreeSail);
	USailSessionSubsystem::ApplyToSettings(Lesson);
	TestTrue(TEXT("The player's Free Sail choice is kept"), S->bFreeSail);
	TestFalse(TEXT("The lesson sails as Career"), S->IsFreeSail());
	TestTrue(TEXT("The choice reads Free Sail"), S->IsFreeSailChoice());
	S->RunFreeSail = -1;   // the title clears the run's mode
	TestTrue(TEXT("Back on the title the mode is Free Sail"), S->IsFreeSail());
	// And a new session from the menus starts in the player's mode.
	TestTrue(TEXT("A new session is Free Sail"), USailSessionSubsystem::MakeDefault().bFreeSail);
	return true;
}

// #404, the first hour on a controller: every command the slice's lessons name in their text ({key:Command.direction}
// in Content/Learning and the first job's script) has a controller button or axis by default, in that direction, and so
// do the steering and mainsheet the first job asks for without naming them. A pad-only player is never told to press a
// key the pad doesn't have. (The Sunfish's board has no button: keyboard only for the slice, #497; no lesson asks for it.)
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIPadCoversLessonKeysTest, "SailingSim.UI.PadCoversLessonKeys", UIFlags)
bool FSailingUIPadCoversLessonKeysTest::RunTest(const FString&)
{
	using namespace SailingBindings;
	const TArray<FSailingKeyBinding>& Defaults = GetDefault<USailingInputSettings>()->GetDefaults();
	TSet<FString> Tokens = { TEXT("Tiller.ease"), TEXT("Tiller.trim"), TEXT("MainSheet.ease"), TEXT("MainSheet.trim") };
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *(FPaths::ProjectContentDir() / TEXT("Learning/*.json")), true, false);
	for (FString& F : Files) F = FPaths::ProjectContentDir() / TEXT("Learning") / F;
	Files.Add(FPaths::ProjectContentDir() / TEXT("FirstSail/first-sail.json"));
	for (const FString& Path : Files)
	{
		FString Text;
		if (!TestTrue(FString::Printf(TEXT("%s reads"), *FPaths::GetCleanFilename(Path)), FFileHelper::LoadFileToString(Text, *Path))) continue;
		int32 From = 0;
		while (true)
		{
			const int32 Start = Text.Find(TEXT("{key:"), ESearchCase::CaseSensitive, ESearchDir::FromStart, From);
			if (Start == INDEX_NONE) break;
			const int32 End = Text.Find(TEXT("}"), ESearchCase::CaseSensitive, ESearchDir::FromStart, Start);
			if (End == INDEX_NONE) break;
			const FString Token = Text.Mid(Start + 5, End - Start - 5);
			if (!Token.StartsWith(TEXT("Action"))) Tokens.Add(Token);   // {key:Action...} is the README's example
			From = End + 1;
		}
	}
	TestTrue(FString::Printf(TEXT("The lessons name commands (%d with the first job's)"), Tokens.Num()), Tokens.Num() > 4);
	for (const FString& Token : Tokens)
	{
		FString Action = Token, Dir;
		Token.Split(TEXT("."), &Action, &Dir);
		const bool bNegative = Dir == TEXT("trim");   // as FLearningContent::ResolveKeys reads a direction
		const FName Name(*Action);
		const bool bPad = Find(Defaults, Name, bNegative, EColumn::Gamepad).IsValid() || FindPadAxis(Defaults, Name, bNegative).IsValid();
		TestTrue(FString::Printf(TEXT("{key:%s} has a controller binding"), *Token), bPad);
	}
	// Bean's pick (Nov 6): the throttle is on the left stick both ways; the board stays on the keyboard.
	TestEqual(TEXT("Throttle ahead on the left stick"), FindPadAxis(Defaults, TEXT("Throttle"), false), EKeys::Gamepad_LeftY);
	TestEqual(TEXT("Throttle astern on the left stick"), FindPadAxis(Defaults, TEXT("Throttle"), true), EKeys::Gamepad_LeftY);
	TestEqual(TEXT("Controls screen: throttle row reads Left stick"), Label(TEXT("Throttle"), false, true), FString(TEXT("Left stick")));
	return true;
}

// No two default controller bindings share a button or axis in the same layer (SailingBindings::SameLayer), except photo
// mode's pad toggle, a half-second hold of the controls card's button, and the dock lines, a hold of the right stick's
// click whose tap changes the view, and photo mode's tab reset, a hold of the click that goes back to the boat
// (ASailboatPawn::BuildContext). A saved key list from
// before the stick throttle gets it, and the throttle mapping carries its dead zone.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIPadNoCollisionsTest, "SailingSim.UI.PadNoCollisions", UIFlags)
bool FSailingUIPadNoCollisionsTest::RunTest(const FString&)
{
	using namespace SailingBindings;
	const TArray<FSailingKeyBinding>& Defaults = GetDefault<USailingInputSettings>()->GetDefaults();
	int32 Pad = 0;
	for (int32 I = 0; I < Defaults.Num(); ++I)
	{
		const FSailingKeyBinding& A = Defaults[I];
		if (!A.Key.IsGamepadKey() || !IsRowAction(A.Action)) continue;
		++Pad;
		for (int32 J = I + 1; J < Defaults.Num(); ++J)
		{
			const FSailingKeyBinding& B = Defaults[J];
			if (B.Key != A.Key || !IsRowAction(B.Action) || !SameLayer(A.Action, B.Action)) continue;
			if (A.Action == B.Action && (A.Scale < 0.f) == (B.Scale < 0.f)) continue;
			auto Pair = [&A, &B](const TCHAR* Hold, const TCHAR* Tap) { return (A.Action == Hold && B.Action == Tap) || (A.Action == Tap && B.Action == Hold); };
			const bool bHoldTap = Pair(TEXT("Photo"), TEXT("ControlsCard")) || Pair(TEXT("DockLines"), TEXT("ChangeView"))
				|| Pair(TEXT("PhotoResetTab"), TEXT("PhotoToBoat"));
			if (bHoldTap) continue;
			AddError(FString::Printf(TEXT("%s is on both %s%s and %s%s"), *PadLabel(A.Key), *A.Action.ToString(), A.Scale < 0.f ? TEXT(" (-)") : TEXT(""),
				*B.Action.ToString(), B.Scale < 0.f ? TEXT(" (-)") : TEXT("")));
		}
	}
	TestTrue(FString::Printf(TEXT("Checked %d default pad bindings"), Pad), Pad > 20);

	// An older saved list (no stick throttle) gains it; one whose left stick Y someone gave to another command doesn't.
	USailingInputSettings* Settings = NewObject<USailingInputSettings>();
	auto HasStick = [](const TArray<FSailingKeyBinding>& L) { return L.ContainsByPredicate([](const FSailingKeyBinding& B) { return B.Action == TEXT("Throttle") && B.Key == EKeys::Gamepad_LeftY; }); };
	Settings->Bindings = Settings->GetDefaults().FilterByPredicate([](const FSailingKeyBinding& B) { return !(B.Action == TEXT("Throttle") && B.Key == EKeys::Gamepad_LeftY); });
	Settings->AddMissingActions();
	TestTrue(TEXT("A saved list gets the stick throttle"), HasStick(Settings->Bindings));
	const int32 Before = Settings->Bindings.Num();
	Settings->AddMissingActions();
	TestEqual(TEXT("Added once"), Settings->Bindings.Num(), Before);
	Settings->Bindings = Settings->GetDefaults().FilterByPredicate([](const FSailingKeyBinding& B) { return !(B.Action == TEXT("Throttle") && B.Key == EKeys::Gamepad_LeftY); });
	FSailingKeyBinding Taken;
	Taken.Action = TEXT("Hike");
	Taken.Key = EKeys::Gamepad_LeftY;
	Settings->Bindings.Add(Taken);
	Settings->AddMissingActions();
	TestFalse(TEXT("Not over another command's stick"), HasStick(Settings->Bindings));

	// The mapping: the throttle's stick has the dead zone, the tiller's doesn't.
	TMap<FName, TObjectPtr<UInputAction>> Actions;
	ASailboatPawn::MakeActions(GetTransientPackage(), Defaults, Actions);
	UInputMappingContext* Context = ASailboatPawn::BuildContext(GetTransientPackage(), TEXT("IMC_PadTest"), Defaults, Actions, false);
	bool bThrottle = false, bTillerClean = true;
	for (const FEnhancedActionKeyMapping& M : Context->GetMappings())
	{
		const UInputModifierDeadZone* Dead = nullptr;
		for (const TObjectPtr<UInputModifier>& Mod : M.Modifiers) if (const UInputModifierDeadZone* D = Cast<UInputModifierDeadZone>(Mod)) Dead = D;
		if (M.Key == EKeys::Gamepad_LeftY && M.Action == Actions.FindRef(TEXT("Throttle")))
			bThrottle = Dead && FMath::IsNearlyEqual(Dead->LowerThreshold, ASailboatPawn::ThrottleStickDeadZone);
		if (M.Key == EKeys::Gamepad_LeftX && M.Action == Actions.FindRef(TEXT("Tiller"))) bTillerClean = Dead == nullptr;
	}
	TestTrue(TEXT("Throttle stick has a 0.5 dead zone"), bThrottle);
	TestTrue(TEXT("The tiller has none of it"), bTillerClean);
	return true;
}

// #490: a session's loading screen shows its own boat, or no boat, never another boat's. Every slice boat on every slice
// world; on the lake each slice boat has its own still.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUILoadingStillTest, "SailingSim.UI.LoadingStill", UIFlags)
bool FSailingUILoadingStillTest::RunTest(const FString&)
{
	using Sailing::EBoatType;
	for (const SailCatalog::FWorld& W : SailCatalog::Worlds())
	{
		TestEqual(FString::Printf(TEXT("%s: a boat for every loading still"), *W.File), W.LoadingBoats.Num(), W.LoadingTextures.Num());
		TestEqual(FString::Printf(TEXT("%s: a look for every loading still"), *W.File), W.LoadingLooks.Num(), W.LoadingTextures.Num());
	}
	for (const int32 Index : { 0, 1 })
	{
		const SailCatalog::FWorld& W = SailCatalog::World(Index);
		for (const EBoatType Type : { EBoatType::J22, EBoatType::Sunfish, EBoatType::Catalina22 })
		{
			const TArray<FString> Stills = SailCatalog::LoadingStills(W, int32(Type));
			for (const FString& Still : Stills)
			{
				const int32 At = W.LoadingTextures.IndexOfByKey(Still);
				const int32 Shows = W.LoadingBoats.IsValidIndex(At) ? W.LoadingBoats[At] : -2;
				TestTrue(FString::Printf(TEXT("%s, boat %d: %s shows that boat or none (%d)"), *W.File, int32(Type), *Still, Shows),
					Shows == int32(Type) || Shows == SailCatalog::FWorld::NoBoat);
			}
			if (Index == 0)
			{
				TestTrue(FString::Printf(TEXT("Ray Hubbard, boat %d: a still of its own"), int32(Type)),
					Stills.Num() > 0 && W.LoadingBoats[W.LoadingTextures.IndexOfByKey(Stills[0])] == int32(Type));
			}
		}
	}
	// A boat with no still and no neutral still in the world: nothing (a plain screen), not another boat.
	SailCatalog::FWorld Bare;
	using SailCatalog::ELoadingLook;
	Bare.LoadingTextures = { TEXT("/Game/UI/A"), TEXT("/Game/UI/B") };
	Bare.LoadingBoats = { int32(EBoatType::J22), int32(EBoatType::Hobie16) };
	Bare.LoadingLooks = { ELoadingLook::Day, ELoadingLook::Day };
	TestEqual(TEXT("no own or neutral still: none"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)).Num(), 0);
	Bare.LoadingTextures.Add(TEXT("/Game/UI/C"));
	Bare.LoadingBoats.Add(SailCatalog::FWorld::NoBoat);
	Bare.LoadingLooks.Add(ELoadingLook::Day);
	TestTrue(TEXT("a neutral still when there is no own one"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)) == TArray<FString>({ TEXT("/Game/UI/C") }));
	TestTrue(TEXT("the own still before the neutral one"), SailCatalog::LoadingStills(Bare, int32(EBoatType::J22)) == TArray<FString>({ TEXT("/Game/UI/A") }));
	// An untagged still (past LoadingBoats) could show any boat: never shown, not even as a neutral one.
	Bare.LoadingTextures.Add(TEXT("/Game/UI/D"));
	TestFalse(TEXT("an untagged still is left out"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)).Contains(TEXT("/Game/UI/D")));
	// A still of another weather is never shown, not even as a neutral one; a still with a boat but no look neither.
	Bare.LoadingBoats.Add(SailCatalog::FWorld::NoBoat);
	Bare.LoadingLooks.Add(ELoadingLook::Night);
	TestTrue(TEXT("a night session: the night still"), SailCatalog::LoadingStills(Bare, int32(EBoatType::J22), ELoadingLook::Night) == TArray<FString>({ TEXT("/Game/UI/D") }));
	TestFalse(TEXT("a day session: never the night still"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)).Contains(TEXT("/Game/UI/D")));
	TestEqual(TEXT("a grey session with no grey still: none"), SailCatalog::LoadingStills(Bare, int32(EBoatType::J22), ELoadingLook::Grey).Num(), 0);
	Bare.LoadingTextures.Add(TEXT("/Game/UI/E"));
	Bare.LoadingBoats.Add(SailCatalog::FWorld::NoBoat);
	TestFalse(TEXT("a still with no look is left out"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)).Contains(TEXT("/Game/UI/E")));
	// Decided, not an accident: the Catalina 22 on Galveston Bay (no still of her there, none without a boat) loads on the
	// plain screen.
	TestEqual(TEXT("Galveston, Catalina 22: the plain screen"), SailCatalog::LoadingStills(SailCatalog::World(1), int32(EBoatType::Catalina22)).Num(), 0);
	// #595: the lake's storm still (2, the J/22 under the shelf cloud) only in a stormy session.
	TestFalse(TEXT("Lake, J/22, fair: no storm still"), SailCatalog::LoadingStills(SailCatalog::World(0), int32(EBoatType::J22)).Contains(TEXT("/Game/UI/T_Load_RayHubbard_2.T_Load_RayHubbard_2")));
	TestTrue(TEXT("Lake, J/22, stormy: the storm still"), SailCatalog::LoadingStills(SailCatalog::World(0), int32(EBoatType::J22), ELoadingLook::Storm) == TArray<FString>({ TEXT("/Game/UI/T_Load_RayHubbard_2.T_Load_RayHubbard_2") }));
	// Nov 10 audit 1-2: no still of another weather. Each slice boat on the lake has a still of her own in every look
	// (docs/loading-stills); the Catalina 30's still is an evening one, so at noon she loads plain.
	auto Lake = [](EBoatType Type, ELoadingLook Look) { return SailCatalog::LoadingStills(SailCatalog::World(0), int32(Type), Look); };
	auto Load = [](int32 N) { return FString::Printf(TEXT("/Game/UI/T_Load_RayHubbard_%d.T_Load_RayHubbard_%d"), N, N); };
	TestTrue(TEXT("Lake, J/22, low sun"), Lake(EBoatType::J22, ELoadingLook::LowSun) == TArray<FString>({ Load(5) }));
	TestTrue(TEXT("Lake, Sunfish, low sun"), Lake(EBoatType::Sunfish, ELoadingLook::LowSun) == TArray<FString>({ Load(6) }));
	TestTrue(TEXT("Lake, J/22, grey"), Lake(EBoatType::J22, ELoadingLook::Grey) == TArray<FString>({ Load(7) }));
	TestTrue(TEXT("Lake, Sunfish, grey"), Lake(EBoatType::Sunfish, ELoadingLook::Grey) == TArray<FString>({ Load(8) }));
	TestTrue(TEXT("Lake, Sunfish, stormy: her storm still, not the J/22's"), Lake(EBoatType::Sunfish, ELoadingLook::Storm) == TArray<FString>({ Load(9) }));
	TestTrue(TEXT("Lake, J/22, night"), Lake(EBoatType::J22, ELoadingLook::Night) == TArray<FString>({ Load(10) }));
	TestTrue(TEXT("Lake, Sunfish, night"), Lake(EBoatType::Sunfish, ELoadingLook::Night) == TArray<FString>({ Load(11) }));
	TestTrue(TEXT("Lake, Sunfish, day: still only her day still"), Lake(EBoatType::Sunfish, ELoadingLook::Day) == TArray<FString>({ Load(3) }));
	TestTrue(TEXT("Lake, Catalina 30, low sun: her evening still"), Lake(EBoatType::Catalina30, ELoadingLook::LowSun) == TArray<FString>({ Load(0) }));
	TestEqual(TEXT("Lake, Catalina 30, noon: not the evening still"), Lake(EBoatType::Catalina30, ELoadingLook::Day).Num(), 0);
	TestEqual(TEXT("Lake, Catalina 22, night: the plain screen"), Lake(EBoatType::Catalina22, ELoadingLook::Night).Num(), 0);
	// A session's look from the presets: the lesson day (the whole first hour) is a day still, the July storm a storm, the
	// norther grey, the glassy morning (07:30 in August) a low sun; the lesson day at 21:00 is night, at 19:15 in April (sun about 8 deg) low sun.
	auto LookOf = [](const TCHAR* PresetId, int32 World)
	{
		FSailConditions K;
		for (const FSailPreset& P : USailSessionSubsystem::Presets()) if (P.Id == FName(PresetId)) K = P.Values;
		return SailCatalog::LoadingLook(K, World);
	};
	TestEqual(TEXT("Lesson day: Day"), FString(SailCatalog::LoadingLookName(LookOf(TEXT("Lesson"), 0))), FString(TEXT("Day")));
	TestEqual(TEXT("July storm: Storm"), FString(SailCatalog::LoadingLookName(LookOf(TEXT("July"), 0))), FString(TEXT("Storm")));
	TestEqual(TEXT("Blue norther: Grey"), FString(SailCatalog::LoadingLookName(LookOf(TEXT("Norther"), 0))), FString(TEXT("Grey")));
	TestEqual(TEXT("Glassy morning: LowSun"), FString(SailCatalog::LoadingLookName(LookOf(TEXT("Glassy"), 0))), FString(TEXT("LowSun")));
	TestEqual(TEXT("Bay sea breeze: Day"), FString(SailCatalog::LoadingLookName(LookOf(TEXT("SeaBreeze"), 1))), FString(TEXT("Day")));
	{
		FSailConditions K;
		for (const FSailPreset& P : USailSessionSubsystem::Presets()) if (P.Id == FName(TEXT("Lesson"))) K = P.Values;
		K.LocalHour = 21.f;
		TestEqual(TEXT("Lesson day at 21:00: Night"), FString(SailCatalog::LoadingLookName(SailCatalog::LoadingLook(K, 0))), FString(TEXT("Night")));
		K.Sky = ESailSky::Storms;
		TestEqual(TEXT("... a storm at 21:00 too (not the noon shelf)"), FString(SailCatalog::LoadingLookName(SailCatalog::LoadingLook(K, 0))), FString(TEXT("Night")));
		K.Sky = ESailSky::Fair;
		K.LocalHour = 19.25f;
		TestEqual(TEXT("Lesson day at 19:15: LowSun"), FString(SailCatalog::LoadingLookName(SailCatalog::LoadingLook(K, 0))), FString(TEXT("LowSun")));
		K.Sky = ESailSky::Fog;
		K.LocalHour = 10.f;
		TestEqual(TEXT("Fog (it runs as overcast): Grey"), FString(SailCatalog::LoadingLookName(SailCatalog::LoadingLook(K, 0))), FString(TEXT("Grey")));
		K.Sky = ESailSky::Rain;
		TestEqual(TEXT("Rain: Grey"), FString(SailCatalog::LoadingLookName(SailCatalog::LoadingLook(K, 0))), FString(TEXT("Grey")));
	}
	// The loading screen itself, for a Sunfish session on the lake: the Sunfish still (no world needed: the session is given).
	if (FSlateApplication::IsInitialized())
	{
		FSailSessionConfig C = USailSessionSubsystem::MakeDefault();
		C.World = 0;
		C.Boat = int32(EBoatType::Sunfish);
		TSharedRef<SSailLoading> Loading = SNew(SSailLoading).Config(C);
		const UObject* Still = Loading->ShownStill();
		TestTrue(FString::Printf(TEXT("A Sunfish session on the lake loads under T_Load_RayHubbard_3 (%s)"), Still ? *Still->GetName() : TEXT("none")),
			Still && Still->GetName() == TEXT("T_Load_RayHubbard_3"));
		C.World = 1;
		C.Boat = int32(EBoatType::Catalina22);
		TSharedRef<SSailLoading> Plain = SNew(SSailLoading).Config(C);
		TestTrue(TEXT("A Catalina 22 session on the bay: the plain screen"), Plain->ShownStill() == nullptr);
		// #595: a J/22 lesson on a fair day never loads under the storm still (twenty tries), and opens on its own tip; the
		// first job opens on tip 1; a stormy session gets the storm still and the thunderstorm tip.
		C.World = 0;
		C.Boat = int32(EBoatType::J22);
		C.Mode = ESailMode::Drill;
		C.DrillIndex = int32(ESailingDrill::HeaveTo) - 1;
		C.Conditions.Sky = ESailSky::Fair;
		C.Conditions.PresetId = TEXT("Lesson");
		bool bStormStill = false;
		for (int32 I = 0; I < 20; ++I)
		{
			TSharedRef<SSailLoading> Fair = SNew(SSailLoading).Config(C);
			bStormStill |= Fair->ShownStill() && Fair->ShownStill()->GetName() == TEXT("T_Load_RayHubbard_2");
			if (I == 0) TestEqual(TEXT("Heave to, fair: its own tip first"), FString(SSailLoading::TipHeading(Fair->ShownTip())), FString(TEXT("Heaving to")));
		}
		TestFalse(TEXT("A fair day: never the storm still"), bStormStill);
		FSailSessionConfig Job = C;
		Job.Mode = ESailMode::Free;
		Job.SceneId = TEXT("first-job");
		TestEqual(TEXT("The first job: tip 1"), SSailLoading::FirstTip(Job), 0);
		TestEqual(TEXT("... Points of sail"), FString(SSailLoading::TipHeading(SSailLoading::FirstTip(Job))), FString(TEXT("Points of sail")));
		FSailSessionConfig Dock = C;
		Dock.DrillIndex = int32(ESailingDrill::ReturnAndDock) - 1;
		TestEqual(TEXT("Return and dock: Docking"), FString(SSailLoading::TipHeading(SSailLoading::FirstTip(Dock))), FString(TEXT("Docking")));
		FSailSessionConfig Leave = C;
		Leave.DrillIndex = int32(ESailingDrill::LeaveTheDock) - 1;
		TestEqual(TEXT("Leave the dock: Leaving a slip"), FString(SSailLoading::TipHeading(SSailLoading::FirstTip(Leave))), FString(TEXT("Leaving a slip")));
		FSailSessionConfig Free = C;
		Free.Mode = ESailMode::Free;
		TestEqual(TEXT("A free sail, fair: no set first tip"), SSailLoading::FirstTip(Free), int32(INDEX_NONE));
		bool bStormTip = false;
		for (int32 I = 0; I < 30; ++I)
		{
			TSharedRef<SSailLoading> Screen = SNew(SSailLoading).Config(Free);
			bStormTip |= FString(SSailLoading::TipHeading(Screen->ShownTip())) == TEXT("Thunderstorms on Texas lakes");
		}
		TestFalse(TEXT("... and never the thunderstorm tip on a fair day (thirty screens)"), bStormTip);
		FSailSessionConfig Preset = Free;
		Preset.Conditions.PresetId = TEXT("Thunderstorm");
		TestFalse(TEXT("Stormy is the sky's, not a preset's name"), SSailLoading::IsStormy(Preset));
		FSailSessionConfig Storm = C;
		Storm.Mode = ESailMode::Free;
		Storm.Conditions.Sky = ESailSky::Storms;
		TSharedRef<SSailLoading> Stormy = SNew(SSailLoading).Config(Storm);
		TestTrue(TEXT("A stormy session: the storm still"), Stormy->ShownStill() && Stormy->ShownStill()->GetName() == TEXT("T_Load_RayHubbard_2"));
		TestEqual(TEXT("... and the thunderstorm tip"), FString(SSailLoading::TipHeading(Stormy->ShownTip())), FString(TEXT("Thunderstorms on Texas lakes")));
	}
	else AddWarning(TEXT("No Slate application: the loading screen itself is not built"));
	return true;
}

// The sail trim panel's plain line (Bean, Nov 15 2026, docs/trim-panel/) says what the coach's tips say, the most urgent
// first (the dock, irons, heel past the boat's limit, the no-go zone, then the sails), and whatever it calls shows on at
// least one of the panel's yarns. #712's first Mac stills said "Sailing well" beside "Too close to the wind" and "Jib is
// stalled": the sweep below holds the headline to SailingCollectBoatTips on every pattern of two strips.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUITrimVerdictTest, "SailingSim.UI.TrimVerdict", UIFlags)
bool FSailingUITrimVerdictTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig J22;
	const FEasyAssists Realistic;
	const FEasyAssists Easy = []() { FEasyAssists E; E.bEnabled = true; return E; }();
	// A boat sailing well close-hauled on starboard: every strip drawing, well above its luff angle and under its stall.
	auto Trimmed = [](int32 NumJib, double TwaDeg = 42.0)
	{
		FBoatTelemetry T;
		T.TrueWindAngle = FMath::DegreesToRadians(TwaDeg);
		T.ApparentWindAngle = FMath::DegreesToRadians(TwaDeg * 0.66);
		T.Heel = FMath::DegreesToRadians(8.0);
		T.NumJibStrips = NumJib;
		T.NumMainStrips = 4;
		for (int32 I = 0; I < kMaxSailStrips; ++I)
		{
			for (FSailStripState* St : { &T.JibStrips[I], &T.MainStrips[I] })
			{
				St->Flow = ESailFlow::Attached;
				St->AlphaN = FMath::DegreesToRadians(12.0);
				St->LuffAlpha = FMath::DegreesToRadians(3.0);
				St->StallAlpha = FMath::DegreesToRadians(20.0);
			}
		}
		return T;
	};
	auto Verdict = [&](const FBoatTelemetry& T, bool bTied = false, const FEasyAssists* A = nullptr) { return SSailHud::TrimVerdict(T, J22, A ? *A : Realistic, bTied); };
	auto Head = [&](const FBoatTelemetry& T, bool bTied = false) { return FString(Verdict(T, bTied).Head); };

	FBoatTelemetry T = Trimmed(5);
	TestEqual(TEXT("Everything streaming: sailing well"), Head(T), FString(TEXT("Sailing well")));
	TestTrue(TEXT("... in the good colour"), Verdict(T).bGood);
	TestEqual(TEXT("At the dock: tied up"), Head(T, true), FString(TEXT("Tied up")));
	TestTrue(TEXT("... in neither colour"), Verdict(T, true).bNeutral);

	// The Mac's three stills.
	T = Trimmed(5, 28.0);
	TestEqual(TEXT("Pinching at 28 deg: too close to the wind"), Head(T), FString(TEXT("Too close to the wind")));
	TestTrue(TEXT("... with a what-to-do line"), FString(Verdict(T).Say).Contains(TEXT("Bear away")));
	TestTrue(TEXT("... but not in the tips' start hold"), SSailHud::TrimVerdict(T, J22, Realistic, false, true).bGood);
	T = Trimmed(5);
	T.JibStrips[0].Flow = T.JibStrips[1].Flow = ESailFlow::Stalled;
	TestEqual(TEXT("Two low jib strips stalled: jib too tight"), Head(T), FString(TEXT("Jib too tight")));
	T = Trimmed(0);
	T.MainStrips[0].Flow = T.MainStrips[1].Flow = ESailFlow::Stalled;
	TestEqual(TEXT("Sunfish with her main stalled: sail too tight"), Head(T), FString(TEXT("Sail too tight")));

	T = Trimmed(5, 50.0);
	TestEqual(TEXT("Easy mode warns before the no-go zone"), FString(Verdict(T, false, &Easy).Head), FString(TEXT("Near the no-go zone")));
	T = Trimmed(5, 95.0);
	for (int32 I = 0; I < 5; ++I) T.JibStrips[I].Flow = ESailFlow::Luffing;
	TestEqual(TEXT("Jib luffing on a reach"), Head(T), FString(TEXT("Jib luffing")));
	TestTrue(TEXT("... sheet the jib in"), FString(Verdict(T).Say).Contains(TEXT("Sheet the jib in")));
	T.Heel = FMath::DegreesToRadians(J22.TrimHeelLimitDeg + 4.0);
	TestEqual(TEXT("Heel past the limit wins over the sails"), Head(T), FString(TEXT("Heeling too much")));
	T.bInIrons = true;
	TestEqual(TEXT("In irons wins over the heel"), Head(T), FString(TEXT("In irons")));
	T = Trimmed(5);
	T.JibStrips[4].Flow = ESailFlow::Luffing;
	TestEqual(TEXT("One luffing strip is not a call (the tips need two)"), Head(T), FString(TEXT("Sailing well")));
	T = Trimmed(5);
	for (int32 I = 0; I < 5; ++I) T.JibStrips[I].AlphaN = T.JibStrips[I].LuffAlpha + FMath::DegreesToRadians(1.0);
	TestTrue(TEXT("Inside yarns lifting short of a luff: still well"), Verdict(T).bGood);
	TestTrue(TEXT("... on the edge, not 'streaming'"), FString(Verdict(T).Say).Contains(TEXT("edge")));
	// #712's second Mac stills: the bottom leech ribbon curled under "Yarns streaming".
	T = Trimmed(5);
	T.MainStrips[0].Flow = ESailFlow::Stalled;
	TestTrue(TEXT("One main strip stalled: still well (the tips need two)"), Verdict(T).bGood);
	TestTrue(TEXT("... but the line names the curling ribbon"), FString(Verdict(T).Say).Contains(TEXT("leech ribbon is curling")));
	T = Trimmed(5);
	T.JibStrips[0].Flow = ESailFlow::Stalled;
	TestTrue(TEXT("One jib strip stalled: the line names the drooping yarn"), FString(Verdict(T).Say).Contains(TEXT("outside yarn is drooping")));

	// A cat rig's tips say nothing about a jib.
	{
		TArray<TPair<FString, int32>> Tips;
		SailingCollectBoatTips(Trimmed(0, 45.0), 1.0, FBoatControls(), Realistic, false, false, Tips);
		TestFalse(TEXT("No jib: no jib tip"), Tips.ContainsByPredicate([](const TPair<FString, int32>& P) { return P.Key.Contains(TEXT("Jib")); }));
		FBoatTelemetry Cat = Trimmed(0, 45.0);
		Cat.MainStrips[0].Flow = Cat.MainStrips[1].Flow = ESailFlow::Stalled;
		Tips.Reset();
		SailingCollectBoatTips(Cat, 1.0, FBoatControls(), Realistic, false, false, Tips);
		TestTrue(TEXT("No jib: her one sail is 'the sail', as on the panel"), Tips.ContainsByPredicate([](const TPair<FString, int32>& P) { return P.Key.StartsWith(TEXT("Sail is stalled")); }));
		TestFalse(TEXT("... never 'Main'"), Tips.ContainsByPredicate([](const TPair<FString, int32>& P) { return P.Key.Contains(TEXT("Main")); }));
		TestEqual(TEXT("... and the panel says the same"), FString(Verdict(Cat).Head), FString(TEXT("Sail too tight")));
	}

	// The headline's hold, the tip card's rule: a warning shows at once and stays TipHoldSeconds; all-clear waits for it.
	{
		SSailHud::FTrimVerdictHold Hold;
		FBoatTelemetry Well = Trimmed(5), Tight = Trimmed(5), Curl = Trimmed(5);
		Tight.MainStrips[0].Flow = Tight.MainStrips[1].Flow = ESailFlow::Stalled;
		Curl.MainStrips[0].Flow = ESailFlow::Stalled;
		auto Shown = [&](const FBoatTelemetry& S, double Now) { return FString(SSailHud::HoldTrimVerdict(Hold, Verdict(S), Now).Head); };
		TestEqual(TEXT("Hold: first call shows"), Shown(Well, 0.0), FString(TEXT("Sailing well")));
		TestEqual(TEXT("Hold: a warning shows at once"), Shown(Tight, 0.1), FString(TEXT("Main too tight")));
		TestEqual(TEXT("Hold: the warning stays while one strip flickers"), Shown(Curl, 3.0), FString(TEXT("Main too tight")));
		TestEqual(TEXT("Hold: ... and when it comes back"), Shown(Tight, 4.0), FString(TEXT("Main too tight")));
		TestEqual(TEXT("Hold: all clear after the tip card's hold"), Shown(Well, 0.1 + SSailHud::TipHoldSeconds + 0.01), FString(TEXT("Sailing well")));
		TestEqual(TEXT("Hold: the dock shows at once"), FString(SSailHud::HoldTrimVerdict(Hold, Verdict(Well, true), 6.2).Head), FString(TEXT("Tied up")));
		const double T0 = 20.0;
		Shown(Well, T0);
		const FString Before = SSailHud::HoldTrimVerdict(Hold, Verdict(Well), T0).Say;
		TestEqual(TEXT("Hold: the line waits a moment"), FString(SSailHud::HoldTrimVerdict(Hold, Verdict(Curl), T0 + 0.5).Say), Before);
		TestTrue(TEXT("Hold: ... then follows"), FString(SSailHud::HoldTrimVerdict(Hold, Verdict(Curl), T0 + SSailHud::TrimSayHoldSeconds + 0.01).Say).Contains(TEXT("curling")));
	}

	// The yarns: each third of the sail shows its worst strip, so a call from any two strips is on a yarn.
	using EYarnFace = SSailHud::ETrimYarn;
	T = Trimmed(5);
	T.JibStrips[0].Flow = T.JibStrips[1].Flow = ESailFlow::Stalled;
	TestTrue(TEXT("Five strips: the bottom third holds strips 0 and 1"), SSailHud::TrimYarnState(T.JibStrips, 5, 0, EYarnFace::LuffLeeward) == ETelltaleState::Stalled);
	TestTrue(TEXT("... the middle yarn streams"), SSailHud::TrimYarnState(T.JibStrips, 5, 1, EYarnFace::LuffLeeward) == ETelltaleState::Streaming);
	TestTrue(TEXT("... the windward face streams"), SSailHud::TrimYarnState(T.JibStrips, 5, 0, EYarnFace::LuffWindward) == ETelltaleState::Streaming);
	T.MainStrips[3].Flow = ESailFlow::Luffing;
	TestTrue(TEXT("Four strips: the top third is strip 3"), SSailHud::TrimYarnState(T.MainStrips, 4, 2, EYarnFace::Leech) == ETelltaleState::Fluttering);
	T.MainStrips[1].Flow = ESailFlow::Stalled;
	TestTrue(TEXT("Two strips: the middle third reads the top strip"), SSailHud::TrimYarnState(T.MainStrips, 2, 1, EYarnFace::Leech) == ETelltaleState::Stalled);
	TestTrue(TEXT("No strips: streaming"), SSailHud::TrimYarnState(T.MainStrips, 0, 1, EYarnFace::Leech) == ETelltaleState::Streaming);
	TestEqual(TEXT("TrimStripAt: three-quarters up four strips"), SSailHud::TrimStripAt(0.75f, 4), 3);
	TestEqual(TEXT("TrimStripAt: no strips reads none past 0"), SSailHud::TrimStripAt(0.75f, 0), 0);

	// The sweep: every pair (and single) of strips luffing, backed or stalled on either sail, on a sloop and a cat-rigged
	// dinghy, across the points of sail, Realistic and Easy. The headline warns exactly when the tips do, and its call shows.
	int32 Cases = 0, Failures = 0;
	auto AnyBand = [](const FSailStripState* Strips, int32 N, EYarnFace Face, ETelltaleState Want)
	{
		for (int32 B = 0; B < 3; ++B) if (SSailHud::TrimYarnState(Strips, N, B, Face) == Want) return true;
		return false;
	};
	const ESailFlow Flows[] = { ESailFlow::Luffing, ESailFlow::Backed, ESailFlow::Stalled };
	for (const int32 NumJib : { 5, 0 })
	for (const double Twa : { 28.0, 33.0, 38.0, 45.0, 50.0, 58.0, 75.0, 100.0, 140.0 })
	for (const FEasyAssists* A : { &Realistic, &Easy })
	for (const bool bMain : { false, true })
	for (const ESailFlow Flow : Flows)
	for (int32 I = 0; I < 5; ++I)
	for (int32 J = I; J < 5; ++J)
	{
		FBoatTelemetry S = Trimmed(NumJib, Twa);
		FSailStripState* Strips = bMain ? S.MainStrips : S.JibStrips;
		const int32 N = bMain ? S.NumMainStrips : S.NumJibStrips;
		if (J >= N) continue;
		Strips[I].Flow = Strips[J].Flow = Flow;
		TArray<TPair<FString, int32>> Tips;
		SailingCollectBoatTips(S, 1.0, FBoatControls(), *A, false, false, Tips);
		bool bTipWarns = false;
		for (const TPair<FString, int32>& Tip : Tips) if (Tip.Value >= 2) bTipWarns = true;
		const SSailHud::FTrimVerdict V = SSailHud::TrimVerdict(S, J22, *A, false);
		const FString H = V.Head;
		// Whatever the headline calls on the sails is on a yarn the panel draws.
		const FSailStripState* Luff = NumJib > 0 ? S.JibStrips : S.MainStrips;
		const int32 NumLuff = NumJib > 0 ? S.NumJibStrips : S.NumMainStrips;
		bool bShown = true;
		if (H == TEXT("Jib luffing") || H == TEXT("Sail luffing")) bShown = AnyBand(Luff, NumLuff, EYarnFace::LuffWindward, ETelltaleState::Lifting);
		else if (H == TEXT("Jib too tight") || H == TEXT("Sail too tight")) bShown = AnyBand(Luff, NumLuff, EYarnFace::LuffLeeward, ETelltaleState::Stalled);
		else if (H == TEXT("Main luffing")) bShown = AnyBand(S.MainStrips, S.NumMainStrips, EYarnFace::Leech, ETelltaleState::Fluttering);
		else if (H == TEXT("Main too tight")) bShown = AnyBand(S.MainStrips, S.NumMainStrips, EYarnFace::Leech, ETelltaleState::Stalled);
		// And the all-clear never says "streaming" beside a curled ribbon.
		else if (V.bGood && AnyBand(S.MainStrips, S.NumMainStrips, EYarnFace::Leech, ETelltaleState::Stalled)) bShown = FString(V.Say).Contains(TEXT("curling"));
		++Cases;
		if (V.bGood == bTipWarns || !bShown)
		{
			if (++Failures <= 8)
			{
				AddError(FString::Printf(TEXT("%s, TWA %.0f, %s, %s strips %d and %d %s: headline \"%s\" (good %d), tips warn %d, call shown %d"),
					NumJib > 0 ? TEXT("sloop") : TEXT("dinghy"), Twa, A->bEnabled ? TEXT("Easy") : TEXT("Realistic"), bMain ? TEXT("main") : TEXT("jib"), I, J,
					Flow == ESailFlow::Stalled ? TEXT("stalled") : Flow == ESailFlow::Backed ? TEXT("backed") : TEXT("luffing"), *H, V.bGood ? 1 : 0, bTipWarns ? 1 : 0, bShown ? 1 : 0));
			}
		}
	}
	TestTrue(TEXT("The sweep ran"), Cases > 500);
	TestEqual(TEXT("Headline and tips disagree in no case"), Failures, 0);
	return true;
}

// The paper's grain (UI overhaul phase 10): it tiles without a seam, stays in range, and is balanced (it must not tint
// the sheet lighter or darker on average).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIPaperGrainTest, "SailingSim.UI.PaperGrain", UIFlags)
bool FSailingUIPaperGrainTest::RunTest(const FString&)
{
	const int32 N = 256;
	double Sum = 0.0;
	float Lo = 1.f, Hi = -1.f, WorstSeam = 0.f, WorstStep = 0.f;
	for (int32 Y = 0; Y < N; ++Y)
	{
		for (int32 X = 0; X < N; ++X)
		{
			const float G = SailUI::PaperGrainValue(X, Y, N);
			Sum += G;
			Lo = FMath::Min(Lo, G);
			Hi = FMath::Max(Hi, G);
		}
		// Wrapping: texel N is texel 0.
		WorstSeam = FMath::Max(WorstSeam, FMath::Abs(SailUI::PaperGrainValue(N, Y, N) - SailUI::PaperGrainValue(0, Y, N)));
		WorstSeam = FMath::Max(WorstSeam, FMath::Abs(SailUI::PaperGrainValue(Y, N, N) - SailUI::PaperGrainValue(Y, 0, N)));
		// The step across the tile's edge is no bigger than the grain's own texel-to-texel steps (tooth and specks).
		WorstStep = FMath::Max(WorstStep, FMath::Abs(SailUI::PaperGrainValue(N - 1, Y, N) - SailUI::PaperGrainValue(N, Y, N)));
	}
	TestTrue(TEXT("The grain stays within -1..1"), Lo >= -1.f && Hi <= 1.f);
	TestTrue(TEXT("It has both light fibres and dark specks"), Lo < -0.3f && Hi > 0.3f);
	TestTrue(TEXT("It is balanced: the sheet keeps its tone"), FMath::Abs(Sum / double(N * N)) < 0.08);
	TestTrue(TEXT("It wraps exactly"), WorstSeam < 1e-6f);
	TestTrue(TEXT("No hard seam at the tile's edge"), WorstStep < 1.2f);
	return true;
}

// Controller glyphs (UI overhaul phase 11): every pad label the prompts use parses to a drawn glyph, not a text pill.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIPadGlyphsTest, "SailingSim.UI.PadGlyphs", UIFlags)
bool FSailingUIPadGlyphsTest::RunTest(const FString&)
{
	using SailUI::EPadGlyph;
	auto One = [this](const TCHAR* Pad, EPadGlyph Kind, const TCHAR* Label, uint8 Arms)
	{
		const TArray<SailUI::FPadGlyph> G = SailUI::ParsePadGlyphs(Pad);
		TestEqual(FString::Printf(TEXT("'%s' is one glyph"), Pad), G.Num(), 1);
		if (G.Num() != 1) return;
		TestTrue(FString::Printf(TEXT("'%s' kind"), Pad), G[0].Kind == Kind);
		TestEqual(FString::Printf(TEXT("'%s' label"), Pad), G[0].Label, FString(Label));
		TestEqual(FString::Printf(TEXT("'%s' arms"), Pad), int32(G[0].Arms), int32(Arms));
	};
	One(TEXT("A"), EPadGlyph::Face, TEXT("A"), 0);
	One(TEXT("Y"), EPadGlyph::Face, TEXT("Y"), 0);
	One(TEXT("L3"), EPadGlyph::StickClick, TEXT("L"), 0);
	One(TEXT("R"), EPadGlyph::Stick, TEXT("R"), 0);
	One(TEXT("R stick"), EPadGlyph::Stick, TEXT("R"), 0);
	One(TEXT("R ↕"), EPadGlyph::Stick, TEXT("R"), 3);
	One(TEXT("D-pad"), EPadGlyph::Dpad, TEXT(""), 15);
	One(TEXT("← →"), EPadGlyph::Dpad, TEXT(""), 12);
	One(TEXT("↑ ↓"), EPadGlyph::Dpad, TEXT(""), 3);
	One(TEXT("View"), EPadGlyph::View, TEXT(""), 0);
	One(TEXT("Menu"), EPadGlyph::Menu, TEXT(""), 0);
	One(TEXT("Hold View"), EPadGlyph::Text, TEXT("Hold View"), 0);

	const TArray<SailUI::FPadGlyph> Pair = SailUI::ParsePadGlyphs(TEXT("LB / RB"));
	TestEqual(TEXT("'LB / RB' is two bumpers"), Pair.Num(), 2);
	if (Pair.Num() == 2)
	{
		TestTrue(TEXT("Both are bumpers"), Pair[0].Kind == EPadGlyph::Bumper && Pair[1].Kind == EPadGlyph::Bumper);
		TestEqual(TEXT("The second is RB"), Pair[1].Label, FString(TEXT("RB")));
	}
	const TArray<SailUI::FPadGlyph> Triggers = SailUI::ParsePadGlyphs(TEXT("LT / RT"));
	TestTrue(TEXT("'LT / RT' is two triggers"), Triggers.Num() == 2 && Triggers[0].Kind == EPadGlyph::Trigger && Triggers[1].Kind == EPadGlyph::Trigger);
	TestTrue(TEXT("A bumper is wider than a face button"), SailUI::PadGlyphWidth(Pair.Num() ? Pair[0] : SailUI::FPadGlyph()) > 24.f);
	return true;
}

// The opening splash (docs/splash/): its fade timeline, the skip, and what it shows.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUISplashTimelineTest, "SailingSim.UI.Splash.Timeline", UIFlags)
bool FSailingUISplashTimelineTest::RunTest(const FString&)
{
	using namespace SailSplash;
	TestEqual(TEXT("Starts black"), ContentAlpha(0.0), 0.f);
	TestEqual(TEXT("Halfway through the fade in"), ContentAlpha(FadeInSeconds * 0.5), 0.5f);
	TestEqual(TEXT("Holds"), ContentAlpha(FadeInSeconds + HoldSeconds * 0.5), 1.f);
	TestEqual(TEXT("Halfway through the fade out"), ContentAlpha(FadeInSeconds + HoldSeconds + FadeOutSeconds * 0.5), 0.5f);
	TestEqual(TEXT("Gone at the end"), ContentAlpha(TotalSeconds), 0.f);
	TestFalse(TEXT("Not finished mid-hold"), IsFinished(2.0));
	TestTrue(TEXT("Finished at the end"), IsFinished(TotalSeconds));
	TestEqual(TEXT("The backdrop is solid through the hold"), BackdropAlpha(2.0), 1.f);
	TestEqual(TEXT("A skip in the hold fades from full"), ContentAlpha(2.0 + SkipFadeSeconds * 0.5, 2.0), 0.5f);
	TestEqual(TEXT("A skip during the fade in fades from what it had"), ContentAlpha(0.3 + SkipFadeSeconds * 0.5, 0.3), 0.25f);
	TestFalse(TEXT("A skip is not finished at once"), IsFinished(2.1, 2.0));
	TestTrue(TEXT("A skip finishes after its short fade"), IsFinished(2.0 + SkipFadeSeconds, 2.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUISplashWidgetTest, "SailingSim.UI.Splash.Widget", UIFlags)
bool FSailingUISplashWidgetTest::RunTest(const FString&)
{
	if (!FSlateApplication::IsInitialized()) return true;
	for (const bool bNvidia : { false, true })
	{
		bool bDone = false;
		TSharedRef<SSailSplash> S = SNew(SSailSplash).ShowNvidia(bNvidia).OnDone(FSimpleDelegate::CreateLambda([&bDone]() { bDone = true; }));
		TArray<FString> Texts;
		CollectTexts(S, Texts);
		auto Shows = [&Texts](const FString& W) { const FString U = W.ToUpper(); return Texts.ContainsByPredicate([&U](const FString& T) { return T.Contains(U); }); };
		TestTrue(TEXT("Names the game"), Shows(TEXT("Ready About")));
		TestTrue(TEXT("Credits Unreal"), Shows(TEXT("Made with Unreal Engine")));
		TestEqual(FString::Printf(TEXT("NVIDIA block only when asked (%d)"), bNvidia), Shows(SailSplash::NvidiaAttribution()), bNvidia);
		// A frame hitch (a map loading) counts at most 0.1 s, so the hold survives it.
		S->Advance(5.f);
		TestTrue(TEXT("A hitch does not eat the splash"), S->Elapsed() <= 0.1 + KINDA_SMALL_NUMBER && !S->IsDone());
		S->Skip();
		TestTrue(TEXT("Skipped"), S->IsSkipped());
		for (int32 I = 0; I < 6 && !bDone; ++I) S->Advance(0.1f);
		TestTrue(TEXT("A skip finishes and calls back"), bDone && S->IsDone());
	}
	return true;
}
