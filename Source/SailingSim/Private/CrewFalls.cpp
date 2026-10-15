#include "CrewFalls.h"

void FCrewFalls::Update(float Dt, float TiltDeg, float LateralG, float VerticalG, bool bCapsized)
{
	bJustFell = bJustRecovered = false;
	const bool bOver = bCapsized || TiltDeg > P.FallTiltDeg;
	const bool bKnock = LateralG > P.KnockG || FMath::Abs(VerticalG) > P.KnockG;
	const bool bSteady = !bCapsized && TiltDeg < P.SteadyTiltDeg && LateralG < P.SteadyG && FMath::Abs(VerticalG) < P.SteadyG;

	// A fall (or a new knock in the middle of gathering) takes the controls down to the weaker of the two causes.
	if (bOver || bKnock)
	{
		const float Floor = bOver ? P.CapsizeStrength : P.KnockStrength;
		if (Current == ECrewFallPhase::Posed)
		{
			bJustFell = true;
			++Falls;
			FallFloor = Floor;
		}
		else
		{
			FallFloor = FMath::Min(FallFloor, Floor);
		}
		if (Current != ECrewFallPhase::Falling) SinceFall = 0.f;
		Current = ECrewFallPhase::Falling;
		ControlStrength = FallFloor;
		Steady = 0.f;
	}

	switch (Current)
	{
	case ECrewFallPhase::Posed:
		ControlStrength = 1.f;
		break;
	case ECrewFallPhase::Falling:
		SinceFall += Dt;
		Steady = bSteady ? Steady + Dt : 0.f;
		if (SinceFall >= P.MinFallSeconds && Steady >= P.SteadySeconds)
		{
			Current = ECrewFallPhase::Gathering;
			Gathered = 0.f;
		}
		break;
	case ECrewFallPhase::Gathering:
		if (!bSteady && !(bOver || bKnock))
		{
			// Unsteady again (but not thrown): stop gaining, don't lose what was gained.
			break;
		}
		ControlStrength = FMath::Min(1.f, ControlStrength + Dt * (1.f - FallFloor) / FMath::Max(P.GatherSeconds, 1e-3f));
		if (ControlStrength >= 1.f)
		{
			Gathered += Dt;
			if (Gathered >= P.HoldSeconds)
			{
				Current = ECrewFallPhase::Posed;
				bJustRecovered = true;
				ControlStrength = 1.f;
			}
		}
		break;
	}
}
