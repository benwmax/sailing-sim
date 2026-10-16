#pragma once

#include "CoreMinimal.h"
#include "SailingSettings.h"

/**
 * Visual V1: the rendering pipeline per quality tier and the physical camera (see docs/visual-1/README.md).
 *
 * Tiers. Low keeps the Phase 8 look and cost (engine scalability Medium: no Lumen, shadow maps, TSR). Medium turns on
 * Lumen with software ray tracing, virtual shadow maps and a temporal upscale; High adds hardware ray tracing for
 * Lumen and renders at native resolution. Ray tracing is compiled in (r.RayTracing, on demand) but only enabled at
 * runtime on High, so the lower tiers pay nothing for it.
 *
 * Camera. On Medium and High exposure follows the light the way a hand-held incident meter does, not the frame: the
 * illuminance at the boat comes from the sun's elevation (clear-sky direct and diffuse), the cloud state, twilight
 * and the moon; EV100 = log2(E / 2.5) (C = 250, ISO 100: 15.5 in full sun, 12-13 under overcast). The eye and the
 * camera adapt only part of the way to gloom, so a storm or the night still reads dark. The scene's lights are not in
 * real lux (the sun is 10), so the metered EV is shifted by a fixed calibration (SceneEVOffset) measured against the
 * Phase 8 auto exposure on a clear noon. The histogram may still move +-0.7 EV around the metered value for framing
 * (into the sun, under the sail).
 */
struct FQualityCVar
{
	const TCHAR* Name;
	float Value;
};

/** The engine scalability level each tier uses (Low = 1, Medium = 2, High = 3). */
SAILINGSIM_API int32 QualityScalabilityLevel(ESailingQuality Quality);

/** The global illumination (Lumen) scalability level per tier: High uses Lumen's High gather with hardware ray
 *  tracing rather than Epic's (Epic's final gather costs 5.5 ms at native on the M5 Pro; see docs/visual-1). */
SAILINGSIM_API int32 QualityGIScalabilityLevel(ESailingQuality Quality);

/** Every console variable a tier sets (ApplyQualitySettings applies them after the scalability level). */
SAILINGSIM_API TArray<FQualityCVar> QualityCVars(ESailingQuality Quality);

/** Medium and High use the physical camera and the V1 look; Low keeps the Phase 8 exposure and post. */
SAILINGSIM_API bool UsesPhysicalCamera(ESailingQuality Quality);

/** Graphics G8: whether the cinematic look applies (Medium and above): -SailingCinematic=0|1 decides when given,
 *  otherwise the Settings toggle or photo mode. Capture mode stays neutral unless asked: its stills are compared with
 *  real photographs. */
SAILINGSIM_API bool UsesCinematicLook(ESailingQuality Quality, bool bSettingOn, bool bPhotoMode, bool bCaptureMode);

/** Horizontal illuminance at the water (real lux) from the sun (elevation deg, cloud shade of its direct light 0..1,
 *  cloud darkness 0..1) and the moon (elevation deg, lit fraction 0..1). Twilight follows the civil and nautical
 *  curve below the horizon; a starlit floor of 0.001 lux. */
SAILINGSIM_API double SceneIlluminanceLux(double SunElevationDeg, double CloudShade, double CloudDarkness, double MoonElevationDeg = -90.0, double MoonLit = 0.0);

/** Incident-meter exposure for an illuminance: EV100 = log2(E * 100 / 250). */
SAILINGSIM_API double MeteredEV100(double Lux);

/** The exposure the game sets (EV100 in scene units): the metered EV, moved part of the way back toward the clear-sky
 *  EV for the same sun (no full adaptation to gloom), shifted into scene units and held above the night floor. */
SAILINGSIM_API double CameraEV100(double SunElevationDeg, double CloudShade, double CloudDarkness, double MoonElevationDeg, double MoonLit, double NightFloorEV);

/** The scene-units offset: real EV100 minus the EV100 the scene needs for the same picture (calibrated, see .cpp). */
SAILINGSIM_API double SceneEVOffset();
