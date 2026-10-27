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
		// On a flat deck (bFlatDeck) the knees come up and the feet rest on the deck in front.
		if (P.bFlatDeck) Legs(Out, 116.f - 6.f * H, 64.f, 12.f);
		else Legs(Out, 84.f - 8.f * H, 82.f - 22.f * H, 8.f);
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
		// (Folded up to 35 deg further under a low boom, the head lifted to keep the eyes forward: P.Stoop.)
		Out.Add(TEXT("spine"), Lean(25.f + 20.f * FMath::Clamp(P.Stoop, 0.f, 1.f)));
		Out.Add(TEXT("chest"), Lean(20.f + 15.f * FMath::Clamp(P.Stoop, 0.f, 1.f)));
		Out.Add(TEXT("neck"), Lean(-30.f - 25.f * FMath::Clamp(P.Stoop, 0.f, 1.f)));
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
		// docs/crew-light-air/: on a flat deck (the Hobie's trampoline) the knees come up and the feet rest on it in front.
		if (P.bFlatDeck) Legs(Out, 116.f - 6.f * H, 64.f, 12.f);
		else Legs(Out, 80.f - 12.f * H, 25.f + 30.f * (1.f - H), 9.f);
		// Sitting in from the edge (light air, a run: the crew model has them inboard) they sit up, a little forward over
		// the tiller and sheet; leaning back 20 deg there, face to the sky, read as a full hike in 4 kn (docs/crew-light-air/).
		const float In = FMath::Clamp(P.Inboard, 0.f, 1.f);
		const float L = FMath::Lerp(-(20.f + 50.f * H), 8.f, In);
		Out.Add(TEXT("spine"), Lean(0.5f * L));
		Out.Add(TEXT("chest"), Lean(0.5f * L));
		// Graphics G8: the head turned toward the bow (the luff and the water ahead), not staring across the boat.
		Out.Add(TEXT("neck"), Q(FVector::UpVector, 30.f * P.Side) * Lean(-0.7f * FMath::Min(L, 0.f)));   // (level against a lean back only)
		// (Round 10: the elbows nearer the sides; the hands' reach keeps this plane, and 40 deg down held them out like wings.)
		Arms(Out, 65.f, 55.f, 45.f, 65.f, 55.f, 45.f);
		break;
	}
	case ECrewStance::Trapeze:
		// Standing on the rail, body straight; one hand on the handle, the other on the sheet. docs/crew-followups/: the
		// handle hand at chest height toward the wire, elbow bent (the hook takes the weight); raised 55 deg over the
		// shoulder, with the body flat out over the water, it read as flailing.
		Legs(Out, 4.f, 6.f, 8.f);
		Arms(Out, 15.f, 55.f, 65.f, 70.f, 40.f, 40.f);
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

	/** The middle joint's hinge in the rest pose (component space), its flexion positive about it, and that joint's limit
	 *  (deg): the elbow turns about the character's up (+ on the left, - on the right: the T-posed arm's forearm swings
	 *  forward), the knee about the character's right (the calf swings back). The right is read off the hips, so it holds
	 *  for every rig's frame. */
	bool LimbHinge(const FReferenceSkeleton& Ref, const TArray<FTransform>& CS, const TArray<FQuat>& D, int32 Lower, FVector& OutRest, double& OutMaxDeg)
	{
		const FString Name = Ref.GetBoneName(Lower).ToString().ToLower();
		const bool bLeft = Name.EndsWith(TEXT("_l"));
		if (!bLeft && !Name.EndsWith(TEXT("_r"))) return false;
		if (Name.StartsWith(TEXT("calf")) || Name.StartsWith(TEXT("shin")))
		{
			const int32 ThighL = Ref.FindBoneIndex(TEXT("thigh_l")), ThighR = Ref.FindBoneIndex(TEXT("thigh_r"));
			if (ThighL == INDEX_NONE || ThighR == INDEX_NONE) return false;
			const int32 Hips = Ref.GetParentIndex(ThighL);
			if (Hips == INDEX_NONE) return false;
			OutRest = D[Hips].UnrotateVector(CS[ThighR].GetLocation() - CS[ThighL].GetLocation()).GetSafeNormal();
			OutMaxDeg = 150.0;
			return !OutRest.IsNearlyZero();
		}
		OutRest = bLeft ? FVector::UpVector : -FVector::UpVector;
		OutMaxDeg = 145.0;
		return true;
	}

	/** Graphics G8, docs/crew-elbow/: two-bone IK for one arm (or leg) toward a wrist (ankle) target, component space. The
	 *  middle joint is a hinge: the forearm turns only about the elbow's own axis, which the upper arm carries, flexed
	 *  between straight and 145 deg (the knee 150), never backwards. The elbow sits in the stance's bend plane where that is
	 *  within 45 deg of where the arm's own hinge puts it (or where Bend asks, a dinghy's knees up under the strap); the
	 *  upper arm turns so its hinge is square to that plane. Before, the elbow went in the stance's plane and the forearm
	 *  was turned straight at the target about any axis: for a target across that plane it folded the wrong way, and the
	 *  held line's swing walked it freely round the reach (Bean's playtest: elbows bent backwards). */
	void ReachArm(const FReferenceSkeleton& Ref, const TArray<FTransform>& CS, const TArray<FQuat>& D, int32 Hand, const FVector& Target,
		TMap<FName, FQuat>& Joints, const FVector& HeldLine, const FVector& Bend)
	{
		const int32 Lower = Ref.GetParentIndex(Hand);
		const int32 Upper = Lower == INDEX_NONE ? INDEX_NONE : Ref.GetParentIndex(Lower);
		const int32 Above = Upper == INDEX_NONE ? INDEX_NONE : Ref.GetParentIndex(Upper);
		if (Above == INDEX_NONE) return;
		FVector HingeRest;
		double MaxFlex = 145.0;
		if (!LimbHinge(Ref, CS, D, Lower, HingeRest, MaxFlex)) return;
		const FVector S = CS[Upper].GetLocation(), E = CS[Lower].GetLocation(), W = CS[Hand].GetLocation();
		const double A = FVector::Dist(S, E), B = FVector::Dist(E, W);
		const FVector ToT = Target - S;
		// Out of reach: the arm straight (half a centimetre short) and the hand falls short; too close: folded to the limit.
		const double MinDist = FMath::Sqrt(FMath::Max(A * A + B * B - 2.0 * A * B * FMath::Cos(FMath::DegreesToRadians(180.0 - MaxFlex)), 0.0)) + 0.1;
		const double Dist = FMath::Clamp(ToT.Size(), FMath::Max(FMath::Abs(A - B) + 1.0, MinDist), A + B - 0.5);
		const FVector X = ToT.GetSafeNormal();
		if (X.IsNearlyZero()) return;
		const double CosA = FMath::Clamp((A * A + Dist * Dist - B * B) / (2.0 * A * Dist), -1.0, 1.0);
		const double SinA = FMath::Sqrt(FMath::Max(0.0, 1.0 - CosA * CosA));
		const FVector T2 = S + X * Dist;
		auto ElbowAt = [&](const FVector& Yk) { return S + X * (A * CosA) + Yk * (A * SinA); };
		// The arm's own hinge now (the upper arm carries it), and the bend direction it gives: square to the hinge and the
		// reach, on the side that flexes the joint the right way.
		const FVector Hinge = D[Upper].RotateVector(HingeRest);
		FVector YHinge = FVector::CrossProduct(Hinge, X);
		if (YHinge.SizeSquared() < 1e-6) YHinge = FVector::CrossProduct(X, FVector::CrossProduct(FVector(0, 0, -1), X));
		YHinge = YHinge.GetSafeNormal();
		{
			const FVector E2 = ElbowAt(YHinge);
			if (FVector::DotProduct(Hinge, FVector::CrossProduct(E2 - S, T2 - E2)) < 0.0) YHinge = -YHinge;
		}
		const FVector Z = FVector::CrossProduct(X, YHinge);
		auto SwingOf = [&](const FVector& V) { return FMath::Atan2(FVector::DotProduct(V, Z), FVector::DotProduct(V, YHinge)); };
		auto AtSwing = [&](double Rad) { return YHinge * FMath::Cos(Rad) + Z * FMath::Sin(Rad); };
		constexpr double MaxSwing = UE_DOUBLE_PI / 4.0;
		// The stance's bend plane (or the asked bend), within 45 deg of the hinge's.
		FVector Want = (E - S) - X * FVector::DotProduct(E - S, X);
		if (!Bend.IsNearlyZero())
		{
			const FVector YB = Bend - X * FVector::DotProduct(Bend, X);
			if (YB.SizeSquared() > 0.01 * Bend.SizeSquared()) Want = YB;
		}
		double Swing = Want.SizeSquared() < 1.0 ? 0.0 : FMath::Clamp(SwingOf(Want), -MaxSwing, MaxSwing);
		// Holding a line: the elbow swings about the reach (10 deg steps, still inside the band, the elbow kept low) to where
		// the forearm runs most nearly square to the line, so the line lies across the palm with the wrist near straight
		// (the PC, Ultra: with the stance's elbow, a sheet led along the forearm cocked the wrist 60-70 deg).
		if (!HeldLine.IsNearlyZero())
		{
			const FVector Line = HeldLine.GetSafeNormal();
			auto SquareAt = [&](double Rad) { return FMath::Abs(FVector::DotProduct((T2 - ElbowAt(AtSwing(Rad))).GetSafeNormal(), Line)); };
			const double Stance = SquareAt(Swing);
			double Best = Stance, BestSwing = Swing;
			for (int32 K = -9; K <= 9; ++K)
			{
				const double Rad = FMath::DegreesToRadians(10.0 * K);
				if (FMath::Abs(Rad) > MaxSwing + 1e-6) continue;
				// (Never with the elbow raised: no higher than the shoulder; swung up, the trimmer's arm went up past the head
				// and the shoulder's skin and vest tore.)
				if ((ElbowAt(AtSwing(Rad)) - S).Z > -0.05 * A) continue;
				const double Cost = SquareAt(Rad) + 0.08 * FMath::Abs(Rad - Swing);   // (a little to stay near the stance's own elbow)
				if (Cost < Best) { Best = Cost; BestSwing = Rad; }
			}
			// (Only for a real gain: a line led along the reach is at the same angle to the forearm wherever the elbow goes.)
			if (Stance - SquareAt(BestSwing) > 0.15) Swing = BestSwing;
		}
		const FVector Y = AtSwing(Swing);
		const FVector E2 = ElbowAt(Y);
		const FVector Up = (E2 - S).GetSafeNormal(), Fore = (T2 - E2).GetSafeNormal();
		// The hinge that bends this arm the right way: square to both bones (the straight arm keeps the swung hinge).
		FVector NewHinge = FVector::CrossProduct(Up, Fore);
		NewHinge = NewHinge.SizeSquared() < 1e-8 ? (Hinge - Up * FVector::DotProduct(Hinge, Up)).GetSafeNormal() : NewHinge.GetSafeNormal();
		// Upper arm: aimed along its new direction with its hinge onto the new one (aim with an up vector).
		auto Basis = [](const FVector& Dir, const FVector& Side)
		{
			const FVector Xb = Dir.GetSafeNormal();
			const FVector Yb = (Side - Xb * FVector::DotProduct(Side, Xb)).GetSafeNormal();
			return FQuat(FMatrix(Xb, Yb, FVector::CrossProduct(Xb, Yb), FVector::ZeroVector));
		};
		const FQuat Q1 = Basis(Up, NewHinge) * Basis(E - S, Hinge).Inverse();
		const FQuat DU = Q1 * D[Upper];
		// Forearm: the rest forearm, carried by the new upper arm, turned about the hinge alone onto the target.
		const FVector RestFore = D[Lower].UnrotateVector(W - E).GetSafeNormal();
		const FVector Carried = DU.RotateVector(RestFore);
		const double Theta = FMath::Atan2(FVector::DotProduct(NewHinge, FVector::CrossProduct(Carried, Fore)), FVector::DotProduct(Carried, Fore));
		const FQuat DL = FQuat(NewHinge, Theta) * DU;
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
	 *  (through the topsides), inboard to the well (or the deck) first; the leg reaches it by two-bone IK. Sitting in a
	 *  cockpit, a foot hanging over the well's sole goes down onto it. */
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
			auto Inside = [&](const FVector& P) { return CrewInsideBoat(C, G.HullDepth, P + FVector(0.0, 0.0, 0.015), G.bTravelerBridge); };
			if (!Inside(B[0]) && !Inside(B[1]))
			{
				// Round 12, the hero J/22: the helm's forward foot hung in the air where the light model's traveler bridge
				// had caught it. A foot over one of the well's levels (the sole or a seat, not the bridge or the deck) up to
				// 25 cm above it goes down onto it; the reach
				// fades out by 32 cm, so a knee drawn up stays up and an idle clip moving the leg does not make it jump. Only
				// a sole within 35 deg of level: a foot hanging pointed down would land on its toe with the heel up (the
				// ankle's 45 deg in LevelFeet can't lay it flat), so it is left hanging.
				FCrewCockpitWell Well;
				if (!G.bFeetDown || !CrewCockpitWell(C, Well, G.bTravelerBridge)) continue;
				const double FootLevel = CrewFloorZ(C, B[0].X, B[0].Y, G.bTravelerBridge);
				const bool bWellLevel = FMath::Abs(FootLevel - Well.SoleZ) <= 0.01 || (Well.SeatZ > 0.0 && FMath::Abs(FootLevel - Well.SeatZ) <= 0.01);
				if (!bWellLevel || FMath::Abs(CrewFloorZ(C, B[1].X, B[1].Y, G.bTravelerBridge) - FootLevel) > 0.01) continue;
				const FVector SoleDir = B[1] - B[0];
				if (FMath::Abs(SoleDir.Z) > FMath::Sin(FMath::DegreesToRadians(35.0)) * SoleDir.Size()) continue;
				const double Hang = FMath::Min(B[0].Z, B[1].Z) - FootLevel;
				const double DownWeight = FMath::Clamp((0.32 - Hang) / 0.07, 0.0, 1.0);
				if (Hang < 0.01 || DownWeight <= 0.0) continue;
				const FVector Down(0.0, 0.0, -(Hang - 0.005) * DownWeight);
				const FVector Target = G.ToBoat.InverseTransformPosition(G.ToBoat.TransformPosition(CS[Foot].GetLocation()) + Down / M);
				ReachArm(Ref, CS, D, Foot, Target, Joints);
				bMoved = true;
				continue;
			}
			FVector Shift = FVector::ZeroVector;
			const FVector Mid = 0.5 * (B[0] + B[1]);
			const double Off = -1e8;
			// Off the deck's plan (through the topsides), or under the side deck beside the well: bring it inboard, into the
			// well where there is one alongside, else onto the nearest hull's deck, 8 cm in from the edge.
			const bool bOffPlan = CrewFloorZ(C, B[0].X, B[0].Y, G.bTravelerBridge) < Off || CrewFloorZ(C, B[1].X, B[1].Y, G.bTravelerBridge) < Off;
			int32 Near = 0;
			for (int32 K = 1; K < int32(C.Hulls.size()); ++K)
			{
				if (FMath::Abs(Mid.Y - C.Hulls[K].CenterY) < FMath::Abs(Mid.Y - C.Hulls[Near].CenterY)) Near = K;
			}
			const FHullShape& H = C.Hulls[Near];
			FCrewCockpitWell W;
			const bool bWell = Near == 0 && CrewCockpitWell(C, W, G.bTravelerBridge) && Mid.X > W.X0 && Mid.X < W.X1;
			const double Limit = (bWell ? (W.SideDeck > 0.0 ? H.DeckHalfBeam(Mid.X) - W.SideDeck : W.HalfWidth) : H.DeckHalfBeam(Mid.X)) - 0.08;
			const double Y = FMath::Max(FMath::Abs(B[0].Y - H.CenterY), FMath::Abs(B[1].Y - H.CenterY));
			// docs/crew-hull-clip/: a foot only just into the deck (within 12 cm of its surface: a crown, a pose resting a
			// heel on it) is lifted onto the deck where it is; only one deep under a side deck goes into the well. The
			// maxi's rail crew at her cockpit's forward end had their feet sent 40 cm down into it.
			const double DeckHere = FMath::Max(CrewFloorZ(C, B[0].X, B[0].Y, G.bTravelerBridge), CrewFloorZ(C, B[1].X, B[1].Y, G.bTravelerBridge));
			const bool bJustInto = !bOffPlan && FMath::Min(B[0].Z, B[1].Z) > DeckHere - 0.12;
			// (And only a foot under a side deck beside the well, within 0.4 m of it, the J/22's side deck and its edge: further
			// out it is on the deck.)
			const bool bBesideWell = bWell && Y - Limit < 0.40 && !G.bFlatDeck;
			if (Y > Limit && (bOffPlan || bBesideWell) && !bJustInto)
			{
				Shift.Y = (Mid.Y >= H.CenterY ? -1.0 : 1.0) * (Y - Limit);
			}
			for (FVector& P : B) P += Shift;
			const double Floor = FMath::Max(CrewFloorZ(C, B[0].X, B[0].Y, G.bTravelerBridge), CrewFloorZ(C, B[1].X, B[1].Y, G.bTravelerBridge));
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
			// The winch hand (the PC, Ultra): closed round a line the fingers stop at its radius (a 6 mm sheet, a tiller
			// extension), not in a full fist, which folded them into a mitten through the line.
			const bool bHeld = Hands.Mode[Side] == FCrewHands::EMode::Reach;
			for (const TCHAR* Finger : FingerNames)
			{
				const bool bThumb = Finger[0] == TEXT('t');
				const float Deg[3] = { bThumb ? 38.f : bHeld ? 55.f : 72.f, bThumb ? 58.f : bHeld ? 70.f : 95.f, bThumb ? 50.f : bHeld ? 45.f : 62.f }; // round 12: the thumb had stood up off a held line
				for (int32 K = 1; K <= 3; ++K)
				{
					const FName Bone(*FString::Printf(TEXT("%s_0%d_%s"), Finger, K, Side == 0 ? TEXT("l") : TEXT("r")));
					const FVector* Axis = Rig.CurlAxis.Find(Bone);
					if (!Axis) continue;
					const FQuat JointTurn(*Axis, FMath::DegreesToRadians(G * Deg[K - 1]));
					Carried.Add(Bone, bThumb ? FQuat::Slerp(FQuat::Identity, Rig.ThumbTurn[Side][K - 1], G) * JointTurn : JointTurn);
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
			const double HeelFloor = CrewFloorZ(C, Heel.X, Heel.Y, G.bTravelerBridge), ToeFloor = CrewFloorZ(C, Toe.X, Toe.Y, G.bTravelerBridge);
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
			const double NewHeelFloor = CrewFloorZ(C, NewHeel.X, NewHeel.Y, G.bTravelerBridge), NewToeFloor = CrewFloorZ(C, NewToe.X, NewToe.Y, G.bTravelerBridge);
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

	/** The wrist within its range (flexion +-MaxFlexDeg: 60, 40 holding a line; deviation +-25), the turn about the forearm left to it (the forearm
	 *  pronates): the winch hand had been bent 90 deg back by the palm's turn to the line. Axes from the rest pose: the
	 *  forearm toward the hand, across the knuckles, and the palm's normal. */
	void ClampWrist(const TArray<FTransform>& RestCS, const TArray<FQuat>& D, int32 Hand, int32 Forearm, int32 IndexK, int32 PinkyK, FName HandName,
		TMap<FName, FQuat>& Carried, double MaxFlexDeg)
	{
		const FVector Along = (RestCS[Hand].GetLocation() - RestCS[Forearm].GetLocation()).GetSafeNormal();
		FVector Across = RestCS[IndexK].GetLocation() - RestCS[PinkyK].GetLocation();
		Across = (Across - FVector::DotProduct(Across, Along) * Along).GetSafeNormal();
		if (Along.IsNearlyZero() || Across.IsNearlyZero()) return;
		const FVector Normal = FVector::CrossProduct(Along, Across);
		const FQuat* Have = Carried.Find(HandName);
		const FQuat Rel = Have ? *Have : D[Forearm].Inverse() * D[Hand];
		FQuat Swing, Twist;
		Rel.ToSwingTwist(Along, Swing, Twist);
		const FVector V = Swing.ToRotationVector();
		const double Flex = FVector::DotProduct(V, Across), Dev = FVector::DotProduct(V, Normal);
		const double MaxFlex = FMath::DegreesToRadians(MaxFlexDeg), MaxDev = FMath::DegreesToRadians(25.0);
		if (FMath::Abs(Flex) <= MaxFlex && FMath::Abs(Dev) <= MaxDev) return;
		const FVector Clamped = Across * FMath::Clamp(Flex, -MaxFlex, MaxFlex) + Normal * FMath::Clamp(Dev, -MaxDev, MaxDev);
		Carried.Add(HandName, FQuat::MakeFromRotationVector(Clamped) * Twist);
	}

	constexpr double kHeldWristDeg = 40.0; // the wrist's flexion holding a line led along the reach (the elbow swung first: ReachArm)

	/** Each finger of a hand closed on a line stops short of it: a finger whose bones pass within kFingerClearCm of the
	 *  line's axis opens (its three curl joints eased toward straight, 15% a step, at most five) until it clears. The curl's
	 *  fixed angles suit a line square across the palm; led diagonally across it the middle finger closed through it. */
	constexpr double kFingerClearCm = 0.75; // the sheet's radius (3 mm) and a finger bone's from its axis
	bool ClearFingers(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, TArray<FTransform>& CS, TArray<FQuat>& D, const FCrewHands& Hands,
		TMap<FName, FQuat>& Carried)
	{
		bool bMoved = false;
		for (int32 Side = 0; Side < 2; ++Side)
		{
			if (Hands.Mode[Side] != FCrewHands::EMode::Reach || Hands.Along[Side].IsNearlyZero()) continue;
			const FVector Line = Hands.Along[Side].GetSafeNormal(), At = Hands.Target[Side];
			for (int32 F = 0; F < 4; ++F) // not the thumb: it closes over the fingers, not round the line
			{
				int32 Bones[3];
				FName Names[3];
				bool bAll = true;
				for (int32 K = 0; K < 3; ++K)
				{
					Names[K] = FName(*FString::Printf(TEXT("%s_0%d_%s"), FingerNames[F], K + 1, Side == 0 ? TEXT("l") : TEXT("r")));
					Bones[K] = Ref.FindBoneIndex(Names[K]);
					bAll &= Bones[K] != INDEX_NONE;
				}
				if (!bAll) continue;
				FVector Near = FVector::ZeroVector;
				auto Closest = [&]()
				{
					double Best = 1e9;
					for (int32 K = 1; K < 3; ++K)
					{
						for (int32 U = 0; U <= 10; ++U)
						{
							const FVector Q = FMath::Lerp(CS[Bones[K - 1]].GetLocation(), CS[Bones[K]].GetLocation(), U / 10.0);
							const double Dist = FVector::CrossProduct(Q - At, Line).Size();
							if (Dist < Best) { Best = Dist; Near = Q; }
						}
					}
					return Best;
				};
				for (int32 Step = 0; Step < 5 && Closest() < kFingerClearCm; ++Step)
				{
					for (const FName& Name : Names)
					{
						if (const FQuat* Q = Carried.Find(Name)) Carried.Add(Name, FQuat::Slerp(FQuat::Identity, *Q, 0.85f));
					}
					Solve(Ref, RestCS, Carried, CS, &D);
					bMoved = true;
				}
				// Still too close where opening barely moves it (the first bone, by the knuckle, with the line led diagonally across
				// the palm): the hand moves off the line by the shortfall, square to it.
				const double Left = Closest();
				const int32 Hand = Ref.GetParentIndex(Bones[0]);
				if (Left < kFingerClearCm && Hand != INDEX_NONE)
				{
					FVector Off = Near - At;
					Off -= FVector::DotProduct(Off, Line) * Line;
					if (Off.Normalize())
					{
						ReachArm(Ref, CS, D, Hand, CS[Hand].GetLocation() + Off * (kFingerClearCm - Left + 0.02), Carried);
						Solve(Ref, RestCS, Carried, CS, &D);
						bMoved = true;
					}
				}
			}
		}
		return bMoved;
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
			// (Four passes holding a line: the swung elbow turns the forearm, and the hand with it, so the palm's offset to the target
			// is taken again after each reach.)
			// The wrist holding a line bends 40 deg at most when the line is led along the reach (within 20 deg of the shoulder to the
			// hand, as a sheet comes from its winch to the trimmer: the PC, Ultra, saw that wrist cocked 60-70 deg); a line
			// across the arm keeps the 60 (the elbow swings first in either case).
			const int32 UpperArm = Forearm == INDEX_NONE ? INDEX_NONE : Ref.GetParentIndex(Forearm);
			const bool bAlongReach = bAlong && UpperArm != INDEX_NONE
				&& FMath::Abs(FVector::DotProduct((Target - CS[UpperArm].GetLocation()).GetSafeNormal(), Hands.Along[Side].GetSafeNormal())) > FMath::Cos(FMath::DegreesToRadians(20.0));
			const double WristDeg = bAlongReach ? kHeldWristDeg : 60.0;
			for (int32 Pass = 0; Pass < (bAlong ? 4 : 2); ++Pass)
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
				}
				if (IndexK != INDEX_NONE && PinkyK != INDEX_NONE && Forearm != INDEX_NONE)
				{
					ClampWrist(RestCS, D, Hand, Forearm, IndexK, PinkyK, Ref.GetBoneName(Hand), Carried, WristDeg);
				}
				Solve(Ref, RestCS, Carried, CS, &D);
				const FVector Palm = Knuckle == INDEX_NONE ? FVector::ZeroVector : (CS[Knuckle].GetLocation() - CS[Hand].GetLocation()) * 0.75;
				ReachArm(Ref, CS, D, Hand, Target - Palm, Carried, bAlong ? Hands.Along[Side] : FVector::ZeroVector);
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

bool CrewReachCheck(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, TMap<FName, FQuat>& Joints, int32 End,
	const FVector& Target, double& OutFlexDeg, double& OutOffHingeDeg, double& OutMissCm)
{
	const int32 Lower = End == INDEX_NONE ? INDEX_NONE : Ref.GetParentIndex(End);
	const int32 Upper = Lower == INDEX_NONE ? INDEX_NONE : Ref.GetParentIndex(Lower);
	if (Upper == INDEX_NONE) return false;
	TArray<FTransform> CS;
	TArray<FQuat> D;
	CrewSolver::Solve(Ref, RestCS, Joints, CS, &D);
	FVector HingeRest;
	double MaxFlex = 0.0;
	if (!CrewSolver::LimbHinge(Ref, CS, D, Lower, HingeRest, MaxFlex)) return false;
	CrewSolver::ReachArm(Ref, CS, D, End, Target, Joints);
	CrewSolver::Solve(Ref, RestCS, Joints, CS, &D);
	const FVector Hinge = D[Upper].RotateVector(HingeRest);
	const FVector U = CS[Lower].GetLocation() - CS[Upper].GetLocation(), F = CS[End].GetLocation() - CS[Lower].GetLocation();
	OutFlexDeg = FMath::RadiansToDegrees(FMath::Atan2(FVector::DotProduct(Hinge, FVector::CrossProduct(U, F)), FVector::DotProduct(U, F)));
	OutOffHingeDeg = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(FMath::Abs(FVector::DotProduct(Hinge, F.GetSafeNormal())), 0.0, 1.0)));
	OutMissCm = FVector::Dist(CS[End].GetLocation(), Target);
	return true;
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
	// Round 12: a closed thumb stood straight up off the line. Close the fist on this skeleton, then turn each thumb joint
	// in turn, base first (55, 30, 30 deg at most), so the thumb's tip comes down onto the outside of the index finger's
	// middle bone, where a thumb lies round a stick. A swing about the palm's normal had moved the tip only millimetres on
	// the MetaHumans (their thumb lies close to that normal), and turning the base alone left it standing above the fist.
	FCrewHands Fist;
	Fist.Grip[0] = Fist.Grip[1] = 1.f;
	const double CapDeg[3] = { 55.0, 30.0, 30.0 };
	for (int32 K = 0; K < 3; ++K)
	{
		TMap<FName, FQuat> Curled;
		CrewSolver::CurlFingers(Rig, Fist, Curled);
		TArray<FTransform> Fisted;
		TArray<FQuat> FistD;
		CrewSolver::Solve(Ref, Rig.RestCS, Curled, Fisted, &FistD);
		for (int32 Side = 0; Side < 2; ++Side)
		{
			const TCHAR* Sx = Side == 0 ? TEXT("l") : TEXT("r");
			auto BoneAt = [&](const TCHAR* Name) { return Ref.FindBoneIndex(*FString::Printf(TEXT("%s_%s"), Name, Sx)); };
			const int32 T2 = BoneAt(TEXT("thumb_02")), T3 = BoneAt(TEXT("thumb_03")), I2 = BoneAt(TEXT("index_02")), I3 = BoneAt(TEXT("index_03"));
			const int32 Joint = BoneAt(K == 0 ? TEXT("thumb_01") : K == 1 ? TEXT("thumb_02") : TEXT("thumb_03"));
			if (T2 == INDEX_NONE || T3 == INDEX_NONE || I2 == INDEX_NONE || I3 == INDEX_NONE || Joint == INDEX_NONE) continue;
			const int32 Parent = Ref.GetParentIndex(Joint);
			if (Parent == INDEX_NONE) continue;
			// The tip is past thumb_03 (its last joint) by about the length of the bone before it.
			const FVector Tip = Fisted[T3].GetLocation() + (Fisted[T3].GetLocation() - Fisted[T2].GetLocation()) * 0.8;
			const FVector Phalanx = (Fisted[I2].GetLocation() + Fisted[I3].GetLocation()) * 0.5;
			const FVector Target = Phalanx + (Tip - Phalanx).GetSafeNormal() * 1.0; // on the finger's skin, not in it
			const FVector Pivot = Fisted[Joint].GetLocation();
			const FVector ToTip = Tip - Pivot, ToTarget = Target - Pivot;
			const FVector TurnAxis = FVector::CrossProduct(ToTip, ToTarget).GetSafeNormal();
			if (TurnAxis.IsNearlyZero()) continue;
			const double TurnRad = FMath::Min(FMath::Acos(FMath::Clamp(FVector::DotProduct(ToTip.GetSafeNormal(), ToTarget.GetSafeNormal()), -1.0, 1.0)),
				FMath::DegreesToRadians(CapDeg[K]));
			// A component-space turn B of the joint is D[parent]^-1 * B * D[parent] before its own turn.
			const FQuat& ParentD = FistD[Parent];
			Rig.ThumbTurn[Side][K] = ParentD.Inverse() * FQuat(TurnAxis, TurnRad) * ParentD * Rig.ThumbTurn[Side][K];
		}
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

bool CrewCockpitWell(const Sailing::FBoatConfig& C, FCrewCockpitWell& W, bool bTravelerBridge)
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
		if (!bTravelerBridge)
		{
			// The hero (build_j22_hero.py COCKPIT_AFT, CABIN_AFT, SIDE_DECK, SEAT_Z, SEAT_IN; the sole from J22H_sockets.json
			// CockpitSole): a deeper well, seats inboard to 0.40 m. Its traveler (pc/j22-feedback, Bean's Harken layout) is a
			// 32 mm track from seat to seat at the boom's end, x -2.06, its top 0.404 m up (Traveler_S/P 0.80 m out).
			W.X0 = -2.92; W.X1 = -0.55; W.SideDeck = 0.25; W.SeatZ = 0.40; W.SeatIn = 0.40; W.SoleZ = 0.136;
			W.TrackX = -2.06; W.TrackHalfX = 0.016; W.TrackZ0 = 0.388; W.TrackZ1 = 0.404; W.TrackHalfY = 0.84;
			return true;
		}
		// build_j22.py: COCKPIT_AFT, CABIN_AFT, SIDE_DECK, SEAT_Z, SEAT_W, SOLE_Z.
		W.X0 = H.SternX + 0.14; W.X1 = -0.72; W.SideDeck = 0.36; W.SeatZ = 0.47; W.SeatW = 0.36; W.SoleZ = 0.30;
		// Its traveler (pc/j22-feedback: at the boom's end, x -2.06, as on the hero): a 32 mm track from seat to seat, its top
		// 0.474 m up, open below (round 12's 16 cm bridge at x -1.75, which the helm's forward foot stood on, is gone).
		W.TrackX = -2.06; W.TrackHalfX = 0.016; W.TrackZ0 = 0.458; W.TrackZ1 = 0.474; W.TrackHalfY = 1.0;
		return true;
	case EBoatType::Sunfish:
		Fleet(-1.18, -0.52, 0.29, 0.20);
		// The model's sole (pc/sunfish-strap's numbers: 0.047 m up from the waterline), not the sheer less the well's depth:
		// that put it 2.7 cm low, the feet below the floor the model draws.
		W.SoleZ = 0.047;
		// pc/sunfish-strap (build_fleet.py): the strap's ends at the well's aft and forward walls, x -1.176 and -0.524; its
		// top 0.167 m up from the waterline at the ends and 0.147 midway, the sole at 0.047 (so 0.120 and 0.100 over the
		// sole), 3 mm of webbing, 25 mm either side of the centreline.
		W.StrapX0 = -1.176; W.StrapX1 = -0.524; W.StrapThick = 0.003; W.StrapHalfY = 0.025;
		W.StrapEndZ = 0.120 - W.StrapThick; W.StrapMidZ = 0.100 - W.StrapThick;
		return true;
	case EBoatType::ILCA7:
		Fleet(-1.62, -0.22, 0.31, 0.22);
		// pc/ilca-fidelity (build_fleet.py): the sole 0.12 m up from the waterline; the strap's ends at x -1.616 and -0.224, its
		// top 0.24 m up at the ends and 0.22 midway (x -0.92), so 0.12 and 0.10 over the sole as on the Sunfish; 25 mm either
		// side of the centreline (3 mm of webbing, as the Sunfish's).
		W.SoleZ = 0.12;
		W.StrapX0 = -1.616; W.StrapX1 = -0.224; W.StrapThick = 0.003; W.StrapHalfY = 0.025;
		W.StrapEndZ = 0.120 - W.StrapThick; W.StrapMidZ = 0.100 - W.StrapThick;
		return true;
	case EBoatType::Catalina22: return Fleet(-3.05, -0.78, 0.63, 0.42);
	case EBoatType::Catalina30: return Fleet(-4.05, -1.32, 0.82, 0.5);
	case EBoatType::Corsair880: return Fleet(-3.75, -0.95, 0.62, 0.45);
	case EBoatType::Maxi:
		// docs/crew-hull-clip/: her cockpit (Tools/boats/maxi ref.json): x -14.6 to -4.6, 4.7 m wide, 0.55 m deep, no
		// seats (the crew sit on the deck beside it or stand in it).
		W.X0 = -14.6; W.X1 = -4.6; W.HalfWidth = 2.35; W.SoleZ = H.SheerHeight(-9.6) - 0.55;
		return true;
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
		const double SeatEdge = W.SeatIn > 0.0 ? FMath::Min(W.SeatIn, Half) : Half - W.SeatW;
		Floor = W.SeatZ > 0.0 && Y > SeatEdge ? W.SeatZ : W.SoleZ;
		return true;
	}
}

namespace CrewPoseDetail
{
	// build_fleet.py SPECS "crown": the deck's camber over the sheer at a hull's centreline.
	double DeckCrown(Sailing::EBoatType Type)
	{
		switch (Type)
		{
		case Sailing::EBoatType::Hobie16: return 0.12;
		case Sailing::EBoatType::Corsair880: return 0.05;
		case Sailing::EBoatType::Lagoon42: return 0.04;
		// docs/crew-hull-clip/: the maxi's deck (Tools/boats/maxi ref.json "deck_camber"); her rail crew's feet were
		// put on the sheer, 6 cm into it.
		case Sailing::EBoatType::Maxi: return 0.12;
		default: return 0.0;
		}
	}
}

namespace
{
	/** The Lagoon 42's helm station (build_fleet.py lagoon_detail(), raised in pc/lagoon-helm): the helm's y, and the heights
	 *  over the bridgedeck of the seat's cushion (0.86, 0.45 by 0.6 m at x -3.25), the helm deck under the helm's feet (0.40,
	 *  x -3.60 to -2.42, y within 0.40 of the helm's) and the step up to it (0.20, x -3.90 to -3.60). The station stands
	 *  outboard of the starboard hull's inner deck edge (the helm's y is 2.16 m, the edge 1.97), so its heights are taken
	 *  from the bridgedeck's level (CrewBetweenHullsZ), not from the surface under it. */
	double LagoonHelmY(const Sailing::FBoatConfig& C)
	{
		const Sailing::FHullShape& Stbd = C.Hulls[1];
		return FMath::Abs(Stbd.CenterY) - Stbd.DeckHalfBeam(0.0) + 0.55 - 0.35;
	}
	bool IsLagoon(const Sailing::FBoatConfig& C) { return C.Type == Sailing::EBoatType::Lagoon42 && C.Hulls.size() >= 2; }
	double LagoonBridgedeckZ(const Sailing::FBoatConfig& C) { return C.Hulls[0].SheerHeight(0.0) + 0.02; }
	/** The helm deck's or the step's height over the bridgedeck at (X, Y), or -1 off them. */
	double LagoonHelmDeckZ(const Sailing::FBoatConfig& C, double X, double Y)
	{
		if (!IsLagoon(C) || FMath::Abs(Y - LagoonHelmY(C)) >= 0.40) return -1.0;
		if (X > -3.60 && X < -2.42) return 0.40;
		if (X > -3.90 && X <= -3.60) return 0.20;
		return -1.0;
	}
}

double CrewFloorZ(const Sailing::FBoatConfig& C, double X, double Y, bool bTravelerBridge)
{
	// (The Lagoon's raised helm deck and its step: the helm's feet rest on them, not on the deck under them.)
	const double HelmDeck = LagoonHelmDeckZ(C, X, Y);
	if (HelmDeck >= 0.0) return LagoonBridgedeckZ(C) + HelmDeck;
	FCrewCockpitWell W;
	const bool bWell = CrewCockpitWell(C, W, bTravelerBridge);
	for (int32 K = 0; K < int32(C.Hulls.size()); ++K)
	{
		const Sailing::FHullShape& H = C.Hulls[K];
		const double Yh = FMath::Abs(Y - H.CenterY);
		if (X < H.SternX || X > H.BowX || Yh >= H.DeckHalfBeam(X)) continue;
		double Floor = 0.0;
		if (K == 0 && bWell && InWell(C, W, X, Yh, Floor)) return Floor;
		// docs/crew-hull-clip/: on a cabin trunk, its top (feet planted on the deck under it went through it).
		FCrewCabinTrunk Trunk;
		if (K == 0 && CrewCabinTrunk(C, Trunk, bTravelerBridge) && X > Trunk.X0 && X < Trunk.X1
			&& Yh < (Trunk.SideDeck > 0.0 ? H.DeckHalfBeam(X) - Trunk.SideDeck : Trunk.HalfWidth))
		{
			return H.SheerHeight(X) + Trunk.Height;
		}
		// (The deck's crown too: the Hobie's and the maxi's feet were planted on the sheer, inside it.)
		return H.SheerHeight(X) + CrewPoseDetail::DeckCrown(C.Type) * FMath::Max(0.0, 1.0 - FMath::Square(Yh / FMath::Max(H.DeckHalfBeam(X), 1e-3)));
	}
	return CrewBetweenHullsZ(C, X, Y);
}


bool CrewNetSpan(const Sailing::FBoatConfig& C, double& AftX, double& ForwardX)
{
	switch (C.Type)
	{
	case Sailing::EBoatType::Hobie16: AftX = -1.75; ForwardX = 0.55; return true;    // "beams"
	case Sailing::EBoatType::Corsair880: AftX = -1.75; ForwardX = 1.55; return true; // "akas"
	case Sailing::EBoatType::Lagoon42: AftX = -4.6; ForwardX = 4.3; return true;     // "bridgedeck"
	default: return false;
	}
}

double CrewBetweenHullsZ(const Sailing::FBoatConfig& C, double X, double Y)
{
	double AftX = 0.0, ForwardX = 0.0;
	if (!C.bMultihull || !CrewNetSpan(C, AftX, ForwardX) || X < AftX || X > ForwardX) return -1e9;
	const Sailing::FHullShape& Outer = C.Hulls.back();
	const double OuterInner = FMath::Abs(Outer.CenterY) - Outer.DeckHalfBeam(X);
	if (FMath::Abs(Y) > OuterInner) return -1e9;
	if (C.Hulls.size() == 3)
	{
		// The Corsair's nets: from the main hull's deck edge out to the ama's centreline deck, bellied 0.12 m up mid-span.
		const Sailing::FHullShape& Main = C.Hulls[0];
		const double Y0 = Main.DeckHalfBeam(X) - 0.05, Y1 = FMath::Abs(Outer.CenterY) - (Outer.DeckHalfBeam(X) - 0.1);
		if (FMath::Abs(Y) < Y0) return -1e9;
		const double T = FMath::Clamp((FMath::Abs(Y) - Y0) / FMath::Max(Y1 - Y0, 0.1), 0.0, 1.0);
		const double Z0 = Main.SheerHeight(X), Z1 = Outer.SheerHeight(X) + CrewPoseDetail::DeckCrown(C.Type);
		return Z0 - 0.02 + 0.12 * FMath::Sin(UE_DOUBLE_PI * T) + (Z1 - Z0) * T;
	}
	// Two hulls: the Hobie's trampoline 0.10 m over the sheer at the forward beam, the Lagoon's bridgedeck 0.02 m over
	// the sheer amidships.
	const Sailing::FHullShape& H = C.Hulls[0];
	return C.Type == Sailing::EBoatType::Hobie16 ? H.SheerHeight(ForwardX) + 0.10 : H.SheerHeight(0.0) + 0.02;
}

double CrewSeatSurfaceZ(const Sailing::FBoatConfig& C, double X, double Y)
{
	// docs/crew-hull-clip/: the Lagoon's helm seat (build_fleet.py lagoon_detail(): its cushion 0.45 by 0.6 m, aft of
	// the saloon on the starboard side; raised in pc/lagoon-helm from 0.49 to 0.86 m over the bridgedeck so the helm
	// sees over the saloon roof).
	if (IsLagoon(C) && FMath::Abs(X + 3.25) < 0.225 && FMath::Abs(Y - LagoonHelmY(C)) < 0.3) return LagoonBridgedeckZ(C) + 0.86;
	FCrewCockpitWell W;
	const bool bWell = CrewCockpitWell(C, W);
	const double Crown = CrewPoseDetail::DeckCrown(C.Type);
	for (int32 K = 0; K < int32(C.Hulls.size()); ++K)
	{
		const Sailing::FHullShape& H = C.Hulls[K];
		const double Half = H.DeckHalfBeam(X), Yh = FMath::Abs(Y - H.CenterY);
		if (X < H.SternX || X > H.BowX || Yh >= Half) continue;
		double Floor = 0.0;
		if (K == 0 && bWell && InWell(C, W, X, Yh, Floor)) return H.SheerHeight(X);
		return H.SheerHeight(X) + Crown * FMath::Max(0.0, 1.0 - FMath::Square(Yh / FMath::Max(Half, 1e-3)));
	}
	const double Between = CrewBetweenHullsZ(C, X, Y);
	if (Between > -1e8) return Between;
	// Out over the water (on the wire) or past the nets: the deck of the hull nearest the sailor's side.
	const Sailing::FHullShape* Near = &C.Hulls[0];
	for (const Sailing::FHullShape& H : C.Hulls)
	{
		if (FMath::Abs(Y - H.CenterY) < FMath::Abs(Y - Near->CenterY)) Near = &H;
	}
	return Near->SheerHeight(FMath::Clamp(X, Near->SternX, Near->BowX)) + Crown;
}

bool CrewHasLifelines(const Sailing::FBoatConfig& C)
{
	return C.Type == Sailing::EBoatType::Catalina22 || C.Type == Sailing::EBoatType::Catalina30 || C.Type == Sailing::EBoatType::Corsair880;
}

bool CrewCabinTrunk(const Sailing::FBoatConfig& C, FCrewCabinTrunk& Out, bool bTravelerBridge)
{
	using Sailing::EBoatType;
	Out = FCrewCabinTrunk();
	// The trunks the drawn models carry (build_fleet.py SPECS "cabin": aft x, forward x, half width, height over the
	// sheer; build_j22.py CABIN_AFT, CABIN_FWD, SIDE_DECK, cabin_height; the hero's build_j22_hero.py).
	switch (C.Type)
	{
	case EBoatType::J22:
		if (bTravelerBridge) { Out.X0 = -0.72; Out.X1 = 1.60; Out.SideDeck = 0.36; Out.Height = 0.31; }
		else { Out.X0 = -0.55; Out.X1 = 1.65; Out.SideDeck = 0.25; Out.Height = 0.30; }
		return true;
	case EBoatType::Catalina22: Out.X0 = -0.78; Out.X1 = 1.70; Out.HalfWidth = 0.62; Out.Height = 0.42; return true;
	case EBoatType::Catalina30: Out.X0 = -1.32; Out.X1 = 2.85; Out.HalfWidth = 0.92; Out.Height = 0.60; return true;
	case EBoatType::Corsair880: Out.X0 = -0.95; Out.X1 = 2.20; Out.HalfWidth = 0.62; Out.Height = 0.48; return true;
	case EBoatType::Maxi: Out.X0 = -4.6; Out.X1 = 3.6; Out.HalfWidth = 2.05; Out.Height = 0.52; return true;   // ref.json "coachroof"
	default: return false;
	}
}

bool CrewInsideBoat(const Sailing::FBoatConfig& C, double HullDepth, const FVector& P, bool bTravelerBridge)
{
	// The Lagoon's raised helm deck and its step are solid (pc/lagoon-helm).
	const double HelmDeck = LagoonHelmDeckZ(C, P.X, P.Y);
	if (HelmDeck >= 0.0 && P.Z >= LagoonBridgedeckZ(C) - 0.3 && P.Z < LagoonBridgedeckZ(C) + HelmDeck) return true;
	FCrewCockpitWell W;
	const bool bWell = CrewCockpitWell(C, W, bTravelerBridge);
	FCrewCabinTrunk Trunk;
	const bool bTrunk = CrewCabinTrunk(C, Trunk, bTravelerBridge);
	const double Crown = CrewPoseDetail::DeckCrown(C.Type);
	for (int32 K = 0; K < int32(C.Hulls.size()); ++K)
	{
		const Sailing::FHullShape& H = C.Hulls[K];
		const double Y = FMath::Abs(P.Y - H.CenterY);
		const double Half = H.DeckHalfBeam(P.X);
		if (P.X < H.SternX || P.X > H.BowX || Y >= Half) continue;
		// docs/crew-hull-clip/: the cabin trunk on the main hull, and the deck's crown (the maxi's 12 cm).
		const double Sheer = H.SheerHeight(P.X);
		if (K == 0 && bTrunk && P.X > Trunk.X0 && P.X < Trunk.X1 && Y < (Trunk.SideDeck > 0.0 ? Half - Trunk.SideDeck : Trunk.HalfWidth)
			&& P.Z < Sheer + Trunk.Height && P.Z > Sheer - 0.05)
		{
			return true;
		}
		if (P.Z >= Sheer + Crown * FMath::Max(0.0, 1.0 - FMath::Square(Y / FMath::Max(Half, 1e-3)))) continue;
		if (P.Z <= H.BottomZ(P.X, Y, HullDepth)) continue;
		double Floor = 0.0;
		if (K == 0 && bWell && InWell(C, W, P.X, Y, Floor) && P.Z >= Floor)
		{
			// (The traveler track across the well.)
			if (W.TrackHalfX > 0.0 && FMath::Abs(P.X - W.TrackX) < W.TrackHalfX && Y < W.TrackHalfY && P.Z >= W.TrackZ0 && P.Z <= W.TrackZ1) return true;
			// (The Sunfish's hiking strap along the well.)
			if (W.StrapHalfY > 0.0 && P.X > W.StrapX0 && P.X < W.StrapX1 && Y < W.StrapHalfY)
			{
				const double Under = W.StrapUnderZ(P.X);
				if (P.Z >= Under && P.Z <= Under + W.StrapThick) return true;
			}
			continue;
		}
		return true;
	}
	// Between a multihull's hulls: through the trampoline or the nets (8 cm), into the Lagoon's bridgedeck (30 cm), her
	// saloon and her cockpit table (build_fleet.py: the saloon from x -2.4 to 2.8, 0.55 m inside the hulls' inner sides,
	// 1.42 m high; the table 1.5 m by 1.1 m at x -3.3, its top 0.71 m up).
	const double Surface = CrewBetweenHullsZ(C, P.X, P.Y);
	if (Surface > -1e8 && P.Z < Surface && P.Z > Surface - (C.Type == Sailing::EBoatType::Lagoon42 ? 0.3 : 0.08)) return true;
	if (C.Type == Sailing::EBoatType::Lagoon42 && Surface > -1e8)
	{
		const Sailing::FHullShape& Inner = C.Hulls[1];
		const double SaloonHalf = FMath::Abs(Inner.CenterY) - Inner.DeckHalfBeam(0.0) + 0.55;
		if (P.X > -2.4 && P.X < 2.8 && FMath::Abs(P.Y) < SaloonHalf && P.Z < Surface + 1.42) return true;
		if (FMath::Abs(P.X + 3.3) < 0.375 && FMath::Abs(P.Y) < 0.55 && P.Z > Surface + 0.67 && P.Z < Surface + 0.73) return true;
	}
	return false;
}
