#include "VisualPipeline.h"

namespace
{
	// Calibrated on a clear noon at Ray Hubbard (Visual V1): the Phase 8 histogram exposure of the beam8 view, matched
	// by mean screen luminance with -SailingEV. See docs/visual-1/README.md.
	constexpr double kSceneEVOffset = 14.1;
	// How far the exposure follows the light into gloom: 1 = a camera's meter (a storm comes out mid-grey), 0 = fixed.
	constexpr double kGloomAdaptation = 0.1;
}

int32 QualityScalabilityLevel(ESailingQuality Quality)
{
	return Quality == ESailingQuality::Low ? 1 : (Quality == ESailingQuality::Medium ? 2 : 3);
}

int32 QualityGIScalabilityLevel(ESailingQuality Quality)
{
	return Quality == ESailingQuality::Low ? 1 : 2;
}

TArray<FQualityCVar> QualityCVars(ESailingQuality Quality)
{
	TArray<FQualityCVar> V;
	const bool bLow = Quality == ESailingQuality::Low, bHigh = Quality == ESailingQuality::High;
	// Volumetric clouds are the most expensive part of the sky: cap their ray-march samples per tier.
	V.Add({ TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), bLow ? 48.f : (bHigh ? 80.f : 72.f) });
	V.Add({ TEXT("r.VolumetricCloud.ReflectionRaySampleMaxCount"), bHigh ? 24.f : 16.f });
	// Shadows: virtual shadow maps from Medium up (crisp rig and sail shadows on the deck); Low keeps cascades.
	V.Add({ TEXT("r.Shadow.Virtual.Enable"), bLow ? 0.f : 1.f });
	// Ray tracing is compiled in on demand; only High turns it on, for Lumen's hardware ray tracing.
	V.Add({ TEXT("r.RayTracing.Enable"), bHigh ? 1.f : 0.f });
	V.Add({ TEXT("r.Lumen.HardwareRayTracing"), bHigh ? 1.f : 0.f });
	// Single Layer Water (Visual V4, Medium and High): its reflections traced at half resolution and denoised.
	V.Add({ TEXT("r.Water.SingleLayer.Reflection.DownsampleFactor"), bLow ? 1.f : 2.f });
	// Anti-aliasing and resolution: Medium renders at 67% and upscales temporally; High renders at native.
	// (0 = none, 2 = TAA, 4 = TSR, 5 = SMAA.) MetalFX is not in this engine build; see docs/visual-1/README.md.
	if (!bLow)
	{
		V.Add({ TEXT("r.AntiAliasingMethod"), bHigh ? 2.f : 2.f });
		V.Add({ TEXT("r.TemporalAA.Upsampling"), 1.f });
		V.Add({ TEXT("r.ScreenPercentage"), bHigh ? 100.f : 67.f });
	}
	return V;
}

bool UsesPhysicalCamera(ESailingQuality Quality)
{
	return Quality != ESailingQuality::Low;
}

double SceneIlluminanceLux(double SunElevationDeg, double CloudShade, double CloudDarkness, double MoonElevationDeg, double MoonLit)
{
	double Sun = 0.0;
	if (SunElevationDeg > 0.0)
	{
		const double S = FMath::Sin(FMath::DegreesToRadians(SunElevationDeg));
		// Direct beam through the air mass (Kasten's 1/sin with a floor near the horizon) and the clear-sky diffuse.
		const double Direct = 127500.0 * S * FMath::Exp(-0.21 / FMath::Max(S, 0.03));
		const double Diffuse = 16000.0 * FMath::Pow(S, 0.6);
		Sun = Direct * FMath::Clamp(CloudShade, 0.0, 1.0) + Diffuse * FMath::Lerp(1.0, 0.25, FMath::Clamp(CloudDarkness, 0.0, 1.0));
	}
	// Twilight: about 400 lux at sunset falling a decade per 2.5 deg (civil twilight ends near 3 lux, nautical near 0.01).
	const double Twilight = SunElevationDeg > -18.0 ? FMath::Pow(10.0, 2.6 + 0.4 * FMath::Min(SunElevationDeg, 0.0)) * (SunElevationDeg > 0.0 ? FMath::Exp(-SunElevationDeg / 2.0) : 1.0) : 0.0;
	const double Moon = MoonElevationDeg > 0.0 ? 0.25 * FMath::Clamp(MoonLit, 0.0, 1.0) * FMath::Sin(FMath::DegreesToRadians(MoonElevationDeg)) : 0.0;
	return Sun + Twilight * FMath::Lerp(1.0, 0.3, FMath::Clamp(CloudDarkness, 0.0, 1.0)) + Moon + 0.001;
}

double MeteredEV100(double Lux)
{
	return FMath::Log2(FMath::Max(Lux, 1e-6) * 100.0 / 250.0);
}

double SceneEVOffset()
{
	return kSceneEVOffset;
}

double CameraEV100(double SunElevationDeg, double CloudShade, double CloudDarkness, double MoonElevationDeg, double MoonLit, double NightFloorEV)
{
	const double Metered = MeteredEV100(SceneIlluminanceLux(SunElevationDeg, CloudShade, CloudDarkness, MoonElevationDeg, MoonLit));
	const double Clear = MeteredEV100(SceneIlluminanceLux(SunElevationDeg, 1.0, 0.0, MoonElevationDeg, MoonLit));
	// Under cloud the exposure opens only part of the way: the gloom stays visible.
	const double Real = Metered + (1.0 - kGloomAdaptation) * FMath::Max(Clear - Metered, 0.0);
	return FMath::Max(Real - kSceneEVOffset, NightFloorEV);
}
