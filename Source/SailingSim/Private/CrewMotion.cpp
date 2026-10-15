#include "CrewMotion.h"
#include "CrewSolver.h"
#include "BoatModel.h"
#include "ReferenceSkeleton.h"

namespace CrewMotionDetail
{
	constexpr double ToCm = 100.0;

	/** A small turn about an axis of the sailor's frame, degrees (CrewPose's conventions: Right leans forward, Forward sideways). */
	FQuat Turn(const FVector& Axis, float Deg) { return FQuat(Axis, FMath::DegreesToRadians(Deg)); }

	/** Turns the sailor's "up" (Z) toward Up, a fraction of the way. */
	FQuat TiltToward(const FVector& Up, float Fraction)
	{
		return FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals(FVector::UpVector, Up.GetSafeNormal()), Fraction);
	}

	void PreMultiply(TMap<FName, FQuat>& Joints, FName Joint, const FQuat& R)
	{
		FQuat& J = Joints.FindOrAdd(Joint, FQuat::Identity);
		J = R * J;
	}

	/** Small hash to [0, 1). */
	float Hash01(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return float(X & 0xffffff) / float(0x1000000);
	}

	/** The base of support for a stance (m): half its width across the sailor and fore and aft, and the centre of mass
	 *  over it. Seated: buttocks and feet; crouched crossing: the feet alone. Zero: no bracing (the wire, righting). */
	void Support(ECrewStance S, double& HalfAcross, double& HalfFore, double& Height)
	{
		switch (S)
		{
		case ECrewStance::Crossing: HalfAcross = 0.16; HalfFore = 0.14; Height = 0.55; break;
		case ECrewStance::Trapeze: case ECrewStance::Righting: HalfAcross = HalfFore = 0.0; Height = 1.0; break;
		default: HalfAcross = 0.20; HalfFore = 0.30; Height = 0.35; break;
		}
	}

	/** The component-space turn that brings a bone's facing and up (rest facing and up carried by D) to the wanted ones. */
	FQuat Aim(const FQuat& D, const FQuat& Frame, const FVector& WantFwd, const FVector& WantUp)
	{
		const FVector F = D.RotateVector(Frame.RotateVector(FVector::ForwardVector));
		const FVector U = D.RotateVector(Frame.RotateVector(FVector::UpVector));
		const FQuat Now = FRotationMatrix::MakeFromXZ(F, U).ToQuat();
		const FQuat Want = FRotationMatrix::MakeFromXZ(WantFwd, WantUp).ToQuat();
		return Want * Now.Inverse();
	}

	/** Limits a rotation's angle (rad). */
	FQuat Limit(const FQuat& Q, double MaxAngle)
	{
		FVector Axis;
		double Angle;
		Q.ToAxisAndAngle(Axis, Angle);
		if (Angle > PI) Angle -= 2.0 * PI;
		if (FMath::Abs(Angle) <= MaxAngle) return Q;
		return FQuat(Axis, FMath::Sign(Angle) * MaxAngle);
	}

	/** Rotates a bone (and so everything below it) by C in component space, given the solved turns D. */
	void RotateBone(const FReferenceSkeleton& Ref, const TArray<FQuat>& D, int32 Bone, const FQuat& C, TMap<FName, FQuat>& Joints)
	{
		const int32 Parent = Ref.GetParentIndex(Bone);
		const FQuat DP = Parent == INDEX_NONE ? FQuat::Identity : D[Parent];
		Joints.Add(Ref.GetBoneName(Bone), DP.Inverse() * C * D[Bone]);
	}
}

void CrewSpring(float& X, float& V, float Target, float Omega, float Dt)
{
	// x'' = -w^2 (x - target) - 2 w x', solved exactly over the step: e(t) = (e0 + (v0 + w e0) t) exp(-w t).
	const float E = X - Target;
	const float K = V + Omega * E;
	const float Ex = FMath::Exp(-Omega * Dt);
	X = Target + (E + K * Dt) * Ex;
	V = (V - Omega * K * Dt) * Ex;
}

FVector CrewFeltGravity(const FCrewBoatMotion& M, const FVector& R)
{
	const FVector A = M.Accel + FVector::CrossProduct(M.Alpha, R) + FVector::CrossProduct(M.Omega, FVector::CrossProduct(M.Omega, R));
	return M.Gravity - A;
}

void FCrewBalance::Decompose(const FVector& G, float& OutRoll, float& OutPitch, float& OutLoad)
{
	// The way they would fall: felt gravity with a component to their right rolls them right, forward pitches them forward.
	const double Down = FMath::Max(-G.Z, 0.5);
	OutRoll = float(FMath::Atan2(G.Y, Down));
	OutPitch = float(FMath::Atan2(G.X, Down));
	OutLoad = float(G.Size() / 9.81 - 1.0);
}

void FCrewBalance::Reset(const FVector& FeltLocal)
{
	History.Reset();
	Clock = 0.0;
	History.Add({ 0.0, FeltLocal });
	float L;
	Decompose(FeltLocal, Roll, Pitch, L);
	Squat = 0.f;
	RollV = PitchV = SquatV = 0.f;
	bStarted = true;
}

FVector FCrewBalance::Delayed() const
{
	if (History.IsEmpty()) return FVector(0.0, 0.0, -9.81);
	const double T = Clock - Lag;
	if (T <= History[0].T) return History[0].V;
	for (int32 K = History.Num() - 1; K > 0; --K)
	{
		if (History[K - 1].T <= T)
		{
			const double Span = History[K].T - History[K - 1].T;
			const double A = Span > 1e-6 ? (T - History[K - 1].T) / Span : 1.0;
			return FMath::Lerp(History[K - 1].V, History[K].V, FMath::Clamp(A, 0.0, 1.0));
		}
	}
	return History[0].V;
}

void FCrewBalance::Step(float Dt, const FVector& FeltLocal)
{
	if (!bStarted) Reset(FeltLocal);
	if (Dt <= 0.f) return;
	Clock += Dt;
	History.Add({ Clock, FeltLocal });
	// Keep a sample older than the lag to interpolate from.
	int32 Drop = 0;
	while (Drop + 1 < History.Num() && History[Drop + 1].T < Clock - Lag - 0.05) ++Drop;
	if (Drop > 0) History.RemoveAt(0, Drop, EAllowShrinking::No);
	float R, P, Load;
	Decompose(Delayed(), R, P, Load);
	// Sub-step long frames (an AI boat's crew update at 15 Hz) so the target's slope is followed.
	const int32 Steps = FMath::Clamp(FMath::CeilToInt(Dt / 0.02f), 1, 8);
	const float H = Dt / Steps;
	for (int32 K = 0; K < Steps; ++K)
	{
		CrewSpring(Roll, RollV, R, Omega, H);
		CrewSpring(Pitch, PitchV, P, Omega, H);
		CrewSpring(Squat, SquatV, FMath::Clamp(Load, -0.6f, 1.5f), SquatOmega, H);
	}
}

float CrewTransitionSeconds(ECrewStance From, ECrewStance To)
{
	if (From == To) return 0.f;
	// Crossing a tack: up and moving in about half a second; settling onto the new rail a little slower.
	if (To == ECrewStance::Crossing) return 0.45f;
	if (From == ECrewStance::Crossing) return 0.6f;
	return 0.8f;
}

void CrewPlacement(const FCrewPlaceInput& In, FCrewPlacement& Out)
{
	using namespace Sailing;
	const FBoatConfig& Cfg = *In.Config;
	const FHullShape& Hull = Cfg.Hulls[0];
	const int32 N = Cfg.CrewCount, I = In.Index;
	const bool bDinghy = Cfg.Type == EBoatType::Sunfish || Cfg.Type == EBoatType::ILCA7 || Cfg.Type == EBoatType::Hobie16;
	const float Side = In.CrewOffset != 0.0 ? float(FMath::Sign(In.CrewOffset)) : float(In.WindwardSide);
	const double Off = FMath::Abs(In.CrewOffset);
	const double X = Cfg.CrewCG.X + 0.55 * (0.5 * (N - 1) - I);
	const double Rail = Cfg.bMultihull ? FMath::Abs(Cfg.Hulls.back().CenterY) + 0.2 : Hull.DeckHalfBeam(X);
	const double Sheer = Cfg.bMultihull ? Hull.SheerZ + 0.1 : Hull.SheerHeight(X);
	FCrewPoseParams& P = Out.Params;
	Out.bHelm = I == N - 1;
	Out.Roll = 0.f;
	Out.Duck = 0.f;
	P.Side = Side;
	P.Hike = float(FMath::Clamp((Off - Cfg.CrewSitOut * 0.8) / FMath::Max(Cfg.CrewHikeOut, 0.1), 0.0, 1.0));
	// Crew C1: a tack or gybe is timed to the boom. Turning through the eye of the wind (or the boom swinging across dead
	// downwind) the crew go over as it comes across the cockpit, crouched under it the closer it is to the centreline,
	// facing forward; or whenever the crew model is moving them across.
	const double BoomAft = Cfg.MainLuffX - Cfg.MainFootChord - 0.1;
	const bool bUnderBoom = X > BoomAft && X < Cfg.MainLuffX && !Cfg.bMultihull;
	const double BoomDeg = FMath::RadiansToDegrees(FMath::Abs(In.BoomAngle));
	const double Twa = FMath::RadiansToDegrees(FMath::Abs(In.TrueWindAngle));
	const bool bTacking = Twa < 28.0 && FMath::Abs(In.TurnRate) > FMath::DegreesToRadians(4.0);
	const bool bGybing = Twa > 150.0 && FMath::Abs(In.BoomRate) > 0.3 && BoomDeg < 45.0;
	// (Hiking in or out moves the crew model as fast as a tack does: only a move through the middle of the boat is a crossing.)
	const bool bCrossing = (bUnderBoom && (bTacking || bGybing)) || ((bTacking || bGybing) && FMath::Abs(In.OffsetRate) > 0.3)
		|| (FMath::Abs(In.OffsetRate) > 0.6 && Off < 0.8 * Cfg.CrewSitOut);
	if (In.bRighting)
	{
		P.Stance = ECrewStance::Righting;
		Out.Pelvis = FVector(X, In.CrewOffset, Sheer + 0.45 + In.CrewOffsetZ);
	}
	else if (Cfg.bTrapeze && !Out.bHelm && Off > Rail)
	{
		// On the wire: feet on the rail, body out over the water.
		P.Stance = ECrewStance::Trapeze;
		Out.Pelvis = FVector(X, Side * (Rail + 0.8), Sheer + 0.35);
		Out.Roll = 72.f * Side;
	}
	else if (bCrossing)
	{
		P.Stance = ECrewStance::Crossing;
		// Heading for the new side: the crew model's motion, or (the boom ahead of it) away from where the boom is going.
		const double Toward = FMath::Abs(In.OffsetRate) > 0.3 ? In.OffsetRate : (FMath::Abs(In.BoomRate) > 0.05 ? -In.BoomRate : -In.BoomAngle);
		P.Side = -float(FMath::Sign(Toward));
		Out.Duck = bUnderBoom ? float(FMath::Clamp(1.25 - BoomDeg / 28.0, 0.0, 1.0)) : 0.f;
		// Down to a crouch under the boom (the head about 0.75 m above the pelvis crouched, 10 cm clear).
		// Into the middle as the boom comes over them (the crew model then takes them to the new side), never lower than a
		// deep crouch over the floor under them.
		const double Y = In.CrewOffset * (1.0 - Out.Duck);
		const double Up = Sheer + (bDinghy ? 0.25 : 0.05);
		const double FloorZ = CrewFloorZ(Cfg, X, Y);
		const double Lowest = FloorZ > -1e8 ? FloorZ + 0.22 : Sheer - 0.3;
		const double Under = FMath::Max(Cfg.BoomZ - 0.85, Lowest);
		Out.Pelvis = FVector(X, Y, FMath::Lerp(Up, FMath::Min(Up, Under), double(Out.Duck)));
	}
	else if (bDinghy)
	{
		P.Stance = ECrewStance::DinghyHike;
		Out.Pelvis = FVector(X, Side * (Rail - 0.04), Sheer + 0.06);
	}
	else if (Out.bHelm)
	{
		P.Stance = ECrewStance::Helm;
		Out.Pelvis = FVector(X, Side * FMath::Max(Rail - 0.18, 0.3), Sheer + 0.07);
	}
	else if (Off > 0.55 * Rail)
	{
		P.Stance = ECrewStance::RailHike;
		Out.Pelvis = FVector(X, Side * (Rail - 0.02), Sheer + 0.07);
	}
	else
	{
		// Light air or downwind: on the cockpit seat (to leeward if the crew model put them there).
		P.Stance = ECrewStance::Cockpit;
		Out.Pelvis = FVector(X, Side * FMath::Clamp(Off, 0.35, FMath::Max(Rail - 0.45, 0.35)), Sheer - 0.10);
	}
	Out.Yaw = CrewFacingYaw(P);
}

void CrewDerivedAttachPoints(const Sailing::FBoatConfig& C, double X, FCrewAttachPoints& Out)
{
	using CrewMotionDetail::ToCm;
	// The J22H_sockets.json points, where the model has no socket: from the cockpit well (CrewCockpitWell), the deck edge
	// and the cabin top (build_j22.py: the handrail on the cabin top just forward of the companionway, 30 cm over the sheer).
	Out = FCrewAttachPoints();
	FCrewCockpitWell W;
	if (!CrewCockpitWell(C, W)) return;
	const Sailing::FHullShape& H = C.Hulls[0];
	X = FMath::Clamp(X, W.X0 + 0.1, W.X1 - 0.1);
	const double Half = W.SideDeck > 0.0 ? H.DeckHalfBeam(X) - W.SideDeck : W.HalfWidth;
	const double SeatZ = W.SeatZ > 0.0 ? W.SeatZ : W.SoleZ;
	const double SeatY = W.SeatZ > 0.0 ? Half - 0.5 * W.SeatW : Half - 0.1;
	const double CabinX = W.X1 + 0.35;
	const double CabinHalf = FMath::Max(0.2, H.DeckHalfBeam(CabinX) - (W.SideDeck > 0.0 ? W.SideDeck : 0.25) - 0.16);
	for (int32 S = 0; S < 2; ++S)
	{
		const double Y = S == 0 ? 1.0 : -1.0;
		Out.Seat[S] = FVector(X, Y * SeatY, SeatZ) * ToCm;
		Out.FootBrace[S] = FVector(X, Y * (Half - (W.SeatZ > 0.0 ? W.SeatW : 0.05) - 0.03), SeatZ - 0.06) * ToCm;
		Out.SideDeck[S] = FVector(X, Y * (H.DeckHalfBeam(X) - 0.05), H.SheerHeight(X)) * ToCm;
		Out.HandholdCoaming[S] = FVector(X, Y * (Half + 0.02), H.SheerHeight(X) + 0.03) * ToCm;
		Out.HandholdCabin[S] = FVector(CabinX, Y * CabinHalf, H.SheerHeight(CabinX) + 0.30) * ToCm;
	}
	Out.CockpitSole = FVector(X, 0.0, W.SoleZ) * ToCm;
	Out.bValid = true;
}

void CrewMotionUpdate(FCrewMotionState& S, const FCrewMotionInput& In, float Dt)
{
	using namespace CrewMotionDetail;
	// The stance, blended over its transition by minimum jerk from wherever the last one had got to.
	TMap<FName, FQuat> Target;
	CrewJointRotations(In.Params, Target);
	if (!S.bStarted)
	{
		S.Current = Target;
		S.Transition = In.Transition;
		S.TransitionS = 1.f;
	}
	if (In.Transition != S.Transition)
	{
		S.From = S.Current;
		S.Transition = In.Transition;
		S.TransitionS = 0.f;
	}
	S.TransitionS = FMath::Min(1.f, S.TransitionS + Dt / FMath::Max(In.TransitionSeconds, 0.05f));
	if (S.TransitionS >= 1.f)
	{
		S.Current = Target;
	}
	else
	{
		const float W = CrewMinJerk(S.TransitionS);
		S.Current.Reset();
		for (const TPair<FName, FQuat>& J : Target)
		{
			const FQuat* F = S.From.Find(J.Key);
			S.Current.Add(J.Key, FQuat::Slerp(F ? *F : FQuat::Identity, J.Value, W));
		}
		for (const TPair<FName, FQuat>& J : S.From)
		{
			if (!Target.Contains(J.Key)) S.Current.Add(J.Key, FQuat::Slerp(J.Value, FQuat::Identity, W));
		}
	}

	// The balance against the gravity they feel at the seat, in their own frame.
	const FVector Felt = CrewFeltGravity(In.Motion, In.SeatFromCG);
	const FQuat ToSailor = FQuat(FRotator(0.f, CrewFacingYaw(In.Params), 0.f)).Inverse();
	const FVector Local = ToSailor.RotateVector(Felt);
	const uint32 Seed = In.Seed;
	S.Balance.Lag = 0.1f + 0.2f * Hash01(Seed * 7919u + 1u);
	S.Balance.Step(Dt, Local);
	S.Report.Felt = Local;

	// Brace past the tipping limit: the felt tilt's tangent beyond half the support's width over the centre of mass height.
	double HalfAcross, HalfFore, Height;
	Support(In.Params.Stance, HalfAcross, HalfFore, Height);
	const FVector Seen = S.Balance.Delayed();
	const double Down = FMath::Max(-Seen.Z, 0.5);
	const double Ratio = HalfAcross > 0.0 ? FMath::Max(FMath::Abs(Seen.Y) / Down / (HalfAcross / Height), FMath::Abs(Seen.X) / Down / (HalfFore / Height)) : 0.0;
	S.Report.TipRatio = float(Ratio);
	S.BraceHold = FMath::Max(0.f, S.BraceHold - Dt);
	if (Ratio > 1.0) { S.bBracing = true; S.BraceHold = 0.8f; }
	else if (S.bBracing && Ratio < 0.8 && S.BraceHold <= 0.f) S.bBracing = false;
	if (HalfAcross <= 0.0) S.bBracing = false;
	S.Report.bBracing = S.bBracing;

	// The gaze: their eyes go to the target, the head follows in a few tenths of a second.
	// (From about where the head is: 1.5 m over the figure's origin, which is under its pelvis at standing height.)
	const FVector Eyes = In.ToBoat.TransformPosition(FVector(0.0, 0.0, 150.0));
	FVector Want = In.Gaze.IsNearlyZero() ? FRotator(0.f, CrewFacingYaw(In.Params), 0.f).Vector() : (In.Gaze - Eyes).GetSafeNormal();
	if (Want.IsNearlyZero()) Want = FVector::ForwardVector;
	if (!S.bStarted) S.GazeDir = Want;
	for (int32 K = 0; K < 3; ++K)
	{
		float X = float(S.GazeDir[K]), V = float(S.GazeV[K]);
		CrewSpring(X, V, float(Want[K]), 6.f, Dt);
		S.GazeDir[K] = X;
		S.GazeV[K] = V;
	}
	S.GazeDir = S.GazeDir.GetSafeNormal(UE_SMALL_NUMBER, Want);
	S.bStarted = true;
}

void CrewMotionPose(const FReferenceSkeleton& Ref, const FCrewRig* Rig, const Sailing::FBoatConfig* Config, double HullDepth,
	FCrewMotionState& S, const FCrewMotionInput& In, TArray<FTransform>& CS)
{
	using namespace CrewMotionDetail;
	const bool bRig = Rig && Rig->bValid && Rig->RestCS.Num() == Ref.GetNum();
	if (!bRig && S.Rest.Num() != Ref.GetNum()) CrewSolver::RestPose(Ref, S.Rest);
	const TArray<FTransform>& RestCS = bRig ? Rig->RestCS : S.Rest;
	const FQuat Frame = bRig ? Rig->Frame : FQuat::Identity;

	// The reaction layer on the sailor's joints (their frame).
	TMap<FName, FQuat> Joints = S.Current;
	if (In.bReact)
	{
		const FCrewBalance& B = S.Balance;
		// Lean the trunk toward the felt "up" (pelvis, spine and chest share it); the head is levelled below. Not on the
		// wire or righting, where the body hangs from a line.
		const FVector Up(-FMath::Tan(B.Pitch), -FMath::Tan(B.Roll), 1.0);
		const bool bHanging = In.Params.Stance == ECrewStance::Trapeze || In.Params.Stance == ECrewStance::Righting;
		const float K = bHanging ? 0.f : 0.45f;
		PreMultiply(Joints, TEXT("pelvis"), TiltToward(Up, 0.25f * K));
		PreMultiply(Joints, TEXT("spine"), TiltToward(Up, 0.40f * K));
		PreMultiply(Joints, TEXT("chest"), TiltToward(Up, 0.35f * K));
		// Never still: breathing in the chest (about 15 a minute) and a slow sway, each sailor on their own phase.
		const float Ph = 6.2832f * Hash01(In.Seed * 31u + 3u);
		const float T = In.Time;
		PreMultiply(Joints, TEXT("chest"), Turn(FVector::RightVector, 1.1f * FMath::Sin(6.2832f * 0.25f * T + Ph)));
		PreMultiply(Joints, TEXT("spine"), Turn(FVector::ForwardVector, 0.9f * FMath::Sin(6.2832f * 0.13f * T + 2.f * Ph)
			+ 0.5f * FMath::Sin(6.2832f * 0.31f * T + 3.f * Ph)) * Turn(FVector::RightVector, 0.6f * FMath::Sin(6.2832f * 0.09f * T + Ph)));
		// A slam: the knees and spine give and come back (Squat is the extra load, in g).
		const float Give = FMath::Clamp(B.Squat, -0.3f, 1.f);
		PreMultiply(Joints, TEXT("spine"), Turn(FVector::RightVector, 7.f * Give));
		PreMultiply(Joints, TEXT("chest"), Turn(FVector::RightVector, 4.f * Give));
		const bool bOnFeet = In.Params.Stance == ECrewStance::Crossing || In.Params.Stance == ECrewStance::Trapeze || In.Params.Stance == ECrewStance::Righting;
		if (bOnFeet)
		{
			for (const TCHAR* Sx : { TEXT("l"), TEXT("r") })
			{
				PreMultiply(Joints, *FString::Printf(TEXT("thigh_%s"), Sx), Turn(FVector::RightVector, -8.f * Give));
				PreMultiply(Joints, *FString::Printf(TEXT("calf_%s"), Sx), Turn(FVector::RightVector, 16.f * Give));
			}
		}
		// Ducking under the boom: folded further forward over the knees.
		if (In.Duck > 0.f)
		{
			PreMultiply(Joints, TEXT("spine"), Turn(FVector::RightVector, 14.f * In.Duck));
			PreMultiply(Joints, TEXT("chest"), Turn(FVector::RightVector, 10.f * In.Duck));
		}
		// Load on a line in the hand: leaning back against it.
		const float Pull = FMath::Max(In.Tension[0], In.Tension[1]);
		PreMultiply(Joints, TEXT("chest"), Turn(FVector::RightVector, -4.f * Pull));
	}

	TMap<FName, FQuat> Carried;
	if (bRig) CrewSolver::Carry(*Rig, Joints, Carried);
	else Carried = Joints;
	FCrewHands Hands = In.Hands;
	for (int32 H = 0; H < 2; ++H)
	{
		if (Hands.Mode[H] == FCrewHands::EMode::Reach) Hands.Grip[H] = FMath::Clamp(0.75f + 0.25f * In.Tension[H], 0.f, 1.f);
	}
	if (bRig) CrewSolver::CurlFingers(*Rig, Hands, Carried);
	TArray<FQuat> D;
	CrewSolver::Solve(Ref, RestCS, Carried, CS, &D);

	// Bracing: the feet push the far seat, a free hand takes the nearest handhold in reach (the coaming or the cabin-top
	// handrail: the J/22 the lessons sail has no lifelines).
	const FTransform& ToBoat = In.ToBoat;
	const bool bBrace = In.bReact && S.bBracing && In.Attach.bValid;
	if (bBrace)
	{
		const int32 Far = ToBoat.GetLocation().Y >= 0.0 ? 1 : 0; // the seat across the cockpit
		for (int32 Side = 0; Side < 2; ++Side)
		{
			const int32 Foot = Ref.FindBoneIndex(Side == 0 ? TEXT("foot_l") : TEXT("foot_r"));
			const int32 Thigh = Ref.FindBoneIndex(Side == 0 ? TEXT("thigh_l") : TEXT("thigh_r"));
			if (Foot == INDEX_NONE || Thigh == INDEX_NONE) continue;
			const FVector Target = ToBoat.InverseTransformPosition(In.Attach.FootBrace[Far]);
			// Only a leg that reaches it (thigh and calf less a bent knee).
			if (FVector::Dist(CS[Thigh].GetLocation(), Target) < 0.92 * (FVector::Dist(CS[Thigh].GetLocation(), CS[Ref.GetParentIndex(Foot)].GetLocation())
				+ FVector::Dist(CS[Ref.GetParentIndex(Foot)].GetLocation(), CS[Foot].GetLocation())))
			{
				CrewSolver::ReachArm(Ref, CS, D, Foot, Target, Carried);
				CrewSolver::Solve(Ref, RestCS, Carried, CS, &D);
				break; // one foot braces; the other stays planted
			}
		}
	}
	FCrewGround Ground;
	if (Config)
	{
		Ground.Config = Config;
		Ground.HullDepth = HullDepth;
		Ground.ToBoat = ToBoat;
		CrewSolver::PlantAllFeet(Ref, RestCS, CS, D, Frame, Ground, Carried);
	}
	if (bBrace)
	{
		for (int32 H = 0; H < 2; ++H)
		{
			if (Hands.Mode[H] == FCrewHands::EMode::Reach) continue;
			const int32 Upper = Ref.FindBoneIndex(H == 0 ? TEXT("upperarm_l") : TEXT("upperarm_r"));
			if (Upper == INDEX_NONE) continue;
			const FVector Shoulder = CS[Upper].GetLocation();
			double Best = 66.0;
			for (const FVector* Set : { In.Attach.HandholdCoaming, In.Attach.HandholdCabin })
			{
				for (int32 K = 0; K < 2; ++K)
				{
					const FVector At = ToBoat.InverseTransformPosition(Set[K]);
					const double Dist = FVector::Dist(At, Shoulder);
					if (Dist < Best) { Best = Dist; Hands.Mode[H] = FCrewHands::EMode::Reach; Hands.Target[H] = At; Hands.Grip[H] = 0.95f; }
				}
			}
		}
	}
	if (CrewSolver::PlaceHands(Ref, RestCS, CS, D, Hands, Carried)) CrewSolver::Solve(Ref, RestCS, Carried, CS, &D);

	// The head: near world-level whatever the boat does, turned to the gaze (within the neck's range of the chest).
	const int32 Head = Ref.FindBoneIndex(TEXT("head"));
	const int32 Neck = Ref.FindBoneIndex(bRig ? TEXT("neck_01") : TEXT("neck"));
	const int32 Chest = Ref.FindBoneIndex(bRig ? TEXT("spine_05") : TEXT("chest"));
	if (Head != INDEX_NONE && In.bReact)
	{
		const FVector UpCS = ToBoat.InverseTransformVectorNoScale(-In.Motion.Gravity.GetSafeNormal());
		FVector Fwd = ToBoat.InverseTransformVectorNoScale(S.GazeDir);
		// Within the neck's reach of the chest: 75 degrees either way, 35 up or down.
		const FVector ChestFwd = Chest != INDEX_NONE ? D[Chest].RotateVector(Frame.RotateVector(FVector::ForwardVector)) : Frame.RotateVector(FVector::ForwardVector);
		const FVector Horiz = (Fwd - UpCS * FVector::DotProduct(Fwd, UpCS)).GetSafeNormal();
		const FVector ChestH = (ChestFwd - UpCS * FVector::DotProduct(ChestFwd, UpCS)).GetSafeNormal();
		FVector H = Horiz;
		if (!ChestH.IsNearlyZero() && !Horiz.IsNearlyZero())
		{
			const double Yaw = FMath::Atan2(FVector::DotProduct(FVector::CrossProduct(ChestH, Horiz), UpCS), FVector::DotProduct(ChestH, Horiz));
			const double Lim = FMath::DegreesToRadians(75.0);
			if (FMath::Abs(Yaw) > Lim) H = FQuat(UpCS, FMath::Sign(Yaw) * Lim).RotateVector(ChestH);
		}
		const double Elev = FMath::Clamp(FMath::Asin(FMath::Clamp(FVector::DotProduct(Fwd, UpCS), -1.0, 1.0)), FMath::DegreesToRadians(-35.0), FMath::DegreesToRadians(35.0));
		Fwd = H * FMath::Cos(Elev) + UpCS * FMath::Sin(Elev);
		// The head's own up stays with the world's up (the eyes level). (Not a partial blend of this rotation: that would mix
		// the gaze's turn into the tilt.)
		// A tenth of the trunk's lean gets through (a head held dead level reads as a gimbal).
		const FVector ChestUp = Chest != INDEX_NONE ? D[Chest].RotateVector(Frame.RotateVector(FVector::UpVector)) : UpCS;
		const FQuat C = Limit(Aim(D[Head], Frame, Fwd, (0.9 * UpCS + 0.1 * ChestUp).GetSafeNormal()), FMath::DegreesToRadians(110.0));
		if (Neck != INDEX_NONE && Neck != Head)
		{
			const FQuat Cn = FQuat::Slerp(FQuat::Identity, C, 0.5f);
			RotateBone(Ref, D, Neck, Cn, Carried);
			// Everything below the neck turned by Cn; the head takes the rest.
			const int32 HP = Ref.GetParentIndex(Head);
			const FQuat DP = Cn * D[HP], DH = Cn * D[Head];
			Carried.Add(Ref.GetBoneName(Head), DP.Inverse() * (C * Cn.Inverse()) * DH);
		}
		else
		{
			RotateBone(Ref, D, Head, C, Carried);
		}
		CrewSolver::Solve(Ref, RestCS, Carried, CS, &D);
		const FVector HeadUp = D[Head].RotateVector(Frame.RotateVector(FVector::UpVector));
		S.Report.HeadTiltDeg = float(FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(HeadUp.GetSafeNormal(), UpCS), -1.0, 1.0))));
	}
}

void CrewSolePoints(const FReferenceSkeleton& Ref, const FCrewRig* Rig, const TArray<FTransform>& CS, FVector Out[2][2])
{
	const bool bRig = Rig && Rig->bValid && Rig->RestCS.Num() == Ref.GetNum();
	TArray<FTransform> Rest;
	if (!bRig) CrewSolver::RestPose(Ref, Rest);
	for (int32 S = 0; S < 2; ++S)
	{
		Out[S][0] = Out[S][1] = FVector::ZeroVector;
		CrewSolver::SolePoints(Ref, bRig ? Rig->RestCS : Rest, CS, bRig ? Rig->Frame : FQuat::Identity, S, Out[S]);
	}
}
