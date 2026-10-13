#include "SailingGameMode.h"
#include "SailingSim.h"
#include "SailboatPawn.h"
#include "SailingHUD.h"
#include "SailingSettings.h"
#include "WaterSurface.h"
#include "DynamicRHI.h"
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

using namespace Sailing;

namespace
{
	constexpr float BenchWarmupSeconds = 3.f;
}

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
	if (Lake.bOcean)
	{
		Ocean = MakeShared<FOcean>();
		Waves.SetOcean(std::shared_ptr<FOcean>(Ocean.Get(), [Keep = Ocean](FOcean*) {}));
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
	FParse::Value(FCommandLine::Get(), TEXT("SailingHour="), Settings->StartHour);
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
	static const bool bForceOn = FParse::Param(FCommandLine::Get(), TEXT("SailingLightsOn")); // screenshots, debugging
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
		TerrainActor->SetActorLocation(FVector(0.0, 0.0, -TideHeight * CmPerMeter));
	}
}

bool ASailingGameMode::GetLaunchSpot(FLaunchSpot& Out) const
{
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
		PendingShelter = Async(EAsyncExecution::ThreadPool, [Terrain, From]()
		{
			const double Start = FPlatformTime::Seconds();
			TSharedPtr<Sailing::FShelterMap> Map = MakeShared<Sailing::FShelterMap>();
			Map->Build(*Terrain, From);
			UE_LOG(LogSailing, Display, TEXT("Shelter map for wind from %.0f built in %.0f ms"), FMath::RadiansToDegrees(From), (FPlatformTime::Seconds() - Start) * 1000.0);
			return Map;
		});
	}
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
	Weather.Configure(EWeatherPreset(Settings->WeatherPreset), uint32(FMath::Max(Settings->WeatherSeed, 1)), Settings->StartHour,
		bStart ? Start.X : 0.0, bStart ? Start.Y : 0.0);

	// The clock: today's date (or -SailingDate=YYYY-MM-DD) at the start time, in this machine's time zone (Texas).
	FDateTime Date = FDateTime::Now();
	FString DateArg;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingDate="), DateArg))
	{
		TArray<FString> Parts;
		DateArg.ParseIntoArray(Parts, TEXT("-"));
		if (Parts.Num() == 3) Date = FDateTime(FCString::Atoi(*Parts[0]), FCString::Atoi(*Parts[1]), FCString::Atoi(*Parts[2]));
	}
	UtcOffsetHours = FMath::RoundToInt((FDateTime::Now() - FDateTime::UtcNow()).GetTotalHours());
	DayOfYear = Date.GetDayOfYear();
	ClockBase = GetSimTime() - WeatherOffset;
	StartUnix = Sailing::UnixSecondsUtc(Date.GetYear(), Date.GetMonth(), Date.GetDay(), 0, 0) + (double(Settings->StartHour) - UtcOffsetHours) * 3600.0;

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
	static float WindFromArg = NAN, GustArg = NAN;
	static bool bWindArgsRead = false;
	if (!bWindArgsRead)
	{
		bWindArgsRead = true;
		FParse::Value(FCommandLine::Get(), TEXT("SailingWindFrom="), WindFromArg);
		FParse::Value(FCommandLine::Get(), TEXT("SailingGust="), GustArg);
	}
	if (!FMath::IsNaN(WindFromArg)) WeatherState.Wind.FromDegrees = WindFromArg;
	if (!FMath::IsNaN(GustArg)) WeatherState.Wind.GustIntensity = GustArg;
	if (bEasy)
	{
		WeatherState.Wind.GustIntensity *= 0.5;
		WeatherState.Wind.ShiftDegrees *= 0.5;
	}
	// The weather's own clock starts at zero; the wind field runs on simulation time.
	WeatherState.Front.StartTime += WeatherStartTime;
	WeatherState.Front.DecayStartTime += WeatherStartTime;
	FWeatherSystem::ApplyToWind(WeatherState, Wind, Now);

	// The sea follows the mean wind at the boat (including a gust front's outflow once it has passed).
	Vec3 BoatPos;
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (const ASailboatPawn* Boat = Cast<ASailboatPawn>(PC->GetPawn()))
		{
			BoatPos = Boat->GetBoatModel().OriginPosition();
		}
	}
	FWaveParams WaveParams;
	WaveParams.WindSpeedKnots = WeatherState.Wind.SpeedKnots;
	WaveParams.WindFromDegrees = WeatherState.Wind.FromDegrees;
	// On the lake, fetch is the open water upwind of the boat, to the real shore.
	WaveParams.FetchMeters = Lake.IsLoaded()
		? FMath::Clamp(Lake.Terrain.FetchToward(BoatPos.X, BoatPos.Y, WeatherState.Wind.FromDegrees * kDegToRad), 200.0, 15000.0)
		: WeatherState.FetchMeters;
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
	Waves.SetWind(WaveParams);
	// Short-fetch chop builds within a minute or two.
	Waves.Update(DeltaSeconds, 40.0);
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
		UE_LOG(LogSailing, Display, TEXT("SailingBench: measuring %.1f s after %.1f s warm-up"), BenchSeconds, BenchWarmupSeconds);
		FrameTimes.Reserve(FMath::CeilToInt(BenchSeconds * 240.f));
		FParse::Value(FCommandLine::Get(), TEXT("SailingRecord="), RecordSeconds);
		FParse::Value(FCommandLine::Get(), TEXT("SailingRecordInterval="), RecordInterval);
		FParse::Value(FCommandLine::Get(), TEXT("SailingShot="), ShotName);
		NextFrameTime = BenchWarmupSeconds;
	}
}

void ASailingGameMode::UpdateResolutionGovernor(float DeltaSeconds)
{
	// Visual V7: High renders at native resolution, but where a view is heavier than 45 fps allows (Bean's slip at Rush
	// Creek: a hundred berthed boats, leaf-card trees and Lumen's reflections of them), the resolution steps down, at most
	// to 82% (TAA upsamples it back), and climbs back when there is headroom. Not in the capture mode (comparable stills)
	// or when -SailingScreenPct fixes it.
	static const bool bFixed = FParse::Param(FCommandLine::Get(), TEXT("SailingScreenPct")) || FCommandLine::Get() && FCString::Strifind(FCommandLine::Get(), TEXT("SailingScreenPct=")) != nullptr
		|| FCString::Strifind(FCommandLine::Get(), TEXT("SailingCapture=")) != nullptr;
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
	OwnClock += DeltaSeconds;
	UpdateWeather(DeltaSeconds);
	UpdateTide();
	UpdateResolutionGovernor(DeltaSeconds);

	if (BenchSeconds <= 0.f || bBenchDone)
	{
		return;
	}

	Elapsed += DeltaSeconds;
	if (Elapsed > BenchWarmupSeconds && Elapsed <= BenchWarmupSeconds + BenchSeconds)
	{
		if (ClothSecondsAtStart < 0.0) ClothSecondsAtStart = ASailboatPawn::ClothCpuSeconds;
		if (WaterSecondsAtStart < 0.0) WaterSecondsAtStart = AWaterSurface::WaterCpuSeconds;
		// Real wall-clock frame time, not the (possibly clamped) game delta.
		FrameTimes.Add(static_cast<float>(FApp::GetDeltaTime()));
	}

	if (RecordSeconds > 0.f && Elapsed >= NextFrameTime && Elapsed < BenchWarmupSeconds + RecordSeconds)
	{
		const FString FramePath = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/rec/frame_%04d.png"), FrameIndex++));
		FScreenshotRequest::RequestScreenshot(FramePath, /*bShowUI*/ true, /*bAddFilenameSuffix*/ false);
		NextFrameTime += RecordInterval;
	}

	// -SailingProfileGPU: dump one frame's GPU timings to the log (for tuning quality tiers).
	static bool bProfiled = false;
	if (!bProfiled && Elapsed > BenchWarmupSeconds + 3.f && FParse::Param(FCommandLine::Get(), TEXT("SailingProfileGPU")))
	{
		bProfiled = true;
		GEngine->Exec(GetWorld(), TEXT("ProfileGPU"));
	}

	const float End = BenchWarmupSeconds + BenchSeconds;
	if (!bScreenshotRequested && Elapsed > End - 1.f)
	{
		const FString ShotPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/%s.png"), *ShotName));
		FScreenshotRequest::RequestScreenshot(ShotPath, /*bShowUI*/ true, /*bAddFilenameSuffix*/ false);
		bScreenshotRequested = true;
	}
	// Visual V1: after the measured window, profile three frames on the GPU (their frame times are not counted) and
	// sum their passes into the plan's budget slices. -SailingNoGpuSlices skips it.
	static const bool bGpuSlices = !FParse::Param(FCommandLine::Get(), TEXT("SailingNoGpuSlices"));
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
		WeatherPresetName(EWeatherPreset(Settings->WeatherPreset)), WeatherState.HourOfDay);
	// Visual V3: sail cloth simulation on the CPU, all boats, per frame of the measured window.
	if (N > 0 && ClothSecondsAtStart >= 0.0)
	{
		Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"cloth_cpu_ms\":%.3f}"), (ASailboatPawn::ClothCpuSeconds - ClothSecondsAtStart) * 1000.0 / N);
	}
	// Visual V4: the water's game-thread work (FFT frames blended and uploaded, the wake grid stepped).
	if (N > 0 && WaterSecondsAtStart >= 0.0)
	{
		Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"water_cpu_ms\":%.3f}"), (AWaterSurface::WaterCpuSeconds - WaterSecondsAtStart) * 1000.0 / N);
	}
	if (!GpuSlicesJson.IsEmpty())
	{
		Summary = Summary.LeftChop(1) + TEXT(",") + GpuSlicesJson + TEXT("}");
	}
	// Visual V7: the render resolution at the end of the window (High's governor may have lowered it).
	Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"render_pct\":%.0f}"), GetRenderScale());

	UE_LOG(LogSailing, Display, TEXT("SailingBench result: %s"), *Summary);
	FFileHelper::SaveStringToFile(Summary, *(FPaths::ProjectSavedDir() / TEXT("Bench/bench.json")));

	FPlatformMisc::RequestExit(false, TEXT("SailingBench finished"));
}
