#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "Wind.h"
#include "CrewPose.h"
#include "CrewMotion.h"
#include "CrewAnimInstance.h"
#include "SailboatPawn.h"
#include "WaterSurface.h"
#include "SailingSim.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "GameFramework/WorldSettings.h"
#include "Components/SkeletalMeshComponent.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags CrewMotionFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** SK_Sailor and the MetaHumans where they are installed (rig, name). */
	struct FCrewBody { const USkeletalMesh* Mesh; FCrewRig Rig; FString Name; };
	void CrewBodies(FAutomationTestBase& Test, TArray<FCrewBody>& Bodies)
	{
		if (const USkeletalMesh* Sailor = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Crew/SK_Sailor.SK_Sailor"))) Bodies.Add({ Sailor, FCrewRig(), TEXT("SK_Sailor") });
		if (!IFileManager::Get().DirectoryExists(*FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Crew/MetaHumans"))))
		{
			Test.AddWarning(TEXT("Content/Crew/MetaHumans is not installed: SK_Sailor only"));
			return;
		}
		for (int32 Role = 0; Role < NumMetaHumanRoles; ++Role)
		{
			USkeletalMesh *Body = nullptr, *Face = nullptr, *Outfit = nullptr;
			if (!LoadMetaHumanCrew(Role, Body, Face, Outfit)) continue;
			FCrewBody& B = Bodies.AddDefaulted_GetRef();
			B.Mesh = Body;
			BuildCrewRig(Body, B.Rig);
			B.Name = MetaHumanRoleName(Role);
		}
	}

	/** The figure's component frame for a placement, as ASailboatPawn::UpdateCrewFigures sets it (no blending). */
	FTransform FigureFrame(const FCrewPlacement& Pl, const FCrewRig* Rig)
	{
		const FQuat Facing(FRotator(0.f, Pl.Yaw, Pl.Roll));
		const FQuat CompRot = Rig ? Facing * Rig->Frame.Inverse() : Facing;
		const FVector Location = Rig ? Pl.Pelvis * Sailing::CmPerMeter - CompRot.RotateVector(Rig->Pelvis) : Pl.Pelvis * Sailing::CmPerMeter - FVector(0.f, 0.f, 93.f);
		return FTransform(CompRot, Location);
	}

	/** A short lake chop under the boat: roll, pitch and heave with their rates and accelerations, about a heeled mean. */
	FCrewBoatMotion Chop(double T, double MeanHeelDeg, double Scale = 1.0)
	{
		const double W1 = 2.0 * PI * 0.45, W2 = 2.0 * PI * 1.1, W3 = 2.0 * PI * 0.6, W4 = 2.0 * PI * 0.5;
		const double R1 = FMath::DegreesToRadians(8.0) * Scale, R2 = FMath::DegreesToRadians(3.0) * Scale, P1 = FMath::DegreesToRadians(4.0) * Scale, H = 0.25 * Scale;
		const double Roll = FMath::DegreesToRadians(MeanHeelDeg) + R1 * FMath::Sin(W1 * T) + R2 * FMath::Sin(W2 * T);
		const double RollRate = R1 * W1 * FMath::Cos(W1 * T) + R2 * W2 * FMath::Cos(W2 * T);
		const double RollAcc = -R1 * W1 * W1 * FMath::Sin(W1 * T) - R2 * W2 * W2 * FMath::Sin(W2 * T);
		const double Pitch = P1 * FMath::Sin(W3 * T + 1.0), PitchRate = P1 * W3 * FMath::Cos(W3 * T + 1.0), PitchAcc = -P1 * W3 * W3 * FMath::Sin(W3 * T + 1.0);
		FCrewBoatMotion M;
		const FQuat Q(FRotator(FMath::RadiansToDegrees(Pitch), 0.0, FMath::RadiansToDegrees(Roll)));
		M.Gravity = Q.UnrotateVector(FVector(0.0, 0.0, -9.81));
		M.Omega = FVector(RollRate, PitchRate, 0.0);
		M.Alpha = FVector(RollAcc, PitchAcc, 0.0);
		M.Accel = Q.UnrotateVector(FVector(0.0, 0.0, -H * W4 * W4 * FMath::Sin(W4 * T)));
		return M;
	}
}

// Crew C1: the physics step exports what the crew feel. Afloat at rest the centre of gravity's acceleration reads zero; in a
// steady turn it is the centripetal acceleration (turn rate times speed) toward the inside of the turn.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBoatAccelerationTest, "SailingSim.Physics.BoatAcceleration", CrewMotionFlags)
bool FSailingBoatAccelerationTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	{
		FWindParams Calm;
		Calm.SpeedKnots = 0.0;
		FWindField Wind(Calm);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		FBoatControls Controls;
		for (int32 I = 0; I < 15 * 120; ++I) Boat.Step(PhysicsDt, Controls, Wind);
		const Vec3& A = Boat.GetTelemetry().AccelBody;
		TestTrue(FString::Printf(TEXT("At rest the acceleration reads zero (%.3f m/s^2)"), A.Length()), A.Length() < 0.03);
		TestTrue(TEXT("At rest no angular acceleration"), Boat.GetTelemetry().AngularAccelBody.Length() < 0.03);
	}
	FWindParams WP;
	WP.SpeedKnots = 12.0;
	FWindField Wind(WP);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, -100.0 * kDegToRad, 2.5);
	FBoatControls Controls;
	Controls.MainSheet = 0.5;
	Controls.JibSheet = 0.5;
	for (int32 I = 0; I < 20 * 120; ++I) Boat.Step(PhysicsDt, Controls, Wind);
	Controls.Tiller = 0.35;
	double SumA = 0.0, SumC = 0.0;
	for (int32 I = 0; I < 6 * 120; ++I)
	{
		Boat.Step(PhysicsDt, Controls, Wind);
		if (I < 3 * 120) continue;
		const FBoatState& S = Boat.GetState();
		const Vec3 V = S.Orientation.Unrotate(S.Velocity);
		SumA += Boat.GetTelemetry().AccelBody.Y;
		SumC += S.AngularVelocity.Z * V.X;
	}
	AddInfo(FString::Printf(TEXT("Turning: lateral acceleration %.3f, turn rate x speed %.3f m/s^2"), SumA / (3 * 120), SumC / (3 * 120)));
	TestTrue(TEXT("The boat is turning"), FMath::Abs(SumC) / (3 * 120) > 0.1);
	TestTrue(TEXT("The lateral acceleration is the centripetal one (within 30 %)"), FMath::Abs(SumA - SumC) < 0.3 * FMath::Abs(SumC));
	return true;
}

// Crew C1: a heel step. The sailor's balance waits out their reaction time, then settles onto the new lean without
// overshoot (critically damped), within 2 % by a second, at 60 Hz and at an AI boat's 15 Hz.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewBalanceStepTest, "SailingSim.Visual.CrewBalanceStep", CrewMotionFlags)
bool FVisualCrewBalanceStepTest::RunTest(const FString& Parameters)
{
	for (const float Hz : { 60.f, 15.f })
	{
		for (const float Lag : { 0.1f, 0.3f })
		{
			FCrewBalance B;
			B.Lag = Lag;
			B.Reset(FVector(0.0, 0.0, -9.81));
			const double Step = FMath::DegreesToRadians(15.0);
			const FVector Tilted(0.0, 9.81 * FMath::Sin(Step), -9.81 * FMath::Cos(Step));
			const float Dt = 1.f / Hz;
			float Peak = 0.f, At1 = 0.f, BeforeLag = 0.f;
			for (int32 K = 1; K <= FMath::RoundToInt(3.f * Hz); ++K)
			{
				B.Step(Dt, Tilted);
				const float T = K * Dt;
				Peak = FMath::Max(Peak, B.Roll);
				if (T <= Lag - Dt) BeforeLag = FMath::Max(BeforeLag, FMath::Abs(B.Roll));
				if (FMath::IsNearlyEqual(T, 1.f, 0.5f * Dt) || (T > 1.f && At1 == 0.f)) At1 = B.Roll;
			}
			const FString Case = FString::Printf(TEXT("%.0f Hz, lag %.1f s"), Hz, Lag);
			TestTrue(Case + FString::Printf(TEXT(": still before the reaction time (%.4f rad)"), BeforeLag), BeforeLag < 0.01 * Step);
			TestTrue(Case + FString::Printf(TEXT(": no overshoot (peak %.2f of the step)"), Peak / Step), Peak <= Step * 1.005f);
			TestTrue(Case + FString::Printf(TEXT(": settled within 2 %% by 1 s (%.3f of the step)"), At1 / Step), FMath::Abs(At1 - Step) < 0.02 * Step);
			TestTrue(Case + TEXT(": ends on the step"), FMath::Abs(B.Roll - Step) < 1e-3);
		}
	}
	// A slam: the load spikes for a tenth of a second; the give comes and goes without bouncing back past zero.
	FCrewBalance B;
	B.Lag = 0.15f;
	B.Reset(FVector(0.0, 0.0, -9.81));
	float Max = 0.f, Min = 0.f;
	for (int32 K = 1; K <= 180; ++K)
	{
		const float T = K / 60.f;
		B.Step(1.f / 60.f, FVector(0.0, 0.0, T > 0.5f && T < 0.6f ? -9.81 * 2.0 : -9.81));
		Max = FMath::Max(Max, B.Squat);
		Min = FMath::Min(Min, B.Squat);
	}
	TestTrue(FString::Printf(TEXT("A slam makes the knees and spine give (%.2f)"), Max), Max > 0.2f);
	TestTrue(FString::Printf(TEXT("... and they recover (%.3f at the end, %.3f below zero at most)"), B.Squat, Min), FMath::Abs(B.Squat) < 0.01f && Min > -0.01f);
	return true;
}

// Crew C1: in a lake chop (roll 8 + 3 degrees, pitch 4, heave) on a heeled boat, every sailor keeps their eyes within a
// few degrees of level while their body goes with the boat; without the reaction layer their head would tilt with it.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewHeadLevelTest, "SailingSim.Visual.CrewHeadLevel", CrewMotionFlags)
bool FVisualCrewHeadLevelTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	TArray<FCrewBody> Bodies;
	CrewBodies(*this, Bodies);
	if (!TestTrue(TEXT("SK_Sailor loads"), Bodies.Num() > 0)) return false;
	const FBoatConfig Cfg;
	const FBoatModel Model(Cfg);
	for (const FCrewBody& Body : Bodies)
	{
		const FCrewRig* Rig = Body.Rig.bValid ? &Body.Rig : nullptr;
		for (int32 I = 0; I < Cfg.CrewCount; ++I)
		{
			if (Rig && Body.Name != MetaHumanRoleName(I == Cfg.CrewCount - 1 ? 0 : (I == Cfg.CrewCount - 2 ? 1 : 2))) continue;
			for (const double Hike : { 0.0, 1.0 })
			{
				FCrewPlaceInput Place;
				Place.Config = &Cfg;
				Place.Index = I;
				Place.CrewOffset = Cfg.CrewSitOut * 0.8 + Hike * Cfg.CrewHikeOut;
				FCrewPlacement Pl;
				CrewPlacement(Place, Pl);
				double Worst[2] = { 0.0, 0.0 }, Mean[2] = { 0.0, 0.0 };
				int32 Count = 0;
				for (const bool bReact : { true, false })
				{
					FCrewMotionState State;
					FCrewMotionInput In;
					In.Params = Pl.Params;
					In.ToBoat = FigureFrame(Pl, Rig);
					In.SeatFromCG = Pl.Pelvis - FVector(Model.GetCenterOfGravity().X, Model.GetCenterOfGravity().Y, Model.GetCenterOfGravity().Z);
					In.Gaze = FVector(2500.0, 0.0, 80.0);
					In.bReact = bReact;
					In.Seed = uint32(I);
					TArray<FTransform> CS;
					Count = 0;
					for (int32 K = 0; K < 8 * 60; ++K)
					{
						const double T = K / 60.0;
						In.Motion = Chop(T, -15.0 * Hike - 5.0); // heeled away from the crew, more when they hike
						In.Time = float(T);
						CrewMotionUpdate(State, In, 1.f / 60.f);
						CrewMotionPose(Body.Mesh->GetRefSkeleton(), Rig, &Cfg, Model.HullDepth(), State, In, CS);
						if (T < 1.0) continue;
						// The head's up against the world's up, in the figure's frame.
						const int32 Head = Body.Mesh->GetRefSkeleton().FindBoneIndex(TEXT("head"));
						const FQuat Frame = Rig ? Rig->Frame : FQuat::Identity;
						const FQuat RestHead = Rig ? Rig->RestCS[Head].GetRotation() : FQuat::Identity;
						FQuat RestQ = RestHead;
						if (!Rig)
						{
							TArray<FTransform> Rest;
							const FReferenceSkeleton& Ref = Body.Mesh->GetRefSkeleton();
							Rest.SetNum(Ref.GetNum());
							for (int32 B = 0; B < Ref.GetNum(); ++B) Rest[B] = Ref.GetParentIndex(B) == INDEX_NONE ? Ref.GetRefBonePose()[B] : Ref.GetRefBonePose()[B] * Rest[Ref.GetParentIndex(B)];
							RestQ = Rest[Head].GetRotation();
						}
						// Level: the eyes' line (the head's right) horizontal. (Nodding to a boat-fixed point is the gaze, not a tilt.)
						const FQuat D = CS[Head].GetRotation() * RestQ.Inverse();
						const FVector Right = D.RotateVector(Frame.RotateVector(FVector::RightVector)).GetSafeNormal();
						const FVector World = In.ToBoat.InverseTransformVectorNoScale(-In.Motion.Gravity.GetSafeNormal());
						const double Tilt = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(FMath::Abs(FVector::DotProduct(Right, World)), 0.0, 1.0)));
						const int32 R = bReact ? 0 : 1;
						Worst[R] = FMath::Max(Worst[R], Tilt);
						Mean[R] += Tilt;
						++Count;
					}
				}
				const FString Case = FString::Printf(TEXT("%s, crew %d (stance %d, hike %.0f)"), *Body.Name, I, int32(Pl.Params.Stance), Hike);
				Mean[0] /= Count;
				Mean[1] /= Count;
				AddInfo(Case + FString::Printf(TEXT(": eye line tilt mean %.1f, worst %.1f deg (without the reaction layer %.1f, %.1f)"), Mean[0], Worst[0], Mean[1], Worst[1]));
				TestTrue(Case + FString::Printf(TEXT(": the head stays within 5 degrees of level (worst %.1f)"), Worst[0]), Worst[0] < 5.0);
				// Facing inboard the heel pitches them (their eye line stays level anyway); facing forward it rolls them.
				if (Mean[1] > 5.0) TestTrue(Case + TEXT(": ... where the stance alone tilts it with the boat"), Mean[1] > 3.0 * Mean[0]);
			}
		}
	}
	return true;
}

// Crew C1: with the reaction layer on (chop, a hard heel that sets them bracing, a tack's crouch under the boom), no heel or
// toe of any boat's crew goes inside the boat.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewMotionFeetTest, "SailingSim.Visual.CrewMotionFeet", CrewMotionFlags)
bool FVisualCrewMotionFeetTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	TArray<FCrewBody> Bodies;
	CrewBodies(*this, Bodies);
	if (!TestTrue(TEXT("SK_Sailor loads"), Bodies.Num() > 0)) return false;
	int32 Checked = 0, Braced = 0, Ducked = 0;
	for (int32 Type = 0; Type < int32(EBoatType::Count); ++Type)
	{
		const FBoatConfig Cfg = FBoatConfig::Make(EBoatType(Type));
		const FBoatModel Model(Cfg);
		const FVector CG(Model.GetCenterOfGravity().X, Model.GetCenterOfGravity().Y, Model.GetCenterOfGravity().Z);
		const int32 N = Cfg.CrewCount;
		for (int32 I = 0; I < N; ++I)
		{
			const bool bHelm = I == N - 1;
			// Sitting up and hiked on either tack; mid-tack with the boom coming over.
			struct FCase { double Offset; double BoomAngle, BoomRate, Rate; double HeelDeg; const TCHAR* Name; double Twa = 0.8, Turn = 0.0; };
			const double Out = Cfg.CrewSitOut * 0.8 + 0.5 * FMath::Max(Cfg.CrewHikeOut, 0.1);
			const FCase Cases[] = {
				{ Out, 0.3, 0.0, 0.0, -12.0, TEXT("starboard rail") }, { -Out, -0.3, 0.0, 0.0, 12.0, TEXT("port rail") },
				{ Out, 0.3, 0.0, 0.0, -42.0, TEXT("knocked down to 42 degrees") },
				{ 0.05, 0.08, -0.4, 0.0, 0.0, TEXT("tacking under the boom"), 0.1, 0.2 },
				{ 0.05, -0.1, 0.5, -0.5, 0.0, TEXT("gybing"), 3.0, -0.15 } };
			for (const FCase& C : Cases)
			{
				FCrewPlaceInput Place;
				Place.Config = &Cfg;
				Place.Index = I;
				Place.CrewOffset = C.Offset;
				Place.WindwardSide = C.Offset >= 0.0 ? 1 : -1;
				Place.BoomAngle = C.BoomAngle;
				Place.BoomRate = C.BoomRate;
				Place.OffsetRate = C.Rate;
				Place.TrueWindAngle = C.Twa;
				Place.TurnRate = C.Turn;
				FCrewPlacement Pl;
				CrewPlacement(Place, Pl);
				if (Pl.Duck > 0.3f) ++Ducked;
				for (const FCrewBody& Body : Bodies)
				{
					const FCrewRig* Rig = Body.Rig.bValid ? &Body.Rig : nullptr;
					if (Rig && Body.Name != MetaHumanRoleName(bHelm ? 0 : (I == N - 2 ? 1 : 2))) continue;
					FCrewMotionState State;
					FCrewMotionInput In;
					In.Params = Pl.Params;
					In.Duck = Pl.Duck;
					In.ToBoat = FigureFrame(Pl, Rig);
					In.SeatFromCG = Pl.Pelvis - CG;
					CrewDerivedAttachPoints(Cfg, Pl.Pelvis.X, In.Attach);
					In.Seed = uint32(I);
					if (Pl.Params.Stance != ECrewStance::Trapeze && Pl.Params.Stance != ECrewStance::Righting && Pl.Params.Stance != ECrewStance::DinghyHike)
					{
						In.Hands.Mode[0] = In.Hands.Mode[1] = FCrewHands::EMode::Knee;
					}
					TArray<FTransform> CS;
					bool bBraced = false;
					for (int32 K = 0; K < 4 * 30; ++K)
					{
						const double T = K / 30.0;
						In.Motion = Chop(T, C.HeelDeg, 0.6);
						In.Time = float(T);
						CrewMotionUpdate(State, In, 1.f / 30.f);
						if (K % 10 != 9) continue;
						CrewMotionPose(Body.Mesh->GetRefSkeleton(), Rig, &Cfg, Model.HullDepth(), State, In, CS);
						bBraced |= State.bBracing;
						FVector Feet[2][2];
						CrewSolePoints(Body.Mesh->GetRefSkeleton(), Rig, CS, Feet);
						for (int32 Sd = 0; Sd < 2; ++Sd)
						{
							for (int32 P = 0; P < 2; ++P)
							{
								const FVector At = In.ToBoat.TransformPosition(Feet[Sd][P]) / CmPerMeter;
								++Checked;
								if (CrewInsideBoat(Cfg, Model.HullDepth(), At + FVector(0.0, 0.0, 0.015)))
								{
									AddError(FString::Printf(TEXT("%s, %s crew %d (%s, stance %d): %s %s inside the boat at (%.2f, %.2f, %.2f) m"), ANSI_TO_TCHAR(BoatTypeName(Cfg.Type)),
										*Body.Name, I, C.Name, int32(Pl.Params.Stance), Sd == 0 ? TEXT("left") : TEXT("right"), P == 0 ? TEXT("heel") : TEXT("toe"), At.X, At.Y, At.Z));
								}
							}
						}
					}
					Braced += bBraced ? 1 : 0;
				}
			}
		}
	}
	AddInfo(FString::Printf(TEXT("%d heel and toe points checked; %d sailors braced, %d placements ducked under the boom"), Checked, Braced, Ducked));
	TestTrue(TEXT("Someone braces in the knockdown"), Braced > 0);
	TestTrue(TEXT("Someone ducks under the boom"), Ducked > 0);
	return true;
}

// Crew C1: in a world the crew are posed by their animation node (the joints off the game thread), the helm's hand goes to
// the tiller extension, and an AI boat's crew update at 15 Hz.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSmokeCrewAnimationTest, "SailingSim.Smoke.CrewAnimation", CrewMotionFlags)
bool FSmokeCrewAnimationTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingCrewWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->GetWorldSettings()->NotifyBeginPlay();
	World->SpawnActor<AWaterSurface>(FVector(0.f, 0.f, 50.f), FRotator::ZeroRotator);
	ASailboatPawn* Boat = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	ASailboatPawn* Ai = World->SpawnActorDeferred<ASailboatPawn>(ASailboatPawn::StaticClass(), FTransform(FVector(9000.f, 0.f, 0.f)));
	if (Ai)
	{
		// As ATrafficManager spawns one.
		Ai->bTrafficBoat = true;
		Ai->AutoPossessPlayer = EAutoReceiveInput::Disabled;
		Ai->AutoPossessAI = EAutoPossessAI::Disabled;
		Ai->FinishSpawning(FTransform(FVector(9000.f, 0.f, 0.f)));
		Ai->InitTraffic(0, 90.0, 0.0, 0.0);
	}
	if (TestNotNull(TEXT("Boat spawns"), Boat) && TestNotNull(TEXT("AI boat spawns"), Ai))
	{
		for (int32 Frame = 0; Frame < 120; ++Frame)
		{
			++GFrameCounter;
			World->Tick(LEVELTICK_All, 1.f / 60.f);
		}
		const TArray<TObjectPtr<USkeletalMeshComponent>>& Crew = Boat->GetCrewMeshes();
		TestTrue(TEXT("The boat has crew"), Crew.Num() > 0);
		for (const USkeletalMeshComponent* Figure : Crew)
		{
			const UCrewAnimInstance* Anim = Figure ? Cast<UCrewAnimInstance>(Figure->GetAnimInstance()) : nullptr;
			TestNotNull(TEXT("Each sailor is posed by the crew motion node"), Anim);
			if (!Figure || !Figure->GetSkeletalMeshAsset()) continue;
			// Seated, not standing in the reference pose: the pelvis over the knees, not above the feet.
			const FVector Knee = Figure->GetBoneLocation(TEXT("calf_l"), EBoneSpaces::ComponentSpace);
			const FVector Thigh = Figure->GetBoneLocation(TEXT("thigh_l"), EBoneSpaces::ComponentSpace);
			TestTrue(FString::Printf(TEXT("%s sits (thigh to knee %.0f cm up)"), *Figure->GetName(), Knee.Z - Thigh.Z), FMath::Abs(Knee.Z - Thigh.Z) < 25.0);
		}
		for (const USkeletalMeshComponent* Figure : Ai->GetCrewMeshes())
		{
			if (Figure) TestEqual(TEXT("AI crew animate at 15 Hz"), Figure->PrimaryComponentTick.TickInterval, 1.f / 15.f, 1e-4f);
		}
	}
	World->EndPlay(EEndPlayReason::Quit);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
