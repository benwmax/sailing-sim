#include "Sail.h"

namespace Sailing
{
	void SailCoefficients(const FSailGeometry& Geo, double AlphaN, double Camber, double StallDelta,
		double& OutCL, double& OutCD, double& OutLuffAlpha, double& OutStallAlpha, ESailFlow& OutFlow)
	{
		const double A = Geo.LiftSlope;
		const double ZeroLift = -2.0 * Camber;               // thin-airfoil zero-lift angle for a parabolic camber
		const double CLMax = 0.95 + 4.5 * Camber;
		const double Stall = CLMax / A + ZeroLift + StallDelta;
		// A cambered sail's ideal (smooth-entry) angle of attack is about zero; a soft luff starts to bubble a few
		// degrees below that, sooner for a flatter sail.
		const double Luff = -(0.4 * Camber + 0.035);
		OutLuffAlpha = Luff;
		OutStallAlpha = Stall;

		double CL;
		double SeparationDrag = 0.0;
		if (AlphaN <= Stall)
		{
			CL = A * (AlphaN - ZeroLift);
		}
		else
		{
			// Past the stall: lift falls away toward a flat plate, drag climbs.
			const double Over = AlphaN - Stall;
			CL = std::max(CLMax - 0.9 * Over, 1.15 * std::sin(2.0 * AlphaN));
			SeparationDrag = std::min(0.6 * Over * Over + 0.4 * Over, 1.3);
		}

		// Luffing: as the angle of attack falls toward the luff angle the sail loses its shape and flogs.
		const double Shape = SmoothStep(Luff - 2.0 * kDegToRad, Luff + 4.0 * kDegToRad, AlphaN);
		CL *= Shape;
		double Flog = (1.0 - Shape) * 0.10;

		// Backed: well below the luff angle the wind fills the sail from the wrong side.
		const double Back = SmoothStep(Luff - 6.0 * kDegToRad, Luff - 16.0 * kDegToRad, AlphaN);
		if (Back > 0.0)
		{
			const double Depth = std::min(Luff - AlphaN, 60.0 * kDegToRad);
			CL = Lerp(CL, -1.0 * std::sin(2.0 * Depth), Back);
			Flog *= (1.0 - Back);
		}

		const double Profile = 0.012 + 0.5 * Camber * Camber;
		const double Induced = CL * CL / (kPi * Geo.InducedAspectRatio);
		// Well past the stall a sail is a bluff plate: a normal force coefficient of about 1.25, so drag grows with
		// sin(alpha) (Marchaj's wind-tunnel sails). This is what drives a boat on a run.
		const double Separated = SmoothStep(Stall, Stall + 10.0 * kDegToRad, AlphaN) * 1.25 * std::fabs(std::sin(AlphaN));
		const double FlatPlate = std::max(1.40 * std::sin(AlphaN) * std::sin(AlphaN), Separated);
		CL = std::min(CL, Geo.MaxLift);
		OutCL = CL;
		OutCD = std::max(Profile + Induced + SeparationDrag + Flog + Geo.ParasiteDrag * std::max(CL, 0.0) / std::max(Geo.MaxLift, 1.0), FlatPlate);

		if (Back > 0.5)
		{
			OutFlow = ESailFlow::Backed;
		}
		else if (Shape < 0.6)
		{
			OutFlow = ESailFlow::Luffing;
		}
		else if (AlphaN > Stall + 2.0 * kDegToRad)
		{
			OutFlow = ESailFlow::Stalled;
		}
		else
		{
			OutFlow = ESailFlow::Attached;
		}
	}
}
