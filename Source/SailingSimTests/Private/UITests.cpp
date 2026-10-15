#include "Misc/AutomationTest.h"
#include "SailSession.h"
#include "SailingSettings.h"
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
		TSharedRef<SSailHud> Hud = SNew(SSailHud);
		TestTrue(TEXT("HUD builds"), Hud->Pawn() == nullptr);
	}
	S->World = W0; S->LaunchSpot = L0; S->BoatType = B0; S->TrafficLevel = T0; S->WeatherPreset = P0; S->StartHour = H0; S->Difficulty = D0; S->bLearningMode = bLearn0;
	S->Save();
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

