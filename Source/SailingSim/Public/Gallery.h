#pragma once

#include "CoreMinimal.h"
#include "UObject/SoftObjectPath.h"

class UWorld;

/**
 * The developer-only asset gallery (docs/gallery-core/, Inputs/gallery/brief.md G1): what it lists, read from the asset
 * registry when it opens (never a hand-kept list), and the graphics snapshot it restores. The screen is the PC's (G2);
 * the stage is AGalleryStage.
 */
struct SAILINGSIM_API FGalleryItem
{
	/** The base mesh's object path (/Game/World/Trees/SM_LiveOak_0.SM_LiveOak_0), or "Boat:<type>" for a whole boat. */
	FString Key;
	FString Name, Description, Category, Folder;
	TArray<FString> Tags;
	FSoftObjectPath Mesh;
	/** Its twins, grouped under it: _Light (the kit's for AI boats) and _Far (trees' stand-ins). */
	FSoftObjectPath Light, Far;
	/** A whole boat (Sailing::EBoatType), or -1. */
	int32 BoatType = -1;
	bool bHero = false;
};

namespace SailGallery
{
	/** A mesh the registry lists: its package path ("/Game/World/Trees") and asset name ("SM_LiveOak_0"). */
	struct FAssetRef
	{
		FString PackagePath, AssetName;
	};

	/** The categories, in the screen's order ("Other" last: a mesh in a folder the table doesn't name). */
	SAILINGSIM_API const TArray<FString>& Categories();
	/** The folders listed (recursively) and the ones left out (baked terrain and marina tiles, the boats' parts). */
	SAILINGSIM_API const TArray<FString>& RootFolders();
	SAILINGSIM_API bool IsExcluded(const FString& PackagePath);
	/** The folder table: a package path's category and default tags; "Other" for a folder it doesn't name. */
	SAILINGSIM_API FString CategoryFor(const FString& PackagePath, const FString& AssetName, TArray<FString>& OutTags);
	/** A display name: the names table's, or the asset name without SM_ with its CamelCase split ("SM_HornCleat" -> "Horn
	 *  cleat"; numbered shapes count from 1: "SM_LiveOak_0" -> "Live oak 1"). */
	SAILINGSIM_API FString DisplayName(const FString& AssetName, FString* OutDescription = nullptr);
	/** The gallery's list from a set of meshes: twins grouped under their base, the eight boats added, sorted by category
	 *  then name. OutOther is how many landed in Other. */
	SAILINGSIM_API TArray<FGalleryItem> BuildIndex(const TArray<FAssetRef>& Meshes, int32* OutOther = nullptr);
	/** The registry's static meshes under RootFolders, built into the list; logs "Gallery index: N assets, M categories,
	 *  K in Other". */
	SAILINGSIM_API TArray<FGalleryItem> ScanRegistry();
	/** The search: every word must be in the name, folder, category or a tag (any case); and the category ("All" or
	 *  empty for any) and every chosen tag must match. */
	SAILINGSIM_API bool Matches(const FGalleryItem& Item, const FString& Search, const FString& Category, const TArray<FString>& Tags);
	SAILINGSIM_API const FGalleryItem* Find(const TArray<FGalleryItem>& Items, const FString& KeyOrPath);

	/** Settings > Graphics as it was on entering the gallery: Restore puts it back (and applies it live). */
	struct SAILINGSIM_API FGraphicsSnapshot
	{
		uint8 Quality = 0;
		int32 ResolutionScale = 0, AntiAliasing = -1, ShadowQuality = -1, LightingQuality = -1, ReflectionQuality = -1, CloudQuality = -1;
		int32 WaterQuality = -1, FoliageQuality = -1, ViewDistanceQuality = -1, MotionBlur = -1;
		bool bCinematicLook = false;
		static FGraphicsSnapshot Capture();
		bool operator==(const FGraphicsSnapshot& O) const;
		bool operator!=(const FGraphicsSnapshot& O) const { return !(*this == O); }
		/** Writes them back to USailingSettings and applies them (the game mode's ApplyQualitySettings), saved or not. */
		void Restore(UWorld* World, bool bSave) const;
	};
}
