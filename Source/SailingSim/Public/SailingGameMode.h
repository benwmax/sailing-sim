#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Waves.h"
#include "Ocean.h"
#include "Weather.h"
#include "Wind.h"
#include "LakeData.h"
#include "Chart.h"
#include "Async/Future.h"
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
	/** The lake (terrain, docks, bridges, launch spots); empty if no lake data is found (open water). */
	const FLakeData& GetLake() const { return Lake; }
	/** Where the boat is launched (from the settings' launch spot); false on open water. */
	bool GetLaunchSpot(FLaunchSpot& Out) const;
	/** The area's data files by setting: "RayHubbard" or "GalvestonBay". */
	static const TCHAR* WorldFileName(int32 World);
	static const TCHAR* WorldDisplayName(int32 World);

	/** Real time (seconds since 1970 UTC): the chosen date and start time plus the time sailed. Tides run on it. */
	double GetUnixTime() const { return StartUnix + (GetSimTime() - ClockBase); }
	/** Day of the year (1-366) of the session's date, for the sun. */
	int32 GetDayOfYear() const { return DayOfYear; }
	/** Local clock hours (0-24) now, in the area's time zone. */
	double GetLocalHour() const;
	/** Water level above chart datum at the boat (m); 0 on the lake. */
	double GetTideHeight() const { return TideHeight; }
	/** Tidal current at a point (m/s, map frame). */
	Sailing::Vec3 GetCurrentAt(double X, double Y) const { return Lake.IsTidal() ? Lake.Tides.CurrentAt(X, Y, GetUnixTime()) : Sailing::Vec3(); }

	/** The next high or low water at the boat (refreshed every minute); false off the coast. */
	bool GetNextTide(Sailing::FTideEvent& Out) const { Out = NextTide; return bHasNextTide; }
	/** Hours to add to UTC for the area's local clock. */
	int32 GetUtcOffsetHours() const { return UtcOffsetHours; }
	/** The vector chart of the area (loaded the first time it is asked for); empty on the lake. */
	const FChartData& GetChart() const;
	/** Whether lights are showing: from sunset to sunrise (sun below the horizon) and in restricted visibility. */
	bool IsDark() const;

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
	void UpdateOcean(double WindKnots, double WindFromDeg);
	TSharedPtr<Sailing::FOcean> Ocean;
	bool bOceanConfigured = false;
	void UpdateTide();
	double StartUnix = 0.0;
	double ClockBase = 0.0;
	int32 DayOfYear = 285;
	int32 UtcOffsetHours = -5;
	double TideHeight = 0.0;
	Sailing::FTideEvent NextTide;
	bool bHasNextTide = false;
	double NextTideUpdate = -1e9;
	mutable FChartData Chart;
	mutable bool bChartTried = false;
	TWeakObjectPtr<AActor> TerrainActor;
	void FinishBenchmark();

	Sailing::FWeatherSystem Weather;
	Sailing::FWeatherState WeatherState;
	Sailing::FWindField Wind;
	Sailing::FWaveField Waves{ 2027 };
	FLakeData Lake;
	TSharedPtr<Sailing::FShelterMap> Shelter;
	TFuture<TSharedPtr<Sailing::FShelterMap>> PendingShelter;
	bool bShelterBuilding = false;
	void UpdateShelter();
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
