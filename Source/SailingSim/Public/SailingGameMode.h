#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Waves.h"
#include "Weather.h"
#include "Wind.h"
#include "SailingGameMode.generated.h"

/**
 * Owns the world's weather, wind and waves and the simulation clock (the boat's physics time), and spawns
 * the player's boat. Command line (for benchmarks and recordings):
 *   -SailingWeather=<CalmMorning|AfternoonBreeze|Overcast|Rain|Thunderstorm|RandomDay>  -SailingHour=<h>
 *   -SailingWind=<knots> (scale the preset to this base wind)  -SailingWeatherTime=<s> (start partway in)
 *   -SailingSeed=<n>  -SailingBench=<s>  -SailingRecord=<s>  -SailingRecordInterval=<s>  -SailingShot=<name>
 */
UCLASS()
class SAILINGSIM_API ASailingGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASailingGameMode();

	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
	virtual void StartPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	const Sailing::FWindField& GetWind() const { return Wind; }
	const Sailing::FWaveField& GetWaves() const { return Waves; }
	const Sailing::FWeatherState& GetWeatherState() const { return WeatherState; }
	const Sailing::FWeatherSystem& GetWeather() const { return Weather; }

	/** Physics time (s): the boat's clock, which the wind, waves and water material all use. */
	double GetSimTime() const;
	/** Seconds since the current weather started (the storm timeline runs on this). */
	double GetWeatherTime() const { return GetSimTime() - WeatherStartTime; }

	/** Re-reads the weather picker, time of day and seed from settings and restarts the weather. */
	void ApplyWeatherSettings();
	/** Applies the quality tier from settings to engine scalability and the water mesh. */
	void ApplyQualitySettings();
	/** Kept for the difficulty toggle: gusts are softer on easy. */
	void ApplyDifficultyToWind() { ApplyWeatherSettings(); }

private:
	void UpdateWeather(float DeltaSeconds);
	void FinishBenchmark();

	Sailing::FWeatherSystem Weather;
	Sailing::FWeatherState WeatherState;
	Sailing::FWindField Wind;
	Sailing::FWaveField Waves{ 2027 };
	double WeatherStartTime = 0.0;
	double OwnClock = 0.0;
	float WindOverrideKnots = 0.f;
	double WindScale = 1.0;

	float BenchSeconds = 0.f;
	float RecordSeconds = 0.f;
	float RecordInterval = 0.1f;
	float NextFrameTime = 0.f;
	int32 FrameIndex = 0;
	float Elapsed = 0.f;
	bool bScreenshotRequested = false;
	bool bBenchDone = false;
	FString ShotName = TEXT("screenshot");
	TArray<float> FrameTimes;
};
