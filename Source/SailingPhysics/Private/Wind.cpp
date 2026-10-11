#include "Wind.h"

namespace Sailing
{
	FWindField::FWindField(const FWindParams& InParams)
	{
		SetParams(InParams);
	}

	void FWindField::SetParams(const FWindParams& InParams)
	{
		Params = InParams;
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
		const double Along = WorldPos.Dot(DownwindDir) - MeanSpeed10 * TimeSeconds;
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
		const double Along = WorldPos.Dot(DownwindDir) - MeanSpeed10 * TimeSeconds;
		const double S = -Along / (MeanSpeed10 * Params.ShiftPeriodSeconds + 1.0) * 2.0 * kPi;
		return Params.ShiftDegrees * kDegToRad * 1.4 * Noise(S, 1);
	}

	Vec3 FWindField::VelocityAt(const Vec3& WorldPos, double TimeSeconds) const
	{
		const double Speed = MeanSpeedAtHeight(WorldPos.Z) * GustFactorAt(WorldPos, TimeSeconds);
		const double Shift = ShiftAt(WorldPos, TimeSeconds);
		const double C = std::cos(Shift), S = std::sin(Shift);
		const Vec3 Dir(DownwindDir.X * C - DownwindDir.Y * S, DownwindDir.X * S + DownwindDir.Y * C, 0.0);
		return Dir * Speed;
	}
}
