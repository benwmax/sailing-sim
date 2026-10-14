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
	return Quality == ESailingQuality::Low ? 1 : (Quality == ESailingQuality::Medium ? 2 : (Quality == ESailingQuality::High ? 3 : 4));
}

int32 QualityGIScalabilityLevel(ESailingQuality Quality)
{
	return Quality == ESailingQuality::Low ? 1 : (Quality == ESailingQuality::Ultra ? 3 : 2);
}

TArray<FQualityCVar> QualityCVars(ESailingQuality Quality)
{
	TArray<FQualityCVar> V;
	const bool bLow = Quality == ESailingQuality::Low, bUltra = Quality == ESailingQuality::Ultra;
	const bool bHigh = Quality == ESailingQuality::High || bUltra;   // Ultra has everything High has, and more
	// Volumetric clouds are the most expensive part of the sky: cap their ray-march samples per tier.
	V.Add({ TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), bLow ? 48.f : (bUltra ? 160.f : (bHigh ? 80.f : 72.f)) });
	V.Add({ TEXT("r.VolumetricCloud.ReflectionRaySampleMaxCount"), bUltra ? 48.f : (bHigh ? 24.f : 16.f) });
	// Graphics G1: Ultra traces the clouds at half resolution (mode 1) instead of a quarter rebuilt over frames (mode 0):
	// the cleanest edges, about four times the tracing (a desktop GPU's budget, not the Mac's).
	V.Add({ TEXT("r.VolumetricRenderTarget.Mode"), bUltra ? 1.f : 0.f });
	// Graphics G1: the reconstruction that kept the grain: bilinear upsampling with jitter keeping the closest sample (3)
	// and the reprojected history clamped to the new samples' neighbourhood measured 60% less high-frequency noise in a
	// storm sky than the defaults (bilateral, unclamped), with no halo on the rig against the sky.
	if (!bLow)
	{
		V.Add({ TEXT("r.VolumetricRenderTarget.UpsamplingMode"), 3.f });
		V.Add({ TEXT("r.VolumetricRenderTarget.ReprojectionBoxConstraint"), 1.f });
	}
	// Visual V5: the volumetric fog that carries the sun's shafts is coarse on Medium, finer on High. (Longer strides
	// through empty sky, r.VolumetricCloud.StepSizeOnZeroConservativeDensity, sparkled: left at 1.)
	V.Add({ TEXT("r.VolumetricFog.GridPixelSize"), bUltra ? 4.f : (bHigh ? 8.f : 16.f) });
	V.Add({ TEXT("r.VolumetricFog.GridSizeZ"), bUltra ? 128.f : (bHigh ? 96.f : 64.f) });
		// Shadows: virtual shadow maps from Medium up (crisp rig and sail shadows on the deck); Low keeps cascades.
	V.Add({ TEXT("r.Shadow.Virtual.Enable"), bLow ? 0.f : 1.f });
	// Ray tracing is compiled in on demand; only High turns it on, for Lumen's hardware ray tracing.
	V.Add({ TEXT("r.RayTracing.Enable"), bHigh ? 1.f : 0.f });
	V.Add({ TEXT("r.Lumen.HardwareRayTracing"), bHigh ? 1.f : 0.f });
	// Visual V6: MegaLights on High shadows the night's street, dock and waterfront lights (ANightLightsActor) at a fixed
	// cost; Medium lights them unshadowed.
	V.Add({ TEXT("r.MegaLights.EnableForProject"), bHigh ? 1.f : 0.f });
	// Graphics G3: the crew's hair. On the Mac (cards: no strand geometry on its shader platform) the hair voxelization,
	// which lights and shadows strands through each other, costs about 1 ms with the crew in view and adds nothing to
	// cards: off (the helm's-eye view went from 44 to 45 fps on High). Windows keeps it for the strands.
#if PLATFORM_MAC
	V.Add({ TEXT("r.HairStrands.Voxelization"), 0.f });
#endif
	// Single Layer Water (Visual V4, Medium and High): its reflections traced at half resolution and denoised.
	V.Add({ TEXT("r.Water.SingleLayer.Reflection.DownsampleFactor"), bLow ? 1.f : 2.f });
	// Anti-aliasing and resolution: Medium renders at 67% and upscales temporally; High renders at native.
	// (0 = none, 2 = TAA, 4 = TSR, 5 = SMAA.) MetalFX is not in this engine build; see docs/visual-1/README.md.
	if (!bLow)
	{
		// Ultra (a desktop GPU) takes TSR at native resolution: the cleanest image, too costly on the Mac.
		V.Add({ TEXT("r.AntiAliasingMethod"), bUltra ? 4.f : 2.f });
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
