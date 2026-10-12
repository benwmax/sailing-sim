#include "Wind.h"
#include "LakeTerrain.h"

namespace Sailing
{
	FWindField::FWindField(const FWindParams& InParams)
	{
		SetParams(InParams);
	}

	double FGustFront::DistanceAhead(double X, double Y, double T) const
	{
		const double A = MoveDegrees * kDegToRad;
		const double Along = (X - StartX) * std::cos(A) + (Y - StartY) * std::sin(A);
		return Along - SpeedMs * (T - StartTime);
	}

	void FWindField::SetParamsAt(const FWindParams& InParams, double T)
	{
		const double Offset = Advected(T);
		SetParams(InParams);
		AdvectionOffset = Offset;
		AdvectionTime = T;
	}

	void FWindField::SetParams(const FWindParams& InParams)
	{
		Params = InParams;
		AdvectionOffset = 0.0;
		AdvectionTime = 0.0;
		MeanSpeed10 = Params.SpeedKnots * kKnot;
		const double From = Params.FromDegrees * kDegToRad;
		DownwindDir = Vec3(-std::cos(From), -std::sin(From), 0.0);

		// Deterministic phases from the seed (xorshift), so gusts repeat exactly for a given seed.
		uint32_t S = Params.Seed ? Params.Seed : 1u;
		for (double& Phase : Phases)
		{
			S ^= S << 13; S ^= S >> 17; S ^= S << 5;
			Phase = (S % 100000u) / 100000.0 * 2.0 * kPi;
		}
	}

	double FWindField::MeanSpeedAtHeight(double HeightMeters) const
	{
		const double Z0 = Params.RoughnessLength;
		const double Z = std::max(HeightMeters, 0.05);
		return MeanSpeed10 * std::log(Z / Z0) / std::log(10.0 / Z0);
	}

	double FWindField::Noise(double S, int Octave) const
	{
		// Sum of incommensurate sines: smooth, cheap, deterministic, zero-mean, roughly unit amplitude.
		const double* P = &Phases[Octave * 4];
		return 0.45 * std::sin(S * 1.000 + P[0]) + 0.30 * std::sin(S * 2.137 + P[1])
			+ 0.15 * std::sin(S * 3.613 + P[2]) + 0.10 * std::sin(S * 5.271 + P[3]);
	}

	double FWindField::GustFactorAt(const Vec3& WorldPos, double TimeSeconds) const
	{
		if (Params.GustIntensity <= 0.0)
		{
			return 1.0;
		}
		// Position along the wind, minus how far the air has travelled: patches move downwind with the flow.
		const double Along = WorldPos.Dot(DownwindDir) - Advected(TimeSeconds);
		const Vec3 Across(-DownwindDir.Y, DownwindDir.X, 0.0);
		const double S = Along / Params.GustLengthMeters * 2.0 * kPi + 0.6 * std::sin(WorldPos.Dot(Across) / Params.GustLengthMeters * 2.0 * kPi + Phases[3]);
		return std::max(0.2, 1.0 + Params.GustIntensity * 1.6 * Noise(S, 0));
	}

	double FWindField::ShiftAt(const Vec3& WorldPos, double TimeSeconds) const
	{
		if (Params.ShiftDegrees <= 0.0)
		{
			return 0.0;
		}
		const double Along = WorldPos.Dot(DownwindDir) - Advected(TimeSeconds);
		const double S = -Along / (MeanSpeed10 * Params.ShiftPeriodSeconds + 1.0) * 2.0 * kPi;
		return Params.ShiftDegrees * kDegToRad * 1.4 * Noise(S, 1);
	}

	Vec3 FWindField::VelocityAt(const Vec3& WorldPos, double TimeSeconds) const
	{
		const double Speed = MeanSpeedAtHeight(WorldPos.Z) * GustFactorAt(WorldPos, TimeSeconds);
		const double Shift = ShiftAt(WorldPos, TimeSeconds);
		const double C = std::cos(Shift), S = std::sin(Shift);
		const Vec3 Dir(DownwindDir.X * C - DownwindDir.Y * S, DownwindDir.X * S + DownwindDir.Y * C, 0.0);
		Vec3 Wind = Dir * Speed;
		if (Shelter)
		{
			// In the lee of a point or treeline: less wind, and what is left is gustier.
			const double F = Shelter->FactorAt(WorldPos.X, WorldPos.Y);
			if (F < 0.999)
			{
				const double Along = WorldPos.Dot(DownwindDir) - Advected(TimeSeconds);
				const double Turbulence = 1.0 + (1.0 - F) * 0.8 * Noise(Along / 60.0 * 2.0 * kPi, 1);
				Wind *= F * std::max(0.3, Turbulence);
			}
		}

		if (Front.bActive && TimeSeconds >= Front.StartTime)
		{
			const double Ahead = Front.DistanceAhead(WorldPos.X, WorldPos.Y, TimeSeconds);
			const double W = SmoothStep(Front.LeadingEdgeMeters, -Front.LeadingEdgeMeters, Ahead);
			if (W > 0.0)
			{
				const double Decay = 1.0 - SmoothStep(Front.DecayStartTime, Front.DecayStartTime + Front.DecaySeconds, TimeSeconds);
				// Outflow: from the storm, strongest just behind the leading edge, with its own fast, violent gusts.
				const double OutFrom = Front.OutflowFromDegrees * kDegToRad;
				const Vec3 OutDir(-std::cos(OutFrom), -std::sin(OutFrom), 0.0);
				const double Profile = std::log(std::max(WorldPos.Z, 0.05) / Params.RoughnessLength) / std::log(10.0 / Params.RoughnessLength);
				const double Behind = std::max(0.0, -Ahead);
				const double EdgeBoost = 1.0 + 0.15 * std::exp(-Behind / 400.0);
				const double S2 = (WorldPos.Dot(OutDir) - Front.OutflowKnots * kKnot * TimeSeconds) / 120.0 * 2.0 * kPi;
				const double Gust = std::max(0.3, 1.0 + Front.OutflowGustIntensity * 1.6 * Noise(S2, 1));
				const Vec3 Outflow = OutDir * (Front.OutflowKnots * kKnot * Profile * EdgeBoost * Gust);
				const double Blend = W * Decay;
				Wind = Wind * (1.0 - Blend) + Outflow * Blend;
			}
		}
		return Wind;
	}

	double FWindField::SurfaceRoughnessAt(double X, double Y, double TimeSeconds) const
	{
		return VelocityAt(Vec3(X, Y, 10.0), TimeSeconds).LengthXY() / 8.0;
	}
}
