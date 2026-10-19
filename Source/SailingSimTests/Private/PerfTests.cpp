// Perf 1: the physics off the game thread must sail exactly as it did on it.
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/IConsoleManager.h"
#include "Async/ParallelFor.h"
#include "Tasks/Task.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "BoatPhysicsTask.h"
#include "FixedStepper.h"
#include "Ocean.h"
#include "SailboatPawn.h"
#include "Traffic.h"
#include "WaterSurface.h"
#include "Waves.h"
#include "Wind.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags PerfFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** A gusty breeze over a lake chop with the Gulf's FFT sea on top (so the shared wave caches are exercised). */
	struct FSea
	{
		static FWindParams Breeze()
		{
			FWindParams P;
			P.SpeedKnots = 14.0;
			P.FromDegrees = 200.0;
			P.GustIntensity = 0.25;
			P.ShiftDegrees = 10.0;
			P.Seed = 9;
			return P;
		}
		FWindField Wind{ Breeze() };
		FWaveField Waves{ 11 };
		FSea()
		{
			FWaveParams WP;
			WP.WindSpeedKnots = 14.0;
			WP.WindFromDegrees = 200.0;
			WP.FetchMeters = 6000.0;
			Waves.SetWind(WP);
			Waves.SnapToTarget();
			std::shared_ptr<FOcean> Ocean = std::make_shared<FOcean>();
			FOceanParams O;
			O.WindMs = 14.0 * kKnot;
			O.WindFromRad = 200.0 * kDegToRad;
			O.SwellHs = 1.0;
			Ocean->Configure(O);
			Waves.SetOcean(Ocean);
		}
	};

	/** Frame lengths that do not divide the step: 60, 45, 144 and 30 fps and a hitch (under the 12-step cap). */
	double FrameDt(int32 F)
	{
		static const double Dts[] = { 1.0 / 60.0, 1.0 / 45.0, 1.0 / 144.0, 1.0 / 60.0, 1.0 / 30.0, 0.0071, 1.0 / 60.0, 0.09 };
		return Dts[F % UE_ARRAY_COUNT(Dts)];
	}

	bool Same(const FBoatState& A, const FBoatState& B)
	{
		return A.Position.X == B.Position.X && A.Position.Y == B.Position.Y && A.Position.Z == B.Position.Z
			&& A.Velocity.X == B.Velocity.X && A.Velocity.Y == B.Velocity.Y && A.Velocity.Z == B.Velocity.Z
			&& A.Orientation.X == B.Orientation.X && A.Orientation.Y == B.Orientation.Y && A.Orientation.Z == B.Orientation.Z && A.Orientation.W == B.Orientation.W
			&& A.AngularVelocity.X == B.AngularVelocity.X && A.AngularVelocity.Y == B.AngularVelocity.Y && A.AngularVelocity.Z == B.AngularVelocity.Z
			&& A.BoomAngle == B.BoomAngle && A.JibAngle == B.JibAngle && A.RudderAngle == B.RudderAngle && A.CrewOffset == B.CrewOffset && A.Time == B.Time;
	}

	struct FSailor
	{
		FBoatModel Boat;
		FBoatControls Controls;
		FAutoTrim Trim;
		FFixedStepper Stepper;
		explicit FSailor(double Y = 0.0)
		{
			Boat.Reset(0.0, Y, -40.0 * kDegToRad, 2.0);
			Controls.MainSheet = 0.3;
			Controls.JibSheet = 0.3;
			Controls.Tiller = 0.05;
		}
		FBoatStepJob Job(const FSea& Sea, int32 Steps, bool bSimple)
		{
			FBoatStepJob J;
			J.Boat = &Boat;
			J.Controls = &Controls;
			J.Trim = &Trim;
			J.Wind = &Sea.Wind;
			J.Waves = &Sea.Waves;
			J.Steps = Steps;
			J.StepDt = Stepper.GetStepDt();
			J.bTrimAssist = !bSimple;
			J.LastManualTrimTime = 3.0; // the assist takes over 4 s after it, partway through
			J.TrimIdleSeconds = 4.0;
			J.bSimple = bSimple;
			return J;
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingTaskStepTest, "SailingSim.Physics.TaskStep", PerfFlags)
bool FSailingTaskStepTest::RunTest(const FString& Parameters)
{
	for (const bool bSimple : { false, true })
	{
		FSea Sea;
		// The pawn's loop as it was before Perf 1 (ASailboatPawn::Tick), on this thread.
		FSailor Ref;
		const double LastManual = 3.0, Idle = 4.0;
		// The same steps as a job on a task, as the pawn launches them now.
		FSailor Task;
		int32 RefSteps = 0, TaskSteps = 0;
		double Elapsed = 0.0;
		for (int32 F = 0; F < 600; ++F)
		{
			const double Dt = FrameDt(F);
			Elapsed += Dt;
			const int32 Steps = Ref.Stepper.Advance(Dt);
			for (int32 I = 0; I < Steps; ++I)
			{
				const FBoatControls Before = Ref.Controls;
				const bool bAssist = !bSimple && Ref.Boat.GetState().Time - LastManual > Idle;
				if (bAssist || bSimple)
				{
					const FBoatControls Assisted = Ref.Trim.Update(Ref.Boat, Ref.Controls, Ref.Stepper.GetStepDt());
					if (bAssist) Ref.Controls = Assisted;
					else
					{
						Ref.Controls.Traveler = Assisted.Traveler;
						Ref.Controls.Vang = Assisted.Vang;
						Ref.Controls.Cunningham = Assisted.Cunningham;
						Ref.Controls.Outhaul = Assisted.Outhaul;
						Ref.Controls.Backstay = Assisted.Backstay;
					}
					Ref.Controls.Tiller = Before.Tiller;
					Ref.Controls.bWingOnWing = Before.bWingOnWing;
				}
				Ref.Boat.Step(Ref.Stepper.GetStepDt(), Ref.Controls, Sea.Wind, &Sea.Waves);
			}
			RefSteps += Steps;

			const int32 TaskFrameSteps = Task.Stepper.Advance(Dt);
			TestEqual(TEXT("The same steps each frame"), TaskFrameSteps, Steps);
			const FBoatStepJob Job = Task.Job(Sea, TaskFrameSteps, bSimple);
			UE::Tasks::Launch(TEXT("TaskStepTest"), [Job]() { Job.Run(); }).Wait();
			TaskSteps += TaskFrameSteps;
			// The world between frames (on the game thread, as the game mode does): the sea builds.
			Sea.Waves.Update(Dt);
		}
		TestTrue(FString::Printf(TEXT("Task and inline steps leave the boat identical (simple %d)"), bSimple), Same(Ref.Boat.GetState(), Task.Boat.GetState()));
		const FBoatControls& RC = Ref.Controls;
		const FBoatControls& TC = Task.Controls;
		TestTrue(TEXT("Controls identical (the assist trimmed the same)"), RC.MainSheet == TC.MainSheet && RC.JibSheet == TC.JibSheet && RC.Traveler == TC.Traveler
			&& RC.Vang == TC.Vang && RC.Cunningham == TC.Cunningham && RC.Outhaul == TC.Outhaul && RC.Backstay == TC.Backstay && RC.Tiller == TC.Tiller);
		TestEqual(TEXT("Same number of steps"), TaskSteps, RefSteps);
		TestEqual(TEXT("Still 120 Hz"), Task.Stepper.GetStepDt(), 1.0 / 120.0);
		// The hitch frames (0.09 s) are under the 12-step cap, so every step of the elapsed time ran.
		TestEqual(TEXT("120 steps a second of frames"), double(TaskSteps), FMath::FloorToDouble(Elapsed * 120.0 + 1e-6), 1.0);
		// (Not frozen: on her fixed tiller she rounds up into irons, sooner or later as the swell takes her; since
		// docs/wave-physics/ its slope pushes her too, and 20 m was the edge.)
		TestTrue(FString::Printf(TEXT("She sailed (%.1f m)"), Task.Boat.GetState().Position.LengthXY()), Task.Boat.GetState().Position.LengthXY() > 10.0);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingParallelBoatsTest, "SailingSim.Physics.ParallelBoatsShareTheSea", PerfFlags)
bool FSailingParallelBoatsTest::RunTest(const FString& Parameters)
{
	// Four boats stepping at once on one wind and sea (the FFT grid cache and the band list shared) end exactly where
	// each does stepping alone.
	constexpr int32 N = 4;
	FSea SeaA, SeaB;
	TArray<TUniquePtr<FSailor>> Alone, Together;
	for (int32 K = 0; K < N; ++K) { Alone.Add(MakeUnique<FSailor>(K * 30.0)); Together.Add(MakeUnique<FSailor>(K * 30.0)); }
	for (int32 F = 0; F < 480; ++F)
	{
		const double Dt = FrameDt(F);
		for (int32 K = 0; K < N; ++K) Alone[K]->Job(SeaA, Alone[K]->Stepper.Advance(Dt), false).Run();
		TArray<UE::Tasks::FTask> Tasks;
		for (int32 K = 0; K < N; ++K)
		{
			const FBoatStepJob Job = Together[K]->Job(SeaB, Together[K]->Stepper.Advance(Dt), false);
			Tasks.Add(UE::Tasks::Launch(TEXT("ParallelBoatsTest"), [Job]() { Job.Run(); }));
		}
		UE::Tasks::Wait(Tasks);
		SeaA.Waves.Update(Dt);
		SeaB.Waves.Update(Dt);
	}
	for (int32 K = 0; K < N; ++K)
	{
		TestTrue(FString::Printf(TEXT("Boat %d identical in parallel"), K), Same(Alone[K]->Boat.GetState(), Together[K]->Boat.GetState()));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTrafficParallelStepTest, "SailingSim.Traffic.ParallelStep", PerfFlags)
bool FTrafficParallelStepTest::RunTest(const FString& Parameters)
{
	// The AI fleet stepped with ParallelFor sails exactly as stepped in order.
	auto Build = [](FTrafficSim& Sim, const FSea& Sea)
	{
		Sim.SetWorld(&Sea.Wind, &Sea.Waves, nullptr);
		for (int32 I = 0; I < 6; ++I)
		{
			const double X = 120.0 * I, Y = 60.0 * (I % 3);
			std::vector<std::pair<double, double>> Route = { { X + 600.0, Y + 300.0 }, { X + 200.0, Y - 500.0 }, { X, Y } };
			const EBoatType Type = I % 3 == 0 ? EBoatType::J22 : (I % 3 == 1 ? EBoatType::Catalina22 : EBoatType::Catalina30);
			Sim.AddSailboat(Type, X, Y, FMath::Atan2(Route[0].second - Y, Route[0].first - X), Route, "Boat");
		}
		Sim.AddPower(ETrafficKind::Powerboat, 300.0, -300.0, 0.3, { { 900.0, 200.0 }, { 300.0, -300.0 } }, "Runabout");
	};
	FSea SeaA, SeaB;
	FTrafficSim InOrder, Parallel;
	Build(InOrder, SeaA);
	Build(Parallel, SeaB);
	int32 Calls = 0;
	Parallel.ParallelFor = [&Calls](int Count, const std::function<void(int)>& Body) { ++Calls; ::ParallelFor(Count, [&Body](int32 I) { Body(I); }); };
	for (int32 F = 0; F < 1800; ++F)
	{
		const double Dt = FrameDt(F);
		InOrder.Step(Dt);
		Parallel.Step(Dt);
		SeaA.Waves.Update(Dt);
		SeaB.Waves.Update(Dt);
	}
	TestTrue(TEXT("The parallel path ran"), Calls > 100);
	const std::vector<FTrafficVessel>& A = InOrder.GetVessels();
	const std::vector<FTrafficVessel>& B = Parallel.GetVessels();
	if (!TestEqual(TEXT("Same fleet"), int32(B.size()), int32(A.size()))) return false;
	double Moved = 0.0;
	for (size_t I = 0; I < A.size(); ++I)
	{
		const FVesselSnapshot SA = A[I].Snapshot(), SB = B[I].Snapshot();
		TestTrue(FString::Printf(TEXT("Vessel %d identical"), int32(I)), SA.X == SB.X && SA.Y == SB.Y && SA.Heading == SB.Heading && SA.VX == SB.VX && SA.VY == SB.VY);
		if (A[I].IsSail()) TestTrue(FString::Printf(TEXT("Sailboat %d state identical"), int32(I)), Same(A[I].Boat->GetState(), B[I].Boat->GetState()));
		Moved += FMath::Sqrt(FMath::Square(SA.X - (120.0 * I)) + FMath::Square(SA.Y));
	}
	TestTrue(TEXT("The fleet sailed"), Moved > 300.0);
	TestEqual(TEXT("Same events"), int32(Parallel.Events().size()), int32(InOrder.Events().size()));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingAsyncPawnTest, "SailingSim.Smoke.AsyncPhysicsMatchesSync", PerfFlags)
bool FSailingAsyncPawnTest::RunTest(const FString& Parameters)
{
	// The pawn in a world ticked frame by frame, its steps inline and then on the task with the join tick: the same boat,
	// drawn where she is.
	IConsoleVariable* Async = IConsoleManager::Get().FindConsoleVariable(TEXT("sailing.AsyncPhysics"));
	if (!TestNotNull(TEXT("sailing.AsyncPhysics exists"), Async)) return false;
	const int32 Was = Async->GetInt();
	auto Sail = [this, Async](int32 bOn, FBoatState& Out, FVector& OutLocation, bool& bOutRanAsync)
	{
		Async->Set(bOn, ECVF_SetByCode);
		UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingAsyncWorld"));
		FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
		Context.SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL());
		World->GetWorldSettings()->NotifyBeginPlay();
		World->SpawnActor<AWaterSurface>(FVector(0.f, 0.f, 50.f), FRotator::ZeroRotator);
		ASailboatPawn* Boat = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
		bOutRanAsync = false;
		if (TestNotNull(TEXT("Boat spawns"), Boat))
		{
			TestTrue(TEXT("The join tick is registered"), Boat->PhysicsJoinTick.IsTickFunctionRegistered());
			for (int32 Frame = 0; Frame < 360; ++Frame)
			{
				++GFrameCounter;
				World->Tick(LEVELTICK_All, float(FrameDt(Frame)));
				TestFalse(TEXT("No task left running after the frame"), Boat->PhysicsTask.IsPending());
				bOutRanAsync |= Boat->PhysicsTask.RanAsync();
			}
			Out = Boat->GetBoatModel().GetState();
			OutLocation = Boat->GetActorLocation();
		}
		World->EndPlay(EEndPlayReason::Quit);
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	};
	FBoatState Sync, Tasked;
	FVector SyncAt, TaskedAt;
	bool bSyncAsync = false, bTaskAsync = false;
	Sail(0, Sync, SyncAt, bSyncAsync);
	Sail(1, Tasked, TaskedAt, bTaskAsync);
	Async->Set(Was, ECVF_SetByCode);
	TestFalse(TEXT("sailing.AsyncPhysics 0 steps inline"), bSyncAsync);
	TestTrue(TEXT("sailing.AsyncPhysics 1 steps on the task"), bTaskAsync);
	TestTrue(TEXT("The same boat either way"), Same(Sync, Tasked));
	TestTrue(TEXT("Drawn where she is (the join applied the state)"), SyncAt.Equals(TaskedAt, 0.01));
	TestTrue(TEXT("She sailed"), Tasked.Position.LengthXY() > 5.0);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
