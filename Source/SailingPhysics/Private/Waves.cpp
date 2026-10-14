#include "Waves.h"
#include "Ocean.h"

namespace Sailing
{
	namespace
	{
		constexpr double kMinFrequency = 0.18; // Hz (wavelength about 48 m)
		constexpr double kMaxFrequency = 2.4;  // Hz (about 0.27 m)
	}

	FWaveField::FWaveField(uint32_t Seed)
	{
		Params.Seed = Seed;
		uint32_t S = Seed ? Seed * 2654435761u : 1u;
		auto Rand = [&S]()
		{
			S ^= S << 13; S ^= S >> 17; S ^= S << 5;
			return (S % 1000000u) / 1000000.0;
		};

		// Log-spaced frequency bands; in each band a few directions spread around the compass with jitter,
		// so every wind direction finds components close to it and the pattern never looks regular.
		const double Ratio = std::pow(kMaxFrequency / kMinFrequency, 1.0 / kWaveBands);
		for (int B = 0; B < kWaveBands; ++B)
		{
			const double F0 = kMinFrequency * std::pow(Ratio, B);
			const double F1 = F0 * Ratio;
			BandWidth[B] = F1 - F0;
			const double Offset = Rand() * 2.0 * kPi;
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				FWaveComponent& C = Components[B * kWaveDirectionsPerBand + D];
				const double F = F0 + (F1 - F0) * (0.2 + 0.6 * Rand());
				const double Omega = 2.0 * kPi * F;
				const double K = Omega * Omega / kGravity;
				const double Dir = Offset + D * 2.0 * kPi / kWaveDirectionsPerBand + (Rand() - 0.5) * 0.6;
				C.Kx = K * std::cos(Dir);
				C.Ky = K * std::sin(Dir);
				C.Omega = Omega;
				C.Phase = Rand() * 2.0 * kPi;
				C.Amplitude = 0.0;
			}
			BandFrequency[B] = std::sqrt(F0 * F1);
		}
		for (double& A : TargetAmplitude) A = 0.0;
	}

	double FWaveField::TargetSignificantHeight(double WindMs, double FetchMeters)
	{
		if (WindMs < 0.5) return 0.0;
		const double U2 = WindMs * WindMs;
		const double Dimensionless = std::min(0.0016 * std::sqrt(kGravity * FetchMeters / U2), 0.243);
		return Dimensionless * U2 / kGravity;
	}

	double FWaveField::TargetPeakPeriod(double WindMs, double FetchMeters)
	{
		if (WindMs < 0.5) return 1.0;
		const double U2 = WindMs * WindMs;
		const double Dimensionless = std::min(0.286 * std::cbrt(kGravity * FetchMeters / U2), 8.13);
		return std::max(Dimensionless * WindMs / kGravity, 0.6);
	}

	void FWaveField::SetWind(const FWaveParams& InParams)
	{
		const uint32_t Seed = Params.Seed;
		Params = InParams;
		Params.Seed = Seed;
		ComputeTargetAmplitudes();
	}

	void FWaveField::ComputeTargetAmplitudes()
	{
		const double U = Params.WindSpeedKnots * kKnot;
		const double Hs = TargetSignificantHeight(U, Params.FetchMeters);
		const double Tp = TargetPeakPeriod(U, Params.FetchMeters);
		const double Fp = 1.0 / Tp;
		// Waves travel downwind.
		const double TravelDir = Params.WindFromDegrees * kDegToRad + kPi;

		// JONSWAP shape (gamma 3.3), scaled afterwards so the discrete sum has exactly the target Hs.
		auto Jonswap = [Fp](double F)
		{
			const double Sigma = F <= Fp ? 0.07 : 0.09;
			const double R = std::exp(-(F - Fp) * (F - Fp) / (2.0 * Sigma * Sigma * Fp * Fp));
			return std::pow(F, -5.0) * std::exp(-1.25 * std::pow(Fp / F, 4.0)) * std::pow(3.3, R);
		};

		double Variance = 0.0;
		for (int B = 0; B < kWaveBands; ++B)
		{
			const double BandEnergy = Jonswap(BandFrequency[B]) * BandWidth[B];
			// cos^2 spreading over the band's directions, normalized within the band.
			double Weights[kWaveDirectionsPerBand];
			double Sum = 0.0;
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				const FWaveComponent& C = Components[B * kWaveDirectionsPerBand + D];
				const double Rel = WrapAngle(std::atan2(C.Ky, C.Kx) - TravelDir);
				const double W = std::fabs(Rel) < kPi * 0.5 ? std::pow(std::cos(Rel), 2.0) : 0.0;
				Weights[D] = W;
				Sum += W;
			}
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				const double E = Sum > 1e-9 ? BandEnergy * Weights[D] / Sum : 0.0;
				TargetAmplitude[B * kWaveDirectionsPerBand + D] = std::sqrt(2.0 * E);
				Variance += E;
			}
		}
		// Scale to the target significant height: Hs = 4 sqrt(variance).
		const double Scale = Variance > 1e-12 ? (Hs / 4.0) / std::sqrt(Variance) : 0.0;
		for (double& A : TargetAmplitude) A *= Scale;
	}

	double FWaveField::GrowthSeconds(double PeriodSeconds)
	{
		return Clamp(8.0 * PeriodSeconds * PeriodSeconds, 5.0, 300.0);
	}

	void FWaveField::Update(double Dt)
	{
		for (int B = 0; B < kWaveBands; ++B)
		{
			// Exponential approach, exact for any step.
			const double T = 1.0 - std::exp(-std::max(Dt, 0.0) / GrowthSeconds(1.0 / BandFrequency[B]));
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				const int I = B * kWaveDirectionsPerBand + D;
				Components[I].Amplitude += (TargetAmplitude[I] - Components[I].Amplitude) * T;
			}
		}
		bBandsDirty = true;
	}

	void FWaveField::SnapToTarget()
	{
		for (int I = 0; I < kWaveComponents; ++I)
		{
			Components[I].Amplitude = TargetAmplitude[I];
		}
		bBandsDirty = true;
	}

	double FWaveField::Height(double X, double Y, double T) const
	{
		double H = 0.0;
		for (const FWaveComponent& C : Components)
		{
			if (C.Amplitude > 1e-6)
			{
				H += C.Amplitude * std::sin(C.Kx * X + C.Ky * Y - C.Omega * T + C.Phase);
			}
		}
		if (Ocean) H += Ocean->Height(X, Y, T);
		return H;
	}

	void FWaveField::Sample(double X, double Y, double T, double& OutHeight, double& OutVerticalVelocity, double& OutSlopeX, double& OutSlopeY) const
	{
		OutHeight = OutVerticalVelocity = OutSlopeX = OutSlopeY = 0.0;
		for (const FWaveComponent& C : Components)
		{
			if (C.Amplitude <= 1e-6) continue;
			const double Arg = C.Kx * X + C.Ky * Y - C.Omega * T + C.Phase;
			const double S = std::sin(Arg), Co = std::cos(Arg);
			OutHeight += C.Amplitude * S;
			OutVerticalVelocity += -C.Amplitude * C.Omega * Co;
			OutSlopeX += C.Amplitude * C.Kx * Co;
			OutSlopeY += C.Amplitude * C.Ky * Co;
		}
		if (Ocean)
		{
			double H, Vz, Sx, Sy;
			Ocean->Sample(X, Y, T, H, Vz, Sx, Sy);
			OutHeight += H;
			OutVerticalVelocity += Vz;
			OutSlopeX += Sx;
			OutSlopeY += Sy;
		}
	}

	double FWaveField::SignificantHeight() const
	{
		double Variance = 0.0;
		for (const FWaveComponent& C : Components) Variance += 0.5 * C.Amplitude * C.Amplitude;
		if (Ocean) Variance += Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
		return 4.0 * std::sqrt(Variance);
	}

	double FWaveField::MeanDirection() const
	{
		double X = 0.0, Y = 0.0;
		for (const FWaveComponent& C : Components)
		{
			const double K = std::sqrt(C.Kx * C.Kx + C.Ky * C.Ky);
			const double E = C.Amplitude * C.Amplitude;
			if (K > 0.0) { X += E * C.Kx / K; Y += E * C.Ky / K; }
		}
		if (Ocean)
		{
			const double E = 2.0 * Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
			X += E * std::cos(Ocean->MeanDirection());
			Y += E * std::sin(Ocean->MeanDirection());
		}
		return std::atan2(Y, X);
	}
}

namespace Sailing
{
	double FWaveField::MeanPeriod() const
	{
		double E = 0.0, EW = 0.0;
		for (const FWaveComponent& C : Components)
		{
			const double Energy = C.Amplitude * C.Amplitude;
			E += Energy;
			EW += Energy * C.Omega;
		}
		if (Ocean && Ocean->MeanPeriod() > 0.0)
		{
			const double Energy = 2.0 * Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
			E += Energy;
			EW += Energy * 2.0 * kPi / Ocean->MeanPeriod();
		}
		return EW > 1e-12 ? 2.0 * kPi * E / EW : 1.0;
	}

	const std::vector<FWaveBand>& FWaveField::Bands() const
	{
		std::lock_guard<std::mutex> Lock(BandLock.M);
		const uint64_t OceanGeneration = Ocean ? Ocean->GetGeneration() : ~1ull;
		if (!bBandsDirty && OceanGeneration == BandOceanGeneration) return BandCache;
		bBandsDirty = false;
		BandOceanGeneration = OceanGeneration;
		BandCache.clear();
		for (const FWaveComponent& C : Components)
		{
			if (C.Amplitude <= 1e-6) continue;
			FWaveBand B;
			const double K = std::sqrt(C.Kx * C.Kx + C.Ky * C.Ky);
			B.Wavelength = 2.0 * kPi / std::max(K, 1e-6);
			B.Variance = 0.5 * C.Amplitude * C.Amplitude;
			B.Direction = std::atan2(C.Ky, C.Kx);
			BandCache.push_back(B);
		}
		if (Ocean) BandCache.insert(BandCache.end(), Ocean->Bands().begin(), Ocean->Bands().end());
		return BandCache;
	}
}
