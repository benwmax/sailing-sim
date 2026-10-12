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
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Scalability.h"
#include "Async/Async.h"
#include "LakeTerrainActor.h"
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
	Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard"));

	// Command-line overrides (benchmarks, recordings) are applied to settings for this run only.
	USailingSettings* Settings = USailingSettings::Get();
	FString Value;
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
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingQuality="), Value))
	{
		Settings->Quality = Value.Equals(TEXT("Low"), ESearchCase::IgnoreCase) ? ESailingQuality::Low
			: (Value.Equals(TEXT("Medium"), ESearchCase::IgnoreCase) ? ESailingQuality::Medium : ESailingQuality::High);
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

bool ASailingGameMode::GetLaunchSpot(FLaunchSpot& Out) const
{
	// -SailingStartAt=<north m>,<east m>,<heading deg> overrides (tests, screenshots).
	FString At;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingStartAt="), At))
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
			TSharedPtr<Sailing::FShelterMap> Map = MakeShared<Sailing::FShelterMap>();
			Map->Build(*Terrain, From);
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
	Weather.Configure(EWeatherPreset(Settings->WeatherPreset), uint32(FMath::Max(Settings->WeatherSeed, 1)), Settings->StartHour);

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
	// Engine scalability: Low = engine Medium (no Lumen), Medium = High, High = Epic.
	Scalability::FQualityLevels Levels = Scalability::GetQualityLevels();
	Levels.SetFromSingleQualityLevel(Quality == ESailingQuality::Low ? 1 : (Quality == ESailingQuality::Medium ? 2 : 3));
	Scalability::SetQualityLevels(Levels);
	// Volumetric clouds are the most expensive part of the sky: cap their ray-march samples per tier.
	auto SetCVar = [](const TCHAR* Name, int32 Value)
	{
		if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name)) Var->Set(Value, ECVF_SetByCode);
	};
	SetCVar(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), Quality == ESailingQuality::Low ? 48 : (Quality == ESailingQuality::Medium ? 80 : 96));
	SetCVar(TEXT("r.VolumetricCloud.ReflectionRaySampleMaxCount"), Quality == ESailingQuality::High ? 24 : 16);
	for (TActorIterator<AWaterSurface> It(GetWorld()); It; ++It)
	{
		It->SetRingCount(Quality == ESailingQuality::Low ? 4 : (Quality == ESailingQuality::Medium ? 5 : 6));
	}
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
	Waves.SetWind(WaveParams);
	// Short-fetch chop builds within a minute or two.
	Waves.Update(DeltaSeconds, 40.0);
}

void ASailingGameMode::StartPlay()
{
	// Weather first: the boat reads the wind when it is spawned during Super::StartPlay.
	ApplyQualitySettings();
	ApplyWeatherSettings();
	Super::StartPlay();

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

void ASailingGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	OwnClock += DeltaSeconds;
	UpdateWeather(DeltaSeconds);

	if (BenchSeconds <= 0.f || bBenchDone)
	{
		return;
	}

	Elapsed += DeltaSeconds;
	if (Elapsed > BenchWarmupSeconds)
	{
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
	if (Elapsed > End)
	{
		FinishBenchmark();
	}
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

	const FString Summary = FString::Printf(
		TEXT("{\"frames\":%d,\"seconds\":%.2f,\"avg_fps\":%.1f,\"avg_ms\":%.2f,\"p99_ms\":%.2f,\"max_ms\":%.2f,\"rhi\":\"%s\",\"resolution\":\"%dx%d\",\"quality\":\"%s\",\"weather\":\"%hs\",\"hour\":%.1f}"),
		N, Total, AvgFps, AvgMs, P99Ms, MaxMs, GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"),
		GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport ? GEngine->GameViewport->Viewport->GetSizeXY().X : 0,
		GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport ? GEngine->GameViewport->Viewport->GetSizeXY().Y : 0,
		Settings->Quality == ESailingQuality::Low ? TEXT("Low") : (Settings->Quality == ESailingQuality::Medium ? TEXT("Medium") : TEXT("High")),
		WeatherPresetName(EWeatherPreset(Settings->WeatherPreset)), WeatherState.HourOfDay);

	UE_LOG(LogSailing, Display, TEXT("SailingBench result: %s"), *Summary);
	FFileHelper::SaveStringToFile(Summary, *(FPaths::ProjectSavedDir() / TEXT("Bench/bench.json")));

	FPlatformMisc::RequestExit(false, TEXT("SailingBench finished"));
}
