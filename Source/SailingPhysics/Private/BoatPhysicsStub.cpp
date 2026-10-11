#include "BoatPhysicsStub.h"

namespace Sailing
{
	double HullSpeedKnots(double WaterlineLengthMeters)
	{
		return 1.34 * FMath::Sqrt(WaterlineLengthMeters / MetersPerFoot);
	}

	namespace
	{
		double HeaveStiffness(const FBoatParams& P) { return WaterDensity * Gravity * P.WaterplaneArea; }
		double HeaveMass(const FBoatParams& P) { return P.Mass * (1.0 + P.AddedMassRatio); }
		double RollStiffness(const FBoatParams& P) { return P.Mass * Gravity * P.MetacentricHeight; }
		double RollInertia(const FBoatParams& P) { return P.Mass * P.RollGyradius * P.RollGyradius * (1.0 + P.AddedMassRatio); }
		double PitchStiffness(const FBoatParams& P) { return P.Mass * Gravity * P.LongitudinalGM; }
		double PitchInertia(const FBoatParams& P) { return P.Mass * P.PitchGyradius * P.PitchGyradius * (1.0 + P.AddedMassRatio); }
		double CriticalDamping(double K, double M) { return 2.0 * FMath::Sqrt(K * M); }
	}

	double FBoatPhysicsStub::HeavePeriod() const
	{
		return 2.0 * PI * FMath::Sqrt(HeaveMass(Params) / HeaveStiffness(Params));
	}

	double FBoatPhysicsStub::RollPeriod() const
	{
		return 2.0 * PI * FMath::Sqrt(RollInertia(Params) / RollStiffness(Params));
	}

	void FBoatPhysicsStub::Step(double Dt, const FBoatControls& Controls, double WaterSurfaceZ)
	{
		const FBoatParams& P = Params;
		FBoatState& S = State;
		const double Rudder = FMath::Clamp(Controls.Rudder, -1.0, 1.0);
		const double Throttle = FMath::Clamp(Controls.Throttle, -1.0, 1.0);

		// Heave: hydrostatic spring from the waterplane area, about the flat water surface.
		{
			const double K = HeaveStiffness(P), M = HeaveMass(P);
			const double C = P.HeaveDampingRatio * CriticalDamping(K, M);
			const double Force = -K * (S.Z - WaterSurfaceZ) - C * S.HeaveRate;
			S.HeaveRate += Force / M * Dt;
		}

		// Surge: placeholder thrust against linear + quadratic drag.
		{
			const double M = P.Mass;
			const double Drag = P.LinearDrag * S.Surge + P.QuadraticDrag * S.Surge * FMath::Abs(S.Surge);
			S.Surge += (Throttle * P.MaxThrust - Drag) / M * Dt;
		}

		// Yaw: bicycle-model turn rate from rudder angle and speed, with a first-order lag.
		{
			const double TargetYawRate = S.Surge * FMath::Tan(Rudder * P.MaxRudderAngle) / P.WaterlineLength;
			S.YawRate += (TargetYawRate - S.YawRate) / P.YawResponseTime * Dt;
		}

		// Heel: righting moment from GM, plus the outward heel a turn produces
		// (keel side force acts below the center of gravity, so a turn to starboard heels to port).
		{
			const double K = RollStiffness(P), I = RollInertia(P);
			const double C = P.RollDampingRatio * CriticalDamping(K, I);
			const double TurnMoment = -P.Mass * S.Surge * S.YawRate * P.TurnHeelCoefficient;
			const double Moment = -K * FMath::Sin(S.Heel) - C * S.RollRate + TurnMoment;
			S.RollRate += Moment / I * Dt;
		}

		// Pitch: righting moment from GML.
		{
			const double K = PitchStiffness(P), I = PitchInertia(P);
			const double C = P.PitchDampingRatio * CriticalDamping(K, I);
			const double Moment = -K * FMath::Sin(S.Pitch) - C * S.PitchRate;
			S.PitchRate += Moment / I * Dt;
		}

		// Semi-implicit Euler: integrate positions with the updated velocities.
		S.Z += S.HeaveRate * Dt;
		S.Heel += S.RollRate * Dt;
		S.Pitch += S.PitchRate * Dt;
		S.Heading = FMath::UnwindRadians(S.Heading + S.YawRate * Dt);
		S.X += S.Surge * FMath::Cos(S.Heading) * Dt;
		S.Y += S.Surge * FMath::Sin(S.Heading) * Dt;
	}
}
