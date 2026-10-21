#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "Wind.h"
#include "CrewPose.h"
#include "CrewMotion.h"
#include "CrewClips.h"
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

// Crew C1b: the idle clips stay within what the stances allow. Every baked frame, either way round, keeps each joint within
// its limit and every weight shift the bake marked leans the way it says. Then on SK_Sailor (and the MetaHumans) in each
// idling stance, through chop and a change of heel, the clip layer keeps each joint within its limit and moves the limbs
// only a little from where the same sailor without clips has them: the feet stay planted.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewClipLimitsTest, "SailingSim.Visual.CrewClipLimits", CrewMotionFlags)
bool FVisualCrewClipLimitsTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	TestTrue(TEXT("There are clips"), CrewClips::Num() >= 6);
	int32 Frames = 0, Onsets = 0, OnsetsRight = 0;
	for (int32 C = 0; C < CrewClips::Num(); ++C)
	{
		const FCrewClipInfo& Info = CrewClips::Info(C);
		for (const bool bMirror : { false, true })
		{
			float WorstRatio = 0.f, WorstGaze = 0.f;
			for (float T = 0.f; T <= CrewClips::Duration(C); T += 1.f / 30.f)
			{
				FVector J[CrewClips::MaxJoints];
				float Yaw, Pitch;
				CrewClips::Sample(C, T, bMirror, J, Yaw, Pitch);
				for (int32 K = 0; K < CrewClips::NumJoints(); ++K)
				{
					WorstRatio = FMath::Max(WorstRatio, float(FMath::RadiansToDegrees(J[K].Size())) / CrewClips::LimitDeg(K));
				}
				WorstGaze = FMath::Max(WorstGaze, FMath::Max(FMath::Abs(Yaw) / CrewClips::GazeLimitDeg(0), FMath::Abs(Pitch) / CrewClips::GazeLimitDeg(1)));
				++Frames;
			}
			TestTrue(FString::Printf(TEXT("%s (%s)%s: every joint within its limit (worst %.2f of it), the gaze too (%.2f)"), Info.Label, Info.Trial,
				bMirror ? TEXT(" mirrored") : TEXT(""), WorstRatio, WorstGaze), WorstRatio <= 1.001f && WorstGaze <= 1.001f);
			for (int32 K = 0; K < Info.OnsetCount; ++K)
			{
				const FCrewClipOnset& O = CrewClips::Onset(Info.OnsetBegin + K);
				FVector A[CrewClips::MaxJoints], B[CrewClips::MaxJoints];
				float Y, P;
				const float T0 = O.Frame / CrewClips::Rate();
				CrewClips::Sample(C, T0, bMirror, A, Y, P);
				CrewClips::Sample(C, FMath::Min(T0 + 1.f, CrewClips::Duration(C)), bMirror, B, Y, P);
				const float Move = CrewClips::TrunkLean(B, O.Axis) - CrewClips::TrunkLean(A, O.Axis);
				++Onsets;
				OnsetsRight += Move * O.Direction * (bMirror && O.Axis == 0 ? -1 : 1) > 0.f ? 1 : 0;
			}
		}
	}
	AddInfo(FString::Printf(TEXT("%d clip frames checked; %d of %d weight-shift onsets lean the marked way within a second"), Frames, OnsetsRight, Onsets));
	TestTrue(TEXT("There are weight-shift onsets"), Onsets > 20);
	TestTrue(TEXT("Nearly every onset leans the way it is marked (95 %)"), OnsetsRight >= FMath::CeilToInt(0.95 * Onsets));

	TArray<FCrewBody> Bodies;
	CrewBodies(*this, Bodies);
	if (!TestTrue(TEXT("SK_Sailor loads"), Bodies.Num() > 0)) return false;
	struct FLimb { const TCHAR* Names[2]; float MaxCm; const TCHAR* What; };
	// How far a limb may move from the clipless pose: the trunk's turns (pelvis, spine and chest, as far as a seated sailor
	// takes them) carry the head and shoulders a few centimetres; a free hand adds its own arm's turns.
	const FLimb Limbs[] = { { { TEXT("head"), TEXT("head") }, 14.f, TEXT("head") }, { { TEXT("hand_l"), TEXT("hand_l") }, 30.f, TEXT("left hand") },
		{ { TEXT("hand_r"), TEXT("hand_r") }, 30.f, TEXT("right hand") }, { { TEXT("forearm_l"), TEXT("lowerarm_l") }, 20.f, TEXT("left elbow") },
		{ { TEXT("forearm_r"), TEXT("lowerarm_r") }, 20.f, TEXT("right elbow") }, { { TEXT("foot_l"), TEXT("foot_l") }, 3.f, TEXT("left foot") },
		{ { TEXT("foot_r"), TEXT("foot_r") }, 3.f, TEXT("right foot") } };
	int32 Cases = 0;
	for (const EBoatType Type : { EBoatType::J22, EBoatType::ILCA7 })
	{
		const FBoatConfig Cfg = FBoatConfig::Make(Type);
		const FBoatModel Model(Cfg);
		const FVector CG(Model.GetCenterOfGravity().X, Model.GetCenterOfGravity().Y, Model.GetCenterOfGravity().Z);
		const int32 N = Cfg.CrewCount;
		for (int32 I = 0; I < N; ++I)
		{
			for (const double Out : { 0.3, Cfg.CrewSitOut * 0.8, Cfg.CrewSitOut + Cfg.CrewHikeOut })
			{
				for (const double Side : { 1.0, -1.0 })
				{
					FCrewPlaceInput Place;
					Place.Config = &Cfg;
					Place.Index = I;
					Place.CrewOffset = Side * Out;
					Place.WindwardSide = int32(Side);
					FCrewPlacement Pl;
					CrewPlacement(Place, Pl);
					if (CrewClipStanceWeight(Pl.Params.Stance, Pl.Params.Hike) <= 0.f) continue;
					for (const FCrewBody& Body : Bodies)
					{
						const FCrewRig* Rig = Body.Rig.bValid ? &Body.Rig : nullptr;
						if (Rig && Body.Name != MetaHumanRoleName(I == N - 1 ? 0 : (I == N - 2 ? 1 : 2))) continue;
						const FReferenceSkeleton& Ref = Body.Mesh->GetRefSkeleton();
						FCrewMotionState On, Off;
						FCrewMotionInput In;
						In.Params = Pl.Params;
						In.ToBoat = FigureFrame(Pl, Rig);
						In.SeatFromCG = Pl.Pelvis - CG;
						In.Gaze = FVector(2500.0, 0.0, 80.0);
						In.Seed = uint32(I) * 977u + uint32(Cases);
						FCrewMotionInput InOff = In;
						InOff.bClips = false;
						TArray<FTransform> CSOn, CSOff;
						float Worst[UE_ARRAY_COUNT(Limbs)] = {};
						float WorstJoint = 0.f, MaxWeight = 0.f;
						for (int32 K = 0; K < 20 * 30; ++K)
						{
							const double T = K / 30.0;
							// Chop, and a puff heeling the boat 12 degrees more over 3 s at 8 s.
							const double Heel = -Side * (5.0 + 12.0 * FMath::Clamp((T - 8.0) / 3.0, 0.0, 1.0));
							In.Motion = InOff.Motion = Chop(T, Heel, 0.5);
							In.Time = InOff.Time = float(T);
							CrewMotionUpdate(On, In, 1.f / 30.f);
							CrewMotionUpdate(Off, InOff, 1.f / 30.f);
							for (int32 J = 0; J < CrewClips::NumJoints(); ++J)
							{
								WorstJoint = FMath::Max(WorstJoint, float(FMath::RadiansToDegrees(On.Clip.Joints[J].Size())) / CrewClips::LimitDeg(J));
							}
							MaxWeight = FMath::Max(MaxWeight, On.Clip.Weight);
							if (K % 5 != 4) continue;
							CrewMotionPose(Ref, Rig, &Cfg, Model.HullDepth(), On, In, CSOn);
							CrewMotionPose(Ref, Rig, &Cfg, Model.HullDepth(), Off, InOff, CSOff);
							for (int32 L = 0; L < UE_ARRAY_COUNT(Limbs); ++L)
							{
								const int32 B = Ref.FindBoneIndex(Limbs[L].Names[Rig ? 1 : 0]);
								if (B != INDEX_NONE) Worst[L] = FMath::Max(Worst[L], float(FVector::Dist(CSOn[B].GetLocation(), CSOff[B].GetLocation())));
							}
						}
						++Cases;
						const FString Case = FString::Printf(TEXT("%s, %s crew %d (stance %d, hike %.1f, side %+.0f)"), ANSI_TO_TCHAR(BoatTypeName(Cfg.Type)), *Body.Name, I,
							int32(Pl.Params.Stance), Pl.Params.Hike, Side);
						TestTrue(Case + FString::Printf(TEXT(": the clips play (weight %.2f)"), MaxWeight), MaxWeight > 0.25f);
						TestTrue(Case + FString::Printf(TEXT(": every joint within its limit (worst %.3f of it)"), WorstJoint), WorstJoint <= 1.0001f);
						FString Moves;
						for (int32 L = 0; L < UE_ARRAY_COUNT(Limbs); ++L)
						{
							Moves += FString::Printf(TEXT(" %s %.1f"), Limbs[L].What, Worst[L]);
							TestTrue(Case + FString::Printf(TEXT(": the %s moves %.1f cm at most (within %.0f)"), Limbs[L].What, Worst[L], Limbs[L].MaxCm), Worst[L] <= Limbs[L].MaxCm);
						}
						AddInfo(Case + TEXT(": cm from the clipless pose:") + Moves);
					}
				}
			}
		}
	}
	TestTrue(TEXT("Idling stances checked"), Cases >= 8);
	return true;
}

// Crew C1b: the clip goes quiet for a tack. Idling on the rail, the crew start across: within a fifth of a second the clip
// lets go and it stays off through the crossing and the settle onto the new rail, then comes back. And a puff that heels
// the boat starts a weight shift against it.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewClipTackTest, "SailingSim.Visual.CrewClipTack", CrewMotionFlags)
bool FVisualCrewClipTackTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	for (uint32 Seed = 0; Seed < 6; ++Seed)
	{
		FCrewMotionState S;
		FCrewMotionInput In;
		In.Params.Stance = ECrewStance::RailHike;
		In.Params.Side = 1.f;
		In.Seed = Seed * 977u;
		const float Dt = 1.f / 60.f;
		float Before = 0.f, QuietBy = 0.f, LoudCrossing = 0.f, After = 0.f, Rest = 0.f;
		for (int32 K = 0; K < 16 * 60; ++K)
		{
			const float T = K * Dt;
			// Idle 6 s; the tack: across for 1.5 s (crouched, ducking), then onto the other rail.
			if (K == 6 * 60) { In.Params.Stance = ECrewStance::Crossing; In.Params.Side = -1.f; In.Transition++; In.TransitionSeconds = 0.45f; }
			if (T >= 6.f && T < 7.5f) In.Duck = 0.5f;
			if (K == FMath::RoundToInt(7.5f * 60)) { In.Params.Stance = ECrewStance::RailHike; In.Duck = 0.f; In.Transition++; In.TransitionSeconds = 0.6f; }
			In.Motion = Chop(T, 10.0 * In.Params.Side, 0.4);
			In.Time = T;
			CrewMotionUpdate(S, In, Dt);
			float Joint = 0.f;
			for (int32 J = 0; J < CrewClips::NumJoints(); ++J) Joint = FMath::Max(Joint, float(FMath::RadiansToDegrees(S.Clip.Joints[J].Size())));
			Joint = FMath::Max(Joint, FMath::Max(FMath::Abs(S.Clip.GazeYaw), FMath::Abs(S.Clip.GazePitch)));
			if (T > 4.f && T < 6.f) Before = FMath::Max(Before, S.Clip.Weight);
			if (T >= 6.2f && T < 8.1f) LoudCrossing = FMath::Max(LoudCrossing, Joint), QuietBy = FMath::Max(QuietBy, S.Clip.Weight);
			if (T > 12.f) After = FMath::Max(After, S.Clip.Weight);
			Rest = S.Clip.Weight;
		}
		const FString Case = FString::Printf(TEXT("Seed %u"), Seed);
		TestTrue(Case + FString::Printf(TEXT(": idling before the tack (weight %.2f)"), Before), Before > 0.8f);
		TestTrue(Case + FString::Printf(TEXT(": quiet from 0.2 s into the tack to the new rail (weight %.4f, largest turn %.3f deg)"), QuietBy, LoudCrossing),
			QuietBy < 1e-3f && LoudCrossing < 0.01f);
		TestTrue(Case + FString::Printf(TEXT(": idling again after (weight %.2f)"), After), After > 0.8f && Rest > 0.8f);
	}

	// A puff: the heel grows 12 degrees over 3 s. The sailor starts a weight shift against it, and the clip's trunk leans
	// that way: on the cockpit seat facing inboard the heel tips them back or forward (they lean to windward), at the helm
	// facing forward it tips them sideways.
	int32 Shifted = 0, Leaned = 0, Seeds = 0;
	for (const ECrewStance Stance : { ECrewStance::Cockpit, ECrewStance::Helm })
	{
		for (uint32 Seed = 0; Seed < 8; ++Seed)
		{
			for (const double Sign : { 1.0, -1.0 })
			{
				FCrewMotionState S;
				FCrewMotionInput In;
				In.Params.Stance = Stance;
				In.Params.Side = 1.f;
				In.Seed = Seed * 31u + 7u;
				const float Dt = 1.f / 60.f;
				float RollBefore = 0.f, PitchBefore = 0.f, LeanAt = 0.f, LeanLater = 0.f;
				int32 TriggerK = -1;
				for (int32 K = 0; K < 14 * 60; ++K)
				{
					const float T = K * Dt;
					const double Heel = Sign * (4.0 + 12.0 * FMath::Clamp((T - 8.0) / 3.0, 0.0, 1.0));
					In.Motion = FCrewBoatMotion();
					In.Motion.Gravity = FQuat(FRotator(0.0, 0.0, Heel)).UnrotateVector(FVector(0.0, 0.0, -9.81));
					In.Time = T;
					const int32 Was = S.Clip.HeelShifts;
					CrewMotionUpdate(S, In, Dt);
					if (FMath::IsNearlyEqual(T, 7.9f, 0.5f * Dt)) RollBefore = S.Balance.Roll, PitchBefore = S.Balance.Pitch;
					if (T > 8.f && S.Clip.HeelShifts > Was && TriggerK < 0) TriggerK = K, LeanAt = S.Clip.Lean[S.Clip.LastShiftAxis];
					if (TriggerK >= 0 && K == TriggerK + 60) LeanLater = S.Clip.Lean[S.Clip.LastShiftAxis];
				}
				++Seeds;
				// The way they tip most, and against it.
				const float DRoll = S.Balance.Roll - RollBefore, DPitch = S.Balance.Pitch - PitchBefore;
				const int32 Axis = FMath::Abs(DPitch) > FMath::Abs(DRoll) ? 1 : 0;
				const int32 Want = -int32(FMath::Sign(Axis == 1 ? DPitch : DRoll));
				if (TriggerK >= 0 && S.Clip.LastShiftDirection == Want && S.Clip.LastShiftAxis == Axis)
				{
					++Shifted;
					Leaned += (LeanLater - LeanAt) * Want > 0.f ? 1 : 0;
				}
				else if (TriggerK < 0 && S.Clip.Lean[Axis] * Want > 0.f)
				{
					++Shifted; // already leaning that way: nothing to start
					++Leaned;
				}
				AddInfo(FString::Printf(TEXT("Stance %d, seed %u, heel %+.0f: %s; the clip's lean %.1f -> %.1f deg a second later (want %+d on axis %d)"), int32(Stance), Seed, Sign,
					TriggerK >= 0 ? *FString::Printf(TEXT("shift at %.2f s toward %+d on axis %d"), TriggerK * Dt, S.Clip.LastShiftDirection, S.Clip.LastShiftAxis) : TEXT("no shift"),
					LeanAt, LeanLater, Want, Axis));
			}
		}
	}
	TestTrue(FString::Printf(TEXT("A change of heel starts a weight shift against it (%d of %d)"), Shifted, Seeds), Shifted == Seeds);
	TestTrue(FString::Printf(TEXT("... and the trunk leans that way within a second (%d of %d)"), Leaned, Shifted), Leaned >= FMath::CeilToInt(0.75 * Shifted));
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualMultihullCrewSeatTest, "SailingSim.Visual.MultihullCrewSeat", CrewMotionFlags)
bool FVisualMultihullCrewSeatTest::RunTest(const FString& Parameters)
{
	// The Corsair's crew had sat over the water aft of her after aka and her helm on the windward ama, out of reach of the
	// tiller, every multihull sailor at the main hull's sheer plus 0.1 m. Each sailor on a multihull sits on what is under
	// them (a hull's deck, the net, trampoline or bridgedeck), apart, the trimaran's helm in her cockpit.
	using namespace Sailing;
	for (const EBoatType Type : { EBoatType::Hobie16, EBoatType::Corsair880, EBoatType::Lagoon42 })
	{
		const FBoatConfig Cfg = FBoatConfig::Make(Type);
		const FString Name = UTF8_TO_TCHAR(Cfg.Name);
		const double Reach = Cfg.CrewSitOut + Cfg.CrewHikeOut;
		for (const double Side : { 1.0, -1.0 })
		{
			for (int32 Step = 0; Step <= 8; ++Step)
			{
				const double Out = Reach * Step / 8.0;
				TArray<FVector> Pelvises;
				for (int32 I = 0; I < Cfg.CrewCount; ++I)
				{
					FCrewPlaceInput Place;
					Place.Config = &Cfg;
					Place.Index = I;
					Place.CrewOffset = Side * Out;
					Place.WindwardSide = int32(Side);
					Place.TrueWindAngle = FMath::DegreesToRadians(80.0);
					FCrewPlacement Pl;
					CrewPlacement(Place, Pl);
					const FVector& P = Pl.Pelvis;
					const FString What = FString::Printf(TEXT("%s sailor %d at %.2f m out (side %+.0f)"), *Name, I, Out, Side);
					Pelvises.Add(P);
					if (Pl.Params.Stance == ECrewStance::Trapeze) continue;
					TestTrue(What + TEXT(" sits over the boat"), CrewFloorZ(Cfg, P.X, P.Y) > -1e8);
					const double Over = P.Z - CrewSeatSurfaceZ(Cfg, P.X, P.Y);
					const double Lowest = Pl.Params.Stance == ECrewStance::Cockpit ? -0.15 : 0.03;
					if (Over < Lowest || Over > 0.10) AddError(FString::Printf(TEXT("%s: pelvis %.2f m over its seat (stance %d)"), *What, Over, int32(Pl.Params.Stance)));
					if (Type == EBoatType::Corsair880 && Pl.bHelm)
					{
						TestTrue(What + TEXT(": the helm is on the main hull, in reach of the tiller"), FMath::Abs(P.Y) < Cfg.Hulls[0].DeckHalfBeam(P.X));
					}
				}
				for (int32 A = 0; A < Pelvises.Num(); ++A)
				{
					for (int32 B = A + 1; B < Pelvises.Num(); ++B)
					{
						if (FVector::Dist(Pelvises[A], Pelvises[B]) < 0.4) AddError(FString::Printf(TEXT("%s: sailors %d and %d sit %.2f m apart at %.2f m out"), *Name, A, B, FVector::Dist(Pelvises[A], Pelvises[B]), Out));
					}
				}
			}
		}
	}
	return true;
}

// Crew hull clip: every stance's body stays clear of the solid boat. On every boat, each sailor sitting up, hiked, at the
// light-air cockpit seat, downwind, knocked down and mid-tack, posed through a chop on SK_Sailor and the MetaHumans: the
// trunk, head, arms and legs (each bone's centreline at three points, with a flesh radius below and to either side) must
// not be inside the hull, under the deck or in the cockpit well's walls (CrewInsideBoat). The feet have their own test.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewHullClearanceTest, "SailingSim.Visual.CrewHullClearance", CrewMotionFlags)
bool FVisualCrewHullClearanceTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	TArray<FCrewBody> Bodies;
	CrewBodies(*this, Bodies);
	if (!TestTrue(TEXT("SK_Sailor loads"), Bodies.Num() > 0)) return false;
	// Flesh radius (m) by bone name; bones not listed (feet, fingers, face, twist and correctives) are not checked.
	auto RadiusFor = [](const FString& Bone) -> double
	{
		const FString B = Bone.ToLower();
		if (B.Contains(TEXT("twist")) || B.Contains(TEXT("corr")) || B.Contains(TEXT("ik_")) || B.Contains(TEXT("root"))) return -1.0;
		// The MetaHumans' helper joints (thigh_bck, thigh_in, calf_knee, ...) sit at or outside the skin: not centrelines.
		if (B.Contains(TEXT("bck")) || B.Contains(TEXT("_in")) || B.Contains(TEXT("_out")) || B.Contains(TEXT("_fwd")) || B.Contains(TEXT("knee"))) return -1.0;
		// (and their muscle helpers, off the centreline: tricep, bicep, latissimus, pec, scap)
		if (B.Contains(TEXT("tricep")) || B.Contains(TEXT("bicep")) || B.Contains(TEXT("latissimus")) || B.Contains(TEXT("pec")) || B.Contains(TEXT("scap"))) return -1.0;
		if (B.StartsWith(TEXT("pelvis"))) return 0.10;
		if (B.StartsWith(TEXT("spine"))) return 0.10;
		if (B.StartsWith(TEXT("neck"))) return 0.05;
		if (B == TEXT("head")) return 0.09;
		if (B.StartsWith(TEXT("thigh"))) return 0.07;
		if (B.StartsWith(TEXT("calf"))) return 0.045;
		if (B.StartsWith(TEXT("clavicle"))) return 0.05;
		if (B.StartsWith(TEXT("upperarm"))) return 0.045;
		if (B.StartsWith(TEXT("lowerarm"))) return 0.035;
		return -1.0;
	};
	int32 Checked = 0, Clipped = 0, Crossings = 0;
	TMap<FString, int32> Worst;
	for (int32 Type = 0; Type < int32(EBoatType::Count); ++Type)
	{
		const FBoatConfig Cfg = FBoatConfig::Make(EBoatType(Type));
		const FBoatModel Model(Cfg);
		const FVector CG(Model.GetCenterOfGravity().X, Model.GetCenterOfGravity().Y, Model.GetCenterOfGravity().Z);
		const int32 N = Cfg.CrewCount;
		for (int32 I = 0; I < N; ++I)
		{
			const bool bHelm = I == N - 1;
			struct FCase { double Offset; double BoomAngle, BoomRate, Rate; double HeelDeg; const TCHAR* Name; double Twa = 0.8, Turn = 0.0; };
			const double Up = Cfg.CrewSitOut * 0.8, Hiked = Cfg.CrewSitOut + Cfg.CrewHikeOut;
			const FCase Cases[] = {
				{ Up, 0.3, 0.0, 0.0, -12.0, TEXT("sitting up, starboard") }, { -Up, -0.3, 0.0, 0.0, 12.0, TEXT("sitting up, port") },
				{ Hiked, 0.25, 0.0, 0.0, -20.0, TEXT("hiked hard") },
				{ 0.3, 0.6, 0.0, 0.0, -4.0, TEXT("light air, cockpit seat"), 1.6 },
				{ -0.2, -1.3, 0.0, 0.0, 2.0, TEXT("running downwind"), 2.9 },
				{ Up, 0.3, 0.0, 0.0, -42.0, TEXT("knocked down to 42 degrees") },
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
				for (const FCrewBody& Body : Bodies)
				{
					const FCrewRig* Rig = Body.Rig.bValid ? &Body.Rig : nullptr;
					if (Rig && Body.Name != MetaHumanRoleName(bHelm ? 0 : (I == N - 2 ? 1 : 2))) continue;
					const FReferenceSkeleton& Ref = Body.Mesh->GetRefSkeleton();
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
					TSet<FString> Reported;
					for (int32 K = 0; K < 4 * 30; ++K)
					{
						const double T = K / 30.0;
						In.Motion = Chop(T, C.HeelDeg, 0.6);
						In.Time = float(T);
						CrewMotionUpdate(State, In, 1.f / 30.f);
						if (K % 10 != 9) continue;
						CrewMotionPose(Ref, Rig, &Cfg, Model.HullDepth(), State, In, CS);
						for (int32 B = 1; B < Ref.GetNum() && B < CS.Num(); ++B)
						{
							const FString BoneName = Ref.GetBoneName(B).ToString();
							const double R = RadiusFor(BoneName);
							const int32 Parent = Ref.GetParentIndex(B);
							if (R < 0.0 || Parent < 0) continue;
							const FVector A = In.ToBoat.TransformPosition(CS[Parent].GetLocation()) / CmPerMeter;
							const FVector Bp = In.ToBoat.TransformPosition(CS[B].GetLocation()) / CmPerMeter;
							// Along the bone from its parent only when the parent is flesh too (the pelvis hangs off the root at
							// the figure's origin: the segment between them is not body).
							const bool bSegment = RadiusFor(Ref.GetBoneName(Parent).ToString()) >= 0.0;
							for (const double U : { 0.25, 0.5, 0.75, 1.0 })
							{
								if (!bSegment && U < 1.0) continue;
								const FVector P = FMath::Lerp(A, Bp, U);
								for (const FVector& Dir : { FVector(0, 0, -1), FVector(0, 1, 0), FVector(0, -1, 0), FVector(1, 0, 0), FVector(-1, 0, 0) })
								{
									++Checked;
									// The flesh may rest on a surface: 1.5 cm of give, 4 cm under the hips, lower back, thighs and calves
									// (seated flesh). A clip is flesh more than 2.5 cm past that inside the boat (how deep: the first
									// point inside along the ray from the bone).
									const bool bSeatFlesh = (Dir.Z < 0.0 && (BoneName.StartsWith(TEXT("pelvis")) || BoneName.StartsWith(TEXT("thigh"))
										|| BoneName == TEXT("spine") || BoneName.StartsWith(TEXT("spine_01")))) || BoneName.StartsWith(TEXT("calf"));
									const double Reach = FMath::Max(R - (bSeatFlesh ? 0.04 : 0.015), 0.0);
									const FVector Q = P + Dir * Reach;
									if (!CrewInsideBoat(Cfg, Model.HullDepth(), Q)) continue;
									double FirstIn = Reach;
									for (double S = 0.0; S < Reach; S += 0.005)
									{
										if (CrewInsideBoat(Cfg, Model.HullDepth(), P + Dir * S)) { FirstIn = S; break; }
									}
									if (Reach - FirstIn < 0.025) continue;
									++Clipped;
									const FString Key = FString::Printf(TEXT("%s, %s crew %d (%s, stance %d%s): %s"), ANSI_TO_TCHAR(BoatTypeName(Cfg.Type)), *Body.Name, I, C.Name, int32(Pl.Params.Stance), Pl.Params.bFlatDeck ? TEXT(" flat") : TEXT(""), *BoneName);
									Worst.FindOrAdd(Key)++;
									if (!Reported.Contains(BoneName))
									{
										Reported.Add(BoneName);
										// Crossing is a half-second transition: its clips are listed, not failed.
										if (Pl.Params.Stance == ECrewStance::Crossing) { ++Crossings; break; }
										AddError(FString::Printf(TEXT("%s inside the boat at (%.2f, %.2f, %.2f) m (pelvis at %.2f, %.2f, %.2f)"), *Key, Q.X, Q.Y, Q.Z, Pl.Pelvis.X, Pl.Pelvis.Y, Pl.Pelvis.Z));
									}
									break;
								}
							}
						}
					}
				}
			}
		}
	}
	AddInfo(FString::Printf(TEXT("%d body points checked, %d inside the boat; %d bones in a crossing (transient, not failed)"), Checked, Clipped, Crossings));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
