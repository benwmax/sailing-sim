#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Waves.h"
#include "SeaState.h"
#include "Ocean.h"
#include "Weather.h"
#include "Wind.h"
#include "WorldClock.h"
#include "ScriptedScene.h"
#include "PerfScopes.h"
#include "LakeData.h"
#include "Chart.h"
#include "WorldStreaming.h"
#include "Async/Future.h"
#include "SailingGameMode.generated.h"

/**
 * Owns the world's weather, wind and waves and the simulation clock (the boat's physics time), and spawns
 * the player's boat. Command line (for benchmarks and recordings):
 *   -SailingWeather=<CalmMorning|AfternoonBreeze|Overcast|Rain|Thunderstorm|RandomDay|Mistral>  -SailingHour=<h>
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
	/** Measuring (-SailingNearShip=<m>): ATrafficManager puts the player this far abeam of the first ship it spawns, so a still
	 *  can frame her exhaust (the ships' spawn varies run to run); GetLaunchSpot returns it once set. */
	TOptional<FLaunchSpot> NearShipStart;
	/** The area's data files by setting: "RayHubbard" or "GalvestonBay". */
	static const TCHAR* WorldFileName(int32 World);
	/** A world by its name or number (-SailingWorld, a scene's setting.world_stand_in): "Lake" 0, "Galveston" 1, "Gulf" 2. */
	static int32 WorldIndexFromName(const FString& Name);
	/** Central European time's offset from UTC on a date (+1, +2 in summer time): the Marseille world's clock. */
	static int32 CentralEuropeanOffsetHours(const FDateTime& Date);
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

	/** Physics time (s): the world clock (FWorldClock), which every boat, the wind, waves and water material run on. */
	double GetSimTime() const { return Clock.GetTime(); }
	/** Moves the world clock by this frame's time, once a frame: the game mode's tick or the first boat to tick, whichever
	 *  runs first (boats step until they reach it, so it has to have moved before they do). */
	void AdvanceClock(float DeltaSeconds);
	/** Seconds since the current weather started (the storm timeline runs on this). */
	double GetWeatherTime() const { return GetSimTime() - WeatherStartTime; }

	/** W5b: rain (0..1) at a point (m), where the storm's core or the radar puts it; the weather's amount otherwise. */
	double GetRainAt(double X, double Y) const { return WeatherState.RainAt(X, Y, GetSimTime()); }
	/** W5b: the real day running (Tools/weather), or null for a preset. */
	const Sailing::FWeatherDay* GetRealDay() const { return RealDay.get(); }
	/** W5b: loads Content/TerrainData/Weather/<date>.wxday; null if it is not there or not valid. */
	static std::shared_ptr<const Sailing::FWeatherDay> LoadRealDay(const FString& Date);

	/** Prologue step 1 (docs/prologue/README.md): the scripted crew scene this session runs, or null. A prologue session is
	 *  -SailingPrologue=1 for now (the first-launch flow comes later); it sails the scene's stand-in boat and wind. */
	const Sailing::FScriptedScene* GetScene() const { return bScene ? &Scene : nullptr; }
	static bool IsPrologueRun();
	/** The boat the scene follows hands it her state and the crew's input once a frame, after her physics (the pawn).
	 *  The scene steps on the sim clock (her physics time). */
	void UpdateScene(const Sailing::FBoatModel& Boat, const Sailing::FSceneInput& Input);
	/** The boat is being (re)started: the scene goes back to its last checkpoint if it is running, and Out* is the pose to
	 *  start from (that checkpoint's, or the first step's before it starts). False when the step has no pose. */
	bool RestartScene(double& OutTwaDeg, double& OutKnots);
	/** Content/Prologue/prologue.json read and checked; false (with a log line) if it is missing or invalid. */
	static bool LoadPrologue(Sailing::FScriptedScene& Out, FString* OutError = nullptr);
	/** Prologue step 3: the scene sails its own boat (setting.boat, the maxi) unless -SailingPrologueBoat names its stand-in;
	 *  the reefs the crew start with (setting.reefs, or the stand-in's). */
	bool IsSceneStandIn() const { return bScene && bSceneStandIn; }
	int32 GetSceneReefs() const { return bScene ? SceneReefs : 0; }

	/** Re-reads the weather picker, time of day and seed from settings and restarts the weather. */
	void ApplyWeatherSettings();
	/** Applies the quality tier from settings to engine scalability and the water mesh. */
	void ApplyQualitySettings();
	/** Kept for the difficulty toggle: gusts are softer on easy. */
	void ApplyDifficultyToWind() { ApplyWeatherSettings(); }

	/** World streaming (docs/world-streaming): the world's height tiles around the boat. */
	const FWorldStreamer& GetStreamer() const { return Streamer; }
	/** Moves the render frame's origin to this map point (m, on the re-centre lattice or not) now; false if the engine
	 *  refused (a level becoming visible). The game does it itself when the boat is kRecentreM from the origin. */
	bool RecentreAt(double NorthM, double EastM);
	/** Re-centres so far, and the longest one's game-thread time (ms). */
	int32 GetRecentres() const { return Recentres; }
	double GetLongestRecentreMs() const { return LongestRecentreMs; }
	/** Where the boat the world follows is (map frame, m): the player's boat, or the camera when there is none. */
	FVector2D GetFollowPoint() const;
	/** The physics' window on a streamed world (the sea fetch, ocean mask and shelter map are built over it). */
	const Sailing::FPhysicsWindow& GetPhysicsWindow() const { return PhysicsWindow; }
	int32 GetWindowMarches() const { return WindowMarches; }
	/** Whether a march of the physics' window is running on a worker. */
	bool IsWindowMarching() const { return bWindowMarching; }

private:
	// World streaming.
	FWorldStreamer Streamer;
	UPROPERTY(Transient) TObjectPtr<class UMaterialParameterCollection> WorldCollection;
	int32 Recentres = 0;
	double LongestRecentreMs = 0.0;
	/** Starts the world's streaming and reads the tiles around the launch spot (end of InitGame). */
	void StartStreaming();
	/** Each frame: tiles around the boat, the render origin, the physics' window. */
	void UpdateStreaming();
	/** MPC_World.RenderOrigin (cm): the materials put their positions back in the map frame with it. */
	void PublishRenderOrigin();
	struct FWindowGrids
	{
		TSharedPtr<const Sailing::FSeaFetch, ESPMode::ThreadSafe> Fetch;
		TSharedPtr<Sailing::FShelterMap> Shelter;
		Sailing::FOcean::FMask Mask;
		bool bMask = false;
		double CenterX = 0.0, CenterY = 0.0, ShelterFrom = 0.0;
		double Ms = 0.0;
	};
	Sailing::FPhysicsWindow PhysicsWindow;
	TFuture<FWindowGrids> PendingWindow;
	bool bWindowMarching = false;
	bool bWindowStale = false;   // the ocean's swell changed: march the window again
	int32 WindowMarches = 0;
	/** Marches the sea fetch, the ocean mask and the shelter map over a window centred on (X, Y) on a worker. */
	void MarchWindow(double X, double Y);
	/** The terrain the derived grids are built on: the window on a streamed world, the whole grid otherwise (a copy). */
	Sailing::FLakeTerrain DerivedTerrain(double CenterX, double CenterY) const;
	void UpdateWeather(float DeltaSeconds);
	void UpdateOcean(double WindKnots, double WindFromDeg);
	TSharedPtr<Sailing::FOcean> Ocean;
	bool bOceanConfigured = false;
	void UpdateTide();
	double StartUnix = 0.0;
	double ClockBase = 0.0;
	int32 DayOfYear = 285;
	double SunsetHour = 19.0; // docs/night-clouds/: local hour, from the date and the latitude (BeginPlay)
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
	// W3: the effective fetch at the boat (nine marches), recomputed when she has moved 25 m or the wind turned 2 deg.
	double FetchCacheX = 1e18, FetchCacheY = 1e18, FetchCacheFrom = 1e18, FetchCacheMeters = 4000.0;
	std::vector<Sailing::FShelterObstacle> ShelterObstacles; // W1: the houses, for the lee map
	// W3, sea state by direction (SeaState.h): the fetch map, built at load; the sea map for the mean wind, rebuilt on a
	// worker when the wind's speed changes 5% or its direction 11.25 deg (-SailingNoSeaMap: one sea everywhere, as before).
	TSharedPtr<const Sailing::FSeaFetch, ESPMode::ThreadSafe> SeaFetch;
	TFuture<std::shared_ptr<const Sailing::FSeaMap>> PendingSeaMap;
	bool bSeaMapBuilding = false;
	double SeaMapKnots = -1.0, SeaMapFrom = 1e9;
	uint32 SeaMapDirections = 0; // the components' direction generation the map was built on
	void UpdateSeaMap(double Knots, double FromDegrees);
	void UpdateShelter();
	void UpdateResolutionGovernor(float DeltaSeconds);
	float GovernorMs = 16.f, GovernorClock = 0.f;
public:
	/** The render resolution in percent now (High's governor may lower it in heavy views). */
	float GetRenderScale() const;
private:
	double WeatherStartTime = 0.0;
	Sailing::FWorldClock Clock;
	uint64 ClockFrame = MAX_uint64;
	float WindOverrideKnots = 0.f;
	double WindScale = 1.0;
	// Graphics G4: the wind direction (true, from) and gust intensity a session or the command line fixes; NaN = the preset's.
	float WindFromOverride = NAN, GustOverride = NAN;
	// W5b: a real day (session or -SailingDay=YYYY-MM-DD) and whether its start hour was given (-SailingHour, the session).
	FString RealDayDate;
	bool bRealDayHour = false;
	std::shared_ptr<const Sailing::FWeatherDay> RealDay;
	// Graphics G4: the session's date (the clock's day); unset = today or -SailingDate.
	FDateTime SessionDate;
	bool bSessionDate = false;
	bool bWindArgsRead = false;
	// Prologue step 1: the scene, its clock (the boat's physics time when it last stepped) and the last call voiced.
	Sailing::FScriptedScene Scene;
	bool bScene = false, bSceneStarted = false, bSceneRecorded = false, bSceneStandIn = false;
	int32 SceneReefs = 0;
	double SceneTime = 0.0;
	int32 SceneCallSerial = 0;
	int32 SceneWeatherSerial = -1;
	int32 SceneStartStep = 0;  // -SailingPrologueStep (stills)
	bool bScenePreset = false; // the scene's setting.weather named a preset (step 4: the mistral)
public:
	/** Graphics G4: changes the running session's weather in place (Pause > Change conditions): no reload. */
	void ApplyConditions(const struct FSailConditions& Conditions);
private:

	float BenchSeconds = 0.f;
	float BenchWarmup = 3.f;
	bool bBenchTrace = false;
	int32 ForegroundFrames = 0;
	/** -SailingBenchTrace: one row a frame (time since start, frame ms, then the game, render, RHI and GPU times the
	 *  engine last published: those lag the frame by one or two). */
	struct FTraceFrame { float T, FrameMs, GameMs, RenderMs, RhiMs, GpuMs; };
	TArray<FTraceFrame> TraceTimes;
	float RecordSeconds = 0.f;
	TArray<TPair<float, FString>> ExecAt;   // -SailingExecAt: (seconds, console command)
	int32 NextExecAt = 0;
	float NextPosLog = 0.f;   // -SailingBenchTrace: the player's position once a minute (soaks: is the boat parked?)
	FVector LastPosLog = FVector::ZeroVector;
	float RecordInterval = 0.1f;
	float NextFrameTime = 0.f;
	int32 FrameIndex = 0;
	float Elapsed = 0.f;
	bool bScreenshotRequested = false;
	bool bBenchDone = false;
	FString ShotName = TEXT("screenshot");
	TArray<float> FrameTimes;
	// Visual V1: GPU time per budget slice (see GpuSlices.h), profiled inside the measured window since Perf (storm-high
	// 2026-10-18); the frames around each profiled one are left out of the frame times.
	TSharedPtr<class FGpuProfileCapture> GpuCapture;
	int32 GpuProfilesRequested = 0;
	int32 GpuProfileSkipFrames = 0;
	int32 GpuProfileSkipped = 0;
	FString GpuSlicesJson;
	double ClothSecondsAtStart = -1.0;
	double WaterSecondsAtStart = -1.0;
	double WindMapSecondsAtStart = -1.0; // W2: the two-level wind map (bench.json windmap_cpu_ms)
	double FarCapSecondsAtStart = -1.0; // far-cap sprites (bench.json farcap_cpu_ms)
	// Perf 1: stat unit's thread times over the measured window, and the game thread's slices at its start.
	SailingPerf::FThreadTimes ThreadTimes;
	double SlicesAtStart[int32(SailingPerf::ESlice::Count)] = {};
	double SlicesAtEnd[int32(SailingPerf::ESlice::Count)] = {};
	bool bSlicesStarted = false;
	void FinishGpuSlices();
};
