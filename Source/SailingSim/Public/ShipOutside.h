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
