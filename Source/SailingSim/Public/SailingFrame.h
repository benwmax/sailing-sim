#pragma once

#include "CoreMinimal.h"

class UWorld;

/**
 * World streaming (Wide World Rendering PR 2, docs/world-streaming): the render frame. The physics lives in the world's map
 * frame (metres, +X north, +Y east, doubles; FGeoAnchor gives lat/lon beside it) and never moves. Unreal draws in a frame
 * whose origin follows the boat: ASailingGameMode moves it with UWorld::SetNewWorldOrigin when she has sailed kRecentreM
 * from it (WorldStream.h), and the engine shifts every actor, component and primitive by the same offset in one frame.
 *
 * So an Unreal world position is (map metres x 100) - the world's OriginLocation (cm), and everything that turns map metres
 * into Unreal positions or back goes through these. Geometry built in an actor's own space, on an actor that sits at the
 * map's origin (its location ToWorld(0, 0, z)), needs nothing: the shift moves the actor.
 */
namespace SailingFrame
{
	/** The render origin in the map frame (cm, absolute): zero until the first re-centre. */
	SAILINGSIM_API FVector OriginCm(const UWorld* World);
	/** The render origin in the map frame (m). */
	inline FVector2D OriginM(const UWorld* World) { const FVector O = OriginCm(World); return FVector2D(O.X, O.Y) / 100.0; }

	/** Map metres (north, east, up) to an Unreal world position (cm). */
	inline FVector ToWorld(const UWorld* World, double NorthM, double EastM, double UpM)
	{
		const FVector O = OriginCm(World);
		return FVector(NorthM * 100.0 - O.X, EastM * 100.0 - O.Y, UpM * 100.0 - O.Z);
	}
	/** An Unreal world position (cm) to map metres (north, east). */
	inline FVector2D ToMap(const UWorld* World, const FVector& WorldCm)
	{
		const FVector O = OriginCm(World);
		return FVector2D((WorldCm.X + O.X) / 100.0, (WorldCm.Y + O.Y) / 100.0);
	}
	/** An Unreal world position (cm) to the map frame in cm (north, east, up): ToMap without the metres. */
	inline FVector ToMapCm(const UWorld* World, const FVector& WorldCm) { return WorldCm + OriginCm(World); }
	/** A map-frame position in cm to Unreal (the inverse of ToMapCm). */
	inline FVector FromMapCm(const UWorld* World, const FVector& MapCm) { return MapCm - OriginCm(World); }
	/** Instance transforms made in the map frame (cm), moved into the render frame in place: for the world-space adds and
	 *  updates of instanced meshes (AddInstances(..., bWorldSpace = true)). */
	inline TArray<FTransform>& ToWorldTransforms(const UWorld* World, TArray<FTransform>& Transforms)
	{
		const FVector O = OriginCm(World);
		if (!O.IsZero()) for (FTransform& T : Transforms) T.AddToTranslation(-O);
		return Transforms;
	}
	/** Where an actor that builds its geometry in map coordinates (cm) sits: the map's origin, at height UpM. */
	inline FVector MapAnchor(const UWorld* World, double UpM = 0.0) { return ToWorld(World, 0.0, 0.0, UpM); }
}
