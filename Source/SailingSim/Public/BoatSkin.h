#pragma once

#include "CoreMinimal.h"
#include "Misc/Optional.h"

struct FBoatLivery;

/**
 * Boat skins (docs/skins/README.md): how a boat looks, as one small JSON file a player can load and unload. A skin is a
 * list of optional sections (paint, wear, sails, lines); a section or a field that is missing leaves the boat as her
 * class has her, so a skin can change only the sails, and unloading it puts her back.
 *
 * A skin is data only and safe to take from someone else: it names colours (hex) and items the game ships (wear levels,
 * rope colourways) and nothing else; no paths, no scripts, no material recipes. The reader refuses a file over
 * MaxFileBytes, clamps every number, drops what it does not know and never fails on a field: a broken file is refused
 * whole, with a message. Skins are cosmetic: nothing here reaches SailingPhysics (online-readiness rule 1), and any
 * vessel can wear one (rule 2). Format version and string ids as the save file's (rule 7).
 */
struct SAILINGSIM_API FBoatSkin
{
	static constexpr int32 CurrentVersion = 1;
	static constexpr int32 MaxFileBytes = 64 * 1024;
	static constexpr int32 MaxNameChars = 32;
	static constexpr int32 MaxIdChars = 40;
	static constexpr int32 MaxSailDigits = 6;
	static constexpr int32 NumWearLevels = 5;

	/** The rope roles a skin can colour. */
	enum class ELine : uint8 { Mainsheet, JibPort, JibStarboard, Control, Count };

	struct FPaint
	{
		TOptional<FLinearColor> Hull, Deck, NonSkid, Bottom, Boot, Cove, Trim, Spars;
		TOptional<bool> bBoot;         // "boot": "none" takes the stripe off (it takes the hull's colour)
		TOptional<bool> bSparsPainted; // "spars": "bare" leaves the anodised aluminium
		TOptional<bool> bCove;         // "cove": "none" takes the cove stripe off
		TOptional<bool> bTrim;         // "trim": "none": no teak (the rails take the deck's colour)
		bool IsEmpty() const
		{
			return !Hull.IsSet() && !Deck.IsSet() && !NonSkid.IsSet() && !Bottom.IsSet() && !Boot.IsSet() && !Cove.IsSet() && !Trim.IsSet()
				&& !Spars.IsSet() && !bBoot.IsSet() && !bSparsPainted.IsSet() && !bCove.IsSet() && !bTrim.IsSet();
		}
	};
	struct FWear
	{
		/** The texture loop's ladder (docs/texture-loop): 0 new, 1 months, 2 club, 3 decades kept, 4 neglected; -1: none. */
		int32 Level = -1;
		/** Or the exact pair ("ageYears", "care"), which beats the level. */
		TOptional<float> AgeYears, Care;
		bool IsEmpty() const { return Level < 0 && !AgeYears.IsSet(); }
	};
	struct FSails
	{
		TOptional<FLinearColor> Cloth;
		TOptional<FString> Number;     // digits only, at most MaxSailDigits; empty: no number
		TOptional<bool> bClassMark;
		bool IsEmpty() const { return !Cloth.IsSet() && !Number.IsSet() && !bClassMark.IsSet(); }
	};
	struct FLines
	{
		/** A colourway's column in T_RopeColourways (Inputs/rope/colourways.json order) per role; -1: the boat's own. */
		int32 Column[int32(ELine::Count)] = { -1, -1, -1, -1 };
		bool IsEmpty() const { for (int32 C : Column) if (C >= 0) return false; return true; }
	};

	int32 Version = CurrentVersion;
	FString Id;        // lower-case letters, digits and hyphens; a built-in's starts "builtin-"
	FString Name;      // what the player sees
	FString BoatId;    // the class she was made for (FSailSave::BoatId); another class takes what fits
	bool bBuiltIn = false;
	FPaint Paint;
	FWear Wear;
	FSails Sails;
	FLines Lines;

	enum class EResult : uint8 { Ok, Refused, Invalid };
	/** Reads a skin's JSON text. Refused: over the size cap or a newer version. Invalid: not a skin. */
	static EResult FromJson(const FString& Text, FBoatSkin& Out, FString* OutMessage = nullptr);
	FString ToJson() const;

	/** Puts the paint, the wear level's channels and the sail number on a livery (BoatLivery.h). */
	void ApplyTo(FBoatLivery& L, int32 BoatType) const;
	/** The wear as M_BoatSurface's Age (years) and Care (0..1). False where the skin has none, or where it is the club
	 *  level the boats already wear unset (docs/hero-ageing). */
	bool AgeCare(float& OutAgeYears, float& OutCare) const;
	/** The colourway column each rope look draws with: identity, but for the roles this skin colours. Out has 256 entries. */
	void RopeColumns(uint8* Out) const;

	// Ids.
	static const TCHAR* WearLevelId(int32 Level);                 // "new", "months", "club", "classic", "neglected"
	static int32 WearLevelIndex(const FString& LevelId);               // -1 if unknown
	static FText WearLevelName(int32 Level);
	static const TCHAR* LineId(ELine Line);
	static int32 NumRopeColourways();
	static const TCHAR* RopeColourwayId(int32 Column);            // "" out of range
	static int32 RopeColourwayIndex(const FString& ColourwayId);           // -1 if unknown
	/** "#RRGGBB" (sRGB) to linear and back. False if the text is not that. */
	static bool ParseHex(const FString& Text, FLinearColor& Out);
	static FString ToHex(const FLinearColor& Linear);
	/** An id made safe: lower case, [a-z0-9-], at most MaxIdChars; empty if nothing is left. */
	static FString CleanId(const FString& In);
	/** Typed text made safe for a name: letters, digits, spaces and . , ' & - / at most MaxNameChars. */
	static FString CleanName(const FString& In);
};

/**
 * Where skins live. Built-in skins are made in code from the boat catalogue's colour schemes (BoatLivery.h), so they
 * cost no files; a player's own are Saved/Skins/<id>.skin.json beside the save. The save (FSailSave::BoatSkins) records
 * only which skin each boat wears.
 */
namespace BoatSkinStore
{
	/** Saved/Skins. */
	SAILINGSIM_API FString Dir();
	/** The built-in skins of a class (by EBoatType as int), in menu order. */
	SAILINGSIM_API TArray<FBoatSkin> BuiltIn(int32 BoatType);
	/** The player's own skins for a class (files made for another class are left out), by name. Unreadable files are
	 *  skipped with a log line. */
	SAILINGSIM_API TArray<FBoatSkin> Mine(int32 BoatType);
	/** A skin by id: a built-in of that class, else the player's file. */
	SAILINGSIM_API bool Find(int32 BoatType, const FString& SkinId, FBoatSkin& Out);
	/** Writes a player's skin (atomic). A built-in id, or no id, is refused. */
	SAILINGSIM_API bool Save(const FBoatSkin& Skin);
	SAILINGSIM_API bool Delete(const FString& SkinId);
	/** An id not yet used by a file, from a name ("my-navy", "my-navy-2"). */
	SAILINGSIM_API FString FreeId(const FString& Name);
	/** The skin a class's boat wears now: -SailingSkin=<id> (stills), else the save's choice. False: none (the class's own look). */
	SAILINGSIM_API bool Active(int32 BoatType, FBoatSkin& Out);
}
