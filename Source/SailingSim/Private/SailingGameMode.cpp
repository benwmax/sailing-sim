#include "SailingGameMode.h"
#include "SailingSim.h"
#include "SailboatPawn.h"
#include "SailingHUD.h"
#include "SailingSettings.h"
#include "DynamicRHI.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "GenericPlatform/GenericPlatformMisc.h"
#include "HAL/FileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace
{
	constexpr float BenchWarmupSeconds = 3.f;
}

ASailingGameMode::ASailingGameMode()
{
	DefaultPawnClass = ASailboatPawn::StaticClass();
	HUDClass = ASailingHUD::StaticClass();
	PrimaryActorTick.bCanEverTick = true;
}

void ASailingGameMode::ApplyDifficultyToWind()
{
	const bool bEasy = USailingSettings::Get()->Difficulty == ESailingDifficulty::Easy;
	Sailing::FWindParams Params;
	Params.SpeedKnots = WindSpeedKnots;
	Params.FromDegrees = WindFromDegrees;
	Params.GustIntensity = GustIntensity * (bEasy ? 0.5f : 1.f);
	Params.ShiftDegrees = ShiftDegrees * (bEasy ? 0.5f : 1.f);
	Params.Seed = uint32(WindSeed);
	Wind.SetParams(Params);
}

void ASailingGameMode::StartPlay()
{
	ApplyDifficultyToWind();
	Super::StartPlay();

	if (FParse::Value(FCommandLine::Get(), TEXT("SailingBench="), BenchSeconds) && BenchSeconds > 0.f)
	{
		UE_LOG(LogSailing, Display, TEXT("SailingBench: measuring %.1f s after %.1f s warm-up"), BenchSeconds, BenchWarmupSeconds);
		FrameTimes.Reserve(FMath::CeilToInt(BenchSeconds * 240.f));
		FParse::Value(FCommandLine::Get(), TEXT("SailingRecord="), RecordSeconds);
		NextFrameTime = BenchWarmupSeconds;
	}
}

void ASailingGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

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
		NextFrameTime += 0.1f;
	}

	const float End = BenchWarmupSeconds + BenchSeconds;
	if (!bScreenshotRequested && Elapsed > End - 1.f)
	{
		const FString ShotPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Bench/screenshot.png"));
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

	const FString Summary = FString::Printf(
		TEXT("{\"frames\":%d,\"seconds\":%.2f,\"avg_fps\":%.1f,\"avg_ms\":%.2f,\"p99_ms\":%.2f,\"max_ms\":%.2f,\"rhi\":\"%s\",\"resolution\":\"%dx%d\"}"),
		N, Total, AvgFps, AvgMs, P99Ms, MaxMs, GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"),
		GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport ? GEngine->GameViewport->Viewport->GetSizeXY().X : 0,
		GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport ? GEngine->GameViewport->Viewport->GetSizeXY().Y : 0);

	UE_LOG(LogSailing, Display, TEXT("SailingBench result: %s"), *Summary);
	FFileHelper::SaveStringToFile(Summary, *(FPaths::ProjectSavedDir() / TEXT("Bench/bench.json")));

	FPlatformMisc::RequestExit(false, TEXT("SailingBench finished"));
}
