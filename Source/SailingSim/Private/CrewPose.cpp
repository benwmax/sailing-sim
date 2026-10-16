#include "CrewPose.h"
#include "CrewSolver.h"
#include "BoatModel.h"
#include "GroomAsset.h"
#include "GroomBindingAsset.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/SkeletalMesh.h"
#include "ReferenceSkeleton.h"

namespace
{
	// Rotations in the character frame (X forward, Y right, Z up). The reference pose is a T-pose.
	FQuat Q(const FVector& Axis, float Deg) { return FQuat(Axis, FMath::DegreesToRadians(Deg)); }
	FQuat LegForward(float Deg) { return Q(FVector::RightVector, -Deg); }  // a downward bone swings forward
	FQuat KneeBend(float Deg) { return Q(FVector::RightVector, Deg); }     // ... and back
	FQuat Lean(float Deg) { return Q(FVector::RightVector, Deg); }         // an upward bone leans forward (+) or back (-)
	FQuat LeanSide(float Deg) { return Q(FVector::ForwardVector, Deg); }   // toward the right (+)
	// Arms: from the T-pose down by Down degrees, then swung forward by Forward; the elbow bends forward.
	FQuat Arm(bool bLeft, float Down, float Forward) { return Q(FVector::RightVector, -Forward) * Q(FVector::ForwardVector, bLeft ? Down : -Down); }
	FQuat Elbow(bool bLeft, float Deg) { return Q(FVector::UpVector, bLeft ? Deg : -Deg); }

	void Legs(TMap<FName, FQuat>& Out, float Raise, float Knee, float Splay = 6.f)
	{
		Out.Add(TEXT("thigh_l"), LeanSide(-Splay) * LegForward(Raise));
		Out.Add(TEXT("thigh_r"), LeanSide(Splay) * LegForward(Raise));
		Out.Add(TEXT("calf_l"), KneeBend(Knee));
		Out.Add(TEXT("calf_r"), KneeBend(Knee));
		Out.Add(TEXT("foot_l"), KneeBend(-0.6f * Knee + 0.4f * Raise));
		Out.Add(TEXT("foot_r"), KneeBend(-0.6f * Knee + 0.4f * Raise));
	}

	void Arms(TMap<FName, FQuat>& Out, float DownL, float FwdL, float ElbowL, float DownR, float FwdR, float ElbowR)
	{
		Out.Add(TEXT("upperarm_l"), Arm(true, DownL, FwdL));
		Out.Add(TEXT("upperarm_r"), Arm(false, DownR, FwdR));
		Out.Add(TEXT("forearm_l"), Elbow(true, ElbowL));
		Out.Add(TEXT("forearm_r"), Elbow(false, ElbowR));
	}
}

float CrewFacingYaw(const FCrewPoseParams& P)
{
	switch (P.Stance)
	{
	case ECrewStance::RailHike: return -80.f * P.Side;         // inboard, turned a little toward the bow (round 11)
	case ECrewStance::Helm: return -25.f * P.Side;             // forward, turned a little inboard
	case ECrewStance::Crossing: return -90.f * P.Side;         // across, toward the new side
	case ECrewStance::Trapeze: return -10.f * P.Side;          // forward on the rail
	case ECrewStance::Righting: return 90.f * P.Side;          // facing the boat (she lies to the other side)
	case ECrewStance::DinghyHike: return -75.f * P.Side;       // inboard, turned a little toward the bow (Graphics G8)
	default: return -90.f * P.Side;                           // facing inboard
	}
}

void CrewJointRotations(const FCrewPoseParams& P, TMap<FName, FQuat>& Out)
{
	Out.Reset();
	const float H = FMath::Clamp(P.Hike, 0.f, 1.f);
	switch (P.Stance)
	{
	case ECrewStance::RailHike:
	{
		// On the windward side deck facing inboard: thighs across the deck, lower legs down into the cockpit well with the
		// feet on the seat or the sole, leaning back out over the water from the hips the harder they hike; hands on the
		// knees (the trimmer's on the sheet). Round 11: they had sat facing outboard with their legs hanging down the
		// topsides, and Bean, who sails J/22s: "people do not hang their legs over a sailboat like that".
		Legs(Out, 84.f - 8.f * H, 82.f - 22.f * H, 8.f);
		const float L = -(6.f + 26.f * H);
		Out.Add(TEXT("spine"), Lean(0.5f * L));
		Out.Add(TEXT("chest"), Lean(0.5f * L));
		// The head stays up and turned toward the bow (the jib and the water ahead).
		Out.Add(TEXT("neck"), Q(FVector::UpVector, 20.f * P.Side) * Lean(-0.7f * L));
		Arms(Out, 76.f, 30.f, 55.f, 76.f, 30.f, 55.f);
		break;
	}
	case ECrewStance::Helm:
	{
		// Aft on the windward deck facing forward, legs into the cockpit; leaning out over the side as the boat
		// heels; the aft hand on the tiller extension, the forward hand on the mainsheet.
		Legs(Out, 82.f, 80.f, 10.f);
		const float Out_ = (6.f + 22.f * H) * P.Side;
		Out.Add(TEXT("pelvis"), LeanSide(Out_ * 0.4f));
		Out.Add(TEXT("spine"), LeanSide(Out_ * 0.6f) * Lean(5.f));
		Out.Add(TEXT("neck"), LeanSide(-Out_ * 0.7f));
		const bool bLeftOutboard = P.Side < 0.f; // facing forward, the left hand is outboard on the port side
		Arms(Out, bLeftOutboard ? 55.f : 70.f, bLeftOutboard ? 60.f : 45.f, bLeftOutboard ? 25.f : 70.f,
			bLeftOutboard ? 70.f : 55.f, bLeftOutboard ? 45.f : 60.f, bLeftOutboard ? 70.f : 25.f);
		break;
	}
	case ECrewStance::Cockpit:
		// Sitting on the cockpit seat (or low to leeward in light air), facing inboard.
		Legs(Out, 86.f, 84.f);
		Out.Add(TEXT("spine"), Lean(6.f));
		Arms(Out, 76.f, 28.f, 55.f, 76.f, 28.f, 55.f);
		break;
	case ECrewStance::Crossing:
		// Crouched, moving across the cockpit under the boom on a tack.
		Legs(Out, 75.f, 112.f);
		Out.Add(TEXT("spine"), Lean(25.f));
		Out.Add(TEXT("chest"), Lean(20.f));
		Out.Add(TEXT("neck"), Lean(-30.f));
		Arms(Out, 60.f, 55.f, 30.f, 60.f, 55.f, 30.f);
		break;
	case ECrewStance::DinghyHike:
	{
		// On the deck edge facing inboard, feet under the hiking strap, leaning back out over the water; the aft hand
		// on the tiller extension, the forward hand on the mainsheet.
		// Graphics G8: sitting up, the thighs lie level across the side deck and the lower legs drop into the cockpit well
		// (the feet under the strap); hiking straightens them.
		// Round 10: sitting out on the edge in a breeze the legs reach across the well to the strap on the centreline
		// (knees bent half as much, the feet planted on the floor under it), and the body leans back from the start; the
		// thighs-level, shins-down seat read as a sailor on a chair.
		Legs(Out, 80.f - 12.f * H, 25.f + 30.f * (1.f - H), 9.f);
		const float L = -(20.f + 50.f * H);
		Out.Add(TEXT("spine"), Lean(0.5f * L));
		Out.Add(TEXT("chest"), Lean(0.5f * L));
		// Graphics G8: the head turned toward the bow (the luff and the water ahead), not staring across the boat.
		Out.Add(TEXT("neck"), Q(FVector::UpVector, 30.f * P.Side) * Lean(-0.7f * L));
		// (Round 10: the elbows nearer the sides; the hands' reach keeps this plane, and 40 deg down held them out like wings.)
		Arms(Out, 65.f, 55.f, 45.f, 65.f, 55.f, 45.f);
		break;
	}
	case ECrewStance::Trapeze:
		// Standing on the rail, body straight; one hand on the handle, the other on the sheet.
		Legs(Out, 4.f, 6.f, 8.f);
		Arms(Out, -55.f, 10.f, 20.f, 70.f, 40.f, 40.f);
		break;
	case ECrewStance::Righting:
		// Standing on the board, leaning back with the hands on the gunwale.
		Legs(Out, 18.f, 25.f, 12.f);
		Out.Add(TEXT("spine"), Lean(-20.f));
		Out.Add(TEXT("chest"), Lean(-15.f));
		Out.Add(TEXT("neck"), Lean(25.f));
		Arms(Out, 25.f, 75.f, 10.f, 25.f, 75.f, 10.f);
		break;
	}
}

namespace CrewSolver
{
	/** The reference pose in component space. */
	void RestPose(const FReferenceSkeleton& Ref, TArray<FTransform>& Out)
	{
		const TArray<FTransform>& Local = Ref.GetRefBonePose();
		Out.SetNum(Ref.GetNum());
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			const int32 Parent = Ref.GetParentIndex(B);
			Out[B] = Parent == INDEX_NONE ? Local[B] : Local[B] * Out[Parent];
		}
	}

	/** Component-space posed transforms from a rest pose: D(bone) = D(parent) * R(bone); rotation D * rest;
	 *  position = parent's posed position + D(parent) * (rest offset from the parent). */
	void Solve(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, const TMap<FName, FQuat>& Joints, TArray<FTransform>& OutCS,
		TArray<FQuat>* OutD)
	{
		const int32 N = Ref.GetNum();
		TArray<FQuat> Local;
		TArray<FQuat>& D = OutD ? *OutD : Local;
		D.SetNum(N);
		OutCS.SetNum(N);
		for (int32 B = 0; B < N; ++B)
		{
			const int32 Parent = Ref.GetParentIndex(B);
			const FQuat* R = Joints.Find(Ref.GetBoneName(B));
			const FQuat Rot = R ? *R : FQuat::Identity;
			D[B] = Parent == INDEX_NONE ? Rot : D[Parent] * Rot;
			const FQuat Rotation = D[B] * RestCS[B].GetRotation();
			const FVector Position = Parent == INDEX_NONE ? RestCS[B].GetLocation()
				: OutCS[Parent].GetLocation() + D[Parent].RotateVector(RestCS[B].GetLocation() - RestCS[Parent].GetLocation());
			OutCS[B] = FTransform(Rotation, Position, RestCS[B].GetScale3D());
		}
	}

	/** The sailor's joints on the rig's skeleton. */
	void Carry(const FCrewRig& Rig, const TMap<FName, FQuat>& Joints, TMap<FName, FQuat>& Out)
	{
		Out.Reset();
		const FQuat Inv = Rig.Frame.Inverse();
		for (const TPair<FName, FQuat>& J : Joints)
		{
			const FQuat R = Rig.Frame * J.Value * Inv;
			if (const TArray<TPair<FName, float>>* Bones = Rig.Map.Find(J.Key))
			{
				for (const TPair<FName, float>& B : *Bones) Out.Add(B.Key, FQuat::Slerp(FQuat::Identity, R, B.Value));
			}
			else
			{
				Out.Add(J.Key, R);
			}
		}
	}

	const TCHAR* const FingerNames[5] = { TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("pinky"), TEXT("thumb") };

	/** Graphics G8: two-bone IK for one arm toward a wrist target (component space). The elbow stays in the plane the
	 *  stance put it in; the shoulder and elbow rotations are written back into the joint map. */
	void ReachArm(const FReferenceSkeleton& Ref, const TArray<FTransform>& CS, const TArray<FQuat>& D, int32 Hand, const FVector& Target,
		TMap<FName, FQuat>& Joints)
	{
		const int32 Lower = Ref.GetParentIndex(Hand);
		const int32 Upper = Lower == INDEX_NONE ? INDEX_NONE : Ref.GetParentIndex(Lower);
		const int32 Above = Upper == INDEX_NONE ? INDEX_NONE : Ref.GetParentIndex(Upper);
		if (Above == INDEX_NONE) return;
		const FVector S = CS[Upper].GetLocation(), E = CS[Lower].GetLocation(), W = CS[Hand].GetLocation();
		const double A = FVector::Dist(S, E), B = FVector::Dist(E, W);
		FVector ToT = Target - S;
		const double Dist = FMath::Clamp(ToT.Size(), FMath::Abs(A - B) + 1.0, A + B - 0.5);
		const FVector X = ToT.GetSafeNormal();
		if (X.IsNearlyZero()) return;
		FVector Y = (E - S) - X * FVector::DotProduct(E - S, X);
		if (Y.SizeSquared() < 1.0) Y = FVector::CrossProduct(X, FVector::CrossProduct(FVector(0, 0, -1), X)); // a straight arm: elbow down
		Y = Y.GetSafeNormal();
		const double CosA = FMath::Clamp((A * A + Dist * Dist - B * B) / (2.0 * A * Dist), -1.0, 1.0);
		const FVector E2 = S + X * (A * CosA) + Y * (A * FMath::Sqrt(FMath::Max(0.0, 1.0 - CosA * CosA)));
		const FVector T2 = S + X * Dist;
		const FQuat Q1 = FQuat::FindBetweenVectors(E - S, E2 - S);
		const FVector W1 = S + Q1.RotateVector(W - S);
		const FQuat Q2 = FQuat::FindBetweenVectors(W1 - E2, T2 - E2);
		const FQuat DU = Q1 * D[Upper], DL = Q2 * Q1 * D[Lower];
		Joints.Add(Ref.GetBoneName(Upper), D[Above].Inverse() * DU);
		Joints.Add(Ref.GetBoneName(Lower), DU.Inverse() * DL);
	}

	/** A posed foot's heel and toe on the sole (component space): in the rest pose's character frame the heel 4 cm
	 *  behind the ankle, the toe 5 cm past the ball (SK_Sailor has no ball: its foot bone runs 17 cm to the toe), both a
	 *  centimetre above the ground, carried by the foot bone. */
	bool SolePoints(const FReferenceSkeleton& Ref, const TArray<FTransform>& Rest, const TArray<FTransform>& CS, const FQuat& Frame, int32 Side, FVector Out[2])
	{
		const int32 Foot = Ref.FindBoneIndex(Side == 0 ? TEXT("foot_l") : TEXT("foot_r"));
		if (Foot == INDEX_NONE) return false;
		const int32 Ball = Ref.FindBoneIndex(Side == 0 ? TEXT("ball_l") : TEXT("ball_r"));
		const FVector Ankle = Frame.UnrotateVector(Rest[Foot].GetLocation());
		const double ToeX = Ball != INDEX_NONE ? Frame.UnrotateVector(Rest[Ball].GetLocation()).X + 5.0 : Ankle.X + 17.0;
		const FVector Sole[2] = { FVector(Ankle.X - 4.0, Ankle.Y, 1.0), FVector(ToeX, Ankle.Y, 1.0) };
		const FQuat D = CS[Foot].GetRotation() * Rest[Foot].GetRotation().Inverse();
		for (int32 K = 0; K < 2; ++K) Out[K] = CS[Foot].GetLocation() + D.RotateVector(Frame.RotateVector(Sole[K]) - Rest[Foot].GetLocation());
		return true;
	}

	/** Crew pose fix: each foot the stance put inside the boat goes onto the floor above it, or, off the deck's plan
	 *  (through the topsides), inboard to the well (or the deck) first; the leg reaches it by two-bone IK. */
	bool PlantFeet(const FReferenceSkeleton& Ref, const TArray<FTransform>& Rest, const TArray<FTransform>& CS, const TArray<FQuat>& D, const FQuat& Frame,
		const FCrewGround& G, TMap<FName, FQuat>& Joints)
	{
		using namespace Sailing;
		const FBoatConfig& C = *G.Config;
		constexpr double M = 0.01; // cm to m
		bool bMoved = false;
		for (int32 Side = 0; Side < 2; ++Side)
		{
			FVector Sole[2];
			if (!SolePoints(Ref, Rest, CS, Frame, Side, Sole)) continue;
			const int32 Foot = Ref.FindBoneIndex(Side == 0 ? TEXT("foot_l") : TEXT("foot_r"));
			FVector B[2] = { G.ToBoat.TransformPosition(Sole[0]) * M, G.ToBoat.TransformPosition(Sole[1]) * M };
			auto Inside = [&](const FVector& P) { return CrewInsideBoat(C, G.HullDepth, P + FVector(0.0, 0.0, 0.015)); };
			if (!Inside(B[0]) && !Inside(B[1])) continue;
			FVector Shift = FVector::ZeroVector;
			const FVector Mid = 0.5 * (B[0] + B[1]);
			const double Off = -1e8;
			// Off the deck's plan (through the topsides), or under the side deck beside the well: bring it inboard, into the
			// well where there is one alongside, else onto the nearest hull's deck, 8 cm in from the edge.
			const bool bOffPlan = CrewFloorZ(C, B[0].X, B[0].Y) < Off || CrewFloorZ(C, B[1].X, B[1].Y) < Off;
			int32 Near = 0;
			for (int32 K = 1; K < int32(C.Hulls.size()); ++K)
			{
				if (FMath::Abs(Mid.Y - C.Hulls[K].CenterY) < FMath::Abs(Mid.Y - C.Hulls[Near].CenterY)) Near = K;
			}
			const FHullShape& H = C.Hulls[Near];
			FCrewCockpitWell W;
			const bool bWell = Near == 0 && CrewCockpitWell(C, W) && Mid.X > W.X0 && Mid.X < W.X1;
			const double Limit = (bWell ? (W.SideDeck > 0.0 ? H.DeckHalfBeam(Mid.X) - W.SideDeck : W.HalfWidth) : H.DeckHalfBeam(Mid.X)) - 0.08;
			const double Y = FMath::Max(FMath::Abs(B[0].Y - H.CenterY), FMath::Abs(B[1].Y - H.CenterY));
			if (Y > Limit && (bOffPlan || bWell))
			{
				Shift.Y = (Mid.Y >= H.CenterY ? -1.0 : 1.0) * (Y - Limit);
			}
			for (FVector& P : B) P += Shift;
			const double Floor = FMath::Max(CrewFloorZ(C, B[0].X, B[0].Y), CrewFloorZ(C, B[1].X, B[1].Y));
			if (Floor < Off) continue;
			Shift.Z = Floor + 0.005 - FMath::Min(B[0].Z, B[1].Z);
			const FVector Target = G.ToBoat.InverseTransformPosition(G.ToBoat.TransformPosition(CS[Foot].GetLocation()) + Shift / M);
			ReachArm(Ref, CS, D, Foot, Target, Joints);
			bMoved = true;
		}
		return bMoved;
	}

	void CurlFingers(const FCrewRig& Rig, const FCrewHands& Hands, TMap<FName, FQuat>& Carried)
	{
		// The fingers curl (a relaxed hand, or closed round a line): the base joint most, the tip least; the thumb less.
		for (int32 Side = 0; Side < 2; ++Side)
		{
			const float G = FMath::Clamp(Hands.Grip[Side], 0.f, 1.f);
			for (const TCHAR* Finger : FingerNames)
			{
				const bool bThumb = Finger[0] == TEXT('t');
				const float Deg[3] = { bThumb ? 25.f : 72.f, bThumb ? 58.f : 95.f, bThumb ? 50.f : 62.f };
				for (int32 K = 1; K <= 3; ++K)
				{
					const FName Bone(*FString::Printf(TEXT("%s_0%d_%s"), Finger, K, Side == 0 ? TEXT("l") : TEXT("r")));
					const FVector* Axis = Rig.CurlAxis.Find(Bone);
					if (!Axis) continue;
					FQuat JointTurn(*Axis, FMath::DegreesToRadians(G * Deg[K - 1]));
					// Round 12: the thumb's base also swings across the palm toward the fingers, so a closed hand's thumb wraps
					// over the line instead of standing up off it.
					if (bThumb && K == 1 && !Rig.ThumbSwing[Side].IsNearlyZero()) JointTurn = FQuat(Rig.ThumbSwing[Side], FMath::DegreesToRadians(G * 40.f)) * JointTurn;
					Carried.Add(Bone, JointTurn);
				}
			}
		}
	}

	/** Round 12: each seated foot standing on the floor lies flat on it. The leg's IK carries the foot with the calf, so
	 *  a leg reaching down or forward to the floor had planted the heel with the toe up in the air ("body parts not
	 *  positioned realistically"). The ankle turns the sole parallel to the floor, within 45 degrees, unless the turn
	 *  would put the heel or toe into the floor under it (across the bridge deck's edge it did). A foot resting on a
	 *  step's edge (the traveler bridge) levels with its other end over the lower floor. The turn fades out from 2 to 5 cm
	 *  over the higher floor, so a foot the idle clips move does not snap. */
	bool LevelFeet(const FReferenceSkeleton& Ref, const TArray<FTransform>& Rest, const TArray<FTransform>& CS, const TArray<FQuat>& D, const FQuat& Frame,
		const FCrewGround& G, TMap<FName, FQuat>& Joints)
	{
		constexpr double M = 0.01; // cm to m
		bool bMoved = false;
		const FQuat BoatRot = G.ToBoat.GetRotation();
		const Sailing::FBoatConfig& C = *G.Config;
		for (int32 Side = 0; Side < 2; ++Side)
		{
			FVector Sole[2];
			if (!SolePoints(Ref, Rest, CS, Frame, Side, Sole)) continue;
			const int32 Foot = Ref.FindBoneIndex(Side == 0 ? TEXT("foot_l") : TEXT("foot_r"));
			const int32 Calf = Ref.GetParentIndex(Foot);
			if (Calf == INDEX_NONE) continue;
			const FVector Ankle = G.ToBoat.TransformPosition(CS[Foot].GetLocation()) * M;
			const FVector Heel = G.ToBoat.TransformPosition(Sole[0]) * M, Toe = G.ToBoat.TransformPosition(Sole[1]) * M;
			const double HeelFloor = CrewFloorZ(C, Heel.X, Heel.Y), ToeFloor = CrewFloorZ(C, Toe.X, Toe.Y);
			if (HeelFloor < -1e8 || ToeFloor < -1e8) continue;
			const bool bOneLevel = FMath::Abs(ToeFloor - HeelFloor) <= 0.01;
			const double Floor = FMath::Max(HeelFloor, ToeFloor);
			const double Gap = FMath::Min(Heel.Z, Toe.Z) - Floor;
			const double Weight = FMath::Clamp((0.05 - Gap) / 0.03, 0.0, 1.0);
			if (Weight <= 0.0) continue; // not standing on it
			const FVector SoleDir = Toe - Heel;
			const FVector SoleFlat(SoleDir.X, SoleDir.Y, 0.0);
			if (SoleFlat.SizeSquared() < 1e-4 || FMath::Abs(SoleDir.Z) < 0.01) continue;
			FQuat FootTurn = FQuat::FindBetweenVectors(SoleDir, SoleFlat);
			const double TurnRad = FootTurn.GetAngle(), MaxRad = FMath::DegreesToRadians(45.0);
			FootTurn = FQuat::Slerp(FQuat::Identity, FootTurn, Weight * FMath::Min(1.0, MaxRad / FMath::Max(TurnRad, 1e-6)));
			const FVector NewHeel = Ankle + FootTurn.RotateVector(Heel - Ankle), NewToe = Ankle + FootTurn.RotateVector(Toe - Ankle);
			const double NewHeelFloor = CrewFloorZ(C, NewHeel.X, NewHeel.Y), NewToeFloor = CrewFloorZ(C, NewToe.X, NewToe.Y);
			if (bOneLevel)
			{
				// On one level the foot stays over it (the planting after lifts a heel or toe the turn dipped a little).
				if (FMath::Abs(NewHeelFloor - HeelFloor) > 0.01 || FMath::Abs(NewToeFloor - HeelFloor) > 0.01) continue;
			}
			// Across a step's edge (the traveler bridge) the other end may overhang the lower floor, but never go into what
			// is under it (a toe turned down over the bridge deck went into it).
			else if (NewHeel.Z < NewHeelFloor - 0.005 || NewToe.Z < NewToeFloor - 0.005) continue;
			const FQuat TurnCS = BoatRot.Inverse() * FootTurn * BoatRot;
			Joints.Add(Ref.GetBoneName(Foot), D[Calf].Inverse() * TurnCS * D[Foot]);
			bMoved = true;
		}
		return bMoved;
	}

	void PlantAllFeet(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, TArray<FTransform>& CS, TArray<FQuat>& D, const FQuat& Frame,
		const FCrewGround& Ground, TMap<FName, FQuat>& Carried)
	{
		for (int32 Pass = 0; Pass < 2; ++Pass)
		{
			if (!PlantFeet(Ref, RestCS, CS, D, Frame, Ground, Carried)) break;
			Solve(Ref, RestCS, Carried, CS, &D);
		}
		// Seated, flat on the floor, then onto it again (turning about the ankle lifts the heel or the toe a little).
		if (Ground.bSeated && LevelFeet(Ref, RestCS, CS, D, Frame, Ground, Carried))
		{
			Solve(Ref, RestCS, Carried, CS, &D);
			for (int32 Pass = 0; Pass < 2; ++Pass)
			{
				if (!PlantFeet(Ref, RestCS, CS, D, Frame, Ground, Carried)) break;
				Solve(Ref, RestCS, Carried, CS, &D);
			}
		}
	}

	bool PlaceHands(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, TArray<FTransform>& CS, TArray<FQuat>& D, const FCrewHands& Hands,
		TMap<FName, FQuat>& Carried)
	{
		bool bMoved = false;
		for (int32 Side = 0; Side < 2; ++Side)
		{
			if (Hands.Mode[Side] == FCrewHands::EMode::Free) continue;
			const TCHAR* Sx = Side == 0 ? TEXT("l") : TEXT("r");
			const int32 Hand = Ref.FindBoneIndex(Side == 0 ? TEXT("hand_l") : TEXT("hand_r"));
			if (Hand == INDEX_NONE) continue;
			FVector Target = Hands.Target[Side];
			if (Hands.Mode[Side] == FCrewHands::EMode::Knee)
			{
				// The palm on top of the knee, the wrist a hand's length back toward the hip.
				const int32 Calf = Ref.FindBoneIndex(*FString::Printf(TEXT("calf_%s"), Sx));
				const int32 Thigh = Ref.FindBoneIndex(*FString::Printf(TEXT("thigh_%s"), Sx));
				if (Calf == INDEX_NONE || Thigh == INDEX_NONE) continue;
				const FVector Knee = CS[Calf].GetLocation(), Hip = CS[Thigh].GetLocation();
				Target = Knee + (Hip - Knee).GetSafeNormal() * 9.0 + FVector(0, 0, 9.0);
				ReachArm(Ref, CS, D, Hand, Target, Carried);
				bMoved = true;
				continue;
			}
			// Reach: the target is where the palm closes (the middle knuckle less a little), so the wrist stops short of it.
			const int32 Knuckle = Ref.FindBoneIndex(*FString::Printf(TEXT("middle_01_%s"), Sx));
			// Round 12: the line runs across the palm from the index knuckle to the little finger's (before, the wrist kept
			// the stance's turn and the closed fingers met the tiller extension end on, an open hand beside it).
			const int32 IndexK = Ref.FindBoneIndex(*FString::Printf(TEXT("index_01_%s"), Sx));
			const int32 PinkyK = Ref.FindBoneIndex(*FString::Printf(TEXT("pinky_01_%s"), Sx));
			const int32 Forearm = Ref.GetParentIndex(Hand);
			const bool bAlong = !Hands.Along[Side].IsNearlyZero() && IndexK != INDEX_NONE && PinkyK != INDEX_NONE && Forearm != INDEX_NONE;
			// (Turned first, then reached: the wrist ends where the palm closes on the target, the line within a few degrees
			// of across it as the second reach turns the forearm.)
			for (int32 Pass = 0; Pass < 2; ++Pass)
			{
				if (bAlong)
				{
					const FVector Across = (CS[IndexK].GetLocation() - CS[PinkyK].GetLocation()).GetSafeNormal();
					FVector Line = Hands.Along[Side].GetSafeNormal();
					if (FVector::DotProduct(Across, Line) < 0.0) Line = -Line;
					FQuat PalmTurn = FQuat::FindBetweenNormals(Across, Line);
					// Within the wrist's range.
					const double TurnRad = PalmTurn.GetAngle(), MaxRad = FMath::DegreesToRadians(55.0);
					if (TurnRad > MaxRad) PalmTurn = FQuat::Slerp(FQuat::Identity, PalmTurn, MaxRad / TurnRad);
					Carried.Add(Ref.GetBoneName(Hand), D[Forearm].Inverse() * PalmTurn * D[Hand]);
					Solve(Ref, RestCS, Carried, CS, &D);
				}
				const FVector Palm = Knuckle == INDEX_NONE ? FVector::ZeroVector : (CS[Knuckle].GetLocation() - CS[Hand].GetLocation()) * 0.75;
				ReachArm(Ref, CS, D, Hand, Target - Palm, Carried);
				Solve(Ref, RestCS, Carried, CS, &D);
			}
		}
		return bMoved;
	}

	void Pose(const FReferenceSkeleton& Ref, const TMap<FName, FQuat>& Joints, const FCrewRig* Rig, TArray<FTransform>& CS,
		const FCrewHands* Hands)
	{
		TArray<FTransform> Rest;
		const bool bRig = Rig && Rig->bValid && Rig->RestCS.Num() == Ref.GetNum();
		if (!bRig) RestPose(Ref, Rest);
		const TArray<FTransform>& RestCS = bRig ? Rig->RestCS : Rest;
		TMap<FName, FQuat> Carried;
		if (bRig) Carry(*Rig, Joints, Carried);
		else Carried = Joints;
		if (!Hands)
		{
			Solve(Ref, RestCS, Carried, CS);
			return;
		}
		if (bRig) CurlFingers(*Rig, *Hands, Carried);
		TArray<FQuat> D;
		Solve(Ref, RestCS, Carried, CS, &D);
		// Crew pose fix: the feet first (the hands' Knee mode rests on the knees where they end up).
		if (Hands->Ground && Hands->Ground->Config) PlantAllFeet(Ref, RestCS, CS, D, bRig ? Rig->Frame : FQuat::Identity, *Hands->Ground, Carried);
		if (PlaceHands(Ref, RestCS, CS, D, *Hands, Carried)) Solve(Ref, RestCS, Carried, CS);
	}
}

const TCHAR* MetaHumanRoleName(int32 Role)
{
	static const TCHAR* Names[NumMetaHumanRoles] = { TEXT("Helm"), TEXT("Trimmer"), TEXT("Bow") };
	return Names[FMath::Clamp(Role, 0, NumMetaHumanRoles - 1)];
}

bool LoadMetaHumanCrew(int32 Role, USkeletalMesh*& Body, USkeletalMesh*& Face, USkeletalMesh*& Outfit)
{
	const FString R = MetaHumanRoleName(Role);
	auto Load = [](const FString& Path) { return LoadObject<USkeletalMesh>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet); };
	Body = Load(FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Body/SKM_%s_BodyMesh.SKM_%s_BodyMesh"), *R, *R, *R));
	Face = Load(FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Face/SKM_%s_FaceMesh.SKM_%s_FaceMesh"), *R, *R, *R));
	Outfit = Load(FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Clothing/%s_Outfits.%s_Outfits"), *R, *R, *R));
	return Body && Face;
}

void LoadMetaHumanGrooms(int32 Role, TArray<TPair<UGroomAsset*, UGroomBindingAsset*>>& Grooms)
{
	// Graphics G3: the grooms the build made for this character (hair, eyebrows, beard, moustache), each with the binding
	// to its face mesh (<Groom>_Binding). Eyelashes and peach fuzz are left out: at sailing distances they cost and show nothing.
	Grooms.Reset();
	const FString Dir = FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Grooms"), MetaHumanRoleName(Role));
	TArray<FAssetData> Assets;
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	Registry.ScanPathsSynchronous({ Dir }); // uncooked runs scan in the background: the folder may not be in yet
	Registry.GetAssetsByPath(FName(*Dir), Assets);
	for (const FAssetData& A : Assets)
	{
		if (A.AssetClassPath != UGroomAsset::StaticClass()->GetClassPathName()) continue;
		const FString Name = A.AssetName.ToString();
		if (Name.Contains(TEXT("Eyelash")) || Name.Contains(TEXT("Fuzz"))) continue;
		UGroomAsset* Groom = Cast<UGroomAsset>(A.GetAsset());
		UGroomBindingAsset* Binding = LoadObject<UGroomBindingAsset>(nullptr, *FString::Printf(TEXT("%s/%s_Binding.%s_Binding"), *Dir, *Name, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
		if (Groom && Binding) Grooms.Add({ Groom, Binding });
	}
	UE_LOG(LogTemp, Log, TEXT("MetaHuman %s: %d grooms"), MetaHumanRoleName(Role), Grooms.Num());
}

void BuildCrewRig(const USkeletalMesh* Mesh, FCrewRig& Rig)
{
	Rig = FCrewRig();
	if (!Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	TArray<FTransform> Rest;
	CrewSolver::RestPose(Ref, Rest);
	auto At = [&](const TCHAR* Name) -> FVector
	{
		const int32 B = Ref.FindBoneIndex(Name);
		return B == INDEX_NONE ? FVector::ZeroVector : Rest[B].GetLocation();
	};
	// Facing: heel to ball of the foot.
	if (Ref.FindBoneIndex(TEXT("foot_l")) != INDEX_NONE && Ref.FindBoneIndex(TEXT("ball_l")) != INDEX_NONE)
	{
		const FVector Fwd = (At(TEXT("ball_l")) - At(TEXT("foot_l"))).GetSafeNormal2D();
		if (!Fwd.IsNearlyZero()) Rig.Frame = FQuat::FindBetweenNormals(FVector::ForwardVector, Fwd);
	}
	if (Ref.FindBoneIndex(TEXT("spine_01")) != INDEX_NONE)
	{
		auto Add = [&](const TCHAR* Joint, std::initializer_list<TPair<FName, float>> Bones) { Rig.Map.Add(Joint, TArray<TPair<FName, float>>(Bones)); };
		Add(TEXT("spine"), { { TEXT("spine_01"), 0.5f }, { TEXT("spine_02"), 0.5f } });
		Add(TEXT("chest"), { { TEXT("spine_03"), 0.34f }, { TEXT("spine_04"), 0.33f }, { TEXT("spine_05"), 0.33f } });
		Add(TEXT("neck"), { { TEXT("neck_01"), 0.5f }, { TEXT("neck_02"), 0.5f } });
		Add(TEXT("forearm_l"), { { TEXT("lowerarm_l"), 1.f } });
		Add(TEXT("forearm_r"), { { TEXT("lowerarm_r"), 1.f } });
		// Crew C1b: the idle clips turn the shoulders.
		Add(TEXT("shoulder_l"), { { TEXT("clavicle_l"), 1.f } });
		Add(TEXT("shoulder_r"), { { TEXT("clavicle_r"), 1.f } });
	}
	// The arms out level (SK_Sailor's T-pose): turn each upper arm to point straight out, then straighten the elbow.
	TMap<FName, FQuat> Fix;
	for (const bool bLeft : { true, false })
	{
		const FName Upper = bLeft ? TEXT("upperarm_l") : TEXT("upperarm_r");
		const FName Lower = bLeft ? TEXT("lowerarm_l") : TEXT("lowerarm_r");
		const FName Hand = bLeft ? TEXT("hand_l") : TEXT("hand_r");
		const int32 U = Ref.FindBoneIndex(Upper), L = Ref.FindBoneIndex(Lower), H = Ref.FindBoneIndex(Hand);
		if (U == INDEX_NONE || L == INDEX_NONE || H == INDEX_NONE) continue;
		const FVector Want = Rig.Frame.RotateVector(bLeft ? -FVector::RightVector : FVector::RightVector);
		const FQuat CU = FQuat::FindBetweenNormals((Rest[L].GetLocation() - Rest[U].GetLocation()).GetSafeNormal(), Want);
		const FQuat CL = FQuat::FindBetweenNormals((Rest[H].GetLocation() - Rest[L].GetLocation()).GetSafeNormal(), CU.Inverse().RotateVector(Want));
		Fix.Add(Upper, CU);
		Fix.Add(Lower, CL);
	}
	CrewSolver::Solve(Ref, Rest, Fix, Rig.RestCS);
	// Graphics G8: the fingers' curl axes. The palm faces the side the resting fingers already bend toward (the middle
	// finger's tip off the line of its first two joints), else the thumb's side; each joint curls about (bone x palm).
	auto RestAt = [&](const FString& Name) -> TOptional<FVector>
	{
		const int32 B = Ref.FindBoneIndex(*Name);
		return B == INDEX_NONE ? TOptional<FVector>() : TOptional<FVector>(Rig.RestCS[B].GetLocation());
	};
	for (const TCHAR* Sx : { TEXT("l"), TEXT("r") })
	{
		const TOptional<FVector> Hand = RestAt(FString::Printf(TEXT("hand_%s"), Sx)), I1 = RestAt(FString::Printf(TEXT("index_01_%s"), Sx)),
			P1 = RestAt(FString::Printf(TEXT("pinky_01_%s"), Sx)), M1 = RestAt(FString::Printf(TEXT("middle_01_%s"), Sx)),
			M2 = RestAt(FString::Printf(TEXT("middle_02_%s"), Sx)), M3 = RestAt(FString::Printf(TEXT("middle_03_%s"), Sx)),
			T3 = RestAt(FString::Printf(TEXT("thumb_03_%s"), Sx));
		if (!Hand || !I1 || !P1 || !M1 || !M2 || !M3) continue;
		FVector Palm = FVector::CrossProduct(*I1 - *Hand, *P1 - *Hand).GetSafeNormal();
		const FVector Line = (*M2 - *M1);
		const FVector Bend = (*M3 - *M2) - Line.GetSafeNormal() * FVector::DotProduct(*M3 - *M2, Line.GetSafeNormal());
		const double Sign = Bend.Size() > 0.05 ? FVector::DotProduct(Bend, Palm) : (T3 ? FVector::DotProduct(*T3 - *Hand, Palm) : 1.0);
		if (Sign < 0.0) Palm = -Palm;
		// Round 12: the thumb swings about the palm's normal, the way that turns it toward the middle finger.
		const TOptional<FVector> T1 = RestAt(FString::Printf(TEXT("thumb_01_%s"), Sx)), T2 = RestAt(FString::Printf(TEXT("thumb_02_%s"), Sx));
		if (T1 && T2)
		{
			const double ThumbToward = FVector::DotProduct(Palm, FVector::CrossProduct(*T2 - *T1, *M1 - *Hand));
			Rig.ThumbSwing[Sx[0] == TEXT('l') ? 0 : 1] = ThumbToward >= 0.0 ? Palm : -Palm;
		}
		for (const TCHAR* Finger : CrewSolver::FingerNames)
		{
			for (int32 K = 1; K <= 3; ++K)
			{
				const TOptional<FVector> A = RestAt(FString::Printf(TEXT("%s_0%d_%s"), Finger, K, Sx));
				const TOptional<FVector> B = RestAt(FString::Printf(TEXT("%s_0%d_%s"), Finger, K < 3 ? K + 1 : K, Sx));
				const TOptional<FVector> Prev = RestAt(FString::Printf(TEXT("%s_0%d_%s"), Finger, K - 1, Sx));
				if (!A) continue;
				const FVector Dir = K < 3 && B ? *B - *A : (Prev ? *A - *Prev : FVector::ZeroVector);
				const FVector Axis = FVector::CrossProduct(Dir, Palm).GetSafeNormal();
				if (!Axis.IsNearlyZero()) Rig.CurlAxis.Add(*FString::Printf(TEXT("%s_0%d_%s"), Finger, K, Sx), Axis);
			}
		}
	}
	// Round 12: the thumb swings the way (about the palm's normal, or not at all) that brings its tip nearest the index
	// finger in a fist, tried on this skeleton: the guess from the rest pose alone barely moved it on some hands.
	FCrewHands Fist;
	Fist.Grip[0] = Fist.Grip[1] = 1.f;
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const TCHAR* Sx = Side == 0 ? TEXT("l") : TEXT("r");
		const int32 Tip = Ref.FindBoneIndex(*FString::Printf(TEXT("thumb_03_%s"), Sx)), Knuckle = Ref.FindBoneIndex(*FString::Printf(TEXT("index_02_%s"), Sx));
		const FVector Swing = Rig.ThumbSwing[Side];
		if (Tip == INDEX_NONE || Knuckle == INDEX_NONE || Swing.IsNearlyZero()) continue;
		double Nearest = TNumericLimits<double>::Max();
		FVector NearestSwing = FVector::ZeroVector;
		for (const FVector& Try : { FVector::ZeroVector, Swing, -Swing })
		{
			Rig.ThumbSwing[Side] = Try;
			TMap<FName, FQuat> Curled;
			CrewSolver::CurlFingers(Rig, Fist, Curled);
			TArray<FTransform> Posed;
			CrewSolver::Solve(Ref, Rig.RestCS, Curled, Posed);
			const double Gap = FVector::Dist(Posed[Tip].GetLocation(), Posed[Knuckle].GetLocation());
			if (Gap < Nearest - 0.1)
			{
				Nearest = Gap;
				NearestSwing = Try;
			}
		}
		Rig.ThumbSwing[Side] = NearestSwing;
	}
	const int32 P = Ref.FindBoneIndex(TEXT("pelvis"));
	Rig.Pelvis = P == INDEX_NONE ? FVector::ZeroVector : Rig.RestCS[P].GetLocation();
	Rig.bValid = true;
}

FTransform FCrewRig::Rest(const USkeletalMesh* Mesh, FName Bone) const
{
	const int32 B = Mesh ? Mesh->GetRefSkeleton().FindBoneIndex(Bone) : INDEX_NONE;
	return B == INDEX_NONE || !RestCS.IsValidIndex(B) ? FTransform::Identity : RestCS[B];
}

void CrewPosedJoints(const USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, TMap<FName, FVector>& Out, const FCrewRig* Rig, const FCrewHands* Hands)
{
	Out.Reset();
	if (!Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	TArray<FTransform> CS;
	CrewSolver::Pose(Ref, Joints, Rig, CS, Hands);
	for (int32 B = 0; B < CS.Num(); ++B) Out.Add(Ref.GetBoneName(B), CS[B].GetLocation());
}

void CrewFootPoints(const USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, FVector Out[2][2], const FCrewRig* Rig, const FCrewHands* Hands)
{
	for (int32 S = 0; S < 2; ++S) Out[S][0] = Out[S][1] = FVector::ZeroVector;
	if (!Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	TArray<FTransform> Rest, CS;
	const bool bRig = Rig && Rig->bValid && Rig->RestCS.Num() == Ref.GetNum();
	if (bRig) Rest = Rig->RestCS;
	else CrewSolver::RestPose(Ref, Rest);
	CrewSolver::Pose(Ref, Joints, Rig, CS, Hands);
	for (int32 S = 0; S < 2; ++S) CrewSolver::SolePoints(Ref, Rest, CS, bRig ? Rig->Frame : FQuat::Identity, S, Out[S]);
}

bool CrewCockpitWell(const Sailing::FBoatConfig& C, FCrewCockpitWell& W)
{
	using Sailing::EBoatType;
	W = FCrewCockpitWell();
	const Sailing::FHullShape& H = C.Hulls[0];
	// build_fleet.py cockpit(): (aft, forward, half width, depth below the deck); seats along both sides when deeper than 0.3 m.
	auto Fleet = [&](double X0, double X1, double Half, double Depth)
	{
		W.X0 = X0; W.X1 = X1; W.HalfWidth = Half;
		W.SoleZ = H.SheerHeight(0.5 * (X0 + X1)) - Depth;
		if (Depth > 0.3) { W.SeatW = 0.34 * FMath::Min(1.0, Half / 0.6); W.SeatZ = W.SoleZ + Depth - 0.14; }
		return true;
	};
	switch (C.Type)
	{
	case EBoatType::J22:
		// build_j22.py: COCKPIT_AFT, CABIN_AFT, SIDE_DECK, SEAT_Z, SEAT_W, SOLE_Z.
		W.X0 = H.SternX + 0.14; W.X1 = -0.72; W.SideDeck = 0.36; W.SeatZ = 0.47; W.SeatW = 0.36; W.SoleZ = 0.30;
		// The traveler's bridge: 16 cm fore and aft at TRAV_X, its top 1.5 cm over the seats.
		W.BridgeX = -1.75; W.BridgeHalfX = 0.08; W.BridgeZ = 0.485;
		return true;
	case EBoatType::Sunfish: return Fleet(-1.18, -0.52, 0.29, 0.20);
	case EBoatType::ILCA7: return Fleet(-1.62, -0.22, 0.31, 0.22);
	case EBoatType::Catalina22: return Fleet(-3.05, -0.78, 0.63, 0.42);
	case EBoatType::Catalina30: return Fleet(-4.05, -1.32, 0.82, 0.5);
	case EBoatType::Corsair880: return Fleet(-3.75, -0.95, 0.62, 0.45);
	default: return false;
	}
}

namespace
{
	/** Is (X, |y|) inside the main hull's cockpit well, and its floor there. */
	bool InWell(const Sailing::FBoatConfig& C, const FCrewCockpitWell& W, double X, double Y, double& Floor)
	{
		if (X <= W.X0 || X >= W.X1) return false;
		const double Half = W.SideDeck > 0.0 ? C.Hulls[0].DeckHalfBeam(X) - W.SideDeck : W.HalfWidth;
		if (Y >= Half) return false;
		Floor = W.SeatZ > 0.0 && Y > Half - W.SeatW ? W.SeatZ : W.SoleZ;
		// Round 12: the helm's forward foot had sunk into the J/22's traveler bridge (this didn't know it was there).
		if (W.BridgeHalfX > 0.0 && FMath::Abs(X - W.BridgeX) < W.BridgeHalfX && Y <= Half - W.SeatW) Floor = W.BridgeZ;
		return true;
	}
}

double CrewFloorZ(const Sailing::FBoatConfig& C, double X, double Y)
{
	FCrewCockpitWell W;
	const bool bWell = CrewCockpitWell(C, W);
	for (int32 K = 0; K < int32(C.Hulls.size()); ++K)
	{
		const Sailing::FHullShape& H = C.Hulls[K];
		const double Yh = FMath::Abs(Y - H.CenterY);
		if (X < H.SternX || X > H.BowX || Yh >= H.DeckHalfBeam(X)) continue;
		double Floor = 0.0;
		if (K == 0 && bWell && InWell(C, W, X, Yh, Floor)) return Floor;
		return H.SheerHeight(X);
	}
	return -1e9;
}

bool CrewInsideBoat(const Sailing::FBoatConfig& C, double HullDepth, const FVector& P)
{
	FCrewCockpitWell W;
	const bool bWell = CrewCockpitWell(C, W);
	for (int32 K = 0; K < int32(C.Hulls.size()); ++K)
	{
		const Sailing::FHullShape& H = C.Hulls[K];
		const double Y = FMath::Abs(P.Y - H.CenterY);
		if (P.X < H.SternX || P.X > H.BowX || Y >= H.DeckHalfBeam(P.X) || P.Z >= H.SheerHeight(P.X)) continue;
		if (P.Z <= H.BottomZ(P.X, Y, HullDepth)) continue;
		double Floor = 0.0;
		if (K == 0 && bWell && InWell(C, W, P.X, Y, Floor) && P.Z >= Floor) continue;
		return true;
	}
	return false;
}
