// A ship's outside model from her export (docs/frigate-import/, ShipOutsideVisuals.cpp): the parts of
// /Game/Boats/<Folder>/Outside/ built in the ship's frame (the hull, decks, fittings, spars, rigging, sails, boats), read
// from the export's table Content/TerrainData/Ships/<Config>.sockets.json, each with the ship states it shows in. The
// parts on their own pivots (the wheel, the capstan) are not hers: the frames (ShipFrames.h) place those.
#pragma once

#include "CoreMinimal.h"

namespace ShipOutside
{
	/** The export's four ship states as bits (Frigate_sockets.json `states`). */
	enum : uint8
	{
		Underway = 1,   // sails set, guns housed
		Action = 2,     // sails set, guns run out, port lids open
		Clewed = 4,     // sails clewed up
		Anchored = 8,   // sails furled
		AllStates = 15
	};

	struct FPart
	{
		FString Name;        // the part ("Skin", "Running_Fore_Set"): the mesh is SM_<Folder>_<Name>
		FString Asset;       // the hero mesh's object path (/Game/Boats/Frigate/Outside/SM_Frigate_Skin.SM_Frigate_Skin)
		FString LightAsset;  // its light twin's, or "" where the export made none
		uint8 States = AllStates;   // the states it shows in
		int32 Triangles = 0;
	};

	/** The outside parts of an export table (its text): every `meshes` entry of group Outside in the ship's frame. False
	 *  with the reason when the text is not such a table. */
	SAILINGSIM_API bool ParseTable(const FString& Json, TArray<FPart>& Out, FString* Error = nullptr);

	/** The table's file for a ship by her config name (Commonwealth -> Content/TerrainData/Ships/Commonwealth.sockets.json). */
	SAILINGSIM_API FString TablePath(const FString& ConfigName);

	/** A deck's placed copy of a shared mesh (the export's `placed`, owner "ship", in a deck's collection: the berth deck's
	 *  hammock hooks, hammocks, mess tables, benches, kids and sea chests), in her frame (cm). */
	struct FDeckCopy
	{
		FString Part;        // the mesh's part name ("BerthHammock")
		FString Asset;       // the mesh's object path
		FString Deck;        // the walk map's deck ("Berth")
		FTransform Transform;
	};

	/** A lantern below (the export's `lights`): a point light in her frame, lit with its deck. */
	struct FLantern
	{
		FString Name;
		FString Deck;              // the walk map's deck ("Gun", "Berth", "Orlop")
		FVector LocationCm = FVector::ZeroVector;
		FLinearColor Colour = FLinearColor(1.f, 0.62f, 0.3f);
		float Lumens = 180.f;
		float RadiusCm = 0.f;      // 0: the deck lamps' reach
		bool bCastShadows = false;
	};

	struct FDeckTable
	{
		TArray<FDeckCopy> Copies;
		TArray<FLantern> Lanterns;
	};

	/** The decks' placed copies and lanterns of an export table (its text). False with the reason when the text is not
	 *  such a table; true with none for a table without them. */
	SAILINGSIM_API bool ParseDecks(const FString& Json, FDeckTable& Out, FString* Error = nullptr);

	/** The walk map's deck for the export's deck or collection name ("BerthDeck_Hammocks" -> "Berth", "GunDeck" -> "Gun",
	 *  "Orlop", "Hold"); "" for a collection that is no deck's (the framed parts, the lids). */
	SAILINGSIM_API FString WalkDeckOf(const FString& ExportDeck);

	/** A ship's deck table by her config name, read once (null without a table). */
	SAILINGSIM_API const FDeckTable* DecksFor(const char* ConfigName);

	/** A state's bit by the export's name ("underway"), 0 for another word. */
	SAILINGSIM_API uint8 StateBit(const FString& Name);

	/** The rig group a part's showing follows ("Fore", "Main", "Mizzen", "Spanker", "Headsails", "Staysails", "Spritsail")
	 *  for the running rigging and blocks exported per group and set (Running_Fore_Set, Blocks_Main_Clewed), "" for a part
	 *  shown by the ship's state as a whole. */
	SAILINGSIM_API FString GroupOf(const FString& PartName);

	/** The group a rig sail belongs to by its table name ("fore_course" -> "Fore", "jib" -> "Headsails",
	 *  "main_topmast_staysail" -> "Staysails"); the spritsail's group follows the fore. */
	SAILINGSIM_API FString GroupOfSail(const FString& SailName);
}
