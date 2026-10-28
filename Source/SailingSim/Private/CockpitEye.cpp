#include "CockpitEye.h"
#include "CrewMotion.h"

void FCockpitEye::Reset(const FVector& Raw)
{
	Eye = Raw;
	EyeV = FVector::ZeroVector;
	Gap = Lift = Lead = LeadV = 0.f;
	SeatedZ = float(Raw.Z);
	Settle = 10.f;
	bStarted = true;
	bWasCrossing = false;
}

FVector FCockpitEye::Step(const FCockpitEyeInput& In, float Dt, float& OutLeadDeg)
{
	// (A teleport, a new boat: more than a metre in a frame.)
	if (!bStarted || FVector::Dist(In.RawEye, Eye) > 100.0) Reset(In.RawEye);
	if (In.bCrossing && !bWasCrossing)
	{
		SeatedZ = float(Eye.Z);
		CrossY = float(Eye.Y);
		CrossDir = Eye.Y > 0.0 ? -1.f : 1.f;   // toward the other side
	}
	Settle = In.bCrossing ? 0.f : Settle + Dt;
	bWasCrossing = In.bCrossing;
	// Across and fore and aft: soft through a crossing (about a second to settle), handing back over 1.5 s after it to the
	// stiff springs that leave steady sailing as it was.
	const float Soft = In.bCrossing ? 1.f : 1.f - FMath::Clamp(Settle / 1.5f, 0.f, 1.f);
	const float OmegaXY = FMath::Lerp(30.f, 6.f, Soft);
	// Height: through the crossing only 40 % of the head's drop below where it sat, and never into the boom; the soft spring
	// also takes out the steps' bob.
	float WantZ = float(In.RawEye.Z);
	if (In.bCrossing) WantZ = SeatedZ - DropShare * FMath::Max(0.f, SeatedZ - float(In.RawEye.Z));
	// (The boom ahead of the eye too: the input's window is wider than the boom, so the soft spring is down before it is
	// overhead and the clamp below seldom binds; a clamp snapping on and off read as a bob.)
	if (In.bBoomNear) WantZ = FMath::Min(WantZ, float(In.BoomUnderZ) - BoomClearCm - 3.f);
	if (In.bBoomOver) WantZ = FMath::Min(WantZ, float(In.BoomUnderZ) - BoomClearCm);
	// (Quicker down while the boom is coming over: the soft spring alone was still above it as it arrived.)
	const float OmegaZ = FMath::Max(FMath::Lerp(30.f, 4.f, Soft), In.bBoomNear && In.RawEye.Z > In.BoomUnderZ - BoomClearCm - 20.0 ? 9.f : 0.f);
	float X = float(Eye.X), Y = float(Eye.Y), Z = float(Eye.Z), Vx = float(EyeV.X), Vy = float(EyeV.Y), Vz = float(EyeV.Z);
	CrewSpring(X, Vx, float(In.RawEye.X), OmegaXY, Dt);
	// (Across one way only: through the crossing the target never goes back toward the old side, as the head sways with
	// the steps.)
	float WantY = float(In.RawEye.Y);
	if (In.bCrossing)
	{
		CrossY = CrossDir < 0.f ? FMath::Min(CrossY, WantY) : FMath::Max(CrossY, WantY);
		WantY = CrossY;
	}
	CrewSpring(Y, Vy, WantY, OmegaXY, Dt);
	if (In.bCrossing) Y = CrossDir < 0.f ? FMath::Min(Y, float(Eye.Y)) : FMath::Max(Y, float(Eye.Y));
	CrewSpring(Z, Vz, WantZ, OmegaZ, Dt);
	Eye = FVector(X, Y, Z);
	EyeV = FVector(Vx, Vy, Vz);
	// A gap to the heads ahead or beside: nearer than 45 cm (not behind the eye), it eases aft by enough to be 45 cm away
	// (in over 0.15 s, out over 0.5 s); where the cockpit's end stops it, it lifts the rest, up to 10 cm.
	float Short = 0.f;
	for (const FVector& H : In.Heads)
	{
		const FVector D = H - Eye;
		if (D.X < -5.0) continue;
		// How far aft puts it GapCm away: solve |D + (s, 0, 0)| = GapCm for s >= 0.
		const double Rest = FMath::Square(double(GapCm)) - D.Y * D.Y - D.Z * D.Z;
		if (Rest <= 0.0) continue;
		Short = FMath::Max(Short, float(FMath::Sqrt(Rest) - D.X));
	}
	Short = FMath::Max(Short, 0.f);
	Gap += (Short - Gap) * FMath::Clamp(Dt / (Short > Gap ? 0.15f : 0.5f), 0.f, 1.f);
	FVector Out = Eye - FVector(Gap, 0.f, 0.f);
	const double Stop = FMath::Max(In.MinX, Out.X);
	const float Unmet = float(Stop - Out.X);
	Out.X = FMath::Min(Stop, In.MaxX);
	Lift += (FMath::Min(Unmet, 10.f) - Lift) * FMath::Clamp(Dt / (Unmet > Lift ? 0.3f : 0.6f), 0.f, 1.f);
	Out.Z += Lift;
	if (In.bBoomOver) Out.Z = FMath::Min(Out.Z, In.BoomUnderZ - BoomClearCm);
	// A small look into the turn (real helms look across at the new side's telltales), not while the player is looking.
	const float WantLead = In.bPlayerLooking ? 0.f : FMath::Clamp(float(FMath::RadiansToDegrees(In.TurnRate * 0.5)), -MaxLeadDeg, MaxLeadDeg);
	CrewSpring(Lead, LeadV, WantLead, 6.f, Dt);
	Lead = FMath::Clamp(Lead, -MaxLeadDeg, MaxLeadDeg);
	OutLeadDeg = Lead;
	return Out;
}
