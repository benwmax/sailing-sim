#include "TrafficManager.h"
#include "BenchRunner.h"
#include "PerfScopes.h"
#include "SailSession.h"
#include "PowerVesselActor.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingSim.h"
#include "Kismet/GameplayStatics.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Async/ParallelFor.h"

using namespace Sailing;

namespace
{
	const TCHAR* SailNames[] = { TEXT("Kestrel"), TEXT("Blue Heron"), TEXT("Second Wind"), TEXT("Windsong"), TEXT("Tern"), TEXT("Osprey"),
		TEXT("Pelican"), TEXT("Sandpiper"), TEXT("Halcyon"), TEXT("Lone Star"), TEXT("Gulf Breeze"), TEXT("Skimmer") };
	const TCHAR* PowerNames[] = { TEXT("Runabout"), TEXT("Bass boat"), TEXT("Center console"), TEXT("Ski boat"), TEXT("Bay boat"), TEXT("Pontoon") };
	const FLinearColor HullColors[] = { FLinearColor(0.92f, 0.92f, 0.9f), FLinearColor(0.08f, 0.13f, 0.3f), FLinearColor(0.12f, 0.35f, 0.25f),
		FLinearColor(0.85f, 0.8f, 0.65f), FLinearColor(0.55f, 0.06f, 0.05f), FLinearColor(0.2f, 0.45f, 0.7f) };

	/** Whistle pitch by size (big ships sound low). */
	float HornHz(ETrafficKind Kind)
	{
		switch (Kind)
		{
		case ETrafficKind::Ship: return 110.f;
		case ETrafficKind::TugAndTow: return 190.f;
		case ETrafficKind::Trawler: return 260.f;
		case ETrafficKind::Committee: return 330.f;
		default: return 420.f;
		}
	}
}

ATrafficManager::ATrafficManager()
{
	PrimaryActorTick.bCanEverTick = true;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

ATrafficManager* ATrafficManager::Find(const UWorld* World)
{
	if (!World) return nullptr;
	TActorIterator<ATrafficManager> It(const_cast<UWorld*>(World));
	return It ? *It : nullptr;
}

void ATrafficManager::BeginPlay()
{
	Super::BeginPlay();
	ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FLakeData& Lake = GM->GetLake();
	// Perf 1: the AI sailboats step in parallel, so the current reads the clock taken on the game thread (it is the same
	// for the whole frame's steps: the player's boat, whose time it is, has already stepped).
	Sim.SetWorld(&GM->GetWind(), &GM->GetWaves(), Lake.IsLoaded() ? &Lake.Terrain : nullptr,
		[this, GM](double X, double Y) { const FLakeData& L = GM->GetLake(); return L.IsTidal() ? L.Tides.CurrentAt(X, Y, UnixNow) : Sailing::Vec3(); });
	Sim.ParallelFor = [](int Count, const std::function<void(int)>& Body) { ::ParallelFor(Count, [&Body](int32 I) { Body(I); }); };
	Sim.SetTime(GM->GetSimTime());
}

FVector2D ATrafficManager::PlayerPosition() const
{
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const ASailboatPawn* P = PC ? Cast<ASailboatPawn>(PC->GetPawn()) : nullptr;
	return P ? P->GetMapPosition() : FVector2D::ZeroVector;
}

FVesselSnapshot ATrafficManager::PlayerSnapshot() const
{
	FVesselSnapshot S;
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const ASailboatPawn* P = PC ? Cast<ASailboatPawn>(PC->GetPawn()) : nullptr;
	if (!P) return S;
	const FBoatModel& B = P->GetBoatModel();
	const Vec3 O = B.OriginPosition();
	S.Id = FTrafficSim::PlayerId;
	S.X = O.X;
	S.Y = O.Y;
	S.VX = B.GetState().Velocity.X;
	S.VY = B.GetState().Velocity.Y;
	S.Heading = B.GetState().Orientation.Heading();
	S.Length = B.GetConfig().LengthOverall;
	// Sails up with the engine running is power-driven (Rule 3(c)); the rules see what you are doing.
	S.Status = P->IsMotoring() ? EVesselStatus::PowerDriven : EVesselStatus::Sailing;
	S.Tack = B.GetState().WindwardSide;
	S.Name = "You";
	return S;
}

int32 ATrafficManager::AddSailboat(EBoatType Type, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const FString& Name)
{
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ASailboatPawn* Pawn = GetWorld()->SpawnActorDeferred<ASailboatPawn>(ASailboatPawn::StaticClass(), FTransform(FVector(X, Y, 0.0) * 100.0), nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (!Pawn) return -1;
	Pawn->bTrafficBoat = true;
	Pawn->TrafficHullColor = HullColors[Rng.UniformInt(0, UE_ARRAY_COUNT(HullColors) - 1)];
	Pawn->AutoPossessPlayer = EAutoReceiveInput::Disabled;
	Pawn->AutoPossessAI = EAutoPossessAI::Disabled;
	Pawn->FinishSpawning(FTransform(FVector(X, Y, 0.0) * 100.0));
	FBoatModel* Model = Pawn->InitTraffic(int32(Type), X, Y, Heading);
	// The actor owns the model; the simulation borrows it for as long as the actor lives.
	const int32 Id = Sim.AddSailboatModel(std::shared_ptr<FBoatModel>(Model, [](FBoatModel*) {}), std::move(Route), TCHAR_TO_UTF8(*Name));
	SailActors.Add(Id, Pawn);
	return Id;
}

int32 ATrafficManager::AddPower(ETrafficKind Kind, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const FString& Name)
{
	const int32 Id = Sim.AddPower(Kind, X, Y, Heading, std::move(Route), TCHAR_TO_UTF8(*Name));
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	APowerVesselActor* Actor = GetWorld()->SpawnActor<APowerVesselActor>(FVector(X, Y, 0.0) * 100.0, FRotator(0.0, FMath::RadiansToDegrees(Heading), 0.0), Params);
	if (Actor)
	{
		Actor->Build(Kind);
		PowerActors.Add(Id, Actor);
		// -SailingNearShip=<m>: the player is moved this far abeam of the first ship, on her heading (measuring stills).
		double NearM = 0.0;
		ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
		if (Kind == ETrafficKind::Ship && GM && !GM->NearShipStart && FParse::Value(SailingArgs::Dev(), TEXT("SailingNearShip="), NearM) && NearM > 0.0)
		{
			GM->NearShipStart = FLaunchSpot{ TEXT("Near ship"), X - NearM * FMath::Sin(Heading), Y + NearM * FMath::Cos(Heading), FMath::RadiansToDegrees(Heading) };
			if (ASailboatPawn* Player = Cast<ASailboatPawn>(UGameplayStatics::GetPlayerPawn(this, 0))) Player->ResetBoat();
		}
	}
	return Id;
}

void ATrafficManager::RemoveVessel(int32 Id)
{
	Sim.Remove(Id); // before the actor goes: the simulation borrows a sailboat's model from it
	if (TObjectPtr<ASailboatPawn>* P = SailActors.Find(Id)) { if (*P) (*P)->Destroy(); SailActors.Remove(Id); }
	if (TObjectPtr<APowerVesselActor>* A = PowerActors.Find(Id)) { if (*A) (*A)->Destroy(); PowerActors.Remove(Id); }
}

void ATrafficManager::ClearTraffic(bool bKeepRace)
{
	TArray<int32> Ids;
	for (const FTrafficVessel& V : Sim.GetVessels())
	{
		if (bKeepRace && (RaceBoats.Contains(V.Id) || V.Id == CommitteeId)) continue;
		Ids.Add(V.Id);
	}
	for (int32 Id : Ids) RemoveVessel(Id);
}

void ATrafficManager::Populate(int32 Level)
{
	PopulatedLevel = Level;
	ClearTraffic(true);
	if (Level <= 0) return;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FLakeData& Lake = GM->GetLake();
	const FLakeTerrain* T = Lake.IsLoaded() ? &Lake.Terrain : nullptr;
	const FVector2D C = PlayerPosition();
	auto U = [this]() { return Rng.Uniform01(); };
	auto Deep = [&](double Radius, double MinDepth, double& X, double& Y)
	{
		for (int32 Try = 0; Try < 20; ++Try)
		{
			if (T ? TrafficRoutes::DeepPoint(*T, Rng, C.X, C.Y, Radius, MinDepth, X, Y) : true)
			{
				if (!T) { const double R = Radius * FMath::Sqrt(U()), A = 2.0 * PI * U(); X = C.X + R * FMath::Cos(A); Y = C.Y + R * FMath::Sin(A); }
				if (FVector2D::Distance(FVector2D(X, Y), C) > 250.0) return true;
			}
		}
		return false;
	};
	auto Loop = [&](double X, double Y, double Radius, double MinDepth, int32 Count)
	{
		if (T) return TrafficRoutes::RandomLoop(*T, Rng, X, Y, Radius, MinDepth, Count);
		std::vector<std::pair<double, double>> R;
		for (int32 I = 0; I < Count; ++I) R.push_back({ C.X + (U() - 0.5) * 2.0 * Radius, C.Y + (U() - 0.5) * 2.0 * Radius });
		R.push_back({ X, Y });
		return R;
	};
	auto HeadingTo = [](double X, double Y, const std::vector<std::pair<double, double>>& R) { return R.empty() ? 0.0 : FMath::Atan2(R[0].second - Y, R[0].first - X); };

	const int32 Sails = Level == 1 ? 3 : 6, Powers = Level == 1 ? 2 : 4;
	const EBoatType Types[] = { EBoatType::J22, EBoatType::Catalina22, EBoatType::Catalina30, EBoatType::Hobie16, EBoatType::J22, EBoatType::Catalina30 };
	int32 NameIndex = Rng.UniformInt(0, UE_ARRAY_COUNT(SailNames) - 1);
	for (int32 I = 0; I < Sails; ++I)
	{
		const EBoatType Type = Types[I % UE_ARRAY_COUNT(Types)];
		const double Draft = FBoatConfig::Make(Type).Draft;
		double X, Y;
		if (!Deep(1500.0, Draft + 1.0, X, Y)) continue;
		auto Route = Loop(X, Y, 2000.0, Draft + 1.0, 4);
		AddSailboat(Type, X, Y, HeadingTo(X, Y, Route), Route, SailNames[(NameIndex++) % UE_ARRAY_COUNT(SailNames)]);
	}
	for (int32 I = 0; I < Powers; ++I)
	{
		double X, Y;
		if (!Deep(2500.0, 1.5, X, Y)) continue;
		auto Route = Loop(X, Y, 3000.0, 1.5, 5);
		const int32 Id = AddPower(ETrafficKind::Powerboat, X, Y, HeadingTo(X, Y, Route), Route, PowerNames[I % UE_ARRAY_COUNT(PowerNames)]);
		if (FTrafficVessel* V = Sim.Find(Id)) V->CruiseFraction = 0.5 + 0.5 * U();
	}
	if (!Lake.IsTidal() || !T) return;

	// The coast's working boats: shrimp trawlers in the open bay, and a towboat and ships in the ship channel.
	for (int32 I = 0; I < (Level == 1 ? 1 : 2); ++I)
	{
		double X, Y;
		if (!Deep(4000.0, 3.0, X, Y)) continue;
		auto Route = Loop(X, Y, 3000.0, 3.0, 3);
		AddPower(ETrafficKind::Trawler, X, Y, HeadingTo(X, Y, Route), Route, I == 0 ? TEXT("Shrimp trawler Miss Kemah") : TEXT("Shrimp trawler Bay Queen"));
	}
	// The Houston Ship Channel, found as the deep water from Bolivar Roads to Morgans Point.
	const FLaunchSpot* Bolivar = Lake.LaunchSpots.FindByPredicate([](const FLaunchSpot& S) { return S.Name.Contains(TEXT("Bolivar")); });
	const FTideStation* Morgans = nullptr;
	for (const FTideStation& S : Lake.Tides.HeightStations) if (FString(UTF8_TO_TCHAR(S.Name.c_str())).Contains(TEXT("Morgans"))) Morgans = &S;
	if (!Bolivar || !Morgans) return;
	std::vector<std::pair<double, double>> Channel = TrafficRoutes::DeepWaterPath(*T, Bolivar->X, Bolivar->Y, Morgans->X, Morgans->Y, 11.0);
	if (Channel.size() < 2)
	{
		UE_LOG(LogSailing, Warning, TEXT("Traffic: no ship channel found"));
		return;
	}
	// Out and back along it: a loop of the channel's legs.
	std::vector<std::pair<double, double>> Loop2 = Channel;
	for (int32 I = int32(Channel.size()) - 2; I > 0; --I) Loop2.push_back(Channel[I]);
	auto StartAlong = [&](double MinDist) -> int32
	{
		// A leg start at least MinDist from the player (ships appear in the distance, not on top of you).
		TArray<int32> Candidates;
		for (int32 I = 0; I + 1 < int32(Loop2.size()); ++I)
			if (FVector2D::Distance(FVector2D(Loop2[I].first, Loop2[I].second), C) > MinDist && FVector2D::Distance(FVector2D(Loop2[I].first, Loop2[I].second), C) < MinDist + 8000.0) Candidates.Add(I);
		return Candidates.Num() ? Candidates[Rng.UniformInt(0, Candidates.Num() - 1)] : 0;
	};
	const int32 Ships = Level == 1 ? 1 : 2;
	for (int32 I = 0; I < Ships + 1; ++I)
	{
		const bool bTug = I == Ships;
		// -SailingTrafficNear: ships start close by (screenshots and checks).
		const int32 Leg = StartAlong(FParse::Param(SailingArgs::Dev(), TEXT("SailingTrafficNear")) ? 600.0 : 3000.0);
		const auto& A = Loop2[Leg];
		const auto& B = Loop2[Leg + 1];
		const int32 Id = AddPower(bTug ? ETrafficKind::TugAndTow : ETrafficKind::Ship, A.first, A.second, FMath::Atan2(B.second - A.second, B.first - A.first), Loop2,
			bTug ? TEXT("Towboat Miss Lynn with two barges") : (I == 0 ? TEXT("Tanker Gulf Pride") : TEXT("Container ship Bayport Star")));
		if (FTrafficVessel* V = Sim.Find(Id)) V->RouteIndex = size_t(Leg + 1);
	}
	UE_LOG(LogSailing, Display, TEXT("Traffic: %d vessels, ship channel %d legs"), int32(Sim.GetVessels().size()), int32(Channel.size()) - 1);
}

void ATrafficManager::StartRace(int32 Boats, double SecondsToStart)
{
	EndRace();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const ASailboatPawn* Player = PC ? Cast<ASailboatPawn>(PC->GetPawn()) : nullptr;
	if (!GM || !Player) return;
	const FLakeTerrain* T = GM->GetLake().IsLoaded() ? &GM->GetLake().Terrain : nullptr;
	const EBoatType Type = Player->GetBoatModel().GetConfig().Type;
	const double Draft = Player->GetBoatModel().GetConfig().Draft + 1.0;
	const double WF = FMath::DegreesToRadians(GM->GetWind().GetParams().FromDegrees);
	const FVector2D P = PlayerPosition();
	const FVector2D W(FMath::Cos(WF), FMath::Sin(WF));
	// The line a little upwind of you, square to the wind; the longest beat that stays in deep water.
	const FVector2D Line = P + W * 250.0;
	double Beat = 0.0;
	for (const double Try : { 900.0, 700.0, 500.0, 350.0 })
	{
		const FVector2D Top = Line + W * Try, Bottom = Line - W * 120.0;
		if (!T || (TrafficRoutes::ClearPath(*T, Bottom.X, Bottom.Y, Top.X, Top.Y, Draft)
			&& TrafficRoutes::ClearPath(*T, Line.X - W.Y * 100.0, Line.Y + W.X * 100.0, Line.X + W.Y * 100.0, Line.Y - W.X * 100.0, Draft)))
		{
			Beat = Try;
			break;
		}
	}
	if (Beat <= 0.0)
	{
		Message(TEXT("No room to lay a course here: sail out to open water and try again"));
		return;
	}
	Race = FRaceRunner();
	Race.Course = FRaceCourse::WindwardLeeward(Line.X, Line.Y, WF, Beat, 120.0, 2);
	Race.TimeLimit = 3600.0;
	CommitteeId = AddPower(ETrafficKind::Committee, Race.Course.CommitteeX, Race.Course.CommitteeY, WF, {}, TEXT("Committee boat"));
	// Stills of a club start (Graphics G5): -SailingRaceBoats=<n> fills the line closer, -SailingRaceMixed mixes the club's
	// keelboats (a PHRF start) instead of one design.
	int32 BoatsWanted = Boats;
	FParse::Value(SailingArgs::Dev(), TEXT("SailingRaceBoats="), BoatsWanted);
	Boats = FMath::Clamp(BoatsWanted, 1, 16);
	const bool bMixed = FParse::Param(SailingArgs::Dev(), TEXT("SailingRaceMixed"));
	const EBoatType Mixed[] = { EBoatType::Catalina30, EBoatType::J22, EBoatType::Catalina22 };
	const double Spacing = FMath::Min(45.0, 200.0 / Boats);
	for (int32 I = 0; I < Boats; ++I)
	{
		const double Lateral = (I - 0.5 * (Boats - 1)) * Spacing;
		const FVector2D At = Line - W * (160.0 + 30.0 * (I % 2)) + FVector2D(-W.Y, W.X) * Lateral;
		const EBoatType BoatType = bMixed ? Mixed[I % UE_ARRAY_COUNT(Mixed)] : Type;
		const FString Name = FString::Printf(TEXT("%s %d"), UTF8_TO_TCHAR(BoatTypeName(BoatType)), I + 2);
		const int32 Id = AddSailboat(BoatType, At.X, At.Y, WF + 0.5 * PI, {}, Name);
		if (FTrafficVessel* V = Sim.Find(Id)) V->RaceEntry = Race.AddEntry(Id, TCHAR_TO_UTF8(*Name));
		RaceBoats.Add(Id);
	}
	Race.AddEntry(FTrafficSim::PlayerId, "You");
	Sim.SetRace(&Race);
	Race.Begin(Sim.GetTime(), SecondsToStart);
	bRace = true;
	bRaceLogged = false;
	const_cast<ASailboatPawn*>(Player)->BeginRun(TEXT("Race"));
	const_cast<ASailboatPawn*>(Player)->AddLogEvent(FString::Printf(TEXT("Race: start sequence begun, windward-leeward, %.0f m beats"), Beat));
	SignalsSeen = 0;

	// Marks: orange inflatable cylinders; the pin end a buoy with a flag.
	UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	UStaticMesh* Sphere = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	auto Mark = [&](UStaticMesh* Mesh, double X, double Y, const FVector& Size, double Z)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetupAttachment(RootComponent);
		C->SetStaticMesh(Mesh);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetAbsolute(true, true, true);
		C->SetWorldLocation(FVector(X, Y, Z) * 100.0);
		C->SetWorldScale3D(Size);
		C->RegisterComponent();
		if (UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Material, this))
		{
			Mid->SetVectorParameterValue(TEXT("Color"), FLinearColor(1.f, 0.33f, 0.02f));
			C->SetMaterial(0, Mid);
		}
		MarkMeshes.Add(C);
	};
	for (const FRaceMark& M : Race.Course.Marks)
	{
		// Each lap's marks are the same buoys: lay each position once.
		bool bDone = false;
		for (const FRaceMark& Prev : Race.Course.Marks) { if (&Prev == &M) break; if (FMath::Abs(Prev.X - M.X) < 1.0 && FMath::Abs(Prev.Y - M.Y) < 1.0) bDone = true; }
		if (!bDone) Mark(Cylinder, M.X, M.Y, FVector(1.6, 1.6, 2.2), 0.8);
	}
	Mark(Sphere, Race.Course.PinX, Race.Course.PinY, FVector(1.1), 0.3);
	Message(FString::Printf(TEXT("Race: windward-leeward, two laps, %.0f m beats. Start between the committee boat (starboard end) and the orange pin."), Beat));
}

void ATrafficManager::EndRace()
{
	if (!bRace && CommitteeId < 0) return;
	Sim.SetRace(nullptr);
	for (int32 Id : RaceBoats) RemoveVessel(Id);
	RaceBoats.Reset();
	if (CommitteeId >= 0) RemoveVessel(CommitteeId);
	CommitteeId = -1;
	for (UStaticMeshComponent* C : MarkMeshes) if (C) C->DestroyComponent();
	MarkMeshes.Reset();
	Race = FRaceRunner();
	bRace = false;
}

int32 ATrafficManager::GetRacePosition() const
{
	if (!bRace) return 0;
	const std::vector<FVesselSnapshot> None;
	auto Progress = [&](const FRaceEntry& E) -> double
	{
		if (E.bFinished) return 1e9 - E.FinishTime;
		double Pos = 0.0;
		FVector2D Where = E.VesselId == FTrafficSim::PlayerId ? PlayerPosition() : FVector2D::ZeroVector;
		if (const FTrafficVessel* V = Sim.Find(E.VesselId)) { const FVesselSnapshot S = V->Snapshot(); Where = FVector2D(S.X, S.Y); }
		double TX = 0.5 * (Race.Course.CommitteeX + Race.Course.PinX), TY = 0.5 * (Race.Course.CommitteeY + Race.Course.PinY);
		if (E.bStarted && E.NextMark < int(Race.Course.Marks.size())) { TX = Race.Course.Marks[E.NextMark].X; TY = Race.Course.Marks[E.NextMark].Y; }
		Pos = (E.bStarted ? 1.0 : 0.0) * 1e6 + E.NextMark * 1e5 - FVector2D::Distance(Where, FVector2D(TX, TY));
		return Pos;
	};
	const FRaceEntry* Me = Race.FindEntry(FTrafficSim::PlayerId);
	if (!Me) return 0;
	const double Mine = Progress(*Me);
	int32 Place = 1;
	for (const FRaceEntry& E : Race.Entries) if (&E != Me && Progress(E) > Mine) ++Place;
	return Place;
}

void ATrafficManager::Message(const FString& Text)
{
	Messages.Add({ Sim.GetTime(), Text });
	if (Messages.Num() > 30) Messages.RemoveAt(0);
	UE_LOG(LogSailing, Display, TEXT("Traffic: %s"), *Text);
}

void ATrafficManager::UpdateHorns(double Now)
{
	float Level = 0.f, Hz = 400.f;
	for (const FBlast& B : Blasts)
	{
		if (Now >= B.Start && Now < B.End && B.Level > Level) { Level = B.Level; Hz = B.Hz; }
	}
	Blasts.RemoveAll([&](const FBlast& B) { return B.End < Now; });
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (ASailboatPawn* P = Cast<ASailboatPawn>(PC->GetPawn())) P->SetHorn(Level, Hz);
	}
}

void ATrafficManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	SAILING_PERF_SCOPE(Traffic);
	ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ASailboatPawn* Player = PC ? Cast<ASailboatPawn>(PC->GetPawn()) : nullptr;
	if (!GM || !Player) return;

	const int32 Level = USailingSettings::Get()->TrafficLevel;
	if (Level != PopulatedLevel)
	{
		const bool bFirst = PopulatedLevel < 0;
		Populate(Level);
		float RaceIn = 0.f;
		if (bFirst && FParse::Value(SailingArgs::Dev(), TEXT("SailingRace="), RaceIn)) StartRace(5, RaceIn); // recordings and the gate
		// Graphics G4: a race session from the front end: five AI boats, the five-minute sequence.
		else if (const USailSessionSubsystem* Session = USailSessionSubsystem::Get(this); bFirst && Session && Session->bHasActive && Session->Active.Mode == ESailMode::Race)
		{
			StartRace(5, 300.0);
		}
	}

	// Perf 1 fix 6: no traffic, no race and no horn sounding: keep the clock and skip the rest (0.9 ms on the PC).
	if (Sim.GetVessels().empty() && !bRace && Blasts.IsEmpty())
	{
		Sim.SetTime(GM->GetSimTime());
		Player->GetMutableBoatModel().SetMovingObstacles({});
		return;
	}
	UnixNow = GM->GetUnixTime();
	const FVesselSnapshot Me = PlayerSnapshot();
	Sim.SetPlayer(Me, Player->GetBoatModel().GetConfig().Beam, true);
	// Run the traffic on the game's clock (the boat's physics time), a frame at a time.
	const double Lag = GM->GetSimTime() - Sim.GetTime();
	if (Lag > 2.0) Sim.SetTime(GM->GetSimTime() - 0.1); // after a pause or a reset: catch up rather than fast-forward
	{ SAILING_PERF_SCOPE(TrafficStep); Sim.Step(FMath::Clamp(GM->GetSimTime() - Sim.GetTime(), 0.0, 0.25)); }
	// Other hulls near the player's boat, for her contact physics.
	Player->GetMutableBoatModel().SetMovingObstacles(Sim.HullsNear(Me.X, Me.Y, 80.0, FTrafficSim::PlayerId));

	// Visuals.
	FVector Camera = FVector::ZeroVector;
	if (PC->PlayerCameraManager) Camera = PC->PlayerCameraManager->GetCameraLocation();
	const bool bDark = GM->IsDark();
	const float Time = float(Sim.GetTime());
	for (const FTrafficVessel& V : Sim.GetVessels())
	{
		if (V.IsSail()) { if (TObjectPtr<ASailboatPawn>* P = SailActors.Find(V.Id)) (*P)->SetTrafficControls(V.Controls); }
		else if (TObjectPtr<APowerVesselActor>* A = PowerActors.Find(V.Id)) (*A)->UpdateFrom(V, bDark, Camera, Time);
	}

	// What the player hears and sees: whistle signals within earshot, vessels keeping clear of her, collisions.
	const std::vector<FTrafficEvent>& Events = Sim.Events();
	for (const FTrafficEvent& E : Events)
	{
		if (E.Time <= LastEventTime) continue;
		const FTrafficVessel* V = Sim.Find(E.Vessel);
		const double Range = V ? FVector2D::Distance(FVector2D(V->Snapshot().X, V->Snapshot().Y), FVector2D(Me.X, Me.Y)) : 0.0;
		const bool bMine = E.Vessel == FTrafficSim::PlayerId || E.Other == FTrafficSim::PlayerId;
		if (E.Type == FTrafficEvent::Signal && V && Range < 3000.0)
		{
			Message(UTF8_TO_TCHAR(E.Text.c_str()));
			// A short blast is about one second, with a second between blasts (Rule 32).
			const float Loud = FMath::Clamp(1.f - float(Range) / 3000.f, 0.08f, 1.f);
			for (int32 B = 0; B < SoundSignalBlasts(E.Sound); ++B) Blasts.Add({ Sim.GetTime() + B * 2.0, Sim.GetTime() + B * 2.0 + 1.0, HornHz(V->Kind), Loud });
		}
		else if ((E.Type == FTrafficEvent::GiveWay || E.Type == FTrafficEvent::StandOnAction || E.Type == FTrafficEvent::Collision) && (bMine || Range < 600.0))
		{
			Message(UTF8_TO_TCHAR(E.Text.c_str()));
		}
	}
	if (!Events.empty()) LastEventTime = Events.back().Time;

	// The race committee's signals, with their sounds.
	if (bRace)
	{
		while (SignalsSeen < int32(Race.Signals.size()))
		{
			const FString Text = UTF8_TO_TCHAR(Race.Signals[SignalsSeen].second.c_str());
			Message(Text);
			const bool bLong = Text.Contains(TEXT("long sound"));
			if (Text.Contains(TEXT("sound"))) Blasts.Add({ Sim.GetTime(), Sim.GetTime() + (bLong ? 3.0 : 1.0), 330.f, 0.9f });
			++SignalsSeen;
		}
	}
	if (Sim.GetTime() - CoachTime > 0.25)
	{
		CoachTime = Sim.GetTime();
		const size_t Before = Coach.GetScores().size();
		Coach.Update(Sim.GetTime(), Me, Sim);
		// The rules judgments go in the log.
		for (size_t I = Before; I < Coach.GetScores().size(); ++I)
		{
			Player->AddLogEvent(FString::Printf(TEXT("Rules %+d: %s"), Coach.GetScores()[I].Points, UTF8_TO_TCHAR(Coach.GetScores()[I].Text.c_str())));
		}
	}
	if (bRace && Race.IsOver() && !bRaceLogged)
	{
		bRaceLogged = true;
		if (const FRaceEntry* E = Race.FindEntry(FTrafficSim::PlayerId))
		{
			Player->AddLogEvent(E->bFinished ? FString::Printf(TEXT("Race: finished %d of %d (%d:%02d)"), E->Place, int32(Race.Entries.size()),
				int32(E->FinishTime - Race.StartTime()) / 60, int32(E->FinishTime - Race.StartTime()) % 60)
				: FString::Printf(TEXT("Race: %s"), UTF8_TO_TCHAR(E->Status.c_str())));
		}
	}
	UpdateHorns(Sim.GetTime());
}
