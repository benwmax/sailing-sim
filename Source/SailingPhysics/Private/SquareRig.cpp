#include "SquareRig.h"

#include <cmath>

namespace Sailing
{
	int FSquareRig::LowestOn(int Mast) const
	{
		int Best = -1;
		for (int I = 0; I < int(Sails.size()); ++I)
		{
			if (Sails[I].Mast == Mast && (Best < 0 || Sails[I].FootZ < Sails[Best].FootZ))
			{
				Best = I;
			}
		}
		return Best;
	}

	double FSquareRig::AreaOn(int Mast) const
	{
		double A = 0.0;
		for (const FSquareSailDef& S : Sails)
		{
			if (S.Mast == Mast) A += S.Area;
		}
		return A;
	}

	double SquareStallAlpha(const FSquareRig& Rig)
	{
		const double AR = Rig.AspectRatio;
		const double Slope = 2.0 * kPi * AR / (2.0 + std::sqrt(AR * AR + 4.0));
		return (0.75 + 4.0 * Rig.Camber) / Slope - 1.4 * Rig.Camber;
	}

	void SquareSailCoefficients(const FSquareRig& Rig, double AlphaRad, double& OutCL, double& OutCD, ESailFlow& OutFlow)
	{
		// A soft sail cut deep and wide, as SailCoefficients' (Sail.cpp) but for a chord that is its yard and an angle of
		// attack folded to 0..90 deg (either yardarm may lead). Lift: Helmbold's slope for its effective aspect ratio
		// from a zero-lift angle set by its belly, up to a maximum that grows with the belly (deep square sails reach
		// about 1.1-1.2: Marchaj, Aero-hydrodynamics of Sailing), then falling toward a bluff plate's 1.1 sin 2 alpha,
		// which is zero square to the wind. Drag: profile plus induced while it draws, and past the stall at least a
		// bluff plate's RunningCD sin^2 alpha (a sail square to the wind drives a ship by its drag alone).
		const double Alpha = Clamp(AlphaRad, 0.0, 0.5 * kPi);
		const double C = Rig.Camber;
		const double AR = Rig.AspectRatio;
		const double Slope = 2.0 * kPi * AR / (2.0 + std::sqrt(AR * AR + 4.0));
		const double ZeroLift = -1.4 * C;
		const double CLMax = 0.75 + 4.0 * C;
		const double Stall = SquareStallAlpha(Rig); // CLMax / Slope + ZeroLift
		double CL, Separation = 0.0;
		if (Alpha <= Stall)
		{
			CL = Slope * (Alpha - ZeroLift);
		}
		else
		{
			const double Over = Alpha - Stall;
			// Falling from its greatest lift, and to nothing square to the wind (the cos term), or the plate's if more.
			CL = std::max((CLMax - 0.9 * Over) * std::cos(Alpha) / std::cos(Stall), 1.1 * std::sin(2.0 * Alpha));
			Separation = std::min(0.6 * Over * Over + 0.4 * Over, 1.3);
		}
		// The weather leech lifts and the sail shakes as the wind comes along the yard.
		const double Luff = Rig.LuffDeg * kDegToRad;
		const double Shape = SmoothStep(0.0, Luff, Alpha);
		CL *= Shape;
		const double Flog = (1.0 - Shape) * 0.10;
		const double Profile = 0.015 + 0.5 * C * C;
		const double Induced = CL * CL / (kPi * Rig.InducedAspectRatio);
		const double Bluff = Rig.RunningCD * std::sin(Alpha) * std::sin(Alpha);
		OutCL = CL;
		OutCD = std::max(std::min(Profile + Induced + Separation + Flog, Rig.RunningCD), Bluff); // never more than the plate square on
		OutFlow = Shape < 0.6 ? ESailFlow::Luffing : (Alpha > Stall + 2.0 * kDegToRad && Alpha < 80.0 * kDegToRad ? ESailFlow::Stalled : ESailFlow::Attached);
	}

	double YardAngleFor(const FSquareRig& Rig, int Sail, double Brace)
	{
		const FSquareSailDef& S = Rig.Sails[Sail];
		const int Low = Rig.LowestOn(S.Mast);
		const double LowLimit = Low >= 0 ? Rig.Sails[Low].BraceLimitDeg : S.BraceLimitDeg;
		const double B = Clamp(Brace, -1.0, 1.0);
		const double LowDeg = B * LowLimit;
		// Squarer by the offset, never past square the other way, and no further than its own limit.
		const double Deg = std::fabs(LowDeg) <= S.BraceOffsetDeg ? 0.0 : LowDeg - (LowDeg > 0.0 ? 1.0 : -1.0) * S.BraceOffsetDeg;
		return Clamp(Deg, -S.BraceLimitDeg, S.BraceLimitDeg) * kDegToRad;
	}

	double BraceForAlpha(const FSquareRig& Rig, int Mast, double AwaRad, double AlphaDeg)
	{
		const int Low = Rig.LowestOn(Mast);
		if (Low < 0) return 0.0;
		const double A = std::fabs(AwaRad) * kRadToDeg;
		const double Psi = std::max(0.0, 90.0 + AlphaDeg - A); // A + psi - 90 = alpha; never braced the wrong way
		const double Sign = AwaRad >= 0.0 ? 1.0 : -1.0;
		return Clamp(Sign * Psi / Rig.Sails[Low].BraceLimitDeg, -1.0, 1.0);
	}
}
