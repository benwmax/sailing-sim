#include "SailSave.h"
#include "SailingSim.h"
#include "BenchRunner.h"
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
#include "Serialization/JsonWriter.h"

namespace SailSaveLocal
{
	// The boats' save ids are EBoatType's names: a new boat is appended there and here, never renamed.
	const TCHAR* const BoatIds[] = { TEXT("J22"), TEXT("Sunfish"), TEXT("ILCA7"), TEXT("Catalina22"), TEXT("Catalina30"), TEXT("Hobie16"),
		TEXT("Corsair880"), TEXT("Lagoon42") };
	static_assert(UE_ARRAY_COUNT(BoatIds) == int32(Sailing::EBoatType::Count), "every boat needs a save id");
	const TCHAR* const WorldIds[] = { TEXT("ray-hubbard"), TEXT("galveston-bay"), TEXT("gulf") };
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

	int32 SpotIndexOf(int32 World, const FString& Id)
	{
		if (Id.IsEmpty()) return 0;
		const int32 I = SailCatalog::SpotIds(World).IndexOfByKey(Id);
		if (I < 0) UE_LOG(LogSailing, Warning, TEXT("Save: unknown launch spot \"%s\" in %s, using the first"), *Id, *FSailSave::WorldId(World));
		return FMath::Max(I, 0);
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

FString FSailSave::WorldId(int32 World) { return SailSaveLocal::WorldIds[FMath::Clamp(World, 0, 2)]; }
int32 FSailSave::WorldIndex(const FString& Id) { return SailSaveLocal::IndexOf(SailSaveLocal::WorldIds, 3, Id); }
FString FSailSave::BoatId(int32 Boat) { return SailSaveLocal::BoatIds[FMath::Clamp(Boat, 0, int32(UE_ARRAY_COUNT(SailSaveLocal::BoatIds)) - 1)]; }
int32 FSailSave::BoatIndex(const FString& Id) { return SailSaveLocal::IndexOf(SailSaveLocal::BoatIds, UE_ARRAY_COUNT(SailSaveLocal::BoatIds), Id); }
FString FSailSave::DrillId(int32 Index) { return FLearningContent::DrillId(ESailingDrill(FMath::Clamp(Index + 1, 1, int32(ESailingDrill::Count) - 1))); }
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
	Display->SetNumberField(TEXT("hudScale"), S.HudScale);
	Display->SetNumberField(TEXT("textScale"), S.TextScale);
	Display->SetStringField(TEXT("speedUnits"), S.SpeedUnits);
	Display->SetStringField(TEXT("depthUnits"), S.DepthUnits);
	Display->SetBoolField(TEXT("headingsTrue"), S.bHeadingsTrue);
	Display->SetBoolField(TEXT("autoStart"), S.bAutoStart);
	Display->SetBoolField(TEXT("pauseOnFocusLoss"), S.bPauseOnFocusLoss);
	Set->SetObjectField(TEXT("display"), Display);
	TSharedRef<FJsonObject> Start = Obj();
	Start->SetStringField(TEXT("world"), S.WorldId);
	Start->SetStringField(TEXT("launchSpot"), S.SpotId);
	Start->SetStringField(TEXT("boat"), S.BoatId);
	Start->SetStringField(TEXT("weather"), S.WeatherId);
	Start->SetNumberField(TEXT("startHour"), S.StartHour);
	Start->SetNumberField(TEXT("traffic"), S.Traffic);
	Start->SetNumberField(TEXT("weatherSeed"), S.WeatherSeed);
	Start->SetBoolField(TEXT("gaugeLakeLevel"), S.bGaugeLakeLevel);
	Set->SetObjectField(TEXT("start"), Start);
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
		Sess->SetStringField(TEXT("boat"), L.BoatId);
		Sess->SetStringField(TEXT("mode"), L.ModeId);
		Sess->SetStringField(TEXT("drill"), L.DrillId);
		Sess->SetBoolField(TEXT("learningMode"), L.bLearningMode);
		Sess->SetBoolField(TEXT("easy"), L.bEasy);
		Sess->SetBoolField(TEXT("learningTips"), L.bLearningTips);
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
	Root->SetObjectField(TEXT("progress"), Prog);

	if (Raw.IsValid()) KeepUnknown(*Root, *Raw);

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
		switch (From)
		{
		// case 1: ...; Root.SetNumberField(TEXT("version"), 2); return true;
		default:
			UE_LOG(LogSailing, Error, TEXT("Save: no migration from version %d"), From);
			return false;
		}
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
			Read(*St, TEXT("boat"), S.BoatId);
			Read(*St, TEXT("weather"), S.WeatherId);
			Read(*St, TEXT("startHour"), S.StartHour);
			Read(*St, TEXT("traffic"), S.Traffic);
			Read(*St, TEXT("weatherSeed"), S.WeatherSeed);
			Read(*St, TEXT("gaugeLakeLevel"), S.bGaugeLakeLevel);
		}
		if (const TSharedPtr<FJsonObject> In = Child(*Set, TEXT("input"))) Read(*In, TEXT("bindings"), S.InputBindings);
	}

	if (const TSharedPtr<FJsonObject> Sess = Child(*Root, TEXT("lastSession")))
	{
		Out.bHasLast = true;
		FSession& L = Out.Last;
		Read(*Sess, TEXT("world"), L.WorldId);
		Read(*Sess, TEXT("launchSpot"), L.SpotId);
		Read(*Sess, TEXT("boat"), L.BoatId);
		Read(*Sess, TEXT("mode"), L.ModeId);
		Read(*Sess, TEXT("drill"), L.DrillId);
		Read(*Sess, TEXT("learningMode"), L.bLearningMode);
		Read(*Sess, TEXT("easy"), L.bEasy);
		Read(*Sess, TEXT("learningTips"), L.bLearningTips);
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
	}
	Say(bMigrated ? FString::Printf(TEXT("migrated from version %d"), Version) : FString(TEXT("ok")));
	return bMigrated ? EResult::Migrated : EResult::Ok;
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
	S.HudScale = In.HudScale;
	S.TextScale = In.TextScale;
	S.SpeedUnits = SpeedIds[FMath::Clamp(In.SpeedUnits, 0, 2)];
	S.DepthUnits = DepthIds[FMath::Clamp(In.DepthUnits, 0, 2)];
	S.bHeadingsTrue = In.bHeadingsTrue;
	S.bAutoStart = In.bAutoStart;
	S.bPauseOnFocusLoss = In.bPauseOnFocusLoss;
	S.WorldId = WorldId(In.World);
	S.SpotId = SpotIdOf(FMath::Clamp(In.World, 0, 2), In.LaunchSpot);
	S.BoatId = BoatId(In.BoatType);
	S.WeatherId = EnumId(In.WeatherPreset);
	S.StartHour = In.StartHour;
	S.Traffic = In.TrafficLevel;
	S.WeatherSeed = In.WeatherSeed;
	S.bGaugeLakeLevel = In.bGaugeLakeLevel;

	bHasLast = InSession.bHasLast;
	const FSailSessionConfig& C = InSession.Last;
	FSession& L = Last;
	L.WorldId = WorldId(C.World);
	L.SpotId = SpotIdOf(FMath::Clamp(C.World, 0, 2), C.LaunchSpot);
	L.BoatId = BoatId(C.Boat);
	L.ModeId = EnumId(C.Mode);
	L.DrillId = DrillId(C.DrillIndex);
	L.bLearningMode = C.bLearningMode;
	L.bEasy = C.bEasy;
	L.bLearningTips = C.bLearningTips;
	L.Traffic = C.Traffic;
	L.SavedAt = C.SavedAt;
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
	Out.HudScale = S.HudScale;
	Out.TextScale = S.TextScale;
	Out.SpeedUnits = FMath::Max(IndexOf(SpeedIds, 3, S.SpeedUnits), 0);
	Out.DepthUnits = FMath::Max(IndexOf(DepthIds, 3, S.DepthUnits), 0);
	Out.bHeadingsTrue = S.bHeadingsTrue;
	Out.bAutoStart = S.bAutoStart;
	Out.bPauseOnFocusLoss = S.bPauseOnFocusLoss;
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
	Out.LaunchSpot = SpotIndexOf(Out.World, S.SpotId);
	Out.BoatType = Boat(S.BoatId);
	Out.WeatherPreset = EnumFrom(S.WeatherId, ESailingWeather::AfternoonBreeze, TEXT("weather"));
	Out.StartHour = S.StartHour;
	Out.TrafficLevel = FMath::Clamp(S.Traffic, 0, 2);
	Out.WeatherSeed = S.WeatherSeed;
	Out.bGaugeLakeLevel = S.bGaugeLakeLevel;

	OutSession.bHasLast = bHasLast;
	OutSession.Last = FSailSessionConfig();
	if (bHasLast)
	{
		const FSession& L = Last;
		FSailSessionConfig& C = OutSession.Last;
		C.World = World(L.WorldId);
		C.LaunchSpot = SpotIndexOf(C.World, L.SpotId);
		C.Boat = Boat(L.BoatId);
		C.Mode = EnumFrom(L.ModeId, ESailMode::Free, TEXT("mode"));
		C.DrillIndex = FMath::Max(DrillIndex(L.DrillId), 0);
		C.bLearningMode = L.bLearningMode;
		C.bEasy = L.bEasy;
		C.bLearningTips = L.bLearningTips;
		C.Traffic = FMath::Clamp(L.Traffic, 0, 2);
		C.SavedAt = L.SavedAt;
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
