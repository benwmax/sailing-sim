#pragma once

#include "CoreMinimal.h"

/**
 * Photo mode PR 1 (docs/photo-freefly/): the free camera's limits. Distances in metres; heights above the water at rest
 * (the physics frame's Z = 0).
 */
struct SAILINGSIM_API FFreeCameraLimits
{
	/** Horizontal leash from the anchor (Bean's pick: 5 km from the player's boat). */
	double LeashM = 5000.0;
	/** Over the leash's last stretch the speed outward falls to nothing. */
	double LeashSoftM = 500.0;
	double CeilingM = 1500.0;
	/** Never under the wave at the camera plus this (wave-top shots work), nor under the ground plus TerrainClearM. */
	double WaterClearM = 0.15;
	double TerrainClearM = 0.5;
	/** The sphere swept against the visibility channel: the camera stops at hulls, docks and bridges. */
	double SweepRadiusM = 0.2;
};

/** The free camera's arithmetic, apart from the actor so the tests hold it. */
namespace FreeCameraMath
{
	/** Base speeds the speed keys step through (m/s): a walk to a fast drone, each about twice the last (camera views
	 *  slice 2: eight steps, the one you chose kept in the save). */
	inline constexpr int32 NumSpeeds = 8;
	/** The step a new camera starts on (2 m/s). */
	inline constexpr int32 DefaultSpeedIndex = 2;
	/** Orbit moves (camera views slice 2: the left stick and WASD in orbit, as in other games' photo modes): the stick's
	 *  sides go round the subject at this rate (deg/s), up and down tilt over it (deg/s), forward and back dolly in and out
	 *  by this share of the distance a second. Boost and slow scale them as they do the fly speed's, gentler. */
	inline constexpr float OrbitTurnDegPerSec = 60.f;
	inline constexpr float OrbitTiltDegPerSec = 40.f;
	inline constexpr float OrbitDollyPerSec = 1.2f;
	SAILINGSIM_API float OrbitRateScale(bool bBoost, bool bSlow);
	SAILINGSIM_API double SpeedStep(int32 Index);
	/** Shift: five times; Ctrl: a fifth. */
	SAILINGSIM_API double Speed(int32 Index, bool bBoost, bool bSlow);
	/** Fraction of the way to the target speed this frame: about 0.25 s to get there (95%), whatever the frame rate. */
	SAILINGSIM_API double EaseAlpha(double Dt, double EaseSeconds = 0.25);
	/** 1 inside the leash's soft stretch, falling to 0 at the leash. */
	SAILINGSIM_API double LeashScale(double DistM, const FFreeCameraLimits& L);
	/** The horizontal velocity the leash allows at this offset from the anchor: its outward part scaled by LeashScale. */
	SAILINGSIM_API FVector2D LeashVelocity(const FVector2D& OffsetM, const FVector2D& VelocityMps, const FFreeCameraLimits& L);
	/** An offset from the anchor pulled back onto the leash. */
	SAILINGSIM_API FVector2D ClampToLeash(const FVector2D& OffsetM, const FFreeCameraLimits& L);
	/** The lowest the camera may be: over the wave at the camera and over the ground. */
	SAILINGSIM_API double FloorM(double WaveM, double GroundM, const FFreeCameraLimits& L);
	/** A height between the floor and the ceiling (the floor wins if a hill reaches the ceiling). */
	SAILINGSIM_API double ClampHeightM(double ZM, double WaveM, double GroundM, const FFreeCameraLimits& L);
}
