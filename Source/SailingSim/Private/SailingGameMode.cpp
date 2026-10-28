#include "SailingGameMode.h"
#include "SailingFrame.h"
#include "EasyAssists.h"
#include "BenchRunner.h"
#include "WindClimate.h"
#include "CoastMarinasActor.h"
#include "SailSession.h"
#include "SailSave.h"
#include "SailingAudio.h"
#include "SailingSim.h"
#include "SailboatPawn.h"
#include "SailingHUD.h"
#include "SailingSettings.h"
#include "WaterSurface.h"
#include "DynamicRHI.h"
#include "RenderingThread.h"
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
#include "FarLightsActor.h"
#include "MarinaActor.h"
#include "BridgesActor.h"
#include "LandmarksActor.h"
#include "NightLightsActor.h"
#include "Ocean.h"
#include "TrafficManager.h"
#include "SailingEnvironment.h"
#include "UnrealClient.h"
#include "ShaderCompiler.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialParameterCollection.h"
#include "UObject/ConstructorHelpers.h"

using namespace Sailing;


ASailingGameMode::ASailingGameMode()
{
	DefaultPawnClass = ASailboatPawn::StaticClass();
	HUDClass = ASailingHUD::StaticClass();
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	// World streaming: the render origin goes to every material through MPC_World.RenderOrigin (a hard reference).
	static ConstructorHelpers::FObjectFinder<UMaterialParameterCollection> WorldMpc(TEXT("/Game/World/MPC_World.MPC_World"));
	WorldCollection = WorldMpc.Object;
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
	// Prologue step 3: the scene's own boat (setting.boat, the maxi), or its stand-in with -SailingPrologueBoat=J22 (steps 1
	// and 2's J/22 in the stand-in wind, for comparison); -SailingBoat still wins. Until the mistral coast exists (step 4)
	// the maxi sails the Gulf's offshore spot, 15 nm south of Galveston: the only water in the game deep enough for her
	// 6 m draft. The command line's world and launch spot still win.
	FString SceneError;
	if (IsPrologueRun())
	{
		bScene = LoadPrologue(Scene, &SceneError);
		if (bScene)
		{
			const Sailing::FSceneSetting& Set = Scene.GetSetting();
			FString Want = UTF8_TO_TCHAR(Set.Boat.c_str());
			FParse::Value(SailingArgs::Dev(), TEXT("SailingPrologueBoat="), Want);
			bSceneStandIn = !Set.StandInBoat.empty() && Want.Equals(UTF8_TO_TCHAR(Set.StandInBoat.c_str()), ESearchCase::IgnoreCase);
			SceneReefs = bSceneStandIn ? Set.StandInReefs : Set.Reefs;
			// -SailingBoat wins (the pawn applies it again; resolved here so the world below follows it).
			const bool bBoatArg = FParse::Value(SailingArgs::Dev(), TEXT("SailingBoat="), Value);
			const int32 Match = USailingSettings::MatchBoatName(bBoatArg ? Value : Want);
			if (Match >= 0) Settings->BoatType = Match;
			// Step 4: the scene's stand-in world (setting.world_stand_in: the Gulf's offshore spot) until its own exists.
			if (!bSceneStandIn && Settings->BoatType == int32(Sailing::EBoatType::Maxi) && !Set.WorldStandIn.empty() && !FParse::Value(SailingArgs::Dev(), TEXT("SailingWorld="), Value))
			{
				Settings->World = WorldIndexFromName(UTF8_TO_TCHAR(Set.WorldStandIn.c_str()));
				Settings->LaunchSpot = Set.WorldStandInLaunch;
			}
			// Step 4: the scene's weather preset (setting.weather, the mistral) and hour; -SailingWeather and -SailingHour win.
			for (int32 I = 0; I < int32(EWeatherPreset::Count); ++I)
			{
				if (FString(UTF8_TO_TCHAR(Set.Weather.c_str())).Equals(FString(WeatherPresetName(EWeatherPreset(I))).Replace(TEXT(" "), TEXT("")), ESearchCase::IgnoreCase))
				{
					Settings->WeatherPreset = ESailingWeather(I);
					bScenePreset = true;
				}
			}
			if (Set.Hour >= 0.0) Settings->StartHour = float(Set.Hour);
			// Stills: -SailingPrologueStep=<step id> starts the scene at that step, the boat on the checkpoint before it.
			FString StepId;
			if (FParse::Value(SailingArgs::Dev(), TEXT("SailingPrologueStep="), StepId))
			{
				SceneStartStep = FMath::Max(0, Scene.FindStep(TCHAR_TO_UTF8(*StepId)));
				UE_LOG(LogSailing, Display, TEXT("Prologue: starting at step %d (%s)"), SceneStartStep, *StepId);
			}
		}
	}
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingWorld="), Value))
	{
		Settings->World = WorldIndexFromName(Value);
	}
	Lake.Load(FLakeData::DefaultDirectory(), WorldFileName(Settings->World));
	// World streaming: the tile index (a streamed world's heights arrive in StartStreaming, at the end of InitGame).
	Streamer.Start(Lake, FLakeData::DefaultDirectory(), WorldFileName(Settings->World));
	// gulf-swell: Galveston carries the Gulf's ocean too (masked out of the bay); -SailingNoOcean compares without it.
	if (Lake.bOcean && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoOcean")))
	{
		Ocean = MakeShared<FOcean>();
		Waves.SetOcean(std::shared_ptr<FOcean>(Ocean.Get(), [Keep = Ocean](FOcean*) {}));
	}
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingWeather="), Value))
	{
		for (int32 I = 0; I < int32(EWeatherPreset::Count); ++I)
		{
			if (Value.Equals(FString(WeatherPresetName(EWeatherPreset(I))).Replace(TEXT(" "), TEXT("")), ESearchCase::IgnoreCase))
			{
				Settings->WeatherPreset = ESailingWeather(I);
			}
		}
	}
	bRealDayHour = FParse::Value(SailingArgs::Dev(), TEXT("SailingHour="), Settings->StartHour);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingDay="), RealDayDate);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingSeed="), Settings->WeatherSeed);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingWind="), WindOverrideKnots);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingLaunch="), Settings->LaunchSpot);
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingLakeLevel="), Value))
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
			if (!FParse::Value(SailingArgs::Dev(), TEXT("SailingWind="), Value)) WindOverrideKnots = FMath::Max(C.WindKn, 0.5f);
			WindFromOverride = C.WindFromDeg;
			GustOverride = FMath::Clamp(C.GustKn / FMath::Max(C.WindKn, 1.f) - 1.f, 0.f, 1.f);
		}
		SessionDate = FDateTime(FDateTime::Now().GetYear(), FMath::Clamp(C.Month, 1, 12), FMath::Clamp(C.Day, 1, FDateTime::DaysInMonth(FDateTime::Now().GetYear(), FMath::Clamp(C.Month, 1, 12))));
		bSessionDate = true;
		if (!Lake.IsCoast() && FMath::Abs(C.LakeLevelFt) > 0.01f)
		{
			Lake.Terrain.SetLevelBelowPool(-C.LakeLevelFt * 0.3048);   // above the pool raises the water: the shore drops by as much
		}
	}
	// Prologue: the scene's wind, by its preset (step 4: the mistral's own 32 kn gusting 40) or, with the stand-in boat
	// or no preset, scaled to the setting's wind and gusts (the command line still wins).
	if (IsPrologueRun())
	{
		if (bScene)
		{
			const Sailing::FSceneSetting& Set = Scene.GetSetting();
			const bool bStandInWind = bSceneStandIn && Set.StandInWindKn > 0.0;
			const double Kn = bStandInWind ? Set.StandInWindKn : Set.WindKn;
			const double Gust = bStandInWind ? Set.StandInGustKn : Set.GustKn;
			if (!FParse::Value(SailingArgs::Dev(), TEXT("SailingWind="), Value)) WindOverrideKnots = float(Kn);
			if (!FParse::Value(SailingArgs::Dev(), TEXT("SailingGust="), Value) && (bStandInWind || !bScenePreset))
				GustOverride = float(FMath::Clamp(Gust / FMath::Max(Kn, 1.0) - 1.0, 0.0, 1.0));
			UE_LOG(LogSailing, Display, TEXT("Prologue: \"%s\", %d steps, %s%s in %.0f kn gusting %.0f, %d reefs"), UTF8_TO_TCHAR(Scene.GetTitle().c_str()),
				int32(Scene.GetSteps().size()), UTF8_TO_TCHAR(Sailing::BoatTypeName(Sailing::EBoatType(Settings->BoatType))), bSceneStandIn ? TEXT(" (stand-in)") : TEXT(""),
				Kn, Gust, SceneReefs);
		}
		else UE_LOG(LogSailing, Warning, TEXT("Prologue: %s"), *SceneError);
	}
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingQuality="), Value))
	{
		Settings->Quality = Value.Equals(TEXT("Low"), ESearchCase::IgnoreCase) ? ESailingQuality::Low
			: (Value.Equals(TEXT("Medium"), ESearchCase::IgnoreCase) ? ESailingQuality::Medium
			: (Value.Equals(TEXT("Ultra"), ESearchCase::IgnoreCase) ? ESailingQuality::Ultra : ESailingQuality::High));
	}
	StartStreaming();
}

void ASailingGameMode::StartStreaming()
{
	// World streaming (docs/world-streaming). A streamed world reads the tiles within the load radius of the launch spot
	// now (the loading screen's "Reading the coast"); every world's derived grids are then marched once here.
	FLaunchSpot Spot;
	const bool bSpot = GetLaunchSpot(Spot);
	if (Lake.bStreamed && Streamer.IsStarted())
	{
		Streamer.LoadAround(bSpot ? Spot.X : 0.0, bSpot ? Spot.Y : 0.0, Streamer.Radii.LoadM);
	}
	// W3: the fetch every way at every point, and the water's depth (about 50 ms). The components' wavenumbers follow the
	// world's median depth (shallow-water dispersion) before anything reads them. On a streamed world, over the physics'
	// window around the start (and again on a worker as the boat sails on: MarchWindow).
	if (Lake.bStreamed)
	{
		PhysicsWindow.CenterX = bSpot ? Spot.X : 0.0;
		PhysicsWindow.CenterY = bSpot ? Spot.Y : 0.0;
		PhysicsWindow.bValid = true;
	}
	if (Lake.IsLoaded() && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoSeaMap")))
	{
		const double Start = FPlatformTime::Seconds();
		TSharedPtr<Sailing::FSeaFetch, ESPMode::ThreadSafe> Fetch = MakeShared<Sailing::FSeaFetch, ESPMode::ThreadSafe>();
		Fetch->Build(DerivedTerrain(PhysicsWindow.CenterX, PhysicsWindow.CenterY));
		SeaFetch = Fetch;
		Waves.SetDepth(Fetch->GetMedianDepth());
		UE_LOG(LogSailing, Display, TEXT("Sea fetch map: %d x %d cells of %.0f m, median depth %.1f m, built in %.0f ms"),
			Fetch->GetRows(), Fetch->GetCols(), Fetch->GetCell(), Fetch->GetMedianDepth(), (FPlatformTime::Seconds() - Start) * 1000.0);
	}
}

Sailing::FLakeTerrain ASailingGameMode::DerivedTerrain(double CenterX, double CenterY) const
{
	return Lake.bStreamed ? Lake.Terrain.WindowAround(CenterX, CenterY, PhysicsWindow.HalfM) : Lake.Terrain;
}

FVector2D ASailingGameMode::GetFollowPoint() const
{
	const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	if (const ASailboatPawn* Boat = PC ? Cast<ASailboatPawn>(PC->GetPawn()) : nullptr)
	{
		const Sailing::Vec3 O = Boat->GetBoatModel().OriginPosition();
		return FVector2D(O.X, O.Y);
	}
	if (PC && PC->PlayerCameraManager) return SailingFrame::ToMap(GetWorld(), PC->PlayerCameraManager->GetCameraLocation());
	return SailingFrame::OriginM(GetWorld());
}

void ASailingGameMode::PublishRenderOrigin()
{
	if (!WorldCollection || !GetWorld()) return;
	const FVector O = SailingFrame::OriginCm(GetWorld());
	UKismetMaterialLibrary::SetVectorParameterValue(this, WorldCollection, TEXT("RenderOrigin"), FLinearColor(float(O.X), float(O.Y), float(O.Z), 0.f));
}

bool ASailingGameMode::RecentreAt(double NorthM, double EastM)
{
	UWorld* World = GetWorld();
	if (!World) return false;
	const FIntVector To(int32(FMath::RoundToInt64(NorthM * CmPerMeter)), int32(FMath::RoundToInt64(EastM * CmPerMeter)), 0);
	if (To == World->OriginLocation) return true;
	const double Start = FPlatformTime::Seconds();
	// The engine shifts every actor, component and render primitive by the difference in one go (UWorld::SetNewWorldOrigin);
	// the physics is in the map frame and does not move.
	// The scene's own shift is one render command (FScene::ApplyWorldOffset); two markers around it time it there.
	TSharedRef<double, ESPMode::ThreadSafe> RenderStart = MakeShared<double, ESPMode::ThreadSafe>(0.0);
	ENQUEUE_RENDER_COMMAND(SailingRecentreStart)([RenderStart](FRHICommandListImmediate&) { *RenderStart = FPlatformTime::Seconds(); });
	if (!World->SetNewWorldOrigin(To)) return false;
	ENQUEUE_RENDER_COMMAND(SailingRecentreEnd)([RenderStart](FRHICommandListImmediate&)
	{
		UE_LOG(LogSailing, Display, TEXT("World streaming: the scene's shift took %.2f ms of render thread"), (FPlatformTime::Seconds() - *RenderStart) * 1000.0);
	});
	PublishRenderOrigin();
	const double Ms = (FPlatformTime::Seconds() - Start) * 1000.0;
	LongestRecentreMs = FMath::Max(LongestRecentreMs, Ms);
	++Recentres;
	UE_LOG(LogSailing, Display, TEXT("World streaming: render origin to %.1f N %.1f E km (%.2f ms)"), NorthM / 1000.0, EastM / 1000.0, Ms);
	return true;
}

void ASailingGameMode::MarchWindow(double X, double Y)
{
	if (bWindowMarching || !Lake.IsLoaded()) return;
	bWindowMarching = true;
	++WindowMarches;
	const Sailing::FLakeTerrain Window = Lake.Terrain.WindowAround(X, Y, PhysicsWindow.HalfM);   // a snapshot: shares the tiles
	const bool bFetch = SeaFetch.IsValid();
	const bool bMask = Ocean.IsValid() && bOceanConfigured;
	const double SwellFrom = bMask ? Ocean->GetParams().SwellFromRad : 0.0, Hs = bMask ? Ocean->SignificantHeight() : 0.0;
	const double ShelterFrom = WeatherState.Wind.FromDegrees * Sailing::kDegToRad;
	const std::vector<Sailing::FShelterObstacle>* Obstacles = &ShelterObstacles;
	PendingWindow = Async(EAsyncExecution::ThreadPool, [Window, X, Y, bFetch, bMask, SwellFrom, Hs, ShelterFrom, Obstacles]()
	{
		const double Start = FPlatformTime::Seconds();
		FWindowGrids G;
		G.CenterX = X;
		G.CenterY = Y;
		G.ShelterFrom = ShelterFrom;
		if (bFetch)
		{
			TSharedPtr<Sailing::FSeaFetch, ESPMode::ThreadSafe> Fetch = MakeShared<Sailing::FSeaFetch, ESPMode::ThreadSafe>();
			Fetch->Build(Window);
			G.Fetch = Fetch;
		}
		if (bMask)
		{
			G.Mask = Sailing::FOcean::MakeMask(Window, SwellFrom, Hs);
			G.bMask = true;
		}
		G.Shelter = MakeShared<Sailing::FShelterMap>();
		G.Shelter->Build(Window, ShelterFrom, 40.0, Obstacles);
		G.Ms = (FPlatformTime::Seconds() - Start) * 1000.0;
		return G;
	});
}

void ASailingGameMode::UpdateStreaming()
{
	if (!Streamer.IsStarted()) return;
	const FVector2D At = GetFollowPoint();
	Streamer.Tick(At.X, At.Y);
	// The render frame: moved when the boat is kRecentreM from its origin, to the lattice point nearest her.
	const FVector2D Origin = SailingFrame::OriginM(GetWorld());
	double NX, NY;
	bool bMoved = false;
	if (Sailing::NeedsRecentre(Origin.X, Origin.Y, At.X, At.Y, NX, NY)) bMoved = RecentreAt(NX, NY);
	if (!Lake.bStreamed) return;
	// The physics' window: its grids, when a march has finished; a new march when the boat has left its core, or the
	// render origin has moved.
	if (bWindowMarching && PendingWindow.IsReady())
	{
		FWindowGrids G = PendingWindow.Consume();
		bWindowMarching = false;
		PhysicsWindow.CenterX = G.CenterX;
		PhysicsWindow.CenterY = G.CenterY;
		PhysicsWindow.bValid = true;
		if (G.Fetch.IsValid())
		{
			SeaFetch = G.Fetch;
			SeaMapKnots = -1.0;   // the sea map again on the new fetch
		}
		if (G.bMask && Ocean.IsValid()) Ocean->SetMask(MoveTemp(G.Mask));
		if (G.Shelter.IsValid())
		{
			Shelter = G.Shelter;
			Wind.SetShelter(Shelter.Get());
		}
		UE_LOG(LogSailing, Display, TEXT("World streaming: physics window at %.1f N %.1f E km marched in %.0f ms (worker)"), G.CenterX / 1000.0, G.CenterY / 1000.0, G.Ms);
	}
	if (!bWindowMarching && (bMoved || !PhysicsWindow.Contains(At.X, At.Y))) MarchWindow(At.X, At.Y);
	else if (!bWindowMarching && bWindowStale) MarchWindow(PhysicsWindow.CenterX, PhysicsWindow.CenterY);
	if (bWindowMarching) bWindowStale = false;
}

void ASailingGameMode::AdvanceClock(float DeltaSeconds)
{
	if (ClockFrame == GFrameCounter) return;
	ClockFrame = GFrameCounter;
	if (!GetWorld()->IsPaused() && !IsWorldHeld()) Clock.Advance(DeltaSeconds);
}

int32 ASailingGameMode::CentralEuropeanOffsetHours(const FDateTime& Date)
{
	// world-marseille: central European time, +1, and +2 from the last Sunday of March to the last Sunday of October (the
	// change is at 01:00 UTC; by the day is close enough for a sailing day's clock).
	auto LastSunday = [](int32 Year, int32 Month)
	{
		const FDateTime Last(Year, Month, FDateTime::DaysInMonth(Year, Month));
		return Last.GetDay() - (int32(Last.GetDayOfWeek()) + 1) % 7;   // EDayOfWeek: Monday 0 .. Sunday 6
	};
	const int32 Y = Date.GetYear(), M = Date.GetMonth(), D = Date.GetDay();
	const bool bSummer = (M > 3 && M < 10) || (M == 3 && D >= LastSunday(Y, 3)) || (M == 10 && D < LastSunday(Y, 10));
	return bSummer ? 2 : 1;
}

int32 ASailingGameMode::WorldIndexFromName(const FString& Name)
{
	// 0 or "Lake", 1 or "Galveston", 2 or "Gulf", 3 or "Marseille", 4 or "TexasCoast" (world streaming: the bay and the
	// Gulf passage as one streamed coast).
	if (Name.StartsWith(TEXT("Texas"), ESearchCase::IgnoreCase) || Name == TEXT("4")) return 4;
	if (Name.StartsWith(TEXT("Mars"), ESearchCase::IgnoreCase) || Name == TEXT("3")) return 3;
	return (Name.StartsWith(TEXT("Gulf"), ESearchCase::IgnoreCase) || Name == TEXT("2")) ? 2
		: ((Name.StartsWith(TEXT("Galv"), ESearchCase::IgnoreCase) || Name == TEXT("1")) ? 1 : 0);
}

const TCHAR* ASailingGameMode::WorldFileName(int32 World)
{
	if (World == 4) return TEXT("TexasCoast");
	return World == 3 ? TEXT("Marseille") : (World == 2 ? TEXT("GulfPassage") : (World == 1 ? TEXT("GalvestonBay") : TEXT("RayHubbard")));
}

const TCHAR* ASailingGameMode::WorldDisplayName(int32 World)
{
	if (World == 4) return TEXT("Texas coast (Clear Lake to Freeport, streamed)");
	return World == 3 ? TEXT("Marseille (Vieux-Port, Frioul, the Calanques)") : (World == 2 ? TEXT("Gulf passage (Galveston to Freeport)")
		: (World == 1 ? TEXT("Galveston Bay (Clear Lake, Kemah)") : TEXT("Lake Ray Hubbard (Rush Creek YC)")));
}

double ASailingGameMode::GetLocalHour() const
{
	const double Local = GetUnixTime() + UtcOffsetHours * 3600.0;
	double Hours = FMath::Fmod(Local / 3600.0, 24.0);
	return Hours < 0.0 ? Hours + 24.0 : Hours;
}

const FChartData& ASailingGameMode::GetChart() const
{
	if (!bChartTried && Lake.IsCoast())
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
			const FVector2D At = SailingFrame::ToMap(GetWorld(), P->GetActorLocation());
			X = At.X;
			Y = At.Y;
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
		const FVector At = SailingFrame::MapAnchor(GetWorld(), -Shown);   // the map's origin, in the render frame
		if (!TerrainActor->GetActorLocation().Equals(At, 0.1)) TerrainActor->SetActorLocation(At);
	}
}

bool ASailingGameMode::GetLaunchSpot(FLaunchSpot& Out) const
{
	if (NearShipStart) { Out = *NearShipStart; return true; }
	// -SailingStartAt=<north m>,<east m>,<heading deg> overrides (tests, screenshots).
	FString At;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingStartAt="), At, false))
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
		// A copy (it shares the heights): a streamed world's tiles may change while the worker reads. On a streamed world,
		// the physics' window.
		const Sailing::FLakeTerrain Terrain = DerivedTerrain(PhysicsWindow.CenterX, PhysicsWindow.CenterY);
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
			Map->Build(Terrain, From, 40.0, Obstacles);
			UE_LOG(LogSailing, Display, TEXT("Shelter map for wind from %.0f built in %.0f ms"), FMath::RadiansToDegrees(From), (FPlatformTime::Seconds() - Start) * 1000.0);
			return Map;
		});
	}
}

void ASailingGameMode::ApplyConditions(const FSailConditions& C)
{
	bPreviewing = false; // the preview, if any, is now the session's
	ApplyConditionsLocal(C);
	if (USailSessionSubsystem* Session = USailSessionSubsystem::Get(this)) Session->Active.Conditions = C;
}

void ASailingGameMode::PreviewConditions(const FSailConditions& C)
{
	if (!bPreviewing)
	{
		// What Back (or the gallery's close) goes back to: the weather's inputs as they are now.
		bPreviewing = true;
		FWeatherInputs& R = PreviewRestore;
		R.Preset = uint8(USailingSettings::Get()->WeatherPreset);
		R.StartHour = USailingSettings::Get()->StartHour;
		R.WindOverrideKnots = WindOverrideKnots;
		R.WindFromOverride = WindFromOverride;
		R.GustOverride = GustOverride;
		R.RealDayDate = RealDayDate;
		R.bRealDayHour = bRealDayHour;
		R.SessionDate = SessionDate;
		R.bSessionDate = bSessionDate;
		R.bWindArgsRead = bWindArgsRead;
	}
	ApplyConditionsLocal(C);
}

void ASailingGameMode::EndPreview(bool bKeep)
{
	if (!bPreviewing) return;
	bPreviewing = false;
	if (bKeep) return;
	const FWeatherInputs& R = PreviewRestore;
	USailingSettings::Get()->WeatherPreset = ESailingWeather(R.Preset);
	USailingSettings::Get()->StartHour = R.StartHour;
	WindOverrideKnots = R.WindOverrideKnots;
	WindFromOverride = R.WindFromOverride;
	GustOverride = R.GustOverride;
	RealDayDate = R.RealDayDate;
	bRealDayHour = R.bRealDayHour;
	SessionDate = R.SessionDate;
	bSessionDate = R.bSessionDate;
	bWindArgsRead = R.bWindArgsRead;
	ApplyWeatherSettings();
}

void ASailingGameMode::ApplyConditionsLocal(const FSailConditions& C)
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
	FParse::Value(SailingArgs::Dev(), TEXT("SailingWeatherTime="), WeatherOffset);
	WeatherStartTime = GetSimTime() - WeatherOffset;
	// The storm's timeline is set for the boat's start (the gust front reaches it at kFrontArrives); before Visual V5 it
	// was the map origin, so a start away from the club met the front a minute or more early.
	FLaunchSpot Start;
	const bool bStart = GetLaunchSpot(Start);
	// -SailingStormDelay=<s> (stills, Graphics G1): the front reaches the start that much later, so a capture a few seconds
	// in sees the storm still kilometres off (the point it reaches at kFrontArrives moved back up its track, toward 290 deg,
	// where it comes from).
	double StormDelay = 0.0;
	FParse::Value(SailingArgs::Dev(), TEXT("SailingStormDelay="), StormDelay);
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
	// Prologue step 4: in the scene's stand-in world its wind comes from where that world has the open water
	// (setting.world_stand_in.wind_from_deg); a scene runs its weather on cue (UpdateScene), not on the preset's timeline.
	Weather.SetPrevailingFrom(std::numeric_limits<double>::quiet_NaN());
	if (bScene)
	{
		const Sailing::FSceneSetting& Set = Scene.GetSetting();
		if (!Set.WorldStandIn.empty() && Set.WorldStandInWindFromDeg >= 0.0 && Settings->World == WorldIndexFromName(UTF8_TO_TCHAR(Set.WorldStandIn.c_str())))
			Weather.SetPrevailingFrom(Set.WorldStandInWindFromDeg);
		Weather.ClearCues();
		SceneWeatherSerial = -1;
	}

	// The clock: today's date (or -SailingDate=YYYY-MM-DD) at the start time, in this machine's time zone (Texas).
	FDateTime Date = bSessionDate ? SessionDate : FDateTime::Now();
	FString DateArg;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingDate="), DateArg))
	{
		TArray<FString> Parts;
		DateArg.ParseIntoArray(Parts, TEXT("-"));
		if (Parts.Num() == 3) Date = FDateTime(FCString::Atoi(*Parts[0]), FCString::Atoi(*Parts[1]), FCString::Atoi(*Parts[2]));
	}
	if (RealDay) Date = FDateTime(RealDay->Year(), RealDay->Month(), RealDay->DayOfMonth());
	UtcOffsetHours = Lake.TimeZone == TEXT("Europe/Paris") ? CentralEuropeanOffsetHours(Date)
		: FMath::RoundToInt((FDateTime::Now() - FDateTime::UtcNow()).GetTotalHours());
	DayOfYear = Date.GetDayOfYear();
	// W1: the wind's calibration and stability follow the month and the water (the lake, or the bay and the Gulf).
	Weather.SetClimate(Date.GetMonth(), Settings->World != 0);
	// docs/night-clouds/: the day's sunset (the sun's upper limb at the horizon, -0.83 deg with refraction), for the
	// cumulus that dies away after it.
	{
		auto Elev = [&](double Hour)
		{
			double El = 0.0, Az = 0.0;
			ASailingEnvironment::SunPosition(Hour, DayOfYear, Lake.Latitude, Lake.Longitude, UtcOffsetHours, El, Az);
			return El + 0.833;
		};
		double Lo = 12.0, Hi = 23.99;
		for (double Hour = 12.0; Hour < 24.0; Hour += 0.25)
		{
			if (Elev(Hour) < 0.0) { Lo = FMath::Max(12.0, Hour - 0.25); Hi = Hour; break; }
		}
		for (int32 I = 0; I < 20; ++I) { const double Mid = 0.5 * (Lo + Hi); (Elev(Mid) > 0.0 ? Lo : Hi) = Mid; }
		SunsetHour = 0.5 * (Lo + Hi);
		Weather.SetSunset(SunsetHour);
		UE_LOG(LogSailing, Display, TEXT("Sunset %02d:%02d local (day %d)"), int32(SunsetHour), int32(FMath::Fmod(SunsetHour, 1.0) * 60.0), DayOfYear);
	}
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
	// The project's own anti-aliasing (DefaultEngine.ini), read before any tier or row has set one.
	static const int32 ProjectAA = IConsoleManager::Get().FindConsoleVariable(TEXT("r.AntiAliasingMethod"))->GetInt();
	// Engine scalability: Low = engine Medium (no Lumen), Medium = High, High = Epic. Then the tier's own console
	// variables (VisualPipeline.h: cloud samples, virtual shadow maps, ray tracing, anti-aliasing and resolution).
	Scalability::FQualityLevels Levels = Scalability::GetQualityLevels();
	Levels.SetFromSingleQualityLevel(QualityScalabilityLevel(Quality));
	Levels.GlobalIlluminationQuality = QualityGIScalabilityLevel(Quality);
	// Settings > Graphics (Bean's playtest): a row set to a tier takes that tier's engine level for its group; Auto (-1)
	// and every measuring run keep the Quality tier's.
	const USailingSettings* S = USailingSettings::Get();
	auto Row = [](int32 V) { const int32 O = USailingSettings::Override(V); return O < 0 ? -1 : FMath::Clamp(O, 0, 3); };
	if (Row(S->ShadowQuality) >= 0) Levels.ShadowQuality = QualityScalabilityLevel(ESailingQuality(Row(S->ShadowQuality)));
	if (Row(S->LightingQuality) >= 0) Levels.GlobalIlluminationQuality = QualityGIScalabilityLevel(ESailingQuality(Row(S->LightingQuality)));
	if (Row(S->ReflectionQuality) >= 0) Levels.ReflectionQuality = QualityScalabilityLevel(ESailingQuality(Row(S->ReflectionQuality)));
	if (Row(S->FoliageQuality) >= 0) Levels.FoliageQuality = QualityScalabilityLevel(ESailingQuality(Row(S->FoliageQuality)));
	if (Row(S->ViewDistanceQuality) >= 0) Levels.ViewDistanceQuality = QualityScalabilityLevel(ESailingQuality(Row(S->ViewDistanceQuality)));
	FParse::Value(SailingArgs::Dev(), TEXT("SailingGI="), Levels.GlobalIlluminationQuality); // measuring
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
	// docs/high-headroom/: High's sun shadow pages at -0.5, not Epic scalability's -1.5 (the Medium tier's level uses 0). At
	// -1.5 the sun's map is about three times the screen's resolution each way; at -0.5 the deck, crew and marina shadows
	// look the same at full resolution, and the crew, slip and coast-day views save 0.9 to 1.3 ms of GPU (interleaved,
	// three pairs each). Only with the Shadows row on Auto (a row set to a tier keeps that tier's level); Ultra keeps -1.5.
	// (Set by code it outranks the scalability level from then on, so on any other tier or row it is put back to that
	// level's own value, BaseScalability.ini's -1.5 at Epic and Cinematic, 0 below, once this has set it.)
	{
		static bool bVsmBiasSet = false;
		const bool bHighAuto = Quality == ESailingQuality::High && Row(S->ShadowQuality) < 0;
		if (bHighAuto || bVsmBiasSet)
		{
			const float Bias = bHighAuto ? -0.5f : (Levels.ShadowQuality >= 3 ? -1.5f : 0.f);
			for (const TCHAR* Name : { TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"), TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectionalMoving") })
			{
				if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name); Var && Var->GetFloat() != Bias) Var->Set(Bias, ECVF_SetByCode);
			}
			bVsmBiasSet = true;
		}
	}
	// The Clouds row: that tier's cloud march (samples, tracing resolution, near-ray distance), whatever the Quality tier.
	if (Row(S->CloudQuality) >= 0)
	{
		auto Set = [](const TCHAR* Name, float Value) { if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name); Var && Var->GetFloat() != Value) Var->Set(Value, ECVF_SetByCode); };
		Set(TEXT("r.VolumetricCloud.DistanceToSampleMaxCount"), 15.f);   // the engine's own, unless the cloud tier sets it
		for (const FQualityCVar& C : QualityCVars(ESailingQuality(Row(S->CloudQuality))))
		{
			if (FCString::Strncmp(C.Name, TEXT("r.VolumetricCloud."), 18) == 0 || FCString::Strncmp(C.Name, TEXT("r.VolumetricRenderTarget."), 25) == 0) Set(C.Name, C.Value);
		}
	}
	// The Anti-aliasing row (0 off, 2 TAA, 4 TSR, 5 SMAA); -SailingAA below still wins for measuring. Low sets no method of
	// its own: back on Auto it gets the project's again.
	IConsoleVariable* AAVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.AntiAliasingMethod"));
	const int32 AARow = USailingSettings::Override(S->AntiAliasing);
	const int32 DLSS = S->DLSSMode();
	if (DLSS >= 0) AAVar->Set(4, ECVF_SetByCode);          // DLSS takes TSR's place as the temporal upscaler
	else if (AARow >= 0 && AARow < 10) AAVar->Set(AARow, ECVF_SetByCode);
	else if (Quality == ESailingQuality::Low) AAVar->Set(ProjectAA, ECVF_SetByCode);   // Auto, or DLSS where it can't run
	if (IConsoleVariable* DLSSVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.NGX.DLSS.Enable"))) DLSSVar->Set(DLSS >= 0 ? 1 : 0, ECVF_SetByCode);
	// The Motion blur row: on or off over the tier's camera look (ASailingEnvironment::ApplyCameraLook sets the amount).
	if (USailingSettings::Override(S->MotionBlur) >= 0)
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.MotionBlurQuality"))->Set(S->MotionBlur == 0 ? 0 : 4, ECVF_SetByCode);
	}
	// Measuring (Graphics G1): -SailingCloudMode=<r.VolumetricRenderTarget.Mode> -SailingCloudSamples=<view ray max>.
	int32 CloudMode = -1, CloudSamples = 0;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudMode="), CloudMode))
		if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricRenderTarget.Mode"))) Var->Set(CloudMode, ECVF_SetByCode);
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudSamples="), CloudSamples))
		if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"))) Var->Set(float(CloudSamples), ECVF_SetByCode);
	// Measuring (Visual V1): -SailingAA=<0 none, 2 TAA, 4 TSR, 5 SMAA> and -SailingScreenPct=<percent> override the tier.
	int32 AAOverride = -1, PctOverride = -1;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingAA="), AAOverride))
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.AntiAliasingMethod"))->Set(AAOverride, ECVF_SetByCode);
	}
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingScreenPct="), PctOverride))
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->Set(PctOverride, ECVF_SetByCode);
	}
	// Graphics G4: the player's resolution scale (Settings > Graphics) fixes the tier's percentage, governor off.
	// NVIDIA DLSS: its mode owns the render scale (the Render scale row and High's governor stand aside).
	else if (S->DLSSMode() >= 0)
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->Set(USailingSettings::DLSSScreenPercentage(S->DLSSMode()), ECVF_SetByCode);
	}
	else if (USailingSettings::Get()->FixedResolutionScale() > 0)
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->Set(float(USailingSettings::Get()->FixedResolutionScale()), ECVF_SetByCode);
	}
	USailingSettings::Get()->ApplyDisplay();
	int32 LumenHW = -1;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingLumenHW="), LumenHW))
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.RayTracing.Enable"))->Set(LumenHW, ECVF_SetByCode);
		IConsoleManager::Get().FindConsoleVariable(TEXT("r.Lumen.HardwareRayTracing"))->Set(LumenHW, ECVF_SetByCode);
	}
	// The Water row: that tier's water (rings and the V4 material), whatever the Quality tier.
	const ESailingQuality WaterTier = Row(S->WaterQuality) >= 0 ? ESailingQuality(Row(S->WaterQuality)) : Quality;
	for (TActorIterator<AWaterSurface> It(GetWorld()); It; ++It)
	{
		It->SetRingCount(WaterTier == ESailingQuality::Low ? 4 : 5);
		It->SetQualityTier(WaterTier == ESailingQuality::Low ? 0 : (WaterTier == ESailingQuality::Medium ? 1 : 2));
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
		// The Foliage row: that tier's share of the trees.
		const ESailingQuality TreeTier = Row(S->FoliageQuality) >= 0 ? ESailingQuality(Row(S->FoliageQuality)) : Quality;
		It->SetTreeFraction(TreeTier == ESailingQuality::Low ? 0.35f : (TreeTier == ESailingQuality::Medium ? 0.7f : 1.f));
	}
}

void ASailingGameMode::UpdateWeather(float DeltaSeconds)
{
	const bool bEasy = USailingSettings::Get()->IsEasy();
	const double Now = GetSimTime();
	WeatherState = Weather.Evaluate(Now - WeatherStartTime);
	WeatherState.Wind.SpeedKnots *= WindScale;
	// Reference captures: the wind of the real clip (direction it blows from, degrees true; gust intensity as a fraction).
	// Graphics G4: or the session's (InitGame); the command line wins.
	if (!bWindArgsRead)
	{
		bWindArgsRead = true;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingWindFrom="), WindFromOverride);
		FParse::Value(SailingArgs::Dev(), TEXT("SailingGust="), GustOverride);
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
		// Easy mode (EasyAssists.h): the gusts, puffs and shifts at a fraction of their strength.
		const double Scale = Sailing::FEasyAssists().WindVariabilityScale;
		WeatherState.Wind.GustIntensity *= Scale;
		if (WeatherState.Wind.PuffIntensity > 0.0) WeatherState.Wind.PuffIntensity *= Scale;
		WeatherState.Wind.ShiftDegrees *= Scale;
		WeatherState.Wind.PersistentShiftDegrees *= Scale;
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
		if (WeatherState.Front.bActive || WeatherState.bSquall) WeatherState.LocalizeStorm(BoatPos.X, BoatPos.Y, Now);
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
	// The wind lays the components' directions first (and, after a turn past 45 deg, again: in phase at the boat), then
	// the sea map reads them.
	WaveParams.HoldX = BoatPos.X;
	WaveParams.HoldY = BoatPos.Y;
	Waves.SetWind(WaveParams);
	UpdateSeaMap(WaveParams.WindSpeedKnots, WaveParams.WindFromDegrees);
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
		|| FMath::Abs(Sailing::WrapAngle((FromDegrees - SeaMapFrom) * kDegToRad)) > 11.25 * kDegToRad
		|| Waves.GetDirectionGeneration() != SeaMapDirections;
	if (bSeaMapBuilding || (!bFirst && !bStale)) return;
	SeaMapKnots = Knots;
	SeaMapFrom = FromDegrees;
	SeaMapDirections = Waves.GetDirectionGeneration();
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
	// The Gulf's swell runs in from the southeast; a world can give its own (Marseille: from the south-southwest).
	P.SwellFromRad = (FMath::IsFinite(Lake.SwellFromDeg) ? Lake.SwellFromDeg : 135.0) * kDegToRad;
	P.WindSeaHs = P.WindSeaTp = 0.0;
	// Prologue step 4: weather that brings its own sea (the mistral's short fetch-limited sea on an older sea from the
	// same way) instead of the Gulf's climatology.
	if (WeatherState.SwellHsM >= 0.0)
	{
		P.SwellHs = WeatherState.SwellHsM;
		P.SwellTp = WeatherState.SwellTpS;
		P.SwellFromRad = WeatherState.SwellFromDeg * kDegToRad;
		P.WindSeaHs = WeatherState.WindSeaHsM;
		P.WindSeaTp = WeatherState.WindSeaTpS;
	}
	float SwellArg = 0.f;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingSwell="), SwellArg)) P.SwellHs = SwellArg;
	const FOceanParams& Old = Ocean->GetParams();
	const bool bChanged = !bOceanConfigured || FMath::Abs(P.WindMs - Old.WindMs) > 0.4 || FMath::Abs(FMath::UnwindRadians(P.WindFromRad - Old.WindFromRad)) > 0.1
		|| P.SwellHs != Old.SwellHs || P.SwellTp != Old.SwellTp || P.SwellFromRad != Old.SwellFromRad || P.WindSeaHs != Old.WindSeaHs || P.WindSeaTp != Old.WindSeaTp;
	if (!bChanged) return;
	const double OldHs = Ocean->SignificantHeight();
	Ocean->Configure(P);
	// The depth limit depends on the wave height: rebuild the mask when it has changed noticeably.
	if (!bOceanConfigured || FMath::Abs(Ocean->SignificantHeight() - OldHs) > 0.15 * OldHs || P.SwellFromRad != Old.SwellFromRad)
	{
		// World streaming: a streamed world's mask is marched over the physics' window, on a worker once under way.
		if (!Lake.bStreamed || !bOceanConfigured) Ocean->BuildMask(DerivedTerrain(PhysicsWindow.CenterX, PhysicsWindow.CenterY));
		else bWindowStale = true;
	}
	bOceanConfigured = true;
}

void ASailingGameMode::StartPlay()
{
	// World streaming: the render frame starts on the lattice point nearest the launch spot when that is past the re-centre
	// distance (Bolivar Roads, the Gulf's offshore spots, a streamed coast's far end), before any actor begins play, so
	// everything is built in its frame from the start.
	PublishRenderOrigin();
	{
		FLaunchSpot Spot;
		double NX, NY;
		if (GetLaunchSpot(Spot) && Sailing::NeedsRecentre(0.0, 0.0, Spot.X, Spot.Y, NX, NY)) RecentreAt(NX, NY);
	}
	// Weather first: the boat reads the wind when it is spawned during Super::StartPlay.
	ApplyQualitySettings();
	ApplyWeatherSettings();
	Super::StartPlay();
	if (Lake.Navaids.Num() > 0)
	{
		GetWorld()->SpawnActor<ANavaidsActor>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);
	}
	// Wide World Rendering PR 3: the far lights, lit shores and horizon ships (-SailingNoFarLights compares).
	if ((Lake.FarLights.Lights.Num() > 0 || Lake.FarLights.Shore.Num() > 0 || Lake.FarLights.Lanes.Num() > 0)
		&& !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoFarLights")))
	{
		GetWorld()->SpawnActor<AFarLightsActor>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);
	}
	if (Lake.Marina.IsLoaded() && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoMarina")))
	{
		GetWorld()->SpawnActor<AMarinaActor>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);
	}
	// Graphics G7: the coast's moored boats and floating walkways (Inputs/g2/piers, <Lake>.piers).
	if (Lake.MooredBoats.Num() > 0 && USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ACoastMarinasActor>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);
	}
	if ((Lake.Bridges.Num() > 0 || Lake.Docks.Num() > 0) && USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ABridgesActor>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);
	}
	if (Lake.Landmarks.Num() > 0 && USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ALandmarksActor>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);
	}
	if (USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		GetWorld()->SpawnActor<ANightLightsActor>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);
	}
	// Other vessels and races. -SailingTraffic=0|1|2 overrides the setting; -SailingRace=<seconds to the start>.
	int32 TrafficArg = 0;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingTraffic="), TrafficArg)) USailingSettings::Get()->TrafficLevel = FMath::Clamp(TrafficArg, 0, 2);
	GetWorld()->SpawnActor<ATrafficManager>(SailingFrame::MapAnchor(GetWorld()), FRotator::ZeroRotator);

	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingBench="), BenchSeconds) && BenchSeconds > 0.f)
	{
		// Bench-fast: -SailingBenchWarmup=<s> (3 by default); -SailingBenchTrace keeps every frame from the start
		// (Saved/Bench/<shot>.frames.csv) to see where the frames settle.
		FParse::Value(SailingArgs::Dev(), TEXT("SailingBenchWarmup="), BenchWarmup);
		bBenchTrace = FParse::Param(SailingArgs::Dev(), TEXT("SailingBenchTrace"));
		UE_LOG(LogSailing, Display, TEXT("SailingBench: measuring %.1f s after %.1f s warm-up"), BenchSeconds, BenchWarmup);
		FrameTimes.Reserve(FMath::CeilToInt(BenchSeconds * 240.f));
		FParse::Value(SailingArgs::Dev(), TEXT("SailingRecord="), RecordSeconds);
		FParse::Value(SailingArgs::Dev(), TEXT("SailingRecordInterval="), RecordInterval);
		// -SailingSlowMo=<f>: the world's time dilated (bench clock, physics and materials alike), so -SailingRecord's
		// screenshots, slow on the Mac (about 0.8 s each), land a short game time apart (docs/far-cap-sprites: popping).
		float SlowMo = 1.f;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingSlowMo="), SlowMo) && SlowMo > 0.f && GetWorldSettings()) GetWorldSettings()->SetTimeDilation(SlowMo);
		FParse::Value(SailingArgs::Dev(), TEXT("SailingShot="), ShotName);
		NextFrameTime = BenchWarmup;
		// Soaks: -SailingExecAt=<s>:<cmd>[;<s>:<cmd>...] runs console commands at those seconds of the bench clock, '+' for
		// spaces (e.g. 600:memreport+-full;600:DumpLLM; docs/budget/mac-soak-high-2-2026-10-17.md).
		FString ExecArg;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingExecAt="), ExecArg, false))
		{
			TArray<FString> Parts;
			ExecArg.ParseIntoArray(Parts, TEXT(";"));
			for (const FString& Part : Parts)
			{
				FString At, Cmd;
				if (Part.Split(TEXT(":"), &At, &Cmd)) ExecAt.Emplace(FCString::Atof(*At), Cmd.Replace(TEXT("+"), TEXT(" ")));
			}
			ExecAt.StableSort([](const TPair<float, FString>& A, const TPair<float, FString>& B) { return A.Key < B.Key; });
		}
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
		bFixed = FParse::Param(SailingArgs::Dev(), TEXT("SailingScreenPct")) || FCString::Strifind(SailingArgs::Dev(), TEXT("SailingScreenPct=")) != nullptr
		|| FCString::Strifind(SailingArgs::Dev(), TEXT("SailingCapture=")) != nullptr;
	}
	if (USailingSettings::Get()->FixedResolutionScale() > 0 || USailingSettings::Get()->DLSSMode() >= 0) return;   // the player fixed it, or DLSS has
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
	if (Next != Now)
	{
		Pct->Set(Next, ECVF_SetByCode);
		UE_LOG(LogSailing, Display, TEXT("Resolution governor: %.0f%% -> %.0f%% (frame %.2f ms smoothed)"), Now, Next, GovernorMs);
	}
}

float ASailingGameMode::GetRenderScale() const
{
	return IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetFloat();
}

void ASailingGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	AdvanceClock(DeltaSeconds);
	{ SAILING_PERF_SCOPE(Streaming); UpdateStreaming(); }
	if (!GetWorld()->IsPaused() && !IsWorldHeld())
	{
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
	if (bBenchTrace)
	{
		TraceTimes.Add({ Elapsed, float(FApp::GetDeltaTime() * 1000.0), float(FPlatformTime::ToMilliseconds(GGameThreadTime)),
			float(FPlatformTime::ToMilliseconds(GRenderThreadTime)), float(FPlatformTime::ToMilliseconds(GRHIThreadTime)),
			float(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0))) });
	}
	// Visual V1: three frames profiled on the GPU (ProfileGPU) and summed into the plan's budget slices. They are taken
	// inside the measured window, at 40, 60 and 80% of it, so they see the same GPU state as the frames measured (after
	// the window the storm's cloud march sat in its slow phase on every launch: docs/budget/storm-high-2026-10-18.md).
	// A profiled frame and the dump hitch the frames that follow; those are left out of the frame and thread times.
	// -SailingNoGpuSlices skips it.
	static SailingArgs::FCachedFlag NoGpuSlicesArg(TEXT("SailingNoGpuSlices"));
	const bool bGpuSlices = !NoGpuSlicesArg.Get();
	const float ProfileAt[] = { 0.4f, 0.6f, 0.8f };
	constexpr int32 FramesSkippedPerProfile = 16; // the profiled frame lands 8-13 frames after the request (storm, High)
	// docs/bench-fullres/: a single run asked to be in front at BeginPlay, before its window was up, and on macOS 27 that
	// request is dropped (bench.json "foreground" 0 on every single run since the update; the list runs, asking once the
	// app is up, stayed in front). So through the warm-up the game raises its own window again every half second until
	// it is the frontmost app.
	if (Elapsed <= BenchWarmup && Elapsed >= NextBenchActivate && !FPlatformApplicationMisc::IsThisApplicationForeground())
	{
		NextBenchActivate = Elapsed + 0.5f;
#if PLATFORM_MAC
		FPlatformApplicationMisc::ActivateApplication();
#endif
		if (GEngine && GEngine->GameViewport && GEngine->GameViewport->GetWindow().IsValid()) GEngine->GameViewport->GetWindow()->BringToFront(true);
	}
	if (Elapsed > BenchWarmup && Elapsed <= BenchWarmup + BenchSeconds && GpuProfileSkipFrames > 0)
	{
		--GpuProfileSkipFrames;
		++GpuProfileSkipped;
	}
	else if (Elapsed > BenchWarmup && Elapsed <= BenchWarmup + BenchSeconds)
	{
		if (ClothSecondsAtStart < 0.0) ClothSecondsAtStart = ASailboatPawn::ClothCpuSeconds;
		if (WaterSecondsAtStart < 0.0) WaterSecondsAtStart = AWaterSurface::WaterCpuSeconds;
		if (WindMapSecondsAtStart < 0.0) WindMapSecondsAtStart = AWaterSurface::WindMapCpuSeconds;
		if (FarCapSecondsAtStart < 0.0) FarCapSecondsAtStart = AWaterSurface::FarCapCpuSeconds;
		if (!bSlicesStarted) { bSlicesStarted = true; FMemory::Memcpy(SlicesAtStart, SailingPerf::GSliceSeconds, sizeof(SlicesAtStart)); }
		// (The thread times read here are the previous frame's, all of them inside the window but the first.)
		ThreadTimes.Sample();
		FMemory::Memcpy(SlicesAtEnd, SailingPerf::GSliceSeconds, sizeof(SlicesAtEnd));
		// Real wall-clock frame time, not the (possibly clamped) game delta.
		FrameTimes.Add(static_cast<float>(FApp::GetDeltaTime()));
		ForegroundFrames += FPlatformApplicationMisc::IsThisApplicationForeground() ? 1 : 0;
		if (bGpuSlices && GpuProfilesRequested < UE_ARRAY_COUNT(ProfileAt) && Elapsed > BenchWarmup + BenchSeconds * ProfileAt[GpuProfilesRequested])
		{
			if (!GpuCapture.IsValid())
			{
				GpuCapture = MakeShared<FGpuProfileCapture>();
				GLog->AddOutputDevice(GpuCapture.Get());
			}
			++GpuProfilesRequested;
			GpuProfileSkipFrames = FramesSkippedPerProfile;
			GEngine->Exec(GetWorld(), TEXT("ProfileGPU"));
		}
	}

	if (RecordSeconds > 0.f && Elapsed >= NextFrameTime && Elapsed < BenchWarmup + RecordSeconds)
	{
		const FString FramePath = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/rec/frame_%04d.png"), FrameIndex++));
		FScreenshotRequest::RequestScreenshot(FramePath, /*bShowUI*/ true, /*bAddFilenameSuffix*/ false);
		NextFrameTime += RecordInterval;
	}

	if (bBenchTrace && Elapsed >= NextPosLog)
	{
		const APlayerController* PC = GetWorld()->GetFirstPlayerController();
		if (const APawn* Pawn = PC ? PC->GetPawn() : nullptr)
		{
			const FVector Pos = SailingFrame::ToMapCm(GetWorld(), Pawn->GetActorLocation()) / CmPerMeter;
			UE_LOG(LogSailing, Display, TEXT("SailingBench: at %.0f s: boat at %.1f N %.1f E, %.1f m since the last line"), Elapsed, Pos.X, Pos.Y,
				NextPosLog > 0.f ? FVector::Dist2D(Pos, LastPosLog) : 0.0);
			LastPosLog = Pos;
		}
		NextPosLog += 60.f;
	}

	while (NextExecAt < ExecAt.Num() && Elapsed >= ExecAt[NextExecAt].Key)
	{
		UE_LOG(LogSailing, Display, TEXT("SailingBench: at %.0f s: %s"), Elapsed, *ExecAt[NextExecAt].Value);
		GEngine->Exec(GetWorld(), *ExecAt[NextExecAt].Value);
		++NextExecAt;
	}

	// -SailingProfileGPU: dump one frame's GPU timings to the log (for tuning quality tiers).
	static SailingArgs::FOnce Profiled;
	if (!Profiled.Taken() && Elapsed > BenchWarmup + 3.f && FParse::Param(SailingArgs::Dev(), TEXT("SailingProfileGPU")))
	{
		Profiled.Take();
		GEngine->Exec(GetWorld(), TEXT("ProfileGPU"));
	}

	// The screenshot is taken after the measured window, and the stats a second later once it is written: inside the
	// window its frame (a render flush and a synchronous PNG compress, about 280 ms) set every view's max_ms and could
	// lift p99 on short runs (the PC's stream-run trace, Oct 20).
	const float End = BenchWarmup + BenchSeconds;
	if (!bScreenshotRequested && Elapsed > End)
	{
		const FString ShotPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/%s.png"), *ShotName));
		FScreenshotRequest::RequestScreenshot(ShotPath, /*bShowUI*/ true, /*bAddFilenameSuffix*/ false);
		bScreenshotRequested = true;
	}
	if (Elapsed > End + 1.f)
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
		Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"farcap_cpu_ms\":%.3f}"), (AWaterSurface::FarCapCpuSeconds - FarCapSecondsAtStart) * 1000.0 / N);
		Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"farcap_slots\":%d}"), AWaterSurface::FarCapSlotsHeld);
		// World streaming (docs/world-streaming): what the loader, the re-centre and the chunks did over the run.
		{
			int32 Chunks = 0, Made = 0, Dropped = 0, FarDropped = 0;
			for (TActorIterator<ALakeTerrainActor> It(GetWorld()); It; ++It)
			{
				Chunks = It->GetNumChunks(); Made = It->GetChunksMade(); Dropped = It->GetChunksDropped(); FarDropped = It->GetFarTilesDropped();
			}
			const FVector2D At = GetFollowPoint();
			Summary = Summary.LeftChop(1) + FString::Printf(TEXT(",\"world\":{\"streamed\":%s,\"tiles_resident\":%d,\"tile_mb\":%.1f,\"tile_loads\":%d,\"tile_drops\":%d,\"loader_longest_ms\":%.3f,\"recentres\":%d,\"recentre_longest_ms\":%.2f,\"window_marches\":%d,\"chunks\":%d,\"chunks_made\":%d,\"chunks_dropped\":%d,\"far_dropped\":%d,\"boat_n\":%.0f,\"boat_e\":%.0f}}"),
				Streamer.IsStreamed() ? TEXT("true") : TEXT("false"), Streamer.NumResident(), Streamer.ResidentBytes() / 1e6, Streamer.NumLoads(), Streamer.NumDrops(),
				Streamer.LongestTickMs(), Recentres, LongestRecentreMs, WindowMarches, Chunks, Made, Dropped, FarDropped, At.X, At.Y);
		}
	}
	// Perf 1: the threads' own times (game thread without its waits) and the game thread's named slices.
	if (const FString Threads = ThreadTimes.JsonFields(); !Threads.IsEmpty())
	{
		Summary = Summary.LeftChop(1) + TEXT(",") + Threads + TEXT(",\"gt\":") + SailingPerf::SlicesJson(SlicesAtStart, SlicesAtEnd, N) + TEXT("}");
	}
	if (!GpuSlicesJson.IsEmpty())
	{
		Summary = Summary.LeftChop(1) + TEXT(",") + GpuSlicesJson + FString::Printf(TEXT(",\"gpu_skipped_frames\":%d}"), GpuProfileSkipped);
	}
	// Easy mode's gate runs: the assists, the player's max heel and the crude tack (ASailboatPawn::EasyRunJson).
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (const ASailboatPawn* Player = Cast<ASailboatPawn>(PC->GetPawn())) Summary = Summary.LeftChop(1) + TEXT(",") + Player->EasyRunJson() + TEXT("}");
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
		FString Csv = TEXT("t_s,frame_ms,game_ms,render_ms,rhi_ms,gpu_ms\n");
		for (const FTraceFrame& F : TraceTimes)
		{
			Csv += FString::Printf(TEXT("%.4f,%.3f,%.3f,%.3f,%.3f,%.3f\n"), F.T, F.FrameMs, F.GameMs, F.RenderMs, F.RhiMs, F.GpuMs);
		}
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

bool ASailingGameMode::IsPrologueRun()
{
	static uint32 Gen = MAX_uint32;
	static bool bArg = false;
	if (Gen != SailingArgs::Generation())
	{
		Gen = SailingArgs::Generation();
		int32 V = 0;
		bArg = FParse::Value(SailingArgs::Dev(), TEXT("SailingPrologue="), V) && V != 0;
	}
	return bArg;
}

bool ASailingGameMode::LoadPrologue(Sailing::FScriptedScene& Out, FString* OutError)
{
	const FString Path = FPaths::ProjectContentDir() / TEXT("Prologue/prologue.json");
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		if (OutError) *OutError = FString::Printf(TEXT("%s not found"), *Path);
		return false;
	}
	std::string Error;
	if (!Out.LoadText(TCHAR_TO_UTF8(*Text), &Error))
	{
		if (OutError) *OutError = FString::Printf(TEXT("%s: %s"), *Path, UTF8_TO_TCHAR(Error.c_str()));
		return false;
	}
	return true;
}

bool ASailingGameMode::RestartScene(double& OutTwaDeg, double& OutKnots)
{
	if (!bScene || Scene.GetSteps().empty()) return false;
	if (Scene.IsActive()) Scene.RestartFromCheckpoint();
	const std::string& At = Scene.GetCheckpoint();
	const Sailing::FSceneStep* Pose = &Scene.GetSteps()[size_t(bSceneStarted ? 0 : Scene.CheckpointAtOrBefore(SceneStartStep))];
	for (const Sailing::FSceneStep& S : Scene.GetSteps()) if (!At.empty() && S.Id == At) Pose = &S;
	if (!Pose->bRestartPose) return false;
	OutTwaDeg = Pose->RestartTwaDeg;
	OutKnots = Pose->RestartSpeedKn;
	return true;
}

void ASailingGameMode::UpdateScene(const Sailing::FBoatModel& Boat, const Sailing::FSceneInput& Input)
{
	if (!bScene) return;
	const double Now = Boat.GetState().Time;
	if (!bSceneStarted)
	{
		bSceneStarted = true;
		SceneTime = Now;
		Scene.Start(Boat, WeatherState.Wind.SpeedKnots, SceneStartStep);
	}
	Scene.SetMeanWindKn(WeatherState.Wind.SpeedKnots);
	Scene.Update(Boat, Input, FMath::Max(0.0, Now - SceneTime));
	SceneTime = Now;
	// Step 4: the scene's weather cues (the squall on the "dump the main" step, its front reaching her as the step's gust
	// trigger is due; the break on the next), on the sim clock: weather time is sim time less WeatherStartTime.
	if (Scene.GetWeatherSerial() != SceneWeatherSerial)
	{
		SceneWeatherSerial = Scene.GetWeatherSerial();
		const Sailing::FSceneStep* Cue = Scene.GetWeatherStep();
		const Vec3 O = Boat.OriginPosition(), V = Boat.GetState().Velocity;
		Weather.ApplySceneCue(Cue ? Cue->WeatherCue : std::string(), Cue && Cue == Scene.GetStep() ? Cue->WeatherInSeconds : 0.0,
			Now - WeatherStartTime, O.X, O.Y, V.X, V.Y);
		UE_LOG(LogSailing, Display, TEXT("Prologue %.1f s: weather %hs (squall at %.0f s, clearing at %.0f s of sim time)"), Scene.GetElapsed(),
			Cue ? Cue->WeatherCue.c_str() : "none yet", Weather.GetSquallArrives() + WeatherStartTime, Weather.GetClearingStarts() + WeatherStartTime);
	}
	// The captain's voice: a recording named for the call id, if the pack has one (none yet: the caption carries it).
	if (Scene.GetCallSerial() != SceneCallSerial)
	{
		SceneCallSerial = Scene.GetCallSerial();
		const FString CallId = UTF8_TO_TCHAR(Scene.GetCallId().c_str());
		const FString Cue = CallId.Replace(TEXT("."), TEXT("_")).Replace(TEXT("-"), TEXT("_"));
		if (USoundBase* Voice = Cue.IsEmpty() ? nullptr : SailingSound::LoadPack(TEXT("Voice/") + Cue)) UGameplayStatics::PlaySound2D(this, Voice);
		UE_LOG(LogSailing, Display, TEXT("Prologue %.1f s: %s (repeat %d)"), Scene.GetElapsed(), *CallId, Scene.GetCallRepeats());
	}
	// The sim judged the scene finished: the save keeps it by id (rule 7), unless this run never writes the save.
	if (Scene.IsComplete() && !bSceneRecorded)
	{
		bSceneRecorded = true;
		const Sailing::FSceneResult& R = Scene.GetResult();
		UE_LOG(LogSailing, Display, TEXT("Prologue done in %.0f s: %d steps answered, %d by the crew, %d repeats"), R.Seconds, R.StepsPassed, R.StepsAssisted, R.Retries);
		if (!USailingSettings::IgnoresSavedChoices())
		{
			SailSaveStore::Progress().RecordScene(R, FDateTime::UtcNow());
			USailSessionSave::Get()->Commit();
		}
	}
}
