#pragma once

#include "CoreMinimal.h"
#include "GeoAnchor.h"

/**
 * Graphics G4: what the front end offers (ui-spec.md 2.5), read from the game's own data rather than typed: launch spots
 * from each world's bake (Content/TerrainData/<World>.json), boat figures from the physics configs and reference polars.
 * Only the words (descriptions, taglines, handling ratings) are written here.
 */
namespace SailCatalog
{
	struct FSpot
	{
		FString Id;                // stable: the bake's "id", or the name made lower-case with dashes (SpotId)
		FString Name, Detail, Tag, StartType;
		double North = 0.0, East = 0.0, Heading = 0.0;
		/** The spot on the earth, from the world's anchor (docs/geo-anchor; rounded to 1e-8 degrees, about a millimetre):
		 *  the save's fallback when a spot id is gone. Shown nowhere yet. */
		double Lat = 0.0, Lon = 0.0;
	};

	struct FWorld
	{
		int32 Index = 0;           // the game's world index (0 lake, 1 Galveston Bay)
		FString Id;                // the save's world id (FSailSave::WorldId)
		FString File, Name, Tagline, Description;
		TArray<TPair<FString, FString>> Facts;   // value, label
		TArray<FSpot> Spots;
		double GridNorth = 0.0, GridEast = 0.0, GridHeightM = 1.0, GridWidthM = 1.0;   // the map image's extent
		bool bTidal = false;
		Sailing::FGeoAnchor Anchor;   // the bake's projection (FLakeData::Anchor without loading the terrain)
		FString MapTexture, CardTexture, TitleTexture;
		TArray<FString> LoadingTextures;
	};

	struct FBoat
	{
		int32 Type = 0;
		FString Name, TypeLine, Description;
		TArray<FString> Flags;
		FString Length, Beam, Draft, Weight, CloseHauled;
		float LengthM = 0.f, BeamM = 0.f, WeightKg = 0.f, CloseHauledKn = 0.f;   // the same as numbers (the showroom's bars)
		int32 Handling = 3;        // 1 easy .. 5 demanding (a designer rating)
		bool bDinghy = false, bMultihull = false;
		float ReefKn = 18.f, ComfortKn = 12.f;   // the "what to expect" bands
	};

	SAILINGSIM_API const TArray<FWorld>& Worlds();
	SAILINGSIM_API const FWorld& World(int32 Index);
	/** The HUD minimap for a settings world (0 lake, 1 Galveston Bay, 2 the Gulf passage): its texture and grid extent. */
	struct FMiniMap
	{
		FString Texture;
		double GridNorth = 0.0, GridEast = 0.0, GridHeightM = 1.0, GridWidthM = 1.0, SpanM = 3000.0;
	};
	SAILINGSIM_API const FMiniMap& MiniMap(int32 SettingsWorld);
	/** A settings world's launch spot ids (0 lake, 1 Galveston Bay, 2 the Gulf passage), in the bake's order. */
	SAILINGSIM_API const TArray<FString>& SpotIds(int32 SettingsWorld);
	/** A settings world's launch spots (ids, map position, lat/lon) and its anchor, read from the bake header alone. */
	SAILINGSIM_API const TArray<FSpot>& Spots(int32 SettingsWorld);
	SAILINGSIM_API const Sailing::FGeoAnchor& Anchor(int32 SettingsWorld);
	/** "Rush Creek Yacht Club" -> "rush-creek-yacht-club". */
	SAILINGSIM_API FString SpotId(const FString& Name);
	SAILINGSIM_API const TArray<FBoat>& Boats();
	SAILINGSIM_API const FBoat& Boat(int32 Type);
	SAILINGSIM_API FString FeetInches(double Meters);
	/** "What to expect" for the conditions panel (ui-spec.md 5.5). */
	SAILINGSIM_API FString Expect(float WindKn, float GustKn, int32 Sky, float Hour, int32 Month, int32 Day, int32 BoatType, int32 World);
	/** Sunset (local clock hour) for a date at a world's latitude. */
	SAILINGSIM_API float SunsetHour(int32 Month, int32 Day, int32 World);
	SAILINGSIM_API FString ClockText(float Hour);
	SAILINGSIM_API FString MonthName(int32 Month);

	/** W5b: a baked real day (Content/TerrainData/Weather/<date>.wxday, Tools/weather): Lake Ray Hubbard only. */
	struct FRealDay
	{
		FString Date, Title, Summary;
		float StartHour = 15.f;
		int32 Month = 6, Day = 1;
		bool bStorm = false;
	};
	SAILINGSIM_API const TArray<FRealDay>& RealDays();

	/**
	 * Release readiness (docs/licences): the credits screen's text, from CREDITS.md (the single source; staged into the
	 * package by SailingSim.Build.cs). The Unreal Engine notice comes first, then every heading and paragraph in order,
	 * with the Markdown reduced to plain text.
	 */
	enum class ECreditKind : uint8 { Notice, Heading1, Heading2, Heading3, Paragraph, Bullet };
	struct FCreditLine
	{
		ECreditKind Kind = ECreditKind::Paragraph;
		FString Text;
	};
	SAILINGSIM_API extern const TCHAR* const UnrealNotice;
	SAILINGSIM_API FString CreditsPath();
	SAILINGSIM_API TArray<FCreditLine> ParseCredits(const FString& Markdown);
	/** CREDITS.md read now (a few kB), or the notice and a missing-file line. */
	SAILINGSIM_API TArray<FCreditLine> Credits();
}
