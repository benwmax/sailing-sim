#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SailingGameMode.generated.h"

/**
 * Spawns the player's boat. Also runs an optional frame-time benchmark for the QA gate:
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

private:
	void FinishBenchmark();

	float BenchSeconds = 0.f;
	float Elapsed = 0.f;
	bool bScreenshotRequested = false;
	bool bBenchDone = false;
	TArray<float> FrameTimes;
};
