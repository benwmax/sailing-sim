#include "SailingGameMode.h"
#include "BenchRunner.h"
#include "WindClimate.h"
#include "CoastMarinasActor.h"
#include "SailSession.h"
#include "SailingSim.h"
#include "SailboatPawn.h"
#include "SailingHUD.h"
#include "SailingSettings.h"
#include "WaterSurface.h"
#include "DynamicRHI.h"
#include "HAL/PlatformApplicationMisc.h"
#include "Engine/GameViewportClient.h"
#include "Widgets/SWindow.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "GenericPlatform/GenericPlatformMisc.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "GpuSlices.h"
#include "VisualPipeline.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Scalability.h"
#include "Async/Async.h"
#include "LakeTerrainActor.h"
#include "NavaidsActor.h"
#include "MarinaActor.h"
#include "BridgesActor.h"
#include "LandmarksActor.h"
#include "NightLightsActor.h"
#include "Ocean.h"
#include "TrafficManager.h"
#include "SailingEnvironment.h"
#include "UnrealClient.h"
#include "ShaderCompiler.h"

using namespace Sailing;


ASailingGameMode::ASailingGameMode()
{
	DefaultPawnClass = ASailboatPawn::StaticClass();
	HUDClass = ASailingHUD::StaticClass();
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
}

void ASailingGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	// Bench-fix: bench, capture, shot, demo, drill and automation runs start from the class defaults (the J/22 at Rush
	// Creek), not the player's saved choices; the ini is left as it is.
	USailingSettings::UseRunDefaults();
	// Command-line overrides (benchmarks, recordings) are applied to settings for this run only.
	USailingSettings* Settings = USailingSettings::Get();
	FString Value;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingWorld="), Value))
	{
		// 0 or "Lake", 1 or "Galveston", 2 or "Gulf".
		Settings->World = (Value.StartsWith(TEXT("Gulf"), ESearchCase::IgnoreCase) || Value == TEXT("2")) ? 2
			: ((Value.StartsWith(TEXT("Galv"), ESearchCase::IgnoreCase) || Value == TEXT("1")) ? 1 : 0);
	}
	Lake.Load(FLakeData::DefaultDirectory(), WorldFileName(Settings->World));
	// gulf-swell: Galveston carries the Gulf's ocean too (masked out of the bay); -SailingNoOcean compares without it.
	if (Lake.bOcean && !FParse::Param(FCommandLine::Get(), TEXT("SailingNoOcean")))
	{
		Ocean = MakeShared<FOcean>();
		Waves.SetOcean(std::shared_ptr<FOcean>(Ocean.Get(), [Keep = Ocean](FOcean*) {}));
	}
	// W3: the fetch every way at every point, and the water's depth (about 50 ms). The components' wavenumbers follow the
	// world's median depth (shallow-water dispersion) before anything reads them.
	if (Lake.IsLoaded() && !FParse::Param(FCommandLine::Get(), TEXT("SailingNoSeaMap")))
	{
		const double Start = FPlatformTime::Seconds();
		TSharedPtr<Sailing::FSeaFetch, ESPMode::ThreadSafe> Fetch = MakeShared<Sailing::FSeaFetch, ESPMode::ThreadSafe>();
		Fetch->Build(Lake.Terrain);
		SeaFetch = Fetch;
		Waves.SetDepth(Fetch->GetMedianDepth());
		UE_LOG(LogSailing, Display, TEXT("Sea fetch map: %d x %d cells of %.0f m, median depth %.1f m, built in %.0f ms"),
			Fetch->GetRows(), Fetch->GetCols(), Fetch->GetCell(), Fetch->GetMedianDepth(), (FPlatformTime::Seconds() - Start) * 1000.0);
	}
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingWeather="), Value))
	{
		for (int32 I = 0; I < int32(EWeatherPreset::Count); ++I)
		{
			if (Value.Equals(FString(WeatherPresetName(EWeatherPreset(I))).Replace(TEXT(" "), TEXT("")), ESearchCase::IgnoreCase))
			{
				Settings->WeatherPreset = ESailingWeather(I);
			}
		}
	}
	bRealDayHour = FParse::Value(FCommandLine::Get(), TEXT("SailingHour="), Settings->StartHour);
	FParse::Value(FCommandLine::Get(), TEXT("SailingDay="), RealDayDate);
	FParse::Value(FCommandLine::Get(), TEXT("SailingSeed="), Settings->WeatherSeed);
	FParse::Value(FCommandLine::Get(), TEXT("SailingWind="), WindOverrideKnots);
	FParse::Value(FCommandLine::Get(), TEXT("SailingLaunch="), Settings->LaunchSpot);
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingLakeLevel="), Value))
	{
		Settings->bGaugeLakeLevel = Value.Equals(TEXT("gauge"), ESearchCase::IgnoreCase);
	}
	if (Settings->bGaugeLakeLevel)
	{
		Lake.Terrain.SetLevelBelowPool(FMath::Max(0.0, (Lake.PoolFeet - Lake.LevelFeet) * 0.3048));
	}
	// Graphics G4: a session started from the front end (SailSession.h): its weather, date and lake level. The
	// command line still wins (benchmarks pass their own conditions).
	if (const USailSessionSubsystem* Session = USailSessionSubsystem::Get(this); Session && Session->bHasActive)
	{
		const FSailConditions& C = Session->Active.Conditions;
		if (!C.RealDay.IsEmpty() && RealDayDate.IsEmpty())
		{
			// W5b: a real day brings its own wind; its start hour is the session's.
			RealDayDate = C.RealDay;
			bRealDayHour = true;
		}
		else if (C.RealDay.IsEmpty())
		{
			if (!FParse::Value(FCommandLine::Get(), TEXT("SailingWind="), Value)) WindOverrideKnots = FMath::Max(C.WindKn, 0.5f);
			WindFromOverride = C.WindFromDeg;
			GustOverride = FMath::Clamp(C.GustKn / FMath::Max(C.WindKn, 1.f) - 1.f, 0.f, 1.f);
		}
		SessionDate = FDateTime(FDateTime::Now().GetYear(), FMath::Clamp(C.Month, 1, 12), FMath::Clamp(C.Day, 1, FDateTime::DaysInMonth(FDateTime::Now().GetYear(), FMath::Clamp(C.Month, 1, 12))));
		bSessionDate = true;
		if (!Lake.IsTidal() && FMath::Abs(C.LakeLevelFt) > 0.01f)
		{
			Lake.Terrain.SetLevelBelowPool(-C.LakeLevelFt * 0.3048);   // above the pool raises the water: the shore drops by as much
		}
	}
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingQuality="), Value))
	{
		Settings->Quality = Value.Equals(TEXT("Low"), ESearchCase::IgnoreCase) ? ESailingQuality::Low
			: (Value.Equals(TEXT("Medium"), ESearchCase::IgnoreCase) ? ESailingQuality::Medium
			: (Value.Equals(TEXT("Ultra"), ESearchCase::IgnoreCase) ? ESailingQuality::Ultra : ESailingQuality::High));
	}
}

double ASailingGameMode::GetSimTime() const
{
	if (const UWorld* World = GetWorld())
	{
		if (const APlayerController* PC = World->GetFirstPlayerController())
		{
			if (const ASailboatPawn* Boat = Cast<ASailboatPawn>(PC->GetPawn()))
			{
				return Boat->GetBoatModel().GetState().Time;
			}
		}
	}
	return OwnClock;
}

const TCHAR* ASailingGameMode::WorldFileName(int32 World)
{
	return World == 2 ? TEXT("GulfPassage") : (World == 1 ? TEXT("GalvestonBay") : TEXT("RayHubbard"));
}

const TCHAR* ASailingGameMode::WorldDisplayName(int32 World)
{
	return World == 2 ? TEXT("Gulf passage (Galveston to Freeport)") : (World == 1 ? TEXT("Galveston Bay (Clear Lake, Kemah)") : TEXT("Lake Ray Hubbard (Rush Creek YC)"));
}

double ASailingGameMode::GetLocalHour() const
{
	const double Local = GetUnixTime() + UtcOffsetHours * 3600.0;
	double Hours = FMath::Fmod(Local / 3600.0, 24.0);
	return Hours < 0.0 ? Hours + 24.0 : Hours;
}

const FChartData& ASailingGameMode::GetChart() const
{
	if (!bChartTried && Lake.IsTidal())
	{
		bChartTried = true;
		Chart.Load(FLakeData::DefaultDirectory() / (Lake.FileName + TEXT(".chart.json")));
	}
	return Chart;
}

bool ASailingGameMode::IsDark() const
{
	static SailingArgs::FCachedFlag LightsOnArg(TEXT("SailingLightsOn")); // screenshots, debugging
	const bool bForceOn = LightsOnArg.Get();
	double Elevation = 0.0, Azimuth = 0.0;
	ASailingEnvironment::SunPosition(WeatherState.HourOfDay, DayOfYear, Lake.Latitude, Lake.Longitude, UtcOffsetHours, Elevation, Azimuth);
	return bForceOn || Elevation < -1.0 || WeatherState.VisibilityKm < 2.0;
}

void ASailingGameMode::UpdateTide()
{
	if (!Lake.IsTidal()) return;
	// The water level at the boat: the terrain (and everything on it) moves down as the tide rises, so the water
	// surface stays at zero; the physics sees the same bed through the terrain's level offset.
	double X = 0.0, Y = 0.0;
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (const APawn* P = PC->GetPawn())
		{
			X = P->GetActorLocation().X / CmPerMeter;
			Y = P->GetActorLocation().Y / CmPerMeter;
		}
	}
	TideHeight = Lake.Tides.HeightAt(X, Y, GetUnixTime());
	if (FMath::Abs(GetUnixTime() - NextTideUpdate) > 60.0)
	{
		NextTideUpdate = GetUnixTime();
		bHasNextTide = Lake.Tides.NextExtreme(X, Y, GetUnixTime(), NextTide);
	}
	Lake.Terrain.SetLevelBelowPool(-TideHeight);
	if (!TerrainActor.IsValid())
	{
		for (TActorIterator<ALakeTerrainActor> It(GetWorld()); It; ++It) TerrainActor = *It;
	}
	if (TerrainActor.IsValid())
	{
		// In 2 cm steps, like the rest of the world kit: moving the actor re-uploads every instance under it (the shore's
		// reeds, houses and docks, some 300,000 on Galveston Bay), and doing that each frame cost the render thread 20 ms.
		const double Shown = FMath::RoundToDouble(TideHeight / 0.02) * 0.02;
		const FVector At(0.0, 0.0, -Shown * CmPerMeter);
		if (!TerrainActor->GetActorLocation().Equals(At, 0.1)) TerrainActor->SetActorLocation(At);
	}
}

bool ASailingGameMode::GetLaunchSpot(FLaunchSpot& Out) const
{
	if (NearShipStart) { Out = *NearShipStart; return true; }
	// -SailingStartAt=<north m>,<east m>,<heading deg> overrides (tests, screenshots).
	FString At;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingStartAt="), At, false))
	{
		TArray<FString> Parts;
		At.ParseIntoArray(Parts, TEXT(","));
		if (Parts.Num() >= 3)
		{
			Out = { TEXT("Command line"), FCString::Atod(*Parts[0]), FCString::Atod(*Parts[1]), FCString::Atod(*Parts[2]) };
			return true;
		}
	}
	if (Lake.LaunchSpots.Num() == 0) return false;
	Out = Lake.LaunchSpots[FMath::Clamp(USailingSettings::Get()->LaunchSpot, 0, Lake.LaunchSpots.Num() - 1)];
	return true;
}

void ASailingGameMode::UpdateShelter()
{
	if (!Lake.IsLoaded()) return;
	if (bShelterBuilding && PendingShelter.IsReady())
	{
		Shelter = PendingShelter.Get();
		Wind.SetShelter(Shelter.Get());
		bShelterBuilding = false;
	}
	// Rebuild the lee map on a worker thread when the wind has swung more than 8 degrees.
	const double From = WeatherState.Wind.FromDegrees * Sailing::kDegToRad;
	if (!bShelterBuilding && (!Shelter || FMath::Abs(Sailing::WrapAngle(Shelter->GetFromRadians() - From)) > 8.0 * Sailing::kDegToRad))
	{
		bShelterBuilding = true;
		const Sailing::FLakeTerrain* Terrain = &Lake.Terrain;
		// W1: houses shelter the water too (their ridge above the water, their wings' extent).
		if (ShelterObstacles.empty())
		{
			for (const FLakeHouse& H : Lake.Houses)
			{
				Sailing::FShelterObstacle O;
				O.X = H.X;
				O.Y = H.Y;
				O.Top = FMath::Max(Lake.Terrain.HeightAt(H.X, H.Y), 0.15) + FMath::Max(H.Ridge, H.Eave);
				O.Radius = 4.0;
				for (const FLakeHouse::FWing& W : H.Wings) O.Radius = FMath::Max(O.Radius, double(FMath::Max(W.HalfLength, W.HalfWidth)) + FVector2D(W.X - H.X, W.Y - H.Y).Size());
				ShelterObstacles.push_back(O);
			}
		}
		const std::vector<Sailing::FShelterObstacle>* Obstacles = &ShelterObstacles;
		PendingShelter = Async(EAsyncExecution::ThreadPool, [Terrain, From, Obstacles]()
		{
			const double Start = FPlatformTime::Seconds();
			TSharedPtr<Sailing::FShelterMap> Map = MakeShared<Sailing::FShelterMap>();
			Map->Build(*Terrain, From, 40.0, Obstacles);
			UE_LOG(LogSailing, Display, TEXT("Shelter map for wind from %.0f built in %.0f ms"), FMath::RadiansToDegrees(From), (FPlatformTime::Seconds() - Start) * 1000.0);
			return Map;
		});
	}
}

void ASailingGameMode::ApplyConditions(const FSailConditions& C)
{
	// The same weather path as a new session, without the reload: preset by sky, start hour, wind speed, direction, gusts.
	USailingSettings* Settings = USailingSettings::Get();
	Settings->WeatherPreset = ESailingWeather(USailSessionSubsystem::WeatherPresetFor(C.Sky));
	Settings->StartHour = FMath::Clamp(C.LocalHour, 5.f, 22.f);
	RealDayDate = C.RealDay;
	bRealDayHour = true;
	WindOverrideKnots = C.RealDay.IsEmpty() ? FMath::Max(C.WindKn, 0.5f) : 0.f;
	WindFromOverride = C.RealDay.IsEmpty() ? C.WindFromDeg : NAN;
	GustOverride = C.RealDay.IsEmpty() ? FMath::Clamp(C.GustKn / FMath::Max(C.WindKn, 1.f) - 1.f, 0.f, 1.f) : NAN;
	SessionDate = FDateTime(FDateTime::Now().GetYear(), FMath::Clamp(C.Month, 1, 12), 1) + FTimespan::FromDays(FMath::Max(C.Day, 1) - 1);
	bSessionDate = true;
	bWindArgsRead = true;   // the session's values stand
	if (USailSessionSubsystem* Session = USailSessionSubsystem::Get(this)) Session->Active.Conditions = C;
	ApplyWeatherSettings();
}

std::shared_ptr<const FWeatherDay> ASailingGameMode::LoadRealDay(const FString& Date)
{
	TArray<uint8> Bytes;
	const FString Path = FPaths::ProjectContentDir() / TEXT("TerrainData") / TEXT("Weather") / (Date + TEXT(".wxday"));
	if (!FFileHelper::LoadFileToArray(Bytes, *Path, FILEREAD_Silent)) return nullptr;
	auto Day = std::make_shared<FWeatherDay>();
	std::string Error;
	if (!Day->LoadFromMemory(Bytes.GetData(), size_t(Bytes.Num()), &Error))
	{
		UE_LOG(LogSailing, Warning, TEXT("SailingDay: %s: %hs"), *Path, Error.c_str());
		return nullptr;
	}
	return Day;
}

void ASailingGameMode::ApplyWeatherSettings()
{
	const USailingSettings* Settings = USailingSettings::Get();
	float WeatherOffset = 0.f;
	FParse::Value(FCommandLine::Get(), TEXT("SailingWeatherTime="), WeatherOffset);
	WeatherStartTime = GetSimTime() - WeatherOffset;
	// The storm's timeline is set for the boat's start (the gust front reaches it at kFrontArrives); before Visual V5 it
	// was the map origin, so a start away from the club met the front a minute or more early.
	FLaunchSpot Start;
	const bool bStart = GetLaunchSpot(Start);
	// -SailingStormDelay=<s> (stills, Graphics G1): the front reaches the start that much later, so a capture a few seconds
	// in sees the storm still kilometres off (the point it reaches at kFrontArrives moved back up its track, toward 290 deg,
	// where it comes from).
	double StormDelay = 0.0;
	FParse::Value(FCommandLine::Get(), TEXT("SailingStormDelay="), StormDelay);
	const double TrackRad = FMath::DegreesToRadians(290.0);
	const double Shift = FWeatherSystem::StormFrontSpeed() * StormDelay;
	// W5b: a real day replaces the preset (its storm, if any, reaches the start when it reached the lake).
	double StartHour = Settings->StartHour;
	RealDay.reset();
	if (!RealDayDate.IsEmpty() && Settings->World == 0)
	{
		RealDay = LoadRealDay(RealDayDate);
		if (!RealDay) UE_LOG(LogSailing, Warning, TEXT("SailingDay: no baked day %s in Content/TerrainData/Weather"), *RealDayDate);
	}
	if (RealDay)
	{
		if (!bRealDayHour) StartHour = RealDay->StartHour;
		Weather.ConfigureDay(RealDay, uint32(FMath::Max(Settings->WeatherSeed, 1)), StartHour, bStart ? Start.X : 0.0, bStart ? Start.Y : 0.0);
	}
	else
	{
		Weather.Configure(EWeatherPreset(Settings->WeatherPreset), uint32(FMath::Max(Settings->WeatherSeed, 1)), Settings->StartHour,
			(bStart ? Start.X : 0.0) + FMath::Cos(TrackRad) * Shift, (bStart ? Start.Y : 0.0) + FMath::Sin(TrackRad) * Shift);
	}

	// The clock: today's date (or -SailingDate=YYYY-MM-DD) at the start time, in this machine's time zone (Texas).
	FDateTime Date = bSessionDate ? SessionDate : FDateTime::Now();
	FString DateArg;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingDate="), DateArg))
	{
		TArray<FString> Parts;
		DateArg.ParseIntoArray(Parts, TEXT("-"));
		if (Parts.Num() == 3) Date = FDateTime(FCString::Atoi(*Parts[0]), FCString::Atoi(*Parts[1]), FCString::Atoi(*Parts[2]));
	}
	if (RealDay) Date = FDateTime(RealDay->Year(), RealDay->Month(), RealDay->DayOfMonth());
	UtcOffsetHours = FMath::RoundToInt((FDateTime::Now() - FDateTime::UtcNow()).GetTotalHours());
	DayOfYear = Date.GetDayOfYear();
	// W1: the wind's calibration and stability follow the month and the water (the lake, or the bay and the Gulf).
	Weather.SetClimate(Date.GetMonth(), Settings->World != 0);
	ClockBase = GetSimTime() - WeatherOffset;
	StartUnix = Sailing::UnixSecondsUtc(Date.GetYear(), Date.GetMonth(), Date.GetDay(), 0, 0) + (StartHour - UtcOffsetHours) * 3600.0;

	// Scale the preset's wind to an explicit base speed when asked (benchmarks).
	WindScale = 1.0;
	const FWeatherState Now = Weather.Evaluate(WeatherOffset);
	if (WindOverrideKnots > 0.f && Now.Wind.SpeedKnots > 0.1)
	{
		WindScale = WindOverrideKnots / Now.Wind.SpeedKnots;
	}
	UpdateWeather(0.f);
	Waves.SnapToTarget();
}

void ASailingGameMode::ApplyQualitySettings()
{
	const ESailingQuality Quality = USailingSettings::Get()->Quality;
	// Engine scalability: Low = engine Medium (no Lumen), Medium = High, High = Epic. Then the tier's own console
	// variables (VisualPipeline.h: cloud samples, virtual shadow maps, ray tracing, anti-aliasing and resolution).
	Scalability::FQualityLevels Levels = Scalability::GetQualityLevels();
	Levels.SetFromSingleQualityLevel(QualityScalabilityLevel(Quality));
	Levels.GlobalIlluminationQuality = QualityGIScalabilityLevel(Quality);
	FParse::Value(FCommandLine::Get(), TEXT("SailingGI="), Levels.GlobalIlluminationQuality); // measuring
	Scalability::SetQualityLevels(Levels);
	for (const FQualityCVar& C : QualityCVars(Quality))
	{
		if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(C.Name))
		{
			// Hardware ray tracing only where the RHI has it (Metal on Apple silicon M3 and later, SM6).
			const bool bRayTracing = FCString::Strcmp(C.Name, TEXT("r.RayTracing.Enable")) == 0 || FCString::Strcmp(C.Name, TEXT("r.Lumen.HardwareRayTracing")) == 0;
			const float Value = bRayTracing && !GRHISupportsRayTracing ? 0.f : C.Value;
			// Only on a change: toggling ray tracing recreates every render state.
			if (Var->GetFloat() != Value) Var->Set(Value, ECVF_SetByCode);
		}
	}
	// Measuring (Graphics G1): -SailingCloudMode=<r.VolumetricRenderTarget.Mode> -SailingCloudSamples=<view ray max>.
	int32 CloudMode = -1, CloudSamples = 0;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingCloudMode="), CloudMode))
		if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricRenderTarget.Mode"))) Var->Set(CloudMode, ECVF_SetByCode);
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingCloudSamples="), CloudSamples))
		if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"))) Var->Set(float(CloudSamples), ECVF_SetByCode);
	// Measuring (Visual V1): -SailingAA=<0 none, 2 TAA, 4 TSR, 5 SMAA> and -SailingScreenPct=<percent> override the tier.
	int32 AAOverride = -1, PctOverride = -1;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingAA="), AAOverride))
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.AntiAliasingMethod"))->Set(AAOverride, ECVF_SetByCode);
	}
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingScreenPct="), PctOverride))
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->Set(PctOverride, ECVF_SetByCode);
	}
	// Graphics G4: the player's resolution scale (Settings > Graphics) fixes the tier's percentage, governor off.
	else if (USailingSettings::Get()->FixedResolutionScale() > 0)
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->Set(float(USailingSettings::Get()->FixedResolutionScale()), ECVF_SetByCode);
	}
	USailingSettings::Get()->ApplyDisplay();
	int32 LumenHW = -1;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingLumenHW="), LumenHW))
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.RayTracing.Enable"))->Set(LumenHW, ECVF_SetByCode);
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.Lumen.HardwareRayTracing"))->Set(LumenHW, ECVF_SetByCode);
	}
	for (TActorIterator<AWaterSurface> It(GetWorld()); It; ++It)
	{
		It->SetRingCount(Quality == ESailingQuality::Low ? 4 : 5);
		It->SetQualityTier(Quality == ESailingQuality::Low ? 0 : (Quality == ESailingQuality::Medium ? 1 : 2));
	}
	UE_LOG(LogSailing, Display, TEXT("Quality %d: AA %d, screen %d%%, VSM %d, ray tracing supported %d enabled %d, Lumen HW %d, Substrate %d"),
		int32(Quality), IConsoleManager::Get().FindConsoleVariable(TEXT("r.AntiAliasingMethod"))->GetInt(),
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetInt(),
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.Shadow.Virtual.Enable"))->GetInt(), int32(GRHISupportsRayTracing),
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.RayTracing.Enable"))->GetInt(),
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.Lumen.HardwareRayTracing"))->GetInt(),
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.Substrate"))->GetInt());
	for (TActorIterator<ALakeTerrainActor> It(GetWorld()); It; ++It)
	{
		It->SetTreeFraction(Quality == ESailingQuality::Low ? 0.35f : (Quality == ESailingQuality::Medium ? 0.7f : 1.f));
	}
}

void ASailingGameMode::UpdateWeather(float DeltaSeconds)
{
	const bool bEasy = USailingSettings::Get()->Difficulty == ESailingDifficulty::Easy;
	const double Now = GetSimTime();
	WeatherState = Weather.Evaluate(Now - WeatherStartTime);
	WeatherState.Wind.SpeedKnots *= WindScale;
	// Reference captures: the wind of the real clip (direction it blows from, degrees true; gust intensity as a fraction).
	// Graphics G4: or the session's (InitGame); the command line wins.
	if (!bWindArgsRead)
	{
		bWindArgsRead = true;
		FParse::Value(FCommandLine::Get(), TEXT("SailingWindFrom="), WindFromOverride);
		FParse::Value(FCommandLine::Get(), TEXT("SailingGust="), GustOverride);
	}
	if (!FMath::IsNaN(WindFromOverride)) WeatherState.Wind.FromDegrees = WindFromOverride;
	if (!FMath::IsNaN(GustOverride))
	{
		// The override is the gusts over the mean (a gust factor less one): the fine turbulence for that factor, the puffs
		// scaled with it (W1).
		const double Fine = Sailing::GustIntensityForFactor(1.0 + GustOverride);
		const double Scale = WeatherState.Wind.GustIntensity > 1e-6 ? Fine / WeatherState.Wind.GustIntensity : 1.0;
		WeatherState.Wind.GustIntensity = Fine;
		WeatherState.Wind.PuffIntensity = WeatherState.Wind.PuffIntensity >= 0.0 ? WeatherState.Wind.PuffIntensity * FMath::Min(Scale, 3.0) : -1.0;
	}
	if (bEasy)
	{
		WeatherState.Wind.GustIntensity *= 0.5;
		if (WeatherState.Wind.PuffIntensity > 0.0) WeatherState.Wind.PuffIntensity *= 0.5;
		WeatherState.Wind.ShiftDegrees *= 0.5;
		WeatherState.Wind.PersistentShiftDegrees *= 0.5;
	}
	// The weather's own clock starts at zero; the wind field runs on simulation time.
	WeatherState.Front.StartTime += WeatherStartTime;
	WeatherState.Front.DecayStartTime += WeatherStartTime;
	WeatherState.Front.BurstStartTime += WeatherStartTime;
	WeatherState.DayStartHour -= WeatherStartTime / 3600.0; // the radar's clock too (its hour = start + sim time)
	Vec3 BoatPos;
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (const ASailboatPawn* Boat = Cast<ASailboatPawn>(PC->GetPawn()))
		{
			BoatPos = Boat->GetBoatModel().OriginPosition();
		}
	}
	// W1: the wind's patterns drift around the boat; a change of direction turns them about her, not the map origin.
	FWeatherSystem::ApplyToWind(WeatherState, Wind, Now, BoatPos.X, BoatPos.Y);
	// W5b: a storm rains where its core (or the radar's rain) is: the rain and the visibility are the boat's (the water,
	// the deck, the sound and the haze follow them).
	if (WeatherState.bStormRain)
	{
		WeatherState.Rain = WeatherState.RainAt(BoatPos.X, BoatPos.Y, Now);
		// W8: and the storm's gloom is the boat's too (sunshine ahead of the front until the shelf is close).
		if (WeatherState.Front.bActive) WeatherState.LocalizeStorm(BoatPos.X, BoatPos.Y, Now);
		else WeatherState.VisibilityKm = FMath::Lerp(FMath::Max(WeatherState.VisibilityKm, 10.0), 1.5, WeatherState.Rain);
	}

	// The sea follows the mean wind at the boat (including a gust front's outflow once it has passed).
	FWaveParams WaveParams;
	WaveParams.WindSpeedKnots = WeatherState.Wind.SpeedKnots;
	WaveParams.WindFromDegrees = WeatherState.Wind.FromDegrees;
	// On the lake, fetch is the open water upwind of the boat, to the real shore: W3's effective fetch over +/-45 deg of
	// the wind (the chop at a lee shore grows along the lake too).
	if (Lake.IsLoaded())
	{
		const double From = WeatherState.Wind.FromDegrees * kDegToRad;
		if (FMath::Square(BoatPos.X - FetchCacheX) + FMath::Square(BoatPos.Y - FetchCacheY) > 25.0 * 25.0
			|| FMath::Abs(Sailing::WrapAngle(From - FetchCacheFrom)) > 2.0 * kDegToRad)
		{
			FetchCacheX = BoatPos.X;
			FetchCacheY = BoatPos.Y;
			FetchCacheFrom = From;
			FetchCacheMeters = FMath::Clamp(Lake.Terrain.EffectiveFetch(BoatPos.X, BoatPos.Y, From), 200.0, 15000.0);
		}
		WaveParams.FetchMeters = FetchCacheMeters;
	}
	else
	{
		WaveParams.FetchMeters = WeatherState.FetchMeters;
	}
	UpdateShelter();
	if (WeatherState.Front.bActive && WeatherState.Front.DistanceAhead(BoatPos.X, BoatPos.Y, Now) < 0.0 && Now < WeatherState.Front.DecayStartTime)
	{
		WaveParams.WindSpeedKnots = WeatherState.Front.OutflowKnots;
		WaveParams.WindFromDegrees = WeatherState.Front.OutflowFromDegrees;
	}
	if (Ocean)
	{
		// Offshore the wind sea and swell are the FFT ocean's; the chop components only make the sheltered water's.
		if (Ocean->MaskAt(BoatPos.X, BoatPos.Y) > 0.5) WaveParams.FetchMeters = 200.0;
		UpdateOcean(WaveParams.WindSpeedKnots, WaveParams.WindFromDegrees);
	}
	UpdateSeaMap(WaveParams.WindSpeedKnots, WaveParams.WindFromDegrees);
	Waves.SetWind(WaveParams);
	// Ripples and chop follow a puff within seconds, the longest lake waves over minutes (FWaveField::GrowthSeconds).
	Waves.Update(DeltaSeconds);
}

void ASailingGameMode::UpdateSeaMap(double Knots, double FromDegrees)
{
	if (!SeaFetch) return;
	if (bSeaMapBuilding && PendingSeaMap.IsReady())
	{
		Waves.SetSeaMap(PendingSeaMap.Get());
		bSeaMapBuilding = false;
	}
	// The map's ratios depend on the wind's speed (the growth laws' spectrum against fetch) and, through the components'
	// fetch directions pulled toward it, its direction. The first one is built here (the start snaps to it).
	const bool bFirst = Waves.GetSeaMap() == nullptr && !bSeaMapBuilding;
	const bool bStale = FMath::Abs(Knots - SeaMapKnots) > 0.05 * FMath::Max(SeaMapKnots, 2.0)
		|| FMath::Abs(Sailing::WrapAngle((FromDegrees - SeaMapFrom) * kDegToRad)) > 11.25 * kDegToRad;
	if (bSeaMapBuilding || (!bFirst && !bStale)) return;
	SeaMapKnots = Knots;
	SeaMapFrom = FromDegrees;
	// The open sea's mask, copied: the FFT ocean carries the wind sea there and the chop keeps a 200 m fetch.
	TSharedPtr<FOcean::FMask, ESPMode::ThreadSafe> Mask;
	if (Ocean && Ocean->GetMask().Rows > 0) Mask = MakeShared<FOcean::FMask, ESPMode::ThreadSafe>(Ocean->GetMask());
	TArray<FWaveComponent> Components(Waves.GetComponents(), kWaveComponents);
	auto Build = [Fetch = SeaFetch, Mask, Components = MoveTemp(Components), Knots, FromDegrees]() -> std::shared_ptr<const Sailing::FSeaMap>
	{
		const double Start = FPlatformTime::Seconds();
		std::function<double(double, double)> OpenSea;
		if (Mask)
		{
			OpenSea = [Mask](double X, double Y)
			{
				// Nearest cell is enough for a 0.5 threshold; beyond the charts is open sea (FOcean::MaskAt).
				const int R = FMath::RoundToInt((X - Mask->X0) / Mask->Cell), C = FMath::RoundToInt((Y - Mask->Y0) / Mask->Cell);
				if (R < 0 || C < 0 || R >= Mask->Rows || C >= Mask->Cols) return 1.0;
				return double(Mask->Values[size_t(R) * Mask->Cols + C]);
			};
		}
		auto Map = std::make_shared<Sailing::FSeaMap>();
		Map->Build(*Fetch, Components.GetData(), Knots * kKnot, FromDegrees * kDegToRad + kPi, true, Sailing::kSeaTowardWind, OpenSea);
		UE_LOG(LogSailing, Verbose, TEXT("Sea map for %.1f kn from %.0f built in %.0f ms"), Knots, FromDegrees, (FPlatformTime::Seconds() - Start) * 1000.0);
		return Map;
	};
	if (bFirst)
	{
		Waves.SetSeaMap(Build());
		return;
	}
	bSeaMapBuilding = true;
	PendingSeaMap = Async(EAsyncExecution::ThreadPool, MoveTemp(Build));
}

void ASailingGameMode::UpdateOcean(double WindKnots, double WindFromDeg)
{
	// The Gulf's swell by the day's weather: it runs in from the southeast, longer and higher ahead of a front.
	FOceanParams P = Ocean->GetParams();
	P.WindMs = WindKnots * kKnot;
	P.WindFromRad = WindFromDeg * kDegToRad;
	switch (Weather.GetPreset())
	{
	case EWeatherPreset::CalmMorning: P.SwellHs = 0.5; P.SwellTp = 8.0; break;
	case EWeatherPreset::Overcast: P.SwellHs = 1.2; P.SwellTp = 9.0; break;
	case EWeatherPreset::Rain: P.SwellHs = 1.0; P.SwellTp = 8.0; break;
	case EWeatherPreset::Thunderstorm: P.SwellHs = 1.4; P.SwellTp = 8.0; break;
	default: P.SwellHs = 0.9; P.SwellTp = 9.0; break;
	}
	float SwellArg = 0.f;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingSwell="), SwellArg)) P.SwellHs = SwellArg;
	P.SwellFromRad = 135.0 * kDegToRad;
	const FOceanParams& Old = Ocean->GetParams();
	const bool bChanged = !bOceanConfigured || FMath::Abs(P.WindMs - Old.WindMs) > 0.4 || FMath::Abs(FMath::UnwindRadians(P.WindFromRad - Old.WindFromRad)) > 0.1
		|| P.SwellHs != Old.SwellHs || P.SwellTp != Old.SwellTp;
	if (!bChanged) return;
	const double OldHs = Ocean->SignificantHeight();
	Ocean->Configure(P);
	// The depth limit depends on the wave height: rebuild the mask when it has changed noticeably.
	if (!bOceanConfigured || FMath::Abs(Ocean->SignificantHeight() - OldHs) > 0.15 * OldHs) Ocean->BuildMask(Lake.Terrain);
	bOceanConfigured = true;
}

void ASailingGameMode::StartPlay()
{
	// Weather first: the boat reads the wind when it is spawned during Super::StartPlay.
	ApplyQualitySettings();
	ApplyWeatherSettings();
	Super::StartPlay();
	if (Lake.Navaids.Num() > 0)
	{
		GetWorld()->SpawnActor<ANavaidsActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	}
	if (Lake.Marina.IsLoaded() && !FParse::Param(FCommandLine::Get(), TEXT("SailingNoMarina")))
	{
		GetWorld()->SpawnActor<AMarinaActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	}
	// Graphics G7: the coast's moored boats and floating walkways (Inputs/g2/piers, <Lake>.piers).
	if (Lake.MooredBoats.Num() > 0 && USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ACoastMarinasActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	}
	if ((Lake.Bridges.Num() > 0 || Lake.Docks.Num() > 0) && USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ABridgesActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	}
	if (Lake.Landmarks.Num() > 0 && USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ALandmarksActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	}
	if (USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ANightLightsActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	}
	// Other vessels and races. -SailingTraffic=0|1|2 overrides the setting; -SailingRace=<seconds to the start>.
	int32 TrafficArg = 0;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingTraffic="), TrafficArg)) USailingSettings::Get()->TrafficLevel = FMath::Clamp(TrafficArg, 0, 2);
	GetWorld()->SpawnActor<ATrafficManager>(FVector::ZeroVector, FRotator::ZeroRotator);

	if (FParse::Value(FCommandLine::Get(), TEXT("SailingBench="), BenchSeconds) && BenchSeconds > 0.f)
	{
		// Bench-fast: -SailingBenchWarmup=<s> (3 by default); -SailingBenchTrace keeps every frame from the start
		// (Saved/Bench/<shot>.frames.csv) to see where the frames settle.
		FParse::Value(FCommandLine::Get(), TEXT("SailingBenchWarmup="), BenchWarmup);
		bBenchTrace = FParse::Param(FCommandLine::Get(), TEXT("SailingBenchTrace"));
		UE_LOG(LogSailing, Display, TEXT("SailingBench: measuring %.1f s after %.1f s warm-up"), BenchSeconds, BenchWarmup);
		FrameTimes.Reserve(FMath::CeilToInt(BenchSeconds * 240.f));
		FParse::Value(FCommandLine::Get(), TEXT("SailingRecord="), RecordSeconds);
		FParse::Value(FCommandLine::Get(), TEXT("SailingRecordInterval="), RecordInterval);
		FParse::Value(FCommandLine::Get(), TEXT("SailingShot="), ShotName);
		NextFrameTime = BenchWarmup;
		// Graphics G4: a bench of the pause menu still ends (and takes its screenshot) while the game is paused.
		SetTickableWhenPaused(true);
		// Bench-fast: macOS throttles a window it hides. A single run is brought to the front by `open`; a bench list
		// keeps one window for many views, so each view brings it forward again (bench.json "foreground" says if it
		// stayed there).
#if PLATFORM_MAC
		FPlatformApplicationMisc::ActivateApplication();   // (Mac only; on Windows BringToFront below is enough)
#endif
		if (GEngine && GEngine->GameViewport && GEngine->GameViewport->GetWindow().IsValid()) GEngine->GameViewport->GetWindow()->BringToFront(true);
	}
}

void ASailingGameMode::UpdateResolutionGovernor(float DeltaSeconds)
{
	// Visual V7: High renders at native resolution, but where a view is heavier than 45 fps allows (Bean's slip at Rush
	// Creek: a hundred berthed boats, leaf-card trees and Lumen's reflections of them), the resolution steps down, at most
	// to 82% (TAA upsamples it back), and climbs back when there is headroom. Not in the capture mode (comparable stills)
	// or when -SailingScreenPct fixes it.
	static uint32 FixedGen = MAX_uint32;
	static bool bFixed = false;
	if (FixedGen != SailingArgs::Generation())
	{
		FixedGen = SailingArgs::Generation();
		bFixed = FParse::Param(FCommandLine::Get(), TEXT("SailingScreenPct")) || FCommandLine::Get() && FCString::Strifind(FCommandLine::Get(), TEXT("SailingScreenPct=")) != nullptr
		|| FCString::Strifind(FCommandLine::Get(), TEXT("SailingCapture=")) != nullptr;
	}
	if (USailingSettings::Get()->FixedResolutionScale() > 0) return;   // the player fixed it
	if (bFixed || USailingSettings::Get()->Quality != ESailingQuality::High || DeltaSeconds <= 0.f || DeltaSeconds > 0.25f) return;
	GovernorMs += (DeltaSeconds * 1000.f - GovernorMs) * FMath::Clamp(DeltaSeconds / 0.5f, 0.f, 1.f);
	GovernorClock += DeltaSeconds;
	if (GovernorClock < 0.5f) return;
	GovernorClock = 0.f;
	IConsoleVariable* Pct = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"));
	const float Now = Pct->GetFloat();
	float Next = Now;
	if (GovernorMs > 21.6f) Next = FMath::Max(82.f, Now - 3.f);      // over 46 fps' budget: step down
	else if (GovernorMs < 18.5f) Next = FMath::Min(100.f, Now + 2.f); // headroom: step back up
	if (Next != Now) Pct->Set(Next, ECVF_SetByCode);
}

float ASailingGameMode::GetRenderScale() const
{
	return IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetFloat();
}

void ASailingGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!GetWorld()->IsPaused())
	{
		OwnClock += DeltaSeconds;
		UpdateWeather(DeltaSeconds);
		UpdateTide();
		UpdateResolutionGovernor(DeltaSeconds);
	}

	if (BenchSeconds <= 0.f || bBenchDone)
	{
		return;
	}

#if WITH_EDITOR
	// Graphics G6: uncooked runs (run-game.sh, capture-scenes.sh) compile shaders on demand and draw a material's default
	// until it is ready: a still once showed a storm sky with no clouds. Finish the compiling before the measured window.
	if (Elapsed < BenchWarmup && GShaderCompilingManager && GShaderCompilingManager->GetNumRemainingJobs() > 0)
	{
		GShaderCompilingManager->FinishAllCompilation();
	}
#endif
	Elapsed += DeltaSeconds;
	if (bBenchTrace) TraceTimes.Emplace(Elapsed, static_cast<float>(FApp::GetDeltaTime() * 1000.0));
	if (Elapsed > BenchWarmup && Elapsed <= BenchWarmup + BenchSeconds)
	{
		if (ClothSecondsAtStart < 0.0) ClothSecondsAtStart = ASailboatPawn::ClothCpuSeconds;
		if (WaterSecondsAtStart < 0.0) WaterSecondsAtStart = AWaterSurface::WaterCpuSeconds;
		if (WindMapSecondsAtStart < 0.0) WindMapSecondsAtStart = AWaterSurface::WindMapCpuSeconds;
		if (!bSlicesStarted) { bSlicesStarted = true; FMemory::Memcpy(SlicesAtStart, SailingPerf::GSliceSeconds, sizeof(SlicesAtStart)); }
		// (The thread times read here are the previous frame's, all of them inside the window but the first.)
		ThreadTimes.Sample();
		FMemory::Memcpy(SlicesAtEnd, SailingPerf::GSliceSeconds, sizeof(SlicesAtEnd));
		// Real wall-clock frame time, not the (possibly clamped) game delta.
		FrameTimes.Add(static_cast<float>(FApp::GetDeltaTime()));
		ForegroundFrames += FPlatformApplicationMisc::IsThisApplicationForeground() ? 1 : 0;
	}

	if (RecordSeconds > 0.f && Elapsed >= NextFrameTime && Elapsed < BenchWarmup + RecordSeconds)
	{
		const FString FramePath = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/rec/frame_%04d.png"), FrameIndex++));
		FScreenshotRequest::RequestScreenshot(FramePath, /*bShowUI*/ true, /*bAddFilenameSuffix*/ false);
		NextFrameTime += RecordInterval;
	}

	// -SailingProfileGPU: dump one frame's GPU timings to the log (for tuning quality tiers).
	static SailingArgs::FOnce Profiled;
	if (!Profiled.Taken() && Elapsed > BenchWarmup + 3.f && FParse::Param(FCommandLine::Get(), TEXT("SailingProfileGPU")))
	{
		Profiled.Take();
		GEngine->Exec(GetWorld(), TEXT("ProfileGPU"));
	}

	const float End = BenchWarmup + BenchSeconds;
	if (!bScreenshotRequested && Elapsed > End - 1.f)
	{
		const FString ShotPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/%s.png"), *ShotName));
		FScreenshotRequest::RequestScreenshot(ShotPath, /*bShowUI*/ true, /*bAddFilenameSuffix*/ false);
		bScreenshotRequested = true;
	}
	// Visual V1: after the measured window, profile three frames on the GPU (their frame times are not counted) and
	// sum their passes into the plan's budget slices. -SailingNoGpuSlices skips it.
	static SailingArgs::FCachedFlag NoGpuSlicesArg(TEXT("SailingNoGpuSlices"));
	const bool bGpuSlices = !NoGpuSlicesArg.Get();
	const float ProfileTimes[] = { 0.3f, 0.9f, 1.5f };
	if (bGpuSlices && Elapsed > End && Elapsed <= End + 2.4f)
	{
		if (!GpuCapture.IsValid())
		{
			GpuCapture = MakeShared<FGpuProfileCapture>();
			GLog->AddOutputDevice(GpuCapture.Get());
		}
		if (GpuProfilesRequested < UE_ARRAY_COUNT(ProfileTimes) && Elapsed > End + ProfileTimes[GpuProfilesRequested])
		{
			++GpuProfilesRequested;
			GEngine->Exec(GetWorld(), TEXT("ProfileGPU"));
		}
		return;
	}
	if (Elapsed > End)
	{
		FinishGpuSlices();
		FinishBenchmark();
	}
}

void ASailingGameMode::FinishGpuSlices()
{
	if (!GpuCapture.IsValid())
	{
		return;
	}
	GLog->RemoveOutputDevice(GpuCapture.Get());
	FGpuSlices Sum;
	for (const TArray<FString>& Dump : GpuCapture->Take())
	{
		FGpuSlices Frame;
		if (ParseProfileGpu(Dump, Frame)) Sum.Accumulate(Frame);
	}
	if (Sum.Frames > 0)
	{
		GpuSlicesJson = Sum.Average().ToJsonField();
	}
	GpuCapture.Reset();
}

void ASailingGameMode::FinishBenchmark()
{
	bBenchDone = true;

	TArray<float> Sorted = FrameTimes;
	Sorted.Sort();
	const int32 N = Sorted.Num();
	double Total = 0.0;
	for (float T : Sorted)
	{
		Total += T;
	}
	const double AvgMs = N > 0 ? Total / N * 1000.0 : 0.0;
	const double AvgFps = Total > 0.0 ? N / Total : 0.0;
	const double P99Ms = N > 0 ? Sorted[FMath::Min(N - 1, FMath::FloorToInt(N * 0.99))] * 1000.0 : 0.0;
	const double MaxMs = N > 0 ? Sorted.Last() * 1000.0 : 0.0;
	const USailingSettings* Settings = USailingSettings::Get();

	FString Summary = FString::Printf(
		TEXT("{\"frames\":%d,\"seconds\":%.2f,\"avg_fps\":%.1f,\"avg_ms\":%.2f,\"p99_ms\":%.2f,\"max_ms\":%.2f,\"rhi\":\"%s\",\"resolution\":\"%dx%d\",\"quality\":\"%s\",\"weather\":\"%hs\",\"hour\":%.1f}"),
		N, Total, AvgFps, AvgMs, P99Ms, MaxMs, GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"),
		GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport ? GEngine->GameViewport->Viewport->GetSizeXY().X : 0,
		GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport ? GEngine->GameViewport->Viewport->GetSizeXY().Y : 0,
		Settings->Quality == ESailingQuality::Low ? TEXT("Low") : (Settings->Quality == ESailingQuality::Medium ? TEXT("Medium")
			: (Settings->Quality == ESailingQuality::High ? TEXT("High") : TEXT("Ultra"))),
		RealDay ? RealDay->Date.c_str() : WeatherPresetName(EWeatherPreset(Settings->WeatherPreset)), WeatherState.HourOfDay);
	// Visual V3: sail cloth simulation on the CPU, all boats, per frame of the measured window.
	if (N > 0 && ClothSecondsAtStart >= 0.0)
	{
		Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"cloth_cpu_ms\":%.3f}"), (ASailboatPawn::ClothCpuSeconds - ClothSecondsAtStart) * 1000.0 / N);
	}
	// Visual V4: the water's game-thread work (FFT frames blended and uploaded, the wake grid stepped).
	if (N > 0 && WaterSecondsAtStart >= 0.0)
	{
		Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"water_cpu_ms\":%.3f}"), (AWaterSurface::WaterCpuSeconds - WaterSecondsAtStart) * 1000.0 / N);
		Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"windmap_cpu_ms\":%.3f}"), (AWaterSurface::WindMapCpuSeconds - WindMapSecondsAtStart) * 1000.0 / N);
	}
	// Perf 1: the threads' own times (game thread without its waits) and the game thread's named slices.
	if (const FString Threads = ThreadTimes.JsonFields(); !Threads.IsEmpty())
	{
		Summary = Summary.LeftChop(1) + TEXT(",") + Threads + TEXT(",\"gt\":") + SailingPerf::SlicesJson(SlicesAtStart, SlicesAtEnd, N) + TEXT("}");
	}
	if (!GpuSlicesJson.IsEmpty())
	{
		Summary = Summary.LeftChop(1) + TEXT(",") + GpuSlicesJson + TEXT("}");
	}
	// Visual V7: the render resolution at the end of the window (High's governor may have lowered it).
	Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"render_pct\":%.0f}"), GetRenderScale());
	// Bench-fast: the share of the window's frames with the game in front (below 1, the view may have been throttled).
	Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"foreground\":%.3f}"), N > 0 ? double(ForegroundFrames) / N : 0.0);
	// Bench-fast: the process's memory at the end of the window (a bench list runs many views in one process).
	const FPlatformMemoryStats Mem = FPlatformMemory::GetStats();
	FTextureMemoryStats TexMem;
	RHIGetTextureMemoryStats(TexMem);
	Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"mem_used_mb\":%.0f,\"mem_peak_mb\":%.0f,\"tex_mem_mb\":%.0f}"),
		Mem.UsedPhysical / 1048576.0, Mem.PeakUsedPhysical / 1048576.0, TexMem.StreamingMemorySize / 1048576.0 + TexMem.NonStreamingMemorySize / 1048576.0);

	UE_LOG(LogSailing, Display, TEXT("SailingBench result: %s"), *Summary);
	FFileHelper::SaveStringToFile(Summary, *(FPaths::ProjectSavedDir() / TEXT("Bench/bench.json")));
	if (bBenchTrace)
	{
		FString Csv = TEXT("t_s,frame_ms\n");
		for (const TPair<float, float>& F : TraceTimes) Csv += FString::Printf(TEXT("%.4f,%.3f\n"), F.Key, F.Value);
		FFileHelper::SaveStringToFile(Csv, *(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/%s.frames.csv"), *ShotName)));
	}

	// Bench-fast: in a bench list the runner saves the view's result and loads the next view.
	if (USailingBenchRunner* Runner = USailingBenchRunner::Get(this))
	{
		Runner->ViewFinished(Summary, this);
		return;
	}
	FPlatformMisc::RequestExit(false, TEXT("SailingBench finished"));
}
