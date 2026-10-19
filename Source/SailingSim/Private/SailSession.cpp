#include "SailSession.h"
#include "SailingSettings.h"
#include "SailSave.h"
#include "Engine/GameInstance.h"
#include "Kismet/GameplayStatics.h"

USailSessionSubsystem* USailSessionSubsystem::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	const UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
	return GI ? GI->GetSubsystem<USailSessionSubsystem>() : nullptr;
}

void USailSessionSave::Commit()
{
	if (USailingSettings::IgnoresSavedChoices()) return;   // a measuring run keeps the player's Continue
	SaveConfig();
	SailSaveStore::Commit();
}

void USailSessionSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	SailSaveStore::LoadOnce();
}

const TArray<FSailPreset>& USailSessionSubsystem::Presets()
{
	// The spec's presets (Inputs/g4/ui-spec.md 2.5). Directions are where the wind blows from, true.
	static TArray<FSailPreset> P = []
	{
		TArray<FSailPreset> Out;
		auto Add = [&Out](const TCHAR* Id, const TCHAR* Name, const TCHAR* Summary, float From, float Kn, float Gust, ESailSky Sky, float Hour,
			int32 Month, int32 Day, float Temp, bool bGalveston)
		{
			FSailPreset S;
			S.Id = Id; S.Name = Name; S.Summary = Summary; S.bGalvestonOnly = bGalveston;
			S.Values.WindFromDeg = From; S.Values.WindKn = Kn; S.Values.GustKn = Gust; S.Values.Sky = Sky; S.Values.LocalHour = Hour;
			S.Values.Month = Month; S.Values.Day = Day; S.Values.AirTempF = Temp; S.Values.PresetId = Id;
			Out.Add(S);
		};
		Add(TEXT("Lesson"), TEXT("ASA 101 lesson day"), TEXT("10 kn S · fair · 10:00"), 180.f, 10.f, 13.f, ESailSky::Fair, 10.f, 4, 18, 74.f, false);
		Add(TEXT("July"), TEXT("Typical July afternoon"), TEXT("12 kn SSE · storms after 4 pm"), 170.f, 12.f, 20.f, ESailSky::Storms, 14.5f, 7, 15, 98.f, false);
		Add(TEXT("Glassy"), TEXT("Glassy morning"), TEXT("2 kn · clear, haze · 07:30"), 120.f, 2.f, 4.f, ESailSky::Clear, 7.5f, 8, 9, 79.f, false);
		Add(TEXT("Norther"), TEXT("Blue norther"), TEXT("20 kn N · overcast · cold"), 0.f, 20.f, 28.f, ESailSky::Overcast, 11.f, 11, 22, 48.f, false);
		Add(TEXT("SeaBreeze"), TEXT("Bay sea breeze"), TEXT("14 kn SE · fair · 15:00"), 140.f, 14.f, 18.f, ESailSky::Fair, 15.f, 6, 20, 88.f, true);
		// "Live from today": no station history is bundled, so it is today's date at the hour with a Texas climatological
		// breeze for the month (the summary says so).
		const FDateTime Now = FDateTime::Now();
		static const float MonthWind[12] = { 11, 12, 13, 13, 11, 10, 9, 8, 9, 10, 11, 11 };
		static const float MonthTemp[12] = { 55, 60, 68, 76, 83, 91, 95, 95, 88, 78, 66, 57 };
		Add(TEXT("Today"), TEXT("Live from today"), TEXT("Today's date · average breeze for the month"), Now.GetMonth() >= 10 || Now.GetMonth() <= 3 ? 0.f : 170.f,
			MonthWind[Now.GetMonth() - 1], MonthWind[Now.GetMonth() - 1] + 5.f, ESailSky::Fair, FMath::Clamp(float(Now.GetHour()) + Now.GetMinute() / 60.f, 7.f, 19.f),
			Now.GetMonth(), Now.GetDay(), MonthTemp[Now.GetMonth() - 1], false);
		return Out;
	}();
	return P;
}

void USailSessionSubsystem::ApplyPreset(FSailConditions& Conditions, const FSailPreset& Preset)
{
	const float Level = Conditions.LakeLevelFt;   // the lake level is the player's, not the weather's
	Conditions = Preset.Values;
	Conditions.LakeLevelFt = Level;
}

FSailSessionConfig USailSessionSubsystem::MakeDefault()
{
	FSailSessionConfig C;
	const USailSessionSave* Save = USailSessionSave::Get();
	C.World = Save->bHasLast ? Save->Last.World : USailingSettings::Get()->World;
	if (C.World == 2) C.World = 1;   // the Gulf passage is Galveston's Passage mode
	// The last session's spot and boat (the save file's), on the conditions of a lesson day.
	C.Boat = Save->bHasLast ? Save->Last.Boat : 0;
	C.LaunchSpot = Save->bHasLast && Save->Last.World == C.World ? Save->Last.LaunchSpot : 0;
	ApplyPreset(C.Conditions, Presets()[0]);
	C.bFreeSail = USailingSettings::Get()->IsFreeSail();
	return C;
}

int32 USailSessionSubsystem::WeatherPresetFor(ESailSky Sky)
{
	// Sailing::EWeatherPreset: CalmMorning, AfternoonBreeze, Overcast, Rain, Thunderstorm, RandomDay. Fog has no preset of its
	// own yet: it runs as overcast (the low, grey sky without rain).
	switch (Sky)
	{
	case ESailSky::Clear: return 0;
	case ESailSky::Fair: return 1;
	case ESailSky::Storms: return 4;
	default: return 2;
	}
}

FString USailSessionSubsystem::SkyName(ESailSky Sky)
{
	static const TCHAR* Names[] = { TEXT("Clear"), TEXT("Fair"), TEXT("Overcast"), TEXT("Storms"), TEXT("Fog") };
	return Names[FMath::Clamp(int32(Sky), 0, 4)];
}

FString USailSessionSubsystem::ModeName(ESailMode Mode)
{
	static const TCHAR* Names[] = { TEXT("Free sail"), TEXT("ASA 101 drills"), TEXT("Race"), TEXT("Passage") };
	return Names[FMath::Clamp(int32(Mode), 0, 3)];
}

FString USailSessionSubsystem::CompassPoint(float Degrees)
{
	static const TCHAR* P[] = { TEXT("N"), TEXT("NNE"), TEXT("NE"), TEXT("ENE"), TEXT("E"), TEXT("ESE"), TEXT("SE"), TEXT("SSE"),
		TEXT("S"), TEXT("SSW"), TEXT("SW"), TEXT("WSW"), TEXT("W"), TEXT("WNW"), TEXT("NW"), TEXT("NNW") };
	const int32 I = FMath::RoundToInt(FMath::Fmod(FMath::Fmod(Degrees, 360.f) + 360.f, 360.f) / 22.5f) % 16;
	return P[I];
}

void USailSessionSubsystem::ApplyToSettings(const FSailSessionConfig& Config)
{
	USailingSettings* S = USailingSettings::Get();
	// Passage mode on Galveston sails the Gulf world (the passage to Freeport).
	S->World = Config.Mode == ESailMode::Passage ? 2 : Config.World;
	S->LaunchSpot = Config.LaunchSpot;
	S->BoatType = Config.Boat;
	S->WeatherPreset = ESailingWeather(WeatherPresetFor(Config.Conditions.Sky));
	S->StartHour = FMath::Clamp(Config.Conditions.LocalHour, 5.f, 22.f);
	S->TrafficLevel = FMath::Clamp(Config.Traffic, 0, 2);
	S->Difficulty = Config.bEasy ? ESailingDifficulty::Easy : ESailingDifficulty::Realistic;
	S->bLearningMode = Config.bLearningMode;
	S->bFreeSail = Config.bFreeSail;
	S->Save();
}

void USailSessionSubsystem::ResetForRun()
{
	Pending = FSailSessionConfig();
	Active = FSailSessionConfig();
	bHasActive = false;
	bStarted = false;
	UIScript.Reset();
	bUIScriptRead = false;
}

void USailSessionSubsystem::StartSession(const FSailSessionConfig& Config, UObject* WorldContext)
{
	Active = Config;
	Active.SavedAt = FDateTime::Now();
	bHasActive = true;
	bStarted = false;
	USailSessionSave* Save = USailSessionSave::Get();
	Save->bHasLast = true;
	Save->Last = Active;
	Save->Commit();
	ApplyToSettings(Active);
	if (WorldContext)
	{
		UGameplayStatics::OpenLevel(WorldContext, FName(*UGameplayStatics::GetCurrentLevelName(WorldContext)));
	}
}
