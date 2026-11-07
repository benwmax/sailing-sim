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
#include "UI/SailLoading.h"
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
	TestEqual(TEXT("Nine boats (the fleet and the prologue's maxi)"), SailCatalog::Boats().Num(), 9);
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
	const TArray<SailCatalog::FCreditLine> Credits = SailCatalog::Credits();
	TArray<FString> Headings;
	for (const SailCatalog::FCreditLine& L : Credits)
		if (L.Kind == SailCatalog::ECreditKind::Heading1 || L.Kind == SailCatalog::ECreditKind::Heading2 || L.Kind == SailCatalog::ECreditKind::Heading3)
			Headings.Add(L.Text);
	TestTrue(TEXT("CREDITS.md has its sections"), Headings.Num() >= 4);
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

// Slice audit finding 25 (Bean, Nov 6 2026): a returning Career player (progress in the save, no last session) starts on
// Career, not Sail; a new save and Free Sail start on Sail; a last session starts on Continue.
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
	TestTrue(FString::Printf(TEXT("A last session starts on Continue (%s)"), *Got), Got.StartsWith(TEXT("CONTINUE")));
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
// mode's pad toggle, a half-second hold of the controls card's button (ASailboatPawn::BuildContext). A saved key list from
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
			const bool bHoldTap = (A.Action == TEXT("Photo") && B.Action == TEXT("ControlsCard")) || (A.Action == TEXT("ControlsCard") && B.Action == TEXT("Photo"));
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
	Bare.LoadingTextures = { TEXT("/Game/UI/A"), TEXT("/Game/UI/B") };
	Bare.LoadingBoats = { int32(EBoatType::J22), int32(EBoatType::Hobie16) };
	TestEqual(TEXT("no own or neutral still: none"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)).Num(), 0);
	Bare.LoadingTextures.Add(TEXT("/Game/UI/C"));
	Bare.LoadingBoats.Add(SailCatalog::FWorld::NoBoat);
	TestTrue(TEXT("a neutral still when there is no own one"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)) == TArray<FString>({ TEXT("/Game/UI/C") }));
	TestTrue(TEXT("the own still before the neutral one"), SailCatalog::LoadingStills(Bare, int32(EBoatType::J22)) == TArray<FString>({ TEXT("/Game/UI/A") }));
	// An untagged still (past LoadingBoats) could show any boat: never shown, not even as a neutral one.
	Bare.LoadingTextures.Add(TEXT("/Game/UI/D"));
	TestFalse(TEXT("an untagged still is left out"), SailCatalog::LoadingStills(Bare, int32(EBoatType::Sunfish)).Contains(TEXT("/Game/UI/D")));
	// Decided, not an accident: the Catalina 22 on Galveston Bay (no still of her there, none without a boat) loads on the
	// plain screen.
	TestEqual(TEXT("Galveston, Catalina 22: the plain screen"), SailCatalog::LoadingStills(SailCatalog::World(1), int32(EBoatType::Catalina22)).Num(), 0);
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
	}
	else AddWarning(TEXT("No Slate application: the loading screen itself is not built"));
	return true;
}
