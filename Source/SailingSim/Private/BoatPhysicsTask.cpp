// Perf 1 fix 2: see BoatPhysicsTask.h.
#include "BoatPhysicsTask.h"
#include "BenchRunner.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "TrafficManager.h"
#include "MarinaActor.h"
#include "NavaidsActor.h"
#include "WaterSurface.h"
#include "SailingEnvironment.h"
#include "GameFramework/HUD.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

using namespace Sailing;

namespace
{
	TAutoConsoleVariable<int32> CVarAsyncPhysics(TEXT("sailing.AsyncPhysics"), 1,
		TEXT("1: the player's boat steps on a task while the rest of TG_PrePhysics ticks; 0: inline in the pawn's tick."));

	/** Adds Prerequisite to Tick unless it is there already; true if it was added. */
	bool Depend(FTickFunction& Tick, UObject* Object, FTickFunction& Prerequisite)
	{
		for (const FTickPrerequisite& P : Tick.GetPrerequisites())
		{
			if (P.PrerequisiteTickFunction == &Prerequisite) return false;
		}
		Tick.AddPrerequisite(Object, Prerequisite);
		return true;
	}
}

void FBoatStepJob::Run() const
{
	for (int32 I = 0; I < Steps; ++I)
	{
		const FBoatControls Before = *Controls;
		const bool bAssist = bTrimAssist && Boat->GetState().Time - LastManualTrimTime > TrimIdleSeconds;
		if (bAssist || bSimple)
		{
			const FBoatControls Assisted = Trim->Update(*Boat, *Controls, StepDt);
			if (bAssist)
			{
				*Controls = Assisted;
			}
			else
			{
				// Simple layout: the crew handles traveler and sail shape; you keep the sheets and hiking.
				Controls->Traveler = Assisted.Traveler;
				Controls->Vang = Assisted.Vang;
				Controls->Cunningham = Assisted.Cunningham;
				Controls->Outhaul = Assisted.Outhaul;
				Controls->Backstay = Assisted.Backstay;
			}
			Controls->Tiller = Before.Tiller;
			Controls->bWingOnWing = Before.bWingOnWing;
		}
		if (Easy && EasyHelm && Easy->bEnabled) Boat->Step(StepDt, EasyHelm->Update(*Boat, *Controls, *Easy, StepDt), *Wind, Waves);
		else Boat->Step(StepDt, *Controls, *Wind, Waves);
	}
}

bool FBoatPhysicsTask::AsyncEnabled()
{
	static SailingArgs::FCachedFlag SyncArg(TEXT("SailingSyncPhysics"));
	const bool bSyncArg = SyncArg.Get();
	return !bSyncArg && CVarAsyncPhysics.GetValueOnGameThread() != 0;
}

bool FBoatPhysicsTask::Start(ASailboatPawn* Pawn, FTickFunction& Join, const FBoatStepJob& Job)
{
	Wait();
	bool bAsync = AsyncEnabled() && Job.Steps > 0 && Join.IsTickFunctionRegistered() && Join.IsTickFunctionEnabled();
	// A reader ordered just now ticks after the join from the next frame (this frame's tick graph is already built).
	if (bAsync && OrderReaders(Pawn, Join)) bAsync = false;
	bRanAsync = bAsync;
	if (!bAsync)
	{
		Job.Run();
		return false;
	}
	bPending = true;
	Task = UE::Tasks::Launch(TEXT("SailboatPhysics"), [Job]()
	{
		TRACE_CPUPROFILER_EVENT_SCOPE(Sailing_BoatPhysicsTask);
		Job.Run();
	});
	return true;
}

void FBoatPhysicsTask::Wait()
{
	if (!bPending) return;
	Task.Wait();
	bPending = false;
}

bool FBoatPhysicsTask::OrderReaders(ASailboatPawn* Pawn, FTickFunction& Join)
{
	const double Now = FPlatformTime::Seconds();
	if (Now - LastOrdered < 1.0) return false;
	LastOrdered = Now;
	UWorld* World = Pawn->GetWorld();
	if (!World) return false;
	bool bChanged = false;
	// Wind, waves and the clock are advanced in the game mode's tick: before the steps.
	if (ASailingGameMode* GM = World->GetAuthGameMode<ASailingGameMode>())
	{
		bChanged |= Depend(Pawn->PrimaryActorTick, GM, GM->PrimaryActorTick);
	}
	if (!Pawn->PrimaryActorTick.bHighPriority)
	{
		// Launch as early in TG_PrePhysics as its prerequisites allow, so the most work overlaps the steps.
		Pawn->PrimaryActorTick.SetPriorityIncludingPrerequisites(true);
	}
	// The pawn's own components (the camera boom, the crew's poseable meshes and grooms) after the rest of its tick.
	for (UActorComponent* C : Pawn->GetComponents())
	{
		if (C && C->PrimaryComponentTick.bCanEverTick) bChanged |= Depend(C->PrimaryComponentTick, Pawn, Join);
	}
	ATrafficManager* Traffic = nullptr;
	TArray<ASailboatPawn*> TrafficBoats;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* A = *It;
		if (A == Pawn || !A->PrimaryActorTick.bCanEverTick) continue;
		if (ASailboatPawn* Other = Cast<ASailboatPawn>(A))
		{
			if (Other->bTrafficBoat) TrafficBoats.Add(Other);
			continue;
		}
		if (ATrafficManager* T = Cast<ATrafficManager>(A)) Traffic = T;
		// Who reads the player's boat (its state, its clock through GetSimTime, its obstacles) or may reset it (the HUD's
		// scripted keys).
		const bool bReader = A->IsA<ATrafficManager>() || A->IsA<AMarinaActor>() || A->IsA<AHUD>() || A->IsA<AWaterSurface>()
			|| A->IsA<ASailingEnvironment>() || A->IsA<ANavaidsActor>();
		if (bReader) bChanged |= Depend(A->PrimaryActorTick, Pawn, Join);
	}
	// The AI boats draw what the traffic simulation stepped this frame (not a race against it).
	if (Traffic)
	{
		for (ASailboatPawn* B : TrafficBoats) Depend(B->PrimaryActorTick, Traffic, Traffic->PrimaryActorTick);
	}
	return bChanged;
}

void FBoatPhysicsTask::RegisterJoin(ASailboatPawn* Pawn, FBoatPhysicsJoinTick& Join, bool bRegister)
{
	if (bRegister)
	{
		if (Join.IsTickFunctionRegistered() || !Pawn->GetLevel()) return;
		Join.Pawn = Pawn;
		Join.TickGroup = TG_PostPhysics;
		Join.EndTickGroup = TG_PostPhysics;
		Join.bCanEverTick = true;
		Join.bStartWithTickEnabled = true;
		Join.bTickEvenWhenPaused = Pawn->PrimaryActorTick.bTickEvenWhenPaused;
		Join.RegisterTickFunction(Pawn->GetLevel());
		Join.AddPrerequisite(Pawn, Pawn->PrimaryActorTick);
	}
	else if (Join.IsTickFunctionRegistered())
	{
		Join.UnRegisterTickFunction();
	}
}

void FBoatPhysicsJoinTick::ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread, const FGraphEventRef& MyCompletionGraphEvent)
{
	if (IsValid(Pawn) && Pawn->PhysicsTask.IsPending())
	{
		Pawn->TickAfterPhysics(DeltaTime);
	}
}
