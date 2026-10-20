#include "Storm.h"
#include "CloudSky.h"
#include "SailingMath.h"

namespace Sailing
{
	// ---------------------------------------------------------------- microburst (Vicroy 1991)

	double FMicroburst::Lambda() const
	{
		// Vicroy eq. A1: the scale factor that puts PeakOutflowMs at (rp, zm).
		return 2.0 * PeakOutflowMs / (PeakRadiusM * (std::exp(C1) - std::exp(C2)) * std::exp(1.0 / (2.0 * Alpha)));
	}

	void FMicroburst::At(double Dx, double Dy, double Z, double& OutU, double& OutV, double& OutW) const
	{
		OutU = OutV = OutW = 0.0;
		if (PeakOutflowMs <= 0.0 || PeakRadiusM <= 0.0 || PeakHeightM <= 0.0) return;
		const double L = Lambda();
		const double Zn = std::max(Z, 0.0) / PeakHeightM;
		const double R2 = Dx * Dx + Dy * Dy;
		// (r / rp)^(2 alpha), and the radial shape e^((2 - that) / (2 alpha)) (eqs. A4 to A6).
		const double Q = std::pow(R2 / (PeakRadiusM * PeakRadiusM), Alpha);
		const double Radial = std::exp((2.0 - Q) / (2.0 * Alpha));
		const double P = std::exp(C1 * Zn) - std::exp(C2 * Zn);
		OutU = 0.5 * L * Dx * P * Radial;
		OutV = 0.5 * L * Dy * P * Radial;
		const double Qz = PeakHeightM / C1 * (std::exp(C1 * Zn) - 1.0) - PeakHeightM / C2 * (std::exp(C2 * Zn) - 1.0);
		OutW = -L * Qz * (1.0 - 0.5 * Q) * Radial;
	}

	double FMicroburst::UpdraftRadius() const
	{
		// w changes sign where (r / rp)^(2 alpha) = 2.
		return PeakRadiusM * std::pow(2.0, 1.0 / (2.0 * Alpha));
	}

	// ---------------------------------------------------------------- cold pool

	double FColdPool::FrontSpeed(double DeltaC, double DepthM, double AirC, double AmbientAlongMs)
	{
		const double Reduced = kGravity * std::max(DeltaC, 0.0) / (AirC + 273.15);
		return kFroude * std::sqrt(Reduced * std::max(DepthM, 0.0)) + kAmbientShare * AmbientAlongMs;
	}

	// ---------------------------------------------------------------- rain

	double FStormRain::LeadingEdge(double AltitudeM)
	{
		// Aloft the curtain hangs from the core's front; toward the water the outflow sweeps it forward into the foot.
		return -FStormShape::CoreBehindM + FootReachM * std::exp(-std::max(AltitudeM, 0.0) / FootHeightM);
	}

	double FStormRain::LateralMask(double AlongFrontM)
	{
		// The weather map's storm channel (FWeatherMap::Paint): a cell some 35 km long along the front.
		return 1.0 - SmoothStep(14000.0, 20000.0, std::fabs(AlongFrontM));
	}

	double FStormRain::RateAt(double DistanceAheadM, double AltitudeM, double AlongFrontM)
	{
		const double Behind = LeadingEdge(AltitudeM) - DistanceAheadM; // m inside the rain
		if (Behind < -EdgeWidthM) return 0.0;
		const double Edge = SmoothStep(-0.5 * EdgeWidthM, 0.5 * EdgeWidthM, Behind);
		// Heaviest just inside the edge (the downdraft core), easing back through the core into trailing rain.
		const double Core = std::exp(-std::max(Behind - 600.0, 0.0) / (0.5 * CoreLengthM));
		const double Trail = TrailMmPerHour * (1.0 - SmoothStep(CoreLengthM, TrailLengthM, Behind));
		// Shafts along the front, a kilometre or two apart (the cloud material's are similar), heavier and lighter.
		const double Shafts = 0.7 + 0.3 * std::sin(AlongFrontM / 1300.0 + 0.6 * std::sin(AlongFrontM / 3100.0));
		return Edge * std::max(PeakMmPerHour * Core * Shafts, Trail) * LateralMask(AlongFrontM);
	}

	double FStormRain::Amount(double MmPerHour)
	{
		// The eye reads rain roughly by the square root of its rate: moderate rain (7.6 mm/h) about 0.4, heavy (25) 0.7.
		return MmPerHour <= 0.0 ? 0.0 : std::sqrt(std::min(MmPerHour / 50.0, 1.0));
	}

	// ---------------------------------------------------------------- squall line (prologue step 4)

	double FSquallLine::Inside(double DistanceAheadM) const
	{
		const double Behind = LeadM - DistanceAheadM; // m inside the rain
		const double Edge = SmoothStep(-0.5 * EdgeWidthM, 0.5 * EdgeWidthM, Behind);
		return Edge * (1.0 - SmoothStep(BandLengthM, 2.0 * BandLengthM, Behind));
	}

	double FSquallLine::RateAt(double DistanceAheadM) const
	{
		// Heaviest at the edge, easing back through the band.
		const double Behind = std::max(LeadM - DistanceAheadM, 0.0);
		return PeakMmPerHour * Inside(DistanceAheadM) * (1.0 - 0.4 * std::min(Behind / BandLengthM, 1.0));
	}
}
