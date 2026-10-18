#include "Misc/AutomationTest.h"
#include "SailSave.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "BoatModel.h"
#include "Drills.h"
#include "Learning.h"
#include "UI/SailCatalog.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

// The versioned save file (docs/save/README.md): every field round-trips, GameUserSettings.ini (version 0) migrates
// into it, older files step forward keeping what they don't know, newer files are refused, writes are atomic and every
// string id resolves against the catalogue.
namespace SailSaveTestsLocal
{
	constexpr EAutomationTestFlags SaveFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	FString TestDir()
	{
		return FPaths::ConvertRelativePathToFull(FPaths::AutomationTransientDir() / TEXT("SailSave"));
	}

	TSharedPtr<FJsonObject> Parse(const FString& Text)
	{
		TSharedPtr<FJsonObject> Root;
		FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
		return Root;
	}

	/** A save with nothing left at its default. */
	FSailSave Everything()
	{
		FSailSave S;
		S.WrittenAt = FDateTime(2026, 10, 18, 16, 0, 0);
		FSailSave::FSettings& T = S.Settings;
		T.Quality = ESailingQuality::High;
		T.Difficulty = ESailingDifficulty::Realistic;
		T.ControlLayout = ESailingControlLayout::Full;
		T.bLearningMode = false;
		T.bTrimAssist = false;
		T.bShowHud = false;
		T.Volume = 0.35f;
		T.ResolutionScale = 75;
		T.FrameCap = 60;
		T.bCinematicLook = true;
		T.HudScale = 115;
		T.TextScale = 130;
		T.SpeedUnits = TEXT("kmh");
		T.DepthUnits = TEXT("fathoms");
		T.bHeadingsTrue = true;
		T.bAutoStart = true;
		T.bPauseOnFocusLoss = true;
		T.WorldId = TEXT("galveston-bay");
		T.SpotId = SailCatalog::SpotIds(1).Last();
		T.bHasSpotAt = true;
		T.SpotLat = SailCatalog::Spots(1).Last().Lat;
		T.SpotLon = SailCatalog::Spots(1).Last().Lon;
		T.BoatId = TEXT("Corsair880");
		T.WeatherId = TEXT("Thunderstorm");
		T.StartHour = 17.5f;
		T.Traffic = 2;
		T.WeatherSeed = 99;
		T.bGaugeLakeLevel = true;
		T.bFreeSail = true;
		T.InputBindings = TEXT("Input.ini");
		S.bHasLast = true;
		FSailSave::FSession& L = S.Last;
		L.WorldId = TEXT("galveston-bay");
		L.SpotId = SailCatalog::SpotIds(1)[2];
		L.bHasSpotAt = true;
		L.SpotLat = SailCatalog::Spots(1)[2].Lat;
		L.SpotLon = SailCatalog::Spots(1)[2].Lon;
		L.BoatId = TEXT("Hobie16");
		L.ModeId = TEXT("Race");
		L.DrillId = TEXT("HeaveTo");
		L.bLearningMode = false;
		L.bEasy = false;
		L.bLearningTips = false;
		L.bFreeSail = true;
		L.Traffic = 0;
		L.SavedAt = FDateTime(2026, 10, 17, 9, 30, 15);
		L.PresetId = TEXT("SeaBreeze");
		L.SkyId = TEXT("Storms");
		L.WindFromDeg = 140.f; L.WindKn = 14.f; L.GustKn = 18.f; L.LocalHour = 15.25f; L.AirTempF = 88.f; L.LakeLevelFt = -1.5f;
		L.Month = 6; L.Day = 20;
		L.RealDay = TEXT("2025-06-01");
		S.Progress.DrillsPassed = { TEXT("LeaveTheDock"), TEXT("SailATriangle") };
		S.Progress.RacesSailed = 4;
		S.Progress.RacesWon = 1;
		S.Progress.LogbookSessions = 7;
		S.Progress.LogbookEntries = 42;
		S.Progress.LogbookMiles = 31.5;
		S.Progress.HoursSailed = 12.25;
		FSailSave::FLessonRecord Lesson;
		Lesson.Id = TEXT("day-sailor.heave-to");
		Lesson.Medal = TEXT("silver");
		Lesson.BestSeconds = 83.5;
		Lesson.Runs = 3;
		Lesson.bQuizPassed = true;
		Lesson.QuizBest = 2;
		Lesson.QuizOf = 3;
		S.Progress.Lessons.Add(Lesson);
		FSailSave::FCheckrideRecord Ride;
		Ride.Id = TEXT("day-sailor.checkride");
		Ride.bPassed = true;
		Ride.QuizBest = 11;
		Ride.QuizOf = 12;
		S.Progress.Checkrides.Add(Ride);
		FSailSave::FCertificateRecord Cert;
		Cert.Id = TEXT("day-sailor");
		Cert.EarnedAt = FDateTime(2026, 10, 18, 15, 2, 9);
		S.Progress.Certificates.Add(Cert);
		return S;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSaveRoundTripTest, "SailingSim.Save.RoundTrip", SailSaveTestsLocal::SaveFlags)
bool FSailingSaveRoundTripTest::RunTest(const FString&)
{
	using namespace SailSaveTestsLocal;
	const FSailSave A = Everything();
	const FString Text = A.ToJson();
	FSailSave B;
	FString Message;
	TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Text, B, &Message)), int32(FSailSave::EResult::Ok));
	const FSailSave::FSettings& X = A.Settings;
	const FSailSave::FSettings& Y = B.Settings;
	TestEqual(TEXT("version"), B.Version, FSailSave::CurrentVersion);
	TestEqual(TEXT("writtenAt"), B.WrittenAt, A.WrittenAt);
	TestTrue(TEXT("quality"), Y.Quality == X.Quality);
	TestTrue(TEXT("difficulty"), Y.Difficulty == X.Difficulty);
	TestTrue(TEXT("control layout"), Y.ControlLayout == X.ControlLayout);
	TestEqual(TEXT("learning mode"), Y.bLearningMode, X.bLearningMode);
	TestEqual(TEXT("trim assist"), Y.bTrimAssist, X.bTrimAssist);
	TestEqual(TEXT("show hud"), Y.bShowHud, X.bShowHud);
	TestEqual(TEXT("volume"), Y.Volume, X.Volume);
	TestEqual(TEXT("resolution"), Y.ResolutionScale, X.ResolutionScale);
	TestEqual(TEXT("frame cap"), Y.FrameCap, X.FrameCap);
	TestEqual(TEXT("cinematic"), Y.bCinematicLook, X.bCinematicLook);
	TestEqual(TEXT("hud scale"), Y.HudScale, X.HudScale);
	TestEqual(TEXT("text scale"), Y.TextScale, X.TextScale);
	TestEqual(TEXT("speed units"), Y.SpeedUnits, X.SpeedUnits);
	TestEqual(TEXT("depth units"), Y.DepthUnits, X.DepthUnits);
	TestEqual(TEXT("headings true"), Y.bHeadingsTrue, X.bHeadingsTrue);
	TestEqual(TEXT("auto start"), Y.bAutoStart, X.bAutoStart);
	TestEqual(TEXT("pause on focus"), Y.bPauseOnFocusLoss, X.bPauseOnFocusLoss);
	TestEqual(TEXT("world"), Y.WorldId, X.WorldId);
	TestEqual(TEXT("spot"), Y.SpotId, X.SpotId);
	TestTrue(TEXT("spot lat/lon"), Y.bHasSpotAt && Y.SpotLat == X.SpotLat && Y.SpotLon == X.SpotLon);
	TestEqual(TEXT("boat"), Y.BoatId, X.BoatId);
	TestEqual(TEXT("weather"), Y.WeatherId, X.WeatherId);
	TestEqual(TEXT("start hour"), Y.StartHour, X.StartHour);
	TestEqual(TEXT("traffic"), Y.Traffic, X.Traffic);
	TestEqual(TEXT("weather seed"), Y.WeatherSeed, X.WeatherSeed);
	TestEqual(TEXT("gauge level"), Y.bGaugeLakeLevel, X.bGaugeLakeLevel);
	TestEqual(TEXT("input bindings"), Y.InputBindings, X.InputBindings);
	TestTrue(TEXT("has last"), B.bHasLast);
	const FSailSave::FSession& L = A.Last;
	const FSailSave::FSession& M = B.Last;
	TestEqual(TEXT("last world"), M.WorldId, L.WorldId);
	TestEqual(TEXT("last spot"), M.SpotId, L.SpotId);
	TestTrue(TEXT("last spot lat/lon"), M.bHasSpotAt && M.SpotLat == L.SpotLat && M.SpotLon == L.SpotLon);
	TestEqual(TEXT("last boat"), M.BoatId, L.BoatId);
	TestEqual(TEXT("last mode"), M.ModeId, L.ModeId);
	TestEqual(TEXT("last drill"), M.DrillId, L.DrillId);
	TestEqual(TEXT("last learning"), M.bLearningMode, L.bLearningMode);
	TestEqual(TEXT("last easy"), M.bEasy, L.bEasy);
	TestEqual(TEXT("last tips"), M.bLearningTips, L.bLearningTips);
	TestEqual(TEXT("last free sail"), M.bFreeSail, L.bFreeSail);
	TestEqual(TEXT("last traffic"), M.Traffic, L.Traffic);
	TestEqual(TEXT("last saved at"), M.SavedAt, L.SavedAt);
	TestEqual(TEXT("preset"), M.PresetId, L.PresetId);
	TestEqual(TEXT("sky"), M.SkyId, L.SkyId);
	TestEqual(TEXT("wind from"), M.WindFromDeg, L.WindFromDeg);
	TestEqual(TEXT("wind"), M.WindKn, L.WindKn);
	TestEqual(TEXT("gust"), M.GustKn, L.GustKn);
	TestEqual(TEXT("hour"), M.LocalHour, L.LocalHour);
	TestEqual(TEXT("air"), M.AirTempF, L.AirTempF);
	TestEqual(TEXT("lake level"), M.LakeLevelFt, L.LakeLevelFt);
	TestEqual(TEXT("month"), M.Month, L.Month);
	TestEqual(TEXT("day"), M.Day, L.Day);
	TestEqual(TEXT("real day"), M.RealDay, L.RealDay);
	TestEqual(TEXT("drills passed"), B.Progress.DrillsPassed, A.Progress.DrillsPassed);
	TestEqual(TEXT("races sailed"), B.Progress.RacesSailed, A.Progress.RacesSailed);
	TestEqual(TEXT("races won"), B.Progress.RacesWon, A.Progress.RacesWon);
	TestEqual(TEXT("log sessions"), B.Progress.LogbookSessions, A.Progress.LogbookSessions);
	TestEqual(TEXT("log entries"), B.Progress.LogbookEntries, A.Progress.LogbookEntries);
	TestEqual(TEXT("log miles"), B.Progress.LogbookMiles, A.Progress.LogbookMiles);
	TestEqual(TEXT("hours"), B.Progress.HoursSailed, A.Progress.HoursSailed);
	TestEqual(TEXT("free sail"), Y.bFreeSail, X.bFreeSail);
	if (TestEqual(TEXT("lessons"), B.Progress.Lessons.Num(), 1))
	{
		const FSailSave::FLessonRecord& P = A.Progress.Lessons[0];
		const FSailSave::FLessonRecord& Q = B.Progress.Lessons[0];
		TestTrue(TEXT("lesson fields"), Q.Id == P.Id && Q.Medal == P.Medal && Q.BestSeconds == P.BestSeconds && Q.Runs == P.Runs && Q.bQuizPassed == P.bQuizPassed
			&& Q.QuizBest == P.QuizBest && Q.QuizOf == P.QuizOf);
	}
	TestTrue(TEXT("checkride"), B.Progress.Checkrides.Num() == 1 && B.Progress.Checkrides[0].Id == A.Progress.Checkrides[0].Id && B.Progress.Checkrides[0].bPassed
		&& B.Progress.Checkrides[0].QuizBest == 11 && B.Progress.Checkrides[0].QuizOf == 12);
	TestTrue(TEXT("certificate"), B.Progress.Certificates.Num() == 1 && B.Progress.Certificates[0].Id == TEXT("day-sailor")
		&& B.Progress.Certificates[0].EarnedAt == A.Progress.Certificates[0].EarnedAt);
	TestEqual(TEXT("Written again, the same text"), B.ToJson(), Text);

	// Through the game's objects and back: Apply then Capture gives the same save.
	USailingSettings* Settings = NewObject<USailingSettings>();
	USailSessionSave* Session = NewObject<USailSessionSave>();
	A.Apply(*Settings, *Session);
	TestEqual(TEXT("Applied: Galveston"), Settings->World, 1);
	TestEqual(TEXT("Applied: last spot index"), Settings->LaunchSpot, SailCatalog::SpotIds(1).Num() - 1);
	TestEqual(TEXT("Applied: Corsair"), Settings->BoatType, int32(Sailing::EBoatType::Corsair880));
	TestEqual(TEXT("Applied: km/h"), Settings->SpeedUnits, 2);
	TestEqual(TEXT("Applied: heave-to is drill 3"), Session->Last.DrillIndex, 2);
	TestEqual(TEXT("Applied: two drills passed"), Session->DrillsPassed.Num(), 2);
	FSailSave C;
	C.Progress = A.Progress;   // the placeholders the game doesn't keep yet
	C.WrittenAt = A.WrittenAt;
	C.Capture(*Settings, *Session);
	TestEqual(TEXT("Captured back, the same text"), C.ToJson(), Text);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSaveIniMigrationTest, "SailingSim.Save.IniMigration", SailSaveTestsLocal::SaveFlags)
bool FSailingSaveIniMigrationTest::RunTest(const FString&)
{
	using namespace SailSaveTestsLocal;
	// Version 0: the ini-backed objects, with indices. Captured, written, read and applied: the same choices.
	USailingSettings* Old = NewObject<USailingSettings>();
	USailSessionSave* OldSession = NewObject<USailSessionSave>();
	Old->World = 2; Old->LaunchSpot = 1; Old->BoatType = int32(Sailing::EBoatType::Lagoon42); Old->WeatherPreset = ESailingWeather::Rain;
	Old->Quality = ESailingQuality::Low; Old->DepthUnits = 1; Old->TrafficLevel = 0;
	OldSession->bHasLast = true;
	OldSession->Last.World = 0; OldSession->Last.LaunchSpot = 3; OldSession->Last.Boat = int32(Sailing::EBoatType::ILCA7);
	OldSession->Last.Mode = ESailMode::Drill; OldSession->Last.DrillIndex = 4; OldSession->Last.Conditions.Sky = ESailSky::Fog;
	OldSession->Last.Conditions.PresetId = TEXT("Norther");
	OldSession->DrillsPassed = { 0, 5 };
	FSailSave Save;
	Save.Capture(*Old, *OldSession);
	const FString Text = Save.ToJson();
	const TSharedPtr<FJsonObject> Root = Parse(Text);
	TestTrue(TEXT("JSON"), Root.IsValid());
	if (!Root.IsValid()) return false;
	TestEqual(TEXT("Written as version 1"), int32(Root->GetNumberField(TEXT("version"))), 1);
	const TSharedPtr<FJsonObject> Start = Root->GetObjectField(TEXT("settings"))->GetObjectField(TEXT("start"));
	TestEqual(TEXT("World by id"), Start->GetStringField(TEXT("world")), FString(TEXT("gulf")));
	TestEqual(TEXT("Spot by id"), Start->GetStringField(TEXT("launchSpot")), SailCatalog::SpotIds(2)[1]);
	TestEqual(TEXT("Boat by id"), Start->GetStringField(TEXT("boat")), FString(TEXT("Lagoon42")));
	TestEqual(TEXT("Weather by id"), Start->GetStringField(TEXT("weather")), FString(TEXT("Rain")));
	const TSharedPtr<FJsonObject> Last = Root->GetObjectField(TEXT("lastSession"));
	TestEqual(TEXT("Last spot by id"), Last->GetStringField(TEXT("launchSpot")), SailCatalog::World(0).Spots[3].Id);
	TestEqual(TEXT("Last drill by id"), Last->GetStringField(TEXT("drill")), FString(TEXT("CrewOverboardQuickStop")));
	TestEqual(TEXT("Mode by name"), Last->GetStringField(TEXT("mode")), FString(TEXT("Drill")));
	TArray<FString> Passed;
	Root->GetObjectField(TEXT("progress"))->TryGetStringArrayField(TEXT("drillsPassed"), Passed);
	TestEqual(TEXT("Drills passed by id"), Passed, TArray<FString>{ TEXT("LeaveTheDock"), TEXT("ReturnAndDock") });

	FSailSave Read;
	TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Text, Read)), int32(FSailSave::EResult::Ok));
	USailingSettings* New = NewObject<USailingSettings>();
	USailSessionSave* NewSession = NewObject<USailSessionSave>();
	Read.Apply(*New, *NewSession);
	TestEqual(TEXT("World"), New->World, 2);
	TestEqual(TEXT("Spot"), New->LaunchSpot, 1);
	TestEqual(TEXT("Boat"), New->BoatType, Old->BoatType);
	TestTrue(TEXT("Weather"), New->WeatherPreset == ESailingWeather::Rain);
	TestTrue(TEXT("Quality"), New->Quality == ESailingQuality::Low);
	TestEqual(TEXT("Depth units"), New->DepthUnits, 1);
	TestEqual(TEXT("Traffic"), New->TrafficLevel, 0);
	TestTrue(TEXT("Has last"), NewSession->bHasLast);
	TestEqual(TEXT("Last world"), NewSession->Last.World, 0);
	TestEqual(TEXT("Last spot"), NewSession->Last.LaunchSpot, 3);
	TestEqual(TEXT("Last boat"), NewSession->Last.Boat, OldSession->Last.Boat);
	TestTrue(TEXT("Last mode"), NewSession->Last.Mode == ESailMode::Drill);
	TestEqual(TEXT("Last drill"), NewSession->Last.DrillIndex, 4);
	TestTrue(TEXT("Last sky"), NewSession->Last.Conditions.Sky == ESailSky::Fog);
	TestEqual(TEXT("Last preset"), NewSession->Last.Conditions.PresetId, FName(TEXT("Norther")));
	TestEqual(TEXT("Drills passed"), NewSession->DrillsPassed, TArray<int32>{ 0, 5 });

	// Version 0 has no JSON: a file without a version (or version 0) is not a save.
	FSailSave Bad;
	TestEqual(TEXT("No version: invalid"), int32(FSailSave::FromJson(TEXT("{\"settings\":{}}"), Bad)), int32(FSailSave::EResult::Invalid));
	TestEqual(TEXT("Not JSON: invalid"), int32(FSailSave::FromJson(TEXT("profile"), Bad)), int32(FSailSave::EResult::Invalid));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSaveMigrationTest, "SailingSim.Save.Migration", SailSaveTestsLocal::SaveFlags)
bool FSailingSaveMigrationTest::RunTest(const FString&)
{
	using namespace SailSaveTestsLocal;
	// A version-1 file from a game that knows more: unknown fields at every level and a drill this game doesn't have.
	const FString Fixture = TEXT(R"({
		"version": 1, "game": "SailingSim", "career": { "rank": "Skipper", "xp": 1200 },
		"settings": { "quality": "Ultra", "colourBlind": "deuteranopia",
			"display": { "speedUnits": "mph", "hdr": true },
			"start": { "world": "ray-hubbard", "launchSpot": "chandlers-landing", "boat": "Sunfish", "weather": "Overcast" } },
		"lastSession": { "world": "galveston-bay", "launchSpot": "texas-city-dike", "boat": "Catalina30", "mode": "Passage",
			"crew": [ "Ada", "Omari" ], "conditions": { "sky": "Overcast", "windKn": 22, "swellM": 1.5 } },
		"progress": { "drillsPassed": [ "HeaveTo", "SpinnakerSet" ], "racesSailed": 3, "badges": [ "first-tack" ] }
	})");
	FSailSave Save;
	FString Message;
	TestEqual(TEXT("Current version reads as is"), int32(FSailSave::FromJson(Fixture, Save, &Message)), int32(FSailSave::EResult::Ok));
	TestTrue(TEXT("Ultra"), Save.Settings.Quality == ESailingQuality::Ultra);
	TestEqual(TEXT("mph"), Save.Settings.SpeedUnits, FString(TEXT("mph")));
	TestEqual(TEXT("Wind"), Save.Last.WindKn, 22.f);
	TestEqual(TEXT("Both drills kept"), Save.Progress.DrillsPassed.Num(), 2);

	// Applied and captured back (as the game does on every write): the unknown drill and fields survive.
	USailingSettings* Settings = NewObject<USailingSettings>();
	USailSessionSave* Session = NewObject<USailSessionSave>();
	Save.Apply(*Settings, *Session);
	TestEqual(TEXT("Chandlers Landing"), Settings->LaunchSpot, SailCatalog::SpotIds(0).IndexOfByKey(FString(TEXT("chandlers-landing"))));
	TestTrue(TEXT("Chandlers Landing is a spot"), Settings->LaunchSpot > 0);
	TestEqual(TEXT("Only the known drill becomes an index"), Session->DrillsPassed, TArray<int32>{ int32(ESailingDrill::HeaveTo) - 1 });
	Session->DrillsPassed.Add(0);   // the player passes Leave the Dock
	Save.Capture(*Settings, *Session);
	const TSharedPtr<FJsonObject> Out = Parse(Save.ToJson());
	TestTrue(TEXT("JSON"), Out.IsValid());
	if (!Out.IsValid()) return false;
	TestEqual(TEXT("Root unknown kept"), Out->GetObjectField(TEXT("career"))->GetStringField(TEXT("rank")), FString(TEXT("Skipper")));
	TestEqual(TEXT("Settings unknown kept"), Out->GetObjectField(TEXT("settings"))->GetStringField(TEXT("colourBlind")), FString(TEXT("deuteranopia")));
	TestTrue(TEXT("Nested unknown kept"), Out->GetObjectField(TEXT("settings"))->GetObjectField(TEXT("display"))->GetBoolField(TEXT("hdr")));
	TestEqual(TEXT("Session unknown kept"), Out->GetObjectField(TEXT("lastSession"))->GetArrayField(TEXT("crew")).Num(), 2);
	TestEqual(TEXT("Conditions unknown kept"), Out->GetObjectField(TEXT("lastSession"))->GetObjectField(TEXT("conditions"))->GetNumberField(TEXT("swellM")), 1.5);
	TestEqual(TEXT("Progress unknown kept"), Out->GetObjectField(TEXT("progress"))->GetArrayField(TEXT("badges")).Num(), 1);
	TArray<FString> Passed;
	Out->GetObjectField(TEXT("progress"))->TryGetStringArrayField(TEXT("drillsPassed"), Passed);
	TestTrue(TEXT("New drill added"), Passed.Contains(TEXT("LeaveTheDock")));
	TestTrue(TEXT("Unknown drill kept"), Passed.Contains(TEXT("SpinnakerSet")));
	TestEqual(TEXT("Known value updated, not the old one"), Out->GetObjectField(TEXT("progress"))->GetNumberField(TEXT("racesSailed")), 3.0);

	// The step chain: from the current version nothing to do; from 0 there is no JSON step (the ini is read instead).
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	TestTrue(TEXT("Current version needs no step"), FSailSave::Migrate(*Root, FSailSave::CurrentVersion));
	AddExpectedError(TEXT("no migration from version 0"), EAutomationExpectedErrorFlags::Contains, 1);
	TestFalse(TEXT("No step from version 0"), FSailSave::Migrate(*Root, 0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSaveNewerTest, "SailingSim.Save.NewerRefused", SailSaveTestsLocal::SaveFlags)
bool FSailingSaveNewerTest::RunTest(const FString&)
{
	FSailSave Save;
	FString Message;
	const FSailSave::EResult R = FSailSave::FromJson(TEXT(R"({ "version": 99, "settings": { "quality": "Low", "start": { "boat": "Sunfish" } } })"), Save, &Message);
	TestEqual(TEXT("Refused"), int32(R), int32(FSailSave::EResult::Refused));
	TestTrue(TEXT("Says why"), Message.Contains(TEXT("99")));
	TestTrue(TEXT("Defaults kept: quality"), Save.Settings.Quality == ESailingQuality::Medium);
	TestEqual(TEXT("Defaults kept: boat"), Save.Settings.BoatId, FString(TEXT("J22")));
	TestFalse(TEXT("No last session"), Save.bHasLast);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSaveAtomicTest, "SailingSim.Save.AtomicWrite", SailSaveTestsLocal::SaveFlags)
bool FSailingSaveAtomicTest::RunTest(const FString&)
{
	using namespace SailSaveTestsLocal;
	IFileManager& Files = IFileManager::Get();
	const FString Dir = TestDir();
	Files.DeleteDirectory(*Dir, false, true);
	const FString Path = Dir / TEXT("profile.json");
	const FString First = FSailSave().ToJson();
	const FString Second = SailSaveTestsLocal::Everything().ToJson();
	TestTrue(TEXT("First write"), FSailSave::WriteAtomic(Path, First));
	TestTrue(TEXT("Second write over it"), FSailSave::WriteAtomic(Path, Second));
	FString Text;
	TestTrue(TEXT("Reads"), FFileHelper::LoadFileToString(Text, *Path));
	TestEqual(TEXT("The whole second file"), Text, Second);
	TestFalse(TEXT("No temporary left"), Files.FileExists(*(Path + TEXT(".tmp"))));
	TArray<FString> Found;
	Files.FindFiles(Found, *(Dir / TEXT("*")), true, false);
	TestEqual(TEXT("One file in the folder"), Found.Num(), 1);

	// A write that cannot finish (its temporary path is taken by a folder) fails and leaves the old file whole.
	Files.MakeDirectory(*(Path + TEXT(".tmp")), true);
	TestFalse(TEXT("Blocked write fails"), FSailSave::WriteAtomic(Path, First));
	TestTrue(TEXT("Reads"), FFileHelper::LoadFileToString(Text, *Path));
	TestEqual(TEXT("Old file intact"), Text, Second);
	Files.DeleteDirectory(*Dir, false, true);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSaveIdsTest, "SailingSim.Save.Ids", SailSaveTestsLocal::SaveFlags)
bool FSailingSaveIdsTest::RunTest(const FString&)
{
	// Worlds.
	for (int32 W = 0; W < 3; ++W) TestEqual(*FString::Printf(TEXT("World %d"), W), FSailSave::WorldIndex(FSailSave::WorldId(W)), W);
	TestEqual(TEXT("Lake id"), FSailSave::WorldId(0), FString(TEXT("ray-hubbard")));
	for (const SailCatalog::FWorld& W : SailCatalog::Worlds()) TestEqual(*FString::Printf(TEXT("Catalogue world %s"), *W.Name), W.Id, FSailSave::WorldId(W.Index));
	TestEqual(TEXT("Unknown world"), FSailSave::WorldIndex(TEXT("lake-tahoe")), -1);
	// Boats: every EBoatType, by its name.
	for (int32 B = 0; B < int32(Sailing::EBoatType::Count); ++B)
	{
		const FString Id = FSailSave::BoatId(B);
		TestEqual(*FString::Printf(TEXT("Boat %s"), *Id), FSailSave::BoatIndex(Id), B);
		const FString Bare = FString(UTF8_TO_TCHAR(Sailing::BoatTypeName(Sailing::EBoatType(B)))).Replace(TEXT("/"), TEXT("")).Replace(TEXT(" "), TEXT(""));
		TestTrue(*FString::Printf(TEXT("Boat %s is its name without punctuation (%s)"), *Id, *Bare), Bare.StartsWith(Id));
	}
	// Spots: unique, non-empty, the catalogue's own, and each one lands on its index through a save.
	for (int32 W = 0; W < 3; ++W)
	{
		const TArray<FString>& Ids = SailCatalog::SpotIds(W);
		TestTrue(*FString::Printf(TEXT("World %d has spots"), W), Ids.Num() > 0);
		TSet<FString> Seen;
		for (int32 I = 0; I < Ids.Num(); ++I)
		{
			TestFalse(*FString::Printf(TEXT("Spot %d.%d has an id"), W, I), Ids[I].IsEmpty());
			TestFalse(*FString::Printf(TEXT("Spot %s is unique"), *Ids[I]), Seen.Contains(Ids[I]));
			Seen.Add(Ids[I]);
			if (W < 2) TestEqual(*FString::Printf(TEXT("Catalogue spot %s"), *Ids[I]), SailCatalog::World(W).Spots[I].Id, Ids[I]);
			USailingSettings* S = NewObject<USailingSettings>();
			USailSessionSave* Session = NewObject<USailSessionSave>();
			S->World = W; S->LaunchSpot = I;
			FSailSave Save;
			Save.Capture(*S, *Session);
			TestEqual(*FString::Printf(TEXT("Spot %s saved by id"), *Ids[I]), Save.Settings.SpotId, Ids[I]);
			S->LaunchSpot = 0;
			Save.Apply(*S, *Session);
			TestEqual(*FString::Printf(TEXT("Spot %s round trip"), *Ids[I]), S->LaunchSpot, I);
		}
	}
	TestEqual(TEXT("Home spot"), SailCatalog::SpotIds(0)[0], FString(TEXT("rush-creek-yacht-club")));
	// Drills: the session's indices, and the Learning content's own ids.
	const FLearningContent& Content = FLearningContent::Get();
	for (int32 I = 0; I < int32(ESailingDrill::Count) - 1; ++I)
	{
		const FString Id = FSailSave::DrillId(I);
		TestEqual(*FString::Printf(TEXT("Drill %s"), *Id), FSailSave::DrillIndex(Id), I);
		TestNotNull(*FString::Printf(TEXT("Drill %s has a briefing"), *Id), Content.Briefing(ESailingDrill(I + 1)));
		if (const FDrillBriefing* B = Content.Briefing(ESailingDrill(I + 1))) TestEqual(*FString::Printf(TEXT("Drill %s is the content's id"), *Id), B->Id, Id);
	}
	// Weather presets, skies and modes by their names.
	USailingSettings* S = NewObject<USailingSettings>();
	USailSessionSave* Session = NewObject<USailSessionSave>();
	Session->bHasLast = true;
	for (int32 P = 0; P <= int32(ESailingWeather::RandomDay); ++P)
	{
		S->WeatherPreset = ESailingWeather(P);
		Session->Last.Conditions.Sky = ESailSky(P % 5);
		Session->Last.Mode = ESailMode(P % 4);
		FSailSave Save;
		Save.Capture(*S, *Session);
		S->WeatherPreset = ESailingWeather::CalmMorning;
		Session->Last.Conditions.Sky = ESailSky::Clear;
		Session->Last.Mode = ESailMode::Free;
		Save.Apply(*S, *Session);
		TestEqual(*FString::Printf(TEXT("Weather %s"), *Save.Settings.WeatherId), int32(S->WeatherPreset), P);
		TestEqual(*FString::Printf(TEXT("Sky %s"), *Save.Last.SkyId), int32(Session->Last.Conditions.Sky), P % 5);
		TestEqual(*FString::Printf(TEXT("Mode %s"), *Save.Last.ModeId), int32(Session->Last.Mode), P % 4);
	}
	for (const FSailPreset& P : USailSessionSubsystem::Presets()) TestFalse(TEXT("Preset id"), P.Id.IsNone());
	// An id this game doesn't know falls back to the default (with a warning), never a crash or a wrong index.
	FSailSave Unknown;
	Unknown.Settings.BoatId = TEXT("Optimist");
	Unknown.Settings.WorldId = TEXT("lake-tahoe");
	Unknown.Settings.SpotId = TEXT("emerald-bay");
	AddExpectedMessage(TEXT("Save: unknown"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 3);
	Unknown.Apply(*S, *Session);
	TestEqual(TEXT("Unknown boat: the J/22"), S->BoatType, 0);
	TestEqual(TEXT("Unknown world: the lake"), S->World, 0);
	TestEqual(TEXT("Unknown spot: the first"), S->LaunchSpot, 0);
	return true;
}
