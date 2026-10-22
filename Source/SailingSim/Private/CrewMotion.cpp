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
	float Side = In.CrewOffset != 0.0 ? float(FMath::Sign(In.CrewOffset)) : float(In.WindwardSide);
	// Running with the boom out past 55 degrees a keelboat's or multihull's crew sit on the windward side, away from the
	// boom, as crews do: on its side an eased mainsheet swept the helm's and the trimmer's backs (the Corsair's traveler at
	// her cockpit's aft end, the maxi's in her cockpit).
	if (!bDinghy && FMath::Abs(In.BoomAngle) > FMath::DegreesToRadians(55.0)) Side = -float(FMath::Sign(In.BoomAngle));
	const double Off = FMath::Abs(In.CrewOffset);
	double X = Cfg.CrewCG.X + 0.55 * (0.5 * (N - 1) - I) + In.CrewOffsetX;
	// Round 11: a keelboat's crew sit beside the cockpit well with their feet in it, so the forward sailor (the J/22's bow,
	// at x -0.65, was beside the cabin trunk, 7 cm forward of the well) comes back to its forward end.
	FCrewCockpitWell KeelWell;
	// (Not the maxi: her rail crew line the deck forward of her 10 m cockpit; the clamp would bunch them at its end.)
	if (!bDinghy && !Cfg.bMultihull && I != N - 1 && Cfg.Type != EBoatType::Maxi && CrewCockpitWell(Cfg, KeelWell))
	{
		// The crew between the bow and the helm (the trimmer) sit 0.1 m further aft: with the bow brought back they were
		// 0.36 m apart and their shoulders overlapped on the rail (docs/crew-pose/mac).
		X = FMath::Clamp(X - (I > 0 ? 0.1 : 0.0), KeelWell.X0 + 0.3, KeelWell.X1 - 0.12);
	}
	// docs/crew-followups/: the Catalinas' crew spread along the cockpit, not shoulder to shoulder in its after part
	// (0.55 m apart round CrewCG they left the forward half empty): the forward hand at its forward end, the helm at the
	// tiller's end (the 22) or where the wheel boat's helm already sits (the 30), the rest evenly between, 0.45-0.9 m apart.
	if ((Cfg.Type == EBoatType::Catalina22 || Cfg.Type == EBoatType::Catalina30) && CrewCockpitWell(Cfg, KeelWell))
	{
		const bool bTiller = Cfg.WheelHardOverSeconds <= 0.0;
		// (Steering from the extension, the helm sits along the tiller, three quarters of the way to its end.)
		const double HelmX = bTiller ? FMath::Clamp(Hull.SternX + 0.75 * Cfg.TillerLength + 0.15, KeelWell.X0 + 0.35, KeelWell.X1 - 0.12)
			: Cfg.CrewCG.X + 0.55 * (0.5 * (N - 1) - (N - 1));
		if (I == N - 1)
		{
			if (bTiller) X = HelmX;
		}
		else
		{
			// (0.8 m clear ahead of the helm: at 0.6 the 22's middle hand's back was a hand's width from the helm's face, the
			// cockpit camera's eye: docs/cockpit-eye/.)
			const double Fwd = KeelWell.X1 - 0.3, Aft = HelmX + 0.8;
			// (At least 0.45 m apart, a body's width and a little: a 0.55 m floor put the 30's aftmost hand 0.43 m from her
			// helm, at the cockpit camera's eye: docs/cockpit-eye/.)
			const double Step = N > 2 ? FMath::Clamp((Fwd - Aft) / (N - 2), 0.45, 0.9) : 0.0;
			X = Fwd - Step * I;
		}
	}
	// Round 12: the J/22's helm sits aft of the traveler, about level with the tiller's end. At x -1.75 they sat forward
	// of the traveler against the trimmer, the three crew bunched by the cabin with the after half of the cockpit empty.
	if (Cfg.Type == EBoatType::J22 && I == N - 1 && CrewCockpitWell(Cfg, KeelWell))
	{
		X = FMath::Clamp(FMath::Min(X, Hull.SternX + Cfg.TillerLength + 0.15), KeelWell.X0 + 0.35, KeelWell.X1 - 0.12);
	}
	// Multihull crew: a trimaran's helm sits in the main hull's cockpit (the Corsair's tiller is on the centreline, the
	// ama 2.8 m out of reach); her crew out past the main hull's deck sit on the windward net, forward of the after aka
	// (at x -2.05 and -2.6 they sat over the water behind it) and of the cockpit, side by side.
	const bool bTrimaran = Cfg.bMultihull && Cfg.Hulls.size() == 3;
	double NetAft = 0.0, NetForward = 0.0;
	if (bTrimaran && I != N - 1 && FMath::Abs(In.CrewOffset) > Hull.DeckHalfBeam(X) && CrewNetSpan(Cfg, NetAft, NetForward))
	{
		// Forward of the cockpit too: facing inboard from beside it, their feet came down on its seats' edge, tilted.
		FCrewCockpitWell TriWell;
		const double From = CrewCockpitWell(Cfg, TriWell) ? FMath::Max(NetAft, TriWell.X1) : NetAft;
		X = FMath::Clamp(X, From + 0.35 + 0.55 * (N - 2 - I), NetForward - 0.5);
	}
	// docs/crew-hull-clip/: the Lagoon's crew in her cockpit, aft of the saloon (x -2.4) and forward of the bridgedeck's
	// end, not in the saloon or under the cockpit table (x -3.3, 1.5 by 1.1 m: build_fleet.py lagoon_detail()).
	const bool bLagoonCockpit = Cfg.Type == EBoatType::Lagoon42 && I != N - 1;
	if (bLagoonCockpit) X = FMath::Clamp(X, -4.1, -2.75);
	const double Rail = Cfg.bMultihull && !(bTrimaran && I == N - 1) ? FMath::Abs(Cfg.Hulls.back().CenterY) + 0.2 : Hull.DeckHalfBeam(X);
	// On a multihull the stances below are placed over 0 and lifted onto the surface under the sailor at the end
	// (CrewSeatSurfaceZ: a hull's deck, the net, trampoline or bridgedeck); before, they all took the main hull's sheer
	// plus 0.1 m, wherever they were.
	const double Sheer = Cfg.bMultihull ? 0.0 : Hull.SheerHeight(X);
	FCrewPoseParams& P = Out.Params;
	Out.bHelm = I == N - 1;
	Out.Roll = 0.f;
	Out.Duck = 0.f;
	P.Side = Side;
	P.Hike = float(FMath::Clamp((Off - Cfg.CrewSitOut * 0.8) / FMath::Max(Cfg.CrewHikeOut, 0.1), 0.0, 1.0));
	// Round 10: a dinghy sailor sits on the side deck, at its edge from about the sit-out offset, and leans out from there:
	// how far they lean is how far the crew model has them past the edge, up to fully hiked (sit-out plus hike-out). Inboard
	// of the edge they slide in along the side deck (the ILCA sailor read as sitting in the cockpit: the hike was measured
	// from 80 % of the sit-out, a bolt-upright sailor at the edge).
	FCrewCockpitWell Well;
	const bool bWell = bDinghy && !Cfg.bMultihull && CrewCockpitWell(Cfg, Well);
	const double Edge = Rail - 0.04;
	const double Inner = bWell ? FMath::Min(Well.HalfWidth + 0.14, Edge) : Edge;
	if (bDinghy)
	{
		const double From = Edge - 0.06, Full = Cfg.CrewSitOut + Cfg.CrewHikeOut;
		P.Hike = float(FMath::Clamp((Off - From) / FMath::Max(Full - From, 0.1), 0.0, 1.0));
		P.Inboard = float(FMath::Clamp((From - Off) / FMath::Max(From - Inner, 0.1), 0.0, 1.0));
	}
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
		|| (FMath::Abs(In.OffsetRate) > 0.6 && Off < (bDinghy ? FMath::Min(0.2, 0.8 * Cfg.CrewSitOut) : 0.8 * Cfg.CrewSitOut));
	// docs/crew-hull-clip/: facing across the boat in the well (on a seat, or crossing), the hips are a body's width
	// apart fore and aft; at 0.12 m from the well's forward end the forward hip went into the cabin trunk's face.
	// (Each a body's width, 0.42 m, further aft than the one forward of them: held all to the same 0.3 m they sat in each
	// other. The J/22's two in the 0.95 m between her cabin and her traveler bridge sit on opposite seats instead: below.)
	if (!bDinghy && !Cfg.bMultihull && Cfg.Type != EBoatType::Maxi && !Out.bHelm && KeelWell.X1 > KeelWell.X0 && (bCrossing || Off <= 0.55 * Rail))
	{
		X = FMath::Min(X, KeelWell.X1 - 0.3 - (Cfg.Type == EBoatType::J22 ? 0.0 : 0.42 * I));
	}
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
		// The Catalina 22's helm crosses forward of her mainsheet's tackle (from the boom's end, MainLuffX less the foot,
		// down to the transom): at the tiller's end they crossed through it (SailingSim.Visual.SheetClearance).
		if (Cfg.Type == EBoatType::Catalina22 && Out.bHelm) X = FMath::Max(X, Cfg.MainLuffX - Cfg.MainFootChord + 0.3);
		Out.Duck = bUnderBoom ? float(FMath::Clamp(1.25 - BoomDeg / 28.0, 0.0, 1.0)) : 0.f;
		// Down to a crouch under the boom (the head about 0.75 m above the pelvis crouched, 10 cm clear).
		// Into the middle as the boom comes over them (the crew model then takes them to the new side), never lower than a
		// deep crouch over the floor under them.
		const double Y = In.CrewOffset * (1.0 - Out.Duck);
		const double Up = Sheer + (bDinghy ? 0.25 : 0.05);
		const double FloorZ = CrewFloorZ(Cfg, X, Y);
		// (30 cm over the floor at the lowest: at 22 the folded knees went through the sole: docs/crew-hull-clip/.)
		const double Lowest = FloorZ > -1e8 ? FloorZ + 0.30 : Sheer - 0.3;
		const double Under = FMath::Max(Cfg.BoomZ - 0.85, Lowest);
		Out.Pelvis = FVector(X, Y, FMath::Lerp(Up, FMath::Min(Up, Under), double(Out.Duck)));
		// docs/crew-hull-clip/: over a cabin trunk (the maxi's coachroof), crossing on top of it.
		FCrewCabinTrunk Trunk;
		if (CrewCabinTrunk(Cfg, Trunk) && X > Trunk.X0 - 0.4 && X < Trunk.X1) Out.Pelvis.Z = FMath::Max(Out.Pelvis.Z, Sheer + Trunk.Height + 0.25);
	}
	else if (bDinghy)
	{
		P.Stance = ECrewStance::DinghyHike;
		Out.Pelvis = FVector(X, Side * FMath::Clamp(Off + 0.06, Inner, Edge), Sheer + 0.06);
	}
	else if (Out.bHelm)
	{
		P.Stance = ECrewStance::Helm;
		Out.Pelvis = FVector(X, Side * FMath::Max(Rail - 0.18, 0.3), Sheer + 0.07);
		// docs/crew-hull-clip/: the maxi's helm aft of the windward wheel (ref.json "wheels": x -13.0, 2.15 m out), on the
		// cockpit's edge with the legs in it; at x -9 on the rail their legs went down through 1.1 m of deck.
		if (Cfg.Type == EBoatType::Maxi) Out.Pelvis = FVector(-13.7, Side * 2.55, CrewSeatSurfaceZ(Cfg, -13.7, Side * 2.55) + 0.07);
		// docs/cockpit-eye/: the Catalina 30's helm behind her wheel (build_fleet.py SPECS: at x -3.45 in the well, which ends
		// at -4.05), on the after deck to windward of its rim (0.42 m across: seated behind it the rim was at eye height), the
		// legs in the well, on a helm seat 25 cm over the deck so they see over the rim. On the rail beside the wheel they faced the crew's row, and the cockpit camera, at their head,
		// looked along it.
		if (Cfg.Type == EBoatType::Catalina30) Out.Pelvis = FVector(-4.15, Side * 0.65, Hull.SheerHeight(-4.15) + 0.32);
		// The Lagoon's helm on her helm seat (build_fleet.py lagoon_detail(): aft of the saloon on the starboard side,
		// the cushion 0.49 m over the bridgedeck), not on a hull's deck aft.
	}
	else if (Off > 0.55 * Rail || (Cfg.Type == EBoatType::Maxi && !Out.bHelm))
	{
		// (The maxi's crew forward of her cockpit have no seat but the side deck: her coachroof fills the middle.)
		P.Stance = ECrewStance::RailHike;
		// Sitting on the side deck a hand's width in from the edge, facing inboard (round 11: not on the edge, legs over).
		// docs/crew-hull-clip/: inside the lifelines where the boat has them (stanchions 5 cm in from the edge, wires at
		// 0.3 and 0.6 m: build_fleet.py lifelines()), and leaning back against them, not out through them.
		const bool bLifelines = CrewHasLifelines(Cfg);
		Out.Pelvis = FVector(X, Side * (Rail - (bLifelines ? 0.32 : 0.12)), Sheer + 0.07);
		if (bLifelines) P.Hike = FMath::Min(P.Hike, 0.3f);
		// On the maxi's cambered deck (the seat is its crown, not the sheer), and her twelve rail crew are not one pose
		// repeated: a little more or less hiked, a little fore or aft, by their place on the rail.
		if (!Cfg.bMultihull) Out.Pelvis.Z = CrewSeatSurfaceZ(Cfg, X, Out.Pelvis.Y) + 0.07;
		if (Cfg.Type == EBoatType::Maxi)
		{
			const float Vary = FMath::Frac(0.618034f * float(I + 1)) - 0.5f;
			P.Hike = FMath::Clamp(P.Hike + 0.5f * Vary, 0.f, 1.f);
			Out.Pelvis.X += 0.16 * FMath::Frac(0.414214 * double(I + 1)) - 0.08;
		}
	}
	else
	{
		// Light air or downwind: on the cockpit seat (to leeward if the crew model put them there).
		P.Stance = ECrewStance::Cockpit;
		// The J/22's trimmer on the leeward seat, by the working jib winch's self-tailer (the crew model can put the light-air
		// crew to windward, 1.1 m across the well from it, and the trimmer let go of the tail); the bow on the other seat:
		// 0.28 m apart on one seat they sat in each other (the well forward of her traveler bridge has room for one a side;
		// further apart their feet stepped onto the bridge or the cabin's face), and 5 cm forward, the knees clear of the
		// trimmer's thigh across the well.
		if (Cfg.Type == EBoatType::J22 && N == 3 && I < N - 1 && In.TrueWindAngle != 0.0)
		{
			const float Lee = -float(FMath::Sign(In.TrueWindAngle));
			P.Side = I == N - 2 ? Lee : -Lee;
			if (I == 0) X = FMath::Min(X + 0.05, KeelWell.X1 - 0.25);
		}
		Out.Pelvis = FVector(X, P.Side * FMath::Clamp(Off, 0.35, FMath::Max(Rail - 0.45, 0.35)), Sheer - 0.10);
		// docs/crew-hull-clip/: on the seat, not 6 cm into it (a seated pelvis is about 9 cm over what it sits on).
		if (!Cfg.bMultihull)
		{
			const double Floor = CrewFloorZ(Cfg, Out.Pelvis.X, Out.Pelvis.Y);
			if (Floor > -1e8) Out.Pelvis.Z = FMath::Max(Out.Pelvis.Z, Floor + 0.09);
		}
		// A multihull's net or bridgedeck has no seat to drop the legs from: sit on it as on a side deck.
		FCrewCockpitWell CockpitWell;
		const bool bInWell = CrewCockpitWell(Cfg, CockpitWell) && CrewFloorZ(Cfg, X, Out.Pelvis.Y) < Hull.SheerHeight(X) - 0.05;
		if (Cfg.bMultihull && !bInWell)
		{
			P.Stance = ECrewStance::RailHike;
			Out.Pelvis.Z = Sheer + 0.07;
		}
	}
	if (bLagoonCockpit && FMath::Abs(Out.Pelvis.X + 3.3) < 0.7 && FMath::Abs(Out.Pelvis.Y) < 0.9) Out.Pelvis.Y = Side * 0.9;
	if (Cfg.Type == EBoatType::Lagoon42 && Out.bHelm && P.Stance == ECrewStance::Helm)
	{
		const Sailing::FHullShape& Stbd = Cfg.Hulls[1];
		const double HelmY = FMath::Abs(Stbd.CenterY) - Stbd.DeckHalfBeam(0.0) + 0.55 - 0.35;
		Out.Pelvis = FVector(-2.75 - 0.5, HelmY, 0.07);   // over the seat (CrewSeatSurfaceZ, below)
		P.Side = 1.f;
	}
	// (On a hull's crowned deck, the seat is the crown under the thighs, a little inboard of the hips: the Hobie's.)
	if (Cfg.bMultihull) Out.Pelvis.Z += FMath::Max(CrewSeatSurfaceZ(Cfg, Out.Pelvis.X, Out.Pelvis.Y), CrewSeatSurfaceZ(Cfg, Out.Pelvis.X, Out.Pelvis.Y - P.Side * 0.10));
	// docs/crew-hull-clip/: sitting where the floor ahead of the feet is as high as the seat (no well to put the feet
	// in): knees up, feet on the deck.
	// (The Hobie's dinghy stance too, on her trampoline: its legs had dropped into a well that isn't there, a kneel.)
	if (P.Stance == ECrewStance::RailHike || (P.Stance == ECrewStance::DinghyHike && Cfg.bMultihull))
	{
		const double FootY = Out.Pelvis.Y - P.Side * 0.45;
		const double SeatZ = Out.Pelvis.Z - 0.07;
		const double FootZ = Cfg.bMultihull ? CrewSeatSurfaceZ(Cfg, Out.Pelvis.X, FootY) : CrewFloorZ(Cfg, Out.Pelvis.X, FootY);
		P.bFlatDeck = FootZ > SeatZ - 0.15;
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
		// (On top of the trunk: docs/crew-hull-clip/, at 0.30 m over the sheer it was inside the J/22's 0.31 m trunk and the
		// reaching arm went through its corner.)
		FCrewCabinTrunk Trunk;
		const double HandrailZ = CrewCabinTrunk(C, Trunk) ? Trunk.Height + 0.10 : 0.30;
		Out.HandholdCabin[S] = FVector(CabinX, Y * CabinHalf, H.SheerHeight(CabinX) + HandrailZ) * ToCm;
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

	// Crew C1b: the idle clips, quiet while the sailor moves (a crossing, a change of seat), braces or ducks.
	FCrewClipInput Clip;
	Clip.Stance = In.Params.Stance;
	Clip.Hike = In.Params.Hike;
	Clip.bQuiet = !In.bReact || !In.bClips || S.TransitionS < 1.f || S.bBracing || In.Duck > 0.f;
	Clip.Roll = S.Balance.Roll;
	Clip.Pitch = S.Balance.Pitch;
	Clip.Seed = Seed;
	CrewClipStep(S.Clip, Clip, Dt);
	S.Report.ClipWeight = S.Clip.Weight;
	S.Report.Clip = S.Clip.Cur.Clip;

	// The gaze: their eyes go to the target, the head follows in a few tenths of a second.
	// (From about where the head is: 1.5 m over the figure's origin, which is under its pelvis at standing height.)
	const FVector Eyes = In.ToBoat.TransformPosition(FVector(0.0, 0.0, 150.0));
	FVector Want = In.Gaze.IsNearlyZero() ? FRotator(0.f, CrewFacingYaw(In.Params), 0.f).Vector() : (In.Gaze - Eyes).GetSafeNormal();
	if (Want.IsNearlyZero()) Want = FVector::ForwardVector;
	// The clip's own glances about it (the head and neck as captured).
	if (S.Clip.Weight > 0.f)
	{
		FRotator Look = Want.Rotation();
		Look.Yaw += S.Clip.GazeYaw;
		Look.Pitch += S.Clip.GazePitch;
		Want = Look.Vector();
	}
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
		// Crew C1b: the idle clip about the stance, first, so the reaction layer stays on top of it.
		if (S.Clip.Weight > 0.f)
		{
			for (int32 J = 0; J < CrewClips::NumJoints(); ++J)
			{
				const FVector& V = S.Clip.Joints[J];
				const double A = V.Size();
				if (A > 1e-6) PreMultiply(Joints, CrewClips::JointName(J), FQuat(V / A, A));
			}
		}
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
	// (Not the feet of a sailor on a flat deck: docs/crew-hull-clip/, the maxi's rail crew reached for the far seat of
	// her cockpit and put a leg down through the deck between.)
	if (bBrace && !In.Params.bFlatDeck)
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
		const ECrewStance St = In.Params.Stance;
		Ground.bSeated = St == ECrewStance::Helm || St == ECrewStance::Cockpit || St == ECrewStance::RailHike;
		Ground.bTravelerBridge = In.bTravelerBridge;
		Ground.bFeetDown = St == ECrewStance::Helm || St == ECrewStance::Cockpit;
		Ground.bFlatDeck = In.Params.bFlatDeck;
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
					if (Dist < Best)
					{
						Best = Dist;
						Hands.Mode[H] = FCrewHands::EMode::Reach;
						Hands.Target[H] = At;
						Hands.Grip[H] = 0.95f;
						Hands.Along[H] = ToBoat.InverseTransformVectorNoScale(FVector::ForwardVector); // the rails run fore and aft
					}
				}
			}
		}
	}
	if (CrewSolver::PlaceHands(Ref, RestCS, CS, D, Hands, Carried)) CrewSolver::Solve(Ref, RestCS, Carried, CS, &D);
	CrewSolver::ClearFingers(Ref, RestCS, CS, D, Hands, Carried);

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
