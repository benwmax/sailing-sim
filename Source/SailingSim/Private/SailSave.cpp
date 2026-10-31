#include "SailSave.h"
#include "SailingSim.h"
#include "BenchRunner.h"
#include "BoatModel.h"
#include "Drills.h"
#include "Learning.h"
#include "ScriptedScene.h"
#include "UI/SailCatalog.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace SailSaveLocal
{
	// The boats' save ids are EBoatType's names: a new boat is appended there and here, never renamed.
	const TCHAR* const BoatIds[] = { TEXT("J22"), TEXT("Sunfish"), TEXT("ILCA7"), TEXT("Catalina22"), TEXT("Catalina30"), TEXT("Hobie16"),
		TEXT("Corsair880"), TEXT("Lagoon42"), TEXT("Maxi") };
	static_assert(UE_ARRAY_COUNT(BoatIds) == int32(Sailing::EBoatType::Count), "every boat needs a save id");
	const TCHAR* const WorldIds[] = { TEXT("ray-hubbard"), TEXT("galveston-bay"), TEXT("gulf"), TEXT("marseille"), TEXT("texas-coast") };
	const TCHAR* const SpeedIds[] = { TEXT("kn"), TEXT("mph"), TEXT("kmh") };
	const TCHAR* const DepthIds[] = { TEXT("ft"), TEXT("m"), TEXT("fathoms") };

	template <typename TEnum>
	FString EnumId(TEnum Value)
	{
		return StaticEnum<TEnum>()->GetNameStringByValue(int64(Value));
	}

	template <typename TEnum>
	TEnum EnumFrom(const FString& Id, TEnum Fallback, const TCHAR* What)
	{
		const int64 V = StaticEnum<TEnum>()->GetValueByNameString(Id);
		if (V == INDEX_NONE || V >= StaticEnum<TEnum>()->GetMaxEnumValue())
		{
			if (!Id.IsEmpty()) UE_LOG(LogSailing, Warning, TEXT("Save: unknown %s \"%s\", using %s"), What, *Id, *EnumId(Fallback));
			return Fallback;
		}
		return TEnum(V);
	}

	int32 IndexOf(const TCHAR* const* Ids, int32 Count, const FString& Id)
	{
		for (int32 I = 0; I < Count; ++I) if (Id == Ids[I]) return I;
		return -1;
	}

	FString SpotIdOf(int32 World, int32 Spot)
	{
		const TArray<FString>& Ids = SailCatalog::SpotIds(World);
		return Ids.IsValidIndex(Spot) ? Ids[Spot] : (Ids.Num() > 0 ? Ids[0] : FString());
	}

	/** The catalogue's lat/lon of a spot (the save's fallback for its id). */
	void SpotAtOf(int32 World, int32 Spot, bool& bOutHas, double& OutLat, double& OutLon)
	{
		const TArray<SailCatalog::FSpot>& Spots = SailCatalog::Spots(World);
		const int32 I = Spots.IsValidIndex(Spot) ? Spot : 0;
		bOutHas = Spots.IsValidIndex(I);
		OutLat = bOutHas ? Spots[I].Lat : 0.0;
		OutLon = bOutHas ? Spots[I].Lon : 0.0;
	}

	void WriteAt(FJsonObject& O, bool bHas, double Lat, double Lon)
	{
		if (!bHas) return;
		TSharedRef<FJsonObject> At = MakeShared<FJsonObject>();
		At->SetNumberField(TEXT("lat"), Lat);
		At->SetNumberField(TEXT("lon"), Lon);
		O.SetObjectField(TEXT("launchSpotAt"), At);
	}

	void ReadAt(const FJsonObject& O, bool& bHas, double& Lat, double& Lon)
	{
		const TSharedPtr<FJsonObject>* At = nullptr;
		double La = 0.0, Lo = 0.0;
		if (O.TryGetObjectField(TEXT("launchSpotAt"), At) && At && (*At)->TryGetNumberField(TEXT("lat"), La) && (*At)->TryGetNumberField(TEXT("lon"), Lo)
			&& FMath::Abs(La) <= 90.0 && FMath::Abs(Lo) <= 180.0)
		{
			bHas = true;
			Lat = La;
			Lon = Lo;
		}
	}

	/** UTC minus local time, to the minute (two calls agree). */
	FTimespan UtcOffset()
	{
		return FTimespan::FromMinutes(FMath::RoundToDouble((FDateTime::UtcNow() - FDateTime::Now()).GetTotalMinutes()));
	}

	// Typed reads that keep the default when a field is missing or of another type.
	void Read(const FJsonObject& O, const TCHAR* Key, bool& V) { O.TryGetBoolField(Key, V); }
	void Read(const FJsonObject& O, const TCHAR* Key, int32& V) { O.TryGetNumberField(Key, V); }
	void Read(const FJsonObject& O, const TCHAR* Key, double& V) { O.TryGetNumberField(Key, V); }
	void Read(const FJsonObject& O, const TCHAR* Key, float& V) { double D = V; if (O.TryGetNumberField(Key, D)) V = float(D); }
	void Read(const FJsonObject& O, const TCHAR* Key, FString& V) { O.TryGetStringField(Key, V); }
	void Read(const FJsonObject& O, const TCHAR* Key, FDateTime& V) { FString S; if (O.TryGetStringField(Key, S)) FDateTime::ParseIso8601(*S, V); }

	TSharedPtr<FJsonObject> Child(const FJsonObject& O, const TCHAR* Key)
	{
		const TSharedPtr<FJsonObject>* C = nullptr;
		return O.TryGetObjectField(Key, C) && C ? *C : TSharedPtr<FJsonObject>();
	}

	TSharedRef<FJsonObject> Obj() { return MakeShared<FJsonObject>(); }

	/** Known fields over the file's own: anything the game doesn't know stays as it was, objects merged all the way down. */
	void KeepUnknown(FJsonObject& Known, const FJsonObject& Old)
	{
		for (const auto& F : Old.Values)
		{
			const TSharedPtr<FJsonValue>* Mine = Known.Values.Find(F.Key);
			if (!Mine) { Known.Values.Add(F.Key, F.Value); continue; }
			if ((*Mine)->Type == EJson::Object && F.Value.IsValid() && F.Value->Type == EJson::Object)
			{
				KeepUnknown(*(*Mine)->AsObject(), *F.Value->AsObject());
			}
		}
	}

	// Store state.
	struct FStore
	{
		bool bLoaded = false;
		bool bRefused = false;   // a newer save: never written over
		FSailSave Save;
		FString Status = TEXT("not loaded");
	};
	FStore& Store() { static FStore S; return S; }
}

// ---------------------------------------------------------------- ids

FString FSailSave::WorldId(int32 World) { return SailSaveLocal::WorldIds[FMath::Clamp(World, 0, int32(UE_ARRAY_COUNT(SailSaveLocal::WorldIds)) - 1)]; }
int32 FSailSave::WorldIndex(const FString& Id) { return SailSaveLocal::IndexOf(SailSaveLocal::WorldIds, UE_ARRAY_COUNT(SailSaveLocal::WorldIds), Id); }
FString FSailSave::BoatId(int32 Boat) { return SailSaveLocal::BoatIds[FMath::Clamp(Boat, 0, int32(UE_ARRAY_COUNT(SailSaveLocal::BoatIds)) - 1)]; }
int32 FSailSave::BoatIndex(const FString& Id) { return SailSaveLocal::IndexOf(SailSaveLocal::BoatIds, UE_ARRAY_COUNT(SailSaveLocal::BoatIds), Id); }
FString FSailSave::DrillId(int32 Index) { return FLearningContent::DrillId(ESailingDrill(FMath::Clamp(Index + 1, 1, int32(ESailingDrill::Count) - 1))); }
int32 FSailSave::SpotIndex(int32 World, const FString& Id, bool bHasAt, double Lat, double Lon)
{
	if (Id.IsEmpty() && !bHasAt) return 0;
	std::vector<Sailing::FPlacedThing> Things;
	for (const SailCatalog::FSpot& S : SailCatalog::Spots(World)) Things.push_back({ TCHAR_TO_UTF8(*S.Id), { S.North, S.East } });
	Sailing::FGeoPlacement Placement;
	Placement.Id = TCHAR_TO_UTF8(*Id);
	Placement.bHasLatLon = bHasAt;
	Placement.Geo = { Lat, Lon };
	Sailing::FMapPoint At;
	bool bById = false;
	const int32 I = Sailing::ResolvePlacement(SailCatalog::Anchor(World), Things, Placement, SpotSnapMeters, At, bById);
	if (I >= 0 && !bById)
	{
		UE_LOG(LogSailing, Log, TEXT("Save: launch spot \"%s\" is gone from %s; %s is at its saved position (%.6f, %.6f)"), *Id, *WorldId(World),
			*SailCatalog::Spots(World)[I].Id, Lat, Lon);
	}
	if (I < 0 && !Id.IsEmpty()) UE_LOG(LogSailing, Warning, TEXT("Save: unknown launch spot \"%s\" in %s, using the first"), *Id, *WorldId(World));
	return FMath::Max(I, 0);
}

int32 FSailSave::DrillIndex(const FString& Id)
{
	const ESailingDrill D = FLearningContent::DrillFromId(Id);
	return D == ESailingDrill::None ? -1 : int32(D) - 1;
}

// ---------------------------------------------------------------- JSON

FString FSailSave::ToJson() const
{
	using namespace SailSaveLocal;
	TSharedRef<FJsonObject> Root = Obj();
	Root->SetNumberField(TEXT("version"), CurrentVersion);
	Root->SetStringField(TEXT("game"), TEXT("SailingSim"));
	Root->SetStringField(TEXT("writtenAt"), WrittenAt.ToIso8601());

	const FSettings& S = Settings;
	TSharedRef<FJsonObject> Set = Obj();
	Set->SetStringField(TEXT("quality"), EnumId(S.Quality));
	Set->SetStringField(TEXT("difficulty"), EnumId(S.Difficulty));
	Set->SetStringField(TEXT("controlLayout"), EnumId(S.ControlLayout));
	Set->SetBoolField(TEXT("learningMode"), S.bLearningMode);
	Set->SetBoolField(TEXT("trimAssist"), S.bTrimAssist);
	Set->SetBoolField(TEXT("showHud"), S.bShowHud);
	TSharedRef<FJsonObject> Audio = Obj();
	Audio->SetNumberField(TEXT("volume"), S.Volume);
	Set->SetObjectField(TEXT("audio"), Audio);
	TSharedRef<FJsonObject> Display = Obj();
	Display->SetNumberField(TEXT("resolutionScale"), S.ResolutionScale);
	Display->SetNumberField(TEXT("frameCap"), S.FrameCap);
	Display->SetBoolField(TEXT("cinematicLook"), S.bCinematicLook);
	TSharedRef<FJsonObject> Graphics = Obj();
	Graphics->SetNumberField(TEXT("antiAliasing"), S.AntiAliasing);
	Graphics->SetNumberField(TEXT("shadowQuality"), S.ShadowQuality);
	Graphics->SetNumberField(TEXT("lightingQuality"), S.LightingQuality);
	Graphics->SetNumberField(TEXT("reflectionQuality"), S.ReflectionQuality);
	Graphics->SetNumberField(TEXT("cloudQuality"), S.CloudQuality);
	Graphics->SetNumberField(TEXT("waterQuality"), S.WaterQuality);
	Graphics->SetNumberField(TEXT("foliageQuality"), S.FoliageQuality);
	Graphics->SetNumberField(TEXT("viewDistanceQuality"), S.ViewDistanceQuality);
	Graphics->SetNumberField(TEXT("motionBlur"), S.MotionBlur);
	Graphics->SetNumberField(TEXT("fieldOfView"), S.FieldOfView);
	Graphics->SetNumberField(TEXT("brightness"), S.Brightness);
	Graphics->SetBoolField(TEXT("vsync"), S.bVSync);
	Set->SetObjectField(TEXT("graphics"), Graphics);
	Display->SetNumberField(TEXT("hudScale"), S.HudScale);
	Display->SetNumberField(TEXT("textScale"), S.TextScale);
	Display->SetStringField(TEXT("speedUnits"), S.SpeedUnits);
	Display->SetStringField(TEXT("depthUnits"), S.DepthUnits);
	Display->SetBoolField(TEXT("headingsTrue"), S.bHeadingsTrue);
	Display->SetBoolField(TEXT("autoStart"), S.bAutoStart);
	Display->SetBoolField(TEXT("pauseOnFocusLoss"), S.bPauseOnFocusLoss);
	Set->SetObjectField(TEXT("display"), Display);
	TSharedRef<FJsonObject> Privacy = Obj();
	Privacy->SetBoolField(TEXT("sendCrashReports"), S.bSendCrashReports);
	Set->SetObjectField(TEXT("privacy"), Privacy);
	TSharedRef<FJsonObject> Start = Obj();
	Start->SetStringField(TEXT("world"), S.WorldId);
	Start->SetStringField(TEXT("launchSpot"), S.SpotId);
	WriteAt(*Start, S.bHasSpotAt, S.SpotLat, S.SpotLon);
	Start->SetStringField(TEXT("boat"), S.BoatId);
	Start->SetStringField(TEXT("weather"), S.WeatherId);
	Start->SetNumberField(TEXT("startHour"), S.StartHour);
	Start->SetNumberField(TEXT("traffic"), S.Traffic);
	Start->SetNumberField(TEXT("weatherSeed"), S.WeatherSeed);
	Start->SetBoolField(TEXT("gaugeLakeLevel"), S.bGaugeLakeLevel);
	Set->SetObjectField(TEXT("start"), Start);
	TSharedRef<FJsonObject> Career = Obj();
	Career->SetBoolField(TEXT("freeSail"), S.bFreeSail);
	Set->SetObjectField(TEXT("career"), Career);
	TSharedRef<FJsonObject> Input = Obj();
	Input->SetStringField(TEXT("bindings"), S.InputBindings);
	Set->SetObjectField(TEXT("input"), Input);
	Root->SetObjectField(TEXT("settings"), Set);

	if (bHasLast)
	{
		const FSession& L = Last;
		TSharedRef<FJsonObject> Sess = Obj();
		Sess->SetStringField(TEXT("world"), L.WorldId);
		Sess->SetStringField(TEXT("launchSpot"), L.SpotId);
		WriteAt(*Sess, L.bHasSpotAt, L.SpotLat, L.SpotLon);
		Sess->SetStringField(TEXT("boat"), L.BoatId);
		Sess->SetStringField(TEXT("mode"), L.ModeId);
		Sess->SetStringField(TEXT("drill"), L.DrillId);
		Sess->SetBoolField(TEXT("learningMode"), L.bLearningMode);
		Sess->SetBoolField(TEXT("easy"), L.bEasy);
		Sess->SetBoolField(TEXT("learningTips"), L.bLearningTips);
		Sess->SetBoolField(TEXT("freeSail"), L.bFreeSail);
		Sess->SetNumberField(TEXT("traffic"), L.Traffic);
		Sess->SetStringField(TEXT("savedAt"), L.SavedAt.ToIso8601());
		TSharedRef<FJsonObject> C = Obj();
		C->SetStringField(TEXT("preset"), L.PresetId);
		C->SetStringField(TEXT("sky"), L.SkyId);
		C->SetNumberField(TEXT("windFromDeg"), L.WindFromDeg);
		C->SetNumberField(TEXT("windKn"), L.WindKn);
		C->SetNumberField(TEXT("gustKn"), L.GustKn);
		C->SetNumberField(TEXT("localHour"), L.LocalHour);
		C->SetNumberField(TEXT("month"), L.Month);
		C->SetNumberField(TEXT("day"), L.Day);
		C->SetNumberField(TEXT("airTempF"), L.AirTempF);
		C->SetNumberField(TEXT("lakeLevelFt"), L.LakeLevelFt);
		C->SetStringField(TEXT("realDay"), L.RealDay);
		Sess->SetObjectField(TEXT("conditions"), C);
		Root->SetObjectField(TEXT("lastSession"), Sess);
	}
	else
	{
		Root->SetField(TEXT("lastSession"), MakeShared<FJsonValueNull>());
	}

	TSharedRef<FJsonObject> Prog = Obj();
	TArray<TSharedPtr<FJsonValue>> Drills;
	for (const FString& D : Progress.DrillsPassed) Drills.Add(MakeShared<FJsonValueString>(D));
	Prog->SetArrayField(TEXT("drillsPassed"), Drills);
	Prog->SetNumberField(TEXT("racesSailed"), Progress.RacesSailed);
	Prog->SetNumberField(TEXT("racesWon"), Progress.RacesWon);
	TSharedRef<FJsonObject> Log = Obj();
	Log->SetNumberField(TEXT("sessions"), Progress.LogbookSessions);
	Log->SetNumberField(TEXT("entries"), Progress.LogbookEntries);
	Log->SetNumberField(TEXT("nauticalMiles"), Progress.LogbookMiles);
	Prog->SetObjectField(TEXT("logbook"), Log);
	Prog->SetNumberField(TEXT("hoursSailed"), Progress.HoursSailed);
	// The career, each record keyed by its id (an object, so a later game's lessons survive KeepUnknown).
	TSharedRef<FJsonObject> Lessons = Obj();
	for (const FLessonRecord& L : Progress.Lessons)
	{
		TSharedRef<FJsonObject> O = Obj();
		O->SetStringField(TEXT("medal"), L.Medal);
		O->SetBoolField(TEXT("medalEasy"), L.bMedalEasy);
		O->SetNumberField(TEXT("bestSeconds"), L.BestSeconds);
		O->SetNumberField(TEXT("runs"), L.Runs);
		O->SetBoolField(TEXT("quizPassed"), L.bQuizPassed);
		O->SetNumberField(TEXT("quizBest"), L.QuizBest);
		O->SetNumberField(TEXT("quizOf"), L.QuizOf);
		Lessons->SetObjectField(L.Id, O);
	}
	Prog->SetObjectField(TEXT("lessons"), Lessons);
	TSharedRef<FJsonObject> Rides = Obj();
	for (const FCheckrideRecord& C : Progress.Checkrides)
	{
		TSharedRef<FJsonObject> O = Obj();
		O->SetBoolField(TEXT("passed"), C.bPassed);
		O->SetNumberField(TEXT("quizBest"), C.QuizBest);
		O->SetNumberField(TEXT("quizOf"), C.QuizOf);
		Rides->SetObjectField(C.Id, O);
	}
	Prog->SetObjectField(TEXT("checkrides"), Rides);
	TSharedRef<FJsonObject> Certs = Obj();
	for (const FCertificateRecord& C : Progress.Certificates)
	{
		TSharedRef<FJsonObject> O = Obj();
		O->SetStringField(TEXT("earnedAt"), C.EarnedAt.ToIso8601());
		Certs->SetObjectField(C.Id, O);
	}
	Prog->SetObjectField(TEXT("certificates"), Certs);
	TSharedRef<FJsonObject> Scenes = Obj();
	for (const FSceneRecord& Sc : Progress.Scenes)
	{
		TSharedRef<FJsonObject> O = Obj();
		O->SetBoolField(TEXT("done"), Sc.bDone);
		O->SetNumberField(TEXT("plays"), Sc.Plays);
		O->SetNumberField(TEXT("bestSeconds"), Sc.BestSeconds);
		O->SetNumberField(TEXT("stepsPassed"), Sc.StepsPassed);
		O->SetNumberField(TEXT("stepsAssisted"), Sc.StepsAssisted);
		O->SetNumberField(TEXT("retries"), Sc.Retries);
		O->SetStringField(TEXT("completedAt"), Sc.CompletedAt.ToIso8601());
		Scenes->SetObjectField(Sc.Id, O);
	}
	Prog->SetObjectField(TEXT("scenes"), Scenes);
	Root->SetObjectField(TEXT("progress"), Prog);

	if (Raw.IsValid()) KeepUnknown(*Root, *Raw);
	// Career 1's Open everything is Free Sail now (docs/free-sail): freeSail carries it, so the old field goes.
	Career->RemoveField(TEXT("openEverything"));

	FString Text;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
	FJsonSerializer::Serialize(Root, Writer);
	return Text;
}

namespace SailSaveLocal
{
	/** One step, From -> From + 1, editing the JSON in place (docs/save/README.md, "Adding a field"). Version 0 has no
	 *  JSON (it is GameUserSettings.ini, read by Capture), so the first step will be 1 -> 2. */
	bool MigrateStep(FJsonObject& Root, int32 From)
	{
		// One step per version, e.g. if (From == 1) { ...; Root.SetNumberField(TEXT("version"), 2); return true; }
		// (an if chain, not a switch: MSVC rejects a switch with only a default, C4065, while there is no step yet).
		(void)Root;
		UE_LOG(LogSailing, Error, TEXT("Save: no migration from version %d"), From);
		return false;
	}
}

bool FSailSave::Migrate(FJsonObject& Root, int32 From)
{
	for (int32 V = From; V < CurrentVersion; ++V)
	{
		if (!SailSaveLocal::MigrateStep(Root, V)) return false;
	}
	Root.SetNumberField(TEXT("version"), CurrentVersion);
	return true;
}

FSailSave::EResult FSailSave::FromJson(const FString& Text, FSailSave& Out, FString* OutMessage)
{
	using namespace SailSaveLocal;
	Out = FSailSave();
	auto Say = [OutMessage](const FString& M) { if (OutMessage) *OutMessage = M; };
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
	{
		Say(TEXT("not a JSON object"));
		return EResult::Invalid;
	}
	int32 Version = -1;
	if (!Root->TryGetNumberField(TEXT("version"), Version) || Version < 1)
	{
		Say(TEXT("no version number"));
		return EResult::Invalid;
	}
	if (Version > CurrentVersion)
	{
		Say(FString::Printf(TEXT("version %d is newer than this game's %d"), Version, CurrentVersion));
		return EResult::Refused;
	}
	const bool bMigrated = Version < CurrentVersion;
	if (bMigrated && !Migrate(*Root, Version))
	{
		Say(FString::Printf(TEXT("cannot migrate version %d"), Version));
		return EResult::Invalid;
	}
	Out.Raw = Root;
	Out.Version = CurrentVersion;
	Read(*Root, TEXT("writtenAt"), Out.WrittenAt);

	if (const TSharedPtr<FJsonObject> Set = Child(*Root, TEXT("settings")))
	{
		FSettings& S = Out.Settings;
		FString Id;
		if (Set->TryGetStringField(TEXT("quality"), Id)) S.Quality = EnumFrom(Id, S.Quality, TEXT("quality"));
		if (Set->TryGetStringField(TEXT("difficulty"), Id)) S.Difficulty = EnumFrom(Id, S.Difficulty, TEXT("difficulty"));
		if (Set->TryGetStringField(TEXT("controlLayout"), Id)) S.ControlLayout = EnumFrom(Id, S.ControlLayout, TEXT("control layout"));
		Read(*Set, TEXT("learningMode"), S.bLearningMode);
		Read(*Set, TEXT("trimAssist"), S.bTrimAssist);
		Read(*Set, TEXT("showHud"), S.bShowHud);
		if (const TSharedPtr<FJsonObject> A = Child(*Set, TEXT("audio"))) Read(*A, TEXT("volume"), S.Volume);
		if (const TSharedPtr<FJsonObject> G = Child(*Set, TEXT("graphics")))
		{
			Read(*G, TEXT("antiAliasing"), S.AntiAliasing);
			Read(*G, TEXT("shadowQuality"), S.ShadowQuality);
			Read(*G, TEXT("lightingQuality"), S.LightingQuality);
			Read(*G, TEXT("reflectionQuality"), S.ReflectionQuality);
			Read(*G, TEXT("cloudQuality"), S.CloudQuality);
			Read(*G, TEXT("waterQuality"), S.WaterQuality);
			Read(*G, TEXT("foliageQuality"), S.FoliageQuality);
			Read(*G, TEXT("viewDistanceQuality"), S.ViewDistanceQuality);
			Read(*G, TEXT("motionBlur"), S.MotionBlur);
			Read(*G, TEXT("fieldOfView"), S.FieldOfView);
			Read(*G, TEXT("brightness"), S.Brightness);
			Read(*G, TEXT("vsync"), S.bVSync);
		}
		if (const TSharedPtr<FJsonObject> D = Child(*Set, TEXT("display")))
		{
			Read(*D, TEXT("resolutionScale"), S.ResolutionScale);
			Read(*D, TEXT("frameCap"), S.FrameCap);
			Read(*D, TEXT("cinematicLook"), S.bCinematicLook);
			Read(*D, TEXT("hudScale"), S.HudScale);
			Read(*D, TEXT("textScale"), S.TextScale);
			Read(*D, TEXT("speedUnits"), S.SpeedUnits);
			Read(*D, TEXT("depthUnits"), S.DepthUnits);
			Read(*D, TEXT("headingsTrue"), S.bHeadingsTrue);
			Read(*D, TEXT("autoStart"), S.bAutoStart);
			Read(*D, TEXT("pauseOnFocusLoss"), S.bPauseOnFocusLoss);
		}
		if (const TSharedPtr<FJsonObject> St = Child(*Set, TEXT("start")))
		{
			Read(*St, TEXT("world"), S.WorldId);
			Read(*St, TEXT("launchSpot"), S.SpotId);
			ReadAt(*St, S.bHasSpotAt, S.SpotLat, S.SpotLon);
			Read(*St, TEXT("boat"), S.BoatId);
			Read(*St, TEXT("weather"), S.WeatherId);
			Read(*St, TEXT("startHour"), S.StartHour);
			Read(*St, TEXT("traffic"), S.Traffic);
			Read(*St, TEXT("weatherSeed"), S.WeatherSeed);
			Read(*St, TEXT("gaugeLakeLevel"), S.bGaugeLakeLevel);
		}
		if (const TSharedPtr<FJsonObject> Pr = Child(*Set, TEXT("privacy"))) Read(*Pr, TEXT("sendCrashReports"), S.bSendCrashReports);
		if (const TSharedPtr<FJsonObject> In = Child(*Set, TEXT("input"))) Read(*In, TEXT("bindings"), S.InputBindings);
		if (const TSharedPtr<FJsonObject> Ca = Child(*Set, TEXT("career")))
		{
			// Free Sail replaced Career 1's Open everything switch: a file from before reads that field.
			if (Ca->HasField(TEXT("freeSail"))) Read(*Ca, TEXT("freeSail"), S.bFreeSail);
			else Read(*Ca, TEXT("openEverything"), S.bFreeSail);
		}
	}

	if (const TSharedPtr<FJsonObject> Sess = Child(*Root, TEXT("lastSession")))
	{
		Out.bHasLast = true;
		FSession& L = Out.Last;
		Read(*Sess, TEXT("world"), L.WorldId);
		Read(*Sess, TEXT("launchSpot"), L.SpotId);
		ReadAt(*Sess, L.bHasSpotAt, L.SpotLat, L.SpotLon);
		Read(*Sess, TEXT("boat"), L.BoatId);
		Read(*Sess, TEXT("mode"), L.ModeId);
		Read(*Sess, TEXT("drill"), L.DrillId);
		Read(*Sess, TEXT("learningMode"), L.bLearningMode);
		Read(*Sess, TEXT("easy"), L.bEasy);
		Read(*Sess, TEXT("learningTips"), L.bLearningTips);
		Read(*Sess, TEXT("freeSail"), L.bFreeSail);
		Read(*Sess, TEXT("traffic"), L.Traffic);
		Read(*Sess, TEXT("savedAt"), L.SavedAt);
		if (const TSharedPtr<FJsonObject> C = Child(*Sess, TEXT("conditions")))
		{
			Read(*C, TEXT("preset"), L.PresetId);
			Read(*C, TEXT("sky"), L.SkyId);
			Read(*C, TEXT("windFromDeg"), L.WindFromDeg);
			Read(*C, TEXT("windKn"), L.WindKn);
			Read(*C, TEXT("gustKn"), L.GustKn);
			Read(*C, TEXT("localHour"), L.LocalHour);
			Read(*C, TEXT("month"), L.Month);
			Read(*C, TEXT("day"), L.Day);
			Read(*C, TEXT("airTempF"), L.AirTempF);
			Read(*C, TEXT("lakeLevelFt"), L.LakeLevelFt);
			Read(*C, TEXT("realDay"), L.RealDay);
		}
	}

	if (const TSharedPtr<FJsonObject> P = Child(*Root, TEXT("progress")))
	{
		const TArray<TSharedPtr<FJsonValue>>* Drills = nullptr;
		if (P->TryGetArrayField(TEXT("drillsPassed"), Drills))
		{
			for (const TSharedPtr<FJsonValue>& D : *Drills)
			{
				FString Id;
				if (D.IsValid() && D->TryGetString(Id)) Out.Progress.DrillsPassed.AddUnique(Id);
			}
		}
		Read(*P, TEXT("racesSailed"), Out.Progress.RacesSailed);
		Read(*P, TEXT("racesWon"), Out.Progress.RacesWon);
		if (const TSharedPtr<FJsonObject> Log = Child(*P, TEXT("logbook")))
		{
			Read(*Log, TEXT("sessions"), Out.Progress.LogbookSessions);
			Read(*Log, TEXT("entries"), Out.Progress.LogbookEntries);
			Read(*Log, TEXT("nauticalMiles"), Out.Progress.LogbookMiles);
		}
		Read(*P, TEXT("hoursSailed"), Out.Progress.HoursSailed);
		if (const TSharedPtr<FJsonObject> Lessons = Child(*P, TEXT("lessons")))
		{
			for (const auto& F : Lessons->Values)
			{
				if (!F.Value.IsValid() || F.Value->Type != EJson::Object || F.Key.IsEmpty()) continue;
				const FJsonObject& O = *F.Value->AsObject();
				FLessonRecord L;
				L.Id = F.Key;
				Read(O, TEXT("medal"), L.Medal);
				Read(O, TEXT("medalEasy"), L.bMedalEasy);
				Read(O, TEXT("bestSeconds"), L.BestSeconds);
				Read(O, TEXT("runs"), L.Runs);
				Read(O, TEXT("quizPassed"), L.bQuizPassed);
				Read(O, TEXT("quizBest"), L.QuizBest);
				Read(O, TEXT("quizOf"), L.QuizOf);
				Out.Progress.Lessons.Add(L);
			}
		}
		if (const TSharedPtr<FJsonObject> Rides = Child(*P, TEXT("checkrides")))
		{
			for (const auto& F : Rides->Values)
			{
				if (!F.Value.IsValid() || F.Value->Type != EJson::Object || F.Key.IsEmpty()) continue;
				const FJsonObject& O = *F.Value->AsObject();
				FCheckrideRecord C;
				C.Id = F.Key;
				Read(O, TEXT("passed"), C.bPassed);
				Read(O, TEXT("quizBest"), C.QuizBest);
				Read(O, TEXT("quizOf"), C.QuizOf);
				Out.Progress.Checkrides.Add(C);
			}
		}
		if (const TSharedPtr<FJsonObject> Certs = Child(*P, TEXT("certificates")))
		{
			for (const auto& F : Certs->Values)
			{
				if (!F.Value.IsValid() || F.Value->Type != EJson::Object || F.Key.IsEmpty()) continue;
				FCertificateRecord C;
				C.Id = F.Key;
				Read(*F.Value->AsObject(), TEXT("earnedAt"), C.EarnedAt);
				Out.Progress.Certificates.Add(C);
			}
		}
		if (const TSharedPtr<FJsonObject> Scenes = Child(*P, TEXT("scenes")))
		{
			for (const auto& F : Scenes->Values)
			{
				if (!F.Value.IsValid() || F.Value->Type != EJson::Object || F.Key.IsEmpty()) continue;
				const FJsonObject& O = *F.Value->AsObject();
				FSceneRecord S;
				S.Id = F.Key;
				Read(O, TEXT("done"), S.bDone);
				Read(O, TEXT("plays"), S.Plays);
				Read(O, TEXT("bestSeconds"), S.BestSeconds);
				Read(O, TEXT("stepsPassed"), S.StepsPassed);
				Read(O, TEXT("stepsAssisted"), S.StepsAssisted);
				Read(O, TEXT("retries"), S.Retries);
				Read(O, TEXT("completedAt"), S.CompletedAt);
				Out.Progress.Scenes.Add(S);
			}
		}
	}
	Say(bMigrated ? FString::Printf(TEXT("migrated from version %d"), Version) : FString(TEXT("ok")));
	return bMigrated ? EResult::Migrated : EResult::Ok;
}

void FSailSave::FProgress::RecordScene(const Sailing::FSceneResult& Result, const FDateTime& NowUtc)
{
	if (!Result.bComplete || Result.SceneId.empty()) return;
	const FString Id = UTF8_TO_TCHAR(Result.SceneId.c_str());
	FSceneRecord* S = Scenes.FindByPredicate([&Id](const FSceneRecord& R) { return R.Id == Id; });
	if (!S)
	{
		S = &Scenes.AddDefaulted_GetRef();
		S->Id = Id;
	}
	if (!S->bDone) S->CompletedAt = NowUtc;
	S->BestSeconds = S->bDone ? FMath::Min(S->BestSeconds, Result.Seconds) : Result.Seconds;
	S->bDone = true;
	++S->Plays;
	S->StepsPassed = Result.StepsPassed;
	S->StepsAssisted = Result.StepsAssisted;
	S->Retries = Result.Retries;
}

// ---------------------------------------------------------------- the game's objects

void FSailSave::Capture(const USailingSettings& In, const USailSessionSave& InSession)
{
	using namespace SailSaveLocal;
	FSettings& S = Settings;
	S.Quality = In.Quality;
	S.Difficulty = In.Difficulty;
	S.ControlLayout = In.ControlLayout;
	S.bLearningMode = In.bLearningMode;
	S.bTrimAssist = In.bTrimAssist;
	S.bShowHud = In.bShowHud;
	S.Volume = In.Volume;
	S.ResolutionScale = In.ResolutionScale;
	S.FrameCap = In.FrameCap;
	S.bCinematicLook = In.bCinematicLook;
	S.AntiAliasing = In.AntiAliasing;
 	S.ShadowQuality = In.ShadowQuality;
 	S.LightingQuality = In.LightingQuality;
 	S.ReflectionQuality = In.ReflectionQuality;
 	S.CloudQuality = In.CloudQuality;
 	S.WaterQuality = In.WaterQuality;
 	S.FoliageQuality = In.FoliageQuality;
 	S.ViewDistanceQuality = In.ViewDistanceQuality;
 	S.MotionBlur = In.MotionBlur;
 	S.FieldOfView = In.FieldOfView;
 	S.Brightness = In.Brightness;
 	S.bVSync = In.bVSync;
	S.HudScale = In.HudScale;
	S.TextScale = In.TextScale;
	S.SpeedUnits = SpeedIds[FMath::Clamp(In.SpeedUnits, 0, 2)];
	S.DepthUnits = DepthIds[FMath::Clamp(In.DepthUnits, 0, 2)];
	S.bHeadingsTrue = In.bHeadingsTrue;
	S.bAutoStart = In.bAutoStart;
	S.bPauseOnFocusLoss = In.bPauseOnFocusLoss;
	S.bSendCrashReports = In.bSendCrashReports;
	S.WorldId = WorldId(In.World);
	S.SpotId = SpotIdOf(FMath::Clamp(In.World, 0, 2), In.LaunchSpot);
	SpotAtOf(FMath::Clamp(In.World, 0, 2), In.LaunchSpot, S.bHasSpotAt, S.SpotLat, S.SpotLon);
	S.BoatId = BoatId(In.BoatType);
	S.WeatherId = EnumId(In.WeatherPreset);
	S.StartHour = In.StartHour;
	S.Traffic = In.TrafficLevel;
	S.WeatherSeed = In.WeatherSeed;
	S.bGaugeLakeLevel = In.bGaugeLakeLevel;
	S.bFreeSail = In.bFreeSail;

	bHasLast = InSession.bHasLast;
	const FSailSessionConfig& C = InSession.Last;
	FSession& L = Last;
	L.WorldId = WorldId(C.World);
	L.SpotId = SpotIdOf(FMath::Clamp(C.World, 0, 2), C.LaunchSpot);
	SpotAtOf(FMath::Clamp(C.World, 0, 2), C.LaunchSpot, L.bHasSpotAt, L.SpotLat, L.SpotLon);
	L.BoatId = BoatId(C.Boat);
	L.ModeId = EnumId(C.Mode);
	L.DrillId = DrillId(C.DrillIndex);
	L.bLearningMode = C.bLearningMode;
	L.bEasy = C.bEasy;
	L.bLearningTips = C.bLearningTips;
	L.bFreeSail = C.bFreeSail;
	L.Traffic = C.Traffic;
	L.SavedAt = C.SavedAt + UtcOffset();   // the game keeps local time; the file UTC
	L.PresetId = C.Conditions.PresetId.ToString();
	L.SkyId = EnumId(C.Conditions.Sky);
	L.WindFromDeg = C.Conditions.WindFromDeg;
	L.WindKn = C.Conditions.WindKn;
	L.GustKn = C.Conditions.GustKn;
	L.LocalHour = C.Conditions.LocalHour;
	L.Month = C.Conditions.Month;
	L.Day = C.Conditions.Day;
	L.AirTempF = C.Conditions.AirTempF;
	L.LakeLevelFt = C.Conditions.LakeLevelFt;
	L.RealDay = C.Conditions.RealDay;

	// Drills passed: the game's, plus any id this version can't name (a later game's drill) kept from the file.
	TArray<FString> Drills;
	for (const int32 I : InSession.DrillsPassed) if (I >= 0 && I < int32(ESailingDrill::Count) - 1) Drills.AddUnique(DrillId(I));
	for (const FString& D : Progress.DrillsPassed) if (DrillIndex(D) < 0) Drills.AddUnique(D);
	Progress.DrillsPassed = Drills;
}

void FSailSave::Apply(USailingSettings& Out, USailSessionSave& OutSession) const
{
	using namespace SailSaveLocal;
	const FSettings& S = Settings;
	Out.Quality = S.Quality;
	Out.Difficulty = S.Difficulty;
	Out.ControlLayout = S.ControlLayout;
	Out.bLearningMode = S.bLearningMode;
	Out.bTrimAssist = S.bTrimAssist;
	Out.bShowHud = S.bShowHud;
	Out.Volume = FMath::Clamp(S.Volume, 0.f, 1.f);
	Out.ResolutionScale = S.ResolutionScale;
	Out.FrameCap = S.FrameCap;
	Out.bCinematicLook = S.bCinematicLook;
	Out.AntiAliasing = S.AntiAliasing;
 	Out.ShadowQuality = S.ShadowQuality;
 	Out.LightingQuality = S.LightingQuality;
 	Out.ReflectionQuality = S.ReflectionQuality;
 	Out.CloudQuality = S.CloudQuality;
 	Out.WaterQuality = S.WaterQuality;
 	Out.FoliageQuality = S.FoliageQuality;
 	Out.ViewDistanceQuality = S.ViewDistanceQuality;
 	Out.MotionBlur = S.MotionBlur;
 	Out.FieldOfView = S.FieldOfView;
 	Out.Brightness = S.Brightness;
 	Out.bVSync = S.bVSync;
	Out.HudScale = S.HudScale;
	Out.TextScale = S.TextScale;
	Out.SpeedUnits = FMath::Max(IndexOf(SpeedIds, 3, S.SpeedUnits), 0);
	Out.DepthUnits = FMath::Max(IndexOf(DepthIds, 3, S.DepthUnits), 0);
	Out.bHeadingsTrue = S.bHeadingsTrue;
	Out.bAutoStart = S.bAutoStart;
	Out.bPauseOnFocusLoss = S.bPauseOnFocusLoss;
	Out.bSendCrashReports = S.bSendCrashReports;
	auto World = [](const FString& Id)
	{
		const int32 W = WorldIndex(Id);
		if (W < 0) UE_LOG(LogSailing, Warning, TEXT("Save: unknown world \"%s\", using %s"), *Id, *WorldId(0));
		return FMath::Max(W, 0);
	};
	auto Boat = [](const FString& Id)
	{
		const int32 B = BoatIndex(Id);
		if (B < 0) UE_LOG(LogSailing, Warning, TEXT("Save: unknown boat \"%s\", using %s"), *Id, *BoatId(0));
		return FMath::Max(B, 0);
	};
	Out.World = World(S.WorldId);
	Out.LaunchSpot = SpotIndex(Out.World, S.SpotId, S.bHasSpotAt, S.SpotLat, S.SpotLon);
	Out.BoatType = Boat(S.BoatId);
	Out.WeatherPreset = EnumFrom(S.WeatherId, ESailingWeather::AfternoonBreeze, TEXT("weather"));
	Out.StartHour = S.StartHour;
	Out.TrafficLevel = FMath::Clamp(S.Traffic, 0, 2);
	Out.WeatherSeed = S.WeatherSeed;
	Out.bGaugeLakeLevel = S.bGaugeLakeLevel;
	Out.bFreeSail = S.bFreeSail;

	OutSession.bHasLast = bHasLast;
	OutSession.Last = FSailSessionConfig();
	if (bHasLast)
	{
		const FSession& L = Last;
		FSailSessionConfig& C = OutSession.Last;
		C.World = World(L.WorldId);
		C.LaunchSpot = SpotIndex(C.World, L.SpotId, L.bHasSpotAt, L.SpotLat, L.SpotLon);
		C.Boat = Boat(L.BoatId);
		C.Mode = EnumFrom(L.ModeId, ESailMode::Free, TEXT("mode"));
		C.DrillIndex = FMath::Max(DrillIndex(L.DrillId), 0);
		C.bLearningMode = L.bLearningMode;
		C.bEasy = L.bEasy;
		C.bLearningTips = L.bLearningTips;
		C.bFreeSail = L.bFreeSail;
		C.Traffic = FMath::Clamp(L.Traffic, 0, 2);
		C.SavedAt = L.SavedAt - UtcOffset();
		C.Conditions.PresetId = FName(*L.PresetId);
		C.Conditions.Sky = EnumFrom(L.SkyId, ESailSky::Fair, TEXT("sky"));
		C.Conditions.WindFromDeg = L.WindFromDeg;
		C.Conditions.WindKn = L.WindKn;
		C.Conditions.GustKn = L.GustKn;
		C.Conditions.LocalHour = L.LocalHour;
		C.Conditions.Month = FMath::Clamp(L.Month, 1, 12);
		C.Conditions.Day = FMath::Clamp(L.Day, 1, 31);
		C.Conditions.AirTempF = L.AirTempF;
		C.Conditions.LakeLevelFt = L.LakeLevelFt;
		C.Conditions.RealDay = L.RealDay;
	}
	OutSession.DrillsPassed.Reset();
	for (const FString& D : Progress.DrillsPassed)
	{
		const int32 I = DrillIndex(D);
		if (I >= 0) OutSession.DrillsPassed.AddUnique(I);
	}
}

bool FSailSave::WriteAtomic(const FString& Path, const FString& Text)
{
	IFileManager& Files = IFileManager::Get();
	Files.MakeDirectory(*FPaths::GetPath(Path), true);
	const FString Temp = Path + TEXT(".tmp");
	if (!FFileHelper::SaveStringToFile(Text, *Temp, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
	{
		Files.Delete(*Temp, false, false, true);
		return false;
	}
	// A rename on the same volume: a reader sees the old file or the new one, never half of one.
	if (!Files.Move(*Path, *Temp, true, true, false, true))
	{
		Files.Delete(*Temp, false, false, true);
		return false;
	}
	return true;
}

// ---------------------------------------------------------------- the store

FString SailSaveStore::Path()
{
	FString Arg;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingSave="), Arg, false) && !Arg.IsEmpty())
	{
		return FPaths::IsRelative(Arg) ? FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / Arg) : Arg;
	}
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("SaveGames") / TEXT("profile.json"));
}

FString SailSaveStore::Status() { return SailSaveLocal::Store().Status; }
FSailSave::FProgress& SailSaveStore::Progress() { return SailSaveLocal::Store().Save.Progress; }

void SailSaveStore::LoadOnce()
{
	using namespace SailSaveLocal;
	FStore& St = Store();
	if (St.bLoaded) return;
	St.bLoaded = true;
	const bool bNamed = FCString::Strifind(SailingArgs::Dev(), TEXT("SailingSave=")) != nullptr;
	if (USailingSettings::IgnoresSavedChoices() && !bNamed)
	{
		St.Status = TEXT("not used (a measuring or automation run)");
		return;
	}
	USailingSettings* Settings = USailingSettings::Get();
	USailSessionSave* Session = USailSessionSave::Get();
	const FString File = Path();
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *File))
	{
		// Version 0: GameUserSettings.ini, already loaded into the objects. Migrated once into a version-1 file.
		St.Save.Capture(*Settings, *Session);
		St.Status = FString::Printf(TEXT("no save at %s: migrated GameUserSettings.ini (version 0)"), *File);
		UE_LOG(LogSailing, Display, TEXT("Save: %s"), *St.Status);
		Commit();
		return;
	}
	FString Message;
	FSailSave Loaded;
	const FSailSave::EResult Result = FSailSave::FromJson(Text, Loaded, &Message);
	switch (Result)
	{
	case FSailSave::EResult::Refused:
		St.bRefused = true;
		St.Status = FString::Printf(TEXT("refused %s: %s; using the defaults and leaving the file as it is"), *File, *Message);
		UE_LOG(LogSailing, Warning, TEXT("Save: %s"), *St.Status);
		USailingSettings::RestoreClassDefaults();
		Session->bHasLast = false;
		Session->Last = FSailSessionConfig();
		Session->DrillsPassed.Reset();
		St.Save.Capture(*Settings, *Session);
		return;
	case FSailSave::EResult::Invalid:
	{
		// Kept beside it for a person to look at; the game goes on from the ini's choices.
		const FString Bad = File + TEXT(".bad");
		IFileManager::Get().Move(*Bad, *File, true, true);
		St.Save.Capture(*Settings, *Session);
		St.Status = FString::Printf(TEXT("unreadable %s (%s): moved to %s, migrated GameUserSettings.ini"), *File, *Message, *Bad);
		UE_LOG(LogSailing, Warning, TEXT("Save: %s"), *St.Status);
		Commit();
		return;
	}
	default:
		break;
	}
	St.Save = MoveTemp(Loaded);
	St.Save.Apply(*Settings, *Session);
	St.Status = FString::Printf(TEXT("loaded %s (%s)"), *File, *Message);
	UE_LOG(LogSailing, Display, TEXT("Save: %s"), *St.Status);
	if (Result == FSailSave::EResult::Migrated) Commit();   // written back at the current version
}

void SailSaveStore::Commit()
{
	using namespace SailSaveLocal;
	FStore& St = Store();
	if (!St.bLoaded || St.bRefused || USailingSettings::IgnoresSavedChoices()) return;
	St.Save.Capture(*USailingSettings::Get(), *USailSessionSave::Get());
	St.Save.WrittenAt = FDateTime::UtcNow();
	const FString File = Path();
	if (!FSailSave::WriteAtomic(File, St.Save.ToJson())) UE_LOG(LogSailing, Warning, TEXT("Save: could not write %s"), *File);
}
