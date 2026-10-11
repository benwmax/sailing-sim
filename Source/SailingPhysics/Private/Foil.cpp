#include "Foil.h"

namespace Sailing
{
	void FoilCoefficients(const FFoilParams& Foil, double Alpha, double& OutCL, double& OutCD, bool& bOutStalled)
	{
		const double Stall = Foil.StallAngleDeg * kDegToRad;
		const double A = std::fabs(Alpha);
		const double Slope = Foil.LiftSlope();

		// Attached flow: linear lift up to the stall angle.
		const double Attached = Slope * Sign(Alpha) * std::min(A, Stall);
		// Separated flow: a flat plate.
		const double FlatPlate = 1.05 * std::sin(2.0 * Alpha);
		const double Blend = SmoothStep(Stall, Stall + 8.0 * kDegToRad, A);

		OutCL = (1.0 - Blend) * Attached + Blend * FlatPlate;
		const double Induced = OutCL * OutCL / (kPi * Foil.EffectiveAspectRatio * Foil.OswaldEfficiency);
		OutCD = Foil.ProfileDrag + Induced + Blend * 1.2 * std::sin(Alpha) * std::sin(Alpha);
		bOutStalled = A > Stall;
	}

	FFoilResult ComputeFoil(const FFoilParams& Foil, const Vec3& FlowBody, const Vec3& ChordDir, double Density, double LiftFactor)
	{
		FFoilResult Result;
		const Vec3 U(FlowBody.X, FlowBody.Y, 0.0);
		const double Speed = U.Length();
		if (Speed < 1e-4)
		{
			return Result;
		}

		const double CrossZ = ChordDir.X * U.Y - ChordDir.Y * U.X;
		const double DotC = ChordDir.X * U.X + ChordDir.Y * U.Y;
		Result.AngleOfAttack = std::atan2(CrossZ, DotC);

		FoilCoefficients(Foil, Result.AngleOfAttack, Result.LiftCoefficient, Result.DragCoefficient, Result.bStalled);
		Result.LiftCoefficient *= LiftFactor;

		const double Q = 0.5 * Density * Speed * Speed * Foil.Area;
		const Vec3 FlowDir = U / Speed;
		const Vec3 LiftDir(-FlowDir.Y, FlowDir.X, 0.0);
		Result.Force = LiftDir * (Result.LiftCoefficient * Q) + FlowDir * (Result.DragCoefficient * Q);
		return Result;
	}
}
