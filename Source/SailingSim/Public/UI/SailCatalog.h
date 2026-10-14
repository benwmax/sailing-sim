#pragma once

#include "CoreMinimal.h"

/**
 * Graphics G4: what the front end offers (ui-spec.md 2.5), read from the game's own data rather than typed: launch spots
 * from each world's bake (Content/TerrainData/<World>.json), boat figures from the physics configs and reference polars.
 * Only the words (descriptions, taglines, handling ratings) are written here.
 */
namespace SailCatalog
{
	struct FSpot
	{
		FString Name, Detail, Tag, StartType;
		double North = 0.0, East = 0.0, Heading = 0.0;
	};

	struct FWorld
	{
		int32 Index = 0;           // the game's world index (0 lake, 1 Galveston Bay)
		FString File, Name, Tagline, Description;
		TArray<TPair<FString, FString>> Facts;   // value, label
		TArray<FSpot> Spots;
		double GridNorth = 0.0, GridEast = 0.0, GridHeightM = 1.0, GridWidthM = 1.0;   // the map image's extent
		bool bTidal = false;
		FString MapTexture, CardTexture, TitleTexture;
		TArray<FString> LoadingTextures;
	};

	struct FBoat
	{
		int32 Type = 0;
		FString Name, TypeLine, Description;
		TArray<FString> Flags;
		FString Length, Beam, Draft, Weight, CloseHauled;
		int32 Handling = 3;        // 1 easy .. 5 demanding (a designer rating)
		bool bDinghy = false, bMultihull = false;
		float ReefKn = 18.f, ComfortKn = 12.f;   // the "what to expect" bands
	};

	SAILINGSIM_API const TArray<FWorld>& Worlds();
	SAILINGSIM_API const FWorld& World(int32 Index);
	SAILINGSIM_API const TArray<FBoat>& Boats();
	SAILINGSIM_API const FBoat& Boat(int32 Type);
	SAILINGSIM_API FString FeetInches(double Meters);
	/** "What to expect" for the conditions panel (ui-spec.md 5.5). */
	SAILINGSIM_API FString Expect(float WindKn, float GustKn, int32 Sky, float Hour, int32 Month, int32 Day, int32 BoatType, int32 World);
	/** Sunset (local clock hour) for a date at a world's latitude. */
	SAILINGSIM_API float SunsetHour(int32 Month, int32 Day, int32 World);
	SAILINGSIM_API FString ClockText(float Hour);
	SAILINGSIM_API FString MonthName(int32 Month);
}
