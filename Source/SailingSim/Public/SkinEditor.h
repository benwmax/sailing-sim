#pragma once

#include "CoreMinimal.h"
#include "BoatSkin.h"

/**
 * Boat skins (docs/skins/README.md): what the Customize screen edits, as plain logic so the tests can drive it without
 * Slate. A draft skin for one class of boat, started from the skin she wears (or from her class's own look), with every
 * change undoable; what Use would write is decided here (SavePlan) and done by Use.
 *
 * Nothing here touches a boat: the screen shows the draft on the showroom's boat (ASailboatPawn::SetSkinPreview) whenever
 * the revision moves.
 */
struct SAILINGSIM_API FSkinEditor
{
	/** The painted parts, in the Paint tab's order. */
	enum class EPart : uint8 { Hull, Deck, NonSkid, Bottom, Boot, Cove, Trim, Spars, Count };
	static constexpr int32 MaxUndo = 50;

	/** Starts on a class's boat with the skin her save names (none: her class's own look). */
	void Open(int32 InBoatType);
	/** The same from a given skin (null: the class's own look): the tests' way in. */
	void OpenWith(int32 InBoatType, const FBoatSkin* Worn);

	int32 GetBoatType() const { return BoatType; }
	const FBoatSkin& GetDraft() const { return Draft; }
	/** The skin the draft started from or was last saved as: its id (empty: the class's own look) and whether it is built in. */
	const FString& GetLoadedId() const { return Baseline.Id; }
	bool IsLoadedBuiltIn() const { return Baseline.bBuiltIn; }
	/** The draft differs from what it started from. */
	bool IsDirty() const;
	/** Counts every change of the draft (edits, loads, undo and redo): the screen previews when it moves. */
	uint32 GetRevision() const { return Revision; }

	// Edits. Each is one undo step, except that repeated changes of one value (a slider dragged) fold into one.
	/** Takes a whole skin as the draft (null: the class's own look) and makes it what the draft is compared to. */
	void Load(const FBoatSkin* Skin);
	void SetPartColour(EPart Part, const FLinearColor& Colour);
	/** Back to the class's own colour for that part. */
	void ClearPart(EPart Part);
	/** The boot stripe off, or the spars left bare aluminium (the other parts: as ClearPart). */
	void SetPartOff(EPart Part);
	TOptional<FLinearColor> PartColour(EPart Part) const;
	bool IsPartOff(EPart Part) const;
	static bool PartCanBeOff(EPart Part) { return Part == EPart::Boot || Part == EPart::Spars; }
	static const TCHAR* PartName(EPart Part);
	/** A wear level (FBoatSkin's ladder), or -1 for the class's own. */
	void SetWearLevel(int32 Level);
	void SetSailCloth(const TOptional<FLinearColor>& Cloth);
	/** Digits only are kept; unset: the class's own number; empty: none. */
	void SetSailNumber(const TOptional<FString>& Number);
	void SetClassMark(const TOptional<bool>& bMark);
	/** A rope role's colourway column, or -1 for the boat's own. */
	void SetLine(FBoatSkin::ELine Line, int32 Column);
	void SetName(const FString& Name);
	/** A look at random from real ones: one of the class's built-in paint schemes, a wear level short of neglected, and
	 *  rope colours (port red and starboard green kept, as the convention has them). One undo step. */
	void Surprise(FRandomStream& Random);

	bool CanUndo() const { return At > 0; }
	bool CanRedo() const { return At + 1 < History.Num(); }
	bool Undo();
	bool Redo();

	/** What Use does with the draft. */
	enum class ESavePlan : uint8
	{
		ClassLook,   // an empty draft: the boat's skin is taken off
		Existing,    // an unchanged skin: the save names it
		Overwrite,   // a changed skin of the player's: its file is written again
		NewFile,     // a changed built-in, or a look made from nothing: a new file of the player's
	};
	ESavePlan SavePlan() const;
	/** The name a new file would get ("My navy"; the store numbers a second one). */
	FString NewName() const;
	/** Carries out SavePlan: writes the file if there is one to write, names the skin in the save and commits it. The draft
	 *  becomes that skin (no longer dirty). False if the file could not be written (nothing changes). */
	bool Use();
	/** Writes the draft as a new skin of the player's whatever it started from, and wears it. */
	bool SaveAsNew();
	/** Deletes the loaded skin's file (the player's own only) and goes back to the class's look, taking it off the boat if
	 *  she wore it. */
	bool DeleteLoaded();

	// What the screen shows for the things a skin names.
	static FString RopeName(int32 Column);
	/** A rope colourway's main colour, for its chip. */
	static FLinearColor RopeChip(int32 Column);

private:
	int32 BoatType = 0;
	FBoatSkin Draft, Baseline;
	TArray<FBoatSkin> History;
	int32 At = 0;
	int32 LastEdit = 0;
	uint32 Revision = 0;
	/** Records the draft after an edit; Edit names the value changed (0: never folded into the step before). */
	void Record(int32 Edit);
	TOptional<FLinearColor>& PartRef(EPart Part);
	bool WriteAs(const FString& Id, const FString& Name);
};
