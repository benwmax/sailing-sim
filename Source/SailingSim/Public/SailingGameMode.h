#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Wind.h"
#include "SailingGameMode.generated.h"

/**
 * Spawns the player's boat and owns the true wind. Also runs an optional frame-time benchmark. Also runs an optional frame-time benchmark for the QA gate:
 *   -SailingBench=<seconds>   measure frame times after a 3 s warm-up, log a summary, write
 *                             Saved/Bench/bench.json and a screenshot, then quit.
 */
UCLASS()
class SAILINGSIM_API ASailingGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASailingGameMode();

	virtual void StartPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	const Sailing::FWindField& GetWind() const { return Wind; }

	/** Gusts are softer on the easy difficulty. */
	void ApplyDifficultyToWind();

	/** True wind at 10 m, in knots. */
	UPROPERTY(EditAnywhere, Category = "Wind")
	float WindSpeedKnots = 10.f;

	/** Direction the wind comes from, degrees clockwise from +X (north on the HUD compass). Default: a westerly. */
	UPROPERTY(EditAnywhere, Category = "Wind")
	float WindFromDegrees = 270.f;

	UPROPERTY(EditAnywhere, Category = "Wind")
	float GustIntensity = 0.2f;

	UPROPERTY(EditAnywhere, Category = "Wind")
	float ShiftDegrees = 8.f;

	UPROPERTY(EditAnywhere, Category = "Wind")
	int32 WindSeed = 2027;

private:
	Sailing::FWindField Wind;

	void FinishBenchmark();

	float BenchSeconds = 0.f;
	float Elapsed = 0.f;
	bool bScreenshotRequested = false;
	bool bBenchDone = false;
	TArray<float> FrameTimes;
};
